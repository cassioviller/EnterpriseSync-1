"""
Circuit Breaker para SIGE
Implementa padrão Circuit Breaker para operações externas e críticas
"""

import time
import threading
from enum import Enum
from functools import wraps
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"       # Funcionando normalmente
    OPEN = "OPEN"           # Circuito aberto - falhando
    HALF_OPEN = "HALF_OPEN" # Testando se voltou a funcionar

class CircuitBreakerError(Exception):
    """Exceção lançada quando circuit breaker está aberto"""
    pass

class CircuitBreaker:
    """
    Implementação de Circuit Breaker thread-safe
    """
    
    def __init__(self, 
                 name: str,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: tuple = (Exception,),
                 fallback: Optional[Callable] = None):
        """
        Args:
            name: Nome do circuit breaker para logs
            failure_threshold: Número de falhas consecutivas para abrir
            recovery_timeout: Tempo em segundos para tentar half-open
            expected_exception: Tupla de exceções que contam como falha
            fallback: Função de fallback quando circuito está aberto
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.fallback = fallback
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._lock = threading.RLock()
        
        logger.info(f"🔌 Circuit Breaker '{name}' inicializado - threshold={failure_threshold}, timeout={recovery_timeout}s")

    @property
    def state(self) -> CircuitState:
        """Estado atual do circuit breaker"""
        with self._lock:
            # Verificar se deve tentar half-open
            if (self._state == CircuitState.OPEN and 
                self._last_failure_time and 
                time.time() - self._last_failure_time >= self.recovery_timeout):
                
                self._state = CircuitState.HALF_OPEN
                logger.info(f"🔄 Circuit Breaker '{self.name}' mudou para HALF_OPEN")
                
            return self._state

    @property
    def failure_count(self) -> int:
        """Número atual de falhas consecutivas"""
        with self._lock:
            return self._failure_count

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa função através do circuit breaker
        """
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            logger.warning(f"🚫 Circuit Breaker '{self.name}' ABERTO - chamada bloqueada")
            if self.fallback:
                logger.info(f"🔄 Executando fallback para '{self.name}'")
                return self.fallback(*args, **kwargs)
            else:
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' está aberto")
        
        try:
            # Executar função
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Sucesso - resetar contador se estava em half-open
            if current_state == CircuitState.HALF_OPEN:
                self._on_success()
                logger.info(f"✅ Circuit Breaker '{self.name}' FECHADO após sucesso em half-open")
            elif self._failure_count > 0:
                # Resetar contador de falhas em caso de sucesso
                with self._lock:
                    self._failure_count = 0
                    
            logger.debug(f"✅ '{self.name}' executado com sucesso em {execution_time:.3f}s")
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            logger.error(f"❌ Falha em '{self.name}': {str(e)}")
            raise
        except Exception as e:
            # Exceções não esperadas não contam como falha do circuit breaker
            logger.error(f"⚠️ Exceção inesperada em '{self.name}': {str(e)}")
            raise

    def _on_success(self):
        """Chamado quando operação é bem-sucedida"""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def _on_failure(self):
        """Chamado quando operação falha"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(f"🔴 Circuit Breaker '{self.name}' ABERTO após {self._failure_count} falhas")

    def reset(self):
        """Reset manual do circuit breaker"""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._last_failure_time = None
            logger.info(f"🔄 Circuit Breaker '{self.name}' resetado manualmente")

    def get_metrics(self) -> dict:
        """Retorna métricas do circuit breaker"""
        with self._lock:
            return {
                'name': self.name,
                'state': self._state.value,
                'failure_count': self._failure_count,
                'failure_threshold': self.failure_threshold,
                'last_failure_time': self._last_failure_time,
                'recovery_timeout': self.recovery_timeout
            }

# Registry global de circuit breakers
_circuit_breakers = {}
_registry_lock = threading.RLock()

def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Obtém ou cria circuit breaker com nome específico
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
        return _circuit_breakers[name]

def circuit_breaker(name: str = None, 
                   failure_threshold: int = 5,
                   recovery_timeout: int = 60,
                   expected_exception: tuple = (Exception,),
                   fallback: Optional[Callable] = None):
    """
    Decorator para aplicar circuit breaker em funções
    
    Args:
        name: Nome do circuit breaker (padrão: nome da função)
        failure_threshold: Número de falhas para abrir circuito
        recovery_timeout: Tempo para tentar refechar
        expected_exception: Exceções que contam como falha
        fallback: Função de fallback
    """
    def decorator(func):
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        breaker = get_circuit_breaker(
            breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            fallback=fallback
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        
        # Adicionar referência ao breaker na função
        wrapper._circuit_breaker = breaker
        return wrapper
    
    return decorator

# Fallbacks específicos do SIGE

def pdf_generation_fallback(*args, **kwargs):
    """Fallback para geração de PDF"""
    logger.warning("📄 PDF generation fallback: retornando resposta simplificada")
    from flask import jsonify
    return jsonify({
        'error': 'Serviço de PDF temporariamente indisponível',
        'message': 'Tente novamente em alguns minutos',
        'fallback': True
    }), 503

def database_query_fallback(*args, **kwargs):
    """Fallback para consultas pesadas ao banco"""
    logger.warning("🗄️ Database query fallback: retornando dados em cache")
    return {
        'data': [],
        'message': 'Dados temporariamente indisponíveis - usando cache',
        'fallback': True
    }

def file_upload_fallback(*args, **kwargs):
    """Fallback para upload de arquivos"""
    logger.warning("📁 File upload fallback: modo offline")
    return {
        'success': False,
        'message': 'Upload temporariamente indisponível',
        'fallback': True
    }

# Métricas de todos os circuit breakers
def get_all_metrics() -> dict:
    """Retorna métricas de todos os circuit breakers"""
    with _registry_lock:
        return {name: breaker.get_metrics() for name, breaker in _circuit_breakers.items()}

def reset_all_breakers():
    """Reset de todos os circuit breakers"""
    with _registry_lock:
        for breaker in _circuit_breakers.values():
            breaker.reset()
        logger.info("🔄 Todos os circuit breakers foram resetados")

# Configurações específicas por ambiente
class CircuitBreakerConfig:
    """Configurações de circuit breaker por ambiente"""
    
    # Configurações para produção
    PRODUCTION = {
        'pdf_generation': {
            'failure_threshold': 3,
            'recovery_timeout': 120,
            'expected_exception': (TimeoutError, ConnectionError, OSError)
        },
        'database_heavy_query': {
            'failure_threshold': 2,
            'recovery_timeout': 60,
            'expected_exception': (TimeoutError, Exception)
        },
        'file_operations': {
            'failure_threshold': 5,
            'recovery_timeout': 30,
            'expected_exception': (IOError, OSError, PermissionError)
        }
    }
    
    # Configurações para desenvolvimento  
    DEVELOPMENT = {
        'pdf_generation': {
            'failure_threshold': 5,
            'recovery_timeout': 30,
            'expected_exception': (Exception,)
        },
        'database_heavy_query': {
            'failure_threshold': 10,
            'recovery_timeout': 15,
            'expected_exception': (Exception,)
        },
        'file_operations': {
            'failure_threshold': 10,
            'recovery_timeout': 10,
            'expected_exception': (Exception,)
        }
    }
    
    @classmethod
    def get_config(cls, name: str, environment: str = 'development') -> dict:
        """Obtém configuração por nome e ambiente"""
        config = getattr(cls, environment.upper(), cls.DEVELOPMENT)
        return config.get(name, {})

# Aplicação automática de circuit breakers em operações críticas do SIGE
def apply_sige_circuit_breakers():
    """Aplica circuit breakers em operações críticas identificadas"""
    import os
    environment = os.getenv('FLASK_ENV', 'development')
    
    # Configurar circuit breakers principais
    pdf_config = CircuitBreakerConfig.get_config('pdf_generation', environment)
    get_circuit_breaker('pdf_generation', fallback=pdf_generation_fallback, **pdf_config)
    
    db_config = CircuitBreakerConfig.get_config('database_heavy_query', environment)
    get_circuit_breaker('database_heavy_query', fallback=database_query_fallback, **db_config)
    
    file_config = CircuitBreakerConfig.get_config('file_operations', environment)
    get_circuit_breaker('file_operations', fallback=file_upload_fallback, **file_config)
    
    logger.info(f"🔌 Circuit breakers SIGE configurados para ambiente: {environment}")