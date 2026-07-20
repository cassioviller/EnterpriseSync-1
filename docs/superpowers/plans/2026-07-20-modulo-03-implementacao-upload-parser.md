# Módulo 03 — Upload e Parser de Cronograma — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development ou superpowers:executing-plans, tarefa a tarefa. Fontes: spec `2026-07-17-modulo-03-upload-parser-mpp.md` **revisada pelo adendo** `2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md` (MSPDI primário; validado contra export real do Project — 103 tarefas, zero divergências). Em conflito spec×adendo, o adendo vence.

**Goal:** Upload de cronograma dentro da obra (`.xml` MSPDI primário, `.mpp` opcional com Java), validado, com hash/dedup, persistido, parseado para o contrato JSON do §10 da spec, registrado em `CronogramaImportacao` (M02) com eventos.

**Architecture:** `services/mspdi_parser.py` (stdlib, in-process) emite o contrato completo; `services/mpp_parser.py` despacha por extensão e isola o MPXJ em subprocess quando houver Java; `views/cronograma_importacao.py` (blueprint novo) faz upload→validação→hash→dedup→storage→parse síncrono→status/eventos. Sem Java, `.mpp` falha com instrução de exportar XML — **a contingência `json_cli` da spec morre** (adendo §4.2).

**Tech Stack:** stdlib (`xml.etree`, `hashlib`, `re`), Flask/SQLAlchemy, `secure_filename` (werkzeug). MPXJ/JPype/JDK **opcionais** — nada de Docker/pyproject neste módulo (adendo §4.3; decisão de declarar Java fica para o M10).

---

## Fatos medidos que o executor precisa saber (2026-07-20, `CRONOGRAMA 16.07.xml` real do Project)

- `UID`, `WBS`, `Milestone`, `Summary`, `OutlineLevel`: presentes em 103/103 tarefas. `Notes`: 0/103 (→ null). `StatusDate` do projeto: ausente (→ null).
- `PredecessorLink` (66 vínculos): campos `PredecessorUID`, `Type`, `CrossProject`, `LinkLag`, `LagFormat`. `Type` observados: `{0, 1, 3}`. `LinkLag` observados: 0, 4800, 9600, 14400, 24000, 28800 — **décimos de minuto** (4800 = 480min = 8h = 1 dia útil → `lag_dias = LinkLag/4800`).
- **NÃO ASSUMIR o mapeamento de `Type`→FS/SS/FF/SF de memória.** A Task 2 verifica contra o MPXJ (`getType()` por vínculo) nos 3 pares de arquivos do repo. Tabela candidata (a confirmar): `0=FF, 1=FS, 2=SF, 3=SS`.
- Parser base de 9 campos + mapa UID→ID: código pronto no adendo (Task 2 de lá) — usar como ponto de partida; a armadilha das predecessoras por UID está documentada lá (§2).
- Precedentes no repo: hash `NotaFiscal.xml_hash` (`models.py:1965`); storage por env `UPLOADS_PATH`; blueprint registrado em `main.py` (padrão dos ~17 extras); decorator `cronograma_import_required` (`decorators.py`, M01); tabelas/JSON do M02 (`CronogramaImportacao`, `CronogramaImportacaoEvento`).
- Pytest direto sempre (`.pythonlibs/bin/python -u -m pytest ... -p no:cacheprovider`); `run_tests.sh` trava sem servidor. Java existe NESTE ambiente dev (glob `/nix/store/*temurin*`), então testes `.mpp` rodam aqui, mas devem `skipif not java_disponivel()` (marker `java`).

## Contrato de saída do parser (ambos os caminhos)

O §10 da spec, com `projeto.data_status` null quando ausente:

```json
{"projeto": {"nome": "Obra Itu - ...", "data_status": null},
 "tarefas": [{"id": 15, "uid": 132, "wbs": "1.3.2", "outline": 3,
   "nome": "FERRAGENS PARA FUNDACAO", "inicio": "2026-07-01", "fim": "2026-07-08",
   "dias": 6.0, "pct_project": 100.0, "resumo": false, "marco": false,
   "predecessoras": [{"id": 14, "uid": 130, "tipo": "FS", "lag_dias": 0.0}],
   "notas": null}]}
```

Diferenças deliberadas vs spec §10: sem `recursos`/`custom` nesta fase (o arquivo real não os tem; M04 não os consome; "dados ausentes ficam ausentes" — spec §12.3). Campos legados (`pct_fisico`, `predecessoras` como lista de ids) NÃO existem neste contrato — a projeção legada é responsabilidade do script de paridade e do CLI (Task 3).

---

## Task 1: `services/mspdi_parser.py` — contrato completo (TDD)

**Files:** Create `services/mspdi_parser.py`, `tests/test_mspdi_parser.py`, `tests/fixtures/mspdi_minimo.xml`

