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
from sqlalchemy import text

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


def _garantir_contas(admin_id, *codigos):
    """Cria, no plano do tenant, as contas que a rotina de integração usa.

    ⚠️ Isto é setup, não conserto. 🔬 As rotinas `contabilizar_*` postam contra
    códigos escritos para OUTRO seeder (`4.1.02.002`, `2.1.03.007`… não existem
    no plano canônico), e remapeá-los é trabalho da **Fase 8**. Semear as contas
    aqui isola o que ESTA task conserta — os atributos inexistentes e a
    aritmética — do de-para que ainda vai mudar.
    """
    from models import PlanoContas

    for codigo in codigos:
        ja = PlanoContas.query.filter_by(admin_id=admin_id, codigo=codigo).first()
        if ja:
            continue
        grupo = codigo[0]
        natureza = 'DEVEDORA' if grupo in ('1', '5', '6') else 'CREDORA'
        db.session.add(PlanoContas(
            admin_id=admin_id, codigo=codigo, nome=f'Conta {codigo}',
            tipo_conta={'1': 'ATIVO', '2': 'PASSIVO', '3': 'PATRIMONIO',
                        '4': 'RECEITA'}.get(grupo, 'DESPESA'),
            natureza=natureza, nivel=len(codigo.split('.')),
            aceita_lancamento=True))
    db.session.flush()


def _categoria_de(admin_id):
    """Categoria do almoxarifado do tenant — `categoria_id` é NOT NULL."""
    from models import AlmoxarifadoCategoria

    cat = AlmoxarifadoCategoria.query.filter_by(admin_id=admin_id).first()
    if not cat:
        cat = AlmoxarifadoCategoria(admin_id=admin_id, nome='Geral Onda 4',
                                    tipo_controle_padrao='CONSUMIVEL')
        db.session.add(cat)
        db.session.flush()
    return cat.id


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


# ---------------------------------------------------------------------------
# Task 2 — a integração contábil para de dar 500
# ---------------------------------------------------------------------------

def _integrar(admin_id, payload):
    """Chama a rota de integração. É a rota que dava erro, não a função."""
    cli = cliente_de(admin_id)
    return cli.post('/contabilidade/api/processar-integracao', json=payload)


def test_integracao_de_proposta_aprovada_nao_estoura():
    """🔴 `contabilizar_proposta_aprovada` lia `proposta.data_aprovacao`.

    🔬 O atributo NÃO EXISTE em `Proposta` (as datas são `data_proposta`,
    `data_envio`, `data_resposta_cliente`). A rota devolvia 400 com o
    `AttributeError` no corpo, e nenhum lançamento nascia.
    """
    from models import Cliente, LancamentoContabil, Obra, Proposta

    with app.app_context():
        t = _tenant_com_plano('onda4_int_prop')
        # ⚠️ A função sai cedo se `status != 'APROVADA'` (maiúsculas) e usa
        # `proposta.obra.nome` para nomear o centro de custo: sem os dois, o
        # teste passaria pelo caminho vazio sem nunca tocar o defeito.
        cli_obj = Cliente(admin_id=t.admin_id, nome='Cliente Onda 4')
        db.session.add(cli_obj)
        db.session.flush()
        obra = Obra(admin_id=t.admin_id, nome='Obra Onda 4',
                    data_inicio=date(2026, 7, 1), cliente_id=cli_obj.id)
        db.session.add(obra)
        db.session.flush()
        p = Proposta(admin_id=t.admin_id, numero=f'P{uuid.uuid4().hex[:6]}',
                     cliente_nome='Cliente Onda 4', valor_total=Decimal('5000.00'),
                     obra_id=obra.id, data_proposta=date(2026, 7, 10),
                     data_resposta_cliente=date(2026, 7, 20), status='APROVADA')
        db.session.add(p)
        _garantir_contas(t.admin_id, '1.1.02.001', '4.1.02.002')
        db.session.commit()
        admin_id, pid = t.admin_id, p.id

    resp = _integrar(admin_id, {'tipo': 'proposta_aprovada', 'origem_id': pid})
    assert resp.status_code == 200, (
        f'a integração de proposta falhou: {resp.status_code} {resp.get_json()}')
    assert resp.get_json()['success'] is True, resp.get_json()

    with app.app_context():
        gravados = LancamentoContabil.query.filter_by(
            admin_id=admin_id, origem='MODULO_1', origem_id=pid).count()
        assert gravados == 1, (
            f'a rota disse sucesso e gravou {gravados} lançamentos')


