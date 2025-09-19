#!/bin/bash

# 🚨 MIGRAÇÃO DE EMERGÊNCIA - SISTEMA DE VEÍCULOS
# ================================================
# Script de emergência para execução manual das migrações em produção
# 
# Autor: Sistema SIGE v10.0
# Data: 2025-01-19
# Versão: 1.0.0 - Implementação completa

set -e  # Exit on any error

echo "🚨 MIGRAÇÃO DE EMERGÊNCIA - SISTEMA DE VEÍCULOS"
echo "================================================"
echo "📅 Iniciado em: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ============================================
# 1. VALIDAÇÕES INICIAIS
# ============================================

# Verificar se DATABASE_URL está definida
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERRO CRÍTICO: DATABASE_URL não está definida!"
    echo "   Configure a variável de ambiente DATABASE_URL antes de executar."
    echo ""
    exit 1
fi

# Extrair e mostrar target mascarado (parte após '@')
DB_TARGET=$(echo "$DATABASE_URL" | sed 's/.*@//')
if [ -n "$DB_TARGET" ]; then
    echo "🔗 Target do banco: $DB_TARGET"
else
    echo "🔗 Target do banco: [não identificado]"
fi
echo ""

# Verificar se o migrador existe
if [ ! -f "database_migrator_complete.py" ]; then
    echo "❌ ERRO: Arquivo database_migrator_complete.py não encontrado!"
    echo "   Certifique-se de executar o script no diretório correto."
    echo ""
    exit 1
fi

# Verificar se python3 está disponível
if ! command -v python3 &> /dev/null; then
    echo "❌ ERRO: python3 não está disponível no sistema!"
    echo "   Instale Python 3 antes de continuar."
    echo ""
    exit 1
fi

echo "✅ Validações iniciais concluídas"
echo "📋 Preparando para executar migração..."
echo ""

# ============================================
# 2. EXECUÇÃO DA MIGRAÇÃO
# ============================================

echo "🚀 Executando database_migrator_complete.py..."
echo "⏱️ Iniciado em: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Executar o migrador e capturar o código de saída
python3 database_migrator_complete.py
MIGRATION_EXIT_CODE=$?

echo ""
echo "⏱️ Finalizado em: $(date '+%Y-%m-%d %H:%M:%S')"
echo "🔄 Código de saída: $MIGRATION_EXIT_CODE"
echo ""

# ============================================
# 3. TRATAMENTO DE RESULTADO
# ============================================

if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
    # SUCESSO
    echo "✅ MIGRAÇÃO EXECUTADA COM SUCESSO"
    echo "🎉 Todas as migrações foram aplicadas corretamente!"
    echo ""
    
    # Tentar reinicialização por plataforma
    echo "🔄 Verificando opções de reinicialização..."
    
    # Detectar EasyPanel
    if [ -n "$EASYPANEL_PROJECT_ID" ]; then
        echo "🟦 EasyPanel detectado (Project ID: $EASYPANEL_PROJECT_ID)"
        echo "ℹ️  Reinicialização automática será gerenciada pelo EasyPanel"
        echo ""
    # Verificar systemctl
    elif command -v systemctl &> /dev/null; then
        echo "🟨 systemctl disponível - tentando reinicializar serviços..."
        
        # Lista de possíveis serviços para tentar reinicializar
        SERVICES_TO_RESTART=("gunicorn" "nginx" "apache2" "httpd")
        
        for service in "${SERVICES_TO_RESTART[@]}"; do
            if systemctl is-active --quiet "$service" 2>/dev/null; then
                echo "🔄 Reinicializando $service..."
                if systemctl restart "$service" 2>/dev/null; then
                    echo "✅ $service reinicializado com sucesso"
                else
                    echo "⚠️ Falha ao reinicializar $service (pode precisar de sudo)"
                fi
            fi
        done
        echo ""
    else
        echo "ℹ️  Nenhuma opção de reinicialização automática detectada"
        echo "   Reinicialize manualmente o serviço da aplicação se necessário"
        echo ""
    fi
    
    echo "🏁 MIGRAÇÃO DE EMERGÊNCIA CONCLUÍDA COM SUCESSO!"
    echo "📁 Logs detalhados disponíveis em: /tmp/database_migrator.log"
    echo ""
    
else
    # FALHA
    echo "❌ MIGRAÇÃO FALHOU"
    echo "💥 O processo de migração encontrou erros e não foi concluído."
    echo ""
    echo "🔍 PRÓXIMOS PASSOS:"
    echo "   1. Verificar logs detalhados em: /tmp/database_migrator.log"
    echo "   2. Identificar e corrigir os problemas encontrados"
    echo "   3. Executar novamente quando os problemas forem resolvidos"
    echo ""
    echo "📞 SUPORTE:"
    echo "   - Consulte a documentação técnica do sistema"
    echo "   - Entre em contato com a equipe de desenvolvimento"
    echo ""
    
    # Mostrar últimas linhas do log se disponível
    if [ -f "/tmp/database_migrator.log" ]; then
        echo "📋 ÚLTIMAS LINHAS DO LOG:"
        echo "------------------------"
        tail -n 10 /tmp/database_migrator.log 2>/dev/null || echo "   (não foi possível ler o log)"
        echo ""
    fi
    
    echo "🛑 MIGRAÇÃO DE EMERGÊNCIA FALHOU!"
    exit 1
fi

# ============================================
# 4. FINALIZAÇÃO
# ============================================

echo "📊 RESUMO DA EXECUÇÃO:"
echo "├── Iniciado: Script executado com sucesso"
echo "├── Validações: DATABASE_URL verificada"
echo "├── Target: $DB_TARGET"
echo "├── Migração: $([ $MIGRATION_EXIT_CODE -eq 0 ] && echo "✅ Sucesso" || echo "❌ Falha")"
echo "└── Logs: /tmp/database_migrator.log"
echo ""
echo "🎯 Migração de emergência finalizada em: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"