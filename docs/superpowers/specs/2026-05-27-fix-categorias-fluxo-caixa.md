# Fix #6 — Categorias FluxoCaixa: Modal, Legacy Select, Export/Upsert

**Data:** 2026-05-27  
**Status:** Aprovado  
**Área:** Financeiro / Catalogos / Importação

---

## Contexto

Três problemas independentes no subsistema de categorias de fluxo de caixa:

1. **Modal HTML mal posicionado**: `<div class="modal">` renderizado dentro de `<tbody>` na tabela de categorias. Causa flicker visual ao deletar linhas porque o DOM fica inválido (modal é filho de tbody → reposicionado pelo browser).

2. **Select de categoria duplicado**: A tela de preview de importação (`preview_fluxo.html`) e o form de novo fluxo de caixa (`fluxo_caixa.html`) exibiam tanto o select dinâmico (categorias do banco, `cfc_<id>`) quanto um select legado hardcoded com `CATEGORIAS_GRUPOS`. Isso causa duplicação visual e confusão quando o tenant tem suas próprias categorias cadastradas.

3. **Export/Import com comportamento incorreto**: O botão "Exportar Modelo" exportava as categorias atuais do tenant, mas devia ser um template em branco. Não havia botão para exportar as categorias atuais. O import ignorava duplicatas (skip), então re-importar um arquivo modificado não atualizava nada — forçando o usuário a deletar e recriar.

---

## Escopo

### Fora do escopo
- Deletar categorias via import (nunca deleta — preserva dados históricos)
- Alterar o modelo de dados `CategoriaFluxoCaixa`
- Alterar a tela de preview de importação (já usa apenas `cfc_<id>`, não é afetada pelo select legado)
- Fix #3 (Transferências sumidas) — spec separada

---

## Parte 1 — Modal HTML fora do tbody

**Arquivo**: `templates/catalogos/categorias_fluxo_caixa.html`

**Problema**: Os modais de confirmação de deleção estão dentro do loop `{% for categoria in categorias %}` que renderiza as `<tr>` da tabela. O browser move elementos inválidos dentro de `<tbody>` para fora, causando refluxo e flicker.

**Solução**: Dois loops separados:
1. Loop `{% for categoria in categorias %}` → renderiza apenas as `<tr>` dentro de `<tbody>`
2. Segundo loop `{% for categoria in categorias %}` → renderiza apenas os `<div class="modal">`, colocado **depois do `</table>`**, no mesmo nível do container principal

**Comportamento esperado**: Sem flicker ao confirmar/cancelar deleção.

---

## Parte 2 — Remover select legado de categoria

**Arquivos afetados**:
- `templates/financeiro/fluxo_caixa.html`
- `financeiro_views.py` → `novo_fluxo_caixa()`

### Template (`fluxo_caixa.html`)

Remover o `<select name="categoria">` com as opções hardcoded de `CATEGORIAS_GRUPOS`. O select dinâmico de `categoria_fluxo_caixa_id` (que usa as categorias do banco) é o único que deve existir.

### View (`novo_fluxo_caixa()`)

Após receber `categoria_fluxo_caixa_id` do form, derivar `categoria` automaticamente:

```python
cfc = CategoriaFluxoCaixa.query.get(categoria_fluxo_caixa_id)
if cfc:
    categoria = 'receita' if cfc.tipo == 'ENTRADA' else 'custo_obra'
else:
    categoria = 'custo_obra'  # fallback seguro
```

Remover imports de `CATEGORIA_LABELS` e `CATEGORIAS_VALIDAS` se não usados em outro lugar desta view.

**Por que manter `categoria` no model**: O campo `FluxoCaixa.categoria` (String) ainda é usado em queries de relatórios e no fluxo legado. A derivação automática garante consistência sem quebrar código existente.

---

## Parte 3 — Export duplo + Upsert no import

### 3a — Dois botões de export

**Arquivo**: `templates/catalogos/categorias_fluxo_caixa.html`

Manter o botão existente "Exportar Modelo" com comportamento alterado: exporta planilha **em branco** (apenas cabeçalhos + exemplos comentados ou linhas de exemplo sem dados reais).

Adicionar novo botão "Exportar Categorias Atuais" que chama nova rota:
```
GET /catalogos/categorias-fluxo-caixa/exportar-atuais
```

Exporta todas as categorias ativas do tenant atual em formato Excel, com as colunas:
- `nome` — nome da categoria
- `tipo` — ENTRADA ou SAIDA
- `grupo_financeiro` — nome do grupo (string, não FK)
- `descricao` — texto livre
- `ativo` — TRUE/FALSE

### 3b — Comportamento upsert no import

**Arquivo**: `views` de importação de categorias (rota existente que processa o Excel)

**Lógica atual**: Ao importar, verifica se já existe pelo nome → se sim, **ignora** (skip).

**Nova lógica**:
```
Para cada linha do Excel:
  chave = (nome.strip().lower(), tipo.upper())
  existente = query por chave
  
  se existente:
    UPDATE grupo_financeiro, descricao, ativo
    (não altera nome, tipo, empresa_id, created_at)
  
  se não existente:
    INSERT novo registro
```

**Nunca deleta** categorias. Categorias existentes no banco que não estão no Excel permanecem intactas.

**Relatório pós-import**: Flash com contagem:
- `X categorias atualizadas, Y novas inseridas`

---

## Arquivos a modificar

| Arquivo | Operação |
|---------|----------|
| `templates/catalogos/categorias_fluxo_caixa.html` | Mover modais para fora do tbody; adicionar botão "Exportar Categorias Atuais" |
| `templates/financeiro/fluxo_caixa.html` | Remover `<select name="categoria">` legado |
| `financeiro_views.py` | Derivar `categoria` de `CategoriaFluxoCaixa.tipo` em `novo_fluxo_caixa()` |
| `catalogo_views.py` (ou equivalente) | Adicionar rota `exportar_categorias_atuais()`; alterar lógica de import para upsert |
| `templates/catalogos/categorias_fluxo_caixa_form.html` | Nenhuma alteração prevista |

---

## Invariantes / Contratos

- **Nunca deletar** categorias via import
- Upsert key: `(nome case-insensitive, tipo)` — case-sensitive nunca, tipo sempre uppercase antes de comparar
- `categoria` em `FluxoCaixa` continua existindo, mas é derivada automaticamente (não entrada manual)
- `categoria_fluxo_caixa_id` continua sendo o campo canônico
- Export "Exportar Modelo" → planilha em branco (zero linhas de dados, apenas cabeçalho)
- Export "Exportar Categorias Atuais" → todas as categorias ativas do tenant, ordenadas por tipo + nome

---

## Ordem de implementação

1. Parte 1 (modal fix) — isolada, zero risco, valida visualmente imediato
2. Parte 2 (remove legacy select) — depende de confirmar que `categoria_fluxo_caixa_id` está sempre presente no form
3. Parte 3a (botão export) — nova rota, sem side effects
4. Parte 3b (upsert import) — maior risco, implementar por último com teste manual

---

## Critérios de aceitação

- [ ] Deletar categoria na tabela não causa flicker
- [ ] Form de fluxo de caixa exibe apenas o select dinâmico (categorias do banco)
- [ ] "Exportar Modelo" gera Excel apenas com cabeçalho (sem dados do tenant)
- [ ] "Exportar Categorias Atuais" gera Excel com todas as categorias ativas do tenant
- [ ] Re-importar Excel modificado atualiza categorias existentes
- [ ] Re-importar Excel não deleta categorias ausentes do arquivo
- [ ] Flash pós-import exibe contagem de atualizadas + inseridas
