"""Rota de upload de cronograma (M03, Task 4).

`POST /obras/<obra_id>/cronograma/importacoes` — recebe um cronograma
(.xml MSPDI ou .mpp), valida (extensão, tamanho, assinatura de conteúdo),
calcula o SHA-256 dos bytes, faz dedup por (obra, sha) contra importações
vivas, persiste em disco sob UPLOADS_PATH, cria os registros de auditoria
(CronogramaImportacao + eventos) e faz o parse SÍNCRONO logo em seguida.

O parse é síncrono de propósito nesta task: o .xml (MSPDI) roda in-process
via stdlib (sem JVM), então a resposta já sai 'parseado'. O .mpp delega ao
worker MPXJ isolado (services/mpp_parser.py) e, sem Java, devolve 422 com a
instrução de exportar como XML — nunca derruba a app.

`parse_cronograma`, `MppParserError` e `java_disponivel` são importados no
nível deste módulo para que os testes possam monkeypatchá-los aqui
(`views.cronograma_importacao.parse_cronograma`).
"""
from __future__ import annotations

import hashlib
import logging
import os
import time

# defusedxml, não a stdlib: barra "billion laughs"/entidades externas num
# upload .xml antes de qualquer processamento (o arquivo vem de um admin
# autenticado, mas a expansão derruba o worker gunicorn compartilhado).
import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException

from flask import Blueprint, jsonify, request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app import db
from decorators import cronograma_import_required
from models import (
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    CronogramaTarefaMapeamento,
    CronogramaVersao,
    Obra,
)
from services.cronograma_normalizacao import (
    NORMALIZADOR_VERSAO,
    NormalizacaoError,
    normalizar,
)
from services.cronograma_reconciliacao import reconciliar
from services.cronograma_versao_service import (
    DecisaoInvalida,
    EstadoInvalido,
    PendenciasSemDecisao,
    aplicar_versao,
    extrair_tarefas_atuais,
    restaurar_versao,
)
from services.mpp_parser import (
    MppParserError,
    java_disponivel,  # noqa: F401 — exposto para monkeypatch nos testes
    parse_cronograma,
)
from utils.tenant import get_tenant_admin_id

logger = logging.getLogger(__name__)

cronograma_importacao_bp = Blueprint('cronograma_importacao', __name__)

# Mensagens ao cliente para motivos cujo texto interno embute stderr da JVM
# (paths /nix/store, stack POI/MPXJ, versão do JDK). O detalhe completo fica
# em imp.erro/log server-side; ao cliente só a versão sem fingerprint de infra.
_MSG_CLIENTE_GENERICA = {
    'arquivo_corrompido': 'O arquivo .mpp está corrompido ou não é um MS '
                          'Project válido.',
    'erro_mpxj': 'Não foi possível ler o arquivo .mpp.',
}

# Teto de upload — cronogramas MS Project reais ficam bem abaixo disso; o
# limite protege disco/memória de arquivos absurdos ou maliciosos.
TAMANHO_MAX = 20 * 1024 * 1024  # 20 MB

# Extensões aceitas e o mapeamento origem/parser correspondente.
_EXTENSOES = {'.xml', '.mpp'}
# Assinatura OLE2 (Compound File Binary) — todo .mpp legítimo começa com ela.
_MAGIC_OLE2 = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
# Namespace/raiz obrigatório de um arquivo MSPDI ("Salvar como XML").
_RAIZ_MSPDI = '{http://schemas.microsoft.com/project}Project'


def _erro(mensagem: str, status: int, **extra):
    """Resposta JSON de erro uniforme."""
    corpo = {'erro': mensagem}
    corpo.update(extra)
    return jsonify(corpo), status


def _base_uploads() -> str:
    """Raiz de armazenamento (lida a cada request para respeitar monkeypatch
    de UPLOADS_PATH nos testes)."""
    return os.environ.get(
        'UPLOADS_PATH', os.path.join(os.getcwd(), 'static', 'uploads')
    )


