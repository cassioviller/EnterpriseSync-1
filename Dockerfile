# SIGE v10.0 - Dockerfile Otimizado para Produção EasyPanel
# Versão simplificada para deploy rápido e confiável
FROM python:3.11-slim

# Variáveis de ambiente básicas
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production
ENV PORT=5000
ENV DIGITAL_MASTERY_MODE=true

# Instalar dependências do sistema (mínimas)
# Fase 0.5 / 1.1 — `postgresql-client` genérico do Debian bookworm instala a
# versão 15. O servidor é PostgreSQL 16, e `pg_dump` RECUSA dumpar servidor
# mais novo ("aborting because of server version mismatch"). Sem o cliente 16,
# a rotina de backup falharia em produção exatamente como falhou no
# desenvolvimento. Fixamos a major 16 pelo repositório oficial do PGDG.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client-16 \
    gcc \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libice6 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Definir diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p \
    /app/static/fotos_funcionarios \
    /app/static/fotos \
    /app/static/images \
    /app/uploads \
    /app/logs

# Copiar e configurar entrypoint otimizado
COPY docker-entrypoint-easypanel-auto.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Expor porta
EXPOSE 5000

# Entrypoint otimizado
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Comando com configurações otimizadas para EasyPanel
# Fase 0.5 / 1.3 — `--access-logfile -` manda o access log para stdout, que o
# EasyPanel coleta. Sem isso o default do gunicorn é `accesslog = None`:
# NENHUMA requisição bem-sucedida era registrada em lugar nenhum.
# O formato acrescenta o tempo de resposta (%(D)s, em microssegundos).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", \
     "--keep-alive", "2", "--worker-connections", "1000", \
     "--access-logfile", "-", \
     "--access-logformat", "%(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s %(D)s \"%(f)s\" \"%(a)s\"", \
     "main:app"]