# Revisão de código, limpeza e otimização — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auditar o SIGE, destrastrear binários/arquivos mortos, remover código morto comprovado e aplicar correções/otimizações seguras — sem quebrar o sistema em produção.

**Architecture:** Pipeline estagiado — (0) baseline + tooling, (1) auditoria read-only que vira relatório, (2) limpeza segura e reversível, (3) correções com checkpoint, (4) otimização medida. Cada mudança é provada antes e verificada depois.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, uv (deps), pytest+Playwright (testes browser), ruff (a adicionar).

---

## Convenções de verificação deste plano

A suíte oficial (`run_tests.sh`) é **Playwright com browser real e exige servidor em
`localhost:5000`** — é pesada e não serve como gate por micro-passo. Portanto:

- **GATE RÁPIDO (usar entre passos):** smoke check de boot —
  ```bash
  python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))"
  ```
  Esperado: termina com `BLUEPRINTS 37` e exit code 0. Se o número de blueprints cair ou
  der exceção, a mudança quebrou o boot → reverter.
- **GATE DE LINT:** `ruff check .` não pode introduzir erros novos vs. a baseline da Task 1.
- **GATE PESADO (manual, no fim):** subir o servidor e rodar `bash run_tests.sh` quando
  viável. Registrado como Task 13.

Commits pequenos e temáticos. Nada de `rm` direto em binário versionado — usar
`git rm --cached`.

---

## Fase 0 — Baseline e tooling

### Task 1: Capturar baseline e adicionar ruff

**Files:**
- Modify: `pyproject.toml` (adicionar `ruff` à lista `dependencies` e bloco `[tool.ruff]`)
- Create: `docs/auditoria/2026-06-23-baseline.md`

- [ ] **Step 1: Registrar baseline de boot e contagem de blueprints**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" 2>&1 | tail -1
```
Expected: `BLUEPRINTS 37`

- [ ] **Step 2: Instalar ruff e registrar versão**

Run:
```bash
.pythonlibs/bin/pip install ruff vulture 2>&1 | tail -2
ruff --version
```
Expected: imprime versão do ruff (ex.: `ruff 0.x.y`).

- [ ] **Step 3: Adicionar ruff às deps e config conservadora**

Em `pyproject.toml`, adicionar `"ruff>=0.6"` ao final da lista `dependencies` (segue o
padrão do projeto, que já lista `pytest`/`playwright` ali), e acrescentar ao fim do
arquivo:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
# Auditoria de higiene; não reformatar o mundo. Regras seguras e de detecção.
extend-exclude = [
    ".pythonlibs", "__pycache__", "archive", "backups", "attached_assets",
    "migrations.py", "uv.lock",
]

[tool.ruff.lint]
# F = pyflakes (imports/vars não usados, redefinição), E9 = erros de sintaxe,
# B = bugbear (bare except, etc.). Conservador de propósito.
select = ["F", "E9", "B"]
ignore = []
```

- [ ] **Step 4: Rodar ruff e salvar a baseline de lint**

Run:
```bash
ruff check . --statistics 2>&1 | tee docs/auditoria/2026-06-23-baseline.md
echo "" >> docs/auditoria/2026-06-23-baseline.md
echo "BLUEPRINTS baseline: 37" >> docs/auditoria/2026-06-23-baseline.md
```
Expected: gera o arquivo com a contagem de violações por regra. Esse número é a baseline
— fases seguintes não podem aumentá-lo (exceto onde a fase reduz).

