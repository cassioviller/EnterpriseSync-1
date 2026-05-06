# Relatório de Auditoria — Módulos de Apoio

**Task #18 — Auditoria + manual dos módulos de apoio**
**Tenant:** Construtora Alfa (`admin@construtoraalfa.com.br`)
**Data:** 06/05/2026
**Escopo:** Dashboard, CRM, Métricas, Catálogo (Insumos/Serviços), Estoque/Almoxarifado, Frota, Alimentação, Portal do Cliente

---

## Metodologia

1. **Smoke test automatizado** (`scripts/smoke_test_modulos_apoio.py`) — login como admin Alfa, GET nas rotas principais de cada módulo, classificação por status HTTP, tempo de resposta, presença de tracebacks ou "Internal Server Error" no HTML.
2. **Inspeção manual de templates** das 8 áreas para apurar consistência visual com `base_completo.html`, contraste, cards, navegação e responsividade declarada.
3. **Revisão de fluxos principais** (criar/editar/excluir/listar) por leitura cruzada de views + templates, comparando o comportamento descrito nos handlers com o que o usuário enxerga.
4. **Consultas read-only ao banco** para confirmar estado de dados sensíveis (token de portal, presença de veículos, restaurantes ativos).

> Nesta task **não foram corrigidos bugs**, **não foi alterada a lógica de negócio** e **não foi rodado nenhum POST destrutivo no demo Alfa** — apenas leituras e descrições. Todos os achados abaixo são para servir de base de novas tasks de correção.

---

## Resultado do smoke test

Todas as **41 rotas** testadas responderam **sem 5xx** e **sem traceback no HTML**. Tempos de resposta entre 9 ms e 115 ms. IDs descobertos no demo: `obra=25`, `lead=109`, `servico=46`, `insumo=93`, `alm_item=20`, `funcionario=37`. Casos a comentar:

| Rota | Status | Observação |
|------|--------|------------|
| `/alimentacao/dashboard` | 302 | Redireciona — verificar se o destino é a tela esperada (`/alimentacao` ou `/alimentacao/lancamentos`). Pode ser intencional, mas o link no menu sugere uma página própria. |
| `/frota/<veiculo_id>` e `/frota/<veiculo_id>/editar` | SKIP | Nenhum **veículo** cadastrado no demo Alfa — smoke não conseguiu descobrir ID. **Achado de dados** (ver abaixo). |
| `/alimentacao/restaurante/<id>` | SKIP | Smoke não conseguiu descobrir ID via scrape do HTML; o demo possui o restaurante "Bom Prato" (id=10) — ajustar smoke para descobrir via lista de restaurantes. |
| `/portal/obra/<token>` | SKIP | Nenhuma obra do demo tem `token_cliente` preenchido (apesar de 3 terem `portal_ativo=True`). **Achado funcional** (ver abaixo). |

O log da aplicação durante o smoke test não registrou exceções não tratadas.

---

## Achados por módulo

A severidade segue: **Crítico** = bloqueia uso ou perde dado / **Alto** = funcionalidade importante quebrada ou inconsistente / **Médio** = afeta UX significativamente / **Baixo** = cosmético ou edge case.

### 1. Dashboard — `/dashboard`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Médio | O **circuit breaker** entra em modo degradado depois de 2 falhas seguidas e devolve `{"error": "Dashboard temporariamente indisponível"}`. Em ambientes lentos, o usuário pode ver mensagem genérica sem instrução. | Forçar timeout em consulta pesada e abrir `/dashboard` | Renderizar uma tela amigável (banner amarelo) em vez de retornar dict; instruir "tente novamente em 1 minuto". |
| Médio | Quando o `admin_id` não pode ser resolvido, o dashboard responde **HTTP 403** seco (`abort(403)`). Sem mensagem explicando o motivo, o usuário pensa que não tem permissão. | Logar como usuário com sessão corrompida | Página dedicada explicando o problema e pedindo logout/login. |
| Baixo | Filtros por **obras_ids** são multi-select sem chip visual de "filtros ativos" — usuário pode esquecer que está filtrando. | Aplicar filtro e navegar para outra rota e voltar | Mostrar resumo "3 obras filtradas — limpar". |

