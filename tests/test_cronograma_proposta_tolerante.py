"""Caminho automático proposta→obra tolerante a catálogo incompleto.

Até 2026-07-21 um PropostaItem cujo serviço não tinha
`template_padrao_id` era marcado `sem_template=True` em
`montar_arvore_preview` (services/cronograma_proposta.py:280-290) e
descartado com um `continue` em `materializar_cronograma`
(:532-533). Resultado: obra aprovada nascia com ZERO tarefa, sem erro e
sem mensagem.

O que estes testes travam:
  * o `servico_id` do nó sem template passa pelo filtro de tenant
    (era cru — vazamento cross-tenant latente, :282);
  * o nó sem template ganha corpo (duracao_dias/unidade) para poder virar
    tarefa;
  * marcado=False continua o default (não regride
    tests/test_cronograma_automatico_aprovacao.py:303);
  * quando MARCADO, vira uma tarefa-esqueleto de nível 0.
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
from models import (Cliente, Obra, Proposta, PropostaItem, Servico,
                    TarefaCronograma, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-proposta-tolerante'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


def _admin():
    suf = _suf()
    u = Usuario(
        username=f'prop_{suf}', email=f'prop_{suf}@test.local',
        nome=f'Prop {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _cenario(admin_id, servico_admin_id=None):
    """Proposta com 1 item apontando para um Servico SEM template.

    `servico_admin_id` permite criar o serviço em OUTRO tenant, para o teste
    de vazamento.
    """
    suf = _suf()
    cliente = Cliente(nome=f'Cliente Prop {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.flush()

    servico = Servico(nome=f'Servico Sem Template {suf}',
                      categoria='Estrutural', unidade_medida='m2',
                      admin_id=servico_admin_id or admin_id, ativo=True)
    db.session.add(servico)
    db.session.flush()

    obra = Obra(nome=f'Obra Prop {suf}', codigo=f'PR-{suf[:8].upper()}',
                admin_id=admin_id, cliente_id=cliente.id,
                data_inicio=date(2026, 1, 1))
    db.session.add(obra)
    db.session.flush()

    proposta = Proposta(numero=f'P-{suf[:10]}', admin_id=admin_id,
                        cliente_id=cliente.id, obra_id=obra.id,
                        cliente_nome=cliente.nome, criado_por=admin_id,
                        status='enviada', valor_total=Decimal('40000.00'))
    db.session.add(proposta)
    db.session.flush()

    item = PropostaItem(admin_id=admin_id, proposta_id=proposta.id,
                        servico_id=servico.id, item_numero=1,
                        descricao='Estrutura em Light Steel Frame',
                        quantidade=Decimal('40'), unidade='m2',
                        preco_unitario=Decimal('1000.00'), ordem=1)
    db.session.add(item)
    db.session.commit()
    return {'admin_id': admin_id, 'obra': obra, 'proposta': proposta,
            'item': item, 'servico': servico}


def test_no_sem_template_nasce_desmarcado():
    """Não regride tests/test_cronograma_automatico_aprovacao.py:303."""
    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        assert len(arvore) == 1
        assert arvore[0]['sem_template'] is True
        assert arvore[0]['marcado'] is False


def test_servico_de_outro_tenant_nao_vaza_para_a_arvore():
    """services/cronograma_proposta.py:282 devolvia it.servico_id cru."""
    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin_a = _admin()
        admin_b = _admin()
        c = _cenario(admin_a.id, servico_admin_id=admin_b.id)
        arvore = montar_arvore_preview(c['proposta'], admin_a.id)
        assert arvore[0]['sem_template'] is True
        assert arvore[0]['servico_id'] is None, (
            'servico_id de outro tenant vazou para a árvore de preview')


def test_no_sem_template_tem_corpo_para_virar_tarefa():
    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        no = montar_arvore_preview(c['proposta'], admin.id)[0]
        assert no['duracao_dias'] >= 1
        assert no['responsavel'] == 'empresa'
        assert no['filhos'] == []
        # quantidade/unidade vêm do PropostaItem — é o único quantitativo que
        # existe quando não há template. Sem eles a tarefa nasce sem como ser
        # apontada por quantidade (services/cronograma_apontamento_service.py:95).
        assert float(no['quantidade_prevista']) == 40.0
        assert no['unidade_medida'] == 'm2'


def test_no_sem_template_marcado_vira_tarefa_esqueleto():
    """O `continue` de :532 fazia a obra nascer com ZERO tarefa, em silêncio."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        arvore[0]['marcado'] = True

        criadas = materializar_cronograma(
            c['proposta'], admin.id, c['obra'].id, arvore_marcada=arvore)
        db.session.commit()

        assert criadas == 1
        tarefas = TarefaCronograma.query.filter_by(
            obra_id=c['obra'].id, admin_id=admin.id,
            gerada_por_proposta_item_id=c['item'].id).all()
        assert len(tarefas) == 1
        t = tarefas[0]
        assert t.tarefa_pai_id is None, 'esqueleto é nó de nível 0'
        assert t.servico_id == c['servico'].id
        assert float(t.quantidade_total) == 40.0
        assert t.unidade_medida == 'm2'
        assert t.responsavel == 'empresa'