- [ ] **Step 5: Gate rápido e commit**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
git add pyproject.toml docs/auditoria/2026-06-23-baseline.md
git commit -m "chore(tooling): adiciona ruff + baseline de lint e boot"
```
Expected: gate imprime `BLUEPRINTS 37`; commit criado.

---

## Fase 1 — Auditoria read-only (entrega: relatório)

### Task 2: Inventário de arquivos mortos / artefatos versionados

**Files:**
- Create: `docs/auditoria/2026-06-23-inventario-arquivos.md`

- [ ] **Step 1: Listar binários pesados versionados**

Run:
```bash
{
echo "## Binários/artefatos versionados (candidatos a git rm --cached)"
git ls-files | grep -iE '\.(zip|mpp|pkl|db)$'
git ls-files | grep -iE '\.(xlsx|pdf)$' | grep -iE 'attached_assets|entrega_baia|Manual_Ciclo|Projeto1|APRESENTACAO'
echo ""
echo "## Imagens de teste versionadas"
git ls-files tests/reports
echo ""
echo "## One-offs / diagnósticos / disabled"
git ls-files | grep -E '^(fix_.*\.py|diagnostico_.*\.json|validacao_.*\.json|relatorio_.*\.(txt|json)|bypass_auth\.py\.disabled)$'
echo ""
echo "## Diretórios de resíduo"
git ls-files archive backups | head -50
} > docs/auditoria/2026-06-23-inventario-arquivos.md
cat docs/auditoria/2026-06-23-inventario-arquivos.md
```
Expected: arquivo populado com as listas acima.

- [ ] **Step 2: Para cada one-off, checar se é importado em código vivo**

Run (exemplo abrangente — confirma que os `fix_*`/`*_cli` não são importados por nada):
```bash
for f in fix_all_admin_id_universal fix_custo_obra_admin_id fix_departamento_admin_id fix_funcao_admin_id fix_horario_trabalho_admin_id fix_rdo_mao_obra_admin_id fix_registro_alimentacao_admin_id; do
  echo -n "$f: "; grep -rl --include='*.py' -E "import $f|from $f" . --exclude-dir=.pythonlibs --exclude-dir=__pycache__ | grep -v "$f.py" || echo "SEM IMPORT (morto)"
done
```
Expected: cada um imprime `SEM IMPORT (morto)` ou as linhas que o referenciam. Anotar o
resultado no fim do inventário sob `## Referências dos one-offs`.

- [ ] **Step 3: Commit do inventário**

```bash
git add docs/auditoria/2026-06-23-inventario-arquivos.md
git commit -m "docs(auditoria): inventário de arquivos mortos/artefatos"
```

### Task 3: Mapa de módulos vivos vs mortos (views topo vs pacote views/)

**Files:**
- Create: `docs/auditoria/2026-06-23-mapa-modulos.md`
- Create: `scripts/auditoria_mapa_modulos.py`

- [ ] **Step 1: Escrever script que mapeia blueprints registrados → módulo de origem**

Create `scripts/auditoria_mapa_modulos.py`:
```python
"""Auditoria: mapeia cada blueprint registrado ao módulo Python que o define,
e cruza com os arquivos *_views.py do topo e do pacote views/ para achar módulos
que NÃO contribuem nenhum blueprint vivo (candidatos a morto)."""
import importlib
import app as app_module

app = app_module.app

registrados = {}
for name, bp in app.blueprints.items():
    mod = getattr(bp, "import_name", "?")
    registrados[name] = mod

print("# Blueprints registrados (", len(registrados), ")")
for name, mod in sorted(registrados.items()):
    print(f"- {name}  <-  {mod}")

modulos_vivos = {m.split(".")[0] if "." in m else m for m in registrados.values()}

import glob, os
candidatos = sorted(
    [os.path.splitext(os.path.basename(p))[0] for p in glob.glob("*_views.py")]
    + ["views." + os.path.splitext(os.path.basename(p))[0] for p in glob.glob("views/*.py") if not p.endswith("__init__.py")]
)
print("\n# Módulos *_views candidatos vs vivos")
for c in candidatos:
    base = c.split(".")[-1]
    vivo = base in {mm.split(".")[-1] for mm in modulos_vivos} or c in modulos_vivos
    print(f"- {c}: {'VIVO' if vivo else 'INCERTO/sem blueprint registrado'}")
```

- [ ] **Step 2: Rodar o script e salvar o mapa**

Run:
```bash
python scripts/auditoria_mapa_modulos.py > docs/auditoria/2026-06-23-mapa-modulos.md 2>&1
cat docs/auditoria/2026-06-23-mapa-modulos.md
```
Expected: lista os 37 blueprints e marca cada módulo como VIVO ou INCERTO.

- [ ] **Step 3: Para cada módulo INCERTO, confirmar não-uso por import/template**

Run (substituir `<MOD>` por cada módulo marcado INCERTO):
```bash
MOD=<MOD>; echo "== $MOD =="; \
grep -rl --include='*.py' -E "import ${MOD}\b|from ${MOD} " . --exclude-dir=.pythonlibs --exclude-dir=__pycache__ | grep -v "${MOD}.py"; \
grep -rl "${MOD#views.}" templates/ 2>/dev/null | head
```
Expected: sem resultados = forte candidato a morto. Anotar veredito (MORTO/VIVO) por
módulo no fim do mapa, sob `## Veredito final`.

