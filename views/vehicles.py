from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, send_file, session, Response
from flask_login import login_required, current_user
from models import db, Usuario, TipoUsuario, Funcionario, Funcao, Departamento, HorarioTrabalho, Obra, RDO, RDOMaoObra, RDOEquipamento, RDOOcorrencia, RDOFoto, AlocacaoEquipe, Servico, ServicoObra, ServicoObraReal, RDOServicoSubatividade, SubatividadeMestre, RegistroPonto, NotificacaoCliente
from auth import admin_required
from utils.tenant import get_tenant_admin_id
from utils import calcular_valor_hora_periodo
from utils.database_diagnostics import capture_db_errors
from views.helpers import safe_db_operation, get_admin_id_robusta, get_admin_id_dinamico
from datetime import datetime, date, timedelta
import calendar
from sqlalchemy import func, desc, or_, and_, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
import os
import json
import logging

from views import main_bp

logger = logging.getLogger(__name__)

try:
    from utils.circuit_breaker import circuit_breaker, pdf_generation_fallback, database_query_fallback
except ImportError:
    def circuit_breaker(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

@main_bp.route('/veiculos/<int:id>/ultima-km')
@login_required
def ultima_km_veiculo(id):
    """Retorna a última quilometragem registrada do veículo"""
    try:
        # [LOCK] SEGURANÇA MULTITENANT: Usar resolver unificado
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado. Usuário não autenticado.'}), 403
        
        from models import Veiculo
        from sqlalchemy import text
        
        # Verificar se o veículo pertence ao usuário
        veiculo = Veiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first_or_404()
        
        # Buscar a última quilometragem registrada (último uso ou km_atual do veículo)
        ultima_km = 0
        
        try:
            # Buscar último uso do veículo ordenado por data
            ultimo_uso = db.session.execute(
                text("""
                    SELECT km_final 
                    FROM uso_veiculo 
                    WHERE veiculo_id = :veiculo_id 
                    AND km_final IS NOT NULL 
                    ORDER BY data_uso DESC, id DESC 
                    LIMIT 1
                """),
                {'veiculo_id': id}
            ).fetchone()
            
            if ultimo_uso and ultimo_uso.km_final:
                ultima_km = ultimo_uso.km_final
            elif veiculo.km_atual:
                ultima_km = veiculo.km_atual
                
        except Exception as e:
            logger.error(f"Erro ao buscar última KM: {str(e)}")
            # Fallback para km_atual do veículo
            ultima_km = veiculo.km_atual or 0
        
        return jsonify({'ultima_km': ultima_km})
        
    except Exception as e:
        logger.error(f"ERRO ÚLTIMA KM VEÍCULO: {str(e)}")
        return jsonify({'error': 'Erro ao carregar última quilometragem', 'ultima_km': 0}), 500

# Rota para calcular KPIs do veículo por período
@main_bp.route('/veiculos/<int:id>/kpis')
@login_required
def kpis_veiculo_periodo(id):
    """Retorna KPIs do veículo filtradas por período"""
    try:
        # [LOCK] SEGURANÇA MULTITENANT: Usar resolver unificado
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado. Usuário não autenticado.'}), 403
        
        from models import Veiculo
        from sqlalchemy import text
        
        # Verificar se o veículo pertence ao usuário
        veiculo = Veiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first_or_404()
        
        # Obter parâmetros de data
        data_inicial = request.args.get('data_inicial')
        data_final = request.args.get('data_final')
        
        # Se não informado, usar mês atual
        if not data_inicial or not data_final:
            hoje = date.today()
            data_inicial = hoje.replace(day=1).strftime('%Y-%m-%d')  # Primeiro dia do mês
            data_final = hoje.strftime('%Y-%m-%d')  # Hoje
        
        # Calcular KPIs do período
        quilometragem_total = 0
        custos_manutencao = 0
        combustivel_gasto = 0
        
        try:
            # Buscar usos no período
            usos_periodo = db.session.execute(
                text("""
                    SELECT km_inicial, km_final 
                    FROM uso_veiculo 
                    WHERE veiculo_id = :veiculo_id 
                    AND data_uso BETWEEN :data_inicial AND :data_final
                    AND km_inicial IS NOT NULL 
                    AND km_final IS NOT NULL
                """),
                {'veiculo_id': id, 'data_inicial': data_inicial, 'data_final': data_final}
            ).fetchall()
            
            # Calcular quilometragem total do período
            for uso in usos_periodo:
                if uso.km_inicial and uso.km_final:
                    quilometragem_total += (uso.km_final - uso.km_inicial)
            
            # Buscar custos no período
            custos_periodo = db.session.execute(
                text("""
                    SELECT tipo_custo, valor 
                    FROM custo_veiculo 
                    WHERE veiculo_id = :veiculo_id 
                    AND data_custo BETWEEN :data_inicial AND :data_final
                """),
                {'veiculo_id': id, 'data_inicial': data_inicial, 'data_final': data_final}
            ).fetchall()
            
            # Calcular custos por tipo
            for custo in custos_periodo:
                if custo.tipo_custo == 'combustivel':
                    combustivel_gasto += custo.valor
                elif custo.tipo_custo in ['manutencao', 'seguro', 'outros']:
                    custos_manutencao += custo.valor
                    
        except Exception as e:
            logger.error(f"Erro ao calcular KPIs: {str(e)}")
        
        kpis = {
            'quilometragem_total': quilometragem_total,
            'custos_manutencao': custos_manutencao,
            'combustivel_gasto': combustivel_gasto,
            'periodo': f"{data_inicial} a {data_final}"
        }
        
        return jsonify(kpis)
        
    except Exception as e:
        logger.error(f"ERRO KPIs VEÍCULO PERÍODO: {str(e)}")
        return jsonify({'error': 'Erro ao calcular KPIs do período'}), 500





# 3. ROTA EXCLUSÃO - /veiculos/<id>/excluir (POST) - REDIRECIONAMENTO
@main_bp.route('/veiculos/<int:id>/excluir', methods=['POST'])
@admin_required
def excluir_veiculo(id):
    """Redireciona para o novo sistema de frota (HTTP 307 preserva POST)"""
    logger.debug(f"[ROUTE] [VEICULOS_EXCLUIR_REDIRECT] Redirecionando para frota.deletar_veiculo({id})")
    return redirect(url_for('frota.deletar_veiculo', id=id), code=307)


# Helper function para processar passageiros por posição
def processar_passageiro_veiculo(passageiro_id, funcionario_id, uso_veiculo_id, admin_id, posicao):
    """
    Processa um passageiro individual do veículo com validações
    Retorna 1 se criado com sucesso, 0 caso contrário
    """
    try:
        passageiro_id = int(passageiro_id)
        
        # Validar se o passageiro não é o mesmo que o funcionário condutor
        if passageiro_id == int(funcionario_id):
            return 0  # Pular funcionário - ele já está registrado como condutor
        
        # Verificar se o funcionário existe e pertence ao mesmo admin
        funcionario_passageiro = Funcionario.query.filter_by(
            id=passageiro_id, 
            admin_id=admin_id, 
            ativo=True
        ).first()
        
        if funcionario_passageiro:
            # CORREÇÃO CRÍTICA: Verificar se já não existe registro (evitar duplicação) COM admin_id
            passageiro_existente = PassageiroVeiculo.query.filter_by(
                uso_veiculo_id=uso_veiculo_id,
                funcionario_id=passageiro_id,
                admin_id=admin_id  # ISOLAMENTO MULTI-TENANT OBRIGATÓRIO
            ).first()
            
            if not passageiro_existente:
                try:
                    passageiro = PassageiroVeiculo(
                        uso_veiculo_id=uso_veiculo_id,
                        funcionario_id=passageiro_id,
                        posicao=posicao,  # Novo campo de posição
                        admin_id=admin_id,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(passageiro)
                    return 1
                except IntegrityError as e:
                    db.session.rollback()
                    logger.error(f"ERRO INTEGRIDADE PASSAGEIRO: {str(e)}")
                    return -1  # Sinalizar erro de integridade
        
        return 0
    except (ValueError, TypeError):
        # ID inválido
        return 0
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"ERRO INTEGRIDADE PASSAGEIRO (Global): {str(e)}")
        return -1
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO INESPERADO PASSAGEIRO: {str(e)}")
        return -1


# 4. ROTA REGISTRO USO - /veiculos/<id>/uso (GET/POST)
# ROTA PARA MODAL DE USO (SEM PARÂMETRO ID NA URL)
@main_bp.route('/veiculos/uso', methods=['POST'])
@login_required  # [LOCK] MUDANÇA: Funcionários podem registrar uso de veículos
def novo_uso_veiculo_lista():
    from forms import UsoVeiculoForm
    from models import Veiculo, UsoVeiculo, Funcionario, Obra
    
    # Obter veiculo_id do form (hidden field)
    veiculo_id = request.form.get('veiculo_id')
    if not veiculo_id:
        flash('Erro: ID do veículo não fornecido.', 'error')
        return redirect(url_for('main.veiculos'))
    
    # [LOCK] SEGURANÇA MULTITENANT: Usar resolver unificado
    tenant_admin_id = get_tenant_admin_id()
    if not tenant_admin_id:
        flash('Acesso negado. Faça login novamente.', 'error')
        return redirect(url_for('auth.login'))
    
    veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first_or_404()
    
    # TRANSAÇÃO ATÔMICA: Flask-SQLAlchemy gerencia transação automaticamente
    try:
        # Validações de negócio críticas
        km_inicial = float(request.form.get('km_inicial', 0))
        km_final = float(request.form.get('km_final', 0))
        
        if km_final and km_inicial:
            if km_final <= km_inicial:
                flash('KM final deve ser maior que KM inicial.', 'error')
                return redirect(url_for('main.veiculos'))
        
        # CRÍTICO: Validação de odômetro
        if km_final and veiculo.km_atual:
            if km_final < veiculo.km_atual:
                flash(f'Erro: KM final não pode ser menor que a quilometragem atual do veículo ({veiculo.km_atual}km).', 'error')
                return redirect(url_for('main.veiculos'))
        
        # Obter dados dos campos do formulário
        funcionario_id = request.form.get('funcionario_id')
        if not funcionario_id:
            flash('Erro: Funcionário é obrigatório.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Processar porcentagem de combustível
        porcentagem_str = request.form.get('porcentagem_combustivel')
        porcentagem_combustivel = None
        if porcentagem_str:
            try:
                porcentagem = int(porcentagem_str)
                if 0 <= porcentagem <= 100:
                    porcentagem_combustivel = porcentagem
                else:
                    flash('Porcentagem de combustível deve estar entre 0 e 100%.', 'warning')
            except (ValueError, TypeError):
                flash('Porcentagem de combustível inválida.', 'warning')
        
        # Criar registro de uso (campos corretos do modelo UsoVeiculo)
        uso = UsoVeiculo(
            veiculo_id=veiculo.id,
            funcionario_id=funcionario_id,  # Campo correto: funcionario_id
            obra_id=request.form.get('obra_id') if request.form.get('obra_id') else None,
            data_uso=datetime.strptime(request.form.get('data_uso'), '%Y-%m-%d').date(),
            hora_saida=datetime.strptime(request.form.get('horario_saida'), '%H:%M').time() if request.form.get('horario_saida') else None,
            hora_retorno=datetime.strptime(request.form.get('horario_chegada'), '%H:%M').time() if request.form.get('horario_chegada') else None,
            km_inicial=km_inicial,
            km_final=km_final,
            km_percorrido=km_final - km_inicial if km_final and km_inicial else 0,
            observacoes=request.form.get('observacoes'),
            admin_id=tenant_admin_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(uso)
        db.session.flush()  # Obter ID do uso para criar passageiros
        
        # Processar passageiros por posição com validações de limite
        passageiros_frente_ids = request.form.getlist('passageiros_frente[]')
        passageiros_tras_ids = request.form.getlist('passageiros_tras[]')
        passageiros_criados = 0
        
        # Validações de limite
        if len(passageiros_frente_ids) > 3:
            flash('Máximo de 3 passageiros permitidos na frente do veículo.', 'error')
            return redirect(url_for('main.veiculos'))
        
        if len(passageiros_tras_ids) > 5:
            flash('Máximo de 5 passageiros permitidos na parte traseira do veículo.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # VALIDAÇÃO CRÍTICA: Contar erros de integridade
        erros_integridade = 0
        
        # Processar passageiros da frente
        if passageiros_frente_ids:
            for passageiro_id in passageiros_frente_ids:
                resultado = processar_passageiro_veiculo(
                    passageiro_id, funcionario_id, uso.id, tenant_admin_id, 'frente'
                )
                if resultado == -1:
                    erros_integridade += 1
                elif resultado == 1:
                    passageiros_criados += 1
        
        # Processar passageiros de trás
        if passageiros_tras_ids:
            for passageiro_id in passageiros_tras_ids:
                resultado = processar_passageiro_veiculo(
                    passageiro_id, funcionario_id, uso.id, tenant_admin_id, 'tras'
                )
                if resultado == -1:
                    erros_integridade += 1
                elif resultado == 1:
                    passageiros_criados += 1
        
        # ROLLBACK SE HOUVER ERROS DE INTEGRIDADE
        if erros_integridade > 0:
            db.session.rollback()
            flash(f'Erro: {erros_integridade} funcionário(s) já estavam registrados como passageiros neste uso. Operação cancelada.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Atualizar KM atual do veículo se fornecido
        if km_final:
            veiculo.km_atual = km_final
            veiculo.updated_at = datetime.utcnow() if hasattr(veiculo, 'updated_at') else None
        
        # COMMIT ATÔMICO - Tudo ou nada
        db.session.commit()
        
        # Mensagem de sucesso com informações sobre passageiros
        if passageiros_criados > 0:
            flash(f'Uso do veículo {veiculo.placa} registrado com sucesso! {passageiros_criados} passageiro(s) adicionado(s).', 'success')
        else:
            flash(f'Uso do veículo {veiculo.placa} registrado com sucesso!', 'success')
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"ERRO INTEGRIDADE USO VEÍCULO: {str(e)}")
        if 'unique constraint' in str(e).lower():
            flash('Erro: Este funcionário já está registrado como passageiro neste uso de veículo.', 'error')
        else:
            flash('Erro de integridade ao registrar uso. Verifique os dados e tente novamente.', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO AO REGISTRAR USO: {str(e)}")
        flash('Erro ao registrar uso do veículo. Tente novamente.', 'error')
    
    return redirect(url_for('main.veiculos'))


# Helper function para organizar passageiros por posição no modal
def organizar_passageiros_por_posicao(passageiros):
    """
    Organiza passageiros por posição (frente/trás) com ícones e contadores
    Retorna HTML formatado para exibição no modal
    """
    # Separar passageiros por posição
    passageiros_frente = [p for p in passageiros if p.posicao == 'frente']
    passageiros_tras = [p for p in passageiros if p.posicao == 'tras']
    
    html = '<div class="row">'
    
    # Passageiros da Frente
    html += '''
    <div class="col-12 mb-2">
        <div class="card border-primary mb-2">
            <div class="card-header bg-light border-primary py-1">
                <h6 class="card-title mb-0 text-primary">
                    Frente ({})
                </h6>
            </div>
            <div class="card-body py-2">
    '''.format(len(passageiros_frente))
    
    if passageiros_frente:
        for passageiro in passageiros_frente:
            nome = passageiro.funcionario.nome if passageiro.funcionario else 'N/A'
            funcao = passageiro.funcionario.funcao_ref.nome if passageiro.funcionario and passageiro.funcionario.funcao_ref else 'Sem função'
            html += f'<div class="mb-1"><strong>{nome}</strong> <small class="text-muted">- {funcao}</small></div>'
    else:
        html += '<small class="text-muted">Nenhum passageiro na frente</small>'
    
    html += '''
            </div>
        </div>
    </div>
    '''
    
    # Passageiros de Trás
    html += '''
    <div class="col-12 mb-2">
        <div class="card border-success mb-2">
            <div class="card-header bg-light border-success py-1">
                <h6 class="card-title mb-0 text-success">
                    Trás ({})
                </h6>
            </div>
            <div class="card-body py-2">
    '''.format(len(passageiros_tras))
    
    if passageiros_tras:
        for passageiro in passageiros_tras:
            nome = passageiro.funcionario.nome if passageiro.funcionario else 'N/A'
            funcao = passageiro.funcionario.funcao_ref.nome if passageiro.funcionario and passageiro.funcionario.funcao_ref else 'Sem função'
            html += f'<div class="mb-1"><strong>{nome}</strong> <small class="text-muted">- {funcao}</small></div>'
    else:
        html += '<small class="text-muted">Nenhum passageiro atrás</small>'
    
    html += '''
            </div>
        </div>
    </div>
    '''
    
    html += '</div>'
    
    # Se não há passageiros em nenhuma posição
    if not passageiros_frente and not passageiros_tras:
        html = '''
        <div class="text-center text-muted">
            <i class="fas fa-info-circle"></i>
            Nenhum passageiro registrado
        </div>
        '''
    
    return html


# ROTA DETALHES USO - /veiculos/uso/<int:uso_id>/detalhes (GET)
@main_bp.route('/veiculos/uso/<int:uso_id>/detalhes', methods=['GET'])
@login_required
def detalhes_uso_veiculo(uso_id):
    """Fornecer dados detalhados de um uso específico via AJAX"""
    from models import UsoVeiculo, Funcionario, Obra, Veiculo, PassageiroVeiculo
    
    try:
        # [LOCK] SEGURANÇA MULTITENANT
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        # Buscar uso com relacionamentos
        uso = UsoVeiculo.query.options(
            db.joinedload(UsoVeiculo.veiculo),
            db.joinedload(UsoVeiculo.funcionario),
            db.joinedload(UsoVeiculo.obra)
        ).filter_by(id=uso_id, admin_id=tenant_admin_id).first()
        
        if not uso:
            return jsonify({'error': 'Uso não encontrado'}), 404
        
        # Buscar passageiros do uso com informações dos funcionários
        passageiros = PassageiroVeiculo.query.options(
            db.joinedload(PassageiroVeiculo.funcionario)
        ).filter_by(
            uso_veiculo_id=uso.id,
            admin_id=tenant_admin_id
        ).all()
        
        # Montar HTML dos detalhes
        html_content = f"""
    <div class="row">
        <div class="col-md-6">
            <h6><i class="fas fa-info-circle"></i> Informações Gerais</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <tr>
                        <td><strong>Data:</strong></td>
                        <td>{uso.data_uso.strftime('%d/%m/%Y') if uso.data_uso else '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Veículo:</strong></td>
                        <td>{uso.veiculo.placa} - {uso.veiculo.marca} {uso.veiculo.modelo}</td>
                    </tr>
                    <tr>
                        <td><strong>Condutor:</strong></td>
                        <td>{uso.funcionario.nome if uso.funcionario else '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Obra:</strong></td>
                        <td>{uso.obra.nome if uso.obra else 'Não vinculado'}</td>
                    </tr>
                </table>
            </div>
        </div>
        <div class="col-md-6">
            <h6><i class="fas fa-tachometer-alt"></i> Dados Técnicos</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <tr>
                        <td><strong>KM Inicial:</strong></td>
                        <td>{f"{uso.km_inicial:,}".replace(",", ".") if uso.km_inicial else '-'} km</td>
                    </tr>
                    <tr>
                        <td><strong>KM Final:</strong></td>
                        <td>{f"{uso.km_final:,}".replace(",", ".") if uso.km_final else '-'} km</td>
                    </tr>
                    <tr>
                        <td><strong>Distância:</strong></td>
                        <td>{f"{uso.km_percorrido:,}".replace(",", ".") if uso.km_percorrido else '-'} km</td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
    
    <div class="row mt-3">
        <div class="col-md-6">
            <h6><i class="fas fa-clock"></i> Horários</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <tr>
                        <td><strong>Saída:</strong></td>
                        <td>{uso.hora_saida.strftime('%H:%M') if uso.hora_saida else '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Retorno:</strong></td>
                        <td>{uso.hora_retorno.strftime('%H:%M') if uso.hora_retorno else '-'}</td>
                    </tr>
                    <tr>
                        <td><strong>Duração:</strong></td>
                        <td>{uso.tempo_uso_str if hasattr(uso, 'tempo_uso_str') else 'N/A'}</td>
                    </tr>
                </table>
            </div>
        </div>
        <div class="col-md-6">
            <h6><i class="fas fa-users"></i> Passageiros por Posição</h6>
            {organizar_passageiros_por_posicao(passageiros)}
        </div>
    </div>
    
    <div class="row mt-3">
        <div class="col-12">
            <h6><i class="fas fa-sticky-note"></i> Observações</h6>
            <div class="card">
                <div class="card-body">
                    {uso.observacoes if uso.observacoes else '<em class="text-muted">Nenhuma observação registrada</em>'}
                </div>
            </div>
        </div>
    </div>
    """
        
        return html_content
        
    except Exception as e:
        logger.error(f"ERRO DETALHES USO: {str(e)}")
        return f'<div class="alert alert-danger">Erro ao carregar detalhes: {str(e)}</div>', 500


# ========================
# CRUD DE USO DE VEÍCULOS  
# ========================

# EDITAR USO DE VEÍCULO
@main_bp.route('/veiculos/uso/<int:uso_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_uso_veiculo(uso_id):
    """Editar uso de veículo existente"""
    from forms import UsoVeiculoForm
    from models import UsoVeiculo, Veiculo, Funcionario, Obra
    
    try:
        # [LOCK] SEGURANÇA MULTITENANT
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Buscar uso com verificação de propriedade
        uso = UsoVeiculo.query.join(Veiculo).filter(
            UsoVeiculo.id == uso_id,
            Veiculo.admin_id == tenant_admin_id
        ).first_or_404()
        
        form = UsoVeiculoForm(obj=uso)
        
        # Carregamento das opções do formulário
        form.veiculo_id.choices = [(v.id, f"{v.placa} - {v.marca} {v.modelo}") 
                                  for v in Veiculo.query.filter_by(admin_id=tenant_admin_id).all()]
        form.funcionario_id.choices = [(f.id, f.nome) 
                                      for f in Funcionario.query.filter_by(admin_id=tenant_admin_id).all()]
        form.obra_id.choices = [(0, "Nenhuma obra")] + [(o.id, o.nome) 
                                                       for o in Obra.query.filter_by(admin_id=tenant_admin_id).all()]
        
        if form.validate_on_submit():
            # Atualizar dados (usando campos corretos do modelo)
            uso.veiculo_id = form.veiculo_id.data
            uso.funcionario_id = form.funcionario_id.data  # Campo correto: funcionario_id
            uso.obra_id = form.obra_id.data if form.obra_id.data != 0 else None
            uso.data_uso = form.data_uso.data
            uso.km_inicial = form.km_inicial.data
            uso.km_final = form.km_final.data
            uso.observacoes = form.observacoes.data
            
            db.session.commit()
            flash('Uso de veículo atualizado com sucesso!', 'success')
            return redirect(url_for('main.detalhes_veiculo', veiculo_id=uso.veiculo_id))
        
        return render_template('veiculos/editar_uso.html', form=form, uso=uso)
        
    except Exception as e:
        logger.error(f"ERRO EDITAR USO: {str(e)}")
        flash(f'Erro ao editar uso: {str(e)}', 'error')
        return redirect(url_for('main.veiculos'))

# DELETAR USO DE VEÍCULO
@main_bp.route('/veiculos/uso/<int:uso_id>/deletar', methods=['POST'])
@login_required
def deletar_uso_veiculo(uso_id):
    """Deletar uso de veículo"""
    from models import UsoVeiculo, Veiculo, PassageiroVeiculo
    
    try:
        # [LOCK] SEGURANÇA MULTITENANT
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Buscar uso com verificação de propriedade
        uso = UsoVeiculo.query.join(Veiculo).filter(
            UsoVeiculo.id == uso_id,
            Veiculo.admin_id == tenant_admin_id
        ).first_or_404()
        
        veiculo_id = uso.veiculo_id
        
        # Deletar passageiros relacionados primeiro
        PassageiroVeiculo.query.filter_by(uso_veiculo_id=uso_id).delete()
        
        # Deletar uso
        db.session.delete(uso)
        db.session.commit()
        
        flash('Uso de veículo excluído com sucesso!', 'success')
        return redirect(url_for('main.detalhes_veiculo', veiculo_id=veiculo_id))
        
    except Exception as e:
        logger.error(f"ERRO DELETAR USO: {str(e)}")
        flash(f'Erro ao excluir uso: {str(e)}', 'error')
        return redirect(url_for('main.veiculos'))

# ===========================
# CRUD DE CUSTO DE VEÍCULOS  
# ===========================

# EDITAR CUSTO DE VEÍCULO
@main_bp.route('/veiculos/custo/<int:custo_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_custo_veiculo(custo_id):
    """Editar custo de veículo existente"""
    from forms import CustoVeiculoForm
    from models import CustoVeiculo, Veiculo
    
    try:
        # [LOCK] SEGURANÇA MULTITENANT
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Buscar custo com verificação de propriedade
        custo = CustoVeiculo.query.join(Veiculo).filter(
            CustoVeiculo.id == custo_id,
            Veiculo.admin_id == tenant_admin_id
        ).first_or_404()
        
        form = CustoVeiculoForm(obj=custo)
        
        if form.validate_on_submit():
            # Atualizar dados
            custo.data_custo = form.data_custo.data
            custo.tipo_custo = form.tipo_custo.data
            custo.valor = form.valor.data
            custo.km_custo = form.km_custo.data
            custo.litros = form.litros.data
            custo.observacoes = form.observacoes.data
            
            db.session.commit()
            flash('Custo de veículo atualizado com sucesso!', 'success')
            return redirect(url_for('main.detalhes_veiculo', veiculo_id=custo.veiculo_id))
        
        return render_template('veiculos/editar_custo.html', form=form, custo=custo)
        
    except Exception as e:
        logger.error(f"ERRO EDITAR CUSTO: {str(e)}")
        flash(f'Erro ao editar custo: {str(e)}', 'error')
        return redirect(url_for('main.veiculos'))

# DELETAR CUSTO DE VEÍCULO
@main_bp.route('/veiculos/custo/<int:custo_id>/deletar', methods=['POST'])
@login_required
def deletar_custo_veiculo(custo_id):
    """Deletar custo de veículo"""
    from models import CustoVeiculo, Veiculo
    
    try:
        # [LOCK] SEGURANÇA MULTITENANT
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Buscar custo com verificação de propriedade
        custo = CustoVeiculo.query.join(Veiculo).filter(
            CustoVeiculo.id == custo_id,
            Veiculo.admin_id == tenant_admin_id
        ).first_or_404()
        
        veiculo_id = custo.veiculo_id
        
        # Deletar custo
        db.session.delete(custo)
        db.session.commit()
        
        flash('Custo de veículo excluído com sucesso!', 'success')
        return redirect(url_for('main.detalhes_veiculo', veiculo_id=veiculo_id))
        
    except Exception as e:
        logger.error(f"ERRO DELETAR CUSTO: {str(e)}")
        flash(f'Erro ao excluir custo: {str(e)}', 'error')
        return redirect(url_for('main.veiculos'))

# ROTA PARA MODAL DE CUSTO (SEM PARÂMETRO ID NA URL)
@main_bp.route('/veiculos/custo', methods=['POST'])
@login_required  # [LOCK] MUDANÇA: Funcionários podem registrar custos de veículos
def novo_custo_veiculo_lista():
    from forms import CustoVeiculoForm
    from models import Veiculo, CustoVeiculo
    
    # Obter veiculo_id do form (hidden field)
    veiculo_id = request.form.get('veiculo_id')
    if not veiculo_id:
        flash('Erro: ID do veículo não fornecido.', 'error')
        return redirect(url_for('main.veiculos'))
    
    # [LOCK] SEGURANÇA MULTITENANT: Usar resolver unificado
    tenant_admin_id = get_tenant_admin_id()
    if not tenant_admin_id:
        flash('Acesso negado. Faça login novamente.', 'error')
        return redirect(url_for('auth.login'))
    
    veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first_or_404()
    
    try:
        # Validações de negócio
        valor = float(request.form.get('valor', 0))
        if valor <= 0:
            flash('Valor deve ser maior que zero.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Campos opcionais específicos por tipo de custo
        tipo_custo = request.form.get('tipo_custo')
        km_custo = request.form.get('km_custo')
        litros = request.form.get('litros')
        
        # Criar registro de custo
        custo = CustoVeiculo(
            veiculo_id=veiculo.id,
            data_custo=datetime.strptime(request.form.get('data_custo'), '%Y-%m-%d').date(),
            tipo_custo=tipo_custo,
            valor=valor,
            descricao=request.form.get('descricao', ''),
            fornecedor=request.form.get('fornecedor', ''),
            km_custo=int(km_custo) if km_custo else None,
            litros=float(litros) if litros else None,
            admin_id=tenant_admin_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(custo)
        db.session.commit()
        flash(f'Custo do veículo {veiculo.placa} registrado com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO AO REGISTRAR CUSTO: {str(e)}")
        flash('Erro ao registrar custo do veículo. Tente novamente.', 'error')
    
    return redirect(url_for('main.veiculos'))




# 5. ROTA REGISTRO CUSTO - /veiculos/<id>/custo (GET/POST)
@main_bp.route('/veiculos/<int:id>/custo', methods=['GET', 'POST'])
@admin_required
def novo_custo_veiculo(id):
    from forms import CustoVeiculoForm
    from models import Veiculo, CustoVeiculo, FluxoCaixa
    
    admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
    veiculo = Veiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    
    form = CustoVeiculoForm()
    form.veiculo_id.data = veiculo.id
    
    if form.validate_on_submit():
        try:
            # CRÍTICO: Validar valor positivo
            if form.valor.data is None or form.valor.data <= 0:
                flash('Erro: O valor do custo deve ser maior que zero.', 'error')
                return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)
            
            # CRÍTICO: Validação de odômetro - km não pode diminuir
            if form.km_atual.data and veiculo.km_atual:
                if form.km_atual.data < veiculo.km_atual:
                    flash(f'Erro: Quilometragem não pode diminuir. Atual: {veiculo.km_atual}km, Tentativa: {form.km_atual.data}km', 'error')
                    return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)
            
            # Validar tipo de custo
            tipos_validos = ['combustivel', 'manutencao', 'seguro', 'multa', 'ipva', 'licenciamento', 'pneus', 'outros']
            if form.tipo_custo.data not in tipos_validos:
                flash(f'Tipo de custo inválido. Use: {", ".join(tipos_validos)}', 'error')
                return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)
            
            # Validações específicas para combustível
            if form.tipo_custo.data == 'combustivel':
                if not form.litros_combustivel.data or form.litros_combustivel.data <= 0:
                    flash('Litros de combustível é obrigatório para abastecimentos.', 'error')
                    return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)
                
                if not form.preco_por_litro.data or form.preco_por_litro.data <= 0:
                    flash('Preço por litro é obrigatório para abastecimentos.', 'error')
                    return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)
            
            # Criar registro de custo com novos campos
            custo = CustoVeiculo(
                veiculo_id=veiculo.id,
                obra_id=form.obra_id.data if form.obra_id.data else None,
                data_custo=form.data_custo.data,
                valor=form.valor.data,
                tipo_custo=form.tipo_custo.data,
                descricao=form.descricao.data,
                km_atual=form.km_atual.data or veiculo.km_atual,
                fornecedor=form.fornecedor.data,
                # Campos específicos para combustível
                litros_combustivel=form.litros_combustivel.data if form.tipo_custo.data == 'combustivel' else None,
                preco_por_litro=form.preco_por_litro.data if form.tipo_custo.data == 'combustivel' else None,
                posto_combustivel=form.posto_combustivel.data if form.tipo_custo.data == 'combustivel' else None,
                tipo_combustivel=form.tipo_combustivel.data if form.tipo_custo.data == 'combustivel' else None,
                tanque_cheio=form.tanque_cheio.data if form.tipo_custo.data == 'combustivel' else False,
                # Campos para manutenção
                numero_nota_fiscal=form.numero_nota_fiscal.data if form.tipo_custo.data == 'manutencao' else None,
                categoria_manutencao=form.categoria_manutencao.data if form.tipo_custo.data == 'manutencao' else None,
                proxima_manutencao_km=form.proxima_manutencao_km.data if form.tipo_custo.data == 'manutencao' else None,
                proxima_manutencao_data=form.proxima_manutencao_data.data if form.tipo_custo.data == 'manutencao' else None,
                # Controle financeiro
                centro_custo=form.centro_custo.data,
                admin_id=admin_id
            )
            
            # Calcular próxima manutenção automaticamente se for manutenção
            if form.tipo_custo.data == 'manutencao':
                custo.calcular_proxima_manutencao()
            
            db.session.add(custo)
            
            # Atualizar KM atual do veículo se informado (já validado acima)
            if form.km_atual.data and form.km_atual.data > veiculo.km_atual:
                veiculo.km_atual = form.km_atual.data
            
            # Integrar com fluxo de caixa (se tabela existir)
            try:
                fluxo = FluxoCaixa(
                    data_movimento=form.data_custo.data,
                    tipo_movimento='SAIDA',
                    categoria='custo_veiculo',
                    valor=form.valor.data,
                    descricao=f'{form.tipo_custo.data.title()} - {veiculo.placa} - {form.descricao.data}',
                    referencia_id=custo.id,
                    referencia_tabela='custo_veiculo'
                )
                db.session.add(fluxo)
            except Exception as fluxo_error:
                logger.error(f"AVISO: Não foi possível integrar com fluxo de caixa: {fluxo_error}")
            
            db.session.commit()
            
            flash(f'Custo de {form.tipo_custo.data} registrado com sucesso!', 'success')
            return redirect(url_for('main.detalhes_veiculo', id=veiculo.id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"ERRO AO REGISTRAR CUSTO DE VEÍCULO: {str(e)}")
            flash('Erro ao registrar custo do veículo. Tente novamente.', 'error')
    
    return render_template('veiculos/novo_custo.html', form=form, veiculo=veiculo)


# ===== NOVAS ROTAS AVANÇADAS PARA SISTEMA DE VEÍCULOS =====

@main_bp.route('/veiculos/<int:id>/dashboard')
@admin_required
def dashboard_veiculo(id):
    """Dashboard completo com KPIs e gráficos de um veículo específico"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        from models import Veiculo, UsoVeiculo, CustoVeiculo
        from sqlalchemy import text
        from sqlalchemy import func, extract
        
        veiculo = Veiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        # Período para análises (últimos 6 meses)
        data_limite = datetime.now() - timedelta(days=180)
        
        # 1. KPIs PRINCIPAIS
        # Total de KMs percorridos (últimos 6 meses)
        usos_periodo = UsoVeiculo.query.filter(
            UsoVeiculo.veiculo_id == id,
            UsoVeiculo.data_uso >= data_limite.date()
        ).all()
        
        total_km = sum([uso.km_percorrido for uso in usos_periodo if uso.km_percorrido])
        total_horas = sum([uso.horas_uso for uso in usos_periodo if uso.horas_uso])
        total_usos = len(usos_periodo)
        
        # Custos por categoria (últimos 6 meses)
        custos_periodo = CustoVeiculo.query.filter(
            CustoVeiculo.veiculo_id == id,
            CustoVeiculo.data_custo >= data_limite.date()
        ).all()
        
        custos_por_tipo = {}
        total_litros = 0
        custo_total = 0
        
        for custo in custos_periodo:
            tipo = custo.tipo_custo
            custos_por_tipo[tipo] = custos_por_tipo.get(tipo, 0) + custo.valor
            custo_total += custo.valor
            
            if tipo == 'combustivel' and custo.litros_combustivel:
                total_litros += custo.litros_combustivel
        
        # Cálculos de eficiência
        consumo_medio = round(total_km / total_litros, 2) if total_litros > 0 else 0
        custo_por_km = round(custo_total / total_km, 2) if total_km > 0 else 0
        horas_por_uso = round(total_horas / total_usos, 2) if total_usos > 0 else 0
        
        # 2. DADOS PARA GRÁFICOS
        # Uso mensal (últimos 6 meses)
        uso_mensal = db.session.query(
            extract('year', UsoVeiculo.data_uso).label('ano'),
            extract('month', UsoVeiculo.data_uso).label('mes'),
            func.sum(UsoVeiculo.km_percorrido).label('total_km'),
            func.count(UsoVeiculo.id).label('total_usos')
        ).filter(
            UsoVeiculo.veiculo_id == id,
            UsoVeiculo.data_uso >= data_limite.date()
        ).group_by('ano', 'mes').order_by('ano', 'mes').all()
        
        # Custos mensais por tipo
        custos_mensais = db.session.query(
            extract('year', CustoVeiculo.data_custo).label('ano'),
            extract('month', CustoVeiculo.data_custo).label('mes'),
            CustoVeiculo.tipo_custo,
            func.sum(CustoVeiculo.valor).label('total_valor')
        ).filter(
            CustoVeiculo.veiculo_id == id,
            CustoVeiculo.data_custo >= data_limite.date()
        ).group_by('ano', 'mes', CustoVeiculo.tipo_custo).all()
        
        # 3. ÚLTIMOS USOS (10 mais recentes)
        ultimos_usos = UsoVeiculo.query.filter_by(veiculo_id=id).order_by(UsoVeiculo.data_uso.desc()).limit(10).all()
        
        # 4. PRÓXIMAS MANUTENÇÕES
        proximas_manutencoes = CustoVeiculo.query.filter(
            CustoVeiculo.veiculo_id == id,
            CustoVeiculo.proxima_manutencao_km.isnot(None),
            CustoVeiculo.proxima_manutencao_km > veiculo.km_atual
        ).order_by(CustoVeiculo.proxima_manutencao_km).all()
        
        kpis = {
            'total_km': total_km,
            'total_horas': total_horas,
            'total_usos': total_usos,
            'consumo_medio': consumo_medio,
            'custo_por_km': custo_por_km,
            'horas_por_uso': horas_por_uso,
            'custo_total': custo_total,
            'custos_por_tipo': custos_por_tipo
        }
        
        return render_template('veiculos/dashboard_veiculo.html',
                             veiculo=veiculo,
                             kpis=kpis,
                             uso_mensal=uso_mensal,
                             custos_mensais=custos_mensais,
                             ultimos_usos=ultimos_usos,
                             proximas_manutencoes=proximas_manutencoes)
        
    except Exception as e:
        logger.error(f"ERRO DASHBOARD VEÍCULO: {str(e)}")
        flash('Erro ao carregar dashboard do veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=id))


@main_bp.route('/veiculos/<int:id>/historico')
@admin_required
def historico_veiculo(id):
    """Histórico completo de uso e custos do veículo com filtros avançados"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        from models import Veiculo, UsoVeiculo, CustoVeiculo
        from sqlalchemy import text, Funcionario, Obra
        
        veiculo = Veiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        # Filtros da query string
        filtros = {
            'tipo': request.args.get('tipo', ''),  # uso, custo ou todos
            'data_inicio': request.args.get('data_inicio'),
            'data_fim': request.args.get('data_fim'),
            'funcionario_id': request.args.get('funcionario_id'),
            'obra_id': request.args.get('obra_id'),
            'tipo_custo': request.args.get('tipo_custo')
        }
        
        # Query base para usos
        query_usos = UsoVeiculo.query.filter_by(veiculo_id=id)
        
        # Query base para custos
        query_custos = CustoVeiculo.query.filter_by(veiculo_id=id)
        
        # Aplicar filtros de data
        if filtros['data_inicio']:
            data_inicio = datetime.strptime(filtros['data_inicio'], '%Y-%m-%d').date()
            query_usos = query_usos.filter(UsoVeiculo.data_uso >= data_inicio)
            query_custos = query_custos.filter(CustoVeiculo.data_custo >= data_inicio)
        
        if filtros['data_fim']:
            data_fim = datetime.strptime(filtros['data_fim'], '%Y-%m-%d').date()
            query_usos = query_usos.filter(UsoVeiculo.data_uso <= data_fim)
            query_custos = query_custos.filter(CustoVeiculo.data_custo <= data_fim)
        
        # Filtros específicos
        if filtros['funcionario_id']:
            query_usos = query_usos.filter(UsoVeiculo.funcionario_id == int(filtros['funcionario_id']))
        
        if filtros['obra_id']:
            query_usos = query_usos.filter(UsoVeiculo.obra_id == int(filtros['obra_id']))
            # [OK] CORREÇÃO: Verificar atributo obra_id antes de usar
            if hasattr(CustoVeiculo, 'obra_id'):
                query_custos = query_custos.filter(CustoVeiculo.obra_id == int(filtros['obra_id']))
        
        if filtros['tipo_custo']:
            query_custos = query_custos.filter(CustoVeiculo.tipo_custo == filtros['tipo_custo'])
        
        # Executar queries baseado no tipo
        usos = []
        custos = []
        
        if filtros['tipo'] in ['', 'todos', 'uso']:
            usos = query_usos.order_by(UsoVeiculo.data_uso.desc()).limit(100).all()
        
        if filtros['tipo'] in ['', 'todos', 'custo']:
            custos = query_custos.order_by(CustoVeiculo.data_custo.desc()).limit(100).all()
        
        # Criar linha do tempo combinada
        eventos = []
        for uso in usos:
            eventos.append({
                'tipo': 'uso',
                'data': uso.data_uso,
                'objeto': uso
            })
        
        for custo in custos:
            eventos.append({
                'tipo': 'custo',
                'data': custo.data_custo,
                'objeto': custo
            })
        
        # Ordenar eventos por data
        eventos.sort(key=lambda x: x['data'], reverse=True)
        
        # Opções para filtros
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        return render_template('veiculos/historico_veiculo.html',
                             veiculo=veiculo,
                             eventos=eventos,
                             filtros=filtros,
                             funcionarios=funcionarios,
                             obras=obras)
        
    except Exception as e:
        logger.error(f"ERRO HISTÓRICO VEÍCULO: {str(e)}")
        flash('Erro ao carregar histórico do veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=id))


@main_bp.route('/veiculos/<int:id>/custos')
@admin_required  
def lista_custos_veiculo(id):
    """Lista completa de custos do veículo com filtros e paginação"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        from models import Veiculo, CustoVeiculo
        
        veiculo = Veiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        # Filtros da query string
        filtros = {
            'tipo': request.args.get('tipo', ''),
            'data_inicio': request.args.get('data_inicio'),
            'data_fim': request.args.get('data_fim')
        }
        
        # Query base
        query = CustoVeiculo.query.filter_by(veiculo_id=id)
        
        # Aplicar filtros
        if filtros['tipo']:
            query = query.filter(CustoVeiculo.tipo_custo == filtros['tipo'])
        
        if filtros['data_inicio']:
            data_inicio = datetime.strptime(filtros['data_inicio'], '%Y-%m-%d').date()
            query = query.filter(CustoVeiculo.data_custo >= data_inicio)
        
        if filtros['data_fim']:
            data_fim = datetime.strptime(filtros['data_fim'], '%Y-%m-%d').date()
            query = query.filter(CustoVeiculo.data_custo <= data_fim)
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        custos = query.order_by(CustoVeiculo.data_custo.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Calcular totais
        total_gasto = db.session.query(func.sum(CustoVeiculo.valor)).filter_by(veiculo_id=id).scalar() or 0
        
        # Custo do mês atual
        inicio_mes = datetime.now().replace(day=1).date()
        custo_mes = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.veiculo_id == id,
            CustoVeiculo.data_custo >= inicio_mes
        ).scalar() or 0
        
        return render_template('veiculos/lista_custos.html',
                             veiculo=veiculo,
                             custos=custos,
                             filtros=filtros,
                             total_gasto=total_gasto,
                             custo_mes=custo_mes)
        
    except Exception as e:
        logger.error(f"ERRO LISTA CUSTOS: {str(e)}")
        flash('Erro ao carregar custos do veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=id))


@main_bp.route('/veiculos/<int:id>/exportar')
@admin_required
def exportar_dados_veiculo(id):
    """Exportar dados do veículo para Excel"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        from models import Veiculo, UsoVeiculo, CustoVeiculo
        from sqlalchemy import text
        import io
        import csv
        from flask import Response
        
        veiculo = Veiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        
        # Criar CSV em memória
        output = io.StringIO()
        writer = csv.writer(output)
        
        tipo_export = request.args.get('tipo', 'completo')
        
        if tipo_export in ['completo', 'usos']:
            # Cabeçalho para usos
            writer.writerow(['=== HISTÓRICO DE USOS ==='])
            writer.writerow(['Data', 'Funcionário', 'Obra', 'KM Inicial', 'KM Final', 'KM Percorrido', 
                           'Horário Saída', 'Horário Retorno', 'Observações'])
            
            usos = UsoVeiculo.query.filter_by(veiculo_id=id).order_by(UsoVeiculo.data_uso.desc()).all()
            for uso in usos:
                writer.writerow([
                    uso.data_uso.strftime('%d/%m/%Y'),
                    uso.funcionario.nome if uso.funcionario else '',
                    uso.obra.nome if uso.obra else '',
                    uso.km_inicial or '',
                    uso.km_final or '',
                    uso.km_percorrido or '',
                    uso.hora_saida.strftime('%H:%M') if uso.hora_saida else '',
                    uso.hora_retorno.strftime('%H:%M') if uso.hora_retorno else '',
                    uso.observacoes or ''
                ])
            writer.writerow([])  # Linha vazia
        
        if tipo_export in ['completo', 'custos']:
            # Cabeçalho para custos
            writer.writerow(['=== HISTÓRICO DE CUSTOS ==='])
            writer.writerow(['Data', 'Tipo', 'Valor', 'Descrição', 'Fornecedor', 'KM Atual', 
                           'Litros', 'Preço/Litro', 'Consumo', 'Categoria Manutenção'])
            
            custos = CustoVeiculo.query.filter_by(veiculo_id=id).order_by(CustoVeiculo.data_custo.desc()).all()
            for custo in custos:
                writer.writerow([
                    custo.data_custo.strftime('%d/%m/%Y'),
                    custo.tipo_custo,
                    f"R$ {custo.valor:.2f}",
                    custo.descricao or '',
                    custo.fornecedor or '',
                    custo.km_atual or '',
                    custo.litros_combustivel or '',
                    f"R$ {custo.preco_por_litro:.2f}" if custo.preco_por_litro else '',
                    f"{custo.consumo_medio} km/l" if custo.consumo_medio else '',
                    custo.categoria_manutencao or ''
                ])
        
        # Preparar resposta
        output.seek(0)
        filename = f"veiculo_{veiculo.placa}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        logger.error(f"ERRO EXPORTAR DADOS: {str(e)}")
        flash('Erro ao exportar dados do veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=id))

# ===== SISTEMA COMPLETO DE HISTÓRICO E LANÇAMENTOS DE VEÍCULOS =====

@main_bp.route('/veiculos/lancamentos')
@login_required  # [LOCK] MUDANÇA: Funcionários podem acessar lançamentos de veículos
def lancamentos_veiculos():
    """Página principal de lançamentos de veículos com filtros avançados"""
    try:
        # [LOCK] SEGURANÇA MULTITENANT: Usar resolver unificado
        from utils.tenant import get_tenant_admin_id
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
            
        from models import Veiculo, UsoVeiculo, CustoVeiculo, Funcionario, Obra
        from sqlalchemy import func, desc, or_, and_
        
        # Parâmetros de filtro
        filtros = {
            'veiculo_id': request.args.get('veiculo_id'),
            'funcionario_id': request.args.get('funcionario_id'),
            'obra_id': request.args.get('obra_id'),
            'data_inicio': request.args.get('data_inicio'),
            'data_fim': request.args.get('data_fim'),
            'tipo_lancamento': request.args.get('tipo_lancamento', 'todos'),  # 'uso', 'custo', 'todos'
            'status': request.args.get('status', 'todos'),  # 'aprovado', 'pendente', 'todos'
            'page': request.args.get('page', 1, type=int)
        }
        
        # Query base para usos
        query_usos = UsoVeiculo.query.filter(UsoVeiculo.admin_id == tenant_admin_id)
        
        # Query base para custos
        query_custos = CustoVeiculo.query.filter(CustoVeiculo.admin_id == tenant_admin_id)
        
        # Aplicar filtros de data (últimos 30 dias por padrão se não especificado)
        if not filtros['data_inicio']:
            filtros['data_inicio'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not filtros['data_fim']:
            filtros['data_fim'] = datetime.now().strftime('%Y-%m-%d')
            
        data_inicio = datetime.strptime(filtros['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(filtros['data_fim'], '%Y-%m-%d').date()
        
        query_usos = query_usos.filter(UsoVeiculo.data_uso >= data_inicio, UsoVeiculo.data_uso <= data_fim)
        query_custos = query_custos.filter(CustoVeiculo.data_custo >= data_inicio, CustoVeiculo.data_custo <= data_fim)
        
        # Aplicar outros filtros
        if filtros['veiculo_id']:
            veiculo_id = int(filtros['veiculo_id'])
            query_usos = query_usos.filter(UsoVeiculo.veiculo_id == veiculo_id)
            query_custos = query_custos.filter(CustoVeiculo.veiculo_id == veiculo_id)
            
        if filtros['funcionario_id']:
            query_usos = query_usos.filter(UsoVeiculo.funcionario_id == int(filtros['funcionario_id']))
            
        if filtros['obra_id']:
            obra_id = int(filtros['obra_id'])
            query_usos = query_usos.filter(UsoVeiculo.obra_id == obra_id)
            # [OK] CORREÇÃO: Usar verificação segura de atributo
            if hasattr(CustoVeiculo, 'obra_id'):
                query_custos = query_custos.filter(CustoVeiculo.obra_id == obra_id)
        
        # Filtro por status de aprovação
        if filtros['status'] == 'aprovado':
            query_usos = query_usos.filter(UsoVeiculo.aprovado == True)
            query_custos = query_custos.filter(CustoVeiculo.aprovado == True)
        elif filtros['status'] == 'pendente':
            query_usos = query_usos.filter(UsoVeiculo.aprovado == False)
            query_custos = query_custos.filter(CustoVeiculo.aprovado == False)
        
        # Executar queries baseado no tipo de lançamento
        lancamentos = []
        
        if filtros['tipo_lancamento'] in ['todos', 'uso']:
            usos = query_usos.order_by(desc(UsoVeiculo.data_uso)).all()
            for uso in usos:
                lancamentos.append({
                    'tipo': 'uso',
                    'data': uso.data_uso,
                    'veiculo': uso.veiculo,
                    'funcionario': uso.funcionario,
                    'obra': uso.obra,
                    'objeto': uso,
                    'approved': uso.aprovado,
                    'created_at': uso.created_at
                })
        
        if filtros['tipo_lancamento'] in ['todos', 'custo']:
            custos = query_custos.order_by(desc(CustoVeiculo.data_custo)).all()
            for custo in custos:
                lancamentos.append({
                    'tipo': 'custo',
                    'data': custo.data_custo,
                    'veiculo': custo.veiculo,
                    'funcionario': None,  # Custos não têm funcionário associado
                    'obra': custo.obra,
                    'objeto': custo,
                    'approved': custo.aprovado,
                    'created_at': custo.created_at
                })
        
        # Ordenar lançamentos por data
        lancamentos.sort(key=lambda x: (x['data'], x['created_at']), reverse=True)
        
        # Paginação manual
        per_page = 20
        total_items = len(lancamentos)
        total_pages = (total_items + per_page - 1) // per_page
        start_idx = (filtros['page'] - 1) * per_page
        end_idx = start_idx + per_page
        lancamentos_pagina = lancamentos[start_idx:end_idx]
        
        # Dados para filtros
        veiculos = Veiculo.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
        funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
        obras = Obra.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
        
        # KPIs do período
        kpis = {
            'total_usos': len([l for l in lancamentos if l['tipo'] == 'uso']),
            'total_custos': len([l for l in lancamentos if l['tipo'] == 'custo']),
            'valor_total_custos': sum([l['objeto'].valor for l in lancamentos if l['tipo'] == 'custo']),
            'km_total': sum([l['objeto'].km_percorrido or 0 for l in lancamentos if l['tipo'] == 'uso']),
            'pendente_aprovacao': len([l for l in lancamentos if not l['approved']])
        }
        
        paginacao = {
            'page': filtros['page'],
            'total_pages': total_pages,
            'per_page': per_page,
            'total_items': total_items,
            'has_prev': filtros['page'] > 1,
            'has_next': filtros['page'] < total_pages,
            'prev_num': filtros['page'] - 1 if filtros['page'] > 1 else None,
            'next_num': filtros['page'] + 1 if filtros['page'] < total_pages else None
        }
        
        return render_template('veiculos/lancamentos.html',
                             lancamentos=lancamentos_pagina,
                             filtros=filtros,
                             veiculos=veiculos,
                             funcionarios=funcionarios,
                             obras=obras,
                             kpis=kpis,
                             paginacao=paginacao)
        
    except Exception as e:
        logger.error(f"ERRO LANÇAMENTOS VEÍCULOS: {str(e)}")
        flash('Erro ao carregar lançamentos de veículos.', 'error')
        return redirect(url_for('main.veiculos'))


@main_bp.route('/veiculos/lancamentos/aprovar/<tipo>/<int:id>', methods=['POST'])
@admin_required  
def aprovar_lancamento_veiculo(tipo, id):
    """Aprovar lançamento de uso ou custo de veículo"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        from models import UsoVeiculo, CustoVeiculo
        
        if tipo == 'uso':
            item = UsoVeiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        elif tipo == 'custo':
            item = CustoVeiculo.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        else:
            flash('Tipo de lançamento inválido.', 'error')
            return redirect(url_for('main.lancamentos_veiculos'))
        
        item.aprovado = True
        item.aprovado_por_id = current_user.id
        item.data_aprovacao = datetime.utcnow()
        
        db.session.commit()
        flash(f'Lançamento de {tipo} aprovado com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO APROVAR LANÇAMENTO: {str(e)}")
        flash('Erro ao aprovar lançamento.', 'error')
    
    return redirect(url_for('main.lancamentos_veiculos'))


@main_bp.route('/veiculos/relatorios')
@login_required  # [LOCK] MUDANÇA: Funcionários podem acessar relatórios de veículos
def relatorios_veiculos():
    """Página de relatórios consolidados de veículos"""
    try:
        # [LOCK] SEGURANÇA MULTITENANT: Usar resolver unificado
        from utils.tenant import get_tenant_admin_id
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
            
        from models import Veiculo, UsoVeiculo, CustoVeiculo
        from sqlalchemy import func, extract
        
        # Período do relatório (últimos 3 meses por padrão)
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        if not data_inicio:
            data_inicio = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        if not data_fim:
            data_fim = datetime.now().strftime('%Y-%m-%d')
        
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Relatório por veículo
        veiculos = Veiculo.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
        relatorio_veiculos = []
        
        for veiculo in veiculos:
            # Usos no período
            usos = UsoVeiculo.query.filter(
                UsoVeiculo.veiculo_id == veiculo.id,
                UsoVeiculo.data_uso >= data_inicio_obj,
                UsoVeiculo.data_uso <= data_fim_obj
            ).all()
            
            # Custos no período
            custos = CustoVeiculo.query.filter(
                CustoVeiculo.veiculo_id == veiculo.id,
                CustoVeiculo.data_custo >= data_inicio_obj,
                CustoVeiculo.data_custo <= data_fim_obj
            ).all()
            
            # Calcular métricas
            total_km = sum([uso.km_percorrido or 0 for uso in usos])
            total_horas = sum([uso.horas_uso or 0 for uso in usos])
            total_custos = sum([custo.valor for custo in custos])
            total_usos = len(usos)
            
            # Custos por tipo
            custos_por_tipo = {}
            for custo in custos:
                if custo.tipo_custo not in custos_por_tipo:
                    custos_por_tipo[custo.tipo_custo] = 0
                custos_por_tipo[custo.tipo_custo] += custo.valor
            
            # Cálculo de eficiência
            custo_por_km = total_custos / total_km if total_km > 0 else 0
            media_km_por_uso = total_km / total_usos if total_usos > 0 else 0
            
            relatorio_veiculos.append({
                'veiculo': veiculo,
                'total_km': total_km,
                'total_horas': total_horas,
                'total_custos': total_custos,
                'total_usos': total_usos,
                'custos_por_tipo': custos_por_tipo,
                'custo_por_km': custo_por_km,
                'media_km_por_uso': media_km_por_uso,
                'dias_periodo': (data_fim_obj - data_inicio_obj).days + 1
            })
        
        # Ordenar por total de KM
        relatorio_veiculos.sort(key=lambda x: x['total_km'], reverse=True)
        
        # Dados consolidados da frota
        consolidado = {
            'total_km_frota': sum([r['total_km'] for r in relatorio_veiculos]),
            'total_custos_frota': sum([r['total_custos'] for r in relatorio_veiculos]),
            'total_usos_frota': sum([r['total_usos'] for r in relatorio_veiculos]),
            'total_horas_frota': sum([r['total_horas'] for r in relatorio_veiculos]),
            'media_custo_por_km': 0,
            'veiculo_mais_usado': None,
            'veiculo_mais_caro': None
        }
        
        if consolidado['total_km_frota'] > 0:
            consolidado['media_custo_por_km'] = consolidado['total_custos_frota'] / consolidado['total_km_frota']
        
        if relatorio_veiculos:
            consolidado['veiculo_mais_usado'] = max(relatorio_veiculos, key=lambda x: x['total_km'])
            consolidado['veiculo_mais_caro'] = max(relatorio_veiculos, key=lambda x: x['total_custos'])
        
        return render_template('veiculos/relatorios.html',
                             relatorio_veiculos=relatorio_veiculos,
                             consolidado=consolidado,
                             data_inicio=data_inicio,
                             data_fim=data_fim)
        
    except Exception as e:
        logger.error(f"ERRO RELATÓRIOS VEÍCULOS: {str(e)}")
        flash('Erro ao carregar relatórios de veículos.', 'error')
        return redirect(url_for('main.veiculos'))


@main_bp.route('/veiculos/relatorios/exportar')
@admin_required
def exportar_relatorio_veiculos():
    """Exportar relatório de veículos em PDF"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        from models import Veiculo, UsoVeiculo, CustoVeiculo
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        import io
        
        # Parâmetros
        data_inicio = request.args.get('data_inicio', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        data_fim = request.args.get('data_fim', datetime.now().strftime('%Y-%m-%d'))
        
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Criar buffer em memória
        buffer = io.BytesIO()
        
        # Criar documento PDF
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], alignment=1, spaceAfter=30)
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("Relatório de Utilização de Veículos", title_style))
        story.append(Paragraph(f"Período: {data_inicio_obj.strftime('%d/%m/%Y')} a {data_fim_obj.strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Buscar dados dos veículos
        veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        # Tabela de resumo por veículo
        data_table = [['Veículo', 'Total KM', 'Total Usos', 'Total Custos', 'Custo/KM']]
        
        for veiculo in veiculos:
            usos = UsoVeiculo.query.filter(
                UsoVeiculo.veiculo_id == veiculo.id,
                UsoVeiculo.data_uso >= data_inicio_obj,
                UsoVeiculo.data_uso <= data_fim_obj
            ).all()
            
            custos = CustoVeiculo.query.filter(
                CustoVeiculo.veiculo_id == veiculo.id,
                CustoVeiculo.data_custo >= data_inicio_obj,
                CustoVeiculo.data_custo <= data_fim_obj
            ).all()
            
            total_km = sum([uso.km_percorrido or 0 for uso in usos])
            total_custos = sum([custo.valor for custo in custos])
            custo_por_km = total_custos / total_km if total_km > 0 else 0
            
            data_table.append([
                f"{veiculo.placa} - {veiculo.marca} {veiculo.modelo}",
                f"{total_km} km",
                f"{len(usos)} usos",
                f"R$ {total_custos:.2f}",
                f"R$ {custo_por_km:.2f}"
            ])
        
        # Criar tabela
        table = Table(data_table)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        
        # Construir PDF
        doc.build(story)
        
        # Preparar resposta
        buffer.seek(0)
        filename = f"relatorio_veiculos_{data_inicio}_{data_fim}.pdf"
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        logger.error(f"ERRO EXPORTAR RELATÓRIO PDF: {str(e)}")
        flash('Erro ao exportar relatório. Verifique se o ReportLab está instalado.', 'error')
        return redirect(url_for('main.relatorios_veiculos'))

# CONTINUAÇÃO DO SISTEMA ANTIGO (TEMPORÁRIO PARA COMPATIBILITY)

# ========================================
# [CAR] ROTAS COMPLETAS DE VEÍCULOS V2.0 
# ========================================
# Implementação completa com design idêntico aos RDOs
# Formulários unificados, proteção multi-tenant, circuit breakers

# Importar services de veículos
try:
    from veiculos_services import VeiculoService, UsoVeiculoService, CustoVeiculoService
    logger.info("[OK] [VEICULOS] Services importados com sucesso")
except ImportError as e:
    logger.error(f"[WARN] [VEICULOS] Erro ao importar services: {e}")
    # Criar fallbacks básicos
    class VeiculoService:
        @staticmethod
        def listar_veiculos(admin_id, filtros=None, page=1, per_page=20):
            return {'veiculos': [], 'pagination': None, 'stats': {}}
        @staticmethod
        def criar_veiculo(dados, admin_id):
            return False, None, "Service não disponível"
    
    class UsoVeiculoService:
        @staticmethod
        def criar_uso_veiculo(dados, admin_id):
            return False, None, "Service não disponível"
    
    class CustoVeiculoService:
        @staticmethod
        def criar_custo_veiculo(dados, admin_id):
            return False, None, "Service não disponível"

# ===== ROTA PRINCIPAL DE VEÍCULOS (REDIRECIONAMENTO PARA FROTA) =====
@main_bp.route('/veiculos')
@login_required
def veiculos():
    """Redireciona para o novo sistema de frota"""
    logger.info("[ROUTE] [VEICULOS_REDIRECT] Redirecionando /veiculos → /frota")
    # Preservar query params (filtros, paginação)
    return redirect(url_for('frota.lista', **request.args))

# ===== REDIRECIONAMENTO: NOVO VEÍCULO =====
@main_bp.route('/veiculos/novo', methods=['GET', 'POST'])
@login_required
def novo_veiculo():
    """Redireciona para o novo sistema de frota"""
    logger.info("[ROUTE] [VEICULOS_NOVO_REDIRECT] Redirecionando /veiculos/novo → /frota/novo")
    return redirect(url_for('frota.novo'))

# ===== ROTA ANTIGA DESATIVADA: NOVO VEÍCULO =====
@main_bp.route('/veiculos/novo_OLD', methods=['GET', 'POST'])
@login_required
def novo_veiculo_OLD():
    """Formulário para cadastrar novo veículo"""
    try:
        logger.info(f"[CAR] [NOVO_VEICULO] Iniciando...")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        if request.method == 'GET':
            return render_template('veiculos_novo.html')
        
        # POST - Processar cadastro
        dados = request.form.to_dict()
        logger.debug(f"[DEBUG] [NOVO_VEICULO] Dados recebidos: {dados.keys()}")
        
        # Validações básicas
        campos_obrigatorios = ['placa', 'marca', 'modelo', 'ano', 'tipo']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                flash(f'Campo {campo.title()} é obrigatório.', 'error')
                return render_template('veiculos_novo.html')
        
        # Usar service para criar veículo
        sucesso, veiculo, mensagem = VeiculoService.criar_veiculo(dados, tenant_admin_id)
        
        if sucesso:
            flash(mensagem, 'success')
            return redirect(url_for('main.veiculos'))
        else:
            flash(mensagem, 'error')
            return render_template('veiculos_novo.html')
        
    except Exception as e:
        logger.error(f"[ERROR] [NOVO_VEICULO] Erro: {str(e)}")
        flash('Erro ao cadastrar veículo. Tente novamente.', 'error')
        return render_template('veiculos_novo.html')

# ===== NOVA ROTA: DETALHES DO VEÍCULO =====
@main_bp.route('/veiculos/<int:id>')
@login_required  
def detalhes_veiculo(id):
    """Página de detalhes do veículo com abas de uso e custos"""
    try:
        logger.info(f"[CAR] [DETALHES_VEICULO] Iniciando para ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo
        from models import Veiculo, Funcionario
        veiculo = Veiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        # Buscar funcionários para exibir nomes nos passageiros
        funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id).all()
        
        # Buscar usos recentes (últimos 20)
        usos_resultado = UsoVeiculoService.listar_usos_veiculo(
            veiculo_id=id,
            admin_id=tenant_admin_id,
            page=1,
            per_page=20
        )
        
        # Buscar custos recentes
        custos_resultado = CustoVeiculoService.listar_custos_veiculo(
            veiculo_id=id,
            admin_id=tenant_admin_id,
            page=1,
            per_page=20
        )
        
        return render_template('veiculos_detalhes.html',
                             veiculo=veiculo,
                             funcionarios=funcionarios,
                             usos=usos_resultado.get('usos', []),
                             stats_uso=usos_resultado.get('stats', {}),
                             custos=custos_resultado.get('custos', []),
                             stats_custos=custos_resultado.get('stats', {}))
        
    except Exception as e:
        logger.error(f"[ERROR] [DETALHES_VEICULO] Erro: {str(e)}")
        flash('Erro ao carregar detalhes do veículo.', 'error')
        return redirect(url_for('main.veiculos'))

# ===== NOVA ROTA: NOVO USO DE VEÍCULO (FORMULÁRIO UNIFICADO) =====
@main_bp.route('/veiculos/<int:veiculo_id>/uso/novo', methods=['GET', 'POST'])
@login_required
def novo_uso_veiculo(veiculo_id):
    """Formulário unificado para novo uso de veículo (uso + custos)"""
    try:
        logger.info(f"[CAR] [NOVO_USO] Iniciando para veículo {veiculo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo
        from models import Veiculo, Funcionario, Obra
        veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        if request.method == 'GET':
            # Buscar funcionários e obras para os selects
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            
            return render_template('uso_veiculo_novo.html',
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
        # POST - Processar criação do uso
        dados = request.form.to_dict()
        dados['veiculo_id'] = veiculo_id  # Garantir que o ID está nos dados
        
        logger.debug(f"[DEBUG] [NOVO_USO] Dados recebidos: {dados.keys()}")
        
        # Validações básicas
        campos_obrigatorios = ['data_uso', 'hora_saida', 'km_inicial']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                flash(f'Campo {campo.replace("_", " ").title()} é obrigatório.', 'error')
                funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
                obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
                return render_template('uso_veiculo_novo.html',
                                     veiculo=veiculo,
                                     funcionarios=funcionarios,
                                     obras=obras)
        
        # Usar service para criar uso
        sucesso, uso, mensagem = UsoVeiculoService.criar_uso_veiculo(dados, tenant_admin_id)
        
        if sucesso:
            flash(mensagem, 'success')
            return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))
        else:
            flash(mensagem, 'error')
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('uso_veiculo_novo.html',
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
    except Exception as e:
        logger.error(f"[ERROR] [NOVO_USO] Erro: {str(e)}")
        flash('Erro ao registrar uso do veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))

# ===== NOVA ROTA: NOVO CUSTO DE VEÍCULO =====
@main_bp.route('/veiculos/<int:veiculo_id>/custo/novo', methods=['GET', 'POST'])
@login_required
def novo_custo_veiculo_form(veiculo_id):
    """Formulário para registrar novos custos de veículo"""
    try:
        logger.info(f"[MONEY] [NOVO_CUSTO] Iniciando para veículo {veiculo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo
        from models import Veiculo, Funcionario, Obra, UsoVeiculo
        veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        if request.method == 'GET':
            # Buscar usos recentes para associação (opcional)
            usos = UsoVeiculo.query.filter_by(
                veiculo_id=veiculo_id, 
                admin_id=tenant_admin_id
            ).order_by(UsoVeiculo.data_uso.desc()).limit(10).all()
            
            # Buscar obras para associação (opcional)
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            
            return render_template('custo_veiculo_novo.html',
                                 veiculo=veiculo,
                                 usos=usos,
                                 obras=obras)
        
        # POST - Processar criação do custo
        dados = request.form.to_dict()
        dados['veiculo_id'] = veiculo_id
        
        logger.debug(f"[DEBUG] [NOVO_CUSTO] Dados recebidos: {dados.keys()}")
        
        # Validações básicas
        campos_obrigatorios = ['data_custo', 'tipo', 'valor']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                flash(f'Campo {campo.replace("_", " ").title()} é obrigatório.', 'error')
                usos = UsoVeiculo.query.filter_by(
                    veiculo_id=veiculo_id, 
                    admin_id=tenant_admin_id
                ).order_by(UsoVeiculo.data_uso.desc()).limit(10).all()
                obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
                return render_template('custo_veiculo_novo.html',
                                     veiculo=veiculo,
                                     usos=usos,
                                     obras=obras)
        
        # Usar service para criar custo
        sucesso, custo, mensagem = CustoVeiculoService.criar_custo_veiculo(dados, tenant_admin_id)
        
        if sucesso:
            flash(mensagem, 'success')
            return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))
        else:
            flash(mensagem, 'error')
            usos = UsoVeiculo.query.filter_by(
                veiculo_id=veiculo_id, 
                admin_id=tenant_admin_id
            ).order_by(UsoVeiculo.data_uso.desc()).limit(10).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('custo_veiculo_novo.html',
                                 veiculo=veiculo,
                                 usos=usos,
                                 obras=obras)
        
    except Exception as e:
        logger.error(f"[ERROR] [NOVO_CUSTO] Erro: {str(e)}")
        flash('Erro ao registrar custo do veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=veiculo_id))

# ===== NOVA ROTA: EDITAR VEÍCULO =====
@main_bp.route('/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_veiculo(id):
    """Formulário para editar dados do veículo"""
    try:
        logger.info(f"[CAR] [EDITAR_VEICULO] Iniciando para ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo
        from models import Veiculo
        veiculo = Veiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('main.veiculos'))
        
        if request.method == 'GET':
            return render_template('veiculos_editar.html', veiculo=veiculo)
        
        # POST - Processar edição
        dados = request.form.to_dict()
        logger.debug(f"[DEBUG] [EDITAR_VEICULO] Dados recebidos: {dados.keys()}")
        
        # Usar service para atualizar veículo
        sucesso, veiculo_atualizado, mensagem = VeiculoService.atualizar_veiculo(id, dados, tenant_admin_id)
        
        if sucesso:
            flash(mensagem, 'success')
            return redirect(url_for('main.detalhes_veiculo', id=id))
        else:
            flash(mensagem, 'error')
            return render_template('veiculos_editar.html', veiculo=veiculo)
        
    except Exception as e:
        logger.error(f"[ERROR] [EDITAR_VEICULO] Erro: {str(e)}")
        flash('Erro ao editar veículo.', 'error')
        return redirect(url_for('main.detalhes_veiculo', id=id))

# ===== API: DADOS DO VEÍCULO ===== 
@main_bp.route('/api/veiculos/<int:id>')
@login_required
def api_dados_veiculo(id):
    """API para obter dados do veículo em JSON"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        from models import Veiculo
        veiculo = Veiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            return jsonify({'error': 'Veículo não encontrado'}), 404
        
        dados = {
            'id': veiculo.id,
            'placa': veiculo.placa,
            'marca': veiculo.marca,
            'modelo': veiculo.modelo,
            'ano': veiculo.ano,
            'tipo': veiculo.tipo,
            'km_atual': veiculo.km_atual,
            'status': veiculo.status,
            'cor': veiculo.cor,
            'combustivel': veiculo.combustivel,
            'chassi': veiculo.chassi,
            'renavam': veiculo.renavam
        }
        
        return jsonify(dados)
        
    except Exception as e:
        logger.error(f"[ERROR] [API_DADOS_VEICULO] Erro: {str(e)}")
        return jsonify({'error': 'Erro interno'}), 500

# ===== API: FINALIZAR USO DE VEÍCULO =====
@main_bp.route('/api/veiculos/uso/<int:uso_id>/finalizar', methods=['POST'])
@login_required
def api_finalizar_uso(uso_id):
    """API para finalizar uso de veículo"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        dados = request.json or {}
        
        # Usar service para finalizar uso
        sucesso, uso, mensagem = UsoVeiculoService.finalizar_uso_veiculo(uso_id, dados, tenant_admin_id)
        
        if sucesso:
            return jsonify({'success': True, 'message': mensagem})
        else:
            return jsonify({'success': False, 'error': mensagem}), 400
        
    except Exception as e:
        logger.error(f"[ERROR] [API_FINALIZAR_USO] Erro: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro interno'}), 500

