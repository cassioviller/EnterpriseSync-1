"""A tela de faixas de alçada — A7 da fase 3 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-15-alcadas-design.md (decisões D6 e D7)
Plano: docs/superpowers/plans/2026-08-15-plano-execucao-alcadas.md (task A7)

`FaixaAlcada` nunca teve CRUD: as faixas só existiam via migration 243 e
UPDATE manual. O passo 1 do runbook manda o operador conferir os tetos, o
`minimo_cotacoes` e as condições ativas ANTES de ligar a flag — e é por esta
tela que sai o UPDATE da D6 (a faixa de topo indo para `minimo_cotacoes = 3`,
que o backfill da 297 deliberadamente não fez).

Duas coisas que estes testes cobram e que não são detalhe de tela:

1. **As validações moram no serviço**, não no template. A tela é a primeira
   consumidora; o script de flag é a segunda; e SQL manual continua sendo
   possível. Por isso os testes batem no serviço além da rota.
2. **Faixa de outro tenant é 404, não 403.** É a convenção da casa — a
   resposta não confirma que a linha existe. Isolamento entre empresas é o
   defeito mais caro deste repositório e o teste existe para que ele não
   volte por uma tela nova.

Molde de tests/test_alcadas_avancadas.py: fixtures locais, tenant por uuid4,
sem depender de seed.
"""
import os
import sys
import uuid
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import ConfiguracaoEmpresa, FaixaAlcada, TipoUsuario, Usuario

pytestmark = pytest.mark.integration

URL_TELA = '/configuracoes/alcadas'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-faixa-alcada-tela'
    yield


# ---------------------------------------------------------------------------
# Helpers — tenant por uuid4, nada vindo de seed
# ---------------------------------------------------------------------------

def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'fxa_{suf}', email=f'fxa_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    db.session.add(ConfiguracaoEmpresa(admin_id=u.id,
                                       nome_empresa=f'Tenant {suf}'))
    db.session.commit()
    return u


def _funcionario(admin_id):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'fxf_{suf}', email=f'fxf_{suf}@test.local', nome=f'Func {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _faixa(admin_id, ordem, valor_ate, aprovacoes=1, exige_admin=False,
           minimo_cotacoes=0, condicoes='', ativo=True):
    f = FaixaAlcada(admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
                    aprovacoes_necessarias=aprovacoes,
                    exige_admin=exige_admin,
                    exige_mapa_concorrencia=minimo_cotacoes > 0,
                    minimo_cotacoes=minimo_cotacoes,
                    condicoes_ativas=condicoes, ativo=ativo)
    db.session.add(f)
    db.session.commit()
    return f


def _escada(admin_id):
    """As três faixas semeadas: 5k → 30k → teto aberto.

    A mesma escada de `FAIXAS_RECOMENDADAS`, montada à mão para que o teste
    não dependa de seed nem da migration 243.
    """
    return [
        _faixa(admin_id, 1, Decimal('5000.00'), aprovacoes=1),
        _faixa(admin_id, 2, Decimal('30000.00'), aprovacoes=2,
               exige_admin=True),
        _faixa(admin_id, 3, None, aprovacoes=2, exige_admin=True,
               minimo_cotacoes=2),
    ]


def _form(faixa, **troca):
    """O formulário COMPLETO da faixa, como a tela o envia.

    A tela posta todos os campos de uma linha por vez; um teste que mandasse
    só o campo alterado provaria um contrato que a tela não usa.
    """
    dados = {
        'ordem': str(faixa.ordem),
        'valor_ate': ('' if faixa.valor_ate is None
                      else f'{faixa.valor_ate:.2f}'),
        'aprovacoes_necessarias': str(faixa.aprovacoes_necessarias),
        'minimo_cotacoes': str(faixa.minimo_cotacoes),
        'condicoes': [c for c in (faixa.condicoes_ativas or '').split(',') if c],
    }
    if faixa.exige_admin:
        dados['exige_admin'] = 'on'
    if faixa.ativo:
        dados['ativo'] = 'on'
    dados.update(troca)
    return dados


def _url_salvar(faixa_id):
    return f'{URL_TELA}/{faixa_id}'


# ---------------------------------------------------------------------------
# Quem alcança a tela
# ---------------------------------------------------------------------------

def test_a_tela_lista_as_faixas_do_proprio_tenant():
    with app.app_context():
        adm = _admin()
        _escada(adm.id)
        resp = _cliente_de(adm.id).get(URL_TELA)
        assert resp.status_code == 200
        corpo = resp.get_data(as_text=True)
        assert '5.000' in corpo or '5000' in corpo
        assert '30.000' in corpo or '30000' in corpo


