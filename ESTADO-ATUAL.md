# ESTADO ATUAL — SIGE / Veks

> Snapshot de 2026-07-21. Este é o documento a ler PRIMEIRO ao retomar o
> trabalho. Os demais (`DEVOLUTIVA.md`, `DOSSIE-REPO.md`, `FECHO-FASE-0.5.md`)
> são o detalhe; este é o mapa.

## Onde estamos

Branch: `fix/fase-0-estancar` · **Nada foi pushado para o GitHub.**

```
36f08e2  fix   correções do code review (9 achados)
549bdf0  chore limpeza de rotas mortas e documentos perigosos
7fa9975  fix   furos de tenant remanescentes
72ee374  fix   Pacote 3 parcial + fecho da Fase 0.5
1f42810  build Pacote 2 — build reproduzível e CI
4a50761  fix   Pacote 1 — backup, segredos, observabilidade
7494f94  docs  dossiê do repositório + anexos
f090b09  fix   Fase 0 — 4 rotas anônimas restantes
fa215fa  fix   Fase 0 — obra duplicada e furos de autorização
8fe6ac9  docs  devolutiva
… + 7 commits do M10 (cronograma .mpp)
```

`main` local e `origin/main` estão **idênticos** em `8fe6ac9` — o merge do M10
subiu. (Conferido em 21/07; a versão anterior deste documento dizia que `main`
estava 67 commits à frente, o que já não era verdade.) O que continua não
pushado são os **10 commits desta branch**.

## 🔴 Três coisas travadas do lado humano

Nenhuma destas eu consigo fazer. Todas bloqueiam o resto.

| # | O quê | Por que trava |
|---|---|---|
| 1 | **Rotacionar `SESSION_SECRET` e a senha do Postgres** no painel EasyPanel | Os valores estão no **histórico do git para sempre** — remover o arquivo não resolve. Com a chave de sessão forja-se cookie de qualquer usuário de qualquer tenant |
| 2 | **`gh auth setup-git`** (ou push manual) | Sem isso nada sobe, o CI nunca roda, e **não existe run verde no Actions** para provar o gate |
| 3 | **Criar o volume `/var/backups/sige`** no painel | O Dockerfile cria e faz chown do diretório, mas sem volume montado os dumps somem no restart |

Além disso, pendem do seu lado: conferir se os valores do painel divergem
dos commitados, verificar se a Hostinger faz snapshot do volume, definir
`SIGE_ENABLE_DEMO_SEED=false`, confirmar a grafia do domínio
(`cassioviller` vs `cassiovillar` — as duas aparecem no código) e decidir o
acesso ao banco de produção.

## O plano aprovado

Sequência confirmada por você, **inalterada**:

| Fase | Conteúdo | Estado |
|---|---|---|
| **0** | Estancar: obra duplicada, decorators no-op, rotas anônimas | ✅ concluída |
| **0.5** | Backup, segredos, observabilidade, build, CI, índices | ✅ Pacotes 1-2; 🟡 Pacote 3 parcial |
| **1** | Fundação de identidade e papéis (RBAC + escopo por obra) | ⬜ **próxima** |
| **2** | Máquina de estados da Obra + handoff do GP | ⬜ |
| **3** | Compras com governança (requisição → aprovação → PO) | ⬜ |
| **4** | Centro de custo obrigatório | ⬜ |
| **5** | RDO com ciclo de vida e assinatura | ⬜ |
| **6** | Orçamento versionado e aditivo | ⬜ |
| **7** | Planejamento avançado (CPM, baseline, EVM) | ⬜ |
| **8** | Financeiro avançado + exportação Domínio | ⬜ |
| **9a** | Assinatura de medição no portal | ⬜ |
| **9b** | Contratos, Drive, notificações | ⬜ |

### 🆕 Requisito novo, priorizado para DEPOIS da Fase 1

Levantado por você em 21/07 e **ainda não especificado em detalhe**:

> **"Cronograma igual ao Project, totalmente editável, sem precisar cadastrar
> insumos. RDO em porcentagem."**

Sua queixa literal: *"demora para levantar o quantitativo e fazer o
cronograma; sem cadastrar os insumos não faz o cronograma"*.

> ⚠️ **Diagnóstico revisado em 21/07.** A versão anterior deste documento
> dizia que "o cronograma nasce preso à proposta — sem catálogo cadastrado,
> não há cronograma". **Isso é falso para a criação manual de tarefa**, e um
> plano baseado nessa premissa reconstruiria código que já existe.

**Criar tarefa sem insumo JÁ FUNCIONA** — resolvido pela Task #116:

- `cronograma_views.py:269` (`criar_tarefa`): *"servico_id é opcional. (…) a
  tarefa é salva com `servico_id=None` (sem vínculo de serviço)"*. O único
  campo obrigatório é `nome_tarefa`.
- `templates/obras/cronograma.html:1658` (`salvarNovaTarefa()`) só valida o
  nome; `subatividade_mestre_id` e `servico_id` vão nulos se o usuário não
  escolher no dropdown. Existe `limparSelecaoCatalogo()` para desvincular.
- O Gantt já tem POST/PUT/DELETE de tarefa ligados
  (`templates/obras/cronograma.html:1691`, `:1864`, `:2036` →
  `cronograma_views.py:269`, `:450`, `:659`).
- `TarefaCronograma.servico_id` é nullable no schema (`models.py:4903`).
- O import `.mpp` cria tarefa sem serviço, subatividade ou insumo
  (`services/cronograma_versao_service.py:534`).

**O que continua verdadeiro e é a frente real de trabalho:**