def test_integracao_de_entrada_material_nao_estoura_e_amarra():
    """🔴 Dois defeitos no mesmo lugar.

    (1) `nota.fornecedor_nome` e `nota.valor_icms` **não existem** em
    `NotaFiscal`. (2) Mesmo corrigidos, o débito era `valor_produtos +
    valor_icms` contra crédito de `valor_total`: sempre que o ICMS está
    embutido no preço — a norma brasileira — o lançamento fica desbalanceado e
    `criar_lancamento_automatico` levanta "Lançamento desbalanceado".
    """
    from models import Fornecedor, LancamentoContabil, NotaFiscal

    with app.app_context():
        t = _tenant_com_plano('onda4_int_nf')
        f = Fornecedor(admin_id=t.admin_id, nome='Fornecedor Onda 4',
                       cnpj=f'{uuid.uuid4().int % 10**14:014d}')
        db.session.add(f)
        db.session.flush()
        nf = NotaFiscal(
            admin_id=t.admin_id, numero=f'{uuid.uuid4().int % 10**6:06d}',
            serie='1', chave_acesso=uuid.uuid4().hex * 1,
            fornecedor_id=f.id, data_emissao=date(2026, 7, 12),
            valor_produtos=Decimal('1000.00'), valor_total=Decimal('1000.00'))
        db.session.add(nf)
        db.session.commit()
        admin_id, nid = t.admin_id, nf.id

    resp = _integrar(admin_id, {'tipo': 'entrada_material', 'origem_id': nid})
    assert resp.status_code == 200, (
        f'a entrada de material falhou: {resp.status_code} {resp.get_json()}')

    with app.app_context():
        lanc = LancamentoContabil.query.filter_by(
            admin_id=admin_id, origem='MODULO_4', origem_id=nid).first()
        assert lanc is not None, 'a rota disse sucesso e não gravou nada'

        from models import PartidaContabil
        partidas = PartidaContabil.query.filter_by(lancamento_id=lanc.id).all()
        deb = sum(p.valor for p in partidas if p.tipo_partida == 'DEBITO')
        cre = sum(p.valor for p in partidas if p.tipo_partida == 'CREDITO')
        assert deb == cre, f'lançamento desbalanceado: débito {deb} × crédito {cre}'


def test_integracao_de_folha_nao_estoura():
    """🔴 `contabilizar_folha_pagamento` somava `f.salario_bruto`.

    🔬 `FolhaPagamento` não tem esse atributo — tem `salario_base`,
    `outros_proventos` e `total_proventos`. O bruto é o `total_proventos`.
    """
    from models import Funcionario, FolhaPagamento, LancamentoContabil

    with app.app_context():
        t = _tenant_com_plano('onda4_int_folha')
        func = Funcionario.query.filter_by(admin_id=t.admin_id).first()
        assert func is not None, 'o tenant nasceu sem funcionário — teste vácuo'
        fp = FolhaPagamento(
            admin_id=t.admin_id, funcionario_id=func.id,
            mes_referencia=date(2026, 7, 1), salario_base=Decimal('3000.00'),
            total_proventos=Decimal('3200.00'),
            # ⚠️ O líquido tem de respeitar a identidade da própria folha
            # (bruto − inss − irrf), senão o lançamento sai desbalanceado por
            # culpa do DADO e o teste acusaria o código de um defeito que é do
            # teste. Foi o que aconteceu na primeira escrita: 2600 em vez de 2800.
            salario_liquido=Decimal('2800.00'),
            inss=Decimal('300.00'), irrf=Decimal('100.00'), fgts=Decimal('256.00'))
        db.session.add(fp)
        _garantir_contas(t.admin_id, '6.1.01.001', '6.1.01.002', '2.1.02.001',
                         '2.1.03.007', '2.1.02.004', '2.1.03.008')
        db.session.commit()
        admin_id = t.admin_id

    resp = _integrar(admin_id, {'tipo': 'folha_pagamento',
                                'mes_referencia': '2026-07-01'})
    assert resp.status_code == 200, (
        f'a folha falhou: {resp.status_code} {resp.get_json()}')

    with app.app_context():
        gravados = LancamentoContabil.query.filter_by(
            admin_id=admin_id, origem='MODULO_6').count()
        assert gravados >= 1, 'a rota disse sucesso e não gravou lançamento'


