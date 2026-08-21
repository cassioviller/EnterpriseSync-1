"""Financeiro em dois fluxos — fase 2 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md
Plano: docs/superpowers/plans/2026-08-14-plano-execucao-financeiro-dois-fluxos.md

A obrigação passa a nascer do que chegou, não do que foi pedido: no Fluxo A a
`ContaPagar` só é pagável com pedido + nota + atesto (a tríade), e no Fluxo B o
adiantamento fica numa lista de espera até o atesto baixá-lo.

Molde de tests/test_recebimento_atesto.py: fixtures locais, tenant por uuid4,
sem depender de seed.
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
        app.secret_key = 'test-financeiro-dois-fluxos'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'fin_{suf}', email=f'fin_{suf}@test.local', nome=f'Adm {suf}',
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
# F1 — o esqueleto: modelos, constraints e os defaults do regime
# ---------------------------------------------------------------------------

def test_modelos_da_fase_existem():
    """As duas tabelas novas do spec são importáveis de `models`."""
    from models import AdiantamentoFornecedor, NotaFiscalPedido
    assert NotaFiscalPedido.__tablename__ == 'nota_fiscal_pedido'
    assert AdiantamentoFornecedor.__tablename__ == 'adiantamento_fornecedor'


def test_nota_do_pedido_aceita_chave_de_acesso_nula():
    """A diferença deliberada em relação à `NotaFiscal` legada.

    Lá `chave_acesso` é NOT NULL **e** UNIQUE global (models.py:2640) — herdar
    isso obrigaria a chave de 44 dígitos para poder pagar, e metade das compras
    de obra chega com recibo ou nota de serviço. Este teste existe para que
    ninguém "conserte" a coluna para NOT NULL sem ler o spec.
    """
    from models import NotaFiscalPedido
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        nf = NotaFiscalPedido(
            pedido_id=ped.id, admin_id=adm.id, fornecedor_id=forn.id,
            numero='1234', serie='1', chave_acesso=None,
            valor_total=Decimal('1625.00'), data_emissao=date(2026, 8, 5),
            data_vencimento=date(2026, 9, 5), lancada_por_id=adm.id)
        db.session.add(nf)
        db.session.commit()

        assert nf.id is not None
        assert nf.chave_acesso is None


def test_nota_duplicada_do_mesmo_fornecedor_recusa():
    """UNIQUE (admin_id, fornecedor_id, numero, serie) — a mesma nota não entra
    duas vezes, e é o que impede pagar o mesmo papel duas vezes."""
    from sqlalchemy.exc import IntegrityError
    from models import NotaFiscalPedido
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        def _nota():
            return NotaFiscalPedido(
                pedido_id=ped.id, admin_id=adm.id, fornecedor_id=forn.id,
                numero='9001', serie='1', valor_total=Decimal('100.00'),
                data_emissao=date(2026, 8, 5), data_vencimento=date(2026, 9, 5),
                lancada_por_id=adm.id)

        db.session.add(_nota())
        db.session.commit()

        db.session.add(_nota())
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_defaults_descrevem_o_registro_historico():
    """Pedido nasce `faturado`, conta nasce `liberada`.

    Qualquer outro default trancaria o parque no dia do deploy: toda conta que
    já existe é pagável hoje, e a migration não pode mudar isso.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        assert ped.fluxo_pagamento == 'faturado'

        cp = ContaPagar(
            fornecedor_id=forn.id, obra_id=obra.id, descricao='Conta de teste',
            valor_original=Decimal('1625.00'), saldo=Decimal('1625.00'),
            data_emissao=date(2026, 8, 1), data_vencimento=date(2026, 9, 1),
            admin_id=adm.id)
        db.session.add(cp)
        db.session.commit()

        assert cp.situacao_liberacao == 'liberada'
        assert cp.liberada_por_id is None
        assert cp.liberada_em is None


def test_fechamento_ganhou_a_trilha_que_faltava():
    """`FechamentoPagamento` já existia e não registrava quem fechou.

    Sem `fechado_por_id` não há segregação possível: a regra "quem montou o
    lote não fecha o lote" precisa saber quem foi.
    """
    from models import FechamentoPagamento
    cols = {c.name for c in FechamentoPagamento.__table__.columns}
    assert {'fechado_por_id', 'fechado_em', 'reaberto_por_id'} <= cols


