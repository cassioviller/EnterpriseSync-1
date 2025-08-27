"""
Middleware de Idempotência para SIGE
Implementa padrão idempotente para operações críticas
"""

import hashlib
import json
import time
from functools import wraps
from flask import request, jsonify, g
from sqlalchemy import text
from app import db
import logging

logger = logging.getLogger(__name__)

class IdempotencyStore:
    """Armazenamento de chaves idempotentes no PostgreSQL"""
    
    @staticmethod
    def ensure_table_exists():
        """Cria tabela de idempotência se não existir"""
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    id SERIAL PRIMARY KEY,
                    key_hash VARCHAR(64) UNIQUE NOT NULL,
                    payload_hash VARCHAR(64) NOT NULL,
                    response_data TEXT,
                    status VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    admin_id INTEGER,
                    operation_type VARCHAR(50),
                    correlation_id VARCHAR(100)
                );
                
                CREATE INDEX IF NOT EXISTS idx_idempotency_key_hash ON idempotency_keys(key_hash);
                CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys(expires_at);
            """))
            db.session.commit()
            logger.info("✅ Tabela idempotency_keys criada/verificada")
        except Exception as e:
            logger.error(f"Erro ao criar tabela idempotency: {e}")
            db.session.rollback()

    @staticmethod
    def store_key(key_hash, payload_hash, status, response_data=None, ttl_seconds=3600, admin_id=None, operation_type=None, correlation_id=None):
        """Armazena chave idempotente"""
        try:
            expires_at = time.time() + ttl_seconds
            
            db.session.execute(text("""
                INSERT INTO idempotency_keys 
                (key_hash, payload_hash, response_data, status, expires_at, admin_id, operation_type, correlation_id)
                VALUES (:key_hash, :payload_hash, :response_data, :status, 
                        to_timestamp(:expires_at), :admin_id, :operation_type, :correlation_id)
                ON CONFLICT (key_hash) DO UPDATE SET
                    response_data = EXCLUDED.response_data,
                    status = EXCLUDED.status
            """), {
                'key_hash': key_hash,
                'payload_hash': payload_hash,
                'response_data': response_data,
                'status': status,
                'expires_at': expires_at,
                'admin_id': admin_id,
                'operation_type': operation_type,
                'correlation_id': correlation_id
            })
            db.session.commit()
            logger.debug(f"🔑 Chave idempotente armazenada: {key_hash[:8]}...")
        except Exception as e:
            logger.error(f"Erro ao armazenar chave idempotente: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def get_key(key_hash):
        """Recupera chave idempotente se existir e não expirou"""
        try:
            result = db.session.execute(text("""
                SELECT payload_hash, response_data, status, correlation_id
                FROM idempotency_keys 
                WHERE key_hash = :key_hash 
                AND expires_at > CURRENT_TIMESTAMP
            """), {'key_hash': key_hash}).fetchone()
            
            if result:
                logger.debug(f"🔍 Chave encontrada: {key_hash[:8]}... status={result[2]}")
                return {
                    'payload_hash': result[0],
                    'response_data': result[1],
                    'status': result[2],
                    'correlation_id': result[3]
                }
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar chave idempotente: {e}")
            return None

    @staticmethod
    def cleanup_expired():
        """Remove chaves expiradas (executar periodicamente)"""
        try:
            result = db.session.execute(text("""
                DELETE FROM idempotency_keys 
                WHERE expires_at < CURRENT_TIMESTAMP
            """))
            deleted = result.rowcount
            db.session.commit()
            if deleted > 0:
                logger.info(f"🧹 Limpeza: {deleted} chaves expiradas removidas")
        except Exception as e:
            logger.error(f"Erro na limpeza de chaves: {e}")
            db.session.rollback()

def generate_key_hash(operation_type, admin_id, custom_key=None, **kwargs):
    """Gera hash da chave idempotente baseado no contexto"""
    key_parts = [
        operation_type,
        str(admin_id) if admin_id else 'no-admin',
        custom_key or 'auto'
    ]
    
    # Adicionar parâmetros específicos ordenados
    for key in sorted(kwargs.keys()):
        key_parts.append(f"{key}={kwargs[key]}")
    
    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()

def generate_payload_hash(data):
    """Gera hash do payload para detectar alterações"""
    if isinstance(data, dict):
        # Ordenar keys para hash consistente
        normalized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    else:
        normalized = str(data)
    
    return hashlib.sha256(normalized.encode()).hexdigest()

def idempotent(operation_type, ttl_seconds=3600, key_generator=None):
    """
    Decorator para tornar operações idempotentes
    
    Args:
        operation_type: Tipo da operação (ex: 'rdo_create', 'funcionario_edit')
        ttl_seconds: TTL da chave em segundos (padrão 1 hora)
        key_generator: Função customizada para gerar chave (opcional)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Garantir que tabela existe
            IdempotencyStore.ensure_table_exists()
            
            # Obter dados da requisição
            payload = {}
            admin_id = None
            
            if request.method in ['POST', 'PUT', 'PATCH']:
                if request.is_json:
                    payload = request.get_json() or {}
                else:
                    payload = request.form.to_dict()
            
            # Detectar admin_id do contexto
            if hasattr(g, 'current_user') and hasattr(g.current_user, 'admin_id'):
                admin_id = g.current_user.admin_id
            elif 'admin_id' in payload:
                admin_id = payload.get('admin_id')
            
            # Gerar chave idempotente
            if key_generator:
                key_hash = key_generator(operation_type, admin_id, payload, *args, **kwargs)
            else:
                # Chave padrão baseada na rota e parâmetros
                route_params = {f"arg_{i}": str(arg) for i, arg in enumerate(args)}
                route_params.update({f"kwarg_{k}": str(v) for k, v in kwargs.items()})
                key_hash = generate_key_hash(operation_type, admin_id, request.endpoint, **route_params)
            
            # Gerar hash do payload
            payload_hash = generate_payload_hash(payload)
            
            # Gerar correlation ID
            correlation_id = f"{operation_type}_{int(time.time())}_{key_hash[:8]}"
            
            logger.info(f"🔑 Operação idempotente: {operation_type} | Key: {key_hash[:8]}... | Correlation: {correlation_id}")
            
            # Verificar se chave já existe
            existing = IdempotencyStore.get_key(key_hash)
            
            if existing:
                if existing['payload_hash'] == payload_hash:
                    # Mesma operação - retornar resposta cacheada
                    if existing['status'] == 'completed' and existing['response_data']:
                        logger.info(f"✅ Operação idempotente: retornando resposta cacheada")
                        try:
                            cached_response = json.loads(existing['response_data'])
                            return cached_response
                        except:
                            # Se não conseguir deserializar, executar novamente
                            pass
                    elif existing['status'] == 'processing':
                        # Operação em andamento - retornar 409
                        logger.warning(f"⚠️ Operação em andamento para chave {key_hash[:8]}...")
                        return jsonify({
                            'error': 'Operação já em andamento',
                            'correlation_id': correlation_id
                        }), 409
                else:
                    # Mesmo identificador mas payload diferente - conflito
                    logger.warning(f"⚠️ Conflito de payload para chave {key_hash[:8]}...")
                    return jsonify({
                        'error': 'Conflito: mesma chave com payload diferente',
                        'correlation_id': correlation_id
                    }), 409
            
            # Marcar operação como em processamento
            IdempotencyStore.store_key(
                key_hash, payload_hash, 'processing', 
                ttl_seconds=ttl_seconds, admin_id=admin_id, 
                operation_type=operation_type, correlation_id=correlation_id
            )
            
            try:
                # Executar operação original
                logger.info(f"🚀 Executando operação: {operation_type}")
                result = func(*args, **kwargs)
                
                # Cacheear resposta se for JSON serializável
                response_data = None
                try:
                    if hasattr(result, 'get_json'):
                        response_data = json.dumps(result.get_json())
                    elif isinstance(result, (dict, list, str, int, bool)):
                        response_data = json.dumps(result)
                except:
                    pass
                
                # Marcar como concluída
                IdempotencyStore.store_key(
                    key_hash, payload_hash, 'completed', 
                    response_data=response_data,
                    ttl_seconds=ttl_seconds, admin_id=admin_id,
                    operation_type=operation_type, correlation_id=correlation_id
                )
                
                logger.info(f"✅ Operação concluída: {operation_type} | Correlation: {correlation_id}")
                return result
                
            except Exception as e:
                # Marcar como falhada
                IdempotencyStore.store_key(
                    key_hash, payload_hash, 'failed', 
                    response_data=json.dumps({'error': str(e)}),
                    ttl_seconds=300,  # TTL menor para falhas
                    admin_id=admin_id,
                    operation_type=operation_type, correlation_id=correlation_id
                )
                
                logger.error(f"❌ Operação falhou: {operation_type} | Error: {e} | Correlation: {correlation_id}")
                raise
                
        return wrapper
    return decorator

# Limpeza automática de chaves expiradas (executar em background)
def cleanup_expired_keys():
    """Função para limpeza periódica das chaves expiradas"""
    IdempotencyStore.cleanup_expired()

# Utilitários específicos do SIGE
def rdo_key_generator(operation_type, admin_id, payload, *args, **kwargs):
    """Gerador de chave específico para RDOs"""
    obra_id = payload.get('obra_id') or kwargs.get('obra_id')
    data_relatorio = payload.get('data_relatorio') or kwargs.get('data_relatorio')
    
    return generate_key_hash(
        operation_type, admin_id, 
        custom_key=f"rdo_{obra_id}_{data_relatorio}"
    )

def funcionario_key_generator(operation_type, admin_id, payload, *args, **kwargs):
    """Gerador de chave específico para Funcionários"""
    funcionario_id = payload.get('funcionario_id') or kwargs.get('funcionario_id') or args[0] if args else None
    data = payload.get('data') or kwargs.get('data')
    
    return generate_key_hash(
        operation_type, admin_id,
        custom_key=f"func_{funcionario_id}_{data}"
    )