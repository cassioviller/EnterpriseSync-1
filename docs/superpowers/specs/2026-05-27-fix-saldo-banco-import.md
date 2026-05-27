# Fix #1 — Saldo Bancário: Desacoplar Import + Arquitetura de Cálculo Real

**Data:** 2026-05-27  
**Escopo:** `importacao_views.py`, `financeiro_views.py`, `financeiro_service.py`, `BancoEmpresa`, `FluxoCaixa`  
**Tipo:** Bug crítico + pré-condição para saldo derivado

---

## Problema central

`fluxo_caixa_confirmar()` commita saldo bancário **antes** do import:

```python
db.session.commit()      # ← saldo gravado
svc.importar(...)        # ← se falhar, saldo errado, import inexistente
```

---

## Três fases

```
Fase 1  →  remove bug + adiciona UI de saldo_inicial no CRUD de banco
Fase 2  →  banco_id obrigatório nos dois pontos de criação ausentes
Fase 3  →  ativa calcular_saldo_banco() como fonte de verdade
```

Fase 1 vai para produção independente.  
Fase 3 só ativa após Fase 2 validada em produção (critério abaixo).

---

## Fase 1 — Fix imediato

### 1a. Remover bloco de saldo do import

`importacao_views.py` — `fluxo_caixa_confirmar()`:

- Remover o bloco `"Atualizar Saldo Inicial de Bancos"` inteiro (~20 linhas).
- Remover os campos `saldo_inicial_<banco_id>` do template `preview_fluxo.html`.
- Resultado: import passa a ter uma única transação atômica.

### 1b. Adicionar data_saldo_inicial ao CRUD de banco existente

`financeiro_views.py` tem duas rotas de criação de banco: `criar_banco()` (modal)
e `novo_banco()` (página). Ambas já recebem `saldo_inicial`. Nesta fase:

- Adicionar `data_saldo_inicial` como campo opcional nos dois forms.
- Regra de validação **apenas para escrita nova**:
  se `saldo_inicial > 0` e `data_saldo_inicial` não informada → erro de validação,
  não salva.
- Bancos **existentes** com `saldo_inicial > 0` e `data_saldo_inicial = NULL`
  não são bloqueados. A tela `listar_bancos` exibe um aviso inline por banco
  nesse estado: *"Defina a data de referência do saldo inicial para habilitar
  o cálculo automático."* Sem bloqueio de edição, sem migração forçada.

### 1c. Migração 186

```sql
ALTER TABLE banco_empresa
  ADD COLUMN IF NOT EXISTS data_saldo_inicial DATE;

CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_banco_data
  ON fluxo_caixa (banco_id, data_movimento)
  WHERE banco_id IS NOT NULL;
```

Nenhum backfill de `data_saldo_inicial` em registros existentes — não há data
confiável para inferir. Bancos existentes ficam em estado "incompleto" até o
usuário preencher via UI.

### Critérios de aceite — Fase 1

- [ ] `fluxo_caixa_confirmar()` sem nenhum `commit` antes de `svc.importar()`
- [ ] Falha no import → saldo bancário inalterado
- [ ] Campo `saldo_inicial_<id>` removido do preview de import
- [ ] Criar banco com `saldo_inicial > 0` sem `data_saldo_inicial` → erro de validação
- [ ] Banco existente com `saldo_inicial > 0` e sem data → aviso na listagem, sem bloqueio
- [ ] Migração 186 idempotente executada

---

## Fase 2 — Pré-condição: banco_id em todos os pontos de escrita

### Pontos atuais

| Arquivo | Criação de FluxoCaixa | banco_id? |
|---------|----------------------|-----------|
| `gestao_custos_views.py` ~L727 | pagamento de GestaoCustoPai | ❌ |
| `gestao_custos_views.py` ~L847 | pagamento parcial | ❌ |
| `financeiro_views.py` ~L387 | lançamento direto | ✅ |
| `financeiro_views.py` ~L758 | lançamento direto | ✅ |
| `services/importacao_excel.py` | import de fluxo | ✅ |

### O que muda

