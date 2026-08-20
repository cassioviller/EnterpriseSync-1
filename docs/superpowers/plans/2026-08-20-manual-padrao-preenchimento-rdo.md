# Manual do Padrão de Preenchimento do RDO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Escrever a **norma de preenchimento** do RDO — o que conta como um RDO aceitável — para que a cobrança ao encarregado seja sobre um documento e não sobre memória de conversa: "está escrito aqui".

**Architecture:** O manual do sistema já existe em `manual/*.md` e é descoberto **por nome de arquivo em ordem alfabética** (`views/manual_views.py:47`) — um capítulo novo entra sem nenhuma mudança de código. O capítulo `23_rdo.md` que existe hoje é um manual **de funcionalidade** (onde clicar); este plano acrescenta um capítulo irmão, `23a_rdo_padrao_preenchimento.md`, que é **normativo** (o que preencher, com que granularidade, e o que não é aceito). São documentos diferentes de propósito: um envelhece com a tela, o outro com a regra de operação.

**Tech Stack:** Markdown (`markdown` com extensões `extra`, `tables`, `sane_lists`, `toc`), Flask, pytest.

**Spec:** Não há spec escrito. Este plano nasce da sessão de brainstorming de 2026-08-20.

## Global Constraints

- O arquivo entra em `manual/` e **precisa** começar com um `# H1` — é dele que sai o título do capítulo (`views/manual_views.py:62-65`).
- O nome do arquivo define a posição no sumário (ordenação alfabética). `23a_` cai entre `23_rdo.md` e `24_cronograma.md`.
- O texto **não pode** conter a expressão "capítulo em construção": ela marca o capítulo como placeholder na UI (`PLACEHOLDER_RE`, `views/manual_views.py:25`).
- Escrita em português do Brasil, no registro do `PRODUCT.md`: técnico-objetivo, terminologia de construção civil, sem jargão de software.
- Testes em `tests/`. Rodar: `python -m pytest tests/<arquivo>.py -v`
- Commits em português: `docs(rdo):`.

## Dependência

**Este plano deve ser executado DEPOIS de `2026-08-20-rdo-efetivo-terceiros.md`.**
O capítulo descreve como registrar equipe de terceiro em qualquer atividade —
se for escrito antes de a tela permitir isso, nasce mentindo. O Paulo foi
explícito na ordem: "aí o que eu pensei, no mesmo estilo de manual que você fez
pro programa, a gente vai ter que ter um manualzinho pro RDO padronizado".

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `manual/23a_rdo_padrao_preenchimento.md` (criar) | A norma: o que preencher, com que granularidade, o que não é aceito. |
| `manual/00_indice.md` (modificar, lista "Estrutura prevista" ~linha 20) | Citar o capítulo novo. |
| `tests/test_manual_rdo_padrao.py` (criar) | Guarda: o capítulo existe, carrega, tem H1, não é placeholder e cobre as seções obrigatórias. |

---

### Task 1: Escrever o capítulo normativo

**Files:**
- Create: `manual/23a_rdo_padrao_preenchimento.md`
- Modify: `manual/00_indice.md`
- Test: `tests/test_manual_rdo_padrao.py`

**Interfaces:**
- Consumes: `views.manual_views._carregar_capitulos() -> List[Capitulo]` com campos `slug`, `anchor`, `titulo`, `html`, `em_construcao`.
- Produces: um `Capitulo` de slug `23a_rdo_padrao_preenchimento`, título `RDO — Padrão de Preenchimento`, `em_construcao=False`.

- [x] **Step 1: Escrever o teste que falha**

Criar `tests/test_manual_rdo_padrao.py`:

```python
"""O capítulo normativo do RDO — reunião de 2026-08-20.

Plano: docs/superpowers/plans/2026-08-20-manual-padrao-preenchimento-rdo.md

O manual só serve ao propósito que o Paulo descreveu — "caso ele me
questionar, tá escrito aqui" — se ele de fato ENTRAR no manual e cobrir os
pontos que hoje ficam a critério de cada encarregado. Este teste é o guarda
disso: sem banco, sem browser, lê o capítulo pelo mesmo carregador que a
tela usa.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from views.manual_views import _carregar_capitulos

SLUG = '23a_rdo_padrao_preenchimento'


@pytest.fixture(scope='module')
def capitulo():
    for c in _carregar_capitulos():
        if c.slug == SLUG:
            return c
    pytest.fail(f'capítulo {SLUG} não encontrado em manual/')


def test_capitulo_entra_no_manual(capitulo):
    assert capitulo.titulo, 'o arquivo precisa começar com um H1'
    assert not capitulo.em_construcao, \
        'o texto contém "capítulo em construção" e a UI vai marcá-lo como vazio'


def test_capitulo_fica_entre_rdo_e_cronograma():
    """A ordem no sumário é a ordem alfabética do nome do arquivo."""
    slugs = [c.slug for c in _carregar_capitulos()]
    assert slugs.index('23_rdo') < slugs.index(SLUG) < slugs.index('24_cronograma')


@pytest.mark.parametrize('assunto', [
    'efetivo',
    'terceiro',
    'ocorrência',
    'foto',
    'clima',
])
def test_capitulo_cobre_os_pontos_obrigatorios(capitulo, assunto):
    """As seções que a reunião elegeu como a fonte das divergências entre o
    RDO do Alan e o do Abel. Se alguma sair do texto, este teste avisa."""
    assert assunto.lower() in capitulo.html.lower(), \
        f'o capítulo não fala de "{assunto}"'
```