@cronograma_importacao_bp.route(
    '/obras/<int:obra_id>/cronograma/importacoes', methods=['POST']
)
@cronograma_import_required
def importar_cronograma(obra_id):
    """Recebe e processa um upload de cronograma para a obra do tenant."""
    # 1. Obra precisa existir DENTRO do tenant do usuário.
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if obra is None:
        return _erro('Obra não encontrada para este usuário.', 404)

    # 2. Arquivo presente, extensão, tamanho e assinatura de conteúdo.
    arquivo = request.files.get('arquivo')
    if arquivo is None or not (arquivo.filename or '').strip():
        return _erro("Envie o arquivo no campo 'arquivo'.", 422)

    ext = os.path.splitext(arquivo.filename)[1].lower()
    if ext not in _EXTENSOES:
        return _erro(
            'Extensão não suportada — envie o cronograma como .xml (MSPDI) '
            'ou .mpp.',
            422,
        )

    conteudo = arquivo.read()
    tamanho = len(conteudo)
    if tamanho == 0:
        return _erro('Arquivo vazio.', 422)
    if tamanho > TAMANHO_MAX:
        return _erro(
            f'Arquivo excede o limite de {TAMANHO_MAX // (1024 * 1024)} MB.',
            422,
        )

    if ext == '.mpp':
        if not conteudo.startswith(_MAGIC_OLE2):
            return _erro(
                'O arquivo .mpp não é um MS Project válido (assinatura OLE2 '
                'ausente).',
                422,
            )
    else:  # .xml — precisa ser MSPDI de verdade, antes de persistir
        try:
            raiz = ET.fromstring(conteudo)
        except DefusedXmlException:
            # DOCTYPE/entidades/refs externas: MSPDI legítimo não tem nada
            # disso — é payload malicioso (billion laughs, XXE).
            return _erro('O arquivo .xml contém construções não permitidas '
                         '(entidades/DTD) e foi rejeitado.', 422)
        except ET.ParseError:
            return _erro('O arquivo .xml não é um XML válido.', 422)
        if raiz.tag != _RAIZ_MSPDI:
            return _erro(
                'O arquivo .xml não é um cronograma MSPDI do MS Project. No '
                'MS Project: Arquivo → Salvar como → tipo XML (.xml).',
                422,
            )

    # 3. Nome seguro e hash dos bytes.
    nome_seguro = secure_filename(arquivo.filename) or f'cronograma{ext}'
    sha256 = hashlib.sha256(conteudo).hexdigest()

    # 4. Dedup — mesma obra + mesmo conteúdo em importação ainda viva.
    existente = (
        CronogramaImportacao.query.filter(
            CronogramaImportacao.obra_id == obra_id,
            CronogramaImportacao.arquivo_sha256 == sha256,
            CronogramaImportacao.status.notin_(['falhou', 'cancelado']),
        ).first()
    )
    if existente is not None:
        return _erro(
            'Este cronograma já foi importado para esta obra.',
            409,
            importacao_existente_id=existente.id,
        )

    # 5. Persistir em disco e criar os registros de auditoria.
    destino_dir = os.path.join(
        _base_uploads(), 'cronograma', str(admin_id), str(obra_id)
    )
    os.makedirs(destino_dir, exist_ok=True)
    destino_path = os.path.join(destino_dir, f'{sha256}{ext}')
    with open(destino_path, 'wb') as fh:
        fh.write(conteudo)

    imp = CronogramaImportacao(
        obra_id=obra_id,
        admin_id=admin_id,
        arquivo_nome=nome_seguro,
        arquivo_tamanho=tamanho,
        arquivo_sha256=sha256,
        arquivo_path=destino_path,
        origem='upload_mspdi' if ext == '.xml' else 'upload_mpp',
        parser_nome='mspdi_stdlib' if ext == '.xml' else 'mpxj',
        status='recebido',
        criado_por_id=current_user.id,
    )
    db.session.add(imp)
    try:
        db.session.flush()  # obtém imp.id sem committar; dispara o índice único
    except IntegrityError:
        # Corrida: outro POST idêntico (mesma obra+sha) inseriu entre o SELECT
        # de dedup e este flush. O índice parcial uq_cron_imp_obra_sha (M02) é
        # o backstop — devolvemos o mesmo 409 amigável, não um 500 opaco.
        db.session.rollback()
        existente = CronogramaImportacao.query.filter(
            CronogramaImportacao.obra_id == obra_id,
            CronogramaImportacao.arquivo_sha256 == sha256,
            CronogramaImportacao.status.notin_(['falhou', 'cancelado']),
        ).first()
        return _erro(
            'Este cronograma já foi importado para esta obra.', 409,
            importacao_existente_id=existente.id if existente else None,
        )

    db.session.add(CronogramaImportacaoEvento(
        importacao_id=imp.id,
        admin_id=admin_id,
        evento='upload',
        detalhes={'tamanho': tamanho, 'sha256': sha256},
        usuario_id=current_user.id,
    ))

    # 6. Parse síncrono — um único commit por ramo (o flush acima já deu o id).
    inicio = time.monotonic()
    try:
        dados = parse_cronograma(destino_path)
    except MppParserError as exc:
        imp.status = 'falhou'
        imp.erro = exc.mensagem  # completo (server-side, para suporte/auditoria)
        logger.warning('parse de cronograma falhou importacao=%s motivo=%s: %s',
                       imp.id, exc.motivo, exc.mensagem)
        db.session.add(CronogramaImportacaoEvento(
            importacao_id=imp.id,
            admin_id=admin_id,
            evento='parse_erro',
            detalhes={'motivo': exc.motivo},
            usuario_id=current_user.id,
        ))
        db.session.commit()
        # Ao cliente: mensagem sem fingerprint de infra para os motivos que
        # embutem stderr da JVM; os demais (java_indisponivel, timeout, ...)
        # já têm texto acionável e seguro.
        msg_cliente = _MSG_CLIENTE_GENERICA.get(exc.motivo, exc.mensagem)
        return _erro(msg_cliente, 422, importacao_id=imp.id)

    tempo_parse_ms = int((time.monotonic() - inicio) * 1000)
    imp.json_bruto = dados
    imp.status = 'parseado'
    db.session.add(CronogramaImportacaoEvento(
        importacao_id=imp.id,
        admin_id=admin_id,
        evento='parse_ok',
        detalhes={
            'tempo_parse_ms': tempo_parse_ms,
            'n_tarefas': len(dados['tarefas']),
        },
        usuario_id=current_user.id,
    ))

    # 7. Normalização determinística (M04): json_bruto → json_normalizado
    # validado por schema, com chaves estáveis e avisos — insumo do M05.
    try:
        normalizado = normalizar(dados)
    except NormalizacaoError as exc:
        # Parse OK mas o bruto não normaliza: quase sempre bug nosso de
        # schema/normalizador, não do usuário. Marca 'falhou' (o dedup
        # ignora 'falhou', então re-upload após correção é permitido).
        imp.status = 'falhou'
        imp.erro = str(exc)
        logger.error('normalização falhou importacao=%s: %s', imp.id, exc)
        db.session.add(CronogramaImportacaoEvento(
            importacao_id=imp.id,
            admin_id=admin_id,
            evento='normalizacao_erro',
            detalhes={'erro': str(exc)[:500]},
            usuario_id=current_user.id,
        ))
        db.session.commit()
        return _erro('O cronograma foi lido mas não pôde ser normalizado. '
                     'Registro salvo para análise.', 422, importacao_id=imp.id)

    imp.json_normalizado = normalizado
    imp.normalizador_versao = NORMALIZADOR_VERSAO
    imp.status = 'normalizado'
    db.session.add(CronogramaImportacaoEvento(
        importacao_id=imp.id,
        admin_id=admin_id,
        evento='normalizado',
        detalhes=normalizado['contadores'],
        usuario_id=current_user.id,
    ))
    db.session.commit()
    return jsonify({'importacao_id': imp.id, 'status': 'normalizado'}), 201


