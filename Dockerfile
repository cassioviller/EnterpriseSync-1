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

# Criar script de verificação melhorado para EasyPanel com tratamento de PostgreSQL
RUN printf '#!/bin/bash\nset -e\n\necho "🚀 INICIANDO SIGE v9.0 - Sistema Integrado de Gestão Empresarial"\necho "🎯 Deploy EasyPanel - Verificação completa com PostgreSQL"\necho "================================================================="\n\n' > /app/docker-entrypoint.sh && \
    printf '# Aguardar PostgreSQL estar disponível\necho "🔄 Aguardando PostgreSQL..."\nfor i in {1..30}; do\n    if pg_isready -h ${DATABASE_HOST:-viajey_sige} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-sige} > /dev/null 2>&1; then\n        echo "✅ PostgreSQL conectado!"\n        break\n    fi\n    echo "⏳ Tentativa $i/30 - aguardando PostgreSQL..."\n    sleep 2\ndone\n\n' >> /app/docker-entrypoint.sh && \
    printf 'echo "🔄 Executando verificações e migrações..."\npython -c "\nimport os\nos.environ.setdefault(\\"DATABASE_URL\\", \\"postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable\\")\nfrom app import app\nimport logging\nlogging.basicConfig(level=logging.INFO)\nwith app.app_context():\n    try:\n        from models import db\n        db.create_all()\n        print(\\"✅ Tabelas verificadas/criadas!\\")\n    except Exception as e:\n        print(f\\"⚠️ Erro nas tabelas: {e}\\")\n    try:\n        from migrations import executar_migracoes\n        executar_migracoes()\n        print(\\"✅ Migrações concluídas!\\")\n    except Exception as e:\n        print(f\\"⚠️ Erro nas migrações: {e}\\")\n"\n\n' >> /app/docker-entrypoint.sh && \
    printf 'echo "✅ SIGE v9.0 pronto para execução!"\necho "================================================================"\n\nexec "$@"\n' >> /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

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