# Plano de conversão do orçamento Baia REV10 para Insumos, Serviços, Composições e Proposta

## 1. Objetivo

Converter o arquivo **Orçamento - Baia - REV10.xlsx** em uma estrutura compatível com o sistema de orçamento, separando corretamente:

1. **Insumos**: materiais, mão de obra, equipamentos e custos indiretos/outros.
2. **Preços dos insumos**: valor vigente por unidade técnica ou comercial.
3. **Serviços**: itens vendáveis/orçáveis, equivalentes aos itens da proposta comercial.
4. **Composição dos serviços**: relação serviço × insumo × coeficiente.
5. **Orçamento/Proposta**: itens da proposta, quantidades, unidades, valores e textos comerciais.
6. **Validação**: comparação entre o valor original da planilha e o valor recalculado pelo modelo de insumos e coeficientes.

O objetivo final não é apenas copiar os valores da proposta, mas transformar o orçamento em uma base reutilizável, permitindo que o sistema recalcule custos por quantidade, produtividade, preço de insumo, mão de obra e margem.

---

## 2. Contexto do aplicativo

Pelo funcionamento observado no sistema, a lógica correta é:

### 2.1. Insumo

O **insumo** é tudo aquilo que entra na execução de um serviço.

Exemplos:

- Aço LSF galvanizado, unidade kg.
- Concreto usinado, unidade m³.
- Parafusos/fixadores, unidade vb, un. ou kg.
- Encarregado, unidade h.
- Montador líder, unidade h.
- Montador, unidade h.
- Ajudante, unidade h.
- Pintor, unidade h.
- Pedreiro, unidade h.
- Hospedagem, unidade diária/mês/vb.
- Frete/viagem, unidade viagem/km/vb.
- Visita técnica, unidade diária/vb.

Campos relevantes do insumo no sistema:

- Nome.
- Tipo: Material, Mão de Obra, Equipamento ou Outros.
- Unidade técnica: h, kg, m², m³, un., vb etc.
- Preço vigente.
- Fator comercial / embalagem.
- Unidade comercial.
- Fracionável ou não.
- Tipo de medição.
- Descrição.

### 2.2. Serviço

O **serviço** é o item que será orçado/vendido.

Exemplos:

- Montagem de estrutura em Aço LSF.
- Pintura do aço estrutural.
- Fechamento interno em placa cimentícia.
- Fechamento externo em régua de pinus.
- Instalação de telha shingle.
- Execução de corredores de concreto.
- Execução de ponto hidráulico por baia.
- Revestimento em pedra moledo.

O serviço tem uma unidade principal de venda, como:

- kg.
- m².
- un.
- vb.

### 2.3. Composição do serviço

A composição define quais insumos entram no serviço e em qual quantidade por unidade do serviço.

A regra central é:

```text
Custo unitário do serviço = soma de todos os insumos
Custo de cada insumo = coeficiente × preço unitário vigente do insumo
```

Exemplo:

```text
Serviço: Montagem de Aço LSF
Unidade do serviço: kg
Insumo: Montador
Unidade do insumo: h
Coeficiente: 0,022
Preço do insumo: R$ 26,14/h
Custo do montador por kg = 0,022 × 26,14
```

### 2.4. Orçamento/proposta

No orçamento, o usuário escolhe o serviço e informa a quantidade.

Exemplo:

```text
Serviço: Montagem de Aço LSF
Quantidade: 1.000 kg
Coeficiente de mão de obra: 0,022 h/kg
Horas necessárias: 1.000 × 0,022 = 22 h
```

Depois o sistema multiplica pelas linhas de insumo e calcula o custo total.

### 2.5. Snapshot/editabilidade

O comportamento ideal do sistema é:

- O catálogo guarda o serviço padrão.
- Ao lançar um serviço no orçamento, o sistema copia a composição para o item do orçamento.
- O item do orçamento pode ser editado sem alterar o catálogo padrão.
- Orçamentos antigos não devem mudar automaticamente quando o preço de um insumo for atualizado, a menos que o usuário solicite “atualizar pelo catálogo”.

---

## 3. Regra de negócio principal: coeficiente

O **coeficiente** significa quanto de um insumo é necessário para executar **1 unidade do serviço**.

### 3.1. Para mão de obra

