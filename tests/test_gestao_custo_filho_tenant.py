"""`editar_filho` não pode mover lançamento para obra de outro tenant.

`gestao_custos_views.editar_filho` gravava `filho.obra_id` direto do
formulário, com `int()` como única validação. Um POST com a obra de outro
tenant era aceito: o lançamento passava a apontar para lá e
`sincronizar_obra_do_pai` levava o `pai.obra_id` junto — dado de um tenant
referenciando a obra de outro.

O campo `obra_servico_custo_id`, escrito logo abaixo no mesmo bloco, sempre
validou com `filter_by(id=..., admin_id=admin_id)`. O `obra_id` ficou de fora.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, GestaoCustoFilho, GestaoCustoPai, Obra,
                    TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-filho-tenant'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _tenant(prefixo):
    """Admin + obra próprios. Devolve (admin_id, obra_id)."""
    suf = _sfx()
    u = Usuario(username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@t.local',
                nome=f'Admin {prefixo} {suf}',
                password_hash=generate_password_hash('Senha@2026'),
                tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    cli = Cliente(nome=f'CLI-{suf}', admin_id=u.id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra {prefixo} {suf}', codigo=f'O{suf[:7].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=u.id, cliente_id=cli.id,
             valor_contrato=100000)
    db.session.add(o)
    db.session.commit()
    return u.id, o.id


def _filho_de(admin_id, obra_id):
    pai = GestaoCustoPai(tipo_categoria='MATERIAL', entidade_nome=f'F {_sfx()}',
                         admin_id=admin_id, obra_id=obra_id, status='PENDENTE')
    db.session.add(pai)
    db.session.flush()
    f = GestaoCustoFilho(
        pai_id=pai.id, admin_id=admin_id, obra_id=obra_id,
        data_referencia=date(2026, 6, 22), descricao='Cimento',
        valor=Decimal('1000.00'), origem_tabela='importacao_custos',
        origem_id=0)
    db.session.add(f)
    db.session.commit()
    return f.id


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c


def _post(user_id, filho_id, obra_id):
    return _cliente_de(user_id).post(
        f'/gestao-custos/filho/{filho_id}/editar',
        data={'descricao': 'Cimento', 'valor': '1000.00',
              'data_referencia': '2026-06-22', 'obra_id': str(obra_id)})


def test_nao_move_lancamento_para_obra_de_outro_tenant():
    with app.app_context():
        admin_a, obra_a = _tenant('gcfA')
        _admin_b, obra_b = _tenant('gcfB')
        fid = _filho_de(admin_a, obra_a)

        resp = _post(admin_a, fid, obra_b)

        assert resp.status_code == 400, (
            f'obra de outro tenant foi aceita ({resp.status_code})')
        db.session.expire_all()
        f = db.session.get(GestaoCustoFilho, fid)
        assert f.obra_id == obra_a, (
            f'lançamento migrou para a obra {f.obra_id} de outro tenant')
        pai = db.session.get(GestaoCustoPai, f.pai_id)
        assert pai.obra_id == obra_a, (
            'a derivação levou o pai junto para a obra do outro tenant')


def test_a_mensagem_nao_revela_que_a_obra_existe():
    """Obra alheia e obra inexistente têm de responder igual.

    Resposta diferente para os dois casos vira oráculo de existência de obra
    de outro tenant. Mesma doutrina do 404-em-vez-de-403 em
    `_rdo_do_tenant_ou_404` e `obra_required`.
    """
    with app.app_context():
        admin_a, obra_a = _tenant('gcfC')
        _admin_b, obra_b = _tenant('gcfD')
        fid = _filho_de(admin_a, obra_a)

        alheia = _post(admin_a, fid, obra_b)
        inexistente = _post(admin_a, fid, 999_999_999)

        assert alheia.status_code == inexistente.status_code
        assert alheia.get_json() == inexistente.get_json(), (
            f'respostas distinguem obra alheia de inexistente: '
            f'{alheia.get_json()} vs {inexistente.get_json()}')


def test_mover_para_obra_do_proprio_tenant_continua_funcionando():
    """A correção não pode ter travado o caso legítimo."""
    with app.app_context():
        admin_a, obra_a = _tenant('gcfE')
        suf = _sfx()
        cli = Cliente(nome=f'CLI2-{suf}', admin_id=admin_a)
        db.session.add(cli)
        db.session.flush()
        outra = Obra(nome=f'Outra {suf}', codigo=f'X{suf[:7].upper()}',
                     data_inicio=date(2026, 1, 1), admin_id=admin_a,
                     cliente_id=cli.id, valor_contrato=50000)
        db.session.add(outra)
        db.session.commit()
        fid = _filho_de(admin_a, obra_a)

        resp = _post(admin_a, fid, outra.id)

        assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
        db.session.expire_all()
        assert db.session.get(GestaoCustoFilho, fid).obra_id == outra.id