def test_flag_e_tolerancia_nascem_na_configuracao():
    """A virada é por tenant, e a tolerância da D1 é dado, não constante."""
    from models import ConfiguracaoEmpresa
    cols = {c.name for c in ConfiguracaoEmpresa.__table__.columns}
    assert 'financeiro_dois_fluxos_ativo' in cols
    assert 'tolerancia_divergencia_nf_pct' in cols


# ---------------------------------------------------------------------------
# F2 — a flag por tenant e o carimbo do fluxo
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


def test_ligar_recusa_tenant_sem_recebimento_atesto():
    """A dependência dura do spec, e ela mora no SCRIPT.

    Sem `recebimento_atesto_ativo` não existe a perna do atesto na tríade: a
    conta nasceria bloqueada sem caminho nenhum para liberar. Quem mexe por SQL
    direto não tem essa guarda — por isso ela tem de estar aqui, e não só na
    tela.
    """
    from scripts.flag_financeiro_dois_fluxos import pode_ligar
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, recebimento_atesto_ativo=False)

        ok, motivo = pode_ligar(adm.id)
        assert ok is False
        assert 'atesto' in motivo.lower(), (
            'o motivo é lido por humano: tem de nomear o que falta')

        _cfg_tenant(adm.id, recebimento_atesto_ativo=True)
        ok, _ = pode_ligar(adm.id)
        assert ok is True


def test_fluxo_do_tenant_segue_a_flag():
    """O que um pedido que nascer AGORA neste tenant seria."""
    from services.financeiro_compra import fluxo_do_tenant
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, recebimento_atesto_ativo=True,
                financeiro_dois_fluxos_ativo=False)
        assert fluxo_do_tenant(adm.id) is False

        _cfg_tenant(adm.id, financeiro_dois_fluxos_ativo=True)
        assert fluxo_do_tenant(adm.id) is True


def test_fluxo_do_tenant_falha_fechada():
    """Falha FECHADA para o comportamento ANTIGO.

    Numa flag que muda o momento em que a obrigação financeira nasce, o modo de
    falha seguro é o que já estava rodando ontem. Mesmo contrato de
    `recebimento_atesto_ativo`.
    """
    from services.financeiro_compra import fluxo_do_tenant
    with app.app_context():
        assert fluxo_do_tenant(None) is False
        assert fluxo_do_tenant(0) is False
        assert fluxo_do_tenant(10**9) is False   # tenant que não existe


def test_desligar_a_flag_nao_reescreve_pedido_ja_emitido():
    """O regime é carimbado na LINHA — desligar não reescreve o passado.

    Mesmo raciocínio de `exige_atesto` da Fase 1: um pedido que nasceu no
    Fluxo B continua sendo do Fluxo B, senão ligar e desligar a flag
    reinterpretaria adiantamento já pago como compra faturada.
    """
    from scripts.flag_financeiro_dois_fluxos import definir_flag
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        _cfg_tenant(adm.id, recebimento_atesto_ativo=True,
                financeiro_dois_fluxos_ativo=True)

        ped = _pedido(adm.id, obra.id, forn.id)
        ped.fluxo_pagamento = 'adiantamento'
        db.session.commit()

        definir_flag(adm.id, False)
        db.session.refresh(ped)
        assert ped.fluxo_pagamento == 'adiantamento'


def test_definir_flag_cria_a_configuracao_que_nao_existe():
    """Tenant que nunca abriu a tela de configurações não tem a linha, e
    `nome_empresa` é NOT NULL — estourar aqui seria transformar o rollout num
    chamado de suporte."""
    from models import ConfiguracaoEmpresa
    from scripts.flag_financeiro_dois_fluxos import definir_flag
    with app.app_context():
        adm = _admin()
        assert ConfiguracaoEmpresa.query.filter_by(admin_id=adm.id).first() is None

        definir_flag(adm.id, True)
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=adm.id).first()
        assert cfg is not None and cfg.financeiro_dois_fluxos_ativo is True


