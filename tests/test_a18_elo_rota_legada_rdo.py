"""A18 — o RDO salvo pela rota legada nasce com o elo subatividade_mestre_id.

A rota `POST /rdo/salvar` (views/rdo.py, rdo_salvar_unificado) cria
`RDOServicoSubatividade` sem o elo com o catálogo, e a derivação de
progresso cai em 'linha' em silêncio. O form legado já carrega o id do
mestre na própria chave (`subatividade_<servico>_<mestre>_percentual`) —
o elo é resolvido por esse id VALIDADO no tenant, com fallback por
igualdade exata de (admin_id, servico_id, nome). Sem match, None — nunca
chutar. É o mesmo elo que o fluxo novo grava em views/rdo.py:4258.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §A18.
"""
import uuid
from datetime import date

import pytest

from app import app, db
from helpers_tenant import cliente_de


@pytest.fixture()
def cenario():
    """Admin + obra + serviço + uma SubatividadeMestre de nome conhecido."""
    with app.app_context():
        from models import (Usuario, TipoUsuario, Obra, Servico,
                            SubatividadeMestre, Cliente)
        from werkzeug.security import generate_password_hash
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'a18{marca}', email=f'a18{marca}@t.local', nome='A18',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.flush()
        cliente = Cliente(nome=f'Cliente A18 {marca}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(nome=f'Obra A18 {marca}', admin_id=admin.id,
                    cliente_id=cliente.id, data_inicio=date(2026, 9, 1))
        db.session.add(obra)
        servico = Servico(nome=f'Servico A18 {marca}', admin_id=admin.id,
                          categoria='estrutura', unidade_medida='un')
        db.session.add(servico)
        db.session.flush()
        sub = SubatividadeMestre(
            nome=f'Montagem de teste A18 {marca}', servico_id=servico.id,
            admin_id=admin.id, ativo=True)
        db.session.add(sub)
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id,
               'servico_id': servico.id, 'sub_id': sub.id,
               'sub_nome': sub.nome}
        db.session.rollback()


def test_rota_legada_grava_o_elo_do_catalogo(cenario):
    c = cenario
    cliente = cliente_de(c['admin_id'])
    resposta = cliente.post('/rdo/salvar', data={
        'obra_id': str(c['obra_id']),
        'data_relatorio': '2026-09-01',
        # formato primário do parser legado:
        # subatividade_<servico_id>_<mestre_id>_percentual
        f"subatividade_{c['servico_id']}_{c['sub_id']}_percentual": '10',
        # campo oculto que o parser prioriza para fixar o serviço
        'servico_id_correto': str(c['servico_id']),
    }, follow_redirects=False)
    assert resposta.status_code in (200, 302), resposta.status_code

    with app.app_context():
        from models import RDOServicoSubatividade
        linha = (RDOServicoSubatividade.query
                 .filter_by(admin_id=c['admin_id'],
                            nome_subatividade=c['sub_nome'])
                 .order_by(RDOServicoSubatividade.id.desc()).first())
        assert linha is not None, (
            'o POST não chegou ao construtor da rota legada — gatilho '
            'quebrado, não o alvo: ajuste o form antes de concluir algo')
        assert linha.subatividade_mestre_id == c['sub_id'], (
            'a rota legada gravou a subatividade SEM o elo do catálogo')
