# Capítulo 3 — Gestão de Funcionários

## 3.1. Introdução à Gestão de Funcionários

O módulo de **Gestão de Funcionários** do SIGE (Sistema Integrado de Gestão Empresarial) centraliza todas as operações relacionadas ao cadastro, acompanhamento e controle da força de trabalho da empresa. Este módulo é acessado pelo menu lateral **Funcionários** na barra de navegação principal do sistema.

Principais funcionalidades cobertas neste capítulo:

| Funcionalidade | Descrição |
|---|---|
| Cadastro de funcionários | Registro completo com dados pessoais, contratuais e de acesso |
| Perfil individual | Visualização detalhada de cada funcionário com KPIs e histórico |
| Reconhecimento facial | Cadastro de múltiplas fotos para verificação de identidade no ponto |
| Controle de ponto eletrônico | Registro, visualização e gestão de frequência com validação biométrica |
| Relatórios | Geração de relatórios individuais e consolidados em PDF |

> **Pré-requisito:** Para utilizar este módulo, o usuário deve possuir permissão de **Administrador** ou **Gestor de Equipes**. Funcionários com perfil básico terão acesso apenas ao seu próprio dashboard em `/funcionario-dashboard`.

---

## 3.2. Tela Principal de Funcionários

### Acessando a Tela

1. No menu de navegação superior, clique em **Funcionários**.
2. O sistema direcionará você para a URL `/funcionarios`.

![Tela principal de funcionários](placeholder_tela_funcionarios.png)

### Visão Geral da Interface

A tela principal de funcionários é dividida nas seguintes áreas:

#### KPIs Resumidos (Topo)

No topo da página, são exibidos indicadores-chave de desempenho (KPIs) gerais do período selecionado:

| KPI | Descrição |
|---|---|
| Total de Funcionários | Quantidade de funcionários ativos cadastrados |
| Horas Trabalhadas | Soma total de horas trabalhadas no período |
| Horas Extras | Total de horas extras acumuladas |
| Faltas | Quantidade de faltas registradas (justificadas e não justificadas) |
| Custo Total | Custo estimado com mão de obra no período |
| Taxa de Absenteísmo | Percentual de ausências em relação aos dias úteis possíveis |

#### Filtros de Período

Acima dos cards de funcionários, há campos para filtrar os dados por período:

1. **Data Início** — Define o início do período de análise (padrão: primeiro dia do mês atual).
2. **Data Fim** — Define o final do período de análise (padrão: data atual).
3. Clique em **Filtrar** para atualizar os KPIs e dados exibidos.

#### Cards de Funcionários

Os funcionários são exibidos em formato de **cards** (cartões visuais), cada um contendo:

- **Foto ou avatar com iniciais** — Se o funcionário possui foto cadastrada, ela será exibida. Caso contrário, um avatar com as iniciais do nome é gerado automaticamente.
- **Nome completo** do funcionário.
- **Função/Cargo** atribuído ao funcionário.
- **Checkbox de seleção** — Permite selecionar múltiplos funcionários para operações em lote.

![Card de funcionário com foto e informações](placeholder_card_funcionario.png)

#### Busca e Filtros

A tela oferece recursos de busca e filtragem:

1. **Campo de busca** — Digite o nome, CPF ou código do funcionário para localizar rapidamente.
2. **Filtro por departamento** — Filtre os funcionários por departamento.
3. **Filtro por função** — Filtre por cargo/função.
4. **Filtro por status** — Visualize funcionários ativos, inativos ou todos.

#### Operações em Lote

Após selecionar funcionários via checkbox, é possível realizar operações em lote como:

- Lançamento de ponto para múltiplos funcionários simultaneamente.
- Alocação em obras.
- Exportação de dados selecionados.

---

## 3.3. Cadastrando um Novo Funcionário

O cadastro de novos funcionários é realizado diretamente na tela principal `/funcionarios`, por meio de um formulário modal. Não existe uma página separada para criação.

### Passo a Passo

1. Na tela de funcionários (`/funcionarios`), clique no botão **+ Novo Funcionário**.
2. Um formulário modal será aberto com os campos organizados em seções.
3. Preencha os dados conforme descrito nas subseções abaixo.
4. Clique em **Salvar** para confirmar o cadastro.

