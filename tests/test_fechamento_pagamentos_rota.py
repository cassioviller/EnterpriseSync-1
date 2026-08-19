"""O POST da tela do lote — passo (e) do runbook da Fase 2.

Achado de 19/08, rodando o runbook por script (`scripts/runbook_fase2.py`):
**a tela fechava o lote sem passar pelo serviço.** A ação `fechar` de
📖 `financeiro_views.fechamento_pagamentos` fazia `fech.status = 'FECHADO';
db.session.commit()` e pronto — `fechar_lote()` e `reabrir_lote()` tinham zero
chamadores de produção, e `financeiro_views.py` importava de
`services.financeiro_compra` só `pernas_faltantes`.

Consequência medida com quatro pessoas distintas: `criado_por_id` NULL,
`fechado_por_id` NULL, quem montou o lote fechando o próprio lote, e o sensor
acusando drift. A segregação de função é o ÚNICO controle que a Fase 2
acrescenta ao passo (e); sem ela o lote é agrupamento, não autorização.

**Por que a suíte não pegou:** `tests/test_financeiro_dois_fluxos.py` cobre
`fechar_lote()` — o serviço — e `test_fechamento_pagamentos_render.py` cobre o
GET. Ninguém exercitava o POST, então o serviço podia ficar sem chamador sem que
nada ficasse vermelho. É a terceira vez que este padrão aparece na Fase 2 (a
primeira foi `liberar()`, em 17/08), e é por isso que este arquivo existe: ele
testa a ROTA, não a regra.

Plano: docs/superpowers/plans/2026-08-19-plano-fechar-lote-pela-tela.md
Molde de fixtures: tests/test_financeiro_dois_fluxos.py
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
from models import (Cliente, ConfiguracaoEmpresa, ContaPagar, FechamentoPagamento,
                    Fornecedor, Obra, PedidoCompra, PedidoCompraItem, TipoUsuario,
                    Usuario)

pytestmark = pytest.mark.integration

ROTA = '/financeiro/fechamento-pagamentos'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fechamento-rota'
    yield


# ── o cenário ───────────────────────────────────────────────────────────────
def _usuario(tipo=TipoUsuario.ADMIN, admin_id=None):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'fpr_{suf}', email=f'fpr_{suf}@test.local', nome=f'Pessoa {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=tipo, admin_id=admin_id, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _cfg(admin_id, **flags):
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin_id, nome_empresa=f'Tenant {admin_id}')
        db.session.add(cfg)
    for k, v in flags.items():
        setattr(cfg, k, v)
    db.session.commit()
    return cfg


def _pedido_do_fluxo_a(admin_id):
    """Pedido faturado que exige atesto — o que faz a conta nascer bloqueada."""
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin_id,
                cliente_id=cliente.id, ativo=True)
    forn = Fornecedor(nome='Forn Teste', cnpj=uuid.uuid4().hex[:14],
                      admin_id=admin_id, ativo=True)
    db.session.add_all([obra, forn])
    db.session.commit()
    p = PedidoCompra(
        numero=f'PC-{uuid.uuid4().hex[:6].upper()}',
        fornecedor_id=forn.id, data_compra=date(2026, 8, 1),
        obra_id=obra.id, condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1625.00'), tipo_compra='normal',
        processada_apos_aprovacao=False, admin_id=admin_id,
        exige_atesto=True, fluxo_pagamento='faturado')
    db.session.add(p)
    db.session.commit()
    db.session.add(PedidoCompraItem(
        pedido_id=p.id, descricao='Cimento CP-II', quantidade=Decimal('50'),
        preco_unitario=Decimal('32.50'), subtotal=Decimal('1625.00'),
        admin_id=admin_id))
    db.session.commit()
    return p


def _conta_avulsa(admin_id, valor=Decimal('900.00')):
    """Conta PENDENTE vencendo hoje — entra na janela do ciclo em qualquer dia."""
    c = ContaPagar(
        descricao='Conta avulsa', valor_original=valor, saldo=valor,
        data_emissao=date.today(), data_vencimento=date.today(),
        status='PENDENTE', admin_id=admin_id)
    db.session.add(c)
    db.session.commit()
    return c


def _lote_aberto(admin_id, contas, criado_por_id=None):
    f = FechamentoPagamento(
        data_fechamento=date.today(), descricao='Lote de teste', status='ABERTO',
        admin_id=admin_id, criado_por_id=criado_por_id,
        total_selecionado=sum(Decimal(str(c.valor_original or 0)) for c in contas))
    db.session.add(f)
    db.session.flush()
    for c in contas:
        c.fechamento_id = f.id
    db.session.commit()
    return f


def _post(user_id, dados):
    from helpers_tenant import cliente_de
    return cliente_de(user_id).post(ROTA, data=dados, follow_redirects=True)


# ── 1. montar o lote carimba quem montou ────────────────────────────────────
def test_criar_o_lote_pela_tela_carimba_quem_montou():
    """Sem `criado_por_id` a segregação não tem com quem comparar.

    E o efeito é pior que perder a informação: o guarda de `fechar_lote` é
    `if criado_por is not None and quem_fecha is not None`, então um autor NULL
    faz a regra passar CALADA — ela não recusa e não avisa que não recusou.
    """
    with app.app_context():
        adm = _usuario()
        conta = _conta_avulsa(adm.id)
        adm_id, conta_id = adm.id, conta.id

    _post(adm_id, {'action': 'create',
                   'data_fechamento': date.today().isoformat(),
                   'descricao': 'Lote da tela',
                   'conta_ids': [str(conta_id)]})

    with app.app_context():
        f = FechamentoPagamento.query.filter_by(
            admin_id=adm_id, descricao='Lote da tela').first()
        assert f is not None, 'a tela não criou o lote'
        assert f.criado_por_id == adm_id, (
            'quem montou o lote não ficou registrado — sem este lado a '
            'segregação de função é inverificável')


# ── 2. fechar carimba o autor e libera as contas ────────────────────────────
def test_fechar_pela_tela_carimba_o_autor_e_libera_as_contas():
    """O fechamento é o ato que autoriza o pagamento — e o que o executa.

    Duas coisas num teste só de propósito: são o mesmo ato. `fechar_lote` chama
    `liberar()` para as contas bloqueadas do lote, e é esse caminho que a tela
    não percorria — a conta ficava bloqueada e o lote saía FECHADO, o que é a
    aparência da autorização sem a autorização.
    """
    from services.financeiro_compra import criar_obrigacao, lancar_nota
    from services.recebimento_pedido import registrar_recebimento
    with app.app_context():
        adm = _usuario()
        _cfg(adm.id, recebimento_atesto_ativo=True, financeiro_dois_fluxos_ativo=True)
        outro = _usuario(tipo=TipoUsuario.FUNCIONARIO, admin_id=adm.id)
        ped = _pedido_do_fluxo_a(adm.id)
        contas = criar_obrigacao(ped)
        db.session.commit()

        item = PedidoCompraItem.query.filter_by(pedido_id=ped.id).first()
        registrar_recebimento(ped, usuario=adm, data=date(2026, 8, 10),
                              linhas=[(item.id, Decimal('50'))])
        lancar_nota(ped, numero='7001', serie='1', valor_total=Decimal('1625.00'),
                    data_emissao=date(2026, 8, 10),
                    data_vencimento=date(2026, 9, 10), usuario=adm)
        db.session.commit()

        assert all(c.situacao_liberacao == 'bloqueada' for c in contas)
        f = _lote_aberto(adm.id, contas, criado_por_id=adm.id)
        f_id, outro_id, conta_ids = f.id, outro.id, [c.id for c in contas]

    _post(outro_id, {'action': 'fechar', 'fechamento_id': str(f_id)})

    with app.app_context():
        f = db.session.get(FechamentoPagamento, f_id)
        assert f.status == 'FECHADO'
        assert f.fechado_por_id == outro_id, (
            'fechado_por_id NULL é o que o runbook chama de "alguém fechou por '
            'SQL" — aqui foi a própria tela')
        assert f.fechado_em is not None
        for cid in conta_ids:
            assert db.session.get(ContaPagar, cid).situacao_liberacao == 'liberada', (
                'fechar o lote é o caminho de usuário da liberação')


# ── 3. quem montou é recusado sem justificativa ─────────────────────────────
def test_quem_montou_o_lote_e_recusado_ao_fechar_sem_justificativa():
    """A regra que dá sentido ao lote, exercida pela porta que o time usa."""
    with app.app_context():
        adm = _usuario()
        conta = _conta_avulsa(adm.id)
        f = _lote_aberto(adm.id, [conta], criado_por_id=adm.id)
        adm_id, f_id = adm.id, f.id

    resposta = _post(adm_id, {'action': 'fechar', 'fechamento_id': str(f_id)})

    with app.app_context():
        f = db.session.get(FechamentoPagamento, f_id)
        assert f.status == 'ABERTO', 'quem montou o lote fechou o próprio lote'
        assert f.fechado_por_id is None
    corpo = resposta.get_data(as_text=True)
    assert 'outra pessoa' in corpo, (
        'a recusa tem de dizer o que fazer — recusar sem saída empurra a '
        'compra para fora do sistema')


# ── 4. …e aceito COM justificativa, que fica gravada ────────────────────────
def test_quem_montou_o_lote_fecha_com_justificativa_e_ela_fica_gravada():
    """A saída decidida em 19/08 (opção b), no molde da ressalva do D6.

    Sem saída, o financeiro de uma pessoa só fica com um lote que ninguém pode
    fechar — e regra que atrapalha sem proteger é regra que o time desliga. Com
    ela a exceção continua possível e deixa de ser silenciosa: o texto fica
    gravado e o lote sai marcado no sensor.
    """
    with app.app_context():
        adm = _usuario()
        conta = _conta_avulsa(adm.id)
        f = _lote_aberto(adm.id, [conta], criado_por_id=adm.id)
        adm_id, f_id = adm.id, f.id

    motivo = 'Somos dois no financeiro e a Helena está de férias esta semana.'
    _post(adm_id, {'action': 'fechar', 'fechamento_id': str(f_id),
                   'justificativa': motivo})

    with app.app_context():
        f = db.session.get(FechamentoPagamento, f_id)
        assert f.status == 'FECHADO'
        assert f.fechado_por_id == adm_id
        assert f.segregacao_justificativa == motivo, (
            'a exceção tem de ficar escrita — é o que a separa de um clique a mais')


def test_a_justificativa_curta_nao_serve():
    """Campo vazio e "ok" são a mesma coisa para quem for auditar."""
    with app.app_context():
        adm = _usuario()
        conta = _conta_avulsa(adm.id)
        f = _lote_aberto(adm.id, [conta], criado_por_id=adm.id)
        adm_id, f_id = adm.id, f.id

    _post(adm_id, {'action': 'fechar', 'fechamento_id': str(f_id),
                   'justificativa': 'ok'})

    with app.app_context():
        f = db.session.get(FechamentoPagamento, f_id)
        assert f.status == 'ABERTO'
        assert f.segregacao_justificativa is None


# ── 5. reabrir respeita o pagamento já feito ────────────────────────────────
def test_reabrir_pela_tela_recusa_lote_com_conta_paga():
    """Lote fechado com pagamento é documento, não rascunho.

    `reabrir_lote()` levanta `LoteImutavel` — e, como o `fechar`, nunca era
    chamado pela rota: a tela devolvia o lote a ABERTO com o dinheiro já fora.
    """
    with app.app_context():
        adm = _usuario()
        conta = _conta_avulsa(adm.id)
        conta.status = 'PAGO'
        conta.valor_pago = conta.valor_original
        conta.saldo = Decimal('0')
        f = _lote_aberto(adm.id, [conta], criado_por_id=adm.id)
        f.status = 'FECHADO'
        db.session.commit()
        adm_id, f_id = adm.id, f.id

    resposta = _post(adm_id, {'action': 'reabrir', 'fechamento_id': str(f_id)})

    with app.app_context():
        assert db.session.get(FechamentoPagamento, f_id).status == 'FECHADO', (
            'reabrir um lote com conta paga reescreve uma autorização que já '
            'virou saída de dinheiro')
    assert 'estorne' in resposta.get_data(as_text=True).lower(), (
        'a recusa tem de apontar o caminho certo, que é o estorno')


# ── 6. paridade: o tenant que não virou fecha como sempre fechou ────────────
def test_tenant_com_a_flag_desligada_fecha_o_lote_como_antes():
    """O bloco novo é inerte para quem não ligou a flag.

    É a mesma medida que a Fase 2 faz desde o começo: nenhuma conta é bloqueada
    fora do regime novo, então `fechar_lote` não tem o que liberar e o
    fechamento continua sendo o que sempre foi — agora com autor.
    """
    with app.app_context():
        adm = _usuario()
        _cfg(adm.id, recebimento_atesto_ativo=False, financeiro_dois_fluxos_ativo=False)
        outro = _usuario(tipo=TipoUsuario.FUNCIONARIO, admin_id=adm.id)
        conta = _conta_avulsa(adm.id)
        f = _lote_aberto(adm.id, [conta], criado_por_id=adm.id)
        f_id, outro_id, conta_id = f.id, outro.id, conta.id

    _post(outro_id, {'action': 'fechar', 'fechamento_id': str(f_id)})

    with app.app_context():
        f = db.session.get(FechamentoPagamento, f_id)
        assert f.status == 'FECHADO'
        assert f.fechado_por_id == outro_id
        c = db.session.get(ContaPagar, conta_id)
        assert c.situacao_liberacao == 'liberada', (
            'fora do regime novo a conta já nasce liberada e nada muda nela')
