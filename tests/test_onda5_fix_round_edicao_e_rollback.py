"""Onda 5 — fix round do code review de 28/08.

Os três defeitos que o gate verde de 2839 não viu, todos introduzidos pela
própria onda (`ce331094` e `ed85d117`). A regra desta rodada é a mesma da
onda, levada a sério: **o que se afirma é olhado NO BANCO**.

Os testes que a onda escreveu para estas duas linhas provam por
`inspect.getsource()` — verificam que a palavra `rollback` aparece no corpo
do `except`, não que o rollback faça a coisa certa. Foi assim que passaram
verdes por cima dos defeitos. Aqui nenhum teste olha o texto do código.
"""
import os
import sys
import uuid
from datetime import date
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda5-fix-round'
    yield


def _marca():
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Defeito 1 — `services/entregas_terceiros.py:366`
# ---------------------------------------------------------------------------

def test_falha_nas_entregas_nao_descarta_a_transacao_do_chamador():
    """🔴 O `except` faz `db.session.rollback()`, que é da SESSÃO INTEIRA.

    A docstring da função promete "NAO faz commit (chamador commita)", e os
    três chamadores (`views/rdo.py:3487`, `:4497`,
    `rdo_editar_sistema.py:503`) chamam no meio da transação — em
    `views/rdo.py` o `db.session.commit()` está SEIS linhas abaixo. Como a
    função engole a exceção e devolve `(0, 0)`, o `except` do chamador nunca
    dispara: o rollback apaga o RDO inteiro que o chamador acabou de montar,
    o commit seguinte persiste uma sessão vazia e o usuário lê "salvo com
    sucesso".

    O que o serviço pode desfazer é o que ELE mutou, e nada além disso.
    """
    from models import TarefaCronograma
    from services.entregas_terceiros import aplicar_entregas_no_rdo

    with app.app_context():
        t = um_tenant('ent-rollback', com_fatos=False)

        # O que o CHAMADOR já pôs na sessão antes de chamar o serviço.
        marca_chamador = _marca()
        pendente_do_chamador = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'trabalho-do-chamador-{marca_chamador}',
            ordem=0, responsavel='propria', duracao_dias=3,
            percentual_concluido=0.0)
        db.session.add(pendente_do_chamador)
        db.session.flush()

        # E o que o serviço vai mutar antes de quebrar.
        alvo = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'sub-terceiro-{marca_chamador}',
            ordem=1, responsavel='terceiros', duracao_dias=5,
            percentual_concluido=0.0)
        db.session.add(alvo)
        db.session.flush()
        alvo_id = alvo.id

        # `rdo` sem `obra_id`: o laço levanta AttributeError DEPOIS de já ter
        # mutado `alvo`. É o formato de falha que o `except` existe para
        # tratar.
        rdo_quebrado = SimpleNamespace(data_relatorio=date(2026, 8, 20))
        qtd, revertidas = aplicar_entregas_no_rdo(
            rdo_quebrado, {'entrega_tarefa_ids[]': [str(alvo_id)]},
            admin_id=t.admin_id)

        assert (qtd, revertidas) == (0, 0), 'a falha deve reportar nada aplicado'

        # O chamador commita, como sempre faz.
        db.session.commit()

        sobreviveu = TarefaCronograma.query.filter_by(
            nome_tarefa=f'trabalho-do-chamador-{marca_chamador}').first()
        assert sobreviveu is not None, (
            'o rollback do serviço apagou o trabalho que o CHAMADOR já tinha '
            'na sessão — o commit dele persistiu uma sessão vazia e a tela '
            'disse sucesso')

        # E o que o serviço mutou não pode ter vazado para o banco.
        depois = db.session.get(TarefaCronograma, alvo_id)
        assert float(depois.percentual_concluido) == 0.0, (
            'a mutação parcial do serviço foi commitada pelo chamador')


# ---------------------------------------------------------------------------
# Defeito 2 — `views/rdo.py:4116`
# ---------------------------------------------------------------------------

def _post_rdo(cliente, obra_id, func_id, data_rel, rdo_id=None):
    form = {
        'obra_id': str(obra_id),
        'data_relatorio': data_rel,
        f'cron_func_{func_id}_horas': '8',
    }
    if rdo_id is not None:
        form['rdo_id'] = str(rdo_id)
    return cliente.post('/salvar-rdo-flexivel', data=form,
                        follow_redirects=False)


def test_editar_rdo_pelo_flexivel_nao_duplica_mao_de_obra():
    """🔴 O ramo de edição de `ed85d117` reusa o RDO e nunca apaga os filhos.

    Em toda a função (3747-4732) não existe um único `.delete()` — só
    `replace_equipamentos_ocorrencias`, que troca apenas as duas tabelas
    dela. Os inserts de `RDOMaoObra` seguem rodando para o mesmo `rdo_id`,
    sem constraint que barre.

    `services/custo_funcionario_dia.py:223-230` soma `horas_trabalhadas`
    sobre TODAS as linhas daquele `rdo_id`: o dia do trabalhador dobra na
    primeira edição. Todo caminho de edição irmão apaga antes
    (`rdo_editar_sistema.py:264`, `crud_rdo_completo.py:298`,
    `rdo_salvar_unificado:2916`).
    """
    from models import RDO, RDOMaoObra

    with app.app_context():
        t = um_tenant('rdo-dup', com_fatos=False)
        cliente = cliente_de(t.admin_id)
        data_rel = '2026-08-20'

        criacao = _post_rdo(cliente, t.obra_id, t.funcionario_id, data_rel)
        assert criacao.status_code in (200, 302), criacao.status_code

        rdo = RDO.query.filter_by(obra_id=t.obra_id).one()
        linhas_apos_criar = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
        assert linhas_apos_criar == 1, (
            f'a criação devia gravar 1 linha de mão de obra, gravou '
            f'{linhas_apos_criar}')

        edicao = _post_rdo(cliente, t.obra_id, t.funcionario_id, data_rel,
                           rdo_id=rdo.id)
        assert edicao.status_code in (200, 302), edicao.status_code

        linhas_apos_editar = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
        assert linhas_apos_editar == 1, (
            f'a edição APENDOU em vez de substituir: {linhas_apos_editar} '
            f'linhas de mão de obra para o mesmo RDO — as horas do '
            f'trabalhador dobraram no dia')