def test_funcionario_nao_alcanca_a_tela_de_faixas():
    """Só ADMIN. Alçada é a régua de quem aprova — quem é regido por ela não
    a edita, e a tela nem chega a renderizar para um FUNCIONARIO."""
    with app.app_context():
        adm = _admin()
        _escada(adm.id)
        func = _funcionario(adm.id)
        resp = _cliente_de(func.id).get(URL_TELA)
        assert resp.status_code != 200
        assert resp.status_code in (302, 403)


def test_a_tela_nao_mostra_faixa_de_outro_tenant():
    with app.app_context():
        adm_a, adm_b = _admin(), _admin()
        _escada(adm_a.id)
        _faixa(adm_b.id, 1, Decimal('777777.00'))
        corpo = _cliente_de(adm_a.id).get(URL_TELA).get_data(as_text=True)
        assert '777777' not in corpo and '777.777' not in corpo


def test_editar_faixa_de_outro_tenant_devolve_404_e_nao_403():
    """404 e não 403: a resposta não confirma que a linha existe.

    É a convenção da casa (`first_or_404` filtrado por `admin_id`), e o motivo
    é que 403 já é vazamento — diz ao vizinho que aquele id é de alguém.
    """
    with app.app_context():
        adm_a, adm_b = _admin(), _admin()
        propria = _escada(adm_a.id)[0]
        alheia = _faixa(adm_b.id, 1, Decimal('5000.00'))

        resp = _cliente_de(adm_a.id).post(_url_salvar(alheia.id),
                                          data=_form(alheia, ordem='1',
                                                     valor_ate='9999.00'))
        assert resp.status_code == 404
        db.session.refresh(alheia)
        assert alheia.valor_ate == Decimal('5000.00')

        # Controle: o MESMO POST na faixa própria passa. Sem ele, um 404 de
        # rota inexistente pareceria isolamento funcionando.
        resp = _cliente_de(adm_a.id).post(
            _url_salvar(propria.id), data=_form(propria, valor_ate='4999.00'))
        assert resp.status_code == 302
        db.session.refresh(propria)
        assert propria.valor_ate == Decimal('4999.00')


# ---------------------------------------------------------------------------
# O invariante da faixa de teto aberto — exatamente uma por tenant
# ---------------------------------------------------------------------------

def test_salvar_recusa_fechar_a_unica_faixa_de_teto_aberto():
    """`valor_ate` NULL é o teto aberto. Sem ele, valor acima de todas as
    faixas cai na falha fechada de `faixa_para_valor` — e o tenant descobre
    isso na primeira compra grande, não aqui."""
    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        resp = _cliente_de(adm.id).post(
            _url_salvar(topo.id), data=_form(topo, valor_ate='90000.00'),
            follow_redirects=True)
        db.session.refresh(topo)
        assert topo.valor_ate is None
        assert 'teto aberto' in resp.get_data(as_text=True)


def test_salvar_recusa_criar_uma_segunda_faixa_de_teto_aberto():
    with app.app_context():
        adm = _admin()
        baixa, _, _ = _escada(adm.id)
        resp = _cliente_de(adm.id).post(_url_salvar(baixa.id),
                                        data=_form(baixa, valor_ate=''),
                                        follow_redirects=True)
        db.session.refresh(baixa)
        assert baixa.valor_ate == Decimal('5000.00')
        # E o operador lê POR QUE foi recusado, na própria tela.
        assert 'não foi salva' in resp.get_data(as_text=True)


def test_tenant_que_ja_tem_dois_tetos_abertos_continua_editavel():
    """A tela recusa o que VOCÊ piora, nunca o que você herdou.

    O invariante nunca teve constraint (só docstring em `models.FaixaAlcada`),
    e há tenant com faixa editada por SQL. Se a validação olhasse só o estado
    final, um tenant já inconsistente ficaria travado justamente na tela que
    existe para consertá-lo.
    """
    with app.app_context():
        adm = _admin()
        um = _faixa(adm.id, 1, None, aprovacoes=1)
        _faixa(adm.id, 2, None, aprovacoes=2)
        resp = _cliente_de(adm.id).post(
            _url_salvar(um.id), data=_form(um, aprovacoes_necessarias='3'))
        assert resp.status_code in (200, 302)
        db.session.refresh(um)
        assert um.aprovacoes_necessarias == 3


def test_tenant_inconsistente_pode_ser_consertado_pela_tela():
    """E o conserto passa: de dois tetos abertos para um."""
    with app.app_context():
        adm = _admin()
        um = _faixa(adm.id, 1, None, aprovacoes=1)
        _faixa(adm.id, 2, None, aprovacoes=2)
        _cliente_de(adm.id).post(
            _url_salvar(um.id), data=_form(um, valor_ate='5000.00'))
        db.session.refresh(um)
        assert um.valor_ate == Decimal('5000.00')
        abertas = FaixaAlcada.query.filter_by(
            admin_id=adm.id, ativo=True, valor_ate=None).count()
        assert abertas == 1


