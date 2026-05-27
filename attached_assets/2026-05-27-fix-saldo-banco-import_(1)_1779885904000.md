# Fix #1 — Saldo Bancário: Desacoplar Import + Arquitetura de Cálculo Real

**Data:** 2026-05-27  
**Escopo:** `importacao_views.py`, `gestao_custos_views.py`, `financeiro_service.py`, `BancoEmpresa`, `FluxoCaixa`  
**Tipo:** Bug crítico + pré-condição para saldo derivado

---

## Problema central

`fluxo_caixa_confirmar()` commita saldo bancário **antes** de iniciar o import:

```python
db.session.commit()      # ← saldo gravado
svc.importar(...)        # ← se falhar, saldo errado, import inexistente
```

Esse é o bug a corrigir agora. O resto deste spec define o caminho para que
`saldo_atual` seja eventualmente derivado de lançamentos reais — mas isso requer
uma pré-condição que ainda não existe.

---

## Decisão 1 — Arquitetura de saldo_atual: on-the-fly, sem persistência

`saldo_atual` não será mais uma coluna gravada. Será uma função que computa
sob demanda:

```
calcular_saldo_banco(banco_id, admin_id) =
    banco.saldo_inicial
    + Σ FluxoCaixa ENTRADA  (banco_id = id, data_movimento >= data_saldo_inicial)
    - Σ FluxoCaixa SAIDA    (banco_id = id, data_movimento >= data_saldo_inicial)
```

**Por que on-the-fly e não persistido com staleness marker:**  
Persistir um valor derivado exige hookar todos os pontos de escrita de `FluxoCaixa`.
Existem hoje pelo menos 4 pontos ativos de criação — 2 deles em `gestao_custos_views.py`
sem `banco_id`. Qualquer hook que se esqueça de um ponto produz staleness silencioso,
que é exatamente o problema que o staleness marker promete resolver mas não resolve
(o marker só diz que está defasado, não corrije). On-the-fly elimina a classe inteira
do problema ao custo de uma query indexada por leitura.

**Pré-condição bloqueante:** on-the-fly só produz número correto quando
`banco_id` é confiável em todos os registros relevantes. Isso não é verdade hoje.
A coluna `saldo_atual` em `BancoEmpresa` é mantida intocada até que a
pré-condição abaixo seja atendida.

**Requisito de performance:** index composto `(banco_id, data_movimento)` em
`fluxo_caixa` — já existente via `banco_id` FK. Confirmar ou adicionar index
explícito na migração.

---

## Decisão 2 — Pré-condição: banco_id obrigatório em todos os pontos de escrita

### Problema real

`banco_id` é nullable em `FluxoCaixa` e está ausente em dois pontos ativos:

| Arquivo | Função | banco_id? |
|---------|--------|-----------|
| `gestao_custos_views.py` ~L727 | pagamento de GestaoCustoPai | ❌ ausente |
| `gestao_custos_views.py` ~L847 | pagamento parcial | ❌ ausente |
| `financeiro_views.py` ~L387 | lançamento direto | ✅ presente |
| `financeiro_views.py` ~L758 | lançamento direto | ✅ presente |
| `services/importacao_excel.py` | import de fluxo | ✅ presente |

Enquanto `banco_id` for ausente nesses pontos, qualquer cálculo derivado
produz saldo menor que o real sem nenhum aviso. Não há solução de backfill
para registros históricos sem banco_id — não se sabe a qual banco pertencem.

### O que este spec define como escopo obrigatório

Antes de ativar `calcular_saldo_banco()` como fonte de verdade:

1. **`gestao_custos_views.py` — dois pontos de criação de FluxoCaixa** precisam
   receber `banco_id` como campo obrigatório no form de pagamento. Se o usuário
   não selecionar um banco, o lançamento não cria FluxoCaixa (comportamento atual
   já tem checkbox "criar lançamento no fluxo de caixa" — esse checkbox passa a
   exigir banco selecionado).

2. **Registros históricos sem `banco_id`** ficam fora do cálculo derivado para sempre,
   a menos que o usuário os vincule manualmente via uma UI de reconciliação
   (fora do escopo deste spec). A função `calcular_saldo_banco()` deve logar
   quantos lançamentos do banco têm `banco_id = NULL` no período calculado,
   para que o resultado possa ser marcado como "parcial" na UI se necessário.

### O que NÃO é backfill automático

Não existe migração que atribua `banco_id` a lançamentos históricos — não há
dado no registro que permita inferir o banco com segurança. A tentativa
produziria dados falsos. Lançamentos sem `banco_id` ficam fora do cálculo
e isso é comunicado explicitamente.

---

## Decisão 3 — Semântica de data_saldo_inicial

Nova coluna em `BancoEmpresa`:

```python
data_saldo_inicial = db.Column(db.Date, nullable=True)
```

**Regra de negócio:**

| saldo_inicial | data_saldo_inicial | Comportamento |
|---|---|---|
| 0 | NULL | soma todos os FluxoCaixa do banco desde sempre |
| > 0 | NULL | inválido — validação impede salvar |
| > 0 | data X | `saldo_inicial` representa saldo em X; soma FluxoCaixa a partir de X |

**Por que `saldo_inicial > 0` + `data_saldo_inicial = NULL` é inválido:**  
`saldo_inicial` existe para representar lançamentos históricos que não estão
no sistema. Se `data_saldo_inicial` for NULL, o cálculo somaria `saldo_inicial`
(que já resume um período) mais todos os lançamentos desde sempre — dupla
contagem garantida. A validação deve ser feita na camada de serviço ao salvar
`BancoEmpresa`, não apenas na UI.

