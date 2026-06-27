# Plano de implementação — Custo/cronograma fiéis + regime de medição

> Spec: `docs/superpowers/specs/2026-06-27-custo-cronograma-fieis-regime-medicao-design.md`
> Data: 2026-06-27. Obra-piloto: Baia.

Ordem pensada para ser incremental e testável a cada fase. Rodar a suíte financeira
após cada fase:
```
python -m pytest tests/test_cronograma_fisico_financeiro.py \
  tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
```

---

## Fase 0 — Rede de segurança (antes de mexer)

**Objetivo:** travar o comportamento atual antes de refatorar.
1. Rodar a suíte e confirmar verde (baseline 61 passed).
2. Anotar os invariantes financeiros que NÃO podem mudar: `veks 800.960`,
   `fat 550.775`, `lucro_caixa_final 24.976`, `imposto 128.903`, `delta_veks ~0`,
   contrato `1.505.613,76`, `data_fim 08/10`.

**Verificação:** suíte verde; invariantes anotados nos asserts existentes.

---

## Fase 1 — `Obra.regime_medicao` (modelo + migração)

**Arquivos:** `models.py`, `migrations.py`.
1. Adicionar coluna `Obra.regime_medicao` (`String`, `'fixa' | 'percentual'`,
   `default 'fixa'`, `nullable=False`).
2. Migração idempotente no padrão do repo (checar `information_schema` antes de
   `ADD COLUMN`; ver migrações existentes em `migrations.py`).
3. **Default por obra existente:** `fixa` para todas, EXCETO obras que já possuem
   `MedicaoObra` (medição física real) → `percentual`. Implementar como passo de
   data-migration após o `ADD COLUMN`.

**Verificação:** teste novo `test_obra_regime_medicao_default` — coluna existe; obra
sem medição física = `fixa`; obra com `MedicaoObra` = `percentual`.

---

## Fase 2 — Custo de período como cidadão de primeira classe (painel)

**Arquivo:** `services/cronograma_fisico_financeiro.py` (`montar_fisico_financeiro`,
~l.218-348).

Hoje uma OSC sem tarefas vinculadas cai em `nao_faseado` (l.287-289) e vira "raiz
sintética". Mudar para tratar **custo de período** explicitamente:
1. Marcar a etapa/OSC como período quando não há `tarefas_mpp` (ou via flag de tipo
   vinda do fixture — ver Fase 5). Período **não** gera aviso "sem tarefas".
2. Período é faseado **apenas** pelas datas das linhas de custo (`fasear_custo_por_linhas`,
   já existe, l.257-264) — Veks/Fat por mês da Planilha1. Não entra `nao_faseado`.
3. No dicionário da etapa, adicionar `tipo: 'periodo' | 'entregavel'` e `pct_fisico:
   None` para período (sem avanço).

**Verificação:** teste — OSC de período com linhas mensais aparece no painel com
custo/caixa, `tipo='periodo'`, sem % físico, e **sem** o aviso "sem tarefas vinculadas".

---

## Fase 3 — Agrupar painel por etapa de custo (não por raiz da árvore)

**Arquivo:** `services/cronograma_fisico_financeiro.py` (`_etapa`, `montar_fisico_financeiro`).

1. Trocar a chave de `_etapa(raiz)` (raiz da árvore) por **identidade da etapa de
   custo** (OSC / `ItemMedicaoComercial`): cada OSC é uma etapa.
2. O previsto físico continua faseado pelas datas das tarefas vinculadas (quando há
   vínculo); o bucket passa a ser o OSC, não a raiz.
3. Auditar consumidores que assumem "raiz da árvore = etapa": `realizado_por_etapa`,
   `fluxo_caixa_divergencia`, `kpis`, `painel_financeiro` — ajustar para a chave por
   OSC.

**Verificação:** `test_painel_financeiro.py` continua verde; etapas agrupadas por custo;
nenhuma colapsa. Este passo é pré-requisito da Fase 4 (senão o outline do `.mpp`
colapsaria tudo numa etapa "OBRA").

---

## Fase 4 — Materializar cronograma fiel ao `.mpp` (independente de custo)

**Arquivo:** `services/importacao_fisico_financeiro.py`
(`_materializar_cronograma_fisico` ~l.173-212; orquestrador ~l.323-395).

1. **Passo A — árvore física (novo):** antes do loop de etapas de custo, materializar
   **todas** as tarefas de `cronograma_tarefas` como `TarefaCronograma`:
   - `tarefa_pai_id` reconstruído pelo `nivel` (pilha: pai = última tarefa de
     `nivel−1`); `data_inicio/fim`, `duracao_dias = dias`, `ordem` = ordem do array,
     `marco`, e o flag `resumo`.
   - Construir mapa `mpp_id → TarefaCronograma.id`.
   - Custo de período **não** entra aqui.
