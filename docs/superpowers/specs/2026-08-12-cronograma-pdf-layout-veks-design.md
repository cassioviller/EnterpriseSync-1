# Cronograma em PDF — a planilha do Project no papel timbrado da empresa

**Data:** 2026-08-12
**Origem:** pedido do Cássio em sessão — "uma exportação em PDF do cronograma em formato
bem parecido com o Project, só que com o layout da Veks", com o arquivo `layout
veks.docx` entregue como referência visual. Na conversa o escopo foi refinado duas
vezes: **sem o gráfico de Gantt, só a tabela**, e **só na tela do cronograma**, sem
botão no portal do cliente.
**Escopo:** uma rota de download, um serviço de geração, um botão na toolbar e a
extração de uma fórmula de progresso que hoje mora dentro de uma view.

---

## Por que existe

O cronograma da obra só sai do sistema de duas formas hoje: pela tela
(`/cronograma/obra/<id>`, um Gantt em HTML de 3.678 linhas) e pelo
`fisico-financeiro/export.xlsx` (`cronograma_views.py:4197`), que exporta o
físico-financeiro e não a planilha de tarefas. Quem precisa mandar o cronograma ao
cliente — anexo de medição, e-mail de acompanhamento, reunião impressa — não tem de onde
tirar um arquivo apresentável. O que existe é print de tela.

O `layout veks.docx` resolve a outra metade do problema: ele define a identidade dos
documentos externos da empresa, e é essa forma que o PDF do cronograma deve herdar.

## O que o docx define

Extraído do arquivo (`word/document.xml`, `word/header1.xml`, `word/footer1.xml`,
`word/media/image1.png`):

| Elemento | Valor |
|---|---|
| Navy institucional | `#1E2A4C` — títulos, cabeçalho de tabela, wordmark |
| Laranja de acento | `#E8620E` — o ponto do logo; usado com parcimônia |
| Cinzas de texto | `#5A6472` (secundário), `#8A93A3` (terciário) |
| Preenchimento | `#F4F6F9` — faixas e zebra de tabela |
| Fio | `#C9CED6` — grade e régua do rodapé |
| Tipografia de título | Georgia (serifada) |
| Cabeçalho | Logo à esquerda; razão social, CNPJ, cidade e site à direita, em corpo pequeno |
| Rodapé | Fio superior, `EMPRESA · <documento>` à esquerda, `pág. X/Y` à direita |

**Georgia não existe no servidor** e não há TTF versionado no repositório (só as fontes
Vera que vêm dentro da reportlab). O PDF usa `Times-Roman`, embutida na reportlab: é a
serifada disponível sem risco de licença nem de deploy. Trocar por uma TTF versionada
depois é uma linha de `registerFont` — não vale carregar esse peso agora.

## Decisões tomadas na conversa

| Pergunta | Decisão |
|---|---|
| Para quem é o PDF | Cliente — documento de acompanhamento |
| Qual cronograma alimenta | **O da tela aberta**: `?cliente=1` exporta a cópia-cliente, sem querystring exporta o interno |
| Gantt ou tabela | **Só a tabela** — a "Planilha de tarefas" do Project, não o gráfico |
| Colunas | EDT, Nome da tarefa, Duração, Início, Término, % concluído |
| Página | A4 retrato; linhas quebram para a página seguinte com o cabeçalho da tabela repetido |
| Onde fica o botão | Só na tela do cronograma, atrás de `@login_required`. **Sem** rota no portal do cliente |
| Marca | A forma do docx é o padrão de todos os tenants; logo, nome, CNPJ e endereço vêm de `ConfiguracaoEmpresa` |

A escolha de "seguir a tela aberta" evita a armadilha registrada em `models.py`
(`TarefaCronograma.do_cronograma_interno`): a obra tem duas populações de tarefa
(`is_cliente=False` viva e alimentada pelo RDO, `is_cliente=True` uma foto tirada por
`gerar_cronograma_cliente`), e escolher a errada em silêncio produz um documento com
percentual congelado. Espelhando a tela, o PDF nunca diz algo diferente do que a pessoa
que clicou tinha na frente.

A marca por tenant não é preciosismo: o sistema é multi-tenant e `ConfiguracaoEmpresa` já
guarda `logo_pdf_base64`, `header_pdf_base64`, `cnpj`, `endereco` e `website`
(`models.py:4324`) justamente porque outros PDFs se personalizam. Embutir a Veks no
código faria todo outro tenant emitir cronograma com a marca dela.

---

## Arquitetura

### Rota

`GET /cronograma/obra/<int:obra_id>/export.pdf`, em `cronograma_views.py`, espelhando
`fisico_financeiro_xlsx` (`cronograma_views.py:4197`): `@login_required`, `_check_v2()`,
`Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()`, e `send_file` de um
`BytesIO` — nada gravado em disco, porque não há o que versionar (o cronograma muda todo
dia; o arquivo é uma foto de agora).

