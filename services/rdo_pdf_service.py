"""Geração de PDF do RDO (Relatório Diário de Obra).

Server-side, alinhado com o padrão de ``services.medicao_service``.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

from app import db
from models import (
    RDO, RDOMaoObra, RDOServicoSubatividade, RDOEquipamento, RDOOcorrencia,
    RDOApontamentoCronograma, ConfiguracaoEmpresa, Funcionario,
    TarefaCronograma,
)
from utils.rdo_horas import normalizar_horas_funcionario


def _fmt_horas(h):
    try:
        return f"{float(h or 0):.1f}h"
    except (TypeError, ValueError):
        return "0.0h"


def _normalizar_horas(mao_obra_rows):
    """Mesma lógica do detalhe: jornada-base dividida entre N atividades.

    Sem isso, RDOs antigos onde o apontador digitou a jornada inteira em
    cada subatividade inflam o total (8h × 5 subs = 40h por funcionário).
    """
    entradas = []
    pesos = {}
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


def gerar_pdf_rdo(rdo):
    """Gera bytes de um PDF estruturado para o RDO informado.

    Args:
        rdo: instância de ``models.RDO`` (com obra acessível por relacionamento).

    Returns:
        bytes do PDF, ou ``None`` se ``rdo`` for inválido.
    """
    if not rdo or not rdo.obra:
        return None

    obra = rdo.obra
    admin_id = rdo.admin_id or obra.admin_id
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

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title=f"RDO {rdo.numero_rdo}",
    )
    styles = getSampleStyleSheet()
    PRIMARY = colors.HexColor('#1976d2')

    title_style = ParagraphStyle(
        'TitleRDO', parent=styles['Title'], fontSize=16, spaceAfter=4 * mm, textColor=PRIMARY,
    )
    subtitle_style = ParagraphStyle(
        'SubtitleRDO', parent=styles['Normal'], fontSize=10, spaceAfter=2 * mm, textColor=colors.HexColor('#555'),
    )
    section_style = ParagraphStyle(
        'SectionRDO', parent=styles['Heading2'], fontSize=12, spaceBefore=4 * mm, spaceAfter=2 * mm, textColor=PRIMARY,
    )
    body_style = ParagraphStyle(
        'BodyRDO', parent=styles['Normal'], fontSize=9, leading=12,
    )

    elements = []

    elements.append(Paragraph(f"Relatório Diário de Obra — {rdo.numero_rdo}", title_style))
    elements.append(Paragraph(empresa_nome, subtitle_style))
    elements.append(Spacer(1, 3 * mm))

    info_rows = [
        ['Obra:', obra.nome, 'Data:', rdo.data_relatorio.strftime('%d/%m/%Y') if rdo.data_relatorio else '—'],
        ['Cliente:', getattr(obra, 'cliente_nome_efetivo', None) or '—', 'Status:', rdo.status or '—'],
        ['Local:', rdo.local or 'Campo', 'Criado por:', rdo.criado_por.nome if rdo.criado_por else 'Sistema'],
    ]
    info_table = Table(info_rows, colWidths=[55, 200, 55, 150])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), PRIMARY),
        ('TEXTCOLOR', (2, 0), (2, -1), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    tem_clima = any([rdo.clima_geral, rdo.temperatura_media, rdo.condicoes_trabalho, rdo.precipitacao, rdo.vento_velocidade, rdo.observacoes_climaticas])
    if tem_clima:
        elements.append(Paragraph("Condições Climáticas", section_style))
        clima_rows = [
            ['Clima geral:', rdo.clima_geral or '—', 'Temperatura:', rdo.temperatura_media or '—'],
            ['Vento:', rdo.vento_velocidade or '—', 'Precipitação:', rdo.precipitacao or '—'],
            ['Condições:', rdo.condicoes_trabalho or '—', 'Umidade:', f"{rdo.umidade_relativa}%" if rdo.umidade_relativa is not None else '—'],
        ]
        clima_table = Table(clima_rows, colWidths=[55, 200, 55, 150])
        clima_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(clima_table)
        if rdo.observacoes_climaticas:
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(f"<b>Obs.:</b> {rdo.observacoes_climaticas}", body_style))

    elements.append(Paragraph("Equipe", section_style))
    if mao_obra_rows:
        equipe_data = [['Funcionário', 'Função', 'Horas']]
        funcionarios_vistos = set()
        for mo in mao_obra_rows:
            if not mo.funcionario_id or mo.funcionario_id in funcionarios_vistos:
                continue
            funcionarios_vistos.add(mo.funcionario_id)
            nome = mo.funcionario.nome if mo.funcionario else f'#{mo.funcionario_id}'
            equipe_data.append([
                nome,
                funcoes_por_funcionario.get(mo.funcionario_id, '—'),
                _fmt_horas(horas_por_funcionario.get(mo.funcionario_id, 0)),
            ])
        equipe_table = Table(equipe_data, colWidths=[230, 160, 70], repeatRows=1)
        equipe_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(equipe_table)
    else:
        elements.append(Paragraph("Nenhum funcionário registrado neste RDO.", body_style))

    if subatividades:
        elements.append(Paragraph("Atividades Executadas (Subatividades)", section_style))
        ativ_data = [['Subatividade', '% Anterior', '% Atual', 'Incremento']]
        for s in subatividades:
            ativ_data.append([
                Paragraph(s.nome_subatividade or '—', body_style),
                f"{float(s.percentual_anterior or 0):.1f}%",
                f"{float(s.percentual_conclusao or 0):.1f}%",
                f"{float(s.incremento_dia or 0):.1f}%",
            ])
        ativ_table = Table(ativ_data, colWidths=[260, 70, 70, 70], repeatRows=1)
        ativ_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(ativ_table)

    if apontamentos_v2:
        elements.append(Paragraph("Apontamentos do Cronograma", section_style))
        ap_data = [['Tarefa', 'Qtd. dia', 'Acumulado', '% Planejado', '% Realizado']]
        for ap, tarefa in apontamentos_v2:
            nome = tarefa.nome_tarefa if tarefa else f'#{ap.tarefa_cronograma_id}'
            unid = (tarefa.unidade_medida or '') if tarefa else ''
            ap_data.append([
                Paragraph(nome, body_style),
                f"{ap.quantidade_executada_dia or 0:g} {unid}".strip(),
                f"{ap.quantidade_acumulada or 0:g} {unid}".strip(),
                f"{ap.percentual_planejado:.1f}%" if ap.percentual_planejado is not None else '—',
                f"{ap.percentual_realizado or 0:.1f}%",
            ])
        ap_table = Table(ap_data, colWidths=[210, 70, 70, 60, 60], repeatRows=1)
        ap_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(ap_table)

    if equipamentos:
        elements.append(Paragraph("Equipamentos", section_style))
        eq_data = [['Equipamento', 'Qtd.', 'Horas de uso', 'Estado']]
        for e in equipamentos:
            eq_data.append([
                e.nome_equipamento or '—',
                str(e.quantidade or 0),
                _fmt_horas(e.horas_uso),
                e.estado_conservacao or '—',
            ])
        eq_table = Table(eq_data, colWidths=[220, 60, 90, 100], repeatRows=1)
        eq_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(eq_table)

    if ocorrencias:
        elements.append(Paragraph("Ocorrências", section_style))
        for occ in ocorrencias:
            cab = f"<b>[{occ.tipo_ocorrencia or 'Observação'} — {occ.severidade or 'Baixa'}]</b>"
            elements.append(Paragraph(cab, body_style))
            if occ.descricao_ocorrencia:
                elements.append(Paragraph(occ.descricao_ocorrencia, body_style))
            if occ.problemas_identificados:
                elements.append(Paragraph(f"<b>Problemas:</b> {occ.problemas_identificados}", body_style))
            if occ.acoes_corretivas:
                elements.append(Paragraph(f"<b>Ações corretivas:</b> {occ.acoes_corretivas}", body_style))
            elements.append(Spacer(1, 2 * mm))

    if rdo.comentario_geral:
        elements.append(Paragraph("Observações Gerais", section_style))
        elements.append(Paragraph(rdo.comentario_geral.replace('\n', '<br/>'), body_style))

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"Documento gerado em {rdo.updated_at.strftime('%d/%m/%Y %H:%M') if rdo.updated_at else ''} — {empresa_nome}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#999')),
    ))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()
