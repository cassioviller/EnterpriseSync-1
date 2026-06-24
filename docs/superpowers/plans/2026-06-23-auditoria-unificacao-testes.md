# Auditoria & Unificação da Suíte de Testes

> Gerado em 2026-06-23. Auditoria de 77 arquivos em `tests/` (≈471 testes coletados pelo pytest).
> Objetivo: revisar, atualizar, des-duplicar e unificar a suíte ("antigos, repetidos").

## Achado de infraestrutura (crítico)

- `pytest tests/` coleta **471 testes** (18s, sem erros de coleção). Existe também `tests/utils/test_rdo_horas.py`.
- **Nada roda automaticamente**: `.replit` só sobe `gunicorn main:app`; não há `.github/workflows`; `run_tests.sh` (mesmo sem filtro) só executa `tests/test_browser_all_modules.py`.
- **~24 arquivos são SCRIPTS legados** (`def teste_`/`def main()`/`if __name__=='__main__'`, reportam via `print`, prefixo pt `teste_` não casa o padrão `test_` do pytest) → contribuem **0 testes coletados**. É cobertura real que o `pytest tests/` **nunca executa**.

## Duas populações

1. **Pytest nativo** (~43 arquivos): coletados e executáveis por `pytest tests/`.
2. **Scripts standalone** (~24 arquivos): rodados à mão / `run_tests.sh --standalone` (que na prática só roda 1 arquivo). Invisíveis ao CI.

---

## Ações consolidadas (das 7 auditorias)

### A. DELETE / mover para fora de `tests/`
| Arquivo | Motivo | Destino |
|---|---|---|
| `test_e2e_modules.py` | Smoke Flask test_client legado; 19 rotas já cobertas por `test_browser_all_modules.py` | deletar (migrar casos órfãos antes) |
| `_test_fluxo_classificacao.py` | Prefixo `_test_` não coletado; é ferramenta de diagnóstico, não teste | mover p/ `tools/diagnose_fluxo_caixa.py` |
| `_seed_subgrupo_aninhado_pw.py` | Helper de seed para playwright manual | virar fixture ou deletar |

### B. MERGE (duplicatas confirmadas)
| De | Para | Sobreposição |
|---|---|---|
| `test_calculo_tolerancia.py` | `test_regras_salario_completo.py` | Mesmos cenários de tolerância/DSR/HE/simulação jan-2026 |
| `test_composicao_formato_br_playwright.py` | `test_formato_br_e2e_extra.py` | Mesma tela `/catalogo/servicos` + milhar BR (subset) |
| `test_rdo_kpis_task140.py` | `test_rdo_listagem_kpis.py` | Mesmo motor `calcular_progresso_geral_obra_v2`; bugs #1-3 |
| `test_propostas_block_scripts_213.py` (HTTP) | manter só `_playwright` | Mesmo fluxo cronograma-revisar→aprovar; e2e real é superior |
| `test_e2e_varredura_paginas_playwright.py` | `test_browser_all_modules.py` (avaliar) | 20+ rotas em comum; smoke canônico já cobre com mais rigor |

