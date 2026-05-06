"""Endpoints JSON do almoxarifado.

Consumidores conhecidos:
- api_item_info        → templates/almoxarifado/entrada.html (preenchimento dinâmico do formulário)
- api_estoque_disponivel → templates/almoxarifado/saida.html (lista itens/qtd ao selecionar item)
- api_lotes_disponiveis  → templates/almoxarifado/saida.html (seleção manual de lotes FIFO)
- api_itens_funcionario  → templates/almoxarifado/devolucao.html (itens em posse do funcionário)
"""
from flask import jsonify
from flask_login import login_required
from app import db
from models import AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento, Funcionario
from sqlalchemy import func
import logging

from views.almoxarifado import almoxarifado_bp, get_admin_id

logger = logging.getLogger(__name__)


@almoxarifado_bp.route('/api/item/<int:id>')
@login_required
def api_item_info(id):
    """API que retorna info do item (tipo_controle, unidade, estoque_atual)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401

    item = AlmoxarifadoItem.query.filter_by(id=id, admin_id=admin_id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404

    if item.tipo_controle == 'SERIALIZADO':
        estoque_atual = AlmoxarifadoEstoque.query.filter_by(
            item_id=id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).count()
    else:
        estoque_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
            item_id=id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).scalar() or 0

    return jsonify({
        'id': item.id,
        'nome': item.nome,
        'codigo': item.codigo,
        'tipo_controle': item.tipo_controle,
        'unidade': item.unidade,
        'estoque_atual': estoque_atual
    })


@almoxarifado_bp.route('/api/estoque-disponivel/<int:item_id>')
@login_required
def api_estoque_disponivel(item_id):
    """API que retorna estoque disponível (SERIALIZADO: lista de itens, CONSUMIVEL: quantidade total)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401

    item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404

    if item.tipo_controle == 'SERIALIZADO':
        itens_disponiveis = AlmoxarifadoEstoque.query.filter_by(
            item_id=item_id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).all()

        return jsonify({
            'tipo_controle': 'SERIALIZADO',
            'itens': [{
                'id': est.id,
                'numero_serie': est.numero_serie,
                'data_entrada': est.created_at.strftime('%d/%m/%Y')
            } for est in itens_disponiveis]
        })
    else:
        quantidade_total = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
            item_id=item_id,
            status='DISPONIVEL',
            admin_id=admin_id
        ).scalar() or 0

        return jsonify({
            'tipo_controle': 'CONSUMIVEL',
            'quantidade_disponivel': quantidade_total,
            'unidade': item.unidade
        })


