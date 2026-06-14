# Mapa de código — Cronograma ↔ Custo ↔ Medição (SIGE)

> Referência do estado REAL do subsistema, levantada por leitura de código (views, handlers,
> services, templates), não de suposição. Base para implementar a espinha financeira
> (`2026-06-14-espinha-financeira-obra-design.md`). Data: 2026-06-14.
> Convenção: ✅ funciona/em uso · 🟡 implementado mas dormente · 🐛 bug · ❌ não existe.

## 0. Estado dos dados (Postgres de produção, 2026-06-14)
- `tarefa_cronograma` = **0** · `rdo_apontamento_cronograma` = **0** · `rdo_mao_obra.tarefa_cronograma_id` = **0/539**.
- `rdo_servico_subatividade` = 297 · `rdo_mao_obra` total = 539 (385 com `subatividade_id`, 154 soltos).
- `subatividade_mestre` = **0** (catálogo de produtividade vazio).
- `item_medicao_comercial` = 11 · propostas aprovadas = 26 · orçamento Baia `ORC-BAIA-REV10` id 98 **sem obra**.
> Leitura: o caminho cronograma (Mundo B) está **implementado mas nunca persistiu dado**; a operação
> real roda no caminho legado por subatividade (Mundo A). A Baia é greenfield.

## 1. Dois fluxos de RDO coexistindo (feature-flag por tenant)
Gate: `is_v2_active()` (`utils/tenant.py:80`, exige `Usuario.versao_sistema=='v2'`).
- **Legado (subatividade-driven):** atividades de `Servico`/`SubatividadeMestre`; grava
  `RDOServicoSubatividade`; MO em `RDOMaoObra.subatividade_id`. **É o que tem dado hoje.**
- **V2 (cronograma-driven):** atividades de `TarefaCronograma`; produção em
  `RDOApontamentoCronograma`; MO em `RDOMaoObra.tarefa_cronograma_id`. 🟡 dormente.

Rotas/arquivos RDO:
- `GET /rdo/novo` → `novo_rdo()` `views/rdo.py:532`; template `templates/rdo/novo.html`.
- `POST /salvar-rdo-flexivel` → `salvar_rdo_flexivel()` `views/rdo.py:3857` (**save em uso**).
- `GET/POST /rdo/editar/<id>` → `rdo_editar_sistema.py:18` / `:168`; template `editar_rdo.html`.
- API atividades p/ RDO: `GET /cronograma/obra/<id>/tarefas-rdo` → `cronograma_views.py:809`.

## 2. Espinha VENDA + AVANÇO por atividade — ✅ existe e está correta
Cadeia: orçamento → proposta aprovada → `TarefaCronograma` + `ItemMedicaoComercial` →
RDO apontamento → % → medição → ContaReceber.

- **Quantidade da atividade:** `TarefaCronograma.quantidade_total` (folhas; grupos = None), definida na
  materialização `services/cronograma_proposta.py:619` a partir do template
  (`CronogramaTemplateItem.quantidade_prevista`).
- **Avanço/acumulado:** `RDOApontamentoCronograma` (`views/rdo.py:866`, `cronograma_views.py:1157`):
  `quantidade_acumulada = Σ quantidade_executada_dia`; `percentual_realizado = acumulada/quantidade_total×100`.
- **% da tarefa:** `utils/cronograma_engine.py:524` `atualizar_percentual_tarefa` (usa o último
  acumulado; rollup bottom-up dos pais por `duracao_dias` em `:217`).
- **% do item (venda):** `services/medicao_service.py:48` `calcular_percentual_item` = média
  ponderada por **peso** dos `percentual_concluido` das tarefas vinculadas.
- **Valor:** `medicao_service.py:120` `valor = (perc_periodo/100) × ItemMedicaoComercial.valor_comercial`.
- **ContaReceber:** `medicao_service.py:275` `recalcular_medicao_obra` faz UPSERT de **UMA** ContaReceber
  por obra (`OBR-MED-{obra_id}`). Fallback por `servico_id` via `RDOServicoSubatividade.percentual_conclusao`
  (`:234`) permite medir sem cronograma.
- **Peso venda↔atividade:** `ItemMedicaoCronogramaTarefa.peso` (Numeric 5,2). Criado na materialização
  por horas (`cronograma_proposta.py:675`, fallback divisão igual em `:677`). **Editor manual já existe:**
  `medicao_views.py:344` `vincular_tarefa` (valida ≤100% e soma); `desvincular_tarefa` `:403`; tela
  `templates/medicao/gestao_itens.html`; validação soma=100% `medicao_service.py:68`.
- **Valor agregado por atividade já é calculável** (`% × peso_norm × valor_comercial`), só não é exposto.

**Pendências da espinha de venda:**
- 🟡 **Materialização não-automática:** `handlers/propostas_handlers.py:131` só materializa se a proposta
  tem `cronograma_default_json` (snapshot revisado). Sem isso → 0 cronograma (explica 26 aprovadas / 0 tarefa).
  Sempre rodam na aprovação: criar `Obra` (`event_manager.py:988`) e `ItemMedicaoComercial` 1:1
  (`propostas_handlers.py:55`).
- 🐛 **Bug edição RDO V2:** `editar_rdo.html:2446` emite `sub_func_{tarefaId}_...`; `rdo_editar_sistema.py:374`
  trata o 1º número como `sub_mestre_id` → **perde** `tarefa_cronograma_id` ao editar. Vínculo da equipe vira solto.

