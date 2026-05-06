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


def _calcular_funcionarios_funcao(admin_id):
    """Calcula funcionários ativos por função com headcount e custo mensal de folha."""
    try:
        rows = db.session.execute(text("""
            SELECT
                fu.nome                           AS nome,
                COUNT(f.id)                       AS total,
                COALESCE(SUM(f.salario), 0)       AS custo_mensal
            FROM funcao fu
            LEFT JOIN funcionario f
                   ON f.funcao_id = fu.id
                  AND f.ativo = true
                  AND f.admin_id = :admin_id
            WHERE fu.admin_id = :admin_id
            GROUP BY fu.nome
            ORDER BY total DESC
        """), {'admin_id': admin_id}).fetchall()

        result = [
            {
                'nome': row[0],
                'total': int(row[1]),
                'custo_mensal': float(row[2] or 0)
            }
            for row in rows if row[1] > 0
        ]

        sem_funcao = db.session.execute(text("""
            SELECT COUNT(*) AS total, COALESCE(SUM(salario), 0) AS custo
            FROM funcionario
            WHERE admin_id = :admin_id AND ativo = true AND funcao_id IS NULL
        """), {'admin_id': admin_id}).first()
        if sem_funcao and sem_funcao[0] > 0:
            result.append({
                'nome': 'Sem Função',
                'total': int(sem_funcao[0]),
                'custo_mensal': float(sem_funcao[1] or 0)
            })

        return result
    except Exception as e:
        logger.error(f"Erro funcionários por função: {e}")
        db.session.rollback()
        return []


def _calcular_funcionarios_departamento(admin_id):
    """Calcula funcionários ativos por departamento com headcount e custo mensal de folha."""
    try:
        rows = db.session.execute(text("""
            SELECT
                d.nome                            AS nome,
                COUNT(f.id)                       AS total,
                COALESCE(SUM(f.salario), 0)       AS custo_mensal
            FROM departamento d
            LEFT JOIN funcionario f
                   ON f.departamento_id = d.id
                  AND f.ativo = true
                  AND f.admin_id = :admin_id
            WHERE d.admin_id = :admin_id
            GROUP BY d.nome
            ORDER BY total DESC
        """), {'admin_id': admin_id}).fetchall()

        result = [
            {
                'nome': row[0],
                'total': int(row[1]),
                'custo_mensal': float(row[2] or 0)
            }
            for row in rows if row[1] > 0
        ]

        # Funcionários sem departamento
        sem_dept = db.session.execute(text("""
            SELECT COUNT(*) AS total, COALESCE(SUM(salario), 0) AS custo
            FROM funcionario
            WHERE admin_id = :admin_id AND ativo = true AND departamento_id IS NULL
        """), {'admin_id': admin_id}).first()
        if sem_dept and sem_dept[0] > 0:
            result.append({
                'nome': 'Sem Departamento',
                'total': int(sem_dept[0]),
                'custo_mensal': float(sem_dept[1] or 0)
            })

        return result
    except Exception as e:
        logger.error(f"Erro funcionários por departamento: {e}")
        db.session.rollback()
        return []


def _calcular_custos_obra(admin_id, data_inicio, data_fim, obras_ids=None):
    """Custo Realizado por obra no período.

    Fontes (evitando dupla contagem):
    - GestaoCustoFilho filtrado por status do pai IN (PENDENTE, SOLICITADO, AUTORIZADO, PAGO, PARCIAL)
    - ContaPagar V1 por obra_id (lançamentos originados diretamente de compras)

    obras_ids: lista opcional de IDs de obras para filtrar; None = todas as obras.
    Retorna lista de dicts: {id, nome, realizado, orcamento, pct, estouro}
    """
    try:
        obras_filter = ""
        if obras_ids:
            ids_sql = ",".join(str(int(i)) for i in obras_ids if str(i).isdigit())
            if ids_sql:
                obras_filter = f"AND o.id IN ({ids_sql})"

        rows = db.session.execute(text(f"""
            SELECT
                o.id                          AS obra_id,
                o.nome                        AS obra_nome,
                COALESCE(o.orcamento, 0)      AS orcamento,
                COALESCE((
                    SELECT SUM(gcf.valor)
                    FROM gestao_custo_filho gcf
                    JOIN gestao_custo_pai gcp ON gcp.id = gcf.pai_id
                    WHERE gcf.obra_id = o.id
                      AND gcf.admin_id = :admin_id
                      AND gcp.status IN ('PENDENTE','SOLICITADO','AUTORIZADO','PAGO','PARCIAL')
                      AND gcf.data_referencia BETWEEN :data_inicio AND :data_fim
                ), 0) AS custo_gestao,
                COALESCE((
                    SELECT SUM(cp.valor_original)
                    FROM conta_pagar cp
                    WHERE cp.obra_id = o.id
                      AND cp.admin_id = :admin_id
                      AND (cp.data_vencimento IS NULL
                           OR cp.data_vencimento BETWEEN :data_inicio AND :data_fim)
                ), 0) AS custo_conta_pagar
            FROM obra o
            WHERE o.admin_id = :admin_id
              {obras_filter}
            ORDER BY o.nome
        """), {
            'admin_id': admin_id,
            'data_inicio': data_inicio,
            'data_fim': data_fim
        }).fetchall()

        result = []
        for row in rows:
            realizado = float(row[3] or 0) + float(row[4] or 0)
            orcamento = float(row[2] or 0)
            if realizado > 0 or orcamento > 0:
                pct = round(realizado / orcamento * 100, 1) if orcamento > 0 else 0.0
                result.append({
                    'id': row[0],
                    'nome': row[1],
                    'realizado': round(realizado, 2),
                    'orcamento': round(orcamento, 2),
                    'pct': pct,
                    'estouro': orcamento > 0 and realizado > orcamento,
                })

        return result
    except Exception as e:
        logger.error(f"Erro custos por obra: {e}")
        db.session.rollback()
        return []