def test_conta_ausente_e_recusada_com_nome_e_sem_rastro():
    """A guarda que esta onda acrescentou ao ponto único das integrações.

    🔬 Antes, postar contra uma conta que o tenant não tem morria em
    `ForeignKeyViolation` e o usuário recebia um dump de SQL de 400 caracteres.
    Agora recebe o **nome da conta que falta** — e nada é gravado.

    ⚠️ Este teste é o registro vivo da divergência que a **Fase 8** vai
    resolver: as rotinas `contabilizar_*` foram escritas contra outro seeder.
    """
    from models import Cliente, LancamentoContabil, Obra, Proposta

    with app.app_context():
        t = _tenant_com_plano('onda4_conta_ausente')
        cli_obj = Cliente(admin_id=t.admin_id, nome='Cliente sem conta')
        db.session.add(cli_obj)
        db.session.flush()
        obra = Obra(admin_id=t.admin_id, nome='Obra sem conta',
                    data_inicio=date(2026, 7, 1), cliente_id=cli_obj.id)
        db.session.add(obra)
        db.session.flush()
        p = Proposta(admin_id=t.admin_id, numero=f'P{uuid.uuid4().hex[:6]}',
                     cliente_nome='Cliente sem conta', valor_total=Decimal('900.00'),
                     obra_id=obra.id, data_proposta=date(2026, 7, 10),
                     data_resposta_cliente=date(2026, 7, 20), status='APROVADA')
        db.session.add(p)
        db.session.commit()  # SEM _garantir_contas: é o ponto do teste
        admin_id, pid = t.admin_id, p.id

    resp = _integrar(admin_id, {'tipo': 'proposta_aprovada', 'origem_id': pid})
    assert resp.status_code == 400, f'esperado 400, veio {resp.status_code}'
    msg = resp.get_json()['message']
    assert '4.1.02.002' in msg, f'a recusa não nomeia a conta que falta: {msg}'
    assert 'psycopg2' not in msg and 'INSERT' not in msg, (
        f'a recusa vazou SQL para o usuário: {msg}')

    with app.app_context():
        sobrou = LancamentoContabil.query.filter_by(
            admin_id=admin_id, origem='MODULO_1', origem_id=pid).count()
        assert sobrou == 0, f'a recusa deixou rastro: {sobrou} lançamentos'


# ---------------------------------------------------------------------------
# Task 3 — os dois relatórios do almoxarifado que nunca rodaram
# ---------------------------------------------------------------------------

def test_relatorio_de_posicao_de_estoque_abre():
    """🔴 `views/almoxarifado/relatorios.py:39` — `ativo=True` numa tabela que
    não tem a coluna.

    🔬 `AlmoxarifadoEstoque` (`models.py:5562`) não tem `ativo`:
    `hasattr(...)` é False e o `grep` na classe devolve zero. O
    `filter_by(admin_id=..., ativo=True)` levanta `InvalidRequestError`, nada
    captura na rota, e o relatório "Posição de Estoque" devolve **500 seco**.
    Nunca funcionou.

    ⚠️ O parâmetro da rota é `tipo`, não `relatorio_tipo` como o plano de 25/08
    escreveu — com o nome errado a requisição cairia no ramo vazio e o teste
    passaria verde sem tocar o defeito.
    """
    with app.app_context():
        t = um_tenant('onda4_posic', com_fatos=False)
        admin_id = t.admin_id

    resp = cliente_de(admin_id).get(
        '/almoxarifado/relatorios?tipo=posicao_estoque')
    assert resp.status_code == 200, (
        f'posição de estoque devolveu {resp.status_code}')


