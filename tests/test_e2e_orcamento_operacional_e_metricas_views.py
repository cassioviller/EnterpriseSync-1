"""
tests/test_e2e_orcamento_operacional_e_metricas_views.py — Task #4 (Power Mode review)

Testes E2E HTTP cobrindo as 3 features auditadas via Flask test_client:

  Orçamento Operacional (Task #1):
    1. GET  /obra/<id>/orcamento-operacional/                    → 200 + clonagem lazy
    2. POST .../item/<item_id>/salvar (modo a_partir_de_hoje)    → cria nova versão
    3. POST .../atualizar-do-original (lista vazia)              → flash 'Nenhuma diferença'

  Métricas (Task #3):
    4. GET  /metricas/funcionarios                               → 200 (lista vazia tolerada)
    5. GET  /metricas/ranking                                    → 200
    6. GET  /metricas/ranking?exportar=csv                       → 200 + Content-Type CSV
    7. GET  /metricas/funcionarios/<outro_admin_id>              → 404 (isolamento de tenant)
"""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.datastructures import MultiDict
from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario, Cliente, Obra, Funcionario,
    Orcamento, OrcamentoItem, Proposta,
    ObraOrcamentoOperacional, ObraOrcamentoOperacionalItem,
    ObraOrcamentoOperacionalItemVersao,
)


def _suf():
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


