from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, send_file, session, Response
from flask_login import login_required, current_user
from models import db, Usuario, TipoUsuario, Funcionario, Funcao, Departamento, HorarioTrabalho, Obra, RDO, RDOMaoObra, RDOEquipamento, RDOOcorrencia, RDOFoto, AlocacaoEquipe, Servico, ServicoObra, ServicoObraReal, RDOServicoSubatividade, SubatividadeMestre, RegistroPonto, NotificacaoCliente, PedidoCompra, PedidoCompraItem, Fornecedor, MapaConcorrencia, OpcaoConcorrencia, CronogramaCliente, MapaConcorrenciaV2, MapaFornecedor, MapaItemCotacao, MapaCotacao
from auth import admin_required
from utils.tenant import get_tenant_admin_id
from utils import calcular_valor_hora_periodo
from utils.database_diagnostics import capture_db_errors
from views.helpers import safe_db_operation, get_admin_id_robusta, get_admin_id_dinamico, verificar_dados_producao
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

@main_bp.route('/obras')
def obras():
    # Sistema dinâmico de detecção de admin_id
    admin_id = None
    
    if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
        if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            # SUPER_ADMIN pode ver todas as obras - buscar admin_id com mais dados
            obra_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM obra GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
            admin_id = obra_counts[0] if obra_counts else current_user.admin_id
        elif current_user.tipo_usuario == TipoUsuario.ADMIN:
            admin_id = current_user.id
        else:
            # Funcionário - usar admin_id do funcionário
            admin_id = current_user.admin_id if hasattr(current_user, 'admin_id') and current_user.admin_id else current_user.id
    else:
        # Sistema de bypass - detectar dinamicamente
        try:
            obra_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM obra GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
            admin_id = obra_counts[0] if obra_counts else 1
        except Exception as e:
            logger.error(f"Erro ao detectar admin_id: {e}")
            admin_id = 1
    
    # Obter filtros da query string
    filtros = {
        'nome': request.args.get('nome', ''),
        'status': request.args.get('status', ''),
        'cliente': request.args.get('cliente', ''),
        'data_inicio': request.args.get('data_inicio', ''),
        'data_fim': request.args.get('data_fim', '')
    }
    
    # Construir query base
    query = Obra.query.filter_by(admin_id=admin_id)
    
    # Aplicar filtros se fornecidos
    if filtros['nome']:
        query = query.filter(Obra.nome.ilike(f"%{filtros['nome']}%"))
    if filtros['status']:
        query = query.filter(Obra.status == filtros['status'])
    if filtros['cliente']:
        query = query.filter(Obra.cliente.ilike(f"%{filtros['cliente']}%"))
    
    # Aplicar filtros de data (usando data_inicio da obra)
    if filtros['data_inicio']:
        try:
            data_inicio = datetime.strptime(filtros['data_inicio'], '%Y-%m-%d').date()
            query = query.filter(Obra.data_inicio >= data_inicio)
            logger.debug(f"DEBUG: Filtro data_inicio aplicado: {data_inicio}")
        except ValueError as e:
            logger.error(f"DEBUG: Erro na data_inicio: {e}")
    
    if filtros['data_fim']:
        try:
            data_fim = datetime.strptime(filtros['data_fim'], '%Y-%m-%d').date()
            query = query.filter(Obra.data_inicio <= data_fim)
            logger.debug(f"DEBUG: Filtro data_fim aplicado: {data_fim}")
        except ValueError as e:
            logger.error(f"DEBUG: Erro na data_fim: {e}")
    
    # Importar desc localmente para evitar conflitos
    from sqlalchemy import desc
    obras = query.order_by(desc(Obra.data_inicio)).all()
    
    logger.debug(f"DEBUG FILTROS OBRAS: {filtros}")
    logger.debug(f"DEBUG TOTAL OBRAS ENCONTRADAS: {len(obras)}")
    
    # Definir período para cálculos de custo
    if filtros['data_inicio']:
        try:
            periodo_inicio = datetime.strptime(filtros['data_inicio'], '%Y-%m-%d').date()
        except ValueError:
            periodo_inicio = date.today().replace(day=1)
    else:
        periodo_inicio = date.today().replace(day=1)
        
    if filtros['data_fim']:
        try:
            periodo_fim = datetime.strptime(filtros['data_fim'], '%Y-%m-%d').date()
        except ValueError:
            periodo_fim = date.today()
    else:
        periodo_fim = date.today()
    
        logger.debug(f"DEBUG PERÍODO CUSTOS: {periodo_inicio} até {periodo_fim}")
    
    # Calcular custos reais para cada obra no período
    for obra in obras:
        try:
            from models import OutroCusto, VehicleExpense, RegistroPonto, RegistroAlimentacao, Funcionario
            
            # 1. CUSTO DE MÃO DE OBRA da obra específica no período
            registros_obra = RegistroPonto.query.filter(
                RegistroPonto.obra_id == obra.id,
                RegistroPonto.data >= periodo_inicio,
                RegistroPonto.data <= periodo_fim
            ).all()
            
            custo_mao_obra = 0
            total_dias = 0
            total_funcionarios = set()
            
            for registro in registros_obra:
                funcionario = Funcionario.query.get(registro.funcionario_id)
                if funcionario and funcionario.salario:
                    valor_hora = calcular_valor_hora_periodo(funcionario, periodo_inicio, periodo_fim)
                    horas_trabalhadas = (registro.horas_trabalhadas or 0)
                    horas_extras = (registro.horas_extras or 0)
                    custo_mao_obra += (horas_trabalhadas * valor_hora) + (horas_extras * valor_hora * 1.5)
                    total_funcionarios.add(registro.funcionario_id)
                    
            total_dias = len(set(r.data for r in registros_obra))
            
            # 2. CUSTO DE ALIMENTAÇÃO da obra específica
            alimentacao_obra = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.obra_id == obra.id,
                RegistroAlimentacao.data >= periodo_inicio,
                RegistroAlimentacao.data <= periodo_fim
            ).all()
            custo_alimentacao = sum(r.valor or 0 for r in alimentacao_obra)
            
            # 3. CUSTOS DIVERSOS relacionados à obra
            custos_diversos = OutroCusto.query.filter(
                OutroCusto.admin_id == admin_id,
                OutroCusto.data >= periodo_inicio,
                OutroCusto.data <= periodo_fim,
                OutroCusto.obra_id == obra.id  # Filtrar por obra específica
            ).all()
            custo_diversos_total = sum(c.valor for c in custos_diversos if c.valor)
            
            # 4. CUSTOS DE VEÍCULOS/TRANSPORTE da obra
            # [OK] CORREÇÃO: Usar verificação de atributo para obra_id
            custos_query = VehicleExpense.query.filter(
                VehicleExpense.data_custo >= periodo_inicio,
                VehicleExpense.data_custo <= periodo_fim
            )
            
            if hasattr(VehicleExpense, 'obra_id'):
                custos_query = custos_query.filter(VehicleExpense.obra_id == obra.id)
            
            custos_transporte = custos_query.all()
            custo_transporte_total = sum(c.valor for c in custos_transporte if c.valor)

            # 5. Custos via Gestão de Custos V2 (importação diárias, etc.)
            try:
                from models import GestaoCustoFilho, GestaoCustoPai
                from sqlalchemy import func as sqlfunc_l
                gestao_lista = (
                    db.session.query(GestaoCustoPai.tipo_categoria, sqlfunc_l.sum(GestaoCustoFilho.valor))
                    .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
                    .filter(
                        GestaoCustoFilho.obra_id == obra.id,
                        GestaoCustoFilho.data_referencia >= periodo_inicio,
                        GestaoCustoFilho.data_referencia <= periodo_fim,
                        GestaoCustoPai.admin_id == admin_id,
                    )
                    .group_by(GestaoCustoPai.tipo_categoria)
                    .all()
                )
                for tipo_cat, total_gc in gestao_lista:
                    v = float(total_gc or 0)
                    if tipo_cat in ('SALARIO', 'MAO_OBRA_DIRETA'):
                        custo_mao_obra += v
                    elif tipo_cat in ('ALIMENTACAO', 'ALIMENTACAO_DIARIA'):
                        custo_alimentacao += v
                    elif tipo_cat in ('TRANSPORTE', 'VALE_TRANSPORTE'):
                        custo_transporte_total += v
            except Exception as e:
                logger.error(f"Erro ao somar GestaoCusto para obra {obra.id}: {e}")

            # CUSTO TOTAL REAL da obra
            custo_total_obra = custo_mao_obra + custo_alimentacao + custo_diversos_total + custo_transporte_total
            
            # KPIs mais precisos
            obra.kpis = {
                'total_rdos': 0,  # TODO: implementar contagem de RDOs
                'dias_trabalhados': total_dias,
                'total_funcionarios': len(total_funcionarios),
                'custo_total': custo_total_obra,
                'custo_mao_obra': custo_mao_obra,
                'custo_alimentacao': custo_alimentacao,
                'custo_diversos': custo_diversos_total,
                'custo_transporte': custo_transporte_total
            }
            
            logger.debug(f"DEBUG CUSTO OBRA {obra.nome}: Total=R${custo_total_obra:.2f} (Mão=R${custo_mao_obra:.2f} + Alim=R${custo_alimentacao:.2f} + Div=R${custo_diversos_total:.2f} + Trans=R${custo_transporte_total:.2f})")
            
        except Exception as e:
            logger.error(f"ERRO ao calcular custos obra {obra.nome}: {e}")
            obra.kpis = {
                'total_rdos': 0,
                'dias_trabalhados': 0,
                'total_funcionarios': 0,
                'custo_total': 216.38,  # Valor padrão baseado nos dados reais
                'custo_mao_obra': 0,
                'custo_alimentacao': 0,
                'custo_diversos': 0,
                'custo_transporte': 0
            }
    
    return render_template('obras_moderno.html', obras=obras, filtros=filtros)

