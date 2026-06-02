# Design — Remediação da Auditoria de Segurança e Lógica (SIGE)

- **Data:** 2026-06-02
- **Autor:** Cássio Viller + Claude
- **Status:** proposto (aguardando revisão)
- **Tipo:** roadmap macro (design de coordenação de 4 sub-projetos)

## Contexto

Uma auditoria do sistema SIGE (gestão de obras, Flask, multitenant por `admin_id`)
identificou e **verificou adversarialmente** um conjunto de falhas. Os achados foram
confirmados lendo o código (não especulação) e re-checados por agentes céticos que
tentaram refutá-los. Este documento **não detalha a correção de cada falha** — ele
define a **estratégia, ordem, dependências e rollout** para tratá-las, decompondo o
trabalho em sub-projetos independentes que recebem cada um seu próprio ciclo
spec → plano → implementação.

### Premissas

- **Produção:** piloto — poucas empresas reais usando. Risco real, exposição contida.
  Agir com prioridade, sem hotfix cego.
- **Execução:** Claude implementa passo-a-passo; o usuário revisa cada bloco e autoriza
  push/merge/deploy explicitamente.
- **Migrações:** sistema próprio (`migrations.py`), numeradas e idempotentes, rastreadas
  na tabela `migration_history`, aplicadas **no boot/redeploy** (não no commit).

### Achados confirmados (resumo — fonte da verdade são os relatórios da auditoria)

| ID | Severidade | Achado |
|----|-----------|--------|
| A1 | CRÍTICO | `views/users.py:72` `editar_usuario` — IDOR: edita senha/`tipo_usuario` de usuário de outro tenant |
| A2 | CRÍTICO | `views/obras.py:822` `editar_obra` — edita qualquer obra; só `@login_required`, sem `@admin_required` |
| A3 | CRÍTICO | `views/obras.py:1338` `detalhes_obra` — sem `@login_required`; fallback "de debug" (1391-1399) desfaz o filtro de tenant de propósito |
| A4 | ALTO | `views/employees.py:293/614` `funcionario_perfil` + PDF — sem `@login_required`; filtro `admin_id` só cobre `RegistroPonto` |
| B1 | CRÍTICO | `decorators.py:8-22` — `admin_required`/`login_required` são no-ops. Usados por `configuracoes_views.py:11` e `ponto_views.py:29` → escalonamento de privilégio (funcionário comum acessa rota admin). **Refutado:** NÃO é acesso anônimo (há `@login_required` real empilhado) |
| B2 | CRÍTICO | `api_organizer.py:61/143/180` — rotas sem auth que leem/gravam `PropostaItem` de qualquer proposta (cross-tenant anônimo) |
| B3 | CRÍTICO | `views/employees.py:36` `/funcionarios` GET+POST — sem `@login_required` |
| B4 | ALTO | `views/api.py:661` `lancamento-finais-semana` — cria registros de ponto sem login |
| B5 | BAIXO | `ponto_views.py:578` `/debug` — sem decorator; vaza versão do Python/timestamp |
| C1 | CRÍTICO | `SESSION_SECRET=sige-production-secret-2025` commitado em `.env.easypanel:6` e `deploy_easypanel_final.sh:35` (versionados, não git-ignored, presentes em HEAD) |
| C2 | CRÍTICO | Credencial de banco `sige:sige` + `sslmode=disable` em `.env.easypanel:2` e fallback hardcoded em `app.py:58` |
| D1 | ALTO | `services/orcamento_service.py:100` — BDI completo TCU da ADR 0001 (status `accepted`) NÃO implementado; só usa `T+L`; campos AC/S/R/G/DF inexistentes no schema |
| D2 | MÉDIO | `services/orcamento_service.py:344` — `lucro = preço − custo` embute imposto (diverge de `L × preço` do CONTEXT). Atenuante: é só rótulo/snapshot, não realimenta o preço cobrado |
| D3 | ALTO | `services/orcamento_service.py:102` — guarda-corpo só bloqueia em `T+L ≥ 100%`; preço explode a 99% sem teto |