### 2. CRM — `/crm/`, `/crm/lista`, `/crm/cadastros`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Médio | A coluna **Valor total** no kanban soma `valor_proposta` apenas dos leads visíveis na tela; o totalizador **não é recalculado** quando filtros de URL são aplicados — pode confundir o usuário. | `/crm/?busca=teste` e comparar com `/crm/` | Recalcular após `_aplicar_filtros` para refletir a visão filtrada. |
| Médio | Mover lead para **"Perdido"** sem motivo cadastrado bloqueia a gravação, mas a regra só está no `_salvar_lead` (form). O drag-and-drop kanban (`/crm/<id>/mudar_status`) não exige motivo, deixando o lead Perdido sem justificativa. | Cadastros vazios em "Motivos de Perda" → drag para coluna Perdido | Padronizar a regra: kanban também exigir motivo via modal. |
| Baixo | A rota `/crm/cadastros` é **uma única página** com 6 abas (Origens, Cadências, Situações, Motivos de Perda, Tipos de Material, Tipos de Obra). Em telas pequenas o switch entre abas não é óbvio. | `/crm/cadastros` no celular | Considerar **bottom-sheet** ou seções colapsáveis. |
| Baixo | `valor_proposta` pode ser `NULL`; o kanban trata como `0` (`Decimal('0')`) mas a lista pode mostrar **vazio** dependendo da macro. Inconsistência visual. | Lead novo sem valor | Padronizar exibição como "—" em ambos. |

### 3. Métricas — `/metricas/*`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | **Não há link no menu principal `base_completo.html`** para `/metricas/*`. O acesso só ocorre por URL direta ou via outros templates internos (`metricas/funcionarios.html`, `metricas/divergencia_servico.html`). O `templates/base.html` legado tinha o link, mas o tema atual é o `_completo`. | `grep "metricas\." templates/base_completo.html` retorna vazio | Adicionar item "Métricas" (ou "Produtividade") no menu superior, próximo de Cronograma. |
| Alto | A ação **"Aplicar como referência"** (`/metricas/servico/aplicar-referencia`) sobrescreve o `coeficiente_padrao` dos insumos do tipo mão-de-obra **sem confirmação explícita** com lista do que será alterado. Usuário pode mudar coeficientes em massa por engano. | `/metricas/servico` → botão "Aplicar como referência" | Mostrar preview ("X coeficientes serão atualizados de A para B") antes de confirmar. |
| Médio | Em demos com poucos dados, `produtividade_por_servico` pode falhar silenciosamente e flashar **"Erro ao calcular métricas"** sem detalhar o que faltou (RDO finalizado? horas de mão-de-obra? quantidade entregue?). | `/metricas/servico` em obra sem RDO finalizado | Mensagem específica: "Sem RDOs com mão-de-obra e quantidade no período X..Y". |
| Médio | `/metricas/funcionarios` carrega cards cinza para todos os ativos sem RDO no período, **mais** o cálculo de top-3 RDOs problemáticos por funcionário. Em tenants grandes pode ser lento na primeira chamada. | `/metricas/funcionarios?data_inicio=...&data_fim=...` em tenant grande | Paginar a lista de cinzas; cachear o cálculo de top-3 por (admin_id, período). |
| Baixo | A função `_metricas_required` é um decorator interno — se o usuário não tiver permissão, o comportamento (403/redirect/flash) precisa estar documentado no manual. | Logar com usuário sem perfil de métricas | Documentar na seção "Como acessar" do capítulo. |

