"""Fase 2 — handoff do Gerente de Projeto.

Antes desta fase, `Obra.responsavel_id` era uma FK para `Funcionario` sem
`relationship`, sem efeito em permissão nenhuma, renderizada em quatro
templates que exibiam sempre vazio. Atribuir "responsável" não dava a
ninguém acesso a coisa alguma.

O handoff junta três coisas que precisam acontecer na MESMA transação, ou a
obra fica meio entregue: o responsável, o vínculo `UsuarioObra(GESTOR)` que
é a permissão de verdade, e a resolução do gate de cronograma.
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
from models import (Cliente, Funcionario, Obra, PapelObra, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase2-handoff'
    yield


def _suf():
    return uuid.uuid4().hex[:8]


def _admin(prefixo='hoa'):
    suf = _suf()
    u = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin, estado='planejamento', status='Planejamento',
          revisado_em=None):
    suf = _suf()
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra {suf}', codigo=f'HO{suf[:6].upper()}',
             cliente_id=cli.id, data_inicio=date(2026, 7, 1),
             status=status, estado=estado, ativo=True, admin_id=admin.id,
             cronograma_revisado_em=revisado_em)
    db.session.add(o)
    db.session.commit()
    return o


def _funcionario(admin, com_login=True):
    """Funcionario do tenant. `com_login=False` reproduz o caso que o handoff
    tem de recusar: sem `Usuario` não há a quem dar o papel GESTOR."""
    from utils.identidade import vincular_funcionario
    suf = _suf()
    f = Funcionario(
        codigo=f'HF{suf[:6].upper()}', nome=f'GP {suf}',
        cpf=f'{uuid.uuid4().int % 10**11:011d}',
        data_admissao=date(2026, 1, 5), admin_id=admin.id, ativo=True,
    )
    db.session.add(f)
    db.session.flush()
    if com_login:
        u = Usuario(
            username=f'hgp_{suf}', email=f'hgp_{suf}@test.local',
            nome=f'Login GP {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, versao_sistema='v2',
        )
        db.session.add(u)
        db.session.flush()
        vincular_funcionario(u, f)
    db.session.commit()
    return f


# ---------------------------------------------------------------------------
# O caminho feliz
# ---------------------------------------------------------------------------

def test_handoff_entrega_a_obra_com_os_tres_efeitos():
    """Responsável, vínculo GESTOR e gate de cronograma — indissociáveis."""
    from datetime import datetime

    from models import ObraTransicaoEstado
    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=datetime.utcnow())
        func = _funcionario(admin)

        r = executar_handoff(obra, func, usuario_id=admin.id,
                             motivo='entrega formal')
        db.session.commit()
        db.session.refresh(obra)

        assert obra.estado == 'em_execucao'
        assert obra.status == 'Em andamento'   # espelho legado
        assert obra.ativo is True
        assert obra.responsavel_id == func.id

        vinculo = UsuarioObra.query.filter_by(
            usuario_id=r['usuario_gp_id'], obra_id=obra.id).one()
        assert vinculo.papel == PapelObra.GESTOR
        assert vinculo.ativo is True
        assert r['vinculo_criado'] is True

        reg = db.session.get(ObraTransicaoEstado, r['transicao_id'])
        assert reg.estado_de == 'planejamento'
        assert reg.estado_para == 'em_execucao'
        assert reg.detalhes['tipo'] == 'handoff'
        assert reg.detalhes['funcionario_id'] == func.id


def test_handoff_da_ao_gp_o_poder_de_transitar_a_obra():
    """O ponto do vínculo. Antes do handoff o GP não pausa a obra; depois,
    pausa — sem passar por nenhum admin."""
    from datetime import datetime

    from models import EstadoObra
    from services.obra_estado import pode_transitar_como
    from services.obra_handoff import executar_handoff
    from utils.identidade import usuario_do_funcionario
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=datetime.utcnow())
        func = _funcionario(admin)
        gp = usuario_do_funcionario(func.id)

        assert pode_transitar_como(obra, EstadoObra.EM_EXECUCAO, gp) is False

        executar_handoff(obra, func, usuario_id=admin.id)
        db.session.commit()
        db.session.refresh(obra)

        assert pode_transitar_como(obra, EstadoObra.PAUSADA, gp) is True
        # Mas continua sem poder cancelar: isso é decisão comercial.
        assert pode_transitar_como(obra, EstadoObra.CANCELADA, gp) is False


def test_handoff_reaproveita_vinculo_existente_em_vez_de_duplicar():
    """`usuario_obra` tem UNIQUE (usuario_id, obra_id) desde a Fase 1: um
    INSERT cego quebraria o handoff de quem já era APONTADOR na obra."""
    from datetime import datetime

    from services.obra_handoff import executar_handoff
    from utils.identidade import usuario_do_funcionario
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=datetime.utcnow())
        func = _funcionario(admin)
        gp = usuario_do_funcionario(func.id)
        db.session.add(UsuarioObra(usuario_id=gp.id, obra_id=obra.id,
                                   papel=PapelObra.APONTADOR,
                                   admin_id=admin.id, ativo=True))
        db.session.commit()

        r = executar_handoff(obra, func, usuario_id=admin.id)
        db.session.commit()

        assert r['vinculo_criado'] is False
        vinculos = UsuarioObra.query.filter_by(
            usuario_id=gp.id, obra_id=obra.id).all()
        assert len(vinculos) == 1
        assert vinculos[0].papel == PapelObra.GESTOR, 'promoveu de APONTADOR'


def test_handoff_carimba_o_gate_de_obra_sem_proposta():
    """Obra criada à mão nunca dispara o gate da Task #200 (não tem proposta
    de origem) e ficaria com `cronograma_revisado_em` NULL para sempre."""
    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=None)
        func = _funcionario(admin)
        r = executar_handoff(obra, func, usuario_id=admin.id)
        db.session.commit()
        db.session.refresh(obra)
        assert r['cronograma_carimbado_no_handoff'] is True
        assert obra.cronograma_revisado_em is not None


# ---------------------------------------------------------------------------
# O que o handoff tem de recusar
# ---------------------------------------------------------------------------

def test_handoff_recusa_funcionario_sem_login():
    """Sem `Usuario` não há a quem atribuir o papel GESTOR — e um handoff que
    não cria vínculo é só um campo preenchido, exatamente o que existia."""
    from services.obra_handoff import HandoffInvalido, executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin, com_login=False)
        with pytest.raises(HandoffInvalido) as exc:
            executar_handoff(obra, func, usuario_id=admin.id)
        assert 'login' in str(exc.value).lower()
        db.session.rollback()
        db.session.refresh(obra)
        assert obra.estado == 'planejamento'
        assert obra.responsavel_id is None


def test_handoff_recusa_funcionario_de_outro_tenant():
    from services.obra_handoff import HandoffInvalido, executar_handoff
    with app.app_context():
        dono = _admin()
        outro = _admin('hob')
        obra = _obra(dono)
        func = _funcionario(outro)
        with pytest.raises(HandoffInvalido) as exc:
            executar_handoff(obra, func, usuario_id=dono.id)
        assert 'tenant' in str(exc.value).lower()
        db.session.rollback()


def test_handoff_recusa_sem_funcionario():
    from services.obra_handoff import HandoffInvalido, executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        with pytest.raises(HandoffInvalido):
            executar_handoff(obra, None, usuario_id=admin.id)
        db.session.rollback()


def test_handoff_de_obra_fora_de_planejamento_e_transicao_invalida():
    """Erro DIFERENTE de HandoffInvalido, de propósito: pré-condição de
    negócio o usuário conserta; estado errado é outra classe de problema."""
    from datetime import datetime

    from services.obra_estado import TransicaoInvalida
    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento',
                     revisado_em=datetime.utcnow())
        func = _funcionario(admin)
        with pytest.raises(TransicaoInvalida):
            executar_handoff(obra, func, usuario_id=admin.id)
        db.session.rollback()


def test_handoff_nao_commita_sozinho():
    """Contrato do repo: quem chama é dono da transação. Um commit aqui
    dentro tornaria impossível desfazer os três efeitos juntos."""
    from datetime import datetime

    from services.obra_handoff import executar_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=datetime.utcnow())
        func = _funcionario(admin)
        obra_id = obra.id
        executar_handoff(obra, func, usuario_id=admin.id)
        db.session.rollback()
        recarregada = db.session.get(Obra, obra_id)
        assert recarregada.estado == 'planejamento'
        assert recarregada.responsavel_id is None
        assert UsuarioObra.query.filter_by(obra_id=obra_id).count() == 0


# ---------------------------------------------------------------------------
# Bloqueios e dossiê — a tela mostra tudo de uma vez
# ---------------------------------------------------------------------------

def test_bloqueios_lista_todos_os_problemas_de_uma_vez():
    """Existe separado de `executar_handoff` para o usuário não descobrir um
    problema por submit."""
    from services.obra_handoff import bloqueios_do_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        func = _funcionario(admin, com_login=False)
        problemas = bloqueios_do_handoff(obra, func)
        assert len(problemas) >= 2, problemas
        junto = ' '.join(problemas).lower()
        assert 'planejamento' in junto
        assert 'login' in junto


def test_bloqueios_vazio_quando_esta_tudo_pronto():
    from datetime import datetime

    from services.obra_handoff import bloqueios_do_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=datetime.utcnow())
        func = _funcionario(admin)
        assert bloqueios_do_handoff(obra, func) == []


def test_dossie_sobrevive_a_obra_sem_proposta_e_sem_cronograma():
    """O dossiê é informativo: derrubá-lo esconderia do usuário justamente a
    tela que explica o que falta."""
    from services.obra_handoff import dossie_handoff
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        d = dossie_handoff(obra)
        assert d['obra']['id'] == obra.id
        assert d['proposta'] is None
        assert d['cronograma']['total_tarefas'] == 0
        assert d['cronograma']['revisado'] is False
        assert isinstance(d['bloqueios'], list)
        assert d['pode_entrar_em_execucao'] is (not d['bloqueios'])


def test_dossie_reusa_o_gate_de_cronograma_em_vez_de_clonar():
    """`_cronograma_pendente` delega a `views.obras`. Um clone escrito antes
    de 27c62bb ainda estaria exigindo template, porque o gate mudou lá."""
    from services import obra_handoff
    import inspect
    fonte = inspect.getsource(obra_handoff._cronograma_pendente)
    assert '_precisa_revisao_cronograma_inicial' in fonte


# ---------------------------------------------------------------------------
# Eventos de catálogo (Task 10 — movida para antes das rotas na execução,
# eliminando os stubs provisórios que o plano previa)
# ---------------------------------------------------------------------------

def test_eventos_novos_estao_na_allowlist_do_webhook():
    from utils.webhook_dispatcher import WEBHOOK_EVENT_ALLOWLIST
    assert 'obra.estado_alterado' in WEBHOOK_EVENT_ALLOWLIST
    assert 'obra.handoff' in WEBHOOK_EVENT_ALLOWLIST


def test_emit_obra_estado_alterado_monta_payload_completo():
    from unittest.mock import patch

    from utils import catalogo_eventos
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='pausada', status='Pausada')
        with patch.object(catalogo_eventos, '_safe_emit') as m:
            catalogo_eventos.emit_obra_estado_alterado(
                obra, admin.id, estado_de='em_execucao',
                estado_para='pausada', motivo='Chuva', usuario_id=admin.id)
        assert m.called
        nome, payload, aid = m.call_args.args
        assert nome == 'obra.estado_alterado'
        assert aid == admin.id
        assert payload['obra_id'] == obra.id
        assert payload['estado_de'] == 'em_execucao'
        assert payload['estado_para'] == 'pausada'
        assert payload['estado_para_rotulo'] == 'Pausada'
        assert payload['motivo'] == 'Chuva'


def test_emit_obra_handoff_monta_payload_com_gp_e_dossie():
    from unittest.mock import patch

    from utils import catalogo_eventos
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        func = _funcionario(admin)
        with patch.object(catalogo_eventos, '_safe_emit') as m:
            catalogo_eventos.emit_obra_handoff(
                obra, admin.id, funcionario=func, usuario_gp_id=1,
                entregue_por_id=admin.id)
        nome, payload, _aid = m.call_args.args
        assert nome == 'obra.handoff'
        assert payload['gerente_projeto']['funcionario_id'] == func.id
        assert payload['gerente_projeto']['nome'] == func.nome
        assert payload['dossie']['obra']['id'] == obra.id


def test_emit_nunca_propaga_excecao():
    """Contrato do catálogo: webhook é best-effort e jamais quebra a
    transação de negócio."""
    from unittest.mock import patch

    from utils import catalogo_eventos
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        with patch('event_manager.EventManager.emit',
                   side_effect=RuntimeError('n8n fora do ar')):
            catalogo_eventos.emit_obra_estado_alterado(
                obra, admin.id, estado_de='planejamento',
                estado_para='em_execucao', motivo='', usuario_id=admin.id)


# ---------------------------------------------------------------------------
# Rotas (Task 8) — o único caminho HTTP de mudança de estado
# ---------------------------------------------------------------------------

def _cliente_logado(user_id):
    """Login por injeção de sessão — padrão do repo. O test_client é criado
    FORA de qualquer app_context aberto (Flask-Login cacheia g._login_user)."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_rota_estado_recusa_transicao_invalida_com_400():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'concluida'}, follow_redirects=False)
    assert r.status_code == 400, f'devolveu {r.status_code}'
    with app.app_context():
        assert db.session.get(Obra, obra_id).estado == 'planejamento'


