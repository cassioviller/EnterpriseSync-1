"""Task #172 — testes para Obra.cliente_id (FK → cliente.id).

Cobertura:
  T1. Schema: a coluna obra.cliente_id existe (migração 132 aplicada).
  T2. Helper services.cliente_resolver:
       a. Cria Cliente quando ainda não existe.
       b. Reaproveita Cliente existente por e-mail.
       c. Reaproveita Cliente existente por nome (case-insensitive).
       d. Quando cliente_id é passado, retorna direto sem dedup.
       e. Sem nome e sem e-mail retorna None.
  T3. nova_obra (views.obras): criação manual via UI deve popular cliente_id.
  T4. event_manager.propagar_proposta_para_obra:
       a. Cria Obra com cliente_id resolvido a partir da Proposta.
       b. Edição posterior do Cliente reflete em Obra (via property efetivo).
       c. Obra legada sem cliente_id ainda mostra dados via fallback texto.

Padrão dos demais testes do projeto: script standalone (não pytest) com
PASS/FAIL impressos. Usa fixtures isoladas por timestamp.
"""
from __future__ import annotations

import os
import sys
import secrets
import logging
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

logging.basicConfig(level=logging.WARNING)

from app import app, db
from models import Usuario, Cliente, Obra, Proposta, TipoUsuario
from services.cliente_resolver import obter_ou_criar_cliente
from werkzeug.security import generate_password_hash


PASS = []
FAIL = []


def record(label, ok, evidence=''):
    (PASS if ok else FAIL).append((label, evidence))
    prefix = 'PASS' if ok else 'FAIL'
    print(f"  {prefix}: {label}{(' — ' + evidence) if evidence else ''}")


def make_admin():
    tag = datetime.utcnow().strftime('%H%M%S%f')
    u = Usuario(
        username=f't172_{tag}',
        email=f't172_{tag}@test.local',
        nome=f'Admin T172 {tag}',
        password_hash=generate_password_hash('senha123'),
        tipo_usuario=TipoUsuario.ADMIN,
    )
    db.session.add(u)
    db.session.flush()
    return u


def t1_schema_coluna_existe():
    res = db.session.execute(db.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='obra' AND column_name='cliente_id'"
    )).fetchone()
    record('T1 — coluna obra.cliente_id existe', res is not None,
           evidence=f"col={res[0] if res else None}")


def t2_resolver_helper():
    admin = make_admin()
    aid = admin.id
    tag = datetime.utcnow().strftime('%H%M%S%f')

    # 2a: cria
    c1 = obter_ou_criar_cliente(aid, nome=f'Cli T172a {tag}',
                                email=f'a_{tag}@cli.test', telefone='1199')
    record('T2a — cria Cliente quando inexistente',
           c1 is not None and c1.id is not None and c1.email.endswith('@cli.test'),
           evidence=f"id={getattr(c1, 'id', None)}")

    # 2b: dedup por e-mail (nome diferente)
    c2 = obter_ou_criar_cliente(aid, nome='Outro Nome', email=f'a_{tag}@cli.test')
    record('T2b — dedup por e-mail (case-insensitive)',
           c2 is not None and c2.id == c1.id,
           evidence=f"id={getattr(c2, 'id', None)} == {c1.id}")

    # 2c: política CONSERVADORA — chamando só por nome NÃO mescla com cliente
    # que já tem e-mail cadastrado (evita merge de homônimos).
    c3 = obter_ou_criar_cliente(aid, nome=f'Cli T172a {tag}'.upper())
    record('T2c — não mescla por nome quando cliente existente tem e-mail',
           c3 is not None and c3.id != c1.id,
           evidence=f"novo id={getattr(c3, 'id', None)} != c1.id={c1.id}")

    # 2d: cliente_id explícito vence
    c4 = obter_ou_criar_cliente(aid, nome='qualquer', email='qualquer@x.test',
                                cliente_id=c1.id)
    record('T2d — cliente_id explícito retorna direto',
           c4 is not None and c4.id == c1.id,
           evidence=f"id={getattr(c4, 'id', None)}")

    # 2e: sem dados → None
    c5 = obter_ou_criar_cliente(aid, nome='', email='')
    record('T2e — sem nome/email retorna None', c5 is None,
           evidence=f"resultado={c5}")

    # 2f: dedup por NOME único QUANDO ambos os lados estão sem e-mail.
    cliente_sem_email = Cliente(nome=f'SemEmail T172 {tag}', email=None,
                                admin_id=aid)
    db.session.add(cliente_sem_email)
    db.session.flush()
    c6 = obter_ou_criar_cliente(aid, nome=f'SemEmail T172 {tag}'.upper())
    record('T2f — dedup por nome único quando ambos sem e-mail',
           c6 is not None and c6.id == cliente_sem_email.id,
           evidence=f"id={getattr(c6, 'id', None)} == {cliente_sem_email.id}")

    # 2g: NÃO mescla homônimos quando há mais de um Cliente com mesmo nome.
    nome_homonimo = f'Homonimo T172 {tag}'
    h1 = Cliente(nome=nome_homonimo, email=None, admin_id=aid)
    h2 = Cliente(nome=nome_homonimo, email=None, admin_id=aid)
    db.session.add_all([h1, h2])
    db.session.flush()
    c7 = obter_ou_criar_cliente(aid, nome=nome_homonimo)
    record('T2g — homônimos sem e-mail → cria novo (não mescla)',
           c7 is not None and c7.id not in (h1.id, h2.id),
           evidence=f"novo id={getattr(c7, 'id', None)} ∉ {{{h1.id}, {h2.id}}}")

    # 2h: e-mail+nome estritos batem mesmo se houver outro homônimo.
    nome_estrito = f'Estrito T172 {tag}'
    email_estrito = f'estrito_{tag}@cli.test'
    s1 = Cliente(nome=nome_estrito, email=email_estrito, admin_id=aid)
    s2 = Cliente(nome=nome_estrito, email=None, admin_id=aid)
    db.session.add_all([s1, s2])
    db.session.flush()
    c8 = obter_ou_criar_cliente(aid, nome=nome_estrito.upper(),
                                email=email_estrito.upper())
    record('T2h — match estrito nome+email retorna o correto',
           c8 is not None and c8.id == s1.id,
           evidence=f"id={getattr(c8, 'id', None)} == {s1.id}")

    # 2i: tenant isolation — outro admin com mesmo e-mail não é encontrado.
    other_admin = make_admin()
    cross = obter_ou_criar_cliente(other_admin.id, nome=f'Cli T172a {tag}',
                                   email=f'a_{tag}@cli.test')
    record('T2i — isolamento por tenant (cria no outro admin)',
           cross is not None and cross.id != c1.id and cross.admin_id == other_admin.id,
           evidence=f"cross id={getattr(cross, 'id', None)} admin={getattr(cross, 'admin_id', None)}")