# ─────────────────────────────────────────────────────────────────────────────
# M05 — reconciliação, decisão manual, aplicação e restauração
# ─────────────────────────────────────────────────────────────────────────────

def _importacao_do_tenant(obra_id, importacao_id, admin_id):
    """(obra, imp) do tenant ou (None, None) — 404 na chamada."""
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if obra is None:
        return None, None
    imp = CronogramaImportacao.query.filter_by(
        id=importacao_id, obra_id=obra_id, admin_id=admin_id).first()
    return obra, imp


def _mapeamento_para_json(mp):
    det = mp.detalhes or {}
    return {
        'id': mp.id,
        'id_temp': det.get('id_temp'),
        'tarefa_atual_id': mp.tarefa_atual_id,
        'chave_nova': mp.chave_nova,
        'tipo': det.get('tipos') or [mp.tipo],
        'nivel_match': det.get('nivel_match'),
        'score': mp.score,
        'decisao_requerida': bool(det.get('decisao_requerida')),
        'candidatos': det.get('candidatos') or [],
        'detalhes': det.get('diff') or {},
        'decisao': det.get('decisao'),
        'origem_decisao': mp.origem_decisao,
        'decidido_por_id': mp.decidido_por_id,
    }


@cronograma_importacao_bp.route(
    '/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>'
    '/reconciliar', methods=['POST']
)
@cronograma_import_required
def reconciliar_importacao(obra_id, importacao_id):
    """Roda a reconciliação (Task 1) contra as tarefas vivas e persiste
    relatorio_diff + mapeamentos; re-executável enquanto não aplicada."""
    admin_id = get_tenant_admin_id()
    obra, imp = _importacao_do_tenant(obra_id, importacao_id, admin_id)
    if imp is None:
        return _erro('Importação não encontrada para esta obra.', 404)
    if imp.status not in ('normalizado', 'aguardando_revisao'):
        return _erro(
            f"Importação está '{imp.status}' — reconciliação exige "
            f"'normalizado' (ou re-execução em 'aguardando_revisao').", 409)

    rel = reconciliar(extrair_tarefas_atuais(obra_id, admin_id),
                      imp.json_normalizado)
    imp.relatorio_diff = rel
    imp.status = 'aguardando_revisao'

    # Re-reconciliar regrava os mapeamentos (dados derivados do diff);
    # decisões antigas caem — o diff pode ter mudado de forma.
    CronogramaTarefaMapeamento.query.filter_by(
        importacao_id=imp.id).delete()
    for m in rel['mapeamentos']:
        db.session.add(CronogramaTarefaMapeamento(
            importacao_id=imp.id,
            admin_id=admin_id,
            tarefa_atual_id=m['tarefa_atual_id'],
            chave_nova=m['chave_nova'],
            tipo=m['tipo'][0],
            score=m['score'],
            origem_decisao=None if m['decisao_requerida'] else 'auto',
            detalhes={
                'id_temp': m['id_temp'],
                'tipos': m['tipo'],
                'nivel_match': m['nivel_match'],
                'decisao_requerida': m['decisao_requerida'],
                'candidatos': m['candidatos'],
                'diff': m['detalhes'],
            },
        ))
    pendencias = sum(1 for m in rel['mapeamentos'] if m['decisao_requerida'])
    db.session.add(CronogramaImportacaoEvento(
        importacao_id=imp.id,
        admin_id=admin_id,
        evento='reconciliado',
        detalhes={'resumo': rel['resumo'], 'pendencias': pendencias},
        usuario_id=current_user.id,
    ))
    db.session.commit()
    return jsonify({
        'importacao_id': imp.id,
        'status': imp.status,
        'resumo': rel['resumo'],
        'pendencias': pendencias,
        'sugestoes_split_merge': rel['sugestoes_split_merge'],
    }), 200


