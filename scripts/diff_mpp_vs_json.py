"""Diff das datas do cronograma: CRONOGRAMA 06.07.mpp  ×  JSON importado.

Objetivo: provar (ou refutar) que a tabela `cronograma_tarefas` do JSON
(usada para fasear as etapas normais) está fiel ao MS Project.

Uso:
    python scripts/diff_mpp_vs_json.py [caminho.mpp]

Dependências do parser de .mpp:  pip install mpxj jpype1
O parsing fica em scripts/dump_mpp.py (acha um JDK completo automaticamente —
o jdk4py não serve porque não tem o charset MacRoman dos .mpp).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MPP = "CRONOGRAMA 06.07.mpp"
JSON = "tests/fixtures/cronograma_fisico_financeiro_baias.json"


def parse_mpp(caminho: str) -> dict[int, dict]:
    """Retorna {task_id: {'nome', 'inicio': date|None, 'fim': date|None}}."""
    from scripts.dump_mpp import dump

    def _iso(s):
        return date.fromisoformat(s) if s else None

    out: dict[int, dict] = {}
    for t in dump(caminho):
        out[int(t["id"])] = {
            "nome": t["nome"],
            "inicio": _iso(t["inicio"]),
            "fim": _iso(t["fim"]),
        }
    return out


def parse_json(caminho: str) -> dict[int, dict]:
    d = json.load(open(caminho, encoding="utf-8"))
    out: dict[int, dict] = {}
    for t in d.get("cronograma_tarefas", []):
        out[int(t["id"])] = {
            "nome": (t.get("nome") or "").strip(),
            "inicio": _iso(t.get("inicio")),
            "fim": _iso(t.get("fim")),
        }
    return out


def _iso(s):
    if not s:
        return None
    return date.fromisoformat(str(s)[:10])


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else MPP
    if not os.path.exists(caminho):
        sys.exit(f"não achei {caminho}")
    mpp = parse_mpp(caminho)
    js = parse_json(JSON)
    print(f"MPP: {len(mpp)} tarefas | JSON: {len(js)} tarefas\n")

    ids = sorted(set(mpp) | set(js))
    divergencias = 0
    for i in ids:
        m = mpp.get(i)
        j = js.get(i)
        if m is None:
            print(f"  [{i:>3}] SÓ NO JSON: {j['nome']}")
            divergencias += 1
            continue
        if j is None:
            print(f"  [{i:>3}] SÓ NO MPP : {m['nome']}")
            divergencias += 1
            continue
        di = "✓" if m["inicio"] == j["inicio"] else f"✗ mpp={m['inicio']} json={j['inicio']}"
        df = "✓" if m["fim"] == j["fim"] else f"✗ mpp={m['fim']} json={j['fim']}"
        if di != "✓" or df != "✓":
            divergencias += 1
            print(f"  [{i:>3}] {m['nome'][:34]:34} início:{di}  fim:{df}")

    print()
    if divergencias == 0:
        print("✅ FIEL: todas as datas do JSON batem com o .mpp.")
    else:
        print(f"⚠️ {divergencias} divergência(s) — corrigir o JSON pelas datas do .mpp.")


if __name__ == "__main__":
    main()
