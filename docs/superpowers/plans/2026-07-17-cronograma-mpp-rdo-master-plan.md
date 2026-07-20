# Plano Mestre — Cronograma .mpp por Obra + RDO Quantitativo/Percentual (100% determinístico, sem API externa)

> **Para agentes executores:** este é o documento mestre. A implementação segue os 10 planos modulares `2026-07-17-modulo-NN-*.md` nesta pasta, na ordem definida na seção "Ordem de implementação". Use superpowers:subagent-driven-development ou superpowers:executing-plans por módulo.

**Objetivo:** transformar o fluxo de importação físico-financeira usado no piloto das baias em uma funcionalidade genérica por obra: upload de `.mpp` dentro da obra → parser local determinístico → normalização determinística → prévia de diferenças → aplicação transacional versionada — preservando RDOs, fotos, medições, custos e histórico.

**Decisão de escopo (pedido do usuário em 2026-07-17):** **nenhuma API externa (Claude/LLM) faz parte do plano.** Toda normalização, classificação e reconciliação é determinística e testável no backend, com revisão manual na prévia para casos ambíguos. Fica documentado apenas um ponto de extensão opcional futuro (seção "Extensão futura opcional"), fora do caminho crítico.

---

## 1. Diagnóstico do estado atual

Consolidado de 5 análises somente-leitura (arquitetura/dados, parser/importação, cálculos, RDO/UX, testes/deploy). Referências verificadas no código.

### 1.1 Importação e cronograma

- A app **não lê `.mpp`**. O parser existe só como ferramenta manual de dev: `scripts/dump_mpp.py` (MPXJ + JPype + JVM; exige JDK completo por causa do charset MacRoman). MPXJ/JPype/JDK **não estão declarados** em `pyproject.toml`, `uv.lock`, `replit.nix` nem nos Dockerfiles — **produção não parseia `.mpp`**.
- O fluxo real das baias: dev roda `scripts/rebuild_baia_from_0607_mpp.py` (caminhos e regras hardcoded: `CRONOGRAMA 06.07.mpp`, `origin/main`, classificador `etapa_de()` por palavra-chave, `REMAP={3:2,4:3,6:5,9:7,15:...}` de ids de apontamento) → gera `cronograma_fisico_financeiro_baias.json` → upload em `/importacao/fisico-financeiro` (`importacao_views.py:1023`, `importar_fisico_financeiro_view`) → `services/importacao_fisico_financeiro.py:552` `importar_fisico_financeiro(payload, admin_id)`.
- A importação é **destrutiva por design** ("idempotência por sobrescrita"): `_limpar_derivados` (`services/importacao_fisico_financeiro.py:141`) apaga `PropostaItem`, `Proposta`, `OrcamentoItem`, `Orcamento`, `ItemMedicaoCronogramaTarefa`, `ObraServicoCustoItem`, `ObraServicoCusto`, `ItemMedicaoComercial`, **`TarefaCronograma`** e `MedicaoContrato`; `_materializar_rdos` (`:423`) apaga e recria todos os RDOs da obra (fotos preservadas por snapshot base64 em `_snapshot_fotos_por_data`, `:398`).
- **Ids de `TarefaCronograma` mudam a cada import.** Vínculos que dependem desses ids: `RDOApontamentoCronograma.tarefa_cronograma_id` (CASCADE, `models.py:4954`), `RDOSubempreitadaApontamento.tarefa_cronograma_id` (CASCADE, `models.py:5568`), `RDOMaoObra.tarefa_cronograma_id` (SET NULL, `models.py:929`), `ItemMedicaoCronogramaTarefa.cronograma_tarefa_id` (CASCADE, `models.py:5251`). Hoje isso só funciona porque o import recria os RDOs juntos (via `tid_to_db` de `_materializar_cronograma_mpp`, `:182`) — **inaceitável para obras com RDOs criados pela UI**.
- Não existe: versão de cronograma, histórico de importação, hash de arquivo, baseline/curva planejada persistida, campo UID/WBS na tarefa, marco (`is_marco`), tipo de vínculo/lag de predecessora (só `predecessora_id` FS único).
- A rota de upload não valida schema, extensão, tamanho, não usa `secure_filename`, não armazena o arquivo e não tem idempotência por hash.

