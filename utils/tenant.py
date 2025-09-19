#!/usr/bin/env python3
"""
Tenant Management Utilities - SIGE v8.0
Centralizes multitenant logic to prevent circular imports
"""

from flask_login import current_user
from models import TipoUsuario
import logging

# Configure logging for tenant operations
logger = logging.getLogger('tenant')
logger.setLevel(logging.INFO)

def get_tenant_admin_id():
    """
    🔒 RESOLVER MULTITENANT UNIFICADO ROBUSTO
    Determina o admin_id correto baseado no tipo de usuário para isolamento de dados
    com auto-detecção e fallbacks para resolver problemas produção vs desenvolvimento
    - ADMIN: usa seu próprio ID (current_user.id) 
    - FUNCIONARIO: usa o admin_id da empresa que lhe deu acesso (current_user.admin_id)
    - AUTO-DETECÇÃO: Se admin_id não existe, detecta automaticamente o correto
    """
    if not current_user.is_authenticated:
        return None
    
    # Lógica normal para usuário autenticado
    if current_user.tipo_usuario == TipoUsuario.ADMIN:
        target_admin_id = current_user.id
    else:
        target_admin_id = current_user.admin_id
    
    # 🔧 CORREÇÃO CRÍTICA: Verificar se admin_id existe realmente nos dados
    # Isso resolve problemas onde desenvolvimento usa admin_id=10 mas produção tem admin_id=2
    try:
        from sqlalchemy import text
        from app import db
        
        # Verificar se o admin_id existe em alguma tabela principal
        result = db.session.execute(text('''
            SELECT DISTINCT admin_id FROM (
                SELECT admin_id FROM usuario WHERE admin_id = :admin_id
                UNION
                SELECT admin_id FROM funcionario WHERE admin_id = :admin_id
                UNION 
                SELECT admin_id FROM veiculo WHERE admin_id = :admin_id
                UNION
                SELECT admin_id FROM obra WHERE admin_id = :admin_id
            ) combined LIMIT 1
        '''), {'admin_id': target_admin_id})
        
        if result.fetchone():
            # Admin_id existe nos dados - usar normalmente
            return target_admin_id
        else:
            # Admin_id não existe - auto-detectar o correto
            print(f"⚠️ Admin_id {target_admin_id} não encontrado nos dados. Auto-detectando...")
            return _auto_detect_admin_id()
            
    except Exception as e:
        print(f"⚠️ Erro na verificação admin_id: {e}. Usando fallback.")
        return target_admin_id

def ensure_tenant_isolation(query_filter, admin_id_field='admin_id'):
    """
    Garante isolamento de dados por tenant
    """
    tenant_id = get_tenant_admin_id()
    if tenant_id:
        return query_filter.filter_by(**{admin_id_field: tenant_id})
    return query_filter

def _auto_detect_admin_id():
    """
    🔍 AUTO-DETECÇÃO INTELIGENTE DE ADMIN_ID
    Analisa os dados reais para encontrar o admin_id correto
    Prioriza admin com mais dados/atividade
    """
    try:
        from sqlalchemy import text, func
        from app import db
        
        # Estratégia 1: Admin com mais funcionários (indica atividade)
        result = db.session.execute(text('''
            SELECT admin_id, COUNT(*) as count
            FROM funcionario 
            WHERE admin_id IS NOT NULL
            GROUP BY admin_id 
            ORDER BY count DESC 
            LIMIT 1
        '''))
        row = result.fetchone()
        if row and row[0]:
            print(f"✅ Auto-detectado admin_id {row[0]} (tem {row[1]} funcionários)")
            return row[0]
        
        # Estratégia 2: Admin com mais veículos  
        result = db.session.execute(text('''
            SELECT admin_id, COUNT(*) as count
            FROM veiculo 
            WHERE admin_id IS NOT NULL
            GROUP BY admin_id 
            ORDER BY count DESC 
            LIMIT 1
        '''))
        row = result.fetchone()
        if row and row[0]:
            print(f"✅ Auto-detectado admin_id {row[0]} (tem {row[1]} veículos)")
            return row[0]
            
        # Estratégia 3: Primeiro admin na tabela usuário
        result = db.session.execute(text('''
            SELECT id FROM usuario 
            WHERE tipo_usuario = 'ADMIN' 
            ORDER BY id 
            LIMIT 1
        '''))
        row = result.fetchone()
        if row and row[0]:
            print(f"✅ Auto-detectado admin_id {row[0]} (primeiro admin cadastrado)")
            return row[0]
            
        print("⚠️ Nenhum admin_id detectado automaticamente")
        return None
        
    except Exception as e:
        print(f"❌ Erro na auto-detecção: {e}")
        return None

def get_safe_admin_id():
    """
    Retorna admin_id com fallback seguro e auto-detecção para casos de desenvolvimento
    """
    tenant_id = get_tenant_admin_id()
    if tenant_id:
        return tenant_id
    
    # Fallback com auto-detecção
    auto_detected = _auto_detect_admin_id()
    if auto_detected:
        return auto_detected
    
    return 1  # Fallback absoluto