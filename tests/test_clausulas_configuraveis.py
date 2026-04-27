"""
Task #174 — Teste E2E HTTP de cláusulas configuráveis em propostas.

Cobre:
  1. Criar Proposta com cláusulas configuráveis (título + texto + ordem)
     via models — incluindo uma cláusula com texto vazio (deve ficar
     oculta) e uma cláusula extra (não-padrão).
  2. GET /propostas/<id>/pdf?formato=padrao        → renderiza pdf.html
     usando o partial _clausulas.html.
  3. GET /propostas/<id>/pdf?formato=estruturas_vale → renderiza
     pdf_estruturas_vale_paginado.html usando o mesmo partial.
  4. GET /propostas/cliente/<token>                → renderiza
     portal_cliente.html usando o mesmo partial (acesso anônimo).

Em cada renderização valida:
  - Cláusula com texto preenchido aparece (título + texto).
  - Cláusula com texto vazio NÃO aparece (nem o título).
  - Ordem de exibição respeita Clausula.ordem.
  - Cláusulas extras (custom) aparecem ao lado das padrão.

Executa com:  python tests/test_clausulas_configuraveis.py
Workflow Replit: `test-clausulas-configuraveis` (a registrar).

Exit code 0 → todos os asserts passaram.
"""
import os
import sys
import json
import secrets
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario,
    Proposta,
    PropostaClausula,
    PropostaTemplate,
    PropostaTemplateClausula,
)

RUN_TAG = f"CLAUS174-{secrets.token_hex(3).upper()}"
REPORT_PATH = ".local/clausulas_step_report.json"
_steps = []


def record(step, ok, evidence="", error=""):
    _steps.append({
        "step": step,
        "ok": bool(ok),
        "evidence": evidence,
        "error": error,
    })
    status = "[OK]" if ok else "[FAIL]"
    extra = f" — {error}" if error else (f" — {evidence}" if evidence else "")
    print(f"  {status} {step}{extra}")


def write_report():
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    summary = {
        "tag": RUN_TAG,
        "ts": datetime.utcnow().isoformat() + "Z",
        "total": len(_steps),
        "passed": sum(1 for s in _steps if s["ok"]),
        "failed": sum(1 for s in _steps if not s["ok"]),
        "steps": _steps,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)
    return summary


def seed_admin_proposta():
    """Cria admin + proposta com 5 cláusulas (1 vazia, 4 visíveis em
    ordem não-natural pra provar que ordering é respeitado)."""
    admin = Usuario(
        username=f"admin_{RUN_TAG.lower()}",
        email=f"{RUN_TAG.lower()}@e2e.local",
        nome=f"Admin {RUN_TAG}",
        password_hash=generate_password_hash("Senha@2026"),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema="v2",
    )
    db.session.add(admin)
    db.session.flush()

    token = secrets.token_urlsafe(24)
    proposta = Proposta(
        admin_id=admin.id,
        criado_por=admin.id,
        numero=f"PROP-{RUN_TAG}",
        titulo=f"Proposta cláusulas {RUN_TAG}",
        descricao="Teste de cláusulas configuráveis",
        cliente_nome=f"Cliente {RUN_TAG}",
        cliente_email=f"cli_{RUN_TAG.lower()}@e2e.local",
        cliente_telefone="11999999999",
        cliente_endereco="Rua Teste, 123",
        valor_total=Decimal("10000.00"),
        prazo_entrega_dias=45,
        validade_dias=30,
        percentual_nota_fiscal=13.5,
        status="ENVIADA",
        token_cliente=token,
    )
    db.session.add(proposta)
    db.session.flush()

    # Cinco cláusulas — propositalmente fora de ordem para provar
    # que o partial usa Clausula.ordem (e não a ordem de inserção).
    db.session.add_all([
        PropostaClausula(
            proposta_id=proposta.id, admin_id=admin.id,
            titulo="Considerações Gerais", ordem=4,
            texto=f"Considerações gerais marker {RUN_TAG}.",
        ),
        PropostaClausula(
            proposta_id=proposta.id, admin_id=admin.id,
            titulo="Condições de Pagamento", ordem=1,
            texto=f"Pagamento marker {RUN_TAG}: 50/50.",
        ),
        PropostaClausula(
            proposta_id=proposta.id, admin_id=admin.id,
            titulo="Cláusula extra customizada", ordem=5,
            texto=f"Extra marker {RUN_TAG}: cláusula adicional.",
        ),
        PropostaClausula(
            proposta_id=proposta.id, admin_id=admin.id,
            titulo="Garantias", ordem=3,
            texto=f"Garantia marker {RUN_TAG}: 12 meses.",
        ),
        # Cláusula com texto vazio — DEVE ficar oculta no render.
        PropostaClausula(
            proposta_id=proposta.id, admin_id=admin.id,
            titulo="Cláusula oculta marker " + RUN_TAG, ordem=2,
            texto="   ",
        ),
    ])
    db.session.commit()
    return admin, proposta, token


