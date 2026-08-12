"""Exportação do cronograma da obra em PDF — a planilha de tarefas no papel
timbrado da empresa.

Spec: `docs/superpowers/specs/2026-08-12-cronograma-pdf-layout-veks-design.md`.

Três funções, uma responsabilidade cada, no par `montar_*`/`exportar_*` que
`services/cronograma_fisico_financeiro.py` estabeleceu:

  * `montar_linhas_cronograma` — dados. Não sabe que existe PDF;
  * `montar_marca_tenant` — a identidade visual do tenant (logo e dados);
  * `exportar_cronograma_pdf` — desenho. Não toca no banco: dict entra,
    bytes saem, e é por isso que ela é testável sem obra nenhuma.

**O critério que governa este módulo é papel-igual-a-tela.** O PDF não
recalcula nada por conta própria: os percentuais e o progresso geral saem das
mesmas funções que `cronograma_views.cronograma_obra` chama, incluindo a
assimetria da linha-raiz descrita em `_percentual_da_linha`. Um número aqui
que não bata com a tela é defeito deste módulo, mesmo que esteja "mais
certo" — é o que `tests/test_cronograma_pdf.py` trava.

O layout vem do **kit oficial** (`veks_layout_pdf`: `template_veks.html` +
`gerar_pdf.py`), que descreve o papel da casa em CSS e o gera via Chromium.
Este módulo porta esse layout para reportlab — mesmas medidas, mesmas cores,
mesma escala tipográfica — porque gerar no servidor com Chromium exigiria o
navegador na imagem de produção (que hoje não o tem; os testes de Playwright
neste host falham justamente por isso).

Tokens do kit, honrados aqui: `--navy #16294a`, `--navy2 #1e3a5f` (rótulos),
`--orange #e8611a`, `--line #d8dde5`, corpo em Helvetica e **títulos em
serifa** (Georgia, com 'DejaVu Serif' como alternativa — é a que o próprio
render do kit embutiu, e está versionada em `static/fonts/`).

A regra 1 do README do kit — "cada página tem cabeçalho, `.footer` e
`.footbar` próprios" — aqui é o `canvasmaker`: ele desenha o filete de duas
cores no topo e a barra navy no pé de TODA página, e a `LongTable` cuida da
quebra. A forma é a mesma para todo tenant; a marca sai de
`ConfiguracaoEmpresa`.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re
import unicodedata
from datetime import date

logger = logging.getLogger(__name__)

# ── Tokens do kit oficial (template_veks.html, bloco :root) ──────────────────
NAVY = '#16294A'          # --navy: azul-marinho institucional
NAVY_ROTULO = '#1E3A5F'   # --navy2: azul dos rótulos da grade
LARANJA = '#E8611A'       # --orange: laranja VEKS
FIO = '#D8DDE5'           # --line: bordas e filetes
CINZA = '#6B7280'         # --gray
INK = '#26303D'           # cor do corpo de texto (body)
PREENCHIMENTO = '#F1F3F7'
BRANCO = '#FFFFFF'

# Geometria da página, em mm, direto do CSS do kit:
#   .page { padding: 11mm 13mm 0 13mm }
#   .header img { height: 13mm; margin-left: -2mm }
#   .rule { height: 2.6pt; margin-top: 4mm }  .rule .o { width: 34mm }
#   .footer { bottom: 0; left: 13mm; padding: 3mm 0 6mm }
#   .footbar { height: 2mm; width: 210mm; background: var(--navy) }
MARGEM_LATERAL_MM = 13
PADDING_TOPO_MM = 11
LOGO_ALTURA_MM = 13
LOGO_RECUO_MM = -2
FILETE_ESPESSURA_PT = 2.6
FILETE_DISTANCIA_MM = 4     # do rodapé do cabeçalho até o filete
FILETE_LARANJA_MM = 34
FOOTBAR_ALTURA_MM = 2

# Piso do `_cor()`: quando o timbre do tenant não traz a chave, vale o token do
# kit. As constantes acima continuam sendo a fonte desse piso — e o dicionário
# existe para que `_cor` não precise de um `if` por cor.
PADRAO_CORES = {
    'navy': NAVY,
    'navy_rotulo': NAVY_ROTULO,
    'laranja': LARANJA,
    'fio': FIO,
    'cinza': CINZA,
    'ink': INK,
    'realce_linha': '#EEF0F4',
}

SANS = 'Helvetica'
SANS_BOLD = 'Helvetica-Bold'
# Preenchidos por `_registrar_serifada()`: o kit pede Georgia com 'DejaVu
# Serif' como alternativa, e foi a DejaVu que o render oficial embutiu.
SERIFADA = 'Times-Roman'
SERIFADA_BOLD = 'Times-Bold'
_serifada_resolvida = False


def _registrar_serifada() -> None:
    """Registra a DejaVu Serif versionada em `static/fonts/`, uma vez.

    O kit declara `font-family: Georgia, 'DejaVu Serif', serif` nos títulos, e
    o PDF de exemplo dele embute justamente a DejaVu Serif — então é ela, e não
    a Times, que reproduz o papel oficial.

    A fonte é versionada no repositório em vez de instalada por `apt`
    (`fonts-dejavu-core`) de propósito: a imagem de produção
    (`python:3.11-slim`) instala `libfontconfig1` mas nenhuma família de
    fontes, e um PDF que muda de tipografia entre dev e produção é o tipo de
    diferença que ninguém percebe até o cliente receber o arquivo.

    Falha de registro cai em `Times-Roman` e segue: título com serifa
    diferente é ruim, download que não acontece é pior.
    """
    global SERIFADA, SERIFADA_BOLD, _serifada_resolvida
    if _serifada_resolvida:
        return
    _serifada_resolvida = True
    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    base = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'static', 'fonts')
    try:
        pdfmetrics.registerFont(TTFont(
            'DejaVuSerif', os.path.join(base, 'DejaVuSerif.ttf')))
        pdfmetrics.registerFont(TTFont(
            'DejaVuSerif-Bold', os.path.join(base, 'DejaVuSerif-Bold.ttf')))
        SERIFADA, SERIFADA_BOLD = 'DejaVuSerif', 'DejaVuSerif-Bold'
    except Exception as e:
        logger.warning('[CRONOGRAMA-PDF] serifada do kit indisponível, '
                       'usando Times: %s', e)

TRACO = '—'  # travessão: data ausente, duração de marco, percentual de marco


# ═════════════════════════════════════════════════════════════════════════════
# DADOS
# ═════════════════════════════════════════════════════════════════════════════

def montar_linhas_cronograma(obra_id: int, admin_id: int, *,
                             cliente: bool = False) -> dict:
    """Monta o cabeçalho e as linhas do cronograma para exportação.

    Lê pela mesma trinca que a tela: `ordenar_arvore_visual` (a fonte única
    da ordem visual e da numeração de linhas), `sincronizar_percentuais_obra`
    e `calcular_progresso_geral_obra_v2` / `progresso_geral_cliente`.

    `cliente=True` lê a cópia-cliente (`is_cliente=True`), o plano combinado
    com o cliente; `False` lê o cronograma interno, que o RDO alimenta. Quem
    chama decide — a rota espelha o modo da tela aberta, para que o papel
    nunca diga algo diferente do que a pessoa tinha na frente.

    Devolve `{'obra': {...}, 'linhas': [...]}`. Obra sem tarefa devolve
    `linhas` vazia (não erro): é situação normal, e quem desenha resolve.
    """
    from models import Obra, TarefaCronograma
    from utils.cronograma_engine import (
        calcular_progresso_geral_obra_v2,
        ordenar_arvore_visual,
        progresso_geral_cliente,
        rollup_realizado,
        sincronizar_percentuais_obra,
    )

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if obra is None:
        raise ValueError(f'obra {obra_id} não encontrada no tenant {admin_id}')

    if not cliente:
        # Mesma sincronização que a tela faz antes de exibir: sem isso o PDF
        # mostraria o percentual anterior ao último apontamento de RDO. Aqui
        # ela é legítima — o valor é DERIVADO do RDO e o recálculo converge.
        sincronizar_percentuais_obra(obra_id, admin_id, cliente=False)

    tarefas_raw = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem)
        .all()
    )
    tarefas, nivel_map = ordenar_arvore_visual(tarefas_raw, com_nivel=True)

    # ── Modo cliente: rollup dos pais EM MEMÓRIA, sem tocar no banco ──────
    #
    # `sincronizar_percentuais_obra(cliente=True)` promete no docstring
    # "apenas recalcula bottom-up dos pais", mas não é o que faz: o laço do
    # RDO roda igual, não acha apontamento (a cópia-cliente nunca tem — o RDO
    # aponta só no plano interno), grava `0.0` em cada folha e comita
    # (`utils/cronograma_engine.py:551-552`). Chamá-la aqui faria o download
    # de um PDF **apagar o plano combinado com o cliente**.
    #
    # Uma exportação não escreve. Então o modo cliente lê o percentual como
    # está e agrega os pais com `rollup_realizado` — a mesma fórmula
    # (M06 §4.1), em memória, ordenada pela profundidade real da árvore.
    #
    # Consequência conhecida e aceita: se a tela do cronograma-cliente for
    # aberta, ela zera as folhas e passa a mostrar 0 onde o PDF mostra o
    # valor gravado. O papel fica *mais* certo que a tela nesse caso — e o
    # defeito é da tela, registrado no spec para ter rodada própria. Entre
    # espelhar uma tela que destrói dado e não escrever, não escrever ganha.
    rollup: dict = {}
    if cliente:
        progresso_geral = progresso_geral_cliente(tarefas)
        rollup = rollup_realizado([
            {'id': t.id, 'tarefa_pai_id': t.tarefa_pai_id,
             'duracao_dias': t.duracao_dias,
             'percentual_realizado': t.percentual_concluido or 0.0}
            for t in tarefas
        ])
    else:
        progresso_geral = calcular_progresso_geral_obra_v2(
            obra_id, date.today(), admin_id)['progresso_geral_pct']

    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}

    linhas = []
    for numero, t in enumerate(tarefas, start=1):
        linhas.append({
            'numero': numero,
            'nivel': nivel_map.get(t.id, 0),
            'nome': t.nome_tarefa or '',
            'duracao_dias': t.duracao_dias,
            'data_inicio': t.data_inicio,
            'data_fim': t.data_fim,
            'percentual': _percentual_da_linha(t, progresso_geral,
                                               rollup=rollup),
            'is_pai': t.id in pai_ids,
            'is_raiz': not t.tarefa_pai_id,
            'is_marco': _e_marco(t),
        })

    datas_inicio = [t.data_inicio for t in tarefas if t.data_inicio]
    datas_fim = [t.data_fim for t in tarefas if t.data_fim]

    return {
        'obra': {
            'nome': obra.nome or '',
            'codigo': obra.codigo or '',
            'cliente': obra.cliente_nome_efetivo,
            'data_inicio': min(datas_inicio) if datas_inicio else None,
            'data_fim': max(datas_fim) if datas_fim else None,
            'progresso_geral': progresso_geral,
            'modo_cliente': cliente,
        },
        'linhas': linhas,
    }


def _e_marco(tarefa) -> bool:
    """Marco pela definição do motor — `is_marco` explícito OU duração zero.

    Reusa `_is_marco_efetivo` em vez de reimplementar `is_marco or dur == 0`:
    a regra "duração zero conta como marco" é do spec M06 §4.2, e o dia em
    que ela mudar não pode deixar este módulo para trás.
    """
    from utils.cronograma_engine import _is_marco_efetivo
    return bool(_is_marco_efetivo(tarefa))


def _percentual_da_linha(tarefa, progresso_geral: float, *,
                         rollup: dict) -> float:
    """O percentual que a linha mostra: linha-raiz recebe o progresso geral.

    `rollup` é o agregado dos pais calculado em memória (só no modo cliente,
    onde não há sync que o grave). Vazio no modo interno, em que o valor já
    está no banco, posto lá por `sincronizar_percentuais_obra`.

    A tela tem DOIS lugares que respondem isso, e eles discordam no modo
    cliente:

    * a **grade HTML** — `templates/obras/cronograma.html:220` e `:397` —
      sobrescreve a linha sem `tarefa_pai_id` com `progresso_geral_header`
      sempre que ele não é None, o que depois da p4 é *sempre*, nos dois
      modos;
    * o array `tarefas_dict` que alimenta as **barras do Gantt** recebe a
      mesma sobrescrita só no modo interno (`cronograma_views.py`, branch
      `else`).

    No modo cliente, portanto, a célula da tabela mostra o progresso geral e a
    barra ao lado mostra o rollup hierárquico. O PDF é uma **tabela**, então o
    referente é a grade — e a regra vale nos dois modos, sem `if cliente`.

    Não é papel de este módulo consertar a discordância da tela: alinhar a
    barra do Gantt à célula é outra rodada — com o número mudando à vista de
    todos, e não escondido numa exportação.
    """
    if not tarefa.tarefa_pai_id:
        return float(progresso_geral)
    if tarefa.id in rollup:
        return float(rollup[tarefa.id])
    return float(tarefa.percentual_concluido or 0.0)


def _cor(marca: dict, chave: str) -> str:
    """A cor do timbre do tenant, com o token do kit como piso.

    O desenho lê tudo por aqui em vez de usar as constantes do módulo: é o que
    permite a um tenant trocar o navy pelo verde dele sem tocar em código, e
    ao mesmo tempo garante que uma chave ausente (ou um timbre antigo, salvo
    antes de a cor existir) caia no padrão em vez de estourar KeyError no meio
    da geração.
    """
    cores = marca.get('cores') or {}
    valor = cores.get(chave)
    if isinstance(valor, str) and valor:
        return valor
    return PADRAO_CORES.get(chave, NAVY)


def montar_marca_tenant(admin_id: int) -> dict:
    """A identidade visual do tenant: dados, logo e CORES.

    A forma do documento é a mesma para todo tenant; o que varia é a marca. E
    desde o timbre em JSON (migration 286), variam também as cores: quem
    resolve a precedência entre os tokens do kit, os campos soltos da tela e o
    JSON importado é `services/timbre_pdf.carregar` — aqui só se traduz o
    resultado para o vocabulário do desenho (bytes de logo em vez de base64).

    A razão social entra como linha própria quando existe: é o
    "Angelin Engenharia Ltda. · CNPJ …" do papel oficial, que não cabia em
    `nome_empresa` sozinho.
    """
    from services.timbre_pdf import carregar

    timbre = carregar(admin_id)
    empresa = timbre['empresa']
    return {
        'nome': empresa.get('nome') or 'Empresa',
        'razao_social': empresa.get('razao_social') or '',
        'cnpj': empresa.get('cnpj') or '',
        'endereco': empresa.get('endereco') or '',
        'website': empresa.get('website') or '',
        'logo': _logo_em_bytes(timbre.get('logo_base64')),
        'cores': timbre.get('cores') or {},
    }


def _logo_em_bytes(dado: str | None) -> bytes | None:
    """Decodifica a logo em base64, tolerando o prefixo `data:` do upload.

    Devolve None e loga quando o conteúdo não é base64 válido: um cadastro
    com logo corrompida não pode derrubar o download do cronograma — o
    cabeçalho degrada para o nome da empresa em serifada, que é informação
    suficiente para o documento.
    """
    if not dado:
        return None
    texto = dado.strip()
    if texto.startswith('data:'):
        _, _, texto = texto.partition(',')
    try:
        return base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError) as e:
        logger.warning('[CRONOGRAMA-PDF] logo do tenant ignorada '
                       '(base64 inválido): %s', e)
        return None


def nome_arquivo(dados: dict, hoje: date | None = None) -> str:
    """`Cronograma_Obra-Angela_2026-08-12.pdf` — sufixo `_cliente` no modo
    cliente. Sanitiza o nome da obra para caber num header HTTP e num sistema
    de arquivos qualquer."""
    hoje = hoje or date.today()
    bruto = dados['obra'].get('nome') or 'obra'
    sem_acento = (unicodedata.normalize('NFKD', bruto)
                  .encode('ascii', 'ignore').decode('ascii'))
    limpo = re.sub(r'[^A-Za-z0-9]+', '-', sem_acento).strip('-') or 'obra'
    sufixo = '_cliente' if dados['obra'].get('modo_cliente') else ''
    return f'Cronograma_{limpo[:60]}_{hoje.isoformat()}{sufixo}.pdf'


# ═════════════════════════════════════════════════════════════════════════════
# DESENHO
# ═════════════════════════════════════════════════════════════════════════════

def exportar_cronograma_pdf(dados: dict, marca: dict) -> bytes:
    """Desenha o PDF e devolve os bytes. Não toca no banco.

    A4 retrato. A tabela é uma `LongTable(repeatRows=1)`: a quebra de página
    e a repetição do cabeçalho vêm da própria reportlab, e não de contagem de
    linhas escrita à mão. O total de páginas do rodapé exige a passada dupla
    do `canvasmaker`, que é o padrão da biblioteca para isso.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
    )

    obra = dados['obra']
    linhas = dados['linhas']

    _registrar_serifada()

    # Cores do TENANT, resolvidas uma vez: os estilos e o canvas leem daqui, e
    # não das constantes do módulo. É o que faz o timbre em JSON valer.
    C = {chave: colors.HexColor(_cor(marca, chave)) for chave in PADRAO_CORES}

    buf = io.BytesIO()
    margem = MARGEM_LATERAL_MM * mm
    # Geometria do kit, somada de cima para baixo: padding do topo (11mm) +
    # altura da logo (13mm) + distância até o filete (4mm) + o filete (2,6pt).
    # É onde o cabeçalho termina, e portanto onde o conteúdo pode começar.
    topo = ((PADDING_TOPO_MM + LOGO_ALTURA_MM + FILETE_DISTANCIA_MM) * mm
            + FILETE_ESPESSURA_PT)
    # E de baixo para cima: barra navy (2mm) + padding do rodapé (6mm) + a
    # linha de texto (7,6pt) + o respiro acima dela (3mm).
    base = (FOOTBAR_ALTURA_MM + 6 + 3) * mm + 7.6

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=margem, rightMargin=margem,
        topMargin=topo, bottomMargin=base,
        title=f"Cronograma — {obra['nome']}",
        author=marca.get('nome') or 'Empresa',
        subject='Cronograma da obra',
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id='corpo', leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='padrao', frames=[frame])])

    # Escala tipográfica do kit. `letter-spacing` do CSS vem em px; 1px a 96dpi
    # equivale a 0,75pt, e é essa a conversão usada nos `charSpace`.
    #
    #   .tag  -> 8pt bold, ls 2.6px, laranja, caps
    #   h1    -> serifa, PESO NORMAL, 21pt, lh 1.18, navy
    #   .lead -> 9.6pt, #4b5563
    #   .lbl  -> 7.2pt bold, ls 1.6px, navy2, caps
    #   thead -> 7.6pt, ls 1.4px, caps, branco, alinhado à ESQUERDA
    #   tbody -> 9.2pt, lh 1.45
    est_etiqueta = ParagraphStyle('etiqueta', fontName=SANS_BOLD, fontSize=8,
                                  leading=11, charSpace=2.6 * 0.75,
                                  textColor=C['laranja'],
                                  spaceAfter=2.5 * mm)
    est_titulo = ParagraphStyle('titulo', fontName=SERIFADA, fontSize=21,
                                leading=21 * 1.18,
                                textColor=C['navy'])
    est_lead = ParagraphStyle('lead', fontName=SANS, fontSize=9.6,
                              leading=9.6 * 1.45, spaceBefore=2.5 * mm,
                              textColor=colors.HexColor('#4B5563'))
    est_rotulo = ParagraphStyle('rotulo', fontName=SANS_BOLD, fontSize=7.2,
                                leading=10, charSpace=1.6 * 0.75,
                                textColor=C['navy_rotulo'],
                                spaceAfter=1.4 * mm)
    est_valor = ParagraphStyle('valor', fontName=SANS, fontSize=9.4,
                               leading=9.4 * 1.35,
                               textColor=C['ink'])
    est_cabecalho = ParagraphStyle('cab', fontName=SANS_BOLD, fontSize=7.6,
                                   leading=10.5, charSpace=1.4 * 0.75,
                                   textColor=colors.HexColor(BRANCO))
    est_celula = ParagraphStyle('celula', fontName=SANS, fontSize=9.2,
                                leading=9.2 * 1.45,
                                textColor=C['ink'])
    est_celula_pai = ParagraphStyle('celula_pai', parent=est_celula,
                                    fontName=SANS_BOLD,
                                    textColor=C['navy'])
    est_vazio = ParagraphStyle('vazio', fontName=SANS, fontSize=9.4,
                               leading=13, textColor=C['cinza'])

    historia = [
        # O `margin-top: 8mm` da `.tag` precisa ser um espaçador explícito: o
        # reportlab descarta `spaceBefore` do PRIMEIRO flowable de um frame
        # (`_atTop`), e sem isto a etiqueta encosta no filete.
        Spacer(1, 8 * mm),
        Paragraph(_etiqueta(obra), est_etiqueta),
        Paragraph('Cronograma Físico', est_titulo),
        Paragraph(_lead(obra), est_lead),
        Spacer(1, 4.5 * mm),
        _grade_informacoes(obra, est_rotulo, est_valor, doc.width, C),
        Spacer(1, 6.5 * mm),
    ]

    if not linhas:
        # Obra sem tarefa é situação normal (cronograma ainda não montado, ou
        # modo cliente numa obra sem cópia-cliente). Um PDF que diz isso é
        # melhor que um 500 ou que um arquivo com a tabela vazia.
        historia.append(Paragraph(
            'Nenhuma tarefa cadastrada neste cronograma.', est_vazio))
    else:
        historia.append(_tabela(linhas, doc.width, est_celula, est_celula_pai,
                                est_cabecalho, C, _cor(marca, 'laranja')))

    doc.build(historia, canvasmaker=_canvas_com_marca(marca, obra, C))
    return buf.getvalue()


