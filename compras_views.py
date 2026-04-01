import logging
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from models import (AlmoxarifadoItem, CentroCusto, ContaPagar, CustoObra,
                    Fornecedor, Funcionario, Obra, PedidoCompra, PedidoCompraItem)
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
    centros_custo = CentroCusto.query.filter_by(admin_id=admin_id).order_by('nome').all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    itens_catalogo = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by('nome').all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    funcionarios_json = [{'id': f.id, 'nome': f.nome} for f in funcionarios]

    return render_template(
        'compras/nova_compra.html',
        fornecedores=fornecedores,
        centros_custo=centros_custo,
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
        fornecedor_id = int(request.form.get('fornecedor_id'))
        centro_custo_id = int(request.form.get('centro_custo_id'))
        data_compra = datetime.strptime(request.form.get('data_compra'), '%Y-%m-%d').date()
        condicao = request.form.get('condicao_pagamento', 'a_vista')
        parcelas = int(request.form.get('parcelas', 1))
        numero = request.form.get('numero', '').strip() or None
        observacoes = request.form.get('observacoes', '').strip() or None
        obra_id = request.form.get('obra_id') or None
        if obra_id:
            obra_id = int(obra_id)

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
        pedido = PedidoCompra(
            numero=numero,
            fornecedor_id=fornecedor_id,
            data_compra=data_compra,
            centro_custo_id=centro_custo_id,
            obra_id=obra_id,
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=observacoes,
            anexo_url=anexo_url,
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

        # --- Apropriação de custo na obra ---
        if obra_id:
            fornecedor = Fornecedor.query.get(fornecedor_id)
            desc_custo = f"Compra{(' NF ' + numero) if numero else ''} - {fornecedor.nome if fornecedor else 'Fornecedor'}"
            if observacoes:
                desc_custo += f" - {observacoes[:80]}"

            custo = CustoObra(
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                tipo='material',
                descricao=desc_custo[:200],
                valor=float(valor_total),
                data=data_compra,
                admin_id=admin_id,
                categoria='compra',
            )
            db.session.add(custo)
            logger.info(f"[OK] CustoObra criado para obra_id={obra_id} via compra")

        # --- Contas a Pagar ---
        fornecedor = Fornecedor.query.get(fornecedor_id)
        vencimentos = _vencimentos(data_compra, condicao, parcelas)
        n_parcelas = len(vencimentos)
        valor_parcela = round(valor_total / n_parcelas, 2)

        for idx, (data_venc, _) in enumerate(vencimentos, start=1):
            # Ajusta última parcela para absorver diferença de arredondamento
            v = valor_parcela if idx < n_parcelas else round(valor_total - valor_parcela * (n_parcelas - 1), 2)
            status_cp = 'PAGO' if condicao == 'a_vista' else 'PENDENTE'
            desc_cp = f"Compra{(' NF ' + numero) if numero else ''}"
            if n_parcelas > 1:
                desc_cp += f" - Parcela {idx}/{n_parcelas}"
            desc_cp += f" - {fornecedor.nome if fornecedor else 'Fornecedor'}"

            cp = ContaPagar(
                fornecedor_id=fornecedor_id,
                obra_id=obra_id,
                numero_documento=numero,
                descricao=desc_cp[:500],
                valor_original=v,
                valor_pago=v if condicao == 'a_vista' else 0,
                saldo=0 if condicao == 'a_vista' else v,
                data_emissao=data_compra,
                data_vencimento=data_venc,
                data_pagamento=data_compra if condicao == 'a_vista' else None,
                status=status_cp,
                origem_tipo='COMPRA',
                origem_id=pedido.id,
                admin_id=admin_id,
            )
            db.session.add(cp)

        logger.info(f"[OK] {n_parcelas} ContaPagar criado(s) para pedido_id={pedido.id}")

        db.session.commit()

        # Lançamento contábil automático V2
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

        # Integração automática: Gestão de Custos V2
        try:
            from utils.financeiro_integration import registrar_custo_automatico
            _forn = Fornecedor.query.get(fornecedor_id)
            _forn_nome = _forn.nome if _forn else 'Fornecedor'
            registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria='COMPRA',
                entidade_nome=_forn_nome,
                entidade_id=fornecedor_id,
                data=data_compra,
                descricao=f"Compra{(' NF ' + numero) if numero else ''} — {_forn_nome}",
                valor=float(valor_total),
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                origem_tabela='pedido_compra',
                origem_id=pedido.id,
            )
            from app import db as _db
            _db.session.commit()
            logger.info(f"[OK] GestaoCusto COMPRA registrado para {_forn_nome}")
        except Exception as _e:
            logger.warning(f"[WARN] Gestao custo compra nao registrado: {_e}")

        # Reembolso a Funcionários V2
        try:
            from utils.financeiro_integration import processar_reembolsos_form
            n_reimb = processar_reembolsos_form(
                request_form=request.form,
                admin_id=admin_id,
                data_despesa=data_compra,
                descricao_origem=f"Compra{(' NF ' + numero) if numero else ''}",
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                origem_tabela='pedido_compra',
                origem_id=pedido.id,
            )
            if n_reimb:
                db.session.commit()
                logger.info(f"[OK] {n_reimb} reembolso(s) registrado(s) na compra {pedido.id}")
        except Exception as _re:
            logger.warning(f"[WARN] Reembolso compra nao processado: {_re}")

        flash(f'Compra registrada com sucesso! {n_parcelas} conta(s) a pagar gerada(s).', 'success')
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
    contas = ContaPagar.query.filter_by(origem_tipo='COMPRA', origem_id=pedido_id).all()

    return render_template(
        'compras/detalhe.html',
        pedido=pedido,
        itens=itens,
        contas=contas,
        CONDICOES=CONDICOES,
    )


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
        # Remover ContaPagar vinculados
        ContaPagar.query.filter_by(origem_tipo='COMPRA', origem_id=pedido_id).delete()
        db.session.delete(pedido)
        db.session.commit()
        flash('Compra e contas a pagar vinculadas foram excluídas.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {e}', 'danger')
    return redirect(url_for('compras.index'))
