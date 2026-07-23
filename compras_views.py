import logging
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from models import (AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
                    ContaPagar, EstadoRequisicao, Fornecedor, Funcionario,
                    MapaConcorrenciaV2, Obra, ObraServicoCusto, PedidoCompra,
                    PedidoCompraItem, RequisicaoCompra, RequisicaoCompraItem,
                    GestaoCustoPai, GestaoCustoFilho, Usuario)
from utils.tenant import get_tenant_admin_id, is_v2_active

# Fase 3 — governança de compras. Imports no topo de propósito: estes
# módulos não importam compras_views de volta, então não há ciclo.
from services.alcada_compras import (esta_totalmente_aprovada,
                                     garantir_faixas_do_tenant,
                                     faixa_para_valor,
                                     pendencias_de_aprovacao, pode_aprovar,
                                     registrar_aprovacao)
from services.requisicao_compra import (TransicaoInvalida, proximo_numero,
                                        recalcular_valor, transicionar)
from utils.autorizacao import (obras_visiveis, pode_comprar_na_obra,
                               pode_requisitar_na_obra, pode_ver_obra)

logger = logging.getLogger(__name__)

compras_bp = Blueprint('compras', __name__, url_prefix='/compras')

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'compras')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'xml', 'webp'}

CONDICOES = {
    'a_vista': 'À Vista',
    '30d': 'Boleto 30 dias',
    '60d': 'Boleto 60 dias',
    '90d': 'Boleto 90 dias',
    'cartao': 'Cartão de Crédito',
    'parcelado': 'Parcelado',
}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_v2():
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


def _admin_id():
    return get_tenant_admin_id()


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS DE PROCESSAMENTO — dois fluxos de compra
# ═════════════════════════════════════════════════════════════════════════════
#
# Fluxo 1 — `processar_compra_normal`:
#   - Gera GestaoCustoPai com tipo_categoria='MATERIAL' (uma por parcela)
#   - TODOS os GCPs nascem como status='PENDENTE', independente da condição de
#     pagamento (inclusive 'a_vista'). A baixa é feita manualmente em Contas a Pagar.
#   - Cria entrada no almoxarifado (AlmoxarifadoMovimento + AlmoxarifadoEstoque)
#     para itens vinculados ao catálogo.
#   - Usado tanto no POST inicial (tipo_compra='normal') como em compras
#     aprovação_cliente que tenham sido marcadas para esse fluxo alternativo
#     futuramente (hoje, só 'normal' dispara este helper).
#
# Fluxo 2 — `processar_compra_aprovada_cliente`:
#   - Só roda DEPOIS de o cliente aprovar no portal.
#   - Gera UM GestaoCustoPai com tipo_categoria='FATURAMENTO_DIRETO', status='PAGO',
#     valor_pago=valor_total, saldo=0. Esse GCP NÃO gera FluxoCaixa porque o
#     dinheiro vai direto do cliente ao fornecedor (faturamento direto).
#   - Cria entrada NO ALMOXARIFADO (movimento ENTRADA + lote de estoque) para
#     itens vinculados ao catálogo e uma SAÍDA imediata contra a obra (obra_id
#     do pedido, sem funcionario), reconhecendo o material como já consumido
#     no centro de custo da obra.
#   - Protegido por `processada_apos_aprovacao` — idempotente.
#
# Regras de segurança comuns:
#   - admin_id SEMPRE = pedido.admin_id (multi-tenant)
#   - todas as operações em uma única transação; rollback em exceção
#   - pedido_compra_id é setado em todos os AlmoxarifadoMovimento para o
#     handler de material_entrada do EventManager ignorar esses movimentos
#     (ele dedup por pedido_compra_id).
# ═════════════════════════════════════════════════════════════════════════════

def _gerar_entrada_almoxarifado(pedido, itens_validos, admin_id, usuario_id):
    """Cria AlmoxarifadoMovimento ENTRADA + AlmoxarifadoEstoque (lote) para cada
    item do pedido que esteja vinculado ao catálogo do almoxarifado.

    NÃO commita — o chamador é responsável pelo commit/rollback.
    Retorna lista de tuplas (movimento, estoque) criadas.
    """
    itens_catalogo = [(desc, qtd, preco, almox_id, subtotal)
                      for desc, qtd, preco, almox_id, subtotal in itens_validos
                      if almox_id]
    lote_ref = pedido.numero or f"PC-{pedido.id}"
    resultado = []
    for desc_item, qtd_item, preco_item, almox_id, _ in itens_catalogo:
        mov = AlmoxarifadoMovimento(
            item_id=almox_id,
            tipo_movimento='ENTRADA',
            quantidade=qtd_item,
            valor_unitario=preco_item,
            nota_fiscal=pedido.numero,
            observacao=f"Entrada automática compra {lote_ref}: {desc_item[:100]}",
            estoque_id=None,
            fornecedor_id=pedido.fornecedor_id,
            admin_id=admin_id,
            usuario_id=usuario_id,
            obra_id=pedido.obra_id,
            pedido_compra_id=pedido.id,
        )
        db.session.add(mov)
        db.session.flush()
        estq = AlmoxarifadoEstoque(
            item_id=almox_id,
            quantidade=qtd_item,
            quantidade_inicial=qtd_item,
            quantidade_disponivel=qtd_item,
            entrada_movimento_id=mov.id,
            valor_unitario=preco_item,
            status='DISPONIVEL',
            lote=lote_ref,
            obra_id=pedido.obra_id,
            admin_id=admin_id,
        )
        db.session.add(estq)
        db.session.flush()
        mov.estoque_id = estq.id
        resultado.append((mov, estq))
    return resultado


def _gerar_saida_almoxarifado(pedido, movs_entrada, admin_id, usuario_id, descricao):
    """Gera SAÍDA imediata para os estoques criados pela ENTRADA, baixando o
    saldo e marcando o lote como CONSUMIDO. Usado tanto em 'normal com obra'
    (consumo direto na obra) quanto em 'aprovacao_cliente' (faturamento direto).

    NÃO commita — o chamador cuida do commit.
    Retorna número de saídas geradas.
    """
    from datetime import datetime as _dt
    saidas = 0
    for mov_in, estq in movs_entrada:
        estq.quantidade_disponivel = 0
        estq.status = 'CONSUMIDO'
        estq.updated_at = _dt.utcnow()

        mov_out = AlmoxarifadoMovimento(
            item_id=mov_in.item_id,
            tipo_movimento='SAIDA',
            quantidade=mov_in.quantidade,
            valor_unitario=mov_in.valor_unitario,
            funcionario_id=None,
            obra_id=pedido.obra_id,
            observacao=descricao,
            estoque_id=estq.id,
            lote=estq.lote,
            admin_id=admin_id,
            usuario_id=usuario_id,
            pedido_compra_id=pedido.id,
        )
        db.session.add(mov_out)
        saidas += 1
    return saidas


