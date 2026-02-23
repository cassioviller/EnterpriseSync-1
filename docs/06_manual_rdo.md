# Capitulo 6 — Relatorio Diario de Obra (RDO)

## 6.1. Introducao ao RDO

O **Relatorio Diario de Obra (RDO)** e o principal instrumento de registro e controle da execucao fisica de uma obra no SIGE. Funciona como um verdadeiro **diario de bordo** da construcao, documentando tudo o que acontece no canteiro de obras a cada dia: mao de obra presente, equipamentos utilizados, servicos executados, condicoes climaticas e registros fotograficos.

### Por que o RDO e essencial?

| Beneficio | Descricao |
|-----------|-----------|
| **Registro historico** | Documenta diariamente todas as atividades executadas no canteiro |
| **Controle de progresso automatico** | Ao aprovar um RDO, o sistema atualiza automaticamente o percentual de conclusao da obra |
| **Rastreabilidade** | Permite verificar quem trabalhou, quais servicos foram realizados e em que condicoes |
| **Evidencia fotografica** | Fotos otimizadas em WebP comprovam a execucao dos servicos |
| **Integracao financeira** | Dados de mao de obra e equipamentos alimentam o modulo financeiro |
| **Base para medicoes** | Serve como base documental para medicoes contratuais com o cliente |

> **Importante:** O RDO foi projetado com **design mobile-first**, permitindo que o responsavel pela obra preencha o relatorio diretamente do canteiro, usando smartphone ou tablet.

### Fluxo Geral do RDO

```
Criacao (Rascunho) → Elaboracao → Envio para Aprovacao → Aprovacao/Rejeicao → Atualizacao Automatica da Obra
```

O sistema utiliza um **EventManager** para integracoes automaticas: ao aprovar um RDO, o progresso da obra, os indicadores financeiros e o dashboard sao atualizados de forma automatica e transparente.

---

## 6.2. Tela Principal de RDOs

### Acessando a Lista Consolidada

Para acessar a tela principal de RDOs, navegue pelo menu lateral ate:

**Menu → RDO → Lista Consolidada**

A URL de acesso direto e: `/funcionario/rdo/consolidado`

![Tela principal de RDOs - Lista consolidada](placeholder_rdo_lista_consolidada.png)

### Colunas da Lista

A tabela consolidada de RDOs apresenta as seguintes informacoes:

| Coluna | Descricao | Exemplo |
|--------|-----------|---------|
| **Numero RDO** | Identificador unico gerado automaticamente | RDO-10-2025-013 |
| **Obra** | Nome da obra associada ao RDO | Obra E2E Test yBSJZA |
| **Data** | Data do relatorio diario | 27/10/2025 |
| **Status** | Situacao atual do RDO | Rascunho |
| **Progresso** | Percentual de conclusao dos servicos registrados | 45,2% |
| **Acoes** | Botoes para visualizar, editar ou excluir | Visualizar / Editar |

### Filtros Disponiveis

A tela principal oferece filtros para localizar RDOs rapidamente:

1. **Filtro por Obra** — Selecione uma obra especifica no dropdown
2. **Filtro por Status** — Filtre por Rascunho, Em Elaboracao, Pendente de Aprovacao, Aprovado ou Reprovado
3. **Filtro por Data Inicio** — Defina a data inicial do periodo de busca
4. **Filtro por Data Fim** — Defina a data final do periodo de busca
5. **Filtro por Funcionario** — Filtre por responsavel pelo preenchimento

### Status dos RDOs

O sistema utiliza os seguintes status para controle do ciclo de vida do RDO:

| Status | Descricao | Cor |
|--------|-----------|-----|
| **Rascunho** | RDO criado, ainda em preenchimento inicial | Cinza |
| **Em Elaboracao** | RDO sendo preenchido com detalhes de servicos e mao de obra | Azul |
| **Pendente de Aprovacao** | RDO finalizado e enviado para aprovacao do gestor | Amarelo |
| **Aprovado** | RDO revisado e aprovado pelo gestor — atualiza progresso da obra | Verde |
| **Reprovado** | RDO rejeitado com observacoes — necessita correcao e reenvio | Vermelho |

