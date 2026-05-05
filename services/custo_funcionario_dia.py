"""
services/custo_funcionario_dia.py

Custo diário de mão-de-obra por funcionário, com persistência em RDOCustoDiario.

Regras:
  Diarista  — custo = valor_diaria * proporção_horas + VA + VT
  Mensalista — custo = salário / dias_úteis_mês * horas_no_rdo + extras (×1.5) + VA + VT
  Rateio proporcional quando o funcionário aparece em >1 RDO no mesmo dia:
    proporção = horas_neste_rdo / total_horas_no_dia

Idempotência: re-salvar o mesmo RDO atualiza a linha existente sem duplicar.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Utilitários
# ────────────────────────────────────────────────────────────

def dias_uteis_mes(ano: int, mes: int) -> int:
    """Conta dias úteis (seg–sex) no mês, sem considerar feriados."""
    _, ultimo = monthrange(ano, mes)
    return sum(
        1 for d in range(1, ultimo + 1)
        if date(ano, mes, d).weekday() < 5
    )


# ────────────────────────────────────────────────────────────
# Cálculo dos componentes de custo
# ────────────────────────────────────────────────────────────

def calcular_custo_funcionario_no_rdo(
    funcionario,
    horas_no_rdo: float,
    horas_totais_dia: float,
    horas_extras_no_rdo: float,
    data_ref: date,
) -> dict:
    """
    Calcula os componentes de custo proporcional de um funcionário para um único RDO.

    Args:
        funcionario       : instância de Funcionario
        horas_no_rdo      : horas normais que este funcionário trabalhou NESTE RDO
        horas_totais_dia  : total de horas normais do funcionário em TODOS os RDOs do dia
        horas_extras_no_rdo: horas extras neste RDO
        data_ref          : date do RDO (usado para calcular días úteis do mês)

    Returns dict com campos:
        tipo_remuneracao_snapshot, componente_folha, componente_va,
        componente_vt, componente_extra, custo_total_dia,
        horas_normais, horas_extras, custo_hora_normal, dias_uteis_mes_referencia
    """
    tipo = getattr(funcionario, 'tipo_remuneracao', 'salario') or 'salario'
    valor_va = float(getattr(funcionario, 'valor_va', 0) or 0)
    valor_vt = float(getattr(funcionario, 'valor_vt', 0) or 0)

    total_dia = max(float(horas_totais_dia or 0), float(horas_no_rdo or 0), 0.001)
    proporcao = min(float(horas_no_rdo or 0) / total_dia, 1.0)

    resultado: dict = {
        'tipo_remuneracao_snapshot': tipo,
        'horas_normais': float(horas_no_rdo),
        'horas_extras': float(horas_extras_no_rdo),
        'componente_folha': Decimal('0'),
        'componente_va': Decimal(str(round(valor_va * proporcao, 2))),
        'componente_vt': Decimal(str(round(valor_vt * proporcao, 2))),
        'componente_extra': Decimal('0'),
        'custo_hora_normal': None,
        'dias_uteis_mes_referencia': None,
    }

    if tipo == 'diaria':
        valor_diaria = float(getattr(funcionario, 'valor_diaria', 0) or 0)
        folha = Decimal(str(round(valor_diaria * proporcao, 2)))
        resultado['componente_folha'] = folha
        if valor_diaria > 0 and horas_no_rdo > 0:
            resultado['custo_hora_normal'] = Decimal(
                str(round(valor_diaria / horas_no_rdo, 4))
            )
        if horas_extras_no_rdo > 0 and resultado['custo_hora_normal']:
            extra_valor = Decimal(str(
                round(horas_extras_no_rdo * float(resultado['custo_hora_normal']) * 1.5, 2)
            ))
            resultado['componente_extra'] = extra_valor
    else:
        du = dias_uteis_mes(data_ref.year, data_ref.month)
        resultado['dias_uteis_mes_referencia'] = du

        try:
            from utils import calcular_valor_hora_periodo
            vh = calcular_valor_hora_periodo(funcionario, data_ref, data_ref) or 0.0
        except Exception:
            salario = float(getattr(funcionario, 'salario', 0) or 0)
            horas_dia = 8.0
            vh = salario / (du * horas_dia) if du > 0 else 0.0

        custo_normal = float(horas_no_rdo) * vh
        resultado['componente_folha'] = Decimal(str(round(custo_normal, 2)))
        resultado['custo_hora_normal'] = Decimal(str(round(vh, 4))) if vh > 0 else None

        if horas_extras_no_rdo > 0 and vh > 0:
            extra_valor = Decimal(str(round(horas_extras_no_rdo * vh * 1.5, 2)))
            resultado['componente_extra'] = extra_valor

    resultado['custo_total_dia'] = (
        resultado['componente_folha']
        + resultado['componente_va']
        + resultado['componente_vt']
        + resultado['componente_extra']
    )
    return resultado


# ────────────────────────────────────────────────────────────
# Hook principal: chamado após RDO salvo/editado
# ────────────────────────────────────────────────────────────

def gravar_custo_funcionario_rdo(rdo, admin_id: int) -> int:
    """
    Calcula e persiste RDOCustoDiario para cada funcionário do RDO.
    Idempotente: re-salvar atualiza linha existente sem duplicar.
    Recalcula a proporção considerando todos os RDOs do funcionário no dia.

    Retorna número de linhas criadas/atualizadas.
    """
    try:
        from app import db
        from models import RDOMaoObra, Funcionario, RDOCustoDiario, RDO
        from sqlalchemy import func as sql_func

        linhas_rdo = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
        if not linhas_rdo:
            return 0

        horas_rdo: dict[int, float] = {}
        extras_rdo: dict[int, float] = {}
        for linha in linhas_rdo:
            fid = linha.funcionario_id
            horas_rdo[fid] = horas_rdo.get(fid, 0.0) + float(linha.horas_trabalhadas or 0)
            extras_rdo[fid] = extras_rdo.get(fid, 0.0) + float(linha.horas_extras or 0)

        data_ref = rdo.data_relatorio
        atualizados = 0

        for func_id, horas_no_rdo in horas_rdo.items():
            funcionario = Funcionario.query.filter_by(
                id=func_id, admin_id=admin_id
            ).first()
            if not funcionario:
                continue

            total_horas_dia = db.session.query(
                sql_func.coalesce(sql_func.sum(RDOMaoObra.horas_trabalhadas), 0)
            ).join(RDO, RDO.id == RDOMaoObra.rdo_id).filter(
                RDOMaoObra.funcionario_id == func_id,
                RDO.data_relatorio == data_ref,
                RDO.admin_id == admin_id,
            ).scalar() or 0.0

            horas_extras_no_rdo = extras_rdo.get(func_id, 0.0)

            comp = calcular_custo_funcionario_no_rdo(
                funcionario,
                horas_no_rdo,
                float(total_horas_dia),
                horas_extras_no_rdo,
                data_ref,
            )

            registro = RDOCustoDiario.query.filter_by(
                rdo_id=rdo.id,
                funcionario_id=func_id,
            ).first()

            if not registro:
                registro = RDOCustoDiario(
                    rdo_id=rdo.id,
                    funcionario_id=func_id,
                    admin_id=admin_id,
                    tipo_lancamento='rdo',
                )
                db.session.add(registro)

            registro.data                      = data_ref
            registro.admin_id                  = admin_id
            registro.tipo_remuneracao_snapshot = comp['tipo_remuneracao_snapshot']
            registro.componente_folha          = comp['componente_folha']
            registro.componente_va             = comp['componente_va']
            registro.componente_vt             = comp['componente_vt']
            registro.componente_extra          = comp['componente_extra']
            registro.custo_total_dia           = comp['custo_total_dia']
            registro.horas_normais             = comp['horas_normais']
            registro.horas_extras              = comp['horas_extras']
            registro.custo_hora_normal         = comp['custo_hora_normal']
            registro.dias_uteis_mes_referencia = comp.get('dias_uteis_mes_referencia')

            atualizados += 1

        db.session.flush()
        logger.info(
            "[custo-dia] RDO %s (%s): %d registro(s) gravados",
            rdo.numero_rdo, data_ref, atualizados,
        )
        return atualizados

    except Exception:
        logger.exception("gravar_custo_funcionario_rdo falhou (rdo_id=%s)", getattr(rdo, 'id', '?'))
        return 0


def remover_custo_diario_rdo(rdo_id: int) -> int:
    """Remove todas as linhas RDOCustoDiario associadas a um RDO.
    Deve ser chamada ANTES de deletar os RDOMaoObra (hook de edição).
    Retorna número de linhas removidas.
    """
    try:
        from app import db
        from models import RDOCustoDiario
        n = RDOCustoDiario.query.filter_by(rdo_id=rdo_id, tipo_lancamento='rdo').delete()
        db.session.flush()
        logger.info("[custo-dia] removidas %d linhas do rdo_id=%s", n, rdo_id)
        return n
    except Exception:
        logger.exception("remover_custo_diario_rdo falhou (rdo_id=%s)", rdo_id)
        return 0


# ────────────────────────────────────────────────────────────
# Consulta do histórico
# ────────────────────────────────────────────────────────────

def obter_custo_funcionario_periodo(
    funcionario_id: int,
    data_inicio: date,
    data_fim: date,
):
    """Retorna lista de RDOCustoDiario para o funcionário no período."""
    try:
        from models import RDOCustoDiario
        return (
            RDOCustoDiario.query
            .filter(
                RDOCustoDiario.funcionario_id == funcionario_id,
                RDOCustoDiario.data >= data_inicio,
                RDOCustoDiario.data <= data_fim,
            )
            .order_by(RDOCustoDiario.data)
            .all()
        )
    except Exception:
        logger.exception("obter_custo_funcionario_periodo falhou")
        return []


# ────────────────────────────────────────────────────────────
# Job de cobertura ociosa (mensalistas)
# ────────────────────────────────────────────────────────────

def gerar_dias_ociosos_mensalista(
    funcionario_id: int,
    ano: int,
    mes: int,
    admin_id: int,
) -> int:
    """
    Cria entradas ocioso_mensal para dias úteis sem RDO de um mensalista.
    Idempotente: não recria linha se já houver qualquer lançamento naquele dia.
    Se um RDO atrasado chega para um dia ocioso, o gravar_custo_funcionario_rdo
    criará/atualizará a linha com tipo='rdo' — a linha ociosa permanece intacta;
    a lógica de consulta deve preferir o registro tipo='rdo' quando ambos existirem.
    Retorna número de linhas criadas.
    """
    try:
        from app import db
        from models import RDOCustoDiario, Funcionario
        from calendar import monthrange

        funcionario = Funcionario.query.filter_by(
            id=funcionario_id, admin_id=admin_id
        ).first()
        if not funcionario:
            return 0
        if getattr(funcionario, 'tipo_remuneracao', 'salario') == 'diaria':
            return 0

        _, ultimo = monthrange(ano, mes)

        dias_com_lancamento = {
            r.data
            for r in RDOCustoDiario.query.filter(
                RDOCustoDiario.funcionario_id == funcionario_id,
                RDOCustoDiario.data >= date(ano, mes, 1),
                RDOCustoDiario.data <= date(ano, mes, ultimo),
            ).all()
        }

        salario = float(getattr(funcionario, 'salario', 0) or 0)
        du = dias_uteis_mes(ano, mes)
        custo_dia_base = Decimal(str(round(salario / du, 2))) if du > 0 else Decimal('0')
        valor_va = Decimal(str(float(getattr(funcionario, 'valor_va', 0) or 0)))
        valor_vt = Decimal(str(float(getattr(funcionario, 'valor_vt', 0) or 0)))
        custo_total = custo_dia_base + valor_va + valor_vt

        criados = 0
        for dia in range(1, ultimo + 1):
            d = date(ano, mes, dia)
            if d.weekday() >= 5:
                continue
            if d in dias_com_lancamento:
                continue
            reg = RDOCustoDiario(
                rdo_id=None,
                funcionario_id=funcionario_id,
                admin_id=admin_id,
                data=d,
                tipo_remuneracao_snapshot='salario',
                componente_folha=custo_dia_base,
                componente_va=valor_va,
                componente_vt=valor_vt,
                componente_extra=Decimal('0'),
                custo_total_dia=custo_total,
                horas_normais=0.0,
                horas_extras=0.0,
                custo_hora_normal=None,
                dias_uteis_mes_referencia=du,
                tipo_lancamento='ocioso_mensal',
            )
            db.session.add(reg)
            criados += 1

        if criados:
            db.session.flush()
        logger.info(
            "[custo-dia] ocioso func=%d %d/%d: %d dias criados",
            funcionario_id, ano, mes, criados,
        )
        return criados

    except Exception:
        logger.exception(
            "gerar_dias_ociosos_mensalista falhou func=%s %s/%s",
            funcionario_id, ano, mes,
        )
        return 0
