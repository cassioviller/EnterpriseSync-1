"""Geração de PDF — Relatório de Compra do Mapa de Concorrência V2.

Materializa um PDF resumindo a decisão de compra: para cada item do mapa,
qual fornecedor foi escolhido, valor unitário, subtotal, e os atributos
comerciais (prazo, condições de pagamento, observação) por fornecedor.

Salva em static/uploads/relatorios_mapa/<obra_id>/ e retorna metadados
(arquivo_path relativo a static/, arquivo_nome, total_geral).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from flask import current_app

logger = logging.getLogger(__name__)


def _fmt_brl(valor) -> str:
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe_str(s) -> str:
    return (s or "").strip() if isinstance(s, str) else (str(s) if s is not None else "")


def gerar_relatorio_compra_pdf(
    *,
    mapa,
    obra,
    versao: int,
    nome_empresa: str = "",
    output_dir: str | None = None,
) -> dict:
    """Gera o PDF e retorna dict com {arquivo_path, arquivo_nome, total_geral}.

    `arquivo_path` é relativo ao diretório `static/` (ex.:
    `uploads/relatorios_mapa/12/relatorio_5_v3_20260429T120000.pdf`).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    )

    # ── resolver caminho de saída ─────────────────────────────────────────
    static_root = os.path.join(current_app.root_path, "static")
    rel_dir = os.path.join("uploads", "relatorios_mapa", str(obra.id))
    abs_dir = os.path.join(static_root, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    # Filename inclui microsegundos + sufixo aleatório para evitar colisão
    # mesmo sob concorrência (vide code review Task #21).
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    suffix = uuid.uuid4().hex[:6]
    arquivo_nome = f"relatorio_mapa{mapa.id}_v{versao}_{timestamp}_{suffix}.pdf"
    abs_path = os.path.join(abs_dir, arquivo_nome)
    rel_path = os.path.join(rel_dir, arquivo_nome).replace("\\", "/")

    # ── construir documento ──────────────────────────────────────────────
    doc = SimpleDocTemplate(
        abs_path, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Relatório de Compra — {mapa.nome}",
    )
    styles = getSampleStyleSheet()
    style_h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=6, leading=18,
    )
    style_h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#1e293b"),
        spaceAfter=4, spaceBefore=10, leading=14,
    )
    style_normal = ParagraphStyle(
        "normal", parent=styles["Normal"], fontSize=9, leading=12,
    )
    style_small = ParagraphStyle(
        "small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#64748b"),
    )

    story: list = []

    # Cabeçalho
    titulo = f"Relatório de Compra — {_safe_str(mapa.nome)}"
    story.append(Paragraph(titulo, style_h1))
    sub = []
    if nome_empresa:
        sub.append(f"<b>{_safe_str(nome_empresa)}</b>")
    sub.append(f"Obra: <b>{_safe_str(obra.nome)}</b>")
    sub.append(f"Versão: <b>{versao}</b>")
    sub.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    story.append(Paragraph(" &nbsp;|&nbsp; ".join(sub), style_small))
    story.append(Spacer(1, 6 * mm))

    # ── TABELA 1: Itens com fornecedor escolhido ─────────────────────────
    story.append(Paragraph("Itens e fornecedores selecionados", style_h2))

    cotacoes_map: dict = {}
    for cot in mapa.cotacoes:
        cotacoes_map.setdefault(cot.item_id, {})[cot.fornecedor_id] = cot
    forn_map = {f.id: f for f in mapa.fornecedores}

    header = ["#", "Item / Serviço", "Qtd", "Un", "Fornecedor", "Vlr Unit.", "Subtotal"]
    data: list = [header]

    total_geral = Decimal("0")
    sem_escolha = 0

    for idx, item in enumerate(mapa.itens, start=1):
        forn_id = getattr(item, "fornecedor_escolhido_id", None)
        forn = forn_map.get(forn_id) if forn_id else None
        cot = cotacoes_map.get(item.id, {}).get(forn_id) if forn_id else None
        try:
            qtd = float(item.quantidade or 0)
        except (TypeError, ValueError):
            qtd = 0.0
        if cot and cot.valor_unitario:
            valor = Decimal(str(cot.valor_unitario))
            subtotal = valor * Decimal(str(qtd))
            total_geral += subtotal
            data.append([
                str(idx),
                Paragraph(_safe_str(item.descricao), style_normal),
                f"{qtd:g}",
                _safe_str(item.unidade),
                Paragraph(_safe_str(forn.nome) if forn else "—", style_normal),
                _fmt_brl(valor),
                _fmt_brl(subtotal),
            ])
        else:
            sem_escolha += 1
            data.append([
                str(idx),
                Paragraph(_safe_str(item.descricao), style_normal),
                f"{qtd:g}",
                _safe_str(item.unidade),
                Paragraph("<i>(sem fornecedor escolhido)</i>", style_small),
                "—",
                "—",
            ])

    data.append([
        "", "", "", "", Paragraph("<b>Total geral</b>", style_normal), "",
        _fmt_brl(total_geral),
    ])

    tbl = Table(
        data,
        colWidths=[10 * mm, 70 * mm, 14 * mm, 12 * mm, 38 * mm, 22 * mm, 24 * mm],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (3, -1), "CENTER"),
        ("ALIGN", (5, 0), (6, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dbeafe")),
        ("FONTNAME", (4, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#1e3a8a")),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    if sem_escolha > 0:
        story.append(Paragraph(
            f"<i>Atenção: {sem_escolha} item(ns) sem fornecedor escolhido — "
            "não computado(s) no total.</i>", style_small,
        ))
        story.append(Spacer(1, 4 * mm))

    # ── TABELA 2: Resumo por fornecedor ──────────────────────────────────
    story.append(Paragraph("Resumo por fornecedor escolhido", style_h2))

    # agrupar subtotais por fornecedor escolhido
    agrupado: dict = {}  # forn_id -> {nome, total, qtd_itens}
    for item in mapa.itens:
        fid = getattr(item, "fornecedor_escolhido_id", None)
        if not fid:
            continue
        cot = cotacoes_map.get(item.id, {}).get(fid)
        if not cot or not cot.valor_unitario:
            continue
        try:
            qtd = float(item.quantidade or 0)
        except (TypeError, ValueError):
            qtd = 0.0
        subtotal = Decimal(str(cot.valor_unitario)) * Decimal(str(qtd))
        f = forn_map.get(fid)
        bucket = agrupado.setdefault(fid, {
            "nome": _safe_str(f.nome) if f else "—",
            "prazo": _safe_str(getattr(f, "prazo_entrega", "")) if f else "",
            "condicoes": _safe_str(getattr(f, "condicoes_pagamento", "")) if f else "",
            "observacao": _safe_str(getattr(f, "observacao", "")) if f else "",
            "total": Decimal("0"),
            "qtd_itens": 0,
        })
        bucket["total"] += subtotal
        bucket["qtd_itens"] += 1

    if agrupado:
        header2 = ["Fornecedor", "Itens", "Prazo", "Condições", "Total"]
        data2: list = [header2]
        for fid, info in sorted(agrupado.items(), key=lambda kv: -float(kv[1]["total"])):
            data2.append([
                Paragraph(f"<b>{info['nome']}</b>", style_normal),
                str(info["qtd_itens"]),
                Paragraph(info["prazo"] or "—", style_normal),
                Paragraph(info["condicoes"] or "—", style_normal),
                _fmt_brl(info["total"]),
            ])
        tbl2 = Table(
            data2,
            colWidths=[55 * mm, 18 * mm, 30 * mm, 50 * mm, 30 * mm],
            repeatRows=1,
        )
        tbl2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (4, 0), (4, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
        ]))
        story.append(tbl2)

        # observações por fornecedor (se existirem)
        obs_lines = []
        for fid, info in agrupado.items():
            if info["observacao"]:
                obs_lines.append(f"<b>{info['nome']}:</b> {info['observacao']}")
        if obs_lines:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Observações", style_h2))
            for line in obs_lines:
                story.append(Paragraph(line, style_normal))
                story.append(Spacer(1, 2 * mm))
    else:
        story.append(Paragraph(
            "<i>Nenhum fornecedor foi escolhido ainda para os itens deste mapa.</i>",
            style_small,
        ))

    # ── TABELA 3 (anexo): Mapa comparativo completo ──────────────────────
    if mapa.fornecedores and mapa.itens:
        story.append(PageBreak())
        story.append(Paragraph("Anexo — Mapa comparativo de cotações", style_h2))

        col_count = 4 + len(mapa.fornecedores)
        header3 = ["Item", "Qtd", "Un", "Escolhido"]
        for f in mapa.fornecedores:
            header3.append(_safe_str(f.nome))
        data3: list = [header3]

        for item in mapa.itens:
            try:
                qtd = float(item.quantidade or 0)
            except (TypeError, ValueError):
                qtd = 0.0
            esc_id = getattr(item, "fornecedor_escolhido_id", None)
            esc_nome = forn_map[esc_id].nome if esc_id and esc_id in forn_map else "—"
            row = [
                Paragraph(_safe_str(item.descricao), style_small),
                f"{qtd:g}",
                _safe_str(item.unidade),
                Paragraph(_safe_str(esc_nome), style_small),
            ]
            for f in mapa.fornecedores:
                cot = cotacoes_map.get(item.id, {}).get(f.id)
                row.append(_fmt_brl(cot.valor_unitario) if cot and cot.valor_unitario else "—")
            data3.append(row)

        # cabeçalho de prazos por fornecedor
        prazo_row = ["", "", "", "Prazo:"]
        for f in mapa.fornecedores:
            prazo_row.append(_safe_str(getattr(f, "prazo_entrega", "")) or "—")
        data3.append(prazo_row)

        item_col_w = max(40, 130 - 18 * len(mapa.fornecedores))
        col_widths = [item_col_w * mm / 1, 12 * mm, 10 * mm, 30 * mm]
        # ajustar para caber em A4 — fornecedores compartilham espaço restante
        page_w = A4[0] / mm - 30  # margens
        used = item_col_w + 12 + 10 + 30
        remaining = max(20, page_w - used)
        forn_w = remaining / max(1, len(mapa.fornecedores))
        col_widths = [item_col_w * mm, 12 * mm, 10 * mm, 30 * mm] + [forn_w * mm] * len(mapa.fornecedores)

        tbl3 = Table(data3, colWidths=col_widths, repeatRows=1)
        tbl3.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef9c3")),
            ("FONTNAME", (3, -1), (3, -1), "Helvetica-Bold"),
            ("ALIGN", (3, -1), (3, -1), "RIGHT"),
        ]))
        story.append(tbl3)

    # ── render ───────────────────────────────────────────────────────────
    doc.build(story)
    logger.info(
        "[RELATORIO_MAPA] PDF gerado: mapa=%s versao=%s arquivo=%s total=%s",
        mapa.id, versao, rel_path, total_geral,
    )

    return {
        "arquivo_path": rel_path,
        "arquivo_nome": arquivo_nome,
        "total_geral": total_geral,
    }
