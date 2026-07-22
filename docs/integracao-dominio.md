# Integração contábil — exportação para o Domínio

> Especificação da exportação de lançamentos do fluxo de caixa do SIGE para
> o **Domínio Web / Domínio Contabilidade**, importação *"Lançamentos
> Contábeis em Lote — Excel (3.1)"*, `codi_leiaute 11758`.
>
> **Status: NÃO IMPLEMENTADO.** Este documento é o contrato-alvo da Fase 8.
> Hoje não existe nenhuma integração com o Domínio no repositório — o que
> existe é uma contabilidade interna de partidas dobradas
> (`contabilidade_views.py`, `LancamentoContabil`/`PartidaContabil`), que é
> outra coisa. A tela `/contabilidade/sped` é vazia por construção (nada
> instancia `SpedContabil`).
>
> **Origem:** a lógica abaixo vem de uma rotina já existente fora deste
> repositório. Ver "Procedência e o que NÃO se aproveita".

## Procedência e o que NÃO se aproveita

A rotina original foi calibrada para **outra empresa** — um cliente da mesma
contabilidade, com plano de contas e de/para de categorias próprios.

| Reaproveitável integralmente | A construir do zero para a Veks |
|---|---|
| Layout 11758 (formato, separadores, ordem de campos) | De/para `categoria + subcategoria → contas` |
| Regras de partida/contrapartida | Mapeamento `conta financeira do fluxo → código reduzido` |
| Deduplicação de transferências | — |
| Validações bloqueantes | — |
| Templates de histórico | — |

O plano de contas da Veks é insumo da Ana/contabilidade e ainda não foi
entregue. **Trate o primeiro mês de exportação como calibração:** volume
alto de pendências é esperado e aceitável.

## Formato do arquivo

- **CSV**, separador de campos `;` (ponto e vírgula). Extensão `.csv` ou
  `.txt` — conteúdo idêntico.
- **Separador decimal `,`** (vírgula). Valor sempre com 2 casas, **sempre
  positivo**, sem separador de milhar.
- **Data** no formato `DD/MM/AAAA`.
- **Código de histórico**: em branco (usa-se apenas o complemento).
- **Complemento histórico**: texto descritivo, ~60 caracteres, gerado por
  template (abaixo).
- **`inicia lote = 1`** para cada lançamento simples — cada linha é seu
  próprio lote.
- **Filial** e **centros de custo** débito/crédito: em branco até
  confirmação de uso.
- **Nome do arquivo**: `importacao_dominio_<empresa>_<periodo>.csv`.

## Templates de complemento histórico

| Tipo | Template |
|---|---|
| Despesa | `<categoria>: <subcategoria> ref. <descrição truncada>` |
| Fornecedor | `Pgto fornecedor: <nome ou descrição truncada>` |
| Cliente | `Receb. cliente conforme fluxo de caixa <data>` |
| Tarifa | `Tarifa bancária: <subcategoria>` |
| Transferência | `Transf. entre contas: <origem> → <destino>` |

## Partida e contrapartida

**Princípio misto:** a contabilidade já recebe as notas fiscais por outro
caminho. O movimento de caixa dá **baixa** em Clientes/Fornecedores — nunca
lança a receita ou a compra de novo.

| Situação | Débito | Crédito |
|---|---|---|
| Recebimento de cliente (NF de venda já lançada) | conta banco | Clientes |
| Pagamento a fornecedor (NF de compra já lançada) | fornecedor específico ou genérico | conta banco |
| Despesa operacional direta (sem NF prévia) | conta da despesa | conta banco |
| Tarifa bancária | conta de tarifas | conta banco |
| Aplicação financeira | conta aplicação | conta banco |
| Resgate de aplicação | conta banco | conta aplicação |
| Imposto pago (provisão já feita) | conta do imposto | conta banco |
| Transferência entre contas | conta destino | conta origem |

## Regras de processamento

1. **Deduplicação de transferências.** Uma transferência entre contas
   aparece como **duas linhas** no fluxo de caixa (saída na origem +
   entrada no destino, mesmo valor e data). Colapsar em **UM** lançamento
   (débito destino, crédito origem). Par incompleto ⇒ pendência.
2. **Não duplicar receita/compra.** Se a NF já está na contabilidade, o
   movimento de caixa dá baixa em Clientes/Fornecedores. Nunca lançar
   receita nem estoque de novo.
3. **Matching de fornecedor específico.** Antes de cair no código genérico
   de Fornecedores, tentar casar a descrição contra os fornecedores
   nominais do plano de contas — comparação *case-insensitive* e sem
   acentos.
4. **Nunca inventar código de conta.** Conta inexistente no plano ⇒ a linha
   vai para pendência, com o motivo registrado.
5. **Descartes automáticos:** linhas de SALDO/TOTAL/Projeção; datas com ano
   1900; linhas sem entrada e sem saída; duplicatas exatas.

## Validações bloqueantes

Rodam **antes** de entregar o arquivo. Qualquer uma que falhe impede a
geração:

1. **Partidas dobradas:** Σ débitos = Σ créditos por lote.
2. Todo código de débito e de crédito **existe** no plano de contas.
3. Datas válidas e dentro do período exportado.
4. Nenhum valor ≤ 0.
5. Nenhuma linha com débito **e** crédito vazios.
6. **Cobertura:** se mais de **20%** das linhas caírem em pendência, parar
   e reportar **antes** de gerar o arquivo.

## Saídas

| Artefato | Conteúdo |
|---|---|
| `importacao_dominio_<empresa>_<periodo>.csv` | O arquivo de importação |
| Relatório de pendências (`.xlsx`) | data, descrição, valor, conta, motivo |
| Resumo do processamento (`.md`) | totais por tipo; débito/crédito por conta |

## Específico da Veks — a construir na Fase 8

Duas tabelas de correspondência, **estruturadas como dados (CSV/tabela),
não como código**, para que a contabilidade possa revisá-las e mantê-las
sem deploy:

1. **De/para `categoria + subcategoria → contas`** (débito e crédito).
2. **Mapeamento `conta financeira do fluxo → código reduzido`** do plano
   de contas da Veks.

## Pontos de encaixe no código atual

O que já existe e alimenta esta exportação:

| Peça | Onde | Papel |
|---|---|---|
| `FluxoCaixa` | `models.py:781` | Fonte dos lançamentos (`banco_id`, `categoria_fluxo_caixa_id`, `fornecedor_id`, `data_movimento`) |
| `CategoriaFluxoCaixa` / `GrupoFinanceiro` | `models.py:7174` / `:7150` | Origem do lado "categoria/subcategoria" do de/para |
| `services/classificador_cadastro.py` | — | Classifica a descrição em categoria antes da exportação; é o que reduz o volume de pendências |
| `BancoEmpresa` | `models.py:1835` | Origem do lado "conta financeira" do mapeamento |
| `calcular_fluxo_caixa` | `financeiro_service.py:437` | Seleção do período |

**Dependência de dados a resolver antes:** `FluxoCaixa.obra_id` é *nullable*
hoje, e lançamento sem obra some do orçado×real. A exportação para o Domínio
não depende de obra, mas a Fase 4 (centro de custo obrigatório) deve vir
antes para que os dois relatórios batam.

## Lacunas conhecidas

- O **plano de contas da Veks** não foi entregue — sem ele, o de/para não
  pode ser construído (pendência registrada do lado do cliente).
- Não há especificação de **importação de retorno** do Domínio (conciliação
  do que foi aceito). O escopo atual é exportação apenas.
- Não foi definido **quem dispara** a exportação nem com que periodicidade
  (mensal manual? job agendado?) — decidir na Fase 8.
