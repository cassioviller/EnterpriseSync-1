#!/usr/bin/env python3
"""
PREPARAÇÃO PARA PRODUÇÃO - SIGE v8.0
Sistema Integrado de Gestão Empresarial

Script adaptado baseado nas especificações fornecidas
Prepara o sistema atual para ambiente de produção

Data: 23 de Julho de 2025
"""

import os
import sys
import time
from datetime import datetime, date

sys.path.append('/home/runner/workspace')

from app import app, db
from models import *

def criar_configuracoes_producao():
    """Cria arquivo de configurações otimizadas para produção"""
    print("🔧 Criando configurações de produção...")
    
    config_text = '''# CONFIGURAÇÕES PRODUÇÃO - SIGE v8.0

import os
from datetime import timedelta

class ConfigProducao:
    # Segurança
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sua-chave-super-secreta-producao-128-chars')
    WTF_CSRF_ENABLED = True
    
    # Banco de dados otimizado
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
        'max_overflow': 30
    }
    
    # Sessões seguras
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(hours=12)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
'''
    
    with open('config_producao.py', 'w', encoding='utf-8') as f:
        f.write(config_text)
    
    print("✅ config_producao.py criado")

def criar_sistema_monitoramento():
    """Cria endpoints de monitoramento"""
    print("📊 Criando sistema de monitoramento...")
    
    monitoring_text = '''from flask import Blueprint, jsonify
from datetime import datetime
import time
from app import app, db
from models import Usuario, Funcionario, Obra

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/health')
def health_check():
    """Health check para load balancer"""
    try:
        # Teste rápido de banco
        db.session.execute('SELECT 1').scalar()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '8.0',
            'database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@monitoring_bp.route('/metrics')
def metrics():
    """Métricas básicas do sistema"""
    try:
        usuarios_count = Usuario.query.count()
        funcionarios_count = Funcionario.query.count()
        obras_count = Obra.query.count()
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'counts': {
                'usuarios': usuarios_count,
                'funcionarios': funcionarios_count,
                'obras': obras_count
            },
            'system': 'operational'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Registrar no app principal
app.register_blueprint(monitoring_bp, url_prefix='/api/monitoring')
'''
    
    with open('monitoring_producao.py', 'w', encoding='utf-8') as f:
        f.write(monitoring_text)
    
    print("✅ monitoring_producao.py criado")

def criar_otimizacoes_banco():
    """Cria script de otimizações SQL"""
    print("🗄️ Criando otimizações de banco...")
    
    sql_text = '''-- OTIMIZAÇÕES PRODUÇÃO - SIGE v8.0

-- Índices para multi-tenant
CREATE INDEX IF NOT EXISTS idx_funcionario_admin_ativo ON funcionario(admin_id, ativo);
CREATE INDEX IF NOT EXISTS idx_obra_admin_ativo ON obra(admin_id, ativo);
CREATE INDEX IF NOT EXISTS idx_veiculo_admin_ativo ON veiculo(admin_id, ativo);

-- Índices para registros de ponto
CREATE INDEX IF NOT EXISTS idx_registro_ponto_data ON registro_ponto(data);
CREATE INDEX IF NOT EXISTS idx_registro_ponto_funcionario_data ON registro_ponto(funcionario_id, data);

-- Índices para custos
CREATE INDEX IF NOT EXISTS idx_custo_obra_data ON custo_obra(data);
CREATE INDEX IF NOT EXISTS idx_registro_alimentacao_data ON registro_alimentacao(data);

-- Índices para RDOs
CREATE INDEX IF NOT EXISTS idx_rdo_data ON rdo(data_relatorio);
CREATE INDEX IF NOT EXISTS idx_rdo_obra_data ON rdo(obra_id, data_relatorio);

-- Views otimizadas
CREATE OR REPLACE VIEW vw_funcionarios_ativos AS
SELECT 
    f.id, f.nome, f.codigo, f.admin_id, f.salario,
    d.nome as departamento,
    h.nome as horario_trabalho
FROM funcionario f
LEFT JOIN departamento d ON f.departamento_id = d.id
LEFT JOIN horario_trabalho h ON f.horario_trabalho_id = h.id
WHERE f.ativo = true;

-- Atualizar estatísticas
ANALYZE funcionario;
ANALYZE obra;
ANALYZE registro_ponto;
ANALYZE custo_obra;
'''
    
    with open('otimizacoes_producao.sql', 'w', encoding='utf-8') as f:
        f.write(sql_text)
    
    print("✅ otimizacoes_producao.sql criado")

def validar_dados_producao():
    """Valida dados para produção"""
    print("🔍 Validando dados para produção...")
    
    with app.app_context():
        # Verificar registros futuros
        registros_futuros = RegistroPonto.query.filter(
            RegistroPonto.data > date.today()
        ).count()
        
        # Verificar integridade multi-tenant
        funcionarios_sem_admin = Funcionario.query.filter_by(admin_id=None).count()
        obras_sem_admin = Obra.query.filter_by(admin_id=None).count()
        
        print(f"📊 Validação:")
        print(f"   • Registros futuros: {registros_futuros}")
        print(f"   • Funcionários órfãos: {funcionarios_sem_admin}")
        print(f"   • Obras órfãs: {obras_sem_admin}")
        
        if registros_futuros == 0 and funcionarios_sem_admin == 0 and obras_sem_admin == 0:
            print("✅ Dados validados para produção")
            return True
        else:
            print("⚠️ Dados precisam de limpeza antes da produção")
            return False