Quando a unidade do serviço é kg, m² ou un., e a unidade do insumo é hora, o coeficiente representa:

```text
horas de trabalho por unidade do serviço
```

Exemplo:

```text
0,022 h/kg = para cada 1 kg executado, são necessárias 0,022 horas daquele trabalhador/equipe.
```

### 3.2. Equipes com pessoas repetidas

Se a equipe é:

```text
1 Encarregado
1 Montador líder
2 Montadores
2 Ajudantes
```

Existem duas formas possíveis de cadastrar:

#### Forma A — repetir linhas, mais visual

Como foi testado que o sistema aceita repetir o mesmo insumo, esta é a forma preferida operacionalmente:

```text
Encarregado     0,022
Montador líder  0,022
Montador        0,022
Montador        0,022
Ajudante        0,022
Ajudante        0,022
```

Vantagem: ao olhar a composição, fica claro que existem 2 montadores e 2 ajudantes.

#### Forma B — consolidar coeficiente

Alternativa, caso algum importador ou tela não aceite repetição:

```text
Encarregado     0,022
Montador líder  0,022
Montador        0,044
Ajudante        0,044
```

As duas formas chegam ao mesmo custo, mas a Forma A é mais fácil de auditar visualmente.

### 3.3. Para material

A regra é:

```text
coeficiente = quantidade total do material / quantidade total do serviço
```

Exemplo:

```text
Serviço: Corredor de concreto
Quantidade do serviço: 500,4 m²
Espessura: 0,20 m
Concreto total: 500,4 × 0,20 = 100,08 m³
Coeficiente do concreto: 100,08 / 500,4 = 0,20 m³/m²
```

### 3.4. Para verba fechada

Quando o orçamento tem apenas valor global e não existe decomposição confiável:

```text
Unidade do serviço: vb
Quantidade: 1
Coeficiente do insumo: 1
Preço do insumo: valor total da verba
```

Isso deve ser marcado como **[verba sem composição detalhada]** para revisão futura.

### 3.5. Para custos indiretos da etapa

Custos como viagem, hospedagem, pedágio e visita técnica podem seguir duas regras:

#### Opção 1 — lançar como insumo “Outros” dentro do serviço

Exemplo:

```text
Insumo: Viagem equipe montagem aço
Tipo: Outros
Unidade: viagem
Coeficiente: número de viagens por serviço ou valor rateado
```

#### Opção 2 — ratear no custo unitário

Exemplo:

```text
Custo de viagem total / quantidade do serviço = custo indireto por unidade
```

Minha recomendação: manter como insumos separados do tipo **Outros**, para o orçamento ficar auditável.

---

## 4. Leitura inicial do arquivo Excel

O arquivo possui as seguintes abas:

1. `Proposta Comercial `
2. `Memorial de calculo`
3. `RESUMO CUSTOS `
4. `Fundação `
5. `Aço `
6. `Cobertura`
7. `Plaqueamento Interno `
8. `Plaqueamento Externo`
9. `Revestimento `
10. `Muro`
11. `Instalação Portas`
12. `Pintura `
13. `Instalações`
14. `PROJETO`
15. `TOPOGRAFIA`

### 4.1. Aba `Proposta Comercial`

É a aba final, usada como proposta para o cliente.

Estrutura observada:

| Coluna | Função |
|---|---|
| B | Item |
| C | Descrição |
| D | Unidade |
| E | Quantidade |
| F | Custo unitário de material |
| G | Custo unitário de mão de obra |
| H | Total material |
| I | Total mão de obra |

Os itens principais vão de **1.1 a 1.17**.

---

## 5. Itens da proposta e interpretação inicial

> Observação: esta é uma interpretação inicial. O Claude Code deve confirmar no Excel, avaliando fórmulas, valores calculados e dependências entre abas.

### 5.1. Item 1.1 — Estrutura em Aço Galvanizado LSF

Fórmulas observadas:

```text
Quantidade: 1 vb
Material: ((21900 * 13,5) * 1,07) + 15000
Mão de obra: 7 * 21900
```

Interpretação:

- 21.900 kg de aço LSF.
- R$ 13,50/kg.
- 7% de perda/sobra.
- R$ 15.000 de fixadores/acessórios.
- Mão de obra calculada a R$ 7,00/kg.

