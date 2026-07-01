"""Importa o JSON físico-financeiro (snapshot Planilha1 + cronograma) e deixa a
obra inteira planejada — agora pela CADEIA COMERCIAL CANÔNICA completa:

    Insumo → Orçamento → Proposta → (aprovação) → Obra + ItemMedicaoComercial
           → ObraServicoCusto → cronograma físico-financeiro + medições + caixa.

Arquitetura híbrida (decisão 2026-06-24):
  • a cadeia comercial (Orçamento/Proposta/IMC/OSC) nasce do mesmo código de
    produção, disparando o evento `proposta_aprovada` com `skip_contabil=True`
    (importar NÃO gera lançamento contábil);
  • os específicos físico-financeiros (cronograma raiz+folhas COM as datas do
    .mpp, vínculos peso, custo veks/fat, MedicaoContrato e snapshot) ficam aqui,
    porque o materializador canônico de cronograma não carrega datas por tarefa.

Idempotente e tenant-scoped.
"""
from __future__ import annotations

import calendar
import logging
import os
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

CENTAVO = Decimal("0.01")

# Base das fotos dos RDOs: uma subpasta por dia (fotos_rdos/AAAA-MM-DD/) com as
# imagens numeradas 1.jpg, 2.jpg… A legenda de cada foto vem no JSON (ver
# _materializar_fotos_rdo e o documento RDO.md). Sobrescrevível por ambiente/teste.
FOTOS_RDO_BASE = os.environ.get('FOTOS_RDO_BASE', 'fotos_rdos')

_MESES_ABREV = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
                'jul', 'ago', 'set', 'out', 'nov', 'dez']


def _parse_date(s):
    if not s:
        return None
    return date.fromisoformat(s[:10])


def _mes_bounds(chave):
    """'YYYY-MM' → (primeiro_dia, último_dia, 'abrev/yy'). Erro se inválida."""
    y, m = int(chave[:4]), int(chave[5:7])
    di = date(y, m, 1)
    df = date(y, m, calendar.monthrange(y, m)[1])
    return di, df, f"{_MESES_ABREV[m - 1]}/{str(y)[2:]}"


def _add_linhas_de_meses(Model, osc, admin_id, nome, meses, fonte, ordem):
    """Cria uma linha por mês a partir do mapa ``{'YYYY-MM': valor}`` (divisão
    mensal verbatim da Planilha1), nomeada com o nome-base e datada no mês (o
    rótulo 'mês/aa' é derivado das datas na UI). Devolve o próximo ``ordem``."""
    from app import db
    for chave in sorted(meses):
        valor = Decimal(str(meses[chave] or 0))
        if valor == 0:
            continue
        di, df, _rotulo = _mes_bounds(chave)  # rótulo é derivado das datas na UI
        db.session.add(Model(
            obra_servico_custo_id=osc.id, admin_id=admin_id,
            descricao=nome[:200], valor=valor, fonte=fonte,
            ordem=ordem, data_inicio=di, data_fim=df))
        ordem += 1
    return ordem


# ----------------------------------------------------------------------
# Resolvers de catálogo (Serviço / Insumo / Composição)
# ----------------------------------------------------------------------
def _resolver_servico(nome: str, categoria, admin_id: int):
    """Encontra ou cria um Serviço do catálogo (tenant-scoped) por nome."""
    from app import db
    from models import Servico
    nome = (nome or "Serviço")[:100]
    serv = Servico.query.filter_by(admin_id=admin_id, nome=nome).first()
    if serv is None:
        serv = Servico(nome=nome, categoria=(categoria or "Steel Frame")[:50],
                       unidade_medida="un", admin_id=admin_id, ativo=True)
        db.session.add(serv)
        db.session.flush()
    return serv


