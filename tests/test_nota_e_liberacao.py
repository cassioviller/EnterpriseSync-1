"""A nota e a liberação — o fecho da Fase 2 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-17-nota-e-liberacao-design.md
Plano: docs/superpowers/plans/2026-08-17-plano-execucao-nota-e-liberacao.md

A Fase 2 entregou `lancar_nota()` e `liberar()` sem rota, sem template e sem
botão: toda `ContaPagar` do Fluxo A nascia `bloqueada` e não havia caminho no
app para destravá-la. Esta suíte cobre o caminho que faltava — e, no gate de
merge, o ciclo inteiro pela tela: emitir → atestar → lançar nota → liberar →
pagar.

Molde de tests/test_financeiro_dois_fluxos.py: fixtures locais, tenant por
uuid4, sem depender de seed.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, ContaPagar, Fornecedor, Obra, PedidoCompra,
                    PedidoCompraItem, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-nota-e-liberacao'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'nl_{suf}', email=f'nl_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _fornecedor(admin_id):
    f = Fornecedor(nome='Forn Teste', cnpj=uuid.uuid4().hex[:14],
                   admin_id=admin_id, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _pedido(admin_id, obra_id, fornecedor_id):
    p = PedidoCompra(
        numero=f'PC-{uuid.uuid4().hex[:6].upper()}',
        fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1),
        obra_id=obra_id, condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1625.00'), tipo_compra='normal',
        processada_apos_aprovacao=False, admin_id=admin_id)
    db.session.add(p)
    db.session.commit()
    db.session.add(PedidoCompraItem(
        pedido_id=p.id, descricao='Cimento CP-II', quantidade=Decimal('50'),
        preco_unitario=Decimal('32.50'), subtotal=Decimal('1625.00'),
        admin_id=admin_id))
    db.session.commit()
    return p


# ---------------------------------------------------------------------------
# N1 — a coluna da liberação excepcional
# ---------------------------------------------------------------------------

def test_conta_nova_nasce_sem_justificativa_de_liberacao():
    """`liberacao_justificativa` não-nulo SIGNIFICA liberação excepcional.

    Por isso o default é NULL e não string vazia: `''` seria uma exceção em
    branco, e a pergunta "quais contas foram liberadas por exceção" passaria a
    depender de quem lembrou de não escrever nada.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)

        cp = ContaPagar(
            fornecedor_id=forn.id, obra_id=obra.id, descricao='Conta de teste',
            valor_original=Decimal('1625.00'), saldo=Decimal('1625.00'),
            data_emissao=date(2026, 8, 1), data_vencimento=date(2026, 9, 1),
            admin_id=adm.id)
        db.session.add(cp)
        db.session.commit()

        assert cp.liberacao_justificativa is None


def test_coluna_existe_no_banco_e_e_nullable():
    """A migration 308 roda no banco de dev — e a coluna aceita NULL.

    Conta histórica não tem exceção a declarar, e é por isso que a 308 não tem
    backfill. Um NOT NULL aqui obrigaria a inventar um texto para 235 mil linhas
    que nunca passaram por exceção nenhuma.
    """
    from sqlalchemy import inspect
    with app.app_context():
        colunas = {c['name']: c
                   for c in inspect(db.engine).get_columns('conta_pagar')}
        assert 'liberacao_justificativa' in colunas, (
            'migration 308 não aplicada — rode o boot do app antes desta suíte')
        assert colunas['liberacao_justificativa']['nullable'] is True


# ---------------------------------------------------------------------------
# N2 — o serviço: a ressalva do D6, e `usuario` deixa de ser opcional
# ---------------------------------------------------------------------------

def _cfg_tenant(admin_id, **flags):
    """Cria/atualiza a ConfiguracaoEmpresa do tenant com as flags pedidas."""
    from models import ConfiguracaoEmpresa
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin_id,
                                  nome_empresa=f'Tenant {admin_id}')
        db.session.add(cfg)
    for k, v in flags.items():
        setattr(cfg, k, v)
    db.session.commit()
    return cfg


