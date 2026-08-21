# Manual Visual do RDO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um PDF passo a passo do RDO, com foto anotada de cada tela, que começa em **"o RDO é alimentado pelas atividades do cronograma"** e vai até **assinar** (e, por decisão D2, aprovar e retificar) — regenerável por três comandos quando a tela mudar.

**Architecture:** Reaproveita inteira a ferramenta do manual de compras (18/08): um **roteiro** (`Tela`/`Campo`/`Acao`) é a única lista de onde saem as caixas numeradas desenhadas **no DOM, ancoradas em seletor**, e a legenda do PDF; a captura **derruba o processo** se um seletor não casar; o cenário é **semeado** num tenant próprio e idempotente. Três coisas novas no motor, todas aditivas: ações `clicar` e `anexar` (modais e fotos), e duas marcas na `Tela` — `permanece` (a foto seguinte é da MESMA página, porque o formulário de RDO é preenchido em etapas) e `guarda_id` (o id do RDO só existe depois de salvar, então é lido da URL e injetado nas rotas seguintes). O gerador de PDF sai de dentro de `gerar_manual_compras.py` para um módulo parametrizado, usado pelos dois manuais.

**Tech Stack:** Python 3, Flask (app de pé em `localhost:5000`), SQLAlchemy, Playwright (Chromium via `preparar_bibliotecas()`), reportlab 4, Pillow 11, pytest.

**Spec:** Não há spec escrito. Decisões da conversa de 2026-08-21 com o Cássio: *"pdf com script passo a passo tirando print de tudo do rdo desde entender que o rdo é alimentado pelo cronograma as atividades ate assinar"*. D1 tenant próprio semeado; D2 ciclo de vida inteiro (submeter → reabrir → assinar → aprovar → retificar); D3 PDF + markdown em `docs/manual_rdo/`, PDF também em `static/docs/manual-rdo.pdf` e linkado do capítulo 23a.

## Global Constraints

- **Falhou, para.** Seletor que não casa, tela que não abre, login que falha → `SystemExit`/`MarcacaoQuebrada` com o nome do passo. Nunca `except Exception: continue` (📖 `scripts/capturar_manual_ciclo.py:76-79` é o contraexemplo que produziu manual com foto velha).
- **Uma lista só.** Caixa da figura e legenda do PDF saem do mesmo `Campo`. Nenhum dicionário paralelo indexado por slug.
- **Seletor, não coordenada.** Toda caixa é um seletor CSS medido no DOM (`anotar_captura.marcar`).
- **Cenário é dado, não achado.** `scripts/seed_manual_rdo.py` cria tudo de que as telas precisam, no tenant `manualrdo`, e é idempotente. Nenhum id fixo no roteiro: `resolver_ids()` lê do banco; ids criados durante a captura (o RDO) vêm da URL via `guarda_id`.
- **Não toca no tenant demo nem em nenhum outro.** Tudo escopado por `admin_id` do tenant `manualrdo`.
- **Chromium:** `capturar_manual_compras.preparar_bibliotecas()` resolve `LD_LIBRARY_PATH` (cache em `.cache/sige_ld_library_path`). Reutilizar por import — não copiar.
- **Servidor:** a captura roda contra `SIGE_BASE` (default `http://localhost:5000`), que serve o checkout principal com `--reload`. O seed escreve no mesmo banco (`DATABASE_URL`).
- Testes novos em `tests/`, nome `test_*.py`; os que tocam banco levam `pytestmark = pytest.mark.integration`; os de roteiro/motor rodam **sem** banco nem browser, como `tests/test_manual_compras_roteiro.py`.
- Commits pequenos, um por task, em português, com o "porquê".

---

## O que já existe, e não deve ser reinventado

| Peça | Onde | O que faz | Como este plano usa |
|---|---|---|---|
| Motor de captura anotada | `scripts/anotar_captura.py` | `Campo(numero, seletor, rotulo, obrigatorio, nota)`, `Acao(tipo, seletor, valor)`, `Tela(slug, titulo, papel, rota, resumo, campos, depois, atencao, recorte, acoes, ato, ato_resumo)`; `marcar(page, campos)` desenha e **levanta** se faltar; `executar(page, acoes)` com `TIPOS_DE_ACAO = ('preencher', 'escolher', 'marcar', 'submeter')` | Task 1 acrescenta `clicar`, `anexar`, `Tela.permanece`, `Tela.guarda_id` |
| Captura de compras | `scripts/capturar_manual_compras.py` | `preparar_bibliotecas()`, `entrar(page, username)`, laço `goto → acoes → marcar → recorte → screenshot` | `capturar_manual_rdo.py` importa as duas funções e repete o laço com `permanece`/`guarda_id` |
| Gerador de compras | `scripts/gerar_manual_compras.py` | estilos reportlab, `construir()` (capa, atos, figura, legenda, avisos), `markdown()` | Task 2 extrai para `scripts/manual_pdf.py` parametrizado; compras passa a chamar o módulo |
| Seed de compras | `scripts/seed_manual_compras.py` | `MARCA`, `SENHA`, `_pessoa()`, vínculo `UsuarioObra(papel=...)`, `--resumo`, idempotência | `seed_manual_rdo.py` segue a mesma forma |
| Teste de roteiro | `tests/test_manual_compras_roteiro.py` | `_PaginaFalsa` para exercitar `marcar` sem browser | mesmo molde para o roteiro do RDO e para as ações novas |

## As telas — inventário conferido em 21/08

Seletores conferidos nos templates (`templates/rdo/novo.html`, `templates/rdo/visualizar_rdo_moderno.html`, `templates/rdo/obras_index.html`, `templates/obras/cronograma.html`). `{chaves}` são resolvidas por `resolver_ids()` (seed) ou por `guarda_id` (captura).

| # | slug | papel | rota | o que mostra | seletores |
|---|---|---|---|---|---|
| 1 | `01_login` | anon | `/login` | entrar | `input[name="username"]`, `input[name="password"]`, `button[type="submit"]` |
| 2 | `02_cronograma` | encarregado | `/cronograma/obra/{obra_id}` | **de onde o RDO vem**: as atividades, a coluna Qtd/Un (quem tem medida aponta por quantidade), Responsável (empresa/terceiros) e **% Realizado — "calculado automaticamente pelos apontamentos do RDO"** (é o `title` do cabeçalho) | `thead.cronograma-thead th.th-nome`, `th[title^="Quantidade prevista"]`, `th[title^="Responsável"]`, `th[title^="Progresso realizado"]`; recorte `#leftPane` |
| 3 | `03_rdos_da_obra` | encarregado | `/rdos` | o painel "RDOs por obra" e o botão Novo RDO | `a[href*="/rdos?obra_id={obra_id}"]`, `a[href*="/rdo/novo"]` |
| 4 | `04_cabecalho` | encarregado | `/rdo/novo?obra_id={obra_id}` | obra, data, clima, temperatura | `#obra_id`, `#data_relatorio`, `#clima_geral`, `#temperatura_media` |
| 5 | `05_atividades` | *permanece* | — | as atividades do cronograma dentro do RDO; onde se aponta quantidade, percentual e marco; os botões de equipe e terceiro em cada linha | `#cronogramaTarefasRDO`, `#qty_tarefa_{t_blocos}`, `#pct_tarefa_{t_pilares}`, `#chk_marco_{t_marco}`, `#btn-equipe-{t_blocos}`, `#btn-terceiro-{t_estacas}` |
| 6 | `06_equipe_lista` | *permanece* | — | o modal de equipe: **só pessoal operacional** (a Ana Escritório não aparece) | ação `clicar #btn-equipe-{t_blocos}`; `#modalFuncFiltro`, `#modalFuncLista` |
| 7 | `07_equipe_horas` | *permanece* | — | duas pessoas escolhidas e as horas de cada uma | ações `clicar #modalFuncLista button:has-text("Davi Montador")`, `clicar #modalFuncLista button:has-text("Pedro Ajudante")`; `#modalEquipeSelecionada`, `input[name="func_{t_blocos}_{f_davi}_horas"]`; depois `preencher` 8 e 8 e `clicar #modalEquipeTarefa button.btn-primary` |
| 8 | `08_terceiro` | *permanece* | — | o modal de terceiro numa atividade de terceiros: nome do cadastro, **quantidade de pessoas**, horas, produção | ação `clicar #btn-terceiro-{t_estacas}`; `#sub_subempreiteiro_id`, `#sub_qtd_pessoas`, `#sub_horas`, `#sub_qtd_prod`; preencher 11 / 9 / 6 e `clicar #modalSubempreitada button.btn-primary` |
| 9 | `09_avanco` | *permanece* | — | quantidade de **hoje** na tarefa por quantidade, percentual **acumulado** na tarefa por percentual, marco em branco | `preencher #qty_tarefa_{t_blocos}` = 2, `preencher #pct_tarefa_{t_pilares}` = 15; marcar os três campos |
| 10 | `10_ocorrencias` | *permanece* | — | uma ocorrência com horário e efeito | `clicar` no botão de adicionar de `#ocorr-rows`; `[name="ocorr_tipo[]"]`, `[name="ocorr_severidade[]"]`, `[name="ocorr_descricao[]"]` |
| 11 | `11_fotos` | *permanece* | — | três fotos anexadas; observações finais | `anexar #fileInputNovoGal` (3 PNGs gerados); `#previewContainerNovo`, `#observacoes_finais` |
| 12 | `12_salvar_rascunho` | *permanece*, `guarda_id=rdo_id` | — | o RDO salvo em **rascunho**: não lança custo, não alimenta o cronograma | `submeter #btnFinalizarRDO` → cai em `/rdo/{rdo_id}`; `.estado-badge` |
| 13 | `13_submeter` | encarregado | `/rdo/{rdo_id}` | **Submeter**: custos lançados, cliente enxerga | `submeter form[action$="/finalizar"] button[type="submit"]`; `.estado-badge` |
| 14 | `14_reabrir` | gestor | `/rdo/{rdo_id}` | o gestor **reabre** (motivo obrigatório, vem de um `prompt`) | `submeter form[action$="/reabrir"] button[type="submit"]` (a captura aceita o `dialog` com o motivo); `.estado-badge` |
| 15 | `15_submeter_de_novo` | encarregado | `/rdo/{rdo_id}` | corrigiu, submete de novo | `submeter form[action$="/finalizar"] button[type="submit"]` |
| 16 | `16_assinar` | encarregado | `/rdo/{rdo_id}` | **Assinar**: imutável | `submeter form[action$="/assinar"] button[type="submit"]`; `.estado-badge` |
| 17 | `17_aprovar` | gestor | `/rdo/{rdo_id}` | **Aprovar**: aceite do gestor | `submeter form[action$="/aprovar"] button[type="submit"]`; `.estado-badge` |
| 18 | `18_retificar` | gestor, `guarda_id=rdo_retif_id` | `/rdo/{rdo_id}` | **Retificar**: nasce um novo RDO da mesma data; o original fica *retificado* | `submeter form[action$="/retificar"] button[type="submit"]` (dialog com o motivo) → cai em `/rdo/{rdo_retif_id}`; `.estado-badge` |

