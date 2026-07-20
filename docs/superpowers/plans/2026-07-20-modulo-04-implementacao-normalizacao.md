# Módulo 04 — Normalização Determinística — Implementation Plan

> **For agentic workers:** fonte: spec `2026-07-17-modulo-04-normalizacao-deterministica.md`
> (decisão D1: sem API externa; tudo determinístico). Em conflito spec×este plano, este
> plano vence — ele reconcilia a spec com o contrato REAL do M03 já commitado.

**Goal:** `services/cronograma_normalizacao.py` — funções puras (sem I/O, sem DB) que
transformam o `json_bruto` do M03 em `json_normalizado` validado por JSON Schema
versionado, com nomes canônicos, fingerprints, classificação por regras e avisos.
Integrado à view do M03: upload → parse → **normaliza** → status `normalizado`.

## Fatos medidos que o executor precisa saber (2026-07-20)

- **Contrato de ENTRADA (json_bruto, M03 real):** `{"projeto": {"nome", "data_status"},
  "tarefas": [{id, uid, wbs, outline, nome, inicio, fim, dias, pct_project, resumo,
  marco, predecessoras: [{id, uid, tipo, lag_dias}], notas}]}`. Tipos: uid/wbs/outline
  podem ser null; `tipo` ∈ {FS,FF,SS,SF} ou null; datas ISO `YYYY-MM-DD` ou null.
- **Fixture real:** usar `parse_mspdi('CRONOGRAMA 16.07.xml')` — 103 tarefas, outlines
  0-4, raiz id=0 outline=0 resumo=true, **in-process sem JVM** (a spec citava 06.07/101
  porque o .xml não existia; o M03 provou os dois caminhos idênticos, então o .xml
  cobre). NÃO criar fixture-arquivo grande; parsear o .xml no teste.
- **jsonschema 4.26.0 já instalado** em .pythonlibs (2026-07-20). Falta declarar em
  `pyproject.toml` (`"jsonschema>=4.22"`).
- **`quantidade`/`unidade` NÃO existem no bruto do M03** (o MSPDI real não traz; spec
  §4 os menciona por herança do JSON das baias). No normalizado saem sempre `null`
  (schema permite); a fórmula do fingerprint usa `''` para ausentes — documentar.
- **Derivação de pai:** o bruto não tem ponteiro de pai. Derivar por pilha de outline
  na ordem do arquivo (tarefa com outline N → pai = última tarefa vista com outline
  N-1), mesma convenção `nivel=outline+1` de `importacao_fisico_financeiro.py`.
  `ordem` = posição no array (0-based). Outline saltando nível (N → N+2) gera aviso
  `outline_salto` e o pai é a última tarefa com outline < N.
- **Tabela de categorias** (dados no módulo, não if-chain): generalizada de
  `scripts/rebuild_baia_from_0607_mpp.py::etapa_de()` SEM os casos da obra
  (FAZENDA/AJR/MOLEDO ficam fora — M09 os mapeia manualmente). Manter: HIDRO, ELET,
  PRELIM, PORTAO, PINT, FECHA, ESTLSF, COBERT, ESTMET, FUND. Ordem importa (lista de
  pares, primeiro match vence). Sem match ⇒ `None` — nunca inventa.
- Pytest direto: `.pythonlibs/bin/python -u -m pytest tests/test_cronograma_normalizacao.py -p no:cacheprovider -q`.

## Contrato de SAÍDA (json_normalizado, para o M5) — spec §4 ajustada

```json
{"versao": "1.0",
 "projeto": {"nome": "...", "data_status": null},
 "tarefas": [{
   "chave": "uid:132", "uid": 132, "wbs": "1.3.2", "id_arquivo": 15,
   "nome_original": "Ferragens p/ fundação", "nome_normalizado": "FERRAGENS P FUNDACAO",
   "caminho": "OBRA ITU .../FUNDACAO/FERRAGENS P FUNDACAO", "fingerprint": "a3f9c2...16hex",
   "nivel": 3, "pai_chave": "uid:130", "ordem": 15,
   "inicio": "2026-07-01", "fim": "2026-07-08", "dias": 6.0,
   "is_resumo": false, "is_marco": false, "categoria_sugerida": "FUND",
   "predecessoras": [{"chave": "uid:130", "tipo": "FS", "lag_dias": 0.0}],
   "quantidade_total": null, "unidade": null, "pct_project": 100.0, "notas": null}],
 "avisos": [{"codigo": "sem_datas", "tarefa_chave": "uid:200", "mensagem": "..."}],
 "contadores": {"n_tarefas": 103, "n_folhas": 71, "n_avisos": {"sem_datas": 1}}}
```

