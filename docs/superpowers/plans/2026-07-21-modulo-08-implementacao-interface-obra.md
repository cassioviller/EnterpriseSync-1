# Módulo 08 — Interface de Cronograma na Obra — Implementation Plan

> Fonte: spec `2026-07-17-modulo-08-interface-obra.md`. Em conflito, este plano
> vence (reconcilia com o modelo vivo pós-M07, medido 2026-07-21).

**Goal:** aba Cronograma da obra ganha a área de importação/versionamento:
status da versão ativa, upload `.xml`/`.mpp`, histórico de versões com
restauração, lista de importações com polling, prévia de diff com decisão de
mapeamentos, aplicação, cancelamento, resultado e auditoria — tudo escopado
explicitamente à obra.

## Fatos do modelo vivo (medidos 2026-07-21 — NÃO re-descobrir)

- Backend do fluxo JÁ EXISTE (M03/M05/M06/M07): upload
  `POST /obras/<id>/cronograma/importacoes` (aceita `.xml` MSPDI primário e
  `.mpp` — a spec citava ".mpp/.json" e está desatualizada, ver adendo M03),
  reconciliar/diff/mapeamentos/aplicar/restaurar em
  `views/cronograma_importacao.py`; eventos em `cronograma_importacao_evento`.
  Faltam: `GET .../importacoes` (lista), `GET .../versoes` (lista),
  `GET .../importacoes/<iid>/status` (polling), `POST .../cancelar`, e as
  PÁGINAS (prévia/resultado).
- **Flag do M10 não existe** — criar `cronograma_mpp_ativo()` em
  `utils/tenant.py` como ponto único (hoje = `is_v2_active()`; o M10 endurece)
  + context processor em `app.py` (padrão de `inject_v2_flag` :274).
- Aba Cronograma: `templates/obras/detalhes_obra_profissional.html:2129`
  (`#tab-cronograma`); inserir `{% include %}` logo após a abertura do pane —
  UM ponto de toque no template de 157 KB. CSRF: meta tag em
  `base_completo.html:10` (JS pega de lá); forms POST levam hidden token.
- Upload síncrono (M03): resposta já sai `normalizado`/`falhou` — o polling é
  cosmético (cobre `.mpp` lento), estado terminal sempre exibido com erro.
- Estados da importação: recebido → parseado → normalizado →
  aguardando_revisao → aplicado | falhou | cancelado. Cancelar só antes de
  aplicado (M05 valida aplicar; cancelar valida aqui).
- Playwright RODA (servidor gunicorn --reload em :5000); usar
  `expect_navigation` em submits (aprendizado M07). Fixture MSPDI mínima:
  gerar XML de 3-5 tarefas no próprio teste (não depender do arquivo real).
- Proibido citar baia/arquivo específico no código novo (critério global 17).

## Task 1: endpoints de apoio + flag — `tests/test_cronograma_interface_obra.py`

`utils/tenant.cronograma_mpp_ativo()` (+context processor). Em
`views/cronograma_importacao.py` (todas `cronograma_import_required` +
tenant-scope, id validado contra a obra da URL):
- `GET /obras/<id>/cronograma/importacoes` → JSON lista (id, arquivo, origem,
  status, erro, criado_em, aplicado_em, pendências quando aguardando_revisao);
- `GET /obras/<id>/cronograma/versoes` → JSON (numero, status, aplicada_em/por
  nome, observacao, importacao arquivo, n_snapshots);
- `GET .../importacoes/<iid>/status` → `{status, erro}` leve;
- `POST .../importacoes/<iid>/cancelar` → só status pré-aplicação (409 senão),
  `status='cancelado'` + evento `cancelado`.
Testes: listas escopadas, outra obra → 404, cancelar estados, status.
Commit: `feat(cronograma): endpoints de lista, status e cancelamento por obra (M08)`.

## Task 2: seção na aba Cronograma + upload/polling/restaurar

`templates/obras/cronograma_importacoes/_secao.html` (cartão de status da
versão ativa + botão Importar + tabela de versões com Restaurar [POST,
confirmação digitando o nº] + lista de importações com ações prévia/cancelar
+ aviso "altera somente a obra {nome}") e
`static/js/cronograma_importacao.js` (fetch das listas, modal de upload com
validação 20 MB/.xml/.mpp, POST com CSRF da meta tag, polling 2s até estado
terminal, cancelar, restaurar). Include único em
`detalhes_obra_profissional.html` atrás de `cronograma_mpp_ativo()`.
Teste: página da obra contém a seção com flag on; admin não-v2 não a vê.
Commit: `feat(cronograma): seção de importações e versões na aba da obra (M08)`.

## Task 3: prévia com decisão de mapeamentos, aplicar, resultado, auditoria

- `GET .../importacoes/<iid>/previa` → `previa.html`: resumo do RelatorioDiff,
  tabela com filtros (novas|removidas|pendentes|alteradas|tudo) e busca
  client-side (dados embutidos como JSON; nomes escapados — dados do arquivo
  são não confiáveis), decisão por linha (modal casar [select das chaves
  livres] | arquivar | nova → `PATCH .../mapeamentos/<mid>`), rodapé com
  pendências + "Aplicar nova versão" (desabilitado com pendência; confirmação
  com resumo) + "Cancelar importação"; secção de auditoria (eventos).
- Aplicar via POST JS → sucesso redireciona `GET .../importacoes/<iid>/resultado`
  → `resultado.html`: versão criada, contadores por nível, antes/depois do
  evento `aplicado` + relatório do `replanejado` (M06), histórico não
  reconciliado, auditoria completa.
- Reconciliar automático: abrir a prévia de importação `normalizado` dispara
  o reconcile server-side (mesma semântica do endpoint M05) — o usuário não
  precisa conhecer o passo técnico.
Testes: prévia 200 com diff, XSS escapado (`<script>` no nome), aplicar com
pendência → 422 na API e botão bloqueado (estado no HTML), resultado 200.
Commit: `feat(cronograma): prévia com decisão manual, aplicação e resultado na obra (M08)`.

## Task 4: Playwright jornada completa + gate + fecho §22

E2E (`tests/test_cronograma_importacao_obra_playwright.py`): obra com tarefas
vivas → aba Cronograma → modal upload (XML MSPDI gerado no teste com rename +
tarefa nova + ambígua) → linha aparece → prévia → resolver pendência no modal
→ aplicar → resultado → tarefas atualizadas e RDO/realizado preservados.
Gate escopado (suítes M03-M08) + fecho com ressalvas.
Commit: `docs(cronograma): fecho do M08 (Task 4)`.

## Critérios de aceite (spec §18)
1. Importação inteira sem sair da página da obra. 2. Impossível aplicar com
pendência. 3. Escopo por obra explícito (texto + 404 cross-obra). 4. Auditoria
visível com usuário/data. 5. Zero referência a baias no código novo.

## Fora de escopo
Redesign do Gantt/aba cliente; hub `/importacao`; flag real por tenant (M10 —
`cronograma_mpp_ativo` fica como ponto único); rascunho de upload assíncrono.
