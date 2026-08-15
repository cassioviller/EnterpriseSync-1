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
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, ConfiguracaoEmpresa, EstadoRequisicao, FaixaAlcada,
                    MapaConcorrenciaV2, MapaFornecedor, Obra, PapelObra,
                    RequisicaoCompra, TipoUsuario, Usuario, UsuarioObra)

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
