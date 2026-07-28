# Revisão das Fases 1–5 — PARCIAL, e o run foi PERDIDO

> Workflow `wf_01f8bb97-6b1`, esforço alto, iniciado 28/07 ~16h40, parado
> 17h10 por créditos, **retomado e concluído — mas revisando outra coisa.**

## Leia isto antes de retomar qualquer coisa

Ao retomar, o agente de escopo rodou de novo e produziu um alvo DIFERENTE.
O journal registra os dois:

```
git diff e6223957..HEAD -- utils/autorizacao.py ... migrations.py ...   ← run original (Fases 1–5)
git diff HEAD~1                                                          ← run retomado
```

Entre a pausa e a retomada houve 6 commits, um fast-forward na `main` e um
branch apagado. O `HEAD` se moveu e o workflow passou a revisar **o último
commit**, não as Fases 1–5. O run concluído teve `candidates: 22`,
`verified: 22`, `refuted: 2`, `reported: 7` — todos em `migrations.py` e no
teste dele.

**Consequência: os 35 candidatos abaixo NUNCA foram verificados.** O run que
os levantou morreu no meio da verificação e o run retomado não os herdou.
Eles são PISTAS, não defeitos.

Lição para a próxima retomada: fixe o comando de diff nas instruções, para o
agente de escopo não poder derivar.

## O que já foi triado à mão (28/07)

Seis dos 35 foram verificados inline depois. **Três eram reais:**

| candidato | veredito |
|---|---|
| `gestao_custos_views.py:539` | ✅ **corrigido** — `obra_id` vinha do form sem checar tenant; escrita cross-tenant reproduzida |
| `services/rdo_assinatura.py:273` | ✅ **corrigido** — retificação contava a jornada 2× (R$ 124 → R$ 248) |
| `views/obras.py:3730` | ✅ **corrigido** — GET do handoff sem escopo por obra |
| `compras_views.py:1743` | ❌ refutado — chama `processar_compra_normal` |
| `views/rdo.py:1928` | ❌ refutado — rebaixamento deliberado; papel checado no corpo |
| `utils/autorizacao.py:225` | ❌ refutado — 1 chamador, usa o default documentado |

Aproveitamento: 3 de 6. Espere algo parecido nos 29 restantes.

## Os 29 candidatos ainda não verificados

### `compras_views.py`

- **:1207** — requisicoes() materializa os ids de todas as obras visíveis do tenant em Python e os injeta num IN(...), em vez de usar a query de obras_visiveis como subquery.
- **:1743** — A rota nova `requisicao_emitir_pedido` não gera o lançamento contábil automático que a rota antiga gerava — com `compras_governanca_ativa` ligada, nenhuma compra de material entra mais na contabilidade.

### `gestao_custos_views.py`

- **:539** — `editar_filho` assigns `filho.obra_id = novo_obra_id` straight from the form with no check that the obra belongs to `admin_id` — the one destination path in Fase 4 that skips validation, while the paired `obra_servico_custo_id` a few lines below is fully tenant-checked.
- **:1379** — `migrar_contas_pagar` builds `GestaoCustoFilho` with `obra_id=conta.obra_id` (nullable) and no `centro_custo_id`, so any ContaPagar without an obra now violates the Fase 4 CHECK `ck_gestao_custo_filho_destino` — and the violation surfaces at the single batch `db.session.commit()` outside the per-conta `try`, discarding the whole migration.

### `migrations.py`

- **:5015** — O CHECK `ck_gestao_custo_filho_destino` trava escritas que não foram roteadas por `destino_de_filho_novo`: a importação de custos por Excel grava `obra_id` possivelmente NULL sem centro de custo e passa a abortar o lote inteiro.

### `portal_obras_views.py`

- **:436** — aprovar_compra chama _registrar_acesso duas vezes no caminho com governança ligada, gravando dois PortalAcessoEvento 'compra_aprovar' para um único clique.

### `services/alcada_compras.py`

- **:170** — pendencias_de_aprovacao recalcula votos_de_aprovacao (que por sua vez refaz _inicio_da_rodada_atual) três vezes, e a rota de detalhe chama a cadeia inteira mais duas.
- **:221** — `pode_aprovar` decides non-admin approval authority via `utils.autorizacao.papel_na_obra`, which returns `PapelObra.GESTOR` for every authenticated tenant user while `escopo_obra_ativo` is off (the migration-216 default) — so the alçada's segregation of duties is void for the vast majority of tenants.

