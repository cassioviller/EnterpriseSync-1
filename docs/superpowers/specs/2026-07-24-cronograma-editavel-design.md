# Design: Cronograma editável estilo MS Project

**Data:** 2026-07-24
**Status:** Aprovado em brainstorming, aguardando plano de implementação

## Objetivo

Evoluir o cronograma por obra para que a edição funcione como no MS Project:
múltiplas predecessoras com tipos de vínculo e latência, recálculo automático
em cascata em dias úteis, caminho crítico, grade de edição estilo planilha,
linha de base (planejado vs. real), desfazer/refazer e um manual de uso em PDF
acessível na própria página.

Fora de escopo: edição adicional via mouse no Gantt (redimensionar barra,
criar vínculo arrastando), cadastro de feriados, mudanças no portal do
cliente e no app mobile (que mantém a lista simplificada atual).

## Contexto atual

- Stack: Flask + SQLAlchemy + PostgreSQL, templates Jinja2 + Bootstrap 5 + JS
  vanilla. Gantt custom (sem biblioteca) em `templates/obras/cronograma.html`.
- A tela já tem edição: duplo clique em células, arrastar barra para mover
  datas, reordenar linhas (SortableJS), criar/editar/excluir tarefas.
- Modelo vivo (`TarefaCronograma`, `models.py:5665`) suporta **uma única**
  predecessora (`predecessora_id`), sem tipo nem lag. Multi-predecessoras
  existem apenas nos snapshots de importação (`predecessoras_json`).
- Recálculo de datas é manual (`POST /recalcular`) e em dias corridos.
- Importação de .mpp/.xml do Project já existe (`views/cronograma_importacao.py`),
  com versionamento (`CronogramaVersao`/`CronogramaTarefaSnapshot`).
- Avanço físico vem de apontamentos de RDO (`RDOApontamentoCronograma`);
  medições ligam em `ItemMedicaoCronogramaTarefa`.

## Abordagem escolhida

**Evoluir o Gantt e a grade atuais, com motor de agendamento no backend
(Python).** Uma única regra de negócio serve a edição manual, a importação
.mpp e a materialização por proposta. Sem bibliotecas pagas, sem reescrever
integrações. Alternativas descartadas: biblioteca pronta (DHTMLX/Bryntum —
licença, motor no navegador, reescrita das integrações) e motor em JS no
frontend (duplicação da regra de negócio e risco de divergência com o banco).

## 1. Modelo de dados

### Nova tabela `tarefa_vinculo`

Substitui o campo único `predecessora_id`:

| Campo | Tipo | Observação |
|---|---|---|
| `id` | PK | |
| `admin_id` | FK | multi-tenant, como as demais tabelas |
| `obra_id` | FK obra | |
| `predecessora_id` | FK `tarefa_cronograma` | |
| `sucessora_id` | FK `tarefa_cronograma` | |
| `tipo` | enum `TI`/`II`/`TT`/`IT` | padrão `TI` (término-início) |
| `lag_dias` | int | em dias úteis; pode ser negativo (antecipação) |

- Único por par (`predecessora_id`, `sucessora_id`); proibido vincular a si mesma.
- Vínculos apenas entre tarefas-folha. Tarefas-resumo (pais) recebem datas por
  roll-up dos filhos.
- **Migração:** cada `predecessora_id` existente vira um vínculo `TI` lag 0.
  O campo antigo fica congelado (somente leitura) até remoção em fase futura.

### Alterações em `tarefa_cronograma`

- `is_critica` (boolean): gravado pelo motor a cada recálculo, permite
  filtrar/exibir sem recalcular.
- `folga_dias` (int): folga total, exibida na grade.

### Novas tabelas de linha de base

- `cronograma_baseline`: `obra_id`, `admin_id`, `nome`, `criada_em`,
  `criada_por`, `ativa` (uma ativa por obra).
- `cronograma_baseline_item`: `baseline_id`, `tarefa_id`, `data_inicio`,
  `data_fim`, `duracao_dias` congelados no momento do salvamento.