Um guard que o export xlsx **não** tem entra aqui: `pode_ver_obra(obra_id)`
(`utils/autorizacao.py:145`) → **404**, não 403. A escolha do 404 é a convenção já
travada por `tests/test_cronograma_permissoes.py` — a existência de uma obra fora do
alcance do usuário não vaza. Com `configuracao_empresa.escopo_obra_ativo` desligada (o
default) `papel_na_obra` devolve GESTOR para todo usuário do tenant e o guard é
transparente; com ela ligada, um LEITOR sem vínculo deixa de baixar o cronograma de uma
obra que não é dele.

O modo sai de `_modo_cliente()` (`cronograma_views.py:365`), o mesmo helper que a tela
usa. Nome do arquivo: `Cronograma_<obra-sanitizada>_<AAAA-MM-DD>.pdf`, com sufixo
`_cliente` no modo cliente.

### Três peças, uma responsabilidade cada

`services/cronograma_pdf.py`, no par `montar_*`/`exportar_*` que
`services/cronograma_fisico_financeiro.py` estabeleceu (`montar_fisico_financeiro` +
`exportar_fisico_financeiro_xlsx`):

**`montar_linhas_cronograma(obra_id, admin_id, *, cliente) -> dict`** — dados, nada de
desenho. Não sabe que existe PDF. Devolve:

```python
{
  'obra': {'nome': ..., 'cliente': ..., 'data_inicio': date|None,
           'data_fim': date|None, 'progresso_geral': float},
  'linhas': [
     {'edt': '1',   'nivel': 0, 'nome': 'Fundação',  'duracao_dias': 33,
      'data_inicio': date, 'data_fim': date, 'percentual': 100.0,
      'is_pai': True,  'is_marco': False},
     {'edt': '1.1', 'nivel': 1, 'nome': 'Escavação', ...},
  ],
}
```

Lê pela mesma trinca que a tela: `ordenar_arvore_visual`
(`utils/cronograma_engine.py:289` — a fonte única da ordem visual e da numeração de
linhas), `sincronizar_percentuais_obra` (`utils/cronograma_engine.py:467`) e
`calcular_progresso_geral_obra_v2` (`utils/cronograma_engine.py:839`).

**`exportar_cronograma_pdf(dados, marca) -> bytes`** — só desenho. Não toca no banco, o
que a torna testável sem obra nenhuma: um dict na entrada, bytes na saída.

**`montar_marca_tenant(admin_id) -> dict`** — nome, CNPJ, endereço, website e logo de
`ConfiguracaoEmpresa`. Preferência de logo: `logo_pdf_base64` → `logo_base64`. Base64
corrompida ou ausente cai no nome da empresa em serifada e registra em log, sem derrubar
o download.

### A EDT sai da árvore, não do `wbs_codigo`

`TarefaCronograma.wbs_codigo` existe, mas só é preenchido nas tarefas que vieram de
importação `.mpp` (migration 208). Numa obra com tarefas criadas na tela a numeração
sairia furada — algumas com código, outras em branco. A EDT é derivada da posição na
árvore na hora da exportação (1, 1.1, 1.2, 2, …), a partir do `nivel_map` que
`ordenar_arvore_visual` já devolve. Determinística e sempre completa.

### A correção de rota: a sexta fórmula de progresso que não vai nascer

O progresso da linha-raiz é calculado hoje em **dois lugares diferentes**, dentro da
mesma view:

* modo interno — `calcular_progresso_geral_obra_v2` (`cronograma_views.py:567`);
* modo cliente — uma média das folhas ponderada por duração, escrita à mão em
  `cronograma_views.py:557-563`.

Copiar a segunda para dentro do serviço de PDF criaria a **sexta** fórmula de progresso
do sistema. O comentário em `templates/obras/cronograma.html:124` registra o que a quinta
custou: era uma média simples escondida numa expressão Jinja, dava peso igual a uma
tarefa de 1 dia e a uma de 40, e contava tarefa-pai junto com as filhas.

Então a média do modo cliente é extraída para `progresso_geral_cliente(tarefas)` em
`utils/cronograma_engine.py`, e **a view e o serviço de PDF chamam a mesma função**. É
extração pura — mesmos números, sem mudança de comportamento —, e o teste que compara
papel com tela é o que garante isso.

Fora dessa extração, nada de refactor: o Gantt em HTML, o editor v2 e o portal do cliente
não são tocados.

### A assimetria da linha-raiz, que o PDF copia em vez de corrigir

