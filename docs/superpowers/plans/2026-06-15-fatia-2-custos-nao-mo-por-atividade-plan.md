# Plano — Fatia 2: Custos não-MO por atividade (+ subempreitada / telhado viga I)

> Data: 2026-06-15. Branch: `design/espinha-financeira-obra`.
> Obedece ao **plano-mestre** (`2026-06-15-espinha-financeira-plano-mestre.md`) — DC1–DC10.
> Depende da Fatia 1 (read-model + tela). Spec §Fatia 2.
> **Esta fatia carrega a ÚNICA migration da espinha (DC2).** Fatias 3–5 ficam sem migration.

## Status de execução (2026-06-15)

- ✅ **F2-A — schema** (commit 5c85906): **migration 195** (não 193, que já fora usada no delta 1)
  — FK `tarefa_cronograma_id` em `gestao_custo_filho`/`movimentacao_estoque`/`custo_veiculo` +
  `verba_unica`/`lucro_pct`/`gestao_custo_pai_id` em `rdo_subempreitada_apontamento`.
- ✅ **F2-B — read-model** (commit 5c85906): `custo_nao_mo_atividade` (direto + rateio hora-homem),
  `custo_incorrido_atividade`, `alarme_custo` (CPI total), `resultado_obra` enriquecido. **DC3**
  (MO não conta 2×) com teste de regressão. 5 testes.
- ✅ **F2-C subempreitada → custo** (commit 33bfed3): `_registrar_custo_subempreitada` (verba+lucro
  → custo ligado à atividade, idempotente), wired em `apontar_subempreitada`. Teste.
- ⬜ **F2-C material direto na UI**: botão/modal "material direto na atividade" (espelha equipe).
  *Custo de material que cai no nível obra já flui por rateio (F2-B); isto é precisão extra.*
- ⬜ **F2-D telhado viga I**: 🔴 **bloqueado por dado externo** — precisa de verba+lucro+opção A/B/C
  (ver `ESPACO_telhado_viga_i_baia_rev10.md`). O mecanismo de custo (subempreitada) já existe.

## Objetivo

Completar o custo incorrido por atividade: além da MO (Fatia 1), somar **material, alimentação,
transporte, equipamento e subempreitada**. Custo **direto** é etiquetado na origem com
`tarefa_cronograma_id`; custo **compartilhado** é rateado por hora-homem/atividade/dia no read-model
(reúso do helper da Fatia 1, DC6). Inclui o **telhado viga I** como subempreitada verba+lucro com a
venda total travada (DC9).

## Regra de correção mais importante (DC3 — ler antes de tudo)

O custo de MO **já vem** de `RDOCustoDiario` no read-model (Fatia 1). O ledger `GestaoCustoFilho`
**também** tem lançamentos `SALARIO`/`VALE_*` (event_manager.py:751, rdo_custos.py:427). Portanto a
leitura do ledger nesta fatia **exclui** as categorias de MO e auxílios — senão a folha conta duas
vezes. Isso é um teste de regressão obrigatório (Task F2-7).

---

## 1. Arquivos

### Migration (DC2)
- `migrations.py` — nova função `_migration_193_espinha_atividade_fks` + registro `(193, …)`.
- `models.py` — colunas novas nos modelos (fonte de verdade; `db.create_all` cobre DB novo).

### Read-model (extensão; assinaturas estáveis — contrato do mestre)
- `services/resultado_atividade_service.py` — novas funções: `custo_orcado_unitario` (generaliza),
  `custo_nao_mo_atividade`, `custo_incorrido_atividade` (MO + não-MO), `alarme_custo` (generaliza
  `alarme_mo`). `resultado_realizado_atividade` passa a usar `custo_incorrido_atividade`.

### Etiquetagem na origem (custo direto)
- `event_manager.py` — `lancar_custos_rdo` (:751) passa `tarefa_cronograma_id` (quando o RDO tem
  uma única atividade) — opcional/secundário, MO já é lida do RDOCustoDiario.
- `almoxarifado_utils.py` (`adicionar_movimentacao`, :147) — aceitar e gravar `tarefa_cronograma_id`.
- `cronograma_views.py` — endpoint novo "lançar material direto na atividade" (espelha o botão de
  equipe) + estender `apontar_subempreitada` (:917) para gerar custo (verba+lucro).

### Orçamento / telhado
- `services/orcamento_view_service.py` — reúso de `recalcular_item`/`recalcular_orcamento` (margin
  lock). Sem novo código de cálculo; um script cria o item do telhado e recalcula.