def test_relatorio_de_alertas_sobrevive_a_estoque_minimo_nulo():
    """🔴 `relatorios.py:286` — `qtd_atual < item.estoque_minimo` sem guarda.

    `estoque_minimo` é nullable, e uma única linha NULL derruba o relatório
    inteiro com `TypeError`. 📖 `dashboard.py` e `itens.py` guardam no mesmo
    cálculo; aqui não.
    """
    from models import AlmoxarifadoItem

    with app.app_context():
        t = um_tenant('onda4_alerta', com_fatos=False)
        suf = uuid.uuid4().hex[:8]
        item = AlmoxarifadoItem(
            admin_id=t.admin_id, nome=f'Sem mínimo {suf}', codigo=f'SM{suf}',
            tipo_controle='CONSUMIVEL', unidade='UN',
            categoria_id=_categoria_de(t.admin_id))
        db.session.add(item)
        db.session.commit()

        # ⚠️ O NULL entra por SQL, e isso é deliberado: a coluna é nullable no
        # banco, mas o ORM tem `default=0`, então escrever `estoque_minimo=None`
        # pelo modelo grava 0 e o teste passaria sem tocar o defeito — foi o que
        # aconteceu na primeira escrita. NULL chega por dado legado, migration
        # ou SQL direto, e é exatamente esse dado que derruba o relatório.
        db.session.execute(
            text('UPDATE almoxarifado_item SET estoque_minimo = NULL '
                 'WHERE id = :i'), {'i': item.id})
        db.session.commit()
        conferido = db.session.execute(
            text('SELECT estoque_minimo FROM almoxarifado_item WHERE id = :i'),
            {'i': item.id}).scalar()
        assert conferido is None, 'o NULL não entrou — teste vácuo'
        admin_id = t.admin_id

    resp = cliente_de(admin_id).get('/almoxarifado/relatorios?tipo=alertas')
    assert resp.status_code == 200, (
        f'alertas devolveu {resp.status_code} com estoque_minimo nulo')


def test_devolucao_multipla_encontra_o_item_em_uso():
    """🔴 `movimentos.py:1285` — `filter_by(funcionario_id=...)` num
    `AlmoxarifadoEstoque`, cuja coluna é `funcionario_atual_id`.

    🔬 A rota de item único (`:1055`) **acerta** o nome; esta erra, e o erro é
    engolido pelo `except Exception` da rota → toda devolução de carrinho
    serializado responde erro genérico, sem dizer o que houve.

    O teste afirma primeiro que o item ESTÁ em uso pelo funcionário — sem isso
    ele passaria verde por não encontrar nada, que é o próprio defeito.
    """
    from models import (AlmoxarifadoEstoque, AlmoxarifadoItem, Funcionario)

    with app.app_context():
        t = um_tenant('onda4_devol', com_fatos=False)
        func = Funcionario.query.filter_by(admin_id=t.admin_id).first()
        assert func is not None, 'tenant sem funcionário — teste vácuo'
        suf = uuid.uuid4().hex[:8]
        item = AlmoxarifadoItem(
            admin_id=t.admin_id, nome=f'Serializado {suf}', codigo=f'SR{suf}',
            tipo_controle='SERIALIZADO', unidade='UN',
            categoria_id=_categoria_de(t.admin_id))
        db.session.add(item)
        db.session.flush()
        estoque = AlmoxarifadoEstoque(
            admin_id=t.admin_id, item_id=item.id, numero_serie=f'NS{suf}',
            quantidade=1, status='EM_USO', funcionario_atual_id=func.id)
        db.session.add(estoque)
        db.session.commit()

        # A guarda contra verdade vácua: o item TEM de estar em uso por ele.
        conferido = AlmoxarifadoEstoque.query.filter_by(
            id=estoque.id, funcionario_atual_id=func.id,
            status='EM_USO', admin_id=t.admin_id).first()
        assert conferido is not None, 'o fixture não deixou o item em uso'
        admin_id, fid, eid, iid = t.admin_id, func.id, estoque.id, item.id
        serie = estoque.numero_serie

    resp = cliente_de(admin_id).post(
        '/almoxarifado/processar-devolucao-multipla',
        # ⚠️ `funcionario_id` vem DENTRO de cada item (`movimentos.py:1246`),
        # não no topo, e as condições válidas são capitalizadas ('Bom', não
        # 'BOM'). Com o payload errado a rota recusa antes do `filter_by` sob
        # teste, e o teste passaria verde sem provar nada.
        json={'itens': [{
            'funcionario_id': fid, 'item_id': iid, 'estoque_id': eid,
            'numero_serie': serie, 'quantidade': 1,
            'tipo_controle': 'SERIALIZADO', 'condicao_item': 'Bom'}]})

    corpo = resp.get_json() or {}
    assert resp.status_code == 200, (
        f'a devolução falhou: {resp.status_code} {corpo}')
    assert 'não está em uso pelo funcionário' not in str(corpo), (
        f'a devolução não achou o item que ESTÁ em uso: {corpo}')

    with app.app_context():
        from models import AlmoxarifadoEstoque as AE
        depois = AE.query.get(eid)
        assert depois.status == 'DISPONIVEL', (
            f'a rota disse sucesso e o item ficou em {depois.status}')


