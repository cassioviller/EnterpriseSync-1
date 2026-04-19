# Manual do Ciclo Completo do Sistema

> **Para você que vai usar o sistema no dia a dia** — engenheiro, dono
> de obra, administrador de empresa de construção. Este manual não
> exige conhecimento de informática nem de programação. Todos os passos
> têm um exemplo real preenchido (a empresa fictícia **Construtora
> Alfa**, o cliente **João da Silva**, a obra **Residencial Bela
> Vista**) para você seguir junto.

---

## Changelog (o que mudou desde a versão anterior — diferenças desde a Task #99)

> Esta versão do manual reflete o sistema **após a entrega da Task #102**
> (cronograma automático na aprovação). A versão anterior do manual
> documentou o estado do sistema na Task #99 — abaixo estão **todas as
> mudanças entre #99 e #107**.

| Bloco | O que mudou | Por que importa para você |
| --- | --- | --- |
| Cadastro de Serviço (etapa 3) | Apareceu um campo novo chamado **"Template padrão"** | É a "receita" que diz para o sistema, na hora da aprovação da proposta, quais grupos e quais subtarefas vão virar cronograma da obra |
| Aprovação da proposta (etapa 6) | O botão "Aprovar" passou a abrir uma **tela de revisão do cronograma** antes de tudo ser efetivado | Você decide — antes de fechar a obra — quais tarefas o cronograma vai ter e ajusta horas/dias de cada uma |
| Pós-aprovação (etapa 7) | A obra já nasce com cronograma de **3 níveis** (Serviço → Grupo → Subtarefa). Tarefas vindas do contrato têm a etiqueta "📋 do contrato" | O engenheiro de campo abre a obra e já encontra tudo organizado, sem precisar montar cronograma na mão |
| Reaprovar a mesma proposta | Não duplica nada | Você pode aprovar, perceber que faltou ajuste, e reaprovar sem virar tudo de cabeça para baixo |
| Aprovar (etapa 6) | Virou uma operação **única e indivisível**: ou tudo entra junto (obra + itens de medição + cronograma) ou nada entra | Acabou o caso "obra criada mas sem cronograma" |
| Regras herdadas | Continua valendo: aprovar **não** cria conta a receber. Existe **uma única** conta a receber por obra (`OBR-MED-#####`), alimentada pelas medições e RDOs finalizados | Se você abrir a tela de Contas a Receber e ver só uma linha por obra, é o esperado |

---

## Como o sistema pensa (leitura obrigatória — 2 minutos)

Antes de entrar nos passos, vale entender a "espinha dorsal" do sistema.
Ele foi construído em torno de uma única ideia:

> *Tudo que você cadastra hoje vai virar dinheiro depois — ou no caixa
> de entrada (cliente paga você) ou no caixa de saída (você paga
> funcionário e fornecedor). Cada cadastro existe para que o sistema
> consiga, sozinho, somar e classificar esse dinheiro nos lugares
> certos.*

A jornada vai mais ou menos assim:

```
  ┌──────────────┐    ┌────────────┐    ┌──────────┐
  │  Catálogo    │───▶│  Proposta  │───▶│  Obra    │
  │ (receitas    │    │ (orçamento │    │  (real)  │
  │  prontas)    │    │  p/ cliente│    │          │
  └──────────────┘    └────────────┘    └────┬─────┘
                                              │
                            ┌─────────────────┼──────────────┐
                            ▼                 ▼              ▼
                       ┌─────────┐      ┌─────────┐   ┌──────────────┐
                       │Cronograma│     │   RDO   │   │   Custos     │
                       │(planejado)│◀──▶│(execução│──▶│ (mão de obra │
                       └────┬─────┘     │  diária)│   │  + material) │
                            │           └────┬────┘   └──────┬───────┘
                            ▼                ▼               │
                       ┌─────────────────────────┐           │
                       │     Medição quinzenal   │           │
                       │  (% executado × valor)  │           │
                       └────────────┬────────────┘           │
                                    │                        │
                                    ▼                        ▼
                       ┌─────────────────────────┐   ┌──────────────┐
                       │   Conta a Receber única │   │ Conta a Pagar│
                       │ "OBR-MED-#####"         │   │              │
                       │ (atualiza sozinha)      │   │              │
                       └────────────┬────────────┘   └──────┬───────┘
                                    └──────┬─────────────────┘
                                           ▼
                                  ┌──────────────────┐
                                  │  Fluxo de Caixa  │
                                  └──────────────────┘
```

**Em uma frase:** você cadastra uma "receita pronta" no catálogo (com
preço, composição de insumos e cronograma-padrão). Quando essa receita
entra numa proposta, o sistema sabe orçar. Quando a proposta é
aprovada, ele cria a obra com tudo montado: lista de itens a medir,
cronograma de tarefas e ficha de custos. À medida que as tarefas
avançam (via RDO e medição), uma única conta a receber da obra cresce
e vira saldo no fluxo de caixa. Os custos lançados (funcionários,
material, almoxarifado) viram contas a pagar e descontam do mesmo
fluxo.

**Por que importa entender isso:** se em algum momento um número
estiver "errado" (ex.: "fiz medição mas não vi conta a receber nova"),
quase sempre o sistema fez exatamente o esperado — só que a intuição
do usuário antigo era de um fluxo diferente. O que vale é o desenho
acima.

---

## Sequência completa do ciclo (com a Construtora Alfa)

> **Cenário-mãe que vai aparecer em todos os passos:**
>
> *A Construtora Alfa acabou de fechar verbalmente com o senhor João
> da Silva a obra do "Residencial Bela Vista" — uma reforma residencial
> de 250 m², com início previsto em 01/05/2026 e contrato de
> R$ 250.000,00. A Alfa tem dois pedreiros: o Carlos (mensalista,
> R$ 2.800,00/mês) e o Pedro (diarista, R$ 180,00/dia). Vai usar dois
> serviços do catálogo (alvenaria e contrapiso), cobrar uma taxa de
> mobilização avulsa e ainda colocar R$ 5.000,00 de honorário de
> projeto digitado livre.*

Cada etapa abaixo segue o mesmo formato fixo de **8 blocos**:

1. *O que você está fazendo de verdade.*
2. *Por que o sistema pede isso.*
3. *Onde clicar.*
4. *O que aparece na tela.*
5. *Cada campo do formulário (com exemplo).*
6. *Botões disponíveis.*
7. *O que muda depois que você clica.*
8. *Notas de atenção.*

---

### Etapa 1 — Login do administrador

**1. O que você está fazendo de verdade.** Você está dizendo ao sistema
que é o dono ou o administrador da Construtora Alfa, para que ele
libere só as informações dela e bloqueie o que pertence a outras
empresas.

**2. Por que o sistema pede isso.** Várias empresas usam o mesmo
sistema. Cada uma só pode ver os próprios dados. Por isso o e-mail e
senha são a sua chave para entrar na "sala" da Construtora Alfa.

**3. Onde clicar.** Abrir o sistema no navegador → tela de login que
aparece sozinha quando você ainda não está logado.

**4. O que aparece na tela.** Cartão centralizado com o logo da empresa
no topo, dois campos verticais (e-mail e senha), um botão azul largo
embaixo. Existe ainda uma linha pequena "Esqueci a senha" abaixo do
botão.

**5. Cada campo do formulário.**

| Campo | Tipo | Obrigatório? | Exemplo | Se ficar vazio |
| --- | --- | :---: | --- | --- |
| E-mail | Texto | Sim | `joao.alfa@construtoraalfa.com` | Volta com aviso vermelho "Por favor, faça login para acessar esta página" |
| Senha | Senha (oculta) | Sim | `Alfa@2026` | Idem |

**6. Botões disponíveis.**

- **Entrar** (azul, ocupando toda a largura): manda os dados ao
  sistema. Se estiverem certos, leva você ao Dashboard. Se errados, o
  sistema mostra "Usuário ou senha inválidos".

**7. O que muda depois que você clica em Entrar.** O sistema carrega o
painel inicial (Dashboard) com os indicadores da Construtora Alfa do
mês atual: faturamento, custos, propostas em aberto, obras ativas. A
partir daqui, todos os menus laterais ficam liberados.

**8. Notas de atenção.**

- Em produção, a sessão fecha sozinha por inatividade — se isso
  acontecer, a próxima ação devolve você para esta tela.
- Se aparecer "Sessão expirada. Por favor, tente novamente.", é a
  mesma coisa: faça login de novo, nada foi perdido.

---

### Etapa 2 — Cadastro dos funcionários

> *Para tocar o Bela Vista, a Alfa precisa cadastrar o Carlos
> (pedreiro mensalista, R$ 2.800/mês) e o Pedro (pedreiro diarista,
> R$ 180/dia). Os dois recebem por PIX e têm vale-alimentação de
> R$ 25/dia trabalhado e vale-transporte de R$ 12/dia.*

**1. O que você está fazendo de verdade.** Cadastrando as pessoas que
vão trabalhar nas obras da Alfa, junto com a forma de pagamento de
cada uma.

**2. Por que o sistema pede isso.** O cadastro do funcionário é o ponto
de partida para tudo que envolve mão de obra: ponto, RDO, folha,
vale-transporte, vale-alimentação e PIX. Sem cadastro, o sistema não
sabe quem está na obra nem quanto custa cada hora.

**3. Onde clicar.** Menu lateral → "Funcionários" → botão verde
"+ Novo Funcionário" no canto superior direito.

**4. O que aparece na tela.** Formulário em duas colunas, agrupado em
quatro blocos verticais:

1. **Dados pessoais** — nome, CPF, RG, nascimento, telefone, e-mail.
2. **Dados profissionais** — admissão, função, departamento, jornada.
3. **Pagamento e benefícios** — tipo de remuneração, salário OU
   diária, chave PIX, vale-alimentação, vale-transporte.
4. **Foto** — campo de upload + foto facial opcional.

**5. Cada campo do formulário (apenas os que importam para o ciclo).**

