"""Cadastro rápido de funcionário — reunião de 2026-08-20.

A Ana cadastra e remove gente toda semana ("Fabrício entrou, ficou dois
dias e já saiu"). Exigir CPF na hora do cadastro trava o fluxo: ela não
sabe o CPF de quem acabou de chegar na obra.
"""
import hashlib
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Funcionario
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _suf

pytestmark = pytest.mark.integration


def _cpf_teste() -> str:
    """CPF de teste sem colisão contra o banco compartilhado (nunca
    limpo entre execuções — ver tests/conftest.py).

    Fix round 4 — antes, os CPFs de teste vinham de `admin_id % 100`.
    Como `admin_id` é sequencial e o banco nunca é limpo, o módulo
    reciclava a cada ~100 execuções e colidia com o UNIQUE de
    `Funcionario.cpf` (`funcionario_cpf_key`) — a própria inserção de
    setup do teste, antes de ele exercitar qualquer coisa, IntegrityError.
    Medido: 32/31/31 linhas acumuladas nos prefixos 33333333/44444444/
    55555555 depois de ~10 execuções desta suíte — em torno de 1 em 3
    falhas espúrias por execução, piorando a cada rodada.

    `_suf()` é o mesmo gerador (tempo de alta resolução + uuid) que
    `_ambiente()` usa para as identidades de admin/obra — é por isso que a
    suíte irmã (test_cronograma_versao_service.py e as que importam
    `_ambiente`) não acumula colisão. Aqui ele é hasheado (SHA-1) e
    reduzido para caber no tamanho de um CPF real (11 dígitos, sem
    pontuação — o que a coluna `String(14)` comporta com folga),
    mantendo o dado reconhecível como sintético (nenhum CPF real de 11
    dígitos tem essa origem) e com espaço de colisão de ~10^11 — nada
    comparável ao módulo por 100 que causou o problema.
    """
    n = int(hashlib.sha1(_suf().encode()).hexdigest(), 16) % (10 ** 11)
    return f'{n:011d}'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cadastro-rapido'
    yield


def test_funcionario_pode_nascer_sem_cpf():
    with app.app_context():
        admin, _obra = _ambiente()
        f = Funcionario(codigo=f'RA{admin.id}', nome='Luiz Ajudante',
                        cpf=None, data_admissao=date(2026, 8, 20),
                        admin_id=admin.id, ativo=True)
        db.session.add(f)
        db.session.commit()
        assert f.id is not None
        assert f.cpf is None


def test_dois_funcionarios_sem_cpf_convivem():
    """O UNIQUE da coluna aceita múltiplos NULL no Postgres — se este
    teste quebrar, o índice precisa virar parcial (WHERE cpf IS NOT NULL)."""
    with app.app_context():
        admin, _obra = _ambiente()
        db.session.add(Funcionario(
            codigo=f'R1{admin.id}', nome='Luiz', cpf=None,
            data_admissao=date(2026, 8, 20), admin_id=admin.id, ativo=True))
        db.session.add(Funcionario(
            codigo=f'R2{admin.id}', nome='Fabrício', cpf=None,
            data_admissao=date(2026, 8, 20), admin_id=admin.id, ativo=True))
        db.session.commit()
        assert Funcionario.query.filter_by(
            admin_id=admin.id, cpf=None).count() == 2


# ---------------------------------------------------------------------------
# Rodada 1 de fix — os dois testes acima só provam o modelo/ORM. A tela real
# passa pelo POST /funcionarios (criação) e POST /funcionarios/<id>/editar
# (edição), com um guard de JS na frente (`validateForm()` em
# templates/funcionarios.html) e uma checagem de duplicidade no servidor.
# Nenhum dos dois testes acima bate nessa rota — daí o `_client_como` já
# importado e nunca usado ter sido a pista perdida na rodada anterior.
# ---------------------------------------------------------------------------

