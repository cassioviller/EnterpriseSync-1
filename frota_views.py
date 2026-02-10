from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Veiculo as FrotaVeiculo, UsoVeiculo as FrotaUtilizacao, CustoVeiculo as FrotaDespesa, Funcionario, Obra
from app import db
from utils.tenant import get_tenant_admin_id
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

frota_bp = Blueprint('frota', __name__, url_prefix='/frota')

# Importar services de veículos (adaptados para frota)
try:
    from veiculos_services import VeiculoService, UsoVeiculoService, CustoVeiculoService
    logger.info("[OK] [FROTA] Services importados com sucesso")
except ImportError as e:
    logger.error(f"[WARN] [FROTA] Erro ao importar services: {e}")
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
        logger.info(f"[CAR] [FROTA_LISTA] Iniciando listagem...")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        # DEBUG: print(f"[DEBUG] [FROTA_LISTA] tenant_admin_id = {tenant_admin_id}")
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        # DEBUG: print(f"[DEBUG] [FROTA_LISTA] Query inicial: admin_id={tenant_admin_id}")
        
        # Aplicar filtros
        if filtros.get('status'):
            if filtros['status'] == 'ativo':
                query = query.filter_by(ativo=True)
                # DEBUG: print(f"[DEBUG] [FROTA_LISTA] Filtro aplicado: ativo=True")
            elif filtros['status'] == 'inativo':
                query = query.filter_by(ativo=False)
                # DEBUG: print(f"[DEBUG] [FROTA_LISTA] Filtro aplicado: ativo=False")
        else:
            # [OK] CORREÇÃO: Por padrão, mostrar apenas veículos ativos
            query = query.filter_by(ativo=True)
            # DEBUG: print(f"[DEBUG] [FROTA_LISTA] Filtro padrão aplicado: ativo=True")
        
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
        
        logger.info(f"[STATS] [FROTA_LISTA] Stats: total={stats['total']}, ativos={stats['ativos']}, inativos={stats['inativos']}")
        logger.info(f"[OK] [FROTA_LISTA] Encontrados {len(veiculos)} veículos na query paginada")
        if veiculos:
            logger.debug(f"[CAR] [FROTA_LISTA] Primeiro veículo: {veiculos[0].placa} (id={veiculos[0].id})")
        
        return render_template('veiculos_lista.html',
                             veiculos=veiculos,
                             pagination=pagination,
                             stats=stats,
                             filtros_aplicados=filtros)
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_LISTA] Erro: {str(e)}")
        flash('Erro ao carregar veículos. Tente novamente.', 'error')
        return redirect(url_for('main.dashboard'))


# ===== ROTA: NOVO VEÍCULO DA FROTA =====
@frota_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    """Formulário para cadastrar novo veículo na frota"""
    try:
        logger.info(f"[CAR] [FROTA_NOVO] Iniciando...")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
        if request.method == 'GET':
            return render_template('veiculos_novo.html')
        
        # POST - Processar cadastro
        dados = request.form.to_dict()
        # DEBUG: print(f"[DEBUG] [FROTA_NOVO] Dados recebidos: {dados.keys()}")
        
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
            logger.error(f"[ERROR] [FROTA_NOVO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao cadastrar veículo: {str(e)}', 'error')
            return render_template('veiculos_novo.html')
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_NOVO] Erro: {str(e)}")
        flash('Erro ao cadastrar veículo. Tente novamente.', 'error')
        return render_template('veiculos_novo.html')


