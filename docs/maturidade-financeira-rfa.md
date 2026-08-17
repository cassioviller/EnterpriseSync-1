# Maturidade financeira — o SIGE medido contra o método RFA

> **Data:** 2026-08-17.
> **Origem:** o arquivo `regras-financeiro.pdf`, deixado na raiz do projeto.
> **O que este documento faz:** mede o que o SIGE oferece hoje contra a régua dos cinco
> passos do método, aponta o degrau em que ele está, e propõe um plano de ação.

Marcas de procedência, as mesmas do `ESTADO-ATUAL.md`: 📖 lido no código com
`caminho:linha` conferido · 🔬 medido · ⚠️ ressalva · 🔴 aberto.

---

## ⚠️ Leia isto antes: o arquivo não contém regras financeiras

O nome sugere uma especificação. Não é.

`regras-financeiro.pdf` é um **ebook institucional** de 10 páginas — *"O Básico bem
Feito"*, de Giovanni Colacicco / eConexão — que apresenta o **Método RFA** (Raciocínio
Financeiro Aplicado): uma trilha de 50 passos agrupada em 5 blocos, encerrando num QR code
para um diagnóstico gratuito de maturidade financeira (5 blocos, 31 grupos, 155 perguntas).

**Não há nele uma única regra de negócio, fórmula, tabela de parâmetros ou enunciado
implementável.** Quem for procurar ali o que codificar não vai achar — e é melhor saber
disso antes de abrir uma spec em cima dele.

O que ele **é** de útil: uma régua de maturidade, construída por fora e sem conhecer este
código. Medir o SIGE contra uma régua externa tem valor justamente por isso — ela não
herda os nossos pontos cegos.

> 🔴 **A pergunta que só o Cássio responde:** este PDF chegou aqui porque a Veks
> **contratou ou vai contratar** essa consultoria? Se sim, o que vale é o diagnóstico que
> **eles** fizerem sobre a operação real, e este documento vira no máximo um preparo. Se
> foi leitura avulsa, o que segue é uma análise nossa a partir de material institucional —
> e deve ser lida com esse desconto.

---

## O método, fielmente resumido

Cinco passos, cada um pressupondo o anterior:

| # | Passo | O que o método pede |
|---|---|---|
| 1 | **Tesouraria** | Caixa, Fluxo de Caixa e **DFC** — a demonstração separando Operação, Investimentos e Financiamentos. *"Saldo em conta mostra quanto dinheiro existe hoje; gestão de caixa mostra por que ele existe e por quanto tempo permanecerá."* |
| 2 | **Contabilidade de Custos** | Gastos Fixos, Gastos Variáveis, **Margem de Contribuição** e **DRE Gerencial**. *"Eficiência não é vender mais. É transformar receita em margem e margem em resultado."* |
| 3 | **Contabilidade Gerencial** | Patrimônio, **Balanço Patrimonial**, **Indicadores e Ciclos** (giro, prazos, equilíbrio) |
| 4 | **Controladoria** | Orçamento (da empresa), Cultura Financeira, Método de Gestão — *dados → análise → decisão → ação → resultados* |
| 5 | **Finanças Estratégicas** | Business Plan, Estratégia Financeira, Governança e Valor |

---

## O mapa — os cinco passos contra o código de hoje

### Passo 1 · Tesouraria — 🟡 metade

**Tem:** fluxo de caixa com tela e CRUD (📖 `financeiro_views.py:1036`, `:1099`, `:1160`),
bancos com `saldo_atual` e o débito rastreável na baixa (`conta_pagar.banco_id`, migração
280), contas a pagar e a receber com baixa, estorno e projeção por vencimento.

**Falta o DFC.** 🔬 Varredura no repositório: **nenhuma ocorrência** de atividades
operacionais / de investimento / de financiamento em código vivo. O sistema sabe *quanto*
entrou e saiu; não sabe dizer *de que natureza* foi o caixa — que é a pergunta inteira do
Passo 1.