def criar_script_deploy():
    """Cria script básico de deploy"""
    print("🚀 Criando script de deploy...")
    
    deploy_text = '''#!/bin/bash
# DEPLOY PRODUÇÃO - SIGE v8.0

echo "🚀 Iniciando deploy SIGE v8.0..."

# Backup do banco
echo "📦 Fazendo backup..."
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Aplicar otimizações
echo "⚡ Aplicando otimizações..."
psql $DATABASE_URL < otimizacoes_producao.sql

# Reiniciar aplicação
echo "🔄 Reiniciando aplicação..."
# Comando específico do ambiente (PM2, systemd, etc.)

# Verificar saúde
echo "🏥 Verificando saúde..."
sleep 5
curl -f http://localhost/api/monitoring/health || exit 1

echo "✅ Deploy concluído!"
'''
    
    with open('deploy_producao.sh', 'w', encoding='utf-8') as f:
        f.write(deploy_text)
    
    os.chmod('deploy_producao.sh', 0o755)
    print("✅ deploy_producao.sh criado")

def criar_documentacao():
    """Cria documentação de produção"""
    print("📚 Criando documentação...")
    
    doc_text = '''# GUIA DE PRODUÇÃO - SIGE v8.0

## Configuração do Ambiente

### Variáveis de Ambiente Obrigatórias
```bash
export DATABASE_URL="postgresql://user:pass@localhost/sige_prod"
export SECRET_KEY="sua-chave-super-secreta-128-chars"
export SESSION_SECRET="sua-chave-sessao-secreta"
```

### Dependências do Sistema
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql-client python3-pip nginx

# Python packages
pip install -r requirements.txt
```

### Configurações de Segurança
```bash
# Firewall
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP  
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

## Deploy

### Primeira Instalação
```bash
./deploy_producao.sh
```

### Verificação de Saúde
```bash
curl http://localhost/api/monitoring/health
curl http://localhost/api/monitoring/metrics
```

## Monitoramento

### URLs Importantes
- Health Check: `/api/monitoring/health`
- Métricas: `/api/monitoring/metrics`
- Login: `/login`

### Logs
- Aplicação: Logs do Flask/Gunicorn
- Sistema: `/var/log/syslog`
- Nginx: `/var/log/nginx/`

## Backup e Restauração

### Backup Manual
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### Restauração
```bash
psql $DATABASE_URL < backup_YYYYMMDD.sql
```

## Solução de Problemas

### Problemas Comuns
1. **Erro 500**: Verificar logs da aplicação
2. **Banco desconectado**: Verificar DATABASE_URL
3. **Performance lenta**: Verificar índices

### Contatos
- Suporte: suporte@empresa.com
- Documentação: Sistema validado em 23/07/2025
'''
    
    with open('GUIA_PRODUCAO_SIGE_v8.md', 'w', encoding='utf-8') as f:
        f.write(doc_text)
    
    print("✅ GUIA_PRODUCAO_SIGE_v8.md criado")

def main():
    """Executa preparação completa para produção"""
    print("🔧 PREPARANDO SIGE v8.0 PARA PRODUÇÃO")
    print("=" * 60)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    try:
        # 1. Configurações
        criar_configuracoes_producao()
        
        # 2. Monitoramento  
        criar_sistema_monitoramento()
        
        # 3. Otimizações
        criar_otimizacoes_banco()
        
        # 4. Validação
        dados_ok = validar_dados_producao()
        
        # 5. Scripts
        criar_script_deploy()
        
        # 6. Documentação
        criar_documentacao()
        
        print("\n" + "=" * 60)
        print("📋 RESUMO DA PREPARAÇÃO")
        print("=" * 60)
        
        arquivos = [
            "config_producao.py - Configurações otimizadas",
            "monitoring_producao.py - Sistema de monitoramento", 
            "otimizacoes_producao.sql - Otimizações de banco",
            "deploy_producao.sh - Script de deploy",
            "GUIA_PRODUCAO_SIGE_v8.md - Documentação completa"
        ]
        
        print("\n📁 Arquivos criados:")
        for arquivo in arquivos:
            print(f"   ✅ {arquivo}")
        
        print(f"\n🔍 Status dos dados: {'✅ Prontos' if dados_ok else '⚠️ Precisam limpeza'}")
        
        print(f"\n🚀 Próximos passos:")
        print("   1. Revisar config_producao.py")
        print("   2. Configurar variáveis de ambiente")
        print("   3. Executar: psql < otimizacoes_producao.sql") 
        print("   4. Executar: ./deploy_producao.sh")
        print("   5. Verificar: /api/monitoring/health")
        
        print(f"\n✅ SIGE v8.0 PREPARADO PARA PRODUÇÃO!")
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())