### 1.2 Cálculo de progresso

- Motor "V2": `utils/cronograma_engine.py` — `calcular_progresso_rdo` (`:368`, planejado = interpolação linear por dias úteis; realizado = Σ`quantidade_executada_dia` até a data, com fallback percentual), `calcular_progresso_geral_obra_v2` (`:457`, média das folhas ponderada por quantidade **somente se todas têm** senão duração senão 1), `sincronizar_percentuais_obra` (`:140`, rollup de pais por duração), `recalcular_cronograma` (`:237`, datas topológicas FS).
- **O mesmo número é calculado por ≥5 caminhos** que podem divergir: (A) engine V2 — usado por header do cronograma (`cronograma_views.py:238`), portal (`portal_obras_views.py:105-107`), curva de avanço (`views/obras.py:2614`), card RDO; (B) KPI legado de detalhes da obra — média simples das subatividades do **último RDO** (`views/obras.py:1694-1710`); (C) fallback V1 por subatividades (`views/rdo.py:207-224`, `crud_rdo_completo.py:125-128`); (D) `calcular_progresso_real_servico` (`views/obras.py:652`); (E) medições por peso comercial (`services/medicao_service.py:48,207`).
- Lógica de apontamento (acumulado anterior + incremento → percentual) **duplicada** em `views/rdo.py:4556-4609` e `cronograma_views.py:1134-1217`; rollup de pais duplicado em `cronograma_views.py:913-934`.
- Planejado é **volátil**: recalculado das datas atuais das tarefas; nenhuma baseline congelada.

### 1.3 RDO

- Dois mecanismos paralelos no mesmo formulário: subatividades percentuais (`RDOServicoSubatividade`, valor digitado = **acumulado**, gravado direto em `percentual_conclusao`, `views/rdo.py:4243`; `percentual_anterior`/`incremento_dia` **não são preenchidos** na gravação, só derivados na leitura) e tarefas do cronograma quantitativas (`RDOApontamentoCronograma`, valor digitado = **incremento do dia**, `views/rdo.py:4584`).
- Não existe `tipo_apontamento`; o modo é implícito por `TarefaCronograma.quantidade_total > 0`. Tarefas sem quantitativo **não têm campo de entrada** no Novo RDO (`templates/rdo/novo.html:1111`) — só recebem percentual via import.
- Sem validação de retrocesso, sem trava >100% no caminho percentual, sem recomputo de acumulados persistidos quando um RDO retroativo é inserido/corrigido (a leitura recalcula certo, mas o persistido fica defasado).
- Três handlers de gravação redundantes: `salvar_rdo_flexivel` (`views/rdo.py:3849`, principal, em `/salvar-rdo-flexivel`), `rdo_salvar_unificado` (`views/rdo.py:2511`, legado, em `/rdo/salvar`) e `crud_rdo_completo.salvar_rdo` (`:230`, legado). Os dois últimos **colidiam na mesma URL `/rdo/salvar`** — resolvido no Módulo 01 passo 5: `rdo_salvar_unificado` sempre venceu (ordem de registro `app.py:463` < `main.py:24`) e o registro de rota da perdedora foi removido. `salvar_rdo_flexivel` **não** colide: URL distinta.

### 1.4 Infra, testes e flags

