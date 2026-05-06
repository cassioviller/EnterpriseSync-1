# Cronograma

O **Cronograma** mostra o planejamento físico da obra em formato Gantt, com hierarquia (grupos → tarefas → subtarefas), datas de início/fim, dependências e progresso real apurado pelos RDOs. Foi remodelado recentemente: hoje suporta arrastar para reordenar, recalcular automaticamente as datas e gerar templates reutilizáveis para novas obras.

## Para que serve

- Planejar e visualizar as **fases e tarefas** de cada obra com datas previstas.
- Apurar o **progresso real** por tarefa a partir dos apontamentos do RDO.
- Comparar **planejado × realizado** com a curva de avanço.
- Manter um **catálogo de subatividades** padrão e **templates de cronograma** reutilizáveis.
- Acompanhar o **painel de produtividade** consolidando todas as obras.

## Como acessar

- **Menu superior → "Obras" → "Cronograma Físico"** abre `/cronograma/` (lista de obras com cronograma).
- **Menu superior → "Obras" → "Painel de Produtividade"** abre `/cronograma/produtividade`.
- Dentro de uma obra: o cronograma específico está em `/cronograma/obra/<obra_id>`.
- **Catálogo de subatividades**: `/cronograma/catalogo`.
- **Templates de cronograma**: `/cronograma/templates`.
- **Calendário (feriados/dias úteis)**: `/cronograma/calendario`.

## Fluxos principais

### 1. Abrir e navegar no cronograma de uma obra
1. **Menu → Obras → Cronograma Físico** lista todas as obras.
2. Clique na obra desejada — abre `/cronograma/obra/<id>` em formato Gantt.
3. Linhas têm **três níveis**: Grupo (negrito) → Tarefa → Subatividade.
4. Use o **scroll horizontal** para navegar nas datas; o **zoom** (dia/semana/mês) está no topo.
5. Barras coloridas indicam: cinza = planejado, verde = realizado dentro do prazo, amarelo = em atraso.

### 2. Adicionar uma tarefa nova
1. No cronograma da obra, clique em **"+ Nova Tarefa"** (botão verde) ou no **"+"** ao lado de um grupo.
2. Preencha **Nome**, **Data Início**, **Duração (dias)** ou **Data Fim**, e **Predecessora** (opcional).
3. Clique em **"Salvar"** — a tarefa entra na grade e o sistema recalcula as datas dependentes.

### 3. Reordenar / mover tarefas (drag-and-drop)
1. Clique e segure no **handle** (≡) à esquerda da linha.
2. Arraste para a posição desejada (mesma hierarquia).
3. Solte — o sistema chama `/cronograma/obra/<id>/reordenar` automaticamente e atualiza a ordem.

### 4. Editar / excluir tarefa
1. Clique na linha da tarefa para abrir o modal de edição.
2. Ajuste campos (datas, duração, predecessora, peso) e clique em **"Salvar"**.
3. Para excluir, use o botão **"Excluir"** dentro do modal (confirma com diálogo).

### 5. Recalcular datas em cascata
1. Botão **"Recalcular"** no topo do cronograma.
2. O sistema percorre toda a árvore aplicando dependências e o calendário (pula fins de semana e feriados se configurado).

### 6. Aplicar template a uma obra nova
1. Em `/cronograma/templates`, clique em **"Novo Template"** ou edite um existente.
2. Adicione tarefas e marque um como **"Padrão"** se quiser que ele seja usado por padrão.
3. Para aplicar a uma obra: dentro do cronograma da obra, clique em **"Aplicar Template"** e escolha o template.
4. As tarefas são copiadas para a obra com as datas calculadas a partir da data de início.

### 7. Painel de produtividade
1. **Menu → Obras → Painel de Produtividade**.
2. Mostra, por obra/serviço, **horas previstas vs. horas reais**, **índice de produtividade** e ranking.
3. Use os filtros de período no topo para comparar meses ou trimestres.

## Dicas e cuidados

- **Recalcular** sobrescreve datas manuais que dependiam de uma predecessora alterada — confira antes de salvar.
- O **catálogo de subatividades** é compartilhado por toda a empresa; cuidado ao excluir um item que possa estar em uso.
- **Templates** são úteis para tipos de obra recorrentes (residencial, comercial, reforma). Crie um template por tipo e mantenha a padronização.
- A produtividade depende de **RDOs finalizados** com `% novo` preenchido — se o painel parecer vazio, comece pelos RDOs.
- O **calendário da empresa** define quais dias são úteis. Configure feriados antes de aplicar templates a obras novas.