![Modal de cadastro de novo funcionário](placeholder_modal_novo_funcionario.png)

### 3.3.1. Dados Pessoais

Preencha as informações pessoais do funcionário:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Nome | Texto | ✅ Sim | Nome completo do funcionário |
| CPF | Texto (14 caracteres) | ✅ Sim | CPF com formatação (000.000.000-00). Deve ser único no sistema |
| RG | Texto | Não | Número do documento de identidade |
| Data de Nascimento | Data | Não | Data de nascimento no formato DD/MM/AAAA |
| Endereço | Texto longo | Não | Endereço completo (rua, número, bairro, cidade, estado, CEP) |
| Telefone | Texto | Não | Telefone com DDD. Ex.: (11) 99999-0000 |
| E-mail | Texto | Não | Endereço de e-mail do funcionário |
| Foto | Arquivo (imagem) | Não | Foto do funcionário (JPG, PNG). Será exibida no card e no perfil |

> **Importante:** O CPF é validado como campo único. Caso um CPF já esteja cadastrado para outro funcionário, o sistema exibirá uma mensagem de erro e impedirá a duplicação.

### 3.3.2. Dados Contratuais

Preencha as informações referentes ao vínculo empregatício:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| Código | Texto (10 caracteres) | Não | Código interno do funcionário (ex.: VV001). Se deixado em branco, será gerado automaticamente pelo sistema |
| Data de Admissão | Data | ✅ Sim | Data de início do vínculo empregatício. Padrão: data atual |
| Salário | Numérico (R$) | Não | Salário mensal bruto do funcionário |
| Departamento | Seleção | Não | Departamento ao qual o funcionário pertence |
| Função/Cargo | Seleção | Não | Função ou cargo exercido pelo funcionário |
| Horário de Trabalho | Seleção | Não | Modelo de horário de trabalho associado (define entrada, saída, pausas e dias da semana) |

> **Código automático:** Quando o campo Código é deixado em branco, o sistema gera automaticamente um código sequencial no formato `VV001`, `VV002`, etc., baseando-se no último código cadastrado.

> **Horário de trabalho:** Os modelos de horário de trabalho podem ser configurados em **Configurações > Horários** e definem horários diferenciados para cada dia da semana (ex.: sexta-feira com expediente reduzido, sábado meio período, etc.).

### 3.3.3. Dados de Acesso

Após o cadastro, o funcionário poderá ter seu horário padrão configurado individualmente através da rota:

```
/funcionarios/<id>/horario-padrao
```

Esta configuração permite personalizar os horários de trabalho do funcionário caso ele possua uma jornada diferente do modelo padrão atribuído ao seu departamento.

---

## 3.4. Perfil do Funcionário

### Acessando o Perfil

Para acessar o perfil detalhado de um funcionário:

1. Na tela principal de funcionários, clique no **card** ou no **nome** do funcionário desejado.
2. O sistema direcionará para a URL `/funcionario_perfil/<id>`.

![Perfil completo do funcionário](placeholder_perfil_funcionario.png)

### Seções do Perfil

O perfil do funcionário está organizado nas seguintes seções:

#### Informações Pessoais

Exibe todos os dados cadastrais do funcionário:

- Nome completo, CPF, RG
- Data de nascimento e endereço
- Telefone e e-mail
- Foto (quando cadastrada)
- Departamento e função
- Data de admissão e salário
- Status (ativo/inativo)

#### KPIs Individuais

Indicadores calculados automaticamente para o período filtrado:

| Indicador | Descrição |
|---|---|
| Horas Trabalhadas | Total de horas registradas no período |
| Horas Extras | Total de horas extras acumuladas (calculadas com fator 1,5x) |
| Faltas | Quantidade de faltas não justificadas |
| Faltas Justificadas | Quantidade de faltas com justificativa/atestado |
| Atrasos | Total de horas de atraso acumuladas |
| Dias Trabalhados | Quantidade de dias com registro de ponto efetivo |
| Taxa de Absenteísmo | Percentual de faltas em relação aos dias úteis do período |
| Valor Hora | Valor da hora calculado com base no salário e jornada contratual |
| Valor Horas Extras | Custo total das horas extras (com fator 1,5x) |
| DSR sobre HE | Descanso Semanal Remunerado calculado sobre horas extras (Lei 605/49) |

