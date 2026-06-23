"""
SISTEMA DE ERRO DETALHADO PARA PRODUÇÃO - SIGE v8.0
Captura erros completos para debugging em ambiente de produção
"""

import traceback
import logging
import os
import sys
from datetime import datetime
from flask import request
import psycopg2
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def capture_production_error(exception, context="Sistema", additional_info=None):
    """
    Captura erro completo para exibição em produção
    
    Args:
        exception: A exceção capturada
        context: Contexto onde ocorreu o erro
        additional_info: Informações adicionais para debugging
    
    Returns:
        Dict com todas as informações para correção
    """
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Informações básicas do erro
    error_info = {
        'timestamp': timestamp,
        'context': context,
        'error_type': type(exception).__name__,
        'error_message': str(exception),
        'traceback': traceback.format_exc(),
    }
    
    # Informações da requisição
    try:
        error_info.update({
            'url': request.url if request else 'N/A',
            'method': request.method if request else 'N/A',
            'form_data': dict(request.form) if request and request.form else {},
            'args': dict(request.args) if request and request.args else {},
        })
    except:
        pass
    
    # Informações do ambiente
    error_info.update({
        'flask_env': os.environ.get('FLASK_ENV', 'unknown'),
        'database_url': os.environ.get('DATABASE_URL', 'not_set')[:50] + '...' if os.environ.get('DATABASE_URL') else 'not_set',
        'python_version': sys.version,
        'working_directory': os.getcwd(),
    })
    
    # Diagnóstico específico para erros SQL
    if isinstance(exception, (psycopg2.Error, SQLAlchemyError)):
        error_info.update(_diagnose_sql_error(exception))
    
    # Informações adicionais específicas do contexto
    if additional_info:
        error_info['additional_info'] = additional_info
    
    # Log completo para análise
    logger.error(f"🚨 ERRO PRODUÇÃO CAPTURADO:\n{format_error_for_log(error_info)}")
    
    return error_info

def _diagnose_sql_error(exception):
    """Diagnóstico específico para erros SQL"""
    
    diagnosis = {
        'sql_error_type': 'unknown',
        'suggested_fix': 'Verificar logs do banco de dados',
        'sql_state': getattr(exception, 'pgcode', 'unknown') if hasattr(exception, 'pgcode') else 'unknown'
    }
    
    error_str = str(exception).lower()
    
    if "column" in error_str and "does not exist" in error_str:
        diagnosis.update({
            'sql_error_type': 'COLUMN_NOT_EXISTS',
            'suggested_fix': 'Executar migração para criar coluna ausente',
            'migration_needed': True,
            'column_missing': _extract_missing_column(str(exception))
        })
    
    elif "transaction" in error_str and "aborted" in error_str:
        diagnosis.update({
            'sql_error_type': 'TRANSACTION_ABORTED',
            'suggested_fix': 'Adicionar rollback automático e retry da transação',
            'auto_recovery': True
        })
    
    elif "duplicate key" in error_str:
        diagnosis.update({
            'sql_error_type': 'DUPLICATE_KEY',
            'suggested_fix': 'Verificar uniqueness constraints e dados duplicados'
        })
    
    elif "foreign key" in error_str:
        diagnosis.update({
            'sql_error_type': 'FOREIGN_KEY_VIOLATION',
            'suggested_fix': 'Verificar integridade referencial das tabelas'
        })
    
    elif "connection" in error_str:
        diagnosis.update({
            'sql_error_type': 'CONNECTION_ERROR',
            'suggested_fix': 'Verificar conectividade com PostgreSQL e pool de conexões'
        })
    
    return diagnosis

def _extract_missing_column(error_message):
    """Extrai nome da coluna ausente do erro"""
    try:
        # Buscar padrão "column table.column does not exist"
        import re
        match = re.search(r'column\s+(\w+)\.(\w+)\s+does\s+not\s+exist', error_message, re.IGNORECASE)
        if match:
            return {
                'table': match.group(1),
                'column': match.group(2)
            }
    except:
        pass
    
    return {'table': 'unknown', 'column': 'unknown'}

def format_error_for_log(error_info):
    """Formata erro para log legível"""
    
    return f"""
=== ERRO PRODUÇÃO DETALHADO ===
Timestamp: {error_info['timestamp']}
Contexto: {error_info['context']}
Tipo: {error_info['error_type']}
Mensagem: {error_info['error_message']}

URL: {error_info.get('url', 'N/A')}
Método: {error_info.get('method', 'N/A')}

Ambiente: {error_info.get('flask_env', 'unknown')}
Database: {error_info.get('database_url', 'not_set')}

{f"SQL Error Type: {error_info.get('sql_error_type', 'N/A')}" if 'sql_error_type' in error_info else ''}
{f"Suggested Fix: {error_info.get('suggested_fix', 'N/A')}" if 'suggested_fix' in error_info else ''}

TRACEBACK:
{error_info['traceback']}
================================
"""

