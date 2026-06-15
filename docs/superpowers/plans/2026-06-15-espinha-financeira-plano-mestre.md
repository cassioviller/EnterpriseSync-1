# Plano-mestre — Espinha Financeira da Obra (Fatias 1–5, visão integrada)

> Data: 2026-06-15. Branch: `design/espinha-financeira-obra`.
> Spec: `docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md`.
> Este documento é o **contrato compartilhado** das 5 fatias. Cada fatia tem seu plano próprio
> (`...-fatia-N-...-plan.md`) e DEVE obedecer às decisões cross-cutting (DC1–DC10) aqui.
> Objetivo de escrevê-las juntas: travar interfaces, achar problemas de integração cedo e
> **reusar ao máximo** o que o sistema já tem.

## Por que um plano-mestre

Planejar as 5 fatias isoladamente esconderia conflitos que só aparecem no conjunto. Olhando tudo
de uma vez, descobrimos **antes de escrever código**:

- **Risco de contar a Mão de Obra duas vezes** — o read-model lê o custo onerado de
  `RDOCustoDiario`; o ledger `GestaoCustoFilho` *também* recebe lançamentos `SALARIO` e `VALE_*`.
  Sem uma regra, a Fatia 2 somaria a folha de novo. → **DC3**.
- **Migrations espalhadas** — a Fatia 2 precisa de FK de atividade em 3 tabelas; a 4 e a 5 também
  tocariam dados. Em vez de N migrations, **uma só na Fatia 2**, desenhada para a espinha inteira.
  → **DC2**.
- **CPI e SPI já existem disfarçados** — o `alarme_mo` da Fatia 1 já é o CPI em R$; o
  `calcular_progresso_geral_obra_v2` já dá planejado×realizado (SPI). A Fatia 3 (EVM) é montagem,
  não motor novo. → **DC7**.

---

## Arquitetura em uma figura

```
                         ┌─────────────────────────────────────────────┐
   FONTES (já existem)    │  services/resultado_atividade_service.py    │   LENTE COMPETÊNCIA
   ─────────────────      │  (read-model — A ESPINHA, cresce por fatia) │   (Resultado real)
   RDOCustoDiario  ──MO──▶│                                             │
   GestaoCustoFilho ─não-MO▶  valor_agregado / custo_incorrido /        │
   composicao_snapshot ─▶ │  resultado / alarme / EAC / CPI / SPI       │
   ItemMedicaoCron.peso ─▶│                                             │
   RDOApontamentoCron ───▶│  Fatia1 MO · Fatia2 +não-MO · Fatia3 EVM    │
   cronograma_engine ────▶│  Fatia5 roll-up portfólio                   │
                          └───────────────┬─────────────────────────────┘
                                          │ (NUNCA funde com caixa — DC4)
   ContaReceber / ContaPagar ───▶ FinanceiroService.calcular_fluxo_caixa  LENTE CAIXA (Fatia 4)
   FluxoCaixa                    + agregar_fluxo_mensal (reuso integral)   (Realizado/Previsto)
```

---

## Decisões cross-cutting (DC) — obrigatórias para todas as fatias

### DC1 — O read-model é a espinha; nada de denormalizar
Tudo é **computado** em `services/resultado_atividade_service.py`. Fatias 3–5 só **leem** dele. Não
se grava custo redundante em tabela (evita inflar ledger e mantém a regra num lugar testável).
Exceção única: a etiquetagem de origem da Fatia 2 (FK `tarefa_cronograma_id` no lançamento), que é
*dado de origem*, não resultado calculado.

### DC2 — UMA migration, na Fatia 2, desenhada agora para a espinha inteira
A Fatia 1 é sem migration. A Fatia 2 traz **uma** migration que adiciona **todas** as FKs/campos de
atividade que a espinha vai precisar — assim Fatias 3, 4 e 5 ficam **sem migration**:

| Tabela | Coluna nova | Tipo | Para |
|---|---|---|---|
| `gestao_custo_filho` | `tarefa_cronograma_id` | FK→tarefa_cronograma, nullable, index, `ondelete='SET NULL'` | custo não-MO direto (Fatia 2) |
| `movimentacao_estoque` | `tarefa_cronograma_id` | FK→tarefa_cronograma, nullable, index, `ondelete='SET NULL'` | material consumido por atividade (Fatia 2) |
| `custo_veiculo` | `tarefa_cronograma_id` | FK→tarefa_cronograma, nullable, index, `ondelete='SET NULL'` | equipamento dedicado (Fatia 2, opcional de uso) |
| `rdo_subempreitada_apontamento` | `verba_unica` | Numeric(15,2) nullable | subempreitada vira custo (Fatia 2 / telhado) |
| `rdo_subempreitada_apontamento` | `lucro_pct` | Numeric(5,2) nullable | idem |
| `rdo_subempreitada_apontamento` | `gestao_custo_pai_id` | FK→gestao_custo_pai, nullable | idempotência do custo de subempreitada |

Fatia 5 (learning loop) escreve em colunas **já existentes** de `SubatividadeMestre`
(`meta_produtividade`, `duracao_estimada_horas`) — sem migration.

### DC3 — A Mão de Obra NUNCA conta duas vezes (regra de correção central)
O custo de **MO** no read-model vem **sempre** de `RDOCustoDiario.custo_total_dia` (onerado real,
inclui folha + VA + VT, já proporcional às horas — `services/custo_funcionario_dia.py`). Portanto a
leitura do ledger `GestaoCustoFilho` (Fatia 2) **exclui** as categorias de MO e auxílios, que já
estão no `RDOCustoDiario`:

```python
# em resultado_atividade_service.py (introduzido na Fatia 2)
_CATEGORIAS_MO = {'SALARIO', 'MAO_OBRA_DIRETA', 'VALE_ALIMENTACAO', 'VALE_TRANSPORTE'}
# o read-model lê do ledger SOMENTE categorias fora deste conjunto:
# MATERIAL, ALIMENTACAO (restaurante ≠ VA), TRANSPORTE (lançamento ≠ VT),
# EQUIPAMENTO/VEICULO, SUBEMPREITADA, OUTROS.
```
**Por quê:** `event_manager.lancar_custos_rdo` (event_manager.py:751) e `services/rdo_custos.py:427`
lançam `SALARIO`/`VALE_*` no ledger; se o read-model somasse isso ao `RDOCustoDiario`, a folha
entraria duas vezes. Esta regra fica num único ponto e é coberta por teste de regressão.

### DC4 — Competência (Resultado) ≠ Caixa, lentes separadas (D4 / ADR 0003)
- **Resultado** (read-model) usa a **data do fato**: `RDOCustoDiario.data`, avanço da medição.
- **Caixa** (Fatia 4) reúsa `FinanceiroService.calcular_fluxo_caixa` + `agregar_fluxo_mensal`
  (financeiro_service.py:430 e :682), filtrado por obra; a variação **parte de 0**; Realizado e
  Previsto **nunca são somados** (ADR 0003).
- As duas lentes **nunca se fundem** numa mesma série/total.

### DC5 — Custo orçado por atividade é uma família de funções sobre o snapshot
A Fatia 1 cria `custo_mo_orcado_unitario(snapshot)` (filtra `tipo=='MAO_OBRA'`). Generaliza-se para
`custo_orcado_unitario(snapshot, tipos)` e a Fatia 2 chama com os demais tipos. **Fonte única e
cadeia única** (confirmada no código):
`TarefaCronograma → ItemMedicaoCronogramaTarefa → ItemMedicaoComercial.proposta_item_id →
PropostaItem.composicao_snapshot`. Chaves do snapshot: `tipo` (MAIÚSC: `MAO_OBRA`/`MATERIAL`/…),
`unidade` (minúsc: `h`/`m2`/…), `coeficiente`, `subtotal_unitario` (custo por unidade de serviço).

### DC6 — Rateio por hora-homem é um helper único, escrito na Fatia 1
A Fatia 1 já rateia o custo onerado por horas/atividade/RDO (`custo_mo_atividade`). Extrair desse
código o helper reutilizável `_horas_func_rdo(rdo_id, func_id)` e o padrão de fração; a Fatia 2 usa
o **mesmo** mecanismo para ratear custos **compartilhados** (alimentação/transporte) por
hora-homem/atividade/dia. Nada de dois rateios divergentes.

### DC7 — CPI e SPI são reúso, não motor novo (Fatia 3)
- **CPI (R$)** já é o `alarme_mo` da Fatia 1 (`orcado_para_avanço / real`). A Fatia 2 o generaliza
  para custo total (`alarme_custo`). A Fatia 3 só lê esse índice.
