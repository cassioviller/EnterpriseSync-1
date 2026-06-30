# Card de RDO mostra o progresso da OBRA (não 0%) — Design

> Data: 2026-06-30. Obra-piloto: **Baia** (id 591 no dev). Segue a rodada dos RDOs no import.

## Problema

Os cards da lista de RDO (`/rdo/lista?obra_id=<id>`, template `rdo_lista_unificada.html`) mostram
**"Progresso Geral 0.0%"** para a Baia, mesmo com o cronograma físico correto (Solo 100%,
Projetos 65%, Nivelamento 20%).

A rota `views/rdo.py::rdos` **já calcula o número certo** — o progresso **acumulado da obra até a
data daquele RDO** — via `calcular_progresso_geral_obra_v2(obra_id, data_relatorio, admin_id)`, e o
template renderiza esse valor (`progresso_medio`). O card NÃO lê a relação obsoleta `atividades`.
O bug é que `calcular_progresso_geral_obra_v2` devolve 0 por causa de uma inconsistência entre dois
motores de progresso físico:

- `sincronizar_percentuais_obra` (alimenta o cronograma físico) lê o **campo
  `RDOApontamentoCronograma.percentual_realizado`** → mostra 100/65/20. ✓
- `calcular_progresso_rdo` (usada por `calcular_progresso_geral_obra_v2`) **ignora** esse campo:
  só calcula `percentual_realizado = quantidade_executada_dia_acumulada / quantidade_total` quando
  `quantidade_total > 0`; senão devolve `0.0`. As tarefas materializadas pelo import **não têm
  `quantidade_total`**, então o resultado é 0. ✗

Isso afeta qualquer obra cujo físico vem por `percentual_realizado` — inclusive as criadas pelo
`scripts/seed_rdos_baias.py` (problema latente, não introduzido pela rodada anterior).

## Confirmação da Parte 1 (tarefas não citadas em 0%)

Verificado no banco (obra 591): das **56 tarefas**, só **5** têm % > 0 — as 3 folhas citadas no
relatório (ESTUDO DE SOLO SPT 100%, EXECUÇÃO DE PROJETOS 65%, FAZENDA: NIVELAMENTO DO PLATÔ 20%) e
2 pais por rollup (MOBILIZAÇÃO 53,21%, OBRA 10,41%). **As outras 51 estão em 0%.**

## Decisão

**Corrigir na raiz: `utils/cronograma_engine.py::calcular_progresso_rdo`.** Quando a tarefa não tem
`quantidade_total`, derivar o `percentual_realizado` do **último apontamento** (com
`RDO.data_relatorio <= data_rdo`, ordenado por data desc) — a mesma fonte que
`sincronizar_percentuais_obra`. Tarefas com `quantidade_total > 0` seguem pelo cálculo atual,
inalteradas.

Efeito em cascata, **sem mexer no template nem na rota**: `calcular_progresso_geral_obra_v2` itera
as folhas chamando `calcular_progresso_rdo` → passa a receber 100/65/20 nas folhas apontadas e 0
nas demais, ponderado por duração. O card já renderiza `progresso_medio`. Cada card mostra o avanço
da obra **na data daquele RDO** (cresce de ~6% em 22/06 a ~10% em 27/06).

### Semântica escolhida

**Acumulado até a data do RDO** (não o snapshot atual). É o que o código já pretende e conta a
evolução da obra dia a dia.

## A correção (forma do código)

Em `calcular_progresso_rdo`, o bloco de "Realizado" (hoje):

```python
perc_realizado = 0.0
if tarefa.quantidade_total and tarefa.quantidade_total > 0:
    perc_realizado = min(100.0, round(acumulado / tarefa.quantidade_total * 100, 2))
```

passa a ter o fallback:

```python
perc_realizado = 0.0
if tarefa.quantidade_total and tarefa.quantidade_total > 0:
    perc_realizado = min(100.0, round(acumulado / tarefa.quantidade_total * 100, 2))
else:
    # Tarefa sem quantidade física: o avanço é o percentual_realizado do ÚLTIMO
    # apontamento até data_rdo (mesma fonte que sincronizar_percentuais_obra).
    ultimo = (
        db.session.query(RDOApontamentoCronograma.percentual_realizado)
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio <= data_rdo,
        )
        .order_by(RDO.data_relatorio.desc())
        .first()
    )
    if ultimo is not None and ultimo[0] is not None:
        perc_realizado = min(100.0, float(ultimo[0]))
        if acumulado <= 0:
            acumulado = perc_realizado  # sinaliza apontamento p/ n_tarefas_apontadas
```

O `acumulado` (retornado como `quantidade_acumulada`) ganha o proxy só quando há apontamento e
ainda estava 0 — assim `calcular_progresso_geral_obra_v2` conta `n_tarefas_apontadas` corretamente
(ele testa `quantidade_acumulada > 0`). Para tarefas sem quantidade física, `quantidade_acumulada`
não tem unidade, então o proxy é inócuo.

## Onde mora

| Camada | Arquivo | Mudança |
|---|---|---|
| Motor de progresso | `utils/cronograma_engine.py::calcular_progresso_rdo` (~l.425-427) | **Modificar** — fallback para `percentual_realizado` sem `quantidade_total` |
| Teste | `tests/test_painel_financeiro.py` (ou `tests/test_importacao_fisico_financeiro.py`) | **Adicionar** — unit do fallback + integração do progresso por data |

`views/rdo.py`, `templates/rdo_lista_unificada.html` e `calcular_progresso_geral_obra_v2`: **sem
mudança** (já consomem o valor corretamente).

## Consumidores de `calcular_progresso_rdo` (sem regressão)

- `calcular_progresso_geral_obra_v2` (lista/detalhe de RDO) — alvo da correção.
- Detalhe do RDO e rota de apontamento — passam a mostrar o realizado real onde antes era 0.
- Tarefas COM `quantidade_total` — caminho inalterado (mesma fórmula).

A mudança só troca `0 → valor real` para tarefas sem `quantidade_total`; é melhoria pura.

## Testes

- **Unit fallback:** tarefa sem `quantidade_total`, 1 apontamento `percentual_realizado=65` em
  RDO de 2026-06-24 → `calcular_progresso_rdo(tid, 2026-06-27, admin)['percentual_realizado'] == 65`
  (antes 0); e com `data_rdo=2026-06-23` (antes do apontamento) → 0.
- **Integração (Baia):** importar a fixture → `calcular_progresso_geral_obra_v2(591, 22/06) > 0`,
  `(591, 27/06) > (591, 22/06)`, ambos < 100.
- **Regressão:** `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
  tests/test_importacao_fisico_financeiro.py -q` verde; invariantes da Baia preservados.
- **Browser:** os 6 cards da Baia mostram % crescente (não mais 0,0%).

## Invariantes da Baia

Inalterados (a mudança é só de leitura/exibição de progresso físico): veks 800.960 / fat 550.775 /
lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10.

## Fora de escopo

- Remover a propriedade obsoleta `RDO.progresso_geral` (relação `atividades`) — não é usada pelo
  card; limpeza separada se desejado.
- Mudar a ponderação do progresso (hoje por `duracao_dias` quando não há `quantidade_total`).
- Mexer no `seed_rdos_baias.py` (a correção já o beneficia).
</content>