def _resolver_insumo(nome: str, valor: Decimal, admin_id: int, data_vig):
    """Encontra ou cria um Insumo por nome (tenant-scoped). Se for novo e ainda
    sem preço, registra um PrecoBaseInsumo vigente com `valor` (fator_comercial=1,
    para que coef×preço_técnico reproduza o valor do item)."""
    from app import db
    from models import Insumo, PrecoBaseInsumo
    nome = (nome or "Item")[:200]
    ins = Insumo.query.filter_by(admin_id=admin_id, nome=nome).first()
    if ins is None:
        ins = Insumo(nome=nome, admin_id=admin_id, tipo="MATERIAL", unidade="un",
                     coeficiente_padrao=Decimal("1"), fator_comercial=Decimal("1"))
        db.session.add(ins)
        db.session.flush()
    if not PrecoBaseInsumo.query.filter_by(insumo_id=ins.id).first():
        db.session.add(PrecoBaseInsumo(
            insumo_id=ins.id, admin_id=admin_id,
            valor=Decimal(str(valor or 0)),
            vigencia_inicio=data_vig or date.today()))
        db.session.flush()
    return ins


def _compor_servico(servico, itens, admin_id: int, data_vig) -> list:
    """Para cada item de custo da etapa, casa com um Insumo do catálogo e cria a
    ComposicaoServico (coeficiente=1). Devolve o `composicao_snapshot` no formato
    que OrcamentoItem/PropostaItem usam. O custo técnico de cada linha reproduz o
    valor (veks+fat) do item."""
    from app import db
    from models import ComposicaoServico
    snap: list = []
    for it in itens or []:
        nome = it.get("item") or "Custo"
        valor = Decimal(str(it.get("veks") or 0)) + Decimal(str(it.get("fat") or 0))
        ins = _resolver_insumo(nome, valor, admin_id, data_vig)
        comp = ComposicaoServico.query.filter_by(
            servico_id=servico.id, insumo_id=ins.id, admin_id=admin_id).first()
        if comp is None:
            db.session.add(ComposicaoServico(
                servico_id=servico.id, insumo_id=ins.id, admin_id=admin_id,
                coeficiente=Decimal("1"), unidade="un"))
        snap.append({
            "insumo_id": ins.id, "descricao": ins.nome, "unidade": "un",
            "coeficiente": 1.0,
            "preco_unitario": float(valor), "preco_embalagem": float(valor),
            "preco_tecnico_unitario": float(valor),
            "subtotal_unitario": float(valor),
        })
    db.session.flush()
    return snap


# ----------------------------------------------------------------------
# Idempotência: limpa todos os derivados da obra (comercial + físico)
# ----------------------------------------------------------------------
def _limpar_derivados(obra, admin_id: int):
    from app import db
    from models import (Orcamento, OrcamentoItem, Proposta, PropostaItem,
                        ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
                        ObraServicoCusto, ObraServicoCustoItem, TarefaCronograma,
                        MedicaoContrato)

    props = Proposta.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
    prop_ids = [p.id for p in props]
    orc_ids = [p.orcamento_id for p in props if p.orcamento_id]
    if prop_ids:
        PropostaItem.query.filter(
            PropostaItem.proposta_id.in_(prop_ids)).delete(synchronize_session=False)
        Proposta.query.filter(
            Proposta.id.in_(prop_ids)).delete(synchronize_session=False)
    if orc_ids:
        OrcamentoItem.query.filter(
            OrcamentoItem.orcamento_id.in_(orc_ids)).delete(synchronize_session=False)
        Orcamento.query.filter(
            Orcamento.id.in_(orc_ids)).delete(synchronize_session=False)

    ids_imc = [r[0] for r in db.session.query(ItemMedicaoComercial.id)
               .filter_by(obra_id=obra.id).all()]
    if ids_imc:
        ItemMedicaoCronogramaTarefa.query.filter(
            ItemMedicaoCronogramaTarefa.item_medicao_id.in_(ids_imc)).delete(synchronize_session=False)
    osc_ids_obra = [r[0] for r in db.session.query(ObraServicoCusto.id)
                    .filter_by(obra_id=obra.id, admin_id=admin_id).all()]
    if osc_ids_obra:
        ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids_obra)).delete(synchronize_session=False)
    ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    ItemMedicaoComercial.query.filter_by(obra_id=obra.id).delete(synchronize_session=False)
    TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    MedicaoContrato.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    db.session.flush()


