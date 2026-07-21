# Módulo 07 — RDO: modos quantitativo e percentual — Fecho

> Fecha o M07 conforme o plano `2026-07-21-modulo-07-implementacao-rdo.md`
> (spec `2026-07-17-modulo-07-rdo.md`). Divergências deliberadas nas ressalvas.

## Entregue (commits nesta branch `feat/cronograma-mpp-m03-upload-parser`)

| Task | Commit | Conteúdo |
|---|---|---|
| 1 | `7a5462d` | Semântica M02 em dupla escrita + validações tipadas + snapshot por linha no serviço |
| 2 | `2482e90` | `recomputar_cadeia` + integração em apontar/salvar/excluir |
| 3 | `f815bd9` | Contrato de modos no `tarefas_rdo`; portal/PDF pelos campos persistidos |
| 4 | `72e9bb1` | UI dos dois modos (preview, filtro, validações espelhadas) + parse no flexivel |
| 5 | (este) | Playwright dos dois modos + gate + fecho |

## Checklist §22 da spec — estado

- [x] **Dois modos funcionais em qualquer obra** — quantitativo (campo
      "Quantidade executada HOJE ({unidade})" com acumulado/saldo) e
      percentual (campo "Percentual ACUMULADO da tarefa (%)" com anterior);
      marco vira toggle binário. Nunca dois campos; modo vem do backend
      (`tarefas_rdo.tipo_modo` ← `modo_da_tarefa`).
- [x] **Campos semânticos gravados; quantidade nunca guarda percentual (modo
      novo)** — `tipo_apontamento`, `percentual_acumulado`,
      `percentual_incremento_dia`, `quantidade_total_snapshot`,
      `unidade_snapshot` gravados SEMPRE; modo percentual zera os campos de
      quantidade. **Ressalva:** a spec pedia NULL — as colunas são NOT NULL
      desde a criação e o M07 não faz migration (§8), então o neutro é 0.0.
- [x] **Retrocesso/>100/override validados e auditados** — exceções tipadas
      (`RetrocessoNaoPermitido`, `SobreexecucaoNaoConfirmada`,
      `MarcoApenasZeroOuCem`, subclasses de ValueError para não derrubar o
      laço legado); justificativa auditada em **log estruturado** (não há
      tabela de eventos de RDO — ressalva; evento de banco exigiria
      migration). Overshoot QUANTITATIVO mantém clamp legado com aviso
      (travado por caracterização). UI espelha com confirm/prompt.
- [x] **Recomputo em cadeia atômico e testado** — mesma transação do caller;
      ordem estável (data_relatorio, id); integrado em `apontar_producao`
      (devolve `rdos_posteriores_recalculados`), `salvar_rdo_flexivel` e
      `excluir_rdo`; valores exatos testados para inserção no meio, edição
      e exclusão, nos dois modos.
- [x] **Snapshots protegem histórico** — % derivado do
      `quantidade_total_snapshot` DA LINHA na escrita e no recomputo; mudar
      `quantidade_total` da tarefa só afeta apontamentos futuros (teste).
- [x] **Portal/PDF consistentes** — portal lê `percentual_incremento_dia`/
      `percentual_acumulado` persistidos (derivação em memória vira fallback
      pré-M02); PDF mostra linha percentual como "+X pp".
      **Ressalva:** sem teste automatizado dedicado de portal/PDF (rotas
      exigem sessão de cliente/render de PDF); cobertos pelo contrato do
      serviço + revisão.
- [x] **Suíte + Playwright verdes** — gate escopado: 153 testes em 11 suítes
      (caracterização SEM edição no modo quantitativo) + 4 E2E de browser
      (novo `test_rdo_dois_modos_playwright.py` com fluxo completo dos dois
      modos + marco + filtro + preview + persistência; regressão dos
      Playwright existentes de RDO que dependem do template alterado).

## Ressalvas de execução (divergências deliberadas)

1. **Modo permissivo no serviço** — a spec §4.1 pedia modo IMPOSTO pela
   tarefa com override auditado; a caracterização legada permite quantidade
   em tarefa sem quantitativo (fallback 0%) e o form legado depende disso.
   `modo_da_tarefa` é contrato de UI; o serviço aceita os dois campos (o
   par UI+backend novo nunca mistura).
2. **Teste percentual do M1 reescrito** — o modo percentual antigo do
   serviço (incremento em `quantidade_executada_dia`) não tinha caller de
   produção (o import grava direto no modelo, formato antigo, até o M9);
   o teste que o travava foi atualizado ao contrato novo.
3. **Sem feature-flag** — infra de rollout é M10; a dupla escrita
   (legado + semântico) fica ligada permanentemente até o M9/M10 desligar.
4. **`editar_rdo.html` intocado** — a edição de apontamento de cronograma
   roda por `apontar_producao` (UPSERT + recomputo), não pelo fluxo de
   subatividades legadas do template de edição.
5. **Playwright**: `form.submit()` navega assíncrono — o teste usa
   `expect_navigation` para não correr contra o POST (falha intermitente
   diagnosticada durante o fecho).

## Próximo

M08 (interface da obra) e M09 (migração das baias — inclui migrar o import
físico-financeiro para o serviço de apontamento, aposentando o formato
antigo e o fallback do portal).
