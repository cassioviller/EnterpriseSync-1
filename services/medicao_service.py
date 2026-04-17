import calendar
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from app import db
from models import (
    Obra, MedicaoObra, MedicaoObraItem, ItemMedicaoComercial,
    ItemMedicaoCronogramaTarefa, TarefaCronograma, ContaReceber,
    ConfiguracaoEmpresa,
)

logger = logging.getLogger(__name__)


def calcular_periodo_atual(obra):
    ultima = (
        MedicaoObra.query
        .filter_by(obra_id=obra.id, admin_id=obra.admin_id)
        .filter(MedicaoObra.status.in_(['APROVADO', 'FATURADO']))
        .order_by(MedicaoObra.numero.desc())
        .first()
    )

    if ultima and ultima.periodo_fim:
        prox = ultima.periodo_fim + timedelta(days=1)
        if prox.day <= 15:
            periodo_inicio = prox.replace(day=1)
        else:
            periodo_inicio = prox.replace(day=16)
    else:
        ref = obra.data_inicio_medicao or obra.data_inicio or date.today()
        if ref.day <= 15:
            periodo_inicio = ref.replace(day=1)
        else:
            periodo_inicio = ref.replace(day=16)

    if periodo_inicio.day <= 15:
        periodo_fim = periodo_inicio.replace(day=15)
    else:
        ultimo_dia = calendar.monthrange(periodo_inicio.year, periodo_inicio.month)[1]
        periodo_fim = periodo_inicio.replace(day=ultimo_dia)

    return periodo_inicio, periodo_fim


def calcular_percentual_item(item):
    vinc = ItemMedicaoCronogramaTarefa.query.filter_by(item_medicao_id=item.id).all()
    if not vinc:
        return Decimal('0')

    total_peso = sum(Decimal(str(v.peso)) for v in vinc)
    if total_peso <= 0:
        return Decimal('0')

    perc_ponderado = Decimal('0')
    for v in vinc:
        tarefa = TarefaCronograma.query.get(v.cronograma_tarefa_id)
        if tarefa:
            perc_tarefa = Decimal(str(tarefa.percentual_concluido or 0))
            peso_norm = Decimal(str(v.peso)) / total_peso
            perc_ponderado += perc_tarefa * peso_norm

    return perc_ponderado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def validar_pesos_item(item_id):
    vinc = ItemMedicaoCronogramaTarefa.query.filter_by(item_medicao_id=item_id).all()
    if not vinc:
        return True, Decimal('0')
    total = sum(Decimal(str(v.peso)) for v in vinc)
    return total == Decimal('100'), total


