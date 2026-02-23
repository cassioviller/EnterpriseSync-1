# Capítulo 3 — Gestão de Funcionários

## 3.1. Introdução

O módulo de **Gestão de Funcionários** é onde você cadastra, acompanha e gerencia toda a equipe da sua empresa. Aqui você pode:

- Cadastrar novos funcionários com todas as informações necessárias
- Consultar e editar dados de qualquer funcionário
- Registrar fotos para o reconhecimento facial no ponto eletrônico
- Acompanhar horas trabalhadas, faltas e horas extras
- Registrar e controlar o ponto eletrônico
- Gerar relatórios e exportar informações em PDF

Este capítulo vai guiar você por cada uma dessas funcionalidades, passo a passo.

> **Quem pode usar:** Para acessar este módulo, você precisa ter permissão de **Administrador** ou **Gestor de Equipes**. Funcionários com acesso básico podem visualizar apenas o próprio painel de informações.

---

## 3.2. Tela Principal de Funcionários

### Como acessar

1. No menu lateral do sistema, clique em **Funcionários**.
2. A tela principal será exibida com todos os funcionários cadastrados.

![Tela principal de funcionários](placeholder_tela_funcionarios.png)

### O que você vai encontrar nessa tela

A tela principal de funcionários é organizada em áreas que facilitam a visualização e o gerenciamento da equipe. Veja cada uma delas:

#### Indicadores no topo da página

No topo da tela, você encontra um resumo rápido com os principais números da equipe no período selecionado:

- **Total de Funcionários** — Quantos funcionários ativos estão cadastrados.
- **Horas Trabalhadas** — Soma de todas as horas trabalhadas pela equipe no período.
- **Horas Extras** — Total de horas extras acumuladas no período.
- **Faltas** — Quantidade de faltas registradas (tanto justificadas quanto não justificadas).
- **Custo Total** — Estimativa do custo com a mão de obra no período.
- **Taxa de Absenteísmo** — Percentual de ausências em relação aos dias úteis.

> **Dica:** Esses indicadores ajudam você a ter uma visão geral rápida da situação da equipe, sem precisar abrir o perfil de cada funcionário.

#### Como filtrar por período

Você pode ajustar o período dos indicadores e dados exibidos na tela:

1. Localize os campos de **Data Início** e **Data Fim** no topo da página.
2. Clique no campo **Data Início** e selecione a data desejada (por padrão, é o primeiro dia do mês atual).
3. Clique no campo **Data Fim** e selecione a data final (por padrão, é o dia de hoje).
4. Clique no botão **Filtrar** para atualizar os dados.

Os indicadores e as informações dos funcionários serão recalculados de acordo com o período escolhido.

#### Cards dos funcionários

Cada funcionário é exibido em um **card** (cartão visual) que mostra:

- **Foto do funcionário** — Se houver uma foto cadastrada, ela aparece no card. Caso contrário, será exibido um ícone com as iniciais do nome.
- **Nome completo** do funcionário.
- **Cargo ou função** que ele exerce.
- **Caixa de seleção** — Permite marcar vários funcionários para realizar ações em grupo.

![Card de funcionário com foto e informações](placeholder_card_funcionario.png)

---

## 3.3. Pesquisando e Filtrando Funcionários

A tela de funcionários oferece ferramentas de busca para facilitar a localização de qualquer pessoa da equipe:

### Busca por nome ou CPF

1. Localize o **campo de busca** na parte superior da lista de funcionários.
2. Digite o **nome**, o **CPF** ou o **código** do funcionário que você procura.
3. Os resultados serão filtrados automaticamente enquanto você digita.

> **Exemplo:** Se você digitar "João", todos os funcionários que tenham "João" no nome serão exibidos.

### Filtros disponíveis

Além da busca por texto, você pode usar os filtros para refinar a lista:

- **Departamento** — Selecione um departamento específico para ver apenas os funcionários daquele setor.
- **Função/Cargo** — Filtre por cargo ou função exercida.
- **Status** — Escolha entre ver funcionários **Ativos**, **Inativos** ou **Todos**.

Para usar os filtros:

1. Clique no filtro desejado (por exemplo, **Departamento**).
2. Selecione a opção na lista que aparece.
3. A lista de funcionários será atualizada automaticamente.

