# Plano de Implementação — RDO em porcentagem livre (`rdo_percentual_livre`)

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — entregue; 🔬 todos os arquivos prometidos existem. 🔬 6/6 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


Spec: `docs/superpowers/specs/2026-07-24-rdo-percentual-livre-design.md`
(aprovado 2026-07-24, abordagem A). Tudo atrás da flag de tenant nova —
**flag OFF = byte-idêntico**.

## Contexto verificado no código

- **Migração 221 já congelou a dedução**: a maioria das tarefas existentes
  tem `modo_apontamento` NÃO nulo (backfill da dedução vigente). Ligar a
  flag precisa sobrepor também a escolha explícita — exatamente o que o
  spec §2 pede. A coluna não é tocada (reversibilidade).
- **Pontos de derivação por quantidade** em `utils/cronograma_engine.py`
  (todos ramificam por `tarefa.quantidade_total > 0`, ignorando o modo):
  `_atualizar_percentual_sem_commit` (l.211), `sincronizar_percentuais_obra`
  (l.243), `calcular_progresso_rdo` (l.487) e `atualizar_percentual_tarefa`
  (l.886, com ramo próprio de terceiros). Além deles,
  `calcular_progresso_geral_obra_v2` (l.677) conta `n_tarefas_apontadas`
  por `quantidade_acumulada > 0` — subconta apontamentos percentuais.
- **Âncoras do scheduler NÃO dependem de quantidade**:
  `_ids_com_apontamento` testa existência de linha de apontamento.
  Nenhuma mudança na Fase 1 do editor.
- **UI do RDO já é dirigida pelo backend**: `templates/rdo/novo.html`
  (l.1107–1226) e `editar_rdo.html` renderizam pelo `tipo_modo` que vem
  de `tarefas-rdo` — mudar o resolvedor muda a tela. O "Total: X un" já
  se esconde quando `quantidade_total` é falsy (pedido do usuário
  atendido de graça); mas na l.1219 a referência só aparece quando
  `modo === 'quantidade'` — precisa aparecer também no modo percentual.
- **Seletor de modo** nos modais do cronograma: `nt_modo` (nova tarefa,
  l.1884) e `ed_modo` (edição, l.1958/2076) em
  `templates/obras/cronograma.html`.
- **Círculo de imports**: `services/cronograma_apontamento_service`
  importa de `utils/cronograma_engine` — o helper da flag NÃO pode morar
  no service (o engine também precisa dele). Vai para `utils/tenant.py`,
  que já é o lar de `is_v2_active`/`get_tenant_admin_id` e importa
  models tardiamente.

## Decisão 1: helper único `rdo_percentual_livre_on(admin_id)` em `utils/tenant.py`

Consulta `ConfiguracaoEmpresa.rdo_percentual_livre` por `admin_id`
explícito (as funções do engine já recebem `admin_id`; nada de
`current_user` em código de serviço). Views usam o mesmo helper com
`get_tenant_admin_id()`.

## Decisão 2: derivação "percentual-first" como função interna única

Em vez de espalhar `if flag` nos 4 pontos, um helper interno no engine
(`_percentual_do_ultimo_apontamento(tarefa_ou_linhas...)`) encapsula a
leitura do `percentual_realizado` mais recente; cada ponto vira
`if rdo_percentual_livre_on(admin_id): usar helper; else: ramo atual`.
O ramo atual fica intocado (caracterização com flag off).

## Step A — Flag (migração 226 + script + helper)

1. `models.py`: coluna `rdo_percentual_livre` em `ConfiguracaoEmpresa`
   (`Boolean, nullable=False, default=False, server_default='false'`).
2. Migração 226 idempotente (`ADD COLUMN IF NOT EXISTS`, padrão da 222),
   registrada em `executar_migracoes()`.
3. `scripts/flag_rdo_percentual_livre.py` (`--status/--ligar/--desligar`),
   clone do molde `flag_cronograma_editor_v2.py`.
4. `utils/tenant.py`: `rdo_percentual_livre_on(admin_id) -> bool`.

## Step B — Resolvedor de modo

`services/cronograma_apontamento_service.modo_da_tarefa`:

```
if _is_marco(tarefa): return 'percentual'          # como hoje
if rdo_percentual_livre_on(tarefa.admin_id): return 'percentual'   # NOVO
... escolha explícita e dedução como hoje ...
```

