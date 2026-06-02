# Plano de Implementação — Bloco 1: Blindagem de Acesso (B → A)

- **Data:** 2026-06-02
- **Spec de origem:** `docs/superpowers/specs/2026-06-02-remediacao-auditoria-design.md`
- **Escopo:** apenas o Bloco 1 (autenticação/decorators + isolamento de tenant). C (segredos) e D (BDI) têm planos próprios.
- **Execução:** Claude implementa; usuário aprova cada commit; push/merge/deploy só sob autorização explícita.

## Princípios

1. **Teste primeiro.** O primeiro passo cria um teste de regressão de 2 tenants que **falha agora** (cross-tenant retorna 200). Ele só fica verde no fim do bloco. É o critério de "pronto".
2. **Commits minúsculos.** Um passo = um commit isolado e reversível. Ordem: fundação (B) antes de aplicação (A), porque A se apoia nos decorators corrigidos.
3. **Reaproveitar o que já existe.** `utils/tenant.py` (`get_tenant_admin_id`, `require_tenant`) e `auth.py` (`admin_required`, `funcionario_required`, `can_access_data`, `get_tenant_filter`) já estão prontos e corretos — o trabalho é *usá-los*, não criar coisa nova.
4. **Branch:** `fix/bloco1-blindagem-acesso`. Sem push até o usuário mandar.

## Decisões de design (confirmar antes de codar)

- **D-1 — SUPER_ADMIN:** mantém visão cross-tenant. Em queries escopadas, usar o padrão de `auth.py`: se `tipo_usuario == SUPER_ADMIN`, não filtrar; senão filtrar por `get_tenant_admin_id()`. (`can_access_data(admin_id)` encapsula essa regra.)
- **D-2 — `editar_usuario`:** um ADMIN só edita usuários do **próprio tenant** (`Usuario.admin_id == current_user.id`). SUPER_ADMIN edita qualquer um. Impede também que um admin promova a si/—outro a SUPER_ADMIN de outro tenant.
- **D-3 — Remoção de fallbacks "bypass":** os ramos `else` que auto-detectam admin_id por contagem (`detalhes_obra` 1373-1383, `funcionarios` 57-60) viram **código morto** assim que `@login_required` garante `current_user` autenticado. Serão removidos, não adaptados.
- **D-4 — `/api/...` que hoje não exigem login:** recebem `@login_required`. Se algum for consumido por integração máquina-a-máquina (n8n?), confirmar antes — pode precisar de token em vez de sessão. **A verificar no passo B2/B4.**

---

## Fase B — Fundação (autenticação/decorators)

### Passo B0 — Teste de regressão (RED)
- **Arquivo novo:** `tests/test_isolamento_tenant_bloco1.py`.
- Cria 2 tenants (admin A e admin B) + um recurso de cada (usuário, obra, funcionário).
- Loga como A e tenta acessar/editar recurso de B em: `editar_usuario`, `editar_obra`, `detalhes_obra`, `funcionario_perfil`. **Espera 403/404.**
- Cobre também as rotas sem auth (`api_organizer`, `/funcionarios` POST, `lancamento-finais-semana`): sem login → espera redirect/401.
- **Estado esperado agora:** VERMELHO (hoje retorna 200/grava). Commit do teste falhando.
- **Verificação:** `pytest tests/test_isolamento_tenant_bloco1.py` → falhas nas asserções de bloqueio.

### Passo B1 — Corrigir `decorators.py` (stub → real)
- Substituir os no-ops por re-exportação dos decorators reais:
  - `login_required` ← `flask_login.login_required`
  - `admin_required` ← `auth.admin_required`
- Conserta de uma vez `configuracoes_views.py:11` e `ponto_views.py:29` (escalonamento de privilégio — achado B1).
- **Cuidado com import circular** (`auth` importa `models`; `decorators` passaria a importar `auth`). Se houver ciclo, importar dentro do wrapper (lazy).
- **Verificação:** app sobe; logar como FUNCIONARIO e confirmar que rota admin de `configuracoes`/`ponto` agora redireciona com "Acesso restrito"; rodar suíte (`run_tests.sh`) sem regressão.
- Commit isolado.

### Passo B2 — `api_organizer.py` (B2): proteger 3 rotas
- Rotas: `/api/templates/carregar-multiplos` (61), `/api/propostas/salvar-organizacao` (143), `/api/propostas/<id>/itens-organizados` (180).
- Adicionar `@login_required` e escopar as queries: `Proposta`/`PropostaItem` filtradas por `admin_id == get_tenant_admin_id()` (via join em `Proposta` para `PropostaItem`).
- **D-4:** confirmar se essas rotas são chamadas só pelo front autenticado (grep nos templates/JS) antes de exigir sessão.
- **Verificação:** sem login → 401/redirect; logado, item de outro tenant → 404.
- Commit isolado.

### Passo B3 — `views/employees.py` `/funcionarios` (B3)
- Adicionar `@login_required` + `@admin_required` (o real, de `auth.py`).
- Remover o fallback de tenant não autenticado (linhas 57-60); `admin_id = get_tenant_admin_id()`.
- **Verificação:** sem login → redirect; POST cria funcionário só no tenant do usuário.
- Commit isolado.

