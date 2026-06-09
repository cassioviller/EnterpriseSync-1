# Plano — Cadastro de Palavras-Chave de Classificação (Fluxo de Caixa)

**Spec:** `docs/superpowers/specs/2026-06-09-cadastro-palavras-chave-design.md`
**Data:** 2026-06-09
**Branch:** `feat/cadastro-palavras-chave`

Princípio: cada passo é um commit pequeno e verificável. A fatia vertical (motor +
seed + teste de regressão) vem cedo, antes da UI, pra garantir que a migração não
altera classificações.

---

## FASE A — Fundação (modelos + tabelas)

### Passo 1 — Modelos `PalavraChaveCategoria` e `PalavraChaveSugestao`
**Arquivo:** `models.py` (logo após `class CategoriaFluxoCaixa`, ~L6863)

- `PalavraChaveCategoria` com campos da §4 do spec: `id`, `admin_id` (FK usuario),
  `categoria_fluxo_caixa_id` (FK), `palavras` (Text), `campo_alvo` (String, default
  `'qualquer'`), `excecoes` (Text, null), `condicao_obra` (String, default
  `'indiferente'`), `prioridade` (Integer, default 50), `tipo` (String), `origem`
  (String, default `'usuario'`), `ativo` (Boolean, default True), `created_at`,
  `updated_at`.
- `PalavraChaveSugestao`: `id`, `admin_id`, `termo`, `ocorrencias`, `soma_valor`
  (Numeric), `exemplo`, `tipo`, `dismissed` (Boolean default False), `created_at`.
- `__tablename__` = `palavra_chave_categoria` / `palavra_chave_sugestao`.

### Passo 2 — Migration das duas tabelas
**Arquivo:** `migrations.py`

- Dois blocos `CREATE TABLE IF NOT EXISTS` (padrão do arquivo), com índice
  `(admin_id, ativo, tipo, prioridade)` em `palavra_chave_categoria`.
- Registrar na sequência de execução de migrations como os demais.

---

## FASE B — Motor de matching (puro, testável, ainda não ligado)

### Passo 3 — Função de classificação por cadastro
**Arquivo novo:** `services/classificador_cadastro.py`

- `classificar_por_cadastro(tipo, plano, descricao, fornecedor, tem_obra, regras)`
  retornando `(categoria_id, categoria_nome)` ou `None`. Lógica da §5 do spec:
  filtro de candidatos + seleção por menor prioridade + desempates
  (especificidade → origem usuário → campo específico).
- Reaproveitar `_normalizar` de `importacao_excel.py` (mover para `utils` comum ou
  importar).
- `MACRO_POR_CATEGORIA: dict[str,str]` — mapa categoria nomeada → `tipo_categoria`
  macro (substitui o cadastro de macro). Função `derivar_macro(categoria_nome)`.

### Passo 4 — Testes unitários do motor
**Arquivo novo:** `tests/test_classificador_cadastro.py`

- Casos: match simples; OU entre palavras; exceção anula; `condicao_obra`
  com/sem obra; empate resolvido por prioridade; empate resolvido por origem;
  campo-alvo `descricao` vs `fornecedor`; nenhum match → None.

---

## FASE C — Seed (hardcode → linhas) + regressão

### Passo 5 — Definição declarativa das regras do sistema
**Arquivo novo:** `services/seed_palavras_chave.py`

- Constante `REGRAS_SISTEMA: list[dict]` reproduzindo fielmente cada bloco de
  `_classificar_categoria_nomeada` (ENTRADA e SAÍDA) como dict
  `{palavras, categoria_nome, campo_alvo, excecoes, condicao_obra, prioridade}`.
- `prioridade` = ordem na cascata × 10. Regras compostas conforme §6 (salário exclui
  `diaria`; vale-transporte vira duas linhas com/sem obra).

### Passo 6 — Runner de seed idempotente
**Arquivo:** `services/seed_palavras_chave.py`

- `seed_para_admin(admin_id)`: resolve `categoria_nome → categoria_fluxo_caixa_id`
  do tenant; cria `PalavraChaveCategoria(origem='sistema')` faltantes; não duplica
  (chave de unicidade: `admin_id + categoria_id + palavras + campo_alvo + prioridade`).
- CLI fina (`scripts/seed_palavras_chave_cli.py`) chamando por `admin_id`.

### Passo 7 — Teste de regressão contra o motor antigo
**Arquivo novo:** `tests/test_regressao_classificacao.py`

- Para cada bloco de `REGRAS_SISTEMA`, sintetizar a entrada e assertar que
  `classificar_por_cadastro` devolve a MESMA categoria que
  `_classificar_categoria_nomeada` para um conjunto de descrições reais extraídas do
  Excel `1. FLUXO DE CAIXA_Veks Engenharia.xlsx`.
- Comparar distribuição agregada de categorias (novo vs antigo) com tolerância zero
  para casos classificados (a redefinição auto/manual é validada à parte).