> **Correção parcial ao relatório original:** B1 foi reclassificado de "acesso sem login"
> para "escalonamento de privilégio" — as rotas têm `@login_required` real do flask_login
> empilhado sobre o stub; o que falha é a checagem de **papel** (o `admin_required` correto
> está em `auth.py`, mas esses arquivos importam o de `decorators.py`).

### Itens verificados como SEGUROS (não fazem parte do escopo)

- Portal do cliente: tokens `secrets.token_urlsafe(32)`, isolamento por `admin_id`, custo
  interno não renderizado.
- Sem SQL injection explorável (f-strings em SQL passam por `int()`/allowlist).
- Senhas com PBKDF2; uploads com `secure_filename` + allowlist + limite 5 MB.
- `bypass_auth.py.disabled` não está importado/ativo em lugar nenhum.
- `calcular_progresso_geral_obra_v2` correto (não passa de 100%, trata divisão por zero).

## Estratégia e princípio de sequência

A ordem **não** é por gravidade isolada, e sim por **risco × dependência × independência
de teste**:

1. **Tampar vazamento ativo antes de mexer em regra de negócio.** A e C expõem dados
   *agora*; D é cálculo errado mas não vaza — D por último.
2. **A e B compartilham o ponto de acesso por rota** (decorators + padrão de query).
   Consertar B (decorators/auth) **primeiro** cria a fundação; A (aplicar `admin_id`)
   se apoia nela. Ordem real: **B → A**.
3. **C é quase ortogonal**, com um passo sensível (rotação de segredo + reescrita de
   histórico git). Pode correr em paralelo, com **gate manual** na rotação.

## Sub-projetos (workstreams)

### Bloco 1 — Blindagem de acesso (B → A) — maior valor

**B (fundação — auth/decorators):**
- Corrigir `decorators.py`: `admin_required`/`login_required` precisam realmente checar,
  OU eliminar o stub e padronizar todos os imports para `auth.py`.
- Adicionar `@login_required` nas rotas órfãs: `api_organizer` (B2), `/funcionarios` (B3),
  `lancamento-finais-semana` (B4); remover ou proteger `/debug` (B5).

**A (aplicação — isolamento de tenant):**
- Padrão único: `filter_by(id=id, admin_id=get_tenant_admin_id()).first_or_404()` nas
  rotas A1–A4.
- **Remover o fallback "de debug"** de `detalhes_obra` (`views/obras.py:1391-1399`) que
  desfaz o filtro de tenant de propósito.

- **Esforço:** médio (~8 rotas + 1 decorator). **Risco de regressão:** médio (pode
  quebrar fluxo que dependia da brecha).
- **Trava de regressão:** teste com 2 tenants provando que tenant A recebe **403/404**
  ao acessar recurso de B (hoje recebe 200).

### Bloco 2 — Segredos (C) — rápido, sensível

- Remover `SESSION_SECRET` e `DATABASE_URL` de `.env.easypanel`,
  `deploy_easypanel_final.sh` e do fallback de `app.py:58`; exigir via env (sem fallback
  com credencial); `sslmode=require`.
- **Rotacionar** o `SESSION_SECRET` (gate manual — derruba sessões ativas) e **trocar a
  senha do banco**.
- **Limpar o histórico git** (os valores estão em commits passados) — passo destrutivo,
  confirmar antes.
- **Esforço:** baixo no código, médio na operação. **Risco:** rotação desloga todos
  (aceitável em piloto, mas avisado).

### Bloco 3 — BDI / lucro (D) — regra de negócio, por último

- Implementar BDI completo TCU (ADR 0001): campos novos no schema (AC/S/R/G/DF), nova
  fórmula, **migração**, guarda-corpo de preço (D3).
- Separar lucro de imposto na exibição (D2).
- **Esforço:** alto (schema + migração + UI + recálculo). **Risco:** propostas antigas —
  decidir se recalcula histórico ou só vale para novas.
- **Merece seu próprio brainstorming dedicado** — aqui entra só no roadmap; a fórmula e a
  estratégia de migração de dados serão desenhadas em spec separado.

## Dependências e esforço

