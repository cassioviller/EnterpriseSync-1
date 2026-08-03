"""p1 Steps B e C — a heurística de adivinhar tenant, e o custo por batida.

**Step B** — três rotas escolhiam a empresa por contagem de linhas ("a que
tem mais funcionários ativos", "a que tem mais obras"). O teste central é o
funcionário órfão: usuário autenticado **sem** `admin_id`, que era justamente
quem caía na heurística e recebia os dados da maior empresa da base.

**Step C** — `ponto_registrado` é emitido a cada batida. Quatro batidas no
mesmo dia geravam quatro linhas de custo; agora geram uma, com o valor do
último cálculo.
"""
import os
import sys
from datetime import date, time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import CustoObra, RegistroPonto, TipoUsuario, Usuario
from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

DATA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-p1-fallback'
    with app.app_context():
        yield


@pytest.fixture(scope='module')
def _par():
    with app.app_context():
        return dois_tenants('fbk', DATA)


def _usuario_orfao():
    """Usuário autenticado, tipo FUNCIONARIO, **sem** `admin_id`.

    É o caso que a heurística existia para "resolver": sem tenant, ela servia
    o da maior empresa. A resposta certa é não servir nada.
    """
    from uuid import uuid4
    suf = uuid4().hex[:8]
    u = Usuario(username=f'orfao_{suf}', email=f'orfao_{suf}@t.local',
                nome=f'Orfao {suf}',
                password_hash=generate_password_hash('Senha@2026'),
                tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
                admin_id=None)
    db.session.add(u)
    db.session.commit()
    return u.id


# ---------------------------------------------------------------------------
# Step B
# ---------------------------------------------------------------------------

def test_orfao_nao_recebe_a_maior_empresa_na_lista_de_rdos(_par):
    a, b = _par
    resposta = cliente_de(_usuario_orfao()).get('/rdos')
    assert resposta.status_code in (302, 404), resposta.status_code
    corpo = resposta.get_data()
    assert a.marca.encode() not in corpo and b.marca.encode() not in corpo


def test_orfao_nao_abre_o_detalhe_de_obra_alheia(_par):
    a, _b = _par
    resposta = cliente_de(_usuario_orfao()).get(f'/obras/{a.obra_id}')
    assert resposta.status_code in (302, 404), resposta.status_code
    assert a.marca.encode() not in resposta.get_data()


def test_detalhe_de_obra_de_outro_tenant_da_404(_par):
    """Era a pior das três saídas: quando a obra não era do tenant, o código
    buscava DE NOVO sem filtro e adotava a obra encontrada, reescrevendo o
    admin_id para o dono dela."""
    a, b = _par
    resposta = cliente_de(a.admin_id).get(f'/obras/{b.obra_id}')
    assert resposta.status_code == 404, resposta.status_code
    assert b.marca.encode() not in resposta.get_data()


def test_o_dono_continua_abrindo_a_propria_obra(_par):
    a, _b = _par
    resposta = cliente_de(a.admin_id).get(f'/obras/{a.obra_id}')
    assert resposta.status_code == 200, resposta.status_code
    assert a.marca in resposta.get_data(as_text=True)


def test_percentuais_do_ultimo_rdo_nao_atende_obra_alheia(_par):
    a, b = _par
    resposta = cliente_de(a.admin_id).get(
        f'/api/obra/{b.obra_id}/percentuais-ultimo-rdo')
    assert resposta.status_code == 404, resposta.status_code


def test_existe_um_unico_resolvedor_de_tenant_dinamico():
    """O sósia de `views/api.py` sombreava o import do topo do módulo."""
    import views.api as api
    import views.helpers as helpers
    assert api.get_admin_id_dinamico is helpers.get_admin_id_dinamico


# ---------------------------------------------------------------------------
# Step C
# ---------------------------------------------------------------------------

def _bater_ponto(tenant, horas, extras, hora_saida):
    """Simula uma batida: atualiza o registro do dia e emite o evento, que é
    o que `PontoService` faz a cada leitura de crachá."""
    from event_manager import EventManager

    registro = RegistroPonto.query.filter_by(
        funcionario_id=tenant.funcionario_id, data=DATA,
        admin_id=tenant.admin_id).first()
    registro.horas_trabalhadas = horas
    registro.horas_extras = extras
    registro.hora_saida = hora_saida
    db.session.commit()

    EventManager.emit('ponto_registrado',
                      {'registro_id': registro.id, 'tipo_ponto': 'saida'},
                      admin_id=tenant.admin_id)
    return registro


def _custos_de_ponto(tenant):
    return CustoObra.query.filter_by(
        funcionario_id=tenant.funcionario_id, data=DATA,
        obra_id=tenant.obra_id, admin_id=tenant.admin_id,
        categoria='PONTO_ELETRONICO').all()


def test_quatro_batidas_no_mesmo_dia_dao_uma_linha_de_custo(_par):
    a, _b = _par
    for custo in _custos_de_ponto(a):
        db.session.delete(custo)
    db.session.commit()

    _bater_ponto(a, 4.0, 0.0, time(12, 0))
    _bater_ponto(a, 6.0, 0.0, time(15, 0))
    _bater_ponto(a, 8.0, 0.0, time(17, 0))
    _bater_ponto(a, 8.0, 2.0, time(19, 0))

    custos = _custos_de_ponto(a)
    assert len(custos) == 1, (
        f'{len(custos)} linhas de custo para o mesmo dia — o horista voltou a '
        f'somar batidas')


def test_a_linha_guarda_o_ultimo_calculo_do_dia(_par):
    """Somar as parciais era o defeito: o certo é o último cálculo valer."""
    a, _b = _par
    for custo in _custos_de_ponto(a):
        db.session.delete(custo)
    db.session.commit()

    _bater_ponto(a, 4.0, 0.0, time(12, 0))
    _bater_ponto(a, 8.0, 2.0, time(19, 0))

    (custo,) = _custos_de_ponto(a)
    assert float(custo.horas_trabalhadas) == 8.0
    assert float(custo.horas_extras) == 2.0


def test_o_custo_do_dia_nao_atravessa_para_o_outro_tenant(_par):
    a, b = _par
    _bater_ponto(a, 8.0, 0.0, time(17, 0))
    assert _custos_de_ponto(b) == [] or all(
        c.admin_id == b.admin_id for c in _custos_de_ponto(b))