def gerar_medicao_quinzenal(obra_id, admin_id, periodo_inicio=None, periodo_fim=None, observacoes=None):
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        return None, "Obra não encontrada"

    itens_comerciais = ItemMedicaoComercial.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).all()
    if not itens_comerciais:
        return None, "Nenhum item de medição comercial cadastrado para esta obra"

    for item in itens_comerciais:
        vinc = ItemMedicaoCronogramaTarefa.query.filter_by(item_medicao_id=item.id).all()
        if vinc:
            soma_pesos = sum(Decimal(str(v.peso)) for v in vinc)
            if soma_pesos != Decimal('100'):
                return None, f'Item "{item.nome}" possui soma de pesos = {float(soma_pesos):.0f}% (deve ser exatamente 100%)'

    if not periodo_inicio or not periodo_fim:
        periodo_inicio, periodo_fim = calcular_periodo_atual(obra)

    ultima = MedicaoObra.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).order_by(MedicaoObra.numero.desc()).first()
    proximo_numero = (ultima.numero + 1) if ultima else 1

    valor_contrato = Decimal(str(obra.valor_contrato or 0))
    valor_entrada = Decimal(str(obra.valor_entrada or 0))

    medicao = MedicaoObra(
        obra_id=obra_id,
        admin_id=admin_id,
        numero=proximo_numero,
        data_medicao=datetime.utcnow(),
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        observacoes=observacoes,
        status='PENDENTE',
    )
    db.session.add(medicao)
    db.session.flush()

    total_medido_periodo = Decimal('0')

    for item in itens_comerciais:
        perc_atual = calcular_percentual_item(item)
        perc_anterior = Decimal(str(item.percentual_executado_acumulado or 0))
        perc_periodo = max(Decimal('0'), perc_atual - perc_anterior)

        valor_comercial = Decimal(str(item.valor_comercial or 0))
        valor_periodo = (perc_periodo / Decimal('100')) * valor_comercial
        valor_acum = (perc_atual / Decimal('100')) * valor_comercial

        moi = MedicaoObraItem(
            medicao_obra_id=medicao.id,
            item_medicao_comercial_id=item.id,
            percentual_anterior=perc_anterior,
            percentual_atual=perc_atual,
            percentual_executado_periodo=perc_periodo,
            valor_medido_periodo=valor_periodo.quantize(Decimal('0.01')),
            percentual_executado_acumulado=perc_atual,
            valor_executado_acumulado=valor_acum.quantize(Decimal('0.01')),
            admin_id=admin_id,
        )
        db.session.add(moi)
        total_medido_periodo += valor_periodo

        item.percentual_executado_acumulado = perc_atual
        item.valor_executado_acumulado = valor_acum.quantize(Decimal('0.01'))
        if perc_atual >= 100:
            item.status = 'CONCLUIDO'

    entrada_proporcional = Decimal('0')
    if valor_contrato > 0 and valor_entrada > 0 and total_medido_periodo > 0:
        entrada_proporcional = (total_medido_periodo * valor_entrada / valor_contrato).quantize(Decimal('0.01'))

    valor_a_faturar = total_medido_periodo - entrada_proporcional
    if valor_a_faturar < 0:
        valor_a_faturar = Decimal('0')

    medicao.valor_total_medido_periodo = total_medido_periodo.quantize(Decimal('0.01'))
    medicao.valor_entrada_abatido_periodo = entrada_proporcional.quantize(Decimal('0.01'))
    medicao.valor_a_faturar_periodo = valor_a_faturar.quantize(Decimal('0.01'))
    medicao.valor_medido = total_medido_periodo.quantize(Decimal('0.01'))

    if valor_contrato > 0:
        soma_acum = sum(Decimal(str(i.valor_executado_acumulado or 0)) for i in itens_comerciais)
        medicao.percentual_executado = float((soma_acum / valor_contrato * 100).quantize(Decimal('0.01')))

    # Task #94: ContaReceber NÃO é mais criada por medição. Em vez disso,
    # `recalcular_medicao_obra` faz UPSERT de UMA ContaReceber por obra
    # (origem_tipo='OBRA_MEDICAO', origem_id=obra.id) refletindo o total
    # medido acumulado descontado da entrada já recebida.
    db.session.commit()

    cr = recalcular_medicao_obra(obra_id, admin_id)
    if cr is not None:
        medicao.conta_receber_id = cr.id
        db.session.commit()

    logger.info(f"[OK] Medição #{proximo_numero} gerada para obra {obra_id}")
    return medicao, None


def fechar_medicao(medicao_id, admin_id):
    medicao = MedicaoObra.query.filter_by(id=medicao_id, admin_id=admin_id).first()
    if not medicao:
        return None, "Medição não encontrada"
    if medicao.status != 'PENDENTE':
        return None, "Medição já fechada"

    medicao.status = 'APROVADO'
    db.session.commit()

    # Task #94: ao fechar a medição, atualizar a ContaReceber única da obra
    cr = recalcular_medicao_obra(medicao.obra_id, admin_id)
    if cr is not None and not medicao.conta_receber_id:
        medicao.conta_receber_id = cr.id
        db.session.commit()

    return medicao, None


