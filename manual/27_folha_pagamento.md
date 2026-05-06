# Folha de Pagamento

A **Folha de Pagamento** processa o cálculo mensal dos colaboradores a partir dos **registros de ponto**, **benefícios cadastrados**, **adiantamentos aprovados** e **parâmetros legais** (INSS, IRRF, FGTS, salário-família). Gera holerites em PDF, relatório analítico e os lançamentos correspondentes em contas a pagar.

## Para que serve

- Calcular automaticamente a **folha mensal** por funcionário (mensalistas, diaristas, horistas).
- Aplicar **parâmetros legais** vigentes (faixas de INSS/IRRF, alíquota FGTS).
- Incluir **benefícios** (VA, VT, plano de saúde) e **descontos** (adiantamentos, faltas).
- Emitir **holerites em PDF** individuais e o **relatório analítico** consolidado do mês.
- Registrar **adiantamentos** com fluxo de aprovação.

## Como acessar

- **Menu superior → "Financeiro" → "Folha de Pagamento"** abre `/folha/dashboard`.
- **Parâmetros legais**: `/folha/parametros-legais`.
- **Benefícios**: `/folha/beneficios`.
- **Adiantamentos**: `/folha/adiantamentos`.
- **Relatórios**: `/folha/relatorios`.

## Fluxos principais

### 1. Configurar parâmetros legais (uma vez ou ao mudar a tabela)
1. **Menu → Financeiro → Folha de Pagamento → Parâmetros Legais**.
2. Se for a primeira vez, o dashboard exibe o aviso amarelo **"Configurar Parâmetros"** — clique nele.
3. Em `/folha/parametros-legais/criar`, preencha:
   - **Vigência** (mês/ano de início).
   - Faixas de **INSS** (percentual e teto por faixa).
   - Faixas de **IRRF** (alíquota, dedução por dependente).
   - **FGTS** (8 % padrão).
   - **Salário-família** e demais constantes.
4. Clique em **"Salvar"**. Os parâmetros viram a base de cálculo das competências futuras.

### 2. Cadastrar benefícios padrão
1. **Menu → Folha → Benefícios** (`/folha/beneficios`).
2. Clique em **"+ Novo Benefício"** (`/folha/beneficios/criar`).
3. Preencha **Nome**, **Tipo** (provento/desconto), **Valor fixo ou % sobre salário**, e marque se é **CLT** (compõe base de INSS).
4. Salve — o benefício passa a estar disponível para vincular aos funcionários.

### 3. Lançar e aprovar adiantamento
1. **Menu → Folha → Adiantamentos** (`/folha/adiantamentos`).
2. **"+ Novo Adiantamento"** (`/folha/adiantamentos/criar`).
3. Selecione o **funcionário**, **valor**, **competência de desconto** e justificativa.
4. Salve como **PENDENTE** e clique em **"Aprovar"** quando autorizar — o desconto entra na próxima folha.
5. Para negar, use **"Rejeitar"** com motivo.

### 4. Processar a folha do mês
1. **Menu → Folha → Dashboard** (`/folha/dashboard`).
2. No topo, escolha a **Competência** no seletor (ex.: "Outubro/2026").
3. Clique em **"Processar Folha"** → **"Processar [mês]"**.
4. O sistema busca:
   - Registros de **ponto** do período (horas normais, extras, faltas).
   - **Benefícios** vinculados ao funcionário.
   - **Adiantamentos** aprovados com competência no mês.
   - **Parâmetros legais** vigentes.
5. Calcula INSS, IRRF, FGTS e líquido. Cria um registro `FolhaProcessada` por funcionário.
6. Para reprocessar (ex.: depois de corrigir ponto), use **"Reprocessar [mês]"** — sobrescreve os cálculos anteriores.

### 5. Emitir holerites e relatório analítico
1. Em `/folha/dashboard`, depois de processado, aparecem os cards com cada funcionário e botão **"Holerite PDF"**.
2. Holerite individual: `/folha/relatorios/holerite/<folha_id>` — abre PDF pronto para imprimir/enviar.
3. **Relatório analítico** do mês: `/folha/relatorios/analitico/<ano>/<mes>` — planilha com todos os funcionários e proventos/descontos.
4. Tela geral de relatórios: `/folha/relatorios`.

## Dicas e cuidados

- **Sempre revise os parâmetros legais** no início do ano (alterações de tabela INSS/IRRF) — o cálculo usa a vigência mais recente.
- **Reprocessar a folha** sobrescreve cálculos. Se já entregou holerite, gere e arquive antes de reprocessar.
- **Adiantamento aprovado depois do processamento** só desconta na próxima competência — aprove antes de processar.
- O **VA/VT** cadastrado no **funcionário** (módulo Funcionários) entra automaticamente. Use os benefícios do `/folha/beneficios` para itens que não são por funcionário fixo.
- **Funcionários inativos** com folha do mês corrente ainda processam — confira a data de demissão antes de rodar.
- O cálculo depende de **registros de ponto fechados**. Confira em **Ponto** se há lançamentos faltando antes de processar.