- [ ] **Step 4: Gate rápido e commit**

```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
git add scripts/auditoria_mapa_modulos.py docs/auditoria/2026-06-23-mapa-modulos.md
git commit -m "docs(auditoria): mapa de módulos vivos vs mortos"
```
Expected: `BLUEPRINTS 37`.

### Task 4: Código morto + padrões de falha

**Files:**
- Create: `docs/auditoria/2026-06-23-codigo-e-falhas.md`

- [ ] **Step 1: Código morto via ruff (imports/vars não usados, redefinições)**

Run:
```bash
{
echo "## Código morto (ruff F401/F811/F841)"
ruff check . --select F401,F811,F841 --output-format concise 2>&1 | grep -v "^Found\|^\[\*\]" | head -200
echo ""
echo "## Candidatos a função/classe morta (vulture, confiança >=80%)"
vulture . --min-confidence 80 --exclude .pythonlibs,archive,backups,attached_assets,migrations.py 2>/dev/null | head -120
} > docs/auditoria/2026-06-23-codigo-e-falhas.md
```
Expected: arquivo com listas de imports não usados e candidatos do vulture.

- [ ] **Step 2: Padrões de falha — bare except e except-pass**

Run:
```bash
{
echo ""
echo "## Bare except (B / E722)"
ruff check . --select E722,B904 --output-format concise 2>&1 | head -120
echo ""
echo "## except: pass (engole erro) — grep textual"
grep -rn --include='*.py' -A1 -E "except[^:]*:\s*$" . --exclude-dir=.pythonlibs --exclude-dir=__pycache__ --exclude-dir=archive | grep -B1 -E "^\s*[0-9-]+\s*pass\b" | head -80
echo ""
echo "## Registro de blueprint silencioso no boot (main.py try/except)"
grep -n -A3 "register_blueprint" main.py | grep -iE "except|pass|WARN|error" | head -40
} >> docs/auditoria/2026-06-23-codigo-e-falhas.md
```
Expected: anexa as seções. Pode haver muitos hits — é esperado; serão triados na Task 5.

- [ ] **Step 3: Commit**

```bash
git add docs/auditoria/2026-06-23-codigo-e-falhas.md
git commit -m "docs(auditoria): código morto e padrões de falha"
```

### Task 5: Relatório consolidado de auditoria (com triagem e severidade)

**Files:**
- Create: `docs/auditoria/2026-06-23-RELATORIO.md`

- [ ] **Step 1: Escrever o relatório consolidando Tasks 2–4**

Create `docs/auditoria/2026-06-23-RELATORIO.md` com estas seções (preencher a partir dos
arquivos das Tasks 2–4; cada item precisa de `arquivo:linha` quando for código):

```markdown
# Relatório de Auditoria SIGE — 2026-06-23

## Resumo executivo
- Nº de binários a destrastrear: __
- Nº de one-offs/disabled a remover: __
- Nº de módulos *_views MORTOS comprovados: __ (listar)
- Nº de imports não usados (ruff F401): __
- Achados de falha por severidade: ALTA __ / MÉDIA __ / BAIXA __

## A. Arquivos mortos (ação: Fase 2)
| arquivo | tipo | tamanho | ação (untrack/delete) |

## B. Módulos mortos (ação: Fase 3, gated)
| módulo | veredito | evidência (sem import/sem blueprint/sem template) |

## C. Código morto (ação: Fase 2 ruff --fix seguro / Fase 3 manual)
(imports não usados; candidatos vulture com risco)

## D. Possíveis falhas (ação: Fase 3)
| id | arquivo:linha | descrição | severidade | correção proposta |
- Incluir: bare excepts, except-pass que escondem erro, registro frágil de blueprint,
  bypass_auth.py.disabled (segurança).

## E. Otimização (ação: Fase 4)
| id | arquivo:linha | hotspot (N+1 / recomputação) | correção proposta |
- Inspecionar manualmente os maiores views vivos (ex.: views/rdo.py, views/obras.py,
  ponto_views.py) por loops com query dentro.

## F. Risco de manutenção (fora de escopo agora — só registrar)
- migrations.py (562KB), models.py (342KB), views/rdo.py (262KB).
```