| Campo | Tipo | Obrigatório? | Exemplo do Carlos | Exemplo do Pedro |
| --- | --- | :---: | --- | --- |
| Nome | Texto | Sim | `Carlos da Silva Pereira` | `Pedro Oliveira` |
| CPF | Texto (com máscara) | Sim | `123.456.789-00` | `987.654.321-00` |
| Data de admissão | Data | Sim | `01/05/2026` | `01/05/2026` |
| Tipo de remuneração | Dropdown ("Salário" / "Diária") | Sim | `Salário` | `Diária` |
| Salário | Numérico (R$) | Só se "Salário" | `R$ 2.800,00` | — |
| Valor da diária | Numérico (R$) | Só se "Diária" | — | `R$ 180,00` |
| Chave PIX | Texto | Não, mas recomendado | `123.456.789-00` | `pedro@gmail.com` |
| Vale-Alimentação por dia | Numérico (R$) | Não | `R$ 25,00` | `R$ 25,00` |
| Vale-Transporte por dia | Numérico (R$) | Não | `R$ 12,00` | `R$ 12,00` |

**6. Botões disponíveis.**

- **Salvar** (verde, embaixo): grava o funcionário e volta para a
  lista.
- **Cancelar** (cinza): volta sem salvar.

**7. O que muda depois que você clica em Salvar.**

- O funcionário aparece na listagem com uma etiqueta "Mensalista" ou
  "Diarista" (cor diferente).
- Ele já pode ser escolhido como mão de obra em qualquer RDO.
- Quando o RDO for finalizado, o sistema usa esse cadastro para
  calcular automaticamente o custo da mão de obra e jogar no Fluxo de
  Caixa como conta a pagar.

**8. Notas de atenção.**

- Para diarista, é obrigatório preencher "Valor da diária"; senão, o
  custo de mão de obra sai zero — é o erro mais comum hoje.
- O VA e o VT são por **dia trabalhado**: o sistema multiplica
  automaticamente quando vê o ponto.
- O CPF é único — se você tentar cadastrar um CPF que já existe (até
  em outra empresa do mesmo sistema), aparece erro vermelho.

---

### Etapa 3 — Catálogo de serviços com Template padrão

> *A Alfa quer cadastrar dois serviços: "Alvenaria de bloco cerâmico"
> e "Contrapiso desempenado". Cada um já tem uma "receita" de
> cronograma — um conjunto de subtarefas que normalmente faz parte
> dele. É essa receita que vai virar o cronograma da obra
> automaticamente quando uma proposta com esses serviços for aprovada.*

**1. O que você está fazendo de verdade.** Você está montando o
"cardápio" da empresa: para cada serviço que ela costuma vender, está
dizendo (a) quanto custa fazer 1 m² (ou 1 unidade), (b) quais insumos
entram na receita e (c) **qual é o cronograma-padrão** que esse serviço
vira quando for aprovado em uma obra.

**2. Por que o sistema pede isso.** Sem catálogo, cada proposta vira
trabalho braçal de digitação e cada obra vira uma planilha do zero.
Com catálogo, fazer uma proposta nova vira escolher do dropdown e
deixar o sistema calcular tudo. Com a "receita" de cronograma
preenchida, aprovar a proposta já gera o cronograma da obra — você
economiza horas de trabalho.

**3. Onde clicar.**

- Para criar/editar um Template de cronograma: menu lateral →
  "Cronograma" → "Templates" → botão verde "+ Novo template".
- Para criar/editar um Serviço: menu lateral → "Catálogo" → aba
  "Serviços" → botão verde "+ Novo Serviço".

**4. O que aparece na tela do serviço.**

- **Topo** — dados do serviço (nome, unidade de medida, categoria,
  imposto%, lucro%).
- **Meio** — composição: lista de insumos com coeficiente (ex.: para
  1 m² de alvenaria, quantos blocos, quantos kg de cimento, quantas
  horas de pedreiro).
- **Bloco novo** — seção "Cronograma":
  - Campo **"Template padrão"** (dropdown com busca) — você escolhe
    qual template do tenant será usado quando uma proposta com esse
    serviço for aprovada.
  - Botão **"Editar template"** (azul, abre o construtor visual em
    uma nova aba).
  - Botão **"Criar novo template"** (verde, abre o construtor visual
    vazio em uma nova aba).
- **Rodapé** — preço calculado automaticamente: custo unitário,
  imposto, lucro, **preço de venda**.

**5. Cada campo (exemplos do "Alvenaria de bloco cerâmico").**

| Campo | Tipo | Obrigatório? | Exemplo | Se ficar vazio |
| --- | --- | :---: | --- | --- |
| Nome | Texto | Sim | `Alvenaria de bloco cerâmico 9x19x19` | Bloqueia o salvar |
| Unidade de medida | Dropdown | Sim | `m²` | Bloqueia |
| Categoria | Texto/Dropdown | Sim | `Estrutura` | Bloqueia |
| Imposto (%) | Numérico | Não | `8` | Sistema usa 0 |
| Margem de lucro (%) | Numérico | Não | `15` | Sistema usa 0 |
| Composição (insumos) | Tabela | Recomendado | `Bloco × 14 un/m²; Argamassa × 0,02 m³/m²; Pedreiro × 0,75 h/m²` | Sai sem custo unitário |
| **Template padrão** | Dropdown com busca | **Não, mas altamente recomendado** | `Alvenaria — passo a passo` | A proposta aprova mas a obra **nasce sem cronograma** desse serviço (apenas o item de medição é criado). Aparece aviso na tela de revisão da etapa 6. |

**6. Botões disponíveis.**

- **Salvar** (verde): grava e volta para a lista de serviços.
- **Recalcular preço** (azul claro): recalcula o "Preço de venda
  unitário" na hora, com base na composição e no imposto+lucro.
- **Editar template** / **Criar novo template**: abrem o construtor
  visual de cronograma-padrão em outra aba (você pode trocar de aba,
  desenhar a árvore Grupo→Subtarefa arrastando os itens, salvar, e
  voltar para finalizar o serviço).

**7. O que muda depois que você clica em Salvar.**

- O serviço passa a aparecer no autocomplete dos formulários de
  Proposta e Medição.
- Quando uma proposta com esse serviço for aprovada, o sistema vai
  consultar o "Template padrão" para sugerir o cronograma da obra.

**8. Notas de atenção.**

- Se Imposto + Lucro chegar a 100% ou mais, o sistema sinaliza erro
  e zera o preço (proteção matemática).
- O mesmo Template pode ser usado por vários serviços diferentes —
  reutilize.
- Itens que não são serviço técnico (mobilização, limpeza final,
  entrega de chaves) podem ser cadastrados como serviços fictícios
  no catálogo, com seu próprio template — é o que a Alfa fará com a
  "Mobilização de obra".

---

### Etapa 4 — Importar funcionários por planilha (opcional)

**1. O que você está fazendo de verdade.** Em vez de cadastrar um por
um, está jogando uma planilha Excel com vários funcionários de uma
vez.

**2. Por que o sistema pede isso.** Construtoras com 30+ funcionários
não querem digitar tudo na mão.

**3. Onde clicar.** Menu lateral → "Importar por Planilha". Se esse
item não aparecer no menu, é porque a tela teve um problema no boot —
o sistema esconde o link automaticamente para evitar erro.

**4. O que aparece na tela.** Em sequência vertical: (1) Botão "Baixar
template Excel oficial". (2) Campo de upload. (3) Tabela com
pré-visualização do que vai ser importado. (4) Botão verde
"Confirmar importação".

**5. Cada coluna esperada na planilha.**

| Coluna | Obrigatória? | Exemplo |
| --- | :---: | --- |
| Nome | Sim | `Carlos da Silva Pereira` |
| CPF | Sim | `123.456.789-00` |
| Tipo de remuneração | Sim | `Salário` ou `Diária` |
| Salário | Sim se Mensalista | `2800,00` |
| Diária | Sim se Diarista | `180,00` |
| Chave PIX | Não | `123.456.789-00` |
| VA | Não | `25,00` |
| VT | Não | `12,00` |
| Data admissão | Sim | `01/05/2026` |
| Função | Sim | `Pedreiro` |

**6. Botões disponíveis.**

- **Baixar template** (cinza): traz o arquivo Excel oficial.
- **Enviar arquivo** (azul): sobe a planilha preenchida.
- **Confirmar importação** (verde, só ativa após o upload).

**7. O que muda depois que você confirma.** Linhas válidas viram
funcionários. Linhas com erro aparecem destacadas em vermelho com a
coluna problemática. Os custos importados (diárias, VA, VT) vão para
um único pai mensal por categoria.

**8. Notas de atenção.** Sempre baixe o template oficial — formatos
diferentes não são aceitos. CPFs duplicados são rejeitados linha a
linha; o resto da planilha continua sendo importado.

---

### Etapa 5 — Nova proposta com catálogo + cálculo automático

> *A Alfa vai montar a proposta para o senhor João: 250 m² de
> alvenaria + 250 m² de contrapiso (ambos com Template padrão), uma
> taxa de mobilização (serviço sem template) e mais R$ 5.000,00 de
> "honorário de projeto" digitado livre (sem serviço de catálogo,
> só texto).*

**1. O que você está fazendo de verdade.** Está montando o orçamento
que vai para o cliente. O sistema consulta o catálogo, calcula tudo
automaticamente, congela esse cálculo na proposta e gera um link
público para o cliente aprovar.

**2. Por que o sistema pede isso.** A proposta é o documento
contratual; congelar o cálculo no momento da gravação garante que
mudanças futuras de preço de insumo não bagunçam propostas antigas (o
sistema guarda uma "foto" do que valia naquele dia).

**3. Onde clicar.** Menu lateral → "Propostas" → botão verde "+ Nova
Proposta" no canto superior direito.

**4. O que aparece na tela.** Cabeçalho com dados do cliente; corpo
com itens da proposta (uma linha por item, repetível); rodapé com
BDI, total geral e botões.