### Passo 2 · Contabilidade de Custos — 🟡 forte por obra, ausente por empresa

Esta é a linha que mais separa o que o SIGE é do que o método pede.

**Tem, e é o ponto mais forte do produto:** custo **por obra**, com centro de custo
obrigatório em 10 módulos (Fase 4), `gestao_custo_pai`/`filho`, fonte única do custo
orçado (`services/custo_orcado.py`), EVM composto (BAC/PV/AC/EV, p10) e DRE com linha
residual que torna omissão silenciosa impossível (Fase 0.6/D3).

**Não tem, e são as três peças centrais do passo:**

- 🔬 **gasto fixo × gasto variável — zero ocorrências** no repositório;
- 🔬 **margem de contribuição — zero ocorrências**;
- o "DRE Gerencial" do método (o que sobra depois dos variáveis) não existe; o que existe é
  o DRE contábil por natureza de conta.

📖 `PlanoContas` (`models.py:3234`) tem `tipo_conta`, `natureza`, `nivel`,
`conta_pai_codigo`, `aceita_lancamento`, `ativo` — **e nenhuma coluna que diga se o gasto é
fixo ou variável**. Sem essa classificação, margem de contribuição não é calculável a
partir do que está gravado.

### Passo 3 · Contabilidade Gerencial — 🟡 as demonstrações existem, os indicadores não

**Tem um módulo contábil de verdade**, e isso costuma surpreender quem só conhece o lado de
obra: 📖 `contabilidade_views.py` expõe dashboard, plano de contas, lançamentos com CRUD e
estorno, **balancete**, **razão por conta**, **DRE**, **balanço patrimonial**, SPED e
exportação em PDF e Excel.

**Falta a leitura.** 🔬 **Zero ocorrências** de liquidez, endividamento, ROE ou giro do
ativo. O balanço é publicado e não é *lido* — nenhum indicador é derivado dele, e "Ciclos"
(prazo médio de recebimento, de pagamento, ciclo financeiro) não existe em lugar nenhum.

### Passo 4 · Controladoria — 🔴 só o pedaço de obra

Orçamento **de obra** existe e é sofisticado (baseline congelada, EVM, curva). **Orçamento
empresarial não existe** — 🔬 zero ocorrências. Não há previsto × realizado no nível da
empresa, que é o que o passo pede.

### Passo 5 · Finanças Estratégicas — 🔴 nada

Business plan, estratégia de capital, perpetuidade. Nada disso existe, e nada disso foi
pedido por cliente nenhum até hoje.

---

## O diagnóstico, em uma frase

**O SIGE é um ERP de obra que cresceu para dentro da contabilidade — não um sistema de
gestão financeira da empresa.** Ele responde muito bem *"quanto custou esta obra"* e mal
*"como está a empresa"*. Na régua do RFA, isso o coloca **entre os passos 2 e 3**: tem as
demonstrações do passo 3 publicadas, mas não tem as ferramentas de decisão do passo 2.

É uma posição melhor do que parece. O que falta não é fundação — é leitura sobre uma
fundação que já existe.

---

## 🔴 O que trava a subida, e é uma coisa só

Os passos 2 e 3 assentam sobre um plano de contas coerente. E ele não é coerente.

📖 Conferido em 17/08, ainda vivo:

| Conflito | Onde |
|---|---|
| `5.1.01` é **"MÃO DE OBRA"** | `financeiro_seeds.py:71` |
| `5.1.01` é **"Materiais Diretos"** | `contabilidade_utils.py:84` |
| "Salários" é lançado em `5.1.01.001` | `event_manager.py:1505` |
| "Salários" é lançado em `6.1.01.001` | `contabilidade_utils.py:229` |

São **quatro planos de contas concorrentes**, e dois deles dão significados **opostos ao
mesmo código**. O diagnóstico é de 21/07 (achado nº 2 da Fase 0.6/D3) e a unificação foi
adiada para a **Fase 8** desde então.

