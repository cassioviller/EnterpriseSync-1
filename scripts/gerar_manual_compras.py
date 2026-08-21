#!/usr/bin/env python3
"""Monta o manual de compras em PDF, a partir do roteiro e das capturas.

Uso:
    python scripts/gerar_manual_compras.py

Lê o MESMO roteiro que desenhou as caixas (`scripts/roteiro_manual_compras.py`),
então a legenda numerada embaixo de cada figura não tem como divergir da caixa
desenhada na figura: são a mesma lista.

Sai em `docs/manual_compras/Manual_Compras_SIGE.pdf`, mais o markdown fonte ao
lado — o PDF é o que se manda para a obra, o markdown é o que se corrige.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manual_pdf import construir_pdf, escrever_markdown
from roteiro_manual_compras import telas

RAIZ = Path('docs/manual_compras')
SHOTS = RAIZ / 'screenshots'
PDF = RAIZ / 'Manual_Compras_SIGE.pdf'
MD = RAIZ / 'manual-compras.md'

# 21/08 — estilos, figura, legenda e avisos saíram daqui para `manual_pdf.py`,
# que o manual do RDO também usa. O que é de compras ficou: caminhos e textos.
TITULO = 'Compras, do pedido ao pagamento'
QUEM = {'anon': 'qualquer pessoa', 'solicitante': 'o encarregado da obra',
        'gestor': 'a gerência', 'comprador': 'o comprador',
        'admin': 'o administrador', 'financeiro': 'o financeiro'}
INTRO = ['Este manual segue uma compra inteira, na ordem em que ela '
         'acontece: o encarregado pede, a gerência aprova, o comprador '
         'negocia e o financeiro paga. Em cada tela, as caixas '
         'numeradas marcam o que precisa ser preenchido.',
         'Os campos marcados com <font color="#c92a2a">*</font> são '
         'obrigatórios.']


def construir():
    roteiro = telas()
    construir_pdf(roteiro, pdf=PDF, shots=SHOTS, titulo=TITULO,
                  subtitulo='Manual de uso do SIGE', intro=INTRO, quem=QUEM)
    return roteiro


def markdown(roteiro):
    escrever_markdown(roteiro, md=MD, titulo=TITULO,
                      gerador='scripts/gerar_manual_compras.py',
                      roteiro_nome='scripts/roteiro_manual_compras.py')


if __name__ == '__main__':
    roteiro = construir()
    markdown(roteiro)
    print(f'[OK] {PDF} ({PDF.stat().st_size // 1024} KB)')
    print(f'[OK] {MD}')