def processar_compra_normal(pedido, itens_validos, admin_id, usuario_id):
    """Processa compra tipo='normal':
       - Cria GestaoCustoPai MATERIAL (N parcelas conforme condicao_pagamento)
       - Cria GestaoCustoFilho vinculado à obra (se obra_id)
       - Cria ENTRADA no almoxarifado para itens do catálogo
       - Se obra_id está definido → também cria SAÍDA imediata contra a obra
         (material reconhecido como consumido na obra).
         Sem obra_id → material fica em estoque (entrada only).

    NÃO commita — o chamador cuida do commit.
    """
    fornecedor = Fornecedor.query.get(pedido.fornecedor_id)
    obra = Obra.query.get(pedido.obra_id) if pedido.obra_id else None
    vencimentos = _vencimentos(
        pedido.data_compra, pedido.condicao_pagamento, pedido.parcelas,
        primeira_parcela=pedido.data_vencimento_primeira_parcela,
        intervalo_dias=pedido.intervalo_parcelas_dias,
    )
    n_parcelas = len(vencimentos)
    valor_total = float(pedido.valor_total)
    valor_parcela = round(valor_total / n_parcelas, 2)
    forn_nome = fornecedor.nome if fornecedor else 'Fornecedor'
    entidade_nome = obra.nome if obra else 'Sem obra'
    entidade_id = pedido.obra_id

    for idx, (data_venc, _) in enumerate(vencimentos, start=1):
        v = valor_parcela if idx < n_parcelas else round(valor_total - valor_parcela * (n_parcelas - 1), 2)
        desc_cp = f"Compra{(' NF ' + pedido.numero) if pedido.numero else ''} - {forn_nome}"
        if n_parcelas > 1:
            desc_cp += f" - Parcela {idx}/{n_parcelas}"

        gcp = GestaoCustoPai(
            admin_id=admin_id,
            tipo_categoria='MATERIAL',
            entidade_nome=entidade_nome,
            entidade_id=entidade_id,
            fornecedor_id=pedido.fornecedor_id,
            valor_total=v,
            valor_pago=0,
            saldo=v,
            status='PENDENTE',
            data_emissao=pedido.data_compra,
            data_vencimento=data_venc,
            data_pagamento=None,
            numero_documento=pedido.numero,
            numero_parcela=idx,
            total_parcelas=n_parcelas,
            observacoes=desc_cp[:300],
            responsavel_id=pedido.responsavel_id,
        )
        db.session.add(gcp)
        db.session.flush()

        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=pedido.data_compra,
            descricao=desc_cp[:300],
            valor=v,
            obra_id=pedido.obra_id,
            obra_servico_custo_id=pedido.obra_servico_custo_id,
            origem_tabela='pedido_compra',
            origem_id=pedido.id,
        )
        db.session.add(gcf)

        # Task #11 — Arquitetura de duas camadas (sem dupla contagem):
        #   GCP (acima)  = camada de CUSTO: centro de custo da obra, DRE, relatórios.
        #   ContaPagar   = camada de OBRIGAÇÃO FINANCEIRA (payables): contas a pagar,
        #                  fluxo de caixa, Fechamento de Pagamentos.
        # A tela de Contas a Pagar exclui GCPs de pedido_compra de custos_v2
        # porque esses já aparecem como ContaPagar na tabela principal.
        # Assim, cada tela consulta apenas sua camada e não há soma duplicada.
        cp = ContaPagar(
            admin_id=admin_id,
            fornecedor_id=pedido.fornecedor_id,
            obra_id=pedido.obra_id,
            numero_documento=pedido.numero,
            descricao=desc_cp[:500],
            valor_original=v,
            valor_pago=0,
            saldo=v,
            status='PENDENTE',
            data_emissao=pedido.data_compra,
            data_vencimento=data_venc,
            origem_tipo='COMPRA',
            origem_id=pedido.id,
            pedido_compra_id=pedido.id,
            parcela_numero=idx,
            parcela_total=n_parcelas,
            responsavel_id=pedido.responsavel_id,
        )
        db.session.add(cp)

    # Entrada automática no almoxarifado (ENTRADA + lote)
    movs_entrada = _gerar_entrada_almoxarifado(pedido, itens_validos, admin_id, usuario_id)

    # Se a compra tem obra, o material é imediatamente consumido nela
    # (saída automática contra a obra). Sem obra, fica em estoque.
    saidas = 0
    if pedido.obra_id and movs_entrada:
        lote_ref = pedido.numero or f"PC-{pedido.id}"
        saidas = _gerar_saida_almoxarifado(
            pedido, movs_entrada, admin_id, usuario_id,
            descricao=f"Consumo direto na obra — compra {lote_ref}",
        )

    logger.info(
        f"[compra normal] pedido={pedido.id} parcelas={n_parcelas} "
        f"entradas_almox={len(movs_entrada)} saidas_obra={saidas}"
    )