> **Dica:** Você pode combinar os filtros. Por exemplo, filtrar por departamento "Obras" e status "Ativo" para ver apenas quem está trabalhando atualmente no setor de obras.

### Operações em grupo

Depois de marcar vários funcionários usando as caixas de seleção nos cards, você pode realizar ações em grupo, como:

- Lançar registros de ponto para vários funcionários ao mesmo tempo.
- Alocar funcionários em uma obra.
- Exportar dados dos funcionários selecionados.

---

## 3.4. Cadastrando um Novo Funcionário

Para adicionar um novo funcionário ao sistema, siga o passo a passo abaixo:

### Passo a passo

1. Na tela de funcionários, clique no botão **+ Novo Funcionário**.
2. Um formulário será aberto na tela.
3. Preencha os campos conforme explicado nas seções a seguir.
4. Após preencher todos os dados, clique no botão **Salvar**.

![Formulário de cadastro de novo funcionário](placeholder_modal_novo_funcionario.png)

### 3.4.1. Dados Pessoais

Preencha as informações pessoais do funcionário:

**Nome** *(obrigatório)*
- Digite o nome completo do funcionário.
- Exemplo: "João Carlos da Silva".

**CPF** *(obrigatório)*
- Digite os 11 números do CPF do funcionário.
- O sistema formata automaticamente (000.000.000-00).
- Cada CPF deve ser único — não é possível cadastrar dois funcionários com o mesmo CPF.

**RG**
- Digite o número do documento de identidade (RG) do funcionário.
- Este campo é opcional.

**Data de Nascimento**
- Selecione a data de nascimento do funcionário no calendário.
- Formato: dia/mês/ano (DD/MM/AAAA).

**Endereço**
- Digite o endereço completo do funcionário: rua, número, bairro, cidade, estado e CEP.
- Exemplo: "Rua das Flores, 123 - Centro - São Paulo/SP - CEP 01234-567".

**Telefone**
- Digite o número de telefone com DDD.
- Exemplo: (11) 99999-0000.

**E-mail**
- Digite o endereço de e-mail do funcionário.
- Este campo é opcional, mas útil para comunicações.

**Foto**
- Clique em **Escolher arquivo** para enviar uma foto do funcionário.
- Formatos aceitos: JPG ou PNG.
- Essa foto será exibida no card do funcionário e no perfil dele.

> **Importante sobre o CPF:** Se você digitar um CPF que já está cadastrado no sistema, uma mensagem de erro será exibida. Verifique se o funcionário já não está registrado antes de criar um novo cadastro.

### 3.4.2. Dados do Contrato de Trabalho

Preencha as informações sobre o vínculo de trabalho:

**Código do funcionário**
- Digite um código interno para identificar o funcionário (exemplo: VV001).
- Se você deixar este campo em branco, o sistema vai gerar um código automaticamente (VV001, VV002, VV003...).

**Data de Admissão** *(obrigatório)*
- Selecione a data em que o funcionário começou a trabalhar na empresa.
- Por padrão, o sistema preenche com a data de hoje.

**Salário**
- Digite o valor do salário mensal bruto do funcionário (em reais).
- Exemplo: 2.500,00.

**Departamento**
- Selecione o departamento ao qual o funcionário pertence.
- Exemplos: Administrativo, Obras, Manutenção, etc.

**Função/Cargo**
- Selecione a função ou cargo que o funcionário vai exercer.
- Exemplos: Pedreiro, Eletricista, Engenheiro, Auxiliar Administrativo, etc.

**Horário de Trabalho**
- Selecione o modelo de horário de trabalho do funcionário.
- Cada modelo define os horários de entrada, saída, pausas e dias da semana em que o funcionário trabalha.
- Se o funcionário tem uma jornada diferente, você poderá ajustar o horário individualmente depois (veja a seção 3.5.3).

> **Sobre o código automático:** Quando você não preenche o campo de código, o sistema cria automaticamente um código sequencial (VV001, VV002...). Isso é útil para manter a organização sem precisar se preocupar com a numeração.

> **Sobre os horários de trabalho:** Os modelos de horário de trabalho são configurados pelo administrador na área de **Configurações > Horários**. Eles permitem definir horários diferentes para cada dia da semana — por exemplo, sexta-feira com expediente reduzido ou sábado com meio período.

---

## 3.5. Perfil do Funcionário

### 3.5.1. Como acessar o perfil