Possível composição:

| Insumo | Tipo | Unidade | Coeficiente |
|---|---|---:|---:|
| Aço LSF galvanizado Z275 | Material | kg | 21.900 |
| Perda/sobra aço LSF | Material/Outros | % ou vb | 7% ou embutido |
| Fixadores/acessórios LSF | Material | vb | 1 |
| Equipe montagem LSF | Mão de Obra | h | calcular |

Para mão de obra:

```text
coeficiente h/kg = 7 / custo_hora_da_equipe
```

Se usar a equipe confirmada pelo usuário:

```text
Custo hora da equipe = R$ 161,37/h
Coeficiente equipe = 7 / 161,37 = 0,04338 h/kg
```

Se usar o coeficiente já discutido de 0,022 h/kg, o custo por kg seria:

```text
0,022 × 161,37 = R$ 3,55/kg
```

Isso não bate com R$ 7/kg. Portanto, há uma decisão de negócio a validar:

- Ou a proposta está usando outra equipe/custo-hora;
- Ou o R$ 7/kg inclui encargos, gestão, folga, produtividade menor ou margem operacional;
- Ou o coeficiente 0,022 foi de outro cenário e não desse item 1.1;
- Ou deve-se cadastrar um insumo “M.O. montagem LSF orçada” com preço direto de R$ 7/kg para preservar o orçamento original.

### 5.2. Item 1.2 — Pintura do aço estrutural LSF do telhado

```text
Quantidade: 1.173 m²
Material: 0
Mão de obra: 35 R$/m²
```

Interpretação:

- Material provavelmente fornecido pelo cliente ou não considerado.
- Serviço pode ser cadastrado com unidade m².
- Mão de obra pode entrar como insumo “Pintor pintura aço” em h/m², se houver custo-hora e produtividade; caso contrário, como verba unitária de R$ 35/m².

### 5.3. Item 1.3 — Pintura e fornecimento de Stain em portão de Pinus

```text
Quantidade: 161 m²
Material: R$ 800
Mão de obra: R$ 35/m²
```

Ponto a validar:

- A fórmula do material parece aplicar R$ 800 uma única vez, não por m², porque o total material usa `ROUND(F12,2)` em vez de `F12 × E12`.
- Isso precisa ser confirmado: o material é verba global de R$ 800, enquanto M.O. é por m².

### 5.4. Item 1.4 — Execução de Portão em Pinus

```text
Quantidade: 24 × 2 = 48 un.
Material: R$ 125/un.
Mão de obra: R$ 350/un.
```

Possível composição:

- Material/fixadores portão: 1 un por portão.
- Mão de obra montagem portão: 1 un por portão ou h/un, se houver produtividade.

### 5.5. Item 1.5 — Fechamento interno em placas cimentícias

```text
Quantidade: 900 m²
Material: 0
Mão de obra: R$ 45/m²
```

Deve ser relacionado à aba `Plaqueamento Interno`.

Ponto a validar:

- Se o material é fornecido pelo cliente.
- Se o R$ 45/m² vem de custo de equipe/área ou foi definido manualmente.

### 5.6. Item 1.6 — Fechamento externo em réguas de pinus

```text
Quantidade: 660 m²
Material: 0
Mão de obra: R$ 45/m²
```

Deve ser relacionado à aba `Plaqueamento Externo`.

### 5.7. Item 1.7 — Pintura dos fechamentos internos

```text
Quantidade: igual ao item 1.5 = 900
Material: 0
Mão de obra: R$ 45/m²
```

Unidade aparece como vb, mas a quantidade usa o m² do item 1.5.

Recomendação:

- No sistema, cadastrar como serviço em m², não vb, se a quantidade for área.
- Se quiser manter igual à proposta, lançar como vb com quantidade 900 gera confusão; melhor revisar unidade.

### 5.8. Item 1.8 — Pintura em Stain das paredes externas

```text
Quantidade: 660 m²
Material: R$ 800
Mão de obra: R$ 30/m²
```

Ponto crítico:

- Material aparenta ser verba global de R$ 800, pois o total material usa `ROUND(F17,2)`, não `F17 × E17`.
- A mão de obra é por m².

### 5.9. Item 1.9 — Estruturação e verticalização de pilares roliços

