# Plano — Importador físico-financeiro preenche o fluxo comercial completo

**Data:** 2026-06-24
**Branch:** `feat/importador-fluxo-completo`

## Objetivo

Ao importar o JSON físico-financeiro, materializar **toda** a cadeia canônica
(Insumo → Orçamento → Proposta → Obra → ItemMedicaoComercial → ObraServicoCusto),
em vez de só criar IMC/OSC à mão. Assim a obra importada passa a existir também
nos módulos **Orçamento** e **Propostas**, com rastreabilidade insumo→venda→custo.

## Decisões (do usuário)

1. **Arquitetura A** — reusar o caminho canônico (emitir `proposta_aprovada`),
   single source of truth.
2. **Sem contábil** — a importação NÃO gera lançamento contábil/partidas.
3. **Casar insumos com o catálogo** — cada item de custo vira Insumo +
   ComposicaoServico (coeficiente × preço).

## Restrição técnica → arquitetura híbrida

`services/cronograma_proposta.materializar_cronograma` só semeia datas a partir
de `obra.data_inicio`; **não carrega as datas por tarefa do MS Project** que o
faseamento físico-financeiro exige. Logo:

- **Cadeia comercial pelo canônico:** Orçamento(+itens c/ composição) → Proposta
  (+itens) → `emit('proposta_aprovada', skip_contabil=True)` → cria Cliente +
  Obra (reusada via `obra_id` pré-setado) + IMC (1/PropostaItem) → listener
  `after_insert` cria OSC.
- **Específicos físico-financeiros no importador:** cronograma raiz+folhas com
  datas do `.mpp`, vínculos `ItemMedicaoCronogramaTarefa` (peso=dias),
  preenchimento de custo (`veks→mao_obra_a_realizar`, `fat→material_a_realizar`),
  `MedicaoContrato` e snapshot. NÃO setar `cronograma_default_json` (assim o
  canônico pula a materialização de cronograma).

## Passos

1. **`handlers/propostas_handlers.py`** — `handle_proposta_aprovada` aceita
   `skip_contabil` no payload do evento; quando True, propaga proposta→obra e
   materializa cronograma, mas pula lançamento contábil/partidas.
2. **`services/importacao_fisico_financeiro.py`** — reescrita híbrida:
   - resolvers `_resolver_servico`, `_resolver_insumo` (+ `PrecoBaseInsumo`),
     `_compor_servico` (ComposicaoServico + composicao_snapshot);
   - cria Orçamento (status `convertido`) + OrcamentoItem/etapa;
   - cria Proposta + PropostaItem/etapa, `obra_id` pré-setado, sem cronograma_default;
   - `emit('proposta_aprovada', skip_contabil=True, raise_on_error=True)`;
   - recupera IMC/OSC por `proposta_item_id`; preenche custo veks/fat;
   - constrói cronograma físico (datas do .mpp) + vínculos;
   - MedicaoContrato + snapshot;
   - idempotência: limpa Orçamento/Proposta/IMC/OSC/cronograma/medições da obra.
3. **Testes** — estende `tests/test_importacao_fisico_financeiro.py`:
   - Orçamento + 12 OrcamentoItem; Proposta + 12 PropostaItem;
   - Insumos + ComposicaoServico criados; composição reproduz o custo;
   - NÃO há `LancamentoContabil` da importação;
   - mantém verdes os invariantes atuais (12 raízes, Σveks≈734460, Σfat≈423700,
     6 medições, snapshot 152047, reimport idempotente, multitenant).

## Invariantes a preservar (testes atuais)

12 raízes / folhas≥12 / 12 IMC / vínculos==folhas / Σveks≈734460 / Σfat≈423700 /
6 MedicaoContrato (Σpct=1, Σvalor≈valor_contrato) / snapshot.lucro_caixa_final=152047 /
reimport não duplica / isolamento multitenant / `avisos` é lista / aviso "sem tarefas".