Para ver todas as informações de um funcionário:

1. Na tela principal de funcionários, localize o funcionário desejado.
2. Clique no **card** (cartão) do funcionário ou diretamente no **nome** dele.
3. A página de perfil será aberta com todas as informações detalhadas.

![Perfil completo do funcionário](placeholder_perfil_funcionario.png)

### 3.5.2. O que você encontra no perfil

O perfil do funcionário está dividido em seções para facilitar a consulta:

#### Informações pessoais e contratuais

Todos os dados cadastrados do funcionário ficam visíveis nessa seção:

- Nome completo, CPF e RG
- Data de nascimento e endereço
- Telefone e e-mail
- Foto do funcionário (quando cadastrada)
- Departamento e função/cargo
- Data de admissão e salário
- Status atual (ativo ou inativo)

#### Indicadores de desempenho

O perfil exibe automaticamente os indicadores do funcionário para o período selecionado:

- **Horas Trabalhadas** — Total de horas que o funcionário trabalhou no período.
- **Horas Extras** — Total de horas extras realizadas.
- **Faltas** — Quantidade de faltas sem justificativa.
- **Faltas Justificadas** — Quantidade de faltas com atestado ou justificativa.
- **Atrasos** — Total de horas de atraso acumuladas.
- **Dias Trabalhados** — Quantidade de dias em que houve registro de ponto.
- **Taxa de Absenteísmo** — Percentual de faltas em relação aos dias úteis do período.
- **Valor da Hora** — Quanto vale cada hora de trabalho do funcionário, calculado com base no salário.
- **Valor das Horas Extras** — Custo total das horas extras realizadas.
- **DSR sobre Horas Extras** — Valor do Descanso Semanal Remunerado calculado sobre as horas extras.

> **O que é DSR?** O Descanso Semanal Remunerado (DSR) é um valor adicional pago sobre as horas extras, garantido por lei. O sistema calcula esse valor automaticamente para você.

#### Histórico de ponto

Uma tabela completa mostra todos os registros de ponto do funcionário no período, incluindo:

- Data do registro
- Horário de entrada
- Horário de saída para almoço
- Horário de retorno do almoço
- Horário de saída
- Total de horas trabalhadas no dia
- Horas extras (se houver)
- Tipo do registro (dia trabalhado, falta, feriado, etc.)
- Observações

#### Obras vinculadas

Lista todas as obras em que o funcionário está ou já esteve alocado, mostrando:

- Nome da obra
- Período em que trabalhou na obra
- Local de trabalho (campo ou escritório)

### 3.5.3. Editando as informações do funcionário

Para alterar qualquer dado cadastral do funcionário:

1. No perfil do funcionário, clique no botão **Editar**.
2. Os campos ficarão disponíveis para edição.
3. Faça as alterações necessárias.
4. Clique em **Salvar** para confirmar.

Você pode editar dados pessoais (nome, endereço, telefone) e dados contratuais (salário, departamento, função, horário de trabalho).

#### Configurando um horário personalizado

Se o funcionário tem uma jornada diferente do padrão do departamento:

1. No perfil do funcionário, localize a opção **Horário Personalizado** ou **Horário Padrão**.
2. Clique para abrir a configuração de horário individual.
3. Defina os horários de entrada, saída e intervalos para cada dia da semana.
4. Clique em **Salvar**.

> **Quando usar o horário personalizado?** Use quando um funcionário específico trabalha em um horário diferente dos demais colegas do mesmo departamento. Por exemplo, se o departamento de obras tem horário das 7h às 17h, mas um engenheiro trabalha das 8h às 18h.

---

## 3.6. Cadastro de Fotos para Reconhecimento Facial

### 3.6.1. Por que cadastrar fotos faciais?

O sistema utiliza reconhecimento facial para garantir que o ponto eletrônico seja registrado pela pessoa certa. Quando o funcionário bate o ponto, o sistema tira uma foto e compara com as fotos cadastradas para confirmar a identidade.

**Por que cadastrar mais de uma foto?**

Cadastrar várias fotos melhora muito a precisão do reconhecimento, porque o sistema consegue identificar o funcionário em diferentes situações do dia a dia:

- Uma foto com óculos e outra sem óculos
- Uma foto em ambiente claro e outra em ambiente com menos luz
- Uma foto de frente e outra levemente de lado

