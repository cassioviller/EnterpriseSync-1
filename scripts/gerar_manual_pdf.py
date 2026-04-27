"""Gera o manual visual do ciclo SIGE em PDF a partir dos screenshots."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
)
from PIL import Image as PILImage

OUT_PDF = Path("docs/manual_ciclo/Manual_Ciclo_SIGE.pdf")
SCREENS = Path("docs/manual_ciclo/screenshots")

PAGE_W, PAGE_H = A4
MARGIN = 1.6 * cm
USABLE_W = PAGE_W - 2 * MARGIN

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("Capa", parent=styles["Title"],
    fontSize=30, leading=36, textColor=colors.HexColor("#1a3d6e"),
    alignment=TA_CENTER, spaceAfter=20))
styles.add(ParagraphStyle("CapaSub", parent=styles["Normal"],
    fontSize=14, leading=18, textColor=colors.HexColor("#445566"),
    alignment=TA_CENTER, spaceAfter=12))
styles.add(ParagraphStyle("Step", parent=styles["Heading2"],
    fontSize=16, leading=20, textColor=colors.HexColor("#1a3d6e"),
    spaceBefore=4, spaceAfter=6))
styles.add(ParagraphStyle("Body", parent=styles["BodyText"],
    fontSize=10.5, leading=14, alignment=TA_JUSTIFY, spaceAfter=6))
styles.add(ParagraphStyle("Small", parent=styles["Normal"],
    fontSize=8.5, leading=11, textColor=colors.HexColor("#666"), spaceAfter=4))
styles.add(ParagraphStyle("URL", parent=styles["Code"],
    fontSize=9, leading=12, textColor=colors.HexColor("#0a5"),
    backColor=colors.HexColor("#f0f5ee"), borderPadding=4, spaceAfter=8))

STEPS = [
    {
        "n": 1, "title": "Tela de login do sistema",
        "img": "01_login.png",
        "url": "/login",
        "desc": (
            "Ponto de entrada do SIGE. Os usuários se autenticam aqui antes de "
            "acessar qualquer módulo do sistema. Para esta sessão de validação "
            "foi usado o usuário <b>admin_E2E208-T7X5RN</b> (perfil ADMIN do "
            "tenant 1037), o mesmo da sessão anterior, para garantir que o "
            "ciclo seja reproduzível sem criar novo cadastro."
        ),
    },
    {
        "n": 2, "title": "Painel principal (dashboard)",
        "img": "02_dashboard.png",
        "url": "/",
        "desc": (
            "Após o login o usuário cai no dashboard, com cards resumindo "
            "obras em andamento, propostas pendentes, indicadores financeiros "
            "e atalhos para os módulos. A partir daqui inicia-se a jornada "
            "comercial → operacional do ciclo completo."
        ),
    },
    {
        "n": 3, "title": "Catálogo — lista de insumos cadastrados",
        "img": "03_lista_insumos.png",
        "url": "/catalogo/insumos?busca=E2E210-RICO",
        "desc": (
            "Filtramos a busca pelo sufixo <b>E2E210-RICO</b> para mostrar "
            "apenas os 5 insumos criados nesta validação: cimento, areia, "
            "brita, aço CA-50 e tinta acrílica. Cada insumo tem unidade de "
            "medida, preço e tipo. Eles serão consumidos nas composições dos "
            "serviços nos próximos passos."
        ),
    },
    {
        "n": 4, "title": "Cadastro de novo insumo",
        "img": "04_form_novo_insumo.png",
        "url": "/catalogo/insumos/novo",
        "desc": (
            "Tela usada para incluir um insumo novo no catálogo. Os campos "
            "obrigatórios são nome, tipo (material, mão de obra, equipamento "
            "etc.), unidade de medida e preço unitário. O coeficiente padrão "
            "é opcional e ajuda no auto-preenchimento das composições."
        ),
    },
    {
        "n": 5, "title": "Catálogo — lista de serviços cadastrados",
        "img": "05_lista_servicos.png",
        "url": "/catalogo/servicos?busca=E2E210-RICO",
        "desc": (
            "Os 2 serviços criados aparecem aqui: <b>Alvenaria estrutural</b> "
            "(categoria Estrutura, m²) e <b>Pintura interna</b> (categoria "
            "Acabamento, m²). Os percentuais de margem de lucro e imposto "
            "ficam guardados por serviço e entram no cálculo automático do "
            "preço de venda no orçamento."
        ),
    },
    {
        "n": 6, "title": "Composição do serviço — Alvenaria",
        "img": "06_composicao_alvenaria.png",
        "url": "/catalogo/servicos/1012/composicao",
        "desc": (
            "Cada serviço tem uma <b>tabela de composição</b> que define "
            "quanto de cada insumo é gasto por unidade do serviço. A "
            "Alvenaria consome 0,5 sc de cimento, 0,08 m³ de areia e 0,06 m³ "
            "de brita por m² executado. Esses coeficientes alimentam o cálculo "
            "automático de custo do orçamento e do RDO."
        ),
    },
    {
        "n": 7, "title": "Composição do serviço — Pintura",
        "img": "07_composicao_pintura.png",
        "url": "/catalogo/servicos/1013/composicao",
        "desc": (
            "A Pintura consome 0,18 L de tinta acrílica e 0,02 sc de cimento "
            "(massa de regularização) por m². A composição é flexível: "
            "qualquer combinação de insumos do catálogo pode ser adicionada."
        ),
    },
    {
        "n": 8, "title": "Edição do orçamento (2 itens)",
        "img": "08_orcamento_editar.png",
        "url": "/orcamentos/132/editar",
        "desc": (
            "O orçamento agrupa serviços com suas quantidades. Aqui temos "
            "<b>100 m² de Alvenaria</b> e <b>150 m² de Pintura</b>. O sistema "
            "calcula automaticamente o custo (insumos × coeficientes), "
            "aplica margem e imposto e exibe o subtotal e total geral. A "
            "partir desta tela é possível gerar a proposta comercial."
        ),
    },
    {
        "n": 9, "title": "Proposta comercial gerada",
        "img": "09_proposta_visualizar.png",
        "url": "/propostas/1222",
        "desc": (
            "A proposta é gerada a partir do orçamento e ganha um número, "
            "número de versão, status e um <b>token público</b> exclusivo "
            "para o cliente. Cada item do orçamento vira um item da proposta. "
            "O status percorre Rascunho → Enviada → Aprovada/Rejeitada. Nesta "
            "validação ela já está marcada como APROVADA."
        ),
    },
    {
        "n": 10, "title": "Portal do cliente (acesso público)",
        "img": "10_portal_cliente.png",
        "url": "/propostas/cliente/<token>",
        "desc": (
            "Acessado em uma janela anônima usando apenas o token (sem "
            "login). O cliente vê a proposta, os itens, o valor e tem dois "
            "botões: aprovar (que cria a obra) ou rejeitar. Note que <b>não "
            "há menus administrativos</b> — é uma página completamente "
            "isolada, segura para enviar por e-mail ao cliente."
        ),
    },
    {
        "n": 11, "title": "Detalhes da obra criada (id 1276)",
        "img": "11_obra_detalhes.png",
        "url": "/obras/1276",
        "desc": (
            "Quando o cliente aprova a proposta, o sistema cria automaticamente "
            "uma obra vinculada. A obra herda valor de contrato, cliente e os "
            "serviços. Esta tela mostra abas para informações gerais, "
            "cronograma, financeiro, RDOs e medições. Antes de liberar o "
            "acesso completo, a obra passa pelo <b>gate de revisão inicial "
            "do cronograma</b> (verificado e cumprido nesta validação)."
        ),
    },
    {
        "n": 12, "title": "Lista de compras da obra",
        "img": "12_lista_compras.png",
        "url": "/compras/?obra_id=1276",
        "desc": (
            "Todas as compras de materiais e serviços vinculadas à obra "
            "aparecem aqui, com fornecedor, data, valor total e status. As "
            "compras alimentam o financeiro da obra automaticamente."
        ),
    },
    {
        "n": 13, "title": "Cadastro de nova compra (com Select2)",
        "img": "13_form_nova_compra.png",
        "url": "/compras/nova",
        "desc": (
            "Esta é a tela aprimorada na Task #202: os campos <b>Fornecedor</b> "
            "e <b>Obra</b> usam Select2 com busca por digitação, evitando rolagem "
            "infinita em listas grandes. A grade de itens aceita várias "
            "linhas (descrição, quantidade, preço unitário). O total é "
            "recalculado automaticamente."
        ),
    },
    {
        "n": 14, "title": "RDO consolidado da obra",
        "img": "14_rdo_lista.png",
        "url": "/funcionario/rdo/consolidado?obra_id=1276",
        "desc": (
            "Tela do <b>Relatório Diário de Obra</b> consolidado, que reúne "
            "todos os RDOs lançados, ocorrências, fotos e progresso por "
            "serviço. É a visão preferida pela equipe de campo (rota moderna, "
            "preferência registrada em replit.md)."
        ),
    },
    {
        "n": 15, "title": "Formulário de novo RDO",
        "img": "15_rdo_form_novo.png",
        "url": "/rdo/novo?obra_id=1276",
        "desc": (
            "Formulário para lançar um novo RDO. A obra já vem pré-selecionada "
            "via parâmetro <code>obra_id</code> da URL. O usuário informa data, "
            "local, condições climáticas, atividades executadas, ocorrências "
            "e fotos. Após salvar, o RDO entra na lista consolidada da obra "
            "(passo 14)."
        ),
    },
]

def fitted_image(path: Path, max_w: float, max_h: float) -> Image:
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    return Image(str(path), width=w * scale, height=h * scale, hAlign="CENTER")

def build():
    doc = SimpleDocTemplate(
        str(OUT_PDF), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="Manual Visual do Ciclo Completo SIGE",
        author="SIGE v10.0",
    )
    story = []

    # ============ CAPA ============
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Manual Visual do Ciclo Completo", styles["Capa"]))
    story.append(Paragraph("SIGE v10.0 — do orçamento ao RDO", styles["CapaSub"]))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        "Documento gerado a partir da execução real e validada do ciclo "
        "completo (Task #210), com prints capturados diretamente da "
        "interface autenticada do sistema.",
        styles["Body"]))
    story.append(Spacer(1, 1.5 * cm))

    resumo = [
        ["Etapa", "Quantidade"],
        ["Insumos cadastrados",          "5"],
        ["Serviços cadastrados",         "2"],
        ["Linhas de composição",         "5"],
        ["Itens no orçamento",           "2"],
        ["Itens na proposta",            "2"],
        ["Obra criada via portal",       "1 (id 1276)"],
        ["Compra com Select2",           "1"],
        ["RDO lançado",                  "1"],
        ["Gate de cronograma",           "Cumprido"],
    ]
    t = Table(resumo, colWidths=[8 * cm, 5 * cm], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 10.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8fafd"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(
        "<b>Tenant:</b> admin_id 1037 · "
        "<b>Sufixo dos dados:</b> E2E210-RICO · "
        f"<b>Total de telas:</b> {len(STEPS)}",
        styles["Small"]))

    story.append(PageBreak())

    # ============ ÍNDICE ============
    story.append(Paragraph("Índice", styles["Step"]))
    story.append(Spacer(1, 0.3 * cm))
    idx_data = [["#", "Tela", "Rota"]]
    for s in STEPS:
        idx_data.append([str(s["n"]), s["title"], s["url"]])
    idx_t = Table(idx_data, colWidths=[1 * cm, 9 * cm, 7.5 * cm])
    idx_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8fafd"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
        ("FONTNAME", (2, 1), (2, -1), "Courier"),
        ("TEXTCOLOR", (2, 1), (2, -1), colors.HexColor("#0a5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(idx_t)
    story.append(PageBreak())

    # ============ STEPS ============
    for s in STEPS:
        img_path = SCREENS / s["img"]
        story.append(Paragraph(f"{s['n']:02d}. {s['title']}", styles["Step"]))
        story.append(Paragraph(f"Rota acessada: <font face='Courier'>{s['url']}</font>",
                               styles["URL"]))
        story.append(Paragraph(s["desc"], styles["Body"]))
        story.append(Spacer(1, 0.3 * cm))

        if img_path.exists():
            max_h = PAGE_H - 2 * MARGIN - 6 * cm
            story.append(fitted_image(img_path, USABLE_W, max_h))
        else:
            story.append(Paragraph(f"<i>(imagem ausente: {s['img']})</i>",
                                   styles["Small"]))
        story.append(PageBreak())

    # ============ FECHAMENTO ============
    story.append(Paragraph("Fechamento do ciclo", styles["Step"]))
    story.append(Paragraph(
        "Este manual reflete <b>uma execução real</b> do ciclo, validada via "
        "navegador automatizado. Todos os dados visíveis nas capturas existem "
        "no banco do ambiente de desenvolvimento e foram criados na sequência "
        "exata mostrada — começando pelo cadastro dos insumos e terminando no "
        "lançamento do RDO.",
        styles["Body"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "A jornada percorrida pode ser resumida em três grandes blocos: "
        "<b>(1) Catálogo</b> — montagem da base de insumos e serviços com "
        "composições; <b>(2) Comercial</b> — transformação do catálogo em "
        "orçamento, geração da proposta e aprovação pelo cliente via portal "
        "público; <b>(3) Operação</b> — abertura da obra, revisão do "
        "cronograma, registro de compras e abertura do RDO.",
        styles["Body"]))

    doc.build(story)
    print(f"PDF gerado: {OUT_PDF}  ({OUT_PDF.stat().st_size:,} bytes)")

if __name__ == "__main__":
    build()
