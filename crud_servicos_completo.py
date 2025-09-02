"""
CRUD COMPLETO DE SERVIÇOS E SUBATIVIDADES - SIGE v8.0
Sistema integrado para gestão de serviços e suas subatividades
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, render_template_string
from models import db, Servico, SubatividadeMestre
import logging
import os
import traceback
from datetime import datetime

# Sistema de tratamento de erros robusto para produção
def handle_detailed_error(exception, context="Sistema", fallback_url="main.dashboard", additional_info=None):
    """Manipula erros com logs detalhados e interface completa para produção"""
    
    # Importar sistema de erro de produção
    try:
        from utils.production_error_handler import capture_production_error, format_error_for_user
        
        # Capturar erro completo
        error_info = capture_production_error(exception, context, additional_info)
        
        # Gerar interface de erro
        error_html = format_error_for_user(error_info)
        
        # Retornar página de erro completa
        from flask import render_template_string
        return render_template_string(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Erro - {context}</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body style="background-color: #f8f9fa;">
            <div class="container-fluid">
                {error_html}
            </div>
        </body>
        </html>
        """), 500
        
    except ImportError:
        # Fallback se não conseguir importar
        import traceback
        error_trace = traceback.format_exc()
        
        logger.error(f"❌ {context}: {str(exception)}")
        logger.error(f"📋 Traceback:\n{error_trace}")
        
        flash(f'Erro no {context.lower()}: {str(exception)}', 'error')
        return redirect(url_for(fallback_url))

def log_sql_error(exception, query_context=""):
    """Log específico para erros SQL"""
    logger.error(f"🚨 ERRO SQL: {str(exception)}")
    if query_context:
        logger.error(f"📋 Contexto: {query_context}")
    
    # Detectar tipos de erro
    error_str = str(exception).lower()
    if "transaction" in error_str and "aborted" in error_str:
        logger.error("💥 TRANSAÇÃO ABORTADA - Possível conflito de dados")
    elif "duplicate key" in error_str:
        logger.error("🔑 CHAVE DUPLICADA - Dados já existem")
    elif "foreign key" in error_str:
        logger.error("🔗 FOREIGN KEY - Referência inválida")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprint
servicos_crud_bp = Blueprint('servicos_crud', __name__, url_prefix='/servicos')

# Funções auxiliares
def get_admin_id():
    """Obter admin_id do usuário atual"""
    try:
        from utils.auth_utils import get_admin_id_from_user
        return get_admin_id_from_user()
    except ImportError:
        from bypass_auth import obter_admin_id
        return obter_admin_id()

# ================================
# ROTAS DE VISUALIZAÇÃO
# ================================