### Acoes Rapidas

Na lista de RDOs, cada registro apresenta botoes de acao:

- **Visualizar** — Abre o RDO em modo somente leitura com todos os detalhes
- **Editar** — Abre o formulario de edicao (disponivel apenas para RDOs em Rascunho ou Em Elaboracao)
- **Excluir** — Remove o RDO e todas as suas dependencias (mao de obra, equipamentos, fotos, subatividades)

> **Dica:** Na tela de Obras (`/funcionario/obras`), cada obra possui um botao **"+RDO"** que permite criar um novo RDO ja vinculado aquela obra, agilizando o preenchimento.

---

## 6.3. Criando um Novo RDO

### Acesso ao Formulario de Criacao

Existem duas formas de criar um novo RDO:

1. **Pela tela de RDOs:** Clique no botao **"Novo RDO"** na lista consolidada
   - URL: `/rdo/novo`
2. **Pela tela de Obras:** Clique no botao **"+RDO"** na obra desejada
   - URL: `/funcionario/rdo/novo?obra_id=<id_da_obra>`

Ao acessar via obra, o formulario ja vem com a obra pre-selecionada e com as atividades do ultimo RDO pre-carregadas.

![Formulario de criacao de novo RDO](placeholder_rdo_novo_formulario.png)

### 6.3.1. Informacoes Gerais

O primeiro bloco do formulario solicita as informacoes basicas do RDO:

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|:-----------:|-----------|
| **Obra** | Dropdown de selecao | Sim | Selecione a obra para a qual o RDO sera registrado |
| **Data** | Campo de data | Sim | Data do relatorio (padrao: data atual) |
| **Condicao Climatica — Manha** | Dropdown | Sim | Condicao do tempo no periodo da manha (Bom, Nublado, Chuvoso, etc.) |
| **Condicao Climatica — Tarde** | Dropdown | Sim | Condicao do tempo no periodo da tarde |
| **Observacoes Meteorologicas** | Texto livre | Nao | Detalhes adicionais sobre as condicoes climaticas |
| **Comentario Geral** | Texto livre | Nao | Observacoes gerais sobre o dia de trabalho |

**Regras de Negocio:**

- O sistema **nao permite** criar dois RDOs para a mesma obra na mesma data. Se ja existir um RDO para a combinacao obra + data selecionada, o usuario sera redirecionado automaticamente para a edicao do RDO existente.
- O **numero do RDO** e gerado automaticamente pelo sistema no formato: `RDO-<obra_id>-<ano>-<sequencial>` (exemplo: RDO-10-2025-013).
- O **responsavel** e identificado automaticamente pelo usuario logado no sistema.

> **Importante:** O campo de data vem preenchido com a data atual, mas pode ser alterado para registrar RDOs retroativos, caso necessario.

### 6.3.2. Mao de Obra

A secao de Mao de Obra permite registrar todos os trabalhadores presentes no canteiro durante o dia:

| Campo | Descricao |
|-------|-----------|
| **Funcionario** | Selecao do funcionario presente (lista filtrada pela obra) |
| **Funcao** | Funcao exercida pelo trabalhador no dia |
| **Tipo** | Classificacao: **Proprio** (equipe interna) ou **Terceirizado** |
| **Horas Trabalhadas** | Quantidade de horas trabalhadas no dia |

**Como adicionar mao de obra:**

1. Clique no botao **"Adicionar Mao de Obra"**
2. Selecione o funcionario no dropdown
3. Informe a funcao exercida
4. Selecione o tipo (proprio ou terceirizado)
5. Informe as horas trabalhadas
6. Repita para cada trabalhador presente

![Secao de mao de obra do RDO](placeholder_rdo_mao_obra.png)

> **Dica:** O sistema pre-carrega a lista de funcionarios ativos vinculados a empresa, facilitando a selecao rapida.

### 6.3.3. Equipamentos

