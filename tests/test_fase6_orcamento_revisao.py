"""Fase 6 / Task 10 — cadeia de revisões do Orçamento.

Plano: docs/superpowers/plans/2026-07-21-fase-6-orcamento-versionado-aditivo.md

Hoje `duplicar` faz uma cópia integral e perde a relação com o original: o novo
orçamento nasce órfão, com o título `"… (cópia)"` e nenhum vínculo. Não dá para
responder "de qual revisão este preço veio" nem "quais são as revisões deste
orçamento" — que é a pergunta que o aditivo faz.

A cadeia é dupla de propósito:

- `revisao_de_id` aponta para a revisão IMEDIATAMENTE anterior (o elo);
- `origem_id` aponta sempre para a RAIZ da cadeia (o atalho).

Guardar só o elo obrigaria a subir a corrente inteira para achar a raiz, e é a
raiz que agrupa "todas as revisões deste orçamento" numa query só. Guardar só a
raiz perderia a ordem. Os dois são baratos e respondem perguntas diferentes.
"""
import os
import sys
from datetime import datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Orcamento, OrcamentoItem, TipoUsuario, Usuario
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.integration


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


@pytest.fixture
def ambiente():
    """Admin + um orçamento com 2 itens. Rollback ao final."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        suf = _suffix()
        admin = Usuario(
            username=f'orc_rev_{suf}',
            email=f'orc_rev_{suf}@test.local',
            nome='Orcamento Revisao',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()

        orc = Orcamento(
            admin_id=admin.id, numero=f'ORC-{suf[-10:]}',
            titulo='Galpão industrial', cliente_nome='Cliente Teste',
            status='rascunho', criado_por=admin.id,
        )
        db.session.add(orc)
        db.session.flush()
        for i, (desc, qtd) in enumerate(
                [('Estrutura metálica', 10), ('Cobertura', 25)], start=1):
            db.session.add(OrcamentoItem(
                admin_id=admin.id, orcamento_id=orc.id, ordem=i,
                descricao=desc, unidade='m2', quantidade=Decimal(str(qtd)),
                # dimensionais: a revisão tem de copiá-los junto (Task #36)
                tipo_medicao_override='area' if i == 1 else None,
                dim_largura=Decimal('3.5') if i == 1 else None,
                dim_comprimento=Decimal('8.0') if i == 1 else None,
            ))
        db.session.commit()
        yield {'admin_id': admin.id, 'orcamento_id': orc.id}
        db.session.rollback()


def test_revisar_grava_a_cadeia_e_a_linhagem_dos_itens(ambiente):
    """A primeira revisão: versão 2, elo para a anterior, raiz para si mesma
    (a v1 é a raiz), e TODO item carregando de qual item ele veio."""
    from services.orcamento_versao import criar_revisao

    with app.app_context():
        raiz = db.session.get(Orcamento, ambiente['orcamento_id'])
        rev = criar_revisao(raiz, ambiente['admin_id'],
                            motivo='cliente pediu telha sanduíche')
        db.session.commit()

        assert rev.id != raiz.id, 'a revisão é um orçamento novo, não o mesmo'
        assert rev.versao == 2, f'revisão nasceu com versao={rev.versao}'
        assert rev.revisao_de_id == raiz.id, 'elo para a revisão anterior'
        assert rev.origem_id == raiz.id, (
            'origem_id aponta para a RAIZ da cadeia — para a rev.2 a raiz é a '
            'própria v1')
        assert rev.motivo_revisao == 'cliente pediu telha sanduíche'
        assert rev.status == 'rascunho'
        assert '(cópia)' not in rev.titulo, (
            'o título de revisão não é mais "(cópia)" — é "(rev. N)"')
        assert 'rev. 2' in rev.titulo, f'título ficou {rev.titulo!r}'

        # A v1 permanece intacta: revisar não mexe no original.
        assert raiz.versao == 1
        assert raiz.origem_id is None and raiz.revisao_de_id is None

        itens_raiz = {i.descricao: i for i in raiz.itens}
        itens_rev = {i.descricao: i for i in rev.itens}
        assert set(itens_rev) == set(itens_raiz), (
            f'a revisão copiou {sorted(itens_rev)}')
        for desc, item in itens_rev.items():
            assert item.item_origem_id == itens_raiz[desc].id, (
                f'item {desc!r} sem linhagem — item_origem_id vazio')

        # Os dimensionais viajam junto (Task #36), senão a revisão perde a
        # medição por área e o preço muda sem ninguém pedir.
        est = itens_rev['Estrutura metálica']
        assert est.tipo_medicao_override == 'area'
        assert est.dim_largura == Decimal('3.5000')
        assert est.dim_comprimento == Decimal('8.0000')


def test_cadeia_de_tres_revisoes_converge_para_a_mesma_raiz(ambiente):
    """v1 → v2 → v3: o elo anda de um em um, a raiz não se move.

    É o que permite listar "todas as revisões deste orçamento" com um
    `filter_by(origem_id=raiz.id)`, sem subir a corrente.
    """
    from services.orcamento_versao import criar_revisao

    with app.app_context():
        v1 = db.session.get(Orcamento, ambiente['orcamento_id'])
        v2 = criar_revisao(v1, ambiente['admin_id'], motivo='r2')
        db.session.commit()
        v3 = criar_revisao(v2, ambiente['admin_id'], motivo='r3')
        db.session.commit()

        assert (v2.versao, v3.versao) == (2, 3), (
            f'versões saíram {v2.versao} e {v3.versao} — a numeração conta a '
            'cadeia, não os filhos diretos')
        assert v3.revisao_de_id == v2.id, 'o elo aponta para a anterior'
        assert v3.origem_id == v1.id, 'a raiz não se move ao longo da cadeia'
        assert v2.origem_id == v1.id

        # A pergunta que a cadeia existe para responder.
        cadeia = Orcamento.query.filter_by(
            origem_id=v1.id, admin_id=ambiente['admin_id']).all()
        assert {o.id for o in cadeia} == {v2.id, v3.id}, (
            'filter_by(origem_id=raiz) tem de devolver a cadeia inteira')

        # Linhagem do item atravessa as três: o item da v3 aponta para o da
        # v2, que aponta para o da v1 — elo a elo, como o orçamento.
        it_v1 = {i.descricao: i for i in v1.itens}
        it_v2 = {i.descricao: i for i in v2.itens}
        it_v3 = {i.descricao: i for i in v3.itens}
        for desc in it_v1:
            assert it_v2[desc].item_origem_id == it_v1[desc].id
            assert it_v3[desc].item_origem_id == it_v2[desc].id


def test_revisar_nao_reaproveita_numero_do_orcamento(ambiente):
    """Cada revisão é um documento com número próprio.

    O `numero` é o identificador que o cliente vê; duas revisões com o mesmo
    número tornariam impossível dizer qual foi enviada.
    """
    from services.orcamento_versao import criar_revisao

    with app.app_context():
        v1 = db.session.get(Orcamento, ambiente['orcamento_id'])
        numero_v1 = v1.numero
        v2 = criar_revisao(v1, ambiente['admin_id'], motivo='r2')
        db.session.commit()
        assert v2.numero != numero_v1, 'revisão reusou o número do original'
