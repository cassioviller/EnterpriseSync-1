# Módulo 09 — Migração do Fluxo das Baias — Fecho

> Fecha a parte EXECUTÁVEL do M09 conforme o plano
> `2026-07-21-modulo-09-implementacao-migracao-baias.md` (spec
> `2026-07-17-modulo-09-migracao-baias.md`). Execução em homologação/produção
> e a descontinuação física (§4.3) são operacionais — ver "Pendências".

## Entregue (commits nesta branch)

| Task | Conteúdo |
|---|---|
| 1 | `scripts/verificar_equivalencia_obra.py` — captura/comparação genérica por obra + CLI |
| 2 | Importador registra versão nº1 + snapshots + importação `json_canonico`; recusa destrutiva em obra migrada |
| 3 | `tests/test_migracao_baias_equivalencia.py` — cenário integral com o `.mpp` real + rollback |
| 4 | Docs da baia atualizados; comentários "baia" neutralizados no núcleo; este fecho |

## Checklist §22 da spec — estado

- [x] **Equivalência automatizada e verde (banco de teste)** — cenário
      integral (marker `java`): fixture canônica (101 tarefas, 19 RDOs) →
      upload do `CRONOGRAMA 06.07.mpp` real → reconciliação com matching
      alto (≥90 casadas, ≤3 removidas — spec §16) → decisão programática
      das pendências (equivalente assistido do REMAP) → aplicar (≥95 uids
      gravados, IDs preservados) → **A≈B**. `[ ]` homolog/produção:
      procedimento documentado em `ESTADO_ATUALIZACAO_BAIA.md` (backup →
      `--salvar` → importar pela aba da obra → `--comparar` → divergiu ⇒
      Restaurar) — execução fora deste ambiente.
- [x] **Rollback ensaiado com sucesso** — no mesmo teste: restaurar a
      versão pré-migração ⇒ **A≈C**.
- [x] **Importador registra versão; recusa destrutiva em obra versionada**
      — versão nº1+snapshots+`CronogramaImportacao(json_canonico)` na
      criação; reimport canônico em obra ainda-canônica permitido (vira
      v2, disciplina M05); obra migrada → ValueError com mensagem que
      aponta a aba Cronograma (o hub exibe como flash). Os 46 testes do
      importador seguem verdes SEM edição.
- [ ] **Inventário de descontinuação (§4.3)** — ADIADO por definição da
      própria spec: só após §4.1 verde EM PRODUÇÃO + 2 semanas de
      estabilidade. Tabela de destino já está na spec; nada foi removido
      (critério global 16: fluxo antigo funcional durante toda a janela).
- [x] **Docs baia atualizados** — `ESTADO_ATUALIZACAO_BAIA.md` (rodada
      M09 com o novo fluxo e o procedimento) e `RDO.md` (aviso no topo).
- [x] **Grep de guarda sem "baia" no núcleo** — `services/` zerado
      (comentários históricos neutralizados, incluindo a atribuição na
      tabela de categorias do M04).

## Aprendizados do cenário real (refinaram o verificador)

1. **Percentual comparado só nas FOLHAS** — os pais agregam por duração
   das filhas e as durações mudam legitimamente na migração (o rebuild
   antigo forçava `dias>=1`; o pipeline novo preserva marcos com 0):
   divergências de centésimos nos pais eram falso positivo.
2. **`rollup_raiz` fora da checagem de concordância** — agregação
   hierárquica difere da flat (v2/kpi/curva) por construção em árvores
   profundas; a própria tela do cronograma substitui a linha raiz pelo
   v2. Fica capturado como informação.
3. **Progresso geral antes/depois não é gate** — marcos com duração 0
   ganham peso 0 pós-M06 (era peso 1 no import antigo); o gate são os
   percentuais por folha (±0.01) e as contagens.

## Pendências operacionais (fora deste ambiente)

1. Executar o procedimento em homologação e produção (com backup e
   janela), usando o CLI de equivalência.
2. Período de estabilidade (2 semanas) → PR de descontinuação (§4.3).
3. Playwright da jornada na baia em homologação (a jornada genérica já é
   coberta pelo E2E do M08).

## Próximo

M10: flag real em `cronograma_mpp_ativo`, observabilidade
(`verificar_consistencia_progresso`, métricas de matching), rollout
faseado e remoção da dupla escrita legada do M07.
