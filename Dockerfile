# DOCKERFILE PRODUÇÃO - SIGE v8.0
# Sistema Integrado de Gestão Empresarial
# Otimizado para Hostinger EasyPanel

FROM python:3.11-slim-buster

# Metadados
LABEL maintainer="SIGE v8.0" \
      version="8.0" \
      description="Sistema Integrado de Gestão Empresarial"

# Variáveis de build
ARG DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Criar usuário não-root para segurança
RUN groupadd -r sige && useradd -r -g sige sige

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências primeiro (otimização de cache)
COPY pyproject.toml ./

# Gerar requirements.txt e instalar dependências
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p /app/static/fotos /app/logs && \
    chown -R sige:sige /app

# Copiar script de entrada
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Mudar para usuário não-root
USER sige

# Variáveis de ambiente
ENV FLASK_ENV=production \
    DATABASE_URL=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable \
    SECRET_KEY=sige-v8-production-secret-key-change-in-production \
    SESSION_SECRET=sige-v8-session-secret-change-in-production \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Expor porta
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/monitoring/health || exit 1

# Comando de entrada
ENTRYPOINT ["/app/docker-entrypoint.sh"]