def test_editar_rdo_pelo_flexivel_grava_a_data_corrigida():
    """🔴 `data_relatorio` é parseada e usada para o `numero_rdo`, mas nunca
    atribuída ao RDO reusado (4115-4128).

    Quem abre o RDO para corrigir a data recebe flash de sucesso e log
    `[EDIT] RDO ... editado`, e a data continua a antiga. Como
    `custo_funcionario_dia` rateia a diária entre os RDOs de UMA data, o
    custo também fica no dia errado.
    """
    from models import RDO

    with app.app_context():
        t = um_tenant('rdo-data', com_fatos=False)
        cliente = cliente_de(t.admin_id)

        _post_rdo(cliente, t.obra_id, t.funcionario_id, '2026-08-20')
        rdo = RDO.query.filter_by(obra_id=t.obra_id).one()

        _post_rdo(cliente, t.obra_id, t.funcionario_id, '2026-08-21',
                  rdo_id=rdo.id)

        db.session.expire_all()
        depois = db.session.get(RDO, rdo.id)
        assert depois.data_relatorio == date(2026, 8, 21), (
            f'a edição ignorou a data corrigida: continua '
            f'{depois.data_relatorio}')


# ---------------------------------------------------------------------------
# Defeito 3 — `views/rdo.py:4050`
# ---------------------------------------------------------------------------

def test_edicao_pelo_flexivel_nao_destroi_filhos_de_rdo_assinado():
    """⚪ Caracterização — **nasceu verde, de propósito**, e está aqui porque
    o delete deste fix round depende dela.

    `salvar_rdo_flexivel` não tem NENHUMA guarda de estado, nem antes nem
    depois de `ed85d117`. Enquanto a edição só APENDAVA, um POST com o
    `rdo_id` de um RDO assinado era sujeira; com o delete, passaria a
    DESTRUIR mão de obra de documento imutável. Conferido de fora antes de
    confiar: quem barra é o `before_flush` de
    `services/rdo_ciclo_vida.py:309`, que levanta `RDOImutavel` no autoflush
    disparado pelo PRÓPRIO delete — nenhuma linha chega a sair, a rota
    devolve 302 e a mão de obra fica intacta.

    Ou seja, o delete é seguro por causa de uma guarda que mora em outro
    módulo. Se alguém afrouxar aquele `before_flush`, este teste é o que
    avisa — e é por isso que ele existe apesar de nunca ter sido vermelho.
    """
    from models import RDO, RDOMaoObra

    with app.app_context():
        t = um_tenant('rdo-assinado', com_fatos=False)
        cliente = cliente_de(t.admin_id)
        data_rel = '2026-08-20'

        _post_rdo(cliente, t.obra_id, t.funcionario_id, data_rel)
        rdo = RDO.query.filter_by(obra_id=t.obra_id).one()
        assert RDOMaoObra.query.filter_by(rdo_id=rdo.id).count() == 1

        rdo.estado = 'assinado'
        db.session.commit()

        _post_rdo(cliente, t.obra_id, t.funcionario_id, data_rel,
                  rdo_id=rdo.id)

        db.session.expire_all()
        assert RDOMaoObra.query.filter_by(rdo_id=rdo.id).count() == 1, (
            'a edição apagou a mão de obra de um RDO ASSINADO — documento '
            'imutável perdeu conteúdo por um POST sem guarda de estado')


def test_rdo_legado_com_admin_id_nulo_e_editado_nao_duplicado():
    """🔴 `_rdo_alvo` filtra `admin_id` direto, e `RDO.admin_id` é
    `nullable=True` — as linhas pré-tenant têm NULL.

    O irmão robusto (`views/rdo.py:2891`) resolve o tenant por
    `RDO.query.join(Obra).filter(Obra.admin_id == ...)`, e existe justamente
    por isso. Com `filter_by(admin_id=...)`, um POST com `rdo_id` de RDO
    legado devolve `None`, cai no ramo de criação e **cria a duplicata que a
    correção existe para impedir**.
    """
    from models import RDO

    with app.app_context():
        t = um_tenant('rdo-legado', com_fatos=False)
        cliente = cliente_de(t.admin_id)

        legado = RDO(
            numero_rdo=f'RDO-LEGADO-{_marca()}',
            obra_id=t.obra_id,
            data_relatorio=date(2026, 8, 20),
            local='Campo',
            admin_id=None)  # linha pré-tenant
        db.session.add(legado)
        db.session.commit()
        legado_id = legado.id

        _post_rdo(cliente, t.obra_id, t.funcionario_id, '2026-08-20',
                  rdo_id=legado_id)

        rdos_da_obra = RDO.query.filter_by(obra_id=t.obra_id).count()
        assert rdos_da_obra == 1, (
            f'o POST com rdo_id do RDO legado criou um RDO novo em vez de '
            f'editá-lo: {rdos_da_obra} RDOs na obra')
