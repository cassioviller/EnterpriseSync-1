# Manual operacional — Ciclo Proposta → Obra → Medido → ContaReceber (Task #94, atualizado #99)

Este manual descreve a regra **vigente** do ciclo comercial/financeiro do
SIGE v9.0 após a refatoração da Task #94 e a reexecução E2E da Task #99
(17/abr/2026).

## Changelog desde a versão da Task #85

| Bloco | Mudou | Origem |
| --- | --- | --- |
| Aprovação de proposta | Agora **emite** `proposta_aprovada` e valida pós-emit que `proposta.obra_id` foi setado | #94 |
| Obra criada via aprovação | Nasce com `OBR####`, `token_cliente`, `portal_ativo=True`, `valor_contrato` e `proposta.obra_id`/`convertida_em_obra=True` setados | #94 |
| ContaReceber | **Não é mais criada na aprovação**. Existe **uma única** CR viva por obra (`origem_tipo='OBRA_MEDICAO'`, `OBR-MED-#####`) atualizada via UPSERT por RDO finalizado / medição quinzenal | #94 |
| Medição quinzenal | Não cria mais `ContaReceber MED-`. Apenas chama `recalcular_medicao_obra` e grava `medicao.conta_receber_id` apontando para a CR única | #94 |
| Snapshot paramétrico | `PropostaItem` e `ItemMedicaoComercial` guardam `custo_unitario`, `lucro_unitario`, `subtotal` no momento da gravação. Mudanças posteriores de preço de insumo **não** alteram propostas antigas | #89 |
| Selector de catálogo | Combobox AJAX nos formulários de Proposta e Medição grava `servico_id` no item; propaga 1:1 para IMC/OSC | #86 |
| Menu V2 | Itens legados (templates de cronograma legados, "Alimentação V1", "Transporte V1", dropdown legado de Serviços) ocultos via `{% if not is_v2_active() %}` em `base_completo.html` | #87 |
| Páginas de erro | `templates/error.html` estende `base_completo.html` e o menu superior **não quebra mais** (#96). | #96 |
| Importar por planilha | Tela `/importacao/` registrada com sucesso no boot; menu lateral mostra o link condicionado a `has_importacao_bp` | #97 |
| Métricas de funcionários | Centralizadas em `services/funcionario_metrics.py`, suportam salaristas (v1) e diaristas (v2). Override por `Funcionario.tipo_remuneracao` tem prioridade sobre `is_v2_active(admin_id)` | #98 |
| Helpers financeiros | `_saldo_seguro*` + `func.coalesce(saldo, valor_original)` evitam 500 em fluxo de caixa / contas a receber com dados legados | #94 |

## Sequência numerada — do superadmin ao portal do cliente (V2)

> Esta sequência cobre o caminho oficial **V2** (`is_v2_active()=True`).
> Em V1 a UI tem itens legados extras; o ciclo funcional é o mesmo.

### 1. Login do administrador

- **Caminho:** abrir o sistema → tela `POST /login`.
- **Layout:** card centralizado com o logo da empresa no topo, dois
  campos verticais e um botão azul largo abaixo. Linha de "Esqueci a
  senha" abaixo do botão (não obrigatória).
- **Campos:** `email` (texto, obrigatório, ex.: `admin.v2@sige.com`);
  `password` (senha, obrigatório). Vazio → mensagem vermelha "Por
  favor, faça login para acessar esta página." sem submeter.
- **Botão:** "Entrar" (azul, full-width).
- **Resultado:** redireciona para `/dashboard` com flash verde de
  boas-vindas. Cookie de sessão é HTTPOnly em produção.

### 2. Cadastro de funcionários

- **Caminho:** menu lateral → "Funcionários" → botão verde "+ Novo
  Funcionário" no canto superior direito.
- **Layout:** formulário em duas colunas, agrupado em blocos: Dados
  pessoais → Dados profissionais → Pagamento e benefícios → Foto.
- **Campos relevantes para o ciclo:**
  - `nome` (texto, obrigatório).
  - `cpf` (texto, obrigatório, único).
  - `data_admissao` (data, obrigatório).
  - `tipo_remuneracao` (dropdown: "Salário"/"Diária"; padrão = tenant).
  - `salario` (numérico, exibido só se tipo=salário).
  - `valor_diaria` (numérico, exibido só se tipo=diária — **regra v2**).
  - `chave_pix` (texto, opcional).
  - `valor_va` (numérico, R$/dia trabalhado, opcional).
  - `valor_vt` (numérico, R$/dia trabalhado, opcional).
- **Botões:** "Salvar" (verde, embaixo) → cria e volta para a lista;
  "Cancelar" (cinza) → volta sem salvar.
- **Resultado:** funcionário aparece na listagem com badge "Mensalista"
  ou "Diarista" (#98) e o "Custo total" do perfil já soma MO + VA + VT
  + Alimentação + Reembolsos + Almoxarifado em posse.
- **Atenção:** se marcar "Diária", **preencher** `valor_diaria` e
  `valor_va`/`valor_vt` por dia. Sem `valor_diaria`, MO sai zero.

### 3. Catálogo de serviços (paramétrico)

- **Caminho:** menu lateral → "Catálogo" → aba "Serviços" → botão "+
  Novo Serviço".
- **Layout:** topo = dados do serviço; meio = composição (lista de
  insumos com coeficiente); rodapé = preço calculado (custo unitário,
  imposto, lucro, preço de venda).
- **Campos:**
  - `nome`, `unidade_medida`, `categoria` (texto/dropdown, obrigatórios).
  - `imposto_pct`, `margem_lucro_pct` (numérico, %).
  - Composição: para cada insumo escolhido — `coeficiente` (qtd por
    unidade do serviço) e `unidade` (snapshot, mig 123).
- **Botões:** "Salvar" → grava; "Recalcular preço" (azul claro) →
  recalcula `preco_venda_unitario` na hora.
- **Resultado:** o card do serviço passa a aparecer no autocomplete dos
  formulários de Proposta e Medição. **Atenção:** se `imposto_pct +
  margem_lucro_pct ≥ 100%`, o cálculo sinaliza "erro" e zera o preço
  (proteção contra divisão por zero).

### 4. Importar funcionários por planilha (#97)

- **Caminho:** menu lateral → "Importar por Planilha" (visível apenas
  se o blueprint `importacao` boot OK; o template usa
  `has_importacao_bp` para esconder o link em caso de falha).
- **Layout:** tela com (1) link para baixar o template Excel oficial,
  (2) input de upload, (3) tabela de pré-visualização, (4) botão
  "Confirmar importação".
- **Resultado esperado:** linhas válidas viram funcionários; linhas com
  erro aparecem em destaque vermelho com a coluna problemática
  identificada. Os custos importados (diária/VA/VT) são agrupados em
  um único `GestaoCustoPai` aberto por categoria por mês (validado por
  `tests/test_agrupamento_diarias_rdo.py`).

### 5. Nova proposta com catálogo + cálculo paramétrico (#86 + #89)

- **Caminho:** menu lateral → "Propostas" → botão verde "+ Nova
  Proposta" no canto superior direito.
- **Layout:** cabeçalho com dados do cliente; corpo com itens da
  proposta (linha por item, repetível); rodapé com BDI, total e botões.
- **Por item:**
  - Combobox "Serviço (catálogo)" (#86) — autocomplete via
    `/catalogo/api/servicos/buscar`. Ao escolher: `descricao`,
    `unidade_medida` e `preco_unitario` são **autopreenchidos** pelo
    `preco_venda_unitario` do serviço.
  - `quantidade_medida` (numérico).
  - `custo_unitario`, `lucro_unitario`, `subtotal` são **calculados
    e congelados** (snapshot mig 124) ao salvar.
  - `servico_id` é gravado em `PropostaItem` para rastreabilidade.
- **Botões:** "Salvar rascunho" (cinza), "Enviar ao cliente" (azul) —
  popula `data_envio` e libera `/propostas/cliente/<token>`.
- **Atenção (snapshot #89):** mudar o preço do insumo **depois** não
  altera propostas já gravadas — a explosão fica congelada (validado
  pelo `test_e2e_orcamento_proposta` fase 4).

### 6. Aprovar proposta → gerar Obra (#94)

- **Caminho admin:** lista de propostas → linha da proposta → botão
  "Aprovar" (verde) → confirmação → status muda para `APROVADA`.
- **Caminho cliente:** link público `/propostas/cliente/<token>` →
  botão "Aprovar proposta" (verde no rodapé) → form de confirmação
  com campo opcional `observacoes_cliente`.
- **O que acontece automaticamente (handlers de `proposta_aprovada`):**
  1. `propagar_proposta_para_obra` cria/recupera Obra com `OBR####`,
     gera `token_cliente`, marca `portal_ativo=True`, popula
     `valor_contrato`, vincula `proposta.obra_id` e
     `convertida_em_obra=True`. **Não cria CR.**
  2. `handle_proposta_aprovada` lança contábil dupla
     (1.1.02.001 / 4.1.01.001) e propaga `PropostaItem → IMC` (e o
     `after_insert` do IMC cria `ObraServicoCusto` pareado).
- **Resultado esperado na tela:** flash verde "Proposta aprovada com
  sucesso" + link para a Obra recém-criada.
- **Atenção (validação pós-emit):** se algo falhar no handler, a tela
  mostra flash de **warning** indicando que a estrutura ficou
  incompleta — reaprovar ou inspecionar logs. Não há mais o caso #85
  de "aprovou e não aconteceu nada".

### 7. Cronograma da obra

- **Caminho:** menu lateral → "Obras" → linha da obra → aba
  "Cronograma" (V2 — `/cronograma/obra/<id>`).
- **Layout:** Gantt interativo com lista hierárquica à esquerda e
  barras temporais à direita. Botões "+ Nova tarefa", "Importar",
  "Recalcular predecessoras".
- **Campos por tarefa:** `nome` (com autocomplete do catálogo),
  `servico_id` (vínculo opcional), `data_inicio`/`data_fim`,
  `predecessora_id`, `percentual_concluido`.
- **Atenção (Issue A — follow-up):** hoje a Obra **nasce sem
  `TarefaCronograma`**. O usuário precisa criar/importar
  manualmente. O recálculo financeiro funciona de qualquer modo
  (fallback por `RDOServicoSubatividade.servico_id`).

### 8. RDO + métricas

- **Caminho:** menu lateral → "RDO" → botão "+ Novo RDO".
- **Por subatividade:** funcionários alocados, horas, quantidade
  produzida.
- **Resultado:** dashboards de produtividade, ranking e índice por
  funcionário vs média da empresa são alimentados por
  `services/funcionario_metrics.py` (#98). Diaristas usam
  `valor_diaria × dias_pagos + (HE/8) × valor_diaria × 1.5`;
  salaristas usam `horas × valor_hora + HE × valor_hora × 1.5`.
- **Quando o RDO vai para `Finalizado`:** dispara o evento
  `rdo_finalizado`, que aciona dois handlers — `lancar_custos_rdo`
  (cria `GestaoCustoFilho`/`CustoObra`) e `recalcular_medicao_apos_rdo`
  (atualiza a CR única `OBR-MED-#####` da obra).

### 9. Custos automáticos (mão de obra + material)

- **Mão de obra:** vem do RDO finalizado (passo 8).
- **Material:** lançado via "Almoxarifado → Saída" ou
  "Compras → Pedido". O evento `material_saida` aciona
  `lancar_custo_material_obra`, que cria custo vinculado ao serviço.
- **Visualizar:** menu "Custos" → "Gestão de Custos V2" — pais/filhos
  por categoria e funcionário/obra (mig 77).

### 10. Medição + ContaReceber (regra nova #94)

- **Caminho:** "Obras" → linha da obra → aba "Medição" →
  `/medicao/obra/<id>`.
- **Layout:** lista de `ItemMedicaoComercial` com colunas
  "Quantidade", "% acumulado", "Valor executado acumulado", "Saldo".
- **Geração quinzenal:** botão "Nova medição quinzenal". Ao gerar
  ou fechar, o sistema chama `recalcular_medicao_obra(obra_id)`,
  que faz **UPSERT** da CR única `OBR-MED-#####`:
  - `valor_original = valor_medido_acumulado`
  - `saldo = max(0, valor_medido - valor_recebido)`
  - `status` flui PENDENTE → PARCIAL → QUITADA conforme recebimento
  - `data_vencimento = hoje + (proposta.prazo_entrega_dias or 30)`
- **Atenção:** **NÃO** existem mais múltiplas `ContaReceber MED-`
  por medição. Existe **uma e somente uma** CR viva por obra. Para
  saber "quanto medi neste fechamento" use o histórico de
  `ItemMedicaoComercial.percentual_executado_acumulado` por período.

### 11. Aprovação financeira e fluxo de caixa

- **Caminho:** menu "Financeiro" → "Aprovação em 2 etapas"
  (sub-blueprint `gestao_custos`).
- Cada lançamento passa por: rascunho → revisão → aprovado → pago.
- **Rotas-chave:**
  - `/financeiro/contas-receber` — lista a CR `OBR-MED-#####` da obra
    (não quebra mais — helpers `_saldo_seguro*` + `func.coalesce`).
  - `/financeiro/fluxo-caixa` — agregação por banco/origem em BRL.

### 12. Cotação / Mapa de Concorrência V2

- **Caminho funcional:** Portal Cliente → mapa de concorrência →
  cliente seleciona fornecedor (rotas
  `aprovar_mapa_concorrencia`, `selecionar_mapa_v2` em
  `portal_obras_views.py`, CSRF-exempt).
- **Atenção (Issue B):** o atalho admin direto
  `/obras/<id>/mapa-v2/<mapa_id>/editar` ainda é sub-documentado;
  follow-up para o time de docs.

### 13. Portal do Cliente

- **Caminho:** `/portal/obra/<token_cliente>` (link gerado
  automaticamente na aprovação — #94).
- **Conteúdo:** Cronograma com dropdown, Mapa de Concorrência,
  Histórico de evolução, Medições visíveis, Painel estratégico,
  formato monetário BR (`brl_filter`).

### 14. Páginas de erro (#96)

- Acessar uma rota inexistente → `error.html` (extends
  `base_completo.html`). O **menu superior renderiza normalmente**,
  com `current_user` tolerado em todos os blocos. Logado, o usuário
  consegue voltar ao Dashboard sem precisar refazer login.

---


## Princípio central

> **Aprovar uma proposta cria estrutura, não dinheiro a receber.**
> A `ContaReceber` da obra nasce e se atualiza **somente** conforme o
> medido avança (RDO finalizado, medição quinzenal gerada/fechada).

Existe **uma e apenas uma** `ContaReceber` viva por obra:

- `origem_tipo='OBRA_MEDICAO'`
- `origem_id = obra.id`
- `numero_documento = 'OBR-MED-#####'`
- `valor_original = valor medido acumulado da obra`
- `saldo = max(0, valor_medido - valor_recebido)`
- `status ∈ {PENDENTE, PARCIAL, QUITADA}`
- `data_vencimento = data_emissao + (proposta.prazo_entrega_dias or 30)`

## Eventos e handlers

| Evento | Handler | Responsabilidade |
| --- | --- | --- |
| `proposta_aprovada` | `event_manager.propagar_proposta_para_obra` | Cria/atualiza Obra (`OBR####`, `token_cliente`, `portal_ativo`, `valor_contrato`). Seta `proposta.obra_id` e `convertida_em_obra`. **Não cria ContaReceber.** |
| `proposta_aprovada` | `handlers.propostas_handlers.handle_proposta_aprovada` | Lança contábil dupla (1.1.02.001 / 4.1.01.001). Propaga itens via `_propagar_proposta_para_obra` (cria `ItemMedicaoComercial` por `PropostaItem` — listener `after_insert` cria `ObraServicoCusto` pareado). **Não cria ContaReceber.** |
| `rdo_finalizado` | `event_manager.lancar_custos_rdo` | Cria `GestaoCustoFilho`/`CustoObra` para a mão de obra do RDO. |
| `rdo_finalizado` | `event_manager.recalcular_medicao_apos_rdo` | Chama `services.medicao_service.recalcular_medicao_obra(obra_id, admin_id)`. |

A ordem dos handlers de `proposta_aprovada` é garantida pela ordem de
import em `app.py` (event_manager primeiro, handlers depois).

## API canônica de recálculo

```python
from services.medicao_service import recalcular_medicao_obra

resultado = recalcular_medicao_obra(obra_id, admin_id)
# resultado is None | {
#   'valor_medido': Decimal,
#   'valor_recebido': Decimal,
#   'valor_a_receber': Decimal,
#   'conta_receber_id': int
# }
```

A função:

1. Recalcula `percentual_executado_acumulado`/`valor_executado_acumulado`
   de cada `ItemMedicaoComercial` da obra a partir do estado vivo do
   cronograma (`ItemMedicaoCronogramaTarefa` ponderado) com fallback por
   `servico_id` em `RDOServicoSubatividade` (RDOs finalizados).
2. Faz UPSERT da `ContaReceber` única da obra.
3. Retorna o payload acima para alimentar painéis.

## Aprovação da proposta — fluxo

### Pelo admin (`POST /propostas/aprovar/<id>`)

1. Status passa a `APROVADA` e histórico é registrado.
2. Commit transacional.
3. Emit `proposta_aprovada`.
4. **Validação pós-emit**: refaz `db.session.refresh(proposta)` e checa
   `proposta.obra_id`. Se vazio, exibe flash de warning indicando que a
   estrutura ficou incompleta (handler falhou em algum ponto).

### Pelo cliente (`POST /propostas/cliente/<token>/aprovar`)

1. Status `APROVADA` + `data_resposta_cliente` + `observacoes_cliente`.
2. Resolução de `admin_id` igual à `portal_cliente()`:
   `usuario.admin_id or usuario.id` (via `Usuario.query.get(criado_por)`),
   com fallback para `proposta.admin_id`.
3. Mesmo `emit + refresh + warning` do fluxo admin.

## Tolerância a dados legados

- `financeiro_views.py` e `financeiro_service.py` usam helpers
  `_saldo_seguro` / `_saldo_seguro_cr` e `func.coalesce(saldo, valor_original)`
  para que `ContaReceber` antigas (`origem_tipo='PROPOSTA'`/`'MEDICAO'`)
  com `saldo NULL` não quebrem dashboards de fluxo de caixa.
- Propostas legadas com `status='aprovada'` (lowercase) continuam sendo
  lidas pelos painéis (`dashboard.py`, `resumo_custos_obra.py`); novas
  aprovações usam `'APROVADA'` (uppercase).

## Rotas relevantes (verificadas em 2026-04-17)

| Função | Método/rota |
| --- | --- |
| Login | `POST /login` (campos `email`, `password`) |
| Listagem de propostas | `GET /propostas` |
| Aprovar proposta (admin) | `POST /propostas/aprovar/<id>` |
| Aprovar proposta (cliente) | `POST /propostas/cliente/<token>/aprovar` |
| Listagem de obras | `GET /obras` |
| Detalhe de obra | `GET /obras/<id>` |
| Contas a receber | `GET /financeiro/contas-receber` *(atenção: rota é `contas-receber`, não `contas-a-receber`)* |

## Smoke test e2e (confirmado)

Cenário read-only executado pelo runner Playwright após o refator:

1. Login admin → dashboard, sem 500.
2. `/propostas` renderiza limpa.
3. `/financeiro/contas-receber` renderiza limpa, **sem TypeError de
   `saldo` NULL** (helpers `_saldo_seguro*` + `func.coalesce` ativos).
4. `/obras` renderiza limpa.
5. Detalhe da primeira obra carrega sem erro.

Resultado: **success**. Veja `reports/relatorio-e2e-task-94.md` para a
matriz completa.

## E2E backend determinístico do ciclo (`tests/test_ciclo_proposta_obra_medido_cr.py`)

Bateria executada após o refator: **30 PASS / 0 FAIL**. Roda em
`python tests/test_ciclo_proposta_obra_medido_cr.py` e cobre as 5
fases do ciclo financeiro novo:

1. **Aprovação cria estrutura, não dinheiro**: emite `proposta_aprovada`
   e valida que Obra (`OBRxxxx`), `token_cliente`, `portal_ativo`,
   `valor_contrato`, `proposta.obra_id` e o `ItemMedicaoComercial` da
   proposta foram criados — e que **nenhuma** `ContaReceber OBRA_MEDICAO`
   apareceu nesse momento.
2. **Avanço 50% via cronograma**: cria `TarefaCronograma` com
   `percentual_concluido=50` ligada ao IMC (peso 100). Chama
   `recalcular_medicao_obra` e valida que a CR `OBR-MED-#####` nasceu
   com `valor_original=R$ 500`, `saldo=R$ 500`, `status='PENDENTE'` e o
   payload retornado contém `valor_medido=500` / `valor_a_receber=500`.
3. **Avanço 100% (UPSERT)**: tarefa vai para 100%, `recalcular_medicao_obra`
   é chamado de novo e a função atualiza a **mesma** CR (id idêntico)
   para `valor_original=R$ 1.000`/`saldo=R$ 1.000`. Continua com **uma
   única** linha `OBR-MED-#####` para a obra (UPSERT, não duplica).
4. **Recebimento parcial → PARCIAL**: setando `valor_recebido=R$ 300`,
   o recálculo aplica `saldo=R$ 700` e `status='PARCIAL'`.
5. **Recebimento total → QUITADA**: com `valor_recebido=R$ 1.000`, o
   recálculo zera o saldo e marca `status='QUITADA'`. A obra continua
   com exatamente uma CR `OBR-MED-#####`.

> **Resultado real do último run**: obra `OBR0005` (id=398), CR
> `OBR-MED-00398` evoluiu PENDENTE@500 → PENDENTE@1000 → PARCIAL@700 →
> QUITADA@0 sem nunca duplicar.

## E2E Orçamento + Proposta (`tests/test_e2e_orcamento_proposta.py`)

Bateria nova introduzida pela Task #95: **36 PASS / 0 FAIL**. Roda em
`python tests/test_e2e_orcamento_proposta.py` e cobre o ciclo do
catálogo paramétrico até a aprovação da proposta — pega o trecho que o
ciclo Proposta→CR (acima) **não** cobre, porque aquele só começa
depois da aprovação.

1. **Setup catálogo paramétrico** — cria `Insumo` (mão de obra +
   material), `PrecoBaseInsumo`, `Servico` (8% imposto + 12% lucro) e
   duas `ComposicaoServico`. Valida `custo_unitario=R$ 90,00` e
   `preco_venda=R$ 112,50`. Quando `imposto+lucro ≥ 100%`, o cálculo
   sinaliza `erro` e zera o preço (proteção contra divisão por zero).
2. **Proposta rascunho com explosão de insumos** — chama
   `explodir_servico_para_quantidade(svc, 10)` e grava o `PropostaItem`
   com `servico_id`, `quantidade_medida=10`, `custo_unitario=90.0000`,
   `lucro_unitario=22.5000` e `subtotal=R$ 1.125,00`.
3. **Recálculo do Servico** — `recalcular_servico_preco(svc)` persiste
   `Servico.preco_venda_unitario`; o `PropostaItem` antigo **não** é
   alterado.
4. **Snapshot imutável** — encerra os `PrecoBaseInsumo` antigos (com
   `vigencia_fim`), insere preços novos vigentes, recalcula o serviço
   (custo sobe para R$ 180 / preço para R$ 225) e confirma que o
   `PropostaItem` original mantém custo R$ 90 / subtotal R$ 1.125. É a
   regra de negócio do orçamento paramétrico: o que valeu na hora da
   proposta vira foto.
5. **Transição rascunho → enviada + portal** — muda o status da
   proposta para `enviada`, popula `data_envio` e valida que
   `GET /propostas/cliente/<token>` responde **200**. Token inválido
   não resolve para nenhuma `Proposta`.
6. **Aprovação portal cliente + isolamento multi-tenant** —
   `POST /propostas/cliente/<token>/aprovar` retorna 302; o status vira
   `APROVADA`, `convertida_em_obra=True`, `obra_id` populado, a `Obra`
   nasce com `OBRxxxx` e `token_cliente`, o `ItemMedicaoComercial` é
   propagado 1:1 herdando o `servico_id` do catálogo. Outro `admin_id`
   consultando a mesma proposta recebe `None` — sem leak entre tenants.
   Confirmação HTTP: logado como usuário do outro tenant,
   `GET /propostas/<id>` devolve **302** (redirect com flash), nunca
   200 com os dados.

> **Resultado real do último run**: proposta `P-E2E95-…`, `Servico`
> id=360, `Obra` id=404 com código `OBR0007`. Snapshot do `PropostaItem`
> resistiu à mudança de preço do insumo (`custo=R$ 90,00` enquanto o
> `Servico` foi para `R$ 225,00`).

### Bug regressivo descoberto e corrigido pelo teste

O e2e UI inicial expôs uma `IntegrityError` em
`uq_obra_codigo_admin_id`: o gerador de `codigo` em
`event_manager.propagar_proposta_para_obra` usava
`func.max(Obra.codigo)` sem filtrar pelo padrão `OBR%`. Quando o admin
tinha alguma `Obra` com `codigo` NULL/vazio, o `max` não retornava
nenhum `OBR####`, o gerador caía em `numero=1` e tentava inserir
`OBR0001` — colidindo com um registro pré-existente. Corrigido
filtrando `Obra.codigo.like('OBR%')` e iterando até encontrar um
código livre. Após a correção, o e2e backend acima passa 30/30.

## Solução de problemas comuns

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| Aprovou proposta e não vê obra | Handler falhou — flash de warning surgiu | Verificar logs (`propagar_proposta_para_obra`); reaprovar |
| `ContaReceber` da obra com valor desatualizado | RDO não chegou a `Finalizado` ou IMC sem cronograma/serviço | Conferir status do RDO e vínculos no cronograma; chamar `recalcular_medicao_obra` manualmente |
| `data_vencimento` "errada" | Proposta sem `prazo_entrega_dias` | Sistema cai no default de 30 dias |
| Status ainda `PARCIAL` após receber tudo | `saldo` ficou positivo por arredondamento | `recalcular_medicao_obra` ajusta no próximo gatilho; status vira `QUITADA` |

## Métricas de Funcionários (v1+v2)

Serviço único `services/funcionario_metrics.py` consolida todas as
métricas de funcionários, suportando **salaristas (v1)** e
**diaristas (v2)** em paralelo. A decisão de modo respeita o override
por funcionário (`Funcionario.tipo_remuneracao`) sobre o tenant
(`is_v2_active(admin_id)`).

### API pública

- `get_modo_remuneracao(funcionario)` → `'salario'` ou `'diaria'`.
- `calcular_valor_hora(funcionario)` → valor/hora atual (0 para diarista).
- `calcular_metricas_funcionario(funcionario, data_ini, data_fim)` →
  dict com `modo`, `horas_trabalhadas`, `horas_extras`, `dias_pagos`,
  `faltas`, `custo_mao_obra`, `custo_va`, `custo_vt`, `custo_alimentacao`,
  `custo_reembolsos`, `custo_almoxarifado`, `custo_total`, `valor_hora_atual`.
- `calcular_metricas_lista(funcionarios, ...)` — em massa.
- `agregar_kpis_geral(metricas_list)` — totais por tenant.

### Fórmulas

| Modo | Mão de obra |
| --- | --- |
| `salario` (v1) | `horas_trabalhadas × valor_hora + horas_extras × valor_hora × 1.5` |
| `diaria` (v2)  | `valor_diaria × dias_pagos + (horas_extras / 8) × valor_diaria × 1.5` |

**Custo total** = MO + VA (× dias_pagos) + VT (× dias_pagos) +
Alimentação real híbrida (RegistroAlimentacao + AlimentacaoLancamento
com rateio M2M) + Reembolsos aprovados + Almoxarifado em posse
(consumível e serializado, valor_unitario × quantidade ativa).

### Consumidores

- `views/employees.py` — lista, perfil e PDF holerite (bloco legado removido).
- `views/dashboard.py` — loop por funcionário usa apenas `custo_mao_obra`
  para evitar double-count com agregações de tenant.
- `api_funcionarios.py` — helper `_valor_hora_api` substitui
  `salario / 160` em todos os pontos da API.
- `relatorios_funcionais.py` — relatório de horas extras suporta diaristas.

### Cobertura de testes

`tests/test_e2e_metricas_funcionario.py` — 27/27 PASS:
- Cenário v1 (salarista puro) — 8 asserts.
- Cenário v2 (diarista com VA/VT/alimentação/reembolso/almoxarifado) — 10 asserts.
- Override v2 → salarista — 3 asserts.
- Helpers + agregação geral — 6 asserts.
