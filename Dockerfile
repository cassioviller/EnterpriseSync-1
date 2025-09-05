# DOCKERFILE MAESTRIA DIGITAL - SIGE v10.0 - JORIS KUYPERS ARCHITECTURE
# Sistema RDO com Observabilidade Completa + Digital Mastery Principles
# "Kaipa da primeira vez certo" - Implementação robusta para produção

FROM python:3.11-slim-bullseye

# Metadados Digital Mastery
LABEL maintainer="SIGE v10.0 Digital Mastery" \
      version="10.0" \
      description="Sistema RDO com Observabilidade Completa - Joris Kuypers Architecture" \
      architecture="Digital Mastery" \
      observability="Complete"

# Variáveis de build
ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_ENV=production

# Instalar dependências sistema + observabilidade
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
    jq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário para segurança (Digital Mastery principle)
RUN groupadd -r sige && useradd -r -g sige sige

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro para cache de dependências
COPY pyproject.toml ./

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

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

# Variáveis de ambiente Digital Mastery
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
    PREFERRED_URL_SCHEME=http \
    DIGITAL_MASTERY_MODE=true \
    OBSERVABILITY_ENABLED=true

# Expor porta
EXPOSE 5000

# Health check com observabilidade
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando de entrada com Digital Mastery
ENTRYPOINT ["/app/docker-entrypoint-digital-mastery.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "main:app"]