- `scripts/incluir_telhado_viga_i.py` — cria o `OrcamentoItem` da subempreitada e trava a venda.

### Testes
- `tests/test_resultado_fatia2_custo_nao_mo.py` — read-model não-MO + DC3 (sem dupla contagem).
- `tests/test_subempreitada_custo.py` — apontamento de subempreitada gera custo na atividade.
- `tests/test_telhado_venda_travada.py` — incluir telhado mantém venda total.

---

## FASE F2-A — Migration única + modelos (DC2)

### Task F2-1 — Colunas nos modelos (fonte de verdade)

- [ ] Em `models.py`, classe `GestaoCustoFilho` (~5045), adicionar após `obra_servico_custo_id`:

```python
    tarefa_cronograma_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    tarefa_cronograma = db.relationship('TarefaCronograma', foreign_keys=[tarefa_cronograma_id])
```

- [ ] Em `MovimentacaoEstoque` (~1991), adicionar após `obra_id`:

```python
    tarefa_cronograma_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
```

- [ ] Em `CustoVeiculo` (~4289), adicionar após `obra_id`:

```python
    tarefa_cronograma_id = db.Column(
        db.Integer,
        db.ForeignKey('tarefa_cronograma.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
```

- [ ] Em `RDOSubempreitadaApontamento` (~5500), adicionar após `observacoes`:

```python
    verba_unica = db.Column(db.Numeric(15, 2), nullable=True)   # custo da subempreitada (verba)
    lucro_pct = db.Column(db.Numeric(5, 2), nullable=True)      # lucro % sobre a verba
    gestao_custo_pai_id = db.Column(
        db.Integer,
        db.ForeignKey('gestao_custo_pai.id', use_alter=True, name='fk_rdosub_gcp'),
        nullable=True,
    )
```

### Task F2-2 — Função de migration idempotente (número 193)

> Idioma do repo: funções `_migration_N_nome(cursor)` com `ALTER TABLE … ADD COLUMN IF NOT EXISTS`,
> registradas na lista de tuplas `(N, descrição, func)` (migrations.py ~linha 4000+). Topo atual = 192.

- [ ] Antes de escrever, **confirmar o próximo número livre**:
  `grep -oE "\([0-9]+, " migrations.py | grep -oE "[0-9]+" | sort -n | tail -3` → usar `max+1` (esperado **193**).
- [ ] Localizar uma migration recente de `ADD COLUMN` para copiar o idioma exato (ex.: a 186 ou 179).
  `grep -n "_migration_186_banco_data_saldo_inicial\|_migration_179_tipo_medicao" migrations.py`
- [ ] Adicionar a função (ajustar abertura de cursor ao padrão local — `raw_connection()`/`db.session.execute(text(...))`, igual à vizinha):

```python
def _migration_193_espinha_atividade_fks(cursor):
    """Espinha financeira (DC2): FKs de atividade para custo não-MO + campos de
    subempreitada (verba+lucro). Idempotente. ON DELETE SET NULL em todas."""
    stmts = [
        "ALTER TABLE gestao_custo_filho "
        "ADD COLUMN IF NOT EXISTS tarefa_cronograma_id INTEGER "
        "REFERENCES tarefa_cronograma(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS idx_gcf_tarefa_cronograma "
        "ON gestao_custo_filho(tarefa_cronograma_id)",

        "ALTER TABLE movimentacao_estoque "
        "ADD COLUMN IF NOT EXISTS tarefa_cronograma_id INTEGER "
        "REFERENCES tarefa_cronograma(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS idx_movest_tarefa_cronograma "
        "ON movimentacao_estoque(tarefa_cronograma_id)",

        "ALTER TABLE custo_veiculo "
        "ADD COLUMN IF NOT EXISTS tarefa_cronograma_id INTEGER "
        "REFERENCES tarefa_cronograma(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS idx_custoveic_tarefa_cronograma "
        "ON custo_veiculo(tarefa_cronograma_id)",

        "ALTER TABLE rdo_subempreitada_apontamento "
        "ADD COLUMN IF NOT EXISTS verba_unica NUMERIC(15,2)",
        "ALTER TABLE rdo_subempreitada_apontamento "
        "ADD COLUMN IF NOT EXISTS lucro_pct NUMERIC(5,2)",
        "ALTER TABLE rdo_subempreitada_apontamento "
        "ADD COLUMN IF NOT EXISTS gestao_custo_pai_id INTEGER "
        "REFERENCES gestao_custo_pai(id) ON DELETE SET NULL",

        # Grill 2026-06-15 / ADR 0005 — distingue Proposta de importacao da comercial
        "ALTER TABLE propostas_comerciais "
        "ADD COLUMN IF NOT EXISTS origem VARCHAR(30)",
    ]
    for s in stmts:
        cursor.execute(s)
```

