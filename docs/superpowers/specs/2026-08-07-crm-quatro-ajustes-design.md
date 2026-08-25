# CRM — quatro ajustes: dropdowns, tag Validado, prazo e exportação

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **REALIZADA** — o plano correspondente foi executado e o código está na árvore.
>
> Veredito dado por **existência de código na árvore**, não por checkbox nem por
> mensagem de commit. Índice completo em `docs/planos-em-aberto-2026-08-25.md`.


**Data:** 2026-08-07
**Origem:** pedido do Cássio em sessão, ao abrir o módulo CRM.
**Escopo:** quatro itens fechados. O quinto pedido — **Indicadores** (conversão, funil,
desempenho) — foi separado por decisão dele e ganha **spec próprio**, porque tem
decisões de desenho que estes quatro não têm.

---

## Por que existe

O Cássio levantou cinco coisas no CRM. Quatro delas são pequenas e independentes; uma
delas nem é pedido de funcionalidade — é defeito. Este spec cobre as quatro:

| # | O que ele disse | O que é de fato |
|---|---|---|
| 1 | "origem de classificação está bugada, não está aparecendo certo" | **Defeito**: os sete dropdowns do CRM renderizam vazios |
| 2 | "tirar a tag validado depois que coloca na coluna enviado" | **Defeito de exibição**: o badge nunca some |
| 3 | "prazo de 3 dias úteis depois da chegada do lead" | **Funcionalidade nova**: sugestão automática de prazo |
| 4 | "exportar excel com todos campos" | **Funcionalidade nova**: exportação, que não existe |

---

## 1. Dropdowns vazios — a origem que não aparece

### O defeito, provado

O motor de dropdowns tem **duas fontes**:

- as tabelas legadas `crm_origem`, `crm_responsavel`, `crm_cadencia`, `crm_situacao`,
  `crm_tipo_material`, `crm_tipo_obra`, `crm_motivo_perda` — **fonte de verdade das FKs
  em `Lead`**, e é contra elas que `_validar_fk_tenant` valida na gravação;
- `dropdown_grupo` / `dropdown_opcao` — de onde o formulário **lê**, via
  `_listas_para_form` → `get_dropdown_options('crm_<slug>', admin_id, for_form=True)`.

Estado medido no banco de dev em 07/08:

| Tabela | Linhas |
|---|---|
| `dropdown_grupo` | **0** |
| `dropdown_opcao` | **0** |
| `crm_origem` (tenant `admin_id=1`) | 6 (Loja, Indicação, Anúncio Meta Ads, Google, Site, Prospecção Ativa) |
| `lead` | 367, dos quais **12 com `origem_id` preenchido** |

`get_dropdown_options` faz `DropdownGrupo.query.filter_by(slug=..., admin_id=...).first()`
e, quando não acha, **retorna `[]` sem log e sem erro**. O `<select>` de Origem em
`templates/crm/lead_form.html` renderiza sem nenhuma `<option>`, e a origem já gravada
não aparece marcada porque a opção não existe na lista para receber o `selected`.

Vale para os **sete** dropdowns, não só origem. O Cássio notou na origem porque é a que
usa.

### A causa

- A migração **173** cria os `DropdownGrupo` **só para os tenants que existiam naquele
  momento**.
- A migração **174** copia as opções das tabelas legadas com
  `JOIN dropdown_grupo dg ON dg.slug = :slug AND dg.admin_id = t.admin_id`. Sem grupo, o
  JOIN não casa: **zero linhas copiadas, e a migração reporta `success` do mesmo jeito**.
- Existe `seed_grupos_sistema` chamado na criação de admin (`views/admin.py`), mas quem
  nasce fora desse caminho fica sem grupo para sempre.
- O leitor **não tem plano B**.

As duas migrações estão registradas como `success` (22/07) e as tabelas estão vazias —
prova de que "migração verde" não garante dado semeado neste caminho.

### O conserto — decisão D-CRM.1: backfill + fallback

Duas peças, cada uma resolvendo uma metade. **Cinto e suspensório**, escolha do Cássio
entre quatro alternativas apresentadas.

**(a) Migração 282** — o número 281 foi gasto na B6.1.

Para **todo** tenant com linha em qualquer tabela `crm_*`: cria o `DropdownGrupo` que
falta (slug + label de `CRM_GRUPOS_META`) e copia as opções da tabela legada, com
`ext_id` apontando de volta para o id legado.

Idempotente por `WHERE NOT EXISTS` nas duas etapas — roda igual num dev vazio e numa
produção já populada. É exatamente onde a 174 falhou: **cria o grupo antes de tentar o
JOIN**.

**(b) Fallback no leitor** — `services/dropdown_service.get_dropdown_options`.