**5. Cada campo do cabeçalho e dos itens.**

| Campo (cabeçalho) | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Cliente | Texto | Sim | `João da Silva` |
| Documento (CPF/CNPJ) | Texto | Recomendado | `111.222.333-44` |
| Endereço da obra | Texto | Recomendado | `Rua das Flores, 100, São Paulo/SP` |
| Prazo de entrega (dias) | Numérico | Recomendado | `90` |

| Campo (item) | Tipo | Exemplo (alvenaria) | Exemplo (mobilização) | Exemplo (honorário) |
| --- | --- | --- | --- | --- |
| Serviço (catálogo) | Combobox com busca | `Alvenaria de bloco cerâmico` | `Mobilização de obra` | (deixar vazio) |
| Descrição | Texto | (preenchido automaticamente) | (idem) | `Honorário de projeto executivo` |
| Quantidade | Numérico | `250` | `1` | `1` |
| Unidade | Texto | `m²` (auto) | `un` (auto) | `un` (digitado) |
| Preço unitário | Numérico (R$) | `R$ 145,00` (auto) | `R$ 1.500,00` (auto) | `R$ 5.000,00` (digitado) |
| Subtotal | Calculado | `R$ 36.250,00` | `R$ 1.500,00` | `R$ 5.000,00` |

**6. Botões disponíveis.**

- **+ Adicionar item** (verde claro): adiciona uma nova linha.
- **Salvar rascunho** (cinza): grava sem enviar ao cliente.
- **Enviar ao cliente** (azul): grava e libera o link público para o
  João abrir.

**7. O que muda depois que você salva.** A proposta entra na lista com
status "Enviada"; o cliente recebe o link; o sistema congela o custo,
lucro e subtotal de cada item; o total geral aparece no cabeçalho.

**8. Notas de atenção.**

- Itens com serviço de catálogo geram cronograma na hora da
  aprovação (próxima etapa). Itens **sem serviço** ou **com serviço
  sem Template padrão** **não** geram tarefas — só item de medição.
- Mudar o preço do insumo no catálogo **depois** não altera propostas
  já gravadas. É de propósito.

---

### Etapa 6 — Aprovar a proposta e revisar o cronograma

> *O senhor João topou o orçamento. Antes de a Alfa fechar a aprovação
> no sistema, ela quer ajustar o cronograma sugerido — tirar uma
> subtarefa que não cabe no escopo dele e aumentar as horas de uma
> outra que ela sabe que vai demorar mais.*

Esta é a etapa que **mais mudou** desde a versão anterior do manual.
Em vez do botão "Aprovar" antigo (que aprovava direto), agora você
passa por uma tela de revisão.

**1. O que você está fazendo de verdade.** Você está dizendo ao
sistema: "Sim, está tudo certo com a proposta — pode criar a obra,
gerar o cronograma desta forma específica e abrir o portal do
cliente."

**2. Por que o sistema pede a tela de revisão.** Cada serviço do
catálogo tem uma receita-padrão de cronograma. Mas cada obra é única.
A tela de revisão é o seu momento de ajustar a receita à realidade
desta obra antes de tudo virar pedra.

**3. Onde clicar.**

- **Caminho admin:** menu lateral → "Propostas" → linha da proposta →
  botão verde **"Aprovar e gerar cronograma"** no canto superior
  direito.
- **Caminho cliente (senhor João):** ele recebe o link público da
  proposta por e-mail, vê a proposta completa e clica no botão verde
  no rodapé "Aprovar proposta". Se você (admin) já tinha
  pré-configurado o cronograma na tela de revisão **antes**, o
  sistema usa essa configuração; senão, ele usa a sugestão padrão
  (tudo marcado).

**4. O que aparece na tela de revisão.**

```
┌──────────────────────────────────────────────────────────────────┐
│ Revisão do cronograma — Proposta #2026-001 / João da Silva       │
├──────────────────────────────────────────────────────────────────┤
│ ▼ ☑ Alvenaria de bloco cerâmico  (250 m²) — 80 h estimadas       │
│       ▼ ☑ Grupo: Preparação                                       │
│             ☑ Marcar bloco e linha de prumo  | 2 dias | 16 h     │
│             ☑ Argamassa de assentamento      | 1 dia  |  8 h     │
│       ▼ ☑ Grupo: Execução                                         │
│             ☑ Levantar paredes               | 5 dias | 40 h     │
│             ☐ Reforço de vergas              | 1 dia  |  8 h     │
│             ☑ Limpeza pós-execução           | 1 dia  |  8 h     │
│ ▼ ☑ Contrapiso desempenado (250 m²) — 40 h estimadas              │
│       ▼ ☑ Grupo: Execução                                         │
│             ☑ Nivelamento                    | 2 dias | 16 h     │
│             ☑ Lançamento                     | 2 dias | 16 h     │
│             ☑ Acabamento                     | 1 dia  |  8 h     │
│ ⚠ Mobilização de obra — sem template                              │
│       Apenas item de medição será criado.                         │
│ ⓘ Honorário de projeto executivo — sem serviço                    │
│       Não vai virar tarefa do cronograma. Adicione manualmente    │
│       depois se precisar.                                         │
├──────────────────────────────────────────────────────────────────┤
│ Resumo: 7 tarefas marcadas | 112 h total | término previsto:     │
│         28/05/2026                                                │
│                                                                  │
│  [ Cancelar ]  [ Salvar pré-configuração ]  [ Confirmar aprovação│
│                                                e gerar cronograma]│
└──────────────────────────────────────────────────────────────────┘
```

**5. Cada elemento da tela.**

| Elemento | Tipo | Como funciona | Exemplo |
| --- | --- | --- | --- |
| Checkbox do Serviço (raiz) | Caixa de seleção | Desmarcar tira o ramo todo | Desmarque "Contrapiso" e a obra nasce só com cronograma de alvenaria |
| Checkbox do Grupo | Caixa de seleção | Cascata: desmarca todas as subtarefas filhas | Desmarque "Grupo: Execução" e some o trio Levantar/Reforço/Limpeza |
| Checkbox da Subtarefa | Caixa de seleção | Marca/desmarca uma folha | Desmarque "Reforço de vergas" porque a obra do João não tem |
| Campo "dias" | Numérico inline | Clique e edite | De `1` para `2` |
| Campo "horas" | Numérico inline | Clique e edite | De `8` para `16` |
| Aviso amarelo (folha sem horas) | Texto | Indica que o sistema vai dividir o peso da medição em partes iguais entre as folhas marcadas | Recomenda voltar à etapa 3 e configurar horas estimadas |
| Aviso laranja (serviço sem template) | Texto | Item criado para medição, mas sem cronograma | "Mobilização de obra" no exemplo |
| Aviso azul (item sem serviço) | Texto | Não cria nada no cronograma | "Honorário de projeto" no exemplo |

**6. Botões disponíveis.**

- **Cancelar** (cinza): volta para a proposta sem aprovar.
- **Salvar pré-configuração** (azul claro, opcional): se a Alfa ainda
  não quer aprovar agora mas quer deixar a configuração pronta para
  o cliente aprovar pelo portal, este botão grava a árvore atual.
  Quando o cliente clicar "Aprovar proposta" no portal, ele herda
  exatamente esta configuração.
- **Confirmar aprovação e gerar cronograma** (verde grande): executa
  tudo de uma vez (criar obra, item de medição, cronograma de 3
  níveis, vínculo Item de Medição × tarefa-folha com peso, lançamento
  contábil). É uma operação **única e indivisível** — se qualquer
  coisa falhar, o sistema desfaz tudo e mostra "Falha ao aprovar a
  proposta. Nada foi gravado".

**7. O que muda depois que você confirma.**

- A proposta vira status "Aprovada".
- Nasce uma **Obra** com código `OBR####`, vinculada à proposta, com
  o nome do cliente ("João da Silva"), valor de contrato (no
  exemplo, R$ 42.750,00), link público do portal e portal já ativo.
- Nasce **um item de medição** por item de proposta (4 itens no
  exemplo: alvenaria, contrapiso, mobilização e honorário).
- Nasce o **cronograma da obra** com 7 tarefas marcadas, organizadas
  em 3 níveis (Serviço → Grupo → Subtarefa).
- Cada item de medição ganha vínculos de peso para suas
  subtarefas-folha (no exemplo: a alvenaria tem 4 folhas marcadas, e
  o peso de cada uma é proporcional às horas).
- O sistema lança contabilmente a aprovação — mas **não** cria conta
  a receber neste momento.
- Tela final: aviso verde "Proposta aprovada com sucesso" + link
  para a obra recém-criada.

**8. Notas de atenção.**

- A aprovação é uma operação **única e indivisível** — se algo der
  ruim no meio, **nada** é gravado. Não vai existir o caso "obra
  criada mas cronograma vazio".
- Reaprovar a mesma proposta não duplica tarefas (ver etapa 8).
- Se você desmarcar **tudo** em um serviço, ele ainda cria o item
  de medição (para você cobrar do cliente), mas o cronograma fica
  sem aquele ramo.
- Se a aprovação vier pelo portal do cliente **sem** pré-configuração
  salva, o sistema usa a árvore default (tudo marcado) — então é
  boa prática você revisar e usar "Salvar pré-configuração" antes
  de enviar a proposta ao cliente.

---

### Etapa 7 — Verificação pós-aprovação

**1. O que você está fazendo de verdade.** Está conferindo se tudo o
que era para ser criado pela aprovação realmente foi criado.

**2. Por que isso importa.** É o seu checklist para garantir que o
engenheiro de campo vai abrir a obra e encontrar tudo certo.

**3. Onde clicar.** Menu lateral → "Obras" → linha "Residencial Bela
Vista" (que apareceu sozinha após a aprovação). O painel da obra abre
com várias abas: Resumo, Cronograma, Medição comercial, Custos,
Contas a Receber, RDOs, Almoxarifado, Cotação.