def test_a_tela_avisa_quando_o_tenant_esta_inconsistente():
    with app.app_context():
        adm = _admin()
        _faixa(adm.id, 1, None)
        _faixa(adm.id, 2, None)
        corpo = _cliente_de(adm.id).get(URL_TELA).get_data(as_text=True)
        assert 'teto aberto' in corpo.lower()


# ---------------------------------------------------------------------------
# Tetos crescentes por ordem
# ---------------------------------------------------------------------------

def test_os_tetos_precisam_crescer_com_a_ordem():
    """Faixa 2 com teto menor que a 1 é escada que desce — e o degrau da A4
    anda POSIÇÕES nessa lista. Teto que desce faz o degrau punir menos."""
    with app.app_context():
        adm = _admin()
        _, meio, _ = _escada(adm.id)
        resp = _cliente_de(adm.id).post(_url_salvar(meio.id),
                                        data=_form(meio, valor_ate='1000.00'),
                                        follow_redirects=True)
        db.session.refresh(meio)
        assert meio.valor_ate == Decimal('30000.00')
        assert 'crescer com a ordem' in resp.get_data(as_text=True)


def test_subir_o_teto_do_meio_sem_furar_a_escada_e_aceito():
    with app.app_context():
        adm = _admin()
        _, meio, _ = _escada(adm.id)
        _cliente_de(adm.id).post(_url_salvar(meio.id),
                                 data=_form(meio, valor_ate='40000.00'))
        db.session.refresh(meio)
        assert meio.valor_ate == Decimal('40000.00')


def test_ordem_repetida_no_tenant_e_recusada():
    """`uq_faixa_alcada_admin_ordem` existe no banco; a tela recusa ANTES,
    para que o operador leia um motivo em português e não um IntegrityError."""
    with app.app_context():
        adm = _admin()
        baixa, meio, _ = _escada(adm.id)
        resp = _cliente_de(adm.id).post(_url_salvar(baixa.id),
                                        data=_form(baixa, ordem='2'),
                                        follow_redirects=True)
        db.session.refresh(baixa)
        assert baixa.ordem == 1
        assert 'já existe uma faixa de ordem 2' in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# minimo_cotacoes — 0 ou >= 2, nunca 1
# ---------------------------------------------------------------------------

def test_minimo_de_cotacoes_recusa_uma_cotacao_so():
    """Uma cotação não é concorrência, é orçamento. O 1 é o único inteiro não
    negativo que a coluna não aceita, e é justamente o que alguém digita
    achando que está exigindo 'pelo menos uma'."""
    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        resp = _cliente_de(adm.id).post(_url_salvar(topo.id),
                                        data=_form(topo, minimo_cotacoes='1'),
                                        follow_redirects=True)
        db.session.refresh(topo)
        assert topo.minimo_cotacoes == 2
        assert 'não é concorrência' in resp.get_data(as_text=True)


def test_minimo_de_cotacoes_zero_dispensa_o_mapa():
    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        _cliente_de(adm.id).post(_url_salvar(topo.id),
                                 data=_form(topo, minimo_cotacoes='0'))
        db.session.refresh(topo)
        assert topo.minimo_cotacoes == 0


def test_a_faixa_de_topo_sobe_para_tres_cotacoes_pela_tela():
    """O UPDATE da decisão D6, feito onde o runbook manda fazê-lo.

    O backfill da migration 297 deixou 2 de propósito (preserva o
    comportamento); subir para 3 é decisão de negócio, e o passo 1 do runbook
    a executa aqui, com o operador olhando a escada inteira.
    """
    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        _cliente_de(adm.id).post(_url_salvar(topo.id),
                                 data=_form(topo, minimo_cotacoes='3'))
        db.session.refresh(topo)
        assert topo.minimo_cotacoes == 3


def test_exige_mapa_concorrencia_passa_a_derivar_do_minimo_de_cotacoes():
    """A coluna antiga continua na tabela e não é mais lida (A3). A tela a
    mantém em sincronia com a nova, para que um SELECT velho não descreva o
    contrário do que o motor faz."""
    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        _cliente_de(adm.id).post(_url_salvar(topo.id),
                                 data=_form(topo, minimo_cotacoes='0'))
        db.session.refresh(topo)
        assert topo.exige_mapa_concorrencia is False

        _cliente_de(adm.id).post(_url_salvar(topo.id),
                                 data=_form(topo, minimo_cotacoes='3'))
        db.session.refresh(topo)
        assert topo.exige_mapa_concorrencia is True


