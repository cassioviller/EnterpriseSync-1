"""
Task #132 — Teste E2E HTTP do ciclo completo SIGE EnterpriseSync.

Cobre o fluxo INTEIRO via Flask test client (HTTP real, não service
layer):

  admin login → POST /catalogo/insumos/novo → POST /catalogo/servicos/novo
  → POST /catalogo/servicos/<id>/composicao/add → POST /propostas/criar
  → GET /propostas/<id>/cronograma-revisar
  → POST /propostas/<id>/cronograma-default (admin valida pré-aprovação)
  → POST /propostas/<id>/status (ENVIADA)
  → GET /propostas/cliente/<token> (anônimo, read-only)
  → POST /propostas/cliente/<token>/aprovar (cliente aprova)
  → GET /cronograma/obra/<obra_id> (admin valida cronograma da obra)

Pré-requisitos seedados via banco (e DOCUMENTADOS — são as lacunas
de UI reportadas em `docs/manual-ciclo-completo.md` § Apêndice B.4):
  S1. Usuário admin V2 (não há rota pública de cadastro de admin no
      sistema — sempre via DB/seed).
  S2. Cliente (sem rota /clientes/novo usada neste fluxo enxuto).
  S3. CronogramaTemplate + itens (UI inexistente para template — gap).
  S4. Patch pós-/catalogo/servicos/novo: `Servico.template_padrao_id`
      (UI inexistente — gap #134).
  S5. Patch pós-/propostas/criar: `PropostaItem.servico_id` (a tela
      /propostas/nova não envia esse campo no POST — gap #135).

Cada passo registra um item no relatório estruturado em
`.local/e2e_step_report.json` com:
  step, method, url, status_http, ok (bool), evidence, error.

Critério de aceite (assert pass/fail por passo):
  1. Login admin retorna 302.
  2. Insumo criado via /catalogo/insumos/novo (302 + DB row).
  3. Serviço criado via /catalogo/servicos/novo (302 + DB row).
  4. Composição adicionada via /catalogo/servicos/<id>/composicao/add
     (302 + DB row).
  5. Proposta criada via /propostas/criar (302 + DB row).
  6. cronograma-revisar retorna 200 e contém o serviço.
  7. cronograma-preview JSON retorna árvore não-vazia.
  8. cronograma-default grava `cronograma_default_json`.
  9. Status RASCUNHO→ENVIADA via API JSON.
  10. Portal cliente (anônimo) abre 200 e NÃO expõe widget de
      validação de cronograma.
  11. POST cliente/aprovar cria obra (proposta.obra_id != NULL).
  12. TarefaCronograma materializadas com gerada_por_proposta_item_id
      != NULL.
  13. GET /cronograma/obra/<id> retorna 200 e renderiza badge
      '📋 do contrato'.

Executa com:  python tests/test_e2e_proposta_aprovacao_cliente.py
Workflow Replit: `test-e2e-proposta-aprovacao-cliente`.

Exit code 0 → todos os asserts passaram. Exit 1 → falha (com
relatório estruturado em .local/e2e_step_report.json e screenshots
de referência em docs/img/manual 2/).
"""
import os
import sys
import json
import secrets
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario,
    Cliente,
    Insumo, ComposicaoServico,
    Servico,
    CronogramaTemplate, CronogramaTemplateItem,
    SubatividadeMestre,
    Proposta, PropostaItem,
    TarefaCronograma,
)

RUN_TAG = f"E2E132-{secrets.token_hex(3).upper()}"
REPORT = []
PASS, FAIL = [], []

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".local", "e2e_step_report.json",
)
SCREENSHOTS_DIR = "docs/img/manual 2"
SCREENSHOT_REFS = {
    "login": "m2-01-login.jpg",
    "insumo_form": "m2-02-insumo-form.jpg",
    "servico_composicao": "m2-03-servico-composicao.jpg",
    "template_cronograma": "m2-04-template-cronograma.jpg",
    "proposta_form": "m2-05-proposta-form.jpg",
    "cronograma_revisar": "m2-06-cronograma-revisar.jpg",
    "portal_cliente": "m2-07-cliente-portal.jpg",
    "cronograma_obra_admin": "m2-08-cronograma-obra-admin.jpg",
    "obra_detalhes": "m2-09-obra-detalhes.jpg",
}