Quando o slug é de CRM (`slug in _CRM_MODELO_MAP`) e **o grupo não existe, ou existe com
zero linhas em `dropdown_opcao`**, lê da tabela legada correspondente.

O gatilho é **zero linhas**, não "zero linhas ativas" — e a diferença importa. Um grupo
com opções todas desativadas é um estado **deliberado** do admin; cair no legado ali
ressuscitaria justamente o que ele desativou. Um grupo com nenhuma linha nunca foi
semeado. Só o segundo caso dispara o fallback.

O caso "grupo existe e está vazio" não é hipotético: `ensure_grupo` é chamado por
`cadastros_views.py` quando alguém abre a tela de cadastros, e cria o grupo sem nenhuma
opção. Um fallback que só olhasse a ausência do grupo deixaria esse tenant vazio.

O objeto devolvido precisa servir aos dois formatos de chamada que já existem:

| Chamador | Campos que usa |
|---|---|
| `_listas_para_form` (`for_form=True`) | `.id`, `.nome` |
| `get_opcoes_valores` e derivados | `.valor` |

Portanto o wrapper expõe **`id`** (= id legado, que é o que a FK do `Lead` espera),
**`nome`**, **`valor`** (mesmo texto que `nome`) e **`ativo`**. Só itens ativos, mantendo
o contrato atual de `for_form`.

### O que NÃO muda

O caminho de **gravação** já está correto: `_salvar_lead` valida cada FK com
`_validar_fk_tenant`, que consulta as tabelas legadas. O defeito é exclusivamente de
leitura. Nenhuma FK de lead existente é reescrita.

---

## 2. A tag "Validado"

### O defeito

`crm_views.py`, rota `mudar_status`: ela nunca zera `validacao_aprovada`. O card em
`templates/crm/kanban.html` mostra o badge "Validado — pronto para envio" olhando só esse
booleano, sem consultar o status. Resultado: a tag acompanha o lead até Aprovado.

`templates/crm/lista.html` tem o mesmo badge com a mesma falha — as duas telas divergem
hoje em detalhes de exibição e passam a seguir a mesma regra.

### O conserto — decisão D-CRM.2: esconder, não apagar

- O badge aparece **só enquanto o lead está antes de Enviado** — a lista positiva é
  **Em fila, Em andamento e Validação**. Some em **Enviado, Aprovado, Feedback, Perdido
  e Congelado** (Feedback é pós-envio: "aguardando retorno" pressupõe proposta enviada).
  Mesma regra no kanban e na lista.
- O botão "Marcar como Validado" também sai de lead já enviado, onde não faz sentido.
- **Os campos `validacao_aprovada`, `validado_por_id` e `validado_em` NÃO são apagados.**

O último ponto é o que importa: são trilha de auditoria — quem liberou o orçamento e
quando. Zerar o booleano tiraria o badge da tela e junto a resposta dessa pergunta. A
mudança é de **exibição**, não de dado.

---

## 3. Prazo de 3 dias úteis

### Como é hoje

`Lead.prazo` é um `Date` nulo, preenchido à mão num `<input type="date">`. Nada calcula
nada. O kanban já tem semáforo de urgência lendo esse campo — que hoje só funciona nos
leads em que alguém lembrou de preencher.

### O conserto — decisão D-CRM.3: sugestão automática, editável

Três peças:

**(a) Helper `somar_dias_uteis(data, n)` em `utils.py`** — onde a contagem de dia útil do
sistema já mora. **Segunda a sexta, sem feriado**: é o mesmo critério que `utils.py` já
aplica em todo cálculo do projeto (`weekday() < 5`), e **não existe tabela de feriado no
projeto**. Premissa assumida e confirmada com o Cássio.

**(b) No formulário de lead novo** (`templates/crm/lead_form.html` via `crm.novo`):
`data_chegada` nasce com **hoje** — hoje ela renderiza em branco — e `prazo` nasce com
**hoje + 3 dias úteis**. Os dois editáveis.

**(c) Garantia no servidor** — em `_salvar_lead`, lead **novo** que chegar com `prazo`
vazio recebe `data_chegada + 3 dias úteis`. Isso vale mesmo se o JS não rodar ou alguém
limpar o campo. A pré-preenchida é para os olhos; esta é para o dado.

### Fronteiras

- **Editar lead existente nunca recalcula.** O `prazo` continua sob controle de quem
  edita, e a mudança segue indo para o `LeadHistorico` como já vai.
- **Nenhum backfill.** Os leads já existentes não são tocados — decisão do Cássio, para
  não inventar data de cobrança retroativa em lead antigo, que nasceria vermelho no
  semáforo.

---

## 4. Exportar Excel

### Decisões tomadas

