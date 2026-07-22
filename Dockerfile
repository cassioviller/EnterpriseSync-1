# SIGE v10.0 - Dockerfile Otimizado para Produção EasyPanel
# Versão simplificada para deploy rápido e confiável
# Fase 0.5 / 2.1 — base com DIGEST fixado. `python:3.11-slim` é tag
# flutuante: dois builds do mesmo commit podiam partir de imagens diferentes.
# Para atualizar a base, troque o digest conscientemente.
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

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

# Fase 0.5 / 2.1 — INSTALAÇÃO PELO LOCKFILE.
# Antes: `COPY pyproject.toml` + `pip install .` — o `uv.lock` NUNCA entrava
# na imagem e o pip re-resolvia do PyPI a cada build, respeitando só os pisos
# `>=`. Dois builds do mesmo commit produziam dependências diferentes, e o
# rollback do EasyPanel (rebuild do commit anterior) não reproduzia a imagem
# anterior. Agora o lock governa, e o build FALHA se ele estiver
# dessincronizado do pyproject (`--frozen`).
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.5.* \
    && uv sync --frozen --no-dev --no-install-project \
    && uv cache clean
ENV PATH="/app/.venv/bin:$PATH"

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

# Fase 0.5 / 2.1 — usuário NÃO-ROOT. O container rodava como root: qualquer
# falha de parser de arquivo não confiável (upload de .mpp/.xlsx/imagem)
# executava com privilégio total e acesso a todo o filesystem.
RUN groupadd --system sige && useradd --system --gid sige --home /app sige \
    && mkdir -p /var/backups/sige \
    && chown -R sige:sige /app /var/backups/sige
# O diretório de backup PRECISA ser volume persistente montado pelo painel —
# sem isso os dumps somem no restart do container. O VOLUME declara a intenção
# e garante que o caminho exista com o dono certo mesmo sem montagem.
VOLUME ["/var/backups/sige"]
USER sige

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