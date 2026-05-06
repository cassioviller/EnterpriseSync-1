# Relatório de Auditoria — Módulos Críticos

**Task #17 — Auditoria + manual dos módulos críticos**
**Tenant:** Construtora Alfa (`admin@construtoraalfa.com.br`)
**Data:** 06/05/2026
**Escopo:** Obras, RDO, Cronograma, Financeiro, Propostas, Folha de Pagamento, Funcionários

---

## Metodologia

1. **Smoke test automatizado** (`scripts/smoke_test_modulos_criticos.py`) — login como admin Alfa, GET nas rotas principais de cada módulo, classificação por status HTTP, tempo de resposta, presença de tracebacks ou "Internal Server Error" no HTML, página quase vazia.
2. **Inspeção manual dos templates** dos 7 módulos para apurar consistência visual com `base_completo.html`, contraste, cards, alinhamento e responsividade declarada.
3. **Revisão de fluxos principais** (criar/editar/excluir/listar) por leitura cruzada de views + templates, comparando o comportamento descrito nos handlers com o que o usuário enxerga.

> Nesta task **não foram corrigidos bugs**, **não foi alterada a lógica de negócio** e **não foi rodado nenhum POST destrutivo no demo Alfa** — apenas leituras e descrições. Todos os achados abaixo são para servir de base de novas tasks de correção.

---

## Resultado do smoke test

Todas as 45 rotas testadas responderam **sem 5xx** e **sem traceback no HTML**. Nenhuma página em branco crítica foi encontrada. IDs descobertos no demo: `obra=25`, `funcionario=37`, `rdo=90`, `proposta=30`. Tempos médios entre 6 ms e 250 ms. Casos a comentar:

| Rota | Status | Observação |
|------|--------|------------|
| `/obras/25/curva-avanco` | 200 | Resposta JSON, não HTML — corretamente classificada como "página quase vazia". É um endpoint de dados consumido pelo Chart.js do detalhes da obra; **não é bug**. |
| `/financeiro/contas-pagar/nova` | 302 | Redireciona para `/financeiro/contas-pagar` (uso do modal). **Não é bug**, mas vale documentar. |
| `/propostas/dashboard` | 302 | Redireciona para `/propostas/`. **Não é bug**. |
| `/propostas/listar` | 302 | Idem. |
| `/equipe` | 308 | Redirect com trailing slash. **Não é bug**. |

O log da aplicação durante o smoke test não registrou exceções não tratadas.

---

## Achados por módulo

A severidade segue: **Crítico** = bloqueia uso ou perde dado / **Alto** = funcionalidade importante quebrada ou inconsistente / **Médio** = afeta UX significativamente / **Baixo** = cosmético ou edge case.

### 1. Obras — `/obras`, `/obras/detalhes/<id>`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Médio | A página de **detalhes da obra** tem três templates (`detalhes_obra.html`, `detalhes_obra_simples.html`, `detalhes_obra_profissional.html`) coexistindo. Não está claro qual é o canônico, e o usuário pode ver layouts diferentes dependendo da rota chamada. | Comparar `templates/obras/detalhes_obra*.html` | Definir um único template oficial; migrar e remover os demais. |
| Médio | **Curva de avanço** depende de RDO finalizado e da função `calcular_progresso_geral_obra_v2`. Em obras sem RDO finalizado, o card no detalhes fica vazio sem mensagem amigável (o endpoint retorna `pontos: []`, mas o front não exibe explicação). | Criar obra nova sem RDO e abrir `/obras/detalhes/<id>` | Mostrar placeholder "Aguardando o primeiro RDO finalizado para gerar a curva". |
| Baixo | Botão "Toggle Status" está em rota separada de "Excluir" e nem sempre aparece com o mesmo estilo no card. | `/obras` | Padronizar grupo de ações no card. |

### 2. RDO — `/funcionario/rdo/consolidado`, `/rdos`, `/rdo/<id>`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | Existem **dois templates de criação** (`templates/rdo/novo.html` e `templates/rdo/novo_backup.html`). Risco de evoluir só um e o outro estar acessível por rota legada. | `ls templates/rdo/` | Remover `novo_backup.html` ou marcá-lo `.bak` fora do diretório. |
| Alto | A rota `/rdo/novo` está duplicada em `views/rdo.py` (linhas 468 e 2088 ambas com `@main_bp.route('/rdo/novo')`). Flask usa a primeira registrada e ignora silenciosamente a segunda; isso pode mascarar features. | `grep -n "/rdo/novo" views/rdo.py` | Remover a duplicata; usar nomes de função distintos. |
| Médio | A rota `/rdo/<int:id>` aparece registrada em duas funções diferentes (linhas 921 e 3237 de `views/rdo.py`) — Flask reclama no boot ou ignora o segundo handler. | `grep -n "@main_bp.route('/rdo/<int:id>')" views/rdo.py` | Consolidar em um único handler. |
| Médio | A tela consolidada de RDO carrega muitos serviços/sub-atividades em uma página só; em obras grandes (>20 serviços) pode ficar lenta. | `/funcionario/rdo/consolidado` em obra grande | Lazy-load por seção / colapsar serviços por padrão. |
| Baixo | O fluxo **Excluir RDO** existe em duas rotas: `/rdo/excluir/<id>` (linha 402) e `/rdo/<id>/excluir_old` (linha 1506). Ambíguo. | `grep "excluir" views/rdo.py` | Remover a `_old`. |