def record(step, method, url, status_http, ok, evidence="", error="",
           screenshot_ref=None):
    REPORT.append({
        "step": step,
        "method": method,
        "url": url,
        "status_http": status_http,
        "ok": bool(ok),
        "evidence": evidence,
        "error": error,
        "screenshot_ref": screenshot_ref,
    })
    tag = "PASS" if ok else "FAIL"
    (PASS if ok else FAIL).append(step)
    extra = f" — {error}" if error else (f" — {evidence}" if evidence else "")
    print(f"  {tag} [{method} {url} → {status_http}] {step}{extra}")


def http_check(step, response, expected_codes, evidence_extractor=None,
               screenshot_ref=None):
    code = response.status_code
    ok = code in expected_codes
    evidence = ""
    error = ""
    if ok and evidence_extractor:
        try:
            evidence = evidence_extractor(response) or ""
        except Exception as e:
            error = f"evidence_extractor falhou: {e}"
            ok = False
    elif not ok:
        body = response.get_data(as_text=True)[:200].replace("\n", " ")
        error = f"esperado {expected_codes}, body[:200]={body!r}"
    record(step, response.request.method if hasattr(response, "request") else "?",
           getattr(response.request, "path", "?") if hasattr(response, "request") else "?",
           code, ok, evidence=evidence, error=error,
           screenshot_ref=screenshot_ref)
    return ok


def assert_db(step, cond, evidence="", error="", screenshot_ref=None):
    record(step, "DB", "n/a", "—", bool(cond),
           evidence=evidence, error=error if not cond else "",
           screenshot_ref=screenshot_ref)


# ────────────────────────────────────────────────────────────────────
# SEED — apenas pré-requisitos sem UI (admin/cliente/template) +
# patches DB documentados como lacunas de UI conhecidas.
# ────────────────────────────────────────────────────────────────────
def seed_prerequisites():
    """Cria admin V2 + cliente + CronogramaTemplate (com 1 grupo +
    2 subatividades-folha). Estes três NÃO têm rota pública de
    cadastro neste sistema — todo o resto da pipeline é HTTP."""
    admin = Usuario(
        username=f"admin_{RUN_TAG}",
        email=f"{RUN_TAG.lower()}@e2e.local",
        nome=f"Admin {RUN_TAG}",
        password_hash=generate_password_hash("Senha@2026"),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema="v2",
    )
    db.session.add(admin)
    db.session.flush()

    cliente = Cliente(
        admin_id=admin.id,
        nome=f"Cliente {RUN_TAG}",
        email=f"cli_{RUN_TAG.lower()}@e2e.local",
        telefone="11999999999",
    )
    db.session.add(cliente)

    sub_a = SubatividadeMestre(
        admin_id=admin.id,
        nome=f"Preparo de massa {RUN_TAG}",
        unidade_medida="m3",
    )
    sub_b = SubatividadeMestre(
        admin_id=admin.id,
        nome=f"Aplicação {RUN_TAG}",
        unidade_medida="m2",
    )
    db.session.add_all([sub_a, sub_b])
    db.session.flush()

    template = CronogramaTemplate(
        admin_id=admin.id,
        nome=f"Template Alvenaria {RUN_TAG}",
        categoria="Alvenaria",
        ativo=True,
    )
    db.session.add(template)
    db.session.flush()

    grupo = CronogramaTemplateItem(
        template_id=template.id,
        admin_id=admin.id,
        nome_tarefa=f"Etapa Alvenaria {RUN_TAG}",
        ordem=0,
        duracao_dias=10,
    )
    db.session.add(grupo)
    db.session.flush()

    db.session.add_all([
        CronogramaTemplateItem(
            template_id=template.id, admin_id=admin.id,
            parent_item_id=grupo.id, subatividade_mestre_id=sub_a.id,
            nome_tarefa=sub_a.nome, ordem=0, duracao_dias=4,
            responsavel="empresa",
        ),
        CronogramaTemplateItem(
            template_id=template.id, admin_id=admin.id,
            parent_item_id=grupo.id, subatividade_mestre_id=sub_b.id,
            nome_tarefa=sub_b.nome, ordem=1, duracao_dias=6,
            responsavel="empresa",
        ),
    ])
    db.session.commit()
    return admin, cliente, template


