"""
Serviço único de métricas/KPIs de funcionários — SIGE v9.0 (Task #98).

Suporta v1 (salário fixo) e v2 (diarista com VA/VT) em paralelo.

Regra de versão:
  • Tenant primeiro via `is_v2_active()`.
  • Override por funcionário via `Funcionario.tipo_remuneracao`.
    - Se `tipo_remuneracao == 'diaria'`: aplica modo "diaria" mesmo em tenant v1.
    - Se `tipo_remuneracao == 'salario'`: aplica modo "salario" mesmo em tenant v2.
    - Caso contrário (valor inesperado): usa o tenant para decidir.

Custo total = MO + VA + VT + Alimentação real (híbrido v1/v2) +
              Reembolsos aprovados/pagos + Almoxarifado em posse (EPI/consumíveis).

Função pública principal: `calcular_metricas_funcionario(funcionario, data_inicio, data_fim)`.

Os dicionários retornados preservam as chaves usadas pelos templates atuais
(`horas_trabalhadas`, `horas_extras`, `faltas`, `faltas_justificadas`, `atrasos`,
`valor_horas_extras`, `valor_faltas`, `custo_total`, `custo_mao_obra`,
`custo_alimentacao`, `custo_transporte`, `outros_custos`, `valor_hora_atual`,
`dias_trabalhados`, `dias_uteis`, `horas_esperadas`, `dias_faltas_justificadas`,
`custo_faltas_justificadas`, `horas_perdidas_total`, `eficiencia`, `produtividade`,
`absenteismo`, `media_diaria`) e adicionam novas chaves:
`modo_remuneracao`, `dias_pagos`, `custo_va`, `custo_vt`, `custo_alimentacao_real`,
`custo_reembolsos`, `custo_almoxarifado_posse`, `breakdown`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func as sa_func

from app import db
from models import (
    AlimentacaoLancamento,
    AlimentacaoLancamentoItem,
    AlmoxarifadoEstoque,
    AlmoxarifadoItem,
    AlmoxarifadoMovimento,
    Funcionario,
    RegistroAlimentacao,
    RegistroPonto,
    ReembolsoFuncionario,
    Usuario,
)


# ---------------------------------------------------------------------------
# Helpers de modo / valor-hora
# ---------------------------------------------------------------------------

_MODOS_VALIDOS = ("salario", "diaria")


def _tenant_is_v2(funcionario: Funcionario) -> bool:
    """Resolve a flag v2 a partir do admin do funcionário (independente do request)."""
    admin = Usuario.query.get(funcionario.admin_id) if funcionario.admin_id else None
    if not admin:
        return False
    return getattr(admin, "versao_sistema", "v1") == "v2"


def get_modo_remuneracao(funcionario: Funcionario) -> str:
    """Decide o modo de remuneração ('salario' ou 'diaria').

    Prioridade: override explícito no funcionário > tenant.
    """
    tipo = (funcionario.tipo_remuneracao or "").strip().lower()
    if tipo in _MODOS_VALIDOS:
        return tipo
    return "diaria" if _tenant_is_v2(funcionario) else "salario"


def calcular_valor_hora(funcionario: Funcionario, data_referencia: Optional[date] = None) -> float:
    """Valor/hora apenas para salaristas (mantém fórmula existente do utils.py).

    Para diaristas retorna 0.0 (a fórmula de custo usa `valor_diaria/8`).
    Erros do helper externo são logados e propagam — não silenciar
    (KPI corrompido sem visibilidade é pior que erro 500 detectado).
    """
    if get_modo_remuneracao(funcionario) != "salario":
        return 0.0
    if not funcionario.salario:
        return 0.0
    from utils import calcular_valor_hora_periodo  # import tardio (evita ciclo)

    return float(calcular_valor_hora_periodo(funcionario, data_referencia, data_referencia) or 0.0)


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------

def _resumo_ponto(funcionario_id: int, data_inicio: date, data_fim: date, admin_id: Optional[int] = None) -> dict:
    """Agrega dados de RegistroPonto para o período."""
    q = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario_id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim,
    )
    if admin_id is not None:
        q = q.filter(RegistroPonto.admin_id == admin_id)
    registros = q.all()

    total_horas = 0.0
    total_extras = 0.0
    total_atraso_horas = 0.0
    faltas = 0
    faltas_justificadas = 0
    dias_trabalhados = 0
    dias_pagos = 0  # dias em que o funcionário deve receber (trabalhou ou folga remunerada)

    for r in registros:
        horas = float(r.horas_trabalhadas or 0)
        extras = float(r.horas_extras or 0)
        total_horas += horas
        total_extras += extras
        total_atraso_horas += float(r.total_atraso_horas or 0)

        tipo = (r.tipo_registro or "trabalhado").lower()
        if tipo == "falta":
            faltas += 1
        elif tipo == "falta_justificada":
            faltas_justificadas += 1
        elif horas > 0 or extras > 0:
            dias_trabalhados += 1

    # `dias_pagos` é resolvido depois conforme o modo (salarista paga falta
    # justificada — CLT —; diarista não paga). Mantemos os contadores brutos
    # e a função pública combina conforme o modo.
    return {
        "registros_count": len(registros),
        "horas_trabalhadas": total_horas,
        "horas_extras": total_extras,
        "atrasos_horas": total_atraso_horas,
        "faltas": faltas,
        "faltas_justificadas": faltas_justificadas,
        "dias_trabalhados": dias_trabalhados,
    }


def _custo_alimentacao_real(funcionario_id: int, data_inicio: date, data_fim: date, admin_id: Optional[int] = None) -> float:
    """Soma alimentação real (híbrido v1+v2):

    • V1 — `RegistroAlimentacao`: campo `valor` direto.
    • V2 — `AlimentacaoLancamentoItem` com `funcionario_id` preenchido (rateio explícito).
    • V2 — `AlimentacaoLancamento` com many-to-many: rateia `valor_total / nº funcionários`.
    """
    total = 0.0

    # V1 — RegistroAlimentacao
    q1 = db.session.query(sa_func.coalesce(sa_func.sum(RegistroAlimentacao.valor), 0.0)).filter(
        RegistroAlimentacao.funcionario_id == funcionario_id,
        RegistroAlimentacao.data >= data_inicio,
        RegistroAlimentacao.data <= data_fim,
    )
    if admin_id is not None:
        q1 = q1.filter(RegistroAlimentacao.admin_id == admin_id)
    total += float(q1.scalar() or 0)

    # V2 — itens detalhados por funcionário
    q2 = db.session.query(sa_func.coalesce(sa_func.sum(AlimentacaoLancamentoItem.subtotal), 0.0)).join(
        AlimentacaoLancamento, AlimentacaoLancamento.id == AlimentacaoLancamentoItem.lancamento_id
    ).filter(
        AlimentacaoLancamentoItem.funcionario_id == funcionario_id,
        AlimentacaoLancamento.data >= data_inicio,
        AlimentacaoLancamento.data <= data_fim,
    )
    if admin_id is not None:
        q2 = q2.filter(AlimentacaoLancamentoItem.admin_id == admin_id)
    total += float(q2.scalar() or 0)

    # V2 — many-to-many sem item detalhado: rateio
    lanc_q = AlimentacaoLancamento.query.filter(
        AlimentacaoLancamento.data >= data_inicio,
        AlimentacaoLancamento.data <= data_fim,
        AlimentacaoLancamento.funcionarios.any(Funcionario.id == funcionario_id),
    )
    if admin_id is not None:
        lanc_q = lanc_q.filter(AlimentacaoLancamento.admin_id == admin_id)

    for lanc in lanc_q.all():
        # Se já há itens detalhados nominais para este funcionário neste lançamento,
        # eles já entraram em q2 — não duplicar.
        ja_detalhado = any(
            it.funcionario_id == funcionario_id for it in (lanc.itens or [])
        )
        if ja_detalhado:
            continue
        nfunc = len(lanc.funcionarios or [])
        if nfunc and lanc.valor_total is not None:
            total += float(lanc.valor_total) / nfunc

    return total


def _custo_reembolsos(funcionario_id: int, data_inicio: date, data_fim: date, admin_id: Optional[int] = None) -> float:
    """Soma reembolsos do funcionário no período.

    Considera todos os reembolsos no intervalo `data_despesa`. O modelo atual não
    possui um campo `status`; entendemos que registros existentes representam
    despesas devidas. Caso o modelo evolua, basta filtrar aqui.
    """
    q = db.session.query(sa_func.coalesce(sa_func.sum(ReembolsoFuncionario.valor), 0)).filter(
        ReembolsoFuncionario.funcionario_id == funcionario_id,
        ReembolsoFuncionario.data_despesa >= data_inicio,
        ReembolsoFuncionario.data_despesa <= data_fim,
    )
    if admin_id is not None:
        q = q.filter(ReembolsoFuncionario.admin_id == admin_id)
    return float(q.scalar() or 0)


def _custo_almoxarifado_em_posse(funcionario_id: int, admin_id: Optional[int] = None) -> float:
    """Valor de itens (EPI/consumíveis) atualmente em posse do funcionário.

    Usa a mesma lógica da rota de perfil:
      • Serializados: `AlmoxarifadoEstoque` com status='EM_USO'.
      • Consumíveis: SAIDA - DEVOLUCAO - CONSUMIDO em movimentos, valor médio
        ponderado das saídas.
    Não filtra por período: representa o saldo atual de responsabilidade.
    """
    if not admin_id:
        admin_id = AlmoxarifadoEstoque.query.with_entities(AlmoxarifadoEstoque.admin_id).filter_by(
            funcionario_atual_id=funcionario_id
        ).limit(1).scalar()

    total = 0.0

    # 1) Serializados em uso
    q_serial = AlmoxarifadoEstoque.query.filter_by(
        funcionario_atual_id=funcionario_id, status="EM_USO"
    )
    if admin_id is not None:
        q_serial = q_serial.filter_by(admin_id=admin_id)
    for e in q_serial.all():
        total += float(e.valor_unitario or 0) * float(e.quantidade or 1)

    # 2) Consumíveis: agrega por item
    movs_q = AlmoxarifadoMovimento.query.filter_by(funcionario_id=funcionario_id)
    if admin_id is not None:
        movs_q = movs_q.filter_by(admin_id=admin_id)
    movs = movs_q.all()
    if not movs:
        return total

    item_ids = {m.item_id for m in movs}
    itens = {i.id: i for i in AlmoxarifadoItem.query.filter(AlmoxarifadoItem.id.in_(item_ids)).all()}

    saldo_por_item: dict[int, dict[str, Decimal]] = {}
    tipos_consumiveis = {"CONSUMIVEL", "QUANTIDADE", "individual"}
    for m in movs:
        item = itens.get(m.item_id)
        if not item or item.tipo_controle not in tipos_consumiveis:
            continue
        bucket = saldo_por_item.setdefault(
            m.item_id,
            {"saida": Decimal("0"), "devolvido": Decimal("0"), "consumido": Decimal("0"),
             "valor_saida": Decimal("0"), "qtd_saida": Decimal("0")},
        )
        qtd = m.quantidade or Decimal("0")
        if m.tipo_movimento == "SAIDA":
            bucket["saida"] += qtd
            bucket["qtd_saida"] += qtd
            bucket["valor_saida"] += (m.valor_unitario or Decimal("0")) * qtd
        elif m.tipo_movimento == "DEVOLUCAO":
            bucket["devolvido"] += qtd
        elif m.tipo_movimento == "CONSUMIDO":
            bucket["consumido"] += qtd

    for b in saldo_por_item.values():
        em_posse = b["saida"] - b["devolvido"] - b["consumido"]
        if em_posse > 0 and b["qtd_saida"] > 0:
            valor_unit = b["valor_saida"] / b["qtd_saida"]
            total += float(valor_unit * em_posse)

    return total


# ---------------------------------------------------------------------------
# Cálculos por modo
# ---------------------------------------------------------------------------

def _dias_uteis(data_inicio: date, data_fim: date) -> int:
    if not data_inicio or not data_fim:
        return 0
    dias = 0
    d = data_inicio
    while d <= data_fim:
        if d.weekday() < 5:
            dias += 1
        d += timedelta(days=1)
    return dias


def _custo_mo_salarista(funcionario: Funcionario, ponto: dict, data_inicio: date) -> dict:
    valor_hora = calcular_valor_hora(funcionario, data_inicio)
    valor_horas = ponto["horas_trabalhadas"] * valor_hora
    valor_extras = ponto["horas_extras"] * valor_hora * 1.5
    valor_faltas = ponto["faltas"] * valor_hora * 8
    valor_faltas_just = ponto["faltas_justificadas"] * valor_hora * 8
    custo_mo = valor_horas + valor_extras
    return {
        "valor_hora_atual": valor_hora,
        "valor_horas_extras": valor_extras,
        "valor_faltas": valor_faltas,
        "custo_faltas_justificadas": valor_faltas_just,
        "custo_mao_obra": custo_mo,
    }


def _custo_mo_diarista(funcionario: Funcionario, ponto: dict, dias_pagos: int) -> dict:
    valor_diaria = float(funcionario.valor_diaria or 0)
    custo_mo = valor_diaria * dias_pagos
    # Diarista: hora extra ainda paga via diária/horas configurada — fórmula simples:
    # 1.5 × (valor_diaria / 8) × horas_extras (assume jornada 8h).
    valor_hora_equiv = (valor_diaria / 8.0) if valor_diaria else 0.0
    valor_extras = ponto["horas_extras"] * valor_hora_equiv * 1.5
    custo_mo += valor_extras
    valor_faltas = ponto["faltas"] * valor_diaria  # cada falta desconta 1 diária
    return {
        "valor_hora_atual": valor_hora_equiv,
        "valor_horas_extras": valor_extras,
        "valor_faltas": valor_faltas,
        "custo_faltas_justificadas": 0.0,  # diarista: justificada não paga (sem CLT)
        "custo_mao_obra": custo_mo,
    }


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def calcular_metricas_funcionario(
    funcionario: Funcionario,
    data_inicio: date,
    data_fim: date,
    admin_id: Optional[int] = None,
) -> dict:
    """Retorna dicionário consolidado de métricas/KPIs de um funcionário."""
    if admin_id is None:
        admin_id = funcionario.admin_id

    modo = get_modo_remuneracao(funcionario)
    ponto = _resumo_ponto(funcionario.id, data_inicio, data_fim, admin_id)

    # Resolução de `dias_pagos` por modo:
    #   • Salarista (CLT): paga falta justificada → dias_trab + faltas_just
    #   • Diarista: NÃO paga falta justificada → apenas dias trabalhados
    if modo == "diaria":
        dias_pagos = ponto["dias_trabalhados"]
        mo = _custo_mo_diarista(funcionario, ponto, dias_pagos)
    else:
        dias_pagos = ponto["dias_trabalhados"] + ponto["faltas_justificadas"]
        mo = _custo_mo_salarista(funcionario, ponto, data_inicio)

    custo_va = float(funcionario.valor_va or 0) * dias_pagos
    custo_vt = float(funcionario.valor_vt or 0) * dias_pagos
    custo_alim_real = _custo_alimentacao_real(funcionario.id, data_inicio, data_fim, admin_id)
    custo_reemb = _custo_reembolsos(funcionario.id, data_inicio, data_fim, admin_id)
    custo_almox = _custo_almoxarifado_em_posse(funcionario.id, admin_id)

    custo_total = (
        mo["custo_mao_obra"]
        + custo_va
        + custo_vt
        + custo_alim_real
        + custo_reemb
        + custo_almox
    )

    dias_uteis = _dias_uteis(data_inicio, data_fim)
    horas_esperadas = dias_uteis * 8
    horas_trab = ponto["horas_trabalhadas"]
    eficiencia = (horas_trab / horas_esperadas * 100.0) if horas_esperadas else 0.0
    produtividade = (
        (horas_trab / (ponto["dias_trabalhados"] * 8) * 100.0)
        if ponto["dias_trabalhados"] else 0.0
    )
    total_faltas_dias = ponto["faltas"] + ponto["faltas_justificadas"]
    absenteismo = (total_faltas_dias / dias_uteis * 100.0) if dias_uteis else 0.0
    media_diaria = (horas_trab / ponto["dias_trabalhados"]) if ponto["dias_trabalhados"] else 0.0
    horas_perdidas_total = ponto["faltas"] * 8 + ponto["atrasos_horas"]

    breakdown = {
        "mao_obra": mo["custo_mao_obra"],
        "vale_alimentacao": custo_va,
        "vale_transporte": custo_vt,
        "alimentacao_real": custo_alim_real,
        "reembolsos": custo_reemb,
        "almoxarifado_em_posse": custo_almox,
    }

    return {
        # ── compatibilidade com templates atuais ──────────────────────────
        "horas_trabalhadas": horas_trab,
        "horas_extras": ponto["horas_extras"],
        "faltas": ponto["faltas"],
        "faltas_justificadas": ponto["faltas_justificadas"],
        "dias_faltas_justificadas": ponto["faltas_justificadas"],
        "atrasos": ponto["atrasos_horas"],
        "valor_horas_extras": mo["valor_horas_extras"],
        "valor_faltas": mo["valor_faltas"],
        "valor_hora_atual": mo["valor_hora_atual"],
        "custo_mao_obra": mo["custo_mao_obra"],
        "custo_alimentacao": custo_alim_real + custo_va,  # tela "Custo Alimentação"
        "custo_transporte": custo_vt,
        "outros_custos": custo_reemb + custo_almox,
        "custo_faltas_justificadas": mo["custo_faltas_justificadas"],
        "custo_total": custo_total,
        "custo_total_geral": custo_total,
        "horas_perdidas_total": horas_perdidas_total,
        "dias_trabalhados": ponto["dias_trabalhados"],
        "dias_uteis": dias_uteis,
        "horas_esperadas": horas_esperadas,
        "eficiencia": round(eficiencia, 2),
        "produtividade": round(produtividade, 2),
        "absenteismo": round(absenteismo, 2),
        "media_diaria": round(media_diaria, 2),
        # ── novos campos v1+v2 ────────────────────────────────────────────
        "modo_remuneracao": modo,
        "dias_pagos": dias_pagos,
        "custo_va": custo_va,
        "custo_vt": custo_vt,
        "custo_alimentacao_real": custo_alim_real,
        "custo_reembolsos": custo_reemb,
        "custo_almoxarifado_posse": custo_almox,
        "custo_almoxarifado": custo_almox,  # alias do contrato (Task #98)
        "breakdown": breakdown,
    }


def calcular_metricas_lista(
    funcionarios: list,
    data_inicio: date,
    data_fim: date,
    admin_id: Optional[int] = None,
) -> list:
    """Retorna lista de dicts `{funcionario, funcao_nome, modo_remuneracao, **metricas}`.

    Útil para a tela `/funcionarios` (cards e KPIs gerais agregados).
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)

    resultado = []
    for f in funcionarios:
        funcao_nome = f.funcao_ref.nome if getattr(f, "funcao_ref", None) else "N/A"
        # Não silenciar erros de cálculo: logamos com contexto (id) e seguimos
        # com zeros para o funcionário problemático, preservando a página.
        try:
            m = calcular_metricas_funcionario(f, data_inicio, data_fim, admin_id)
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            _log.error(
                "calcular_metricas_funcionario falhou para funcionario_id=%s admin_id=%s: %s",
                getattr(f, "id", None), admin_id, e, exc_info=True,
            )
            m = {
                "horas_trabalhadas": 0, "horas_extras": 0, "faltas": 0,
                "faltas_justificadas": 0, "dias_pagos": 0,
                "custo_mao_obra": 0, "custo_va": 0, "custo_vt": 0,
                "custo_alimentacao": 0, "custo_alimentacao_real": 0,
                "custo_transporte": 0, "custo_reembolsos": 0,
                "custo_almoxarifado": 0, "custo_almoxarifado_posse": 0,
                "outros_custos": 0, "custo_total": 0,
                "valor_hora_atual": 0,
                "modo_remuneracao": get_modo_remuneracao(f),
                "_erro": str(e),
            }
        item = {
            "funcionario": f,
            "funcao_nome": funcao_nome,
            # contrato exigido pela Task #98 — todas as métricas no item da lista
            "modo_remuneracao": m.get("modo_remuneracao"),
            "horas_trabalhadas": m.get("horas_trabalhadas", 0),
            "horas_extras": m.get("horas_extras", 0),
            "faltas": m.get("faltas", 0),
            "faltas_justificadas": m.get("faltas_justificadas", 0),
            "dias_pagos": m.get("dias_pagos", 0),
            "valor_hora_atual": m.get("valor_hora_atual", 0),
            "custo_mao_obra": m.get("custo_mao_obra", 0),
            "custo_va": m.get("custo_va", 0),
            "custo_vt": m.get("custo_vt", 0),
            "custo_alimentacao_real": m.get("custo_alimentacao_real", 0),
            "custo_reembolsos": m.get("custo_reembolsos", 0),
            "custo_almoxarifado": m.get("custo_almoxarifado", m.get("custo_almoxarifado_posse", 0)),
            "custo_total": m.get("custo_total", 0),
            # aliases de retro-compat usados pelo template antigo
            "total_horas": m.get("horas_trabalhadas", 0),
            "total_extras": m.get("horas_extras", 0),
            "total_faltas": m.get("faltas", 0),
            "total_faltas_justificadas": m.get("faltas_justificadas", 0),
        }
        resultado.append(item)
    return resultado