def _recalcular_imc_avanco(obra_id, admin_id):
    """Task #94 — recalcula `percentual_executado_acumulado` e
    `valor_executado_acumulado` de cada `ItemMedicaoComercial` da obra a
    partir do estado vivo do cronograma e dos RDOs.

    Fontes (em ordem de precedência):
      1) Vínculos `ItemMedicaoCronogramaTarefa` → média ponderada de
         `TarefaCronograma.percentual_concluido` (mesma regra usada em
         `gerar_medicao_quinzenal`).
      2) Fallback por `IMC.servico_id`: maior `RDOServicoSubatividade
         .percentual_conclusao` registrado para aquele servico em RDOs
         **finalizados** da obra (RDO.status in {'Finalizado','FINALIZADO'}).

    Persiste os campos diretamente no IMC. Retorna o total medido acumulado
    da obra (Decimal).
    """
    from models import (
        ItemMedicaoComercial as _IMC, RDOServicoSubatividade as _RSS, RDO as _RDO,
    )

    itens = _IMC.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()
    total_medido = Decimal('0')

    for item in itens:
        perc_atual = calcular_percentual_item(item)

        # Fallback por servico_id quando não há vínculos no cronograma
        if perc_atual <= 0 and getattr(item, 'servico_id', None):
            try:
                max_perc = (
                    db.session.query(db.func.max(_RSS.percentual_conclusao))
                    .join(_RDO, _RDO.id == _RSS.rdo_id)
                    .filter(
                        _RSS.servico_id == item.servico_id,
                        _RSS.admin_id == admin_id,
                        _RDO.obra_id == obra_id,
                        _RDO.status.in_(['Finalizado', 'FINALIZADO', 'finalizado']),
                    )
                    .scalar()
                )
                if max_perc is not None:
                    perc_atual = Decimal(str(max_perc)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception as e:
                logger.warning(f"_recalcular_imc_avanco fallback RDO falhou item={item.id}: {e}")

        # Cap em 100
        if perc_atual > Decimal('100'):
            perc_atual = Decimal('100')
        if perc_atual < Decimal('0'):
            perc_atual = Decimal('0')

        valor_comercial = Decimal(str(item.valor_comercial or 0))
        valor_acum = (perc_atual / Decimal('100')) * valor_comercial
        valor_acum = valor_acum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        item.percentual_executado_acumulado = perc_atual
        item.valor_executado_acumulado = valor_acum
        if perc_atual >= Decimal('100') and getattr(item, 'status', None) != 'CONCLUIDO':
            try:
                item.status = 'CONCLUIDO'
            except Exception:
                pass

        total_medido += valor_acum

    return total_medido.quantize(Decimal('0.01'))


def recalcular_medicao_obra(obra_id, admin_id):
    """Task #94 — recalcula avanço dos IMC + UPSERT da ContaReceber única
    por obra (`origem_tipo='OBRA_MEDICAO'`, `origem_id=obra.id`,
    `numero_documento='OBR-MED-#####'`).

    Fluxo:
      1) `_recalcular_imc_avanco` atualiza `percentual_executado_acumulado`
         e `valor_executado_acumulado` por IMC (cronograma ponderado, com
         fallback por `RDOServicoSubatividade.servico_id`).
      2) Soma o medido acumulado, desconta `obra.valor_entrada` (quando
         `data_entrada` está preenchida) e calcula `valor_a_faturar`.
      3) Cria ou atualiza a `ContaReceber` única com status
         `PENDENTE`/`PARCIAL`/`QUITADA` conforme `valor_recebido`.

    Retorna a `ContaReceber` resultante, ou None se ainda não havia o que
    cobrar e nenhuma CR pré-existia.
    """
    from models import Obra

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        logger.warning(f"recalcular_medicao_obra: obra {obra_id} não encontrada (admin={admin_id})")
        return None

    # 1) Recalcular avanço por IMC (cronograma + fallback RDO)
    medido_total = _recalcular_imc_avanco(obra_id, admin_id)

    # 2) Task #94: a CR acumulada da obra reflete o **medido**:
    #    valor_original = valor_medido (sem abater entrada — entrada é
    #    paga em CR separada se houver) e saldo = max(0, medido - recebido).
    valor_medido = medido_total

    cr = ContaReceber.query.filter_by(
        admin_id=admin_id, origem_tipo='OBRA_MEDICAO', origem_id=obra_id
    ).first()

    if valor_medido <= 0 and not cr:
        # Persistir o recálculo do avanço mesmo sem CR a criar
        db.session.commit()
        return None

    cliente_nome = obra.cliente or obra.cliente_nome or obra.nome or 'Cliente'
    descricao = f"Medição da obra {obra.codigo or obra.nome} — saldo a faturar acumulado"
    hoje = date.today()

    if cr is None:
        cr = ContaReceber(
            cliente_nome=cliente_nome,
            obra_id=obra_id,
            numero_documento=f"OBR-MED-{obra_id:05d}",
            descricao=descricao,
            valor_original=valor_medido,
            valor_recebido=Decimal('0'),
            saldo=valor_medido,
            data_emissao=hoje,
            data_vencimento=hoje + timedelta(days=30),
            status='PENDENTE' if valor_medido > 0 else 'QUITADA',
            origem_tipo='OBRA_MEDICAO',
            origem_id=obra_id,
            admin_id=admin_id,
        )
        db.session.add(cr)
        db.session.flush()
        logger.info(
            f"[OK] ContaReceber OBRA_MEDICAO criada (id={cr.id}) obra={obra_id} "
            f"valor_medido=R$ {float(valor_medido):.2f}"
        )
    else:
        cr.cliente_nome = cliente_nome
        cr.descricao = descricao
        cr.valor_original = valor_medido
        recebido = Decimal(str(cr.valor_recebido or 0))
        novo_saldo = valor_medido - recebido
        if novo_saldo < 0:
            novo_saldo = Decimal('0')
        cr.saldo = novo_saldo
        if novo_saldo <= 0 and recebido > 0:
            cr.status = 'QUITADA'
        elif recebido > 0:
            cr.status = 'PARCIAL'
        else:
            cr.status = 'PENDENTE'
        logger.info(
            f"[OK] ContaReceber OBRA_MEDICAO atualizada (id={cr.id}) obra={obra_id} "
            f"valor_medido=R$ {float(valor_medido):.2f} saldo=R$ {float(novo_saldo):.2f} "
            f"recebido=R$ {float(recebido):.2f} status={cr.status}"
        )

    db.session.commit()
    return cr


def gerar_pdf_extrato_medicao(medicao_id, admin_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    medicao = MedicaoObra.query.filter_by(id=medicao_id, admin_id=admin_id).first()
    if not medicao:
        return None

    obra = Obra.query.get(medicao.obra_id)
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    itens = MedicaoObraItem.query.filter_by(medicao_obra_id=medicao.id).all()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleMed', parent=styles['Title'], fontSize=16, spaceAfter=4*mm, textColor=colors.HexColor('#1976d2'))
    subtitle_style = ParagraphStyle('SubtitleMed', parent=styles['Normal'], fontSize=10, spaceAfter=2*mm, textColor=colors.HexColor('#555'))
    header_style = ParagraphStyle('HeaderMed', parent=styles['Normal'], fontSize=11, spaceAfter=3*mm, textColor=colors.HexColor('#333'), leading=14)

    elements = []

    empresa_nome = config.nome_empresa if config else 'Empresa'
    elements.append(Paragraph(f"Extrato de Medição #{medicao.numero:03d}", title_style))
    elements.append(Paragraph(empresa_nome, subtitle_style))
    elements.append(Spacer(1, 4*mm))

    info_data = [
        ['Obra:', obra.nome, 'Contrato:', f"R$ {float(obra.valor_contrato or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
        ['Período:', f"{medicao.periodo_inicio.strftime('%d/%m/%Y')} a {medicao.periodo_fim.strftime('%d/%m/%Y')}", 'Status:', medicao.status],
        ['Cliente:', obra.cliente or '—', 'Medição Nº:', f"{medicao.numero:03d}"],
    ]
    info_table = Table(info_data, colWidths=[60, 180, 70, 150])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1976d2')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#1976d2')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6*mm))

    elements.append(Paragraph("Itens da Medição", header_style))

    table_data = [['Item', '% Ant.', '% Atual', '% Período', 'Valor Comercial', 'Valor Período', 'Valor Acum.']]
    for mi in itens:
        ic = mi.item_comercial
        table_data.append([
            ic.nome if ic else '—',
            f"{float(mi.percentual_anterior or 0):.1f}%",
            f"{float(mi.percentual_atual or 0):.1f}%",
            f"{float(mi.percentual_executado_periodo or 0):.1f}%",
            f"R$ {float(ic.valor_comercial or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            f"R$ {float(mi.valor_medido_periodo or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            f"R$ {float(mi.valor_executado_acumulado or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6*mm))

    def fmt_brl(v):
        return f"R$ {float(v or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    entrada_perc = 0
    if obra.valor_contrato and float(obra.valor_contrato) > 0 and obra.valor_entrada:
        entrada_perc = float(obra.valor_entrada) / float(obra.valor_contrato) * 100

    resumo_data = [
        ['Total Medido no Período:', fmt_brl(medicao.valor_total_medido_periodo)],
        [f'Entrada Abatida ({entrada_perc:.1f}%):', f"(−) {fmt_brl(medicao.valor_entrada_abatido_periodo)}"],
        ['Valor a Faturar:', fmt_brl(medicao.valor_a_faturar_periodo)],
    ]
    rt = Table(resumo_data, colWidths=[300, 160])
    rt.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, 2), (-1, 2), 1.5, colors.HexColor('#1976d2')),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, 2), (1, 2), colors.HexColor('#1976d2')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(rt)

    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — {empresa_nome}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#999'))
    ))

    doc.build(elements)
    buf.seek(0)
    return buf
