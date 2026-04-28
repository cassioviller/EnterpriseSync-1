"""
Task #213 — guard de regressão: o JS dos templates de propostas precisa
estar dentro de `{% block scripts %}` (único bloco renderizado por
`base_completo.html`). Antes da Task #213, esses templates declaravam
o JS em `{% block extra_js %}`, que não existe na base — então o JS
nunca chegava ao browser e o admin perdia tudo o que editava na
revisão de cronograma.

O teste cobre 3 templates afetados + executa os 2 fluxos críticos de
`/propostas/<id>/cronograma-revisar` ponta-a-ponta via HTTP:

  CENÁRIO A — guard estático nos 3 templates:
    GET /propostas/<id>/cronograma-revisar
    GET /propostas/editar/<id>
    GET /propostas/<id>          (visualizar)
    Cada resposta DEVE conter os marcadores JS específicos do template.
    Se o `block scripts` voltar a ser `extra_js`, esses marcadores
    desaparecem do HTML e o teste falha imediatamente.

  CENÁRIO B — POST /propostas/<id>/cronograma-default:
    Submete a árvore (como o JS faria) e confirma snapshot persistido
    em `propostas_comerciais.cronograma_default_json`.

  CENÁRIO C — POST /propostas/<id>/aprovar:
    Submete a árvore com todas as folhas marcadas e confirma:
      - status = APROVADA
      - obra_id criado
      - TarefaCronograma materializadas (>0)

Executa com:  python tests/test_propostas_block_scripts_213.py
Exit 0 → todos asserts OK. Exit 1 → falha (com diagnóstico no stdout).

Nota: o limite de 10 workflows do .replit já está ocupado, então este
teste não foi registrado como workflow. Quando algum dos workflows
existentes for retirado, registrar este como `test-propostas-block-scripts-213`
para entrar na rotação automática.
"""
import os
import sys
import json
import secrets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
)

RUN_TAG = f"E2E213-{secrets.token_hex(3).upper()}"
PASS, FAIL = [], []


