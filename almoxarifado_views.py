# ===== MÓDULO 4: VIEWS DO ALMOXARIFADO INTELIGENTE =====

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from auth import almoxarife_required, pode_gerenciar_almoxarifado, get_tenant_filter
from models import (Produto, CategoriaProduto, Fornecedor, NotaFiscal, MovimentacaoEstoque, RDO, Obra, db)
from almoxarifado_utils import (
    atualizar_estoque_produto, calcular_estoque_minimo_inteligente,
    prever_ruptura_estoque, gerar_relatorio_estoque, calcular_kpis_almoxarifado,
    obter_materiais_rdo, lancar_material_rdo
)
from codigo_barras_utils import (
    gerar_codigo_interno, validar_codigo_barras, buscar_produto_por_codigo,
    sugerir_produtos_similares, gerar_qr_code_produto
)
from xml_nfe_processor import ProcessadorXMLNFe, validar_xml_nfe_rapido, extrair_resumo_xml

almoxarifado_bp = Blueprint('almoxarifado', __name__, url_prefix='/almoxarifado')

@almoxarifado_bp.route('/')
@login_required
@almoxarife_required
def dashboard():
    """Dashboard principal do almoxarifado"""
    admin_id = get_tenant_filter()
    
    # Calcular KPIs
    kpis = calcular_kpis_almoxarifado(admin_id)
    
    # Produtos com estoque crítico
    produtos_criticos = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.ativo == True,
        Produto.estoque_atual <= (Produto.estoque_minimo * 0.5)
    ).limit(10).all()
    
    # Últimas movimentações
    ultimas_movimentacoes = MovimentacaoEstoque.query.filter_by(
        admin_id=admin_id
    ).order_by(MovimentacaoEstoque.data_movimentacao.desc()).limit(10).all()
    
    # Notas fiscais pendentes
    nfs_pendentes = NotaFiscal.query.filter_by(
        admin_id=admin_id,
        status='Pendente'
    ).order_by(NotaFiscal.data_emissao.desc()).limit(5).all()
    
    return render_template('almoxarifado/dashboard.html',
                         kpis=kpis,
                         produtos_criticos=produtos_criticos,
                         ultimas_movimentacoes=ultimas_movimentacoes,
                         nfs_pendentes=nfs_pendentes,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/produtos')
@login_required
@almoxarife_required
def listar_produtos():
    """Listar produtos do almoxarifado"""
    admin_id = get_tenant_filter()
    
    # Filtros
    categoria_id = request.args.get('categoria_id', type=int)
    status_estoque = request.args.get('status_estoque')
    busca = request.args.get('busca', '').strip()
    
    # Query base
    query = Produto.query.filter_by(admin_id=admin_id, ativo=True)
    
    # Aplicar filtros
    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)
    
    if status_estoque:
        if status_estoque == 'BAIXO':
            query = query.filter(Produto.estoque_atual <= Produto.estoque_minimo)
        elif status_estoque == 'CRITICO':
            query = query.filter(Produto.estoque_atual <= (Produto.estoque_minimo * 0.5))
        elif status_estoque == 'ZERADO':
            query = query.filter(Produto.estoque_atual <= 0)
    
    if busca:
        query = query.filter(db.or_(
            Produto.nome.ilike(f'%{busca}%'),
            Produto.codigo_interno.ilike(f'%{busca}%'),
            Produto.codigo_barras.ilike(f'%{busca}%')
        ))
    
    produtos = query.order_by(Produto.nome).all()
    
    # Buscar categorias para filtro
    categorias = CategoriaProduto.query.filter_by(admin_id=admin_id).order_by(CategoriaProduto.nome).all()
    
    return render_template('almoxarifado/produtos.html',
                         produtos=produtos,
                         categorias=categorias,
                         categoria_id=categoria_id,
                         status_estoque=status_estoque,
                         busca=busca,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
@almoxarife_required
def novo_produto():
    """Criar novo produto"""
    admin_id = get_tenant_filter()
    
    if request.method == 'POST':
        try:
            # Validar categoria
            categoria_id = request.form.get('categoria_id', type=int)
            categoria = CategoriaProduto.query.filter_by(id=categoria_id, admin_id=admin_id).first()
            if not categoria:
                flash('Categoria inválida', 'danger')
                return redirect(url_for('almoxarifado.novo_produto'))
            
            # Gerar código interno
            codigo_interno = gerar_codigo_interno(admin_id, categoria.codigo)
            
            produto = Produto(
                codigo_interno=codigo_interno,
                codigo_barras=request.form.get('codigo_barras', '').strip() or None,
                nome=request.form['nome'].strip(),
                descricao=request.form.get('descricao', '').strip(),
                categoria_id=categoria_id,
                unidade_medida=request.form['unidade_medida'],
                peso_unitario=request.form.get('peso_unitario', type=float),
                dimensoes=request.form.get('dimensoes', '').strip() or None,
                estoque_minimo=request.form.get('estoque_minimo', 0, type=float),
                estoque_maximo=request.form.get('estoque_maximo', type=float),
                ultimo_valor_compra=request.form.get('ultimo_valor_compra', type=float),
                critico=bool(request.form.get('critico')),
                admin_id=admin_id
            )
            
            # Definir valor médio se informado
            if produto.ultimo_valor_compra:
                produto.valor_medio = produto.ultimo_valor_compra
            
            db.session.add(produto)
            db.session.commit()
            
            flash(f'Produto {produto.nome} criado com sucesso! Código: {codigo_interno}', 'success')
            return redirect(url_for('almoxarifado.ver_produto', id=produto.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar produto: {str(e)}', 'danger')
    
    # Buscar categorias
    categorias = CategoriaProduto.query.filter_by(admin_id=admin_id).order_by(CategoriaProduto.nome).all()
    
    return render_template('almoxarifado/produto_form.html',
                         categorias=categorias,
                         produto=None)

@almoxarifado_bp.route('/produtos/<int:id>')
@login_required
@almoxarife_required
def ver_produto(id):
    """Ver detalhes do produto"""
    admin_id = get_tenant_filter()
    produto = Produto.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    # Últimas movimentações
    movimentacoes = MovimentacaoEstoque.query.filter_by(
        produto_id=id
    ).order_by(MovimentacaoEstoque.data_movimentacao.desc()).limit(20).all()
    
    # Previsão de ruptura
    previsao_ruptura = prever_ruptura_estoque(id)
    
    # Estoque mínimo sugerido pela IA
    estoque_minimo_ia = calcular_estoque_minimo_inteligente(id)
    
    return render_template('almoxarifado/produto_detalhes.html',
                         produto=produto,
                         movimentacoes=movimentacoes,
                         previsao_ruptura=previsao_ruptura,
                         estoque_minimo_ia=estoque_minimo_ia,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/movimentacoes')
@login_required
@almoxarife_required
def listar_movimentacoes():
    """Listar movimentações de estoque"""
    admin_id = get_tenant_filter()
    
    # Filtros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_movimentacao = request.args.get('tipo_movimentacao')
    produto_id = request.args.get('produto_id', type=int)
    obra_id = request.args.get('obra_id', type=int)
    
    # Query base
    query = MovimentacaoEstoque.query.filter_by(admin_id=admin_id)
    
    # Aplicar filtros
    if data_inicio:
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            query = query.filter(MovimentacaoEstoque.data_movimentacao >= data_inicio)
        except:
            pass
    
    if data_fim:
        try:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            query = query.filter(MovimentacaoEstoque.data_movimentacao <= data_fim)
        except:
            pass
    
    if tipo_movimentacao:
        query = query.filter_by(tipo_movimentacao=tipo_movimentacao)
    
    if produto_id:
        query = query.filter_by(produto_id=produto_id)
    
    if obra_id:
        query = query.filter_by(obra_id=obra_id)
    
    movimentacoes = query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).limit(100).all()
    
    # Dados para filtros
    produtos = Produto.query.filter_by(admin_id=admin_id, ativo=True).order_by(Produto.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    
    return render_template('almoxarifado/movimentacoes.html',
                         movimentacoes=movimentacoes,
                         produtos=produtos,
                         obras=obras,
                         filtros={
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'tipo_movimentacao': tipo_movimentacao,
                             'produto_id': produto_id,
                             'obra_id': obra_id
                         })

@almoxarifado_bp.route('/movimentar', methods=['POST'])
@login_required
@almoxarife_required
def movimentar_estoque():
    """Criar movimentação manual de estoque"""
    try:
        admin_id = get_tenant_filter()
        
        produto_id = request.form.get('produto_id', type=int)
        tipo_movimentacao = request.form.get('tipo_movimentacao')
        quantidade = request.form.get('quantidade', type=float)
        valor_unitario = request.form.get('valor_unitario', type=float)
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validações
        if not all([produto_id, tipo_movimentacao, quantidade]):
            flash('Todos os campos obrigatórios devem ser preenchidos', 'danger')
            return redirect(request.referrer)
        
        if quantidade <= 0:
            flash('Quantidade deve ser maior que zero', 'danger')
            return redirect(request.referrer)
        
        # Verificar se produto pertence ao admin
        produto = Produto.query.filter_by(id=produto_id, admin_id=admin_id).first()
        if not produto:
            flash('Produto não encontrado', 'danger')
            return redirect(request.referrer)
        
        # Criar movimentação
        movimentacao = atualizar_estoque_produto(
            produto_id=produto_id,
            quantidade=quantidade,
            tipo_movimentacao=tipo_movimentacao,
            valor_unitario=valor_unitario,
            usuario_id=current_user.id,
            observacoes=observacoes,
            ip_address=request.remote_addr
        )
        
        flash(f'Movimentação registrada com sucesso! {tipo_movimentacao} de {quantidade} {produto.unidade_medida}', 'success')
        
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Erro ao registrar movimentação: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('almoxarifado.dashboard'))

@almoxarifado_bp.route('/categorias')
@login_required
@almoxarife_required
def listar_categorias():
    """Listar categorias de produtos"""
    admin_id = get_tenant_filter()
    categorias = CategoriaProduto.query.filter_by(admin_id=admin_id).order_by(CategoriaProduto.nome).all()
    
    return render_template('almoxarifado/categorias.html',
                         categorias=categorias,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/categorias/nova', methods=['POST'])
@login_required
@almoxarife_required
def nova_categoria():
    """Criar nova categoria"""
    try:
        admin_id = get_tenant_filter()
        
        categoria = CategoriaProduto(
            nome=request.form['nome'].strip(),
            descricao=request.form.get('descricao', '').strip(),
            codigo=request.form['codigo'].strip().upper(),
            cor_hex=request.form.get('cor_hex', '#007bff'),
            admin_id=admin_id
        )
        
        db.session.add(categoria)
        db.session.commit()
        
        flash(f'Categoria {categoria.nome} criada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar categoria: {str(e)}', 'danger')
    
    return redirect(url_for('almoxarifado.listar_categorias'))

@almoxarifado_bp.route('/fornecedores')
@login_required
@almoxarife_required
def listar_fornecedores():
    """Listar fornecedores"""
    admin_id = get_tenant_filter()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by(Fornecedor.razao_social).all()
    
    return render_template('almoxarifado/fornecedores.html',
                         fornecedores=fornecedores,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/notas-fiscais')
@login_required
@almoxarife_required
def listar_notas_fiscais():
    """Listar notas fiscais"""
    admin_id = get_tenant_filter()
    
    status = request.args.get('status', 'Pendente')
    notas_fiscais = NotaFiscal.query.filter_by(
        admin_id=admin_id,
        status=status
    ).order_by(NotaFiscal.data_emissao.desc()).all()
    
    return render_template('almoxarifado/notas_fiscais.html',
                         notas_fiscais=notas_fiscais,
                         status_atual=status,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/rdo/<int:rdo_id>/materiais')
@login_required
@almoxarife_required
def materiais_rdo(rdo_id):
    """Ver materiais lançados em um RDO"""
    admin_id = get_tenant_filter()
    
    # Verificar se RDO pertence ao admin
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first_or_404()
    
    materiais = obter_materiais_rdo(rdo_id)
    
    # Produtos disponíveis para lançamento
    produtos = Produto.query.filter_by(admin_id=admin_id, ativo=True).order_by(Produto.nome).all()
    
    return render_template('almoxarifado/materiais_rdo.html',
                         rdo=rdo,
                         materiais=materiais,
                         produtos=produtos,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/rdo/<int:rdo_id>/lancar-material', methods=['POST'])
@login_required
@almoxarife_required
def lancar_material_rdo_view(rdo_id):
    """Lançar material em RDO"""
    try:
        produto_id = request.form.get('produto_id', type=int)
        quantidade = request.form.get('quantidade', type=float)
        observacoes = request.form.get('observacoes', '').strip()
        
        if not all([produto_id, quantidade]) or quantidade <= 0:
            flash('Produto e quantidade são obrigatórios', 'danger')
            return redirect(url_for('almoxarifado.materiais_rdo', rdo_id=rdo_id))
        
        movimentacao = lancar_material_rdo(
            rdo_id=rdo_id,
            produto_id=produto_id,
            quantidade=quantidade,
            usuario_id=current_user.id,
            observacoes=observacoes
        )
        
        flash('Material lançado no RDO com sucesso!', 'success')
        
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Erro ao lançar material: {str(e)}', 'danger')
    
    return redirect(url_for('almoxarifado.materiais_rdo', rdo_id=rdo_id))

@almoxarifado_bp.route('/relatorios')
@login_required
@almoxarife_required
def relatorios():
    """Página de relatórios do almoxarifado"""
    admin_id = get_tenant_filter()
    
    # Gerar relatório básico de estoque
    relatorio_estoque = gerar_relatorio_estoque(admin_id)
    
    return render_template('almoxarifado/relatorios.html',
                         relatorio_estoque=relatorio_estoque)

# ===== APIs REST PARA INTEGRAÇÃO =====

@almoxarifado_bp.route('/api/produtos', methods=['GET'])
@login_required
@almoxarife_required
def api_produtos():
    """API para buscar produtos"""
    admin_id = get_tenant_filter()
    busca = request.args.get('q', '').strip()
    
    query = Produto.query.filter_by(admin_id=admin_id, ativo=True)
    
    if busca:
        query = query.filter(db.or_(
            Produto.nome.ilike(f'%{busca}%'),
            Produto.codigo_interno.ilike(f'%{busca}%'),
            Produto.codigo_barras.ilike(f'%{busca}%')
        ))
    
    produtos = query.order_by(Produto.nome).limit(20).all()
    
    return jsonify([{
        'id': p.id,
        'codigo_interno': p.codigo_interno,
        'nome': p.nome,
        'unidade_medida': p.unidade_medida,
        'estoque_atual': float(p.estoque_atual),
        'status_estoque': p.status_estoque
    } for p in produtos])

@almoxarifado_bp.route('/api/produto/<int:id>/estoque')
@login_required
@almoxarife_required
def api_estoque_produto(id):
    """API para verificar estoque de um produto"""
    admin_id = get_tenant_filter()
    produto = Produto.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    return jsonify({
        'id': produto.id,
        'nome': produto.nome,
        'estoque_atual': float(produto.estoque_atual),
        'estoque_minimo': float(produto.estoque_minimo),
        'status_estoque': produto.status_estoque,
        'valor_medio': float(produto.valor_medio),
        'unidade_medida': produto.unidade_medida
    })

# ===== APIS AVANÇADAS BASEADAS NA REUNIÃO TÉCNICA =====

@almoxarifado_bp.route('/scanner')
@login_required
@almoxarife_required
def scanner_codigo_barras():
    """Interface de scanner de código de barras mobile-first"""
    admin_id = get_tenant_filter()
    
    # Últimos códigos escaneados (simulado por enquanto)
    codigos_recentes = []
    
    # Produtos com estoque baixo
    produtos_baixo = Produto.query.filter(
        Produto.admin_id == admin_id,
        Produto.ativo == True,
        Produto.estoque_atual <= Produto.estoque_minimo
    ).limit(5).all()
    
    return render_template('almoxarifado/scanner.html',
                         codigos_recentes=codigos_recentes,
                         produtos_baixo=produtos_baixo,
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/api/buscar-codigo', methods=['POST'])
@login_required
@almoxarife_required
def api_buscar_codigo():
    """API para buscar produto por código de barras"""
    admin_id = get_tenant_filter()
    data = request.get_json()
    
    codigo = data.get('codigo', '').strip()
    if not codigo:
        return jsonify({'erro': 'Código não fornecido'}), 400
    
    # Validar código
    validacao = validar_codigo_barras(codigo)
    if not validacao['valido']:
        return jsonify({'erro': validacao['erro']}), 400
    
    # Buscar produto
    resultado = buscar_produto_por_codigo(codigo, admin_id)
    
    if resultado['encontrado']:
        produto = resultado['produto']
        return jsonify({
            'encontrado': True,
            'produto': {
                'id': produto.id,
                'nome': produto.nome,
                'codigo_interno': produto.codigo_interno,
                'estoque_atual': float(produto.estoque_atual),
                'estoque_minimo': float(produto.estoque_minimo),
                'status_estoque': produto.status_estoque,
                'unidade_medida': produto.unidade_medida,
                'valor_medio': float(produto.valor_medio),
                'categoria': produto.categoria.nome if produto.categoria else None
            },
            'tipo_busca': resultado['tipo_busca']
        })
    
    # Se não encontrou, retornar sugestões
    sugestoes = []
    if resultado.get('sugestoes'):
        for sugestao in resultado['sugestoes']:
            sugestoes.append({
                'id': sugestao.id,
                'nome': sugestao.nome,
                'codigo_interno': sugestao.codigo_interno,
                'estoque_atual': float(sugestao.estoque_atual)
            })
    
    return jsonify({
        'encontrado': False,
        'codigo_buscado': codigo,
        'sugestoes': sugestoes
    })

@almoxarifado_bp.route('/api/gerar-qr/<int:produto_id>')
@login_required
@almoxarife_required
def api_gerar_qr_code(produto_id):
    """API para gerar QR Code de produto"""
    admin_id = get_tenant_filter()
    produto = Produto.query.filter_by(id=produto_id, admin_id=admin_id).first_or_404()
    
    qr_code_base64 = gerar_qr_code_produto(produto_id)
    
    return jsonify({
        'qr_code': qr_code_base64,
        'produto_nome': produto.nome,
        'codigo_interno': produto.codigo_interno
    })

@almoxarifado_bp.route('/importar-xml')
@login_required
@almoxarife_required
def importar_xml():
    """Página de importação de XML NFe"""
    return render_template('almoxarifado/importar_xml.html',
                         pode_gerenciar=pode_gerenciar_almoxarifado())

@almoxarifado_bp.route('/api/upload-xml', methods=['POST'])
@login_required
@almoxarife_required
def api_upload_xml():
    """API para upload e processamento de XML NFe"""
    admin_id = get_tenant_filter()
    
    if 'arquivo_xml' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    
    arquivo = request.files['arquivo_xml']
    if arquivo.filename == '':
        return jsonify({'erro': 'Nenhum arquivo selecionado'}), 400
    
    if not arquivo.filename.lower().endswith('.xml'):
        return jsonify({'erro': 'Arquivo deve ser XML'}), 400
    
    try:
        # Ler conteúdo do arquivo
        xml_content = arquivo.read().decode('utf-8')
        
        # Validação rápida
        validacao = validar_xml_nfe_rapido(xml_content)
        if not validacao['valido']:
            return jsonify({'erro': validacao['erro']}), 400
        
        # Extrair resumo para pré-visualização
        resumo = extrair_resumo_xml(xml_content)
        if not resumo['valido']:
            return jsonify({'erro': resumo['erro']}), 400
        
        # Processar XML completo
        processador = ProcessadorXMLNFe(admin_id)
        resultado = processador.processar_xml(xml_content, current_user.id)
        
        if 'erro' in resultado:
            return jsonify({'erro': resultado['erro']}), 400
        
        return jsonify({
            'sucesso': True,
            'resumo': resultado['resumo'],
            'nota_fiscal_id': resultado['nota_fiscal_id'],
            'produtos_criados': resultado['produtos_criados'],
            'produtos_atualizados': resultado['produtos_atualizados'],
            'valor_total': resultado['valor_total_importado']
        })
        
    except Exception as e:
        return jsonify({'erro': f'Erro ao processar arquivo: {str(e)}'}), 500

@almoxarifado_bp.route('/api/estoque-minimo-ia/<int:produto_id>')
@login_required
@almoxarife_required
def api_estoque_minimo_ia(produto_id):
    """API para calcular estoque mínimo usando IA"""
    admin_id = get_tenant_filter()
    produto = Produto.query.filter_by(id=produto_id, admin_id=admin_id).first_or_404()
    
    # Calcular estoque mínimo inteligente
    estoque_ia = calcular_estoque_minimo_inteligente(produto_id)
    
    # Previsão de ruptura
    previsao = prever_ruptura_estoque(produto_id)
    
    return jsonify({
        'produto_id': produto_id,
        'produto_nome': produto.nome,
        'estoque_atual': float(produto.estoque_atual),
        'estoque_minimo_atual': float(produto.estoque_minimo),
        'estoque_minimo_sugerido': float(estoque_ia),
        'diferenca': float(estoque_ia - produto.estoque_minimo),
        'previsao_ruptura': previsao,
        'recomendacao': 'Ajustar estoque mínimo' if abs(estoque_ia - produto.estoque_minimo) > 5 else 'Manter configuração atual'
    })

@almoxarifado_bp.route('/api/atualizar-estoque-minimo', methods=['POST'])
@login_required
@almoxarife_required
def api_atualizar_estoque_minimo():
    """API para atualizar estoque mínimo"""
    admin_id = get_tenant_filter()
    data = request.get_json()
    
    produto_id = data.get('produto_id')
    novo_estoque_minimo = data.get('estoque_minimo')
    
    if not produto_id or novo_estoque_minimo is None:
        return jsonify({'erro': 'Dados incompletos'}), 400
    
    produto = Produto.query.filter_by(id=produto_id, admin_id=admin_id).first_or_404()
    
    try:
        produto.estoque_minimo = float(novo_estoque_minimo)
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'produto_nome': produto.nome,
            'novo_estoque_minimo': float(produto.estoque_minimo)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

@almoxarifado_bp.route('/movimentacoes-estoque')
@login_required
@almoxarife_required
def listar_movimentacoes_estoque():
    """Listar movimentações de estoque com filtros avançados"""
    admin_id = get_tenant_filter()
    
    # Filtros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_movimentacao = request.args.get('tipo_movimentacao')
    produto_id = request.args.get('produto_id', type=int)
    obra_id = request.args.get('obra_id', type=int)
    funcionario_id = request.args.get('funcionario_id', type=int)
    
    # Query base
    query = MovimentacaoEstoque.query.filter_by(admin_id=admin_id)
    
    # Aplicar filtros
    if data_inicio:
        try:
            data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(MovimentacaoEstoque.data_movimentacao >= data_inicio_dt)
        except:
            flash('Data de início inválida', 'warning')
    
    if data_fim:
        try:
            data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
            # Incluir todo o dia
            data_fim_dt = data_fim_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(MovimentacaoEstoque.data_movimentacao <= data_fim_dt)
        except:
            flash('Data de fim inválida', 'warning')
    
    if tipo_movimentacao:
        query = query.filter_by(tipo_movimentacao=tipo_movimentacao)
    
    if produto_id:
        query = query.filter_by(produto_id=produto_id)
    
    if obra_id:
        query = query.filter_by(obra_id=obra_id)
    
    if funcionario_id:
        query = query.filter_by(funcionario_id=funcionario_id)
    
    # Paginação
    page = request.args.get('page', 1, type=int)
    movimentacoes = query.order_by(
        MovimentacaoEstoque.data_movimentacao.desc()
    ).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Dados para filtros
    produtos = Produto.query.filter_by(admin_id=admin_id, ativo=True).order_by(Produto.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('almoxarifado/movimentacoes.html',
                         movimentacoes=movimentacoes,
                         produtos=produtos,
                         obras=obras,
                         funcionarios=funcionarios,
                         filtros={
                             'data_inicio': data_inicio,
                             'data_fim': data_fim,
                             'tipo_movimentacao': tipo_movimentacao,
                             'produto_id': produto_id,
                             'obra_id': obra_id,
                             'funcionario_id': funcionario_id
                         },
                         pode_gerenciar=pode_gerenciar_almoxarifado())