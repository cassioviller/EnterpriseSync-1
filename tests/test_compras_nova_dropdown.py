"""
Task #202 — Teste E2E HTTP do dropdown de fornecedores em /compras/nova.

Cobre, na rota real `compras_views.nova` / `nova_post`:

  1. GET /compras/nova com tenant SEM fornecedores
     → renderiza alerta de empty-state com link para
       /almoxarifado/fornecedores/criar (não exibe `<select>`).

  2. GET /compras/nova com tenant COM fornecedores ativos
     → renderiza `<select name="fornecedor_id" class="... select2-ajax">`
       com options de TODOS os fornecedores ativos do tenant
       (e nenhum fornecedor de outro tenant).

  3. GET /compras/nova
     → expõe assets do Select2 (CSS/JS via CDN) + script init para
       a classe `.select2-ajax`. Garante que o dropdown é
       pesquisável (mesma UX dos demais formulários).

  4. POST /compras/nova com fornecedor/obra do próprio tenant
     → cria PedidoCompra (302 → /compras/<id>) e persiste itens.

  5. POST /compras/nova SEM fornecedor_id (ou vazio)
     → redireciona com flash `danger` e NÃO cria PedidoCompra.

  6. POST /compras/nova com fornecedor_id de OUTRO tenant
     → defesa multi-tenant: redireciona com flash, NÃO cria
       PedidoCompra.

  7. POST /compras/nova com obra_id de OUTRO tenant
     → defesa multi-tenant: redireciona com flash, NÃO cria
       PedidoCompra.

Executa com:  python tests/test_compras_nova_dropdown.py
Workflow Replit: `test-compras-nova-dropdown`.

Exit code 0 → todos os asserts passaram.
"""
import os
import re
import sys
import secrets
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario,
    Fornecedor, Cliente, Obra, PedidoCompra, PedidoCompraItem,
    AlmoxarifadoMovimento, AlmoxarifadoEstoque,
    GestaoCustoPai, GestaoCustoFilho,
    LancamentoContabil, PartidaContabil, PlanoContas,
)

RUN_TAG = f"COMPRAS202-{secrets.token_hex(3).upper()}"
PASS = 0
FAIL = 0
ERRORS = []