Permissões (📖 `utils/autorizacao.py:194-200`): `submeter`/`assinar` exigem `pode_apontar_na_obra` → GESTOR ou APONTADOR; `aprovar`/`reabrir` exigem `pode_editar_obra` → GESTOR. ADMIN é GESTOR implícito. Por isso duas pessoas: **encarregado** (APONTADOR) e **gestor** (GESTOR).

Dados que o tenant precisa ter (Task 3): obra com cronograma interno (`is_cliente=False`) de **4 folhas**: uma por quantidade da empresa (`t_blocos`), uma de terceiros com quantidade (`t_estacas`), uma por percentual (`t_pilares`, sem `quantidade_total`), um marco (`t_marco`, `is_marco=True`); **3 funcionários operacionais** + **1 administrativo** (para mostrar o filtro); **1 subempreiteiro**. 📖 `services/cronograma_apontamento_service._modo_deduzido`: sem `modo_apontamento`, quantidade > 0 **e** unidade não vazia ⇒ 'quantidade'; senão 'percentual'. A flag `rdo_percentual_livre` fica **desligada** (default).

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `scripts/anotar_captura.py` (modificar) | Ações `clicar` e `anexar`; `Tela.permanece: bool = False`; `Tela.guarda_id: str = ''`. |
| `scripts/manual_pdf.py` (criar) | `construir_pdf(roteiro, *, pdf, shots, titulo, subtitulo, intro, quem)` e `escrever_markdown(roteiro, *, md, titulo, gerador, roteiro_nome)` — extraídos de `gerar_manual_compras.py`. |
| `scripts/gerar_manual_compras.py` (modificar) | Passa a chamar `manual_pdf` com os textos de compras. Mesmo PDF, mesmo markdown. |
| `scripts/seed_manual_rdo.py` (criar) | Tenant `manualrdo`: 3 pessoas, vínculos, flags, obra, cliente, funções, funcionários, subempreiteiro, cronograma. `--resumo`, `--limpar-rdos`. |
| `scripts/roteiro_manual_rdo.py` (criar) | `resolver_ids()`, `montar(ids)`, `telas(ids=None)` — as 18 telas. |
| `scripts/capturar_manual_rdo.py` (criar) | Laço de captura com `permanece`, `guarda_id`, `dialog` e fotos geradas. |
| `scripts/gerar_manual_rdo.py` (criar) | `docs/manual_rdo/Manual_RDO_SIGE.pdf`, `docs/manual_rdo/manual-rdo.md`, cópia em `static/docs/manual-rdo.pdf`. |
| `manual/23a_rdo_padrao_preenchimento.md` (modificar) | Link para o PDF no topo. |
| `tests/test_manual_rdo_roteiro.py` (criar) | Motor (ações novas) e invariantes do roteiro — sem banco, sem browser. |
| `tests/test_manual_rdo_seed.py` (criar) | Seed idempotente e o feed `tarefas-rdo` com os 4 modos — integração. |

---

### Task 1: Motor — `clicar`, `anexar`, `permanece`, `guarda_id`

O formulário de RDO é preenchido em etapas na **mesma página** (modais, campos, fotos) e o id do RDO só existe depois do salvar. O motor de compras não precisava disso. Quatro acréscimos, todos com default que mantém o comportamento de compras.

**Files:**
- Modify: `scripts/anotar_captura.py` (`TIPOS_DE_ACAO` linha 75, `class Tela` linhas 78-102, `executar` linhas 166-193)
- Test: `tests/test_manual_rdo_roteiro.py` (criar)

**Interfaces:**
- Produces: `Acao('clicar', seletor)` — `page.click(seletor)` + 400 ms, **sem** esperar navegação; `Acao('anexar', seletor, valor)` — `page.set_input_files(seletor, valor.split(';'))`; `Tela.permanece: bool` — a captura não faz `goto`; `Tela.guarda_id: str` — depois da foto, a captura lê `/rdo/(\d+)` da URL e guarda em `ctx[guarda_id]`. Consumidos pelas Tasks 4 e 5.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_manual_rdo_roteiro.py`:

```python
"""Motor de captura — o que o manual do RDO acrescentou — e o roteiro do RDO.

Sem banco, sem browser: exercita a lista e o guarda, como
tests/test_manual_compras_roteiro.py. Plano:
docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from anotar_captura import Acao, MarcacaoQuebrada, Tela, executar


class _PaginaFalsa:
    """O mínimo de `page` que `executar` usa, com registro do que foi chamado."""

    def __init__(self, existe=True):
        self.existe = existe
        self.chamadas = []

    def query_selector(self, seletor):
        return object() if self.existe else None

    def click(self, seletor):
        self.chamadas.append(('click', seletor))

    def set_input_files(self, seletor, arquivos):
        self.chamadas.append(('files', seletor, tuple(arquivos)))

    def wait_for_timeout(self, ms):
        self.chamadas.append(('wait', ms))

    def wait_for_load_state(self, estado):
        self.chamadas.append(('load', estado))


def test_clicar_clica_sem_esperar_navegacao():
    pagina = _PaginaFalsa()
    executar(pagina, [Acao('clicar', '#btn-equipe-7')])
    assert ('click', '#btn-equipe-7') in pagina.chamadas
    assert not any(c[0] == 'load' for c in pagina.chamadas), \
        'clicar abre modal na MESMA página — não pode esperar navegação'


def test_anexar_manda_os_arquivos_separados_por_ponto_e_virgula():
    pagina = _PaginaFalsa()
    executar(pagina, [Acao('anexar', '#fileInputNovoGal', '/tmp/a.png;/tmp/b.png')])
    assert ('files', '#fileInputNovoGal', ('/tmp/a.png', '/tmp/b.png')) in pagina.chamadas


def test_acao_nova_tambem_para_se_o_seletor_nao_existe():
    pagina = _PaginaFalsa(existe=False)
    with pytest.raises(MarcacaoQuebrada):
        executar(pagina, [Acao('clicar', '#sumiu')])
    with pytest.raises(MarcacaoQuebrada):
        executar(pagina, [Acao('anexar', '#sumiu', '/tmp/a.png')])


def test_tela_nasce_sem_permanecer_e_sem_guardar_id():
    """Os defaults mantêm o roteiro de compras exatamente como era."""
    t = Tela(slug='x', titulo='X', papel='anon', rota='/x', resumo='x')
    assert t.permanece is False
    assert t.guarda_id == ''
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_roteiro.py -q`

Esperado: **4 failed** — `MarcacaoQuebrada: tipo desconhecido 'clicar'` nos dois primeiros, `AttributeError`/`TypeError` em `permanece`.

- [ ] **Step 3: Acrescentar as ações e os campos**

Em `scripts/anotar_captura.py`:

```python
TIPOS_DE_ACAO = ('preencher', 'escolher', 'marcar', 'submeter', 'clicar', 'anexar')
```

Na `class Tela`, depois de `ato_resumo: str = ''`:

```python
    # Manual do RDO (21/08). O formulário de RDO é preenchido em ETAPAS na
    # mesma página — modal de equipe, modal de terceiro, avanço, fotos —, e
    # cada etapa merece a sua foto. `permanece=True` diz à captura para NÃO
    # navegar: a foto é do estado em que a tela anterior deixou a página.
    permanece: bool = False
    # O id do RDO só existe depois de salvar. `guarda_id='rdo_id'` manda a
    # captura ler `/rdo/<n>` da URL depois desta tela e guardar em ctx['rdo_id'],
    # que as rotas seguintes usam via `{rdo_id}`.
    guarda_id: str = ''
```

Em `executar`, trocar o `else:` final por:

```python
        elif a.tipo == 'clicar':
            # Abre modal / acrescenta linha: fica na mesma página, então NÃO
            # espera navegação — esperar `load` aqui pendura até o timeout.
            page.click(a.seletor)
            page.wait_for_timeout(400)
        elif a.tipo == 'anexar':
            # Vários arquivos separados por ';' — um input[type=file] multiple.
            page.set_input_files(a.seletor, a.valor.split(';'))
            page.wait_for_timeout(400)
        else:                                  # submeter
            page.click(a.seletor)
            page.wait_for_load_state('domcontentloaded')
            page.wait_for_timeout(900)         # o flash é renderizado no servidor
```

- [ ] **Step 4: Rodar os testes — novos e os de compras**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_roteiro.py tests/test_manual_compras_roteiro.py -q`

Esperado: **todos PASSAM.**

- [ ] **Step 5: Commit**

```bash
git add scripts/anotar_captura.py tests/test_manual_rdo_roteiro.py
git commit -m "feat(captura): acoes clicar/anexar e Tela.permanece/guarda_id para formularios em etapas"
```

---

### Task 2: Gerador de PDF parametrizado (`scripts/manual_pdf.py`)

`gerar_manual_compras.py` tem os estilos, a capa, a figura com legenda e os avisos — tudo o que o RDO precisa, preso a textos e caminhos de compras. Sai para um módulo; compras continua gerando o mesmo PDF.

**Files:**
- Create: `scripts/manual_pdf.py`
- Modify: `scripts/gerar_manual_compras.py` (linhas 28-215: constantes, estilos, `construir`, `markdown`)
- Test: `tests/test_manual_rdo_roteiro.py` (acrescentar)

**Interfaces:**
- Produces:
  ```python
  def construir_pdf(roteiro, *, pdf: Path, shots: Path, titulo: str, subtitulo: str,
                    intro: list[str], quem: dict[str, str], autor: str = 'SIGE') -> None
  def escrever_markdown(roteiro, *, md: Path, titulo: str, gerador: str, roteiro_nome: str) -> None
  ```
  `roteiro` é a lista de `Tela`. `construir_pdf` levanta `SystemExit('faltam capturas: ...')` se faltar PNG de algum slug. `quem` mapeia `papel → "quem faz"` para o rodapé de cada passo.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar em `tests/test_manual_rdo_roteiro.py`:

```python
def test_construir_pdf_monta_um_manual_de_uma_tela(tmp_path):
    from PIL import Image
    from manual_pdf import construir_pdf, escrever_markdown
    from anotar_captura import Campo

    shots = tmp_path / 'shots'
    shots.mkdir()
    Image.new('RGB', (640, 400), (240, 240, 240)).save(shots / 'x.png')
    roteiro = [Tela(slug='x', titulo='Uma tela', papel='anon', rota='/x',
                    resumo='Resumo.', campos=[Campo(1, '#a', 'Campo A', True)],
                    depois='Depois.', atencao='Atenção.',
                    ato='Ato único', ato_resumo='Só um ato.')]
    pdf, md = tmp_path / 'm.pdf', tmp_path / 'm.md'

    construir_pdf(roteiro, pdf=pdf, shots=shots, titulo='T', subtitulo='S',
                  intro=['Linha.'], quem={'anon': 'qualquer pessoa'})
    escrever_markdown(roteiro, md=md, titulo='T', gerador='g.py', roteiro_nome='r.py')

    assert pdf.exists() and pdf.stat().st_size > 1000
    texto = md.read_text(encoding='utf-8')
    assert '## Ato único' in texto and '![Uma tela](screenshots/x.png)' in texto
    assert '| 1 | Campo A * |' in texto


def test_construir_pdf_recusa_foto_faltando(tmp_path):
    from manual_pdf import construir_pdf
    roteiro = [Tela(slug='sem_foto', titulo='X', papel='anon', rota='/x', resumo='x')]
    with pytest.raises(SystemExit) as erro:
        construir_pdf(roteiro, pdf=tmp_path / 'm.pdf', shots=tmp_path, titulo='T',
                      subtitulo='S', intro=[], quem={})
    assert 'sem_foto' in str(erro.value)
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_roteiro.py -q -k pdf`

Esperado: **2 failed** — `ModuleNotFoundError: manual_pdf`.

- [ ] **Step 3: Criar `scripts/manual_pdf.py`**

Mover de `gerar_manual_compras.py` as constantes de cor/margem, os estilos (`est`), `_imagem`, `_tabela_legenda`, `_aviso`, e o corpo de `construir`/`markdown`, parametrizando o que era de compras:

```python
#!/usr/bin/env python3
"""Monta um manual visual (PDF + markdown) a partir de um roteiro e das capturas.

