"""B5.3 — RDO de outro tenant — E de outra obra — responde 404.

Task B5.3 de `docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`.

**O que este arquivo mede.** Três coisas que o 302 de hoje esconde:

1. O eixo TENANT: `/rdo/<id>`, `/rdo/<id>/pdf` e `/rdo/excluir/<id>` de RDO
   alheio devolviam 302 com flash — e `finalizar`/`atualizar`/`editar` tinham
   o 404 ESCRITO (`_rdo_do_tenant_ou_404` / `first_or_404`) e ENGOLIDO por
   `except Exception` largo. A regra da casa (B1.15, `_rdo_do_tenant_ou_404`)
   é 404 — não vazar sequer a existência.
2. O eixo OBRA (Fase 1): com `escopo_obra_ativo` ligado, um APONTADOR
   vinculado só à obra X lia, exportava PDF e APAGAVA o RDO da obra Y do
   mesmo tenant. A rota irmã de leitura (`cronograma_views.py:2695-2704`)
   já barra com 404; as três daqui não barravam.
3. O oráculo de enumeração POR MENSAGEM em `criar_rdo`: depois de a query com
   tenant falhar, uma SEGUNDA query sem tenant escolhia entre "outra empresa"
   e "não encontrada" — os dois caminhos 302, o vazamento na flash.

**Matriz de mutação (Step do recorte).** Remover o `except HTTPException:
raise` de um handler derruba o caso 5 daquele handler; remover o
`pode_ver_obra` derruba só o caso 6; restaurar a segunda query sem tenant
derruba só o caso 7.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Obra, PapelObra, RDO, TipoUsuario, Usuario,
                    UsuarioObra)


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin B53'):
    s = _sfx()
    u = Usuario(
        username=f'b53_{s}', email=f'b53_{s}@test.local', nome=f'{nome} {s}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id):
    s = _sfx()
    u = Usuario(
        username=f'b53op_{s}', email=f'b53op_{s}@test.local', nome=f'Op {s}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=admin_id)
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra B53'):
    s = _sfx()
    cliente = Cliente(nome=f'Cliente {s}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.flush()
    o = Obra(nome=f'{nome} {s}', codigo=f'B53{s[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, status='Em andamento', ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _rdo(obra, admin_id):
    s = _sfx()
    r = RDO(numero_rdo=f'RDO-B53-{s}', data_relatorio=date(2026, 6, 22),
            obra_id=obra.id, admin_id=admin_id,
            comentario_geral='B5.3', clima_geral='Bom')
    db.session.add(r)
    db.session.commit()
    return r


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c


def _flashes(cli):
    with cli.session_transaction() as s:
        return s.get('_flashes', [])


@pytest.fixture()
def dois_tenants_com_rdo():
    """Tenant A (quem ataca) e tenant B (dono do RDO). Function-scoped: o caso
    4 apaga estado."""
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        rdo_b = _rdo(obra_b, admin_b.id)
        return {'aid': admin_a.id, 'bid': admin_b.id,
                'obra_b': obra_b.id, 'rdo_b': rdo_b.id}


def test_caso1_e_2_visualizar_alheio_e_inexistente_404_corpo_identico(dois_tenants_com_rdo):
    ctx = dois_tenants_com_rdo
    cli = _cliente_de(ctx['aid'])

    r_alheio = cli.get(f"/rdo/{ctx['rdo_b']}", follow_redirects=False)
    r_inexistente = cli.get('/rdo/99999999', follow_redirects=False)

    assert r_alheio.status_code == 404, (
        f"RDO alheio devolveu {r_alheio.status_code} — o 302 com flash é o "
        f"comportamento que a B5.3 aposenta")
    assert r_inexistente.status_code == 404
    # Corpo idêntico: alheio e inexistente não podem ser distinguíveis — é o
    # mesmo critério de oráculo da B1.15.
    assert r_alheio.get_data() == r_inexistente.get_data()


def test_caso3_pdf_de_rdo_alheio_404(dois_tenants_com_rdo):
    ctx = dois_tenants_com_rdo
    cli = _cliente_de(ctx['aid'])
    r = cli.get(f"/rdo/{ctx['rdo_b']}/pdf", follow_redirects=False)
    assert r.status_code == 404, f'PDF de RDO alheio devolveu {r.status_code}'


def test_caso4_excluir_rdo_alheio_404_e_rdo_sobrevive(dois_tenants_com_rdo):
    ctx = dois_tenants_com_rdo
    cli = _cliente_de(ctx['aid'])
    r = cli.post(f"/rdo/excluir/{ctx['rdo_b']}", follow_redirects=False)
    assert r.status_code == 404, (
        f'excluir RDO alheio devolveu {r.status_code}')
    with app.app_context():
        assert db.session.get(RDO, ctx['rdo_b']) is not None, (
            'o RDO de B foi apagado por um usuário de A')


def test_caso5_finalizar_atualizar_editar_alheios_404(dois_tenants_com_rdo):
    """As três rotas em que o 404 já estava ESCRITO e era engolido pelo
    `except Exception` largo (`views/rdo.py:1660`, `:2069`, `:2150`) —
    devolviam 302 (🔬 Location `/rdo/lista`, `/rdo/<id>/editar`, `/rdo/lista`).
    """
    ctx = dois_tenants_com_rdo
    cli = _cliente_de(ctx['aid'])

    r_fin = cli.post(f"/rdo/{ctx['rdo_b']}/finalizar", follow_redirects=False)
    r_atu = cli.post(f"/rdo/{ctx['rdo_b']}/atualizar",
                     data={'data_relatorio': '2026-06-23'},
                     follow_redirects=False)
    r_edi = cli.get(f"/rdo/{ctx['rdo_b']}/editar", follow_redirects=False)

    assert r_fin.status_code == 404, f'finalizar: {r_fin.status_code}'
    assert r_atu.status_code == 404, f'atualizar: {r_atu.status_code}'
    assert r_edi.status_code == 404, f'editar: {r_edi.status_code}'


def test_caso6_escopo_obra_apontador_nao_ve_rdo_de_outra_obra_do_tenant():
    """Eixo OBRA da Fase 1: APONTADOR vinculado só à obra X, flag ligada, pede
    o RDO da obra Y DO MESMO TENANT → 404 nas três rotas. É o que
    `cronograma_views.py:2695-2704` já faz em rota de leitura de RDO."""
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin('C6')
        obra_x, obra_y = _obra(admin.id, 'ObraX'), _obra(admin.id, 'ObraY')
        rdo_y = _rdo(obra_y, admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra_x.id,
                                   papel=PapelObra.APONTADOR,
                                   admin_id=admin.id))
        db.session.commit()
        definir_flag(admin.id, True)
        rid, opid = rdo_y.id, op.id

    cli = _cliente_de(opid)
    r_ver = cli.get(f'/rdo/{rid}', follow_redirects=False)
    r_pdf = cli.get(f'/rdo/{rid}/pdf', follow_redirects=False)
    r_exc = cli.post(f'/rdo/excluir/{rid}', follow_redirects=False)

    assert r_ver.status_code == 404, (
        f'visualizar cross-obra: {r_ver.status_code} — o APONTADOR da obra X '
        f'leu o RDO da obra Y')
    assert r_pdf.status_code == 404, f'pdf cross-obra: {r_pdf.status_code}'
    assert r_exc.status_code == 404, f'excluir cross-obra: {r_exc.status_code}'
    with app.app_context():
        assert db.session.get(RDO, rid) is not None


def test_caso7_criar_rdo_nao_distingue_outra_empresa_de_inexistente(dois_tenants_com_rdo):
    """A segunda query SEM tenant de `criar_rdo` existia só para escolher a
    mensagem — 'Acesso negado: esta obra pertence a outra empresa.' contra
    'Obra não encontrada.'. Enumeração por mensagem; os dois caminhos 302."""
    ctx = dois_tenants_com_rdo
    cli = _cliente_de(ctx['aid'])

    cli.post('/rdo/criar',
             data={'obra_id': str(ctx['obra_b']),
                   'data_relatorio': '2026-06-22'},
             follow_redirects=False)
    msgs_alheia = [m for _, m in _flashes(cli)]

    cli2 = _cliente_de(ctx['aid'])
    cli2.post('/rdo/criar',
              data={'obra_id': '99999999', 'data_relatorio': '2026-06-22'},
              follow_redirects=False)
    msgs_inexistente = [m for _, m in _flashes(cli2)]

    assert not any('outra empresa' in m for m in msgs_alheia), (
        f'a flash distingue obra alheia de inexistente: {msgs_alheia}')
    assert msgs_alheia == msgs_inexistente, (
        f'mensagens diferentes = oráculo: {msgs_alheia} × {msgs_inexistente}')
