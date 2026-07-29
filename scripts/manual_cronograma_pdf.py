#!/usr/bin/env python3
"""Gera o manual do cronograma editável — `static/docs/manual-cronograma.pdf`.

Fase 5 do editor v2 (spec §7): o PDF é ESTÁTICO e versionado no repositório;
este script existe para regenerá-lo quando a ferramenta mudar. As capturas
vêm de `docs/img/manual-cronograma/` (geradas por
`scripts/manual_cronograma_capturas.py` — rode-o antes se a UI mudou).

Uso:
    python scripts/manual_cronograma_capturas.py   # se a UI mudou
    python scripts/manual_cronograma_pdf.py
"""
from __future__ import annotations

import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMGS = os.path.join(RAIZ, 'docs', 'img', 'manual-cronograma')
SAIDA = os.path.join(RAIZ, 'static', 'docs', 'manual-cronograma.pdf')

AZUL = colors.HexColor('#1d4ed8')
CINZA = colors.HexColor('#475569')
CINZA_CLARO = colors.HexColor('#e2e8f0')

LARGURA_UTIL = A4[0] - 4 * cm  # margens de 2 cm

est_titulo = ParagraphStyle(
    'titulo', fontName='Helvetica-Bold', fontSize=26, leading=32,
    textColor=AZUL, spaceAfter=6)
est_subtitulo = ParagraphStyle(
    'subtitulo', fontName='Helvetica', fontSize=13, leading=18,
    textColor=CINZA, spaceAfter=18)
est_h1 = ParagraphStyle(
    'h1', fontName='Helvetica-Bold', fontSize=16, leading=20,
    textColor=AZUL, spaceBefore=18, spaceAfter=8)
est_corpo = ParagraphStyle(
    'corpo', fontName='Helvetica', fontSize=10.5, leading=15,
    spaceAfter=8)
est_item = ParagraphStyle(
    'item', parent=est_corpo, leftIndent=14, bulletIndent=4, spaceAfter=4)
est_legenda = ParagraphStyle(
    'legenda', fontName='Helvetica-Oblique', fontSize=8.5, leading=11,
    textColor=CINZA, spaceBefore=3, spaceAfter=12, alignment=1)


def _img(nome: str, largura: float) -> Image:
    """Imagem com moldura implícita, escalada por largura mantendo proporção."""
    caminho = os.path.join(IMGS, nome)
    iw, ih = ImageReader(caminho).getSize()
    return Image(caminho, width=largura, height=largura * ih / iw)


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, 'Manual do Cronograma — SIGE')
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f'{doc.page}')
    canvas.restoreState()


def P(texto: str) -> Paragraph:
    return Paragraph(texto, est_corpo)


def B(texto: str) -> Paragraph:
    return Paragraph(f'• {texto}', est_item)