- **SPI** já vem de `utils/cronograma_engine.calcular_progresso_geral_obra_v2` (obra) e
  `calcular_progresso_rdo` (tarefa) — planejado×realizado já calculados, `percentual_planejado`
  já persistido (`RDOApontamentoCronograma.percentual_planejado`, models.py:4944).
- **EAC** = `custo_orcado_total / CPI`; **datas projetadas** via SPI sobre `data_fim` planejada.
  A curva-S já existe (`views/obras.py:2312 curva_avanco_obra`). Fatia 3 = montagem + projeção.

### DC8 — Peso Serviço→Atividade é o da medição (D6), fonte única
`ItemMedicaoCronogramaTarefa.peso` (editor pronto: `medicao_views.py:344`, validação soma=100% em
`medicao_service.py:68`). Vale para **venda, custo orçado e rateio de orçado**. Nunca criar peso
paralelo.

### DC9 — Telhado viga I: subempreitada verba+lucro com venda total travada (Fatia 2)
Reusa o *margin lock* de `services/orcamento_view_service.py:recalcular_item` (venda = custo /
(1 − imposto% − margem%)) + `recalcular_orcamento` (:325) para manter a venda total em
**R$1.720.796,75** ao incluir o item. O custo entra no ledger via `apontar_subempreitada` estendido
(`cronograma_views.py:917`) → `registrar_custo_automatico(tipo_categoria='SUBEMPREITADA', …)` ligado
à atividade. Ver `ESPACO_telhado_viga_i_baia_rev10.md` (opção A/B a confirmar com o usuário).

### DC10 — Learning loop fecha o ciclo, sem migration (Fatia 5)
`indice_produtividade`/`produtividade_real` já são calculados (`services/rdo_custos.py:236`) mas
**nunca voltam** ao catálogo. A Fatia 5 lê os índices de RDOs finalizados e **atualiza**
`SubatividadeMestre.meta_produtividade`/`duracao_estimada_horas` (colunas existentes), melhorando o
próximo orçamento e os pesos da próxima materialização (`cronograma_proposta.py:675`).

---

## Contrato do read-model (interface que cresce, mas não muda assinaturas)

`services/resultado_atividade_service.py` — assinaturas estáveis a partir da Fatia 1:

| Função | Fatia | Retorno | Evolução |
|---|---|---|---|
| `valor_agregado_atividade(tarefa)` | 1 | Decimal | estável |
| `custo_mo_atividade(tarefa)` | 1 | Decimal | estável |
| `custo_orcado_unitario(snapshot, tipos)` | 1→2 | Decimal | Fatia 1 expõe `custo_mo_orcado_unitario`; Fatia 2 generaliza |
| `custo_nao_mo_atividade(tarefa)` | 2 | Decimal | nova (lê ledger etiquetado + rateio compartilhado, DC3) |
| `custo_incorrido_atividade(tarefa)` | 1→2 | Decimal | Fatia 1 = MO; Fatia 2 = MO + não-MO |
| `resultado_realizado_atividade(tarefa)` | 1 | Decimal | passa a usar `custo_incorrido` (sem mudar assinatura) |
| `alarme_custo(tarefa)` | 1→2 | dict | Fatia 1 = `alarme_mo`; Fatia 2 generaliza p/ custo total (CPI) |
| `evm_atividade(tarefa)` / `evm_obra(obra_id)` | 3 | dict (CPI/SPI/EAC) | novas, puras sobre o read-model |
| `resultado_obra(obra_id)` | 1→5 | dict | Fatia 1 rollup; Fatia 5 acrescenta o agregado de portfólio |

**Regra:** Fatia N só adiciona funções ou enriquece o **dict de retorno** de `resultado_obra`/
`evm_*`; nunca quebra a assinatura que a fatia anterior publicou.

---

## Mapa de reúso (o que NÃO vamos reescrever)

