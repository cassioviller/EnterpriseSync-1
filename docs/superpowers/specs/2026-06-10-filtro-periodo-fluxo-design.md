# Design — Filtro de Período + Visibilidade Pós-Importação (Fluxo de Caixa)

**Data:** 2026-06-10
**Autor:** Cássio + Claude
**Status:** Aprovado (design)
**Relacionados:** `financeiro_views.py`, `financeiro_service.py`,
`services/importacao_excel.py`, `templates/financeiro/{contas_pagar,contas_receber,fluxo_caixa}.html`,
`templates/importacao/resultado_fluxo.html`

## 1. Problema

Dois sintomas relatados pelo usuário, com **raiz comum**:

1. **"Depois de importado e lançado como pago, não aparece no Fluxo de Caixa."**
   A importação cria corretamente os registros `FluxoCaixa` (modo normal:
   `referencia_tabela='gestao_custo_pai'`; modo "Apenas Pagamento":
   `referencia_tabela=None`). Ambos são lidos por
   `FinanceiroService.calcular_fluxo_caixa`. **Porém** as queries filtram por
   `data_movimento BETWEEN data_inicio AND data_fim`, e a tela abre por padrão em
   **hoje → hoje+30**. A planilha real da Veks é importada para **01/01/2026 a
   05/06/2026** (runner `_import_save.py`), tudo **antes de hoje (10/06/2026)** →
   100% cai fora da janela padrão → invisível. Não é dado perdido; é janela.

2. **Falta filtro de período** em Contas a Pagar e Contas a Receber (têm status/obra,
   mas não intervalo de datas). Fluxo de Caixa já tem `data_inicio`/`data_fim`.

## 2. Decisões (confirmadas com o usuário)

- **Campo de corte** do filtro em Contas a Pagar/Receber: **`data_vencimento`**.
- **Default do Fluxo de Caixa** sem filtro: **mês corrente inteiro** (1º dia →
  último dia do mês atual).
- **Formato de data na UI:** `<input type="date">` nativo (mostra DD/MM/AAAA em
  navegador pt-BR, envia YYYY-MM-DD). Sem dependências novas.

## 3. Mudanças

### 3.1 Filtro de período — Contas a Pagar e Contas a Receber
- `FinanceiroService.listar_contas_pagar` e `listar_contas_receber`: novos params
  `data_inicio: date = None`, `data_fim: date = None`. Quando presentes, adicionam
  `ContaX.data_vencimento >= data_inicio` / `<= data_fim`. Ambos opcionais; vazio =
  sem corte.
- `financeiro_views.listar_contas_pagar` / `listar_contas_receber`: ler
  `request.args` (`data_inicio`/`data_fim`, parse `%Y-%m-%d`, tolerante a vazio),
  repassar ao service, e devolver os valores ao template (para repopular o form).
- Templates `contas_pagar.html` / `contas_receber.html`: dois `<input type="date">`
  no `<form method="get">` de filtros já existente, repopulados com o valor atual.

### 3.2 Default do Fluxo de Caixa = mês corrente
- `financeiro_views.fluxo_caixa`: trocar default `data_inicio = hoje`,
  `data_fim = hoje+30` por **`data_inicio = 1º dia do mês`**, **`data_fim = último
  dia do mês`** (via `calendar.monthrange`). Query params continuam sobrescrevendo.

### 3.3 Visibilidade pós-importação
- `resultado_fluxo.html`: botão de destaque **"Ver no Fluxo de Caixa"** apontando
  para `financeiro.fluxo_caixa` com `data_inicio`/`data_fim` = **menor e maior
  `data_movimento` do batch importado**.
- `importacao_views` (handler do confirmar): calcular `data_min`/`data_max` do batch
  (a partir do resultado da importação ou query no `import_batch_id`) e passar ao
  template `resultado_fluxo.html`.

## 4. Verificação (nesta sessão)
1. Rodar `_import_save.py` (importa a planilha real → cria FluxoCaixa do batch).
2. Abrir Fluxo de Caixa no período do batch (01/01/2026–05/06/2026) e confirmar que
   os lançamentos pagos aparecem e os totais batem.
3. Conferir que o default (mês corrente) e o botão pós-import funcionam.

## 5. Fora de escopo
- Refino das categorias/regras de classificação (continua sendo trabalhado à parte).
- Mudança de formato de armazenamento de datas; máscara de texto custom.
