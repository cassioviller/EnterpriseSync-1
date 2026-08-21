"""O cenário do manual do RDO é DADO: o seed cria tudo, duas vezes dá o mesmo.

Plano: docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import main  # noqa: F401 — registra os blueprints
from app import app
from models import (Funcionario, PapelObra, Subempreiteiro, TarefaCronograma,
                    Usuario, UsuarioObra)
from test_cronograma_endpoints_m05 import _client_como

pytestmark = pytest.mark.integration


def _contagens(admin_id, obra_id):
    return {
        'tarefas': TarefaCronograma.query.filter_by(obra_id=obra_id, ativa=True).count(),
        'funcionarios': Funcionario.query.filter_by(admin_id=admin_id).count(),
        'subempreiteiros': Subempreiteiro.query.filter_by(admin_id=admin_id).count(),
        'vinculos': UsuarioObra.query.filter_by(obra_id=obra_id).count(),
    }


def test_seed_e_idempotente_e_monta_o_cenario_inteiro():
    from seed_manual_rdo import resumo, semear
    with app.app_context():
        admin = semear()
        ids = resumo(admin)
        antes = _contagens(admin.id, ids['obra_id'])
        admin2 = semear()
        depois = _contagens(admin2.id, ids['obra_id'])
    assert admin2.id == admin.id
    assert antes == depois
    assert antes['tarefas'] == 6          # 2 fases + 4 folhas
    assert antes['funcionarios'] == 4     # 3 operacionais + 1 administrativo
    assert antes['subempreiteiros'] == 1
    assert antes['vinculos'] == 2         # encarregado APONTADOR, gestor GESTOR


def test_encarregado_aponta_e_gestor_edita():
    from seed_manual_rdo import resumo, semear
    with app.app_context():
        admin = semear()
        ids = resumo(admin)
        enc = Usuario.query.filter_by(username='manualrdo_encarregado').one()
        ges = Usuario.query.filter_by(username='manualrdo_gestor').one()
        papeis = {v.usuario_id: v.papel for v in
                  UsuarioObra.query.filter_by(obra_id=ids['obra_id']).all()}
    assert papeis[enc.id] == PapelObra.APONTADOR
    assert papeis[ges.id] == PapelObra.GESTOR


def test_feed_do_rdo_traz_as_quatro_folhas_com_o_modo_certo():
    """É o que a tela 05 fotografa: quantidade, terceiros, percentual e marco."""
    from seed_manual_rdo import resumo, semear
    with app.app_context():
        admin = semear()
        ids = resumo(admin)
        enc_id = Usuario.query.filter_by(username='manualrdo_encarregado').one().id
    client = _client_como(enc_id)
    r = client.get(f"/cronograma/obra/{ids['obra_id']}/tarefas-rdo")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    tarefas = corpo.get('tarefas') if isinstance(corpo, dict) else corpo
    por_id = {t['id']: t for t in tarefas}
    assert ids['t_blocos'] in por_id and ids['t_estacas'] in por_id
    assert ids['t_pilares'] in por_id and ids['t_marco'] in por_id
    assert por_id[ids['t_estacas']]['responsavel'] == 'terceiros'
    assert por_id[ids['t_marco']].get('is_marco') is True