# ---------------------------------------------------------------------------
# Task 6 — o vocabulário partido do almoxarifado
# ---------------------------------------------------------------------------

VOCABULARIO_DE_ESTOQUE = {'DISPONIVEL', 'EM_USO', 'MANUTENCAO', 'DESCARTADO',
                          'CONSUMIDO'}


def _devolver_serializado(condicao):
    """Devolve um item serializado na condição pedida e devolve o status final.

    Vai pela rota, não pelo modelo: o vocabulário é partido entre quem ESCREVE
    (a rota de devolução) e quem LÊ (dashboard e relatório), e só a rota prova
    qual palavra é gravada de verdade.
    """
    from models import (AlmoxarifadoEstoque, AlmoxarifadoItem, Funcionario)

    with app.app_context():
        t = um_tenant(f'onda4_vocab_{condicao.lower()}', com_fatos=False)
        func = Funcionario.query.filter_by(admin_id=t.admin_id).first()
        assert func is not None, 'tenant sem funcionário — teste vácuo'
        suf = uuid.uuid4().hex[:8]
        item = AlmoxarifadoItem(
            admin_id=t.admin_id, nome=f'Vocab {suf}', codigo=f'VC{suf}',
            tipo_controle='SERIALIZADO', unidade='UN',
            categoria_id=_categoria_de(t.admin_id))
        db.session.add(item)
        db.session.flush()
        est = AlmoxarifadoEstoque(
            admin_id=t.admin_id, item_id=item.id, numero_serie=f'NS{suf}',
            quantidade=1, status='EM_USO', funcionario_atual_id=func.id)
        db.session.add(est)
        db.session.commit()
        admin_id, fid, eid, iid = t.admin_id, func.id, est.id, item.id
        serie = est.numero_serie

    resp = cliente_de(admin_id).post(
        '/almoxarifado/processar-devolucao-multipla',
        json={'itens': [{
            'funcionario_id': fid, 'item_id': iid, 'estoque_id': eid,
            'numero_serie': serie, 'quantidade': 1,
            'tipo_controle': 'SERIALIZADO', 'condicao_item': condicao}]})
    assert resp.status_code == 200, (
        f'a devolução em {condicao} falhou: {resp.status_code} {resp.get_json()}')

    with app.app_context():
        from models import AlmoxarifadoEstoque as AE
        return admin_id, AE.query.get(eid).status


@pytest.mark.parametrize('condicao', ['Danificado', 'Inutilizado'])
def test_devolucao_grava_o_vocabulario_da_definicao(condicao):
    """🔴 A rota gravava `EM_MANUTENCAO` e `INUTILIZADO`, e a definição
    (`models.py:5576`) diz `MANUTENCAO` e `DESCARTADO`.

    📖 O vocabulário estava partido no meio: `funcionario_perfil.html` e
    `itens_detalhes.html` testam `MANUTENCAO`, enquanto `dashboard.py` e
    `relatorios.py` casavam `EM_MANUTENCAO`. Item devolvido avariado não
    aparecia com selo em duas telas.
    """
    _, status = _devolver_serializado(condicao)
    assert status in VOCABULARIO_DE_ESTOQUE, (
        f'status {status!r} está fora do vocabulário da definição '
        f'{sorted(VOCABULARIO_DE_ESTOQUE)}')


