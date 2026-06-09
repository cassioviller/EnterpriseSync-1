# Issues de remediação — saúde do app

Issues grabbable derivadas do plano
`docs/superpowers/plans/2026-06-08-remediacao-saude-app-plan.md`. Cada arquivo é
o corpo de uma issue (pronto para colar no GitHub). Ordem sugerida por
prioridade/risco.

| # | Issue | Prioridade | Esforço | Risco | Depende de |
|---|-------|-----------|---------|-------|-----------|
| A | [Cache de instância ORM](A-cache-instancia-orm.md) | P1 | baixo | baixo | — |
| B | [Falhas silenciosas → sinais acionáveis](B-falhas-silenciosas-acionaveis.md) | P2 | médio | baixo | parte de D |
| C | [create_app() único](C-create-app-unico.md) | P3 | médio | médio | — |
| D | [Fonte única do plano de contas (+ADR)](D-fonte-unica-plano-contas.md) | P4 | médio | médio | — |
| E | [Precificação única](E-precificacao-unica.md) | P5 | médio | médio | — |
| F | [N+1 de config por request](F-nmais1-config-por-request.md) | P6 | baixo | baixo | A (padrão) |
| G | [Onboarding / prontidão do tenant](G-onboarding-prontidao-tenant.md) | P7 | médio | baixo | B |
| H | [Infra de testes + migrações](H-infra-testes-migracoes.md) | P8 | baixo | baixo | C |

**Independentes (paralelizáveis):** A, C, D, E, F.
**Começar por:** A (bug latente real, baixo risco, teste RED claro).

Para abrir no GitHub depois de autenticar (`gh auth login`), cada arquivo vira
uma issue via `gh issue create --title ... --body-file <arquivo>`.
