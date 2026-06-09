# Design — Cadastro de Palavras-Chave de Classificação (Fluxo de Caixa)

**Data:** 2026-06-09
**Autor:** Cássio + Claude
**Status:** Aprovado (design) — pendente plano de implementação

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

## 5. Motor de matching (substitui `_classificar_categoria_nomeada`)

Função pura `classificar_por_cadastro(tipo, plano, descricao, fornecedor, tem_obra,
regras) -> (categoria_id, categoria_nome) | None`:

1. Monta campos de busca: `descricao`, `fornecedor`, `plano`, e `blob` (concatenado).
2. **Filtra candidatos**: `ativo` + `tipo` compatível + `condicao_obra` satisfeita +
   pelo menos uma `palavra` presente no(s) `campo_alvo` + nenhuma `excecao` presente.
3. **Seleciona vencedor**: menor `prioridade`. Empate desempata por:
   (a) palavra casada mais longa/específica; (b) `origem=usuario` > `sistema`;
   (c) campo específico (fornecedor) > `qualquer`.
4. Sem candidato → `None` (revisão manual + vira sugestão).

Performance: as regras são carregadas **uma vez** por importação (como já é feito com
funcionários/fornecedores/obras); o matching é todo em memória.

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

## 7. Motor de sugestões

Função pura sobre os lançamentos não classificados (`saidas_manual` / entradas no
fallback):

1. Tokeniza `fornecedor` + `descricao` (normalizado); gera termos candidatos —
   **priorizando n-gramas (1–3 palavras) do nome do fornecedor**.
2. Descarta termos já cobertos por alguma regra existente.
3. Agrega por termo: `ocorrencias`, `soma_valor`, um `exemplo`.
4. Ordena por `ocorrencias × soma_valor` (resolve o que mais importa primeiro).
5. Persiste em `PalavraChaveSugestao` (substituindo as do tenant).

No painel: usuário escolhe a categoria por termo e cadastra em lote → cria
`PalavraChaveCategoria` (`origem='usuario'`, `campo_alvo='fornecedor'` por padrão,
`prioridade=40`). Após salvar, o preview é **re-classificado na hora**.

## 8. UI / Rotas

Estende `views/catalogos_views.py` (lar natural — já existe o catálogo de categorias):

- `GET  /catalogos/palavras-chave` — tabela + filtros (busca, categoria, origem) +
  painel de sugestões.
- `POST /catalogos/palavras-chave/criar`
- `POST /catalogos/palavras-chave/<id>/editar`
- `POST /catalogos/palavras-chave/<id>/toggle`
- `POST /catalogos/palavras-chave/<id>/excluir`
- `POST /catalogos/palavras-chave/sugestoes/cadastrar` — criação em lote.

Templates: `catalogos/palavras_chave.html` + parcial de formulário (modal).
Base visual: o mockup já validado (`static/mockups/palavras_chave_mockup.html`).

**Detecção de conflito** no salvar: duas regras com mesma palavra + mesma prioridade
+ mesma especificidade apontando para categorias diferentes → a tela **avisa** em vez
de escolher silenciosamente.

**Integração no preview de importação**: o painel de sugestões também aparece em
`templates/importacao/preview_fluxo.html`, onde os dados não classificados já existem.

## 9. Testes

- **Regressão (crítico):** rodar o motor NOVO (semeado a partir do hardcode) sobre o
  Excel real e comparar a distribuição de categorias com a saída do motor ANTIGO. A
  migração não pode alterar classificações (exceto a redefinição auto/manual da §3,
  que é validada à parte). Base: `tests/_test_fluxo_classificacao.py`.
- **Unitários do matching:** prioridade, exceções, `condicao_obra`, desempates.
- **Unitários das sugestões:** agregação, ordenação, exclusão de termos já cobertos.
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