- [ ] Registrar na lista de migrations (junto às tuplas existentes):

```python
            (193, "Espinha financeira — FKs de atividade (gestao_custo_filho, "
                  "movimentacao_estoque, custo_veiculo) + verba/lucro em "
                  "rdo_subempreitada_apontamento", _migration_193_espinha_atividade_fks),
```

- [ ] Rodar a app/o runner de migration uma vez e conferir em `migration_history` que a 193 ficou
  `success` (ou rodar `python -c "from app import app; ..."` conforme `pre_start.py`).
- [ ] **Commit:** `feat(db): migration 193 — FKs de atividade para a espinha financeira (custo não-MO + subempreitada)`

---

## FASE F2-B — Read-model: custo não-MO + custo incorrido + alarme generalizado

### Task F2-3 — Generalizar `custo_orcado_unitario` (DC5) (RED→GREEN)

- [ ] Teste em `tests/test_resultado_fatia2_custo_nao_mo.py`:

```python
def test_custo_orcado_unitario_por_tipos():
    from services.resultado_atividade_service import custo_orcado_unitario
    snap = [
        {'tipo': 'MAO_OBRA', 'unidade': 'h', 'subtotal_unitario': 10.0},
        {'tipo': 'MATERIAL', 'unidade': 'm2', 'subtotal_unitario': 40.0},
        {'tipo': 'OUTROS', 'unidade': 'vb', 'subtotal_unitario': 5.0},
    ]
    from decimal import Decimal
    assert custo_orcado_unitario(snap, {'MAO_OBRA'}) == Decimal('10.0')
    assert custo_orcado_unitario(snap, {'MATERIAL', 'OUTROS'}) == Decimal('45.0')
    assert custo_orcado_unitario(snap, None) == Decimal('55.0')   # None = todos
```

- [ ] Implementar (e refatorar `custo_mo_orcado_unitario` para delegar — sem quebrar a Fatia 1):

```python
def custo_orcado_unitario(composicao_snapshot, tipos=None):
    """Custo orçado por UMA unidade de serviço, somando subtotal_unitario das
    linhas cujo tipo está em `tipos` (None = todos). Função pura."""
    total = Decimal('0')
    for linha in (composicao_snapshot or []):
        tp = (linha.get('tipo') or '').upper()
        if tipos is None or tp in tipos:
            total += _D(linha.get('subtotal_unitario'))
    return total


def custo_mo_orcado_unitario(composicao_snapshot):
    return custo_orcado_unitario(composicao_snapshot, {'MAO_OBRA'})
```

- [ ] Rodar. **Commit:** `refactor(resultado): custo_orcado_unitario generaliza MO/material/outros (DC5)`

### Task F2-4 — `custo_nao_mo_atividade` (ledger etiquetado + rateio, DC3+DC6) (RED→GREEN)

- [ ] Teste (cobre direto, compartilhado e a exclusão de MO):

```python
def test_custo_nao_mo_direto_e_rateio_sem_dupla_contagem(ambiente, builders):
    """- material etiquetado na atividade entra direto;
       - alimentação no nível obra é rateada por hora-homem/atividade;
       - SALARIO/VALE_* no ledger NÃO entram (já estão no RDOCustoDiario — DC3)."""
    from services.resultado_atividade_service import custo_nao_mo_atividade
    from decimal import Decimal
    # … builders criam: tarefa T com 8h apontadas (1 func), e:
    #   GestaoCustoFilho MATERIAL R$100 com tarefa_cronograma_id=T   → direto
    #   GestaoCustoFilho ALIMENTACAO R$60 obra_id=obra, sem tarefa    → rateio (T tem 100% das horas)
    #   GestaoCustoFilho SALARIO R$500 obra_id=obra                   → IGNORADO (DC3)
    assert custo_nao_mo_atividade(T) == Decimal('160.00')   # 100 + 60, sem os 500
```

- [ ] Implementar. Usa o helper de horas extraído da Fatia 1 (DC6):

