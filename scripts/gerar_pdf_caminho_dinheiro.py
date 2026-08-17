#!/usr/bin/env python3
"""Gera `caminho-do-dinheiro.pdf` — o material de aprovação da Fase 8.

Existe como script, e não como PDF solto na raiz, porque o conteúdo vem do spec
(`docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md`) e vai mudar
quando as decisões forem fechadas ou quando a medição em produção for feita.
PDF regerado por comando é PDF que acompanha o spec; PDF anexado à mão é PDF
que envelhece calado.

⚠️ Os números daqui são ⚠️ dev, medidos em 17/08. A Task 1 da fase é refazer a
medição em produção — quando isso acontecer, os três números do resumo e o
"164 lançamentos" mudam AQUI, não só no spec.

Uso:
    python scripts/gerar_pdf_caminho_dinheiro.py [--saida caminho.pdf]

Por que ReportLab e não HTML→PDF: 🔬 17/08 o Chromium do Playwright não sobe
neste ambiente (faltam libnss3, libnspr4, libgbm e mais três, e não há root
para instalá-las). ReportLab já é dependência do projeto e é o que gera todos
os outros PDFs daqui.
"""
import argparse
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Paleta ────────────────────────────────────────────────────────────────
# O mundo do assunto é o livro-razão: papel greenbar, tinta com viés verde.
# Nada de cinza puro — neutro puro lê como não escolhido.
TINTA        = colors.HexColor('#1A211E')
TINTA_SUAVE  = colors.HexColor('#4C5852')
TINTA_MUDA   = colors.HexColor('#6E7A74')
PAPEL        = colors.HexColor('#FFFFFF')
FAIXA        = colors.HexColor('#ECF1EA')   # a listra do formulário contínuo
REGUA        = colors.HexColor('#D5DDD6')
REGUA_FORTE  = colors.HexColor('#A9B6AB')
ACENTO       = colors.HexColor('#1F5C4B')
ACENTO_FUNDO = colors.HexColor('#E2EDE7')
SINAL        = colors.HexColor('#A8641B')   # decisão pendente
SINAL_FUNDO  = colors.HexColor('#F6EBDC')
ALARME       = colors.HexColor('#8C2F2A')   # onde o caminho quebra
ALARME_FUNDO = colors.HexColor('#F6E5E3')

SERIF, SERIF_B = 'Times-Roman', 'Times-Bold'
SANS,  SANS_B  = 'Helvetica', 'Helvetica-Bold'
MONO,  MONO_B  = 'Courier', 'Courier-Bold'

LARGURA_UTIL = A4[0] - 40 * mm


