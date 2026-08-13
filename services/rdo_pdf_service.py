"""Geração de PDF do RDO (Relatório Diário de Obra).

Server-side, alinhado ao DESIGN.md (Bootstrap primary #0d6efd, neutros
tintados, layout denso e técnico). Headers de tabela cinzas (table-light),
faixa de cabeçalho compacta com KPI de progresso geral, omissão de linhas
vazias, paginação no rodapé.
"""
import base64
import logging
import re
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
    Image,
)

from app import db
from models import (
    RDO, RDOMaoObra, RDOServicoSubatividade, RDOEquipamento, RDOOcorrencia,
    RDOApontamentoCronograma, RDOFoto, ConfiguracaoEmpresa,
    EngenheiroResponsavel, Funcionario, TarefaCronograma,
)
from utils.rdo_horas import normalizar_horas_funcionario

logger = logging.getLogger('rdo.pdf')


# ─── Paleta SIGE (DESIGN.md) ────────────────────────────────────────────────
PRIMARY = colors.HexColor('#0d6efd')
PRIMARY_DARK = colors.HexColor('#0a58ca')
INK = colors.HexColor('#212529')
MUTED = colors.HexColor('#6c757d')
BORDER = colors.HexColor('#dee2e6')
TABLE_HEAD = colors.HexColor('#f8f9fa')
TABLE_ZEBRA = colors.HexColor('#fbfbfc')


def _fmt_horas(h):
    try:
        return f"{float(h or 0):.1f}h"
    except (TypeError, ValueError):
        return "0.0h"


def _fmt_pct(v):
    try:
        return f"{float(v or 0):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


_DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


def _fmt_data_br(d):
    if not d:
        return '—'
    try:
        return f"{_DIAS_SEMANA[d.weekday()]}, {d.strftime('%d/%m/%Y')}"
    except Exception:
        return d.strftime('%d/%m/%Y')


def _logo_image(config, max_w=110, max_h=42):
    """Decodifica logo_pdf_base64 (preferencial) ou logo_base64. Mantém
    aspect ratio dentro de max_w × max_h pontos."""
    if not config:
        return None
    raw = (config.logo_pdf_base64 or '').strip() or (config.logo_base64 or '').strip()
    if not raw:
        return None
    # remove prefixo data:image/...;base64,
    raw = re.sub(r'^data:image/[^;]+;base64,', '', raw)
    try:
        data = base64.b64decode(raw)
        reader = ImageReader(BytesIO(data))
        iw, ih = reader.getSize()
        if not iw or not ih:
            return None
        ratio = min(max_w / iw, max_h / ih)
        return Image(BytesIO(data), width=iw * ratio, height=ih * ratio)
    except Exception:
        return None


def _foto_image(foto, max_w=255, max_h=160):
    """Renderiza uma RDOFoto em Image. Prefere a versão otimizada
    (1200px) → thumbnail (300px) → original → caminho_arquivo no disco.
    Mantém aspect ratio."""
    raw = None
    for attr in ('imagem_otimizada_base64', 'thumbnail_base64', 'imagem_original_base64'):
        val = (getattr(foto, attr, None) or '').strip()
        if val:
            raw = val
            break
    data = None
    if raw:
        raw = re.sub(r'^data:image/[^;]+;base64,', '', raw)
        try:
            data = base64.b64decode(raw)
        except Exception:
            data = None
    if not data and foto.caminho_arquivo:
        # Fallback: ler do disco (caminho relativo a static/)
        import os
        candidates = [
            foto.caminho_arquivo,
            os.path.join('static', foto.caminho_arquivo),
            os.path.join('/home/runner/workspace/static', foto.caminho_arquivo.lstrip('/')),
        ]
        for path in candidates:
            try:
                if os.path.exists(path):
                    with open(path, 'rb') as fp:
                        data = fp.read()
                    break
            except Exception:
                continue
    if not data:
        return None
    try:
        reader = ImageReader(BytesIO(data))
        iw, ih = reader.getSize()
        if not iw or not ih:
            return None
        ratio = min(max_w / iw, max_h / ih)
        return Image(BytesIO(data), width=iw * ratio, height=ih * ratio)
    except Exception:
        return None


def _data_bar(pct, width=70, height=4):
    """Mini barra de progresso inline (estilo Excel data bar). Subtle: fundo
    cinza claro com barra primary, sem texto."""
    try:
        p = max(0.0, min(100.0, float(pct or 0)))
    except (TypeError, ValueError):
        p = 0.0
    fill = max(1.0, width * p / 100.0) if p > 0 else 0
    bar = Table([['', '']], colWidths=[fill, max(0.1, width - fill)],
                rowHeights=[height], hAlign='LEFT')
    bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), PRIMARY),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#e9ecef')),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return bar


def _normalizar_horas(mao_obra_rows):
    """Distribui jornada-base entre N atividades por funcionário. Sem isso,
    RDOs antigos onde o apontador digitou a jornada inteira em cada
    subatividade inflam o total (8h × 5 subs = 40h por funcionário)."""
    entradas, pesos = [], {}
    for mo in mao_obra_rows:
        horas = float(mo.horas_trabalhadas or 0)
        if horas <= 0 or not mo.funcionario_id:
            continue
        key = ('sub', mo.subatividade_id) if mo.subatividade_id else ('row', mo.id)
        entradas.append((mo.funcionario_id, key, horas))
        peso = getattr(mo, 'peso_distribuicao', None)
        if peso is not None:
            pesos[(mo.funcionario_id, key)] = peso
    norm = normalizar_horas_funcionario(entradas, pesos=pesos) if pesos else normalizar_horas_funcionario(entradas)
    return {(e[0], e[1]): e[2] for e in norm}