---

## FASE D — Ligar no fluxo de importação

### Passo 8 — `processar()` consome o cadastro
**Arquivo:** `services/importacao_excel.py` → `ImportacaoFluxoCaixa.processar` (~L1690)

- Carregar `regras = PalavraChaveCategoria.query.filter_by(admin_id, ativo=True)` uma
  vez (junto com funcionários/fornecedores/obras).
- Substituir as chamadas a `_classificar_categoria_nomeada` por
  `classificar_por_cadastro(...)`.
- Derivar `tipo_categoria` macro via `derivar_macro(categoria_nome)`.
- **Redefinir auto vs manual** (§3): manual quando a categoria resolvida for o
  fallback genérico (`Outras Saídas` / `Outros Recebimentos`) ou `None`.
- Manter `_categoria_por_plano` / `_classificar_keywords` apenas se o teste de
  regressão exigir; senão remover na Fase G.

---

## FASE E — Motor de sugestões

### Passo 9 — Função de sugestões
**Arquivo:** `services/classificador_cadastro.py`

- `gerar_sugestoes(lancamentos_nao_classificados, regras_existentes)`: tokeniza
  fornecedor + descrição (n-gramas 1–3), descarta termos já cobertos, agrega por
  termo (`ocorrencias`, `soma_valor`, `exemplo`), ordena por `ocorrencias × soma_valor`.

### Passo 10 — Persistência das sugestões no preview
**Arquivo:** `services/importacao_excel.py` (fim de `processar`) + retorno do dict

- Após classificar, rodar `gerar_sugestoes` sobre os não classificados e gravar em
  `PalavraChaveSugestao` (substituindo as do tenant). Incluir `sugestoes` no dict de
  retorno.

### Passo 11 — Testes das sugestões
**Arquivo:** `tests/test_classificador_cadastro.py`

- Agregação correta; exclusão de termos já cobertos; ordenação por frequência×valor.

---

## FASE F — UI (CRUD + sugestões)

### Passo 12 — Rotas CRUD
**Arquivo:** `views/catalogos_views.py`

- `GET /catalogos/palavras-chave` (lista + filtros + sugestões),
  `POST .../criar`, `POST .../<id>/editar`, `POST .../<id>/toggle`,
  `POST .../<id>/excluir`, `POST .../sugestoes/cadastrar` (lote).
- Validação de tenant em todas (padrão do arquivo).

### Passo 13 — Template da página
**Arquivos:** `templates/catalogos/palavras_chave.html` (+ parcial de form/modal)

- Portar o mockup `static/mockups/palavras_chave_mockup.html` para Jinja, ligado a
  dados reais. Filtros por busca/categoria/origem; paginação.

### Passo 14 — Detecção de conflito no salvar
**Arquivo:** `views/catalogos_views.py` (criar/editar)

- Antes de gravar: se existir regra com mesma palavra + mesma prioridade + mesma
  especificidade e categoria diferente → `flash` de aviso e não grava (ou pede
  confirmação).

### Passo 15 — Cadastrar sugestões em lote + re-classificar preview
**Arquivos:** `views/catalogos_views.py` + `importacao_views.py`

- `sugestoes/cadastrar` cria `PalavraChaveCategoria(origem='usuario',
  campo_alvo='fornecedor', prioridade=40)` para os termos marcados; marca as
  `PalavraChaveSugestao` como `dismissed`.
- No preview de importação: botão que re-roda a classificação do payload em memória
  e atualiza as seções auto/manual.

### Passo 16 — Painel de sugestões no preview + entrada no menu
**Arquivos:** `templates/importacao/preview_fluxo.html`, menu de catálogos

- Incluir o painel de sugestões no preview (dados já disponíveis).
- Link "Palavras-Chave" na landing `/catalogos/` e no menu lateral.

---

## FASE G — Limpeza

### Passo 17 — Aposentar o hardcode
**Arquivo:** `services/importacao_excel.py`

- Após regressão verde em produção: remover `_classificar_categoria_nomeada`,
  `_PLANO_PARA_CATEGORIA`, `_KEYWORDS_CATEGORIA`, `_KEYWORDS_REEMBOLSO_CONTEXTO`,
  `_categoria_por_plano`, `_classificar_keywords` (manter só o que o motor novo usar).
- Manter cópia do oráculo apenas no teste de regressão (ou removê-lo também).

### Passo 18 — Remover o mockup temporário
**Arquivos:** `templates/importacao/index.html`, `static/mockups/`, `docs/mockups/`

- Remover o botão "Prévia: Palavras-Chave" e os arquivos de mockup (a página real os
  substitui).

---

## Ordem de verificação

1. Fases A–C entregam o motor + seed + **regressão verde** (nada muda na prática
   ainda — segurança máxima).
2. Fase D liga no import; rodar uma importação real e conferir contagens.
3. Fases E–F entregam a experiência (sugestões + tela).
4. Fase G limpa.
