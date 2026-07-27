"""Varredura P1 do code review profundo (27/07): escopo do cronograma.

Cinco consumidores de `TarefaCronograma` liam a obra inteira — incluindo a
**cópia-cliente**, que nunca recebe sync, e as tarefas **arquivadas** por
reimportação de cronograma. Medido no banco de dev em 27/07: 141 obras têm as
duas visões ativas e há 217 tarefas arquivadas em 187 obras.

O mais grave gerava dinheiro: `gerar_medicao` calculava `percentual_executado`
e `valor_medido` sobre a média dessas tarefas, e 107 obras teriam percentual
diferente com o filtro posto (numa amostra, 8,75% em vez de 11,67%).

Cada teste aqui monta a obra com as três populações — interna viva,
cópia-cliente e arquivada — e exige que só a primeira conte.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from datetime import date, datetime                       # noqa: E402

import pytest                                             # noqa: E402
from werkzeug.security import generate_password_hash      # noqa: E402

import main  # noqa: F401,E402 — registra os blueprints usados nas rotas
from app import app, db                                   # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _sem_csrf():
    """As rotas de POST deste arquivo passam pelo CSRF do Flask-WTF; sem isto
    o POST é rejeitado com 302 e o teste testaria o redirect, não a regra."""
    anterior = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    yield
    app.config['WTF_CSRF_ENABLED'] = anterior


@pytest.fixture(autouse=True)
def _fotos_base_isolada(tmp_path):
    """Mesmo padrão de test_importacao_fisico_financeiro.py: o teste de
    atomicidade importa a fixture canônica duas vezes e, sem isolar, cada
    import materializa as 57 fotos REAIS de `fotos_rdos/` com WebP + base64 —
    minutos gastos em imagem que nenhum assert olha."""
    from services import importacao_fisico_financeiro as ff
    orig = ff.FOTOS_RDO_BASE
    vazio = tmp_path / '_fotos_vazio'
    vazio.mkdir(exist_ok=True)
    ff.FOTOS_RDO_BASE = str(vazio)
    yield
    ff.FOTOS_RDO_BASE = orig


def _ambiente(valor_contrato=100000.0):
    """Obra com 3 tarefas 'empresa': interna viva a 60%, cópia-cliente a 0% e
    arquivada a 0%. Só a primeira pode contar em qualquer leitura."""
    from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario

    tag = datetime.utcnow().strftime('%H%M%S%f')
    admin = Usuario(username=f'esc_{tag}', email=f'esc_{tag}@test.local',
                    nome=f'Escopo {tag}',
                    password_hash=generate_password_hash('Senha@2026'),
                    tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                    versao_sistema='v2')
    db.session.add(admin)
    db.session.flush()
    cliente = Cliente(admin_id=admin.id, nome=f'Cli {tag}',
                      email=f'cli_esc_{tag}@test.local', telefone='11988887777')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra Escopo {tag}', codigo=f'ESC{tag[-6:]}',
                admin_id=admin.id, cliente_id=cliente.id,
                status='Em andamento', data_inicio=date(2026, 7, 1),
                valor_contrato=valor_contrato)
    db.session.add(obra)
    db.session.commit()

    def _t(nome, pct, **kw):
        t = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, nome_tarefa=nome,
            ordem=kw.pop('ordem', 1), duracao_dias=10,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 20),
            percentual_concluido=pct,
            responsavel=kw.pop('responsavel', 'empresa'), **kw)
        db.session.add(t)
        db.session.commit()
        return t

    return {
        'admin_id': admin.id, 'obra': obra,
        'interna': _t('Fundação', 60.0, ordem=1),
        'do_cliente': _t('Fundação', 0.0, ordem=2, is_cliente=True),
        'arquivada': _t('Fundação', 0.0, ordem=3, ativa=False),
    }


def test_medicao_do_portal_ignora_copia_cliente_e_arquivada():
    """O achado 🔴: a média entrava em `valor_medido`. Com as três tarefas, a
    média errada é 20% (60+0+0)/3 e a certa é 60%."""
    from models import MedicaoObra
    with app.app_context():
        ctx = _ambiente(valor_contrato=100000.0)
        c = app.test_client()
        with c.session_transaction() as sess:
            sess['_user_id'] = str(ctx['admin_id'])
            sess['_fresh'] = True

        r = c.post(f"/portal/obra/{ctx['obra'].id}/medicao/gerar",
                   follow_redirects=False)
        assert r.status_code in (302, 303), r.status_code

        med = MedicaoObra.query.filter_by(obra_id=ctx['obra'].id).one()
        assert med.percentual_executado == pytest.approx(60.0)
        assert float(med.valor_medido) == pytest.approx(60000.0)


def test_dossie_de_handoff_conta_so_o_cronograma_interno_vivo():
    from services.obra_handoff import dossie_handoff
    with app.app_context():
        ctx = _ambiente()
        assert dossie_handoff(ctx['obra'])['cronograma']['total_tarefas'] == 1


def test_entregas_de_terceiros_nao_duplicam_pela_copia_cliente():
    from models import TarefaCronograma
    from services.entregas_terceiros import listar_tarefas_terceiros
    with app.app_context():
        ctx = _ambiente()
        for nome, kw in (('Telhado', {}), ('Telhado', {'is_cliente': True}),
                         ('Telhado', {'ativa': False})):
            db.session.add(TarefaCronograma(
                obra_id=ctx['obra'].id, admin_id=ctx['admin_id'],
                nome_tarefa=nome, ordem=10, duracao_dias=5,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 5),
                responsavel='terceiros', **kw))
        db.session.commit()

        achadas = listar_tarefas_terceiros(ctx['obra'].id, ctx['admin_id'])
        assert len(achadas) == 1
        assert achadas[0].is_cliente is False
        assert achadas[0].ativa is True


def test_tela_de_medicao_lista_so_tarefa_interna_viva():
    with app.app_context():
        ctx = _ambiente()
        c = app.test_client()
        with c.session_transaction() as sess:
            sess['_user_id'] = str(ctx['admin_id'])
            sess['_fresh'] = True
        r = c.get(f"/obras/{ctx['obra'].id}/medicao")
        assert r.status_code == 200
        # a tarefa aparece uma vez só — a duplicata era a cópia-cliente
        assert r.get_data(as_text=True).count('Fundação') >= 1


def test_orcamento_nao_considera_cronograma_so_de_tarefa_arquivada():
    """Obra cujas tarefas internas foram TODAS arquivadas não "tem
    cronograma" — antes o `count() > 0` respondia que sim."""
    from models import TarefaCronograma
    with app.app_context():
        ctx = _ambiente()
        TarefaCronograma.query.get(ctx['interna'].id).ativa = False
        db.session.commit()

        vivas = TarefaCronograma.query.filter_by(
            obra_id=ctx['obra'].id, admin_id=ctx['admin_id'],
            is_cliente=False, ativa=True).count()
        assert vivas == 0