@cronograma_importacao_bp.route(
    '/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>/diff'
)
@cronograma_import_required
def diff_importacao(obra_id, importacao_id):
    """Relatório de reconciliação + estado das decisões, para a revisão."""
    admin_id = get_tenant_admin_id()
    obra, imp = _importacao_do_tenant(obra_id, importacao_id, admin_id)
    if imp is None:
        return _erro('Importação não encontrada para esta obra.', 404)
    if not imp.relatorio_diff:
        return _erro('Importação ainda não foi reconciliada.', 409)
    mapeamentos = (CronogramaTarefaMapeamento.query
                   .filter_by(importacao_id=imp.id)
                   .order_by(CronogramaTarefaMapeamento.id)
                   .all())
    return jsonify({
        'importacao_id': imp.id,
        'status': imp.status,
        'relatorio_diff': imp.relatorio_diff,
        'mapeamentos': [_mapeamento_para_json(mp) for mp in mapeamentos],
    }), 200


@cronograma_importacao_bp.route(
    '/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>'
    '/mapeamentos/<int:mapeamento_id>', methods=['PATCH']
)
@cronograma_import_required
def decidir_mapeamento(obra_id, importacao_id, mapeamento_id):
    """Registra a decisão manual de um mapeamento pendente
    (acao: casar|arquivar|nova; casar exige chave_nova)."""
    admin_id = get_tenant_admin_id()
    obra, imp = _importacao_do_tenant(obra_id, importacao_id, admin_id)
    if imp is None:
        return _erro('Importação não encontrada para esta obra.', 404)
    if imp.status != 'aguardando_revisao':
        return _erro(
            f"Importação está '{imp.status}' — decisões só em "
            f"'aguardando_revisao'.", 409)
    mp = CronogramaTarefaMapeamento.query.filter_by(
        id=mapeamento_id, importacao_id=imp.id, admin_id=admin_id).first()
    if mp is None:
        return _erro('Mapeamento não encontrado nesta importação.', 404)
    det = dict(mp.detalhes or {})
    if not det.get('decisao_requerida'):
        return _erro('Este mapeamento não requer decisão.', 422)

    corpo = request.get_json(silent=True) or {}
    acao = corpo.get('acao')
    if acao not in ('casar', 'arquivar', 'nova'):
        return _erro("Campo 'acao' deve ser casar, arquivar ou nova.", 422)
    decisao = {'acao': acao}
    if acao == 'casar':
        chave = corpo.get('chave_nova')
        if not chave:
            return _erro("Ação 'casar' exige 'chave_nova'.", 422)
        decisao['chave_nova'] = chave

    det['decisao'] = decisao
    mp.detalhes = det
    mp.origem_decisao = 'manual'
    mp.decidido_por_id = current_user.id
    db.session.add(CronogramaImportacaoEvento(
        importacao_id=imp.id,
        admin_id=admin_id,
        evento='revisao_alterada',
        detalhes={'mapeamento_id': mp.id, 'id_temp': det.get('id_temp'),
                  'decisao': decisao},
        usuario_id=current_user.id,
    ))
    db.session.commit()
    return jsonify(_mapeamento_para_json(mp)), 200


