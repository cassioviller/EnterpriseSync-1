"""
Sistema de Diagnóstico Automático de Erros de Banco de Dados - SIGE
Captura, analisa e reporta erros de banco de forma clara e acionável
"""

import logging
import os
import re
from datetime import datetime
from functools import wraps
from flask import flash, url_for
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
import traceback

logger = logging.getLogger(__name__)

# Arquivo de log de diagnósticos
DIAGNOSTICS_LOG_FILE = '/tmp/db_diagnostics.log'

# Tabelas que devem ter admin_id (Migração 48) - Lista CORRETA sincronizada com migrations.py
MIGRATION_48_TABLES = [
    'departamento', 'funcao', 'horario_trabalho',
    'servico_obra', 'historico_produtividade_servico',
    'tipo_ocorrencia', 'ocorrencia', 'calendario_util',
    'centro_custo', 'receita', 'orcamento_obra',
    'fluxo_caixa', 'registro_alimentacao',
    'rdo_mao_obra', 'rdo_equipamento', 'rdo_ocorrencia', 'rdo_foto',
    'notificacao_cliente', 'proposta_itens', 'proposta_arquivos'
]


def analyze_db_error(error):
    """
    Analisa erro SQLAlchemy e extrai informações úteis
    
    Args:
        error: Exception do SQLAlchemy
        
    Returns:
        dict com informações do erro: {
            'tipo': str,
            'mensagem': str,
            'tabela': str ou None,
            'coluna': str ou None,
            'sql': str ou None,
            'trace': str
        }
    """
    error_info = {
        'tipo': type(error).__name__,
        'mensagem': str(error),
        'tabela': None,
        'coluna': None,
        'sql': None,
        'trace': traceback.format_exc()
    }
    
    error_msg = str(error).lower()
    
    # Extrair nome da tabela
    table_pattern = r'(?:table|relation)\s+["\']?(\w+)["\']?'
    table_match = re.search(table_pattern, error_msg)
    if table_match:
        error_info['tabela'] = table_match.group(1)
    
    # Extrair nome da coluna (especialmente para "column does not exist")
    column_pattern = r'column\s+(?:[\w]+\.)?(\w+)\s+does not exist'
    column_match = re.search(column_pattern, error_msg)
    if column_match:
        error_info['coluna'] = column_match.group(1)
        # Tentar extrair tabela do formato "table.column"
        table_column_pattern = r'column\s+([\w]+)\.([\w]+)\s+does not exist'
        tc_match = re.search(table_column_pattern, error_msg)
        if tc_match:
            error_info['tabela'] = tc_match.group(1)
            error_info['coluna'] = tc_match.group(2)
    
    # Extrair SQL original se disponível
    if hasattr(error, 'statement'):
        error_info['sql'] = str(error.statement)[:500]  # Limitar tamanho
    
    return error_info


def get_table_structure(table_name, engine=None):
    """
    Retorna estrutura completa de uma tabela do banco de dados
    
    Args:
        table_name: Nome da tabela
        engine: SQLAlchemy engine (opcional, usa db.engine se None)
        
    Returns:
        list de dicts: [{
            'nome': str,
            'tipo': str,
            'nullable': bool,
            'default': str ou None,
            'primary_key': bool
        }]
    """
    from models import db
    
    if engine is None:
        engine = db.engine
    
    try:
        inspector = inspect(engine)
        
        if table_name not in inspector.get_table_names():
            return None
        
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pk_columns = pk_constraint.get('constrained_columns', []) if pk_constraint else []
        
        structure = []
        for col in columns:
            structure.append({
                'nome': col['name'],
                'tipo': str(col['type']),
                'nullable': col['nullable'],
                'default': str(col['default']) if col['default'] else None,
                'primary_key': col['name'] in pk_columns
            })
        
        return structure
    except Exception as e:
        logger.error(f"Erro ao obter estrutura da tabela {table_name}: {e}")
        return None


def get_missing_columns(table_name, expected_columns, engine=None):
    """
    Verifica quais colunas estão faltando em uma tabela
    
    Args:
        table_name: Nome da tabela
        expected_columns: Lista de nomes de colunas esperadas
        engine: SQLAlchemy engine (opcional)
        
    Returns:
        dict: {
            'faltando': list de colunas que não existem,
            'existentes': list de colunas que existem,
            'extras': list de colunas que existem mas não eram esperadas
        }
    """
    structure = get_table_structure(table_name, engine)
    
    if structure is None:
        return {
            'faltando': expected_columns,
            'existentes': [],
            'extras': [],
            'table_exists': False
        }
    
    existing_columns = {col['nome'] for col in structure}
    expected_set = set(expected_columns)
    
    return {
        'faltando': list(expected_set - existing_columns),
        'existentes': list(expected_set & existing_columns),
        'extras': list(existing_columns - expected_set),
        'table_exists': True
    }