def agregar_kpis_geral(metricas_lista: list, num_funcionarios_ativos: int) -> dict:
    """Agrega métricas individuais em KPIs do cabeçalho da tela `/funcionarios`."""
    total_horas = sum(k.get("total_horas", 0) for k in metricas_lista)
    total_extras = sum(k.get("total_extras", 0) for k in metricas_lista)
    total_faltas = sum(k.get("total_faltas", 0) for k in metricas_lista)
    total_faltas_just = sum(k.get("total_faltas_justificadas", 0) for k in metricas_lista)
    total_custo = sum(k.get("custo_total", 0) for k in metricas_lista)

    total_dias_possiveis = num_funcionarios_ativos * 22  # média mensal
    taxa_absent = (
        (total_faltas + total_faltas_just) / total_dias_possiveis * 100.0
        if total_dias_possiveis else 0.0
    )

    return {
        "total_funcionarios": num_funcionarios_ativos,
        "funcionarios_ativos": num_funcionarios_ativos,
        "total_horas_geral": total_horas,
        "total_extras_geral": total_extras,
        "total_faltas_geral": total_faltas,
        "total_faltas_justificadas_geral": total_faltas_just,
        "total_custo_geral": total_custo,
        "total_custo_faltas_geral": 0.0,  # depreciado: já compõe custo_total
        "taxa_absenteismo_geral": round(taxa_absent, 2),
    }