- Separadas do versionamento de importação (`CronogramaVersao`), que continua
  servindo somente ao fluxo de .mpp.

### Nova tabela `cronograma_acao` (desfazer/refazer)

- `obra_id`, `admin_id`, `usuario_id`, `criada_em`, `tipo_acao`,
  `payload_antes` (JSON), `payload_depois` (JSON), `desfeita` (boolean).
- Payloads guardam o estado de **todas** as tarefas e vínculos afetados pela
  ação, incluindo as datas alteradas pela cascata do recálculo.
- Pilha por usuário e obra, limitada às últimas 50 ações.

## 2. Motor de agendamento

Novo serviço `services/cronograma_scheduler.py`. A cada edição, recalcula a
obra inteira (centenas de tarefas → recálculo completo é barato e elimina
bugs de propagação parcial):

1. Monta o grafo de tarefas e vínculos. **Edição que cria ciclo é rejeitada**
   com mensagem clara (ex.: "a tarefa 12 já depende da 30").
2. Ordenação topológica + passe para frente: para cada tarefa **não
   iniciada**, `data_inicio` = maior restrição entre as predecessoras
   (conforme tipo de vínculo + lag, contado em dias úteis);
   `data_fim` = início + duração em dias úteis − 1.
3. **Tarefas iniciadas** (com apontamento de RDO ou `data_entrega_real`)
   ficam ancoradas: as próprias datas não mudam, mas continuam empurrando as
   sucessoras.
4. Tarefas sem predecessora mantêm a própria `data_inicio` como âncora
   ("não começar antes de").
5. Roll-up: pais recebem `min(início)`/`max(fim)` dos filhos; duração derivada.
6. Passe para trás: calcula a folga total; folga zero → `is_critica = true`
   (barra vermelha no Gantt).

Calendário: dias úteis de segunda a sexta, sem feriados (evolução futura).
Tarefas nunca começam ou terminam em fim de semana.

## 3. API e fluxo de edição

- O `PUT` de tarefa existente (`cronograma_views.py`) passa a invocar o motor
  e devolve `{tarefas_afetadas: [...]}` com novas datas, folgas e flags de
  crítica de todas as tarefas alteradas. O frontend atualiza grade e barras em
  lote, sem recarregar a página.
- Vínculos: `POST/PUT/DELETE /obra/<id>/vinculo`. A coluna "Predecessoras" da
  grade aceita o formato do Project — `12`, `12TI`, `12TI+3`, `12II-2`,
  múltiplas separadas por `;` — parseado no backend, que materializa os
  vínculos. Número refere-se ao número da linha exibido na grade.
- Desfazer/refazer: `POST /obra/<id>/desfazer` e `/refazer`, respondendo no
  mesmo formato do PUT (tarefas afetadas).
- Baseline: `POST /obra/<id>/baseline` (criar, com nome), listagem e
  ativação; o `GET` da obra inclui os itens da baseline ativa.
- O botão "Recalcular" atual passa a usar o novo motor (permanece como
  "forçar recálculo geral").
- Erros de validação (ciclo, editar início de tarefa iniciada) retornam
  mensagem legível e a célula reverte ao valor anterior.

## 4. Grade tipo planilha

Na tabela já existente da tela (desktop; mobile mantém a lista atual):

- Clique único seleciona a célula; digitar ou segundo clique entra em edição;
  `Tab`/`Shift+Tab` move na horizontal; `Enter` confirma e desce; setas
  navegam; `Esc` cancela.
- Colunas editáveis: nome, duração, data de início (somente tarefas não
  iniciadas), predecessoras (formato Project), quantidade, unidade,
  responsável.
- Recuar/desrecuar (indent/outdent): botões na toolbar + atalhos
  `Alt+Shift+→` / `Alt+Shift+←` (os do Project). Recuar torna a tarefa filha
  da linha de cima; o motor recalcula roll-ups imediatamente.