def assert_clausulas_visiveis(label, html):
    """Aplica os 5 asserts críticos do partial sobre um HTML render."""
    visiveis = [
        ("Pagamento marker",     f"Pagamento marker {RUN_TAG}"),
        ("Garantia marker",      f"Garantia marker {RUN_TAG}"),
        ("Considerações marker", f"Considerações gerais marker {RUN_TAG}"),
        ("Extra marker",         f"Extra marker {RUN_TAG}"),
    ]
    for nome, marker in visiveis:
        record(
            f"{label} — cláusula visível ({nome})",
            marker in html,
            evidence=f"marker={marker!r}",
            error=("texto não encontrado no HTML render" if marker not in html else ""),
        )

    # Cláusula oculta NÃO deve aparecer (nem o título único).
    titulo_oculto = f"Cláusula oculta marker {RUN_TAG}"
    record(
        f"{label} — cláusula oculta (texto vazio) NÃO aparece",
        titulo_oculto not in html,
        evidence=f"titulo_oculto={titulo_oculto!r}",
        error=("título da cláusula oculta apareceu no render"
               if titulo_oculto in html else ""),
    )

    # Ordering — Pagamento (ordem 1) precisa vir antes de Garantia (3),
    # que precisa vir antes de Considerações (4), antes de Extra (5).
    pos_pag    = html.find(f"Pagamento marker {RUN_TAG}")
    pos_gar    = html.find(f"Garantia marker {RUN_TAG}")
    pos_consid = html.find(f"Considerações gerais marker {RUN_TAG}")
    pos_extra  = html.find(f"Extra marker {RUN_TAG}")
    ord_ok = -1 < pos_pag < pos_gar < pos_consid < pos_extra
    record(
        f"{label} — ordering respeita Clausula.ordem",
        ord_ok,
        evidence=f"posições pag={pos_pag} gar={pos_gar} consid={pos_consid} extra={pos_extra}",
        error=("posições fora de ordem" if not ord_ok else ""),
    )


