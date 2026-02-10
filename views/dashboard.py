from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, send_file, session, Response
from flask_login import login_required, current_user
from models import db, Usuario, TipoUsuario, Funcionario, Funcao, Departamento, HorarioTrabalho, Obra, RDO, RDOMaoObra, RDOEquipamento, RDOOcorrencia, RDOFoto, AlocacaoEquipe, Servico, ServicoObra, ServicoObraReal, RDOServicoSubatividade, SubatividadeMestre, RegistroPonto, NotificacaoCliente
from auth import admin_required
from utils.tenant import get_tenant_admin_id
from utils import calcular_valor_hora_periodo
from utils.database_diagnostics import capture_db_errors
from views.helpers import safe_db_operation, _calcular_funcionarios_departamento, _calcular_custos_obra, get_admin_id_robusta, get_admin_id_dinamico
from datetime import datetime, date, timedelta
import calendar
from sqlalchemy import func, desc, or_, and_, text, inspect
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

# Health check endpoint para EasyPanel
@main_bp.route('/health')
def health_check():
    try:
        # Verificar conexão com banco
        db.session.execute(text('SELECT 1'))
        return {'status': 'healthy', 'database': 'connected', 'veiculos_check': '/health/veiculos'}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500

# Health check específico para veículos
@main_bp.route('/health/veiculos')
def health_check_veiculos():
    """Health check detalhado do sistema de veículos para produção"""
    start_time = datetime.now()
    
    # Inicializar resultado e variáveis críticas ANTES dos try blocks
    resultado = {
        'timestamp': start_time.isoformat(),
        'status': 'unknown',
        'checks': {},
        'errors': [],
        'warnings': [],
        'duracao_ms': 0
    }
    
    # Inicializar tabelas_existentes como lista vazia para evitar NameError
    tabelas_existentes = []
    tabelas_essenciais = ['veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo']
    tabelas_obsoletas = ['alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo', 'manutencao_veiculo', 'alerta_veiculo']
    
    try:
        # 1. Verificar conexão com banco
        try:
            db.session.execute(text("SELECT 1"))
            resultado['checks']['database_connection'] = 'OK'
        except Exception as e:
            resultado['checks']['database_connection'] = 'FAIL'
            resultado['errors'].append(f"Conexão banco: {str(e)[:200]}")  # Limitar tamanho da mensagem
            
        # 2. Verificar tabelas essenciais
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tabelas_existentes = inspector.get_table_names()
            
            # Verificar tabelas essenciais
            for tabela in tabelas_essenciais:
                if tabela in tabelas_existentes:
                    resultado['checks'][f'tabela_{tabela}'] = 'OK'
                else:
                    resultado['checks'][f'tabela_{tabela}'] = 'MISSING'
                    resultado['errors'].append(f"Tabela essencial ausente: {tabela}")
            
            # Verificar se tabelas obsoletas foram removidas
            for tabela in tabelas_obsoletas:
                if tabela in tabelas_existentes:
                    resultado['checks'][f'obsoleta_{tabela}'] = 'PRESENT'
                    resultado['warnings'].append(f"Tabela obsoleta ainda presente: {tabela}")
                else:
                    resultado['checks'][f'obsoleta_{tabela}'] = 'REMOVED'
                    
        except Exception as e:
            resultado['errors'].append(f"Erro ao verificar tabelas: {str(e)[:200]}")
            
        # 3. Verificar contagem de dados usando SQL RAW (mais robusto)
        try:
            # Contar veículos usando SQL raw
            if 'veiculo' in tabelas_existentes:
                try:
                    result = db.session.execute(text("SELECT COUNT(*) FROM veiculo"))
                    count_veiculos = result.scalar()
                    resultado['checks']['count_veiculos'] = count_veiculos
                except Exception as e:
                    resultado['warnings'].append(f"Erro ao contar veículos: {str(e)[:100]}")
                    resultado['checks']['count_veiculos'] = 'ERROR'
                
            # Contar usos usando SQL raw
            if 'uso_veiculo' in tabelas_existentes:
                try:
                    result = db.session.execute(text("SELECT COUNT(*) FROM uso_veiculo"))
                    count_usos = result.scalar()
                    resultado['checks']['count_usos'] = count_usos
                except Exception as e:
                    resultado['warnings'].append(f"Erro ao contar usos: {str(e)[:100]}")
                    resultado['checks']['count_usos'] = 'ERROR'
                
            # Contar custos usando SQL raw
            if 'custo_veiculo' in tabelas_existentes:
                try:
                    result = db.session.execute(text("SELECT COUNT(*) FROM custo_veiculo"))
                    count_custos = result.scalar()
                    resultado['checks']['count_custos'] = count_custos
                except Exception as e:
                    resultado['warnings'].append(f"Erro ao contar custos: {str(e)[:100]}")
                    resultado['checks']['count_custos'] = 'ERROR'
                
        except Exception as e:
            resultado['errors'].append(f"Erro ao contar dados: {str(e)[:200]}")
            
        # 4. Teste de tenant isolation usando SQL raw
        try:
            tenant_admin_id = get_tenant_admin_id()
            if tenant_admin_id:
                resultado['checks']['tenant_admin_id'] = str(tenant_admin_id)  # Convert to string para JSON
                
                # Testar query específica de tenant usando SQL raw
                if 'veiculo' in tabelas_existentes:
                    try:
                        result = db.session.execute(text("SELECT COUNT(*) FROM veiculo WHERE admin_id = :admin_id"), 
                                                  {"admin_id": tenant_admin_id})
                        veiculos_tenant = result.scalar()
                        resultado['checks']['veiculos_tenant'] = veiculos_tenant
                    except Exception as e:
                        resultado['warnings'].append(f"Erro no count tenant: {str(e)[:100]}")
            else:
                resultado['warnings'].append("Tenant admin_id não detectado")
                
        except Exception as e:
            resultado['warnings'].append(f"Erro no teste de tenant: {str(e)[:200]}")
            
        # 5. Determinar status final
        if resultado['errors']:
            resultado['status'] = 'error'
            status_code = 500
        elif resultado['warnings']:
            resultado['status'] = 'warning' 
            status_code = 200
        else:
            resultado['status'] = 'healthy'
            status_code = 200
            
    except Exception as e:
        # Capturar qualquer erro crítico não previsto
        resultado['status'] = 'error'
        resultado['errors'].append(f"Erro crítico não tratado: {str(e)[:200]}")
        status_code = 500
        
    finally:
        # SEMPRE calcular duração e retornar JSON válido
        try:
            end_time = datetime.now()
            duracao = (end_time - start_time).total_seconds() * 1000
            resultado['duracao_ms'] = round(duracao, 2)
        except:
            resultado['duracao_ms'] = 0
        
        # Garantir que sempre retorna JSON válido
        try:
            # Verificar se resultado pode ser serializado para JSON
            import json
            json.dumps(resultado)
            return resultado, status_code
        except Exception as json_error:
            # Em caso de erro de serialização, retornar estrutura mínima válida
            fallback_result = {
                'timestamp': start_time.isoformat(),
                'status': 'error',
                'errors': [f'Erro de serialização JSON: {str(json_error)[:100]}'],
                'checks': {},
                'warnings': [],
                'duracao_ms': 0
            }
            return fallback_result, 500

