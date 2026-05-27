# Plano — Fix #6 Categorias FluxoCaixa

**Spec:** `docs/superpowers/specs/2026-05-27-fix-categorias-fluxo-caixa.md`  
**Data:** 2026-05-27

---

## Passo 1 — Modal fora do tbody
**Arquivo:** `templates/catalogos/categorias_fluxo_caixa.html`

- Remover `<div class="modal">` de dentro do loop `{% for cat in categorias %}` (linhas 142–163)
- Fechar `</tbody></table>` logo após `{% endfor %}` da primeira iteração
- Adicionar segundo `{% for cat in categorias %}` loop logo após `</table>`, só com os modais

---

## Passo 2 — Remove select legado no template
**Arquivo:** `templates/financeiro/fluxo_caixa.html`

- Remover bloco `<div class="col-md-4">` com `<select name="categoria">` (linhas ~346–356)
- Remover o `{% if categorias_fc %}` guard do select dinâmico — tornar sempre visível (mas com mensagem se vazio)
- Manter `<select name="categoria_fluxo_caixa_id">` com opção "— Nenhuma —"

---

## Passo 3 — Remove import legado na view de listagem
**Arquivo:** `financeiro_views.py` → função `fluxo_caixa()` (~L695–L700, L714)

- Remover import de `CATEGORIAS_GRUPOS` e `CATEGORIA_LABELS`
- Remover variável `categorias_grupos`
- Remover `categorias_grupos=categorias_grupos` do `render_template()`

---

## Passo 4 — Derivar `categoria` automaticamente em `novo_fluxo_caixa()`
**Arquivo:** `financeiro_views.py` → função `novo_fluxo_caixa()` (~L727–L739)

- Remover import de `CATEGORIA_LABELS` e variável `CATEGORIAS_VALIDAS`
- Remover `categoria = request.form.get('categoria', 'OUTROS')` e validação
- Após resolver `categoria_fc_id`, derivar `categoria`:
  ```python
  if categoria_fc_id:
      cfc = CategoriaFluxoCaixa.query.filter_by(id=categoria_fc_id, admin_id=admin_id).first()
      if cfc:
          categoria_fc_id = cfc.id
          categoria = 'receita' if cfc.tipo == 'ENTRADA' else 'custo_obra'
      else:
          categoria_fc_id = None
          categoria = 'custo_obra'
  else:
      categoria = 'receita' if tipo_movimento == 'ENTRADA' else 'custo_obra'
  ```
  (remover o bloco separado de validação de cfc que existia antes)

---

## Passo 5 — Rota exportar categorias atuais
**Arquivo:** `views/catalogos_views.py`

- Adicionar rota `GET /catalogos/categorias-fluxo-caixa/exportar-atuais`
- Exporta todas as categorias ativas do tenant (colunas: Nome, Tipo, Grupo Financeiro, Descrição, Ativo)
- Download name: `categorias_fluxo_caixa_<admin_id>.xlsx`

---

## Passo 6 — Alterar "Exportar Modelo" para template em branco
**Arquivo:** `views/catalogos_views.py` → `categorias_fluxo_caixa_exportar_modelo()`

- Remover as duas linhas `ws.append([...])` com dados de exemplo
- Manter apenas cabeçalho + linha de nota

---

## Passo 7 — Upsert no import
**Arquivo:** `views/catalogos_views.py` → `categorias_fluxo_caixa_importar()`

- Adicionar variável `atualizadas = 0`
- Mudar bloco `if existe: ignoradas += 1; continue` para:
  ```python
  if existe:
      existe.grupo_financeiro = grupo_nome or existe.grupo_financeiro
      existe.grupo_financeiro_id = grupo_id or existe.grupo_financeiro_id
      existe.descricao = desc or existe.descricao
      atualizadas += 1
      continue
  ```
- Flash final: `f'{criadas} nova(s) inserida(s), {atualizadas} atualizada(s).'`

---

## Passo 8 — Atualizar texto explicativo no template
**Arquivo:** `templates/catalogos/categorias_fluxo_caixa.html`

- Alterar `<p class="text-muted small mb-3">` dentro do collapse de importação:
  "Categorias com mesmo nome e tipo **serão atualizadas** (não duplicadas). Novas serão inseridas. Nenhuma será excluída."
- Adicionar botão "Exportar Categorias Atuais" no header, ao lado de "Exportar Modelo"

---

## Ordem de commit

1. Passos 1 (modal) — commit isolado
2. Passos 2+3+4 (remove legacy select) — commit único
3. Passos 5+6+7+8 (export+upsert) — commit único