def run():
    # Em test_client desabilita CSRF (equivalente a configurar o
    # cabeçalho/token via UI real — irrelevante para o assert do fluxo).
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    with app.app_context():
        admin, cliente, template = seed_prerequisites()
        admin_id = admin.id
        admin_email = admin.email

        client = app.test_client()
        anon = app.test_client()

        # Step 1 — Login admin
        r = client.post("/login",
                        data={"email": admin_email, "password": "Senha@2026"},
                        follow_redirects=False)
        record("Login admin", "POST", "/login", r.status_code,
               r.status_code in (302, 303),
               evidence=f"Set-Cookie={'session' in (r.headers.get('Set-Cookie') or '')}",
               screenshot_ref=SCREENSHOT_REFS["login"])

        # Step 2 — Cria insumo via /catalogo/insumos/novo
        nome_insumo = f"Cimento CPII {RUN_TAG}"
        r = client.post("/catalogo/insumos/novo", data={
            "nome": nome_insumo, "tipo": "MATERIAL", "unidade": "kg",
            "preco": "0.85",
        }, follow_redirects=False)
        record("Cria insumo via UI", "POST", "/catalogo/insumos/novo",
               r.status_code, r.status_code in (302, 303),
               screenshot_ref=SCREENSHOT_REFS["insumo_form"])
        insumo = Insumo.query.filter_by(admin_id=admin_id, nome=nome_insumo).first()
        assert_db("Insumo persistido no DB",
                  insumo is not None,
                  evidence=f"insumo.id={getattr(insumo, 'id', None)}")

        # Step 3 — Cria serviço via /catalogo/servicos/novo
        nome_servico = f"Alvenaria estrutural {RUN_TAG}"
        r = client.post("/catalogo/servicos/novo", data={
            "nome": nome_servico, "categoria": "Estrutura",
            "unidade_medida": "m2", "imposto_pct": "13.5",
            "margem_lucro_pct": "20",
        }, follow_redirects=False)
        record("Cria servico via UI", "POST", "/catalogo/servicos/novo",
               r.status_code, r.status_code in (302, 303),
               screenshot_ref=SCREENSHOT_REFS["servico_composicao"])
        servico = Servico.query.filter_by(admin_id=admin_id, nome=nome_servico).first()
        assert_db("Servico persistido no DB",
                  servico is not None,
                  evidence=f"servico.id={getattr(servico, 'id', None)}")

        # Step 4 — Adiciona composição via UI
        r = client.post(
            f"/catalogo/servicos/{servico.id}/composicao/add",
            data={"insumo_id": str(insumo.id), "coeficiente": "12.5"},
            follow_redirects=False,
        )
        record("Composição (insumo+coef) via UI", "POST",
               f"/catalogo/servicos/{servico.id}/composicao/add",
               r.status_code, r.status_code in (302, 303),
               screenshot_ref=SCREENSHOT_REFS["servico_composicao"])
        comp = ComposicaoServico.query.filter_by(
            servico_id=servico.id, insumo_id=insumo.id).first()
        assert_db("ComposicaoServico persistida",
                  comp is not None and float(comp.coeficiente) == 12.5,
                  evidence=f"coef={comp.coeficiente if comp else None}")

        # Patch S4 — UI inexistente para amarrar template ao serviço (gap #134)
        servico.template_padrao_id = template.id
        db.session.commit()
        record("[gap #134] Servico.template_padrao_id via DB", "DB",
               "n/a", "—", True,
               evidence=f"template_id={template.id} → servico.id={servico.id}",
               screenshot_ref=SCREENSHOT_REFS["template_cronograma"])

        # Step 5 — Cria proposta via /propostas/criar
        numero_prop = f"PROP-{RUN_TAG}"
        r = client.post("/propostas/criar", data={
            "numero_proposta": numero_prop,
            "cliente_nome": cliente.nome,
            "cliente_email": cliente.email or "",
            "cliente_telefone": cliente.telefone or "",
            "assunto": f"Proposta E2E {RUN_TAG}",
            "objeto": "Reforma residencial — teste E2E Task #132",
            "item_descricao": [nome_servico],
            "item_quantidade": ["100"],
            "item_unidade": ["m2"],
            "item_preco": ["120,00"],
            "prazo_entrega_dias": "60",
        }, follow_redirects=False)
        record("Cria proposta via UI", "POST", "/propostas/criar",
               r.status_code, r.status_code in (302, 303),
               screenshot_ref=SCREENSHOT_REFS["proposta_form"])

        prop = Proposta.query.filter_by(admin_id=admin_id, numero=numero_prop).first()
        assert_db("Proposta persistida no DB",
                  prop is not None,
                  evidence=f"proposta.id={getattr(prop, 'id', None)}")

        # Garante token público (rota /criar pode não setar)
        if prop and not prop.token_cliente:
            prop.token_cliente = secrets.token_urlsafe(32)
            db.session.commit()

        # Patch S5 — /propostas/criar não persiste item_servico_id (gap #135)
        item = (PropostaItem.query
                .filter_by(proposta_id=prop.id, admin_id=admin_id)
                .order_by(PropostaItem.ordem).first())
        assert_db("PropostaItem foi criada pela UI",
                  item is not None,
                  evidence=f"item.id={getattr(item, 'id', None)}, desc={getattr(item, 'descricao', None)}")
        if item and not item.servico_id:
            item.servico_id = servico.id
            db.session.commit()
            record("[gap #135] PropostaItem.servico_id via DB", "DB",
                   "n/a", "—", True,
                   evidence=f"item.id={item.id} → servico.id={servico.id}")

        proposta_id = prop.id
        token = prop.token_cliente

        # Step 6 — Admin abre cronograma-revisar
        r = client.get(f"/propostas/{proposta_id}/cronograma-revisar")
        body = r.get_data(as_text=True)
        http_check(
            "Admin GET cronograma-revisar", r, [200],
            evidence_extractor=lambda _r: f"contém serviço={'sim' if nome_servico in body else 'NÃO'}",
            screenshot_ref=SCREENSHOT_REFS["cronograma_revisar"],
        )
        assert_db("cronograma-revisar lista o serviço",
                  nome_servico in body,
                  evidence=f"len(body)={len(body)}")

        # Step 7 — Preview JSON
        r = client.get(f"/propostas/{proposta_id}/cronograma-preview")
        ok_preview = http_check(
            "GET cronograma-preview JSON", r, [200],
            evidence_extractor=lambda _r: f"keys={list((_r.get_json() or {}).keys())}",
        )
        payload = r.get_json() if ok_preview else {}
        arvore = (payload or {}).get("arvore") or []
        assert_db("Preview JSON retorna árvore não-vazia",
                  len(arvore) > 0, evidence=f"raiz={len(arvore)} nó(s)")

        def marcar_tudo(nodes):
            for n in nodes:
                n["marcado"] = True
                if n.get("filhos"):
                    marcar_tudo(n["filhos"])
        marcar_tudo(arvore)

        # Step 8 — Admin salva snapshot (validação pré-aprovação)
        r = client.post(
            f"/propostas/{proposta_id}/cronograma-default",
            data={"cronograma_marcado_json": json.dumps(arvore)},
            follow_redirects=False,
        )
        record("Admin POST cronograma-default", "POST",
               f"/propostas/{proposta_id}/cronograma-default",
               r.status_code, r.status_code in (200, 302))
        db.session.expire_all()
        prop = db.session.get(Proposta, proposta_id)
        assert_db("cronograma_default_json gravado",
                  prop.cronograma_default_json is not None,
                  evidence=f"snapshot_size={len(json.dumps(prop.cronograma_default_json or []))}")

        # Step 9 — Admin envia ao cliente (status RASCUNHO→ENVIADA)
        r = client.post(f"/propostas/{proposta_id}/status",
                        json={"status": "ENVIADA"})
        http_check("Admin POST status ENVIADA", r, [200])
        db.session.expire_all()
        prop = db.session.get(Proposta, proposta_id)
        assert_db("Proposta.status = ENVIADA",
                  (prop.status or "").upper() == "ENVIADA",
                  evidence=f"status={prop.status}")

        # Step 10 — Cliente abre portal (anônimo)
        r = anon.get(f"/propostas/cliente/{token}")
        portal_body = r.get_data(as_text=True)
        http_check("Cliente GET portal", r, [200],
                   evidence_extractor=lambda _r: f"len={len(portal_body)}",
                   screenshot_ref=SCREENSHOT_REFS["portal_cliente"])
        assert_db("Portal NÃO expõe rota cronograma-revisar",
                  "cronograma-revisar" not in portal_body,
                  error="encontrou 'cronograma-revisar' no portal")
        assert_db("Portal NÃO expõe formulário de validação de cronograma",
                  "cronograma_marcado_json" not in portal_body,
                  error="encontrou 'cronograma_marcado_json' no portal")

        # Step 11 — Cliente aprova
        r = anon.post(f"/propostas/cliente/{token}/aprovar",
                      data={"observacoes": "Aprovado — teste E2E"},
                      follow_redirects=False)
        record("Cliente POST aprovar", "POST",
               f"/propostas/cliente/{token}/aprovar",
               r.status_code, r.status_code in (200, 302))
        db.session.expire_all()
        prop = db.session.get(Proposta, proposta_id)
        assert_db("Obra criada (proposta.obra_id != NULL)",
                  prop.obra_id is not None,
                  evidence=f"obra_id={prop.obra_id}")

        # Step 12 — Tarefas materializadas com flag "do contrato"
        tarefas = TarefaCronograma.query.filter_by(obra_id=prop.obra_id).all()
        do_contrato = [t for t in tarefas if t.gerada_por_proposta_item_id is not None]
        assert_db("TarefaCronograma materializadas",
                  len(tarefas) > 0,
                  evidence=f"{len(tarefas)} tarefa(s) na obra {prop.obra_id}")
        assert_db("Tarefas marcadas '📋 do contrato'",
                  len(do_contrato) > 0,
                  evidence=f"{len(do_contrato)} com gerada_por_proposta_item_id")

        # Step 13 — Admin abre cronograma da obra (validação pós-aprovação)
        r = client.get(f"/cronograma/obra/{prop.obra_id}")
        cbody = r.get_data(as_text=True)
        http_check("Admin GET /cronograma/obra/<id>", r, [200],
                   screenshot_ref=SCREENSHOT_REFS["cronograma_obra_admin"])
        assert_db("Página cronograma da obra exibe badge 'do contrato'",
                  "do contrato" in cbody,
                  evidence=f"len(body)={len(cbody)}")

    # ───── Persiste relatório estruturado ─────
    summary = {
        "run_tag": RUN_TAG,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "total": len(REPORT),
        "passed": len(PASS),
        "failed": len(FAIL),
        "screenshots_dir": SCREENSHOTS_DIR,
        "steps": REPORT,
    }
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"E2E Task #132 ({RUN_TAG}) — {len(PASS)} PASS / {len(FAIL)} FAIL")
    print(f"Relatório estruturado: {REPORT_PATH}")
    print(f"Screenshots de referência: {SCREENSHOTS_DIR}/")
    print("=" * 70)
    if FAIL:
        print("\nFALHAS:")
        for f in FAIL:
            entry = next((s for s in REPORT if s["step"] == f), None)
            if entry:
                print(f"  - {f}")
                print(f"      URL: {entry['method']} {entry['url']} → {entry['status_http']}")
                if entry["error"]:
                    print(f"      Erro: {entry['error']}")
                if entry["screenshot_ref"]:
                    print(f"      Screenshot referência: {SCREENSHOTS_DIR}/{entry['screenshot_ref']}")
        sys.exit(1)
    print("OK — fluxo HTTP completo aprovado.")
    sys.exit(0)


if __name__ == "__main__":
    run()