# ---------------------------------------------------------------------------
# As quatro condições — os checkboxes que a A4 lê
# ---------------------------------------------------------------------------

def test_os_checkboxes_gravam_as_condicoes_na_ordem_canonica():
    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        _cliente_de(adm.id).post(
            _url_salvar(topo.id),
            data=_form(topo, condicoes=['fora_do_orcamento',
                                        'fornecedor_novo']))
        db.session.refresh(topo)
        assert topo.condicoes_ativas == 'fornecedor_novo,fora_do_orcamento'


def test_desmarcar_todos_os_checkboxes_desliga_as_condicoes():
    with app.app_context():
        adm = _admin()
        topo = _faixa(adm.id, 1, None, condicoes='fornecedor_novo,sem_cotacao')
        _cliente_de(adm.id).post(_url_salvar(topo.id),
                                 data=_form(topo, condicoes=[]))
        db.session.refresh(topo)
        assert topo.condicoes_ativas == ''


def test_condicao_desconhecida_no_formulario_e_recusada():
    """O POST não vem só da tela — vem de quem souber montar um. Condição que
    o motor não conhece viraria degrau que ninguém sabe explicar."""
    with app.app_context():
        adm = _admin()
        topo = _faixa(adm.id, 1, None, condicoes='fornecedor_novo')
        resp = _cliente_de(adm.id).post(
            _url_salvar(topo.id),
            data=_form(topo, condicoes=['fornecedor_novo', 'frete_caro']),
            follow_redirects=True)
        db.session.refresh(topo)
        assert topo.condicoes_ativas == 'fornecedor_novo'
        assert 'condição desconhecida' in resp.get_data(as_text=True)


def test_a_tela_oferece_as_quatro_condicoes():
    with app.app_context():
        adm = _admin()
        _escada(adm.id)
        corpo = _cliente_de(adm.id).get(URL_TELA).get_data(as_text=True)
        for codigo in ('fornecedor_novo', 'sem_cotacao', 'nao_menor_preco',
                       'fora_do_orcamento'):
            assert codigo in corpo


# ---------------------------------------------------------------------------
# O tenant sem faixa nenhuma — a falha fechada tem que ser visível
# ---------------------------------------------------------------------------

def test_tenant_sem_faixa_nenhuma_pode_semear_as_recomendadas():
    """Sem faixa, `faixa_para_valor` devolve a `_FaixaSeguranca` e ninguém vê
    isso numa tela. Semear é o caminho, e ele é explícito — não acontece por
    efeito colateral de abrir a página."""
    with app.app_context():
        adm = _admin()
        assert FaixaAlcada.query.filter_by(admin_id=adm.id).count() == 0
        cli = _cliente_de(adm.id)
        cli.post(f'{URL_TELA}/semear')
        faixas = (FaixaAlcada.query.filter_by(admin_id=adm.id)
                  .order_by(FaixaAlcada.ordem).all())
        assert [f.ordem for f in faixas] == [1, 2, 3]
        assert faixas[-1].valor_ate is None


def test_semear_nao_duplica_faixa_de_tenant_que_ja_tem():
    with app.app_context():
        adm = _admin()
        _escada(adm.id)
        resp = _cliente_de(adm.id).post(f'{URL_TELA}/semear',
                                        follow_redirects=True)
        assert FaixaAlcada.query.filter_by(admin_id=adm.id).count() == 3
        assert 'já tem faixas' in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# O serviço — a tela é a primeira consumidora, não a única
# ---------------------------------------------------------------------------

def test_o_servico_recusa_sem_precisar_da_tela():
    """As validações moram no serviço. O script de flag é a segunda
    consumidora e SQL manual continua possível — se a regra morasse no
    template, o único caminho protegido seria o do navegador."""
    from services.faixa_alcada_admin import FaixaInvalida, salvar_faixa

    with app.app_context():
        adm = _admin()
        _, _, topo = _escada(adm.id)
        with pytest.raises(FaixaInvalida) as erro:
            salvar_faixa(adm.id, topo.id, {'ordem': 3, 'valor_ate': None,
                                           'aprovacoes_necessarias': 2,
                                           'minimo_cotacoes': 1,
                                           'exige_admin': True, 'ativo': True,
                                           'condicoes': []})
        assert any('cotaç' in m.lower() for m in erro.value.erros)


def test_o_servico_enxerga_o_tenant_inconsistente():
    from services.faixa_alcada_admin import diagnosticar

    with app.app_context():
        adm_ok = _admin()
        _escada(adm_ok.id)
        assert diagnosticar(adm_ok.id) == []

        adm_ruim = _admin()
        _faixa(adm_ruim.id, 1, None)
        _faixa(adm_ruim.id, 2, None)
        assert diagnosticar(adm_ruim.id) != []
