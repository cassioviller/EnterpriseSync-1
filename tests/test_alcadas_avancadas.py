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
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, ConfiguracaoEmpresa, EstadoRequisicao, FaixaAlcada,
                    Fornecedor, MapaConcorrenciaV2, MapaCotacao, MapaFornecedor,
                    MapaItemCotacao, Obra, ObraServicoCusto, PapelObra,
                    PedidoCompra, RequisicaoCompra, TipoUsuario, Usuario,
                    UsuarioObra)

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


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'alcp_{suf}', email=f'alcp_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _vincular(usuario, obra, papel):
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id, papel=papel,
                    admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def _mapa(admin_id, obra_id, fornecedores=2, status='concluido', nome=None):
    """Mapa V2 com N fornecedores. N é o que a faixa conta como cotação."""
    m = MapaConcorrenciaV2(obra_id=obra_id, admin_id=admin_id,
                           nome=nome or f'Mapa {uuid.uuid4().hex[:8]}',
                           status=status)
    db.session.add(m)
    db.session.flush()
    for i in range(fornecedores):
        db.session.add(MapaFornecedor(mapa_id=m.id, admin_id=admin_id,
                                      nome=f'Fornecedor {i + 1}', ordem=i))
    db.session.commit()
    return m


def _faixa_topo(admin_id, minimo_cotacoes, valor_ate=None, ordem=9,
                aprovacoes=1, exige_admin=False, exige_mapa=True):
    f = FaixaAlcada(admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
                    aprovacoes_necessarias=aprovacoes,
                    exige_admin=exige_admin,
                    exige_mapa_concorrencia=exige_mapa,
                    minimo_cotacoes=minimo_cotacoes, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


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


# ---------------------------------------------------------------------------
# A3 — o corte de cotações vira dado, e a faixa de topo destrava
#
# Esta seção fecha o 🔴 aberto desde a Fase 3 do núcleo (📖 spec, "O que já
# existe — e o teto em que ela bate", item 3): a faixa de topo exigia
# `requisicao.mapa_v2_id`, a rota lia o campo do form e o gravava, e nenhum
# template tinha o input. Toda requisição acima de R$ 30.000 nascia com uma
# pendência que o usuário não tinha como resolver pela tela.
# ---------------------------------------------------------------------------

def test_minimo_de_cotacoes_da_faixa_diz_quantos_fornecedores_bastam():
    """O corte deixa de ser `len(mapa.fornecedores) >= 2` literal.

    O MESMO mapa, com dois fornecedores, serve numa faixa que pede 2 e não
    serve na que pede 3. Era a única regra de alçada que não era dado — e o
    número que decide passa a vir da linha da tabela, por tenant.
    """
    from services.alcada_compras import _mapa_serve_de_concorrencia
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        mapa = _mapa(adm.id, obra.id, fornecedores=2)
        req = _requisicao(adm.id, obra.id, adm.id)
        req.mapa_v2_id = mapa.id
        db.session.commit()

        exige_dois = _faixa_topo(adm.id, minimo_cotacoes=2, ordem=1)
        exige_tres = _faixa_topo(adm.id, minimo_cotacoes=3, ordem=2)

        assert _mapa_serve_de_concorrencia(req, exige_dois) is True
        assert _mapa_serve_de_concorrencia(req, exige_tres) is False, (
            'o mesmo mapa não pode servir para os dois cortes — quem decide '
            'é a faixa, não o código')


def test_minimo_de_cotacoes_zero_dispensa_o_mapa():
    """`minimo_cotacoes = 0` dispensa — mesmo com `exige_mapa_concorrencia`.

    É este teste que prova que a coluna antiga DEIXOU DE SER LIDA. Ela
    permanece na tabela (há tenant com faixa editada por SQL, e coluna não se
    remove no mesmo release que muda o leitor), mas quem responde a pergunta
    agora é `minimo_cotacoes`.
    """
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        _faixa_topo(adm.id, minimo_cotacoes=0, exige_mapa=True,
                    aprovacoes=0, ordem=1)

        assert not any('mapa' in p.lower() for p in pendencias_de_aprovacao(req))


def test_pendencia_de_mapa_diz_quantas_cotacoes_faltam():
    """A pendência passa a dizer QUANTAS faltam, não só que falta mapa.

    Um aprovador que lê "falta mapa" e anexa um mapa de duas cotações numa
    faixa que pede três volta ao mesmo lugar. O número tem de estar na tela.
    """
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        _faixa_topo(adm.id, minimo_cotacoes=3, aprovacoes=0, ordem=1)

        sem_mapa = ' | '.join(pendencias_de_aprovacao(req))
        assert 'mapa' in sem_mapa.lower() and '3' in sem_mapa

        req.mapa_v2_id = _mapa(adm.id, obra.id, fornecedores=2).id
        db.session.commit()
        curto = ' | '.join(pendencias_de_aprovacao(req))
        assert '2 de 3' in curto, (
            f'a pendência tem de contar o que já existe: {curto!r}')


def test_mapa_de_outra_obra_ou_de_outro_tenant_nunca_serve():
    """Isolamento no SERVIÇO — a rota é a segunda barreira, não a única."""
    from services.alcada_compras import _mapa_serve_de_concorrencia
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        outra_obra = _obra(adm.id)
        outro = _admin()
        obra_do_outro = _obra(outro.id)

        faixa = _faixa_topo(adm.id, minimo_cotacoes=2, ordem=1)
        req = _requisicao(adm.id, obra.id, adm.id)

        req.mapa_v2_id = _mapa(adm.id, outra_obra.id, fornecedores=3).id
        db.session.commit()
        assert _mapa_serve_de_concorrencia(req, faixa) is False

        req.mapa_v2_id = _mapa(outro.id, obra_do_outro.id, fornecedores=3).id
        db.session.commit()
        assert _mapa_serve_de_concorrencia(req, faixa) is False

        req.mapa_v2_id = _mapa(adm.id, obra.id, fornecedores=3,
                               status='aberto').id
        db.session.commit()
        assert _mapa_serve_de_concorrencia(req, faixa) is False, (
            'mapa ainda aberto é cotação em andamento, não concorrência')


def test_form_de_nova_requisicao_oferece_os_mapas_concluidos_da_obra():
    """O campo que nunca existiu. 📖 grep por `mapa_v2_id` em `templates/`
    retornava ZERO — este teste é o que passa a impedir que volte a zero."""
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        concluido = _mapa(adm.id, obra.id, fornecedores=3,
                          nome=f'MapaOK{uuid.uuid4().hex[:8]}')
        aberto = _mapa(adm.id, obra.id, fornecedores=3, status='aberto',
                       nome=f'MapaAberto{uuid.uuid4().hex[:8]}')
        outro = _admin()
        alheio = _mapa(outro.id, _obra(outro.id).id, fornecedores=3,
                       nome=f'MapaAlheio{uuid.uuid4().hex[:8]}')
        aid = adm.id
        nome_ok, nome_aberto, nome_alheio = (concluido.nome, aberto.nome,
                                             alheio.nome)

    html = _cliente_de(aid).get('/compras/requisicoes/nova').get_data(as_text=True)
    assert 'mapa_v2_id' in html, 'o input do mapa tem de existir na tela'
    assert nome_ok in html
    assert nome_aberto not in html, 'mapa aberto não é concorrência fechada'
    assert nome_alheio not in html, 'mapa de outra empresa nunca aparece'


def test_post_com_mapa_vindo_do_form_grava_o_vinculo():
    """O ciclo real: o id sai do SELECT RENDERIZADO e volta no POST.

    Ler o valor do HTML em vez de montá-lo no teste é o ponto: prova que a
    tela oferece exatamente o que a rota aceita.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        mapa = _mapa(adm.id, obra.id, fornecedores=3)
        aid, oid, mid = adm.id, obra.id, mapa.id

    cliente = _cliente_de(aid)
    html = cliente.get('/compras/requisicoes/nova').get_data(as_text=True)
    ofertados = re.findall(
        r'<option[^>]*value="(\d+)"[^>]*data-obra="%d"' % oid, html)
    assert str(mid) in ofertados, (
        f'o mapa {mid} tinha de estar no select da obra {oid}: {ofertados}')

    r = cliente.post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'mapa_v2_id': ofertados[ofertados.index(str(mid))],
        'justificativa': 'Esquadrias do bloco B',
        'item_descricao[]': ['Esquadria de alumínio'],
        'item_unidade[]': ['un'],
        'item_quantidade[]': ['4'],
        'item_preco[]': ['1.500,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        assert req.mapa_v2_id == mid


def test_rota_recusa_mapa_de_outra_empresa_e_de_outra_obra():
    """Isolamento entre empresas NA ROTA — o defeito mais caro deste
    repositório. O serviço já barra; a rota barra antes de gravar, para que o
    vínculo indevido nunca chegue a existir na linha."""
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        outra_obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        outro = _admin()
        alheio = _mapa(outro.id, _obra(outro.id).id, fornecedores=3)
        da_outra_obra = _mapa(adm.id, outra_obra.id, fornecedores=3)
        aid, oid = adm.id, obra.id
        ids = {'alheio': alheio.id, 'outra_obra': da_outra_obra.id}

    base = {
        'obra_id': str(oid),
        'justificativa': 'Tentativa',
        'item_descricao[]': ['Item'],
        'item_unidade[]': ['un'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['10,00'],
        'item_almoxarifado_id[]': [''],
    }
    for rotulo, mid in ids.items():
        dados = dict(base, mapa_v2_id=str(mid))
        assert _cliente_de(aid).post('/compras/requisicoes/nova', data=dados,
                                     follow_redirects=False).status_code == 302

    with app.app_context():
        for req in RequisicaoCompra.query.filter_by(admin_id=aid).all():
            assert req.mapa_v2_id is None, (
                'mapa de outro tenant ou de outra obra não pode ser gravado')


def test_detalhe_da_pendencia_de_mapa_tem_saida_na_propria_tela():
    """Pendência sem saída é pendência que vira ligação para o suporte.

    A tela de detalhe passa a oferecer as duas saídas: vincular um mapa
    concluído que já existe, ou ir criar um na obra.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _faixa_topo(adm.id, minimo_cotacoes=2, aprovacoes=0, ordem=1)
        mapa = _mapa(adm.id, obra.id, fornecedores=2,
                     nome=f'MapaSaida{uuid.uuid4().hex[:8]}')
        req = _requisicao(adm.id, obra.id, adm.id)
        req.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()
        aid, oid, rid, nome = adm.id, obra.id, req.id, mapa.nome

    html = _cliente_de(aid).get(
        f'/compras/requisicoes/{rid}').get_data(as_text=True)
    assert 'mapa' in html.lower()
    assert nome in html, 'o mapa concluído da obra tem de estar oferecido'
    assert f'/obras/detalhes/{oid}#tab-mapa' in html, (
        'e tem de haver caminho para criar um mapa novo na obra')


def test_vincular_mapa_pela_tela_de_detalhe_resolve_a_pendencia():
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _faixa_topo(adm.id, minimo_cotacoes=2, aprovacoes=0, ordem=1)
        mapa = _mapa(adm.id, obra.id, fornecedores=2)
        outro = _admin()
        alheio = _mapa(outro.id, _obra(outro.id).id, fornecedores=3)
        req = _requisicao(adm.id, obra.id, adm.id)
        req.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()
        aid, rid, mid, alheio_id = adm.id, req.id, mapa.id, alheio.id

    cliente = _cliente_de(aid)
    cliente.post(f'/compras/requisicoes/{rid}/vincular-mapa',
                 data={'mapa_v2_id': str(alheio_id)}, follow_redirects=False)
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).mapa_v2_id is None, (
            'a rota confere admin_id e obra_id ANTES de gravar')

    cliente.post(f'/compras/requisicoes/{rid}/vincular-mapa',
                 data={'mapa_v2_id': str(mid)}, follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, rid)
        assert req.mapa_v2_id == mid
        assert not any('mapa' in p.lower() for p in pendencias_de_aprovacao(req))