### Passo B4 — `views/api.py:661` `lancamento-finais-semana` (B4)
- Adicionar `@login_required`; remover o fallback "primeiro admin do sistema"; usar `require_tenant()`.
- **D-4:** verificar consumidor (provável front interno).
- **Verificação:** sem login → 401; cria ponto só no tenant do usuário.
- Commit isolado.

### Passo B5 — `ponto_views.py:578` `/debug` (B5)
- Menor impacto. Opção escolhida: **proteger** com `@login_required` + `@admin_required` (ou remover a rota se não for usada — grep antes).
- **Verificação:** rota não responde anônima.
- Commit isolado.

---

## Fase A — Aplicação (isolamento de tenant) — depende da Fase B

### Passo A1 — `views/users.py:72` `editar_usuario` (A1)
- Trocar `Usuario.query.get_or_404(user_id)` por busca escopada:
  - SUPER_ADMIN: `get_or_404` direto.
  - Senão: `Usuario.query.filter_by(id=user_id, admin_id=get_tenant_admin_id()).first_or_404()`.
- Aplica D-2 (admin só mexe no próprio tenant; não consegue setar SUPER_ADMIN alheio).
- **Verificação:** A edita usuário de B → 404. Teste B0 (parte usuário) → verde.
- Commit isolado.

### Passo A2 — `views/obras.py:822` `editar_obra` (A2)
- Adicionar `@admin_required`; busca escopada `filter_by(id=id, admin_id=get_tenant_admin_id())...first_or_404()`.
- Remover a derivação de `admin_id` a partir da própria obra (`get_admin_id_robusta(obra, ...)`).
- **Verificação:** A edita obra de B → 404. Teste B0 (parte obra-editar) → verde.
- Commit isolado.

### Passo A3 — `views/obras.py:1338` `detalhes_obra` (A3) — o mais delicado
- Adicionar `@login_required`.
- **Remover** o ramo de bypass auto-detect (1373-1383) e o fallback de debug (1391-1399) — ambos viram código morto sob login.
- Manter a regra SUPER_ADMIN (admin_id=None → vê todas) via `auth`-style; ADMIN/FUNCIONARIO → `get_tenant_admin_id()`.
- Busca: super_admin → `filter_by(id=id)`; senão → `filter_by(id=id, admin_id=tenant)`. Se não achar → `abort(404)`.
- **Verificação:** A abre obra de B → 404; super_admin ainda abre qualquer uma. Teste B0 (parte obra-detalhe) → verde.
- Commit isolado.

### Passo A4 — `views/employees.py:293/614` `funcionario_perfil` + PDF (A4)
- Adicionar `@login_required` em ambas.
- Escopar a busca de `Funcionario` por `admin_id` (não só a query de `RegistroPonto`).
- **Verificação:** A abre perfil/PDF de funcionário de B → 404. Teste B0 (parte funcionário) → verde.
- Commit isolado.

### Passo A5 — Fechar o bloco (GREEN)
- Rodar `tests/test_isolamento_tenant_bloco1.py` completo → **tudo verde**.
- Rodar suíte completa (`run_tests.sh` + pytest + Playwright e2e) → sem regressão.
- Se algum e2e quebrar por depender da brecha, corrigir o teste/fluxo legítimo.
- Commit final do bloco.

---

## Gate de deploy (produção piloto) — fora da codificação, sob autorização

1. **Item 0 — pré-flight de migração** (do spec): rodar contra produção
   `SELECT max(migration_number), count(*) FROM migration_history;` e comparar com o código (~#188). Não deployar se a produção estiver atrás.
2. Merge `fix/bloco1-blindagem-acesso` → redeploy do container → conferir log de migração.
3. Smoke test das rotas corrigidas em produção.
4. (Bloco 1 **não** mexe em segredos nem em schema — sem rotação nem migração nova aqui.)

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Import circular em `decorators.py`→`auth.py` | import lazy dentro do wrapper |
| Rota `/api/...` era usada por integração sem sessão | grep de consumidores no passo B2/B4 antes de exigir login (D-4) |
| e2e existente dependia da brecha (acesso sem login) | ajustar o teste para logar primeiro; é correção legítima |
| Remover fallback quebra fluxo "bypass" | bypass já está desativado no sistema; ramos são código morto sob `@login_required` |

## Sequência de commits (resumo)

```
B0  test(sec): regressão de isolamento de tenant (RED)
B1  fix(auth): decorators.py reexporta decorators reais
B2  fix(auth): exige login + escopo em api_organizer
B3  fix(auth): protege /funcionarios
B4  fix(auth): protege lancamento-finais-semana
B5  fix(auth): protege /debug do ponto
A1  fix(sec): escopo de tenant em editar_usuario
A2  fix(sec): escopo de tenant + admin_required em editar_obra
A3  fix(sec): remove fallback e escopa detalhes_obra
A4  fix(sec): escopo de tenant em funcionario_perfil + pdf
A5  test(sec): suíte de isolamento verde + regressão geral
```