@servicos_crud_bp.route('/')
@servicos_crud_bp.route('/index')
def index():
    """Lista todos os serviços com suas subatividades"""
    try:
        admin_id = get_admin_id()
        logger.info(f"📋 Carregando lista de serviços para admin_id={admin_id}")
        
        # Buscar serviços ativos com tratamento de erro específico
        try:
            servicos = Servico.query.filter(
                Servico.admin_id == admin_id,
                Servico.ativo == True
            ).order_by(Servico.nome).all()
            logger.info(f"✅ Query executada com sucesso - encontrados {len(servicos)} serviços")
        except Exception as query_error:
            logger.error(f"❌ Erro na query de serviços: {str(query_error)}")
            # Tentar query mais simples
            try:
                servicos = db.session.execute(
                    db.text("SELECT * FROM servico WHERE admin_id = :admin_id AND ativo = true ORDER BY nome"),
                    {"admin_id": admin_id}
                ).fetchall()
                logger.info(f"✅ Query SQL direta executada - encontrados {len(servicos)} serviços")
                # Converter para objetos Servico
                servicos = [Servico.query.get(s.id) for s in servicos]
            except Exception as raw_query_error:
                logger.error(f"❌ Erro na query SQL direta: {str(raw_query_error)}")
                raise query_error
        
        # Para cada serviço, buscar suas subatividades com tratamento de erro
        for servico in servicos:
            try:
                subatividades = SubatividadeMestre.query.filter(
                    SubatividadeMestre.servico_id == servico.id,
                    SubatividadeMestre.admin_id == admin_id,
                    SubatividadeMestre.ativo == True
                ).order_by(SubatividadeMestre.ordem_padrao).all()
                
                # Adicionar subatividades ao objeto serviço
                servico.subatividades = subatividades
                logger.debug(f"  - {servico.nome}: {len(subatividades)} subatividades")
            except Exception as sub_error:
                logger.error(f"❌ Erro ao buscar subatividades para serviço {servico.id}: {str(sub_error)}")
                # Em caso de erro, definir lista vazia
                servico.subatividades = []
        
        # Calcular estatísticas
        total_subatividades = sum(len(s.subatividades) for s in servicos)
        categorias_count = len(set(s.categoria for s in servicos if s.categoria))
        
        logger.info(f"✅ Encontrados {len(servicos)} serviços")
        
        estatisticas = {
            'total': len(servicos),
            'ativo': len(servicos),
            'subatividades': total_subatividades,
            'categorias': categorias_count
        }
        
        # Verificar se template existe, senão usar template base
        try:
            return render_template('servicos/index_novo.html',
                                 servicos=servicos,
                                 estatisticas=estatisticas)
        except Exception:
            # Fallback para template básico se não existir
            return render_template('base_completo.html',
                                 title="Serviços",
                                 content=f"""
                                 <div class="container mt-4">
                                     <div class="card">
                                         <div class="card-header">
                                             <h3>Serviços Cadastrados</h3>
                                         </div>
                                         <div class="card-body">
                                             <p>Total: {len(servicos)} serviços</p>
                                             <p>Subatividades: {total_subatividades}</p>
                                             <p>Categorias: {categorias_count}</p>
                                             <hr>
                                             <h5>Lista de Serviços:</h5>
                                             <ul>
                                             {''.join([f'<li><strong>{s.nome}</strong> ({s.categoria}) - {len(s.subatividades)} subatividades</li>' for s in servicos])}
                                             </ul>
                                         </div>
                                     </div>
                                 </div>
                                 """)
        
    except Exception as e:
        # Rollback da transação se necessário
        try:
            db.session.rollback()
        except:
            pass
        
        # Log específico para erros SQL
        log_sql_error(e, "Carregamento de serviços")
        
        # Usar sistema de erro detalhado
        return handle_detailed_error(e, "Sistema de Serviços", "main.dashboard")