#### Histórico de Ponto

Tabela detalhada com todos os registros de ponto do período, exibindo:

- Data do registro
- Hora de entrada e saída
- Hora de saída e retorno do almoço
- Horas trabalhadas e horas extras
- Tipo de registro (trabalhado, falta, feriado, etc.)
- Observações

#### Obras Vinculadas

Lista de obras nas quais o funcionário está ou esteve alocado, com informações de:

- Nome da obra
- Período de alocação
- Tipo de local (campo ou escritório)

#### Dashboard Individual

O funcionário possui um dashboard personalizado acessível em `/funcionario-dashboard`, que apresenta um resumo visual de seus indicadores de desempenho.

### Exportando o Perfil em PDF

Para gerar um relatório PDF do perfil do funcionário:

1. No perfil do funcionário, clique no botão **Exportar PDF** ou **Gerar PDF**.
2. O sistema gerará o documento e iniciará o download automaticamente.
3. A URL direta para geração do PDF é `/funcionario_perfil/<id>/pdf`.

O PDF inclui dados pessoais, KPIs do período e o histórico detalhado de registros de ponto.

---

## 3.5. Reconhecimento Facial

### 3.5.1. Importância do Reconhecimento Facial

O SIGE utiliza reconhecimento facial como camada de segurança para validar a identidade do funcionário no momento do registro de ponto. Este recurso previne fraudes como o chamado "ponto amigo" (quando um colega registra o ponto no lugar de outro).

**Parâmetros técnicos do reconhecimento:**

| Parâmetro | Valor | Descrição |
|---|---|---|
| Limiar de distância | 0.40 | Distância máxima entre a foto capturada e a foto cadastrada para considerar uma correspondência |
| Confiança mínima | 60% | Percentual mínimo de confiança exigido para validar o reconhecimento |
| Modelo utilizado | VGG-Face | Rede neural utilizada para extração de características faciais |
| Brilho aceito | 30 a 230 | Faixa de luminosidade aceita na foto (evita fotos muito escuras ou com flash excessivo) |
| Tamanho mínimo | 150×150 px | Resolução mínima da foto capturada para garantir qualidade do reconhecimento |

> **Nota:** Quanto menor a distância facial, maior a confiança de que a pessoa na foto é realmente o funcionário cadastrado.

### 3.5.2. Cadastrando Fotos Faciais

O sistema permite cadastrar **múltiplas fotos faciais** por funcionário, o que melhora significativamente a precisão do reconhecimento em diferentes condições.

#### Acessando a Gestão de Fotos Faciais

1. Acesse o perfil do funcionário em `/funcionario_perfil/<id>`.
2. Clique na opção **Fotos Faciais** ou acesse diretamente a URL:
   ```
   /ponto/funcionario/<id>/fotos-faciais
   ```

![Tela de gerenciamento de fotos faciais](placeholder_fotos_faciais.png)

#### Cadastrando uma Nova Foto

1. Na tela de fotos faciais, clique em **Adicionar Foto**.
2. A câmera do dispositivo será ativada (ou selecione um arquivo de imagem).
3. Posicione o rosto centralizado no enquadramento.
4. Capture ou selecione a foto.
5. Adicione uma **descrição** para a foto (ex.: "Frontal sem óculos", "Com óculos", "Perfil esquerdo").
6. Clique em **Salvar**.

#### Recomendações para Fotos de Qualidade

Para garantir o melhor desempenho do reconhecimento facial, siga estas orientações:

1. **Cadastre pelo menos 3 fotos** com variações:
   - Uma foto frontal sem acessórios
   - Uma foto com óculos (se o funcionário usa)
   - Uma foto em perfil lateral

2. **Iluminação adequada:**
   - Evite fotos com flash direto ou contraluz
   - Prefira ambientes com iluminação natural ou difusa
   - O sistema rejeita fotos com brilho fora da faixa 30-230

3. **Enquadramento correto:**
   - Rosto centralizado e ocupando a maior parte da imagem
   - Resolução mínima de 150×150 pixels
   - Sem obstruções no rosto (mãos, máscaras, bonés)

