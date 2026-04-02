# Manual do Módulo Financeiro — SIGE v9.0

> Tudo que envolve dinheiro: contas a pagar, contas a receber, bancos e fluxo de caixa.

---

## 1. Acessar o Módulo Financeiro

No menu superior, clique em **Financeiro**.  
Um dropdown aparece com as opções:

- Dashboard Financeiro
- Fluxo de Caixa
- Contas a Pagar
- Contas a Receber
- Bancos
- Folha de Pagamento
- Contabilidade
- Gestão de Custos

---

## 2. Cadastrar um Banco / Conta

Antes de registrar pagamentos, cadastre as contas bancárias da empresa.

**Caminho:** Financeiro → Bancos → botão **Novo Banco**

**Preencha:**
- Nome do Banco (ex: Banco do Brasil, Caixa, Nubank, Caixa Física)
- Agência e Conta (opcional)
- Tipo de Conta: Corrente, Poupança, Investimento ou Caixa Físico
- Saldo Inicial: valor atual nessa conta

Clique em **Cadastrar Banco**.

> O saldo dos bancos cadastrados forma o **Saldo Inicial** do Fluxo de Caixa.

---

## 3. Registrar uma Conta a Pagar

Use para registrar despesas futuras: fornecedores, aluguel, boletos, notas fiscais, etc.

**Caminho:** Financeiro → Contas a Pagar → botão **Nova Conta a Pagar**

**Preencha:**
- Descrição (obrigatório) — ex: "NF 1234 – Cimento"
- Valor (obrigatório)
- Vencimento (obrigatório)
- Fornecedor (opcional) — selecione da lista se já cadastrado
- Obra Vinculada (opcional) — vincula o custo a uma obra
- Nº Documento (opcional) — número da NF, boleto, etc.
- Conta Contábil (opcional) — se usar contabilidade de partidas dobradas

Clique em **Salvar Conta a Pagar**.

**Resultado automático:** a conta aparece imediatamente em **Saídas Previstas** no Fluxo de Caixa.

---

## 4. Dar Baixa em uma Conta a Pagar (registrar pagamento)

**Caminho:** Financeiro → Contas a Pagar → localizar a conta → botão **Pagar** (ícone de check)

**Preencha:**
- Valor Pago (preenche automaticamente com o saldo restante)
- Data do Pagamento
- Forma de Pagamento: PIX, TED, Boleto, Cartão, Dinheiro, Cheque
- Banco (opcional) — se informado, o saldo desse banco é debitado automaticamente

Clique em **Confirmar Pagamento**.

**O que muda automaticamente:**
- Status da conta → **PAGO** (quitação total) ou **PARCIAL** (quitação parcial)
- A conta **sai das Saídas Previstas** no Fluxo de Caixa
- O saldo do banco selecionado **diminui** automaticamente
- Se havia conta contábil vinculada → **lançamento contábil criado** (partida dobrada)

---

## 5. Registrar uma Conta a Receber

Use para registrar receitas futuras: medições de obra, serviços prestados, contratos, etc.

**Caminho:** Financeiro → Contas a Receber → botão **Nova Conta a Receber**

**Preencha:**
- Descrição (obrigatório) — ex: "Medição #3 – Obra Vila Nova"
- Cliente / Devedor (obrigatório) — nome da empresa ou pessoa
- CPF / CNPJ (opcional)
- Valor (obrigatório)
- Vencimento (obrigatório)
- Obra Vinculada (opcional)
- Nº Documento (opcional)
- Conta Contábil (opcional)

Clique em **Salvar Conta a Receber**.

**Resultado automático:** a conta aparece imediatamente em **Entradas Previstas** no Fluxo de Caixa.

---

## 6. Dar Baixa em uma Conta a Receber (registrar recebimento)

**Caminho:** Financeiro → Contas a Receber → localizar a conta → botão **Receber** (ícone de check)

**Preencha:**
- Valor Recebido (preenche automaticamente com o saldo restante)
- Data do Recebimento
- Forma de Recebimento: PIX, TED, Boleto, Cartão, Dinheiro, Cheque
- Banco (opcional) — se informado, o saldo desse banco é creditado automaticamente

Clique em **Confirmar Recebimento**.

**O que muda automaticamente:**
- Status da conta → **RECEBIDO** (total) ou **PARCIAL**
- A conta **sai das Entradas Previstas** no Fluxo de Caixa
- O saldo do banco selecionado **aumenta** automaticamente
- Se havia conta contábil vinculada → lançamento contábil criado

---

## 7. Visualizar o Fluxo de Caixa

Projeção do dinheiro que vai entrar e sair em um período.

**Caminho:** Financeiro → Fluxo de Caixa

**Filtros disponíveis:**
- Data Início / Data Fim — período de vencimentos a analisar
- Obra (opcional) — filtra por obra específica

**O que cada card significa:**

| Card | Cor | Significado |
|---|---|---|
| Saldo Inicial | Azul | Soma atual de todos os bancos cadastrados |
| Entradas Previstas | Verde | Total das contas a receber PENDENTES no período |
| Saídas Previstas | Vermelho | Total das contas a pagar PENDENTES no período + Gestão de Custos aprovados |
| Saldo Final Projetado | Azul/Amarelo | Saldo Inicial + Entradas − Saídas |

**Tabela de Movimentos:**
- Linhas **verdes** = entradas (contas a receber pendentes)
- Linhas **vermelhas** = saídas (contas a pagar pendentes + custos V2 aprovados)
- Ordenadas por data de vencimento

---

## 8. Gestão de Custos V2 e o Fluxo de Caixa

Custos criados pelo módulo **Gestão de Custos** também entram no Fluxo de Caixa automaticamente:

| Status do Custo | Aparece no Fluxo de Caixa? |
|---|---|
| PENDENTE | Não |
| SOLICITADO | Sim — Saídas Previstas |
| AUTORIZADO | Sim — Saídas Previstas |
| PAGO | Não (já realizado — aparece só no histórico) |

**Caminho para aprovar um custo:** Financeiro → Gestão de Custos → localizar → botão **Solicitar** → depois **Autorizar** → depois **Pagar**

---

## 9. Resumo do Fluxo Automático

```
Criar Conta a Pagar
    → Aparece em Saídas Previstas no Fluxo de Caixa
    → Dar baixa (Pagar)
        → Sai das Saídas Previstas
        → Saldo do banco diminui (se banco informado)
        → Lançamento contábil gerado (se conta contábil vinculada)

Criar Conta a Receber
    → Aparece em Entradas Previstas no Fluxo de Caixa
    → Dar baixa (Receber)
        → Sai das Entradas Previstas
        → Saldo do banco aumenta (se banco informado)
        → Lançamento contábil gerado (se conta contábil vinculada)

Gestão de Custos V2 (SOLICITADO/AUTORIZADO)
    → Aparece em Saídas Previstas no Fluxo de Caixa
    → Ao marcar como PAGO
        → Sai das Saídas Previstas
        → Saldo do Fluxo de Caixa se ajusta
```

---

## 10. Dicas Práticas

- **Sempre selecione o banco** ao dar baixa — assim o saldo das contas bancárias fica correto e o Fluxo de Caixa reflete a realidade.
- **Vincule à Obra** quando o custo pertencer a uma construção — facilita o relatório de custo por obra.
- **Pagamento parcial** é suportado: informe apenas o valor pago hoje; o saldo restante continua em aberto no Fluxo de Caixa.
- **Vencimentos passados** com status PENDENTE aparecem como **VENCIDO** na lista — ainda entram nas Saídas Previstas se o filtro de data incluir a data de vencimento.
