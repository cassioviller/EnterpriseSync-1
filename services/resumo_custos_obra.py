"""Task #70 — Resumo de Custos da Obra.

Camada de cálculo que consolida, por obra, os 12 indicadores do painel
estratégico e os datasets que alimentam os gráficos existentes
(`painelEstrategicoChart` e `chartComposicaoCusto`).

Exporta:
    - recalcular_servico(obra_servico_custo_id)
    - recalcular_obra(obra_id, admin_id=None)
    - calcular_resumo_obra(obra_id, admin_id=None) -> dict
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func as sqlfunc

logger = logging.getLogger(__name__)


# Mapeamento de tipo_categoria (GestaoCustoPai) -> slot de realizado
_CATEGORIA_MATERIAL = {'MATERIAL', 'COMPRA', 'EQUIPAMENTO', 'VEICULO'}
_CATEGORIA_MAO_OBRA = {'MAO_OBRA_DIRETA', 'SALARIO', 'SUBEMPREITADA',
                       'ALIMENTACAO', 'ALIMENTACAO_DIARIA',
                       'TRANSPORTE', 'VALE_TRANSPORTE'}
_CATEGORIA_FATURAMENTO_DIRETO = {'FATURAMENTO_DIRETO'}


def _f(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────────────────────────────────
# Recálculo por serviço
# ─────────────────────────────────────────────────────────────────────────
def recalcular_servico(obra_servico_custo_id: int) -> bool:
    """Recalcula os campos derivados de um ObraServicoCusto:
    - mao_obra_a_realizar = soma das linhas de equipe planejada
    - material_a_realizar (só se houver cotação SELECIONADA que sobrescreve)
    """
    try:
        from models import (
            db,
            ObraServicoCusto,
            ObraServicoCotacaoInterna,
        )

        svc = db.session.get(ObraServicoCusto, obra_servico_custo_id)
        if not svc:
            logger.warning(
                "recalcular_servico(%s): ObraServicoCusto não encontrado",
                obra_servico_custo_id,
            )
            return False

        mao_obra_total = 0.0
        for linha in (svc.equipe_planejada or []):
            mao_obra_total += _f(linha.custo_dia) * _f(linha.quantidade_dias)
        svc.mao_obra_a_realizar = Decimal(str(round(mao_obra_total, 2)))

        cot_sel = (
            ObraServicoCotacaoInterna.query
            .filter_by(
                obra_servico_custo_id=svc.id,
                admin_id=svc.admin_id,
                selecionada=True,
            )
            .first()
        )
        if cot_sel:
            svc.cotacao_selecionada_id = cot_sel.id
            svc.material_a_realizar = Decimal(str(round(cot_sel.valor_total, 2)))
        # Sem cotação selecionada: mantém valor manual digitado
        # Observação: não emitimos flush explícito aqui pois a função pode ser
        # chamada a partir de listeners da sessão. O commit/flush natural do
        # caller persiste as mutações.
        return True
    except Exception:
        logger.exception("recalcular_servico(%s) falhou", obra_servico_custo_id)
        return False


# ─────────────────────────────────────────────────────────────────────────
# Recálculo por obra (realizado a partir de GestaoCustoFilho)
# ─────────────────────────────────────────────────────────────────────────
def _bucket_categoria(cat: str) -> str | None:
    """Mapeia tipo_categoria → bucket: 'material' | 'mao_obra' | 'outros' | None."""
    c = (cat or '').upper()
    if c in _CATEGORIA_FATURAMENTO_DIRETO:
        return None
    if c in _CATEGORIA_MATERIAL:
        return 'material'
    if c in _CATEGORIA_MAO_OBRA:
        return 'mao_obra'
    return 'outros'


def recalcular_obra(obra_id: int, admin_id=None) -> bool:
    """Atualiza o 'Realizado' de cada serviço com base em GestaoCustoFilho,
    agregado por categoria.

    Estratégia (Task #74):
      - Quando um filho está vinculado diretamente a um serviço via
        ``obra_servico_custo_id``, o valor é somado ao realizado daquele
        serviço (na categoria correspondente — material/mão de obra/outros).
      - O restante (filhos não vinculados) é rateado entre os demais
        serviços proporcionalmente ao ``valor_orcado``; quando não há
        orçado, aplica rateio uniforme.
      - Serviços com ``override_realizado_manual=True`` nunca são
        sobrescritos (nem por vínculo direto nem por rateio).
    """
    try:
        from models import (
            db,
            ObraServicoCusto,
            GestaoCustoFilho,
            GestaoCustoPai,
        )

        q_svcs = ObraServicoCusto.query.filter_by(obra_id=obra_id)
        if admin_id is not None:
            q_svcs = q_svcs.filter_by(admin_id=admin_id)
        svcs = q_svcs.all()
        if not svcs:
            return True

        svc_ids = {s.id for s in svcs}

        # Soma todos os filhos da obra agrupados por (servico, categoria),
        # incluindo os não vinculados (NULL).
        q = (
            db.session.query(
                GestaoCustoFilho.obra_servico_custo_id,
                GestaoCustoPai.tipo_categoria,
                sqlfunc.coalesce(sqlfunc.sum(GestaoCustoFilho.valor), 0),
            )
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra_id)
            .group_by(
                GestaoCustoFilho.obra_servico_custo_id,
                GestaoCustoPai.tipo_categoria,
            )
        )
        if admin_id is not None:
            q = q.filter(GestaoCustoPai.admin_id == admin_id)

        # direto[svc_id] = {'material':.., 'mao_obra':.., 'outros':..}
        direto: dict[int, dict[str, float]] = {
            sid: {'material': 0.0, 'mao_obra': 0.0, 'outros': 0.0}
            for sid in svc_ids
        }
        rest_material = 0.0
        rest_mao_obra = 0.0
        rest_outros = 0.0

        for svc_id, cat, total in q.all():
            bucket = _bucket_categoria(cat)
            if bucket is None:
                continue
            v = _f(total)
            # Vínculo válido apenas se o serviço pertence à obra (e tenant)
            if svc_id and svc_id in svc_ids:
                direto[svc_id][bucket] += v
            else:
                if bucket == 'material':
                    rest_material += v
                elif bucket == 'mao_obra':
                    rest_mao_obra += v
                else:
                    rest_outros += v

        alvos = [s for s in svcs if not s.override_realizado_manual]

        # Filhos diretamente vinculados a serviços com override são ignorados
        # (o serviço mantém o valor manual). Não jogamos esse valor no rateio
        # para não distorcer os demais.

        if not alvos:
            db.session.flush()
            return True

        total_orcado = sum(_f(s.valor_orcado) for s in alvos)
        use_proporcional = total_orcado > 0
        n_alvos = len(alvos)

        for s in alvos:
            if use_proporcional:
                w = _f(s.valor_orcado) / total_orcado
            else:
                w = 1.0 / n_alvos
            d = direto.get(s.id, {'material': 0.0, 'mao_obra': 0.0, 'outros': 0.0})
            s.realizado_material = Decimal(str(round(d['material'] + rest_material * w, 2)))
            s.realizado_mao_obra = Decimal(str(round(d['mao_obra'] + rest_mao_obra * w, 2)))
            s.realizado_outros = Decimal(str(round(d['outros'] + rest_outros * w, 2)))
        # Sem flush explícito: persiste no próximo flush do caller.
        return True
    except Exception as e:
        logger.error(f"recalcular_obra({obra_id}): {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────
# Resumo consolidado (12 indicadores + dados dos gráficos)
# ─────────────────────────────────────────────────────────────────────────
def calcular_resumo_obra(obra_id: int, admin_id=None) -> dict:
    """Retorna dicionário com 12 indicadores + payloads dos 2 gráficos.

    Indicadores (em BRL, float):
      total_proposta_orcada, valor_custo_orcado, total_realizado,
      total_a_realizar, custo_real_da_obra, verba_disponivel,
      faturamento_direto, valor_medido, valor_recebido, valor_a_receber,
      lucro_liquido, administracao.

    Payloads:
      grafico_barras:
        {'receita': {'contrato':..,'medido':..,'recebido':..},
         'custo': {'orcado':..,'realizado':..,'a_realizar':..,'real_projetado':..}}
      grafico_composicao:
        {'realizado':  [{'categoria':..,'valor':..,'cor':..}, ...],
         'a_realizar': [{'categoria':..,'valor':..,'cor':..}, ...]}
    """
    from models import (
        db,
        Obra,
        ObraServicoCusto,
        ItemMedicaoComercial,
        GestaoCustoPai,
        GestaoCustoFilho,
        ContaReceber,
    )

    obra = db.session.get(Obra, obra_id)
    if not obra:
        return _resumo_vazio()

    if admin_id is None:
        admin_id = obra.admin_id

    q_svcs = ObraServicoCusto.query.filter_by(obra_id=obra_id)
    if admin_id is not None:
        q_svcs = q_svcs.filter_by(admin_id=admin_id)
    svcs = q_svcs.all()
    valor_custo_orcado = sum(_f(s.valor_orcado) for s in svcs)
    total_realizado_svc = sum(s.realizado_total for s in svcs)
    total_a_realizar = sum(s.a_realizar_total for s in svcs)

    # Realizado da obra = soma de GestaoCustoFilho (exceto FATURAMENTO_DIRETO)
    q_real = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(GestaoCustoFilho.valor), 0))
        .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
        .filter(GestaoCustoFilho.obra_id == obra_id)
        .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
    )
    if admin_id is not None:
        q_real = q_real.filter(GestaoCustoPai.admin_id == admin_id)
    total_realizado_obra = _f(q_real.scalar() or 0)

    # Prioriza o snapshot por serviço (obra_servico_custo) quando houver
    # planejamento de custos cadastrado — assim overrides manuais "para
    # baixo" feitos por serviço refletem no resumo. Só cai para o agregado
    # legado de GestaoCustoFilho quando não há dados novos.
    if svcs:
        total_realizado = total_realizado_svc
    else:
        total_realizado = total_realizado_obra

    # Faturamento Direto (pai com categoria especial)
    q_fat = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(GestaoCustoFilho.valor), 0))
        .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
        .filter(GestaoCustoFilho.obra_id == obra_id)
        .filter(GestaoCustoPai.tipo_categoria == 'FATURAMENTO_DIRETO')
    )
    if admin_id is not None:
        q_fat = q_fat.filter(GestaoCustoPai.admin_id == admin_id)
    faturamento_direto = _f(q_fat.scalar() or 0)

    # Multi-tenant rigoroso: usa admin_id da obra quando o caller não passou
    # um admin_id explícito, para não vazar dados entre tenants.
    tenant_admin_id = admin_id if admin_id is not None else obra.admin_id

    # Receita
    # Total Proposta Orçada: valor_contrato da obra; fallback = Proposta.valor_total
    # mais recente vinculada à obra (preferindo status 'aprovada').
    total_proposta_orcada = _f(obra.valor_contrato)
    if not total_proposta_orcada:
        try:
            from models import Proposta
            prop = (
                Proposta.query
                .filter_by(obra_id=obra.id, admin_id=tenant_admin_id)
                .filter(Proposta.status == 'aprovada')
                .order_by(Proposta.id.desc())
                .first()
                or Proposta.query
                .filter_by(obra_id=obra.id, admin_id=tenant_admin_id)
                .order_by(Proposta.id.desc())
                .first()
            )
            if prop:
                total_proposta_orcada = _f(prop.valor_total)
        except Exception:
            logger.exception(
                "calcular_resumo_obra(%s): falha no fallback Proposta.valor_total",
                obra.id,
            )
    medido_q = db.session.query(
        sqlfunc.coalesce(sqlfunc.sum(ItemMedicaoComercial.valor_executado_acumulado), 0)
    ).filter(ItemMedicaoComercial.obra_id == obra_id)
    if tenant_admin_id is not None and hasattr(ItemMedicaoComercial, 'admin_id'):
        medido_q = medido_q.filter(ItemMedicaoComercial.admin_id == tenant_admin_id)
    valor_medido = _f(medido_q.scalar() or 0)

    recebido_q = db.session.query(
        sqlfunc.coalesce(sqlfunc.sum(ContaReceber.valor_recebido), 0)
    ).filter(ContaReceber.obra_id == obra_id)
    if tenant_admin_id is not None and hasattr(ContaReceber, 'admin_id'):
        recebido_q = recebido_q.filter(ContaReceber.admin_id == tenant_admin_id)
    recebido_contas = _f(recebido_q.scalar() or 0)
    entrada = _f(obra.valor_entrada) if obra.data_entrada else 0.0
    valor_recebido = recebido_contas + entrada
    valor_a_receber = max(valor_medido - valor_recebido, 0.0)

    percentual_adm = _f(obra.percentual_administracao)
    administracao = total_proposta_orcada * (percentual_adm / 100.0)

    custo_real_da_obra = total_realizado + total_a_realizar + administracao + faturamento_direto
    verba_disponivel = total_proposta_orcada - custo_real_da_obra
    lucro_liquido = valor_medido - (total_realizado + administracao + faturamento_direto)

    indicadores = {
        'total_proposta_orcada': round(total_proposta_orcada, 2),
        'valor_custo_orcado': round(valor_custo_orcado, 2),
        'total_realizado': round(total_realizado, 2),
        'total_a_realizar': round(total_a_realizar, 2),
        'custo_real_da_obra': round(custo_real_da_obra, 2),
        'verba_disponivel': round(verba_disponivel, 2),
        'faturamento_direto': round(faturamento_direto, 2),
        'valor_medido': round(valor_medido, 2),
        'valor_recebido': round(valor_recebido, 2),
        'valor_a_receber': round(valor_a_receber, 2),
        'lucro_liquido': round(lucro_liquido, 2),
        'administracao': round(administracao, 2),
        'percentual_administracao': percentual_adm,
    }

    tem_dados_novos = bool(svcs) or total_a_realizar > 0 or valor_custo_orcado > 0

    grafico_barras = {
        'receita': {
            'contrato': round(total_proposta_orcada, 2),
            'medido': round(valor_medido, 2),
            'recebido': round(valor_recebido, 2),
        },
        'custo': {
            'orcado': round(valor_custo_orcado, 2),
            'realizado': round(total_realizado, 2),
            'a_realizar': round(total_a_realizar, 2),
            'real_projetado': round(total_realizado + total_a_realizar, 2),
        },
        'tem_dados_novos': tem_dados_novos,
    }

    # Composição (2 anéis) agregada por categoria
    realizado_mat = sum(_f(s.realizado_material) for s in svcs)
    realizado_mo = sum(_f(s.realizado_mao_obra) for s in svcs)
    realizado_out = sum(_f(s.realizado_outros) for s in svcs)
    a_realizar_mat = sum(_f(s.material_a_realizar) for s in svcs)
    a_realizar_mo = sum(_f(s.mao_obra_a_realizar) for s in svcs)
    a_realizar_out = sum(_f(s.outros_a_realizar) for s in svcs)

    grafico_composicao = {
        'realizado': [
            {'categoria': 'Material', 'valor': round(realizado_mat, 2), 'cor': '#ef4444'},
            {'categoria': 'Mão de Obra', 'valor': round(realizado_mo, 2), 'cor': '#f59e0b'},
            {'categoria': 'Outros', 'valor': round(realizado_out, 2), 'cor': '#8b5cf6'},
        ],
        'a_realizar': [
            {'categoria': 'Material', 'valor': round(a_realizar_mat, 2), 'cor': '#fca5a5'},
            {'categoria': 'Mão de Obra', 'valor': round(a_realizar_mo, 2), 'cor': '#fcd34d'},
            {'categoria': 'Outros', 'valor': round(a_realizar_out, 2), 'cor': '#c4b5fd'},
        ],
        'tem_dados_novos': tem_dados_novos,
    }

    return {
        'indicadores': indicadores,
        'servicos': svcs,
        'grafico_barras': grafico_barras,
        'grafico_composicao': grafico_composicao,
        'tem_dados_novos': tem_dados_novos,
    }


def _resumo_vazio():
    empty = {k: 0.0 for k in [
        'total_proposta_orcada', 'valor_custo_orcado', 'total_realizado',
        'total_a_realizar', 'custo_real_da_obra', 'verba_disponivel',
        'faturamento_direto', 'valor_medido', 'valor_recebido',
        'valor_a_receber', 'lucro_liquido', 'administracao',
        'percentual_administracao',
    ]}
    return {
        'indicadores': empty,
        'servicos': [],
        'grafico_barras': {
            'receita': {'contrato': 0, 'medido': 0, 'recebido': 0},
            'custo': {'orcado': 0, 'realizado': 0, 'a_realizar': 0, 'real_projetado': 0},
            'tem_dados_novos': False,
        },
        'grafico_composicao': {
            'realizado': [],
            'a_realizar': [],
            'tem_dados_novos': False,
        },
        'tem_dados_novos': False,
    }