def test_requisicao_acima_de_30k_com_mapa_de_tres_chega_a_aprovada():
    """🔴 O teste que prova que o bloqueio permanente morreu.

    Ciclo inteiro PELA TELA, sem tocar no banco no meio: criar com o mapa
    escolhido no select, enviar, e as duas aprovações da faixa de topo. Antes
    da A3 este caminho não existia — a requisição parava numa pendência que
    nenhum template sabia resolver.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        # As três faixas recomendadas, com a de topo já na decisão D6 (3
        # cotações acima de 30k) — que é UPDATE de tenant, não migration.
        _faixa_topo(adm.id, 0, valor_ate=Decimal('5000.00'), ordem=1,
                    aprovacoes=1, exige_admin=False, exige_mapa=False)
        _faixa_topo(adm.id, 0, valor_ate=Decimal('30000.00'), ordem=2,
                    aprovacoes=2, exige_admin=True, exige_mapa=False)
        _faixa_topo(adm.id, 3, valor_ate=None, ordem=3,
                    aprovacoes=2, exige_admin=True, exige_mapa=True)
        solicitante = _operador(adm.id, 'Solicitante')
        gestor = _operador(adm.id, 'Gestor')
        _vincular(solicitante, obra, PapelObra.COMPRADOR)
        _vincular(gestor, obra, PapelObra.GESTOR)
        _mapa(adm.id, obra.id, fornecedores=3)
        aid, oid = adm.id, obra.id
        sid, gid = solicitante.id, gestor.id

    cliente = _cliente_de(sid)
    html = cliente.get('/compras/requisicoes/nova').get_data(as_text=True)
    ofertados = re.findall(
        r'<option[^>]*value="(\d+)"[^>]*data-obra="%d"' % oid, html)
    assert ofertados, 'sem mapa no select não há como destravar a faixa de topo'

    assert cliente.post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'mapa_v2_id': ofertados[0],
        'justificativa': 'Estrutura metálica — 3 cotações no mapa',
        'item_descricao[]': ['Estrutura metálica'],
        'item_unidade[]': ['un'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['40.000,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False).status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        rid = req.id
        assert req.valor_estimado == Decimal('40000.00')
        assert req.mapa_v2_id is not None

    cliente.post(f'/compras/requisicoes/{rid}/enviar', follow_redirects=False)
    _cliente_de(gid).post(f'/compras/requisicoes/{rid}/aprovar',
                          follow_redirects=False)
    _cliente_de(aid).post(f'/compras/requisicoes/{rid}/aprovar',
                          follow_redirects=False)

    with app.app_context():
        req = db.session.get(RequisicaoCompra, rid)
        assert req.estado == EstadoRequisicao.APROVADA, (
            'acima de 30k com mapa de 3 cotações a requisição TEM de chegar '
            'a APROVADA pela tela — é o 🔴 que a A3 fecha')


# ---------------------------------------------------------------------------
# A4 — `faixa_efetiva` e as quatro condições  ← gate de merge
#
# A ordem desta seção não é decorativa. A PARIDADE vem primeiro porque é ela
# que autoriza todo o resto: enquanto não estiver provado que, com a flag
# desligada, a regra nova devolve exatamente a faixa de sempre, nenhum degrau
# pode ser ligado em lugar nenhum. `faixa_para_valor` fica INTOCADA — a regra
# nova mora numa função ACIMA dela, e é isso que protege os 100+ testes de
# alçada que já existiam (📖 spec, "O motor ganha uma pergunta, não um
# segundo motor").
# ---------------------------------------------------------------------------

# A grade cruza os TRÊS tetos das faixas recomendadas, e cruza cada um por
# baixo, em cima e por fora: 5000 e 30000 estão lá porque a comparação é
# inclusiva (`valor <= valor_ate`) e um `<` no lugar do `<=` só apareceria
# num desses dois pontos.
GRADE_DE_PARIDADE = [0, 4999, 5000, 5001, 29999, 30000, 30001, 1000000]

TODAS_AS_CONDICOES = ('fornecedor_novo,sem_cotacao,nao_menor_preco,'
                      'fora_do_orcamento')


def _escada(admin_id, condicoes='', minimo_topo=0):
    """As três faixas recomendadas do tenant, na ordem: 5k → 30k → aberta.

    Os números são os de `FAIXAS_RECOMENDADAS`: 5k pede 1 aprovação; 30k pede
    2 e uma de admin; a aberta pede 2 + admin. `condicoes` é o texto de
    `condicoes_ativas` aplicado a TODAS as faixas — quem decide se a condição
    roda é a faixa BASE, e ter a mesma lista nas três é o caso realista.
    """
    faixas = []
    for ordem, teto, aprov, adm in ((1, Decimal('5000.00'), 1, False),
                                    (2, Decimal('30000.00'), 2, True),
                                    (3, None, 2, True)):
        f = FaixaAlcada(admin_id=admin_id, ordem=ordem, valor_ate=teto,
                        aprovacoes_necessarias=aprov, exige_admin=adm,
                        exige_mapa_concorrencia=(ordem == 3),
                        minimo_cotacoes=(minimo_topo if ordem == 3 else 0),
                        condicoes_ativas=condicoes, ativo=True)
        db.session.add(f)
        faixas.append(f)
    db.session.commit()
    return faixas


def _etapa(obra, orcado='10000.00'):
    """Etapa (centro de custo) da obra, com o orçado no campo agregado.

    Sem `ObraServicoCustoItem`, de propósito: é o fluxo manual/legado, em que
    `custo_orcado_por_servico` cai para `valor_orcado` (📖
    services/custo_orcado.py). É o caminho que o teste quer exercitar porque é
    o que a maioria dos tenants tem.
    """
    e = ObraServicoCusto(admin_id=obra.admin_id, obra_id=obra.id,
                         nome=f'Etapa {uuid.uuid4().hex[:6]}',
                         valor_orcado=Decimal(orcado))
    db.session.add(e)
    db.session.commit()
    return e


def _fornecedor(admin_id):
    suf = uuid.uuid4().hex[:8]
    f = Fornecedor(nome=f'Fornecedor {suf}', cnpj=f'{suf}0001-99',
                   admin_id=admin_id, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _pedido(admin_id, fornecedor_id, obra_id=None, valor='100.00'):
    p = PedidoCompra(fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1),
                     obra_id=obra_id, valor_total=Decimal(valor),
                     admin_id=admin_id, tipo_compra='normal')
    db.session.add(p)
    db.session.commit()
    return p


def _mapa_com_precos(admin_id, obra_id, precos, escolhido=0):
    """Mapa concluído com UM item, N fornecedores e um preço para cada.

    `escolhido` é o índice do fornecedor marcado em
    `MapaItemCotacao.fornecedor_escolhido_id` — a fonte canônica da escolha
    desde a Task #21 (a migration 142 fez o backfill a partir de
    `MapaCotacao.selecionado`, que o spec ainda nomeia).
    """
    m = MapaConcorrenciaV2(obra_id=obra_id, admin_id=admin_id,
                           nome=f'Mapa {uuid.uuid4().hex[:8]}',
                           status='concluido')
    db.session.add(m)
    db.session.flush()
    forns = []
    for i, _ in enumerate(precos):
        f = MapaFornecedor(mapa_id=m.id, admin_id=admin_id,
                           nome=f'Fornecedor {i + 1}', ordem=i)
        db.session.add(f)
        forns.append(f)
    item = MapaItemCotacao(mapa_id=m.id, admin_id=admin_id, descricao='Item',
                           unidade='un', quantidade=1, ordem=0)
    db.session.add(item)
    db.session.flush()
    for f, preco in zip(forns, precos):
        db.session.add(MapaCotacao(mapa_id=m.id, item_id=item.id,
                                   fornecedor_id=f.id, admin_id=admin_id,
                                   valor_unitario=Decimal(str(preco))))
    item.fornecedor_escolhido_id = forns[escolhido].id
    db.session.commit()
    return m


def test_faixa_efetiva_com_a_flag_desligada_e_a_faixa_de_sempre():
    """PARIDADE — o teste que autoriza todos os outros.

    Com a flag desligada, `faixa_efetiva` devolve **o mesmo objeto** que
    `faixa_para_valor` em toda a grade, e as quatro condições estão ATIVAS nas
    três faixas: é justamente o cenário em que um degrau vazado apareceria. O
    que segura o degrau é o `regime_alcada` carimbado na linha, e nada mais.
    """
    from scripts.flag_alcadas_avancadas import alcadas_avancadas_ativa
    from services.alcada_compras import faixa_efetiva, faixa_para_valor
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _escada(adm.id, condicoes=TODAS_AS_CONDICOES, minimo_topo=3)
        assert alcadas_avancadas_ativa(adm.id) is False

        req = _requisicao(adm.id, obra.id, adm.id)
        assert req.regime_alcada == 'simples'

        for valor in GRADE_DE_PARIDADE:
            req.valor_estimado = Decimal(str(valor))
            db.session.flush()
            esperada = faixa_para_valor(adm.id, req.valor_estimado)
            assert faixa_efetiva(req) is esperada, (
                f'com a flag OFF o valor {valor} tem de cair exatamente na '
                f'faixa de sempre (ordem {esperada.ordem})')

        assert req.degrau_aplicado == '', (
            'flag desligada não escreve trilha de degrau nenhuma')


def test_regime_simples_ignora_as_condicoes_ainda_que_a_flag_esteja_ligada():
    """Quem decide é o CARIMBO da linha, não a flag do tenant.

    Requisição nascida antes da virada continua no motor de hoje mesmo com a
    flag ligada — é a outra metade de "desligar não reescreve o passado":
    ligar também não reescreve.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    from services.alcada_compras import faixa_efetiva, faixa_para_valor
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        _escada(adm.id, condicoes=TODAS_AS_CONDICOES)

        req = _requisicao(adm.id, obra.id, adm.id)   # nasce 'simples'
        assert faixa_efetiva(req) is faixa_para_valor(adm.id,
                                                      req.valor_estimado)
        assert req.degrau_aplicado == ''


