# DOCKERFILE MAESTRIA DIGITAL - SIGE v10.0 - JORIS KUYPERS ARCHITECTURE
# Sistema RDO com Observabilidade Completa + Digital Mastery Principles
# "Kaipa da primeira vez certo" - Implementação robusta para produção
# Aplicação dos princípios: Robustez, Escalabilidade, Observabilidade e Manutenibilidade

# Usar imagem mais leve e segura para produção
FROM python:3.11-slim-bookworm

# Metadados Digital Mastery
LABEL maintainer="SIGE v10.0 Digital Mastery" \
      version="10.0" \
      description="Sistema RDO com Observabilidade Completa - Joris Kuypers Architecture" \
      architecture="Digital Mastery" \
      observability="Complete"

# Variáveis de build
ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_ENV=production

# Instalar dependências sistema com segurança otimizada (Digital Mastery)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL client para conexão
    postgresql-client \
    # Ferramentas de observabilidade
    curl \
    wget \
    jq \
    # Build tools mínimos
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    make \
    # Segurança e monitoramento
    ca-certificates \
    procps \
    # Cleanup automático
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Criar usuário para segurança (Digital Mastery principle)
RUN groupadd -r sige && useradd -r -g sige sige

# Definir diretório de trabalho
WORKDIR /app

# Multi-stage dependency caching (Joris principle: efficiency)
COPY pyproject.toml* setup.py* ./

# Instalar dependências Python com otimização (Digital Mastery)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Instalar dependências principais do pyproject.toml
    if [ -f pyproject.toml ]; then pip install --no-cache-dir .; fi && \
    # Cleanup pip cache
    pip cache purge

# Copiar código da aplicação (incluindo sistema de observabilidade)
COPY . .

# Criar diretórios necessários com observabilidade
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/fotos \
    /app/static/images \
    /app/uploads \
    /app/logs \
    /app/temp \
    /app/debug \
    && chown -R sige:sige /app

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente Digital Mastery (Produção Otimizada)
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    WTF_CSRF_ENABLED=false \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    # Segurança aprimorada para produção
    SHOW_DETAILED_ERRORS=false \
    # CORS controlado para produção
    CORS_ORIGINS="https://sige.cassiovilier.tech,http://localhost:5000" \
    CORS_METHODS="GET,POST,PUT,DELETE,OPTIONS" \
    SERVER_NAME=0.0.0.0:5000 \
    APPLICATION_ROOT=/ \
    PREFERRED_URL_SCHEME=https \
    # Digital Mastery flags
    DIGITAL_MASTERY_MODE=true \
    OBSERVABILITY_ENABLED=true \
    PRODUCTION_MODE=true \
    # Performance tuning
    GUNICORN_WORKERS=4 \
    GUNICORN_TIMEOUT=300 \
    GUNICORN_KEEPALIVE=65 \
    # Circuit breaker config
    CIRCUIT_BREAKER_ENABLED=true \
    RETRY_MAX_ATTEMPTS=3

# Expor porta
EXPOSE 5000

# Health check avançado com observabilidade (Joris principle: robustness)
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
  CMD curl -f http://localhost:${PORT:-5000}/health \
      --connect-timeout 10 \
      --max-time 15 \
      --retry 2 \
      --retry-delay 1 \
      --retry-max-time 30 \
      --silent \
      --show-error \
      || exit 1

# Comando de entrada com Digital Mastery (Produção Otimizada)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", \
    "--bind", "0.0.0.0:5000", \
    "--workers", "${GUNICORN_WORKERS:-4}", \
    "--worker-class", "sync", \
    "--worker-connections", "1000", \
    "--timeout", "${GUNICORN_TIMEOUT:-300}", \
    "--keepalive", "${GUNICORN_KEEPALIVE:-65}", \
    "--max-requests", "1000", \
    "--max-requests-jitter", "100", \
    "--preload", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info", \
    "--capture-output", \
    "main:app"]