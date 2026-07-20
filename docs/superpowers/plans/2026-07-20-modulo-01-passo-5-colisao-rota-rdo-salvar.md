# Colisão de rota `/rdo/salvar` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para rastreamento.

**Goal:** Eliminar a regra de URL duplicada `/rdo/salvar` do `url_map`, tornando o roteamento determinístico e explícito, sem alterar qual código atende a requisição.

**Architecture:** Duas regras Flask registram hoje o mesmo path `/rdo/salvar`. A vencedora (`main.rdo_salvar_unificado`) é decidida por ordem de registro de blueprint e nunca muda; a perdedora (`rdo_crud.salvar_rdo`) é inalcançável por construção. A correção é remover o **registro de rota** da perdedora — não a função — o que remove a regra fantasma do `url_map` sem mudar uma única resposta HTTP.

**Tech Stack:** Flask/Werkzeug (`url_map`, blueprints), pytest, PostgreSQL real via `tests/conftest.py`.

---

## 1. Objetivo

Passo 5 do Módulo 01 (`2026-07-17-modulo-01-auditoria-refatoracao-dominio.md` §21). Fechar o item de checklist "Colisão de rota resolvida e testada".

## 2. Estado atual verificado no código

Medido em runtime sobre o app canônico (`main:app`, o mesmo que o gunicorn serve), não inferido:

```
/rdo/salvar           -> main.rdo_salvar_unificado    ['POST']
/rdo/salvar           -> rdo_crud.salvar_rdo          ['POST']
/salvar-rdo-flexivel  -> main.salvar_rdo_flexivel     ['POST']

url_map.bind('localhost').match('/rdo/salvar', method='POST')
  → ('main.rdo_salvar_unificado', {})
```

- Vencedora: `views/rdo.py:2511` — `@main_bp.route('/rdo/salvar', methods=['POST'])`, `@funcionario_required`.
- Perdedora: `crud_rdo_completo.py:230` — `@rdo_crud_bp.route('/salvar', methods=['POST'])` sob `url_prefix='/rdo'`, `@login_required`.
- A ordem é estável: `app.py:463` registra `main_bp`; `main.py:24` registra `rdo_crud_bp` depois. Ambas as regras são estáticas (sem conversores) e têm os mesmos métodos, então o Werkzeug decide por ordem de inserção. Não há contexto em que a perdedora vença: sem `main.py` ela sequer é registrada.

## 3. Correções ao plano mestre exigidas por este passo

O plano mestre (`...-master-plan.md` §1.3) e o Módulo 01 (§4) afirmam:

> "Três handlers de gravação redundantes: `salvar_rdo_flexivel` (`views/rdo.py:3851`), `rdo_salvar_unificado` (`views/rdo.py:2513`) e `crud_rdo_completo.salvar_rdo` (`:232`) — os dois últimos **colidem na mesma URL `/rdo/salvar`**."
> "manter o handler que hoje efetivamente atende (verificar ordem de registro em runtime com teste) e fazer o outro redirecionar/410"

Dois erros a corrigir no doc:

1. **`salvar_rdo_flexivel` não colide.** Ele está em `@main_bp.route('/salvar-rdo-flexivel')` (`views/rdo.py:3849`), URL distinta. Colidem **2** handlers, não 3.
2. **"fazer o outro redirecionar/410" é impossível como escrito.** A perdedora é inalcançável: o Flask nunca a despacha, então nenhum corpo de resposta dela — 410 inclusive — pode ser observado por um cliente. Devolver 410 exigiria *dar a ela uma URL nova e alcançável*, ou seja, criar superfície HTTP que não existe hoje. Fora do espírito de "zero mudança de comportamento" (§18.1).

## 4. Escopo

- Congelar por teste o vencedor atual de `/rdo/salvar` (protege contra inversão silenciosa se alguém reordenar blueprints).
- Remover o registro de rota da perdedora, deixando `/rdo/salvar` com exatamente uma regra no `url_map`.
- Corrigir a telemetria enganosa descrita em §5.
- Corrigir as duas afirmações erradas do plano mestre e marcar o checklist do Módulo 01.

## 5. Descoberta colateral: telemetria que nunca pôde disparar

`crud_rdo_completo.py:243-249` emite:

```
[LEGACY-RDO] POST /rdo/salvar (rdo_crud.salvar_rdo) chamado — endpoint legado. user=... referrer=... path=...
```