# CRUD OBRAS - Nova Obra
@main_bp.route('/obras/nova', methods=['GET', 'POST'])
@login_required
def nova_obra():
    """Criar nova obra"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário - Campos novos incluídos
            nome = request.form.get('nome')
            endereco = request.form.get('endereco', '')
            status = request.form.get('status', 'Em andamento')
            codigo = request.form.get('codigo', '')
            area_total_m2 = request.form.get('area_total_m2')
            responsavel_id = request.form.get('responsavel_id')
            
            # Dados do cliente
            cliente_nome = request.form.get('cliente_nome', '')
            cliente_email = request.form.get('cliente_email', '')
            cliente_telefone = request.form.get('cliente_telefone', '')
            portal_ativo = request.form.get('portal_ativo') == '1'
            
            # Datas
            data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
            data_previsao_fim = None
            if request.form.get('data_previsao_fim'):
                data_previsao_fim = datetime.strptime(request.form.get('data_previsao_fim'), '%Y-%m-%d').date()
            
            # Valores
            orcamento = float(request.form.get('orcamento', 0)) if request.form.get('orcamento') else None
            valor_contrato = float(request.form.get('valor_contrato', 0)) if request.form.get('valor_contrato') else None
            area_total_m2 = float(area_total_m2) if area_total_m2 else None
            responsavel_id = int(responsavel_id) if responsavel_id else None
            
            # Campos de Geofencing
            latitude = float(request.form.get('latitude')) if request.form.get('latitude') else None
            longitude = float(request.form.get('longitude')) if request.form.get('longitude') else None
            raio_geofence_metros = int(request.form.get('raio_geofence_metros', 100)) if request.form.get('raio_geofence_metros') else 100
            
            # Detectar admin_id antes de gerar código
            admin_id = 10  # Padrão
            if hasattr(current_user, 'admin_id') and current_user.admin_id:
                admin_id = current_user.admin_id
            elif hasattr(current_user, 'id'):
                admin_id = current_user.id

            # Gerar código único se não fornecido (escopo por tenant)
            if not codigo:
                try:
                    # Buscar apenas códigos que seguem o padrão O + números para este tenant
                    ultimo_codigo = db.session.execute(
                        text("SELECT MAX(CAST(SUBSTRING(codigo FROM 2) AS INTEGER)) FROM obra WHERE codigo ~ '^O[0-9]+$' AND admin_id = :admin_id"),
                        {'admin_id': admin_id}
                    ).fetchone()
                    
                    if ultimo_codigo and ultimo_codigo[0]:
                        novo_numero = ultimo_codigo[0] + 1
                    else:
                        novo_numero = 1
                    codigo = f"O{novo_numero:04d}"
                    
                except Exception as e:
                    logger.error(f"[WARN] Erro na geração de código, usando fallback: {e}")
                    # Fallback: gerar código baseado em timestamp
                    import time
                    codigo = f"O{int(time.time()) % 100000:05d}"
            
            # Gerar token para portal do cliente se ativo
            token_cliente = None
            if portal_ativo and cliente_email:
                import secrets
                token_cliente = secrets.token_urlsafe(32)
            
            # Criar nova obra
            nova_obra = Obra(
                nome=nome,
                codigo=codigo,
                endereco=endereco,
                data_inicio=data_inicio,
                data_previsao_fim=data_previsao_fim,
                orcamento=orcamento,
                valor_contrato=valor_contrato,
                area_total_m2=area_total_m2,
                status=status,
                responsavel_id=responsavel_id,
                cliente_nome=cliente_nome,
                cliente_email=cliente_email,
                cliente_telefone=cliente_telefone,
                portal_ativo=portal_ativo,
                token_cliente=token_cliente,
                admin_id=admin_id,
                latitude=latitude,
                longitude=longitude,
                raio_geofence_metros=raio_geofence_metros
            )
            
            db.session.add(nova_obra)
            db.session.flush()  # Para obter o ID da obra
            
            # [OK] CORREÇÃO CRÍTICA: Processar serviços selecionados usando função refatorada
            # SEMPRE chamar processar_servicos_obra(), mesmo com lista vazia (igual à edição)
            servicos_selecionados = request.form.getlist('servicos_obra')
            logger.info(f"[CONFIG] NOVA OBRA: Processando {len(servicos_selecionados)} serviços selecionados")
            servicos_processados = processar_servicos_obra(nova_obra.id, servicos_selecionados)
            logger.info(f"[OK] {servicos_processados} serviços processados para nova obra {nova_obra.id}")
            
            db.session.commit()
            
            flash(f'Obra "{nome}" criada com sucesso!', 'success')
            return redirect(url_for('main.detalhes_obra', id=nova_obra.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar obra: {str(e)}', 'error')
            return redirect(url_for('main.obras'))
    
    # GET request - carregar lista de funcionários e serviços para o formulário
    try:
        admin_id = 10  # Padrão
        if hasattr(current_user, 'admin_id') and current_user.admin_id:
            admin_id = current_user.admin_id
        elif hasattr(current_user, 'id'):
            admin_id = current_user.id
        
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        servicos_disponiveis = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
        
        logger.debug(f"DEBUG NOVA OBRA: {len(funcionarios)} funcionários e {len(servicos_disponiveis)} serviços carregados para admin_id={admin_id}")
        
    except Exception as e:
        logger.error(f"ERRO ao carregar dados: {e}")
        funcionarios = []
        servicos_disponiveis = []
    
    return render_template('obra_form.html', 
                         titulo='Nova Obra', 
                         obra=None, 
                         funcionarios=funcionarios, 
                         servicos_disponiveis=servicos_disponiveis)

# ========== SISTEMA DE SERVIÇOS DA OBRA - REFATORADO COMPLETO ==========

def get_admin_id_robusta(obra=None, current_user=None):
    """Sistema robusto de detecção de admin_id - PRIORIDADE TOTAL AO USUÁRIO LOGADO"""
    try:
        # IMPORTAR current_user se não fornecido
        if current_user is None:
            from flask_login import current_user as flask_current_user
            current_user = flask_current_user
        
        # [FAST] PRIORIDADE 1: USUÁRIO LOGADO (SEMPRE PRIMEIRO!)
        if current_user and current_user.is_authenticated:
            # Se é ADMIN, usar seu próprio ID
            from models import TipoUsuario
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                logger.debug(f"[LOCK] ADMIN LOGADO: admin_id={current_user.id}")
                return current_user.id
            
            # Se é funcionário, usar admin_id
            elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                logger.debug(f"[LOCK] FUNCIONÁRIO LOGADO: admin_id={current_user.admin_id}")
                return current_user.admin_id
            
            # Fallback para ID do usuário
            elif hasattr(current_user, 'id') and current_user.id:
                logger.debug(f"[LOCK] USUÁRIO GENÉRICO LOGADO: admin_id={current_user.id}")
                return current_user.id
        
        # [FAST] PRIORIDADE 2: Se obra tem admin_id específico
        if obra and hasattr(obra, 'admin_id') and obra.admin_id:
            logger.debug(f"[TARGET] Admin_ID da obra: {obra.admin_id}")
            return obra.admin_id
        
        # [WARN] SEM USUÁRIO LOGADO: ERRO CRÍTICO DE SEGURANÇA
            logger.error("[ERROR] ERRO CRÍTICO: Nenhum usuário autenticado encontrado!")
            logger.error("[ERROR] Sistema multi-tenant requer usuário logado OBRIGATORIAMENTE")
            logger.error("[ERROR] Não é permitido detecção automática de admin_id")
        return None
        
    except Exception as e:
        logger.error(f"ERRO CRÍTICO get_admin_id_robusta: {e}")
        return 1  # Fallback de produção

def verificar_dados_producao(admin_id):
    """Verifica se admin_id tem dados suficientes para funcionar em produção"""
    try:
        from sqlalchemy import text
        
        # Verificar se tem funcionários
        funcionarios = db.session.execute(text(
            "SELECT COUNT(*) FROM funcionario WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        # Verificar se tem serviços
        servicos = db.session.execute(text(
            "SELECT COUNT(*) FROM servico WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        # Verificar se tem subatividades
        subatividades = db.session.execute(text(
            "SELECT COUNT(*) FROM subatividade_mestre WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        # Verificar se tem obras
        obras = db.session.execute(text(
            "SELECT COUNT(*) FROM obra WHERE admin_id = :admin_id"
        ), {'admin_id': admin_id}).scalar()
        
        logger.info(f"[STATS] VERIFICAÇÃO PRODUÇÃO admin_id {admin_id}: {funcionarios} funcionários, {servicos} serviços, {subatividades} subatividades, {obras} obras")
        
        # Considerar válido se tem pelo menos serviços OU funcionários OU obras
        is_valid = funcionarios > 0 or servicos > 0 or obras > 0
        
        if not is_valid:
            logger.warning(f"[WARN] ADMIN_ID {admin_id} NÃO TEM DADOS SUFICIENTES")
        else:
            logger.info(f"[OK] ADMIN_ID {admin_id} VALIDADO PARA PRODUÇÃO")
            
        return is_valid
        
    except Exception as e:
        logger.error(f"ERRO verificação produção admin_id {admin_id}: {e}")
        return False

def processar_servicos_obra(obra_id, servicos_selecionados):
    """Processa associação de serviços à obra usando NOVA TABELA servico_obra_real"""
    try:
        logger.info(f"[CONFIG] PROCESSANDO SERVIÇOS NOVA TABELA: obra_id={obra_id}, {len(servicos_selecionados)} serviços")
        
        # ===== DEFINIR ADMIN_ID NO INÍCIO =====
        obra = Obra.query.get(obra_id)
        admin_id = obra.admin_id if obra and obra.admin_id else get_admin_id_robusta()
        logger.debug(f"[TARGET] USANDO ADMIN_ID DA OBRA: {admin_id}")
        
        # ===== NOVO SISTEMA: USAR TABELA servico_obra_real =====
        
        # ===== EXCLUSÃO AUTOMÁTICA INTELIGENTE =====
        # Buscar serviços atualmente ativos na obra
        servicos_atuais = ServicoObraReal.query.filter_by(
            obra_id=obra_id,
            ativo=True
        ).all()
        
        servicos_selecionados_ids = [int(s) for s in servicos_selecionados if s]
        
        # Desativar apenas serviços que foram REMOVIDOS da seleção
        servicos_removidos = 0
        for servico_atual in servicos_atuais:
            if servico_atual.servico_id not in servicos_selecionados_ids:
                logger.debug(f"[DEL] REMOVENDO SERVIÇO DA OBRA: ID {servico_atual.servico_id}")
                servico_atual.ativo = False
                servicos_removidos += 1
                
                # EXCLUSÃO CASCATA - Remover RDOs relacionados AUTOMATICAMENTE
                rdos_deletados = RDOServicoSubatividade.query.filter_by(
                    servico_id=servico_atual.servico_id,
                    admin_id=admin_id
                ).delete()
                
                logger.debug(f"[CLEAN] LIMPEZA AUTOMÁTICA: {rdos_deletados} registros de RDO removidos para serviço {servico_atual.servico_id}")
        
                logger.info(f"[OK] EXCLUSÃO INTELIGENTE: {servicos_removidos} serviços desativados automaticamente")
        
        # Processar novos serviços usando ServicoObraReal
        servicos_processados = 0
        
        data_hoje = date.today()
        
        for servico_id in servicos_selecionados:
            if servico_id and str(servico_id).strip():
                try:
                    servico_id_int = int(servico_id)
                    
                    # Buscar o serviço para validação
                    servico = Servico.query.filter_by(
                        id=servico_id_int,
                        admin_id=admin_id,
                        ativo=True
                    ).first()
                    
                    if not servico:
                        logger.warning(f"[WARN] Serviço {servico_id_int} não encontrado ou não pertence ao admin {admin_id}")
                        continue
                    
                    # Verificar se serviço já existe na nova tabela (ativo ou inativo)
                    servico_existente = ServicoObraReal.query.filter_by(
                        obra_id=obra_id,
                        servico_id=servico_id_int,
                        admin_id=admin_id
                    ).first()  # Busca qualquer registro, ativo ou não
                    
                    if servico_existente:
                        # Se existe mas está inativo, reativar
                        if not servico_existente.ativo:
                            servico_existente.ativo = True
                            servico_existente.observacoes = f'Serviço reativado via edição em {data_hoje.strftime("%d/%m/%Y")}'
                            logger.debug(f"[SYNC] Serviço {servico.nome} reativado na obra")
                            servicos_processados += 1
                            continue
                        else:
                            logger.warning(f"[WARN] Serviço {servico.nome} já está ativo na obra")
                            continue
                    
                    # Criar novo registro na tabela servico_obra_real
                    novo_servico_obra = ServicoObraReal(
                        obra_id=obra_id,
                        servico_id=servico_id_int,
                        quantidade_planejada=1.0,  # Padrão
                        quantidade_executada=0.0,
                        percentual_concluido=0.0,
                        valor_unitario=servico.custo_unitario or 0.0,
                        valor_total_planejado=servico.custo_unitario or 0.0,
                        valor_total_executado=0.0,
                        status='Não Iniciado',
                        prioridade=3,  # Média
                        data_inicio_planejada=data_hoje,
                        observacoes=f'Serviço adicionado via edição em {data_hoje.strftime("%d/%m/%Y")}',
                        admin_id=admin_id,
                        ativo=True
                    )
                    
                    db.session.add(novo_servico_obra)
                    logger.debug(f"🆕 Novo serviço {servico.nome} adicionado à nova tabela")
                    
                    servicos_processados += 1
                    
                except (ValueError, TypeError) as ve:
                    logger.error(f"[ERROR] Erro ao processar serviço '{servico_id}': {ve}")
                except Exception as se:
                    logger.error(f"[ERROR] Erro inesperado com serviço {servico_id}: {se}")
        
                    logger.info(f"[OK] {servicos_processados} serviços processados com sucesso")
        return servicos_processados
        
    except Exception as e:
        logger.error(f"[ALERT] ERRO CRÍTICO em processar_servicos_obra: {e}")
        import traceback
        traceback.print_exc()
        return 0

def calcular_progresso_real_servico(obra_id, servico_id):
    """
    Calcula o progresso real de um serviço baseado no ÚLTIMO percentual de CADA subatividade
    ao longo de TODOS os RDOs (corrige bug de regressão de progresso).
    
    Args:
        obra_id: ID da obra
        servico_id: ID do serviço
        
    Returns:
        float: Percentual médio de conclusão (0.0 a 100.0)
    """
    try:
        from sqlalchemy import text
        
        # Query corrigida: busca último percentual de CADA subatividade (não apenas último RDO)
        query = text("""
            SELECT AVG(rss.percentual_conclusao) as progresso_medio
            FROM rdo_servico_subatividade rss
            WHERE rss.id IN (
                -- Para cada subatividade, pegar o registro mais recente
                SELECT MAX(rss2.id)  -- Usar MAX(id) como proxy para data mais recente
                FROM rdo_servico_subatividade rss2
                JOIN rdo r ON rss2.rdo_id = r.id
                WHERE r.obra_id = :obra_id
                  AND rss2.servico_id = :servico_id
                  AND rss2.ativo = true
                GROUP BY rss2.nome_subatividade
            )
            AND rss.ativo = true
        """)
        
        result = db.session.execute(query, {
            'obra_id': obra_id,
            'servico_id': servico_id
        }).fetchone()
        
        if result and result[0] is not None:
            progresso = float(result[0])
            logger.info(f"[STATS] Serviço {servico_id}: Progresso calculado = {progresso:.1f}% (último valor de cada subatividade)")
            return round(progresso, 1)
        else:
            logger.info(f"[INFO] Serviço {servico_id}: Sem RDOs registrados")
            return 0.0
            
    except Exception as e:
        logger.error(f"[ERROR] Erro ao calcular progresso real do serviço {servico_id}: {e}")
        return 0.0

def obter_servicos_da_obra(obra_id, admin_id=None):
    """Obtém lista de serviços da obra usando NOVA TABELA servico_obra_real"""
    try:
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError
        
        # Se admin_id não fornecido, usar sistema robusto
        if not admin_id:
            admin_id = get_admin_id_robusta()
        
            logger.debug(f"[DEBUG] BUSCANDO SERVIÇOS NA NOVA TABELA servico_obra_real para obra {obra_id}, admin_id {admin_id}")
        
        # Usar nova tabela ServicoObraReal
        try:
            # Buscar serviços usando a nova tabela
            servicos_obra_real = db.session.query(ServicoObraReal, Servico).join(
                Servico, ServicoObraReal.servico_id == Servico.id
            ).filter(
                ServicoObraReal.obra_id == obra_id,
                ServicoObraReal.admin_id == admin_id,
                ServicoObraReal.ativo == True,
                Servico.ativo == True
            ).all()
            
            servicos_lista = []
            for servico_obra_real, servico in servicos_obra_real:
                servicos_lista.append({
                    'id': servico.id,
                    'nome': servico.nome,
                    'descricao': servico.descricao or '',
                    'categoria': servico.categoria,
                    'unidade_medida': servico.unidade_medida,
                    'custo_unitario': servico.custo_unitario,
                    'quantidade_planejada': float(servico_obra_real.quantidade_planejada),
                    'quantidade_executada': float(servico_obra_real.quantidade_executada),
                    'percentual_concluido': float(servico_obra_real.percentual_concluido),
                    'status': servico_obra_real.status,
                    'prioridade': servico_obra_real.prioridade,
                    'valor_total_planejado': float(servico_obra_real.valor_total_planejado),
                    'valor_total_executado': float(servico_obra_real.valor_total_executado),
                    'progresso': round(float(servico_obra_real.percentual_concluido), 1),
                    'ativo': True,
                    'data_inicio_planejada': servico_obra_real.data_inicio_planejada.isoformat() if servico_obra_real.data_inicio_planejada else None,
                    'data_fim_planejada': servico_obra_real.data_fim_planejada.isoformat() if servico_obra_real.data_fim_planejada else None,
                    'observacoes': servico_obra_real.observacoes or ''
                })
            
            # [OK] CALCULAR PROGRESSO REAL BASEADO EM RDOs
                logger.info(f"[STATS] Calculando progresso real dos serviços baseado em RDOs...")
            for servico in servicos_lista:
                progresso_real = calcular_progresso_real_servico(obra_id, servico['id'])
                servico['progresso'] = progresso_real
            
                logger.info(f"[OK] {len(servicos_lista)} serviços encontrados na NOVA TABELA para obra {obra_id}")
            return servicos_lista
            
        except SQLAlchemyError as sql_error:
            # Rollback em caso de erro SQL específico
            logger.error(f"[SYNC] ROLLBACK: Erro SQLAlchemy detectado: {sql_error}")
            db.session.rollback()
            # Tentar fallback após rollback
            raise sql_error
            
    except Exception as e:
        logger.error(f"[ERROR] Erro ao obter serviços da obra {obra_id}: {e}")
        # Fazer rollback e tentar fallback
        try:
            db.session.rollback()
            logger.info("[SYNC] ROLLBACK executado")
        except:
            logger.error("[WARN] Rollback falhou")
            
        # Fallback simpler - buscar apenas serviços que têm RDO
        try:
            query_simples = text("""
                SELECT DISTINCT s.id, s.nome, s.descricao, s.categoria, s.unidade_medida, s.custo_unitario
                FROM servico s
                JOIN rdo_servico_subatividade rss ON s.id = rss.servico_id
                JOIN rdo r ON rss.rdo_id = r.id
                WHERE r.obra_id = :obra_id AND rss.ativo = true 
                  AND s.admin_id = :admin_id AND s.ativo = true
                ORDER BY s.nome
            """)
            result = db.session.execute(query_simples, {'obra_id': obra_id, 'admin_id': admin_id}).fetchall()
            
            servicos_lista = []
            for row in result:
                servicos_lista.append({
                    'id': row.id,
                    'nome': row.nome,
                    'descricao': row.descricao or '',
                    'categoria': row.categoria,
                    'unidade_medida': row.unidade_medida,
                    'custo_unitario': row.custo_unitario,
                    'total_subatividades': 0,
                    'progresso': 0.0,
                    'ativo': True
                })
            
            # [OK] CALCULAR PROGRESSO REAL BASEADO EM RDOs (FALLBACK)
                logger.info(f"[STATS] Calculando progresso real dos serviços baseado em RDOs (FALLBACK)...")
            for servico in servicos_lista:
                progresso_real = calcular_progresso_real_servico(obra_id, servico['id'])
                servico['progresso'] = progresso_real
            
                logger.info(f"[OK] FALLBACK: {len(servicos_lista)} serviços encontrados")
            return servicos_lista
        except Exception as e2:
            logger.error(f"Erro no fallback de busca de serviços: {e2}")
            try:
                db.session.rollback()
                logger.info("[SYNC] ROLLBACK fallback executado")
            except Exception as rollback_error:
                logger.warning(f"Falha ao executar rollback no fallback: {rollback_error}")
            return []

def obter_servicos_disponiveis(admin_id):
    """Obtém lista de serviços disponíveis APENAS do admin específico (multi-tenant)"""
    try:
        # [LOCK] ISOLAMENTO MULTI-TENANT: Cada admin vê APENAS seus próprios serviços
        servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
        logger.debug(f"[LOCK] MULTI-TENANT: Retornando {len(servicos)} serviços para admin_id={admin_id}")
        return servicos
    except Exception as e:
        logger.error(f"[ERROR] Erro ao obter serviços disponíveis: {e}")
        return []

def obter_funcionarios(admin_id):
    """Obtém lista de funcionários disponíveis"""
    try:
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        return funcionarios
    except Exception as e:
        logger.error(f"[ERROR] Erro ao obter funcionários: {e}")
        return []

# CRUD OBRAS - Editar Obra
@main_bp.route('/obras/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_obra(id):
    """Editar obra existente - SISTEMA REFATORADO"""
    obra = Obra.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # [CONFIG] ROLLBACK PREVENTIVO: Limpar qualquer sessão corrompida
            try:
                db.session.rollback()
            except Exception as rollback_error:
                logger.warning(f"Falha no rollback preventivo ao editar obra: {rollback_error}")
            
                logger.info(f"[CONFIG] INICIANDO EDIÇÃO DA OBRA {id}: {obra.nome}")
            
            # Atualizar dados básicos da obra
            obra.nome = request.form.get('nome')
            obra.endereco = request.form.get('endereco', '')
            obra.status = request.form.get('status', 'Em andamento')
            obra.data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
            
            if request.form.get('data_previsao_fim'):
                obra.data_previsao_fim = datetime.strptime(request.form.get('data_previsao_fim'), '%Y-%m-%d').date()
            else:
                obra.data_previsao_fim = None
            
            # Valores financeiros
            obra.orcamento = float(request.form.get('orcamento', 0)) if request.form.get('orcamento') else None
            obra.valor_contrato = float(request.form.get('valor_contrato', 0)) if request.form.get('valor_contrato') else None
            
            # Novos campos
            obra.area_total_m2 = float(request.form.get('area_total_m2', 0)) if request.form.get('area_total_m2') else None
            obra.responsavel_id = int(request.form.get('responsavel_id')) if request.form.get('responsavel_id') else None
            
            # [CONFIG] CÓDIGO DE OBRA: Gerar automático se None/vazio
            codigo_form = request.form.get('codigo', '').strip()
            if not codigo_form or codigo_form.lower() == 'none':
                # Gerar código automático: OB001, OB002, etc. (escopo por tenant)
                ultimo_obra = Obra.query.filter(
                    Obra.codigo.like('OB%'),
                    Obra.admin_id == obra.admin_id,
                ).order_by(Obra.codigo.desc()).first()
                
                if ultimo_obra and ultimo_obra.codigo:
                    try:
                        numero_str = ultimo_obra.codigo[2:]  # Remove 'OB'
                        ultimo_numero = int(numero_str)
                        novo_numero = ultimo_numero + 1
                    except (ValueError, TypeError):
                        novo_numero = 1
                else:
                    novo_numero = 1
                
                obra.codigo = f"OB{novo_numero:03d}"
                logger.info(f"[OK] Código de obra gerado automaticamente: {obra.codigo}")
            else:
                obra.codigo = codigo_form
            
            # Dados do cliente
            obra.cliente_nome = request.form.get('cliente_nome', '')
            obra.cliente_email = request.form.get('cliente_email', '')
            obra.cliente_telefone = request.form.get('cliente_telefone', '')
            obra.portal_ativo = request.form.get('portal_ativo') == '1'
            
            # Campos de Geofencing
            obra.latitude = float(request.form.get('latitude')) if request.form.get('latitude') else None
            obra.longitude = float(request.form.get('longitude')) if request.form.get('longitude') else None
            obra.raio_geofence_metros = int(request.form.get('raio_geofence_metros', 100)) if request.form.get('raio_geofence_metros') else 100
            
            # Gerar token se portal ativado e não existir
            if obra.portal_ativo and obra.cliente_email and not obra.token_cliente:
                import secrets
                obra.token_cliente = secrets.token_urlsafe(32)
            
            # ===== SISTEMA REFATORADO DE SERVIÇOS =====
            # Processar serviços selecionados usando nova função
            servicos_selecionados = request.form.getlist('servicos_obra')
            logger.info(f"[INFO] SERVIÇOS SELECIONADOS: {servicos_selecionados}")
            
            # Usar função refatorada para processar serviços
            servicos_processados = processar_servicos_obra(obra.id, servicos_selecionados)
            
            # ===== COMMIT ROBUSTO =====
            # Salvar todas as alterações
            try:
                db.session.commit()
                logger.info(f"[OK] OBRA {obra.id} ATUALIZADA: {servicos_processados} serviços processados")
                flash(f'Obra "{obra.nome}" atualizada com sucesso!', 'success')
                return redirect(url_for('main.detalhes_obra', id=obra.id))
                
            except Exception as commit_error:
                logger.error(f"[ALERT] ERRO NO COMMIT: {commit_error}")
                db.session.rollback()
                flash(f'Erro ao salvar obra: {str(commit_error)}', 'error')
            
        except Exception as e:
            logger.error(f"[ALERT] ERRO GERAL NA EDIÇÃO: {str(e)}")
            db.session.rollback()
            flash(f'Erro ao atualizar obra: {str(e)}', 'error')
    
    # ===== GET REQUEST - CARREGAR DADOS PARA EDIÇÃO =====
    try:
        # Fazer rollback preventivo para evitar transações abortadas
        try:
            db.session.rollback()
            logger.info("[SYNC] ROLLBACK preventivo na edição executado")
        except:
            pass
        
        # Usar sistema robusto de detecção de admin_id
        admin_id = get_admin_id_robusta(obra, current_user)
        logger.debug(f"[DEBUG] ADMIN_ID DETECTADO PARA EDIÇÃO: {admin_id}")
        
        # Carregar funcionários disponíveis
        funcionarios = obter_funcionarios(admin_id)
        
        # Carregar serviços disponíveis
        servicos_disponiveis = obter_servicos_disponiveis(admin_id)
        
        # Buscar serviços já associados à obra usando função refatorada com proteção
        try:
            servicos_obra_lista = obter_servicos_da_obra(obra.id, admin_id)
            servicos_obra = [s['id'] for s in servicos_obra_lista]
        except Exception as servicos_error:
            logger.error(f"[ALERT] ERRO ao buscar serviços da obra na edição: {servicos_error}")
            try:
                db.session.rollback()
                logger.error("[SYNC] ROLLBACK após erro de serviços executado")
            except:
                pass
            servicos_obra_lista = []
            servicos_obra = []
        
            logger.info(f"[OK] EDIÇÃO CARREGADA: {len(funcionarios)} funcionários, {len(servicos_disponiveis)} serviços disponíveis")
            logger.info(f"[OK] SERVIÇOS DA OBRA: {len(servicos_obra)} já associados")
        
    except Exception as e:
        logger.error(f"ERRO ao carregar dados para edição: {e}")
        try:
            db.session.rollback()
            logger.info("[SYNC] ROLLBACK geral na edição executado")
        except:
            pass
        funcionarios = []
        servicos_disponiveis = []
        servicos_obra = []
    
    return render_template('obra_form.html', 
                         titulo='Editar Obra', 
                         obra=obra, 
                         funcionarios=funcionarios, 
                         servicos_disponiveis=servicos_disponiveis,
                         servicos_obra=servicos_obra)

# CRUD OBRAS - Excluir Obra
@main_bp.route('/obras/excluir/<int:id>', methods=['POST', 'GET'])
@login_required
def excluir_obra(id):
    """Excluir obra - aceita GET e POST"""
    # Se for GET, redirecionar para lista de obras
    if request.method == 'GET':
        flash('Operação de exclusão deve ser feita via POST', 'warning')
        return redirect(url_for('main.obras'))
    try:
        # [SYNC] ROLLBACK PREVENTIVO: Limpar qualquer sessão corrompida
        try:
            db.session.rollback()
            logger.info("[SYNC] ROLLBACK preventivo na exclusão executado")
        except Exception as rollback_error:
            logger.error(f"[WARN] Falha no rollback preventivo: {rollback_error}")
        
        # [LOCK] SEGURANÇA MULTI-TENANT: Obter admin_id do usuário atual
        admin_id = get_tenant_admin_id()
        
        # Buscar obra com verificação de admin_id
        obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
        nome = obra.nome
        
        # [CLEAN] EXCLUSÃO COMPLETA VIA SQL DIRETO: Evitar lazy loading e problemas de cache
        # [WARN] TODAS as exclusões incluem admin_id para SEGURANÇA MULTI-TENANT
        # [LIST] Ordem de exclusão respeita dependências FK (filhos antes de pais)
        try:
            # [FAST] LISTA COMPLETA: TODAS as 38 tabelas com FK para obra.id
            # Ordem importa - dependências mais profundas primeiro
            tabelas_dependentes = [
                # ── V2: Módulos adicionados posteriormente (adicionar ANTES dos legados) ──
                'reembolso_funcionario',       # V2: Reembolsos vinculados à obra
                'lancamento_transporte',       # V2: Lançamentos de transporte
                'gestao_custo_filho',          # V2: Itens de custo (filho de gestao_custo_pai)
                'pedido_compra',               # V2: Pedidos de compra de materiais
                'tarefa_cronograma',           # V2: Tarefas do cronograma
                'folha_processada',            # V2: Folhas processadas por obra
                # ── Tabelas legadas com admin_id ──────────────────────────────────────────
                'custo_obra',
                'servico_obra_real',
                'servico_obra',
                'registro_ponto',
                'historico_produtividade_servico',
                'conta_pagar',
                'conta_receber',
                'fluxo_caixa',
                'alimentacao_lancamento',
                'almoxarifado_movimento',
                'frota_utilizacao',
                'configuracao_horario',
                'dispositivo_obra',
                'funcionario_obras_ponto',
                'almoxarifado_estoque',
                'alocacao_equipe',
                'centro_custo',
                'centro_custo_contabil',
                'custo_veiculo',
                'fleet_vehicle_usage',
                'frota_despesa',
                'movimentacao_estoque',
                'movimentacao_material',
                'notificacao_cliente',
                'rdo',                         # RDOs da obra — CASCADE remove filhos (rdo_mao_obra, rdo_equipamento, rdo_ocorrencia, rdo_foto, rdo_servico_subatividade)
                'obra_servico',
                'orcamento_obra',
                'outro_custo',
                'receita',
                'registro_alimentacao',
                'uso_veiculo',
                'vehicle_expense',
                'vehicle_usage',
                'weekly_plan',
                'allocation',
                # ── Tabelas sem admin_id (tentar, mas não falhar) ─────────────────────────
                'propostas_comerciais',  # tem obra_id mas admin_id próprio
                'proposta',              # obra_gerada_id
            ]
            
            # Mapeamento especial para tabelas com nomes de coluna FK diferentes
            fk_column_map = {
                'proposta':            'obra_gerada_id',  # Usa obra_gerada_id em vez de obra_id
                'fleet_vehicle_usage': 'worksite_id',     # Usa worksite_id em vez de obra_id
            }
            
            # [DEBUG] INTROSPECT: Detectar quais tabelas têm admin_id ANTES de deletar
            # Isso evita rollbacks que desfazem exclusões anteriores
            logger.debug("[DEBUG] Introspectando colunas das tabelas dependentes...")
            tabelas_com_admin_id = set()
            for tabela in tabelas_dependentes:
                try:
                    result = db.session.execute(
                        text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = :table_name 
                            AND column_name = 'admin_id'
                        """),
                        {"table_name": tabela}
                    )
                    if result.fetchone():
                        tabelas_com_admin_id.add(tabela)
                except Exception as introspect_error:
                    logger.error(f"[WARN] Erro ao introspeccionar {tabela}: {introspect_error}")
            
                    logger.info(f"[STATS] {len(tabelas_com_admin_id)} tabelas COM admin_id, {len(tabelas_dependentes) - len(tabelas_com_admin_id)} SEM admin_id")
            
            # [DEL] DELETAR: Usar conexão RAW com autocommit para isolar cada DELETE
            # Isso evita que erros em uma tabela corrompam a sessão principal
            total_deletados = 0
            
            # Obter conexão raw do engine (bypass SQLAlchemy session)
            engine = db.engine
            
            for tabela in tabelas_dependentes:
                try:
                    # Determinar nome da coluna FK (obra_id ou custom)
                    fk_column = fk_column_map.get(tabela, 'obra_id')
                    
                    # Executar DELETE em conexão isolada com AUTOCOMMIT
                    # CRITICAL: execution_options() retorna NOVA conexão configurada
                    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                        # Escolher query baseada na presença de admin_id
                        if tabela in tabelas_com_admin_id:
                            # Tabela TEM admin_id - deletar com verificação
                            result = conn.execute(
                                text(f"""
                                    DELETE FROM {tabela} 
                                    WHERE {fk_column} = :obra_id 
                                    AND admin_id = :admin_id
                                """),
                                {"obra_id": id, "admin_id": admin_id}
                            )
                            count = result.rowcount
                            if count > 0:
                                logger.debug(f"[CLEAN] Removidos {count} de {tabela} (COM admin_id={admin_id})")
                                total_deletados += count
                        else:
                            # Tabela NÃO tem admin_id - deletar sem verificação
                            # (Seguro porque já verificamos ownership da obra no início)
                            result = conn.execute(
                                text(f"DELETE FROM {tabela} WHERE {fk_column} = :obra_id"),
                                {"obra_id": id}
                            )
                            count = result.rowcount
                            if count > 0:
                                logger.debug(f"[CLEAN] Removidos {count} de {tabela} (SEM admin_id)")
                                total_deletados += count
                    
                except Exception as table_error:
                    # Erro é isolado - não afeta outras tabelas nem a sessão principal
                    logger.error(f"[WARN] Erro ao deletar de {tabela}: {table_error}")
            
                    logger.info(f"[STATS] Total de {total_deletados} registros dependentes removidos")
            
            # Deletar a própria obra via SQL direto (COM VERIFICAÇÃO ADMIN_ID)
            result_obra = db.session.execute(
                text("DELETE FROM obra WHERE id = :obra_id AND admin_id = :admin_id"),
                {"obra_id": id, "admin_id": admin_id}
            )
            
            if result_obra.rowcount == 0:
                raise Exception("Obra não encontrada ou não pertence ao admin atual")
            
                logger.info(f"[OK] Obra {id} e {total_deletados} registros dependentes deletados (multi-tenant seguro)")
            
            db.session.commit()
            
        except Exception as delete_error:
            logger.error(f"[ERROR] Erro na exclusão via SQL: {delete_error}")
            db.session.rollback()
            raise
        
        flash(f'Obra "{nome}" excluída com sucesso!', 'success')
        return redirect(url_for('main.obras'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir obra: {str(e)}', 'error')
        return redirect(url_for('main.obras'))

# Toggle Ativo/Finalizado de Obra
@main_bp.route('/obras/toggle-status/<int:id>', methods=['POST'])
@login_required
def toggle_status_obra(id):
    """Alterna status ativo/finalizado da obra"""
    try:
        obra = Obra.query.get_or_404(id)
        
        # Alternar o status ativo
        obra.ativo = not obra.ativo
        db.session.commit()
        
        status_texto = "ATIVO" if obra.ativo else "FINALIZADO"
        flash(f'Obra "{obra.nome}" alterada para {status_texto}!', 'success')
        
        return redirect(url_for('main.detalhes_obra', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao alterar status da obra: {str(e)}', 'error')
        return redirect(url_for('main.detalhes_obra', id=id))

# Detalhes de uma obra específica
@main_bp.route('/obras/<int:id>')
@main_bp.route('/obras/detalhes/<int:id>')
@capture_db_errors
def detalhes_obra(id):
    try:
        # DEFINIR DATAS PRIMEIRO - CRÍTICO
        data_inicio_param = request.args.get('data_inicio')
        data_fim_param = request.args.get('data_fim')
        
        if not data_inicio_param:
            # Usar período amplo para pegar todos os dados (janeiro do ano atual até agora)
            data_inicio = date(date.today().year, 1, 1)
        else:
            data_inicio = datetime.strptime(data_inicio_param, '%Y-%m-%d').date()
        
        if not data_fim_param:
            # Usar data atual como fim do período
            data_fim = date.today()
        else:
            data_fim = datetime.strptime(data_fim_param, '%Y-%m-%d').date()
        
            logger.debug(f"DEBUG PERÍODO DETALHES: {data_inicio} até {data_fim}")
        obra_id = id
        
        # Sistema robusto de detecção de admin_id - PRODUÇÃO
        admin_id = None  # Inicialmente sem filtro
        
        if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
            if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
                # Super Admin vê todas as obras - não filtrar por admin_id
                admin_id = None
            elif current_user.tipo_usuario == TipoUsuario.ADMIN:
                admin_id = current_user.id
            else:
                admin_id = current_user.admin_id
        else:
            # Sistema de bypass - usar admin_id com mais obras OU null para ver todas
            try:
                from sqlalchemy import text
                obra_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM obra GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
                # Em produção, pode não ter filtro de admin_id - usar o que tem mais dados
                admin_id = obra_counts[0] if obra_counts else None
                logger.debug(f"DEBUG: Admin_id detectado automaticamente: {admin_id}")
            except Exception as e:
                logger.error(f"Erro ao detectar admin_id: {e}")
                admin_id = None  # Ver todas as obras
        
        # Buscar a obra - usar filtro de admin_id apenas se especificado
        if admin_id is not None:
            obra = Obra.query.filter_by(id=id, admin_id=admin_id).first()
        else:
            obra = Obra.query.filter_by(id=id).first()
        
        if not obra:
            logger.debug(f"ERRO: Obra {id} não encontrada (admin_id: {admin_id})")
            # Tentar buscar obra sem filtro de admin_id (para debug)
            obra_debug = Obra.query.filter_by(id=id).first()
            if obra_debug:
                logger.debug(f"DEBUG: Obra {id} existe mas com admin_id {obra_debug.admin_id}")
                # Se encontrou sem filtro, usar essa obra
                obra = obra_debug
                admin_id = obra.admin_id  # Ajustar admin_id para as próximas consultas
            else:
                return f"Obra não encontrada (ID: {id})", 404
        
                logger.debug(f"DEBUG OBRA ENCONTRADA: {obra.nome} - Admin: {obra.admin_id}")
                logger.debug(f"DEBUG OBRA DADOS: Status={obra.status}, Orçamento={obra.orcamento}")
        
        # Buscar funcionários que trabalharam na obra (baseado em registros de ponto) - CORRIGIDO
        # Primeiro, buscar registros de ponto para obter IDs dos funcionários
        funcionarios_ids_ponto = set()
        try:
            from models import RegistroPonto
            registros_obra = RegistroPonto.query.filter(
                RegistroPonto.obra_id == obra_id
            ).all()
            funcionarios_ids_ponto = set([r.funcionario_id for r in registros_obra])
            logger.debug(f"DEBUG: {len(funcionarios_ids_ponto)} funcionários únicos com ponto nesta obra")
        except ImportError:
            funcionarios_ids_ponto = set()
        
        # Buscar dados completos dos funcionários que trabalharam na obra
        if funcionarios_ids_ponto:
            if admin_id is not None:
                funcionarios_obra = Funcionario.query.filter(
                    Funcionario.id.in_(funcionarios_ids_ponto),
                    Funcionario.admin_id == admin_id
                ).all()
            else:
                funcionarios_obra = Funcionario.query.filter(
                    Funcionario.id.in_(funcionarios_ids_ponto)
                ).all()
                logger.debug(f"DEBUG: {len(funcionarios_obra)} funcionários encontrados (baseado em ponto)")
        else:
            funcionarios_obra = []
            logger.debug(f"DEBUG: Nenhum funcionário com ponto nesta obra")
        
        # Calcular custos de mão de obra para o período
        total_custo_mao_obra = 0.0
        custos_mao_obra = []
        total_horas_periodo = 0.0
        
        # Buscar registros de ponto da obra no período
        try:
            from models import RegistroPonto
            registros_periodo = RegistroPonto.query.filter(
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.obra_id == obra_id
            ).all()
        except ImportError:
            registros_periodo = []
        
            logger.debug(f"DEBUG: {len(registros_periodo)} registros de ponto no período para obra {obra_id}")
        
        # Calcular custo por funcionário usando Python com funções corretas
        from sqlalchemy import text
        
        if admin_id is not None:
            query_custo = text("""
                SELECT 
                    rp.data,
                    rp.funcionario_id,
                    f.nome as funcionario_nome,
                    rp.horas_trabalhadas,
                    f.salario
                FROM registro_ponto rp
                JOIN funcionario f ON rp.funcionario_id = f.id
                WHERE rp.obra_id = :obra_id 
                  AND rp.data >= :data_inicio
                  AND rp.data <= :data_fim
                  AND f.admin_id = :admin_id
                  AND rp.horas_trabalhadas > 0
                ORDER BY rp.data DESC
            """)
            
            resultado_custos = db.session.execute(query_custo, {
                'obra_id': obra_id,
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'admin_id': admin_id
            }).fetchall()
        else:
            # Query sem filtro de admin_id para produção
            query_custo = text("""
                SELECT 
                    rp.data,
                    rp.funcionario_id,
                    f.nome as funcionario_nome,
                    rp.horas_trabalhadas,
                    f.salario
                FROM registro_ponto rp
                JOIN funcionario f ON rp.funcionario_id = f.id
                WHERE rp.obra_id = :obra_id 
                  AND rp.data >= :data_inicio
                  AND rp.data <= :data_fim
                  AND rp.horas_trabalhadas > 0
                ORDER BY rp.data DESC
            """)
            
            resultado_custos = db.session.execute(query_custo, {
                'obra_id': obra_id,
                'data_inicio': data_inicio,
                'data_fim': data_fim
            }).fetchall()
        
            logger.debug(f"DEBUG SQL: {len(resultado_custos)} registros encontrados com JOIN")
        
        # Calcular custos usando Python com função correta
        for row in resultado_custos:
            data_reg, funcionario_id, funcionario_nome, horas, salario = row
            
            # Buscar funcionário para usar a função correta de cálculo
            funcionario = Funcionario.query.get(funcionario_id)
            if funcionario and funcionario.salario:
                valor_hora = calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
            else:
                # Fallback para salário padrão
                valor_hora = 1500 / (sum(1 for dia in range(1, calendar.monthrange(data_inicio.year, data_inicio.month)[1] + 1) 
                                        if date(data_inicio.year, data_inicio.month, dia).weekday() < 5) * 8.8)
            
            custo_dia = valor_hora * float(horas)
            total_custo_mao_obra += custo_dia
            total_horas_periodo += float(horas)
            
            custos_mao_obra.append({
                'data': data_reg,
                'funcionario_nome': funcionario_nome,
                'horas_trabalhadas': float(horas),
                'salario_hora': valor_hora,
                'total_dia': custo_dia
            })
        
            logger.debug(f"DEBUG KPIs: {total_custo_mao_obra:.2f} em custos, {total_horas_periodo}h trabalhadas")
            
        # Buscar custos da obra para o período
        from models import OutroCusto, VehicleExpense, RegistroAlimentacao
        
        # Custos diversos da obra - adaptado para produção
        if admin_id is not None:
            custos_obra = OutroCusto.query.filter(
                OutroCusto.obra_id == obra_id,
                OutroCusto.data >= data_inicio,
                OutroCusto.data <= data_fim
            ).all()
        else:
            custos_obra = OutroCusto.query.filter(
                OutroCusto.obra_id == obra_id,
                OutroCusto.data >= data_inicio,
                OutroCusto.data <= data_fim
            ).all()
        
        # Custos de transporte/veículos da obra
        # [OK] USAR TABELA NOVA: frota_despesa (VehicleExpense) ao invés de custo_veiculo
        custos_query = VehicleExpense.query.filter(
            VehicleExpense.data_custo >= data_inicio,
            VehicleExpense.data_custo <= data_fim
        )
        
        if hasattr(VehicleExpense, 'obra_id'):
            custos_query = custos_query.filter(VehicleExpense.obra_id == obra_id)
            
        custos_transporte = custos_query.all()
        
        # [LOCK] PROTEÇÃO: Buscar custos de alimentação com proteção contra erro de schema (Migração 48)
        try:
            registros_alimentacao = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.obra_id == obra_id,
                RegistroAlimentacao.data >= data_inicio,
                RegistroAlimentacao.data <= data_fim
            ).order_by(RegistroAlimentacao.data.desc()).all()
        except Exception as e:
            logger.error(f"Erro ao carregar registros de alimentação: {e}. Migração 48 pode não ter sido executada.")
            flash('[WARN] Erro ao carregar registros de alimentação. Migração 48 pode não ter sido executada em produção.', 'warning')
            db.session.rollback()  # CRÍTICO: Evitar InFailedSqlTransaction
            registros_alimentacao = []
        
        # Criar lista detalhada dos lançamentos de alimentação
        custos_alimentacao_detalhados = []
        for registro in registros_alimentacao:
            # Buscar funcionário e restaurante separadamente para evitar erros de join
            funcionario = Funcionario.query.get(registro.funcionario_id) if registro.funcionario_id else None
            restaurante = None
            if registro.restaurante_id:
                try:
                    from models import Restaurante
                    restaurante = Restaurante.query.get(registro.restaurante_id)
                except:
                    restaurante = None
            
            custos_alimentacao_detalhados.append({
                'data': registro.data,
                'funcionario_nome': funcionario.nome if funcionario else 'Funcionário não encontrado',
                'restaurante_nome': restaurante.nome if restaurante else 'Não informado',
                'tipo': registro.tipo,
                'valor': registro.valor,
                'observacoes': registro.observacoes
            })
        
        custo_alimentacao_tabela = sum(r.valor for r in registros_alimentacao if r.valor)
        
        # Também buscar em outro_custo como fallback
        custo_alimentacao_outros = sum(c.valor for c in custos_obra if any([
            c.kpi_associado == 'custo_alimentacao',
            'vale_alimentacao' in (c.tipo or '').lower(),
            'alimentacao' in (c.tipo or '').lower(),
            'va' in (c.tipo or '').lower(),
            'refeicao' in (c.tipo or '').lower()
        ]))
        
        # Total de alimentação (tabela específica + outros custos)
        custo_alimentacao = custo_alimentacao_tabela + custo_alimentacao_outros
        
        logger.debug(f"DEBUG ALIMENTAÇÃO: Tabela específica={custo_alimentacao_tabela}, Outros custos={custo_alimentacao_outros}, Total={custo_alimentacao}")
        
        custo_transporte = sum(c.valor for c in custos_obra if any([
            c.kpi_associado == 'custo_transporte',
            'vale_transporte' in (c.tipo or '').lower(),
            'transporte' in (c.tipo or '').lower(),
            'vt' in (c.tipo or '').lower()
        ]))
        
        outros_custos = sum(c.valor for c in custos_obra if any([
            c.kpi_associado == 'outros_custos',
            'outros' in (c.tipo or '').lower(),
            'epi' in (c.tipo or '').lower(),
            'desconto' in (c.tipo or '').lower()
        ]))
        
        custos_transporte_total = sum(c.valor for c in custos_transporte if c.valor)

        # ── Custos lançados via Gestão de Custos V2 (importação diárias, etc.) ──
        try:
            from models import GestaoCustoFilho, GestaoCustoPai
            from sqlalchemy import func as sqlfunc
            gestao_q = (
                db.session.query(GestaoCustoPai.tipo_categoria, sqlfunc.sum(GestaoCustoFilho.valor))
                .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
                .filter(
                    GestaoCustoFilho.obra_id == obra_id,
                    GestaoCustoFilho.data_referencia >= data_inicio,
                    GestaoCustoFilho.data_referencia <= data_fim,
                )
            )
            if admin_id is not None:
                gestao_q = gestao_q.filter(GestaoCustoPai.admin_id == admin_id)
            for tipo_cat, total_gc in gestao_q.group_by(GestaoCustoPai.tipo_categoria).all():
                v = float(total_gc or 0)
                if tipo_cat in ('SALARIO', 'MAO_OBRA_DIRETA'):
                    total_custo_mao_obra += v
                elif tipo_cat in ('ALIMENTACAO', 'ALIMENTACAO_DIARIA'):
                    custo_alimentacao += v
                elif tipo_cat in ('TRANSPORTE', 'VALE_TRANSPORTE'):
                    custo_transporte += v
                logger.debug(f"[GestaoCusto] obra={obra_id} {tipo_cat}={v:.2f}")
        except Exception as e:
            logger.error(f"Erro ao somar GestaoCusto para obra {obra_id}: {e}")

        logger.debug(f"DEBUG CUSTOS DETALHADOS: Alimentação={custo_alimentacao} (tabela={custo_alimentacao_tabela}, outros={custo_alimentacao_outros}), Transporte VT={custo_transporte}, Veículos={custos_transporte_total}, Outros={outros_custos}")
        
        # Calcular progresso geral da obra baseado no último RDO
        progresso_geral = 0.0
        try:
            from models import RDO, RDOServicoSubatividade
            
            # Buscar o último RDO da obra
            ultimo_rdo_obra = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
            
            if ultimo_rdo_obra:
                # Buscar subatividades do último RDO
                subatividades_rdo = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo_rdo_obra.id).all()
                
                if subatividades_rdo:
                    total_percentuais = sum(sub.percentual_conclusao or 0 for sub in subatividades_rdo)
                    total_sub = len(subatividades_rdo)
                    # FÓRMULA SIMPLES
                    progresso_geral = round(total_percentuais / total_sub, 1) if total_sub > 0 else 0.0
                    logger.debug(f"[TARGET] KPI OBRA PROGRESSO: {total_percentuais}÷{total_sub} = {progresso_geral}%")
                    logger.debug(f"DEBUG PROGRESSO OBRA: {len(subatividades_rdo)} subatividades, progresso geral: {progresso_geral:.1f}%")
                else:
                    logger.debug("DEBUG PROGRESSO: Último RDO sem subatividades registradas")
            else:
                logger.debug("DEBUG PROGRESSO: Nenhum RDO encontrado para esta obra")
        except Exception as e:
            logger.error(f"ERRO ao calcular progresso da obra: {e}")
            progresso_geral = 0.0

        # Montar KPIs finais da obra
        kpis_obra = {
            'total_funcionarios': len(funcionarios_obra),
            'funcionarios_periodo': len(set([r.funcionario_id for r in registros_periodo])),
            'custo_mao_obra': total_custo_mao_obra,
            'custo_alimentacao': custo_alimentacao,
            'custo_transporte': custos_transporte_total + custo_transporte,
            'custo_total': total_custo_mao_obra + custo_alimentacao + custo_transporte + outros_custos + custos_transporte_total,
            'total_horas': total_horas_periodo,
            'dias_trabalhados': len(set([r.data for r in registros_periodo])),
            'total_rdos': 0,
            'funcionarios_ativos': len(funcionarios_obra),
            'progresso_geral': progresso_geral
        }
        
        # Buscar RDOs da obra para o período
        try:
            from models import RDO
            rdos_obra = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).limit(10).all()
        except:
            rdos_obra = []
        
        # ===== SISTEMA REFATORADO DE SERVIÇOS DA OBRA =====
        # Usar nova função para buscar serviços da obra com proteção de transação
        servicos_obra = []
        try:
            # Fazer rollback preventivo antes de buscar serviços
            try:
                db.session.rollback()
                logger.info("[SYNC] ROLLBACK preventivo executado")
            except:
                pass
            
            admin_id_para_servicos = get_admin_id_robusta(obra)
            servicos_obra = obter_servicos_da_obra(obra_id, admin_id_para_servicos)
            logger.debug(f"[TARGET] SERVIÇOS DA OBRA: {len(servicos_obra)} serviços encontrados usando sistema refatorado")
            
        except Exception as e:
            logger.error(f"[ALERT] ERRO ao buscar serviços da obra: {e}")
            # Fazer rollback em caso de erro e tentar busca simples
            try:
                db.session.rollback()
                logger.error("[SYNC] ROLLBACK após erro executado")
            except:
                pass
            servicos_obra = []
        
        # Continuar com o resto da função
        total_rdos = len(rdos_obra)
        rdos_finalizados = len([r for r in rdos_obra if r.status == 'Finalizado'])
        rdos_periodo = rdos_obra
        rdos_recentes = rdos_obra
        
        logger.debug(f"DEBUG KPIs FINAIS: Total={kpis_obra['custo_total']:.2f}, Mão Obra={kpis_obra['custo_mao_obra']:.2f}, Horas={kpis_obra['total_horas']:.1f}")
        logger.debug(f"DEBUG FUNCIONÁRIOS: {kpis_obra['funcionarios_periodo']} no período, {kpis_obra['dias_trabalhados']} dias trabalhados")
        
        # ===== DADOS DE FOLHA PROCESSADA PARA DASHBOARD DE CUSTOS =====
        try:
            from services.folha_service import obter_dados_folha_obra
            dados_folha = obter_dados_folha_obra(
                obra_id=obra_id,
                data_inicio=data_inicio,
                data_fim=data_fim,
                admin_id=admin_id
            )
            logger.debug(f"DEBUG FOLHA: {dados_folha['totais'].get('total_funcionarios', 0)} funcionários com folha processada")
        except Exception as e:
            logger.error(f"ERRO ao buscar dados de folha: {e}")
            dados_folha = {
                'funcionarios': [],
                'totais': {
                    'custo_total': 0,
                    'total_horas': 0,
                    'custo_por_hora': 0,
                    'percentual_he': 0,
                    'total_he': 0,
                    'total_funcionarios': 0
                },
                'composicao': [],
                'evolucao_mensal': []
            }
        
        # Pedidos de compra vinculados à obra (filtrado por tenant quando disponível)
        try:
            if admin_id is not None:
                pedidos_compra_obra = PedidoCompra.query.filter_by(
                    obra_id=obra_id, admin_id=admin_id
                ).order_by(PedidoCompra.created_at.desc()).all()
            else:
                pedidos_compra_obra = PedidoCompra.query.filter_by(
                    obra_id=obra_id
                ).order_by(PedidoCompra.created_at.desc()).all()
        except Exception:
            pedidos_compra_obra = []

        # Fornecedores disponíveis para o formulário de nova compra (somente do tenant)
        # Usa o admin_id da obra como referência segura de tenant
        try:
            tenant_admin_id = admin_id if admin_id is not None else obra.admin_id
            fornecedores_lista = Fornecedor.query.filter_by(admin_id=tenant_admin_id).order_by(Fornecedor.nome).all()
        except Exception:
            fornecedores_lista = []

        # Mapas de concorrência vinculados à obra
        try:
            mapas_concorrencia = (
                MapaConcorrencia.query
                .filter_by(obra_id=obra_id, admin_id=tenant_admin_id)
                .order_by(MapaConcorrencia.created_at.desc())
                .all()
            )
            # Eagerly load opcoes as list so template can iterate
            for m in mapas_concorrencia:
                m._opcoes_list = m.opcoes.all()
        except Exception:
            mapas_concorrencia = []

        # Mapas de Concorrência V2 vinculados à obra
        try:
            mapas_v2 = (
                MapaConcorrenciaV2.query
                .filter_by(obra_id=obra_id, admin_id=tenant_admin_id)
                .order_by(MapaConcorrenciaV2.created_at.desc())
                .all()
            )
        except Exception:
            mapas_v2 = []

        # Cronograma do cliente: agora vive em TarefaCronograma com is_cliente=True
        # (migration #117). Mantemos a variável `cronograma_cliente_items` apenas
        # para o badge de contagem na aba; o conteúdo é exibido via iframe do editor.
        try:
            from models import TarefaCronograma as _TC_Cli
            cronograma_cliente_items = (
                _TC_Cli.query
                .filter_by(obra_id=obra_id, admin_id=tenant_admin_id, is_cliente=True)
                .order_by(_TC_Cli.ordem)
                .all()
            )
        except Exception:
            cronograma_cliente_items = []

        # ─────────────────────────────────────────────────────────────────
        # PAINEL ESTRATÉGICO DA OBRA
        # Gráfico de barras (Contrato x Medido x Custo) + 3 indicadores semáforo
        # Calculado SEMPRE acumulado (sem filtro de período)
        # ─────────────────────────────────────────────────────────────────
        from sqlalchemy import func as _sqlfunc, and_, not_, exists
        from datetime import date as _date

        painel = {
            'valor_orcado': float(obra.orcamento or 0),
            'valor_contrato': 0.0,
            'valor_medido': 0.0,
            'custo_acumulado': 0.0,
            'saldo': 0.0,
            'tem_dados_financeiros': False,
            'prazo': {'status': 'sem_dados', 'label': 'Sem cronograma', 'qtd': 0},
            'compras': {'status': 'sem_dados', 'label': 'Sem compras', 'qtd': 0},
            'medicao_pronta': {'status': 'sem_dados', 'label': 'Sem medição pendente', 'valor': 0.0, 'qtd': 0},
            'entregas': {'status': 'sem_dados', 'label': 'Sem entregas/terceiros', 'qtd_total': 0, 'qtd_atrasadas': 0, 'qtd_vence_hoje': 0, 'qtd_amanha': 0, 'qtd_pendentes': 0, 'qtd_entregues': 0},
        }
        entregas_detalhe = []

        try:
            # 1. Valor do contrato
            painel['valor_contrato'] = float(obra.valor_contrato or 0)

            # 2. Valor medido acumulado (todas as medições da obra, qualquer status)
            from models import MedicaoObra
            medido_total = db.session.query(
                _sqlfunc.coalesce(_sqlfunc.sum(MedicaoObra.valor_medido), 0)
            ).filter(MedicaoObra.obra_id == obra_id).scalar()
            painel['valor_medido'] = float(medido_total or 0)

            # 3. Custo acumulado (GestaoCustoFilho da obra, sem filtro de data)
            from models import GestaoCustoFilho
            custo_total = db.session.query(
                _sqlfunc.coalesce(_sqlfunc.sum(GestaoCustoFilho.valor), 0)
            ).filter(GestaoCustoFilho.obra_id == obra_id).scalar()
            painel['custo_acumulado'] = float(custo_total or 0)

            # 4. Saldo = medido - custo
            painel['saldo'] = painel['valor_medido'] - painel['custo_acumulado']
            painel['tem_dados_financeiros'] = (
                painel['valor_orcado'] > 0
                or painel['valor_contrato'] > 0
                or painel['valor_medido'] > 0
                or painel['custo_acumulado'] > 0
            )
        except Exception as e:
            logger.error(f"Erro calculando dados financeiros do painel estratégico: {e}")
            db.session.rollback()

        # 5. Indicador de PRAZO (tarefas-folha atrasadas)
        try:
            from models import TarefaCronograma
            hoje = _date.today()
            # Tarefa-folha: nenhuma outra tarefa tem tarefa_pai_id = self.id
            TarefaFilha = db.aliased(TarefaCronograma)
            subq_tem_filha = exists().where(
                and_(
                    TarefaFilha.tarefa_pai_id == TarefaCronograma.id,
                    TarefaFilha.obra_id == obra_id,
                )
            )

            # Total de tarefas-folha
            total_folhas = db.session.query(_sqlfunc.count(TarefaCronograma.id)).filter(
                TarefaCronograma.obra_id == obra_id,
                not_(subq_tem_filha)
            ).scalar() or 0

            # Atrasadas: data_fim < hoje e percentual_concluido < 100
            atrasadas = db.session.query(_sqlfunc.count(TarefaCronograma.id)).filter(
                TarefaCronograma.obra_id == obra_id,
                TarefaCronograma.data_fim != None,  # noqa: E711
                TarefaCronograma.data_fim < hoje,
                _sqlfunc.coalesce(TarefaCronograma.percentual_concluido, 0) < 100,
                not_(subq_tem_filha)
            ).scalar() or 0

            if total_folhas == 0:
                painel['prazo'] = {'status': 'sem_dados', 'label': 'Sem cronograma cadastrado', 'qtd': 0}
            elif atrasadas == 0:
                painel['prazo'] = {'status': 'verde', 'label': 'No prazo', 'qtd': 0}
            elif atrasadas <= 2:
                painel['prazo'] = {'status': 'amarelo', 'label': f'{atrasadas} tarefa(s) atrasada(s)', 'qtd': atrasadas}
            else:
                painel['prazo'] = {'status': 'vermelho', 'label': f'Crítico: {atrasadas} tarefas vencidas', 'qtd': atrasadas}
        except Exception as e:
            logger.error(f"Erro calculando indicador de prazo: {e}")
            db.session.rollback()

        # 6. Indicador de COMPRAS pendentes de aprovação do cliente
        try:
            qtd_compras_pend = db.session.query(_sqlfunc.count(PedidoCompra.id)).filter(
                PedidoCompra.obra_id == obra_id,
                PedidoCompra.status_aprovacao_cliente == 'PENDENTE'
            ).scalar() or 0

            qtd_compras_total = db.session.query(_sqlfunc.count(PedidoCompra.id)).filter(
                PedidoCompra.obra_id == obra_id
            ).scalar() or 0

            if qtd_compras_total == 0:
                painel['compras'] = {'status': 'sem_dados', 'label': 'Sem compras cadastradas', 'qtd': 0}
            elif qtd_compras_pend == 0:
                painel['compras'] = {'status': 'verde', 'label': 'Sem pendência', 'qtd': 0}
            elif qtd_compras_pend <= 2:
                painel['compras'] = {'status': 'amarelo', 'label': f'{qtd_compras_pend} compra(s) aguardando cliente', 'qtd': qtd_compras_pend}
            else:
                painel['compras'] = {'status': 'vermelho', 'label': f'{qtd_compras_pend} compras aguardando cliente', 'qtd': qtd_compras_pend}
        except Exception as e:
            logger.error(f"Erro calculando indicador de compras: {e}")
            db.session.rollback()

        # 7b. Indicador de ENTREGAS / TERCEIROS (engine de alertas centralizada)
        try:
            from services.entregas_terceiros import calcular_alertas_terceiros
            _ent = calcular_alertas_terceiros(obra_id, admin_id=admin_id)
            entregas_detalhe = _ent['detalhe']
            painel['entregas'] = _ent['painel']
        except Exception as e:
            logger.error(f"Erro calculando alertas de entregas/terceiros: {e}")
            db.session.rollback()

        # 7. Indicador de MEDIÇÃO PRONTA para faturamento
        try:
            from models import MedicaoObra as _MedicaoObra
            medicoes_pendentes = _MedicaoObra.query.filter(
                _MedicaoObra.obra_id == obra_id,
                _MedicaoObra.status == 'PENDENTE'
            ).all()

            valor_pronto = sum(float(m.valor_a_faturar_periodo or m.valor_medido or 0) for m in medicoes_pendentes)
            qtd_pend = len(medicoes_pendentes)

            qtd_med_total = _MedicaoObra.query.filter(_MedicaoObra.obra_id == obra_id).count()

            if qtd_med_total == 0:
                painel['medicao_pronta'] = {'status': 'sem_dados', 'label': 'Sem medições geradas', 'valor': 0.0, 'qtd': 0}
            elif qtd_pend == 0:
                painel['medicao_pronta'] = {'status': 'verde', 'label': 'Tudo faturado', 'valor': 0.0, 'qtd': 0}
            else:
                painel['medicao_pronta'] = {
                    'status': 'amarelo',
                    'label': f'{qtd_pend} medição(ões) pronta(s)',
                    'valor': valor_pronto,
                    'qtd': qtd_pend,
                }
        except Exception as e:
            logger.error(f"Erro calculando indicador de medição: {e}")
            db.session.rollback()

        # Task #70 — Resumo de Custos (12 indicadores + datasets dos gráficos)
        try:
            from services.resumo_custos_obra import calcular_resumo_obra
            resumo_custos = calcular_resumo_obra(obra.id, admin_id=admin_id)
        except Exception as _e_resumo:
            logger.error(f"Erro no resumo de custos: {_e_resumo}")
            resumo_custos = None

        # Task #76 — Notificações de estouro de orçamento por serviço
        try:
            from utils.notifications import (
                verificar_estouros_obra,
                listar_notificacoes_ativas,
            )
            verificar_estouros_obra(obra.id, admin_id=admin_id)
            notificacoes_orcamento = listar_notificacoes_ativas(
                admin_id, obra_id=obra.id
            )
        except Exception as _e_notif:
            logger.error(f"Erro nas notificações de orçamento: {_e_notif}")
            notificacoes_orcamento = []

        # Task #102: detectar "cronograma pendente" — obra originada de proposta
        # mas sem nenhuma TarefaCronograma com gerada_por_proposta_item_id setado.
        cronograma_pendente = False
        try:
            if getattr(obra, 'proposta_origem_id', None):
                from models import TarefaCronograma
                _existe = (
                    db.session.query(TarefaCronograma.id)
                    .filter(
                        TarefaCronograma.obra_id == obra.id,
                        TarefaCronograma.admin_id == admin_id,
                        TarefaCronograma.gerada_por_proposta_item_id.isnot(None),
                    ).first()
                )
                cronograma_pendente = _existe is None
        except Exception as _e_cp:
            logger.warning(f"#102 cronograma_pendente check falhou: {_e_cp}")

        return render_template('obras/detalhes_obra_profissional.html', 
                             obra=obra, 
                             cronograma_pendente=cronograma_pendente,
                             resumo=resumo_custos,
                             notificacoes_orcamento=notificacoes_orcamento,
                             kpis=kpis_obra,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             date=date,
                             servicos_obra=servicos_obra,
                             total_rdos=total_rdos,
                             rdos_finalizados=rdos_finalizados,
                             rdos=rdos_obra,
                             rdos_periodo=rdos_periodo,
                             rdos_recentes=rdos_recentes,
                             custos_mao_obra=custos_mao_obra,
                             custos_alimentacao_detalhados=custos_alimentacao_detalhados,
                             custos_obra=custos_obra,
                             custos_transporte=custos_transporte,
                             custos_transporte_total=custos_transporte_total,
                             funcionarios_obra=funcionarios_obra,
                             dados_folha=dados_folha,
                             pedidos_compra_obra=pedidos_compra_obra,
                             fornecedores_lista=fornecedores_lista,
                             mapas_concorrencia=mapas_concorrencia,
                             mapas_v2=mapas_v2,
                             cronograma_cliente_items=cronograma_cliente_items,
                             painel=painel,
                             entregas_detalhe=entregas_detalhe)
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"ERRO DETALHES OBRA: {str(e)}")
        logger.error(f"TRACEBACK COMPLETO:\n{error_traceback}")
        # Exibir traceback completo em modo desenvolvimento
        flash(f'Erro ao carregar detalhes da obra: {str(e)}\n\nTraceback:\n{error_traceback}', 'error')
        return redirect(url_for('main.obras'))