def _p(nome, **kw):
    base = dict(fontName=SANS, fontSize=9.5, leading=14, textColor=TINTA,
                alignment=TA_LEFT, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(nome, **base)


E = {
    'titulo':     _p('titulo', fontName=SERIF, fontSize=30, leading=32, spaceAfter=10),
    'sobrancelha': _p('sobrancelha', fontName=MONO, fontSize=7.5, leading=11,
                      textColor=ACENTO, spaceAfter=10),
    'chamada':    _p('chamada', fontName=SERIF, fontSize=12.5, leading=17,
                     textColor=TINTA_SUAVE, spaceAfter=12),
    'meta':       _p('meta', fontName=MONO, fontSize=7.5, leading=11, textColor=TINTA_MUDA),
    'rotulo':     _p('rotulo', fontName=MONO, fontSize=7.5, leading=11,
                     textColor=TINTA_MUDA, spaceAfter=4),
    'h2':         _p('h2', fontName=SERIF, fontSize=17, leading=20, spaceAfter=8),
    'h3':         _p('h3', fontName=SANS_B, fontSize=10, leading=14, spaceAfter=4),
    'corpo':      _p('corpo', spaceAfter=8),
    'corpo_suave': _p('corpo_suave', textColor=TINTA_SUAVE, spaceAfter=6),
    'no_titulo':  _p('no_titulo', fontName=SANS_B, fontSize=10.5, leading=14),
    'no_corpo':   _p('no_corpo', fontSize=9, leading=13, textColor=TINTA_SUAVE),
    'campos':     _p('campos', fontName=MONO, fontSize=7.5, leading=11.5,
                     textColor=TINTA_MUDA),
    'quem':       _p('quem', fontName=MONO, fontSize=7, leading=10, textColor=TINTA),
    'fase':       _p('fase', fontName=MONO, fontSize=7.5, leading=11, textColor=ACENTO),
    'num_grande': _p('num_grande', fontName=SERIF, fontSize=22, leading=24),
    'cel':        _p('cel', fontSize=8.5, leading=12),
    'cel_cab':    _p('cel_cab', fontName=MONO, fontSize=7, leading=10, textColor=TINTA_MUDA),
    'cel_mono':   _p('cel_mono', fontName=MONO, fontSize=7.5, leading=11),
    'dre':        _p('dre', fontSize=9, leading=13),
    'dre_num':    _p('dre_num', fontName=MONO, fontSize=9, leading=13, alignment=TA_RIGHT),
    'pergunta':   _p('pergunta', fontName=SERIF, fontSize=11.5, leading=15, spaceAfter=3),
    'rodape':     _p('rodape', fontSize=8, leading=12, textColor=TINTA_MUDA),
}


class Regua(Flowable):
    """Fio horizontal. O documento é um razão; o fio é o que separa as linhas."""

    def __init__(self, cor=REGUA, espessura=0.6, largura=None, espaco=0):
        Flowable.__init__(self)
        self.cor, self.espessura = cor, espessura
        self.largura, self.espaco = largura, espaco
        self.height = espessura + espaco

    def wrap(self, aw, ah):
        self.width = self.largura or aw
        return (self.width, self.height)

    def draw(self):
        self.canv.setStrokeColor(self.cor)
        self.canv.setLineWidth(self.espessura)
        self.canv.line(0, self.espaco, self.width, self.espaco)


class Seta(Flowable):
    """A seta do fluxograma. Desenhada, e não escrita como caractere: ▼ não
    existe nas fontes internas do ReportLab e sairia como quadrado vazio."""

    def __init__(self, altura=15):
        Flowable.__init__(self)
        self.height = altura

    def wrap(self, aw, ah):
        self.width = aw
        return (aw, self.height)

    def draw(self):
        x = self.width / 2.0
        self.canv.setStrokeColor(REGUA_FORTE)
        self.canv.setFillColor(REGUA_FORTE)
        self.canv.setLineWidth(1)
        self.canv.line(x, self.height, x, 5)
        p = self.canv.beginPath()
        p.moveTo(x - 3.2, 5)
        p.lineTo(x + 3.2, 5)
        p.lineTo(x, 0)
        p.close()
        self.canv.drawPath(p, fill=1, stroke=0)


def _caixa(conteudo, borda=REGUA, fundo=PAPEL, largura=None, pad=9):
    """Uma caixa do fluxograma, ou qualquer bloco emoldurado."""
    t = Table([[conteudo]], colWidths=[largura or LARGURA_UTIL])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, borda),
        ('BACKGROUND', (0, 0), (-1, -1), fundo),
        ('LEFTPADDING', (0, 0), (-1, -1), pad),
        ('RIGHTPADDING', (0, 0), (-1, -1), pad),
        ('TOPPADDING', (0, 0), (-1, -1), pad),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _chip(texto, cor_borda=REGUA_FORTE, cor_texto=TINTA, fundo=FAIXA):
    """A etiqueta de QUEM faz o passo."""
    t = Table([[Paragraph(texto.upper(), ParagraphStyle(
        'chip', parent=E['quem'], textColor=cor_texto))]])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, cor_borda),
        ('BACKGROUND', (0, 0), (-1, -1), fundo),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return t


def no(quem, titulo, descricao, campos=None, tom='normal', largura=None):
    """Uma caixa do fluxograma: quem faz · o que acontece · o que fica registrado."""
    borda, fundo = REGUA, PAPEL
    chip_borda, chip_texto, chip_fundo = REGUA_FORTE, TINTA, FAIXA
    if tom == 'quebrado':
        borda, fundo = ALARME, ALARME_FUNDO
        chip_borda, chip_texto, chip_fundo = ALARME, ALARME, PAPEL
    elif tom == 'novo':
        borda, fundo = ACENTO, ACENTO_FUNDO
        chip_borda, chip_texto, chip_fundo = ACENTO, ACENTO, PAPEL
    elif tom == 'ramo':
        fundo = FAIXA

    larg = largura or LARGURA_UTIL
    interna = larg - 18

    linhas = [[_chip(quem, chip_borda, chip_texto, chip_fundo)],
              [Spacer(1, 4)],
              [Paragraph(titulo, E['no_titulo'])],
              [Paragraph(descricao, E['no_corpo'])]]
    if campos:
        linhas += [[Spacer(1, 5)],
                   [Regua(REGUA, 0.4, espaco=2)],
                   [Spacer(1, 3)],
                   [Paragraph(campos, E['campos'])]]

    miolo = Table(linhas, colWidths=[interna])
    miolo.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
    ]))
    return _caixa(miolo, borda, fundo, larg)