def test_uma_condicao_ativa_sobe_uma_faixa_e_grava_o_motivo():
    """R$ 4.900 é faixa 1; sem etapa apontada, `fora_do_orcamento` dispara e a
    exigência passa a ser a da faixa 2 — 2 aprovações, uma de admin."""
    from services.alcada_compras import faixa_efetiva, faixa_para_valor
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, f2, _f3 = _escada(adm.id, condicoes='fora_do_orcamento')

        req = _requisicao(adm.id, obra.id, adm.id)
        req.regime_alcada = 'avancado'
        db.session.commit()

        assert faixa_para_valor(adm.id, req.valor_estimado) is f1
        assert faixa_efetiva(req) is f2, 'uma condição sobe UMA faixa'
        assert req.degrau_aplicado == 'fora_do_orcamento', (
            'a trilha diz POR QUE subiu — sem ela o aprovador liga para o '
            'suporte')


def test_duas_condicoes_sobem_duas_faixas():
    """Degrau é contagem, não booleano: duas condições sobem dois degraus."""
    from services.alcada_compras import faixa_efetiva
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, _f2, f3 = _escada(adm.id,
                              condicoes='sem_cotacao,fora_do_orcamento')
        # A faixa BASE passa a exigir mapa: é ela quem diz se `sem_cotacao`
        # dispara, e a requisição não tem mapa nenhum.
        f1.minimo_cotacoes = 2
        db.session.commit()

        req = _requisicao(adm.id, obra.id, adm.id)
        req.regime_alcada = 'avancado'
        db.session.commit()

        assert faixa_efetiva(req) is f3
        assert req.degrau_aplicado == 'sem_cotacao,fora_do_orcamento'