2. **Passo B — vínculo opcional:** para cada etapa entregável, criar
   `ItemMedicaoCronogramaTarefa(imc, <tarefa materializada>, peso=dias)` referenciando
   as folhas do mapa (o `tarefas_mpp` da etapa vira referência; **não** cria folha
   nova). Período: sem vínculo.
3. Remover a criação de "raiz por etapa de custo" do `_materializar_cronograma_fisico`
   antigo (a árvore agora é o outline do `.mpp`, materializada uma vez).

**Verificação:** teste — 56 `TarefaCronograma` materializadas; hierarquia do outline
(ex.: pai de FUNDAÇÃO é BAIAS); FAZENDA/limpeza/desmob presentes (R$ 0); INDIRETOS
ausente; resumos presentes como pais; vínculos das 11 entregáveis criados.

---

## Fase 5 — Reconciliar o fixture da Baia

**Arquivo:** `tests/fixtures/cronograma_fisico_financeiro_baias.json`.

1. `cronograma_tarefas`: confirmar que as 56 tarefas carregam `nivel`, `resumo`,
   `marco`, `dias`, datas (já carregam — validar).
2. **INDIRETOS → custo de período:**
   - `tipo: 'periodo'`; remover `tarefas_mpp` (ou `[]`).
   - Itens com `meses_veks` (escritório/empréstimo/miscelânea/estadia/refeições/
     encarregado/carro) distribuídos jun–out conforme a `Planilha1`, somando **457.000**.
   - Remover do INDIRETOS as adoções de tarefas `2,6,19,34,36,55,56` (resumo + FAZENDA
     + limpeza/desmob).
3. **11 etapas entregáveis:** Veks/Fat e itens fiéis à `Planilha1`; `tarefas_mpp` = suas
   folhas reais do `.mpp` (vínculo opcional da Baia, mapa já revisado).
4. `obra.regime_medicao = 'fixa'`.

**Verificação:** `python3` lê o fixture e confere: Σveks etapas+período = 800.960;
Σfat = 550.775; INDIRETOS mensal soma 457.000; nenhum `tarefas_mpp` aponta para resumo.

---

## Fase 6 — Apresentação no detalhe financeiro

**Arquivos:** `templates/cronograma/fisico_financeiro.html`,
`templates/obras/detalhes_obra_profissional.html`, `static/js/financeiro_obra.js`.

1. Na tabela de etapas, renderizar linhas de período junto das entregáveis, com a
   coluna de % físico vazia/“—” (tudo junto — decisão do usuário).
2. Garantir que o caixa/curva S inclui o período (já vem do faseamento por linhas).

**Verificação:** render server-side da página não quebra; INDIRETOS aparece como linha
de custo sem %; etapas entregáveis com % e custo.

---

## Fase 7 — Exclusão de período do RDO/portal (garantia)

**Arquivos:** rotas de RDO (`views/rdo.py`, `cronograma_views.py`) e portal
(`portal_obras_views.py`).

1. Como período não é `TarefaCronograma`, ele já não aparece. **Auditar** as queries de
   RDO/portal/cronograma para confirmar que nenhuma lista linhas de custo de período.
2. Teste de regressão: portal e RDO da Baia não contêm "Indiretos".

**Verificação:** teste — listagem de tarefas do RDO/portal da Baia não inclui período.

---

## Fase 8 — Atualizar testes e fechar

**Arquivo:** `tests/test_importacao_fisico_financeiro.py`,
`tests/test_painel_financeiro.py`, `tests/test_cronograma_fisico_financeiro.py`.

1. `test_importa_cria_etapas_tarefas_e_custos`: trocar `raizes == 12` (não há mais 12
   raízes) por asserts da nova árvore (1 raiz OBRA + outline; 56 tarefas; FAZENDA
   presente; INDIRETOS ausente) e 12 linhas de custo no painel.
2. Atualizar asserts de veks/fat/lucro (mantêm 800.960 / 550.775 / 24.976).
3. Adicionar os testes das Fases 1, 2, 4, 7.
4. Rodar a suíte inteira; confirmar verde.

**Verificação:** suíte financeira 100% verde; invariantes da Fase 0 preservados.

---

## Sequência de dependências
```
F0 → F1
F0 → F2 → F3 → F4 → F5 → F6 → F7 → F8
            (F3 é pré-requisito de F4)
```
F1 (regime) é independente das demais e pode ir em paralelo, mas o faturamento por
regime só é exercitado no teste após F8.

## Rollback
Cada fase é um commit isolado. Se o agrupamento por OSC (F3) ou a materialização (F4)
regredir números, reverter o commit da fase mantém as anteriores estáveis.
