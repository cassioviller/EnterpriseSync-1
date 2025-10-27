"""
Database utilities - Decorators e helpers para operações DB
✅ OTIMIZAÇÃO MÉDIO PRAZO 3: Decorator @db_transaction
"""

from functools import wraps
from models import db
import logging

logger = logging.getLogger(__name__)


def db_transaction(f):
    """
    Decorator que envolve funções em uma transação atômica de banco de dados.
    
    Comportamento:
    - Inicia transação automaticamente
    - Commit automático se função executar sem erro
    - Rollback automático se houver exceção
    - Re-levanta exceção para código chamador lidar
    
    Uso:
    ```python
    @db_transaction
    def minha_funcao():
        obj1 = Model1(...)
        db.session.add(obj1)
        # Mais operações...
        # Commit automático no final
        return resultado
    ```
    
    Benefícios:
    - Reduz código boilerplate (try/except/commit/rollback)
    - Garante atomicidade (tudo ou nada)
    - Melhora legibilidade
    - Logging automático de erros
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Executar função
            result = f(*args, **kwargs)
            
            # Commit automático se tudo deu certo
            db.session.commit()
            logger.debug(f"✅ Transação {f.__name__} concluída com sucesso")
            
            return result
            
        except Exception as e:
            # Rollback automático em caso de erro
            db.session.rollback()
            logger.error(f"❌ Transação {f.__name__} falhou: {str(e)}")
            
            # Re-levantar exceção para código chamador lidar
            raise
    
    return decorated_function


def safe_db_operation(operation_name):
    """
    Decorator parametrizado para operações DB com nome personalizado.
    
    Uso:
    ```python
    @safe_db_operation("criar_custo_obra")
    def criar_custo(...):
        # código
    ```
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                db.session.commit()
                logger.info(f"✅ Operação '{operation_name}' concluída")
                return result
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Operação '{operation_name}' falhou: {str(e)}")
                raise
        return wrapper
    return decorator
