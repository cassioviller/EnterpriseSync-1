# Propostas Comerciais

O módulo de **Propostas** é a porta de entrada do ciclo: a partir do catálogo de serviços, monta uma proposta profissional com itens, cronograma sugerido, condições comerciais e cláusulas; envia ao cliente por link/PDF; e, quando aprovada, **cria a obra automaticamente**, com orçamento operacional, cronograma materializado e a primeira conta a receber.

## Para que serve

- Gerar propostas a partir do catálogo de serviços (com cálculo automático de preço, mão de obra e materiais).
- Enviar ao cliente por **link público com token** ou **PDF profissional**.
- Receber **aprovação/rejeição** do cliente pelo portal.
- Manter **versões** da proposta (ex.: "001.26 v2") quando o cliente pede ajustes.
- Converter a proposta aprovada em **obra** com 1 clique.
- Reutilizar **templates** de propostas para tipos de serviço recorrentes.

## Como acessar

- **Menu superior → "Propostas" → "Dashboard"** (`/propostas/dashboard`) — visão geral.
- **Menu → Propostas → "Nova Proposta"** (`/propostas/nova`).
- **Menu → Propostas → "Templates"** (`/propostas/templates`).
- **Lista geral**: `/propostas/` ou `/propostas/listar`.

## Fluxos principais

### 1. Criar uma proposta nova
1. **Menu → Propostas → Nova Proposta**.
2. Em **Dados do Cliente**, preencha **Nome do Cliente \***, telefone, e-mail e endereço. Se o cliente já existir no cadastro, comece a digitar o nome — o sistema sugere a partir de `/propostas/api/clientes`.
3. Em **Dados da Proposta**, preencha **Número** (sugestão automática, ex.: `003.26`), **Data**, **Validade**, **Local da Obra**, **Descrição do Escopo**.
4. Em **Itens**, clique em **"+ Adicionar Serviço"**:
   - Selecione o **Serviço** do catálogo (ou marque **"Item livre"**).
   - Preencha **Quantidade** e **Unidade**.
   - O sistema calcula **Preço Unitário** e **Total** com base no catálogo; pode sobrescrever manualmente.
5. (Opcional) Anexe **arquivos** (memorial, plantas) e edite as **cláusulas** padrão.
6. Clique em **"Salvar"** — a proposta entra como **RASCUNHO**.

### 2. Visualizar / editar / gerar PDF
1. Na **lista de propostas**, clique no número/título.
2. Tela `/propostas/<id>` mostra resumo, itens, cronograma sugerido, anexos e histórico.
3. **Editar**: botão "Editar" (`/propostas/editar/<id>`).
4. **PDF**: botão "Baixar PDF" (`/propostas/<id>/pdf`) — usa o template visual da empresa.
5. **Nova versão**: clique em "Nova Versão" para clonar e editar mantendo o histórico.

### 3. Enviar ao cliente
1. Em `/propostas/<id>`, clique em **"Enviar ao Cliente"**.
2. Escolha o canal: **Link** (gera URL pública `/propostas/cliente/<token>`) ou **WhatsApp** (registra o envio).
3. O cliente abre o link, vê a proposta com os itens e clica em **"Aprovar"** ou **"Rejeitar"**.
4. O status da proposta atualiza em tempo real; o histórico registra quem aprovou e quando.

### 4. Aprovar internamente (admin)
1. Em `/propostas/<id>`, o admin pode clicar em **"Aprovar"** (rota `/propostas/aprovar/<id>`).
2. O sistema executa atomicamente:
   - Cria a **Obra** ligada ao cliente (com o nome/escopo da proposta).
   - **Materializa o cronograma** baseado nos serviços e templates.
   - Abre o **ItemMedicaoComercial** e a **ContaReceber** cumulativa.
   - Marca a proposta como **APROVADA**.
3. Você é redirecionado para `/obras/detalhes/<id>` da obra recém-criada.

### 5. Rejeitar / cancelar
1. Em `/propostas/<id>`, clique em **"Rejeitar"** (`/propostas/rejeitar/<id>`).
2. Informe o **motivo** — ele entra no histórico para análise comercial.
3. Para excluir definitivamente: **"Excluir"** (`/propostas/deletar/<id>`) — pede confirmação por POST.

### 6. Templates de proposta
1. **Menu → Propostas → Templates** (`/propostas/templates`).
2. Crie um novo (`/propostas/templates/novo`) ou edite um existente.
3. Marque um como **"Padrão"** para que abra por default ao criar uma proposta nova.
4. Templates pré-carregam cláusulas, condições comerciais e set de serviços.

## Dicas e cuidados

- **Revise os itens** antes de aprovar — depois de aprovada, a proposta vira a base do orçamento operacional da obra.
- **Use versões** quando o cliente pedir ajustes, em vez de sobrescrever a proposta original. O histórico é auditável.
- **Validade** da proposta: depois do prazo, o link público continua funcionando (não bloqueia), mas o status fica visível como "Vencida" — renove com nova versão se for o caso.
- O **número da proposta** segue o padrão `NNN.AA` (ex.: `001.26`). Mantenha sequencial por ano para facilitar a auditoria.
- O **portal cliente** exige só o token na URL — não precisa login. Trate o link como senha: quem tem o link pode aprovar.
