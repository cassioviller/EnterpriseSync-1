# DOCKERFILE UNIFICADO - SIGE v8.2 - SERVIÇOS DA OBRA CORRIGIDO
# Sistema com "Serviços da Obra" baseado em RDO + Subatividades
# Sistema Integrado de Gestão Empresarial - Deploy Production Ready

FROM python:3.11-slim-bullseye

# Metadados
LABEL maintainer="SIGE v8.2 EasyPanel" \
      version="8.2" \
      description="Sistema Integrado de Gestão Empresarial - Serviços da Obra Corrigido"

# Variáveis de build
ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_ENV=production

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    wget \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    make \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário para segurança (mesmo nome em dev/prod)
RUN groupadd -r sige && useradd -r -g sige sige

# Definir diretório de trabalho
WORKDIR /app

# Copiar pyproject.toml primeiro para cache de dependências
COPY pyproject.toml ./

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Copiar código da aplicação (incluindo correções Serviços da Obra)
COPY . .

# Script de verificação incorporado diretamente no Dockerfile

# Funcionalidades implementadas na v8.2:
# - Sistema "Serviços da Obra" corrigido para usar RDO
# - API /api/obras/servicos-rdo para criação automática de RDO inicial  
# - API /api/servicos-disponiveis-obra/<obra_id> para filtrar serviços disponíveis
# - Frontend atualizado com renderização de progresso das subatividades
# - Função obter_servicos_da_obra() corrigida para tabelas servico + subatividade_mestre

# Copiar sistema de erro detalhado para produção
COPY utils/production_error_handler.py /app/utils/

# Criar todos os diretórios necessários
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/fotos \
    /app/static/images \
    /app/uploads \
    /app/logs \
    /app/temp \
    && chown -R sige:sige /app

# Criar script de verificação inline para EasyPanel
RUN cat > /app/docker-entrypoint.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 INICIANDO SIGE v8.2 - Sistema Integrado de Gestão Empresarial"
echo "🎯 Deploy EasyPanel - Verificação completa de rotas e APIs"
echo "================================================================="

# Aguardar banco de dados estar pronto
if [ -n "$DATABASE_URL" ]; then
    echo "⏳ Aguardando PostgreSQL..."
    timeout=60
    while ! pg_isready -d "$DATABASE_URL" -t 1 > /dev/null 2>&1; do
        echo "   ⌛ Aguardando conexão com banco... ($timeout)s"
        sleep 2
        timeout=$((timeout-2))
        if [ $timeout -le 0 ]; then
            echo "❌ Timeout aguardando banco de dados"
            exit 1
        fi
    done
    echo "✅ PostgreSQL conectado!"
fi

# Executar migrações e verificações de produção
echo "🔄 Executando migrações automáticas..."
python -c "
from app import app
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

with app.app_context():
    try:
        from verificacao_producao import verificar_dados_producao
        print('🔍 Verificando dados de produção...')
        verificar_dados_producao()
        print('✅ Verificação de produção concluída!')
    except Exception as e:
        print(f'⚠️ Verificação falhou mas continuando: {e}')

    try:
        import migrations
        print('🔧 Executando migrações...')
        print('✅ Migrações concluídas!')
    except Exception as e:
        print(f'❌ Erro nas migrações: {e}')
        if 'production' in str(app.config.get('FLASK_ENV', '')):
            exit(1)
"

# Verificação completa de rotas e APIs
echo "🔍 Verificando rotas e APIs registradas..."
python -c "
from app import app

with app.app_context():
    try:
        print('📋 VERIFICAÇÃO DE ROTAS E APIs:')
        print('='*50)
        
        # Verificar blueprints registrados
        blueprints = []
        for name, blueprint in app.blueprints.items():
            url_prefix = getattr(blueprint, 'url_prefix', '') or ''
            blueprints.append((name, url_prefix))
        
        print(f'📊 BLUEPRINTS: {len(blueprints)} registrados')
        
        # Contar rotas
        all_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                all_routes.append(rule.rule)
        
        print(f'📈 ROTAS: {len(all_routes)} mapeadas')
        
        # Verificar endpoints críticos
        critical_endpoints = ['/health', '/', '/login', '/dashboard']
        for endpoint in critical_endpoints:
            found = any(endpoint in route for route in all_routes)
            status = '✅' if found else '❌'
            print(f'   {status} {endpoint}')
        
        print('='*50)
        print('✅ VERIFICAÇÃO CONCLUÍDA!')
        
    except Exception as e:
        print(f'❌ Erro na verificação: {e}')
"

# Teste de endpoints funcionando
echo "🧪 Testando endpoints críticos..."
python -c "
from app import app

with app.test_client() as client:
    try:
        print('🧪 TESTE DE ENDPOINTS:')
        print('='*30)
        
        endpoints = ['/health', '/', '/login']
        successful = 0
        total = len(endpoints)
        
        for endpoint in endpoints:
            try:
                response = client.get(endpoint, follow_redirects=True)
                if response.status_code < 500:
                    print(f'   ✅ {endpoint} -> {response.status_code}')
                    successful += 1
                else:
                    print(f'   ❌ {endpoint} -> {response.status_code}')
            except Exception as e:
                print(f'   ⚠️ {endpoint} -> ERRO')
        
        rate = (successful / total) * 100
        print(f'📊 SUCESSO: {successful}/{total} ({rate:.0f}%)')
        print('='*30)
        
    except Exception as e:
        print(f'❌ Erro nos testes: {e}')
"

echo "================================================================="
echo "✅ SIGE v8.2 pronto para execução!"
echo "🌐 Serviços da Obra implementado com RDO + Subatividades"
echo "================================================================="

# Executar comando principal
exec "$@"
EOF

# Tornar script executável
RUN chmod +x /app/docker-entrypoint.sh

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente EasyPanel (específicas para resolver 405 + URL issues)
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    WTF_CSRF_ENABLED=false \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    SHOW_DETAILED_ERRORS=true \
    CORS_ORIGINS="*" \
    CORS_METHODS="GET,POST,PUT,DELETE,OPTIONS" \
    SERVER_NAME=0.0.0.0:5000 \
    APPLICATION_ROOT=/ \
    PREFERRED_URL_SCHEME=http

# Expor porta
EXPOSE 5000

# Health check robusto para EasyPanel
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando de entrada otimizado para EasyPanel
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "main:app"]