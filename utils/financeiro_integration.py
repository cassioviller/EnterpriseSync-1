"""
utils/financeiro_integration.py
Funções de integração para o módulo Gestão de Custos V2.
Chamada automaticamente pelos módulos operacionais (Alimentação, Transporte, etc.)
"""

import logging
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


def resolver_obra_servico_custo_id(obra_id, servico_id, admin_id):
    """Tenta resolver o ``ObraServicoCusto`` correspondente a um par
    (obra_id, servico_id) — usado para auto-vincular custos gerados a partir
    do RDO ao serviço da obra que está sendo executado.

    Estratégia:
      1. Procura um ``ServicoObraReal`` com (obra_id, servico_id) — se houver
         um único ``ObraServicoCusto`` apontando para ele, usa-o.
      2. Se nada acima resolver, retorna ``None`` (sem chute).

    Retorna o ``id`` do ``ObraServicoCusto`` ou ``None``.
    """
    if not obra_id or not servico_id or not admin_id:
        return None
    try:
        from models import ObraServicoCusto, ServicoObraReal

        sor = (
            ServicoObraReal.query
            .filter_by(obra_id=obra_id, servico_id=servico_id, admin_id=admin_id)
            .first()
        )
        if not sor:
            return None

        candidatos = (
            ObraServicoCusto.query
            .filter_by(
                obra_id=obra_id,
                admin_id=admin_id,
                servico_obra_real_id=sor.id,
            )
            .all()
        )
        if len(candidatos) == 1:
            return candidatos[0].id
        return None
    except Exception:
        logger.exception(
            "resolver_obra_servico_custo_id(obra=%s, servico=%s) falhou",
            obra_id, servico_id,
        )
        return None


def registrar_custo_automatico(
    admin_id: int,
    tipo_categoria: str,
    entidade_nome: str,
    entidade_id,
    data,
    descricao: str,
    valor,
    obra_id=None,
    centro_custo_id=None,
    origem_tabela: str = None,
    origem_id: int = None,
    obra_servico_custo_id=None,
):
    """
    Coração da integração: registra automaticamente um custo no módulo
    Gestão de Custos V2 quando um módulo operacional gera uma despesa.

    Fluxo:
    1. Busca um GestaoCustoPai PENDENTE para a mesma (admin_id, tipo_categoria, entidade_id/nome)
    2. Se não existir, cria um novo
    3. Adiciona um GestaoCustoFilho com o lançamento
    4. Recalcula o valor_total do Pai
    5. Faz flush (sem commit — o módulo chamador faz o commit)

    Retorna o objeto GestaoCustoFilho criado, ou None em caso de erro.
    """
    try:
        from utils.tenant import is_v2_active
        if not is_v2_active():
            return None

        from app import db
        from models import GestaoCustoPai, GestaoCustoFilho
        from sqlalchemy import func

        valor_dec = Decimal(str(valor))
        if isinstance(data, str):
            data = datetime.strptime(data, '%Y-%m-%d').date()

        # Normaliza categoria (legada → nova) ANTES de buscar/gravar.
        # Ex.: SALARIO → MAO_OBRA_DIRETA, COMPRA → MATERIAL, VEICULO → EQUIPAMENTO,
        #      REEMBOLSO/DESPESA_GERAL → OUTROS
        legada_map = GestaoCustoPai._CATEGORIA_LEGADA_MAP
        categoria_normalizada = legada_map.get(tipo_categoria, tipo_categoria)

        # Lista de categorias equivalentes para casar pais antigos que ficaram
        # gravados com o nome legado no banco (antes desta normalização).
        categorias_equivalentes = {categoria_normalizada}
        for legada, nova in legada_map.items():
            if nova == categoria_normalizada:
                categorias_equivalentes.add(legada)

        # Busca pai em aberto (não PAGO/RECUSADO) para a mesma categoria+entidade
        # → 1 dropdown por (categoria + entidade), independente da data.
        # Quando entidade_id está presente (funcionário, fornecedor canônico),
        # usamos ele como chave canônica e ignoramos diferenças de entidade_nome
        # (caixa/espacos). Quando NÃO há entidade_id, fallback em entidade_nome.
        filtros = [
            GestaoCustoPai.admin_id == admin_id,
            GestaoCustoPai.tipo_categoria.in_(list(categorias_equivalentes)),
            GestaoCustoPai.status.notin_(['PAGO', 'RECUSADO']),
        ]
        if entidade_id:
            filtros.append(GestaoCustoPai.entidade_id == entidade_id)
        else:
            filtros.append(GestaoCustoPai.entidade_id.is_(None))
            filtros.append(GestaoCustoPai.entidade_nome == entidade_nome)

        pai = (
            GestaoCustoPai.query
            .filter(*filtros)
            .order_by(GestaoCustoPai.id.asc())
            .first()
        )

        if not pai:
            pai = GestaoCustoPai(
                admin_id=admin_id,
                tipo_categoria=categoria_normalizada,
                entidade_nome=entidade_nome,
                entidade_id=entidade_id,
                valor_total=Decimal('0.00'),
                status='PENDENTE',
            )
            db.session.add(pai)
            db.session.flush()
            logger.info(f"[OK] GestaoCustoPai criado: {tipo_categoria} / {entidade_nome}")

        # Calcula a soma dos filhos ANTES de adicionar o novo (evita dupla contagem
        # pelo autoflush do SQLAlchemy que executaria o INSERT antes da query)
        total_existente = (
            db.session.query(func.coalesce(func.sum(GestaoCustoFilho.valor), 0))
            .filter_by(pai_id=pai.id)
            .scalar()
        ) or Decimal('0.00')

        # Valida vínculo direto custo→serviço (Task #78). Só persiste o
        # ``obra_servico_custo_id`` quando ele pertence ao mesmo tenant e à
        # mesma obra do lançamento — caso contrário, ignora silenciosamente.
        svc_custo_id_validado = None
        if obra_servico_custo_id and obra_id:
            try:
                from models import ObraServicoCusto
                svc = ObraServicoCusto.query.filter_by(
                    id=obra_servico_custo_id,
                    admin_id=admin_id,
                    obra_id=obra_id,
                ).first()
                if svc:
                    svc_custo_id_validado = svc.id
                else:
                    logger.info(
                        "[INFO] obra_servico_custo_id=%s não pertence à obra=%s/admin=%s — ignorando vínculo",
                        obra_servico_custo_id, obra_id, admin_id,
                    )
            except Exception:
                logger.exception(
                    "Falha ao validar obra_servico_custo_id=%s",
                    obra_servico_custo_id,
                )

        filho = GestaoCustoFilho(
            pai_id=pai.id,
            data_referencia=data,
            descricao=descricao,
            valor=valor_dec,
            obra_id=obra_id,
            centro_custo_id=centro_custo_id,
            obra_servico_custo_id=svc_custo_id_validado,
            origem_tabela=origem_tabela,
            origem_id=origem_id,
            admin_id=admin_id,
        )
        db.session.add(filho)

        pai.valor_total = Decimal(str(total_existente)) + valor_dec

        db.session.flush()
        logger.info(
            f"[OK] GestaoCustoFilho adicionado: pai={pai.id} valor={valor_dec} desc={descricao[:50]}"
        )
        return filho

    except Exception as e:
        logger.error(f"[ERROR] registrar_custo_automatico falhou: {e}", exc_info=True)
        return None