def format_error_for_user(error_info):
    """Formata erro para exibição ao usuário em produção"""
    
    # Determinar se é ambiente de desenvolvimento
    is_dev = (error_info.get('flask_env') == 'development' or 
              os.environ.get('SHOW_DETAILED_ERRORS') == 'true')
    
    if is_dev:
        return f"""
        <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; margin: 20px; border-radius: 8px; font-family: 'Segoe UI', sans-serif;">
            <h3 style="color: #721c24; margin: 0 0 15px 0;">🚨 Erro Detalhado - {error_info['context']}</h3>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h4 style="margin: 0 0 10px 0; color: #495057;">📋 Informações do Erro</h4>
                <p><strong>Tipo:</strong> {error_info['error_type']}</p>
                <p><strong>Mensagem:</strong> {error_info['error_message']}</p>
                <p><strong>Timestamp:</strong> {error_info['timestamp']}</p>
                
                {f'<p><strong>Erro SQL:</strong> {error_info.get("sql_error_type", "N/A")}</p>' if 'sql_error_type' in error_info else ''}
                {f'<p><strong>Correção Sugerida:</strong> {error_info.get("suggested_fix", "N/A")}</p>' if 'suggested_fix' in error_info else ''}
            </div>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h4 style="margin: 0 0 10px 0; color: #495057;">🌐 Contexto da Requisição</h4>
                <p><strong>URL:</strong> {error_info.get('url', 'N/A')}</p>
                <p><strong>Método:</strong> {error_info.get('method', 'N/A')}</p>
                <p><strong>Dados do Form:</strong> {error_info.get('form_data', {})}</p>
            </div>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h4 style="margin: 0 0 10px 0; color: #495057;">🔧 Ambiente</h4>
                <p><strong>Flask Env:</strong> {error_info.get('flask_env', 'unknown')}</p>
                <p><strong>Database:</strong> {error_info.get('database_url', 'not_set')}</p>
            </div>
            
            <details style="margin: 15px 0;">
                <summary style="cursor: pointer; padding: 10px; background: #e9ecef; border-radius: 5px; font-weight: bold;">
                    🔍 Stack Trace Completo
                </summary>
                <pre style="background: #2d3748; color: #e2e8f0; padding: 20px; border-radius: 5px; font-family: 'Consolas', monospace; font-size: 12px; overflow-x: auto; margin: 10px 0;">{error_info['traceback']}</pre>
            </details>
            
            <div style="margin-top: 20px;">
                <button onclick="copyErrorDetails()" style="background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-right: 10px;">
                    📋 Copiar Detalhes do Erro
                </button>
                <a href="/dashboard" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    ← Voltar ao Dashboard
                </a>
            </div>
            
            <script>
                function copyErrorDetails() {{
                    const errorText = `ERRO PRODUÇÃO - {error_info['context']}
Timestamp: {error_info['timestamp']}
Tipo: {error_info['error_type']}
Mensagem: {error_info['error_message']}
URL: {error_info.get('url', 'N/A')}
{f"SQL Error: {error_info.get('sql_error_type', 'N/A')}" if 'sql_error_type' in error_info else ''}
{f"Correção: {error_info.get('suggested_fix', 'N/A')}" if 'suggested_fix' in error_info else ''}

STACK TRACE:
{error_info['traceback']}`;
                    
                    navigator.clipboard.writeText(errorText).then(function() {{
                        alert('✅ Detalhes do erro copiados! Cole no chat para análise.');
                    }});
                }}
            </script>
        </div>
        """
    else:
        # Produção: mensagem resumida mas informativa
        return f"""
        <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; margin: 20px; border-radius: 8px; font-family: 'Segoe UI', sans-serif;">
            <h4 style="color: #721c24; margin: 0 0 15px 0;">⚠️ Erro no {error_info['context']}</h4>
            <p style="margin: 0 0 10px 0;">Erro: <strong>{error_info['error_type']}</strong></p>
            <p style="margin: 0 0 10px 0;">Horário: <strong>{error_info['timestamp']}</strong></p>
            {f'<p style="margin: 0 0 10px 0;">Tipo SQL: <strong>{error_info.get("sql_error_type", "N/A")}</strong></p>' if 'sql_error_type' in error_info else ''}
            {f'<p style="margin: 0 0 15px 0;">Solução: <strong>{error_info.get("suggested_fix", "Entre em contato com o suporte")}</strong></p>' if 'suggested_fix' in error_info else ''}
            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; border-radius: 5px; font-size: 14px;">
                ℹ️ Os detalhes técnicos foram registrados nos logs do sistema para análise.
            </div>
        </div>
        """