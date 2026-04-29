#!/bin/bash
set -e

echo "[post-merge] Executando migracoes do GestaoCustoPai (Task #8)..."
python migrate_gestao_custos.py

echo "[post-merge] Task #18 — colunas itens_inclusos/itens_exclusos em orcamento_item e proposta_itens..."
psql "$DATABASE_URL" -c "ALTER TABLE orcamento_item ADD COLUMN IF NOT EXISTS itens_inclusos TEXT, ADD COLUMN IF NOT EXISTS itens_exclusos TEXT; ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS itens_inclusos TEXT, ADD COLUMN IF NOT EXISTS itens_exclusos TEXT;"

echo "[post-merge] Concluido."
