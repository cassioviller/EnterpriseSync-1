# Plano de Implementação — Fix #1: Saldo Bancário

**Spec:** `docs/superpowers/specs/2026-05-27-fix-saldo-banco-import.md`  
**Data:** 2026-05-27

---

## Fase 1 — Fix imediato (deploya isolado)

### Passo 1 — Migração 186 (`migrations.py`)

**Onde:** após `_migration_185_insumo_fracionavel` (linha ~13267), antes do fim do arquivo.

**O que adicionar:**

```python
def _migration_186_banco_data_saldo_inicial():
    """
    Fase 1 Fix #1: adiciona data_saldo_inicial em banco_empresa
    e índice composto (banco_id, data_movimento) em fluxo_caixa.
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        cursor.execute("""
            ALTER TABLE banco_empresa
              ADD COLUMN IF NOT EXISTS data_saldo_inicial DATE
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_banco_data
              ON fluxo_caixa (banco_id, data_movimento)
              WHERE banco_id IS NOT NULL
        """)
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("[Migration 186] data_saldo_inicial e idx_fluxo_caixa_banco_data criados.")
    except Exception as e:
        logger.error(f"[Migration 186] Falha: {e}")
        raise
```

**Registrar na lista `migrations_to_run`** (linha ~3938, após entrada 185):

```python
(186, "Fix #1 Fase 1 — BancoEmpresa: data_saldo_inicial + índice fluxo_caixa(banco_id, data_movimento)", _migration_186_banco_data_saldo_inicial),
```

---

### Passo 2 — Modelo `BancoEmpresa` (`models.py`)

**Onde:** linha 1824 (após `saldo_atual`).

**Adicionar campo:**

```python
data_saldo_inicial = db.Column(db.Date, nullable=True)
```

Resultado da classe após edição:
```python
saldo_inicial    = db.Column(db.Numeric(15, 2), default=0)
saldo_atual      = db.Column(db.Numeric(15, 2), default=0)
data_saldo_inicial = db.Column(db.Date, nullable=True)   # ← novo
ativo            = db.Column(db.Boolean, default=True)
```

---

### Passo 3 — `importacao_views.py`: remover bloco de saldo

**Onde:** linhas 688–708.

**Remover inteiro** o bloco:
```python
# ── Atualizar Saldo Inicial de Bancos ────────────────────────────
try:
    from models import BancoEmpresa
    bancos_todos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).all()
    saldos_atualizados = 0
    for banco in bancos_todos:
        campo = request.form.get(f'saldo_inicial_{banco.id}', '').strip()
        if campo:
            try:
                novo_saldo = float(campo.replace('.', '').replace(',', '.'))
                banco.saldo_inicial = novo_saldo
                # Atualiza saldo_atual apenas se estiver zerado (inicialização)
                if (banco.saldo_atual or 0) == 0:
                    banco.saldo_atual = novo_saldo
                saldos_atualizados += 1
            except ValueError:
                pass
    if saldos_atualizados:
        db.session.commit()
except Exception as e_saldo:
    logger.warning(f'[FLUXO_CAIXA] Erro ao atualizar saldo inicial: {e_saldo}')
```

Resultado: o `try` na linha 710 (`from services.importacao_excel import ImportacaoFluxoCaixa`) passa a ser o primeiro bloco ativo após a construção de `batch_id`. Transação atômica — sem commit prévio.

---

### Passo 4 — Template `preview_fluxo.html`: remover seção saldo

**Onde:** linhas 745–787 (bloco `<!-- 6. SALDO INICIAL DE BANCOS -->`).

**Remover inteiro:**
```html
<!-- 6. SALDO INICIAL DE BANCOS -->
{% if bancos %}
<div class="mb-4">
  ... (bloco inteiro até </div> fechando o {% endif %})
</div>
{% endif %}
```

Se `bancos` ainda for passado pelo contexto para outros fins, verificar e remover do `render_template` em `fluxo_caixa_upload()` se não usado em outro lugar. Se não for, deixar — variável não usada em template não causa erro.

---

### Passo 5 — `financeiro_views.py`: adicionar `data_saldo_inicial` ao modal `criar_banco()`

