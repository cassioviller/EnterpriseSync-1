"""Helper de precificação centralizado — BDI completo padrão TCU.

Unidade isolada (sem dependência de template/HTTP), testável sozinha.
Toda a fórmula e o guarda-corpo do orçamento vivem aqui; as 3 funções de
cálculo em `services/orcamento_service.py` delegam a este módulo.

Fórmula (ADR 0001 / spec 2026-06-05):

    indiretos = custo_direto × (AC + S + R + G + DF)/100
    base      = custo_direto + indiretos
    preço     = base / (1 − (T + L)/100)
    tributos  = preço × T/100
    lucro     = preço × L/100            # L "por dentro" (corrige D2)

Invariante: custo_direto + indiretos + tributos + lucro == preço.
Com AC=S=R=G=DF=0 reduz a `custo / (1 − (T+L)/100)` — idêntico ao
comportamento legado (não-disrupção).

Guarda-corpo (D3), com tl = T + L:
    tl ≥ bloqueio  → status='bloqueio', preço=0 (camadas de escrita não gravam)
    aviso ≤ tl < bloqueio → status='aviso' (calcula normalmente, alerta na UI)
    senão          → status='ok'

`resolver_aliquotas()` (cascata serviço/proposta/empresa) entra no P3.
"""
from dataclasses import dataclass, field
from decimal import Decimal

CEM = Decimal(100)
UM = Decimal(1)
ZERO = Decimal(0)


def _pct_str(d: Decimal) -> str:
    """Formata um percentual Decimal sem expoente nem zeros à direita."""
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


@dataclass(frozen=True)
class Aliquotas:
    """Percentuais (em %) já resolvidos para um cálculo. Value-object só de
    leitura. `t`/`l` por dentro; `ac..df` compõem o BDI; `tl_aviso`/
    `tl_bloqueio` são os limiares do guarda-corpo (defaults do schema)."""
    t: Decimal = ZERO
    l: Decimal = ZERO
    ac: Decimal = ZERO
    s: Decimal = ZERO
    r: Decimal = ZERO
    g: Decimal = ZERO
    df: Decimal = ZERO
    tl_aviso: Decimal = Decimal(60)
    tl_bloqueio: Decimal = Decimal(90)


@dataclass(frozen=True)
class Precificacao:
    """Resultado da precificação — breakdown completo para telas internas."""
    custo_direto: Decimal
    indiretos: Decimal
    tributos: Decimal
    lucro: Decimal
    preco: Decimal
    soma_bdi_pct: Decimal
    tl_pct: Decimal
    status: str            # 'ok' | 'aviso' | 'bloqueio'
    mensagem: str
    indiretos_componentes: dict = field(default_factory=dict)


def _config_empresa(admin_id):
    """Busca a ConfiguracaoEmpresa do tenant, com cache por contexto de app.

    Ao precificar muitos serviços no mesmo request (ex.: materializar todos os
    itens de uma proposta), evita um SELECT por item — consulta uma vez por
    admin_id e reaproveita. Fora de um contexto de app (ex.: chamada isolada),
    cai para a consulta direta.
    """
    from models import ConfiguracaoEmpresa
    try:
        from flask import g
        cache = getattr(g, "_bdi_cfg_cache", None)
        if cache is None:
            cache = g._bdi_cfg_cache = {}
        if admin_id not in cache:
            cache[admin_id] = ConfiguracaoEmpresa.query.filter_by(
                admin_id=admin_id).first()
        return cache[admin_id]
    except RuntimeError:
        # Sem contexto de aplicação ativo — consulta direta.
        return ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()


def _primeiro(*vals) -> Decimal:
    """Primeiro valor não-nulo da cascata, convertido para Decimal; senão 0."""
    for v in vals:
        if v is not None:
            return v if isinstance(v, Decimal) else Decimal(str(v))
    return ZERO


