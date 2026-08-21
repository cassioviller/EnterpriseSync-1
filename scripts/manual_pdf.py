#!/usr/bin/env python3
"""Monta um manual visual (PDF + markdown) a partir de um roteiro e das capturas.

Extraído de `gerar_manual_compras.py` em 21/08 para servir também ao manual do
RDO. A regra que veio junto: a legenda numerada embaixo de cada figura sai do
MESMO `Campo` que desenhou a caixa — não existem duas listas para divergir. E o
ato é um campo da própria `Tela` (📖 o dicionário `ATOS` por prefixo de slug foi
removido em 19/08: era a segunda lista, e divergiu).

Uso, pelos geradores de cada manual:

    construir_pdf(roteiro, pdf=..., shots=..., titulo=..., subtitulo=...,
                  intro=[parágrafos], quem={papel: 'quem faz'})
    escrever_markdown(roteiro, md=..., titulo=..., gerador=..., roteiro_nome=...)

`construir_pdf` levanta `SystemExit` se faltar a captura de algum slug — manual
com foto velha é o defeito que a ferramenta existe para impedir.
"""
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

AZUL = colors.HexColor('#1a3d6e')
LARANJA = colors.HexColor('#e8590c')
CINZA = colors.HexColor('#5a6673')

PAGE_W, PAGE_H = A4
MARGEM = 1.7 * cm
UTIL = PAGE_W - 2 * MARGEM

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


def construir_pdf(roteiro, *, pdf, shots, titulo, subtitulo, intro, quem, autor='SIGE'):
    """Escreve o PDF. `intro` é a lista de parágrafos da capa; `quem` mapeia o
    `papel` da tela para "quem faz" no rodapé de cada passo."""
    pdf, shots = Path(pdf), Path(shots)
    faltando = [t.slug for t in roteiro if not (shots / f'{t.slug}.png').exists()]
    if faltando:
        raise SystemExit(
            'faltam capturas: ' + ', '.join(faltando)
            + '\nRode a captura antes — e não monte o manual com foto velha.')
    pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(pdf), pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
        title=titulo, author=autor)

    fluxo = [Spacer(1, 5 * cm),
             Paragraph(titulo, est['Capa']),
             Paragraph(subtitulo, est['CapaSub']),
             Spacer(1, 1.2 * cm)]
    fluxo += [Paragraph(p, est['Corpo']) for p in intro]
    fluxo.append(PageBreak())

    for i, tela in enumerate(roteiro):
        if tela.ato:
            if i:
                fluxo.append(PageBreak())
            fluxo.append(Paragraph(tela.ato, est['Ato']))
            fluxo.append(Paragraph(tela.ato_resumo, est['AtoSub']))
        elif i:
            fluxo.append(PageBreak())
        fluxo.append(Paragraph(f'{i + 1}. {tela.titulo}', est['Passo']))
        fluxo.append(Paragraph(
            f'Quem faz: <b>{quem.get(tela.papel, tela.papel)}</b> &nbsp;·&nbsp; '
            f'Onde: <font face="Courier">{tela.rota or "(mesma tela)"}</font>', est['Papel']))
        fluxo.append(Paragraph(tela.resumo, est['Corpo']))
        fluxo.append(_imagem(shots / f'{tela.slug}.png', UTIL))
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


def escrever_markdown(roteiro, *, md, titulo, gerador, roteiro_nome):
    """O markdown fonte ao lado do PDF: o PDF é o que se manda, o markdown é o
    que se corrige — mas só editando o roteiro e gerando de novo."""
    md = Path(md)
    linhas = [f'# {titulo}',
              '', 'Manual de uso do SIGE. Gerado por '
              f'`{gerador}` a partir de '
              f'`{roteiro_nome}` — **não edite este arquivo à '
              'mão**: edite o roteiro e gere de novo.', '']
    for i, t in enumerate(roteiro):
        if t.ato:
            linhas += [f'## {t.ato}', '', t.ato_resumo, '']
        linhas += [f'### {i + 1}. {t.titulo}', '',
                   f'**Quem faz:** {t.papel} · **Onde:** `{t.rota or "(mesma tela)"}`', '',
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
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text('\n'.join(linhas), encoding='utf-8')