### 4. Catálogo — `/catalogo/insumos`, `/catalogo/servicos`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Médio | O catálogo **não está no menu superior próprio** — fica dentro do dropdown "Cadastros" de `base_completo.html` (linhas ~1106 e ~1109). Para empresas que usam o catálogo intensivamente, o caminho é pouco descobrível. | Olhar a barra de menu — não há "Catálogo" | Promover para item top-level ou criar dropdown "Catálogo" ao lado de "Cadastros". |
| Médio | A nova **vigência de preço** (`/catalogo/insumos/<id>/preco`) encerra a anterior automaticamente, mas a tela não exibe um diff "Preço sai de R$ X para R$ Y, vigente desde DD/MM" antes de salvar — usuário pode duplicar registros por engano. | Cadastrar preço novo sem trocar a data | Mostrar preview e exigir confirmação se a vigência for igual à existente. |
| Baixo | O **template de cronograma vinculado** ao serviço só é instanciado em obras criadas **depois** do vínculo. Não há aviso disso na tela `/catalogo/servicos/<id>/composicao`. | Vincular template e abrir obra antiga | Mostrar nota explicativa no card "Cronograma Padrão". |
| Baixo | `recalcular_servico_preco` é chamada após cada add/edit/excluir de composição, mas o resultado não é exibido como animação/feedback — só recarrega a página. Pequena melhoria de UX. | Adicionar item de composição | Mostrar toast "Preço recalculado: R$ X". |

### 5. Estoque / Almoxarifado — `/almoxarifado/*`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | O arquivo `almoxarifado_views.py` é um **god-file de ~140 KB** com dashboard, CRUD de itens/categorias/fornecedores, entrada/saída/devolução, APIs de consulta, processamento e relatórios. Manutenção difícil; risco de regressão a cada alteração. | `wc -c almoxarifado_views.py` | Refatorar em sub-blueprints (`almoxarifado/itens.py`, `almoxarifado/movimentos.py`, `almoxarifado/api.py`, `almoxarifado/relatorios.py`). |
| Médio | `estoque_minimo` em branco é **tratado como 0** no dashboard, então itens recém-cadastrados nunca aparecem em "Estoque baixo" até o usuário definir o mínimo. Pode dar falsa sensação de tudo OK. | Cadastrar item sem mínimo e esvaziar estoque | No formulário de item, exigir o mínimo ou marcar visualmente "sem mínimo definido". |
| Médio | O **dashboard re-itera todos os itens em Python** para calcular estoque baixo (loop em `AlmoxarifadoItem.query.all()` com sub-queries por item). Em tenants com 1000+ itens isso vira um N+1 pesado. | Cadastrar 500 itens e abrir `/almoxarifado/` | Substituir por uma única query agregada com `LEFT JOIN` em `AlmoxarifadoEstoque`. |
| Médio | A tela de **saída** carrega **todos os funcionários ativos e todas as obras ativas** num único `<select>`. Em tenants grandes vira combo gigante. | `/almoxarifado/saida` em tenant com 200 funcionários | Trocar por componente de busca (autocompletar). |
| Baixo | APIs públicas (`/almoxarifado/api/item/<id>`, `/api/lotes-disponiveis/<id>`, `/api/estoque-disponivel/<id>`) retornam **JSON 200/401/404** mas não documentam claramente qual front consome cada uma — risco de quebrar templates ao alterar a API. | `grep "/almoxarifado/api" templates/` | Comentar no topo de cada handler quais templates dependem dela. |