def test_todo_ponto_que_cria_pedido_carimba_o_fluxo():
    """Guarda de fonte: nenhum `PedidoCompra(...)` sem `fluxo_pagamento`.

    Irmão direto de `test_todo_ponto_que_cria_pedido_carimba_o_regime`
    (tests/test_recebimento_atesto.py), e existe pela lição que aquele aprendeu
    na C9: ele varria só `compras_views.py` e afirmava proteger contra "um
    terceiro ponto de criação" — que já existia, em `views/obras.py`, sem
    carimbo nenhum, com o teste verde.

    Um pedido criado sem carimbo cai em `faturado` pelo default da coluna.
    Silenciosamente: aquele caminho passa a prometer a tríade sem nunca ter
    decidido sobre ela, e ninguém descobre até uma conta ficar bloqueada sem
    explicação. Por `ast` e não regex, pelo mesmo motivo de lá — formatação não
    é contrato.

    Fica na F2 (e não na F7, com o guarda de `ContaPagar`) porque é o carimbo
    desta etapa que ele protege.
    """
    import ast

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ignorados = {'tests', '.pythonlibs', 'archive', 'node_modules',
                 '__pycache__', '.git', 'backups', 'attached_assets',
                 'migrations_backup', '.local', 'obra_kabod'}

    construcoes, sem_carimbo = [], []
    for pasta, subpastas, arquivos in os.walk(raiz):
        # Diretório oculto nunca é código do projeto — e .claude/worktrees/
        # guarda cópias INTEIRAS da árvore, que fariam este sensor ver
        # N pontos onde há um.
        subpastas[:] = [d for d in subpastas
                        if d not in ignorados and not d.startswith('.')]
        for nome in arquivos:
            if not nome.endswith('.py'):
                continue
            caminho = os.path.join(pasta, nome)
            try:
                with open(caminho, encoding='utf-8') as f:
                    arvore = ast.parse(f.read(), filename=caminho)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                alvo = no.func
                chamado = getattr(alvo, 'id', None) or getattr(alvo, 'attr', None)
                if chamado != 'PedidoCompra':
                    continue
                onde = f'{os.path.relpath(caminho, raiz)}:{no.lineno}'
                construcoes.append(onde)
                if not any(kw.arg == 'fluxo_pagamento' for kw in no.keywords):
                    sem_carimbo.append(onde)

    assert construcoes, 'nenhuma construção de PedidoCompra encontrada'
    assert not sem_carimbo, (
        f'{len(sem_carimbo)} de {len(construcoes)} construções de PedidoCompra '
        f'não carimbam `fluxo_pagamento`, e um pedido sem carimbo cai em '
        f'`faturado` pelo default da coluna — sem ninguém ter decidido. Use '
        f'`fluxo_do_pedido_novo(admin_id, escolha)` para pedido de usuário, ou '
        f"`'faturado'` explícito para dado histórico ou de demonstração.\n  "
        + '\n  '.join(sem_carimbo))


# ---------------------------------------------------------------------------
# F3 — o serviço: conta bloqueada, nota e liberação
# ---------------------------------------------------------------------------

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


def test_obrigacao_do_fluxo_a_nasce_bloqueada_com_o_valor_do_pedido():
    """Bloqueada, e NÃO com valor zero.

    O valor do atestado no instante da emissão é zero — nada chegou ainda. Uma
    conta de R$ 0,00 some de toda projeção de caixa, e o financeiro perderia a
    previsão, que é metade do valor do módulo. O reajuste para o atestado
    acontece na LIBERAÇÃO, não no nascimento.
    """
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()

        contas = criar_obrigacao(ped)
        db.session.commit()

        assert contas, 'a emissão tem de criar a obrigação, mesmo bloqueada'
        for cp in contas:
            assert cp.situacao_liberacao == 'bloqueada'
            assert cp.liberada_em is None
        assert sum(Decimal(str(c.valor_original)) for c in contas) == Decimal('1625.00')


def test_lancar_nota_recusa_duplicada_e_aceita_sem_chave():
    from services.financeiro_compra import lancar_nota, NotaDuplicada
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()

        nf = lancar_nota(ped, numero='555', serie='1',
                         valor_total=Decimal('1625.00'),
                         data_emissao=date(2026, 8, 5),
                         data_vencimento=date(2026, 9, 5),
                         usuario=adm)
        db.session.commit()
        assert nf.chave_acesso is None
        assert nf.lancada_por_id == adm.id

        with pytest.raises(NotaDuplicada):
            lancar_nota(ped, numero='555', serie='1',
                        valor_total=Decimal('1625.00'),
                        data_emissao=date(2026, 8, 5),
                        data_vencimento=date(2026, 9, 5), usuario=adm)
        db.session.rollback()


