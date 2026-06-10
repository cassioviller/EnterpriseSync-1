import os, sys
WS = "/home/runner/workspace"
sys.path.insert(0, WS)
os.chdir(WS)
from datetime import date, datetime
import main
from main import app
from services.importacao_excel import ImportacaoFluxoCaixa

XLSX = os.path.join(WS, "1. FLUXO DE CAIXA_Veks Engenharia.xlsx")
with app.app_context():
    svc = ImportacaoFluxoCaixa()
    print("[1] processando 2026-01-01 a 2026-06-05...", flush=True)
    res = svc.processar(XLSX, 1, data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 5))
    saidas = res['saidas_auto'] + res['saidas_manual']
    entradas = res['entradas']
    FB = {'Outras Saídas', 'Outros Recebimentos'}
    sem_cat = [r for r in saidas if r.get('categoria_nome') in FB]
    print(f"[2] preview: {len(saidas)} saídas ({len(sem_cat)} sem classificar) + {len(entradas)} entradas", flush=True)
    batch = "veks2026_" + datetime.utcnow().strftime("%H%M%S")
    dados = {'entradas': entradas, 'saidas': saidas, 'batch_id': batch}
    print("[3] SALVANDO (importar)...", flush=True)
    r = svc.importar(dados, 1)
    print("[4] RESULTADO DO SAVE:", flush=True)
    for k in ('n_entradas', 'n_saidas', 'n_fluxo', 'n_conta_pagar', 'n_apenas_pagamento',
              'n_fornecedores_criados', 'duplicados'):
        if k in r:
            print(f"    {k}: {r[k]}", flush=True)
    erros = r.get('erros') or []
    print(f"    erros: {len(erros)}", flush=True)
    for e in erros[:5]:
        print("      -", str(e)[:140], flush=True)
    from models import FluxoCaixa, CategoriaFluxoCaixa, ContaPagar
    from collections import Counter
    fc_batch = FluxoCaixa.query.filter_by(admin_id=1, import_batch_id=batch).all()
    catmap = {c.id: c.nome for c in CategoriaFluxoCaixa.query.filter_by(admin_id=1).all()}
    cnt = Counter(catmap.get(f.categoria_fluxo_caixa_id, '(sem categoria_fluxo_caixa_id)') for f in fc_batch)
    print(f"[5] FluxoCaixa criados no batch: {len(fc_batch)}", flush=True)
    for nome, n in cnt.most_common(10):
        print(f"      {n:5}  {nome}", flush=True)
    print("BATCH=" + batch, flush=True)
print("FIM", flush=True)
