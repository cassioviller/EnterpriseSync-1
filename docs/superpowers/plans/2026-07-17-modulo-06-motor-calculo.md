# Módulo 6 — Motor de Cálculo e Recálculo da Obra

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`.

## 1. Objetivo

Fazer de `utils/cronograma_engine.py` a fonte única de percentual planejado, realizado, incremento, rollup e progresso geral — consumida por cronograma, RDO, detalhes da obra, portal e medições-avanço — e adicionar o replanejamento determinístico usado na aplicação de versões (M5), preservando os comportamentos corretos já travados por teste.

## 2. Estado atual encontrado no código

Fonte "V2" correta e já consumida por: header do cronograma (`cronograma_views.py:238`), portal (`portal_obras_views.py:105-107`), curva de avanço (`views/obras.py:2614`), card/lista de RDO (`views/rdo.py:200`, `crud_rdo_completo.py:118`), PDF (`services/rdo_pdf_service.py:186`). Funções: `calcular_progresso_rdo` (`utils/cronograma_engine.py:368`), `calcular_progresso_geral_obra_v2` (`:457`), `sincronizar_percentuais_obra` (`:140`), `recalcular_cronograma` (`:237`), `atualizar_percentual_tarefa` (`:556`).

Caminhos divergentes a convergir:
- **B** — KPI de detalhes da obra: média simples das subatividades do último RDO (`views/obras.py:1694-1710`, "FÓRMULA SIMPLES").
- **C** — fallback V1 por subatividades quando a obra não tem `TarefaCronograma` (`views/rdo.py:207-224`, `crud_rdo_completo.py:125-128`) — legítimo para obras sem cronograma; mantido como fallback documentado.
- **D** — `calcular_progresso_real_servico` (`views/obras.py:652`, AVG SQL cru por serviço).
- **E** — medições por peso comercial (`services/medicao_service.py:48/207`) — número financeiro, conceito distinto; não converge, mas passa a ler `percentual_concluido` sincronizado pelo engine (já faz).
- Rollup duplicado on-the-fly em `cronograma_views.py:913-934`; `_atualizar_percentual_com_subempreitada` (`cronograma_views.py:1099`) como caminho alternativo somando `RDOApontamentoCronograma`+`RDOSubempreitadaApontamento` sem fallback percentual.

Regras vigentes (a preservar): peso do agregado = quantidade **somente se todas as folhas têm** (`usar_qtd = all(...)`, `:523` — proteção contra mistura de unidades), senão duração, senão 1; rollup de pais por duração; folhas `responsavel='terceiros'` puladas no sync (`:203`); planejado linear por dias úteis; sem datas/duração → planejado `None` ("Sem plano", `:405-408`); pais excluídos do agregado (`:501-503`).

Lacunas: marcos (`duracao_dias=0`) caem em peso=1 e planejado None sem tratamento explícito; `usar_qtd=True` não valida unidade homogênea; nenhum replanejamento de curvas ao mudar datas; tarefas arquivadas (M5) desconhecidas.

## 3. Problemas atuais

1. Números diferentes em telas diferentes (B/D vs A).
2. Sem replanejamento: `RDOApontamentoCronograma.percentual_planejado` é snapshot do momento do RDO e fica órfão quando as datas mudam.
3. Sem semântica para tarefas arquivadas/histórico não reconciliado.
4. Marcos e unidades mistas sem regra documentada.

## 4. Escopo

### 4.1 Consolidação (comportamento novo mínimo)

- `views/obras.py:1694-1719`: KPI passa a usar `calcular_progresso_geral_obra_v2` quando a obra tem cronograma (mesma bifurcação já usada em `crud_rdo_completo.py:102-108`); fallback C mantido para obras sem cronograma.
- `cronograma_views.py:tarefas_rdo:913-934`: substituir o rollup duplicado por função nova do engine `rollup_realizado(tarefas, percentuais) -> dict` (mesma fórmula, um só lugar).
- `_atualizar_percentual_com_subempreitada`: mover para o engine como parte de `atualizar_percentual_tarefa` (soma subempreitada quando existir), eliminando o caminho alternativo.
- **D** (`calcular_progresso_real_servico`) permanece para o contexto "por serviço" mas ganha teste de caracterização e comentário de escopo (não é progresso da obra).

### 4.2 Regras novas determinísticas (documentadas em docstring e testadas)

- **Marcos** (`is_marco` — M2): peso 0 no agregado; planejado = 0% antes de `data_inicio`, 100% a partir dela; realizado = 0 ou 100 (apontamento binário — M7).
- **Unidades**: `usar_qtd=True` exige adicionalmente `len({unidade_medida das folhas}) == 1`; caso contrário duração (formaliza a proteção existente; nunca soma m+un+dias).
- **Tarefas de terceiros**: continuam manuais (comportamento atual preservado); entram no agregado pelo `percentual_concluido` manual.
- **Tarefas sem datas**: planejado None; entram no agregado planejado como 0 (atual, preservado) — aviso na UI via M8.
- **Tarefas arquivadas (M5)**: excluídas do planejado futuro; **incluídas** no realizado histórico para datas ≤ `arquivada_em` (curva de avanço não "perde" trabalho feito); função `calcular_progresso_geral_obra_v2` ganha parâmetro interno para isso (assinatura pública inalterada).
- **Duração zero não-marco**: tratada como marco para peso/planejado (com aviso do M4).

### 4.3 Replanejamento (chamado pela aplicação de versão — M5)

Novo `replanejar_curvas_obra(obra_id, admin_id)`:
1. Para cada RDO da obra (ordem cronológica) e cada apontamento: recalcular `percentual_planejado` com as datas vigentes (`calcular_progresso_rdo(t, data_rdo)`), preservando **intocados** `quantidade_executada_dia`, `quantidade_acumulada`, `percentual_realizado`, `percentual_acumulado` (críterios: recalcular planejado ✓, preservar realizado ✓).
2. Rollup dos pais e sync (`sincronizar_percentuais_obra`).
3. Retornar relatório `{apontamentos_replanejados, tarefas_sem_historico_reconciliado: [ids arquivados com apontamentos], progresso_antes, progresso_depois}` — gravado no evento `aplicado` (M5).

## 5. Fora de escopo

Peso financeiro no progresso físico (medições continuam domínio próprio); múltiplas predecessoras/tipos SS-FF-SF e lag no motor de datas (`recalcular_cronograma` continua FS simples — os dados ficam preservados no snapshot/JSON para evolução futura; documentado como limitação); curva planejada persistida (continua derivada — determinística e barata); mudanças de UI.

## 6. Arquivos atuais envolvidos

`utils/cronograma_engine.py`, `cronograma_views.py` (`tarefas_rdo`, `_atualizar_percentual_com_subempreitada`, `apontar_producao`), `views/obras.py` (KPI :1694, `calcular_progresso_real_servico` :652, `curva_avanco_obra` ~:2594), `views/rdo.py` / `crud_rdo_completo.py` (bifurcação V1/V2 — não muda), `services/medicao_service.py` (não muda), `portal_obras_views.py` (não muda).

## 7. Arquivos novos ou alterados previstos

Alterados: `utils/cronograma_engine.py` (+`rollup_realizado`, +`replanejar_curvas_obra`, regras §4.2), `cronograma_views.py`, `views/obras.py`. Novos testes: `tests/test_cronograma_engine_unificado.py`, `tests/test_replanejamento.py`.

## 8. Alterações de banco

Nenhuma (usa `is_marco`/`ativa` do M2; atualiza valores de `percentual_planejado` existentes no replanejamento).

## 9. Serviços e responsabilidades

Engine = único dono das fórmulas. Views nunca implementam fórmula; medição usa `percentual_concluido` sincronizado; regra escrita no topo do engine como contrato.

## 10. Rotas e contratos de API

Nenhuma rota nova. Contratos internos: `rollup_realizado`, `replanejar_curvas_obra` (§4).

## 11. Fluxo de frontend

Única mudança visível: KPI de detalhes da obra passa a bater com header/portal/RDO (pode mudar o número exibido — comunicar no rollout M10).

## 12. Regras de negócio

Tabela normativa (docstring do engine):

| Caso | Peso agregado | Planejado | Realizado |
|---|---|---|---|
| Folha quantitativa (todas qtd + mesma unidade) | quantidade | linear dias úteis | Σqtd_dia/total |
| Folha sem qtd (ou mix) | duração (>0) senão 1 | linear | último acumulado percentual |
| Pai/resumo | excluído (rollup por duração) | rollup | rollup |
| Marco | 0 | degrau na data | 0/100 |
| Terceiros | igual às demais | linear | manual |
| Sem datas | duração/1 | None (agrega 0) | normal |
| Arquivada | 0 no futuro | 0 no futuro | mantido p/ datas ≤ arquivamento |

## 13. Estratégia de migração

Replanejamento roda apenas quando uma versão é aplicada (M5) — sem migração de dados própria. A convergência do KPI B é mudança de exibição, atrás da mesma flag de rollout do M10 se quisermos prudência (decisão de rollout, não de arquitetura).

## 14. Compatibilidade

Testes existentes que travam o V2 (`test_cronograma_header_usa_progresso_v2` `:766`, `test_portal_cliente_usa_progresso_v2` `:829`, `test_progresso_geral_obra_cresce_por_data` `:749`, `test_calcular_progresso_rdo_fallback_sem_quantidade_total` `:723` etc.) devem permanecer verdes sem edição.

## 15. Segurança

Sem superfície nova.

## 16. Observabilidade

Relatório do replanejamento persistido em evento; log de divergência: job/manage-command simples `verificar_consistencia_progresso(obra_id)` compara persistido×recalculado e loga drift (ferramenta de suporte).

## 17. Testes

- Caracterização de B e D antes de mudar.
- Unit por linha da tabela §12 (incl. marco, unidade mista → peso duração, arquivada antes/depois).
- Replanejamento: obra com 3 RDOs → mudar datas → planejado recalculado por data de RDO, realizado byte-idêntico; pais e progresso geral recalculados; relatório correto.
- Convergência: número idêntico em header, KPI detalhes, card RDO, portal e curva para a fixture das baias (teste de igualdade entre as 5 fontes).
- Propriedade: progresso geral monotônico não-decrescente por data com apontamentos não-negativos (já existe `test_progresso_geral_obra_cresce_por_data` — estender para pós-replanejamento).

## 18. Critérios de aceite

Critérios globais 9, 10, 11, 18: planejado recalculado, realizado intocado, mesmo número nas 4 telas + portal, tudo determinístico e testado.

## 19. Riscos

- Mudança do KPI B altera número que o usuário via (era errado, mas visível) → comunicar; flag se necessário.
- Replanejamento em obra com muitos RDOs (N_rdos×N_tarefas) → batch por query única de apontamentos, mesmo padrão do sync em lote (`sincronizar_percentuais_obra:166-195`).
- Incluir arquivadas no histórico pode surpreender consultas existentes → parâmetro explícito, default preserva comportamento atual exceto onde M5 pede.

## 20. Dependências

M2 (`is_marco`, `ativa`); M1 (serviço de apontamento único). M5 depende deste módulo.

## 21. Ordem detalhada de implementação

1. Testes de caracterização (B, D, rollup duplicado). 2. Regras §4.2 no engine (TDD por linha da tabela). 3. `rollup_realizado` + substituição em `tarefas_rdo`. 4. Mover subempreitada para o engine. 5. Convergir KPI B. 6. `replanejar_curvas_obra` (TDD). 7. Teste de convergência 5-fontes. 8. Suíte completa. Commits por passo.

## 22. Checklist de conclusão

- [ ] Tabela normativa implementada e testada caso a caso
- [ ] Rollup e subempreitada só no engine
- [ ] KPI de detalhes convergido
- [ ] Replanejamento preserva realizado (teste byte-a-byte)
- [ ] Igualdade entre as 5 fontes provada
- [ ] Suíte `--gate` verde sem editar os testes V2 existentes
