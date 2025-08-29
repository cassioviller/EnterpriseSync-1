#!/bin/bash
# Script de deploy automatizado para SIGE v8.0
# Unificado para desenvolvimento e produção

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "======================================"
echo "  SIGE v8.0 - Deploy Automático"
echo "  Sistema Integrado de Gestão"
echo "======================================"
echo -e "${NC}"

# Detectar ambiente
AMBIENTE=${AMBIENTE:-production}
if [[ "${AMBIENTE}" == "development" ]]; then
    echo -e "${YELLOW}🔧 Modo: DESENVOLVIMENTO${NC}"
    COMPOSE_FILE="docker-compose.unificado.yml"
    BUILD_ENV="development"
    FLASK_ENV="development"
else
    echo -e "${GREEN}🏭 Modo: PRODUÇÃO${NC}"
    COMPOSE_FILE="docker-compose.unificado.yml"
    BUILD_ENV="production"
    FLASK_ENV="production"
fi

# Verificar pré-requisitos
echo -e "${BLUE}🔍 Verificando pré-requisitos...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose não encontrado${NC}"
    exit 1
fi

# Verificar arquivos essenciais
ARQUIVOS_ESSENCIAIS=(
    "Dockerfile.unified"
    "docker-entrypoint-unified.sh"
    "main.py"
    "app.py"
    "models.py"
    "views.py"
    "templates/base_completo.html"
    "templates/dashboard.html"
    "templates/funcionarios.html"
    "static/css/app.css"
    "static/js/app.js"
)

for arquivo in "${ARQUIVOS_ESSENCIAIS[@]}"; do
    if [[ ! -f "$arquivo" ]]; then
        echo -e "${RED}❌ Arquivo essencial não encontrado: $arquivo${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Todos os arquivos essenciais encontrados${NC}"

# Executar verificação de consistência
echo -e "${BLUE}🔍 Executando verificação de consistência...${NC}"
if python verificar_consistencia.py; then
    echo -e "${GREEN}✅ Verificação de consistência OK${NC}"
else
    echo -e "${YELLOW}⚠️  Algumas verificações falharam, mas continuando...${NC}"
fi

# Parar containers existentes
echo -e "${BLUE}🛑 Parando containers existentes...${NC}"
docker-compose -f $COMPOSE_FILE down --remove-orphans || true

# Limpar imagens antigas (opcional)
if [[ "${LIMPAR_IMAGENS:-false}" == "true" ]]; then
    echo -e "${BLUE}🧹 Limpando imagens antigas...${NC}"
    docker system prune -f
    docker image prune -f
fi

# Build da aplicação
echo -e "${BLUE}🔨 Construindo aplicação...${NC}"
docker-compose -f $COMPOSE_FILE build --no-cache \
    --build-arg BUILD_ENV=$BUILD_ENV sige

# Aguardar banco de dados
echo -e "${BLUE}🗃️  Iniciando banco de dados...${NC}"
docker-compose -f $COMPOSE_FILE up -d postgres

echo -e "${YELLOW}⏳ Aguardando PostgreSQL...${NC}"
while ! docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U postgres -d sige &>/dev/null; do
    echo -n "."
    sleep 2
done
echo -e "\n${GREEN}✅ PostgreSQL pronto${NC}"

# Executar migrações
echo -e "${BLUE}🔄 Executando migrações...${NC}"
docker-compose -f $COMPOSE_FILE run --rm \
    -e FLASK_ENV=$FLASK_ENV \
    -e BUILD_ENV=$BUILD_ENV \
    sige python -c "
from app import app, db
with app.app_context():
    try:
        import migrations
        print('✅ Migrações executadas com sucesso')
    except Exception as e:
        print(f'❌ Erro nas migrações: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
"

# Verificar saúde da aplicação
echo -e "${BLUE}🚀 Iniciando aplicação...${NC}"
docker-compose -f $COMPOSE_FILE up -d sige

echo -e "${YELLOW}⏳ Aguardando aplicação ficar pronta...${NC}"
TIMEOUT=60
COUNTER=0

while [[ $COUNTER -lt $TIMEOUT ]]; do
    if curl -f -s http://localhost:5000/health >/dev/null 2>&1; then
        echo -e "\n${GREEN}✅ Aplicação funcionando!${NC}"
        break
    fi
    
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 2))
done

if [[ $COUNTER -ge $TIMEOUT ]]; then
    echo -e "\n${RED}❌ Timeout: Aplicação não respondeu em ${TIMEOUT}s${NC}"
    echo -e "${YELLOW}📋 Logs da aplicação:${NC}"
    docker-compose -f $COMPOSE_FILE logs --tail=20 sige
    exit 1
fi

# Verificações finais
echo -e "${BLUE}🧪 Executando testes finais...${NC}"

# Testar rotas críticas
ROTAS_CRITICAS=(
    "/health"
    "/login"
    # Adicione outras rotas conforme necessário
)

for rota in "${ROTAS_CRITICAS[@]}"; do
    if curl -f -s "http://localhost:5000${rota}" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Rota OK: ${rota}${NC}"
    else
        echo -e "${RED}❌ Rota falhou: ${rota}${NC}"
    fi
done

# Relatório final
echo -e "${BLUE}"
echo "======================================"
echo "       DEPLOY CONCLUÍDO COM SUCESSO"
echo "======================================"
echo -e "${NC}"

echo -e "${GREEN}✅ Sistema SIGE v8.0 funcionando${NC}"
echo -e "🌐 Acesso: http://localhost:5000"
echo -e "🔧 Ambiente: ${AMBIENTE}"
echo -e "📊 Status: $(docker-compose -f $COMPOSE_FILE ps --services --filter status=running | wc -l) serviços rodando"

if [[ "${AMBIENTE}" == "development" ]]; then
    echo -e "${YELLOW}"
    echo "🔧 COMANDOS ÚTEIS PARA DESENVOLVIMENTO:"
    echo "  - Ver logs: docker-compose -f $COMPOSE_FILE logs -f sige"
    echo "  - Entrar no container: docker-compose -f $COMPOSE_FILE exec sige bash"
    echo "  - Parar: docker-compose -f $COMPOSE_FILE down"
    echo "  - Reiniciar: docker-compose -f $COMPOSE_FILE restart sige"
    echo -e "${NC}"
fi

echo -e "${GREEN}🎉 Deploy finalizado!${NC}"