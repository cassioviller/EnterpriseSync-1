# Plano de Remediação — Saúde do App (pós-iterações e2e)

- **Data:** 2026-06-08
- **Origem:** achados das iterações sobre `test_browser_all_modules.py` (87→115 testes) e da implementação do Bloco 3 (BDI). Ver [[bloco3-bdi-estado]].
- **Branch:** trabalhar a partir de `main` (já contém Bloco 3 + fix de folha). Cada bloco abaixo em sua própria branch; push/merge/deploy só sob autorização.

## Princípios

1. **Commits minúsculos, isolados, reversíveis.** Fundação antes de aplicação.
2. **Teste primeiro** onde há lógica (cache, precificação, eventos). Smoke/e2e onde é UX.
3. **Sem regressão de comportamento de preço/financeiro** — a suíte all-modules (115) e a de BDI (25) ficam verdes ao fim de cada bloco.
4. **Decisões de schema (multi-tenancy) não são aplicadas sem ADR + análise de impacto.**

## Ordem de execução (por valor/risco)

```
P1 (alta, baixo risco)  → Bloco A: sweep do cache de instância ORM
P2 (alta, baixo risco)  → Bloco B: falhas silenciosas → sinais acionáveis
P3 (alta, médio risco)  → Bloco C: create_app() único (app == main:app)
P4 (média)              → Bloco D: fonte única do plano de contas (+ ADR de PK)
P5 (média)              → Bloco E: precificação única (server autoritativo)
P6 (média)              → Bloco F: caching de config por request (N+1)
P7 (média)              → Bloco G: onboarding / prontidão do tenant
P8 (baixa)              → Bloco H: infra de testes + migrações
```

Blocos A, B, F são independentes entre si. C é pré-requisito recomendado de H. D é pré-requisito de parte de B (avisos de plano de contas).

---

## Bloco A — Sweep do cache de instância ORM (P1)

**Problema (confirmado):** caches de processo guardam instâncias SQLAlchemy → *detached* após o teardown da sessão → erro intermitente em worker longevo.
- `services/folha_service.py:_obter_parametros_legais` — **já corrigido** (referência).
- `models.py:2398` `ParametrosLegais.get_parametros_cached` (`@lru_cache`).
- `models.py:2503` `PlanoContas.get_conta_cached` (`@lru_cache(256)`).

**Abordagem:** cachear **valores**, não entidades. Padrão único: ou (a) cache por-request via `flask.g`, ou (b) `@lru_cache` retornando um value-object imutável (namedtuple/dataclass) com os campos usados.

**Passos**
- A0 — Teste de regressão: chamar o getter em 2 contextos de app distintos (simulando 2 requests) e acessar atributos no 2º — hoje quebra (RED p/ os 2 ainda não corrigidos).
- A1 — `get_parametros_cached`: retornar value-object (ou query direta). Manter `invalidar_cache()` funcional.
- A2 — `get_conta_cached`: idem; conferir todos os callers (lançamentos, folha, handlers).
- A3 — Auditar `grep -rn "@lru_cache" --include=*.py` e qualquer `_cache_* = {}` por instâncias ORM; corrigir os que retornarem entidade.
- A4 — Garantir invalidação ao editar (params/contas) limpa o caminho certo.

**Verificação:** A0 verde; suíte de folha/contabilidade sem regressão; processar folha 3× no mesmo worker mantém geração de lançamento.
**Esforço:** baixo. **Risco:** baixo.

---

## Bloco B — Falhas silenciosas → sinais acionáveis (P2)

**Problema (confirmado):** efeitos colaterais de evento falham calados quando faltam pré-requisitos. Ex.: folha "processada com sucesso" mas sem `LancamentoContabil` (conta ausente); handler aborta com `logger.warning` invisível ao gestor (`event_manager.py:1110`).

**Abordagem:** tornar a ausência de pré-requisito **visível e acionável**, sem quebrar o fluxo principal.