def test_esqueleto_nao_duplica_na_segunda_materializacao():
    """Idempotência prometida no docstring do módulo vale para o esqueleto."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        arvore[0]['marcado'] = True

        materializar_cronograma(c['proposta'], admin.id, c['obra'].id,
                                arvore_marcada=arvore)
        db.session.commit()
        materializar_cronograma(c['proposta'], admin.id, c['obra'].id,
                                arvore_marcada=arvore)
        db.session.commit()

        assert TarefaCronograma.query.filter_by(
            obra_id=c['obra'].id, admin_id=admin.id).count() == 1


def test_arvore_e_serializavel_em_json():
    """A árvore é persistida em `Proposta.cronograma_default_json` (coluna JSON).

    `PropostaItem.quantidade` é Numeric → Decimal, e Decimal não é
    serializável: devolver o valor cru quebrava o replay de pré-configuração
    de tests/test_cronograma_automatico_aprovacao.py:430 com
    `TypeError: Object of type Decimal is not JSON serializable`.
    """
    import json

    from services.cronograma_proposta import montar_arvore_preview

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        arvore = montar_arvore_preview(c['proposta'], admin.id)
        json.dumps(arvore)  # não pode levantar TypeError
        assert isinstance(arvore[0]['quantidade_prevista'], float)


def test_payload_da_tela_preserva_o_quantitativo():
    """Round-trip tela→`cronograma_default_json`→materialização.

    `_construirArvoreFinal()` (templates/propostas/cronograma_revisar.html:501)
    serializava só proposta_item_id/servico_id/servico_nome/template_id/
    template_nome/sem_template/horas_totais_estimadas/marcado/filhos —
    descartava o corpo do nó. Como a aprovação passa o JSON salvo DIRETO para
    `materializar_cronograma` (handlers/propostas_handlers.py:243), sem
    reconstruir a árvore, a tarefa-esqueleto nascia sem quantidade e caía no
    fallback percentual.

    Este teste monta o payload com os campos que a tela hoje envia; se alguém
    voltar a podá-los no JS, ele quebra.
    """
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        no = montar_arvore_preview(c['proposta'], admin.id)[0]

        # Espelha _construirArvoreFinal() com o admin tendo marcado o card.
        payload = [{
            'proposta_item_id': no['proposta_item_id'],
            'servico_id': no['servico_id'],
            'servico_nome': no['servico_nome'],
            'template_id': no['template_id'],
            'template_nome': no['template_nome'],
            'sem_template': no['sem_template'],
            'horas_totais_estimadas': no['horas_totais_estimadas'],
            'duracao_dias': no['duracao_dias'],
            'quantidade_prevista': no['quantidade_prevista'],
            'unidade_medida': no['unidade_medida'],
            'responsavel': no['responsavel'],
            'marcado': True,
            'filhos': [],
        }]
        c['proposta'].cronograma_default_json = payload
        db.session.commit()

        materializar_cronograma(
            c['proposta'], admin.id, c['obra'].id,
            arvore_marcada=c['proposta'].cronograma_default_json)
        db.session.commit()

        t = TarefaCronograma.query.filter_by(
            obra_id=c['obra'].id, admin_id=admin.id,
            gerada_por_proposta_item_id=c['item'].id).one()
        assert t.quantidade_total is not None, (
            'quantitativo perdido no round-trip — tarefa cai no fallback percentual')
        assert float(t.quantidade_total) == 40.0
        assert t.unidade_medida == 'm2'


def test_tela_de_revisao_deixa_marcar_o_no_sem_template():
    """O checkbox do nó sem template vinha `disabled`.

    templates/propostas/cronograma_revisar.html:266 renderizava
    `<input ... disabled title="...não gera tarefas">`, então o caminho de
    materialização era inalcançável pela UI: o admin não tinha como marcar.
    """
    import re

    with app.app_context():
        admin = _admin()
        c = _cenario(admin.id)
        pid = c['proposta'].id
        email = admin.email

    with app.test_client() as client:
        r = client.post('/login', data={'email': email,
                                        'password': 'Senha@2026'})
        assert r.status_code in (302, 303), f'login falhou: {r.status_code}'
        r = client.get(f'/propostas/{pid}/cronograma-revisar')
        assert r.status_code == 200, f'página não abriu: {r.status_code}'
        html = r.get_data(as_text=True)

    card = re.search(r'<div class="tree-card[^>]*no-template.*?</div>\s*</div>',
                     html, re.S)
    assert card, 'card sem template não foi renderizado'
    trecho = card.group(0)
    assert 'chk-raiz' in trecho, 'checkbox do nó sem template não é marcável'
    assert 'disabled' not in trecho, 'checkbox do nó sem template voltou a ser disabled'
    assert 'não gera tarefas' not in html, (
        'copy desatualizada: o nó sem template agora gera 1 tarefa')


def _com_template(admin_id, servico, n_folhas=2):
    """Vincula um template de 2 folhas ao serviço, para exercitar o ramo
    COM template de `materializar_cronograma` (folhas, não raiz-esqueleto)."""
    from models import (CronogramaTemplate, CronogramaTemplateItem,
                        SubatividadeMestre)

    suf = _suf()
    tmpl = CronogramaTemplate(nome=f'Tmpl {suf}', categoria='Estrutural',
                              admin_id=admin_id, ativo=True)
    db.session.add(tmpl)
    db.session.flush()
    for i in range(n_folhas):
        sub = SubatividadeMestre(servico_id=servico.id, tipo='subatividade',
                                 nome=f'Sub {i} {suf}', admin_id=admin_id,
                                 duracao_estimada_horas=8.0,
                                 unidade_medida='m2')
        db.session.add(sub)
        db.session.flush()
        db.session.add(CronogramaTemplateItem(
            template_id=tmpl.id, subatividade_mestre_id=sub.id,
            admin_id=admin_id, nome_tarefa=sub.nome, duracao_dias=2,
            quantidade_prevista=20.0, ordem=i))
    servico.template_padrao_id = tmpl.id
    db.session.commit()
    return tmpl


def _materializar_em_regime(admin_id, regime, com_template=False):
    """Materializa uma proposta numa obra do regime dado. Devolve as tarefas."""
    from services.cronograma_proposta import (materializar_cronograma,
                                              montar_arvore_preview)

    c = _cenario(admin_id)
    if com_template:
        _com_template(admin_id, c['servico'])
    c['obra'].regime_medicao = regime
    db.session.commit()

    arvore = montar_arvore_preview(c['proposta'], admin_id)
    arvore[0]['marcado'] = True
    materializar_cronograma(c['proposta'], admin_id, c['obra'].id,
                            arvore_marcada=arvore)
    db.session.commit()
    return TarefaCronograma.query.filter_by(
        obra_id=c['obra'].id, admin_id=admin_id).all()


@pytest.mark.parametrize('com_template', [False, True],
                         ids=['esqueleto', 'folhas-de-template'])
def test_obra_percentual_materializa_tarefa_em_modo_percentual(com_template):
    """`cronograma_views.criar_tarefa:471` aplica o default de regime da obra,
    mas só no caminho de criação MANUAL.

    Tarefa nascida de proposta ficava com `modo_apontamento` NULL, e
    `modo_da_tarefa` deduzia 'quantidade' a partir do quantitativo comercial
    — contradizendo uma obra que fatura pelo % físico do RDO.
    """
    from services.cronograma_apontamento_service import modo_da_tarefa

    with app.app_context():
        admin = _admin()
        tarefas = _materializar_em_regime(admin.id, 'percentual',
                                          com_template=com_template)
        assert tarefas
        for t in tarefas:
            assert t.modo_apontamento == 'percentual', (
                f'{t.nome_tarefa}: regime da obra não chegou à tarefa')
            assert modo_da_tarefa(t) == 'percentual', (
                f'{t.nome_tarefa}: modo contradiz o regime da obra')


@pytest.mark.parametrize('com_template', [False, True],
                         ids=['esqueleto', 'folhas-de-template'])
def test_obra_fixa_mantem_a_deducao_legada(com_template):
    """`'fixa'` é o default do schema: a coluna fica NULL e a dedução por
    quantitativo continua valendo. Nada muda nas obras existentes."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    with app.app_context():
        admin = _admin()
        tarefas = _materializar_em_regime(admin.id, 'fixa',
                                          com_template=com_template)
        assert tarefas
        for t in tarefas:
            assert t.modo_apontamento is None, (
                f'{t.nome_tarefa}: obra fixa não deve gravar modo explícito')
        folhas = [t for t in tarefas if t.quantidade_total]
        assert folhas, 'cenário não produziu folha com quantitativo'
        for t in folhas:
            assert modo_da_tarefa(t) == 'quantidade'