1. Fixture mínima: 2 tarefas (resumo + filha marco), com `WBS`, `Milestone`, `PredecessorLink` com `Type` e `LinkLag=4800`, predecessora referenciando UID (não ID). Testes: campos do contrato; `lag_dias == 1.0`; mapeamento UID→ID nas predecessoras (`id` correto); rejeição de XML não-MSPDI (`ValueError`, root ≠ `{http://schemas.microsoft.com/project}Project`); `notas`/`data_status` null quando ausentes. Rodar → vermelho.
2. Implementar `parse_mspdi(caminho) -> dict` partindo do código do adendo (Task 2 Step 3 de lá), estendido para o contrato acima. `tipo` do vínculo: mapear por tabela `_TIPO_VINCULO = {...}` definida na Task 2 — até lá, usar a candidata e marcar `# VERIFICAR-T2`. Duração: manter `_duracao_dias` do adendo (`_HORAS_POR_DIA = 8.0`).
3. Teste de integração com o arquivo real: `parse_mspdi('CRONOGRAMA 16.07.xml')` → 103 tarefas, todas com `uid` e `wbs` não nulos, 66 predecessoras no total, `projeto.nome == 'Obra Itu - Baias Fazenda Santa Mônica'`.
4. Verde → commit `feat(cronograma): parser MSPDI stdlib com contrato completo (M03)`.

## Task 2: paridade estendida + tabela de tipos verificada

**Files:** Create `scripts/verificar_paridade_mspdi.py`; Modify `services/mspdi_parser.py` (tabela `_TIPO_VINCULO` confirmada)

1. Script no molde do adendo (Task 2 Step 5 de lá), com DUAS camadas:
   - **Legada** (9 campos): projeta o contrato novo para o shape de `dump_mpp.py` (`pct_fisico=pct_project`, `predecessoras=[p['id'] for ...]`) e compara com `scripts/dump_mpp.py::dump`. Esperado: 0 divergências nos 3 arquivos (`06.07`, `OFICIAL`, `16.07` — o último contra o `.xml` real).
   - **Estendida** (só onde o MPXJ expõe): `uid`↔`getUniqueID`, `wbs`↔`getWBS`, `marco`↔`getMilestone`, e por vínculo `tipo`↔`RelationType`/`lag_dias`↔`getLag`. É AQUI que a tabela `_TIPO_VINCULO` é confirmada: se a candidata divergir do MPXJ, corrigir a tabela no parser e re-rodar até 0 divergências. Remover o marcador `# VERIFICAR-T2`.
2. Rodar nos 3 pares; imprimir resumo por arquivo; exit ≠ 0 em divergência. Saídas no commit message.
3. Commit `test(cronograma): paridade MSPDI×MPXJ estendida — tabela de vínculos verificada`.

## Task 3: despacho, subprocess e CLI

**Files:** Create `services/mpp_parser.py`, `services/mpp_parser_worker.py`; Modify `scripts/dump_mpp.py`; Modify `tests/test_mspdi_parser.py` (ou arquivo novo `tests/test_mpp_parser.py`)

1. `services/mpp_parser.py`: `MppParserError(motivo, mensagem)` com `motivo ∈ {java_indisponivel, arquivo_corrompido, timeout, erro_mpxj, extensao_invalida}`; `java_disponivel()` (extraída de `scripts/dump_mpp.py::_achar_java_home`); `parse_cronograma(caminho, timeout_s=120)` — `.xml` → `parse_mspdi` in-process; `.mpp` → subprocess `[sys.executable, '-m', 'services.mpp_parser_worker', caminho]` com `subprocess.run(..., timeout=timeout_s, capture_output=True)`, stdout = JSON do contrato; sem Java → `MppParserError('java_indisponivel', MSG_SEM_JAVA)` com a instrução de exportar XML (texto no adendo Task 3).
2. `services/mpp_parser_worker.py`: o `dump()` atual ampliado para o contrato (uid=getUniqueID, wbs=getWBS, marco=getMilestone, pct_project=getPercentageComplete, predecessoras com tipo/lag via getType/getLag convertido a dias, notas=getNotes). Imprime o JSON no stdout e sai 0; erro → stderr + exit ≠ 0 (o orquestrador tipifica: OLE2 inválido → `arquivo_corrompido`; demais → `erro_mpxj`).
3. Testes: `.xml` despacha sem Java (monkeypatch `java_disponivel=False` → funciona); `.mpp` sem Java → erro tipado com 'Salvar como' na mensagem; extensão `.txt` → `extensao_invalida`; **timeout comprovado**: `.mpp` real com `timeout_s=0.01` → `MppParserError('timeout')` (marker `java`); `.mpp` real com Java → 103 tarefas idênticas ao caminho `.xml` (marker `java`).
4. `scripts/dump_mpp.py` vira CLI fino: chama `parse_cronograma` e **projeta para o formato legado de 9 campos** (compatibilidade com `rebuild_baia_from_0607_mpp.py` — spec §14); conferir com `diff` da saída antiga vs nova no `CRONOGRAMA 06.07.mpp`.
5. Commit `feat(cronograma): despacho xml/mpp com subprocess isolado e CLI compatível (M03)`.

