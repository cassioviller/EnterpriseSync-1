# Alimentação e Transporte ganham o campo "Etapa" (Pedaço 4)

> Data: 2026-06-29. Obra-piloto: Baia.
> Parte 4 da iniciativa "custo realizado por lançamentos amarrados à etapa".
> Contexto: `2026-06-29-compras-campo-etapa-design.md` (padrão validado no Pedaço 3) e
> `2026-06-29-realizado-por-lancamentos-design.md` (visão completa).
> Pedaços 1-3 implementados (realizado por lançamentos, categoria de fluxo de caixa, Compras).

## Onde este pedaço entra

A visão é que todo módulo de custo (Compras, Alimentação, Transporte, diárias do RDO, Folha…)
nasça ligado à obra **e** à etapa, fluindo ao Realizado da etapa. O Pedaço 3 fez **Compras** e
validou o padrão. Este pedaço aplica o mesmo padrão a **Alimentação** e **Transporte** — os dois
módulos restantes que já criam custo via `registrar_custo_automatico` (que aceita
`obra_servico_custo_id` desde o Pedaço 2). É só passar a etapa.

**Mapa dos demais módulos (do levantamento):**

| Módulo | Cria custo via | Já amarra etapa? |
|---|---|---|
| Compras | manual (`processar_compra_normal`) | ✅ Pedaço 3 |
| Alimentação | `registrar_custo_automatico('ALIMENTACAO')` | ❌ — **este pedaço** |
| Transporte | `registrar_custo_automatico('TRANSPORTE')` | ❌ — **este pedaço** |
| RDO / mão de obra | `registrar_custo_automatico('SALARIO')`, origem `registro_ponto` | ✅ já (auto via `resolver_obra_servico_custo_id`) |
| Folha | monta `GestaoCustoPai/Filho` à mão, **sem `obra_id`** | ❌ — fora de escopo (precisa rateio) |

## Problema

- **Alimentação** (`alimentacao_views.py`): o lançamento (`AlimentacaoLancamento`) tem `obra_id`
  (NOT NULL), e a integração chama `registrar_custo_automatico(tipo_categoria='ALIMENTACAO',
  obra_id=obra.id, ...)` **sem `obra_servico_custo_id`**. Logo o custo não cai em etapa nenhuma.
- **Transporte** (`transporte_views.py`, `novo_post`): `LancamentoTransporte` tem `obra_id`
  (obrigatória no form), e chama `registrar_custo_automatico(tipo_categoria='TRANSPORTE',
  obra_id=obra_id, ...)` **sem `obra_servico_custo_id`**.

Ambos têm **uma obra por lançamento** (cabeçalho), então a etapa é um **único select** em
cascata — exatamente como o Compras.

## Decisões (acordadas no brainstorming)

- **Escopo: Alimentação + Transporte juntos** neste pedaço (mesmo padrão simples).
- **Etapa OPCIONAL** (consistente com Compras). Sem etapa → comportamento atual preservado.
  Etapa inválida/de outra obra → tratada como `None` (nunca derruba o lançamento).
- **Grava em dois lugares** (consistente com Compras): coluna `obra_servico_custo_id` na
  entidade do módulo (rastreabilidade) **e** repassada à `registrar_custo_automatico` (o que faz
  o realizado somar).
- **RDO**: já amarra a etapa automaticamente (`origem_tabela='registro_ponto'`, `osc_id` via
  `resolver_obra_servico_custo_id`). Sem mudança de código — só um teste de regressão.
- **Folha**: fora de escopo (folha é da empresa, sem `obra_id`; exige rateio/apropriação por
  obra — iniciativa própria).

## Modelo de dados

- **`AlimentacaoLancamento.obra_servico_custo_id`** — `db.Column(db.Integer,
  db.ForeignKey('obra_servico_custo.id'), nullable=True)` + relationship
  `obra_servico_custo = db.relationship('ObraServicoCusto', foreign_keys=[obra_servico_custo_id])`.
- **`LancamentoTransporte.obra_servico_custo_id`** — idem (FK nullable) + relationship.
- `GestaoCustoFilho.obra_servico_custo_id` já existe — passa a ser preenchido por estes módulos.

### Migração 206

`migrations.py`, após `_migration_205_pedido_compra_obra_servico_custo`, idempotente, padrão do
repo — uma função que adiciona as **duas** colunas:

```python
def _migration_206_alimentacao_transporte_obra_servico_custo():
    """Alimentação/Transporte por etapa — adiciona obra_servico_custo_id em
    alimentacao_lancamento e lancamento_transporte (FK p/ obra_servico_custo).
    Idempotente. Ver spec 2026-06-29-alimentacao-transporte-campo-etapa-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            for tabela in ('alimentacao_lancamento', 'lancamento_transporte'):
                conn.execute(sa_text(
                    f"ALTER TABLE {tabela} "
                    "ADD COLUMN IF NOT EXISTS obra_servico_custo_id INTEGER "
                    "REFERENCES obra_servico_custo(id)"))
        logger.info("[Migration 206] obra_servico_custo_id adicionada em alimentacao_lancamento e lancamento_transporte.")
    except Exception as e:
        logger.error(f"[Migration 206] Falha: {e}", exc_info=True)
        raise
```

Registrar na lista `migrations_to_run`, após a 205:

```python
            (206, "Alimentação/Transporte por etapa — obra_servico_custo_id", _migration_206_alimentacao_transporte_obra_servico_custo),
```