- [x] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_manual_rdo_padrao.py -v`

Esperado: **FAIL** — `capítulo 23a_rdo_padrao_preenchimento não encontrado em manual/`.

- [x] **Step 3: Escrever o capítulo**

Criar `manual/23a_rdo_padrao_preenchimento.md`:

```markdown
# RDO — Padrão de Preenchimento

Este capítulo é a **norma** do RDO. O capítulo anterior ensina onde clicar;
este define **o que precisa estar preenchido para o RDO ser aceito**.

Ele existe porque o mesmo dia de obra hoje vira relatórios diferentes conforme
quem preenche. Um RDO que não permite reconstruir o dia não serve para medição,
não serve para produtividade e não serve como prova em discussão com o cliente.

## Regra geral

**Um RDO por obra, por dia trabalhado, lançado no mesmo dia.**

RDO lançado dias depois é reconstrução de memória: as horas arredondam, o
efetivo some e a ocorrência que importava não é registrada. Se o dia não teve
trabalho na obra, não se cria RDO.

## 1. Efetivo próprio

Registre **todas** as pessoas da equipe própria que estiveram na obra, em cada
atividade em que trabalharam, com as horas.

- Use o botão de **equipe** (ícone de pessoas) na atividade.
- Só aparece pessoal **operacional**. Se alguém que trabalhou na obra não
  aparece na lista, a função dele está marcada como administrativa no cadastro
  — avise o escritório, não deixe de fora.
- Uma pessoa pode estar em mais de uma atividade no mesmo dia. Divida as horas
  entre elas; a soma tem de bater com a jornada.
- Se contratou ajudante avulso por alguns dias, ele precisa estar **cadastrado**
  antes de aparecer no RDO. Peça o cadastro ao escritório no primeiro dia — não
  no fim da semana, junto com o reembolso.

**Não é aceito:** escrever o efetivo em campo de observação, ou registrar só o
número de pessoas sem dizer quem.

## 2. Terceiros

Registre **cada equipe de terceiro** que trabalhou, na atividade em que
trabalhou, com o **nome do terceiro** e a **quantidade de pessoas**.

- Use o botão de **terceiro** (ícone de martelo) na atividade. Ele existe em
  qualquer atividade, inclusive nas que também têm equipe nossa.
- **Nome do terceiro**: o cadastro, não o apelido do dia. Se o terceiro não
  está cadastrado, peça o cadastro ao escritório.
- **Quantidade de pessoas**: quantas pessoas da equipe dele estavam na obra
  naquele dia. Este número é o que permite responder depois "o Abraão fez
  aquela fundação em quantos dias, com quantos homens".
- **Horas**: a jornada da equipe naquele dia.
- **Quantidade produzida**: preencha só quando houver medida física do dia
  (m², m³, unidades). Se não houver, deixe zero — registrar efetivo **não**
  move o avanço da atividade, e não é para mover.

**Não é aceito:** anotar "11 pessoas" em observação, ou deixar de registrar o
terceiro porque a atividade está marcada como nossa.

## 3. Avanço das atividades

Aponte o avanço **das atividades que andaram hoje**, e só delas.

- Atividade por **quantidade**: informe o que foi executado **hoje**, não o
  acumulado. O sistema soma.
- Atividade por **percentual**: informe o **percentual acumulado** da
  atividade, não o do dia.
- **Marco**: marque a caixa apenas no dia em que ele de fato ocorreu.
- Atividade que não andou fica **em branco**. Repetir o número da véspera para
  "não deixar vazio" cria avanço que não existiu.

**Não é aceito:** apontar 100% "porque está quase acabando".

## 4. Ocorrências

Registre toda ocorrência que **afetou ou pode afetar prazo, custo ou
segurança**, no dia em que aconteceu.

Entram, no mínimo:

- chuva ou condição que parou ou reduziu o serviço, **com o horário**;
- falta de material, equipamento ou frente de trabalho liberada;
- retrabalho e o motivo;
- acidente, quase-acidente ou interdição;
- visita ou determinação do cliente/fiscalização que mudou o combinado.

Escreva **o que aconteceu, quando e qual o efeito**. "Choveu" não é ocorrência;
"chuva das 10h às 14h, concretagem da sapata S3 adiada para o dia seguinte" é.

**Não é aceito:** deixar sem ocorrência um dia em que a produção caiu.

## 5. Fotos

Mínimo de **três fotos por dia**: uma da frente de serviço no início, uma do
que foi executado, e uma de qualquer ocorrência registrada.

- Foto de ocorrência é **obrigatória** quando a ocorrência é física (dano,
  interdição, material errado, alagamento).
- Foto tem de permitir identificar **o local**. Detalhe fechado sem referência
  não serve como prova depois.

## 6. Clima

Preencha o clima do dia. É o que sustenta a ocorrência de chuva quando ela vira
discussão de prazo com o cliente.

## 7. Fechamento

- Salve como **rascunho** durante o dia, quantas vezes quiser.
- **Finalize** o RDO no fim do dia. A finalização é o que gera custo e alimenta
  o cronograma.
- Corrigiu algo depois? Edite o RDO e salve — o sistema ressincroniza custo e
  avanço. Não crie um segundo RDO do mesmo dia para "consertar".

## O que o escritório confere

Um RDO é devolvido para correção quando:

1. tem avanço apontado e **nenhum efetivo** (nem próprio, nem terceiro);
2. tem terceiro em observação em vez de registrado no campo próprio;
3. tem queda de produção **sem ocorrência** que a explique;
4. tem ocorrência física **sem foto**;
5. foi lançado com mais de **dois dias** de atraso.
```

- [x] **Step 4: Citar o capítulo no índice**

Em `manual/00_indice.md`, na lista "Estrutura prevista", trocar a linha:

```markdown
   - RDO (Relatório Diário de Obra)
```

por:

```markdown
   - RDO (Relatório Diário de Obra)
   - RDO — Padrão de Preenchimento (a norma: o que precisa estar preenchido)
```

- [x] **Step 5: Rodar os testes**

Run: `python -m pytest tests/test_manual_rdo_padrao.py -v`

Esperado: **os 7 PASSAM** (2 + 5 do parametrize).

- [x] **Step 6: Conferir a renderização**

Subir a app e abrir `/manual`. Conferir:
1. O capítulo aparece no sumário lateral, **entre** "RDO" e "Cronograma".
2. As tabelas e listas numeradas renderizam (extensões `extra`/`sane_lists`).
3. O capítulo **não** está marcado como "em construção".
4. `/manual/download` inclui o capítulo novo.

- [x] **Step 7: Commit**

```bash
git add manual/23a_rdo_padrao_preenchimento.md manual/00_indice.md tests/test_manual_rdo_padrao.py
git commit -m "docs(rdo): manual do padrao de preenchimento do RDO"
```

---

### Task 2: Revisar a norma com quem vai ser cobrado por ela

Um manual normativo escrito só pelo escritório vira letra morta na primeira
divergência. Esta task não é de código.

**Files:**
- Modify: `manual/23a_rdo_padrao_preenchimento.md` (conforme a revisão)
- Test: `tests/test_manual_rdo_padrao.py` (atualizar a lista do parametrize se alguma seção mudar de nome)

**Interfaces:**
- Consumes: o capítulo da Task 1.
- Produces: a versão revisada.

- [ ] **Step 1: Levar o capítulo ao Alan e ao Abel**

Enviar o capítulo (ou `/manual` direto) e pedir resposta a três perguntas:
1. Tem alguma regra aqui que **não dá para cumprir** no campo? Qual e por quê?
2. Tem alguma coisa que você já registra e **não está aqui**?
3. Os cinco motivos de devolução no fim são justos?

- [ ] **Step 2: Aplicar as correções**

Ajustar o texto conforme as respostas. Se uma regra cair, **registre o motivo**
no próprio capítulo — a norma seguinte vai perguntar por que ela não está lá.

- [ ] **Step 3: Rodar os testes**

Run: `python -m pytest tests/test_manual_rdo_padrao.py -v`

Se alguma seção obrigatória foi renomeada, atualizar a lista do
`@pytest.mark.parametrize` — o teste existe para avisar, não para congelar.

- [ ] **Step 4: Commit**

```bash
git add manual/23a_rdo_padrao_preenchimento.md tests/test_manual_rdo_padrao.py
git commit -m "docs(rdo): padrao de preenchimento revisado com o campo"
```