def resolver_aliquotas(servico, proposta=None, cfg=None) -> Aliquotas:
    """Resolve as alíquotas pela cascata do Bloco 3.

    - `T, L`  : serviço → empresa → 0   (`imposto_pct`/`margem_lucro_pct` →
      `imposto_pct_padrao`/`lucro_pct_padrao`).
    - `AC..DF`: proposta (se não-nula) → empresa → 0.
    - limiares do guarda-corpo: empresa (`bdi_tl_aviso_pct`/`bdi_tl_bloqueio_pct`),
      default 60/90.

    `cfg` (ConfiguracaoEmpresa) pode ser injetado; se ausente, é buscado pelo
    `admin_id` do serviço. Injetá-lo mantém esta função testável sem banco.
    """
    if cfg is None and getattr(servico, "admin_id", None) is not None:
        cfg = _config_empresa(servico.admin_id)

    def emp(attr):
        return getattr(cfg, attr, None) if cfg is not None else None

    def prop(attr):
        return getattr(proposta, attr, None) if proposta is not None else None

    t = _primeiro(getattr(servico, "imposto_pct", None), emp("imposto_pct_padrao"))
    l = _primeiro(getattr(servico, "margem_lucro_pct", None), emp("lucro_pct_padrao"))

    ac = _primeiro(prop("bdi_ac_pct"), emp("bdi_ac_pct"))
    s = _primeiro(prop("bdi_seguro_pct"), emp("bdi_seguro_pct"))
    r = _primeiro(prop("bdi_risco_pct"), emp("bdi_risco_pct"))
    g = _primeiro(prop("bdi_garantia_pct"), emp("bdi_garantia_pct"))
    df = _primeiro(prop("bdi_desp_financeiras_pct"), emp("bdi_desp_financeiras_pct"))

    tl_aviso = _primeiro(emp("bdi_tl_aviso_pct"), 60)
    tl_bloqueio = _primeiro(emp("bdi_tl_bloqueio_pct"), 90)

    return Aliquotas(
        t=t, l=l, ac=ac, s=s, r=r, g=g, df=df,
        tl_aviso=tl_aviso, tl_bloqueio=tl_bloqueio,
    )


def precificar(custo_total: Decimal, aliquotas: Aliquotas) -> Precificacao:
    """Aplica a fórmula TCU + guarda-corpo. Tudo em Decimal."""
    custo = custo_total if isinstance(custo_total, Decimal) else Decimal(str(custo_total))
    a = aliquotas

    soma_bdi_pct = a.ac + a.s + a.r + a.g + a.df
    indiretos = custo * soma_bdi_pct / CEM
    base = custo + indiretos
    tl_pct = a.t + a.l

    componentes = {
        "ac": custo * a.ac / CEM,
        "s": custo * a.s / CEM,
        "r": custo * a.r / CEM,
        "g": custo * a.g / CEM,
        "df": custo * a.df / CEM,
    }

    # Guarda-corpo (D3): bloqueio antes de qualquer divisão por ~0.
    if tl_pct >= a.tl_bloqueio:
        return Precificacao(
            custo_direto=custo,
            indiretos=indiretos,
            tributos=ZERO,
            lucro=ZERO,
            preco=ZERO,
            soma_bdi_pct=soma_bdi_pct,
            tl_pct=tl_pct,
            status="bloqueio",
            mensagem=(
                f"T+L ≥ {_pct_str(a.tl_bloqueio)}% — ajuste os percentuais "
                "de imposto/lucro"
            ),
            indiretos_componentes=componentes,
        )

    divisor = UM - tl_pct / CEM
    preco = base / divisor if divisor != ZERO else ZERO
    tributos = preco * a.t / CEM
    lucro = preco * a.l / CEM

    if tl_pct >= a.tl_aviso:
        status = "aviso"
        mensagem = (
            f"T+L = {_pct_str(tl_pct)}% — acima de {_pct_str(a.tl_aviso)}%; "
            "preço sensível a pequenas mudanças"
        )
    else:
        status = "ok"
        mensagem = ""

    return Precificacao(
        custo_direto=custo,
        indiretos=indiretos,
        tributos=tributos,
        lucro=lucro,
        preco=preco,
        soma_bdi_pct=soma_bdi_pct,
        tl_pct=tl_pct,
        status=status,
        mensagem=mensagem,
        indiretos_componentes=componentes,
    )
