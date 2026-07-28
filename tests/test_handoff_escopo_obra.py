"""O dossiê de handoff respeita o escopo por obra da Fase 1.

`handoff_obra_get` filtrava só por tenant. Com `escopo_obra_ativo` ligada,
qualquer usuário do tenant abria o dossiê de handoff de qualquer obra dele —
inclusive de obra em que não tem vínculo nenhum. O POST irmão
(`handoff_obra_post`) já checava com `pode_transitar_como`; era o GET que
entregava a informação.

Não é escalada de privilégio (o POST continua barrado), é exposição: o
dossiê traz o dado da obra e a lista de candidatos a gestor.
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
from models import (Cliente, Funcionario, Obra, PapelObra, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-handoff-escopo'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _cenario(com_vinculo, flag_ligada=True):
    """Admin + obra + um FUNCIONARIO com ou sem vínculo na obra.

    Devolve (admin_id, obra_id, usuario_id do funcionário).
    """
    from scripts.flag_escopo_obra import definir_flag

    suf = _sfx()
    admin = Usuario(username=f'hof_{suf}', email=f'hof_{suf}@t.local',
                    nome=f'Admin HOF {suf}',
                    password_hash=generate_password_hash('Senha@2026'),
                    tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                    versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()
    # Sem a flag, `papel_na_obra` devolve GESTOR a todo mundo do tenant
    # (comportamento pré-Fase 1 preservado de propósito) e o teste não
    # distinguiria nada.
    definir_flag(admin.id, flag_ligada)

    cli = Cliente(nome=f'CLI-HOF-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra HOF {suf}', codigo=f'OHF{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    func = Funcionario(codigo=f'H{suf[:6].upper()}', nome=f'Pessoa {suf}',
                       cpf=suf.ljust(14, '0')[:14],
                       data_admissao=date(2025, 1, 1), admin_id=admin.id,
                       ativo=True)
    db.session.add(func)
    db.session.commit()

    ator = Usuario(username=f'hofu_{suf}', email=f'hofu_{suf}@t.local',
                   nome=f'Ator {suf}',
                   password_hash=generate_password_hash('x'),
                   tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
                   admin_id=admin.id, funcionario_id=func.id)
    db.session.add(ator)
    db.session.commit()

    if com_vinculo:
        db.session.add(UsuarioObra(usuario_id=ator.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id,
                                   ativo=True))
        db.session.commit()

    return admin.id, obra.id, ator.id


def _get_handoff(user_id, obra_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c.get(f'/obras/{obra_id}/handoff')


def test_sem_vinculo_na_obra_nao_ve_o_dossie():
    with app.app_context():
        _admin_id, obra_id, ator_id = _cenario(com_vinculo=False)

        resp = _get_handoff(ator_id, obra_id)

        assert resp.status_code == 404, (
            f'usuário sem vínculo abriu o dossiê de handoff ({resp.status_code})')


def test_com_vinculo_continua_vendo():
    """A correção não pode ter trancado quem tem direito."""
    with app.app_context():
        _admin_id, obra_id, ator_id = _cenario(com_vinculo=True)

        resp = _get_handoff(ator_id, obra_id)

        assert resp.status_code == 200, (
            f'gestor vinculado foi barrado ({resp.status_code})')


def test_admin_do_tenant_ve_sem_precisar_de_vinculo():
    """ADMIN não tem linha em `usuario_obra` e enxerga tudo do tenant."""
    with app.app_context():
        admin_id, obra_id, _ator = _cenario(com_vinculo=False)

        resp = _get_handoff(admin_id, obra_id)

        assert resp.status_code == 200, (
            f'admin do tenant foi barrado ({resp.status_code})')


def test_com_a_flag_desligada_nada_muda():
    """`escopo_obra_ativo` desligada = comportamento pré-Fase 1, permissivo.

    `papel_na_obra` devolve GESTOR a qualquer usuário do tenant quando o eixo
    de obra não está em vigor — a correção não pode antecipar o rollout.
    """
    with app.app_context():
        _admin_id, obra_id, ator_id = _cenario(com_vinculo=False,
                                               flag_ligada=False)

        resp = _get_handoff(ator_id, obra_id)

        assert resp.status_code == 200, (
            'a correção estreitou o acesso com a flag DESLIGADA — isso é '
            'antecipar o rollout da Fase 1')
