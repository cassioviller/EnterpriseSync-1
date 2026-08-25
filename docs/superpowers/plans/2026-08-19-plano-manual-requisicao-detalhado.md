# Plano — o manual da requisição em detalhe (16 → 24 telas)

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — Fases 1–3 do ciclo de compras, entregues com runbook rodado por script. ⚠️ o code review de 25/08 achou defeitos vivos neste módulo — ver `docs/auditoria/achados-code-review-2026-08-25.md` §5. 🔬 5/5 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


> **Spec:** `docs/superpowers/specs/2026-08-19-manual-requisicao-detalhado-design.md`
> **Ordem de execução:** T1 → T7. Cada tarefa é commitável sozinha, mas o manual
> só é regerado uma vez, na T6.

## T1 — o motor: `Acao` em `scripts/anotar_captura.py`

Acrescentar, ao lado de `Campo` e `Tela`:

```python
@dataclass
class Acao:
    tipo: str          # 'preencher' | 'escolher' | 'marcar' | 'submeter'
    seletor: str
    valor: str = ''
```

e `Tela.acoes: list = _field(default_factory=list)`.

Função `executar(page, acoes)`:

* resolve cada seletor; **não casou, levanta `MarcacaoQuebrada`** com o seletor
  na mensagem — mesma exceção do marcador, porque o modo de falha é o mesmo:
  seguir em frente produz a foto da tela errada;
* `preencher` → `fill`; `escolher` → `select_option`; `marcar` → `check`;
  `submeter` → `click` + `wait_for_load_state('domcontentloaded')`;
* devolve o número de ações executadas (o capturador imprime, para o log dizer
  o que foi feito antes da foto).

**Guarda extra:** `submeter` só pode ser a **última** ação da lista. Ação depois
do POST agiria na página seguinte, que não é a que está sendo fotografada.
Conferido na T5, não em tempo de execução.

## T2 — `scripts/capturar_manual_compras.py` executa as ações

No laço, entre o `goto`/`wait_for_timeout` e o `marcar`:

```python
if tela.acoes:
    n = executar(pg, tela.acoes)
    print(f'      {n} ação(ões) antes da foto')
```

Nada mais muda: a limpeza de modal, o recorte e o relatório de falhas seguem
iguais. A regra do arquivo (falhou, para) já cobre a exceção nova.

## T3 — `scripts/seed_manual_compras.py` ganha a segunda obra

Uma obra `OB-LIMPA` ("Reforma da Sede — janela limpa"), do mesmo cliente e admin,
com vínculo `UsuarioObra` para **solicitante, gestor e comprador** (o solicitante
precisa dela para criar; os outros dois para que a tela não mude de comportamento
por falta de papel).

**Nenhuma requisição nasce nela no seed.** É isso que a torna a janela limpa da
tela `04`.

📌 O resumo impresso pelo seed passa a listar as duas obras — quem roda precisa
ver que são duas, senão a dependência de ordem da T4 vira mistério.

## T4 — `scripts/roteiro_manual_compras.py`: as 8 telas novas

`resolver_ids()` passa a devolver também `obra_limpa` e `obra_manual` (ids das
duas obras, achadas por `codigo`), porque as ações precisam escolher a obra pelo
`value` do `<select>`.

Seletores conferidos nos templates (📖 `requisicoes.html`, `requisicao_nova.html`,
`requisicao_detalhe.html`):

| Tela | Ações | Campos marcados |
|---|---|---|
| `02_lista_requisicoes` | — | `a[href*="/requisicoes/nova"]`, filtro `a[href*="estado="]`, `thead th:nth-child(5)` (valor), `th:nth-child(6)` (estado), `tbody .badge` |
| `03_nova_requisicao` | — | os 10 de hoje **+** `#btnAddItem`, `.btn-remover`, `button[type="submit"]` |
| `04_alcada_no_sucesso` | escolher obra **limpa**, preencher item/qtd/preço, submeter | `.alert` (o flash da alçada) |
| `05_recusa_sem_obra` | preencher item, submeter (sem obra) | `.alert-danger` |
| `06_recusa_sem_item` | escolher obra, submeter (sem item) | `.alert-danger` |
| `07_recusa_emergencia` | escolher obra, marcar emergencial, preencher item, submeter | `.alert-danger` |
| `08_rascunho_itens` | — | (era `04`) |
| `09_enviar` | — | (era `05`) |
| `10_aguardando` | — | `.badge.fs-6` (o estado) — a ausência do botão de editar vai no `atencao`, porque ausência não se marca |
| `11_subiu_de_faixa` | escolher obra **`OB-MANUAL`**, preencher, submeter | `.alert` |
| `12_emergencia` | escolher obra, marcar emergencial, preencher justificativa e item, submeter | `.alert` |
| `17_aprovada_emitir` | — | `form[action*="emitir-pedido"]` |

⚠️ **O campo "total estimado" não existe no formulário** — o spec o mencionava.
Conferido em `requisicao_nova.html`: há `#btnAddItem`, `.btn-remover` e
`button[type="submit"]`, não há total. **Sai do plano em vez de ser inventado.**

⚠️ **`#emergencialAviso` nasce com `d-none`** e campo invisível é falha
deliberada do marcador. Não marcar.

A renumeração de todos os slugs acompanha (`06`→`13` … `16`→`24`).

## T5 — `tests/test_manual_compras_roteiro.py`

Três testes novos, sem browser e sem banco, no espírito dos quatro que já existem:

1. toda `Acao` tem `tipo` na lista conhecida e `seletor` não vazio;
2. tela com `acoes` tem **pelo menos um campo** marcado (recusa sem flash marcado
   é print sem legenda);
3. `submeter`, quando existe, é a **última** ação da tela.

## T6 — regerar e conferir

```bash
python scripts/seed_manual_compras.py
python scripts/capturar_manual_compras.py
python scripts/gerar_manual_compras.py
```

Conferir: **24 PNG** na pasta, o markdown com 24 seções, o PDF gerado, e o log da
captura mostrando as ações. Falha de seletor derruba o processo — é o esperado.

## T7 — registrar

`ESTADO-ATUAL.md`: a atualização do manual **e** o achado de produto — 📖 o
formulário não oferece etapa, mas `compras_views.py:2005-2015` lê e valida
`obra_servico_custo_id`; toda requisição criada pela tela cai no grupo de etapa
NULA, e o agrupamento por etapa do anti-fracionamento é inalcançável por esse
caminho. Fica como pergunta: ou a tela passa a oferecer, ou a leitura é vestigial.
