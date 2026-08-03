"""p1 Step F — a reconciliação do histórico já duplicado.

Decisão do Cássio (03/08): *"consertar para frente primeiro, reconciliar
depois."* Os Steps C-E impedem a duplicação nova; este script mede e remove a
antiga — e é operação assistida, não migração de boot.

O que estes testes garantem, na ordem do risco:

  1. **dry-run não escreve nada** — é o modo padrão, e é onde o operador lê os
     números antes de decidir;
  2. **o lançamento do PONTO sobrevive**, o do RDO sai (o ponto é o fato
     medido);
  3. **`RDOMaoObra` nunca é apagado** — a rota `excluir_filho` apaga a origem
     junto, e aqui isso seria destruir registro de campo;
  4. **PAGO/RECUSADO não é tocado** — custo pago tem contrapartida no
     financeiro.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import GestaoCustoFilho, GestaoCustoPai, RDO, RDOMaoObra
from helpers_tenant import dois_tenants
from scripts.reconciliar_custos_mao_obra import main, pares_duplicados

pytestmark = pytest.mark.integration

DATA = date(2026, 5, 20)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p1-reconciliacao'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('rec', DATA)
    return a


def _lancamento(t, origem, status='PENDENTE', valor='150.00'):
    """Um par pai+filho de mão de obra, na origem pedida."""
    pai = GestaoCustoPai(tipo_categoria='SALARIO', entidade_nome=f'F {t.marca}',
                         entidade_id=t.funcionario_id, admin_id=t.admin_id,
                         obra_id=t.obra_id, status=status)
    db.session.add(pai)
    db.session.flush()
    filho = GestaoCustoFilho(
        pai_id=pai.id, admin_id=t.admin_id, obra_id=t.obra_id,
        data_referencia=DATA, descricao=f'Diária {origem}',
        valor=Decimal(valor), origem_tabela=origem, origem_id=0)
    db.session.add(filho)
    db.session.commit()
    return pai.id, filho.id


def _rdo_mao_obra(t):
    rdo = RDO(numero_rdo=f'RDO-{uuid4().hex[:8]}', obra_id=t.obra_id,
              admin_id=t.admin_id, data_relatorio=DATA,
              criado_por_id=t.admin_id)
    db.session.add(rdo)
    db.session.flush()
    mo = RDOMaoObra(rdo_id=rdo.id, funcionario_id=t.funcionario_id,
                    admin_id=t.admin_id, horas_trabalhadas=8.0,
                    funcao_exercida='Servente')
    db.session.add(mo)
    db.session.commit()
    return mo.id


def test_dry_run_e_o_padrao_e_nao_escreve_nada():
    t = _tenant()
    _, filho_ponto = _lancamento(t, 'registro_ponto')
    _, filho_rdo = _lancamento(t, 'rdo_mao_obra')

    assert main(['--admin-id', str(t.admin_id)]) == 0

    db.session.expire_all()
    assert db.session.get(GestaoCustoFilho, filho_ponto) is not None
    assert db.session.get(GestaoCustoFilho, filho_rdo) is not None, (
        'o dry-run apagou lançamento — é o modo em que o operador ainda está '
        'lendo os números')


def test_detecta_o_par_duplicado():
    t = _tenant()
    _lancamento(t, 'registro_ponto')
    _lancamento(t, 'rdo_mao_obra')

    (achado,) = pares_duplicados(t.admin_id)
    assert achado['funcionario_id'] == t.funcionario_id
    assert achado['data'] == DATA
    assert achado['valor_ponto'] == 150.0 and achado['valor_rdo'] == 150.0


def test_dia_com_uma_origem_so_nao_e_duplicado():
    """Metade dos dias tem só ponto (ou só RDO). Eles não são o problema."""
    t = _tenant()
    _lancamento(t, 'registro_ponto')
    assert pares_duplicados(t.admin_id) == []


def test_aplicar_remove_o_do_rdo_e_preserva_o_do_ponto():
    t = _tenant()
    _, filho_ponto = _lancamento(t, 'registro_ponto')
    _, filho_rdo = _lancamento(t, 'rdo_mao_obra')

    assert main(['--admin-id', str(t.admin_id), '--aplicar']) == 0

    db.session.expire_all()
    assert db.session.get(GestaoCustoFilho, filho_ponto) is not None, (
        'o ponto é o fato medido e tinha de sobreviver')
    assert db.session.get(GestaoCustoFilho, filho_rdo) is None


def test_o_apontamento_de_campo_nunca_e_apagado():
    """`excluir_filho` apaga a origem junto — aqui isso seria destruir o
    registro do que a obra viveu."""
    t = _tenant()
    mo_id = _rdo_mao_obra(t)
    _lancamento(t, 'registro_ponto')
    _lancamento(t, 'rdo_mao_obra')

    main(['--admin-id', str(t.admin_id), '--aplicar'])

    db.session.expire_all()
    assert db.session.get(RDOMaoObra, mo_id) is not None


def test_lancamento_pago_nao_e_tocado():
    """Custo pago tem contrapartida no financeiro — sumir com ele em silêncio
    cria um segundo problema no lugar do primeiro."""
    t = _tenant()
    _lancamento(t, 'registro_ponto')
    _, filho_rdo = _lancamento(t, 'rdo_mao_obra', status='PAGO')

    main(['--admin-id', str(t.admin_id), '--aplicar'])

    db.session.expire_all()
    assert db.session.get(GestaoCustoFilho, filho_rdo) is not None


def test_nao_atravessa_tenant():
    a, b = dois_tenants('rec2', DATA)
    for t in (a, b):
        _lancamento(t, 'registro_ponto')
        _lancamento(t, 'rdo_mao_obra')

    filhos_b = {f.id for f in GestaoCustoFilho.query.filter_by(
        admin_id=b.admin_id, data_referencia=DATA).all()}

    main(['--admin-id', str(a.admin_id), '--aplicar'])

    db.session.expire_all()
    restantes_b = {f.id for f in GestaoCustoFilho.query.filter_by(
        admin_id=b.admin_id, data_referencia=DATA).all()}
    assert restantes_b == filhos_b, 'a reconciliação de A tocou no tenant B'