| Necessidade | Reusa | Arquivo |
|---|---|---|
| % por tarefa / venda | `calcular_percentual_item`, `valor = %×valor_comercial` | medicao_service.py:48,120 |
| custo onerado MO/dia | `RDOCustoDiario` + `calcular_custo_funcionario_no_rdo` | custo_funcionario_dia.py:52 |
| horas normalizadas por atividade | `normalizar_horas_funcionario` | utils/rdo_horas.py |
| baseline/curva planejada e SPI | `calcular_progresso_rdo`, `calcular_progresso_geral_obra_v2`, `curva_avanco_obra` | cronograma_engine.py:369,437 · obras.py:2312 |
| ledger de custo + agregação por serviço | `registrar_custo_automatico`, `recalcular_obra` (rateio) | financeiro_integration.py:59 · resumo_custos_obra.py:106 |
| caixa Realizado/Previsto | `calcular_fluxo_caixa`, `agregar_fluxo_mensal` | financeiro_service.py:430,682 |
| margin lock do orçamento | `recalcular_item`, `recalcular_orcamento` | orcamento_view_service.py:79,325 |
| produtividade observada | `recalcular_produtividade_rdo`, `metricas_produtividade.*` | rdo_custos.py:236 · metricas_produtividade.py |
| custo subempreitada manual (padrão) | `novo_custo_manual` (cria pai+filho) | gestao_custos_views.py:253 |
| materialização cronograma + peso | `materializar_cronograma`, `montar_arvore_preview` | cronograma_proposta.py:453,675 |
| aba na obra / portfólio | `detalhes_obra` (tabs L875), `dashboard_obras` | obras.py:1341 · dashboards_especificos.py:496 |

---

## Riscos cross-fatia (achados agora) e suas soluções

| # | Risco | Quando estouraria | Solução desenhada |
|---|---|---|---|
| R1 | MO contada 2× (RDOCustoDiario + ledger SALARIO) | Fatia 2 | **DC3** — `_CATEGORIAS_MO` exclui MO/VALE do ledger; teste de regressão |
| R2 | VA/VT contados 2× (já em `custo_total_dia` e como `VALE_*` no ledger) | Fatia 2 | **DC3** — VALE_* no conjunto excluído |
| R3 | Várias migrations + churn | Fatias 2,4,5 | **DC2** — migration única na Fatia 2 |
| R4 | Material só chega à obra (`MovimentacaoEstoque` sem FK de atividade) | Fatia 2 | **DC2** + espelhar o botão de equipe para "material direto na atividade" |
| R5 | Peso por divisão igual quando catálogo vazio | Fatias 1,2 (orçado/rateio errados) | **DC8** editor de medição + **DC10** learning loop alimenta o catálogo |
| R6 | Orçado zerado p/ item sem snapshot (ex.: telhado antes de cadastrar) | Fatias 1,2 | alarme degrada p/ "sem orçado", não quebra; cobrir em teste |
| R7 | Competência e caixa fundidas numa série | Fatia 4 | **DC4** — lentes separadas, nunca somadas |
| R8 | Gate v2 ausente | todas | checar `is_v2_active()` em toda view; obra/admin em `versao_sistema='v2'` |
| R9 | Quebra de assinatura do read-model entre fatias | 2–5 | Contrato (seção acima): só adicionar, nunca quebrar |

---

## Ordem de execução e dependências

```
Fatia 1 (MO + alarme + tela + habilitação Baia)        ── sem migration
   └─▶ Fatia 2 (migration ÚNICA; não-MO + subempreitada/telhado; custo_incorrido completo)
          ├─▶ Fatia 3 (EVM: CPI/SPI/EAC — puro cálculo sobre 1+2)         ── sem migration
          ├─▶ Fatia 4 (caixa: reuso fluxo de caixa por obra)              ── sem migration
          └─▶ Fatia 5 (portfólio roll-up + learning loop)                 ── sem migration
```
Fatias 3, 4 e 5 dependem da 2 (custo completo) mas são **independentes entre si** — podem ser feitas
em qualquer ordem ou em paralelo depois da 2.

## Critério de "pronto" da espinha
1. Resultado real por atividade (MO + material + transporte + subempreitada) bate com cálculo manual.
2. Editar RDO não corrompe vínculos (Fatia 1).
3. Soma dos custos das atividades = custo apontado da obra (sem dupla contagem — DC3).
4. EVM (CPI/SPI/EAC) coerente com Resultado e com a curva-S existente.
5. Lente de caixa separada da de competência (DC4), batendo com o fluxo de caixa atual.
6. Roll-up de portfólio soma as obras; learning loop melhora o catálogo a cada ciclo.