def test_item_avariado_aparece_para_quem_le():
    """A prova de que escrita e leitura falam a MESMA palavra.

    ⚠️ Um teste que só olhasse o status gravado passaria mesmo com os leitores
    apontando para a palavra antiga — e o item continuaria invisível na tela.
    Este vai pela rota do relatório e exige o item lá dentro.
    """
    from flask import template_rendered

    admin_id, status = _devolver_serializado('Danificado')
    assert status == 'MANUTENCAO', f'gravou {status!r}'

    capturado = []

    def _registrar(sender, template, context, **extra):
        capturado.append(context)

    # ⚠️ Não existe `tipo=manutencao`: o bloco de manutenção é montado DENTRO
    # do ramo `alertas` (`relatorios.py:303`). Pedir um tipo que não existe cai
    # no ramo vazio e o teste passaria sem ler nada.
    template_rendered.connect(_registrar, app)
    try:
        resp = cliente_de(admin_id).get(
            '/almoxarifado/relatorios?tipo=alertas')
    finally:
        template_rendered.disconnect(_registrar, app)

    assert resp.status_code == 200, f'o relatório devolveu {resp.status_code}'
    assert capturado, 'nenhum template renderizado — teste vácuo'
    dados = capturado[-1].get('dados_relatorio') or {}
    manutencao = dados.get('manutencao') or []
    assert len(manutencao) >= 1, (
        'o item avariado não apareceu para quem lê — o vocabulário continua '
        'partido entre escrita e leitura')


# ---------------------------------------------------------------------------
# Task 7 — EVM e medição param de mentir
# ---------------------------------------------------------------------------

# ⚠️ O plano de 25/08 escreveu estes testes com `inspect.getsource`, checando se
# uma string de código sumiu. As Global Constraints do PRÓPRIO plano proíbem
# isso ("nenhum teste prova por inspect.getsource()"), e com razão: aquele teste
# passaria com o defeito intacto e o texto reescrito. Aqui as funções são
# CHAMADAS, com a forma de dado que `montar_fisico_financeiro` devolve de
# verdade — conferida na obra 1 do banco em 03/09.

def test_cpi_zero_nao_e_confundido_com_ausencia_de_cpi():
    """🔴 `services/evm.py:100` — `eac = (bac / _d(cpi)) if cpi else bac`.

    `cpi == 0.0` (EV=0 com AC>0, o **pior** cenário possível) é falsy e caía no
    ramo "ainda não gastou nada": EAC = BAC e **VAC = 0**, ou seja, "exatamente
    no orçamento". Já `cpi is None` significa de fato "sem dado".

    A projeção honesta quando o índice é zero é a fórmula sem CPI:
    EAC = AC + (BAC − EV) — o que já se gastou mais o que falta, ao custo
    orçado.
    """
    from services.evm import projetar_eac

    bac, ev, ac = Decimal('100000'), Decimal('0'), Decimal('30000')

    eac_sem_dado = projetar_eac(bac, ev, ac, None)
    assert eac_sem_dado == bac, (
        f'sem CPI a projeção deveria ser o próprio BAC, veio {eac_sem_dado}')

    eac_zero = projetar_eac(bac, ev, ac, 0.0)
    assert eac_zero != bac, (
        'CPI zero ainda é tratado como "sem CPI": EAC saiu igual ao BAC, '
        'e o VAC diria "exatamente no orçamento" no pior cenário possível')
    assert eac_zero == ac + (bac - ev), (
        f'esperado AC + (BAC − EV) = {ac + (bac - ev)}, veio {eac_zero}')


def test_pv_conta_a_etapa_de_periodo_que_o_bac_conta():
    """🔴 `services/evm.py:130` — o PV somava só `etapa['meses']`.

    🔬 Medido na obra 1 em 03/09: ela tem **duas etapas `periodo`** (Honorário
    de projeto, R$ 12.483,69; Mobilização, R$ 8.738,58) com `meses` **vazio** —
    `montar_fisico_financeiro` só faseia etapas `entregavel`. O BAC
    (`custo_orcado_da_obra`) soma TODA linha de custo, inclusive essas. PV menor
    que o universo do BAC dá **SPI estruturalmente inflado** e SV positivo em
    obra que está em dia.

    Custo de período é *level of effort*: sem fase própria, ele se apropria
    linearmente na janela da obra — que é o tratamento clássico, não uma
    invenção deste conserto.
    """
    from services.evm import _pv_ate_hoje

    hoje = date.today().strftime('%Y-%m')
    passado = '2020-01'
    dados = {
        'curva_s': {'meses': [passado, hoje]},
        'etapas': [
            {'nome': 'Entregável', 'tipo': 'entregavel',
             'meses': {passado: Decimal('1000')},
             'previsto': {'total': Decimal('1000')}},
            {'nome': 'Honorário', 'tipo': 'periodo', 'meses': {},
             'previsto': {'total': Decimal('400')}},
        ],
    }

    pv = _pv_ate_hoje(dados)
    assert pv > Decimal('1000'), (
        f'PV ficou em {pv}: a etapa de período não entrou, e o BAC a conta — '
        f'o SPI sai estruturalmente inflado')


