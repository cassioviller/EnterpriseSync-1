# DOCKERFILE PRODUÇÃO - SIGE v9.0
# Sistema de Gestão Empresarial - Limpo e Otimizado

FROM python:3.11-slim-bullseye

# Metadados
LABEL maintainer="SIGE v9.0" \
      version="9.0.0" \
      description="Sistema de Gestão Empresarial - Produção" \
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

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/uploads \
    /app/logs \
    && chown -R sige:sige /app

# Garantir que arquivos Python sejam executáveis
RUN find /app -name "*.py" -exec chmod 644 {} \;

# Script de entrada otimizado
COPY docker-entrypoint-v8.3-final.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    DEBUG=false

# Expor porta
EXPOSE 5000

# Health check robusto para ambos ambientes
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Comando de entrada otimizado para produção
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "--keepalive", "2", "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "--preload", "main:app"]