**Passos**
- B1 — Registrar resultado dos eventos: tabela/linha `evento_integracao` (status ok/falha + motivo + link de correção) escrita pelos handlers. (Ou reusar log estruturado existente, se houver.)
- B2 — Handler de folha: ao faltar conta essencial, gravar a falha (B1) e devolver no flash da rota de processar: "Folha processada; lançamento contábil pendente — conta 5.1.01.001 ausente. [Configurar plano de contas]".
- B3 — Mesmo tratamento para `material_entrada → GestaoCusto` e `proposta_aprovada → Obra` (faltando fornecedor/cliente/etc.).
- B4 — Painel "Integrações pendentes" (lista das falhas B1 não resolvidas) na home do gestor ou em Contabilidade.

**Verificação:** e2e — processar folha sem a conta → flash de pendência + registro em B1; com a conta → ok e pendência some.
**Esforço:** médio. **Risco:** baixo (aditivo). Depende parcialmente de D para a mensagem de plano de contas.

---

## Bloco C — `create_app()` único (app == main:app) (P3)

**Problema (confirmado, bati 2×):** `from app import app` registra 37 blueprints; produção sobe `main:app` com +17 (custos_escritório, importação, hubs…). Bugs aparecem só num caminho (ex.: `BuildError custos_escritorio.painel_mensal`).

**Abordagem:** fábrica única `create_app()` que registra **todos** os blueprints; `app` e `main` passam a usá-la.

**Passos**
- C1 — Extrair o registro de blueprints de `main.py` para uma função `registrar_blueprints(app)` em módulo neutro.
- C2 — `app.py` chama `registrar_blueprints(app)` (idempotente; try/except por blueprint como hoje em main).
- C3 — `main.py` passa a só importar `app` (sem re-registrar) ou chamar a fábrica.
- C4 — Remover o `import main` que adicionei como contorno em `tests/test_orcamento_formato_br.py`.

**Verificação:** `python -c "from app import app; print(len(list(app.url_map.iter_rules())))"` == produção; suíte all-modules verde; `url_for` do nav resolve em ambos os caminhos.
**Esforço:** médio. **Risco:** médio (ordem de import / efeitos no boot). Fazer com a suíte rodando a cada passo.

---

## Bloco D — Fonte única do plano de contas + ADR de PK (P4)

**Problema (confirmado):** dois seeders divergentes (`financeiro_seeds.py` vs `contabilidade_utils.py`) para os mesmos códigos; tenant demo incompleto (sem ramo 5.x). `PlanoContas.codigo` é **PK global** → plano de contas efetivamente compartilhado entre tenants.

**Abordagem:** (1) consolidar o seed; (2) decidir, via ADR, se a chave deve ser `(admin_id, codigo)`.

**Passos**
- D1 — Escolher a definição canônica (provável: `financeiro_seeds`, que tem a cadeia 5.x → 5.1.01.001 que o handler de folha exige). Marcar a outra como deprecada.
- D2 — `seed_plano_contas_if_needed` passa a **completar lacunas** (idempotente por código, criando pais faltantes), não só pular se já há contas.
- D3 — Migração de saneamento: para cada tenant, garantir as contas essenciais (5.1.01.001 e o conjunto do handler de folha).
- D4 — **ADR**: `PlanoContas.codigo` global vs `(admin_id, codigo)`. Análise de impacto (FK `conta_pai_codigo`, queries, isolamento). **Não aplicar schema sem aceite.**

**Verificação:** todo tenant tem as contas essenciais; teste de isolamento (tenant A não vê/usa conta de B) conforme decisão do ADR.
**Esforço:** médio (alto se a PK mudar). **Risco:** médio/alto na parte de schema → gated pelo ADR.

---

## Bloco E — Precificação única (server autoritativo) (P5)

**Problema (confirmado):** duas precificações — `services/pricing.py` (catálogo/proposta, BDI) e `orcamento_view_service` + **fórmula JS duplicada** no template `orcamentos/editar.html`. O teste de paridade existe mas é frágil (quebrou por drift de nome de variável).

**Abordagem:** uma fórmula autoritativa no servidor; o JS do editor só **exibe preview** chamando um endpoint de cálculo (ou recebendo o resultado), sem reimplementar a conta.

**Passos**
- E1 — Endpoint leve `POST /orcamentos/preview-preco` que devolve o cálculo do backend (reusando o helper canônico).
- E2 — Avaliar fundir o cálculo de orçamento ao `services/pricing.py` (ou extrair o núcleo comum). Mapear diferenças (custo real de compra vs BDI completo) antes de unificar.
- E3 — JS do editor passa a consumir E1 (debounce) em vez da fórmula local; remover a fórmula duplicada.
- E4 — Aposentar o teste de paridade regex; substituir por teste do endpoint.

