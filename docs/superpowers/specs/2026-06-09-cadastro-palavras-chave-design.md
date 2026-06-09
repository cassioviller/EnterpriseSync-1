# Design — Cadastro de Palavras-Chave de Classificação (Fluxo de Caixa)

**Data:** 2026-06-09 (rev. 2 — pós grill-with-docs)
**Autor:** Cássio + Claude
**Status:** Aprovado (design)
**Relacionados:** ADR `docs/adr/0002-classificacao-fluxo-caixa-via-cadastro-por-tenant.md`,
glossário `CONTEXT.md` (seção Importação / Classificação de Fluxo de Caixa)

> **Terminologia (canônica — ver CONTEXT.md):** a unidade que o usuário cadastra é uma
> **Regra de Classificação** (não "palavra-chave"); o conjunto de palavras dela é o
> **Gatilho**. Um lançamento que não casa regra específica é um **Pendente de
> Classificação**. Pendentes são agrupados por **Termo** recorrente. Uma decisão de
> categoria em um lançamento individual é uma **Correção** (memorizada via **Memória
> Exata**). Propostas que viram regra só com confirmação são **Sugestões**.

## 1. Objetivo

Substituir a lógica de classificação **hardcoded** da importação de Fluxo de Caixa
(`services/importacao_excel.py`) por um **cadastro de palavras-chave por tenant,
editável pelo usuário**. O classificador passa a ler 100% do banco; o hardcode é
aposentado. Adicionalmente, um **motor de sugestões** analisa os lançamentos que
caíram em "revisão manual" e propõe novas palavras-chave (ex.: `maranhão →
Subempreitada`), resolvendo vários lançamentos de uma vez.

Motivação: importar os dados específicos da Veks da forma mais rápida, deixando o
campo pronto para o usuário apenas dizer "isso é subempreitada" e o sistema passar
a reconhecer a palavra dali em diante.

## 2. Decisão de arquitetura

**Migração total para o banco** (escolhida pelo usuário). Todas as ~300 regras do
classificador nomeado viram linhas no cadastro, inclusive as compostas. O hardcode
`_classificar_categoria_nomeada` é retirado de produção (mantido temporariamente
apenas como *oráculo* de teste de regressão, depois removido).

## 3. Escopo de classificação

Hoje existem duas saídas de classificação:

- **(a) `tipo_categoria`** (macro: MATERIAL, SALARIO…) — hoje decide auto vs revisão
  manual e alimenta `GestaoCustoPai.tipo_categoria`.
- **(b) `categoria_fluxo_caixa_id` / `categoria_nome`** (uma das ~45 categorias
  nomeadas do tenant) — alimenta o relatório de Fluxo de Caixa e é o que o cadastro
  modela.

**Unificação:** o cadastro dirige **(b)**. O macro **(a)** passa a ser **derivado**
da categoria nomeada por um mapa fixo `categoria_nome → tipo_categoria`. Assim há uma
única fonte de verdade (palavra → categoria nomeada), e o conjunto de keywords macro
separado é eliminado.

**Redefinição de auto vs revisão manual** (mudança de comportamento intencional):
- **Auto** = o cadastro produziu uma categoria nomeada específica.
- **Revisão manual** = caiu no fallback genérico (`Outras Saídas` / `Outros
  Recebimentos`).

Vale tanto para a aba **Saída** quanto **Entrada** (as regras `ENTRADA` do
classificador atual também migram).

## 4. Modelo de dados

### `PalavraChaveCategoria` (nova tabela)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | PK | |
| `admin_id` | FK usuario | tenant |
| `categoria_fluxo_caixa_id` | FK | destino (categoria nomeada) — **único** |
| `palavras` | Text | lista separada por vírgula/linha; normalizada; semântica **OU** |
| `campo_alvo` | String | `qualquer` \| `descricao` \| `fornecedor` \| `plano` (aceita múltiplos por vírgula) |
| `excecoes` | Text (null) | lista OU; se qualquer aparecer, a regra é anulada |
| `condicao_obra` | String | `indiferente` \| `com_obra` \| `sem_obra` |
| `prioridade` | Integer | default 50; **menor decide primeiro** |
| `tipo` | String | `SAIDA` \| `ENTRADA` (espelha o tipo da categoria) |
| `origem` | String | `sistema` (semeado) \| `usuario` |
| `ativo` | Boolean | |
| `created_at` / `updated_at` | DateTime | |

Índice: `(admin_id, ativo, tipo, prioridade)`.

### `PalavraChaveSugestao` (nova tabela — alimenta o painel de sugestões)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | PK | |
| `admin_id` | FK usuario | |
| `termo` | String | termo recorrente normalizado |
| `ocorrencias` | Integer | nº de lançamentos não classificados que contêm o termo |
| `soma_valor` | Numeric | Σ valor desses lançamentos |
| `exemplo` | String | uma descrição de exemplo |
| `tipo` | String | `SAIDA` \| `ENTRADA` |
| `dismissed` | Boolean | usuário descartou a sugestão |
| `created_at` | DateTime | |