- 46 testes de integração em `tests/test_importacao_fisico_financeiro.py` travam o comportamento atual (idempotência, RDOs no import, fotos, progresso V2 em header/raiz/portal, modo quantitativo e percentual, multitenant). Rodam contra PostgreSQL real via `run_tests.sh --gate`. Fixture canônica: symlink `tests/fixtures/cronograma_fisico_financeiro_baias.json` → raiz.
- Migrations: arquivo único `migrations.py` (última: 199), idempotentes via `migration_history` (`run_migration_safe`, `migrations.py:146`), executadas **no startup** (`pre_start.py` chamado por `docker-entrypoint-easypanel-auto.sh`).
- Feature flag existente = versão de sistema por tenant (`utils/tenant.py:is_v2_active`); não há flags por funcionalidade.
- Nenhuma integração LLM existe no código (verificado por grep). Toda a normalização atual já é determinística.

## 2. Arquitetura proposta

### 2.1 Princípios

1. **Determinismo total**: parser local (MPXJ), normalização por regras, matching por chaves estáveis + similaridade fuzzy da stdlib (`difflib.SequenceMatcher`), revisão manual para ambiguidade. Zero dependência de rede.
2. **Identidade estável de tarefa**: `TarefaCronograma` existente vira a entidade lógica estável (ids nunca são recriados em atualização de cronograma). Versões são **snapshots**, não linhas paralelas.
3. **Separação de casos de uso**: criação inicial de obra completa (importador físico-financeiro atual, intacto) ≠ atualização de cronograma (novo pipeline, não-destrutivo) ≠ RDO ≠ custos ≠ medições.
4. **Aplicação transacional com prévia obrigatória**: nada é gravado no cronograma ativo sem confirmação; commit único; rollback por restauração de snapshot.
5. **Motor de cálculo único**: todos os consumidores (cronograma, RDO, detalhes da obra, portal, medições-avanço) leem do engine V2 consolidado.

### 2.2 Decisão central: alternativas A/B/C

| | A — tarefas versionadas (linhas novas por versão) | B — atividade lógica + ocorrências por versão | C — identidade estável + camada de mapeamento |
|---|---|---|---|
| Integridade histórica | Alta (linhas antigas intactas) | Alta | Alta (linhas nunca deletadas; snapshot por versão) |
| Impacto nos RDOs | **Grave**: apontamentos apontam para linhas arquivadas; realizado precisa ser re-remapeado a cada versão | **Grave**: exige migrar TODAS as FKs (`RDOApontamentoCronograma`, `RDOSubempreitadaApontamento`, `RDOMaoObra`, `ItemMedicaoCronogramaTarefa`) para a nova entidade | **Nenhum**: FKs continuam válidas; tarefa correspondida mantém o id |
| Impacto no código existente | Todo `filter_by(obra_id)` sobre `TarefaCronograma` (dezenas de pontos em `cronograma_views.py`, `views/rdo.py`, engine, portal, medições) precisaria de filtro de versão — alto risco de regressão silenciosa | Reescrita ampla de queries e modelos | Pequeno: um filtro `ativa=True` apenas nas listagens; histórico continua enxergando tarefas arquivadas |
| Migração dos dados atuais | Backfill de versão em tudo | Criação de entidades lógicas + reapontamento de milhões de FKs | Backfill leve (colunas novas + snapshot v1) |
| Rollback de versão | Trocar ponteiro de versão (simples) | Trocar ponteiro (simples) | Restaurar snapshot (transacional, mais código, testável) |
| Risco com os 46 testes travados | Alto | Alto | Baixo |

**Escolha: C ampliada ("identidade estável + snapshots versionados + mapeamento")** — na prática é a Alternativa B com a própria `TarefaCronograma` fazendo o papel de atividade lógica, evitando a migração de FKs. Não é a mais simples por preguiça: é a que preserva integridade histórica (nenhuma FK de RDO/medição é tocada), dá rastreabilidade completa (snapshot integral de cada versão + tabela de mapeamento + trilha de eventos) e minimiza o raio de regressão sobre um código com muitos consumidores diretos de `TarefaCronograma`. As desvantagens (rollback por restauração em vez de troca de ponteiro; necessidade do flag `ativa`) são cobertas por testes dedicados no Módulo 5 e 10.