### 6. Frota — `/frota/*`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | **Demo Alfa não tem nenhum veículo cadastrado** (`SELECT COUNT(*) FROM veiculo` retornou 0). O smoke test e o usuário que entrar na demo vão ver dashboard zerado. Achado de **dados** — não de código. | `/frota/` no demo Alfa | Adicionar 2-3 veículos no seeder do demo (ex.: HR, Saveiro, Hilux) com usos e despesas para popular o TCO. |
| Médio | **Passageiros** são gravados como **CSV** dentro do registro (`passageiros_frente='3,7,12'`). Quebra o ORM (não há relação) e impede consultas tipo "em quantos usos o funcionário X foi passageiro". | `grep "passageiros_frente" frota_views.py` | Modelar como tabela associativa `frota_utilizacao_passageiros (utilizacao_id, funcionario_id, posicao)`. |
| Médio | A rota `/frota/<id>/deletar` está marcada como POST mas não há confirmação dupla nem suporte a "soft-delete vs. exclusão real" — o handler marca `ativo=False`, o que é bom, mas o botão diz "Excluir" e induz a achar que apaga. | `/frota/` → "Excluir" | Renomear para "Desativar" e mover "Excluir definitivamente" para um menu secundário (apenas para veículos sem histórico). |
| Baixo | Os filtros do dashboard são `tipo`, `data_inicio`, `data_fim`, `status` (default `ativo`). Não há filtro por **obra**, embora `FrotaUtilizacao` tenha `obra_id`. | `/frota/dashboard` querendo TCO de uma obra | Adicionar `?obra_id=` ao filtro. |
| Baixo | Cálculo `total_km` usa apenas `FrotaUtilizacao.km_percorrido`. Se o usuário não preencher `km_final`, esse campo fica `0` e o **custo médio/km** vira infinito (mas o handler protege com `if total_km > 0`). | Cadastrar uso sem KM final | Validar no formulário que `km_final >= km_inicial` ou tornar `km_final` obrigatório. |

### 7. Alimentação — `/alimentacao/*`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Alto | Coexistem **duas telas de novo lançamento**: V1 (`/alimentacao/lancamentos/novo`) e V2 (`/alimentacao/lancamentos/novo-v2`), ambas linkadas no menu. Risco de cadastros divergentes (V1 ratea por funcionário, V2 detalha por linha). | Menu → "Alimentação" mostra os dois itens | Marcar V1 como **legado** no menu (ícone diferente) ou esconder atrás de uma flag. |
| Médio | `/alimentacao/dashboard` responde **302** no smoke; precisa investigar se o redirect é desejado. O item de menu sugere uma tela própria. | `/alimentacao/dashboard` | Confirmar destino do redirect e ou fazer a tela renderizar de fato, ou apontar o menu direto para o destino. |
| Médio | Em **V2** a quantidade vai para `int(qtd_raw)` sem validação de máximo. Um valor absurdo (`9999`) gera subtotal estourado e contas a pagar erradas. | V2 → quantidade 9999 num item de R$ 25 | Validar limite razoável (1..200) com mensagem amigável. |
| Médio | A associação `alimentacao_funcionarios_assoc` é populada via `INSERT` direto com `text(...)` em vez de relação SQLAlchemy. Foge do padrão do resto do projeto e dificulta auditoria/rollback. | `grep "INSERT INTO alimentacao_funcionarios_assoc" alimentacao_views.py` | Mapear como `relationship` com `secondary=` no modelo. |
| Baixo | Vários templates próximos: `lancamento_novo.html` × `lancamento_novo_v2.html`, `lancamentos_lista.html`, `restaurantes_lista.html`, `itens_lista.html`. Documentar qual é o canônico no `manual/`. | `ls templates/alimentacao/` | Ver capítulo do manual recém-criado. |

### 8. Portal do Cliente — `/portal/obra/<token>`