Extraído de `gerar_manual_compras.py` em 21/08 para servir também ao manual do
RDO. A regra que veio junto: a legenda numerada embaixo de cada figura sai do
MESMO `Campo` que desenhou a caixa — não existem duas listas para divergir.
"""
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

AZUL = colors.HexColor('#1a3d6e')
LARANJA = colors.HexColor('#e8590c')
CINZA = colors.HexColor('#5a6673')
PAGE_W, PAGE_H = A4
MARGEM = 1.7 * cm
UTIL = PAGE_W - 2 * MARGEM

est = getSampleStyleSheet()
# ... (os mesmos ParagraphStyle de gerar_manual_compras.py: Capa, CapaSub, Ato,
#      AtoSub, Passo, Corpo, Legenda, Papel — copiar tal qual)


def _imagem(caminho, largura):
    # copiar de gerar_manual_compras.py
    ...


def _tabela_legenda(tela):
    # copiar de gerar_manual_compras.py
    ...


def _aviso(texto, cor_fundo, cor_borda, rotulo):
    # copiar de gerar_manual_compras.py
    ...


def construir_pdf(roteiro, *, pdf, shots, titulo, subtitulo, intro, quem, autor='SIGE'):
    pdf, shots = Path(pdf), Path(shots)
    faltando = [t.slug for t in roteiro if not (shots / f'{t.slug}.png').exists()]
    if faltando:
        raise SystemExit('faltam capturas: ' + ', '.join(faltando)
                         + '\nRode a captura antes — e não monte o manual com foto velha.')
    pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                            topMargin=MARGEM, bottomMargin=MARGEM, title=titulo, author=autor)
    fluxo = [Spacer(1, 5 * cm), Paragraph(titulo, est['Capa']),
             Paragraph(subtitulo, est['CapaSub']), Spacer(1, 1.2 * cm)]
    fluxo += [Paragraph(p, est['Corpo']) for p in intro]
    fluxo.append(PageBreak())
    for i, tela in enumerate(roteiro):
        # mesmo corpo do laço de gerar_manual_compras.construir, com
        # `quem.get(tela.papel, tela.papel)` no lugar do dicionário local
        ...
    doc.build(fluxo)


def escrever_markdown(roteiro, *, md, titulo, gerador, roteiro_nome):
    # mesmo corpo de gerar_manual_compras.markdown, com título/gerador/roteiro
    # vindos dos parâmetros
    ...
```

(Os `...` acima são **o corpo existente** de `gerar_manual_compras.py`, movido sem alteração de lógica — copiar linha a linha das funções de mesmo nome; o único ponto que muda é a origem dos textos.)

- [ ] **Step 4: `gerar_manual_compras.py` passa a usar o módulo**

Substituir as constantes de estilo, `_imagem`, `_tabela_legenda`, `_aviso`, `construir` e `markdown` por:

```python
from manual_pdf import construir_pdf, escrever_markdown
from roteiro_manual_compras import telas

RAIZ = Path('docs/manual_compras')
SHOTS = RAIZ / 'screenshots'
PDF = RAIZ / 'Manual_Compras_SIGE.pdf'
MD = RAIZ / 'manual-compras.md'

QUEM = {'anon': 'qualquer pessoa', 'solicitante': 'o encarregado da obra',
        'gestor': 'a gerência', 'comprador': 'o comprador',
        'admin': 'o administrador', 'financeiro': 'o financeiro'}
INTRO = ['Este manual segue uma compra inteira, na ordem em que ela acontece: o '
         'encarregado pede, a gerência aprova, o comprador negocia e o financeiro '
         'paga. Em cada tela, as caixas numeradas marcam o que precisa ser preenchido.',
         'Os campos marcados com <font color="#c92a2a">*</font> são obrigatórios.']


def main():
    roteiro = telas()
    construir_pdf(roteiro, pdf=PDF, shots=SHOTS, titulo='Compras, do pedido ao pagamento',
                  subtitulo='Manual de uso do SIGE', intro=INTRO, quem=QUEM)
    escrever_markdown(roteiro, md=MD, titulo='Compras, do pedido ao pagamento',
                      gerador='scripts/gerar_manual_compras.py',
                      roteiro_nome='scripts/roteiro_manual_compras.py')
    print(f'ok: {PDF} e {MD}')


if __name__ == '__main__':
    main()
```

Conferir que o `main()` antigo não fazia nada além de `construir()` + `markdown()` + print (`grep -n "def main" -A8 scripts/gerar_manual_compras.py` antes de apagar).

- [ ] **Step 5: Rodar os testes e regerar o manual de compras**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_roteiro.py tests/test_manual_compras_roteiro.py -q`
Esperado: **todos PASSAM.**

Run: `cp docs/manual_compras/manual-compras.md /tmp/claude-1000/-home-runner-workspace/d5a46dab-89eb-4b97-808d-0e37f37724d3/scratchpad/manual-compras-antes.md && .pythonlibs/bin/python scripts/gerar_manual_compras.py && diff /tmp/claude-1000/-home-runner-workspace/d5a46dab-89eb-4b97-808d-0e37f37724d3/scratchpad/manual-compras-antes.md docs/manual_compras/manual-compras.md && echo "markdown idêntico"`
Esperado: `ok: ...` e **"markdown idêntico"** (o PDF muda só no timestamp interno; o markdown é a prova de que a lógica não mudou).

- [ ] **Step 6: Commit**

```bash
git add scripts/manual_pdf.py scripts/gerar_manual_compras.py tests/test_manual_rdo_roteiro.py
git commit -m "refactor(manual): gerador de PDF/markdown sai de compras para manual_pdf.py, parametrizado"
```

---

### Task 3: Seed — o tenant `manualrdo`

**Files:**
- Create: `scripts/seed_manual_rdo.py`
- Test: `tests/test_manual_rdo_seed.py` (criar)

**Interfaces:**
- Produces: `MARCA = 'manualrdo'`, `SENHA = 'Manual@2026'`, `PESSOAS` (lista de tuplas `(chave, username, nome, cargo)` com chaves `admin`, `encarregado`, `gestor`), `semear() -> Usuario` (o admin), `limpar_rdos(admin_id) -> int`, `resumo(admin) -> dict` com as chaves `obra_id`, `t_blocos`, `t_estacas`, `t_pilares`, `t_marco`, `f_davi`, `f_pedro`, `sub_id`. Usernames: `manualrdo_admin`, `manualrdo_encarregado`, `manualrdo_gestor`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_manual_rdo_seed.py`:

```python
"""O cenário do manual do RDO é DADO: o seed cria tudo, duas vezes dá o mesmo.

Plano: docs/superpowers/plans/2026-08-21-manual-visual-rdo.md
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

import main  # noqa: F401 — registra os blueprints
from app import app
from models import (Funcionario, PapelObra, Subempreiteiro, TarefaCronograma,
                    Usuario, UsuarioObra)
from test_cronograma_endpoints_m05 import _client_como

pytestmark = pytest.mark.integration


def _contagens(admin_id, obra_id):
    return {
        'tarefas': TarefaCronograma.query.filter_by(obra_id=obra_id, ativa=True).count(),
        'funcionarios': Funcionario.query.filter_by(admin_id=admin_id).count(),
        'subempreiteiros': Subempreiteiro.query.filter_by(admin_id=admin_id).count(),
        'vinculos': UsuarioObra.query.filter_by(obra_id=obra_id).count(),
    }


def test_seed_e_idempotente_e_monta_o_cenario_inteiro():
    from seed_manual_rdo import resumo, semear
    with app.app_context():
        admin = semear()
        ids = resumo(admin)
        antes = _contagens(admin.id, ids['obra_id'])
        admin2 = semear()
        depois = _contagens(admin2.id, ids['obra_id'])
    assert admin2.id == admin.id
    assert antes == depois
    assert antes['tarefas'] == 6          # 2 fases + 4 folhas
    assert antes['funcionarios'] == 4     # 3 operacionais + 1 administrativo
    assert antes['subempreiteiros'] == 1
    assert antes['vinculos'] == 2         # encarregado APONTADOR, gestor GESTOR


def test_encarregado_aponta_e_gestor_edita():
    from seed_manual_rdo import resumo, semear
    with app.app_context():
        admin = semear()
        ids = resumo(admin)
        enc = Usuario.query.filter_by(username='manualrdo_encarregado').one()
        ges = Usuario.query.filter_by(username='manualrdo_gestor').one()
        papeis = {v.usuario_id: v.papel for v in
                  UsuarioObra.query.filter_by(obra_id=ids['obra_id']).all()}
    assert papeis[enc.id] == PapelObra.APONTADOR
    assert papeis[ges.id] == PapelObra.GESTOR


