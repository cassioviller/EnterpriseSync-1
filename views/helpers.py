from flask_login import current_user
from models import db, Usuario, TipoUsuario, Funcionario, Funcao, Departamento, Obra, Servico, ServicoObra, ServicoObraReal, RDOServicoSubatividade, SubatividadeMestre, RegistroPonto
from utils.tenant import get_tenant_admin_id
from utils import calcular_valor_hora_periodo
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, or_, and_, text
from sqlalchemy.orm import joinedload
import os
import json
import logging
import sys
import importlib.util

logger = logging.getLogger(__name__)

def verificar_modulo_detalhado(nome_modulo, descricao=""):
    """Verificar se um módulo existe e mostrar logs detalhados"""
    try:
        spec = importlib.util.find_spec(nome_modulo)
        if spec is None:
            logger.error(f"[ERROR] MÓDULO NÃO ENCONTRADO: {nome_modulo} ({descricao})")
            logger.debug(f" [LOC] Localização esperada: {nome_modulo.replace('.', '/')}.py")
            logger.debug(f" [DIR] Python path: {sys.path}")
            return False
        else:
            logger.info(f"[OK] MÓDULO ENCONTRADO: {nome_modulo} ({descricao})")
            logger.debug(f" [LOC] Localização: {spec.origin}")
            return True
    except Exception as e:
        logger.error(f"[ALERT] ERRO AO VERIFICAR MÓDULO {nome_modulo}: {e}")
        return False

# Verificar módulos específicos
logger.debug("[DEBUG] VERIFICAÇÃO DETALHADA DE MÓDULOS - INÍCIO")

modulos_verificar = [
    ('utils.idempotency', 'Utilitários de idempotência'),
    ('utils.circuit_breaker', 'Circuit breakers para resiliência'),
    ('utils.saga', 'Padrão SAGA para transações'),
    ('migrations', 'Sistema de migrações automáticas'),
    ('models', 'Modelos do banco de dados'),
    ('auth', 'Sistema de autenticação')
]

modulos_encontrados = []
modulos_faltando = []

for modulo, desc_mod in modulos_verificar:
    if verificar_modulo_detalhado(modulo, desc_mod):
        modulos_encontrados.append(modulo)
    else:
        modulos_faltando.append(modulo)

logger.info(f"[STATS] RESUMO: {len(modulos_encontrados)} encontrados, {len(modulos_faltando)} faltando")

if modulos_faltando:
    logger.debug(f"[ALERT] MÓDULOS FALTANDO: {', '.join(modulos_faltando)}")

try:
    from utils.circuit_breaker import circuit_breaker, pdf_generation_fallback, database_query_fallback
    from utils.saga import RDOSaga, FuncionarioSaga
    logger.info("[OK] Utilitários de resiliência importados com sucesso")