def test_na_faixa_de_topo_o_degrau_satura_e_mesmo_assim_grava():
    """Teto é teto — e a trilha registra que disparou ainda que a exigência
    não tenha mudado. Sem isso, a requisição de topo seria a única em que
    ninguém saberia que uma condição pegou (📖 spec, "Casos de borda")."""
    from services.alcada_compras import faixa_efetiva
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _f1, _f2, f3 = _escada(adm.id, condicoes='fora_do_orcamento')

        req = _requisicao(adm.id, obra.id, adm.id)
        req.regime_alcada = 'avancado'
        req.valor_estimado = Decimal('40000.00')
        db.session.commit()

        assert faixa_efetiva(req) is f3, 'não há para onde subir'
        assert req.degrau_aplicado == 'fora_do_orcamento', (
            'saturado NÃO é motivo para não registrar')


def test_condicao_que_o_tenant_nao_ativou_nao_e_nem_avaliada(monkeypatch):
    """Custo de query também é comportamento.

    A condição que não está em `condicoes_ativas` não roda — não é avaliada e
    descartada, é *não avaliada*. O avaliador trocado por uma bomba prova a
    diferença: se ele for chamado, o teste estoura.
    """
    from services import alcada_compras
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, _f2, _f3 = _escada(adm.id, condicoes='sem_cotacao')
        f1.minimo_cotacoes = 2
        db.session.commit()

        req = _requisicao(adm.id, obra.id, adm.id)
        req.regime_alcada = 'avancado'
        db.session.commit()

        def _bomba(*args, **kwargs):
            raise AssertionError('condição não ativada não pode nem ser '
                                 'consultada')

        monkeypatch.setattr(alcada_compras, '_cond_fora_do_orcamento', _bomba)
        assert alcada_compras.condicoes_disparadas(req, f1) == ['sem_cotacao']


def test_codigo_desconhecido_em_condicoes_ativas_e_ignorado():
    """`condicoes_ativas` é texto, e texto editado por SQL erra.

    Um código que o código não conhece não pode virar degrau silencioso nem
    exceção no meio de uma aprovação: é ignorado, e a lista das quatro
    conhecidas continua valendo.
    """
    from services.alcada_compras import condicoes_disparadas
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, _f2, _f3 = _escada(adm.id,
                               condicoes='frete_alto, fora_do_orcamento ,')

        req = _requisicao(adm.id, obra.id, adm.id)
        req.regime_alcada = 'avancado'
        db.session.commit()

        assert condicoes_disparadas(req, f1) == ['fora_do_orcamento']


# ── Os quatro avaliadores, um a um ─────────────────────────────────────────

def test_cond_fornecedor_novo_nao_e_avaliavel_sem_fornecedor():
    """A requisição NÃO TEM fornecedor — ele só é escolhido na emissão
    (📖 `PedidoCompra.fornecedor_id` é NOT NULL; a requisição não tem a
    coluna). Ausência de fornecedor é condição NÃO AVALIADA (None), e não
    "não disparou" (False): a diferença é o que impede o dia em que alguém
    concluir que todo fornecedor da tela de requisição é conhecido."""
    from services.alcada_compras import _cond_fornecedor_novo
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)

        assert _cond_fornecedor_novo(req, None) is None
        assert _cond_fornecedor_novo(req) is None


