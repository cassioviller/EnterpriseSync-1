#!/bin/bash
# Remove locks travados
rm -f .git/index.lock
rm -f .git/ORIG_HEAD.lock

# Marca todos os conflitos como resolvidos
git add alimentacao_views.py manual/33_alimentacao.md portal_obras_views.py scripts/seed_demo_alfa.py templates/dashboard.html templates/financeiro/contas_pagar.html templates/portal/portal_obra.html views/almoxarifado/__init__.py views/almoxarifado/api.py views/almoxarifado/categorias.py views/almoxarifado/dashboard.py views/almoxarifado/fornecedores.py views/almoxarifado/itens.py views/almoxarifado/movimentos.py views/almoxarifado/relatorios.py views/rdo.py

# Finaliza o merge
git commit --no-edit

echo "============================="
echo "Merge concluido com sucesso!"
echo "============================="