## Task 4: upload — blueprint, validações, dedup, eventos (TDD)

**Files:** Create `views/cronograma_importacao.py`, `tests/test_upload_cronograma.py`; Modify `main.py` (registrar blueprint)

Rota `POST /obras/<int:obra_id>/cronograma/importacoes`, decorator `cronograma_import_required`, na ordem:
1. Obra do tenant (`get_tenant_admin_id` + `Obra.query.filter_by(id=..., admin_id=...)` → 404 se não).
2. Arquivo presente; extensão ∈ {`.xml`, `.mpp`}; tamanho ≤ 20 MB (constante); magic bytes: `.mpp` → OLE2 `D0 CF 11 E0 A1 B1 1A E1`; `.xml` → parse + root MSPDI (reusar a validação do parser). Falha → 422 `{erro}`.
3. `secure_filename` + SHA-256 do conteúdo.
4. Dedup: `CronogramaImportacao` da obra com mesmo sha e `status NOT IN ('falhou','cancelado')` → 409 `{importacao_existente_id}` (o índice parcial `uq_cron_imp_obra_sha` do M02 é o backstop; a query é a mensagem amigável).
5. Persistir em `{UPLOADS_PATH}/cronogramas/{admin_id}/{obra_id}/{sha256}{ext}` (default `UPLOADS_PATH=uploads`; criar dirs). Criar `CronogramaImportacao(status='recebido', origem='upload_mspdi'|'upload_mpp', parser_nome='mspdi_stdlib'|'mpxj', arquivo_*)` + evento `upload` (detalhes: tamanho, sha).
6. Parse síncrono: `parse_cronograma(path)` → `json_bruto`, `status='parseado'`, evento `parse_ok` (detalhes: `tempo_parse_ms`, `n_tarefas`); `MppParserError` → `status='falhou'`, `erro=mensagem`, evento `parse_erro` (detalhes: motivo) → 422. Commit único ao final; 201 `{importacao_id, status}`.

Testes de integração (client autenticado admin, padrão `test_caracterizacao_apontamento_cronograma.py`): upload do `CRONOGRAMA 16.07.xml` real → 201, registro com `json_bruto` de 103 tarefas, 2 eventos; mesmo arquivo de novo → 409; `.txt` → 422; XML não-MSPDI → 422; obra de outro admin → 404; funcionário → 403 (decorator); `.mpp` com `java_disponivel` monkeypatchado False → 422 com instrução no erro. Vermelho→verde→commit `feat(cronograma): upload de cronograma na obra com hash, dedup e eventos (M03)`.

## Task 5: regressão e fecho

1. Conjunto rápido: os arquivos de teste novos + migrations M02 + caracterização + apontamento + rota + decorator + importação → tudo verde.
2. Gate completo em background (`pytest tests/ -m "not browser"`); esperado ≥446 passed + novos, 0 falhas (testes `java` podem skipar onde não houver JVM).
3. Fechar checklist §22 da spec do M03 com ressalvas: itens de Docker/Java ficam explicitamente **transferidos ao M10** (adendo §4.3); `json_cli` removido (adendo §4.2). Marcar as Tasks 2-4 do adendo como cumpridas por este plano. Commit.

## Critérios de aceite

1. Upload do `.xml` real → `CronogramaImportacao` com `json_bruto` de 103 tarefas com uid/wbs/predecessoras tipadas (spec §18.1, via MSPDI).
2. Mesmo arquivo → 409 por hash (spec §18.2).
3. Sem Java, o fluxo `.xml` completa o pipeline inteiro; `.mpp` degrada com instrução (substitui spec §18.3).
4. Worker nunca trava: timeout de subprocess comprovado por teste (spec §18.4).
5. Tabela de tipos de vínculo VERIFICADA contra MPXJ, não assumida.
6. `scripts/rebuild_baia_from_0607_mpp.py` continua funcionando (CLI compatível).

## Riscos

| Risco | Mitigação |
|---|---|
| Mapeamento Type errado corrompe grafo de dependências | Task 2 verifica contra MPXJ nos 3 arquivos; teste unitário fixa a tabela |
| `LinkLag` com `LagFormat` exótico (percentual, minutos decorridos) | Task 2 compara `lag_dias` com `getLag` do MPXJ; divergência → tratar o formato antes de seguir |
| JVM do subprocess estourar memória com 2 workers gunicorn | Parse síncrono com timeout; medição em `tempo_parse_ms`; lock de 1 parse concorrente só se o M10 medir problema |
| `db.create_all()` criar diretório/estado inesperado nos testes de upload | Storage em tmp_path nos testes (monkeypatch `UPLOADS_PATH`) |
