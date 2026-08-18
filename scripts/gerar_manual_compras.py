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

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from roteiro_manual_compras import telas

RAIZ = Path('docs/manual_compras')
SHOTS = RAIZ / 'screenshots'
PDF = RAIZ / 'Manual_Compras_SIGE.pdf'
MD = RAIZ / 'manual-compras.md'

AZUL = colors.HexColor('#1a3d6e')
LARANJA = colors.HexColor('#e8590c')
CINZA = colors.HexColor('#5a6673')

PAGE_W, PAGE_H = A4
MARGEM = 1.7 * cm
UTIL = PAGE_W - 2 * MARGEM

ATOS = {
    '01': ('Antes de tudo', 'Entrar no sistema.'),
    '02': ('Ato 1 — Quem precisa, pede',
           'O encarregado da obra abre a requisição. Nada foi comprado ainda.'),
    '06': ('Ato 2 — Quem responde pela obra, decide',
           'A gerência aprova, rejeita ou devolve para conserto.'),
    '10': ('Ato 3 — Quem compra, negocia',
           'A requisição aprovada vira pedido, com fornecedor e valor real.'),
    '11': ('Ato 4 — Quem paga, confere',
           'A conta só é paga quando pedido, atesto e nota fecham.'),
}

est = getSampleStyleSheet()
est.add(ParagraphStyle('Capa', parent=est['Title'], fontSize=28, leading=34,
                       textColor=AZUL, alignment=TA_CENTER, spaceAfter=18))
est.add(ParagraphStyle('CapaSub', parent=est['Normal'], fontSize=13, leading=18,
                       textColor=CINZA, alignment=TA_CENTER, spaceAfter=10))
est.add(ParagraphStyle('Ato', parent=est['Heading1'], fontSize=19, leading=24,
                       textColor=LARANJA, spaceBefore=6, spaceAfter=3))
est.add(ParagraphStyle('AtoSub', parent=est['Normal'], fontSize=11, leading=15,
                       textColor=CINZA, spaceAfter=14))
est.add(ParagraphStyle('Passo', parent=est['Heading2'], fontSize=15, leading=19,
                       textColor=AZUL, spaceBefore=2, spaceAfter=5))
est.add(ParagraphStyle('Corpo', parent=est['BodyText'], fontSize=10.5, leading=14.5,
                       spaceAfter=7))
est.add(ParagraphStyle('Legenda', parent=est['Normal'], fontSize=9.5, leading=13))
est.add(ParagraphStyle('Papel', parent=est['Normal'], fontSize=9, leading=12,
                       textColor=CINZA, spaceAfter=8))


def _imagem(caminho, largura):
    with PILImage.open(caminho) as im:
        w, h = im.size
    altura = largura * h / w
    # Uma tela longa (formulário inteiro) não pode empurrar a legenda para fora
    # da página: limita pela altura útil e recalcula a largura.
    teto = PAGE_H - 2 * MARGEM - 8 * cm
    if altura > teto:
        largura = largura * teto / altura
        altura = teto
    return Image(str(caminho), width=largura, height=altura)


