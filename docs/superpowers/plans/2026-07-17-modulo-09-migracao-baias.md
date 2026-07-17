# Módulo 9 — Compatibilidade e Migração do Fluxo das Baias

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`.

## 1. Objetivo

Converter a obra-piloto das baias para a arquitetura genérica — o que hoje funciona por scripts e JSON canônico vira um caso de uso normal (importação de `.mpp` na obra) — preservando integralmente cronograma (101 tarefas), 19 RDOs (22/06–13/07), fotos, apontamentos, percentuais, portal, custos, medições e todos os testes, sem remover o fluxo antigo antes de migração testada com rollback.

## 2. Estado atual encontrado no código

- Fluxo vigente: dev roda `scripts/rebuild_baia_from_0607_mpp.py` (hardcodes: `OUT` absoluto `:11`, `origin/main` `:12`, `CRONOGRAMA 06.07.mpp` `:13`, `etapa_de()` `:19-39`, `FERRAGENS_KEY` + qtd 48 `:42,:60-63`, `REMAP` `:92`) → `cronograma_fisico_financeiro_baias.json` → upload em `/importacao/fisico-financeiro` → `importar_fisico_financeiro` (destrutivo, recria tudo inclusive RDOs).
- Artefatos específicos: JSONs na raiz (canônico + `Baia_fisico_financeiro_IMPORTAR.json` legado), `.mpp` versionados (`CRONOGRAMA 06.07.mpp`, `CRONOGRAMA OFICIAL.mpp`), `fotos_rdos/` (19 pastas), symlink `tests/fixtures/cronograma_fisico_financeiro_baias.json`, scripts `seed_fisico_financeiro_baias.py`, `seed_rdos_baias.py` (obsoleto p/ baia, `ESTADO_ATUALIZACAO_BAIA.md:18`), `seed_fotos_rdos_baias.py`, `diff_mpp_vs_json.py`, `gerar_importacao_baia_rev10.py` e família REV10 (orçamento — fora deste fluxo), docs `ESTADO_ATUALIZACAO_BAIA.md`, `RDO.md`, `entrega_baia_rev10/`.
- Nenhuma condicional "baia" em `models.py`/`migrations.py` (verificado); no núcleo genérico há apenas comentários de spec (`services/importacao_fisico_financeiro.py:255,:427`) e a constante `FOTOS_RDO_BASE='fotos_rdos'` (`:32`).
- 46 testes de integração travam o comportamento (`tests/test_importacao_fisico_financeiro.py`), incluindo contagens exatas (19 RDOs, percentuais físicos, ferragens 48/48).

## 3. Problemas atuais

O caso baia depende de scripts com hardcodes e de recriação total; qualquer atualização de cronograma exige regenerar e reimportar tudo; `REMAP` manual é a "reconciliação" atual.

## 4. Escopo

### 4.1 Migração da obra baia (procedimento, executado em homologação antes de produção)

1. Pré-condições: M2-M8 em produção; backfill 203 criou versão nº1 + snapshots da baia; flag ligada para o tenant.
2. Gravar identidades: importar `CRONOGRAMA 06.07.mpp` pelo pipeline novo **em modo reconciliação** contra o cronograma vigente. Espera-se: alto casamento por caminho/nome/fingerprint (mesma origem); os poucos ambíguos são decididos manualmente na prévia (equivalente assistido do antigo `REMAP`). Aplicar ⇒ uids/wbs gravados nas 101 tarefas, ids preservados, **nenhuma alteração de datas/nomes esperada** (arquivo idêntico à origem).
3. Verificação de equivalência (script de verificação novo, ver §7): antes/depois — nº tarefas ativas=101, 19 RDOs com mesmas datas, contagem de apontamentos/fotos/mão de obra idêntica, `percentual_concluido` por tarefa idêntico (tolerância 0.01), progresso geral idêntico nas 5 fontes, medições/custos intocados, portal renderizando.
4. Rollback ensaiado: restaurar versão nº1 e re-verificar equivalência.
5. Repetir em produção com janela e backup (`pg_dump` antes).

### 4.2 Ajuste do importador físico-financeiro (separação de responsabilidade)

- `importar_fisico_financeiro` continua existindo para **criação inicial**; ganha registro de versão: ao materializar cronograma, cria `CronogramaVersao` nº1 + snapshots + `CronogramaImportacao(origem='json_canonico')` (aditivo; testes atuais continuam verdes com asserts adicionais).
- Reimport do JSON canônico numa obra que **já tem versão aplicada pelo fluxo novo** → recusado com erro claro ("use a importação de cronograma da obra") — impede o caminho destrutivo de atropelar o versionado.

### 4.3 Inventário de descontinuação (executar somente após §4.1 verde em produção + 2 semanas de estabilidade)

| Artefato | Destino |
|---|---|
| `scripts/rebuild_baia_from_0607_mpp.py` (com `REMAP`, `etapa_de`, `FERRAGENS_KEY`) | Descontinuar (mover p/ `archive/`) — substituído por parser+normalização+reconciliação |
| `scripts/diff_mpp_vs_json.py` | Descontinuar — prévia do M5/M8 cobre |
| `scripts/seed_rdos_baias.py` | Já obsoleto — arquivar |
| `Baia_fisico_financeiro_IMPORTAR.json` | Arquivar (teste que o usa passa a fixture própria reduzida) |
| `cronograma_fisico_financeiro_baias.json` + symlink | **Mantido** enquanto for fixture dos testes de criação inicial; deixa de ser o meio de atualização |
| `CRONOGRAMA *.mpp` na raiz | Mantidos como fixtures de integração do parser (M3) |
| `scripts/seed_fisico_financeiro_baias.py`, `seed_fotos_rdos_baias.py` | Mantidos (seed de dev) |
| Comentários spec-baia no serviço | Atualizados para apontar os novos docs |
| `ESTADO_ATUALIZACAO_BAIA.md` / `RDO.md` | Atualizados: novo fluxo de atualização = UI da obra |

## 5. Fora de escopo

Remover o importador físico-financeiro (permanece como criação inicial); tocar família REV10 de orçamento; alterar `FOTOS_RDO_BASE` (contrato de fotos permanece).

## 6. Arquivos atuais envolvidos

`services/importacao_fisico_financeiro.py`, `tests/test_importacao_fisico_financeiro.py`, scripts e artefatos do §2, `RDO.md`, `ESTADO_ATUALIZACAO_BAIA.md`.

## 7. Arquivos novos ou alterados previstos

Novos: `scripts/verificar_equivalencia_obra.py` (CLI de verificação §4.1.3 — genérico por `obra_id`, reutilizável no rollout), `tests/test_migracao_baias_equivalencia.py` (roda o cenário completo: import canônico → reconciliar `.mpp` → aplicar → equivalência → rollback → equivalência). Alterados: serviço (registro de versão + recusa §4.2), testes de import (asserts adicionais de versão), docs.

## 8. Alterações de banco

Nenhuma nova; escreve versões/snapshots/uids via fluxos M2/M5.

## 9. Serviços e responsabilidades

Criação inicial (JSON canônico) e atualização (pipeline .mpp) formalmente separados — tabela do doc de casos de uso do M1 atualizada.

## 10. Rotas e contratos de API

Nenhuma nova; `/importacao/fisico-financeiro` ganha a recusa §4.2 (422 com mensagem).

## 11. Fluxo de frontend

Nenhum novo (usa M8). Mensagem de recusa clara no hub de importação.

## 12. Regras de negócio

Equivalência é o gate: qualquer divergência nos itens do §4.1.3 aborta a migração (restaurar + investigar). Nenhum artefato removido antes do período de estabilidade.

## 13. Estratégia de migração

Homologação → produção com backup; rollback = restaurar versão nº1 (testado antes); flag por tenant permite desligar a UI nova sem afetar dados.

## 14. Compatibilidade

Durante toda a janela: fluxo antigo funcional (critério global 16); suíte de 46 testes verde em todos os commits; após descontinuação, testes que referenciam artefatos arquivados são atualizados no mesmo PR.

## 15. Segurança

Migração executada por usuário admin real (auditoria com nome); backup obrigatório antes da produção.

## 16. Observabilidade

Relatório de equivalência salvo como evento da importação; métricas de matching da baia (esperado ~100% nos níveis 3-5) comparadas às de obras novas.

## 17. Testes

`test_migracao_baias_equivalencia.py` (cenário completo em banco de teste); suíte `--gate` integral; Playwright da jornada de importação na baia em homologação; teste da recusa §4.2.

## 18. Critérios de aceite

Critérios globais 16 e 17: baias funcionam durante toda a migração; ao final, nenhuma regra específica de baia no núcleo (grep de guarda: `baia` não aparece em `services/` exceto docs/comentários históricos removidos).

## 19. Riscos

- Divergência sutil de percentuais por arredondamento no replanejamento → tolerância 0.01 definida; investigar qualquer excesso.
- `.mpp` 06.07 não parsear idêntico ao JSON canônico (o rebuild forçava `nivel=outline+1` e `dias||1`) → o normalizador M4 precisa reproduzir essas convenções (nivel=outline+1 já é a convenção de `_materializar_cronograma_mpp:186-188`; `dias||1` documentar como regra de normalização) — o teste de equivalência pega.
- Testes com contagens exatas quebrarem por asserts novos → asserts adicionais, nunca alterar os existentes.

## 20. Dependências

M2-M8 completos; M10 fase 1 (obra de teste) concluída antes da baia.

## 21. Ordem detalhada de implementação

1. `verificar_equivalencia_obra.py` + teste. 2. Registro de versão no importador (aditivo) + asserts. 3. Recusa §4.2 + teste. 4. Cenário completo `test_migracao_baias_equivalencia.py` em banco de teste. 5. Execução em homologação (checklist manual documentado). 6. Produção com backup. 7. Período de estabilidade. 8. PR de descontinuação (§4.3) + atualização de docs/testes. Commits por passo.

## 22. Checklist de conclusão

- [ ] Equivalência automatizada e verde (homolog + prod)
- [ ] Rollback ensaiado com sucesso
- [ ] Importador registra versão; recusa destrutiva em obra versionada
- [ ] Inventário de descontinuação executado após estabilidade
- [ ] Docs baia atualizados
- [ ] Grep de guarda sem "baia" no núcleo