def run():
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    with app.app_context():
        admin, proposta, token = seed_admin_proposta()
        admin_email = admin.email
        proposta_id = proposta.id

        client = app.test_client()
        anon   = app.test_client()

        # 1) Verifica via DB que a relação backref carrega ordenado.
        p_db = Proposta.query.get(proposta_id)
        ordens = [(c.ordem, c.titulo) for c in p_db.clausulas]
        record(
            "Backref Proposta.clausulas ordenado por ordem",
            ordens == sorted(ordens, key=lambda t: t[0]),
            evidence=f"ordens={ordens}",
        )
        record(
            "Proposta tem 5 cláusulas persistidas (incluindo a vazia)",
            len(p_db.clausulas) == 5,
            evidence=f"len={len(p_db.clausulas)}",
        )

        # 2) Login admin (necessário para PDF rotas internas)
        r = client.post("/login",
                        data={"email": admin_email, "password": "Senha@2026"},
                        follow_redirects=False)
        record("Login admin", r.status_code in (302, 303),
               evidence=f"status={r.status_code}")

        # 3) GET PDF formato 'padrao' (templates/propostas/pdf.html)
        r = client.get(f"/propostas/{proposta_id}/pdf?formato=padrao")
        ok = r.status_code == 200
        record("GET /propostas/<id>/pdf?formato=padrao retorna 200", ok,
               evidence=f"status={r.status_code}, len={len(r.data)}")
        if ok:
            html_pdf_padrao = r.get_data(as_text=True)
            record(
                "pdf.html (padrao) usa o partial _clausulas.html "
                "(classe proposta-clausula presente)",
                'proposta-clausula' in html_pdf_padrao,
                evidence="classe proposta-clausula encontrada",
                error=("partial _clausulas.html não foi incluído"
                       if 'proposta-clausula' not in html_pdf_padrao else ""),
            )
            assert_clausulas_visiveis("pdf.html(padrao)", html_pdf_padrao)
            # Sanity — bloco "VALIDADE DA PROPOSTA" continua presente
            # (não foi removido ao tirar as seções fixas).
            record(
                "pdf.html(padrao) preserva bloco VALIDADE",
                "VALIDADE DA PROPOSTA" in html_pdf_padrao,
                evidence="texto VALIDADE DA PROPOSTA presente",
            )

        # 4) GET PDF formato 'estruturas_vale' (paginado)
        r = client.get(f"/propostas/{proposta_id}/pdf?formato=estruturas_vale")
        ok = r.status_code == 200
        record("GET /propostas/<id>/pdf?formato=estruturas_vale retorna 200", ok,
               evidence=f"status={r.status_code}, len={len(r.data)}")
        if ok:
            html_pdf_paginado = r.get_data(as_text=True)
            record(
                "pdf_estruturas_vale_paginado.html usa o partial _clausulas.html",
                'proposta-clausula' in html_pdf_paginado,
                evidence="classe proposta-clausula encontrada",
                error=("partial _clausulas.html não foi incluído"
                       if 'proposta-clausula' not in html_pdf_paginado else ""),
            )
            assert_clausulas_visiveis(
                "pdf_estruturas_vale_paginado", html_pdf_paginado
            )
            # Sanity — VALIDADE continua presente.
            record(
                "pdf_estruturas_vale preserva bloco VALIDADE",
                "VALIDADE DA PROPOSTA" in html_pdf_paginado,
                evidence="texto VALIDADE DA PROPOSTA presente",
            )

        # 5) GET portal_cliente (anônimo)
        r = anon.get(f"/propostas/cliente/{token}")
        ok = r.status_code == 200
        record("GET /propostas/cliente/<token> retorna 200 (anônimo)", ok,
               evidence=f"status={r.status_code}, len={len(r.data)}")
        if ok:
            html_portal = r.get_data(as_text=True)
            record(
                "portal_cliente.html usa o partial _clausulas.html",
                'proposta-clausula' in html_portal,
                evidence="classe proposta-clausula encontrada",
                error=("partial _clausulas.html não foi incluído"
                       if 'proposta-clausula' not in html_portal else ""),
            )
            assert_clausulas_visiveis("portal_cliente", html_portal)
            # Portal continua mostrando o prazo numérico (não migrou
            # para cláusula).
            record(
                "portal_cliente preserva bloco 'Prazo de Execução' (numérico)",
                "Prazo de Execução" in html_portal,
                evidence="texto 'Prazo de Execução' presente",
            )

        # 6) Modelo de Template também tem cláusulas — sanity simples
        # criando 1 template + 2 cláusulas e verificando o backref.
        tmpl = PropostaTemplate(
            admin_id=admin.id,
            nome=f"Template {RUN_TAG}",
            descricao="t",
            ativo=True,
            categoria="GERAL",
        )
        db.session.add(tmpl)
        db.session.flush()
        db.session.add_all([
            PropostaTemplateClausula(
                proposta_template_id=tmpl.id, admin_id=admin.id,
                titulo="Objeto", texto="Texto do objeto", ordem=1,
            ),
            PropostaTemplateClausula(
                proposta_template_id=tmpl.id, admin_id=admin.id,
                titulo="Validade", texto="Validade da proposta", ordem=2,
            ),
        ])
        db.session.commit()
        tmpl_db = PropostaTemplate.query.get(tmpl.id)
        record(
            "PropostaTemplate.clausulas backref funciona",
            len(tmpl_db.clausulas) == 2 and
            tmpl_db.clausulas[0].titulo == "Objeto",
            evidence=f"clausulas={[c.titulo for c in tmpl_db.clausulas]}",
        )

        # ===== Task #174 (rev2) — UI de gerência de Templates =====
        # 7) GET /propostas/templates exibe template criado acima
        r = client.get("/propostas/templates")
        ok = r.status_code == 200
        record("GET /propostas/templates retorna 200", ok,
               evidence=f"status={r.status_code}")
        if ok:
            html_lst = r.get_data(as_text=True)
            record(
                "templates_lista.html mostra o template seed",
                f"Template {RUN_TAG}" in html_lst,
                evidence="nome do template encontrado na lista",
                error=("nome do template não foi renderizado"
                       if f"Template {RUN_TAG}" not in html_lst else ""),
            )

        # 8) GET /propostas/templates/novo — formulário em branco renderiza
        r = client.get("/propostas/templates/novo")
        record("GET /propostas/templates/novo retorna 200",
               r.status_code == 200,
               evidence=f"status={r.status_code}")

        # 9) POST /propostas/templates/criar — cria template via UI com
        #    cláusulas configuráveis (incluindo uma cláusula vazia que
        #    deve ser descartada).
        nome_ui = f"TemplateUI {RUN_TAG}"
        r = client.post("/propostas/templates/criar", data={
            "nome": nome_ui,
            "categoria": "TestCat",
            "descricao": "Criado via UI no teste E2E",
            "ativo": "on",
            # Bloco dinâmico de cláusulas (3 entradas — 1 vazia)
            "clausula_titulo": [
                "Objeto UI", "Pagamento UI", "Vazia UI",
            ],
            "clausula_texto": [
                f"Objeto-UI marker {RUN_TAG}",
                f"Pagamento-UI marker {RUN_TAG}",
                "",  # vazia → descartada
            ],
            "clausula_ordem": ["1", "2", "3"],
        }, follow_redirects=False)
        ok = r.status_code in (302, 303)
        record("POST /propostas/templates/criar redireciona após sucesso", ok,
               evidence=f"status={r.status_code} location={r.headers.get('Location','')}")

        tmpl_ui = PropostaTemplate.query.filter_by(
            admin_id=admin.id, nome=nome_ui,
        ).first()
        record("Template UI persistido no DB",
               tmpl_ui is not None,
               evidence=f"id={getattr(tmpl_ui,'id',None)}")
        if tmpl_ui:
            cls_ui = sorted(tmpl_ui.clausulas, key=lambda c: c.ordem)
            titulos_ui = [c.titulo for c in cls_ui]
            record(
                "Template UI tem 2 cláusulas (a vazia foi descartada)",
                len(cls_ui) == 2,
                evidence=f"titulos={titulos_ui}",
                error=("número de cláusulas inesperado" if len(cls_ui) != 2 else ""),
            )
            record(
                "Template UI ordering preservada (Objeto < Pagamento)",
                len(cls_ui) >= 2 and
                cls_ui[0].titulo == "Objeto UI" and
                cls_ui[1].titulo == "Pagamento UI",
                evidence=f"ordem={titulos_ui}",
            )

        # 10) GET /propostas/templates/<id>/editar e POST atualizar:
        #     remove uma cláusula (texto vazio) e adiciona uma nova.
        if tmpl_ui:
            r = client.get(f"/propostas/templates/{tmpl_ui.id}/editar")
            ok = r.status_code == 200
            record("GET /propostas/templates/<id>/editar retorna 200", ok,
                   evidence=f"status={r.status_code}")
            if ok:
                html_edit = r.get_data(as_text=True)
                record(
                    "template_form.html (editar) inclui texto da cláusula",
                    f"Objeto-UI marker {RUN_TAG}" in html_edit,
                    evidence="texto da cláusula presente no form de edição",
                )

            r = client.post(
                f"/propostas/templates/{tmpl_ui.id}/atualizar",
                data={
                    "nome": nome_ui + " v2",
                    "categoria": "TestCat",
                    "descricao": "Editado via UI",
                    "ativo": "on",
                    "clausula_titulo": [
                        "Objeto UI", "Pagamento UI", "Garantia Nova UI",
                    ],
                    "clausula_texto": [
                        "",  # remove a cláusula Objeto
                        f"Pagamento-UI marker {RUN_TAG}",
                        f"GarantiaNova-UI marker {RUN_TAG}",
                    ],
                    "clausula_ordem": ["1", "2", "3"],
                },
                follow_redirects=False,
            )
            record(
                "POST /propostas/templates/<id>/atualizar redireciona",
                r.status_code in (302, 303),
                evidence=f"status={r.status_code}",
            )
            db.session.expire_all()
            tmpl_ui_db = PropostaTemplate.query.get(tmpl_ui.id)
            cls_after = sorted(tmpl_ui_db.clausulas, key=lambda c: c.ordem)
            titulos_after = [c.titulo for c in cls_after]
            record(
                "Após edição UI: Objeto removido, Garantia adicionada",
                len(cls_after) == 2 and
                set(titulos_after) == {"Pagamento UI", "Garantia Nova UI"},
                evidence=f"titulos_apos={titulos_after}",
                error=("regrade de cláusulas falhou" if not (
                    len(cls_after) == 2 and
                    set(titulos_after) == {"Pagamento UI", "Garantia Nova UI"}
                ) else ""),
            )
            record(
                "Após edição UI: nome do template foi atualizado",
                tmpl_ui_db.nome == nome_ui + " v2",
                evidence=f"nome={tmpl_ui_db.nome}",
            )

        # 11) Criar Proposta via /propostas/criar usando template_id —
        #     as cláusulas devem ser COPIADAS do template (não do seed
        #     legado). Usa o template UI atualizado no passo 10.
        if tmpl_ui:
            r = client.post("/propostas/criar", data={
                "cliente_nome": f"Cliente Tmpl {RUN_TAG}",
                "cliente_email": f"cli_tmpl_{RUN_TAG.lower()}@e2e.local",
                "cliente_telefone": "11988880000",
                "cliente_endereco": "Av Template, 999",
                "titulo": f"Proposta-vinda-de-template {RUN_TAG}",
                "descricao": "criada via template_id",
                "prazo_entrega_dias": "60",
                "percentual_nota_fiscal": "13.5",
                "template_id": str(tmpl_ui.id),
                # Seed legado também presente — deve ser IGNORADO porque
                # o template tem cláusulas (prioridade #1).
                "condicoes_pagamento": "SEED-LEGADO-NAO-DEVE-APARECER",
                "garantias": "SEED-LEGADO-NAO-DEVE-APARECER",
                # Sem itens — proposta vazia é aceita
            }, follow_redirects=False)
            ok = r.status_code in (302, 303)
            record(
                "POST /propostas/criar com template_id redireciona após sucesso",
                ok,
                evidence=f"status={r.status_code}",
            )

            prop_tmpl = Proposta.query.filter_by(
                admin_id=admin.id,
                titulo=f"Proposta-vinda-de-template {RUN_TAG}",
            ).first()
            record(
                "Proposta criada a partir do template existe no DB",
                prop_tmpl is not None,
                evidence=f"id={getattr(prop_tmpl,'id',None)}",
            )
            if prop_tmpl:
                cls_prop = sorted(prop_tmpl.clausulas, key=lambda c: c.ordem)
                titulos_prop = [c.titulo for c in cls_prop]
                record(
                    "Proposta tem cláusulas COPIADAS do template (2 itens)",
                    len(cls_prop) == 2 and
                    set(titulos_prop) == {"Pagamento UI", "Garantia Nova UI"},
                    evidence=f"titulos={titulos_prop}",
                    error=("cláusulas do template não foram copiadas"
                           if not (
                               len(cls_prop) == 2 and
                               set(titulos_prop) == {"Pagamento UI", "Garantia Nova UI"}
                           ) else ""),
                )
                # Garante que o seed legado foi IGNORADO (prioridade
                # #1 do template). Nenhuma cláusula deve ter o título
                # legado nem o texto-marker legado.
                tem_seed_legado = any(
                    "SEED-LEGADO-NAO-DEVE-APARECER" in (c.texto or '')
                    for c in cls_prop
                )
                record(
                    "Seed legado IGNORADO quando template fornece cláusulas",
                    not tem_seed_legado,
                    evidence="nenhum texto SEED-LEGADO encontrado",
                    error=("seed legado vazou — prioridade do template quebrou"
                           if tem_seed_legado else ""),
                )
                # Texto da cláusula do template está realmente lá
                record(
                    "Texto Pagamento-UI marker presente nas cláusulas copiadas",
                    any(f"Pagamento-UI marker {RUN_TAG}" in (c.texto or '')
                        for c in cls_prop),
                    evidence="marker do template encontrado",
                )

        # 12) Criar Proposta SEM template_id — cai no seed legado
        #     (regressão garantida).
        r = client.post("/propostas/criar", data={
            "cliente_nome": f"Cliente Seed {RUN_TAG}",
            "cliente_email": f"cli_seed_{RUN_TAG.lower()}@e2e.local",
            "cliente_telefone": "11977770000",
            "cliente_endereco": "Av Seed, 1",
            "titulo": f"Proposta-seed-legado {RUN_TAG}",
            "descricao": "sem template_id",
            "prazo_entrega_dias": "30",
            "percentual_nota_fiscal": "13.5",
            "condicoes_pagamento": f"SeedPagto marker {RUN_TAG}",
            "garantias": f"SeedGarantia marker {RUN_TAG}",
            "consideracoes_gerais": f"SeedGeral marker {RUN_TAG}",
        }, follow_redirects=False)
        record(
            "POST /propostas/criar SEM template_id redireciona",
            r.status_code in (302, 303),
            evidence=f"status={r.status_code}",
        )
        prop_seed = Proposta.query.filter_by(
            admin_id=admin.id,
            titulo=f"Proposta-seed-legado {RUN_TAG}",
        ).first()
        if prop_seed:
            textos_seed = [(c.titulo, c.texto) for c in prop_seed.clausulas]
            record(
                "Sem template_id: 3 cláusulas seedadas a partir dos campos legados",
                len(prop_seed.clausulas) == 3,
                evidence=f"clausulas={textos_seed}",
            )
            record(
                "Seed legado preservou marker de pagamento",
                any(f"SeedPagto marker {RUN_TAG}" in (t or '')
                    for _, t in textos_seed),
                evidence="texto seedado encontrado",
            )

        # 13) REV4 — Renderização unificada via _clausulas.html.
        #     Proposta SEM cláusulas configuradas E com legacy fields NULL
        #     deve renderizar 200, NÃO mostrar nenhum texto hardcoded
        #     histórico (nem '25% de entrada', nem 'limita-se a reparar',
        #     nem 'NBR 8800', etc.) e NÃO mostrar texto dos campos legados.
        #     Trust no migration 134: backfill já converteu legacy → cláusulas.
        from models import Cliente as _Cliente
        from sqlalchemy import text as _sql_text
        cli_legacy = _Cliente(
            admin_id=admin.id,
            nome=f"Cliente Legacy Vazio {RUN_TAG}",
            email=f"cli_legacy_vazio_{RUN_TAG.lower()}@e2e.local",
        )
        db.session.add(cli_legacy)
        db.session.flush()
        prop_vazia = Proposta(
            admin_id=admin.id,
            numero=f"PROP-LE-{RUN_TAG}",
            titulo=f"Proposta Legacy Vazia {RUN_TAG}",
            cliente_nome=cli_legacy.nome,
            cliente_email=cli_legacy.email,
            cliente_id=cli_legacy.id,
            status="rascunho",
            valor_total=Decimal("100.00"),
        )
        db.session.add(prop_vazia)
        db.session.flush()
        # Forçamos NULL via SQL p/ bypassar defaults Python-side do modelo.
        db.session.execute(
            _sql_text(
                "UPDATE propostas_comerciais "
                "SET condicoes_pagamento=NULL, garantias=NULL, consideracoes_gerais=NULL "
                "WHERE id=:id"
            ),
            {"id": prop_vazia.id},
        )
        db.session.commit()
        db.session.refresh(prop_vazia)
        record(
            "REV4: Proposta sem cláusulas e legacy NULL — sanidade",
            len(prop_vazia.clausulas) == 0,
            evidence=f"clausulas={len(prop_vazia.clausulas)}",
        )
        r_pdf_legacy = client.get(
            f"/propostas/{prop_vazia.id}/pdf?formato=estruturas_vale"
        )
        record(
            "REV4: GET /propostas/<id>/pdf?formato=estruturas_vale (sem cláusulas) retorna 200",
            r_pdf_legacy.status_code == 200,
            evidence=f"status={r_pdf_legacy.status_code}",
        )
        body_legacy = r_pdf_legacy.get_data(as_text=True)
        # Hardcoded histórico NÃO deve mais aparecer — semântica unificada
        # com pdf.html e portal_cliente.html.
        record(
            "REV4: paginado SEM cláusulas NÃO contém '25% de entrada' (sem fallback hardcoded)",
            "25% de entrada na assinatura do contrato" not in body_legacy,
            evidence="hardcoded payment fallback corretamente AUSENTE",
        )
        record(
            "REV4: paginado SEM cláusulas NÃO contém 'limita-se a reparar'",
            "limita-se a reparar ou substituir os itens defeituosos" not in body_legacy,
            evidence="hardcoded warranty fallback corretamente AUSENTE",
        )
        record(
            "REV4: paginado SEM cláusulas NÃO contém 'normas técnicas brasileiras'",
            "Execução conforme normas técnicas brasileiras" not in body_legacy,
            evidence="hardcoded NBR fallback corretamente AUSENTE",
        )
        # Sanidade: seções derivadas dos campos numéricos (entrega, validade)
        # continuam aparecendo — não são cláusulas.
        record(
            "REV4: paginado preserva 'CONDIÇÕES DE ENTREGA' (numérico, não-cláusula)",
            "CONDIÇÕES DE ENTREGA" in body_legacy,
            evidence="seção numérica (prazo) presente",
        )
        record(
            "REV4: paginado preserva 'VALIDADE DA PROPOSTA' (numérico, não-cláusula)",
            "VALIDADE DA PROPOSTA" in body_legacy,
            evidence="seção numérica (validade) presente",
        )

        # 14) REV4 — Removendo uma cláusula via UI, ela some dos 3 renderers
        #     (pdf padrão, pdf paginado e portal cliente). Esta é a
        #     verificação explícita pedida pelo code review.
        prop_remove = Proposta(
            admin_id=admin.id,
            numero=f"PROP-RM-{RUN_TAG}",
            titulo=f"Proposta Remoção {RUN_TAG}",
            cliente_nome=cli_legacy.nome,
            cliente_email=cli_legacy.email,
            cliente_id=cli_legacy.id,
            status="enviada",
            valor_total=Decimal("100.00"),
            token_cliente=f"tok-rm-{RUN_TAG.lower()}",
        )
        db.session.add(prop_remove)
        db.session.flush()
        db.session.execute(
            _sql_text(
                "UPDATE propostas_comerciais "
                "SET condicoes_pagamento=NULL, garantias=NULL, consideracoes_gerais=NULL "
                "WHERE id=:id"
            ),
            {"id": prop_remove.id},
        )
        marker_pgto = f"PAGTO-CUSTOM-{RUN_TAG}"
        db.session.add(PropostaClausula(
            proposta_id=prop_remove.id,
            titulo="Condições de Pagamento",
            texto=marker_pgto,
            ordem=1,
        ))
        db.session.commit()
        # Antes da remoção: marker presente nos 3 renderers
        body_pdf_a = client.get(
            f"/propostas/{prop_remove.id}/pdf?formato=estruturas_vale"
        ).get_data(as_text=True)
        body_pdf_b = client.get(
            f"/propostas/{prop_remove.id}/pdf?formato=padrao"
        ).get_data(as_text=True)
        body_portal_a = client.get(
            f"/propostas/cliente/{prop_remove.token_cliente}"
        ).get_data(as_text=True)
        record(
            "REV4 antes-remoção: marker 'Condições de Pagamento' presente no PDF paginado",
            marker_pgto in body_pdf_a,
            evidence="cláusula visível no paginado",
        )
        record(
            "REV4 antes-remoção: marker presente no PDF padrão",
            marker_pgto in body_pdf_b,
            evidence="cláusula visível no padrão",
        )
        record(
            "REV4 antes-remoção: marker presente no portal do cliente",
            marker_pgto in body_portal_a,
            evidence="cláusula visível no portal",
        )
        # Remove a cláusula via UI usando a sentinela (POST sem cláusulas)
        r_rm = client.post(
            f"/propostas/editar/{prop_remove.id}",
            data={
                "numero": prop_remove.numero,
                "titulo": prop_remove.titulo,
                "descricao": "",
                "cliente_nome": prop_remove.cliente_nome,
                "cliente_email": prop_remove.cliente_email or "",
                "cliente_telefone": "",
                "cliente_endereco": "",
                "prazo_entrega_dias": "90",
                "percentual_nota_fiscal": "13.5",
                "clausulas_payload_present": "1",
            },
            follow_redirects=False,
        )
        record(
            "REV4 POST remoção via UI redireciona",
            r_rm.status_code in (200, 302),
            evidence=f"status={r_rm.status_code}",
        )
        n_apos = PropostaClausula.query.filter_by(
            proposta_id=prop_remove.id
        ).count()
        record(
            "REV4 cláusula removida do banco após POST com sentinela",
            n_apos == 0,
            evidence=f"clausulas={n_apos}",
        )
        # Depois da remoção: marker AUSENTE em TODOS os 3 renderers
        body_pdf_a2 = client.get(
            f"/propostas/{prop_remove.id}/pdf?formato=estruturas_vale"
        ).get_data(as_text=True)
        body_pdf_b2 = client.get(
            f"/propostas/{prop_remove.id}/pdf?formato=padrao"
        ).get_data(as_text=True)
        body_portal_a2 = client.get(
            f"/propostas/cliente/{prop_remove.token_cliente}"
        ).get_data(as_text=True)
        record(
            "REV4 após-remoção: marker AUSENTE no PDF paginado",
            marker_pgto not in body_pdf_a2,
            evidence="cláusula corretamente sumiu do paginado",
        )
        record(
            "REV4 após-remoção: marker AUSENTE no PDF padrão",
            marker_pgto not in body_pdf_b2,
            evidence="cláusula corretamente sumiu do padrão",
        )
        record(
            "REV4 após-remoção: marker AUSENTE no portal do cliente",
            marker_pgto not in body_portal_a2,
            evidence="cláusula corretamente sumiu do portal",
        )

        # 15) REV4 — Selector de PropostaTemplate aparece em GET /propostas/nova.
        #     Garante que a UI de criação de proposta expõe os templates do admin
        #     (corrige o gap em que o template_id era aceito por POST mas não havia
        #     forma de selecioná-lo na interface).
        # Cria um template marker para garantir que será listado.
        tpl_marker_nome = f"TplSelector-{RUN_TAG}"
        tpl_marker = PropostaTemplate(
            admin_id=admin.id,
            nome=tpl_marker_nome,
            categoria="Estrutura Metálica",
            ativo=True,
        )
        db.session.add(tpl_marker)
        db.session.commit()
        r_nova = client.get("/propostas/nova")
        record(
            "REV4 GET /propostas/nova retorna 200",
            r_nova.status_code == 200,
            evidence=f"status={r_nova.status_code}",
        )
        body_nova = r_nova.get_data(as_text=True)
        record(
            "REV4 form de criação contém <select name=\"template_id\">",
            'name="template_id"' in body_nova,
            evidence="template_id selector present in nova_proposta.html",
        )
        record(
            f"REV4 selector lista template recém-criado ({tpl_marker_nome})",
            tpl_marker_nome in body_nova,
            evidence="admin's PropostaTemplate listed in selector",
        )
        record(
            "REV4 selector inclui opção vazia (sem template = comportamento legado)",
            'value=""' in body_nova and "Sem template" in body_nova,
            evidence="empty option present (preserves legacy behavior)",
        )

        # 16) REV4 — Sentinela `clausulas_payload_present` permite remover TODAS
        #     as cláusulas via UI. POST /propostas/<id>/atualizar com sentinela=1
        #     e SEM nenhuma linha clausula_titulo[]/clausula_texto[] zera a tabela.
        prop_del = Proposta(
            admin_id=admin.id,
            numero=f"PROP-DEL-{RUN_TAG}",
            titulo=f"Proposta Delete-All {RUN_TAG}",
            cliente_nome=cli_legacy.nome,
            cliente_email=cli_legacy.email,
            cliente_id=cli_legacy.id,
            status="rascunho",
            valor_total=Decimal("100.00"),
        )
        db.session.add(prop_del)
        db.session.flush()
        # Pré-popula 3 cláusulas
        for _i, _t in enumerate(["A", "B", "C"], start=1):
            db.session.add(PropostaClausula(
                proposta_id=prop_del.id,
                titulo=f"Cláusula {_t}",
                texto=f"Texto {_t}",
                ordem=_i,
            ))
        db.session.commit()
        antes = PropostaClausula.query.filter_by(proposta_id=prop_del.id).count()
        record(
            "REV4 pré-condição: Proposta tem 3 cláusulas antes do delete",
            antes == 3,
            evidence=f"clausulas={antes}",
        )
        # Submete o form com sentinela mas sem nenhum clausula_titulo[]
        r_del = client.post(
            f"/propostas/editar/{prop_del.id}",
            data={
                "numero": prop_del.numero,
                "titulo": prop_del.titulo,
                "descricao": "",
                "cliente_nome": prop_del.cliente_nome,
                "cliente_email": prop_del.cliente_email or "",
                "cliente_telefone": "",
                "cliente_endereco": "",
                "prazo_entrega_dias": "90",
                "percentual_nota_fiscal": "13.5",
                "clausulas_payload_present": "1",
            },
            follow_redirects=False,
        )
        record(
            "REV4 POST atualizar com sentinela e sem cláusulas redireciona",
            r_del.status_code in (200, 302),
            evidence=f"status={r_del.status_code}",
        )
        depois = PropostaClausula.query.filter_by(proposta_id=prop_del.id).count()
        record(
            "REV4 sentinela permite remover TODAS as cláusulas via UI",
            depois == 0,
            evidence=f"clausulas após delete={depois} (esperado 0)",
        )

        # 17) REV4 — Sentinela equivalente para PropostaTemplate.
        tpl_del = PropostaTemplate(
            admin_id=admin.id,
            nome=f"TplDel-{RUN_TAG}",
            categoria="Estrutura Metálica",
            ativo=True,
        )
        db.session.add(tpl_del)
        db.session.flush()
        for _i, _t in enumerate(["X", "Y"], start=1):
            db.session.add(PropostaTemplateClausula(
                proposta_template_id=tpl_del.id,
                admin_id=admin.id,
                titulo=f"Tpl Cl {_t}",
                texto=f"Tpl Texto {_t}",
                ordem=_i,
            ))
        db.session.commit()
        antes_t = PropostaTemplateClausula.query.filter_by(
            proposta_template_id=tpl_del.id
        ).count()
        record(
            "REV4 pré-condição: PropostaTemplate tem 2 cláusulas antes",
            antes_t == 2,
            evidence=f"clausulas={antes_t}",
        )
        r_tdel = client.post(
            f"/propostas/templates/{tpl_del.id}/atualizar",
            data={
                "nome": tpl_del.nome,
                "categoria": tpl_del.categoria,
                "descricao": "",
                "ativo": "1",
                "clausulas_payload_present": "1",
            },
            follow_redirects=False,
        )
        record(
            "REV4 POST template atualizar com sentinela redireciona",
            r_tdel.status_code in (200, 302),
            evidence=f"status={r_tdel.status_code}",
        )
        depois_t = PropostaTemplateClausula.query.filter_by(
            proposta_template_id=tpl_del.id
        ).count()
        record(
            "REV4 sentinela permite remover TODAS as cláusulas do TEMPLATE",
            depois_t == 0,
            evidence=f"clausulas após delete={depois_t} (esperado 0)",
        )

        # 18) REV5 — Proposta criada de template MIGRADO contendo cláusulas
        #     "Condições de Entrega" e "Validade da Proposta" (que vieram
        #     do backfill da migration 134) NÃO deve duplicá-las como
        #     cláusulas — essas seções são derivadas dos campos numéricos
        #     prazo_entrega_dias/validade_dias e renderizadas separadamente
        #     no PDF paginado. _copiar_clausulas_template_para_proposta()
        #     pula esses 2 títulos.
        tpl_migrado = PropostaTemplate(
            admin_id=admin.id,
            nome=f"TplMigrado {RUN_TAG}",
            categoria="ESTRUTURAS_VALE",
            ativo=True,
        )
        db.session.add(tpl_migrado)
        db.session.flush()
        # Simula um template backfilled pela migration 134 com as 6 cláusulas.
        # REV6: incluímos VARIANTES nos títulos de entrega/validade
        # (UPPERCASE + dois-pontos trailing) para validar que o normalizador
        # _normalizar_titulo_clausula é tolerante a acentos/caixa/pontuação.
        for ordem, titulo, marker in [
            (1, "Objeto", f"OBJ-{RUN_TAG}"),
            (2, "Condições de Pagamento", f"PAG-{RUN_TAG}"),
            (3, "CONDIÇÕES DE ENTREGA", f"ENT-{RUN_TAG}"),
            (4, "Garantias", f"GAR-{RUN_TAG}"),
            (5, "Considerações Gerais", f"CONS-{RUN_TAG}"),
            (6, "Validade da Proposta:", f"VAL-{RUN_TAG}"),
        ]:
            db.session.add(PropostaTemplateClausula(
                proposta_template_id=tpl_migrado.id,
                admin_id=admin.id,
                titulo=titulo,
                texto=marker,
                ordem=ordem,
            ))
        db.session.commit()
        # Cria proposta a partir desse template via UI (mesmo padrão do step 11)
        prop_mig_titulo = f"Proposta de Template Migrado {RUN_TAG}"
        r_mig = client.post(
            "/propostas/criar",
            data={
                "cliente_nome": f"Cliente Migrado {RUN_TAG}",
                "cliente_email": f"cli_mig_{RUN_TAG.lower()}@e2e.local",
                "cliente_telefone": "11988880000",
                "cliente_endereco": "Rua Mig, 1",
                "titulo": prop_mig_titulo,
                "descricao": "criada via template_id (entrega/validade)",
                "prazo_entrega_dias": "90",
                "validade_dias": "7",
                "percentual_nota_fiscal": "13.5",
                "template_id": str(tpl_migrado.id),
            },
            follow_redirects=False,
        )
        record(
            "REV5 POST /propostas/criar com template migrado redireciona",
            r_mig.status_code in (302, 303),
            evidence=f"status={r_mig.status_code}",
        )
        prop_mig = Proposta.query.filter_by(
            admin_id=admin.id,
            titulo=prop_mig_titulo,
        ).first()
        record(
            "REV5 proposta criada do template migrado existe",
            prop_mig is not None,
            evidence=f"id={prop_mig.id if prop_mig else 'None'}",
        )
        if prop_mig:
            titulos_copiados = [c.titulo for c in prop_mig.clausulas]
            record(
                "REV5 entrega/validade NÃO duplicadas como cláusulas",
                "Condições de Entrega" not in titulos_copiados
                and "Validade da Proposta" not in titulos_copiados,
                evidence=f"titulos copiados={titulos_copiados}",
            )
            record(
                "REV5 demais cláusulas (Objeto/Pagamento/Garantias/Considerações) preservadas",
                set(titulos_copiados) == {
                    "Objeto", "Condições de Pagamento", "Garantias", "Considerações Gerais"
                },
                evidence=f"titulos copiados={titulos_copiados}",
            )
            # Renderiza paginado e confirma seções numéricas presentes,
            # mas SEM duplicação dos textos das cláusulas entrega/validade.
            body_mig = client.get(
                f"/propostas/{prop_mig.id}/pdf?formato=estruturas_vale"
            ).get_data(as_text=True)
            record(
                "REV5 paginado SEM duplicação: marker ENT- ausente (skipped)",
                f"ENT-{RUN_TAG}" not in body_mig,
                evidence="texto da cláusula 'Condições de Entrega' do template NÃO aparece",
            )
            record(
                "REV5 paginado SEM duplicação: marker VAL- ausente (skipped)",
                f"VAL-{RUN_TAG}" not in body_mig,
                evidence="texto da cláusula 'Validade da Proposta' do template NÃO aparece",
            )
            record(
                "REV5 paginado preserva seção numérica 'CONDIÇÕES DE ENTREGA'",
                "CONDIÇÕES DE ENTREGA" in body_mig,
                evidence="seção numérica derivada de prazo_entrega_dias presente",
            )
            record(
                "REV5 paginado preserva seção numérica 'VALIDADE DA PROPOSTA'",
                "VALIDADE DA PROPOSTA" in body_mig,
                evidence="seção numérica derivada de validade_dias presente",
            )

    summary = write_report()
    print()
    print(f"=== RESULTADO {RUN_TAG} ===")
    print(f"   Passed: {summary['passed']}/{summary['total']}")
    print(f"   Failed: {summary['failed']}")
    print(f"   Relatório: {REPORT_PATH}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
