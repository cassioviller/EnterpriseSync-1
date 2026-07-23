"""Filtro de Obra em FinanceiroService.calcular_fluxo_caixa (Passo 1 do redesenho
do Fluxo de Caixa — spec 2026-06-11, decisões Q5/Q6/Q8).

Reescrito em 23/07: a versão original era read-only sobre o lote importado do
tenant 1 (obra 25) e SKIPAVA quando o dado não existia — verde falso em banco
recém-criado, exatamente o que a queda do Postgres de 22/07 produziu. Agora
cada teste semeia o próprio cenário num tenant descartável. As asserções
continuam RELACIONAIS: o esperado é recalculado por query direta com o mesmo
filtro do service, nunca uma constante.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

DI = date(2026, 1, 1)
DF = date(2026, 6, 5)


@pytest.fixture(scope="module")
def cenario():
    """Tenant descartável com duas obras e lançamentos nos dois lados do
    filtro — sem a obra B não dá para provar que o filtro RESTRINGE."""
    from main import app
    from app import db
    from models import (Cliente, ContaReceber, FluxoCaixa, GestaoCustoFilho,
                        GestaoCustoPai, Obra, TipoUsuario, Usuario)

    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = Usuario(
            username=f'fxo_{suf}', email=f'fxo_{suf}@test.local',
            nome=f'Admin Fluxo {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()

        def _obra(nome):
            o = Obra(nome=f'{nome} {suf}', codigo=f'X{uuid.uuid4().hex[:6].upper()}',
                     data_inicio=date(2026, 1, 1), admin_id=admin.id,
                     cliente_id=cliente.id, ativo=True)
            db.session.add(o)
            db.session.commit()
            return o

        obra_a, obra_b = _obra('Obra A'), _obra('Obra B')

        # Entradas previstas: ContaReceber pendente nas duas obras
        for obra, valor in ((obra_a, '1000.00'), (obra_a, '500.00'), (obra_b, '700.00')):
            db.session.add(ContaReceber(
                cliente_nome=cliente.nome, obra_id=obra.id,
                descricao=f'CR {obra.nome}', valor_original=Decimal(valor),
                saldo=Decimal(valor), data_emissao=DI, data_vencimento=date(2026, 3, 10),
                status='PENDENTE', admin_id=admin.id,
            ))

        # Saídas realizadas: FluxoCaixa SAIDA de gestão de custo nas duas obras
        for obra, valor in ((obra_a, '300.00'), (obra_a, '200.00'), (obra_b, '400.00')):
            db.session.add(FluxoCaixa(
                admin_id=admin.id, data_movimento=date(2026, 2, 15),
                tipo_movimento='SAIDA', categoria='custo_obra',
                valor=Decimal(valor), descricao=f'Pagamento {obra.nome}',
                obra_id=obra.id, referencia_tabela='gestao_custo_pai',
                referencia_id=999,
            ))

        # Saídas previstas: um Pai em aberto com filho na obra A (Q8: o pai
        # não tem obra — o filtro entra pelos filhos)
        pai = GestaoCustoPai(
            tipo_categoria='MATERIAL', entidade_nome=f'Fornecedor {suf}',
            valor_total=Decimal('900.00'), status='PENDENTE',
            data_vencimento=date(2026, 4, 20), admin_id=admin.id,
        )
        db.session.add(pai)
        db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, data_referencia=date(2026, 4, 20),
            descricao='Material obra A', valor=Decimal('900.00'),
            obra_id=obra_a.id, admin_id=admin.id,
        ))
        db.session.commit()
        return {'admin_id': admin.id, 'obra_a': obra_a.id, 'obra_b': obra_b.id}


@pytest.fixture(scope="module")
def app_ctx():
    from main import app
    with app.app_context():
        yield


pytestmark = pytest.mark.integration


def test_filtro_obra_restringe_entradas_previstas(app_ctx, cenario):
    """Com obra_id, entradas_previstas == soma das ContaReceber pendentes da obra."""
    from financeiro_service import FinanceiroService
    from models import ContaReceber

    admin, obra = cenario['admin_id'], cenario['obra_a']
    contas = ContaReceber.query.filter(
        ContaReceber.admin_id == admin,
        ContaReceber.data_vencimento >= DI,
        ContaReceber.data_vencimento <= DF,
        ContaReceber.status.in_(["PENDENTE", "PARCIAL"]),
        ContaReceber.obra_id == obra,
    ).all()
    esperado = float(sum(
        (c.saldo if c.saldo is not None else (c.valor_original or 0)) for c in contas
    ))
    assert esperado > 0, "o cenário semeado tem de ter ContaReceber pendente"

    res = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF, obra_id=obra)
    res_geral = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF)
    assert res["entradas_previstas"] == pytest.approx(esperado, abs=0.01)
    # a obra B garante que o filtro de fato restringe
    assert res["entradas_previstas"] < res_geral["entradas_previstas"]


def test_filtro_obra_restringe_saidas_realizadas(app_ctx, cenario):
    """Com obra_id, as saídas realizadas (FluxoCaixa) batem com a query direta da obra
    e ficam menores que o total sem filtro."""
    from financeiro_service import FinanceiroService
    from models import FluxoCaixa

    admin, obra = cenario['admin_id'], cenario['obra_a']
    fc = FluxoCaixa.query.filter(
        FluxoCaixa.admin_id == admin,
        FluxoCaixa.tipo_movimento == "SAIDA",
        FluxoCaixa.data_movimento >= DI,
        FluxoCaixa.data_movimento <= DF,
        FluxoCaixa.obra_id == obra,
        FluxoCaixa.referencia_tabela == "gestao_custo_pai",
    ).all()
    esperado = float(sum(float(f.valor) for f in fc))
    assert esperado > 0, "o cenário semeado tem de ter FluxoCaixa SAIDA da obra"

    res_obra = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF, obra_id=obra)
    res_geral = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF)

    def saidas_realizadas(res):
        return float(sum(
            d["valor"] for d in res["detalhes"]
            if d["tipo"] == "SAIDA" and d.get("realizado")
        ))

    assert saidas_realizadas(res_obra) == pytest.approx(esperado, abs=0.01)
    assert saidas_realizadas(res_obra) < saidas_realizadas(res_geral)


def test_filtro_obra_inexistente_zera_saidas_previstas(app_ctx, cenario):
    """Filtrar por uma obra sem nada zera as saídas previstas (GestaoCustoPai via
    filhos — Q8) e devolve detalhes vazios; prova que um 'pai' sem filho na obra
    não vaza."""
    from financeiro_service import FinanceiroService

    admin = cenario['admin_id']
    OBRA_VAZIA = 999_999_999

    geral = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF)
    assert geral["saidas_previstas"] > 0, "o cenário semeado tem de ter Pai em aberto"

    res = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF, obra_id=OBRA_VAZIA)
    assert res["saidas_previstas"] == pytest.approx(0.0, abs=0.01)
    assert res["detalhes"] == []
