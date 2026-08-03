# p1 — Estancar sangramento: tenant e dupla contagem (design)

> Spec do pacote **p1** do `PLANO-NUCLEO.md` (onda A). Escrita em
> **2026-08-03**, com cada ponto reconferido no código vivo nesta data — os
> vereditos de 31/07 já são de outra semana, e dois deles mudaram de tamanho.
>
> **Por que este é o primeiro pacote:** ele não depende de nada, e todo custo
> que o sistema exibe hoje é potencialmente inflado. Os pacotes que vêm depois
> (p3 custo orçado, p4 fórmula de progresso, p10 EVM) existem para **consolidar
> números**. Consolidar número errado é o pior uso possível deles.

## Resumo

Cinco frentes, todas de conserto, nenhuma feature:

| # | Frente | O que sangra hoje |
|---|---|---|
| F1 | Escopo de tenant nos relatórios | 9 consultas servem dados de **todas as empresas** |
| F2 | Heurística "admin com mais dados" | 3 pontos escolhem a empresa por contagem de linhas |
| F3 | Dupla contagem cross-origem | Ponto e RDO lançam o mesmo dia; nenhum dedup enxerga o outro |
| F4 | Idempotência do ponto horista | Custo lançado **a cada batida** |
| F5 | Custo sem medição | 3 caminhos de salvar RDO geram custo e não recalculam a medição |

---

## Contexto verificado (03/08)

### F1 — `relatorios_funcionais.py`

O veredito nº 7 do plano diz "7 relatórios + 3 exportações = 10 pontos".
A varredura função a função dá **9**, e a diferença é boa notícia:

| Sem escopo de tenant | Já corrigido (padrão a copiar) |
|---|---|
| `_relatorio_funcionarios` :58 | `_relatorio_veiculos` :264 |
| `_relatorio_ponto` :81 | `_relatorio_dashboard_executivo` :304 |
| `_relatorio_horas_extras` :115 | `_relatorio_progresso_obras` :356 |
| `_relatorio_alimentacao` :166 | `_relatorio_rentabilidade` :384 |
| `_relatorio_obras` :202 | |
| `_relatorio_custos_obra` :231 | |
| `_exportar_csv` :438 · `_exportar_excel` :483 · `_exportar_pdf` :535 | |

Quatro funções **já usam** `_tenant_id()` (`:287`), que delega para
`utils.tenant.get_tenant_admin_id` e aborta quando não há tenant. Elas estão
carimbadas `Fase 0 / R3`. Ou seja: **o padrão está pronto dentro do próprio
arquivo** — F1 é replicá-lo, não projetá-lo.

Os três `_gerar_*_export` (`:677`, `:692`, `:730`) **não consultam nada** —
renderizam o que recebem. Ficam fora da conta de propósito.

### F2 — a heurística de adivinhar o tenant

O plano fala em "5 fallbacks". Dois deles **já não existem**: as duas
definições de `get_admin_id_dinamico` (`views/helpers.py:411` e a duplicata
em `views/api.py:1002`) foram esvaziadas pela Fase 0.5 e hoje delegam para o
resolvedor canônico. Sobra delas o problema de higiene: **duas definições
idênticas** do mesmo nome em dois módulos.

O que continua vivo é a heurística **inline**, copiada em três lugares:

```sql
SELECT admin_id, COUNT(*) FROM funcionario WHERE ativo = true
 GROUP BY admin_id ORDER BY total DESC LIMIT 1
```

- `views/rdo.py:92` e `views/rdo.py:2274` — serve um funcionário da empresa
  com mais funcionários ativos;
- `views/obras.py:1523` — mesmo padrão sobre `obra`; e quando a consulta
  falha, `admin_id = None` faz a linha `:1533` virar
  `Obra.query.filter_by(id=id)` — **sem tenant nenhum**.

Agravante que não está em veredito algum: as duas rotas de RDO fazem
`Funcionario.query.filter_by(email=email_busca).first()` (`:88`, `:2270`)
**antes** do fallback. Busca por e-mail no parque inteiro: com o mesmo e-mail
em dois tenants, o primeiro registro ganha e a heurística nem chega a rodar.

### F3 — os dois dedups que não se cruzam

`event_manager.lancar_custos_rdo` (`:590`) deduplica `CustoObra` por
**`rdo_id` + funcionário + data + admin** (`:706-713`). O custo gerado pelo
ponto nasce com **`rdo_id` NULL** e `categoria='PONTO_ELETRONICO'`
(`event_manager.py:486-505`) — é invisível para essa chave, por construção.

O mesmo vale um andar acima: o `GestaoCustoFilho` do RDO é deduplicado por
`origem_tabela='rdo_mao_obra'` + data + entidade + admin, e o do ponto grava
outra `origem_tabela`. **Dois ledgers, quatro origens, nenhum cruzamento.**

A guarda certa **já existe**: `services/rdo_custos.existe_ponto_no_dia`
(`:50`) responde "há `RegistroPonto` de (funcionário, dia, admin)?" e é usada
pelo caminho paralelo `gerar_custos_mao_obra_rdo`. O handler do evento não a
usa.

### F4 — o horista sem chave

No mesmo handler de `ponto_registrado`, o caminho **diarista** tem guardas
`ja_existe_*` antes de cada lançamento (diária, VA, VT). O caminho
**horista** (`:458-505`) calcula e insere `CustoObra` direto, sem checar nada.

E `PontoService` emite `ponto_registrado` **a cada batida**
(`ponto_service.py:142-148`) — entrada e saída são eventos separados. Um dia
com quatro batidas gera quatro custos.

### F5 — custo sem medição