def processar_reembolsos_form(request_form, admin_id, data_despesa, descricao_origem,
                              obra_id=None, centro_custo_id=None,
                              origem_tabela=None, origem_id=None):
    """
    Lê os campos de reembolso do formulário e persiste os registros.

    Campos esperados no form:
        is_reembolso  = 'true' | 'false'
        reimb_func_id[] = lista de funcionario_id
        reimb_valor[]   = lista de valores

    Retorna número de reembolsos criados (0 se não houver).
    """
    try:
        if request_form.get('is_reembolso') != 'true':
            return 0

        func_ids = request_form.getlist('reimb_func_id[]')
        valores = request_form.getlist('reimb_valor[]')

        if not func_ids:
            return 0

        from app import db
        from models import ReembolsoFuncionario, Funcionario
        from decimal import Decimal

        count = 0
        for func_id_raw, valor_raw in zip(func_ids, valores):
            try:
                func_id = int(func_id_raw)
                valor = Decimal(str(valor_raw).replace(',', '.'))
                if valor <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            func = Funcionario.query.get(func_id)
            if not func or func.admin_id != admin_id:
                continue

            reembolso = ReembolsoFuncionario(
                funcionario_id=func_id,
                valor=valor,
                data_despesa=data_despesa,
                descricao=f"Reembolso ref. {descricao_origem}"[:200],
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                origem_tabela=origem_tabela,
                origem_id=origem_id,
                admin_id=admin_id,
            )
            db.session.add(reembolso)
            db.session.flush()

            registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria='REEMBOLSO',
                entidade_nome=func.nome,
                entidade_id=func_id,
                data=data_despesa,
                descricao=f"Reembolso ref. {descricao_origem}"[:200],
                valor=float(valor),
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                origem_tabela='reembolso_funcionario',
                origem_id=reembolso.id,
            )
            count += 1
            logger.info(f"[OK] Reembolso criado: func={func.nome} valor={valor}")

        return count

    except Exception as e:
        logger.error(f"[ERROR] processar_reembolsos_form: {e}", exc_info=True)
        return 0


# Mapeamento legível de categorias
CATEGORIA_LABELS = {
    'SALARIO': 'Pagamento Salário',
    'ALIMENTACAO': 'Despesa Alimentação',
    'TRANSPORTE': 'Despesa Transporte',
    'VEICULO': 'Despesa de Frota',
    'COMPRA': 'Compra de Material',
    'REEMBOLSO': 'Reembolso a Pagar',
    'OUTROS': 'Outros Custos',
}

# Cores de status para a UI
STATUS_BADGES = {
    'PENDENTE': 'secondary',
    'SOLICITADO': 'warning',
    'AUTORIZADO': 'success',
    'PAGO': 'primary',
    'RECUSADO': 'danger',
}