### `services/obra_handoff.py`

- **:51** — _cronograma_pendente engole qualquer exceção e devolve False ('nada pendente'), fazendo o handoff prosseguir e carimbar cronograma_revisado_em numa obra cujo cronograma nunca foi revisado.

### `services/rdo_assinatura.py`

- **:173** — `criar_retificador` copia a mão de obra para um RDO novo sem cancelar os custos do RDO original, e a idempotência de `CustoObra` é por `rdo_id` — a diária do funcionário é lançada duas vezes no mesmo dia.
- **:207** — Serviço importa de camada de view: `from views.rdo import _gerar_numero_rdo_unico` dentro de criar_retificador, mesmo padrão de services/obra_handoff.py:49 e :106 (que importam de views.obras).
- **:210** — O RDO retificador nasce com o default status='Finalizado' (models.py:1128) enquanto estado='rascunho', então os ≥9 consumidores que filtram por status=='Finalizado' passam a contar o rascunho ao lado do original retificado.
- **:273** — criar_retificador copia mão de obra para o novo RDO mas nunca cancela os custos já lançados pelo original, e a idempotência de gerar_custos_mao_obra_rdo é por origem_id (RDOMaoObra/RDOCustoDiario do RDO antigo), então o dia é lançado duas vezes.

### `services/rdo_ciclo_vida.py`

- **:242** — _MODELOS_FILHOS é uma lista manual de nomes de classe que omite RDOCustoDiario (models.py:1268), o filho do RDO que guarda os componentes financeiros do dia — escrita nele num RDO assinado não é barrada.
- **:262** — A guarda de imutabilidade é registrada como before_flush de SESSÃO global, então todo flush da aplicação — importação de cronograma, folha, seed — varre session.new/dirty/deleted mesmo quando nenhum RDO está envolvido.
- **:263** — A guarda `before_flush` de imutabilidade bloqueia os UPDATEs que `recomputar_cadeia` faz nos apontamentos de RDOs POSTERIORES, derrubando as rotas de apontamento e de exclusão de RDO quando qualquer RDO posterior da mesma tarefa está assinado/aprovado.
- **:285** — `from sqlalchemy import inspect as sa_inspect` está dentro do laço por rdo_id, executado a cada iteração de cada flush que toca um RDO.

### `services/rdo_foto_service.py`

- **:459** — Same Fase 5 base64 switch: the client portal's RDO photo templates were never updated alongside the internal one, and their only non-base64 branch points at a URL path that no route serves since `/persistent-uploads/<path>` was deleted in the same change.

### `services/rdo_hash.py`

- **:91** — payload_canonico emite seis SELECTs independentes por chamada e calcular_hash é invocado mais de uma vez por operação (aprovar recalcula o hash mesmo quando já existe assinatura de gestor).

### `services/rdo_pdf_service.py`

- **:91** — `_foto_image` procura o arquivo da foto só sob `static/`, ignorando `caminho_absoluto`/UPLOADS_PATH — o PDF do RDO sai sem registro fotográfico para toda foto gravada depois da Fase 5.
- **:108** — Fase 5 stopped writing the base64 columns when `UPLOADS_PATH` is set, but `_foto_image`'s disk fallback still resolves only against `static/` — it was never switched to `rdo_foto_service.caminho_absoluto`, unlike the HTML template and `crud_rdo_completo.servir_foto`.
- **:865** — In the new electronic-signature block, `a.nome_signatario` and `a.cargo_signatario` are interpolated into a `Paragraph` mini-XML string without `xml.sax.saxutils.escape`, while the same function escapes task names three hunks earlier for exactly this reason.

### `templates/custos/gestao.html`

- **:177** — Fase 4 added `required` to the destino select while keeping the "Administrativo" choice as the empty-value option, so HTML5 validation blocks exactly the case Fase 4 exists to support — launching a cost with no obra.

### `utils/autorizacao.py`

