"""
Task #213 — Playwright e2e: valida que o JS do template
`templates/propostas/cronograma_revisar.html`, agora dentro de
`{% block scripts %}` (era `extra_js`, que `base_completo.html` NÃO
renderiza), realmente executa no browser e leva a revisão do admin
até o servidor com sucesso.

Cobre o "Done looks like" da Task #213 com cliques REAIS em DOM real:

  P1. /propostas/<id>/cronograma-revisar renderiza com tree visível
      (input.inp-horas, input.chk-node, button#btnSalvarPreconfig,
      submit "Aprovar Proposta e Gerar Cronograma").

  P2. Path "Salvar pré-configuração (sem aprovar)":
      admin edita 1ª folha p/ 42 horas + 7 dias, clica
      #btnSalvarPreconfig, browser sai da tela de revisão.
      DB: `propostas_comerciais.cronograma_default_json` é populado
      (>50 bytes), contém "horas_estimadas", contém "42", e a
      `Proposta.status` permanece RASCUNHO.

  P3. Path "Aprovar Proposta e Gerar Cronograma":
      admin reabre a tela, edita 1ª folha p/ 55 horas, clica o submit
      principal. Browser sai da tela.
      DB: `Proposta.status = APROVADA`, `Proposta.obra_id` IS NOT NULL,
      e `TarefaCronograma` materializadas (>0) — prova que o hidden
      `cronograma_marcado_json` chegou populado ao /aprovar.

  Pré-condição: Flask em http://localhost:5000 (workflow "Start
  application"). Banco apontado por DATABASE_URL.

  Uso direto:
      python tests/test_propostas_block_scripts_213_playwright.py

  Nota: o limite de 10 workflows do .replit já está ocupado, então este
  teste não foi registrado como workflow nominal. Quando algum dos
  workflows existentes for retirado, registrar como
  `test-propostas-block-scripts-213-playwright`.
"""
import os
import sys
import json
import logging
import secrets
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario,
    Cliente,
    Insumo, Servico, ComposicaoServico,
    CronogramaTemplate, CronogramaTemplateItem,
    SubatividadeMestre,
    Proposta, PropostaItem,
    TarefaCronograma,
    Obra,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = os.environ.get("PW_BASE_URL", "http://localhost:5000")
SENHA = "Senha@2026"
RUN_TAG = f"E2E213PW-{secrets.token_hex(3).upper()}"


def seed():
    """admin + cliente + insumo + servico (template_padrao_id) + composicao
    + Proposta (RASCUNHO) + PropostaItem. Retorna dict com ids."""
    with app.app_context():
        admin = Usuario(
            username=f"admin_{RUN_TAG}",
            email=f"{RUN_TAG.lower()}@e2e.local",
            nome=f"Admin {RUN_TAG}",
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema="v2",
        )
        db.session.add(admin); db.session.flush()

        cliente = Cliente(
            admin_id=admin.id, nome=f"Cliente {RUN_TAG}",
            email=f"cli_{RUN_TAG.lower()}@e2e.local", telefone="11999999999",
        )
        db.session.add(cliente); db.session.flush()

        sub_a = SubatividadeMestre(admin_id=admin.id,
                                   nome=f"Preparo {RUN_TAG}", unidade_medida="m3")
        sub_b = SubatividadeMestre(admin_id=admin.id,
                                   nome=f"Aplicacao {RUN_TAG}", unidade_medida="m2")
        db.session.add_all([sub_a, sub_b]); db.session.flush()

        template = CronogramaTemplate(admin_id=admin.id, nome=f"Tpl {RUN_TAG}",
                                      categoria="Estrutura", ativo=True)
        db.session.add(template); db.session.flush()

        grupo = CronogramaTemplateItem(
            template_id=template.id, admin_id=admin.id,
            nome_tarefa=f"Etapa {RUN_TAG}", ordem=0, duracao_dias=10,
        )
        db.session.add(grupo); db.session.flush()
        db.session.add_all([
            CronogramaTemplateItem(
                template_id=template.id, admin_id=admin.id,
                parent_item_id=grupo.id, subatividade_mestre_id=sub_a.id,
                nome_tarefa=sub_a.nome, ordem=0, duracao_dias=4, responsavel="empresa",
            ),
            CronogramaTemplateItem(
                template_id=template.id, admin_id=admin.id,
                parent_item_id=grupo.id, subatividade_mestre_id=sub_b.id,
                nome_tarefa=sub_b.nome, ordem=1, duracao_dias=6, responsavel="empresa",
            ),
        ])
        db.session.commit()

        insumo = Insumo(admin_id=admin.id, nome=f"Cimento {RUN_TAG}",
                        tipo="MATERIAL", unidade="kg")
        db.session.add(insumo); db.session.flush()

        servico = Servico(
            admin_id=admin.id, nome=f"Servico {RUN_TAG}",
            categoria="Estrutura", unidade_medida="m2",
            imposto_pct=13.5, margem_lucro_pct=20,
            template_padrao_id=template.id,
        )
        db.session.add(servico); db.session.flush()

        db.session.add(ComposicaoServico(
            admin_id=admin.id, servico_id=servico.id,
            insumo_id=insumo.id, coeficiente=12.5,
        ))
        db.session.commit()

        prop = Proposta(
            admin_id=admin.id, numero=f"PROP-{RUN_TAG}",
            cliente_nome=cliente.nome, cliente_email=cliente.email,
            cliente_telefone=cliente.telefone, cliente_id=cliente.id,
            titulo=f"Reforma {RUN_TAG}",
            status="RASCUNHO", valor_total=12000, prazo_entrega_dias=60,
        )
        db.session.add(prop); db.session.flush()

        item = PropostaItem(
            admin_id=admin.id, proposta_id=prop.id, item_numero=1,
            descricao=servico.nome, servico_id=servico.id,
            quantidade=100, unidade="m2", preco_unitario=120,
            subtotal=12000, ordem=0,
        )
        db.session.add(item); db.session.commit()

        return dict(
            admin_id=admin.id, admin_email=admin.email,
            cliente_id=cliente.id,
            sub_a_id=sub_a.id, sub_b_id=sub_b.id,
            servico_id=servico.id, template_id=template.id,
            insumo_id=insumo.id,
            proposta_id=prop.id, item_id=item.id,
        )


