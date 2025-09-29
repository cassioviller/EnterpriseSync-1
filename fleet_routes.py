# ================================
# FLEET ROUTES - ROTAS USANDO FLEETSERVICE
# ================================
# Rotas refatoradas para usar FleetService com feature flag
# Mantém total compatibilidade com frontend

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from auth import admin_required, get_tenant_admin_id
from fleet_service import FleetService

# Blueprint para rotas FLEET
fleet_bp = Blueprint('fleet', __name__)


def fleet_enabled():
    """Verificar se sistema FLEET está ativo"""
    return os.environ.get('FLEET_CUTOVER', 'false').lower() == 'true'


def fleet_route(route_path, **kwargs):
    """Decorator para registrar rotas FLEET apenas quando ativas"""
    def decorator(func):
        if fleet_enabled():
            return fleet_bp.route(route_path, **kwargs)(func)
        else:
            # Não registrar a rota se FLEET não estiver ativo
            return func
    return decorator


# ================================
# ROTAS PRINCIPAIS DE VEÍCULOS
# ================================

@fleet_route('/veiculos')
@login_required
def veiculos_fleet():
    """Lista principal de veículos usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Capturar filtros da URL
        filtros = {
            'status': request.args.get('status'),
            'tipo': request.args.get('tipo'),
            'placa': request.args.get('placa'),
            'marca': request.args.get('marca'),
            'busca': request.args.get('busca')
        }
        # Remover filtros vazios
        filtros = {k: v for k, v in filtros.items() if v}
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Usar FleetService para listar veículos
        resultado = FleetService.listar_veiculos(
            admin_id=tenant_admin_id,
            filtros=filtros,
            page=page,
            per_page=per_page
        )
        
        if not resultado['success']:
            flash(f'Erro ao carregar veículos: {resultado["error"]}', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Renderizar com dados no formato esperado pelo frontend
        return render_template('veiculos_lista.html',
                             veiculos=resultado['veiculos'],
                             pagination=resultado['pagination'],
                             stats={},  # Adicionar stats se necessário
                             filtros_aplicados=filtros)
        
    except Exception as e:
        flash('Erro ao carregar veículos. Tente novamente.', 'error')
        return redirect(url_for('main.dashboard'))


@fleet_route('/veiculos/novo', methods=['GET', 'POST'])
@login_required
def novo_veiculo_fleet():
    """Formulário para cadastrar novo veículo usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        if request.method == 'GET':
            return render_template('veiculos_novo.html')
        
        # POST - Processar cadastro
        dados = request.form.to_dict()
        
        # Validações básicas
        campos_obrigatorios = ['placa', 'marca', 'ano']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                flash(f'Campo {campo.title()} é obrigatório.', 'error')
                return render_template('veiculos_novo.html')
        
        # Usar FleetService para criar veículo
        resultado = FleetService.criar_veiculo(dados, tenant_admin_id)
        
        if resultado['success']:
            flash(resultado['message'], 'success')
            return redirect(url_for('fleet.veiculos_fleet'))
        else:
            flash(resultado['error'], 'error')
            return render_template('veiculos_novo.html')
        
    except Exception as e:
        flash('Erro ao criar veículo. Tente novamente.', 'error')
        return render_template('veiculos_novo.html')


@fleet_route('/veiculos/<int:id>')
@login_required
def detalhes_veiculo_fleet(id):
    """Detalhes do veículo usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Obter veículo
        resultado_veiculo = FleetService.obter_veiculo(id, tenant_admin_id)
        if not resultado_veiculo['success']:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('fleet.veiculos_fleet'))
        
        veiculo = resultado_veiculo['veiculo']
        
        # Obter usos recentes
        resultado_usos = FleetService.listar_usos_veiculo(
            id, tenant_admin_id, page=1, per_page=10
        )
        usos = resultado_usos['usos'] if resultado_usos['success'] else []
        
        # Obter custos recentes
        resultado_custos = FleetService.listar_custos_veiculo(
            id, tenant_admin_id, page=1, per_page=10
        )
        custos = resultado_custos['custos'] if resultado_custos['success'] else []
        
        # Obter estatísticas
        resultado_stats = FleetService.obter_estatisticas_veiculo(id, tenant_admin_id)
        stats = resultado_stats['estatisticas'] if resultado_stats['success'] else {}
        
        return render_template('veiculos_detalhes.html',
                             veiculo=veiculo,
                             usos=usos,
                             custos=custos,
                             stats=stats)
        
    except Exception as e:
        flash('Erro ao carregar detalhes do veículo.', 'error')
        return redirect(url_for('fleet.veiculos_fleet'))


@fleet_route('/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_veiculo_fleet(id):
    """Editar veículo usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Obter veículo atual
        resultado_veiculo = FleetService.obter_veiculo(id, tenant_admin_id)
        if not resultado_veiculo['success']:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('fleet.veiculos_fleet'))
        
        veiculo = resultado_veiculo['veiculo']
        
        if request.method == 'GET':
            return render_template('veiculos_novo.html', veiculo=veiculo, editando=True)
        
        # POST - Processar edição
        dados = request.form.to_dict()
        
        # Usar FleetService para atualizar
        resultado = FleetService.atualizar_veiculo(id, dados, tenant_admin_id)
        
        if resultado['success']:
            flash(resultado['message'], 'success')
            return redirect(url_for('fleet.detalhes_veiculo_fleet', id=id))
        else:
            flash(resultado['error'], 'error')
            return render_template('veiculos_novo.html', veiculo=veiculo, editando=True)
        
    except Exception as e:
        flash('Erro ao editar veículo.', 'error')
        return redirect(url_for('fleet.veiculos_fleet'))


