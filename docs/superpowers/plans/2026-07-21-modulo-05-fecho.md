# Módulo 05 — Reconciliação e Versionamento — Fecho

> Fecha o M05 conforme o plano `2026-07-20-modulo-05-implementacao-reconciliacao.md`
> (que reconcilia a spec `2026-07-17-modulo-05-reconciliacao-versionamento.md` com o
> modelo vivo). Em conflito, o plano bite-sized vence; as divergências de execução
> estão nas ressalvas abaixo.

## Entregue (commits nesta branch `feat/cronograma-mpp-m03-upload-parser`)

| Task | Commit | Conteúdo |
|---|---|---|
| 1 | `1d2870b` | `services/cronograma_reconciliacao.py` — reconciliação PURA por cascata §4.1 (7 níveis) + 26 testes |
| 2 | `2624bb7` | `services/cronograma_versao_service.py` — `aplicar_versao` transacional; filtro `ativa` em views + engine; 12 testes |
| 3 | `0b1d137` | `restaurar_versao` — rollback por snapshot com round-trip por reflexão; 3 testes |
| 4 | `e087674` | Endpoints reconciliar/diff/mapeamentos/aplicar/restaurar em `views/cronograma_importacao.py`; 6 testes |

## Critérios de aceite (§18/§22) — estado

- [x] **1. Cascata coberta nível a nível** — `test_cronograma_reconciliacao.py`:
      um cenário por nível (mpp_uid com uid 0 válido, wbs com ''→None, caminho
      antes de nome_unico, nome único com colisão pulada, fingerprint, score
      único ≥0.85, ambígua 2 altos e faixa média, resto novas/removidas/
      revisao_manual), cumulativos, determinismo bit a bit e independência da
      ordem de entrada.
- [x] **2. Ambíguo nunca auto-aplicado** — teste negativo em três camadas:
      serviço puro (`chave_nova=None` + `decisao_requerida=true`), aplicação
      (`PendenciasSemDecisao` com a lista de `id_temp`) e endpoint
      (`POST .../aplicar` → 422 com `pendencias`).
- [x] **3. Aplicação preserva 100% dos RDOs/medições** — casadas recebem
      UPDATE in-place (IDs intactos); `test_aplicar_preserva_ids_apontamentos_e_percentual`
      confere contagem e valores dos `RDOApontamentoCronograma` e que
      `percentual_concluido` continua vindo do apontamento, nunca do arquivo.
- [x] **4. Rollback round-trip verde** — aplicar vN+1 → restaurar vN ⇒ tarefas
      e a foto da nova versão idênticas ao snapshot de vN por **reflexão sobre
      as colunas** do `CronogramaTarefaSnapshot` (não lista manual de campos).
- [x] **5. Transacionalidade** — exceção injetada após updates/inserts/
      arquivamentos ⇒ obra byte-idêntica (comparação de todas as colunas),
      zero versões criadas, importação segue `aguardando_revisao`.
- [x] **6. Nenhum DELETE de tarefa_cronograma** — arquivamento lógico
      (`ativa=False, arquivada_em`) + assert anti-DELETE em código (contagem
      total antes/depois) nos dois serviços, coberto por teste em aplicar e
      restaurar.
- [x] **7. Concorrência: 2ª aplicação falha limpa** — `SELECT FOR UPDATE` na
      obra + revalidação do status após o lock; teste sequencial garante
      `EstadoInvalido` e exatamente 1 versão ativa. **Ressalva:** teste com
      duas sessões Postgres simultâneas de verdade não roda neste ambiente
      (DB serverless, cold start) — o caminho do lock é o mesmo exercido pelo
      teste sequencial.

## Gate escopado (2026-07-21)

`pytest` sobre as 14 suítes de cronograma (reconciliação 26, versão 12,
restauração 3, endpoints 6, normalização M04, upload M03, decorator,
migrations, apontamento/caracterização/aprovação/duplicado/físico-financeiro/
revisão): **166 passed, 0 failed**. A suíte COMPLETA do repositório continua
não concluindo neste ambiente por testes pré-existentes que exigem servidor
vivo — mesmo bloqueio já registrado no fecho do M03, independente do M05.

## Ressalvas de execução (divergências deliberadas do plano)

1. **Motor pós-commit e obra sem RDO.** `recalcular_cronograma` e
   `sincronizar_percentuais_obra` comitam internamente (motor legado), então
   rodam APÓS o commit estrutural único — e **não rodam quando a obra não tem
   nenhum RDO**: ambos zeram folhas sem apontamento, o que apagaria a carga
   inicial de `pct_project` (conflito interno do plano, passos 4 vs 6,
   resolvido a favor da preservação de dados). Sem RDO, as datas ficam
   fielmente as do arquivo (o MS Project já as calculou); com RDO, o motor
   local volta a ser a fonte de verdade.
2. **Mapeamentos persistidos: uma linha por PAR**, com `tipo` = rótulo
   principal e a lista completa em `detalhes.tipos` (+ `id_temp`, candidatos,
   decisão) — não uma linha por classificação como o comentário do modelo
   sugeria. Decisão manual precisa de identidade por par; filtros por rótulo
   principal continuam possíveis.
3. **Filtro `ativa` também no motor** (`cronograma_engine`: sincronizar,
   recalcular, progresso geral), além das queries de views mapeadas pelo
   plano — tarefas arquivadas com `tarefa_pai_id` vivo corromperiam o rollup
   de datas/percentuais dos pais.
4. **`fingerprint` viaja em `payload_extra` do snapshot** (o modelo não tem
   coluna própria) para a restauração devolver a identidade M04.
5. **Quantidade/unidade nunca são apagadas pela importação** — só atualizam
   quando o arquivo traz valor (o M04 hoje entrega sempre `None`; "dados
   ausentes ficam ausentes").
6. **Evento `rollback` é omitido quando não há importação alguma na cadeia**
   (backfill puro): `cronograma_importacao_evento.importacao_id` é NOT NULL.
7. **401 dos endpoints testado direto no decorator** (`test_request_context`),
   como no M03: um request anônimo via `test_client` congela o estado do
   bypass legado de autenticação do processo e derrubaria o resto da suíte.

## Próximo passo sugerido

M06 (unificação do motor de recálculo) pode absorver: predecessora tipada/lag
no recálculo (hoje só no snapshot), decisão sobre `is_resumo` materializado, e
o semáforo de concorrência JVM diferido do M03/M10.
