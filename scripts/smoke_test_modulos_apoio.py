"""Smoke test dos módulos de apoio (Task #18).

Loga como admin@construtoraalfa.com.br, faz GET nas rotas principais dos
módulos de apoio (Dashboard, CRM, Métricas, Catálogo, Estoque, Frota,
Alimentação, Portal Cliente). Não modifica dados.
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
    ids: dict = {}
    # obra id da listagem
    r = s.get(f"{BASE}/obras", timeout=10)
    m = re.search(r"/obras/detalhes/(\d+)|/obras/(\d+)", r.text)
    if m:
        ids["obra"] = int(m.group(1) or m.group(2))
    # token portal cliente da obra
    if "obra" in ids:
        try:
            r = s.get(f"{BASE}/obras/detalhes/{ids['obra']}", timeout=10)
            m = re.search(r"/portal/obra/([A-Za-z0-9_\-]{16,})", r.text)
            if m:
                ids["token"] = m.group(1)
        except Exception:
            pass
    # CRM lead id
    try:
        r = s.get(f"{BASE}/crm/lista", timeout=10)
        m = re.search(r"/crm/(\d+)/editar", r.text)
        if m:
            ids["lead"] = int(m.group(1))
    except Exception:
        pass
    # Catálogo: serviço e insumo
    try:
        r = s.get(f"{BASE}/catalogo/servicos", timeout=10)
        m = re.search(r"/catalogo/servicos/(\d+)/composicao", r.text)
        if m:
            ids["servico"] = int(m.group(1))
    except Exception:
        pass
    try:
        r = s.get(f"{BASE}/catalogo/insumos", timeout=10)
        m = re.search(r"/catalogo/insumos/(\d+)\b", r.text)
        if m:
            ids["insumo"] = int(m.group(1))
    except Exception:
        pass
    # Veículo
    try:
        r = s.get(f"{BASE}/frota/", timeout=10)
        m = re.search(r"/frota/(\d+)\b", r.text)
        if m:
            ids["veiculo"] = int(m.group(1))
    except Exception:
        pass
    # Item de almoxarifado
    try:
        r = s.get(f"{BASE}/almoxarifado/itens", timeout=10)
        m = re.search(r"/almoxarifado/itens/(\d+)\b", r.text)
        if m:
            ids["alm_item"] = int(m.group(1))
    except Exception:
        pass
    # Restaurante
    try:
        r = s.get(f"{BASE}/alimentacao/restaurantes", timeout=10)
        m = re.search(r"/alimentacao/restaurante/(\d+)", r.text)
        if m:
            ids["restaurante"] = int(m.group(1))
    except Exception:
        pass
    # Funcionário (para métricas detalhe)
    try:
        r = s.get(f"{BASE}/funcionarios", timeout=10)
        m = re.search(r"/funcionario_perfil/(\d+)", r.text)
        if m:
            ids["funcionario"] = int(m.group(1))
    except Exception:
        pass
    return ids


ROUTES = {
    "Dashboard": [
        "/dashboard",
    ],
    "CRM": [
        "/crm/",
        "/crm/lista",
        "/crm/novo",
        "/crm/{lead}/editar",
        "/crm/cadastros",
    ],
    "Metricas": [
        "/metricas/servico",
        "/metricas/funcionarios",
        "/metricas/funcionarios/{funcionario}",
        "/metricas/ranking",
    ],
    "Catalogo": [
        "/catalogo/insumos",
        "/catalogo/insumos/novo",
        "/catalogo/insumos/{insumo}",
        "/catalogo/servicos",
        "/catalogo/servicos/novo",
        "/catalogo/servicos/{servico}/composicao",
        "/catalogo/servicos/{servico}/historico-obras",
    ],
    "Estoque": [
        "/almoxarifado/",
        "/almoxarifado/itens",
        "/almoxarifado/itens/criar",
        "/almoxarifado/itens/{alm_item}",
        "/almoxarifado/itens/{alm_item}/movimentacoes",
        "/almoxarifado/categorias",
        "/almoxarifado/entrada",
        "/almoxarifado/saida",
        "/almoxarifado/devolucao",
        "/almoxarifado/movimentacoes",
        "/almoxarifado/relatorios",
        "/almoxarifado/fornecedores",
    ],
    "Frota": [
        "/frota/",
        "/frota/novo",
        "/frota/{veiculo}",
        "/frota/{veiculo}/editar",
        "/frota/dashboard",
    ],
    "Alimentacao": [
        "/alimentacao/",
        "/alimentacao/dashboard",
        "/alimentacao/lancamentos",
        "/alimentacao/lancamentos/novo",
        "/alimentacao/lancamentos/novo-v2",
        "/alimentacao/restaurantes",
        "/alimentacao/restaurantes/novo",
        "/alimentacao/restaurante/{restaurante}",
        "/alimentacao/itens",
    ],
    "PortalCliente": [
        "/portal/obra/{token}",
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


def main() -> int:
    s = requests.Session()
    if not login(s):
        print("FALHA no login", file=sys.stderr)
        return 1
    ids = discover_ids(s)
    print(f"# IDs descobertos: {ids}\n")
    print(f"{'Modulo':<14} {'Rota':<60} {'Status':<8} {'Tempo':<7} Resultado")
    print("-" * 115)
    erros = 0
    for mod, paths in ROUTES.items():
        for p in paths:
            try:
                full = p.format(**ids)
            except KeyError as e:
                print(f"{mod:<14} {p:<60} SKIP    -       sem id ({e})")
                continue
            t0 = time.perf_counter()
            try:
                # Portal do cliente: usar sessão NOVA (sem login)
                if mod == "PortalCliente":
                    s2 = requests.Session()
                    r = s2.get(BASE + full, timeout=20, allow_redirects=False)
                else:
                    r = s.get(BASE + full, timeout=20, allow_redirects=False)
                dt = (time.perf_counter() - t0) * 1000
                tag = classify(r.status_code, r.text or "")
                if tag.startswith("ERRO") or tag == "EXCEÇÃO no HTML":
                    erros += 1
                print(f"{mod:<14} {full:<60} {r.status_code:<8} {dt:>5.0f}ms {tag}")
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                erros += 1
                print(f"{mod:<14} {full:<60} ERR      {dt:>5.0f}ms {e!r}")
    print(f"\n# Erros 5xx/exception: {erros}")
    return 0 if erros == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