- **:63** — _escopo_ativo emite um SELECT em configuracao_empresa a cada chamada, e papel_na_obra o chama toda vez — somado ao db.session.get(Obra) e ao SELECT em usuario_obra, cada pergunta de permissão custa três round-trips.
- **:225** — obra_required trata qualquer papel_minimo fora de PAPEIS_QUE_EDITAM_OBRA como 'basta ver', então @obra_required(PapelObra.COMPRADOR) ou (PapelObra.APONTADOR) vira silenciosamente leitura livre em vez de erro.

### `utils/centro_custo.py`

- **:70** — centro_custo_administrativo grava codigo='ADM' fixo, sem o fallback 'ADM-<n>' que migration_251 implementa para o mesmo caso — as duas cópias da mesma regra divergem no tratamento de colisão.

### `utils/financeiro_integration.py`

- **:95** — destino_de_filho_novo (que pode CRIAR e flushar um CentroCusto) roda antes da checagem de is_v2_active, que descarta a chamada logo em seguida.

### `utils/tenant.py`

- **:158** — Quinta cópia do mesmo padrão 'ler um booleano de configuracao_empresa por admin_id com try/except → False': cronograma_mpp_ativo:132, cronograma_editor_v2_ativo:158, rdo_percentual_livre_on:187, scripts/flag_escopo_obra.escopo_ativo:26 e scripts/flag_compras_governanca.governanca_ativa:29.

### `views/dashboard.py`

- **:434** — A lista literal ['planejamento','em_execucao','pausada'] é repetida em quatro filtros do dashboard (:434, :1024, :1047, :1067) em vez de derivar de services.obra_estado, que já define ESTADOS_INATIVOS e TRANSICOES.

### `views/obras.py`

- **:1343** — `toggle_status_obra` (and its JSON twin `toggle_ativo_obra_api` at :1389) call `services.obra_estado.transitar()` directly with only `@login_required` + a tenant filter — the `pode_transitar_como` authority check that the new `POST /obras/<id>/estado` route applies is missing, so the AUTORIDADE table ('admin' to reopen a concluded obra, 'gestor' to conclude one) is bypassable.
- **:1352** — The `obra.concluida` webhook emission deleted from `editar_obra` was re-established only in `alterar_estado_obra` via `_notificar_transicao`; the two toggle routes, which also now drive the obra to CONCLUIDA, emit nothing.
- **:3663** — alterar_estado_obra, handoff_obra_get e handoff_obra_post repetem o mesmo bloco de três linhas 'get_tenant_admin_id → Obra.query.filter_by → 404' em vez de usar @obra_required(), que a própria Fase 1 criou e que já é usado em views/obras.py:1464.
- **:3730** — handoff_obra_get filtra só por tenant e não aplica o escopo por obra da Fase 1 (obra_required/obras_visiveis), devolvendo o dossiê completo da obra a qualquer usuário autenticado do tenant.

### `views/rdo.py`

- **:1928** — `duplicar_rdo` was downgraded from `@admin_required` to `@login_required` and rewritten around `_rdo_do_tenant_ou_404`, but is the only Fase 5 RDO write route with no per-obra authorization call — every sibling (assinar/aprovar/reabrir/retificar/finalizar) calls `pode_apontar_na_obra` or `pode_editar_obra`.
- **:1929** — `duplicar_rdo` was downgraded from `@admin_required` to `@login_required` but only gained a tenant check (`_rdo_do_tenant_ou_404`) — no `pode_apontar_na_obra`/`pode_editar_obra` guard, unlike every other Fase 5 route (assinar/aprovar/reabrir/retificar).


## O que falta fazer

1. **Triar os 29 restantes.** Inline (barato, ~6 por rodada) ou workflow novo
   com o diff FIXADO nas instruções (custo cheio, ~960k tokens de subagente).
2. Não há nada a "retomar": o run terminou, com outro alvo.

## Escopo original que foi pedido ao workflow

Fases 1–5 já em `main` (migrations 214-216, 230-232, 240-247, 250-254,
260-265). Excluídos: os 6 defeitos corrigidos em 28/07 (`6db59790..c79b179c`)
e dois pontos já investigados e limpos (guarda de imutabilidade não escapa
por append via relacionamento; `RdoAtividade` é modelo legado nunca
instanciado).