except ImportError as e:
    logger.warning(f"[WARN] MODULO UTILS FALTANDO: {e}")
    logger.info(" [INFO] Criando fallbacks para manter compatibilidade...")
    def idempotent(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def circuit_breaker(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    logger.info(" [OK] Fallbacks criados com sucesso")


def safe_db_operation(operation, default_value=None):
    """Executa operação no banco com tratamento seguro de transação"""
    try:
        return operation()
    except Exception as e:
        logger.error(f"Erro em operação de banco de dados: {e}")
        try:
            db.session.rollback()
        except Exception as rollback_error:
            logger.warning(f"Falha ao executar rollback: {rollback_error}")
        return default_value


def _calcular_funcionarios_departamento(admin_id):
    """Calcula funcionários por departamento com proteção de transação"""
    try:
        from models import Departamento
        funcionarios_por_departamento = {}
        
        departamentos = db.session.execute(text("""
            SELECT d.nome as nome, COALESCE(COUNT(f.id), 0) as total
            FROM departamento d 
            LEFT JOIN funcionario f ON f.departamento_id = d.id 
                AND f.ativo = true 
                AND f.admin_id = :admin_id
            GROUP BY d.nome 
            ORDER BY total DESC
        """), {'admin_id': admin_id}).fetchall()
        
        funcionarios_por_departamento = {
            dept[0]: dept[1] for dept in departamentos if dept[1] > 0
        }
        
        sem_dept = Funcionario.query.filter_by(
            admin_id=admin_id, 
            ativo=True, 
            departamento_id=None
        ).count()
        if sem_dept > 0:
            funcionarios_por_departamento['Sem Departamento'] = sem_dept
            
        return funcionarios_por_departamento
    except Exception as e:
        logger.error(f"Erro funcionários por departamento: {e}")
        db.session.rollback()
        return {}

def _calcular_custos_obra(admin_id, data_inicio, data_fim):
    """Calcula custos por obra com proteção de transação"""
    try:
        from models import VehicleExpense, RegistroPonto, RegistroAlimentacao
        custos_por_obra = {}
        
        obras_admin = Obra.query.filter_by(admin_id=admin_id).all()
        
        for obra in obras_admin:
            custo_total_obra = 0
            
            registros_obra = RegistroPonto.query.filter(
                RegistroPonto.obra_id == obra.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim
            ).options(joinedload(RegistroPonto.funcionario_ref)).all()
            
            for registro in registros_obra:
                funcionario = registro.funcionario_ref
                if funcionario and funcionario.salario:
                    valor_hora = calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
                    horas = (registro.horas_trabalhadas or 0) + (registro.horas_extras or 0) * 1.5
                    custo_total_obra += horas * valor_hora
            
            try:
                if hasattr(VehicleExpense, 'obra_id'):
                    veiculos_obra = VehicleExpense.query.filter(
                        VehicleExpense.obra_id == obra.id,
                        VehicleExpense.data_custo >= data_inicio,
                        VehicleExpense.data_custo <= data_fim
                    ).all()
                else:
                    veiculos_obra = []
                custo_total_obra += sum(v.valor or 0 for v in veiculos_obra)
            except Exception as e:
                logger.error(f"Erro ao calcular custos de veículos para obra {obra.nome} (ID: {obra.id}): {e}")
            
            if custo_total_obra > 0:
                custos_por_obra[obra.nome] = round(custo_total_obra, 2)
                
        return custos_por_obra
    except Exception as e:
        logger.error(f"Erro custos por obra: {e}")
        db.session.rollback()
        return {}


def get_admin_id_robusta(obra=None, current_user=None):
    """Sistema robusto de detecção de admin_id - PRIORIDADE TOTAL AO USUÁRIO LOGADO"""
    try:
        if current_user is None:
            from flask_login import current_user as flask_current_user
            current_user = flask_current_user
        
        if current_user and current_user.is_authenticated:
            from models import TipoUsuario
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                logger.debug(f"[LOCK] ADMIN LOGADO: admin_id={current_user.id}")
                return current_user.id
            
            elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                logger.debug(f"[LOCK] FUNCIONÁRIO LOGADO: admin_id={current_user.admin_id}")
                return current_user.admin_id
            
            elif hasattr(current_user, 'id') and current_user.id:
                logger.debug(f"[LOCK] USUÁRIO GENÉRICO LOGADO: admin_id={current_user.id}")
                return current_user.id
        
        if obra and hasattr(obra, 'admin_id') and obra.admin_id:
            logger.debug(f"[TARGET] Admin_ID da obra: {obra.admin_id}")
            return obra.admin_id
        
        logger.error("[ERROR] ERRO CRÍTICO: Nenhum usuário autenticado encontrado!")
        return None
        
    except Exception as e:
        logger.error(f"ERRO CRÍTICO get_admin_id_robusta: {e}")
        return 1


def get_admin_id_dinamico():
    """Função helper para detectar admin_id dinamicamente no sistema multi-tenant"""
    try:
        from sqlalchemy import text
        
        if current_user.is_authenticated:
            if current_user.tipo_usuario == TipoUsuario.ADMIN:
                return current_user.id
            elif current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
                obra_counts = db.session.execute(
                    text("SELECT admin_id, COUNT(*) as total FROM obra WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
                ).fetchone()
                if obra_counts and obra_counts[0]:
                    logger.info(f"[OK] SUPER_ADMIN: usando admin_id={obra_counts[0]} ({obra_counts[1]} obras)")
                    return obra_counts[0]
                func_counts = db.session.execute(
                    text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
                ).fetchone()
                if func_counts and func_counts[0]:
                    return func_counts[0]
                return current_user.id
            elif current_user.admin_id:
                return current_user.admin_id
            else:
                pass
        
        from sqlalchemy import text
        
        admin_funcionarios = db.session.execute(
            text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 3")
        ).fetchall()
        
        logger.debug(f"[DEBUG] ADMINS DISPONÍVEIS: {admin_funcionarios}")
        
        for admin_info in admin_funcionarios:
            admin_id, total = admin_info
            if total >= 1:
                logger.info(f"[OK] SELECIONADO: admin_id={admin_id} ({total} funcionários)")
                return admin_id
        
        admin_servicos = db.session.execute(
            text("SELECT admin_id, COUNT(*) as total FROM servico WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
        ).fetchone()
        
        if admin_servicos:
            logger.info(f"[OK] FALLBACK SERVIÇOS: admin_id={admin_servicos[0]} ({admin_servicos[1]} serviços)")
            return admin_servicos[0]
            
        primeiro_admin = db.session.execute(
            text("SELECT DISTINCT admin_id FROM funcionario ORDER BY admin_id LIMIT 1")
        ).fetchone()
        
        if primeiro_admin:
            logger.info(f"[OK] ÚLTIMO FALLBACK: admin_id={primeiro_admin[0]}")
            return primeiro_admin[0]
            
        logger.warning("[WARN] USANDO DEFAULT: admin_id=1")
        return 1
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO GET_ADMIN_ID_DINAMICO: {str(e)}")
        try:
            primeiro_admin = db.session.execute(text("SELECT MIN(admin_id) FROM funcionario")).fetchone()
            return primeiro_admin[0] if primeiro_admin and primeiro_admin[0] else 1
        except:
            return 1


def verificar_dados_producao(admin_id):
    """Verifica se admin_id tem dados suficientes para funcionar em produção"""
    try:
        from sqlalchemy import text
        
        funcionarios = db.session.execute(text(
            "SELECT COUNT(*) FROM funcionario WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        servicos = db.session.execute(text(
            "SELECT COUNT(*) FROM servico WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        subatividades = db.session.execute(text(
            "SELECT COUNT(*) FROM subatividade_mestre WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        obras = db.session.execute(text(
            "SELECT COUNT(*) FROM obra WHERE admin_id = :admin_id"
        ), {'admin_id': admin_id}).scalar()
        
        logger.info(f"[STATS] VERIFICAÇÃO PRODUÇÃO admin_id {admin_id}: {funcionarios} funcionários, {servicos} serviços, {subatividades} subatividades, {obras} obras")
        
        is_valid = funcionarios > 0 or servicos > 0 or obras > 0
        
        if not is_valid:
            logger.warning(f"[WARN] ADMIN_ID {admin_id} NÃO TEM DADOS SUFICIENTES")
        else:
            logger.info(f"[OK] ADMIN_ID {admin_id} VALIDADO PARA PRODUÇÃO")
            
        return is_valid
        
    except Exception as e:
        logger.error(f"ERRO verificação produção admin_id {admin_id}: {e}")
        return False