def test_medicao_quinzenal_usa_o_fallback_que_o_vizinho_ja_usa():
    """🔴 `services/medicao_service.py:156` — `gerar_medicao_quinzenal` usa
    `calcular_percentual_item` e **omite o fallback** que
    `_recalcular_imc_avanco` tem 100 linhas abaixo.

    `calcular_percentual_item` devolve 0 quando o item não tem vínculo de
    cronograma. Sem o fallback por `servico_id`, essas obras geram medição
    **vazia para sempre** — `perc_periodo = max(0, 0 − 0) = 0` a cada ciclo — e
    o extrato PDF sai 0% enquanto o RDO mostra a obra andando.
    """
    from models import (Cliente, ItemMedicaoComercial, Obra, RDO,
                        RDOServicoSubatividade, Servico)
    from services.medicao_service import (calcular_percentual_item,
                                          gerar_medicao_quinzenal)

    with app.app_context():
        t = um_tenant('onda4_medicao', com_fatos=False)
        suf = uuid.uuid4().hex[:6]
        cli_obj = Cliente(admin_id=t.admin_id, nome=f'Cliente medição {suf}')
        db.session.add(cli_obj)
        db.session.flush()
        obra = Obra(admin_id=t.admin_id, nome=f'Obra medição {suf}',
                    data_inicio=date(2026, 7, 1), cliente_id=cli_obj.id)
        serv = Servico(admin_id=t.admin_id, nome=f'Serviço {suf}',
                       categoria='estrutura', unidade_medida='m2')
        db.session.add_all([obra, serv])
        db.session.flush()

        item = ItemMedicaoComercial(
            admin_id=t.admin_id, obra_id=obra.id, nome=f'Item {suf}',
            valor_comercial=Decimal('10000.00'), servico_id=serv.id)
        db.session.add(item)
        db.session.flush()

        # A fonte que o fallback lê: RDO finalizado com subatividade a 40%.
        rdo = RDO(admin_id=t.admin_id, obra_id=obra.id,
                  numero_rdo=f'RDO-{suf}', data_relatorio=date(2026, 7, 15),
                  status='Finalizado')
        db.session.add(rdo)
        db.session.flush()
        db.session.add(RDOServicoSubatividade(
            admin_id=t.admin_id, rdo_id=rdo.id, servico_id=serv.id,
            nome_subatividade='Execução', percentual_conclusao=40.0))
        db.session.commit()

        # As duas guardas contra verdade vácua: o item NÃO tem vínculo de
        # cronograma (senão não exercita o fallback), e o fallback TEM o que
        # devolver (senão a medição sairia vazia com razão).
        assert calcular_percentual_item(item) == Decimal('0'), (
            'o item tem vínculo de cronograma — não exercita o fallback')
        from services.progresso_subatividade import percentual_do_servico_na_obra
        assert percentual_do_servico_na_obra(serv.id, obra.id, t.admin_id), (
            'a fonte do fallback está vazia — o teste não provaria nada'
        )

        medicao, erro = gerar_medicao_quinzenal(
            obra.id, t.admin_id, periodo_inicio=date(2026, 7, 1),
            periodo_fim=date(2026, 7, 31))
        db.session.commit()

        assert medicao is not None, f'nenhuma medição foi gerada: {erro}'
        total = Decimal(str(medicao.valor_total_medido_periodo or 0))
        assert total > 0, (
            f'a medição nasceu vazia ({total}) apesar de o RDO finalizado '
            f'marcar 40% no serviço — é o fallback que falta')