---

## O que muda em cada arquivo

### Fase 1 — Fix imediato (bug do commit antecipado)

**`importacao_views.py` — `fluxo_caixa_confirmar()`:**
- Remover bloco `"Atualizar Saldo Inicial de Bancos"` (~20 linhas)
- Remover campos `saldo_inicial_<id>` do template `preview_fluxo.html`
- Resultado: import passa a ter uma única transação atômica

**`models.py` — `BancoEmpresa`:**
- Adicionar `data_saldo_inicial = db.Column(db.Date, nullable=True)`
- Manter `saldo_atual` como está (ainda não é calculado on-the-fly)

**`migrations.py` — migração 186:**
```sql
ALTER TABLE banco_empresa
  ADD COLUMN IF NOT EXISTS data_saldo_inicial DATE;

CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_banco_data
  ON fluxo_caixa (banco_id, data_movimento)
  WHERE banco_id IS NOT NULL;
```

---

### Fase 2 — Pré-condição (banco_id obrigatório nos pagamentos)

**`gestao_custos_views.py` — dois pontos de criação de FluxoCaixa:**
- Form de pagamento passa a exigir `banco_id` quando "criar lançamento no FC" está marcado
- `FluxoCaixa(banco_id=banco_id_form, ...)` nos dois pontos
- Validação: se `banco_id` não informado e checkbox marcado → erro de validação, não cria FC

---

### Fase 3 — Saldo on-the-fly (só após Fase 2 em produção)

**`financeiro_service.py` — nova função:**

```python
def calcular_saldo_banco(banco_id: int, admin_id: int) -> dict:
    """
    Retorna {'saldo': Decimal, 'cobertura_total': int, 'sem_banco_id': int}
    Não persiste nada. Não faz commit.
    """
    banco = BancoEmpresa.query.filter_by(id=banco_id, admin_id=admin_id).first()
    if not banco:
        raise ValueError(f'BancoEmpresa {banco_id} não encontrado para admin {admin_id}')

    q = FluxoCaixa.query.filter(
        FluxoCaixa.admin_id == admin_id,
        FluxoCaixa.banco_id == banco_id,
    )
    if banco.data_saldo_inicial:
        q = q.filter(FluxoCaixa.data_movimento >= banco.data_saldo_inicial)

    entradas = db.session.query(
        db.func.coalesce(db.func.sum(FluxoCaixa.valor), 0)
    ).filter(
        FluxoCaixa.admin_id == admin_id,
        FluxoCaixa.banco_id == banco_id,
        FluxoCaixa.tipo_movimento == 'ENTRADA',
        *([] if not banco.data_saldo_inicial else
          [FluxoCaixa.data_movimento >= banco.data_saldo_inicial])
    ).scalar()

    saidas = db.session.query(
        db.func.coalesce(db.func.sum(FluxoCaixa.valor), 0)
    ).filter(
        FluxoCaixa.admin_id == admin_id,
        FluxoCaixa.banco_id == banco_id,
        FluxoCaixa.tipo_movimento == 'SAIDA',
        *([] if not banco.data_saldo_inicial else
          [FluxoCaixa.data_movimento >= banco.data_saldo_inicial])
    ).scalar()

    sem_banco_id = FluxoCaixa.query.filter(
        FluxoCaixa.admin_id == admin_id,
        FluxoCaixa.banco_id == None,
    ).count()

    saldo = Decimal(str(banco.saldo_inicial or 0)) + Decimal(str(entradas)) - Decimal(str(saidas))

    return {
        'saldo': saldo,
        'cobertura_parcial': sem_banco_id > 0,
        'sem_banco_id': sem_banco_id,
    }
```

**`BancoEmpresa` — coluna `saldo_atual` drop (migração 187, após Fase 2 validada):**

```sql
-- Só executar após confirmar que banco_id está preenchido em >= 95% dos FluxoCaixa
ALTER TABLE banco_empresa DROP COLUMN IF EXISTS saldo_atual;
```

Esta migração é separada e só executa após validação manual de cobertura.

---

## Sequência de execução

```
Fase 1  → remove bug imediato, sem risco
Fase 2  → torna banco_id confiável nos pagamentos de gestão de custos
Fase 3  → ativa calcular_saldo_banco() + drop de saldo_atual (após validar cobertura)
```

Fase 1 pode ir para produção independente. Fases 2 e 3 são sequenciais.

---

## Critérios de aceite por fase

**Fase 1:**
- [ ] `fluxo_caixa_confirmar()` sem nenhum `db.session.commit()` antes de `svc.importar()`
- [ ] Falha no import → saldo bancário inalterado
- [ ] Campo `saldo_inicial_<id>` removido do preview de import
- [ ] Migração 186 idempotente executada

**Fase 2:**
- [ ] Pagamento em `gestao_custos_views.py` exige banco selecionado para criar FC
- [ ] Novos `FluxoCaixa` criados por pagamento de gestão de custos têm `banco_id` preenchido

**Fase 3:**
- [ ] `calcular_saldo_banco()` retorna `cobertura_parcial: False` para novos bancos
- [ ] Saldo exibido na UI vem de `calcular_saldo_banco()`, não de coluna persista
- [ ] Coluna `saldo_atual` dropada após validação de cobertura >= 95%
