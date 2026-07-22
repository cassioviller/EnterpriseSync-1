"""Fase 2 — máquina de estados da Obra.

Antes desta fase `Obra.status` era `db.Column(db.String(20),
default='Em andamento')` (models.py:297): texto livre, alimentado por um
dropdown editável pelo tenant (`services/dropdown_service.py:94`), sem
transição validada e sem histórico. A Fase 0.6 / D5 já atacou metade do problema: `utils/status_obra.py`
canonizou a grafia (`'Em Andamento'` → `'Em andamento'`, migration 217) e
o `@validates('status')` de `models.py:415` impede que ela volte. O que a
Fase 2 acrescenta é o que falta: transição validada, histórico de quem
mudou o quê e por quê, e um vocabulário FECHADO — hoje `status` continua
aceitando qualquer texto que o tenant digite no dropdown.

`Obra.ativo` é um segundo eixo, paralelo e nunca sincronizado com
`status`: a UI chama `ativo=False` de "Concluída / Inativa"
(`templates/obras_moderno.html:803`) sem que nada garanta a correspondência.

Estes testes travam o vocabulário fechado e o grafo. Lógica pura — nenhum
toca o banco.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db  # noqa: F401

pytestmark = pytest.mark.integration


def test_enum_tem_exatamente_os_cinco_estados():
    from models import EstadoObra
    assert {e.value for e in EstadoObra} == {
        'planejamento', 'em_execucao', 'pausada', 'concluida', 'cancelada',
    }


def test_rotulo_de_cada_estado_e_o_texto_legado():
    """Os rótulos precisam ser exatamente o que `Obra.status` já grava —
    é o que permite manter as ~40 leituras de status funcionando."""
    from models import EstadoObra
    from services.obra_estado import ROTULOS
    assert ROTULOS[EstadoObra.EM_EXECUCAO] == 'Em andamento'
    assert ROTULOS[EstadoObra.CONCLUIDA] == 'Concluída'
    assert ROTULOS[EstadoObra.PAUSADA] == 'Pausada'
    assert ROTULOS[EstadoObra.CANCELADA] == 'Cancelada'
    assert ROTULOS[EstadoObra.PLANEJAMENTO] == 'Planejamento'
    assert set(ROTULOS) == set(EstadoObra)


def test_rotulo_cabe_na_coluna_legada():
    """`Obra.status` é String(20) — um rótulo maior seria truncado pelo
    write-through e quebraria o filtro de igualdade exata."""
    from services.obra_estado import ROTULOS
    for estado, rotulo in ROTULOS.items():
        assert len(rotulo) <= 20, f'{estado}: rótulo {rotulo!r} não cabe'


def test_grafo_cobre_todos_os_estados():
    from models import EstadoObra
    from services.obra_estado import TRANSICOES
    assert set(TRANSICOES) == set(EstadoObra)


def test_cancelada_e_terminal():
    from models import EstadoObra
    from services.obra_estado import transicoes_possiveis
    assert transicoes_possiveis(EstadoObra.CANCELADA) == ()


def test_planejamento_so_vai_para_execucao_ou_cancelada():
    from models import EstadoObra
    from services.obra_estado import transicoes_possiveis
    assert set(transicoes_possiveis(EstadoObra.PLANEJAMENTO)) == {
        EstadoObra.EM_EXECUCAO, EstadoObra.CANCELADA,
    }


def test_pode_transitar_recusa_salto_invalido():
    from models import EstadoObra
    from services.obra_estado import pode_transitar
    # Pular o handoff: planejamento não conclui obra.
    assert pode_transitar(EstadoObra.PLANEJAMENTO, EstadoObra.CONCLUIDA) is False
    assert pode_transitar(EstadoObra.PLANEJAMENTO, EstadoObra.PAUSADA) is False
    assert pode_transitar(EstadoObra.CANCELADA, EstadoObra.EM_EXECUCAO) is False
    assert pode_transitar(EstadoObra.EM_EXECUCAO, EstadoObra.CONCLUIDA) is True


def test_nenhuma_transicao_aponta_para_o_proprio_estado():
    from services.obra_estado import TRANSICOES
    for origem, destinos in TRANSICOES.items():
        assert origem not in destinos, f'{origem} transita para si mesma'


def test_coagir_aceita_str_value_nome_e_enum():
    from models import EstadoObra
    from services.obra_estado import coagir
    assert coagir('em_execucao') is EstadoObra.EM_EXECUCAO
    assert coagir('EM_EXECUCAO') is EstadoObra.EM_EXECUCAO
    assert coagir(EstadoObra.EM_EXECUCAO) is EstadoObra.EM_EXECUCAO


def test_coagir_recusa_lixo():
    from services.obra_estado import EstadoDesconhecido, coagir
    with pytest.raises(EstadoDesconhecido):
        coagir('em execução')
    with pytest.raises(EstadoDesconhecido):
        coagir(None)


def test_coagir_recusa_rotulo_humano():
    """Rótulo é saída, não entrada. Aceitá-lo abriria uma segunda porta de
    escrita com o vocabulário que a fase está justamente fechando."""
    from services.obra_estado import EstadoDesconhecido, coagir
    with pytest.raises(EstadoDesconhecido):
        coagir('Em andamento')


def test_estado_do_status_legado_mapeia_as_grafias_do_censo():
    """As grafias que existem no banco e no código caem no lugar certo."""
    from models import EstadoObra
    from services.obra_estado import estado_do_status_legado
    assert estado_do_status_legado('Em andamento') is EstadoObra.EM_EXECUCAO
    assert estado_do_status_legado('Em Andamento') is EstadoObra.EM_EXECUCAO
    assert estado_do_status_legado('Concluída') is EstadoObra.CONCLUIDA
    # Sem acento e em caixa alta — grafias plausíveis num tenant customizado.
    assert estado_do_status_legado('CONCLUIDA') is EstadoObra.CONCLUIDA
    assert estado_do_status_legado('pausado') is EstadoObra.PAUSADA
    assert estado_do_status_legado('Planejamento') is EstadoObra.PLANEJAMENTO
    # Valor customizado desconhecido não explode: cai em None, e quem chama decide.
    assert estado_do_status_legado('Aguardando ART') is None
    assert estado_do_status_legado(None) is None


def test_todo_estado_e_alcancavel_pelo_mapa_legado():
    """Se um estado não tem nenhuma grafia legada que o produza, o backfill
    da migration 231 nunca conseguiria chegar nele."""
    from models import EstadoObra
    from services.obra_estado import _MAPA_LEGADO
    assert set(_MAPA_LEGADO.values()) == set(EstadoObra)


def test_rotulo_de_volta_para_o_proprio_estado():
    """Ida e volta: o texto que o write-through grava em `Obra.status` tem
    que ser relido como o mesmo estado, senão a migration 232 (normalizar
    legado) e o backfill divergiriam."""
    from models import EstadoObra
    from services.obra_estado import ROTULOS, estado_do_status_legado
    for estado in EstadoObra:
        assert estado_do_status_legado(ROTULOS[estado]) is estado


def test_estados_inativos_sao_os_terminais_de_negocio():
    from models import EstadoObra
    from services.obra_estado import ESTADOS_INATIVOS
    assert ESTADOS_INATIVOS == {EstadoObra.CONCLUIDA, EstadoObra.CANCELADA}


def test_toda_transicao_do_grafo_tem_autoridade_declarada():
    """Uma transição sem entrada em AUTORIDADE cairia no default 'admin'
    silenciosamente — o grafo e a tabela de autoridade têm que casar."""
    from services.obra_estado import AUTORIDADE, TRANSICOES
    pares = {(o, d) for o, destinos in TRANSICOES.items() for d in destinos}
    assert pares == set(AUTORIDADE), (
        f'sem autoridade: {pares - set(AUTORIDADE)}; '
        f'sobrando: {set(AUTORIDADE) - pares}')


def test_toda_transicao_que_exige_motivo_existe_no_grafo():
    from services.obra_estado import TRANSICOES, TRANSICOES_QUE_EXIGEM_MOTIVO
    pares = {(o, d) for o, destinos in TRANSICOES.items() for d in destinos}
    assert TRANSICOES_QUE_EXIGEM_MOTIVO <= pares


def test_normalizacao_e_compartilhada_com_utils_status_obra():
    """Achado A da revisão de 22/07: `utils/status_obra.py` já existia e se
    declara "a única fonte da verdade do vocabulário" de `Obra.status`.

    Uma cópia local de `_chave` dentro de `obra_estado` seria a TERCEIRA
    implementação da mesma normalização e poderia divergir em silêncio do
    vocabulário que deveria espelhar. Este teste trava a identidade — não a
    equivalência — para que a duplicação não volte por descuido.
    """
    from utils.status_obra import chave_status
    from services import obra_estado
    assert obra_estado._sem_acento is chave_status


def test_planejamento_entrou_no_vocabulario_canonico():
    """A Fase 2 faz a obra NASCER em PLANEJAMENTO e o write-through grava o
    rótulo em `Obra.status`. Fora de STATUS_OBRA_CANONICOS, o estado inicial
    de toda obra nova seria não-canônico para o módulo que governa o
    vocabulário."""
    from services.obra_estado import ROTULOS
    from models import EstadoObra
    from utils.status_obra import STATUS_OBRA_CANONICOS, eh_status_canonico
    assert 'Planejamento' in STATUS_OBRA_CANONICOS
    for estado in EstadoObra:
        assert eh_status_canonico(ROTULOS[estado]), (
            f'{estado}: rótulo {ROTULOS[estado]!r} fora do vocabulário canônico')


def test_rotulo_sobrevive_ao_validates_de_status():
    """`models.Obra` tem `@validates('status')` (models.py:415) que passa todo
    valor por `normalizar_status_obra`. O write-through desta fase escreve
    ROTULOS[estado] nesse campo — se o validador reescrevesse o texto, o
    espelho divergiria do estado sem ninguém notar."""
    from services.obra_estado import ROTULOS
    from models import EstadoObra
    from utils.status_obra import normalizar_status_obra
    for estado in EstadoObra:
        rotulo = ROTULOS[estado]
        assert normalizar_status_obra(rotulo) == rotulo, (
            f'{estado}: @validates reescreveria {rotulo!r} como '
            f'{normalizar_status_obra(rotulo)!r}')


# ---------------------------------------------------------------------------
# Task 2 — tabela de histórico `obra_transicao_estado`
# ---------------------------------------------------------------------------
# `Obra.cliente_id` é NOT NULL, então todo cenário cria Cliente antes.
# A fixture NÃO passa `estado=` por default (achado E da revisão de 22/07):
# a coluna só nasce na Task 3, e a versão original do plano tornava esta task
# não verificável isoladamente.
import uuid
from datetime import date

from werkzeug.security import generate_password_hash


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase2-estados'
    yield


def _admin(prefixo='f2a'):
    from models import TipoUsuario, Usuario
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin, estado=None, status='Planejamento', ativo=True):
    from models import Cliente, Obra
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    kwargs = {'estado': estado} if estado is not None else {}
    o = Obra(
        nome=f'Obra {suf}', codigo=f'F2{suf[:6].upper()}',
        cliente_id=cli.id, data_inicio=date(2026, 7, 1),
        status=status, ativo=ativo, admin_id=admin.id, **kwargs,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_tabela_de_historico_existe_e_grava():
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        reg = ObraTransicaoEstado(
            obra_id=obra.id, admin_id=admin.id,
            estado_de='planejamento', estado_para='em_execucao',
            motivo='teste', detalhes={'origem': 'pytest'},
            usuario_id=admin.id,
        )
        db.session.add(reg)
        db.session.commit()
        lido = db.session.get(ObraTransicaoEstado, reg.id)
        assert lido.estado_de == 'planejamento'
        assert lido.estado_para == 'em_execucao'
        assert lido.detalhes == {'origem': 'pytest'}
        assert lido.usuario_id == admin.id
        assert lido.criado_em is not None


def test_historico_e_acessivel_pela_obra_em_ordem_cronologica():
    with app.app_context():
        from models import ObraTransicaoEstado
        admin = _admin()
        obra = _obra(admin)
        for de, para in (('planejamento', 'em_execucao'),
                         ('em_execucao', 'pausada')):
            db.session.add(ObraTransicaoEstado(
                obra_id=obra.id, admin_id=admin.id,
                estado_de=de, estado_para=para, usuario_id=admin.id))
        db.session.commit()
        db.session.refresh(obra)
        assert [t.estado_para for t in obra.transicoes] == [
            'em_execucao', 'pausada']


def test_estado_de_aceita_null_para_a_linha_de_backfill():
    """A linha que a migration 231 escreve não tem origem — é o nascimento
    do estado, não uma transição. `estado_de` NULL é o que a distingue."""
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        db.session.add(ObraTransicaoEstado(
            obra_id=obra.id, admin_id=admin.id,
            estado_de=None, estado_para='em_execucao',
            motivo='backfill — status legado=Em andamento | ativo=true'))
        db.session.commit()
        linha = ObraTransicaoEstado.query.filter_by(
            obra_id=obra.id, estado_de=None).one()
        assert linha.usuario_id is None, 'migração não tem usuário'


def test_apagar_obra_leva_o_historico_junto():
    """FK com ON DELETE CASCADE: histórico órfão apontaria para obra que
    não existe mais e quebraria qualquer relatório que faça join."""
    from models import Obra, ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        db.session.add(ObraTransicaoEstado(
            obra_id=obra.id, admin_id=admin.id,
            estado_de=None, estado_para='planejamento'))
        db.session.commit()
        obra_id = obra.id
        db.session.delete(db.session.get(Obra, obra_id))
        db.session.commit()
        assert ObraTransicaoEstado.query.filter_by(obra_id=obra_id).count() == 0


def test_migration_230_e_idempotente():
    from migrations import migration_230_obra_transicao_estado
    with app.app_context():
        migration_230_obra_transicao_estado()
        migration_230_obra_transicao_estado()


def test_migration_230_garante_os_indices():
    """`create_all` roda ANTES das migrações (app.py:595 vs :703), então o
    CREATE TABLE da 230 é no-op numa base onde o modelo já foi importado —
    e os índices declarados só no DDL nunca nasceriam. Por isso são criados
    separadamente, e é isso que este teste trava."""
    from migrations import migration_230_obra_transicao_estado
    with app.app_context():
        migration_230_obra_transicao_estado()
        nomes = {r[0] for r in db.session.execute(db.text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'obra_transicao_estado'"))}
        assert 'ix_obra_transicao_obra_criado' in nomes, nomes


# ---------------------------------------------------------------------------
# Task 3 — coluna `Obra.estado` + migration 231 (backfill)
# ---------------------------------------------------------------------------

def test_coluna_estado_existe_com_default_planejamento():
    """Obra criada sem informar `estado` nasce em PLANEJAMENTO — decisão 4
    da Fase 2: não existe obra em execução sem GP."""
    from models import Cliente, Obra
    with app.app_context():
        admin = _admin()
        suf = uuid.uuid4().hex[:8]
        cli = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cli)
        db.session.flush()
        o = Obra(nome=f'Obra {suf}', codigo=f'F2D{suf[:5].upper()}',
                 cliente_id=cli.id, data_inicio=date(2026, 7, 1),
                 admin_id=admin.id)
        db.session.add(o)
        db.session.commit()
        assert o.estado == 'planejamento'


def test_check_constraint_recusa_estado_fora_do_vocabulario():
    from sqlalchemy.exc import DatabaseError
    with app.app_context():
        admin = _admin()
        obra = _obra(admin)
        with pytest.raises(DatabaseError):
            db.session.execute(
                db.text('UPDATE obra SET estado = :e WHERE id = :i'),
                {'e': 'inventado', 'i': obra.id})
            db.session.commit()
        db.session.rollback()


def test_derivacao_sql_cobre_a_matriz_de_status_e_ativo():
    """A regra de derivação da 231, sobre todas as combinações que importam.

    NÃO usa `UPDATE obra SET estado = NULL` para simular a base
    pré-migração, como o plano propunha: depois que a 231 roda, a coluna é
    NOT NULL e aquele teste passaria uma única vez na vida do banco. A regra
    foi extraída para `migrations._CASE_DERIVA_ESTADO_OBRA` e é exercida aqui
    sobre um VALUES — repetível, e sem tocar em nenhuma obra real.
    """
    from migrations import _CASE_DERIVA_ESTADO_OBRA
    matriz = [
        ('Em andamento', True, 'em_execucao'),
        ('Em andamento', False, 'concluida'),    # ativo vence status
        ('Em Andamento', True, 'em_execucao'),   # caixa
        ('Concluída', True, 'concluida'),
        ('Concluída', False, 'concluida'),
        ('CONCLUIDA', True, 'concluida'),        # sem acento, caixa alta
        ('Pausada', True, 'pausada'),
        ('Pausada', False, 'concluida'),         # ativo vence status
        ('Cancelada', True, 'cancelada'),        # cancelada vence ativo=true
        ('Cancelada', False, 'cancelada'),
        ('Planejamento', True, 'planejamento'),
        ('Aguardando ART', True, 'em_execucao'), # customizado desconhecido
        ('Aguardando ART', False, 'concluida'),
        (None, True, 'em_execucao'),             # status NULL
    ]
    expr = _CASE_DERIVA_ESTADO_OBRA.format(status='t.status', ativo='t.ativo')
    with app.app_context():
        for status, ativo, esperado in matriz:
            obtido = db.session.execute(
                db.text(f'SELECT {expr} FROM (SELECT CAST(:s AS text) AS status, '
                        f'CAST(:a AS boolean) AS ativo) AS t'),
                {'s': status, 'a': ativo}).scalar()
            assert obtido == esperado, (
                f'status={status!r} ativo={ativo} → {obtido!r}, '
                f'esperado {esperado!r}')


def test_derivacao_sql_e_python_concordam():
    """Achado D da revisão de 22/07: a regra vive em SQL (a 231) e em Python
    (`estado_atual`, Task 4 — fallback de runtime para obra sem estado).

    Duas implementações da mesma regra divergem. Divergiam justamente em
    `status='Em andamento'` + `ativo=False`: o SQL diz 'concluida' porque
    `ativo` vence, e a versão original do Python consultava `status` primeiro.
    Este teste compara as duas sobre a mesma matriz; enquanto `estado_atual`
    não existe (Task 4), ele documenta o contrato que ela terá de cumprir.
    """
    from migrations import _CASE_DERIVA_ESTADO_OBRA
    try:
        from services.obra_estado import estado_atual
    except ImportError:
        pytest.skip('estado_atual chega na Task 4 — contrato já travado acima')

    class _ObraFalsa:
        def __init__(self, status, ativo):
            self.estado, self.status, self.ativo = None, status, ativo

    expr = _CASE_DERIVA_ESTADO_OBRA.format(status='t.status', ativo='t.ativo')
    casos = [('Em andamento', True), ('Em andamento', False),
             ('Concluída', True), ('Pausada', False), ('Cancelada', True),
             ('Planejamento', True), ('Aguardando ART', False), (None, True)]
    with app.app_context():
        for status, ativo in casos:
            do_sql = db.session.execute(
                db.text(f'SELECT {expr} FROM (SELECT CAST(:s AS text) AS status, '
                        f'CAST(:a AS boolean) AS ativo) AS t'),
                {'s': status, 'a': ativo}).scalar()
            do_python = estado_atual(_ObraFalsa(status, ativo)).value
            assert do_sql == do_python, (
                f'status={status!r} ativo={ativo}: SQL diz {do_sql!r}, '
                f'Python diz {do_python!r} — a regra divergiu de si mesma')


def test_backfill_231_grava_historico_com_o_legado_verbatim():
    """A linha de backfill precisa carregar `status` e `ativo` originais —
    é o que torna a migration 232 reversível a partir do próprio banco."""
    from migrations import migration_231_obra_estado
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='concluida', status='Em andamento',
                     ativo=False)
        migration_231_obra_estado()
        linha = ObraTransicaoEstado.query.filter_by(
            obra_id=obra.id, estado_de=None).one()
        assert linha.estado_para == 'concluida'
        assert 'Em andamento' in linha.motivo
        assert 'ativo=false' in linha.motivo
        assert linha.usuario_id is None


def test_backfill_231_e_idempotente():
    from migrations import migration_231_obra_estado
    from models import ObraTransicaoEstado
    with app.app_context():
        admin = _admin()
        obra = _obra(admin, estado='em_execucao', status='Em andamento')
        migration_231_obra_estado()
        n1 = ObraTransicaoEstado.query.filter_by(obra_id=obra.id).count()
        migration_231_obra_estado()
        n2 = ObraTransicaoEstado.query.filter_by(obra_id=obra.id).count()
        assert n1 == n2, 'reexecutar a 231 duplicou histórico'
        db.session.refresh(obra)
        assert obra.estado == 'em_execucao'


def test_backfill_231_nao_deixa_nenhuma_obra_sem_estado():
    from migrations import migration_231_obra_estado
    from models import Obra
    with app.app_context():
        migration_231_obra_estado()
        orfas = db.session.query(Obra.id).filter(Obra.estado.is_(None)).count()
        assert orfas == 0