Refeita (substituída) a cada importação para o tenant.

### `CorrecaoClassificacao` (nova tabela — Correção + Memória Exata)

Registra a decisão de categoria feita pelo usuário em um lançamento individual no
drill-down de um Termo, para reaplicação automática (Memória Exata) e para alimentar
Sugestões de regra refinada.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | PK | |
| `admin_id` | FK usuario | |
| `texto_norm` | String | descrição+fornecedor normalizados — chave da Memória Exata |
| `categoria_fluxo_caixa_id` | FK | categoria escolhida pelo usuário |
| `termo_origem` | String (null) | Termo cuja regra foi contrariada (ex.: `maranhão`) |
| `tipo` | String | `SAIDA` \| `ENTRADA` |
| `created_at` | DateTime | |

Índice único: `(admin_id, texto_norm)` — reaplicação O(1) por texto idêntico.

## 5. Motor de matching (substitui `_classificar_categoria_nomeada`)

Função pura `classificar_por_cadastro(tipo, plano, descricao, fornecedor, tem_obra,
regras) -> (categoria_id, categoria_nome) | None`:

1. Monta campos de busca: `descricao`, `fornecedor`, `plano`, e `blob` (concatenado).
2. **Filtra candidatos**: `ativo` + `tipo` compatível + `condicao_obra` satisfeita +
   pelo menos uma `palavra` presente no(s) `campo_alvo` + nenhuma `excecao` presente.
3. **Seleciona vencedor**: menor `prioridade`. Empate desempata por:
   (a) palavra casada mais longa/específica; (b) `origem=usuario` > `sistema`;
   (c) campo específico (fornecedor) > `qualquer`.
4. Sem candidato → consulta **Memória Exata** (`CorrecaoClassificacao` por
   `texto_norm`); se houver, usa a categoria da Correção. Senão → `None` (vira
   Pendente de Classificação + alimenta Sugestões).

Ordem de resolução por lançamento: **Regra de Classificação** (por prioridade) →
**Memória Exata** → Pendente.

Performance: regras e correções são carregadas **uma vez** por importação (como já é
feito com funcionários/fornecedores/obras); o matching é todo em memória.

## 6. Semeadura (migração do hardcode)

Script/CLI **idempotente** que converte cada bloco de regra do
`_classificar_categoria_nomeada` (e dos mapas de plano/keywords) em linhas
`PalavraChaveCategoria` com `origem='sistema'`:

