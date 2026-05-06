# CRM — Leads

O **CRM** (`/crm/`) gerencia o **funil de leads** desde a chegada até o fechamento (proposta enviada, ganho ou perda). Oferece visão **kanban** com drag-and-drop, **lista** filtrável e **cadastros auxiliares** (origens, cadências, situações, motivos de perda, tipos de material/obra).

## Para que serve

- Centralizar o **funil comercial**: cada lead tem nome, contato, demanda, valor potencial, responsável, origem e status.
- Mover leads entre os **status** (`Em fila`, `Em negociação`, `Proposta enviada`, `Ganho`, `Perdido`, `Congelado`) com arrasto.
- Registrar **histórico de interações** e **motivos de perda** para análise.
- Configurar **listas mestre** (origens, tipos de obra, cadências, situações) por tenant.

## Como acessar

- **Menu superior → "CRM"** (dropdown):
  - `/crm/` — Kanban.
  - `/crm/lista` — Lista filtrável.
  - `/crm/novo` — Novo lead.
  - `/crm/cadastros` — Listas mestre.
- Drawer mobile: **"CRM"** leva direto ao kanban.

## Fluxos principais

### 1. Cadastrar um novo lead

1. **Menu → CRM → "+ Novo Lead"** (`/crm/novo`).
2. Preencha:
   - **Nome** (obrigatório), **contato** (telefone), **e-mail**, **demanda** (texto livre).
   - **Localização** (cidade/bairro), **valor estimado da proposta**.
   - **Responsável** (usuário do tenant), **origem** (Indicação / Site / Anúncio…), **cadência**, **situação**.
   - **Tipo de material** e **tipo de obra** (listas mestre).
   - **Status inicial** (padrão: "Em fila").
3. Clique em **"Salvar"**. O lead aparece imediatamente no kanban e na lista.

### 2. Mover lead no kanban (drag-and-drop)

1. **Menu → CRM** abre `/crm/`.
2. Clique e segure o card do lead, arraste para a coluna de status desejada.
3. O sistema chama `POST /crm/<id>/mudar_status` (Sortable.js), atualiza o `status` e grava `status_changed_at`.
4. Se o status novo for **"Perdido"**, o sistema exige o **Motivo da Perda** — abre modal pedindo a seleção antes de gravar.
5. Mover para **"Ganho"** dispara o evento de conversão (proposta enviada → fechada).

### 3. Filtrar a lista de leads

1. **Menu → CRM → Lista** (`/crm/lista`).
2. Use os filtros do topo: **busca livre** (nome, contato, e-mail, demanda, localização), **responsável**, **origem**, **tipo de material**, **tipo de obra**, **mês de chegada** (`YYYY-MM`).
3. Cada submit ajusta a query string. Para limpar, apague o conteúdo dos filtros e submeta novamente.

### 4. Editar e marcar como Perdido

1. No kanban ou na lista, clique no nome do lead → `/crm/<id>/editar`.
2. Atualize qualquer campo. Para marcar como **Perdido**, escolha o status, selecione o **Motivo da Perda** (obrigatório) e salve.
3. O `status_changed_at` é atualizado automaticamente para registrar a transição.

### 5. Configurar listas mestre

1. **Menu → CRM → Cadastros** (`/crm/cadastros`).
2. A página agrupa as listas em abas: **Origens**, **Cadências**, **Situações**, **Motivos de Perda**, **Tipos de Material**, **Tipos de Obra**.
3. Clique em **"+ Adicionar"** dentro da aba para incluir um novo item, ou no lápis para editar.
4. As alterações ficam disponíveis imediatamente nos formulários de lead.

## Dicas e cuidados

- **Drag-and-drop só funciona no kanban**, não na lista — quando precisar mover muitos leads, use o kanban.
- Mover um lead para **"Perdido"** sem motivo cadastrado bloqueia a gravação. Cadastre os motivos antes do uso intensivo.
- A **busca livre** é case-insensitive e cobre 5 campos — use trechos curtos.
- Para reabrir um lead `Congelado` ou `Perdido`, basta arrastar de volta para `Em fila` no kanban.
- O CRM é **isolado por tenant** — cada admin vê apenas os próprios leads e listas mestre.
- A coluna **Valor total** no topo de cada coluna do kanban soma `valor_proposta` dos leads visíveis (não considera filtros aplicados na URL).