def test_feed_do_rdo_traz_as_quatro_folhas_com_o_modo_certo():
    """É o que a tela 05 fotografa: quantidade, terceiros, percentual e marco."""
    from seed_manual_rdo import resumo, semear
    with app.app_context():
        admin = semear()
        ids = resumo(admin)
        enc_id = Usuario.query.filter_by(username='manualrdo_encarregado').one().id
    client = _client_como(enc_id)
    r = client.get(f"/cronograma/obra/{ids['obra_id']}/tarefas-rdo")
    assert r.status_code == 200, r.get_data(as_text=True)
    corpo = r.get_json()
    tarefas = corpo.get('tarefas') if isinstance(corpo, dict) else corpo
    por_id = {t['id']: t for t in tarefas}
    assert ids['t_blocos'] in por_id and ids['t_estacas'] in por_id
    assert ids['t_pilares'] in por_id and ids['t_marco'] in por_id
    assert por_id[ids['t_estacas']]['responsavel'] == 'terceiros'
    assert por_id[ids['t_marco']].get('is_marco') is True
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_seed.py -q`
Esperado: **3 failed** — `ModuleNotFoundError: seed_manual_rdo`.

- [ ] **Step 3: Conferir a forma do JSON de `tarefas-rdo`**

Run: `sed -n '2549,2640p' cronograma_views.py | grep -nE "jsonify|'id'|'responsavel'|'is_marco'|'modo'|'nome'"`

Anotar as chaves reais; se o JSON não trouxer `is_marco`/`responsavel` com esses nomes, **ajustar o teste** para as chaves existentes (o teste existe para fixar o contrato que a tela 05 usa, não para inventar um).

- [ ] **Step 4: Escrever `scripts/seed_manual_rdo.py`**

```python
#!/usr/bin/env python3
"""Cenário determinístico para o manual visual do RDO — 2026-08-21.

Uso:
    .pythonlibs/bin/python scripts/seed_manual_rdo.py               # cria/recria
    .pythonlibs/bin/python scripts/seed_manual_rdo.py --resumo      # mostra os ids
    .pythonlibs/bin/python scripts/seed_manual_rdo.py --limpar-rdos # apaga os RDOs do tenant

Mesma regra do seed de compras: o cenário é DADO, não achado. Tudo no tenant
`manualrdo`, idempotente, e nenhum id fixo — quem precisa de id lê `resumo()`.

O QUE ELE MONTA. Um tenant com cronograma v2 ligado; três pessoas (admin,
encarregado APONTADOR, gestor GESTOR); uma obra com cronograma interno de duas
fases e quatro folhas — uma por quantidade (empresa), uma de terceiros com
quantidade, uma por percentual e um marco —, três funcionários operacionais,
um administrativo (para a tela do filtro) e um subempreiteiro.
"""
import argparse
import os
import sys
from datetime import date

os.environ.setdefault('SIGE_BOOT_DDL', '0')
os.environ.setdefault('SIGE_ENABLE_DEMO_SEED', 'false')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MARCA = 'manualrdo'
SENHA = 'Manual@2026'
PESSOAS = [
    ('admin',       f'{MARCA}_admin',       'Beatriz Campos', 'Administradora'),
    ('encarregado', f'{MARCA}_encarregado', 'Mateus Lira',    'Encarregado da obra'),
    ('gestor',      f'{MARCA}_gestor',      'Carla Nunes',    'Gestora da obra'),
]
OBRA_NOME = 'Galpão Logístico Vila Norte'
OBRA_CODIGO = 'MRDO-01'
FUNCOES = [('Montador', True), ('Soldador', True), ('Auxiliar Administrativo', False)]
FUNCIONARIOS = [  # (codigo, nome, funcao)
    ('MR01', 'Davi Montador', 'Montador'),
    ('MR02', 'Lucas Soldador', 'Soldador'),
    ('MR03', 'Pedro Ajudante', 'Montador'),
    ('MR04', 'Ana Escritório', 'Auxiliar Administrativo'),
]
SUBEMPREITEIRO = ('Abraão Fundações', 'Fundações')
# (chave, nome, pai, ordem, inicio, fim, quantidade, unidade, responsavel, marco)
TAREFAS = [
    ('fundacoes', 'Fundações',                                None,        0, date(2026, 8, 3),  date(2026, 12, 30), None, None, 'empresa',   False),
    ('t_estacas', 'Estacas hélice contínua',                  'fundacoes', 1, date(2026, 8, 3),  date(2026, 12, 30), 120.0, 'un', 'terceiros', False),
    ('t_blocos',  'Blocos de coroamento',                     'fundacoes', 2, date(2026, 8, 10), date(2026, 12, 30), 24.0,  'un', 'empresa',   False),
    ('estrutura', 'Estrutura metálica',                       None,        3, date(2026, 8, 17), date(2026, 12, 30), None, None, 'empresa',   False),
    ('t_pilares', 'Montagem de pilares',                      'estrutura', 4, date(2026, 8, 17), date(2026, 12, 30), None, None, 'empresa',   False),
    ('t_marco',   'Liberação da estrutura pela fiscalização', 'estrutura', 5, date(2026, 12, 30), date(2026, 12, 30), None, None, 'empresa',  True),
]


def _pessoa(chave, username, nome, admin_id=None):
    """Encontra ou cria. NÃO reescreve a senha de quem já existe."""
    from werkzeug.security import generate_password_hash
    from app import db
    from models import TipoUsuario, Usuario
    u = Usuario.query.filter_by(username=username).first()
    if u:
        return u
    u = Usuario(username=username, email=f'{username}@dev.local', nome=nome,
                password_hash=generate_password_hash(SENHA),
                tipo_usuario=TipoUsuario.ADMIN if chave == 'admin' else TipoUsuario.FUNCIONARIO,
                admin_id=admin_id, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    return u


def _flags(admin):
    from app import db
    from models import ConfiguracaoEmpresa
    from scripts.flag_cronograma_mpp import definir_flag
    definir_flag(admin.id, True)
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin.id, nome_empresa='Vila Norte Construções')
        db.session.add(cfg)
    cfg.cronograma_editor_v2 = True
    db.session.commit()


def _obra(admin):
    from app import db
    from models import Cliente, Obra
    cliente = Cliente.query.filter_by(admin_id=admin.id, nome='Logis Norte Ltda').first()
    if cliente is None:
        cliente = Cliente(admin_id=admin.id, nome='Logis Norte Ltda',
                          email=f'{MARCA}_cliente@dev.local', telefone='11999990000')
        db.session.add(cliente)
        db.session.flush()
    obra = Obra.query.filter_by(admin_id=admin.id, codigo=OBRA_CODIGO).first()
    if obra is None:
        obra = Obra(nome=OBRA_NOME, codigo=OBRA_CODIGO, admin_id=admin.id,
                    cliente_id=cliente.id, status='Em andamento',
                    data_inicio=date(2026, 8, 3), ativo=True)
        db.session.add(obra)
        db.session.flush()
    return obra


def _vinculos(admin, obra, pessoas):
    from app import db
    from models import PapelObra, UsuarioObra
    for chave, papel in (('encarregado', PapelObra.APONTADOR), ('gestor', PapelObra.GESTOR)):
        u = pessoas[chave]
        v = UsuarioObra.query.filter_by(usuario_id=u.id, obra_id=obra.id).first()
        if v is None:
            v = UsuarioObra(usuario_id=u.id, obra_id=obra.id, admin_id=admin.id)
            db.session.add(v)
        v.papel = papel
        v.ativo = True
    db.session.commit()


def _pessoal(admin):
    from app import db
    from models import Funcao, Funcionario
    funcoes = {}
    for nome, operacional in FUNCOES:
        f = Funcao.query.filter_by(admin_id=admin.id, nome=nome).first()
        if f is None:
            f = Funcao(nome=nome, admin_id=admin.id, salario_base=0.0)
            db.session.add(f)
            db.session.flush()
        f.operacional = operacional
        funcoes[nome] = f
    ids = {}
    for i, (codigo, nome, funcao) in enumerate(FUNCIONARIOS, start=1):
        fx = Funcionario.query.filter_by(admin_id=admin.id, codigo=codigo).first()
        if fx is None:
            fx = Funcionario(codigo=codigo, nome=nome, cpf=f'{admin.id:09d}{i:02d}',
                             data_admissao=date(2026, 8, 3), admin_id=admin.id,
                             funcao_id=funcoes[funcao].id, ativo=True, salario=3200.0)
            db.session.add(fx)
            db.session.flush()
        ids[nome] = fx.id
    db.session.commit()
    return ids


def _subempreiteiro(admin):
    from app import db
    from models import Subempreiteiro
    nome, esp = SUBEMPREITEIRO
    s = Subempreiteiro.query.filter_by(admin_id=admin.id, nome=nome).first()
    if s is None:
        s = Subempreiteiro(admin_id=admin.id, nome=nome, especialidade=esp, ativo=True)
        db.session.add(s)
        db.session.commit()
    return s


def _cronograma(admin, obra):
    from app import db
    from models import TarefaCronograma
    ids = {}
    for chave, nome, pai, ordem, ini, fim, qtd, un, resp, marco in TAREFAS:
        t = TarefaCronograma.query.filter_by(obra_id=obra.id, nome_tarefa=nome,
                                             is_cliente=False).first()
        if t is None:
            t = TarefaCronograma(obra_id=obra.id, admin_id=admin.id, nome_tarefa=nome,
                                 ordem=ordem, duracao_dias=max((fim - ini).days, 1),
                                 data_inicio=ini, data_fim=fim, is_cliente=False)
            db.session.add(t)
            db.session.flush()
        t.tarefa_pai_id = ids[pai] if pai else None
        t.quantidade_total = qtd
        t.unidade_medida = un
        t.responsavel = resp
        t.is_marco = marco
        t.ativa = True
        ids[chave] = t.id
    db.session.commit()
    return ids


def semear():
    from app import db
    from models import Usuario
    admin = _pessoa(*PESSOAS[0][:3])
    db.session.commit()
    pessoas = {'admin': admin}
    for chave, username, nome, _cargo in PESSOAS[1:]:
        pessoas[chave] = _pessoa(chave, username, nome, admin_id=admin.id)
    db.session.commit()
    _flags(admin)
    obra = _obra(admin)
    _vinculos(admin, obra, pessoas)
    _pessoal(admin)
    _subempreiteiro(admin)
    _cronograma(admin, obra)
    return Usuario.query.get(admin.id)


def limpar_rdos(admin_id):
    """Apaga os RDOs do tenant (filhos primeiro), para a captura começar do zero."""
    from app import db
    from models import (RDO, RDOApontamentoCronograma, RDOAssinatura, RDOFoto,
                        RDOServicoSubatividade, RDOSubempreitadaApontamento,
                        RDOTransicaoEstado, Obra)
    obra_ids = [o.id for o in Obra.query.filter_by(admin_id=admin_id).all()]
    rdos = RDO.query.filter(RDO.obra_id.in_(obra_ids)).all() if obra_ids else []
    for r in rdos:
        for modelo in (RDOSubempreitadaApontamento, RDOApontamentoCronograma,
                       RDOServicoSubatividade, RDOFoto, RDOAssinatura, RDOTransicaoEstado):
            modelo.query.filter_by(rdo_id=r.id).delete(synchronize_session=False)
        db.session.delete(r)          # mao_obra, equipamentos, ocorrencias: cascade no modelo
    db.session.commit()
    return len(rdos)


