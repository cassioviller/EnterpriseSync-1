# Fix #1 — Saldo Bancário Desacoplado da Importação de Fluxo de Caixa

**Data:** 2026-05-27
**Escopo:** `fluxo_caixa_confirmar()`, `ImportacaoFluxoCaixa.importar()`, `BancoEmpresa`, `financeiro_service.py`
**Tipo:** Bug crítico + refatoração de arquitetura financeira

---

## Problema

Em `fluxo_caixa_confirmar()`, o saldo bancário é atualizado e commitado **antes** da transação de importação:

```python
# 1. Commit antecipado de saldo
db.session.commit()           # ← saldo gravado aqui

# 2. Import roda depois
svc.importar(...)             # ← se falhar, saldo fica errado
```

Se o import falhar após o commit de saldo, o banco fica com um saldo atualizado mas sem nenhuma transação correspondente. **Inconsistência financeira garantida.**

Além disso, `saldo_atual` era sobrescrito por valor manual informado pelo usuário, sem relação com os lançamentos reais no banco de dados.

---

## Decisão de design

`saldo_atual` deve ser sempre derivado dos lançamentos reais (`FluxoCaixa`), nunca informado manualmente durante o import. O usuário define apenas o **ponto zero histórico** (`saldo_inicial` + `data_saldo_inicial`) na tela de configuração bancária.

---

## O que muda

### 1. `fluxo_caixa_confirmar()` — `importacao_views.py`

**Remover** o bloco completo:

```python
# ── Atualizar Saldo Inicial de Bancos ────────────────────────────
try:
    from models import BancoEmpresa
    bancos_todos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).all()
    ...
    if saldos_atualizados:
        db.session.commit()   # commit antecipado removido
except Exception as e_saldo:
    logger.warning(...)
```

Nenhum outro código é alterado nessa view.

---

### 2. `BancoEmpresa` — `models.py`

Adicionar coluna:

```python
data_saldo_inicial = db.Column(db.Date, nullable=True)
# NULL = considerar todos os FluxoCaixa desde sempre
```

Semântica: o sistema soma todos os `FluxoCaixa` com `banco_id = banco.id` e
`data_movimento >= banco.data_saldo_inicial` (se definida) para calcular `saldo_atual`.

---

### 3. `recalcular_saldo_banco()` — `financeiro_service.py`

Nova função pública:

```python
def recalcular_saldo_banco(banco_id: int, admin_id: int) -> Decimal:
    """
    Recalcula e persiste saldo_atual do banco a partir de:
      saldo_atual = saldo_inicial
                  + Σ FluxoCaixa ENTRADA (banco_id, data >= data_saldo_inicial)
                  - Σ FluxoCaixa SAIDA   (banco_id, data >= data_saldo_inicial)

    Retorna o novo saldo_atual.
    Deve ser chamada DENTRO de uma transação já aberta (não faz commit).
    """
```

Regras:
- Filtra apenas `FluxoCaixa` do `admin_id` correto (segurança multitenant)
- Se `banco.data_saldo_inicial` for `None`, soma todos os lançamentos do banco
- Usa `Decimal` em todo o cálculo (sem float)
- Não faz `db.session.commit()` — responsabilidade do chamador

---

### 4. `ImportacaoFluxoCaixa.importar()` — `services/importacao_excel.py`

Ao final do `importar()`, após o `db.session.commit()`, chamar recálculo para cada banco presente no lote:

```python
# Recalcular saldo dos bancos afetados pelo lote
bancos_afetados = {row.get('banco_id') for row in dados.get('saidas', []) + dados.get('entradas', []) if row.get('banco_id')}
for banco_id in bancos_afetados:
    recalcular_saldo_banco(banco_id, admin_id)
db.session.commit()   # segundo commit apenas para saldos
```

> O recálculo roda **após** o commit principal do import — se falhar, o import já foi salvo e o saldo fica desatualizado até o próximo recálculo. Isso é aceitável: o import não perde dados, e o saldo pode ser recalculado manualmente.

---

### 5. Migração do banco — `migrations.py`

Nova migração `_migration_186_banco_empresa_data_saldo_inicial`:

```sql
ALTER TABLE banco_empresa
  ADD COLUMN IF NOT EXISTS data_saldo_inicial DATE;
```

---

### 6. UI de configuração bancária (futura, fora deste escopo)

A tela de edição de `BancoEmpresa` (já existente em configurações) recebe dois campos:
- `saldo_inicial` (já existe)
- `data_saldo_inicial` (novo) — datepicker, opcional

Ao salvar, chamar `recalcular_saldo_banco()` para atualizar `saldo_atual` imediatamente.

Esta parte é **fora do escopo deste fix** — pode ser implementada em task separada.

---

## Fluxo depois do fix

```
fluxo_caixa_confirmar()
  ↓
_verificar_payload()          (valida HMAC)
  ↓
ImportacaoFluxoCaixa.importar()
  ├── cria GCP / GCF / FluxoCaixa / ContaPagar / ContaReceber
  ├── db.session.commit()     ← transação atômica única
  ├── recalcular_saldo_banco() para cada banco do lote
  └── db.session.commit()     ← saldos atualizados
  ↓
render resultado
```

Se o import falhar → rollback total, saldo intocado.
Se o recálculo de saldo falhar → import já salvo, log de warning, saldo fica desatualizado (aceitável).

---

## Arquivos alterados

| Arquivo | Tipo de mudança |
|---------|----------------|
| `importacao_views.py` | Remover bloco de saldo (~20 linhas) |
| `models.py` | Adicionar `BancoEmpresa.data_saldo_inicial` |
| `financeiro_service.py` | Adicionar `recalcular_saldo_banco()` |
| `services/importacao_excel.py` | Chamar recálculo após commit |
| `migrations.py` | Migração 186 |

---

## O que NÃO muda neste fix

- Lógica de classificação de saídas/entradas
- Fuzzy match de fornecedores/funcionários
- HMAC de payload
- Template de preview (`importacao/preview_fluxo.html`) — campo `saldo_inicial_<id>` some do form
- Rollback por lote (`fluxo_caixa_rollback`)

---

## Critérios de aceite

- [ ] Import de fluxo de caixa sem nenhum commit antecipado de saldo
- [ ] Falha no import → saldo bancário inalterado
- [ ] `saldo_atual` após import reflete `saldo_inicial + Σ lançamentos` do lote
- [ ] `recalcular_saldo_banco()` pode ser chamada independentemente (sem import)
- [ ] Migração 186 idempotente (`ADD COLUMN IF NOT EXISTS`)
