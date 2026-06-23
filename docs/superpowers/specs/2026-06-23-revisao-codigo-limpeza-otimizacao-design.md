# Revisão de código, limpeza de arquivos mortos e otimização — Design

**Data:** 2026-06-23
**Autor:** Cássio Viller (com Claude Code)
**Status:** Aprovado para planejamento

## 1. Objetivo

Fazer uma passada de **revisão de código + limpeza + otimização** no SIGE (sistema de
gestão para construtoras, Flask/SQLAlchemy em produção), entregando:

1. Um **relatório de auditoria** versionado, com achados classificados por risco.
2. Um conjunto de **mudanças seguras e estagiadas** que reduzem cruft, removem código
   morto e corrigem falhas confirmadas — sem quebrar o sistema em produção.

Não é um refactor amplo nem reescrita. É a higiene que um bom dev faz no código em que
está trabalhando: achar o que está morto/quebrado, provar, e remover/corrigir com rede
de segurança.

## 2. Princípio reitor: seguro por construção

O sistema está em produção e **não tem tooling de qualidade nem CI de lint**. Toda
mudança precisa de rede de segurança:

- **Nada é "morto" por suposição** — precisa ser provado (sem referências, blueprint não
  registrado, não importado, não alcançável por rota/template).
- **Tudo é reversível** — preferir `git rm --cached` + `.gitignore` a `rm`; mudanças de
  código só após baseline de teste verde.
- **Estágios independentes** — limpeza de artefato (risco zero) é separada de remoção de
  código (risco médio) que é separada de otimização (risco de comportamento).
- **Checkpoints** — correções de código entram uma por vez, com testes, na execução.

## 3. Achados concretos que motivam o trabalho (levantados na auditoria inicial)

### 3.1 Arquivos mortos / artefatos versionados indevidamente
- Binários pesados no git: `entrega_baia_rev10.zip` (~8.7MB), `Projeto1.mpp`,
  `APRESENTACAO_Baia_REV10.pdf`, múltiplos `.xlsx`/`.pdf` em `attached_assets/`,
  `docs/manual_ciclo/Manual_Ciclo_SIGE.pdf`, `cache_facial.pkl`, `sige.db` (vazio).
- Imagens de teste versionadas: `tests/reports/*.png` (já no `.gitignore` daqui pra
  frente, mas ainda rastreadas).
- Scripts one-off no topo: `fix_*_admin_id.py` (7), `*_cli.py`,
  `diagnostico_veiculos_*.json`, `validacao_*.json`, `relatorio_*.txt/json`.
- `bypass_auth.py.disabled` (resíduo de bypass de autenticação — também é achado de
  segurança).
- `backups/legacy_*.csv` e `archive/legacy_cleanup/`.

### 3.2 Duplicação estrutural (módulos potencialmente mortos)
- Coexistem 23 módulos `*_views.py` no diretório raiz **e** um pacote `views/` (~20
  módulos). É uma migração de estrutura pela metade.
- Blueprints são registrados em `main.py` via blocos `try/except` (alguns do topo, alguns
  de `views/`). **Não se pode assumir** qual lado está morto — precisa mapear o que é
  efetivamente registrado e alcançável.

### 3.3 Falhas potenciais
- `try/except` no registro de blueprints em `main.py` que pode silenciar falha de boot
  (a tela só "some" em vez de falhar visível).
- Padrões de `except: pass` / bare `except` que engolem erros (a varrer).
- `bypass_auth.py.disabled` como risco de segurança latente.
- Arquivos gigantes (`migrations.py` 562KB, `models.py` 342KB, `views/rdo.py` 262KB) —
  risco de manutenção; candidatos a mapear (não necessariamente quebrar agora).

### 3.4 Otimização
- Hotspots de N+1 e recomputação nas views maiores (a confirmar por inspeção, não por
  suposição).

## 4. Abordagem escolhida

**Pipeline estagiado "Auditar → Limpar com segurança → Corrigir com checkpoint →
Otimizar".** Alternativas descartadas:

- *Refactor grande de uma vez* — risco alto demais p/ produção sem CI.
- *Só relatório, sem mudanças* — entrega menos do que o pedido (limpeza/otimização).

### Fase 0 — Baseline e tooling
- Rodar a suíte de testes existente e registrar o estado (verde/vermelho) como linha de
  base. Se houver vermelhos pré-existentes, documentar e não confundir com regressão.
