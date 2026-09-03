"""Onda 4 — o relatório passa a funcionar.

A regra desta onda: **todo teste CHAMA o relatório**. Os quatro que nunca
funcionaram quebravam na primeira linha e passavam em teste de fumaça com base
vazia — foi assim que sobreviveram meses. Testar a função pura não teria pego
nenhum deles.

⚠️ Os nomes de função que o plano de 25/08 citava (`gerar_balancete`,
`gerar_dre`) não existem na árvore. Os reais são `obter_dados_balancete` e
`calcular_dre_mensal` — ancorados por nome, como o pré-voo de 03/09 mandou.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

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
        app.secret_key = 'test-onda4-relatorio'
    yield


def _lancamento(admin_id, conta_debito, conta_credito, valor, quando=None):
    """Um lançamento de partida dobrada, pelo caminho normal.

    ⚠️ `numero` e `sequencia` são NOT NULL sem default — omiti-los faz o teste
    morrer de `IntegrityError` ANTES de tocar o relatório, que é o RED pelo
    motivo errado. Foi o que aconteceu na primeira escrita deste arquivo.
    """
    from models import LancamentoContabil, PartidaContabil

    proximo = (db.session.query(db.func.coalesce(
        db.func.max(LancamentoContabil.numero), 0))
        .filter(LancamentoContabil.admin_id == admin_id).scalar() or 0) + 1

    lanc = LancamentoContabil(
        admin_id=admin_id, numero=proximo,
        data_lancamento=quando or date(2026, 7, 15),
        historico=f'onda4 {uuid.uuid4().hex[:6]}', valor_total=valor)
    db.session.add(lanc)
    db.session.flush()
    for i, (codigo, tipo) in enumerate(
            ((conta_debito, 'DEBITO'), (conta_credito, 'CREDITO')), start=1):
        db.session.add(PartidaContabil(
            admin_id=admin_id, lancamento_id=lanc.id, sequencia=i,
            conta_codigo=codigo, tipo_partida=tipo, valor=valor))
    db.session.flush()
    return lanc


def _tenant_com_plano(prefixo):
    """Tenant com plano de contas semeado — sem ele o balancete itera vazio.

    ⚠️ É a armadilha da própria onda: um balancete sobre zero contas amarra
    trivialmente (0 == 0) e o teste passaria sem tocar no defeito.
    """
    from contabilidade_utils import seed_plano_contas_if_needed

    t = um_tenant(prefixo, com_fatos=False)
    seed_plano_contas_if_needed(t.admin_id)
    db.session.commit()
    return t


def _codigos_existentes(admin_id, *preferidos):
    """Devolve, para cada prefixo pedido, um código que EXISTE no plano.

    Não fixa `1.1.01` na pedra: o plano de contas do tenant é semeado por um
    dos seeders da casa, e a Fase 8 ainda vai unificá-los.
    """
    from models import PlanoContas

    achados = []
    for pref in preferidos:
        c = (PlanoContas.query
             .filter(PlanoContas.admin_id == admin_id,
                     PlanoContas.codigo.like(f'{pref}%'),
                     PlanoContas.aceita_lancamento.is_(True))
             .order_by(PlanoContas.codigo).first())
        assert c is not None, f'o plano semeado não tem conta {pref}*'
        achados.append(c.codigo)
    return achados


# ---------------------------------------------------------------------------
# Task 1 — a DRE e o balancete passam a fechar
# ---------------------------------------------------------------------------

def test_balancete_de_um_lancamento_balanceado_amarra():
    """🔴 A coluna era decidida DEPOIS de o sinal já ter sido normalizado.

    `saldo_atual` sai normalizado pela natureza (devedora: D−C; credora: C−D) e
    logo depois `'saldo_devedor': saldo_atual if saldo_atual > 0` joga o saldo
    CREDOR normal de uma conta credora na coluna de DÉBITO.

    D Caixa 1.000 / C Receita 1.000 dava devedor 2.000, credor 0 — um balancete
    de verificação que nunca amarra.
    """
    from contabilidade_utils import obter_dados_balancete

    with app.app_context():
        t = _tenant_com_plano('onda4_balan')
        caixa, receita = _codigos_existentes(t.admin_id, '1.1.01', '4.1.01')
        _lancamento(t.admin_id, caixa, receita, Decimal('1000.00'))
        db.session.commit()

        dados = obter_dados_balancete(t.admin_id, 7, 2026)

        # A guarda contra verdade vácua: se nenhuma conta entrou, o assert de
        # baixo passaria com 0 == 0 sem nunca tocar no defeito.
        assert dados['contas'], 'nenhuma conta com movimento — teste vácuo'

        tot = dados['totais']
        assert Decimal(str(tot['total_saldo_devedor'])) == \
            Decimal(str(tot['total_saldo_credor'])), (
                f"balancete não amarra: devedor {tot['total_saldo_devedor']} "
                f"× credor {tot['total_saldo_credor']}")


def test_estorno_some_da_dre():
    """🔴 A DRE contava só um lado das partidas.

    `if tipo_esperado: if partida.tipo_partida == tipo_esperado: total += valor`
    — o estorno grava a partida inversa CORRETA, e ela era filtrada fora. A DRE
    reportava a receita para sempre, discordando do balancete no mesmo mês.
    """
    from contabilidade_utils import calcular_dre_mensal

    with app.app_context():
        t = _tenant_com_plano('onda4_dre')
        caixa, receita = _codigos_existentes(t.admin_id, '1.1.01', '4.1.01')

        _lancamento(t.admin_id, caixa, receita, Decimal('840.00'))
        db.session.commit()
        com_receita = calcular_dre_mensal(t.admin_id, 2026, 7)
        bruta_antes = Decimal(str(com_receita['receita_bruta']))
        assert bruta_antes >= Decimal('840.00'), (
            f'a receita nem entrou na DRE: {bruta_antes} — teste vácuo')

        # O estorno: a partida inversa, pelo mesmo caminho.
        _lancamento(t.admin_id, receita, caixa, Decimal('840.00'))
        db.session.commit()
        depois = calcular_dre_mensal(t.admin_id, 2026, 7)
        bruta_depois = Decimal(str(depois['receita_bruta']))

        assert bruta_depois == bruta_antes - Decimal('840.00'), (
            f'o estorno não baixou a receita: {bruta_antes} → {bruta_depois}')


def test_a_rota_do_balancete_tambem_amarra():
    """🔴 O MESMO defeito, copiado em `contabilidade_views.py:616-620`.

    Corrigir só `contabilidade_utils` deixaria a tela — que é o que o usuário
    abre — continuar mostrando devedor 2× e credor zero. Este teste vai pela
    **rota HTTP**, com o contexto do template capturado, porque é lá que a
    afirmação vale.
    """
    from flask import template_rendered

    with app.app_context():
        t = _tenant_com_plano('onda4_rota_balan')
        caixa, receita = _codigos_existentes(t.admin_id, '1.1.01', '4.1.01')
        _lancamento(t.admin_id, caixa, receita, Decimal('1000.00'))
        db.session.commit()
        admin_id = t.admin_id

    capturado = []

    def _registrar(sender, template, context, **extra):
        capturado.append(context)

    template_rendered.connect(_registrar, app)
    try:
        cli = cliente_de(admin_id)
        resp = cli.get('/contabilidade/balancete?mes=7&ano=2026')
    finally:
        template_rendered.disconnect(_registrar, app)

    assert resp.status_code == 200, (
        f'a rota do balancete não abriu: {resp.status_code}')
    assert capturado, 'nenhum template renderizado — o teste não chegou lá'

    ctx = capturado[-1]
    assert ctx.get('contas'), 'nenhuma conta com movimento — teste vácuo'
    tot = ctx['totais']
    assert Decimal(str(tot['total_saldo_devedor'])) == \
        Decimal(str(tot['total_saldo_credor'])), (
            f"a TELA do balancete não amarra: devedor "
            f"{tot['total_saldo_devedor']} × credor {tot['total_saldo_credor']}")


def test_passivo_invertido_nao_se_disfarca_de_passivo_normal():
    """🔴 `gerar_balanco_patrimonial` aplicava `abs()` ao saldo do passivo e do
    PL, e com isso um saldo INVERTIDO virava um saldo normal na tela.

    🔬 `calcular_saldo_conta` devolve D−C, sem normalizar por natureza: um
    passivo com saldo devedor (invertido) sai positivo, o `abs()` o mantém
    positivo, e ele **soma** ao total do passivo em vez de reduzi-lo. O número
    fica plausível e errado — que é pior que faltar.

    A regra desta onda: relatório não esconde o que não sabe. O saldo invertido
    aparece com o sinal dele.
    """
    from contabilidade_utils import gerar_balanco_patrimonial

    with app.app_context():
        t = _tenant_com_plano('onda4_balanco')
        caixa, passivo_cod = _codigos_existentes(t.admin_id, '1.1.01', '2.1.01')

        # D passivo / C caixa: paga-se uma dívida que não se devia — o passivo
        # fica INVERTIDO (saldo devedor).
        _lancamento(t.admin_id, passivo_cod, caixa, Decimal('1000.00'))
        db.session.commit()

        balanco = gerar_balanco_patrimonial(t.admin_id, date(2026, 7, 31))

        linha = balanco['passivo']['circulante'].get(passivo_cod)
        assert linha is not None, (
            f'a conta {passivo_cod} nem apareceu no balanço — teste vácuo')
        assert Decimal(str(linha['saldo'])) < 0, (
            f"passivo invertido saiu como {linha['saldo']}, positivo — "
            f'disfarçado de passivo normal')
