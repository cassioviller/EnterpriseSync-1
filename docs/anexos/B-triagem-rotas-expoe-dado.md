# Anexo B — Triagem caso a caso das rotas `EXPOE DADO`

> **Data:** 2026-07-23 · **Procedência:** 📖 lido no código (cada `arquivo:linha`
> conferido nesta data, branch `main` pós-merge da Fase 3).
> Fecha o item aberto da Fase 0.5 registrado no `ESTADO-ATUAL.md`
> ("28 rotas `EXPOE DADO` sem auth — triagem caso a caso").
>
> **Nota de contagem:** o Anexo A lista 11 `EXPOE DADO (api)` + 18
> `EXPOE DADO (página)` = **29** rotas, não 28. Todas as 29 estão aqui.
> O censo (medido em `f090b09`) envelheceu: as Fases 1, 0.5/3.2 e 0.5/3.3
> fecharam ou removeram 11 delas — o que este anexo registra rota a rota.
>
> **Este anexo não altera código.** Vereditos:
> **FECHAR** (adicionar `@login_required`/`@admin_required` é seguro) ·
> **TOKEN** (escopo do portal por token) · **PÚBLICA** (legítima sem auth) ·
> **MORTA** (sem referência viva, candidata a remoção) ·
> **DECISÃO** (dono do produto) · **JÁ FECHADA** (censo envelheceu).

## Resumo

| Veredito | Rotas |
|---|---:|
| JÁ FECHADA (Fases 1 / 0.5) | 9 |
| FECHAR | 3 |
| TOKEN | 2 |
| PÚBLICA | 5 |
| MORTA | 9 — **as 7 que ainda existiam foram REMOVIDAS em 23/07** (as outras 2, `/health` e `/health/simple`, já tinham morrido com `health.py` em `549bdf06`). Junto foi `templates/rdo/novo_backup.html`, o único referenciador e que nenhum `.py` renderiza. Regressão: `tests/test_triagem_rotas_fechadas.py::test_rota_morta_removida` |
| DECISÃO | 1 |
| **Total** | **29** |

## EXPOE DADO (api) — 11 rotas

| Rota | Arquivo:linha (hoje) | Dado exposto a anônimo | Veredito | Justificativa |
|---|---|---|---|---|
| `/api/funcionarios/buscar` | 📖 `api_funcionarios.py:83-85` | — (era lista de funcionários) | **JÁ FECHADA** | Blueprint `api_funcionarios_buscar` removido (0.5/3.2); a rota sobrevivente tem `@login_required`. |
| `/api/` (`api_status`) | 📖 `api_organizer.py:15-16` | JSON estático com lista de endpoints | **PÚBLICA** | Nenhum dado de tenant — só nomes de rotas já públicas no censo; inócua. |
| `/api/templates/listar` | 📖 `api_organizer.py:29-30` | — | **JÁ FECHADA** | `@login_required` adicionado (Fase 0.5/3.3). |
| `/api/propostas/<id>/itens-organizados` | 📖 `api_organizer.py:184-185` | — | **JÁ FECHADA** | `@login_required` adicionado (Fase 0.5/3.3). |
| `/api/obra/<id>/servicos` GET | 📖 `api_servicos_obra_limpa.py:29-30` | — | **JÁ FECHADA** | `@login_required` adicionado (Fase 0.5/3.3). |
| `/api/funcionarios/<obra_id>` | 📖 `views/api.py:33-35` (virou `/api/obras/<id>/funcionarios`) | — | **JÁ FECHADA** | Rota renomeada e com `@login_required`; colisão de path resolvida. |
| `/api/funcionarios` | 📖 `views/api.py:63-64` | Lista de funcionários (id, nome, função, departamento) do tenant com MAIS funcionários — bypass anônimo explícito em `views/api.py:100-108` | **FECHAR** | Viva (📖 `templates/obras.html:567`, página já logada) — nada anônimo legítimo a consome; o bypass entrega o maior tenant a qualquer um. |
| `/rdo/api/ultimo-rdo/<obra_id>` | 📖 `views/rdo.py:1925-1933` | Último RDO + serviços da obra; anônimo cai em `admin_id = 10` chumbado | **MORTA** | Zero referências em templates/static (varredura completa); enquanto viver, expõe o tenant 10. |
| `/api/test/rdo/servicos-obra/<obra_id>` | 📖 `views/rdo.py:3392-3393` | Serviços/subatividades de QUALQUER tenant (admin_id lido da própria obra) | **MORTA** | Endpoint "TEST"; única referência é `templates/rdo/novo_backup.html:1273`, que nenhum `.py` renderiza. |
| `/api/ultimo-rdo-dados/<obra_id>` | 📖 `views/rdo.py:3464-3465` | Último RDO completo de QUALQUER tenant — cross-tenant explícito e logado como "PERMITIDO" (📖 `views/rdo.py:3490`) | **MORTA** | Sem referência viva; a mais grave do grupo enquanto existir — enumeração de `obra_id` varre todos os tenants. |
| `/api/servicos-obra-primeira-rdo/<obra_id>` | 📖 `views/rdo.py:3754-3755` | Serviços + subatividades de QUALQUER tenant (admin_id lido da obra) | **MORTA** | Única referência é `templates/rdo/novo_backup.html:2171` (template morto). |

## EXPOE DADO (página) — 18 rotas