## 3. Custo de MO — como é calculado e rateado
- **Horas normalizadas:** `utils/rdo_horas.py` `normalizar_horas_funcionario` — jornada-base = MAIOR
  hora lançada; dividida (igual ou por pesos) entre as N atividades distintas (8h em 3 ⇒ 8/3, não 24).
  Chamada em `views/rdo.py:4343`. Logo `RDOMaoObra.horas_trabalhadas` já é a hora real **por atividade**.
- **Custo diário onerado:** `services/custo_funcionario_dia.py:52` `calcular_custo_funcionario_no_rdo`:
  diarista = `valor_diaria × (horas_no_rdo/horas_totais_dia)`; mensalista = `horas_no_rdo × valor_hora`;
  `+VA+VT`. Grava `RDOCustoDiario.custo_total_dia` (`models.py:961`). `horas_totais_dia` = soma das horas
  do funcionário em todos os RDOs do dia. **`tipo_lancamento='ocioso_mensal'`** captura salário pago não
  apontado (sem entrada manual).
> Para custo de MO **por atividade** (D1 do design): ratear `custo_total_dia × horas_atividade /
> horas_totais_dia`. Fecha sem perder nem inflar (mesmo denominador). **Computado no read-model**, não gravado.

## 4. Pipeline de custo — onde cada custo aterrissa (o BURACO)
Dois destinos: `CustoObra` (legado; `models.py:659`; sem servico/tarefa) e `GestaoCustoPai`/`GestaoCustoFilho`
(ledger V2; único elo fino = `GestaoCustoFilho.obra_servico_custo_id`, nível **Serviço**).
**Nenhuma tabela de custo tem `tarefa_cronograma_id` nem `subatividade_id`.**

| Custo | Handler (`event_manager.py`) | Grava | Nível mais fino |
|---|---|---|---|
| MO (RDO) | `lancar_custos_rdo` :580 | CustoObra :705 + GestaoCustoFilho :751 | **Serviço** (só se func. tocou 1 serviço; senão rateio) |
| MO (ponto) | `calcular_horas_folha` :292 | CustoObra/GestaoCustoFilho | Obra |
| Material | compra `:129`; saída `:87` é **no-op** | GestaoCustoFilho (na compra) | **Empresa** (nem chega à obra) |
| Combustível | `lancar_custo_combustivel` :507 | CustoObra :553 | Obra |
| Alimentação | `criar_conta_pagar_alimentacao` :1235 | ContaPagar :1295 + GestaoCustoFilho | Obra |
| Subempreitada | manual `gestao_custos_views.py:253` | GestaoCustoFilho | Obra |

- **MO descarta o elo de atividade:** `lancar_custos_rdo` agrega por funcionário/dia e infere serviço só
  se único (`event_manager.py:645-671`); ignora `RDOMaoObra.subatividade_id`/`tarefa_cronograma_id`.
  `services/rdo_custos.py:303` `gerar_custos_mao_obra_rdo` (caminho V2) nunca passa `obra_servico_custo_id`.
- **"Realizado por serviço"** de `services/resumo_custos_obra.py:106` `recalcular_obra` é majoritariamente
  **rateio por orçado** (`:190`), não incorrido real.
- ❌ **Subempreitada:** `RDOSubempreitadaApontamento` (`models.py:5500`) **tem `tarefa_cronograma_id`** (:5509)
  mas **não gera custo nenhum** (só produtividade, `cronograma_views.py:914`). Gancho pronto p/ o telhado viga I.

## 5. Como o orçamento é montado (composição)
- `services/orcamento_service.py:34` `calcular_precos_servico`: `custo_unitario = Σ(coeficiente ×
  preço_vigente)`; split material/MO/outros por `Insumo.tipo` (`:74`).
- **Coeficiente** = consumo do insumo por **unidade do serviço**; a unidade depende do `Insumo.unidade`.
- **Baia tem MO mista** (dado real do orçamento 98):
  - **hora** (`un=h`, coef em h/un): item **1.1 LSF** (Encarregado 0,022 h/kg, Ajudante 0,044 h/kg…). Tem hora-homem.
  - **R$/m²** (`un=m²`, coef=1, preço/m²): 1.2, 1.3, 1.5, 1.6… (maioria). **Sem hora.**
  - **un / verba**: 1.4 portão etc.
  - Tenant: 224 insumos MO em `h`, 12 `m²`, 5 `un`, 5 `vb`, 1 `m`, 1 `dia`.
> Por isso o alarme primário é em **R$** (D5): a hora orçada não existe na maioria dos itens.
- `OrcamentoItem.composicao_snapshot` (JSON) guarda as linhas com `tipo` e `subtotal` (por unidade) —
  fonte do **custo MO orçado da atividade** (Σ linhas MAO_OBRA × quantidade × peso).

## 6. Arquivos-chave (índice)
`views/rdo.py` · `rdo_editar_sistema.py` · `cronograma_views.py` · `templates/rdo/{novo,editar_rdo}.html` ·
`services/cronograma_proposta.py` · `utils/cronograma_engine.py` · `services/medicao_service.py` ·
`medicao_views.py` · `templates/medicao/gestao_itens.html` · `handlers/propostas_handlers.py` ·
`event_manager.py` · `utils/financeiro_integration.py` · `services/rdo_custos.py` ·
`services/custo_funcionario_dia.py` · `utils/rdo_horas.py` · `services/resumo_custos_obra.py` ·
`services/orcamento_service.py` · `models.py`.