## Backend

Reusa o endpoint `GET /obras/<id>/etapas-custo` (Pedaço 3) para o cascata; nenhuma rota nova.

### Alimentação (`alimentacao_views.py`)

No POST que cria o `AlimentacaoLancamento` (a obra já é validada: `obra_id = int(request.form['obra_id'])`
→ `obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()`):

- Ler e validar a etapa: `obra_servico_custo_id` do form; se preenchido e pertencer à
  `ObraServicoCusto(obra_id=obra.id, admin_id=admin_id)`, usar; senão `None`.
- Gravar `obra_servico_custo_id` no `AlimentacaoLancamento`.
- Passar `obra_servico_custo_id=<resolvido>` na chamada `registrar_custo_automatico(...)`
  (tipo_categoria='ALIMENTACAO').

### Transporte (`transporte_views.py`, `novo_post`)

Após a validação de `obra_id` (já obrigatória):

- Ler e validar a etapa: `obra_servico_custo_id` do form; se pertencer à obra+tenant, usar;
  senão `None`.
- Gravar `obra_servico_custo_id` no `LancamentoTransporte`.
- Passar `obra_servico_custo_id=<resolvido>` na chamada `registrar_custo_automatico(...)`
  (tipo_categoria='TRANSPORTE'). O `CustoObra` legado continua como está (não recebe etapa).

## Exibição no Realizado da etapa

`ALIMENTACAO` e `TRANSPORTE` não são `FATURAMENTO_DIRETO`, então `realizado_por_etapa` /
`curva_realizado` / `lancamentos_da_etapa` já os somam por `obra_servico_custo_id`. Estender o
mapa `_ORIGEM_LABELS` (em `services/cronograma_fisico_financeiro.py`) para rótulos amigáveis e
só-leitura na aba (só `lancamento_periodo_manual` é editável):

```python
_ORIGEM_LABELS = {
    'lancamento_periodo_manual': 'Manual',
    'pedido_compra': 'Compra',
    'alimentacao_lancamento': 'Alimentação',
    'lancamento_transporte': 'Transporte',
    'registro_ponto': 'Mão de obra',
    'registro_ponto_va': 'Vale alimentação',
    'registro_ponto_vt': 'Vale transporte',
}
```

## UI

Padrão do Compras (select Etapa em cascata, opcional, alimentado por `/obras/<id>/etapas-custo`).

### Alimentação (`templates/alimentacao/lancamento_novo_v2.html`)

Após o `<select name="obra_id" id="obra_id">`, adicionar um `<select name="obra_servico_custo_id"
id="oscSelect">` (opção inicial "— Sem etapa —", desabilitado). JS: ao mudar `#obra_id`, faz
`fetch('/obras/<id>/etapas-custo')` e popula; limpa/desabilita quando a obra fica vazia.

### Transporte (`templates/transporte/novo_lancamento.html`)

O `<select name="obra_id">` (l.78) não tem `id` — adicionar `id="obraSelect"`. Depois dele,
inserir `<select name="obra_servico_custo_id" id="oscSelect">` com o mesmo comportamento de
cascata.

## Testes

- **Colunas:** `AlimentacaoLancamento.__table__` e `LancamentoTransporte.__table__` têm
  `obra_servico_custo_id`.
- **Alimentação grava a etapa:** criar lançamento (via view ou montando o registro e chamando o
  caminho de integração) com `obra_servico_custo_id` → o `AlimentacaoLancamento` e o
  `GestaoCustoFilho` (`origem_tabela='alimentacao_lancamento'`) ficam com a etapa; `realizado_por_etapa`
  soma. Etapa de outra obra → `None`.
- **Transporte grava a etapa:** `POST /transporte/novo` com `obra_servico_custo_id` → o
  `LancamentoTransporte` e o `GestaoCustoFilho` (`origem_tabela='lancamento_transporte'`) ficam
  com a etapa; `realizado_por_etapa` soma. Etapa inválida → `None`.
- **`origem_label`:** `lancamentos_da_etapa` mostra "Alimentação" e "Transporte" (e "Mão de obra"
  para `registro_ponto`), todos `editavel=False`.
- **RDO (regressão):** uma diária de RDO (`origem_tabela='registro_ponto'`) com
  `obra_servico_custo_id` aparece no realizado da etapa e em `lancamentos_da_etapa` com
  `origem_label='Mão de obra'`, `editavel=False`.
- **Invariantes da Baia** preservados; suíte financeira + de cada módulo verde:
  `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
  (mais os testes de alimentação/transporte existentes, se houver — ver `tests/`).
- **UI** (cascata Obra→Etapa nos dois forms + custos aparecendo no Realizado) verificada no
  browser real (Playwright/chromium do Nix).

## Invariantes da Baia

- **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 /
  contrato 1.505.613,76 / data_fim 08/10.
- **Realizado** continua vindo de `GestaoCustoFilho` ligados às etapas; agora alimentação e
  transporte com etapa também somam.

## Fora de escopo (Pedaço 4)

- **Folha** (rateio/apropriação por obra) — iniciativa própria.
- Mudança no `CustoObra` legado (de alimentação/transporte) — mantido como está.
- Override manual de etapa no RDO (hoje é automático por serviço único) — futuro, se necessário.
- Editar a etapa de um lançamento já criado.
</content>