```python
from models import GestaoCustoFilho, GestaoCustoPai, RDO

_CATEGORIAS_MO = {'SALARIO', 'MAO_OBRA_DIRETA', 'VALE_ALIMENTACAO', 'VALE_TRANSPORTE'}


def _ledger_nao_mo_query(obra_id):
    """Lançamentos do ledger da obra que NÃO são MO (DC3)."""
    return (
        db.session.query(GestaoCustoFilho, GestaoCustoPai.tipo_categoria)
        .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
        .filter(GestaoCustoFilho.obra_id == obra_id)
        .filter(~GestaoCustoPai.tipo_categoria.in_(_CATEGORIAS_MO))
    )


def _horas_obra_por_dia(obra_id, data):
    """Total de hora-homem apontado na obra num dia (denominador do rateio, DC6)."""
    return _D(
        db.session.query(db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0))
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .filter(RDO.obra_id == obra_id, RDO.data_relatorio == data)
        .scalar()
    )


def _horas_atividade_por_dia(tarefa_id, data):
    return _D(
        db.session.query(db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0))
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .filter(RDOMaoObra.tarefa_cronograma_id == tarefa_id, RDO.data_relatorio == data)
        .scalar()
    )


def custo_nao_mo_atividade(tarefa):
    """Custo não-MO da atividade (Fatia 2):
       (a) DIRETO: GestaoCustoFilho com tarefa_cronograma_id == tarefa.id;
       (b) COMPARTILHADO: lançamentos do dia sem tarefa, rateados pela fração de
           hora-homem da atividade naquele dia (DC6).
       Exclui categorias de MO (DC3)."""
    total = Decimal('0')
    for filho, _cat in _ledger_nao_mo_query(tarefa.obra_id).all():
        if filho.tarefa_cronograma_id == tarefa.id:
            total += _D(filho.valor)                       # (a) direto
        elif filho.tarefa_cronograma_id is None:
            dia = filho.data_referencia
            h_obra = _horas_obra_por_dia(tarefa.obra_id, dia)
            if h_obra > 0:
                frac = _horas_atividade_por_dia(tarefa.id, dia) / h_obra
                total += _D(filho.valor) * frac            # (b) rateio
        # se tem tarefa_cronograma_id de OUTRA tarefa → ignora (é dela)
    return _q(total)
```

- [ ] Rodar. **Commit:** `feat(resultado): custo_nao_mo_atividade (direto+rateio, sem dupla contagem MO — DC3/DC6)`

### Task F2-5 — `custo_incorrido_atividade` + `resultado` usa o total (GREEN)

- [ ] Teste:

```python
def test_custo_incorrido_soma_mo_e_nao_mo(ambiente, builders):
    from services.resultado_atividade_service import (
        custo_incorrido_atividade, resultado_realizado_atividade,
    )
    # T: custo MO 300 (via RDOCustoDiario) + não-MO 160 = 460; agregado 1000 → resultado 540
    ...
    assert custo_incorrido_atividade(T) == Decimal('460.00')
    assert resultado_realizado_atividade(T) == Decimal('540.00')
```

- [ ] Implementar:

```python
def custo_incorrido_atividade(tarefa):
    """Custo incorrido total da atividade = MO (Fatia 1) + não-MO (Fatia 2)."""
    return _q(custo_mo_atividade(tarefa) + custo_nao_mo_atividade(tarefa))
```

- [ ] Atualizar `resultado_realizado_atividade` para usar o total (sem mudar assinatura):

```python
def resultado_realizado_atividade(tarefa):
    return _q(valor_agregado_atividade(tarefa) - custo_incorrido_atividade(tarefa))
```

- [ ] Atualizar `resultado_obra` para reportar `custo_mo`, `custo_nao_mo` e `custo_incorrido`
  (enriquecer o dict, sem quebrar chaves existentes — contrato do mestre).
- [ ] Rodar a suíte da Fatia 1 também (não pode regredir):
  `python -m pytest tests/test_resultado_atividade_service.py -x`
- [ ] **Commit:** `feat(resultado): custo_incorrido_atividade = MO + não-MO`

### Task F2-6 — `alarme_custo` generaliza `alarme_mo` (CPI base p/ Fatia 3, DC7) (RED→GREEN)

- [ ] Teste: orçado total (todos os tipos) vs custo incorrido total.
- [ ] Implementar generalização (mantendo `alarme_mo` como caso particular):