def _cenario_orcamento(admin_id, servico_admin_id=None):
    """Orçamento com 1 item apontando para um Servico SEM template."""
    from models import Orcamento, OrcamentoItem

    suf = _suf()
    cliente = Cliente(nome=f'Cliente Orc {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.flush()

    servico = Servico(nome=f'Servico Orc Sem Template {suf}',
                      categoria='Estrutural', unidade_medida='m2',
                      admin_id=servico_admin_id or admin_id, ativo=True)
    db.session.add(servico)
    db.session.flush()

    orc = Orcamento(admin_id=admin_id, numero=f'O-{suf[:10]}',
                    titulo=f'Orcamento {suf}', cliente_id=cliente.id,
                    cliente_nome=cliente.nome, criado_por=admin_id,
                    status='rascunho')
    db.session.add(orc)
    db.session.flush()

    item = OrcamentoItem(admin_id=admin_id, orcamento_id=orc.id,
                         servico_id=servico.id, ordem=1,
                         descricao='Estrutura em Light Steel Frame',
                         quantidade=Decimal('40'), unidade='m2')
    db.session.add(item)
    db.session.commit()
    return {'orcamento': orc, 'item': item, 'servico': servico}


def test_orcamento_no_sem_template_tem_o_mesmo_shape_da_proposta():
    """Paridade de shape entre as duas árvores de preview.

    A árvore do orçamento nunca é materializada (`materializar_cronograma` lê
    `proposta_item_id`), mas alimenta orcamentos/editar.html. Se divergir, a
    tela do orçamento promete um cronograma diferente do que a proposta gera.
    """
    from services.cronograma_proposta import (montar_arvore_preview,
                                              montar_arvore_preview_orcamento)

    with app.app_context():
        admin = _admin()
        no_orc = montar_arvore_preview_orcamento(
            _cenario_orcamento(admin.id)['orcamento'], admin.id)[0]
        no_prop = montar_arvore_preview(
            _cenario(admin.id)['proposta'], admin.id)[0]

        comuns = set(no_prop) - {'proposta_item_id'}
        assert comuns - set(no_orc) == set(), (
            'nó sem template do orçamento perdeu campos que a proposta tem')
        for campo in ('duracao_dias', 'quantidade_prevista', 'unidade_medida',
                      'responsavel', 'marcado'):
            assert no_orc[campo] == no_prop[campo], f'divergência em {campo}'


def test_orcamento_arvore_e_serializavel_em_json():
    """`OrcamentoItem.quantidade` também é Numeric — vai direto para jsonify
    em /orcamentos/<id>/preview-cronograma (views/orcamentos_views.py:864)."""
    import json

    from services.cronograma_proposta import montar_arvore_preview_orcamento

    with app.app_context():
        admin = _admin()
        c = _cenario_orcamento(admin.id)
        arvore = montar_arvore_preview_orcamento(c['orcamento'], admin.id)
        json.dumps(arvore)
        assert isinstance(arvore[0]['quantidade_prevista'], float)


def test_orcamento_servico_de_outro_tenant_nao_vaza():
    """Mesmo vazamento de :282, no ramo do orçamento (:410)."""
    from services.cronograma_proposta import montar_arvore_preview_orcamento

    with app.app_context():
        admin_a = _admin()
        admin_b = _admin()
        c = _cenario_orcamento(admin_a.id, servico_admin_id=admin_b.id)
        no = montar_arvore_preview_orcamento(c['orcamento'], admin_a.id)[0]
        assert no['sem_template'] is True
        assert no['servico_id'] is None