def test_pernas_faltantes_nomeia_o_que_falta():
    """Função PURA — é o que a tela e a mensagem de erro consomem.

    Pura porque a mensagem "sem nota lançada" tem de ser testável sem montar
    meio banco, e porque recusar sem dizer o que falta é o que faz usuário
    procurar o caminho de fora do sistema.
    """
    from services.financeiro_compra import lancar_nota, pernas_faltantes
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()

        faltam = pernas_faltantes(ped)
        assert 'nota' in ' '.join(faltam).lower()
        assert 'atesto' in ' '.join(faltam).lower()

        lancar_nota(ped, numero='777', serie='1',
                    valor_total=Decimal('1625.00'),
                    data_emissao=date(2026, 8, 5),
                    data_vencimento=date(2026, 9, 5), usuario=adm)
        db.session.commit()

        faltam = pernas_faltantes(ped)
        assert 'nota' not in ' '.join(faltam).lower()
        assert 'atesto' in ' '.join(faltam).lower()


def test_liberar_recusa_com_a_triade_incompleta():
    from services.financeiro_compra import TriadeIncompleta, criar_obrigacao, liberar
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()

        with pytest.raises(TriadeIncompleta) as exc:
            liberar(ped, usuario=adm)
        assert 'nota' in str(exc.value).lower()
        db.session.rollback()


def test_paridade_da_obrigacao_com_a_flag_desligada():
    """A prova de que mover a criação para o serviço não mudou nada.

    Este é o teste que autoriza o Step 3 da F3: com `financeiro_dois_fluxos_ativo`
    DESLIGADA, a `ContaPagar` que `processar_compra_normal` produz tem de ser a
    mesma de antes — mesmos valores, mesmas parcelas, mesma descrição, e
    `liberada`. Ler o diff não prova isso; contar as linhas no banco prova.
    """
    from compras_views import processar_compra_normal
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, recebimento_atesto_ativo=False,
                    financeiro_dois_fluxos_ativo=False)
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)

        processar_compra_normal(ped, [], adm.id, adm.id)
        db.session.commit()

        contas = ContaPagar.query.filter_by(pedido_compra_id=ped.id).all()
        assert len(contas) == 1
        cp = contas[0]
        assert cp.situacao_liberacao == 'liberada'
        assert Decimal(str(cp.valor_original)) == Decimal('1625.00')
        assert Decimal(str(cp.saldo)) == Decimal('1625.00')
        assert cp.status == 'PENDENTE'
        assert cp.origem_tipo == 'COMPRA'
        assert cp.parcela_numero == 1 and cp.parcela_total == 1
        assert cp.obra_id == obra.id
        assert 'Forn Teste' in cp.descricao


def test_liberar_reajusta_a_conta_para_o_que_chegou():
    """O momento em que `valor_atestado` finalmente é lido por alguém.

    Entrega parcial: pediu R$ 1.625,00 (50 × 32,50) e chegaram 30 — R$ 975,00.
    A conta tem de cair para o que veio, e a diferença tem de ficar ESCRITA, não
    sumida.
    """
    from services.financeiro_compra import criar_obrigacao, lancar_nota, liberar
    from services.recebimento_pedido import registrar_recebimento
    from models import PedidoCompraItem
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        criar_obrigacao(ped)
        db.session.commit()

        item = PedidoCompraItem.query.filter_by(pedido_id=ped.id).first()
        registrar_recebimento(
            ped, usuario=adm, data=date(2026, 8, 10),
            linhas=[(item.id, Decimal('30'))])
        lancar_nota(ped, numero='4242', serie='1',
                    valor_total=Decimal('975.00'),
                    data_emissao=date(2026, 8, 10),
                    data_vencimento=date(2026, 9, 10), usuario=adm)
        db.session.commit()

        contas = liberar(ped, usuario=adm)
        db.session.commit()

        assert len(contas) == 1
        cp = contas[0]
        assert cp.situacao_liberacao == 'liberada'
        assert cp.liberada_por_id == adm.id
        assert cp.liberada_em is not None
        assert Decimal(str(cp.valor_original)) == Decimal('975.00')
        assert 'ajustado' in (cp.observacoes or '').lower(), (
            'a diferença tem de ficar escrita — sumir com ela é o defeito')


# ---------------------------------------------------------------------------
# F4 — a tríade barra o pagamento
# ---------------------------------------------------------------------------

def _flashes(cli):
    with cli.session_transaction() as s:
        return ' | '.join(m for _cat, m in s.get('_flashes', []))


