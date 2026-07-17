# Módulo 8 — Interface de Cronograma dentro de cada Obra

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`.

## 1. Objetivo

Dar à página de detalhes da obra uma área de cronograma com: versão ativa, importação de `.mpp`, histórico de versões, prévia de diferenças com edição de mapeamentos, aplicação, cancelamento, restauração e trilha de auditoria — deixando explícito que tudo é escopado à obra atual.

## 2. Estado atual encontrado no código

- Página da obra: `templates/obras/detalhes_obra_profissional.html` (157 KB, renderizada por `views/obras.py:2063`); abas em `:878-916` (Visão Geral, Financeiro, Mão de Obra, RDOs, Compras, **Cronograma** `#tab-cronograma` `:2129`, Mapa); a aba Cronograma mostra o cronograma do cliente via iframe (`:2197`, `cronograma.cronograma_obra?cliente=1`) + botões "Cronograma interno"/"Regenerar do interno". **Não há UI de importação na obra**; o import físico-financeiro fica no hub global `templates/importacao/index.html:29-41` → `fisico_financeiro_upload.html` (form mínimo `accept=".json"`).
- Editor Gantt interno: `templates/obras/cronograma.html` (107 KB, `cronograma_views.py:247`).
- Padrões de template: base `templates/base_completo.html`, macros `templates/_partials/macros.html`; abas com hash JS (`detalhes_obra_profissional.html:2865-2898`); operações destrutivas via POST com form JS (preferência registrada em `replit.md`).
- Flag por tenant: `is_v2_active` via context processor (`app.py:275`).

## 3. Problemas atuais

Importação é global (hub), não por obra; nenhum lugar mostra "que cronograma esta obra está usando", histórico ou auditoria; usuário não tem como comparar antes de aplicar.

## 4. Escopo

### 4.1 Seção "Cronograma → Importações e versões" na aba Cronograma da obra

Bloco novo (acima do iframe atual), visível só com flag ligada (`is_v2_active` + flag específica `cronograma_mpp_ativo` — M10):

- **Cartão de status**: versão ativa (nº, data de aplicação, quem aplicou), nome/hash do arquivo de origem, data da última importação, botão **"Importar cronograma (.mpp)"**.
- **Histórico de versões**: tabela (nº, origem, status, aplicada em/por, ações: ver snapshot, **Restaurar** [POST + confirmação]).
- **Importações**: lista (arquivo, status do processamento com os estados do M2, erros legíveis, ações: ver prévia | cancelar).
- Aviso permanente no topo do fluxo: "Esta importação altera somente a obra **{obra.nome}**".

### 4.2 Tela de prévia (`/obras/<id>/cronograma/importacoes/<iid>/previa`)

- Resumo numérico (do `RelatorioDiff` M5): exatas, prováveis, novas, removidas, ambíguas, revisão manual, alterações por tipo.
- Tabela de tarefas com filtros (novas | removidas | conflitos/ambíguas | alteradas | tudo) e busca por nome; cada linha: tarefa atual ↔ tarefa nova, classificação, score, campos alterados (antes→depois), avisos do M4.
- Edição manual de mapeamento por linha (modal: confirmar | rejeitar | vincular a outra tarefa [autocomplete das tarefas da obra] | marcar nova | compor divisão/fusão) → `PATCH .../mapeamentos/<mid>` (M5).
- Rodapé: contagem de pendências; botão **"Aplicar nova versão"** desabilitado enquanto houver pendência; botão "Cancelar importação".
- Pós-aplicação: página de resultado com antes/depois (progresso geral, nº tarefas) e lista "histórico não reconciliado" (M6).

### 4.3 Trilha de auditoria

Aba/secção "Auditoria" na tela da importação: eventos (`cronograma_importacao_evento`) em ordem cronológica com usuário/data/detalhes.

## 5. Fora de escopo

Redesign do Gantt/aba atual; portal do cliente (inalterado); hub `/importacao` (permanece para os outros módulos); qualquer configuração global — **proibido** qualquer referência a arquivo/variável específica de baia no código novo (critério global 17).

## 6. Arquivos atuais envolvidos

`templates/obras/detalhes_obra_profissional.html` (inclusão do bloco), `views/obras.py:2063` (contexto extra), `views/cronograma_importacao.py` (M3/M5 — rotas de página), `app.py`/`main.py` (registro do blueprint).

## 7. Arquivos novos ou alterados previstos