def _progresso_geral(rdo):
    """Progresso da obra no PDF — as mesmas duas funções que a TELA usa (A19).

    ## Por que este é o call-site mais pesado dos sete

    Não porque mova dinheiro — nenhum da família V1 move —, mas porque vira
    **papel assinado**: este PDF é o documento por trás do ato de ciência do
    cliente. Um número aqui diferente do que o apontador vê na tela do mesmo RDO
    é uma divergência que chega ao cliente por escrito.

    ## O que mudou, e por que o `except` sumiu

    Antes: predicado V2 próprio (sem `ativa`, sem `is_cliente`, sem
    `is_v2_active()`) e uma reimplementação da fórmula V1 agrupando só por
    `nome_subatividade`. Um `try/except Exception: pass` em volta **engolia a
    falha e caía em V1 em silêncio** — e PDF que mente o percentual é pior que
    PDF que falha. Agora a exceção sobe.

    O parâmetro `subatividades_count` saiu: ele decidia ramo, e
    `progresso_v1_acumulado` já devolve 0.0 quando não há chave.
    """
    from utils.cronograma_engine import (calcular_progresso_geral_obra_v2,
                                         obra_em_modo_v2,
                                         progresso_v1_acumulado)

    admin_id = rdo.admin_id or (rdo.obra.admin_id if rdo.obra else None)

    if obra_em_modo_v2(rdo.obra_id, admin_id):
        res = calcular_progresso_geral_obra_v2(
            rdo.obra_id, rdo.data_relatorio, admin_id)
        return float(res.get('progresso_geral_pct') or 0)

    return progresso_v1_acumulado(rdo.obra_id, admin_id, rdo.data_relatorio)


# ─── Styles ─────────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('t', parent=base['Normal'],
                                fontName='Helvetica-Bold', fontSize=10,
                                textColor=MUTED, leading=12,
                                letterSpacing=1.2),
        'h1': ParagraphStyle('h1', parent=base['Normal'],
                             fontName='Helvetica-Bold', fontSize=18,
                             textColor=INK, leading=22),
        'subtle': ParagraphStyle('sub', parent=base['Normal'],
                                 fontName='Helvetica', fontSize=8.5,
                                 textColor=MUTED, leading=11),
        'kpi_label': ParagraphStyle('kl', parent=base['Normal'],
                                    fontName='Helvetica-Bold', fontSize=7,
                                    textColor=MUTED, leading=9,
                                    spaceAfter=1),
        'kpi_value': ParagraphStyle('kv', parent=base['Normal'],
                                    fontName='Helvetica-Bold', fontSize=11,
                                    textColor=INK, leading=13),
        'kpi_value_primary': ParagraphStyle('kvp', parent=base['Normal'],
                                            fontName='Helvetica-Bold', fontSize=15,
                                            textColor=PRIMARY, leading=17),
        'section': ParagraphStyle('s', parent=base['Normal'],
                                  fontName='Helvetica-Bold', fontSize=8.5,
                                  textColor=PRIMARY_DARK, leading=10,
                                  spaceBefore=6, spaceAfter=3,
                                  letterSpacing=1.4),
        'body': ParagraphStyle('b', parent=base['Normal'],
                               fontName='Helvetica', fontSize=8.8,
                               textColor=INK, leading=12),
        'body_muted': ParagraphStyle('bm', parent=base['Normal'],
                                     fontName='Helvetica', fontSize=8,
                                     textColor=MUTED, leading=11),
        'cell': ParagraphStyle('c', parent=base['Normal'],
                               fontName='Helvetica', fontSize=8.3,
                               textColor=INK, leading=11),
        'cell_b': ParagraphStyle('cb', parent=base['Normal'],
                                 fontName='Helvetica-Bold', fontSize=8.3,
                                 textColor=INK, leading=11),
        # Faixa de grupo dos apontamentos ("Baias › Galpão B › Fundação"):
        # menor e mais clara que a linha de dado, para separar sem competir.
        'cell_group': ParagraphStyle('cg', parent=base['Normal'],
                                     fontName='Helvetica-Bold', fontSize=7.2,
                                     textColor=MUTED, leading=9.5),
        'mono': ParagraphStyle('mono', parent=base['Normal'],
                               fontName='Courier', fontSize=8.3,
                               textColor=INK, leading=11, alignment=2),
        'mono_b': ParagraphStyle('monob', parent=base['Normal'],
                                 fontName='Courier-Bold', fontSize=8.3,
                                 textColor=INK, leading=11, alignment=2),
        'badge_lbl': ParagraphStyle('bl', parent=base['Normal'],
                                    fontName='Helvetica-Bold', fontSize=7.5,
                                    textColor=colors.white, leading=9,
                                    alignment=1, letterSpacing=0.8),
    }


