# Plano — Cadastro de Palavras-Chave de Classificação (Fluxo de Caixa)

**Spec:** `docs/superpowers/specs/2026-06-09-cadastro-palavras-chave-design.md`
**Data:** 2026-06-09
**Branch:** `feat/cadastro-palavras-chave`

Princípio: cada passo é um commit pequeno e verificável. A fatia vertical (motor +
seed + teste de regressão) vem cedo, antes da UI, pra garantir que a migração não
altera classificações.

---

## FASE A — Fundação (modelos + tabelas)

### Passo 1 — Modelos `PalavraChaveCategoria`, `PalavraChaveSugestao`, `CorrecaoClassificacao`
**Arquivo:** `models.py` (logo após `class CategoriaFluxoCaixa`, ~L6863)

- `PalavraChaveCategoria` com campos da §4 do spec: `id`, `admin_id` (FK usuario),
  `categoria_fluxo_caixa_id` (FK), `palavras` (Text), `campo_alvo` (String, default
  `'qualquer'`), `excecoes` (Text, null), `condicao_obra` (String, default
  `'indiferente'`), `prioridade` (Integer, default 50), `tipo` (String), `origem`
  (String, default `'usuario'`), `ativo` (Boolean, default True), `created_at`,
  `updated_at`.
- `PalavraChaveSugestao`: `id`, `admin_id`, `termo`, `ocorrencias`, `soma_valor`
  (Numeric), `exemplo`, `tipo`, `dismissed` (Boolean default False), `created_at`.
- `CorrecaoClassificacao` (Correção + Memória Exata): `id`, `admin_id`, `texto_norm`
  (String), `categoria_fluxo_caixa_id` (FK), `termo_origem` (String, null), `tipo`
  (String), `created_at`. Índice **único** `(admin_id, texto_norm)`.
- `__tablename__` = `palavra_chave_categoria` / `palavra_chave_sugestao` /
  `correcao_classificacao`.

### Passo 2 — Migration das três tabelas
**Arquivo:** `migrations.py`

- Três blocos `CREATE TABLE IF NOT EXISTS` (padrão do arquivo): índice
  `(admin_id, ativo, tipo, prioridade)` em `palavra_chave_categoria`; índice único
  `(admin_id, texto_norm)` em `correcao_classificacao`.
- Registrar na sequência de execução de migrations como os demais.

---

## FASE B — Motor de matching (puro, testável, ainda não ligado)

### Passo 3 — Classificador profundo (devolve Veredito)
**Arquivo novo:** `services/classificador_cadastro.py`

- Interface `classificar(lancamento, contexto) -> Veredito`, onde `Veredito` tem
  `categoria_id`, `categoria_nome`, `origem_decisao` (`regra|memoria_exata|fallback`),
  `eh_pendente`. **A ordem de resolução (Regra → Memória Exata → Pendente), o desempate
  por prioridade e a decisão auto/Pendente vivem DENTRO do módulo** — `processar()` só
  consome o veredito (decisão da review técnica, §5 do spec).
- Filtro de candidatos + menor prioridade + desempates (especificidade → origem usuário
  → campo específico).
- Reaproveitar `_normalizar` de `importacao_excel.py` (mover para `utils` comum ou
  importar).
- `MACRO_POR_CATEGORIA: dict[str,str]` — mapa categoria nomeada → `tipo_categoria`
  macro. Função `derivar_macro(categoria_nome)`.

### Passo 3b — Leitor de Planilha (separar Parse de Classify)
**Arquivos:** `services/importacao_excel.py` (extrair) ou novo `services/leitor_fluxo.py`

- Extrair a leitura do Excel para `ler(workbook, periodo) -> list[Lançamento]` — só
  openpyxl, **sem DB e sem classificação**. `processar()` passa a ser cola: carrega
  contexto + chama Leitor + Classificador (§5 do spec). Parse testável com um `.xlsx`
  minúsculo, sem app context.

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

## FASE E — Fila por Termo, sugestões e aprendizado

### Passo 9 — Função de sugestões (fila por Termo)
**Arquivo:** `services/classificador_cadastro.py`

- `gerar_sugestoes(pendentes, regras_existentes)`: tokeniza fornecedor + descrição
  (n-gramas 1–3), descarta termos já cobertos, agrega por termo (`ocorrencias`,
  `soma_valor`, `exemplo`), ordena por `ocorrencias × soma_valor`.

### Passo 10 — Persistência das sugestões no preview
**Arquivo:** `services/importacao_excel.py` (fim de `processar`) + retorno do dict

- Após classificar, rodar `gerar_sugestoes` sobre os Pendentes e gravar em
  `PalavraChaveSugestao` (substituindo as do tenant). Incluir `sugestoes` e os
  **lançamentos individuais por termo** no dict de retorno (para o drill-down §7.2).

### Passo 11 — Correção, Memória Exata e regra refinada
**Arquivos:** `services/classificador_cadastro.py`

