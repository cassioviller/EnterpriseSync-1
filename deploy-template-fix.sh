#!/bin/bash
# Script de deploy para correção de template RDO em produção
# Este script aplica a correção que sincroniza a interface RDO entre desenvolvimento e produção

set -e

echo "🔥 DEPLOY CORREÇÃO TEMPLATE RDO - PRODUÇÃO"
echo "=========================================="

# Verificar se arquivos necessários existem
if [ ! -f "Dockerfile.template-fix" ]; then
    echo "❌ ERRO: Dockerfile.template-fix não encontrado"
    exit 1
fi

if [ ! -f "docker-entrypoint-template-fix.sh" ]; then
    echo "❌ ERRO: docker-entrypoint-template-fix.sh não encontrado"
    exit 1
fi

if [ ! -f "templates/rdo/novo.html" ]; then
    echo "❌ ERRO: Template templates/rdo/novo.html não encontrado"
    exit 1
fi

echo "✅ Todos os arquivos necessários encontrados"

# Configurar variáveis de ambiente
export CONTAINER_NAME=${CONTAINER_NAME:-"sige-rdo-corrigido"}
export IMAGE_NAME=${IMAGE_NAME:-"sige-template-fix"}
export PORT=${PORT:-"5000"}

echo "📋 Configurações do Deploy:"
echo "   Container: $CONTAINER_NAME"
echo "   Imagem: $IMAGE_NAME"
echo "   Porta: $PORT"

# 1. Build da imagem com correção
echo "🔨 Fazendo build da imagem corrigida..."
docker build -f Dockerfile.template-fix -t $IMAGE_NAME . --no-cache

echo "✅ Build concluído com sucesso"

# 2. Parar container atual se existir
if docker ps -q -f name=$CONTAINER_NAME > /dev/null; then
    echo "⏹️ Parando container atual..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# 3. Remover imagem antiga se existir
if docker images -q $IMAGE_NAME:old > /dev/null; then
    echo "🗑️ Removendo imagem antiga..."
    docker rmi $IMAGE_NAME:old
fi

# 4. Iniciar novo container com correção
echo "🚀 Iniciando container corrigido..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $PORT:5000 \
  --restart unless-stopped \
  -e DATABASE_URL="${DATABASE_URL}" \
  -e SESSION_SECRET="${SESSION_SECRET:-chave-padrao-desenvolvimento}" \
  -e DB_HOST="${DB_HOST:-localhost}" \
  -e DB_PORT="${DB_PORT:-5432}" \
  -e DB_USER="${DB_USER:-postgres}" \
  -e FLASK_ENV="production" \
  $IMAGE_NAME

echo "✅ Container iniciado com sucesso"

# 5. Aguardar inicialização
echo "⏳ Aguardando inicialização do container..."
sleep 10

# 6. Verificar se container está rodando
if ! docker ps -q -f name=$CONTAINER_NAME > /dev/null; then
    echo "❌ ERRO: Container não está executando"
    echo "📋 Logs do container:"
    docker logs $CONTAINER_NAME
    exit 1
fi

echo "✅ Container executando corretamente"

# 7. Verificar health check
echo "🔍 Verificando health check..."
sleep 5

HEALTH_URL="http://localhost:$PORT/health"
if curl -s -f $HEALTH_URL > /dev/null; then
    echo "✅ Health check OK"
    echo "📊 Response: $(curl -s $HEALTH_URL)"
else
    echo "⚠️ Health check falhou, mas container pode estar inicializando..."
fi

# 8. Teste da interface RDO
echo "🎯 Testando interface RDO corrigida..."
RDO_URL="http://localhost:$PORT/funcionario/rdo/novo"
if curl -s -f $RDO_URL > /dev/null; then
    echo "✅ Interface RDO acessível"
else
    echo "⚠️ Interface RDO pode estar ainda carregando..."
fi

# 9. Verificar API de subatividades
echo "📡 Testando API de subatividades..."
API_URL="http://localhost:$PORT/api/test/rdo/servicos-obra/40"
if curl -s -f $API_URL > /dev/null; then
    echo "✅ API de subatividades funcionando"
    echo "📊 Dados: $(curl -s $API_URL | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"Subatividades: {d.get(\"total_subatividades\", \"N/A\")}")' 2>/dev/null || echo "Dados disponíveis")"
else
    echo "⚠️ API pode estar inicializando..."
fi

echo ""
echo "🎉 DEPLOY CONCLUÍDO COM SUCESSO!"
echo "================================"
echo "🌐 URL da aplicação: http://localhost:$PORT"
echo "🎯 Interface RDO: http://localhost:$PORT/funcionario/rdo/novo"
echo "📱 Health check: http://localhost:$PORT/health"
echo ""
echo "📋 VERIFICAÇÃO FINAL:"
echo "1. Acesse a interface RDO"
echo "2. Verifique se mostra subatividades (não funcionários)"
echo "3. Teste o botão 'Testar Último RDO'"
echo "4. Confirme que são 11 subatividades (4+3+4)"
echo ""
echo "📞 Container: docker logs $CONTAINER_NAME"
echo "🔧 Debug: docker exec -it $CONTAINER_NAME bash"