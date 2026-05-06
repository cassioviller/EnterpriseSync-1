# Dashboard

O **Dashboard** (`/dashboard`) é a tela inicial do administrador depois do login. Ele consolida em uma única página os indicadores de **funcionários ativos**, **obras em andamento**, **financeiro do período**, **produtividade** e **alertas operacionais**, com filtros de data e de obras.

## Para que serve

- Dar uma visão única, em tempo real, do estado do negócio (pessoas, obras, dinheiro).
- Permitir filtrar por **período** e por **conjunto de obras** para comparações.
- Servir de ponto de entrada para os módulos detalhados (clicar num KPI leva ao módulo correspondente).
- Bloquear funcionários do dashboard administrativo — eles são redirecionados para `/funcionario/rdo/consolidado`.

## Como acessar

- **Login** com usuário `ADMIN` → o sistema redireciona automaticamente para `/dashboard`.
- Pelo logo no canto superior esquerdo de qualquer tela.
- Usuários `SUPER_ADMIN` são redirecionados para o **Super Admin Dashboard**.
- Usuários `FUNCIONARIO` são bloqueados e enviados para a tela consolidada de RDO (regra de segurança).

## Fluxos principais

### 1. Visão padrão (sem filtros)

1. Ao abrir `/dashboard`, o sistema usa por padrão o **mês corrente** (`primeiro dia → último dia`).
2. Carrega:
   - **Funcionários ativos** (contagem em `Funcionario` com `ativo=True`).
   - **Obras em andamento** (cards com progresso).
   - **Custos do período** (mão de obra, materiais, alimentação, transporte, fretes).
   - **Receitas do período** (faturas emitidas).
   - **Alertas** (CNH a vencer, obras sem RDO há X dias, contas a pagar vencidas).
3. Cada card é clicável e leva ao módulo de origem.

### 2. Filtrar por período e obra

1. No topo da tela, ajuste **Data Início** e **Data Fim**.
2. Marque uma ou mais **obras** no seletor multi-select.
3. Clique em **"Filtrar"** — a URL passa a refletir os filtros (`?data_inicio=...&data_fim=...&obras_ids=25&obras_ids=26`), permitindo salvar o link.
4. Para voltar ao padrão, clique em **"Limpar filtros"**.

### 3. Drill-down a partir do KPI

1. Clique no card **Funcionários** → vai para `/funcionarios`.
2. Card **Obras em andamento** → `/obras`.
3. Card **Receitas / Custos** → `/financeiro` ou `/gestao-custos`.
4. **Alertas** → cada alerta leva à tela específica (CNH vence → ficha do funcionário; conta vencida → `/financeiro/contas-pagar`).

### 4. Diagnóstico de tenant

1. Se o cookie de sessão não conseguir resolver o `admin_id` corretamente, o dashboard responde **403 Acesso negado** (proteção multi-tenant).
2. O log da aplicação grava `[SECURITY] Dashboard sem admin_id resolvido` — usado pelo suporte para investigar problemas de login.

## Dicas e cuidados

- O Dashboard tem **circuit breaker** ativo: se houver duas falhas seguidas em consultas pesadas, o módulo entra em modo degradado por 60 s e devolve a mensagem **"Dashboard temporariamente indisponível"** — basta recarregar depois.
- **Não use o Dashboard como relatório oficial** — para fechamento mensal use o módulo Financeiro / Métricas.
- Filtros de obras seguem o tenant: você só vê suas próprias obras (multi-tenant).
- Em telas pequenas, os cards rolam na vertical; alguns gráficos auxiliares podem ficar comprimidos — use o **/metricas/** para análises detalhadas.
- Funcionário que tenta abrir `/dashboard` **sempre** é redirecionado para o consolidado de RDO — comportamento de segurança, não é bug.
