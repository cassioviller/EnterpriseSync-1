"""A13 — quem lê `valor_orcado` (VENDA) como se fosse custo, na ROTA.

**Por que este arquivo existe, sendo que o p3 já tem testes.** Os testes de
`tests/test_p3_p9_orcado_e_contrato.py` chamam `custo_orcado_da_obra` e
`custo_orcado_por_servico` **direto**: provam que a fonte nova calcula certo e
não fazem uma única afirmação sobre quem ainda lê a fonte velha. Aqui a
afirmação é sobre o **banco depois de um GET** — `NotificacaoOrcamento` gravada
ou não gravada por `/obras/<id>/planejamento-custos/`. Não existia no repositório
nenhum teste que fizesse esse GET nem que instanciasse `NotificacaoOrcamento`.

**O defeito, com o número da obra Baia.** A etapa Fundação tem
`valor_orcado = 173.747,83` (que é PREÇO DE VENDA, herdado do listener comercial)
e duas linhas de custo somando **155.982,64**. Com linhas, o `a_realizar_total`
gravado É o próprio custo orçado — identidade de `recalcular_osc_dos_itens`. Então
`utils/notifications.py:45` calcula `projetado = realizado + a_realizar` =
`realizado + 155.982,64`, e compara com a venda: o alerta dispara quando
`realizado > 173.747,83 − 155.982,64`, ou seja, a partir de **R$ 17.766** — 11% do
custo da etapa.

Não é alerta tarde demais: é **alarme falso cedo demais**, com uma mensagem que
chama preço de venda de "orçado".

**A asserção que protege contra a correção ingênua** é a do 1º GET. Trocar a base
de comparação sem passar pelo `a_realizar_efetivo` faz `projetado` virar
`realizado + orcado`, e aí QUALQUER realizado > 0 estoura — avalanche em vez de
correção. O 1º GET afirma zero notificação para 20.000 de realizado dentro de
155.982,64 de custo.
"""
import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (NotificacaoOrcamento, ObraServicoCusto,
                    ObraServicoCustoItem)

from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

# Os números da obra Baia, que é onde o defeito foi medido.
VENDA = Decimal('173747.83')
LINHA_VEKS = Decimal('68100.00')
LINHA_FAT_DIRETO = Decimal('87882.64')
CUSTO = LINHA_VEKS + LINHA_FAT_DIRETO          # 155.982,64
REALIZADO_DENTRO = Decimal('20000.00')
REALIZADO_ESTOURANDO = Decimal('160000.00')


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a13'
    yield


def _fundacao(t, realizado=REALIZADO_DENTRO):
    """A etapa Fundação no estado que o sistema real grava.

    `override_realizado_manual=True` porque senão o snapshot de realizado é
    reescrito a partir de `GestaoCustoFilho`, e o cenário deixa de controlar o
    número que está sendo medido.

    O `a_realizar` é semeado como `recalcular_osc_dos_itens` grava — mão de obra
    recebe a soma de fonte != 'fat_direto', material recebe a de 'fat_direto'.
    Semear diferente disso mediria uma versão do defeito, não o defeito.
    """
    osc = ObraServicoCusto(
        obra_id=t.obra_id, admin_id=t.admin_id, nome='Fundação',
        valor_orcado=VENDA,
        realizado_material=0, realizado_mao_obra=realizado, realizado_outros=0,
        override_realizado_manual=True,
        mao_obra_a_realizar=LINHA_VEKS,
        material_a_realizar=LINHA_FAT_DIRETO,
        outros_a_realizar=0)
    db.session.add(osc)
    db.session.flush()
    for valor, fonte in ((LINHA_VEKS, 'veks'), (LINHA_FAT_DIRETO, 'fat_direto')):
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=t.admin_id,
            descricao=f'linha {fonte}', valor=valor, fonte=fonte))
    db.session.commit()
    return osc


def _ativas(t):
    db.session.expire_all()
    return NotificacaoOrcamento.query.filter_by(
        obra_id=t.obra_id, ativa=True).all()


