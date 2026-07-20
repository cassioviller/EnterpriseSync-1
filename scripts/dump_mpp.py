"""Dump de cronograma -> JSON legado de 9 campos. CLI fino sobre o M03.

Uso:
    python scripts/dump_mpp.py "CRONOGRAMA 06.07.mpp" [saida.json]

Sem o segundo argumento, escreve em stdout. Aceita `.mpp` (worker MPXJ em
subprocess, requer Java — ver services/mpp_parser_worker.py) e `.xml`
(MSPDI, stdlib, sem Java).

Desde o M03 (Task 3) o parse canônico vive em
`services.mpp_parser.parse_cronograma` (contrato completo com uid/wbs/
marco/vínculos tipados); este script apenas PROJETA aquele contrato para o
shape histórico de 9 campos consumido por `rebuild_baia_from_0607_mpp.py`
e `verificar_paridade_mspdi.py`. Compatibilidade provada por diff da saída
antiga vs nova sobre `CRONOGRAMA 06.07.mpp` (idêntica byte a byte).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mpp_parser import _achar_java_home, parse_cronograma  # noqa: E402,F401
# _achar_java_home é re-exportado porque scripts/verificar_paridade_mspdi.py
# (e o histórico de uso deste módulo) o importa daqui.


def _projetar_legado(tarefa: dict) -> dict:
    """Contrato do M03 → shape legado de 9 campos (spec §14)."""
    return {
        "id": tarefa["id"],
        "outline": tarefa["outline"],
        "nome": tarefa["nome"],
        "inicio": tarefa["inicio"],
        "fim": tarefa["fim"],
        "dias": tarefa["dias"],
        "pct_fisico": tarefa["pct_project"],
        "predecessoras": [p["id"] for p in tarefa["predecessoras"]],
        "resumo": tarefa["resumo"],
    }


def dump(caminho):
    """Lista de tarefas no shape legado — mesma assinatura/saída de sempre."""
    return [_projetar_legado(t) for t in parse_cronograma(caminho)["tarefas"]]


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
