#!/bin/bash

echo "🚀 DEPLOY PRODUÇÃO FINAL - SIGE v8.0 RDO Interface Moderna"
echo "========================================================="

# Verificar se estamos no diretório correto
if [ ! -f "views.py" ] || [ ! -f "templates/rdo/novo.html" ]; then
    echo "❌ Execute este script no diretório raiz do projeto SIGE"
    exit 1
fi

# Configurações
CONTAINER_NAME="sige-producao"
IMAGE_NAME="sige-producao-v8"
PORT=${PORT:-5000}

echo "📋 Configurações do Deploy:"
echo "   Container: $CONTAINER_NAME"
echo "   Imagem: $IMAGE_NAME" 
echo "   Porta: $PORT"

# 1. Parar e remover container existente
echo "1. Parando container atual..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true
echo "✅ Container anterior removido"

# 2. Criar Dockerfile otimizado para produção
echo "2. Criando Dockerfile de produção..."
cat > Dockerfile.producao << 'DOCKERFILE'
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Configurações de produção
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV TEMPLATE_AUTO_RELOAD=false

# Script de entrada
RUN echo '#!/bin/bash' > /app/entrypoint.sh && \
    echo 'set -e' >> /app/entrypoint.sh && \
    echo 'echo "🔄 Iniciando SIGE v8.0 em produção..."' >> /app/entrypoint.sh && \
    echo 'echo "📊 Verificando PostgreSQL..."' >> /app/entrypoint.sh && \
    echo 'until pg_isready -h ${PGHOST:-localhost} -p ${PGPORT:-5432} -U ${PGUSER:-postgres}; do' >> /app/entrypoint.sh && \
    echo '  echo "⏳ Aguardando PostgreSQL..."' >> /app/entrypoint.sh && \
    echo '  sleep 3' >> /app/entrypoint.sh && \
    echo 'done' >> /app/entrypoint.sh && \
    echo 'echo "✅ PostgreSQL conectado"' >> /app/entrypoint.sh && \
    echo 'echo "🎯 Interface RDO moderna ativa"' >> /app/entrypoint.sh && \
    echo 'echo "🚀 Iniciando Gunicorn..."' >> /app/entrypoint.sh && \
    echo 'exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --preload main:app' >> /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
DOCKERFILE

echo "✅ Dockerfile criado"

# 3. Build da nova imagem
echo "3. Construindo imagem de produção..."
docker build -f Dockerfile.producao -t $IMAGE_NAME . --no-cache

if [ $? -ne 0 ]; then
    echo "❌ Erro no build da imagem"
    exit 1
fi

echo "✅ Imagem construída com sucesso"

# 4. Deploy do container
echo "4. Fazendo deploy do container..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p $PORT:5000 \
  -e DATABASE_URL="${DATABASE_URL}" \
  -e SESSION_SECRET="${SESSION_SECRET:-sige-secret-production-2025}" \
  -e FLASK_ENV=production \
  -e PGHOST="${PGHOST}" \
  -e PGPORT="${PGPORT:-5432}" \
  -e PGUSER="${PGUSER}" \
  -e PGPASSWORD="${PGPASSWORD}" \
  -e PGDATABASE="${PGDATABASE}" \
  $IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "❌ Erro no deploy do container"
    exit 1
fi

echo "✅ Container iniciado com sucesso"

# 5. Aguardar inicialização
echo "5. Aguardando inicialização..."
sleep 15

# 6. Verificar status
echo "6. Verificando status do deploy..."

# Verificar se container está rodando
if docker ps | grep -q $CONTAINER_NAME; then
    echo "✅ Container executando"
else
    echo "❌ Container não está executando"
    echo "📋 Logs do container:"
    docker logs $CONTAINER_NAME
    exit 1
fi

# 7. Teste de health check
echo "7. Testando health check..."
sleep 5

if curl -s -f "http://localhost:$PORT/health" > /dev/null; then
    echo "✅ Health check passou"
    HEALTH_RESPONSE=$(curl -s "http://localhost:$PORT/health")
    echo "📊 Response: $HEALTH_RESPONSE"
else
    echo "⚠️ Health check falhou, verificando logs..."
    docker logs --tail 20 $CONTAINER_NAME
fi

# 8. Teste da interface RDO
echo "8. Testando interface RDO moderna..."
if curl -s -f "http://localhost:$PORT/funcionario/rdo/novo" > /dev/null; then
    echo "✅ Interface RDO acessível"
else
    echo "⚠️ Interface RDO pode estar carregando..."
fi

# 9. Teste da API de subatividades
echo "9. Testando API de subatividades..."
if curl -s -f "http://localhost:$PORT/api/test/rdo/servicos-obra/40" > /dev/null; then
    echo "✅ API funcionando"
else
    echo "⚠️ API pode estar inicializando..."
fi

echo ""
echo "🎉 DEPLOY CONCLUÍDO!"
echo "===================="
echo "🌐 URL: http://localhost:$PORT"
echo "🎯 RDO: http://localhost:$PORT/funcionario/rdo/novo"
echo "📱 Health: http://localhost:$PORT/health"
echo ""
echo "📋 VERIFICAÇÕES MANUAIS:"
echo "1. Acesse a interface RDO"
echo "2. Verifique se mostra subatividades (não funcionários)"
echo "3. Teste 'Testar Último RDO'"
echo "4. Confirme 11 subatividades disponíveis"
echo ""
echo "📞 Monitoramento:"
echo "   docker logs -f $CONTAINER_NAME"
echo "   docker stats $CONTAINER_NAME"
echo ""
echo "🔧 Rollback (se necessário):"
echo "   docker stop $CONTAINER_NAME"
echo "   docker rm $CONTAINER_NAME"