# Módulo 3 — Upload, Armazenamento e Parser `.mpp`

> Parte do plano mestre `2026-07-17-cronograma-mpp-rdo-master-plan.md`. Parser 100% local (MPXJ/JPype); nenhuma chamada externa.

## 1. Objetivo

Receber o `.mpp` dentro da obra, validar, armazenar com hash, e convertê-lo em JSON bruto por um serviço determinístico reutilizável — funcionando em dev, teste e produção, com contingência quando a JVM não estiver disponível.

## 2. Estado atual encontrado no código

- `scripts/dump_mpp.py` (110 linhas): parser canônico. `_achar_java_home()` (`:23-31`) procura JDK completo (`$JAVA_HOME` ou glob `/nix/store/*temurin|adoptopenjdk|openjdk*`); docstring (`:8-12`) documenta que `jdk4py` falha por falta do charset MacRoman. Usa `org.mpxj.reader.UniversalProjectReader` (`:65`), sobe JVM com `jpype.startJVM()` (`:61-64`). Extrai por tarefa (`:82-92`): `id` (getID — **não** getUniqueID), `outline`, `nome`, `inicio`, `fim`, `dias`, `pct_fisico` (getPercentageComplete), `predecessoras` (só IDs, sem tipo/lag, `:74-80`), `resumo` (getSummary). **Não extrai**: UID, WBS, marco, tipo de vínculo, lag, recursos, notas, campos personalizados, calendário.
- `scripts/diff_mpp_vs_json.py`: variante com fallback `jdk4py` (`:25-32`) — inconsistente com o dump_mpp.
- MPXJ/JPype/JDK **ausentes** de `pyproject.toml`, `uv.lock`, `replit.nix`, `.replit`, `Dockerfile`, `Dockerfile.production` — instalação manual `pip install mpxj jpype1` (docstring `:8`). Produção (python:3.11-slim) não tem Java.
- Upload atual (`importacao_views.py:1023-1056`): só JSON, em memória, sem `secure_filename`, sem validação de extensão/tamanho/schema, sem hash, sem persistência do arquivo. Precedente de hash no projeto: `NotaFiscal.xml_hash` (`models.py:1965`). Precedente de storage: env `UPLOADS_PATH` (`replit.md`).

## 3. Problemas atuais

1. Parser é ferramenta manual dev-only; produção não converte `.mpp`.
2. Campos indispensáveis à reconciliação (UID, WBS, tipo de vínculo, lag, marco) não são extraídos.
3. JVM no processo web = risco de crash/memória no worker gunicorn.
4. Upload sem validação nem idempotência.

## 4. Escopo

### 4.1 Serviço de parser

- Novo `services/mpp_parser.py`:
  - `parse_mpp(caminho_arquivo: str, timeout_s: int = 120) -> dict` — executa o parsing em **subprocess** (`subprocess.run([sys.executable, '-m', 'services.mpp_parser_worker', caminho], timeout=...)`) para isolar a JVM do worker web (crash/OOM/timeout não derrubam o gunicorn). Retorna o JSON bruto (contrato §10) ou lança `MppParserError(motivo)` tipado: `java_indisponivel | arquivo_corrompido | timeout | erro_mpxj`.
  - `java_disponivel() -> bool` — reusa/extrai `_achar_java_home()` de `scripts/dump_mpp.py`.
- Novo `services/mpp_parser_worker.py`: o código hoje em `scripts/dump_mpp.py::dump`, ampliado para extrair (quando disponível no arquivo — **nunca inventar**; ausente = chave omitida/null):
  `id` (getID), `uid` (getUniqueID), `wbs` (getWBS), `outline` (getOutlineLevel), `nome`, `inicio`, `fim`, `dias` (getDuration), `pct_project` (getPercentageComplete), `predecessoras: [{id, uid, tipo (FS/SS/FF/SF via getType), lag_dias (getLag)}]`, `resumo` (getSummary), `marco` (getMilestone), `calendario` (nome, se houver), `recursos: [nome]` (getResourceAssignments), `notas` (getNotes), `custom: {TextN/NumberN não vazios}`. Quantidade/unidade: procurados em campos custom configuráveis (`Number1`/`Text1` por convenção documentada) — sem heurística mágica; se não há, ficam null e a tarefa entra sem quantitativo.
- `scripts/dump_mpp.py` vira **CLI fino** sobre `services/mpp_parser.py` (mesma interface de linha de comando atual, para não quebrar o hábito documentado em `RDO.md`).

