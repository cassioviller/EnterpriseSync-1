#!/bin/bash

# 🚀 SCRIPT DE EXECUÇÃO MANUAL DE MIGRAÇÕES FORÇADAS - PRODUÇÃO
# ==============================================================
# Este script executa manualmente as migrações forçadas de veículos
# Ideal para situações de emergência em produção

set -e  # Sair em caso de erro

echo "🚀 SCRIPT DE MIGRAÇÕES FORÇADAS DE VEÍCULOS - PRODUÇÃO"
echo "======================================================"

# Verificar se DATABASE_URL está definida
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERRO: DATABASE_URL não está definida!"
    echo "💡 Defina a variável antes de executar:"
    echo "   export DATABASE_URL='postgresql://user:password@host:port/database'"
    exit 1
fi

# Mascarar credenciais para logs seguros
DATABASE_URL_MASKED=$(echo "$DATABASE_URL" | sed 's/:\/\/[^:]*:[^@]*@/:\/\/****:****@/')
echo "🎯 TARGET DATABASE: $DATABASE_URL_MASKED"

# Verificar se Python está disponível
if ! command -v python3 &> /dev/null; then
    echo "❌ ERRO: Python3 não encontrado!"
    exit 1
fi

# Verificar se o arquivo de migração existe
if [ ! -f "migration_force_veiculos.py" ]; then
    echo "❌ ERRO: Arquivo migration_force_veiculos.py não encontrado!"
    echo "💡 Certifique-se de que está no diretório correto do projeto"
    exit 1
fi

echo ""
echo "⚠️  AVISO: Esta operação executará ALTER TABLE no banco de produção"
echo "📊 Operações que serão executadas:"
echo "   - Adicionar colunas faltantes na tabela uso_veiculo"  
echo "   - Adicionar colunas faltantes na tabela custo_veiculo"
echo "   - Verificar integridade das tabelas"
echo ""

# Confirmar execução (apenas se executado interativamente)
if [ -t 0 ]; then
    read -p "🤔 Deseja continuar com as migrações? (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
        echo "❌ Operação cancelada pelo usuário"
        exit 0
    fi
fi

echo ""
echo "🔄 EXECUTANDO MIGRAÇÕES FORÇADAS..."
echo "=" * 40

# Executar as migrações
python3 migration_force_veiculos.py

# Capturar o código de saída
EXIT_CODE=$?

echo ""
echo "=" * 40

if [ $EXIT_CODE -eq 0 ]; then
    echo "🎉 MIGRAÇÕES EXECUTADAS COM SUCESSO!"
    echo "✅ Sistema pronto para uso em produção"
    echo ""
    echo "📋 Próximos passos recomendados:"
    echo "   1. Verificar logs do aplicativo"
    echo "   2. Testar funcionalidades de veículos"
    echo "   3. Monitorar por erros de colunas faltantes"
else
    echo "❌ MIGRAÇÕES FALHARAM!"
    echo "🔍 Verificar logs acima para detalhes do erro"
    echo ""
    echo "🚨 Ações de emergência:"
    echo "   1. Verificar conectividade com o banco"
    echo "   2. Confirmar permissões de ALTER TABLE"
    echo "   3. Verificar se as tabelas existem"
    exit 1
fi

echo ""
echo "📊 MIGRAÇÃO COMPLETA - $(date)"