def _cenario_de_baixa(regime_novo=True):
    """Devolve ids — a rota roda em outro app_context."""
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, recebimento_atesto_ativo=regime_novo,
                    financeiro_dois_fluxos_ativo=regime_novo)
        obra = _obra(adm.id)
        forn = _fornecedor(adm.id)
        ped = _pedido(adm.id, obra.id, forn.id)
        ped.exige_atesto = regime_novo
        ped.fluxo_pagamento = 'faturado'
        db.session.commit()

        contas = criar_obrigacao(ped)
        db.session.commit()
        return adm.id, ped.id, contas[0].id


def test_pagar_conta_bloqueada_recusa_e_diz_o_que_falta():
    """Recusar sem dizer o que falta é o que manda o usuário para fora do
    sistema. A mensagem tem de nomear a perna."""
    from helpers_tenant import cliente_de
    admin_id, _ped_id, conta_id = _cenario_de_baixa(regime_novo=True)
    cli = cliente_de(admin_id)

    resposta = cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar',
                        data={'valor_pago': '1625.00',
                              'data_pagamento': '2026-08-20',
                              'forma_pagamento': 'PIX'})

    assert resposta.status_code == 302, 'a recusa redireciona, não estoura 500'
    msg = _flashes(cli).lower()
    assert 'nota' in msg, f'a mensagem não nomeia a perna que falta: {msg!r}'

    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert (cp.valor_pago or 0) == 0, 'a baixa foi gravada mesmo recusada'
        assert cp.status == 'PENDENTE'
        assert cp.situacao_liberacao == 'bloqueada'


def test_conta_liberada_continua_pagando_igual():
    """O caminho feliz não pode regredir — é metade do valor da guarda."""
    from helpers_tenant import cliente_de
    admin_id, _ped_id, conta_id = _cenario_de_baixa(regime_novo=True)

    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        cp.situacao_liberacao = 'liberada'
        db.session.commit()

    cli = cliente_de(admin_id)
    resposta = cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar',
                        data={'valor_pago': '1625.00',
                              'data_pagamento': '2026-08-20',
                              'forma_pagamento': 'PIX'})

    assert resposta.status_code == 302
    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert Decimal(str(cp.valor_pago or 0)) == Decimal('1625.00')
        assert cp.status == 'PAGO'


def test_paridade_da_baixa_com_a_flag_desligada():
    """Com o regime desligado, emitir e pagar produz o mesmo de sempre."""
    from helpers_tenant import cliente_de
    admin_id, _ped_id, conta_id = _cenario_de_baixa(regime_novo=False)

    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert cp.situacao_liberacao == 'liberada', (
            'fora do regime novo a conta não pode nascer bloqueada')

    cli = cliente_de(admin_id)
    resposta = cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar',
                        data={'valor_pago': '1625.00',
                              'data_pagamento': '2026-08-20',
                              'forma_pagamento': 'PIX'})

    assert resposta.status_code == 302
    with app.app_context():
        cp = db.session.get(ContaPagar, conta_id)
        assert Decimal(str(cp.valor_pago or 0)) == Decimal('1625.00')
        assert cp.status == 'PAGO'


def test_a_guarda_nao_e_engolida_pelo_except_do_post():
    """A guarda mora ANTES do `if POST` e FORA do try.

    A B5.1 documenta em financeiro_views.py:445 por quê: `abort()` dentro
    daquele try é capturado pelo `except Exception` e vira 200 com flash de
    'Erro ao registrar pagamento' — a recusa viraria erro genérico, e o usuário
    nunca saberia que faltava a nota.
    """
    from helpers_tenant import cliente_de
    admin_id, _ped_id, conta_id = _cenario_de_baixa(regime_novo=True)
    cli = cliente_de(admin_id)

    cli.post(f'/financeiro/contas-pagar/{conta_id}/pagar',
             data={'valor_pago': '1625.00', 'data_pagamento': '2026-08-20',
                   'forma_pagamento': 'PIX'})

    msg = _flashes(cli).lower()
    assert 'liberada' in msg, (
        f'a recusa não aconteceu ou não se identificou como tal: {msg!r}')
    assert 'erro ao registrar pagamento' not in msg, (
        'a recusa caiu no except genérico — a guarda está dentro do try')


# ---------------------------------------------------------------------------
# F5 — o fechamento ganha efeito e segregação
# ---------------------------------------------------------------------------

