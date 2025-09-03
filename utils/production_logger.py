"""
SISTEMA DE LOGGING PARA PRODUÇÃO - SIGE v8.0.1
Captura detalhada de erros sem acesso direto aos dados de produção
"""

import logging
import traceback
import json
import os
from datetime import datetime
from flask import request, session, g
from functools import wraps

class ProductionLogger:
    """Logger especializado para ambiente de produção"""
    
    def __init__(self, app=None):
        self.app = app
        self.setup_logging()
        
    def setup_logging(self):
        """Configurar sistema de logging para produção"""
        # Criar diretório de logs se não existir
        os.makedirs('/app/logs', exist_ok=True)
        
        # Configurar formatter detalhado
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
        )
        
        # Handler para arquivo de erro geral
        error_handler = logging.FileHandler('/app/logs/production_errors.log')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        
        # Handler para debug específico
        debug_handler = logging.FileHandler('/app/logs/production_debug.log')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)
        
        # Handler para console (visível nos logs do container)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Configurar logger raiz
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(debug_handler)
        root_logger.addHandler(console_handler)
        
        # Logger específico para RDO
        self.rdo_logger = logging.getLogger('RDO_PRODUCTION')
        self.rdo_logger.setLevel(logging.DEBUG)
        
        # Logger específico para banco de dados
        self.db_logger = logging.getLogger('DB_PRODUCTION')
        self.db_logger.setLevel(logging.DEBUG)
        
        print("✅ Sistema de logging de produção configurado")

    def capture_context(self):
        """Capturar contexto completo da requisição"""
        context = {
            'timestamp': datetime.now().isoformat(),
            'url': getattr(request, 'url', 'N/A') if request else 'N/A',
            'method': getattr(request, 'method', 'N/A') if request else 'N/A',
            'remote_addr': getattr(request, 'remote_addr', 'N/A') if request else 'N/A',
            'user_agent': getattr(request, 'headers', {}).get('User-Agent', 'N/A') if request else 'N/A',
            'form_data_keys': list(request.form.keys()) if request and hasattr(request, 'form') else [],
            'session_keys': list(session.keys()) if session else [],
            'has_current_user': hasattr(g, 'user') if g else False,
            'environment': os.environ.get('FLASK_ENV', 'unknown'),
            'database_url_set': bool(os.environ.get('DATABASE_URL')),
        }
        return context

    def log_rdo_error(self, operation, error, extra_context=None):
        """Log específico para erros de RDO"""
        context = self.capture_context()
        if extra_context:
            context.update(extra_context)
            
        error_data = {
            'operation': operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context
        }
        
        self.rdo_logger.error(f"RDO_ERROR: {operation} - {error}")
        self.rdo_logger.error(f"RDO_CONTEXT: {json.dumps(error_data, indent=2, default=str)}")
        
        # Log no console para visibilidade imediata
        print(f"🚨 RDO_PRODUCTION_ERROR: {operation}")
        print(f"   ❌ {type(error).__name__}: {error}")
        print(f"   📍 URL: {context.get('url', 'N/A')}")
        print(f"   🔍 Form keys: {context.get('form_data_keys', [])}")
        
        return error_data

    def log_db_error(self, query, error, params=None):
        """Log específico para erros de banco de dados"""
        context = self.capture_context()
        
        db_error_data = {
            'query': query,
            'params': params,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context
        }
        
        self.db_logger.error(f"DB_ERROR: {query}")
        self.db_logger.error(f"DB_CONTEXT: {json.dumps(db_error_data, indent=2, default=str)}")
        
        # Log no console
        print(f"🚨 DB_PRODUCTION_ERROR: {type(error).__name__}")
        print(f"   📊 Query: {query[:100]}...")
        print(f"   ❌ Error: {error}")
        
        return db_error_data

    def log_success(self, operation, details=None):
        """Log de operações bem-sucedidas para debugging"""
        context = self.capture_context()
        success_data = {
            'operation': operation,
            'details': details,
            'context': context
        }
        
        self.rdo_logger.info(f"RDO_SUCCESS: {operation}")
        if details:
            self.rdo_logger.debug(f"RDO_SUCCESS_DETAILS: {json.dumps(details, default=str)}")

def log_production_error(operation):
    """Decorator para capturar erros automaticamente"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                # Log sucesso se configurado
                if hasattr(g, 'production_logger'):
                    g.production_logger.log_success(f"{func.__name__}({operation})")
                return result
            except Exception as e:
                # Capturar erro detalhado
                logger = getattr(g, 'production_logger', None)
                if logger:
                    error_data = logger.log_rdo_error(f"{func.__name__}({operation})", e)
                else:
                    # Fallback básico
                    print(f"🚨 PRODUCTION_ERROR_FALLBACK: {func.__name__} - {e}")
                    traceback.print_exc()
                
                # Re-raise o erro para não quebrar o fluxo
                raise e
        return wrapper
    return decorator

# Instância global
production_logger = ProductionLogger()