def cleanup(ctx):
    with app.app_context():
        try:
            obra_id = db.session.query(Proposta.obra_id).filter_by(id=ctx["proposta_id"]).scalar()
            if obra_id:
                TarefaCronograma.query.filter_by(obra_id=obra_id).delete()
                Obra.query.filter_by(id=obra_id).delete()
            PropostaItem.query.filter_by(proposta_id=ctx["proposta_id"]).delete()
            Proposta.query.filter_by(id=ctx["proposta_id"]).delete()
            ComposicaoServico.query.filter_by(servico_id=ctx["servico_id"]).delete()
            Servico.query.filter_by(id=ctx["servico_id"]).delete()
            Insumo.query.filter_by(id=ctx["insumo_id"]).delete()
            CronogramaTemplateItem.query.filter_by(template_id=ctx["template_id"]).delete()
            CronogramaTemplate.query.filter_by(id=ctx["template_id"]).delete()
            SubatividadeMestre.query.filter(
                SubatividadeMestre.id.in_([ctx["sub_a_id"], ctx["sub_b_id"]])
            ).delete(synchronize_session=False)
            Cliente.query.filter_by(id=ctx["cliente_id"]).delete()
            Usuario.query.filter_by(id=ctx["admin_id"]).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            log.warning(f"cleanup falhou (não fatal): {e}")