def step(label, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    (PASS if ok else FAIL).append((label, detail))
    print(f"  {tag} {label}{(' — ' + detail) if detail else ''}")


def seed():
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
        categoria="Estrutura",
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

    insumo = Insumo(admin_id=admin.id, nome=f"Cimento {RUN_TAG}", tipo="MATERIAL",
                    unidade="kg")
    db.session.add(insumo)
    db.session.flush()

    servico = Servico(
        admin_id=admin.id,
        nome=f"Servico {RUN_TAG}",
        categoria="Estrutura",
        unidade_medida="m2",
        imposto_pct=13.5,
        margem_lucro_pct=20,
        template_padrao_id=template.id,
    )
    db.session.add(servico)
    db.session.flush()

    db.session.add(ComposicaoServico(
        admin_id=admin.id, servico_id=servico.id,
        insumo_id=insumo.id, coeficiente=12.5,
    ))
    db.session.commit()

    numero = f"PROP-{RUN_TAG}"
    prop = Proposta(
        admin_id=admin.id,
        numero=numero,
        cliente_nome=cliente.nome,
        cliente_email=cliente.email,
        cliente_telefone=cliente.telefone,
        cliente_id=cliente.id,
        titulo=f"Reforma {RUN_TAG}",
        status="RASCUNHO",
        valor_total=12000,
        prazo_entrega_dias=60,
    )
    db.session.add(prop)
    db.session.flush()

    item = PropostaItem(
        admin_id=admin.id,
        proposta_id=prop.id,
        item_numero=1,
        descricao=servico.nome,
        servico_id=servico.id,
        quantidade=100,
        unidade="m2",
        preco_unitario=120,
        subtotal=12000,
        ordem=0,
    )
    db.session.add(item)
    db.session.commit()

    return admin, prop, item, sub_a, sub_b


def login(client, email):
    r = client.post("/login",
                    data={"email": email, "password": "Senha@2026"},
                    follow_redirects=False)
    assert r.status_code in (302, 303), f"login falhou: {r.status_code}"


def assert_in_html(label, html, marker):
    """Marker DEVE aparecer no HTML; se não aparece, o block scripts foi quebrado."""
    ok = marker in html
    step(label, ok, "" if ok else f"marker ausente: {marker!r}")
    return ok


def cenario_a_guard_estatico(client, prop, item):
    """O template afetado pelo bug deve renderizar seu JS no HTML.

    Apenas `cronograma_revisar.html` é checado aqui porque é o único dos 3
    templates ajustados que está ligado a uma rota ativa (GET /propostas/
    <id>/cronograma-revisar). Os outros 2 (`proposta_form.html`,
    `visualizar_proposta.html`) foram normalizados preventivamente para
    `{% block scripts %}` no mesmo commit, mas são órfãos — nenhuma rota
    os renderiza hoje, então não há como o teste exercitá-los via HTTP.
    """
    print("\n[A] Guard estático — JS de cronograma_revisar.html no HTML renderizado")

    r = client.get(f"/propostas/{prop.id}/cronograma-revisar")
    step("A1 GET cronograma-revisar 200", r.status_code == 200, f"status={r.status_code}")
    h = r.get_data(as_text=True)
    assert_in_html("A1.a marker arvoreServer", h, "const arvoreServer")
    assert_in_html("A1.b marker _construirArvoreFinal", h, "_construirArvoreFinal")
    assert_in_html("A1.c marker btnSalvarPreconfig listener", h, "btnSalvarPreconfig")
    assert_in_html("A1.d hidden cronogramaJson presente", h, 'id="cronogramaJson"')


def build_arvore_payload(item, sub_a_nome, sub_b_nome, horas_a, marcado_b=True):
    """Monta o JSON que o JS produziria — 1 raiz (etapa) + 2 folhas."""
    return [{
        "proposta_item_id": item.id,
        "servico_id": item.servico_id,
        "servico_nome": "raiz",
        "template_id": None,
        "template_nome": None,
        "sem_template": False,
        "horas_totais_estimadas": horas_a + 24,
        "marcado": True,
        "filhos": [{
            "tipo": "grupo",
            "nome": "Etapa",
            "marcado": True,
            "filhos": [
                {
                    "tipo": "folha",
                    "subatividade_mestre_id": None,
                    "nome": sub_a_nome,
                    "marcado": True,
                    "horas_estimadas": float(horas_a),
                    "duracao_dias": 4,
                    "responsavel": "empresa",
                },
                {
                    "tipo": "folha",
                    "subatividade_mestre_id": None,
                    "nome": sub_b_nome,
                    "marcado": bool(marcado_b),
                    "horas_estimadas": 24.0,
                    "duracao_dias": 6,
                    "responsavel": "empresa",
                },
            ],
        }],
    }]


def cenario_b_preconfig(client, prop, item, sub_a, sub_b):
    print("\n[B] POST /cronograma-default — snapshot persistido sem aprovar")
    arvore = build_arvore_payload(item, sub_a.nome, sub_b.nome, horas_a=42, marcado_b=False)
    r = client.post(
        f"/propostas/{prop.id}/cronograma-default",
        data={"cronograma_marcado_json": json.dumps(arvore)},
        follow_redirects=False,
    )
    step("B1 POST cronograma-default 302", r.status_code in (302, 303), f"status={r.status_code}")

    db.session.expire_all()
    p = Proposta.query.get(prop.id)
    snap = p.cronograma_default_json
    step("B2 snapshot persistido", snap is not None and len(json.dumps(snap)) > 50,
         f"len={len(json.dumps(snap)) if snap else 0}")
    snap_str = json.dumps(snap) if snap else ""
    step("B3 snapshot contém horas_estimadas", "horas_estimadas" in snap_str)
    step("B4 snapshot contém '42'", "42" in snap_str)
    step("B5 status permanece RASCUNHO (não aprovou)", p.status == "RASCUNHO", f"status={p.status}")


def cenario_c_aprovar(client, prop, item, sub_a, sub_b):
    print("\n[C] POST /aprovar — submit constrói árvore, materializa tarefas")
    arvore = build_arvore_payload(item, sub_a.nome, sub_b.nome, horas_a=55, marcado_b=True)
    r = client.post(
        f"/propostas/aprovar/{prop.id}",
        data={"cronograma_marcado_json": json.dumps(arvore)},
        follow_redirects=False,
    )
    step("C1 POST aprovar 302", r.status_code in (302, 303), f"status={r.status_code}")

    db.session.expire_all()
    p = Proposta.query.get(prop.id)
    step("C2 status = APROVADA", (p.status or "").upper() == "APROVADA", f"status={p.status}")
    step("C3 obra_id criado", p.obra_id is not None, f"obra_id={p.obra_id}")

    n = TarefaCronograma.query.filter_by(obra_id=p.obra_id, is_cliente=False).count()
    step("C4 TarefaCronograma materializadas (>0)", n > 0, f"n_tarefas={n}")


def run():
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        admin, prop, item, sub_a, sub_b = seed()
        with app.test_client() as client:
            login(client, admin.email)
            cenario_a_guard_estatico(client, prop, item)
            cenario_b_preconfig(client, prop, item, sub_a, sub_b)
            cenario_c_aprovar(client, prop, item, sub_a, sub_b)

    print("\n" + "=" * 70)
    print(f"PASSED: {len(PASS)}  FAILED: {len(FAIL)}")
    print("=" * 70)
    if FAIL:
        for label, detail in FAIL:
            print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    run()