# ===== DASHBOARD PRINCIPAL =====
@main_bp.route('/dashboard')
@circuit_breaker(
    name="database_heavy_query",
    failure_threshold=2,
    recovery_timeout=60,
    expected_exception=(TimeoutError, Exception),
    fallback=lambda *args, **kwargs: {"error": "Dashboard temporariamente indisponível"}
)
def dashboard():
    # DEFINIR VARIÁVEIS DE DATA NO INÍCIO (SEMPRE) - date e datetime já importados no topo
    data_inicio_param = request.args.get('data_inicio')
    data_fim_param = request.args.get('data_fim')
    
    if data_inicio_param:
        data_inicio = datetime.strptime(data_inicio_param, '%Y-%m-%d').date()
    else:
        # Período será determinado depois que admin_id for identificado
        data_inicio = date(2024, 7, 1)  # Fallback temporário
        
    if data_fim_param:
        data_fim = datetime.strptime(data_fim_param, '%Y-%m-%d').date()
    else:
        data_fim = date(2024, 7, 31)  # Fallback temporário
    
    # REDIRECIONAMENTO BASEADO NO TIPO DE USUÁRIO
    if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
        # FUNCIONÁRIO - SEMPRE vai para dashboard específico (SEGURANÇA CRÍTICA)
        if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            logger.debug(f"DEBUG DASHBOARD: Funcionário {current_user.email} BLOQUEADO do dashboard admin - redirecionado")
            return redirect(url_for('main.funcionario_rdo_consolidado'))
            
        # SUPER ADMIN - vai para dashboard específico
        elif current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            return redirect(url_for('main.super_admin_dashboard'))
    
    # Sistema robusto de detecção de admin_id para produção (MESMA LÓGICA DA PÁGINA FUNCIONÁRIOS)
    try:
        logger.debug("DEBUG: Iniciando cálculos do dashboard...")
        # Determinar admin_id - usar mesma lógica que funciona na página funcionários
        admin_id = None  # Vamos detectar dinamicamente
        
        # DIAGNÓSTICO COMPLETO PARA PRODUÇÃO
        # Determinar admin_id para produção
        
        if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
            if current_user.tipo_usuario == TipoUsuario.ADMIN:
                admin_id = current_user.id
                logger.debug(f"[OK] DEBUG DASHBOARD PROD: Admin direto - admin_id={admin_id}")
            elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                admin_id = current_user.admin_id
                logger.debug(f"[OK] DEBUG DASHBOARD PROD: Via admin_id do usuário - admin_id={admin_id}")
            else:
                # Buscar pelo email na tabela usuarios
                try:
                    usuario_db = Usuario.query.filter_by(email=current_user.email).first()
                    if usuario_db and usuario_db.admin_id:
                        admin_id = usuario_db.admin_id
                        logger.debug(f"[OK] DEBUG DASHBOARD PROD: Via busca na tabela usuarios - admin_id={admin_id}")
                    else:
                        logger.warning(f"[WARN] DASHBOARD PROD: Usuário não encontrado na tabela usuarios ou sem admin_id")
                except Exception as e:
                    logger.error(f"[ERROR] DEBUG DASHBOARD PROD: Erro ao buscar na tabela usuarios: {e}")
        
        # Se ainda não encontrou admin_id, detectar automaticamente
        if admin_id is None:
            try:
                # Buscar admin_id com mais funcionários ativos (desenvolvimento e produção)
                admin_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC")).fetchall()
                logger.info(f"[STATS] DADOS DISPONÍVEIS POR ADMIN_ID: {[(row[0], row[1]) for row in admin_counts]}")
                
                if admin_counts and len(admin_counts) > 0:
                    admin_id = admin_counts[0][0]
                    logger.debug(f"[SYNC] DETECÇÃO AUTOMÁTICA: Usando admin_id={admin_id} (tem {admin_counts[0][1]} funcionários)")
                else:
                    # Buscar qualquer admin_id existente na tabela usuarios
                    try:
                        primeiro_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
                        if primeiro_admin:
                            admin_id = primeiro_admin.id
                            logger.debug(f"[DEBUG] ADMIN ENCONTRADO NA TABELA USUARIOS: admin_id={admin_id}")
                        else:
                            admin_id = 1  # Fallback absoluto
                            logger.debug(f"🆘 FALLBACK FINAL: admin_id={admin_id}")
                    except Exception as e2:
                        logger.error(f"[ERROR] Erro ao buscar admin na tabela usuarios: {e2}")
                        admin_id = 1  # Fallback absoluto
            except Exception as e:
                logger.error(f"[ERROR] Erro ao detectar admin_id automaticamente: {e}")
                admin_id = 1  # Fallback absoluto
        
        # [OK] CORREÇÃO: Determinar período com dados APÓS admin_id estar definido
        if not data_inicio_param:
            try:
                # Buscar último registro de ponto DO ADMIN específico (multi-tenant seguro)
                ultimo_registro = db.session.execute(
                    text("SELECT MAX(rp.data) FROM registro_ponto rp JOIN funcionario f ON rp.funcionario_id = f.id WHERE f.admin_id = :admin_id"),
                    {"admin_id": admin_id}
                ).scalar()
                
                if ultimo_registro:
                    # Usar o mês do último registro
                    data_inicio = date(ultimo_registro.year, ultimo_registro.month, 1)
                    logger.info(f"[OK] PERÍODO DINÂMICO (TENANT {admin_id}): {data_inicio} (último registro: {ultimo_registro})")
                else:
                    # Fallback para período conhecido com dados
                    data_inicio = date(2024, 7, 1)
                    logger.info(f"[OK] PERÍODO FALLBACK: Julho/2024 (sem registros para admin_id={admin_id})")
            except Exception as e:
                logger.error(f"[WARN] Erro ao buscar período dinâmico: {e}")
                data_inicio = date(2024, 7, 1)
                
        if not data_fim_param:
            ultimo_dia = calendar.monthrange(data_inicio.year, data_inicio.month)[1]
            data_fim = date(data_inicio.year, data_inicio.month, ultimo_dia)
            logger.info(f"[OK] PERÍODO FIM: {data_fim}")
        
        # Estatísticas básicas
            logger.debug("DEBUG: Buscando funcionários...")
        total_funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).count()
        logger.debug(f"DEBUG: {total_funcionarios} funcionários encontrados")
        
        logger.debug("DEBUG: Buscando obras...")
        total_obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).count()
        logger.debug(f"DEBUG: {total_obras} obras ativas encontradas")
        
        # [OK] CORREÇÃO 4: Calcular veículos ANTES dos custos
        logger.debug("DEBUG: Buscando veículos...")
        try:
            from models import Veiculo
            total_veiculos = Veiculo.query.filter_by(
                admin_id=admin_id, 
                ativo=True
            ).count()
            logger.debug(f"DEBUG: {total_veiculos} veículos ativos para admin_id={admin_id}")
        except Exception as e:
            logger.error(f"Erro ao contar veículos: {e}")
            total_veiculos = 0
        
        # ========== MÉTRICAS DE PROPOSTAS DINÂMICAS ==========
        from models import Proposta, PropostaTemplate, PropostaHistorico
        # datetime já importado no topo do arquivo
        
        try:
            # 1. PROPOSTAS POR STATUS ([OK] CORREÇÃO 6: Adicionado filtro de período)
            logger.debug("DEBUG: Calculando métricas de propostas...")
            from datetime import timedelta  # Import necessário para cálculos de validade
            propostas_aprovadas = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.status == 'aprovada',
                Proposta.data_proposta >= data_inicio,
                Proposta.data_proposta <= data_fim
            ).count()
            propostas_enviadas = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.status == 'enviada',
                Proposta.data_proposta >= data_inicio,
                Proposta.data_proposta <= data_fim
            ).count()
            propostas_rascunho = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.status == 'rascunho',
                Proposta.data_proposta >= data_inicio,
                Proposta.data_proposta <= data_fim
            ).count()
            propostas_rejeitadas = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.status == 'rejeitada',
                Proposta.data_proposta >= data_inicio,
                Proposta.data_proposta <= data_fim
            ).count()
            
            # Expiradas: propostas enviadas com data_proposta + validade_dias < hoje
            hoje = date.today()
            propostas_expiradas = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.status == 'enviada',
                Proposta.validade_dias.isnot(None)
            ).all()
            propostas_expiradas = len([p for p in propostas_expiradas if p.data_proposta and (p.data_proposta + timedelta(days=p.validade_dias or 7)) < hoje])
            
            # [OK] CORREÇÃO 6 COMPLETA: Total de propostas também com filtro de período
            total_propostas = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.data_proposta >= data_inicio,
                Proposta.data_proposta <= data_fim
            ).count()
            logger.debug(f"DEBUG: Propostas - Total: {total_propostas}, Aprovadas: {propostas_aprovadas}, Enviadas: {propostas_enviadas}")
            
            # 2. PERFORMANCE COMERCIAL
            # Taxa de conversão: (aprovadas / total enviadas+aprovadas) * 100
            total_enviadas_ou_aprovadas = propostas_enviadas + propostas_aprovadas + propostas_rejeitadas
            taxa_conversao = round((propostas_aprovadas / total_enviadas_ou_aprovadas * 100), 1) if total_enviadas_ou_aprovadas > 0 else 0
            
            # Valor médio das propostas aprovadas ([OK] CORREÇÃO 7: Filtrar apenas propostas com valor válido)
            from sqlalchemy import func as sql_func
            valor_medio_result = db.session.query(sql_func.avg(Proposta.valor_total)).filter(
                Proposta.admin_id == admin_id,
                Proposta.status == 'aprovada',
                Proposta.valor_total.isnot(None),
                Proposta.valor_total > 0,
                Proposta.data_proposta >= data_inicio,
                Proposta.data_proposta <= data_fim
            ).scalar()
            valor_medio = float(valor_medio_result or 0)
            
            # Tempo de resposta médio (diferença entre criado_em e quando foi aprovada/rejeitada)
            # Usar PropostaHistorico para calcular tempo até aprovação
            tempo_resposta_medio = 2.5  # Placeholder - precisa de histórico detalhado
            
            # Propostas por mês (média dos últimos 6 meses)
            seis_meses_atras = hoje - timedelta(days=180)
            propostas_ultimos_6_meses = Proposta.query.filter(
                Proposta.admin_id == admin_id,
                Proposta.criado_em >= seis_meses_atras
            ).count()
            propostas_por_mes = round(propostas_ultimos_6_meses / 6, 1) if propostas_ultimos_6_meses > 0 else 0
            
            # 3. TEMPLATES MAIS UTILIZADOS
            templates_uso = db.session.query(
                PropostaTemplate.nome,
                PropostaTemplate.uso_contador
            ).filter_by(
                admin_id=admin_id
            ).order_by(PropostaTemplate.uso_contador.desc()).limit(3).all()
            
            templates_populares = [{'nome': t[0], 'uso': t[1]} for t in templates_uso] if templates_uso else []
            outros_templates = PropostaTemplate.query.filter_by(admin_id=admin_id).count() - len(templates_populares)
            
            # 4. PORTAL DO CLIENTE (placeholder - precisa de rastreamento específico)
            acessos_unicos = 0  # Precisa de tabela de tracking
            tempo_medio_portal = "0h 0m"
            feedbacks_positivos = 0
            downloads_pdf = 0
            
            logger.debug(f"DEBUG: Taxa Conversão: {taxa_conversao}%, Valor Médio: R$ {valor_medio:.2f}")
            
        except Exception as e:
            logger.error(f"ERRO ao calcular métricas de propostas: {e}")
            # Valores padrão em caso de erro
            propostas_aprovadas = 0
            propostas_enviadas = 0
            propostas_rascunho = 0
            propostas_rejeitadas = 0
            propostas_expiradas = 0
            taxa_conversao = 0
            valor_medio = 0
            tempo_resposta_medio = 0
            propostas_por_mes = 0
            templates_populares = []
            outros_templates = 0
            acessos_unicos = 0
            tempo_medio_portal = "0h 0m"
            feedbacks_positivos = 0
            downloads_pdf = 0
        # ====================================================
        
        # Funcionários recentes
            logger.debug("DEBUG: Buscando funcionários recentes...")
        funcionarios_recentes = Funcionario.query.filter_by(
            admin_id=admin_id, ativo=True
        ).order_by(Funcionario.created_at.desc()).limit(5).all()
        logger.debug(f"DEBUG: {len(funcionarios_recentes)} funcionários recentes")
        
        # Obras ativas com progresso baseado em RDOs
        logger.debug("DEBUG: Buscando obras ativas...")
        obras_ativas = Obra.query.filter_by(
            admin_id=admin_id
        ).filter(
            Obra.status.in_(['ATIVO', 'andamento', 'Em andamento', 'ativa', 'planejamento'])
        ).order_by(Obra.created_at.desc()).limit(5).all()
        logger.debug(f"DEBUG: {len(obras_ativas)} obras ativas encontradas - Status: {[o.status for o in obras_ativas]}")
        
        # Calcular progresso de cada obra baseado no RDO mais recente
        for obra in obras_ativas:
            try:
                # Buscar o RDO mais recente da obra
                rdo_mais_recente = RDO.query.filter_by(
                    obra_id=obra.id
                ).order_by(RDO.data_relatorio.desc()).first()
                
                if rdo_mais_recente and rdo_mais_recente.servico_subatividades:
                    # FÓRMULA SIMPLES: média das subatividades
                    total_percentual = sum(
                        sub.percentual_conclusao for sub in rdo_mais_recente.servico_subatividades
                    )
                    total_sub = len(rdo_mais_recente.servico_subatividades)
                    progresso = round(total_percentual / total_sub, 1) if total_sub > 0 else 0
                    obra.progresso_atual = min(progresso, 100)  # Max 100%
                    logger.debug(f"[TARGET] DASHBOARD PROGRESSO: {total_percentual}÷{total_sub} = {progresso}%")
                    obra.data_ultimo_rdo = rdo_mais_recente.data_relatorio
                    obra.total_subatividades = len(rdo_mais_recente.servico_subatividades)
                else:
                    obra.progresso_atual = 0
                    obra.data_ultimo_rdo = None
                    obra.total_subatividades = 0
                    
            except Exception as e:
                logger.error(f"Erro ao calcular progresso da obra {obra.id}: {e}")
                obra.progresso_atual = 0
                obra.data_ultimo_rdo = None
                obra.total_subatividades = 0
    except Exception as e:
        # Log do erro para debug
        logger.error(f"ERRO NO DASHBOARD: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # [OK] CORREÇÃO 3: Só inicializar variáveis se não existirem (não resetar valores já calculados)
        if 'total_funcionarios' not in locals():
            total_funcionarios = 0
        if 'total_obras' not in locals():
            total_obras = 0
        if 'funcionarios_recentes' not in locals():
            funcionarios_recentes = []
        if 'obras_ativas' not in locals():
            obras_ativas = []
    
    # CÁLCULOS REAIS - Usar mesma lógica da página funcionários
    try:
        # Imports necessários (date e datetime já importados no topo)
        from models import RegistroPonto, RegistroAlimentacao
        
        # Garantir que admin_id está definido - usar valor do usuário atual
        if 'admin_id' not in locals() or admin_id is None:
            # Usar sistema automático de detecção
            if current_user.is_authenticated:
                if current_user.tipo_usuario == TipoUsuario.ADMIN:
                    admin_id = current_user.id
                else:
                    admin_id = current_user.admin_id or current_user.id
            else:
                # Fallback: detectar automaticamente baseado em funcionários ativos
                funcionarios_admin = db.session.execute(
                    text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
                ).fetchone()
                admin_id = funcionarios_admin[0] if funcionarios_admin else 1
            
                logger.debug(f"[OK] DEBUG DASHBOARD KPIs: Usando admin_id={admin_id} para cálculos")
                logger.debug(f"[DATE] PERÍODO SELECIONADO: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
                logger.info(f"[STATS] PERÍODO EM DIAS: {(data_fim - data_inicio).days + 1} dias")
        
        # Verificar estrutura completa do banco para diagnóstico
        try:
            # Diagnóstico completo do banco de dados
            logger.debug(f"[DEBUG] DIAGNÓSTICO COMPLETO DO BANCO DE DADOS:")
            
            # Total de funcionários por admin_id
            funcionarios_por_admin = db.session.execute(
                text("SELECT admin_id, COUNT(*) as total, COUNT(CASE WHEN ativo = true THEN 1 END) as ativos FROM funcionario GROUP BY admin_id ORDER BY admin_id")
            ).fetchall()
            logger.info(f" [STATS] FUNCIONÁRIOS POR ADMIN: {[(row[0], row[1], row[2]) for row in funcionarios_por_admin]}")
            
            # Total de obras por admin_id
            obras_por_admin = db.session.execute(
                text("SELECT admin_id, COUNT(*) as total FROM obra GROUP BY admin_id ORDER BY admin_id")
            ).fetchall()
            logger.debug(f" [BUILD] OBRAS POR ADMIN: {[(row[0], row[1]) for row in obras_por_admin]}")
            
            # Verificar estrutura da tabela registro_ponto primeiro
            try:
                colunas_ponto = db.session.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'registro_ponto' ORDER BY ordinal_position")
                ).fetchall()
                colunas_str = [col[0] for col in colunas_ponto]
                logger.debug(f" [DEBUG] COLUNAS REGISTRO_PONTO: {colunas_str}")
                
                # Usar coluna correta baseada na estrutura real
                coluna_data = 'data' if 'data' in colunas_str else 'data_registro'
                registros_ponto = db.session.execute(
                    text(f"SELECT COUNT(*) FROM registro_ponto WHERE {coluna_data} >= :data_inicio AND {coluna_data} <= :data_fim"),
                    {"data_inicio": data_inicio, "data_fim": data_fim}
                ).fetchone()
                logger.debug(f" [TIME] REGISTROS DE PONTO ({data_inicio.strftime('%b/%Y')}): {registros_ponto[0] if registros_ponto else 0}")
            except Exception as e:
                logger.error(f" [ERROR] ERRO registros ponto: {e}")
            
            # Total de custos de veículos - verificar se tabela existe
            try:
                tabelas_existentes = db.session.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                ).fetchall()
                tabelas_str = [t[0] for t in tabelas_existentes]
                
                if 'custo_veiculo' in tabelas_str:
                    custos_veiculo = db.session.execute(
                        text("SELECT COUNT(*), COALESCE(SUM(valor), 0) FROM custo_veiculo WHERE data_custo >= :data_inicio AND data_custo <= :data_fim"),
                        {"data_inicio": data_inicio, "data_fim": data_fim}
                    ).fetchone()
                    logger.debug(f" [CAR] CUSTOS VEÍCULOS ({data_inicio.strftime('%b/%Y')}): {custos_veiculo[0] if custos_veiculo else 0} registros, R$ {custos_veiculo[1] if custos_veiculo else 0}")
                else:
                    logger.debug(f" [CAR] TABELA custo_veiculo NÃO EXISTE")
            except Exception as e:
                logger.error(f" [ERROR] ERRO custos veículo: {e}")
            
            # Total de alimentação - verificar se tabela existe
            try:
                if 'registro_alimentacao' in tabelas_str:
                    alimentacao = db.session.execute(
                        text("SELECT COUNT(*), COALESCE(SUM(valor), 0) FROM registro_alimentacao WHERE data >= :data_inicio AND data <= :data_fim"),
                        {"data_inicio": data_inicio, "data_fim": data_fim}
                    ).fetchone()
                    logger.debug(f" [FOOD] ALIMENTAÇÃO ({data_inicio.strftime('%b/%Y')}): {alimentacao[0] if alimentacao else 0} registros, R$ {alimentacao[1] if alimentacao else 0}")
                else:
                    logger.debug(f" [FOOD] TABELA registro_alimentacao NÃO EXISTE")
            except Exception as e:
                logger.error(f" [ERROR] ERRO alimentação: {e}")
            
        except Exception as e:
            logger.error(f"[ERROR] ERRO no diagnóstico do banco: {e}")
        
        # Buscar todos os funcionários ativos para o admin_id detectado
        funcionarios_dashboard = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        logger.debug(f"[OK] DEBUG DASHBOARD KPIs: Encontrados {len(funcionarios_dashboard)} funcionários para admin_id={admin_id}")
        
        # Se não encontrou funcionários, buscar o admin_id com mais dados
        if len(funcionarios_dashboard) == 0:
            logger.warning(f"[WARN] AVISO PRODUÇÃO: Nenhum funcionário encontrado para admin_id={admin_id}")
            try:
                todos_admins = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC")).fetchall()
                logger.info(f"[STATS] TODOS OS ADMINS DISPONÍVEIS: {[(row[0], row[1]) for row in todos_admins]}")
                if todos_admins and len(todos_admins) > 0:
                    admin_correto = todos_admins[0][0]
                    logger.debug(f"[SYNC] CORREÇÃO AUTOMÁTICA: Mudando de admin_id={admin_id} para admin_id={admin_correto} (tem {todos_admins[0][1]} funcionários)")
                    admin_id = admin_correto
                    funcionarios_dashboard = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
                    logger.info(f"[OK] APÓS CORREÇÃO: {len(funcionarios_dashboard)} funcionários encontrados")
            except Exception as e:
                logger.error(f"[ERROR] ERRO ao detectar admin_id correto: {e}")
        
        # Calcular KPIs reais com proteção de transação
        total_custo_real = 0
        total_horas_real = 0
        total_extras_real = 0
        total_faltas_real = 0
        custo_transporte_real = 0
        
        try:
            # Reiniciar conexão para evitar transação abortada
            db.session.rollback()
            
            # Refazer busca de funcionários
            funcionarios_dashboard = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
            logger.info(f"[OK] APÓS ROLLBACK: {len(funcionarios_dashboard)} funcionários encontrados")
            
            for func in funcionarios_dashboard:
                try:
                    # Buscar registros de ponto com proteção
                    registros = RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id == func.id,
                        RegistroPonto.data >= data_inicio,
                        RegistroPonto.data <= data_fim
                    ).all()
                    
                    # Calcular valores por funcionário
                    horas_func = sum(r.horas_trabalhadas or 0 for r in registros)
                    extras_func = sum(r.horas_extras or 0 for r in registros)
                    faltas_func = len([r for r in registros if r.tipo_registro == 'falta'])
                    
                    # [OK] CORREÇÃO CRÍTICA: Sem registros = Sem custo (não usar fallback)
                    # Fallback removido - se não há registros de ponto, custo = R$ 0.00
                    # Isso evita estimativas incorretas quando período está vazio
                    if len(registros) == 0:
                        custo_func = 0
                        horas_func = 0
                        extras_func = 0
                    else:
                        # Cálculo normal com registros de ponto
                        valor_hora = calcular_valor_hora_periodo(func, data_inicio, data_fim) if func.salario else 0
                        custo_func = (horas_func + extras_func * 1.5) * valor_hora
                    
                    # Acumular totais
                    total_custo_real += custo_func
                    total_horas_real += horas_func
                    total_extras_real += extras_func
                    total_faltas_real += faltas_func
                    
                except Exception as func_error:
                    logger.error(f"[ERROR] ERRO ao processar funcionário {func.nome}: {func_error}")
                    continue
                    
        except Exception as kpi_error:
            logger.error(f"[ERROR] ERRO GERAL nos cálculos KPI: {kpi_error}")
            db.session.rollback()
        
        # Buscar custos de alimentação TOTAL para o período (não por funcionário para evitar duplicação)
        custo_alimentacao_real = 0
        try:
            # 1. Tabela NOVA: alimentacao_lancamento (tem admin_id direto)
            from models import AlimentacaoLancamento
            lancamentos_novos = AlimentacaoLancamento.query.filter(
                AlimentacaoLancamento.admin_id == admin_id,
                AlimentacaoLancamento.data >= data_inicio,
                AlimentacaoLancamento.data <= data_fim
            ).all()
            total_lancamentos_novos = sum(float(l.valor_total or 0) for l in lancamentos_novos)
            custo_alimentacao_real += total_lancamentos_novos
            
            # 2. Tabela ANTIGA: registro_alimentacao (sem admin_id direto, precisa JOIN)
            alimentacao_registros = db.session.query(RegistroAlimentacao).join(
                Funcionario, RegistroAlimentacao.funcionario_id == Funcionario.id
            ).filter(
                Funcionario.admin_id == admin_id,
                RegistroAlimentacao.data >= data_inicio,
                RegistroAlimentacao.data <= data_fim
            ).all()
            total_registros_antigos = sum(a.valor or 0 for a in alimentacao_registros)
            custo_alimentacao_real += total_registros_antigos
            
            # 3. Também buscar em outro_custo
            from models import OutroCusto
            outros_alimentacao = OutroCusto.query.filter(
                OutroCusto.admin_id == admin_id,
                OutroCusto.data >= data_inicio,
                OutroCusto.data <= data_fim,
                OutroCusto.kpi_associado == 'custo_alimentacao'
            ).all()
            total_outros = sum(o.valor or 0 for o in outros_alimentacao)
            custo_alimentacao_real += total_outros
            
            logger.debug(f"DEBUG ALIMENTAÇÃO DASHBOARD: Lançamentos Novos ({len(lancamentos_novos)})=R${total_lancamentos_novos:.2f}, Registros Antigos ({len(alimentacao_registros)})=R${total_registros_antigos:.2f}, Outros ({len(outros_alimentacao)})=R${total_outros:.2f}, Total=R${custo_alimentacao_real:.2f}")
        except Exception as e:
            logger.error(f"Erro cálculo alimentação: {e}")
            import traceback
            traceback.print_exc()
            custo_alimentacao_real = 0
        
        # Debug dos valores calculados
            logger.debug(f"DEBUG DASHBOARD: {len(funcionarios_dashboard)} funcionários")
            logger.debug(f"DEBUG DASHBOARD: Custo total calculado: R$ {total_custo_real:.2f}")
            logger.debug(f"DEBUG DASHBOARD: Horas totais: {total_horas_real}")
            logger.debug(f"DEBUG DASHBOARD: Extras totais: {total_extras_real}")
        
        # Calcular KPIs específicos corretamente
        # 1. Custos de Transporte (veículos) - usar safe_db_operation para evitar transaction abort
        def calcular_custos_veiculo():
            from models import VehicleExpense, CustoObra
            
            # 1.1. Tabela VehicleExpense (frota)
            custos_veiculo = VehicleExpense.query.filter(
                VehicleExpense.admin_id == admin_id,
                VehicleExpense.data_custo >= data_inicio,
                VehicleExpense.data_custo <= data_fim
            ).all()
            total_vehicle_expense = sum(c.valor or 0 for c in custos_veiculo)
            
            # 1.2. Tabela CustoObra (tipo='transporte')
            custos_obra_transporte = CustoObra.query.filter(
                CustoObra.admin_id == admin_id,
                CustoObra.data >= data_inicio,
                CustoObra.data <= data_fim,
                CustoObra.tipo == 'transporte'
            ).all()
            total_custo_obra = sum(float(c.valor or 0) for c in custos_obra_transporte)
            
            total = total_vehicle_expense + total_custo_obra
            logger.debug(f" DEBUG TRANSPORTE: VehicleExpense ({len(custos_veiculo)})=R${total_vehicle_expense:.2f}, CustoObra ({len(custos_obra_transporte)})=R${total_custo_obra:.2f}, Total=R${total:.2f}")
            return total
        
        custo_transporte_real = safe_db_operation(calcular_custos_veiculo, 0)
        logger.debug(f"DEBUG Custos Transporte FINAL: R$ {custo_transporte_real:.2f}")
        
        # 2. Faltas Justificadas (quantidade e valor em R$) - usar safe_db_operation
        def calcular_faltas_justificadas():
            # Buscar todas as faltas justificadas no período (RegistroPonto tem admin_id)
            faltas_justificadas = RegistroPonto.query.filter(
                RegistroPonto.admin_id == admin_id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.tipo_registro == 'falta_justificada'
            ).all()
            
            quantidade = len(faltas_justificadas)
            custo = 0
            
            for falta in faltas_justificadas:
                funcionario = Funcionario.query.get(falta.funcionario_id)
                if funcionario and funcionario.salario:
                    # Calcular dias úteis reais do mês
                    mes = falta.data.month
                    ano = falta.data.year
                    dias_uteis = sum(1 for dia in range(1, calendar.monthrange(ano, mes)[1] + 1) 
                                    if date(ano, mes, dia).weekday() < 5)
                    valor_dia = funcionario.salario / dias_uteis
                    custo += valor_dia
            
            return quantidade, custo
        
        resultado_faltas = safe_db_operation(calcular_faltas_justificadas, (0, 0))
        quantidade_faltas_justificadas, custo_faltas_justificadas = resultado_faltas
        logger.debug(f"DEBUG Faltas Justificadas: {quantidade_faltas_justificadas} faltas, R$ {custo_faltas_justificadas:.2f}")
        
        # 3. Outros Custos (não transporte nem alimentação) - usar safe_db_operation
        def calcular_outros_custos():
            from models import OutroCusto, CustoObra
            
            # 3.1. Tabela OutroCusto (genérica)
            outros_custos = OutroCusto.query.filter(
                OutroCusto.admin_id == admin_id,
                OutroCusto.data >= data_inicio,
                OutroCusto.data <= data_fim,
                ~OutroCusto.tipo.in_(['transporte', 'alimentacao'])
            ).all()
            total_outro_custo = sum(o.valor or 0 for o in outros_custos)
            
            # 3.2. Tabela CustoObra (tipo='outros' ou 'servico' ou 'material')
            custos_obra_outros = CustoObra.query.filter(
                CustoObra.admin_id == admin_id,
                CustoObra.data >= data_inicio,
                CustoObra.data <= data_fim,
                CustoObra.tipo.in_(['outros', 'servico', 'material'])
            ).all()
            total_custo_obra = sum(float(c.valor or 0) for c in custos_obra_outros)
            
            total = total_outro_custo + total_custo_obra
            logger.debug(f" DEBUG OUTROS: OutroCusto ({len(outros_custos)})=R${total_outro_custo:.2f}, CustoObra ({len(custos_obra_outros)})=R${total_custo_obra:.2f}, Total=R${total:.2f}")
            return total
        
        custo_outros_real = safe_db_operation(calcular_outros_custos, 0)
        logger.debug(f"DEBUG Custos Outros FINAL: R$ {custo_outros_real:.2f}")
        
        # 4. Funcionários por Departamento - com proteção de transação
        funcionarios_por_departamento = safe_db_operation(
            lambda: _calcular_funcionarios_departamento(admin_id), 
            {}
        )
        logger.debug(f"DEBUG FINAL - Funcionários por dept: {funcionarios_por_departamento}")
        
        # 5. Custos por Obra - com proteção de transação
        custos_por_obra = safe_db_operation(
            lambda: _calcular_custos_obra(admin_id, data_inicio, data_fim), 
            {}
        )
        logger.debug(f"DEBUG FINAL - Custos por obra: {custos_por_obra}")
        
        # Dados calculados reais
        # Inicializar admin_id se não definido
        if 'admin_id' not in locals():
            admin_id = 10  # Admin padrão com mais dados
            
        # [OK] CORREÇÃO 4: Veículos já calculados no início (linha 535) - removido daqui
        # Converter todos para float antes de somar (corrige erro float + Decimal)
        custos_mes = float(total_custo_real) + float(custo_alimentacao_real) + float(custo_transporte_real) + float(custo_outros_real)
        custos_detalhados = {
            'alimentacao': custo_alimentacao_real,
            'transporte': custo_transporte_real,
            'mao_obra': total_custo_real,
            'outros': custo_outros_real,
            'faltas_justificadas': custo_faltas_justificadas,
            'faltas_justificadas_qtd': quantidade_faltas_justificadas,
            'total': custos_mes
        }
        
    except Exception as e:
        logger.error(f"ERRO CÁLCULO DASHBOARD: {str(e)}")
        # Em caso de erro, usar valores padrão
        total_veiculos = 0
        total_custo_real = 0
        custo_alimentacao_real = 0
        custo_transporte_real = 0
        custo_outros_real = 0
        total_horas_real = 0
        custos_mes = 0
        custos_detalhados = {
            'alimentacao': 0,
            'transporte': 0,
            'mao_obra': 0,
            'outros': 0,
            'faltas_justificadas': 0,
            'faltas_justificadas_qtd': 0,
            'total': 0
        }
        funcionarios_por_departamento = {}
        custos_por_obra = {}
    
    # Estatísticas dinâmicas calculadas
    funcionarios_ativos = total_funcionarios
    obras_ativas_count = len(obras_ativas)
    
    # 1. EFICIÊNCIA GERAL - Calcular baseado em horas trabalhadas vs esperadas
    eficiencia_geral = 0
    try:
        # Horas esperadas = funcionários ativos * dias úteis * 8h
        # datetime já importado no topo do arquivo (linha 9)
        dias_uteis_mes = 22  # Média de dias úteis
        horas_esperadas = funcionarios_ativos * dias_uteis_mes * 8
        
        if horas_esperadas > 0 and total_horas_real > 0:
            eficiencia_geral = round((total_horas_real / horas_esperadas) * 100, 1)
            # Limitar entre 0 e 100%
            eficiencia_geral = max(0, min(100, eficiencia_geral))
            logger.debug(f"DEBUG EFICIÊNCIA: {total_horas_real}h trabalhadas / {horas_esperadas}h esperadas = {eficiencia_geral}%")
    except Exception as e:
        logger.error(f"Erro ao calcular eficiência: {e}")
        eficiencia_geral = 0
    
    # 2. PRODUTIVIDADE OBRA - Calcular baseado no progresso médio das obras
    produtividade_obra = 0
    try:
        if len(obras_ativas) > 0:
            progressos = [getattr(obra, 'progresso_atual', 0) for obra in obras_ativas]
            produtividade_obra = round(sum(progressos) / len(progressos), 1)
            logger.debug(f"DEBUG PRODUTIVIDADE: Média de {produtividade_obra}% em {len(obras_ativas)} obras")
    except Exception as e:
        logger.error(f"Erro ao calcular produtividade: {e}")
        produtividade_obra = 0
    
    # 3. VEÍCULOS DISPONÍVEIS - Buscar do banco de dados
    veiculos_disponiveis = 0
    try:
        from models import Veiculo
        veiculos_disponiveis = Veiculo.query.filter_by(
            admin_id=admin_id, 
            ativo=True
        ).count()
        logger.debug(f"DEBUG VEÍCULOS: {veiculos_disponiveis} ativos para admin_id={admin_id}")
    except Exception as e:
        logger.error(f"Erro ao contar veículos disponíveis: {e}")
        veiculos_disponiveis = 0
    
    # 4. MARGEM DE LUCRO - Calcular baseado em valor de contratos vs custos
    margem_percentual = 0
    valor_contrato_total = 0
    try:
        # Buscar valor total de contratos das obras ativas (importar func explicitamente)
        from sqlalchemy import func as sql_func
        valor_contrato_total = db.session.query(
            sql_func.sum(Obra.valor_contrato)
        ).filter(
            Obra.admin_id == admin_id,
            Obra.status.in_(['ATIVO', 'andamento', 'Em andamento', 'ativa', 'planejamento'])
        ).scalar() or 0
        
        # Calcular margem percentual
        if valor_contrato_total > 0:
            margem_percentual = round(
                ((valor_contrato_total - custos_mes) / valor_contrato_total) * 100, 
                1
            )
            # Margem pode ser >100% (se custos < 0) ou negativa (se custos > contratos)
            logger.debug(f"DEBUG MARGEM: Contratos=R${valor_contrato_total:.2f}, Custos=R${custos_mes:.2f}, Margem={margem_percentual}%")
    except Exception as e:
        logger.error(f"Erro ao calcular margem: {e}")
        valor_contrato_total = 0
        margem_percentual = 0
    
    # Adicionar contagem correta de obras ativas com tratamento de erro
    obras_ativas_count = safe_db_operation(
        lambda: Obra.query.filter_by(admin_id=admin_id).filter(
            Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
        ).count(),
        default_value=0
    )
    
    # [OK] CORREÇÃO 5: Converter dicionários para listas com proteção
    if isinstance(funcionarios_por_departamento, dict) and funcionarios_por_departamento:
        funcionarios_dept = [{'nome': k, 'total': v} for k, v in funcionarios_por_departamento.items()]
    else:
        funcionarios_dept = []
        logger.warning("[WARN] funcionarios_por_departamento vazio ou inválido")
    
    if isinstance(custos_por_obra, dict) and custos_por_obra:
        custos_recentes = [{'nome': k, 'total_custo': v} for k, v in custos_por_obra.items()]
    else:
        custos_recentes = []
        logger.warning("[WARN] custos_por_obra vazio ou inválido")
    
    # Debug final
        logger.debug(f"DEBUG FINAL - Funcionários por dept: {funcionarios_dept}")
        logger.debug(f"DEBUG FINAL - Custos por obra: {custos_recentes}")
    
    # Buscar obras em andamento para a tabela com tratamento de erro
    obras_andamento = safe_db_operation(
        lambda: Obra.query.filter_by(admin_id=admin_id).filter(
            Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
        ).order_by(Obra.data_inicio.desc()).limit(5).all(),
        default_value=[]
    )
    
    return render_template('dashboard.html',
                         total_funcionarios=total_funcionarios,
                         total_obras=total_obras,
                         total_veiculos=total_veiculos,
                         funcionarios_recentes=funcionarios_recentes,
                         obras_ativas=obras_ativas,
                         custos_mes=custos_mes,
                         custos_detalhados=custos_detalhados,
                         custo_mao_obra=total_custo_real,
                         custo_alimentacao=custo_alimentacao_real,
                         custo_transporte=custo_transporte_real,
                         custo_outros=custo_outros_real,
                         total_horas=total_horas_real,
                         eficiencia_geral=eficiencia_geral,
                         produtividade_obra=produtividade_obra,
                         funcionarios_ativos=funcionarios_ativos,
                         obras_ativas_count=obras_ativas_count,
                         veiculos_disponiveis=veiculos_disponiveis,
                         margem_percentual=margem_percentual,
                         valor_contrato_total=valor_contrato_total,
                         funcionarios_por_departamento=funcionarios_por_departamento,
                         custos_por_obra=custos_por_obra,
                         funcionarios_dept=funcionarios_dept,
                         custos_recentes=custos_recentes,
                         obras_andamento=obras_andamento,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         # Métricas de Propostas
                         propostas_aprovadas=propostas_aprovadas,
                         propostas_enviadas=propostas_enviadas,
                         propostas_rascunho=propostas_rascunho,
                         propostas_rejeitadas=propostas_rejeitadas,
                         propostas_expiradas=propostas_expiradas,
                         taxa_conversao=taxa_conversao,
                         valor_medio=valor_medio,
                         tempo_resposta_medio=tempo_resposta_medio,
                         propostas_por_mes=propostas_por_mes,
                         templates_populares=templates_populares,
                         outros_templates=outros_templates,
                         acessos_unicos=acessos_unicos,
                         tempo_medio_portal=tempo_medio_portal,
                         feedbacks_positivos=feedbacks_positivos,
                         downloads_pdf=downloads_pdf)

# ===== USUÁRIOS DO SISTEMA =====