- `palavras` = a lista de keywords do bloco.
- `campo_alvo` = `descricao` se a regra usava `hd(...)`, senão `qualquer` (`hb`).
- `prioridade` = posição na cascata × 10 (preserva a ordem "específico antes de
  genérico").
- `excecoes` = as cláusulas `and not hd(...)` (ex.: regra de salário exclui `diaria`).
- `condicao_obra` = derivada das ramificações `tem_obra` (ex.: vale transporte vira
  **duas** linhas: `com_obra → Transporte de Obra`, `sem_obra → Benefício Transporte`).

Executável por `admin_id` (as regras são idênticas no seed; cada tenant recebe sua
cópia editável). Idempotente: re-rodar não duplica.

## 7. Fila de trabalho, sugestões e aprendizado

A unidade de trabalho do usuário **não é a linha, é o Termo**. O objetivo é classificar
o máximo de lançamentos com o mínimo de cliques e convergir para "quase zero ajuste
manual" nas importações seguintes.

### 7.1 Fila por Termo (Sugestões de regra)

Função pura sobre os Pendentes de Classificação:

1. Tokeniza `fornecedor` + `descricao` (normalizado); gera termos candidatos —
   **priorizando n-gramas (1–3 palavras) do nome do fornecedor**.
2. Descarta termos já cobertos por alguma regra existente.
3. Agrega por termo: `ocorrencias`, `soma_valor`, um `exemplo`.
4. Ordena por `ocorrencias × soma_valor` (resolve o que mais pesa primeiro).
5. Persiste em `PalavraChaveSugestao` (substituindo as do tenant).

Ao classificar um Termo, cria-se uma **Regra de Classificação**
(`origem='usuario'`, `campo_alvo='fornecedor'` por padrão, `prioridade=40`) e o preview
é **reclassificado ao vivo, sem re-upload** — os lançamentos daquele termo saem da fila
na hora. (Loop ao vivo dentro do preview — ver §7.4.)

### 7.2 Drill-down por contexto

Clicar na contagem de um Termo (ex.: "18 lançamentos") **expande os lançamentos
individuais** (data, descrição, fornecedor, valor, obra). Necessário porque o termo
sozinho às vezes não revela a categoria — o contexto revela. Implica manter os
lançamentos do preview **vivos no servidor** durante a sessão (não só agregados).

### 7.3 Correção e aprendizado

No drill-down, o usuário pode dar uma **Correção** em um lançamento individual cujo
contexto contraria a regra do Termo (ex.: dentre 18 "maranhão", 2 são compra de
material). A Correção:

- vale para aquela importação (o lançamento muda de categoria e sai da fila);
- **não cria regra sozinha** (não polui o cadastro);
- é gravada em `CorrecaoClassificacao`, gerando dois aprendizados:
  - **Memória Exata (automática):** texto idêntico em importação futura já vem
    classificado, sem ação do usuário;
  - **Sugestão de regra refinada (confirmada):** o sistema detecta o token distintivo
    e oferece *"virar regra? `maranhão + material → Materiais`"* com **prioridade maior**
    que a regra do termo (para vencer o conflito). Vira regra **só com 1 clique** do
    usuário — nunca silenciosamente.

### 7.4 Loop ao vivo (sequência)

Upload → classificação → fila por Termo no preview → usuário classifica termos e/ou
corrige linhas → reclassificação em memória a cada ação (sem re-upload) → quando a fila
está no ponto, **Confirmar** persiste o lote. Sem ida-e-volta para uma página separada.

## 8. UI / Rotas

Estende `views/catalogos_views.py` (lar natural — já existe o catálogo de categorias):

- `GET  /catalogos/palavras-chave` — tabela + filtros (busca, categoria, origem) +
  painel de sugestões.
- `POST /catalogos/palavras-chave/criar`
- `POST /catalogos/palavras-chave/<id>/editar`
- `POST /catalogos/palavras-chave/<id>/toggle`
- `POST /catalogos/palavras-chave/<id>/excluir`
- `POST /catalogos/palavras-chave/sugestoes/cadastrar` — criação em lote.

No preview de importação (`importacao_views.py`):

- `POST /importacao/fluxo-caixa/classificar-termo` — classifica um Termo → cria Regra,
  reclassifica o payload em memória e devolve a fila atualizada.
- `POST /importacao/fluxo-caixa/corrigir-linha` — grava uma Correção
  (`CorrecaoClassificacao`), aplica à linha e oferece a Sugestão de regra refinada.
- `POST /importacao/fluxo-caixa/confirmar-regra-refinada` — efetiva a Sugestão de
  regra refinada (1 clique).

Templates: `catalogos/palavras_chave.html` + parcial de formulário (modal).
Base visual: o mockup `static/mockups/palavras_chave_mockup.html` — **a ser portado em
light-only** (o mockup está em dark, que **viola** o `DESIGN.md` "o sistema é
light-only"; a página real deve seguir o padrão claro). Não expor nomes internos de
tabela/modelo na UI (regra do `DESIGN.md`): falar "regra"/"palavra-chave", nunca
`PalavraChaveCategoria`.

**Loop ao vivo no preview** (§7.4): a fila por Termo e o drill-down ficam em
`templates/importacao/preview_fluxo.html`, com os lançamentos vivos no servidor durante
a sessão. A página `/catalogos/palavras-chave` é o CRUD completo das regras + visão das
sugestões.

**Detecção de conflito** no salvar: duas regras com mesma palavra + mesma prioridade
+ mesma especificidade apontando para categorias diferentes → a tela **avisa** em vez
de escolher silenciosamente.

## 9. Testes

- **Regressão (crítico):** rodar o motor NOVO (semeado a partir do hardcode) sobre o
  Excel real e comparar a distribuição de categorias com a saída do motor ANTIGO. A
  migração não pode alterar classificações (exceto a redefinição auto/manual da §3,
  que é validada à parte). Base: `tests/_test_fluxo_classificacao.py`.
- **Unitários do matching:** prioridade, exceções, `condicao_obra`, desempates,
  **ordem Regra → Memória Exata → Pendente**.
- **Unitários das sugestões:** agregação, ordenação, exclusão de termos já cobertos.
- **Correção / Memória Exata:** texto idêntico reaparece → reaplica categoria;
  Correção não cria regra; Sugestão de regra refinada só vira regra com confirmação.
- **Idempotência do seed.**

## 10. Decisões de escopo (YAGNI)

- Macro `tipo_categoria` **derivado** da categoria nomeada (sem cadastro de macro
  separado).
- Entradas e saídas usam o mesmo motor.
- O hardcode antigo vira oráculo de teste e depois é removido.
- Sem versionamento/histórico de regras nesta fase.
- Sugestões: n-gramas de 1–3 palavras; sem ML, só frequência × valor.

## 11. Riscos

- **Fidelidade do seed:** reproduzir as ~300 regras (com ordem, exceções e condições)
  exige cuidado; o teste de regressão é a rede de segurança.
- **Mudança auto/manual** (§3) altera a contagem do split — intencional, mas precisa
  ser comunicada e validada.
- **Volume na tela:** ~300 linhas no cadastro — busca + filtro + paginação seguram.