### 4.2 Upload e armazenamento

- Nova rota `POST /obras/<obra_id>/cronograma/importacoes` (blueprint novo `cronograma_importacao_bp`, prefixo `/obras/<obra_id>/cronograma` — rotas completas no M8):
  1. Autorização (decorator do M1) + obra do tenant (`get_tenant_admin_id`).
  2. Validações: extensão `.mpp` (e `.json` para contingência), MIME sniff dos magic bytes (`.mpp` é OLE2: `D0 CF 11 E0`), tamanho ≤ 20 MB (config).
  3. `secure_filename` + SHA-256 do conteúdo.
  4. Dedup: se existe `cronograma_importacao` da mesma obra com mesmo `arquivo_sha256` e status ≠ `falhou|cancelado` → responder 409 com link para a importação existente (critério global 2). Reimportar após falha é permitido.
  5. Persistir arquivo em `{UPLOADS_PATH}/cronogramas/{admin_id}/{obra_id}/{sha256}.mpp` + criar `CronogramaImportacao(status='recebido')` + evento `upload`.
  6. Disparar processamento **síncrono na request** com timeout (parse típico <10s para 101 tarefas; gunicorn timeout=120 comporta) → status `parseado` (json_bruto) → segue ao M4. Se `MppParserError`: status `falhou`, erro legível, evento `parse_erro`. (Job assíncrono é evolução futura; síncrono simplifica e o timeout do subprocess protege o worker.)
- Contingência sem Java (`java_indisponivel`): o mesmo endpoint aceita upload do **JSON bruto** gerado pelo CLI em dev (`origem='json_cli'`), validado pelo mesmo schema; a UI (M8) exibe instrução. Nada mais difere no pipeline.

### 4.3 Infra

- `pyproject.toml`: adicionar `mpxj` e `jpype1` (pinados).
- `Dockerfile` (EasyPanel): adicionar `default-jre-headless` (Debian slim) — validar no build com `java -version`; documentar acréscimo de imagem (~180 MB). `Dockerfile.production` idem.
- `.replit`/`replit.nix`: adicionar JDK (Temurin) para dev.
- Limpeza de temporários: parser trabalha no arquivo persistido (sem tmp); worker subprocess não deixa lixo.

## 5. Fora de escopo

Normalização/classificação (M4), reconciliação/aplicação (M5), UI (M8), fila assíncrona, parsing de `.xml`/`.mpx` do Project (MPXJ suporta; ativar depois se pedirem).

## 6. Arquivos atuais envolvidos

`scripts/dump_mpp.py`, `scripts/diff_mpp_vs_json.py` (passa a usar o serviço, removendo o fallback jdk4py inconsistente), `importacao_views.py` (referência, não alterado), `pyproject.toml`, `Dockerfile`, `Dockerfile.production`, `.replit`, `replit.nix`.

## 7. Arquivos novos ou alterados previstos

Novos: `services/mpp_parser.py`, `services/mpp_parser_worker.py`, `views/cronograma_importacao.py` (blueprint; rotas restantes no M8), `tests/fixtures/cronograma_teste_pequeno.mpp` (fixture sintética pequena versionada; além dela, os `.mpp` reais já versionados na raiz servem de fixture de integração). Alterados: os do §6.

## 8. Alterações de banco

Nenhuma (usa tabelas do M2).

## 9. Serviços e responsabilidades

| Serviço | Responsabilidade |
|---|---|
| `services/mpp_parser.py` | Orquestrar subprocess, timeout, erros tipados, disponibilidade de Java |
| `services/mpp_parser_worker.py` | MPXJ→JSON bruto determinístico, sem inventar dados |
| `views/cronograma_importacao.py` | Upload, validação, hash, dedup, criação da importação, eventos |

## 10. Rotas e contratos de API

`POST /obras/<obra_id>/cronograma/importacoes` → 201 `{importacao_id, status}` | 409 `{importacao_existente_id}` | 422 `{erro}`.

JSON bruto (contrato versionado `parser_versao`):
```json
{"projeto": {"nome": "...", "data_status": "2026-07-06"},
 "tarefas": [{"id": 15, "uid": 132, "wbs": "1.3.2", "outline": 3,
   "nome": "FERRAGENS PARA FUNDACAO", "inicio": "2026-07-01", "fim": "2026-07-08",
   "dias": 6.0, "pct_project": 100.0, "resumo": false, "marco": false,
   "predecessoras": [{"id": 14, "uid": 130, "tipo": "FS", "lag_dias": 0}],
   "recursos": ["Equipe A"], "notas": null, "custom": {}}]}
```