### 3. Cronograma — `/cronograma/`, `/cronograma/obra/<id>`, `/cronograma/produtividade`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Médio | O **drag-and-drop** depende de Sortable.js carregado em `base_completo.html`; em telas onde o `base_completo` não foi adotado (ex.: páginas legacy abertas em outra aba), o reorder não funciona. | Verificar carregamento de Sortable nas páginas `/cronograma/*` | Garantir import explícito por página de cronograma. |
| Médio | **Recalcular** sobrescreve datas manuais de tarefas com predecessora alterada sem aviso. Usuário pode perder ajustes. | `/cronograma/obra/<id>` → "Recalcular" | Diálogo de confirmação listando o que vai mudar. |
| Baixo | Painel de produtividade (`/cronograma/produtividade`) mostra cards numéricos sem comparação visual (gráfico). | `/cronograma/produtividade` | Adicionar mini-gráficos ao card. |

### 4. Financeiro — `/financeiro/`, `/financeiro/contas-pagar`, `/financeiro/fluxo-caixa`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | O banner "Versão V2 ativa" em `/financeiro/contas-pagar` direciona para Gestão de Custos, mas a tela de **"+ Nova Conta a Pagar"** continua disponível como botão principal no topo. Mensagem mista para o usuário. | `/financeiro/contas-pagar` em ambiente V2 | Em modo V2, transformar o botão principal em "Despesa via Gestão de Custos" e deixar o lançamento direto como secundário. |
| Médio | Filtros do `/financeiro/contas-pagar` não têm botão "Aplicar"; usam `onchange="this.form.submit()"`. Em mobile, mudar dois selects gera duas requisições. | `/financeiro/contas-pagar` no celular | Trocar por botão "Filtrar" único. |
| Médio | `/financeiro/contas-pagar/nova` redireciona em vez de ser uma página própria (modal-only). Quem chega por link/bookmark perde o contexto do modal. | Acessar `/financeiro/contas-pagar/nova` direto | Aceitar a rota e abrir o modal automaticamente, ou renderizar página dedicada. |
| Baixo | A coluna **Vencidas** no resumo usa `bg-danger` com texto branco mas o **valor** vem de macro `brl` que pode renderizar zero como "R$ 0,00" em estilo idêntico ao positivo. Sem destaque visual quando há vencidas. | `/financeiro/contas-pagar` com contas em atraso | Adicionar ícone/badge no card. |

### 5. Propostas — `/propostas/`, `/propostas/nova`, `/propostas/<id>`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | A pasta `templates/propostas/` tem **5 variantes de PDF** (`pdf_estruturas_vale*.html`, `pdf.html`). Sem documentação clara de qual é usado pela rota `/propostas/<id>/pdf`. Risco de evoluir uma versão errada. | `ls templates/propostas/pdf*` | Consolidar em um template único; arquivar legados. |
| Alto | Existem dois templates de listagem (`lista_propostas.html` e `listar.html`) e dois de criação (`nova.html` e `nova_proposta.html`); a coexistência confunde manutenção. | `ls templates/propostas/` | Definir versões oficiais e remover obsoletos. |
| Médio | Em **Nova Proposta**, o seletor de cliente usa input livre + autocomplete `api/clientes`. Se o usuário digitar errado e enviar, cria-se um cliente novo sem aviso explícito. | `/propostas/nova` com nome novo | Diálogo "Cliente não encontrado, deseja criar?". |
| Médio | A rota pública do portal do cliente (`/propostas/cliente/<token>`) não tem rate-limit visível. Token vazado pode ser rebatido externamente. | Inspeção do código | Adicionar rate-limit por IP/token. |
| Baixo | Botão "Voltar" no topo do `/propostas/nova` leva a `/propostas/` (lista). Após salvar, redireciona para `/propostas/<id>`. Sem breadcrumb. | `/propostas/nova` | Adicionar breadcrumb consistente. |