def t3_nova_obra_via_post():
    """Posta /obras/nova autenticado e confere que obra.cliente_id foi resolvido."""
    admin = make_admin()
    aid = admin.id
    tag = datetime.utcnow().strftime('%H%M%S%f')

    nome_cliente = f'Cliente Nova Obra {tag}'
    email_cliente = f'novaobra_{tag}@cli.test'

    # Faz a session do request reconhecer este admin (login_user via test_client)
    with app.test_client() as c:
        # Persistimos o admin antes de logar
        db.session.commit()

        with c.session_transaction() as sess:
            sess['_user_id'] = str(aid)
            sess['_fresh'] = True

        codigo = f'T172-{tag[-6:]}'
        resp = c.post('/obras/nova', data={
            'nome': f'Obra T172 {tag}',
            'codigo': codigo,
            'cliente_nome': nome_cliente,
            'cliente_email': email_cliente,
            'cliente_telefone': '11988887777',
            'data_inicio': datetime.utcnow().date().isoformat(),
            'orcamento': '0',
            'valor_contrato': '0',
            'area_total_m2': '0',
            'status': 'Em andamento',
        }, follow_redirects=False)
        record('T3a — POST /obras/nova retorna 302/200',
               resp.status_code in (200, 302),
               evidence=f"status={resp.status_code}")

    obra = Obra.query.filter_by(admin_id=aid, codigo=codigo).first()
    record('T3b — Obra persistida no DB',
           obra is not None,
           evidence=f"obra.id={getattr(obra, 'id', None)}")

    if obra:
        record('T3c — obra.cliente_id populado',
               obra.cliente_id is not None,
               evidence=f"cliente_id={obra.cliente_id}")

        if obra.cliente_id:
            cli = Cliente.query.get(obra.cliente_id)
            record('T3d — Cliente vinculado tem o nome esperado',
                   cli is not None and cli.nome == nome_cliente,
                   evidence=f"nome={getattr(cli, 'nome', None)!r}")

            # Helper property
            record('T3e — obra.cliente_nome_efetivo == cliente.nome',
                   obra.cliente_nome_efetivo == nome_cliente,
                   evidence=f"efetivo={obra.cliente_nome_efetivo!r}")