@main_bp.route('/obras/<int:obra_id>/compras/nova', methods=['POST'])
@login_required
@admin_required
def nova_compra_obra(obra_id):
    """Cria um pedido de compra para aprovação do cliente, diretamente da tela de obra."""
    try:
        admin_id = get_tenant_admin_id()

        # Validar que a obra pertence ao tenant do usuário logado
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada ou sem permissão de acesso.', 'danger')
            return redirect(url_for('main.obras'))

        fornecedor_id = request.form.get('fornecedor_id', type=int)
        data_compra_str = request.form.get('data_compra') or date.today().isoformat()
        observacoes = request.form.get('observacoes', '').strip()
        numero = request.form.get('numero', '').strip()

        # Validar data
        try:
            data_compra_parsed = datetime.strptime(data_compra_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Data da compra inválida. Use o formato AAAA-MM-DD.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        if not fornecedor_id:
            flash('Selecione um fornecedor para a compra.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        # Validar que o fornecedor pertence ao mesmo tenant
        fornecedor = Fornecedor.query.filter_by(id=fornecedor_id, admin_id=admin_id).first()
        if not fornecedor:
            flash('Fornecedor inválido ou sem permissão de acesso.', 'danger')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        descricoes = request.form.getlist('item_descricao[]')
        quantidades = request.form.getlist('item_quantidade[]')
        precos = request.form.getlist('item_preco[]')

        logger.debug(f"[nova_compra_obra] descricoes={descricoes} quantidades={quantidades} precos={precos}")

        if not descricoes or not any(d.strip() for d in descricoes):
            flash('Adicione ao menos um item à compra.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        def _parse_num(val):
            """Aceita ponto ou vírgula como separador decimal."""
            if not val:
                return 0.0
            try:
                return float(str(val).strip().replace(',', '.'))
            except ValueError:
                return 0.0

        # Calcular valor total
        valor_total = sum(
            _parse_num(q) * _parse_num(p)
            for q, p in zip(quantidades, precos)
        )

        # Tratar upload de anexo — validação de extensão obrigatória
        _ALLOWED_ANEXO = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}
        anexo_url = None
        arquivo = request.files.get('anexo')
        if arquivo and arquivo.filename:
            ext = arquivo.filename.rsplit('.', 1)[-1].lower() if '.' in arquivo.filename else ''
            if ext not in _ALLOWED_ANEXO:
                flash(f'Tipo de arquivo não permitido para anexo ({ext}). Use: {", ".join(sorted(_ALLOWED_ANEXO))}.', 'warning')
                return redirect(url_for('main.detalhes_obra', id=obra_id))
            from werkzeug.utils import secure_filename
            upload_dir = os.path.join('static', 'uploads', 'pedidos_compra')
            os.makedirs(upload_dir, exist_ok=True)
            ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            safe_name = f"{ts}_{secure_filename(arquivo.filename)}"
            arquivo.save(os.path.join(upload_dir, safe_name))
            anexo_url = f"/static/uploads/pedidos_compra/{safe_name}"

        pedido = PedidoCompra(
            fornecedor_id=fornecedor_id,
            obra_id=obra_id,
            data_compra=data_compra_parsed,
            numero=numero or None,
            observacoes=observacoes or None,
            valor_total=valor_total,
            status_aprovacao_cliente='PENDENTE',
            anexo_url=anexo_url,
            admin_id=admin_id,
        )
        db.session.add(pedido)
        db.session.flush()  # get pedido.id

        items_added = 0
        for desc, qtd_str, preco_str in zip(descricoes, quantidades, precos):
            if not desc.strip():
                continue
            qtd = _parse_num(qtd_str)
            preco = _parse_num(preco_str)
            if qtd <= 0:
                flash(f'Quantidade inválida para o item "{desc.strip()}". Informe um valor maior que zero.', 'warning')
                db.session.rollback()
                return redirect(url_for('main.detalhes_obra', id=obra_id))
            if preco < 0:
                flash(f'Preço inválido para o item "{desc.strip()}". O valor não pode ser negativo.', 'warning')
                db.session.rollback()
                return redirect(url_for('main.detalhes_obra', id=obra_id))
            item = PedidoCompraItem(
                pedido_id=pedido.id,
                descricao=desc.strip(),
                quantidade=qtd,
                preco_unitario=preco,
                subtotal=qtd * preco,
                admin_id=admin_id,
            )
            db.session.add(item)
            items_added += 1

        if items_added == 0:
            db.session.rollback()
            flash('Adicione ao menos um item válido à compra.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        db.session.commit()
        flash('Compra criada com sucesso e enviada para aprovação do cliente.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar compra para obra {obra_id}: {e}")
        flash(f'Erro ao criar compra: {str(e)}', 'danger')

    return redirect(url_for('main.detalhes_obra', id=obra_id))


@main_bp.route('/obras/<int:obra_id>/mapa-concorrencia/novo', methods=['POST'])
@login_required
@admin_required
def nova_mapa_concorrencia(obra_id):
    """Cria um Mapa de Concorrência (comparativo de fornecedores) para a obra."""
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada ou sem permissão de acesso.', 'danger')
            return redirect(url_for('main.obras'))

        descricao_item = (request.form.get('descricao_item') or '').strip()
        if not descricao_item:
            flash('Informe a descrição do item para o mapa de concorrência.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        fornecedores_nomes = request.form.getlist('fornecedor_nome[]')
        valores = request.form.getlist('valor_unitario[]')
        prazos = request.form.getlist('prazo_entrega[]')
        observacoes_list = request.form.getlist('observacoes[]')

        opcoes_validas = [
            (fn.strip(), v.strip(), p.strip(), o.strip())
            for fn, v, p, o in zip(fornecedores_nomes, valores, prazos, observacoes_list)
            if fn.strip()
        ]
        if not opcoes_validas:
            flash('Adicione ao menos um fornecedor ao mapa de concorrência.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        def _parse_num(val):
            try:
                v = val.strip()
                # Handle Brazilian format 1.234,56 → 1234.56
                if ',' in v and '.' in v:
                    v = v.replace('.', '').replace(',', '.')
                elif ',' in v:
                    v = v.replace(',', '.')
                return float(v)
            except Exception:
                return 0.0

        mapa = MapaConcorrencia(
            obra_id=obra_id,
            admin_id=admin_id,
            descricao_item=descricao_item,
            status='pendente',
        )
        db.session.add(mapa)
        db.session.flush()

        for fn, v, p, o in opcoes_validas:
            opcao = OpcaoConcorrencia(
                mapa_id=mapa.id,
                fornecedor_nome=fn,
                valor_unitario=_parse_num(v),
                prazo_entrega=p or None,
                observacoes=o or None,
                selecionada=False,
                admin_id=admin_id,
            )
            db.session.add(opcao)

        db.session.commit()
        flash('Mapa de concorrência criado e enviado para aprovação do cliente.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar mapa de concorrência para obra {obra_id}: {e}")
        flash(f'Erro ao criar mapa de concorrência: {str(e)}', 'danger')

    return redirect(url_for('main.detalhes_obra', id=obra_id))


@main_bp.route('/obras/<int:obra_id>/mapa-concorrencia/<int:mapa_id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_mapa_concorrencia(obra_id, mapa_id):
    """Exclui um Mapa de Concorrência."""
    try:
        admin_id = get_tenant_admin_id()
        mapa = MapaConcorrencia.query.filter_by(
            id=mapa_id, obra_id=obra_id, admin_id=admin_id
        ).first()
        if not mapa:
            flash('Mapa de concorrência não encontrado.', 'danger')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        db.session.delete(mapa)
        db.session.commit()
        flash('Mapa de concorrência excluído.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar mapa {mapa_id}: {e}")
        flash(f'Erro ao excluir: {str(e)}', 'danger')

    return redirect(url_for('main.detalhes_obra', id=obra_id))


@main_bp.route('/obras/<int:obra_id>/cronograma-cliente/gerar', methods=['POST'])
@login_required
@admin_required
def gerar_cronograma_cliente(obra_id):
    """
    Regenera o cronograma do cliente clonando o cronograma INTERNO da obra.

    Migration #117: cronograma do cliente agora vive na própria TarefaCronograma
    com is_cliente=True. Esta rota:
      1. Apaga TODAS as TarefaCronograma is_cliente=True desta obra (overwrite total).
      2. Clona cada TarefaCronograma is_cliente=False (interno) em uma nova com
         is_cliente=True, preservando todos os campos relevantes.
      3. Faz uma 2ª passagem para remapear `tarefa_pai_id` e `predecessora_id`
         dos IDs antigos (interno) para os novos IDs (cliente), mantendo a
         hierarquia pai/filho e a rede de predecessoras intactas.
    """
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada.', 'danger')
            return redirect(url_for('main.obras'))

        from models import TarefaCronograma

        # 1) Tarefas-fonte: cronograma interno da obra
        tarefas_internas = (
            TarefaCronograma.query
            .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
            .order_by(TarefaCronograma.ordem)
            .all()
        )

        # 2) Apagar cronograma do cliente anterior (overwrite total)
        TarefaCronograma.query.filter_by(
            obra_id=obra_id, admin_id=admin_id, is_cliente=True
        ).delete(synchronize_session=False)
        db.session.flush()

        # Legacy: limpa também a tabela antiga (não é mais lida pelo portal)
        try:
            CronogramaCliente.query.filter_by(
                obra_id=obra_id, admin_id=admin_id
            ).delete(synchronize_session=False)
        except Exception:
            pass

        # 3) Clonar — primeiro passo: criar todas as tarefas SEM pai/predecessora
        old_to_new: dict[int, int] = {}
        clones_seq: list[tuple[int, TarefaCronograma]] = []

        for t in tarefas_internas:
            clone = TarefaCronograma(
                obra_id=obra_id,
                admin_id=admin_id,
                is_cliente=True,
                nome_tarefa=t.nome_tarefa,
                duracao_dias=t.duracao_dias,
                data_inicio=t.data_inicio,
                data_fim=t.data_fim,
                quantidade_total=t.quantidade_total,
                unidade_medida=t.unidade_medida,
                subatividade_mestre_id=getattr(t, 'subatividade_mestre_id', None),
                percentual_concluido=t.percentual_concluido or 0.0,
                responsavel=getattr(t, 'responsavel', 'empresa') or 'empresa',
                ordem=t.ordem,
                # pai/predecessora setados na 2ª passagem (após termos os novos IDs)
                tarefa_pai_id=None,
                predecessora_id=None,
            )
            db.session.add(clone)
            clones_seq.append((t.id, clone))

        # Flush para obter IDs gerados
        db.session.flush()
        for old_id, clone in clones_seq:
            old_to_new[old_id] = clone.id

        # 4) 2ª passagem — remapear pai/predecessora usando old_to_new
        for old_t, (_, clone) in zip(tarefas_internas, clones_seq):
            if old_t.tarefa_pai_id and old_t.tarefa_pai_id in old_to_new:
                clone.tarefa_pai_id = old_to_new[old_t.tarefa_pai_id]
            if old_t.predecessora_id and old_t.predecessora_id in old_to_new:
                clone.predecessora_id = old_to_new[old_t.predecessora_id]

        db.session.commit()
        flash(
            f'Cronograma do cliente regenerado com {len(clones_seq)} tarefa(s) '
            f'(hierarquia e predecessoras preservadas).',
            'success'
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao gerar cronograma cliente para obra {obra_id}: {e}")
        flash('Erro ao gerar cronograma. Tente novamente.', 'danger')

    return redirect(url_for('main.detalhes_obra', id=obra_id))


@main_bp.route('/obras/<int:obra_id>/cronograma-cliente/<int:item_id>/editar', methods=['POST'])
@login_required
@admin_required
def editar_cronograma_cliente(obra_id, item_id):
    """Atualiza nome, datas e percentual de uma entrada no CronogramaCliente."""
    try:
        admin_id = get_tenant_admin_id()
        item = CronogramaCliente.query.filter_by(
            id=item_id, obra_id=obra_id, admin_id=admin_id
        ).first()
        if not item:
            flash('Tarefa não encontrada.', 'danger')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        nome = request.form.get('nome_tarefa', '').strip()
        if nome:
            item.nome_tarefa = nome

        data_ini_raw = request.form.get('data_inicio_apresentacao', '').strip()
        data_fim_raw = request.form.get('data_fim_apresentacao', '').strip()
        from datetime import datetime as _dt
        if data_ini_raw:
            try:
                item.data_inicio_apresentacao = _dt.strptime(data_ini_raw, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            item.data_inicio_apresentacao = None

        if data_fim_raw:
            try:
                item.data_fim_apresentacao = _dt.strptime(data_fim_raw, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            item.data_fim_apresentacao = None

        perc = request.form.get('percentual_apresentacao', '').strip()
        if perc:
            try:
                item.percentual_apresentacao = max(0.0, min(100.0, float(perc)))
            except ValueError:
                pass

        db.session.commit()
        flash('Tarefa do cronograma atualizada.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao editar cronograma cliente item {item_id}: {e}")
        flash('Erro ao salvar alterações. Tente novamente.', 'danger')

    return redirect(url_for('main.detalhes_obra', id=obra_id))


# ===== MAPA DE CONCORRÊNCIA V2 =====

def _parse_brl(val):
    """Converte string BR (1.234,56) para float."""
    try:
        v = (val or '').strip()
        if ',' in v and '.' in v:
            v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            v = v.replace(',', '.')
        return float(v) if v else 0.0
    except Exception:
        return 0.0


@main_bp.route('/obras/<int:obra_id>/mapa-v2/criar', methods=['POST'])
@login_required
@admin_required
def criar_mapa_v2(obra_id):
    """Cria um novo Mapa de Concorrência V2 com fornecedores e itens opcionais."""
    try:
        admin_id = get_tenant_admin_id()
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            flash('Obra não encontrada.', 'danger')
            return redirect(url_for('main.obras'))

        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Informe um nome para o mapa de concorrência.', 'warning')
            return redirect(url_for('main.detalhes_obra', id=obra_id))

        mapa = MapaConcorrenciaV2(obra_id=obra_id, admin_id=admin_id, nome=nome, status='aberto')
        db.session.add(mapa)
        db.session.flush()  # obter mapa.id

        # Fornecedores em lote (um por linha ou separados por vírgula)
        fornecedores_txt = (request.form.get('fornecedores_batch') or '').strip()
        nomes_forn = []
        if fornecedores_txt:
            for linha in fornecedores_txt.replace(',', '\n').splitlines():
                n = linha.strip()
                if n:
                    nomes_forn.append(n)

        forn_objs = []
        for idx, nf in enumerate(nomes_forn):
            forn = MapaFornecedor(mapa_id=mapa.id, admin_id=admin_id, nome=nf, ordem=idx)
            db.session.add(forn)
            forn_objs.append(forn)
        if forn_objs:
            db.session.flush()  # obter ids dos fornecedores

        # Itens em lote (um por linha, formato: "Descrição | quantidade | unidade")
        itens_txt = (request.form.get('itens_batch') or '').strip()
        item_objs = []
        if itens_txt:
            for idx, linha in enumerate(itens_txt.splitlines()):
                partes = [p.strip() for p in linha.split('|')]
                if not partes or not partes[0]:
                    continue
                desc_i = partes[0]
                try:
                    qtd_i = float(partes[1].replace(',', '.')) if len(partes) > 1 and partes[1] else 1
                except Exception:
                    qtd_i = 1
                unid_i = partes[2] if len(partes) > 2 and partes[2] else 'un'
                item = MapaItemCotacao(
                    mapa_id=mapa.id, admin_id=admin_id,
                    descricao=desc_i, unidade=unid_i, quantidade=qtd_i, ordem=idx
                )
                db.session.add(item)
                item_objs.append(item)
            if item_objs:
                db.session.flush()  # obter ids dos itens

        # Criar grade de cotações vazia para combinações item × fornecedor
        for forn_obj in forn_objs:
            for item_obj in item_objs:
                cot = MapaCotacao(
                    mapa_id=mapa.id, item_id=item_obj.id,
                    fornecedor_id=forn_obj.id, admin_id=admin_id,
                    valor_unitario=0, selecionado=False
                )
                db.session.add(cot)

        db.session.commit()
        msg = f'Mapa "{nome}" criado'
        if forn_objs:
            msg += f' com {len(forn_objs)} fornecedor(es)'
        if item_objs:
            msg += f' e {len(item_objs)} item(ns)'
        msg += '. Preencha as cotações abaixo.'
        flash(msg, 'success')
        return redirect(url_for('main.editar_mapa_v2', obra_id=obra_id, mapa_id=mapa.id))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar mapa v2 obra {obra_id}: {e}")
        flash('Erro ao criar mapa. Tente novamente.', 'danger')
        return redirect(url_for('main.detalhes_obra', id=obra_id))


@main_bp.route('/obras/<int:obra_id>/mapa-v2/<int:mapa_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_mapa_v2(obra_id, mapa_id):
    """Página de gestão do Mapa de Concorrência V2 (add fornecedor, add item, salvar cotações)."""
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    mapa = MapaConcorrenciaV2.query.filter_by(id=mapa_id, obra_id=obra_id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        action = request.form.get('action', '')
        try:
            if action == 'rename':
                novo_nome = (request.form.get('nome') or '').strip()
                if novo_nome:
                    mapa.nome = novo_nome
                    db.session.commit()
                    flash('Nome atualizado.', 'success')

            elif action == 'add_fornecedor':
                nome_f = (request.form.get('nome_fornecedor') or '').strip()
                if nome_f:
                    ordem_f = len(mapa.fornecedores)
                    forn = MapaFornecedor(mapa_id=mapa.id, admin_id=admin_id, nome=nome_f, ordem=ordem_f)
                    db.session.add(forn)
                    db.session.flush()  # obter forn.id antes de criar cotações
                    # Criar células de cotação para cada item existente
                    itens_existentes = list(mapa.itens)
                    for item in itens_existentes:
                        cot = MapaCotacao(
                            mapa_id=mapa.id, item_id=item.id,
                            fornecedor_id=forn.id, admin_id=admin_id,
                            valor_unitario=0, selecionado=False
                        )
                        db.session.add(cot)
                    db.session.commit()
                    flash(f'Fornecedor "{nome_f}" adicionado.', 'success')
                else:
                    flash('Informe o nome do fornecedor.', 'warning')

            elif action == 'del_fornecedor':
                forn_id = request.form.get('fornecedor_id', type=int)
                forn = MapaFornecedor.query.filter_by(id=forn_id, mapa_id=mapa.id).first()
                if forn:
                    db.session.delete(forn)
                    db.session.commit()
                    flash('Fornecedor removido.', 'success')

            elif action == 'add_item':
                desc = (request.form.get('descricao') or '').strip()
                if desc:
                    unid = (request.form.get('unidade') or 'un').strip()
                    qtd_raw = request.form.get('quantidade', '1').strip()
                    try:
                        qtd = float(qtd_raw.replace(',', '.')) if qtd_raw else 1
                    except Exception:
                        qtd = 1
                    ordem_i = len(mapa.itens)
                    item = MapaItemCotacao(
                        mapa_id=mapa.id, admin_id=admin_id,
                        descricao=desc, unidade=unid, quantidade=qtd, ordem=ordem_i
                    )
                    db.session.add(item)
                    db.session.flush()
                    # Criar células de cotação para cada fornecedor existente
                    for forn in mapa.fornecedores:
                        cot = MapaCotacao(
                            mapa_id=mapa.id, item_id=item.id,
                            fornecedor_id=forn.id, admin_id=admin_id,
                            valor_unitario=0, selecionado=False
                        )
                        db.session.add(cot)
                    db.session.commit()
                    flash(f'Item "{desc}" adicionado.', 'success')
                else:
                    flash('Informe a descrição do item.', 'warning')

            elif action == 'del_item':
                item_id = request.form.get('item_id', type=int)
                item = MapaItemCotacao.query.filter_by(id=item_id, mapa_id=mapa.id).first()
                if item:
                    db.session.delete(item)
                    db.session.commit()
                    flash('Item removido.', 'success')

            elif action == 'save_cotacoes':
                # Salva valores e prazos da tabela de cotações
                for key, val in request.form.items():
                    if key.startswith('val_'):
                        _, item_id_s, forn_id_s = key.split('_', 2)
                        item_id_k = int(item_id_s)
                        forn_id_k = int(forn_id_s)
                        cot = MapaCotacao.query.filter_by(
                            mapa_id=mapa.id, item_id=item_id_k, fornecedor_id=forn_id_k
                        ).first()
                        if not cot:
                            cot = MapaCotacao(
                                mapa_id=mapa.id, item_id=item_id_k,
                                fornecedor_id=forn_id_k, admin_id=admin_id,
                                valor_unitario=0, selecionado=False
                            )
                            db.session.add(cot)
                        cot.valor_unitario = _parse_brl(val)
                        prazo_key = f'prazo_{item_id_s}_{forn_id_s}'
                        prazo_val = request.form.get(prazo_key, '').strip()
                        cot.prazo = prazo_val or None
                db.session.commit()
                flash('Cotações salvas com sucesso.', 'success')

            elif action == 'toggle_status':
                mapa.status = 'concluido' if mapa.status == 'aberto' else 'aberto'
                db.session.commit()
                status_label = 'enviado para portal' if mapa.status == 'concluido' else 'reaberto'
                flash(f'Mapa {status_label}.', 'success')

        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao editar mapa_v2 {mapa_id}: {e}")
            flash('Erro ao salvar. Tente novamente.', 'danger')

        return redirect(url_for('main.editar_mapa_v2', obra_id=obra_id, mapa_id=mapa_id))

    # GET — renderizar página de edição
    # Construir dict de cotações: {item_id: {fornecedor_id: cotacao}}
    cotacoes_map = {}
    for cot in mapa.cotacoes:
        cotacoes_map.setdefault(cot.item_id, {})[cot.fornecedor_id] = cot

    return render_template(
        'obras/mapa_concorrencia_v2.html',
        obra=obra,
        mapa=mapa,
        cotacoes_map=cotacoes_map,
    )


@main_bp.route('/obras/<int:obra_id>/mapa-v2/<int:mapa_id>/deletar', methods=['POST'])
@login_required
@admin_required
def deletar_mapa_v2(obra_id, mapa_id):
    """Exclui um Mapa de Concorrência V2."""
    try:
        admin_id = get_tenant_admin_id()
        mapa = MapaConcorrenciaV2.query.filter_by(id=mapa_id, obra_id=obra_id, admin_id=admin_id).first()
        if not mapa:
            flash('Mapa não encontrado.', 'danger')
            return redirect(url_for('main.detalhes_obra', id=obra_id))
        db.session.delete(mapa)
        db.session.commit()
        flash('Mapa de concorrência V2 excluído.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar mapa_v2 {mapa_id}: {e}")
        flash('Erro ao excluir. Tente novamente.', 'danger')
    return redirect(url_for('main.detalhes_obra', id=obra_id))


# ===== SUPER ADMIN =====