Semântica da atualização de cronograma (Módulo 5):
- Tarefa **correspondida** → UPDATE in-place (datas, duração, hierarquia, quantidade, unidade, wbs, uid) mantendo o id.
- Tarefa **nova** → INSERT.
- Tarefa **removida** → `ativa=False` + `arquivada_em` (nunca DELETE — CASCADE mataria apontamentos).
- Tarefa **dividida/fundida** → mapeamento N:M registrado; histórico permanece na(s) tarefa(s) antiga(s) arquivada(s) ou na sobrevivente, conforme regra do Módulo 5.
- Antes de aplicar, snapshot integral da versão corrente; aplicar = uma transação; rollback = restaurar snapshot.

### 2.3 Diagrama textual do fluxo

```
[Usuário na página da obra]
   │ upload .mpp (Módulo 8: UI)
   ▼
[Rota POST /obras/<id>/cronograma/importacoes]  (Módulo 3)
   │ valida extensão/MIME/tamanho → SHA-256 → dedup por hash
   │ grava arquivo + CronogramaImportacao(status=recebido)
   ▼
[services/mpp_parser.py — subprocess MPXJ/JPype com timeout]  (Módulo 3)
   │ .mpp → JSON BRUTO (uid, wbs, outline, nome, datas, duração,
   │        % project, predecessoras+tipo+lag, resumo, marco, recursos,
   │        quantidade/unidade de campos custom, notas)
   ▼
[services/cronograma_normalizacao.py — determinístico]  (Módulo 4)
   │ sanitização, normalização de nomes, fingerprints,
   │ classificação por regras, validações → JSON NORMALIZADO
   │ (validado por JSON Schema versionado)
   ▼
[services/cronograma_reconciliacao.py]  (Módulo 5)
   │ diff contra cronograma ativo da obra:
   │ exata | provável | nova | removida | renomeada | movida |
   │ datas/duração/predecessoras/quantidade/unidade alteradas |
   │ ambígua | revisão manual
   ▼
[Prévia na UI da obra]  (Módulo 8)
   │ usuário revisa, ajusta mapeamentos, confirma
   ▼
[Aplicação transacional]  (Módulo 5)
   │ snapshot da versão atual → UPDATE/INSERT/arquivar →
   │ nova CronogramaVersao ativa → remap de histórico se preciso
   ▼
[Recálculo]  (Módulos 6 e 7)
   │ recalcular_cronograma + sincronizar percentuais +
   │ replanejado por data de RDO (curva) — realizado intocado
   ▼
[Cronograma | RDO | Detalhes da obra | Portal]  — mesmo número (engine V2)
```

Contingência sem Java em produção: o mesmo pipeline aceita o **JSON bruto** gerado pelo CLI `scripts/dump_mpp.py` (que vira wrapper fino do serviço) — o restante do fluxo é idêntico.

### 2.4 Fontes da verdade

- `.mpp`: estrutura, hierarquia, datas, duração, predecessoras, quantidades planejadas → **planejado**.
- RDO (`RDOApontamentoCronograma` + subatividades): avanço físico → **realizado**. `% concluído` do `.mpp` só como carga inicial quando a obra não tem nenhum RDO; depois é ignorado (comportamento já vigente: `rebuild_baia_from_0607_mpp.py` zera `pct_fisico`; commit `13bca49`).
- Percentual planejado por data: recalculado deterministicamente pelo engine a cada versão; snapshot por apontamento (`percentual_planejado`) atualizado pelo replanejamento do Módulo 6.

## 3. Decisões principais