def test_realizado_dentro_do_custo_nao_gera_alerta():
    """20.000 gastos numa etapa que custa 155.982,64 não é estouro.

    🔬 **Esta é a asserção que prova o defeito E protege contra a correção
    ingênua**, e por isso é a primeira. Hoje o GET grava UMA notificação ativa:
    `projetado = 20.000 + 155.982,64 = 175.982,64 > 173.747,83`. E se a correção
    trocar a base sem o `a_realizar_efetivo`, ela continua gravando — pelo motivo
    oposto, `20.000 + 155.982,64 > 155.982,64`. Só o cálculo certo dá zero.
    """
    with app.app_context():
        a, _b = dois_tenants('a13')
        _fundacao(a)

        r = cliente_de(a.admin_id).get(
            f'/obras/{a.obra_id}/planejamento-custos/')
        assert r.status_code == 200, f'a rota respondeu {r.status_code}'

        ativas = _ativas(a)
        assert len(ativas) == 0, (
            f'{len(ativas)} alerta(s) para R$ 20.000 gastos numa etapa de '
            f'R$ 155.982,64 de custo — o alerta está comparando com o PREÇO DE '
            f'VENDA (R$ 173.747,83) e dispara a partir de R$ 17.766')


def test_estouro_de_verdade_alerta_com_os_numeros_de_custo():
    """160.000 numa etapa de 155.982,64 é estouro, e o alerta diz isso em custo.

    O que se afirma não é só "alertou": é que os números GRAVADOS na notificação
    são de custo. Se `valor_orcado` sair 173.747,83, o alerta continua contando a
    história errada mesmo tendo disparado na hora certa.
    """
    with app.app_context():
        a, _b = dois_tenants('a13est')
        _fundacao(a, realizado=REALIZADO_ESTOURANDO)

        r = cliente_de(a.admin_id).get(
            f'/obras/{a.obra_id}/planejamento-custos/')
        assert r.status_code == 200

        ativas = _ativas(a)
        assert len(ativas) == 1, f'{len(ativas)} alertas para um estouro'
        n = ativas[0]
        assert Decimal(n.valor_orcado) == CUSTO, (
            f'o alerta gravou orçado {n.valor_orcado} — 173747.83 é a venda, e '
            f'o custo da etapa é {CUSTO}')
        assert Decimal(n.valor_projetado) == REALIZADO_ESTOURANDO, (
            f'projetado {n.valor_projetado}: com o realizado acima do custo, o '
            f'a_realizar_efetivo é zero e a projeção é o próprio realizado')
        assert Decimal(n.valor_excesso) == REALIZADO_ESTOURANDO - CUSTO, (
            f'excesso {n.valor_excesso}, esperado {REALIZADO_ESTOURANDO - CUSTO}')


def test_a_coluna_orcado_da_tela_exibe_custo_e_nao_venda():
    """B2.3 — o corpo do GET traz 155.982,64, e NÃO 173.747,83.

    A tela mostrava, na mesma página, um card "Valor Custo Orç." com o custo
    (vindo de `calcular_resumo_obra`) e uma coluna "Orçado" com a venda. Dois
    números para a mesma pergunta, a três centímetros um do outro.

    A coluna "A Realizar" entra junto, e não é zelo: com linhas de custo o
    `a_realizar_total` gravado É o orçado, então deixá-la como estava mostraria
    Orçado 155.982,64 e A Realizar 155.982,64 numa etapa com R$ 20.000 já gastos
    — a linha diria que nada foi gasto. Trocar uma metade e não a outra é o que o
    recorte chama de "deixar as duas metades em regras diferentes".
    """
    with app.app_context():
        a, _b = dois_tenants('a13col')
        _fundacao(a)

        r = cliente_de(a.admin_id).get(
            f'/obras/{a.obra_id}/planejamento-custos/')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)

        assert '155.982,64' in corpo, (
            'o custo orçado da etapa não aparece na tela')
        assert '173.747,83' not in corpo, (
            'o preço de venda ainda está sendo exibido como "Orçado"')
        assert '135.982,64' in corpo, (
            'A Realizar continua mostrando o orçado inteiro, como se nada '
            'tivesse sido gasto')


