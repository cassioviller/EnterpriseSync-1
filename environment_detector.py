"""
🤖 DETECÇÃO AUTOMÁTICA DE AMBIENTE SIGE v10.0
============================================
Sistema inteligente para detectar automaticamente se a aplicação está rodando em:
- EasyPanel/Hostinger (Produção)
- Desenvolvimento (Replit/Local)
- Docker/Container

Elimina necessidade de configuração manual de flags e variáveis
"""
import os
import socket
import logging
import re
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

class EnvironmentDetector:
    """
    Classe para detecção automática e inteligente de ambiente
    """
    
    def __init__(self):
        self.hostname = self._get_hostname()
        self.database_url = os.environ.get('DATABASE_URL', '')
        self.environment_vars = dict(os.environ)
        self._detection_results = None
    
    def _get_hostname(self) -> str:
        """Obter hostname do sistema"""
        try:
            return socket.gethostname()
        except Exception:
            return os.environ.get('HOSTNAME', 'unknown')
    
    def detect_environment(self) -> Dict[str, Any]:
        """
        Detecta automaticamente o ambiente com base em múltiplos fatores
        Retorna: {
            'environment': 'production'|'development'|'staging',
            'platform': 'easypanel'|'replit'|'docker'|'local',
            'auto_migrations': True|False,
            'auto_cleanup': True|False,
            'database_config': dict,
            'confidence': float (0-1)
        }
        """
        if self._detection_results:
            return self._detection_results
            
        logger.info(f"🔍 INICIANDO DETECÇÃO AUTOMÁTICA DE AMBIENTE")
        logger.info(f"🖥️ Hostname: {self.hostname}")
        logger.info(f"🔗 DATABASE_URL: {self._mask_database_url(self.database_url)}")
        
        # Inicializar resultado padrão
        result = {
            'environment': 'development',
            'platform': 'unknown',
            'auto_migrations': False,
            'auto_cleanup': False,
            'database_config': {},
            'confidence': 0.0,
            'detection_reasons': []
        }
        
        confidence_points = 0
        max_confidence = 10
        
        # DETECÇÃO 1: EasyPanel/Hostinger por hostname
        if 'viajey_sige' in self.hostname.lower():
            result['environment'] = 'production'
            result['platform'] = 'easypanel'
            result['auto_migrations'] = True
            result['auto_cleanup'] = True
            confidence_points += 4
            result['detection_reasons'].append("Hostname 'viajey_sige' detectado - EasyPanel")
            logger.info("✅ PRODUÇÃO EASYPANEL detectada por hostname")
        
        # DETECÇÃO 2: EasyPanel por características do DATABASE_URL
        elif self._is_easypanel_database():
            result['environment'] = 'production'
            result['platform'] = 'easypanel'
            result['auto_migrations'] = True
            result['auto_cleanup'] = True
            confidence_points += 3
            result['detection_reasons'].append("DATABASE_URL padrão EasyPanel detectada")
            logger.info("✅ PRODUÇÃO EASYPANEL detectada por DATABASE_URL")
        
        # DETECÇÃO 3: Desenvolvimento Replit
        elif 'neon' in self.database_url or 'localhost' in self.database_url:
            result['environment'] = 'development'
            result['platform'] = 'replit' if 'neon' in self.database_url else 'local'
            confidence_points += 3
            result['detection_reasons'].append("DATABASE_URL de desenvolvimento detectada")
            logger.info("✅ DESENVOLVIMENTO detectado por DATABASE_URL")
        
        # DETECÇÃO 4: Container/Docker por hostname formato específico
        elif re.match(r'^[a-f0-9]{12}$', self.hostname):
            result['platform'] = 'docker'
            confidence_points += 2
            result['detection_reasons'].append("Container Docker detectado por hostname")
            logger.info("🐳 Container Docker detectado")
        
        # DETECÇÃO 5: Variáveis de ambiente específicas
        env_indicators = self._check_environment_variables()
        confidence_points += env_indicators['points']
        result['detection_reasons'].extend(env_indicators['reasons'])
        
        # DETECÇÃO 6: Configurações de produção automáticas
        if result['environment'] == 'production':
            result['database_config'] = self._get_production_database_config()
            # Forçar configurações de produção
            os.environ['RUN_MIGRATIONS'] = '1'
            os.environ['RUN_CLEANUP_VEICULOS'] = '1'
            os.environ['FLASK_ENV'] = 'production'
            logger.info("🚀 Configurações de produção aplicadas automaticamente")
        
        # Calcular confiança final
        result['confidence'] = min(confidence_points / max_confidence, 1.0)
        
        # Log do resultado final
        logger.info(f"🎯 DETECÇÃO COMPLETA:")
        logger.info(f"   🌍 Ambiente: {result['environment'].upper()}")
        logger.info(f"   🖥️ Plataforma: {result['platform'].upper()}")
        logger.info(f"   🔄 Auto-migrações: {result['auto_migrations']}")
        logger.info(f"   🗑️ Auto-limpeza: {result['auto_cleanup']}")
        logger.info(f"   📊 Confiança: {result['confidence']:.1%}")
        logger.info(f"   📋 Motivos: {', '.join(result['detection_reasons'])}")
        
        self._detection_results = result
        return result
    
    def _is_easypanel_database(self) -> bool:
        """Verifica se DATABASE_URL é do padrão EasyPanel"""
        if not self.database_url:
            return False
        
        # Padrões típicos do EasyPanel/Hostinger
        easypanel_patterns = [
            r'@viajey_sige:',
            r'postgresql://sige:sige@',
            r'sslmode=disable',
            # Adicionar outros padrões conforme necessário
        ]
        
        return any(re.search(pattern, self.database_url) for pattern in easypanel_patterns)
    
    def _check_environment_variables(self) -> Dict[str, Any]:
        """Analisa variáveis de ambiente para detectar plataforma"""
        points = 0
        reasons = []
        
        # Variáveis que indicam produção
        production_vars = [
            'DIGITAL_MASTERY_MODE',
            'DEPLOYMENT_TIMESTAMP',
            'AUTO_MIGRATIONS_ENABLED'
        ]
        
        for var in production_vars:
            if self.environment_vars.get(var):
                points += 1
                reasons.append(f"Variável {var} presente")
        
        # Variáveis que indicam desenvolvimento
        dev_vars = ['REPL_ID', 'REPL_SLUG', 'REPL_OWNER']
        for var in dev_vars:
            if self.environment_vars.get(var):
                reasons.append(f"Variável de desenvolvimento {var} presente")
                # Não adicionar pontos, pois queremos detectar dev vs prod
        
        return {'points': points, 'reasons': reasons}
    
    def _get_production_database_config(self) -> Dict[str, str]:
        """Gera configuração automática de banco para produção"""
        if self.database_url:
            return {'url': self.database_url}
        
        # Configuração padrão EasyPanel se não houver DATABASE_URL
        default_config = {
            'url': 'postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable',
            'host': 'viajey_sige',
            'port': '5432',
            'database': 'sige',
            'user': 'sige',
            'ssl_mode': 'disable'
        }
        
        logger.info("🔧 Usando configuração padrão EasyPanel")
        return default_config
    
    def _mask_database_url(self, url: str) -> str:
        """Mascara credenciais em URLs de banco para logs seguros"""
        if not url:
            return "None"
        # Mascarar senha: user:password@host -> user:****@host
        masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
        return masked
    
    def should_run_migrations(self) -> bool:
        """Determina se deve executar migrações automaticamente"""
        result = self.detect_environment()
        return result['auto_migrations']
    
    def should_run_cleanup(self) -> bool:
        """Determina se deve executar limpeza automaticamente"""
        result = self.detect_environment()
        return result['auto_cleanup']
    
    def get_database_url(self) -> str:
        """Retorna DATABASE_URL configurada automaticamente"""
        result = self.detect_environment()
        
        if result['environment'] == 'production' and not self.database_url:
            # Auto-configurar para EasyPanel
            auto_url = result['database_config']['url']
            os.environ['DATABASE_URL'] = auto_url
            logger.info("🔧 DATABASE_URL configurada automaticamente para produção")
            return auto_url
        
        return self.database_url


