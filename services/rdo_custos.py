"""
services/rdo_custos.py
Geração automática de custos de mão-de-obra a partir do RDO.

Quando um RDO é salvo/finalizado, cada linha de RDOMaoObra vira um
GestaoCustoFilho via utils.financeiro_integration.registrar_custo_automatico,
seguindo a mesma rotina já usada pelo handler ponto_registrado:

  - Diarista (Funcionario.tipo_remuneracao == 'diaria'):
      1 custo de DIÁRIA + (opcional) VA + VT por dia, mesmo que o
      funcionário apareça em várias subatividades do mesmo RDO.
  - Salarista/horista:
      custo proporcional = horas × valor_hora (+ extras × valor_hora × 1.5),
      somando todas as linhas do funcionário no mesmo RDO.

Fonte de verdade para valores:
  RDOCustoDiario (quando existir) é lido ANTES do cálculo manual —
  assim a proporção de rateio entre RDOs do mesmo dia já foi aplicada.
  O fallback para cálculo direto existe apenas para chamadas sem
  RDOCustoDiario prévio (fluxo legado / testes).

Anti-duplicação:
  - Se já existe RegistroPonto do mesmo (funcionário, data) no admin,
    o handler ponto_registrado já gerou o custo — pulamos no RDO.
  - Idempotência por origem ('rdo_mao_obra' / '_va' / '_vt' + rdo_mao_obra.id):
    re-execuções não duplicam.
"""

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def _tenant_is_v2(admin_id: int) -> bool:
    """Versão do is_v2_active() que funciona fora de request (seed/background).
    Olha direto a versao_sistema do admin do tenant.
    """
    try:
        from models import Usuario
        admin = Usuario.query.get(admin_id)
        if not admin:
            return False
        return getattr(admin, 'versao_sistema', 'v1') == 'v2'
    except Exception:
        return False


def _existe_ponto_no_dia(funcionario_id, data_ref, admin_id) -> bool:
    try:
        from models import RegistroPonto
        return (
            RegistroPonto.query
            .filter_by(
                funcionario_id=funcionario_id,
                data=data_ref,
                admin_id=admin_id,
            )
            .first() is not None
        )
    except Exception:
        return False


def _custo_diario_rdo(rdo_id: int, funcionario_id: int):
    """Retorna a linha RDOCustoDiario para (rdo_id, funcionario_id) ou None."""
    try:
        from models import RDOCustoDiario
        return RDOCustoDiario.query.filter_by(
            rdo_id=rdo_id,
            funcionario_id=funcionario_id,
            tipo_lancamento='rdo',
        ).first()
    except Exception:
        return None


def remover_custos_rdo(rdo, admin_id) -> int:
    """Remove GestaoCustoFilho ligados aos RDOMaoObra deste RDO.

    DEVE ser chamada ANTES de RDOMaoObra ser deletado pelo fluxo de
    edição (precisamos dos IDs para casar com origem_id).
    Recalcula valor_total dos pais afetados; remove pais zerados PENDENTES.
    """
    try:
        from app import db
        from models import RDOMaoObra, GestaoCustoFilho, GestaoCustoPai
        from sqlalchemy import func

        ids = [r.id for r in RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()]
        if not ids:
            return 0

        origens = ['rdo_mao_obra', 'rdo_mao_obra_va', 'rdo_mao_obra_vt']
        filhos = (
            GestaoCustoFilho.query
            .filter(
                GestaoCustoFilho.admin_id == admin_id,
                GestaoCustoFilho.origem_tabela.in_(origens),
                GestaoCustoFilho.origem_id.in_(ids),
            )
            .all()
        )
        if not filhos:
            return 0

        pais_afetados = set()
        for f in filhos:
            pais_afetados.add(f.pai_id)
            db.session.delete(f)
        db.session.flush()

        for pai_id in pais_afetados:
            pai = GestaoCustoPai.query.get(pai_id)
            if not pai:
                continue
            total = (
                db.session.query(func.coalesce(func.sum(GestaoCustoFilho.valor), 0))
                .filter_by(pai_id=pai.id)
                .scalar()
            ) or Decimal('0.00')
            pai.valor_total = total
            if Decimal(str(total)) == Decimal('0.00') and pai.status == 'PENDENTE':
                db.session.delete(pai)

        db.session.flush()
        logger.info(
            f"[rdo-custo] removidos {len(filhos)} filhos do RDO {rdo.id}"
        )
        return len(filhos)
    except Exception:
        logger.exception("remover_custos_rdo falhou")
        return 0