@servicos_crud_bp.route('/novo', methods=['GET'])
def novo_servico():
    """Exibe formulário para criar novo serviço"""
    try:
        admin_id = get_admin_id()
        logger.info(f"📝 Abrindo formulário de novo serviço para admin_id={admin_id}")
        
        # Importar sistema de categorias
        try:
            from categoria_servicos import obter_categorias_disponiveis
            categorias = obter_categorias_disponiveis(admin_id)
        except ImportError:
            # Fallback se módulo não estiver disponível
            categorias = [
                'Estrutural',
                'Soldagem',
                'Pintura',
                'Instalação',
                'Acabamento',
                'Manutenção',
                'Outros'
            ]
        
        # Verificar se template existe, senão usar inline
        try:
            return render_template('servicos/novo.html', categorias=categorias)
        except Exception as template_error:
            logger.warning(f"⚠️ Template servicos/novo.html não encontrado: {template_error}")
            logger.info("🔄 Usando template inline como fallback")
            # Template inline como fallback
            return render_template('base_completo.html',
                                 title="Novo Serviço",
                                 content=f"""
                                 <div class="container mt-4">
                                     <div class="card">
                                         <div class="card-header">
                                             <h3>Criar Novo Serviço</h3>
                                         </div>
                                         <div class="card-body">
                                             <form method="POST" action="/servicos/criar">
                                                 <div class="mb-3">
                                                     <label for="nome" class="form-label">Nome do Serviço</label>
                                                     <input type="text" class="form-control" id="nome" name="nome" required>
                                                 </div>
                                                 <div class="mb-3">
                                                     <label for="descricao" class="form-label">Descrição</label>
                                                     <textarea class="form-control" id="descricao" name="descricao" rows="3"></textarea>
                                                 </div>
                                                 <div class="mb-3">
                                                     <label for="categoria" class="form-label">Categoria</label>
                                                     <div class="input-group">
                                                         <select class="form-control" id="categoria" name="categoria">
                                                             {''.join([f'<option value="{cat}">{cat}</option>' for cat in categorias])}
                                                         </select>
                                                         <button type="button" class="btn btn-outline-success" onclick="abrirModalCategorias()" title="Gerenciar Categorias">
                                                             <i class="fas fa-plus"></i>
                                                         </button>
                                                     </div>
                                                 </div>
                                                 <button type="submit" class="btn btn-success">Criar Serviço</button>
                                                 <a href="/servicos" class="btn btn-secondary">Cancelar</a>
                                             </form>
                                         </div>
                                     </div>
                                 </div>
                                 
                                 <!-- Modal de Categorias -->
                                 <div class="modal fade" id="modalCategorias" tabindex="-1">
                                     <div class="modal-dialog modal-lg">
                                         <div class="modal-content">
                                             <div class="modal-header bg-success text-white">
                                                 <h5 class="modal-title">Gerenciar Categorias</h5>
                                                 <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                             </div>
                                             <div class="modal-body">
                                                 <div class="row mb-3">
                                                     <div class="col-md-8">
                                                         <input type="text" class="form-control" id="novaCategoria" placeholder="Nome da nova categoria">
                                                     </div>
                                                     <div class="col-md-4">
                                                         <button class="btn btn-success w-100" onclick="adicionarCategoria()">Adicionar</button>
                                                     </div>
                                                 </div>
                                                 <div id="listaCategorias" style="max-height: 300px; overflow-y: auto;">
                                                     <div class="text-center py-3">Carregando...</div>
                                                 </div>
                                             </div>
                                             <div class="modal-footer">
                                                 <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                                                 <button type="button" class="btn btn-success" onclick="atualizarSelectCategoria()">Atualizar Lista</button>
                                             </div>
                                         </div>
                                     </div>
                                 </div>
                                 
                                 <!-- Scripts necessários -->
                                 <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
                                 <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/js/all.min.js"></script>
                                 
                                 <script>
                                 // Sistema de gestão de categorias
                                 let categorias = [];
                                 
                                 function abrirModalCategorias() {{
                                     console.log('Abrindo modal de categorias...');
                                     const modal = new bootstrap.Modal(document.getElementById('modalCategorias'));
                                     modal.show();
                                     carregarCategorias();
                                 }}
                                 
                                 async function carregarCategorias() {{
                                     try {{
                                         const response = await fetch('/categorias-servicos/api/listar');
                                         const data = await response.json();
                                         
                                         if (data.success) {{
                                             categorias = data.categorias;
                                             renderizarCategorias();
                                         }} else {{
                                             document.getElementById('listaCategorias').innerHTML = '<div class="alert alert-danger">Erro ao carregar categorias</div>';
                                         }}
                                     }} catch (error) {{
                                         console.error('Erro:', error);
                                         document.getElementById('listaCategorias').innerHTML = '<div class="alert alert-danger">Erro de conexão</div>';
                                     }}
                                 }}
                                 
                                 function renderizarCategorias() {{
                                     const lista = document.getElementById('listaCategorias');
                                     
                                     if (categorias.length === 0) {{
                                         lista.innerHTML = '<div class="text-center py-3 text-muted">Nenhuma categoria encontrada</div>';
                                         return;
                                     }}
                                     
                                     let html = '';
                                     categorias.forEach(categoria => {{
                                         html += `
                                             <div class="d-flex justify-content-between align-items-center p-2 border-bottom">
                                                 <div>
                                                     <span class="badge" style="background-color: ${{categoria.cor || '#198754'}}">
                                                         ${{categoria.nome}}
                                                     </span>
                                                     <small class="text-muted ms-2">${{categoria.descricao || ''}}</small>
                                                 </div>
                                                 <div>
                                                     <button class="btn btn-sm btn-outline-warning me-1" onclick="editarCategoria(${{categoria.id}})">
                                                         <i class="fas fa-edit"></i>
                                                     </button>
                                                     <button class="btn btn-sm btn-outline-danger" onclick="excluirCategoria(${{categoria.id}}, '${{categoria.nome}}')">
                                                         <i class="fas fa-trash"></i>
                                                     </button>
                                                 </div>
                                             </div>
                                         `;
                                     }});
                                     
                                     lista.innerHTML = html;
                                 }}
                                 
                                 async function adicionarCategoria() {{
                                     const nome = document.getElementById('novaCategoria').value.trim();
                                     if (!nome) {{
                                         alert('Digite o nome da categoria');
                                         return;
                                     }}
                                     
                                     try {{
                                         const response = await fetch('/categorias-servicos/api/criar', {{
                                             method: 'POST',
                                             headers: {{'Content-Type': 'application/json'}},
                                             body: JSON.stringify({{nome: nome}})
                                         }});
                                         
                                         const result = await response.json();
                                         
                                         if (result.success) {{
                                             document.getElementById('novaCategoria').value = '';
                                             carregarCategorias();
                                             alert('Categoria adicionada com sucesso!');
                                         }} else {{
                                             alert('Erro: ' + result.error);
                                         }}
                                     }} catch (error) {{
                                         console.error('Erro:', error);
                                         alert('Erro de conexão');
                                     }}
                                 }}
                                 
                                 async function excluirCategoria(id, nome) {{
                                     if (confirm(`Excluir categoria "${{nome}}"?`)) {{
                                         try {{
                                             const response = await fetch(`/categorias-servicos/api/${{id}}/excluir`, {{
                                                 method: 'DELETE'
                                             }});
                                             
                                             const result = await response.json();
                                             
                                             if (result.success) {{
                                                 carregarCategorias();
                                                 alert('Categoria excluída com sucesso!');
                                             }} else {{
                                                 alert('Erro: ' + result.error);
                                             }}
                                         }} catch (error) {{
                                             console.error('Erro:', error);
                                             alert('Erro de conexão');
                                         }}
                                     }}
                                 }}
                                 
                                 async function atualizarSelectCategoria() {{
                                     try {{
                                         const response = await fetch('/categorias-servicos/api/listar');
                                         const data = await response.json();
                                         
                                         if (data.success) {{
                                             const select = document.getElementById('categoria');
                                             const valorAtual = select.value;
                                             select.innerHTML = '<option value="">Selecione uma categoria</option>';
                                             
                                             data.categorias.forEach(categoria => {{
                                                 const option = document.createElement('option');
                                                 option.value = categoria.nome;
                                                 option.textContent = categoria.nome;
                                                 if (categoria.nome === valorAtual) option.selected = true;
                                                 select.appendChild(option);
                                             }});
                                             
                                             const modal = bootstrap.Modal.getInstance(document.getElementById('modalCategorias'));
                                             modal.hide();
                                             alert('Lista atualizada!');
                                         }}
                                     }} catch (error) {{
                                         console.error('Erro:', error);
                                         alert('Erro ao atualizar');
                                     }}
                                 }}
                                 
                                 // Permitir Enter no campo de nova categoria
                                 document.addEventListener('DOMContentLoaded', function() {{
                                     const inputNovaCategoria = document.getElementById('novaCategoria');
                                     if (inputNovaCategoria) {{
                                         inputNovaCategoria.addEventListener('keypress', function(e) {{
                                             if (e.key === 'Enter') {{
                                                 adicionarCategoria();
                                             }}
                                         }});
                                     }}
                                 }});
                                 </script>
                                 """)
        
    except Exception as e:
        logger.error(f"❌ Erro ao abrir formulário: {str(e)}")
        flash(f'Erro ao abrir formulário: {str(e)}', 'error')
        return redirect(url_for('servicos_crud.index'))

