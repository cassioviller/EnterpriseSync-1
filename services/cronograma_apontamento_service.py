"""
Serviço único de apontamento de produção do cronograma.

M1 extraiu a fórmula duplicada de views/rdo.py e cronograma_views.py; o
M07 adiciona a semântica do M02 e as validações da spec
`2026-07-17-modulo-07-rdo.md` (plano bite-sized 2026-07-21):

- **Dupla escrita permanente** (sem feature-flag até M9/M10): os campos
  legados (`quantidade_executada_dia`, `quantidade_acumulada`,
  `percentual_realizado`) continuam preenchidos como sempre; os campos
  semânticos do M02 (`tipo_apontamento`, `percentual_acumulado`,
  `percentual_incremento_dia`, `quantidade_total_snapshot`,
  `unidade_snapshot`) passam a ser gravados SEMPRE.
- **Modo percentual novo**: o % ACUMULADO digitado vai para
  `percentual_acumulado` (raw — só passa de 100 com
  `permitir_sobreexecucao`); o incremento vai para
  `percentual_incremento_dia` (pode ser negativo em correção
  justificada); `quantidade_executada_dia`/`quantidade_acumulada` ficam
  **0.0** — fim do abuso de gravar incremento em campo de quantidade.
  (A spec pedia NULL; as colunas são NOT NULL desde a criação e o M07
  não faz migration — 0.0 é o neutro possível.)
- **Modo quantitativo**: semântica legada intacta (caracterização verde)
  + snapshot de total/unidade por linha: o % é derivado do
  `quantidade_total_snapshot` DA LINHA — mudar `quantidade_total` da
  tarefa nunca reinterpreta o histórico (problema 4 da spec).
- **Validações** (server-side; a UI espelha por cortesia):
  retrocesso exige `permitir_retrocesso=True` + `justificativa`
  (auditada em log estruturado — não há tabela de eventos de RDO);
  percentual digitado >100 exige `permitir_sobreexecucao=True`
  (o agregado `percentual_realizado` clampa em 100 mesmo assim);
  overshoot QUANTITATIVO continua com clamp em 100 + aviso (comportamento
  legado, travado por caracterização); marco só aceita 0 ou 100.
- O import físico-financeiro grava DIRETO no modelo (formato antigo) até
  o M9 — este serviço não é chamado por ele.

Responsabilidades que FICAM NO CALLER (sem mudança de comportamento):
  - validação de tenant / is_v2_active / is_cliente / parse do request;
  - filtro qty <= 0 (salvar_rdo_flexivel ignora; apontar_producao aceita 0);
  - flush/commit da sessão;
  - atualizar_percentual_tarefa (rollup do percentual_concluido da tarefa).
"""
from __future__ import annotations

import logging

from models import db, RDO, RDOApontamentoCronograma
from utils.cronograma_engine import calcular_progresso_rdo

logger = logging.getLogger(__name__)


class ApontamentoInvalido(ValueError):
    """Base das violações de apontamento (mensagem apta à UI).

    Subclasse de ValueError de propósito: os callers legados protegem o
    laço de parsing com `except (ValueError, TypeError)` — uma violação
    num item não pode derrubar o RDO inteiro.
    """


class RetrocessoNaoPermitido(ApontamentoInvalido):
    """Acumulado menor que o anterior sem permitir_retrocesso+justificativa."""


class SobreexecucaoNaoConfirmada(ApontamentoInvalido):
    """Percentual acumulado digitado acima de 100 sem confirmação explícita."""


class MarcoApenasZeroOuCem(ApontamentoInvalido):
    """Marco é binário: o percentual digitado só pode ser 0 ou 100."""


def modo_da_tarefa(tarefa) -> str:
    """Modo de apontamento que a UI deve oferecer para a tarefa (spec §4.1):
    'quantidade' quando há quantitativo E unidade; senão 'percentual'
    (marco incluído — sempre percentual binário)."""
    if getattr(tarefa, 'is_marco', False):
        return 'percentual'
    if (tarefa.quantidade_total and float(tarefa.quantidade_total) > 0
            and (tarefa.unidade_medida or '').strip()):
        return 'quantidade'
    return 'percentual'


def _is_marco(tarefa) -> bool:
    if getattr(tarefa, 'is_marco', False):
        return True
    dur = getattr(tarefa, 'duracao_dias', None)
    return dur is not None and int(dur) == 0