**4. O que aparece na tela.** Aba "Resumo" no topo com card de cliente,
valor de contrato, código `OBR####`, status "Em andamento" e link do
portal do cliente.

**5. Cada aba e o que conferir.**

| Aba | O que conferir | O que esperar (exemplo) |
| --- | --- | --- |
| Resumo | Cliente, valor, código, link | Cliente "João da Silva", R$ 42.750,00, `OBR0012`, link preenchido |
| Cronograma | 7 tarefas em 3 níveis, etiqueta "📋 do contrato", datas começando em 01/05/2026 | Alvenaria como raiz, Preparação/Execução como grupos, subtarefas como folhas |
| Medição comercial | 4 itens; alvenaria/contrapiso com vínculos para as folhas; mobilização e honorário sem vínculo de cronograma | 250 m² de alvenaria, 250 m² de contrapiso, 1 mobilização, 1 honorário |
| Custos | Zerada — não há lançamentos ainda | Tabela vazia |
| Contas a Receber | Zerada — porque a aprovação não cria conta a receber | Tabela vazia (nascerá só na primeira medição) |

**6. Botões disponíveis nesta tela.**

- **Editar obra** (azul): abrir formulário de obra para ajustar
  endereço, datas, etc.
- **Abrir portal do cliente** (cinza): abre em outra aba como o
  senhor João vê.
- **+ Novo RDO** (verde, na aba RDOs): inicia o relatório do dia
  (etapa 10).

**7. O que muda depois que você verifica.** Nada — esta é uma etapa
de leitura, não escreve nada no sistema.

**8. Notas de atenção.**

- O "Honorário de projeto" aparece como item de medição mas sem
  cronograma — se você quiser cobrar isso por etapa, lance uma
  tarefa avulsa no cronograma e vincule manualmente ao item.
- Se aparecer aviso laranja "cronograma pendente" no topo da aba
  Cronograma, é uma obra antiga (anterior à atualização da etapa 6).
  Aprovações novas não cairão nesse caso.

---

### Etapa 8 — Reaprovar (idempotência)

**1. O que você está fazendo de verdade.** Testando que, se você
clicar de novo em "Aprovar e gerar cronograma" para a mesma proposta,
o sistema não vai duplicar nada.

**2. Por que importa.** Acontece muito do usuário achar que o clique
não foi registrado e clicar de novo. O sistema tem que ser robusto a
isso.

**3. Onde clicar.** Mesma tela da etapa 6 — botão "Aprovar e gerar
cronograma" outra vez.

**4. O que aparece na tela.** Mesma tela de revisão, com a árvore já
preenchida do jeito que você marcou da última vez.

**5. Cada elemento (igual à etapa 6).** Não muda — o sistema só
reabre a árvore com a configuração salva.

**6. Botões disponíveis.** Os mesmos da etapa 6 — Cancelar, Salvar
pré-configuração, Confirmar aprovação.

**7. O que muda depois que você confirma de novo.**

- A obra continua com 7 tarefas (não vira 14).
- A conta a receber continua igual.
- Aparece aviso informativo "Proposta já está aprovada. Nenhuma
  alteração foi feita".

**8. Notas de atenção.**

- A não-duplicação vale para tudo o que **ainda existe** na obra. Se
  você excluiu uma tarefa "📋 do contrato" manualmente entre as duas
  aprovações, ela **não** é recriada na segunda aprovação (ver etapa
  9). Para forçar recriação, ajuste manualmente o cronograma da obra.

---

### Etapa 9 — Cronograma da obra

**1. O que você está fazendo de verdade.** Refinando o cronograma já
criado: ajustando datas, adicionando predecessoras, criando tarefas
extras se precisar.

**2. Por que importa.** Mesmo o melhor template de catálogo não
adivinha a realidade da obra do João — chuva, atraso de fornecedor,
mudança de pedido do cliente. O cronograma da obra é o lugar onde a
vida real entra.

**3. Onde clicar.** Aba "Cronograma" da obra.

**4. O que aparece na tela.** Gantt interativo: lista de tarefas
hierárquica à esquerda (com seta de expandir/recolher por grupo),
barras temporais à direita. Cada tarefa do contrato exibe a etiqueta
**"📋 do contrato"** com tooltip dizendo de qual item da proposta ela
veio.

**5. Cada coluna e cada interação.**

| Coluna / Interação | Tipo | Para que serve |
| --- | --- | --- |
| Nome da tarefa | Texto editável (clique) | Renomear |
| Início / Fim | Data editável | Ajustar prazo |
| Dias | Numérico | Aumentar/diminuir duração |
| Predecessora | Dropdown | Escolher tarefa que precisa terminar antes |
| Responsável | Dropdown | Empresa ou cliente |
| % concluído | Numérico (0–100) | Avanço manual (no dia a dia, vem do RDO) |
| Etiqueta "📋 do contrato" | Indicador | Mostra que a tarefa veio da aprovação da proposta |

**6. Botões disponíveis.**

- **+ Nova tarefa** (verde): inserir tarefa avulsa.
- **Importar** (azul): importar de planilha.
- **Recalcular predecessoras** (cinza): refaz datas em cascata
  respeitando calendário e predecessoras.
- **Excluir** (vermelho, ao passar o mouse na linha): remove a
  tarefa.

**7. O que muda depois que você edita.**

- Mudar duração ou predecessora dispara recálculo automático das
  datas das tarefas dependentes.
- Avanço manual em % atualiza a barra do Gantt na hora.
- Excluir tarefa "📋 do contrato" remove o vínculo dela com o item de
  medição — peso da medição se redistribui automaticamente.

**8. Notas de atenção.**

- Ao tentar **editar** ou **excluir** uma tarefa que tem a etiqueta
  "📋 do contrato", o sistema mostra um aviso extra:
  > *"Esta tarefa veio do contrato (proposta #2026-001). Mexer nela
  > pode afetar o cálculo da medição. Confirma mesmo assim?"*
- Tarefas adicionadas manualmente **depois** da aprovação não têm
  essa etiqueta e podem ser editadas livremente.

---

### Etapa 10 — RDO + métricas

> *Hoje é 02/05/2026, segundo dia da obra. O Carlos e o Pedro
> trabalharam 8 horas cada um na subtarefa "Marcar bloco e linha de
> prumo". Produziram 30 m² da marcação.*

**1. O que você está fazendo de verdade.** O encarregado preenche
diariamente o "Relatório Diário de Obra" — quem trabalhou, em qual
subtarefa, por quantas horas e quanto produziu.

**2. Por que importa.** O RDO é o gatilho que faz o sistema recalcular
a medição (e portanto a conta a receber) e os custos da obra
automaticamente.

**3. Onde clicar.** Menu lateral → "RDO" → botão verde "+ Novo RDO".

**4. O que aparece na tela.** Cabeçalho com data + obra. Em seguida,
duas seções: **(a) Mão de obra** (lista de funcionários alocados com
horas trabalhadas) e **(b) Avanço de subatividade** (lista de
subtarefas com quantidade produzida no dia).

**5. Cada campo do RDO.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Data | Data | Sim | `02/05/2026` |
| Obra | Dropdown | Sim | `Residencial Bela Vista` |
| Funcionário | Dropdown | Sim | `Carlos da Silva Pereira` |
| Horas trabalhadas | Numérico | Sim | `8` |
| Hora extra | Numérico | Não | `0` |
| Subatividade do cronograma | Dropdown | Sim | `Marcar bloco e linha de prumo` |
| Quantidade produzida | Numérico | Sim | `30` (m²) |
| Observação | Texto | Não | `Marcação concluída no quarto 1` |

**6. Botões disponíveis.**

- **Salvar rascunho** (cinza): pode editar depois.
- **Finalizar** (verde): dispara recálculo de custo + medição.
- **Cancelar** (cinza claro).

**7. O que muda depois de finalizar o RDO.**

- O sistema cria automaticamente um custo de mão de obra para cada
  funcionário do RDO (Carlos pelo valor-hora do salário; Pedro pelo
  valor da diária + adicional de hora extra se houver).
- A subtarefa do cronograma avança em % conforme a quantidade
  produzida.
- A conta a receber única da obra (`OBR-MED-#####`) é atualizada
  com o novo valor medido — sem criar uma linha nova.

**8. Notas de atenção.**

- RDO em rascunho não dispara nada. Só a transição para
  **"Finalizado"** dispara o cálculo.
- Diaristas usam fórmula `valor_diaria × dias_pagos + (HE/8) ×
  valor_diaria × 1,5`; mensalistas usam `horas × valor_hora + HE ×
  valor_hora × 1,5`.
- Se o funcionário foi cadastrado sem salário/diária (etapa 2), o
  custo sai zero. Volte na ficha do funcionário e arrume.

---

### Etapa 11 — Custos automáticos (mão de obra + material)

> *O encarregado tirou 14 sacos de cimento e 200 blocos do almoxarifado
> para a obra do Bela Vista. Cada saco custou R$ 30,00 e cada bloco
> R$ 1,80.*

**1. O que você está fazendo de verdade.** Está garantindo que o
sistema some sozinho todo gasto da obra: salário do funcionário (via
RDO) + material (via almoxarifado ou compras) + serviços terceirizados.

**2. Por que importa.** Sem este cálculo automático, a margem da obra
no fim do mês é só chute. Com ele, você compara em tempo real
"recebido" × "gasto".

**3. Onde clicar.**

- Mão de obra: nada a fazer aqui — vem sozinha do RDO finalizado
  (etapa 10).
- Material por almoxarifado: menu lateral → "Almoxarifado" →
  "Saídas" → botão "+ Nova saída" → selecione obra + serviço + item +
  quantidade.
- Material por compra direta: menu lateral → "Compras" → "+ Novo
  pedido" → selecione obra + serviço + fornecedor + itens.

