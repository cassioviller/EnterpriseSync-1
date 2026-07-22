"""Fase 0.6 / D5 — a obra salva pelo formulário sumia da listagem.

`Obra.status` é texto livre (`models.py:257`) e o sistema tinha DUAS grafias
do mesmo estado circulando ao mesmo tempo:

- o default do modelo, o contador e o filtro da listagem usavam
  `'Em andamento'` (`models.py:257`, `templates/obras_moderno.html:572,616`,
  `views/obras.py:83` com igualdade exata);
- o `<select>` do formulário de cadastro oferecia `'Em Andamento'`, porque é
  isso que `_SLUG_DEFAULTS['obra_status']` semeia
  (`services/dropdown_service.py:94`) e o que `forms.py:42` traz como default.

Resultado medido em 2026-07-21 no banco de desenvolvimento: **53 obras** com
`'Em Andamento'`. Elas existiam, mas não apareciam na listagem nem no
contador — o usuário salvava a obra e ela sumia da tela.

O `templates/obras.html` chegava a divergir de si mesmo: o botão de filtro
(`:50`) e o `<option>` (`:82`) mandavam `'Em Andamento'`, enquanto o badge
(`:213`) e o `<option>` do modal (`:410`) testavam `'Em andamento'`.

A correção não troca string por string: cria um vocabulário canônico
(`utils/status_obra.py`) e normaliza na ESCRITA, via `@validates` no modelo,
de modo que todo caminho de gravação — formulário, `event_manager.py:1018`,
seeds, importadores — converge para a mesma grafia.
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
from models import Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase06-d5'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'd5_{suf}', email=f'd5_{suf}@test.local',
        nome=f'Admin D5 {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _cliente(admin):
    # Task #176 — Obra.cliente_id é FK NOT NULL.
    c = Cliente(nome=f'Cliente D5 {uuid.uuid4().hex[:8]}', admin_id=admin.id)
    db.session.add(c)
    db.session.commit()
    return c


def _obra(admin, status):
    o = Obra(
        nome=f'Obra D5 {uuid.uuid4().hex[:8]}',
        admin_id=admin.id, status=status, data_inicio=date(2026, 7, 1),
        cliente_id=_cliente(admin).id,
    )
    db.session.add(o)
    db.session.commit()
    return o


# ---------------------------------------------------------------------------
# O vocabulário canônico
# ---------------------------------------------------------------------------

def test_vocabulario_canonico_existe_e_usa_a_grafia_do_modelo():
    """A grafia canônica é a do default do modelo: 'Em andamento'.

    Foi escolhida por ser a que 7.926 das 7.979 obras já usavam em 21/07 —
    corrigir para o outro lado exigiria reescrever o banco inteiro.
    """
    from utils.status_obra import STATUS_OBRA_CANONICOS

    assert 'Em andamento' in STATUS_OBRA_CANONICOS
    assert 'Em Andamento' not in STATUS_OBRA_CANONICOS


@pytest.mark.parametrize('entrada,esperado', [
    ('Em Andamento', 'Em andamento'),   # a grafia do formulário — a causa do D5
    ('Em andamento', 'Em andamento'),   # a canônica passa incólume
    ('EM ANDAMENTO', 'Em andamento'),
    ('  em andamento  ', 'Em andamento'),
    ('Concluida', 'Concluída'),         # sem acento → com acento
    ('CONCLUÍDA', 'Concluída'),
    ('pausada', 'Pausada'),
    ('Cancelada', 'Cancelada'),
])
def test_normalizador_converge_as_variantes(entrada, esperado):
    from utils.status_obra import normalizar_status_obra

    assert normalizar_status_obra(entrada) == esperado


def test_normalizador_nao_engole_valor_desconhecido():
    """Um status fora do vocabulário volta preservado (só com strip).

    Silenciar o desconhecido seria repetir o defeito do
    `services/cronograma_proposta.py:532` — descartar sem avisar.
    """
    from utils.status_obra import normalizar_status_obra

    assert normalizar_status_obra('  Paralisada por chuva ') == 'Paralisada por chuva'
    assert normalizar_status_obra(None) is None
    assert normalizar_status_obra('') == ''


# ---------------------------------------------------------------------------
# A normalização acontece na escrita, para TODO caminho de gravação
# ---------------------------------------------------------------------------

def test_obra_nasce_com_status_canonico_mesmo_recebendo_a_grafia_do_formulario():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, 'Em Andamento')

        db.session.expire(obra)
        assert obra.status == 'Em andamento'


def test_atualizar_status_tambem_normaliza():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, 'Em andamento')

        obra.status = 'CONCLUIDA'
        db.session.commit()
        db.session.expire(obra)
        assert obra.status == 'Concluída'


def test_obra_gravada_com_a_grafia_do_formulario_aparece_no_filtro_da_listagem():
    """O teste de regressão do D5 propriamente dito.

    Antes: `views/obras.py:83` fazia `Obra.status == 'Em andamento'` e a obra
    gravada como `'Em Andamento'` ficava de fora.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, 'Em Andamento')

        encontradas = Obra.query.filter(
            Obra.admin_id == admin.id,
            Obra.status == 'Em andamento',
        ).all()
        assert obra.id in [o.id for o in encontradas]


# ---------------------------------------------------------------------------
# As fontes da grafia divergente
# ---------------------------------------------------------------------------

def test_seed_de_dropdown_usa_a_grafia_canonica():
    """`_SLUG_DEFAULTS` era a origem do 'Em Andamento' no `<select>`.

    Sem isto, todo tenant novo volta a semear a grafia errada.
    """
    from services.dropdown_service import _SLUG_DEFAULTS
    from utils.status_obra import STATUS_OBRA_CANONICOS

    for valor in _SLUG_DEFAULTS['obra_status']:
        assert valor in STATUS_OBRA_CANONICOS, (
            f'{valor!r} não está no vocabulário canônico'
        )


def test_nenhum_template_de_obra_filtra_pela_grafia_errada():
    """Varre os templates que constroem filtro/badge de status de obra.

    `templates/obras.html` divergia de si mesmo: `:50` e `:82` mandavam
    'Em Andamento' para a query string, `:213` e `:410` testavam
    'Em andamento'.
    """
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alvos = [
        'templates/obras.html',
        'templates/obras_safe.html',
        'templates/obras_moderno.html',
        'templates/obra_form.html',
    ]
    ofensores = []
    for rel in alvos:
        caminho = os.path.join(raiz, rel)
        if not os.path.exists(caminho):
            continue
        with open(caminho, encoding='utf-8') as fh:
            for n, linha in enumerate(fh, 1):
                # Só o VALOR importa; o rótulo visível pode ser 'Em Andamento'.
                if "'Em Andamento'" in linha or '"Em Andamento"' in linha:
                    ofensores.append(f'{rel}:{n}')
    assert not ofensores, (
        'grafia não-canônica em valor de status: ' + ', '.join(ofensores)
    )


def test_forms_nao_traz_default_com_grafia_errada():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, 'forms.py'), encoding='utf-8') as fh:
        linhas = fh.readlines()
    # forms.py:42 — ObraForm.status
    assert "default='Em Andamento'" not in ''.join(linhas[:60]), (
        'ObraForm ainda tem default com a grafia não-canônica'
    )