# ----------------------------------------------------------------------
# Cronograma físico-financeiro (raiz + folhas COM datas do .mpp) + vínculos
# ----------------------------------------------------------------------
def _materializar_cronograma_mpp(obra, admin_id, tarefas_mpp):
    """Materializa o cronograma físico FIEL ao .mpp: uma TarefaCronograma por tarefa,
    na hierarquia do outline (pai = tarefa anterior de nível imediatamente menor).
    Independente de custo — TODA tarefa do .mpp aparece, inclusive físico-puras
    (FAZENDA/limpeza/desmobilização, sem custo) e resumos (que viram nós-pai). O
    modelo não tem coluna de 'resumo'/'marco'; a hierarquia via tarefa_pai_id já
    distingue pais (resumos) de folhas. Retorna {mpp_id: tarefa_cronograma_id}."""
    from app import db
    from models import TarefaCronograma

    tid_to_db: dict = {}
    ancestral_por_nivel: dict = {}   # nivel -> id da última tarefa vista nesse nível
    for ordem, t in enumerate(tarefas_mpp):
        nivel = int(t.get("nivel") or 1)
        pai_id = None
        for n in range(nivel - 1, 0, -1):
            if n in ancestral_por_nivel:
                pai_id = ancestral_por_nivel[n]
                break
        tarefa = TarefaCronograma(
            obra_id=obra.id, admin_id=admin_id,
            nome_tarefa=(t.get("nome") or "Tarefa")[:200],
            tarefa_pai_id=pai_id,
            data_inicio=_parse_date(t.get("inicio")),
            data_fim=_parse_date(t.get("fim")),
            duracao_dias=max(1, int(t.get("dias") or 1)),
            ordem=ordem, percentual_concluido=0)
        db.session.add(tarefa)
        db.session.flush()
        tid_to_db[t["id"]] = tarefa.id
        ancestral_por_nivel[nivel] = tarefa.id
        # níveis mais profundos deixam de ser ancestrais válidos
        for n in [x for x in ancestral_por_nivel if x > nivel]:
            del ancestral_por_nivel[n]
    return tid_to_db


def _vincular_etapa_tarefas(admin_id, imc, etapa, mpp, tid_to_db, avisos):
    """Vínculo OPCIONAL custo↔tarefa: liga o IMC da etapa às folhas do .mpp que
    carregam seu avanço físico (peso = dias). Etapa de PERÍODO (sem `tarefas_mpp`)
    não vincula — é custo, não medição física, e não vira tarefa no cronograma.
    Ver spec 2026-06-27-custo-cronograma-fieis-regime-medicao."""
    from app import db
    from models import ItemMedicaoCronogramaTarefa

    cron = etapa.get("cronograma", {}) or {}
    for tid in (cron.get("tarefas_mpp") or []):
        db_id = tid_to_db.get(tid)
        if db_id is None:
            avisos.append(f"Etapa '{etapa['nome']}': tarefa {tid} do .mpp não encontrada.")
            continue
        dias = max(1, int((mpp.get(tid) or {}).get("dias") or 1))
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc.id, cronograma_tarefa_id=db_id,
            admin_id=admin_id, peso=dias))
    db.session.flush()


def _rdos_sinteticos_do_pct_fisico(payload):
    """Quando o arquivo NÃO traz a seção `rdos` (físico real do documento), deriva
    UM "RDO de físico inicial" a partir do `pct_fisico` das tarefas FOLHA do
    cronograma (coluna %físico do MS Project). É isso que permite LANÇAR a
    porcentagem da obra direto do cronograma — SEM adicionar pessoas
    (`mao_de_obra=0`; o usuário adiciona mão de obra ao editar o RDO).

    Tarefas-resumo não entram (são rollup dos filhos → evitam dupla contagem).
    Retorna [] quando não há físico a lançar (cai no comportamento padrão).
    Ver spec 2026-06-30-pct-fisico-no-import-baia."""
    tarefas = payload.get('cronograma_tarefas', []) or []
    apont = [
        {'tarefa_mpp': t['id'], 'pct': float(t.get('pct_fisico') or 0)}
        for t in tarefas
        if not t.get('resumo') and float(t.get('pct_fisico') or 0) > 0
    ]
    if not apont:
        return []
    # Data do snapshot: geração do arquivo (precisa ser ≤ hoje p/ aparecer no card
    # de hoje, que chama calcular_progresso_geral_obra_v2 com date.today());
    # fallback p/ início do contrato; nunca no futuro.
    hoje = date.today()
    meta = payload.get('_meta') or {}
    contrato = payload.get('contrato') or {}
    data_snap = (_parse_date(meta.get('gerado_em'))
                 or _parse_date(contrato.get('data_inicio'))
                 or hoje)
    if data_snap > hoje:
        data_snap = hoje
    return [{
        'data': data_snap.isoformat(),
        'mao_de_obra': 0,
        'clima': 'Não informado',
        'comentario': 'Físico inicial importado do cronograma (%físico do MS Project).',
        'apontamentos': apont,
    }]