| Decisão | Escolha |
|---|---|
| Alcance | **Todos os leads do tenant** — sem aplicar os filtros da tela |
| Campos | **Todos** os da tabela `lead`, exceto `admin_id` |
| Permissão | **Só admin**, como já é o `exportar_modelo` |
| Volta pelo importador | **Não.** É só exportar |

### Rota

`GET /crm/exportar`, `@login_required`, admin-only. Botão ao lado do "Baixar Modelo" que
já existe em `templates/crm/lista.html`.

A query usa **`_query_leads_visiveis(admin_id)` sem `_aplicar_filtros`**. O helper
continua no caminho porque é ele que garante o isolamento entre tenants; para um admin
ele já devolve o funil inteiro.

### Aba: `Leads` — deliberadamente NÃO `Lead.2026`

O importador casa colunas **pelo nome do cabeçalho** (case-insensitive) e exige a aba
`Lead.2026`. Usar outro nome de aba torna a planilha exportada **impossível de
reimportar por engano** — e isso é proposital: o importador hoje só **cria** leads, não
reconhece `ID` para atualizar. Exportar 12 leads, corrigir uma célula e reimportar viraria
24 leads. O nome da aba é a trava.

### As 37 colunas, na ordem

A tabela `lead` tem **37 colunas**. Tirando `admin_id`, sobram **36** para a planilha; com
a coluna derivada `Dias parado no status`, a aba sai com **37**.

Agrupadas por assunto, não espelhando o modelo de importação (a ordem é livre, já que o
importador casa por nome — e aqui não há importação de volta):

| Grupo | Colunas | Nº |
|---|---|---|
| Identificação | `ID`, `Nome`, `Status` | 3 |
| Contato | `Contato Lead`, `E-mail` | 2 |
| Datas | `Data de Chegada`, `Prazo`, `Data de Envio`, `Data de Retomada` | 4 |
| Comercial | `Valor da Proposta`, `Prioridade`, `Demanda`, `Observação` | 4 |
| Classificação | `Origem`, `Cadência`, `Situação`, `Tipo de Material`, `Tipo de obra`, `Motivo da Perda` | 6 |
| Pessoas | `Responsável`, `Vendedor`, `Orçamentista` | 3 |
| Local | `Localização`, `Detalhes Loc.`, `Pasta` | 3 |
| Validação | `Validado`, `Validado por`, `Validado em`, `Comentário de revisão` | 4 |
| Vínculos | `Cliente`, `Proposta`, `Obra` | 3 |
| Auditoria | `Criado por`, `Criado em`, `Atualizado em`, `Status alterado em` | 4 |
| Derivada | `Dias parado no status` | 1 |
| | **Total** | **37** |

**As FKs saem pelo nome**, não pelo id: `Origem` = "Indicação", não `2`. Vale para as sete
listas mestras, para os três responsáveis, e para `Cliente`, `Proposta` e `Obra`.

`Dias parado no status` é a única coluna **derivada** (de `status_changed_at`) — entra
porque responde "qual lead está encalhado" sem ninguém fazer conta.

### Apresentação

- **AutoFiltro** ligado em toda a faixa (`ws.auto_filter.ref`) — cada cabeçalho já vem com
  a setinha de filtro do Excel.
- **Painéis congelados em `D2`**: cabeçalho fixo no topo, e `ID`/`Nome`/`Status` fixos à
  esquerda, para não perder de vista qual lead é ao rolar pelas 37 colunas.
- Cabeçalho no mesmo **azul `1F4E79`** com texto branco em negrito que a planilha-modelo
  já usa — as duas saem com a mesma cara.
- **Larguras por coluna**: data ~12, `Nome` ~32, `Demanda` e `Observação` ~45. Não 18 para
  tudo, como o `exportar_modelo` faz hoje.
- **Tipos nativos, não texto**: `Valor da Proposta` como número com formato
  `R$ #,##0.00` (soma e ordena de verdade no Excel); datas como data em `DD/MM/AAAA`;
  datetimes em `DD/MM/AAAA HH:MM`; `Prioridade` e `Validado` como `Sim`/`Não`.
- **Zebra** nas linhas, e a célula de `Status` tingida com a cor daquela coluna do kanban.
- Nome do arquivo: `leads_crm_AAAA-MM-DD.xlsx`.

### Fora de escopo, de propósito

**Aba de resumo** com contagem e valor por status. É o começo do **Indicadores**, que tem
spec próprio. Meia versão aqui tiraria a versão inteira de lá.

---

## Testes

Red-first, na disciplina das rodadas B5/B6: cada teste falha antes do conserto e passa
depois.