```text
Quantidade: 44 - 12 = 32 un.
Material: 0
Mão de obra: (50000/2)/44 = R$ 568,18 por pilar
```

Interpretação:

- Foi usada metade de R$ 50.000 dividida por 44 pilares.
- A quantidade final considerada é 32 pilares.
- Há divergência lógica potencial: o custo unitário foi calculado em cima de 44, mas a quantidade vendida é 32.

Validar se isso é intencional.

### 5.10. Item 1.10 — Corredores em concreto

```text
Quantidade: 1 vb
Material: (500,4 × 0,2) × 550 + 1500
Mão de obra: (500,4 × 25) + 2500
```

Interpretação:

- Área: 500,4 m².
- Espessura: 0,20 m.
- Volume concreto: 100,08 m³.
- Preço concreto: R$ 550/m³.
- Extra de material/ferramenta: R$ 1.500.
- Mão de obra: R$ 25/m² + R$ 2.500 fixo.

Recomendação:

Cadastrar em composição:

- Concreto: coeficiente 100,08 m³ por vb, ou 0,20 m³/m² se serviço for em m².
- Ferramenta/miscelânea concreto: 1 vb.
- Equipe concretagem: 500,4 × coeficiente h/m², ou verba se não houver produtividade.
- Taxa fixa concretagem: 1 vb.

### 5.11. Item 1.11 — Revestimento em pedra moledo nos pilares

```text
Quantidade: 80/2 = 40 m²
Material: 0
Mão de obra: R$ 230/m²
```

Recomendação:

- Serviço em m².
- Material fornecido pelo cliente ou não incluso.
- M.O. como pedreiro/revestidor em h/m², se houver produtividade, ou verba R$/m².

### 5.12. Item 1.12 — Instalação de pontos de luz

```text
Quantidade: 1 un. / vb
Material: (12 × 400) + 1500 + 610
Mão de obra: R$ 6.500
```

Interpretação:

- 12 pontos/baias × R$ 400.
- R$ 1.500 de adicional.
- R$ 610 de quadro/outros.
- M.O. global.

Ponto a revisar:

- A descrição fala em um ponto de luz por baia e um ponto por pilar; a fórmula usa 12, mas outras partes do orçamento indicam 24 baias e 44 pilares.
- Precisa validar se são 12 pontos ou se faltou parte da quantidade.

### 5.13. Item 1.13 — Instalação de telha Shingle

```text
Quantidade: 1.173 m²
Material: 0
Mão de obra: R$ 85/m²
```

Relacionar com aba `Cobertura`.

### 5.14. Item 1.14 — Execução de cercado das baias

```text
Quantidade: 24 un.
Material: R$ 100/un.
Mão de obra: R$ 450/un.
```

Material parece representar fixadores e acessórios, pois madeira/pilares são fornecidos pelo cliente.

### 5.15. Item 1.15 — Pintura em Stain do cercado

```text
Quantidade: 24 un.
Material: R$ 800
Mão de obra: R$ 400/un.
```

Ponto crítico:

- Material parece verba global de R$ 800, porque o total material usa `ROUND(F24,2)`, não `F24 × E24`.
- Mão de obra é por unidade.

### 5.16. Item 1.16 — Ponto hidráulico por baia

```text
Quantidade: 24 un.
Material: 667 × 1,3 = R$ 867,10/un.
Mão de obra: R$ 100/un.
```

Interpretação:

- R$ 667 de material com acréscimo de 30%.
- M.O. por ponto.

### 5.17. Item 1.17 — Pacote/escopo grande complementar

```text
Quantidade: 1 VB
Material: 49322 + 3000
Mão de obra: 37742 + 2500
```

Descrição engloba várias etapas:

- Projeto de fundação.
- Aço para vigas baldrame/radier.
- Forma.
- Concretagem.
- Regularização de radier.
- Projeto estrutural + aço engenheirado.
- Painelização e verticalização.
- Fechamento interno e externo.
- Instalação de régua pinus.
- Isolamento.
- Forro PVC.
- Infra elétrica.
- Cabeamento.
- Quadro elétrico.
- Instalações hidráulicas.

Recomendação:

- Não importar como um único serviço se o objetivo for ter controle gerencial.
- Primeiro decompor esse item em subserviços, usando as abas `Fundação`, `Instalações`, `PROJETO`, `TOPOGRAFIA` e demais memoriais.
- Se não houver tempo, cadastrar como “Pacote complementar REV10” com composição de verba, mas marcar como **[pendente de decomposição]**.

---

## 6. Regras para transformar a planilha em cadastro do sistema

### 6.1. Regra 1 — Não perder a rastreabilidade

Cada serviço criado deve guardar referência ao item original:

```text
Origem: Proposta Comercial item 1.x
Origem fórmula material: célula Fxx
Origem fórmula mão de obra: célula Gxx
Origem quantidade: célula Exx
Aba técnica relacionada: nome da aba, se houver
```

### 6.2. Regra 2 — Separar o que é calculado do que é número fixo

Tipos de origem:

1. **Calculado por fórmula física**: exemplo concreto = área × espessura × preço.
2. **Valor unitário arbitrado**: exemplo R$ 35/m², R$ 45/m², R$ 85/m².
3. **Verba global**: exemplo R$ 800 de stain, R$ 15.000 de fixadores.
4. **Valor vindo de memorial**: exemplo custo geral de uma aba dividido pela área/peso.
5. **Pacote sem decomposição**: item 1.17.

### 6.3. Regra 3 — Preferir unidade técnica correta

Exemplos:

- Mão de obra deve ser cadastrada em **h**, não em kg ou m².
- Aço deve ser em **kg**.
- Concreto deve ser em **m³**.
- Pintura pode ser serviço em **m²**, mas insumo de mão de obra deve ser h se houver produtividade.
- Verbas globais devem usar **vb**.

### 6.4. Regra 4 — Coeficiente deve representar consumo por unidade do serviço

Exemplos:

```text
h/kg
h/m²
kg/vb
m³/m²
un./un.
vb/vb
```

### 6.5. Regra 5 — Custos globais devem ser explícitos

Evitar embutir viagem, hospedagem, visita técnica e taxas dentro do valor de mão de obra sem registrar.

Criar insumos tipo **Outros**:

- Viagem equipe.
- Hospedagem.
- Pedágio.
- Visita técnica.
- Frete/ferramentas.
- Miscelâneas.

### 6.6. Regra 6 — Se o Excel não explicar o número, não inventar

Quando um valor não tiver origem clara:

- Manter o valor como insumo de verba ou taxa unitária.
- Marcar como `[origem não detalhada no Excel]`.
- Não tentar criar produtividade falsa.

### 6.7. Regra 7 — Validar sempre contra a proposta original

Para cada item:

```text
Valor original material = H da proposta
Valor original M.O. = I da proposta
Valor recalculado material = soma dos insumos materiais
Valor recalculado M.O. = soma dos insumos M.O.
Diferença R$
Diferença %
Status: OK / Revisar / Divergente
```

---

## 7. Estratégia de análise em loops

### Loop 1 — Inventário da planilha

Para cada aba:

1. Listar células preenchidas.
2. Separar blocos por assunto:
   - deslocamento;
   - hospedagem;
   - equipe;
   - resumo;
   - materiais;
   - levantamento de área/quantidade.
3. Registrar fórmulas importantes.
4. Identificar células que alimentam a proposta.

### Loop 2 — Análise das fórmulas da proposta

Para cada item 1.1 a 1.17:

1. Ler descrição, unidade, quantidade, custo material, custo M.O.
2. Identificar se F e G são número fixo ou fórmula.
3. Calcular valor unitário e total.
4. Mapear se o item depende de uma aba técnica.
5. Classificar origem:
   - físico;
   - arbitrado;
   - verba;
   - memorial;
   - pacote.

### Loop 3 — Extração de insumos

Para cada item:

1. Extrair materiais explícitos.
2. Extrair funções de mão de obra.
3. Extrair custos indiretos.
4. Criar nomes padronizados de insumos.
5. Definir tipo, unidade e preço.

### Loop 4 — Cálculo de coeficientes

Para cada serviço:

1. Definir a unidade principal do serviço.
2. Calcular material por unidade do serviço.
3. Calcular horas por unidade, quando possível.
4. Repetir insumo quando houver múltiplas pessoas iguais, se o sistema permitir.
5. Consolidar coeficiente apenas se a importação impedir duplicidade.

