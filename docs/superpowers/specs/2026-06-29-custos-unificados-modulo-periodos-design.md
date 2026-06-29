# Custos unificados por grupo + módulo de períodos (Previsão × Realizado)

> Data: 2026-06-29. Obra-piloto: Baia.
> Contexto de partida: ver `2026-06-27-custo-cronograma-fieis-regime-medicao-design.md`
> (modelo custo↔cronograma, custo de período, etapas no painel Financeiro).

## Problema

No detalhe da obra → aba **Financeiro**, ao clicar numa etapa, os custos recorrentes
aparecem como **uma linha por mês** ("Escritório (jun/26)", "Escritório (jul/26)"…),
porque `_add_linhas_de_meses` cria um `ObraServicoCustoItem` por mês. A tabela fica longa
e repetitiva, e não há lugar para registrar o **realizado por período**.

## Objetivo

1. **Unificar** as linhas que se repetem mês a mês em **uma linha por tipo de custo**.
2. Clicar nessa linha abre um **módulo (modal)** com os **períodos e valores** daquele
   custo, onde o usuário pode **adicionar/remover períodos e editar valores**.
3. O módulo tem **duas abas**: **Previsão** e **Realizado** (realizado por período).

## Decisões (acordadas no brainstorming)

- **Realizado = lançamento manual** nesta versão. O modo "puxar do sistema" (híbrido)
  fica como direção futura; a estrutura deve deixar a costura pronta, sem implementá-lo.
- **Realizado manual alimenta os indicadores** do Financeiro: KPI "custo realizado",
  Curva S e caixa/verba disponível.
- **Sem tratamento de duplicação.** Hoje RDO/compras **não** são vinculados a etapas, logo
  o realizado por etapa é efetivamente vazio — o manual é a única fonte. O valor é
  **aditivo** ao pipeline existente (que, na prática, contribui zero para estas etapas).
- O mecanismo (agrupar + módulo) vale para **todas** as etapas, de forma uniforme.
- **Abordagem A (reaproveitar `ObraServicoCustoItem`)**, não criar tabelas novas.

## Modelo de dados

`ObraServicoCustoItem` já é, na prática, "uma linha por período": `descricao`, `valor`
(= previsto), `fonte` (`veks|fat_direto`), `data_inicio`, `data_fim`, `ordem`.

Mudanças:

1. **Nova coluna** `valor_realizado` (`Numeric(15,2)`, `nullable=False`, `default 0`) →
   realizado manual por período. `valor` continua sendo o **previsto** por período.
2. **Descrição passa a ser o nome-base** ("Escritório"), sem o sufixo "(mês/aa)". O rótulo
   do período é **derivado das datas** (`data_inicio` → "jun/26"). `_add_linhas_de_meses`
   para de anexar o sufixo.
3. **Identidade do grupo (linha unificada)** = par **(`descricao`, `fonte`)** dentro da
   mesma OSC. Cada `ObraServicoCustoItem` do grupo é um **período**.

### Migração

- Número: próximo livre (**202**; a 201 é `Obra.regime_medicao`).
- Idempotente, padrão do repo: checar `information_schema.columns` antes do `ADD COLUMN`.
- **Data-migration:** remover o sufixo "(mês/aa)" das descrições existentes (regex no fim
  da string: ` \((jan|fev|…|dez)/\d{2}\)$`), para os itens já gravados agruparem certo.
- `valor_realizado` começa em 0 para todos.

## UI

### Tabela da etapa (substitui a lista plana de itens)

Uma linha **por grupo** `(descricao, fonte)`:

| Custo | Fonte | Períodos | Previsto | Realizado |  |
|---|---|---|---|---|---|
| Escritório | Veks | 5 | Σ valor | Σ valor_realizado | `▸` |

`▸` abre o módulo. Linha de total da etapa preservada (Realizado / Previsto no cabeçalho).
Etapas sem `osc_id` (multi-OSC) seguem com a mensagem atual de "edição indisponível".

### Módulo (modal) — abas Previsão e Realizado

Cabeçalho: nome-base + selo da fonte.

- **Aba Previsão:** uma linha por período — `mês | valor previsto`. Editar `valor`;
  **+ Adicionar período** (seletor de mês → `data_inicio` = 1º dia, `data_fim` = último
  dia; permite intervalo custom); remover período. Total da aba = Σ previsto.
- **Aba Realizado:** os mesmos períodos — `mês | valor realizado`. Editar `valor_realizado`.
  Sem digitação automática (costura para o híbrido futuro). Total da aba = Σ realizado.

Período = um `ObraServicoCustoItem`. Adicionar período = novo item no grupo (mesma
`descricao` + `fonte`). Remover = excluir o item.

### Persistência

Reaproveitar `POST /obras/<id>/financeiro/etapa/<osc_id>/itens` (substitui os itens da
OSC). O payload de cada item passa a carregar **`valor_realizado`** além de
`descricao/valor/fonte/data_inicio/data_fim`. O front envia o conjunto completo de
períodos de todos os grupos da etapa (a tabela + os módulos compõem o estado).

## Realizado → indicadores

- **Painel/KPI:** o realizado da etapa passa a incluir `Σ valor_realizado` dos seus itens
  (`painel_financeiro` / `montar_fisico_financeiro`). Aditivo ao `realizado_por_etapa`
  atual (que é ~0 para estas etapas).
- **Curva S realizado:** somar a contribuição mensal de `valor_realizado` por mês
  (`data_inicio`) à série `realizado` (`curva_realizado` hoje só lê `GestaoCustoFilho`).
- **Caixa/verba disponível:** segue de "custo realizado", então herda o novo realizado.

## Fora de escopo

- Modo híbrido (puxar realizado de RDO/compras automaticamente).
- Vincular RDO/compras a etapas.
- Mudança no cronograma físico, RDO ou portal (custo de período continua fora deles).

## Testes

- Agrupamento: itens com mesma `(descricao, fonte)` colapsam numa linha; `fonte`
  diferente = grupos diferentes.
- Migração: sufixo "(mês/aa)" removido; agrupamento correto sobre dados existentes.
- Módulo: adicionar período cria item; remover exclui; `valor_realizado` persiste.
- Indicadores: `valor_realizado` manual entra no KPI custo realizado e na Curva S.
- **Invariantes da Baia preservados:** veks 800.960 / fat 550.775 / lucro 24.976 /
  imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10 (previsto não muda; realizado
  começa em 0).
- Suíte financeira verde:
  `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`.