**Onde:** rota `criar_banco()` — linha 842 (após leitura de `saldo_inicial`).

**Adicionar leitura do campo:**

```python
saldo_inicial = Decimal(request.form.get('saldo_inicial', '0'))
data_saldo_str = request.form.get('data_saldo_inicial', '').strip()

# Validação: novo banco com saldo > 0 exige data de referência
if saldo_inicial > 0 and not data_saldo_str:
    flash('Informe a data de referência do saldo inicial.', 'danger')
    return redirect(url_for('financeiro.listar_bancos'))

data_saldo_inicial = None
if data_saldo_str:
    from datetime import date as date_type
    try:
        data_saldo_inicial = date_type.fromisoformat(data_saldo_str)
    except ValueError:
        flash('Data de saldo inicial inválida.', 'danger')
        return redirect(url_for('financeiro.listar_bancos'))
```

**Adicionar ao construtor `BancoEmpresa`:**
```python
banco = BancoEmpresa(
    admin_id=admin_id,
    nome_banco=nome_banco,
    tipo_conta=tipo_conta,
    agencia=agencia,
    conta=conta,
    saldo_inicial=saldo_inicial,
    saldo_atual=saldo_inicial,
    data_saldo_inicial=data_saldo_inicial,  # ← novo
    ativo=ativo
)
```

---

### Passo 6 — `financeiro_views.py`: adicionar `data_saldo_inicial` à rota `novo_banco()`

**Onde:** rota `novo_banco()` — linha 881 (após leitura de `saldo_inicial`).

**Adicionar leitura + validação (mesmo padrão do passo 5):**

```python
saldo_inicial = Decimal(request.form.get('saldo_inicial', '0'))
data_saldo_str = request.form.get('data_saldo_inicial', '').strip()

if saldo_inicial > 0 and not data_saldo_str:
    flash('Informe a data de referência do saldo inicial.', 'danger')
    return render_template('financeiro/novo_banco.html')

data_saldo_inicial = None
if data_saldo_str:
    from datetime import date as date_type
    try:
        data_saldo_inicial = date_type.fromisoformat(data_saldo_str)
    except ValueError:
        flash('Data de saldo inicial inválida.', 'danger')
        return render_template('financeiro/novo_banco.html')
```

**Na chamada `FinanceiroService.criar_banco()`**, adicionar `data_saldo_inicial=data_saldo_inicial`.  
Verificar se `FinanceiroService.criar_banco()` aceita e repassa o campo; se não aceitar kwargs extras, adicionar o parâmetro lá também e passá-lo ao construtor.

---

### Passo 7 — Template `bancos.html`: campo `data_saldo_inicial` no modal

**Onde:** modal `#modalNovoBanco` — após o campo `saldo_inicial` (linha 154).

**Adicionar campo:**
```html
<div class="col-md-6 mb-3">
    <label class="form-label">Data de Referência do Saldo</label>
    <input type="date" name="data_saldo_inicial" class="form-control"
           id="dataSaldoInicial">
    <div class="form-text">Obrigatório se saldo inicial &gt; 0.</div>
</div>
```

**Adicionar validação client-side (JS no modal):**
```javascript
document.querySelector('form[action*="criar_banco"]').addEventListener('submit', function(e) {
    const saldo = parseFloat(document.querySelector('[name=saldo_inicial]').value || '0');
    const data = document.getElementById('dataSaldoInicial').value;
    if (saldo > 0 && !data) {
        e.preventDefault();
        alert('Informe a data de referência do saldo inicial.');
    }
});
```

---

### Passo 8 — Template `novo_banco.html`: campo `data_saldo_inicial`

**Onde:** após o campo `saldo_inicial` (linha 58).

**Adicionar campo:**
```html
<div class="mb-3">
    <label class="form-label">Data de Referência do Saldo</label>
    <input type="date" name="data_saldo_inicial" class="form-control"
           id="dataSaldoInicialNovo">
    <div class="form-text">Obrigatório se saldo inicial &gt; 0.</div>
</div>
```

**Adicionar validação client-side equivalente.**

---

### Passo 9 — Template `bancos.html`: aviso inline para bancos sem `data_saldo_inicial`