def t4_propagacao_proposta_aprovada():
    """Aprova proposta via handler do event_manager e confere FK + reflexo."""
    from event_manager import propagar_proposta_para_obra

    admin = make_admin()
    aid = admin.id
    tag = datetime.utcnow().strftime('%H%M%S%f')

    nome_cli = f'Cli Prop {tag}'
    email_cli = f'prop_{tag}@cli.test'

    proposta = Proposta(
        admin_id=aid,
        numero=f'T172-PROP-{tag}',
        titulo=f'Proposta T172 {tag}',
        cliente_nome=nome_cli,
        cliente_email=email_cli,
        cliente_telefone='11977776666',
        valor_total=Decimal('1000.00'),
        status='APROVADA',
    )
    db.session.add(proposta)
    db.session.flush()

    # Handler é responsabilidade da rota chamadora, então aqui chamamos direto.
    propagar_proposta_para_obra(
        {'proposta_id': proposta.id, 'cliente_nome': nome_cli,
         'valor_total': 1000.0, 'data_aprovacao': datetime.utcnow().isoformat()},
        aid,
    )
    db.session.flush()

    obra = Obra.query.filter_by(admin_id=aid, proposta_origem_id=proposta.id).first()
    record('T4a — Obra criada via handler proposta_aprovada',
           obra is not None,
           evidence=f"obra.id={getattr(obra, 'id', None)}")

    if obra:
        record('T4b — Obra criada com cliente_id populado',
               obra.cliente_id is not None,
               evidence=f"cliente_id={obra.cliente_id}")

        cliente = Cliente.query.get(obra.cliente_id) if obra.cliente_id else None
        if cliente:
            record('T4c — Cliente.email match',
                   cliente.email == email_cli,
                   evidence=f"email={cliente.email!r}")

            # T4d: editar Cliente reflete em obra via property efetivo
            novo_nome = f'Cli Prop EDITADO {tag}'
            cliente.nome = novo_nome
            db.session.flush()
            db.session.refresh(obra)
            record('T4d — alterar Cliente.nome reflete em obra.cliente_nome_efetivo',
                   obra.cliente_nome_efetivo == novo_nome,
                   evidence=f"efetivo={obra.cliente_nome_efetivo!r}")

            # T4e: 2ª aprovação não duplica Cliente nem cria nova Obra
            cliente_id_original = obra.cliente_id
            obra_id_original = obra.id
            propagar_proposta_para_obra(
                {'proposta_id': proposta.id, 'cliente_nome': nome_cli,
                 'valor_total': 1000.0, 'data_aprovacao': datetime.utcnow().isoformat()},
                aid,
            )
            db.session.flush()
            obras = Obra.query.filter_by(admin_id=aid, proposta_origem_id=proposta.id).all()
            clientes = Cliente.query.filter_by(admin_id=aid, email=email_cli).all()
            record('T4e — re-propagar é idempotente (1 obra + 1 cliente)',
                   len(obras) == 1 and len(clientes) == 1
                   and obras[0].id == obra_id_original
                   and obras[0].cliente_id == cliente_id_original,
                   evidence=f"obras={len(obras)} clientes={len(clientes)}")


def t5_fallback_obra_legada():
    """Obra sem cliente_id (legada) deve usar texto via property efetivo."""
    admin = make_admin()
    aid = admin.id
    tag = datetime.utcnow().strftime('%H%M%S%f')

    obra = Obra(
        nome=f'Obra Legada {tag}',
        codigo=f'LEG-{tag[-6:]}',
        cliente_nome=f'Texto Legado {tag}',
        cliente_email=f'legado_{tag}@x.test',
        cliente_telefone='11900000000',
        admin_id=aid,
        status='Em andamento',
        data_inicio=datetime.utcnow().date(),
    )
    db.session.add(obra)
    db.session.flush()

    record('T5a — Obra legada não tem cliente_id',
           obra.cliente_id is None,
           evidence=f"cliente_id={obra.cliente_id}")
    record('T5b — fallback cliente_nome_efetivo == cliente_nome',
           obra.cliente_nome_efetivo == f'Texto Legado {tag}',
           evidence=f"efetivo={obra.cliente_nome_efetivo!r}")
    record('T5c — fallback cliente_email_efetivo == cliente_email',
           obra.cliente_email_efetivo == f'legado_{tag}@x.test',
           evidence=f"efetivo={obra.cliente_email_efetivo!r}")
    record('T5d — fallback cliente_telefone_efetivo == cliente_telefone',
           obra.cliente_telefone_efetivo == '11900000000',
           evidence=f"efetivo={obra.cliente_telefone_efetivo!r}")


def main():
    print('=' * 80)
    print('TASK #172 — Obra.cliente_id FK + helpers + propagação')
    print('=' * 80)

    with app.app_context():
        try:
            t1_schema_coluna_existe()
            t2_resolver_helper()
            t3_nova_obra_via_post()
            t4_propagacao_proposta_aprovada()
            t5_fallback_obra_legada()
            db.session.rollback()
        except Exception as e:
            db.session.rollback()
            FAIL.append(('EXCEPTION', str(e)))
            import traceback
            traceback.print_exc()

    print('=' * 80)
    print(f'PASS: {len(PASS)}  FAIL: {len(FAIL)}')
    print('=' * 80)
    for label, ev in FAIL:
        print(f'  FAIL: {label} — {ev}')
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
