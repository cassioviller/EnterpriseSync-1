"""Task #115 — guard test: superfícies VISÍVEIS AO CLIENTE não podem
expor custo, imposto, margem, lucro, composição ou fórmulas internas.

Inspeciona estaticamente templates servidos ao cliente:
  - templates/propostas/portal_cliente.html
  - templates/propostas/pdf*.html
  - templates/propostas/visualizar.html
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, 'templates', 'propostas')

CLIENT_FACING = [
    'portal_cliente.html',
    'visualizar.html',
    'pdf.html',
    'pdf_estruturas_vale.html',
    'pdf_estruturas_vale_final.html',
    'pdf_estruturas_vale_new.html',
    'pdf_estruturas_vale_paginado.html',
]

FORBIDDEN_PATTERNS = [
    (r'percentual_nota_fiscal', 'percentual_nota_fiscal exposto'),
    (r'imposto_pct', 'imposto_pct exposto'),
    (r'margem_pct|margem_lucro_pct', 'margem_pct exposto'),
    (r'custo_unitario|custo_total|custoUnit\b|custoTot\b', 'custo exposto'),
    (r'lucro_total|lucro_unit', 'lucro exposto'),
    (r'composicao_snapshot|composicao_servico', 'composição exposta'),
    (r'\bformula\b|\bfórmula\b', 'fórmula exposta'),
]

# Allow-list trechos puramente decorativos / CSS (margem CSS, etc.)
def is_false_positive(line: str, label: str) -> bool:
    if 'margem_pct exposto' in label and re.search(r'(?i)margin[-:]', line):
        return True
    # Comentários jinja/html
    if re.match(r'\s*(<!--|{#)', line):
        return True
    return False


def scan_file(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    leaks = []
    for i, line in enumerate(lines, 1):
        for pattern, label in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                if is_false_positive(line, label):
                    continue
                leaks.append((i, label, line.rstrip()))
    return leaks


def main():
    print('=' * 70)
    print('Guard: nenhum dado interno (custo/imposto/margem/lucro/composição)')
    print('       deve aparecer em superfícies cliente')
    print('=' * 70)
    total_leaks = 0
    for fname in CLIENT_FACING:
        path = os.path.join(TPL_DIR, fname)
        if not os.path.exists(path):
            print(f'SKIP  {fname} (não existe)')
            continue
        leaks = scan_file(path)
        if not leaks:
            print(f'PASS  {fname}')
        else:
            for ln, label, content in leaks:
                print(f'FAIL  {fname}:{ln}  [{label}]  {content[:120]}')
                total_leaks += 1

    print('=' * 70)
    print(f'TOTAL leaks: {total_leaks}')
    print('=' * 70)
    sys.exit(0 if total_leaks == 0 else 1)


if __name__ == '__main__':
    main()