| # | Teste | Vermelho antes porque |
|---|---|---|
| 1 | Tenant sem `DropdownGrupo` → `_listas_para_form` devolve as 6 origens da tabela legada | hoje devolve `[]` |
| 1b | Grupo **existe com zero opções** → também cai no legado | hoje devolve `[]` |
| 1c | Grupo existe com opções **todas desativadas** → devolve `[]`, **não** cai no legado | — (guarda contra ressuscitar o que o admin desativou) |
| 2 | Migração 282 rodada duas vezes não duplica opção nem grupo | — (guarda de idempotência) |
| 3 | Migração 282 num tenant com `crm_*` populado e `dropdown_grupo` vazio cria grupo + opções com `ext_id` correto | hoje o JOIN da 174 não casa |
| 4 | Lead com `validacao_aprovada=True` em **Enviado** → o HTML do kanban **não** contém "Validado" | hoje contém |
| 5 | Lead com `validacao_aprovada=True` em **Validação** → o HTML **contém** "Validado" | — (guarda contra esconder demais) |
| 6 | Lead novo salvo sem `prazo` → `prazo == data_chegada + 3 dias úteis` | hoje fica `None` |
| 7 | Chegada numa **quinta** → prazo na **terça** seguinte | prova que atravessa o fim de semana |
| 8 | Editar lead antigo sem mexer no prazo **não** recalcula | guarda da fronteira |
| 9 | Admin recebe xlsx com **todas** as linhas do tenant, ignorando qualquer filtro na query string | a rota não existe |
| 10 | Lead de **outro tenant** não aparece na exportação | guarda de isolamento |
| 11 | Não-admin é barrado na exportação | guarda de permissão |

O teste 7 é o que realmente prova a regra de dias úteis — um teste com chegada na segunda
passaria mesmo com uma implementação que só somasse 3 dias corridos.

O teste 5 existe pelo precedente da WF-4: *guarda de teste sem o dado que ela guarda é
guarda vazia*. Sem ele, uma implementação que escondesse o badge em **todos** os status
passaria no teste 4.

---

## Tratamento de erro

| Situação | Comportamento |
|---|---|
| Exportação sem nenhum lead | Planilha sai com cabeçalho e AutoFiltro, sem linhas. **Não é erro** |
| Não-admin tenta exportar | `flash` + redirect para `crm.lista` — mesmo padrão do `exportar_modelo` |
| Grupo de dropdown ausente | Fallback silencioso para a tabela legada, **com log em nível INFO** para o caso não sumir de vista de novo |
| Migração 282 num tenant sem nenhuma tabela `crm_*` populada | Não faz nada. Sem erro |

---

## Ordem de execução sugerida

1. **Dropdowns** (migração 282 + fallback) — é defeito, e é o que impede o cadastro hoje.
2. **Tag Validado** — mudança só de template, independente.
3. **Prazo** — helper + form + `_salvar_lead`.
4. **Exportação** — a maior das quatro, e a única que não depende de nenhuma outra.

As quatro são independentes entre si. A única sobreposição de arquivo é
`crm_views.py`, tocado pelos itens 3 e 4 em regiões distintas
(`_salvar_lead` × rota nova no fim).

---

## Decisões registradas

| Decisão | Escolha do Cássio |
|---|---|
| **D-CRM.1** | Dropdowns: **migração de backfill + fallback no leitor** (entre 4 alternativas) |
| **D-CRM.2** | Tag Validado: esconder da coluna Enviado em diante, **preservando os campos de auditoria** |
| **D-CRM.3** | Prazo: **sugestão automática editável**, não regra dura |
| **D-CRM.4** | Prazo: **só leads novos** — sem backfill dos 367 existentes |
| **D-CRM.5** | Exportação: **todos os leads, todos os campos**, sem filtros de tela |
| **D-CRM.6** | Exportação: **só exportar** — aba `Leads`, sem volta pelo importador |

Premissas assumidas e confirmadas: **dias úteis = seg-sex sem feriado** (precedente do
`utils.py`, e não há tabela de feriado no projeto) e **exportar é ação de admin**
(precedente do `exportar_modelo`).

---

## Ressalva

Todo o diagnóstico do item 1 foi medido **no banco de dev**. Em produção o estado de
`dropdown_grupo`/`dropdown_opcao` pode ser outro, e pela decisão anterior do Cássio não se
consulta produção. Por isso o conserto foi desenhado para ser **correto nos dois
cenários**: a migração é idempotente e o fallback não supõe nada sobre o que existe lá.

---

## Fora deste spec

**Indicadores** — conversão por etapa, tempo médio parado, valor no funil, ranking por
vendedor, motivo de perda mais comum. A matéria-prima existe (`LeadHistorico` grava cada
mudança de status, `status_changed_at`, `valor_proposta`, `motivo_perda_id`). Ganha spec
próprio, por decisão do Cássio, para não travar estes quatro consertos atrás de uma
feature grande.
