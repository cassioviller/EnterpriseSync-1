# Audit Report — SIGE (Orçamentos + Catálogo)

**Data:** 2026-05-26
**Comando:** `/impeccable audit`
**Escopo:** `templates/orcamentos/`, `templates/catalogo/`, `templates/base_completo.html`

---

## Audit Health Score

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2 | 36 labels sem `for=` na tabela de composição; `<th>` sem `scope`; modal busca insumo sem `aria-label` |
| 2 | Performance | 3 | CDN correto; sem thrash detectado; Chart.js carregado globalmente em páginas sem gráficos |
| 3 | Responsive Design | 3 | Tabela de composição em `table-responsive` ✓; botões de ação na tabela < 44px em mobile |
| 4 | Theming | 2 | `style="border-left:5px solid #198754"` hardcoded; padrão `border-left-primary/success` em dashboards sem variável CSS |
| 5 | Anti-Patterns | 2 | 1 violação crítica de ban absoluto (side-stripe), 20+ instâncias em outros módulos (contabilidade, CRM, alimentação) |
| **Total** | | **12/20** | **Acceptable (significant work needed)** |

---

## Anti-Patterns Verdict

**Não parece gerado por IA — passa no test de familiaridade.** O vocabulário de construção civil é autêntico, a hierarquia da tabela de composição faz sentido técnico, sem gradientes decorativos em botões ou cards hero-metric no core do orçamento.

**Tells presentes (2):**

1. `border-left:5px solid #198754` em `editar.html:164` — violação de ban absoluto, exatamente a pattern listada.
2. `border-left-primary/success/warning` em dashboards de contabilidade, CRM e alimentação — 20+ instâncias. Fora do escopo principal do orçamento, mas indicam pattern sistêmico adquirido de um template SB Admin 2-era Bootstrap.

---

## Executive Summary

- **Audit Health Score: 12/20 (Acceptable)**
- Issues: 1 P1, 4 P2, 3 P3
- Top issues: side-stripe ban violation, labels sem `for=`, `<th>` sem `scope`, Chart.js global desnecessário

---

## Detailed Findings by Severity

### [P1] Side-stripe border — ban absoluto violado

- **Location:** `templates/orcamentos/editar.html:164`
- **Category:** Anti-Pattern / Theming
- **Impact:** Viola ban explícito no DESIGN.md e impeccable; sinaliza que o padrão está sendo criado com hardcode em vez de Bootstrap utilities
- **Code:** `style="border-left:5px solid #198754;"`
- **Recommendation:** Substituir pelo alert nativo — `class="alert alert-success"` já tem borda semântica. Se quiser ênfase visual, usar `border border-success border-2` ou background tint `bg-success bg-opacity-10`.
- **Suggested command:** `/impeccable polish editar.html`

---

### [P2] Tabela de composição: `<th>` sem `scope="col"`

- **Location:** `templates/orcamentos/editar.html:613–645`
- **Category:** Accessibility — WCAG 1.3.1
- **Impact:** Screen readers não associam cabeçalho à coluna corretamente em tabelas complexas com 11 colunas
- **Recommendation:** Adicionar `scope="col"` em todos os `<th>` do thead

---

### [P2] 36 `<label>` sem `for=` na tabela de composição

- **Location:** `templates/orcamentos/editar.html` — inputs `comp_coeficiente`, `comp_preco_unitario`, `comp_nome`, etc.
- **Category:** Accessibility — WCAG 1.3.1, 4.1.2
- **Impact:** Inputs de tabela não têm label associado. Tab-navigation com leitor de tela não anuncia o campo. Usuários que navegam por Tab perdem contexto.
- **Recommendation:** Adicionar `aria-label="Coeficiente"`, `aria-label="Preço embalagem"`, etc. nos inputs de cada `<td>` da tabela. Alternativa: `title=` (já presente em alguns `<th>` — replicar nos inputs).

---

### [P2] Modal `#insumoPickerModal` sem `aria-labelledby`

- **Location:** `templates/orcamentos/editar.html:1312`
- **Category:** Accessibility — WCAG 4.1.2
- **Impact:** Modal de busca de insumo não tem título acessível. `aria-hidden="true"` está correto, mas falta `aria-labelledby`.
- **Recommendation:** Adicionar `aria-labelledby="insumoPickerLabel"` no modal e `id="insumoPickerLabel"` no `<h5>` interno.

