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

O layout vem de `layout veks.docx`: navy `#1E2A4C`, laranja `#E8620E`,
cinzas `#5A6472`/`#8A93A3`, preenchimento `#F4F6F9`, fio `#C9CED6`, título
serifado, cabeçalho com logo e rodapé com `pág. X/Y`. A forma é a mesma para
todo tenant; a marca sai de `ConfiguracaoEmpresa`.
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

# ── Paleta do layout (layout veks.docx) ──────────────────────────────────────
NAVY = '#1E2A4C'
LARANJA = '#E8620E'
CINZA_TEXTO = '#5A6472'
CINZA_FRACO = '#8A93A3'
PREENCHIMENTO = '#F4F6F9'
FIO = '#C9CED6'
BRANCO = '#FFFFFF'

# Georgia (a serifada do docx) não existe no servidor e não há TTF versionado
# no repositório. `Times-Roman` vem embutida na reportlab — serifada, sem
# risco de licença nem de deploy. Trocar por uma TTF é uma linha de
# `registerFont` no dia em que a diferença incomodar.
SERIFADA = 'Times-Roman'
SERIFADA_BOLD = 'Times-Bold'
SANS = 'Helvetica'
SANS_BOLD = 'Helvetica-Bold'

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


def montar_marca_tenant(admin_id: int) -> dict:
    """A identidade visual do tenant: nome, dados de contato e logo.

    A forma do documento é a mesma para todo tenant; o que varia é a marca.
    Preferência de logo: `logo_pdf_base64` (a específica para PDF) →
    `logo_base64`. Tenant sem `ConfiguracaoEmpresa` recebe o mesmo nome
    padrão que `cronograma_obra` usa ('Empresa'), em vez de erro.
    """
    from models import ConfiguracaoEmpresa

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        return {'nome': 'Empresa', 'cnpj': '', 'endereco': '', 'website': '',
                'logo': None}

    return {
        'nome': config.nome_empresa or 'Empresa',
        'cnpj': config.cnpj or '',
        'endereco': (config.endereco or '').replace('\n', ' ').strip(),
        'website': config.website or '',
        'logo': _logo_em_bytes(config.logo_pdf_base64 or config.logo_base64),
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

    buf = io.BytesIO()
    margem = 18 * mm
    # O topo abre espaço para a faixa de marca, desenhada pelo canvas em
    # todas as páginas; o rodapé, para o fio e a paginação.
    topo = 34 * mm
    base = 16 * mm

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

    est_titulo = ParagraphStyle('titulo', fontName=SERIFADA_BOLD, fontSize=15,
                                leading=18, textColor=colors.HexColor(NAVY),
                                spaceAfter=1)
    est_obra = ParagraphStyle('obra', fontName=SERIFADA, fontSize=11,
                              leading=14, textColor=colors.HexColor(NAVY))
    est_meta = ParagraphStyle('meta', fontName=SANS, fontSize=7.5, leading=10,
                              textColor=colors.HexColor(CINZA_TEXTO))
    est_celula = ParagraphStyle('celula', fontName=SANS, fontSize=7.5,
                                leading=9.5,
                                textColor=colors.HexColor('#22272F'))
    est_celula_pai = ParagraphStyle('celula_pai', parent=est_celula,
                                    fontName=SANS_BOLD,
                                    textColor=colors.HexColor(NAVY))
    est_vazio = ParagraphStyle('vazio', fontName=SANS, fontSize=9, leading=13,
                               textColor=colors.HexColor(CINZA_TEXTO))

    historia = [
        Paragraph('Cronograma da Obra', est_titulo),
        Paragraph(_titulo_da_obra(obra), est_obra),
        Spacer(1, 5 * mm),
        _faixa_metadados(obra, est_meta, doc.width),
        Spacer(1, 4 * mm),
    ]

    if not linhas:
        # Obra sem tarefa é situação normal (cronograma ainda não montado, ou
        # modo cliente numa obra sem cópia-cliente). Um PDF que diz isso é
        # melhor que um 500 ou que um arquivo com a tabela vazia.
        historia.append(Paragraph(
            'Nenhuma tarefa cadastrada neste cronograma.', est_vazio))
    else:
        historia.append(_tabela(linhas, doc.width, est_celula, est_celula_pai))

    doc.build(historia, canvasmaker=_canvas_com_marca(marca, obra))
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


def _titulo_da_obra(obra: dict) -> str:
    if obra.get('codigo'):
        return f"{_esc(obra['nome'])} · {_esc(obra['codigo'])}"
    return _esc(obra['nome'])


def _faixa_metadados(obra: dict, estilo, largura):
    """Faixa cinza-clara com cliente, período, progresso e emissão."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    periodo = TRACO
    if obra.get('data_inicio') and obra.get('data_fim'):
        periodo = (f"{_data(obra['data_inicio'])} a "
                   f"{_data(obra['data_fim'])}")

    itens = [
        ('Cliente', obra.get('cliente') or TRACO),
        ('Período', periodo),
        ('Progresso geral', f"{_percentual(obra.get('progresso_geral'))}"),
        ('Emitido em', _data(date.today())),
    ]
    if obra.get('modo_cliente'):
        itens.insert(1, ('Visão', 'Cronograma do cliente'))

    celulas = [Paragraph(f'<b>{rotulo}</b><br/>{_esc(valor)}', estilo)
               for rotulo, valor in itens]
    tabela = Table([celulas], colWidths=[largura / len(celulas)] * len(celulas))
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(PREENCHIMENTO)),
        ('BOX', (0, 0), (-1, -1), 0.3, colors.HexColor(FIO)),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor(FIO)),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return tabela


def _tabela(linhas, largura, est_celula, est_celula_pai):
    """A planilha de tarefas: `#`, Nome, Dur., Início, Término, %.

    A coluna `#` é o número de linha sequencial da grade
    (`templates/obras/cronograma.html:189`) — a mesma numeração que a coluna
    `Pred.` referencia. Não é EDT hierárquica: a hierarquia aparece pela
    indentação do nome e pelo negrito da tarefa-pai.
    """
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, TableStyle

    cabecalho = ['#', 'Nome da Tarefa', 'Dur.', 'Início', 'Término', '%']
    corpo = [cabecalho]
    estilo_extra = []

    for i, ln in enumerate(linhas, start=1):  # +1: linha 0 é o cabeçalho
        estilo_nome = est_celula_pai if ln['is_pai'] else est_celula
        nome = _nome_com_hierarquia(ln)
        corpo.append([
            str(ln['numero']),
            Paragraph(nome, estilo_nome),
            _duracao(ln),
            _data(ln['data_inicio']),
            _data(ln['data_fim']),
            _percentual_celula(ln),
        ])
        if ln['is_pai']:
            estilo_extra += [
                ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#EDEFF4')),
                ('FONTNAME', (0, i), (0, i), SANS_BOLD),
                ('FONTNAME', (2, i), (-1, i), SANS_BOLD),
                ('TEXTCOLOR', (0, i), (-1, i), colors.HexColor(NAVY)),
            ]

    tabela = LongTable(
        corpo, repeatRows=1,
        colWidths=[9 * mm, largura - 9 * mm - 13 * mm - 20 * mm - 20 * mm - 13 * mm,
                   13 * mm, 20 * mm, 20 * mm, 13 * mm],
    )
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(BRANCO)),
        ('FONTNAME', (0, 0), (-1, 0), SANS_BOLD),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('FONTNAME', (0, 1), (-1, -1), SANS),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#22272F')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor(PREENCHIMENTO)]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor(FIO)),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ] + estilo_extra))
    return tabela


def _nome_com_hierarquia(linha: dict) -> str:
    """Indentação por nível e losango laranja no marco.

    A indentação é feita com espaços não-quebráveis dentro do `Paragraph`
    (7pt por nível seria a alternativa via `leftIndent`, mas ela some quando
    o nome quebra em duas linhas, e o alinhamento da segunda linha é
    justamente o que faz a hierarquia ser legível).
    """
    recuo = '&nbsp;' * (4 * int(linha.get('nivel') or 0))
    nome = _esc(linha['nome'])
    if linha['is_marco']:
        return f'{recuo}<font color="{LARANJA}">&#9670;</font> {nome}'
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


def _canvas_com_marca(marca: dict, obra: dict):
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
    margem = 18 * mm
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
            y_base = altura_pagina - margem
            desenhou_logo = False
            if logo_bytes:
                try:
                    img = ImageReader(io.BytesIO(logo_bytes))
                    lg, ag = img.getSize()
                    altura = 12 * mm
                    largura = altura * (lg / ag) if ag else altura
                    # Logo muito larga (wordmark alongado) é limitada pela
                    # largura para não invadir o bloco de dados da empresa.
                    max_largura = 55 * mm
                    if largura > max_largura:
                        largura = max_largura
                        altura = largura * (ag / lg) if lg else altura
                    self.drawImage(img, margem, y_base - altura,
                                   width=largura, height=altura,
                                   mask='auto')
                    desenhou_logo = True
                except Exception as e:  # imagem ilegível não derruba o PDF
                    logger.warning('[CRONOGRAMA-PDF] logo não pôde ser '
                                   'desenhada: %s', e)
            if not desenhou_logo:
                self.setFont(SERIFADA_BOLD, 15)
                self.setFillColor(colors.HexColor(NAVY))
                self.drawString(margem, y_base - 11, marca.get('nome') or '')

            # Bloco de identificação, alinhado à direita
            self.setFont(SANS, 7)
            self.setFillColor(colors.HexColor(CINZA_TEXTO))
            direita = largura_pagina - margem
            partes = [marca.get('nome') or '']
            if marca.get('cnpj'):
                partes.append(f"CNPJ {marca['cnpj']}")
            segunda = ' · '.join(p for p in [marca.get('endereco'),
                                             marca.get('website')] if p)
            y = y_base - 3
            self.drawRightString(direita, y, ' · '.join(p for p in partes if p))
            if segunda:
                self.drawRightString(direita, y - 8.5, segunda[:110])

            # Fio abaixo da faixa
            self.setStrokeColor(colors.HexColor(FIO))
            self.setLineWidth(0.5)
            linha_y = altura_pagina - margem - 15 * mm
            self.line(margem, linha_y, largura_pagina - margem, linha_y)

        def _desenhar_rodape(self, total: int):
            y = 11 * mm
            self.setStrokeColor(colors.HexColor(FIO))
            self.setLineWidth(0.5)
            self.line(margem, y + 5, largura_pagina - margem, y + 5)
            self.setFont(SANS, 7.5)
            self.setFillColor(colors.HexColor(CINZA_FRACO))
            esquerda = (f"{marca.get('nome') or ''} · Cronograma — "
                        f"{obra.get('nome') or ''}")
            self.drawString(margem, y - 3, esquerda[:95])
            self.drawRightString(largura_pagina - margem, y - 3,
                                 f'pág. {self._pageNumber}/{total}')

    return CanvasComMarca
