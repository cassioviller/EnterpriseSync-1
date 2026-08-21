#!/usr/bin/env python3
"""Monta o manual do RDO em PDF e markdown, a partir do roteiro e das capturas.

Uso:
    .pythonlibs/bin/python scripts/gerar_manual_rdo.py

Lê o MESMO roteiro que desenhou as caixas (`scripts/roteiro_manual_rdo.py`).
Sai em `docs/manual_rdo/Manual_RDO_SIGE.pdf` + `manual-rdo.md`, e copia o PDF
para `static/docs/manual-rdo.pdf`, que o capítulo 23a do manual do sistema linka.

Plano: docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manual_pdf import construir_pdf, escrever_markdown

RAIZ = Path('docs/manual_rdo')
SHOTS = RAIZ / 'screenshots'
PDF = RAIZ / 'Manual_RDO_SIGE.pdf'
MD = RAIZ / 'manual-rdo.md'
PDF_NO_APP = Path('static/docs/manual-rdo.pdf')

TITULO = 'RDO, do cronograma à assinatura'
QUEM = {'anon': 'qualquer pessoa', 'encarregado': 'o encarregado (apontador da obra)',
        'gestor': 'o gestor da obra', 'admin': 'o administrador'}
INTRO = [
    'Este manual segue um dia de obra inteiro, na ordem em que ele acontece no '
    'sistema: as atividades vêm do cronograma, o encarregado lança efetivo, '
    'terceiros, avanço, ocorrências e fotos, salva, submete, o gestor confere, o '
    'encarregado assina, o gestor aprova — e, se um erro aparecer depois, retifica.',
    'Em cada tela, as caixas numeradas marcam o que precisa ser preenchido. Os '
    'campos com <font color="#c92a2a">*</font> são obrigatórios. A regra por trás '
    'de cada passo está no capítulo "RDO — Padrão de Preenchimento" do manual do '
    'sistema (/manual).',
]


def main():
    from roteiro_manual_rdo import telas
    roteiro = telas()
    construir_pdf(roteiro, pdf=PDF, shots=SHOTS, titulo=TITULO,
                  subtitulo='Manual de uso do SIGE', intro=INTRO, quem=QUEM)
    escrever_markdown(roteiro, md=MD, titulo=TITULO,
                      gerador='scripts/gerar_manual_rdo.py',
                      roteiro_nome='scripts/roteiro_manual_rdo.py')
    PDF_NO_APP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PDF, PDF_NO_APP)
    print(f'ok: {PDF} ({PDF.stat().st_size // 1024} KB), {MD}, {PDF_NO_APP}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