def _resolver_arquivo_foto(pasta, indice, nome):
    """Localiza o arquivo de uma foto dentro de `pasta` (fotos_rdos/<data>/).

    - Se `nome` foi informado no JSON, usa-o direto.
    - Senão, aplica a convenção posicional: a i-ésima foto da lista é o arquivo
      `(indice+1).<ext>` (1.jpg, 2.png…), na ordem em que o usuário numerou.
    Retorna o caminho absoluto/relativo do arquivo, ou None se não existir.
    """
    import glob
    if nome:
        cam = os.path.join(pasta, nome)
        return cam if os.path.isfile(cam) else None
    achados = sorted(glob.glob(os.path.join(pasta, f"{indice + 1}.*")))
    return achados[0] if achados else None


def _materializar_fotos_rdo(rdo, admin_id, dia, fotos):
    """Anexa as fotos de um RDO a partir da lista `fotos` do JSON.

    Cada item pode ser:
      - uma STRING → só a legenda; o arquivo é inferido pela ordem na pasta
        `fotos_rdos/<data>/` (1.<ext>, 2.<ext>…);
      - um OBJETO `{"arquivo": "1.jpg", "legenda": "..."}` → nome explícito.

    Reusa `salvar_foto_rdo` (mesma otimização WebP + base64 do upload da tela), de
    modo que a foto fica persistida no banco (sobrevive a deploy/restart). Fotos
    ausentes na pasta viram warning — NÃO quebram o import. Retorna nº de fotos
    criadas. Idempotência: o RDO é recriado no reimport e a FK ON DELETE CASCADE
    remove as RDOFoto antigas junto, então não duplica."""
    if not fotos:
        return 0
    from app import db
    from models import RDOFoto
    from services.rdo_foto_service import salvar_foto_rdo
    from werkzeug.datastructures import FileStorage

    pasta = os.path.join(FOTOS_RDO_BASE, dia.isoformat())
    criadas = 0
    for i, f in enumerate(fotos):
        if isinstance(f, str):
            nome, legenda = None, f
        elif isinstance(f, dict):
            nome, legenda = f.get('arquivo'), (f.get('legenda') or '')
        else:
            continue
        caminho = _resolver_arquivo_foto(pasta, i, nome)
        if caminho is None:
            logger.warning(
                "[FF_IMPORT] RDO %s: foto %s não encontrada em %s (pulada)",
                dia.isoformat(), nome or (i + 1), pasta)
            continue
        try:
            with open(caminho, 'rb') as fh:
                fs = FileStorage(stream=fh, filename=os.path.basename(caminho))
                res = salvar_foto_rdo(fs, admin_id, rdo.id)
        except Exception as e:  # foto inválida/corrompida não derruba o import
            logger.warning("[FF_IMPORT] RDO %s: falha ao processar %s: %s",
                           dia.isoformat(), caminho, e)
            continue
        db.session.add(RDOFoto(
            admin_id=admin_id, rdo_id=rdo.id,
            # campos legados NOT NULL
            nome_arquivo=res['nome_original'],
            caminho_arquivo=res['arquivo_otimizado'],
            legenda=legenda, descricao=legenda,
            # v9.0 (arquivos físicos, backup)
            arquivo_original=res['arquivo_original'],
            arquivo_otimizado=res['arquivo_otimizado'],
            thumbnail=res['thumbnail'],
            nome_original=res['nome_original'],
            tamanho_bytes=res['tamanho_bytes'],
            ordem=i,
            # v9.0.4 (base64 — persistência no banco)
            imagem_original_base64=res['imagem_original_base64'],
            imagem_otimizada_base64=res['imagem_otimizada_base64'],
            thumbnail_base64=res['thumbnail_base64'],
        ))
        criadas += 1
    return criadas