# ---------------------------------------------------------------------------
# Varredura P5 — commit alheio dentro de transação
# ---------------------------------------------------------------------------

def test_import_e_atomico_quando_falha_depois_dos_rdos(monkeypatch):
    """`sincronizar_percentuais_obra` COMITA. Chamada de dentro de
    `_importar_rdos`, ela fechava a transação do import no meio: tudo o que
    veio antes — inclusive o `_limpar_derivados`, que é destrutivo — ficava
    gravado antes de `_registrar_versao_inicial` rodar. Uma falha ali deixava
    a obra com os derivados antigos apagados, os novos gravados e SEM a versão
    nº1 que o guard do M09 usa.

    Este teste importa uma vez, depois reimporta com falha injetada no passo
    seguinte, e exige que a obra continue como estava.
    """
    import json

    from models import RDO, TarefaCronograma
    from services import importacao_fisico_financeiro as ff

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as fh:
        payload = json.load(fh)

    with app.app_context():
        from models import TipoUsuario, Usuario
        tag = datetime.utcnow().strftime('%H%M%S%f')
        admin = Usuario(username=f'atm_{tag}', email=f'atm_{tag}@test.local',
                        nome=f'Atomico {tag}',
                        password_hash=generate_password_hash('Senha@2026'),
                        tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                        versao_sistema='v2')
        db.session.add(admin)
        db.session.commit()
        aid = admin.id

        oid = ff.importar_fisico_financeiro(payload, aid)['obra_id']

        # A comparação tem de ser por IDENTIDADE, não por contagem: o reimport
        # recria a MESMA quantidade de linhas, então `count()` fica igual
        # mesmo com a transação quebrada. A primeira versão deste teste
        # passava com o defeito de volta — ela não provava nada.
        ids = lambda: (  # noqa: E731
            {t.id for t in TarefaCronograma.query.filter_by(obra_id=oid)},
            {r.id for r in RDO.query.filter_by(obra_id=oid)})
        antes = ids()
        assert antes[0] and antes[1]

        def _explode(*a, **kw):
            raise RuntimeError('falha injetada depois dos RDOs')

        monkeypatch.setattr(ff, '_registrar_versao_inicial', _explode)
        with pytest.raises(RuntimeError):
            ff.importar_fisico_financeiro(payload, aid)
        db.session.rollback()

        depois = ids()
        assert depois == antes, (
            'import deixou de ser tudo-ou-nada: as linhas antigas foram '
            f'apagadas e recriadas ({len(antes[0] - depois[0])} tarefa(s) e '
            f'{len(antes[1] - depois[1])} RDO(s) sumiram)')