def _esc(texto) -> str:
    """Escapa `&`, `<` e `>` para o mini-XML do `Paragraph`.

    Todo texto de banco que entra num `Paragraph` passa por aqui. Sem isso,
    um cliente chamado "Silva & Filhos" — ou uma tarefa "Laje <2º pav>" —
    derruba a geração inteira com erro de parse, e o usuário vê um 500 no
    lugar do download. Nomes com `&` são comuns o suficiente para que isso
    seja quando, não se.
    """
    from xml.sax.saxutils import escape
    return escape(str(texto or ''))


def _etiqueta(obra: dict) -> str:
    """`.tag` do kit: laranja, caixa-alta espaçada, nomeando o documento e a
    obra — no template, `CRONOGRAMA DE OBRA · {{NOME_DA_OBRA}}`."""
    partes = ['CRONOGRAMA DE OBRA']
    if obra.get('modo_cliente'):
        partes.append('VISÃO DO CLIENTE')
    if obra.get('nome'):
        partes.append(_esc(obra['nome'].upper()))
    return ' · '.join(partes)


def _lead(obra: dict) -> str:
    """`.lead` do kit: a frase cinza abaixo do título."""
    partes = []
    if obra.get('codigo'):
        partes.append(f"Obra {_esc(obra['codigo'])}")
    if obra.get('data_inicio') and obra.get('data_fim'):
        partes.append(f"planejamento de {_data(obra['data_inicio'])} "
                      f"a {_data(obra['data_fim'])}")
    partes.append(f"progresso geral de {_percentual(obra.get('progresso_geral'))}")
    return ' · '.join(partes) + '.'