def gerar_custos_mao_obra_rdo(rdo, admin_id) -> int:
    """Gera GestaoCustoFilho a partir dos valores pré-computados em RDOCustoDiario.

    Retorna o número de filhos criados (0 se nada a fazer).
    Faz commit ao final. Em caso de erro, faz rollback e devolve 0
    sem propagar exceção (o salvamento do RDO em si não pode quebrar).

    Ordem de chamada esperada:
      1. gravar_custo_funcionario_rdo(rdo, admin_id)  ← cria RDOCustoDiario
      2. gerar_custos_mao_obra_rdo(rdo, admin_id)     ← cria GestaoCustoFilho

    Fonte de valores: RDOCustoDiario (componente_folha, componente_va,
    componente_vt, componente_extra). Fallback para cálculo direto quando
    o registro diário não existir (compatibilidade com fluxos legados).
    """
    try:
        if not _tenant_is_v2(admin_id):
            logger.info(
                f"[rdo-custo] tenant {admin_id} não está em V2 — pulando geração"
            )
            return 0

        from app import db
        from models import RDOMaoObra, Funcionario, GestaoCustoFilho
        from utils.financeiro_integration import registrar_custo_automatico
        from utils import calcular_valor_hora_periodo

        if getattr(rdo, 'status', None) != 'Finalizado':
            return 0

        registros = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
        if not registros:
            return 0

        # Agrega por funcionário (1 lançamento por dia por tipo de custo)
        horas_por_func = {}
        extras_por_func = {}
        primeiro_por_func = {}
        for r in registros:
            horas_por_func[r.funcionario_id] = (
                horas_por_func.get(r.funcionario_id, 0) + float(r.horas_trabalhadas or 0)
            )
            extras_por_func[r.funcionario_id] = (
                extras_por_func.get(r.funcionario_id, 0) + float(r.horas_extras or 0)
            )
            primeiro_por_func.setdefault(r.funcionario_id, r)

        criados = 0
        for func_id, primeiro in primeiro_por_func.items():
            funcionario = Funcionario.query.filter_by(
                id=func_id, admin_id=admin_id
            ).first()
            if not funcionario:
                continue

            # Anti-duplicação com Ponto Eletrônico
            if _existe_ponto_no_dia(func_id, rdo.data_relatorio, admin_id):
                logger.info(
                    f"[rdo-custo] {funcionario.nome} em {rdo.data_relatorio}: "
                    "já tem ponto — custo será gerado pelo handler ponto_registrado"
                )
                continue

            # Idempotência principal: já existe filho desta linha?
            ja = GestaoCustoFilho.query.filter_by(
                origem_tabela='rdo_mao_obra',
                origem_id=primeiro.id,
                admin_id=admin_id,
            ).first()
            if ja:
                continue

            data_ref = rdo.data_relatorio
            data_str = data_ref.strftime('%d/%m/%Y')

            # ── Lê valores de RDOCustoDiario (pré-calculado com rateio) ────
            custo_dia = _custo_diario_rdo(rdo.id, func_id)

            if custo_dia:
                # Usa os componentes já proporcionais do registro diário
                tipo_remun = custo_dia.tipo_remuneracao_snapshot
                valor_folha = float(custo_dia.componente_folha or 0)
                valor_va    = float(custo_dia.componente_va or 0)
                valor_vt    = float(custo_dia.componente_vt or 0)
                valor_extra = float(custo_dia.componente_extra or 0)
                valor_total_folha = valor_folha + valor_extra  # SALARIO inclui extra
            else:
                # Fallback: calcula direto de RDOMaoObra (sem rateio cross-RDO)
                tipo_remun = getattr(funcionario, 'tipo_remuneracao', 'salario') or 'salario'
                if tipo_remun == 'diaria':
                    valor_folha = float(getattr(funcionario, 'valor_diaria', 0) or 0)
                    valor_extra = 0.0
                    valor_total_folha = valor_folha
                else:
                    horas = horas_por_func.get(func_id, 0)
                    extras = extras_por_func.get(func_id, 0)
                    vh = calcular_valor_hora_periodo(funcionario, data_ref, data_ref) or 0
                    valor_total_folha = horas * vh + extras * vh * 1.5
                    valor_folha = valor_total_folha
                    valor_extra = extras * vh * 1.5 if vh > 0 else 0.0
                valor_va = float(getattr(funcionario, 'valor_va', 0) or 0)
                valor_vt = float(getattr(funcionario, 'valor_vt', 0) or 0)

            if valor_total_folha <= 0 and valor_va <= 0 and valor_vt <= 0:
                logger.warning(
                    f"[rdo-custo] {funcionario.nome} sem valor > 0 — pulando"
                )
                continue

            # ── Lança custo de folha/salário ────────────────────────────────
            if valor_total_folha > 0:
                if tipo_remun == 'diaria':
                    desc_folha = (f"Diária - {funcionario.nome} - {data_str} "
                                  f"(RDO {rdo.numero_rdo})")
                else:
                    horas = horas_por_func.get(func_id, 0)
                    extras = extras_por_func.get(func_id, 0)
                    pedaco_extras = f" + {extras}h extras" if extras else ""
                    desc_folha = (f"Mão de obra: {funcionario.nome} - {data_str} "
                                  f"({horas}h{pedaco_extras}) (RDO {rdo.numero_rdo})")

                f = registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria='SALARIO',
                    entidade_nome=funcionario.nome,
                    entidade_id=funcionario.id,
                    data=data_ref,
                    descricao=desc_folha,
                    valor=valor_total_folha,
                    obra_id=rdo.obra_id,
                    origem_tabela='rdo_mao_obra',
                    origem_id=primeiro.id,
                    force_v2=True,
                )
                if f:
                    criados += 1

            # ── VA / VT (por dia trabalhado) ─────────────────────────────────
            for tag, v, cat in [
                ('VA', valor_va, 'ALIMENTACAO'),
                ('VT', valor_vt, 'TRANSPORTE'),
            ]:
                if v <= 0:
                    continue
                origem_t = f'rdo_mao_obra_{tag.lower()}'
                ja2 = GestaoCustoFilho.query.filter_by(
                    origem_tabela=origem_t,
                    origem_id=primeiro.id,
                    admin_id=admin_id,
                ).first()
                if ja2:
                    continue
                fx = registrar_custo_automatico(
                    admin_id=admin_id,
                    tipo_categoria=cat,
                    entidade_nome=funcionario.nome,
                    entidade_id=funcionario.id,
                    data=data_ref,
                    descricao=(f"{tag} - {funcionario.nome} - {data_str} "
                               f"(RDO {rdo.numero_rdo})"),
                    valor=v,
                    obra_id=rdo.obra_id,
                    origem_tabela=origem_t,
                    origem_id=primeiro.id,
                    force_v2=True,
                )
                if fx:
                    criados += 1

        db.session.commit()
        logger.info(
            f"[rdo-custo] RDO {rdo.numero_rdo}: {criados} custo(s) gerado(s)"
        )
        return criados
    except Exception:
        logger.exception("gerar_custos_mao_obra_rdo falhou")
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        return 0