**4. O que aparece na tela.** Em "Custos" (menu lateral → "Custos" →
"Gestão de Custos V2") aparecem dois níveis: pais (categorias) e
filhos (lançamentos individuais), filtráveis por obra, por funcionário
e por mês.

**5. Cada campo de uma saída de almoxarifado.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Obra | Dropdown | Sim | `Residencial Bela Vista` |
| Serviço da obra | Dropdown | Recomendado | `Alvenaria de bloco cerâmico` |
| Item | Dropdown | Sim | `Cimento CP-II 50 kg` |
| Quantidade | Numérico | Sim | `14` |
| Data | Data | Sim | `02/05/2026` |

**6. Botões disponíveis.**

- **Salvar** (verde): efetiva a saída.
- **Cancelar** (cinza).

**7. O que muda depois que você confirma.**

- O estoque do almoxarifado diminui.
- Um custo de material é criado e vinculado à obra (e ao serviço, se
  você selecionou).
- O custo aparece automaticamente nos painéis "Custos" e "Fluxo de
  Caixa".

**8. Notas de atenção.**

- Se você lançar uma saída **antes** de cadastrar o serviço da obra
  correspondente, o custo entra **sem** vínculo ao serviço. Existe
  um plano de melhoria para corrigir essa lacuna.
- Custos antigos de RDO (antes da última grande atualização) podem
  estar sem vínculo de serviço — também há plano de melhoria
  específico para isso.

---

### Etapa 12 — Medição quinzenal e a Conta a Receber única

> *Quinze dias depois do início da obra (15/05/2026), a Alfa quer
> fazer a primeira medição para enviar a fatura ao senhor João. Já
> foram executados 70 m² de alvenaria.*

**1. O que você está fazendo de verdade.** Está consolidando quanto
da obra foi executado nestes 15 dias e gerando o documento oficial de
medição para enviar ao cliente.

**2. Por que importa.** A medição é o que vira fatura. Mas — e é a
parte mais importante para entender — a medição **não cria uma nova
conta a receber**: ela atualiza a **única** conta a receber viva da
obra.

**3. Onde clicar.** Aba "Medição" da obra → botão "Nova medição
quinzenal".

**4. O que aparece na tela.** Lista de itens de medição com colunas:
"Quantidade contratada", "% acumulado", "Valor executado acumulado",
"Saldo", campo "Quantidade desta medição" (editável).

**5. Cada coluna.**

| Coluna | Tipo | Exemplo (alvenaria) |
| --- | --- | --- |
| Item | Texto | `Alvenaria de bloco cerâmico` |
| Quantidade contratada | Numérico | `250 m²` |
| Quantidade desta medição | Numérico (editável) | `70` |
| % desta medição | Calculado | `28%` |
| Valor desta medição | Calculado (R$) | `R$ 10.150,00` |
| % acumulado | Calculado | `28%` |
| Valor executado acumulado | Calculado (R$) | `R$ 10.150,00` |

**6. Botões disponíveis.**

- **Salvar rascunho** (cinza): edita depois.
- **Fechar medição** (verde): efetiva e atualiza a conta a receber.
- **Gerar PDF** (azul, depois de fechada): produz o boletim oficial.

**7. O que muda depois de fechar a medição.**

- O sistema soma o valor medido acumulado de todos os itens.
- A conta a receber única `OBR-MED-#####` é atualizada:
  - Valor da conta = novo valor medido acumulado.
  - Saldo = valor medido − valor já recebido (mínimo zero).
  - Status anda sozinho: PENDENTE → PARCIAL → QUITADA conforme o
    senhor João vai pagando.
- A medição quinzenal fica vinculada a essa mesma conta — **não há
  uma conta separada por medição** (regra mais importante de
  entender).

**8. Notas de atenção — a dúvida mais comum.**