def _tenant_regime_novo():
    """Tenant com as duas flags ligadas + obra + fornecedor + pedido faturado."""
    adm = _admin()
    _cfg_tenant(adm.id, recebimento_atesto_ativo=True,
                financeiro_dois_fluxos_ativo=True)
    obra = _obra(adm.id)
    forn = _fornecedor(adm.id)
    ped = _pedido(adm.id, obra.id, forn.id)
    ped.exige_atesto = True
    ped.fluxo_pagamento = 'faturado'
    db.session.commit()
    return adm, obra, forn, ped


def _atestar(pedido, admin, qtd=Decimal('50')):
    """Fecha a perna do atesto — a que tem tela desde a Fase 1."""
    from services.recebimento_pedido import registrar_recebimento
    item = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).first()
    registrar_recebimento(pedido, usuario=admin, data=date(2026, 8, 10),
                          linhas=[(item.id, qtd)])
    db.session.commit()


def _notar(pedido, admin, valor=Decimal('1625.00')):
    """Fecha a perna da nota."""
    from services.financeiro_compra import lancar_nota
    lancar_nota(pedido, numero=uuid.uuid4().hex[:8], serie='1',
                valor_total=valor, data_emissao=date(2026, 8, 10),
                data_vencimento=date(2026, 9, 10), usuario=admin)
    db.session.commit()


RESSALVA = 'Fornecedor emite a nota so no fechamento do mes; material conferido.'


def test_ressalva_libera_a_conta_e_fica_gravada():
    """O D6 da Fase 2, finalmente operável.

    Material chegou, foi conferido, e a nota vem semanas depois. Sem esta porta
    o pagamento fica preso num ato administrativo do fornecedor — e quem paga o
    preço é a obra, que já recebeu.
    """
    from services.financeiro_compra import criar_obrigacao, liberar
    with app.app_context():
        adm, _obra_, _forn, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)          # atesto sim, nota NÃO

        contas = liberar(ped, usuario=adm, justificativa=RESSALVA)
        db.session.commit()

        assert len(contas) == 1
        cp = contas[0]
        assert cp.situacao_liberacao == 'liberada'
        assert cp.liberacao_justificativa == RESSALVA
        assert cp.liberada_por_id == adm.id
        assert cp.liberada_em is not None


def test_ressalva_curta_demais_e_recusada():
    """Campo vazio e "ok" são a mesma coisa para quem for auditar.

    O mínimo não é burocracia: é o que separa uma exceção explicada de um
    clique a mais no caminho de sempre.
    """
    from services.financeiro_compra import (RessalvaInvalida, criar_obrigacao,
                                            liberar)
    with app.app_context():
        adm, _obra_, _forn, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)

        with pytest.raises(RessalvaInvalida):
            liberar(ped, usuario=adm, justificativa='ok')

        db.session.rollback()
        cp = ContaPagar.query.filter_by(pedido_compra_id=ped.id).first()
        assert cp.situacao_liberacao == 'bloqueada'
        assert cp.liberacao_justificativa is None


def test_sem_ressalva_o_comportamento_e_o_de_hoje():
    """A fronteira nº 5 do plano: esta fase não afrouxa a Fase 2.

    Se este teste precisar ser reescrito para passar, alguma coisa saiu do
    lugar — a ressalva é uma porta a mais, não uma porta mais larga.
    """
    from services.financeiro_compra import (TriadeIncompleta, criar_obrigacao,
                                            liberar)
    with app.app_context():
        adm, _obra_, _forn, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)

        with pytest.raises(TriadeIncompleta) as erro:
            liberar(ped, usuario=adm)

        assert 'nota' in str(erro.value).lower()