Os dois pontos em `gestao_custos_views.py` passam a exigir `banco_id` no form
de pagamento quando o checkbox "Criar lançamento no Fluxo de Caixa" está marcado.
Se banco não selecionado e checkbox marcado → erro de validação, FC não criado.

Registros históricos sem `banco_id` não têm backfill automático — não existe dado
para inferir o banco. Ficam fora do cálculo derivado.

### Critérios de aceite — Fase 2

- [ ] Pagamento em `gestao_custos_views.py` com FC marcado exige banco selecionado
- [ ] Novos FluxoCaixa criados via pagamento de gestão de custos têm `banco_id` preenchido
- [ ] Nenhum novo FluxoCaixa criado por qualquer rota ativa sem `banco_id`

---

## Fase 3 — Cálculo on-the-fly (após Fase 2 validada)

### Critério de ativação

**100% dos FluxoCaixa criados após a data de deploy da Fase 2 têm `banco_id`
preenchido.** Verificado via query antes de ativar:

```sql
SELECT COUNT(*)
FROM fluxo_caixa
WHERE created_at > '<data_deploy_fase2>'
  AND banco_id IS NULL
  AND admin_id IN (SELECT id FROM usuario WHERE tipo = 'admin');
-- Resultado deve ser 0
```

Se não for zero, a Fase 2 tem pontos de escrita ainda descobertos. Não ativar.

### calcular_saldo_banco()

`financeiro_service.py` — nova função:

```python
def calcular_saldo_banco(banco_id: int, admin_id: int) -> Decimal:
    """
    Retorna saldo_atual calculado on-the-fly.
    Não persiste nada. Não faz commit.

    Formula:
        saldo = banco.saldo_inicial
              + Σ ENTRADA (banco_id, data >= data_saldo_inicial)
              - Σ SAIDA   (banco_id, data >= data_saldo_inicial)

    Lançamentos históricos sem banco_id ficam fora do cálculo por definição.
    """
```

Sem retorno de cobertura, sem contagem de `banco_id = NULL`. A função calcula
o saldo dos lançamentos que têm `banco_id` preenchido para este banco — ponto.
O que está fora fica fora; isso é responsabilidade da Fase 2, não desta função.

### saldo_atual → saldo_legado (rename, nunca drop)

Migração 187:

```sql
ALTER TABLE banco_empresa
  RENAME COLUMN saldo_atual TO saldo_legado;
```

`saldo_legado` é mantido como referência histórica e fallback de emergência.
Nunca é dropado. A UI e `listar_bancos()` passam a exibir `calcular_saldo_banco()`
como fonte de verdade; `saldo_legado` fica visível como "saldo anterior (legado)"
apenas na tela de configuração do banco, para auditoria.

### Atualização em listar_bancos()

```python
# Antes
total_saldo = sum(b.saldo_atual for b in bancos if b.ativo)

# Depois
total_saldo = sum(calcular_saldo_banco(b.id, admin_id) for b in bancos if b.ativo)
```

### Critérios de aceite — Fase 3

- [ ] Query de verificação retorna 0 FluxoCaixa sem banco_id criados após Fase 2
- [ ] `calcular_saldo_banco()` retorna `Decimal`, sem campos de cobertura
- [ ] `listar_bancos()` usa `calcular_saldo_banco()` — `saldo_legado` não aparece no total
- [ ] Coluna `saldo_legado` existe, é somente leitura na UI do banco
- [ ] Migração 187 idempotente

---

## Arquivos alterados por fase

| Arquivo | Fase 1 | Fase 2 | Fase 3 |
|---------|--------|--------|--------|
| `importacao_views.py` | remove bloco saldo | — | — |
| `templates/importacao/preview_fluxo.html` | remove campos saldo | — | — |
| `financeiro_views.py` | add data_saldo_inicial nos forms + aviso listagem | banco_id obrigatório | usa calcular_saldo_banco() |
| `gestao_custos_views.py` | — | banco_id obrigatório | — |
| `financeiro_service.py` | — | — | add calcular_saldo_banco() |
| `models.py` | add data_saldo_inicial | — | rename saldo_atual→saldo_legado |
| `migrations.py` | migração 186 | — | migração 187 |
