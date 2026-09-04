# ESTADO — Espinha Financeira da Obra (Resultado por Atividade)

> Ponto de entrada único para retomar. Atualizado: **2026-06-15 (fim de sessão)**.
> Branch: `design/espinha-financeira-obra` · **PR #6** aberto: https://github.com/cassioviller/EnterpriseSync-1/pull/6
> Foco do usuário (Cássio): **qualidade**. Trabalho feito fase a fase, com **teste entre cada etapa**.

> 🟢 **04/09 — O PORTE FOI FEITO. Este documento está APOSENTADO como fonte de estado.**
>
> O que este arquivo descreve foi escrito em 15/06 sobre a branch
> `design/espinha-financeira-obra` (PR #6). Em 22/07 a história do repositório
> foi recomeçada e as duas linhagens ficaram **disjuntas**. Entre 03/09 e
> 04/09 o código foi **portado** para o `main` de hoje, task a task, pelo
> plano `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`.
>
> ### 🔴 O PR #6 NÃO É MESCLÁVEL. Não tente.
>
> Isto está escrito porque alguém vai tentar. 🔬 medido em 04/09:
> `git merge-base main origin/design/espinha-financeira-obra` devolve
> **vazio** — as duas árvores não têm um único commit em comum — e
> `git rev-list --count origin/fix/fase-0-estancar..main` devolve **722**
> (o número anda; meça no dia). Não há merge possível, só porte. O item 6
> da lista "PRÓXIMOS PASSOS" mais abaixo ("Merge do PR #6") **deixa de
> existir**: ele descreve uma operação que o git não pode executar.
>
> ### O que FOI portado, e em que commit
>
> | O quê | Commit |
> |---|---|
> | Ref durável (tag `espinha-pr6-origem`) + inventário conferido | `6981caac` |
> | `caixa_obra_service` e `aprendizado_produtividade`, com filtro de estado | `42bb5000` |
> | `cronograma_template_item.peso_medicao` (migration 319) | `917637bf` |
> | `propostas_comerciais.origem` (migration 320) | `0aa54db1` |
> | Read-model `resultado_atividade_service` + `gestao_custo_filho.tarefa_cronograma_id` (migration 321) | `4ec10aeb` |
> | Importador de obra por planilha, pelo escritor único de contrato | `dfd15ea4` |
> | Telas (resultado, caixa, portfólio, importação) + blueprint | `a1fddb6c` |
> | Fatia 2 §D: verba/lucro/pai na subempreitada (migration 322) | `eb24281c` |
> | Scripts da Baia REV10 + E2E ponta a ponta | `b5265988` |
>
> **O porte não foi cópia.** Três correções obrigatórias, e a primeira é a
> que importa: o read-model de 15/06 **não filtrava estado de RDO** — somava
> `RDOCustoDiario` e `RDOMaoObra` de todo RDO que encontrasse, porque
> `RDO.estado` só nasceu na Fase 5. Portado como estava, faria **rascunho
> contar como custo real**, movendo alarme, CPI e EAC. Cinco leitores ganharam
> `RDO.estado != 'rascunho'`, com teste próprio
> (`tests/test_espinha_rascunho_nao_conta.py`). As outras duas: o importador
> passou a gravar `valor_contrato` pelo escritor único
> (`services/contrato_obra`, Fase 6), senão a obra nasceria sem
> `ObraContratoVersao` nº1; e o funil comercial passou a filtrar
> `origem='importacao_obra'` da listagem e dos KPIs.
>
> ### O que NÃO foi portado (e por quê)
>
> 1. **Importador genérico.** Os três scripts da Baia são Baia-específicos
>    por desenho (`gerar_importacao_baia_rev10.SERVICOS`). "Qualquer obra pela
>    planilha" precisa de um parser novo: é **trabalho novo**, não porte.
> 2. **Datas/durações por atividade.** Dependem de exportar o `.mpp` para XML.
>    Por isso o **SPI continua `None`** — o EVM entrega CPI e EAC, não SPI.
> 3. **Material direto na UI** e o refino do EVM F3-4. Refinos de 15/06, sem dono.
> 4. **A ratificação comercial do telhado viga I.** A opção B (markup uniforme)
>    foi decidida em 01/09 e o schema que ela precisa está no `main`
>    (migration 322), mas o `RATIFICAR` com o dono segue pendente — é escolha
>    comercial e não bloqueava o porte.
>
> ### Como ler o resto deste arquivo
>
> Tudo abaixo desta linha foi escrito em 15/06 e descreve **a branch**. Onde
> ele fala de arquivos e testes, eles agora existem no `main` — mas com as
> correções acima, não como estão descritos aqui. Onde ele fala de
> **próximos passos**, são passos de outra árvore. A fonte de estado é o
> `ESTADO-ATUAL.md`, o código e o git.
>
> Índice de estado de todos os planos e specs: `docs/planos-em-aberto-2026-08-25.md`.

## TL;DR — onde estamos
As **5 fatias da espinha financeira estão implementadas, testadas e no PR** (~40 testes verdes).
A obra dá, por atividade do cronograma: **Valor agregado − Custo incorrido = Resultado**, com alarme,
previsão (EVM) e lente de caixa; mais roll-up de portfólio e learning loop. Há um **importador que cria
a obra inteira a partir de uma planilha (pela tela ou por comando), sem configurar nada**. Falta: ligar
o SPI (datas do MPP), o telhado viga I (dado externo) e tornar o importador genérico (hoje é Baia REV10).

## LER PRIMEIRO (a verdade do design vive aqui)
- **`docs/superpowers/plans/2026-06-15-espinha-financeira-plano-mestre.md`** — contrato cross-cutting (DC1–DC11).
- **`docs/adr/0004-...`** (granularidade serviço→N atividades; 1:1 é fallback; congela no apontamento).
- **`docs/adr/0005-...`** (importar como obra: Proposta de importação fora do funil; **orçado = baseline
  congelado da Proposta**).
- **`CONTEXT.md`** — glossário (Atividade, Serviço, Peso da medição, Orçado baseline, Proposta de importação…).
- Planos por fatia: `docs/superpowers/plans/2026-06-15-fatia-{1..5}-*.md` (cada um com "Status de execução").
- Spec original: `docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md` (D1–D6).

## Decisões travadas (D1–D6 do spec + grill)
- **D1** Custo MO/atividade = computado: rateio de `RDOCustoDiario.custo_total_dia` por horas apontadas.
- **D3 (DC3)** **MO nunca conta 2×**: read-model lê MO do `RDOCustoDiario`; do ledger `GestaoCustoFilho`
  lê SÓ não-MO (exclui SALARIO/MAO_OBRA_DIRETA/VALE_*). Teste de regressão guarda isso.
- **D4** Competência (Resultado) ≠ Caixa (Realizado/Previsto, ADR 0003). Lentes separadas, nunca somadas.
- **D5** Alarme primário em R$; horas só onde a MO é precificada em hora (1.1 LSF).
- **D6/D8** Peso Serviço→Atividade = `ItemMedicaoCronogramaTarefa.peso` (fonte única p/ venda e orçado).
- **Grill (corrigido pelo usuário):** **orçado = baseline congelado da Proposta** (`PropostaItem.composicao_snapshot`),
  NÃO do Orçamento operacional — para o alarme não poder ser mascarado por revisões. (ADR 0005)
- **Granularidade:** 1 Serviço → N Atividades pelo peso do cronograma refinado; "Serviço=Atividade" é só
  fallback sem template; congela ao iniciar o apontamento. (ADR 0004)

## CÓDIGO ENTREGUE (mapa para retomar)
**Read-model (coração):** `services/resultado_atividade_service.py`
- F1: `valor_agregado_atividade`, `custo_mo_atividade`, `custo_mo_orcado_atividade`, `alarme_mo`,
  `indice_horas`, `resultado_obra`, `_folhas_da_obra`, helpers `_soma_peso_item`/`_horas_func_no_rdo`.
- F2: `custo_orcado_unitario(tipos)`, `custo_nao_mo_atividade` (direto+rateio, DC3),
  `custo_incorrido_atividade`, `alarme_custo`, `custo_orcado_atividade_por_tipos`.
- F3: `venda_total_atividade`, `evm_atividade`, `evm_obra` (CPI/SPI/EAC/resultado projetado).
- F5: `resultado_portfolio`.

**Importador auto-wiring:** `services/importar_obra_completa.py` (`importar_obra_completa(orcamento_id, admin_id)`)
— cria Proposta(origem='importacao_obra')→Obra→IMC 1:1→Cronograma. Usa template do serviço
(`CronogramaTemplateItem.peso_medicao`) p/ N atividades; senão sintetiza 1:1. Idempotente.

**Caixa:** `services/caixa_obra_service.py` (`fluxo_caixa_obra`) — reúso do `FinanceiroService`.
**Aprendizado:** `services/aprendizado_produtividade.py` (`produtividade_observada`, `atualizar_catalogo_produtividade`).
**Views:** `resultado_views.py` (blueprint `resultado`) — rotas:
`/obras/<id>/resultado`, `/obras/<id>/caixa`, `/resultado/portfolio`, `/resultado/importar-obra` (upload),
`/resultado/aprender-produtividade`. Registrado em `main.py`.
**Templates:** `templates/resultado/{por_atividade,caixa_obra,portfolio,importar_obra}.html`; link no
`templates/obras/detalhes_obra_profissional.html` (abas Resultado/Caixa) e botão em `templates/orcamentos/editar.html`.

**Import de produção (Baia):**
- `scripts/criar_orcamento_baia_rev10.py` → `criar_orcamento_baia(admin_id, xlsx_path)` (catálogo+orçamento do xlsx).
- `scripts/seed_templates_baia_rev10.py` → `seed_templates_baia(admin_id, orcamento_id)` (28 atividades, peso do doc).
- `scripts/importar_baia_easypanel.py` → `importar_baia_completa(admin_id, xlsx_path)` (cadeia inteira, idempotente).
- Arquivo: **`obra_kabod/IMPORTACAO_Baia_REV10_completa.xlsx`** (agora versionado).

**Migrations (rodam no deploy via `docker-entrypoint.sh`):** 193 `cronograma_template_item.peso_medicao` ·
194 `propostas_comerciais.origem` · 195 FKs `tarefa_cronograma_id` em gestao_custo_filho/movimentacao_estoque/
custo_veiculo + verba/lucro/pai em rdo_subempreitada_apontamento.

**Bug consertado:** `rdo_editar_sistema.py` — edição preserva `tarefa_cronograma_id` (emite/parseia `cron_tarefa_*`).

## TESTES (todos verdes)
`tests/test_rdo_edicao_preserva_tarefa.py` · `test_resultado_atividade_service.py` (read-model+EVM+rota) ·
`test_resultado_fatia2_custo_nao_mo.py` (DC3) · `test_importar_obra_completa.py` (auto-wiring+template+UI) ·
`test_caixa_obra.py` · `test_fatia5_inteligencia.py` · **`test_import_baia_e2e.py`** (importa o xlsx real
ponta a ponta + upload pela tela). Rodar: `python -m pytest tests/test_<x>.py -x -p no:warnings`.

## COMO RODAR EM PRODUÇÃO (EasyPanel) — já testado
1. Merge do PR + deploy. O entrypoint roda `db.create_all` + **migrations** (idempotentes); o xlsx vai na imagem.
2. Logar **no perfil (tenant) desejado**, que precisa estar em `versao_sistema='v2'`.
3. **Portfólio → "Importar obra (planilha)"** (`/resultado/importar-obra`) → subir o xlsx → confirma → cai na obra.
   - Alternativa por terminal: `python -m scripts.importar_baia_easypanel <admin_id>`.
- Estado atual neste banco de dev: obra **655** (admin 1) já materializada com **28 atividades**.

## PRÓXIMOS PASSOS (pendentes, em ordem de valor)
1. **Datas/durações por atividade** — exportar `Projeto1.mpp` → XML, gravar `data_inicio/duracao` nas
   TarefaCronograma. Liga o **SPI** (hoje None) e a Linha de Balanço (ritmo baias/dia).
2. **Telhado viga I** (Fatia 2 §D) — pegar com o usuário **verba + lucro % + opção A/B/C** (manter venda
   total travada). Mecanismo de custo (subempreitada→GestaoCustoFilho) já existe.
3. **Importador genérico** — hoje o importar_baia usa `gerar_importacao_baia_rev10.SERVICOS` (Baia-específico).
   Para "qualquer obra pela planilha", o xlsx precisa definir serviços/quantidades (parser novo).
4. **Material direto na UI** (Fatia 2) — botão espelhando o de equipe (custo já flui por rateio; é precisão).
5. **EVM F3-4 alavanca** ("quanto falta p/ fechar a meta") — refino.
6. **Merge do PR #6.**

## Notas/armadilhas conhecidas
- Telas da espinha são **gated por v2** (`is_v2_active`). Sem v2, redireciona.
- CSRF: os forms POST dependem do JS global do `base_completo.html` (injeta `csrf_token`). Em teste, usar
  `WTF_CSRF_ENABLED=False`. Testes HTTP precisam `import main` p/ registrar blueprints.
- Re-import da Baia no MESMO tenant é idempotente (não duplica); a obra só re-materializa multi-atividade
  se ainda **não tiver RDO apontado** (granularidade congela — ADR 0004).
