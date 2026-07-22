"""E2E (browser real) — marcar um item SEM template na tela de revisão.

Complementa tests/test_cronograma_proposta_tolerante.py, que cobre o mesmo
fluxo server-side. Aqui o que se prova é o pedaço que só o browser executa:

  1. o checkbox do card sem template é clicável (era `disabled` —
     templates/propostas/cronograma_revisar.html:266);
  2. `_recalcular()` conta o card no resumo (havia um `return` que pulava
     cards `.no-template`, então o total exibido não batia com o que a obra
     receberia);
  3. `_construirArvoreFinal()` envia o quantitativo. Ele serializava só
     9 campos e descartava duracao_dias/quantidade_prevista/unidade_medida/
     responsavel; como a aprovação passa `cronograma_default_json` DIRETO
     para `materializar_cronograma` (handlers/propostas_handlers.py:243),
     sem reconstruir a árvore, a tarefa nascia sem quantidade e caía no
     fallback percentual.

Pré-requisito (igual aos demais _playwright.py): servidor em localhost:5000
compartilhando o MESMO Postgres deste processo.

    pytest tests/test_cronograma_sem_template_playwright.py -v

Se o Chromium do Playwright não estiver instalado::

    python -m playwright install chromium

Neste ambiente Nix o binário baixado ainda não acha as libs de sistema
(libnspr4/libnss3/libgbm/libasound/libxkbcommon) e morre com TargetClosedError.
`playwright install-deps` não resolve (precisa de apt/root); aponte o loader
para o nix store antes de rodar::

    export LD_LIBRARY_PATH=$(ls -d /nix/store/*-{alsa-lib,mesa-libgbm,nspr,nss,libxkbcommon}-*/lib | paste -sd:)
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, Obra, Proposta, PropostaItem, Servico,
                    TarefaCronograma, TipoUsuario, Usuario)

BASE_URL = os.environ.get("PW_BASE_URL", "http://localhost:5000")
TIMEOUT_MS = int(os.environ.get("SIGE_TIMEOUT_MS", "30000"))
SENHA = "Senha@2026"

pytestmark = [pytest.mark.browser, pytest.mark.integration]


@pytest.fixture(scope="module")
def cenario():
    """admin + cliente + servico SEM template + obra + proposta com 1 item."""
    suf = uuid.uuid4().hex[:10]
    with app.app_context():
        admin = Usuario(
            username=f"pw_{suf}", email=f"pw_{suf}@test.local",
            nome=f"PW {suf}", password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema="v2",
        )
        db.session.add(admin)
        db.session.commit()

        cliente = Cliente(nome=f"Cliente PW {suf}", admin_id=admin.id)
        db.session.add(cliente)
        db.session.flush()

        servico = Servico(nome=f"Servico PW Sem Template {suf}",
                          categoria="Estrutural", unidade_medida="m2",
                          admin_id=admin.id, ativo=True)
        db.session.add(servico)
        db.session.flush()

        obra = Obra(nome=f"Obra PW {suf}", codigo=f"PW-{suf[:8].upper()}",
                    admin_id=admin.id, cliente_id=cliente.id,
                    data_inicio=date(2026, 1, 1))
        db.session.add(obra)
        db.session.flush()

        proposta = Proposta(numero=f"PW-{suf[:10]}", admin_id=admin.id,
                            cliente_id=cliente.id, obra_id=obra.id,
                            cliente_nome=cliente.nome, criado_por=admin.id,
                            status="enviada", valor_total=Decimal("40000.00"))
        db.session.add(proposta)
        db.session.flush()

        item = PropostaItem(admin_id=admin.id, proposta_id=proposta.id,
                            servico_id=servico.id, item_numero=1,
                            descricao="Estrutura em Light Steel Frame",
                            quantidade=Decimal("40"), unidade="m2",
                            preco_unitario=Decimal("1000.00"), ordem=1)
        db.session.add(item)
        db.session.commit()

        return {"username": admin.username, "admin_id": admin.id,
                "proposta_id": proposta.id, "obra_id": obra.id,
                "item_id": item.id, "servico_id": servico.id}


@pytest.fixture(scope="module")
def page(cenario):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        pg = browser.new_context().new_page()
        pg.set_default_timeout(TIMEOUT_MS)
        pg.goto(f"{BASE_URL}/login")
        pg.fill("input[name=username]", cenario["username"])
        pg.fill("input[name=password]", SENHA)
        pg.click("button[type=submit]")
        pg.wait_for_load_state("networkidle")
        assert "/login" not in pg.url, f"login falhou, url atual: {pg.url}"
        yield pg
        browser.close()


def test_marcar_item_sem_template_gera_tarefa_com_quantitativo(page, cenario):
    page.goto(f"{BASE_URL}/propostas/{cenario['proposta_id']}/cronograma-revisar")
    page.wait_for_load_state("networkidle")

    card = page.locator(".tree-card.no-template")
    assert card.count() == 1, "card sem template não foi renderizado"
    chk = card.locator("input.chk-raiz")

    # (1) clicável — era `disabled`
    assert chk.count() == 1, "card sem template não tem checkbox .chk-raiz"
    assert chk.is_enabled(), "checkbox do nó sem template está disabled"
    assert not chk.is_checked(), "nó sem template deve nascer desmarcado"
    assert page.locator("#totMarcados").inner_text().strip() == "0"

    chk.check()

    # (2) entra no resumo — `_recalcular()` pulava cards .no-template
    assert page.locator("#totMarcados").inner_text().strip() == "1", (
        "card sem template marcado não entrou no resumo de tarefas selecionadas")

    # (3) o payload leva o quantitativo
    page.click("#btnSalvarPreconfig")
    page.wait_for_load_state("networkidle")

    with app.app_context():
        snap = Proposta.query.get(cenario["proposta_id"]).cronograma_default_json
        assert snap, "pré-configuração não foi salva"
        no = snap[0]
        assert no["marcado"] is True, "marcação do card não chegou ao servidor"
        assert no["sem_template"] is True
        assert float(no["quantidade_prevista"]) == 40.0, (
            "quantitativo podado por _construirArvoreFinal() — a tarefa cairia "
            "no fallback percentual")
        assert no["unidade_medida"] == "m2"
        assert no["responsavel"] == "empresa"
        assert int(no["duracao_dias"]) >= 1

        # E o snapshot que a tela produziu de fato materializa a tarefa.
        from services.cronograma_proposta import materializar_cronograma
        proposta = Proposta.query.get(cenario["proposta_id"])
        criadas = materializar_cronograma(
            proposta, cenario["admin_id"], cenario["obra_id"],
            arvore_marcada=proposta.cronograma_default_json)
        db.session.commit()

        assert criadas == 1
        t = TarefaCronograma.query.filter_by(
            obra_id=cenario["obra_id"], admin_id=cenario["admin_id"],
            gerada_por_proposta_item_id=cenario["item_id"]).one()
        assert t.tarefa_pai_id is None, "esqueleto é nó de nível 0"
        assert float(t.quantidade_total) == 40.0
        assert t.unidade_medida == "m2"
        assert t.servico_id == cenario["servico_id"]