| Severidade | Descrição | Reproduzir | Sugestão |
|------------|-----------|------------|----------|
| Crítico | No demo Alfa, **3 obras têm `portal_ativo=True` e `token_cliente=NULL`** simultaneamente. Sem token, a URL não pode ser montada e o cliente nunca acessa, embora o sistema mostre o portal como "ativo". | `SELECT id, nome, portal_ativo, token_cliente FROM obra WHERE portal_ativo=True` | Garantir que ao ativar o portal o handler **gere o token** (`secrets.token_urlsafe(32)`) se estiver vazio; bloquear "ativo sem token" no banco com `CHECK`. Considerar back-fill nos demos. |
| Alto | O template `portal/portal_obra.html` tem **~1300 linhas** num único arquivo, com galeria, cronograma, RDOs, fotos, mapas de concorrência e formulários de aprovação/comprovante. Manutenção difícil e renderização lenta em obras grandes. | `wc -l templates/portal/portal_obra.html` | Quebrar em parciais (`_resumo.html`, `_rdos.html`, `_compras.html`, `_comprovante.html`) com `{% include %}`. |
| Alto | O token de portal trafega pela URL pública e não tem **validade** nem **revogação simples** na UI — só desativando o portal. Se o link vazar, o tenant precisa abrir a obra, desativar e reativar (que pode ou não regenerar o token, ver achado anterior). | `/obras/detalhes/<id>` | Botão "Regenerar Token" explícito; opcional: timestamp `token_expira_em`. |
| Médio | Uploads de comprovante vão para `static/uploads/comprovantes/` e são servidos pela mesma rota estática do Flask. **Sem validação de tamanho** nem antivírus, e o nome inclui apenas `secure_filename` — usuário pode subir PDFs grandes que enchem o disco. | `/portal/obra/<token>/comprovante` upload de arquivo grande | Limite de tamanho (`MAX_CONTENT_LENGTH`), prefixo com hash, e mover para `/var/data/comprovantes` fora de `static/`. |
| Baixo | O acesso bem-sucedido grava `obra.ultima_visualizacao_cliente = now()` mas não há histórico — só o último timestamp. Para auditoria de "quantas vezes o cliente abriu" perde-se informação. | Acessar `/portal/obra/<token>` várias vezes | Tabela `PortalAcessoLog (obra_id, ip, user_agent, criado_em)`. |
| Baixo | A tela `portal_inativo.html` é mostrada quando o portal está desativado, mas continua revelando o **nome da obra** e **branding do tenant** ao visitante. Pode ser considerado vazamento mínimo de informação. | Desativar portal e abrir o link | Mostrar apenas mensagem genérica "Portal indisponível" sem dados. |

---

## Resumo executivo

| Módulo | Achados Crítico | Alto | Médio | Baixo |
|--------|-----------------|------|-------|-------|
| Dashboard | 0 | 0 | 2 | 1 |
| CRM | 0 | 0 | 2 | 2 |
| Métricas | 0 | 2 | 2 | 1 |
| Catálogo | 0 | 0 | 2 | 2 |
| Estoque/Almoxarifado | 0 | 1 | 3 | 1 |
| Frota | 0 | 1 | 2 | 2 |
| Alimentação | 0 | 1 | 3 | 1 |
| Portal do Cliente | **1** | 2 | 1 | 2 |
| **Totais** | **1** | **7** | **17** | **12** |

**Prioridades recomendadas (ordem de tratamento):**

1. **Portal do Cliente — token NULL com portal ativo** (Crítico): a obra "ativa" não pode ser acessada pelo cliente. Adicionar geração automática do token e back-fill no demo.
2. **Métricas sem link no menu** (Alto): impede descoberta da feature; adicionar item ao menu principal.
3. **Métricas — confirmação ao aplicar referência** (Alto): risco de mudar coeficientes em massa por engano.
4. **Almoxarifado — refatorar god-file** (Alto): manutenção bloqueada; quebrar em sub-blueprints.
5. **Frota — popular o demo Alfa com veículos** (Alto, dado): dashboard TCO zerado prejudica a percepção da feature.
6. **Alimentação — esclarecer V1 × V2 no menu** (Alto): risco de cadastros inconsistentes.
7. **Portal — refatorar template de 1300 linhas** (Alto) e **regenerar token explícito** (Alto).

Os demais achados (médios e baixos) podem ser agrupados em tasks de melhoria contínua por módulo.

---

## Anexos

- **Smoke test:** `scripts/smoke_test_modulos_apoio.py`
- **Manuais (capítulos preenchidos nesta task):**
  - `manual/20_dashboard.md`
  - `manual/28_crm.md`
  - `manual/29_metricas.md`
  - `manual/30_catalogo.md`
  - `manual/31_estoque.md`
  - `manual/32_frota.md`
  - `manual/33_alimentacao.md`
  - `manual/34_portal_cliente.md`
- **Auditoria irmã (módulos críticos):** `manual/relatorios/auditoria_modulos_criticos.md`
