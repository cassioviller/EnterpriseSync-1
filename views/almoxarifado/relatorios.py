from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from app import db
from models import (
    AlmoxarifadoCategoria,
    AlmoxarifadoItem,
    AlmoxarifadoEstoque,
    AlmoxarifadoMovimento,
    Funcionario,
    Obra,
)
from . import almoxarifado_bp, get_admin_id


@almoxarifado_bp.route('/relatorios')
@login_required
def relatorios():
    """Sistema de Relatórios do Almoxarifado - 5 Relatórios Completos"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Identificar qual relatório gerar
    relatorio_tipo = request.args.get('tipo', '')
    
    # Dados para os filtros (multi-tenant)
    categorias = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).order_by(AlmoxarifadoCategoria.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    dados_relatorio = None
    
    # ========================================
    # RELATÓRIO 1: POSIÇÃO DE ESTOQUE
    # ========================================
    if relatorio_tipo == 'posicao_estoque':
        categoria_id = request.args.get('categoria_id', type=int)
        tipo_controle = request.args.get('tipo_controle', '')
        condicao = request.args.get('condicao', '')
        
        # Query base com multi-tenant
        query = AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, ativo=True)
        query = query.join(AlmoxarifadoItem, AlmoxarifadoEstoque.item_id == AlmoxarifadoItem.id)
        query = query.join(AlmoxarifadoCategoria, AlmoxarifadoItem.categoria_id == AlmoxarifadoCategoria.id)
        
        # Filtros
        if categoria_id:
            query = query.filter(AlmoxarifadoItem.categoria_id == categoria_id)
        
        if tipo_controle:
            query = query.filter(AlmoxarifadoItem.tipo_controle == tipo_controle)
        
        if condicao:
            query = query.filter(AlmoxarifadoEstoque.status == condicao)
        
        # Ordenar por categoria e item
        query = query.order_by(AlmoxarifadoCategoria.nome, AlmoxarifadoItem.nome)
        
        itens_estoque = query.all()
        
        # Agrupar por categoria
        estoque_por_categoria = {}
        for estoque in itens_estoque:
            cat_nome = estoque.item.categoria.nome
            if cat_nome not in estoque_por_categoria:
                estoque_por_categoria[cat_nome] = []
            estoque_por_categoria[cat_nome].append(estoque)
        
        # Calcular subtotais
        subtotais = {}
        for cat, itens in estoque_por_categoria.items():
            subtotal = sum([(e.valor_unitario or 0) * (e.quantidade or 0) for e in itens])
            subtotais[cat] = subtotal
        
        total_geral = sum(subtotais.values())
        
        dados_relatorio = {
            'tipo': 'posicao_estoque',
            'estoque_por_categoria': estoque_por_categoria,
            'subtotais': subtotais,
            'total_geral': total_geral,
            'filtros': {
                'categoria_id': categoria_id,
                'tipo_controle': tipo_controle,
                'condicao': condicao
            }
        }
    
    # ========================================
    # RELATÓRIO 2: MOVIMENTAÇÕES POR PERÍODO
    # ========================================
    elif relatorio_tipo == 'movimentacoes':
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        tipo_movimento = request.args.get('tipo_movimento', '')
        funcionario_id = request.args.get('funcionario_id', type=int)
        obra_id = request.args.get('obra_id', type=int)
        
        # Query base com multi-tenant
        query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id)
        query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
        query = query.outerjoin(Funcionario, and_(
            AlmoxarifadoMovimento.funcionario_id == Funcionario.id,
            Funcionario.admin_id == admin_id
        ))
        query = query.outerjoin(Obra, and_(
            AlmoxarifadoMovimento.obra_id == Obra.id,
            Obra.admin_id == admin_id
        ))
        
        # Filtros de data (obrigatório)
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(AlmoxarifadoMovimento.data_movimento >= data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_obj = data_fim_obj + timedelta(days=1)
                query = query.filter(AlmoxarifadoMovimento.data_movimento < data_fim_obj)
            except ValueError:
                pass
        
        if tipo_movimento:
            query = query.filter(AlmoxarifadoMovimento.tipo_movimento == tipo_movimento)
        
        if funcionario_id:
            query = query.filter(AlmoxarifadoMovimento.funcionario_id == funcionario_id)
        
        if obra_id:
            query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)
        
        query = query.order_by(AlmoxarifadoMovimento.data_movimento.desc())
        
        movimentos = query.all()
        
        # Agrupar por tipo
        movimentos_por_tipo = {
            'ENTRADA': [],
            'SAIDA': [],
            'DEVOLUCAO': []
        }
        
        for mov in movimentos:
            if mov.tipo_movimento in movimentos_por_tipo:
                movimentos_por_tipo[mov.tipo_movimento].append(mov)
        
        # Calcular subtotais por tipo
        subtotais_tipo = {}
        for tipo, movs in movimentos_por_tipo.items():
            subtotal = sum([(m.quantidade or 0) for m in movs])
            subtotais_tipo[tipo] = subtotal
        
        dados_relatorio = {
            'tipo': 'movimentacoes',
            'movimentos_por_tipo': movimentos_por_tipo,
            'subtotais_tipo': subtotais_tipo,
            'filtros': {
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'tipo_movimento': tipo_movimento,
                'funcionario_id': funcionario_id,
                'obra_id': obra_id
            }
        }
    
    # ========================================
    # RELATÓRIO 3: ITENS POR FUNCIONÁRIO
    # ========================================
    elif relatorio_tipo == 'itens_funcionario':
        funcionario_id = request.args.get('funcionario_id', type=int)
        obra_id = request.args.get('obra_id', type=int)
        
        # Query base: Itens EM_USO com multi-tenant
        query = AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, status='EM_USO')
        query = query.join(AlmoxarifadoItem, AlmoxarifadoEstoque.item_id == AlmoxarifadoItem.id)
        query = query.join(Funcionario, and_(
            AlmoxarifadoEstoque.funcionario_atual_id == Funcionario.id,
            Funcionario.admin_id == admin_id
        ))
        query = query.outerjoin(Obra, and_(
            AlmoxarifadoEstoque.obra_id == Obra.id,
            Obra.admin_id == admin_id
        ))
        
        # Filtros
        if funcionario_id:
            query = query.filter(AlmoxarifadoEstoque.funcionario_atual_id == funcionario_id)
        
        if obra_id:
            query = query.filter(AlmoxarifadoEstoque.obra_id == obra_id)
        
        query = query.order_by(Funcionario.nome, AlmoxarifadoEstoque.updated_at.desc())
        
        itens_funcionario = query.all()
        
        # Agrupar por funcionário
        itens_por_funcionario = {}
        for estoque in itens_funcionario:
            func_nome = estoque.funcionario_atual.nome if estoque.funcionario_atual else 'Sem Funcionário'
            if func_nome not in itens_por_funcionario:
                itens_por_funcionario[func_nome] = []
            itens_por_funcionario[func_nome].append(estoque)
        
        # Calcular subtotais
        subtotais_func = {}
        for func, itens in itens_por_funcionario.items():
            subtotal = sum([(e.valor_unitario or 0) * (e.quantidade or 0) for e in itens])
            subtotais_func[func] = subtotal
        
        total_geral = sum(subtotais_func.values())
        
        dados_relatorio = {
            'tipo': 'itens_funcionario',
            'itens_por_funcionario': itens_por_funcionario,
            'subtotais_func': subtotais_func,
            'total_geral': total_geral,
            'filtros': {
                'funcionario_id': funcionario_id,
                'obra_id': obra_id
            }
        }
    
    # ========================================
    # RELATÓRIO 4: CONSUMO POR OBRA
    # ========================================
    elif relatorio_tipo == 'consumo_obra':
        obra_id = request.args.get('obra_id', type=int)
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        
        # Query: SAIDA não devolvida (CONSUMIVEL ou SERIALIZADO sem DEVOLUCAO)
        query = AlmoxarifadoMovimento.query.filter_by(admin_id=admin_id, tipo_movimento='SAIDA')
        query = query.join(AlmoxarifadoItem, AlmoxarifadoMovimento.item_id == AlmoxarifadoItem.id)
        query = query.join(Obra, and_(
            AlmoxarifadoMovimento.obra_id == Obra.id,
            Obra.admin_id == admin_id
        ))
        
        # Filtros
        if obra_id:
            query = query.filter(AlmoxarifadoMovimento.obra_id == obra_id)
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(AlmoxarifadoMovimento.data_movimento >= data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_obj = data_fim_obj + timedelta(days=1)
                query = query.filter(AlmoxarifadoMovimento.data_movimento < data_fim_obj)
            except ValueError:
                pass
        
        query = query.order_by(Obra.nome, AlmoxarifadoMovimento.data_movimento.desc())
        
        saidas = query.all()
        
        # Agrupar por obra
        consumo_por_obra = {}
        for saida in saidas:
            obra_nome = saida.obra.nome if saida.obra else 'Sem Obra'
            if obra_nome not in consumo_por_obra:
                consumo_por_obra[obra_nome] = []
            consumo_por_obra[obra_nome].append(saida)
        
        # Calcular subtotais
        subtotais_obra = {}
        for obra, saidas_obra in consumo_por_obra.items():
            subtotal = sum([(s.valor_unitario or 0) * (s.quantidade or 0) for s in saidas_obra])
            subtotais_obra[obra] = subtotal
        
        total_geral = sum(subtotais_obra.values())
        
        dados_relatorio = {
            'tipo': 'consumo_obra',
            'consumo_por_obra': consumo_por_obra,
            'subtotais_obra': subtotais_obra,
            'total_geral': total_geral,
            'filtros': {
                'obra_id': obra_id,
                'data_inicio': data_inicio,
                'data_fim': data_fim
            }
        }
    
    # ========================================
    # RELATÓRIO 5: ALERTAS E PENDÊNCIAS
    # ========================================
    elif relatorio_tipo == 'alertas':
        # 1. Estoque Baixo
        itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).all()
        estoque_baixo = []
        
        for item in itens:
            if item.tipo_controle == 'SERIALIZADO':
                qtd_atual = AlmoxarifadoEstoque.query.filter_by(
                    item_id=item.id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).count()
            else:
                qtd_atual = db.session.query(func.sum(AlmoxarifadoEstoque.quantidade)).filter_by(
                    item_id=item.id,
                    status='DISPONIVEL',
                    admin_id=admin_id
                ).scalar() or 0
            
            if qtd_atual < item.estoque_minimo:
                estoque_baixo.append({
                    'item': item,
                    'qtd_atual': qtd_atual,
                    'qtd_minima': item.estoque_minimo,
                    'diferenca': item.estoque_minimo - qtd_atual
                })
        
        # 2. Manutenção Pendente
        manutencao = AlmoxarifadoEstoque.query.filter_by(
            admin_id=admin_id,
            status='EM_MANUTENCAO'
        ).join(AlmoxarifadoItem).all()
        
        # 3. Itens não devolvidos há >30 dias
        data_limite = datetime.now() - timedelta(days=30)
        
        nao_devolvidos = AlmoxarifadoEstoque.query.filter(
            AlmoxarifadoEstoque.admin_id == admin_id,
            AlmoxarifadoEstoque.status == 'EM_USO',
            AlmoxarifadoEstoque.updated_at <= data_limite
        ).join(AlmoxarifadoItem).outerjoin(Funcionario, and_(
            AlmoxarifadoEstoque.funcionario_atual_id == Funcionario.id,
            Funcionario.admin_id == admin_id
        )).outerjoin(Obra, and_(
            AlmoxarifadoEstoque.obra_id == Obra.id,
            Obra.admin_id == admin_id
        )).all()
        
        # Calcular dias pendentes
        nao_devolvidos_com_dias = []
        for item in nao_devolvidos:
            dias_pendente = (datetime.now() - item.updated_at).days
            nao_devolvidos_com_dias.append({
                'item': item,
                'dias_pendente': dias_pendente
            })
        
        dados_relatorio = {
            'tipo': 'alertas',
            'estoque_baixo': estoque_baixo,
            'manutencao': manutencao,
            'nao_devolvidos': nao_devolvidos_com_dias,
            'filtros': {}
        }
    
    return render_template('almoxarifado/relatorios.html',
                         categorias=categorias,
                         funcionarios=funcionarios,
                         obras=obras,
                         dados_relatorio=dados_relatorio,
                         relatorio_tipo=relatorio_tipo)
