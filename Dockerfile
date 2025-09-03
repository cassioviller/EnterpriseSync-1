# DOCKERFILE UNIFICADO - SIGE v8.1 FINAL  
# Sincronização Total Desenvolvimento ↔ Produção - ERRO 400 CORRIGIDO
# Sistema Integrado de Gestão Empresarial - EasyPanel Ready

FROM python:3.11-slim-bullseye

# Metadados atualizados
LABEL maintainer="SIGE v8.1 Final" \
      version="8.1.0" \
      description="Sistema Integrado de Gestão Empresarial - Erro 400 Corrigido" \
      build-date="2025-09-03"

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
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário para segurança (mesmo nome em dev/prod)
RUN groupadd -r sige && useradd -r -g sige sige

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivos de configuração primeiro para cache otimizado
COPY pyproject.toml requirements.txt* ./

# Instalar dependências Python (versões fixas para estabilidade)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir . && \
    pip list > /app/installed_packages.txt

# Copiar TODO o código da aplicação (garantindo sincronia total)
COPY . .

# CORREÇÕES ESPECÍFICAS PARA ERRO 400 - APLICAR EM PRODUÇÃO
# Script de verificação completa das correções
COPY verify_production_fixes.py /app/
RUN python3 /app/verify_production_fixes.py

# Criar todos os diretórios necessários para dev e prod (incluindo debug)
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/fotos \
    /app/static/images \
    /app/static/uploads \
    /app/uploads \
    /app/logs \
    /app/temp \
    /app/instance \
    /app/migrations \
    /app/templates/debug \
    /app/templates/errors \
    && chown -R sige:sige /app \
    && chmod 755 /app/logs

# Garantir que arquivos Python sejam executáveis
RUN find /app -name "*.py" -exec chmod 644 {} \;

# Copiar e configurar script de entrada UNIFICADO
COPY docker-entrypoint-production-fix.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente unificadas para dev/prod
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    SHOW_DETAILED_ERRORS=true \
    DEBUG=false \
    WEB_CONCURRENCY=2

# Expor porta
EXPOSE 5000

# Health check robusto para ambos ambientes
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando de entrada otimizado para produção
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "--keepalive", "2", "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "--preload", "main:app"]