def test_rota_estado_recusa_falta_de_motivo_com_400():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/estado', data={'estado': 'pausada'})
    assert r.status_code == 400


def test_rota_estado_aplica_transicao_valida():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'pausada', 'motivo': 'Chuva 12 dias'},
               follow_redirects=False)
    assert r.status_code in (302, 303), r.get_data(as_text=True)[:200]
    with app.app_context():
        from models import ObraTransicaoEstado
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'pausada'
        assert o.status == 'Pausada'
        t = ObraTransicaoEstado.query.filter_by(
            obra_id=obra_id, estado_para='pausada').one()
        assert t.motivo == 'Chuva 12 dias'
        assert t.usuario_id == admin_id


def test_rota_estado_de_outro_tenant_devolve_404():
    with app.app_context():
        dono = _admin()
        intruso = _admin('f2z')
        obra = _obra(dono, estado='em_execucao', status='Em andamento')
        obra_id, intruso_id = obra.id, intruso.id
    c = _cliente_logado(intruso_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'pausada', 'motivo': 'x'})
    assert r.status_code == 404


def test_rota_estado_exige_login():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        obra_id = obra.id
    anon = app.test_client()
    r = anon.post(f'/obras/{obra_id}/estado',
                  data={'estado': 'pausada', 'motivo': 'x'},
                  follow_redirects=False)
    assert r.status_code in (302, 401, 403)