def recomputar_cadeia(tarefa_id: int, a_partir_de, admin_id: int) -> int:
    """Reprocessa em ordem cronológica ((data_relatorio, id) — desempate
    estável) os apontamentos da tarefa com `data_relatorio >= a_partir_de`,
    recalculando os DERIVADOS a partir do estado anterior à janela:

    - quantitativo: `quantidade_acumulada` = acumulado anterior + dia;
      `percentual_realizado` pelo `quantidade_total_snapshot` DA LINHA
      (senão total vigente da tarefa — linhas pré-M02);
    - percentual: `percentual_incremento_dia` = acumulado − anterior;
      `percentual_realizado` = clamp(0, 100, acumulado).

    NUNCA altera: `quantidade_executada_dia` (fato bruto do dia),
    `percentual_acumulado` digitado, snapshots, `percentual_planejado`
    (replanejamento M06 é o dono). Sem commit — roda na MESMA transação do
    caller (correção retroativa atômica, spec §12). Devolve o nº de linhas
    alteradas. Chamar após criar/editar/excluir apontamento retroativo.
    """
    from sqlalchemy import func as sqlfunc
    from models import TarefaCronograma

    tarefa = db.session.get(TarefaCronograma, tarefa_id)
    if tarefa is None:
        return 0

    # Estado ANTES da janela.
    acum = (
        db.session.query(sqlfunc.coalesce(
            sqlfunc.sum(RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio < a_partir_de,
        )
        .scalar()
    ) or 0.0
    ant = (
        db.session.query(RDOApontamentoCronograma.percentual_acumulado,
                         RDOApontamentoCronograma.percentual_realizado)
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio < a_partir_de,
        )
        .order_by(RDO.data_relatorio.desc(), RDOApontamentoCronograma.id.desc())
        .first()
    )
    pct_ant = 0.0
    if ant is not None:
        pct_ant = float(ant[0] if ant[0] is not None else (ant[1] or 0.0))

    linhas = (
        db.session.query(RDOApontamentoCronograma)
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio >= a_partir_de,
        )
        .order_by(RDO.data_relatorio.asc(), RDOApontamentoCronograma.id.asc())
        .all()
    )

    alteradas = 0
    for ap in linhas:
        # Mesma regra de classificação do backfill (migration 210).
        tipo = ap.tipo_apontamento or (
            'quantitativo' if (tarefa.quantidade_total or 0) > 0
            else 'percentual')
        antes = (ap.quantidade_acumulada, ap.percentual_realizado,
                 ap.percentual_incremento_dia, ap.percentual_acumulado)
        if tipo == 'quantitativo':
            acum += float(ap.quantidade_executada_dia or 0)
            total = float(ap.quantidade_total_snapshot or 0) or float(
                tarefa.quantidade_total or 0)
            pct = (min(100.0, round(acum / total * 100, 2))
                   if total > 0 else 0.0)
            ap.quantidade_acumulada = acum
            ap.percentual_realizado = pct
            ap.percentual_acumulado = pct
            ap.percentual_incremento_dia = round(pct - pct_ant, 2)
            pct_ant = pct
        else:
            pct = float(ap.percentual_acumulado
                        if ap.percentual_acumulado is not None
                        else (ap.percentual_realizado or 0.0))
            ap.percentual_realizado = max(0.0, min(100.0, pct))
            ap.percentual_acumulado = pct
            ap.percentual_incremento_dia = round(pct - pct_ant, 2)
            pct_ant = pct
        if (ap.quantidade_acumulada, ap.percentual_realizado,
                ap.percentual_incremento_dia, ap.percentual_acumulado) != antes:
            alteradas += 1

    if alteradas:
        logger.info('[recomputo-cadeia] tarefa=%s a_partir_de=%s admin=%s: '
                    '%d de %d apontamento(s) recalculado(s)',
                    tarefa_id, a_partir_de, admin_id, alteradas, len(linhas))
    return alteradas