4. **Expressão neutra:**
   - Prefira expressões neutras ou levemente sorridente
   - Evite caretas ou expressões exageradas

| Situação | Recomendação |
|---|---|
| Funcionário usa óculos | Cadastrar fotos com e sem óculos |
| Funcionário usa barba | Atualizar fotos após mudanças significativas no visual |
| Funcionário trabalha em campo | Cadastrar foto com EPI (capacete) quando aplicável |
| Baixa taxa de reconhecimento | Adicionar mais fotos em condições variadas de iluminação |

> **Dica:** Fotos faciais podem ser gerenciadas a qualquer momento. Se o sistema apresentar dificuldade em reconhecer um funcionário, adicione novas fotos com condições de iluminação similares às do ambiente de trabalho.

---

## 3.6. Controle de Ponto Eletrônico

O módulo de ponto eletrônico do SIGE permite o registro da jornada de trabalho dos funcionários com validação por reconhecimento facial e geolocalização (geofencing).

### 3.6.1. Registrando Ponto

#### Acesso à Tela de Ponto

1. No menu de navegação, clique no dropdown **Ponto**.
2. Selecione **Registrar Ponto** para acessar a URL `/ponto`.

![Tela de registro de ponto](placeholder_registro_ponto.png)

#### Fluxo de Registro com Reconhecimento Facial

O processo de registro de ponto segue as seguintes etapas:

1. **Seleção do funcionário** — O funcionário é identificado automaticamente (se logado) ou selecionado manualmente pelo gestor.

2. **Captura da foto** — A câmera do dispositivo é ativada para capturar a foto do funcionário no momento do registro.

3. **Validação facial** — O sistema compara a foto capturada com as fotos faciais cadastradas:
   - Se a distância facial for **≤ 0.40** e a confiança **≥ 60%**: registro aprovado ✅
   - Caso contrário: registro rejeitado com mensagem de erro ❌

4. **Validação de geolocalização (Geofencing)** — Se a obra possui coordenadas cadastradas:
   - O GPS do dispositivo é consultado
   - A distância entre o funcionário e a obra é calculada
   - Se a distância for **≤ 100 metros** (raio padrão): localização validada ✅
   - Caso contrário: alerta de localização fora do perímetro ⚠️

5. **Registro efetivado** — Após as validações, o ponto é registrado com:
   - Hora de entrada ou saída
   - Foto capturada (armazenada em base64)
   - Resultado do reconhecimento facial (sucesso/falha, confiança, modelo)
   - Coordenadas GPS e distância da obra

#### Tipos de Registro

O sistema suporta os seguintes tipos de registro de ponto:

| Tipo | Descrição |
|---|---|
| `trabalhado` | Dia normal de trabalho |
| `falta` | Falta não justificada |
| `falta_justificada` | Falta com justificativa ou atestado médico |
| `feriado` | Dia de feriado (sem trabalho) |
| `feriado_trabalhado` | Trabalho em dia de feriado |
| `sabado_horas_extras` | Trabalho em sábado (computado como hora extra) |
| `domingo_horas_extras` | Trabalho em domingo (computado como hora extra) |

### 3.6.2. Visualizando Registros de Ponto

#### Controle de Ponto (Gestão)

1. No menu **Ponto**, selecione **Controle de Ponto** para acessar `/controle_ponto`.
2. Utilize os filtros disponíveis:
   - **Funcionário** — Selecione um funcionário específico ou visualize todos.
   - **Período** — Defina as datas de início e fim.
   - **Obra** — Filtre por obra específica.
   - **Tipo de registro** — Filtre por tipo (trabalhado, falta, etc.).

![Tela de controle de ponto](placeholder_controle_ponto.png)

A tabela de registros exibe:

| Coluna | Descrição |
|---|---|
| Data | Data do registro |
| Funcionário | Nome do funcionário |
| Entrada | Hora de entrada registrada |
| Saída Almoço | Hora de saída para almoço |
| Retorno Almoço | Hora de retorno do almoço |
| Saída | Hora de saída registrada |
| Horas Trabalhadas | Total de horas calculado automaticamente |
| Horas Extras | Horas extras calculadas (excedente da jornada contratual) |
| Tipo | Tipo do registro (trabalhado, falta, feriado, etc.) |
| Reconhecimento | Indica se houve validação facial ✅ ou não ❌ |
| Observações | Anotações adicionais |