def test_rota_estado_recusa_usuario_sem_autoridade_com_403():
    """FUNCIONARIO sem vínculo GESTOR alcança a obra (mesmo tenant) mas não
    transiciona: 403, não 404 — a obra existe para ele."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        suf = _suf()
        comum = Usuario(
            username=f'hfx_{suf}', email=f'hfx_{suf}@test.local',
            nome=f'Comum {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, versao_sistema='v2')
        db.session.add(comum)
        db.session.commit()
        obra_id, comum_id = obra.id, comum.id
    c = _cliente_logado(comum_id)
    r = c.post(f'/obras/{obra_id}/estado',
               data={'estado': 'pausada', 'motivo': 'x'})
    assert r.status_code == 403, f'devolveu {r.status_code}'
    with app.app_context():
        assert db.session.get(Obra, obra_id).estado == 'em_execucao'


def test_rota_handoff_get_devolve_dossie_json():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, revisado_em=None)
        _funcionario(admin)
        obra_id, admin_id = obra.id, admin.id
    c = _cliente_logado(admin_id)
    r = c.get(f'/obras/{obra_id}/handoff',
              headers={'Accept': 'application/json'})
    assert r.status_code == 200
    dados = r.get_json()
    assert dados['obra']['id'] == obra_id
    assert dados['pode_entrar_em_execucao'] is True
    assert isinstance(dados['candidatos'], list)
    assert len(dados['candidatos']) >= 1


def test_rota_handoff_get_nao_oferece_funcionario_sem_login():
    """Filtrar candidatos aqui evita oferecer no select alguém que
    `executar_handoff` vai recusar depois."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        sem_login = _funcionario(admin, com_login=False)
        obra_id, admin_id, sem_login_id = obra.id, admin.id, sem_login.id
    c = _cliente_logado(admin_id)
    dados = _cliente_logado(admin_id).get(
        f'/obras/{obra_id}/handoff',
        headers={'Accept': 'application/json'}).get_json()
    ids = {c['id'] for c in dados['candidatos']}
    assert sem_login_id not in ids


def test_rota_handoff_post_entrega_a_obra():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin)
        obra_id, admin_id, func_id = obra.id, admin.id, func.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/handoff',
               data={'responsavel_id': str(func_id), 'motivo': 'Kickoff'},
               follow_redirects=False)
    assert r.status_code in (302, 303), r.get_data(as_text=True)[:200]
    with app.app_context():
        o = db.session.get(Obra, obra_id)
        assert o.estado == 'em_execucao'
        assert o.responsavel_id == func_id
        assert UsuarioObra.query.filter_by(
            obra_id=obra_id, papel=PapelObra.GESTOR, ativo=True).count() == 1


def test_rota_handoff_post_com_gp_sem_login_devolve_400():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        func = _funcionario(admin, com_login=False)
        obra_id, admin_id, func_id = obra.id, admin.id, func.id
    c = _cliente_logado(admin_id)
    r = c.post(f'/obras/{obra_id}/handoff',
               data={'responsavel_id': str(func_id)})
    assert r.status_code == 400
    with app.app_context():
        assert db.session.get(Obra, obra_id).estado == 'planejamento'