**Onde:** no `{% for banco in bancos %}` (linha ~21) — após exibição do saldo, antes dos botões.

**Adicionar aviso condicional:**
```html
{% if banco.saldo_inicial and banco.saldo_inicial > 0 and not banco.data_saldo_inicial %}
<div class="alert alert-warning alert-sm py-1 px-2 mt-1 mb-0" style="font-size:0.8rem;">
    <i data-feather="alert-circle" style="width:12px;height:12px;"></i>
    Defina a data de referência do saldo inicial para habilitar o cálculo automático.
    <a href="#" onclick="editarBanco({{ banco.id }})">Definir</a>
</div>
{% endif %}
```

Nota: `editarBanco()` atualmente só faz `alert()`. Se edição inline de banco não existir, o link pode apontar para uma rota de edição a ser implementada, ou temporariamente omitir o link e deixar apenas o texto.

---

### Critérios de aceite — Fase 1

- [ ] `fluxo_caixa_confirmar()` sem nenhum `commit` antes de `svc.importar()`
- [ ] Falha no import → saldo bancário inalterado (testar com `svc.importar` lançando exceção)
- [ ] Seção "Saldo Inicial de Bancos" removida do template `preview_fluxo.html`
- [ ] Criar banco via modal com `saldo_inicial > 0` sem data → flash de erro, banco não criado
- [ ] Criar banco via modal com `saldo_inicial > 0` com data válida → banco criado com `data_saldo_inicial` preenchido
- [ ] Criar banco com `saldo_inicial = 0` sem data → banco criado normalmente
- [ ] Banco existente com `saldo_inicial > 0` e `data_saldo_inicial = NULL` → aviso inline em `listar_bancos`
- [ ] Banco existente com data preenchida → sem aviso
- [ ] Migração 186 idempotente (executar duas vezes, sem erro)
- [ ] `banco_empresa.data_saldo_inicial` existe no banco de dados

---

## Fase 2 — `banco_id` obrigatório em `gestao_custos_views.py`

> **Pré-condição:** Fase 1 em produção e validada.

### Passo 10 — Ponto 1: pagamento de `GestaoCustoPai` (~linha 727)

**Onde:** bloco `if criar_fc:` (linha 726).

**Antes da criação do `FluxoCaixa`**, garantir que `banco_id` foi fornecido:

```python
criar_fc = 'criar_fluxo_caixa' in request.form

# Fase 2: banco obrigatório quando FC marcado
if criar_fc:
    if not banco_id_str:
        flash('Selecione o banco para criar lançamento no Fluxo de Caixa.', 'danger')
        return redirect(url_for('gestao_custos.index'))

fc = None
if criar_fc:
    fc = FluxoCaixa(
        admin_id=admin_id,
        data_movimento=data_pgto,
        tipo_movimento='SAIDA',
        categoria=cat_fc,
        valor=float(valor_autorizado),
        descricao=f'{label} — {pai.entidade_nome}',
        referencia_id=pai.id,
        referencia_tabela='gestao_custo_pai',
        observacoes=conta or None,
        banco_id=int(banco_id_str),   # ← novo
    )
    db.session.add(fc)
    db.session.flush()
```

---

### Passo 11 — Ponto 2: pagamento parcial (~linha 847)

**Onde:** criação do `FluxoCaixa` em pagamento parcial (linha 847).

O ponto 2 não tem o checkbox `criar_fluxo_caixa` — o FC é criado incondicionalmente. Aplicar a mesma validação: se `banco_id_str` estiver vazio, retornar erro.

```python
# Fase 2: banco obrigatório para pagamento parcial com FC
if not banco_id_str:
    flash('Selecione o banco para registrar o pagamento.', 'danger')
    return redirect(url_for('gestao_custos.index'))

fc = FluxoCaixa(
    admin_id=admin_id,
    data_movimento=data_pgto,
    tipo_movimento='SAIDA',
    categoria=cat_fc,
    valor=float(valor_pago_agora),
    descricao=f'{label} — {pai.entidade_nome}',
    referencia_id=pai.id,
    referencia_tabela='gestao_custo_pai',
    observacoes=conta or None,
    banco_id=int(banco_id_str),   # ← novo
)
```