def _lote(admin_id, contas, criado_por_id):
    from models import FechamentoPagamento
    f = FechamentoPagamento(
        data_fechamento=date(2026, 8, 20), descricao='Lote de teste',
        status='ABERTO', admin_id=admin_id, criado_por_id=criado_por_id,
        total_selecionado=sum(Decimal(str(c.valor_original)) for c in contas))
    db.session.add(f)
    db.session.flush()
    for c in contas:
        c.fechamento_id = f.id
    db.session.commit()
    return f


def test_fechar_o_lote_libera_as_contas():
    """Fechar o lote é o caminho de usuário da liberação.

    A F3 fez `liberar()` existir; a F5 põe alguém para chamá-la — e é o
    fechamento do lote, feito por outra pessoa, que faz isso.
    """
    from services.financeiro_compra import (criar_obrigacao, fechar_lote,
                                            lancar_nota)
    from services.recebimento_pedido import registrar_recebimento
    from models import PedidoCompraItem
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        outro = _admin()
        contas = criar_obrigacao(ped)
        db.session.commit()

        item = PedidoCompraItem.query.filter_by(pedido_id=ped.id).first()
        registrar_recebimento(ped, usuario=adm, data=date(2026, 8, 10),
                              linhas=[(item.id, Decimal('50'))])
        lancar_nota(ped, numero='8001', serie='1',
                    valor_total=Decimal('1625.00'),
                    data_emissao=date(2026, 8, 10),
                    data_vencimento=date(2026, 9, 10), usuario=adm)
        f = _lote(adm.id, contas, criado_por_id=adm.id)

        fechar_lote(f, usuario=outro)
        db.session.commit()

        assert f.status == 'FECHADO'
        assert f.fechado_por_id == outro.id
        assert f.fechado_em is not None
        for c in contas:
            db.session.refresh(c)
            assert c.situacao_liberacao == 'liberada'


def test_quem_montou_o_lote_nao_o_fecha():
    """Invariante, não configuração — espelha solicitante != aprovador da Fase 3."""
    from services.financeiro_compra import SegregacaoViolada, criar_obrigacao, fechar_lote
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        contas = criar_obrigacao(ped)
        db.session.commit()
        f = _lote(adm.id, contas, criado_por_id=adm.id)

        with pytest.raises(SegregacaoViolada):
            fechar_lote(f, usuario=adm)
        db.session.rollback()
        assert f.status == 'ABERTO'


def test_reabrir_recusa_lote_com_conta_paga():
    """Lote fechado com pagamento é documento — reabrir seria reescrevê-lo."""
    from services.financeiro_compra import (LoteImutavel, criar_obrigacao,
                                            reabrir_lote)
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        outro = _admin()
        contas = criar_obrigacao(ped)
        db.session.commit()
        f = _lote(adm.id, contas, criado_por_id=adm.id)
        f.status = 'FECHADO'
        contas[0].status = 'PAGO'
        db.session.commit()

        with pytest.raises(LoteImutavel):
            reabrir_lote(f, usuario=outro)
        db.session.rollback()
        assert f.status == 'FECHADO'


def test_reabrir_grava_quem_reabriu():
    from services.financeiro_compra import criar_obrigacao, reabrir_lote
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        outro = _admin()
        contas = criar_obrigacao(ped)
        db.session.commit()
        f = _lote(adm.id, contas, criado_por_id=adm.id)
        f.status = 'FECHADO'
        db.session.commit()

        reabrir_lote(f, usuario=outro)
        db.session.commit()
        assert f.status == 'ABERTO'
        assert f.reaberto_por_id == outro.id


def test_lote_sem_autor_conhecido_nao_trava_o_fechamento():
    """Lote histórico não tem `criado_por_id` — a segregação exige DOIS lados.

    Exigir com um lado desconhecido travaria todo lote anterior à migration 296,
    e o efeito prático seria o time desligar a regra.
    """
    from services.financeiro_compra import criar_obrigacao, fechar_lote
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        contas = criar_obrigacao(ped)
        db.session.commit()
        f = _lote(adm.id, contas, criado_por_id=None)

        fechar_lote(f, usuario=adm)   # não levanta
        db.session.commit()
        assert f.status == 'FECHADO'


# ---------------------------------------------------------------------------
# F6 — Fluxo B: adiantamento e a lista de espera
# ---------------------------------------------------------------------------