### Loop 5 — Validação

Para cada serviço:

1. Recalcular custo material.
2. Recalcular custo M.O.
3. Comparar com proposta original.
4. Marcar divergências.
5. Explicar a origem de cada divergência.

### Loop 6 — Plano de importação

Gerar arquivos/abas finais:

1. `01_INSUMOS`
2. `02_PRECOS_INSUMOS`
3. `03_SERVICOS`
4. `04_COMPOSICAO_SERVICOS`
5. `05_ORCAMENTO_PROPOSTA`
6. `06_VALIDACAO`
7. `07_DE_PARA_ORIGINAL`

---

## 8. Minha avaliação do plano

Este é um bom plano porque:

1. Separa o que hoje está misturado na planilha: material, mão de obra, equipe, viagem, hospedagem e proposta.
2. Permite reaproveitar serviços em orçamentos futuros.
3. Permite atualizar preço de insumos sem refazer tudo manualmente.
4. Mantém rastreabilidade com a planilha original.
5. Evita cadastrar mão de obra com unidade errada, como kg ou m².
6. Permite validar se o sistema está batendo com a planilha original.
7. Evita transformar números sem origem clara em produtividade falsa.

O ponto mais importante é não tentar “forçar” todos os números a virarem produtividade/hora quando a planilha não dá base para isso. Em alguns casos, o correto é cadastrar como verba ou taxa unitária e marcar para revisão.

---

## 9. Pontos de atenção encontrados

1. O item 1.1 usa R$ 7/kg de mão de obra, mas o coeficiente 0,022 h/kg com equipe de R$ 161,37/h gera R$ 3,55/kg. Isso precisa ser conciliado.
2. Alguns materiais aparecem como valor global, mas estão em coluna de custo unitário. Exemplo: R$ 800 em itens de pintura/stain, onde o total material não multiplica pela quantidade.
3. Alguns itens estão com unidade `vb`, mas usam quantidade em m². Exemplo: pintura dos fechamentos internos.
4. O item 1.9 calcula custo unitário com base em 44 pilares, mas a quantidade final é 32. Precisa confirmar se está correto.
5. O item 1.12 fala em ponto de luz por baia e pilar, mas a fórmula usa 12 × 400. Precisa conferir a quantidade real.
6. O item 1.17 é muito amplo e deve ser decomposto antes de virar catálogo definitivo.
7. As abas técnicas têm dados úteis de equipe e produção, mas nem todos os valores da proposta estão vinculados diretamente a elas.

---

## 10. Decisões recomendadas antes de importar

1. Definir jornada padrão: **8h ou 8,8h por dia**.
2. Definir se mão de obra será importada por função individual ou como equipe fechada.
3. Confirmar se o sistema aceitará insumo repetido na composição importada.
4. Confirmar se custos indiretos serão rateados ou lançados como insumos separados.
5. Definir se a meta é:
   - bater exatamente a proposta original;
   - ou montar uma base técnica mais correta, mesmo que apareçam diferenças.
6. Para valores sem origem clara, decidir se ficam como verba ou se serão revisados manualmente.

---

## 11. Prompt para Claude Code

Use o prompt abaixo no Claude Code junto com este arquivo `.md` e o Excel na file tree.