**Verificação:** preview do editor == backend para a tabela de casos atual; sem fórmula de preço em JS.
**Esforço:** médio. **Risco:** médio (mudança de UX no editor). Snapshots de orçamento existentes não recalculam.

---

## Bloco F — Caching de config por request (N+1) (P6)

**Problema:** padrão `ConfiguracaoEmpresa.query` por-item em ~10 arquivos (medição, cronograma, portal de obras…). Um N+1 já foi resolvido no BDI via `flask.g` (`services/pricing.py:_config_empresa`).

**Abordagem:** helper único `config_empresa_cached(admin_id)` (escopo de request, `flask.g`), adotado nos hotspots de loop.

**Passos**
- F1 — Promover o `_config_empresa` do pricing a util compartilhado (`services/tenant_config.py`).
- F2 — Substituir as consultas em loop pelos hotspots (medição/cronograma/portal) pelo util.
- F3 — Medir queries antes/depois num fluxo representativo (materializar proposta / render de medição).

**Verificação:** contagem de queries a `configuracao_empresa` cai para 1 por request nos fluxos tocados; sem regressão.
**Esforço:** baixo/médio. **Risco:** baixo.

---

## Bloco G — Onboarding / prontidão do tenant (P7)

**Problema:** a cadeia folha→contabilidade exige params legais + plano de contas + funcionários; tenant novo (e o demo) cai nas falhas silenciosas.

**Abordagem:** checklist de configuração e bloqueios suaves.

**Passos**
- G1 — Serviço `prontidao_tenant(admin_id)` → lista de itens (params do ano, plano de contas essencial, BDI, ≥1 funcionário) com status e link.
- G2 — Card "Configuração da empresa: X% pronta" na home do gestor.
- G3 — Avisos contextuais (ex.: tela de folha mostra "Parâmetros legais 2026 ausentes [Configurar]" antes de processar).

**Verificação:** e2e — tenant sem params mostra checklist incompleto e CTA; após configurar, 100%.
**Esforço:** médio. **Risco:** baixo. Reusa B1/B4.

---

## Bloco H — Infra de testes + migrações (P8)

**Problema:** testes misturam pytest e scripts `sys.exit`, com `admin_id` hardcoded e **skip silencioso** (escondia 9 integrações — já mitigado pelo seed). `migrations.py` tem 13.4k linhas, numeração manual com lacunas.

**Abordagem:** camada de fixtures + organização de migrações (incremental, sem big-bang).

**Passos**
- H1 — Fixture pytest `tenant_demo` que garante os pré-requisitos (generalizar `_garantir_dados_e2e`), eliminando skips por dado ausente.
- H2 — Converter os scripts standalone-críticos em testes pytest de verdade (sem `sys.exit`).
- H3 — Migrações: extrair a lista-registro para módulo próprio; documentar a convenção de numeração; (futuro) avaliar split por domínio.

**Verificação:** `pytest tests/` sem skips por dado ambiente; suíte estável em CI.
**Esforço:** médio. **Risco:** baixo.

---

## Resumo de sequência e gates

| Bloco | Prioridade | Esforço | Risco | Gate especial |
|-------|-----------|---------|-------|---------------|
| A cache ORM | P1 | baixo | baixo | — |
| B falhas→sinais | P2 | médio | baixo | depende parte de D |
| C create_app | P3 | médio | médio | suíte verde por passo |
| D plano de contas | P4 | médio/alto | médio/alto | **ADR de PK antes de schema** |
| E precificação única | P5 | médio | médio | snapshots não recalculam |
| F N+1 config | P6 | baixo | baixo | — |
| G onboarding | P7 | médio | baixo | reusa B |
| H testes/migrações | P8 | médio | baixo | — |

**Não-objetivos:** reescrever EventManager; trocar ORM/stack; refatorar UI fora dos pontos citados.

**Próximo passo sugerido:** começar pelo **Bloco A** (bug latente real, baixo risco) com o teste A0 em RED.