# Colunas de RDOFoto copiadas ao preservar/restaurar (tudo menos id e rdo_id).
_FOTO_COLS = ('nome_arquivo', 'caminho_arquivo', 'legenda', 'descricao',
              'arquivo_original', 'arquivo_otimizado', 'thumbnail', 'nome_original',
              'tamanho_bytes', 'ordem', 'imagem_original_base64',
              'imagem_otimizada_base64', 'thumbnail_base64')


def _snapshot_fotos_por_data(rdos_antigos):
    """Copia as fotos dos RDOs antigos (indexadas por data) ANTES do reimport
    apagá-los. As fotos ficam em base64 no banco — persistentes —, então se o
    usuário apagar os arquivos da pasta `fotos_rdos/<data>/` para aliviar espaço,
    o reimport não deve perdê-las. Retorna {data_iso: [dict de colunas RDOFoto]}."""
    snap = {}
    for r in rdos_antigos:
        fotos = list(getattr(r, 'fotos', None) or [])
        if not fotos or not r.data_relatorio:
            continue
        snap.setdefault(r.data_relatorio.isoformat(), []).extend(
            {c: getattr(f, c) for c in _FOTO_COLS} for f in fotos)
    return snap


def _restaurar_fotos_preservadas(rdo, admin_id, snapshots):
    """Recria as RDOFoto preservadas (do snapshot) no RDO novo, com o mesmo
    conteúdo/base64. Usado quando a pasta do dia está vazia no reimport."""
    from app import db
    from models import RDOFoto
    for dados in snapshots:
        db.session.add(RDOFoto(admin_id=admin_id, rdo_id=rdo.id, **dados))
    return len(snapshots)


def _materializar_rdos(obra, admin_id, rdos, tid_to_db):
    """Cria os RDOs da obra a partir do payload (seção `rdos`), referenciando as
    tarefas pelo id do .mpp (traduzido por `tid_to_db`). Idempotente: apaga os RDOs
    da obra antes de recriar. Mão de obra é só realismo do documento (não gera
    custo). Retorna o nº de RDOs criados. Ver spec 2026-06-30-rdos-no-import-baia."""
    from app import db
    from models import (RDO, RDOMaoObra, RDOApontamentoCronograma, Funcionario,
                        CustoObra, NotificacaoCliente, MovimentacaoEstoque,
                        AlocacaoEquipe)

    if not rdos:
        return 0

    # Idempotência: remove RDOs anteriores desta obra. As filhas com ON DELETE
    # CASCADE (mão de obra, apontamentos, fotos…) somem junto; as que referenciam
    # o RDO SEM cascade precisam ser tratadas antes, senão o DELETE viola FK:
    #   - custo_obra: custo derivado do RDO (ex.: mão de obra) → removido junto;
    #   - notificacao_cliente / movimentacao_estoque / alocacao_equipe → desvincula
    #     (preserva o histórico, só solta o ponteiro para o RDO que vai sumir).
    antigos = RDO.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
    # Preserva as fotos já importadas (base64) por data, para não perdê-las quando
    # a pasta `fotos_rdos/<data>/` estiver vazia neste reimport (ver loop abaixo).
    fotos_snap = _snapshot_fotos_por_data(antigos)
    old_ids = [r.id for r in antigos]
    if old_ids:
        CustoObra.query.filter(CustoObra.rdo_id.in_(old_ids)).delete(
            synchronize_session=False)
        NotificacaoCliente.query.filter(NotificacaoCliente.rdo_id.in_(old_ids)).update(
            {NotificacaoCliente.rdo_id: None}, synchronize_session=False)
        MovimentacaoEstoque.query.filter(MovimentacaoEstoque.rdo_id.in_(old_ids)).update(
            {MovimentacaoEstoque.rdo_id: None}, synchronize_session=False)
        AlocacaoEquipe.query.filter(AlocacaoEquipe.rdo_gerado_id.in_(old_ids)).update(
            {AlocacaoEquipe.rdo_gerado_id: None}, synchronize_session=False)
        db.session.flush()
    for r in antigos:
        db.session.delete(r)
    db.session.flush()

    funcs = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).limit(10).all()
    criados = 0
    for item in rdos:
        dia = _parse_date(item.get('data'))
        if dia is None:
            continue
        rdo = RDO(
            numero_rdo=f"RDO-{obra.id}-{dia.strftime('%Y%m%d')}",
            obra_id=obra.id, admin_id=admin_id, criado_por_id=admin_id,
            data_relatorio=dia, local='Campo', status='Finalizado',
            clima_geral=(item.get('clima') or 'Não informado')[:50],
            precipitacao=(item.get('precipitacao') or '')[:20],
            comentario_geral=item.get('comentario') or '',
        )
        db.session.add(rdo)
        db.session.flush()

        qtd_mo = int(item.get('mao_de_obra') or 0)
        for f in funcs[:qtd_mo]:
            funcao_nome = getattr(getattr(f, 'funcao_ref', None), 'nome', None) \
                or getattr(f, 'funcao', None) or 'Operário'
            db.session.add(RDOMaoObra(
                rdo_id=rdo.id, admin_id=admin_id, funcionario_id=f.id,
                funcao_exercida=str(funcao_nome)[:100], horas_trabalhadas=8.0))

        for ap in (item.get('apontamentos') or []):
            db_id = tid_to_db.get(ap.get('tarefa_mpp'))
            if db_id is None:
                continue
            pct = float(ap.get('pct') or 0)
            db.session.add(RDOApontamentoCronograma(
                rdo_id=rdo.id, tarefa_cronograma_id=db_id, admin_id=admin_id,
                quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
                percentual_realizado=pct, percentual_planejado=None))

        # Regra de foto no reimport: se a pasta do dia tiver arquivos, ELA manda
        # (reconstrói). Se vier vazia (0 fotos criadas), preserva as que já
        # estavam no RDO — assim o usuário pode apagar os arquivos da raiz para
        # aliviar espaço sem perder as fotos já importadas (ficam em base64).
        criadas = _materializar_fotos_rdo(rdo, admin_id, dia, item.get('fotos'))
        if criadas == 0:
            preservadas = fotos_snap.get(dia.isoformat())
            if preservadas:
                _restaurar_fotos_preservadas(rdo, admin_id, preservadas)
        criados += 1

    db.session.flush()
    return criados