```text
Você está em um projeto de sistema de orçamento/gestão de obras. Eu vou colocar na file tree dois arquivos:

1. Um arquivo Markdown com regras de negócio e plano de conversão do orçamento: `plano_regras_conversao_orcamento_baia_rev10.md`.
2. O Excel original do orçamento: `Orçamento - Baia - REV10.xlsx` ou nome semelhante.

Sua tarefa inicial NÃO é sair implementando. Primeiro, faça uma análise técnica completa e confirme se o plano do Markdown é bom, se tem falhas, e como melhorá-lo.

Contexto do sistema:
- O aplicativo trabalha com catálogo de insumos, preços de insumos, serviços, composição de serviços e orçamento/proposta.
- Insumo é material, mão de obra, equipamento ou outros custos.
- Serviço é o item orçável/vendável.
- Composição é serviço × insumo × coeficiente.
- Coeficiente significa quanto de um insumo entra em 1 unidade do serviço.
- Para mão de obra, a unidade correta do insumo é hora (`h`).
- Para material, usar unidade física real: kg, m², m³, un., vb etc.
- O sistema aceita repetir o mesmo insumo em mais de uma linha na composição. Se houver 2 montadores, prefiro 2 linhas de Montador com o mesmo coeficiente, em vez de 1 linha com coeficiente dobrado. Se encontrar limitação técnica no código/importador, a alternativa é consolidar o coeficiente.

O que preciso que você faça:

1. Leia o Markdown inteiro.
2. Abra e analise o Excel inteiro, todas as abas:
   - `Proposta Comercial `
   - `Memorial de calculo`
   - `RESUMO CUSTOS `
   - `Fundação `
   - `Aço `
   - `Cobertura`
   - `Plaqueamento Interno `
   - `Plaqueamento Externo`
   - `Revestimento `
   - `Muro`
   - `Instalação Portas`
   - `Pintura `
   - `Instalações`
   - `PROJETO`
   - `TOPOGRAFIA`
3. Não altere o Excel original.
4. Analise em loops:
   - Loop 1: inventário de abas, blocos e campos importantes.
   - Loop 2: fórmulas da aba `Proposta Comercial`, item por item, de 1.1 a 1.17.
   - Loop 3: origem dos valores em cada item: material, mão de obra, verba global, memorial ou número arbitrado.
   - Loop 4: possíveis insumos extraídos por item.
   - Loop 5: possíveis serviços e composições.
   - Loop 6: cálculo de coeficientes e validação contra valores originais.
5. Avalie as fórmulas, não apenas os valores visíveis. Se o Excel tiver fórmulas sem valores calculados, use um método confiável para recalcular ou interprete as fórmulas manualmente. Se precisar, use LibreOffice headless, Python ou outra ferramenta adequada para inspecionar fórmulas e valores.
6. Procure referências cruzadas entre abas. Exemplo: células da proposta que puxam valores de `RESUMO CUSTOS`, `Aço`, `Fundação`, etc.
7. Confirme ou corrija a interpretação dos itens 1.1 a 1.17 descrita no Markdown.
8. Identifique divergências, ambiguidades e riscos. Exemplos esperados:
   - Item 1.1 usa R$ 7/kg de mão de obra, mas o coeficiente 0,022 h/kg com equipe de R$ 161,37/h gera R$ 3,55/kg.
   - Alguns materiais aparecem como verba global mesmo estando na coluna de custo unitário.
   - Alguns itens usam unidade `vb`, mas a quantidade parece ser m².
   - Item 1.9 usa base de 44 pilares mas quantidade final de 32.
   - Item 1.12 usa 12 pontos na fórmula, mas a descrição pode sugerir mais pontos.
9. Depois da análise, entregue um relatório em Markdown com:
   - Resumo executivo.
   - Mapa das abas e o papel de cada uma.
   - Tabela item 1.1 a 1.17 com fórmula, origem, interpretação, serviço sugerido, insumos sugeridos e status de confiança.
   - Lista de insumos candidatos.
   - Lista de serviços candidatos.
   - Regras de coeficiente confirmadas/corrigidas.
   - Pontos de decisão para o usuário.
   - Melhor plano de execução.
10. Só depois desse relatório, sugira a estrutura de arquivos/abas para importação:
   - `01_INSUMOS`
   - `02_PRECOS_INSUMOS`
   - `03_SERVICOS`
   - `04_COMPOSICAO_SERVICOS`
   - `05_ORCAMENTO_PROPOSTA`
   - `06_VALIDACAO`
   - `07_DE_PARA_ORIGINAL`
11. Não implemente alterações no sistema sem minha aprovação. Primeiro quero a confirmação do plano e a análise completa do orçamento.

Critérios de qualidade:
- Não invente origem de valores.
- Marque claramente `[não confirmado]`, `[inferência]` ou `[precisa validar]` quando a planilha não explicar o número.
- Priorize fidelidade ao orçamento original.
- Preserve rastreabilidade: cada insumo/serviço sugerido deve indicar de qual item, aba ou fórmula veio.
- Quando houver duas formas de modelar, explique prós e contras.
- Sempre compare o valor recalculado com o valor original da proposta.

Ao final, responda se o plano do Markdown é aprovado, aprovado com ajustes ou reprovado, explicando o motivo.
```
