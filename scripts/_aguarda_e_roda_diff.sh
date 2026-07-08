#!/usr/bin/env bash
# Espera o Python voltar (pós-restart do Repl), instala o parser e roda o diff.
set -u
cd /home/runner/workspace
for i in $(seq 1 80); do   # ~40 min de janela (80 x 30s)
  if python3 -c "import json" >/dev/null 2>&1; then
    echo "=== Python voltou (tentativa $i). Instalando parser de .mpp ==="
    python3 -m pip install --quiet mpxj jpype1 jdk4py 2>&1 | tail -5
    echo "=== Rodando diff .mpp x JSON ==="
    python3 scripts/diff_mpp_vs_json.py 2>&1
    exit 0
  fi
  sleep 30
done
echo "Timeout: Python não voltou em ~40 min. Reinicie o Repl e me avise."
exit 1