# ----------------------------------------------------------------------
# Orquestrador
# ----------------------------------------------------------------------
def importar_fisico_financeiro(payload: dict, admin_id: int) -> dict:
    from app import db
    from event_manager import EventManager
    from models import (Obra, Orcamento, OrcamentoItem, Proposta, PropostaItem,
                        ItemMedicaoComercial, ObraServicoCusto)
    from services.cliente_resolver import obter_ou_criar_cliente

    obra_j = payload['obra']
    contrato = payload.get('contrato', {})
    data_inicio = _parse_date(contrato.get('data_inicio')) or date.today()

    cliente = obter_ou_criar_cliente(nome=obra_j.get('cliente'), admin_id=admin_id)
    if cliente is None:
        raise ValueError(
            "O arquivo precisa de 'obra.cliente' (nome do cliente) — "
            "obrigatório para criar a obra."
        )
    codigo = obra_j.get('codigo_obra') or (obra_j.get('nome') or '')[:20]

    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if obra is None:
        obra = Obra(codigo=codigo, admin_id=admin_id, nome=obra_j.get('nome'),
                    data_inicio=data_inicio)
        db.session.add(obra)
    obra.nome = obra_j.get('nome')
    obra.valor_contrato = float(contrato.get('valor_venda') or 0)
    obra.data_inicio = data_inicio
    obra.data_previsao_fim = _parse_date(contrato.get('data_fim_cronograma'))
    obra.cliente_id = cliente.id
    db.session.flush()

    valor_venda = Decimal(str(contrato.get('valor_venda') or 0))
    avisos: list[str] = []

    # Idempotência: zera os derivados (comercial + físico) desta obra.
    _limpar_derivados(obra, admin_id)

    titulo = f"Físico-financeiro — {obra.nome or codigo}"[:255]

    # 1) ORÇAMENTO (catálogo: serviços + insumos + composição) ---------------
    orc = Orcamento(admin_id=admin_id, numero=f'FF-{obra.id}', titulo=titulo,
                    cliente_id=cliente.id, cliente_nome=cliente.nome,
                    status='convertido', criado_por=admin_id)
    db.session.add(orc)
    db.session.flush()

    # 2) PROPOSTA (back-link da obra ANTES de aprovar; sem cronograma_default) -
    proposta = Proposta(admin_id=admin_id, numero=f'FF-{obra.id}',
                        data_proposta=data_inicio, cliente_id=cliente.id,
                        cliente_nome=cliente.nome, titulo=titulo,
                        valor_total=valor_venda, obra_id=obra.id, status='enviada',
                        orcamento_id=orc.id)
    db.session.add(proposta)
    db.session.flush()

    etapa_por_pi: dict = {}     # proposta_item_id -> {etapa, veks, fat}
    custo_total_orc = Decimal('0')
    venda_total_orc = Decimal('0')
    for ordem, etapa in enumerate(payload.get('eap', []), start=1):
        custo = etapa.get('custo', {})
        veks = Decimal(str(custo.get('veks') or 0))
        fat = Decimal(str(custo.get('fat_direto') or 0))
        peso_pct = Decimal(str(custo.get('peso_pct') or 0))
        venda_item = (valor_venda * peso_pct).quantize(CENTAVO)
        nome_etapa = etapa['nome']

        servico = _resolver_servico(nome_etapa, etapa.get('grupo'), admin_id)
        snap = _compor_servico(servico, etapa.get('itens'), admin_id, data_inicio)
        custo_comp = sum((Decimal(str(l['subtotal_unitario'])) for l in snap), Decimal('0'))
        if custo_comp == 0:
            custo_comp = veks + fat  # etapa sem itens detalhados

        db.session.add(OrcamentoItem(
            admin_id=admin_id, orcamento_id=orc.id, ordem=ordem,
            servico_id=servico.id, descricao=nome_etapa[:500], unidade='un',
            quantidade=Decimal('1'), composicao_snapshot=snap,
            custo_unitario=custo_comp, preco_venda_unitario=venda_item,
            custo_total=custo_comp, venda_total=venda_item,
            lucro_total=venda_item - custo_comp))

        pi = PropostaItem(
            admin_id=admin_id, proposta_id=proposta.id, item_numero=ordem, ordem=ordem,
            descricao=nome_etapa[:500], quantidade=Decimal('1'), unidade='un',
            preco_unitario=venda_item, subtotal=venda_item, servico_id=servico.id,
            custo_unitario=custo_comp, composicao_snapshot=snap)
        db.session.add(pi)
        db.session.flush()
        etapa_por_pi[pi.id] = {'etapa': etapa, 'veks': veks, 'fat': fat}
        custo_total_orc += custo_comp
        venda_total_orc += venda_item

    orc.custo_total = custo_total_orc
    orc.venda_total = venda_total_orc
    orc.lucro_total = venda_total_orc - custo_total_orc
    db.session.flush()

    # 3) APROVAÇÃO canônica (skip contábil) → liga Obra + cria IMC + OSC -------
    EventManager.emit('proposta_aprovada', {
        'proposta_id': proposta.id,
        'cliente_nome': cliente.nome,
        'valor_total': float(valor_venda),
        'data_aprovacao': data_inicio.isoformat(),
        'skip_contabil': True,
    }, admin_id, raise_on_error=True)

    # 4) recupera IMC/OSC por PropostaItem e preenche custo + cronograma físico -
    mpp = {t['id']: t for t in payload.get('cronograma_tarefas', [])}
    # Cronograma físico = espelho do .mpp (todas as tarefas, no outline), criado UMA
    # vez e independente de custo. As etapas de custo só REFERENCIAM essas tarefas.
    tid_to_db = _materializar_cronograma_mpp(
        obra, admin_id, payload.get('cronograma_tarefas', []))
    imcs = ItemMedicaoComercial.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
    imc_por_pi = {i.proposta_item_id: i for i in imcs if i.proposta_item_id}
    for pi_id, info in etapa_por_pi.items():
        imc = imc_por_pi.get(pi_id)
        if imc is None:
            avisos.append(f"Etapa '{info['etapa']['nome']}' sem IMC após aprovação.")
            continue
        osc = ObraServicoCusto.query.filter_by(
            item_medicao_comercial_id=imc.id, admin_id=admin_id).first()
        if osc is not None:
            from models import ObraServicoCustoItem
            from services.cronograma_fisico_financeiro import recalcular_osc_dos_itens
            # Linhas de custo (insumos) da etapa = eap.itens (cada item vira linha
            # Veks e/ou Fat). Estas linhas são a fonte da verdade; os agregados da
            # OSC são derivados delas.
            ObraServicoCustoItem.query.filter_by(
                obra_servico_custo_id=osc.id).delete(synchronize_session=False)
            # Janela de desembolso default da linha = cronograma da etapa.
            cron_etapa = info['etapa'].get('cronograma', {}) or {}
            di_etapa = _parse_date(cron_etapa.get('inicio'))
            df_etapa = _parse_date(cron_etapa.get('fim'))
            ordem = 0
            for it in (info['etapa'].get('itens') or []):
                nome_it = (it.get('item') or 'Item')[:200]
                meses_v = it.get('meses_veks') or {}
                meses_f = it.get('meses_fat') or {}
                if meses_v or meses_f:
                    # Item com divisão mensal explícita (Planilha1, custo de
                    # período): uma linha por mês (nome-base, datada no mês; o
                    # rótulo 'mês/aa' é derivado das datas na UI), com o valor
                    # verbatim da planilha.
                    ordem = _add_linhas_de_meses(
                        ObraServicoCustoItem, osc, admin_id, nome_it[:180],
                        meses_v, 'veks', ordem)
                    ordem = _add_linhas_de_meses(
                        ObraServicoCustoItem, osc, admin_id, nome_it[:180],
                        meses_f, 'fat_direto', ordem)
                    continue
                v = Decimal(str(it.get('veks') or 0))
                f = Decimal(str(it.get('fat') or 0))
                if v > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=nome_it, valor=v, fonte='veks', ordem=ordem,
                        data_inicio=di_etapa, data_fim=df_etapa)); ordem += 1
                if f > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=nome_it, valor=f, fonte='fat_direto', ordem=ordem,
                        data_inicio=di_etapa, data_fim=df_etapa)); ordem += 1
            if ordem == 0:
                # Etapa sem itens detalhados no JSON → linhas do agregado.
                if info['veks'] > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=info['etapa']['nome'][:200], valor=info['veks'],
                        fonte='veks', ordem=ordem,
                        data_inicio=di_etapa, data_fim=df_etapa)); ordem += 1
                if info['fat'] > 0:
                    db.session.add(ObraServicoCustoItem(
                        obra_servico_custo_id=osc.id, admin_id=admin_id,
                        descricao=info['etapa']['nome'][:200], valor=info['fat'],
                        fonte='fat_direto', ordem=ordem,
                        data_inicio=di_etapa, data_fim=df_etapa)); ordem += 1
            db.session.flush()
            osc.fonte_outros = 'veks'
            osc.realizado_material = 0
            osc.realizado_mao_obra = 0
            osc.realizado_outros = 0
            recalcular_osc_dos_itens(osc)
        _vincular_etapa_tarefas(admin_id, imc, info['etapa'], mpp, tid_to_db, avisos)

    # 5) medições de contrato + snapshot do fluxo de caixa da planilha --------
    from models import MedicaoContrato
    for i, med in enumerate(payload.get('medicoes', [])):
        db.session.add(MedicaoContrato(
            obra_id=obra.id, admin_id=admin_id, nome=med.get('nome'),
            data=_parse_date(med.get('data')),
            pct=Decimal(str(med.get('pct') or 0)),
            recebido_no_mes=med.get('recebido_no_mes'),
            obs=med.get('obs'), ordem=i))

    obra.fluxo_caixa_planilha = payload.get('fluxo_caixa_mensal')

    # RDOs (físico real) a partir do payload; depois sincroniza o % das tarefas
    # pelo último apontamento. `tid_to_db` foi montado em _materializar_cronograma_mpp.
    # Sem seção `rdos`, deriva o físico do `pct_fisico` do cronograma (lança a
    # porcentagem da obra sem adicionar pessoas) — ver _rdos_sinteticos_do_pct_fisico.
    rdos = payload.get('rdos') or _rdos_sinteticos_do_pct_fisico(payload)
    _materializar_rdos(obra, admin_id, rdos, tid_to_db)
    db.session.flush()
    from utils.cronograma_engine import sincronizar_percentuais_obra
    sincronizar_percentuais_obra(obra.id, admin_id)

    db.session.commit()
    return {'obra_id': obra.id, 'orcamento_id': orc.id,
            'proposta_id': proposta.id, 'avisos': avisos}