---

### [P2] Chart.js carregado globalmente

- **Location:** `templates/base_completo.html:27`
- **Category:** Performance
- **Impact:** ~200KB JS carregado em toda página, incluindo `editar.html` que não usa gráficos
- **Recommendation:** Mover `chart.js` para bloco `{% block extra_scripts %}` e só incluir nas pages que precisam (dashboard).

---

### [P3] Botões de remoção de linha muito pequenos em mobile

- **Location:** `templates/orcamentos/editar.html:700` — `btn btn-sm btn-link`
- **Category:** Responsive
- **Impact:** Área clicável < 44×44px em viewport mobile. Uso primário é desktop, risco baixo mas real.
- **Recommendation:** Adicionar `p-2` ao botão de remoção de linha.

---

### [P3] `border-left-primary` em 20+ cards de dashboard (sistêmico)

- **Location:** `templates/contabilidade/`, `templates/crm/`, `templates/alimentacao/` — múltiplos arquivos
- **Category:** Anti-Pattern (fora do escopo principal do orçamento)
- **Impact:** Pattern de SB Admin 2 sem suporte Bootstrap 5 nativo; exige CSS customizado; inconsistente com DESIGN.md
- **Recommendation:** Substituir gradualmente por `border-top border-primary border-3` (Bootstrap 5) ou card com badge de cabeçalho.

---

### [P3] `<label>` em inputs de dimensão sem `for=`

- **Location:** `templates/orcamentos/editar.html:344–382` (add-dim-row)
- **Category:** Accessibility
- **Impact:** Labels da seção de dimensões (Largura, Comprimento, etc.) não conectados programaticamente aos inputs
- **Recommendation:** Adicionar `for="add-dim-largura"` etc. nos labels correspondentes.

---

## Patterns & Systemic Issues

1. **`border-left-*` como affordance de status** — padrão copiado de SB Admin 2/3 (Bootstrap 3-era). Aparece em 20+ componentes em 4 módulos distintos. O DESIGN.md proíbe explicitamente. Indica que diferentes partes do sistema foram geradas com templates pré-Bootstrap-5.

2. **Labels de tabela sem `for=`** — todos os inputs dentro de `<td>` da tabela de composição carecem de associação. Padrão comum em tabelas densas mas viola WCAG 1.3.1 sistematicamente.

---

## Positive Findings

- **`table-responsive` em todas as tabelas críticas** — composição, lista de insumos, lista de serviços, cronograma.
- **`inputmode="decimal"` + `type="text"`** em todos os campos numéricos monetários — conforme DESIGN.md, correto para pt-BR.
- **Tooltips com `data-bs-toggle="tooltip"`** nos cabeçalhos técnicos da tabela de composição (coef, fator, subtotal compra) — excelente para usuários novos.
- **`aria-labelledby` e `aria-hidden` nos modais** de proposta e novoServiço — correto.
- **Focus trap implementado** no drawer lateral (`base_completo.html:1379–1423`) — raro e valioso.
- **`comp_fracionavel` hidden inputs** posicionados corretamente antes do checkbox para garantir valor `false` quando desmarcado.
- **Nenhum gradiente decorativo em botões** no módulo de orçamento.

---

## Recommended Actions

| Prioridade | Comando | Contexto |
|---|---|---|
| P1 | `/impeccable polish templates/orcamentos/editar.html` | Remover `border-left:5px solid #198754` linha 164, substituir por alert Bootstrap padrão |
| P2 | `/impeccable harden templates/orcamentos/editar.html` | Adicionar `scope="col"` nos `<th>`, `aria-label` nos inputs de tabela, `aria-labelledby` no `#insumoPickerModal` |
| P2 | `/impeccable optimize templates/base_completo.html` | Mover Chart.js para bloco condicional |
| P3 | `/impeccable polish templates/contabilidade/ templates/crm/ templates/alimentacao/` | Substituir padrão `border-left-primary` por Bootstrap 5 utilities |
| P3 | `/impeccable adapt templates/orcamentos/editar.html` | Aumentar touch target do botão de remoção de linha |

Reexecute `/impeccable audit` após as correções para ver o score subir.