def _section_rule(label, styles):
    """Cabeçalho de seção compacto: 1 linha com filete inferior em PRIMARY.

    hAlign='LEFT' impede o ReportLab de centralizar (ou encolher) a tabela
    quando ela está dentro de um KeepTogether ao lado de outro flowable
    mais estreito (ex.: grid de fotos com hAlign='LEFT')."""
    p = Paragraph(label.upper(), styles['section'])
    wrap = Table([[p]], colWidths=[565], hAlign='LEFT')
    wrap.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.8, PRIMARY),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return wrap


def _table_style(num_cols, right_align_from=1):
    """Estilo de tabela neutro (table-light): header cinza com texto escuro,
    linhas zebradas suaves, grid mínimo."""
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEAD),
        ('TEXTCOLOR', (0, 0), (-1, 0), INK),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.8),
        ('FONTSIZE', (0, 1), (-1, -1), 8.3),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('TEXTCOLOR', (0, 1), (-1, -1), INK),
        ('LINEABOVE', (0, 0), (-1, 0), 0.4, BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, PRIMARY),
        ('LINEBELOW', (0, 1), (-1, -1), 0.3, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TABLE_ZEBRA]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LETTERSPACING', (0, 0), (-1, 0), 0.6),
    ]
    if right_align_from is not None and right_align_from < num_cols:
        cmds.append(('ALIGN', (right_align_from, 0), (-1, -1), 'RIGHT'))
    return TableStyle(cmds)


def _status_chip(label):
    """Chip pequeno para o status do RDO (semântico, sem cor extra)."""
    color_map = {
        'Finalizado': colors.HexColor('#198754'),
        'Aprovado': PRIMARY,
        'Rascunho': MUTED,
        'Em Andamento': colors.HexColor('#ffc107'),
    }
    bg = color_map.get(label or '', MUTED)
    t = Table([[label or '—']], colWidths=[70], rowHeights=[14], hAlign='RIGHT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [3, 3, 3, 3]),
    ]))
    return t


# ─── Paginação ──────────────────────────────────────────────────────────────
class _Footer:
    def __init__(self, empresa_nome, rdo_numero):
        self.empresa_nome = empresa_nome
        self.rdo_numero = rdo_numero
        self.gerado_em = datetime.now().strftime('%d/%m/%Y %H:%M')

    def __call__(self, canv, doc):
        canv.saveState()
        w, _ = A4
        y = 10 * mm
        canv.setStrokeColor(BORDER)
        canv.setLineWidth(0.4)
        canv.line(15 * mm, y + 6, w - 15 * mm, y + 6)
        canv.setFont('Helvetica', 7)
        canv.setFillColor(MUTED)
        # `empresa_nome` vazio é o recibo do portal do cliente, que não leva a
        # marca da construtora — sem o filtro sobraria um " · " órfão na frente.
        partes = [p for p in (self.empresa_nome, self.rdo_numero,
                              f"Emitido em {self.gerado_em}") if p]
        canv.drawString(15 * mm, y, "  ·  ".join(partes))
        canv.drawRightString(w - 15 * mm, y, f"Página {doc.page}")
        canv.restoreState()


# ─── Header bar (faixa superior compacta) ───────────────────────────────────
def _header_bar(rdo, progresso_geral, empresa_nome, config, styles):
    obra_nome = rdo.obra.nome if rdo.obra else '—'
    cliente = getattr(rdo.obra, 'cliente_nome_efetivo', None) or '—'
    data_str = _fmt_data_br(rdo.data_relatorio)

    logo_img = _logo_image(config)
    contato = ' · '.join([p for p in [
        getattr(config, 'cnpj', None),
        getattr(config, 'telefone', None),
        getattr(config, 'email', None),
    ] if p])

    title_block = [
        [Paragraph("RELATÓRIO DIÁRIO DE OBRA", styles['title'])],
        [Paragraph(obra_nome, styles['h1'])],
        [Paragraph(
            f"<b>{empresa_nome}</b>  ·  Cliente: {cliente}"
            + (f'<br/><font color="#6c757d" size="7.5">{contato}</font>' if contato else ''),
            styles['subtle'])],
    ]
    if logo_img:
        title_tbl = Table(
            [[logo_img, Table(title_block, colWidths=[230])]],
            colWidths=[60, 230],
        )
        title_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('VALIGN', (1, 0), (1, 0), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 10),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        # Style do bloco interno
        inner = title_tbl._cellvalues[0][1]
        inner.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        left_tbl = title_tbl
    else:
        left_tbl = Table(title_block, colWidths=[290])
        left_tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

    def kpi_cell(label, value, primary=False, big=False):
        size = 15 if primary else (10 if big else 11)
        return Paragraph(
            f'<font name="Helvetica-Bold" size="6.8" color="#6c757d">'
            f'{label.upper()}</font><br/>'
            f'<font name="Helvetica-Bold" size="{size}" '
            f'color="{"#0d6efd" if primary else "#212529"}">{value}</font>',
            ParagraphStyle('kpi_inline', parent=styles['body'],
                           leading=18, spaceBefore=0, spaceAfter=0),
        )

    kpi_row = Table([[
        kpi_cell('RDO Nº', rdo.numero_rdo or '—', big=True),
        kpi_cell('Data', data_str, big=True),
        kpi_cell('Progresso geral', _fmt_pct(progresso_geral), primary=True),
    ]], colWidths=[105, 80, 90])
    kpi_row.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    bar = Table([[left_tbl, kpi_row]], colWidths=[290, 275])
    bar.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 1.4, PRIMARY),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return bar