@almoxarifado_bp.route('/api/lotes-disponiveis/<int:item_id>')
@login_required
def api_lotes_disponiveis(item_id):
    """Retorna lotes disponíveis de um item ordenados por FIFO (created_at ASC)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401

    item = AlmoxarifadoItem.query.filter_by(id=item_id, admin_id=admin_id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado'}), 404

    lotes = AlmoxarifadoEstoque.query.filter_by(
        item_id=item_id,
        status='DISPONIVEL',
        admin_id=admin_id
    ).order_by(AlmoxarifadoEstoque.created_at.asc()).all()

    lotes_data = []
    for lote in lotes:
        nota_fiscal = None
        if lote.entrada_movimento_id:
            movimento_entrada = AlmoxarifadoMovimento.query.filter_by(
                id=lote.entrada_movimento_id,
                admin_id=admin_id
            ).first()
            if movimento_entrada:
                nota_fiscal = movimento_entrada.nota_fiscal

        qtd_disponivel = float(lote.quantidade_disponivel) if lote.quantidade_disponivel else float(lote.quantidade)

        lotes_data.append({
            'estoque_id': lote.id,
            'lote': lote.lote,
            'numero_serie': lote.numero_serie,
            'quantidade_disponivel': qtd_disponivel,
            'quantidade_inicial': float(lote.quantidade_inicial) if lote.quantidade_inicial else float(lote.quantidade),
            'valor_unitario': float(lote.valor_unitario) if lote.valor_unitario else 0.0,
            'data_entrada': lote.created_at.strftime('%d/%m/%Y %H:%M'),
            'nota_fiscal': nota_fiscal,
            'data_validade': lote.data_validade.strftime('%d/%m/%Y') if lote.data_validade else None
        })

    return jsonify({
        'success': True,
        'item_id': item_id,
        'item_nome': item.nome,
        'tipo_controle': item.tipo_controle,
        'unidade': item.unidade,
        'lotes': lotes_data,
        'total_disponivel': sum(l['quantidade_disponivel'] for l in lotes_data)
    })


@almoxarifado_bp.route('/api/itens-funcionario/<int:funcionario_id>')
@login_required
def api_itens_funcionario(funcionario_id):
    """API que retorna itens em posse do funcionário (SERIALIZADOS + CONSUMÍVEIS retornáveis)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'error': 'Não autenticado'}), 401

    funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
    if not funcionario:
        return jsonify({'error': 'Funcionário não encontrado'}), 404

    from models import AlmoxarifadoItem as _Item
    itens_retornaveis = []

    estoques_serializados = AlmoxarifadoEstoque.query.filter_by(
        funcionario_atual_id=funcionario_id,
        status='EM_USO',
        admin_id=admin_id
    ).join(_Item).filter(
        _Item.tipo_controle == 'SERIALIZADO'
    ).all()

    for est in estoques_serializados:
        itens_retornaveis.append({
            'estoque_id': est.id,
            'item_id': est.item_id,
            'item_nome': est.item.nome,
            'tipo_controle': 'SERIALIZADO',
            'numero_serie': est.numero_serie,
            'obra': est.obra.nome if est.obra else 'N/A',
            'data_saida': est.updated_at.strftime('%d/%m/%Y') if est.updated_at else 'N/A'
        })

    movimentos_saida = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='SAIDA',
        admin_id=admin_id
    ).join(_Item).filter(
        _Item.tipo_controle == 'CONSUMIVEL'
    ).all()

    consumiveis_dict = {}
    for mov in movimentos_saida:
        if mov.item_id not in consumiveis_dict:
            consumiveis_dict[mov.item_id] = {
                'item': mov.item,
                'quantidade_saida': 0,
                'quantidade_devolvida': 0
            }
        consumiveis_dict[mov.item_id]['quantidade_saida'] += mov.quantidade or 0

    movimentos_devolucao = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='DEVOLUCAO',
        admin_id=admin_id
    ).all()

    for mov in movimentos_devolucao:
        if mov.item_id in consumiveis_dict:
            consumiveis_dict[mov.item_id]['quantidade_devolvida'] += mov.quantidade or 0

    movimentos_consumido = AlmoxarifadoMovimento.query.filter_by(
        funcionario_id=funcionario_id,
        tipo_movimento='CONSUMIDO',
        admin_id=admin_id
    ).all()

    for mov in movimentos_consumido:
        if mov.item_id not in consumiveis_dict:
            consumiveis_dict[mov.item_id] = {
                'item': mov.item,
                'quantidade_saida': 0,
                'quantidade_devolvida': 0
            }
        if 'quantidade_consumida' not in consumiveis_dict[mov.item_id]:
            consumiveis_dict[mov.item_id]['quantidade_consumida'] = 0
        consumiveis_dict[mov.item_id]['quantidade_consumida'] += mov.quantidade or 0

    for item_id, dados in consumiveis_dict.items():
        quantidade_consumida = dados.get('quantidade_consumida', 0)
        qtd_disponivel = dados['quantidade_saida'] - dados['quantidade_devolvida'] - quantidade_consumida
        if qtd_disponivel > 0:
            itens_retornaveis.append({
                'item_id': item_id,
                'item_nome': dados['item'].nome,
                'tipo_controle': 'CONSUMIVEL',
                'quantidade_disponivel': qtd_disponivel,
                'unidade': dados['item'].unidade,
                'permite_devolucao': dados['item'].permite_devolucao
            })

    return jsonify({'itens': itens_retornaveis})