def _tabela_legenda(tela):
    linhas = [[Paragraph('<b>#</b>', est['Legenda']),
               Paragraph('<b>Campo</b>', est['Legenda']),
               Paragraph('<b>O que preencher</b>', est['Legenda'])]]
    for c in tela.campos:
        rotulo = c.rotulo + (' <font color="#c92a2a">*</font>' if c.obrigatorio else '')
        linhas.append([
            Paragraph(f'<b>{c.numero}</b>', est['Legenda']),
            Paragraph(rotulo, est['Legenda']),
            Paragraph(c.nota or ('Obrigatório.' if c.obrigatorio else '—'),
                      est['Legenda']),
        ])
    t = Table(linhas, colWidths=[1.0 * cm, 5.2 * cm, UTIL - 6.2 * cm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
        ('TEXTCOLOR', (0, 1), (0, -1), LARANJA),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#c9d2dc')),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _aviso(texto, cor_fundo, cor_borda, rotulo):
    p = Paragraph(f'<b>{rotulo}</b> {texto}', est['Corpo'])
    t = Table([[p]], colWidths=[UTIL])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo),
        ('LINEBEFORE', (0, 0), (0, -1), 3, cor_borda),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def construir():
    roteiro = telas()
    faltando = [t.slug for t in roteiro if not (SHOTS / f'{t.slug}.png').exists()]
    if faltando:
        raise SystemExit(
            'faltam capturas: ' + ', '.join(faltando)
            + '\nRode scripts/capturar_manual_compras.py antes — e não monte o '
              'manual com foto velha.')

    RAIZ.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF), pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
        title='Manual de compras — SIGE', author='SIGE')

    fluxo = [Spacer(1, 5 * cm),
             Paragraph('Compras, do pedido ao pagamento', est['Capa']),
             Paragraph('Manual de uso do SIGE', est['CapaSub']),
             Spacer(1, 1.2 * cm),
             Paragraph('Este manual segue uma compra inteira, na ordem em que ela '
                       'acontece: o encarregado pede, a gerência aprova, o comprador '
                       'negocia e o financeiro paga. Em cada tela, as caixas '
                       'numeradas marcam o que precisa ser preenchido.', est['Corpo']),
             Paragraph('Os campos marcados com <font color="#c92a2a">*</font> são '
                       'obrigatórios.', est['Corpo']),
             PageBreak()]

    for i, tela in enumerate(roteiro):
        chave = tela.slug.split('_')[0]
        if chave in ATOS:
            titulo, sub = ATOS[chave]
            if i:
                fluxo.append(PageBreak())
            fluxo.append(Paragraph(titulo, est['Ato']))
            fluxo.append(Paragraph(sub, est['AtoSub']))
        elif i:
            fluxo.append(PageBreak())

        fluxo.append(Paragraph(f'{i + 1}. {tela.titulo}', est['Passo']))
        quem = {'anon': 'qualquer pessoa', 'solicitante': 'o encarregado da obra',
                'gestor': 'a gerência', 'comprador': 'o comprador',
                'admin': 'o administrador', 'financeiro': 'o financeiro'}
        fluxo.append(Paragraph(
            f'Quem faz: <b>{quem.get(tela.papel, tela.papel)}</b> &nbsp;·&nbsp; '
            f'Onde: <font face="Courier">{tela.rota}</font>', est['Papel']))
        fluxo.append(Paragraph(tela.resumo, est['Corpo']))
        fluxo.append(_imagem(SHOTS / f'{tela.slug}.png', UTIL))
        fluxo.append(Spacer(1, 0.4 * cm))
        if tela.campos:
            fluxo.append(_tabela_legenda(tela))
            fluxo.append(Spacer(1, 0.3 * cm))
        # Os dois avisos viajam GRUDADOS: sozinhos numa página, viram um bilhete
        # solto que ninguém liga à tela de que estão falando.
        rodape = []
        if tela.depois:
            rodape.append(_aviso(tela.depois, colors.HexColor('#eaf6ec'),
                                 colors.HexColor('#2f9e44'), 'O que acontece:'))
            rodape.append(Spacer(1, 0.2 * cm))
        if tela.atencao:
            rodape.append(_aviso(tela.atencao, colors.HexColor('#fff4e6'),
                                 LARANJA, 'Atenção:'))
        if rodape:
            fluxo.append(KeepTogether(rodape))

    doc.build(fluxo)
    return roteiro


def markdown(roteiro):
    linhas = ['# Compras, do pedido ao pagamento',
              '', 'Manual de uso do SIGE. Gerado por '
              '`scripts/gerar_manual_compras.py` a partir de '
              '`scripts/roteiro_manual_compras.py` — **não edite este arquivo à '
              'mão**: edite o roteiro e gere de novo.', '']
    for i, t in enumerate(roteiro):
        chave = t.slug.split('_')[0]
        if chave in ATOS:
            titulo, sub = ATOS[chave]
            linhas += [f'## {titulo}', '', sub, '']
        linhas += [f'### {i + 1}. {t.titulo}', '',
                   f'**Quem faz:** {t.papel} · **Onde:** `{t.rota}`', '',
                   t.resumo, '',
                   f'![{t.titulo}](screenshots/{t.slug}.png)', '']
        if t.campos:
            linhas += ['| # | Campo | O que preencher |', '|---|---|---|']
            for c in t.campos:
                rot = c.rotulo + (' *' if c.obrigatorio else '')
                linhas.append(f'| {c.numero} | {rot} | '
                              f'{c.nota or ("Obrigatório." if c.obrigatorio else "—")} |')
            linhas.append('')
        if t.depois:
            linhas += [f'> **O que acontece:** {t.depois}', '']
        if t.atencao:
            linhas += [f'> ⚠️ **Atenção:** {t.atencao}', '']
    MD.write_text('\n'.join(linhas), encoding='utf-8')


if __name__ == '__main__':
    roteiro = construir()
    markdown(roteiro)
    print(f'[OK] {PDF} ({PDF.stat().st_size // 1024} KB)')
    print(f'[OK] {MD}')