```
Bloco 1:  B (decorators/auth) ──► A (admin_id por rota)   [sequencial: A depende de B]
Bloco 2:  C (segredos)                                     [paralelo, gate manual na rotação]
Bloco 3:  D (BDI)                                          [por último, spec próprio, depende de migração]
```

| Stream | Esforço (código) | Esforço (operação) | Risco regressão | Migração? |
|--------|------------------|--------------------|-----------------|-----------|
| B | Baixo-médio | — | Médio | Não |
| A | Médio (~8 rotas) | — | Médio | Não |
| C | Baixo | Médio (rotação + git) | Baixo (desloga sessões) | Não |
| D | Alto | Médio | Alto (propostas antigas) | **Sim** |

Único acoplamento forte: **A depende de B**. C e D são independentes.

## Item 0 — Pré-flight de migração (bloqueante, antes de qualquer deploy)

**Problema:** migrações não viajam no commit; aplicam no restart/redeploy. Além disso,
o runner **sobe o app mesmo se a migração falhar** (`app.py` — `"continuará mesmo com
erro"`), então a produção pode estar com schema meio-aplicado em silêncio.

**Ação:** antes de qualquer novo deploy, confirmar o estado real da produção comparando o
maior `migration_number` aplicado com o maior existente no código (~#188):

```sql
SELECT max(migration_number) AS aplicada, count(*) AS total
FROM migration_history;
```

- Se a produção estiver **atrás** do código → faltam migrações (investigar se falharam em
  silêncio antes de subir mais qualquer coisa).
- Se **baterem** → schema em dia; seguir o rollout normal.

Entregar isso como um comando/rota de diagnóstico de leitura (sem efeito colateral) para o
usuário rodar contra a produção. **Nenhum deploy dos Blocos 1–3 acontece antes deste
pré-flight passar.**

## Testes e rollout

**Padrão de trabalho:** um **branch por bloco**. Claude faz as edições, roda a suíte
existente (`run_tests.sh` + pytest + Playwright e2e), mostra o diff; o usuário aprova;
**push/merge/deploy só sob autorização explícita**.

**Travas de regressão por bloco:**
- **B+A:** teste e2e/integração com 2 tenants → tenant A leva 403/404 em
  `editar_usuario`/`detalhes_obra`/`funcionario_perfil` de B (vermelho antes, verde
  depois). Esse teste é o critério de "pronto".
- **C:** boot com env limpa (sem fallback) funciona; `git ls-files` não traz mais segredo.
- **D:** cálculo de preço com BDI completo vs valor esperado da ADR; decisão explícita
  sobre propostas antigas.

**Rollout (produção piloto):** Item 0 (pré-flight) → merge → redeploy do container →
conferir log de migração → smoke test das rotas corrigidas. A rotação do `SESSION_SECRET`
(Bloco 2) entra **nesse** restart (deslogue geral, avisado).

## Critérios de sucesso

- Bloco 1: nenhuma das rotas A1–A4/B2–B4 responde com dados/escrita cross-tenant; teste de
  2 tenants verde; nenhum funcionário comum acessa rota admin.
- Bloco 2: nenhum segredo em `git ls-files` nem no histórico; app sobe só com env; sessão
  e senha de banco rotacionadas.
- Bloco 3: preço segue a fórmula da ADR 0001; lucro exibido = `L × preço`; preço não
  explode perto de `T+L = 100%`.

## Fora de escopo (desta rodada)

- Refatoração não relacionada (ex.: aposentar `auto_fix_all_admin_id` do boot, código
  morto v1/v2, stubs do relatório de frota) — registrar como dívida, tratar depois.
- CSRF dos blueprints autenticados (achado ALTO) — candidato a um Bloco futuro; não entra
  nesta rodada para manter foco.
- Lock de concorrência no runner de migração — anotado como risco; fora desta rodada.

## Próximos passos

1. Revisão deste spec pelo usuário.
2. `writing-plans` para o **Bloco 1 (B → A)** — primeiro plano de implementação.
3. Blocos 2 e 3 ganham seus próprios specs/planos quando chegada a vez (D exige
   brainstorming dedicado de domínio).