def main() -> None:
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    doc = SimpleDocTemplate(
        SAIDA, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title='Manual do Cronograma Editável',
        author='SIGE')

    fl = []

    # ── Capa / visão geral ──
    fl.append(Paragraph('Manual do Cronograma Editável', est_titulo))
    fl.append(Paragraph(
        'Edição estilo MS Project: grade tipo planilha, predecessoras com '
        'tipos de vínculo, recálculo automático, caminho crítico, linha de '
        f'base e desfazer/refazer. — {date.today().strftime("%d/%m/%Y")}',
        est_subtitulo))
    fl.append(P(
        'A página <b>Cronograma</b> de cada obra (menu Obras → obra → '
        'Cronograma) reúne a grade de tarefas à esquerda e o gráfico de '
        'Gantt à direita. Toda edição feita na grade é salva imediatamente '
        'e as datas das tarefas dependentes são recalculadas na hora — não '
        'existe botão "salvar".'))
    fl.append(_img('01-visao-geral.png', LARGURA_UTIL))
    fl.append(Paragraph(
        'Visão geral: grade editável, indicadores e Gantt com barras de '
        'progresso.', est_legenda))
    fl.append(P(
        'A barra de ações no topo concentra os comandos do editor: nova '
        'tarefa, linha de base, desfazer/refazer, recuar/desrecuar, inserir '
        'e excluir linha, além do recálculo manual.'))
    fl.append(_img('02-toolbar.png', LARGURA_UTIL))
    fl.append(Paragraph('Barra de ações da página do cronograma.',
                        est_legenda))
    fl.append(PageBreak())

    # ── Grade ──
    fl.append(Paragraph('1. Edição na grade', est_h1))
    fl.append(P(
        'A grade funciona como uma planilha: clique numa célula para '
        'selecioná-la e navegue com as setas do teclado. As colunas '
        'editáveis são Nome, Duração, Início, Predecessoras, Quantidade/'
        'Unidade e Responsável.'))
    fl.append(B('<b>Enter</b> ou <b>F2</b> abre a edição da célula '
                'selecionada; digitar qualquer caractere também abre a '
                'edição, já substituindo o conteúdo (como no Excel).'))
    fl.append(B('Dentro do editor, <b>Tab</b> confirma e vai para a célula '
                'seguinte; <b>Enter</b> confirma e desce uma linha; '
                '<b>Esc</b> cancela sem salvar.'))
    fl.append(B('Os botões da barra (ou o menu da linha) inserem uma linha '
                'acima/abaixo da selecionada e excluem a linha. A exclusão '
                'é reversível com Desfazer — os apontamentos de RDO da '
                'tarefa são preservados.'))
    fl.append(B('<b>Clique com o botão direito</b> em qualquer linha para o '
                'menu com todas essas ações. Pelo teclado: <b>Insert</b> '
                'insere abaixo, <b>Shift+Insert</b> acima e <b>Alt+Insert</b> '
                'cria uma subtarefa já dentro da linha selecionada.'))
    fl.append(B('<b>Alt+Shift+→</b> recua a tarefa (ela vira subtarefa da '
                'linha de cima); <b>Alt+Shift+←</b> desrecua (sobe um '
                'nível). Tarefas-resumo têm datas e duração calculadas a '
                'partir das subtarefas e não são editáveis diretamente.'))
    fl.append(B('Para reorganizar com o mouse, arraste a linha pela alça à '
                'esquerda: soltar <b>entre</b> duas linhas reordena; soltar '
                '<b>sobre</b> uma linha (que acende) faz a arrastada virar '
                'subtarefa dela. Os botões de expandir/recolher tudo abrem e '
                'fecham a árvore inteira de uma vez.'))
    fl.append(B('Uma tarefa que já foi iniciada, ou que tem vínculos de '
                'predecessora, não pode virar tarefa-resumo — o sistema '
                'recusa a operação e explica o motivo.'))
    fl.append(B('Tarefa que já tem avanço apontado em RDO não permite '
                'alterar a data de início — ela já começou.'))
    fl.append(KeepTogether([
        _img('03-grade-edicao.png', 11 * cm),
        Paragraph(
            'Célula de nome em edição (F2) com a linha selecionada '
            'destacada.', est_legenda),
    ]))
    fl.append(PageBreak())

    # ── Predecessoras ──
    fl.append(Paragraph('2. Predecessoras e tipos de vínculo', est_h1))
    fl.append(P(
        'A coluna <b>Pred.</b> usa o formato do MS Project: o número da '
        'linha da predecessora, o tipo de vínculo e uma latência (lag) '
        'opcional em dias úteis. Vários vínculos são separados por ponto e '
        'vírgula. Exemplos: <b>7</b> (término→início simples), '
        '<b>5II+2</b> (início→início com 2 dias de espera), '
        '<b>15TI+1;13TT+2</b> (dois vínculos na mesma tarefa).'))
    tabela_tipos = Table(
        [['Tipo', 'Significado', 'A sucessora...'],
         ['TI', 'Término → Início (padrão)',
          'começa depois que a predecessora termina'],
         ['II', 'Início → Início',
          'começa junto com o início da predecessora'],
         ['TT', 'Término → Término',
          'termina junto com o término da predecessora'],
         ['IT', 'Início → Término',
          'termina quando a predecessora começa']],
        colWidths=[1.5 * cm, 5.5 * cm, LARGURA_UTIL - 7 * cm])
    tabela_tipos.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('BACKGROUND', (0, 0), (-1, 0), CINZA_CLARO),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    fl.append(tabela_tipos)
    fl.append(Spacer(0, 8))
    fl.append(P(
        'O lag pode ser negativo para antecipar (ex.: <b>7TI-2</b> começa '
        '2 dias úteis antes do término da predecessora). Apagar o conteúdo '
        'da célula remove os vínculos. Vínculos que formariam um ciclo são '
        'recusados com uma mensagem explicando o caminho do ciclo.'))
    fl.append(KeepTogether([
        _img('04-predecessoras.png', 11 * cm),
        Paragraph(
            'Célula de predecessoras em edição com dois vínculos: '
            '15TI+1;13TT+2.', est_legenda),
    ]))
    fl.append(PageBreak())

    # ── Recálculo ──
    fl.append(Paragraph('3. Recálculo automático', est_h1))
    fl.append(P(
        'Ao editar duração, início ou predecessoras, o sistema recalcula '
        'em cascata as datas de todas as tarefas afetadas, imediatamente e '
        'sem pedir confirmação. O cálculo usa <b>dias úteis</b> (segunda a '
        'sexta): duração de 5 dias iniciada numa quinta termina na '
        'quarta seguinte.'))
    fl.append(B('<b>Tarefas ancoradas:</b> tarefa com avanço real apontado '
                'em RDO não é movida pelo recálculo — mas continua '
                'empurrando as sucessoras. O plano se ajusta ao que já '
                'aconteceu em campo, nunca o contrário.'))
    fl.append(B('Tarefa sem predecessora e sem avanço mantém o início '
                'digitado por você.'))
    fl.append(B('O botão <b>Recalcular</b> refaz a obra inteira — útil '
                'após muitas mudanças ou importação de arquivo.'))

    # ── Caminho crítico ──
    fl.append(Paragraph('4. Caminho crítico', est_h1))
    fl.append(P(
        'As tarefas sem folga — aquelas em que qualquer atraso adia o fim '
        'da obra — aparecem com a barra <b>vermelha</b> no Gantt. Tarefas '
        'com folga permanecem azuis (ou verdes quando concluídas). Use o '
        'caminho crítico para decidir onde colocar atenção e recursos.'))

    # ── Linha de base ──
    fl.append(Paragraph('5. Linha de base (planejado × real)', est_h1))
    fl.append(P(
        'O botão <b>Linha de base</b> congela as datas planejadas de todas '
        'as tarefas no momento em que você salva. A partir daí o Gantt '
        'mostra uma <b>barra cinza</b> sob cada barra atual (o plano '
        'congelado) e a grade ganha a coluna <b>Desvio</b> — a diferença, '
        'em dias, entre o término atual e o término congelado. Desvio '
        'positivo (vermelho) significa atraso em relação ao plano.'))
    fl.append(B('Só existe <b>uma linha de base ativa</b> por obra, mas o '
                'histórico fica guardado: salvar de novo cria outra e a '
                'torna ativa; as anteriores podem ser reativadas ou '
                'excluídas na janela do botão.'))
    tbl_imgs = Table(
        [[_img('05-gantt-critico.png', 6.8 * cm),
          _img('06-desvio.png', 9.6 * cm)]],
        colWidths=[7.2 * cm, LARGURA_UTIL - 7.2 * cm])
    tbl_imgs.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    fl.append(KeepTogether([
        tbl_imgs,
        Paragraph(
            'À esquerda: Gantt com barras vermelhas (caminho crítico) e '
            'cinzas (linha de base). À direita: coluna Desvio em vermelho '
            'nas tarefas atrasadas.', est_legenda),
    ]))

    # ── Desfazer ──
    fl.append(Paragraph('6. Desfazer e refazer', est_h1))
    fl.append(P(
        '<b>Ctrl+Z</b> desfaz a última edição e <b>Ctrl+Y</b> (ou '
        'Ctrl+Shift+Z) refaz — os botões de seta na barra de ações fazem o '
        'mesmo. Cada usuário tem a sua própria pilha de ações por obra.'))
    fl.append(B('O desfazer reverte exatamente os campos alterados pela '
                'ação — incluindo o recálculo em cascata que ela causou.'))
    fl.append(B('O <b>percentual realizado</b> vem dos apontamentos de RDO '
                'e nunca é alterado pelo desfazer.'))
    fl.append(B('Desfazer uma exclusão restaura a tarefa com todos os '
                'vínculos e apontamentos.'))

    # ── Atalhos ──
    fl.append(Paragraph('7. Resumo dos atalhos de teclado', est_h1))
    atalhos = [
        ['Atalho', 'Ação'],
        ['Setas', 'Navegar entre as células da grade'],
        ['Tab / Shift+Tab', 'Célula seguinte / anterior (com quebra de '
                            'linha, como numa planilha)'],
        ['Enter ou F2', 'Editar a célula selecionada'],
        ['Qualquer caractere', 'Editar já substituindo o conteúdo'],
        ['Enter (editando)', 'Confirmar e descer uma linha'],
        ['Tab (editando)', 'Confirmar e ir para a célula seguinte'],
        ['Esc', 'Cancelar a edição / limpar a seleção'],
        ['Insert', 'Inserir linha abaixo da selecionada'],
        ['Shift+Insert', 'Inserir linha acima da selecionada'],
        ['Alt+Insert', 'Nova subtarefa dentro da selecionada'],
        ['Ctrl+Shift+Enter', 'Inserir linha abaixo (teclado sem a tecla '
                             'Insert)'],
        ['Alt+Shift+→', 'Recuar (virar subtarefa da linha de cima)'],
        ['Alt+Shift+←', 'Desrecuar (subir um nível na hierarquia)'],
        ['Shift+F10 ou Menu', 'Abrir o menu de contexto da linha'],
        ['Ctrl+Z', 'Desfazer'],
        ['Ctrl+Y ou Ctrl+Shift+Z', 'Refazer'],
    ]
    tabela_atalhos = Table(atalhos, colWidths=[5.5 * cm,
                                               LARGURA_UTIL - 5.5 * cm])
    tabela_atalhos.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('BACKGROUND', (0, 0), (-1, 0), CINZA_CLARO),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    fl.append(tabela_atalhos)

    doc.build(fl, onFirstPage=_rodape, onLaterPages=_rodape)
    kb = os.path.getsize(SAIDA) / 1024
    print(f'[OK] {SAIDA} gerado ({kb:.0f} KB)')


if __name__ == '__main__':
    main()