def test_adiantamento_nasce_liberado_e_pendente_de_entrega():
    """No Fluxo B não há o que atestar ainda — o que fica pendente é a ENTREGA."""
    from models import AdiantamentoFornecedor
    from services.financeiro_compra import criar_obrigacao, registrar_adiantamento
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        ped.fluxo_pagamento = 'adiantamento'
        db.session.commit()

        contas = criar_obrigacao(ped)
        db.session.commit()
        assert all(c.situacao_liberacao == 'liberada' for c in contas)

        registrar_adiantamento(ped, valor=Decimal('812.50'),
                               conta_pagar=contas[0],
                               data_prevista_entrega=date(2026, 9, 1))
        db.session.commit()

        pend = AdiantamentoFornecedor.query.filter_by(
            pedido_id=ped.id, baixado_em=None).all()
        assert len(pend) == 1
        assert pend[0].pendente is True


def test_adiantamento_parcial_e_o_caso_comum():
    """50% na assinatura e 50% na entrega — D4. Duas linhas, não uma."""
    from models import AdiantamentoFornecedor
    from services.financeiro_compra import criar_obrigacao, registrar_adiantamento
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        ped.fluxo_pagamento = 'adiantamento'
        db.session.commit()
        contas = criar_obrigacao(ped)
        db.session.commit()

        registrar_adiantamento(ped, valor=Decimal('812.50'), conta_pagar=contas[0])
        registrar_adiantamento(ped, valor=Decimal('812.50'), conta_pagar=contas[0])
        db.session.commit()

        assert AdiantamentoFornecedor.query.filter_by(pedido_id=ped.id).count() == 2


def test_o_atesto_baixa_todos_os_adiantamentos_pendentes():
    """E SÓ o atesto baixa: baixa manual sem material é o buraco que a lista
    existe para tapar."""
    from models import AdiantamentoFornecedor, PedidoCompraItem
    from services.financeiro_compra import criar_obrigacao, registrar_adiantamento
    from services.recebimento_pedido import registrar_recebimento
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        ped.fluxo_pagamento = 'adiantamento'
        db.session.commit()
        contas = criar_obrigacao(ped)
        db.session.commit()
        registrar_adiantamento(ped, valor=Decimal('812.50'), conta_pagar=contas[0])
        registrar_adiantamento(ped, valor=Decimal('812.50'), conta_pagar=contas[0])
        db.session.commit()

        item = PedidoCompraItem.query.filter_by(pedido_id=ped.id).first()
        registrar_recebimento(ped, usuario=adm, data=date(2026, 8, 12),
                              linhas=[(item.id, Decimal('50'))])
        db.session.commit()

        pendentes = AdiantamentoFornecedor.query.filter_by(
            pedido_id=ped.id, baixado_em=None).count()
        assert pendentes == 0, 'o atesto não baixou os adiantamentos'


def test_a_lista_de_espera_nao_vaza_entre_tenants():
    from services.financeiro_compra import (adiantamentos_pendentes,
                                            criar_obrigacao,
                                            registrar_adiantamento)
    with app.app_context():
        adm_a, _o, _f, ped_a = _tenant_regime_novo()
        ped_a.fluxo_pagamento = 'adiantamento'
        db.session.commit()
        contas_a = criar_obrigacao(ped_a)
        db.session.commit()
        registrar_adiantamento(ped_a, valor=Decimal('100'), conta_pagar=contas_a[0])
        db.session.commit()

        adm_b, _o2, _f2, ped_b = _tenant_regime_novo()
        lista_b = adiantamentos_pendentes(adm_b.id)
        assert all(a.admin_id == adm_b.id for a in lista_b)
        assert ped_a.id not in [a.pedido_id for a in lista_b]


# ---------------------------------------------------------------------------
# F7 — consistência, teste-guarda e runbook
# ---------------------------------------------------------------------------

# Os pontos que criam `ContaPagar` fora do serviço de compra, com o motivo de
# cada um estar de fora. A lista é EXPLÍCITA de propósito: é ela que faz a
# PRÓXIMA criação em caminho de compra aparecer como falha, em vez de herdar o
# silêncio. Mesmo formato do guarda de regime da C9 (Fase 1), que foi quem
# provou que varredura acha o que leitura não acha.
CRIACOES_LEGITIMAS_DE_CONTA_PAGAR = {
    'custos_escritorio_views.py': 'custo de escritório — não é compra de obra',
    'event_manager.py': 'handler de evento — não passa por pedido',
    'financeiro_service.py': 'lançamento avulso pela tela do financeiro',
    'services/importacao_excel.py': 'import de planilha; nasce já PAGO',
    'services/financeiro_compra.py': 'O serviço — é aqui que a compra cria',
}


