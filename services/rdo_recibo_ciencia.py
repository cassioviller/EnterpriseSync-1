#!/usr/bin/env python3
"""Recibo em PDF de UMA ciência de cliente — SIGE, redesenho de 29/07.

Documento próprio, não uma seção do PDF do RDO: `rdo_pdf_service` produz o
relatório inteiro para arquivo da obra; este produz o comprovante do ATO,
para a mão de quem acabou de assinar (spec
`docs/superpowers/specs/2026-07-29-ciencia-rdo-portal-ux-design.md`, §4).

Reaproveita deliberadamente `_logo_image`, `_build_styles` e `_Footer` do
serviço grande — mesmo cabeçalho, mesmo rodapé, mesma tipografia — para que
recibo e relatório pareçam vir da mesma casa.

O hash sai COMPLETO. Na tela ele é abreviado por legibilidade; num documento
que existe para provar, a abreviação o tornaria decorativo.
"""
from __future__ import annotations

import logging
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from models import ConfiguracaoEmpresa, Obra
from services.rdo_pdf_service import _build_styles, _Footer, _logo_image

logger = logging.getLogger(__name__)

_BORDA = colors.HexColor('#e2e8f0')
_FUNDO = colors.HexColor('#f8fafc')


def gerar_recibo_ciencia(assinatura) -> bytes:
    """PDF do recibo de uma `RDOAssinatura` de papel cliente."""
    rdo = assinatura.rdo
    obra = Obra.query.get(rdo.obra_id)
    config = ConfiguracaoEmpresa.query.filter_by(
        admin_id=assinatura.admin_id).first()
    empresa = config.nome_empresa if config else 'Construtora'
    numero = rdo.numero_rdo or f'RDO #{rdo.id}'

    styles = _build_styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=f'Recibo de ciência — {numero}',
    )

    elementos = []

    # ── Cabeçalho: logo + quem emite ──
    logo = _logo_image(config)
    cabeca_txt = [
        Paragraph('RECIBO DE CIÊNCIA', styles['title']),
        Paragraph(f'{numero} — {obra.nome if obra else ""}', styles['h1']),
        Paragraph(empresa, styles['subtle']),
    ]
    if logo is not None:
        cabeca = Table([[cabeca_txt, logo]],
                       colWidths=[None, 45 * mm])
        cabeca.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(cabeca)
    else:
        elementos.extend(cabeca_txt)
    elementos.append(Spacer(1, 10))

    # ── O que este documento é ──
    data_rdo = (rdo.data_relatorio.strftime('%d/%m/%Y')
                if rdo.data_relatorio else '—')
    elementos.append(Paragraph(
        f'Este recibo comprova que o responsável abaixo identificado deu '
        f'ciência no Relatório Diário de Obra ({numero}) de {data_rdo}, '
        f'da obra {obra.nome if obra else "—"}, pelo portal do cliente.',
        styles['body']))
    elementos.append(Spacer(1, 8))

    # ── O registro ──
    linhas = [
        ('Responsável', assinatura.nome_signatario or '—'),
        ('Cargo', assinatura.cargo_signatario or '—'),
        ('Data e hora do servidor',
         assinatura.assinado_em.strftime('%d/%m/%Y %H:%M:%S')
         if assinatura.assinado_em else '—'),
        ('Endereço de acesso (IP)', assinatura.ip or '—'),
        ('Algoritmo', (assinatura.algoritmo or 'sha256').upper()),
        # COMPLETO, de propósito — ver docstring do módulo.
        ('Impressão digital do conteúdo', assinatura.hash_conteudo or '—'),
    ]
    if assinatura.observacao:
        linhas.append(('Observação do responsável', assinatura.observacao))

    corpo = [[Paragraph(k, styles['cell_b']),
              Paragraph(str(v), styles['cell'])] for k, v in linhas]
    tabela = Table(corpo, colWidths=[52 * mm, None])
    tabela.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), _FUNDO),
        ('GRID', (0, 0), (-1, -1), 0.4, _BORDA),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabela)
    elementos.append(Spacer(1, 10))

    # ── O termo — o mesmo português da tela do ato ──
    elementos.append(Paragraph(
        'A impressão digital acima é um resumo criptográfico do conteúdo do '
        'relatório no momento da ciência: recalculá-la sobre o documento e '
        'obter o mesmo valor prova que ele não foi alterado desde então. '
        'Registro de autoria e integridade nos termos da MP 2.200-2/2001, '
        'art. 10, §2º, conforme aceito pelas partes.',
        styles['body_muted']))

    doc.build(elementos,
              onFirstPage=_Footer(empresa, numero),
              onLaterPages=_Footer(empresa, numero))
    buf.seek(0)
    pdf = buf.getvalue()
    logger.info('[recibo-ciencia] gerado — assinatura=%s rdo=%s bytes=%s',
                assinatura.id, rdo.id, len(pdf))
    return pdf