# ===== ROTA: DETALHES DO VEÍCULO DA FROTA =====
@frota_bp.route('/<int:id>')
@login_required  
def detalhes(id):
    """Página de detalhes do veículo da frota com abas de uso e custos"""
    try:
        logger.info(f"[CAR] [FROTA_DETALHES] Iniciando para ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        # Buscar funcionários para exibir nomes nos passageiros
        funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id).all()
        # DEBUG: print(f"[DEBUG] [FROTA_DETALHES] {len(funcionarios)} funcionários encontrados")
        
        # Buscar usos recentes (últimos 20) com tratamento de erro
        try:
            # DEBUG: print(f"[DEBUG] [FROTA_DETALHES] Buscando usos do veículo ID={id}, admin_id={tenant_admin_id}")
            usos = FrotaUtilizacao.query.filter_by(
                veiculo_id=id,
                admin_id=tenant_admin_id
            ).order_by(FrotaUtilizacao.data_uso.desc()).limit(20).all()
            logger.info(f"[OK] [FROTA_DETALHES] {len(usos)} usos encontrados")
            
            # Debug: mostrar os primeiros usos
            if usos:
                for uso in usos[:3]:
                    logger.debug(f" [LIST] Uso: ID={uso.id}, Data={uso.data_uso}, Veiculo={uso.veiculo_id}, Admin={uso.admin_id}")
            else:
                # Verificar se existem usos SEM filtro de admin_id
                total_usos_veiculo = FrotaUtilizacao.query.filter_by(veiculo_id=id).count()
                logger.warning(f"[WARN] [FROTA_DETALHES] Total de usos do veículo (sem filtro admin): {total_usos_veiculo}")
                if total_usos_veiculo > 0:
                    # Verificar admin_id dos usos existentes
                    uso_sample = FrotaUtilizacao.query.filter_by(veiculo_id=id).first()
                    logger.warning(f"[WARN] [FROTA_DETALHES] Uso existente tem admin_id={uso_sample.admin_id}, esperado={tenant_admin_id}")
        except Exception as e_usos:
            logger.error(f"[WARN] [FROTA_DETALHES] Erro ao buscar usos: {str(e_usos)}")
            import traceback
            logger.info(traceback.format_exc())
            usos = []
        
        # Estatísticas de uso com tratamento de erro
        try:
            stats_uso = {
                'total': FrotaUtilizacao.query.filter_by(veiculo_id=id, admin_id=tenant_admin_id).count(),
                'km_total': db.session.query(db.func.sum(FrotaUtilizacao.km_percorrido)).filter_by(
                    veiculo_id=id, admin_id=tenant_admin_id
                ).scalar() or 0
            }
        except Exception as e_stats:
            logger.error(f"[WARN] [FROTA_DETALHES] Erro ao calcular stats de uso: {str(e_stats)}")
            stats_uso = {'total': 0, 'km_total': 0}
        
        # Buscar custos recentes com tratamento de erro
        try:
            custos = FrotaDespesa.query.filter_by(
                veiculo_id=id,
                admin_id=tenant_admin_id
            ).order_by(FrotaDespesa.data_custo.desc()).limit(20).all()
            logger.info(f"[OK] [FROTA_DETALHES] {len(custos)} custos encontrados")
        except Exception as e_custos:
            logger.error(f"[WARN] [FROTA_DETALHES] Erro ao buscar custos: {str(e_custos)}")
            custos = []
        
        # Estatísticas de custos com tratamento de erro
        try:
            stats_custos = {
                'total': FrotaDespesa.query.filter_by(veiculo_id=id, admin_id=tenant_admin_id).count(),
                'valor_total': db.session.query(db.func.sum(FrotaDespesa.valor)).filter_by(
                    veiculo_id=id, admin_id=tenant_admin_id
                ).scalar() or 0
            }
        except Exception as e_stats_custos:
            logger.error(f"[WARN] [FROTA_DETALHES] Erro ao calcular stats de custos: {str(e_stats_custos)}")
            stats_custos = {'total': 0, 'valor_total': 0}
        
        return render_template('veiculos_detalhes.html',
                             veiculo=veiculo,
                             funcionarios=funcionarios,
                             usos=usos,
                             stats_uso=stats_uso,
                             custos=custos,
                             stats_custos=stats_custos)
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_DETALHES] Erro: {str(e)}")
        flash('Erro ao carregar detalhes do veículo.', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: EDITAR VEÍCULO DA FROTA =====
@frota_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Formulário para editar dados do veículo da frota"""
    try:
        logger.info(f"[CAR] [FROTA_EDITAR] Iniciando para ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
        # Buscar veículo da frota
        veiculo = FrotaVeiculo.query.filter_by(id=id, admin_id=tenant_admin_id).first()
        if not veiculo:
            flash('Veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        if request.method == 'GET':
            return render_template('veiculos_editar.html', veiculo=veiculo)
        
        # POST - Processar edição
        dados = request.form.to_dict()
        # DEBUG: print(f"[DEBUG] [FROTA_EDITAR] Dados recebidos: {dados.keys()}")
        
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
            logger.error(f"[ERROR] [FROTA_EDITAR] Erro ao salvar: {str(e)}")
            flash(f'Erro ao atualizar veículo: {str(e)}', 'error')
            return render_template('veiculos_editar.html', veiculo=veiculo)
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_EDITAR] Erro: {str(e)}")
        flash('Erro ao editar veículo.', 'error')
        return redirect(url_for('frota.detalhes', id=id))


# ===== ROTA: REATIVAR VEÍCULO INATIVO =====
@frota_bp.route('/<int:id>/reativar', methods=['POST'])
@login_required
def reativar(id):
    """Reativar um veículo inativo"""
    try:
        logger.debug(f"[CAR] [FROTA_REATIVAR] Reativando veículo ID {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        logger.info(f"[OK] [FROTA_REATIVAR] Veículo {veiculo.placa} reativado")
        
        return redirect(url_for('frota.lista'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] [FROTA_REATIVAR] Erro: {str(e)}")
        flash(f'Erro ao reativar veículo: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: NOVO USO DE VEÍCULO DA FROTA =====
@frota_bp.route('/<int:veiculo_id>/uso/novo', methods=['GET', 'POST'])
@login_required
def novo_uso(veiculo_id):
    """Formulário unificado para novo uso de veículo da frota (uso + custos)"""
    try:
        logger.info(f"[CAR] [FROTA_NOVO_USO] Iniciando para veículo {veiculo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        
        # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Dados recebidos: {dados.keys()}")
        # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Passageiros Frente: '{dados.get('passageiros_frente')}'")
        # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Passageiros Trás: '{dados.get('passageiros_tras')}'")
        
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
            # [READY] RECEBER PASSAGEIROS DE SELECT MULTIPLE (retorna lista de IDs)
            passageiros_frente_list = request.form.getlist('passageiros_frente')
            passageiros_tras_list = request.form.getlist('passageiros_tras')
            
            # Converter lista de IDs para string CSV
            passageiros_frente_csv = ','.join(passageiros_frente_list) if passageiros_frente_list else ''
            passageiros_tras_csv = ','.join(passageiros_tras_list) if passageiros_tras_list else ''
            
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
                passageiros_frente=passageiros_frente_csv,
                passageiros_tras=passageiros_tras_csv,
                responsavel_veiculo=dados.get('responsavel_veiculo'),
                observacoes=dados.get('observacoes'),
                admin_id=tenant_admin_id
            )
            
            # Calcular KM percorrido
            if novo_uso.km_inicial and novo_uso.km_final:
                novo_uso.km_percorrido = novo_uso.km_final - novo_uso.km_inicial
            
            db.session.add(novo_uso)
            
            # [CAR] ATUALIZAR KM ATUAL DO VEÍCULO
            if novo_uso.km_final:
                veiculo.km_atual = novo_uso.km_final
                logger.info(f"[OK] [FROTA_NOVO_USO] KM Atual do veículo atualizado: {veiculo.km_atual} km")
            
            # [DEBUG] DEBUG: Verificar campos de passageiros antes do commit
            # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Antes do commit - Passageiros Frente: '{novo_uso.passageiros_frente}'")
            # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Antes do commit - Passageiros Trás: '{novo_uso.passageiros_tras}'")
            
            db.session.commit()
            
            # [DEBUG] DEBUG: Verificar campos de passageiros após o commit
            db.session.refresh(novo_uso)
            # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Após o commit - Passageiros Frente: '{novo_uso.passageiros_frente}'")
            # DEBUG: print(f"[DEBUG] [FROTA_NOVO_USO] Após o commit - Passageiros Trás: '{novo_uso.passageiros_tras}'")
            
            # [LINK] INTEGRAÇÃO AUTOMÁTICA - Emitir evento de veículo usado
            try:
                from event_manager import EventManager
                EventManager.emit('veiculo_usado', {
                    'uso_id': novo_uso.id,
                    'veiculo_id': veiculo_id,
                    'obra_id': novo_uso.obra_id,
                    'km_percorrido': novo_uso.km_percorrido or 0,
                    'funcionario_id': novo_uso.funcionario_id
                }, tenant_admin_id)
            except Exception as e:
                logger.error(f'Integração automática falhou (não crítico): {e}')
            
            flash(f'Uso do veículo registrado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=veiculo_id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] [FROTA_NOVO_USO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao registrar uso: {str(e)}', 'error')
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('uso_veiculo_novo.html',
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_NOVO_USO] Erro: {str(e)}")
        flash('Erro ao registrar uso do veículo.', 'error')
        return redirect(url_for('frota.detalhes', id=veiculo_id))


# ===== ROTA: NOVO CUSTO DE VEÍCULO DA FROTA =====
@frota_bp.route('/<int:veiculo_id>/custo/novo', methods=['GET', 'POST'])
@login_required
def novo_custo(veiculo_id):
    """Formulário para registrar novos custos de veículo da frota"""
    try:
        logger.info(f"[MONEY] [FROTA_NOVO_CUSTO] Iniciando para veículo {veiculo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        
        # DEBUG: print(f"[DEBUG] [FROTA_NOVO_CUSTO] Dados recebidos: {dados.keys()}")
        
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
                obra_id=int(dados['obra_id']) if dados.get('obra_id') else None,
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
            logger.error(f"[ERROR] [FROTA_NOVO_CUSTO] Erro ao salvar: {str(e)}")
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
        logger.error(f"[ERROR] [FROTA_NOVO_CUSTO] Erro: {str(e)}")
        flash('Erro ao registrar custo do veículo.', 'error')
        return redirect(url_for('frota.detalhes', id=veiculo_id))


# ===== ROTA: EDITAR USO DE VEÍCULO DA FROTA =====
@frota_bp.route('/uso/<int:uso_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_uso(uso_id):
    """Formulário para editar uso existente de veículo da frota"""
    try:
        logger.info(f"[EDIT] [FROTA_EDITAR_USO] Iniciando para uso {uso_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        # DEBUG: print(f"[DEBUG] [FROTA_EDITAR_USO] Dados recebidos: {dados.keys()}")
        
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
            
            # [CAR] ATUALIZAR KM ATUAL DO VEÍCULO (se editou km_final)
            if dados.get('km_final'):
                # Verificar se esse uso é o mais recente
                ultimo_uso = FrotaUtilizacao.query.filter_by(
                    veiculo_id=veiculo.id,
                    admin_id=tenant_admin_id
                ).order_by(FrotaUtilizacao.data_uso.desc(), FrotaUtilizacao.id.desc()).first()
                
                if ultimo_uso and ultimo_uso.id == uso.id and ultimo_uso.km_final:
                    veiculo.km_atual = ultimo_uso.km_final
                    logger.info(f"[OK] [FROTA_EDITAR_USO] KM Atual do veículo atualizado: {veiculo.km_atual} km")
            
            db.session.commit()
            
            flash('Uso do veículo atualizado com sucesso!', 'success')
            return redirect(url_for('frota.detalhes', id=veiculo.id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] [FROTA_EDITAR_USO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao atualizar uso: {str(e)}', 'error')
            funcionarios = Funcionario.query.filter_by(admin_id=tenant_admin_id, ativo=True).all()
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('uso_veiculo_editar.html',
                                 uso=uso,
                                 veiculo=veiculo,
                                 funcionarios=funcionarios,
                                 obras=obras)
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_EDITAR_USO] Erro: {str(e)}")
        flash('Erro ao editar uso do veículo.', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DELETAR USO DE VEÍCULO DA FROTA =====
@frota_bp.route('/uso/<int:uso_id>/deletar', methods=['POST'])
@login_required
def deletar_uso(uso_id):
    """Deleta um uso de veículo da frota"""
    try:
        logger.info(f"[DEL] [FROTA_DELETAR_USO] Iniciando para uso {uso_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
        # Buscar uso da frota
        uso = FrotaUtilizacao.query.filter_by(id=uso_id, admin_id=tenant_admin_id).first()
        if not uso:
            flash('Uso de veículo não encontrado.', 'error')
            return redirect(url_for('frota.lista'))
        
        veiculo_id = uso.veiculo_id
        
        # Buscar veículo antes de deletar
        veiculo = FrotaVeiculo.query.filter_by(id=veiculo_id, admin_id=tenant_admin_id).first()
        
        # [DEL] DELETAR REGISTROS DA TABELA LEGADA passageiro_veiculo (CASCADE)
        # TODO: Promover para ORM-level cascade relationship quando refatorar modelos
        # Architect recomendou substituir raw SQL por configuração cascade="all, delete-orphan"
        try:
            db.session.execute(
                db.text("DELETE FROM passageiro_veiculo WHERE uso_veiculo_id = :uso_id"),
                {"uso_id": uso_id}
            )
            logger.info(f"[OK] [FROTA_DELETAR_USO] Registros de passageiro_veiculo deletados")
        except Exception as e:
            logger.error(f"[WARN] [FROTA_DELETAR_USO] Erro ao deletar passageiros (tabela pode não existir): {e}")
        
        db.session.delete(uso)
        db.session.flush()
        
        # [CAR] ATUALIZAR KM ATUAL DO VEÍCULO após deleção
        if veiculo:
            # Buscar o último uso restante (após a deleção)
            ultimo_uso = FrotaUtilizacao.query.filter_by(
                veiculo_id=veiculo_id,
                admin_id=tenant_admin_id
            ).order_by(FrotaUtilizacao.data_uso.desc(), FrotaUtilizacao.id.desc()).first()
            
            if ultimo_uso and ultimo_uso.km_final:
                veiculo.km_atual = ultimo_uso.km_final
                logger.info(f"[OK] [FROTA_DELETAR_USO] KM Atual atualizado para último uso: {veiculo.km_atual} km")
            else:
                # Se não houver mais usos, manter o km_atual do veículo
                logger.debug(f"[INFO] [FROTA_DELETAR_USO] Nenhum uso restante, km_atual mantido")
        
        db.session.commit()
        
        flash('Uso do veículo deletado com sucesso!', 'success')
        return redirect(url_for('frota.detalhes', id=veiculo_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] [FROTA_DELETAR_USO] Erro: {str(e)}")
        flash(f'Erro ao deletar uso: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: EDITAR CUSTO DE VEÍCULO DA FROTA =====
@frota_bp.route('/custo/<int:custo_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_custo(custo_id):
    """Formulário para editar custo existente de veículo da frota"""
    try:
        logger.info(f"[EDIT] [FROTA_EDITAR_CUSTO] Iniciando para custo {custo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        # DEBUG: print(f"[DEBUG] [FROTA_EDITAR_CUSTO] Dados recebidos: {dados.keys()}")
        
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
            logger.error(f"[ERROR] [FROTA_EDITAR_CUSTO] Erro ao salvar: {str(e)}")
            flash(f'Erro ao atualizar custo: {str(e)}', 'error')
            obras = Obra.query.filter_by(admin_id=tenant_admin_id).all()
            return render_template('custo_veiculo_editar.html',
                                 custo=custo,
                                 veiculo=veiculo,
                                 obras=obras)
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_EDITAR_CUSTO] Erro: {str(e)}")
        flash('Erro ao editar custo do veículo.', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DELETAR CUSTO DE VEÍCULO DA FROTA =====
@frota_bp.route('/custo/<int:custo_id>/deletar', methods=['POST'])
@login_required
def deletar_custo(custo_id):
    """Deleta um custo de veículo da frota"""
    try:
        logger.info(f"[DEL] [FROTA_DELETAR_CUSTO] Iniciando para custo {custo_id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        logger.error(f"[ERROR] [FROTA_DELETAR_CUSTO] Erro: {str(e)}")
        flash(f'Erro ao deletar custo: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DELETAR VEÍCULO DA FROTA (SOFT DELETE) =====
@frota_bp.route('/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_veiculo(id):
    """Deleta um veículo da frota (soft delete)"""
    try:
        logger.info(f"[DEL] [FROTA_DELETAR_VEICULO] Iniciando para veículo {id}")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
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
        logger.error(f"[ERROR] [FROTA_DELETAR_VEICULO] Erro: {str(e)}")
        flash(f'Erro ao deletar veículo: {str(e)}', 'error')
        return redirect(url_for('frota.lista'))


# ===== ROTA: DASHBOARD TCO (TOTAL COST OF OWNERSHIP) =====
@frota_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard TCO (Total Cost of Ownership) da Frota"""
    try:
        from sqlalchemy import func, desc
        from decimal import Decimal
        from datetime import datetime, date
        from dateutil.relativedelta import relativedelta
        
        logger.info(f"[STATS] [FROTA_DASHBOARD] Iniciando dashboard TCO...")
        
        # Proteção multi-tenant
        tenant_admin_id = get_tenant_admin_id()
        if not tenant_admin_id:
            flash('Acesso negado. Faça login novamente.', 'error')
            return redirect(url_for('main.login'))
        
        # Capturar filtros da URL
        filtro_tipo = request.args.get('tipo')
        filtro_data_inicio = request.args.get('data_inicio')
        filtro_data_fim = request.args.get('data_fim')
        filtro_status = request.args.get('status', 'ativo')  # Padrão: apenas ativos
        
        # Converter datas se fornecidas
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date() if filtro_data_inicio else None
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date() if filtro_data_fim else None
        
        # Query base para despesas (custos)
        query_custos = FrotaDespesa.query.filter_by(admin_id=tenant_admin_id)
        
        # Aplicar filtros de data
        if data_inicio:
            query_custos = query_custos.filter(FrotaDespesa.data_custo >= data_inicio)
        if data_fim:
            query_custos = query_custos.filter(FrotaDespesa.data_custo <= data_fim)
        
        # Aplicar filtro de tipo de veículo (join com Vehicle)
        if filtro_tipo:
            query_custos = query_custos.join(FrotaVeiculo).filter(FrotaVeiculo.tipo == filtro_tipo)
        
        # Aplicar filtro de status (apenas veículos ativos/inativos)
        if filtro_status == 'ativo':
            query_custos = query_custos.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            query_custos = query_custos.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == False)
        
        # KPI 1: TCO Total (Total Cost of Ownership)
        tco_total = db.session.query(
            func.coalesce(func.sum(FrotaDespesa.valor), Decimal('0'))
        ).filter(FrotaDespesa.admin_id == tenant_admin_id)
        
        if data_inicio:
            tco_total = tco_total.filter(FrotaDespesa.data_custo >= data_inicio)
        if data_fim:
            tco_total = tco_total.filter(FrotaDespesa.data_custo <= data_fim)
        if filtro_tipo:
            tco_total = tco_total.join(FrotaVeiculo).filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            tco_total = tco_total.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            tco_total = tco_total.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == False)
        
        tco_total = float(tco_total.scalar() or 0)
        
        # KPI 2: Total de KM percorridos (para calcular custo médio/km)
        query_km = db.session.query(
            func.coalesce(func.sum(FrotaUtilizacao.km_percorrido), 0)
        ).filter(FrotaUtilizacao.admin_id == tenant_admin_id)
        
        if data_inicio:
            query_km = query_km.filter(FrotaUtilizacao.data_uso >= data_inicio)
        if data_fim:
            query_km = query_km.filter(FrotaUtilizacao.data_uso <= data_fim)
        if filtro_tipo:
            query_km = query_km.join(FrotaVeiculo).filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            query_km = query_km.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            query_km = query_km.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == False)
        
        total_km = query_km.scalar() or 0
        custo_medio_km = round(tco_total / total_km, 2) if total_km > 0 else 0
        
        # KPI 3: Total de Veículos
        query_veiculos = FrotaVeiculo.query.filter_by(admin_id=tenant_admin_id)
        if filtro_tipo:
            query_veiculos = query_veiculos.filter_by(tipo=filtro_tipo)
        if filtro_status == 'ativo':
            query_veiculos = query_veiculos.filter_by(ativo=True)
        elif filtro_status == 'inativo':
            query_veiculos = query_veiculos.filter_by(ativo=False)
        
        total_veiculos = query_veiculos.count()
        
        # KPI 4: Custos do Mês Atual (com comparação)
        hoje = date.today()
        inicio_mes_atual = date(hoje.year, hoje.month, 1)
        inicio_mes_anterior = (inicio_mes_atual - relativedelta(months=1))
        fim_mes_anterior = inicio_mes_atual - relativedelta(days=1)
        
        # Custos do mês atual
        query_mes_atual = db.session.query(
            func.coalesce(func.sum(FrotaDespesa.valor), Decimal('0'))
        ).filter(
            FrotaDespesa.admin_id == tenant_admin_id,
            FrotaDespesa.data_custo >= inicio_mes_atual
        )
        if filtro_tipo:
            query_mes_atual = query_mes_atual.join(FrotaVeiculo).filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            query_mes_atual = query_mes_atual.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            query_mes_atual = query_mes_atual.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == False)
        
        custos_mes_atual = float(query_mes_atual.scalar() or 0)
        
        # Custos do mês anterior
        query_mes_anterior = db.session.query(
            func.coalesce(func.sum(FrotaDespesa.valor), Decimal('0'))
        ).filter(
            FrotaDespesa.admin_id == tenant_admin_id,
            FrotaDespesa.data_custo >= inicio_mes_anterior,
            FrotaDespesa.data_custo <= fim_mes_anterior
        )
        if filtro_tipo:
            query_mes_anterior = query_mes_anterior.join(FrotaVeiculo).filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            query_mes_anterior = query_mes_anterior.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            query_mes_anterior = query_mes_anterior.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == False)
        
        custos_mes_anterior = float(query_mes_anterior.scalar() or 0)
        
        # Calcular variação percentual
        if custos_mes_anterior > 0:
            variacao_percentual = round(((custos_mes_atual - custos_mes_anterior) / custos_mes_anterior) * 100, 1)
        else:
            variacao_percentual = 100.0 if custos_mes_atual > 0 else 0.0
        
        # Gráfico 1: Custos por Tipo de Veículo (Pizza)
        custos_por_tipo = db.session.query(
            FrotaVeiculo.tipo,
            func.sum(FrotaDespesa.valor).label('total')
        ).join(FrotaDespesa).filter(
            FrotaDespesa.admin_id == tenant_admin_id
        )
        
        if data_inicio:
            custos_por_tipo = custos_por_tipo.filter(FrotaDespesa.data_custo >= data_inicio)
        if data_fim:
            custos_por_tipo = custos_por_tipo.filter(FrotaDespesa.data_custo <= data_fim)
        if filtro_tipo:
            custos_por_tipo = custos_por_tipo.filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            custos_por_tipo = custos_por_tipo.filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            custos_por_tipo = custos_por_tipo.filter(FrotaVeiculo.ativo == False)
        
        custos_por_tipo = custos_por_tipo.group_by(FrotaVeiculo.tipo).all()
        
        # Gráfico 2: Evolução Mensal de Custos (Linha)
        evolucao_mensal = db.session.query(
            func.to_char(FrotaDespesa.data_custo, 'YYYY-MM').label('mes'),
            func.sum(FrotaDespesa.valor).label('total')
        ).filter(
            FrotaDespesa.admin_id == tenant_admin_id
        )
        
        if data_inicio:
            evolucao_mensal = evolucao_mensal.filter(FrotaDespesa.data_custo >= data_inicio)
        if data_fim:
            evolucao_mensal = evolucao_mensal.filter(FrotaDespesa.data_custo <= data_fim)
        if filtro_tipo:
            evolucao_mensal = evolucao_mensal.join(FrotaVeiculo).filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            evolucao_mensal = evolucao_mensal.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            evolucao_mensal = evolucao_mensal.join(FrotaVeiculo).filter(FrotaVeiculo.ativo == False)
        
        evolucao_mensal = evolucao_mensal.group_by(
            func.to_char(FrotaDespesa.data_custo, 'YYYY-MM')
        ).order_by(desc('mes')).limit(6).all()
        
        # Gráfico 3: Top 5 Veículos com Maior Custo
        top_veiculos = db.session.query(
            FrotaVeiculo.placa,
            FrotaVeiculo.id,
            func.sum(FrotaDespesa.valor).label('total_custos')
        ).join(FrotaDespesa).filter(
            FrotaDespesa.admin_id == tenant_admin_id,
            FrotaVeiculo.admin_id == tenant_admin_id
        )
        
        if data_inicio:
            top_veiculos = top_veiculos.filter(FrotaDespesa.data_custo >= data_inicio)
        if data_fim:
            top_veiculos = top_veiculos.filter(FrotaDespesa.data_custo <= data_fim)
        if filtro_tipo:
            top_veiculos = top_veiculos.filter(FrotaVeiculo.tipo == filtro_tipo)
        if filtro_status == 'ativo':
            top_veiculos = top_veiculos.filter(FrotaVeiculo.ativo == True)
        elif filtro_status == 'inativo':
            top_veiculos = top_veiculos.filter(FrotaVeiculo.ativo == False)
        
        top_veiculos = top_veiculos.group_by(FrotaVeiculo.id, FrotaVeiculo.placa).order_by(
            desc('total_custos')
        ).limit(5).all()
        
        # Buscar tipos de veículos disponíveis para o filtro
        tipos_disponiveis = db.session.query(FrotaVeiculo.tipo).filter_by(
            admin_id=tenant_admin_id
        ).distinct().all()
        tipos_disponiveis = [t[0] for t in tipos_disponiveis]
        
        logger.info(f"[OK] [FROTA_DASHBOARD] KPIs calculados: TCO={tco_total}, Custo/km={custo_medio_km}, Veículos={total_veiculos}")
        
        return render_template('frota/dashboard.html',
                             tco_total=tco_total,
                             custo_medio_km=custo_medio_km,
                             total_veiculos=total_veiculos,
                             custos_mes_atual=custos_mes_atual,
                             variacao_percentual=variacao_percentual,
                             custos_por_tipo=custos_por_tipo,
                             evolucao_mensal=evolucao_mensal,
                             top_veiculos=top_veiculos,
                             tipos_disponiveis=tipos_disponiveis,
                             filtros={
                                 'tipo': filtro_tipo,
                                 'data_inicio': filtro_data_inicio,
                                 'data_fim': filtro_data_fim,
                                 'status': filtro_status
                             })
        
    except Exception as e:
        logger.error(f"[ERROR] [FROTA_DASHBOARD] Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar dashboard de frota. Tente novamente.', 'error')
        return redirect(url_for('frota.lista'))


# ===== FUNÇÃO AUXILIAR: VERIFICAR ALERTAS DE VEÍCULOS =====
def verificar_alertas(admin_id):
    """
    Verifica alertas de manutenção e vencimentos para veículos da frota.
    Retorna lista de veículos que precisam de atenção.
    
    [OK] TAREFA 6: Sistema de alertas implementado
    """
    from datetime import date, timedelta
    
    alertas = []
    hoje = date.today()
    prazo_alerta = hoje + timedelta(days=30)  # Alertar com 30 dias de antecedência
    
    # Buscar veículos ativos do admin
    veiculos = FrotaVeiculo.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    for veiculo in veiculos:
        alerta_veiculo = {
            'veiculo_id': veiculo.id,
            'placa': veiculo.placa,
            'modelo': f"{veiculo.marca} {veiculo.modelo}",
            'alertas': []
        }
        
        # Alerta 1: Manutenção por KM
        if veiculo.km_proxima_manutencao and veiculo.km_atual:
            km_restantes = veiculo.km_proxima_manutencao - veiculo.km_atual
            if km_restantes <= 500:  # Alertar quando faltam 500km ou menos
                alerta_veiculo['alertas'].append({
                    'tipo': 'manutencao_km',
                    'mensagem': f'Manutenção próxima: faltam {km_restantes}km',
                    'urgencia': 'alta' if km_restantes <= 100 else 'media'
                })
        
        # Alerta 2: Manutenção por Data
        if veiculo.data_proxima_manutencao:
            if veiculo.data_proxima_manutencao <= hoje:
                alerta_veiculo['alertas'].append({
                    'tipo': 'manutencao_vencida',
                    'mensagem': f'Manutenção VENCIDA desde {veiculo.data_proxima_manutencao.strftime("%d/%m/%Y")}',
                    'urgencia': 'critica'
                })
            elif veiculo.data_proxima_manutencao <= prazo_alerta:
                dias_restantes = (veiculo.data_proxima_manutencao - hoje).days
                alerta_veiculo['alertas'].append({
                    'tipo': 'manutencao_proxima',
                    'mensagem': f'Manutenção em {dias_restantes} dias',
                    'urgencia': 'media' if dias_restantes > 15 else 'alta'
                })
        
        # Alerta 3: IPVA Vencido/Próximo
        if veiculo.data_vencimento_ipva:
            if veiculo.data_vencimento_ipva <= hoje:
                alerta_veiculo['alertas'].append({
                    'tipo': 'ipva_vencido',
                    'mensagem': f'IPVA VENCIDO desde {veiculo.data_vencimento_ipva.strftime("%d/%m/%Y")}',
                    'urgencia': 'critica'
                })
            elif veiculo.data_vencimento_ipva <= prazo_alerta:
                dias_restantes = (veiculo.data_vencimento_ipva - hoje).days
                alerta_veiculo['alertas'].append({
                    'tipo': 'ipva_proximo',
                    'mensagem': f'IPVA vence em {dias_restantes} dias',
                    'urgencia': 'media' if dias_restantes > 15 else 'alta'
                })
        
        # Alerta 4: Seguro Vencido/Próximo
        if veiculo.data_vencimento_seguro:
            if veiculo.data_vencimento_seguro <= hoje:
                alerta_veiculo['alertas'].append({
                    'tipo': 'seguro_vencido',
                    'mensagem': f'Seguro VENCIDO desde {veiculo.data_vencimento_seguro.strftime("%d/%m/%Y")}',
                    'urgencia': 'critica'
                })
            elif veiculo.data_vencimento_seguro <= prazo_alerta:
                dias_restantes = (veiculo.data_vencimento_seguro - hoje).days
                alerta_veiculo['alertas'].append({
                    'tipo': 'seguro_proximo',
                    'mensagem': f'Seguro vence em {dias_restantes} dias',
                    'urgencia': 'media' if dias_restantes > 15 else 'alta'
                })
        
        # Adicionar veículo à lista apenas se tiver alertas
        if alerta_veiculo['alertas']:
            alertas.append(alerta_veiculo)
    
    # Ordenar alertas por urgência (crítica > alta > média)
    urgencia_ordem = {'critica': 0, 'alta': 1, 'media': 2}
    alertas.sort(key=lambda x: min([urgencia_ordem.get(a['urgencia'], 3) for a in x['alertas']]))
    
    return alertas
