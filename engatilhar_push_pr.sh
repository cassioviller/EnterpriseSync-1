#!/usr/bin/env bash
# Engatilhado por Claude (16/06/2026). Rode DEPOIS de `gh auth login`:
#     bash engatilhar_push_pr.sh
# Faz push do branch de hotfix e abre o PR contra main.
set -euo pipefail

cd /home/runner/workspace
BRANCH="hotfix/rdo-edicao-funcionario"

# 0) Sanidade: precisa do gh autenticado
if ! gh auth status >/dev/null 2>&1; then
  echo "❌ gh não autenticado. Rode primeiro:  gh auth login"
  exit 1
fi

# 1) Garantir branch certo
git checkout "$BRANCH"

# 2) Empurrar os 4 commits do hotfix DIRETO para a main remota (fast-forward).
#    Sem PR, conforme pedido ("coloque tudo na main").
echo "Empurrando $BRANCH -> origin/main ..."
git push origin "${BRANCH}:main"

echo "✅ Hotfix enviado para origin/main. O deploy do EasyPanel pode ser disparado."
