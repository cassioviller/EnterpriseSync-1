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
from models import CronogramaImportacao, CronogramaImportacaoEvento, Obra
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
    db.session.commit()
    return jsonify({'importacao_id': imp.id, 'status': 'parseado'}), 201
