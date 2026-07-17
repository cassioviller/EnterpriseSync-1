# Módulo 5 — Reconciliação e Versionamento do Cronograma

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`. Matching 100% determinístico (D1); ambiguidade sempre vai a revisão manual.

## 1. Objetivo

Comparar o cronograma ativo da obra com o JSON normalizado (M4), classificar as diferenças, permitir revisão manual, e aplicar a nova versão em transação única — preservando todos os RDOs, apontamentos, fotos, medições, custos e histórico, com rollback por snapshot.

## 2. Estado atual encontrado no código

- Atualização de cronograma hoje = destruição: `_limpar_derivados` deleta `TarefaCronograma` (`services/importacao_fisico_financeiro.py:174`) e `_materializar_rdos` recria RDOs (`:423-459`); ids trocam; `tid_to_db` (`:182-223`) remapeia só dentro do próprio import; `REMAP` hardcoded no rebuild script (`scripts/rebuild_baia_from_0607_mpp.py:92`) faz o "matching" manualmente entre versões de `.mpp`.
- FKs que morrem com DELETE de tarefa (CASCADE): `RDOApontamentoCronograma` (`models.py:4954`), `RDOSubempreitadaApontamento` (`:5568`), `ItemMedicaoCronogramaTarefa` (`:5251`); SET NULL: `RDOMaoObra` (`:929`), filhas/predecessoras (`:4874/:4880`).
- Precedente de remapeamento seguro no repo: `scripts/dedupe_tarefa_cronograma.py` (Task #144) reaponta apontamentos e relações pai/predecessora — referência de código para o aplicador.
- Não há comparação/preview em lugar nenhum.

## 3. Problemas atuais

Importar nova versão numa obra com RDOs criados pela UI destruiria o histórico (o fluxo baias só sobrevive porque os RDOs vêm no mesmo JSON). Matching entre versões é manual e hardcoded.

## 4. Escopo

### 4.1 Reconciliação — `services/cronograma_reconciliacao.py` (puro, sem commit)

`reconciliar(tarefas_atuais: list[TarefaCronograma], normalizado: dict) -> RelatorioDiff`

Cascata determinística de matching (na ordem; primeiro match vence; cada nível só considera não-casados):

1. `mpp_uid` (coluna do M2, backfilled a partir da 1ª importação nova) == `uid` do arquivo.
2. `wbs_codigo` == `wbs` (exato).
3. Caminho hierárquico completo normalizado (igualdade exata).
4. Nome normalizado único nos dois lados (igualdade exata; se duplicado em qualquer lado → pula para 7).
5. Fingerprint (M4) — cobre pai+nome+duração+quantidade.
6. Similaridade composta determinística: `score = 0.5*difflib.SequenceMatcher(nome_norm).ratio() + 0.2*(mesmo pai) + 0.15*(sobreposição de datas) + 0.1*(mesma duração ±1d) + 0.05*(mesmas predecessoras)`. `score ≥ 0.85` e único candidato acima de 0.85 → `correspondencia_provavel`; dois candidatos ≥0.85 ou top entre 0.60-0.85 → `ambigua`.
7. Resto: lado novo → `nova`; lado atual → `removida`; ambíguos → `revisao_manual`.

Classificações adicionais sobre pares casados (cumulativas, uma linha de mapeamento por rótulo — M2): `renomeada` (casou por 1-3/5-6 com nome diferente), `movida_hierarquia`, `datas_alteradas`, `duracao_alterada`, `predecessoras_alteradas`, `quantidade_alterada`, `unidade_alterada`.

Split/merge (detecção assistida, decisão sempre manual):
- **Divisão** (1 antiga → N novas, ex.: "GABARITO" → "GABARITO GALPÃO A"/"GALPÃO B", padrão real do PR #13): tarefa `removida` cujo nome normalizado é prefixo/subconjunto de ≥2 tarefas `novas` sob o mesmo pai → sugerir grupo `dividida`; ao confirmar: a tarefa antiga é arquivada (`ativa=False`), as novas criadas, mapeamento 1:N gravado. O histórico de apontamentos permanece na tarefa antiga arquivada; o realizado dela é preservado no rollup histórico (M6 lê arquivadas para datas ≤ arquivamento). Não se tenta ratear quantitativo antigo entre as novas automaticamente.
- **Fusão** (N antigas → 1 nova): espelho do anterior; as antigas são arquivadas, mapeamento N:1; a nova nasce com realizado inicial derivado **apenas** se todas as antigas eram quantitativas com mesma unidade (soma dos acumulados); caso contrário nasce sem realizado e o histórico fica nas arquivadas (aviso na prévia).

Regra dura: **nenhum mapeamento `ambigua`/`revisao_manual`/`dividida`/`fundida` é aplicado sem decisão manual registrada** (`origem_decisao='manual'`, `decidido_por_id`).

### 4.2 Aplicação — `services/cronograma_versao_service.py`

`aplicar_versao(importacao_id, decisoes, usuario_id) -> CronogramaVersao` — transação única:

1. Validar: importação `aguardando_revisao`; zero pendências sem decisão; obra trancada (SELECT FOR UPDATE na obra) contra aplicação concorrente.
2. Snapshot integral da versão ativa atual (se ainda não snapshotada) — `cronograma_tarefa_snapshot`.
3. Executar mapeamentos: casadas → UPDATE in-place (nome, datas, duração, hierarquia via `tarefa_pai_id`, `predecessora_id` (primeira FS; demais ficam no snapshot/JSON), `quantidade_total`, `unidade_medida`, `wbs_codigo`, `mpp_uid`, `is_marco`, `ordem`); novas → INSERT (`versao_criacao_id`); removidas/divididas/fundidas → `ativa=False, arquivada_em=now()` (**nunca DELETE**).
4. Carga inicial de realizado pelo `pct_project`: somente se a obra não tem nenhum RDO (regra do master §2.4).
5. Criar `CronogramaVersao` nova `ativa`; anterior → `arquivada`; snapshot da nova.
6. Recalcular (M6): `recalcular_cronograma` + `sincronizar_percentuais_obra` + replanejamento das curvas por data de RDO; gravar antes/depois no evento `aplicado` (progresso geral, nº tarefas, tarefas com histórico não reconciliado).
7. Commit único; qualquer exceção → rollback total (obra intacta — critérios globais 12/13).

`restaurar_versao(versao_id, usuario_id)`: reconstrói o estado das tarefas a partir do snapshot da versão alvo (UPDATE nas vivas, reativação de arquivadas, arquivamento das criadas depois), nova `CronogramaVersao` com `observacao='rollback da vN'`, mesmo recálculo. Propriedade testada: aplicar vN+1 e restaurar vN ⇒ tarefas idênticas ao snapshot de vN.

Reimportação do mesmo arquivo: barrada por hash no M3 (409). Importação de arquivo corrigido: novo hash → pipeline normal; matching por uid tende a 100% exato.

## 5. Fora de escopo

UI da prévia (M8 — este módulo expõe o `RelatorioDiff` como JSON); replanejamento fino das curvas (M6); múltiplas predecessoras no motor de datas (M6 §5); alterações no importador físico-financeiro (M9).

## 6. Arquivos atuais envolvidos

`models.py` (tarefas/apontamentos/medições — leitura), `utils/cronograma_engine.py` (chamado ao final), `services/importacao_fisico_financeiro.py` (não alterado), `scripts/dedupe_tarefa_cronograma.py` (referência de remapeamento).

## 7. Arquivos novos ou alterados previstos

Novos: `services/cronograma_reconciliacao.py`, `services/cronograma_versao_service.py`, `tests/test_cronograma_reconciliacao.py`, `tests/test_cronograma_versao_service.py`. Alterado: `views/cronograma_importacao.py` (M3) ganha os endpoints §10.

## 8. Alterações de banco

Nenhuma nova (usa M2). Escritas: mapeamentos, snapshots, versões, eventos, updates em `tarefa_cronograma`.

## 9. Serviços e responsabilidades

| Serviço | Responsabilidade |
|---|---|
| `cronograma_reconciliacao` | Diff puro e determinístico; nunca escreve |
| `cronograma_versao_service` | Aplicação transacional, arquivamento, rollback, recálculo, auditoria |

## 10. Rotas e contratos de API

- `POST /obras/<id>/cronograma/importacoes/<iid>/reconciliar` → grava `relatorio_diff` + mapeamentos `auto`, status `aguardando_revisao`; retorna resumo `{exatas, provaveis, novas, removidas, ambiguas, revisao_manual, alteracoes:{datas, duracao, ...}}`.
- `GET /obras/<id>/cronograma/importacoes/<iid>/diff` → `RelatorioDiff` completo (consumido pela UI M8).
- `PATCH /obras/<id>/cronograma/importacoes/<iid>/mapeamentos/<mid>` → decisão manual `{acao: confirmar|rejeitar|vincular_a: tarefa_id|marcar_nova|marcar_dividida:[...]}`.
- `POST /obras/<id>/cronograma/importacoes/<iid>/aplicar` → aplica (422 se pendências).
- `POST /obras/<id>/cronograma/versoes/<vid>/restaurar` → rollback.
Todas com decorator de autorização (M1) e tenant-scope.

## 11. Fluxo de frontend

Ver M8 (prévia, filtros, edição de mapeamento, aplicar, restaurar).

## 12. Regras de negócio

- Histórico nunca desaparece: DELETE de `tarefa_cronograma` é proibido no serviço (assert em código + teste).
- Tarefa arquivada com apontamentos aparece no relatório final como "histórico não reconciliado" quando não mapeada (critério do replanejamento — informa, não bloqueia).
- `percentual_concluido` de tarefa casada **não** é sobrescrito pelo arquivo (realizado vem do RDO; exceção única: carga inicial sem RDO).
- Aplicações concorrentes na mesma obra: a segunda falha limpa (lock).

## 13. Estratégia de migração

Primeira importação nova numa obra pré-existente: nenhuma tarefa tem `mpp_uid` ⇒ cascata cai para caminhos 3-6 + revisão manual; após aplicar, uids ficam gravados e as próximas importações casam por uid. Para as baias, o M9 prepara um mapeamento assistido.

## 14. Compatibilidade

Fluxo antigo (import físico-financeiro destrutivo) permanece válido para criação inicial; o serviço novo se recusa a rodar em importação de origem física-financeira (separação de casos de uso do M1).

## 15. Segurança

Decisões manuais auditadas (usuário/data); lock por obra; validação de que toda tarefa referenciada pertence à obra/tenant.

## 16. Observabilidade

Evento `aplicado` com antes/depois; contadores de matching por nível da cascata (quantos casaram por uid/wbs/caminho/nome/fingerprint/score) — métrica-chave do M10.

## 17. Testes

- Unit da cascata: um cenário por nível (uid, wbs, caminho, nome único, fingerprint, score alto único, ambíguo, novo, removido) + cumulativos (renomeada+datas_alteradas).
- Split/merge: cenário GABARITO→A/B real (extraído do diff 16.06→06.07 das baias) detecta sugestão `dividida`; fusão espelho; nunca auto-aplica.
- Aplicação: obra com RDOs criados via UI → aplicar versão com datas novas → **todos** os `RDOApontamentoCronograma`/fotos/medições intactos (contagem e valores); ids de tarefas casadas inalterados.
- Transacionalidade: exceção injetada no meio da aplicação → obra byte-idêntica (snapshot compare).
- Rollback: aplicar → restaurar ⇒ igualdade com snapshot anterior (propriedade).
- Concorrência: duas aplicações simultâneas → uma falha limpa.
- Idempotência de hash (M3) + reimport corrigido casa 100% por uid.
- Multitenant: reconciliação nunca enxerga tarefas de outro tenant.

## 18. Critérios de aceite

Critérios globais 3, 4, 5, 12, 13, 14, 15 verificados por teste automatizado; ambíguo jamais aplicado sem decisão manual (teste negativo).

## 19. Riscos

- Falso-positivo no nível 6 (score) → threshold conservador 0.85 + unicidade exigida + rótulo `provavel` destacado na prévia (usuário pode rejeitar).
- Snapshot/rollback divergirem do estado real por campo esquecido → teste de propriedade round-trip cobre todos os campos do modelo (reflexão sobre colunas).
- Obras gigantes (milhares de tarefas): cascata é O(n²) no pior caso do nível 6 → indexar por pai e só comparar dentro do mesmo pai/nível; limite documentado.

## 20. Dependências

M2 (schema), M3 (importação/json), M4 (normalizado/fingerprint), M6 (recálculo — ordem de execução: M6 antes de M5, ver master §4).

## 21. Ordem detalhada de implementação

1. `RelatorioDiff` dataclasses + testes da cascata nível a nível (TDD). 2. Classificações cumulativas. 3. Detector de split/merge + testes com caso real das baias. 4. Endpoints reconciliar/diff/decisão. 5. `aplicar_versao` incremental: (a) snapshot, (b) updates/inserts/arquivamento, (c) recálculo, (d) eventos — teste de preservação total após cada passo. 6. Transacionalidade (exceção injetada). 7. `restaurar_versao` + round-trip. 8. Lock de concorrência. 9. Suíte completa. Commits por passo.

## 22. Checklist de conclusão

- [ ] Cascata determinística coberta nível a nível
- [ ] Ambíguo nunca auto-aplicado (teste)
- [ ] Aplicação transacional com preservação total de RDOs/fotos/medições
- [ ] Rollback round-trip verde
- [ ] Split/merge assistidos e manuais
- [ ] Eventos de auditoria completos
- [ ] Suíte `--gate` verde
