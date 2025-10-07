from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Restaurante, AlimentacaoLancamento, Funcionario, Obra
from datetime import datetime
from sqlalchemy import func
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

alimentacao_bp = Blueprint('alimentacao', __name__, url_prefix='/alimentacao')

# ===== HELPER FUNCTION =====
def get_admin_id():
    """Retorna admin_id do usuário atual"""
    if current_user.is_authenticated:
        return current_user.admin_id if current_user.admin_id else current_user.id
    return None

# ===== RESTAURANTES - CRUD COMPLETO =====

@alimentacao_bp.route('/restaurantes')
@login_required
def restaurantes_lista():
    """Lista todos os restaurantes"""
    admin_id = get_admin_id()
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    return render_template('alimentacao/restaurantes_lista.html', restaurantes=restaurantes)

@alimentacao_bp.route('/restaurantes/novo', methods=['GET', 'POST'])
@login_required
def restaurante_novo():
    """Criar novo restaurante"""
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            restaurante = Restaurante(
                nome=request.form['nome'],
                endereco=request.form.get('endereco', ''),
                telefone=request.form.get('telefone', ''),
                admin_id=admin_id
            )
            db.session.add(restaurante)
            db.session.commit()
            flash('Restaurante cadastrado com sucesso!', 'success')
            return redirect(url_for('alimentacao.restaurantes_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar restaurante: {e}")
            flash('Erro ao cadastrar restaurante', 'error')
    
    return render_template('alimentacao/restaurante_novo.html')

@alimentacao_bp.route('/restaurantes/<int:restaurante_id>/editar', methods=['GET', 'POST'])
@login_required
def restaurante_editar(restaurante_id):
    """Editar restaurante"""
    admin_id = get_admin_id()
    restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            restaurante.nome = request.form['nome']
            restaurante.endereco = request.form.get('endereco', '')
            restaurante.telefone = request.form.get('telefone', '')
            db.session.commit()
            flash('Restaurante atualizado com sucesso!', 'success')
            return redirect(url_for('alimentacao.restaurantes_lista'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar restaurante: {e}")
            flash('Erro ao atualizar restaurante', 'error')
    
    return render_template('alimentacao/restaurante_editar.html', restaurante=restaurante)

@alimentacao_bp.route('/restaurantes/<int:restaurante_id>/deletar', methods=['POST'])
@login_required
def restaurante_deletar(restaurante_id):
    """Deletar restaurante"""
    try:
        admin_id = get_admin_id()
        restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first_or_404()
        db.session.delete(restaurante)
        db.session.commit()
        flash('Restaurante excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar restaurante: {e}")
        flash('Erro ao excluir restaurante', 'error')
    
    return redirect(url_for('alimentacao.restaurantes_lista'))

# ===== LANÇAMENTOS - CRUD =====

@alimentacao_bp.route('/')
@login_required
def lancamentos_lista():
    """Lista lançamentos de alimentação"""
    admin_id = get_admin_id()
    lancamentos = AlimentacaoLancamento.query.filter_by(admin_id=admin_id).order_by(AlimentacaoLancamento.data.desc()).all()
    return render_template('alimentacao/lancamentos_lista.html', lancamentos=lancamentos)

@alimentacao_bp.route('/lancamentos/novo', methods=['GET', 'POST'])
@login_required
def lancamento_novo():
    """Criar novo lançamento com rateio"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            admin_id = get_admin_id()
            
            # VALIDAÇÃO TENANT: Verificar restaurante
            restaurante_id = int(request.form['restaurante_id'])
            restaurante = Restaurante.query.filter_by(id=restaurante_id, admin_id=admin_id).first()
            if not restaurante:
                logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar restaurante_id={restaurante_id}")
                flash('Restaurante inválido ou sem permissão', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # VALIDAÇÃO TENANT: Verificar obra
            obra_id = int(request.form['obra_id'])
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra:
                logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar obra_id={obra_id}")
                flash('Obra inválida ou sem permissão', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # VALIDAÇÃO TENANT: Verificar funcionários
            funcionarios_ids = request.form.getlist('funcionarios')
            if not funcionarios_ids:
                flash('Selecione pelo menos um funcionário', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # Validar cada funcionário contra admin_id
            funcionarios_validos = []
            for func_id in funcionarios_ids:
                funcionario = Funcionario.query.filter_by(id=int(func_id), admin_id=admin_id).first()
                if funcionario:
                    funcionarios_validos.append(funcionario)
                else:
                    logger.warning(f"Tentativa de acesso cross-tenant: admin_id={admin_id} tentou acessar funcionario_id={func_id}")
            
            if not funcionarios_validos:
                flash('Nenhum funcionário válido selecionado', 'error')
                return redirect(url_for('alimentacao.lancamento_novo'))
            
            # Criar lançamento (agora seguro)
            lancamento = AlimentacaoLancamento(
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                valor_total=Decimal(request.form['valor_total']),
                descricao=request.form.get('descricao', ''),
                restaurante_id=restaurante.id,  # Usar objeto validado
                obra_id=obra.id,  # Usar objeto validado
                admin_id=admin_id
            )
            db.session.add(lancamento)
            db.session.flush()
            
            # Associar apenas funcionários validados
            for funcionario in funcionarios_validos:
                lancamento.funcionarios.append(funcionario)
            
            db.session.commit()
            flash(f'Lançamento criado! Valor por funcionário: R$ {lancamento.valor_por_funcionario:.2f}', 'success')
            return redirect(url_for('alimentacao.lancamentos_lista'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar lançamento: {e}")
            flash('Erro ao criar lançamento', 'error')
    
    # GET - carregar dados para o formulário
    restaurantes = Restaurante.query.filter_by(admin_id=admin_id).order_by(Restaurante.nome).all()
    obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id).order_by(Funcionario.nome).all()
    
    return render_template('alimentacao/lancamento_novo.html', 
                         restaurantes=restaurantes, 
                         obras=obras, 
                         funcionarios=funcionarios)
