"""Gera uma APRESENTAÇÃO (não importação) do orçamento Baia REV10: cada serviço
seguido, logo abaixo, dos insumos vinculados a ele — para visualizar/apresentar.

Reaproveita os MESMOS dados do gerador de importação (INSUMOS, SERVICOS) sem
alterá-lo. Não toca nas planilhas de importação.

Saída:
  - APRESENTACAO_Baia_REV10.xlsx  (Excel formatado, hierárquico)
  - APRESENTACAO_Baia_REV10.pdf   (PDF paisagem, pronto p/ apresentar)
"""
from decimal import Decimal, ROUND_HALF_UP
import importlib.util
import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer, KeepTogether)

# --- carrega os dados do gerador de importação (sem rodá-lo) ---
_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'gerar_importacao_baia_rev10', os.path.join(_HERE, 'gerar_importacao_baia_rev10.py'))
_gi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gi)
INSUMOS, SERVICOS, D = _gi.INSUMOS, _gi.SERVICOS, _gi.D

AZUL = '2F5496'
AZUL_CLARO = 'D9E1F2'
CINZA = 'F2F2F2'
VERDE = '548235'


def money(x):
    """Formata Decimal em R$ pt-BR: 1.234,56"""
    q = Decimal(x).quantize(Decimal('0.01'), ROUND_HALF_UP)
    s = f'{q:,.2f}'  # 1,234.56
    return 'R$ ' + s.replace(',', '@').replace('.', ',').replace('@', '.')


def num(x):
    """Coeficiente/preço sem R$, pt-BR."""
    q = Decimal(x)
    s = f'{q:,.4f}'.rstrip('0').rstrip('.')
    if s in ('', '-0'):
        s = '0'
    return s.replace(',', '@').replace('.', ',').replace('@', '.')


def computar():
    """Retorna lista de serviços, cada um com seus insumos e totais (custo+venda)."""
    blocos = []
    tot_custo = tot_venda = Decimal('0')
    for cod, nome, un, qty_s, comps, bdi in SERVICOS:
        qty = D(qty_s)
        Lmat = Decimal(bdi.get('Lmat', '0.20'))
        Tmo = Decimal('0.13')
        Lmo = Decimal(bdi.get('Lmo', '0.28'))
        linhas = []
        mat = mo = Decimal('0')
        for ins, coef_s, obs in comps:
            tipo, un_ins, preco = INSUMOS[ins]
            coef = D(coef_s); p = D(preco)
            ct = coef * p * qty
            if tipo in ('MATERIAL', 'EQUIPAMENTO'):
                mat += ct
            else:
                mo += ct
            linhas.append({
                'insumo': ins, 'tipo': tipo, 'un': un_ins,
                'coef': coef, 'preco': p, 'custo_total': ct, 'obs': obs,
            })
        custo_total = mat + mo
        venda = mat / (1 - Lmat) + mo / (1 - (Tmo + Lmo))
        cu = (custo_total / qty) if qty else custo_total
        blocos.append({
            'cod': cod, 'nome': nome, 'un': un, 'qty': qty,
            'custo_unit': cu, 'custo_total': custo_total, 'venda': venda,
            'mat': mat, 'mo': mo, 'linhas': linhas,
        })
        tot_custo += custo_total; tot_venda += venda
    return blocos, tot_custo, tot_venda


# ============================== EXCEL ==============================
def build_xlsx(blocos, tot_custo, tot_venda, out):
    wb = Workbook(); ws = wb.active; ws.title = 'Orçamento Baia REV10'
    thin = Side(style='thin', color='BFBFBF')
    borda = Border(left=thin, right=thin, top=thin, bottom=thin)
    COLS = ['', 'Descrição', 'Tipo', 'Un', 'Coef', 'Preço unit.', 'Custo total', 'Observação']
    widths = [8, 42, 11, 6, 11, 15, 16, 50]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 1
    # título
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(r, 1, 'ORÇAMENTO — Baias de Bovinos (Kabod Cabana) · REV10')
    c.font = Font(bold=True, size=15, color='FFFFFF'); c.fill = PatternFill('solid', fgColor=AZUL)
    c.alignment = Alignment(horizontal='center', vertical='center'); ws.row_dimensions[r].height = 26
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    c = ws.cell(r, 1, f'Custo total: {money(tot_custo)}     ·     Venda total (c/ BDI): {money(tot_venda)}'
                      f'     ·     21 serviços')
    c.font = Font(bold=True, size=11, color=AZUL); c.alignment = Alignment(horizontal='center')
    ws.row_dimensions[r].height = 20
    r += 2

    for b in blocos:
        # banner do serviço (merge)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c = ws.cell(r, 1, f'  {b["cod"]}   {b["nome"]}        ({b["un"]} · qtd {num(b["qty"])})'
                          f'        CUSTO {money(b["custo_total"])}   ·   VENDA {money(b["venda"])}')
        c.font = Font(bold=True, size=11, color='FFFFFF'); c.fill = PatternFill('solid', fgColor=AZUL)
        c.alignment = Alignment(horizontal='left', vertical='center'); ws.row_dimensions[r].height = 20
        r += 1
        # cabeçalho de colunas dos insumos
        for i, h in enumerate(COLS, 1):
            cc = ws.cell(r, i, h)
            cc.font = Font(bold=True, size=9, color=AZUL); cc.fill = PatternFill('solid', fgColor=AZUL_CLARO)
            cc.alignment = Alignment(horizontal='center' if i not in (2, 8) else 'left'); cc.border = borda
        r += 1
        # linhas de insumo
        for j, ln in enumerate(b['linhas']):
            vals = ['•', ln['insumo'], ln['tipo'], ln['un'], num(ln['coef']),
                    money(ln['preco']), money(ln['custo_total']), ln['obs']]
            fill = CINZA if j % 2 else 'FFFFFF'
            for i, v in enumerate(vals, 1):
                cc = ws.cell(r, i, v)
                cc.fill = PatternFill('solid', fgColor=fill); cc.border = borda
                cc.font = Font(size=9, color='7030A0' if ln['tipo'] == 'MAO_OBRA' else '000000')
                if i in (5, 6, 7):
                    cc.alignment = Alignment(horizontal='right')
                elif i in (1, 3, 4):
                    cc.alignment = Alignment(horizontal='center')
                else:
                    cc.alignment = Alignment(horizontal='left', wrap_text=(i == 8))
            r += 1
        r += 1  # espaçador

    ws.freeze_panes = 'A4'
    wb.save(out)
    return out