def _grade_informacoes(obra: dict, est_rotulo, est_valor, largura, C):
    """`.grid` do kit: caixa de fio fino, DUAS colunas, rótulo em caixa-alta
    espaçada sobre o valor.

    O CSS é explícito na estrutura: `grid-template-columns: 1fr 1fr`, célula
    com `padding: 2.5mm 4mm`, borda à direita nas ímpares e sem borda inferior
    nas duas últimas. A faixa de quatro células numa linha só, que este módulo
    tinha antes, era invenção minha — não existe no kit.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle

    periodo = TRACO
    if obra.get('data_inicio') and obra.get('data_fim'):
        periodo = (f"{_data(obra['data_inicio'])} a "
                   f"{_data(obra['data_fim'])}")

    itens = [
        ('CLIENTE', obra.get('cliente') or TRACO),
        ('OBRA', obra.get('nome') or TRACO),
        ('PERÍODO PLANEJADO', periodo),
        ('PROGRESSO GERAL', _percentual(obra.get('progresso_geral'))),
        ('DATA DE EMISSÃO', _data(date.today())),
        ('VISÃO', 'Cronograma do cliente' if obra.get('modo_cliente')
         else 'Cronograma interno da obra'),
    ]

    def _celula(item):
        rotulo, valor = item
        return [Paragraph(rotulo, est_rotulo), Paragraph(_esc(valor), est_valor)]

    corpo = [[_celula(itens[i]), _celula(itens[i + 1])]
             for i in range(0, len(itens), 2)]

    tabela = Table(corpo, colWidths=[largura / 2, largura / 2])
    tabela.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, C['fio']),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C['fio']),
        ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return tabela


def _tabela(linhas, largura, est_celula, est_celula_pai, est_cabecalho,
            C, laranja_hex):
    """A planilha de tarefas: `#`, Nome, Dur., Início, Término, %.

    A coluna `#` é o número de linha sequencial da grade
    (`templates/obras/cronograma.html:189`) — a mesma numeração que a coluna
    `Pred.` referencia. Não é EDT hierárquica: a hierarquia aparece pela
    indentação do nome e pelo negrito da tarefa-pai.

    Traços do kit (`thead th` e `tbody td` do template): cabeçalho navy com
    texto branco em caixa-alta espaçada de 7,6pt, alinhado à ESQUERDA, com
    `padding: 2.2mm 3.5mm`; corpo em 9,2pt com `border-bottom` no fio e
    alinhamento vertical ao topo. O kit não usa zebra — a separação é o fio.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, TableStyle

    cabecalho = [Paragraph(t, est_cabecalho) for t in
                 ('#', 'NOME DA TAREFA', 'DUR.', 'INÍCIO', 'TÉRMINO', '%')]
    corpo = [cabecalho]
    estilo_extra = []

    for i, ln in enumerate(linhas, start=1):  # +1: linha 0 é o cabeçalho
        estilo_nome = est_celula_pai if ln['is_pai'] else est_celula
        nome = _nome_com_hierarquia(ln, laranja_hex)
        corpo.append([
            str(ln['numero']),
            Paragraph(nome, estilo_nome),
            _duracao(ln),
            _data(ln['data_inicio']),
            _data(ln['data_fim']),
            _percentual_celula(ln),
        ])
        if ln['is_pai']:
            # `tr.totalrow` do kit: fundo #eef0f4, negrito, navy. É o único
            # realce de linha que o template tem, e serve à tarefa-pai.
            estilo_extra += [
                ('BACKGROUND', (0, i), (-1, i), C['realce_linha']),
                ('FONTNAME', (0, i), (0, i), SANS_BOLD),
                ('FONTNAME', (2, i), (-1, i), SANS_BOLD),
                ('TEXTCOLOR', (0, i), (-1, i), C['navy']),
            ]

    col_num, col_dur, col_data, col_perc = 10 * mm, 15 * mm, 21 * mm, 14 * mm
    tabela = LongTable(
        corpo, repeatRows=1,
        colWidths=[col_num,
                   largura - col_num - col_dur - 2 * col_data - col_perc,
                   col_dur, col_data, col_data, col_perc],
    )
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C['navy']),
        ('FONTNAME', (0, 1), (-1, -1), SANS),
        ('FONTSIZE', (0, 1), (-1, -1), 9.2),
        ('TEXTCOLOR', (0, 1), (-1, -1), C['ink']),
        # `tbody td { border-bottom: 1px solid var(--line) }` — só o fio
        # horizontal, sem grade fechada e sem zebra, como no kit.
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, C['fio']),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # `thead th { padding: 2.2mm 3.5mm }` e `tbody td { 2.3mm 3.5mm }`.
        ('LEFTPADDING', (0, 0), (-1, -1), 3.5 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3.5 * mm),
        ('TOPPADDING', (0, 0), (-1, 0), 2.2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2.2 * mm),
        ('TOPPADDING', (0, 1), (-1, -1), 2.3 * mm),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 2.3 * mm),
    ] + estilo_extra))
    return tabela


