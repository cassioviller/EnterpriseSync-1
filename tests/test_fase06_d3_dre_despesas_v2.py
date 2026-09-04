"""Fase 0.6 / D3 — nenhuma despesa do motor V2 aparecia no DRE.

`calcular_dre_mensal` (`contabilidade_utils.py:504`) somava as despesas
operacionais por prefixo fixo: `5.1.01`, `5.1.02`, `5.1.04`, `5.1.05`,
`5.1.06` (`:596-600`). O motor contábil V2 (`MAPEAMENTO_CONTABIL`, `:1449`)
debita em `6.1.01.001`, `6.1.01.002` e `6.1.02.002`. **Interseção vazia**:
alimentação, transporte e folha eram lançados e não entravam no resultado.
O DRE mostrava a empresa mais lucrativa do que ela é.

Medido no banco de desenvolvimento em 2026-07-21: R$ 840,00 em `6.1.01.002`
(alimentação) e R$ 2.400,00 em `6.1.02.002` (transporte) lançados e
invisíveis.

O sistema tem QUATRO planos de contas concorrentes, e dois deles dão
significados diferentes ao mesmo código:

| Origem                                     | 5.1.01        | 5.1.02        | 6.1.02                |
|--------------------------------------------|---------------|---------------|-----------------------|
| `financeiro_seeds.py:70`                   | MÃO DE OBRA   | MATERIAIS     | —                     |
| `contabilidade_utils.criar_plano_contas...`| Materiais Dir.| Mão de Obra D.| DESPESAS ADMINISTRAT. |
| `_V2_CONTAS_SEED` (`:1459`)                | —             | —             | DESPESAS GERAIS       |

Havia dois lançadores distintos de "Salários": `contabilidade_utils.py:229`
gravava em `6.1.01.001` e `event_manager.py` gravava em `5.1.01.001` — a
citação original apontava `event_manager.py:1114`; 🔬 04/09 o sítio estava em
`:1488`, e âncora por número envelhece em um mês.

✅ **A Fase 8 / Task 4 acabou com a coexistência.** A migration 324 move toda
partida `5.x` para o canônico por (assinatura, código) e desativa as `5.x`
que ficam sem partida; `event_manager` passou a gravar a folha em
`6.1.01.001`, o mesmo destino que o `DEPARA_5X` dá para `5.1.01.001`. Por
isso este arquivo **não cria mais conta `5.x`**: criá-las aqui era o que
enchia o banco de dev de resíduo de suíte (🔬 04/09: 211 tenants com `5.x`,
todos `d3_*@test.local`) e o que fazia a própria migration parar.

O que esta correção garante continua sendo mais estreito e verificável:
**nenhum débito em conta de resultado pode ficar de fora do DRE.** Se um
código não casar com nenhuma linha declarada, ele cai em "outras despesas" —
nunca desaparece.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration

ANO, MES = 2026, 3
DATA = date(ANO, MES, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase06-d3'
    yield


@pytest.fixture
def admin():
    """Tenant novo — DRE começa zerado, então todo delta é do teste."""
    with app.app_context():
        s = uuid.uuid4().hex[:8]
        u = Usuario(
            username=f'd3_{s}', email=f'd3_{s}@test.local', nome=f'Admin {s}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(u)
        db.session.commit()
        yield u.id


def _lancar(admin_id, tipo_operacao, valor):
    from contabilidade_utils import gerar_lancamento_contabil_automatico
    ok = gerar_lancamento_contabil_automatico(
        admin_id=admin_id, tipo_operacao=tipo_operacao, valor=valor,
        data=DATA, descricao=f'teste D3 {tipo_operacao}',
    )
    db.session.commit()
    assert ok, f'lançamento {tipo_operacao} não foi criado'


def _dre(admin_id):
    from contabilidade_utils import calcular_dre_mensal
    dre = calcular_dre_mensal(admin_id=admin_id, ano=ANO, mes=MES)
    assert dre is not None, 'calcular_dre_mensal devolveu None'
    return dre


def _garantir_conta(admin_id, codigo, nome, pai=None):
    """Cria a conta para ESTE tenant, com a cadeia de pais, se não existir.

    Desde a migration 218 (D4) a PK de `plano_contas` é `(admin_id, codigo)` e
    `partida_contabil` tem FK composta: uma partida do tenant A não pode mais
    apontar para a conta do tenant B. Antes disso, este helper podia criar a
    conta em qualquer tenant que o teste enxergaria assim mesmo.
    """
    from sqlalchemy import text as sa_text
    existe = db.session.execute(
        sa_text('SELECT 1 FROM plano_contas WHERE codigo = :c AND admin_id = :a'),
        {'c': codigo, 'a': admin_id},
    ).scalar()
    if existe:
        return
    if pai:
        _garantir_conta(admin_id, pai, f'{nome} (agrupador)',
                        pai='.'.join(pai.split('.')[:-1]) or None)
    db.session.execute(sa_text("""
        INSERT INTO plano_contas
            (codigo, nome, tipo_conta, natureza, nivel, conta_pai_codigo,
             aceita_lancamento, ativo, admin_id)
        VALUES (:c, :n, 'DESPESA', 'DEVEDORA', :nivel, :pai, true, true, :a)
    """), {'c': codigo, 'n': nome[:100], 'nivel': len(codigo.split('.')),
           'pai': pai, 'a': admin_id})
    db.session.commit()


# ---------------------------------------------------------------------------
# Cada operação do motor V2 tem que chegar ao resultado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('tipo_operacao,valor', [
    ('despesa_alimentacao', 840.00),
    ('despesa_transporte', 2400.00),
    ('folha_pagamento', 15000.00),
])
def test_despesa_do_motor_v2_entra_no_dre(admin, tipo_operacao, valor):
    with app.app_context():
        antes = _dre(admin)['despesas_operacionais']['total']

        _lancar(admin, tipo_operacao, valor)

        depois = _dre(admin)['despesas_operacionais']['total']
        assert depois == pytest.approx(antes + valor), (
            f'{tipo_operacao}: lançado R$ {valor:.2f} e o DRE não mudou'
        )


def test_despesa_do_motor_v2_reduz_o_lucro_liquido(admin):
    """A consequência que importa: o DRE mostrava a empresa mais lucrativa."""
    with app.app_context():
        antes = _dre(admin)['lucro_liquido']

        _lancar(admin, 'despesa_alimentacao', 1000.00)
        _lancar(admin, 'despesa_transporte', 500.00)

        depois = _dre(admin)['lucro_liquido']
        assert depois == pytest.approx(antes - 1500.00)


def test_salario_tem_UMA_conta_so_e_o_dre_a_ve_uma_vez(admin):
    """Fase 8 / Task 4 — era `test_as_duas_contas_de_salario_...`.

    O teste antigo provava a COEXISTÊNCIA de `6.1.01.001` (contabilidade_utils)
    e `5.1.01.001` (event_manager), criando a segunda a cada rodada. Era a
    prova viva do defeito que a Fase 8 removeu — e a fábrica do resíduo `5.x`
    do banco de dev. Agora há UM lançador só, e o DRE tem de vê-lo uma vez.
    """
    from contabilidade_utils import criar_lancamento_automatico
    from decimal import Decimal

    from contabilidade_utils import seed_plano_contas_if_needed

    with app.app_context():
        seed_plano_contas_if_needed(admin)
        db.session.commit()
        antes = _dre(admin)['despesas_operacionais']['total']

        for _ in range(2):
            criar_lancamento_automatico(
                data=DATA, historico='salário via 6.1.01.001',
                valor=Decimal('1000.00'), origem='TESTE_D3', origem_id=None,
                admin_id=admin,
                partidas=[
                    {'tipo': 'DEBITO', 'conta': '6.1.01.001', 'valor': Decimal('1000.00')},
                    {'tipo': 'CREDITO', 'conta': '2.1.02.001', 'valor': Decimal('1000.00')},
                ],
            )
        db.session.commit()

        depois = _dre(admin)['despesas_operacionais']['total']
        assert depois == pytest.approx(antes + 2000.00), (
            'a conta de salário tem que somar exatamente uma vez por lançamento'
        )


# ---------------------------------------------------------------------------
# A invariante: nada de resultado pode ficar fora
# ---------------------------------------------------------------------------

def test_conta_de_despesa_desconhecida_cai_em_outras_e_nao_some(admin):
    """A garantia estrutural — a que impede o D3 de renascer.

    Um código de despesa que nenhuma linha do DRE declara não pode
    simplesmente não aparecer. Cai em "outras despesas", visível.
    """
    from contabilidade_utils import criar_lancamento_automatico
    from decimal import Decimal

    with app.app_context():
        _garantir_conta(admin, '6.9.99.001', 'Despesa nunca vista', pai='6.9.99')
        _garantir_conta(admin, '1.1.01.002', 'Bancos Conta Movimento')
        antes = _dre(admin)['despesas_operacionais']

        criar_lancamento_automatico(
            data=DATA, historico='despesa de conta nunca vista',
            valor=Decimal('777.00'), origem='TESTE_D3', origem_id=None,
            admin_id=admin,
            partidas=[
                {'tipo': 'DEBITO', 'conta': '6.9.99.001', 'valor': Decimal('777.00')},
                {'tipo': 'CREDITO', 'conta': '1.1.01.002', 'valor': Decimal('777.00')},
            ],
        )
        db.session.commit()

        depois = _dre(admin)['despesas_operacionais']
        assert depois['outras'] == pytest.approx(antes['outras'] + 777.00)
        assert depois['total'] == pytest.approx(antes['total'] + 777.00)


def test_dre_fecha_com_o_total_de_debitos_de_resultado(admin):
    """Invariante de fechamento: soma das linhas == soma dos débitos.

    Nenhum débito em conta de resultado pode ficar sem casa: ou está numa
    linha declarada, ou cai no residual `outras`.

    ⚠️ Fase 8 / Task 4 — este teste criava `5.1.03.001` e `5.2.01.001` a cada
    rodada. 🔬 Era exatamente o resíduo (74 partidas em 37 tenants, 04/09) que
    fazia a migration 324 parar com "de-para incompleto". As linhas próprias
    de CMV, despesa financeira e provisão ficaram SEM BASE no canônico
    (`_DRE_LINHAS_SEM_BASE`), então o que sobra a provar aqui é o residual.
    """
    from contabilidade_utils import criar_lancamento_automatico
    from decimal import Decimal

    with app.app_context():
        for codigo, nome in (('6.1.02.009', 'Despesas Gerais Diversas'),
                             ('6.9.99.001', 'Despesa nunca vista'),
                             ('1.1.01.002', 'Bancos Conta Movimento')):
            pai = codigo.rsplit('.', 1)[0] if codigo != '1.1.01.002' else None
            _garantir_conta(admin, codigo, nome, pai=pai)
        _lancar(admin, 'despesa_alimentacao', 300.00)
        _lancar(admin, 'despesa_transporte', 200.00)
        for conta, valor in (('6.1.02.009', 100.00),   # despesa geral
                             ('6.9.99.001', 25.00)):   # desconhecida
            criar_lancamento_automatico(
                data=DATA, historico=f'debito {conta}',
                valor=Decimal(str(valor)), origem='TESTE_D3', origem_id=None,
                admin_id=admin,
                partidas=[
                    {'tipo': 'DEBITO', 'conta': conta, 'valor': Decimal(str(valor))},
                    {'tipo': 'CREDITO', 'conta': '1.1.01.002', 'valor': Decimal(str(valor))},
                ],
            )
        db.session.commit()

        dre = _dre(admin)
        contabilizado = (
            dre['despesas_operacionais']['total']
            + dre['cmv']
            + dre['resultado_financeiro']['despesas']
            + dre['provisao_ir_csll']['total']
        )
        assert contabilizado == pytest.approx(300 + 200 + 100 + 25), (
            'há débito em conta de resultado que o DRE não reporta em '
            'linha nenhuma'
        )
        assert 'cmv' in dre['sem_base'], (
            'a linha de CMV tem de sair declarada SEM BASE — o canônico não '
            'tem conta de CMV (Fase 8 / Task 4)'
        )