# ============================== PDF ==============================
def build_pdf(blocos, tot_custo, tot_venda, out):
    doc = SimpleDocTemplate(out, pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    ss = getSampleStyleSheet()
    h_title = ParagraphStyle('t', parent=ss['Title'], fontSize=16, textColor=colors.HexColor('#' + AZUL))
    h_sub = ParagraphStyle('s', parent=ss['Normal'], fontSize=10, textColor=colors.HexColor('#' + AZUL),
                           alignment=1, spaceAfter=8)
    svc_style = ParagraphStyle('svc', parent=ss['Normal'], fontSize=10.5, textColor=colors.white,
                               leading=14)
    obs_style = ParagraphStyle('obs', parent=ss['Normal'], fontSize=7.2, textColor=colors.HexColor('#555555'),
                               leading=8.5)
    ins_style = ParagraphStyle('ins', parent=ss['Normal'], fontSize=8, leading=9.5)

    story = [Paragraph('Orçamento — Baias de Bovinos (Kabod Cabana) · REV10', h_title),
             Paragraph(f'Custo total: {money(tot_custo)} &nbsp;·&nbsp; Venda total (c/ BDI): '
                       f'{money(tot_venda)} &nbsp;·&nbsp; 21 serviços', h_sub),
             Spacer(1, 4)]

    col_w = [12 * mm, 70 * mm, 24 * mm, 12 * mm, 20 * mm, 26 * mm, 28 * mm, 50 * mm]
    for b in blocos:
        # faixa do serviço
        faixa = Table([[Paragraph(
            f'<b>{b["cod"]}</b> &nbsp; <b>{b["nome"]}</b> &nbsp;&nbsp;({b["un"]} · qtd {num(b["qty"])}) '
            f'&nbsp;&nbsp;&nbsp; CUSTO <b>{money(b["custo_total"])}</b> &nbsp;·&nbsp; VENDA '
            f'<b>{money(b["venda"])}</b>', svc_style)]], colWidths=[sum(col_w)])
        faixa.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#' + AZUL)),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))

        head = ['', 'Insumo', 'Tipo', 'Un', 'Coef', 'Preço unit.', 'Custo total', 'Observação']
        data = [head]
        for ln in b['linhas']:
            data.append(['•', Paragraph(ln['insumo'], ins_style), ln['tipo'], ln['un'],
                         num(ln['coef']), money(ln['preco']), money(ln['custo_total']),
                         Paragraph(ln['obs'], obs_style)])
        t = Table(data, colWidths=col_w, repeatRows=1)
        sty = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#' + AZUL_CLARO)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#' + AZUL)),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BFBFBF')),
            ('ALIGN', (4, 1), (6, -1), 'RIGHT'), ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (3, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]
        for i, ln in enumerate(b['linhas'], 1):
            if ln['tipo'] == 'MAO_OBRA':
                sty.append(('TEXTCOLOR', (1, i), (1, i), colors.HexColor('#7030A0')))
            if i % 2 == 0:
                sty.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F2F2F2')))
        t.setStyle(TableStyle(sty))

        # mantém faixa + tabela juntas na mesma página
        story.append(KeepTogether([faixa, t, Spacer(1, 7)]))

    doc.build(story)
    return out


if __name__ == '__main__':
    blocos, tc, tv = computar()
    x = build_xlsx(blocos, tc, tv, 'APRESENTACAO_Baia_REV10.xlsx')
    p = build_pdf(blocos, tc, tv, 'APRESENTACAO_Baia_REV10.pdf')
    print(f'gerado: {x}')
    print(f'gerado: {p}')
    print(f'\n{len(blocos)} serviços · custo {money(tc)} · venda {money(tv)}')
