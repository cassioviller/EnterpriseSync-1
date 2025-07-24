#!/bin/bash
# Script para manter fotos persistentes no deploy do SIGE
# Deve ser executado sempre após atualizações do sistema

echo "=== MANTENDO FOTOS PERSISTENTES - SIGE ==="
echo "Executando em: $(date)"

# Executar correção de fotos
echo "Corrigindo fotos dos funcionários..."
python3 corrigir_fotos_funcionarios.py

# Verificar se funcionou
if [ -f "fotos_corrigidas.log" ]; then
    echo "✅ Fotos corrigidas com sucesso!"
    cat fotos_corrigidas.log
else
    echo "❌ Erro ao corrigir fotos"
    exit 1
fi

echo "=== CONCLUÍDO ==="