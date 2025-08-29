#!/bin/bash

echo "🚀 DEPLOY PRODUÇÃO CORRIGIDO - SIGE v8.0"
echo "========================================"

# Parar container existente
echo "1. Parando container atual..."
docker stop sige-producao 2>/dev/null || true
docker rm sige-producao 2>/dev/null || true

# Build nova imagem
echo "2. Construindo imagem corrigida..."
docker build -f Dockerfile.producao-corrigido -t sige:producao-corrigida .

if [ $? -ne 0 ]; then
    echo "❌ Erro no build da imagem"
    exit 1
fi

echo "✅ Imagem construída com sucesso"

# Deploy com variáveis de ambiente
echo "3. Fazendo deploy..."
docker run -d \
  --name sige-producao \
  --restart unless-stopped \
  -p 5000:5000 \
  -e DATABASE_URL="${DATABASE_URL:-postgresql://user:pass@localhost:5432/sige}" \
  -e SESSION_SECRET="${SESSION_SECRET:-seu-secret-key-aqui}" \
  -e FLASK_ENV=production \
  -e PGHOST="${PGHOST:-localhost}" \
  -e PGPORT="${PGPORT:-5432}" \
  -e PGUSER="${PGUSER:-postgres}" \
  -e PGPASSWORD="${PGPASSWORD:-password}" \
  -e PGDATABASE="${PGDATABASE:-sige}" \
  sige:producao-corrigida

if [ $? -ne 0 ]; then
    echo "❌ Erro no deploy"
    exit 1
fi

echo "✅ Deploy realizado com sucesso"

# Verificar saúde da aplicação
echo "4. Verificando aplicação..."
sleep 10

if docker ps | grep -q sige-producao; then
    echo "✅ Container rodando"
    
    # Teste de conectividade
    if curl -f http://localhost:5000/health >/dev/null 2>&1; then
        echo "✅ Health check passou"
        echo ""
        echo "🎉 DEPLOY PRODUÇÃO CONCLUÍDO COM SUCESSO!"
        echo "📱 Interface RDO moderna sincronizada"
        echo "🔗 Acesse: http://seu-dominio.com"
    else
        echo "⚠️ Health check falhou - verificar logs"
        docker logs sige-producao --tail 20
    fi
else
    echo "❌ Container não está rodando"
    docker logs sige-producao --tail 20
    exit 1
fi