Essa linha foi adicionada (Task #9) como telemetria para decidir quando remover o endpoint legado, conforme o docstring: *"telemetria para confirmar quando este endpoint legado é efetivamente usado em produção"*. **Ela nunca pôde ser emitida** — a função é inalcançável desde que a colisão existe. Qualquer decisão futura baseada em "`rdo_crud.salvar_rdo` não aparece nos logs, pode remover" seria inválida: a ausência mede o roteamento, não o uso. Isso precisa ficar escrito no código, senão a armadilha sobrevive à remoção da rota.

`tests/test_rdo_legacy_endpoints_horas.py` cobre os cenários L1 (`/rdo/criar`) e L2 (`/rdo/salvar` → `rdo_salvar_unificado`) e valida a telemetria **do vencedor** — que de fato dispara. Nenhum teste exercita a perdedora.

## 6. Fora de escopo

- Remover a função `salvar_rdo` ou o blueprint `rdo_crud_bp` (Módulo 01 §5: remoção de handlers legados fica para depois do rollout).
- Alterar `rdo_salvar_unificado`, `salvar_rdo_flexivel` ou `/funcionario/rdo/criar`.
- Mudar qualquer decorator de autorização (Módulo 01 §4 restringe o decorator novo às rotas dos Módulos 3/5/8).
- Reordenar registro de blueprints em `app.py` / `main.py`.

## 7. Arquivos

- Criar: `tests/test_rota_rdo_salvar_unica.py`
- Modificar: `crud_rdo_completo.py:230-249`
- Modificar: `docs/superpowers/plans/2026-07-17-cronograma-mpp-rdo-master-plan.md` (§1.3)
- Modificar: `docs/superpowers/plans/2026-07-17-modulo-01-auditoria-refatoracao-dominio.md` (§4 e §22)

## 8. Alterações de banco

Nenhuma.

## 9. Compatibilidade

Nenhuma URL muda de comportamento. `POST /rdo/salvar` continua atendido por `main.rdo_salvar_unificado`, com o mesmo decorator, o mesmo corpo e a mesma telemetria. A única diferença observável é o tamanho do `url_map`.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Algum consumidor depender de `url_for('rdo_crud.salvar_rdo')` | Verificado: zero ocorrências em `.py`, `.html` e `.js` fora de `archive/`. A única referência ao nome é a própria string de log. |
| A função virar código morto silencioso | Task 3 escreve o motivo no docstring, incluindo a armadilha da telemetria. |
| Alguém reintroduzir a colisão | Task 1 deixa um teste que falha se `/rdo/salvar` voltar a ter >1 regra. |

---

## Task 1: Congelar o roteamento atual

**Files:**
- Create: `tests/test_rota_rdo_salvar_unica.py`

- [ ] **Step 1: Escrever o teste de caracterização**

O `conftest.py` já monta o app canônico via fixture autouse `_registrar_blueprints_opcionais` (`import main`), então ambos os blueprints estão registrados na hora da coleta.

```python
"""Módulo 01 / passo 5 — a rota POST /rdo/salvar tem dono único e determinístico.

Antes deste passo, `/rdo/salvar` tinha DUAS regras no url_map:
`main.rdo_salvar_unificado` (registrada por app.py:463) e
`rdo_crud.salvar_rdo` (registrada por main.py:24). A primeira sempre
vencia — ambas são estáticas e têm os mesmos métodos, então o Werkzeug
decide por ordem de inserção. A segunda era inalcançável por construção.
"""
from app import app


def test_post_rdo_salvar_resolve_para_rdo_salvar_unificado():
    """O dono de POST /rdo/salvar não pode mudar sem quebrar este teste."""
    adapter = app.url_map.bind('localhost')
    endpoint, _args = adapter.match('/rdo/salvar', method='POST')
    assert endpoint == 'main.rdo_salvar_unificado'


def test_salvar_rdo_flexivel_tem_url_propria():
    """O fluxo principal NÃO colide com /rdo/salvar — URL distinta."""
    adapter = app.url_map.bind('localhost')
    endpoint, _args = adapter.match('/salvar-rdo-flexivel', method='POST')
    assert endpoint == 'main.salvar_rdo_flexivel'
```

- [ ] **Step 2: Rodar e verificar que passa**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_rota_rdo_salvar_unica.py -p no:cacheprovider -q`
Expected: `2 passed`

- [ ] **Step 3: Commit**

```bash
git add tests/test_rota_rdo_salvar_unica.py
git commit -m "test(rdo): congela o dono da rota POST /rdo/salvar"
```

---

## Task 2: Exigir regra única e remover a duplicata

**Files:**
- Modify: `tests/test_rota_rdo_salvar_unica.py`
- Modify: `crud_rdo_completo.py:230-232`

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/test_rota_rdo_salvar_unica.py`:

```python
def test_rdo_salvar_tem_exatamente_uma_regra():
    """Uma segunda regra em /rdo/salvar é inalcançável e engana quem lê o código."""
    regras = [r for r in app.url_map.iter_rules() if r.rule == '/rdo/salvar']
    endpoints = sorted(r.endpoint for r in regras)
    assert endpoints == ['main.rdo_salvar_unificado'], (
        f'esperava dono único, encontrei {endpoints}'
    )
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_rota_rdo_salvar_unica.py::test_rdo_salvar_tem_exatamente_uma_regra -p no:cacheprovider -q`
Expected: FAIL — `esperava dono único, encontrei ['main.rdo_salvar_unificado', 'rdo_crud.salvar_rdo']`

- [ ] **Step 3: Remover o registro de rota da perdedora**

Em `crud_rdo_completo.py`, trocar as linhas 230-232:

```python
@rdo_crud_bp.route('/salvar', methods=['POST'])
@login_required
def salvar_rdo():
```

por:

```python
# Módulo 01 / passo 5 — rota REMOVIDA (não a função).
# Esta view registrava `/rdo/salvar` sob o url_prefix do rdo_crud_bp,
# colidindo com @main_bp.route('/rdo/salvar') em views/rdo.py:2511.
# O main_bp é registrado antes (app.py:463 vs main.py:24), então esta
# função NUNCA foi despachada. Manter o registro só mantinha uma regra
# fantasma no url_map. A função fica para o rollout do Módulo 07.
def salvar_rdo():
```

Manter o corpo inteiro da função intacto. `login_required` continua importado e usado por outras views do arquivo — não remover o import.

- [ ] **Step 4: Rodar o arquivo de teste inteiro**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_rota_rdo_salvar_unica.py -p no:cacheprovider -q`
Expected: `3 passed`

- [ ] **Step 5: Rodar os testes que exercitam os endpoints legados de RDO**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_rdo_legacy_endpoints_horas.py -p no:cacheprovider --tb=short -q`
Expected: PASS — o cenário L2 (`POST /rdo/salvar`) continua atendido e continua emitindo `[LEGACY-RDO]`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_rota_rdo_salvar_unica.py crud_rdo_completo.py
git commit -m "fix(rdo): remove regra fantasma /rdo/salvar do url_map"
```

---

## Task 3: Documentar a telemetria que nunca disparou

**Files:**
- Modify: `crud_rdo_completo.py:233-249`

- [ ] **Step 1: Corrigir o docstring e a linha de log**

O docstring atual afirma que a linha `[LEGACY-RDO]` é telemetria de uso em produção. Substituir o docstring de `salvar_rdo` por:

```python
    """Salvar RDO (criar ou editar) — endpoint legado, HOJE SEM ROTA.

    ATENÇÃO ao decidir remover esta função: a linha [LEGACY-RDO] abaixo
    foi adicionada (Task #9) como telemetria de uso em produção, mas
    NUNCA PÔDE DISPARAR — a rota `/rdo/salvar` desta view colidia com
    @main_bp.route('/rdo/salvar') (views/rdo.py:2511), que é registrada
    antes e sempre venceu o despacho. Ausência de [LEGACY-RDO] com
    `rdo_crud.salvar_rdo` nos logs mede o ROTEAMENTO, não o uso — não
    use isso como evidência de que ninguém chama este fluxo.

    O fluxo principal é POST /salvar-rdo-flexivel; o legado alcançável
    é POST /rdo/salvar → views.rdo:rdo_salvar_unificado.
    """
```

E trocar a string de log (`crud_rdo_completo.py:244`) para não afirmar um path que esta função não serve:

```python
            "[LEGACY-RDO] rdo_crud.salvar_rdo chamado — função legada SEM ROTA "
            "(ver docstring). user=%s referrer=%s path=%s",
```

- [ ] **Step 2: Rodar os testes das duas tarefas anteriores**

Run: `.pythonlibs/bin/python -u -m pytest tests/test_rota_rdo_salvar_unica.py tests/test_rdo_legacy_endpoints_horas.py -p no:cacheprovider -q`
Expected: PASS — nenhum teste asserta a string antiga (`test_rdo_legacy_endpoints_horas.py` casa `[LEGACY-RDO]` do vencedor, em `views/rdo.py`).

- [ ] **Step 3: Commit**

```bash
git add crud_rdo_completo.py
git commit -m "docs(rdo): registra que a telemetria de rdo_crud.salvar_rdo nunca disparou"
```

---

## Task 4: Corrigir os planos e fechar o checklist

**Files:**
- Modify: `docs/superpowers/plans/2026-07-17-cronograma-mpp-rdo-master-plan.md` (§1.3)
- Modify: `docs/superpowers/plans/2026-07-17-modulo-01-auditoria-refatoracao-dominio.md` (§4, §22)

- [ ] **Step 1: Corrigir §1.3 do plano mestre**

Trocar a frase final de §1.3 por:

```markdown
- Três handlers de gravação redundantes: `salvar_rdo_flexivel` (`views/rdo.py:3849`, principal, em `/salvar-rdo-flexivel`), `rdo_salvar_unificado` (`views/rdo.py:2511`, legado, em `/rdo/salvar`) e `crud_rdo_completo.salvar_rdo` (`:230`, legado). Os dois últimos **colidiam na mesma URL `/rdo/salvar`** — resolvido no Módulo 01 passo 5: `rdo_salvar_unificado` sempre venceu (ordem de registro `app.py:463` < `main.py:24`) e o registro de rota da perdedora foi removido. `salvar_rdo_flexivel` **não** colide: URL distinta.
```

- [ ] **Step 2: Corrigir §4 do Módulo 01**

Trocar o bullet da colisão por:

```markdown
- Resolução da colisão `/rdo/salvar`: verificado em runtime que `main.rdo_salvar_unificado` sempre vence (ordem de registro de blueprint, regras estáticas de mesmos métodos). A perdedora `rdo_crud.salvar_rdo` é inalcançável por construção, portanto NÃO pode redirecionar nem devolver 410 — qualquer resposta dela exigiria criar uma URL nova. Correção: remover o registro de rota da perdedora (função preservada para o rollout do Módulo 07). Ver `2026-07-20-modulo-01-passo-5-colisao-rota-rdo-salvar.md`.
```

- [ ] **Step 3: Marcar o checklist de §22 do Módulo 01**

```markdown
- [x] Caracterização congelada e verde
- [x] Serviço de apontamento único em uso pelos dois callers
- [x] Colisão de rota resolvida e testada
```

Deixar os demais itens desmarcados.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/
git commit -m "docs(plano): corrige a colisão /rdo/salvar e fecha o passo 5 do M01"
```

---

## Critérios de aceite

1. `POST /rdo/salvar` continua atendido por `main.rdo_salvar_unificado` — mesmo corpo, mesmo decorator, mesma telemetria.
2. `/rdo/salvar` tem exatamente uma regra no `url_map`, com teste que falha se voltar a ter duas.
3. `tests/test_rdo_legacy_endpoints_horas.py` verde (cenários L1 e L2 intactos).
4. A armadilha da telemetria inalcançável está escrita no código, não só neste plano.
5. Plano mestre e Módulo 01 sem as duas afirmações erradas.

## Verificação final

Antes de considerar o passo concluído, rodar o conjunto que toca RDO e cronograma:

```bash
.pythonlibs/bin/python -u -m pytest \
  tests/test_rota_rdo_salvar_unica.py \
  tests/test_rdo_legacy_endpoints_horas.py \
  tests/test_caracterizacao_apontamento_cronograma.py \
  tests/test_cronograma_apontamento_service.py \
  tests/test_importacao_fisico_financeiro.py \
  -p no:cacheprovider --tb=short -q
```

Nota sobre `run_tests.sh --gate`: o wrapper faz *polling* esperando um servidor em `http://localhost:5000` antes de invocar o pytest, e trava indefinidamente se não houver um. Para o gate sem browser, invocar o pytest direto: `.pythonlibs/bin/python -m pytest tests/ -m "not browser"`.
