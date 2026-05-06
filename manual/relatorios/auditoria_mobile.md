# Auditoria Mobile — SIGE v9.0 (Task #19)

> Resumo do estado mobile **antes** das correções desta task. Serve como
> referência para futuros ajustes finos.

## Metodologia
Telas inspecionadas com viewport 360–430px (Android comum a iPhone Pro Max),
em modo retrato. Foco nos 5 módulos críticos de uso diário:

1. Obras (`/obras`, `/obras/<id>`)
2. RDO (`/funcionario/rdo/consolidado`, `/rdo/novo`)
3. Cronograma (`/cronograma`, `/cronograma/obra/<id>`)
4. Financeiro (`/financeiro/dashboard`, `/financeiro/contas-pagar`, `/financeiro/contas-receber`)
5. Funcionários (`/funcionarios`)

## Problemas observados

### Globais (atingem todos os módulos)
- **Menu colapsado herdado do Bootstrap** — abre como acordeão dentro da
  navbar; quando o usuário tem ~15 itens com submenus, vira uma rolagem
  cansativa. Sem busca, sem agrupamento visual.
- **Sem atalhos rápidos no rodapé** — funcionário que abre o app no
  caminhão precisa tocar 3 vezes para chegar no RDO.
- **Tabelas com muitas colunas** geram scroll horizontal silencioso (sem
  affordance), induzindo o usuário a achar que faltam dados.
- **Filtros em linha** (data início, data fim, status…) ficam apertados em
  4 colunas no mobile — viram caixas de 70px de largura.
- **Botões em barra de ação** (Novo / Importar / Exportar) ficam todos na
  mesma linha e estouram a largura.
- **Inputs `type="date"` com `font-size:14px`** disparam zoom automático
  no Safari iOS.

### Por módulo

**Obras (`/obras`)**
- Header com título grande + 2 botões na mesma linha já tem media query
  acionando `flex-wrap` em 768px, mas o "Visualização" toggle some em
  telas pequenas porque sai do alinhamento do flex.
- Cards de obra (`obras_moderno.html`) já se reorganizam para 1 coluna,
  mas o `obra-card-subtitle` empilha mal os badges (ficam cortados).

**RDO (`/funcionario/rdo/consolidado`)**
- Listagem usa cards mas o filtro de data + obra ocupa metade da tela
  antes mesmo do primeiro card.
- Em `rdo/novo.html`, os campos de execução de subatividade ficam em
  colunas Bootstrap fixas (col-md-3) que viram col-12 no mobile, mas
  sem espaçamento vertical adequado.

**Cronograma (`/cronograma/obra/<id>`)**
- O Gantt é absolutamente inviável no mobile: largura mínima ~1200px,
  rolagem horizontal sem afford. **Decisão:** no mobile mostrar aviso
  "Visualize em tela maior" + cair na lista hierárquica plana.
- Listagem `/cronograma` já tem cards responsivos — OK.

**Financeiro (`/financeiro/dashboard`)**
- KPIs em `col-md-3` viram 1 coluna no mobile (4 cards empilhados, muito
  scroll). **Decisão:** no mobile mostrar grid 2x2.
- Filtros de data + botão na mesma linha estouram.

**Funcionários (`/funcionarios`)**
- Tabela tem ~7 colunas (foto, nome, função, departamento, telefone,
  status, ações) — não cabe nem com scroll horizontal aceitável.
- **Decisão:** transformar em cards no mobile (foto + nome + função +
  ações).

## Decisões arquiteturais (aplicadas nesta task)

1. **Mobile shell global** no `base_completo.html`:
   - Header fixo simplificado (logo + hamburguer + avatar)
   - **Drawer offcanvas** lateral com menu completo agrupado
   - **Bottom nav fixo** com 5 atalhos: Dashboard, Obras, RDO, Equipe, +Mais
2. **CSS namespace `.sige-mobile-*`** carregado via novo
   `static/css/sige-mobile.css`. Tudo dentro de `@media (max-width: 991px)`.
3. **Padding-bottom: 72px** no `<main>` em mobile para o conteúdo não
   ficar sob o bottom nav.
4. **Tabelas críticas** ganham wrapper `.sige-table-mobile-cards` que
   converte cada `<tr>` em card via CSS quando a tela é estreita.
5. **Cronograma Gantt** desabilitado no mobile com `.sige-mobile-hide`,
   exibindo aviso `.sige-mobile-only-notice`.
6. **Página `/dev/mobile-preview`** standalone para testar telas dentro
   do iframe do Replit (sem precisar de DevTools).

## Não escopo (mantém para tasks futuras)
- Refazer cada formulário linha-a-linha — apenas tratamento global.
- PWA / offline / push notifications.
- Otimização de imagens / lazy load avançado.
- Acessibilidade (WCAG) profunda — só os mínimos (focus visible, alvo de
  toque ≥44px, aria-label nos botões do shell mobile).