A secao de Equipamentos registra as maquinas e equipamentos utilizados no dia:

| Campo | Descricao |
|-------|-----------|
| **Descricao** | Nome ou descricao do equipamento utilizado |
| **Quantidade** | Quantidade de unidades do equipamento |
| **Tipo** | Classificacao: **Proprio** ou **Alugado** |

**Como adicionar equipamentos:**

1. Clique no botao **"Adicionar Equipamento"**
2. Informe a descricao do equipamento (ex: "Retroescavadeira CAT 416F")
3. Informe a quantidade
4. Selecione o tipo (proprio ou alugado)
5. Repita para cada equipamento utilizado

---

## 6.4. Registrando Atividades no RDO

A secao de Atividades e a parte mais importante do RDO, pois alimenta diretamente o calculo de progresso da obra. O sistema utiliza uma estrutura hierarquica: **Servicos → Subatividades**.

### 6.4.1. Selecionando Servicos

Os servicos disponiveis para registro no RDO sao aqueles previamente cadastrados na obra atraves do modulo de **Servicos da Obra** (`servico_obra_real`).

**Pre-carregamento inteligente:**

- Ao criar o **primeiro RDO** de uma obra, o sistema carrega automaticamente todos os servicos cadastrados naquela obra, com suas respectivas subatividades
- Ao criar **RDOs subsequentes**, o sistema pre-carrega os dados do ultimo RDO da obra, permitindo atualizar os percentuais de conclusao

| Informacao Exibida | Descricao |
|--------------------|-----------|
| **Nome do Servico** | Nome do servico cadastrado (ex: "Alvenaria de Vedacao") |
| **Categoria** | Categoria do servico (ex: "Estrutura", "Acabamento") |
| **Quantidade Planejada** | Quantidade total planejada para o servico na obra |
| **Unidade de Medida** | Unidade utilizada (m2, m3, kg, un, m, h, etc.) |

### 6.4.2. Registrando Subatividades

Cada servico pode conter multiplas **subatividades** cadastradas na tabela mestre (`SubatividadeMestre`). No RDO, o usuario registra:

| Campo | Descricao |
|-------|-----------|
| **Subatividade** | Nome da subatividade (pre-carregado da tabela mestre) |
| **Quantidade Executada** | Quantidade efetivamente executada no dia |
| **Percentual de Conclusao** | Percentual acumulado de conclusao da subatividade |
| **Observacoes Tecnicas** | Notas tecnicas sobre a execucao |

**Calculo de Progresso:**

O progresso total do RDO e calculado como a **media simples** dos percentuais de conclusao de todas as subatividades registradas:

```
Progresso Total = Soma dos Percentuais / Numero de Subatividades
```

Exemplo: Se um RDO possui 3 subatividades com 100%, 50% e 30%, o progresso total sera:
```
(100 + 50 + 30) / 3 = 60%
```

### 6.4.3. Anexando Fotos

O sistema permite anexar fotografias para documentar a execucao dos servicos:

| Campo | Descricao |
|-------|-----------|
| **Foto** | Upload de imagem (JPG, PNG ou WebP) |
| **Descricao** | Descricao da foto (o que ela documenta) |
| **Tipo** | Classificacao da foto (servico, material, seguranca, etc.) |

**Caracteristicas do upload de fotos:**

- As fotos sao automaticamente **otimizadas para formato WebP**, reduzindo o tamanho do arquivo sem perda significativa de qualidade
- As fotos sao armazenadas na pasta `static/uploads/rdo/<obra_id>/<rdo_id>/`
- E possivel anexar multiplas fotos por RDO
- As fotos ficam disponiveis para visualizacao na tela de detalhes do RDO e no portal do cliente

![Secao de upload de fotos do RDO](placeholder_rdo_fotos_upload.png)

> **Dica Mobile:** O upload de fotos foi otimizado para dispositivos moveis, permitindo capturar fotos diretamente da camera do smartphone e anexar ao RDO em tempo real.

---

## 6.5. Finalizando e Enviando para Aprovacao

