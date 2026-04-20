"""Task #115 — paridade entre cálculo backend (services/orcamento_view_service.py)
e fórmula JS embutida em templates/orcamentos/editar.html.

Garante que o preview "tempo real" mostrado ao usuário coincide com os totais
persistidos pelo backend para os mesmos inputs.
"""
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.orcamento_view_service import _d, _q2  # noqa: E402


def js_preview(custo_unit: float, qtd: float, imp_pct: float, mar_pct: float):
    """Replica EXATA da fórmula JS em templates/orcamentos/editar.html."""
    divisor = 1 - (imp_pct or 0) / 100 - (mar_pct or 0) / 100
    if divisor <= 0:
        preco_unit = 0.0
    else:
        preco_unit = round((custo_unit / divisor) * 10000) / 10000
    custo_tot = round(custo_unit * qtd * 100) / 100
    venda_tot = round(preco_unit * qtd * 100) / 100
    lucro_tot = round((venda_tot - custo_tot) * 100) / 100
    return custo_tot, venda_tot, lucro_tot


def backend_preview(custo_unit, qtd, imp_pct, mar_pct):
    """Replica do cálculo no recalcular_item() (Decimal-based)."""
    custo_unit = _d(custo_unit)
    qtd = _d(qtd)
    imp = _d(imp_pct)
    mar = _d(mar_pct)
    divisor = Decimal('1') - (imp / Decimal('100')) - (mar / Decimal('100'))
    if divisor <= 0:
        preco_unit = Decimal('0')
    else:
        preco_unit = (custo_unit / divisor).quantize(Decimal('0.0001'))
    custo_tot = _q2(qtd * custo_unit)
    venda_tot = _q2(qtd * preco_unit)
    lucro_tot = venda_tot - custo_tot
    return float(custo_tot), float(venda_tot), float(lucro_tot)


def assert_close(a, b, tol=0.005, label=''):
    assert abs(a - b) <= tol, f'PARITY FAIL {label}: js={a} vs backend={b} (Δ={a-b})'


def main():
    cases = [
        # (custo_unit, qtd, imp%, mar%)
        (100.00, 1, 0, 0),
        (100.00, 10, 13.5, 30),
        (250.50, 3.5, 18, 25),
        (1000.00, 1, 0, 50),
        (75.25, 100, 5.5, 12.5),
        (12.34, 1000, 9.9, 19.9),
    ]
    print('=' * 70)
    print('PARIDADE Frontend (JS) ↔ Backend (services/orcamento_view_service)')
    print('=' * 70)
    fails = 0
    for custo_unit, qtd, imp, mar in cases:
        jc, jv, jl = js_preview(custo_unit, qtd, imp, mar)
        bc, bv, bl = backend_preview(custo_unit, qtd, imp, mar)
        try:
            assert_close(jc, bc, label=f'custo qtd={qtd} imp={imp} mar={mar}')
            assert_close(jv, bv, label=f'venda qtd={qtd} imp={imp} mar={mar}')
            assert_close(jl, bl, label=f'lucro qtd={qtd} imp={imp} mar={mar}')
            print(f'PASS  custo={custo_unit} q={qtd} imp={imp}% mar={mar}%  '
                  f'→ venda={jv:.2f} lucro={jl:.2f}')
        except AssertionError as e:
            fails += 1
            print(f'FAIL  {e}')

    # Edge: imposto + margem >= 100% deve render preço/venda = 0 em ambos
    jc, jv, jl = js_preview(500.0, 2, 60, 40)
    bc, bv, bl = backend_preview(500.0, 2, 60, 40)
    if jv == 0 and bv == 0:
        print('PASS  edge imp+mar=100% → venda=0 em ambos')
    else:
        fails += 1
        print(f'FAIL  edge imp+mar=100%: js_venda={jv} backend_venda={bv}')

    # Verifica que a fórmula no template realmente é "custo / (1 - imp/100 - mar/100)"
    tpl_path = os.path.join(os.path.dirname(__file__), '..', 'templates',
                            'orcamentos', 'editar.html')
    with open(tpl_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if re.search(r'custoUnit\s*/\s*divisor', content) and \
       re.search(r'1\s*-\s*\(imp\|\|0\)\s*/\s*100\s*-\s*\(mar\|\|0\)\s*/\s*100',
                 content) and 'Math.round((custoUnit / divisor) * 10000)' in content:
        print('PASS  template usa fórmula canônica do backend')
    else:
        fails += 1
        print('FAIL  template editar.html não usa fórmula canônica')

    print('=' * 70)
    print(f'TOTAL: {len(cases) + 2} checks, {fails} fail(s)')
    print('=' * 70)
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()