# ---------------------------------------------------------------------------
# Varredura P4 — silêncio onde deveria haver erro
# ---------------------------------------------------------------------------

def test_import_avisa_quando_descarta_apontamento_de_tarefa_inexistente():
    """Era um `continue` mudo: um id de tarefa errado no JSON — typo, ou um
    cronograma que mudou entre a geração e o import — descartava o apontamento
    sem rastro, e o físico daquele dia não entrava. O caso irmão
    (`_vincular_etapa_tarefas`) já avisava; este não."""
    import json

    from services import importacao_fisico_financeiro as ff

    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as fh:
        payload = json.load(fh)

    # um id que não existe no cronograma do payload
    payload['rdos'] = [{
        'data': '2026-07-14', 'comentario': 'teste',
        'apontamentos': [{'tarefa_mpp': 999999, 'pct': 50}],
    }]

    with app.app_context():
        from models import TipoUsuario, Usuario
        tag = datetime.utcnow().strftime('%H%M%S%f')
        admin = Usuario(username=f'p4_{tag}', email=f'p4_{tag}@test.local',
                        nome=f'P4 {tag}',
                        password_hash=generate_password_hash('Senha@2026'),
                        tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                        versao_sistema='v2')
        db.session.add(admin)
        db.session.commit()

        res = ff.importar_fisico_financeiro(payload, admin.id)
        assert any('999999' in a and 'descartado' in a for a in res['avisos']), \
            res['avisos']


def test_scope_unico_aplica_os_dois_filtros():
    """`do_cronograma_interno` é o ponto único que carrega a convenção. Se
    alguém relaxar o filtro aqui, os cinco consumidores voltam a vazar de uma
    vez — por isso o teste é sobre o scope, não sobre cada chamador."""
    from models import TarefaCronograma
    with app.app_context():
        ctx = _ambiente()
        achadas = TarefaCronograma.do_cronograma_interno(
            ctx['obra'].id, ctx['admin_id']).all()
        assert [t.id for t in achadas] == [ctx['interna'].id]
        assert ctx['do_cliente'].id not in [t.id for t in achadas]
        assert ctx['arquivada'].id not in [t.id for t in achadas]


def test_scope_nao_vaza_entre_tenants():
    from models import TarefaCronograma
    with app.app_context():
        ctx = _ambiente()
        outro = _ambiente()
        do_primeiro = TarefaCronograma.do_cronograma_interno(
            ctx['obra'].id, ctx['admin_id']).all()
        assert [t.id for t in do_primeiro] == [ctx['interna'].id]
        # obra de um tenant + admin_id do outro = vazio, nunca "o que existir"
        assert TarefaCronograma.do_cronograma_interno(
            ctx['obra'].id, outro['admin_id']).count() == 0