- `chave`: `uid:<n>` se uid≠null; senão `wbs:<código>`; senão `fp:<fingerprint>` (§12).
- `predecessoras[].chave` resolvida pela MESMA regra, apontando para a tarefa-alvo.
- `nome_normalizado`: NFKD sem acento, casefold→UPPER, pontuação→espaço, colapso de
  espaços, remoção de sufixo ` (n)` de duplicata; dígitos significativos preservados
  ("BAIA 01" ≠ "BAIA 02").
- `fingerprint`: sha256 hex[:16] de `nome_normalizado|caminho_do_pai|dias|unidade|quantidade`
  (ausente ⇒ `''`) — SEM datas, SEM id/uid. Mudou a fórmula ⇒ bump `NORMALIZADOR_VERSAO`.
- Avisos (um código por caso, spec §4): `fim_antes_inicio`, `folha_sem_datas`,
  `duracao_zero_sem_marco`, `predecessora_inexistente`, `ciclo_predecessoras`,
  `outline_salto`, `nomes_duplicados_mesmo_pai` (→ `ambiguidade_potencial` quando
  também colide fingerprint), `pct_project_sera_ignorado` (1 aviso agregado se
  qualquer pct>0).
- Sanitização: strings sem control chars; nome ≤ 255; notas ≤ 2000.

## Task 1 (subagente): módulo puro completo + testes (TDD)

**Files:** Create `services/cronograma_normalizacao.py`,
`services/schemas/cronograma_bruto.schema.json`,
`services/schemas/cronograma_normalizado.schema.json`,
`tests/test_cronograma_normalizacao.py`.

API pública do módulo: `NORMALIZADOR_VERSAO = '1.0'`, `NormalizacaoError(Exception)`
(payload inválido contra schema — mensagem inclui o path do erro),
`normalizar_nome(str) -> str`, `caminho_hierarquico(...)`, `fingerprint(...)`,
`classificar(...)`, `detectar_inconsistencias(...)`, `normalizar(json_bruto) -> dict`
(valida entrada contra o schema bruto e a própria saída contra o normalizado).

Testes obrigatórios (spec §17): tabela de casos de `normalizar_nome`; fingerprint
estável/insensível a datas/sensível a nome-pai-duração; um teste por código de aviso;
pipeline com o XML real (103 tarefas, zero perda, valida contra schema); payload
inválido → `NormalizacaoError`; **determinismo** (duas execuções, JSON serializado
idêntico); **idempotência** de `normalizar_nome`; **import-lint** (o módulo importado
não pode ter `models`, `app`, `flask`, `requests`, `sqlalchemy` em `sys.modules`
novos — teste em subprocess `python -c "import services.cronograma_normalizacao"`).

Commit: `feat(cronograma): normalização determinística com schemas versionados (M04)`.

## Task 2 (main loop, após review da Task 1): integração na view do M03

**Files:** Modify `views/cronograma_importacao.py`, `tests/test_upload_cronograma.py`,
`pyproject.toml` (+jsonschema), `docs/superpowers/plans/` (fecho M04).

Na rota, após `parse_cronograma` OK: `normalizar(dados)` → `imp.json_normalizado`,
`imp.normalizador_versao = NORMALIZADOR_VERSAO`, `imp.status = 'normalizado'`, evento
`normalizado` (detalhes = `contadores`). `NormalizacaoError` → `status='falhou'`,
`erro`, evento `normalizacao_erro` → 422 (re-upload permitido: dedup ignora `falhou`).
Resposta 201 passa a `{"status": "normalizado"}`. Atualizar os testes de upload
(status/eventos esperados: `{upload, parse_ok, normalizado}`) + 1 teste novo:
`json_normalizado` tem 103 tarefas com `chave` única e `contadores` no evento.

Commit: `feat(cronograma): pipeline de importação normaliza após parse (M04)`.

## Critérios de aceite (spec §18 + §22)

1. XML real normaliza validando contra o schema, 103 tarefas, zero perda.
2. Duas execuções ⇒ saída bit-idêntica.
3. Módulo puro: nenhum import de models/db/flask/requests (teste automatizado).
4. Upload real termina em `status='normalizado'` com 3 eventos.
5. Schemas versionados no repo; `normalizador_versao` gravado na importação.