def _nome_com_hierarquia(linha: dict, laranja_hex: str) -> str:
    """Indentação por nível e losango laranja no marco.

    A indentação é feita com espaços não-quebráveis dentro do `Paragraph`
    (7pt por nível seria a alternativa via `leftIndent`, mas ela some quando
    o nome quebra em duas linhas, e o alinhamento da segunda linha é
    justamente o que faz a hierarquia ser legível).
    """
    recuo = '&nbsp;' * (4 * int(linha.get('nivel') or 0))
    nome = _esc(linha['nome'])
    if linha['is_marco']:
        return f'{recuo}<font color="{laranja_hex}">&#9670;</font> {nome}'
    return f'{recuo}{nome}'


def _duracao(linha: dict) -> str:
    """`33d` — em dias, como a coluna do modelo guarda. Marco não tem
    duração para mostrar."""
    if linha['is_marco']:
        return TRACO
    dur = linha.get('duracao_dias')
    if dur is None:
        return TRACO
    return f'{int(dur)}d'


def _data(d) -> str:
    return d.strftime('%d/%m/%y') if d else TRACO


def _percentual_celula(linha: dict) -> str:
    """O texto da célula de %, com o mesmo arredondamento da grade da tela.

    A grade formata de dois jeitos diferentes na MESMA coluna
    (`templates/obras/cronograma.html:397`): a linha-raiz sai com uma casa
    decimal (`"%.1f"|format(progresso_geral_header)`) e as demais saem
    truncadas para inteiro (`perc`, que é `|int`). Truncado, não arredondado:
    40,6% aparece como 40 na tela. O PDF copia os dois comportamentos, senão
    uma tarefa em 40,6% sairia como 41 no papel e 40 na tela — divergência
    pequena, do tipo que faz alguém conferir a soma três vezes.

    Marco não mostra percentual: `—`. É decisão de layout do spec (a tela
    mostra o número, o documento do cliente não finge que um marco tem
    andamento parcial), e por isso está aqui na formatação e não no dado.
    """
    if linha.get('is_marco'):
        return TRACO
    try:
        valor = float(linha.get('percentual') or 0)
    except (TypeError, ValueError):
        return TRACO
    if linha.get('is_raiz'):
        return f'{valor:.1f}%'
    return f'{int(valor)}%'