- `Ctrl+Z`/`Ctrl+Y` chamam os endpoints de desfazer/refazer.
- Inserir linha acima/abaixo pela toolbar; excluir com confirmação.

## 5. Linha de base no Gantt

- Botão "Salvar linha de base" na toolbar (nome sugerido com a data). Salvar
  novamente cria outra baseline e pergunta se deve ativá-la.
- Com baseline ativa: barra cinza fina abaixo da barra atual de cada tarefa
  com as datas congeladas; coluna opcional "Desvio (dias)" na grade
  (fim atual − fim da baseline; positivo = atrasado, destacado em vermelho).
- Somente na visão interna; o portal do cliente não muda.

## 6. Desfazer/refazer

- Toda ação (editar célula, criar/excluir tarefa, vínculo, recuar/desrecuar,
  arrastar barra) grava estado anterior e posterior completos em
  `cronograma_acao`. Um `Ctrl+Z` desfaz a ação **e** toda a sua cascata.
- Ação nova após desfazer descarta o "refazer" pendente.
- Exclusão de tarefa usa o arquivamento lógico existente
  (`ativa`/`arquivada_em`); o desfazer restaura sem perder apontamentos de RDO.

## 7. Manual de uso em PDF

- Botão "Manual (PDF)" na toolbar da página do cronograma, servindo
  `static/docs/manual-cronograma.pdf`.
- Conteúdo: edição na grade e atalhos, formato de predecessoras, como o
  recálculo automático funciona (âncoras, dias úteis), caminho crítico,
  linha de base e desfazer — com capturas de tela da ferramenta.
- Arquivo estático versionado no repositório (sem geração dinâmica),
  atualizado quando a ferramenta mudar. Escrito na última fase, com a
  ferramenta pronta.

## 8. Integrações e migração

- **Importação .mpp/.xml:** passa a materializar **todas** as predecessoras
  (de `predecessoras_json` dos snapshots) como vínculos com tipo e lag —
  hoje apenas a primeira é gravada no modelo vivo.
- **Cronograma gerado por proposta** (`services/cronograma_proposta.py`):
  continua criando a sequência atual, agora como vínculos `TI` na tabela nova.
- **Rollout atrás de flag de tenant** `cronograma_editor_v2`, no mesmo padrão
  de `cronograma_mpp_ativo` — liga por empresa, com rollback simples.

## 9. Fases de implementação

1. **Fase 1 — Motor:** tabela de vínculos + migração + motor de agendamento +
   recálculo automático + caminho crítico, integrados à tela atual.
2. **Fase 2 — Grade:** edição estilo planilha (teclado, indent/outdent).
3. **Fase 3 — Desfazer/refazer.**
4. **Fase 4 — Linha de base.**
5. **Fase 5 — Manual em PDF.**

Cada fase é entregável e testável isoladamente.

## 10. Testes

- Unitários do motor: cada tipo de vínculo (TI/II/TT/IT), lag positivo e
  negativo, detecção de ciclo, âncora de tarefa iniciada, âncora de tarefa
  sem predecessora, contagem em dias úteis, folga/caminho crítico, roll-up
  de resumos.
- Testes de API dos novos endpoints (vínculos, desfazer/refazer, baseline) e
  do PUT com cascata.
- Parse do formato de predecessoras (entradas válidas e inválidas).
- Matriz papel × estado × ação seguindo o padrão existente do projeto.
- Regressão: importação .mpp com multi-predecessoras e geração por proposta.

## Decisões registradas

| Decisão | Escolha |
|---|---|
| Reação das sucessoras à edição | Recálculo automático imediato, sem confirmação |
| Tarefas com avanço de RDO | Ancoradas: não se movem, mas empurram sucessoras |
| Calendário | Dias úteis seg–sex, sem feriados (futuro) |
| Edição via mouse no Gantt (resize/link) | Fora de escopo |
| Motor de recálculo | Backend (Python), fonte única de verdade |
| Biblioteca de Gantt pronta | Descartada (licença + motor no navegador) |