- Adicionar `ruff` ao `pyproject.toml` com config conservadora (lint + format-check),
  **sem** rodar `--fix` ainda. Serve como ferramenta objetiva para achar imports/variáveis
  não usados, redefinições, etc.
- Opcional: `vulture` para candidatos a função/classe morta (sempre tratados como
  *candidatos*, nunca remoção automática).

### Fase 1 — Auditoria read-only (entrega: relatório)
Produzir `docs/auditoria/2026-06-23-auditoria-codigo.md` com seções:
- **Arquivos mortos** — lista classificada (artefato binário / one-off / backup /
  disabled) com tamanho e recomendação (untrack vs delete).
- **Módulos mortos** — mapa `*_views.py` topo vs `views/`: para cada um, se o blueprint é
  registrado, se há rotas alcançáveis, se é importado em algum lugar. Marcar VIVO /
  MORTO / INCERTO.
- **Código morto** — saída do ruff (F401/F811/etc.) + candidatos do vulture.
- **Possíveis falhas** — bare excepts, except-pass, registro frágil de blueprint,
  `bypass_auth`, e qualquer bug concreto encontrado, cada um com arquivo:linha e
  severidade.
- **Otimização** — hotspots concretos (N+1, recomputação) com arquivo:linha.

### Fase 2 — Limpeza segura (reversível)
- `git rm --cached` dos binários pesados + entradas no `.gitignore` (zip, mpp, pdf, xlsx
  de `attached_assets`, `cache_facial.pkl`, `sige.db`, `tests/reports/*.png`).
- Remover/arquivar one-offs e `.disabled` (recuperáveis via histórico git).
- `ruff --fix` **apenas** das regras seguras (imports não usados, etc.), **após** baseline
  verde; rodar testes de novo após.
- Commits pequenos e temáticos.

### Fase 3 — Correções com checkpoint
- Resolver a duplicação de módulos *comprovadamente* mortos (remover o lado morto, ou
  consolidar), um módulo por vez, com testes.
- Tornar o registro de blueprints menos silencioso onde for falha real (log/erro visível
  em vez de tela sumindo) — sem mudar comportamento de boot intencional.
- Corrigir bugs confirmados da Fase 1, um por vez.

### Fase 4 — Otimização medida
- Apenas hotspots confirmados da Fase 1, com correção pontual (ex.: eager loading p/
  N+1) e verificação de que o comportamento não muda.

## 5. Componentes / unidades de trabalho

- **Auditor (read-only):** roda ferramentas + inspeção, produz o relatório. Não muda
  código.
- **Faxina de artefatos:** opera só sobre arquivos versionados não-código (binários,
  one-offs). Independente do código.
- **Faxina de código:** opera sobre imports/funções mortas e módulos duplicados; depende
  do mapa da Fase 1.
- **Otimizador:** opera sobre hotspots confirmados; depende da Fase 1.

Cada unidade tem entrada (lista de alvos da Fase 1), saída (commits) e critério de
verificação (testes verdes, ruff sem novos erros).

## 6. Tratamento de erro e segurança

- Toda remoção de código é precedida de prova de não-uso e seguida de testes.
- Binários saem via `git rm --cached` (continuam no working tree e no histórico).
- Se a baseline de testes estiver vermelha, a Fase 0 documenta e as fases seguintes não
  introduzem novos vermelhos (comparação relativa, não absoluta).
- `bypass_auth.py.disabled`: remover do repo (já desabilitado); registrar no relatório
  como achado de segurança.

## 7. Testes / verificação

- **Baseline:** `./run_tests.sh` (ou `pytest`) antes de tudo.
- **Após cada fase de mudança:** rodar testes + `ruff check` e confirmar que não há novos
  erros nem regressões.
- **Critério de pronto:** relatório commitado; binários destrastreados; one-offs/disabled
  removidos; ruff limpo nas regras seguras; módulos mortos comprovados removidos sem
  regressão; otimizações confirmadas aplicadas e verificadas.

## 8. Fora de escopo (YAGNI)

- Reescrever/quebrar `migrations.py`, `models.py`, `views/rdo.py` em arquivos menores
  (apenas mapear como risco — quebrar é projeto à parte).
- Migração completa da estrutura flat → `views/` (só remover o lado morto comprovado).
- Introduzir CI/pipeline novo (só a config local de ruff).
- Refactors estéticos sem ganho de risco/manutenção.