- `registrar_correcao(admin_id, lancamento, categoria_id)`: grava
  `CorrecaoClassificacao` (`texto_norm`, `termo_origem`), upsert por
  `(admin_id, texto_norm)`.
- `sugerir_regra_refinada(correcao, regra_conflitante)`: deriva o token distintivo e
  monta a Sugestão `gatilho_refinado → categoria` com `prioridade` menor que a regra do
  termo (vence o conflito). **Não grava regra** — só devolve a proposta.

### Passo 12 — Testes de sugestões + aprendizado
**Arquivo:** `tests/test_classificador_cadastro.py`

- Agregação/ordenação/exclusão de termos cobertos; Memória Exata reaplica em texto
  idêntico; Correção não cria regra; regra refinada só efetiva com confirmação.

---

## FASE F — Loop ao vivo no preview (a experiência que o usuário pediu)

### Passo 13 — Estado do preview: payload-como-estado
**Arquivos:** `importacao_views.py`

- **Decisão da review técnica:** usar **payload-como-estado** — cada ação do loop ao
  vivo re-envia o payload assinado (HMAC, mecanismo já existente), o servidor
  reclassifica em memória e devolve o delta. **Sem store/cache server-side novo.**
  O payload passa a incluir os lançamentos individuais (para drill-down).
- Se o volume virar gargalo, migrar depois para `token → Lançamentos` server-side.

### Passo 14 — Endpoint: classificar Termo (cria Regra + reclassifica ao vivo)
**Arquivo:** `importacao_views.py`

- `POST /importacao/fluxo-caixa/classificar-termo`: cria
  `PalavraChaveCategoria(origem='usuario', campo_alvo='fornecedor', prioridade=40)`,
  reclassifica o payload em memória e devolve a fila + seções atualizadas.

### Passo 15 — Endpoint: corrigir linha (Correção + oferta de regra refinada)
**Arquivo:** `importacao_views.py`

- `POST /importacao/fluxo-caixa/corrigir-linha`: chama `registrar_correcao`, aplica à
  linha, devolve a Sugestão de regra refinada (`sugerir_regra_refinada`).
- `POST /importacao/fluxo-caixa/confirmar-regra-refinada`: efetiva a regra (1 clique).

### Passo 16 — UI do preview: fila por Termo + drill-down + correções
**Arquivo:** `templates/importacao/preview_fluxo.html`

- Fila agrupada por Termo (ordenada por impacto); clique expande os lançamentos;
  dropdown de categoria por termo e por linha; reclassificação ao vivo (JS).
- **Light-only** conforme `DESIGN.md`; faixa de cor semântica por bloco
  (entrada=verde, saída=azul, transferência=ciano).

## FASE F2 — Página de cadastro (CRUD das Regras)

### Passo 17 — Rotas CRUD
**Arquivo:** `views/catalogos_views.py`

- `GET /catalogos/palavras-chave` (lista + filtros + sugestões), `POST .../criar`,
  `POST .../<id>/editar`, `POST .../<id>/toggle`, `POST .../<id>/excluir`,
  `POST .../sugestoes/cadastrar` (lote). Validação de tenant em todas.
- **Detecção de conflito** no salvar (mesma palavra + mesma prioridade +
  especificidade, categoria diferente → avisa, não grava silenciosamente).

### Passo 18 — Template da página + menu
**Arquivos:** `templates/catalogos/palavras_chave.html` (+ parcial), menu de catálogos

- Portar o mockup para Jinja, **light-only** (corrigir o dark do mockup), dados reais,
  filtros (busca/categoria/origem), paginação. Não expor nomes de tabela/modelo na UI.
- Link "Palavras-Chave" na landing `/catalogos/` e no menu lateral.

---

## FASE G — Limpeza

### Passo 19 — Aposentar o hardcode
**Arquivo:** `services/importacao_excel.py`

- Após regressão verde em produção: remover `_classificar_categoria_nomeada`,
  `_PLANO_PARA_CATEGORIA`, `_KEYWORDS_CATEGORIA`, `_KEYWORDS_REEMBOLSO_CONTEXTO`,
  `_categoria_por_plano`, `_classificar_keywords` (manter só o que o motor novo usar).
- Manter cópia do oráculo apenas no teste de regressão (ou removê-lo também).

### Passo 20 — Remover o mockup temporário
**Arquivos:** `templates/importacao/index.html`, `static/mockups/`, `docs/mockups/`

- Remover o botão "Prévia: Palavras-Chave" e os arquivos de mockup (a página real os
  substitui).

---

## Ordem de verificação

1. Fases A–C entregam o motor + seed + **regressão verde** (nada muda na prática
   ainda — segurança máxima).
2. Fase D liga no import; rodar uma importação real e conferir contagens.
3. Fase E entrega o cérebro (sugestões + aprendizado); Fases F/F2 entregam a
   experiência (loop ao vivo no preview + página de cadastro).
4. Fase G limpa.
