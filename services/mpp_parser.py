"""Despacho de parse de cronograma por extensão (M03, adendo §4.1).

- `.xml` (MSPDI, "Salvar como → XML" do MS Project) → services/mspdi_parser.py,
  stdlib in-process — não há JVM para isolar, e produção funciona sem Java.
- `.mpp` → worker MPXJ em subprocess isolado (services/mpp_parser_worker.py):
  a JVM do JPype nunca entra no processo do gunicorn; crash, OOM ou
  travamento viram MppParserError tipado, jamais derrubam a app.

Ambos os caminhos devolvem o MESMO contrato JSON (plano M03, §"Contrato de
saída do parser"): {"projeto": {...}, "tarefas": [...]}.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys

from services.mspdi_parser import parse_mspdi

# Instrução acionável quando não há JVM (adendo §4.1 — texto obrigatório).
MSG_SEM_JAVA = ("Este servidor não lê .mpp. No MS Project: Arquivo → "
                "Salvar como → tipo 'XML' (.xml), e suba o .xml.")

# Trechos de stderr do worker que identificam .mpp inválido/corrompido.
# Medido em 2026-07-20 (worker sobre OLE2 adulterado, texto puro e .mpp
# truncado): nos 3 casos o UniversalProjectReader devolve null sem levantar,
# e o marcador que dispara é o RuntimeError do próprio worker ("não
# reconhecido pelo MPXJ"). Os nomes de exceção POI/MPXJ ficam como defesa
# para corrupções que passem do sniffing do reader.
_MARCADORES_CORROMPIDO = (
    'não reconhecido pelo MPXJ',  # UniversalProjectReader devolveu null (medido)
    'NotOLE2FileException',       # magic bytes não são OLE2
    'Invalid header signature',   # idem, mensagem do POI
    'IndexOutOfBoundsException',  # OLE2 truncado/adulterado
    'FileFormatException',        # container OLE2 malformado
    'MPXJException',              # "Invalid file format" e afins
)

_STDERR_MAX = 2000
_RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOTIVOS = ('java_indisponivel', 'arquivo_corrompido', 'timeout',
           'erro_mpxj', 'extensao_invalida', 'erro_parse')


class MppParserError(Exception):
    """Falha tipada de parse de cronograma.

    `motivo` ∈ MOTIVOS; `mensagem` é o texto exibível ao usuário.
    """

    def __init__(self, motivo: str, mensagem: str):
        super().__init__(mensagem)
        self.motivo = motivo
        self.mensagem = mensagem


def _achar_java_home():
    """Lógica de scripts/dump_mpp.py: JAVA_HOME ou JDK completo no /nix/store.

    O jdk4py (JRE em wheel) não inclui o charset MacRoman que os .mpp usam,
    por isso procuramos um Temurin/OpenJDK completo no sistema.
    """
    if os.environ.get('JAVA_HOME'):
        return os.environ['JAVA_HOME']
    for padrao in ('*temurin*bin*', '*adoptopenjdk*hotspot*bin*', '*openjdk*bin*'):
        for d in sorted(glob.glob(f'/nix/store/{padrao}')):
            if os.path.exists(os.path.join(d, 'bin', 'java')):
                return d
    return None  # se houver Java no PATH, o JPype acha sozinho


def java_disponivel() -> bool:
    """True se o worker MPXJ tem JVM para subir (JAVA_HOME/nix ou PATH)."""
    return _achar_java_home() is not None or shutil.which('java') is not None


def parse_cronograma(caminho: str, timeout_s: float = 120) -> dict:
    """Parseia `.xml` (MSPDI) ou `.mpp` para o contrato do M03.

    Levanta MppParserError com motivo tipado em qualquer falha.
    """
    ext = os.path.splitext(caminho)[1].lower()

    if ext == '.xml':
        try:
            return parse_mspdi(caminho)
        except MppParserError:
            raise
        except Exception as exc:  # noqa: BLE001 — contrato: falha tipada, nunca crua
            # MSPDI bem-formado mas com conteúdo inválido (ex.: <ID>abc</ID> →
            # ValueError) ou entidade barrada pelo defusedxml. Sem este wrap a
            # exceção sobe até a rota como HTTP 500 e deixa arquivo órfão.
            raise MppParserError(
                'erro_parse',
                f'não foi possível interpretar o cronograma MSPDI ({exc}).',
            ) from exc

    if ext != '.mpp':
        raise MppParserError(
            'extensao_invalida',
            f'extensão {ext or "(sem extensão)"!r} não suportada — envie o '
            f'cronograma como .xml (MSPDI) ou .mpp.',
        )

    if not java_disponivel():
        raise MppParserError('java_indisponivel', MSG_SEM_JAVA)

    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'services.mpp_parser_worker',
             os.path.abspath(caminho)],
            capture_output=True, text=True, timeout=timeout_s,
            cwd=_RAIZ_PROJETO,  # `-m services...` precisa da raiz no sys.path
        )
    except subprocess.TimeoutExpired:
        raise MppParserError(
            'timeout',
            f'o parse do .mpp excedeu {timeout_s}s e o worker MPXJ foi '
            f'abortado. Tente exportar como XML no MS Project '
            f'(Arquivo → Salvar como → XML).',
        )

    if proc.returncode != 0:
        stderr = (proc.stderr or '').strip()[:_STDERR_MAX]
        if any(m in stderr for m in _MARCADORES_CORROMPIDO):
            raise MppParserError(
                'arquivo_corrompido',
                f'o arquivo .mpp está corrompido ou não é um MS Project '
                f'válido: {stderr}',
            )
        raise MppParserError('erro_mpxj',
                             f'falha do MPXJ ao ler o .mpp: {stderr}')

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        # Worker saiu 0 mas não emitiu JSON válido (stdout vazio ou ruído da
        # JVM que vazou o fd real). Mantém a garantia do contrato: todo
        # caminho de falha sai como MppParserError, nunca como exceção crua.
        trecho = (proc.stdout or '').strip()[:_STDERR_MAX]
        raise MppParserError(
            'erro_mpxj',
            f'o worker MPXJ terminou sem produzir JSON válido ({exc}); '
            f'stdout={trecho!r}',
        )