# Instância global do detector
detector = EnvironmentDetector()


def get_environment_info() -> Dict[str, Any]:
    """
    Função conveniente para obter informações do ambiente
    """
    return detector.detect_environment()


def is_production() -> bool:
    """
    Função conveniente para verificar se está em produção
    """
    return detector.detect_environment()['environment'] == 'production'


def is_development() -> bool:
    """
    Função conveniente para verificar se está em desenvolvimento  
    """
    return detector.detect_environment()['environment'] == 'development'


def auto_configure_environment():
    """
    Configura automaticamente variáveis de ambiente baseado na detecção
    """
    env_info = detector.detect_environment()
    
    if env_info['environment'] == 'production':
        # Configurar automaticamente para produção
        os.environ['RUN_MIGRATIONS'] = '1'
        os.environ['RUN_CLEANUP_VEICULOS'] = '1'
        os.environ['FLASK_ENV'] = 'production'
        os.environ['DIGITAL_MASTERY_MODE'] = 'true'
        
        # Configurar DATABASE_URL se necessário
        if not os.environ.get('DATABASE_URL') and env_info['database_config'].get('url'):
            os.environ['DATABASE_URL'] = env_info['database_config']['url']
            
        logger.info("🚀 Ambiente de produção configurado automaticamente")
        
    else:
        logger.info("🔧 Ambiente de desenvolvimento mantido")
    
    return env_info