Validações intactas: `MarcoApenasZeroOuCem`, retrocesso com
justificativa, sobreexecução. O caminho quantitativo do service continua
existindo (flag off).

## Step C — Derivação percentual-first no engine

Com a flag ligada (por `admin_id`):

- `_atualizar_percentual_sem_commit`, `sincronizar_percentuais_obra`,
  `atualizar_percentual_tarefa`: `percentual_concluido` = min(100,
  `percentual_realizado` do apontamento mais recente), para TODA tarefa
  (não só as sem quantidade). Carve-outs preservados: `responsavel ==
  'terceiros'` continua manual; rollup bottom-up dos pais inalterado.
- `calcular_progresso_rdo`: o ramo `quantidade_total > 0` deixa de
  derivar por quantidade; devolve o acumulado percentual (mesma fonte do
  ramo sem quantidade). `quantidade_acumulada` continua no dict de
  resposta (soma dos dias — será 0 para apontamentos percentuais, como
  hoje).
- `calcular_progresso_geral_obra_v2`: `n_tarefas_apontadas` passa a
  contar (flag on) tarefa com `percentual_realizado > 0` OU
  `quantidade_acumulada > 0` — corrige a subcontagem sem mexer no caso
  flag off.

## Step D — Views e UI

1. `cronograma_views.tarefas_rdo` (l.2153): nada estrutural — `tipo_modo`
   já sai do resolvedor; `saldo` já só é calculado quando
   `tipo_modo == 'quantidade'` (com flag on nunca ocorre → `null`, valor
   que o contrato atual já usa para percentuais).
2. `templates/rdo/novo.html` (e espelho em `editar_rdo.html`): exibir a
   referência "Total: X un" também quando `modo === 'percentual'` e
   houver `quantidade_total` (l.1219; a l.1156 já faz isso no outro
   card). Nenhum "0" quando vazio (comportamento falsy atual).
3. `templates/obras/cronograma.html`: esconder o seletor de modo
   (`nt_modo`, `ed_modo` + hint) quando a flag do tenant estiver ligada —
   novo booleano `rdo_percentual_livre` no contexto do template
   (`cronograma_obra`), `d-none` nos wrappers. A API continua aceitando
   `modo_apontamento` (inerte com flag on).

## Step E — Testes (`tests/test_rdo_percentual_livre.py`) + regressão

Padrão das fases (fixture `_ambiente`, `WTF_CSRF_ENABLED=False`,
mensagens pt-BR verbatim):

1. Resolvedor: flag on → 'percentual' para tarefa com quantitativo, com
   escolha explícita 'quantidade' e com modo NULL; marco → 'percentual'
   nos dois estados da flag; flag off → dedução/escolha como hoje.
2. Continuidade: tarefa com histórico quantitativo (ex.: 62% derivado)
   mantém 62% após ligar a flag (sync + progresso); próximo apontamento
   percentual (70) atualiza para 70.
3. Regressão do bug atual: tarefa com `quantidade_total > 0` apontada em
   percentual mostra o % digitado (não 0) com a flag ligada.
4. Validações com flag on: retrocesso sem justificativa recusa
   (mensagem verbatim); >100 sem sobreexecução recusa; marco 40 recusa.
5. `tarefas-rdo` flag on: `tipo_modo == 'percentual'` para todas,
   `saldo is None`, `quantidade_total`/`unidade_medida` presentes quando
   cadastrados.
6. Flag off byte-idêntico: resposta de `tarefas-rdo` e
   `percentual_concluido` sincronizado idênticos aos de hoje (tarefa
   quantitativa continua derivando por quantidade).
7. `n_tarefas_apontadas` conta tarefa apontada em % (flag on).
8. Regressão completa da suíte ao final; commit único.

## Riscos

- **Tela do RDO tem dois pontos de render** (novo/editar + variações de
  card): conferir visualmente os dois fluxos com a flag ligada antes do
  commit (subir app local, como na Fase 5).
- **Banco de dev instável em rodadas longas** (aprendizado da Fase 5):
  se a regressão falhar com `OperationalError` de conexão, rodar os
  arquivos falhos isolados antes de suspeitar do código.
- **KPIs que leem `percentual_concluido`** (dashboards, portal) não
  mudam de fonte — continuam lendo o campo sincronizado; só a fórmula de
  sincronização muda com a flag. Nenhuma mudança de contrato.