def _calcular_custos_obra_acumulado(admin_id, obras_ids=None):
    """Custo Realizado acumulado por obra — sem recorte de data.

    Soma todo o histórico da obra (desde o início), independente do período
    selecionado no filtro do dashboard. Usa as mesmas fontes e filtros de
    status de _calcular_custos_obra, mas sem restrição de data.

    Retorna lista de dicts: {id, nome, realizado_acumulado, orcamento}
    """
    try:
        obras_filter = ""
        if obras_ids:
            ids_sql = ",".join(str(int(i)) for i in obras_ids if str(i).isdigit())
            if ids_sql:
                obras_filter = f"AND o.id IN ({ids_sql})"

        rows = db.session.execute(text(f"""
            SELECT
                o.id                          AS obra_id,
                o.nome                        AS obra_nome,
                COALESCE(o.orcamento, 0)      AS orcamento,
                COALESCE((
                    SELECT SUM(gcf.valor)
                    FROM gestao_custo_filho gcf
                    JOIN gestao_custo_pai gcp ON gcp.id = gcf.pai_id
                    WHERE gcf.obra_id = o.id
                      AND gcf.admin_id = :admin_id
                      AND gcp.status IN ('PENDENTE','SOLICITADO','AUTORIZADO','PAGO','PARCIAL')
                ), 0) AS custo_gestao,
                COALESCE((
                    SELECT SUM(cp.valor_original)
                    FROM conta_pagar cp
                    WHERE cp.obra_id = o.id
                      AND cp.admin_id = :admin_id
                ), 0) AS custo_conta_pagar
            FROM obra o
            WHERE o.admin_id = :admin_id
              {obras_filter}
            ORDER BY o.nome
        """), {'admin_id': admin_id}).fetchall()

        result = []
        for row in rows:
            realizado = float(row[3] or 0) + float(row[4] or 0)
            orcamento = float(row[2] or 0)
            if realizado > 0 or orcamento > 0:
                result.append({
                    'id': row[0],
                    'nome': row[1],
                    'realizado_acumulado': round(realizado, 2),
                    'orcamento': round(orcamento, 2),
                })

        return result
    except Exception as e:
        logger.error(f"Erro custos obra acumulado: {e}")
        db.session.rollback()
        return []


def _calcular_serie_temporal_custos(admin_id, obras_ids=None):
    """Custo mensal por obra para gráfico de linha de acumulado ao longo do tempo.

    Agrega os custos mês a mês (sem recorte de período do dashboard).
    Fontes:
    - gestao_custo_filho (por data_referencia) filtrado por status do pai
    - conta_pagar V1 por obra_id (por data_vencimento)

    obras_ids: lista opcional de IDs; None = todas as obras.
    Retorna lista de dicts ordenada por obra e mês:
      {obra_id, nome, ano_mes (YYYY-MM), custo_mensal}
    """
    try:
        obras_filter = ""
        if obras_ids:
            ids_sql = ",".join(str(int(i)) for i in obras_ids if str(i).isdigit())
            if ids_sql:
                obras_filter = f"AND o.id IN ({ids_sql})"

        rows = db.session.execute(text(f"""
            SELECT
                o.id                                                    AS obra_id,
                o.nome                                                  AS obra_nome,
                TO_CHAR(DATE_TRUNC('month', s.data_mes), 'YYYY-MM')    AS ano_mes,
                SUM(s.custo)                                            AS custo_mensal
            FROM obra o
            JOIN (
                SELECT gcf.obra_id, gcf.admin_id,
                       DATE_TRUNC('month', gcf.data_referencia) AS data_mes,
                       gcf.valor AS custo
                FROM gestao_custo_filho gcf
                JOIN gestao_custo_pai gcp ON gcp.id = gcf.pai_id
                WHERE gcf.admin_id = :admin_id
                  AND gcp.status IN ('PENDENTE','SOLICITADO','AUTORIZADO','PAGO','PARCIAL')
                  AND gcf.data_referencia IS NOT NULL
                UNION ALL
                SELECT cp.obra_id, cp.admin_id,
                       DATE_TRUNC('month', cp.data_vencimento) AS data_mes,
                       cp.valor_original AS custo
                FROM conta_pagar cp
                WHERE cp.admin_id = :admin_id
                  AND cp.obra_id IS NOT NULL
                  AND cp.data_vencimento IS NOT NULL
            ) s ON s.obra_id = o.id AND s.admin_id = :admin_id
            WHERE o.admin_id = :admin_id
              {obras_filter}
            GROUP BY o.id, o.nome, DATE_TRUNC('month', s.data_mes)
            ORDER BY o.nome, ano_mes
        """), {'admin_id': admin_id}).fetchall()

        result = []
        for row in rows:
            result.append({
                'obra_id':     row[0],
                'nome':        row[1],
                'ano_mes':     row[2],
                'custo_mensal': round(float(row[3] or 0), 2),
            })
        return result
    except Exception as e:
        logger.error(f"Erro série temporal custos: {e}")
        db.session.rollback()
        return []


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
