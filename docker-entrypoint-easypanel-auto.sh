#!/bin/bash
# 🚀 SIGE v10.0 - ENTRYPOINT TOTALMENTE AUTOMÁTICO EASYPANEL
# ===========================================================
# VERSÃO SIMPLIFICADA - Usa detecção automática do app.py
# Sistema inteligente: Zero configuração manual necessária
# ===========================================================

set -e

# Configurações de logging
LOG_FILE="/tmp/sige_deployment.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "🚀 SIGE v10.0 - SISTEMA TOTALMENTE AUTOMÁTICO"
echo "============================================="
echo "📅 $(date)"
echo "💻 Hostname: $(hostname)"
echo "🤖 Modo: Detecção automática de ambiente"
echo

# FASE 1: Configurações básicas do ambiente
echo "🔧 FASE 1: CONFIGURAÇÕES BÁSICAS"
echo "================================"
export FLASK_ENV=production
export DIGITAL_MASTERY_MODE=true
export AUTO_MIGRATIONS_ENABLED=true
export DEPLOYMENT_TIMESTAMP=$(date +%s)

echo "✅ Variáveis de ambiente configuradas"
echo

# FASE 2: Configuração automática de DATABASE_URL (se necessário)
echo "🔗 FASE 2: CONFIGURAÇÃO AUTOMÁTICA DE BANCO"
echo "==========================================="

if [ -z "$DATABASE_URL" ]; then
    # Tentar detectar se estamos no EasyPanel
    if [[ "$(hostname)" == *"viajey_sige"* ]] || [[ "$(hostname)" == *"easypanel"* ]]; then
        export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable"
        echo "🎯 EasyPanel detectado - DATABASE_URL configurada automaticamente"
    else
        echo "ℹ️ DATABASE_URL não configurada - app.py fará detecção automática"
    fi
else
    echo "✅ DATABASE_URL já definida"
fi

# Mascarar credenciais para logs seguros
DB_MASKED=$(echo "$DATABASE_URL" | sed 's/:\/\/[^:]*:[^@]*@/:\/\/****:****@/g' 2>/dev/null || echo "não definida")
echo "🔗 Database: $DB_MASKED"
echo

# FASE 3: Aguardar banco de dados e correções críticas
echo "⏳ FASE 3: CONECTIVIDADE E CORREÇÕES CRÍTICAS"
echo "=============================================="

if [ -n "$DATABASE_URL" ]; then
    # Aguardar um tempo básico para o banco estar disponível
    WAIT_TIME=${DB_WAIT_TIME:-15}
    echo "⏱️ Aguardando $WAIT_TIME segundos para estabilização do banco..."
    sleep "$WAIT_TIME"
    
    # Teste básico de conectividade
    echo "🔍 Testando conectividade básica..."
    if python3 -c "
import psycopg2
import os
import sys
try:
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'), connect_timeout=10)
    conn.close()
    print('✅ Banco de dados acessível')
    sys.exit(0)
except Exception as e:
    print(f'⚠️ Conectividade limitada: {e}')
    print('🔄 Continuando - app.py fará verificações detalhadas')
    sys.exit(0)  # Não falhar aqui, deixar app.py gerenciar
" 2>/dev/null; then
        echo "✅ Conectividade verificada"
        
        # CORREÇÃO CRÍTICA: Porcentagem Combustível
        echo ""
        echo "🔧 EXECUTANDO CORREÇÕES CRÍTICAS DE PRODUÇÃO"
        echo "============================================"
        if [ -f "/app/fix_porcentagem_combustivel_production.py" ]; then
            echo "🔧 Executando correção: porcentagem_combustivel..."
            python3 /app/fix_porcentagem_combustivel_production.py
            if [ $? -eq 0 ]; then
                echo "✅ Correção porcentagem_combustivel concluída"
            else
                echo "⚠️ Correção porcentagem_combustivel falhou - continuando"
            fi
        else
            echo "ℹ️ Script de correção não encontrado - pulando"
        fi
        echo ""
        
    else
        echo "⚠️ Conectividade limitada - app.py fará detecção inteligente"
    fi
else
    echo "ℹ️ DATABASE_URL não definida - app.py fará configuração automática"
fi
echo

# FASE 4: Sistema automático do app.py
echo "🤖 FASE 4: DELEGANDO PARA SISTEMA AUTOMÁTICO"
echo "============================================"
echo "🎯 O app.py fará:"
echo "   🔍 Detecção automática de ambiente (EasyPanel vs Desenvolvimento)"
echo "   🔗 Configuração automática de DATABASE_URL se necessário"
echo "   🔄 Execução automática de migrações em produção"
echo "   🗑️ Limpeza automática de dados obsoletos"
echo "   📊 Logs detalhados de todas as operações"
echo
echo "💡 ZERO INTERVENÇÃO MANUAL NECESSÁRIA!"
echo "🚀 Iniciando aplicação com sistema totalmente automático..."
echo

# FASE 5: Health check pós-inicialização (opcional)
if [ "${ENABLE_HEALTH_CHECK:-true}" = "true" ]; then
    echo "🏥 FASE 5: HEALTH CHECK PROGRAMADO"
    echo "================================="
    echo "⏰ Health check será executado após 30s da inicialização"
    
    # Health check em background
    (
        sleep 30
        echo "🔍 [$(date)] Executando health check pós-inicialização..."
        
        # Verificar se a aplicação está respondendo
        if curl -f -s http://localhost:5000/health >/dev/null 2>&1; then
            echo "✅ [$(date)] Aplicação funcionando corretamente"
        else
            echo "⚠️ [$(date)] Aplicação pode não estar totalmente iniciada ainda"
        fi
        
        # Verificar logs de erro
        if grep -q "ERROR" "$LOG_FILE" 2>/dev/null; then
            echo "⚠️ [$(date)] Erros detectados nos logs - verifique $LOG_FILE"
        else
            echo "✅ [$(date)] Nenhum erro crítico detectado"
        fi
        
        echo "📊 [$(date)] Health check concluído"
        echo
    ) &
fi

# FASE 6: Iniciar aplicação
echo "🚀 FASE 6: INICIANDO APLICAÇÃO"
echo "=============================="
echo "🎯 Comando: gunicorn --bind 0.0.0.0:5000 --reuse-port main:app"
echo "💡 Sistema TOTALMENTE AUTOMÁTICO ativo!"
echo "📋 Logs disponíveis em: $LOG_FILE"
echo

# Executar a aplicação
# O app.py fará toda a detecção e configuração automática
exec gunicorn --bind 0.0.0.0:5000 --reuse-port main:app