"""Fase 1 — escopo por obra.

Até 2026-07-21 o único eixo de isolamento era `admin_id` (tenant): quem
entrava via qualquer papel enxergava TODAS as obras da empresa. Estes
testes travam o segundo eixo — o vínculo usuário↔obra.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, Obra, PapelObra, TipoUsuario, Usuario, UsuarioObra

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-escopo'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1e_{suf}', email=f'f1e_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f1o_{suf}', email=f'f1o_{suf}@test.local',
        nome=f'{nome} {suf}', password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'O{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id, ativo=True,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_papel_obra_tem_os_valores_esperados():
    """Três na Fase 1; COMPRADOR entrou na Fase 3, com rota que o consome."""
    assert {p.name for p in PapelObra} == {
        'GESTOR', 'APONTADOR', 'LEITOR', 'COMPRADOR'}


def test_vinculo_usuario_obra_persiste():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        v = UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                        papel=PapelObra.GESTOR, admin_id=admin.id)
        db.session.add(v)
        db.session.commit()
        vid = v.id

    with app.app_context():
        recarregado = db.session.get(UsuarioObra, vid)
        assert recarregado.papel == PapelObra.GESTOR
        assert recarregado.ativo is True


def test_usuario_nao_se_vincula_duas_vezes_a_mesma_obra():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id))
        db.session.commit()
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Flag de rollout
# ---------------------------------------------------------------------------

def test_flag_escopo_obra_nasce_desligada():
    from scripts.flag_escopo_obra import escopo_ativo

    with app.app_context():
        admin = _admin()
        assert escopo_ativo(admin.id) is False, (
            'flag ligada por padrão tiraria acesso de todo mundo no deploy')


def test_flag_escopo_obra_liga_e_desliga():
    from scripts.flag_escopo_obra import definir_flag, escopo_ativo

    with app.app_context():
        admin = _admin()
        definir_flag(admin.id, True)
        assert escopo_ativo(admin.id) is True
        definir_flag(admin.id, False)
        assert escopo_ativo(admin.id) is False


# ---------------------------------------------------------------------------
# Chokepoint de autorização
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_admin_ve_todas_as_obras_do_tenant_mesmo_com_flag_ligada():
    """ADMIN não precisa de vínculo. Regra que evita apagão no deploy."""
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import obras_visiveis

    with app.app_context():
        admin = _admin()
        o1, o2 = _obra(admin.id, 'Um'), _obra(admin.id, 'Dois')
        definir_flag(admin.id, True)
        ids_esperados = {o1.id, o2.id}
        aid = admin.id

    cliente = _cliente_de(aid)
    with cliente:
        cliente.get('/dashboard')
        visiveis = {o.id for o in obras_visiveis().all()}
    assert ids_esperados <= visiveis


def test_flag_desligada_preserva_o_comportamento_antigo():
    """Não-admin sem vínculo continua vendo o tenant inteiro."""
    from utils.autorizacao import obras_visiveis

    with app.app_context():
        admin = _admin()
        o1 = _obra(admin.id)
        op = _operador(admin.id)  # sem nenhum UsuarioObra
        oid, opid = o1.id, op.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        visiveis = {o.id for o in obras_visiveis().all()}
    assert oid in visiveis


def test_flag_ligada_restringe_nao_admin_as_obras_vinculadas():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import obras_visiveis

    with app.app_context():
        admin = _admin()
        minha, alheia = _obra(admin.id, 'Minha'), _obra(admin.id, 'Alheia')
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=minha.id,
                                   papel=PapelObra.APONTADOR, admin_id=admin.id))
        db.session.commit()
        definir_flag(admin.id, True)
        minha_id, alheia_id, opid = minha.id, alheia.id, op.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        visiveis = {o.id for o in obras_visiveis().all()}
    assert minha_id in visiveis
    assert alheia_id not in visiveis, 'obra sem vínculo vazou com a flag ligada'


def test_vinculo_inativo_nao_da_acesso():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import pode_ver_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id,
                                   ativo=False))
        db.session.commit()
        definir_flag(admin.id, True)
        oid, opid = obra.id, op.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(oid) is False


def test_obra_de_outro_tenant_nunca_e_visivel():
    """O eixo antigo (tenant) continua valendo, flag ou não."""
    from utils.autorizacao import pode_ver_obra

    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        op_a = _operador(admin_a.id)
        oid, opid = obra_b.id, op_a.id

    cliente = _cliente_de(opid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(oid) is False


def test_leitor_nao_edita_apontador_nao_edita_gestor_edita():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import pode_editar_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        definir_flag(admin.id, True)
        atores = {}
        for papel in (PapelObra.LEITOR, PapelObra.APONTADOR, PapelObra.GESTOR):
            op = _operador(admin.id, papel.value)
            db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id))
            atores[papel] = op.id
        db.session.commit()
        oid = obra.id

    esperado = {PapelObra.LEITOR: False, PapelObra.APONTADOR: False,
                PapelObra.GESTOR: True}
    for papel, uid in atores.items():
        cliente = _cliente_de(uid)
        with cliente:
            cliente.get('/dashboard')
            assert pode_editar_obra(oid) is esperado[papel], (
                f'{papel.name} deveria ter pode_editar_obra='
                f'{esperado[papel]}')


def test_anonimo_nao_ve_obra_nenhuma():
    from utils.autorizacao import obras_visiveis, pode_ver_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        oid = obra.id

    anon = app.test_client()
    with anon:
        anon.get('/dashboard')
        assert obras_visiveis().count() == 0
        assert pode_ver_obra(oid) is False


# ---------------------------------------------------------------------------
# Flag DESLIGADA — a promessa de reversibilidade
# ---------------------------------------------------------------------------
#
# Lacuna encontrada ao revisar o chokepoint contra o código real, não
# prevista pelo plano da Fase 1: os testes acima só exercitam a flag
# LIGADA. A decisão nº 5 da fase diz que "com a flag desligada o
# comportamento é idêntico ao de hoje" — e hoje `editar_obra`
# (views/obras.py:848) tem apenas `@login_required`, sem `@admin_required`.
# Qualquer usuário autenticado do tenant edita qualquer obra dele.
#
# A primeira versão do chokepoint devolvia LEITOR para não-admin com a flag
# desligada, o que faria TODO não-admin perder a edição no dia do deploy —
# exatamente o que a flag existe para impedir.

def test_flag_desligada_nao_tira_edicao_de_ninguem():
    from utils.autorizacao import pode_editar_obra, pode_ver_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        operador = _operador(admin.id, 'sem-vinculo')
        db.session.commit()
        oid, uid = obra.id, operador.id
        # flag NÃO é ligada — é o estado de todo tenant no deploy

    cliente = _cliente_de(uid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(oid) is True
        assert pode_editar_obra(oid) is True, (
            'com o escopo desligado, o não-admin perdeu a edição que tinha '
            'antes da Fase 1 — a flag deixou de ser reversível')


def test_flag_desligada_ignora_vinculo_restritivo():
    """O backfill grava vínculos ANTES de a flag ser ligada.

    Um LEITOR gravado nessa janela não pode restringir ninguém enquanto o
    eixo de obra não estiver em vigor.
    """
    from utils.autorizacao import pode_editar_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        operador = _operador(admin.id, 'leitor-precoce')
        db.session.add(UsuarioObra(usuario_id=operador.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id))
        db.session.commit()
        oid, uid = obra.id, operador.id

    cliente = _cliente_de(uid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_editar_obra(oid) is True, (
            'vínculo gravado pelo backfill restringiu antes de a flag ligar'
        )


def test_flag_ligada_faz_o_vinculo_valer():
    """A contraprova: o mesmo cenário, com o eixo em vigor, restringe."""
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import pode_editar_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        operador = _operador(admin.id, 'leitor')
        db.session.add(UsuarioObra(usuario_id=operador.id, obra_id=obra.id,
                                   papel=PapelObra.LEITOR, admin_id=admin.id))
        db.session.commit()
        definir_flag(admin.id, True)
        oid, uid = obra.id, operador.id

    cliente = _cliente_de(uid)
    with cliente:
        cliente.get('/dashboard')
        assert pode_editar_obra(oid) is False


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

ROTAS_QUE_EXIGEM_LOGIN = [
    '/obras',
    '/dashboard',
]


@pytest.mark.parametrize('rota', ROTAS_QUE_EXIGEM_LOGIN)
def test_rota_anonima_exige_login(rota):
    """Rotas que estavam SEM decorator nenhum até a Fase 1."""
    anon = app.test_client()
    r = anon.get(rota, follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'{rota} devolveu {r.status_code} para anônimo — deveria exigir login')
    if r.status_code == 302:
        assert '/login' in r.headers.get('Location', '')


def test_detalhe_de_obra_exige_login():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        oid = obra.id

    anon = app.test_client()
    r = anon.get(f'/obras/{oid}', follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'/obras/{oid} devolveu {r.status_code} para anônimo')


def test_detalhe_de_obra_de_outro_tenant_devolve_404():
    """404 e não 403: não vazar sequer a existência da obra."""
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        op_a = _operador(admin_a.id)
        oid, opid = obra_b.id, op_a.id

    cliente = _cliente_de(opid)
    r = cliente.get(f'/obras/{oid}', follow_redirects=False)
    assert r.status_code == 404, (
        f'obra de outro tenant devolveu {r.status_code} — deveria ser 404')


def test_detalhe_de_obra_sem_vinculo_devolve_404_com_flag_ligada():
    from scripts.flag_escopo_obra import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)  # sem vínculo
        definir_flag(admin.id, True)
        oid, opid = obra.id, op.id

    cliente = _cliente_de(opid)
    r = cliente.get(f'/obras/{oid}', follow_redirects=False)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Backfill de vínculos
# ---------------------------------------------------------------------------

def test_obra_tem_relationship_responsavel():
    """`obra.responsavel` resolvia para Undefined nos templates."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        assert hasattr(obra, 'responsavel')
        assert obra.responsavel is None  # sem responsavel_id


