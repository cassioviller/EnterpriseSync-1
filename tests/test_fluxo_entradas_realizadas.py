"""calcular_fluxo_caixa deve incluir entradas REALIZADAS vindas de contas a receber
baixadas (FluxoCaixa ENTRADA, referencia_tabela='conta_receber') — simétrico às
saídas realizadas de gestão de custo. Passo 2.5 do redesenho (achado na verificação
com dados reais: R$ 1,17M recebidos ficavam invisíveis).

Reescrito em 23/07: a versão original era read-only sobre o tenant 1 e SKIPAVA
sem o lote importado — verde falso em banco recém-criado. Agora semeia o próprio
cenário; a asserção continua relacional (esperado por query direta).
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

DI = date(2026, 1, 1)
DF = date(2026, 6, 5)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def cenario():
    from main import app
    from app import db
    from models import (Cliente, ContaReceber, FluxoCaixa, Obra,
                        TipoUsuario, Usuario)

    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = Usuario(
            username=f'fxe_{suf}', email=f'fxe_{suf}@test.local',
            nome=f'Admin Entradas {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(nome=f'Obra {suf}', codigo=f'E{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=admin.id,
                    cliente_id=cliente.id, ativo=True)
        db.session.add(obra)
        db.session.commit()

        # Duas baixas de conta a receber (o alvo do teste)
        for valor, dia in (('1170.00', date(2026, 2, 10)), ('830.00', date(2026, 3, 5))):
            db.session.add(FluxoCaixa(
                admin_id=admin.id, data_movimento=dia,
                tipo_movimento='ENTRADA', categoria='receita',
                valor=Decimal(valor), descricao='Recebimento de cliente',
                obra_id=obra.id, referencia_tabela='conta_receber',
                referencia_id=999,
            ))
        # Ruído que NÃO pode contaminar a soma de ENTRADAS realizadas:
        # uma SAÍDA realizada e uma conta a receber ainda PENDENTE (prevista).
        db.session.add(FluxoCaixa(
            admin_id=admin.id, data_movimento=date(2026, 2, 20),
            tipo_movimento='SAIDA', categoria='custo_obra',
            valor=Decimal('444.00'), descricao='Pagamento fornecedor',
            obra_id=obra.id, referencia_tabela='gestao_custo_pai',
            referencia_id=999,
        ))
        db.session.add(ContaReceber(
            cliente_nome=cliente.nome, obra_id=obra.id,
            descricao='CR pendente', valor_original=Decimal('555.00'),
            saldo=Decimal('555.00'), data_emissao=DI,
            data_vencimento=date(2026, 4, 1), status='PENDENTE',
            admin_id=admin.id,
        ))
        db.session.commit()
        return {'admin_id': admin.id}


@pytest.fixture(scope="module")
def app_ctx():
    from main import app
    with app.app_context():
        yield


def test_entradas_recebidas_aparecem_como_realizadas(app_ctx, cenario):
    from financeiro_service import FinanceiroService
    from models import FluxoCaixa

    admin = cenario['admin_id']
    fc = FluxoCaixa.query.filter(
        FluxoCaixa.admin_id == admin,
        FluxoCaixa.tipo_movimento == "ENTRADA",
        FluxoCaixa.data_movimento >= DI,
        FluxoCaixa.data_movimento <= DF,
        FluxoCaixa.referencia_tabela == "conta_receber",
    ).all()
    esperado = float(sum(float(f.valor) for f in fc))
    assert esperado > 0, "o cenário semeado tem de ter entradas recebidas"

    res = FinanceiroService.calcular_fluxo_caixa(admin, DI, DF)
    entradas_real = float(sum(
        d["valor"] for d in res["detalhes"]
        if d["tipo"] == "ENTRADA" and d.get("realizado")
    ))
    assert entradas_real == pytest.approx(esperado, abs=0.01)
