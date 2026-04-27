import logging
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from models import (AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
                    CentroCusto, ContaPagar, CustoObra,
                    Fornecedor, Funcionario, Obra, PedidoCompra, PedidoCompraItem,
                    GestaoCustoPai, GestaoCustoFilho)
from utils.tenant import get_tenant_admin_id, is_v2_active

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
#   - Se condição 'a_vista' → status='PAGO' (e GCP autorizado/pago normalmente via
#     o fluxo padrão da Gestão de Custos, que cria FluxoCaixa quando o usuário paga)
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
    from decimal import Decimal
    fornecedor = Fornecedor.query.get(pedido.fornecedor_id)
    obra = Obra.query.get(pedido.obra_id) if pedido.obra_id else None
    vencimentos = _vencimentos(pedido.data_compra, pedido.condicao_pagamento, pedido.parcelas)
    n_parcelas = len(vencimentos)
    valor_total = float(pedido.valor_total)
    valor_parcela = round(valor_total / n_parcelas, 2)
    forn_nome = fornecedor.nome if fornecedor else 'Fornecedor'
    entidade_nome = obra.nome if obra else 'Sem obra'
    entidade_id = pedido.obra_id

    for idx, (data_venc, _) in enumerate(vencimentos, start=1):
        v = valor_parcela if idx < n_parcelas else round(valor_total - valor_parcela * (n_parcelas - 1), 2)
        is_avista = (pedido.condicao_pagamento == 'a_vista')
        status_gcp = 'PAGO' if is_avista else 'PENDENTE'
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
            valor_pago=v if is_avista else 0,
            saldo=0 if is_avista else v,
            status=status_gcp,
            data_emissao=pedido.data_compra,
            data_vencimento=data_venc,
            data_pagamento=pedido.data_compra if is_avista else None,
            numero_documento=pedido.numero,
            numero_parcela=idx,
            total_parcelas=n_parcelas,
            observacoes=desc_cp[:300],
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
            origem_tabela='pedido_compra',
            origem_id=pedido.id,
        )
        db.session.add(gcf)

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
    from decimal import Decimal
    from datetime import datetime as _dt

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


def _vencimentos(data_compra, condicao, parcelas):
    """Gera lista de (data_vencimento, valor_parcela) para ContaPagar."""
    if not isinstance(data_compra, date):
        data_compra = date.today()

    mapa_dias = {'a_vista': 0, '30d': 30, '60d': 60, '90d': 90, 'cartao': 30}

    if condicao in mapa_dias:
        dias = mapa_dias[condicao]
        return [(data_compra + timedelta(days=dias), None)]  # valor definido depois

    # parcelado → N datas com intervalo de 30 dias
    parcelas = max(1, int(parcelas or 1))
    datas = []
    for i in range(1, parcelas + 1):
        datas.append((data_compra + timedelta(days=30 * i), None))
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

    return render_template(
        'compras/nova_compra.html',
        fornecedores=fornecedores,
        obras=obras,
        itens_catalogo=itens_catalogo,
        funcionarios=funcionarios,
        funcionarios_json=funcionarios_json,
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
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=observacoes,
            anexo_url=anexo_url,
            tipo_compra=tipo_compra,
            processada_apos_aprovacao=False,
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE' if tipo_compra == 'aprovacao_cliente' else None,
            admin_id=admin_id,
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