def fase(texto):
    t = _caixa(Paragraph(texto.upper(), E['fase']), REGUA, ACENTO_FUNDO,
               largura=len(texto) * 4.6 + 24, pad=5)
    t.hAlign = 'LEFT'
    return t


def secao(rotulo, titulo):
    return [Spacer(1, 16), Paragraph(rotulo.upper(), E['rotulo']),
            Regua(REGUA, 0.6, espaco=3), Spacer(1, 8),
            Paragraph(titulo, E['h2'])]


def aviso(tag, texto, tom='neutro'):
    borda, fundo, cor_tag = REGUA, PAPEL, TINTA_MUDA
    if tom == 'sinal':
        borda, fundo, cor_tag = SINAL, SINAL_FUNDO, SINAL
    elif tom == 'alarme':
        borda, fundo, cor_tag = ALARME, ALARME_FUNDO, ALARME
    miolo = Table([[Paragraph(tag.upper(), ParagraphStyle(
                        'tag', parent=E['rotulo'], textColor=cor_tag, spaceAfter=3))],
                   [Paragraph(texto, E['no_corpo'])]],
                  colWidths=[LARGURA_UTIL - 20])
    miolo.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return _caixa(miolo, borda, fundo, pad=10)


def tabela(cabecalho, linhas, larguras, alinhamento_num=None):
    """Tabela em listras de razão — a linha par ganha a faixa verde."""
    dados = [[Paragraph(c.upper(), E['cel_cab']) for c in cabecalho]]
    for ln in linhas:
        dados.append([c if isinstance(c, Paragraph) else Paragraph(str(c), E['cel'])
                      for c in ln])
    t = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [
        ('BOX', (0, 0), (-1, -1), 0.8, REGUA),
        ('BACKGROUND', (0, 0), (-1, 0), FAIXA),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, REGUA_FORTE),
        ('LINEBELOW', (0, 1), (-1, -2), 0.4, REGUA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]
    for i in range(2, len(dados), 2):
        estilo.append(('BACKGROUND', (0, i), (-1, i), FAIXA))
    if alinhamento_num:
        estilo.append(('ALIGN', (alinhamento_num, 1), (alinhamento_num, -1), 'RIGHT'))
    t.setStyle(TableStyle(estilo))
    return t


def lado_a_lado(caixas, espaco=8):
    """Duas ou três caixas na mesma linha — o ramo do fluxograma."""
    n = len(caixas)
    larg = (LARGURA_UTIL - espaco * (n - 1)) / n
    linha, cols = [], []
    for i, c in enumerate(caixas):
        linha.append(c)
        cols.append(larg)
        if i < n - 1:
            linha.append('')
            cols.append(espaco)
    t = Table([linha], colWidths=cols)
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _rodape_pagina(canv: rl_canvas.Canvas, doc):
    canv.saveState()
    canv.setFont(MONO, 7)
    canv.setFillColor(TINTA_MUDA)
    canv.drawString(20 * mm, 12 * mm, 'SIGE · Veks Engenharia · Fase 8 — proposta para aprovação')
    canv.drawRightString(A4[0] - 20 * mm, 12 * mm, f'{doc.page}')
    canv.setStrokeColor(REGUA)
    canv.setLineWidth(0.5)
    canv.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canv.restoreState()