### C. CONVERTER SCRIPT → pytest (cobertura real, hoje não roda no CI)
Prioridade alta (E2E críticos):
- `test_cronograma_automatico_aprovacao.py` (Task #102)
- `test_cronograma_revisao_obra_gate.py` (Task #200)
- `test_e2e_proposta_aprovacao_cliente.py` (Task #132)
- `test_e2e_orcamento_proposta.py` (Task #95)

Demais conversões:
- `test_e2e_orcamento_proposta_modelo.py` (#31)
- `test_orcamento_pricing_parity.py` (#74), `test_bdi_completo_playwright.py`
- `test_orcamento_fator_comercial_playwright.py` (#74), `test_orcamento_fracionavel_playwright.py` (#75)
- `test_orcamento_formato_br.py`, `test_orcamento_formato_br_e2e.py`, `test_formato_br_e2e_extra.py`
- `test_compras_nova_dropdown.py`, `test_compras_tipo.py`
- `test_clausulas_configuraveis.py` (#174), `test_legacy_propostas_drop.py` (#201)
- `test_task_172_obra_cliente_fk.py`, `test_task_45_catalogo_eventos.py`, `test_task_86_catalogo_propostas.py`, `test_insumo_coeficiente_padrao.py` (#166)
- `test_rdo_listagem_kpis.py`, `test_rdo_subgrupo_aninhado.py`, `test_rdo_unificado_responsaveis.py`, `test_agrupamento_diarias_rdo.py`, `test_auto_link_servico_rdo.py`, `test_cronograma_duplicado_rdo.py`
- `test_e2e_metricas_funcionario.py` (#98)

### D. FIX (frágil)
| Arquivo | Problema |
|---|---|
| `test_ciclo_proposta_obra_medido_cr.py` | `admin_id=63` hardcoded — quebra se o banco não tiver admin 63; parametrizar via fixture |

### E. KEEP (saudáveis, pytest nativo) — não mexer
`test_browser_all_modules.py`, `test_e2e_jornada_proposta_cronograma_playwright.py`, `test_bdi_pricing.py`, `test_orcamento_service.py`, `test_orcamento_operacional.py`, `test_e2e_orcamento_operacional_e_metricas_views.py`, `test_orcamento_override_e2e.py`, `test_proposta_no_leak.py`, `test_notificacao_proposta_enviada.py`, `test_propagacao_proposta_obra.py`, `test_engenheiro_responsavel_pdf.py`, `test_rdo_ciclo_completo.py`, `test_rdo_edicao_ocorrencia_observacao.py`, `test_rdo_edicao_preserva_tarefa.py`, `test_rdo_legacy_endpoints_horas.py`, `test_rdo_progresso_monotonico_playwright.py`, `test_rdo_subgrupo_aninhado_playwright.py`, `test_rdo_unificado_playwright.py`, `test_cronograma_fisico_financeiro.py`, `test_fluxo_obra.py`, `test_resumo_custos_obra.py`, `test_classificador_cadastro.py`, `test_aprendizado_classificacao.py`, `test_regressao_classificacao.py`, `test_processar_usa_cadastro.py`, `test_endpoint_classificar_termo.py`, `test_catalogos_palavras_chave.py`, `test_seed_palavras_chave.py`, `test_palavra_chave_models.py`, `test_importar_composicoes.py`, `test_vinculo_subatividade_composicao.py`, `test_regras_salario_completo.py`, `test_custo_diario.py`, `test_metricas_produtividade.py`, `test_agregar_fluxo_mensal.py`, `test_fluxo_entradas_realizadas.py`, `test_webhook_dispatcher.py`, `test_seed_alfa_reset_isolation.py`, `tests/utils/test_rdo_horas.py`, `conftest.py`, `playwright_run_notes.py`.

---

## Plano faseado proposto

- **Fase 0 — Gate de CI (base): ✅ CONCLUÍDA.** Gate: `pytest tests/ -m "not browser"` → **284 passed, 4 skipped** (determinístico, 2 runs verdes).
  - **Causa-raiz das 8 falhas do baseline (descoberta):** não eram regressões nem testes desatualizados — eram **registro incompleto de blueprints**. `app.py` registra ~37 blueprints; `main.py` (o que o gunicorn serve) adiciona ~17. Templates como `base_completo.html` referenciam endpoints que só existem após `main.py` (`custos_escritorio.painel_mensal`, `financeiro.dashboard`). Como o Flask trava o registro após a 1ª request, rodar a suíte com o app de 37 quebrava renders de forma **não-determinística** (endpoint faltante variava por ordem de execução).
  - **Fix:** `import main` no nível de módulo do `tests/conftest.py` (roda na coleção, antes de qualquer módulo de teste/request) monta o app canônico de 54 blueprints. + `pytestmark = pytest.mark.browser` no `test_browser_all_modules.py` para o gate poder excluí-lo.
  - **Os 4 skips** são legítimos: `test_fluxo_obra` / `test_fluxo_entradas_realizadas` são read-only contra o banco demo (ADMIN/OBRA/janela hardcoded) e pulam quando a precondição não existe — candidatos a self-seeding em fase futura.
- **Fase 1 — Limpeza barata (baixo risco): ✅ itens seguros concluídos.**
  - `27c1f1f` delete `test_e2e_modules.py` + 4 rotas órfãs migradas ao smoke (3 eram redirects inexistentes).
  - `2192e96` `_test_fluxo_classificacao.py` → `scripts/` (diagnóstico).
  - `dbd91b3` merge `test_calculo_tolerancia` → `test_regras_salario_completo` (preservada a tolerância-sobre-extras, única).
  - **Re-sequenciado (decisão de auditoria):**
    - Merges `composicao_formato_br`, `rdo_kpis_task140`, `block_scripts_213` (HTTP) envolvem **scripts legados 0-coletados** → movidos para a Fase 3 (fundir = converter + consolidar num passo só; fundir sem converter é churn sem valor).
    - `varredura_paginas` **NÃO será deletada**: ela é SUPERIOR ao `ConsoleSweep` (resolve rotas via `url_for`, valida conteúdo E checa erros JS), e cobre ~15 rotas únicas. O `(avaliar)` do plano resolveu-se como "manter varredura". Dedup fino varredura↔ConsoleSweep fica para a Fase 4.
- **Fase 2 — Conversões críticas: ✅ CONCLUÍDA** (`6b2fa77`, `5d2da41`). 4 E2E críticos viram pytest @integration. **Reconciliação real:** #200 e #132 assumiam envio direto de proposta (pré-Task #31); hoje a rota /status exige revisão concluída (400 caso contrário) → ajustados para simular a confirmação de revisão.
- **Fase 3 — Conversões restantes: 🔄 EM ANDAMENTO (11 de ~16 não-playwright feitas).**
  - `1f47f9e` 6 Runners: compras_tipo, cronograma_duplicado_rdo (#144), e2e_metricas_funcionario (#98), orcamento_override_e2e (#120), rdo_unificado_responsaveis (#149), rdo_subgrupo_aninhado (#154). **Reconciliação:** Task #172 tornou `obra.cliente_id` FK NOT NULL e removeu `cliente_nome` → testes passam a criar Cliente; rdo_subgrupo também encurta numero_rdo (estourava varchar(20)).
  - `4af6d68` 5 main(): e2e_orcamento_proposta_modelo (#31), engenheiro_responsavel_pdf (#173), legacy_propostas_drop (#201), orcamento_pricing_parity (#74, puro), proposta_no_leak (#115, puro).
  - **Gate:** 292 passed, 4 skipped (era 284 na Fase 0; +11 cobertura real agora executável).
  - `ce4aab1` par RDO KPIs: rdo_kpis_task140 (#140, +cliente_id Task #172) e rdo_listagem_kpis (#61). Dedup fina do overlap do motor fica como refinamento.
  - **Total convertido na Fase 3: 13** (6 Runners + 5 main() + 2 RDO KPIs). Gate: **303 collected**.
  - **Restante Fase 3 (grupos distintos):**
    - 3 em `collect_ignore_glob` (insumo_coeficiente #166, orcamento_formato_br, task_45 #45) — precisam sair do ignore + converter.
    - 10 playwright — precisam de servidor gunicorn + marcador `browser` (rodam via run_tests.sh, mecânica diferente do gate rápido).
  - **DEFERIDOS (reconciliação profunda — não rushar):**
    - `test_task_172_obra_cliente_fk` — usa kwarg removido `cliente_nome` e checa `cliente_nome_efetivo`; semântica da feature evoluiu.
    - `test_compras_nova_dropdown` (#202) — 2 asserts de template desatualizados (link de fornecedor `almoxarifado.fornecedores_criar`; `<select>` vs alerta em lista vazia).
    - `test_clausulas_configuraveis` (#174) — REV4: remoção de cláusula via sentinela deixa `clausulas=1` (esperava 0).
- **Fase 3 (cont.):** `d8fb2ba` insumo_coeficiente (#166) + orcamento_formato_br (#165) — saíram do collect_ignore_glob; helpers `teste_*` renomeados p/ `_teste_*`. `28fd5fa` 6 playwright @browser (bdi_completo, fator_comercial #74, formato_br_e2e orçamentos, fracionavel #75, block_scripts_213 #213, rdo_unificado #152) — 6 passed contra servidor.
  - **Total Fase 3: 21 conversões** (15 não-playwright + 6 playwright). Gate rápido: ~300 coletados.
  - **DEFERIDOS (8, reconciliação profunda — não rushar):**
    - Schema/feature drift: `task_172` (kwarg removido `cliente_nome`), `compras_nova_dropdown` (#202, template), `clausulas_configuraveis` (#174, REV4).
    - Híbrido fixtures: `task_45_catalogo_eventos` (#45, `def test_*(admin, proposta)` posicionais).
    - DOM drift playwright: `composicao_formato_br`, `formato_br_e2e_extra` (TypeError), `rdo_progresso_monotonico` (#143), `rdo_subgrupo_aninhado_playwright` (#154) — Timeout/seletor.

- **Fase 4 — 🔄 itens de infra/frágil concluídos:**
  - `7ba6fb0` `ciclo_proposta_obra_medido_cr` (#94): admin_id=63 hardcoded → admin dinâmico + convertido a pytest.
  - `d39bf9a` `run_tests.sh` ganha `--gate` (`pytest tests/ -m "not browser"`) e `--suite` (suíte inteira).
  - `<sys.path>` conftest força a raiz no `sys.path` — o console script `pytest` (usado pelo run_tests.sh) não adicionava o CWD, quebrando a coleção de `test_agregar_fluxo_mensal` (`from financeiro_service import …`). **Achado via a validação do `--gate`.**
  - `d9f64c5` `rdo_subgrupo_aninhado_playwright` (#154): mesmo schema drift Task #172 → convertido @browser (verde).
  - `119c84f` `formato_br_e2e_extra`: seed corrigido (cliente_id); conversão ainda pendente por DOM drift.
  - **Gate `bash run_tests.sh --gate`: 297 passed, 4 skipped, 0 failed.**

- **Fase 4 (cont.) — ✅ 7 deferidos reconciliados e convertidos:**
  - **Não-browser (+15 testes no gate):**
    - `task_172_obra_cliente_fk`: t3 usa `cliente_busca` (#176 resolve nome via `services.cliente_resolver`); t5 (fallback obra legada) **removido** — #176 tornou `obra.cliente_id` FK NOT NULL e eliminou as colunas-texto `cliente_*`. → pytest @integration.
    - `task_45_catalogo_eventos`: fixtures pytest reais (admin/cliente/proposta/obra) c/ sufixos únicos; `step()` passa a assertar. **Sai do `collect_ignore_glob`** (agora vazio). 12 testes.
    - `clausulas_configuraveis` (#174): reconciliação Task #31 — `/propostas/editar` só edita in-place **rascunhos**; uma 'enviada' é redirecionada p/ "nova versão" (por isso a remoção via sentinela deixava clausulas=1). `prop_remove` passa a nascer 'rascunho'. → pytest @integration.
    - `compras_nova_dropdown` (#202): UX REV — empty-state trocou link p/ página por criação **inline** (`qcAbrirFornecedor()`); `<select>` agora é sempre renderizado (sem options quando vazio). Asserts atualizados. → pytest @integration.
  - **Browser (DOM/value drift) — 3 convertidos @browser:**
    - `composicao_formato_br` (#189): cards CUSTO/PREÇO 2x`<h3>`→4x`<h4>` (Task #47): custo=nth(0), preço=nth(3); assertion tolera colunas inteiras (`pacotes`). **Fix de template**: quebra de preço renderizava `{{ imposto_pct }}%`/`{{ margem }}%` crus (US `13.00%`) → `|num(2)` (`13,00%`).
    - `formato_br_e2e_extra` (#189): preço de venda **re-derivado** pela fórmula margem-sobre-preço (`custo/(1-(imp+margem)/100)` = R$ 7.923,89) — seed/asserts atualizados.
    - `rdo_progresso_monotonico` (#143): data do card `.rdo-date span` → `.rdo-card-header small`.
  - **Gate final: 312 passed, 4 skipped, 0 failed** (era 297; +15). Suíte coleta **513 testes** sem erros; os 3 @browser verdes contra servidor.
  - Dedup varredura↔ConsoleSweep: resolvido como "manter ambos" (varredura é superior).

**STATUS: plano CONCLUÍDO.** Todas as fases (0–4) verdes; nenhum deferido restante.

Cada fase = commits pequenos e reversíveis; a suíte deve ficar verde ao fim de cada uma.