Apos preencher todas as secoes do RDO, o usuario pode:

### Salvar como Rascunho

- Clique no botao **"Salvar Rascunho"**
- O RDO sera salvo com status **Rascunho** e podera ser editado posteriormente
- Ideal para quando o preenchimento sera concluido em outro momento

### Enviar para Aprovacao

1. Revise todas as informacoes preenchidas (mao de obra, equipamentos, servicos, fotos)
2. Clique no botao **"Enviar para Aprovacao"**
3. O status do RDO sera alterado para **Pendente de Aprovacao**
4. O gestor/administrador recebera uma notificacao sobre o novo RDO pendente

**Checklist antes de enviar:**

- [ ] Condicoes climaticas informadas para manha e tarde
- [ ] Mao de obra presente registrada com horas trabalhadas
- [ ] Equipamentos utilizados registrados (se houver)
- [ ] Servicos e subatividades com percentuais atualizados
- [ ] Fotos anexadas documentando os servicos executados
- [ ] Comentarios e observacoes preenchidos quando necessario

> **Atencao:** Apos o envio para aprovacao, o RDO **nao podera ser editado** pelo responsavel ate que o gestor aprove ou rejeite o documento.

---

## 6.6. Aprovacao de RDOs

O fluxo de aprovacao e responsabilidade do **gestor** ou **administrador** da empresa.

### Acessando RDOs Pendentes

1. Acesse a lista de RDOs pelo menu lateral
2. Utilize o filtro de status **"Pendente de Aprovacao"**
3. Os RDOs pendentes serao exibidos com destaque visual (badge amarelo)

### Fluxo de Aprovacao

O gestor pode realizar as seguintes acoes em um RDO pendente:

| Acao | Descricao | Resultado |
|------|-----------|-----------|
| **Aprovar** | Confirma que os dados do RDO estao corretos | Status muda para **Aprovado**; progresso da obra e atualizado automaticamente |
| **Reprovar** | Indica que o RDO necessita de correcoes | Status muda para **Reprovado**; RDO retorna para edicao do responsavel |

### Aprovando um RDO

1. Abra o RDO pendente clicando em **"Visualizar"**
2. Revise todos os dados: mao de obra, servicos executados, fotos e observacoes
3. Clique no botao **"Aprovar RDO"**
4. Confirme a aprovacao na caixa de dialogo
5. O sistema registra o aprovador e a data/hora da aprovacao

**Dados registrados na aprovacao:**

- `aprovado_por` — Identificacao do gestor que aprovou
- `data_aprovacao` — Data e hora exata da aprovacao

### Reprovando um RDO

1. Abra o RDO pendente clicando em **"Visualizar"**
2. Identifique os pontos que necessitam correcao
3. Clique no botao **"Reprovar RDO"**
4. Informe o motivo da reprovacao no campo de observacoes
5. O RDO retorna para o status de edicao e o responsavel pode corrigir e reenviar

> **Boas praticas para aprovacao:** Sempre verifique se as fotos anexadas correspondem aos servicos declarados e se os percentuais de conclusao sao coerentes com o historico da obra.

---

## 6.7. Impacto do RDO no Sistema

O RDO nao e apenas um documento de registro — ele e o **motor de atualizacao** de diversos modulos do SIGE. Quando um RDO e aprovado, uma cadeia de atualizacoes automaticas e disparada pelo **EventManager**.

### 6.7.1. Atualizacao Automatica do Progresso da Obra

Ao aprovar um RDO, o sistema:

1. Recalcula o percentual de conclusao de cada servico da obra baseado nas subatividades registradas
2. Atualiza o campo `quantidade_executada` dos servicos reais (`servico_obra_real`)
3. Recalcula o percentual de conclusao global da obra
4. Atualiza o status do servico (Nao Iniciado → Em Andamento → Concluido)

### 6.7.2. Atualizacao Financeira

Os dados de mao de obra e equipamentos alimentam o modulo financeiro:

- **Horas trabalhadas** sao contabilizadas para calculo de custo de mao de obra
- **Equipamentos alugados** sao considerados no custo operacional
- A **produtividade** (quantidade/hora) e registrada no historico de produtividade por servico

### 6.7.3. Atualizacao do Dashboard

O dashboard principal reflete os dados dos RDOs aprovados:

- **KPIs de progresso** sao recalculados com base nos servicos atualizados
- **Graficos de evolucao** apresentam a curva de progresso real vs. planejado
- **Alertas** sao gerados automaticamente quando o progresso esta abaixo do esperado

### 6.7.4. Portal do Cliente

Quando o portal do cliente esta ativo para a obra:

- O progresso atualizado e refletido automaticamente no portal
- As fotos do RDO podem ser disponibilizadas para visualizacao do cliente
- Notificacoes sao enviadas ao cliente sobre atualizacoes relevantes

---

## 6.8. Relatorios de RDO

O SIGE oferece opcoes de geracao de relatorios a partir dos dados coletados nos RDOs.

### 6.8.1. Relatorio Consolidado

O relatorio consolidado apresenta uma visao geral de todos os RDOs de uma obra ou periodo:

| Informacao | Descricao |
|------------|-----------|
| **Resumo de Mao de Obra** | Total de horas trabalhadas por funcionario e por tipo (proprio/terceirizado) |
| **Resumo de Equipamentos** | Equipamentos utilizados com classificacao proprio/alugado |
| **Progresso Acumulado** | Evolucao do percentual de conclusao dos servicos ao longo do tempo |
| **Condicoes Climaticas** | Historico de condicoes climaticas que podem justificar atrasos |
| **Registro Fotografico** | Galeria cronologica de fotos organizadas por data |

**Filtros do relatorio consolidado:**

1. **Periodo** — Selecione data inicio e data fim
2. **Obra** — Filtre por obra especifica
3. **Status** — Inclua apenas RDOs aprovados, todos, ou filtre por status especifico

### 6.8.2. Exportacao Individual em PDF

Cada RDO pode ser exportado individualmente em formato PDF contendo:

- Cabecalho com dados da obra e data do relatorio
- Condicoes climaticas do dia
- Tabela de mao de obra com horas trabalhadas
- Tabela de equipamentos utilizados
- Detalhamento de servicos e subatividades executadas
- Fotos anexadas com descricoes
- Observacoes gerais e assinatura do responsavel

**Para exportar um RDO em PDF:**

1. Acesse o RDO desejado clicando em **"Visualizar"**
2. Clique no botao **"Exportar PDF"** localizado no topo da pagina
3. O arquivo PDF sera gerado e disponibilizado para download

![Exemplo de RDO exportado em PDF](placeholder_rdo_pdf_export.png)

### 6.8.3. Relatorio de Produtividade

O sistema gera relatorios de produtividade baseados nos dados dos RDOs:

| Metrica | Calculo |
|---------|---------|
| **Produtividade por Servico** | Quantidade executada / Horas de mao de obra |
| **Eficiencia da Equipe** | Comparacao entre planejado e realizado |
| **Custo Real vs. Orcado** | Custo de mao de obra real vs. custo orcado por servico |

---

## Resumo do Capitulo

O RDO e a peca central do controle de execucao de obras no SIGE. Atraves dele, o responsavel em campo documenta diariamente o que foi realizado, permitindo que gestores acompanhem o progresso em tempo real e tomem decisoes baseadas em dados concretos.

**Pontos-chave:**

1. O RDO registra mao de obra, equipamentos, servicos executados e fotos
2. O preenchimento e otimizado para dispositivos moveis (mobile-first)
3. O fluxo de aprovacao garante a qualidade dos dados registrados
4. A aprovacao do RDO dispara atualizacoes automaticas de progresso, financeiro e dashboard
5. Fotos sao otimizadas automaticamente para WebP, economizando armazenamento
6. Relatorios consolidados e PDFs individuais podem ser gerados a qualquer momento

---

*Proximo capitulo: [Capitulo 7 — Modulo Financeiro](07_manual_financeiro.md)*
