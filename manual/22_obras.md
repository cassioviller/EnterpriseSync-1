# Obras

A **Obra** é a entidade central do SIGE. Tudo o que acontece no sistema — RDO, custos, alocação de equipe, compras, medições, propostas aprovadas, contas a receber — orbita em torno de uma obra. Capriche no cadastro: ele é a base do orçamento operacional e do acompanhamento físico-financeiro.

## Para que serve

- Cadastrar e acompanhar cada obra/projeto com dados de cliente, código, datas, área e valor contratado.
- Manter o **orçamento operacional** próprio (cópia editável do orçamento da proposta).
- Acompanhar a **execução** via RDOs, cronograma físico, curva de avanço e medições quinzenais.
- Centralizar **mapas de concorrência**, **pedidos de compra**, e o **portal do cliente** específico da obra.

## Como acessar

- **Menu superior → "Obras" → "Listar Obras"** abre `/obras`.
- Para o **cronograma da obra**: **Menu → Obras → "Cronograma Físico"** (`/cronograma/`) e clicar na obra desejada.
- Para o **painel de produtividade**: **Menu → Obras → "Painel de Produtividade"** (`/cronograma/produtividade`).

## Fluxos principais

### 1. Criar uma nova obra (manualmente)
1. **Menu → Obras → Listar Obras**.
2. Clique em **"+ Nova Obra"** (botão verde, canto superior direito) — abre `/obras/nova`.
3. Preencha:
   - **Código** (ex.: `OBR-2026-003`) — único por empresa.
   - **Nome** (ex.: "Residencial Jardim das Flores").
   - **Cliente** — selecione no dropdown (cadastre antes em **Cadastros → Clientes** se ainda não existir).
   - **Endereço**, **Cidade**, **Estado**.
   - **Data de Início** e **Data de Término Prevista**.
   - **Área Total (m²)** e **Valor Contratado (R$)**.
   - **Responsável Técnico** — escolha um funcionário com função compatível.
4. Clique em **"Salvar Obra"** — o sistema redireciona para `/obras/detalhes/<id>` com a tela completa da obra.

> **Forma recomendada:** criar a obra **a partir de uma proposta aprovada** (ver capítulo Propostas). Isso já materializa o orçamento operacional, o cronograma e a conta a receber automaticamente.

### 2. Editar dados da obra
1. Na listagem, clique no botão **"Editar"** (lápis) do card da obra, ou em **"Editar Obra"** dentro da tela de detalhes.
2. Em `/obras/editar/<id>`, ajuste os campos e clique em **"Salvar Alterações"**.

### 3. Tela de detalhes da obra (`/obras/detalhes/<id>`)
A tela é dividida em abas/cards:

- **Resumo financeiro**: valor contratado, custo realizado, margem prevista vs. realizada.
- **Curva de avanço**: gráfico Planejado × Realizado, alimentado pelos RDOs finalizados.
- **RDOs recentes**: lista dos últimos relatórios; clique em qualquer RDO para abri-lo.
- **Cronograma físico**: link para o Gantt da obra.
- **Mapa de concorrência**: comparativo de cotações de fornecedores.
- **Pedidos de compra**: histórico e botão para nova compra.
- **Portal do cliente**: link com token para enviar ao cliente.

### 4. Criar pedido de compra para a obra
1. Em `/obras/detalhes/<id>`, role até a seção **"Pedidos de Compra"**.
2. Clique em **"+ Nova Compra"** — abre o formulário.
3. Selecione **fornecedor**, **insumos** e **quantidades**, e clique em **"Enviar para Aprovação"**.
4. O cliente recebe o pedido no Portal do Cliente; depois de aprovado, vira ordem de compra.

### 5. Mapa de concorrência V2
1. Em **"Mapa de Concorrência"**, clique em **"Novo Mapa"**.
2. Selecione os **insumos/serviços** a cotar.
3. Adicione **fornecedores** e preencha **preço unitário** por item de cada fornecedor.
4. O sistema marca a melhor oferta por linha e calcula o total por fornecedor.
5. Clique em **"Salvar"** para fixar o mapa e em **"Enviar ao Cliente"** se quiser aprovação externa.

### 6. Excluir uma obra
1. Na listagem, clique no botão **"Excluir"** do card.
2. Confirme no diálogo (a exclusão é via POST por questão de segurança).
3. **Cuidado:** obras com RDO, medições ou contas associadas não podem ser excluídas — desative-as com **"Toggle Status"** em vez disso.

## Dicas e cuidados

- O **código da obra** aparece em todos os relatórios; padronize um formato (ex.: `OBR-AAAA-NNN`) e mantenha.
- **Não troque o cliente** de uma obra depois de aprovada a proposta — isso desconecta a conta a receber e pode inconsistir o histórico.
- A **curva de avanço** só aparece depois que existir pelo menos um **RDO finalizado** na obra.
- Para acompanhar várias obras ao mesmo tempo, use a **listagem `/obras`** com os filtros de status (Em Andamento / Concluída / Pausada).
