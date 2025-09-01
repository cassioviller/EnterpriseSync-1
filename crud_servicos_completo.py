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

# Importar sistema de erro detalhado
try:
    from utils.error_handler import handle_detailed_error, log_sql_error
except ImportError:
    # Fallback se não conseguir importar
    def handle_detailed_error(exception, context="Sistema", fallback_url="main.dashboard"):
        logger.error(f"❌ {context}: {str(exception)}")
        flash(f'Erro no {context.lower()}', 'error')
        return redirect(url_for(fallback_url))
    
    def log_sql_error(exception, query_context=""):
        logger.error(f"🚨 ERRO SQL: {str(exception)}")

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
        
        # Buscar serviços ativos
        servicos = Servico.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).order_by(Servico.nome).all()
        
        # Para cada serviço, buscar suas subatividades
        for servico in servicos:
            subatividades = SubatividadeMestre.query.filter_by(
                servico_id=servico.id,
                admin_id=admin_id,
                ativo=True
            ).order_by(SubatividadeMestre.ordem_padrao).all()
            
            # Adicionar subatividades ao objeto serviço
            servico.subatividades = subatividades
        
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
        
        return render_template('servicos/index_novo.html',
                             servicos=servicos,
                             estatisticas=estatisticas,
)
        
    except Exception as e:
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
        
        # Categorias disponíveis (fixas)
        categorias = [
            'Estrutural',
            'Soldagem',
            'Pintura',
            'Instalação',
            'Acabamento',
            'Manutenção',
            'Outros'
        ]
        
        return render_template('servicos/novo.html', categorias=categorias)
        
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
        
        # Categorias disponíveis
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

@servicos_crud_bp.route('/<int:servico_id>/excluir', methods=['POST'])
def excluir_servico(servico_id):
    """Exclui serviço (soft delete)"""
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
        
        return redirect(url_for('servicos_crud.index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao excluir serviço: {str(e)}")
        flash(f'Erro ao excluir serviço: {str(e)}', 'error')
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