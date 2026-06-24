"""
Seed — Físico-Financeiro (piloto Baias Kabod).

Deixa a obra inteira planejada numa ação: cronograma (tarefas raiz+folhas),
custo por etapa (Veks × Fat Direto), vinculação atividade↔custo, medições de
contrato e o snapshot do fluxo de caixa da Planilha1. Também coloca o tenant
em **v2** (a página do painel é v2-gated; sem isso a rota redireciona).

Idempotente: re-rodar não duplica (upsert por (codigo, admin_id)).

Uso:
    python scripts/seed_fisico_financeiro_baias.py <admin_id|username> [caminho_json]

Se o caminho do JSON for omitido, usa o arquivo canônico do repositório:
    cronograma_fisico_financeiro_baias.json  (raiz)  ou  tests/fixtures/<mesmo nome>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

from main import app
from models import db, Usuario
from services.importacao_fisico_financeiro import importar_fisico_financeiro

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATOS_JSON = [
    os.path.join(_RAIZ, "tests", "fixtures", "cronograma_fisico_financeiro_baias.json"),
    os.path.join(_RAIZ, "cronograma_fisico_financeiro_baias.json"),
]


def _resolver_admin(arg):
    if str(arg).isdigit():
        return int(arg)
    u = Usuario.query.filter_by(username=arg).first()
    return u.id if u else None


def _achar_json(caminho_arg):
    if caminho_arg:
        return caminho_arg if os.path.exists(caminho_arg) else None
    for c in _CANDIDATOS_JSON:
        if os.path.exists(c):
            return c
    return None


def seed(admin_id, caminho_json=None):
    caminho = _achar_json(caminho_json)
    if not caminho:
        raise FileNotFoundError(
            "JSON não encontrado. Passe o caminho ou coloque "
            "'cronograma_fisico_financeiro_baias.json' na raiz do projeto."
        )

    # 1) Tenant em v2 (o painel físico-financeiro é v2-gated)
    admin = Usuario.query.get(admin_id)
    if admin is None:
        raise ValueError(f"admin_id {admin_id} não encontrado")
    if admin.versao_sistema != "v2":
        admin.versao_sistema = "v2"
        db.session.add(admin)
        db.session.commit()

    # 2) Importa tudo (idempotente)
    with open(caminho, encoding="utf-8") as f:
        payload = json.load(f)
    res = importar_fisico_financeiro(payload, admin_id)
    return {"caminho": caminho, "versao": admin.versao_sistema, **res}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python scripts/seed_fisico_financeiro_baias.py <admin_id|username> [caminho_json]")
        sys.exit(1)
    with app.app_context():
        admin_id = _resolver_admin(sys.argv[1])
        if not admin_id:
            print("admin não encontrado:", sys.argv[1])
            sys.exit(1)
        caminho_json = sys.argv[2] if len(sys.argv) > 2 else None
        r = seed(admin_id, caminho_json)
        print(f"[seed_fisico_financeiro_baias] admin_id={admin_id}  versao={r['versao']}")
        print(f"  JSON:   {r['caminho']}")
        print(f"  obra_id={r['obra_id']}")
        if r.get("avisos"):
            print("  avisos:")
            for a in r["avisos"]:
                print(f"    - {a}")
        print(f"  Painel: /cronograma/obra/{r['obra_id']}/fisico-financeiro")
