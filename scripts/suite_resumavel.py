#!/usr/bin/env python3
"""Roda a suíte em chunks, com progresso durável e veredito honesto.

Por que este script existe
--------------------------
A suíte completa leva ~46 min num container que reinicia sozinho. Em 01/09
três gates e uma suíte morreram no meio, e o que sobrou foi um log truncado.
Pior: o registro escrito a partir dele dizia "interrompida a ~18% com 2 FAILED"
quando o log real dizia 62% e 7 FAILED — um placar parcial virou placar, e uma
decisão foi tomada em cima dele.

Este runner ataca as duas metades disso:

  1. **Progresso durável.** A suíte é dividida em chunks; cada chunk roda em
     processo próprio e grava o resultado em disco assim que termina. Rodar o
     mesmo comando de novo pula o que já tem registro. Uma morte custa um
     chunk, não 46 minutos.

  2. **Veredito que não mente.** Faltando qualquer chunk, o veredito é
     INCOMPLETO e o código de saída é ≠ 0. Nunca existe "somar o que veio e
     parecer verde" — que foi exatamente o modo como o registro de 01/09
     enganou quem o leu.

Isolamento de processo não é só sobrevivência: em 02/09 uma fixture de sessão
segurando `sync_playwright()` derrubou 80 testes de browser em outros arquivos
(ver `tests/test_contrato_isolamento_playwright.py`). Por isso cada arquivo de
browser roda no seu próprio chunk.

⚠️ **O que este runner NÃO faz:** rodar tudo num processo só. Isolar processo
esconde bugs de ORDEM — um teste que só falha depois de outro passa a passar
aqui. Este runner é o cavalo de trabalho não supervisionado; a rodada
monolítica (`bash run_tests.sh --suite`) continua sendo a checagem de ordem, e
as duas dizem coisas diferentes de propósito.

Uso
---
    setsid nohup python3 scripts/suite_resumavel.py > tests/reports/runner.log 2>&1 &

Morreu? Rode de novo o mesmo comando: retoma de onde parou.
Recomeçar do zero: `--do-zero` (apaga o ledger da rodada).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_TESTES_PADRAO = os.path.join(RAIZ, "tests")
LEDGER_PADRAO = os.path.join(RAIZ, "tests", "reports", "ledger")

# Arquivos de gate são rápidos e centenas; um processo pytest por arquivo
# custaria ~4 s de import da app cada, ~17 min só de overhead. Agrupados em 20,
# o overhead cai a ~1 min e a granularidade de retomada segue boa (um grupo
# perdido custa segundos, não minutos).
TAMANHO_CHUNK_GATE = 20

CHAVES_PLACAR = ("passed", "failed", "skipped", "xfailed", "errors")


@dataclass(frozen=True)
class Chunk:
    nome: str
    arquivos: List[str] = field(default_factory=list)


# ── leitura do placar ────────────────────────────────────────────────────────

# O resumo do pytest vem em duas formas: com "=" em volta (modo normal/-v) e
# sem eles (modo -q). Exigir os "=" faria toda rodada quieta parecer não
# terminada. O que identifica um resumo nas duas formas é a dupla "in <n>s" +
# pelo menos uma contagem — e é isso que se exige.
_DURACAO = re.compile(r"\bin\s[\d.]+s\b")
_CONTAGEM = re.compile(r"(\d+)\s+(failed|passed|skipped|xfailed|errors?)\b")


def parse_placar(linha: str) -> Optional[Dict[str, int]]:
    """Lê a linha de resumo do pytest. Devolve None se não for uma.

    O None é a parte que importa: uma linha qualquer NÃO pode virar um placar
    de zeros, porque zeros somam igual a "nada falhou". Um log truncado no meio
    não tem linha de resumo, e é assim que se sabe que a rodada não terminou.
    """
    if not linha or not _DURACAO.search(linha):
        return None
    contagens = _CONTAGEM.findall(linha)
    if not contagens:
        return None
    placar = {chave: 0 for chave in CHAVES_PLACAR}
    for quantidade, rotulo in contagens:
        chave = "errors" if rotulo.startswith("error") else rotulo
        placar[chave] = int(quantidade)
    return placar


def placar_do_log(caminho_log: str) -> Optional[Dict[str, int]]:
    """Varre o log de trás para frente atrás da linha de resumo."""
    try:
        with open(caminho_log, encoding="utf-8", errors="replace") as fh:
            linhas = fh.readlines()
    except OSError:
        return None
    for linha in reversed(linhas):
        placar = parse_placar(linha)
        if placar is not None:
            return placar
    return None


# ── divisão em chunks ────────────────────────────────────────────────────────

def _usa_playwright(caminho: str) -> bool:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            return "sync_playwright" in fh.read()
    except OSError:
        return False


def descobrir_chunks(dir_testes: str = DIR_TESTES_PADRAO,
                     tamanho_chunk_gate: int = TAMANHO_CHUNK_GATE) -> List[Chunk]:
    """Chunks de gate primeiro (baratos, sinal cedo), browser depois — um por
    arquivo, porque é o isolamento de processo que impede um arquivo de
    derrubar o próximo."""
    arquivos = sorted(
        n for n in os.listdir(dir_testes)
        if n.startswith("test_") and n.endswith(".py")
    )
    browser, resto = [], []
    for nome in arquivos:
        (browser if _usa_playwright(os.path.join(dir_testes, nome)) else resto).append(nome)

    chunks: List[Chunk] = []
    for i in range(0, len(resto), tamanho_chunk_gate):
        chunks.append(Chunk(f"gate_{i // tamanho_chunk_gate:02d}", resto[i:i + tamanho_chunk_gate]))
    chunks.extend(Chunk(nome[:-3], [nome]) for nome in browser)
    return chunks


# ── retomada ─────────────────────────────────────────────────────────────────

def _caminho_registro(dir_done: str, nome_chunk: str) -> str:
    return os.path.join(dir_done, f"{nome_chunk}.json")


def _registro_cobre(caminho: str, chunk: Chunk) -> bool:
    """Um registro só vale para a lista de arquivos que ele gravou.

    Os nomes de chunk são posicionais (gate_00, gate_01...): acrescentar ou
    remover um arquivo de teste desloca a numeração, e o registro de ontem
    passa a ter o nome de um chunk que hoje cobre OUTROS arquivos. Confiar no
    nome faria a retomada pular um chunk que nunca rodou, e o veredito diria
    "completo" sobre uma rodada furada.
    """
    try:
        with open(caminho, encoding="utf-8") as fh:
            registro = json.load(fh)
    except (OSError, ValueError):
        return False
    return list(registro.get("arquivos", [])) == list(chunk.arquivos)


def chunks_pendentes(chunks: List[Chunk], dir_done: str) -> List[Chunk]:
    return [c for c in chunks
            if not _registro_cobre(_caminho_registro(dir_done, c.nome), c)]


def registros_gravados(dir_done: str) -> List[dict]:
    if not os.path.isdir(dir_done):
        return []
    registros = []
    for nome in sorted(os.listdir(dir_done)):
        if not nome.endswith(".json"):
            continue
        try:
            with open(os.path.join(dir_done, nome), encoding="utf-8") as fh:
                registros.append(json.load(fh))
        except (OSError, ValueError):
            continue
    return registros


# ── veredito ─────────────────────────────────────────────────────────────────

def agregar(registros: List[dict]) -> Dict[str, int]:
    total = {chave: 0 for chave in CHAVES_PLACAR}
    for registro in registros:
        for chave in CHAVES_PLACAR:
            total[chave] += registro.get("placar", {}).get(chave, 0)
    return total


def veredito(total_de_chunks: int, registros: List[dict]):
    """Devolve (texto, código de saída).

    Três estados, e só um deles é sucesso:
      • falta chunk   → INCOMPLETO, código 2. Não há placar, há rodada parcial.
      • completo, com falha/erro → placar, código 1, e a palavra SUCESSO não
        aparece em lugar nenhum.
      • completo e limpo → SUCESSO, código 0.
    """
    total = agregar(registros)
    placar = ", ".join(f"{total[c]} {c}" for c in CHAVES_PLACAR if total[c] or c == "passed")
    feitos = len(registros)

    if feitos < total_de_chunks:
        faltando = total_de_chunks - feitos
        texto = (
            f"INCOMPLETO — {feitos} de {total_de_chunks} chunks concluídos "
            f"({faltando} faltando).\n"
            f"Placar PARCIAL, que não é placar: {placar}\n"
            "Rode o mesmo comando de novo para retomar de onde parou."
        )
        return texto, 2

    if total["failed"] or total["errors"]:
        return (f"COMPLETO E VERMELHO — {total_de_chunks} chunks.\n{placar}"), 1

    return (f"SUCESSO — {total_de_chunks} chunks, rodada completa.\n{placar}"), 0


# ── execução ─────────────────────────────────────────────────────────────────

def rodar_chunk(chunk: Chunk, dir_testes: str, dir_logs: str) -> dict:
    caminho_log = os.path.join(dir_logs, f"{chunk.nome}.log")
    alvos = [os.path.join(os.path.relpath(dir_testes, RAIZ), a) for a in chunk.arquivos]
    inicio = time.time()
    with open(caminho_log, "w", encoding="utf-8") as saida:
        processo = subprocess.run(
            ["bash", "run_tests.sh", "--arquivos", *alvos],
            cwd=RAIZ, stdout=saida, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    placar = placar_do_log(caminho_log)
    return {
        "chunk": chunk.nome,
        "arquivos": chunk.arquivos,
        "placar": placar,
        "exit_code": processo.returncode,
        "segundos": round(time.time() - inicio, 1),
        # Sem linha de resumo no log, o chunk NÃO terminou — mesmo que o
        # processo tenha saído. Fica sem registro e é retomado na próxima.
        "concluido": placar is not None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", default=LEDGER_PADRAO)
    parser.add_argument("--dir-testes", default=DIR_TESTES_PADRAO)
    parser.add_argument("--tamanho-chunk", type=int, default=TAMANHO_CHUNK_GATE,
                        help="arquivos por chunk de gate (browser é sempre 1 por chunk)")
    parser.add_argument("--do-zero", action="store_true",
                        help="apaga o ledger e recomeça a rodada")
    args = parser.parse_args(argv)

    dir_done = os.path.join(args.ledger, "done")
    dir_logs = os.path.join(args.ledger, "logs")
    if args.do_zero:
        import shutil
        shutil.rmtree(args.ledger, ignore_errors=True)
    os.makedirs(dir_done, exist_ok=True)
    os.makedirs(dir_logs, exist_ok=True)

    chunks = descobrir_chunks(args.dir_testes, args.tamanho_chunk)
    pendentes = chunks_pendentes(chunks, dir_done)
    print(f"[runner] {len(chunks)} chunks; {len(pendentes)} pendentes; ledger={args.ledger}",
          flush=True)

    for indice, chunk in enumerate(pendentes, 1):
        print(f"[runner] ({indice}/{len(pendentes)}) {chunk.nome} "
              f"— {len(chunk.arquivos)} arquivo(s)", flush=True)
        registro = rodar_chunk(chunk, args.dir_testes, dir_logs)
        if not registro["concluido"]:
            # Sem placar não se grava registro: gravar seria transformar uma
            # morte em "chunk feito", que é a mentira que este runner existe
            # para impedir.
            print(f"[runner] {chunk.nome} NÃO concluiu (sem linha de resumo) — "
                  f"fica pendente. Log: {dir_logs}/{chunk.nome}.log", flush=True)
            continue
        with open(_caminho_registro(dir_done, chunk.nome), "w", encoding="utf-8") as fh:
            json.dump(registro, fh, ensure_ascii=False, indent=2)
        p = registro["placar"]
        print(f"[runner] {chunk.nome}: {p['passed']} passed, {p['failed']} failed, "
              f"{p['errors']} errors ({registro['segundos']}s)", flush=True)

    texto, codigo = veredito(len(chunks), registros_gravados(dir_done))
    caminho_veredito = os.path.join(args.ledger, "veredito.txt")
    with open(caminho_veredito, "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")
    print("\n" + texto, flush=True)
    print(f"[runner] veredito em {caminho_veredito}", flush=True)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
