"""Alçadas avançadas — fase 3 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-15-alcadas-design.md
Plano: docs/superpowers/plans/2026-08-15-plano-execucao-alcadas.md

O valor deixa de ser a única pergunta: as quatro condições que sobem um degrau,
o anti-fracionamento por janela, o rito de emergência 48h e o corte de cotações
que vira dado da faixa.

Molde de tests/test_financeiro_dois_fluxos.py: fixtures locais, tenant por
uuid4, sem depender de seed.

A1 — só o esqueleto. Estes testes cobrem os DEFAULTS das colunas novas, e
default aqui não é detalhe: cada um deles é a descrição do registro histórico.
Requisição que já existia é `'simples'`, não emergencial e sem degrau; faixa
que já existia não exige cotação nenhuma por dado e não sobe degrau por
condição nenhuma; tenant que já existia tem a flag desligada. É o que garante
que a migration não reescreve o passado.
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
from models import (Cliente, ConfiguracaoEmpresa, EstadoRequisicao, FaixaAlcada,
                    Obra, RequisicaoCompra, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-alcadas-avancadas'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'alc_{suf}', email=f'alc_{suf}@test.local', nome=f'Adm {suf}',
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


def _faixa(admin_id, ordem=1, valor_ate=Decimal('5000.00')):
    f = FaixaAlcada(admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
                    aprovacoes_necessarias=1, exige_admin=False,
                    exige_mapa_concorrencia=False, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _requisicao(admin_id, obra_id, solicitante_id):
    r = RequisicaoCompra(
        numero=f'RC-{uuid.uuid4().hex[:8].upper()}', admin_id=admin_id,
        obra_id=obra_id, solicitante_id=solicitante_id,
        estado=EstadoRequisicao.RASCUNHO,
        valor_estimado=Decimal('4900.00'))
    db.session.add(r)
    db.session.commit()
    return r


def _configuracao(admin_id):
    cfg = ConfiguracaoEmpresa(admin_id=admin_id,
                              nome_empresa=f'Tenant {admin_id}')
    db.session.add(cfg)
    db.session.commit()
    return cfg


def _cfg_tenant(admin_id, **flags):
    """Cria ou atualiza a ConfiguracaoEmpresa do tenant com as flags dadas.

    Molde de tests/test_financeiro_dois_fluxos._cfg_tenant. As fixtures desta
    fase ligam `escopo_obra_ativo` E `compras_governanca_ativa` por padrão —
    sem as duas, `papel_na_obra` devolve GESTOR a todo autenticado e nenhum
    teste de papel distingue ninguém (📖 spec, "Regime de virada").
    """
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin_id,
                                  nome_empresa=f'Tenant {admin_id}')
        db.session.add(cfg)
    padrao = {'escopo_obra_ativo': True, 'compras_governanca_ativa': True}
    padrao.update(flags)
    for campo, valor in padrao.items():
        setattr(cfg, campo, valor)
    db.session.commit()
    return cfg


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# A1 — o esqueleto: as colunas e os defaults que descrevem o passado
# ---------------------------------------------------------------------------

def test_faixa_de_alcada_nasce_sem_exigir_cotacao_por_dado():
    """`minimo_cotacoes` nasce 0 — a faixa não exige mapa por dado.

    0 é o valor que preserva o comportamento de quem já existia: quem exigia
    mapa exigia por `exige_mapa_concorrencia`, e é o backfill da 297 (não o
    default) que traduz aquele booleano em 2 cotações.
    """
    with app.app_context():
        adm = _admin()
        faixa = _faixa(adm.id)
        db.session.refresh(faixa)
        assert faixa.minimo_cotacoes == 0


def test_faixa_de_alcada_nasce_sem_condicao_ativa():
    """`condicoes_ativas` nasce `''` — nenhuma das quatro vale por padrão.

    Vazio é o comportamento de hoje: faixa que não ativa condição nenhuma
    nunca sobe degrau. Ligar condição é decisão do tenant, uma a uma.
    """
    with app.app_context():
        adm = _admin()
        faixa = _faixa(adm.id)
        db.session.refresh(faixa)
        assert faixa.condicoes_ativas == ''


def test_requisicao_nasce_em_regime_simples():
    """`regime_alcada` nasce `'simples'` — o motor de hoje.

    O regime é carimbado na linha na criação, a partir da flag. Requisição
    que já existia no banco é `'simples'` por definição: ela foi criada num
    mundo em que a alçada só olhava o valor.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        db.session.refresh(req)
        assert req.regime_alcada == 'simples'