def processar_compra_aprovada_cliente(pedido, usuario_id):
    """Processa compra tipo='aprovacao_cliente' APÓS aprovação do cliente.

    Cria:
      - UM GestaoCustoPai com tipo_categoria='FATURAMENTO_DIRETO', status='PAGO'
        (NÃO gera FluxoCaixa — o dinheiro do cliente vai direto ao fornecedor)
      - UM GestaoCustoFilho vinculado à obra
      - ENTRADA no almoxarifado para itens de catálogo
      - SAÍDA imediata contra a obra (consumo reconhecido no centro de custo)

    Idempotente: se `pedido.processada_apos_aprovacao` já é True, retorna
    imediatamente sem fazer nada.

    NÃO commita — o chamador cuida do commit/rollback.
    Levanta exceção em caso de erro (chamador faz rollback).
    """

    if pedido.processada_apos_aprovacao:
        logger.info(f"[compra aprovada cliente] pedido={pedido.id} já processado, noop")
        return

    if pedido.tipo_compra != 'aprovacao_cliente':
        raise ValueError(
            f"processar_compra_aprovada_cliente chamado com pedido tipo_compra="
            f"{pedido.tipo_compra} (esperado 'aprovacao_cliente')"
        )

    admin_id = pedido.admin_id
    fornecedor = Fornecedor.query.get(pedido.fornecedor_id)
    obra = Obra.query.get(pedido.obra_id) if pedido.obra_id else None
    forn_nome = fornecedor.nome if fornecedor else 'Fornecedor'
    entidade_nome = obra.nome if obra else 'Sem obra'

    desc_cp = (
        f"Faturamento direto cliente"
        f"{(' NF ' + pedido.numero) if pedido.numero else ''} — {forn_nome}"
    )

    # 1) GestaoCustoPai FATURAMENTO_DIRETO (status=PAGO, não gera FluxoCaixa)
    gcp = GestaoCustoPai(
        admin_id=admin_id,
        tipo_categoria='FATURAMENTO_DIRETO',
        entidade_nome=entidade_nome,
        entidade_id=pedido.obra_id,
        fornecedor_id=pedido.fornecedor_id,
        valor_total=pedido.valor_total,
        valor_pago=pedido.valor_total,
        saldo=0,
        status='PAGO',
        data_emissao=pedido.data_compra,
        data_vencimento=pedido.data_compra,
        data_pagamento=pedido.data_compra,
        numero_documento=pedido.numero,
        numero_parcela=1,
        total_parcelas=1,
        observacoes=desc_cp[:300],
        responsavel_id=pedido.responsavel_id,
    )
    db.session.add(gcp)
    db.session.flush()

    gcf = GestaoCustoFilho(
        pai_id=gcp.id,
        admin_id=admin_id,
        data_referencia=pedido.data_compra,
        descricao=desc_cp[:300],
        valor=pedido.valor_total,
        obra_id=pedido.obra_id,
        obra_servico_custo_id=pedido.obra_servico_custo_id,
        origem_tabela='pedido_compra',
        origem_id=pedido.id,
    )
    db.session.add(gcf)

    # 2) Reconstituir itens_validos a partir dos PedidoCompraItem para gerar movimentos
    itens_pedido = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()
    itens_validos = [
        (i.descricao, float(i.quantidade), float(i.preco_unitario),
         i.almoxarifado_item_id, float(i.subtotal))
        for i in itens_pedido
    ]
    movs_entrada = _gerar_entrada_almoxarifado(pedido, itens_validos, admin_id, usuario_id)

    # 3) SAÍDA imediata contra a obra (reconhecendo consumo faturamento direto)
    lote_ref = pedido.numero or f"PC-{pedido.id}"
    saidas = _gerar_saida_almoxarifado(
        pedido, movs_entrada, admin_id, usuario_id,
        descricao=f"Consumo faturamento direto — compra {lote_ref}",
    )

    pedido.processada_apos_aprovacao = True
    db.session.flush()

    logger.info(
        f"[compra aprovada cliente] pedido={pedido.id} GCP#{gcp.id} FATURAMENTO_DIRETO "
        f"criado; entradas={len(movs_entrada)} saidas={saidas}"
    )


def _vencimentos(data_compra, condicao, parcelas, primeira_parcela=None, intervalo_dias=None):
    """Gera lista de (data_vencimento, valor_parcela) para ContaPagar / GCP.

    Args:
        primeira_parcela: date opcional — data do primeiro vencimento (Task #11).
        intervalo_dias: int opcional — dias entre parcelas (default 30).
    """
    if not isinstance(data_compra, date):
        data_compra = date.today()

    mapa_dias = {'a_vista': 0, '30d': 30, '60d': 60, '90d': 90, 'cartao': 30}

    if condicao in mapa_dias:
        dias = mapa_dias[condicao]
        # Se data personalizada foi fornecida, usá-la; senão calcular como antes
        data_venc = primeira_parcela if primeira_parcela else (data_compra + timedelta(days=dias))
        return [(data_venc, None)]

    # parcelado → N datas
    parcelas = max(1, int(parcelas or 1))
    intervalo = int(intervalo_dias) if intervalo_dias else 30
    datas = []
    for i in range(1, parcelas + 1):
        if primeira_parcela:
            data_venc = primeira_parcela + timedelta(days=intervalo * (i - 1))
        else:
            data_venc = data_compra + timedelta(days=intervalo * i)
        datas.append((data_venc, None))
    return datas


# ─────────────────────────────────────────────
# LISTA
# ─────────────────────────────────────────────
@compras_bp.route('/')
@login_required
def index():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    filtro_fornecedor = request.args.get('fornecedor_id', type=int)
    filtro_data_inicio = request.args.get('data_inicio')
    filtro_data_fim = request.args.get('data_fim')

    query = PedidoCompra.query.filter_by(admin_id=admin_id).order_by(PedidoCompra.data_compra.desc())

    if filtro_fornecedor:
        query = query.filter_by(fornecedor_id=filtro_fornecedor)
    if filtro_data_inicio:
        query = query.filter(PedidoCompra.data_compra >= filtro_data_inicio)
    if filtro_data_fim:
        query = query.filter(PedidoCompra.data_compra <= filtro_data_fim)

    pedidos = query.limit(200).all()
    total_valor = sum(float(p.valor_total) for p in pedidos)

    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()

    return render_template(
        'compras/index.html',
        pedidos=pedidos,
        total_valor=total_valor,
        fornecedores=fornecedores,
        filtro_fornecedor=filtro_fornecedor,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim,
        CONDICOES=CONDICOES,
    )


# ─────────────────────────────────────────────
# APROVAÇÃO DO CLIENTE — lista de compras aguardando
# ─────────────────────────────────────────────
@compras_bp.route('/aprovacao')
@login_required
def aprovacao():
    """Lista compras do tipo 'aprovacao_cliente' agrupadas por status:
       - PENDENTE  : aguardando cliente aprovar no portal
       - APROVADO  : cliente aprovou (já processadas)
       - RECUSADO  : cliente recusou
    """
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    base = (
        PedidoCompra.query
        .filter_by(admin_id=admin_id, tipo_compra='aprovacao_cliente')
        .order_by(PedidoCompra.created_at.desc())
    )

    # Pendentes: AGUARDANDO_APROVACAO_CLIENTE (novo) + PENDENTE (legado) + NULL
    pendentes = base.filter(
        db.or_(
            PedidoCompra.status_aprovacao_cliente == 'AGUARDANDO_APROVACAO_CLIENTE',
            PedidoCompra.status_aprovacao_cliente == 'PENDENTE',
            PedidoCompra.status_aprovacao_cliente.is_(None),
        )
    ).all()
    aprovadas = base.filter(PedidoCompra.status_aprovacao_cliente == 'APROVADO').all()
    recusadas = base.filter(
        PedidoCompra.status_aprovacao_cliente.in_(['RECUSADO', 'REJEITADO'])
    ).all()

    total_pendente = sum(float(p.valor_total) for p in pendentes)
    total_aprovada = sum(float(p.valor_total) for p in aprovadas)

    return render_template(
        'compras/aprovacao.html',
        pendentes=pendentes,
        aprovadas=aprovadas,
        recusadas=recusadas,
        total_pendente=total_pendente,
        total_aprovada=total_aprovada,
        CONDICOES=CONDICOES,
    )