def generate_diagnostic_report(error, context=None):
    """
    Gera relatório de diagnóstico formatado para um erro
    
    Args:
        error: Exception do banco de dados
        context: Dict com contexto adicional (opcional)
        
    Returns:
        str: Relatório formatado
    """
    error_info = analyze_db_error(error)
    
    report_lines = [
        "🔴 ERRO DE BANCO DE DADOS DETECTADO",
        "=" * 80
    ]
    
    # Informações básicas do erro
    if error_info['tabela']:
        report_lines.append(f"Tabela: {error_info['tabela']}")
    
    report_lines.append(f"Tipo: {error_info['tipo']}")
    report_lines.append(f"Erro: {error_info['mensagem'][:200]}")
    report_lines.append("")
    
    # Se houver informação sobre coluna faltando
    if error_info['coluna'] and 'does not exist' in error_info['mensagem'].lower():
        report_lines.append(f"❌ COLUNA FALTANDO: {error_info['coluna']}")
        report_lines.append("")
        
        # Mostrar estrutura atual da tabela se possível
        if error_info['tabela']:
            structure = get_table_structure(error_info['tabela'])
            if structure:
                report_lines.append("📊 ESTRUTURA ATUAL DA TABELA:")
                for col in structure:
                    pk_mark = ", PRIMARY KEY" if col['primary_key'] else ""
                    null_mark = "" if col['nullable'] else ", NOT NULL"
                    report_lines.append(f"  - {col['nome']} ({col['tipo']}{pk_mark}{null_mark})")
                report_lines.append("")
            
            # Verificar se é uma tabela da Migração 48
            if error_info['tabela'] in MIGRATION_48_TABLES and error_info['coluna'] == 'admin_id':
                report_lines.append("✅ SOLUÇÃO:")
                report_lines.append("Execute a Migração 48 em produção para adicionar admin_id em 20 tabelas.")
                report_lines.append("")
    
    # SQL que causou o erro
    if error_info['sql']:
        report_lines.append("💻 SQL QUE CAUSOU O ERRO:")
        report_lines.append(f"{error_info['sql'][:300]}")
        report_lines.append("")
    
    # Verificações
    if error_info['tabela']:
        report_lines.append("📋 VERIFICAÇÕES:")
        structure = get_table_structure(error_info['tabela'])
        report_lines.append(f"  - Tabela existe: {'✅' if structure else '❌'}")
        
        if structure and error_info['coluna']:
            has_column = any(col['nome'] == error_info['coluna'] for col in structure)
            report_lines.append(f"  - Coluna '{error_info['coluna']}' existe: {'✅' if has_column else '❌'}")
        
        if error_info['tabela'] in MIGRATION_48_TABLES:
            has_admin_id = structure and any(col['nome'] == 'admin_id' for col in structure)
            report_lines.append(f"  - Admin_id existe: {'✅' if has_admin_id else '❌'}")
            report_lines.append(f"  - Migração 48 executada: {'✅' if has_admin_id else '❌'}")
        
        report_lines.append("")
    
    # Ação recomendada
    report_lines.append("🔧 AÇÃO RECOMENDADA:")
    if error_info['coluna'] == 'admin_id' and error_info['tabela'] in MIGRATION_48_TABLES:
        report_lines.append("1. Fazer backup do banco de dados")
        report_lines.append("2. Executar migração 48 (adicionar admin_id às tabelas)")
        report_lines.append("3. Reiniciar a aplicação")
    else:
        report_lines.append("1. Verificar logs completos do erro")
        report_lines.append("2. Consultar documentação do sistema")
        report_lines.append("3. Contatar suporte técnico se necessário")
    
    report_lines.append("=" * 80)
    
    # Adicionar contexto se fornecido
    if context:
        report_lines.append("")
        report_lines.append("📝 CONTEXTO ADICIONAL:")
        for key, value in context.items():
            report_lines.append(f"  {key}: {value}")
    
    return "\n".join(report_lines)