def test_projecao_indisponivel_cai_no_caminho_antigo_e_avisa(monkeypatch, caplog):
    """Mapa vazio é "não sei", e "não sei" não pode virar "orçado zero".

    `custo_orcado.py` engole exceção e devolve `{}`. Se `servico_estourou`
    tratasse isso como orçado zero, **toda** etapa da obra passaria a estourar na
    primeira falha de query — indisponibilidade virando alarme geral na tela.

    Este teste existe porque o ramo de compatibilidade é, por natureza, o que
    nunca roda em condição normal: sem cobri-lo, ele é código morto que ninguém
    descobre estar quebrado até o dia em que precisa dele. Com o mapa forçado a
    vazio, o comportamento tem de ser exatamente o de antes do A13 — alerta pela
    régua da venda — e um WARNING no log dizendo que foi isso que aconteceu.
    """
    import services.custo_orcado as mod

    with app.app_context():
        a, _b = dois_tenants('a13fb')
        _fundacao(a)  # 20.000 realizado: dentro do custo, FORA da margem

        monkeypatch.setattr(mod, 'projecao_de_custo_por_servico',
                            lambda *a_, **k: {})

        with caplog.at_level('WARNING'):
            r = cliente_de(a.admin_id).get(
                f'/obras/{a.obra_id}/planejamento-custos/')
        assert r.status_code == 200

        assert len(_ativas(a)) == 1, (
            'sem projeção o comportamento tem de ser o antigo — alertar pela '
            'venda —, nunca "orçado zero"')
        assert any('projeção de custo vazia' in m for m in caplog.messages), (
            f'o fallback rodou calado; mensagens: {caplog.messages}')


def test_a_obra_de_outro_tenant_nao_mexe_nas_notificacoes():
    """GET de B na obra de A: 404, e nada criado nem apagado do lado de A.

    O risco específico é o `_resolver_notificacao`: uma varredura que rodasse com
    o tenant errado desativaria silenciosamente os alertas de A.

    🔬 **UM GET só, e o alerta de A é semeado direto no banco** — e desta vez o
    motivo tem nome. `g` pertence ao APP context, não ao request, e o Flask-Login
    guarda o usuário resolvido em `g._login_user`. Dentro de um único
    ``with app.app_context()``, o segundo cliente herda o `current_user` do
    primeiro: **a requisição de B roda como A.** Foi o que fez a primeira versão
    deste teste ver 200 onde a rota, sozinha, responde 404 corretamente.

    O perigo não é o falso vermelho que apareceu aqui — é o falso VERDE: um teste
    de isolamento escrito assim afirma "B não vê o dado de A" enquanto na verdade
    A está olhando os próprios dados, e passa. **Varrido o repositório em 05/08:
    quatro blocos usam dois clientes no mesmo `app_context`, todos no par
    "logado + anônimo" contra rota pública por token que nunca lê `current_user`
    — nenhum teste de isolamento está contaminado hoje.** A regra que fica:
    *um request autenticado por `app_context`; o resto é precondição semeada.*
    """
    with app.app_context():
        a, b = dois_tenants('a13ten')
        osc = _fundacao(a, realizado=REALIZADO_ESTOURANDO)

        # Precondição semeada, não obtida por request: A já tem alerta ativo.
        db.session.add(NotificacaoOrcamento(
            admin_id=a.admin_id, obra_id=a.obra_id,
            obra_servico_custo_id=osc.id,
            percentual=Decimal('102.58'),
            valor_excesso=REALIZADO_ESTOURANDO - CUSTO,
            valor_orcado=CUSTO, valor_projetado=REALIZADO_ESTOURANDO,
            mensagem='semeado', ativa=True))
        db.session.commit()
        antes = {n.id for n in _ativas(a)}
        assert antes, 'cenário quebrado — A precisa ter alerta ativo'

        r = cliente_de(b.admin_id).get(
            f'/obras/{a.obra_id}/planejamento-custos/')
        assert r.status_code == 404, (
            f'obra de outro tenant respondeu {r.status_code} — 403 já confirma '
            f'que ela existe')
        assert {n.id for n in _ativas(a)} == antes, (
            'o GET do outro tenant mexeu nas notificações de A')
