# DOCKERFILE SIGE v10.0 - DIGITAL MASTERY PRODUCTION
# Otimizado para EasyPanel/Hostinger - Joris Kuypers Architecture
# Data: 2025-09-08 - Versão: 10.0.1

FROM python:3.11-slim

# Metadata
LABEL maintainer="Cassio Viller <cassio@sige.tech>"
LABEL version="10.0.1"
LABEL description="SIGE Digital Mastery - Sistema Integrado de Gestão Empresarial"

# Variáveis de ambiente para produção
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production
ENV FLASK_APP=app.py
ENV DIGITAL_MASTERY_MODE=true
ENV OBSERVABILITY_ENABLED=true
ENV LOG_LEVEL=INFO

# Configurações de timezone
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    wget \
    git \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root para segurança
RUN useradd --create-home --shell /bin/bash sige

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências primeiro (para cache do Docker)
COPY pyproject.toml ./
COPY requirements.txt* ./

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]