def registrar_apontamento(rdo, tarefa, *, quantidade_dia=None,
                          percentual_acumulado=None,
                          admin_id,
                          permitir_retrocesso=False,
                          justificativa=None,
                          permitir_sobreexecucao=False) -> RDOApontamentoCronograma:
    """Registra (UPSERT por rdo+tarefa) um apontamento nos dois formatos
    (legado + semântico M02). `quantidade_dia` XOR `percentual_acumulado`.
    Sem commit (caller comita). Levanta subclasses de ApontamentoInvalido
    nas violações — ver docstring do módulo.
    """
    if (quantidade_dia is None) == (percentual_acumulado is None):
        raise ValueError(
            'registrar_apontamento: informe exatamente um entre '
            'quantidade_dia e percentual_acumulado'
        )

    from sqlalchemy import func as sqlfunc

    # Acumulado ANTES deste RDO (cópia literal da query original — soma dos
    # dias em RDOs com data anterior).
    acum_ant = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa.id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio < rdo.data_relatorio,
        )
        .scalar()
    ) or 0.0

    # Último percentual acumulado ANTES deste RDO (para incremento e
    # validação de retrocesso, nos dois modos).
    pct_ant_row = (
        db.session.query(RDOApontamentoCronograma.percentual_realizado)
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa.id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio < rdo.data_relatorio,
        )
        .order_by(RDO.data_relatorio.desc(), RDOApontamentoCronograma.id.desc())
        .first()
    )
    pct_ant = float(pct_ant_row[0]) if pct_ant_row and pct_ant_row[0] is not None else 0.0

    # Planejado na data do RDO (None = tarefa sem plano calculável).
    progresso = calcular_progresso_rdo(tarefa.id, rdo.data_relatorio, admin_id)
    perc_planejado = progresso['percentual_planejado']

    if quantidade_dia is not None:
        tipo = 'quantitativo'
        qty = float(quantidade_dia)
        if qty < 0 and not (permitir_retrocesso and justificativa):
            raise RetrocessoNaoPermitido(
                'Quantidade negativa (correção) exige permitir_retrocesso '
                'com justificativa.')
        nova_acum = acum_ant + qty
        # % pelo snapshot DESTA linha (blindagem do histórico): no momento
        # da escrita snapshot == total vigente da tarefa.
        total_snapshot = float(tarefa.quantidade_total or 0)
        perc_real = 0.0
        if total_snapshot > 0:
            if nova_acum > total_snapshot:
                # Overshoot quantitativo: clamp em 100 com aviso (regra
                # legada, travada por caracterização). A acumulada real
                # fica registrada nos campos de quantidade.
                logger.warning(
                    '[apontamento] sobre-execução quantitativa rdo=%s '
                    'tarefa=%s acumulada=%.2f > total=%.2f — percentual '
                    'clampado em 100', rdo.id, tarefa.id, nova_acum,
                    total_snapshot)
            perc_real = min(100.0, round(nova_acum / total_snapshot * 100, 2))
        pct_acumulado = perc_real
        campos = {
            'quantidade_executada_dia': qty,
            'quantidade_acumulada': nova_acum,
            'quantidade_total_snapshot': total_snapshot or None,
            'unidade_snapshot': (tarefa.unidade_medida or None),
        }
    else:
        tipo = 'percentual'
        pct = float(percentual_acumulado or 0)
        if _is_marco(tarefa) and pct not in (0.0, 100.0):
            raise MarcoApenasZeroOuCem(
                f'Marco aceita apenas 0%% ou 100%% — recebido {pct:g}%%.')
        if pct > 100.0 and not permitir_sobreexecucao:
            raise SobreexecucaoNaoConfirmada(
                f'Percentual acumulado {pct:g}%% excede 100%% — exige '
                f'confirmação explícita.')
        if pct < pct_ant and not (permitir_retrocesso and justificativa):
            raise RetrocessoNaoPermitido(
                f'Acumulado {pct:g}%% menor que o anterior {pct_ant:g}%% — '
                f'exige permitir_retrocesso com justificativa.')
        pct_acumulado = pct
        perc_real = max(0.0, min(100.0, pct))
        campos = {
            # Fim do abuso: quantidade NUNCA guarda percentual. NOT NULL
            # nas colunas ⇒ 0.0 (neutro), verdade nos campos semânticos.
            'quantidade_executada_dia': 0.0,
            'quantidade_acumulada': 0.0,
            'quantidade_total_snapshot': None,
            'unidade_snapshot': None,
        }

    incremento = round(pct_acumulado - pct_ant, 2)

    # UPSERT por (rdo_id, tarefa_cronograma_id) — cópia literal da busca de
    # apontar_producao (sem filtro extra de admin_id, como no original).
    ap = RDOApontamentoCronograma.query.filter_by(
        rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id
    ).first()
    criado = ap is None
    antes = None if criado else {
        'quantidade_executada_dia': ap.quantidade_executada_dia,
        'quantidade_acumulada': ap.quantidade_acumulada,
        'percentual_realizado': ap.percentual_realizado,
        'percentual_planejado': ap.percentual_planejado,
    }
    if criado:
        ap = RDOApontamentoCronograma(
            rdo_id=rdo.id,
            tarefa_cronograma_id=tarefa.id,
            admin_id=admin_id,
        )
        db.session.add(ap)

    ap.percentual_realizado = perc_real
    ap.percentual_planejado = perc_planejado
    ap.tipo_apontamento = tipo
    ap.percentual_acumulado = pct_acumulado
    ap.percentual_incremento_dia = incremento
    for campo, valor in campos.items():
        setattr(ap, campo, valor)

    # Log estruturado = trilha de auditoria dos apontamentos (não há tabela
    # de eventos de RDO): modo, antes/depois, retrocesso/justificativa.
    logger.info(
        '[apontamento] rdo=%s tarefa=%s tipo=%s %s '
        'antes=%s depois={acumulado_pct: %s, incremento: %s, perc_real: %s, '
        'perc_plan: %s} acum_ant=%s retrocesso=%s justificativa=%r admin=%s',
        rdo.id, tarefa.id, tipo, 'criado' if criado else 'atualizado',
        antes, pct_acumulado, incremento, perc_real, perc_planejado,
        acum_ant, bool(permitir_retrocesso), justificativa, admin_id,
    )
    return ap
