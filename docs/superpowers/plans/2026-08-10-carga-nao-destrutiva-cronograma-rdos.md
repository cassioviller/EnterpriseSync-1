# Plano — carga não-destrutiva de cronograma + RDOs (export → mescla → upsert) — 2026-08-10

**O problema.** Colocar numa obra EXISTENTE de produção (caso concreto: Angela)
o cronograma novo (.mpp com %) e RDOs vindos do WhatsApp, **sem** o reimport
físico-financeiro — que apaga RDOs/tarefas/medições e é recusado em obra já
versionada por .mpp. As duas metades não-destrutivas JÁ existem
(`services/cronograma_versao_service.py` e `services/atualizacao_rdos.py`);
o que falta é a costura e, antes dela, o **retrato do que já está no sistema**.

**O fluxo confirmado com o Cássio (2026-08-10).** Três artefatos entram no
file tree do repo:

1. **Zip de export da obra** (botão novo na página da obra em produção) —
   autossuficiente: carrega a identidade da obra (dispensa passar
   codigo/admin_id à mão) + RDOs já salvos + tabela de tarefas.
2. **`.mpp`** com as % novas — *opcional*; sem ele só a fase de RDOs roda.
3. **Zip do WhatsApp** com os RDOs que não entraram no sistema — a mescla
   tolera sobreposição (data nos dois lados vira `_conflito` para revisão
   humana; nada é decidido em silêncio).

## Contrato de round-trip (verificado em `services/atualizacao_rdos.py`)

O upsert só sobrescreve as chaves PRESENTES no payload; dia sem `comentario`
não zera o que já estava. Campos que round-tripam: `data` (chave), `clima`
→ `clima_geral`, `precipitacao`, `comentario` → `comentario_geral`,
`apontamentos[].pct` (acumulado, via `registrar_apontamento`), `fotos`
(puladas se o RDO já tem). O resto (temperatura, vento, efetivo real,
estado/retificação) sai como chave `_underscore` — o updater ignora por
contrato; serve de contexto de revisão, nunca de gravação.

**Chave de apontamento.** `tarefa_mpp` = `TarefaCronograma.mpp_uid` quando
existe. Tarefa sem `mpp_uid` (obra que nunca importou .mpp) sai como
**`-tarefa.id` (negativo)** — nunca colide com uid real do MS Project — e o
`mapa_nomes.json` que acompanha o zip resolve pelo fallback por
nome+ancestrais do `IndiceTarefas` (mesmo formato de `mapa_nomes_do_json`).

## Fases

| # | Entrega | Estado |
|---|---|---|
| 1 | **Export**: `services/exportacao_rdos.py` + rota zip + botão + testes | esta rodada |
| 2 | `preflight` (diagnóstico local: tarefas vivas, RDOs, versão, mpp_uid, 5 portas) | |
| 3 | Fase cronograma via serviços M03–M05 em CLI, parada obrigatória em `decisao_requerida` | |
| 4 | Fase RDO: mescla export+WhatsApp (`_conflito` por data) + fotos por obra (`fotos_rdos/obras/<codigo>/<data>/`) | |
| 5 | Relatório único + `--dry-run` ponta a ponta (default; gravar exige `--aplicar`) | |

### Fase 1 — o zip de export (read-only, risco zero)

Conteúdo:

- `obra.json` — identidade (id, codigo, nome, admin_id/username, datas,
  status), versão ativa do cronograma, contagens de RDO por estado e a
  **tabela de tarefas** do cronograma interno vivo (id, mpp_uid, nome,
  pai, %, quantidade_total, unidade_medida) — tudo que o script local
  precisa sem tocar no banco de produção.
- `rdos.json` — `{"rdos": [...]}` no formato canônico do upsert, ordenado
  por data, com as chaves `_` de contexto (`_numero_rdo`, `_estado`, …).
- `mapa_nomes.json` — `{tarefa_mpp: {nome, pai, caminho}}` para TODAS as
  chaves exportadas (robustez: mesmo com mpp_uid presente o fallback fica
  disponível).
- `fotos/<data>/N.<ext>` — **opcional** (`?fotos=1`): só para migrar RDOs
  entre obras; round-trip na MESMA obra não precisa (fotos já no banco,
  updater preserva). Fonte: disco quando `caminho_arquivo` existe, senão
  colunas base64 (deferred — carregar só quando pedido).

Rota: `GET /obras/<obra_id>/rdos/exportar` em `views/rdo.py` (main_bp),
admin + escopo de tenant (padrão `Obra.admin_id == get_admin_id_robusta()`),
`send_file` de BytesIO. Botão na página da obra
(`templates/obras/detalhes_obra_profissional.html`).

Testes (`tests/test_exportacao_rdos.py`, molde de
`test_atualizacao_rdos.py`): round-trip export→`atualizar_rdos` em obra
clone reproduz clima/comentário/pct; obra sem `mpp_uid` → chave negativa +
mapa resolve; RDO imutável exporta com `_estado` e o reimport o pula;
cross-tenant 404.

## Fronteiras

- `pct_project` do .mpp só carrega em obra SEM RDO
  (`cronograma_versao_service.py`, carga inicial). Obra com RDO + `--mpp`
  ⇒ aviso explícito e flag de aceite; nunca descarte silencioso.
- Pastas legadas `fotos_rdos/<data>/` são da Baia — **não migrar, não
  tocar**. Obras novas usam `fotos_rdos/obras/<codigo>/<data>/` (fase 4).
- O reimport físico-financeiro destrutivo continua existindo só para
  criação inicial; este plano não encosta nele.