| # | Decisão | Justificativa |
|---|---|---|
| D1 | Sem API externa; núcleo determinístico | Pedido explícito; já não há LLM no código; matching fuzzy da stdlib + revisão manual cobrem o caso semântico |
| D2 | Alternativa C ampliada (identidade estável + snapshots) | Ver §2.2 |
| D3 | Parser MPXJ como serviço em subprocess; Java empacotado no Docker; CLI mantido | Isola JVM (crash/timeout), funciona em prod; contingência via JSON do CLI |
| D4 | Importador físico-financeiro atual permanece intacto para criação inicial | 46 testes travam o comportamento; baias continuam funcionando durante a migração |
| D5 | Novo pipeline é aditivo, atrás de flag por tenant (padrão `is_v2_active`) | Rollout seguro, começa em obra de teste |
| D6 | `tipo_apontamento` explícito + campos semânticos (`percentual_acumulado`, `percentual_incremento_dia`, snapshots de quantidade/unidade) em `RDOApontamentoCronograma` | Elimina ambiguidade acumulado×incremento e o uso de campos de quantidade para percentual |
| D7 | Motor único: caminhos B/C/D/E do diagnóstico convergem para o engine V2 | Mesmo número em todas as telas (critério de aceite 11) |
| D8 | Nenhum DELETE de tarefa em atualização de cronograma; arquivamento lógico | FKs CASCADE tornam DELETE destrutivo para RDOs/medições |
| D9 | Migrations seguem o padrão vigente (`run_migration_safe`, numeração ≥200, idempotentes) | Compatível com startup automático |

## 4. Dependências entre módulos e ordem de implementação

```
M1 (auditoria/refatoração) ──► M2 (modelo de dados) ──► M3 (parser/upload)
                                        │                      │
                                        ▼                      ▼
                              M5 (reconciliação) ◄── M4 (normalização determinística)
                                        │
                    ┌───────────────────┼────────────────┐
                    ▼                   ▼                ▼
              M6 (motor de cálculo)   M8 (UI da obra)  M7 (RDO)
                    │                   │                │
                    └───────────► M9 (migração baias) ◄──┘
                                        │
                                  M10 (testes/rollout — transversal, fecha o ciclo)
```

Ordem de execução: **M1 → M2 → M3 → M4 → M6 → M5 → M7 → M8 → M9 → M10**, com M10 também transversal (cada módulo entrega seus próprios testes; M10 consolida E2E, observabilidade e rollout). M6 antes de M5 porque a aplicação de versão precisa do replanejamento consolidado.

## 5. Estratégia de migração

1. Tudo aditivo primeiro: novas tabelas + novas colunas em `TarefaCronograma` e `RDOApontamentoCronograma` (nullable/backfill), zero mudança de comportamento.
2. Backfill: cronograma atual de cada obra vira `CronogramaVersao` nº 1 ativa (snapshot); apontamentos existentes ganham `tipo_apontamento` inferido (`quantidade_total > 0` → quantitativo; senão percentual) e snapshots de quantidade/unidade copiados da tarefa.
3. Novo pipeline habilitado por flag em obra de teste (tenant de homologação).
4. Baias migradas pelo Módulo 9 (import do `.mpp` vigente pelo novo fluxo, com verificação de equivalência: 101 tarefas, 19 RDOs, percentuais idênticos antes/depois).
5. Só depois de M9 verde + rollback testado: descontinuar `rebuild_baia_from_0607_mpp.py`, `REMAP`, symlinks e o caminho destrutivo de cronograma dentro do importador (o importador segue existindo para criação inicial).

## 6. Estratégia de rollout

- Fase 0: schema + backfill em produção (sem UI).
- Fase 1: flag ligada para tenant de teste; importação real de `.mpp` em obra sintética; conferência de métricas.
- Fase 2: flag para o tenant das baias; M9 executado; testes de equivalência.
- Fase 3: flag padrão ligada para novos tenants; documentação de usuário.
- Abort/rollback por fase: desligar flag (fases 1-3) não afeta dados; restaurar versão anterior cobre importações aplicadas.

## 7. Riscos gerais

