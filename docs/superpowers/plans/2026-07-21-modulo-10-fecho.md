# Módulo 10 — Testes, Observabilidade e Implantação — Fecho

> Fecha a parte EXECUTÁVEL do M10 conforme o plano
> `2026-07-21-modulo-10-implementacao-testes-observabilidade.md` (spec
> `2026-07-17-modulo-10-testes-observabilidade-rollout.md`). A execução das
> fases 0-3 do rollout é operacional (homolog/produção) — ver "Runbook" e
> "Pendências". Com este documento fecha-se também o plano mestre
> `2026-07-17-cronograma-mpp-rdo-master-plan.md`.

## Entregue (commits nesta branch)

| Task | Commit | Conteúdo |
|---|---|---|
| 1 | `edc284c` | Flag por tenant: migração 211, helper endurecido, `scripts/flag_cronograma_mpp.py` |
| 2 | `89a1cb2` | `--java` no `run_tests.sh` |
| 3 | `c5d5f7f` | `test_cronograma_multitenancy.py` + `test_cronograma_permissoes.py` |
| 4 | `ed55430` | Métricas §4.3, logger `cronograma.importacao`, CLI de consistência |
| — | `6442e7a` | **Correção das duas regressões do M06 que o gate revelou** (fora do plano; ver abaixo) |
| 5 | este | Mapa dos 18 critérios, smoke de JVM no entrypoint, runbook, dívidas |

## O que o gate completo revelou (o achado do módulo)

A primeira execução do `--gate` até o fim neste módulo veio **2 failed,
650 passed**. Bisect: verde em `4418fbc` (fecho M05), vermelho em
`e7af912` (fecho M06). Ou seja: **duas famílias ficaram vermelhas do M06
ao M09 sem ninguém ver** — nenhum fecho anterior rodou a suíte inteira até
o fim. É exatamente a falha que este módulo existe para pegar, e o
argumento mais forte a favor do gate obrigatório por fase no runbook.

**1. Bug real de produção** (regressão de `335b0a6`, M06):
`rollup_realizado` ordenava os pais por `ordem` decrescente como *proxy* de
profundidade. O payload de `/cronograma/obra/<id>/tarefas-rdo` nunca teve
a chave `ordem` — todos viravam `0`, o sort estável processava a RAIZ
antes do subgrupo e ela lia `0` em vez do agregado das filhas. **Em árvore
de 3 níveis a raiz mostrava 0% no card de apontamento do RDO.** Corrigido
para ordenar por profundidade real da cadeia de `tarefa_pai_id`, com
proteção contra ciclo e pai órfão.

Vale notar que o fecho do M09 já havia registrado `rollup_raiz` como
"divergente por construção em árvores profundas" e o excluído da checagem
de concordância. Aquilo não era característica da agregação hierárquica —
era este bug, racionalizado.

**2. Teste desatualizado, não bug** (semântica intencional de `845db37`):
`test_rdo_kpis_task140` esperava pesos `100+50+10=160`. A tarefa de peso 10
(`Mobilização (sem plano)`, `duracao_dias=0`, unidade `vb`) é marco efetivo
pela tabela normativa §12 — peso 0 e fora do critério de homogeneidade de
unidade. Sobram t1/t2 em m² ⇒ `usar_qtd` com soma 150 ⇒ **13.33% é o valor
correto**. Expectativa atualizada com o porquê no comentário do teste.

## Checklist §22 da spec — estado

- [x] **Flag por tenant operante** — `configuracao_empresa.cronograma_mpp_ativo`
      (migração 211; a 204 sugerida pela spec já estava tomada por
      `_migration_204_gestao_custo_pai_categoria_fc`). Default FALSE;
      `utils.tenant.cronograma_mpp_ativo()` exige V2 **e** a flag, com falha
      segura em todos os caminhos (sem linha, sem tenant, erro de banco).
      13 testes em `tests/test_flag_cronograma_mpp.py`.
- [x] **Matriz de testes completa e verde** — os dois arquivos que faltavam
      existem; `--gate` e `--java` verdes SÓ APÓS a correção `6442e7a`
      (números na seção "Gate").
- [x] **Métricas por importação persistidas e visíveis** — consolidadas dos
      eventos do M02 por `services/cronograma_observabilidade.py` e
      servidas na lista da aba Cronograma. 8 testes em
      `tests/test_cronograma_metricas.py`.
- [ ] **Rollout fases 0-2 concluídas** — operacional, fora deste ambiente.
      Runbook abaixo.
- [x] **Critérios globais 1-18 verificados** — mapa abaixo (16 por teste,
      2 por checklist de fase).