def test_cond_fornecedor_novo_olha_pedido_anterior_do_tenant():
    """Novo = sem pedido emitido NESTE tenant. E a segunda compra do mesmo
    fornecedor no mesmo dia já não é nova — é intencional (📖 spec, "Casos de
    borda")."""
    from services.alcada_compras import _cond_fornecedor_novo
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        forn = _fornecedor(adm.id)

        assert _cond_fornecedor_novo(req, forn) is True

        # Pedido do MESMO fornecedor, mas de outro tenant: não conta.
        outro = _admin()
        _pedido(outro.id, forn.id)
        assert _cond_fornecedor_novo(req, forn) is True, (
            'histórico de outra empresa não torna o fornecedor conhecido aqui')

        _pedido(adm.id, forn.id, obra_id=obra.id)
        assert _cond_fornecedor_novo(req, forn) is False


def test_cond_sem_cotacao_segue_o_minimo_da_faixa():
    """Dispara quando a faixa exige mapa e a requisição não tem um que sirva.

    Não substitui a pendência de mapa — ela continua. A condição existe para
    a DISPENSA (fornecedor único, item sem concorrente), que hoje não tem
    caminho nenhum e por isso vira requisição travada.
    """
    from services.alcada_compras import _cond_sem_cotacao
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        dispensa = _faixa_topo(adm.id, minimo_cotacoes=0, ordem=1)
        exige_tres = _faixa_topo(adm.id, minimo_cotacoes=3, ordem=2)

        assert _cond_sem_cotacao(req, dispensa) is False
        assert _cond_sem_cotacao(req, exige_tres) is True

        req.mapa_v2_id = _mapa(adm.id, obra.id, fornecedores=3).id
        db.session.commit()
        assert _cond_sem_cotacao(req, exige_tres) is False


def test_cond_nao_menor_preco_compara_o_escolhido_com_o_menor_do_item():
    """O mapa existe, tem escolha, e a escolha não é a mais barata.

    É o caso que o mapa de concorrência sozinho nunca barrou: escolher o
    fornecedor mais caro é legítimo (prazo, qualidade) — e por isso custa uma
    aprovação a mais, registrada, em vez de um bloqueio.
    """
    from services.alcada_compras import _cond_nao_menor_preco
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)

        assert _cond_nao_menor_preco(req) is False, (
            'sem mapa vinculado quem cobre é sem_cotacao, não esta')

        barato = _mapa_com_precos(adm.id, obra.id, [10, 20, 30], escolhido=0)
        req.mapa_v2_id = barato.id
        db.session.commit()
        assert _cond_nao_menor_preco(req) is False

        caro = _mapa_com_precos(adm.id, obra.id, [10, 20, 30], escolhido=2)
        req.mapa_v2_id = caro.id
        db.session.commit()
        assert _cond_nao_menor_preco(req) is True


def test_cond_fora_do_orcamento_dispara_sem_etapa_apontada():
    """A mais RUIDOSA das quatro, e de propósito (⚠️ D1 do spec).

    `obra_servico_custo_id` é nullable: requisição que simplesmente não aponta
    etapa dispara. É comportamento correto — compra sem centro de custo é o
    que a Fase 4 do núcleo passou a barrar — e é por isso que a condição é
    ligável uma a uma, por tenant.
    """
    from services.alcada_compras import _cond_fora_do_orcamento
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)   # sem etapa
        assert req.obra_servico_custo_id is None
        assert _cond_fora_do_orcamento(req) is True


def test_cond_fora_do_orcamento_soma_as_requisicoes_da_etapa():
    """Com etapa apontada, dispara quando a SOMA da etapa passa o previsto.

    A soma inclui as irmãs da mesma etapa; REJEITADA e CANCELADA ficam de
    fora, pelo mesmo critério do acumulado (📖 spec, "Casos de borda").
    """
    from services.alcada_compras import _cond_fora_do_orcamento
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        etapa = _etapa(obra, orcado='10000.00')

        req = _requisicao(adm.id, obra.id, adm.id)   # R$ 4.900
        req.obra_servico_custo_id = etapa.id
        db.session.commit()
        assert _cond_fora_do_orcamento(req) is False

        irma = _requisicao(adm.id, obra.id, adm.id)  # + R$ 4.900 = 9.800
        irma.obra_servico_custo_id = etapa.id
        db.session.commit()
        assert _cond_fora_do_orcamento(req) is False

        cancelada = _requisicao(adm.id, obra.id, adm.id)
        cancelada.obra_servico_custo_id = etapa.id
        cancelada.estado = EstadoRequisicao.CANCELADA
        db.session.commit()
        assert _cond_fora_do_orcamento(req) is False, (
            'requisição cancelada não consome orçamento de etapa nenhuma')

        terceira = _requisicao(adm.id, obra.id, adm.id)  # + 4.900 = 14.700
        terceira.obra_servico_custo_id = etapa.id
        db.session.commit()
        assert _cond_fora_do_orcamento(req) is True


# ── Os pontos que DECIDEM e o ponto que EXIBE ──────────────────────────────

def test_pendencias_cobram_a_faixa_efetiva_e_nao_a_faixa_do_valor():
    """O primeiro dos quatro pontos de decisão.

    Sem isto o degrau seria decoração: a faixa subiria e a requisição fecharia
    a alçada com o número de aprovações da faixa de baixo.
    """
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _escada(adm.id, condicoes='fora_do_orcamento')

        req = _requisicao(adm.id, obra.id, adm.id)
        req.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        req.regime_alcada = 'avancado'
        db.session.commit()

        texto = ' | '.join(pendencias_de_aprovacao(req))
        assert 'de 2' in texto, (
            f'a faixa efetiva pede 2 aprovações, não 1: {texto!r}')
        assert 'administrador' in texto, (
            'e a faixa efetiva também é quem diz que uma tem de ser de admin')