@servicos_crud_bp.route('/criar', methods=['POST'])
def criar_servico():
    """Cria novo serviço com subatividades"""
    try:
        admin_id = get_admin_id()
        logger.info(f"💾 Criando novo serviço para admin_id={admin_id}")
        
        # Dados do serviço
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        categoria = request.form.get('categoria', 'Outros')
        
        # Validação
        if not nome:
            flash('Nome do serviço é obrigatório', 'error')
            return redirect(url_for('servicos_crud.index'))
        
        # Verificar se serviço já existe
        servico_existente = Servico.query.filter_by(
            nome=nome,
            admin_id=admin_id,
            ativo=True
        ).first()
        
        if servico_existente:
            flash(f'Serviço "{nome}" já existe', 'error')
            return redirect(url_for('servicos_crud.index'))
            
        # Criar novo serviço
        novo_servico = Servico(
            nome=nome,
            descricao=descricao,
            categoria=categoria,
            admin_id=admin_id,
            ativo=True
        )
        
        db.session.add(novo_servico)
        db.session.flush()  # Para obter o ID do serviço
        
        # Processar subatividades
        subatividades = request.form.getlist('subatividades[]')
        subatividades_criadas = 0
        
        for i, nome_sub in enumerate(subatividades):
            nome_sub = nome_sub.strip()
            if nome_sub:  # Só criar se não estiver vazio
                subatividade = SubatividadeMestre(
                    nome=nome_sub,
                    servico_id=novo_servico.id,
                    admin_id=admin_id,
                    ordem_padrao=i + 1,
                    ativo=True
                )
                db.session.add(subatividade)
                subatividades_criadas += 1
        
        # Salvar tudo
        db.session.commit()
        
        logger.info(f"✅ Serviço '{nome}' criado com {subatividades_criadas} subatividades")
        flash(f'Serviço "{nome}" criado com sucesso!', 'success')
        
        return redirect(url_for('servicos_crud.index'))
        
    except Exception as e:
        db.session.rollback()
        error_trace = traceback.format_exc()
        error_msg = f"Erro ao criar serviço: {str(e)}"
        
        logger.error(f"❌ {error_msg}")
        logger.error(f"📋 Traceback completo:\n{error_trace}")
        
        # Em desenvolvimento, mostrar erro detalhado
        if current_app.config.get('DEBUG', False) or os.environ.get('FLASK_ENV') == 'development':
            error_template = f"""
            <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; margin: 20px; border-radius: 5px; font-family: Arial, sans-serif;">
                <h3>🚨 Erro ao Criar Serviço</h3>
                <p><strong>Erro:</strong> {str(e)}</p>
                <details>
                    <summary style="cursor: pointer; margin: 10px 0;">📋 Ver Traceback Completo</summary>
                    <pre style="background: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; overflow-x: auto; font-family: monospace;">{error_trace}</pre>
                </details>
                <hr>
                <p><strong>Dados do Formulário:</strong></p>
                <ul>
                    <li>Nome: {request.form.get('nome', 'N/A')}</li>
                    <li>Descrição: {request.form.get('descricao', 'N/A')}</li>
                    <li>Categoria: {request.form.get('categoria', 'N/A')}</li>
                </ul>
                <a href="/servicos" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 3px;">← Voltar aos Serviços</a>
            </div>
            """
            return render_template_string(error_template), 500
        else:
            flash(f'Erro ao criar serviço. Detalhes registrados nos logs.', 'error')
            return redirect(url_for('servicos_crud.index'))