def construir():
    h = []

    # ── Capa ──────────────────────────────────────────────────────────────
    h += [
        Paragraph('PROPOSTA PARA APROVAÇÃO &nbsp;·&nbsp; FASE 8 &nbsp;·&nbsp; FINANCEIRO', E['sobrancelha']),
        Paragraph('O Caminho do Dinheiro', E['titulo']),
        Paragraph(
            'Como o dinheiro percorre o sistema hoje, o ponto exato em que a informação '
            'se perde, e o que muda para que o financeiro consiga responder '
            '&ldquo;como está a empresa&rdquo; — e não só &ldquo;quanto custou esta obra&rdquo;.',
            E['chamada']),
        Spacer(1, 6),
        Paragraph('DATA 17/08/2026 &nbsp;&nbsp;&nbsp; SISTEMA SIGE · VEKS ENGENHARIA '
                  '&nbsp;&nbsp;&nbsp; SITUAÇÃO AGUARDANDO APROVAÇÃO', E['meta']),
        Spacer(1, 6),
        Regua(REGUA_FORTE, 1.2, espaco=4),
    ]

    # ── Resumo ────────────────────────────────────────────────────────────
    h += secao('Em uma página', 'O que está sendo proposto')
    h += [
        Paragraph(
            'O sistema registra bem o que sai. O que ele não faz é <b>classificar</b> o '
            'que sai de um jeito só — e sem isso não há margem de contribuição, não há '
            'demonstração de fluxo de caixa e não há indicador nenhum.', E['corpo']),
        Paragraph(
            'A causa é uma só: <b>o plano de contas foi criado por três caminhos '
            'diferentes</b>, e o mesmo código de conta significa coisas diferentes '
            'dependendo de por qual tela a empresa entrou primeiro.', E['corpo']),
        Spacer(1, 6),
    ]

    resumo = []
    for numero, rotulo, texto in [
        ('94%', 'Empresas já no plano certo',
         'A maioria já usa o plano que vai virar o oficial. A correção alcança a minoria.'),
        ('164', 'Lançamentos a remapear',
         'De um total de 4.481. É o único ponto que mexe em registro histórico.'),
        ('0', 'Lançamentos sem conta válida',
         'Nenhum lançamento aponta para conta inexistente. A base está íntegra.'),
    ]:
        miolo = Table([[Paragraph(rotulo.upper(), E['rotulo'])],
                       [Paragraph(numero, E['num_grande'])],
                       [Spacer(1, 3)],
                       [Paragraph(texto, E['no_corpo'])]],
                      colWidths=[(LARGURA_UTIL - 16) / 3 - 18])
        miolo.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        resumo.append(_caixa(miolo, REGUA, PAPEL, (LARGURA_UTIL - 16) / 3))
    h += [lado_a_lado(resumo), Spacer(1, 10)]

    h += [aviso('Leia antes de aprovar',
                'Os três números acima foram medidos no <b>ambiente de testes</b>, não no '
                'sistema em produção. Eles provam a <i>forma</i> do problema, não o '
                '<i>tamanho</i> dele. <b>A primeira tarefa do plano é medir em produção</b> — '
                'e se o resultado for muito diferente, a proposta volta para a mesa antes '
                'de qualquer linha de código.', 'sinal')]

    # ── Fluxograma 1 ──────────────────────────────────────────────────────
    h += secao('Fluxograma 1 de 2', 'O caminho do dinheiro hoje')
    h += [Paragraph(
        'Da necessidade no canteiro até o relatório. Cada caixa mostra <b>quem faz</b>, '
        '<b>o que acontece</b> e <b>o que fica registrado</b>. As caixas em vermelho são '
        'onde o caminho quebra.', E['corpo']), Spacer(1, 6)]

    h += [KeepTogether([
        fase('1 · Compra'), Spacer(1, 5),
        no('Encarregado da obra', 'Requisição de compra',
           'Pede o material que falta, com justificativa e data de necessidade.',
           '<b>Registra:</b> nº da requisição · obra · etapa · itens (descrição, '
           'unidade, quantidade, preço estimado) · solicitante · data'),
    ]), Seta()]
    h += [no('Gestor / Diretoria', 'Aprovação por alçada',
             'O valor e mais quatro condições definem quantas assinaturas a compra exige.',
             '<b>Registra:</b> faixa de alçada · aprovadores · data e valor no momento '
             'da assinatura · motivo do degrau'), Seta()]
    h += [no('Comprador', 'Pedido ao fornecedor',
             'A requisição aprovada vira pedido. É aqui que nasce a obrigação a pagar.',
             '<b>Registra:</b> nº do pedido · fornecedor · condição de pagamento · '
             'parcelas · valor · centro de custo')]

    h += [Spacer(1, 12), KeepTogether([
        fase('2 · Entrega'), Spacer(1, 5),
        no('Almoxarife', 'Recebimento e atesto',
           'Confere o que chegou de fato. O estoque nasce daqui, não da compra.',
           '<b>Registra:</b> data do recebimento · quantidade por item · quem recebeu · '
           'encerramento de saldo com motivo'),
    ]), Seta()]
    h += [no('Financeiro', 'Nota fiscal e liberação',
             'Com pedido, nota e atesto fechados, a conta é liberada para pagamento.',
             '<b>Registra:</b> número e série da nota · valor · emissão · vencimento · '
             'quem lançou · quem liberou · justificativa, quando liberada com pendência')]

    h += [Spacer(1, 12), KeepTogether([
        fase('3 · Pagamento'), Spacer(1, 5),
        lado_a_lado([
        no('Fluxo A', 'Faturado', 'Paga depois de receber. Exige a tríade completa.',
           tom='ramo', largura=(LARGURA_UTIL - 8) / 2),
        no('Fluxo B', 'Adiantamento',
           'Paga antes. Fica na lista &ldquo;pago, aguardando entrega&rdquo; até o '
           'material chegar.', tom='ramo', largura=(LARGURA_UTIL - 8) / 2),
        ]),
    ]), Seta()]
    h += [no('Financeiro', 'Baixa do pagamento',
             'O dinheiro sai do banco e a conta é quitada.',
             '<b>Registra:</b> valor pago · data · forma de pagamento · banco debitado')]

    # KeepTogether: rótulo de fase separado das caixas dele é a pior quebra de
    # página possível num fluxograma — quem vira a folha perde o agrupamento.
    h += [Spacer(1, 12), KeepTogether([
        fase('4 · Registro contábil'), Spacer(1, 5),
        no('Sistema', 'Lançamento na conta contábil',
           'O sistema debita e credita automaticamente. <b>É aqui que o caminho '
           'quebra:</b> a conta escolhida depende de qual plano de contas a empresa '
           'recebeu — e são três planos possíveis, com significados diferentes.',
           '<b>Registra:</b> data · histórico · valor · <b>código da conta</b> '
           '&lt;-- o campo em disputa', tom='quebrado'),
    ]), Seta()]
    h += [no('Financeiro', 'Relatórios',
             'Balancete, razão, DRE e balanço saem — e saem certos dentro do que sabem. '
             '<b>Não existe margem de contribuição, não existe demonstração de fluxo de '
             'caixa e não existe indicador nenhum</b>, porque nenhum deles é calculável '
             'sobre um código que significa duas coisas.', tom='quebrado')]

    # ── A causa ───────────────────────────────────────────────────────────
    h += secao('A causa', 'O mesmo código, dois significados')
    h += [Paragraph(
        'Três telas diferentes criam o plano de contas, cada uma com um conteúdo próprio. '
        'A que for usada primeiro decide — e as outras são ignoradas em silêncio. '
        'O resultado, hoje, em empresas diferentes do mesmo sistema:', E['corpo']),
        Spacer(1, 6)]

    def _colisao(codigo, significa, fonte):
        miolo = Table([[Paragraph(codigo, ParagraphStyle(
                            'cod', fontName=MONO, fontSize=17, leading=20,
                            textColor=ALARME))],
                       [Spacer(1, 3)],
                       [Paragraph(significa, ParagraphStyle(
                            'sig', fontName=SERIF, fontSize=13.5, leading=17,
                            textColor=TINTA))],
                       [Spacer(1, 5)],
                       [Paragraph(fonte, E['campos'])]],
                      colWidths=[(LARGURA_UTIL - 8) / 2 - 18])
        miolo.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return _caixa(miolo, ALARME, PAPEL, (LARGURA_UTIL - 8) / 2)

    h += [lado_a_lado([
        _colisao('5.1.01', 'Mão de Obra', 'quando o plano nasceu pela tela do Financeiro'),
        _colisao('5.1.01', 'Materiais Diretos', 'quando o plano nasceu pela tela da Contabilidade'),
    ]), Spacer(1, 10)]
    h += [Paragraph(
        'Não é aleatório e não é erro de digitação: é <b>em qual tela alguém clicou '
        'primeiro</b>. Duas empresas no mesmo sistema podem ter a mesma conta querendo '
        'dizer coisas opostas, e qualquer relatório que assuma um significado está errado '
        'para uma parte delas. O mesmo vale para &ldquo;Salários&rdquo;, hoje lançado em '
        'duas contas diferentes conforme o módulo que originou o lançamento.', E['corpo'])]
    h += [aviso('Vale registrar',
                'O sistema <b>já sabe disso e já se protege</b>: o DRE só classifica em '
                'linha própria os códigos cujo significado é igual nos três planos, e joga '
                'o restante numa linha &ldquo;outras despesas&rdquo;. Nada desaparece — mas '
                'também nada é analisável. A proposta é o conserto definitivo dessa contenção.')]

    # ── Fluxograma 2 ──────────────────────────────────────────────────────
    h += secao('Fluxograma 2 de 2', 'Como o caminho fica')
    h += [Paragraph(
        'As fases 1 a 3 não mudam em nada. O que muda é do registro contábil em diante: '
        'um plano de contas só, com dois campos novos, alimentando três leituras que hoje '
        'não existem.', E['corpo']), Spacer(1, 6)]
    h += [no('Fases 1 a 3', 'Compra, entrega e pagamento',
             'Idênticas ao fluxograma anterior. Nenhuma tela, nenhum campo, nenhuma '
             'rotina muda.'), Seta()]
    h += [no('Sistema', 'Plano de contas único',
             'Um plano oficial, criado pelo mesmo caminho para todo mundo. As duas telas '
             'concorrentes passam a alimentá-lo em vez de criar o seu próprio.',
             '<b>Campos novos na conta:</b> classificação do gasto (fixo / variável) · '
             'atividade no fluxo de caixa (operacional / investimento / financiamento)',
             tom='novo'), Seta()]
    h += [no('Financeiro', 'Classificação das contas',
             'Tela nova, preenchida uma vez e ajustável quando a empresa quiser. É a '
             '<b>única tarefa nova de rotina</b> que esta mudança cria — e ela é de vocês, '
             'porque a decisão é de negócio, não de sistema.',
             '<b>Por conta:</b> fixo · variável · não se aplica · não classificado',
             tom='novo'), Seta()]
    larg3 = (LARGURA_UTIL - 16) / 3
    h += [lado_a_lado([
        no('Novo', 'DRE Gerencial',
           'Receita menos variáveis = margem de contribuição. Menos fixos = resultado.',
           tom='novo', largura=larg3),
        no('Novo', 'DFC',
           'O caixa separado em operação, investimento e financiamento.',
           tom='novo', largura=larg3),
        no('Novo', 'Indicadores',
           'Liquidez, endividamento, margem, giro e ciclo financeiro.',
           tom='novo', largura=larg3),
    ])]
    h += [Spacer(1, 8),
          aviso('Por que isto é barato',
                'As três leituras novas <b>não gravam nada</b> — elas apenas leem '
                'lançamentos que já existem. O único ponto que toca registro histórico é o '
                'remapeamento dos 164 lançamentos que estão no plano antigo, e ele é feito '
                'com uma tabela de correspondência conferida conta a conta, não por '
                'adivinhação.')]

    # ── Campos ────────────────────────────────────────────────────────────
    h += secao('Detalhamento', 'Os campos novos')
    h += [Paragraph(
        'Dois campos, ambos na conta contábil. Nenhum campo novo é pedido em nota fiscal, '
        'pedido, requisição ou pagamento.', E['corpo']), Spacer(1, 4)]
    h += [tabela(
        ['Campo', 'Onde aparece', 'Valores possíveis', 'Quem preenche'],
        [[Paragraph('Classificação<br/>do gasto', E['cel_mono']),
          Paragraph('Cadastro do plano de contas', E['cel']),
          Paragraph('<b>Fixo</b> — não varia com o volume de obra<br/>'
                    '<b>Variável</b> — varia com o volume<br/>'
                    '<b>Não se aplica</b> — ativo, passivo e receita<br/>'
                    '<b>Não classificado</b> — padrão inicial', E['cel']),
          Paragraph('Financeiro,<br/>por empresa', E['cel'])],
         [Paragraph('Atividade no<br/>fluxo de caixa', E['cel_mono']),
          Paragraph('Cadastro do plano de contas', E['cel']),
          Paragraph('<b>Operacional</b> — o dia a dia (padrão)<br/>'
                    '<b>Investimento</b> — compra e venda de bens<br/>'
                    '<b>Financiamento</b> — empréstimos e aportes', E['cel']),
          Paragraph('Financeiro,<br/>uma vez', E['cel'])]],
        [78, 95, 205, 77])]
    h += [Spacer(1, 10),
          Paragraph('Por que o padrão é &ldquo;não classificado&rdquo;, e não &ldquo;fixo&rdquo;', E['h3']),
          Paragraph(
              'Um padrão que já classifica produz uma margem que <i>parece</i> pronta e está '
              'errada. Conta não classificada <b>aparece no relatório como não '
              'classificada</b>, com o valor ao lado — quem lê sabe exatamente o quanto da '
              'conta ainda não foi decidido.', E['corpo']),
          Paragraph('Por que a classificação é por empresa', E['h3']),
          Paragraph(
              'O mesmo gasto é fixo para uma e variável para outra, e as duas estão certas: '
              'frota própria é custo fixo; frota alugada por obra é variável. O sistema não '
              'tem como decidir isso — e não deve fingir que tem.', E['corpo'])]

    # ── Resultado ─────────────────────────────────────────────────────────
    h += secao('O resultado', 'O que o financeiro passa a conseguir ler')
    h += [Paragraph(
        'Exemplo ilustrativo com números redondos, só para mostrar a forma do relatório — '
        '<b>não são dados da Veks</b>.', E['corpo']), Spacer(1, 4)]

    linhas_dre = [
        ('Receita de obras', '1.000.000,00', None),
        ('(−) Materiais aplicados', '380.000,00', None),
        ('(−) Mão de obra de produção', '240.000,00', None),
        ('(−) Equipamentos alugados por obra', '60.000,00', None),
        ('= Margem de contribuição', '320.000,00', 'destaque'),
        ('(−) Administrativo', '120.000,00', None),
        ('(−) Estrutura e escritório', '70.000,00', None),
        ('(−) Não classificado', '18.000,00', 'pendente'),
        ('= Resultado', '112.000,00', 'total'),
    ]
    dados = [[Paragraph('DRE GERENCIAL · EXEMPLO', E['cel_cab']),
              Paragraph('VALOR', ParagraphStyle('c', parent=E['cel_cab'], alignment=TA_RIGHT))]]
    estilo = [
        ('BOX', (0, 0), (-1, -1), 0.8, REGUA),
        ('BACKGROUND', (0, 0), (-1, 0), FAIXA),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, REGUA_FORTE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for i, (rot, val, tom) in enumerate(linhas_dre, start=1):
        cor = TINTA
        fonte, fonte_num = SANS, MONO
        if tom == 'destaque':
            cor, fonte, fonte_num = ACENTO, SANS_B, MONO_B
            estilo.append(('LINEABOVE', (0, i), (-1, i), 0.8, REGUA_FORTE))
        elif tom == 'pendente':
            cor = SINAL
        elif tom == 'total':
            fonte, fonte_num = SANS_B, MONO_B
            estilo.append(('LINEABOVE', (0, i), (-1, i), 0.8, REGUA_FORTE))
        dados.append([
            Paragraph(rot, ParagraphStyle(f'd{i}', parent=E['dre'], fontName=fonte, textColor=cor)),
            Paragraph(val, ParagraphStyle(f'n{i}', parent=E['dre_num'], fontName=fonte_num, textColor=cor)),
        ])
    t_dre = Table(dados, colWidths=[LARGURA_UTIL - 120, 120])
    t_dre.setStyle(TableStyle(estilo))
    h += [t_dre, Spacer(1, 8)]
    h += [Paragraph(
        'A linha em destaque é a pergunta que hoje não tem resposta no sistema: '
        '<b>quanto sobra de cada real faturado antes de pagar a estrutura</b>. A linha em '
        'âmbar é a honestidade do relatório — ela some sozinha à medida que as contas '
        'forem classificadas.', E['corpo'])]
    h += [Paragraph('E as outras duas leituras', E['h3']),
          Paragraph(
              '<b>DFC</b> — separa o caixa em operação, investimento e financiamento, e '
              'mostra a diferença se os três não fecharem com o extrato, em vez de '
              'escondê-la.', E['corpo']),
          Paragraph(
              '<b>Indicadores</b> — liquidez corrente e seca, endividamento, margem líquida, '
              'retorno sobre o patrimônio, giro do ativo, prazos médios e ciclo financeiro. '
              'Cada um exibindo a data-base e as contas que o compõem.', E['corpo'])]

    # ── Garantias ─────────────────────────────────────────────────────────
    h += secao('Garantias', 'O que não muda')
    for txt in [
        '<b>Nenhum número que já existe muda.</b> DRE e balanço de qualquer período '
        'fechado continuam saindo iguais — há um teste específico comparando antes e '
        'depois, e ele é condição para a mudança entrar.',
        '<b>Nenhuma rotina de compra, recebimento ou pagamento é alterada.</b> As telas '
        'do dia a dia continuam idênticas.',
        '<b>Nenhuma conta é apagada.</b> As contas do plano antigo sem lançamento são '
        'apenas desativadas — somem das listas de seleção e continuam existindo para o '
        'histórico.',
        '<b>Nenhum lançamento é apagado ou somado duas vezes.</b> Se um código não tiver '
        'correspondência clara no plano novo, a mudança <i>falha e aponta o código</i> — '
        'nunca chuta.',
    ]:
        h += [Paragraph('— ' + txt, E['corpo'])]

    # ── Decisões ──────────────────────────────────────────────────────────
    h += secao('O que precisamos de vocês', 'Cinco decisões')
    h += [Paragraph(
        'Nenhuma trava o início do trabalho — todas já têm recomendação, e seguem por ela '
        'se não houver objeção. Mas as três primeiras são de negócio, e a resposta de '
        'vocês vale mais que a nossa.', E['corpo']), Spacer(1, 4)]

    for pergunta, rec in [
        ('Qual plano de contas vira o oficial?',
         'o que 94% das empresas já usam, e que é o único que os lançamentos automáticos '
         'alimentam. Escolher outro seria migrar a maioria para agradar a minoria.'),
        ('Os lançamentos no plano antigo são convertidos ou congelados?',
         'convertidos, por uma tabela de correspondência conferida conta a conta. Congelar '
         'deixaria dois significados vivos para sempre. <i>Condicionada à medição em produção.</i>'),
        ('Quem classifica cada conta como fixa ou variável?',
         'o sistema sugere um padrão, o financeiro ajusta. O que não pode é o sistema '
         'decidir sozinho e a margem sair calculada com uma premissa que ninguém viu.'),
        ('O fluxo de caixa é montado pela entrada e saída de banco?',
         'sim — para cada movimento de banco, a natureza vem da contrapartida do '
         'lançamento. É o dado mais denso que o sistema tem hoje.'),
        ('Orçamento da empresa e plano de negócios entram agora?',
         'não. São produto novo, não correção. Esta fase paga a fundação; andar novo é '
         'outra conversa, depois desta funcionando.'),
    ]:
        miolo = Table([[Paragraph(pergunta, E['pergunta'])],
                       [Paragraph('<b><font color="#1F5C4B">Recomendação:</font></b> ' + rec,
                                  E['no_corpo'])]],
                      colWidths=[LARGURA_UTIL - 20])
        miolo.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        h += [KeepTogether(_caixa(miolo, REGUA, PAPEL, pad=10)), Spacer(1, 6)]

    # ── Rodapé ────────────────────────────────────────────────────────────
    h += [Spacer(1, 14), Regua(REGUA_FORTE, 1.2, espaco=4), Spacer(1, 8),
          Paragraph(
              'Documento preparado para a aprovação do plano da Fase 8 do SIGE. Os números '
              'citados foram medidos em <b>17/08/2026, no ambiente de testes</b> — a primeira '
              'tarefa do plano é repetir a medição em produção, e o resultado dela pode '
              'alterar a proposta antes de qualquer desenvolvimento.', E['rodape'])]

    return h


def main():
    ap = argparse.ArgumentParser(description='Gera o PDF de aprovação da Fase 8')
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--saida', default=os.path.join(raiz, 'caminho-do-dinheiro.pdf'))
    args = ap.parse_args()

    doc = BaseDocTemplate(
        args.saida, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title='O Caminho do Dinheiro',
        author='SIGE · Veks Engenharia',
        subject='Fase 8 — proposta para aprovação do financeiro',
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='corpo')
    doc.addPageTemplates([PageTemplate(id='padrao', frames=[frame],
                                       onPage=_rodape_pagina)])
    doc.build(construir())
    print(f'PDF gerado: {args.saida}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
