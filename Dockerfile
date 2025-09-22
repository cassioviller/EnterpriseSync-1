# SIGE v10.0 - Dockerfile Otimizado para Produção EasyPanel
# Versão com correções automáticas para deploy rápido e confiável
# Inclui correção automática da coluna porcentagem_combustivel
FROM python:3.11-slim

# Variáveis de ambiente básicas
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production
ENV PORT=5000
ENV DIGITAL_MASTERY_MODE=true

# Instalar dependências do sistema (mínimas)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    libpq-dev \
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

# Copiar scripts de correção de produção
COPY fix_porcentagem_combustivel_production.py /app/
RUN chmod +x /app/fix_porcentagem_combustivel_production.py

# Copiar e configurar entrypoint otimizado com correções automáticas
COPY docker-entrypoint-easypanel-auto.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Expor porta
EXPOSE 5000

# Entrypoint otimizado
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Comando com configurações otimizadas para EasyPanel
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--keep-alive", "2", "--worker-connections", "1000", "main:app"]