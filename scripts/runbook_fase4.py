#!/usr/bin/env python3
"""Runbook da Fase 4 do ciclo de compras (régua de status), PELA TELA.

Uso:
    python scripts/runbook_fase4.py              # semeia e roda
    python scripts/runbook_fase4.py --sem-semear # aproveita o cenário que está lá

Pré-requisito: o app de pé em http://localhost:5000.

POR QUE ESTE RUNBOOK EXISTE, e é a razão de a fase ter critério de tela: 📖 a
spec fixou que "função pura que ninguém chama passa em todo teste — foi assim
que fechar_lote() ficou semanas testado e inalcançável". Aqui a afirmação é
sobre o DOM: a régua tem de estar na página, com as nove casas e o ponteiro.

O QUE ELE AFIRMA, passo a passo:
  1. a listagem tem ao menos um pedido com ponteiro, e o detalhe desse pedido
     tem #regua-status com as NOVE casas;
  2. o ponteiro existe e é uma das nove casas (ou o selo de nada pendente);
  3. as nove casas estão sempre no DOM, independentemente de aplicabilidade —
     casa apagada aparece, não some.

A sessão é a mesma maquinaria dos runbooks anteriores (`runbook_comum.py`):
Chromium via Playwright, login pela tela com `entrar()`, cenário do manual de
compras (`seed_manual_compras.py`), achado por MARCA de username, não por id.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

from runbook_comum import (VIEWPORT, Runbook, _pessoas_e_obra, abrir, entrar,
                           preparar_bibliotecas, semear)

RAIZ = Path(__file__).resolve().parent.parent
rb = Runbook('DA FASE 4 — RÉGUA DE STATUS (SEED)')

CHAVES = ('requisitada', 'aprovada', 'pedido_emitido', 'material_recebido',
          'nota_lancada', 'liberada', 'em_lote', 'paga', 'encerrada')

verdes, total = 0, 0


def afirma(descricao, condicao):
    global verdes, total
    total += 1
    if condicao:
        verdes += 1
        print('  OK   %s' % descricao)
    else:
        print('  FALHA %s' % descricao)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sem-semear', action='store_true')
    args = ap.parse_args()

    preparar_bibliotecas()

    if not args.sem_semear:
        print('semeando o cenário…')
        if not semear(RAIZ, rb, 'seed_manual_compras.py'):
            print('\n%d/%d' % (verdes, total))
            return 1

    from app import app
    from seed_manual_compras import MARCA, SENHA

    with app.app_context():
        pessoas, obra = _pessoas_e_obra()
        usuarios = {k: f'{MARCA}_{k}' for k in pessoas}

    with sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True,
                                 args=['--no-sandbox', '--disable-dev-shm-usage'])
        pg = nav.new_context(viewport=VIEWPORT).new_page()
        entrar(pg, usuarios['admin'], SENHA)

        try:
            print('Passo 1 — a régua está no detalhe do pedido')
            abrir(pg, '/compras')
            lista = pg.content()
            ids = re.findall(r'data-ponteiro-pedido="(\d+)"', lista)
            afirma('a listagem traz ao menos um pedido com ponteiro', bool(ids))
            if not ids:
                print('\n%d/%d' % (verdes, total))
                return 1

            abrir(pg, '/compras/%s' % ids[0])
            html = pg.content()
            afirma('o detalhe tem #regua-status', 'id="regua-status"' in html)
            for chave in CHAVES:
                afirma('a casa %s está no DOM' % chave,
                       'data-casa="%s"' % chave in html)

            print('\nPasso 2 — o ponteiro existe e é uma casa da régua')
            ponteiro = re.search(r'data-ponteiro="([a-z_]*)"', html)
            afirma('há ponteiro (ou o selo de nada pendente)', ponteiro is not None)
            if ponteiro and ponteiro.group(1):
                afirma('o ponteiro é uma das nove casas', ponteiro.group(1) in CHAVES)

            print('\nPasso 3 — casa apagada aparece, não some')
            apagadas = re.findall(r'data-aplicavel="nao"', html)
            print('  (informativo) casas inaplicáveis nesta compra: %d' % len(apagadas))
            afirma('as nove casas estão no DOM independentemente de aplicabilidade',
                   len(re.findall(r'data-casa="', html)) == 9)
        finally:
            nav.close()

    print('\n%d/%d' % (verdes, total))
    return 0 if verdes == total else 1


if __name__ == '__main__':
    sys.exit(main())