def resumo(admin):
    from models import Funcionario, Obra, Subempreiteiro, TarefaCronograma
    obra = Obra.query.filter_by(admin_id=admin.id, codigo=OBRA_CODIGO).one()
    def tarefa(nome):
        return TarefaCronograma.query.filter_by(obra_id=obra.id, nome_tarefa=nome).one().id
    def func(codigo):
        return Funcionario.query.filter_by(admin_id=admin.id, codigo=codigo).one().id
    return {
        'obra_id': obra.id,
        't_estacas': tarefa('Estacas hélice contínua'),
        't_blocos': tarefa('Blocos de coroamento'),
        't_pilares': tarefa('Montagem de pilares'),
        't_marco': tarefa('Liberação da estrutura pela fiscalização'),
        'f_davi': func('MR01'), 'f_pedro': func('MR03'),
        'sub_id': Subempreiteiro.query.filter_by(admin_id=admin.id).one().id,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resumo', action='store_true')
    ap.add_argument('--limpar-rdos', action='store_true')
    args = ap.parse_args()
    import main as _main  # noqa: F401
    from app import app
    from models import Usuario
    with app.app_context():
        if args.resumo:
            admin = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
            if admin is None:
                raise SystemExit('tenant manualrdo não existe — rode sem --resumo primeiro')
            for k, v in resumo(admin).items():
                print(f'{k:10s} {v}')
            return 0
        if args.limpar_rdos:
            admin = Usuario.query.filter_by(username=f'{MARCA}_admin').one()
            print(f'{limpar_rdos(admin.id)} RDO(s) apagado(s)')
            return 0
        admin = semear()
        print(f'tenant {MARCA} (admin {admin.id}) pronto')
        for k, v in resumo(admin).items():
            print(f'{k:10s} {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

Antes de rodar, conferir três nomes de coluna que o seed usa e que variam entre modelos:
Run: `grep -nE "^\s+(salario|ativo|especialidade|cargo_id|funcao_id) = db\.Column" models.py | awk -F: '$1>290 && $1<340 || $1>7700 && $1<7760'`
Se `Funcionario` não tiver `salario` ou `Subempreiteiro` não tiver `ativo`, retirar o argumento correspondente do construtor — o seed não pode inventar coluna.

- [ ] **Step 5: Rodar o seed e os testes**

Run: `.pythonlibs/bin/python scripts/seed_manual_rdo.py && .pythonlibs/bin/python scripts/seed_manual_rdo.py --resumo`
Esperado: `tenant manualrdo (admin N) pronto` e os 8 ids.

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_seed.py -q`
Esperado: **3 passed.**

- [ ] **Step 6: Conferir na aplicação que o encarregado enxerga a obra e o cronograma**

Run: `J=$(mktemp); curl -s -c $J -o /dev/null http://localhost:5000/login; curl -s -b $J -c $J -o /dev/null -d "username=manualrdo_encarregado&password=Manual@2026" http://localhost:5000/login; OBRA=$(.pythonlibs/bin/python scripts/seed_manual_rdo.py --resumo | awk '$1=="obra_id"{print $2}'); for p in /rdos "/cronograma/obra/$OBRA" "/rdo/novo?obra_id=$OBRA"; do curl -s -b $J -o /dev/null -w "$p -> HTTP %{http_code}\n" "http://localhost:5000$p"; done`
Esperado: **200** nos três. Se `/cronograma/obra/<id>` devolver 302/403 para o APONTADOR, a tela 02 passa a usar `papel='gestor'` no roteiro (Task 4) — anotar no plano o motivo.

- [ ] **Step 7: Commit**

```bash
git add scripts/seed_manual_rdo.py tests/test_manual_rdo_seed.py
git commit -m "feat(manual-rdo): seed do tenant manualrdo — obra, cronograma de 4 modos, pessoal e terceiro"
```

---

### Task 4: Roteiro — as 18 telas

**Files:**
- Create: `scripts/roteiro_manual_rdo.py`
- Test: `tests/test_manual_rdo_roteiro.py` (acrescentar)

**Interfaces:**
- Consumes: `Tela`, `Campo`, `Acao` (Task 1); `seed_manual_rdo.resumo`/`MARCA`/`PESSOAS` (Task 3).
- Produces: `resolver_ids() -> dict` (os 8 ids do seed + `hoje` em ISO), `montar(ids) -> list[Tela]`, `telas(ids=None) -> list[Tela]`. Rotas e valores podem conter `{rdo_id}` e `{rdo_retif_id}`, que a captura resolve em runtime. `FOTOS = '{foto1};{foto2};{foto3}'` também resolvido pela captura.

- [ ] **Step 1: Descobrir os `value` dos selects que o roteiro escolhe**

Run: `grep -n -A12 'id="clima_geral"' templates/rdo/novo.html | grep -oE '<option value="[^"]*"[^>]*>[^<]*' | head -6; grep -n -A8 'name="ocorr_tipo\[\]"' templates/rdo/novo.html | grep -oE '<option value="[^"]*"' | head -6; grep -n -A8 'name="ocorr_severidade\[\]"' templates/rdo/novo.html | grep -oE '<option value="[^"]*"' | head -6; grep -n -B3 'id="ocorr-rows"' templates/rdo/novo.html | grep -oE 'onclick="[^"]+"' | head -2`

Anotar: o `value` de clima para "Ensolarado" (ou o primeiro não vazio), o de tipo de ocorrência para chuva/clima, o de severidade média, e o `onclick` exato do botão que adiciona linha de ocorrência — o seletor da ação 10 é `button[onclick="<esse onclick>"]`.

- [ ] **Step 2: Escrever os testes de invariantes do roteiro**

Acrescentar em `tests/test_manual_rdo_roteiro.py`:

```python
def _roteiro_de_teste():
    from roteiro_manual_rdo import montar
    ids = {'obra_id': 1, 't_blocos': 2, 't_estacas': 3, 't_pilares': 4, 't_marco': 5,
           'f_davi': 6, 'f_pedro': 7, 'sub_id': 8, 'hoje': '2026-08-21'}
    return montar(ids)


def test_roteiro_tem_slugs_unicos_e_em_ordem():
    slugs = [t.slug for t in _roteiro_de_teste()]
    assert len(slugs) == len(set(slugs))
    assert slugs == sorted(slugs), 'o prefixo numérico do slug é a ordem do manual'


def test_numeracao_das_caixas_e_contigua_em_cada_tela():
    for t in _roteiro_de_teste():
        numeros = [c.numero for c in t.campos]
        assert numeros == list(range(1, len(numeros) + 1)), (t.slug, numeros)


def test_toda_acao_usa_tipo_que_o_motor_conhece():
    from anotar_captura import TIPOS_DE_ACAO
    for t in _roteiro_de_teste():
        for a in t.acoes:
            assert a.tipo in TIPOS_DE_ACAO, (t.slug, a.tipo)


def test_rdo_id_so_aparece_depois_da_tela_que_o_guarda():
    """`{rdo_id}` numa rota ANTES do salvar é um manual que não tem como rodar."""
    liberado = set()
    for t in _roteiro_de_teste():
        for chave in ('rdo_id', 'rdo_retif_id'):
            if '{' + chave + '}' in t.rota:
                assert chave in liberado, (t.slug, chave)
        if t.guarda_id:
            liberado.add(t.guarda_id)


def test_tela_que_permanece_nao_tem_rota():
    for t in _roteiro_de_teste():
        if t.permanece:
            assert t.rota == '', (t.slug, 'permanece=True não navega — rota vazia')
        else:
            assert t.rota.startswith('/'), t.slug
```

- [ ] **Step 3: Rodar para confirmar que falha**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_roteiro.py -q -k roteiro`
Esperado: **5 failed** — `ModuleNotFoundError: roteiro_manual_rdo`.

- [ ] **Step 4: Escrever `scripts/roteiro_manual_rdo.py`**

```python
#!/usr/bin/env python3
"""As telas do manual do RDO — a ÚNICA lista de onde saem caixas e legendas.

Ordem: de onde o RDO vem (o cronograma) → preencher (efetivo, terceiro, avanço,
ocorrência, fotos) → salvar → submeter → reabrir → submeter → assinar → aprovar
→ retificar. Segue a norma do capítulo 23a do manual.

`{obra_id}`, `{t_*}`, `{f_*}`, `{sub_id}`, `{hoje}` vêm de `resolver_ids()`
(seed). `{rdo_id}` e `{rdo_retif_id}` só existem depois de salvar/retificar:
a captura os lê da URL (`Tela.guarda_id`) e resolve em runtime. `{foto1..3}`
são os PNGs que a captura gera.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anotar_captura import Acao, Campo, Tela

FOTOS = '{foto1};{foto2};{foto3}'
MOTIVO_REABERTURA = 'Faltou a hora da chuva na ocorrência'
MOTIVO_RETIFICACAO = 'Quantidade de estacas do dia era 5, não 6'


def resolver_ids():
    from datetime import date
    import main as _main  # noqa: F401
    from app import app
    from models import Usuario
    from seed_manual_rdo import MARCA, resumo
    with app.app_context():
        admin = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
        if admin is None:
            raise SystemExit('tenant manualrdo não existe — rode scripts/seed_manual_rdo.py')
        ids = resumo(admin)
    ids['hoje'] = date.today().isoformat()
    return ids


def montar(ids):
    i = ids
    return [
        # ---------------- ANTES — de onde o RDO vem ----------------
        Tela(slug='01_login', titulo='Entrar no sistema', papel='anon',
             ato='Antes de tudo', ato_resumo='Entrar, e entender de onde o RDO vem.',
             rota='/login',
             resumo='Quem lança RDO entra com o próprio usuário. O que aparece depois '
                    'depende do papel na obra: apontador lança e assina; gestor '
                    'reabre e aprova.',
             campos=[Campo(1, 'input[name="username"]', 'Usuário ou e-mail', True),
                     Campo(2, 'input[name="password"]', 'Senha', True),
                     Campo(3, 'button[type="submit"]', 'Entrar')],
             recorte='form'),
        Tela(slug='02_cronograma', titulo='O RDO é alimentado pelo cronograma',
             papel='encarregado', rota=f"/cronograma/obra/{i['obra_id']}",
             resumo='As atividades que você vai apontar no RDO são ESTAS. O RDO não '
                    'tem lista própria: ele lê o cronograma da obra, e cada apontamento '
                    'volta para cá como avanço.',
             campos=[Campo(1, 'thead.cronograma-thead th.th-nome', 'As atividades',
                           nota='Só as folhas (sem filhas) recebem apontamento. As fases '
                                'somam as filhas.'),
                     Campo(2, 'thead.cronograma-thead th[title^="Quantidade prevista"]',
                           'Qtd / Un.',
                           nota='Atividade com quantidade e unidade é apontada por '
                                'QUANTIDADE executada no dia. Sem quantidade, por '
                                'percentual acumulado.'),
                     Campo(3, 'thead.cronograma-thead th[title^="Responsável"]',
                           'Responsável',
                           nota='"terceiros" é equipe de terceiro — mas o botão de '
                                'terceiro existe em qualquer atividade.'),
                     Campo(4, 'thead.cronograma-thead th[title^="Progresso realizado"]',
                           '% Realizado',
                           nota='Calculado automaticamente pelos apontamentos do RDO. '
                                'Ninguém digita aqui.')],
             recorte='#leftPane',
             atencao='RDO em rascunho NÃO mexe nesta coluna. Só o RDO submetido.'),
        Tela(slug='03_rdos_da_obra', titulo='Os RDOs da obra', papel='encarregado',
             rota='/rdos',
             resumo='Um RDO por obra, por dia trabalhado. Aqui você vê o que já foi '
                    'lançado e cria o de hoje.',
             campos=[Campo(1, f'a[href*="/rdos?obra_id={i["obra_id"]}"]', 'A obra'),
                     Campo(2, 'a[href*="/rdo/novo"]', 'Novo RDO')]),
        # ---------------- ATO 1 — preencher ----------------
        Tela(slug='04_cabecalho', titulo='Obra, data e clima', papel='encarregado',
             ato='Ato 1 — Preencher o dia',
             ato_resumo='Do cabeçalho às fotos, na ordem em que a tela pede.',
             rota=f"/rdo/novo?obra_id={i['obra_id']}",
             acoes=[Acao('escolher', '#obra_id', str(i['obra_id'])),
                    Acao('preencher', '#data_relatorio', i['hoje']),
                    Acao('escolher', '#clima_geral', 'Ensolarado'),   # Step 1: conferir o value
                    Acao('preencher', '#temperatura_media', '29°C')],
             campos=[Campo(1, '#obra_id', 'Obra', True),
                     Campo(2, '#data_relatorio', 'Data do RDO', True,
                           nota='A data do dia trabalhado — lançado NO MESMO DIA. Dois '
                                'dias de atraso é motivo de devolução.'),
                     Campo(3, '#clima_geral', 'Clima',
                           nota='É o que sustenta a ocorrência de chuva quando ela vira '
                                'discussão de prazo.'),
                     Campo(4, '#temperatura_media', 'Temperatura')],
             depois='Ao escolher a obra, as atividades do cronograma aparecem abaixo.'),
        Tela(slug='05_atividades', titulo='As atividades, dentro do RDO', papel='encarregado',
             rota='', permanece=True,
             resumo='São as mesmas atividades do cronograma. Em cada linha: onde apontar '
                    'o avanço, e os dois botões — equipe própria e terceiro.',
             campos=[Campo(1, '#cronogramaTarefasRDO', 'As atividades do cronograma'),
                     Campo(2, f'#qty_tarefa_{i["t_blocos"]}', 'Quantidade de HOJE',
                           nota='Atividade por quantidade: o que foi executado hoje, não '
                                'o acumulado. O sistema soma.'),
                     Campo(3, f'#pct_tarefa_{i["t_pilares"]}', 'Percentual ACUMULADO',
                           nota='Atividade por percentual: o acumulado da atividade, não '
                                'o do dia.'),
                     Campo(4, f'#chk_marco_{i["t_marco"]}', 'Marco',
                           nota='Marque só no dia em que ele de fato ocorreu.'),
                     Campo(5, f'#btn-equipe-{i["t_blocos"]}', 'Equipe própria'),
                     Campo(6, f'#btn-terceiro-{i["t_estacas"]}', 'Terceiro',
                           nota='Existe em qualquer atividade, inclusive nas nossas.')],
             recorte='#cronogramaTarefasRDO'),
        Tela(slug='06_equipe_lista', titulo='Equipe própria — só quem é operacional',
             papel='encarregado', rota='', permanece=True,
             acoes=[Acao('clicar', f'#btn-equipe-{i["t_blocos"]}')],
             resumo='A lista traz só o pessoal OPERACIONAL. A Ana, do escritório, não '
                    'aparece — a função dela está marcada como administrativa.',
             campos=[Campo(1, '#modalFuncFiltro', 'Buscar pelo nome'),
                     Campo(2, '#modalFuncLista', 'Quem pode ser alocado',
                           nota='Quem trabalhou e não aparece aqui está com a função '
                                'marcada como administrativa no cadastro — avise o '
                                'escritório, não deixe de fora.')],
             recorte='#modalEquipeTarefa .modal-content'),
        Tela(slug='07_equipe_horas', titulo='Quem esteve, e quantas horas',
             papel='encarregado', rota='', permanece=True,
             acoes=[Acao('clicar', '#modalFuncLista button:has-text("Davi Montador")'),
                    Acao('clicar', '#modalFuncLista button:has-text("Pedro Ajudante")'),
                    Acao('preencher', f'input[name="func_{i["t_blocos"]}_{i["f_davi"]}_horas"]', '8'),
                    Acao('preencher', f'input[name="func_{i["t_blocos"]}_{i["f_pedro"]}_horas"]', '8')],
             resumo='Cada pessoa com as horas NESTA atividade. Quem trabalhou em duas '
                    'atividades aparece nas duas, com as horas divididas — a soma bate '
                    'com a jornada.',
             campos=[Campo(1, '#modalEquipeSelecionada', 'Alocados nesta atividade'),
                     Campo(2, f'input[name="func_{i["t_blocos"]}_{i["f_davi"]}_horas"]',
                           'Horas de cada um', True),
                     Campo(3, '#modalEquipeTarefa button.btn-primary', 'Confirmar')],
             recorte='#modalEquipeTarefa .modal-content',
             atencao='Não é aceito: escrever o efetivo em observação, ou só o número de '
                     'pessoas sem dizer quem.'),
        Tela(slug='08_terceiro', titulo='Equipe de terceiro', papel='encarregado',
             rota='', permanece=True,
             acoes=[Acao('clicar', '#modalEquipeTarefa button.btn-primary'),
                    Acao('clicar', f'#btn-terceiro-{i["t_estacas"]}'),
                    Acao('escolher', '#sub_subempreiteiro_id', str(i['sub_id'])),
                    Acao('preencher', '#sub_qtd_pessoas', '11'),
                    Acao('preencher', '#sub_horas', '9'),
                    Acao('preencher', '#sub_qtd_prod', '6')],
             resumo='"Abraão, 11 pessoas" deixa de ser anotação no papel: nome do '
                    'cadastro, quantidade de pessoas, horas e — se houver medida física '
                    'do dia — a produção.',
             campos=[Campo(1, '#sub_subempreiteiro_id', 'Terceiro (do cadastro)', True,
                           nota='Não está cadastrado? Peça o cadastro ao escritório.'),
                     Campo(2, '#sub_qtd_pessoas', 'Quantidade de pessoas', True,
                           nota='É este número que responde depois "em quantos dias, '
                                'com quantos homens".'),
                     Campo(3, '#sub_horas', 'Horas da equipe'),
                     Campo(4, '#sub_qtd_prod', 'Produção do dia',
                           nota='Só quando houver medida física (un, m², m³). Sem medida, '
                                'zero — registrar efetivo NÃO move o avanço.'),
                     Campo(5, '#modalSubempreitada button.btn-primary', 'Salvar')],
             recorte='#modalSubempreitada .modal-content',
             atencao='Não é aceito: anotar "11 pessoas" em observação, ou pular o terceiro '
                     'porque a atividade é nossa.'),
        Tela(slug='09_avanco', titulo='O avanço de quem andou hoje', papel='encarregado',
             rota='', permanece=True,
             acoes=[Acao('clicar', '#modalSubempreitada button.btn-primary'),
                    Acao('preencher', f'#qty_tarefa_{i["t_blocos"]}', '2'),
                    Acao('preencher', f'#pct_tarefa_{i["t_pilares"]}', '15')],
             resumo='Aponte só as atividades que andaram. Quantidade é a de HOJE; '
                    'percentual é o ACUMULADO; marco só no dia em que ocorreu.',
             campos=[Campo(1, f'#qty_tarefa_{i["t_blocos"]}', 'Blocos: 2 hoje'),
                     Campo(2, f'#pct_tarefa_{i["t_pilares"]}', 'Pilares: 15 % acumulado'),
                     Campo(3, f'#chk_marco_{i["t_marco"]}', 'Marco: em branco',
                           nota='A liberação ainda não aconteceu. Em branco.')],
             recorte='#cronogramaTarefasRDO',
             atencao='Não é aceito: repetir o número da véspera para "não deixar vazio", '
                     'nem apontar 100 % "porque está quase acabando".'),
        Tela(slug='10_ocorrencias', titulo='O que aconteceu, quando e qual o efeito',
             papel='encarregado', rota='', permanece=True,
             acoes=[Acao('clicar', 'button[onclick="ADICIONAR_OCORRENCIA"]'),   # Step 1: onclick real
                    Acao('escolher', '[name="ocorr_tipo[]"]', 'clima'),          # Step 1: value real
                    Acao('escolher', '[name="ocorr_severidade[]"]', 'media'),    # Step 1: value real
                    Acao('preencher', '[name="ocorr_descricao[]"]',
                         'Chuva das 10h às 14h — concretagem do bloco B3 adiada para amanhã')],
             resumo='"Choveu" não é ocorrência. "Chuva das 10h às 14h, concretagem do '
                    'bloco B3 adiada" é: diz o que, quando e o efeito.',
             campos=[Campo(1, '[name="ocorr_tipo[]"]', 'Tipo', True),
                     Campo(2, '[name="ocorr_severidade[]"]', 'Severidade'),
                     Campo(3, '[name="ocorr_descricao[]"]', 'O que, quando, efeito', True)],
             recorte='#ocorr-rows',
             atencao='Não é aceito: dia em que a produção caiu sem ocorrência que explique.'),
        Tela(slug='11_fotos', titulo='Três fotos, no mínimo', papel='encarregado',
             rota='', permanece=True,
             acoes=[Acao('anexar', '#fileInputNovoGal', FOTOS),
                    Acao('preencher', '#observacoes_finais',
                         'Frente de serviço liberada às 7h. Chuva das 10h às 14h.')],
             resumo='Uma da frente de serviço no início, uma do que foi executado, uma de '
                    'cada ocorrência física. A foto tem de deixar ver ONDE é.',
             campos=[Campo(1, '#previewContainerNovo', 'As fotos anexadas'),
                     Campo(2, '#observacoes_finais', 'Observações finais')],
             atencao='Ocorrência física (dano, interdição, material errado, alagamento) '
                     'sem foto é motivo de devolução.'),
        Tela(slug='12_salvar_rascunho', titulo='Salvo — mas ainda é rascunho',
             papel='encarregado', rota='', permanece=True, guarda_id='rdo_id',
             acoes=[Acao('submeter', '#btnFinalizarRDO')],
             resumo='O RDO nasce em RASCUNHO. Pode editar à vontade durante o dia — mas '
                    'rascunho não lança custo nem alimenta o cronograma. Para o resto do '
                    'sistema, é um dia que ainda não existiu.',
             campos=[Campo(1, '.estado-badge', 'O estado: rascunho')],
             atencao='RDO esquecido em rascunho não é devolvido: ele simplesmente não '
                     'conta. É o sexto motivo da lista do escritório.'),
        # ---------------- ATO 2 — fechar ----------------
        Tela(slug='13_submeter', titulo='Submeter: o fecho do dia', papel='encarregado',
             ato='Ato 2 — Fechar o dia',
             ato_resumo='Submeter, corrigir se preciso, assinar. Depois disso o documento '
                        'não se mexe — se retifica.',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/finalizar"] button[type="submit"]')],
             resumo='É aqui que os custos de mão de obra são lançados, a medição é '
                    'recalculada e o cliente passa a enxergar o dia. No fim do DIA, não '
                    'no fim da semana.',
             campos=[Campo(1, '.estado-badge', 'O estado: preenchido')],
             depois='O % Realizado do cronograma (tela 2) acabou de mudar.'),
        Tela(slug='14_reabrir', titulo='Errou? O gestor reabre', papel='gestor',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/reabrir"] button[type="submit"]')],
             resumo='Enquanto está PREENCHIDO, o RDO ainda é corrigível: o gestor reabre '
                    '(com motivo), ele volta a rascunho, você corrige e submete de novo.',
             campos=[Campo(1, '.estado-badge', 'Voltou a rascunho')],
             atencao=f'O motivo é obrigatório e fica registrado. Aqui: "{MOTIVO_REABERTURA}".'),
        Tela(slug='15_submeter_de_novo', titulo='Corrigiu, submete de novo',
             papel='encarregado', rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/finalizar"] button[type="submit"]')],
             resumo='O mesmo botão. O histórico guarda a reabertura e a nova submissão.',
             campos=[Campo(1, '.estado-badge', 'Preenchido outra vez')]),
        Tela(slug='16_assinar', titulo='Assinar: vira documento', papel='encarregado',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/assinar"] button[type="submit"]')],
             resumo='A assinatura é o que dá ao RDO valor de documento. Depois dela, '
                    'nada mais é editado — de propósito.',
             campos=[Campo(1, '.estado-badge', 'Assinado — imutável')],
             atencao='Nunca crie um segundo RDO do mesmo dia "por fora" para consertar. '
                     'Ou se reabre antes de assinar, ou se retifica depois.'),
        Tela(slug='17_aprovar', titulo='Aprovar: o aceite do gestor', papel='gestor',
             rota='/rdo/{rdo_id}',
             acoes=[Acao('submeter', 'form[action$="/aprovar"] button[type="submit"]')],
             resumo='O gestor da obra aceita o dia. Estado final.',
             campos=[Campo(1, '.estado-badge', 'Aprovado')]),
        Tela(slug='18_retificar', titulo='Achou erro depois? Retifica', papel='gestor',
             rota='/rdo/{rdo_id}', guarda_id='rdo_retif_id',
             acoes=[Acao('submeter', 'form[action$="/retificar"] button[type="submit"]')],
             resumo='Um documento de data não se apaga — se retifica. O sistema emite um '
                    'NOVO RDO da mesma data, e marca o original como retificado. Os dois '
                    'ficam, e a correção é rastreável.',
             campos=[Campo(1, '.estado-badge', 'O retificador nasce em rascunho')],
             depois=f'Motivo registrado: "{MOTIVO_RETIFICACAO}". Preencha o retificador '
                    'como o original, dizendo o que o primeiro deveria ter dito, e feche '
                    'pelo mesmo caminho.'),
    ]


def telas(ids=None):
    return montar(ids or resolver_ids())
```

Depois de escrever, **substituir** os três marcadores `Ensolarado` / `ADICIONAR_OCORRENCIA` / `clima` / `media` pelos valores anotados no Step 1.

- [ ] **Step 5: Rodar os testes do roteiro**

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_roteiro.py -q`
Esperado: **todos PASSAM** (os 5 novos e os anteriores).

- [ ] **Step 6: Commit**

```bash
git add scripts/roteiro_manual_rdo.py tests/test_manual_rdo_roteiro.py
git commit -m "feat(manual-rdo): roteiro das 18 telas — do cronograma a retificar"
```

---

### Task 5: Captura

**Files:**
- Create: `scripts/capturar_manual_rdo.py`

**Interfaces:**
- Consumes: `capturar_manual_compras.preparar_bibliotecas`, `capturar_manual_compras.entrar`; `anotar_captura.executar/marcar/limpar/MarcacaoQuebrada`; `roteiro_manual_rdo.telas`; `seed_manual_rdo.MARCA/SENHA/limpar_rdos`.
- Produces: `docs/manual_rdo/screenshots/<slug>.png` para as 18 telas, ou exit ≠ 0 dizendo qual tela quebrou.

- [ ] **Step 1: Escrever `scripts/capturar_manual_rdo.py`**

```python
#!/usr/bin/env python3
"""Captura as telas do manual do RDO, já com as caixas numeradas.

Uso:
    .pythonlibs/bin/python scripts/seed_manual_rdo.py        # 1. o cenário
    .pythonlibs/bin/python scripts/capturar_manual_rdo.py    # 2. as fotos
    .pythonlibs/bin/python scripts/gerar_manual_rdo.py       # 3. o PDF

Pré-requisito: o app de pé em SIGE_BASE (default http://localhost:5000).

A REGRA (herdada de capturar_manual_compras.py): falhou, para. Seletor que não
casa, tela que não abre, login que falha → exit ≠ 0 com o nome da tela.

O que é diferente de compras: o formulário de RDO é preenchido em etapas na
MESMA página (`Tela.permanece`), o id do RDO nasce no meio da captura
(`Tela.guarda_id` lê da URL), reabrir/retificar pedem motivo num `prompt`
(tratado pelo handler de dialog) e as fotos são PNGs gerados aqui.
"""
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SIGE_BOOT_DDL', '0')
os.environ.setdefault('SIGE_ENABLE_DEMO_SEED', 'false')

from playwright.sync_api import sync_playwright

from anotar_captura import MarcacaoQuebrada, executar, limpar, marcar
from capturar_manual_compras import entrar, preparar_bibliotecas

BASE = os.environ.get('SIGE_BASE', 'http://localhost:5000')
SAIDA = Path('docs/manual_rdo/screenshots')
FOTOS_DIR = Path('.cache/manual_rdo_fotos')
VIEWPORT = {'width': 1440, 'height': 950}


def _fotos():
    """Três PNGs distintos, com legenda, para o input de fotos."""
    from PIL import Image, ImageDraw
    FOTOS_DIR.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for n, (texto, cor) in enumerate([('Frente de serviço — 7h', (120, 140, 160)),
                                      ('Blocos B1 e B2 concretados', (150, 130, 110)),
                                      ('Chuva — 10h', (100, 110, 130))], start=1):
        img = Image.new('RGB', (960, 640), cor)
        ImageDraw.Draw(img).text((30, 30), texto, fill=(255, 255, 255))
        p = FOTOS_DIR / f'foto{n}.png'
        img.save(p)
        caminhos.append(str(p.resolve()))
    return caminhos


def main():
    preparar_bibliotecas()
    import capturar_manual_compras
    from roteiro_manual_rdo import MOTIVO_REABERTURA, MOTIVO_RETIFICACAO, telas
    from seed_manual_rdo import MARCA, SENHA, limpar_rdos
    capturar_manual_compras.SENHA = SENHA        # `entrar` lê o módulo dele

    # RDO do dia anterior atrapalha: a captura sempre começa do zero.
    import main as _main  # noqa: F401
    from app import app
    from models import Usuario
    with app.app_context():
        admin = Usuario.query.filter_by(username=f'{MARCA}_admin').one()
        print(f'  {limpar_rdos(admin.id)} RDO(s) anteriores apagados')

    roteiro = telas()
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir(parents=True, exist_ok=True)
    f1, f2, f3 = _fotos()
    ctx = {'foto1': f1, 'foto2': f2, 'foto3': f3}
    usuarios = {'encarregado': f'{MARCA}_encarregado', 'gestor': f'{MARCA}_gestor',
                'admin': f'{MARCA}_admin'}
    motivos = {'/reabrir': MOTIVO_REABERTURA, '/retificar': MOTIVO_RETIFICACAO}

    def resolver(texto):
        try:
            return texto.format(**ctx) if texto else texto
        except KeyError as e:
            raise SystemExit(f'rota/valor usa {e} antes de ele existir — ordem do roteiro')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=['--no-sandbox', '--disable-dev-shm-usage'])
        paginas = {}

        def pagina_de(papel):
            if papel not in paginas:
                pg = browser.new_context(viewport=VIEWPORT).new_page()
                # reabrir/retificar pedem o motivo num prompt(): aceitar com o
                # motivo do roteiro, para o documento sair com texto de verdade.
                pg.on('dialog', lambda d: d.accept(
                    next((m for k, m in motivos.items() if k in (d.message or '') or True), '')))
                if papel != 'anon':
                    entrar(pg, usuarios[papel])
                paginas[papel] = pg
            return paginas[papel]

        atual = None
        for tela in roteiro:
            destino = SAIDA / f'{tela.slug}.png'
            rota = resolver(tela.rota)
            print(f'  {tela.slug:22s} {tela.papel:12s} {"(mesma página)" if tela.permanece else rota}')
            pg = pagina_de(tela.papel) if not tela.permanece else atual
            if pg is None:
                raise SystemExit(f'{tela.slug}: permanece=True sem tela anterior')
            try:
                if not tela.permanece:
                    resp = pg.goto(f'{BASE}{rota}', wait_until='domcontentloaded', timeout=30000)
                    if resp is not None and resp.status >= 400:
                        raise RuntimeError(f'HTTP {resp.status}')
                    if tela.papel != 'anon' and '/login' in pg.url:
                        raise RuntimeError('caiu no login — sessão perdida ou sem permissão')
                    pg.wait_for_timeout(1600)
                    pg.evaluate("""() => document.querySelectorAll(
                        '.modal-backdrop, .toast').forEach(e => e.remove())""")
                else:
                    limpar(pg)          # as caixas da foto anterior
                acoes = [type(a)(a.tipo, resolver(a.seletor), resolver(a.valor)) for a in tela.acoes]
                if acoes:
                    print(f'      {executar(pg, acoes)} ação(ões) antes da foto')
                    pg.wait_for_timeout(600)
                marcar(pg, tela.campos)
                if tela.recorte:
                    alvo = pg.query_selector(tela.recorte)
                    if alvo is None:
                        raise MarcacaoQuebrada(f'recorte não existe na página: {tela.recorte}')
                    alvo.screenshot(path=str(destino))
                else:
                    pg.screenshot(path=str(destino), full_page=True)
                if tela.guarda_id:
                    m = re.search(r'/rdo/(\d+)', pg.url)
                    if not m:
                        raise RuntimeError(f'guarda_id={tela.guarda_id}: URL sem /rdo/<id>: {pg.url}')
                    ctx[tela.guarda_id] = m.group(1)
                    print(f'      {tela.guarda_id} = {m.group(1)}')
            except (MarcacaoQuebrada, RuntimeError) as e:
                raise SystemExit(f'\nFALHOU em {tela.slug}: {e}\nURL: {pg.url}')
            atual = pg
        browser.close()
    print(f'\n{len(roteiro)} capturas em {SAIDA}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

O handler de `dialog` acima aceita **qualquer** prompt com o motivo que casar com a mensagem (`'Motivo da reabertura:'` contém "reabertura"; `'Motivo da retificação'` contém "retifica"). Escrever assim, sem o `or True`:

```python
                def _aceitar(d):
                    msg = (d.message or '').lower()
                    if 'reabert' in msg:
                        d.accept(MOTIVO_REABERTURA)
                    elif 'retific' in msg:
                        d.accept(MOTIVO_RETIFICACAO)
                    else:
                        d.accept()
                pg.on('dialog', _aceitar)
```

- [ ] **Step 2: Rodar a captura**

Run: `.pythonlibs/bin/python scripts/seed_manual_rdo.py && .pythonlibs/bin/python scripts/capturar_manual_rdo.py`

Esperado: 18 linhas `slug papel rota`, `rdo_id = N` depois da 12 e `rdo_retif_id = M` depois da 18, e `18 capturas em docs/manual_rdo/screenshots`.

Se parar numa tela, o erro diz o seletor. Os prováveis:
- **05**: `#cronogramaTarefasRDO` vazio porque a lista carrega depois de escolher a obra — se o `wait_for_timeout(600)` não bastar, acrescentar `Acao('clicar', 'button[onclick^="carregarTarefasRDO"]')` no início das ações da tela 05.
- **07**: `button:has-text(...)` — conferir se o nome renderizado no modal é o `nome` completo do funcionário (📖 `novo.html` monta `${f.nome}`).
- **14/18**: o `prompt` — se o estado não mudar, o dialog não foi aceito: conferir a mensagem exata em `visualizar_rdo_moderno.html:1111,1121`.
- **02** com 302: APONTADOR não vê o cronograma → trocar `papel='gestor'` na tela 02 (Task 3, Step 6 já avisou).

- [ ] **Step 3: Olhar as 18 imagens**

Run: `ls -la docs/manual_rdo/screenshots/ && .pythonlibs/bin/python -c "
from PIL import Image; import glob
for p in sorted(glob.glob('docs/manual_rdo/screenshots/*.png')):
    im = Image.open(p); print(f'{p.split(\"/\")[-1]:26s} {im.size[0]}x{im.size[1]}')"`

Abrir com o `Read` pelo menos `05_atividades.png`, `08_terceiro.png`, `12_salvar_rascunho.png` e `18_retificar.png` e conferir: caixas numeradas nos campos certos, estado visível no badge, nenhuma imagem de página de erro.

- [ ] **Step 4: Commit**

```bash
git add scripts/capturar_manual_rdo.py docs/manual_rdo/screenshots
git commit -m "feat(manual-rdo): captura das 18 telas — formulario em etapas, id do RDO lido da URL, prompt de motivo"
```

---

### Task 6: PDF, markdown, link no manual do sistema e registro

**Files:**
- Create: `scripts/gerar_manual_rdo.py`
- Modify: `manual/23a_rdo_padrao_preenchimento.md` (topo)
- Output: `docs/manual_rdo/Manual_RDO_SIGE.pdf`, `docs/manual_rdo/manual-rdo.md`, `static/docs/manual-rdo.pdf`
- Modify: `ESTADO-ATUAL.md` (seção 21/08)

**Interfaces:**
- Consumes: `manual_pdf.construir_pdf/escrever_markdown` (Task 2), `roteiro_manual_rdo.telas` (Task 4), as capturas (Task 5).

- [ ] **Step 1: Escrever `scripts/gerar_manual_rdo.py`**

```python
#!/usr/bin/env python3
"""Monta o manual do RDO em PDF e markdown, a partir do roteiro e das capturas.

Uso:
    .pythonlibs/bin/python scripts/gerar_manual_rdo.py

Lê o MESMO roteiro que desenhou as caixas (`scripts/roteiro_manual_rdo.py`).
Sai em `docs/manual_rdo/Manual_RDO_SIGE.pdf` + `manual-rdo.md`, e copia o PDF
para `static/docs/manual-rdo.pdf`, que o capítulo 23a do manual do sistema linka.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manual_pdf import construir_pdf, escrever_markdown

RAIZ = Path('docs/manual_rdo')
SHOTS = RAIZ / 'screenshots'
PDF = RAIZ / 'Manual_RDO_SIGE.pdf'
MD = RAIZ / 'manual-rdo.md'
PDF_NO_APP = Path('static/docs/manual-rdo.pdf')

TITULO = 'RDO, do cronograma à assinatura'
QUEM = {'anon': 'qualquer pessoa', 'encarregado': 'o encarregado (apontador da obra)',
        'gestor': 'o gestor da obra', 'admin': 'o administrador'}
INTRO = [
    'Este manual segue um dia de obra inteiro, na ordem em que ele acontece no '
    'sistema: as atividades vêm do cronograma, o encarregado lança efetivo, '
    'terceiros, avanço, ocorrências e fotos, salva, submete, o gestor confere, o '
    'encarregado assina, o gestor aprova — e, se um erro aparecer depois, retifica.',
    'Em cada tela, as caixas numeradas marcam o que precisa ser preenchido. Os '
    'campos com <font color="#c92a2a">*</font> são obrigatórios. A regra por trás '
    'de cada passo está no capítulo "RDO — Padrão de Preenchimento" do manual do '
    'sistema (/manual).',
]


def main():
    from roteiro_manual_rdo import telas
    roteiro = telas()
    construir_pdf(roteiro, pdf=PDF, shots=SHOTS, titulo=TITULO,
                  subtitulo='Manual de uso do SIGE', intro=INTRO, quem=QUEM)
    escrever_markdown(roteiro, md=MD, titulo=TITULO,
                      gerador='scripts/gerar_manual_rdo.py',
                      roteiro_nome='scripts/roteiro_manual_rdo.py')
    PDF_NO_APP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PDF, PDF_NO_APP)
    print(f'ok: {PDF} ({PDF.stat().st_size // 1024} KB), {MD}, {PDF_NO_APP}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2: Gerar**

Run: `.pythonlibs/bin/python scripts/gerar_manual_rdo.py && .pythonlibs/bin/python -c "
from pypdf import PdfReader" 2>/dev/null && .pythonlibs/bin/python -c "
from pypdf import PdfReader; r = PdfReader('docs/manual_rdo/Manual_RDO_SIGE.pdf'); print(len(r.pages), 'páginas')" || echo "(pypdf ausente — conferir páginas abrindo o PDF)"`

Esperado: `ok: ...` e **19+ páginas** (capa + 18 telas, algumas com quebra).

- [ ] **Step 3: Ler o PDF**

Abrir `docs/manual_rdo/Manual_RDO_SIGE.pdf` com o `Read` (páginas 1-8 e 14-20) e conferir: capa, atos na ordem, cada figura com a legenda numerada embaixo, avisos "O que acontece"/"Atenção" grudados à tela.

- [ ] **Step 4: Linkar do capítulo 23a**

Em `manual/23a_rdo_padrao_preenchimento.md`, logo depois do parágrafo que começa com "Este capítulo é a **norma** do RDO", inserir:

```markdown
> 📘 **Versão ilustrada:** [RDO, do cronograma à assinatura (PDF)](/static/docs/manual-rdo.pdf) —
> as mesmas regras, tela a tela, com as caixas numeradas. Regerável por
> `scripts/seed_manual_rdo.py` → `capturar_manual_rdo.py` → `gerar_manual_rdo.py`.
```

Run: `.pythonlibs/bin/pytest tests/test_manual_rdo_padrao.py -q`
Esperado: **passa** (o teste confere seções e a ausência de "capítulo em construção"; o link não mexe em nenhuma das duas).

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/static/docs/manual-rdo.pdf`
Esperado: **200**.

- [ ] **Step 5: Registrar no `ESTADO-ATUAL.md`**

Na seção `### ✅ 21/08 — reunião de 20/08: o que estava preso numa branch, integrado`, antes do parágrafo `**O Chromium do Playwright não sobe nesta máquina**`, acrescentar:

```markdown
**📘 Manual visual do RDO — `docs/manual_rdo/`, regenerável por três comandos.**
18 telas do cronograma à retificação, caixas numeradas por seletor, PDF + markdown,
PDF também em `static/docs/manual-rdo.pdf` (linkado do capítulo 23a). Mesma
ferramenta do manual de compras, com quatro acréscimos aditivos no motor
(`clicar`, `anexar`, `Tela.permanece`, `Tela.guarda_id`) e o gerador de PDF
extraído para `scripts/manual_pdf.py` — compras passou a usá-lo, markdown idêntico.
Cenário no tenant `manualrdo` (`scripts/seed_manual_rdo.py`, idempotente). Plano:
`docs/superpowers/plans/2026-08-21-manual-visual-rdo.md`.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/gerar_manual_rdo.py docs/manual_rdo manual/23a_rdo_padrao_preenchimento.md static/docs/manual-rdo.pdf ESTADO-ATUAL.md
git commit -m "docs(manual-rdo): PDF e markdown do manual visual do RDO, linkados do capitulo 23a"
```

---

## Riscos

| Risco | Sinal | Resposta |
|---|---|---|
| O APONTADOR não abre `/cronograma/obra/<id>` | 302 para login/obras na tela 02 | tela 02 com `papel='gestor'`; o texto não muda |
| A lista de atividades do RDO carrega depois do `wait` | `#qty_tarefa_*` "não existe" na 05 | `Acao('clicar', 'button[onclick^="carregarTarefasRDO"]')` no início da 05 |
| `has-text` não casa por acento/HTML | 07 falha em "Davi Montador" | usar `button:has-text("Davi")` |
| O `prompt` de motivo não é aceito | estado não muda na 14/18 | conferir a mensagem do `prompt` e o `_aceitar` |
| Retificar exige papel diferente | 403/flash na 18 | ler `views/rdo.py:1910-1960` e trocar o papel da tela |
| `tarefas-rdo` esconde a fase pai | só 4 linhas na 05 | esperado — só folhas recebem apontamento; o texto da tela 02 já diz |

## Fronteiras

- Não cobre a **edição** de RDO (`/rdo/<id>/editar`) nem o PDF do RDO (`/rdo/<id>/pdf`).
- Não cobre o portal do cliente.
- Não mexe no manual de compras além da extração do gerador (markdown tem de sair idêntico).
