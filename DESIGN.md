---
name: SIGE
description: Bootstrap 5 funcional com overrides de construção civil — azul primário institucional, tabelas densas, formulários pt-BR.

colors:
  primary: "#0d6efd"           # Bootstrap primary — azul institucional
  primary-dark: "#0a58ca"      # hover/active
  secondary: "#6c757d"         # muted / labels secundários
  success: "#198754"           # aprovado, concluído, positivo
  warning: "#ffc107"           # atenção, pendente, rascunho
  danger: "#dc3545"            # erro, excluído, negativo
  info: "#0dcaf0"              # informativo
  light: "#f8f9fa"             # fundo de cards, table-striped
  dark: "#212529"              # texto principal
  white: "#ffffff"
  border: "#dee2e6"            # Bootstrap border padrão
  muted-text: "#6c757d"        # .text-muted

typography:
  base:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"           # 16px
    fontWeight: 400
    lineHeight: 1.5
  small:
    fontSize: "0.875rem"       # form-control-sm, table cells
  label:
    fontSize: "0.875rem"
    fontWeight: 500
  heading:
    fontWeight: 600

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  "2xl": "48px"

rounded:
  default: "0.375rem"          # Bootstrap padrão (6px)
  sm: "0.25rem"
  lg: "0.5rem"
  pill: "50rem"

components:
  btn-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.white}"
    rounded: "{rounded.default}"
    padding: "6px 12px"
  btn-sm:
    padding: "4px 8px"
    fontSize: "0.875rem"
  table:
    fontSize: "0.875rem"
    lineHeight: 1.4
  card:
    backgroundColor: "{colors.white}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.default}"
    shadow: "0 1px 3px rgba(0,0,0,0.075)"
  form-control:
    border: "1px solid {colors.border}"
    rounded: "{rounded.default}"
    padding: "6px 12px"
    fontSize: "1rem"
  form-control-sm:
    padding: "4px 8px"
    fontSize: "0.875rem"
  badge-status:
    rascunho: "bg-secondary"
    pendente: "bg-warning text-dark"
    aprovado: "bg-success"
    cancelado: "bg-danger"
    concluido: "bg-primary"
---

# Design System: SIGE

## 1. Visão Geral

Bootstrap 5 com sobrescrita mínima. O sistema é uma ferramenta de trabalho — a hierarquia visual serve à eficiência, não à estética.

**Padrões principais:**
- Tabelas densas com `table-sm` + `table-hover` para listas de itens e composições
- Cards `shadow-sm` com cabeçalho `.card-header.bg-light` para seções
- Formulários em grid `row g-3` com labels claros e help text `.form-text.text-muted`
- Botões de ação primária no final dos formulários; ações destrutivas em `btn-outline-danger`
- Badges de status com cores semânticas (ver `badge-status` nos componentes)

## 2. Padrões de Formulário

**Inputs numéricos pt-BR:**
- Sempre `inputmode="decimal"` + `type="text"` (nunca `type="number"` para valores monetários)
- Placeholder `Ex.: 1.234,56` para indicar o formato esperado
- Label + input + `.form-text.text-muted` com explicação do campo

**Campos de composição de serviço (tabela interna):**
- `form-control-sm` em todos os inputs da tabela
- Colunas de display (`js-subtotal-unit`, `js-qtd-comercial`) em `.text-muted` quando informativo, `.fw-bold.text-warning` quando há arredondamento ativo
- Botão de remover linha: `btn-sm btn-link text-danger`

## 3. Hierarquia de Tabelas

**Tabela de composição do orçamento:**
```
Tipo | Insumo | Unidade | Coef | Preço embalagem | Custo/un | Consumo | Fator | Un.compra | Qtd.compra | Subtotal compra | Ação
```
- Colunas de leitura: `.text-muted` ou `.text-dark`
- Colunas de entrada: `form-control-sm`
- Células de total: `<strong>` + `fmtBRL()`

## 4. Status e Feedback

**Orçamento:** `rascunho` → `fechado` → `convertido`
**Proposta:** `rascunho` → `enviada` → `aprovada` / `reprovada`
**Item do cronograma:** `nao_iniciado` → `em_andamento` → `concluido`

Sempre usar badge semântico + texto (nunca só cor).

## 5. Do's e Don'ts para este projeto

### Do:
- Use `table-sm` + `table-hover` para listas de insumos/serviços/itens
- Use `text-muted small` para metadados e notas de campo
- Use `fw-bold text-warning` para indicar arredondamento forçado (fator > 1 ou não fracionável)
- Use tooltips `data-bs-toggle="tooltip"` em abreviações técnicas (coef., BDI, fator comercial)
- Mostre separação clara entre **custo técnico** e **custo real de compra**

### Don't:
- Não use `border-left` colorido em cards de status — Bootstrap já tem badge para isso
- Não use dark mode — o sistema é light-only
- Não omita o `form-text` explicativo em campos calculados ou com regra especial
- Não misture R$ com notação americana (1.234.56) — sempre pt-BR
- Não use gradientes em botões de ação principal