> **Resultado:** Quanto mais fotos cadastradas em condições variadas, mais rápido e preciso será o reconhecimento na hora de bater o ponto.

### 3.6.2. Como cadastrar fotos faciais

#### Acessando a tela de fotos

1. Acesse o perfil do funcionário (clicando no card dele na tela de funcionários).
2. No perfil, clique na opção **Fotos Faciais** ou **Gerenciar Fotos**.

![Tela de gerenciamento de fotos faciais](placeholder_fotos_faciais.png)

#### Adicionando uma nova foto

1. Na tela de fotos faciais, clique no botão **Adicionar Foto**.
2. A câmera do seu dispositivo (computador, tablet ou celular) será ativada.
   - Se preferir, você também pode selecionar uma foto já existente no dispositivo.
3. Posicione o rosto do funcionário no centro da tela, de forma que o rosto fique bem visível.
4. Clique em **Capturar** (ou selecione o arquivo de imagem).
5. No campo **Descrição**, escreva uma identificação para a foto. Exemplos:
   - "Foto frontal sem óculos"
   - "Com óculos de grau"
   - "Com capacete de obra"
   - "Perfil lado esquerdo"
6. Clique em **Salvar** para concluir.

Repita esse processo para adicionar mais fotos do mesmo funcionário.

### 3.6.3. Dicas para fotos de qualidade

Siga estas orientações para garantir que o reconhecimento facial funcione da melhor forma:

#### Quantidade de fotos

- Cadastre **pelo menos 3 fotos** de cada funcionário.
- Quanto mais fotos, melhor a precisão.

#### Variações recomendadas

| Situação | O que cadastrar |
|---|---|
| Funcionário usa óculos | Uma foto **com** óculos e outra **sem** óculos |
| Funcionário tem barba | Atualize as fotos se houver mudança significativa (raspou a barba, deixou crescer) |
| Funcionário trabalha em obra | Uma foto **com** capacete/EPI e outra **sem** |
| Funcionário trabalha em ambientes variados | Fotos em diferentes condições de luz (escritório, ar livre) |

#### Cuidados com a iluminação

- Tire as fotos em um local **bem iluminado**, de preferência com luz natural.
- **Evite** fotos com flash direto no rosto — a luz forte pode atrapalhar o reconhecimento.
- **Evite** tirar fotos contra a luz (contraluz) — o rosto ficará escuro e o sistema pode não reconhecer.

#### Posicionamento correto

- O rosto deve estar **centralizado** na foto.
- O rosto deve ocupar a **maior parte** da imagem — não tire fotos de corpo inteiro.
- **Não cubra o rosto** com as mãos, máscara, boné ou outros objetos.

#### Expressão facial

- Prefira uma expressão **natural**, com o rosto relaxado.
- Evite caretas ou expressões muito exageradas.

> **O reconhecimento não está funcionando bem?** Se o sistema tem dificuldade em reconhecer um funcionário, tente cadastrar novas fotos em condições parecidas com o ambiente onde ele bate o ponto (mesma iluminação, com ou sem EPI, etc.).

---

## 3.7. Ponto Eletrônico — Registro de Ponto

O ponto eletrônico permite registrar os horários de entrada e saída dos funcionários. O sistema pode usar reconhecimento facial e localização para validar cada registro.

### 3.7.1. Como registrar o ponto

#### Passo a passo

1. No menu do sistema, clique em **Ponto**.
2. Selecione a opção **Registrar Ponto**.

![Tela de registro de ponto](placeholder_registro_ponto.png)

3. **Selecione o funcionário:**
   - Se você é um gestor, selecione o nome do funcionário na lista.
   - Se o funcionário está logado no sistema, o nome dele já estará preenchido.

4. **Tire a foto para reconhecimento facial:**
   - A câmera do dispositivo será ativada automaticamente.
   - Posicione o rosto do funcionário de forma centralizada.
   - Clique em **Capturar**.

5. **Aguarde a validação:**
   - O sistema vai comparar a foto tirada com as fotos cadastradas do funcionário.
   - Se a foto corresponder, aparecerá uma mensagem de **confirmação** ✅.
   - Se a foto não corresponder, aparecerá uma mensagem de **erro** ❌. Nesse caso, tente novamente com melhor iluminação ou posicionamento.