- [ ] **Step 2: Triar D e E manualmente (não despejar grep cru)**

Para cada hit de falha das Tasks 4, abrir o arquivo na linha e decidir severidade real:
- **ALTA:** engole erro que mascara bug/segurança, ou falha de boot silenciosa de rota
  usada.
- **MÉDIA:** except amplo recuperável mas sem log.
- **BAIXA:** import morto, except amplo em script utilitário.
Para E, confirmar N+1 lendo o trecho (query dentro de `for`). Só listar o que foi visto.

- [ ] **Step 3: Commit do relatório**

```bash
git add docs/auditoria/2026-06-23-RELATORIO.md
git commit -m "docs(auditoria): relatório consolidado com triagem e severidade"
```

**>>> CHECKPOINT HUMANO:** revisar o RELATORIO.md antes de qualquer mudança das Fases 2–4.

---

## Fase 2 — Limpeza segura (reversível)

### Task 6: Destrastrear binários pesados + .gitignore

**Files:**
- Modify: `.gitignore`
- Untrack (git rm --cached): binários listados no inventário

- [ ] **Step 1: Adicionar padrões ao .gitignore**

Acrescentar ao fim de `.gitignore`:
```gitignore
# Artefatos pesados / entregáveis (não devem ir ao git)
*.zip
*.mpp
*.pkl
/sige.db
APRESENTACAO_*.pdf
Projeto1.mpp
docs/manual_ciclo/*.pdf
# Planilhas/PDFs colados em attached_assets
attached_assets/*.xlsx
attached_assets/*.pdf
# Screenshots de teste (runtime)
tests/reports/*.png
```

- [ ] **Step 2: Destrastrear (mantém no working tree, sai do índice)**

Run:
```bash
git rm --cached -r --ignore-unmatch \
  "10. Kabod Cabana - Baias de bovinos-20260611T214935Z-3-001.zip" \
  entrega_baia_rev10.zip Projeto1.mpp cache_facial.pkl sige.db \
  APRESENTACAO_Baia_REV10.pdf "docs/manual_ciclo/Manual_Ciclo_SIGE.pdf"
git rm --cached --ignore-unmatch attached_assets/*.xlsx attached_assets/*.pdf
git rm --cached --ignore-unmatch tests/reports/*.png
```
Expected: lista os arquivos removidos do índice. Os arquivos continuam no disco.

- [ ] **Step 3: Gate rápido (boot não pode quebrar)**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
```
Expected: `BLUEPRINTS 37` (binários não são importados; boot intacto).

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore(repo): destrastreia binários pesados e ignora artefatos"
```

### Task 7: Remover one-offs, diagnósticos e .disabled

**Files:**
- Delete: one-offs confirmados MORTOS na Task 2, Step 2

- [ ] **Step 1: Remover os que a Task 2 provou sem import**

Run (somente os confirmados SEM IMPORT na Task 2; ajustar a lista conforme o veredito):
```bash
git rm --ignore-unmatch \
  fix_all_admin_id_universal.py fix_custo_obra_admin_id.py fix_departamento_admin_id.py \
  fix_funcao_admin_id.py fix_horario_trabalho_admin_id.py fix_rdo_mao_obra_admin_id.py \
  fix_registro_alimentacao_admin_id.py \
  diagnostico_veiculos_20250929_113736.json \
  relatorio_multitenant.txt relatorio_rapido.txt relatorio_templates.txt \
  relatorio_validacao_sige_v8.json validacao_sige_v8_resultados.json \
  bypass_auth.py.disabled
```
Expected: arquivos removidos (recuperáveis via histórico git).

- [ ] **Step 2: Gate rápido**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
```
Expected: `BLUEPRINTS 37`.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(repo): remove scripts one-off, diagnósticos e bypass_auth desabilitado"
```

### Task 8: ruff --fix das regras seguras (imports não usados)

**Files:**
- Modify: vários `.py` (apenas remoção de imports/vars não usados)

- [ ] **Step 1: Aplicar fix só de F401/F811 (seguro)**

Run:
```bash
ruff check . --select F401,F811 --fix 2>&1 | tail -5
```
Expected: relata quantos fixes aplicou.