def test_flash_da_criacao_anuncia_a_mesma_faixa_que_a_pendencia_cobra():
    """A tela não pode prometer uma faixa e o envio cobrar outra.

    O flash da criação e as pendências saem do MESMO cálculo. Foi o risco
    nomeado no Step 5 do plano: ponto de exibição e ponto de decisão em
    desacordo fariam a fase nascer mentindo.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        _escada(adm.id, condicoes='fora_do_orcamento')
        aid, oid = adm.id, obra.id

    html = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'justificativa': 'Cimento — sem etapa apontada de propósito',
        'item_descricao[]': ['Cimento CP-II'],
        'item_unidade[]': ['sc'],
        'item_quantidade[]': ['10'],
        'item_preco[]': ['100,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=True).get_data(as_text=True)

    assert 'precisar de 2 aprovação(ões)' in html, (
        'o flash da criação tem de anunciar a faixa EFETIVA')

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        assert req.regime_alcada == 'avancado'
        assert req.degrau_aplicado == 'fora_do_orcamento', (
            'a rota é quem persiste o carimbo — `faixa_efetiva` não commita')
        assert 'de 2' in ' | '.join(pendencias_de_aprovacao(req)), (
            'e o que o envio cobra é exatamente o que a tela prometeu')


def test_detalhe_mostra_a_faixa_base_a_efetiva_e_o_motivo_em_portugues():
    """Pendência sem motivo visível é pendência que vira ligação para o
    suporte. A tela mostra as duas faixas e o código traduzido."""
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _escada(adm.id, condicoes='fora_do_orcamento')

        req = _requisicao(adm.id, obra.id, adm.id)
        req.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        req.regime_alcada = 'avancado'
        db.session.commit()
        aid, rid = adm.id, req.id

    html = _cliente_de(aid).get(
        f'/compras/requisicoes/{rid}').get_data(as_text=True)
    assert 'subiu de faixa' in html.lower()
    assert 'R$ 5000.00' in html, 'a faixa BASE (pelo valor) tem de aparecer'
    assert 'R$ 30000.00' in html, 'e a EFETIVA, que é a que vai ser cobrada'
    assert 'etapa' in html.lower(), (
        'o motivo em português, não o código: quem lê a tela não lê o spec')


def test_emissao_usa_a_faixa_efetiva_e_e_onde_o_fornecedor_novo_pesa():
    """O quarto ponto de decisão — a guarda 2 de `requisicao_emitir_pedido`.

    `fornecedor_novo` só existe aqui: a requisição não tem fornecedor, e por
    isso a aprovação passou pela faixa de baixo. Na emissão o fornecedor
    aparece, a faixa efetiva sobe para 2 aprovações e a separação de funções
    passa a valer — quem aprovou não emite.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        _escada(adm.id, condicoes='fornecedor_novo')
        solicitante = _operador(adm.id, 'Comprador')
        _vincular(solicitante, obra, PapelObra.COMPRADOR)
        forn = _fornecedor(adm.id)
        aid, oid, sid, fid = adm.id, obra.id, solicitante.id, forn.id

    cliente = _cliente_de(sid)
    assert cliente.post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'justificativa': 'Andaime',
        'item_descricao[]': ['Andaime'],
        'item_unidade[]': ['un'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['1.000,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False).status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        rid = req.id
        # Sem fornecedor a condição não é avaliada: a faixa base vale, e uma
        # aprovação fecha a alçada.
        assert req.degrau_aplicado == ''

    cliente.post(f'/compras/requisicoes/{rid}/enviar', follow_redirects=False)
    # O ADMIN aprova (o solicitante nunca aprova a própria requisição).
    _cliente_de(aid).post(f'/compras/requisicoes/{rid}/aprovar',
                          follow_redirects=False)
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).estado == \
            EstadoRequisicao.APROVADA

    # ADMIN aprovou e agora tenta emitir: com o fornecedor novo a faixa
    # efetiva pede 2 aprovações, e a guarda 2 passa a morder.
    html = _cliente_de(aid).post(
        f'/compras/requisicoes/{rid}/emitir-pedido',
        data={'fornecedor_id': str(fid), 'data_compra': '2026-08-15'},
        follow_redirects=True).get_data(as_text=True)

    assert 'não pode emitir o pedido' in html, (
        'a guarda 2 tem de ler a faixa EFETIVA, e ela conhece o fornecedor')
    with app.app_context():
        req = db.session.get(RequisicaoCompra, rid)
        assert PedidoCompra.query.filter_by(requisicao_id=rid).count() == 0
        assert req.degrau_aplicado == '', (
            'a guarda recusou e a rota NÃO commitou — `faixa_efetiva` carimba '
            'na sessão, e quem persiste é sempre a rota')


# ---------------------------------------------------------------------------
# A5 — anti-fracionamento: o acumulado da janela passa a definir a faixa
#
# Dois acumulados, e eles NÃO são o mesmo com filtro diferente. O critério de
# qual vale é DE ONDE VEIO A CHAMADA, não um parâmetro solto:
#   * no envio da requisição, `(obra, etapa)` — porque a requisição não tem
#     fornecedor (📖 `PedidoCompra.fornecedor_id` é NOT NULL; a requisição não
#     tem a coluna);
#   * na emissão do pedido, `(admin, obra, fornecedor)` — o único momento em
#     que o fornecedor existe.
# O efeito é DEGRAU, não bloqueio (D3): bloquear compra legítima de obra grande
# empurra a compra para fora do sistema, e o sistema deixa de saber o que a
# obra gastou.
# ---------------------------------------------------------------------------

def _req_na_etapa(admin_id, obra_id, solicitante_id, etapa_id=None,
                  valor='4900.00', estado=EstadoRequisicao.RASCUNHO,
                  dias_atras=0, regime='avancado'):
    """Requisição com etapa, valor, estado e IDADE escolhidos.

    `dias_atras` escreve `created_at` na criação — a janela é por data e a
    borda dela só se exercita com a data na mão. O default da coluna continua
    valendo para quem não passa nada (é o caminho da rota).
    """
    r = RequisicaoCompra(
        numero=f'RC-{uuid.uuid4().hex[:8].upper()}', admin_id=admin_id,
        obra_id=obra_id, solicitante_id=solicitante_id,
        obra_servico_custo_id=etapa_id, estado=estado,
        regime_alcada=regime, valor_estimado=Decimal(valor),
        created_at=datetime.utcnow() - timedelta(days=dias_atras))
    db.session.add(r)
    db.session.commit()
    return r


def test_acumulado_da_etapa_soma_a_janela_e_deixa_de_fora_o_que_morreu():
    """O acumulado é a soma da `(obra, etapa)` na janela, a própria inclusa.

    REJEITADA e CANCELADA ficam de fora (📖 spec, "Casos de borda"): a
    requisição rejeitada e reenviada conta a rodada nova, não as duas, e uma
    requisição morta não pode segurar faixa nenhuma. CONVERTIDA conta — ela
    virou compra de verdade, que é justamente o que o fracionamento divide.
    """
    from services.alcada_compras import acumulado_da_etapa
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        etapa = _etapa(obra)

        alvo = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        assert acumulado_da_etapa(alvo, 30) == Decimal('4900.00'), (
            'sozinha, a requisição acumula o próprio valor')

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id,
                      estado=EstadoRequisicao.CONVERTIDA)
        assert acumulado_da_etapa(alvo, 30) == Decimal('14700.00')

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id,
                      estado=EstadoRequisicao.REJEITADA)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id,
                      estado=EstadoRequisicao.CANCELADA)
        assert acumulado_da_etapa(alvo, 30) == Decimal('14700.00'), (
            'rejeitada e cancelada não entram no acumulado')

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, dias_atras=45)
        assert acumulado_da_etapa(alvo, 30) == Decimal('14700.00'), (
            'fora da janela não entra')

        outra_etapa = _etapa(obra)
        _req_na_etapa(adm.id, obra.id, adm.id, outra_etapa.id)
        assert acumulado_da_etapa(alvo, 30) == Decimal('14700.00'), (
            'o agrupamento é por (obra, etapa) — outra etapa é outra conta')