# ─────────────────────────────────────────────
# NOVA COMPRA — GET
# ─────────────────────────────────────────────
@compras_bp.route('/nova', methods=['GET'])
@login_required
def nova():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    itens_catalogo = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by('nome').all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    funcionarios_json = [{'id': f.id, 'nome': f.nome} for f in funcionarios]
    # Usuários ativos do tenant para seleção de responsável
    usuarios = Usuario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()

    return render_template(
        'compras/nova_compra.html',
        fornecedores=fornecedores,
        obras=obras,
        itens_catalogo=itens_catalogo,
        funcionarios=funcionarios,
        funcionarios_json=funcionarios_json,
        usuarios=usuarios,
        CONDICOES=CONDICOES,
        hoje=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# NOVA COMPRA — POST
# ─────────────────────────────────────────────
@compras_bp.route('/nova', methods=['POST'])
@login_required
def nova_post():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    try:
        fornecedor_id_raw = request.form.get('fornecedor_id', '').strip()
        if not fornecedor_id_raw:
            flash('Selecione um fornecedor antes de salvar a compra. '
                  'Se nenhum aparece no menu, cadastre o primeiro fornecedor.', 'danger')
            return redirect(url_for('compras.nova'))
        try:
            fornecedor_id = int(fornecedor_id_raw)
        except (TypeError, ValueError):
            flash('Fornecedor inválido. Selecione um fornecedor pelo menu.', 'danger')
            return redirect(url_for('compras.nova'))

        # Defesa multi-tenant: garante que o fornecedor pertence ao admin logado
        from models import Fornecedor as _Fornecedor
        fornecedor_owner = _Fornecedor.query.filter_by(
            id=fornecedor_id, admin_id=admin_id, ativo=True
        ).first()
        if not fornecedor_owner:
            flash('Fornecedor não encontrado ou não pertence à sua conta. '
                  'Selecione um fornecedor da lista.', 'danger')
            return redirect(url_for('compras.nova'))

        data_compra = datetime.strptime(request.form.get('data_compra'), '%Y-%m-%d').date()
        condicao = request.form.get('condicao_pagamento', 'a_vista')
        parcelas = int(request.form.get('parcelas', 1))
        numero = request.form.get('numero', '').strip() or None
        observacoes = request.form.get('observacoes', '').strip() or None
        # Task #11 — Responsável e datas de parcela personalizadas
        responsavel_id_raw = request.form.get('responsavel_id', '').strip()
        responsavel_id = int(responsavel_id_raw) if responsavel_id_raw else None
        # Multi-tenant validation: responsavel must belong to this tenant
        if responsavel_id:
            resp_ok = Usuario.query.filter_by(id=responsavel_id, admin_id=admin_id).first()
            if not resp_ok:
                responsavel_id = None
        primeira_parcela_raw = request.form.get('data_primeira_parcela', '').strip()
        data_primeira_parcela = (
            datetime.strptime(primeira_parcela_raw, '%Y-%m-%d').date()
            if primeira_parcela_raw else None
        )
        intervalo_parcelas_raw = request.form.get('intervalo_parcelas_dias', '').strip()
        intervalo_parcelas_dias = int(intervalo_parcelas_raw) if intervalo_parcelas_raw else None
        obra_id = request.form.get('obra_id') or None
        if obra_id:
            try:
                obra_id = int(obra_id)
            except (TypeError, ValueError):
                flash('Obra inválida. Selecione uma obra pelo menu.', 'danger')
                return redirect(url_for('compras.nova'))
            # Defesa multi-tenant: garante que a obra pertence ao admin logado
            from models import Obra as _Obra
            obra_owner = _Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra_owner:
                flash('Obra não encontrada ou não pertence à sua conta. '
                      'Selecione uma obra da lista.', 'danger')
                return redirect(url_for('compras.nova'))

        # Etapa (ObraServicoCusto) opcional — só vale com obra; valida obra+tenant.
        osc_id = request.form.get('obra_servico_custo_id') or None
        if osc_id and obra_id:
            try:
                osc_id = int(osc_id)
            except (TypeError, ValueError):
                osc_id = None
            if osc_id:
                from models import ObraServicoCusto as _OSC
                if not _OSC.query.filter_by(
                        id=osc_id, obra_id=obra_id, admin_id=admin_id).first():
                    osc_id = None
        else:
            osc_id = None

        # Tipo de compra: 'normal' (default) ou 'aprovacao_cliente'
        tipo_compra = request.form.get('tipo_compra', 'normal').strip()
        if tipo_compra not in ('normal', 'aprovacao_cliente'):
            tipo_compra = 'normal'

        # Regra: 'aprovacao_cliente' EXIGE obra (o cliente aprova no portal da obra).
        if tipo_compra == 'aprovacao_cliente' and not obra_id:
            flash('Compras do tipo "Aprovação do Cliente" exigem uma obra '
                  '(o cliente aprova pelo portal da obra). Selecione uma obra.', 'danger')
            return redirect(url_for('compras.nova'))

        # Reembolso é incompatível com aprovação_cliente (o dinheiro vem do cliente,
        # ninguém está pagando do bolso)
        is_reembolso = request.form.get('is_reembolso') == 'true'
        if tipo_compra == 'aprovacao_cliente' and is_reembolso:
            flash('Compras com aprovação do cliente não podem ter reembolso. '
                  'Desmarque a opção de reembolso ou escolha tipo "Normal".', 'danger')
            return redirect(url_for('compras.nova'))

        # Itens da compra
        descricoes = request.form.getlist('item_descricao[]')
        quantidades = request.form.getlist('item_quantidade[]')
        precos = request.form.getlist('item_preco[]')
        almox_ids = request.form.getlist('item_almoxarifado_id[]')

        if not descricoes or not any(d.strip() for d in descricoes):
            flash('Adicione pelo menos um item à compra.', 'danger')
            return redirect(url_for('compras.nova'))

        # Upload do anexo
        anexo_url = None
        arquivo = request.files.get('anexo')
        if arquivo and arquivo.filename and _allowed_file(arquivo.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            nome_arquivo = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(arquivo.filename)}"
            caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
            arquivo.save(caminho)
            anexo_url = '/' + caminho.replace(os.sep, '/')

        # Calcular valor total
        valor_total = 0.0
        itens_validos = []
        for i, desc in enumerate(descricoes):
            desc = desc.strip()
            if not desc:
                continue
            qtd = float((quantidades[i] if i < len(quantidades) else '1').replace(',', '.') or '1')
            preco = float((precos[i] if i < len(precos) else '0').replace(',', '.') or '0')
            almox_id = almox_ids[i] if i < len(almox_ids) else ''
            almox_id = int(almox_id) if almox_id else None
            subtotal = round(qtd * preco, 2)
            valor_total += subtotal
            itens_validos.append((desc, qtd, preco, almox_id, subtotal))

        valor_total = round(valor_total, 2)

        # --- Pedido principal ---
        # Para tipo 'aprovacao_cliente', começa com status_aprovacao_cliente='PENDENTE'
        # e processada_apos_aprovacao=False; nenhuma GestaoCustoPai/movimento é criado
        # até o cliente aprovar no portal.
        pedido = PedidoCompra(
            numero=numero,
            fornecedor_id=fornecedor_id,
            data_compra=data_compra,
            obra_id=obra_id,
            obra_servico_custo_id=osc_id,
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=observacoes,
            anexo_url=anexo_url,
            tipo_compra=tipo_compra,
            processada_apos_aprovacao=False,
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE' if tipo_compra == 'aprovacao_cliente' else None,
            admin_id=admin_id,
            responsavel_id=responsavel_id,
            data_vencimento_primeira_parcela=data_primeira_parcela,
            intervalo_parcelas_dias=intervalo_parcelas_dias,
        )
        db.session.add(pedido)
        db.session.flush()

        # --- Itens ---
        for desc, qtd, preco, almox_id, subtotal in itens_validos:
            item = PedidoCompraItem(
                pedido_id=pedido.id,
                almoxarifado_item_id=almox_id,
                descricao=desc,
                quantidade=qtd,
                preco_unitario=preco,
                subtotal=subtotal,
                admin_id=admin_id,
            )
            db.session.add(item)
        db.session.flush()

        # --- Bifurca por tipo_compra ---
        if tipo_compra == 'normal':
            processar_compra_normal(pedido, itens_validos, admin_id, current_user.id)
            db.session.commit()

            # Lançamento contábil automático V2 (só faz sentido p/ normal)
            try:
                from contabilidade_utils import gerar_lancamento_contabil_automatico
                forn = Fornecedor.query.get(fornecedor_id)
                gerar_lancamento_contabil_automatico(
                    admin_id=admin_id,
                    tipo_operacao='compra_material',
                    valor=float(valor_total),
                    data=data_compra,
                    descricao=f"Compra{(' NF ' + numero) if numero else ''} - {forn.nome if forn else 'Fornecedor'}",
                )
            except Exception as _e:
                logger.warning(f"[WARN] Lancamento contabil compra nao gerado: {_e}")

            # Reembolso a Funcionários V2 (só em compras normais)
            try:
                from utils.financeiro_integration import processar_reembolsos_form
                n_reimb = processar_reembolsos_form(
                    request_form=request.form,
                    admin_id=admin_id,
                    data_despesa=data_compra,
                    descricao_origem=f"Compra{(' NF ' + numero) if numero else ''}",
                    obra_id=obra_id,
                    centro_custo_id=(int(request.form.get('centro_custo_id'))
                                     if request.form.get('centro_custo_id') else None),
                    origem_tabela='pedido_compra',
                    origem_id=pedido.id,
                )
                if n_reimb:
                    db.session.commit()
                    logger.info(f"[OK] {n_reimb} reembolso(s) registrado(s) na compra {pedido.id}")
            except Exception as _re:
                logger.warning(f"[WARN] Reembolso compra nao processado: {_re}")

            flash('Compra registrada com sucesso! Custo, contas a pagar e entrada no almoxarifado geradas.', 'success')

        else:  # tipo_compra == 'aprovacao_cliente'
            # Apenas persiste o pedido + itens. Custos e movimentos só serão criados
            # quando o cliente aprovar no portal (em portal_obras_views.aprovar_compra).
            db.session.commit()
            flash('Compra registrada e enviada para aprovação do cliente. '
                  'Nenhum custo ou movimento de estoque foi criado ainda — isso acontecerá '
                  'automaticamente quando o cliente aprovar no portal.', 'info')

        return redirect(url_for('compras.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao salvar pedido_compra: {e}")
        flash(f'Erro ao salvar compra: {str(e)}', 'danger')
        return redirect(url_for('compras.nova'))


# ─────────────────────────────────────────────
# DETALHE
# ─────────────────────────────────────────────
@compras_bp.route('/<int:pedido_id>')
@login_required
def detalhe(pedido_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()
    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido_id).all()
    custos_gestao = GestaoCustoFilho.query.filter_by(
        origem_tabela='pedido_compra', origem_id=pedido_id
    ).all()

    # Calcular quantidades já recebidas por almoxarifado_item_id
    from sqlalchemy import func as sqlfunc2
    rows_det = (
        db.session.query(
            AlmoxarifadoMovimento.item_id,
            sqlfunc2.sum(AlmoxarifadoMovimento.quantidade).label('qtd_tot'),
            sqlfunc2.max(AlmoxarifadoMovimento.id).label('last_mov_id'),
        )
        .filter_by(pedido_compra_id=pedido_id, tipo_movimento='ENTRADA', admin_id=admin_id)
        .group_by(AlmoxarifadoMovimento.item_id)
        .all()
    )
    qtd_recebida_detalhe = {r.item_id: float(r.qtd_tot or 0) for r in rows_det}
    last_mov_id_map = {r.item_id: r.last_mov_id for r in rows_det}
    # Carregar o movimento mais recente por item para mostrar data e qtd no template
    recebimento_por_item = {}
    for item_id, mov_id in last_mov_id_map.items():
        mov = AlmoxarifadoMovimento.query.get(mov_id)
        if mov:
            recebimento_por_item[item_id] = mov
    itens_recebidos_ids = set(qtd_recebida_detalhe.keys())

    # Itens do pedido que têm vínculo com o catálogo do almoxarifado
    tem_itens_almox = any(i.almoxarifado_item_id for i in itens)
    # todos_recebidos: baseado em quantidade total (suporta múltiplas linhas com mesmo item_id)
    qtd_total_por_item_pedido = {}
    for i in itens:
        if i.almoxarifado_item_id:
            qtd_total_por_item_pedido[i.almoxarifado_item_id] = (
                qtd_total_por_item_pedido.get(i.almoxarifado_item_id, 0.0) + float(i.quantidade or 0)
            )
    todos_recebidos = tem_itens_almox and all(
        qtd_recebida_detalhe.get(item_id, 0.0) >= qtd_total
        for item_id, qtd_total in qtd_total_por_item_pedido.items()
    )

    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()

    return render_template(
        'compras/detalhe.html',
        pedido=pedido,
        itens=itens,
        custos_gestao=custos_gestao,
        CONDICOES=CONDICOES,
        itens_recebidos_ids=itens_recebidos_ids,
        recebimento_por_item=recebimento_por_item,
        qtd_recebida_detalhe=qtd_recebida_detalhe,
        tem_itens_almox=tem_itens_almox,
        todos_recebidos=todos_recebidos,
        fornecedores=fornecedores,
        obras=obras,
    )


# ─────────────────────────────────────────────
# RECEBIMENTO NO ALMOXARIFADO
# ─────────────────────────────────────────────
@compras_bp.route('/receber/<int:pedido_id>', methods=['POST'])
@login_required
def receber(pedido_id):
    """Registra o recebimento físico dos itens de um PedidoCompra no almoxarifado."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()
    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido_id).all()
    itens_com_catalogo = [i for i in itens if i.almoxarifado_item_id]

    if not itens_com_catalogo:
        flash('Nenhum item deste pedido está vinculado ao catálogo do almoxarifado.', 'warning')
        return redirect(url_for('compras.detalhe', pedido_id=pedido_id))

    movimentos_criados = 0
    from sqlalchemy import func as sqlfunc
    # Quantidades já recebidas (somadas) por almoxarifado_item_id para este pedido
    rows_recebidos = (
        db.session.query(
            AlmoxarifadoMovimento.item_id,
            sqlfunc.sum(AlmoxarifadoMovimento.quantidade).label('qtd_recebida')
        )
        .filter_by(pedido_compra_id=pedido_id, tipo_movimento='ENTRADA', admin_id=admin_id)
        .group_by(AlmoxarifadoMovimento.item_id)
        .all()
    )
    qtd_recebida_por_item = {r.item_id: float(r.qtd_recebida or 0) for r in rows_recebidos}

    # Agregar quantidades totais pedidas por almoxarifado_item_id (suporta itens repetidos).
    # Usar último preço e primeira descrição do grupo para o movimento.
    from collections import OrderedDict
    itens_agregados = OrderedDict()
    for item in itens_com_catalogo:
        aid = item.almoxarifado_item_id
        if aid not in itens_agregados:
            itens_agregados[aid] = {
                'qtd_total': 0.0,
                'preco': float(item.preco_unitario or 0),
                'descricao': item.descricao,
            }
        itens_agregados[aid]['qtd_total'] += float(item.quantidade or 0)
        itens_agregados[aid]['preco'] = float(item.preco_unitario or 0)

    lote_ref = pedido.numero or f"PC-{pedido_id}"

    try:
        for almox_id, info in itens_agregados.items():
            qtd_total_pedido = info['qtd_total']
            qtd_ja_recebida = qtd_recebida_por_item.get(almox_id, 0.0)
            qtd_pendente = round(qtd_total_pedido - qtd_ja_recebida, 6)
            if qtd_pendente <= 0:
                logger.info(f"[SKIP] Item {almox_id}: já totalmente recebido ({qtd_ja_recebida}/{qtd_total_pedido})")
                continue

            preco_unit = info['preco']
            desc_item = info['descricao']

            # Um movimento por item_id consolidado
            movimento = AlmoxarifadoMovimento(
                item_id=almox_id,
                tipo_movimento='ENTRADA',
                quantidade=qtd_pendente,
                valor_unitario=preco_unit,
                nota_fiscal=pedido.numero,
                observacao=f"Recebimento Compra {lote_ref}: {desc_item[:100]}",
                estoque_id=None,
                fornecedor_id=pedido.fornecedor_id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=pedido.obra_id,
                pedido_compra_id=pedido_id,
            )
            db.session.add(movimento)
            db.session.flush()

            # Lote FIFO no estoque
            estoque = AlmoxarifadoEstoque(
                item_id=almox_id,
                quantidade=qtd_pendente,
                quantidade_inicial=qtd_pendente,
                quantidade_disponivel=qtd_pendente,
                entrada_movimento_id=movimento.id,
                valor_unitario=preco_unit,
                status='DISPONIVEL',
                lote=lote_ref,
                obra_id=pedido.obra_id,
                admin_id=admin_id,
            )
            db.session.add(estoque)
            db.session.flush()
            movimento.estoque_id = estoque.id
            movimentos_criados += 1

        db.session.commit()
        if movimentos_criados:
            flash(f'Recebimento registrado: {movimentos_criados} item(ns) lançado(s) no almoxarifado. '
                  f'Custo já reconhecido na compra — sem duplicação.', 'success')
        else:
            flash('Todos os itens já haviam sido recebidos anteriormente.', 'info')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Falha ao registrar recebimento do pedido {pedido_id}: {e}")
        flash(f'Erro ao registrar recebimento: {str(e)}', 'danger')

    return redirect(url_for('compras.detalhe', pedido_id=pedido_id))


# ─────────────────────────────────────────────
# EDIÇÃO DE LANÇAMENTO FINANCEIRO DE COMPRA
# ─────────────────────────────────────────────
@compras_bp.route('/lancamento/<int:gcp_id>/editar', methods=['POST'])
@login_required
def editar_lancamento(gcp_id):
    """Edita campos financeiros/vínculo de um GestaoCustoPai originado de compra,
    independentemente de estar PAGO ou PENDENTE.
    Campos permitidos: obra_id, data_vencimento, fornecedor_id, observacoes.
    """
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    gcp = GestaoCustoPai.query.filter_by(id=gcp_id, admin_id=admin_id).first_or_404()

    # Restrição de segurança: apenas GCPs originados de pedido_compra podem ser
    # editados por esta rota — evita edição acidental de outros lançamentos.
    filho_compra = GestaoCustoFilho.query.filter_by(
        pai_id=gcp_id, origem_tabela='pedido_compra'
    ).first()
    if not filho_compra:
        flash('Este lançamento não pode ser editado por esta rota.', 'danger')
        return redirect(request.referrer or url_for('compras.index'))

    try:
        obra_id_raw = request.form.get('obra_id', '').strip()
        obra_id = int(obra_id_raw) if obra_id_raw else None
        if obra_id:
            obra_check = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra_check:
                flash('Obra não encontrada ou sem permissão.', 'danger')
                return redirect(request.referrer or url_for('compras.index'))
            gcp.entidade_nome = obra_check.nome
            gcp.entidade_id = obra_id
        else:
            gcp.entidade_nome = 'Sem obra'
            gcp.entidade_id = None

        data_venc_raw = request.form.get('data_vencimento', '').strip()
        if data_venc_raw:
            from datetime import datetime as _dt
            gcp.data_vencimento = _dt.strptime(data_venc_raw, '%Y-%m-%d').date()

        fornecedor_id_raw = request.form.get('fornecedor_id', '').strip()
        if fornecedor_id_raw:
            forn_id = int(fornecedor_id_raw)
            forn_check = Fornecedor.query.filter_by(id=forn_id, admin_id=admin_id).first()
            if forn_check:
                gcp.fornecedor_id = forn_id

        observacoes = request.form.get('observacoes', '').strip()
        gcp.observacoes = observacoes[:300] if observacoes else None

        # Sync GestaoCustoFilho obra_id
        for filho in gcp.itens:
            filho.obra_id = obra_id

        db.session.commit()
        flash('Lançamento atualizado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Falha ao editar lancamento GCP#{gcp_id}: {e}")
        flash('Não foi possível atualizar o lançamento. Tente novamente.', 'danger')

    return redirect(request.referrer or url_for('compras.index'))


# ─────────────────────────────────────────────
# EXCLUSÃO
# ─────────────────────────────────────────────
@compras_bp.route('/excluir/<int:pedido_id>', methods=['POST'])
@login_required
def excluir(pedido_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()
    try:
        # Remover GestaoCustoPai vinculados (criados via filho origem_tabela=pedido_compra)
        filhos = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=pedido_id
        ).all()
        pai_ids = list({f.pai_id for f in filhos})
        for pai_id in pai_ids:
            pai = GestaoCustoPai.query.get(pai_id)
            if pai and pai.status in ('PENDENTE', 'RECUSADO'):
                db.session.delete(pai)
        # Manter ContaPagar legados (histórico) mas não criar novos
        db.session.delete(pedido)
        db.session.commit()
        flash('Compra e custos vinculados foram excluídos.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {e}', 'danger')
    return redirect(url_for('compras.index'))


# ═════════════════════════════════════════════════════════════════════════════
# FASE 3 — REQUISIÇÃO DE COMPRA (requisição → aprovação → pedido)
# ═════════════════════════════════════════════════════════════════════════════
#
# Estas rotas existem SEMPRE. O que a flag `compras_governanca_ativa`
# muda é apenas se `POST /compras/nova` continua aceitando pedido sem
# requisição (Task 9). Com a flag desligada, este é um caminho opcional
# que não tira nada de ninguém.


def _requisicao_do_tenant(requisicao_id):
    """Carrega a requisição do tenant logado ou aborta com 404.

    404 e não 403, pela mesma razão do `obra_required` da Fase 1: não
    vazar sequer a existência de documento de outra empresa.
    """
    from flask import abort

    admin_id = _admin_id()
    if admin_id is None:
        abort(404)
    req = RequisicaoCompra.query.filter_by(
        id=requisicao_id, admin_id=admin_id).first()
    if req is None:
        abort(404)
    return req


def _itens_do_form():
    """Lê os itens do formulário. Devolve lista de dicts, ignorando linhas
    sem descrição (o formulário mantém uma linha-modelo vazia)."""
    descricoes = request.form.getlist('item_descricao[]')
    unidades = request.form.getlist('item_unidade[]')
    quantidades = request.form.getlist('item_quantidade[]')
    precos = request.form.getlist('item_preco[]')
    almox_ids = request.form.getlist('item_almoxarifado_id[]')

    itens = []
    for i, desc in enumerate(descricoes):
        desc = (desc or '').strip()
        if not desc:
            continue

        def _num(lista, idx, padrao='0'):
            bruto = (lista[idx] if idx < len(lista) else '') or padrao
            return float(str(bruto).replace('.', '').replace(',', '.')
                         if ',' in str(bruto) else str(bruto))

        almox_bruto = almox_ids[i] if i < len(almox_ids) else ''
        itens.append({
            'descricao': desc[:200],
            'unidade': ((unidades[i] if i < len(unidades) else '') or 'un')[:20],
            'quantidade': _num(quantidades, i, '1'),
            'preco': _num(precos, i, '0'),
            'almoxarifado_item_id': int(almox_bruto) if almox_bruto else None,
        })
    return itens


@compras_bp.route('/requisicoes')
@login_required
def requisicoes():
    """Lista de requisições do tenant, filtrada pelo escopo de obra."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    estado_filtro = (request.args.get('estado') or '').strip().upper()

    query = RequisicaoCompra.query.filter_by(admin_id=admin_id)

    # Fase 1 — escopo por obra. `obras_visiveis()` já aplica os dois eixos
    # (tenant sempre; obra só com a flag do tenant ligada). Sem isso, a
    # listagem repetiria o erro de `compras_views.py:421`, que filtra só
    # por admin_id.
    ids_visiveis = [o.id for o in obras_visiveis(admin_id).with_entities(Obra.id)]
    query = query.filter(RequisicaoCompra.obra_id.in_(ids_visiveis or [-1]))

    if estado_filtro in {e.name for e in EstadoRequisicao}:
        query = query.filter(RequisicaoCompra.estado ==
                             EstadoRequisicao[estado_filtro])

    requisicoes_lista = query.order_by(RequisicaoCompra.id.desc()).limit(200).all()

    contagem = {}
    for estado in EstadoRequisicao:
        contagem[estado.name] = sum(
            1 for r in requisicoes_lista if r.estado == estado)

    return render_template(
        'compras/requisicoes.html',
        requisicoes=requisicoes_lista,
        contagem=contagem,
        estado_filtro=estado_filtro,
        estados=list(EstadoRequisicao),
    )


@compras_bp.route('/requisicoes/nova', methods=['GET'])
@login_required
def requisicao_nova():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = obras_visiveis(admin_id).filter(Obra.ativo.is_(True)).order_by(
        Obra.nome).all()
    itens_catalogo = AlmoxarifadoItem.query.filter_by(
        admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()

    return render_template(
        'compras/requisicao_nova.html',
        obras=obras,
        itens_catalogo=itens_catalogo,
        hoje=date.today().isoformat(),
    )


@compras_bp.route('/requisicoes/nova', methods=['POST'])
@login_required
def requisicao_nova_post():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    obra_id_bruto = (request.form.get('obra_id') or '').strip()
    if not obra_id_bruto:
        flash('Toda requisição precisa de uma obra. É o vínculo que faz o '
              'custo aparecer no lugar certo.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))
    try:
        obra_id = int(obra_id_bruto)
    except (TypeError, ValueError):
        flash('Obra inválida. Selecione uma obra pelo menu.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Defesa de tenant + escopo de obra (Fase 1) num só predicado.
    if not pode_ver_obra(obra_id):
        flash('Obra não encontrada ou fora do seu acesso.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))
    if not pode_requisitar_na_obra(obra_id):
        flash('Você não tem papel de gestor ou comprador nesta obra e não '
              'pode abrir requisição para ela.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Etapa opcional — mesma validação de pedido_compra (compras_views.py:597)
    osc_id_bruto = (request.form.get('obra_servico_custo_id') or '').strip()
    osc_id = None
    if osc_id_bruto:
        try:
            candidato = int(osc_id_bruto)
        except (TypeError, ValueError):
            candidato = None
        if candidato and ObraServicoCusto.query.filter_by(
                id=candidato, obra_id=obra_id, admin_id=admin_id).first():
            osc_id = candidato

    mapa_id_bruto = (request.form.get('mapa_v2_id') or '').strip()
    mapa_id = None
    if mapa_id_bruto:
        try:
            candidato = int(mapa_id_bruto)
        except (TypeError, ValueError):
            candidato = None
        if candidato and MapaConcorrenciaV2.query.filter_by(
                id=candidato, obra_id=obra_id, admin_id=admin_id).first():
            mapa_id = candidato

    itens = _itens_do_form()
    if not itens:
        flash('Adicione pelo menos um item à requisição.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    data_nec_bruta = (request.form.get('data_necessidade') or '').strip()
    try:
        data_necessidade = (datetime.strptime(data_nec_bruta, '%Y-%m-%d').date()
                            if data_nec_bruta else None)
    except ValueError:
        data_necessidade = None

    # Tenants criados depois da migration 243 não têm faixa; semeia aqui,
    # antes de existir requisição que dependa delas.
    garantir_faixas_do_tenant(admin_id)

    # Retry de numeração: o UNIQUE (admin_id, numero) fecha a corrida entre
    # dois requests simultâneos. Mesmo padrão de views/obras.py:3279.
    from sqlalchemy.exc import IntegrityError

    for tentativa in range(3):
        try:
            requisicao = RequisicaoCompra(
                numero=proximo_numero(admin_id),
                admin_id=admin_id,
                obra_id=obra_id,
                obra_servico_custo_id=osc_id,
                mapa_v2_id=mapa_id,
                solicitante_id=current_user.id,
                estado=EstadoRequisicao.RASCUNHO,
                justificativa=(request.form.get('justificativa') or '').strip() or None,
                data_necessidade=data_necessidade,
                valor_estimado=0,
            )
            db.session.add(requisicao)
            db.session.flush()

            for item in itens:
                db.session.add(RequisicaoCompraItem(
                    requisicao_id=requisicao.id,
                    admin_id=admin_id,
                    almoxarifado_item_id=item['almoxarifado_item_id'],
                    descricao=item['descricao'],
                    unidade=item['unidade'],
                    quantidade=item['quantidade'],
                    preco_estimado=item['preco'],
                ))
            db.session.flush()
            recalcular_valor(requisicao)
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            logger.warning('colisão de numeração de requisição no tenant %s '
                           '(tentativa %s)', admin_id, tentativa + 1)
    else:
        flash('Não foi possível gerar o número da requisição. Tente novamente.',
              'danger')
        return redirect(url_for('compras.requisicao_nova'))

    faixa = faixa_para_valor(admin_id, requisicao.valor_estimado)
    flash(f'Requisição {requisicao.numero} criada (R$ '
          f'{requisicao.valor_estimado}). Pela alçada configurada, ela vai '
          f'precisar de {faixa.aprovacoes_necessarias} aprovação(ões).',
          'success')
    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao.id))


@compras_bp.route('/requisicoes/<int:requisicao_id>')
@login_required
def requisicao_detalhe(requisicao_id):
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    from flask import abort
    if not pode_ver_obra(requisicao.obra_id):
        abort(404)

    faixa = faixa_para_valor(requisicao.admin_id, requisicao.valor_estimado)
    pode, motivo_recusa = pode_aprovar(requisicao, current_user)

    pedidos = PedidoCompra.query.filter_by(
        requisicao_id=requisicao.id).all() if hasattr(
            PedidoCompra, 'requisicao_id') else []

    return render_template(
        'compras/requisicao_detalhe.html',
        requisicao=requisicao,
        itens=requisicao.itens.all(),
        transicoes=requisicao.transicoes.all(),
        faixa=faixa,
        pendencias=pendencias_de_aprovacao(requisicao),
        pode_aprovar=pode,
        motivo_recusa=motivo_recusa,
        pode_emitir=pode_comprar_na_obra(requisicao.obra_id),
        pedidos=pedidos,
        EstadoRequisicao=EstadoRequisicao,
    )


@compras_bp.route('/requisicoes/<int:requisicao_id>/enviar', methods=['POST'])
@login_required
def requisicao_enviar(requisicao_id):
    """RASCUNHO → AGUARDANDO_APROVACAO."""
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Requisição sem item aprovada é assinatura em branco.
    if requisicao.itens.count() == 0:
        flash('Requisição sem itens não vai para aprovação.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    recalcular_valor(requisicao)
    try:
        transicionar(requisicao, EstadoRequisicao.AGUARDANDO_APROVACAO,
                     current_user,
                     motivo=(request.form.get('motivo') or '').strip() or None)
        db.session.commit()
        flash(f'Requisição {requisicao.numero} enviada para aprovação.', 'success')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/cancelar', methods=['POST'])
@login_required
def requisicao_cancelar(requisicao_id):
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        transicionar(requisicao, EstadoRequisicao.CANCELADA, current_user,
                     motivo=(request.form.get('motivo') or '').strip() or None)
        db.session.commit()
        flash(f'Requisição {requisicao.numero} cancelada.', 'info')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/aprovar', methods=['POST'])
@login_required
def requisicao_aprovar(requisicao_id):
    """Registra UM voto de aprovação; move para APROVADA quando a alçada fecha.

    Um voto não é uma transição de estado: a faixa pode exigir dois. Por
    isso `registrar_aprovacao` grava a RequisicaoTransicao com
    `para_estado == estado atual` (voto) e só depois, se
    `esta_totalmente_aprovada`, é que `transicionar` roda de verdade.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    permitido, motivo = pode_aprovar(requisicao, current_user)
    if not permitido:
        flash(motivo, 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    observacao = (request.form.get('observacao') or '').strip() or None

    try:
        registrar_aprovacao(requisicao, current_user, observacao=observacao)

        if esta_totalmente_aprovada(requisicao):
            transicionar(requisicao, EstadoRequisicao.APROVADA, current_user,
                         motivo='alçada atendida')
            db.session.commit()
            flash(f'Requisição {requisicao.numero} APROVADA. Já pode virar '
                  f'pedido de compra.', 'success')
        else:
            db.session.commit()
            faltando = '; '.join(pendencias_de_aprovacao(requisicao))
            flash(f'Sua aprovação foi registrada. Ainda falta: {faltando}.',
                  'info')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error('[fase3] falha ao aprovar requisicao %s: %s',
                     requisicao_id, e, exc_info=True)
        flash('Não foi possível registrar a aprovação. Tente novamente.',
              'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/rejeitar', methods=['POST'])
@login_required
def requisicao_rejeitar(requisicao_id):
    """AGUARDANDO_APROVACAO → REJEITADA. Motivo obrigatório.

    Rejeitar sem motivo é a forma mais rápida de tornar a trilha inútil:
    seis meses depois ninguém sabe se a compra foi barrada por preço, por
    prazo ou por especificação errada.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    permitido, motivo_recusa = pode_aprovar(requisicao, current_user)
    if not permitido:
        flash(motivo_recusa, 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash('Informe o motivo da rejeição — sem ele o histórico não '
              'serve para nada.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        transicionar(requisicao, EstadoRequisicao.REJEITADA, current_user,
                     motivo=motivo[:2000])
        db.session.commit()
        flash(f'Requisição {requisicao.numero} rejeitada. O solicitante pode '
              f'corrigir e reenviar.', 'warning')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))
