"""Smoke test dos módulos críticos (Task #17).

Loga como admin@construtoraalfa.com.br, faz GET nas rotas principais e
classifica cada uma. Não modifica dados.
"""
from __future__ import annotations

import os
import re
import sys
import time

import requests

BASE = "http://localhost:5000"
EMAIL = "admin@construtoraalfa.com.br"
PASSWORD = "Alfa@2026"


def login(s: requests.Session) -> bool:
    r = s.get(f"{BASE}/login", timeout=10)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
    token = m.group(1) if m else ""
    r = s.post(
        f"{BASE}/login",
        data={"email": EMAIL, "password": PASSWORD, "csrf_token": token},
        allow_redirects=False,
        timeout=10,
    )
    return r.status_code in (302, 303)


def discover_ids(s: requests.Session) -> dict:
    """Pega 1 obra/rdo/funcionario/proposta/conta de demo p/ exercitar rotas com <int:id>."""
    ids = {}
    # obra id da listagem
    r = s.get(f"{BASE}/obras", timeout=10)
    m = re.search(r"/obras/detalhes/(\d+)|/obras/(\d+)", r.text)
    if m:
        ids["obra"] = int(m.group(1) or m.group(2))
    # funcionario id
    r = s.get(f"{BASE}/funcionarios", timeout=10)
    m = re.search(r"/funcionario_perfil/(\d+)", r.text)
    if m:
        ids["funcionario"] = int(m.group(1))
    # rdo id
    r = s.get(f"{BASE}/rdos", timeout=10)
    m = re.search(r"/rdo/(\d+)\b|/funcionario/rdo/(\d+)", r.text)
    if m:
        ids["rdo"] = int(m.group(1) or m.group(2))
    # proposta id
    r = s.get(f"{BASE}/propostas/", timeout=10)
    m = re.search(r"/propostas/(\d+)\b", r.text)
    if m:
        ids["proposta"] = int(m.group(1))
    return ids


ROUTES = {
    "Obras": [
        "/obras",
        "/obras/nova",
        "/obras/detalhes/{obra}",
        "/obras/editar/{obra}",
        "/obras/{obra}/curva-avanco",
    ],
    "RDO": [
        "/rdos",
        "/rdo",
        "/rdo/lista",
        "/rdo/novo",
        "/funcionario/rdo/consolidado",
        "/rdo/{rdo}",
    ],
    "Cronograma": [
        "/cronograma/",
        "/cronograma/obra/{obra}",
        "/cronograma/calendario",
        "/cronograma/catalogo",
        "/cronograma/templates",
        "/cronograma/produtividade",
    ],
    "Financeiro": [
        "/financeiro/",
        "/financeiro/contas-pagar",
        "/financeiro/contas-pagar/nova",
        "/financeiro/contas-receber",
        "/financeiro/contas-receber/nova",
        "/financeiro/fluxo-caixa",
        "/financeiro/bancos",
        "/contabilidade/dashboard",
    ],
    "Propostas": [
        "/propostas/",
        "/propostas/dashboard",
        "/propostas/listar",
        "/propostas/nova",
        "/propostas/templates",
        "/propostas/{proposta}",
        "/propostas/editar/{proposta}",
    ],
    "Folha": [
        "/folha/dashboard",
        "/folha/parametros-legais",
        "/folha/beneficios",
        "/folha/adiantamentos",
        "/folha/relatorios",
    ],
    "Funcionarios": [
        "/funcionarios",
        "/funcionario_perfil/{funcionario}",
        "/funcionario_perfil/{funcionario}/pdf",
        "/equipe",
        "/ponto/",
        "/ponto/lista-obras",
        "/ponto/configuracao/obras-funcionarios",
        "/ponto/importar",
        "/configuracoes/horarios",
    ],
}


def classify(status: int, body: str) -> str:
    if status >= 500:
        return "ERRO 5xx"
    if status == 404:
        return "404"
    if status == 403:
        return "403"
    if status in (302, 303):
        return f"redirect ({status})"
    if status != 200:
        return f"status {status}"
    if "Internal Server Error" in body or "Traceback (most recent call" in body:
        return "EXCEÇÃO no HTML"
    if len(body) < 500:
        return "página quase vazia"
    return "ok"


def _snapshot_log_position(log_path: str) -> int:
    try:
        return os.path.getsize(log_path)
    except OSError:
        return 0


def _scan_log_for_tracebacks(log_path: str, start_pos: int) -> list[str]:
    """Lê o log da aplicação a partir de start_pos e retorna linhas suspeitas
    (Traceback, ERROR/CRITICAL, Internal Server Error)."""
    findings: list[str] = []
    try:
        with open(log_path, "rb") as fh:
            fh.seek(start_pos)
            data = fh.read().decode("utf-8", errors="replace")
        for ln in data.splitlines():
            if (
                "Traceback (most recent call" in ln
                or "Internal Server Error" in ln
                or " ERROR " in ln
                or " CRITICAL " in ln
            ):
                findings.append(ln.strip())
    except OSError:
        pass
    return findings


def _find_app_log() -> str | None:
    """Tenta localizar o log do workflow Start application."""
    candidates = [
        "/tmp/logs",
        os.path.expanduser("~/.local/state/workflow-logs"),
        ".local/state/workflow-logs",
    ]
    newest: tuple[float, str] | None = None
    for root in candidates:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for f in files:
                if not f.endswith(".log") and "log" not in f.lower():
                    continue
                full = os.path.join(dirpath, f)
                try:
                    mt = os.path.getmtime(full)
                except OSError:
                    continue
                if newest is None or mt > newest[0]:
                    newest = (mt, full)
    return newest[1] if newest else None


def main() -> int:
    s = requests.Session()
    if not login(s):
        print("FALHA no login", file=sys.stderr)
        return 1
    ids = discover_ids(s)
    print(f"# IDs descobertos: {ids}\n")
    log_path = _find_app_log()
    log_start = _snapshot_log_position(log_path) if log_path else 0
    if log_path:
        print(f"# Monitorando log: {log_path} (offset inicial={log_start})\n")
    else:
        print("# Nenhum arquivo de log de workflow localizado para inspeção.\n")
    print(f"{'Modulo':<14} {'Rota':<55} {'Status':<8} {'Tempo':<7} Resultado")
    print("-" * 110)
    for mod, paths in ROUTES.items():
        for p in paths:
            try:
                full = p.format(**ids)
            except KeyError as e:
                print(f"{mod:<14} {p:<55} SKIP    -       sem id ({e})")
                continue
            t0 = time.perf_counter()
            try:
                r = s.get(BASE + full, timeout=20, allow_redirects=False)
                dt = (time.perf_counter() - t0) * 1000
                tag = classify(r.status_code, r.text or "")
                print(f"{mod:<14} {full:<55} {r.status_code:<8} {dt:>5.0f}ms {tag}")
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                print(f"{mod:<14} {full:<55} ERR      {dt:>5.0f}ms {e!r}")
    if log_path:
        log_findings = _scan_log_for_tracebacks(log_path, log_start)
        print()
        if log_findings:
            print(f"# {len(log_findings)} linha(s) suspeita(s) no log durante o smoke test:")
            for ln in log_findings[:50]:
                print(f"  ! {ln[:240]}")
            return 2
        print("# Nenhuma traceback/ERROR/CRITICAL encontrada no log durante o smoke test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