A view faz uma coisa a mais no modo interno e não faz no modo cliente: depois de calcular
o progresso geral, ela sobrescreve o percentual de **toda linha sem `tarefa_pai_id`** com
esse número (`cronograma_views.py:570-573`, comentada como "alinha a linha raiz ao mesmo
número no array do front"). No modo cliente esse laço não roda — a linha-raiz da grade
mantém o rollup hierárquico dela.

O PDF reproduz a assimetria **exatamente como está**, porque o critério deste spec é
papel-igual-a-tela e não papel-mais-certo-que-tela. Se essa diferença for um defeito, ela
é um defeito da tela, e consertá-la é outra rodada, com o número do card mudando à vista
de todos. Aqui ela fica registrada para não ser "corrigida" por engano na
implementação — o que faria o teste de paridade quebrar sem que ninguém entendesse por
quê.

---

## Layout

A4 retrato, margens de 18 mm.

**Cabeçalho** — logo à esquerda com 14 mm de altura e proporção preservada; à direita, em
7,5pt `#5A6472`: razão social, CNPJ, endereço e site. Abaixo, título em `Times-Roman`
navy `#1E2A4C` — "Cronograma da Obra" — e o nome da obra em corpo maior.

**Faixa de metadados** em `#F4F6F9`: cliente, período do plano (menor `data_inicio` →
maior `data_fim`), progresso geral e "emitido em".

**Tabela** `LongTable(repeatRows=1)` — a paginação e a repetição do cabeçalho vêm da
própria reportlab, e não de contagem de linhas escrita à mão:

| Traço | Regra |
|---|---|
| Cabeçalho | Fundo `#1E2A4C`, texto branco, 8pt |
| Zebra | `#F4F6F9` alternado |
| Grade | `#C9CED6` a 0,3pt |
| Tarefa-pai | Negrito, fundo navy a 6% |
| Tarefa-filha | Indentada 7pt por nível, dentro da célula |
| Marco | `◆` laranja `#E8620E` antes do nome; duração e % como `—` |
| Nome longo | `Paragraph` com quebra de linha — nunca cortado |
| Data ausente | `—` |
| Percentual | Inteiro com `%` (`100%`); marco sem percentual |

**Rodapé** — fio superior `#C9CED6`, `NOME DA EMPRESA · Cronograma — <obra>` à esquerda e
`pág. X/Y` à direita, 7,5pt `#8A93A3`. O `Y` exige a passada dupla do `canvasmaker`, que
é o padrão da reportlab para total de páginas.

**Botão** — um `<a target="_blank">` na toolbar de `templates/obras/cronograma.html`, ao
lado de "Físico-Financeiro", **fora** do bloco da flag do editor v2 (o export não depende
dela), levando `?cliente=1` quando `modo_cliente`.

## Casos de borda

| Situação | Comportamento |
|---|---|
| Obra sem tarefa nenhuma | PDF de uma página com "Nenhuma tarefa cadastrada" — não 500, não arquivo de zero byte |
| Tarefa arquivada (`ativa=False`) | Fica fora, como na tela |
| Obra de 300 tarefas | Só rende mais páginas; `LongTable` pagina sozinha |
| Logo base64 corrompida | Degrada para o nome em texto e loga |
| Tenant sem `ConfiguracaoEmpresa` | Cabeçalho com o nome padrão ("Empresa"), como `cronograma_obra` já faz |
| Falha ao montar os dados | Propaga — melhor erro visível que PDF mentiroso |
| Modo cliente numa obra sem cópia-cliente | PDF de uma página com "Nenhuma tarefa cadastrada"; é o que a tela também mostra |

## Testes — `tests/test_cronograma_pdf.py`

**Camada de dados** (sem PDF):

* EDT correta numa árvore de três níveis, e ordem idêntica a `ordenar_arvore_visual`;
* marco entra sem duração e sem percentual;
* tarefa arquivada fica fora;
* modo cliente lê só `is_cliente=True` e não vaza tarefa interna — e o inverso;
* **o guarda central:** o percentual de cada linha e o progresso geral do PDF batem com o
  que `cronograma_obra` entrega ao template, nos dois modos. É o teste que impede papel e
  tela de divergirem, e é ele que trava a extração de `progresso_geral_cliente`;
* a assimetria da linha-raiz, explicitamente: no modo interno a raiz sai com o progresso
  geral, no modo cliente sai com o rollup dela. Dois casos, para que ninguém "arrume" um
  dos lados sem ver o outro quebrar.

**Camada de arquivo:**

* bytes começam com `%PDF-`;
* obra vazia gera PDF válido;
* contagem de páginas por um helper que conta `/Type /Page` nos bytes — o repositório não
  tem `pypdf`, e `tests/test_cronograma_manual_pdf.py` já assina PDF por bytes.

**Rota:**

* 200 com `Content-Type: application/pdf` para quem pode ver;
* 404 para obra de outro tenant;
* 404 para usuário sem papel na obra com `escopo_obra_ativo` ligada;
* o botão aparece na página, e leva `cliente=1` no modo cliente.

## Fora de escopo

O gráfico de Gantt no PDF, o botão no portal do cliente, o anexo automático na medição, a
exportação de várias obras num arquivo e a fonte Georgia versionada. Cada um desses foi
considerado e recusado nesta rodada — os três primeiros por decisão explícita do Cássio na
conversa.
