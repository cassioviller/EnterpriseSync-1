#!/bin/bash

# Script para debugar problemas de dashboard em produção
# SIGE v8.0 - Debug Dashboard Produção

echo "🔍 SIGE v8.0 - Debug Dashboard Produção"
echo "========================================"

# Verificar se DATABASE_URL está definida
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL não está definida"
    exit 1
fi

echo "✅ Conectando ao banco de dados..."

# Verificar funcionários por admin_id
echo ""
echo "📊 FUNCIONÁRIOS POR ADMIN_ID:"
psql "$DATABASE_URL" -c "
SELECT 
    admin_id, 
    COUNT(*) as total, 
    COUNT(CASE WHEN ativo = true THEN 1 END) as ativos,
    STRING_AGG(nome, ', ') as nomes
FROM funcionario 
GROUP BY admin_id 
ORDER BY total DESC;
"

# Verificar obras por admin_id
echo ""
echo "🏗️ OBRAS POR ADMIN_ID:"
psql "$DATABASE_URL" -c "
SELECT 
    admin_id, 
    COUNT(*) as total,
    STRING_AGG(nome, ', ') as obras
FROM obra 
GROUP BY admin_id 
ORDER BY total DESC;
"

# Verificar registros de ponto do último mês
echo ""
echo "⏰ REGISTROS DE PONTO (Últimos 30 dias):"
psql "$DATABASE_URL" -c "
SELECT 
    COUNT(*) as total_registros,
    COUNT(DISTINCT funcionario_id) as funcionarios_diferentes,
    MIN(data_registro) as primeira_data,
    MAX(data_registro) as ultima_data
FROM registro_ponto 
WHERE data_registro >= CURRENT_DATE - INTERVAL '30 days';
"

# Verificar custos de veículos
echo ""
echo "🚗 CUSTOS DE VEÍCULOS (Últimos 30 dias):"
psql "$DATABASE_URL" -c "
SELECT 
    COUNT(*) as total_custos,
    COALESCE(SUM(valor), 0) as valor_total
FROM custo_veiculo 
WHERE data_custo >= CURRENT_DATE - INTERVAL '30 days';
" 2>/dev/null || echo "Tabela custo_veiculo não existe"

# Verificar alimentação
echo ""
echo "🍽️ REGISTROS DE ALIMENTAÇÃO (Últimos 30 dias):"
psql "$DATABASE_URL" -c "
SELECT 
    COUNT(*) as total_registros,
    COALESCE(SUM(valor), 0) as valor_total
FROM registro_alimentacao 
WHERE data >= CURRENT_DATE - INTERVAL '30 days';
" 2>/dev/null || echo "Tabela registro_alimentacao não existe"

# Verificar usuários
echo ""
echo "👤 USUÁRIOS CADASTRADOS:"
psql "$DATABASE_URL" -c "
SELECT 
    id,
    username,
    email,
    tipo_usuario,
    admin_id,
    ativo
FROM usuario 
ORDER BY id;
"

echo ""
echo "✅ Debug concluído!"
echo ""
echo "PRÓXIMOS PASSOS:"
echo "1. Verificar qual admin_id tem mais dados"
echo "2. Verificar se o usuário logado está com admin_id correto"
echo "3. Verificar se há dados suficientes para cálculos de KPIs"