def test_triade_fechada_nao_grava_ressalva_mesmo_se_ela_vier():
    """Não houve exceção — gravar sugeriria uma.

    `liberacao_justificativa` não-nulo é a definição de liberação excepcional.
    Deixar o texto entrar quando a tríade fechou faria o relatório de exceções
    contar liberações normais, e um relatório que conta o normal deixa de
    apontar o anormal.
    """
    from services.financeiro_compra import criar_obrigacao, liberar
    with app.app_context():
        adm, _obra_, _forn, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        _notar(ped, adm)

        contas = liberar(ped, usuario=adm, justificativa=RESSALVA)
        db.session.commit()

        assert contas[0].situacao_liberacao == 'liberada'
        assert contas[0].liberacao_justificativa is None


def _emergencia_vencida(admin_id, obra_id, usuario):
    """RequisicaoCompra aprovada pelo rito de emergência há mais de 48h e nunca
    ratificada — o gatilho da sanção da Fase 3 (D5).

    Montada aqui pelos símbolos que a própria `alcada_compras` lê
    (`MARCA_EMERGENCIA` no motivo da transição para APROVADA), e não por
    chamada ao rito inteiro: o que este teste precisa provar é que a RESSALVA
    não passa por cima da sanção, não que o rito funciona — isso é da suíte
    das alçadas.
    """
    from datetime import datetime, timedelta
    from models import EstadoRequisicao, RequisicaoCompra, RequisicaoTransicao
    from services.alcada_compras import MARCA_EMERGENCIA

    req = RequisicaoCompra(
        numero=f'RC-2026-{uuid.uuid4().hex[:4].upper()}', admin_id=admin_id,
        obra_id=obra_id, solicitante_id=usuario.id,
        estado=EstadoRequisicao.APROVADA, valor_estimado=Decimal('1625.00'),
        justificativa='Bomba queimou e a concretagem e amanha',
        emergencial=True, ratificada_em=None, regime_alcada='avancado')
    db.session.add(req)
    db.session.commit()

    t = RequisicaoTransicao(
        requisicao_id=req.id, admin_id=admin_id,
        de_estado=EstadoRequisicao.AGUARDANDO_APROVACAO,
        para_estado=EstadoRequisicao.APROVADA, usuario_id=usuario.id,
        papel_aplicado='ADMIN', valor_no_momento=Decimal('1625.00'),
        motivo=f'{MARCA_EMERGENCIA} bomba queimou')
    db.session.add(t)
    db.session.commit()
    t.criado_em = datetime.utcnow() - timedelta(hours=72)
    db.session.commit()
    return req


def test_ressalva_nao_passa_por_cima_da_emergencia_vencida():
    """A sanção da Fase 3 não é perna da tríade, e não se dispensa por escrito.

    A emergência 48h não ratificada bloqueia a conta como PUNIÇÃO de um ato
    administrativo que não aconteceu — e o dinheiro é o único ponto onde ainda
    dá para parar (D5 das alçadas). Deixar a ressalva destravá-la apagaria o
    único lugar onde o rito morde.
    """
    from services.financeiro_compra import (TriadeIncompleta, criar_obrigacao,
                                            liberar)
    with app.app_context():
        adm, obra, _forn, ped = _tenant_regime_novo()
        req = _emergencia_vencida(adm.id, obra.id, adm)
        ped.requisicao_id = req.id
        db.session.commit()

        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        _notar(ped, adm)            # tríade INTEIRA fechada

        with pytest.raises(TriadeIncompleta) as erro:
            liberar(ped, usuario=adm, justificativa=RESSALVA)

        assert 'ratifica' in str(erro.value).lower(), (
            'a recusa tem de nomear a emergência, não falar de nota')

        db.session.rollback()
        cp = ContaPagar.query.filter_by(pedido_compra_id=ped.id).first()
        assert cp.situacao_liberacao == 'bloqueada'