def _percentual(valor) -> str:
    """Percentual com uma casa, para a faixa de metadados — o mesmo formato
    do card "Progresso Geral" da tela (`id="statPercGeral"`)."""
    try:
        return f'{float(valor or 0):.1f}%'
    except (TypeError, ValueError):
        return TRACO


def _canvas_com_marca(marca: dict, obra: dict, C):
    """Fábrica do canvas que desenha a faixa de marca e o rodapé.

    Subclasse de `canvas.Canvas` acumulando os estados das páginas para que o
    rodapé possa escrever `pág. X/Y` — sem a passada dupla, `Y` é
    desconhecido enquanto a primeira página é desenhada. É o padrão da
    reportlab para total de páginas.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as canvas_mod

    largura_pagina, altura_pagina = A4
    margem = MARGEM_LATERAL_MM * mm
    logo_bytes = marca.get('logo')

    class CanvasComMarca(canvas_mod.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for estado in self._paginas:
                self.__dict__.update(estado)
                self._desenhar_marca()
                self._desenhar_rodape(total)
                super().showPage()
            super().save()

        def _desenhar_marca(self):
            """`.header` + `.rule` do kit, em toda página (regra 1 do README).

            O topo da logo fica no `padding` de 11mm; ela tem 13mm de altura e
            recua 2mm para a esquerda (`margin-left: -2mm`), o que faz o
            wordmark encostar na margem óptica em vez de parecer deslocado.
            """
            topo_conteudo = altura_pagina - PADDING_TOPO_MM * mm
            altura_logo = LOGO_ALTURA_MM * mm
            x_logo = margem + LOGO_RECUO_MM * mm
            desenhou_logo = False
            if logo_bytes:
                try:
                    img = ImageReader(io.BytesIO(logo_bytes))
                    lg, ag = img.getSize()
                    largura = altura_logo * (lg / ag) if ag else altura_logo
                    # Logo muito larga (wordmark alongado) é limitada pela
                    # largura para não invadir o bloco de dados da empresa.
                    max_largura = 62 * mm
                    altura = altura_logo
                    if largura > max_largura:
                        largura = max_largura
                        altura = largura * (ag / lg) if lg else altura
                    self.drawImage(img, x_logo, topo_conteudo - altura,
                                   width=largura, height=altura, mask='auto')
                    desenhou_logo = True
                except Exception as e:  # imagem ilegível não derruba o PDF
                    logger.warning('[CRONOGRAMA-PDF] logo não pôde ser '
                                   'desenhada: %s', e)
            if not desenhou_logo:
                # Sem logo cadastrada, o nome da empresa ocupa o lugar dela —
                # em caixa-alta espaçada, no navy, para preencher a faixa em
                # vez de virar um texto miúdo perdido no canto (foi o que o
                # primeiro export real mostrou, e o sintoma era cadastro
                # vazio, não layout).
                # `setCharSpace` NÃO existe no Canvas — só no objeto de texto
                # (`beginText`). Chamá-lo no canvas levanta AttributeError e
                # derruba o download inteiro; foi o que os testes pegaram, num
                # caminho que o meu teste manual nunca tocou porque lá havia
                # logo cadastrada.
                texto = self.beginText(
                    margem, topo_conteudo - altura_logo + 3 * mm)
                texto.setFont(SANS_BOLD, 17)
                texto.setFillColor(C['navy'])
                texto.setCharSpace(1.6)
                texto.textOut((marca.get('nome') or '').upper()[:26])
                self.drawText(texto)

            # `.header .hright`: três linhas à direita, 8pt cinza com
            # `line-height: 1.5`, e a primeira em negrito navy a 8,6pt.
            direita = largura_pagina - margem
            y = topo_conteudo - 8.6
            self.setFont(SANS_BOLD, 8.6)
            self.setFillColor(C['navy'])
            self.drawRightString(direita, y, (marca.get('nome') or '')[:60])
            self.setFont(SANS, 8)
            self.setFillColor(C['cinza'])
            # Segunda linha: razão social e CNPJ juntos, como no papel oficial
            # ("Angelin Engenharia Ltda. · CNPJ 42.547.087/0001-61"). Sem razão
            # social cadastrada, sobra o CNPJ sozinho.
            segunda = ' · '.join(p for p in [
                marca.get('razao_social'),
                f"CNPJ {marca['cnpj']}" if marca.get('cnpj') else ''] if p)
            if segunda:
                y -= 8 * 1.5
                self.drawRightString(direita, y, segunda[:105])
            terceira = ' · '.join(p for p in [marca.get('endereco'),
                                              marca.get('website')] if p)
            if terceira:
                y -= 8 * 1.5
                self.drawRightString(direita, y, terceira[:105])

            # `.rule`: filete de 2,6pt a 4mm do cabeçalho — 34mm em laranja e
            # o resto em navy. É a assinatura da folha, e o que faltava aqui.
            linha_y = (topo_conteudo - altura_logo - FILETE_DISTANCIA_MM * mm
                       - FILETE_ESPESSURA_PT / 2)
            self.setLineWidth(FILETE_ESPESSURA_PT)
            self.setStrokeColor(C['laranja'])
            self.line(margem, linha_y, margem + FILETE_LARANJA_MM * mm, linha_y)
            self.setStrokeColor(C['navy'])
            self.line(margem + FILETE_LARANJA_MM * mm, linha_y,
                      largura_pagina - margem, linha_y)

        def _desenhar_rodape(self, total: int):
            """`.footer` + `.footbar` do kit.

            A `.footbar` é uma barra navy de 2mm colada no pé da página, de
            borda a borda (`left: 0; width: 210mm`) — ela SANGRA, e é por isso
            que não respeita a margem lateral. Era o elemento que faltava, e o
            que fazia a margem inferior parecer errada.

            Acima dela: `padding: 3mm 0 6mm`, fio superior no `--line`, texto
            de 7,6pt em cinza com o nome da empresa em navy negrito.
            """
            # A barra que sangra.
            self.setFillColor(C['navy'])
            self.rect(0, 0, largura_pagina, FOOTBAR_ALTURA_MM * mm,
                      stroke=0, fill=1)

            base_texto = (FOOTBAR_ALTURA_MM + 6) * mm
            self.setStrokeColor(C['fio'])
            self.setLineWidth(0.5)
            fio_y = base_texto + 7.6 + 3 * mm
            self.line(margem, fio_y, largura_pagina - margem, fio_y)

            # Esquerda: empresa em navy negrito, resto em cinza — como o
            # `.footer b { color: var(--navy) }` do kit.
            empresa = (marca.get('nome') or '')[:40]
            self.setFont(SANS_BOLD, 7.6)
            self.setFillColor(C['navy'])
            self.drawString(margem, base_texto, empresa)
            largura_empresa = self.stringWidth(empresa, SANS_BOLD, 7.6)
            self.setFont(SANS, 7.6)
            self.setFillColor(C['cinza'])
            self.drawString(margem + largura_empresa, base_texto,
                            f" · Cronograma de Obra — {obra.get('nome') or ''}"[:80])

            # Direita: cliente e a paginação, na ordem do kit.
            partes = [p for p in [obra.get('cliente'),
                                  f'pág. {self._pageNumber}/{total}'] if p]
            self.drawRightString(largura_pagina - margem, base_texto,
                                 ' · '.join(partes)[:80])

    return CanvasComMarca