@pytest.fixture(scope='module')
def ctx():
    """Cria admin + obra + orçamento original com 1 item composto."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        s = _suf()
        admin = Usuario(
            username=f't4_{s}',
            email=f't4_{s}@sige.test',
            nome='Admin Task#4',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()

        outro_admin = Usuario(
            username=f't4o_{s}',
            email=f't4o_{s}@sige.test',
            nome='Outro Admin',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(outro_admin); db.session.flush()

        cli = Cliente(admin_id=admin.id, nome=f'Cli T4 {s}', email=f'cli_{s}@x.com')
        db.session.add(cli); db.session.flush()

        orc = Orcamento(
            admin_id=admin.id, numero=f'ORC-T4-{s[-6:]}',
            titulo='Orc T4', cliente_id=cli.id, status='fechado',
        )
        db.session.add(orc); db.session.flush()

        item_orc = OrcamentoItem(
            admin_id=admin.id, orcamento_id=orc.id, ordem=1,
            descricao='Alvenaria m²', unidade='m2', quantidade=100,
            margem_pct=20, imposto_pct=10,
            composicao_snapshot=[
                {'tipo': 'MATERIAL', 'insumo_id': None, 'nome': 'Cimento',
                 'unidade': 'kg', 'coeficiente': 5.0, 'preco_unitario': 1.5,
                 'subtotal_unitario': 7.5},
                {'tipo': 'MAO_OBRA', 'insumo_id': None, 'nome': 'Pedreiro',
                 'unidade': 'h', 'coeficiente': 0.5, 'preco_unitario': 30.0,
                 'subtotal_unitario': 15.0},
            ],
        )
        db.session.add(item_orc); db.session.flush()

        prop = Proposta(
            admin_id=admin.id, numero=f'PROP-T4-{s[-6:]}',
            data_proposta=date(2026, 3, 1), titulo='Prop T4',
            cliente_id=cli.id,
            cliente_nome=cli.nome,
            cliente_email=cli.email,
            orcamento_id=orc.id, status='aprovada',
        )
        db.session.add(prop); db.session.flush()

        obra = Obra(
            admin_id=admin.id, cliente_id=cli.id,
            nome=f'Obra T4 {s}', codigo=f'OT4{s[:8]}',
            data_inicio=date(2026, 3, 1),
            valor_contrato=500000,
            proposta_origem_id=prop.id,
        )
        db.session.add(obra); db.session.commit()

        # Funcionário do "outro admin" para teste de isolamento
        outro_func = Funcionario(
            admin_id=outro_admin.id,
            codigo=f'O{s[:6]}',
            nome='Funcionario Outro Admin',
            cpf=f'9{s[-10:]}',
            data_admissao=date(2026, 1, 1),
            ativo=True,
        )
        db.session.add(outro_func); db.session.commit()

        yield {
            'admin_id': admin.id,
            'outro_admin_id': outro_admin.id,
            'obra_id': obra.id,
            'orc_item_id': item_orc.id,
            'outro_func_id': outro_func.id,
        }


def _client_logado(user_id: int):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ──────────────────────────────────────────────────────────────────────────────
# Orçamento Operacional (Task #1)
# ──────────────────────────────────────────────────────────────────────────────

def test_get_index_clona_lazy_e_renderiza(ctx):
    """GET na index deve clonar do original (lazy) e renderizar 200 com tabs."""
    with app.app_context():
        c = _client_logado(ctx['admin_id'])
        resp = c.get(f'/obra/{ctx["obra_id"]}/orcamento-operacional/')
        assert resp.status_code == 200, f'esperado 200, obtido {resp.status_code}'
        html = resp.get_data(as_text=True)
        # Cabeçalho da tela
        assert 'Orçamento Operacional' in html
        # Aba "Itens (1)" — clonou o item do original
        assert 'Itens (1)' in html, 'esperava aba Itens com 1 item após lazy-clone'
        # Componentes do item devem aparecer como inputs
        assert 'Cimento' in html
        assert 'Pedreiro' in html

        # Persistência: ObraOrcamentoOperacional + 1 item + 1 versão (clonagem_inicial)
        op = ObraOrcamentoOperacional.query.filter_by(obra_id=ctx['obra_id']).first()
        assert op is not None
        itens = ObraOrcamentoOperacionalItem.query.filter_by(operacional_id=op.id).all()
        assert len(itens) == 1
        versoes = ObraOrcamentoOperacionalItemVersao.query.filter_by(item_id=itens[0].id).all()
        assert len(versoes) == 1
        assert versoes[0].modo_aplicacao == 'clonagem_inicial'


def test_post_salvar_item_cria_nova_versao_a_partir_de_hoje(ctx):
    """POST salvar com modo='a_partir_de_hoje' fecha vigente + abre nova versão."""
    with app.app_context():
        op = ObraOrcamentoOperacional.query.filter_by(obra_id=ctx['obra_id']).first()
        item = ObraOrcamentoOperacionalItem.query.filter_by(operacional_id=op.id).first()
        item_id = item.id
        n_versoes_antes = ObraOrcamentoOperacionalItemVersao.query.filter_by(item_id=item_id).count()

        c = _client_logado(ctx['admin_id'])
        resp = c.post(
            f'/obra/{ctx["obra_id"]}/orcamento-operacional/item/{item_id}/salvar',
            data=MultiDict([
                ('modo_aplicacao', 'a_partir_de_hoje'),
                ('motivo', 'Reajuste de preço do cimento'),
                ('comp_tipo', 'MATERIAL'),
                ('comp_nome', 'Cimento'),
                ('comp_unidade', 'kg'),
                ('comp_coeficiente', '5,0000'),
                ('comp_preco_unitario', '2,00'),
                ('comp_insumo_id', ''),
                ('comp_tipo', 'MAO_OBRA'),
                ('comp_nome', 'Pedreiro'),
                ('comp_unidade', 'h'),
                ('comp_coeficiente', '0,5000'),
                ('comp_preco_unitario', '30,00'),
                ('comp_insumo_id', ''),
                ('margem_pct', '25,00'),
                ('imposto_pct', '10,00'),
            ]),
            follow_redirects=False,
        )
        assert resp.status_code == 302, f'esperava redirect 302, obtido {resp.status_code}'

        n_versoes_depois = ObraOrcamentoOperacionalItemVersao.query.filter_by(item_id=item_id).count()
        assert n_versoes_depois == n_versoes_antes + 1, (
            f'modo a_partir_de_hoje deve criar 1 nova versão (antes={n_versoes_antes}, depois={n_versoes_depois})'
        )

        # Apenas 1 vigente (vigente_ate IS NULL)
        vigentes = ObraOrcamentoOperacionalItemVersao.query.filter_by(
            item_id=item_id, vigente_ate=None
        ).all()
        assert len(vigentes) == 1
        # Nova versão refletindo o preço atualizado de cimento (2.00)
        comp = vigentes[0].composicao_snapshot or []
        cimento = next((c for c in comp if c.get('nome') == 'Cimento'), None)
        assert cimento is not None
        assert float(cimento['preco_unitario']) == pytest.approx(2.0)
        assert vigentes[0].motivo == 'Reajuste de preço do cimento'


def test_post_atualizar_do_original_sem_diff_flash_info(ctx):
    """Após sincronizar, propagar do original sem diferenças deve devolver flash 'info'."""
    with app.app_context():
        # Re-alinhar: aplica retroativo com os MESMOS valores do original para zerar diffs
        c = _client_logado(ctx['admin_id'])
        op = ObraOrcamentoOperacional.query.filter_by(obra_id=ctx['obra_id']).first()
        item = ObraOrcamentoOperacionalItem.query.filter_by(operacional_id=op.id).first()
        c.post(
            f'/obra/{ctx["obra_id"]}/orcamento-operacional/item/{item.id}/salvar',
            data=MultiDict([
                ('modo_aplicacao', 'retroativo'),
                ('comp_tipo', 'MATERIAL'),
                ('comp_nome', 'Cimento'),
                ('comp_unidade', 'kg'),
                ('comp_coeficiente', '5,0000'),
                ('comp_preco_unitario', '1,50'),
                ('comp_insumo_id', ''),
                ('comp_tipo', 'MAO_OBRA'),
                ('comp_nome', 'Pedreiro'),
                ('comp_unidade', 'h'),
                ('comp_coeficiente', '0,5000'),
                ('comp_preco_unitario', '30,00'),
                ('comp_insumo_id', ''),
                ('margem_pct', '20,00'),
                ('imposto_pct', '10,00'),
            ]),
        )

        # Agora atualizar-do-original sem item_ids → todos divergentes (zero) → flash info
        resp = c.post(
            f'/obra/{ctx["obra_id"]}/orcamento-operacional/atualizar-do-original',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'alinhado' in html.lower() or 'nenhuma diferença' in html.lower(), (
            'esperava flash informando que operacional já está alinhado com o original'
        )


# ──────────────────────────────────────────────────────────────────────────────
# Métricas (Task #3)
# ──────────────────────────────────────────────────────────────────────────────

def test_get_metricas_funcionarios_renderiza_vazio(ctx):
    """Sem RDOs/funcionários no admin de teste, renderiza 200 com mensagem informativa."""
    with app.app_context():
        c = _client_logado(ctx['admin_id'])
        resp = c.get('/metricas/funcionarios')
        assert resp.status_code == 200, f'esperava 200, obtido {resp.status_code}'
        html = resp.get_data(as_text=True)
        assert 'Métricas de Funcionários' in html


def test_get_metricas_ranking_renderiza(ctx):
    """Ranking renderiza 200 mesmo sem dados."""
    with app.app_context():
        c = _client_logado(ctx['admin_id'])
        resp = c.get('/metricas/ranking')
        assert resp.status_code == 200, f'esperava 200, obtido {resp.status_code}'
        html = resp.get_data(as_text=True)
        assert 'Ranking de Funcionários' in html


def test_get_metricas_ranking_export_csv(ctx):
    """Export CSV deve devolver Content-Type text/csv com cabeçalho esperado."""
    with app.app_context():
        c = _client_logado(ctx['admin_id'])
        resp = c.get('/metricas/ranking?exportar=csv')
        assert resp.status_code == 200
        ct = resp.headers.get('Content-type', '')
        assert 'text/csv' in ct, f'esperava text/csv no Content-type, obtido: {ct!r}'
        cd = resp.headers.get('Content-Disposition', '')
        assert 'attachment' in cd and 'ranking_' in cd, (
            f'esperava header attachment com prefixo ranking_, obtido: {cd!r}'
        )
        body = resp.get_data(as_text=True)
        # Cabeçalho da 1a linha do CSV
        assert body.startswith('Nome,'), f'CSV deveria começar com cabeçalho Nome,..., início: {body[:80]!r}'
        assert 'Lucro Total' in body.splitlines()[0]


def test_detalhe_funcionario_de_outro_admin_retorna_404(ctx):
    """Isolamento de tenant: funcionário de outro admin deve dar 404."""
    with app.app_context():
        c = _client_logado(ctx['admin_id'])
        resp = c.get(f'/metricas/funcionarios/{ctx["outro_func_id"]}')
        assert resp.status_code == 404, (
            f'esperava 404 (isolamento de tenant), obtido {resp.status_code}'
        )
