"""Migrations do porte da Espinha Financeira (PR #6) — as colunas que a
linhagem velha tinha e que nunca chegaram ao repo recomeçado em 22/07.

🔬 O repo foi recomeçado em 22/07 e as migrations 193/194/195 da linhagem
antiga ficaram do outro lado da fratura. Sem elas o importador de obra quebra
em `AttributeError` na materialização multi-atividade.

Numeração: o plano de 24/08 escrevia 317/318/319, mas as 317 e 318 foram
gastas em 01/09 (A09 e A24). Renumeradas para **319** (`peso_medicao`),
**320** (`origem`) e **321** (`verba`/`lucro`/`pai`). O máximo real foi
conferido no momento de escrever, como a Global Constraint manda.

⚠️ As funções de migration são importadas DENTRO de cada teste, não no topo:
no RED elas ainda não existem, e um import no topo quebraria a coleção do
arquivo inteiro em vez de dar o vermelho limpo que o TDD pede.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from sqlalchemy import text as sa_text  # noqa: E402

pytestmark = pytest.mark.integration


def _coluna_existe(tabela, coluna):
    """A coluna existe no banco de verdade — não no modelo."""
    with app.app_context():
        row = db.session.execute(sa_text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ), {'t': tabela, 'c': coluna}).fetchone()
    return row


# ---------------------------------------------------------------------------
# Migration 319 — cronograma_template_item.peso_medicao (repõe a 193)
# ---------------------------------------------------------------------------

def test_template_item_tem_peso_medicao_e_nasce_nulo():
    from models import CronogramaTemplateItem
    with app.app_context():
        assert hasattr(CronogramaTemplateItem, 'peso_medicao'), (
            'sem esta coluna o importador quebra em AttributeError na '
            'materialização multi-atividade')
        col = CronogramaTemplateItem.__table__.columns['peso_medicao']
        assert col.nullable, (
            'peso_medicao é nullable de propósito: NULL significa "template '
            'sem peso definido" e o importador cai no fallback 1:1. Um '
            'default numérico fingiria um peso que ninguém definiu')


def test_migration_319_e_idempotente_e_cria_a_coluna():
    from migrations import _migration_319_template_item_peso_medicao
    with app.app_context():
        assert _migration_319_template_item_peso_medicao() is True, \
            'a migration 319 falhou na primeira execução'
        assert _migration_319_template_item_peso_medicao() is True, \
            'a migration 319 não é idempotente: a segunda execução falhou'

    row = _coluna_existe('cronograma_template_item', 'peso_medicao')
    assert row is not None, 'a coluna não existe no banco depois da migration'
    assert row[1] == 'YES', f'peso_medicao devia ser nullable, veio {row[1]}'