6. **Validação de localização (quando aplicável):**
   - Se a obra possui localização cadastrada, o sistema verifica se o funcionário está próximo do local de trabalho.
   - Se estiver dentro do perímetro, a localização será validada ✅.
   - Se estiver fora do perímetro, um alerta será exibido ⚠️.

7. **Ponto registrado!**
   - Após as validações, o ponto é salvo automaticamente com o horário atual.

> **Dica:** O registro de ponto pode ser feito pelo celular, tablet ou computador. Basta acessar o sistema pelo navegador do dispositivo.

### 3.7.2. Tipos de registro de ponto

O sistema reconhece diferentes tipos de dias no registro de ponto:

| Tipo | O que significa |
|---|---|
| Dia trabalhado | Dia normal de trabalho |
| Falta | O funcionário não compareceu e não apresentou justificativa |
| Falta justificada | O funcionário não compareceu, mas apresentou justificativa (atestado médico, licença, etc.) |
| Feriado | Dia de feriado — sem trabalho |
| Feriado trabalhado | O funcionário trabalhou em um dia de feriado |
| Sábado (hora extra) | Trabalho realizado no sábado, contado como hora extra |
| Domingo (hora extra) | Trabalho realizado no domingo, contado como hora extra |

### 3.7.3. O que o sistema calcula automaticamente

Você não precisa fazer contas! O sistema calcula automaticamente:

- **Horas trabalhadas** — Com base nos horários de entrada e saída, descontando o intervalo de almoço.
- **Horas extras** — A diferença entre as horas trabalhadas e a jornada prevista no contrato.
- **Atrasos** — Se o funcionário chegou depois do horário de entrada previsto, o atraso é registrado.
- **DSR sobre horas extras** — O Descanso Semanal Remunerado sobre as horas extras é calculado conforme a legislação.

> **Sobre o almoço:** Se o funcionário trabalha mais de 6 horas, o sistema desconta automaticamente 1 hora de almoço do total de horas trabalhadas.

---

## 3.8. Consultando os Registros de Ponto

### Como acessar o controle de ponto

1. No menu do sistema, clique em **Ponto**.
2. Selecione a opção **Controle de Ponto**.

![Tela de controle de ponto](placeholder_controle_ponto.png)

### Usando os filtros

A tela de controle de ponto permite filtrar os registros de diversas formas:

1. **Por funcionário** — Selecione um funcionário específico ou escolha "Todos" para ver a equipe toda.
2. **Por período** — Preencha os campos de **Data Início** e **Data Fim** para definir o período desejado.
3. **Por obra** — Selecione uma obra específica para ver apenas os registros daquela obra.
4. **Por tipo de registro** — Filtre por dia trabalhado, falta, feriado, etc.

Após selecionar os filtros, clique em **Filtrar** para atualizar a tabela.

### Entendendo a tabela de registros

A tabela exibe as seguintes informações para cada registro:

| Coluna | O que mostra |
|---|---|
| Data | A data do registro |
| Funcionário | O nome do funcionário |
| Entrada | Horário em que chegou ao trabalho |
| Saída Almoço | Horário em que saiu para almoçar |
| Retorno Almoço | Horário em que voltou do almoço |
| Saída | Horário em que encerrou o expediente |
| Horas Trabalhadas | Total de horas no dia (calculado automaticamente) |
| Horas Extras | Horas extras no dia (se houver) |
| Tipo | Tipo do registro (trabalhado, falta, feriado, etc.) |
| Reconhecimento | Indica se o rosto foi verificado ✅ ou não ❌ |
| Observações | Notas ou comentários sobre o registro |

### Editando um registro de ponto

Se for necessário corrigir um registro (por exemplo, o funcionário esqueceu de bater o ponto de saída):

1. Na tela de controle de ponto, localize o registro que precisa ser corrigido.
2. Clique no botão **Editar** (ícone de lápis) ao lado do registro.
3. O formulário de edição será aberto. Você pode alterar:
   - Horários de entrada, saída e almoço
   - Tipo do registro
   - Obra vinculada
   - Observações
4. Faça as correções necessárias.
5. Clique em **Salvar** para confirmar.

### Justificando uma falta

Se um funcionário faltou mas apresentou justificativa (atestado médico, por exemplo):

