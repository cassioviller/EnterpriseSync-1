#!/bin/bash

echo "🚨 HOTFIX PRODUÇÃO URGENTE - SIGE RDO Interface"
echo "================================================"

# Verificar arquivos necessários
echo "1. Verificando arquivos de correção..."
if [ ! -f "templates/rdo/novo.html" ]; then
    echo "❌ Template novo.html não encontrado"
    exit 1
fi

if [ ! -f "views.py" ]; then
    echo "❌ views.py não encontrado" 
    exit 1
fi

echo "✅ Arquivos de correção encontrados"

# Criar Dockerfile de correção para produção
echo "2. Criando Dockerfile de correção..."
cat > Dockerfile.producao-corrigido << 'EOF'
FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar script de entrada para produção
RUN echo '#!/bin/bash' > /app/docker-entrypoint-producao.sh && \
    echo 'set -e' >> /app/docker-entrypoint-producao.sh && \
    echo 'echo "🔄 Iniciando SIGE v8.0 em produção..."' >> /app/docker-entrypoint-producao.sh && \
    echo 'echo "📊 Verificando conectividade PostgreSQL..."' >> /app/docker-entrypoint-producao.sh && \
    echo 'until pg_isready -h $PGHOST -p $PGPORT -U $PGUSER; do' >> /app/docker-entrypoint-producao.sh && \
    echo '  echo "⏳ Aguardando PostgreSQL ficar disponível..."' >> /app/docker-entrypoint-producao.sh && \
    echo '  sleep 2' >> /app/docker-entrypoint-producao.sh && \
    echo 'done' >> /app/docker-entrypoint-producao.sh && \
    echo 'echo "✅ PostgreSQL conectado com sucesso"' >> /app/docker-entrypoint-producao.sh && \
    echo 'echo "🎯 Interface RDO moderna sincronizada"' >> /app/docker-entrypoint-producao.sh && \
    echo 'echo "🚀 Iniciando servidor Gunicorn..."' >> /app/docker-entrypoint-producao.sh && \
    echo 'exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --reload main:app' >> /app/docker-entrypoint-producao.sh

# Tornar script executável
RUN chmod +x /app/docker-entrypoint-producao.sh

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint-producao.sh"]
EOF

echo "✅ Dockerfile.producao-corrigido criado"

# Criar script de build e deploy
echo "3. Criando script de deploy automatizado..."
cat > deploy-producao-corrigido.sh << 'DEPLOY_SCRIPT'
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
EOF

chmod +x deploy-producao-corrigido.sh
echo "✅ Script de deploy criado"

echo ""
echo "📋 INSTRUÇÕES DE DEPLOY PRODUÇÃO:"
echo "=================================="
echo "1. Configure as variáveis de ambiente:"
echo "   export DATABASE_URL='postgresql://user:pass@host:port/db'"
echo "   export SESSION_SECRET='seu-secret-seguro'"
echo ""
echo "2. Execute o deploy:"
echo "   ./deploy-producao-corrigido.sh"
echo ""
echo "3. Monitore os logs:"
echo "   docker logs -f sige-producao"
echo ""
echo "✅ Hotfix preparado! Execute o deploy quando ready."
EOF

chmod +x hotfix-producao-urgente.sh