def check(name, ok, evidence=""):
    global PASS, FAIL
    status = "[OK]  " if ok else "[FAIL]"
    extra = f"  — {evidence}" if evidence else ""
    print(f"  {status} {name}{extra}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(name)


# ────────────────────────────────────────────────────────────────
# Setup helpers
# ────────────────────────────────────────────────────────────────

def _make_admin(suffix):
    email = f"compras202_{suffix}_{RUN_TAG.lower()}@test.local"
    u = Usuario(
        username=f"compras202_{suffix}_{RUN_TAG.lower()}",
        nome=f"Compras 202 {suffix}",
        email=email,
        password_hash=generate_password_hash("Senha@2026"),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _make_fornecedor(admin_id, nome, ativo=True):
    # CNPJ válido em comprimento: XX.XXX.XXX/XXXX-XX = 18 chars exatos.
    n = secrets.randbelow(10**8)
    cnpj = f"{n // 10**6 % 100:02d}.{n // 10**3 % 1000:03d}.{n % 1000:03d}/0001-{secrets.randbelow(100):02d}"
    f = Fornecedor(
        nome=nome,
        cnpj=cnpj,
        ativo=ativo,
        admin_id=admin_id,
    )
    db.session.add(f)
    db.session.commit()
    return f


def _make_cliente(admin_id, nome):
    c = Cliente(nome=nome, email=f"cli_{secrets.token_hex(3)}@test.local", admin_id=admin_id)
    db.session.add(c)
    db.session.commit()
    return c


def _make_obra(admin_id, cliente_id, nome):
    o = Obra(
        nome=nome,
        codigo=f"OBR-{secrets.token_hex(3).upper()}",
        data_inicio=date.today(),
        cliente_id=cliente_id,
        admin_id=admin_id,
        ativo=True,
        cronograma_revisado_em=None,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _login(client, email):
    r = client.post(
        "/login",
        data={"email": email, "password": "Senha@2026"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), f"Login falhou: {r.status_code}"


def _logout(client):
    client.get("/logout", follow_redirects=False)


# ────────────────────────────────────────────────────────────────
# Cleanup
# ────────────────────────────────────────────────────────────────

def cleanup(admin_ids):
    """Remove tudo o que o teste criou (idempotente).

    Ordem importa por causa de FKs: derivados (custos, almoxarifado,
    pedidos) antes de obra/cliente/fornecedor/usuário.
    """
    if not admin_ids:
        return
    try:
        # 1) Custos derivados do pedido (filhos antes do pai;
        # FK em GestaoCustoFilho é `pai_id`, não `gestao_custo_pai_id`)
        gcps = GestaoCustoPai.query.filter(
            GestaoCustoPai.admin_id.in_(admin_ids)
        ).all()
        gcp_ids = [g.id for g in gcps]
        if gcp_ids:
            GestaoCustoFilho.query.filter(
                GestaoCustoFilho.pai_id.in_(gcp_ids)
            ).delete(synchronize_session=False)
            db.session.commit()
        GestaoCustoFilho.query.filter(
            GestaoCustoFilho.admin_id.in_(admin_ids)
        ).delete(synchronize_session=False)
        GestaoCustoPai.query.filter(
            GestaoCustoPai.admin_id.in_(admin_ids)
        ).delete(synchronize_session=False)
        db.session.commit()

        # 1b) Lançamentos contábeis (compra de material gera partida dobrada).
        # PartidaContabil tem FK para LancamentoContabil → apaga partidas
        # primeiro via subquery por admin.
        lc_ids = [r[0] for r in db.session.query(LancamentoContabil.id).filter(
            LancamentoContabil.admin_id.in_(admin_ids)
        ).all()]
        if lc_ids:
            PartidaContabil.query.filter(
                PartidaContabil.lancamento_id.in_(lc_ids)
            ).delete(synchronize_session=False)
            db.session.commit()
        LancamentoContabil.query.filter(
            LancamentoContabil.admin_id.in_(admin_ids)
        ).delete(synchronize_session=False)
        db.session.commit()

        # 2) Almoxarifado (estoque antes de movimento — FKs apontam para movimento)
        AlmoxarifadoEstoque.query.filter(
            AlmoxarifadoEstoque.admin_id.in_(admin_ids)
        ).delete(synchronize_session=False)
        AlmoxarifadoMovimento.query.filter(
            AlmoxarifadoMovimento.admin_id.in_(admin_ids)
        ).delete(synchronize_session=False)
        db.session.commit()

        # 3) Pedidos de compra (cascade dos itens via relationship)
        pedidos = PedidoCompra.query.filter(
            PedidoCompra.admin_id.in_(admin_ids)
        ).all()
        for p in pedidos:
            db.session.delete(p)
        db.session.commit()

        # 4) Obra → Cliente → Fornecedor
        Obra.query.filter(Obra.admin_id.in_(admin_ids)).delete(synchronize_session=False)
        Cliente.query.filter(Cliente.admin_id.in_(admin_ids)).delete(synchronize_session=False)
        Fornecedor.query.filter(Fornecedor.admin_id.in_(admin_ids)).delete(synchronize_session=False)
        db.session.commit()

        # 5) PlanoContas (auto-seedado pelo primeiro lançamento contábil
        # via contabilidade_utils.seed_plano_contas_v2). Tabela tem self-FK
        # via conta_pai_codigo, mas DELETE em massa pelo admin_id resolve
        # tudo em uma transação. Nenhuma outra tabela referencia esses
        # códigos depois que LancamentoContabil/Partidas foram apagados.
        PlanoContas.query.filter(
            PlanoContas.admin_id.in_(admin_ids)
        ).delete(synchronize_session=False)
        db.session.commit()

        # 6) Usuario (admin) — agora sem dependências pendentes
        Usuario.query.filter(Usuario.id.in_(admin_ids)).delete(synchronize_session=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"  [WARN] cleanup falhou: {e}")


# ────────────────────────────────────────────────────────────────
# Test runner
# ────────────────────────────────────────────────────────────────

def run():
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    admin_ids = []
    try:
        with app.app_context():
            print(f"\n=== Task #202 — /compras/nova dropdown ({RUN_TAG}) ===\n")

            admin_a = _make_admin("A")
            admin_b = _make_admin("B")
            admin_ids = [admin_a.id, admin_b.id]
            admin_a_id = admin_a.id
            admin_a_email = admin_a.email
            admin_b_id = admin_b.id

            # ── Cenário A: tenant SEM fornecedores ──────────────
            print("\n[1] GET /compras/nova com tenant SEM fornecedores")
            client = app.test_client()
            _login(client, admin_a_email)

            r = client.get("/compras/nova", follow_redirects=False)
            html_empty = r.data.decode("utf-8", errors="replace") if r.status_code == 200 else ""
            check("GET /compras/nova retorna 200",
                  r.status_code == 200, f"status={r.status_code}")

            check("Empty-state alerta presente",
                  "Nenhum fornecedor cadastrado" in html_empty,
                  "alert-warning visível")
            check("Link para cadastrar fornecedor presente",
                  "/almoxarifado/fornecedores/criar" in html_empty,
                  "url_for(almoxarifado.fornecedores_criar)")
            # No empty state, NÃO renderiza o select
            check("Select de fornecedor ausente quando lista vazia",
                  '<select name="fornecedor_id"' not in html_empty
                  and '<select name=fornecedor_id' not in html_empty,
                  "select substituído por alerta")

            # ── Seed fornecedores no admin A (e ruído no admin B) ─
            print("\n[2] Seed: 2 ativos + 1 inativo no admin A; 1 fornecedor no admin B (ruído)")
            forn_ativo_1 = _make_fornecedor(admin_a_id, f"Fornec Alfa {RUN_TAG}")
            forn_ativo_2 = _make_fornecedor(admin_a_id, f"Fornec Beta {RUN_TAG}")
            forn_inativo = _make_fornecedor(admin_a_id, f"Fornec Inativo {RUN_TAG}", ativo=False)
            forn_outro_tenant = _make_fornecedor(admin_b_id, f"Fornec Outro {RUN_TAG}")
            cliente_a = _make_cliente(admin_a_id, f"Cliente {RUN_TAG}")
            obra_a = _make_obra(admin_a_id, cliente_a.id, f"Obra A {RUN_TAG}")
            cliente_b = _make_cliente(admin_b_id, f"Cliente B {RUN_TAG}")
            obra_b_outro_tenant = _make_obra(admin_b_id, cliente_b.id, f"Obra B {RUN_TAG}")

            check("Fornecedores ativos seeded",
                  forn_ativo_1.ativo and forn_ativo_2.ativo,
                  f"ids={forn_ativo_1.id},{forn_ativo_2.id}")

            # ── Cenário B: tenant COM fornecedores ──────────────
            print("\n[3] GET /compras/nova com tenant COM fornecedores")
            r = client.get("/compras/nova", follow_redirects=False)
            html = r.data.decode("utf-8", errors="replace")
            check("GET /compras/nova retorna 200", r.status_code == 200, f"status={r.status_code}")

            # Select de fornecedor presente com classe select2-ajax (typeahead)
            select_match = re.search(
                r'<select[^>]*name="fornecedor_id"[^>]*>(.*?)</select>',
                html, re.DOTALL,
            )
            check("Select de fornecedor renderizado", select_match is not None)

            select_html = select_match.group(0) if select_match else ""
            inner = select_match.group(1) if select_match else ""

            check("Select tem classe select2-ajax (pesquisável)",
                  "select2-ajax" in select_html,
                  "class contém select2-ajax")
            check("Select tem placeholder de busca",
                  "data-placeholder" in select_html,
                  "atributo data-placeholder")
            check("Select é required",
                  " required" in select_html,
                  "atributo required")

            options = re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]*)</option>', inner)
            ids = {int(v) for v, _ in options}
            check("Fornecedor ativo 1 está no dropdown",
                  forn_ativo_1.id in ids,
                  f"option value={forn_ativo_1.id}")
            check("Fornecedor ativo 2 está no dropdown",
                  forn_ativo_2.id in ids,
                  f"option value={forn_ativo_2.id}")
            check("Fornecedor INATIVO NÃO está no dropdown",
                  forn_inativo.id not in ids,
                  f"option value={forn_inativo.id} ausente")
            check("Fornecedor de OUTRO tenant NÃO está no dropdown",
                  forn_outro_tenant.id not in ids,
                  "isolamento multi-tenant na UI")

            # Empty-state escondido quando há fornecedores
            check("Empty-state escondido quando há fornecedores",
                  "Nenhum fornecedor cadastrado" not in html,
                  "alert-warning ausente")

            # ── Cenário C: assets do Select2 carregados ─────────
            print("\n[4] Assets Select2 carregados (CSS + JS + init)")
            check("CSS Select2 incluído",
                  "select2.min.css" in html,
                  "CDN select2@4.1")
            check("Theme bootstrap-5 incluído",
                  "select2-bootstrap-5-theme" in html,
                  "tema visual consistente")
            check("JS Select2 incluído",
                  "select2.min.js" in html,
                  "CDN script tag")
            check("Init do Select2 chamado",
                  ".select2-ajax" in html and "select2(" in html,
                  "jQuery(function($){$('.select2-ajax').select2(...)})")

            # ── Cenário D: POST válido cria a compra ─────────────
            print("\n[5] POST /compras/nova com dados válidos")
            r = client.post("/compras/nova", data={
                "fornecedor_id": str(forn_ativo_1.id),
                "obra_id": str(obra_a.id),
                "data_compra": date.today().isoformat(),
                "condicao_pagamento": "a_vista",
                "parcelas": "1",
                "tipo_compra": "normal",
                "numero": f"NF-{RUN_TAG}",
                "observacoes": "criado via teste E2E #202",
                "item_descricao[]": ["Cimento CPII saco 50kg"],
                "item_quantidade[]": ["10"],
                "item_preco[]": ["35,90"],
                "item_almoxarifado_id[]": [""],
            }, follow_redirects=False)

            check("POST válido retorna redirect",
                  r.status_code in (302, 303),
                  f"status={r.status_code} Location={r.headers.get('Location')}")

            pedido = (PedidoCompra.query
                      .filter_by(admin_id=admin_a_id, fornecedor_id=forn_ativo_1.id)
                      .order_by(PedidoCompra.id.desc())
                      .first())
            check("PedidoCompra persistido no DB",
                  pedido is not None,
                  f"pedido.id={getattr(pedido, 'id', None)}")
            if pedido:
                location = r.headers.get("Location") or ""
                check("Redirect aponta para área de compras (sucesso)",
                      "/compras" in location,
                      location)
                check("Pedido vinculado à obra correta",
                      pedido.obra_id == obra_a.id,
                      f"obra_id={pedido.obra_id}")
                check("valor_total = 10 * 35.90 = 359.00",
                      float(pedido.valor_total) == 359.00,
                      f"valor_total={pedido.valor_total}")

            # ── Cenário E: POST sem fornecedor_id ───────────────
            print("\n[6] POST /compras/nova SEM fornecedor_id")
            n_antes = PedidoCompra.query.filter_by(admin_id=admin_a_id).count()
            r = client.post("/compras/nova", data={
                "fornecedor_id": "",
                "data_compra": date.today().isoformat(),
                "condicao_pagamento": "a_vista",
                "tipo_compra": "normal",
                "item_descricao[]": ["Item teste"],
                "item_quantidade[]": ["1"],
                "item_preco[]": ["10,00"],
            }, follow_redirects=False)
            n_depois = PedidoCompra.query.filter_by(admin_id=admin_a_id).count()
            check("POST sem fornecedor redireciona (não 500)",
                  r.status_code in (302, 303, 200),
                  f"status={r.status_code}")
            check("POST sem fornecedor NÃO cria PedidoCompra",
                  n_depois == n_antes,
                  f"count {n_antes} → {n_depois}")

            # ── Cenário F: POST com fornecedor de outro tenant ──
            print("\n[7] POST /compras/nova com fornecedor_id de OUTRO tenant")
            n_antes = PedidoCompra.query.filter_by(admin_id=admin_a_id).count()
            r = client.post("/compras/nova", data={
                "fornecedor_id": str(forn_outro_tenant.id),
                "data_compra": date.today().isoformat(),
                "condicao_pagamento": "a_vista",
                "tipo_compra": "normal",
                "item_descricao[]": ["Item invasor"],
                "item_quantidade[]": ["1"],
                "item_preco[]": ["1,00"],
            }, follow_redirects=False)
            n_depois = PedidoCompra.query.filter_by(admin_id=admin_a_id).count()
            check("POST cross-tenant retorna redirect",
                  r.status_code in (302, 303),
                  f"status={r.status_code}")
            check("POST cross-tenant NÃO cria PedidoCompra para admin A",
                  n_depois == n_antes,
                  f"count {n_antes} → {n_depois}")
            # E não cria para o admin B também
            cross_b = (PedidoCompra.query
                       .filter_by(admin_id=admin_b_id,
                                  fornecedor_id=forn_outro_tenant.id)
                       .count())
            check("POST cross-tenant NÃO cria PedidoCompra para admin B",
                  cross_b == 0,
                  f"count admin_b={cross_b}")

            # ── Cenário G: POST com obra de outro tenant ────────
            print("\n[8] POST /compras/nova com obra_id de OUTRO tenant")
            n_antes = PedidoCompra.query.filter_by(admin_id=admin_a_id).count()
            r = client.post("/compras/nova", data={
                "fornecedor_id": str(forn_ativo_2.id),
                "obra_id": str(obra_b_outro_tenant.id),
                "data_compra": date.today().isoformat(),
                "condicao_pagamento": "a_vista",
                "tipo_compra": "normal",
                "item_descricao[]": ["Item obra invasora"],
                "item_quantidade[]": ["1"],
                "item_preco[]": ["1,00"],
            }, follow_redirects=False)
            n_depois = PedidoCompra.query.filter_by(admin_id=admin_a_id).count()
            check("POST obra cross-tenant retorna redirect",
                  r.status_code in (302, 303),
                  f"status={r.status_code}")
            check("POST obra cross-tenant NÃO cria PedidoCompra",
                  n_depois == n_antes,
                  f"count {n_antes} → {n_depois}")

            _logout(client)

            print(f"\n=== RESULTADO: {PASS} PASS / {FAIL} FAIL ===")
            if ERRORS:
                print("Falhas:")
                for e in ERRORS:
                    print(f"  - {e}")
    finally:
        with app.app_context():
            cleanup(admin_ids)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