#### Cálculos Automáticos

O sistema realiza os seguintes cálculos automaticamente:

1. **Horas trabalhadas** — Diferença entre entrada e saída, descontando o período de almoço. Se a jornada ultrapassa 6 horas, 1 hora de almoço é descontada automaticamente.
2. **Horas extras** — Diferença entre as horas trabalhadas e a jornada contratual definida no horário de trabalho do funcionário.
3. **Atrasos** — Diferença entre o horário contratual de entrada e o horário efetivo de entrada.
4. **DSR sobre horas extras** — Descanso semanal remunerado calculado proporcionalmente sobre as horas extras, conforme a Lei 605/49.

### 3.6.3. Editando e Justificando Registros

#### Editando um Registro

1. Na tela de controle de ponto (`/controle_ponto`), localize o registro desejado.
2. Clique no botão **Editar** (ícone de lápis) na linha correspondente.
3. Um formulário será exibido permitindo alterar:
   - Horários de entrada, saída, almoço
   - Tipo de registro
   - Obra vinculada
   - Observações
4. Clique em **Salvar** para confirmar as alterações.

#### Justificando Faltas

Para registrar uma justificativa de falta:

1. Localize o registro de falta na tela de controle de ponto.
2. Clique em **Editar**.
3. Altere o tipo de registro para **Falta Justificada**.
4. No campo **Observações**, registre o motivo da justificativa (ex.: "Atestado médico", "Licença", etc.).
5. Salve o registro.

> **Importante:** Faltas justificadas são tratadas de forma diferente no cálculo de DSR. Enquanto faltas não justificadas podem gerar perda proporcional do DSR, faltas justificadas preservam o direito ao descanso semanal remunerado.

---

## 3.7. Relatórios de Funcionários

O SIGE oferece diversas opções de relatórios relacionados aos funcionários:

### Relatório Individual (PDF)

Gere um relatório completo de um funcionário específico:

1. Acesse o perfil do funcionário em `/funcionario_perfil/<id>`.
2. Selecione o período desejado nos filtros de data.
3. Clique em **Gerar PDF** ou acesse diretamente:
   ```
   /funcionario_perfil/<id>/pdf
   ```

O relatório PDF inclui:

- Dados cadastrais completos
- KPIs do período selecionado (horas, extras, faltas, custos)
- Detalhamento financeiro (valor hora, DSR, descontos)
- Histórico completo de registros de ponto
- Informações de obras vinculadas

### Relatórios Consolidados

Na tela principal de funcionários (`/funcionarios`), os KPIs consolidados oferecem uma visão gerencial de toda a equipe:

| Relatório | Dados Incluídos |
|---|---|
| Resumo de horas | Total de horas trabalhadas e extras por funcionário |
| Controle de faltas | Faltas, faltas justificadas e taxa de absenteísmo |
| Custo de mão de obra | Custo total com salários, horas extras e encargos |
| Produtividade | Horas por obra, eficiência e alocação |

### Acessando Relatórios Gerais

1. No menu de navegação, clique em **Relatórios**.
2. Selecione a categoria **Funcionários** ou **Ponto**.
3. Configure os filtros (período, departamento, obra).
4. Clique em **Gerar Relatório**.

![Exemplo de relatório de funcionários](placeholder_relatorio_funcionarios.png)

---

## Resumo de URLs do Módulo

| Funcionalidade | URL | Método |
|---|---|---|
| Lista de funcionários | `/funcionarios` | GET |
| Criar funcionário | `/funcionarios` | POST |
| Perfil do funcionário | `/funcionario_perfil/<id>` | GET |
| PDF do perfil | `/funcionario_perfil/<id>/pdf` | GET |
| Dashboard do funcionário | `/funcionario-dashboard` | GET |
| Horário padrão | `/funcionarios/<id>/horario-padrao` | GET |
| Fotos faciais | `/ponto/funcionario/<id>/fotos-faciais` | GET/POST |
| Registro de ponto | `/ponto` | GET/POST |
| Controle de ponto | `/controle_ponto` | GET |

---

> **Próximo capítulo:** [Capítulo 4 — Gestão de Obras](04_manual_obras.md)