@cronograma_importacao_bp.route(
    '/obras/<int:obra_id>/cronograma/importacoes/<int:importacao_id>'
    '/aplicar', methods=['POST']
)
@cronograma_import_required
def aplicar_importacao(obra_id, importacao_id):
    """Aplica a importação como nova versão (Task 2). 422 se ainda há
    pendências sem decisão; 409 para estado inválido/concorrência."""
    admin_id = get_tenant_admin_id()
    obra, imp = _importacao_do_tenant(obra_id, importacao_id, admin_id)
    if imp is None:
        return _erro('Importação não encontrada para esta obra.', 404)

    decisoes = {}
    for mp in CronogramaTarefaMapeamento.query.filter_by(
            importacao_id=imp.id).all():
        det = mp.detalhes or {}
        if det.get('decisao') and det.get('id_temp') is not None:
            decisoes[det['id_temp']] = det['decisao']

    try:
        versao = aplicar_versao(imp.id, decisoes, current_user.id)
    except PendenciasSemDecisao as exc:
        return _erro(str(exc), 422, pendencias=exc.id_temps)
    except DecisaoInvalida as exc:
        return _erro(str(exc), 422)
    except EstadoInvalido as exc:
        return _erro(str(exc), 409)
    return jsonify({
        'importacao_id': imp.id,
        'status': 'aplicado',
        'versao_id': versao.id,
        'versao_numero': versao.numero,
    }), 200


@cronograma_importacao_bp.route(
    '/obras/<int:obra_id>/cronograma/versoes/<int:versao_id>/restaurar',
    methods=['POST']
)
@cronograma_import_required
def restaurar_versao_endpoint(obra_id, versao_id):
    """Rollback: restaura o cronograma ao snapshot da versão (Task 3)."""
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if obra is None:
        return _erro('Obra não encontrada para este usuário.', 404)
    versao = CronogramaVersao.query.filter_by(
        id=versao_id, obra_id=obra_id, admin_id=admin_id).first()
    if versao is None:
        return _erro('Versão não encontrada para esta obra.', 404)

    try:
        nova = restaurar_versao(versao.id, current_user.id)
    except EstadoInvalido as exc:
        return _erro(str(exc), 409)
    return jsonify({
        'versao_id': nova.id,
        'versao_numero': nova.numero,
        'restaurada_de': versao.numero,
        'status': 'ativa',
    }), 200