def test_tres_requisicoes_de_4900_na_mesma_etapa_levam_a_terceira_a_30k():
    """O caso do spec, inteiro: 3 × R$ 4.900 na mesma `(obra, etapa)`.

    Cada uma sozinha é faixa de 5k, uma aprovação. Somadas na janela dão
    R$ 14.700, que é faixa de 30k — 2 aprovações e uma de admin. A terceira
    sobe, e a trilha diz por quê.
    """
    from services.alcada_compras import faixa_efetiva, faixa_para_valor
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _f1, f2, _f3 = _escada(adm.id)      # sem condição nenhuma ativa
        etapa = _etapa(obra)

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        terceira = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)

        assert faixa_para_valor(adm.id, terceira.valor_estimado).ordem == 1
        assert faixa_efetiva(terceira) is f2, (
            'o acumulado da janela cruza o teto que a linha sozinha não cruza')
        assert terceira.degrau_aplicado == 'fracionamento', (
            'a trilha registra que quem subiu a faixa foi o acumulado, e não '
            'uma das quatro condições')


def test_a_mesma_terceira_fora_da_janela_fica_na_faixa_do_proprio_valor():
    """A outra metade do teste anterior — e é ela que prova que existe janela.

    As duas irmãs de 45 dias atrás não somam com a de hoje: compra que se
    repete todo mês não é compra dividida.
    """
    from services.alcada_compras import faixa_efetiva
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, _f2, _f3 = _escada(adm.id)
        etapa = _etapa(obra)

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, dias_atras=45)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, dias_atras=45)
        terceira = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)

        assert faixa_efetiva(terceira) is f1
        assert terceira.degrau_aplicado == ''


def test_a_janela_vem_da_configuracao_do_tenant_e_nao_do_codigo():
    """Configurar 7 dias muda o resultado SEM tocar em código (D2).

    As irmãs são de 10 dias atrás: dentro dos 30 do default, fora dos 7 que o
    tenant configurou. É por isso que a janela é coluna e não constante.
    """
    from services.alcada_compras import faixa_efetiva
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, f2, _f3 = _escada(adm.id)
        etapa = _etapa(obra)

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, dias_atras=10)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, dias_atras=10)
        alvo = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)

        assert faixa_efetiva(alvo) is f2, 'com os 30 dias do default, soma'

        _cfg_tenant(adm.id, janela_fracionamento_dias=7)
        alvo.degrau_aplicado = ''      # a trilha só cresce; aqui o teste zera
        db.session.commit()
        assert faixa_efetiva(alvo) is f1, (
            'com a janela em 7 dias as irmãs de 10 dias atrás saem da conta — '
            'e ninguém tocou em código para isso')
        assert alvo.degrau_aplicado == ''


def test_o_acumulado_por_fornecedor_aparece_so_na_emissao():
    """Os dois acumulados são coisas diferentes, e o critério é a chamada.

    O mesmo fornecedor já levou R$ 40.000 desta obra na janela. No ENVIO isso
    é invisível — a requisição não tem fornecedor. Na EMISSÃO, que é onde ele
    é escolhido, o acumulado passa a valer e a faixa sobe.
    """
    from services.alcada_compras import (acumulado_do_fornecedor,
                                         faixa_efetiva)
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, _f2, f3 = _escada(adm.id)
        forn = _fornecedor(adm.id)

        _pedido(adm.id, forn.id, obra_id=obra.id, valor='20000.00')
        _pedido(adm.id, forn.id, obra_id=obra.id, valor='20000.00')
        assert acumulado_do_fornecedor(adm.id, obra.id, forn.id,
                                       3650) == Decimal('40000.00')

        req = _req_na_etapa(adm.id, obra.id, adm.id)

        assert faixa_efetiva(req) is f1, (
            'no envio o fornecedor não existe — o acumulado dele não pode '
            'entrar na conta')
        assert req.degrau_aplicado == ''

        assert faixa_efetiva(req, fornecedor=forn) is f3
        assert req.degrau_aplicado == 'fracionamento'


def test_o_acumulado_nunca_faz_a_faixa_descer():
    """`max(valor da linha, acumulado)` — e o max não é decoração.

    Requisição de R$ 40.000 com um único pedido de R$ 100 no histórico do
    fornecedor: o acumulado é menor que a linha, e a faixa continua sendo a
    da linha. Teto é teto, e acumulado só sobe.
    """
    from services.alcada_compras import faixa_efetiva, valor_para_alcada
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _f1, _f2, f3 = _escada(adm.id)
        forn = _fornecedor(adm.id)
        _pedido(adm.id, forn.id, obra_id=obra.id, valor='100.00')

        req = _req_na_etapa(adm.id, obra.id, adm.id, valor='40000.00')
        assert valor_para_alcada(req, forn) == Decimal('40000.00')
        assert faixa_efetiva(req, fornecedor=forn) is f3
        assert req.degrau_aplicado == '', (
            'sem mudança de faixa não há fracionamento a registrar')


def test_fracionamento_e_condicao_somam_degraus_sem_contar_duas_vezes():
    """O acumulado move a BASE; as condições andam a partir dela.

    R$ 4.900 com duas irmãs na etapa vira base de 30k pelo acumulado; a
    condição `fora_do_orcamento` sobe mais um, e o resultado é a faixa aberta
    — não a de 30k contada duas vezes.
    """
    from services.alcada_compras import decisao_de_alcada
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        f1, _f2, f3 = _escada(adm.id, condicoes='fora_do_orcamento')
        etapa = _etapa(obra, orcado='1.00')

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        alvo = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)

        decisao = decisao_de_alcada(alvo)
        assert decisao.base is f1, (
            'a faixa BASE exibida continua sendo a do valor da linha — é o '
            'que a tela mostra como "pelo valor, cairia em"')
        assert decisao.efetiva is f3
        assert decisao.condicoes == ['fracionamento', 'fora_do_orcamento']
        assert alvo.degrau_aplicado == 'fracionamento,fora_do_orcamento'