def test_post_criar_dois_funcionarios_sem_cpf_convivem_via_rota():
    """POST real em /funcionarios com cpf='' precisa gravar NULL (não '')
    e dois cadastros assim seguidos não podem colidir no UNIQUE."""
    with app.app_context():
        admin, _obra = _ambiente()
        admin_id = admin.id
        c = _client_como(admin_id)

        resp1 = c.post('/funcionarios', data={
            'nome': 'Luiz Rota', 'cpf': '', 'codigo': f'C1{admin_id}',
            'data_admissao': '2026-08-20',
        })
        assert resp1.status_code in (200, 302)

        resp2 = c.post('/funcionarios', data={
            'nome': 'Fabrício Rota', 'cpf': '', 'codigo': f'C2{admin_id}',
            'data_admissao': '2026-08-20',
        })
        assert resp2.status_code in (200, 302)

        f1 = Funcionario.query.filter_by(admin_id=admin_id, codigo=f'C1{admin_id}').first()
        f2 = Funcionario.query.filter_by(admin_id=admin_id, codigo=f'C2{admin_id}').first()
        assert f1 is not None and f2 is not None
        assert f1.cpf is None, f"esperado NULL, veio {f1.cpf!r}"
        assert f2.cpf is None, f"esperado NULL, veio {f2.cpf!r}"


def test_post_editar_limpando_cpf_grava_null_e_preserva_outros_campos():
    """POST real em /funcionarios/<id>/editar limpando o CPF precisa gravar
    NULL (não ''), dois funcionários editados assim não podem colidir no
    UNIQUE, e um campo irmão trocado na mesma submissão precisa persistir —
    é a regressão de perda de dados do Critical 2 (rollback do except
    genérico quando a UniqueViolation de '' == '' estourava)."""
    with app.app_context():
        admin, _obra = _ambiente()
        admin_id = admin.id
        c = _client_como(admin_id)

        f1 = Funcionario(codigo=f'E1{admin_id}', nome='Original Um',
                          cpf=_cpf_teste(),
                          data_admissao=date(2026, 8, 20),
                          admin_id=admin_id, ativo=True)
        f2 = Funcionario(codigo=f'E2{admin_id}', nome='Original Dois',
                          cpf=_cpf_teste(),
                          data_admissao=date(2026, 8, 20),
                          admin_id=admin_id, ativo=True)
        db.session.add_all([f1, f2])
        db.session.commit()
        f1_id, f2_id = f1.id, f2.id

        resp1 = c.post(f'/funcionarios/{f1_id}/editar', data={
            'nome': 'Editado Um', 'cpf': '',
        })
        assert resp1.status_code in (200, 302)

        resp2 = c.post(f'/funcionarios/{f2_id}/editar', data={
            'nome': 'Editado Dois', 'cpf': '',
        })
        assert resp2.status_code in (200, 302)

        db.session.expire_all()
        f1_depois = Funcionario.query.get(f1_id)
        f2_depois = Funcionario.query.get(f2_id)

        assert f1_depois.cpf is None, f"esperado NULL, veio {f1_depois.cpf!r}"
        assert f2_depois.cpf is None, f"esperado NULL, veio {f2_depois.cpf!r}"
        # Prova de que a UniqueViolation não estourou e não fez rollback: o
        # nome trocado na mesma submissão precisa ter sobrevivido.
        assert f1_depois.nome == 'Editado Um'
        assert f2_depois.nome == 'Editado Dois'


# ---------------------------------------------------------------------------
# Fix round 2 — a review encontrou a checagem de duplicidade da edição
# escopada por admin_id, enquanto o UNIQUE de Funcionario.cpf (models.py) é
# global, sem coluna de tenant. Isso reabre o Critical 2 de um jeito mais
# estreito: dois admins diferentes, cada um editando seu próprio
# funcionário, colidem no CPF sem que a checagem veja (ela só olha o
# próprio tenant) — o INSERT/UPDATE segue, o commit estoura
# UniqueViolation, o except genérico faz rollback e perde os outros campos
# da submissão. Os dois testes abaixo cobrem: (1) a exclusão do próprio id
# continua funcionando isoladamente do "or None" (a rodada anterior só
# provou os dois juntos via stash do arquivo inteiro); (2) a checagem
# global rejeita duplicata entre tenants de forma limpa, sem crash e sem
# perder o campo irmão trocado na mesma submissão.
# ---------------------------------------------------------------------------

