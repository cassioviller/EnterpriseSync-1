"""Bloco 3 — P0 (RED): tabela da fórmula de precificação BDI (padrão TCU)
e guarda-corpo (D3).

Contrato exercitado (a ser implementado em `services/pricing.py`):

    from services.pricing import precificar, Aliquotas
    r = precificar(custo_total: Decimal, aliquotas: Aliquotas) -> Precificacao

Fórmula (ADR 0001 / spec 2026-06-05):

    indiretos = custo_direto × (AC + S + R + G + DF)/100
    base      = custo_direto + indiretos
    preço     = base / (1 − (T + L)/100)
    tributos  = preço × T/100
    lucro     = preço × L/100            # L "por dentro" — corrige D2

Invariante: custo_direto + indiretos + tributos + lucro == preço.
Quando AC=S=R=G=DF=0, reduz a `custo / (1 − (T+L)/100)` — idêntico ao
comportamento atual (não-disrupção).

Estado esperado AGORA: VERMELHO — `services/pricing.py` ainda não existe.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from services.pricing import Aliquotas, precificar, resolver_aliquotas


def D(x):
    return Decimal(str(x))


def aliq(t=0, l=0, ac=0, s=0, r=0, g=0, df=0, tl_aviso=60, tl_bloqueio=90):
    """Constrói Aliquotas com percentuais (em %). Defaults de guarda-corpo
    iguais ao schema da empresa (aviso 60, bloqueio 90)."""
    return Aliquotas(
        t=D(t), l=D(l), ac=D(ac), s=D(s), r=D(r), g=D(g), df=D(df),
        tl_aviso=D(tl_aviso), tl_bloqueio=D(tl_bloqueio),
    )


# --------------------------------------------------------------------------
# Não-disrupção: BDI=0 reduz à fórmula atual `custo / (1 − T − L)`.
# --------------------------------------------------------------------------

def test_bdi_zero_reduz_ao_calculo_atual():
    custo = D(1000)
    a = aliq(t=15, l=5)  # T+L = 20%, sem componentes de BDI
    r = precificar(custo, a)

    esperado_atual = custo / (D(1) - (D(15) + D(5)) / D(100))  # = 1250
    assert r.preco == esperado_atual == D(1250)
    assert r.custo_direto == custo
    assert r.indiretos == D(0)
    assert r.status == "ok"


@pytest.mark.parametrize(
    "custo,t,l",
    [(1000, 10, 10), (2500, 22, 8), (777.77, 5, 12), (100000, 0, 0)],
)
def test_bdi_zero_identico_a_formula_legada(custo, t, l):
    a = aliq(t=t, l=l)
    r = precificar(D(custo), a)
    legado = D(custo) / (D(1) - (D(t) + D(l)) / D(100))
    assert r.preco == legado


# --------------------------------------------------------------------------
# Exemplo TCU conhecido (valores calculados à mão).
#   custo=1000; AC=20,S=1,R=1,G=1,DF=2 (ΣBDI=25); T=15,L=5
#   indiretos=250  base=1250  divisor=0.80  preço=1562.50
#   tributos=234.375  lucro=78.125
# --------------------------------------------------------------------------

def test_exemplo_tcu_conhecido():
    a = aliq(t=15, l=5, ac=20, s=1, r=1, g=1, df=2)
    r = precificar(D(1000), a)

    assert r.custo_direto == D(1000)
    assert r.indiretos == D(250)
    assert r.soma_bdi_pct == D(25)
    assert r.tl_pct == D(20)
    assert r.preco == D("1562.50")
    assert r.tributos == D("234.375")
    assert r.lucro == D("78.125")
    assert r.status == "ok"


def test_invariante_no_exemplo_tcu():
    a = aliq(t=15, l=5, ac=20, s=1, r=1, g=1, df=2)
    r = precificar(D(1000), a)
    assert r.custo_direto + r.indiretos + r.tributos + r.lucro == r.preco


@pytest.mark.parametrize(
    "custo,t,l,ac,s,r_,g,df",
    [
        (1000, 15, 5, 20, 1, 1, 1, 2),
        (2500, 22, 8, 10, 0.5, 1, 0.5, 3),
        (888.88, 5, 12, 4, 1, 2, 1, 1),
        (12345.67, 0, 0, 7, 0, 0, 0, 0),
    ],
)
def test_invariante_geral(custo, t, l, ac, s, r_, g, df):
    a = aliq(t=t, l=l, ac=ac, s=s, r=r_, g=g, df=df)
    res = precificar(D(custo), a)
    soma = res.custo_direto + res.indiretos + res.tributos + res.lucro
    # Tolerância de 1 centavo cobre arredondamento de divisão Decimal.
    assert abs(soma - res.preco) < D("0.01")


# --------------------------------------------------------------------------
# D2: lucro = L × preço (NÃO preço − custo, que embutia o imposto).
# --------------------------------------------------------------------------

def test_d2_lucro_e_l_vezes_preco():
    a = aliq(t=15, l=5, ac=20, s=1, r=1, g=1, df=2)
    r = precificar(D(1000), a)

    assert r.lucro == r.preco * D(5) / D(100)        # = 78.125
    # O cálculo legado errado seria preço − custo = 562.50.
    assert r.lucro != r.preco - r.custo_direto


# --------------------------------------------------------------------------
# D3: guarda-corpo — faixas ok / aviso / bloqueio.
# --------------------------------------------------------------------------

def test_d3_faixa_ok_default():
    r = precificar(D(1000), aliq(t=15, l=5))   # T+L=20 < 60
    assert r.status == "ok"
    assert not r.mensagem
    assert r.preco > 0


def test_d3_faixa_aviso_default():
    r = precificar(D(1000), aliq(t=40, l=25))  # T+L=65 ∈ [60,90)
    assert r.status == "aviso"
    assert r.mensagem            # mensagem de alerta para a UI
    assert r.preco > 0           # aviso calcula normalmente


def test_d3_faixa_bloqueio_default():
    r = precificar(D(1000), aliq(t=50, l=45))  # T+L=95 ≥ 90
    assert r.status == "bloqueio"
    assert r.preco == D(0)
    assert r.mensagem


def test_d3_limiares_de_borda():
    # tl == aviso → aviso; tl == bloqueio → bloqueio.
    assert precificar(D(1000), aliq(t=30, l=30)).status == "aviso"      # 60
    assert precificar(D(1000), aliq(t=45, l=45)).status == "bloqueio"   # 90


def test_d3_limiares_customizados():
    a_aviso = aliq(t=20, l=15, tl_aviso=30, tl_bloqueio=50)   # 35 ∈ [30,50)
    a_bloq = aliq(t=30, l=25, tl_aviso=30, tl_bloqueio=50)    # 55 ≥ 50
    assert precificar(D(1000), a_aviso).status == "aviso"
    bloq = precificar(D(1000), a_bloq)
    assert bloq.status == "bloqueio"
    assert bloq.preco == D(0)


# --------------------------------------------------------------------------
# Casos de borda.
# --------------------------------------------------------------------------

def test_custo_zero_nao_explode():
    r = precificar(D(0), aliq(t=15, l=5, ac=20))
    assert r.preco == D(0)
    assert r.status == "ok"


def test_sem_aliquotas_preco_igual_custo():
    r = precificar(D(1000), aliq())  # tudo 0
    assert r.preco == D(1000)
    assert r.indiretos == D(0)
    assert r.tributos == D(0)
    assert r.lucro == D(0)


# --------------------------------------------------------------------------
# Cascata: resolver_aliquotas (serviço/proposta/empresa → 0).
# cfg é injetado para testar sem banco.
# --------------------------------------------------------------------------

def _empresa(**kw):
    base = dict(
        imposto_pct_padrao=D(8), lucro_pct_padrao=D(10),
        bdi_ac_pct=D(5), bdi_seguro_pct=D(1), bdi_risco_pct=D(2),
        bdi_garantia_pct=D(1), bdi_desp_financeiras_pct=D(3),
        bdi_tl_aviso_pct=D(60), bdi_tl_bloqueio_pct=D(90),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _servico(imposto_pct=None, margem_lucro_pct=None):
    return SimpleNamespace(
        admin_id=1, imposto_pct=imposto_pct, margem_lucro_pct=margem_lucro_pct,
    )


def _proposta(**kw):
    base = dict(
        bdi_ac_pct=None, bdi_seguro_pct=None, bdi_risco_pct=None,
        bdi_garantia_pct=None, bdi_desp_financeiras_pct=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_cascata_tl_servico_vence_empresa():
    a = resolver_aliquotas(_servico(imposto_pct=D(15), margem_lucro_pct=D(5)),
                           cfg=_empresa())
    assert a.t == D(15) and a.l == D(5)


def test_cascata_tl_herda_empresa_quando_servico_nulo():
    a = resolver_aliquotas(_servico(), cfg=_empresa())
    assert a.t == D(8) and a.l == D(10)


def test_cascata_bdi_proposta_vence_empresa():
    a = resolver_aliquotas(_servico(), proposta=_proposta(bdi_ac_pct=D(20)),
                           cfg=_empresa())
    assert a.ac == D(20)        # override da proposta
    assert a.s == D(1)          # demais herdam a empresa
    assert a.df == D(3)


def test_cascata_bdi_herda_empresa_sem_proposta():
    a = resolver_aliquotas(_servico(), cfg=_empresa())
    assert (a.ac, a.s, a.r, a.g, a.df) == (D(5), D(1), D(2), D(1), D(3))


def test_cascata_tudo_zero_sem_empresa():
    # admin_id=None → sem lookup de empresa; tudo cai para 0/defaults.
    serv = SimpleNamespace(admin_id=None, imposto_pct=None, margem_lucro_pct=None)
    a = resolver_aliquotas(serv, cfg=None)
    assert (a.t, a.l, a.ac, a.s, a.r, a.g, a.df) == (D(0),) * 7
    assert a.tl_aviso == D(60) and a.tl_bloqueio == D(90)  # defaults


def test_cascata_limiares_da_empresa():
    a = resolver_aliquotas(_servico(), cfg=_empresa(bdi_tl_aviso_pct=D(40),
                                                    bdi_tl_bloqueio_pct=D(70)))
    assert a.tl_aviso == D(40) and a.tl_bloqueio == D(70)