- [ ] **Step 2: Revisar o diff (não pode remover import com efeito colateral)**

Run:
```bash
git diff --stat
```
Inspecionar: se algum import removido for de módulo que registra blueprint/handler por
import (ex.: `import event_manager`, `import handlers.*` em `app.py`), **reverter aquele
hunk** — esses imports têm efeito colateral e o ruff pode marcá-los como não usados.

- [ ] **Step 3: Gate rápido (crítico aqui)**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
```
Expected: `BLUEPRINTS 37`. Se cair, um import com efeito colateral foi removido →
`git checkout -- <arquivo>` e refazer manualmente.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "style(lint): remove imports não usados (ruff F401/F811 seguro)"
```

---

## Fase 3 — Correções com checkpoint

> As Tasks 9–11 são instanciadas a partir do RELATORIO.md (seções B e D). Para cada
> item, criar uma sub-tarefa seguindo o template do passo correspondente. Uma mudança por
> commit, gate rápido após cada uma.

### Task 9: Tornar visível a falha de registro de blueprint (achado D, severidade)

**Files:**
- Modify: `main.py` (blocos `try/except` de `register_blueprint` que hoje só logam WARN)

- [ ] **Step 1: Localizar os blocos que escondem falha de rota usada**

Run:
```bash
grep -n -B1 -A4 "register_blueprint" main.py | grep -iE "try|except|WARN|register_blueprint" | head -60
```
Para cada bloco, decidir pelo RELATORIO: se a rota é usada, a falha deve ser visível.

- [ ] **Step 2: Elevar o log de WARN para ERROR com stacktrace (sem mudar o boot)**

Para cada `except Exception as e:` que apenas faz `logger.error("[WARN] ...")`, trocar a
mensagem para incluir `exc_info=True`, p.ex.:
```python
    except Exception as e:
        logger.error(f"[BOOT] Falha ao registrar blueprint X: {e}", exc_info=True)
```
Não mudar o fato de o boot continuar (decisão de design existente) — só deixar o erro
rastreável. Repetir por bloco identificado.

- [ ] **Step 3: Gate rápido e commit**

```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
git add main.py
git commit -m "fix(boot): registro de blueprint falha de forma rastreável (exc_info)"
```
Expected: `BLUEPRINTS 37`.

### Task 10: Remover módulos *_views MORTOS comprovados (seção B)

**Files:**
- Delete: cada módulo com veredito MORTO no mapa (Task 3)

> Repetir este bloco para CADA módulo MORTO, um commit por módulo.

- [ ] **Step 1: Reconfirmar não-uso imediatamente antes de remover**

Run (substituir `<MOD>` e `<arquivo>`):
```bash
MOD=<MOD>
grep -rl --include='*.py' -E "import ${MOD##*.}\b|from ${MOD} " . --exclude-dir=.pythonlibs --exclude-dir=__pycache__ | grep -v "<arquivo>"
grep -rln "${MOD##*.}" templates/ 2>/dev/null
```
Expected: nenhuma saída. Se houver, NÃO remover — reclassificar como VIVO no mapa.

- [ ] **Step 2: Remover o módulo**

Run:
```bash
git rm <arquivo>
```

- [ ] **Step 3: Gate rápido (boot tem que manter 37 blueprints)**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
```
Expected: `BLUEPRINTS 37`. Se cair ou der ImportError, o módulo era usado →
`git checkout -- <arquivo>` e reclassificar.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(views): remove módulo morto <arquivo> (sem blueprint/import/template)"
```

### Task 11: Corrigir bugs confirmados (seção D, severidade ALTA/MÉDIA)

**Files:**
- Modify: arquivos apontados na seção D do RELATORIO
- Test: `tests/` quando a correção for testável por unidade

> Repetir para CADA achado D priorizado (ALTA primeiro). Um commit por correção.

- [ ] **Step 1: Reproduzir/entender o achado**

Abrir `arquivo:linha` do achado. Para `except: pass` que esconde erro: substituir por
captura específica com log, p.ex.:
```python
    except SpecificError as e:
        logger.warning(f"<contexto>: {e}")
        # comportamento de fallback explícito
```
Nunca trocar `except: pass` por `raise` cego se o caminho de fallback é intencional —
preservar o comportamento, só deixar de engolir silenciosamente.