| Rota | Arquivo:linha (hoje) | Dado exposto a anônimo | Veredito | Justificativa |
|---|---|---|---|---|
| `/persistent-uploads/<path:filename>` | 📖 `app.py:178-183` | QUALQUER arquivo do volume de uploads (comprovantes de pagamento, fotos, planilhas) por path adivinhável, sem escopo de tenant | **TOKEN** | O portal por token consome (📖 `portal_obras_views.py:578` grava a URL; `templates/portal/_portal_compras.html:98` renderiza) — precisa servir comprovante verificando o escopo do token, não o volume inteiro aberto. |
| `/ponto-diagnostico` | 📖 `app.py:506-507` | Traceback de import (paths internos, trechos de código) | **MORTA** | Página de debug de incidente antigo; zero referências. |
| `/health` (`health.py:14`) | 📖 arquivo deletado em `549bdf06` | — | **MORTA** | `health.py` removido na Fase 0.5/3.2 (era sombreado por `views/dashboard.py`); já resolvida. |
| `/health/simple` (`health.py:56`) | 📖 arquivo deletado em `549bdf06` | — | **MORTA** | Idem — removida junto com o arquivo. |
| `/site` | 📖 `landing_views.py:5-7` | Landing page estática | **PÚBLICA** | É a landing comercial; anônimo é o público-alvo. |
| `/servicos` (redirect legado) | 📖 `main.py:118-121` | Nada — `redirect(url_for('catalogo.servicos_list'))`, e o destino exige login | **PÚBLICA** | Redirect puro para não quebrar bookmarks (Task #128). |
| `/medicao/portal/pdf/<medicao_id>` | 📖 `medicao_views.py:512-524` | PDF de extrato de medição — mas exige `?token=` e filtra `MedicaoObra` pela obra do token | **TOKEN** | Já está corretamente escopada por token (`token_cliente` + `portal_ativo` + `obra_id`); o censo envelheceu, é o desenho do portal. |
| `/ponto/debug` | 📖 `ponto_views.py:576-577` | Versão do Python e confirmação de blueprint | **MORTA** | Página de debug; zero referências. |
| `/` (`index`) | 📖 `views/auth.py:46-47` | Nada — só decide o redirect (login ou dashboard) | **PÚBLICA** | É a raiz do app; anônimo vai para `/login`. |
| `/health` | 📖 `views/dashboard.py:24-25` | Status do banco (`healthy`/`unhealthy`) | **PÚBLICA** | Healthcheck consumido pelo EasyPanel; fechar quebraria o deploy. |
| `/health/veiculos` | 📖 `views/dashboard.py:34-50` | Diagnóstico de schema: nomes de tabelas OK/MISSING, warnings, erros truncados | **DECISÃO** | Sem dado de tenant, mas revela schema; se nenhum monitor externo a consome, fechar (ou remover) — só o dono sabe. |
| `/dashboard` | 📖 `views/dashboard.py:190-198` | — | **JÁ FECHADA** | `@login_required` adicionado na Fase 1. |
| `/funcionario_perfil/<id>` | 📖 `views/employees.py:286-289` | — | **JÁ FECHADA** | `@login_required` + `@admin_required` adicionados na Fase 1. |
| `/funcionario_perfil/<id>/pdf` | 📖 `views/employees.py:598-609` | PDF com ponto e KPIs de QUALQUER funcionário de QUALQUER tenant — `get_or_404(id)` sem filtro de tenant e, anônimo, `admin_id=None` remove o filtro de `RegistroPonto` (📖 `:626-633`) | **FECHAR** | A irmã `/funcionario_perfil/<id>` já exige `@login_required`+`@admin_required`; o link vem de página logada (📖 `templates/funcionario_perfil.html:14`) — mesmos decorators aqui são seguros. |
| `/test` | 📖 `views/employees.py:738-740` | JSON estático `{'status': 'ok'}` | **MORTA** | Rota de teste sem dado e sem referência. |
| `/obras` | 📖 `views/obras.py:44-45` | — | **JÁ FECHADA** | `@login_required` adicionado na Fase 1. |
| `/obras/<id>` | 📖 `views/obras.py:1446-1450` | — | **JÁ FECHADA** | `@login_required` + `@obra_required()` adicionados na Fase 1. |
| `/rdo/<id>` | 📖 `views/rdo.py:927-947` | RDO renderizado; corpo já escopa por tenant (`Obra.admin_id == admin_id_atual`), anônimo só quebra por `AttributeError` engolido pelo `except` | **FECHAR** | Nenhum consumidor anônimo; `@login_required` transforma o crash acidental em 401 intencional. |

## As 3 exposições vivas mais graves

1. 📖 `views/employees.py:598` — `/funcionario_perfil/<id>/pdf`: dossiê
   trabalhista (ponto, KPIs) de qualquer funcionário de qualquer tenant, para
   anônimo, por enumeração de `id`.
2. 📖 `views/rdo.py:3464` — `/api/ultimo-rdo-dados/<obra_id>`: último RDO
   completo de qualquer tenant por enumeração de `obra_id`, com o cross-tenant
   logado como "PERMITIDO". (Morta por referência, viva por URL.)
3. 📖 `app.py:178` — `/persistent-uploads/<path>`: o volume de uploads inteiro
   (comprovantes de pagamento, fotos de RDO) legível por path, sem escopo de
   tenant nem de token.

Menção: 📖 `views/api.py:63` — `/api/funcionarios` entrega a lista de
funcionários do maior tenant do banco a qualquer anônimo, e está viva
(`templates/obras.html:567`).