def test_post_editar_mantendo_cpf_igual_nao_se_autorrejeita():
    """Salvar um funcionário sem trocar o CPF não pode disparar a checagem
    de duplicidade contra ele mesmo — é o que a exclusão `Funcionario.id !=
    funcionario_id` garante. Sem essa cláusula, o bug de perda de dados do
    Critical 2 vira pior ainda: impossível salvar QUALQUER edição de quem
    já tem CPF, mesmo sem mexer nele.

    Fix round 3 — a rerevisão provou por mutação que a versão anterior
    deste teste NÃO isolava essa cláusula: removendo só o `Funcionario.id
    != funcionario_id` da rota, o teste continuava passando (o guard
    disparava mais cedo, `funcionario.cpf` nunca era tocado, então "cpf
    inalterado" valia mesmo no código quebrado; e o nome "persistia" só
    porque o teste e a rota compartilhavam a mesma sessão sem teardown no
    meio). A leitura final agora cruza um limite de sessão de verdade
    (`db.session.remove()` — o mesmo que `teardown_appcontext` do
    Flask-SQLAlchemy chama ao fim de toda requisição real) antes de
    reler o funcionário, para provar contra estado commitado, não contra
    a identity map da própria requisição."""
    with app.app_context():
        admin, _obra = _ambiente()
        admin_id = admin.id
        c = _client_como(admin_id)

        cpf_original = _cpf_teste()
        f = Funcionario(codigo=f'M1{admin_id}', nome='Nome Original',
                         cpf=cpf_original, data_admissao=date(2026, 8, 20),
                         admin_id=admin_id, ativo=True)
        db.session.add(f)
        db.session.commit()
        f_id = f.id

        resp = c.post(f'/funcionarios/{f_id}/editar', data={
            'nome': 'Nome Trocado', 'cpf': cpf_original,
        })
        assert resp.status_code in (200, 302)

        # Cruza um limite de sessão de verdade — ver docstring.
        db.session.remove()
        f_depois = Funcionario.query.get(f_id)
        assert f_depois.cpf == cpf_original, (
            f"a autoexclusão falhou — CPF virou {f_depois.cpf!r}")
        assert f_depois.nome == 'Nome Trocado', (
            "o nome não persistiu — a edição foi rejeitada quando não devia")


