"""E2E do importador auto-wiring (services/importar_obra_completa.py).

Prova que importar um orçamento cria, sem config manual, a cadeia completa
vinculada (Proposta→Obra→IMC→Cronograma com pesos) e que o read-model
"Resultado por Atividade" funciona em cima disso após um apontamento.
"""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
import main  # noqa: F401 — registra blueprints (rota /orcamentos/<id>/importar-obra)
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    Orcamento, OrcamentoItem, Proposta, PropostaItem,
    ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, TarefaCronograma,
    RDO, RDOMaoObra, RDOCustoDiario,
)
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


class FX:
    admin = None


_fx = FX()


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        s = _sfx()
        admin = Usuario(
            username=f'imp_{s}', email=f'imp_{s}@sige.test', nome='Imp',
            tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.commit()
        _fx.admin = admin
        yield


def _orcamento_baia_like():
    """Orçamento com 2 itens e composicao_snapshot (1 MO em m², 1 MO+material)."""
    s = _sfx()
    orc = Orcamento(
        admin_id=_fx.admin.id, numero=f'ORC-T-{s}', titulo='Baia Teste',
        descricao='obra teste', cliente_nome='Cliente Teste',
        venda_total=Decimal('15000'), status='rascunho', criado_por=_fx.admin.id,
    )
    db.session.add(orc); db.session.flush()
    # Item 1: MO em m² (10/m²), material 40/m², qtd 100 → venda 5000
    i1 = OrcamentoItem(
        admin_id=_fx.admin.id, orcamento_id=orc.id, ordem=1,
        descricao='Alvenaria', unidade='m2', quantidade=Decimal('100'),
        preco_venda_unitario=Decimal('50'), venda_total=Decimal('5000'),
        composicao_snapshot=[
            {'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0},
            {'tipo': 'MATERIAL', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 40.0},
        ],
    )
    i2 = OrcamentoItem(
        admin_id=_fx.admin.id, orcamento_id=orc.id, ordem=2,
        descricao='Pintura', unidade='m2', quantidade=Decimal('200'),
        preco_venda_unitario=Decimal('50'), venda_total=Decimal('10000'),
        composicao_snapshot=[
            {'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 20.0},
        ],
    )
    db.session.add_all([i1, i2])
    db.session.commit()
    return orc


def test_import_auto_wire_cria_cadeia_completa():
    from services.importar_obra_completa import importar_obra_completa
    with app.app_context():
        orc = _orcamento_baia_like()
        res = importar_obra_completa(orc.id, _fx.admin.id)

        assert res['criado'] is True
        assert res['n_itens'] == 2
        assert res['n_tarefas'] == 2

        # Proposta criada e ligada ao orçamento, com snapshot propagado
        prop = Proposta.query.filter_by(orcamento_id=orc.id, admin_id=_fx.admin.id).first()
        assert prop is not None and prop.obra_id is not None
        pis = PropostaItem.query.filter_by(proposta_id=prop.id).all()
        assert len(pis) == 2
        assert all(pi.composicao_snapshot for pi in pis)   # snapshot copiado (custo orçado)

        # Obra + IMC 1:1
        obra = Obra.query.get(prop.obra_id)
        assert obra is not None
        imcs = ItemMedicaoComercial.query.filter_by(obra_id=obra.id).all()
        assert len(imcs) == 2

        # Cronograma sintetizado: 1 atividade por item, vínculo peso 100
        tarefas = TarefaCronograma.query.filter_by(obra_id=obra.id).all()
        assert len(tarefas) == 2
        for t in tarefas:
            links = ItemMedicaoCronogramaTarefa.query.filter_by(cronograma_tarefa_id=t.id).all()
            assert len(links) == 1
            assert Decimal(str(links[0].peso)) == Decimal('100')


def test_import_idempotente():
    from services.importar_obra_completa import importar_obra_completa
    with app.app_context():
        orc = _orcamento_baia_like()
        r1 = importar_obra_completa(orc.id, _fx.admin.id)
        r2 = importar_obra_completa(orc.id, _fx.admin.id)   # 2ª vez não duplica
        assert r2['criado'] is False
        assert r2['obra_id'] == r1['obra_id']
        obra_id = r1['obra_id']
        assert TarefaCronograma.query.filter_by(obra_id=obra_id).count() == 2
        assert ItemMedicaoComercial.query.filter_by(obra_id=obra_id).count() == 2
        prop = Proposta.query.filter_by(orcamento_id=orc.id).all()
        assert len(prop) == 1


def test_resultado_por_atividade_funciona_apos_import():
    """Depois do import, basta apontar um RDO para a tela ter dados reais."""
    from services.importar_obra_completa import importar_obra_completa
    from services.resultado_atividade_service import (
        valor_agregado_atividade, custo_mo_atividade, resultado_realizado_atividade,
        alarme_mo, resultado_obra,
    )
    with app.app_context():
        orc = _orcamento_baia_like()
        res = importar_obra_completa(orc.id, _fx.admin.id)
        obra_id = res['obra_id']

        # pega a atividade "Alvenaria" (item 1: MO orçada 10/m² × 100 = 1000)
        tarefa = (TarefaCronograma.query
                  .filter_by(obra_id=obra_id)
                  .filter(TarefaCronograma.nome_tarefa.like('Alvenaria%'))
                  .first())
        assert tarefa is not None

        # simula avanço 50% + 1 RDO com custo onerado de MO = 400
        tarefa.percentual_concluido = 50.0
        func = Funcionario(
            nome=f'F {_sfx()}', cpf=f'7{_sfx()}'.ljust(14, '0')[:14],
            codigo=f'F{_sfx()[:8]}', data_admissao=date(2025, 1, 1),
            admin_id=_fx.admin.id, tipo_remuneracao='salario', salario=3000.0,
            valor_va=0.0, valor_vt=0.0, ativo=True,
        )
        db.session.add(func); db.session.flush()
        rdo = RDO(numero_rdo=f'RDO-IMP-{_sfx()}', obra_id=obra_id,
                  data_relatorio=date(2026, 3, 1), admin_id=_fx.admin.id,
                  status='Finalizado', criado_por_id=_fx.admin.id)
        db.session.add(rdo); db.session.flush()
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, funcionario_id=func.id, funcao_exercida='Op',
            horas_trabalhadas=8.0, admin_id=_fx.admin.id,
            subatividade_id=None, tarefa_cronograma_id=tarefa.id,
        ))
        db.session.add(RDOCustoDiario(
            rdo_id=rdo.id, funcionario_id=func.id, admin_id=_fx.admin.id,
            data=rdo.data_relatorio, tipo_remuneracao_snapshot='salario',
            custo_total_dia=Decimal('400'), tipo_lancamento='rdo',
        ))
        db.session.commit()

        # venda agregada = 50% × 5000 (peso 100) = 2500; custo MO = 400 (1 func, 1 RDO)
        assert valor_agregado_atividade(tarefa) == Decimal('2500.00')
        assert custo_mo_atividade(tarefa) == Decimal('400.00')
        assert resultado_realizado_atividade(tarefa) == Decimal('2100.00')

        # alarme: orçado MO total = 1000; p/ avanço 50% = 500; real 400 → no verde
        a = alarme_mo(tarefa)
        assert a['orcado_para_avanco'] == Decimal('500.00')
        assert a['real'] == Decimal('400.00')
        assert a['estouro'] is False

        # rollup da obra inclui a atividade
        ro = resultado_obra(obra_id)
        assert ro['valor_agregado'] >= Decimal('2500.00')
        nomes = {x['nome'] for x in ro['atividades']}
        assert any(n.startswith('Alvenaria') for n in nomes)


def _servico_com_template(nome, itens_peso):
    """Cria um Servico com CronogramaTemplate de N itens, cada um com peso_medicao."""
    from models import Servico, CronogramaTemplate, CronogramaTemplateItem
    tmpl = CronogramaTemplate(nome=f'TMPL {nome} {_sfx()}', ativo=True, admin_id=_fx.admin.id)
    db.session.add(tmpl); db.session.flush()
    for i, (nm, peso) in enumerate(itens_peso, start=1):
        db.session.add(CronogramaTemplateItem(
            template_id=tmpl.id, nome_tarefa=nm, ordem=i, duracao_dias=1,
            admin_id=_fx.admin.id, peso_medicao=Decimal(str(peso)),
        ))
    serv = Servico(
        nome=f'{nome} {_sfx()}', categoria='Estrutura', unidade_medida='m2',
        admin_id=_fx.admin.id, template_padrao_id=tmpl.id,
    )
    db.session.add(serv); db.session.flush()
    return serv


def _orcamento_1item(servico_id, quantidade=100, venda=5000):
    s = _sfx()
    orc = Orcamento(
        admin_id=_fx.admin.id, numero=f'ORC-T1-{s}', titulo='Obra 1 item',
        descricao='t', cliente_nome='Cliente', venda_total=Decimal(str(venda)),
        status='rascunho', criado_por=_fx.admin.id,
    )
    db.session.add(orc); db.session.flush()
    db.session.add(OrcamentoItem(
        admin_id=_fx.admin.id, orcamento_id=orc.id, ordem=1,
        descricao='Serviço com template', unidade='m2', quantidade=Decimal(str(quantidade)),
        preco_venda_unitario=Decimal(str(venda)) / Decimal(str(quantidade)),
        venda_total=Decimal(str(venda)), servico_id=servico_id,
        composicao_snapshot=[
            {'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0},
        ],
    ))
    db.session.commit()
    return orc


def test_import_multi_atividade_via_template():
    """Serviço com CronogramaTemplate → importação cria N atividades com os
    pesos explícitos (peso_medicao), não 1:1."""
    from services.importar_obra_completa import importar_obra_completa
    with app.app_context():
        serv = _servico_com_template('Estrutura LSF', [('Painelização', 60), ('Montagem', 40)])
        orc = _orcamento_1item(serv.id)
        res = importar_obra_completa(orc.id, _fx.admin.id)
        obra_id = res['obra_id']

        tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id).order_by(TarefaCronograma.ordem).all()
        assert len(tarefas) == 2, [t.nome_tarefa for t in tarefas]
        pesos = {}
        for t in tarefas:
            link = ItemMedicaoCronogramaTarefa.query.filter_by(cronograma_tarefa_id=t.id).first()
            assert link is not None
            pesos[t.nome_tarefa] = Decimal(str(link.peso))
        assert pesos['Painelização'] == Decimal('60')
        assert pesos['Montagem'] == Decimal('40')
        assert sum(pesos.values()) == Decimal('100')


def test_import_marca_origem_e_sai_do_funil_comercial():
    """Delta 2 (ADR 0005): a Proposta de importação recebe origem='importacao_obra'
    e NÃO aparece na listagem comercial; uma proposta comercial normal aparece."""
    from datetime import date
    from services.importar_obra_completa import importar_obra_completa
    with app.app_context():
        orc = _orcamento_baia_like()
        res = importar_obra_completa(orc.id, _fx.admin.id)
        ponte = Proposta.query.filter_by(orcamento_id=orc.id).first()
        assert ponte.origem == 'importacao_obra'

        # proposta comercial normal (deve aparecer no funil)
        normal = Proposta(
            admin_id=_fx.admin.id, numero=f'PROP-NORMAL-{_sfx()}',
            cliente_nome='Cliente Normal', data_proposta=date(2026, 1, 1),
            status='pendente', origem=None,
        )
        db.session.add(normal); db.session.commit()

        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(_fx.admin.id)
                sess['_fresh'] = True
            resp = c.get('/propostas/')
        assert resp.status_code == 200, resp.status_code
        assert normal.numero.encode() in resp.data         # comercial aparece
        assert ponte.numero.encode() not in resp.data       # ponte não aparece


def test_rota_importar_obra_cria_e_redireciona():
    """Smoke da UI: POST /orcamentos/<id>/importar-obra cria a obra e redireciona."""
    with app.app_context():
        orc = _orcamento_baia_like()
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(_fx.admin.id)
                sess['_fresh'] = True
            resp = c.post(f'/orcamentos/{orc.id}/importar-obra', follow_redirects=False)
        assert resp.status_code in (302, 303), resp.status_code
        assert '/obras/' in resp.headers.get('Location', '')
        prop = Proposta.query.filter_by(orcamento_id=orc.id).first()
        assert prop is not None and prop.obra_id is not None
        assert TarefaCronograma.query.filter_by(obra_id=prop.obra_id).count() == 2