def log_diagnostic(report, error=None):
    """
    Registra diagnóstico em arquivo de log
    
    Args:
        report: Relatório formatado
        error: Exception original (opcional)
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(DIAGNOSTICS_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"TIMESTAMP: {timestamp}\n")
            f.write(report)
            f.write(f"\n{'='*80}\n\n")
        
        logger.info(f"Diagnóstico registrado em {DIAGNOSTICS_LOG_FILE}")
    except Exception as e:
        logger.error(f"Erro ao registrar diagnóstico: {e}")


def capture_db_errors(func):
    """
    Decorator para capturar automaticamente erros de banco de dados
    
    Usage:
        @capture_db_errors
        def minha_funcao():
            # código que pode gerar erro de DB
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (SQLAlchemyError, OperationalError, ProgrammingError) as e:
            # Gerar relatório de diagnóstico
            context = {
                'funcao': func.__name__,
                'modulo': func.__module__
            }
            report = generate_diagnostic_report(e, context)
            
            # Registrar em log
            log_diagnostic(report, e)
            
            # Adicionar flash message com link para diagnóstico
            try:
                flash(
                    f'❌ Erro de banco de dados detectado. '
                    f'<a href="{url_for("main.database_diagnostics")}">Ver diagnóstico completo</a>',
                    'danger'
                )
            except:
                pass  # Se não estiver em contexto de request, ignorar flash
            
            # Re-raise o erro para não quebrar o fluxo
            raise
    
    return wrapper


class DatabaseDiagnostics:
    """
    Classe para facilitar operações de diagnóstico de banco de dados
    """
    
    def __init__(self, db_engine=None):
        """
        Args:
            db_engine: SQLAlchemy engine (opcional, usa db.engine se None)
        """
        self.engine = db_engine
        if self.engine is None:
            from models import db
            self.engine = db.engine
    
    def check_migration_48_status(self):
        """
        Verifica status da migração 48 (admin_id em 20 tabelas)
        
        Returns:
            dict: {
                'completa': bool,
                'tabelas_ok': list,
                'tabelas_faltando': list,
                'detalhes': dict
            }
        """
        result = {
            'completa': True,
            'tabelas_ok': [],
            'tabelas_faltando': [],
            'detalhes': {}
        }
        
        for table in MIGRATION_48_TABLES:
            structure = get_table_structure(table, self.engine)
            
            if structure is None:
                result['tabelas_faltando'].append(table)
                result['detalhes'][table] = 'Tabela não existe'
                result['completa'] = False
            else:
                has_admin_id = any(col['nome'] == 'admin_id' for col in structure)
                
                if has_admin_id:
                    result['tabelas_ok'].append(table)
                    result['detalhes'][table] = 'OK - admin_id presente'
                else:
                    result['tabelas_faltando'].append(table)
                    result['detalhes'][table] = 'FALTA - admin_id ausente'
                    result['completa'] = False
        
        return result
    
    def get_all_tables(self):
        """
        Retorna lista de todas as tabelas do banco
        
        Returns:
            list de strings (nomes das tabelas)
        """
        try:
            inspector = inspect(self.engine)
            return sorted(inspector.get_table_names())
        except Exception as e:
            logger.error(f"Erro ao listar tabelas: {e}")
            return []
    
    def check_table_health(self, table_name):
        """
        Verifica saúde geral de uma tabela
        
        Returns:
            dict com informações de saúde da tabela
        """
        structure = get_table_structure(table_name, self.engine)
        
        if structure is None:
            return {
                'exists': False,
                'error': 'Tabela não encontrada'
            }
        
        # Contar registros
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
        except Exception as e:
            count = None
            error = str(e)
        
        return {
            'exists': True,
            'columns': len(structure),
            'column_list': [col['nome'] for col in structure],
            'has_admin_id': any(col['nome'] == 'admin_id' for col in structure),
            'row_count': count,
            'primary_keys': [col['nome'] for col in structure if col['primary_key']]
        }
    
    def read_recent_diagnostics(self, max_entries=10):
        """
        Lê diagnósticos recentes do arquivo de log
        
        Args:
            max_entries: Número máximo de entradas a retornar
            
        Returns:
            list de strings (relatórios de diagnóstico)
        """
        if not os.path.exists(DIAGNOSTICS_LOG_FILE):
            return []
        
        try:
            with open(DIAGNOSTICS_LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Dividir por separadores
            entries = content.split('=' * 80)
            
            # Filtrar entradas vazias e pegar as mais recentes
            valid_entries = [e.strip() for e in entries if e.strip()]
            
            return valid_entries[-max_entries:][::-1]  # Reverter para mais recente primeiro
        except Exception as e:
            logger.error(f"Erro ao ler diagnósticos: {e}")
            return []