1. Na tela de controle de ponto, localize o registro de falta do funcionário.
2. Clique no botão **Editar** (ícone de lápis).
3. No campo **Tipo**, altere de "Falta" para **Falta Justificada**.
4. No campo **Observações**, descreva o motivo da justificativa.
   - Exemplo: "Atestado médico — consulta odontológica".
   - Exemplo: "Licença para acompanhar filho ao médico".
5. Clique em **Salvar**.

> **Por que justificar faltas?** Faltas sem justificativa podem afetar o cálculo do Descanso Semanal Remunerado (DSR) do funcionário. Quando a falta é justificada, o funcionário mantém o direito ao DSR integral.

---

## 3.9. Relatórios de Funcionários

### 3.9.1. Relatório individual em PDF

Para gerar um relatório completo de um funcionário específico:

1. Acesse o perfil do funcionário (clicando no card dele na tela de funcionários).
2. No perfil, ajuste o período desejado nos campos de **Data Início** e **Data Fim**.
3. Clique no botão **Gerar PDF** ou **Exportar PDF**.
4. O sistema vai gerar o documento e o download começará automaticamente.

#### O que o PDF inclui:

- **Dados cadastrais** — Nome, CPF, departamento, função, data de admissão, etc.
- **Indicadores do período** — Horas trabalhadas, horas extras, faltas, atrasos, custos.
- **Detalhamento financeiro** — Valor da hora, valor das horas extras, DSR, descontos.
- **Histórico de ponto** — Tabela com todos os registros de ponto do período.
- **Obras vinculadas** — Lista de obras em que o funcionário trabalhou.

> **Dica:** Esse relatório é muito útil para fechar a folha de pagamento, acompanhar produtividade individual ou apresentar informações para auditorias.

### 3.9.2. Indicadores consolidados da equipe

Na tela principal de funcionários, os indicadores no topo da página oferecem uma visão geral de toda a equipe:

| Indicador | O que mostra |
|---|---|
| Resumo de horas | Total de horas trabalhadas e horas extras por funcionário |
| Controle de faltas | Faltas, faltas justificadas e taxa de absenteísmo da equipe |
| Custo de mão de obra | Custo total com salários, horas extras e encargos |
| Produtividade | Horas trabalhadas por obra e eficiência da alocação |

### 3.9.3. Relatórios gerais

Para acessar relatórios mais detalhados:

1. No menu do sistema, clique em **Relatórios**.
2. Selecione a categoria **Funcionários** ou **Ponto**.
3. Configure os filtros:
   - **Período** — Selecione as datas de início e fim.
   - **Departamento** — Filtre por departamento específico (ou selecione "Todos").
   - **Obra** — Filtre por obra específica (ou selecione "Todas").
4. Clique em **Gerar Relatório**.
5. O relatório será exibido na tela e poderá ser exportado em PDF.

![Exemplo de relatório de funcionários](placeholder_relatorio_funcionarios.png)

---

## 3.10. Perguntas Frequentes

**Posso cadastrar dois funcionários com o mesmo CPF?**
Não. O CPF é único para cada funcionário. Se você tentar cadastrar um CPF que já existe, o sistema não vai permitir e exibirá uma mensagem de erro.

**O que faço se o reconhecimento facial não está funcionando para um funcionário?**
Cadastre novas fotos faciais em condições parecidas com o ambiente onde o ponto é batido. Veja as dicas na seção 3.6.3 deste manual.

**Posso corrigir um ponto registrado com horário errado?**
Sim. Acesse o controle de ponto, localize o registro, clique em Editar e corrija os horários. Veja o passo a passo na seção 3.8.

**Como mudo o horário de trabalho de um funcionário específico?**
No perfil do funcionário, use a opção de horário personalizado para definir uma jornada diferente da padrão do departamento. Veja a seção 3.5.3.

**Preciso cadastrar fotos faciais para todos os funcionários?**
Recomendamos que sim. As fotos faciais garantem que o registro de ponto seja feito pela pessoa certa, evitando fraudes. Sem fotos cadastradas, o ponto poderá ser registrado sem verificação de identidade.

**Quantas fotos devo cadastrar por funcionário?**
Recomendamos pelo menos 3 fotos com variações (com óculos, sem óculos, diferentes iluminações). Quanto mais fotos, melhor a precisão do reconhecimento.

---

> **Próximo capítulo:** [Capítulo 4 — Gestão de Obras](04_manual_obras.md)
