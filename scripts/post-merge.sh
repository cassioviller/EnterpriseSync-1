#!/bin/bash
set -e

echo "[post-merge] Executando migracoes do GestaoCustoPai (Task #8)..."
python migrate_gestao_custos.py

echo "[post-merge] Concluido."