def test_post_editar_cpf_duplicado_entre_admins_e_rejeitado_sem_perder_dados():
    """CPF já usado por funcionário de OUTRO admin precisa ser rejeitado
    pela checagem do servidor (caminho amigável — flash específico e
    redirect), não descoberto só no commit via UniqueViolation não
    tratada.

    Fix round 3 — a rerevisão mostrou, cruzando um limite de sessão de
    verdade (`db.session.remove()`, o que `teardown_appcontext` do
    Flask-SQLAlchemy chama ao fim de toda requisição real), que o nome
    trocado na mesma submissão NÃO sobrevivia em produção: antes,
    `funcionario.nome` era atribuído antes do guard de CPF, e como esse
    caminho de rejeição nunca chamava `db.session.commit()`, o teardown
    da requisição real desfazia essa atribuição pendente — só que
    silenciosamente, sem o usuário saber que a troca de nome também
    tinha sumido junto com a rejeição do CPF. O teste anterior não via
    isso porque reaproveitava a mesma sessão da requisição sem nenhum
    teardown no meio.

    A rota agora valida o CPF ANTES de atribuir qualquer campo (inclusive
    `nome`), então a rejeição é atômica de verdade: nada fica pendente
    na sessão para o teardown desfazer, porque nada foi tocado.

    Duas camadas de verificação, porque uma sozinha não distingue a
    ordem certa da errada:
    1. Logo após o POST, ainda dentro da MESMA sessão/app_context (o
       test_client reaproveita o `with app.app_context():` de fora, não
       abre um novo) — `fb` aqui é o MESMO objeto Python que a rota leu
       e mutou via identity map do SQLAlchemy (mesma sessão, mesma PK).
       Se a atribuição de `nome` rodasse antes do guard, `fb.nome` já
       apareceria trocado nesse ponto, mesmo sem nenhum commit — é
       exatamente essa leitura em memória que provou o bug nesta rodada.
       Essa é a camada que realmente distingue a ordem certa da errada.
    2. Depois de um `db.session.remove()` (o que `teardown_appcontext`
       do Flask-SQLAlchemy chama ao fim de toda requisição real),
       relendo do zero — prova o estado commitado de verdade. Sozinha
       essa camada NÃO distingue a ordem: como `db.session.commit()`
       nunca é alcançado no caminho de rejeição em nenhuma das duas
       ordens, o rollback do `remove()` desfaz a atribuição pendente de
       qualquer jeito — foi assim que a mutação nesta rodada (reverter só
       a ordem, sem mexer no guard) passou o teste até eu adicionar a
       camada 1."""
    with app.app_context():
        admin_a, _obra_a = _ambiente()
        admin_b, _obra_b = _ambiente()

        cpf_do_a = _cpf_teste()
        fa = Funcionario(codigo=f'DA{admin_a.id}', nome='Funcionario A',
                          cpf=cpf_do_a, data_admissao=date(2026, 8, 20),
                          admin_id=admin_a.id, ativo=True)
        fb = Funcionario(codigo=f'DB{admin_b.id}', nome='Funcionario B Original',
                          cpf=_cpf_teste(),
                          data_admissao=date(2026, 8, 20),
                          admin_id=admin_b.id, ativo=True)
        db.session.add_all([fa, fb])
        db.session.commit()
        fb_id = fb.id
        cpf_original_b = fb.cpf
        admin_b_id = admin_b.id

        c_b = _client_como(admin_b_id)
        resp = c_b.post(f'/funcionarios/{fb_id}/editar', data={
            'nome': 'Funcionario B Renomeado', 'cpf': cpf_do_a,
        })
        # Caminho amigável (redirect com flash), nunca um 500 de
        # UniqueViolation não tratada.
        assert resp.status_code in (200, 302)

        with c_b.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
        assert any('já está cadastrado' in msg for _cat, msg in flashes), (
            f"esperava flash amigável de duplicidade, veio {flashes!r}")

        # Camada 1 — mesma sessão, mesmo objeto (identity map): prova que
        # `funcionario.nome` nunca chegou a ser atribuído durante esta
        # requisição, não só que a atribuição foi desfeita depois.
        assert fb.nome == 'Funcionario B Original', (
            "nome foi atribuído no objeto ANTES da rejeição — o guard de "
            "CPF não está rodando antes de mutar o funcionário")

        # Camada 2 — cruza um limite de sessão de verdade (ver docstring).
        db.session.remove()
        fb_depois = Funcionario.query.get(fb_id)
        assert fb_depois.cpf == cpf_original_b, (
            f"CPF de outro admin vazou para dentro do tenant B: {fb_depois.cpf!r}")
        assert fb_depois.nome == 'Funcionario B Original', (
            "nome persistiu no banco apesar da edição ter sido rejeitada — "
            "a rejeição não é atômica")


# ---------------------------------------------------------------------------
# Task 2 (reunião 2026-08-20) — ativar/desativar em lote. Hoje são três
# cliques por pessoa (toggleStatusFuncionario → confirm → reload). Para os
# oito e tantos que a Ana precisa desligar de uma vez, isso é "uma porrada
# de cara pra ficar desativando". A confirmação continua existindo — o
# Paulo defendeu o segundo clique —, mas agora é UMA confirmação para o
# lote inteiro.
# ---------------------------------------------------------------------------

def _tres_funcionarios():
    with app.app_context():
        admin, _obra = _ambiente()
        ids = []
        for i, nome in enumerate(('Davi', 'Cristiano', 'Fabrício')):
            f = Funcionario(codigo=f'L{i}{admin.id}', nome=nome, cpf=None,
                            data_admissao=date(2026, 8, 20),
                            admin_id=admin.id, ativo=True)
            db.session.add(f)
            db.session.flush()
            ids.append(f.id)
        db.session.commit()
        # `_client_como` recebe o ID; e o objeto ORM devolvido de dentro do
        # contexto já está destacado quando ele fecha.
        return admin.id, ids


def test_desativar_em_lote():
    admin_id, ids = _tres_funcionarios()
    client = _client_como(admin_id)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': ids[:2], 'ativo': False})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['alterados'] == 2
    with app.app_context():
        assert Funcionario.query.get(ids[0]).ativo is False
        assert Funcionario.query.get(ids[1]).ativo is False
        assert Funcionario.query.get(ids[2]).ativo is True