def test_regime_simples_ignora_o_acumulado():
    """Paridade também vale para o acumulado: sem o carimbo, nada soma."""
    from services.alcada_compras import faixa_efetiva, faixa_para_valor
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _escada(adm.id)
        etapa = _etapa(obra)

        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, regime='simples')
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id, regime='simples')
        alvo = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id,
                             regime='simples')

        assert faixa_efetiva(alvo) is faixa_para_valor(adm.id,
                                                       alvo.valor_estimado)
        assert alvo.degrau_aplicado == ''


def test_envio_pela_tela_carimba_o_fracionamento_e_anuncia_a_faixa_nova():
    """O chokepoint do envio (`requisicao_enviar`) é quem persiste o carimbo.

    `faixa_efetiva` escreve na sessão e não commita — quem commita é a rota,
    e é por isso que o carimbo tem de ser conferido DEPOIS do POST.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        _escada(adm.id)
        etapa = _etapa(obra)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        aid, oid, eid = adm.id, obra.id, etapa.id

    cliente = _cliente_de(aid)
    assert cliente.post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'obra_servico_custo_id': str(eid),
        'justificativa': 'A terceira compra da mesma etapa no mês',
        'item_descricao[]': ['Cimento CP-II'],
        'item_unidade[]': ['sc'],
        'item_quantidade[]': ['49'],
        'item_preco[]': ['100,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False).status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(
            admin_id=aid, obra_servico_custo_id=eid).filter(
                RequisicaoCompra.valor_estimado == Decimal('4900.00')).order_by(
                    RequisicaoCompra.id.desc()).first()
        rid = req.id

    html = cliente.post(f'/compras/requisicoes/{rid}/enviar',
                        follow_redirects=True).get_data(as_text=True)
    assert 'acumulado' in html.lower(), (
        'o envio anuncia que a faixa subiu por acumulado — quem envia precisa '
        'saber que a exigência mudou antes de ir cobrar aprovação')

    with app.app_context():
        req = db.session.get(RequisicaoCompra, rid)
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO
        assert 'fracionamento' in req.degrau_aplicado


def test_emissao_recusa_quando_o_acumulado_do_fornecedor_sobe_a_faixa():
    """D3 na emissão: recusa com SAÍDA, e sem invalidar a aprovação dada.

    A requisição foi aprovada na faixa do valor dela, e a aprovação continua
    valendo: o estado segue APROVADA. O que a emissão faz é não sair calada —
    o acumulado com este fornecedor põe a compra numa faixa que pede mais
    aprovação do que a requisição tem, e a mensagem diz o que fazer.
    """
    from scripts.flag_alcadas_avancadas import definir_flag
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        definir_flag(adm.id, True)
        _escada(adm.id)
        comprador = _operador(adm.id, 'Comprador')
        gestor = _operador(adm.id, 'Gestor')
        _vincular(comprador, obra, PapelObra.COMPRADOR)
        _vincular(gestor, obra, PapelObra.GESTOR)
        forn = _fornecedor(adm.id)
        _pedido(adm.id, forn.id, obra_id=obra.id, valor='20000.00')
        _pedido(adm.id, forn.id, obra_id=obra.id, valor='20000.00')
        aid, oid, cid, gid, fid = (adm.id, obra.id, comprador.id, gestor.id,
                                   forn.id)

    cliente = _cliente_de(cid)
    assert cliente.post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'justificativa': 'Mais uma parcela do mesmo fornecedor',
        'item_descricao[]': ['Tubo PVC'],
        'item_unidade[]': ['un'],
        'item_quantidade[]': ['49'],
        'item_preco[]': ['100,00'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False).status_code == 302

    with app.app_context():
        rid = RequisicaoCompra.query.filter_by(admin_id=aid).one().id

    cliente.post(f'/compras/requisicoes/{rid}/enviar', follow_redirects=False)
    _cliente_de(gid).post(f'/compras/requisicoes/{rid}/aprovar',
                          follow_redirects=False)
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).estado == \
            EstadoRequisicao.APROVADA, (
            'a faixa do valor pede uma aprovação, e ela foi dada')

    html = cliente.post(
        f'/compras/requisicoes/{rid}/emitir-pedido',
        data={'fornecedor_id': str(fid), 'data_compra': date.today().isoformat()},
        follow_redirects=True).get_data(as_text=True)

    assert 'acumulado' in html.lower(), (
        'a recusa nomeia o FATO que a gerou, não só a exigência')
    assert 'reenvie para aprovação' in html, (
        'D3 é degrau, não bloqueio: a mensagem diz o que fazer para seguir')

    with app.app_context():
        req = db.session.get(RequisicaoCompra, rid)
        assert PedidoCompra.query.filter_by(requisicao_id=rid).count() == 0
        assert req.estado == EstadoRequisicao.APROVADA, (
            'o degrau por fracionamento NÃO invalida a aprovação já dada')
        assert 'fracionamento' in req.degrau_aplicado, (
            'e a trilha fica gravada, senão quem for reaprovar não vê por quê')


def test_listagem_marca_quem_subiu_por_acumulado():
    """O marcador na listagem — o aprovador escolhe o que abrir por ele."""
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        etapa = _etapa(obra)
        req = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        req.degrau_aplicado = 'fracionamento'
        comum = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        db.session.commit()
        aid, numero, numero_comum = adm.id, req.numero, comum.numero

    html = _cliente_de(aid).get('/compras/requisicoes').get_data(as_text=True)
    assert numero in html and numero_comum in html
    assert 'acumulado' in html.lower(), (
        'a listagem tem de marcar quem subiu por acumulado')


def test_detalhe_mostra_as_irmas_da_janela_com_numero_e_valor():
    """O fato que gerou a exigência, na mesma tela em que a exigência aparece.

    Aprovador que vê "esta requisição subiu de faixa" sem ver QUAIS irmãs
    somaram liga para o suporte — foi o defeito nº 8 da revisão da Fase 3.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        _escada(adm.id)
        etapa = _etapa(obra)
        irma1 = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        irma2 = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        alvo = _req_na_etapa(adm.id, obra.id, adm.id, etapa.id)
        alvo.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()
        aid, rid = adm.id, alvo.id
        numeros = (irma1.numero, irma2.numero)

    html = _cliente_de(aid).get(
        f'/compras/requisicoes/{rid}').get_data(as_text=True)
    for numero in numeros:
        assert numero in html, f'a irmã {numero} tem de aparecer no detalhe'
    assert '14700' in html.replace('.', '').replace(',', ''), (
        'e o acumulado da janela tem de estar escrito')
    assert '4900' in html.replace('.', '').replace(',', ''), (
        'com o valor de cada irmã, não só a soma')
