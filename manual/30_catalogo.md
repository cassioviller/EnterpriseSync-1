# Catálogo — Insumos e Serviços

O **Catálogo** (`/catalogo/`) é a **fonte de verdade** dos itens contratados pela empresa: **insumos** (materiais, mão-de-obra, equipamentos) com **preços vigentes** e **serviços paramétricos** (composições de insumos com **margem** e **imposto**).

## Para que serve

- Manter um **cadastro único de insumos** (nome, tipo, unidade, coeficiente padrão).
- Versionar **preços base** com **vigência** (a próxima vigência encerra a anterior automaticamente).
- Cadastrar **serviços** com **composição** (insumos × coeficientes), **imposto %** e **margem de lucro %** para gerar **preço de venda**.
- Vincular um **template de cronograma** padrão a cada serviço, para reuso em obras novas.
- Consultar **histórico de obras** que já contrataram cada serviço.

## Como acessar

- **Menu superior → "Cadastros" → "Insumos"** (`/catalogo/insumos`).
- **Menu superior → "Cadastros" → "Serviços"** (`/catalogo/servicos`).
- Detalhe de insumo: `/catalogo/insumos/<id>`.
- Composição de serviço: `/catalogo/servicos/<id>/composicao`.
- Histórico do serviço em obras: `/catalogo/servicos/<id>/historico-obras`.

## Fluxos principais

### 1. Cadastrar um insumo

1. **Menu → Cadastros → Insumos → "+ Novo Insumo"** (`/catalogo/insumos/novo`).
2. Preencha **Nome** (obrigatório), **Tipo** (`MATERIAL`, `MAO_OBRA`, `EQUIPAMENTO`), **Unidade** (m², m³, h, un., kg…), **Coeficiente padrão** (>= 0) e **Descrição**.
3. Opcional: informe um **Preço base** inicial (cria a primeira `PrecoBaseInsumo` com vigência hoje).
4. Salve — o sistema redireciona para `/catalogo/insumos/<id>` para adicionar mais preços, se necessário.

### 2. Atualizar preço (nova vigência)

1. Em `/catalogo/insumos/<id>`, role até **Histórico de Preços**.
2. Clique em **"+ Novo Preço"** (`/catalogo/insumos/<id>/preco`).
3. Informe **Valor** e **Vigência Início** (`YYYY-MM-DD`).
4. O sistema **encerra a vigência anterior** e cria a nova — orçamentos novos passam a usar o valor atualizado.

### 3. Cadastrar serviço

1. **Menu → Cadastros → Serviços → "+ Novo Serviço"** (`/catalogo/servicos/novo`).
2. Preencha **Nome**, **Categoria**, **Unidade** (m², m³, un.), **Imposto %** e **Margem de Lucro %**.
3. Salve — o sistema redireciona para a tela de **composição** (`/catalogo/servicos/<id>/composicao`).

### 4. Montar a composição do serviço

1. Em `/catalogo/servicos/<id>/composicao`, escolha um **Insumo** disponível.
2. Informe o **Coeficiente** (quanto de insumo por unidade do serviço — ex.: 0,65 sacos de cimento por m²).
3. Clique em **"Adicionar"** — a linha entra na composição e o **preço de custo** é recalculado automaticamente.
4. Para editar uma linha, use o botão de edição (atualiza coeficiente/observação).
5. Para excluir, clique em **"Remover"** (POST individual).

### 5. Atualizar imposto, margem ou preço de venda

1. Em `/catalogo/servicos/<id>/composicao`, ajuste **Imposto %** e **Margem %** no card superior.
2. Submeta — o sistema executa `recalcular_servico_preco` e exibe o novo **preço de venda**.

### 6. Vincular cronograma padrão ao serviço

1. Em `/catalogo/servicos/<id>/composicao`, no card **"Cronograma Padrão"**, escolha um **Template** (criado em `/cronograma/templates`).
2. Submeta — quando o serviço for adicionado a uma obra nova, esse cronograma é instanciado automaticamente.
3. Para desvincular, salve com seleção em branco.

### 7. Consultar histórico de obras

1. Em `/catalogo/servicos/<id>/composicao`, clique em **"Histórico de Obras"** → `/catalogo/servicos/<id>/historico-obras`.
2. A tela lista todas as obras que já contrataram esse serviço, com **quantidade**, **preço aplicado** e **status**.
3. Útil para análises de tendência de preço e demanda.

## Dicas e cuidados

- O preço **vigente** é sempre o de menor `vigencia_inicio` ainda **não encerrado**. Use o histórico para auditar mudanças.
- O **coeficiente padrão do insumo** é aplicado automaticamente quando o insumo entra em composições novas (pode ser sobrescrito por composição).
- **Excluir um insumo usado** em composições é bloqueado pelo banco (FK). Inative em vez de excluir.
- O **preço de venda** mostrado no catálogo é referencial — o orçamento real pode ter ajustes específicos da obra.
- O catálogo **não está no menu principal `base_completo.html`** — está dentro do dropdown "Cadastros". Ajuste expectativas em treinamentos.
- O **template de cronograma vinculado** só é instanciado em obras **criadas após** o vínculo; obras existentes não recebem retroativamente.
