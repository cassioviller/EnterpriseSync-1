"""
SIGE - Módulo de Funções Auxiliares
==================================
Funções compartilhadas entre diferentes módulos do sistema
"""

import logging
from flask_login import current_user as flask_current_user
from typing import Optional, Any

logger = logging.getLogger(__name__)

def get_admin_id_robusta(obra=None, current_user=None):
    """Sistema robusto de detecção de admin_id - PRIORIDADE TOTAL AO USUÁRIO LOGADO"""
    try:
        # IMPORTAR current_user se não fornecido
        if current_user is None:
            current_user = flask_current_user
        
        # ⚡ PRIORIDADE 1: USUÁRIO LOGADO (SEMPRE PRIMEIRO!)
        if current_user and current_user.is_authenticated:
            # Se é ADMIN, usar seu próprio ID
            from models import TipoUsuario
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                logger.info(f"🔒 ADMIN LOGADO: admin_id={current_user.id}")
                return current_user.id
            
            # Se é funcionário, usar admin_id
            elif hasattr(current_user, 'admin_id') and current_user.admin_id:
                logger.info(f"🔒 FUNCIONÁRIO LOGADO: admin_id={current_user.admin_id}")
                return current_user.admin_id
            
            # Fallback para ID do usuário
            elif hasattr(current_user, 'id') and current_user.id:
                logger.info(f"🔒 USUÁRIO GENÉRICO LOGADO: admin_id={current_user.id}")
                return current_user.id
        
        # ⚡ PRIORIDADE 2: Se obra tem admin_id específico
        if obra and hasattr(obra, 'admin_id') and obra.admin_id:
            logger.info(f"🎯 Admin_ID da obra: {obra.admin_id}")
            return obra.admin_id
        
        # ⚠️ SEM USUÁRIO LOGADO: ERRO CRÍTICO DE SEGURANÇA
        logger.error("❌ ERRO CRÍTICO: Nenhum usuário autenticado encontrado!")
        logger.error("❌ Sistema multi-tenant requer usuário logado OBRIGATORIAMENTE")
        logger.error("❌ Não é permitido detecção automática de admin_id")
        return None
        
    except Exception as e:
        logger.error(f"ERRO CRÍTICO get_admin_id_robusta: {e}")
        return 1  # Fallback de produção

def verificar_dados_producao(admin_id: int) -> bool:
    """Verifica se admin_id tem dados suficientes para funcionar em produção"""
    try:
        from models import db
        from sqlalchemy import text
        
        # Verificar se tem funcionários
        funcionarios = db.session.execute(text(
            "SELECT COUNT(*) FROM funcionario WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        # Verificar se tem serviços
        servicos = db.session.execute(text(
            "SELECT COUNT(*) FROM servico WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        # Verificar se tem subatividades
        subatividades = db.session.execute(text(
            "SELECT COUNT(*) FROM subatividade_mestre WHERE admin_id = :admin_id AND ativo = true"
        ), {'admin_id': admin_id}).scalar()
        
        # Verificar se tem obras
        obras = db.session.execute(text(
            "SELECT COUNT(*) FROM obra WHERE admin_id = :admin_id"
        ), {'admin_id': admin_id}).scalar()
        
        logger.info(f"📊 VERIFICAÇÃO PRODUÇÃO admin_id {admin_id}: {funcionarios} funcionários, {servicos} serviços, {subatividades} subatividades, {obras} obras")
        
        # Considerar válido se tem pelo menos serviços OU funcionários OU obras
        is_valid = funcionarios > 0 or servicos > 0 or obras > 0
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Erro ao verificar dados de produção para admin_id {admin_id}: {e}")
        return False

def get_tenant_admin_id():
    """Wrapper para compatibilidade com utils.tenant"""
    return get_admin_id_robusta()

def mask_database_url(url: str) -> str:
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    import re
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

def format_currency(value: float) -> str:
    """Formata valor monetário para exibição"""
    if value is None:
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def validate_cpf(cpf: str) -> bool:
    """Valida CPF brasileiro"""
    if not cpf:
        return False
        
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Valida primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    if resto < 2:
        digito1 = 0
    else:
        digito1 = 11 - resto
    
    if int(cpf[9]) != digito1:
        return False
    
    # Valida segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    if resto < 2:
        digito2 = 0
    else:
        digito2 = 11 - resto
    
    return int(cpf[10]) == digito2

def validate_cnpj(cnpj: str) -> bool:
    """Valida CNPJ brasileiro"""
    if not cnpj:
        return False
        
    # Remove caracteres não numéricos
    cnpj = ''.join(filter(str.isdigit, cnpj))
    
    if len(cnpj) != 14:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cnpj == cnpj[0] * 14:
        return False
    
    # Valida primeiro dígito verificador
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cnpj[12]) != digito1:
        return False
    
    # Valida segundo dígito verificador
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    return int(cnpj[13]) == digito2