def test_backfill_promove_responsavel_da_obra_a_gestor():
    from datetime import date as _date

    from models import Funcionario
    from scripts.backfill_usuario_obra import executar_backfill_obras
    from utils.identidade import vincular_funcionario

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        suf = uuid.uuid4().hex[:8]
        func = Funcionario(
            codigo=f'R{suf[:6].upper()}', nome=f'Responsavel {suf}',
            cpf=f'{suf[:11]}', email=f'resp_{suf}@test.local',
            data_admissao=_date(2026, 1, 1), admin_id=admin.id, ativo=True)
        db.session.add(func)
        db.session.commit()

        op = _operador(admin.id)
        vincular_funcionario(op, func)
        obra.responsavel_id = func.id
        db.session.commit()
        oid, opid = obra.id, op.id

        executar_backfill_obras(dry_run=False, admin_id=admin.id)

        vinculo = UsuarioObra.query.filter_by(
            usuario_id=opid, obra_id=oid).first()
        assert vinculo is not None, 'responsável não virou GESTOR'
        assert vinculo.papel == PapelObra.GESTOR


def test_backfill_obras_e_idempotente():
    from scripts.backfill_usuario_obra import executar_backfill_obras

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        db.session.add(UsuarioObra(usuario_id=op.id, obra_id=obra.id,
                                   papel=PapelObra.GESTOR, admin_id=admin.id))
        db.session.commit()

        relatorio = executar_backfill_obras(dry_run=False, admin_id=admin.id)
        assert relatorio['criados'] == 0


def test_backfill_obras_nao_cruza_tenant():
    from scripts.backfill_usuario_obra import executar_backfill_obras

    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        _operador(admin_a.id)
        executar_backfill_obras(dry_run=False, admin_id=admin_a.id)

        vazou = UsuarioObra.query.filter_by(obra_id=obra_b.id).count()
        assert vazou == 0
