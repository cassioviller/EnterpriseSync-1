# Módulo 03 — Upload e Parser de Cronograma — Fecho

> Fecha o M03 conforme o plano `2026-07-20-modulo-03-implementacao-upload-parser.md`,
> reconciliando a spec `2026-07-17-modulo-03-upload-parser-mpp.md` com o adendo
> `2026-07-20-modulo-03-adendo-parser-mspdi-sem-jvm.md`. Em conflito, o adendo vence.

## Entregue (commits nesta branch `feat/cronograma-mpp-m03-upload-parser`)

| Task | Commit | Conteúdo |
|---|---|---|
| 1 | `452c318` | `services/mspdi_parser.py` — parser MSPDI stdlib, contrato completo |
| 2 | `6361f54` | `scripts/verificar_paridade_mspdi.py` — paridade MSPDI×MPXJ, tabela de tipos verificada |
| 3 | `4fc768c` | `services/mpp_parser.py` + worker — despacho xml/mpp, subprocess isolado, CLI compatível |
| 4 | `925b170` | `views/cronograma_importacao.py` — upload com hash, dedup e eventos |
| Hardening | `bf66c92` | Correções da auditoria adversarial de segurança |

## Checklist §22 da spec — estado

- [x] **Worker extrai uid/wbs/tipo/lag/marco/notas** — completo.
      **Ressalva:** `recursos` e `custom` ficam de fora deliberadamente — o
      arquivo real não os tem, o M04 não os consome, e "dados ausentes ficam
      ausentes" (spec §12.3; adendo). Entram quando um consumidor exigir.
- [x] **Subprocess + timeout testados** — `test_mpp_parser.py`
      (`test_timeout_do_worker_e_tipado`, marker `java`): `.mpp` real com
      `timeout_s=0.01` → `MppParserError('timeout')`, worker morto sem órfão.
- [x] **CLI mantém compatibilidade** — diff da saída antiga vs nova de
      `scripts/dump_mpp.py` sobre `CRONOGRAMA 06.07.mpp`: **byte-idêntico**
      (101 tarefas). `rebuild_baia_from_0607_mpp.py` segue funcionando.
- [x] **Upload validado com hash e dedup** — Task 4. SHA-256 dos bytes;
      dedup por (obra, sha) em importação viva → 409; índice parcial
      `uq_cron_imp_obra_sha` (M02) como backstop de corrida (→ 409, não 500).
- [ ] **Java em Docker/dev declarado e verificado** — **TRANSFERIDO AO M10**
      (adendo §4.3). O M03 roda 100% sem Java pelo caminho `.xml`; declarar a
      infra Java (Dockerfile/nixpkgs) é decisão do M10. Java existe neste
      ambiente dev, então os testes `.mpp` rodam aqui e skipam onde não houver JVM.
- [x] **Contingência sem Java funcional** — o `.xml` (MSPDI) completa o
      pipeline inteiro sem JVM; o `.mpp` sem Java degrada com instrução
      acionável ("Salvar como → XML"). **A contingência `json_cli` da spec foi
      removida** (adendo §4.2) — substituída pelo caminho MSPDI-primário.
- [~] **Suíte verde** — verificação **escopada** ao M03 (verde): parser
      MSPDI (5), upload (9, inclui os 2 testes de segurança da auditoria),
      despacho/subprocess `.mpp`↔`.xml` com marker `java` (5) e decorator (4)
      — todos passando. **Ressalva:** a suíte COMPLETA (`pytest tests/ -m
      "not browser"`) não conclui neste ambiente porque testes de integração
      não-relacionados ao M03 travam esperando servidor vivo (mesmo motivo de
      `run_tests.sh` "travar sem servidor", já anotado no plano). O bloqueio é
      pré-existente e independente das mudanças do M03.

## Tasks do adendo cumpridas por este plano

- **Adendo Task 2** (parser base MSPDI + mapa UID→ID + tabela de tipos) →
  cumprida pelas Tasks 1–2 (`452c318`, `6361f54`).
- **Adendo Task 3** (despacho, subprocess, mensagem sem Java) → cumprida pela
  Task 3 (`4fc768c`).
- **Adendo Task 4** (upload) → cumprida pela Task 4 (`925b170`).

## Auditoria de segurança (commit `bf66c92`)

Auditoria adversarial da trilha de upload+parser. Corrigidos:

- **A1 (Alta)** — billion laughs / expansão de entidades XML: troca para
  `defusedxml` na view e no `mspdi_parser`. Era DoS de disponibilidade
  multi-tenant a partir de privilégio baixo (admin do tenant).
- **M1 (Média)** — MSPDI bem-formado com conteúdo inválido gerava HTTP 500 +
  arquivo órfão: `parse_cronograma` embrulha exceção inesperada em
  `MppParserError('erro_parse')` → 422 com registro `falhou`.
- **M2 (Média)** — corrida de dedup gerava 500: `IntegrityError` do índice
  único → rollback + 409 amigável.
- **B1 (Baixa)** — stderr da JVM vazava ao cliente: mensagem genérica ao
  cliente, detalhe completo em `imp.erro`/log server-side.

**Aceito como OK pela auditoria** (7 eixos): path traversal, XXE externo,
injeção de subprocess, timeout/JVM órfã, isolamento de tenant, correção do
parser, fd-juggling do worker.

**Diferido ao M10** (registrado, não corrigido no M03):
- **B4** — 1 JVM por request `.mpp` sem semáforo de concorrência. O parse é
  síncrono com timeout; um limite de concorrência entra no M10 se a medição
  de memória lá justificar (risco já listado no plano do M03).

## Verificação

- Contrato idêntico entre caminhos `.mpp` (MPXJ) e `.xml` (MSPDI) provado no
  par real 16.07: projeto + 103 tarefas byte a byte
  (`test_mpp_e_xml_produzem_o_mesmo_contrato`).
- Verificação escopada M03: parser (5) + upload (9) + despacho `java` (5) +
  decorator (4) verdes; diff CLI antigo×novo byte-idêntico (101 tarefas).
  Suíte completa não roda neste ambiente (integração pré-existente que exige
  servidor — não é regressão do M03).
