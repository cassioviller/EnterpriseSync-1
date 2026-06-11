# Importação de obra com coeficientes precisos (Baia REV10) — Design

> Data: 2026-06-11
> Status: aprovado (design) — aguardando plano de implementação
> Obra-piloto: **Kabod Cabana — Baias de bovinos (Fazenda Santa Mônica, Itu/SP)**, proposta REV10

## 1. Objetivo

Colocar uma obra real dentro do sistema de orçamento com **coeficientes auditáveis** (consumo de insumo por unidade de serviço), em vez do orçamento por duração/verba que a planilha original usa. O objetivo não é copiar valores: é montar uma base que o sistema recalcula por quantidade × coeficiente × preço, aplicando BDI/lucro/imposto, de modo que dê para:

- orçar com certeza (validar o recalculado contra o valor cobrado),
- organizar compra e execução (coeficiente + `fator_comercial`),
- evitar erro no dia a dia (número de consumo explícito por unidade).

O trabalho tem **duas partes**: (A) uma peça nova no sistema — importador de Composições via Excel; (B) o fluxo de dados que converte a obra REV10 nos 17 itens da proposta.

## 2. Contexto do sistema (já existe)

A cadeia de orçamento já está modelada e é exatamente a que precisamos:

```
Insumo → PrecoBaseInsumo (vigência) → Servico → ComposicaoServico (coeficiente) → Orcamento/OrcamentoItem → Proposta
```

Referências de código:

- `Insumo` — `models.py:5995` (tipo MATERIAL/MAO_OBRA/EQUIPAMENTO, `unidade`, `coeficiente_padrao`, `fator_comercial`, `fracionavel`, `tipo_medicao`)
- `PrecoBaseInsumo` — `models.py:6060` (`valor`, vigência), método `Insumo.preco_vigente(data_ref)`
- `Servico` — `models.py:415` (`unidade_medida`, `imposto_pct`, `margem_lucro_pct`, relação `composicoes`)
- `ComposicaoServico` — `models.py:6085` (**`coeficiente` Decimal 15,6** = qtd insumo por unidade do serviço; UNIQUE (servico_id, insumo_id))
- `ComposicaoServicoHistorico` — `models.py:6114` (rastreia alteração de coeficiente)
- `Orcamento`/`OrcamentoItem` — `models.py:6201` (item tem `composicao_snapshot` JSON, `quantidade`, override de `imposto_pct`/`margem_pct`)
- Cálculo de preço — `services/orcamento_service.py:34` (`calcular_precos_servico()`)
- BDI/lucro/imposto — `services/pricing.py:104` (`resolver_aliquotas`, `precificar`), spec `docs/superpowers/specs/2026-05-29-orcamento-bdi-lucro-impostos-proposta.md`
- Importador de **Insumos** (existe) — `services/catalogo_excel.py:300` (`importar_insumos_xlsx`)
- **NÃO existe** importador de Composições — só cadastro manual via UI. É a lacuna que a Parte A preenche.

## 3. Decisões travadas

| Tema | Decisão |
|---|---|
| Fonte do coeficiente | **SINAPI** como base inicial (composições analíticas públicas, grátis), o usuário **edita** pra realidade da obra depois. TCPO descartado (pago). |
| Quantitativos | **Híbrido**: quantidade da proposta REV10 como base; conferir nas **pranchas PDF** e resolver divergências nos itens de maior valor (ex.: 22 × 24 baias). |
| Carga no sistema | **Criar importador de Composições via Excel** (reutilizável para obras futuras), no padrão do importador de Insumos. |
| Escopo | Os **17 itens** da proposta (1.1–1.17). |
| Jornada | 8 h/dia, 22 dias/mês (premissa para converter mão de obra em h/unidade). |

## 4. Parte A — Importador de Composições (feature)

### 4.1. Função

Nova função em `services/catalogo_excel.py`, espelhando `importar_insumos_xlsx`:

```
importar_composicoes_xlsx(arquivo, admin_id) -> dict
```

### 4.2. Formato da planilha

Uma aba ("Composicoes" ou primeira aba). Cabeçalho na linha 1. Uma linha por par serviço×insumo:

| coluna | obrigatória | descrição |
|---|---|---|
| `servico_nome` | sim | nome do serviço (chave de upsert do Serviço) |
| `servico_unidade` | sim | unidade do serviço (kg, m², m³, un, vb…) |
| `categoria` | não | categoria do serviço |
| `insumo_nome` | sim | nome do insumo — **precisa já existir** (upsert por nome, igual ao importador de insumos) |
| `coeficiente` | sim | consumo do insumo por unidade do serviço (Decimal) |
| `unidade_insumo` | não | snapshot da unidade do insumo |
| `observacao` | não | livre (ex.: "perda 5%", "h/kg") |