- [ ] **Step 2: Se testável por unidade, escrever teste que falha**

Quando o bug for de lógica pura (não-browser), criar `tests/test_<area>_fix.py` com um
caso que falha antes da correção. Rodar:
```bash
.pythonlibs/bin/pytest tests/test_<area>_fix.py -v
```
Expected: FAIL antes da correção. (Se o achado só for reproduzível via browser, pular o
teste unitário e validar no GATE PESADO da Task 13; registrar isso no commit.)

- [ ] **Step 3: Aplicar a correção mínima**

Editar `arquivo:linha` conforme a "correção proposta" do relatório.

- [ ] **Step 4: Verificar**

Run:
```bash
.pythonlibs/bin/pytest tests/test_<area>_fix.py -v 2>/dev/null; python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
```
Expected: teste PASS (se houver) e `BLUEPRINTS 37`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix(<area>): <descrição do achado D corrigido>"
```

---

## Fase 4 — Otimização medida

### Task 12: Aplicar otimizações de hotspots confirmados (seção E)

**Files:**
- Modify: arquivos da seção E do RELATORIO

> Repetir para CADA hotspot confirmado. Um commit por otimização.

- [ ] **Step 1: Confirmar o N+1 / recomputação lendo o trecho**

Abrir `arquivo:linha`. Confirmar query dentro de loop ou recomputação repetida.

- [ ] **Step 2: Aplicar correção pontual preservando o resultado**

Para N+1 em SQLAlchemy, usar eager loading, p.ex.:
```python
from sqlalchemy.orm import joinedload
itens = Model.query.options(joinedload(Model.relacao)).filter_by(...).all()
```
Para recomputação, içar o cálculo para fora do loop guardando em variável. **Não** mudar
o conjunto de resultados — só como é obtido.

- [ ] **Step 3: Verificar boot e equivalência**

Run:
```bash
python -c "import app; print('BLUEPRINTS', len(app.app.blueprints))" | tail -1
```
Expected: `BLUEPRINTS 37`. Se a rota for testável via browser, validar na Task 13.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "perf(<area>): elimina N+1/recomputação em <arquivo>"
```

---

## Fase 5 — Verificação final

### Task 13: Gate pesado (suíte Playwright) e fechamento

**Files:**
- Modify: `docs/auditoria/2026-06-23-RELATORIO.md` (marcar itens resolvidos)

- [ ] **Step 1: Subir servidor e rodar a suíte (quando viável)**

Run (em terminais separados; o segundo só após o server responder em :5000):
```bash
# terminal A: subir o app
python main.py &
# terminal B:
bash run_tests.sh 2>&1 | tail -40
```
Expected: comparar com a baseline da Task 1 — não pode haver NOVAS falhas vs. o estado
inicial. Falhas pré-existentes (documentadas) não contam como regressão.

- [ ] **Step 2: Confirmar lint não regrediu**

Run:
```bash
ruff check . --statistics 2>&1 | tail -20
```
Expected: contagem ≤ baseline da Task 1 (idealmente menor após a Task 8).

- [ ] **Step 3: Atualizar relatório e commit final**

Marcar no RELATORIO.md o que foi resolvido (A–E) e o que ficou registrado como
risco (F). Run:
```bash
git add -A
git commit -m "docs(auditoria): fecha relatório com itens resolvidos e riscos remanescentes"
```

---

## Mapa de cobertura do spec (self-review)

- Spec §3.1 Arquivos mortos → Tasks 2, 6, 7
- Spec §3.2 Módulos duplicados/mortos → Tasks 3, 10
- Spec §3.3 Falhas (excepts, boot, bypass_auth) → Tasks 4, 7, 9, 11
- Spec §3.4 / §4 Fase 4 Otimização → Tasks 5(E), 12
- Spec §4 Fase 0 baseline+tooling → Task 1
- Spec §4 Fase 1 relatório → Tasks 2–5
- Spec §6 segurança (reversível, git rm --cached) → Tasks 6, 7 (e gates em todas)
- Spec §7 testes/verificação → "Convenções de verificação", gates por task, Task 13
- Spec §8 fora de escopo (não quebrar arquivos gigantes; não migrar estrutura toda) →
  respeitado; só registrado em RELATORIO seção F
```
