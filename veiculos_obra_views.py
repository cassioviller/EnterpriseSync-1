"""
SISTEMA AVANÇADO DE INTEGRAÇÃO VEÍCULOS-OBRAS - SIGE v8.0
Views para funcionalidades completas de alocação, controle de uso e relatórios
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_, text
from sqlalchemy.exc import IntegrityError
import os
import json
from io import BytesIO
import csv

# Importar modelos
from models import (
    db, Veiculo, AlocacaoVeiculo, EquipeVeiculo, TransferenciaVeiculo,
    UsoVeiculo, CustoVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required, funcionario_required

# Criação do Blueprint
veiculos_obra_bp = Blueprint('veiculos_obra', __name__, url_prefix='/veiculos-obra')

# ===== UTILITÁRIOS DE APOIO =====

def get_admin_id():
    """Obtém admin_id do usuário atual com tratamento robusto"""
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario.value == 'admin':
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return current_user.id

def safe_db_operation(operation, default_value=None, error_message="Erro na operação"):
    """Executa operação no banco com tratamento seguro"""
    try:
        return operation()
    except Exception as e:
        print(f"ERRO DB: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        flash(f"{error_message}: {str(e)}", 'danger')
        return default_value

# ===== DASHBOARD PRINCIPAL INTEGRADO =====

@veiculos_obra_bp.route('/dashboard')
@login_required
@admin_required
def dashboard_integrado():
    """Dashboard principal da integração veículos-obras"""
    admin_id = get_admin_id()
    
    try:
        # Dados básicos para o dashboard
        veiculos_total = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).count()
        obras_ativas = Obra.query.filter_by(admin_id=admin_id, ativo=True).count()
        alocacoes_ativas = AlocacaoVeiculo.query.filter_by(
            admin_id=admin_id, 
            ativo=True
        ).filter(AlocacaoVeiculo.data_fim.is_(None)).count()
        
        # Veículos por status
        veiculos_disponivel = Veiculo.query.filter_by(
            admin_id=admin_id, ativo=True, status='Disponível'
        ).count()
        veiculos_alocados = db.session.query(func.count(Veiculo.id)).join(AlocacaoVeiculo).filter(
            Veiculo.admin_id == admin_id,
            Veiculo.ativo == True,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).scalar()
        veiculos_manutencao = Veiculo.query.filter_by(
            admin_id=admin_id, ativo=True, status='Manutenção'
        ).count()
        
        # Custos do mês atual
        mes_atual = date.today().replace(day=1)
        proximo_mes = (mes_atual + timedelta(days=32)).replace(day=1)
        
        custos_mes_atual = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.admin_id == admin_id,
            CustoVeiculo.data_custo >= mes_atual,
            CustoVeiculo.data_custo < proximo_mes
        ).scalar() or 0
        
        # Obras com mais veículos
        obras_veiculos = db.session.query(
            Obra.nome,
            func.count(AlocacaoVeiculo.id).label('total_veiculos')
        ).join(AlocacaoVeiculo).filter(
            Obra.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None)
        ).group_by(Obra.nome).order_by(desc('total_veiculos')).limit(5).all()
        
        # Últimas alocações
        ultimas_alocacoes = AlocacaoVeiculo.query.filter_by(
            admin_id=admin_id, ativo=True
        ).order_by(desc(AlocacaoVeiculo.created_at)).limit(10).all()
        
        # Alertas importantes
        alertas = []
        
        # Verificar veículos com alocação vencendo
        alocacoes_vencendo = AlocacaoVeiculo.query.filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None),
            AlocacaoVeiculo.data_prevista_retorno <= date.today() + timedelta(days=3),
            AlocacaoVeiculo.data_prevista_retorno >= date.today()
        ).all()
        
        for alocacao in alocacoes_vencendo:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Alocação Vencendo',
                'mensagem': f'Veículo {alocacao.veiculo.placa} deve retornar da obra {alocacao.obra.nome} em {alocacao.data_prevista_retorno.strftime("%d/%m/%Y")}'
            })
        
        # Verificar alocações atrasadas
        alocacoes_atrasadas = AlocacaoVeiculo.query.filter(
            AlocacaoVeiculo.admin_id == admin_id,
            AlocacaoVeiculo.ativo == True,
            AlocacaoVeiculo.data_fim.is_(None),
            AlocacaoVeiculo.data_prevista_retorno < date.today()
        ).all()
        
        for alocacao in alocacoes_atrasadas:
            alertas.append({
                'tipo': 'danger',
                'titulo': 'Alocação Atrasada',
                'mensagem': f'Veículo {alocacao.veiculo.placa} está atrasado na obra {alocacao.obra.nome} desde {alocacao.data_prevista_retorno.strftime("%d/%m/%Y")}'
            })
        
        dados_dashboard = {
            'veiculos_total': veiculos_total,
            'obras_ativas': obras_ativas,
            'alocacoes_ativas': alocacoes_ativas,
            'veiculos_disponivel': veiculos_disponivel,
            'veiculos_alocados': veiculos_alocados,
            'veiculos_manutencao': veiculos_manutencao,
            'custos_mes_atual': custos_mes_atual,
            'obras_veiculos': obras_veiculos,
            'ultimas_alocacoes': ultimas_alocacoes,
            'alertas': alertas
        }
        
        return render_template('veiculos_obra/dashboard.html', **dados_dashboard)
        
    except Exception as e:
        print(f"Erro no dashboard integrado: {e}")
        flash('Erro ao carregar dashboard', 'danger')
        return redirect(url_for('main.dashboard'))

# ===== ALOCAÇÃO DE VEÍCULOS =====

@veiculos_obra_bp.route('/alocacoes')
@login_required
@admin_required
def listar_alocacoes():
    """Lista todas as alocações com filtros avançados"""
    admin_id = get_admin_id()
    
    # Parâmetros de filtro
    filtro_status = request.args.get('status', 'todas')
    filtro_obra = request.args.get('obra_id', type=int)
    filtro_veiculo = request.args.get('veiculo_id', type=int)
    filtro_data_inicio = request.args.get('data_inicio')
    filtro_data_fim = request.args.get('data_fim')
    
    # Query base
    query = AlocacaoVeiculo.query.filter_by(admin_id=admin_id, ativo=True)
    
    # Aplicar filtros
    if filtro_status == 'ativas':
        query = query.filter(AlocacaoVeiculo.data_fim.is_(None))
    elif filtro_status == 'finalizadas':
        query = query.filter(AlocacaoVeiculo.data_fim.isnot(None))
    elif filtro_status == 'atrasadas':
        query = query.filter(
            AlocacaoVeiculo.data_fim.is_(None),
            AlocacaoVeiculo.data_prevista_retorno < date.today()
        )
    
    if filtro_obra:
        query = query.filter_by(obra_id=filtro_obra)
    
    if filtro_veiculo:
        query = query.filter_by(veiculo_id=filtro_veiculo)
    
    if filtro_data_inicio:
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date()
        query = query.filter(AlocacaoVeiculo.data_inicio >= data_inicio)
    
    if filtro_data_fim:
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date()
        query = query.filter(AlocacaoVeiculo.data_inicio <= data_fim)
    
    # Ordenar e paginar
    alocacoes = query.order_by(desc(AlocacaoVeiculo.created_at)).all()
    
    # Dados para os filtros
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template('veiculos_obra/alocacoes/lista.html',
                         alocacoes=alocacoes, obras=obras, veiculos=veiculos)

@veiculos_obra_bp.route('/alocar', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_alocacao():
    """Criar nova alocação de veículo para obra"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            # Dados do formulário
            veiculo_id = request.form.get('veiculo_id', type=int)
            obra_id = request.form.get('obra_id', type=int)
            responsavel_id = request.form.get('responsavel_id', type=int)
            data_prevista_retorno = request.form.get('data_prevista_retorno')
            proposito = request.form.get('proposito')
            prioridade = request.form.get('prioridade', type=int, default=3)
            observacoes = request.form.get('observacoes_inicio', '')
            
            # Validações básicas
            if not veiculo_id or not obra_id or not responsavel_id or not proposito:
                flash('Todos os campos obrigatórios devem ser preenchidos', 'danger')
                return redirect(url_for('veiculos_obra.nova_alocacao'))
            
            # Buscar entidades
            veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=admin_id, ativo=True).first()
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id, ativo=True).first()
            responsavel = Funcionario.query.filter_by(id=responsavel_id, admin_id=admin_id, ativo=True).first()
            
            if not veiculo or not obra or not responsavel:
                flash('Dados inválidos selecionados', 'danger')
                return redirect(url_for('veiculos_obra.nova_alocacao'))
            
            # Verificar disponibilidade do veículo
            pode_alocar, motivo = veiculo.pode_ser_alocado()
            if not pode_alocar:
                flash(f'Não é possível alocar o veículo: {motivo}', 'danger')
                return redirect(url_for('veiculos_obra.nova_alocacao'))
            
            # Criar alocação
            alocacao = AlocacaoVeiculo(
                veiculo_id=veiculo_id,
                obra_id=obra_id,
                responsavel_id=responsavel_id,
                autorizado_por_id=current_user.id,
                km_inicial=veiculo.km_atual or 0,
                proposito=proposito,
                prioridade=prioridade,
                observacoes_inicio=observacoes,
                admin_id=admin_id
            )
            
            # Data prevista de retorno
            if data_prevista_retorno:
                alocacao.data_prevista_retorno = datetime.strptime(data_prevista_retorno, '%Y-%m-%d').date()
            
            # Validar alocação
            errors = alocacao.validar_alocacao()
            if errors:
                for error in errors:
                    flash(error, 'danger')
                return redirect(url_for('veiculos_obra.nova_alocacao'))
            
            # Salvar no banco
            db.session.add(alocacao)
            
            # Atualizar status do veículo
            veiculo.status = 'Em uso'
            
            db.session.commit()
            
            flash(f'Veículo {veiculo.placa} alocado com sucesso para a obra {obra.nome}', 'success')
            return redirect(url_for('veiculos_obra.detalhes_alocacao', id=alocacao.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar alocação: {e}")
            flash('Erro ao criar alocação', 'danger')
            return redirect(url_for('veiculos_obra.nova_alocacao'))
    
    # GET - exibir formulário
    veiculos_disponiveis = Veiculo.query.filter_by(
        admin_id=admin_id, ativo=True, status='Disponível'
    ).all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template('veiculos_obra/alocacoes/nova.html',
                         veiculos=veiculos_disponiveis, obras=obras, funcionarios=funcionarios)

@veiculos_obra_bp.route('/alocacao/<int:id>')
@login_required
@admin_required
def detalhes_alocacao(id):
    """Detalhes completos de uma alocação"""
    admin_id = get_admin_id()
    
    alocacao = AlocacaoVeiculo.query.filter_by(
        id=id, admin_id=admin_id, ativo=True
    ).first_or_404()
    
    # Buscar equipe autorizada
    equipe = EquipeVeiculo.query.filter_by(alocacao_id=id).all()
    
    # Buscar custos do período
    custos = CustoVeiculo.query.filter(
        CustoVeiculo.veiculo_id == alocacao.veiculo_id,
        CustoVeiculo.obra_id == alocacao.obra_id,
        CustoVeiculo.data_custo >= alocacao.data_inicio,
        CustoVeiculo.data_custo <= (alocacao.data_fim or date.today())
    ).order_by(desc(CustoVeiculo.data_custo)).all()
    
    # Buscar usos do período
    usos = UsoVeiculo.query.filter(
        UsoVeiculo.veiculo_id == alocacao.veiculo_id,
        UsoVeiculo.obra_id == alocacao.obra_id,
        UsoVeiculo.data_uso >= alocacao.data_inicio,
        UsoVeiculo.data_uso <= (alocacao.data_fim or date.today())
    ).order_by(desc(UsoVeiculo.data_uso)).all()
    
    # Buscar transferências
    transferencias = TransferenciaVeiculo.query.filter_by(
        alocacao_origem_id=id
    ).order_by(desc(TransferenciaVeiculo.created_at)).all()
    
    return render_template('veiculos_obra/alocacoes/detalhes.html',
                         alocacao=alocacao, equipe=equipe, custos=custos, 
                         usos=usos, transferencias=transferencias)

@veiculos_obra_bp.route('/alocacao/<int:id>/finalizar', methods=['POST'])
@login_required
@admin_required
def finalizar_alocacao(id):
    """Finalizar uma alocação ativa"""
    admin_id = get_admin_id()
    
    alocacao = AlocacaoVeiculo.query.filter_by(
        id=id, admin_id=admin_id, ativo=True
    ).first_or_404()
    
    if alocacao.data_fim:
        flash('Esta alocação já foi finalizada', 'warning')
        return redirect(url_for('veiculos_obra.detalhes_alocacao', id=id))
    
    try:
        km_final = request.form.get('km_final', type=int)
        observacoes = request.form.get('observacoes_fim', '')
        condicoes_veiculo = request.form.get('condicoes_veiculo_fim', '')
        
        # Validar KM final
        if km_final and km_final < alocacao.km_inicial:
            flash('KM final não pode ser menor que KM inicial', 'danger')
            return redirect(url_for('veiculos_obra.detalhes_alocacao', id=id))
        
        # Finalizar alocação
        alocacao.finalizar_alocacao(
            km_final=km_final,
            observacoes=observacoes,
            condicoes_veiculo=condicoes_veiculo
        )
        
        # Atualizar KM do veículo se fornecido
        if km_final:
            alocacao.veiculo.km_atual = km_final
        
        db.session.commit()
        
        flash(f'Alocação finalizada com sucesso. Veículo {alocacao.veiculo.placa} está disponível novamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao finalizar alocação: {e}")
        flash('Erro ao finalizar alocação', 'danger')
    
    return redirect(url_for('veiculos_obra.detalhes_alocacao', id=id))

# ===== GESTÃO DE EQUIPES =====

@veiculos_obra_bp.route('/alocacao/<int:id>/equipe', methods=['GET', 'POST'])
@login_required
@admin_required
def gerenciar_equipe(id):
    """Gerenciar equipe autorizada para um veículo"""
    admin_id = get_admin_id()
    
    alocacao = AlocacaoVeiculo.query.filter_by(
        id=id, admin_id=admin_id, ativo=True
    ).first_or_404()
    
    if request.method == 'POST':
        try:
            funcionario_id = request.form.get('funcionario_id', type=int)
            pode_dirigir = request.form.get('pode_dirigir') == 'on'
            pode_abastecer = request.form.get('pode_abastecer') == 'on'
            pode_levar_manutencao = request.form.get('pode_levar_manutencao') == 'on'
            eh_responsavel_principal = request.form.get('eh_responsavel_principal') == 'on'
            observacoes = request.form.get('observacoes', '')
            
            # Verificar se funcionário existe
            funcionario = Funcionario.query.filter_by(
                id=funcionario_id, admin_id=admin_id, ativo=True
            ).first()
            
            if not funcionario:
                flash('Funcionário inválido', 'danger')
                return redirect(url_for('veiculos_obra.gerenciar_equipe', id=id))
            
            # Verificar se já existe na equipe
            equipe_existente = EquipeVeiculo.query.filter_by(
                alocacao_id=id, funcionario_id=funcionario_id
            ).first()
            
            if equipe_existente:
                flash('Funcionário já está na equipe deste veículo', 'warning')
                return redirect(url_for('veiculos_obra.gerenciar_equipe', id=id))
            
            # Se marcado como responsável principal, remover de outros
            if eh_responsavel_principal:
                EquipeVeiculo.query.filter_by(
                    alocacao_id=id, eh_responsavel_principal=True
                ).update({'eh_responsavel_principal': False})
            
            # Criar nova autorização
            equipe = EquipeVeiculo(
                alocacao_id=id,
                funcionario_id=funcionario_id,
                pode_dirigir=pode_dirigir,
                pode_abastecer=pode_abastecer,
                pode_levar_manutencao=pode_levar_manutencao,
                eh_responsavel_principal=eh_responsavel_principal,
                observacoes=observacoes
            )
            
            db.session.add(equipe)
            db.session.commit()
            
            flash(f'Funcionário {funcionario.nome} adicionado à equipe com sucesso', 'success')
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao adicionar funcionário à equipe: {e}")
            flash('Erro ao adicionar funcionário à equipe', 'danger')
        
        return redirect(url_for('veiculos_obra.gerenciar_equipe', id=id))
    
    # GET - exibir formulário
    equipe_atual = EquipeVeiculo.query.filter_by(alocacao_id=id).all()
    funcionarios_obra = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    # Remover funcionários que já estão na equipe
    funcionarios_ids_equipe = [e.funcionario_id for e in equipe_atual]
    funcionarios_disponiveis = [f for f in funcionarios_obra if f.id not in funcionarios_ids_equipe]
    
    return render_template('veiculos_obra/equipe/gerenciar.html',
                         alocacao=alocacao, equipe_atual=equipe_atual, 
                         funcionarios_disponiveis=funcionarios_disponiveis)

@veiculos_obra_bp.route('/equipe/<int:id>/remover', methods=['POST'])
@login_required
@admin_required
def remover_equipe(id):
    """Remover funcionário da equipe do veículo"""
    admin_id = get_admin_id()
    
    equipe = EquipeVeiculo.query.filter_by(id=id).first_or_404()
    
    # Verificar permissão
    if equipe.alocacao.admin_id != admin_id:
        flash('Sem permissão para esta operação', 'danger')
        return redirect(url_for('veiculos_obra.listar_alocacoes'))
    
    try:
        alocacao_id = equipe.alocacao_id
        funcionario_nome = equipe.funcionario.nome
        
        db.session.delete(equipe)
        db.session.commit()
        
        flash(f'Funcionário {funcionario_nome} removido da equipe', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover funcionário da equipe: {e}")
        flash('Erro ao remover funcionário da equipe', 'danger')
    
    return redirect(url_for('veiculos_obra.gerenciar_equipe', id=alocacao_id))

# ===== CONTROLE DE USO DIÁRIO =====

@veiculos_obra_bp.route('/uso/novo/<int:alocacao_id>', methods=['GET', 'POST'])
@login_required
@funcionario_required
def novo_uso_obra(alocacao_id):
    """Registrar novo uso de veículo vinculado à obra específica"""
    admin_id = get_admin_id()
    
    # Buscar alocação ativa
    alocacao = AlocacaoVeiculo.query.filter_by(
        id=alocacao_id, admin_id=admin_id, ativo=True
    ).filter(AlocacaoVeiculo.data_fim.is_(None)).first_or_404()
    
    # Verificar se o usuário pode usar este veículo
    if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario.value != 'admin':
        funcionario_atual = Funcionario.query.filter_by(
            admin_id=admin_id, email=current_user.email
        ).first()
        
        if funcionario_atual:
            equipe_autorizada = EquipeVeiculo.query.filter_by(
                alocacao_id=alocacao_id, funcionario_id=funcionario_atual.id
            ).first()
            
            if not equipe_autorizada:
                flash('Você não está autorizado a usar este veículo', 'danger')
                return redirect(url_for('veiculos_obra.dashboard_integrado'))
    
    if request.method == 'POST':
        try:
            # Dados do formulário
            data_uso = request.form.get('data_uso')
            km_inicial = request.form.get('km_inicial', type=int)
            km_final = request.form.get('km_final', type=int)
            horario_saida = request.form.get('horario_saida')
            horario_chegada = request.form.get('horario_chegada')
            destino = request.form.get('destino')
            finalidade = request.form.get('finalidade')
            observacoes = request.form.get('observacoes', '')
            
            # Validações
            if not all([data_uso, km_inicial, km_final, horario_saida, horario_chegada, destino, finalidade]):
                flash('Todos os campos obrigatórios devem ser preenchidos', 'danger')
                return redirect(url_for('veiculos_obra.novo_uso_obra', alocacao_id=alocacao_id))
            
            if km_final <= km_inicial:
                flash('KM final deve ser maior que KM inicial', 'danger')
                return redirect(url_for('veiculos_obra.novo_uso_obra', alocacao_id=alocacao_id))
            
            # Converter datas e horários
            data_uso_obj = datetime.strptime(data_uso, '%Y-%m-%d').date()
            horario_saida_obj = datetime.strptime(horario_saida, '%H:%M').time()
            horario_chegada_obj = datetime.strptime(horario_chegada, '%H:%M').time()
            
            # Determinar funcionário
            funcionario_id = None
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario.value != 'admin':
                funcionario_atual = Funcionario.query.filter_by(
                    admin_id=admin_id, email=current_user.email
                ).first()
                funcionario_id = funcionario_atual.id if funcionario_atual else None
            else:
                funcionario_id = request.form.get('funcionario_id', type=int)
            
            if not funcionario_id:
                flash('Funcionário deve ser especificado', 'danger')
                return redirect(url_for('veiculos_obra.novo_uso_obra', alocacao_id=alocacao_id))
            
            # Criar registro de uso
            uso = UsoVeiculo(
                veiculo_id=alocacao.veiculo_id,
                obra_id=alocacao.obra_id,
                funcionario_id=funcionario_id,
                data_uso=data_uso_obj,
                km_inicial=km_inicial,
                km_final=km_final,
                horario_saida=horario_saida_obj,
                horario_chegada=horario_chegada_obj,
                destino=destino,
                finalidade=finalidade,
                observacoes=observacoes,
                admin_id=admin_id
            )
            
            # Calcular campos automáticos
            uso.calcular_campos_automaticos()
            
            db.session.add(uso)
            
            # Atualizar KM do veículo
            alocacao.veiculo.km_atual = km_final
            
            db.session.commit()
            
            flash('Uso registrado com sucesso', 'success')
            return redirect(url_for('veiculos_obra.detalhes_alocacao', id=alocacao_id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao registrar uso: {e}")
            flash('Erro ao registrar uso', 'danger')
            return redirect(url_for('veiculos_obra.novo_uso_obra', alocacao_id=alocacao_id))
    
    # GET - exibir formulário
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template('veiculos_obra/uso/novo.html',
                         alocacao=alocacao, funcionarios=funcionarios)

# ===== TRANSFERÊNCIAS =====

@veiculos_obra_bp.route('/alocacao/<int:id>/transferir', methods=['GET', 'POST'])
@login_required
@admin_required
def transferir_veiculo(id):
    """Transferir veículo para outra obra"""
    admin_id = get_admin_id()
    
    alocacao = AlocacaoVeiculo.query.filter_by(
        id=id, admin_id=admin_id, ativo=True
    ).first_or_404()
    
    if alocacao.data_fim:
        flash('Não é possível transferir uma alocação já finalizada', 'warning')
        return redirect(url_for('veiculos_obra.detalhes_alocacao', id=id))
    
    if request.method == 'POST':
        try:
            obra_destino_id = request.form.get('obra_destino_id', type=int)
            responsavel_id = request.form.get('responsavel_transferencia_id', type=int)
            motivo = request.form.get('motivo')
            urgencia = request.form.get('urgencia', 'Normal')
            km_saida = request.form.get('km_saida', type=int)
            observacoes = request.form.get('observacoes_saida', '')
            
            # Validações
            if not all([obra_destino_id, responsavel_id, motivo, km_saida]):
                flash('Todos os campos obrigatórios devem ser preenchidos', 'danger')
                return redirect(url_for('veiculos_obra.transferir_veiculo', id=id))
            
            # Verificar se obra destino existe
            obra_destino = Obra.query.filter_by(
                id=obra_destino_id, admin_id=admin_id, ativo=True
            ).first()
            
            if not obra_destino:
                flash('Obra de destino inválida', 'danger')
                return redirect(url_for('veiculos_obra.transferir_veiculo', id=id))
            
            if obra_destino_id == alocacao.obra_id:
                flash('Obra de destino deve ser diferente da atual', 'danger')
                return redirect(url_for('veiculos_obra.transferir_veiculo', id=id))
            
            # Criar transferência
            transferencia = TransferenciaVeiculo(
                alocacao_origem_id=id,
                obra_destino_id=obra_destino_id,
                responsavel_transferencia_id=responsavel_id,
                motivo=motivo,
                urgencia=urgencia,
                km_saida=km_saida,
                observacoes_saida=observacoes,
                admin_id=admin_id
            )
            
            db.session.add(transferencia)
            
            # Atualizar status da alocação
            alocacao.status = 'Transferindo'
            
            db.session.commit()
            
            flash(f'Transferência iniciada para a obra {obra_destino.nome}', 'success')
            return redirect(url_for('veiculos_obra.detalhes_alocacao', id=id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao iniciar transferência: {e}")
            flash('Erro ao iniciar transferência', 'danger')
            return redirect(url_for('veiculos_obra.transferir_veiculo', id=id))
    
    # GET - exibir formulário
    obras_destino = Obra.query.filter(
        Obra.admin_id == admin_id,
        Obra.ativo == True,
        Obra.id != alocacao.obra_id
    ).all()
    
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template('veiculos_obra/transferencias/nova.html',
                         alocacao=alocacao, obras_destino=obras_destino, 
                         funcionarios=funcionarios)

@veiculos_obra_bp.route('/transferencia/<int:id>/confirmar', methods=['POST'])
@login_required
@admin_required
def confirmar_chegada_transferencia(id):
    """Confirmar chegada de veículo transferido"""
    admin_id = get_admin_id()
    
    transferencia = TransferenciaVeiculo.query.filter_by(
        id=id, admin_id=admin_id
    ).first_or_404()
    
    if transferencia.status == 'Chegou':
        flash('Esta transferência já foi confirmada', 'warning')
        return redirect(url_for('veiculos_obra.listar_alocacoes'))
    
    try:
        km_chegada = request.form.get('km_chegada', type=int)
        responsavel_recebimento_id = request.form.get('responsavel_recebimento_id', type=int)
        observacoes = request.form.get('observacoes_chegada', '')
        
        # Validações
        if not km_chegada or not responsavel_recebimento_id:
            flash('KM de chegada e responsável pelo recebimento são obrigatórios', 'danger')
            return redirect(url_for('veiculos_obra.detalhes_alocacao', 
                                  id=transferencia.alocacao_origem_id))
        
        if km_chegada < transferencia.km_saida:
            flash('KM de chegada não pode ser menor que KM de saída', 'danger')
            return redirect(url_for('veiculos_obra.detalhes_alocacao', 
                                  id=transferencia.alocacao_origem_id))
        
        # Confirmar chegada
        nova_alocacao = transferencia.confirmar_chegada(
            km_chegada=km_chegada,
            responsavel_recebimento_id=responsavel_recebimento_id,
            observacoes=observacoes
        )
        
        db.session.commit()
        
        flash(f'Chegada confirmada. Nova alocação criada na obra {transferencia.obra_destino.nome}', 'success')
        return redirect(url_for('veiculos_obra.detalhes_alocacao', id=nova_alocacao.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao confirmar chegada: {e}")
        flash('Erro ao confirmar chegada', 'danger')
        return redirect(url_for('veiculos_obra.listar_alocacoes'))

print("✅ Sistema avançado de integração veículos-obras carregado com sucesso")