- [x] **Dívidas registradas** — seção própria.

## Gate

```
bash run_tests.sh --gate   → 652 passed, 4 skipped, 200 deselected em 2238s (37m18s)
bash run_tests.sh --java   → 3 passed, 832 deselected em 143s
```

Primeira execução (antes de `6442e7a`): `2 failed, 650 passed`. A correção
das duas regressões do M06 fecha exatamente a diferença. A suíte é quase
toda de integração contra PostgreSQL real — daí os ~37 min; é o custo de
não ter mocks, e é por isso que os fechos anteriores o pularam.

## Mapa dos 18 critérios globais → o que os prova

| # | Critério | Prova |
|---|---|---|
| 1 | Duas obras com `.mpp` e cronogramas independentes | `test_cronograma_multitenancy.py` (6 testes; sensor = `capturar_estado` do M09) |
| 2 | Reimport do mesmo arquivo reconhecido por SHA-256 | `test_upload_cronograma.py::test_dedup_retorna_409` (+ escopo por obra em `test_cronograma_multitenancy.py::test_upload_do_mesmo_arquivo_em_obras_diferentes_nao_colide`) |
| 3 | Nova versão comparável antes de aplicar | `test_cronograma_endpoints_m05.py` (diff) + `test_cronograma_interface_obra.py::test_previa_*` |
| 4 | RDOs existentes nunca apagados | `test_cronograma_versao_service.py::test_aplicar_preserva_ids_apontamentos_e_percentual`, `::test_removida_e_arquivada_nunca_deletada_e_some_da_ui` |
| 5 | Fotos e comentários seguem vinculados | `test_migracao_baias_equivalencia.py` (equivalência compara contagem de fotos/apontamentos) + preservação de ids no critério 4 (a FK das fotos é o apontamento) |
| 6 | Tarefa quantitativa deriva percentual | `test_rdo_modos_apontamento.py::test_quantitativo_grava_semantica_e_snapshot` |
| 7 | Tarefa sem quantitativo aceita percentual acumulado | `test_rdo_modos_apontamento.py::test_apontar_producao_percentual_via_http`, `::test_salvar_rdo_flexivel_modo_percentual_via_form` |
| 8 | Correção retroativa recalcula acumulados posteriores | `test_rdo_recomputo_cadeia.py` (7 testes) |
| 9 | Planejado recalculado pelas novas datas | `test_replanejamento.py::test_replaneja_planejado_por_data_de_rdo_e_preserva_realizado`, `::test_aplicar_versao_replaneja_e_audita_evento` |
| 10 | Realizado permanece dos RDOs | mesmo teste do 9 (preserva realizado) + `test_cronograma_engine_unificado.py` |
| 11 | Cronograma, RDO, detalhes e portal exibem o mesmo percentual | `test_cronograma_engine_unificado.py::test_convergencia_todas_as_fontes_dao_o_mesmo_numero` + `test_rdo_subgrupo_aninhado.py` T3/T4 (cascata de N níveis — o teste que pegou o bug do rollup); em produção, `scripts/verificar_consistencia_progresso.py` (exit 1 = drift) |
| 12 | Falha no pipeline não deixa obra parcialmente alterada | `test_cronograma_versao_service.py::test_excecao_no_meio_faz_rollback_total` |
| 13 | Aplicação de versão transacional | mesmo teste do 12 + `::test_segunda_aplicacao_falha_limpa`, `::test_diff_desatualizado_e_rejeitado` |
| 14 | Restauração da versão anterior funciona | `test_cronograma_restaurar_versao.py::test_round_trip_aplicar_e_restaurar_volta_ao_snapshot` |
| 15 | Toda alteração tem usuário, data e origem | `CronogramaImportacaoEvento` em todas as transições — `test_cronograma_metricas.py` (eventos + logger com `importacao_id`/`obra_id`), `test_cronograma_restaurar_versao.py::test_restaurar_nao_deleta_e_registra_evento` |
| 16 | Fluxo atual das baias funciona durante toda a migração | **checklist de fase** — os 46 testes de `test_importacao_fisico_financeiro.py` seguem verdes sem edição desde o M09; a confirmação final depende da janela de estabilidade em produção |
| 17 | Nenhuma regra específica de baia no núcleo | **checklist de fase** — grep de guarda zerado em `services/` (M09 Task 4); a descontinuação física do §4.3 é pós-estabilidade |
| 18 | Todos os cálculos determinísticos e cobertos por testes | `test_cronograma_normalizacao.py` (determinismo), `test_cronograma_reconciliacao.py`, `test_cronograma_engine_unificado.py`, `test_replanejamento.py` |