def test_so_o_servico_cria_conta_pagar_de_compra():
    """Guarda de fonte: nenhum `ContaPagar(...)` novo em caminho de compra.

    A F3 tirou a criação de `compras_views.py` e a pôs no serviço. Sem este
    teste, a próxima rota de compra que precisar de uma conta a criaria inline
    de novo — `situacao_liberacao` cairia no default 'liberada' e aquele caminho
    passaria a furar a tríade em silêncio, que é o defeito que a fase inteira
    existe para fechar.

    Por `ast` e não regex: formatação não é contrato.
    """
    import ast

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ignorados = {'tests', '.pythonlibs', 'archive', 'node_modules',
                 '__pycache__', '.git', 'backups', 'attached_assets',
                 'migrations_backup', '.local', 'obra_kabod'}

    inesperadas = []
    for pasta, subpastas, arquivos in os.walk(raiz):
        # Diretório oculto nunca é código do projeto — e .claude/worktrees/
        # guarda cópias INTEIRAS da árvore, que fariam este sensor ver
        # N pontos onde há um.
        subpastas[:] = [d for d in subpastas
                        if d not in ignorados and not d.startswith('.')]
        for nome in arquivos:
            if not nome.endswith('.py'):
                continue
            caminho = os.path.join(pasta, nome)
            try:
                with open(caminho, encoding='utf-8') as f:
                    arvore = ast.parse(f.read(), filename=caminho)
            except (SyntaxError, UnicodeDecodeError):
                continue
            rel = os.path.relpath(caminho, raiz)
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                chamado = (getattr(no.func, 'id', None)
                           or getattr(no.func, 'attr', None))
                if chamado != 'ContaPagar':
                    continue
                if rel not in CRIACOES_LEGITIMAS_DE_CONTA_PAGAR:
                    inesperadas.append(f'{rel}:{no.lineno}')

    assert not inesperadas, (
        'ContaPagar criada fora da lista conhecida:\n  '
        + '\n  '.join(inesperadas)
        + '\n\nSe for compra, use `services.financeiro_compra.criar_obrigacao` '
          '— senão a conta nasce `liberada` por default e aquele caminho fura '
          'a tríade em silêncio. Se NÃO for compra, acrescente o arquivo a '
          '`CRIACOES_LEGITIMAS_DE_CONTA_PAGAR` com o motivo por escrito.')


def test_a_criacao_de_compra_saiu_de_compras_views():
    """O que a F3 moveu não pode voltar sem alguém perceber."""
    import ast
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, 'compras_views.py'), encoding='utf-8') as f:
        arvore = ast.parse(f.read())
    criacoes = [no.lineno for no in ast.walk(arvore)
                if isinstance(no, ast.Call)
                and (getattr(no.func, 'id', None)
                     or getattr(no.func, 'attr', None)) == 'ContaPagar']
    assert not criacoes, (
        f'`compras_views.py` voltou a criar ContaPagar (linhas {criacoes}). '
        f'A camada de obrigação mora em services/financeiro_compra.py.')


def test_sensor_acha_conta_liberada_sem_a_triade():
    """O sensor grita quando alguém escreve `situacao_liberacao` na marra."""
    from scripts.verificar_consistencia_financeiro import inconsistencias
    from services.financeiro_compra import criar_obrigacao
    with app.app_context():
        adm, obra, forn, ped = _tenant_regime_novo()
        contas = criar_obrigacao(ped)
        db.session.commit()

        assert inconsistencias(adm.id) == [], (
            'conta bloqueada e sem tríade é o estado NORMAL — não é drift')

        contas[0].situacao_liberacao = 'liberada'   # na marra
        db.session.commit()

        achados = inconsistencias(adm.id)
        assert achados, 'o sensor não viu a conta liberada sem a tríade'
        assert any(str(contas[0].id) in str(a) for a in achados)


def test_sensor_ignora_o_regime_antigo():
    """Sensor que grita sempre não é lido nunca.

    Todo pedido legado tem conta `liberada` e nenhuma nota — varrer esses seria
    produzir drift de mentira em cada tenant que ainda não virou.
    """
    from scripts.verificar_consistencia_financeiro import inconsistencias
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

        assert inconsistencias(adm.id) == []
