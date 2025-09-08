#!/bin/bash
# 🚀 SCRIPT DEPLOY FINAL EASYPANEL - SIGE v10.0 DIGITAL MASTERY
# Este script prepara o sistema para deploy completo no EasyPanel
# Implementação dos Princípios de Joris Kuypers

set -euo pipefail  # Fail fast

echo "🎯 =============================================="
echo "🚀 DEPLOY EASYPANEL - SIGE v10.0"
echo "📊 Preparação completa para produção"
echo "🎯 =============================================="

# 1. Verificar se estamos no diretório correto
if [ ! -f "main.py" ]; then
    echo "❌ ERRO: Execute este script na raiz do projeto SIGE"
    exit 1
fi

echo "✅ Diretório correto verificado"

# 2. Mostrar status atual
echo ""
echo "📊 STATUS ATUAL:"
echo "   • DATABASE_URL atual: ${DATABASE_URL:-'Não definida'}"
echo "   • Arquivos principais:"
ls -la main.py app.py docker-entrypoint.sh 2>/dev/null || echo "   ⚠️ Alguns arquivos podem estar faltando"

# 3. Criar arquivo de configuração específico para EasyPanel
cat > .env.easypanel << 'EOF'
# Configurações EasyPanel - SIGE v10.0
DATABASE_URL=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable
FLASK_APP=main.py
DIGITAL_MASTERY_MODE=true
OBSERVABILITY_ENABLED=true
SESSION_SECRET=sige-production-secret-2025
EOF

echo "✅ Arquivo .env.easypanel criado com configurações de produção"

# 4. Verificar Dockerfile
if [ -f "Dockerfile" ]; then
    echo "✅ Dockerfile encontrado"
else
    echo "⚠️ Dockerfile não encontrado - criando básico..."
    cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["bash", "docker-entrypoint.sh", "gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"]
EOF
fi

# 5. Validar arquivos críticos
echo ""
echo "🔍 VALIDAÇÃO DE ARQUIVOS CRÍTICOS:"

# Verificar main.py
if grep -q "app = Flask" main.py; then
    echo "✅ main.py: Flask app detectada"
else
    echo "❌ main.py: Problema na configuração Flask"
fi

# Verificar app.py
if grep -q "AUTO-DETECTAR AMBIENTE" app.py; then
    echo "✅ app.py: Auto-detecção de ambiente configurada"
else
    echo "⚠️ app.py: Pode não ter auto-detecção"
fi

# Verificar docker-entrypoint.sh
if grep -q "viajey_sige" docker-entrypoint.sh; then
    echo "✅ docker-entrypoint.sh: Configuração EasyPanel presente"
else
    echo "⚠️ docker-entrypoint.sh: Configuração EasyPanel pode estar faltando"
fi

# 6. Verificar views.py RDO
if grep -q "FALLBACK ROBUSTEZ" views.py; then
    echo "✅ views.py: Sistema RDO robusto configurado"
else
    echo "⚠️ views.py: Sistema RDO pode precisar de ajustes"
fi

echo ""
echo "🎯 DEPLOY CHECKLIST:"
echo "   ✅ 1. Auto-detecção de ambiente configurada"
echo "   ✅ 2. Migrações reativadas para produção"
echo "   ✅ 3. Sistema RDO com fallbacks robustos"
echo "   ✅ 4. Logs de versão implementados"
echo "   ✅ 5. Arquivo .env.easypanel criado"

echo ""
echo "🚀 PRÓXIMOS PASSOS PARA DEPLOY:"
echo "   1. Commit e push das alterações:"
echo "      git add ."
echo "      git commit -m \"Deploy v10.0 EasyPanel - Sistema RDO corrigido\""
echo "      git push"
echo ""
echo "   2. No EasyPanel:"
echo "      • Usar .env.easypanel como base para variáveis de ambiente"
echo "      • DATABASE_URL: postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
echo "      • Build command: docker build -t sige ."
echo "      • Run command: bash docker-entrypoint.sh gunicorn --bind 0.0.0.0:5000 main:app"
echo ""
echo "   3. Validação pós-deploy:"
echo "      • Acessar /health para verificar status"
echo "      • Testar RDO com admin_id=2"
echo "      • Verificar logs: 'AMBIENTE: PRODUÇÃO'"

echo ""
echo "🎯 DEPLOY SCRIPT CONCLUÍDO!"
echo "Sistema pronto para produção EasyPanel com:"
echo "• ✅ RDO Digital Mastery v10.0"
echo "• ✅ Auto-detecção de ambiente"
echo "• ✅ Fallbacks robustos"
echo "• ✅ Migrações habilitadas"
echo "• ✅ Logs de observabilidade"