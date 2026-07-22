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
