"""Arreio: custo de RDO por ROTA — as três rotas vivas, o mesmo cenário.

Task B0.3 do `docs/superpowers/plans/2026-08-04-plano-consolidado.md`.

**O que este arquivo mede que nenhum outro media.** A suíte sabia postar em rota
e sabia afirmar sobre banco, mas nunca ligou as duas coisas no caminho do
dinheiro. Aqui um MESMO funcionário mensalista, uma MESMA obra e um MESMO dia
passam pelas três rotas de RDO, e o teste pergunta a única coisa que importa:
**quanto custo sobrou no banco.**

A referência é `POST /salvar-rdo-flexivel` (`views/rdo.py:3612`) — a única das
três que chama `gerar_custos_mao_obra_rdo` (`:4489`) **e** emite o evento com
`obra_id` (`:4500-4504`). As outras duas se comparam a ela. O valor esperado
**não é chumbado**: sai do que a rota de referência produziu no próprio teste.
Chumbar R$ 124,00 amarraria o arreio ao mês em que foi escrito, porque o valor
sai de `salario / (dias_úteis × horas_diárias)`.

**Por que os testes atuais não pegavam.** `tests/test_p1_dedup_cross_origem.py:151-165`
abre `rdo_editar_sistema.py` e `crud_rdo_completo.py` como TEXTO e verifica se a
string ``"EventManager.emit('rdo_finalizado'"`` aparece — ela aparece, e o teste
fica verde enquanto o banco não recebe um centavo. Os dois testes de
comportamento do mesmo arquivo (`:98-114`, `:117-130`) emitem o evento à mão,
pulando a rota inteira, afirmam ``<= 1`` (verdadeiro para zero) e usam um tenant
que já traz `RegistroPonto` na data — o que faz `existe_ponto_no_dia`
(`event_manager.py:722-726`) pular o lançamento antes de o defeito ser
alcançado.

**Marcação.** Os casos que dependem de A05 entram com
``xfail(strict=True)``: `strict` faz o teste **falhar quando o defeito for
corrigido** e alguém esquecer de tirar a marca. É de propósito — o xfail é o
checklist de B1, não um TODO.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import ContaReceber

from helpers_dinheiro import (custo_diario, filhos_mao_de_obra,
                              linhas_mao_de_obra, mao_de_obra, form_rdo,
                              rdo_da_obra, soma, tarefa_da_obra)
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

# Dia sem nenhum RegistroPonto semeado — ver o docstring de `um_tenant`.
DIA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-arreio-rdo'
    yield


def _cenario(prefixo, **perfil):
    """Tenant limpo + tarefa de cronograma. Um por teste, de propósito:
    reaproveitar tenant entre casos faria a contagem de um vazar no outro."""
    perfil.setdefault('tipo_remuneracao', 'salario')
    perfil.setdefault('valor_diaria', 0.0)
    perfil.setdefault('salario', 3000.0)
    tenant = um_tenant(prefixo, data_ref=DIA, com_fatos=False, **perfil)
    tarefa = tarefa_da_obra(tenant)
    return tenant, tarefa


def _ok(resposta):
    """Status é PRÉ-FILTRO, nunca prova.

    As rotas capturam quase tudo em `except` amplo e redirecionam com flash de
    erro (`crud_rdo_completo.py:487-509`, `rdo_editar_sistema.py:566-585`), então
    302 pode ser sucesso ou desastre. Quem decide é linha de banco — este helper
    só barra o 401/500 óbvio.
    """
    assert resposta.status_code in (200, 302), (
        f'rota respondeu {resposta.status_code} — nem sucesso nem redirect')


def _via_flexivel(tenant, tarefa, dia=DIA, horas=8.0):
    """A rota de REFERÊNCIA. Cria o RDO a partir do formulário."""
    cli = cliente_de(tenant.admin_id)
    form = form_rdo(tenant, dia, tarefa_id=tarefa.id, horas=horas)
    form['funcionario_id'] = str(tenant.funcionario_id)
    _ok(cli.post('/salvar-rdo-flexivel', data=form))


def _via_finalizar(tenant, tarefa, dia=DIA, horas=8.0):
    """`POST /rdo/finalizar/<id>`. Exige RDO com mão de obra ANTES do POST —
    sem isso a rota sai por `crud_rdo_completo.py:576-578` com flash+redirect."""
    rdo = rdo_da_obra(tenant, dia)
    mao_de_obra(rdo, tenant, horas=horas, tarefa=tarefa)
    cli = cliente_de(tenant.admin_id)
    _ok(cli.post(f'/rdo/finalizar/{rdo.id}',
                 data=form_rdo(tenant, dia, tarefa_id=tarefa.id, horas=horas)))
    return rdo


def _via_editar(tenant, tarefa, dia=DIA, horas=8.0):
    """`POST /rdo/editar/<id>`. A rota APAGA e reescreve a mão de obra a partir
    do formulário (`rdo_editar_sistema.py:445-491`) — por isso o form carrega as
    chaves `cron_tarefa_*`, e por isso o chamador confere `RDOMaoObra` depois."""
    rdo = rdo_da_obra(tenant, dia)
    mao_de_obra(rdo, tenant, horas=horas, tarefa=tarefa)
    cli = cliente_de(tenant.admin_id)
    _ok(cli.post(f'/rdo/editar/{rdo.id}',
                 data=form_rdo(tenant, dia, tarefa_id=tarefa.id, horas=horas)))
    return rdo


# ---------------------------------------------------------------------------
# A referência — o que a rota boa produz
# ---------------------------------------------------------------------------

def test_a_rota_de_referencia_gera_custo_para_mensalista():
    """Piso do arreio. Se ESTE quebrar, o problema não é A05 — é o cenário."""
    with app.app_context():
        tenant, tarefa = _cenario('ref')
        _via_flexivel(tenant, tarefa)

        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1, (
            f'a rota de referência não gerou custo — o cenário está errado, '
            f'não o código. Encontrou {len(linhas)} linha(s).')
        assert soma(linhas) > 0


# ---------------------------------------------------------------------------
# (a) e (b) — paridade entre as rotas
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason='A05 — event_manager.py:729-733 faz '
                                       'continue quando valor_diaria <= 0')
def test_finalizar_produz_o_mesmo_custo_que_a_rota_de_referencia():
    with app.app_context():
        ref, tarefa_ref = _cenario('parref')
        _via_flexivel(ref, tarefa_ref)
        esperado = soma(filhos_mao_de_obra(ref, DIA))

        alvo, tarefa_alvo = _cenario('parfin')
        _via_finalizar(alvo, tarefa_alvo)

        obtido = soma(filhos_mao_de_obra(alvo, DIA))
        assert obtido == pytest.approx(esperado), (
            f'/rdo/finalizar rendeu R$ {obtido:.2f} onde a referência rendeu '
            f'R$ {esperado:.2f}')


@pytest.mark.xfail(strict=True, reason='A05 — mesmo continue, pela rota de edição')
def test_editar_produz_o_mesmo_custo_que_a_rota_de_referencia():
    with app.app_context():
        ref, tarefa_ref = _cenario('parref2')
        _via_flexivel(ref, tarefa_ref)
        esperado = soma(filhos_mao_de_obra(ref, DIA))

        alvo, tarefa_alvo = _cenario('paredit')
        rdo = _via_editar(alvo, tarefa_alvo)

        # A equipe tem de ter sobrevivido ao POST, senão o assert de dinheiro
        # abaixo seria vacuoso: zero custo porque zero gente.
        assert len(linhas_mao_de_obra(rdo.id)) == 1, (
            'o POST apagou a mão de obra — o formulário não carregava as '
            'chaves cron_tarefa_*, e este teste mediria o apagamento')

        obtido = soma(filhos_mao_de_obra(alvo, DIA))
        assert obtido == pytest.approx(esperado), (
            f'/rdo/editar rendeu R$ {obtido:.2f} onde a referência rendeu '
            f'R$ {esperado:.2f}')


# ---------------------------------------------------------------------------
# (c) — o payload carrega obra_id, provado pelo EFEITO
# ---------------------------------------------------------------------------

def _semear_cr_sentinela(tenant):
    """ContaReceber OBRA_MEDICAO com valor deliberadamente errado.

    `recalcular_medicao_obra` sobrescreve `valor_original` com o medido
    (`services/medicao_service.py:393`). Se o handler rodar, a sentinela some;
    se `recalcular_medicao_apos_rdo` sair por falta de `obra_id`
    (`event_manager.py:1529-1531`), ela fica. É o efeito observável mais barato
    — e não lê o dict do evento, que é o que o plano proíbe.
    """
    cr = ContaReceber(
        cliente_nome='Sentinela', obra_id=tenant.obra_id,
        numero_documento=f'OBR-MED-{tenant.obra_id:05d}',
        descricao='sentinela do arreio',
        valor_original=Decimal('777.00'), valor_recebido=Decimal('0'),
        saldo=Decimal('777.00'), data_emissao=DIA, data_vencimento=DIA,
        status='PENDENTE', origem_tipo='OBRA_MEDICAO',
        origem_id=tenant.obra_id, admin_id=tenant.admin_id)
    db.session.add(cr)
    db.session.commit()
    return cr


def _sentinela_intacta(tenant):
    db.session.expire_all()
    cr = ContaReceber.query.filter_by(
        admin_id=tenant.admin_id, origem_tipo='OBRA_MEDICAO',
        origem_id=tenant.obra_id).first()
    return cr is not None and float(cr.valor_original) == 777.00


def test_a_rota_de_referencia_dispara_o_recalculo_da_medicao():
    with app.app_context():
        tenant, tarefa = _cenario('medref')
        _semear_cr_sentinela(tenant)
        _via_flexivel(tenant, tarefa)

        assert not _sentinela_intacta(tenant), (
            'a sentinela sobreviveu: o recálculo de medição não rodou nem pela '
            'rota de referência')


@pytest.mark.xfail(strict=True, reason='A05 — payload {rdo_id} sem obra_id; '
                                       'event_manager.py:1529-1531 retorna')
def test_finalizar_dispara_o_recalculo_da_medicao():
    with app.app_context():
        tenant, tarefa = _cenario('medfin')
        _semear_cr_sentinela(tenant)
        _via_finalizar(tenant, tarefa)

        assert not _sentinela_intacta(tenant), (
            'a sentinela sobreviveu: o evento chegou sem obra_id e '
            'recalcular_medicao_apos_rdo saiu antes de recalcular')


# ---------------------------------------------------------------------------
# (d) — reexecutar não duplica
# ---------------------------------------------------------------------------

def test_reexecutar_o_mesmo_rdo_nao_duplica_o_custo():
    """A idempotência que o p1 entregou não pode ser desfeita ao consertar A05.

    Usa diarista de propósito: é o único perfil que hoje gera custo pelas rotas
    de edição/finalização, então o teste mede a idempotência de verdade em vez
    de comparar zero com zero.
    """
    with app.app_context():
        tenant, tarefa = _cenario('idem', tipo_remuneracao='diaria',
                                  valor_diaria=150.0)
        rdo = rdo_da_obra(tenant, DIA)
        mao_de_obra(rdo, tenant, horas=8.0, tarefa=tarefa)
        cli = cliente_de(tenant.admin_id)
        form = form_rdo(tenant, DIA, tarefa_id=tarefa.id, horas=8.0)

        _ok(cli.post(f'/rdo/editar/{rdo.id}', data=form))
        depois_de_uma = filhos_mao_de_obra(tenant, DIA)

        _ok(cli.post(f'/rdo/editar/{rdo.id}', data=form))
        depois_de_duas = filhos_mao_de_obra(tenant, DIA)

        assert len(depois_de_uma) == 1
        assert len(depois_de_duas) == 1, (
            f'a segunda passada no MESMO RDO criou linha nova: '
            f'{len(depois_de_duas)} no total')
        assert soma(depois_de_duas) == pytest.approx(150.0)


@pytest.mark.xfail(strict=True, reason='achado do arreio B0, sem item no plano '
                                       '— o rateio proporcional documentado em '
                                       'services/custo_funcionario_dia.py:9-19 '
                                       'não é aplicado')
def test_dois_rdos_no_mesmo_dia_nao_dobram_o_custo_do_dia():
    """Dois RDOs no mesmo dia, mesmo funcionário, mesma obra, 8h cada.

    O funcionário trabalhou um dia, não dois. `services/custo_funcionario_dia.py`
    **documenta** a regra certa no próprio cabeçalho (`:9-11`):

        Rateio proporcional quando o funcionário aparece em >1 RDO no mesmo dia:
          proporção = horas_neste_rdo / total_horas_no_dia

    e o `:18-19` promete recalcular os RDOs vizinhos "pois a proporção mudou".
    O log do serviço confirma que o vizinho foi recalculado — e mesmo assim os
    dois RDOs ficam com o custo integral do dia.

    Medido: R$ 124,00 + R$ 124,00 = R$ 248,00 por um dia de 8 horas. O dedup de
    `services/rdo_custos.py:422-428` não pega, porque a chave é
    `(origem_tabela, origem_id, admin_id)` e `origem_id` é por RDO — dois RDOs
    são duas chaves distintas, por construção.

    É o espelho de A05: lá o custo some, aqui ele dobra. E acontece na rota que
    o plano trata como referência.
    """
    with app.app_context():
        tenant, tarefa = _cenario('doisrdo')

        _via_flexivel(tenant, tarefa)
        um_rdo = soma(filhos_mao_de_obra(tenant, DIA))

        _via_flexivel(tenant, tarefa)
        dois_rdos = soma(filhos_mao_de_obra(tenant, DIA))

        assert dois_rdos == pytest.approx(um_rdo), (
            f'o dia custou R$ {um_rdo:.2f} com um RDO e R$ {dois_rdos:.2f} com '
            f'dois — o rateio proporcional não foi aplicado')


# ---------------------------------------------------------------------------
# (e) — matriz de perfis
# ---------------------------------------------------------------------------

def test_diarista_gera_custo_pela_rota_de_finalizar():
    """O diarista passa porque `valor_diaria > 0` — é o único perfil que o
    handler do evento sabe custear (`event_manager.py:730-733`). Serve de
    controle: prova que a rota funciona e que o defeito é do PERFIL, não da rota."""
    with app.app_context():
        tenant, tarefa = _cenario('diarista', tipo_remuneracao='diaria',
                                  valor_diaria=150.0)
        _via_finalizar(tenant, tarefa)

        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1, (
            f'nem o diarista gerou custo por /rdo/finalizar — o defeito é maior '
            f'do que A05 descreve. Encontrou {len(linhas)}.')
        assert soma(linhas) == pytest.approx(150.0)


@pytest.mark.xfail(strict=True, reason='A05 — mensalista cai no continue')
def test_mensalista_gera_custo_pela_rota_de_finalizar():
    """O espelho do anterior. A diferença entre os dois é UMA coluna do
    funcionário — e é ela que hoje decide se o dia custa ou não custa nada."""
    with app.app_context():
        tenant, tarefa = _cenario('mensal')
        _via_finalizar(tenant, tarefa)

        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1, (
            f'mensalista não gerou custo por /rdo/finalizar: {len(linhas)} linha(s)')


# ---------------------------------------------------------------------------
# (g) — a assinatura estrutural do defeito
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason='A05 — a linha de custo diário existe e '
                                       'não vira lançamento')
def test_custo_diario_gravado_implica_lancamento_na_gestao_de_custos():
    """A asserção mais barata de todas, e a que descreve o defeito com precisão:
    se `RDOCustoDiario.componente_folha > 0`, alguém calculou o custo do dia.
    Zero `GestaoCustoFilho` depois disso significa que o cálculo foi jogado fora
    entre uma tabela e outra."""
    with app.app_context():
        tenant, tarefa = _cenario('assin')
        rdo = _via_editar(tenant, tarefa)

        folha = soma(custo_diario(rdo.id), campo='componente_folha')
        filhos = filhos_mao_de_obra(tenant, DIA)

        if folha > 0:
            assert len(filhos) > 0, (
                f'RDOCustoDiario.componente_folha = R$ {folha:.2f} e nenhum '
                f'GestaoCustoFilho: o custo foi calculado e descartado')


# ---------------------------------------------------------------------------
# (f) — congelar o gap conhecido de /rdo/salvar
# ---------------------------------------------------------------------------

def test_rdo_salvar_unificado_gera_custo_e_nao_recalcula_medicao():
    """Congela o comportamento de `POST /rdo/salvar` (`views/rdo.py:2766`).

    Não é xfail: não é defeito de A05, é um gap conhecido e diferente — a rota
    lança custo e não emite `rdo_finalizado`. Fica registrado por teste para que
    a correção de A05 não o altere sem que alguém veja.
    """
    with app.app_context():
        tenant, tarefa = _cenario('unif')
        _semear_cr_sentinela(tenant)

        cli = cliente_de(tenant.admin_id)
        form = form_rdo(tenant, DIA, tarefa_id=tarefa.id)
        form['funcionario_id'] = str(tenant.funcionario_id)
        _ok(cli.post('/rdo/salvar', data=form))

        assert _sentinela_intacta(tenant), (
            'a sentinela sumiu: /rdo/salvar passou a recalcular medição — '
            'comportamento mudou e este teste precisa ser reavaliado')