> 📖 **O próprio código do DRE já sabe disso, e é a confirmação mais forte que existe.**
> `contabilidade_utils.py:536-540` classifica em linhas do DRE apenas os prefixos *"cujo
> significado é o MESMO nos planos que os definem"* — e comenta, na linha ao lado, que
> `6.1.02` fica **deliberadamente fora** por isso. Ou seja: a limitação já foi encontrada
> por quem escreveu o DRE, contornada com honestidade (o residual `outras`), e registrada
> como dívida da Fase 8.

**Consequência para qualquer coisa do RFA:** uma margem de contribuição ou um indicador
construídos sobre isso somam coisas diferentes com o mesmo nome, e erram sem avisar.
**Nenhum indicador vale mais que o plano de contas que o alimenta.**

---

## Plano de ação

### A convergência que dá confiança na ordem

O plano aprovado já tem a **Fase 8 — Financeiro avançado + exportação Domínio**, cujo
escopo original é justamente unificar os quatro planos de contas. Um método construído por
fora, sem conhecer este código, aponta para o mesmo degrau. **A ordem não muda; o escopo
cresce um pouco.**

### Fase 8, como eu a proporia agora

| # | Entrega | Por quê, e o que custa |
|---|---|---|
| **8.1** | **Unificar os quatro planos de contas** (escopo original) | Pré-requisito de tudo abaixo. É o mais caro e o único que mexe em dado histórico |
| **8.2** | **Classificar cada conta como fixa ou variável** | Uma coluna em `plano_contas` + a classificação. Destrava margem de contribuição **e** DRE gerencial de uma vez. Barato **depois** da 8.1, impossível antes |
| **8.3** | **DFC pelos três grupos** | Um mapa conta → atividade (operação/investimento/financiamento). É **leitura**: os lançamentos já existem, nada novo é gravado |
| **8.4** | **Painel de indicadores e ciclos** | Liquidez, endividamento, margem, giro, prazos médios. Derivados do balanço que **já é publicado** |
| **8.5** | Exportação Domínio (escopo original) | Onde já estava |

**8.2 a 8.4 são leitura sobre dado que já existe.** Nenhuma delas cria um caminho de
escrita novo, e por isso nenhuma delas carrega o risco que as fases do ciclo de compras
carregaram. A 8.1 é a que precisa de cuidado — e de decisão humana.

### O que fica de fora, e por quê

**Passos 4 e 5 do RFA (orçamento empresarial, business plan, perpetuidade).** São **produto
novo**, não dívida técnica, e nenhum cliente pediu. Colocá-los na fila agora seria trocar
o conserto de uma fundação que range por um andar a mais.

> ⚠️ **E uma ressalva sobre o próprio exercício.** Este documento mede o SIGE contra um
> material institucional, não contra a operação da Veks. As lacunas apontadas são reais no
> código — todas conferidas com `caminho:linha` — mas **se elas importam** para quem usa o
> sistema é outra pergunta, e ela não se responde lendo código. É o mesmo alerta que o spec
> das alçadas carrega: *"quem for medir se a fase acertou tem que medir contra a operação
> real, não contra o spec"*.

---

## As decisões que este documento não pode tomar

1. 🔴 **A consultoria foi contratada?** Se sim, o diagnóstico deles substitui este mapa.
2. 🔴 **A Fase 8 sobe na fila?** Hoje o ciclo de compras está na frente, com as Fases 4
   (régua de 9 etapas) e 5 (relatórios) sem spec — e com **nenhuma flag ligada em tenant
   real**. Colocar a Fase 8 antes disso é escolher fundação em vez de acabamento, e é uma
   escolha legítima; só não é gratuita.
3. 🔴 **A classificação fixo × variável é por tenant ou padrão do sistema?** Empresas
   classificam diferente o mesmo gasto. Recomendação: **coluna por tenant, com um padrão
   semeado** — mesmo desenho de `FaixaAlcada`, pelo mesmo motivo (número que é regra de
   negócio não entra em `if`).