### 6. Folha de Pagamento — `/folha/dashboard`, `/folha/relatorios`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | O botão **"Processar Folha"** dispara `processarFolha(...)` via JavaScript inline (POST sem confirmação visível na UI). Em produção, um clique acidental processa a competência inteira. | `/folha/dashboard` → clique em "Processar [mês]" | Modal de confirmação obrigatório antes do POST. |
| Alto | O **"Reprocessar"** sobrescreve cálculos sem indicar quais holerites já foram emitidos. Risco de gerar holerites diferentes do que foi entregue ao funcionário. | `/folha/dashboard` com folha já processada | Mostrar lista de holerites já gerados e exigir confirmação extra. |
| Médio | Quando **parâmetros legais não estão configurados**, o dashboard mostra alerta e o botão "Configurar Parâmetros". Mas o **botão "Processar Folha" continua clicável** — gera erro silencioso. | Tenant sem parâmetros legais | Desabilitar "Processar" enquanto não houver parâmetros. |
| Médio | O seletor de **Competência** depende de `competencias` vindo do backend. Em meses sem dados, fica vazio sem mensagem. | Tenant novo | Mostrar "Nenhuma competência disponível — cadastre funcionários e bata ponto primeiro". |
| Baixo | Holerite PDF (`/folha/relatorios/holerite/<id>`) abre na mesma aba — usuário perde o filtro do dashboard. | Clicar em "Holerite PDF" | Abrir em nova aba (`target=_blank`). |

### 7. Funcionários — `/funcionarios`, `/funcionario_perfil/<id>`, `/ponto`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | A tela `/funcionarios` usa **3 modais simultâneos** ("Novo", "Lançamento Múltiplo", "Sábados e Domingos"). O modal de novo funcionário tem muitos campos e em mobile fica cortado. | `/funcionarios` no celular | Transformar "Novo Funcionário" em página dedicada (`/funcionarios/novo`). |
| Médio | **Excluir funcionário** com histórico de ponto retorna erro de FK no banco e a mensagem para o usuário é genérica. | Tentar excluir funcionário com ponto | Capturar a exceção e oferecer "Inativar em vez de excluir". |
| Médio | A rota `/equipe` retorna **308 redirect** (trailing slash). Links que não redirecionam (alguns clientes HTTP) podem quebrar. | `curl http://localhost:5000/equipe` | Aceitar ambas as formas (`/equipe` e `/equipe/`). |
| Médio | O perfil do funcionário (`/funcionario_perfil/<id>`) exibe KPIs do mês corrente por padrão; não há atalho rápido para "Mês Anterior". | `/funcionario_perfil/<id>` | Botões pré-prontos "Mês atual / Mês anterior / 90 dias". |
| Baixo | Card do funcionário na lista usa `fas fa-user-plus` no botão de novo, mas usa `fas fa-plus` em outro local — inconsistência cosmética. | `/funcionarios` | Padronizar ícones. |

---

## Itens transversais (afetam múltiplos módulos)

| Severidade | Descrição |
|------------|-----------|
| Alto | **Templates duplicados/legados** em vários módulos (RDO, Propostas, Obras). Aumentam risco de regressão. Recomendado: rodada dedicada para consolidar e arquivar. |
| Médio | **Mensagens de erro genéricas** em vários POSTs (ex.: ao tentar excluir registro com FK). Usuário recebe "Erro ao excluir" sem direção. |
| Médio | **Confirmações de operações destrutivas** (excluir RDO, processar folha, recalcular cronograma) variam entre alert nativo, modal Bootstrap e nada. Padronizar com componente único. |
| Baixo | **Inconsistências cosméticas** de ícones, espaçamentos e cores em telas migradas vs. legadas. Esperar a próxima rodada visual com screenshots para mapear ponto-a-ponto. |

---

## Próximos passos sugeridos (para o usuário priorizar)

1. **Limpar templates duplicados** — RDO (`novo_backup.html`), Propostas (PDFs), Obras (3 detalhes).
2. **Corrigir rotas duplicadas em `views/rdo.py`** (`/rdo/novo`, `/rdo/<id>`).
3. **Modal de confirmação obrigatório** em "Processar/Reprocessar Folha".
4. **Desabilitar "Processar Folha"** enquanto parâmetros legais não estiverem configurados.
5. **Mensagem "inativar em vez de excluir"** para funcionário com histórico.
6. **Banner V2 de Contas a Pagar** — esconder o botão de lançamento direto quando o modo V2 estiver ativo.
7. **Placeholder amigável** na curva de avanço de obras sem RDO.
8. **Rodada de revisão visual com screenshots** depois das correções acima — ela é o próximo passo natural depois desta auditoria textual.
