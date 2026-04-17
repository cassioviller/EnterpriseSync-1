# Manual do Ciclo Completo — SIGE v9.0

> Versão validada em **17/abr/2026** no tenant V2 (`admin.v2@sige.com`).  
> Onde existem bugs bloqueantes confirmados na Task #85, o passo está marcado com ⚠️ e há um *workaround* explicado. Veja `reports/relatorio-e2e-task-85.md` para os bugs em detalhe.

## Sumário

1. [Login no sistema](#1-login)
2. [Cadastro de funcionários](#2-funcionários)
3. [Catálogo de Insumos e Serviços (Task #82)](#3-catálogo)
4. [Cadastro de Proposta a partir do Catálogo](#4-proposta)
5. [Aprovação da Proposta](#5-aprovação) ⚠️
6. [Cronograma da obra](#6-cronograma)
7. [Vínculo cronograma ↔ serviço do catálogo](#7-vínculo)
8. [Lançamento de RDO consolidado](#8-rdo)
9. [Custos automáticos do RDO](#9-custos)
10. [Medição quinzenal](#10-medição)
11. [Contas a receber e Fluxo de Caixa](#11-financeiro) ⚠️
12. [Cotação / Mapa de Concorrência V2](#12-cotação) ⚠️
13. [Portal do Cliente](#13-portal-cliente) ⚠️
14. [Boas práticas e auditoria de duplicação](#14-auditoria)
15. [Resumo do ciclo](#15-resumo)

---

## 1. Login

1. Acesse `https://<seu-domínio>/login`.
2. Informe e-mail e senha do administrador da empresa (no ambiente de teste: `admin.v2@sige.com` / `admin123`).
3. O sistema redireciona para o dashboard. O menu lateral é o ponto único de navegação — **prefira-o ao dropdown legado "Serviços"** no header (será removido na Task #87).

## 2. Funcionários

1. Menu lateral → **Equipe** → **Funcionários**.
2. **Novo Funcionário** preencha nome, função, salário, horário e admissão.
3. Funcionários cadastrados ficam disponíveis para apontamento em RDO, ponto eletrônico e folha.

> O tenant V2 já vem com 22 funcionários ativos para teste. Pule esta etapa em ambientes de demonstração.

## 3. Catálogo

O Catálogo é a fonte única de **insumos** (materiais, mão-de-obra, equipamentos) e **serviços** (composições paramétricas).

### 3.1 Cadastrar Insumos

1. Menu lateral → **Catálogo** → **Insumos** (`/catalogo/insumos`).
2. **Novo Insumo**: defina código, descrição, unidade e tipo (`MATERIAL`, `MAO_OBRA` ou `EQUIPAMENTO`).
3. Após salvar, no detalhe do insumo, adicione **Preço Base** com vigência (a partir de qual data esse preço passa a valer). O sistema mantém histórico versionado em `PrecoBaseInsumo`.

### 3.2 Cadastrar Serviço com composição

1. Menu lateral → **Catálogo** → **Serviços** (`/catalogo/servicos`).
2. **Novo Serviço**: nome, unidade de venda, **% imposto** e **% margem de lucro** (defaults vêm de `ConfiguracaoEmpresa.imposto_pct_padrao/lucro_pct_padrao`).
3. Abra a aba **Composição** (`/catalogo/servicos/<id>/composicao`).
4. Para cada insumo da receita, adicione uma linha com **coeficiente** (quantidade de insumo por unidade do serviço).
5. Clique em **Recalcular preço**. O sistema calcula:

   ```
   custo_total   = Σ (coeficiente × preço_base_vigente)
   preço_venda   = custo / (1 − imposto/100 − margem/100)
   ```

   Validado em teste: Alvenaria 1/2 vez (Cimento 0.5 + Pedreiro 1.5) com imposto 10% e margem 20% → custo R$ 55,25 → **preço de venda R$ 78,93/m²**.

### 3.3 Histórico cross-obra

`/catalogo/servicos/<id>/historico-obras` mostra todas as obras onde o serviço foi vendido, com margem real vs. orçada.

## 4. Proposta

1. Menu lateral → **Propostas** → **Nova Proposta**.
2. Preencha cabeçalho (cliente, assunto, validade, prazo, condições).
3. Em **Itens**, clique em **Adicionar do Catálogo**: a busca em `/catalogo/api/servicos/buscar` retorna os serviços e ao selecionar, preço e descrição são preenchidos automaticamente.
4. Itens manuais (sem catálogo) também são aceitos — basta preencher descrição, quantidade, unidade e preço unitário.
5. Salvar gera a proposta em status `RASCUNHO`.

> ⚠️ **Bug #5 confirmado:** itens vindos do catálogo podem perder o `servico_id` ao salvar. Após criar a proposta, abra a tabela `proposta_itens` e confirme que `servico_id` está populado para os itens vindos do catálogo. Se NULL, use a rota auxiliar `POST /catalogo/proposta-itens/<id>/vincular-servico` para vincular a posteriori.

## 5. Aprovação

1. Menu lateral → **Propostas** → abrir a proposta.
2. Clique **Enviar para Cliente** (status passa a `ENVIADA`) — o sistema gera token e link do portal.
3. Após confirmação verbal/email do cliente, clique **Aprovar Proposta**. Confirme no modal.

> ⚠️ **Bug #3 confirmado e bloqueante:** a rota chamada pelo botão da UI (`POST /propostas/<id>/status`) **não emite o evento `proposta_aprovada`**. Resultado: nada acontece — Obra não é criada, ContaReceber não é gerada, lançamento contábil não é feito e os `ItemMedicaoComercial` não são criados.
>
> **Workaround temporário (até o fix):** após clicar "Aprovar", abra um shell Python:
>
> ```python
> from app import app
> from event_manager import EventManager
> with app.app_context():
>     EventManager.emit('proposta_aprovada',
>                       {'proposta_id': <ID>, 'admin_id': <ADMIN_ID>},
>                       <ADMIN_ID>)
> ```
>
> Em seguida atualize `propostas_comerciais.obra_id` para o id da Obra recém-criada e `convertida_em_obra=true` (Bug #4) — só então o `_propagar_proposta_para_obra` cria os `ItemMedicaoComercial` e os `ObraServicoCusto` correspondentes. Atribua também um `token_cliente` à obra com `UPDATE obra SET token_cliente='<token>' WHERE id=<obra_id>;` para liberar o portal.

Quando o ciclo correto é destravado, são criados automaticamente:

- **Obra** com `proposta_origem_id`, `valor_contrato` igual ao total da proposta, status "Em andamento".
- **ContaReceber** PENDENTE com vencimento de +30 dias.
- **LançamentoContábil** com partidas dobradas (1.1.02.001 débito / 4.1.01.001 crédito).
- **Um `ItemMedicaoComercial` por `PropostaItem`** na obra (herdando `valor_comercial` e `servico_id`).
- **Um `ObraServicoCusto` por IMC** (criado pelo listener after_insert; `valor_orcado = valor_comercial`, `servico_catalogo_id = servico_id`).

## 6. Cronograma

1. Na Obra → aba **Cronograma** (`/cronograma/obra/<id>`).
2. Use o Gantt MS-Project-style para criar tarefas, durações e hierarquia.
3. Drag-and-drop reordena e recalcula a cadeia automaticamente.

## 7. Vínculo

Em cada tarefa do cronograma você pode vincular um `Servico` do catálogo. Esse vínculo é o que permite ao engine de medição calcular o **% executado** ponderado por tarefa (`ItemMedicaoCronogramaTarefa`).

## 8. RDO

1. Menu lateral → **RDO** → **RDO consolidado** (`/funcionario/rdo/consolidado`).
2. Selecione obra e data.
3. Adicione mão-de-obra (funcionários × horas), serviços executados (% concluído por subitem) e fotos.
4. Salvar gera o RDO em status `RASCUNHO`. **Finalizar** dispara o evento `rdo_finalizado`.

## 9. Custos

Após o RDO ser finalizado:

- **Mão-de-obra do RDO** vira `GestaoCustoFilho` agrupado em `GestaoCustoPai` (origem `rdo_mao_obra`).
- Materiais saídos do almoxarifado (evento `material_saida`) viram `GestaoCustoFilho` na obra.
- Compras recebidas (`Compras V2`) viram `GestaoCustoPai` com `tipo_categoria=MATERIAL/COMPRA`.

Acompanhe em **Gestão de Custos** (`/gestao-custos/`). A coluna "Realizado" no `ObraServicoCusto` agrega esses custos por serviço, comparando com `valor_orcado`.

## 10. Medição

1. Na obra → **Medições** (`/medicao/obra/<id>`).
2. **Nova Medição Quinzenal**: o sistema lê os `ItemMedicaoComercial` da obra (criados automaticamente pela aprovação da proposta) e busca os vínculos com tarefas do cronograma para calcular `% executado` ponderado.
3. Revise os percentuais (pode ajustar manualmente), salve e clique **Fechar Medição**.
4. Ao fechar, o sistema gera um **PDF Extrato** (ReportLab) com cabeçalho da empresa e detalhamento por item.

> **Importante (resposta à pergunta do escopo):** o fechamento da medição **não cria nova ContaReceber**. A ContaReceber é criada uma única vez no momento da aprovação da proposta com o valor total. A medição mede apenas o avanço — não particiona financeiramente. Se essa regra precisar mudar, será uma evolução futura.

## 11. Financeiro

1. Menu lateral → **Financeiro** → **Contas a Receber** (`/financeiro/contas-receber`).
2. Aqui deveriam aparecer todas as ContasReceber, incluindo a gerada na aprovação da proposta.
3. Em **Fluxo de Caixa** (`/financeiro/fluxo-caixa`) você lança recebimentos, custos diretos/indiretos e despesas administrativas. A "Nova Movimentação" tem categorias agrupadas e permite vincular obra+banco.

> ⚠️ **Bugs #1 e #2 confirmados e bloqueantes:** ambas as listagens retornam **HTTP 500** (TypeError: `sum` recebendo `None`). Até o fix, consulte os dados via SQL direto:
>
> ```sql
> SELECT id, descricao, valor_original, saldo, status, data_vencimento
> FROM conta_receber WHERE admin_id = <id> ORDER BY data_vencimento;
> ```

## 12. Cotação

O **Mapa de Concorrência V2** permite comparar N itens × N fornecedores numa grade única, com destaque automático do menor preço por item.

> ⚠️ **Bug #6:** as rotas admin documentadas no `replit.md` (`/obras/<id>/mapa-v2/<mapa_id>/editar`) **não foram localizadas** durante a Task #85 — `GET /obras/342/mapa-v2` retorna 404. Apenas as rotas do **lado do portal cliente** existem (`/portal/obra/<token>/mapa/<id>/aprovar` e `/portal/obra/<token>/mapa-v2/<id>/selecionar`). Será preciso confirmar onde está o blueprint admin antes de documentar este passo. Por enquanto, o cliente pode receber um mapa apenas se ele tiver sido criado por outro caminho.

## 13. Portal Cliente

1. Pegue o `token_cliente` da Obra (em condições normais é gerado automaticamente na aprovação — hoje precisa ser atribuído manualmente, ver Bug #4).
2. Compartilhe o link `https://<seu-domínio>/portal/obra/<token>` com o cliente — sem login.
3. O portal mostra: dados da obra, andamento do cronograma, mapa de concorrência, aprovações pendentes (compras), medições com download de PDF e upload de comprovante de pagamento (PIX da Fornecedor.chave_pix).
4. O cliente pode aprovar/rejeitar compras, selecionar fornecedor no mapa de concorrência e enviar comprovantes.

## 14. Auditoria

Pontos de atenção observados:

- **Dropdown "Serviços" no header** sobrevive como menu legado — confunde o operador. Use sempre **Catálogo** no menu lateral. (Task #87 já proposta para esconder.)
- **Operações destrutivas devem ser POST via formulário JS** — links GET destrutivos foram banidos (vide preferência do usuário no `replit.md`).
- **Não fazer auto-fill de campos de filtro/busca** — pode quebrar a UX (preferência do usuário).

## 15. Resumo

```
Login → Funcionários → Catálogo (Insumos + Serviços com composição)
   → Proposta (com itens do catálogo)
       → APROVAR (⚠️ requer fix do Bug #3 + #4 + #5 para fluir sozinho)
           → Obra criada
              ├─ ContaReceber (PENDENTE)
              ├─ LancamentoContabil (partidas dobradas)
              ├─ ItemMedicaoComercial (por item da proposta)  ← Task #82
              └─ ObraServicoCusto (1:1 com IMC)              ← listener after_insert
   → Cronograma (Gantt) com tarefas vinculadas a serviços
   → RDO consolidado (mão-de-obra + serviços executados)
       └─ Custos automáticos em Gestão de Custos
   → Medição quinzenal (% executado, PDF extrato)
       *(não cria nova ContaReceber — a única vem da aprovação da proposta)*
   → Financeiro: Contas a Receber + Fluxo de Caixa  (⚠️ Bugs #1/#2 quebram a UI)
   → Cotação / Mapa V2  (⚠️ Bug #6 — rota admin a confirmar)
   → Portal Cliente  (⚠️ depende de token_cliente — Bug #4)
```

A arquitetura está implementada de ponta a ponta. **5 bugs bloqueantes** impedem hoje que o operador percorra o ciclo sem intervenção manual no banco — uma vez aplicados os fixes #1 a #5, o ciclo flui inteiramente pela UI sem `psql`.