`imposto_pct` / `margem_lucro_pct` do serviço **não** entram nesta planilha — ficam nos defaults do Serviço/Orçamento/Empresa (cascata já existente em `pricing.resolver_aliquotas`). Mantém o importador focado só em composição.

### 4.3. Regras

- **Upsert do Serviço** por `(admin_id, lower(servico_nome))`: cria se não existir, com `unidade_medida = servico_unidade` e `categoria`; se existir, mantém.
- **Resolução do Insumo** por `(admin_id, lower(insumo_nome))`: se não existir → **rejeita a linha** com motivo (`insumo não encontrado: <nome>`). O importador **não cria insumo** (isolamento — insumos vêm do importador próprio, antes).
- **Upsert da Composição** pela UNIQUE `(servico_id, insumo_id)`: cria, ou atualiza o `coeficiente` (e grava `ComposicaoServicoHistorico` quando o coeficiente muda).
- Parse de `coeficiente` como Decimal; valores inválidos rejeitam a linha.
- `servico_unidade` obrigatória em pelo menos uma linha do serviço.

### 4.4. Retorno

```python
{
  'servicos_created': int,
  'servicos_updated': int,
  'composicoes_created': int,
  'composicoes_updated': int,
  'rejected': [{'linha': int, 'motivo': str}],
}
```

### 4.5. Integração e testes

- Rota de upload em `importacao_views.py` (onde já mora o de insumos) + botão na tela de importação.
- Testes em `tests/`: planilha válida (cria serviço+composições), insumo inexistente (rejeita linha), reimportação (atualiza coeficiente + grava histórico), coeficiente inválido (rejeita).

## 5. Parte B — Fluxo da obra (7 passos)

| Passo | Ação | Fonte | Saída |
|---|---|---|---|
| 0. Convenções | jornada 8h/22d; mapear lucro/imposto por item para `imposto_pct`/`margem_lucro_pct`; **decidir custo × venda** (o "Valor do Projeto" R$ 1.145.717 é custo, não venda) | docs anteriores + decisão do usuário | tabela de premissas |
| 1. Insumos | catálogo de materiais/mão de obra/equipamento com unidade e preço | REV10 + preços SINAPI | aba "Insumos" → importada pelo importador existente |
| 2. Composições | casar cada um dos 17 serviços com a(s) composição(ões) SINAPI corretas e extrair coeficientes | SINAPI (web/planilha oficial) | aba "Composicoes" → importada pela Parte A |
| 3. Quantitativos | quantidade por serviço; conferir pesados nas pranchas PDF | proposta REV10 + pranchas | quantidades por item |
| 4. Orçamento | criar Orçamento + 17 `OrcamentoItem`; sistema recalcula custo e aplica BDI | sistema | orçamento no sistema |
| 5. Validação | comparar total recalculado × valor REV10, item a item; sinalizar divergência | sistema | relatório "bate / não bate" |
| 6. Calibração | usuário ajusta coeficientes que destoam da realidade; histórico registrado | conhecimento do usuário | coeficientes da casa |

O mapeamento concreto **serviço → código SINAPI** dos 17 itens fica no plano de implementação (não neste spec).

## 6. Critérios de sucesso

1. Importador de Composições funciona: planilha serviço×insumo×coeficiente popula `Servico` + `ComposicaoServico`, com upsert e histórico, e rejeita linhas inválidas com motivo.
2. Os 17 itens da obra existem no sistema como serviços com composição SINAPI e quantidades.
3. **Validação (Passo 5)**: para cada item, o sistema é comparado à REV10 nos **dois** números — custo recalculado × custo REV10, **e** preço de venda (pós-BDI) × preço de venda REV10 (colunas K–AE). Divergências ficam explícitas e justificadas (erro corrigido da planilha, escolha de coeficiente, ou ajuste de quantidade).
4. Cada coeficiente é editável e rastreável (`ComposicaoServicoHistorico`).

## 7. Fora de escopo

- Leitura direta de `.dwg` (uso os PDFs equivalentes das pranchas).
- TCPO (base paga).
- `GERENCIAMENTO FINANCEIRO/Planilha de Custos.xlsx` e `MEDIÇÃO/Medição.xlsx` **não são fonte** — estão vazias / com dados aleatórios, conforme o usuário.
- Importação automática de Orçamento/Proposta via Excel (o Orçamento é montado a partir dos serviços + quantidades; Proposta é gerada do Orçamento pelo fluxo que já existe).

## 8. Decisões do Passo 0 (resolvidas)

- **Custo × venda**: a validação usa **os dois**. Compara custo recalculado × custo REV10 **e** preço de venda (pós-BDI) × preço de venda REV10 (colunas K–AE). Os dois precisam ser reconciliados.
- **Erros da planilha**: **corrigir na importação** — modelar o valor correto (não replicar o erro), documentando cada correção. Casos conhecidos: material "verba global" multiplicado por quantidade no preço de venda; item 1.16 com material contado uma vez para 24 baias.
