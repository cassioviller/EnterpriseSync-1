# DOCKERFILE PRODUÇÃO - SIGE v8.0
# Sistema Integrado de Gestão Empresarial
# Otimizado para Hostinger EasyPanel

FROM python:3.11-slim-bullseye

# Metadados
LABEL maintainer="SIGE v8.0" \
      version="8.0" \
      description="Sistema Integrado de Gestão Empresarial"

# Variáveis de build
ARG DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    gcc \
    python3-dev \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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

# Variáveis de ambiente (não-sensíveis)
ENV FLASK_ENV=production \
    PORT=5000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Expor porta
EXPOSE 5000

# Comando de entrada
ENTRYPOINT ["/app/docker-entrypoint.sh"]