@servicos_crud_bp.route('/<int:servico_id>/editar')
def editar_servico(servico_id):
    """Exibe formulário para editar serviço"""
    try:
        admin_id = get_admin_id()
        logger.info(f"✏️ Editando serviço {servico_id} para admin_id={admin_id}")
        
        # Buscar serviço
        servico = Servico.query.filter_by(
            id=servico_id,
            admin_id=admin_id
        ).first()
        
        if not servico:
            flash('Serviço não encontrado', 'error')
            return redirect(url_for('servicos_crud.index'))
        
        # Buscar subatividades do serviço
        subatividades = SubatividadeMestre.query.filter_by(
            servico_id=servico_id,
            admin_id=admin_id,
            ativo=True
        ).order_by(SubatividadeMestre.ordem_padrao).all()
        
        # Importar sistema de categorias
        try:
            from categoria_servicos import obter_categorias_disponiveis
            categorias = obter_categorias_disponiveis(admin_id)
        except ImportError:
            # Fallback se módulo não estiver disponível
            categorias = [
                'Estrutural',
                'Soldagem', 
                'Pintura',
                'Instalação',
                'Acabamento',
                'Manutenção',
                'Outros'
            ]
        
        logger.info(f"✅ Serviço carregado: {servico.nome} com {len(subatividades)} subatividades")
        
        return render_template('servicos/editar.html',
                             servico=servico,
                             subatividades=subatividades,
                             categorias=categorias)
        
    except Exception as e:
        logger.error(f"❌ Erro ao editar serviço: {str(e)}")
        flash(f'Erro ao editar serviço: {str(e)}', 'error')
        return redirect(url_for('servicos_crud.index'))