def test_lancar_nota_sem_usuario_recusa_com_erro_de_dominio():
    """🔴 O default `usuario=None` mentia sobre o contrato.

    `lancada_por_id` é NOT NULL (models.py + migration 287), então chamar sem
    usuário não dava erro de domínio: estourava IntegrityError e **abortava a
    transação inteira** — exatamente o que o resto de `lancar_nota` existe para
    evitar (ver o comentário da conferência de duplicidade).
    """
    from sqlalchemy.exc import IntegrityError
    from services.financeiro_compra import lancar_nota
    with app.app_context():
        adm, _obra_, _forn, ped = _tenant_regime_novo()

        with pytest.raises(Exception) as erro:
            lancar_nota(ped, numero='7777', serie='1',
                        valor_total=Decimal('100.00'),
                        data_emissao=date(2026, 8, 10))

        assert not isinstance(erro.value, IntegrityError), (
            'tem de recusar ANTES do INSERT — IntegrityError aborta a '
            'transação de quem estava no meio de um lançamento')


# ---------------------------------------------------------------------------
# N3 — a tela da nota
# ---------------------------------------------------------------------------

def _flashes(cli):
    with cli.session_transaction() as s:
        return ' | '.join(m for _cat, m in s.get('_flashes', []))


def _funcionario_do_tenant(admin_id):
    """Usuário autenticado que NÃO é admin — quem a D1 mantém de fora."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'func_{suf}', email=f'func_{suf}@test.local',
        nome=f'Func {suf}', password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, versao_sistema='v2',
        admin_id=admin_id)
    db.session.add(u)
    db.session.commit()
    return u


def test_nota_de_pedido_de_outro_tenant_da_404():
    """Por FILTRO com admin_id, não por get() seguido de comparação.

    O achado nº 2 de 03/08 (`detalhes_obra`) foi exatamente isto: buscar por id
    e conferir o tenant depois deixa a linha carregada na sessão, e o passo
    seguinte esquece de conferir. Filtrar é o que torna o esquecimento
    impossível.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        adm_a, _o, _f, ped_a = _tenant_regime_novo()
        ped_id = ped_a.id
        adm_b = _admin()
        adm_b_id = adm_b.id

    resposta = cliente_de(adm_b_id).get(f'/compras/{ped_id}/nota')
    assert resposta.status_code == 404


def test_nao_admin_nao_lanca_nota():
    """D1: lançar e liberar são atos de ADMIN do tenant."""
    from helpers_tenant import cliente_de
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        func = _funcionario_do_tenant(adm.id)
        ped_id, func_id = ped.id, func.id

    resposta = cliente_de(func_id).post(
        f'/compras/{ped_id}/nota',
        data={'numero': '123', 'valor_total': '1625,00',
              'data_emissao': '2026-08-10'})
    assert resposta.status_code == 403

    with app.app_context():
        from models import NotaFiscalPedido
        assert NotaFiscalPedido.query.filter_by(pedido_id=ped_id).count() == 0


def test_pedido_do_regime_antigo_recusa_com_a_razao_dita():
    """Nota em pedido sem tríade é linha órfã: não bloqueia nem libera nada.

    A recusa explicada é o padrão da casa desde a Fase 1 — um no-op silencioso
    é pior, porque quem clicou acha que registrou.
    """
    from helpers_tenant import cliente_de
    from models import NotaFiscalPedido
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        ped.fluxo_pagamento = 'adiantamento'   # Fluxo B: conta nasce liberada
        db.session.commit()
        adm_id, ped_id = adm.id, ped.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/nota',
                        data={'numero': '123', 'valor_total': '1625,00',
                              'data_emissao': '2026-08-10'})

    assert resposta.status_code == 302
    assert 'fluxo a' in _flashes(cli).lower()
    with app.app_context():
        assert NotaFiscalPedido.query.filter_by(pedido_id=ped_id).count() == 0


def test_nota_duplicada_vira_aviso_e_nao_500():
    """A mensagem do serviço já é escrita para o operador — a rota só repassa."""
    from helpers_tenant import cliente_de
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        adm_id, ped_id = adm.id, ped.id

    cli = cliente_de(adm_id)
    dados = {'numero': '4242', 'serie': '1', 'valor_total': '1625,00',
             'data_emissao': '2026-08-10'}
    assert cli.post(f'/compras/{ped_id}/nota', data=dados).status_code == 302
    resposta = cli.post(f'/compras/{ped_id}/nota', data=dados)

    assert resposta.status_code == 302, 'duplicada não pode virar 500'
    assert 'já foi lançada' in _flashes(cli)

    with app.app_context():
        from models import NotaFiscalPedido
        assert NotaFiscalPedido.query.filter_by(pedido_id=ped_id).count() == 1