def test_requisicao_nasce_sem_emergencia_e_sem_degrau():
    """`emergencial` False, `ratificada_em` None, `degrau_aplicado` `''`.

    As três juntas dizem "esta requisição não invocou rito nenhum e não subiu
    de faixa por motivo nenhum" — que é a verdade sobre todo o histórico.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        db.session.refresh(req)
        assert req.emergencial is False
        assert req.ratificada_em is None
        assert req.degrau_aplicado == ''


def test_tenant_nasce_com_alcadas_avancadas_desligadas_e_janela_de_30_dias():
    """A flag nasce OFF e a janela do fracionamento nasce em 30 dias (D2).

    OFF porque ninguém vira sozinho — a virada é por tenant, e a cadeia de
    cinco elos é conferida pelo script da A2. Os 30 dias são a recomendação
    do spec, e são COLUNA justamente para poder virar 7 por UPDATE.
    """
    with app.app_context():
        adm = _admin()
        cfg = _configuracao(adm.id)
        db.session.refresh(cfg)
        assert cfg.alcadas_avancadas_ativa is False
        assert cfg.janela_fracionamento_dias == 30


# ---------------------------------------------------------------------------
# A2 — a flag e o carimbo do regime
# ---------------------------------------------------------------------------

def test_leitor_da_flag_nasce_desligado_e_segue_o_que_foi_gravado():
    """`alcadas_avancadas_ativa(admin_id)` é o único leitor da flag.

    Tenant sem configuração e tenant com a configuração recém-criada dão o
    mesmo: DESLIGADO. Ninguém vira sozinho.
    """
    from scripts.flag_alcadas_avancadas import (alcadas_avancadas_ativa,
                                                definir_flag)
    with app.app_context():
        adm = _admin()
        assert alcadas_avancadas_ativa(adm.id) is False

        _cfg_tenant(adm.id)
        assert alcadas_avancadas_ativa(adm.id) is False

        definir_flag(adm.id, True)
        assert alcadas_avancadas_ativa(adm.id) is True

        definir_flag(adm.id, False)
        assert alcadas_avancadas_ativa(adm.id) is False


def test_flag_ilegivel_e_tratada_como_desligada():
    """Falha FECHADA para o comportamento ANTIGO: erro devolve False.

    Numa flag que muda quantas aprovações uma compra exige, o modo de falha
    seguro é o que já estava rodando ontem. Mesmo contrato de
    `governanca_ativa` e de `financeiro_dois_fluxos_ativo`.
    """
    from scripts.flag_alcadas_avancadas import alcadas_avancadas_ativa
    with app.app_context():
        assert alcadas_avancadas_ativa(None) is False
        assert alcadas_avancadas_ativa(0) is False
        assert alcadas_avancadas_ativa(-1) is False
        assert alcadas_avancadas_ativa(10 ** 9) is False   # tenant inexistente


def test_ligar_recusa_tenant_sem_governanca_de_compras():
    """Dependência DURA — e a recusa imprime o comando exato que falta.

    Sem `compras_governanca_ativa` não há alçada sobre o que o degrau possa
    agir: a requisição nem passa pelo caminho de aprovação. Ligar alçada
    avançada aí é ligar um motor sem eixo. Quem mexe por SQL direto não tem
    guarda nenhuma — por isso ela mora no script.
    """
    from scripts.flag_alcadas_avancadas import pode_ligar
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, compras_governanca_ativa=False,
                    financeiro_dois_fluxos_ativo=True)

        ok, motivo = pode_ligar(adm.id)
        assert ok is False
        assert 'governan' in motivo.lower(), (
            'o motivo é lido por humano: tem de nomear o que falta')
        assert motivo.rstrip().endswith(
            f'python scripts/flag_compras_governanca.py {adm.id} --ligar'), (
            'a recusa termina no comando exato da flag que falta — quem lê '
            'copia e cola, não deduz')


def test_ligar_avisa_e_nao_recusa_sem_o_financeiro_em_dois_fluxos():
    """Dependência PARCIAL — avisa, não recusa.

    Só a SANÇÃO da emergência depende da Fase 2: sem `situacao_liberacao` a
    conta nasce liberada e a não-ratificação não morde. As outras três regras
    (condições, acumulado e corte de cotações) funcionam sem ela. Recusar
    seria negar três quartos da fase por causa de um quarto.
    """
    from scripts.flag_alcadas_avancadas import pode_ligar
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id, compras_governanca_ativa=True,
                    financeiro_dois_fluxos_ativo=False)

        ok, motivo = pode_ligar(adm.id)
        assert ok is True, 'dois fluxos OFF avisa, nunca recusa'
        assert motivo, 'e o aviso tem de sair escrito, não em silêncio'
        assert 'emerg' in motivo.lower(), (
            'o aviso nomeia o que perde o dente: a sanção da emergência')

        _cfg_tenant(adm.id, financeiro_dois_fluxos_ativo=True)
        ok, motivo = pode_ligar(adm.id)
        assert ok is True
        assert motivo == '', 'com a cadeia inteira ligada não há o que avisar'


def test_definir_flag_cria_a_configuracao_que_nao_existe():
    """Tenant que nunca abriu a tela de configurações não tem a linha, e
    `nome_empresa` é NOT NULL — estourar aqui transformaria o rollout num
    chamado de suporte."""
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        assert ConfiguracaoEmpresa.query.filter_by(
            admin_id=adm.id).first() is None

        definir_flag(adm.id, True)
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=adm.id).first()
        assert cfg is not None and cfg.alcadas_avancadas_ativa is True


def test_regime_alcada_do_tenant_segue_a_flag():
    """O regime que uma requisição nascida AGORA neste tenant carregaria."""
    from services.alcada_compras import regime_alcada_do_tenant
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        _cfg_tenant(adm.id)
        assert regime_alcada_do_tenant(adm.id) == 'simples'

        definir_flag(adm.id, True)
        assert regime_alcada_do_tenant(adm.id) == 'avancado'

        definir_flag(adm.id, False)
        assert regime_alcada_do_tenant(adm.id) == 'simples'


def test_requisicao_criada_com_a_flag_ligada_nasce_avancada():
    """O carimbo, pela ROTA — `requisicao_nova_post` é hoje o único ponto que
    cria `RequisicaoCompra` (📖 compras_views.py, `requisicao_nova_post`).

    Pela rota e não pelo modelo de propósito: o default da coluna já foi
    testado na A1, e o que falta provar é que a rota LÊ a flag.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        aid, oid = adm.id, obra.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'justificativa': 'Cimento para a laje do 3º',
        'item_descricao[]': ['Cimento CP-II'],
        'item_unidade[]': ['sc'],
        'item_quantidade[]': ['10'],
        'item_preco[]': ['42,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        assert req.regime_alcada == 'avancado'


def test_desligar_a_flag_nao_reescreve_requisicao_ja_criada():
    """O regime é carimbado na LINHA — desligar não reescreve o passado.

    Mesma decisão das Fases 1 e 2 (`exige_atesto`, `fluxo_pagamento`).
    Rebaixar a alçada de uma requisição em curso por causa de um toggle é o
    contrário do que a fase faz: quem já foi avisado de que precisa de duas
    aprovações não passa a precisar de uma porque alguém desligou a flag.
    O que volta ao normal é a requisição NOVA.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        aid, oid = adm.id, obra.id

    dados = {
        'obra_id': str(oid),
        'justificativa': 'Areia média',
        'item_descricao[]': ['Areia'],
        'item_unidade[]': ['m3'],
        'item_quantidade[]': ['3'],
        'item_preco[]': ['120,00'],
        'item_almoxarifado_id[]': [''],
    }
    assert _cliente_de(aid).post('/compras/requisicoes/nova', data=dados,
                                 follow_redirects=False).status_code == 302

    with app.app_context():
        antiga = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        antiga_id = antiga.id
        assert antiga.regime_alcada == 'avancado'
        definir_flag(aid, False)

    assert _cliente_de(aid).post('/compras/requisicoes/nova', data=dados,
                                 follow_redirects=False).status_code == 302

    with app.app_context():
        antiga = db.session.get(RequisicaoCompra, antiga_id)
        db.session.refresh(antiga)
        assert antiga.regime_alcada == 'avancado', (
            'desligar a flag não reescreve requisição já criada')
        nova = RequisicaoCompra.query.filter_by(admin_id=aid).filter(
            RequisicaoCompra.id != antiga_id).one()
        assert nova.regime_alcada == 'simples', (
            'a requisição NOVA volta ao regime antigo — é isso que o '
            '--desligar faz, e é só isso')