```python
def custo_orcado_atividade_por_tipos(tarefa, tipos=None):
    """Orçado da atividade somando os tipos pedidos (None=todos), via snapshot×qtd×peso."""
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item or not item.proposta_item_id:
            continue
        pi = db.session.get(PropostaItem, item.proposta_item_id)
        if not pi:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        unit = custo_orcado_unitario(pi.composicao_snapshot, tipos)
        qtd = _D(item.quantidade) if item.quantidade is not None else _D(pi.quantidade)
        total += unit * qtd * (_D(link.peso) / soma_peso)
    return _q(total)


def alarme_custo(tarefa):
    """Alarme em R$ sobre o custo TOTAL (CPI): orçado-para-o-avanço vs incorrido."""
    perc = _D(tarefa.percentual_concluido) / CEM
    orcado_total = custo_orcado_atividade_por_tipos(tarefa, None)   # todos os tipos
    orcado_para_avanco = _q(orcado_total * perc)
    real = custo_incorrido_atividade(tarefa)
    indice = (orcado_para_avanco / real).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP) \
        if real > 0 else None
    return {
        'orcado_total': orcado_total, 'orcado_para_avanco': orcado_para_avanco,
        'real': real, 'estouro': real > orcado_para_avanco, 'indice_rs': indice,
    }
```
(`custo_mo_orcado_atividade` da Fatia 1 vira `custo_orcado_atividade_por_tipos(tarefa, {'MAO_OBRA'})`.)

- [ ] Atualizar a tela da Fatia 1 (`templates/resultado/por_atividade.html`) para mostrar o alarme de
  custo total além do de MO (ou substituir, conforme preferência) — colunas: custo MO, custo não-MO,
  custo total, alarme total.
- [ ] **Commit:** `feat(resultado): alarme_custo (CPI sobre custo total) + colunas não-MO na tela`

### Task F2-7 — Teste de regressão DC3 (sem dupla contagem) — **obrigatório**

- [ ] Teste end-to-end: lançar 1 RDO (gera RDOCustoDiario MO + GestaoCustoFilho SALARIO) e conferir
  que `custo_incorrido_atividade` == custo MO do RDOCustoDiario + não-MO, **sem** somar o SALARIO do
  ledger. Este é o guardião do risco R1/R2.
- [ ] **Commit:** `test(resultado): regressão DC3 — MO não conta duas vezes`

---

## FASE F2-C — Etiquetar custo direto na origem

### Task F2-8 — Material consumido na atividade (espelha o botão de equipe)

- [ ] `almoxarifado_utils.py:adicionar_movimentacao` (~147): aceitar `tarefa_cronograma_id` em kwargs
  e gravá-lo no `MovimentacaoEstoque(...)`. Mudança mínima:

```python
        tarefa_cronograma_id=kwargs.get('tarefa_cronograma_id'),
```

- [ ] Onde o material vira **custo** no ledger (a entrada `material_entrada` em event_manager.py:129
  ou o caminho de compra `compras_views.py:195`), passar `tarefa_cronograma_id` para
  `registrar_custo_automatico(...)` quando a saída/consumo estiver vinculada a uma atividade.
- [ ] UI: endpoint novo em `cronograma_views.py` espelhando o painel de equipe
  (`templates/rdo/novo.html` `_cronTaskEquipe`/`cron_tarefa_*`): "lançar material direto na
  atividade". Reusar o GET `/cronograma/obra/<id>/tarefas-rdo` (:809) para listar atividades. Form
  posta `material_tarefa_<tarefaId>_...`; handler grava a movimentação com `tarefa_cronograma_id`.
  *(Detalhar a UI no momento da implementação, seguindo o idiom do painel de equipe.)*
- [ ] Teste: material lançado na atividade aparece como custo direto em `custo_nao_mo_atividade`.
- [ ] **Commit:** `feat(material): consumo etiquetável por atividade (FK + UI espelhando equipe)`

### Task F2-9 — Subempreitada → custo por atividade (RED→GREEN)

- [ ] `cronograma_views.py:apontar_subempreitada` (:917): após `apt.calcular_homem_hora()`, se vier
  `verba_unica`/`lucro_pct`, registrar o custo ligado à atividade e guardar o pai p/ idempotência:

```python
        verba = float(data.get('verba_unica', 0) or 0)
        lucro = float(data.get('lucro_pct', 0) or 0)
        if verba > 0:
            from decimal import Decimal as _Dec
            apt.verba_unica = _Dec(str(verba))
            apt.lucro_pct = _Dec(str(lucro))
            custo_total = _Dec(str(verba)) * (1 + _Dec(str(lucro)) / 100)
            from utils.financeiro_integration import registrar_custo_automatico
            from models import ObraServicoCusto
            osc_id = None
            if tarefa.servico_id:
                osc = ObraServicoCusto.query.filter_by(
                    obra_id=tarefa.obra_id, servico_id=tarefa.servico_id, admin_id=admin_id,
                ).first()
                osc_id = osc.id if osc else None
            filho = registrar_custo_automatico(
                admin_id=admin_id, tipo_categoria='SUBEMPREITADA',
                entidade_nome=sub.nome, entidade_id=sub.id,
                data=rdo.data_relatorio,
                descricao=f"Subempreitada {sub.nome} — {tarefa.nome_tarefa}",
                valor=custo_total, obra_id=tarefa.obra_id,
                origem_tabela='rdo_subempreitada_apontamento', origem_id=apt.id,
                obra_servico_custo_id=osc_id, force_v2=True,
            )
            # NOVO: etiquetar o lançamento com a atividade (DC2 deu a FK)
            if filho:
                filho.tarefa_cronograma_id = tarefa.id
                apt.gestao_custo_pai_id = filho.pai_id
```

- [ ] **Idempotência:** ao reeditar o apontamento, remover o custo anterior (por
  `origem_tabela='rdo_subempreitada_apontamento'`, `origem_id=apt.id`) antes de recriar — espelhar
  `remover_custos_rdo` (rdo_custos.py).
- [ ] Teste em `tests/test_subempreitada_custo.py`: apontar subempreitada com verba+lucro cria um
  `GestaoCustoFilho` `SUBEMPREITADA` com `tarefa_cronograma_id` da atividade; reeditar não duplica.
- [ ] **Commit:** `feat(subempreitada): apontamento gera custo verba+lucro por atividade`

---

## FASE F2-D — Telhado viga I (DC9)

### Task F2-10 — Decisão de absorção da venda (precisa do usuário)

- [ ] **Bloqueio de dados** (ver `ESPACO_telhado_viga_i_baia_rev10.md`): obter do usuário
  **(1)** valor da verba do subempreiteiro, **(2)** lucro %, **(3)** opção A/B/C de absorção. Sem
  isso, não dá para travar a venda. Registrar a resposta no espaço.

### Task F2-11 — Incluir o item e travar a venda total (reúso do margin lock)

- [ ] Criar `scripts/incluir_telhado_viga_i.py`: cria 1 `OrcamentoItem` no ORC-BAIA-REV10 (id 98) com
  `composicao_snapshot` de **uma linha** (subempreitada como custo) e chama
  `recalcular_item` + `recalcular_orcamento` (orcamento_view_service.py:79,325). Para a opção B
  (markup uniforme), ajustar `orcamento.margem_pct_global` até `venda_total == 1720796.75`; para a A,
  reduzir margens dos demais proporcionalmente. *(O cálculo concreto depende da Task F2-10.)*
- [ ] Teste `tests/test_telhado_venda_travada.py`: após incluir o telhado e recalcular,
  `orcamento.venda_total == Decimal('1720796.75')` (tolerância de centavos).
- [ ] Regenerar proposta/apresentação/importação se necessário (fluxo existente).
- [ ] No cronograma: as atividades "ESTRUTURA METÁLICA/FABRICAÇÃO DE AÇO PARA TELHADO" passam a ter
  item/venda para medir, `responsavel='terceiros'`.
- [ ] **Commit:** `feat(orcamento): telhado viga I como subempreitada, venda total travada (DC9)`

---

## Revisão final (Fatia 2)
- [ ] Cobertura spec §Fatia 2: FK em GestaoCustoFilho ✅(F2-1/2) · direto+rateio ✅(F2-4) · subempreitada→custo ✅(F2-9) · telhado ✅(F2-10/11) · custo_incorrido = MO+direto+rateio+subempreitada ✅(F2-5).
- [ ] DC3 (sem dupla contagem) coberto por F2-7. DC2 (migration única) por F2-2. DC6 (rateio reúso) por F2-4. DC9 por F2-11.
- [ ] Sem placeholders: pontos dependentes de dado externo (número da migration, ids da Baia, verba/lucro/opção do telhado) marcados como passo de verificação/bloqueio explícito.
- [ ] Tipos: read-model continua em Decimal `0.01`; categorias em strings MAIÚSCULAS conforme `_CATEGORIA_LEGADA_MAP`.
