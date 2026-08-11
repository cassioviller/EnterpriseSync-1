# Obra 10 — Baias Kabod (Fazenda Santa Mônica, Itu/SP)

> ⚠️ **Esta pasta é diferente das outras duas de `cargas/`.** A `obra-43` e a
> `obra-OB004` guardam payloads do formato **`carga-obra/1.1`**, que sobem pelo
> upload da página da obra (aba RDOs → "Atualizar por JSON") e **não apagam
> nada**. O arquivo daqui é do **formato canônico**, vai por outro caminho e
> **é destrutivo**. Subir um no lugar do outro não funciona: o
> `validar_payload` recusa o canônico com "formato desconhecido", e o
> importador canônico não entende o `carga-obra/1.1`.

## O arquivo

`cronograma_fisico_financeiro_baias.json` é um **symlink** para o canônico na
raiz do repositório. Não é cópia de propósito — cópia envelhece em silêncio, e
o `tests/fixtures/` usa exatamente o mesmo truque pelo mesmo motivo. Editar,
regerar ou dar `git pull` na raiz reflete aqui na hora.

Conteúdo atual (rodada de 11/08, do `CRONOGRAMA BAIAS 10.08.mpp`):

| | |
|---|---|
| tarefas | 109 |
| RDOs | 37 (22/06 a 06/08) |
| fotos | 167, em `fotos_rdos/<AAAA-MM-DD>/` |
| fim do cronograma | 19/10 |
| `_meta.cronograma_atualizado_em` | `2026-08-10` |

Confira antes de importar — se vier 101 tarefas e `2026-07-08`, é a versão
anterior à revisão estrutural:

```bash
python -c "import json;d=json.load(open('cronograma_fisico_financeiro_baias.json'));print(d['_meta']['cronograma_atualizado_em'], len(d['cronograma_tarefas']), len(d['rdos']))"
# esperado: 2026-08-10 109 37
```

## Como importar

**No servidor, por CLI — não pela tela.** Pelo gunicorn dá timeout com este
volume de fotos (ver `docs/deploy-checklist-easypanel.md`).

```bash
git pull                      # o servidor precisa estar no commit que tem o JSON E as fotos
SIGE_ENABLE_DEMO_SEED=false python scripts/seed_fisico_financeiro_baias.py <admin>
```

## Antes de rodar, três verificações

1. **Nenhum RDO da Baia pode estar `assinado`, `aprovado` ou `retificado`.**
   O `_materializar_rdos` apaga os RDOs com `db.session.delete` sem checar
   estado, e a guarda `before_flush` de `services/rdo_ciclo_vida.py` derruba a
   **transação inteira** — não é "pula aquele dia", é o import todo falhar.
2. **A obra não pode ter `CronogramaVersao` de origem `upload_mspdi`/`upload_mpp`.**
   `_recusar_se_versionada_pelo_fluxo_novo`
   (`services/importacao_fisico_financeiro.py:815`) recusaria o reimport, e o
   caminho viraria obrigatoriamente a aba Cronograma (M09).
3. **As fotos precisam existir na máquina que roda o import.** Elas vêm de
   `fotos_rdos/<data>/`, versionadas no repositório. Se o servidor estiver num
   commit anterior, as fotos dos dias novos não existem lá e o importador
   **não quebra** — loga warning e pula. Você fica com os RDOs certos e o álbum
   incompleto, sem erro visível.

## O que o import apaga e recria

Propostas e seus itens, orçamentos e seus itens, itens de medição,
`ObraServicoCusto`, `TarefaCronograma`, `MedicaoContrato` e **todos os RDOs da
obra**. Tudo volta do JSON — **o que tiver sido lançado pela UI depois do
último sync do arquivo se perde** (mão de obra editada em RDO, foto anexada à
mão, RDO criado pela tela).

## Para regerar

```bash
python scripts/rebuild_baia_from_1008_mpp.py
```

O de-para das tarefas, o fechamento pelo % do Project e as decisões de cada
percentual estão no script e em `ESTADO_ATUALIZACAO_BAIA.md`.
