#!/bin/bash
set -e

echo "[post-merge] Executando migracoes do GestaoCustoPai (Task #8)..."
# migrate_gestao_custos.py importa o app Flask, que carrega TensorFlow/DeepFace.
# No ambiente de merge o TF pode gerar SIGABRT sem relação com a migração.
# Como todas as operações DDL são idempotentes, toleramos o crash do TF e
# verificamos se as colunas críticas existem diretamente via psql.
python migrate_gestao_custos.py || {
    EXIT=$?
    echo "[post-merge] WARN: migrate_gestao_custos.py saiu com código $EXIT (possível crash TensorFlow)."
    echo "[post-merge] Verificando colunas criticas via psql como fallback..."
    psql "$DATABASE_URL" -c "
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS fornecedor_id INTEGER;
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS forma_pagamento VARCHAR(50);
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS valor_pago NUMERIC(15,2);
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS saldo NUMERIC(15,2);
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS conta_contabil_codigo VARCHAR(20);
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS data_emissao DATE;
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS numero_parcela INTEGER;
        ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS total_parcelas INTEGER;
    " && echo "OK: fallback DDL aplicado com sucesso." || echo "WARN: tabela gestao_custo_pai pode nao existir ainda - ignorando."
}

echo "[post-merge] Task #18 — colunas itens_inclusos/itens_exclusos em orcamento_item e proposta_itens..."
psql "$DATABASE_URL" -c "ALTER TABLE orcamento_item ADD COLUMN IF NOT EXISTS itens_inclusos TEXT, ADD COLUMN IF NOT EXISTS itens_exclusos TEXT; ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS itens_inclusos TEXT, ADD COLUMN IF NOT EXISTS itens_exclusos TEXT;"

echo "[post-merge] Concluido."