1. **O modo de apontamento é deduzido, não escolhido.**
   `services/cronograma_apontamento_service.py`, `modo_da_tarefa()`: devolve
   `'quantidade'` quando a tarefa tem `quantidade_total > 0` **e**
   `unidade_medida`; só cai em `'percentual'` caso contrário. Você não
   escolhe.
2. **O caminho automático proposta→obra ainda exige a cadeia
   serviço → composição → insumo** — `materializar_cronograma`
   (`services/cronograma_proposta.py:452`). Vale para a obra que nasce de
   proposta aprovada, não para a criação manual.
3. **Pode ser só flag desligada.** Todo o módulo passa por `_check_v2()`
   (`cronograma_views.py:39`), que redireciona ao dashboard se o admin do
   tenant não tiver `versao_sistema == 'v2'`; e `cronograma_mpp_ativo`
   (`models.py:3620`) nasce desligada, escondendo a aba de importação.
   **Verificar as flags do tenant ANTES de planejar qualquer código.**

Plano detalhado em
`docs/superpowers/plans/2026-07-21-cronograma-editavel-rdo-percentual.md`.

## O que está em aberto da Fase 0.5

| Item | Situação |
|---|---|
| Triagem de `fix/bloco2-segredos` e `fix/bloco1-blindagem-acesso` | ❌ as duas branches continuam órfãs, 402 commits atrás |
| `gitleaks`/`trufflehog` | ❌ não disponíveis no ambiente; a varredura manual não cobriu blobs binários |
| Conflito `opencv-python` × `headless` | ❌ entra transitivamente por `deepface`/`retina-face`; resolver exige decidir sobre reconhecimento facial |
| `psycopg2-binary` → `psycopg2` compilado | ⏸️ recomendado (1h); migrar para psycopg 3 **não** foi recomendado agora |
| 28 rotas `EXPOE DADO` sem auth | ❌ exigem triagem caso a caso |
| Backup **agendado** (só existe o pré-migração) | ❌ recomendação: job do EasyPanel, não APScheduler |
| Skips de precondição de dado convertidos | ❌ ainda produzem verde falso em banco novo |
| `duplicar_rdo` emite webhook sem lançar custos (bug 6d) | ❌ |
| `scripts/medir_producao.py` | ❌ aguarda decisão de acesso ao banco |

## Números que valem lembrar

| | |
|---|---|
| Rotas totais / sem autenticação | 724 / **40** (eram 64) |
| Rotas de **escrita** sem auth | **1** — e é `/login` |
| Índice `rdo_apontamento_cronograma` | 881 ms → **0,034 ms** (era Seq Scan em 61.923 linhas) |
| Testes | 878, gate ~39 min |
| Violações de ruff herdadas | 543, das quais **186 F821** (nome indefinido) |
| Tabelas vazias | ~65 de 178 (**37%**) — módulos inteiros nunca usados |
| `models.py` / `migrations.py` | 7.610 / 14.300+ linhas |
| **Banco de produção** | 14 GB, dos quais **`rdo_foto` sozinha ocupa 14 GB** |

## Armadilhas para quem retomar

1. **O banco de desenvolvimento não tem dados reais.** 6.479 admins, todos de
   domínio de teste. Toda a volumetria do dossiê mede carga de suíte
   automatizada — nenhuma decisão de dimensionamento deve sair dela.
2. **`rdo_foto` guarda três cópias base64 de cada foto** e define o RPO real:
   backup completo de 14 GB não cabe em janela curta. As colunas de caminho
   em disco já existem na mesma tabela.
3. **`gestao_custo_pai` não tem coluna `obra_id`** — 1.118 linhas 100%
   órfãs. A Fase 4 precisa criar a coluna e decidir a regra de derivação
   antes de qualquer `NOT NULL`.
4. **`Funcionario` não tem FK para `Usuario`.** O responsável pela obra não é
   um usuário logável. A Fase 1 tem que criar essa FK antes de qualquer
   escopo por obra.
5. **A ordem de import em `app.py` é contrato não declarado.** Mover um
   `register_blueprint` acima da linha 386 quebra metade do sistema, e a
   cascata de `proposta_aprovada` depende da ordem em que os handlers são
   importados.
6. **A flag `cronograma_mpp_ativo` nasce desligada.** Ninguém vê a aba de
   importação até rodar `scripts/flag_cronograma_mpp.py <admin_id> --ligar`.
7. **`STYLE.md` foi deletado** — era o brief editorial de outro produto e
   induzia agentes a reescrever documentação correta. `design_guidelines.md`
   ficou marcado como histórico (prescreve Tailwind num projeto Bootstrap).

## Mapa dos documentos

| Arquivo | O que é |
|---|---|
| **`ESTADO-ATUAL.md`** | este — leia primeiro |
| `DEVOLUTIVA.md` | análise de aderência à especificação do app + sequência de fases |
| `DOSSIE-REPO.md` | as 29 respostas sobre arquitetura, dados, infra e qualidade |
| `docs/anexos/A-rotas-sem-autenticacao.md` | censo AST das 724 rotas |
| `FECHO-FASE-0.5.md` | o que a Fase 0.5 entregou e o que não |
| `docs/integracao-dominio.md` | layout 11758 para a exportação contábil |
| `docs/analise-lacuna-veks-2026-07-21.md` | primeira varredura (superada pela DEVOLUTIVA) |
| `docs/superpowers/plans/` | os 10 módulos do cronograma .mpp (M01–M10), fechados |
| `docs/archive/` | 12 documentos mortos, arquivados nesta rodada |
