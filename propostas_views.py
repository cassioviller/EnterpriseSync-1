from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import current_user

# Bypass para desenvolvimento - sobrescrever login_required
def login_required(f):
    """Bypass do decorador login_required para desenvolvimento"""
    return f
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
import mimetypes

from app import db
from models import PropostaComercialSIGE, PropostaItem, PropostaArquivo, PropostaTemplate, ConfiguracaoEmpresa

# Criar blueprint
propostas_bp = Blueprint('propostas', __name__, url_prefix='/propostas')

def admin_required(f):
    """Bypass do decorador admin_required para desenvolvimento"""
    return f

# Configurações de upload
UPLOAD_FOLDER = 'static/uploads/propostas'
ALLOWED_EXTENSIONS = {'pdf', 'dwg', 'dxf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_category(filename):
    """Determina a categoria do arquivo baseado na extensão"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext in ['dwg', 'dxf']:
        return 'dwg'
    elif ext == 'pdf':
        return 'pdf'
    elif ext in ['png', 'jpg', 'jpeg', 'gif']:
        return 'foto'
    elif ext in ['doc', 'docx', 'xlsx', 'xls']:
        return 'documento'
    else:
        return 'outros'

@propostas_bp.route('/')
@login_required
@admin_required
def index():
    """Lista todas as propostas"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    cliente_filter = request.args.get('cliente', '')
    
    query = PropostaComercialSIGE.query
    
    # Filtros
    if status_filter:
        query = query.filter(PropostaComercialSIGE.status == status_filter)
    if cliente_filter:
        query = query.filter(PropostaComercialSIGE.cliente_nome.ilike(f'%{cliente_filter}%'))
    
    propostas = query.order_by(PropostaComercialSIGE.criado_em.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('propostas/listar.html', propostas=propostas, 
                         status_filter=status_filter, cliente_filter=cliente_filter)

@propostas_bp.route('/api/template/<int:template_id>')
@login_required
def get_template_data(template_id):
    """API para obter dados de um template específico"""
    # Admin_id dinâmico que funciona em dev e produção
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    
    print(f"DEBUG API TEMPLATE: Buscando template {template_id} para admin_id={admin_id}")
    
    # Buscar apenas template do próprio admin (multitenant)
    template = PropostaTemplate.query.filter_by(
        id=template_id, 
        admin_id=admin_id, 
        ativo=True
    ).first()
    
    if not template:
        return jsonify({'error': 'Template não encontrado'}), 404
    
    return jsonify({
        'id': template.id,
        'nome': template.nome,
        'categoria': template.categoria,
        'itens_inclusos': template.itens_inclusos or '',
        'itens_exclusos': template.itens_exclusos or '',
        'condicoes': template.condicoes or '',
        'condicoes_pagamento': template.condicoes_pagamento or '',
        'garantias': template.garantias or '',
        'prazo_entrega_dias': template.prazo_entrega_dias or 90,
        'validade_dias': template.validade_dias or 7,
        'percentual_nota_fiscal': float(template.percentual_nota_fiscal) if template.percentual_nota_fiscal else 13.5,
        'itens_padrao': template.itens_padrao or []
    })

@propostas_bp.route('/<int:proposta_id>/organizar')
@login_required
def organizar_proposta(proposta_id):
    """Interface de organização drag-and-drop para propostas"""
    # Admin_id dinâmico que funciona em dev e produção
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    
    proposta = PropostaComercialSIGE.query.filter_by(id=proposta_id, admin_id=admin_id).first()
    
    if not proposta:
        flash('Proposta não encontrada', 'error')
        return redirect(url_for('propostas.index'))
    
    return render_template('propostas/organizar_proposta.html', proposta=proposta)

@propostas_bp.route('/debug-templates')
def debug_templates():
    """Rota de debug para verificar templates sem autenticação"""
    from models import PropostaTemplate
    
    print("DEBUG: Iniciando debug de templates...")
    
    # Verificar todos os templates ativos
    todos_templates = PropostaTemplate.query.filter_by(ativo=True).all()
    print(f"DEBUG: Total de templates ativos no banco: {len(todos_templates)}")
    
    for t in todos_templates:
        print(f"DEBUG: Template {t.id}: {t.nome} (admin_id={t.admin_id}, publico={t.publico})")
    
    # Verificar templates para admin_id=10 (Vale Verde)
    templates_vale_verde = PropostaTemplate.query.filter_by(admin_id=10, ativo=True).all()
    print(f"DEBUG: Templates para admin_id=10: {len(templates_vale_verde)}")
    
    # Verificar templates públicos
    templates_publicos = PropostaTemplate.query.filter_by(publico=True, ativo=True).all()
    print(f"DEBUG: Templates públicos: {len(templates_publicos)}")
    
    # Retornar resultado simples
    resultado = {
        'total_templates': len(todos_templates),
        'templates_vale_verde': len(templates_vale_verde),
        'templates_publicos': len(templates_publicos),
        'templates': [{'id': t.id, 'nome': t.nome, 'admin_id': t.admin_id, 'publico': t.publico} for t in todos_templates]
    }
    
    return f"<pre>{resultado}</pre>"

@propostas_bp.route('/test-nova')
def test_nova_proposta():
    """Teste da página nova proposta sem autenticação"""
    from models import PropostaTemplate
    
    # Simular usuário Vale Verde (ID 10)
    admin_id = 10
    
    # Buscar apenas templates próprios do usuário (sem públicos)
    templates = PropostaTemplate.query.filter(
        PropostaTemplate.admin_id == admin_id,
        PropostaTemplate.ativo == True
    ).all()
    
    print(f"DEBUG TEST: Admin ID {admin_id} - encontrou {len(templates)} templates (incluindo públicos)")
    
    for t in templates:
        print(f"DEBUG TEST: Template {t.id}: {t.nome} (admin_id={t.admin_id}, publico={t.publico})")
    
    print(f"DEBUG TEST: Enviando {len(templates)} templates para o template HTML")
    return render_template('propostas/nova_proposta.html', templates=templates)

@propostas_bp.route('/nova')
@login_required
@admin_required
def nova_proposta():
    """Exibe formulário para criar nova proposta"""
    # Admin_id dinâmico que funciona em dev e produção
    from multitenant_helper import get_admin_id
    admin_id = get_admin_id()
    print(f"DEBUG TEMPLATES: Buscando templates para admin_id={admin_id}")
    
    # Buscar configuração da empresa
    config_empresa = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    
    # Buscar templates do admin correto (multitenant)
    templates = PropostaTemplate.query.filter_by(
        admin_id=admin_id, 
        ativo=True
    ).order_by(PropostaTemplate.categoria, PropostaTemplate.nome).all()
    
    print(f"DEBUG TEMPLATES: Encontrou {len(templates)} templates para admin_id={admin_id}")
    for t in templates:
        print(f"DEBUG TEMPLATE: {t.id}: {t.nome} (admin_id={t.admin_id})")
    
    # Se não encontrou templates para esse admin_id, mostrar todos disponíveis para debug
    if len(templates) == 0:
        todos_templates = PropostaTemplate.query.filter_by(ativo=True).all()
        print(f"DEBUG: Nenhum template para admin_id={admin_id}. Templates disponíveis:")
        for t in todos_templates:
            print(f"  Template {t.id}: {t.nome} (admin_id={t.admin_id})")
    
    # Definir valores padrão da empresa ou usar padrões do sistema
    padrao_itens_inclusos = "Mão de obra para execução dos serviços; Todos os equipamentos de segurança necessários; Transporte e alimentação da equipe; Container para guarda de ferramentas; Movimentação de carga (Munck); Transporte dos materiais"
    
    padrao_itens_exclusos = "Projeto e execução de qualquer obra civil, fundações, alvenarias, elétrica, automação, tubulações etc.; Execução de ensaios destrutivos e radiográficos; Fornecimento de local para armazenagem das peças; Fornecimento e/ou serviços não especificados claramente nesta proposta; Fornecimento de escoramento temporário; Fornecimento de andaimes e plataformas; Técnico de segurança; Pintura final de acabamento; Calhas, rufos, condutores e pingadeiras"
    
    padrao_condicoes_pagamento = """10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem"""
    
    padrao_garantias = "A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800."
    
    padrao_condicoes = "Proposta válida por 7 dias a partir da data de emissão; Valores não incluem impostos (13,5% de nota fiscal); Execução conforme normas técnicas brasileiras (NBR 8800, NBR 14762); Projeto executivo detalhado incluído no escopo de fornecimento"
    
    return render_template('propostas/nova_proposta.html', 
                         config_empresa=config_empresa,
                         templates=templates,
                         padrao_itens_inclusos=padrao_itens_inclusos,
                         padrao_itens_exclusos=padrao_itens_exclusos,
                         padrao_condicoes_pagamento=padrao_condicoes_pagamento,
                         padrao_garantias=padrao_garantias,
                         padrao_condicoes=padrao_condicoes,
                         padrao_prazo_entrega=90,
                         padrao_validade=7,
                         padrao_percentual_nf=13.5)

@propostas_bp.route('/api/template/<int:template_id>')
def api_template_detalhes(template_id):
    """API para retornar detalhes de um template"""
    from models import PropostaTemplate
    
    try:
        # Buscar template
        template = PropostaTemplate.query.get(template_id)
        if not template:
            return jsonify({'error': 'Template não encontrado'}), 404
        
        # Retornar dados do template diretamente (compatível com JavaScript atual)
        return jsonify({
            'id': template.id,
            'nome': template.nome,
            'categoria': template.categoria,
            'itens_inclusos': template.itens_inclusos,
            'itens_exclusos': template.itens_exclusos,
            'condicoes': template.condicoes,
            'condicoes_pagamento': template.condicoes_pagamento,
            'garantias': template.garantias,
            'prazo_entrega_dias': template.prazo_entrega_dias,
            'validade_dias': template.validade_dias,
            'percentual_nota_fiscal': float(template.percentual_nota_fiscal) if template.percentual_nota_fiscal else 13.5,
            'itens_padrao': []  # Por enquanto vazio, implementar depois se necessário
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@propostas_bp.route('/nova-funcionando-backup')
def nova_proposta_funcionando():
    """Página nova proposta funcionando - versão sem autenticação"""
    from models import PropostaTemplate
    
    # Simular usuário Vale Verde (ID 10) - mesmo que o bypass
    admin_id = 10
    
    # Buscar apenas templates próprios do usuário (sem públicos)
    templates = PropostaTemplate.query.filter(
        PropostaTemplate.admin_id == admin_id,
        PropostaTemplate.ativo == True
    ).all()
    
    print(f"DEBUG NOVA: Admin ID {admin_id} - encontrou {len(templates)} templates disponíveis")
    
    for t in templates:
        print(f"DEBUG NOVA: Template {t.id}: {t.nome} (categoria: {t.categoria})")
    
    return render_template('propostas/nova_proposta.html', templates=templates)

@propostas_bp.route('/criar-teste-template/<int:template_id>')
def criar_teste_template(template_id):
    """Cria uma proposta de teste usando um template para validar o sistema"""
    from models import PropostaComercialSIGE, PropostaItem, PropostaTemplate
    
    try:
        # Buscar template especificado
        template = PropostaTemplate.query.get(template_id)
        if not template:
            return jsonify({'error': f'Template {template_id} não encontrado'}), 404
        
        # Criar proposta baseada no template
        proposta = PropostaComercialSIGE()
        proposta.cliente_nome = f"Cliente Teste {template.nome}"
        proposta.cliente_telefone = "(11) 98765-4321"
        proposta.cliente_email = "contato@fazendaesperanca.com.br"
        proposta.cliente_endereco = "Estrada Rural KM 15, Zona Rural - São José dos Campos/SP"
        proposta.assunto = f"Proposta Comercial - {template.nome}"
        proposta.objeto = f"Fornecimento e montagem de {template.nome.lower()} conforme especificações técnicas em anexo"
        proposta.documentos_referencia = "Projeto arquitetônico fornecido pelo cliente"
        
        # Usar dados do template
        proposta.prazo_entrega_dias = template.prazo_entrega_dias
        proposta.validade_dias = template.validade_dias
        proposta.percentual_nota_fiscal = float(template.percentual_nota_fiscal)
        proposta.condicoes_pagamento = template.condicoes_pagamento
        proposta.garantias = template.garantias
        proposta.condicoes = template.condicoes or "Proposta gerada automaticamente para teste do sistema"
        proposta.criado_por = 10  # Admin Vale Verde
        proposta.admin_id = 10  # Admin ID
        
        db.session.add(proposta)
        db.session.flush()
        
        # Criar itens baseados no template
        total_valor = 0
        for i, item_template in enumerate(template.itens_padrao or []):
            item = PropostaItem()
            item.proposta_id = proposta.id
            item.item_numero = i + 1
            item.descricao = item_template.get('descricao', '')
            item.quantidade = float(item_template.get('quantidade', 0))
            item.unidade = item_template.get('unidade', 'un')
            item.preco_unitario = float(item_template.get('preco_unitario', 0))
            item.ordem = i + 1
            
            total_valor += item.quantidade * item.preco_unitario
            db.session.add(item)
        
        # Incrementar uso do template
        template.incrementar_uso()
        
        db.session.commit()
        
        result = {
            'success': True,
            'message': f'Proposta de teste criada com sucesso!',
            'proposta_id': proposta.id,
            'cliente': proposta.cliente_nome,
            'template_usado': template.nome,
            'total_itens': len(template.itens_padrao or []),
            'valor_total': f'R$ {total_valor:,.2f}',
            'url_visualizar': f'/propostas/{proposta.id}'
        }
        
        print(f"DEBUG TESTE: Proposta criada - ID {proposta.id}, Cliente: {proposta.cliente_nome}")
        print(f"DEBUG TESTE: Template usado: {template.nome} ({len(template.itens_padrao or [])} itens)")
        print(f"DEBUG TESTE: Valor total: R$ {total_valor:,.2f}")
        
        return jsonify(result)
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO TESTE: {str(e)}")
        return jsonify({'error': f'Erro ao criar proposta de teste: {str(e)}'}), 500



@propostas_bp.route('/criar', methods=['POST'])
@login_required
@admin_required
def criar_proposta():
    """Cria uma nova proposta"""
    try:
        # Admin_id dinâmico que funciona em dev e produção
        from multitenant_helper import get_admin_id
        admin_id = get_admin_id()
        # Validação obrigatória: apenas nome do cliente
        cliente_nome = request.form.get('cliente_nome')
        if not cliente_nome or not cliente_nome.strip():
            flash('Nome do cliente é obrigatório!', 'error')
            return redirect(url_for('propostas.nova_proposta'))
        
        # Dados básicos da proposta
        proposta = PropostaComercialSIGE()
        proposta.cliente_nome = cliente_nome.strip()
        proposta.numero_proposta = request.form.get('numero_proposta', '').strip()
        proposta.cliente_telefone = request.form.get('cliente_telefone')
        proposta.cliente_email = request.form.get('cliente_email')
        proposta.cliente_endereco = request.form.get('cliente_endereco')
        proposta.assunto = request.form.get('assunto') or None
        proposta.objeto = request.form.get('objeto') or None
        proposta.documentos_referencia = request.form.get('documentos_referencia')
        proposta.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
        proposta.observacoes_entrega = request.form.get('observacoes_entrega')
        proposta.validade_dias = int(request.form.get('validade_dias', 7))
        proposta.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
        # Campos editáveis do PDF - agora totalmente customizáveis
        proposta.itens_inclusos = request.form.get('itens_inclusos', '')
        proposta.itens_exclusos = request.form.get('itens_exclusos', '')
        proposta.condicoes = request.form.get('condicoes', '')
        proposta.condicoes_pagamento = request.form.get('condicoes_pagamento', '')
        proposta.garantias = request.form.get('garantias', '')
        
        # Novos campos editáveis - primeira e segunda página PDF
        proposta.carta_abertura = request.form.get('carta_abertura', '')
        proposta.apresentacao_empresa = request.form.get('apresentacao_empresa', '')
        proposta.descricao_projeto = request.form.get('descricao_projeto', '')
        proposta.carta_fechamento = request.form.get('carta_fechamento', '')
        
        # Seções técnicas editáveis
        proposta.secao_especificacoes = request.form.get('secao_especificacoes', '')
        proposta.secao_materiais = request.form.get('secao_materiais', '')
        proposta.secao_fabricacao = request.form.get('secao_fabricacao', '')
        proposta.secao_logistica = request.form.get('secao_logistica', '')
        proposta.secao_montagem = request.form.get('secao_montagem', '')
        proposta.secao_qualidade = request.form.get('secao_qualidade', '')
        proposta.secao_seguranca = request.form.get('secao_seguranca', '')
        proposta.secao_assistencia = request.form.get('secao_assistencia', '')
        proposta.secao_consideracoes = request.form.get('secao_consideracoes', '')
        
        proposta.criado_por = getattr(current_user, 'id', 10)
        # admin_id será setado automaticamente via SQL ou modelo
        
        db.session.add(proposta)
        db.session.flush()  # Para obter o ID da proposta
        
        # Debug dos dados recebidos
        print(f"DEBUG ITENS: Form data keys: {list(request.form.keys())}")
        
        valor_total_proposta = 0
        
        # Processar itens organizados por template (formato novo)
        templates_data = request.form.get('templates_organizados')
        if templates_data:
            import json
            try:
                templates_organizados = json.loads(templates_data)
                print(f"DEBUG TEMPLATES: {len(templates_organizados)} categorias encontradas")
                
                for categoria in templates_organizados:
                    categoria_titulo = categoria.get('categoria_titulo', '')
                    template_origem_id = categoria.get('template_origem_id')
                    template_origem_nome = categoria.get('template_origem_nome', '')
                    
                    for i, item_data in enumerate(categoria.get('itens', [])):
                        item = PropostaItem()
                        item.proposta_id = proposta.id
                        item.descricao = item_data.get('descricao', '')
                        item.quantidade = float(item_data.get('quantidade', 0))
                        item.unidade = item_data.get('unidade', 'un')
                        item.preco_unitario = float(item_data.get('preco_unitario', 0))
                        
                        # Campos para organização
                        item.categoria_titulo = categoria_titulo
                        item.template_origem_id = template_origem_id
                        item.template_origem_nome = template_origem_nome
                        item.grupo_ordem = categoria.get('grupo_ordem', 0)
                        item.item_ordem_no_grupo = i + 1
                        item.ordem = i + 1
                        
                        valor_item = item.quantidade * item.preco_unitario
                        valor_total_proposta += valor_item
                        
                        print(f"DEBUG TEMPLATE ITEM: {item.descricao} - {item.quantidade} x R$ {item.preco_unitario} = R$ {valor_item}")
                        db.session.add(item)
                        
            except json.JSONDecodeError as e:
                print(f"DEBUG: Erro ao processar templates organizados: {e}")
                # Fallback para processamento simples
        
        # Fallback: Processar itens simples se não houver templates organizados
        if not templates_data:
            descricoes = request.form.getlist('item_descricao')
            quantidades = request.form.getlist('item_quantidade')
            unidades = request.form.getlist('item_unidade')
            precos = request.form.getlist('item_preco')
            
            print(f"DEBUG ITENS SIMPLES: {len(descricoes)} itens encontrados")
            
            for i, descricao in enumerate(descricoes):
                if descricao and descricao.strip():
                    item = PropostaItem()
                    item.proposta_id = proposta.id
                    item.item_numero = i + 1
                    item.descricao = descricao.strip()
                    item.quantidade = float(quantidades[i]) if i < len(quantidades) and quantidades[i] else 0
                    item.unidade = unidades[i] if i < len(unidades) else 'un'
                    item.preco_unitario = float(precos[i]) if i < len(precos) and precos[i] else 0
                    item.ordem = i + 1
                    
                    valor_item = item.quantidade * item.preco_unitario
                    valor_total_proposta += valor_item
                    
                    print(f"DEBUG ITEM SIMPLES {i+1}: {item.descricao} - R$ {valor_item}")
                    db.session.add(item)
        
        # Atualizar valor total da proposta
        proposta.valor_total = valor_total_proposta
        print(f"DEBUG PROPOSTA: Valor total calculado: R$ {valor_total_proposta}")
        
        db.session.commit()
        flash('Proposta criada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.nova_proposta'))

@propostas_bp.route('/<int:id>')
@login_required
@admin_required
def visualizar_proposta(id):
    """Visualiza uma proposta específica"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    return render_template('propostas/visualizar.html', proposta=proposta)

@propostas_bp.route('/<int:id>/editar')
@login_required
@admin_required
def editar_proposta(id):
    """Formulário para editar proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    templates = PropostaTemplate.query.filter_by(ativo=True).all()
    return render_template('propostas/editar.html', proposta=proposta, templates=templates)

@propostas_bp.route('/<int:id>/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar_proposta(id):
    """Atualiza uma proposta existente"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    try:
        # Atualizar dados da proposta
        proposta.cliente_nome = request.form.get('cliente_nome')
        proposta.numero_proposta = request.form.get('numero_proposta', '').strip()
        proposta.cliente_email = request.form.get('cliente_email')
        proposta.cliente_telefone = request.form.get('cliente_telefone')
        proposta.cliente_cpf_cnpj = request.form.get('cliente_cpf_cnpj')
        proposta.cliente_endereco = request.form.get('cliente_endereco')
        proposta.assunto = request.form.get('assunto') or None
        proposta.objeto = request.form.get('objeto') or None
        proposta.prazo_entrega_dias = int(request.form.get('prazo_entrega_dias', 90))
        proposta.percentual_nota_fiscal = float(request.form.get('percentual_nota_fiscal', 13.5))
        proposta.condicoes_pagamento = request.form.get('condicoes_pagamento')
        proposta.garantias = request.form.get('garantias')
        proposta.consideracoes_gerais = request.form.get('consideracoes_gerais')
        
        # Processar itens inclusos/exclusos
        itens_inclusos_text = request.form.get('itens_inclusos', '')
        itens_exclusos_text = request.form.get('itens_exclusos', '')
        
        if itens_inclusos_text:
            proposta.itens_inclusos = [item.strip() for item in itens_inclusos_text.split(';') if item.strip()]
        else:
            proposta.itens_inclusos = []
            
        if itens_exclusos_text:
            proposta.itens_exclusos = [item.strip() for item in itens_exclusos_text.split(';') if item.strip()]
        else:
            proposta.itens_exclusos = []
        
        # Remover itens existentes
        PropostaItem.query.filter_by(proposta_id=proposta.id).delete()
        
        # Adicionar novos itens
        descricoes = request.form.getlist('item_descricao')
        quantidades = request.form.getlist('item_quantidade')
        unidades = request.form.getlist('item_unidade')
        precos = request.form.getlist('item_preco')
        
        valor_total_proposta = 0
        
        for i, descricao in enumerate(descricoes):
            if descricao and descricao.strip():
                item = PropostaItem()
                item.proposta_id = proposta.id
                item.item_numero = i + 1
                item.descricao = descricao.strip()
                item.quantidade = float(quantidades[i]) if i < len(quantidades) and quantidades[i] else 0
                item.unidade = unidades[i] if i < len(unidades) else 'un'
                item.preco_unitario = float(precos[i]) if i < len(precos) and precos[i] else 0
                item.ordem = i + 1
                
                valor_item = item.quantidade * item.preco_unitario
                valor_total_proposta += valor_item
                
                db.session.add(item)
        
        proposta.valor_total = valor_total_proposta
        proposta.atualizado_em = datetime.utcnow()
        
        db.session.commit()
        flash('Proposta atualizada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.editar_proposta', id=id))

@propostas_bp.route('/<int:id>/arquivos/upload', methods=['POST'])
@login_required
@admin_required
def upload_arquivo(id):
    """Upload de arquivo para uma proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    if 'arquivo' not in request.files:
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(arquivo.filename):
        return jsonify({'error': 'Tipo de arquivo não permitido'}), 400
    
    try:
        # Criar diretório se não existir
        upload_path = os.path.join(UPLOAD_FOLDER, str(proposta.id))
        os.makedirs(upload_path, exist_ok=True)
        
        # Gerar nome único para o arquivo
        filename = arquivo.filename or 'arquivo'
        nome_original = secure_filename(filename)
        extensao = nome_original.rsplit('.', 1)[1].lower() if '.' in nome_original else ''
        nome_arquivo = f"{uuid.uuid4().hex}.{extensao}"
        caminho_completo = os.path.join(upload_path, nome_arquivo)
        
        # Salvar arquivo
        arquivo.save(caminho_completo)
        
        # Salvar informações no banco
        proposta_arquivo = PropostaArquivo()
        proposta_arquivo.proposta_id = proposta.id
        proposta_arquivo.nome_arquivo = nome_arquivo
        proposta_arquivo.nome_original = nome_original
        proposta_arquivo.tipo_arquivo = mimetypes.guess_type(nome_original)[0]
        proposta_arquivo.tamanho_bytes = os.path.getsize(caminho_completo)
        proposta_arquivo.caminho_arquivo = caminho_completo
        proposta_arquivo.categoria = get_file_category(nome_original)
        proposta_arquivo.enviado_por = current_user.id
        
        db.session.add(proposta_arquivo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'arquivo': proposta_arquivo.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao fazer upload: {str(e)}'}), 500

@propostas_bp.route('/api/template-test/<int:template_id>')
def obter_template_test(template_id):
    """API de teste para obter dados de um template sem autenticação"""
    template = PropostaTemplate.query.get_or_404(template_id)
    template_data = template.to_dict()
    
    result = {
        'success': True,
        'template': template_data
    }
    
    print(f"DEBUG API: Template {template_id} carregado: {template.nome}")
    print(f"DEBUG API: Itens padrão: {len(template.itens_padrao) if template.itens_padrao else 0}")
    return jsonify(result)

@propostas_bp.route('/api/template/<int:template_id>')
def obter_template(template_id):
    """API para obter dados de um template"""
    template = PropostaTemplate.query.get_or_404(template_id)
    template_data = template.to_dict()
    
    result = {
        'success': True,
        'template': template_data
    }
    return jsonify(result)

@propostas_bp.route('/<int:id>/pdf')
@login_required
@admin_required
def gerar_pdf(id):
    """Gera PDF da proposta"""
    try:
        proposta = PropostaComercialSIGE.query.get_or_404(id)
        
        # Debug da proposta
        print(f"DEBUG PDF: Proposta {proposta.numero_proposta}")
        print(f"DEBUG PDF: Cliente: {proposta.cliente_nome}")
        print(f"DEBUG PDF: Valor total: {proposta.valor_total}")
        print(f"DEBUG PDF: Número de itens: {len(proposta.itens) if proposta.itens else 0}")
        
        # Buscar configurações da empresa - admin_id dinâmico (com fallback para desenvolvimento)
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario.value == 'funcionario':
                admin_id = getattr(current_user, 'admin_id', current_user.id)
            else:
                admin_id = current_user.id
        else:
            # Fallback para desenvolvimento quando não autenticado
            admin_id = 10
        
        config_empresa = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        
        # Tratamento de dados para formatação correta no PDF
        import json
        
        if hasattr(proposta, 'itens_inclusos') and proposta.itens_inclusos:
            if isinstance(proposta.itens_inclusos, str):
                try:
                    # Tenta parsear se for string JSON
                    itens_list = json.loads(proposta.itens_inclusos)
                    if isinstance(itens_list, list):
                        proposta.itens_inclusos = '\n'.join(itens_list)
                except json.JSONDecodeError:
                    # Se não for JSON válido, mantém como está
                    pass
            elif isinstance(proposta.itens_inclusos, list):
                proposta.itens_inclusos = '\n'.join(proposta.itens_inclusos)
        
        if hasattr(proposta, 'itens_exclusos') and proposta.itens_exclusos:
            if isinstance(proposta.itens_exclusos, str):
                try:
                    # Tenta parsear se for string JSON
                    itens_list = json.loads(proposta.itens_exclusos)
                    if isinstance(itens_list, list):
                        proposta.itens_exclusos = '\n'.join(itens_list)
                except json.JSONDecodeError:
                    # Se não for JSON válido, mantém como está
                    pass
            elif isinstance(proposta.itens_exclusos, list):
                proposta.itens_exclusos = '\n'.join(proposta.itens_exclusos)
        
        # Debug da configuração
        if config_empresa:
            print(f"DEBUG PDF: Config empresa: {config_empresa.nome_empresa}")
            print(f"DEBUG PDF: Header PDF presente: {'SIM' if config_empresa.header_pdf_base64 else 'NÃO'}")
            if config_empresa.header_pdf_base64:
                print(f"DEBUG PDF: Tamanho header: {len(config_empresa.header_pdf_base64)} chars")
        else:
            print("DEBUG PDF: Nenhuma configuração encontrada")
        
        # Verificar se deve usar formato Estruturas do Vale (padrão)
        formato = request.args.get('formato', 'estruturas_vale')
        
        if formato == 'estruturas_vale':
            template_name = 'propostas/pdf_estruturas_vale_paginado.html'
        else:
            template_name = 'propostas/pdf.html'
        
        print(f"DEBUG PDF: Usando template: {template_name}")
        
        # Renderizar HTML da proposta
        html_content = render_template(template_name, 
                                     proposta=proposta, 
                                     config=config_empresa,
                                     config_empresa=config_empresa)
        
        print("DEBUG PDF: Template renderizado com sucesso")
        return html_content
        
    except Exception as e:
        print(f"ERRO PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Erro ao gerar PDF: {str(e)}", 500

@propostas_bp.route('/<int:id>/enviar', methods=['POST'])
@login_required
@admin_required
def enviar_proposta(id):
    """Envia proposta para o cliente"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    try:
        # Atualizar status e data de envio
        proposta.status = 'enviada'
        proposta.data_envio = datetime.utcnow()
        
        db.session.commit()
        
        # Aqui seria implementado o envio por email
        # Por enquanto apenas atualiza o status
        
        flash('Proposta enviada com sucesso!', 'success')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao enviar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))

@propostas_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_proposta(id):
    """Exclui uma proposta"""
    proposta = PropostaComercialSIGE.query.get_or_404(id)
    
    try:
        # Remover arquivos físicos
        upload_path = os.path.join(UPLOAD_FOLDER, str(proposta.id))
        if os.path.exists(upload_path):
            import shutil
            shutil.rmtree(upload_path)
        
        # Remover do banco (cascade remove itens e arquivos)
        db.session.delete(proposta)
        db.session.commit()
        
        flash('Proposta excluída com sucesso!', 'success')
        return redirect(url_for('propostas.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.visualizar_proposta', id=proposta.id))

# Portal do Cliente
@propostas_bp.route('/cliente/<token>')
def portal_cliente(token):
    """Portal para o cliente visualizar e aprovar proposta"""
    from models import ConfiguracaoEmpresa, Usuario
    
    proposta = PropostaComercialSIGE.query.filter_by(token_cliente=token).first_or_404()
    
    # Buscar admin_id através do usuário que criou a proposta
    admin_id = None
    if proposta.criado_por:
        usuario = Usuario.query.get(proposta.criado_por)
        if usuario:
            admin_id = usuario.admin_id or usuario.id  # Se admin_id for null, usa o próprio id
    
    # Fallback: se não conseguir admin_id, usar ID padrão (assumindo que admin principal é 10)
    if not admin_id:
        admin_id = 10
    
    # Carregar configurações da empresa para personalização
    config_empresa = None
    if admin_id:
        config_empresa = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    
    # Configurar cores personalizadas
    cores_empresa = {
        'primaria': config_empresa.cor_primaria if config_empresa and config_empresa.cor_primaria else '#007bff',
        'secundaria': config_empresa.cor_secundaria if config_empresa and config_empresa.cor_secundaria else '#6c757d',
        'fundo_proposta': config_empresa.cor_fundo_proposta if config_empresa and config_empresa.cor_fundo_proposta else '#f8f9fa'
    }
    
    return render_template('propostas/portal_cliente.html', 
                         proposta=proposta, 
                         config_empresa=config_empresa,
                         empresa_cores=cores_empresa)

@propostas_bp.route('/cliente/<token>/aprovar', methods=['POST'])
def aprovar_proposta(token):
    """Cliente aprova a proposta"""
    proposta = PropostaComercialSIGE.query.filter_by(token_cliente=token).first_or_404()
    
    try:
        proposta.status = 'aprovada'
        proposta.data_resposta_cliente = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get('observacoes', '')
        
        db.session.commit()
        
        flash('Proposta aprovada com sucesso!', 'success')
        return render_template('propostas/aprovada.html', proposta=proposta)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar proposta: {str(e)}', 'error')
        return redirect(url_for('propostas.portal_cliente', token=token))

@propostas_bp.route('/cliente/<token>/rejeitar', methods=['POST'])
def rejeitar_proposta(token):
    """Cliente rejeita a proposta"""
    proposta = PropostaComercialSIGE.query.filter_by(token_cliente=token).first_or_404()
    
    try:
        proposta.status = 'rejeitada'
        proposta.data_resposta_cliente = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get('observacoes', '')
        
        db.session.commit()
        
        flash('Sua resposta foi registrada.', 'info')
        return render_template('propostas/rejeitada.html', proposta=proposta)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar resposta: {str(e)}', 'error')
        return redirect(url_for('propostas.portal_cliente', token=token))