| Risco | Severidade | Mitigação |
|---|---|---|
| Java/MPXJ em produção (imagem, memória JVM, charset) | Alta | Subprocess isolado + timeout; teste de fixture real no CI; contingência por JSON do CLI |
| Regressão nos 46 testes do import das baias | Alta | Importador atual intocado (D4); M9 só migra com equivalência provada |
| Matching errado aplicado silenciosamente | Alta | Ambíguo nunca auto-aplica; prévia obrigatória; trilha de auditoria |
| Drift entre valores persistidos e recalculados (RDO retroativo) | Média | Recomputo em cadeia do Módulo 7 + job de verificação |
| Migrations no startup com timeout 300s (backfill grande) | Média | Backfill em lotes idempotentes; migração separada do DDL |
| `decorators.py` com bypass de auth (dev) | Média | M8 exige autorização real nas rotas novas; apontado em M1 |
| Snapshot/rollback com bugs sutis | Média | Testes de propriedade (aplicar→rollback = identidade) no M5/M10 |

## 8. Definição global de pronto

Os 18 critérios de aceite do pedido, verificáveis por teste automatizado:

1. Duas obras com `.mpp` e cronogramas independentes (teste multitenant/multi-obra, M10).
2. Reimport do mesmo arquivo reconhecido por SHA-256 (M3).
3. Nova versão comparável antes de aplicar (M5/M8).
4. RDOs existentes nunca apagados por atualização de cronograma (M5).
5. Fotos e comentários seguem vinculados (M5/M9).
6. Tarefa quantitativa deriva percentual automaticamente (M7).
7. Tarefa sem quantitativo aceita percentual acumulado (M7).
8. Correção retroativa recalcula acumulados posteriores (M7).
9. Planejado recalculado pelas novas datas (M6).
10. Realizado permanece dos RDOs (M6).
11. Cronograma, RDO, detalhes e portal exibem o mesmo percentual (M6).
12. Falha em qualquer etapa do pipeline não deixa a obra parcialmente alterada (M5 — transação única; sem API externa, o modo de falha relevante é parser/validação, que ocorre antes de qualquer escrita no cronograma).
13. Aplicação de versão transacional (M5).
14. Restauração da versão anterior funciona (M5).
15. Toda alteração tem usuário, data e origem (`CronogramaImportacaoEvento`, M2).
16. Fluxo atual das baias funciona durante toda a migração (M9; suíte `--gate` verde em todos os passos).
17. Nenhuma regra específica de baia no núcleo genérico (M9 — inventário de descontinuação).
18. Todos os cálculos determinísticos e cobertos por testes (M6/M10).

## 9. Extensão futura opcional (fora deste plano)

Se um dia se quiser sugestão semântica assistida por LLM, o ponto de encaixe já fica definido: `services/cronograma_reconciliacao.py` expõe a etapa `sugerir_correspondencias(pendentes) -> list[Sugestao]`, cuja única implementação planejada é a determinística (fuzzy + regras). Uma implementação alternativa poderia propor pares para os itens `requer_revisao_manual` — sempre como sugestão a confirmar na prévia, nunca aplicada automaticamente. Nada no schema, nas rotas ou na UI depende disso.

## 10. Documentos do plano

1. `2026-07-17-modulo-01-auditoria-refatoracao-dominio.md`
2. `2026-07-17-modulo-02-modelo-dados-migrations.md`
3. `2026-07-17-modulo-03-upload-parser-mpp.md`
4. `2026-07-17-modulo-04-normalizacao-deterministica.md`
5. `2026-07-17-modulo-05-reconciliacao-versionamento.md`
6. `2026-07-17-modulo-06-motor-calculo.md`
7. `2026-07-17-modulo-07-rdo.md`
8. `2026-07-17-modulo-08-interface-obra.md`
9. `2026-07-17-modulo-09-migracao-baias.md`
10. `2026-07-17-modulo-10-testes-observabilidade-rollout.md`