# ================================
# ROTAS DE USO DE VEÍCULOS
# ================================

@fleet_route('/veiculos/<int:veiculo_id>/uso/novo', methods=['GET', 'POST'])
@login_required
def novo_uso_veiculo_fleet(veiculo_id):
    """Formulário para registrar uso de veículo usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Verificar se veículo existe
        resultado_veiculo = FleetService.obter_veiculo(veiculo_id, tenant_admin_id)
        if not resultado_veiculo['success']:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('fleet.veiculos_fleet'))
        
        veiculo = resultado_veiculo['veiculo']
        
        if request.method == 'GET':
            return render_template('uso_veiculo_novo.html', veiculo=veiculo)
        
        # POST - Processar registro de uso
        dados = request.form.to_dict()
        dados['veiculo_id'] = veiculo_id
        
        # Usar FleetService para criar uso
        resultado = FleetService.criar_uso_veiculo(dados, tenant_admin_id)
        
        if resultado['success']:
            flash(resultado['message'], 'success')
            return redirect(url_for('fleet.detalhes_veiculo_fleet', id=veiculo_id))
        else:
            flash(resultado['error'], 'error')
            return render_template('uso_veiculo_novo.html', veiculo=veiculo)
        
    except Exception as e:
        flash('Erro ao registrar uso de veículo.', 'error')
        return redirect(url_for('fleet.veiculos_fleet'))


# ================================
# ROTAS DE CUSTOS DE VEÍCULOS
# ================================

@fleet_route('/veiculos/<int:veiculo_id>/custo/novo', methods=['GET', 'POST'])
@login_required
def novo_custo_veiculo_fleet(veiculo_id):
    """Formulário para registrar custo de veículo usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Verificar se veículo existe
        resultado_veiculo = FleetService.obter_veiculo(veiculo_id, tenant_admin_id)
        if not resultado_veiculo['success']:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('fleet.veiculos_fleet'))
        
        veiculo = resultado_veiculo['veiculo']
        
        if request.method == 'GET':
            return render_template('custo_veiculo_novo.html', veiculo=veiculo)
        
        # POST - Processar registro de custo
        dados = request.form.to_dict()
        dados['veiculo_id'] = veiculo_id
        
        # Usar FleetService para criar custo
        resultado = FleetService.criar_custo_veiculo(dados, tenant_admin_id)
        
        if resultado['success']:
            flash(resultado['message'], 'success')
            return redirect(url_for('fleet.detalhes_veiculo_fleet', id=veiculo_id))
        else:
            flash(resultado['error'], 'error')
            return render_template('custo_veiculo_novo.html', veiculo=veiculo)
        
    except Exception as e:
        flash('Erro ao registrar custo de veículo.', 'error')
        return redirect(url_for('fleet.veiculos_fleet'))


# ================================
# APIS FLEET
# ================================

@fleet_route('/api/veiculos/<int:id>')
@login_required
def api_dados_veiculo_fleet(id):
    """API para obter dados do veículo usando FleetService"""
    try:
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        # Obter veículo
        resultado = FleetService.obter_veiculo(id, tenant_admin_id)
        
        if resultado['success']:
            return jsonify({
                'success': True,
                'veiculo': resultado['veiculo']
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado['error']
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500


@fleet_route('/api/fleet/status')
@login_required
def api_fleet_status():
    """API para verificar status do sistema FLEET"""
    try:
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        # Obter contadores
        resultado = FleetService.obter_contadores_admin(tenant_admin_id)
        
        return jsonify({
            'fleet_enabled': fleet_enabled(),
            'contadores': resultado['contadores'] if resultado['success'] else None,
            'timestamp': os.environ.get('FLEET_CUTOVER_TIMESTAMP')
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Erro ao obter status: {str(e)}'
        }), 500


# ================================
# UTILITÁRIOS DE INICIALIZAÇÃO
# ================================

def register_fleet_routes(app):
    """Registrar rotas FLEET na aplicação se estiver ativo"""
    if fleet_enabled():
        app.register_blueprint(fleet_bp)
        print("✅ FLEET ROUTES: Rotas FLEET registradas com sucesso")
        print(f"📊 FLEET ROUTES: {len(fleet_bp.deferred_functions)} rotas ativas")
        return True
    else:
        print("⚠️ FLEET ROUTES: Sistema FLEET desabilitado - rotas não registradas")
        return False


def get_fleet_info():
    """Obter informações do sistema FLEET"""
    return {
        'enabled': fleet_enabled(),
        'cutover_env': os.environ.get('FLEET_CUTOVER', 'false'),
        'routes_count': len(fleet_bp.deferred_functions) if fleet_enabled() else 0,
        'service_available': FleetService.verificar_sistema_ativo()
    }