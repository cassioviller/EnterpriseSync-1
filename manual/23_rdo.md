# RDO — Relatório Diário de Obra

O **RDO** é o coração da operação no campo. Cada dia de obra gera um RDO com **mão de obra alocada**, **equipamentos**, **serviços executados (com % de progresso por subatividade)**, **fotos**, **ocorrências** e o **clima**. Quando o RDO é **finalizado**, o sistema atualiza automaticamente os custos da obra, o avanço físico no cronograma e a base para a próxima medição quinzenal.

## Para que serve

- Registrar o que aconteceu na obra em cada dia.
- Alocar funcionários e equipamentos ao dia, gerando custo de mão de obra e horas para a folha.
- Apontar progresso por **serviço/subatividade**, alimentando o cronograma e o painel de produtividade.
- Anexar **fotos** do dia direto pelo celular.
- Registrar **ocorrências** (atrasos, problemas, riscos) que ficam visíveis ao gestor e ao cliente.

## Como acessar

- **Menu superior → "RDO"** (link direto, sempre visível) abre `/funcionario/rdo/consolidado` — a tela moderna unificada.
- **Listagem geral** dos RDOs por obra: `/rdos` (também acessível pelo menu).
- **Visualizar um RDO específico**: `/rdo/<id>` (a partir de qualquer link/cartão de RDO no sistema).

## Fluxos principais

### 1. Criar um RDO novo
1. **Menu → RDO** abre a tela consolidada `/funcionario/rdo/consolidado`.
2. No topo, escolha a **Obra** no dropdown — só aparecem obras em que o usuário está alocado (ou todas, para admin).
3. Selecione a **Data do Relatório** (padrão: hoje).
4. Clique em **"Novo RDO"** — o sistema cria o esqueleto com:
   - **Mão de Obra**: lista de funcionários alocados (preenchida do último RDO da obra, se houver).
   - **Serviços**: lista de serviços do orçamento operacional, com `% atual` e `% novo` por subatividade.
   - **Equipamentos**, **Fotos**, **Ocorrências**, **Clima**.
5. Em **Mão de Obra**, ajuste **horas trabalhadas** e **horas extras** de cada funcionário; remova quem não veio com o "x".
6. Em **Serviços**, atualize o **`% novo`** das subatividades executadas hoje (sempre `≥ % atual`).
7. Suba **fotos** pelo botão **"Adicionar Foto"** (funciona com câmera do celular).
8. Registre **ocorrências** se houver (descrição + severidade).
9. Clique em **"Salvar RDO"** — fica como **Rascunho** e pode ser editado depois.
10. Quando estiver completo, clique em **"Finalizar RDO"** — a partir desse momento ele gera **custos automáticos** e atualiza o cronograma.

> **Cuidado:** finalizar é **definitivo** para fins de custo. Se precisar corrigir depois, use **Editar** (`/rdo/<id>/editar`) — qualquer mudança ressincroniza os custos.

### 2. Visualizar / editar um RDO
1. Em `/rdos` (lista), clique no card do RDO.
2. A tela `/rdo/<id>` mostra todas as seções em modo leitura.
3. Para alterar, clique em **"Editar"** no topo. RDOs **Finalizados** podem ser reabertos pela mesma rota.
4. Use **"Duplicar"** para criar um RDO do dia seguinte com a mesma equipe e os mesmos % de progresso de partida.

### 3. Excluir um RDO
1. Em `/rdo/<id>`, clique em **"Excluir"** (botão vermelho).
2. Confirme no diálogo. A exclusão usa **POST** e pede confirmação dupla.
3. **Cuidado:** excluir um RDO finalizado **reverte os custos** e o **avanço** que ele havia gerado.

### 4. Painel "RDOs por obra" (`/funcionario/obras`)
1. Útil para encarregados que tocam várias obras.
2. Lista cada obra com o **último RDO** e botões rápidos: **Ver**, **Novo RDO**, **Histórico**.

## Dicas e cuidados

- **Registre o RDO no dia certo.** A `data_relatorio` é a referência para custos, folha, cronograma e medição. Trocar a data depois desloca tudo.
- **Atualize o `% novo` das subatividades** — sem isso o cronograma não avança e o painel de produtividade fica vazio.
- **Fotos**: o sistema aceita JPG/PNG. No celular, prefira capturar pela própria página em vez de subir do rolo da câmera (a foto fica georreferenciada com data).
- **Ocorrências** aparecem para o cliente no portal: redija com clareza profissional.
- **Clima** afeta produtividade — registrar dias de chuva ajuda a justificar atrasos depois.
- A rota antiga `/rdo/novo` continua funcionando, mas a recomendada é **`/funcionario/rdo/consolidado`** (tela moderna, unificada e mais rápida).
