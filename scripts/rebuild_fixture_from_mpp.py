"""Reconstrói tests/fixtures/cronograma_fisico_financeiro_baias.json a partir de
um dump do MS Project (scripts/dump_mpp.py) — SEM tocar no financeiro.

O JSON tem duas visões amarradas pelo id da tarefa:
  • cronograma_tarefas : dump do MS Project (datas + %físico)      ← substituído
  • eap[].cronograma.tarefas_mpp : quais tarefas fasear cada etapa  ← remapeado

Custos (veks/fat/peso_pct/itens), medições, fluxo de caixa, resumo e parâmetros
vêm da Planilha de Custos e são PRESERVADOS verbatim.

Uso:  python scripts/rebuild_fixture_from_mpp.py <dump_mpp.json>
"""
from __future__ import annotations

import json
import sys

FIXTURE = "tests/fixtures/cronograma_fisico_financeiro_baias.json"
FONTE_MPP = "CRONOGRAMA_06_07.mpp (MS Project — cronograma físico)"

# --- Mapa etapa de custo (código EAP) -> ids das tarefas do cronograma novo ---
# Estrutura nova: Baias = Galpão B (9) + Galpão A (53), cada um com o mesmo
# conjunto de subetapas. Cada etapa de custo agrega as folhas dos DOIS galpões.
MAPA = {
    "PRELIM":    [2, 3, 4, 5, 7],
    # Fundação: todas as folhas de fundação dos dois galpões, menos içamento de
    # pilares (-> ESTLSF) e assentamento de moledo (-> MOLEDO).
    "FUND":      [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26,
                  55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 70, 71],
    "ESTMET":    [29, 30, 31, 74, 75, 76],       # fabricação aço + estrutura metálica
    "ESTLSF":    [24, 36, 37, 69, 81, 82],        # painelização/verticalização + içamento
    "COBERT":    [32, 77],                          # telhado shingle
    "FECHA":     [42, 43, 44, 87, 88, 89],         # plaqueamento madeira/cimentícia + basecoat
    "PINT":      [33, 45, 78, 90],                 # pintura estrutura telhado + stain
    "MOLEDO":    [27, 46, 72, 91],                 # assentamento + resina moledo
    "PORTAO":    [51, 52, 96, 97],                 # produção + instalação portões
    "ELET":      [40, 48, 49, 85, 93, 94],         # infra elétrica + pontos
    "HIDRO":     [39, 84],                          # infra hidráulica
    # Indiretos/gestão (transversal, período): dreno da fazenda + desmobilização.
    "INDIRETOS": [34, 79, 99, 100],
}


def _wavg(pcts_dias):
    """Média de %físico ponderada por duração (dias). 0 se sem peso."""
    tot = sum(d for _, d in pcts_dias) or 0
    if tot == 0:
        return 0.0
    return round(sum(p * d for p, d in pcts_dias) / tot, 1)


def main():
    dump_path = sys.argv[1]
    dump = json.load(open(dump_path, encoding="utf-8"))
    by_id = {t["id"]: t for t in dump}

    fx = json.load(open(FIXTURE, encoding="utf-8"))

    # 1) cronograma_tarefas = dump do MS Project (mantém o formato do fixture) --
    cron = []
    for t in dump:
        cron.append({
            "id": t["id"],
            "nivel": t["outline"],
            "nome": t["nome"],
            "inicio": t["inicio"],
            "fim": t["fim"],
            "dias": t["dias"],
            "pct_fisico": t.get("pct_fisico") or 0.0,
            "predecessoras": t.get("predecessoras", []),
            "marco": (t.get("dias") or 0) == 0,
            "resumo": t.get("resumo", False),
        })
    fx["cronograma_tarefas"] = cron

    # 2) Remapeia cada etapa de custo: tarefas_mpp + datas + %físico base ------
    faltando = []
    for etapa in fx["eap"]:
        cod = etapa["codigo"]
        ids = MAPA.get(cod, [])
        if not ids:
            faltando.append(cod)
        etapa.setdefault("cronograma", {})
        etapa["cronograma"]["tarefas_mpp"] = ids
        folhas = [by_id[i] for i in ids if i in by_id]
        inicios = [f["inicio"] for f in folhas if f["inicio"]]
        fins = [f["fim"] for f in folhas if f["fim"]]
        if inicios:
            etapa["cronograma"]["inicio"] = min(inicios)
        if fins:
            etapa["cronograma"]["fim"] = max(fins)
        # %físico base = média ponderada por duração das folhas (do MS Project)
        etapa["cronograma"]["pct_fisico"] = _wavg(
            [(f.get("pct_fisico") or 0.0, f.get("dias") or 1) for f in folhas])

    # 3) Metadados / datas de topo -------------------------------------------
    fim_obra = max(t["fim"] for t in dump if t["fim"])
    ini_obra = min(t["inicio"] for t in dump if t["inicio"])
    fx["contrato"]["data_fim_cronograma"] = fim_obra
    fx.setdefault("_meta", {})
    fontes = fx["_meta"].get("fontes", [])
    fontes = [FONTE_MPP if "mpp" in f.lower() else f for f in fontes]
    fx["_meta"]["fontes"] = fontes
    fx["_meta"]["cronograma_atualizado_em"] = "2026-07-07"
    fx["_meta"]["cronograma_janela"] = f"{ini_obra} → {fim_obra}"

    json.dump(fx, open(FIXTURE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Relatório
    print(f"cronograma_tarefas: {len(cron)} tarefas")
    print(f"obra: {ini_obra} → {fim_obra}")
    if faltando:
        print("!! etapas SEM mapeamento:", faltando)
    print("\netapa            base%  janela                 nº folhas")
    for e in fx["eap"]:
        c = e["cronograma"]
        print(f"  {e['codigo']:<10} {c['pct_fisico']:>5}  "
              f"{c.get('inicio')}→{c.get('fim')}  {len(c['tarefas_mpp'])}")


if __name__ == "__main__":
    main()