Novos: `templates/obras/cronograma_importacoes/_secao.html` (parcial incluída na aba), `templates/obras/cronograma_importacoes/previa.html`, `templates/obras/cronograma_importacoes/resultado.html`, `static/js/cronograma_importacao.js` (upload com progresso, polling de status, filtros da prévia, modal de mapeamento). Alterados: os do §6.

## 8. Alterações de banco

Nenhuma.

## 9. Serviços e responsabilidades

Views desta área são finas: parse de request → serviços M3/M5 → template/JSON. Nenhuma fórmula ou matching na view/JS.

## 10. Rotas e contratos de API

Páginas: `GET /obras/<id>/cronograma/importacoes` (histórico), `GET .../importacoes/<iid>/previa`, `GET .../importacoes/<iid>/resultado`. APIs: as do M3/M5 + `GET .../importacoes/<iid>/status` (polling leve `{status, erro}`), `POST .../importacoes/<iid>/cancelar`. Todas tenant-scoped + decorator (M1); IDs sempre validados contra a obra da URL (objeto de outra obra → 404).

## 11. Fluxo de frontend

1. Aba Cronograma → "Importar cronograma (.mpp)" → modal de upload (drag&drop, limite 20 MB, extensões .mpp/.json-contingência). 2. Upload → linha na lista com status ao vivo (polling 2s até `aguardando_revisao|falhou`). 3. "Ver prévia" → tela §4.2 → resolver pendências → Aplicar (confirmação com resumo: "X alteradas, Y novas, Z arquivadas — RDOs e fotos preservados"). 4. Resultado antes/depois. 5. Histórico permite Restaurar com confirmação dupla (digitar nº da versão).

## 12. Regras de negócio

Espelha M5: aplicar bloqueado com pendências; restaurar cria versão nova (nunca apaga); cancelar só em status pré-aplicação.

## 13. Estratégia de migração

Bloco invisível sem flag; nenhum template existente muda de comportamento com flag desligada.

## 14. Compatibilidade

Aba atual (iframe cliente, botões existentes) intacta; link do hub de importação permanece; nomes de tarefa renderizados com escape padrão Jinja (dados do `.mpp` são não confiáveis).

## 15. Segurança

Autorização real (decorator M1 — não o bypass de `decorators.py`); CSRF nos POSTs como no padrão do projeto; validação de posse obra/tenant em toda rota; ações destrutivas via POST com confirmação (preferência `replit.md`).

## 16. Observabilidade

Eventos de auditoria já cobrem; front loga erros de upload no console + mensagem amigável.

## 17. Testes

- Integração: seção invisível sem flag; visível com flag; upload→status→prévia→decidir→aplicar→resultado (fluxo feliz com fixture `.mpp` pequena); aplicar com pendência → 422; restaurar → confirmação; objeto de outra obra → 404; XSS: tarefa com nome `<script>` renderiza escapada.
- Playwright: jornada completa de importação na obra de teste (novo arquivo, prévia, ajuste manual de 1 mapeamento, aplicar, conferir progresso inalterado no realizado); padrão dos testes `_playwright.py` existentes.

## 18. Critérios de aceite

1. Usuário completa importação inteira sem sair da página da obra.
2. Impossível aplicar com ambiguidade pendente.
3. Escopo por obra explícito em texto e comportamento (critério global 1).
4. Trilha de auditoria visível com usuário/data/origem (critério 15).

## 19. Riscos

- Template de 157 KB frágil → bloco como parcial `include` isolada, tocando o arquivo grande em um único ponto.
- Polling simples pode mascarar falha de worker → status `falhou` sempre terminal com erro exibido.

## 20. Dependências

M3 (upload/status), M5 (diff/aplicar/restaurar), M6 (números do resultado), M10 (flag).

## 21. Ordem detalhada de implementação

1. Parcial da seção + rota de histórico (flag on). 2. Modal upload + polling. 3. Tela de prévia read-only. 4. Edição de mapeamentos. 5. Aplicar/resultado. 6. Restaurar. 7. Auditoria. 8. Playwright. Commits por passo.

## 22. Checklist de conclusão

- [ ] Seção na aba Cronograma atrás de flag
- [ ] Upload→prévia→aplicar→resultado completo
- [ ] Edição manual de mapeamentos funcional
- [ ] Restaurar e auditoria visíveis
- [ ] Zero referência a baias no código novo
- [ ] Playwright verde
