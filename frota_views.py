from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import FrotaVeiculo, FrotaUtilizacao, FrotaDespesa, Funcionario, Obra
from app import db
from utils.tenant import get_tenant_admin_id
from datetime import datetime

frota_bp = Blueprint('frota', __name__, url_prefix='/frota')

# Importar services de veículos (adaptados para frota)
try:
    from veiculos_services import VeiculoService, UsoVeiculoService, CustoVeiculoService
    print("✅ [FROTA] Services importados com sucesso")
except ImportError as e:
    print(f"⚠️ [FROTA] Erro ao importar services: {e}")
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


# ===== ROTA PRINCIPAL: LISTA DE VEÍCULOS DA FROTA =====
@frota_bp.route('/')
@login_required
def lista():
    """Lista principal de veículos da frota com filtros e estatísticas"""
    try:
        print(f"🚗 [FROTA_LISTA] Iniciando listagem...")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        print(f"🔍 [FROTA_LISTA] tenant_admin_id = {tenant_admin_id}")
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Capturar filtros da URL
        filtros = {
            'status': request.args.get('status'),
            'tipo': request.args.get('tipo'),
            'placa': request.args.get('placa'),
            'marca': request.args.get('marca')
        }
        # Remover filtros vazios
        filtros = {k: v for k, v in filtros.items() if v}
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Buscar veículos da frota diretamente
        query = FrotaVeiculo.query.filter_by(admin_id=tenant_admin_id)
        print(f"🔍 [FROTA_LISTA] Query inicial: admin_id={tenant_admin_id}")
        
        # Aplicar filtros
        if filtros.get('status'):
            if filtros['status'] == 'ativo':
                query = query.filter_by(ativo=True)
                print(f"🔍 [FROTA_LISTA] Filtro aplicado: ativo=True")
            elif filtros['status'] == 'inativo':
                query = query.filter_by(ativo=False)
                print(f"🔍 [FROTA_LISTA] Filtro aplicado: ativo=False")
        else:
            # ✅ CORREÇÃO: Por padrão, mostrar apenas veículos ativos
            query = query.filter_by(ativo=True)
            print(f"🔍 [FROTA_LISTA] Filtro padrão aplicado: ativo=True")
        
        if filtros.get('tipo'):
            query = query.filter_by(tipo=filtros['tipo'])
        
        if filtros.get('placa'):
            query = query.filter(FrotaVeiculo.placa.ilike(f"%{filtros['placa']}%"))
        
        if filtros.get('marca'):
            query = query.filter(FrotaVeiculo.marca.ilike(f"%{filtros['marca']}%"))
        
        # Paginação
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        veiculos = pagination.items
        
        # Estatísticas básicas
        stats = {
            'total': FrotaVeiculo.query.filter_by(admin_id=tenant_admin_id).count(),
            'ativos': FrotaVeiculo.query.filter_by(admin_id=tenant_admin_id, ativo=True).count(),
            'inativos': FrotaVeiculo.query.filter_by(admin_id=tenant_admin_id, ativo=False).count()
        }
        
        print(f"📊 [FROTA_LISTA] Stats: total={stats['total']}, ativos={stats['ativos']}, inativos={stats['inativos']}")
        print(f"✅ [FROTA_LISTA] Encontrados {len(veiculos)} veículos na query paginada")
        if veiculos:
            print(f"🚗 [FROTA_LISTA] Primeiro veículo: {veiculos[0].placa} (id={veiculos[0].id})")
        
        return render_template('veiculos_lista.html',
                             veiculos=veiculos,
                             pagination=pagination,
                             stats=stats,
                             filtros_aplicados=filtros)
        
    except Exception as e:
        print(f"❌ [FROTA_LISTA] Erro: {str(e)}")
        flash('Erro ao carregar veículos. Tente novamente.', 'error')
        return redirect(url_for('main.dashboard'))