---

### Passo 12 — Verificar formulários de pagamento em `gestao_custos`

Confirmar que o campo `banco_id` já existe nos templates de pagamento de gestão de custos (checkbox + select de banco). Se `banco_id` já é enviado mas estava sendo ignorado na criação do FC (o código em L680–686 já lê o valor), o select já existe na UI — apenas o repasse para o construtor `FluxoCaixa` estava faltando.

Se o select não existir na UI, adicionar:
```html
<div class="mb-3">
    <label class="form-label">Banco *</label>
    <select name="banco_id" class="form-select" required>
        <option value="">Selecione...</option>
        {% for banco in bancos %}
        <option value="{{ banco.id }}">{{ banco.nome_banco }}</option>
        {% endfor %}
    </select>
</div>
```

---

### Critérios de aceite — Fase 2

- [ ] Pagamento de GestaoCustoPai com "Criar FC" marcado e banco não selecionado → flash de erro, FC não criado
- [ ] Pagamento parcial sem banco → flash de erro, FC não criado
- [ ] Novos FluxoCaixa criados via gestão de custos têm `banco_id` preenchido (verificar no banco)
- [ ] Query de cobertura após alguns dias: `SELECT COUNT(*) FROM fluxo_caixa WHERE created_at > '<deploy_fase2>' AND banco_id IS NULL AND admin_id IN (SELECT id FROM usuario WHERE tipo = 'admin')` retorna 0

---

## Fase 3 — Cálculo on-the-fly (apenas após query de cobertura = 0)

> **Pré-condição:** query de cobertura da Fase 2 retorna 0.

### Passo 13 — `financeiro_service.py`: nova função `calcular_saldo_banco()`

**Adicionar no módulo** (localizar onde estão outras funções utilitárias de banco):

```python
from decimal import Decimal

def calcular_saldo_banco(banco_id: int, admin_id: int) -> Decimal:
    """
    Retorna o saldo atual calculado on-the-fly.
    Não persiste nada. Não faz commit.

    Fórmula:
        saldo = banco.saldo_inicial
              + Σ ENTRADA  (banco_id, data_movimento >= data_saldo_inicial)
              - Σ SAIDA    (banco_id, data_movimento >= data_saldo_inicial)

    Lançamentos sem banco_id ficam fora do cálculo por definição.
    Banco sem data_saldo_inicial: usa todos os lançamentos (data >= epoch).
    """
    from models import BancoEmpresa, FluxoCaixa
    from sqlalchemy import func

    banco = BancoEmpresa.query.filter_by(id=banco_id, admin_id=admin_id).first()
    if not banco:
        return Decimal('0')

    saldo_base = Decimal(str(banco.saldo_inicial or 0))
    data_ref = banco.data_saldo_inicial  # pode ser None

    q = FluxoCaixa.query.filter_by(banco_id=banco_id, admin_id=admin_id)
    if data_ref:
        q = q.filter(FluxoCaixa.data_movimento >= data_ref)

    entradas = q.filter_by(tipo_movimento='ENTRADA').with_entities(
        func.coalesce(func.sum(FluxoCaixa.valor), 0)
    ).scalar()

    saidas = q.filter_by(tipo_movimento='SAIDA').with_entities(
        func.coalesce(func.sum(FluxoCaixa.valor), 0)
    ).scalar()

    return saldo_base + Decimal(str(entradas)) - Decimal(str(saidas))
```

---

### Passo 14 — Migração 187 (`migrations.py`)

**Adicionar após `_migration_186_banco_data_saldo_inicial`:**

```python
def _migration_187_banco_saldo_atual_para_legado():
    """
    Fase 3 Fix #1: renomeia saldo_atual → saldo_legado em banco_empresa.
    A coluna é mantida como referência histórica. Nunca será dropada.
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        # Idempotente: só executa se saldo_atual ainda existir
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'banco_empresa' AND column_name = 'saldo_atual'
        """)
        if cursor.fetchone():
            cursor.execute("""
                ALTER TABLE banco_empresa RENAME COLUMN saldo_atual TO saldo_legado
            """)
            connection.commit()
            logger.info("[Migration 187] saldo_atual renomeado para saldo_legado.")
        else:
            logger.info("[Migration 187] saldo_legado já existe — skip.")
        cursor.close()
        connection.close()
    except Exception as e:
        logger.error(f"[Migration 187] Falha: {e}")
        raise
```

