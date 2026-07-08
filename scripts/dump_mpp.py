"""Dump completo de um .mpp -> JSON. Parser canônico de cronograma do repo.

Uso:
    python scripts/dump_mpp.py "CRONOGRAMA 06.07.mpp" [saida.json]

Sem o segundo argumento, escreve em stdout.

Dependências:  pip install mpxj jpype1
`mpxj` traz os .jar e sobe a JVM via JPype. É preciso um JRE/JDK COMPLETO:
o `jdk4py` (JRE em wheel) não inclui o charset MacRoman que os .mpp usam e
quebra com UnsupportedCharsetException — por isso procuramos um Temurin/OpenJDK
completo no sistema (inclusive no /nix/store dos ambientes Replit/Nix).
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import date


def _achar_java_home():
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    # JDK completo no /nix/store (Replit/Nix) — precisa ter bin/java.
    for padrao in ("*temurin*bin*", "*adoptopenjdk*hotspot*bin*", "*openjdk*bin*"):
        for d in sorted(glob.glob(f"/nix/store/{padrao}")):
            if os.path.exists(os.path.join(d, "bin", "java")):
                return d
    return None  # se houver Java no PATH, o JPype acha sozinho


def _d(v):
    if v is None:
        return None
    try:
        return date(v.getYear(), v.getMonthValue(), v.getDayOfMonth()).isoformat()
    except Exception:
        s = str(v)[:10]
        return s if s[:4].isdigit() else None


def _num(v):
    if v is None:
        return None
    try:
        return float(v.doubleValue() if hasattr(v, "doubleValue") else v)
    except Exception:
        try:
            return float(str(v))
        except Exception:
            return None


def dump(caminho):
    jh = _achar_java_home()
    if jh:
        os.environ["JAVA_HOME"] = jh
    import mpxj  # noqa: F401  (registra os .jar no classpath e sobe a JVM)
    import jpype
    import jpype.imports  # noqa: F401
    if not jpype.isJVMStarted():
        jpype.startJVM()
    from org.mpxj.reader import UniversalProjectReader

    project = UniversalProjectReader().read(caminho)
    out = []
    for t in project.getTasks():
        tid = t.getID()
        if tid is None:
            continue
        preds = []
        try:
            for r in (t.getPredecessors() or []):
                st = r.getPredecessorTask()
                if st is not None and st.getID() is not None:
                    preds.append(int(st.getID().intValue()))
        except Exception:
            pass
        dur = t.getDuration()
        out.append({
            "id": int(tid.intValue()),
            "outline": int(t.getOutlineLevel().intValue()) if t.getOutlineLevel() is not None else None,
            "nome": str(t.getName() or "").strip(),
            "inicio": _d(t.getStart()),
            "fim": _d(t.getFinish()),
            "dias": _num(dur.getDuration()) if dur is not None else None,
            "pct_fisico": _num(t.getPercentageComplete()),
            "predecessoras": preds,
            "resumo": bool(t.getSummary()),
        })
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: python scripts/dump_mpp.py "<arquivo.mpp>" [saida.json]')
    dados = dump(sys.argv[1])
    texto = json.dumps(dados, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"{len(dados)} tarefas -> {sys.argv[2]}")
    else:
        print(texto)


if __name__ == "__main__":
    main()