# ================================
# ROTAS DE AÇÃO (POST)
# ================================

@servicos_crud_bp.route('/<int:servico_id>/atualizar', methods=['POST'])
def atualizar_servico(servico_id):
    """Atualiza serviço existente e suas subatividades"""
    try:
        admin_id = get_admin_id()
        
        # Buscar serviço
        servico = Servico.query.filter_by(
            id=servico_id,
            admin_id=admin_id
        ).first()
        
        if not servico:
            flash('Serviço não encontrado', 'error')
            return redirect(url_for('servicos_crud.index'))
        
        # Atualizar dados básicos
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        categoria = request.form.get('categoria', '').strip()
        
        if not nome:
            flash('Nome do serviço é obrigatório', 'error')
            return redirect(url_for('servicos_crud.editar_servico', servico_id=servico_id))
        
        logger.info(f"🔄 Atualizando serviço {servico_id}: {nome}")
        
        servico.nome = nome
        servico.descricao = descricao
        servico.categoria = categoria
        servico.updated_at = datetime.utcnow()
        
        # Atualizar subatividades
        # Primeiro, desativar todas as existentes
        SubatividadeMestre.query.filter_by(
            servico_id=servico_id,
            admin_id=admin_id
        ).update({'ativo': False})
        
        # Processar subatividades do formulário
        subatividades_nomes = request.form.getlist('subatividade_nome[]')
        subatividades_descricoes = request.form.getlist('subatividade_descricao[]')
        subatividades_ids = request.form.getlist('subatividade_id[]')
        
        subatividades_salvas = 0
        for i, nome_sub in enumerate(subatividades_nomes):
            if nome_sub.strip():
                descricao_sub = ''
                if i < len(subatividades_descricoes):
                    descricao_sub = subatividades_descricoes[i].strip()
                
                # Verificar se é atualização ou criação
                subatividade_id = None
                if i < len(subatividades_ids) and subatividades_ids[i]:
                    subatividade_id = int(subatividades_ids[i])
                
                if subatividade_id:
                    # Atualizar existente
                    subatividade = SubatividadeMestre.query.get(subatividade_id)
                    if subatividade and subatividade.admin_id == admin_id:
                        subatividade.nome = nome_sub.strip()
                        subatividade.descricao = descricao_sub
                        subatividade.ordem_padrao = i + 1
                        subatividade.ativo = True
                        subatividade.updated_at = datetime.utcnow()
                        logger.info(f"  🔄 Subatividade atualizada: {nome_sub.strip()}")
                else:
                    # Criar nova
                    subatividade = SubatividadeMestre(
                        servico_id=servico_id,
                        nome=nome_sub.strip(),
                        descricao=descricao_sub,
                        ordem_padrao=i + 1,
                        obrigatoria=True,
                        admin_id=admin_id,
                        ativo=True,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(subatividade)
                    logger.info(f"  ➕ Subatividade nova: {nome_sub.strip()}")
                
                subatividades_salvas += 1
        
        db.session.commit()
        
        logger.info(f"✅ Serviço atualizado: {nome} com {subatividades_salvas} subatividades")
        flash(f'Serviço "{nome}" atualizado com sucesso! ({subatividades_salvas} subatividades)', 'success')
        
        return redirect(url_for('servicos_crud.index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao atualizar serviço: {str(e)}")
        flash(f'Erro ao atualizar serviço: {str(e)}', 'error')
        return redirect(url_for('servicos_crud.editar_servico', servico_id=servico_id))

@servicos_crud_bp.route('/<int:servico_id>/excluir', methods=['POST', 'DELETE', 'GET'])
def excluir_servico(servico_id):
    """Exclui serviço (soft delete) - aceita GET, POST e DELETE"""
    try:
        admin_id = get_admin_id()
        
        # Para GET, mostrar confirmação
        if request.method == 'GET':
            # Buscar serviço para confirmação
            servico = Servico.query.filter_by(
                id=servico_id,
                admin_id=admin_id
            ).first()
            
            if not servico:
                flash('Serviço não encontrado', 'error')
                return redirect(url_for('servicos_crud.index'))
            
            # Retornar página de confirmação
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Confirmar Exclusão</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body>
                <div class="container mt-5">
                    <div class="card">
                        <div class="card-header bg-danger text-white">
                            <h3>⚠️ Confirmar Exclusão</h3>
                        </div>
                        <div class="card-body">
                            <p>Tem certeza que deseja excluir o serviço:</p>
                            <h4>"{{ servico.nome }}"</h4>
                            <p><strong>Categoria:</strong> {{ servico.categoria }}</p>
                            <p><strong>Descrição:</strong> {{ servico.descricao }}</p>
                            
                            <div class="d-flex gap-2 mt-4">
                                <form method="POST" action="{{ url_for('servicos_crud.excluir_servico', servico_id=servico.id) }}">
                                    <button type="submit" class="btn btn-danger">
                                        🗑️ Sim, Excluir
                                    </button>
                                </form>
                                <a href="{{ url_for('servicos_crud.index') }}" class="btn btn-secondary">
                                    ↩️ Cancelar
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """, servico=servico)
        
        # Para POST e DELETE, executar exclusão
        # Buscar serviço
        servico = Servico.query.filter_by(
            id=servico_id,
            admin_id=admin_id
        ).first()
        
        if not servico:
            flash('Serviço não encontrado', 'error')
            return redirect(url_for('servicos_crud.index'))
        
        logger.info(f"🗑️ Excluindo serviço {servico_id}: {servico.nome}")
        
        # Soft delete - desativar serviço e subatividades
        servico.ativo = False
        servico.updated_at = datetime.utcnow()
        
        # Desativar todas as subatividades
        SubatividadeMestre.query.filter_by(
            servico_id=servico_id,
            admin_id=admin_id
        ).update({'ativo': False, 'updated_at': datetime.utcnow()})
        
        db.session.commit()
        
        logger.info(f"✅ Serviço excluído: {servico.nome}")
        flash(f'Serviço "{servico.nome}" excluído com sucesso!', 'success')
        
        # Resposta diferente para diferentes métodos
        if request.method == 'DELETE':
            return jsonify({
                'success': True,
                'message': f'Serviço "{servico.nome}" excluído com sucesso!'
            })
        else:
            return redirect(url_for('servicos_crud.index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao excluir serviço: {str(e)}")
        flash(f'Erro ao excluir serviço: {str(e)}', 'error')
        
        if request.method == 'DELETE':
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        else:
            return redirect(url_for('servicos_crud.index'))

# ================================
# API ENDPOINTS
# ================================

@servicos_crud_bp.route('/api/servicos')
def api_servicos():
    """API para buscar serviços com subatividades"""
    try:
        admin_id = get_admin_id()
        
        # Buscar serviços ativos
        servicos = Servico.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Servico.nome).all()
        
        servicos_data = []
        for servico in servicos:
            subatividades = SubatividadeMestre.query.filter_by(
                servico_id=servico.id,
                admin_id=admin_id,
                ativo=True
            ).order_by(SubatividadeMestre.ordem_padrao).all()
            
            servicos_data.append({
                'id': servico.id,
                'nome': servico.nome,
                'descricao': servico.descricao,
                'categoria': servico.categoria,
                'subatividades': [sub.to_dict() for sub in subatividades]
            })
        
        return jsonify({
            'success': True,
            'servicos': servicos_data,
            'total': len(servicos_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na API de serviços: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'servicos': []
        }), 500

@servicos_crud_bp.route('/api/obra/<int:obra_id>/servicos')
def api_servicos_por_obra(obra_id):
    """API para buscar serviços vinculados a uma obra específica"""
    try:
        admin_id = get_admin_id()
        
        # Buscar serviços da obra (através da tabela de vínculo)
        from models import ServicoObra
        
        servicos_obra = db.session.query(Servico, ServicoObra).join(
            ServicoObra, Servico.id == ServicoObra.servico_id
        ).filter(
            ServicoObra.obra_id == obra_id,
            Servico.admin_id == admin_id,
            Servico.ativo == True,
            ServicoObra.ativo == True
        ).order_by(Servico.nome).all()
        
        servicos_data = []
        for servico, servico_obra in servicos_obra:
            subatividades = SubatividadeMestre.query.filter_by(
                servico_id=servico.id,
                admin_id=admin_id,
                ativo=True
            ).order_by(SubatividadeMestre.ordem_padrao).all()
            
            servicos_data.append({
                'id': servico.id,
                'nome': servico.nome,
                'descricao': servico.descricao,
                'categoria': servico.categoria,
                'subatividades': [sub.to_dict() for sub in subatividades]
            })
        
        logger.info(f"📋 API: {len(servicos_data)} serviços encontrados para obra {obra_id}")
        
        return jsonify({
            'success': True,
            'obra_id': obra_id,
            'servicos': servicos_data,
            'total': len(servicos_data),
            'total_subatividades': sum(len(s['subatividades']) for s in servicos_data)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na API de serviços por obra: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'servicos': []
        }), 500

@servicos_crud_bp.route('/importar-excel', methods=['POST'])
def importar_excel():
    """Importar serviços via Excel"""
    try:
        admin_id = get_admin_id()
        dados = request.get_json()
        
        if not dados or 'servicos' not in dados:
            return jsonify({
                'success': False,
                'error': 'Dados de serviços não fornecidos'
            }), 400
        
        servicos_dados = dados['servicos']
        importados = 0
        duplicados = 0
        
        logger.info(f"🔄 Iniciando importação de {len(servicos_dados)} serviços para admin_id={admin_id}")
        
        for servico_data in servicos_dados:
            nome_servico = servico_data.get('nome', '').strip()
            subatividades = servico_data.get('subatividades', [])
            
            if not nome_servico:
                continue
            
            # Verificar se serviço já existe
            servico_existente = Servico.query.filter_by(
                nome=nome_servico,
                admin_id=admin_id
            ).first()
            
            if servico_existente:
                duplicados += 1
                logger.warning(f"⚠️ Serviço '{nome_servico}' já existe, ignorando")
                continue
            
            # Criar novo serviço
            novo_servico = Servico(
                nome=nome_servico,
                descricao=f'Importado via Excel - {len(subatividades)} subatividades',
                categoria='Importado',
                admin_id=admin_id,
                ativo=True,
                criado_em=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(novo_servico)
            db.session.flush()  # Para obter o ID
            
            # Adicionar subatividades usando SubatividadeMestre
            for ordem, nome_sub in enumerate(subatividades, 1):
                if nome_sub.strip():
                    subatividade = SubatividadeMestre(
                        nome=nome_sub.strip(),
                        servico_id=novo_servico.id,
                        ordem_padrao=ordem,
                        admin_id=admin_id,
                        ativo=True
                    )
                    db.session.add(subatividade)
            
            importados += 1
            logger.info(f"✅ Serviço '{nome_servico}' importado com {len(subatividades)} subatividades")
        
        db.session.commit()
        
        logger.info(f"🎯 Importação concluída: {importados} importados, {duplicados} duplicados")
        
        return jsonify({
            'success': True,
            'message': 'Importação concluída com sucesso',
            'importados': importados,
            'duplicados': duplicados,
            'total_processados': len(servicos_dados)
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro na importação Excel: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro na importação: {str(e)}'
        }), 500