**Registrar na lista:**
```python
(187, "Fix #1 Fase 3 — BancoEmpresa: renomear saldo_atual → saldo_legado", _migration_187_banco_saldo_atual_para_legado),
```

---

### Passo 15 — `models.py`: renomear atributo

**Substituir** (após migração 187 aplicada em produção):
```python
saldo_atual      = db.Column(db.Numeric(15, 2), default=0)
```
por:
```python
saldo_legado     = db.Column('saldo_legado', db.Numeric(15, 2), default=0)
```

---

### Passo 16 — `financeiro_views.py`: atualizar `listar_bancos()`

```python
# Antes
total_saldo = sum(b.saldo_atual for b in bancos if b.ativo)

# Depois
from financeiro_service import calcular_saldo_banco
total_saldo = sum(
    calcular_saldo_banco(b.id, admin_id)
    for b in bancos if b.ativo
)
```

Passar também o saldo calculado por banco ao template (para exibição individual):
```python
saldos = {b.id: calcular_saldo_banco(b.id, admin_id) for b in bancos if b.ativo}
return render_template('financeiro/bancos.html', bancos=bancos, total_saldo=total_saldo, saldos=saldos)
```

---

### Passo 17 — Template `bancos.html`: exibir saldo calculado + legado

**Trocar** a exibição do saldo bancário individual:

```html
{# Antes #}
<h4 class="{% if banco.saldo_atual >= 0 %}text-success{% else %}text-danger{% endif %}">
    {{ banco.saldo_atual|brl }}
</h4>

{# Depois #}
{% set saldo_calc = saldos.get(banco.id, 0) %}
<h4 class="{% if saldo_calc >= 0 %}text-success{% else %}text-danger{% endif %}">
    {{ saldo_calc|brl }}
</h4>
{% if banco.saldo_legado is defined %}
<small class="text-muted d-block">Legado: {{ banco.saldo_legado|brl }}</small>
{% endif %}
```

---

### Critérios de aceite — Fase 3

- [ ] Query de cobertura retorna 0 antes de ativar
- [ ] `calcular_saldo_banco()` retorna `Decimal`
- [ ] `calcular_saldo_banco()` com `data_saldo_inicial = None` usa todos os lançamentos do banco
- [ ] `calcular_saldo_banco()` com `data_saldo_inicial` definida ignora lançamentos anteriores à data
- [ ] `listar_bancos()` exibe saldo calculado (não `saldo_legado`) no card e no total
- [ ] `saldo_legado` visível como dado secundário na tela de detalhe/config do banco
- [ ] Migração 187 idempotente (executar duas vezes, sem erro)
- [ ] Nenhuma referência a `saldo_atual` restante no código (grep confirma)

---

## Ordem de execução

```
Fase 1:
  1 → migrations.py (add _migration_186, registrar)
  2 → models.py (add data_saldo_inicial)
  3 → importacao_views.py (remove bloco saldo)
  4 → preview_fluxo.html (remove seção)
  5–6 → financeiro_views.py criar_banco() + novo_banco()
  7–8 → bancos.html + novo_banco.html (add campo data_saldo_inicial)
  9 → bancos.html (aviso inline)
  → Deploy + validar critérios de aceite Fase 1

Fase 2:
  10–11 → gestao_custos_views.py (banco_id obrigatório nos dois pontos)
  12 → Templates de pagamento (confirmar select banco)
  → Deploy + monitorar query de cobertura por ≥ 7 dias

Fase 3 (só após query = 0):
  13 → financeiro_service.py (calcular_saldo_banco)
  14 → migrations.py (add _migration_187, registrar)
  15 → models.py (renomear saldo_atual → saldo_legado)
  16 → financeiro_views.py listar_bancos()
  17 → bancos.html (exibir saldo calculado)
  → Deploy + validar critérios de aceite Fase 3
```
