"""Diff das datas do cronograma: CRONOGRAMA 16.06 (1).mpp  ×  JSON importado.

Objetivo: provar (ou refutar) que a tabela `cronograma_tarefas` do JSON
(usada para fasear as etapas normais) está fiel ao MS Project.

Uso:
    python scripts/diff_mpp_vs_json.py

Dependências do parser de .mpp (instalar se faltar — o repo não usa Java):
    pip install mpxj jpype1 jdk4py
`mpxj` lê .mpp via JPype; `jdk4py` provê um JRE em wheel (sem precisar de Java
no sistema). O script aponta JAVA_HOME para o jdk4py automaticamente.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

MPP = "CRONOGRAMA 16.06 (1).mpp"
JSON = "tests/fixtures/cronograma_fisico_financeiro_baias.json"


def _ensure_jvm():
    """Garante um JRE para o JPype/mpxj. Usa jdk4py se o sistema não tem Java."""
    if not os.environ.get("JAVA_HOME"):
        try:
            from jdk4py import JAVA_HOME  # type: ignore
            os.environ["JAVA_HOME"] = str(JAVA_HOME)
        except Exception:
            pass  # se houver Java no sistema, segue


def parse_mpp(caminho: str) -> dict[int, dict]:
    """Retorna {task_id: {'nome', 'inicio': date|None, 'fim': date|None}}."""
    _ensure_jvm()
    import jpype  # noqa
    from mpxj import UniversalProjectReader  # type: ignore

    project = UniversalProjectReader().read(caminho)
    out: dict[int, dict] = {}

    def _d(v):
        if v is None:
            return None
        # mpxj devolve java.time.LocalDateTime; tem year/month/day
        try:
            return date(v.getYear(), v.getMonthValue(), v.getDayOfMonth())
        except Exception:
            s = str(v)[:10]
            return date.fromisoformat(s) if s[:4].isdigit() else None

    for t in project.getTasks():
        tid = t.getID()
        if tid is None:
            continue
        out[int(tid.intValue() if hasattr(tid, "intValue") else tid)] = {
            "nome": str(t.getName() or "").strip(),
            "inicio": _d(t.getStart()),
            "fim": _d(t.getFinish()),
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
    if not os.path.exists(MPP):
        sys.exit(f"não achei {MPP}")
    mpp = parse_mpp(MPP)
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