> *"Lancei medição mas não vi conta a receber nova. Está errado?"*
>
> **Não.** É exatamente o esperado. Existe **uma única** conta a
> receber viva por obra. Olhe a linha `OBR-MED-#####` da obra: o
> valor dela aumentou. Para saber "quanto medi neste fechamento", use
> o histórico de itens de medição por período (a aba "Medição
> comercial" mostra o acumulado por data).

---

### Etapa 13 — Aprovação financeira em 2 etapas + Fluxo de Caixa

**1. O que você está fazendo de verdade.** Cada custo (compras, mão
de obra) e cada receita passa por dois olhos: rascunho → aprovado →
pago. Isso evita pagamento duplicado ou esquecido.

**2. Por que importa.** Em construtoras com vários departamentos, a
pessoa que lança o pedido nem sempre é a que aprova o pagamento. A
divisão em duas etapas trava esse fluxo.

**3. Onde clicar.** Menu lateral → "Financeiro" → "Aprovação em 2
etapas" (painel de gestão de custos). Para o caixa: menu lateral →
"Financeiro" → "Fluxo de Caixa".

**4. O que aparece na tela.** Painel de aprovação com três colunas
(Rascunho / Aprovado / Pago) estilo Kanban; cada cartão mostra valor,
fornecedor, obra. Tela de Fluxo de Caixa traz tabela com agregação por
banco/origem em formato BRL (R$ com vírgula decimal e ponto milhar) +
gráfico mensal.

**5. Cada elemento.**

| Elemento | Tipo | O que faz |
| --- | --- | --- |
| Cartão "Rascunho" | Card | Lançado, mas ainda não aprovado |
| Botão "Aprovar" | Verde | Move para "Aprovado" |
| Botão "Pagar" | Azul | Move para "Pago" e baixa do caixa |
| Filtro por obra | Dropdown | Restringe os cartões à obra escolhida |
| Filtro por mês | Dropdown | Restringe ao mês escolhido |

**6. Botões disponíveis.** Aprovar, Pagar, Estornar (volta um passo),
Editar, Excluir (só rascunhos).

**7. O que muda depois que você aprova ou paga.**

- Aprovar: o lançamento aparece na previsão do fluxo de caixa.
- Pagar: o lançamento sai da previsão e entra no realizado, baixando
  do banco.

**8. Notas de atenção.**

- Contas a Receber/Pagar antigas que ficaram com valor "vazio"
  continuam aparecendo sem quebrar a tela (correção introduzida na
  versão anterior).
- O formato BRL é obrigatório em todas as exibições de valor.

---

### Etapa 14 — Cotação (Mapa de Concorrência)

> *A Alfa quer comprar 5.000 blocos cerâmicos. Pediu cotação a três
> fornecedores diferentes e quer mostrar para o senhor João escolher
> qual prefere.*

**1. O que você está fazendo de verdade.** Está pedindo orçamento de
fornecedores diferentes para o mesmo material/serviço da obra e
escolhendo o mais vantajoso.

**2. Por que importa.** Sem mapa de concorrência, a escolha do
fornecedor fica no e-mail e no WhatsApp; com ele, você tem histórico
auditável e o cliente pode até participar da decisão pelo portal.

**3. Onde clicar.** Aba da obra → "Mapa de Concorrência" → botão "+
Novo mapa".

**4. O que aparece na tela.** Tabela com itens nas linhas e
fornecedores nas colunas. Cada célula recebe preço unitário e prazo de
entrega.

**5. Cada campo.**

| Campo | Tipo | Exemplo |
| --- | --- | --- |
| Item | Dropdown / texto | `Bloco cerâmico 9x19x19` |
| Quantidade | Numérico | `5000` |
| Fornecedor 1 / 2 / 3 | Texto + R$ + dias | `Cerâmica Forte / R$ 1,75 / 10 dias` |
| Observação | Texto | `Frete CIF incluído` |

**6. Botões disponíveis.**

- **Salvar** (verde).
- **Enviar para o cliente** (azul): libera o mapa no portal do
  cliente para o senhor João escolher.
- **Aprovar fornecedor** (verde escuro): efetiva a escolha e gera
  pedido de compra.

**7. O que muda depois que você aprova.** O fornecedor escolhido vira
pedido de compra na tela "Compras"; o item entra no almoxarifado
quando recebido.

**8. Notas de atenção.** O atalho de edição direta pelo admin ainda
está sub-documentado — para a versão atual, prefira sempre o caminho
"Aba da obra → Mapa de Concorrência".

---

### Etapa 15 — Portal do Cliente

**1. O que você está fazendo de verdade.** Está validando o que o
senhor João vê quando entra no link público que recebeu por e-mail.

**2. Por que importa.** É o "rosto" da Construtora Alfa para o
cliente. Se algum bloco aparecer quebrado, é uma dor de imagem.

**3. Onde acessar.** O link é gerado sozinho na aprovação (etapa 6).
Você pode copiar do "Resumo" da obra e abrir em uma janela anônima
para simular o cliente.

**4. O que aparece para o cliente.** Página única vertical com seções:
(a) Cabeçalho da obra; (b) Cronograma com dropdown (escolher entre
vários cronogramas se houver); (c) Mapa de Concorrência; (d) Histórico
de evolução; (e) Medições; (f) Painel estratégico.

**5. Cada seção.**

| Seção | O que mostra | Interação |
| --- | --- | --- |
| Cabeçalho | Nome da obra, valor de contrato, % avanço, dias decorridos | Apenas leitura |
| Cronograma | Lista hierárquica de tarefas com % executado | Dropdown para alternar entre cronogramas (planejado, executado, etc.) |
| Mapa de Concorrência | Fornecedores lado a lado | Botão "Escolher" (se você liberou para o cliente decidir) |
| Histórico de evolução | Foto + texto por dia | Apenas leitura |
| Medições | Lista de medições fechadas com PDF | Botão "Baixar PDF" por medição |
| Painel estratégico | Indicadores de saldo a receber, prazo, % avanço | Apenas leitura |

**6. Botões disponíveis para o cliente.** "Aprovar proposta" (só
aparece antes de a obra existir), "Escolher fornecedor" (no mapa),
"Baixar PDF" (na medição).

**7. O que muda quando o cliente interage.** Aprovar proposta → mesma
sequência da etapa 6 (caminho cliente). Escolher fornecedor → grava a
escolha e notifica o admin. Baixar PDF → apenas leitura.

**8. Notas de atenção.**

- O link público é único e não exige login do cliente — ele recebe
  por e-mail uma vez. Não compartilhe em grupos abertos.
- Valores são exibidos em formato BRL (R$ 1.234,56).

---

### Etapa 16 — Páginas de erro / menu superior

**1. O que você está fazendo de verdade.** Verificando que, quando
algo dá errado (um link quebrado, um clique em página que não existe),
o usuário não fica preso.

**2. Por que importa.** Antigamente, ao acessar uma URL que não
existe, a página de erro tirava o menu superior — o usuário ficava
isolado e tinha que fazer login de novo.

**3. Onde reproduzir.** Digite na barra de endereço uma URL
inexistente (ex.: `/teste-nao-existe-mesmo`).

**4. O que aparece na tela.** Página com a mensagem de erro centrada
("404 — Página não encontrada"), **com o menu lateral e o menu
superior intactos** ao redor.

**5. Cada elemento.**

| Elemento | Tipo | O que faz |
| --- | --- | --- |
| Mensagem de erro | Texto grande | Explica o erro |
| Botão "Voltar ao Dashboard" | Verde | Leva para a tela inicial |
| Menu lateral | Idem ao restante do sistema | Continua navegável |
| Menu superior | Idem ao restante do sistema | Continua navegável |

**6. Botões disponíveis.** "Voltar ao Dashboard" + qualquer item do
menu lateral funciona normalmente.

**7. O que muda depois que você clica em qualquer menu.** Sai da
página de erro sem precisar refazer login.

**8. Notas de atenção.** Se mesmo assim o menu sumir, é um problema
real — abra um ticket interno.

---

### Etapa 17 — Auditoria de cadastros duplicados / áreas legadas

**1. O que você está fazendo de verdade.** Olhando o sistema com olho
crítico para dizer ao time o que ainda está duplicado ou obsoleto.

**2. Por que importa.** Tela duplicada confunde o usuário novo. Tela
legada acumula dados que não conversam com a versão atual.

**3. Onde verificar.** Percorrer o menu lateral inteiro (de cima até
embaixo) procurando: (a) itens com sufixo "V1" ou "Legado"; (b) duas
telas que parecem cadastrar a mesma coisa; (c) itens que não abrem ou
abrem com erro.

**4. O que aparece na tela atual.** Para o tenant V2 (a Construtora
Alfa), o menu já não exibe itens legados — eles foram escondidos
automaticamente na versão anterior do sistema. Você só os veria como
superadmin.

**5. Cada item já tratado.**

| Item antigo | Item oficial novo | Status |
| --- | --- | --- |
| "Cronograma legado" | "Cronograma → Templates" | Oculto |
| Dropdown "Serviços" no header | "Catálogo" no menu lateral | Oculto |
| "Alimentação V1" | Almoxarifado V2 | Oculto |
| "Transporte V1" | Despesas Gerais V2 | Oculto |

**6. Botões disponíveis.** Não se aplica — esta etapa é só de
verificação visual.

**7. O que muda depois.** Nada — esta etapa não escreve no sistema.

**8. Notas de atenção.** Se algum dia um item legado reaparecer no
menu para um tenant V2, abra ticket interno: significa que a regra de
ocultação quebrou.

---

## FAQ — Perguntas reais que aparecem no dia a dia

**1. Lancei o RDO mas o custo de mão de obra não apareceu, e agora?**

Verifique se o RDO foi efetivamente colocado em **"Finalizado"** (não
basta salvar como rascunho). Só essa transição dispara o lançamento.
Se o RDO já está finalizado e o custo continua zerado, abra o
funcionário e confirme: para mensalistas, precisa ter "Salário"
preenchido; para diaristas, precisa ter "Valor da diária".

**2. Por que a medição não criou uma conta a receber nova?**

Porque é exatamente o esperado. Existe **uma única** conta a receber
viva por obra (`OBR-MED-#####`). A medição **atualiza** essa linha
única — ela não cria outra. Olhe na tela de Contas a Receber: o
valor da linha da sua obra aumentou.

**3. Aprovei a proposta sem revisar o cronograma — como ajustar
depois?**

A obra já foi criada com a árvore default (tudo marcado). Vá na aba
"Cronograma" da obra, exclua as tarefas que não fazem sentido (o
sistema vai pedir confirmação extra porque elas têm a etiqueta "📋 do
contrato") e/ou crie tarefas novas com "+ Nova tarefa". Mudanças não
desfazem o vínculo de medição já criado, mas excluir uma folha
remove o peso correspondente — refaça o vínculo se precisar.

**4. Cliente aprovou pelo portal antes de eu revisar o cronograma —
o que acontece?**

A obra é criada com a árvore default (tudo marcado). Para evitar
isso, na próxima vez use "Salvar pré-configuração" na tela de
revisão **antes** de mandar o link ao cliente.

**5. Tentei aprovar e apareceu "Falha ao aprovar a proposta. Nada
foi gravado." — perdi tudo?**

Não. A mensagem significa que a aprovação foi feita como uma operação
única e indivisível: como algum passo falhou (pode ser uma
subatividade que sumiu do mestre, um template excluído, etc.), o
sistema desfez tudo. Sua proposta continua em aberto. Olhe a árvore
na tela de revisão — provavelmente um nó está com aviso. Ajuste e
tente de novo.

**6. Mudei o preço de um insumo no catálogo e propostas antigas
ficaram com valor errado?**

Não ficaram. Por design, o sistema guarda uma "foto" do cálculo no
momento da gravação da proposta. Mudar o insumo agora afeta apenas
**propostas novas** ou serviços recalculados. As antigas mantêm o
custo original.

**7. Onde vejo "quanto recebi" desta obra?**

Aba "Medição comercial" da obra → coluna "Valor recebido". Ou na
tela "Financeiro → Contas a Receber" → linha `OBR-MED-#####` da
obra → campo "Valor recebido".

**8. Cadastrei o template do cronograma, mas a aprovação não criou
tarefas para um serviço específico — por quê?**

Três motivos possíveis: (a) o serviço **não tem o "Template padrão"
preenchido** (volte na etapa 3 e configure); (b) você **desmarcou
tudo** desse serviço na tela de revisão; (c) o item da proposta foi
digitado livre, sem escolher o serviço do catálogo. O sistema mostra
um aviso na tela de revisão para cada um desses casos.

**9. Como faço a Alfa importar 30 funcionários de uma vez?**

Etapa 4 — menu "Importar por Planilha", baixe o template oficial,
preencha em casa, suba o arquivo, confira a pré-visualização e
"Confirmar importação". Linhas com erro vêm destacadas em vermelho.

**10. Excluí uma tarefa "📋 do contrato" sem querer. Quebrei o
sistema?**

Não. A medição daquele serviço pode ficar com peso desbalanceado
(menos folhas, peso da folha excluída se redistribui automaticamente
nas próximas medições). Se quiser voltar tudo, reaprove a proposta —
mas atenção: a regra de não duplicação só vale para o que ainda
existe; tarefas excluídas **não** são recriadas pela reaprovação.
Para forçar recriação, ajuste manualmente o cronograma da obra.

---

## Anexo técnico (opcional, para o time de TI)

> Este bloco é um cartão de referência rápida para administradores
> técnicos do sistema; **não é necessário ler para usar o sistema**.

### Eventos automáticos do sistema

| Quando acontece | O que o sistema faz sozinho |
| --- | --- |
| Você clica "Confirmar aprovação e gerar cronograma" | Cria Obra (`OBR####`), `token_cliente`, `valor_contrato`, abre o portal do cliente, cria itens de medição, cria o cronograma de 3 níveis, lança contábil. **Não cria conta a receber.** |
| RDO vai para "Finalizado" | Cria custos automáticos de mão de obra; recalcula a medição; atualiza a conta a receber única da obra. |
| Você gera/fecha medição quinzenal | Recalcula a conta a receber única da obra (UPSERT — atualiza, não duplica). |

### Conta a receber única

- Uma e apenas uma por obra: `origem_tipo='OBRA_MEDICAO'`,
  `numero_documento='OBR-MED-#####'`.
- `valor_original` = valor medido acumulado.
- `saldo = max(0, valor_medido - valor_recebido)`.
- `status` flui PENDENTE → PARCIAL → QUITADA.

### Métricas de funcionários

| Modo | Mão de obra |
| --- | --- |
| `salario` | `horas × valor_hora + HE × valor_hora × 1.5` |
| `diaria` | `valor_diaria × dias_pagos + (HE / 8) × valor_diaria × 1.5` |

**Custo total** = MO + VA × dias_pagos + VT × dias_pagos +
Alimentação real + Reembolsos aprovados + Almoxarifado em posse.

### Cobertura de teste do ciclo (referência para o time técnico)

- `tests/test_cronograma_automatico_aprovacao.py` — 33/33 PASS
  (cobre cronograma automático na aprovação ponta a ponta).
- `tests/test_ciclo_proposta_obra_medido_cr.py` — 30/30 PASS (cobre
  o ciclo financeiro pós-aprovação, regra da CR única).
- `tests/test_e2e_orcamento_proposta.py` — 36/36 PASS (cobre catálogo
  paramétrico → aprovação cliente).
- `tests/test_e2e_metricas_funcionario.py` — 27/27 PASS (cobre
  v1+v2 de métricas).

---

# Anexo A — Modo Agente (operação dirigida via dataset Alfa)

> **Propósito.** Permitir que um operador (humano ou agente
> automatizado) reproduza o ciclo de ponta a ponta deste manual a
> partir de um estado conhecido, sem intervir no banco. O dataset
> "Construtora Alfa" é semeado por `scripts/seed_demo_alfa.py` e expõe
> URL/método/seletor verificáveis em cada uma das 17 etapas.

## A.1 — Como rodar o seed

### Em desenvolvimento (Replit / local)
```bash
# Plantar (no-op se admin Alfa já existe)
python3 scripts/seed_demo_alfa.py

# Forçar replantio (apaga e refaz)
python3 scripts/seed_demo_alfa.py --reset
```
O script imprime, no final, um bloco `DEMO PRONTA` com URL de login,
credenciais e os IDs principais (admin, cliente, funcionários, serviços,
templates, proposta, obra, medição, conta a receber).

### Em produção (acionamento consciente)
Auto-seed em produção está **desligado por padrão** desde a Task #108.
Para acionar manualmente:
```bash
SIGE_ALLOW_PROD_SEED=1 \
  python3 /app/scripts/seed_demo_alfa.py --ambiente prod
```
Se o admin Alfa já existir e `--reset` não for passado, o script aborta
com **exit 2** — ato consciente é exigido. Para re-habilitar o auto-seed
no entrypoint Easypanel (NÃO recomendado), defina **as duas** variáveis:
`SIGE_ENABLE_DEMO_SEED=true` **e** `SIGE_ALLOW_PROD_SEED=1`.

## A.2 — Credenciais publicadas (Construtora Alfa)

| Campo               | Valor                                  |
|---------------------|----------------------------------------|
| URL de login (dev)  | `http://localhost:5000/login`          |
| URL de login (prod) | `https://construtoraalfa.estruturasdoval.com.br/login` |
| E-mail              | `admin@construtoraalfa.com.br`         |
| Senha               | `Alfa@2026`                            |
| Cliente PF          | João da Silva — CPF `123.456.789-09`   |
| Funcionário 1       | Carlos Pereira — mensalista R$ 2.800   |
| Funcionário 2       | Pedro Souza   — diarista  R$ 180/dia   |
| Proposta            | nº `001.26` (4 itens, R$ 62.250,00)    |
| Obra                | `OBR-2026-001` — Residencial Bela Vista|

## A.3 — URL por etapa (17 etapas do ciclo)

> Os IDs `<proposta_id>`, `<obra_id>`, `<medicao_id>` são impressos no
> bloco `DEMO PRONTA` no fim da execução do seed. Em todas as rotas,
> o agente deve estar logado com a sessão do admin Alfa.

| # | Etapa                          | Método | URL                                              | DOM esperado (seletor)                              |
|---|--------------------------------|--------|--------------------------------------------------|------------------------------------------------------|
| 1 | Login                          | GET / POST | `/login`                                     | sucesso → redireciona para `/dashboard`             |
| 2 | Dashboard inicial              | GET    | `/dashboard`                                     | `h1` com "Dashboard"; cards de KPI (≥4)             |
| 3 | Lista de funcionários          | GET    | `/funcionarios`                                  | linhas de funcionário ≥ 2 (Carlos + Pedro)          |
| 4 | Cadastro de funcionário        | POST   | `/funcionarios` (modal "Novo Funcionário" na própria página) | `select[name=tipo_remuneracao]` no modal; toast de sucesso |
| 5 | Catálogo de serviços           | GET    | `/catalogo/servicos`                             | 3 linhas de serviço (Alvenaria / Contrapiso / Mobilização) |
| 6 | Detalhe de serviço + composição| GET    | `/catalogo/servicos/<servico_id>/composicao`     | tabela de composição visível; bloco "Template padrão" preenchido para Alvenaria/Contrapiso |
| 7 | Lista de propostas             | GET    | `/propostas/`                                    | linha com nº `001.26` e badge `Aprovada`            |
| 8 | Nova proposta                  | GET / POST | `GET /propostas/nova` ; `POST /propostas/criar` | form de proposta; após salvar, redireciona para o detalhe |
| 9 | Detalhe da proposta            | GET    | `/propostas/<proposta_id>`                       | status visível = `Aprovada`; 4 itens listados       |
| 10| Revisão do cronograma da proposta | GET | `/propostas/<proposta_id>/cronograma-revisar`    | árvore com checkboxes (≥9 nós) renderizada         |
| 11| Aprovação da proposta          | POST   | `/propostas/aprovar/<proposta_id>`               | redireciona para `/obras/<obra_id>`                 |
| 12| Detalhe da obra                | GET    | `/obras/<obra_id>`                               | título com "Residencial Bela Vista"                 |
| 13| Cronograma da obra (Gantt)     | GET    | `/cronograma/obra/<obra_id>`                     | barras Gantt ≥9; árvore Serviço→Grupo→Subatividade  |
| 14| Lista de RDOs                  | GET    | `/rdo`                                           | linhas de RDO finalizado ≥ 2                        |
| 15| Novo RDO / Salvar              | GET / POST | `GET /rdo/novo` ; `POST /salvar-rdo-flexivel` (form `#formNovoRDO` enctype `multipart/form-data`) | toast de sucesso; novo RDO aparece em `/rdo` (status pode ficar `Rascunho` até finalização explícita via POST `/rdo/<rdo_id>/finalizar`) |
| 16| Tela de medições + aprovação   | GET / POST | `GET /obras/<obra_id>/medicao` (alias `/medicao/obra/<obra_id>`); `POST /obras/<obra_id>/medicao/fechar` (gerar) e `/obras/<obra_id>/medicao/<medicao_id>/aprovar` (aprovar) | medição #001 visível e com status `APROVADO` |
| 17| Contas a Receber               | GET    | `/financeiro/contas-receber`                     | linha `OBR-MED-<obra_id>` com valor R$ 32.250,00    |

## A.4 — Mapas "Rótulo → name/id → tipo" para os formulários centrais

### A.4.1 — Funcionário (template real `templates/funcionarios.html` — modal `#funcionarioModal`, form `#funcionarioForm`, action `POST /funcionarios`, `enctype=multipart/form-data`)

| Rótulo na tela                | `name` / `id`              | Tipo HTML            | Observações                                  |
|-------------------------------|----------------------------|----------------------|----------------------------------------------|
| Nome completo                 | `nome`                     | `text` (required)    |                                              |
| CPF                           | `cpf`                      | `text` (required)    | mask 999.999.999-99                          |
| Foto                          | `foto`                     | `file`               | jpg/png, opcional                            |
| RG                            | `rg`                       | `text`               |                                              |
| Data de nascimento            | `data_nascimento`          | `date`               |                                              |
| Endereço                      | `endereco`                 | `textarea`           |                                              |
| Telefone                      | `telefone`                 | `text`               |                                              |
| E-mail                        | `email`                    | `email`              |                                              |
| Data de admissão              | `data_admissao`            | `date`               |                                              |
| **Tipo de remuneração**       | `tipo_remuneracao`         | `select`             | opções: `salario`, `diaria`                  |
| Salário fixo (mensalistas)    | `salario`                  | `number step=0.01`   | visível quando `tipo_remuneracao=salario`    |
| Valor da diária (diaristas)   | `valor_diaria`             | `number step=0.01`   | visível quando `tipo_remuneracao=diaria`     |
| Função                        | `funcao_id`                | `select`             | FK funcao                                    |
| Horário de trabalho           | `horario_trabalho_id`      | `select`             | FK horario_trabalho                          |
| Ativo                         | `ativo`                    | `checkbox`           | default checked                              |

> Observação: `valor_va`, `valor_vt` e `chave_pix` existem como
> colunas na tabela `funcionario` e são exibidos nas listas/cards, mas
> **não estão no modal** — para preenchê-los o agente deve usar
> `services/funcionario_service.py` ou um update direto pós-criação.

### A.4.2 — Serviço (template real `templates/servicos/editar.html`, mesmo form usado em "novo" e "editar" — endpoint `POST /servicos` / `POST /servicos/<id>/atualizar` via `crud_servicos_completo.py`)

| Rótulo                         | `name`                      | Tipo            |
|--------------------------------|-----------------------------|-----------------|
| Nome                           | `nome`                      | `text` required |
| Categoria                      | `categoria`                 | `select`        |
| Descrição                      | `descricao`                 | `textarea`      |
| **Template padrão (cronograma)** | `template_padrao_id`      | `select`        |
| Subatividades (linha repetida) | `subatividades[]`           | `text`          |

> Observação: `unidade_medida`, `custo_unitario`, `imposto_pct`,
> `margem_lucro_pct` e `preco_venda_unitario` existem como colunas em
> `servico` (consumidas pelo cálculo paramétrico em
> `services/orcamento_parametrico.py`), porém **não fazem parte do form
> real**; são populadas via composição (insumo × coeficiente) no
> template `templates/catalogo/composicao_servico.html`.

### A.4.3 — Proposta (template real `templates/propostas/nova_proposta.html` — form `#formNovaProposta`, action `POST /propostas/criar`)

| Rótulo                       | `name`                       | Tipo                |
|------------------------------|------------------------------|---------------------|
| Cliente — nome               | `cliente_nome`               | `text` required     |
| Cliente — e-mail             | `cliente_email`              | `email`             |
| Cliente — telefone           | `cliente_telefone`           | `text`              |
| Cliente — CPF/CNPJ           | `cliente_cpf_cnpj`           | `text`              |
| Número da proposta           | `numero_proposta`            | `text` required     |
| Assunto                      | `assunto`                    | `text`              |
| Objeto / descrição           | `objeto`                     | `textarea`          |
| Endereço da obra             | `endereco_obra`              | `textarea`          |
| Área total (m²)              | `area_total_m2`              | `number step=0.01`  |
| Prazo de execução (dias)     | `prazo_execucao`             | `number`            |
| Item — serviço (FK oculto)   | `item_servico_id`            | `hidden` (linha)    |
| Item — template (FK oculto)  | `item_template_id`           | `hidden` (linha)    |
| Item — descrição             | `item_descricao`             | `text` (linha)      |
| Item — quantidade            | `item_quantidade`            | `number step=0.01`  |
| Item — unidade               | `item_unidade`               | `select` (linha)    |
| Item — preço unitário        | `item_preco`                 | `number step=0.01`  |
| Seção especificações         | `secao_especificacoes`       | `textarea`          |
| Seção materiais              | `secao_materiais`            | `textarea`          |
| Seção fabricação             | `secao_fabricacao`           | `textarea`          |
| Seção logística              | `secao_logistica`            | `textarea`          |
| Seção montagem               | `secao_montagem`             | `textarea`          |
| Seção qualidade              | `secao_qualidade`            | `textarea`          |
| Seção segurança              | `secao_seguranca`            | `textarea`          |
| Seção assistência técnica    | `secao_assistencia`          | `textarea`          |
| Seção considerações          | `secao_consideracoes`        | `textarea`          |
| % Nota fiscal                | `percentual_nota_fiscal`     | `number`            |
| Valor total                  | `valor_total`                | `number step=0.01`  |
| Itens (JSON serializado)     | `servicos_json`              | `hidden`            |

> Observação: o template alternativo `templates/propostas/editar.html`
> (rota `GET/POST /propostas/editar/<id>`) usa nomes diferentes
> (`numero`, `titulo`, `descricao`, `cliente_endereco`,
> `prazo_entrega_dias`, `condicoes_pagamento`) — verifique qual
> template a rota acessada renderiza antes de mapear.

### A.4.4 — Cronograma (revisão pré-aprovação)

| Rótulo                      | `name` / `id`                                | Tipo       |
|-----------------------------|----------------------------------------------|------------|
| Marcar / desmarcar nó       | `marcado_<proposta_item_id>_<no_id>`         | `checkbox` |
| Horas estimadas (override)  | `horas_<proposta_item_id>_<no_id>`           | `number`   |
| Duração em dias (override)  | `duracao_<proposta_item_id>_<no_id>`         | `number`   |
| Confirmar e aprovar         | `button[type=submit][name=acao][value=aprovar]` | `submit` |

### A.4.5 — RDO (template real `templates/rdo/novo.html` — form `#formNovoRDO`, action `POST /salvar-rdo-flexivel`, `enctype=multipart/form-data`)

> O RDO usa um fluxo flexível: a tela é populada via JavaScript a partir
> das tarefas do cronograma da obra selecionada, e os campos de mão de
> obra são gerados dinamicamente por subatividade/funcionário. Os
> seletores estáveis para automação são os listados abaixo.

| Rótulo / função                        | `name` / `id`                                  | Tipo                |
|----------------------------------------|------------------------------------------------|---------------------|
| Funcionário logado (oculto)            | `funcionario_id`                               | `hidden`            |
| Admin (oculto)                         | `admin_id_form`                                | `hidden`            |
| Obra                                   | `obra_id` (`select#obra_id`)                   | `select`            |
| Data do relatório                      | `data_relatorio` (`input#data_relatorio`)      | `date`              |
| Tarefas do cronograma (gerado por JS)  | `cronograma_tarefa_<tarefa_id>`                | `checkbox`/`number` |
| Tarefas para entrega (multi-select)    | `entrega_tarefa_ids[]`                         | `select multiple`   |
| Horas por funcionário × subatividade   | `func_<subId>_<funcId>_horas`                  | `number step=0.5`   |
| Fotos (câmera)                         | `fotos[]` (`#fileInputNovoCam`)                | `file multiple`     |
| Fotos (galeria)                        | `fotos[]` (`#fileInputNovoGal`)                | `file multiple`     |
| Legenda da foto                        | `legenda_foto_<i>`                             | `text`              |

Para **finalizar um RDO já salvo** (mudar `status` para `Finalizado`),
o agente faz `POST /rdo/<rdo_id>/finalizar` (sem corpo).

### A.4.6 — Medição quinzenal (template real `templates/medicao/gestao_itens.html`)

> No template real, cada ação está num `<form method="post" action="...">`
> dedicado, com botões de envio simples (`type="submit"`). Para automação,
> selecione o formulário pela `action` e clique no submit dentro dele.

| Rótulo / ação                     | Localização (selector)                                                         | Endpoint Flask                          |
|-----------------------------------|--------------------------------------------------------------------------------|------------------------------------------|
| Período — início (gerar)          | `form[action*="/medicao/fechar"] input[name=periodo_inicio]`                   | POST `/obras/<obra_id>/medicao/fechar` (endpoint `medicao.gerar_medicao`) |
| Período — fim (gerar)             | `form[action*="/medicao/fechar"] input[name=periodo_fim]`                      | idem                                    |
| Observações (gerar)               | `form[action*="/medicao/fechar"] textarea[name=observacoes]`                   | idem                                    |
| Botão "Gerar medição"             | `form[action*="/medicao/fechar"] button[type=submit]`                          | idem                                    |
| Botão "Aprovar medição #N"        | `form[action*="/medicao/<medicao_id>/aprovar"] button[type=submit]`            | POST `/obras/<obra_id>/medicao/<medicao_id>/aprovar` (endpoint `medicao.fechar`) |
| Configuração da obra (data inicial / valor de entrada) | `form[action*="/medicao/config"]` com `data_inicio_medicao`, `valor_entrada`, `data_entrada` | POST `/obras/<obra_id>/medicao/config` (endpoint `medicao.config_obra_medicao`) |
| Novo item de medição (modal)      | `form#formNovoItemMedicao` com `servico_id`, `nome`, `quantidade`, `valor_comercial` | POST `/obras/<obra_id>/medicao/itens` (endpoint `medicao.criar_item`) |

## A.5 — Critério de aceite verificável por etapa

Cada etapa pode ser validada por **uma consulta SQL** (no banco do
tenant Alfa) **ou** por **um seletor CSS** (em testes E2E Playwright).
A coluna `admin_id` deve sempre ser filtrada pelo ID do admin Alfa
impresso no bloco `DEMO PRONTA`.

| # | Etapa                  | Critério SQL (preferencial)                                         | Seletor CSS / DOM (alternativa E2E)                  |
|---|------------------------|---------------------------------------------------------------------|------------------------------------------------------|
| 1 | Login                  | `SELECT 1 FROM usuario WHERE email='admin@construtoraalfa.com.br'`  | URL final = `/dashboard`                             |
| 2 | Dashboard              | n/a                                                                 | cards de KPI count ≥ 4                               |
| 3 | Lista funcionários     | `SELECT count(*) FROM funcionario WHERE admin_id=:a` ≥ 2            | linhas de funcionário ≥ 2                            |
| 4 | Cadastro funcionário   | `SELECT tipo_remuneracao,valor_diaria FROM funcionario WHERE cpf='900.901.002-02'` retorna `('diaria',180.00)` | toast "Funcionário cadastrado" após POST `/funcionarios` |
| 5 | Catálogo serviços      | `SELECT count(*) FROM servico WHERE admin_id=:a` = 3                | tabela com 3 linhas de serviço                       |
| 6 | Serviço com template   | `SELECT template_padrao_id IS NOT NULL FROM servico WHERE nome='Alvenaria de bloco cerâmico' AND admin_id=:a` retorna `t` | em `/catalogo/servicos/<id>/composicao`, bloco "Template padrão" preenchido |
| 7 | Lista propostas        | `SELECT numero,status FROM propostas_comerciais WHERE admin_id=:a`  | linha com `001.26` + badge `Aprovada`                |
| 8 | Itens da proposta      | `SELECT count(*) FROM proposta_itens WHERE proposta_id=:p` = 4      | tabela de itens da proposta com 4 linhas             |
| 9 | Detalhe proposta       | `SELECT status FROM propostas_comerciais WHERE id=:p` = `'aprovada'`| status visível "Aprovada"                            |
|10 | Revisão cronograma     | `SELECT cronograma_default_json IS NOT NULL FROM propostas_comerciais WHERE id=:p` retorna `t` | árvore renderizada com checkboxes  |
|11 | Aprovação              | `SELECT id FROM obra WHERE proposta_origem_id=:p` retorna 1 linha   | POST `/propostas/aprovar/<p>` redireciona para `/obras/<obra_id>` |
|12 | Detalhe obra           | `SELECT codigo FROM obra WHERE id=:o` = `'OBR-2026-001'`            | título "Residencial Bela Vista"                      |
|13 | Cronograma materializado | `SELECT count(*) FROM tarefa_cronograma WHERE obra_id=:o AND admin_id=:a` ≥ 9 | barras Gantt count ≥ 9                  |
|14 | RDOs finalizados       | `SELECT count(*) FROM rdo WHERE obra_id=:o AND status='Finalizado'` = 2 | 2 linhas com status "Finalizado"                |
|15 | RDO mão de obra        | `SELECT count(DISTINCT funcionario_id) FROM rdo_mao_obra rmo JOIN rdo r ON rmo.rdo_id=r.id WHERE r.obra_id=:o` = 2 | toast `RDO finalizado`         |
|16 | Medição aprovada       | `SELECT status,numero FROM medicao_obra WHERE obra_id=:o` retorna `('APROVADO',1)` | em `/obras/<obra_id>/medicao`, medição #001 exibida com badge `APROVADO` |
|17 | Conta a Receber        | `SELECT valor_original,status FROM conta_receber WHERE origem_tipo='OBRA_MEDICAO' AND origem_id=:o` retorna `(32250.00,'PENDENTE')` | linha `OBR-MED-<obra_id>` valor `R$ 32.250,00` |

## A.6 — Ordem recomendada para um agente E2E

1. Rodar `python3 scripts/seed_demo_alfa.py --reset` para garantir
   estado conhecido.
2. Capturar do stdout os IDs (`<admin_id>`, `<proposta_id>`,
   `<obra_id>`, `<medicao_id>`).
3. Executar a etapa 1 (login) e validar o critério da linha 1.
4. Para cada etapa N (2..17), abrir a URL listada em A.3 e validar
   o critério da linha N em A.5. Se o critério falhar, capturar
   screenshot e logs e parar.
5. Ao final, conferir que `SELECT count(*) FROM conta_receber WHERE
   origem_tipo='OBRA_MEDICAO' AND origem_id=:o` é exatamente **1**
   (regra da CR única do ciclo).