def test_valor_ambiguo_e_recusado_em_vez_de_chutado():
    """"1.500" vale mil e quinhentos ou um e meio — e chutar erra por 1000×.

    A tela nasce usando `_quantidade_do_form`, que RECUSA o ambíguo. É o achado
    nº 6 da revisão da Fase 3, que ficou em aberto lá porque consertar só num
    lugar criaria divergência; aqui a tela é nova e nasce certa.
    """
    from helpers_tenant import cliente_de
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        adm_id, ped_id = adm.id, ped.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/nota',
                        data={'numero': '9', 'valor_total': '1.500',
                              'data_emissao': '2026-08-10'})

    assert resposta.status_code == 302
    with app.app_context():
        from models import NotaFiscalPedido
        assert NotaFiscalPedido.query.filter_by(pedido_id=ped_id).count() == 0


def test_excluir_nota_com_a_conta_ainda_bloqueada():
    """Quem digitou errado precisa do número de volta (D5)."""
    from helpers_tenant import cliente_de
    from models import NotaFiscalPedido
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _notar(ped, adm)
        nf_id = NotaFiscalPedido.query.filter_by(pedido_id=ped.id).first().id
        adm_id, ped_id = adm.id, ped.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/nota/{nf_id}/excluir')

    assert resposta.status_code == 302
    with app.app_context():
        assert NotaFiscalPedido.query.filter_by(pedido_id=ped_id).count() == 0


def test_excluir_nota_de_conta_ja_liberada_e_recusado():
    """Depois de liberada, a nota é premissa de um ato já praticado.

    Apagá-la deixaria a liberação apoiada em nada — e o sensor passaria a ver
    uma conta liberada sem tríade, que é a assinatura de UPDATE na marra.
    """
    from helpers_tenant import cliente_de
    from models import NotaFiscalPedido
    from services.financeiro_compra import criar_obrigacao, liberar
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        _notar(ped, adm)
        liberar(ped, usuario=adm)
        db.session.commit()
        nf_id = NotaFiscalPedido.query.filter_by(pedido_id=ped.id).first().id
        adm_id, ped_id = adm.id, ped.id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/nota/{nf_id}/excluir')

    assert resposta.status_code == 302
    assert 'liberada' in _flashes(cli).lower()
    with app.app_context():
        assert NotaFiscalPedido.query.filter_by(pedido_id=ped_id).count() == 1


# ---------------------------------------------------------------------------
# N4 — o painel da tríade e o botão de liberar
# ---------------------------------------------------------------------------

def test_liberar_pela_tela_e_entao_a_baixa_passa():
    """⭐ O gate de merge desta fase.

    Emitir → atestar → lançar nota → liberar → pagar, tudo por rota. É o ciclo
    que a Fase 2 nunca conseguiu executar sem shell, e é o motivo de esta fase
    existir. Se só um teste daqui sobreviver, é este.
    """
    from helpers_tenant import cliente_de
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        adm_id, ped_id = adm.id, ped.id
        conta_id = ContaPagar.query.filter_by(pedido_compra_id=ped_id).first().id

    cli = cliente_de(adm_id)

    # 1. a nota, pela tela
    assert cli.post(f'/compras/{ped_id}/nota',
                    data={'numero': '5150', 'serie': '1',
                          'valor_total': '1625,00',
                          'data_emissao': '2026-08-10'}).status_code == 302

    # 2. a liberação, pela tela
    assert cli.post(f'/compras/{ped_id}/liberar').status_code == 302
    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert cp.situacao_liberacao == 'liberada'
        assert cp.liberada_por_id == adm_id
        assert cp.liberacao_justificativa is None, 'não houve exceção nenhuma'

    # 3. a baixa, que até 17/08 era impossível de alcançar
    cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar',
             data={'valor_pago': '1625.00', 'data_pagamento': '2026-08-20',
                   'forma_pagamento': 'PIX'})
    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert float(cp.valor_pago or 0) == 1625.00, (
            'o ciclo não fechou: a baixa não foi gravada')