# ===== ROTA: NOVO VEÍCULO DA FROTA =====
@frota_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    """Formulário para cadastrar novo veículo na frota"""
    try:
        print(f"🚗 [FROTA_NOVO] Iniciando...")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        if request.method == 'GET':
            return render_template('veiculos_novo.html')
        
        # POST - Processar cadastro
        dados = request.form.to_dict()
        print(f"🔍 [FROTA_NOVO] Dados recebidos: {dados.keys()}")
        
        # Validações básicas
        campos_obrigatorios = ['placa', 'marca', 'modelo', 'ano', 'tipo']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                flash(f'Campo {campo.title()} é obrigatório.', 'error')
                return render_template('veiculos_novo.html')
        
        # Criar novo veículo da frota
        try:
            novo_veiculo = FrotaVeiculo(
                placa=dados['placa'].upper(),
                marca=dados['marca'],
                modelo=dados['modelo'],
                ano=int(dados['ano']),
                tipo=dados.get('tipo', 'Utilitário'),
                cor=dados.get('cor'),
                combustivel=dados.get('combustivel', 'Gasolina'),
                chassi=dados.get('chassi'),
                renavam=dados.get('renavam'),
                km_atual=int(dados.get('km_atual', 0)),
                admin_id=tenant_admin_id
            )
            
            db.session.add(novo_veiculo)
            db.session.commit()
            
            flash(f'Veículo {novo_veiculo.placa} cadastrado com sucesso!', 'success')
            return redirect(url_for('frota.lista'))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [FROTA_NOVO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao cadastrar veículo: {str(e)}', 'error')
            return render_template('veiculos_novo.html')
        
    except Exception as e:
        print(f"❌ [FROTA_NOVO] Erro: {str(e)}")
        flash('Erro ao cadastrar veículo. Tente novamente.', 'error')
        return render_template('veiculos_novo.html')


# ===== ROTA: DETALHES DO VEÍCULO DA FROTA =====
@frota_bp.route('/<int:id>')
@login_required  
def detalhes(id):
    """Página de detalhes do veículo da frota com abas de uso e custos"""
    try:
        print(f"🚗 [FROTA_DETALHES] Iniciando para ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        # Buscar funcionários para exibir nomes nos passageiros
        funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id).all()
        
        # Buscar usos recentes (últimos 20)
        usos = FrotaUtilizacao.query.filter_by(
            veiculo_id=id,
            admin_id=tenant_admin_id
        ).order_by(FrotaUtilizacao.data_uso.desc()).limit(20).all()
        
        # Estatísticas de uso
        stats_uso = {
            'total': FrotaUtilizacao.query.filter_by(veiculo_id=id, admin_id=tenant_admin_id).count(),
            'km_total': db.session.query(db.func.sum(FrotaUtilizacao.km_percorrido)).filter_by(
                veiculo_id=id, admin_id=tenant_admin_id
            ).scalar() or 0
        }
        
        # Buscar custos recentes
        custos = FrotaDespesa.query.filter_by(
            veiculo_id=id,
            admin_id=tenant_admin_id
        ).order_by(FrotaDespesa.data_custo.desc()).limit(20).all()
        
        # Estatísticas de custos
        stats_custos = {
            'total': FrotaDespesa.query.filter_by(veiculo_id=id, admin_id=tenant_admin_id).count(),
            'valor_total': db.session.query(db.func.sum(FrotaDespesa.valor)).filter_by(
                veiculo_id=id, admin_id=tenant_admin_id
            ).scalar() or 0
        }
        
        return render_template('veiculos_detalhes.html',
                             veiculo=veiculo,
                             funcionarios=funcionarios,
                             usos=usos,
                             stats_uso=stats_uso,
                             custos=custos,
                             stats_custos=stats_custos)
        
    except Exception as e:
        print(f"❌ [FROTA_DETALHES] Erro: {str(e)}")
        flash('Erro ao carregar detalhes do veículo.', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: EDITAR VEÍCULO DA FROTA =====
@frota_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Formulário para editar dados do veículo da frota"""
    try:
        print(f"🚗 [FROTA_EDITAR] Iniciando para ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        if request.method == 'GET':
            return render_template('veiculos_editar.html', veiculo=veiculo)
        
        # POST - Processar edição
        dados = request.form.to_dict()
        print(f"🔍 [FROTA_EDITAR] Dados recebidos: {dados.keys()}")
        
        try:
            # Atualizar campos
            if dados.get('placa'):
                veiculo.placa = dados['placa'].upper()
            if dados.get('marca'):
                veiculo.marca = dados['marca']
            if dados.get('modelo'):
                veiculo.modelo = dados['modelo']
            if dados.get('ano'):
                veiculo.ano = int(dados['ano'])
            if dados.get('tipo'):
                veiculo.tipo = dados['tipo']
            if dados.get('cor'):
                veiculo.cor = dados['cor']
            if dados.get('combustivel'):
                veiculo.combustivel = dados['combustivel']
            if dados.get('chassi'):
                veiculo.chassi = dados['chassi']
            if dados.get('renavam'):
                veiculo.renavam = dados['renavam']
            if dados.get('km_atual'):
                veiculo.km_atual = int(dados['km_atual'])
            if 'ativo' in dados:
                veiculo.ativo = dados['ativo'] == 'true' or dados['ativo'] == '1'
            
            veiculo.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Veículo {veiculo.placa} atualizado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [FROTA_EDITAR] Erro ao salvar: {str(e)}")
            flash(f'Erro ao atualizar veículo: {str(e)}', 'error')
            return render_template('veiculos_editar.html', veiculo=veiculo)
        
    except Exception as e:
        print(f"❌ [FROTA_EDITAR] Erro: {str(e)}")
        flash('Erro ao editar veículo.', 'error')
        return redirect(url_for('frota.detalhes', id=id))


# ===== ROTA: REATIVAR VEÍCULO INATIVO =====
@frota_bp.route('/<int:id>/reativar', methods=['POST'])
@login_required
def reativar(id):
    """Reativar um veículo inativo"""
    try:
        print(f"🚗 [FROTA_REATIVAR] Reativando veículo ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo inativo
        veiculo = FrotaVeiculo.query.filter_by(id=id, admin_id=tenant_admin_id, ativo=False).first()
        if not veiculo:
            flash('Veículo não encontrado ou já está ativo.', 'error')
            return redirect(url_for('frota.lista'))
        
        # Reativar
        veiculo.ativo = True
        veiculo.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash(f'Veículo {veiculo.placa} reativado com sucesso!', 'success')
        print(f"✅ [FROTA_REATIVAR] Veículo {veiculo.placa} reativado")
        
        return redirect(url_for('frota.lista'))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [FROTA_REATIVAR] Erro: {str(e)}")
        flash(f'Erro ao reativar veículo: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: NOVO USO DE VEÍCULO DA FROTA =====
@frota_bp.route('/<int:veiculo_id>/uso/novo', methods=['GET', 'POST'])
@login_required
def novo_uso(veiculo_id):
    """Formulário unificado para novo uso de veículo da frota (uso + custos)"""
    try:
        print(f"🚗 [FROTA_NOVO_USO] Iniciando para veículo {veiculo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
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
        
        print(f"🔍 [FROTA_NOVO_USO] Dados recebidos: {dados.keys()}")
        
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
        
        try:
            # Criar novo uso da frota
            novo_uso = FrotaUtilizacao(
                veiculo_id=veiculo_id,
                funcionario_id=int(dados['funcionario_id']) if dados.get('funcionario_id') else None,
                obra_id=int(dados['obra_id']) if dados.get('obra_id') else None,
                data_uso=datetime.strptime(dados['data_uso'], '%Y-%m-%d').date(),
                hora_saida=datetime.strptime(dados['hora_saida'], '%H:%M').time() if dados.get('hora_saida') else None,
                hora_retorno=datetime.strptime(dados['hora_retorno'], '%H:%M').time() if dados.get('hora_retorno') else None,
                km_inicial=int(dados['km_inicial']) if dados.get('km_inicial') else None,
                km_final=int(dados['km_final']) if dados.get('km_final') else None,
                passageiros_frente=dados.get('passageiros_frente'),
                passageiros_tras=dados.get('passageiros_tras'),
                responsavel_veiculo=dados.get('responsavel_veiculo'),
                observacoes=dados.get('observacoes'),
                admin_id=tenant_admin_id
            )
            
            # Calcular KM percorrido
            if novo_uso.km_inicial and novo_uso.km_final:
                novo_uso.km_percorrido = novo_uso.km_final - novo_uso.km_inicial
            
            db.session.add(novo_uso)
            db.session.commit()
            
            flash(f'Uso do veículo registrado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=veiculo_id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [FROTA_NOVO_USO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao registrar uso: {str(e)}', 'error')
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('uso_veiculo_novo.html',
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
    except Exception as e:
        print(f"❌ [FROTA_NOVO_USO] Erro: {str(e)}")
        flash('Erro ao registrar uso do veículo.', 'error')
        return redirect(url_for('frota.detalhes', id=veiculo_id))


# ===== ROTA: NOVO CUSTO DE VEÍCULO DA FROTA =====
@frota_bp.route('/<int:veiculo_id>/custo/novo', methods=['GET', 'POST'])
@login_required
def novo_custo(veiculo_id):
    """Formulário para registrar novos custos de veículo da frota"""
    try:
        print(f"💰 [FROTA_NOVO_CUSTO] Iniciando para veículo {veiculo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        if request.method == 'GET':
            # Buscar usos recentes para associação (opcional)
            usos = FrotaUtilizacao.query.filter_by(
                veiculo_id=veiculo_id, 
                admin_id=tenant_admin_id
            ).order_by(FrotaUtilizacao.data_uso.desc()).limit(10).all()
            
            # Buscar obras para associação (opcional)
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            
            return render_template('custo_veiculo_novo.html',
                                 veiculo=veiculo,
                                 usos=usos,
                                 obras=obras)
        
        # POST - Processar criação do custo
        dados = request.form.to_dict()
        dados['veiculo_id'] = veiculo_id
        
        print(f"🔍 [FROTA_NOVO_CUSTO] Dados recebidos: {dados.keys()}")
        
        # Validações básicas
        campos_obrigatorios = ['data_custo', 'tipo', 'valor']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                flash(f'Campo {campo.replace("_", " ").title()} é obrigatório.', 'error')
                usos = FrotaUtilizacao.query.filter_by(
                    veiculo_id=veiculo_id, 
                    admin_id=tenant_admin_id
                ).order_by(FrotaUtilizacao.data_uso.desc()).limit(10).all()
                obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
                return render_template('custo_veiculo_novo.html',
                                     veiculo=veiculo,
                                     usos=usos,
                                     obras=obras)
        
        try:
            # Criar novo custo da frota
            novo_custo = FrotaDespesa(
                veiculo_id=veiculo_id,
                data_custo=datetime.strptime(dados['data_custo'], '%Y-%m-%d').date(),
                tipo_custo=dados['tipo'],
                valor=float(dados['valor']),
                descricao=dados.get('descricao', ''),
                fornecedor=dados.get('fornecedor'),
                numero_nota_fiscal=dados.get('numero_nota_fiscal'),
                data_vencimento=datetime.strptime(dados['data_vencimento'], '%Y-%m-%d').date() if dados.get('data_vencimento') else None,
                status_pagamento=dados.get('status_pagamento', 'Pendente'),
                forma_pagamento=dados.get('forma_pagamento'),
                km_veiculo=int(dados['km_veiculo']) if dados.get('km_veiculo') else None,
                observacoes=dados.get('observacoes'),
                admin_id=tenant_admin_id
            )
            
            db.session.add(novo_custo)
            db.session.commit()
            
            flash(f'Custo registrado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=veiculo_id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [FROTA_NOVO_CUSTO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao registrar custo: {str(e)}', 'error')
            usos = FrotaUtilizacao.query.filter_by(
                veiculo_id=veiculo_id, 
                admin_id=tenant_admin_id
            ).order_by(FrotaUtilizacao.data_uso.desc()).limit(10).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('custo_veiculo_novo.html',
                                 veiculo=veiculo,
                                 usos=usos,
                                 obras=obras)
        
    except Exception as e:
        print(f"❌ [FROTA_NOVO_CUSTO] Erro: {str(e)}")
        flash('Erro ao registrar custo do veículo.', 'error')
        return redirect(url_for('frota.detalhes', id=veiculo_id))


# ===== ROTA: EDITAR USO DE VEÍCULO DA FROTA =====
@frota_bp.route('/uso/<int:uso_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_uso(uso_id):
    """Formulário para editar uso existente de veículo da frota"""
    try:
        print(f"✏️ [FROTA_EDITAR_USO] Iniciando para uso {uso_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar uso da frota
        uso = FrotaUtilizacao.query.filter_by(id=uso_id, admin_id=tenant_admin_id).first()
        if not uso:
            flash('Uso de veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        # Buscar veículo
        veiculo = FrotaVeiculo.query.filter_by(id=uso.veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        if request.method == 'GET':
            # Buscar funcionários e obras para os selects
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            
            return render_template('uso_veiculo_editar.html',
                                 uso=uso,
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
        # POST - Processar edição
        dados = request.form.to_dict()
        print(f"🔍 [FROTA_EDITAR_USO] Dados recebidos: {dados.keys()}")
        
        try:
            # Atualizar campos
            if dados.get('funcionario_id'):
                uso.funcionario_id = int(dados['funcionario_id'])
            if dados.get('obra_id'):
                uso.obra_id = int(dados['obra_id'])
            if dados.get('data_uso'):
                uso.data_uso = datetime.strptime(dados['data_uso'], '%Y-%m-%d').date()
            if dados.get('hora_saida'):
                uso.hora_saida = datetime.strptime(dados['hora_saida'], '%H:%M').time()
            if dados.get('hora_retorno'):
                uso.hora_retorno = datetime.strptime(dados['hora_retorno'], '%H:%M').time()
            if dados.get('km_inicial'):
                uso.km_inicial = int(dados['km_inicial'])
            if dados.get('km_final'):
                uso.km_final = int(dados['km_final'])
            
            # Recalcular KM percorrido
            if uso.km_inicial and uso.km_final:
                uso.km_percorrido = uso.km_final - uso.km_inicial
            
            uso.passageiros_frente = dados.get('passageiros_frente')
            uso.passageiros_tras = dados.get('passageiros_tras')
            uso.responsavel_veiculo = dados.get('responsavel_veiculo')
            uso.observacoes = dados.get('observacoes')
            
            db.session.commit()
            
            flash('Uso do veículo atualizado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=veiculo.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [FROTA_EDITAR_USO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao atualizar uso: {str(e)}', 'error')
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('uso_veiculo_editar.html',
                                 uso=uso,
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
    except Exception as e:
        print(f"❌ [FROTA_EDITAR_USO] Erro: {str(e)}")
        flash('Erro ao editar uso do veículo.', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DELETAR USO DE VEÍCULO DA FROTA =====
@frota_bp.route('/uso/<int:uso_id>/deletar', methods=['POST'])
@login_required
def deletar_uso(uso_id):
    """Deleta um uso de veículo da frota"""
    try:
        print(f"🗑️ [FROTA_DELETAR_USO] Iniciando para uso {uso_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar uso da frota
        uso = FrotaUtilizacao.query.filter_by(id=uso_id, admin_id=tenant_admin_id).first()
        if not uso:
            flash('Uso de veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        veiculo_id = uso.veiculo_id
        
        db.session.delete(uso)
        db.session.commit()
        
        flash('Uso do veículo deletado com sucesso!', 'success')
        return redirect(url_for('frota.detalhes', id=veiculo_id))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [FROTA_DELETAR_USO] Erro: {str(e)}")
        flash(f'Erro ao deletar uso: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: EDITAR CUSTO DE VEÍCULO DA FROTA =====
@frota_bp.route('/custo/<int:custo_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_custo(custo_id):
    """Formulário para editar custo existente de veículo da frota"""
    try:
        print(f"✏️ [FROTA_EDITAR_CUSTO] Iniciando para custo {custo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar custo da frota
        custo = FrotaDespesa.query.filter_by(id=custo_id, admin_id=tenant_admin_id).first()
        if not custo:
            flash('Custo de veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        # Buscar veículo
        veiculo = FrotaVeiculo.query.filter_by(id=custo.veiculo_id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        if request.method == 'GET':
            # Buscar obras para associação (opcional)
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            
            return render_template('custo_veiculo_editar.html',
                                 custo=custo,
                                 veiculo=veiculo,
                                 obras=obras)
        
        # POST - Processar edição
        dados = request.form.to_dict()
        print(f"🔍 [FROTA_EDITAR_CUSTO] Dados recebidos: {dados.keys()}")
        
        try:
            # Atualizar campos
            if dados.get('data_custo'):
                custo.data_custo = datetime.strptime(dados['data_custo'], '%Y-%m-%d').date()
            if dados.get('tipo'):
                custo.tipo_custo = dados['tipo']
            if dados.get('valor'):
                custo.valor = float(dados['valor'])
            
            custo.descricao = dados.get('descricao', '')
            custo.fornecedor = dados.get('fornecedor')
            custo.numero_nota_fiscal = dados.get('numero_nota_fiscal')
            
            if dados.get('data_vencimento'):
                custo.data_vencimento = datetime.strptime(dados['data_vencimento'], '%Y-%m-%d').date()
            
            if dados.get('status_pagamento'):
                custo.status_pagamento = dados['status_pagamento']
            
            custo.forma_pagamento = dados.get('forma_pagamento')
            
            if dados.get('km_veiculo'):
                custo.km_veiculo = int(dados['km_veiculo'])
            
            custo.observacoes = dados.get('observacoes')
            
            db.session.commit()
            
            flash('Custo do veículo atualizado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=veiculo.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [FROTA_EDITAR_CUSTO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao atualizar custo: {str(e)}', 'error')
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('custo_veiculo_editar.html',
                                 custo=custo,
                                 veiculo=veiculo,
                                 obras=obras)
        
    except Exception as e:
        print(f"❌ [FROTA_EDITAR_CUSTO] Erro: {str(e)}")
        flash('Erro ao editar custo do veículo.', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DELETAR CUSTO DE VEÍCULO DA FROTA =====
@frota_bp.route('/custo/<int:custo_id>/deletar', methods=['POST'])
@login_required
def deletar_custo(custo_id):
    """Deleta um custo de veículo da frota"""
    try:
        print(f"🗑️ [FROTA_DELETAR_CUSTO] Iniciando para custo {custo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar custo da frota
        custo = FrotaDespesa.query.filter_by(id=custo_id, admin_id=tenant_admin_id).first()
        if not custo:
            flash('Custo de veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        veiculo_id = custo.veiculo_id
        
        db.session.delete(custo)
        db.session.commit()
        
        flash('Custo do veículo deletado com sucesso!', 'success')
        return redirect(url_for('frota.detalhes', id=veiculo_id))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [FROTA_DELETAR_CUSTO] Erro: {str(e)}")
        flash(f'Erro ao deletar custo: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DELETAR VEÍCULO DA FROTA (SOFT DELETE) =====
@frota_bp.route('/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_veiculo(id):
    """Deleta um veículo da frota (soft delete)"""
    try:
        print(f"🗑️ [FROTA_DELETAR_VEICULO] Iniciando para veículo {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('auth.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        # Soft delete (marcar como inativo)
        veiculo.ativo = False
        if hasattr(veiculo, 'updated_at'):
            veiculo.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Veículo {veiculo.placa} removido com sucesso!', 'success')
        return redirect(url_for('frota.lista'))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [FROTA_DELETAR_VEICULO] Erro: {str(e)}")
        flash(f'Erro ao deletar veículo: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))