## 11. Fluxo de frontend

Somente o botão de upload provisório (tela completa no M8). Estados exibidos: recebido/parseado/falhou + mensagem de erro amigável por tipo (`arquivo_corrompido`, `java_indisponivel` com instrução da contingência).

## 12. Regras de negócio

- Hash idêntico na mesma obra = mesma importação (sem reprocessar).
- Arquivo inválido/corrompido nunca cria versão nem toca cronograma (falha antes de qualquer escrita em tarefa).
- Dados ausentes no `.mpp` ficam ausentes no JSON (proibido inferir).

## 13. Estratégia de migração

Sem dados. Infra: deploy do Docker com Java antes de ligar a flag (M10 fase 0/1); healthcheck novo loga `java_disponivel()` no boot.

## 14. Compatibilidade

- `scripts/dump_mpp.py` mantém CLI e formato de saída **superset** (chaves novas adicionadas; `rebuild_baia_from_0607_mpp.py` continua funcionando pois lê chaves existentes `id/outline/nome/inicio/fim/dias/predecessoras/resumo`).
- Rota `/importacao/fisico-financeiro` intocada.

## 15. Segurança

Extensão+magic bytes+tamanho; `secure_filename`; arquivo fora de static; path por tenant; subprocess sem shell; JSON bruto tratado como dado não confiável (validação de tipos no M4); sem execução de macros/conteúdo do arquivo (MPXJ só lê estruturas).

## 16. Observabilidade

Logs: tamanho, hash, duração do parse, nº de tarefas, versão mpxj. Métricas simples persistidas em `cronograma_importacao_evento.detalhes` (tempo_parse_ms, n_tarefas) — base para o M10.

## 17. Testes

- Unit worker (marcador novo `java`, skip se `not java_disponivel()`): fixture `.mpp` pequena → campos esperados; `CRONOGRAMA 06.07.mpp` → 101 tarefas, ids/datas batendo com `cronograma_fisico_financeiro_baias.json` (paridade com `scripts/diff_mpp_vs_json.py`); arquivo corrompido (bytes aleatórios com header OLE2) → `arquivo_corrompido`; timeout com limite artificial 0.01s → `timeout`.
- Integração rota: upload ok → 201+registro+evento; duplicado → 409; extensão errada/tamanho → 422; tenant errado → 404; Java ausente (monkeypatch `java_disponivel`) → aceita JSON de contingência.
- CI/`run_tests.sh --gate` continua passando sem Java (testes `java` skipam); job dedicado com Java roda a família completa (M10).

## 18. Critérios de aceite

1. Upload de `.mpp` real numa obra qualquer gera `CronogramaImportacao` com json_bruto de 101 tarefas com uid/wbs/predecessoras tipadas.
2. Mesmo arquivo de novo → 409 por hash.
3. Sem Java, o fluxo por JSON de contingência completa o mesmo pipeline.
4. Worker web nunca trava: subprocess com timeout comprovado por teste.

## 19. Riscos

- Peso da JVM na imagem/memória (2 workers gunicorn + subprocess JVM ~256 MB pico) — medir na fase 1; se necessário, limitar 1 parse concorrente por lock simples.
- Versões mpxj mudam API — pinar e gravar `parser_versao`.
- `.mpp` de versões exóticas do Project — `UniversalProjectReader` cobre; erro tipado cai em contingência.

## 20. Dependências

M2 (tabelas). M1 (decorator).

## 21. Ordem detalhada de implementação

1. Extrair worker de `dump_mpp.py` + ampliar campos; testes unit com fixtures (vermelho→verde). 2. `services/mpp_parser.py` (subprocess/timeout/erros) + testes. 3. Reescrever `scripts/dump_mpp.py` como CLI fino; conferir paridade de saída. 4. Infra (pyproject, Dockerfiles, replit) + smoke `java -version`. 5. Blueprint upload + validações + hash + dedup + eventos; testes de integração. 6. Contingência JSON. 7. Suíte completa; commits por passo.

## 22. Checklist de conclusão

- [ ] Worker extrai uid/wbs/tipo/lag/marco/recursos/notas/custom
- [ ] Subprocess+timeout testados
- [ ] CLI mantém compatibilidade
- [ ] Upload validado com hash e dedup
- [ ] Java em Docker/dev declarado e verificado
- [ ] Contingência sem Java funcional
- [ ] Suíte `--gate` verde (testes `java` skipáveis)