def run():
    ctx = seed()
    log.info(f"seed: proposta_id={ctx['proposta_id']} admin={ctx['admin_email']}")
    failed, passed = [], []

    def ok(cond, label, detail=""):
        (passed if cond else failed).append(label)
        tag = "PASS" if cond else "FAIL"
        extra = f" — {detail}" if detail else ""
        log.info(f"{tag} {label}{extra}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            page = context.new_page()

            # ── 1) login ───────────────────────────────────────────────
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
            page.fill('input[name="username"]', ctx["admin_email"])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state("networkidle")
            ok("/login" not in page.url, "P0 login redireciona", f"url={page.url}")

            # ── 2) PATH A — Salvar pré-configuração ────────────────────
            url_revisar = f"{BASE_URL}/propostas/{ctx['proposta_id']}/cronograma-revisar"
            page.goto(url_revisar, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")

            ok("Revisar Cronograma" in page.content() or "cronograma" in page.content().lower(),
               "P1.a página de revisão carregou")
            inp_horas = page.locator("input.inp-horas").first
            inp_dias = page.locator("input.inp-dias").first
            chk_raiz = page.locator("input.chk-raiz").first
            btn_pre = page.locator("#btnSalvarPreconfig")
            btn_aprovar = page.locator('button[type="submit"]:has-text("Aprovar Proposta")')

            ok(inp_horas.count() > 0, "P1.b input.inp-horas presente")
            ok(page.locator("input.chk-node").count() > 0, "P1.c input.chk-node presente")
            ok(btn_pre.count() > 0, "P1.d btn salvar pré-configuração presente")
            ok(btn_aprovar.count() > 0, "P1.e btn aprovar presente")

            # garante folhas todas marcadas (caso algum chk-raiz/node esteja off)
            if chk_raiz.count() > 0 and not chk_raiz.is_checked():
                chk_raiz.check()
            inp_horas.fill("42")
            inp_horas.dispatch_event("input")
            inp_dias.fill("7")
            inp_dias.dispatch_event("input")

            btn_pre.click()
            page.wait_for_load_state("networkidle")
            ok("/cronograma-revisar" not in page.url,
               "P2.a saiu da tela de revisão após pré-configurar",
               f"url={page.url}")

            with app.app_context():
                db.session.expire_all()
                p_db = Proposta.query.get(ctx["proposta_id"])
                snap = p_db.cronograma_default_json
                snap_str = json.dumps(snap) if snap else ""
                ok(snap is not None and len(snap_str) > 50,
                   "P2.b snapshot persistido", f"len={len(snap_str)}")
                ok("horas_estimadas" in snap_str, "P2.c snapshot contém horas_estimadas")
                ok("42" in snap_str, "P2.d snapshot contém '42'")
                ok((p_db.status or "").upper() == "RASCUNHO",
                   "P2.e status permanece RASCUNHO", f"status={p_db.status}")

            # ── 3) PATH B — Aprovar Proposta e Gerar Cronograma ────────
            #     Aqui validamos NÃO só que houve materialização, mas que
            #     as edições específicas do admin foram refletidas:
            #       - duracao_dias=9 da sub_a (folha #0) chega ao DB
            #       - sub_b DESMARCADA não vira tarefa
            page.goto(url_revisar, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")

            inp_horas_list = page.locator("input.inp-horas")
            inp_dias_list = page.locator("input.inp-dias")
            ok(inp_horas_list.count() >= 2, "P3.a tela reabriu c/ 2 folhas",
               f"n_horas={inp_horas_list.count()}")

            # Edita sub_a (folha #0)
            inp_horas_list.first.fill("55")
            inp_horas_list.first.dispatch_event("input")
            inp_dias_list.first.fill("9")
            inp_dias_list.first.dispatch_event("input")

            # Garante chk-raiz marcado (root da raiz do serviço)
            for i in range(page.locator("input.chk-raiz").count()):
                cb = page.locator("input.chk-raiz").nth(i)
                if not cb.is_checked():
                    cb.check()

            # DESMARCA a 2ª folha (sub_b) — chk-node da 2ª li.node-sub
            sub_b_li = page.locator("li.node-sub").nth(1)
            sub_b_chk = sub_b_li.locator("> .node-label > input.chk-node")
            ok(sub_b_chk.count() == 1, "P3.b chk-node sub_b localizado")
            if sub_b_chk.is_checked():
                sub_b_chk.uncheck()
            ok(not sub_b_chk.is_checked(), "P3.c chk-node sub_b agora desmarcado")

            page.locator('button[type="submit"]:has-text("Aprovar Proposta")').first.click()
            page.wait_for_load_state("networkidle")
            ok("/cronograma-revisar" not in page.url,
               "P3.d saiu da tela após aprovar", f"url={page.url}")

            sub_a_nome = f"Preparo {RUN_TAG}"
            sub_b_nome = f"Aplicacao {RUN_TAG}"

            with app.app_context():
                db.session.expire_all()
                p_db = Proposta.query.get(ctx["proposta_id"])
                ok((p_db.status or "").upper() == "APROVADA",
                   "P3.e status = APROVADA", f"status={p_db.status}")
                ok(p_db.obra_id is not None,
                   "P3.f obra_id criado", f"obra_id={p_db.obra_id}")
                if p_db.obra_id:
                    tarefas = TarefaCronograma.query.filter_by(
                        obra_id=p_db.obra_id, is_cliente=False).all()
                    nomes = sorted(t.nome_tarefa for t in tarefas)
                    ok(len(tarefas) > 0,
                       "P3.g TarefaCronograma materializadas (>0)",
                       f"n_tarefas={len(tarefas)} nomes={nomes}")

                    # sub_a foi materializada com a duracao editada (9 dias)
                    t_a = next((t for t in tarefas if t.nome_tarefa == sub_a_nome), None)
                    ok(t_a is not None,
                       "P3.h sub_a (marcada) materializada como tarefa",
                       f"encontrada={bool(t_a)}")
                    if t_a:
                        ok(int(t_a.duracao_dias or 0) == 9,
                           "P3.i sub_a tem duracao_dias=9 (edição do admin refletida)",
                           f"duracao_dias={t_a.duracao_dias}")

                    # sub_b (desmarcada) NÃO pode ter virado tarefa
                    t_b = next((t for t in tarefas if t.nome_tarefa == sub_b_nome), None)
                    ok(t_b is None,
                       "P3.j sub_b (desmarcada) NÃO foi materializada",
                       f"tarefa_b_inesperada={t_b.id if t_b else None}")

            browser.close()

    finally:
        cleanup(ctx)

    log.info("=" * 70)
    log.info(f"PASSED: {len(passed)}  FAILED: {len(failed)}")
    log.info("=" * 70)
    if failed:
        for label in failed:
            log.error(f"FAIL {label}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    run()