def test_liberar_sem_a_triade_recusa_nomeando_a_perna():
    from helpers_tenant import cliente_de
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)          # sem nota
        adm_id, ped_id = adm.id, ped.id
        conta_id = ContaPagar.query.filter_by(pedido_compra_id=ped_id).first().id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/liberar')

    assert resposta.status_code == 302
    assert 'nota' in _flashes(cli).lower()
    with app.app_context():
        assert db.session.get(
            ContaPagar, conta_id).situacao_liberacao == 'bloqueada'


def test_liberar_com_ressalva_pela_tela():
    """A porta de escape do D6, do jeito que o operador a encontra."""
    from helpers_tenant import cliente_de
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        adm_id, ped_id = adm.id, ped.id
        conta_id = ContaPagar.query.filter_by(pedido_compra_id=ped_id).first().id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/liberar',
                        data={'justificativa': RESSALVA})

    assert resposta.status_code == 302
    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert cp.situacao_liberacao == 'liberada'
        assert cp.liberacao_justificativa == RESSALVA


def test_ressalva_curta_pela_tela_devolve_o_texto_e_nao_libera():
    """`RessalvaInvalida` existe para que esta tela seja diferente da outra.

    "Faltou perna" OFERECE o campo; "a justificativa não serve" devolve o campo
    preenchido com o que a pessoa escreveu. Com uma exceção só, as duas telas
    seriam a mesma e o texto se perderia.
    """
    from helpers_tenant import cliente_de
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        adm_id, ped_id = adm.id, ped.id
        conta_id = ContaPagar.query.filter_by(pedido_compra_id=ped_id).first().id

    cli = cliente_de(adm_id)
    resposta = cli.post(f'/compras/{ped_id}/liberar',
                        data={'justificativa': 'ok'})

    assert resposta.status_code == 302
    assert 'caracteres' in _flashes(cli).lower()
    with app.app_context():
        assert db.session.get(
            ContaPagar, conta_id).situacao_liberacao == 'bloqueada'


def test_nao_admin_nao_libera():
    from helpers_tenant import cliente_de
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, _o, _f, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()
        _atestar(ped, adm)
        _notar(ped, adm)
        func = _funcionario_do_tenant(adm.id)
        ped_id, func_id = ped.id, func.id
        conta_id = ContaPagar.query.filter_by(pedido_compra_id=ped_id).first().id

    assert cliente_de(func_id).post(
        f'/compras/{ped_id}/liberar').status_code == 403
    with app.app_context():
        assert db.session.get(
            ContaPagar, conta_id).situacao_liberacao == 'bloqueada'


def test_paridade_com_a_flag_desligada():
    """A fronteira nº 4 do plano: esta fase não tem flag própria.

    Com `financeiro_dois_fluxos_ativo` DESLIGADA nada pode mudar — a conta
    nasce liberada, o painel não aparece na tela do pedido, e a baixa passa
    como sempre passou. Conferido por SELECT, não pela ORM.
    """
    from sqlalchemy import text as sa_text
    from helpers_tenant import cliente_de
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, recebimento_atesto_ativo=False,
                    financeiro_dois_fluxos_ativo=False)
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)
        criar_obrigacao(ped)
        db.session.commit()
        adm_id, ped_id = adm.id, ped.id
        linha = db.session.execute(sa_text(
            'SELECT situacao_liberacao, liberacao_justificativa '
            'FROM conta_pagar WHERE pedido_compra_id = :p'),
            {'p': ped_id}).fetchone()
        assert linha[0] == 'liberada' and linha[1] is None

    cli = cliente_de(adm_id)
    corpo = cli.get(f'/compras/{ped_id}').get_data(as_text=True)
    assert 'Liberar para pagamento' not in corpo, (
        'o botão apareceu num tenant que não ligou a Fase 2')
