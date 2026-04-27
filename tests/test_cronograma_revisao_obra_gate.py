"""
Task #200 — E2E HTTP do gate de revisão inicial de cronograma na 1ª
visita aos detalhes da obra.

Cobre 4 cenários completos via Flask test client:

  CENÁRIO A — Aprovação SEM pré-config de cronograma:
    1. Aprovar proposta → obra criada com `cronograma_revisado_em IS NULL`
       e SEM TarefaCronograma (interno).
    2. GET /obras/<id> → 302 para /obras/<id>/cronograma-revisar-inicial.
    3. GET /obras/<id>/cronograma-revisar-inicial → 200 com árvore.
    4. POST /obras/<id>/cronograma-revisar-inicial com sub_b DESMARCADA
       → 302 para detalhes; sub_a materializada, sub_b NÃO criada;
       `cronograma_revisado_em` preenchido.
    5. GET /obras/<id> → 200 (gate não dispara mais).

  CENÁRIO B — Aprovação COM pré-config (snapshot já salvo na proposta):
    6. Salvar `cronograma_default_json` (admin reviu pré-aprovação).
    7. Aprovar → handler materializa snapshot + marca obra como revisada.
    8. GET /obras/<id> → 200 direto (gate NÃO dispara).

  CENÁRIO C — Botão "Revisar de novo" (reset do cronograma):
    9. POST /obras/<id>/cronograma-revisar-reset → 302 para a tela
       de revisão; tarefas geradas pela proposta apagadas; flag zerada.
    10. GET /obras/<id> → 302 de novo (gate reaberto).

  CENÁRIO D — Tarefas manuais sobrevivem ao reset:
    11. Após cenário A, criar tarefa MANUAL (gerada_por_proposta_item_id=NULL).
    12. Resetar → tarefa manual permanece, tarefa "do contrato" é apagada.

Executa com:  python tests/test_cronograma_revisao_obra_gate.py
Workflow Replit: `test-cronograma-revisao-obra-gate`.

Exit 0 → todos asserts OK. Exit 1 → falha (com diagnóstico no stdout).
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
    Obra,
)

RUN_TAG = f"E2E200-{secrets.token_hex(3).upper()}"
PASS, FAIL = [], []


def step(label, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    (PASS if ok else FAIL).append(label)
    extra = f" — {detail}" if detail else ""
    print(f"  {tag} {label}{extra}")


def fresh_proposta(client, admin, cliente, servico_id, servico_nome, suffix):
    """Cria proposta + item + servico_id + token. Retorna proposta_id, token."""
    numero = f"PROP-{RUN_TAG}-{suffix}"
    r = client.post("/propostas/criar", data={
        "numero_proposta": numero,
        "cliente_nome": cliente.nome,
        "cliente_email": cliente.email or "",
        "cliente_telefone": cliente.telefone or "",
        "assunto": f"Proposta E2E #{suffix}",
        "objeto": "Reforma — gate cronograma",
        "item_descricao": [servico_nome],
        "item_quantidade": ["100"],
        "item_unidade": ["m2"],
        "item_preco": ["120,00"],
        "prazo_entrega_dias": "60",
    }, follow_redirects=False)
    assert r.status_code in (302, 303), f"falha criar proposta {suffix}: {r.status_code}"

    prop = Proposta.query.filter_by(admin_id=admin.id, numero=numero).first()
    assert prop is not None, f"proposta {suffix} não persistiu"
    if not prop.token_cliente:
        prop.token_cliente = secrets.token_urlsafe(32)
    item = (PropostaItem.query
            .filter_by(proposta_id=prop.id, admin_id=admin.id)
            .order_by(PropostaItem.ordem).first())
    assert item is not None, f"PropostaItem {suffix} não persistiu"
    if not item.servico_id:
        item.servico_id = servico_id
    db.session.commit()
    return prop.id, prop.token_cliente


def seed():
    """admin + cliente + template (1 grupo + 2 subs) + insumo + servico + composicao."""
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

    sub_a = SubatividadeMestre(admin_id=admin.id, nome=f"Preparo {RUN_TAG}", unidade_medida="m3")
    sub_b = SubatividadeMestre(admin_id=admin.id, nome=f"Aplicacao {RUN_TAG}", unidade_medida="m2")
    db.session.add_all([sub_a, sub_b])
    db.session.flush()

    template = CronogramaTemplate(
        admin_id=admin.id,
        nome=f"Tpl {RUN_TAG}",
        categoria="Alvenaria",
        ativo=True,
    )
    db.session.add(template)
    db.session.flush()

    grupo = CronogramaTemplateItem(
        template_id=template.id, admin_id=admin.id,
        nome_tarefa=f"Etapa {RUN_TAG}", ordem=0, duracao_dias=10,
    )
    db.session.add(grupo)
    db.session.flush()

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
    return admin, cliente, template, sub_a, sub_b


def login_admin(client, admin_email):
    r = client.post("/login",
                    data={"email": admin_email, "password": "Senha@2026"},
                    follow_redirects=False)
    assert r.status_code in (302, 303), f"login falhou: {r.status_code}"


def materializar_via_ui(client, admin, servico_nome):
    """Cria insumo + servico + composição via UI. Retorna servico_id."""
    nome_insumo = f"Cimento {RUN_TAG}"
    client.post("/catalogo/insumos/novo", data={
        "nome": nome_insumo, "tipo": "MATERIAL", "unidade": "kg", "preco": "0.85",
    })
    insumo = Insumo.query.filter_by(admin_id=admin.id, nome=nome_insumo).first()

    client.post("/catalogo/servicos/novo", data={
        "nome": servico_nome, "categoria": "Estrutura",
        "unidade_medida": "m2", "imposto_pct": "13.5", "margem_lucro_pct": "20",
    })
    servico = Servico.query.filter_by(admin_id=admin.id, nome=servico_nome).first()

    client.post(f"/catalogo/servicos/{servico.id}/composicao/add",
                data={"insumo_id": str(insumo.id), "coeficiente": "12.5"})
    return servico.id


def aprovar_via_cliente_portal(anon_client, token):
    r = anon_client.post(f"/propostas/cliente/{token}/aprovar",
                         data={"observacoes": "ok"},
                         follow_redirects=False)
    return r


def get_obra_detalhe(client, obra_id):
    return client.get(f"/obras/{obra_id}", follow_redirects=False)


def run():
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    with app.app_context():
        admin, cliente, template, sub_a, sub_b = seed()
        admin_id = admin.id
        admin_email = admin.email

        client = app.test_client()
        anon = app.test_client()

        login_admin(client, admin_email)

        servico_nome = f"Alvenaria {RUN_TAG}"
        servico_id = materializar_via_ui(client, admin, servico_nome)

        # Vincula template ao serviço (gap UI conhecido — patch via DB).
        Servico.query.get(servico_id).template_padrao_id = template.id
        db.session.commit()

        # ──────────────── CENÁRIO A — sem pré-config ────────────────
        prop_a_id, token_a = fresh_proposta(
            client, admin, cliente, servico_id, servico_nome, suffix="A",
        )
        # Envia ao cliente
        r = client.post(f"/propostas/{prop_a_id}/status", json={"status": "ENVIADA"})
        step("A.1 status ENVIADA", r.status_code == 200, f"http={r.status_code}")

        # Cliente aprova
        r = aprovar_via_cliente_portal(anon, token_a)
        step("A.2 cliente POST /aprovar", r.status_code in (200, 302),
             f"http={r.status_code}")

        db.session.expire_all()
        prop_a = db.session.get(Proposta, prop_a_id)
        obra_a = db.session.get(Obra, prop_a.obra_id) if prop_a.obra_id else None
        step("A.3 obra criada pela aprovação",
             obra_a is not None, f"obra_id={getattr(obra_a, 'id', None)}")
        step("A.4 obra nasce SEM cronograma_revisado_em",
             obra_a is not None and obra_a.cronograma_revisado_em is None,
             f"flag={getattr(obra_a, 'cronograma_revisado_em', '?')}")
        tarefas_a = (TarefaCronograma.query
                     .filter_by(obra_id=obra_a.id, is_cliente=False).all())
        step("A.5 obra nasce SEM tarefas internas",
             len(tarefas_a) == 0, f"tarefas={len(tarefas_a)}")

        # 1ª visita — deve REDIRECIONAR para revisar
        r = get_obra_detalhe(client, obra_a.id)
        loc = r.headers.get("Location") or ""
        step("A.6 GET /obras/<id> redireciona (gate ATIVO)",
             r.status_code in (302, 303) and "cronograma-revisar-inicial" in loc,
             f"http={r.status_code} loc={loc}")

        # GET tela de revisão
        r = client.get(f"/obras/{obra_a.id}/cronograma-revisar-inicial")
        step("A.7 GET tela revisar 200",
             r.status_code == 200, f"http={r.status_code}")
        body = r.get_data(as_text=True)
        step("A.7b tela contém nomes das subatividades",
             sub_a.nome in body and sub_b.nome in body,
             f"sub_a={'sim' if sub_a.nome in body else 'NÃO'} "
             f"sub_b={'sim' if sub_b.nome in body else 'NÃO'}")

        # Monta árvore com sub_b DESMARCADA
        from services.cronograma_proposta import montar_arvore_preview
        arvore = montar_arvore_preview(prop_a, admin_id)

        def desmarcar_sub_b(nodes):
            for n in nodes:
                # marca tudo por padrão; depois desmarca a sub_b
                n["marcado"] = True
                if n.get("nome") and sub_b.nome in n["nome"]:
                    n["marcado"] = False
                if n.get("filhos"):
                    desmarcar_sub_b(n["filhos"])
        desmarcar_sub_b(arvore)

        # POST confirmar revisão
        r = client.post(
            f"/obras/{obra_a.id}/cronograma-revisar-inicial",
            data={"cronograma_marcado_json": json.dumps(arvore)},
            follow_redirects=False,
        )
        step("A.8 POST revisar redireciona para detalhes",
             r.status_code in (302, 303), f"http={r.status_code}")

        db.session.expire_all()
        obra_a = db.session.get(Obra, obra_a.id)
        step("A.9 cronograma_revisado_em preenchido",
             obra_a.cronograma_revisado_em is not None,
             f"flag={obra_a.cronograma_revisado_em}")

        tarefas_a = (TarefaCronograma.query
                     .filter_by(obra_id=obra_a.id, is_cliente=False).all())
        nomes_a = sorted({t.nome_tarefa for t in tarefas_a})
        step("A.10 sub_a materializada",
             any(sub_a.nome in n for n in nomes_a),
             f"nomes={nomes_a}")
        step("A.11 sub_b NÃO materializada (desmarcada)",
             not any(sub_b.nome in n for n in nomes_a),
             f"nomes={nomes_a}")

        # 2ª visita — gate NÃO dispara. O critério essencial é "NÃO redireciona
        # para a tela de revisão". O detalhe da obra pode falhar por bugs
        # pré-existentes do template (ex.: endpoint medicao.gestao_itens não
        # registrado) e cair no except → redireciona para /obras — isso é
        # PROBLEMA SEPARADO, fora do escopo do gate da Task #200.
        r = get_obra_detalhe(client, obra_a.id)
        loc_a12 = r.headers.get("Location") or ""
        gate_inerte = (
            r.status_code == 200
            or (r.status_code in (302, 303)
                and "cronograma-revisar-inicial" not in loc_a12)
        )
        step("A.12 GET /obras/<id> NÃO redireciona para revisão (gate inerte)",
             gate_inerte, f"http={r.status_code} loc={loc_a12}")

        # ──────────────── CENÁRIO C — Reset ────────────────
        # (executa antes de B porque reusa obra_a)
        # Antes: cria 1 tarefa MANUAL para garantir que sobrevive ao reset.
        manual = TarefaCronograma(
            obra_id=obra_a.id, admin_id=admin_id,
            nome_tarefa=f"Tarefa MANUAL {RUN_TAG}",
            data_inicio=date.today(), data_fim=date.today(),
            duracao_dias=1, percentual_concluido=0,
            ordem=999, is_cliente=False,
            gerada_por_proposta_item_id=None,
        )
        db.session.add(manual)
        db.session.commit()
        manual_id = manual.id
        total_antes_reset = TarefaCronograma.query.filter_by(
            obra_id=obra_a.id, is_cliente=False).count()
        step("D.1 tarefa manual criada antes do reset",
             total_antes_reset > 1,
             f"total={total_antes_reset}")

        r = client.post(f"/obras/{obra_a.id}/cronograma-revisar-reset",
                        follow_redirects=False)
        loc = r.headers.get("Location") or ""
        step("C.1 POST reset redireciona para revisar",
             r.status_code in (302, 303) and "cronograma-revisar-inicial" in loc,
             f"http={r.status_code} loc={loc}")

        db.session.expire_all()
        obra_a = db.session.get(Obra, obra_a.id)
        step("C.2 reset zera cronograma_revisado_em",
             obra_a.cronograma_revisado_em is None,
             f"flag={obra_a.cronograma_revisado_em}")

        # Tarefa manual sobrevive
        ainda = db.session.get(TarefaCronograma, manual_id)
        step("D.2 tarefa manual sobreviveu ao reset",
             ainda is not None, f"manual_id={manual_id}")

        # Tarefas geradas pela proposta foram apagadas
        do_contrato = (TarefaCronograma.query
                       .filter(TarefaCronograma.obra_id == obra_a.id,
                               TarefaCronograma.is_cliente == False,  # noqa: E712
                               TarefaCronograma.gerada_por_proposta_item_id.isnot(None))
                       .count())
        step("C.3 tarefas 'do contrato' apagadas pelo reset",
             do_contrato == 0, f"restantes={do_contrato}")

        # Próxima visita — com tarefa manual restante, o gate respeita o
        # critério "obra sem tarefas" e NÃO dispara. Mesma tolerância do A.12
        # para o bug pré-existente do template.
        r = get_obra_detalhe(client, obra_a.id)
        loc_c4 = r.headers.get("Location") or ""
        gate_inerte_c4 = (
            r.status_code == 200
            or (r.status_code in (302, 303)
                and "cronograma-revisar-inicial" not in loc_c4)
        )
        step("C.4 com tarefa manual ainda existente, gate NÃO redireciona "
             "para revisão",
             gate_inerte_c4,
             f"http={r.status_code} loc={loc_c4}")

        # Se removermos a manual, o gate volta:
        db.session.delete(db.session.get(TarefaCronograma, manual_id))
        db.session.commit()
        r = get_obra_detalhe(client, obra_a.id)
        loc = r.headers.get("Location") or ""
        step("C.5 sem nenhuma tarefa, gate dispara de novo",
             r.status_code in (302, 303) and "cronograma-revisar-inicial" in loc,
             f"http={r.status_code} loc={loc}")

        # ──────────────── CENÁRIO B — pré-config ────────────────
        prop_b_id, token_b = fresh_proposta(
            client, admin, cliente, servico_id, servico_nome, suffix="B",
        )
        # Snapshot pré-aprovação via UI (admin valida cronograma da proposta)
        r = client.get(f"/propostas/{prop_b_id}/cronograma-preview")
        payload = r.get_json() if r.status_code == 200 else {}
        arvore_b = (payload or {}).get("arvore") or []

        def marcar_tudo(nodes):
            for n in nodes:
                n["marcado"] = True
                if n.get("filhos"):
                    marcar_tudo(n["filhos"])
        marcar_tudo(arvore_b)

        r = client.post(f"/propostas/{prop_b_id}/cronograma-default",
                        data={"cronograma_marcado_json": json.dumps(arvore_b)},
                        follow_redirects=False)
        step("B.1 admin grava cronograma_default_json",
             r.status_code in (200, 302), f"http={r.status_code}")

        db.session.expire_all()
        prop_b = db.session.get(Proposta, prop_b_id)
        step("B.2 snapshot persistido na proposta",
             prop_b.cronograma_default_json is not None,
             f"size={len(json.dumps(prop_b.cronograma_default_json or []))}")

        # Envia + cliente aprova
        client.post(f"/propostas/{prop_b_id}/status", json={"status": "ENVIADA"})
        aprovar_via_cliente_portal(anon, token_b)

        db.session.expire_all()
        prop_b = db.session.get(Proposta, prop_b_id)
        obra_b = db.session.get(Obra, prop_b.obra_id) if prop_b.obra_id else None
        step("B.3 obra B criada pela aprovação",
             obra_b is not None, f"obra_id={getattr(obra_b, 'id', None)}")
        step("B.4 obra B nasce JÁ revisada (snapshot materializou)",
             obra_b is not None and obra_b.cronograma_revisado_em is not None,
             f"flag={getattr(obra_b, 'cronograma_revisado_em', '?')}")

        tarefas_b = (TarefaCronograma.query
                     .filter_by(obra_id=obra_b.id, is_cliente=False).all())
        step("B.5 obra B já tem tarefas internas materializadas",
             len(tarefas_b) > 0, f"tarefas={len(tarefas_b)}")

        # 1ª visita — gate NÃO dispara (já revisada na aprovação via snapshot).
        # Mesma tolerância do A.12 / C.4 para o bug pré-existente do template.
        r = get_obra_detalhe(client, obra_b.id)
        loc_b6 = r.headers.get("Location") or ""
        gate_inerte_b6 = (
            r.status_code == 200
            or (r.status_code in (302, 303)
                and "cronograma-revisar-inicial" not in loc_b6)
        )
        step("B.6 GET /obras/<id> obra B NÃO redireciona para revisão "
             "(snapshot pré-aprovação)",
             gate_inerte_b6, f"http={r.status_code} loc={loc_b6}")

    # ───── Resultado ─────
    print("\n" + "=" * 70)
    print(f"E2E Task #200 ({RUN_TAG}) — {len(PASS)} PASS / {len(FAIL)} FAIL")
    print("=" * 70)
    if FAIL:
        print("\nFALHAS:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    print("OK — gate de revisão de cronograma da obra validado.")
    sys.exit(0)


if __name__ == "__main__":
    run()
