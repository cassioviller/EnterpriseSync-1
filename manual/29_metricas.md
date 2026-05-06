# Métricas

O módulo **Métricas** (`/metricas/`) calcula a **produtividade real** da empresa cruzando **horas de RDO**, **custos**, **receitas (orçamento)** e **coeficientes de catálogo**. Tem três visões principais: **por serviço** (empresa), **por funcionário** e **drill-down de divergências**.

## Para que serve

- Medir **horas-homem por unidade de serviço** entregue (m², m³, un.) e comparar com o coeficiente de catálogo.
- Identificar **funcionários que produzem menos que a média** ou que têm **custo > receita** no período.
- Aplicar a **produtividade média real** como **referência** que sobrescreve o coeficiente do catálogo.
- Drilldown: ver **quais RDOs causaram a divergência** em um serviço problemático.

## Como acessar

- **Não há item no menu principal `base_completo.html`** — o acesso é direto pela URL ou via templates internos.
- **Empresa por serviço:** `/metricas/servico`.
- **Funcionários (cards):** `/metricas/funcionarios`.
- **Detalhe do funcionário:** `/metricas/funcionarios/<id>`.
- **Ranking:** `/metricas/ranking`.
- **Divergência por serviço:** `/metricas/divergencia/servico/<servico_id>`.

## Fluxos principais

### 1. Empresa por serviço — comparar real × catálogo

1. Abra `/metricas/servico`.
2. Período padrão: **últimos 90 dias**. Ajuste **Data Início**, **Data Fim** e, opcionalmente, filtre por **obra**.
3. A tabela mostra cada serviço com:
   - **Quantidade entregue** no período (somada dos RDOs).
   - **Horas-homem reais** lançadas.
   - **Produtividade real** (HH/un.) e **produtividade catálogo**.
   - **Índice empresa × catálogo** (% acima/abaixo).
4. Use o link de cada serviço para abrir a divergência detalhada.

### 2. Aplicar produtividade real como referência

1. Em `/metricas/servico`, na linha do serviço desejado, clique no botão **"Aplicar como referência"**.
2. Confirme o POST para `/metricas/servico/aplicar-referencia`.
3. O sistema atualiza o `coeficiente_padrao` dos insumos do tipo "mão-de-obra" daquele serviço para refletir a média real.
4. Mensagem de sucesso informa quantos coeficientes foram atualizados.

### 3. Produção por funcionário (cards)

1. Abra `/metricas/funcionarios`.
2. Filtros: **período**, **obras** (multi-select), **funções** (multi-select), **status** (`com_custo`, `sem_custo`, `com_receita`, `todos`).
3. Cada card mostra:
   - **Horas normais / extras**, **dias com RDO**, **assiduidade**.
   - **Custo total**, **receita total**, **lucro**, **prod. real** e **índice vs. pares**.
4. Funcionários **ativos sem nenhum RDO no período** aparecem como **cards cinza** ("zero_rdo") para forçar o gestor a investigar.
5. Para funcionários com **lucro negativo** ou **custo sem receita**, o card lista os **3 piores RDOs** com link para análise.

### 4. Detalhe do funcionário

1. Clique no nome do funcionário em `/metricas/funcionarios` → abre `/metricas/funcionarios/<id>`.
2. A tela detalha por serviço: horas, quantidade entregue, prod. real e contribuição financeira.
3. Útil para conversa de feedback / plano de melhoria.

### 5. Drill-down de divergência por serviço

1. Em `/metricas/servico`, clique no link de um serviço com prejuízo.
2. Abre `/metricas/divergencia/servico/<id>`.
3. Lista cada **RDO** onde o serviço foi lançado, ordenado por **prejuízo** ou outro critério.
4. Mostra **funcionários envolvidos**, **horas**, **quantidade**, **custo**.

### 6. Ranking

1. `/metricas/ranking` consolida os melhores e piores funcionários no período em uma tabela única.
2. Útil para premiação ou para identificar quem precisa de treinamento.

## Dicas e cuidados

- **Produtividade só é confiável** quando os RDOs têm **mão-de-obra** e **quantidade entregue** preenchidos corretamente. Sem esses dados, o serviço cai como "sem produtividade".
- **Aplicar como referência** sobrescreve coeficiente de catálogo — comunique o time antes para evitar que orçamentos novos saiam diferentes do esperado.
- Os cards cinza ("sem nenhum RDO") incluem funcionários ativos do período. Se o funcionário acabou de ser admitido, considere ajustar o filtro de período.
- O cálculo memoiza dados em memória por requisição; abrir `/metricas/funcionarios` em obra grande pode levar alguns segundos na primeira chamada.
- Em demos com poucos dados, é normal ver "Erro ao calcular métricas" — pode indicar `produtividade_por_servico` sem amostras; verifique o RDO antes de interpretar como bug.