def _meta_row(rdo, styles):
    """Linha discreta com Local / Status / Criado por."""
    criado_por = rdo.criado_por.nome if rdo.criado_por else 'Sistema'
    items = [
        ('Local', rdo.local or 'Campo'),
        ('Criado por', criado_por),
    ]
    cells = []
    for label, value in items:
        cells.append(Paragraph(
            f'<font color="#6c757d">{label.upper()}</font>  '
            f'<font color="#212529"><b>{value}</b></font>',
            styles['body_muted'],
        ))
    cells.append(_status_chip(rdo.status))
    row = Table([cells], colWidths=[180, 230, 80])
    row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return row


# ─── Builder principal ─────────────────────────────────────────────────────
def gerar_pdf_rdo(rdo):
    """Gera bytes de um PDF estruturado para o RDO informado.

    Args:
        rdo: instância de ``models.RDO`` (com obra acessível por relacionamento).

    Returns:
        bytes do PDF, ou ``None`` se ``rdo`` for inválido.
    """
    if not rdo or not rdo.obra:
        return None

    admin_id = rdo.admin_id or rdo.obra.admin_id
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    empresa_nome = config.nome_empresa if config else 'Empresa'

    subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).order_by(
        RDOServicoSubatividade.ordem_execucao.asc().nulls_last(),
        RDOServicoSubatividade.id.asc(),
    ).all()
    mao_obra_rows = (
        RDOMaoObra.query.filter_by(rdo_id=rdo.id)
        .join(Funcionario, RDOMaoObra.funcionario_id == Funcionario.id)
        .order_by(Funcionario.nome)
        .all()
    )
    equipamentos = RDOEquipamento.query.filter_by(rdo_id=rdo.id).all()
    ocorrencias = RDOOcorrencia.query.filter_by(rdo_id=rdo.id).all()
    apontamentos_v2 = (
        db.session.query(RDOApontamentoCronograma, TarefaCronograma)
        .outerjoin(TarefaCronograma, RDOApontamentoCronograma.tarefa_cronograma_id == TarefaCronograma.id)
        .filter(RDOApontamentoCronograma.rdo_id == rdo.id)
        .all()
    )

    # V1 xor V2 — se há subatividades, prevalecem; senão usa apontamentos
    # do cronograma. Evita duplicação visual quando o RDO híbrido grava as
    # mesmas atividades nas duas tabelas.
    usar_v1 = bool(subatividades)
    mostrar_v2 = bool(apontamentos_v2) and not usar_v1

    horas_map = _normalizar_horas(mao_obra_rows)
    horas_por_funcionario = {}
    funcoes_por_funcionario = {}
    for mo in mao_obra_rows:
        if not mo.funcionario_id:
            continue
        key = ('sub', mo.subatividade_id) if mo.subatividade_id else ('row', mo.id)
        h = horas_map.get((mo.funcionario_id, key), 0.0)
        horas_por_funcionario[mo.funcionario_id] = horas_por_funcionario.get(mo.funcionario_id, 0.0) + h
        funcoes_por_funcionario.setdefault(mo.funcionario_id, mo.funcao_exercida or '—')

    progresso_geral = _progresso_geral(rdo)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"RDO {rdo.numero_rdo or rdo.id}",
        author=empresa_nome,
    )
    styles = _build_styles()
    elements = []

    elements.append(_header_bar(rdo, progresso_geral, empresa_nome, config, styles))
    elements.append(Spacer(1, 4))
    elements.append(_meta_row(rdo, styles))
    elements.append(Spacer(1, 6))

    # ── Condições Climáticas (omite linhas vazias) ──
    clima_pairs = [
        ('Clima', rdo.clima_geral),
        ('Temperatura', rdo.temperatura_media),
        ('Vento', rdo.vento_velocidade),
        ('Precipitação', rdo.precipitacao),
        ('Condições', rdo.condicoes_trabalho),
        ('Umidade', f"{rdo.umidade_relativa}%" if rdo.umidade_relativa is not None else None),
    ]
    clima_pairs = [(k, v) for k, v in clima_pairs if v]
    if clima_pairs:
        elements.append(_section_rule('Condições Climáticas', styles))
        items = []
        for k, v in clima_pairs:
            items.append(Paragraph(
                f'<font color="#6c757d">{k}</font>  <font color="#212529"><b>{v}</b></font>',
                styles['body'],
            ))
        cols = 3
        rows_data = [items[i:i + cols] for i in range(0, len(items), cols)]
        for row in rows_data:
            while len(row) < cols:
                row.append('')
        clima_tbl = Table(rows_data, colWidths=[185] * cols)
        clima_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(clima_tbl)
        if rdo.observacoes_climaticas:
            elements.append(Spacer(1, 2))
            elements.append(Paragraph(
                f'<font color="#6c757d">Obs.</font>  {rdo.observacoes_climaticas}',
                styles['body_muted'],
            ))

    # ── Equipe ──
    if mao_obra_rows:
        elements.append(_section_rule('Equipe', styles))
        equipe_data = [['Funcionário', 'Função', 'Horas']]
        vistos = set()
        total_horas = 0.0
        for mo in mao_obra_rows:
            if not mo.funcionario_id or mo.funcionario_id in vistos:
                continue
            vistos.add(mo.funcionario_id)
            nome = mo.funcionario.nome if mo.funcionario else f'#{mo.funcionario_id}'
            h = horas_por_funcionario.get(mo.funcionario_id, 0)
            total_horas += h
            equipe_data.append([
                Paragraph(nome, styles['cell']),
                Paragraph(funcoes_por_funcionario.get(mo.funcionario_id, '—'), styles['cell']),
                Paragraph(_fmt_horas(h), styles['mono']),
            ])
        equipe_data.append([
            Paragraph('<b>Total</b>', styles['cell_b']),
            f'{len(vistos)} funcionários',
            Paragraph(f'{total_horas:.1f}h', styles['mono_b']),
        ])
        equipe_tbl = Table(equipe_data, colWidths=[300, 175, 90], repeatRows=1)
        style = _table_style(3, right_align_from=2)
        style.add('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
        style.add('BACKGROUND', (0, -1), (-1, -1), TABLE_HEAD)
        style.add('LINEABOVE', (0, -1), (-1, -1), 0.6, BORDER)
        equipe_tbl.setStyle(style)
        elements.append(equipe_tbl)

    # ── Atividades (V1 xor V2 — evita duplicação visual) ──
    if usar_v1:
        elements.append(_section_rule('Atividades Executadas', styles))
        data = [['Subatividade', 'Progresso', '% Ant.', '% Atual', 'Δ Dia']]
        for s in subatividades:
            ant = float(s.percentual_anterior or 0)
            atual = float(s.percentual_conclusao or 0)
            inc = float(s.incremento_dia or 0)
            data.append([
                Paragraph(s.nome_subatividade or '—', styles['cell']),
                _data_bar(atual, width=80, height=4),
                Paragraph(_fmt_pct(ant), styles['mono']),
                Paragraph(_fmt_pct(atual), styles['mono_b']),
                Paragraph(_fmt_pct(inc), styles['mono']),
            ])
        tbl = Table(data, colWidths=[225, 95, 65, 70, 60], repeatRows=1)
        style = _table_style(5, right_align_from=2)
        style.add('ALIGN', (1, 1), (1, -1), 'LEFT')
        style.add('VALIGN', (1, 1), (1, -1), 'MIDDLE')
        tbl.setStyle(style)
        elements.append(tbl)
    elif mostrar_v2:
        elements.append(_section_rule('Apontamentos do Cronograma', styles))
        data = [['Tarefa', 'Progresso', 'Qtd. dia', 'Acumulado', '% Plan.', '% Real.']]
        # Mesmo agrupamento do portal e da tela: as atividades saem sob um
        # cabeçalho por lugar do cronograma. Sem isto, a mesma atividade nos
        # dois galpões da Baia vira duas linhas idênticas na tabela e lê-se
        # como lançamento em duplicidade.
        from xml.sax.saxutils import escape as _xml_escape
        from utils.cronograma_engine import (agrupar_atividades_por_caminho,
                                             caminho_ancestrais_tarefa)
        _cache_pai: dict = {}
        _linhas = []
        for ap, tarefa in apontamentos_v2:
            _linhas.append(SimpleNamespace(
                ap=ap, tarefa=tarefa,
                caminho_tarefa=caminho_ancestrais_tarefa(tarefa, _cache_pai)))
        linhas_de_grupo = []      # índices que viram faixa de cabeçalho
        for titulo, itens in agrupar_atividades_por_caminho(_linhas):
            if titulo:
                linhas_de_grupo.append(len(data))
                data.append([Paragraph(_xml_escape(titulo), styles['cell_group']),
                             '', '', '', '', ''])
            for linha in itens:
                ap, tarefa = linha.ap, linha.tarefa
                nome = tarefa.nome_tarefa if tarefa else f'#{ap.tarefa_cronograma_id}'
                # `Paragraph` faz parse de mini-XML: um `&` no nome derruba a
                # geração do PDF inteiro se não for escapado.
                nome = _xml_escape(nome)
                unid = (tarefa.unidade_medida or '') if tarefa else ''
                if ap.tipo_apontamento == 'percentual':
                    # M07: linha percentual mostra o incremento persistido em
                    # pontos percentuais — não "0 {unidade}".
                    inc_pp = float(ap.percentual_incremento_dia or 0)
                    qtd_dia = f'{inc_pp:+g} pp'
                    qtd_ac = _fmt_pct(ap.percentual_acumulado
                                      if ap.percentual_acumulado is not None
                                      else ap.percentual_realizado)
                else:
                    qtd_dia = f"{ap.quantidade_executada_dia or 0:g} {unid}".strip()
                    qtd_ac = f"{ap.quantidade_acumulada or 0:g} {unid}".strip()
                data.append([
                    Paragraph(nome, styles['cell']),
                    _data_bar(ap.percentual_realizado, width=70, height=4),
                    Paragraph(qtd_dia, styles['mono']),
                    Paragraph(qtd_ac, styles['mono']),
                    Paragraph(_fmt_pct(ap.percentual_planejado) if ap.percentual_planejado is not None else '—', styles['mono']),
                    Paragraph(_fmt_pct(ap.percentual_realizado), styles['mono_b']),
                ])
        tbl = Table(data, colWidths=[185, 80, 70, 70, 55, 55], repeatRows=1)
        style = _table_style(6, right_align_from=2)
        style.add('ALIGN', (1, 1), (1, -1), 'LEFT')
        style.add('VALIGN', (1, 1), (1, -1), 'MIDDLE')
        for i in linhas_de_grupo:
            # A faixa ocupa a largura toda; sem o SPAN o título seria espremido
            # na 1ª coluna e as células vazias herdariam a zebra.
            style.add('SPAN', (0, i), (-1, i))
            style.add('BACKGROUND', (0, i), (-1, i), TABLE_HEAD)
            style.add('ALIGN', (0, i), (-1, i), 'LEFT')
        tbl.setStyle(style)
        elements.append(tbl)

    # ── Equipamentos ──
    if equipamentos:
        elements.append(_section_rule('Equipamentos', styles))
        data = [['Equipamento', 'Qtd.', 'Horas', 'Estado']]
        for e in equipamentos:
            data.append([
                Paragraph(e.nome_equipamento or '—', styles['cell']),
                Paragraph(str(e.quantidade or 0), styles['mono']),
                Paragraph(_fmt_horas(e.horas_uso), styles['mono']),
                Paragraph(e.estado_conservacao or '—', styles['cell']),
            ])
        tbl = Table(data, colWidths=[280, 70, 90, 125], repeatRows=1)
        style = _table_style(4, right_align_from=1)
        style.add('ALIGN', (3, 1), (3, -1), 'LEFT')
        tbl.setStyle(style)
        elements.append(tbl)

    # ── Ocorrências ──
    if ocorrencias:
        elements.append(_section_rule('Ocorrências', styles))
        for occ in ocorrencias:
            tipo = occ.tipo_ocorrencia or 'Observação'
            sev = occ.severidade or 'Baixa'
            sev_color = {
                'Crítica': colors.HexColor('#dc3545'),
                'Alta': colors.HexColor('#fd7e14'),
                'Média': colors.HexColor('#ffc107'),
                'Baixa': MUTED,
            }.get(sev, MUTED)

            tag = Table([[Paragraph(tipo, styles['badge_lbl']),
                          Paragraph(sev, styles['badge_lbl'])]],
                        colWidths=[70, 55], rowHeights=[13],
                        hAlign='LEFT')
            tag.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), PRIMARY_DARK),
                ('BACKGROUND', (1, 0), (1, 0), sev_color),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))

            occ_block = [tag, Spacer(1, 2)]
            if occ.descricao_ocorrencia:
                occ_block.append(Paragraph(occ.descricao_ocorrencia, styles['body']))
            if occ.problemas_identificados:
                occ_block.append(Paragraph(
                    f'<font color="#6c757d">Problemas</font>  {occ.problemas_identificados}',
                    styles['body_muted'],
                ))
            if occ.acoes_corretivas:
                occ_block.append(Paragraph(
                    f'<font color="#6c757d">Ações</font>  {occ.acoes_corretivas}',
                    styles['body_muted'],
                ))
            occ_block.append(Spacer(1, 4))
            elements.append(KeepTogether(occ_block))

    # ── Observações Gerais ──
    if rdo.comentario_geral:
        elements.append(_section_rule('Observações Gerais', styles))
        elements.append(Paragraph(
            rdo.comentario_geral.replace('\n', '<br/>'), styles['body'],
        ))

    # ── Registro Fotográfico ──
    fotos = (
        RDOFoto.query.filter_by(rdo_id=rdo.id)
        .order_by(RDOFoto.ordem.asc().nulls_last(), RDOFoto.id.asc())
        .limit(12)
        .all()
    )
    if fotos:
        foto_section_items = [_section_rule('Registro Fotográfico', styles)]
        cell_w = 268
        img_max_w = cell_w - 8
        img_max_h = 150
        cap_style = ParagraphStyle(
            'foto_cap', parent=styles['body_muted'],
            fontSize=7.5, leading=10, alignment=1,
        )
        cells = []
        for idx, foto in enumerate(fotos, start=1):
            img = _foto_image(foto, max_w=img_max_w, max_h=img_max_h)
            if not img:
                continue
            legenda = (foto.legenda or foto.descricao or '').strip()
            cap = f"Foto {idx}" + (f" — {legenda}" if legenda else "")
            cell = Table([[img], [Paragraph(cap, cap_style)]], colWidths=[cell_w])
            cell.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.4, BORDER),
                ('LINEBELOW', (0, 0), (-1, 0), 0.3, BORDER),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            cells.append(cell)
        # Agrupa em linhas de 2 colunas
        rows = []
        for i in range(0, len(cells), 2):
            row = cells[i:i + 2]
            while len(row) < 2:
                row.append('')
            rows.append(row)
        if rows:
            # Renderiza uma linha por vez. A primeira fica junto do título
            # (KeepTogether) para não deixar o cabeçalho órfão. As demais
            # linhas fluem normalmente e podem quebrar entre páginas.
            for ridx, row in enumerate(rows):
                grid = Table([row], colWidths=[cell_w, cell_w], hAlign='LEFT')
                grid.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (0, -1), 12),
                    ('RIGHTPADDING', (1, 0), (1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                if ridx == 0:
                    foto_section_items.append(grid)
                    elements.append(KeepTogether(foto_section_items))
                else:
                    elements.append(grid)

    # ── Assinaturas ──
    sig_block = _signature_block(rdo, config, styles)
    if sig_block:
        elements.append(Spacer(1, 18))
        elements.append(sig_block)

    # ── Ciência do cliente (Fase 9a) ──
    # Vem DEPOIS das assinaturas porque é outra coisa: aquelas são autoria
    # (quem executou, quem responde); esta é o aceite de quem contratou.
    ciencia_block = _ciencia_cliente_block(rdo, styles)
    if ciencia_block:
        elements.append(Spacer(1, 12))
        elements.append(ciencia_block)

    footer = _Footer(empresa_nome, rdo.numero_rdo or f'RDO #{rdo.id}')
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)
    return buf.getvalue()


def _assinaturas_desatualizadas(rdo, assinaturas):
    """Assinaturas cujo hash não bate mais com o RDO de hoje.

    UM recálculo para o documento inteiro (o payload canônico é o mesmo para
    todas as assinaturas dele), comparado com o que cada uma guardou.

    Falha FECHADA, como `services/rdo_hash.verificar_integridade`: se o hash
    não puder ser recalculado, TODAS entram como desatualizadas. Num PDF que
    se apresenta como evidência, um silêncio otimista é o pior resultado
    possível — melhor um alerta a mais do que uma prova falsa.
    """
    try:
        from services.rdo_hash import calcular_hash
        atual = calcular_hash(rdo)
    except Exception:
        logger.exception('[rdo-pdf] falha ao recalcular hash do rdo %s',
                         getattr(rdo, 'id', None))
        return list(assinaturas)

    return [a for a in assinaturas
            if (a.algoritmo or 'sha256') != 'sha256'
            or a.hash_conteudo != atual]


def _ciencia_cliente_block(rdo, styles):
    """Fase 9a — quadro da ciência do cliente, com quem FALTA assinar.

    A tabela de assinaturas já lista quem assinou (as de papel `cliente`
    entram nela junto com as internas). O que só este bloco diz é o
    denominador: "2 de 3", e o nome de quem ainda não deu ciência. Num
    documento entregue ao cliente ou anexado a uma medição, essa é a
    diferença entre "duas pessoas assinaram" e "falta o diretor assinar".

    Devolve None quando a obra não tem responsáveis cadastrados — sem
    denominador não há placar, e uma seção vazia só ocuparia página.
    """
    try:
        from services.rdo_ciencia_cliente import placar
        p = placar(rdo)
    except Exception:
        logger.exception('[rdo-pdf] placar de ciência ilegível no rdo %s',
                         getattr(rdo, 'id', None))
        return None

    if not p['total']:
        return None

    corpo = ParagraphStyle('cie_body', parent=styles['body'], fontSize=8,
                           leading=10.5, textColor=INK)

    situacao = (f"<b>{p['assinados']} de {p['total']}</b> "
                f"{'responsável deu' if p['total'] == 1 else 'responsáveis deram'}"
                f" ciência neste relatório.")
    if p['completo']:
        situacao += ' <b>Ciência completa.</b>'

    linhas = [Paragraph(situacao, corpo)]

    for item in p['itens']:
        s, a = item['signatario'], item['assinatura']
        cargo = f" — {s.cargo}" if s.cargo else ''
        if a is not None:
            quando = (a.assinado_em.strftime('%d/%m/%Y %H:%M:%S')
                      if a.assinado_em else '—')
            marca = '' if item['integra'] else '  <b>[conteúdo alterado depois]</b>'
            texto = (f'&#10003; <b>{s.nome}</b>{cargo} — {quando} (UTC), '
                     f'IP {a.ip or "—"}{marca}')
        else:
            # `&#183;` (·) e não `&#9675;` (○): a fonte base do reportlab não
            # tem o círculo vazio e desenha um quadrado preto no lugar — que
            # num PDF de obra parece marca de item CONCLUÍDO, o oposto do que
            # a linha diz. O ponto médio é Latin-1 e sempre renderiza.
            texto = (f'&#183; <b>{s.nome}</b>{cargo} — '
                     f'<b>aguardando ciência</b>')
        linhas.append(Paragraph(texto, corpo))

    linhas.append(Spacer(1, 4))
    linhas.append(Paragraph(
        'A ciência é registrada pelo portal do cliente, com autenticação '
        'individual por responsável, carimbo de tempo do servidor e verificação '
        'de integridade (SHA-256) do conteúdo deste RDO. Ela atesta o aceite do '
        'contratante e não substitui as assinaturas de autoria acima.',
        ParagraphStyle('cie_nota', parent=styles['body_muted'], fontSize=6.5,
                       leading=8.5)))

    return KeepTogether([_section_rule('Ciência do cliente', styles)] + linhas)


def _signature_block(rdo, config, styles):
    """Bloco de assinaturas no rodapé do conteúdo.

    Fase 5: quando existe `RDOAssinatura` (assinatura eletrônica com
    hash + carimbo de tempo + IP), o PDF imprime a EVIDÊNCIA — nome,
    papel, data/hora, IP e prefixo do hash — em vez da linha em branco
    para caneta. Sem assinatura eletrônica, o comportamento antigo é
    preservado integralmente: coluna do responsável pelo preenchimento +
    coluna do engenheiro responsável, com linha para assinar à mão.
    """
    assinaturas = list(getattr(rdo, 'assinaturas', None) or [])

    if assinaturas:
        cabecalho_style = ParagraphStyle(
            'sig_head', parent=styles['body'], fontSize=8, leading=10,
            textColor=INK)
        celula_style = ParagraphStyle(
            'sig_cell', parent=styles['body'], fontSize=7.5, leading=9.5,
            textColor=INK)

        linhas = [[
            Paragraph('<b>Papel</b>', cabecalho_style),
            Paragraph('<b>Assinado por</b>', cabecalho_style),
            Paragraph('<b>Data/hora (UTC)</b>', cabecalho_style),
            Paragraph('<b>IP</b>', cabecalho_style),
            Paragraph('<b>SHA-256</b>', cabecalho_style),
        ]]
        for a in assinaturas:
            quando = (a.assinado_em.strftime('%d/%m/%Y %H:%M:%S')
                      if a.assinado_em else '—')
            nome = a.nome_signatario or '—'
            if a.cargo_signatario:
                nome = f'{nome}<br/><font size="6.5">{a.cargo_signatario}</font>'
            linhas.append([
                Paragraph((a.papel or '').capitalize(), celula_style),
                Paragraph(nome, celula_style),
                Paragraph(quando, celula_style),
                Paragraph(a.ip or '—', celula_style),
                Paragraph((a.hash_conteudo or '')[:24] + '…', celula_style),
            ])

        tabela = Table(linhas, colWidths=[52, 150, 92, 72, 134])
        tabela.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, 0), 0.6, INK),
            ('LINEBELOW', (0, 1), (-1, -1), 0.25, INK),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        nota = Paragraph(
            'Assinatura eletrônica com registro de autoria e verificação de '
            'integridade (SHA-256 sobre o conteúdo do RDO), nos termos do '
            'art. 10, §2º da MP 2.200-2/2001. Carimbo de tempo do servidor.',
            ParagraphStyle('sig_nota', parent=styles['body_muted'],
                           fontSize=6.5, leading=8.5))

        blocos = [_section_rule('Assinaturas', styles), tabela,
                  Spacer(1, 4), nota]

        # Fase 9a — um PDF que lista assinaturas de um documento ALTERADO
        # depois delas é pior que um PDF sem assinatura nenhuma: parece prova
        # e não é. Se algum hash não bate mais, o papel precisa dizer.
        desatualizadas = _assinaturas_desatualizadas(rdo, assinaturas)
        if desatualizadas:
            nomes = ', '.join(a.nome_signatario or '—' for a in desatualizadas)
            blocos.append(Spacer(1, 4))
            blocos.append(Paragraph(
                f'<b>ATENÇÃO:</b> o conteúdo deste RDO não corresponde mais '
                f'ao que foi assinado por {nomes}. A verificação de '
                f'integridade (SHA-256) falhou para {len(desatualizadas)} '
                f'assinatura(s) — este documento não deve ser usado como '
                f'evidência sem antes esclarecer a divergência.',
                ParagraphStyle('sig_alerta', parent=styles['body'],
                               fontSize=7, leading=9,
                               textColor=colors.HexColor('#b45309'))))

        return KeepTogether(blocos)

    # ── Sem assinatura eletrônica: comportamento pré-Fase 5 ──────────
    responsavel_nome = rdo.criado_por.nome if rdo.criado_por else 'Responsável pelo preenchimento'
    responsavel_cargo = 'Apontador / Mestre de Obras'

    eng = None
    if config and config.engenheiro_padrao_id:
        eng = EngenheiroResponsavel.query.get(config.engenheiro_padrao_id)
    if not eng and config:
        # Fallback: usar assinatura_nome do ConfiguracaoEmpresa
        if config.assinatura_nome:
            eng_nome = config.assinatura_nome
            eng_cargo = config.assinatura_cargo or 'Responsável Técnico'
            eng_crea = ''
        else:
            return None
    elif eng:
        eng_nome = eng.nome
        eng_cargo = 'Engenheiro Responsável'
        eng_crea = f'CREA {eng.crea}' if eng.crea else ''
    else:
        return None

    def sig_col(nome, cargo, extra=''):
        line_style = ParagraphStyle(
            'sigline', parent=styles['body'], alignment=1,
            fontSize=8.5, leading=11, textColor=INK,
        )
        cargo_style = ParagraphStyle(
            'sigcargo', parent=styles['body_muted'], alignment=1,
            fontSize=7.5, leading=10,
        )
        rule = Table([['']], colWidths=[200], rowHeights=[0.6])
        rule.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, -1), 0.6, INK),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        inner = [
            [Spacer(1, 22)],
            [rule],
            [Paragraph(f'<b>{nome}</b>', line_style)],
            [Paragraph(cargo + (f' · {extra}' if extra else ''), cargo_style)],
        ]
        t = Table(inner, colWidths=[220])
        t.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        return t

    row = Table([[
        sig_col(responsavel_nome, responsavel_cargo),
        '',
        sig_col(eng_nome, eng_cargo, eng_crea),
    ]], colWidths=[220, 60, 220])
    row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether(row)