def test_reativar_em_lote():
    """Fix round 1 — a versão anterior só conferia o estado final
    (`ativo is True`), que também é o estado INICIAL de `_tres_funcionarios`
    (todos nascem `ativo=True`). Isso deixava o teste incapaz de distinguir
    "reativação funcionou" de "nada aconteceu": um stub que devolvesse
    `{'alterados': len(ids)}` sem tocar no banco passava igual, porque o
    primeiro POST (desativar) virava no-op e o segundo (reativar) só
    reencontrava o `True` que já estava lá desde o início.

    Agora o teste pina o estado intermediário — depois do primeiro POST,
    antes do segundo — então uma rota que não persiste nada falha já nessa
    checagem, antes mesmo de chegar na reativação."""
    admin_id, ids = _tres_funcionarios()
    client = _client_como(admin_id)
    client.post('/api/funcionarios/toggle-ativo-lote',
                json={'ids': ids, 'ativo': False})

    # Pina o estado intermediário: se a desativação foi um no-op, isto já
    # falha aqui, antes da reativação ter qualquer chance de "acertar por
    # coincidência" o estado inicial.
    with app.app_context():
        assert all(Funcionario.query.get(i).ativo is False for i in ids)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': ids, 'ativo': True})

    assert resp.get_json()['alterados'] == 3
    with app.app_context():
        assert all(Funcionario.query.get(i).ativo is True for i in ids)


def test_lote_ignora_id_de_outro_tenant():
    """Silencioso de propósito: responder 404 diria a um tenant que o id
    existe em outro."""
    admin_a_id, ids_a = _tres_funcionarios()
    _admin_b_id, ids_b = _tres_funcionarios()
    client = _client_como(admin_a_id)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': [ids_a[0], ids_b[0]], 'ativo': False})

    assert resp.get_json()['alterados'] == 1
    with app.app_context():
        assert Funcionario.query.get(ids_b[0]).ativo is True


def test_lote_nao_conta_quem_ja_estava_no_estado_pedido():
    """Fix round 1 — `alterados` precisa contar só quem de fato mudou de
    estado, não quantos ids vieram na lista. Sem essa distinção, mandar de
    novo um id que já está inativo infla a contagem, e a confirmação
    ("N desativados") passa a mentir sobre o que realmente aconteceu — na
    tela ela é o único registro do que a ação fez.

    Este teste desativa 3 funcionários primeiro e depois manda um lote com
    esses 3 (já inativos) MAIS 2 ainda ativos, pedindo `ativo=False`.
    Só os 2 ainda ativos podem contar. Sem o guard `if f.ativo == ativo:
    continue` na rota, os 5 seriam contados."""
    admin_id, ids_inativos = _tres_funcionarios()
    client = _client_como(admin_id)
    client.post('/api/funcionarios/toggle-ativo-lote',
                json={'ids': ids_inativos, 'ativo': False})
    with app.app_context():
        assert all(Funcionario.query.get(i).ativo is False
                   for i in ids_inativos)

    # Dois funcionários extras do MESMO tenant, ainda ativos — cobre o
    # guard de idempotência dentro do próprio tenant (id fora do tenant já
    # é coberto por test_lote_ignora_id_de_outro_tenant, e por outro
    # motivo: filtro de admin_id, não o guard `if f.ativo == ativo`).
    with app.app_context():
        f_ativo1 = Funcionario(codigo=f'X1{admin_id}', nome='Extra Um',
                               cpf=None, data_admissao=date(2026, 8, 20),
                               admin_id=admin_id, ativo=True)
        f_ativo2 = Funcionario(codigo=f'X2{admin_id}', nome='Extra Dois',
                               cpf=None, data_admissao=date(2026, 8, 20),
                               admin_id=admin_id, ativo=True)
        db.session.add_all([f_ativo1, f_ativo2])
        db.session.commit()
        ids_extra_ativos = [f_ativo1.id, f_ativo2.id]

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': ids_inativos + ids_extra_ativos,
                             'ativo': False})

    assert resp.get_json()['alterados'] == 2, resp.get_data(as_text=True)
    with app.app_context():
        assert all(Funcionario.query.get(i).ativo is False
                   for i in ids_inativos + ids_extra_ativos)


def test_lote_vazio_recusa():
    admin_id, _ids = _tres_funcionarios()
    client = _client_como(admin_id)

    resp = client.post('/api/funcionarios/toggle-ativo-lote',
                       json={'ids': [], 'ativo': False})

    assert resp.status_code == 400
    assert resp.get_json()['success'] is False