Três caminhos de salvar RDO chamam `gerar_custos_mao_obra_rdo` diretamente e
**não** emitem `rdo_finalizado`:

- `rdo_editar_sistema.py:551`
- `crud_rdo_completo.py:469`
- `crud_rdo_completo.py:579`

Os emissores estão só em `views/rdo.py` (`:1756`, `:2153`, `:4498`). Quem
salva pelos três primeiros gera custo e **não dispara o listener de
`rdo_finalizado`** (`event_manager.py:1418`), que é quem recalcula a medição.
Resultado: custo sobe, medição não acompanha.

*(As chamadas em `migrations.py` e `scripts/` são deliberadas — backfill não
deve reemitir evento. Ficam como estão.)*

---

## O desenho

### F1 — um resolvedor, nenhuma exceção

Cada uma das 9 funções recebe `admin_id = _tenant_id()` e filtra por ele,
copiando `_relatorio_veiculos` (`:264`). Nas que hoje fazem `Model.query`
cru, o filtro entra **antes** de qualquer `join`, para não depender de ordem.

`_tenant_id()` já aborta quando não há tenant — nenhuma função nova precisa
decidir o que fazer nesse caso.

### F2 — quem não tem tenant não recebe o de outro

As três heurísticas inline saem. No lugar:

- `views/rdo.py:88-95` e `:2270-2277` — `Funcionario.query.filter_by(email=…,
  admin_id=tenant)`; sem funcionário no tenant, a rota responde 404 em vez de
  servir o de outra empresa;
- `views/obras.py:1520-1533` — o ramo de bypass sai inteiro; sem tenant
  resolvido, 404.

As duas definições gêmeas de `get_admin_id_dinamico` viram uma só: `views/api.py`
importa de `views/helpers.py`. Comportamento idêntico — é remoção de sósia.

### F3 — o dedup passa a cruzar as origens

`lancar_custos_rdo` chama `existe_ponto_no_dia(func_id, data_rdo, admin_id)`
antes de lançar, exatamente como `gerar_custos_mao_obra_rdo` já faz. Havendo
ponto no dia, o custo do RDO é pulado e **logado** — silêncio aqui é o que
produziu o problema.

Para o `GestaoCustoFilho`, a chave de idempotência passa a ser
(entidade, data, obra, admin) **independente de `origem_tabela`** para as
categorias de mão de obra (`SALARIO`, `MAO_OBRA_DIRETA`). É a mudança que
faz o dedup enxergar a outra origem.

### F4 — idempotência no horista

Antes do `CustoObra` do horista, a mesma pergunta que o diarista já faz:
existe custo de (funcionário, data, obra, admin) com `categoria =
'PONTO_ELETRONICO'`? Existindo, **atualiza** o valor em vez de inserir — as
horas do dia mudam a cada batida, então o certo é o último cálculo valer, não
somar N linhas.

### F5 — um único caminho de "RDO virou custo"

Os três chamadores diretos passam a emitir `rdo_finalizado` e a deixar o
handler lançar, em vez de chamar o serviço na mão. Fecha a assimetria sem
criar caminho novo: o handler já faz o que eles fazem, **mais** o recálculo
de medição.

---

## O que esta spec deliberadamente NÃO faz

- **Não unifica os ledgers.** `CustoObra` × `GestaoCustoFilho` é o p8 (onda
  E). Aqui os dois continuam existindo — só param de contar o mesmo fato
  duas vezes.
- **Não mexe no histórico já gravado.** Ver a decisão nº 1 abaixo.
- **Não trata o A09** (dedup de NF na entrada manual de almoxarifado). Ele
  está no p1 do plano, mas a entrada manual não foi localizada nesta rodada —
  entra quando for, ou vira spec própria. Registrar isso é melhor do que
  fingir escopo.

---

## Decisões pendentes

| # | Decisão | Recomendação |
|---|---|---|
| 1 | **Histórico duplicado**: consertar só para frente, ou reconciliar o passado? | Consertar para frente **primeiro**; depois um script de reconciliação com `--dry-run`, no padrão dos backfills da casa. Sem isso, o número velho continua inflado — mas apagar custo em produção sem ensaio é como o projeto perdeu dado antes |
| 2 | **Resposta das rotas sem tenant**: 403 ou 404? | **404.** 403 confirma que o recurso existe em outra empresa |
| 3 | **Horista: atualizar ou somar** o custo do dia | **Atualizar** — o último cálculo do dia é o correto; somar batidas é o defeito |

## Testes

1. **Cross-tenant vermelho → verde**: dois tenants com dado equivalente; cada
   um dos 9 relatórios/exportações devolve **só** as linhas do tenant
   autenticado. Hoje esse teste passa vermelho — é o critério de pronto.
2. **Fallback morto**: usuário autenticado sem `admin_id` (funcionário órfão)
   nas três rotas → 404, nunca dado de outra empresa.
3. **Um dia, uma linha**: dia simulado com batidas múltiplas **mais**
   finalização de RDO, para horista e diarista, produz **exatamente uma**
   linha de custo de mão de obra por (funcionário, data, obra) em cada ledger.
4. **Custo implica medição**: salvar RDO pelos três caminhos de F5 recalcula
   a medição, como os de `views/rdo.py` já fazem.

## Rollout

**Sem flag.** F1 e F2 são correção de vazamento entre empresas — flag aqui
significaria "deixar vazando para alguns". F3-F5 mudam número de custo, e é
por isso que o critério de pronto nº 3 é um teste, não uma observação em
produção.

O que **exige ensaio** é a decisão nº 1: qualquer varredura no histórico
gravado roda em `--dry-run` primeiro, com o relatório do que apagaria, e só
depois com escrita — mesmo protocolo dos backfills de cronograma.
