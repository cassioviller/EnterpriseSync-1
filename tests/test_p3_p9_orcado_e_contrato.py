"""p3 e p9 — a fonte única do custo orçado, e o escritor único do contrato.

**p3.** `ObraServicoCusto.valor_orcado` guarda VENDA, não custo (o listener
da Task #82 herda `valor_comercial`). A regra certa — "linha de custo vence
agregado" — existia dentro de `resumo_custos_obra` e virou
`services/custo_orcado.py`. O teste que importa é o de convergência: resumo e
painel físico-financeiro devolvendo o MESMO número para a mesma obra.

**p9.** Cinco lugares escreviam `Obra.valor_contrato`. O teste é de forma —
varre o código e falha se um sexto aparecer fora de
`services/contrato_obra.py`. É o tipo de regressão que volta por conveniência
("só aqui"), e o inventário da Fase 6 já tinha esquecido um.
"""
import os
import re
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import ObraServicoCusto, ObraServicoCustoItem
from helpers_tenant import dois_tenants
from services.custo_orcado import custo_orcado_da_obra, custo_orcado_por_servico

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p3-p9'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('orc')
    return a


def _servico_de_custo(t, valor_orcado, linhas=()):
    """Um ObraServicoCusto com `valor_orcado` (= venda, na cadeia comercial)
    e, opcionalmente, linhas de custo — que são a verdade do custo."""
    osc = ObraServicoCusto(obra_id=t.obra_id, admin_id=t.admin_id,
                           nome=f'Serviço {t.marca}',
                           valor_orcado=Decimal(str(valor_orcado)),
                           realizado_material=0, realizado_mao_obra=0,
                           realizado_outros=0)
    db.session.add(osc)
    db.session.flush()
    for valor in linhas:
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=t.admin_id,
            descricao='linha', valor=Decimal(str(valor))))
    db.session.commit()
    return osc


# ---------------------------------------------------------------------------
# p3
# ---------------------------------------------------------------------------

def test_linha_de_custo_vence_o_agregado_de_venda():
    """O caso que motivou o pacote: agregado com preço de venda (10.000) e
    linhas com o custo real (6.000)."""
    t = _tenant()
    _servico_de_custo(t, 10000, linhas=(4000, 2000))

    assert custo_orcado_da_obra(t.obra_id, t.admin_id) == 6000.0


def test_sem_linhas_cai_para_o_agregado():
    """Fluxo manual/legado: sem linha cadastrada, o agregado é o único número
    que existe — e ali ele costuma ser custo de verdade."""
    t = _tenant()
    _servico_de_custo(t, 7500)

    assert custo_orcado_da_obra(t.obra_id, t.admin_id) == 7500.0


def test_obra_sem_custo_cadastrado_devolve_zero():
    t = _tenant()
    assert custo_orcado_da_obra(t.obra_id, t.admin_id) == 0.0


def test_o_fallback_e_por_servico_nao_pela_obra_inteira():
    """Um serviço com linhas não pode fazer o irmão sem linhas valer zero —
    e nem o contrário."""
    t = _tenant()
    com_linhas = _servico_de_custo(t, 10000, linhas=(6000,))
    sem_linhas = _servico_de_custo(t, 2500)

    mapa = custo_orcado_por_servico(t.obra_id, t.admin_id)
    assert mapa[com_linhas.id] == 6000.0
    assert mapa[sem_linhas.id] == 2500.0
    assert custo_orcado_da_obra(t.obra_id, t.admin_id) == 6000.0


def test_resumo_e_painel_convergem_no_mesmo_orcado():
    """O critério de pronto do p3: dois consumidores, um número."""
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    from services.resumo_custos_obra import calcular_resumo_obra

    t = _tenant()
    _servico_de_custo(t, 10000, linhas=(6000,))

    resumo = calcular_resumo_obra(t.obra_id, admin_id=t.admin_id)
    painel = montar_fisico_financeiro(t.obra_id, t.admin_id)

    orcado_resumo = float(resumo['indicadores'].get('valor_custo_orcado') or 0)
    orcado_painel = sum(float(e.get('orcado') or 0)
                        for e in painel.get('etapas', []))
    assert orcado_resumo == pytest.approx(orcado_painel), (
        f'resumo diz {orcado_resumo} e painel diz {orcado_painel} para a '
        f'mesma obra')


def test_o_orcado_nao_atravessa_tenants():
    a, b = dois_tenants('orc2')
    osc = ObraServicoCusto(obra_id=b.obra_id, admin_id=b.admin_id,
                           nome='Do outro', valor_orcado=Decimal('9999'),
                           realizado_material=0, realizado_mao_obra=0,
                           realizado_outros=0)
    db.session.add(osc)
    db.session.commit()

    assert custo_orcado_da_obra(a.obra_id, a.admin_id) == 0.0


# ---------------------------------------------------------------------------
# p9
# ---------------------------------------------------------------------------

ARQUIVOS_QUE_ESCREVIAM = (
    'event_manager.py',
    'views/obras.py',
    'services/importacao_fisico_financeiro.py',
)


def test_ninguem_escreve_valor_contrato_fora_do_ponto_unico():
    """O inventário da Fase 6 já tinha esquecido um escritor. Este teste é
    para o sexto não passar despercebido."""
    padrao = re.compile(r'^\s*\w+\.valor_contrato\s*=(?!=)', re.MULTILINE)
    for arquivo in ARQUIVOS_QUE_ESCREVIAM:
        with open(arquivo, encoding='utf-8') as fh:
            achados = padrao.findall(fh.read())
        assert not achados, (
            f'{arquivo} voltou a escrever valor_contrato direto '
            f'({len(achados)}x) — use services/contrato_obra.py')


def test_o_construtor_de_obra_tambem_nao_escreve():
    """`Obra(valor_contrato=…)` no construtor é escrita como qualquer outra, e
    era assim que criar-obra escapava do ponto único."""
    for arquivo in ('views/obras.py', 'event_manager.py'):
        with open(arquivo, encoding='utf-8') as fh:
            texto = fh.read()
        assert 'valor_contrato=valor_total' not in texto
        assert 'valor_contrato=valor_contrato' not in texto


def test_o_ponto_unico_grava_e_devolve():
    from services.contrato_obra import ORIGEM_EDICAO, definir_valor_contrato

    t = _tenant()
    from models import Obra
    obra = db.session.get(Obra, t.obra_id)

    assert definir_valor_contrato(obra, 250000, origem=ORIGEM_EDICAO,
                                  motivo='teste') == 250000.0
    db.session.commit()
    db.session.expire_all()
    assert float(db.session.get(Obra, t.obra_id).valor_contrato) == 250000.0


def test_origem_desconhecida_nao_bloqueia_mas_avisa(caplog):
    """Derrubar um cadastro por causa de rótulo de log seria pior que o
    problema — mas o quinto escritor precisa aparecer em algum lugar."""
    from services.contrato_obra import definir_valor_contrato

    t = _tenant()
    from models import Obra
    obra = db.session.get(Obra, t.obra_id)

    with caplog.at_level('WARNING'):
        definir_valor_contrato(obra, 1000, origem='origem_inventada')
    assert any('origem desconhecida' in r.getMessage()
               for r in caplog.records)