## Decisão transferida do M03: Java em Docker

O fecho do M03 transferiu ao M10 a decisão sobre declarar JVM na infra.
**Decisão: não embutir JDK na imagem de produção.**

Razão: o pipeline inteiro (upload → parse → normalizar → reconciliar →
aplicar) roda sem JVM pelo caminho `.xml` (MSPDI), que é um "Salvar como
XML" no MS Project. A JVM só habilita o `.mpp` binário — conveniência que
não paga o custo de ~300 MB de imagem e de um modo de falha novo no
startup. Sem JVM, o `.mpp` devolve 422 com instrução acionável (M03).

Executado aqui: smoke informativo no `docker-entrypoint-easypanel-auto.sh`
(aviso, nunca bloqueio — spec §4.4 fase 0), que registra no log de deploy
qual dos dois modos o ambiente tem. Se algum dia o `.mpp` direto virar
requisito, a mudança é de uma linha no Dockerfile e o smoke já reporta.

## Runbook de rollout (operacional)

**Gate manual pós-deploy, em toda fase:** conferir que as migrations
207-211 estão `success` em `migration_history` — o entrypoint pode engolir
falha de migration quando `ENABLE_ROLLBACK` está desligado, então o log
verde do deploy não é prova.

| Fase | O que | Gate | Reversão |
|---|---|---|---|
| 0 — schema | Deploy com migrations 207-211 | `migration_history` 207-211 `success`; startup < 300s (backfill 210 comita por obra) | Migrations são aditivas — sem down |
| 1 — obra de teste | `flag_cronograma_mpp.py <admin> --ligar` só no tenant de homologação; importar `.mpp`/`.xml` real | Jornada completa na aba Cronograma + `verificar_consistencia_progresso.py` exit 0 + métricas §4.3 visíveis na lista | `--desligar` (sem perda de dados) |
| 2 — baias | Procedimento do M09 (`ESTADO_ATUALIZACAO_BAIA.md`): backup → `verificar_equivalencia_obra.py --salvar` → importar pela aba → `--comparar` | Equivalência `equivalente: true` | Divergiu ⇒ Restaurar versão pela aba; depois `--desligar` |
| 3 — geral | Flag ligada para os demais tenants; doc de usuário | 2 semanas sem drift | `--desligar` por tenant |

Depois da fase 3 estável: PR de descontinuação (M09 §4.3) e remoção da
dupla escrita legada (M07 §13).

## Dívidas registradas (não executadas aqui)

1. **Dupla escrita legada do M07** — `cronograma_apontamento_service` grava
   os campos legados junto com os semânticos, por desenho (reversibilidade).
   Remover só após a fase 3 estável.
2. **Inventário de descontinuação do M09 §4.3** — scripts/artefatos das
   baias; pós-estabilidade, critério global 16.
3. **Entrypoints Docker divergentes** — só
   `docker-entrypoint-easypanel-auto.sh` roda migrations; os demais
   divergem. Fora de escopo da spec (§5), mas é armadilha de deploy.
4. **Bypasses legados de `decorators.py`** — `admin_required`/`login_required`
   liberam tudo em desenvolvimento. As rotas do cronograma usam o decorator
   real do M01 e `test_cronograma_import_decorator.py::test_decorators_legados_intactos`
   falha se alguém mexer neles; o saneamento em si é de outro módulo.
5. **Gate completo antes de cada fecho** — dívida de PROCESSO, e a mais
   cara deste plano: os fechos M06-M09 declararam verde sem rodar
   `--gate` até o fim (ele leva ~36 min nesta suíte, quase toda de
   integração contra PostgreSQL real). Duas famílias ficaram vermelhas por
   quatro módulos. Nenhum fecho de módulo deveria ser aceito sem a linha
   final do `--gate` colada no documento.
6. **Métricas com dois nomes** — a aplicação grava `matching_por_nivel` e
   `decisoes_manuais` (M05/M06); a reconciliação grava `matches_por_nivel`
   e a consolidação expõe `n_manuais` (nomes da spec §4.3). Não renomeamos
   as chaves antigas para não quebrar eventos já gravados; a tradução vive
   em `metricas_da_importacao`.

## Pendências operacionais (fora deste ambiente)

1. Executar as fases 0-3 conforme o runbook.
2. Playwright da jornada em homologação antes de cada fase (a jornada
   genérica já é coberta por `test_cronograma_importacao_obra_playwright.py`).
3. Após 2 semanas estáveis: PRs de descontinuação (dívidas 1 e 2).
