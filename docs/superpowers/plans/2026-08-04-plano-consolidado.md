# Plano consolidado — 2026-08-04

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recomendado) ou `superpowers:executing-plans` para executar tarefa a tarefa.
> Os passos usam checkbox (`- [ ]`).

**O que é:** o recorte de execução que sai da reconferência de 04/08. Onze recortes
foram aprofundados abrindo o código vivo; nenhum foi descartado na leitura. Este
documento os ordena em cinco blocos, com Task numerada, `arquivo:linha`, teste que
prova e risco por Task.

**Contra o quê:** `main` no commit **`a723babe`** (03/08), árvore limpa. Toda linha
citada aqui foi aberta em 04/08 — onde o número diverge da reconferência, vale este
documento, e a divergência está registrada na §9.

**O que substitui:** a **§5 do `PLANO-NUCLEO.md`** (backlog de 25 automações), que já
havia sido substituída pela §6 da reconferência. Este plano substitui as duas: é a
lista de trabalho com recorte de execução. **Não substitui** a §4 (os dez pacotes),
a §6 (estruturas mortas — ver B4), nem a §7 (decisões, ver §5 aqui).

**A regra da casa continua valendo:** nada aqui vira mudança sem spec própria em
`docs/superpowers/specs/`, seguindo spec → plano → fases atrás de flag. Este
documento é o plano; a spec de cada bloco é escrita antes da primeira Task dele.

**Tech stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de
migrações próprio numerado (`migrations.py` / `executar_migracoes`), PostgreSQL,
pytest (`bash run_tests.sh --gate` = `pytest tests/ -m "not browser"`;
`pyproject.toml:76-86` define `--strict-markers --timeout=300`).

---

## 1. A espinha, em uma página

**O sistema está perdendo dado de dinheiro e de presença em três lugares, e não
consegue perceber, porque seus testes conferem texto de arquivo em vez de
comportamento.**

Os três lugares, medidos nesta rodada rodando o código contra o Postgres de
desenvolvimento — não inferidos por leitura:

1. **RDO.** Mesmo funcionário mensalista (`tipo_remuneracao='salario'`,
   `valor_diaria=0` — o default de `models.py:302-303`), mesma obra, 8h apontadas,
   três rotas:
   `POST /salvar-rdo-flexivel` (`views/rdo.py:3612`) → 1 `RDOCustoDiario` de
   R$ 124,00 e 1 `GestaoCustoFilho`; `POST /rdo/editar/<id>`
   (`rdo_editar_sistema.py:164`) → `RDOCustoDiario` de R$ 124,00 e **zero**
   `GestaoCustoFilho`; `POST /rdo/finalizar/<id>` (`crud_rdo_completo.py:555`) →
   **zero** dos dois. **R$ 124,00 por mensalista por dia**, nas duas últimas.
   Causa: `event_manager.py:729-733` lê só `funcionario.valor_diaria` e faz
   `continue` quando é 0 — enquanto `services/rdo_custos.py:385-413` lê
   `RDOCustoDiario`.

2. **Ponto.** Dois `POST /novo_ponto` (`views/admin.py:98`) no mesmo dia e obra —
   08:00-12:00 e 13:00-17:00 — devolvem 200/200, criam **2** `RegistroPonto`
   (4h + 4h = 8h) e deixam **um** `CustoObra` de R$ 62,00 por 4h. O dia de 8h vira
   metade. `views/admin.py:150` cria o registro incondicionalmente (os outros nove
   criadores de `RegistroPonto` do sistema reusam o do dia);
   `event_manager.py:524-545` sobrescreve em vez de somar.

3. **Presença planejada.** `AllocationEmployee.sincronizar_com_ponto`
   (`models.py:4556`) protege o registro do dia por uma condição só —
   `tem_batida_real = bool(hora_entrada or hora_saida)` (`models.py:4580-4581`).
   Ausência classificada não tem hora nenhuma: atestado, falta justificada e férias
   caem no ramo de preenchimento (`models.py:4600-4616`) e viram
   `trabalho_normal` com 8h na obra do plano, em silêncio.

E o motivo de nada disso ter aparecido:

**O gate de 1778 testes está verde e não prova comportamento.** Os testes-guarda
dos pacotes leem TEXTO DE ARQUIVO. `tests/test_p1_dedup_cross_origem.py:151-165`
faz `re.findall(r'^\s*gerar_custos_mao_obra_rdo\(', texto)` e
`assert "EventManager.emit('rdo_finalizado'" in texto` sobre dois arquivos, e nem
abre `views/rdo.py`. Um emissor que mandasse `{}` como payload passaria — e é
literalmente o que aconteceu: os três emitem `{'rdo_id': rdo.id}`
(`crud_rdo_completo.py:475`, `:592`, `rdo_editar_sistema.py:557`),
`recalcular_medicao_apos_rdo` sai em `event_manager.py:1529-1531` por falta de
`obra_id`, e o teste continuou verde afirmando que "custo implica medição".

Pior que os textuais: os dois testes de **comportamento** do mesmo arquivo também
não pegavam, por dois motivos somados. As asserções são `len(custos) <= 1`
(`tests/test_p1_dedup_cross_origem.py:112`) e `len(filhos) <= 1` (`:128`) —
**verdadeiras para ZERO**. E o tenant do arreio semeia um `RegistroPonto` na mesma
data (`tests/helpers_tenant.py:88-90`), então a guarda `existe_ponto_no_dia`
(`event_manager.py:722-726`) faz `continue` antes de o defeito ser alcançado: o
teste mede a guarda, não o custo. O funcionário do arreio
(`tests/helpers_tenant.py:80-84`) é `'salario'` com `valor_diaria` no default 0 —
exatamente o perfil que o handler descarta.

O único teste da suíte que POSTA em `/rdo/editar` com um mensalista
(`tests/test_rdo_ciclo_completo.py:69-74` e `:167`) conta `RDOMaoObra`,
`RDOOcorrencia` e `RDOCustoDiario` e **nunca olha `GestaoCustoFilho`**: estava a uma
asserção de distância de pegar a regressão.

**Disso decorre a ordem deste plano.** O arreio (B0) vem primeiro não por gosto de
processo, mas porque sem ele as correções de dinheiro são inverificáveis. Já houve
uma regressão de custo aprovada por um gate verde; repetir a correção sem trocar o
instrumento de medida é repetir o método que produziu o defeito.

A ordem completa:

| Bloco | O que é | Por que nesta posição |
|---|---|---|
| **B0** | O arreio de teste por rota | Habilitador. Sem ele nada abaixo é verificável |
| **B1** | Parar de perder dado | Dinheiro e presença saindo do sistema hoje |
| **B2** | Consertar o que o sistema informa errado | O dado existe; o número exibido mente |
| **B3** | Fechar os elos que morrem a um passo | Peças construídas que não se tocam |
| **B4** | Aposentadorias | Só depois que o resto está estável |

---

## 2. Contagem de Tasks

| Bloco | Tasks | Entregues | Abertas | Esforço agregado |
|---|---|---|---|---|
| B0 — o arreio | 6 | **6** ✅ | 0 | M |
| B1 — parar de perder dado | 16 *(era 16, subiu a 17, e a B1.14 foi cortada)* | **16** ✅ | 0 | G |
| B2 — o que o sistema informa errado | 20 | **1** | **19** | G |
| B3 — os elos que morrem a um passo | 10 | 0 | **10** | M |
| B4 — aposentadorias | 9 | 0 | **9** | M |
| **Total** | **61** *(62 − 1 cortada)* | **23** | **38** | |

**Estado em 05/08: os blocos B0 e B1 estão FECHADOS.** A05, A10, A16-a e A09
fechados; B0 inteiro (6/6), a trilha T1 (B1.1-B1.5b), a T2 inteira (B1.6-B1.11) e
a T3 (B1.12, B1.13, B1.15, B1.16 — com a **B1.14 cortada**, §8.1). A contagem
subiu de 61 para 62 porque o B0 achou um defeito que nenhum recorte tinha visto
(B1.5b), e voltou a 61 com o corte.

**O próximo trabalho é o B2**, e ele não espera nada.

**Sobram TRÊS `xfail` no repositório inteiro, e nenhum é dívida técnica** —
todos esperam decisão ou Task futura:

| Onde | Item | Espera |
|---|---|---|
| `test_arreio_presenca_rotas.py:391` | A16, 2ª metade | **D6** |
| `test_p1_dedup_cross_origem.py:98` | A16, 2ª metade | **D6** |
| `test_arreio_aprovacao_proposta_rotas.py:166` | A14 | Task **B3.5** |

⚠️ **O segundo estava rotulado como `A05` e o rótulo era falso** — corrigido no
fecho da sessão. Depois da B1.3 o guard exige ponto **produtivo** e cobre só
`CustoObra`, então o RDO abster-se ali é o comportamento CERTO: existe
`RegistroPonto` de 8h com obra, e o ponto é o fato medido. O que falta é a outra
ponta — **o custo do ponto nunca chega**, porque nada em `models.py` emite
`ponto_registrado` (`grep EventManager models.py`: vazio). Mesmo buraco do
primeiro, mesma trava. Quem lesse o rótulo antigo iria procurar defeito em A05,
que está fechado.

Dos oito xfail que o B0 plantou, sete foram cobrados e removidos pelo próprio
mecanismo que corrigiram.

**As duas últimas do B1, e o que aconteceu com cada uma:**

* **B1.15** — ✅ **entregue em 05/08**: 403 → 404 na entrada múltipla. Fechou o
  bloco. O T5 que a prova **não existia** apesar de a B1.12 marcar o Step 1 como
  feito — escrito antes da correção e visto vermelho.
* **B1.14** — ⛔ **CORTADA em 05/08** (decisão do Cássio: seguir a recomendação).
  Mexia em função sem chamador vivo onde a correção isolada troca uma mensagem
  errada por um 500. Ver §8.1.

Com o B1 fechado começa o **B2** — o maior bloco, 20 Tasks, e onde o assunto
muda: sai *"o sistema está perdendo dado"* e entra *"o número exibido mente"*.

**Como este documento registra progresso.** Task entregue leva uma linha
`**Status:**` logo abaixo do título, com o commit e — quando houve — o **desvio**
em relação ao que estava escrito aqui. O desvio é a parte que importa: checkbox
marcado não ensina nada a quem retomar, e três das quatro Tasks de B1 foram
entregues fora do recorte planejado, por motivo técnico registrado em cada uma.

---

## 3. B0 — O arreio de teste por rota

**Por que existe.** A suíte tem 171 arquivos e **sabe** exercitar rota:
`tests/test_rdo_ciclo_completo.py:95-218` posta em `/salvar-rdo-flexivel` e
`/rdo/editar` e afirma sobre o banco; `tests/test_gestao_custo_filho_tenant.py:88-112`
posta e relê `GestaoCustoFilho`; `tests/test_caracterizacao_apontamento_cronograma.py:149-215`
posta e relê `RDOApontamentoCronograma`. O que **não existe** é arreio ligando
ROTA → DINHEIRO: nenhum teste do repositório afirma sobre `GestaoCustoFilho` ou
`CustoObra` depois de um POST nas rotas de RDO ou de ponto.

**O que entrega.** Semeadores e coletores reutilizáveis, quatro arquivos de teste
por rota cobrindo RDO, ponto e aprovação de proposta, e o aperto das asserções
vacuosas do p1. **O arreio nasce vermelho** nos casos que dependem de B1 — e é isso
que se quer: o vermelho vira o checklist de A05/A10/A16.

**Infra existente a reaproveitar:** `conftest.py:41-44` importa `main` no tempo de
coleção (54 blueprints antes da 1ª request — **não repetir por conta própria**);
`conftest.py:69-94` repete como fixture session/autouse. Não há fixture `app` nem
`client` global: cada arquivo monta a sua (`app.test_client()` +
`session_transaction()['_user_id']`, como `tests/helpers_tenant.py:111-118` e
`tests/test_gestao_custo_filho_tenant.py:80-85`).

**Esforço:** M. **Migração:** nenhuma. **Depende de:** nada.

---

### Task B0.1: `helpers_tenant` ganha tenant sem fatos e perfil de remuneração parametrizável

**Files:** Modify `tests/helpers_tenant.py` (`_um_tenant`, linhas 52-101;
`dois_tenants`, 104-108)

**Comportamento novo.** `_um_tenant` ganha `com_fatos=True`. Com `com_fatos=False`
o tenant nasce só com admin + cliente + obra + funcionário — **sem** o
`RegistroPonto` de `:88-90`, sem `RegistroAlimentacao` e sem `CustoObra`. O
funcionário ganha `tipo_remuneracao` e `valor_diaria` opcionais (hoje chumbados em
`'salario'`/`None` em `:80-84`), para o arreio semear mensalista, horista e diarista
lado a lado. Assinatura antiga segue valendo, com os mesmos defaults.

**Teste que prova:** os quatro testes que já usam `dois_tenants`
(`tests/test_p1_dedup_cross_origem.py`, `tests/test_p1_fallback_e_idempotencia.py`,
`tests/test_p1_isolamento_relatorios.py`, `tests/test_gestao_custo_filho_tenant.py`)
rodam **sem edição** e continuam verdes. Verde sem edição é a prova de neutralidade.

**Risco → mitigação.** Mudar os defaults quebra os quatro consumidores, que dependem
dos três fatos semeados → não mexer nos defaults. E é justamente o `RegistroPonto` de
`:88-90` que faz o dedup do RDO pular: quem semear ponto **e** RDO na mesma data
testa `event_manager.py:722-726`, não o custo.

- [x] **Step 1:** acrescentar `com_fatos` e os dois parâmetros de remuneração
- [x] **Step 2:** `pytest tests/test_p1_dedup_cross_origem.py tests/test_p1_fallback_e_idempotencia.py tests/test_p1_isolamento_relatorios.py tests/test_gestao_custo_filho_tenant.py -q` — verdes sem edição
- [x] **Step 3:** commit — `test(arreio): helpers_tenant com com_fatos e perfil de remuneração`

**Status: ✅ entregue em `88d3f924`.** Sem desvio. Os quatro consumidores rodaram
sem edição, que era a prova de neutralidade pedida.

---

### Task B0.2: `tests/helpers_dinheiro.py` — semeadores, coletores de estado e `assert_custo_do_dia`

**Files:** Create `tests/helpers_dinheiro.py` (ao lado de `tests/helpers_tenant.py`;
importado como `from helpers_dinheiro import ...` — o `sys.path` já é resolvido por
`conftest.py:25`)

**Comportamento novo.** Três blocos:

1. **Semeadores.** `rdo_com_mao_de_obra(tenant, data, horas)` cria RDO + `RDOMaoObra`.
   `form_rdo(...)` monta o dict de formulário com as chaves REAIS que as rotas
   parseiam: `obra_id`, `admin_id_form`, `data_relatorio`,
   `cron_tarefa_<tarefa_id>_func_<func_id>_horas` (regex em
   `rdo_editar_sistema.py:401`, espelho em `views/rdo.py`) e
   `sub_func_<sub_mestre_id>_<func_id>_horas` (regex em `rdo_editar_sistema.py:370`).
2. **Coletores de ESTADO.** `filhos_mao_de_obra(tenant, data)` (join
   `GestaoCustoFilho` × `GestaoCustoPai` por `entidade_id` + `tipo_categoria` in
   `('SALARIO','MAO_OBRA_DIRETA')`), `custos_obra(tenant, data, categoria=None)`,
   `custo_diario(rdo_id)`, `soma(...)`.
3. **`assert_custo_do_dia(tenant, data, valor_esperado, linhas_esperadas)`** — afirma
   contagem E soma, com mensagem de falha que imprime o que encontrou.

**Teste que prova:** um autoteste do módulo — semear um custo conhecido e conferir
que o coletor o encontra e que o coletor do outro tenant não.

**Risco → mitigação.** (a) Os handlers commitam por dentro e a sessão do teste guarda
o objeto velho → todo coletor chama `db.session.expire_all()` antes de reler (padrão
de `tests/test_gestao_custo_filho_tenant.py:105`). (b) Coletor sem `admin_id` vira
contagem global e a base de dev é compartilhada entre execuções → todo coletor filtra
por `admin_id`. (c) O módulo **não** expõe semeador que crie `RegistroPonto` e RDO na
mesma data por acidente: quem quiser os dois chama duas funções explícitas, e o
docstring registra que a combinação testa `event_manager.py:722-726`, não o
lançamento.

- [x] **Step 1:** escrever os três blocos
- [x] **Step 2:** autoteste do coletor (semeia, coleta, cruza tenant)
- [x] **Step 3:** commit — `test(arreio): helpers_dinheiro — coletores de estado por tenant`

**Status: ✅ entregue em `7d929e42`.** Sem desvio.

---

### Task B0.3: `tests/test_arreio_custo_rdo_rotas.py` — as rotas vivas de RDO, mesmo cenário

**Files:** Create `tests/test_arreio_custo_rdo_rotas.py`
(modelo estrutural: `tests/test_rdo_ciclo_completo.py:41-81` — fixture `amb`
scope='module' com app_context — mais `tests/test_gestao_custo_filho_tenant.py:31-37`
— fixture `_config` autouse com `TESTING`/`WTF_CSRF_ENABLED`)

**Cenário.** Um tenant com obra, uma `TarefaCronograma` da obra e UM funcionário
mensalista (`tipo_remuneracao='salario'`, `salario=3000.0`, `valor_diaria=0` — o
perfil da maioria da base). Data fixa, **sem nenhum `RegistroPonto` semeado nessa
data**. Três RDOs equivalentes do mesmo dia, um por rota, todos com o mesmo campo
`cron_tarefa_<tarefa_id>_func_<func_id>_horas = '8'`.

**Comportamento afirmado.** `POST /salvar-rdo-flexivel` (`views/rdo.py:3612`) é a
**referência** — é a única que chama `gerar_custos_mao_obra_rdo` (`:4489`) **e**
emite com `obra_id` (`:4500-4504`). Testes:

- (a) paridade `/rdo/finalizar` × flexível;
- (b) paridade `/rdo/editar` × flexível;
- (c) o payload carrega `obra_id`, afirmado pelo **efeito** (medição /
  `ContaReceber` `origem_tipo='OBRA_MEDICAO'` da obra mudou), nunca lendo o dict;
- (d) reexecutar a mesma rota não duplica;
- (e) matriz de perfis — mensalista (`salario=3000`, `valor_diaria=0`), diarista
  (`valor_diaria=150`) e horista, cada um com exatamente uma linha;
- (f) `POST /rdo/salvar` (`views/rdo.py:2766`) gera custo e **não** emite —
  congelar e marcar o gap.
- (g) segunda asserção estrutural: `RDOCustoDiario.componente_folha > 0` implica
  `GestaoCustoFilho > 0`. A linha de custo diário existir e o filho não é a
  assinatura exata do defeito de `event_manager.py:730-733`.

**Asserção.** O valor esperado **não é chumbado**: sai do que `/salvar-rdo-flexivel`
produziu. Medido hoje: flexível = 1 filho de R$ 124,00, origem `'rdo_custo_diario'`;
editar = 0 filhos **com** `RDOCustoDiario` de R$ 124,00 já gravado; finalizar = 0
filhos e 0 `RDOCustoDiario`. Todo teste termina em assert sobre
`GestaoCustoFilho`/`CustoObra`/`RDOCustoDiario`, nunca em `status_code` sozinho.

**Por que o teste textual atual não pegava.** `tests/test_p1_dedup_cross_origem.py:151-165`
abre `rdo_editar_sistema.py` e `crud_rdo_completo.py` como TEXTO e verifica se a
string `"EventManager.emit('rdo_finalizado'"` aparece — ela aparece, e o teste fica
verde enquanto o banco não recebe um centavo. Os dois testes de comportamento do
mesmo arquivo (`:98-114`, `:117-130`) emitem o evento à mão (`:72-75`) em vez de
postar na rota, afirmam `<= 1` (verdadeiro para zero) e usam um tenant que já traz
`RegistroPonto` na data.

**Riscos → mitigação.**
1. `/rdo/finalizar` exige subatividade OU funcionário, senão sai por
   `crud_rdo_completo.py:576-578` com flash+redirect → semear `RDOMaoObra` ANTES do POST.
2. `/rdo/editar` REESCREVE a mão de obra a partir do formulário
   (`rdo_editar_sistema.py:445-491`) → postar sem as chaves `cron_tarefa_*`/`sub_func_*`
   apaga a equipe e o teste vira vacuoso. **Toda função do arreio que posta um RDO
   afirma, ANTES de olhar dinheiro, que `RDOMaoObra.count()` do RDO é o esperado.**
3. Não semear `RegistroPonto` na mesma data, ou `event_manager.py:722-726` pula o
   custo antes do defeito.
4. Não gastar teste com `crud_rdo_completo.py:475` — `salvar_rdo()` não tem rota
   desde `b30923b5` (documentado em `crud_rdo_completo.py:243-254`).
5. HTTP 302 não é sucesso: as rotas capturam quase tudo em `except` amplo e
   redirecionam com flash de erro (`crud_rdo_completo.py:487-509`,
   `rdo_editar_sistema.py:566-585`) → status é pré-filtro
   (`assert r.status_code in (200,302)`); quem decide é linha de banco.

**Marcação.** Os casos (a), (b) e (g) entram com
`@pytest.mark.xfail(strict=True, reason='A05')`. `strict=True` faz o teste **falhar
quando o defeito for corrigido** e alguém esquecer de tirar a marca — o xfail vira o
checklist de B1. Os que já passam (idempotência, isolamento, paridade da rota
flexível) entram sem marca.

- [x] **Step 1:** escrever o arquivo com os sete casos
- [x] **Step 2:** rodar — confirmar que (a), (b) e (g) são xfail e o resto passa
- [x] **Step 3:** commit — `test(arreio): custo de RDO por rota — paridade entre os três caminhos`

**Status: ✅ entregue em `35975e7a`, corrigido em `ddbbc1b7`. Dois desvios, os dois
do tipo que este documento existe para registrar.**

**Desvio 1 — um defeito que eu havia relatado NÃO existe.** Estava escrito que dois
RDOs no mesmo dia dobravam o custo do mensalista (R$ 248,00 por um dia de 8h). Medido
nos três arranjos: 8h em um RDO = R$ 124,00; 4h+4h em dois = R$ 62,00 + R$ 62,00 =
R$ 124,00; 8h+8h em dois = R$ 248,00. O custo do mensalista é `horas × valor_hora`
(`services/custo_funcionario_dia.py:113-116`) e a soma acompanha as horas
**reportadas** — 8+8 são 16 horas digitadas, e o sistema custeou fielmente o que
recebeu. O `proporcao` de `:81` é aplicado ao diarista (`:97`) e a VA/VT (`:87-88`),
onde a unidade é o DIA, e deliberadamente não ao mensalista, onde a unidade é a hora;
aplicá-lo ali quebraria o caso 4h+4h. **O teste virou congelamento dessa regra**, com
a medição no docstring, para que quem ler o cabeçalho do módulo ("rateio proporcional
quando aparece em >1 RDO") não "conserte" o que não está quebrado.

**Desvio 2 — no lugar, a mesma sonda achou um defeito real e mais preciso**, no
diarista: `RDOCustoDiario = [75,00 · 75,00]` → R$ 150,00 (uma diária, correto) contra
`GestaoCustoFilho = [150,00 · 75,00]` → R$ 225,00 (uma diária e meia). **Virou a Task
B1.5b**, que não existia em recorte nenhum.

**Erro meu de construção, corrigido em `ddbbc1b7`:** o teste novo criava dois cenários
no mesmo `app_context` e o segundo POST dava 404 — o arreio diz "um cenário por teste"
no próprio helper, e eu violei.

---

### Task B0.4: `tests/test_arreio_presenca_rotas.py` — ponto manual e sync do plano

**Files:** Create `tests/test_arreio_presenca_rotas.py`
Rotas: `POST /novo_ponto` (`views/admin.py:97`, responde JSON) e
`POST /equipe/api/sync-ponto` (`equipe_views.py:1213`, recebe JSON com
`data_processamento`)

**Comportamento afirmado.**
- (a) Dois `POST /novo_ponto` no mesmo (funcionário, data, obra) — 4h de manhã e 4h
  à tarde: a SOMA dos `CustoObra` `categoria='PONTO_ELETRONICO'` do dia corresponde
  às 8h lançadas. Hoje: 1 linha de R$ 62,00 para 8h.
- (b) POST que só corrige o horário do MESMO registro continua produzindo UMA linha
  (a idempotência do p1 não pode ser desfeita ao consertar (a)).
- (c) Sync do plano: semeia `RegistroPonto` `tipo_registro='atestado'` sem hora (o
  que `ponto_service.py:330-360` cria) + `Allocation`/`AllocationEmployee` do dia,
  posta `/equipe/api/sync-ponto` com essa data, e afirma que `tipo_registro`
  CONTINUA `'atestado'` e `horas_trabalhadas` continua 0 — hoje `models.py:4602-4616`
  sobrescreve para `'trabalho_normal'` com 8h.
- (d) Após sync que CRIA registro (`models.py:4623-4642`), afirma que existe
  `CustoObra` do dia — hoje não existe, porque nada em `models.py` emite
  `ponto_registrado`.

**Por que o atual não pegava.** `tests/test_p1_fallback_e_idempotencia.py:119-135`
(`_bater_ponto`) busca o `RegistroPonto` já semeado e **muta** esse objeto — por
construção nunca existe mais de um registro no dia, que é a precondição do defeito —,
emite o evento à mão pulando `POST /novo_ponto` inteiro, e afirma `len(custos) == 1`
(`:152`), asserção que o defeito **satisfaz**. Uma linha de custo é o sintoma, não a
cura: o que faltava era relacionar horas GRAVADAS com horas CUSTEADAS.

**Riscos → mitigação.**
1. `processar_lancamentos_automaticos` (`models.py:4745`) usa `date.today()-1`
   quando não recebe data → SEMPRE mandar `data_processamento` explícito, ancorado
   na semente.
2. A rota é `@admin_required` e varre TODOS os funcionários ativos do tenant → o
   tenant do teste precisa nascer isolado (`com_fatos=False`), senão a asserção pega
   funcionário alheio ao cenário.

**Marcação.** (a), (c) e (d) entram `xfail(strict=True)` — dependem de A10 e A16-a.

- [x] **Step 1:** escrever os quatro casos
- [x] **Step 2:** rodar — (b) verde, (a)/(c)/(d) xfail
- [x] **Step 3:** commit — `test(arreio): presença por rota — /novo_ponto e sync do plano`

**Status: ✅ entregue em `a9bf2fd9`.** Sem desvio. Os três xfail são o checklist de
B1.6-B1.11 — quando aquelas Tasks entrarem, é aqui que o XPASS(strict) cobra a
remoção da marca.

---

### Task B0.5: `tests/test_arreio_aprovacao_proposta_rotas.py` — congelar o que hoje funciona

**Files:** Create `tests/test_arreio_aprovacao_proposta_rotas.py`
Rotas: `POST /propostas/aprovar/<id>` (`propostas_consolidated.py:2332`) e
`POST /propostas/cliente/<token>/aprovar` (`propostas_consolidated.py:2507`, sem login)

**Comportamento afirmado.**
- (a) Aprovar proposta de valor > 0 pela rota: Obra materializada,
  `ItemMedicaoComercial` criado, `LancamentoContabil` + 2 `PartidaContabil`
  (1.1.02.001 × 4.1.01.001) somando o valor, `ServicoObraReal` semeado e Lead fechado.
- (b) Aprovar proposta de valor ZERO pela mesma rota: `ServicoObraReal` existe —
  hoje **não existe**, porque `handlers/propostas_handlers.py:378-385` dá `return`
  antes de `_semear_servicos_reais`/`_fechar_lead_da_proposta`, que só aparecem em
  `:427-428` e `:493-494`.
- (c) Reaprovar (revisão sem mudança de valor) não duplica lançamento contábil.
- (d) Aprovar pela rota do cliente com token de outro tenant: 404 e nada gravado.

**Por que vale.** É a única superfície do arreio onde o dinheiro hoje **chega** no
caminho principal — cobrir serve para congelar o que funciona antes de B3 mexer no
branch de valor zero. E o caminho de valor zero é o mesmo que
`services/importacao_fisico_financeiro.py:572-578` usa com `skip_contabil=True`:
cobri-lo pela rota cobre a importação de graça, sem montar planilha.

**Risco → mitigação.** As duas rotas são donas da transação e emitem com
`raise_on_error=True` (`propostas_consolidated.py:2360-2371` e `:2540-2551`):
exceção em handler faz rollback TOTAL e a rota devolve 302 com flash.
`assert status_code == 302` não prova nada — só o banco prova.

**Marcação.** (b) entra `xfail(strict=True, reason='A14')`.

- [x] **Step 1:** escrever os quatro casos
- [x] **Step 2:** rodar — (a), (c), (d) verdes; (b) xfail
- [x] **Step 3:** commit — `test(arreio): aprovação de proposta por rota`

**Status: ✅ entregue em `d3ea0471`.** Sem desvio. O xfail de (b) é o checklist de
B3.5 (A14).

---

### Task B0.6: apertar os `<= 1` do p1 e rebaixar os testes textuais

**Files:** Modify `tests/test_p1_dedup_cross_origem.py` (`:112`, `:128`, `:151-165`);
`tests/test_p5_aprovacao_semeia_obra.py:210-220`;
`tests/test_p4_formula_unica_progresso.py:133-177`

**Comportamento novo.** As duas asserções `<= 1` viram `== 1`, com mensagem que
distingue zero de dois (`'perdeu o custo'` × `'contou duas vezes'`) — foi o `<=` que
deixou o zero passar. Os testes de leitura de texto são **MANTIDOS e rebaixados**:
renomeados para deixar claro que são guarda-de-forma contra reversão do padrão, com
docstring apontando em qual arquivo do arreio mora a prova de comportamento.

**Por que manter os textuais.** Custam milissegundos e pegam uma classe real —
alguém reintroduzir a chamada direta "só aqui", que foi como a assimetria nasceu
(está escrito na mensagem do commit `31aed041`). O erro deles não é existir, é serem
os ÚNICOS. O que não pode continuar é a docstring mentindo:
`tests/test_p5_aprovacao_semeia_obra.py:210` diz cobrir o caminho de importação e só
faz `texto.count(...) == 2`.

> **Nota de contradição (ver §9, nº 1).** O recorte de A05 propõe apagar os textuais
> de `:151-165`. Adotamos a posição de B0 — manter e rebaixar.

**Risco → mitigação.** Apertar para `== 1` antes de B1 deixa dois testes vermelhos →
esta Task roda **por último no bloco**, e só depois que a prova de comportamento
existir é que faz sentido rebaixar a de forma. Se B0 entrar sozinho, os dois `== 1`
recebem `xfail(strict=True, reason='A05')` como o resto.

- [x] **Step 1:** trocar `<=` por `==` com mensagens distintas
- [x] **Step 2:** renomear e corrigir docstrings dos três arquivos textuais
- [x] **Step 3:** `bash run_tests.sh --gate`
- [x] **Step 4:** commit — `test(p1): asserção de igualdade no custo; guardas textuais rebaixadas a guarda-de-forma`

**Status: ✅ entregue em `6969a912`.** Sem desvio. Vale registrar que a posição
adotada na §9 nº 1 (manter e rebaixar, em vez de apagar) sobreviveu à execução: os
textuais continuam custando milissegundos e continuam pegando a classe de regressão
que o teste de rota só detecta **depois** do efeito.

---

## 4. B1 — Parar de perder dado

**Por que existe.** Os três lugares da §1. É o único bloco em que há dinheiro
saindo do sistema hoje, medido: R$ 124,00 por mensalista por dia de RDO por duas
das três rotas, metade do custo do dia em ponto partido, e atestado virando dia
trabalhado.

**O que entrega.** O custo do RDO volta a existir para mensalista e horista com o
evento virando mecanismo canônico; o ponto manual para de sobrescrever a si mesmo;
o plano para de destruir ausência classificada; e os dois vazamentos de tenant
sobreviventes do p1 — reclassificados ao abrir o código — mais a dedup de NF que
nunca existiu.

**Esforço:** G. **Migração:** nenhuma. **Depende de:** B0 (para ser verificável).

---

### 4.1 A05 — o custo do RDO volta a existir, e o evento para de calcular valor sozinho

O defeito é maior do que o relatado e a decisão a/b se resolve por **leitura**, não
por negócio. O que a leitura decide:

- `services/rdo_custos.gerar_custos_mao_obra_rdo` (`:316`) **não grava `CustoObra`**,
  que é lida pelo dashboard de custos inteiro (`custos_views.py:42,56,87,102,156,436`),
  por `relatorios_funcionais.py:265,376,421` e por `utils.py:522`. Adotar "o serviço é
  canônico" esvaziaria essas telas.
- Ela tem dois portões que o evento não tem: `_tenant_is_v2`
  (`services/rdo_custos.py:337-341`) devolve 0 para tenant v1, e
  `status != 'Finalizado'` (`:330`). O evento usa `force_v2=True`
  (`event_manager.py:855`) e atende v1.
- Em compensação ela tem o que falta ao evento: a **fórmula certa** por tipo de
  remuneração com rateio proporcional entre RDOs do mesmo dia, persistida em
  `RDOCustoDiario` por `services/custo_funcionario_dia.calcular_custo_funcionario_no_rdo`
  (`:54-125`) e `gravar_custo_funcionario_rdo` (`:200`), e a **chave de idempotência
  certa** (`origem_tabela='rdo_custo_diario'`, `origem_id=RDOCustoDiario.id`,
  `services/rdo_custos.py:414-418`) — exatamente a que `remover_custos_rdo` sabe
  apagar (`:110-111`, `:131-140`).

**Decisão adotada: (a) o evento é canônico — com a condição de que
`lancar_custos_rdo` PARE de calcular valor e passe a LER `RDOCustoDiario`.** Escrever
o fallback horista à mão dentro do handler seria a sexta cópia da fórmula, o mesmo
pecado que o p4 acabou de consertar no progresso. E adotar a chave `rdo_custo_diario`
torna os dois mecanismos mutuamente idempotentes: quem rodar primeiro vence, o
segundo encontra `ja` e sai. É isso que permite apagar as chamadas diretas sem medo.

**Quantos caminhos existem hoje: seis vivos**, e nenhum faz a mesma coisa —
`views/rdo.py:1698` (só emite), `:2066` (chama o serviço em `:2151`/`:2157` **e**
emite em `:2164`), `:2766` (chama em `:3418`/`:3425` e **não emite**), `:3612` (chama
em `:4481`/`:4490` e emite em `:4500`), `crud_rdo_completo.py:555` (só emite, payload
truncado, **e emite ANTES do commit** de `:618`) e `rdo_editar_sistema.py:164` (grava
`RDOCustoDiario` em `:544` e emite em `:557`, payload truncado).
`crud_rdo_completo.py:475` é **código morto** — a rota foi removida e `main_bp` vence
`/rdo/salvar` (`crud_rdo_completo.py:236-243`).

**Esforço:** G.

---

### Task B1.1: o handler passa a ler `RDOCustoDiario` em vez de calcular valor

**Files:** Modify `event_manager.py` — `lancar_custos_rdo`: inserir logo após o guard
de `mao_obra_registros` (`:685-688`) e antes de `data_rdo = rdo.data_relatorio`
(`:690`); depois substituir `:729-733`; depois `:959`

**Comportamento novo.**
1. Antes do laço, o handler chama
   `services.custo_funcionario_dia.gravar_custo_funcionario_rdo(rdo, admin_id)` —
   idempotente (upsert de `RDOCustoDiario`, `services/custo_funcionario_dia.py:200-305`)
   e o único lugar do código que conhece a fórmula por tipo de remuneração mais o
   rateio quando o funcionário aparece em vários RDOs do mesmo dia. A partir daí
   existe um `RDOCustoDiario` por (rdo, funcionário) com `componente_folha` correto
   para diarista **e** para mensalista.
2. `event_manager.py:729-733` (comentário `# Custo base: valor_diaria — sem fallback
   para horário` + `valor_diaria`/`continue`) sai. Entra a leitura do `RDOCustoDiario`
   do par (`rdo.id`, `func_id`) — `services/rdo_custos._custo_diario_rdo(rdo.id, func_id)`
   (`services/rdo_custos.py:76-86`) já faz exatamente essa consulta com
   `tipo_lancamento='rdo'`. Passam a existir `valor_folha`, `valor_va` e `valor_vt`.
   Se a linha não existir (defensivo), calcular na hora com
   `calcular_custo_funcionario_no_rdo(funcionario, horas_do_func_neste_rdo,
   horas_totais_do_dia, data_rdo)` — **nunca reescrevendo a fórmula**.
3. O `continue` passa a ser `if valor_folha <= 0 and valor_va <= 0 and valor_vt <= 0`,
   espelhando `services/rdo_custos.py:443-447`.
4. `valor_total_custos += valor_diaria` (`:959`) vira `+= valor_folha`.

**Teste que prova:** B0.3 casos (a)/(b)/(g) e `tests/test_a05_custo_mensalista_por_rota.py`
(Task B1.5) caso 1 — 1 `CustoObra` para (funcionário, DATA) com valor igual ao
`componente_folha` que `calcular_custo_funcionario_no_rdo(f, 8.0, 8.0, DATA)`
devolve (compara-se contra a função, não contra literal — a fórmula fica num lugar só).

**Riscos → mitigação.**
1. O `continue` de `:733` está ACIMA do laço de benefícios (`:889-957`): se continuar
   disparando por folha zerada, VA/VT continuam morrendo → o novo `continue` exige os
   três zerados.
2. `gravar_custo_funcionario_rdo` faz `db.session.commit()` interno
   (`services/custo_funcionario_dia.py:290`); em `crud_rdo_completo.py:592` o evento é
   emitido com `rdo.status='Finalizado'` ainda pendente → corrigir junto na Task B1.4.
3. **Armadilha do decorador:** NÃO extrair helper novo colando-o entre
   `@event_handler('rdo_finalizado')` (`event_manager.py:649`) e
   `def lancar_custos_rdo` (`:650`) — o decorador adota a função imediatamente abaixo.

- [x] **Step 1:** escrever/rodar o teste da Task B1.5 e vê-lo VERMELHO nos quatro casos que hoje dão zero
- [x] **Step 2:** as quatro edições, na ordem em que o dado flui
- [x] **Step 3:** rodar B0.3 e B1.5 — casos 1, 3 e 4 ficam verdes; o custo ainda não é removível
- [x] **Step 4:** commit — `fix(rdo): handler de custo lê RDOCustoDiario em vez de recalcular por valor_diaria`

**Status: ✅ entregue em `cefba5e7`, JUNTO da Task B1.2. Desvio deliberado de
recorte** — ver o Status da B1.2 para o motivo. O Step 1 foi cumprido pelo arreio
B0.3, não pelo arquivo `tests/test_a05_custo_mensalista_por_rota.py`: o arreio já
posta nas rotas com mensalista e afirma sobre `GestaoCustoFilho`, que é exatamente o
que aquele arquivo faria. **Esse arquivo não será criado** — ver o Status da B1.5.

---

### Task B1.2: chave de origem `rdo_custo_diario` + guard inverso do ponto, no MESMO commit

**Files:** Modify `event_manager.py` — chamadas a `registrar_custo_automatico` em
`:860-861` (folha) e `:941-942` (VA/VT); e o guard inverso em `:379-390`

**Comportamento novo.** `origem_tabela='rdo_mao_obra'` / `origem_id=rdo.id` viram
`origem_tabela='rdo_custo_diario'` / `origem_id=custo_dia.id`, e
`f'rdo_mao_obra_{tag.lower()}'` vira `f'rdo_custo_diario_{tag.lower()}'`. Passa a ser
exatamente a chave que `remover_custos_rdo` já sabe apagar
(`services/rdo_custos.py:111`, `:131-140`), que `cancelar_custos_rdo` já sabe cancelar
(`:203-212`) e que `gerar_custos_mao_obra_rdo` já usa (`:398-401`, `:414-418`).

No mesmo commit, o guard inverso do ponto (`event_manager.py:379-390`) troca
`GestaoCustoFilho.origem_tabela == 'rdo_mao_obra'` por
`.in_(['rdo_mao_obra','rdo_custo_diario'])`.

**Por que isso corrige o ciclo de edição.** Hoje o handler grava
`origem_id=rdo.id` (`event_manager.py:860-861`) e `remover_custos_rdo`
(`services/rdo_custos.py:122-129`) procura `origem_id IN [RDOMaoObra.id…]` — espaços
de id diferentes. **Nenhum filho criado pelo evento é removível quando o RDO é
editado** (`crud_rdo_completo.py:284`, `rdo_editar_sistema.py:357`,
`services/rdo_assinatura.py:234`). Editar horas nunca corrige o custo.

**Teste que prova:** B1.5 caso 2 (reexecução) mais um caso novo — ponto criado APÓS o
POST de finalizar, para diarista: continua havendo 1 filho só.

**Risco → mitigação.** Separar as duas edições abre uma janela em que batida tardia de
diarista volta a duplicar → **os dois no mesmo commit, sem exceção**.

- [x] **Step 1:** as duas trocas de chave + o `in_` do guard inverso
- [x] **Step 2:** teste de batida tardia
- [x] **Step 3:** commit — `fix(rdo): chave de origem rdo_custo_diario no handler e no guard inverso do ponto`

**Status: ✅ entregue em `cefba5e7`, no MESMO commit da B1.1. Desvio deliberado de
recorte, e o motivo é o mesmo que a própria Task argumenta para as suas duas
edições internas:** a troca de chave é o que torna os dois mecanismos **mutuamente
idempotentes** — com `origem_tabela='rdo_custo_diario'` e `origem_id=RDOCustoDiario.id`,
quem rodar primeiro vence e o segundo encontra `ja` e sai. Separadas, a B1.1 sozinha
faria o evento e a chamada direta lançarem **em cima um do outro** — abrindo, entre os
dois commits, exatamente a dupla contagem que o p1 existiu para fechar. O plano
previa a janela entre B1.2 e B1.3; não previa esta, entre B1.1 e B1.2.

**Efeito colateral verificado, e é o retorno do investimento do B0:**
`test_mensalista_gera_custo_pela_rota_de_finalizar` e
`test_custo_diario_gravado_implica_lancamento` deram **XPASS(strict)** — o mecanismo
cobrando a remoção da marca obsoleta. As duas paridades (`/rdo/finalizar` e
`/rdo/editar` contra a referência) passaram a fechar em R$ 124,00.

**Terceiro achado, este de construção dos testes de paridade do B0.3:** eles usavam
DOIS tenants no mesmo `app_context`, e o segundo POST não completava. Acusavam
R$ 0,00 na presença **e** na ausência do defeito — teriam ficado verdes por engano.
Corrigido para um tenant e duas datas. É a segunda vez na mesma rodada que "dois
cenários no mesmo `app_context`" produz teste vacuoso; está virando padrão de erro.

---

### Task B1.3: `existe_ponto_no_dia` só conta ponto produtivo; o guard cobre só `CustoObra`; resíduo removível

**Files:** Modify `services/rdo_custos.py` (`existe_ponto_no_dia`, `:50-71`;
`remover_custos_rdo`, `:121-140`); `event_manager.py` (guard de `:722`; upsert de
`:788-812`)

**Comportamento novo.**

1. **`existe_ponto_no_dia` passa a exigir ponto PRODUTIVO.** Hoje ela só faz
   `filter_by(funcionario_id, data, admin_id)` (`services/rdo_custos.py:50-71`).
   Acrescentar `RegistroPonto.horas_trabalhadas > 0` e `RegistroPonto.obra_id.isnot(None)`
   — as duas condições sob as quais `calcular_horas_folha` de fato gera custo
   (`event_manager.py:328-330` e `:496-498`). Uma linha de `falta`/`falta_justificada`/
   `feriado` (`models.py:779`) deixa de suprimir o custo do RDO.
2. **O guard `existe_ponto_no_dia` de `event_manager.py:722` sai de cima do laço e
   passa a cobrir APENAS o bloco de `CustoObra` (`:788-812`).** Os blocos de
   `GestaoCustoFilho` (`:826-885`) e de VA/VT (`:889-957`) passam a decidir pelas suas
   próprias chaves largas do p1 Step D, que já cruzam origem (`:826-847` filtra por
   `data_referencia` + `entidade_id` + categoria SALARIO/MAO_OBRA_DIRETA + `admin_id`,
   **sem filtro de origem**). Para diarista com ponto, a chave larga acha o filho do
   ponto e pula — idêntico a hoje. Para **mensalista** com ponto, o ponto nunca criou
   filho (`calcular_horas_folha` só cria `GestaoCustoFilho` no ramo diarista,
   `event_manager.py:404-416`; o ramo horista/mensalista, `:527-563`, grava **apenas**
   `CustoObra`), a chave larga não acha nada e o RDO lança.
3. **`CustoObra` vira upsert** em vez de skip (`:788` / `:794`), no mesmo formato do
   upsert do ponto (`:531-544`). Para `tipo_remuneracao_snapshot == 'diaria'`,
   `quantidade=1` e `valor_unitario=valor_folha`; caso contrário
   `horas_trabalhadas=custo_dia.horas_normais`, `quantidade=horas_normais`,
   `valor_unitario=custo_dia.custo_hora_normal`. A descrição deixa de dizer
   `'1 diária'` fixo (`:782`) e passa a `'1 diária'` ou `'{horas}h'`, como
   `services/rdo_custos.py:452-459` já faz.
4. **`remover_custos_rdo` alcança o resíduo legado.** Terceira cláusula:
   `origem_tabela IN ('rdo_mao_obra','rdo_mao_obra_va','rdo_mao_obra_vt')` E
   `origem_id == rdo.id` E `admin_id == admin_id` E
   `data_referencia == rdo.data_relatorio`. Sem isso, os filhos já gravados em
   produção pelo evento nunca saem e a chave larga os encontra para sempre.

**Teste que prova:** B1.5 casos 3 (mensalista com ponto → ao menos 1 filho; hoje ZERO)
e 4 (falta no dia → 1 `CustoObra` de RDO; hoje ZERO).

**Riscos → mitigação.**
1. A chave larga de `:826-847` **só** é mais precisa que `existe_ponto_no_dia` porque
   não filtra origem. Se alguém "melhorar" essa consulta acrescentando
   `origem_tabela == 'rdo_custo_diario'`, a dupla contagem diarista × ponto volta na
   hora → deixar escrito no comentário do bloco que a ausência de filtro é intencional.
2. `existe_ponto_no_dia` é compartilhada — também chamada por
   `gerar_custos_mao_obra_rdo` (`:368`), pela verificação pós-fase-2 da migração 154
   (`migrations.py:13996`) e por `scripts/migrar_rdos_rascunho_legados.py:135`. Todos
   querem a mesma semântica → mudar a função é o certo, mas **não introduzir parâmetro
   opcional com default diferente**, que é como esse tipo de guard se bifurca.
3. Sem o recorte por `data_referencia` na cláusula nova, um filho legítimo de OUTRO
   RDO cujo `RDOMaoObra.id` coincida numericamente com este `rdo.id` seria removido →
   não afrouxar.
4. Relatórios que somam `CustoObra.horas_trabalhadas` passarão a ver horas onde viam
   zero (hoje `Decimal('0')` chumbado em `:803`) — é a correção pretendida, mas
   conferir `relatorios_funcionais.py` antes de considerar surpresa.

- [x] **Step 1:** `existe_ponto_no_dia`
- [x] **Step 2:** mover o guard e virar `CustoObra` em upsert
- [x] **Step 3:** cláusula de resíduo em `remover_custos_rdo`
- [x] **Step 4:** rodar B1.5 casos 3 e 4
- [x] **Step 5:** commit — `fix(rdo): guard de ponto só cobre CustoObra; ponto não-produtivo deixa de suprimir custo`

**Status: ✅ entregue em `060146ac`, junto da B1.4.** As quatro edições saíram como
planejadas. Duas notas de execução:

1. **O item 3 (upsert de `CustoObra`) valia mais do que o recorte dizia.** O
   `if not existing` deixava o custo velho intacto quando as horas eram corrigidas —
   **editar o RDO nunca alcançava a linha**. Estava escrito aqui como "upsert em vez
   de skip", o que soa cosmético; é correção de dado velho.
2. **A cláusula de resíduo (item 4) tem alcance maior que o descrito.** Antes da
   B1.2, o handler gravava `origem_id=rdo.id` num campo comparado contra ids de
   `RDOMaoObra`/`RDOCustoDiario` — espaços de id diferentes, nenhum filho criado pelo
   evento era removível. **Todo banco que já rodou tem essas linhas**, e sem a
   cláusula a chave larga as encontra para sempre e o custo velho congela no lugar do
   certo. O recorte por `data_referencia` ficou como o plano manda, e é ele que
   impede apagar filho de OUTRO RDO cujo `RDOMaoObra.id` coincida com este `rdo.id`.

---

### Task B1.4: payloads com `obra_id`, handler autossuficiente, emit pós-commit

**Files:** Modify `crud_rdo_completo.py` (emit `:592`, commit `:618`; e `:475` com
comentário); `rdo_editar_sistema.py:557`; `event_manager.py` (`recalcular_medicao_apos_rdo`,
`:1526-1531`)

**Comportamento novo.**
1. Os payloads passam a `{'rdo_id': rdo.id, 'obra_id': rdo.obra_id,
   'data_relatorio': str(rdo.data_relatorio)}`, igual a `views/rdo.py:1767-1771`.
2. O bloco do emit de `crud_rdo_completo.py:592` sai de antes do cálculo de
   produtividade e vai para DEPOIS do `db.session.commit()` de `:618`, como fazem os
   outros cinco caminhos.
3. `recalcular_medicao_apos_rdo`: quando `data.get('obra_id')` vier vazio, resolver a
   partir do RDO — `RDO.query.filter_by(id=data.get('rdo_id'), admin_id=admin_id).first()`
   e usar `.obra_id`. Só desiste (com o warning atual de `:1530`) se nem `rdo_id`
   houver.
4. `crud_rdo_completo.py:475` recebe o payload corrigido **por consistência**, com
   comentário registrando que a função NÃO é despachada. Não apagar: `:239-243` diz
   que está reservada para o rollout do Módulo 07, e a telemetria `[LEGACY-RDO]` nunca
   pôde disparar — ausência de log aqui não é prova de desuso.

**Teste que prova:** B0.3 caso (c) — o payload carrega `obra_id`, afirmado pelo
EFEITO (`ItemMedicaoComercial.valor_executado_acumulado` e `ContaReceber`
`origem_tipo='OBRA_MEDICAO'`), nunca lendo o dict. Mais B1.5 caso 5.

**Riscos → mitigação.**
1. `EventManager.emit` repassa `data` INTACTO (`event_manager.py:46`) — corrigir
   apenas os payloads deixa o próximo emissor livre para repetir o erro em silêncio →
   fazer **as duas coisas**: payload explícito E handler autossuficiente.
2. A resolução no handler tem que filtrar por `admin_id`, senão vira leitura
   cross-tenant.
3. `crud_rdo_completo.py:592` é o único emissor pré-commit: movendo-o, o `except` da
   rota (`:621-623`) volta a poder desfazer de verdade o `status='Finalizado'`.

- [x] **Step 1:** os três payloads
- [x] **Step 2:** reposicionar o emit de `crud_rdo_completo.py` para depois de `:618`
- [x] **Step 3:** fallback autossuficiente em `recalcular_medicao_apos_rdo`
- [x] **Step 4:** commit — `fix(rdo): payload com obra_id nos três emissores e handler de medição autossuficiente`

**Status: ✅ entregue em `060146ac`, junto da B1.3.** Sem desvio de recorte. O risco 1
("corrigir apenas os payloads deixa o próximo emissor livre para repetir o erro em
silêncio") **não é hipotético e merece ficar registrado como fato**: foi exatamente
assim que dois payloads truncados sobreviveram a um gate verde. Por isso as duas
coisas saíram juntas — payload explícito **e** handler autossuficiente.

O Step 2 fechou o único emissor pré-commit dos seis caminhos: o handler via um RDO
que podia não existir, e o `except` da rota não desfazia mais nada porque o handler
já havia commitado por dentro. Terceiro XPASS(strict) da rodada aqui — a sentinela da
medição —, marca removida.

---

### Task B1.5: `views/rdo.py` consolida — chamadas diretas saem, `/rdo/salvar` passa a emitir

**Files:** Modify `views/rdo.py` — `atualizar_rdo` `:2155-2159`;
`salvar_rdo_flexivel` `:4488-4493`; `rdo_salvar_unificado` `:3416-3426`.
Test: ~~`tests/test_a05_custo_mensalista_por_rota.py`~~ — **ver a nota abaixo.**

> **Nota de 04/08 — o arquivo de teste desta Task NÃO será criado.** O arreio B0.3
> (`tests/test_arreio_custo_rdo_rotas.py`, commit `35975e7a`) já posta nas rotas com
> funcionário mensalista e afirma sobre `GestaoCustoFilho`/`CustoObra`/`RDOCustoDiario`
> — que é exatamente o que os cinco casos da tabela abaixo fariam, e pela mesma porta
> (a rota). Escrever o arquivo separado seria uma segunda cópia da mesma prova, com o
> risco conhecido de as duas divergirem. **A tabela dos cinco casos continua valendo
> como especificação**; o que muda é onde ela vive. Os casos 1-4 já estão cobertos;
> confirmar que o caso 5 (medição + `ContaReceber`) tem equivalente no arreio antes de
> fechar esta Task — se não tiver, ele entra em `tests/test_arreio_custo_rdo_rotas.py`,
> não em arquivo novo.
>
> **Estado das três linhas, conferido contra `060146ac`:** as três chamadas diretas
> seguem no lugar — `views/rdo.py:2157`, `:3425` e `:4490`. Nada desta Task foi feito.

**Comportamento novo.**
1. Remover as duas chamadas diretas a `gerar_custos_mao_obra_rdo` (`:2157`, `:4490`).
   Ambas as rotas já emitem logo em seguida (`:2164`, `:4500`) e o handler passa a
   fazer tudo o que elas faziam, com a mesma chave de idempotência. As chamadas a
   `gravar_custo_funcionario_rdo` (`:2151`, `:4481`) podem ficar — são idempotentes e
   o handler as repete.
2. `rdo_salvar_unificado` (`POST /rdo/salvar`, `:2766`) troca a chamada de `:3425` por
   `EventManager.emit('rdo_finalizado', {...}, admin_id_correto)`. É o único caminho
   vivo que gera custo e nunca recalcula medição — a situação que o Step E dizia ter
   eliminado.

**Teste — o arquivo `tests/test_a05_custo_mensalista_por_rota.py`.** Semente própria
(NÃO usar `dois_tenants` sem ajuste — planta `RegistroPonto` na data em
`tests/helpers_tenant.py:88`): admin `versao_sistema='v2'`, cliente, obra, e um
`Funcionario(tipo_remuneracao='salario', salario=3000.0, valor_va=20.0, valor_vt=10.0)`
com `valor_diaria` no default 0.0. `DATA = date(2026, 6, 15)` e **todas** as consultas
filtram por `data == DATA` / `data_referencia == DATA` — nunca janela até
`date.today()`. RDO com `RDOMaoObra(horas_trabalhadas=8.0)`. Login por `cliente_de` e
`POST /rdo/finalizar/{rdo.id}`. Cinco casos:

| # | Cenário | Asserção (estado do banco) |
|---|---|---|
| 1 | Sem ponto no dia | 1 `CustoObra`(rdo_id, func, DATA, admin) com valor == `calcular_custo_funcionario_no_rdo(f, 8.0, 8.0, DATA)`; 1 `RDOCustoDiario` com `componente_folha > 0`; 1 `GestaoCustoFilho` SALARIO/MAO_OBRA_DIRETA com `origem_tabela=='rdo_custo_diario'` e `origem_id==custo_dia.id`; 1 filho ALIMENTACAO R$ 20,00 e 1 TRANSPORTE R$ 10,00 |
| 2 | Re-POST na mesma rota | as quatro contagens idênticas |
| 3 | Com `RegistroPonto(trabalhado, 8h, obra_id)` | exatamente 1 `CustoObra` (a do ponto, `PONTO_ELETRONICO`, `rdo_id` nulo) E ao menos 1 `GestaoCustoFilho` na data (**hoje ZERO**) |
| 4 | Com `RegistroPonto(falta, 0h, obra_id=None)` | 1 `CustoObra(rdo_id=...)` (**hoje ZERO**) |
| 5 | Obra com `ItemMedicaoComercial(servico=S, 10000)` + `RDOServicoSubatividade(S, 50%)` | `valor_executado_acumulado == 5000.00` e existe `ContaReceber(origem_tipo='OBRA_MEDICAO', origem_id=obra.id)` |

**Por que o textual não pegava:** `tests/test_p1_dedup_cross_origem.py:151-165` prova
que a string existe; os três testes que chamam o handler
(`tests/test_agrupamento_diarias_rdo.py:223`, `tests/test_auto_link_servico_rdo.py:226`,
`tests/test_fase5_rdo_ciclo_vida.py:605`) usam todos `tipo_remuneracao='diaria'` com
`valor_diaria` preenchido — o único perfil que continuou funcionando.

**Riscos → mitigação.**
1. Remover as chamadas diretas ANTES da Task B1.2 significa perder a chave que
   `remover_custos_rdo` reconhece → **esta Task é a última do A05**.
2. `POST /rdo/salvar` também CRIA RDO novo. O handler não tem portão de status (ao
   contrário de `services/rdo_custos.py:330`), mas esse portão é vazio na prática —
   todo RDO nasce `status='Finalizado'` (`views/rdo.py:1721-1723`). Conferir que o
   `rdo` de `:3425` já tem `obra_id` e `data_relatorio` no ponto do emit.
3. Dashboards de custo sobem de valor no dia do deploy: mensalistas que nunca geraram
   custo de RDO passam a gerar → é a correção, mas **anunciar**. `scripts/medir_producao`
   (commit `d99ce7e2`) já existe para tirar o antes/depois por tenant; rodar antes do
   deploy e guardar o número.
4. Tenant v1 perde custo se alguém "simplificar" o handler chamando
   `gerar_custos_mao_obra_rdo` → não delegar a ESCRITA, só o CÁLCULO. Deixar escrito no
   comentário do handler, porque é exatamente o tipo de refactor que parece limpeza.

- [x] **Step 1:** remover as duas chamadas diretas
- [x] **Step 2:** converter `:3425` em emit
- [x] **Step 3:** rodar B0.3 (os xfail (a)/(b)/(g) **já viraram XPASS em `cefba5e7`/`060146ac`** e as marcas já saíram; o que se confere aqui é que continuam verdes)
- [x] **Step 4:** `bash run_tests.sh --gate`
- [x] **Step 5:** commit — `fix(rdo): mecanismo único de custo — evento canônico, chamadas diretas removidas`

**Status: ✅ entregue JUNTO da B1.5b, no mesmo commit — e essa fusão não é
preferência de recorte, é a única forma correta.**

**🔴 Desvio que corrige o próprio plano: B1.5 sozinha é uma REGRESSÃO DE
DINHEIRO.** A §11.3 dizia que a B1.5b "depende de" B1.5. Depende — mas separá-las
por um commit deixa o parque com custo a menos, medido pelo arreio no instante
seguinte à remoção das chamadas diretas:

```
mensalista, 4h + 4h em dois RDOs do mesmo dia
  antes da B1.5:  2 linhas × R$ 62,00 = R$ 124,00   ✅
  com B1.5 só:    1 linha  × R$ 62,00 = R$  62,00   ❌ metade do dia some
```

A causa é a troca de guarda que a B1.5 provoca sem dizer. Enquanto havia chamada
direta, quem criava as linhas era o guard de chave ESTREITA do serviço
(`origem_id=RDOCustoDiario.id`, um por RDO). Removidas as chamadas, o único
escritor passa a ser o handler, cujo guard é o de chave LARGA (`data` +
`funcionário` + categoria, sem origem) — e ele colapsa todos os RDOs do dia num
lançamento só. **A B1.5 não muda quem escreve o custo; ela muda qual guard
decide, e os dois guards não são equivalentes.** Isso não estava no recorte, e é o
tipo de coisa que só aparece medindo.

**Os três Steps saíram como escritos** (as duas chamadas diretas fora, `:3425`
convertida em emit pós-commit com payload completo). O que a execução acrescentou
está na B1.5b.

**Terceiro teste vacuoso da mesma família, achado aqui.**
`test_rdo_salvar_unificado_*` afirmava no nome que a rota "gera custo" e **nunca
conferiu**: ele postava com as chaves `cron_tarefa_*`, que esta rota não parseia
(`views/rdo.py:3292-3316` lê `funcionario_<id>_nome`/`_horas`), então o RDO nascia
sem mão de obra e não havia custo nenhum para gerar. A sentinela sobrevivia por
ausência de fato, não por ausência de emit. Corrigido com `flat_func=True` em
`form_rdo` e um assert de custo. **Padrão que já apareceu três vezes nesta rodada:
o teste postava num formulário que a rota não lê, e media o vazio.**

**Armadilha de rota registrada de passagem:** `POST /rdo/salvar` aborta em
`views/rdo.py:3199` (flash + redirect) quando o tenant não tem nenhum `Servico` —
**depois** de já ter criado e commitado o RDO, e **antes** de parsear a mão de obra.
Sobra um RDO órfão com `status='Finalizado'`, zero mão de obra e zero subatividade,
e a rota responde 302 como se nada houvesse. Não foi corrigido (fora do recorte);
está congelado no docstring de `_servico_do_tenant` no arreio.

**Dívida da B1.2 achada e paga aqui.** `tests/test_auto_link_servico_rdo.py`
procurava a chave de origem ANTIGA (`'rdo_mao_obra'`/`rdo.id`) e estava
**vermelho desde `cefba5e7`** — o gate não foi re-rodado naquele commit e ninguém
viu. Confirmado rodando o teste com as mudanças de hoje guardadas no stash: já
falhava antes. Passou a consultar pela linha de `RDOCustoDiario` em vez de chumbar
a string, para seguir a chave em vez de congelá-la.

---

### Task B1.5b: a idempotência do custo de mão de obra para de ignorar mudança de valor

> **Esta Task não existia no plano de 04/08.** Nasceu do arreio B0.3 (commit
> `ddbbc1b7`), que a achou no lugar de um defeito meu que não existia. É o último
> `xfail` vivo do arreio e o que resta de A05 depois da B1.5.

**Files:** Decidido pelo Step 1 — `event_manager.py` (`lancar_custos_rdo`, guard
`existing_filho` `:933-948` e o `else` de `:976`) e/ou `services/rdo_custos.py`
(`gerar_custos_mao_obra_rdo`, guard `ja` `:460-467`).
Test: `tests/test_arreio_custo_rdo_rotas.py:317`
(`test_o_razao_acompanha_o_recalculo_cruzado_da_diaria`, hoje `xfail(strict=True)`)

**O defeito, medido — não inferido.** Diarista de R$ 150,00 em dois RDOs do mesmo dia:

```
RDOCustoDiario   = [75,00 · 75,00]  → R$ 150,00   uma diária        ✅
GestaoCustoFilho = [150,00 · 75,00] → R$ 225,00   uma diária e meia ❌
```

A diária **tem teto** — é uma por dia, rateada entre os RDOs
(`services/custo_funcionario_dia.py:95-97`), e o módulo promete recalcular os RDOs
vizinhos quando a proporção muda (`:18-19`). **A promessa é cumprida na tabela de
origem e não no razão.** O primeiro lançamento nasceu com 150,00 quando era o único
RDO do dia; quando o segundo chegou e a proporção virou 50/50, o vizinho foi
recalculado na origem, mas o guard de idempotência encontrou o filho existente e fez
`continue` em vez de atualizar. **Idempotência que ignora mudança de valor vira dado
velho**, e a fonte e o razão divergem em R$ 75,00.

O mesmo cego existe nos dois mecanismos, e é a mesma frase de código nos dois:
`services/rdo_custos.py:460-467` (`ja = ...; if ja: continue`) e
`event_manager.py:933-948` + `:976` (`existing_filho` → `else: skip`). Nenhum dos dois
compara valor; os dois só perguntam se a linha existe.

**Por que vem DEPOIS da B1.5, e não antes.** Hoje o defeito é observável pela rota
`/salvar-rdo-flexivel`, que chama o serviço direto (`views/rdo.py:4490`) **e** emite:
o serviço cria um filho por RDO com chave estreita, e o handler depois encontra a
chave larga e sai. A B1.5 remove as chamadas diretas e deixa o handler como único
escritor — **e o guard do handler é o de chave LARGA**, que se comporta de outro modo
neste cenário (encontra o filho do primeiro RDO e pula o segundo por inteiro). Corrigir
antes da B1.5 significa corrigir nos dois lugares e depois descobrir qual deles
sobreviveu. **Por isso o Step 1 é medir de novo, não editar.**

**Comportamento novo (a decidir no Step 1, com o default abaixo).** O guard que
sobreviver passa a **comparar valor antes de sair**: se a linha existe e o valor
diverge do que a fonte (`RDOCustoDiario`) diz agora, **atualizar** — valor, descrição e
`obra_id` — em vez de `continue`. Manter o `continue` quando o valor confere, que é o
caso comum e o que torna a reexecução barata.

**Default recomendado se o Step 1 deixar dúvida:** corrigir **no handler**, porque
depois da B1.5 ele é o mecanismo canônico (D1), e deixar o guard do serviço como está,
com comentário apontando para cá. O serviço fica sem chamador de rota depois da B1.5 —
sobram `migrations.py:13968` (migração 154) e
`scripts/migrar_rdos_rascunho_legados.py:120`, ambos de reprocesso, onde dado velho é
justamente o que se quer corrigir.

**Teste que prova:** o `xfail(strict=True)` de `tests/test_arreio_custo_rdo_rotas.py:317`
vira XPASS e a marca sai. Ele já mede as duas somas (origem × razão) e falha com as
duas impressas.

**Riscos → mitigação.**
1. **Atualizar valor de filho cujo pai já foi PAGO** é a mesma classe de problema que
   adiou o A12 (§8.2) → o update tem que ser recusado, com WARNING, quando o
   `GestaoCustoPai` estiver em estado que não admita revisão. **Conferir o estado do pai
   antes de escrever**, e se não houver campo que o diga, registrar isso como achado e
   parar — não inventar semântica de pagamento aqui.
2. Comparar `float` de dinheiro com `==` produz falso negativo por representação →
   comparar com a mesma tolerância que o resto do módulo usa, ou em `Decimal`.
3. Um guard que atualiza é um guard que **escreve** em caminho antes somente-leitura:
   reexecutar o evento passa a poder mexer em linha antiga. É o efeito pretendido, mas
   é o tipo de mudança que o arreio precisa cobrir nos dois sentidos — teste de que o
   valor CONFERINDO não gera escrita nenhuma.
4. A divergência de numeração: o docstring do teste cita
   `services/rdo_custos.py:422-428`, que era a linha em `35975e7a`; depois de `cefba5e7`
   o guard está em `:460-467`. **Corrigir a citação do docstring junto**, senão a
   próxima leitura persegue linha errada.

- [x] **Step 1:** depois da B1.5, rodar o teste de novo e **medir qual guard sobrou** —
      as duas somas, com os valores impressos. Só então decidir o arquivo
- [x] **Step 2:** o guard passa a comparar valor e atualizar; `continue` só quando confere
- [x] **Step 3:** conferir o estado do pai antes de atualizar (risco 1)
- [x] **Step 4:** teste de não-escrita quando o valor confere (risco 3); corrigir a
      citação de linha no docstring (risco 4)
- [x] **Step 5:** rodar o arreio inteiro — o `xfail` de `:317` deve virar XPASS e a marca sai
- [x] **Step 6:** commit — `fix(rdo): idempotência do custo de mão de obra compara valor, não só existência`

**Status: ✅ entregue junto da B1.5, no mesmo commit (ver o Status dela).**

**Desvio: o Step 1 mudou o desenho da Task.** Estava escrito que o guard
sobrevivente passaria a "comparar valor antes de sair". A medição mostrou que
comparar valor é **metade** do conserto, e sozinha não resolveria nada: o guard
que sobreviveu é o de chave LARGA do handler, e ele nem chegava a comparar valor
porque saía antes, ao encontrar a linha de OUTRO RDO do mesmo dia. O cego tem
dois lados, e os dois precisavam ceder:

1. **Origem.** A chave larga tem de continuar larga para o **ponto** — é para
   isso que o p1 Step D tirou o filtro de origem, e sem isso a diária entra duas
   vezes. Mas irmã de outro RDO do mesmo dia **não é duplicata, é a outra metade
   do dia**. O guard passa a distinguir: linha de origem fora da família do RDO
   (o ponto) bloqueia; linha de origem `rdo_custo_diario` não bloqueia.
2. **Valor.** Aí sim, comparar e reconciliar — na nossa linha e nas irmãs, cujo
   valor muda quando este RDO entra e o rateio do dia vira.

O resultado é que o razão do dia passa a **espelhar o conjunto de linhas de
`RDOCustoDiario`**, uma por RDO, com o valor de agora — que é a formulação que a
Task deveria ter tido desde o começo, e que só ficou visível depois de medir.
Fecha os dois casos de uma vez, e são casos com respostas opostas:

```
diarista  150,00 rateado 75/75  →  2 linhas × R$ 75,00  = R$ 150,00  (tem teto)
mensalista 4h + 4h              →  2 linhas × R$ 62,00  = R$ 124,00  (não tem)
```

**O risco 1 (pai já pago) foi respondido por leitura e virou outra coisa.** Não
há estado de pagamento a conferir no caminho, mas há um problema vizinho que o
recorte não tinha visto: `GestaoCustoPai.valor_total` **não é derivado** — é
somatório mantido à mão (`utils/financeiro_integration.py:222`). Reconciliar o
filho sem ajustar o pai consertaria a divergência entre origem e razão criando a
mesma divergência um andar acima. O ajuste por delta entrou em
`_reconciliar_valor`.

**E o que a medição diz sobre esse ajuste, para não haver ilusão:** hoje
**nenhum** caminho de rota depende dele. `registrar_custo_automatico` recomputa
`pai.valor_total` somando os filhos a cada inserção (`:177-181`), então quando a
reconciliação é seguida de inserção — o caso medido — o pai se autocura.
Confirmado desligando o ajuste: os testes seguem verdes. Ele fica como defesa do
caminho sem inserção depois (job de reprocesso, rota futura que não apague antes),
e o `_assert_pais_fecham_com_os_filhos` do arreio fica como **invariante de casa,
declaradamente não como prova de defeito atual**. Está escrito assim nos dois
docstrings, para ninguém ler mais garantia do que existe.

---

### 4.2 A10 — o ponto manual para de perder custo

A perda tem **duas bocas**. (1) `views/admin.py:98` (`POST /novo_ponto`,
`@login_required`, sem `@admin_required`) monta `RegistroPonto` em `:150-161` sem
nenhuma consulta prévia, commita em `:175-176` e emite em `:185-188`. Levantei TODOS
os criadores de `RegistroPonto` fora de `archive/` e `tests/` — são **dez**, e **nove**
reusam o registro do dia antes de criar (`ponto_service.py:105-118` e `:326-350`,
`ponto_views.py:1483-1500`, `:1642-1656`, `:2362-2382`, `views/api.py:337-343` e
`:732-737`, `models.py:4562`, `models.py:4777`). O único fora da regra é
`views/admin.py:150` — e o consenso dos nove é a prova de que a invariante da casa é
**um registro por (funcionário, data)**. (2) `event_manager.py:524-530` procura o
`CustoObra` por (funcionario_id, data, **obra_id**, admin_id, `PONTO_ELETRONICO`);
achou, cai no UPDATE de `:532-545` e **sobrescreve**.

O encontro: dois lançamentos no mesmo dia/obra ⇒ 2 `RegistroPonto` de 4h ⇒ 1
`CustoObra` com as 4h do segundo. E o inverso, pior e não citado antes: dois
lançamentos no mesmo dia em obras **diferentes** ⇒ 2 `RegistroPonto` e **2**
`CustoObra` (a chave inclui `obra_id`) ⇒ o dia cobrado duas vezes.

A incoerência é observável sem olhar o banco: `services/funcionario_metrics.py:99-144`
soma `horas_trabalhadas` linha a linha — o KPI do funcionário mostra 8h enquanto a
obra recebeu custo de 4h.

**Sobre unique no banco:** `models.py:800-804` tem três índices, os três NÃO-únicos.
Não existe caso legítimo de mais de um registro por dia: o modelo
(`models.py:759-763`) tem UM `hora_entrada`, UM `hora_saida`, UM par de almoço; turno
partido se escreve numa linha só; não há coluna de turno nem de sequência.

> **Confiança:** alta nos fatos de código; **média** sobre a frequência do cenário em
> produção — ninguém contou quantos pares (funcionário, data) têm mais de um
> `RegistroPonto`. É por isso que a Task B1.8 (`q7`) existe, e é por isso que o índice
> único fica **fora** deste bloco.

**Esforço:** M. **A ordem importa e é contraintuitiva** — `event_manager.py`
PRIMEIRO, `views/admin.py` depois. Se `/novo_ponto` for corrigido antes, o cenário da
troca de obra fica **pior** do que hoje: passaria a existir UM `RegistroPonto` de 4h
com DOIS `CustoObra` de 4h (o órfão na obra antiga mais o novo), o dia cobrado em dobro
sem nenhuma linha de ponto que justifique.

---

### Task B1.6: a chave do custo de ponto perde `obra_id` e o custo segue a obra do registro

**Files:** Modify `event_manager.py` — `calcular_horas_folha` (decorado em `:302`),
bloco `:524-545`

**Comportamento novo.** A busca do `CustoObra` existente passa a casar por
(`funcionario_id`, `data`, `admin_id`, `categoria='PONTO_ELETRONICO'`) — **sem**
`obra_id`. Um único custo de ponto por funcionário-dia, que é a invariante que o resto
do código já assume. No ramo de UPDATE (`:532-538`) entra o realinhamento
`custo.obra_id = registro.obra_id`, para que o custo SIGA a obra hoje gravada em vez
de deixar linha órfã na obra anterior. Nada é apagado: a linha é **movida**. O INSERT
(`:547-560`) fica intacto. O log INFO de `:540-544` passa a registrar obra de origem e
de destino quando `custo.obra_id != registro.obra_id`.

**Teste que prova:** B0.4 caso (a); e `tests/test_p1_fallback_e_idempotencia.py::test_quatro_batidas_no_mesmo_dia_dao_uma_linha_de_custo`
tem de continuar verde **sem edição** — ele reusa o mesmo registro e a mesma obra. Se
quebrar, a chave foi estreitada demais.

**Riscos → mitigação.**
1. Consulta sem `admin_id` acha custo de outra empresa (`funcionario_id` é global) →
   manter `admin_id` na chave.
2. Em produção pode haver mais de um custo por dia (herança das duas obras) →
   usar `.first()` **ordenado por `id`** e deixar as sobras para a reconciliação;
   `.all()` com laço de merge transformaria esta correção numa deleção silenciosa de
   histórico.
3. O total do dia numa base com dois registros em obras diferentes deixa de ser 8h e
   passa a 4h → é o resultado correto (as 8h nunca foram trabalhadas), mas é mudança de
   saldo em obra viva: por isso o log.
4. **Armadilha do decorador:** a mudança é toda DENTRO do corpo; não inserir função
   entre `@event_handler('ponto_registrado')` (`:302`) e `def calcular_horas_folha`.

- [x] **Step 1:** chave sem `obra_id` + realinhamento + log origem→destino
- [x] **Step 2:** `pytest tests/test_p1_fallback_e_idempotencia.py -q` — verde sem edição
- [x] **Step 3:** commit — `fix(ponto): custo de ponto é um por funcionário-dia e segue a obra do registro`

**Status: ✅ entregue em `cdf18195`.** Sem desvio. A ordem contraintuitiva que a
§4.2 defende (esta ANTES da B1.7) foi respeitada, e o `test_p1_fallback_e_idempotencia`
passou **sem edição** — a prova de neutralidade que a Task pedia, e o sinal de que
a chave não foi estreitada demais.

---

### Task B1.7: `/novo_ponto` reusa o registro do dia com semântica de merge

**Files:** Modify `views/admin.py` — rota `novo_ponto` (`:98`): construção `:150-161`,
cálculo de horas `:163-173`, commit `:175-176`, emissão `:180-190`, resposta `:192-196`

**Comportamento novo.** Antes de construir, a rota busca `RegistroPonto` por
(`funcionario_id`, data-do-formulário, `admin_id`). Se existir, **REUSA com semântica
de MERGE**: cada campo do formulário só sobrescreve o que veio preenchido
(`hora_entrada`, `hora_saida`, `hora_almoco_saida`, `hora_almoco_retorno`, `obra_id`,
`observacoes`, `tipo_lancamento`); campo vazio no POST **não apaga** valor já gravado.
Se não existir, cria como hoje. O recálculo de horas (`:163-173`) passa a rodar sobre o
registro APÓS o merge, e a condição de `:163` passa a olhar `registro.hora_entrada`/
`registro.hora_saida` (o objeto), não as variáveis locais parseadas do POST. A emissão
de `:181` idem. A resposta (`:192-196`) devolve `criado: true/false` além de
`registro_id`, e a mensagem diz "atualizado" quando reusou — e o `alert()` de
`templates/funcionario_perfil.html:2238` deve dizer "Registro do dia atualizado".
Não é cosmético: é o que torna visível uma sobrescrita que hoje acontece em silêncio
no custo.

**Teste que prova:** `tests/test_a10_ponto_manual_nao_perde_custo.py` (escrito ANTES
desta Task rodar verde: com B1.6 aplicado e esta não, o Teste 1 deve falhar em
`RegistroPonto.count() == 1` — é essa falha que prova que o teste exercita o defeito,
e não a forma). Usa `dois_tenants('a10', DATA_SEMENTE)` e
`DIA = DATA_SEMENTE + timedelta(days=1)` — nunca `date.today()`.

| Teste | Ação | Asserção |
|---|---|---|
| 1 — dia partido | dois `POST /novo_ponto`, obra A, 08:00-12:00 e 13:00-17:00 | `RegistroPonto.count() == 1`; `CustoObra(PONTO_ELETRONICO).count() == 1`; **e a que carrega o item:** Σ`horas_trabalhadas` dos `RegistroPonto` == Σ`horas_trabalhadas` dos `CustoObra` do dia. Hoje 8.0 contra 4.0 |
| 2 — troca de obra | POST obra 1, depois POST obra 2 no mesmo DIA | exatamente UM `CustoObra` somando todas as obras, com `obra_id` igual ao do único `RegistroPonto`. Hoje dois custos, 4h em cada, para 8h que nunca foram trabalhadas |
| 3 — tenant | `cliente_de(a.admin_id)` posta com `funcionario_id` de B | 404 e `RegistroPonto.count() == 0` para B |

**Por que o atual não pegava:** `tests/test_p1_fallback_e_idempotencia.py:119-135`
muta o registro já semeado (nunca há dois no dia — a precondição do defeito), emite o
evento à mão pulando a rota inteira (a linha `views/admin.py:150` não é executada por
teste nenhum da suíte), e afirma `len(custos) == 1` — asserção que o **defeito
satisfaz**.

**Riscos → mitigação.**
1. `obra_id`: `:73-77` já converte vazio em `None`; no merge, `None` **não pode**
   sobrescrever a obra existente — se sobrescrever, o handler sai em `:326-328`
   ("sem obra vinculada") e o dia inteiro perde custo.
2. `tipo_registro`: `:159` usa `data.get('tipo_lancamento', 'trabalho_normal')` — no
   merge, aplicar só se a chave veio no POST, senão um lançamento de correção rebaixa
   um dia marcado `falta` para `trabalho_normal` e `services/funcionario_metrics.py:124-128`
   deixa de contar a falta.
3. O `except Exception` largo de `:198-201` não tem `except HTTPException: raise`
   antes; hoje não morde (o 404 de tenant em `:120-122` é `jsonify` explícito), mas se
   a correção introduzir `abort(404)` o catch-all engole e a rota devolve 200 com corpo
   de erro → **manter o `jsonify(...), 404`**.
4. Contrato percebido muda: quem hoje lança duas linhas para turno partido passa a ver
   UMA → é o que a resposta `criado: false` e a mensagem tornam visível.
5. Duas requisições simultâneas ainda passam pelo lookup e criam dois registros →
   **aceitar**. É lançamento manual digitado por gente; a janela é de milissegundos e o
   defeito real é o sequencial. Fechar de verdade exige o unique, que depende de `q7`.
6. **Não existe rota de edição.** O JS de `templates/funcionario_perfil.html:2196-2199`
   faz `PUT /ponto/registro/<id>` e `ponto_views.py` só registra `DELETE` em `:792`,
   `GET /excluir-preview` em `:819` e `POST /excluir` em `:877` — editar um ponto pelo
   perfil devolve **405 hoje**, e é isso que produz as duplicatas em produção. Com o
   merge, `/novo_ponto` vira de fato o caminho de edição. **Não criar o PUT dentro
   deste recorte**, ou o item dobra de tamanho e passa a mexer no JS.

- [x] **Step 1:** escrever o teste e vê-lo vermelho no `count() == 1`
- [x] **Step 2:** lookup + merge + recálculo sobre o objeto + emissão baseada em `registro.hora_entrada`
- [x] **Step 3:** resposta com `criado` e mensagem; ajustar o `alert()` do template
- [x] **Step 4:** commit — `fix(ponto): /novo_ponto reusa o registro do dia (merge) em vez de criar incondicionalmente`

**Status: ✅ entregue em `3710b864`. 🔴 Desvio de SEMÂNTICA, decidido pelo Cássio —
o recorte desta Task contradizia a §1 deste mesmo documento.**

A §1 diagnostica: *"08:00-12:00 e 13:00-17:00 criam 2 `RegistroPonto` (4h + 4h =
8h) e deixam um `CustoObra` de 4h. **O dia de 8h vira metade**"* — tratando 8h
como a verdade perdida. Mas o merge desta Task, como escrito ("cada campo do
formulário só sobrescreve o que veio preenchido"), faria o segundo POST trocar
`hora_entrada` para 13:00 e o dia passar a valer **4h**: o sistema ficaria
coerente consigo mesmo concordando que a jornada foi de meia jornada, e a manhã
sumiria do registro do trabalhador. Coerência não é correção.

**Decidido: TURNO PARTIDO.** A regra, e o que distingue os casos:

| Segundo lançamento | Interpretação | Resultado |
|---|---|---|
| COMEÇA depois de o registrado terminar | segunda metade do dia | `08:00→17:00`, almoço `12:00-13:00`, **8h** |
| SE SOBREPÕE ao registrado | correção, vale o último | `08:00→18:00`, **9h** |
| Terceiro turno, almoço já ocupado | não cabe no modelo | aplicado como correção + `WARNING` |

O terceiro caso é o único onde se perde informação, e a escolha é deliberada: o
modelo tem **um** par de almoço (`models.py:759-763`), e esticar a saída por cima
do intervalo faria `calcular_horas_trabalhadas` contar o vão como trabalhado.
**Superestimar folha é pior que subestimar** — um erro paga a mais e ninguém
reclama; o outro aparece.

**Os seis riscos do recorte foram todos aplicados como escritos.** O que a
execução acrescentou:

1. **O `alert()` do template parou de adivinhar.** Ele decidia por `registroId`,
   que só diz se o formulário abriu em modo de edição — não sabe que um
   lançamento novo pode ter REUSADO o registro do dia, nem que duas metades
   viraram turno partido. Passa a exibir a mensagem do servidor. **Não é
   cosmético: a sobrescrita SILENCIOSA era o defeito**, e dizer em voz alta o que
   aconteceu é metade da correção.
2. **Quarto instrumento medindo o vazio nesta rodada.** O coletor `custos_obra`
   estava preso a `tenant.obra_id`, e a invariante da B1.6 é **entre** obras: o
   teste de troca de obra achava zero linha e passava a acusar o oposto do que
   investigava. Ganhou `qualquer_obra=True`, com o motivo no docstring.
3. **O caso de isolamento de tenant ficou mais necessário do que era.** Com
   merge, um vazamento passa a **alterar** registro alheio, não só criar.

---

### Task B1.8: `q7_pontos_duplicados_no_dia` em `scripts/medir_producao.py`

**Files:** Modify `scripts/medir_producao.py` — nova pergunta no molde de
`q6_duplicacao_ponto_rdo` (`:211-244`), registrada na tupla de `main()` em `:259-261`

**Comportamento novo.** Consulta SOMENTE-LEITURA que conta, por `admin_id`, quantos
pares (`funcionario_id`, `data`) têm mais de um `RegistroPonto`, quantas obras
distintas aparecem nesses dias e quantas horas estão gravadas sem custo
correspondente. É a medida que falta para decidir, **depois e com número na mão**, se
cabe um índice único — e é o inventário do estrago já feito, que a correção de rota
não desfaz.

**Teste que prova:** nenhum automatizado — é script de medição. A prova é rodar contra
dev e contra produção e o número sair.

**Riscos → mitigação.** O script conecta com `set_session(readonly=True)` (`:256`) →
não acrescentar nada que escreva. E **não** fazer o script CORRIGIR o histórico:
consolidar linhas duplicadas é decisão de negócio (qual obra fica com o custo), não
efeito colateral de uma medição.

- [x] **Step 1:** escrever `q7` e registrá-la em `main()`
- [~] **Step 2:** rodar em dev ✅, **em produção — PENDENTE**
- [x] **Step 3:** commit — `feat(scripts): q7 — pontos duplicados no dia, por tenant`

**Status: ✅ código entregue em `36a077b0`; ⚠️ a MEDIÇÃO em produção segue
pendente, e é ela que serve para alguma coisa.**

Rodada em dev, onde o resultado é resíduo de suíte e **não vale como estimativa**
— mas exibe o defeito com clareza: 29 tenants, e o padrão repetido é **8.0h
gravadas contra 4.0h custeadas**. A consulta traz também a coluna de dias em mais
de uma obra, que é o lado pior (dia cobrado duas vezes) e que a B1.6 acabou de
fechar para o futuro.

**O que depende deste número:** o índice único em `(funcionario_id, data)` — hoje
os três índices de `models.py:800-804` são todos NÃO-únicos, e um
`CREATE UNIQUE INDEX` falharia se produção tiver linhas que o violem. Foi
`/novo_ponto` que as criou, então provavelmente tem. Se couber, é a **migração
280** (faixa liberada pelo corte da Fase 7, §12).

---

### 4.3 A16-a — o plano para de sobrescrever ausência classificada

`AllocationEmployee.sincronizar_com_ponto` (`models.py:4556`) busca o registro do dia
em `:4562-4565` (`filter_by(funcionario_id, data)` — **sem `admin_id`**) e decide por
uma condição só: `tem_batida_real = bool(hora_entrada or hora_saida)` (`:4580-4581`).
Tudo que não tem hora cai no ramo de preenchimento (`:4600-4616`), que reescreve
`obra_id` (`:4602`), `tipo_local` (`:4603`), os horários do turno (`:4604-4605`),
almoço e percentual (`:4607-4612`), `tipo_registro = self.tipo_lancamento` (`:4614`) e
`horas_trabalhadas = self._calcular_horas_trabalhadas()` (`:4616`) — 8.0 para o turno
padrão 08:00–17:00 (defaults em `:4478-4485`, cálculo em `:4656-4700`).

Ausência classificada **não tem hora nenhuma, por construção**:
`PontoService.registrar_falta` cria sem hora (`ponto_service.py:344-350`) com `motivo`
vindo **cru** da rota (`ponto_views.py:1016` — **não há allowlist**, qualquer string é
persistida); o import de Excel grava o tipo verbatim e **em CAIXA ALTA**
(`services/ponto_importacao.py:576-580`, `:598-599`, `:602-608`;
`ponto_views.py:1498`); o cron cria `falta`/`sabado_folga`/`domingo_folga`/`feriado_folga`
sem hora (`models.py:4783-4793`); e o modal (`templates/controle_ponto.html:289-299`)
**limpa os campos de horário** para esses tipos (`:606-618`).

**Conclusão de projeto:** a definição certa não é "tem hora". É **lista branca fechada
de tipos neutros + ausência de qualquer marca de trabalho medido**, comparada com
normalização de caixa. Denylist não serve (o Excel escreve maiúsculas e a rota de falta
aceita string livre); comparação sensível a caixa deixaria `'ATESTADO'` passar.

**Esforço:** P. **Esta é a fatia livre do A16** — a outra metade (emitir
`ponto_registrado` do ramo do plano) está travada pela **D6** (§10) e **tem de vir
depois desta**: emitir do ramo de preenchimento antes da guarda existir significaria
emitir custo por cima de um atestado.

---

### Task B1.9: `TIPOS_PONTO_NEUTROS_PARA_O_PLANO` + `registro_ponto_tem_fato_humano`

**Files:** Modify `models.py` — logo abaixo da classe `RegistroPonto`, entre `:804`
(fim do `__table_args__`) e `:806` (`class ConfiguracaoHorario`); módulo, não dentro de
classe decorada

**Comportamento novo.** Passa a existir uma constante única
`TIPOS_PONTO_NEUTROS_PARA_O_PLANO` (frozenset, tudo minúsculo: `''`, `'trabalhado'`,
`'trabalho_normal'`, `'normal'`, `'trab'`, `'sabado_trabalhado'`,
`'domingo_trabalhado'`, `'feriado_trabalhado'`, `'sab_trab'`, `'dom_trab'`,
`'fer_trab'`) e uma função `registro_ponto_tem_fato_humano(registro) -> bool` que
devolve True se QUALQUER uma valer:

1. alguma das quatro marcas de horário estiver preenchida (`hora_entrada`,
   `hora_saida`, `hora_almoco_saida`, `hora_almoco_retorno`);
2. `horas_trabalhadas` ou `horas_extras` for > 0;
3. `(registro.tipo_registro or '').strip().lower()` **não** estiver na lista branca.

**Fail-closed: tipo desconhecido é fato humano.** A função fica ao lado da coluna que
lê (`models.py:779`), com comentário apontando o modal
(`templates/controle_ponto.html:280-300`) e o vocabulário do Excel
(`services/ponto_importacao.py:598-599`) para quem acrescentar um tipo novo saber que
precisa mexer aqui.

**Inventário classificado — NÃO SOBRESCRIVÍVEL:** `'falta'`, `'falta_justificada'`
(`ponto_service.py:349`, `models.py:4783`), `'ferias'`, `'sabado_folga'`,
`'domingo_folga'`, `'feriado_folga'` (`models.py:4810-4820`, `views/api.py:348-350`,
`:728`), `'meio_periodo'`, a família em caixa alta do Excel
(`'FALTA'`,`'FALTA_J'`,`'ATESTADO'`,`'FERIAS'`,`'SAB_FOLGA'`,`'DOM_FOLGA'`,`'FER_FOLGA'`),
qualquer string desconhecida, e — o caso que mais dói —
`'sabado_horas_extras'`/`'domingo_horas_extras'`: sem escritor vivo, mas **lidos com
regra de pagamento própria** (`utils.py:337-342` paga 1.5x/2.0x sobre TODAS as horas;
`pdf_generator.py:306-309`). Convertê-los para `'sabado_trabalhado'` não casa com
nenhum ramo de `utils.py:326-344` → **o custo vira zero**.

**Teste que prova:** unidade sobre a função, com os três gatilhos e a normalização de
caixa; e o arquivo de rota da Task B1.10.

**Risco → mitigação.** A lista branca é de valores JÁ normalizados (strip+lower): se
alguém escrever `'ATESTADO'` nela, ela nunca casa e o efeito é o oposto do pretendido.

- [x] **Step 1:** constante + função, **sozinhas**, sem trocar a chamada ainda
- [x] **Step 2:** teste de unidade da função
- [x] **Step 3:** commit — `feat(ponto): registro_ponto_tem_fato_humano — lista branca fechada de tipos neutros`

**Status: ✅ entregue em `7a33a7f6`.** Sem desvio — 44 testes de unidade, sem
banco, em `tests/test_a16_fato_humano.py`.

O teste que mais vale entre eles é o que **varre a própria lista branca** e exige
forma normalizada (`tipo == tipo.strip().lower()`). O erro provável na manutenção
da constante é acrescentar um valor em CAIXA ALTA; aí a entrada nunca casa, o
caso legítimo passa a ser tratado como classificado, **o plano deixa de converter
tudo — em silêncio, e sem nenhum outro teste reclamando.** É o risco que a Task
já apontava, agora com cão de guarda.

---

### Task B1.10: a guarda do sync passa a usar a função, com log que diz a causa

**Files:** Modify `models.py` — `AllocationEmployee.sincronizar_com_ponto`,
`:4580-4582` (a atribuição de `tem_batida_real` e o `if`) e a mensagem de `:4583-4589`

**Comportamento novo.** A condição vira `registro_ponto_tem_fato_humano(registro_existente)`.
Todo o corpo do ramo protegido (`:4583-4598`) fica como está — marca
`sincronizado_ponto=True`, grava `data_sincronizacao`, commita e retorna True, para não
virar retentativa a cada rodada do cron. Só a mensagem de log muda: passa a dizer QUAL
das três causas travou (hora / horas medidas / tipo classificado) e a imprimir
`registro_existente.tipo_registro`, em WARNING quando a causa for tipo classificado,
para que o operador consiga achar no log a falta automática que o plano deixou de
converter. Os ramos de preenchimento (`:4600-4616`) e de criação (`:4617-4650`) **não
mudam uma linha**.

**Teste que prova:** `tests/test_a16_plano_nao_sobrescreve_ausencia.py`, **nível
rota**. `DATA_SEED = date(2026, 3, 9)` (o que `dois_tenants` já popula) e
`DATA_PLANO = date(2026, 3, 10)` — data fixa e **enviada no corpo do POST**, então nada
depende do dia do mês. Para os quatro casos: `Allocation` + `AllocationEmployee`
(`turno_inicio=time(8,0)`, `turno_fim=time(17,0)`, sem passar `tipo_lancamento`, para
usar o default `'trabalho_normal'` e não depender do dia da semana). Ação única e
idêntica: `cliente_de(t.admin_id).post('/equipe/api/sync-ponto',
json={'data_processamento': DATA_PLANO.isoformat()})`.

| Caso | Semente | Asserção após `db.session.expire_all()` |
|---|---|---|
| 1 | `RegistroPonto(tipo_registro='atestado', observacoes='Atestado 3 dias', horas_trabalhadas=0.0)`, sem hora, sem obra | UM registro; `tipo_registro` intacto; `hora_entrada is None`; `hora_saida is None`; `horas_trabalhadas == 0`; `obra_id is None`; `observacoes` intacto; `AllocationEmployee.sincronizado_ponto is True` |
| 2 | idem com `'ATESTADO'` e depois `'FALTA_J'` (caixa alta do Excel) | idêntico ao caso 1 |
| 3 | `tipo_registro='trabalho_normal'`, `horas_trabalhadas=0.0`, sem hora | `hora_entrada == time(8,0)`; `hora_saida == time(17,0)`; `obra_id == t.obra_id`; `horas_trabalhadas == 8.0` — **o caso legítimo não pode morrer** |
| 4 | sem registro em `DATA_PLANO` | registro criado, `admin_id == t.admin_id`, `hora_entrada == time(8,0)`, `obra_id == t.obra_id` |
| 5 | tenant | nenhum `RegistroPonto` de `b.funcionario_id` em `DATA_PLANO` criado ou alterado pelo POST feito como A |

**Por que o atual não pegava.** Os testes vivos de p7
(`tests/test_p7_p8_presenca_e_progresso.py:74-92`, `:95-105`, `:108-125`) não são
textuais — mas chamam `ae.sincronizar_com_ponto()` **direto**, e os três só semeiam o
caso que a condição atual já cobre: `registro.hora_entrada = time(7,12)` (`:78`,
`:100`) ou registro apagado (`:113-115`). Nenhum semeia registro com `tipo_registro`
de ausência e sem hora — exatamente o ramo `models.py:4600-4616`, que portanto **nunca
foi exercitado**. Como o método é chamado direto, a rota `POST /equipe/api/sync-ponto`
(`equipe_views.py:1212-1236`) e `processar_lancamentos_automaticos` (`models.py:4745`)
também nunca rodaram em teste: o gate `if not alocacao.sincronizado_ponto`
(`models.py:4773`), o `join(Allocation)` com filtro de `admin_id` (`:4767-4771`) e a
resolução de `get_admin_id()` na rota estão todos sem cobertura. E um teste textual não
pegaria nem em princípio: a linha `tem_batida_real = bool(...)` **está** no arquivo e
está errada — o texto presente é justamente o defeito.

**Riscos → mitigação.**
1. Falta gerada pelo próprio cron (`models.py:4783`) passa a ser protegida; alocação
   criada retroativamente não converte mais → é o preço deliberado da lista branca
   fechada (a alternativa, carve-out pelo prefixo `'Lançamento automático'` em
   `observacoes`, reabre o buraco via string que um humano pode digitar). Mitigar com o
   WARNING e documentar no docstring que a correção do caso retroativo é manual.
2. Tipo novo no modal ou no Excel nasce PROTEGIDO por padrão → fail-closed é a direção
   certa (errar protegendo dado do usuário, não destruindo), e o WARNING faz o caso
   aparecer.
3. O ramo protegido marca `sincronizado_ponto = True` (`:4590`): se o usuário depois
   apagar o atestado, o sync não reprocessa → é **simétrico** ao comportamento que já
   existe para batida real, não é regressão nova. Manter simétrico de propósito; a
   alternativa faz o cron reprocessar a mesma alocação todo dia, que foi o defeito que
   `tests/test_p7_p8_presenca_e_progresso.py:95-105` existe para travar.
4. `horas_trabalhadas > 0 or horas_extras > 0` na guarda muda o comportamento de
   registros neutros com horas medidas — que é o que `tests/helpers_tenant.py:88`
   semeia (8.0/2.0 sem hora) → é intencional: recalcular por cima zeraria
   `horas_extras`. Nenhum teste vivo afirma o contrário. Rodar
   `pytest tests/test_p7_p8_presenca_e_progresso.py -q` como primeiro sinal.
5. O nome `tem_batida_real` some do arquivo → `grep -rn tem_batida_real tests/` antes,
   caso algum guarda textual o procure.

- [x] **Step 1:** trocar a condição e ampliar a mensagem de log
- [x] **Step 2:** `pytest tests/test_p7_p8_presenca_e_progresso.py -q` — 10 passed
- [x] **Step 3:** escrever/rodar os casos de rota (no arreio, não em arquivo novo)
- [x] **Step 4:** commit — `fix(ponto): plano não sobrescreve registro com fato humano (ausência classificada)`

**Status: ✅ entregue junto da B1.11.** Dois desvios, os dois de forma e não de
desenho:

1. **O arquivo `tests/test_a16_plano_nao_sobrescreve_ausencia.py` não foi
   criado.** Os casos foram para `tests/test_arreio_presenca_rotas.py`, que já
   posta em `/equipe/api/sync-ponto` com o cenário montado — mesma decisão que a
   B1.5 tomou sobre `test_a05_custo_mensalista_por_rota.py`, e pelo mesmo motivo:
   segunda cópia da mesma prova é duas provas que divergem depois.
2. **O caso 1 da tabela virou parametrizado por CAMINHO DE ENTRADA**, que é mais
   forte do que estava escrito: `'atestado'` (rota de falta), `'ATESTADO'` e
   `'FALTA_J'` (importador de Excel, caixa alta), `'ferias'`, e
   `'licenca_inventada_2026'` — este último prova o **fail-closed**, e não é
   hipótese acadêmica: `ponto_views.py:1016` persiste `motivo` cru, sem allowlist,
   então tipo desconhecido é entrada normal do sistema.

Acrescentado um caso que a tabela não previa e que é o contrapeso necessário:
**registro neutro e vazio continua sendo preenchido**. Guarda estreita demais
custa dado do usuário; guarda larga demais desliga a funcionalidade inteira, e
sem barulho nenhum.

O risco 5 (`grep tem_batida_real tests/`) foi conferido: o nome só aparece em
docstring do próprio arreio, nenhum guarda textual o procura.

---

### Task B1.11: `admin_id` na busca do registro do sync

**Files:** Modify `models.py:4562-4565` (o `filter_by` de `sincronizar_com_ponto`)

**Comportamento novo.** Acrescentar `admin_id=self.admin_id`. Hoje a busca é só por
`funcionario_id` + `data`, então a guarda decidiria com base no `tipo_registro` de um
registro de outro tenant — e o ramo de preenchimento escreveria nele.

**Teste que prova:** caso 5 da Task B1.10.

**Risco → mitigação.** Se existir em produção `RegistroPonto` do funcionário com
`admin_id` divergente do `AllocationEmployee.admin_id`, o sync deixa de encontrá-lo e
cai no ramo de criação (`:4623`), gerando um SEGUNDO registro no mesmo dia — não há
unique em (funcionario_id, data). **Conferir com um SELECT de contagem antes de
aplicar**; se houver divergência, deixar esta Task de fora e tratá-la à parte. Por isso
ela é separada das duas anteriores: é a única que pode gerar registro duplicado e
precisa ser descartável sem desfazer o resto.

- [x] **Step 1:** SELECT de contagem de divergência `RegistroPonto.admin_id` × `AllocationEmployee.admin_id`
- [x] **Step 2:** se zero, acrescentar `admin_id` ao `filter_by`
- [x] **Step 3:** `pytest tests/test_p7_p8_presenca_e_progresso.py -q` — separar "a guarda nova quebrou p7" de "o filtro de tenant quebrou p7"
- [x] **Step 4:** commit — `fix(ponto): sync de alocação busca o registro dentro do tenant`

**Status: ✅ entregue junto da B1.10.**

**Step 1, medido em dev: ZERO divergências, em 90 pares casados.** Era o risco
que justificava esta Task ser separável e descartável — com divergência, o filtro
faria o sync não achar o registro e cair no ramo de criação, gerando um SEGUNDO
registro no dia (não há unique em `funcionario_id, data`). Como deu zero, entrou
junto. **A contagem precisa ser repetida em produção antes do deploy**; está
anotada no comentário do código, ao lado da consulta.

**Por que acabou saindo com a B1.10, e não separada:** a B1.10 **piora** este
buraco antes de a B1.11 fechá-lo. Com a guarda nova, um atestado de OUTRO tenant
passaria a proteger o dia deste, e o plano deixaria de converter sem ninguém
entender a causa. Separá-las abriria essa janela.

**🔬 O teste de tenant que eu escrevi primeiro era VACUOSO** — quinto caso desta
rodada, e o mais instrutivo porque o docstring afirmava o que o código não fazia:
ele semeava o registro do funcionário de B, mas **cada tenant tem o seu
funcionário, com id próprio**, então a colisão que ele dizia montar não existia e
ele passava com e sem o filtro. Só apareceu porque desliguei a correção para ver
o teste falhar — disciplina que virou hábito nesta sessão e que se pagou de novo.

O cenário verdadeiro é **dado sujo**: uma linha com o funcionário de A e o
`admin_id` de B. É exatamente a divergência que o Step 1 mandou contar, e é a
única forma de a busca antiga achar algo que não é dela. Reescrito assim, o teste
falha sem a correção com a mensagem certa: *"o tenant A deveria ter um registro
próprio no dia, tem 0 — a busca achou a linha de B e a guarda protegeu o dia
errado"*.

---

### 4.4 A09 + os dois "vazamentos de tenant" — reclassificados ao abrir o código

**Duas das três premissas do recorte estavam erradas, e o executor precisa saber ANTES
de escrever código:**

- **`almoxarifado_utils.py:257` está em função MORTA.** `grep processar_xml_nfe` fora
  de `archive/` devolve só a definição de `:250` — nenhuma rota, template ou job. E o
  bloqueio cross-tenant que existe de verdade **não está nessa linha**: está no UNIQUE
  **global** de `NotaFiscal.chave_acesso` (`models.py:2550`). Consertar a `:257`
  sozinha não resolve e **piora**: com `admin_id` na consulta, o fluxo passa a chegar
  ao `db.session.add` de `:328` + `flush()` de `:329` e estoura IntegrityError — troca
  uma mensagem amigável errada por um 500.
- **`views/obras.py:743-757` NÃO vaza nada hoje.** A cadeia inteira foi aberta: os
  únicos chamadores são `:826` e `:878`, ambos dentro de `obter_servicos_da_obra`
  (`:776`); os únicos chamadores dela são `:1104` (`editar_obra`, que resolve a obra em
  `:927` com `obras_visiveis().filter(...).first_or_404()`) e `:1884` (`detalhes_obra`,
  com `@obra_required()` em `:1503`); `utils/autorizacao.py:73-99` filtra
  `Obra.admin_id == tenant` SEMPRE; e a consulta é fechada por obra
  (`JOIN rdo r ON rss2.rdo_id = r.id WHERE r.obra_id = :obra_id`, `:750-751`). O
  `admin_id` faltante é **defesa em profundidade**, não vazamento vivo, e **não deve
  entrar no changelog como `fix(tenant)`**.

**O vazamento de leitura DE VERDADE não está em nenhum dos dois documentos** e fica 40
linhas abaixo: `views/obras.py:791-798` junta `ServicoObraReal` com `Servico`
filtrando `ServicoObraReal.admin_id == admin_id` (`:795`) e `Servico.ativo == True`
(`:797`), mas **nunca `Servico.admin_id`** (conferido hoje em `views/obras.py:789-798`).
Nome, categoria, unidade e `custo_unitario` de um `Servico` alheio sobem para
`servicos_lista` (`:803-808`) e para a tela de detalhes/edição da obra. O próprio
fallback logo abaixo já faz certo: `:856` tem `s.admin_id = :admin_id`.

**A09 confirmado ausente:** `views/almoxarifado/movimentos.py` lê `nota_fiscal` em
`:47` (form) e `:217` (JSON) e grava direto em `:107`, `:159`, `:178`, `:322`, `:363`,
`:382` — sem verificação. A única guarda é por número de série (`:88-96`, `:263-271`).
Reenviar o formulário duplica estoque silenciosamente.

**Esforço:** M. **Passo 0 — escrever o arreio ANTES de qualquer correção**, para que
T1, T2, T4 e T5 falhem VERMELHO. É o critério do p1 Step 0 (`c9138a39`): sem os dois
tenants semeados lado a lado, "não vaza" é opinião.

**O teste do bloco:** `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py`, com
`dois_tenants('almox')` + `cliente_de(...)` e seeding local de almoxarifado (o helper
não semeia isso: uma `AlmoxarifadoCategoria`, um `AlmoxarifadoItem` CONSUMIVEL —
`categoria_id` é NOT NULL, `models.py:5253` — e um `Fornecedor` por tenant).

| # | Ação | Asserção (estado do banco, salvo o status) |
|---|---|---|
| T1 | A posta `/almoxarifado/processar-entrada` com `nota_fiscal='NF-4321'`, duas vezes | `AlmoxarifadoMovimento.filter_by(admin_id=a, nota_fiscal='NF-4321').count() == 1`; Σ`AlmoxarifadoEstoque.quantidade` equivale a UMA entrada |
| T2 | B posta a MESMA NF com item e fornecedor DELE | `count() == 1` para B **e** continua 1 para A — a NF de A não pode recusar a entrada de B |
| T3 | A posta duas vezes com `nota_fiscal=''` | dois movimentos gravados — NF vazia não é chave |
| T4 | RDO + `RDOServicoSubatividade` (30 e 50) na obra de A; GET `/obras/<obra_A>` como A e como B | como A: 200 e progresso do serviço == **40.0** (o AVG — prova que o filtro de `admin_id` não zerou nada), e `b.marca` ausente do corpo; como B: **404**, nunca 403 nem 200 |
| T5 | A posta JSON `/almoxarifado/processar-entrada-multipla` com `fornecedor_id` de B | 404 e `AlmoxarifadoMovimento.filter_by(admin_id=a).count()` inalterado |

**Por que o atual não pegava.** `tests/test_p1_dedup_cross_origem.py:151-165` nunca
sobe um request, nunca abre sessão com dois tenants e nunca inspeciona o que foi
gravado — nenhum caractere de `views/almoxarifado/movimentos.py` nem do SQL de
`views/obras.py:743-757` é lido por ele. Do outro lado,
`tests/test_cronograma_engine_unificado.py:90-114` chama
`calcular_progresso_real_servico(obra.id, servico.id)` **direto**, com um tenant só:
exercita a fórmula e não o isolamento, e continuaria verde com o join de `:791-798`
vazando catálogo alheio.

---

### Task B1.12: `Servico.admin_id` no join de `obter_servicos_da_obra` — o único vazamento real

**Files:** Modify `views/obras.py:793-798`

**Comportamento novo.** O join com `Servico` passa a exigir
`Servico.admin_id == admin_id`, além do `ServicoObraReal.admin_id` que já existe em
`:795`. Linha de `servico_obra_real` que aponte para catálogo de outra empresa deixa de
trazer nome, categoria, unidade e `custo_unitario` alheios para a tela.

**Teste que prova:** T4 (o corpo do GET de A não contém `b.marca`).

**Riscos → mitigação.**
1. O filtro de tenant entra ANTES do filtro de negócio, na mesma lista do `.filter()`
   — regra do p1 (`955aeb9f`): escopo depois de join depende de ordem e volta a vazar
   na primeira refatoração.
2. Se em alguma base houver linha legítima com catálogo cruzado, o serviço some da tela
   em vez de aparecer errado — comportamento desejado, mas a contagem do log de `:829`
   pode cair.
3. A função é cercada por `except Exception` que degrada em silêncio (`:839-846` cai no
   fallback) → o teste afirma o **valor** 40.0, não apenas "não explodiu", e confere no
   `caplog` que rodou o caminho principal (log `[STATS]` de `:824`), não o fallback.

- [x] **Step 1:** arreio vermelho (T1, T2, T4) — ⚠️ **o T5 estava nesta lista e
  NÃO foi escrito.** Marcado por engano em 04/08; corrigido e entregue em 05/08,
  junto da B1.15 que ele prova. Ver o Status da B1.15
- [x] **Step 2:** o filtro
- [x] **Step 3:** commit — ~~`fix(tenant): ...`~~ → **renomeado**, ver abaixo

**Status: ✅ entregue. 🔴 A TERCEIRA premissa deste bloco também estava errada, e
esta é do próprio plano.**

O §4.4 diz que nome, categoria, unidade e `custo_unitario` alheios "sobem para
`servicos_lista` (`:803-808`) **e para a tela de detalhes/edição da obra**". A
primeira metade é verdade; **a segunda não**. Medido nas duas rotas vivas:

* `/obras/<id>` passa `servicos_obra` para `obras/detalhes_obra_profissional.html`,
  que **não referencia a variável** — o dado chega ao template e morre lá;
* `/obras/editar/<id>` reduz a lista a IDs (`:1105`), usados só para marcar
  checkbox (`templates/obra_form.html:666`), e id alheio nunca casa com um
  serviço listado.

As duas respondem 200 **sem o nome no corpo**. Ou seja: o defeito da consulta é
real e sai por ela, mas **não é vazamento observável pelo usuário hoje** — é
exatamente a classificação que este bloco deu ao `views/obras.py:743-757`, e vale
a mesma consequência: **não entra no changelog como `fix(tenant)`**. O commit foi
renomeado para `chore(tenant)`.

**Consequência para o arreio:** o teste afirma sobre a FUNÇÃO, não sobre o corpo
da resposta. Um teste por corpo aqui seria o **sexto instrumento medindo o vazio**
desta rodada — teria passado antes e depois da correção, provando nada.

---

### Task B1.13: `admin_id` opcional no SQL de progresso por serviço — defesa em profundidade

**Files:** Modify `views/obras.py` — assinatura de `calcular_progresso_real_servico`
(`:727`), bloco SQL `:743-762`, e as duas chamadas `:826` e `:878`

**Comportamento novo.** A função aceita `admin_id=None`. Quando vier preenchido, a
**SUBCONSULTA** (dentro do WHERE de `:751-753`, junto de `r.obra_id` e
`rss2.servico_id`) ganha `AND rss2.admin_id = :admin_id`, com o bind acrescentado ao
dict de `:759-762`. Com `admin_id=None` o SQL fica idêntico ao de hoje. As duas
chamadas repassam o `admin_id` que `obter_servicos_da_obra` já tem em mãos (parâmetro
de `:776`, resolvido em `:783-784` por `get_admin_id_robusta`).

**O que isso defende de verdade:** `rdo_servico_subatividade.admin_id` é NOT NULL
(`models.py:1949`) enquanto `rdo.admin_id` é nullable (`models.py:1110`); linhas com
`admin_id` divergente do dono da obra — herança de base antiga, ver
`fix_all_admin_id_universal.py` na raiz — entram no AVG hoje.

**Teste que prova:** T4 (progresso == 40.0 com o filtro ligado).

**Riscos → mitigação.**
1. O filtro vai na subconsulta, **nunca só na query externa** — a externa (`:744-746`)
   apenas recolhe ids que a subconsulta já escolheu; filtrar lá não muda o conjunto de
   `MAX(id)` e dá falsa sensação de correção.
2. Ligar sem rede pode ZERAR o progresso de obras com linhas herdadas de `admin_id`
   errado → por isso o parâmetro é **opcional**, não incondicional.
3. O `except Exception` de `:772-774` devolve `0.0` em silêncio: um filtro errado não
   aparece como erro, aparece como 0% na tela → o teste afirma número > 0.
4. `get_admin_id_robusta` (`views/obras.py:527-568`) pode devolver None (`:562`).
   Repassar None é seguro por construção; **não** tratar None como "tenant zero".

**Commit:** a mensagem diz *defesa em profundidade*, não `fix(tenant)`.

- [x] **Step 1:** parâmetro + bind na subconsulta + as duas chamadas
- [x] **Step 2:** T4 verde com valor 40.0
- [x] **Step 3:** commit — `chore(obras): escopo de admin_id na subconsulta de progresso por serviço (defesa em profundidade)`

**Status: ✅ entregue.** Sem desvio de desenho. Uma nota de implementação:
`text()` não aceita cláusula variável, então o filtro entra por interpolação
condicional — com `admin_id=None` a linha **some** e o SQL fica byte a byte o de
antes. É o que garante o Step 2: `tests/test_cronograma_engine_unificado.py:114`
chama a função direto, sem tenant, e passou **sem edição**.

**Lembrete de sequenciamento (§11.3):** esta Task tem de continuar valendo até a
**B2.8**, que apaga a função inteira. Fazer B2.8 antes invalidaria o filtro que
acabou de entrar.

---

### Task B1.14: dedup de XML por tenant + guarda honesta de `chave_acesso`, no MESMO commit

**Files:** Modify `almoxarifado_utils.py` — `processar_xml_nfe` `:257`; e novo bloco
entre a extração de `chave_acesso` (`:273`) e a busca de fornecedor (`:280`)

**Comportamento novo.**
1. `:257` passa a `filter_by(xml_hash=xml_hash, admin_id=admin_id)`. XML idêntico já
   importado por outra empresa deixa de recusar a importação desta.
2. Guarda explícita por chave de acesso, em dois ramos: (a) mesma `chave_acesso` E
   mesmo `admin_id` → o texto já existente de `:259` ("Nota fiscal já foi importada
   anteriormente"); (b) mesma `chave_acesso` em OUTRO tenant → mensagem distinta e
   **genérica**, do tipo "Esta NF-e já está registrada em outra conta do sistema —
   acione o suporte", **sem citar nome de empresa, fornecedor, número ou valor**. É o
   preço de não poder mexer no UNIQUE agora.

**Teste que prova:** nenhum de rota — a função está morta (impacto em produção hoje:
zero). Teste de unidade chamando `processar_xml_nfe` com o mesmo XML em dois tenants,
afirmando as duas mensagens distintas e que a do ramo (b) não contém nenhum dado do
outro tenant.

**Riscos → mitigação.**
1. Fazer só a `:257` troca recusa amigável por IntegrityError 500 no flush de `:329` →
   **as duas no mesmo commit**.
2. A mensagem do ramo (b) é a superfície de vazamento inteira deste conserto: qualquer
   dado do outro tenant nela é pior que o bug original.
3. Não usar `abort()`/`first_or_404()` — é função utilitária, não rota; o contrato de
   retorno é `{'erro': ...}` e tem que continuar sendo.

- [ ] ~~**Step 1:** as duas edições juntas~~
- [ ] ~~**Step 2:** teste de unidade das duas mensagens~~
- [ ] ~~**Step 3:** commit~~

**Status: ⛔ CORTADA em 05/08 — a recomendação abaixo virou decisão do Cássio, e a
Task está na §8.1.** O texto do recorte fica aqui inteiro, porque o dia em que
`processar_xml_nfe` ganhar chamador ele volta a valer — mas só junto com a decisão
sobre o UNIQUE global. **Nada abaixo desta linha é trabalho pendente.**

A Task inteira mexe em `almoxarifado_utils.py:250-330` (`processar_xml_nfe`), e o
próprio §4.4 já registra que a função **está morta**: `grep processar_xml_nfe`
fora de `archive/` devolve **só a definição de `:250`** — nenhuma rota, template
ou job. Reconferido hoje, continua assim.

**Por que não executei mesmo assim:** o §4.4 também registra que corrigir a `:257`
sozinha **piora** — com `admin_id` na consulta o fluxo passa a alcançar o
`db.session.add` de `:328` + `flush()` de `:329` e estoura `IntegrityError`
contra o UNIQUE **global** de `NotaFiscal.chave_acesso` (`models.py:2550`),
trocando uma mensagem amigável errada por um **500**. Escrever isso em código sem
chamador é pagar risco por zero benefício.

**O que fazer com ela, em ordem de preferência:**
1. **Cortar** e mover para a §8.1, com a razão acima. Era a recomendação, e foi
   **o que se fez em 05/08**.
2. Se um dia `processar_xml_nfe` ganhar chamador, a Task volta — **e aí junto com
   a decisão sobre o UNIQUE global**, que é o defeito de verdade e é decisão de
   negócio (§12 já registra que trocá-lo por `UNIQUE (admin_id, chave_acesso)`
   não é decisão de execução).

---

### Task B1.15: fornecedor de outro tenant responde 404, não 403

**Files:** Modify `views/almoxarifado/movimentos.py:229-231`
(`processar_entrada_multipla`)

**Comportamento novo.** O status passa de 403 para 404. A mensagem já é genérica
("Fornecedor não encontrado ou sem permissão") e não muda. A rota irmã
`processar_entrada` (`:71-74`) já resolve por flash+redirect e não precisa mudar.

**Teste que prova:** T5 (404 e nada gravado).

**Risco → mitigação.** 403 confirma que o fornecedor existe em outra empresa — é
exatamente o critério que `955aeb9f` fixou e que `tests/test_gestao_custo_filho_tenant.py`
registrou. **Conferir o JS de `templates/almoxarifado/entrada.html:428`** (`fetch` para
`processar_entrada_multipla`): se ele ramifica por `response.status === 403`, o handler
tem que passar a tratar 404.

- [x] **Step 1:** 403 → 404
- [x] **Step 2:** conferir e ajustar o `fetch` do template — **nada a ajustar**, ver abaixo
- [x] **Step 3:** commit

**Status: ✅ entregue em 05/08. Com ela o bloco B1 FECHA.** O ponto era um só:
`views/almoxarifado/movimentos.py:278` respondia `403` quando o `fornecedor_id`
era de outro tenant. A consulta já filtrava `admin_id` — **o dado nunca vazou;
vazava o código**, que é um oráculo de enumeração: chutando `fornecedor_id` de 1 a
5000, o 403 desenha a base de fornecedores das outras empresas e o 404 não conta
nada.

**🔴 O T5 NÃO EXISTIA, e o Step 1 da B1.12 estava marcado dizendo que sim.** O
recorte manda "**Teste que prova:** T5", e a B1.12 tem `[x] Step 1: arreio
vermelho (T1, T2, T4, T5)` — mas `grep entrada.multipla tests/` devolvia **vazio**.
O arreio da T3 nasceu com T1-T4 e o T5 nunca foi escrito. Escrito agora, antes da
correção, e visto **vermelho pelo motivo certo** (403 ≠ 404, zero movimentos
gravados) — `tests/test_arreio_almoxarifado_e_tenant.py`,
`test_fornecedor_de_outro_tenant_na_entrada_multipla_responde_404`. **É o oitavo
instrumento defeituoso da rodada e o primeiro de um tipo novo: os sete anteriores
mediam o vazio; este não existia e a caixa estava marcada.** A lição de método é
outra, e mais barata: *antes de marcar o checkbox de um arreio, `grep` pelo nome
da rota.*

**O Step 2 não deu trabalho, e virou asserção em vez de conferência.** O `fetch`
de `templates/almoxarifado/entrada.html:428` **não ramifica por
`response.status`** — faz `await response.json()` e decide por `result.success`
(`:441-450`), então 403 e 404 são indistinguíveis para ele. Nenhum JS do
repositório ramifica por 403 (`grep 'status === 403'`: vazio). Mas o que o JS
**exige** é que o corpo siga sendo JSON — um 404 que caísse no handler de erro do
Flask devolveria HTML, o `response.json()` estouraria e o usuário veria "tente
novamente" no lugar da mensagem. Como aqui é `jsonify(...), 404` explícito, o
handler não entra; **e o teste passou a afirmar isso**, porque conferência de olho
não impede regressão.

**Nota:** a rota de formulário (`processar_entrada`) já usa 404 em
`'Item não encontrado'` e resolve fornecedor alheio por flash+redirect — mais uma
vez o mesmo arquivo responde a mesma pergunta de dois jeitos, que foi o padrão
desta sessão inteira. O flash+redirect **não é oráculo** (não devolve status
distinguível), então fica como está.

---

### Task B1.16: A09 — dedup de NF nas duas rotas de entrada

**Files:** Modify `views/almoxarifado/movimentos.py` — `processar_entrada`: após a
validação de fornecedor (`:65-74`) e antes do `if tipo_controle == 'SERIALIZADO'`
(`:76`); `processar_entrada_multipla`: FASE 1 de validação (bloco de `erros`,
`:234-301`), usando `nota_fiscal` de `:217` e `fornecedor_id` de `:219`

**Comportamento novo.**
- `processar_entrada`: se `nota_fiscal` não for vazia, procura `AlmoxarifadoMovimento`
  com `tipo_movimento='ENTRADA'`, mesma `nota_fiscal`, mesmo `fornecedor_id` e
  `admin_id`. Achando, faz flash de aviso e `redirect(url_for('almoxarifado.entrada'))`
  sem gravar movimento nem estoque.
- `processar_entrada_multipla`: mesma guarda, acrescentando um item à lista `erros`
  para sair pelo `return jsonify(...), 400` que já existe em `:296-301`. Roda **UMA
  vez** para o carrinho inteiro (a NF é do carrinho, não do item), antes do laço de
  processamento de `:307`.

**Teste que prova:** T1, T2 e T3.

**Riscos → mitigação.**
1. NF vazia é "sem chave": `request.form.get('nota_fiscal','').strip()` (`:47`) devolve
   `''`, e `''` casaria com TODA entrada anterior sem NF → a guarda sai fora quando
   `not nota_fiscal`, senão a segunda entrada sem nota do dia é recusada (T3 é a trava).
2. `fornecedor_id` é opcional (`:50`, `:65`): sem fornecedor a chave cai para
   (`nota_fiscal`, `admin_id`, `fornecedor_id IS NULL`) — **não colapsar** para
   (`nota_fiscal`, `admin_id`), senão o mesmo número de NF de dois fornecedores colide
   (ver **D7**, §10).
3. A guarda fica DENTRO do `try` de `:44` e ANTES do primeiro `db.session.add`
   (`:101` no ramo serializado, `:154` no consumível). Na rota múltipla, antes da
   FASE 2 (`:302`), porque a partir de `:330` já há `add` + `flush()`.
4. Não colocar a guarda dentro do laço de itens (`:237-294`) — a mensagem sairia
   repetida N vezes.
5. O `except Exception` largo de `:199-203` engoliria um `abort()`; hoje o caminho é
   flash+redirect e não há abort, mas se alguém trocar por abort é obrigatório um
   `except HTTPException: raise` antes de `:199`.
6. **É a única mudança do lote que altera o que o almoxarife vê na tela**, e é
   conveniência, não isolamento → vai POR ÚLTIMO e em commit isolado no fim da pilha,
   para que um revert não desfaça junto os quatro consertos de isolamento.

- [x] **Step 1:** guarda em `processar_entrada`
- [x] **Step 2:** guarda em `processar_entrada_multipla` (FASE 1)
- [x] **Step 3:** T1, T2, T3 verdes
- [~] **Step 4:** `bash run_tests.sh --gate` — **estava rodando quando a sessão fechou**
- [x] **Step 5:** commit — `feat(almox): dedup de nota fiscal na entrada manual`

**Status: ✅ código entregue; ⚠️ gate completo NÃO confirmado (ver §Histórico).**

A guarda virou um helper único, `entrada_ja_lancada`, usado pelas duas rotas. **A
chave é (tenant, nota, item)** e cada parte foi escolhida contra um erro concreto:

| Parte | Sem ela |
|---|---|
| `admin_id` | repetiria o defeito de um andar acima — o UNIQUE **global** de `NotaFiscal.chave_acesso` faz a nota de uma empresa bloquear a de outra. Numeração de NF é sequencial **por emitente**, não universal |
| `item_id` | impediria lançar o segundo item de uma nota já parcialmente dada entrada — correção normal de quem esqueceu uma linha |
| nota vazia fora da chave | a segunda compra sem nota sumiria. Entrada sem NF é rotina em obra: balcão, doação, sobra de outra obra |

Na rota de carrinho a guarda entra na **FASE 1 (validação)**, antes de qualquer
escrita: o carrinho é tudo-ou-nada e recusar no meio deixaria metade da nota
lançada.

**🔬 Sétimo instrumento vacuoso desta rodada, e o terceiro do mesmo padrão.** O
teste cross-tenant postava pelas DUAS rotas dentro do mesmo `app_context`, e o
segundo cliente não completa — o mesmo defeito de construção já registrado duas
vezes em `tests/test_arreio_custo_rdo_rotas.py`. Reescrito com **um POST só**: a
nota de A vira precondição semeada no banco, e só B posta. O que o teste precisa é
de uma precondição e **uma** ação; a segunda rota era cenário, não asserção.

---

## 5. B2 — Consertar o que o sistema informa errado

**Por que existe.** Em B1 o dado sai do sistema. Aqui o dado existe e o número exibido
mente: margem contra o próprio preço de venda, progresso que muda conforme a rota,
27,6% de encargo gravado contra 28% calculado, curva planejada apontando para um plano
que não existe mais, e uma rota que responde `success: True` para um agendamento que
nunca existiu.

**Esforço:** G. **Migração:** nenhuma. **Depende de:** B0 (verificabilidade). Não
depende de B1 — mas ver §7 sobre colisão em `event_manager.py`.

---

### 5.1 A13 — os consumidores residuais que leem `valor_orcado` (venda) como se fosse custo

Ao abrir o código o defeito é maior e mais estranho do que "margem contra o próprio
preço": há **DOIS regimes**, errados em direções opostas, e o divisor entre eles é a
existência de linhas de custo.

**O fato que amarra tudo e não está escrito em lugar nenhum:** quando um
`ObraServicoCusto` tem linhas (`ObraServicoCustoItem`), o `a_realizar_total` **É o
próprio custo orçado**. `services/cronograma_fisico_financeiro.py:739-752`
(`recalcular_osc_dos_itens`) grava `mao_obra_a_realizar = Σ linhas fonte != 'fat_direto'`,
`material_a_realizar = Σ linhas fonte == 'fat_direto'`, `outros_a_realizar = 0` — logo
`a_realizar_total == Σ linhas == custo_orcado_por_servico[id]`, por identidade. Vale
nos dois escritores vivos de linha: `services/importacao_fisico_financeiro.py:612-672`
(rota viva em `importacao_views.py:1025-1044`) e `views/obras.py:2341-2405` (recalcula
em `:2403`).

**Regime 1 — serviço COM linhas.** `utils/notifications.py:45-46` (conferido hoje) faz
`projetado = realizado + a_realizar` = `realizado + custo`, e compara com
`valor_orcado` = venda (`models.py:7544`/`:7553`). O alerta dispara quando
`realizado > venda − custo`, isto é, quando o gasto passa da **MARGEM** da etapa. Na
obra Baia (payload real: venda 1.505.613,76 / custo EAP 1.351.734,33, markup 11,4%), a
etapa Fundação tem `valor_orcado` = R$ 173.747,83 e linhas somando R$ 155.982,64 — o
alerta "estourou o orçamento" dispara com **R$ 17.766** de realizado, 11% do custo da
etapa. Não é alerta tarde demais: é **alarme falso cedo demais**, com uma mensagem
(`utils/notifications.py:73-77`) que chama preço de venda de "orçado".

**Regime 2 — serviço SEM linhas** nascido do listener comercial (`models.py:7528-7562`),
`a_realizar_total = 0`: o alerta só dispara quando `realizado > venda`. Aí sim é a
leitura do documento — tarde demais.

Os outros quatro consumidores herdam o vício sem o alerta: `models.py:7198-7200`
(`saldo`); `templates/obras/planejamento_custos/lista.html:95` mostra `s.valor_orcado`
cru na coluna "Orçado" enquanto o card `:46` da MESMA tela já mostra
`i.valor_custo_orcado` vindo de `services/resumo_custos_obra.py:262-263`;
`views/catalogo_views.py:675-676` calcula `delta_pct = (realizado − venda)/venda` e
vende isso como "Δ Realizado vs Orçado" no histórico cross-obra (rota viva, linkada de
`templates/catalogo/servicos_list.html:138`); e `services/resumo_custos_obra.py:192-198`
rateia o realizado NÃO vinculado com peso `valor_orcado/total_orcado` — distribui custo
real com peso de preço de venda.

**Limite honesto do item, que precisa ficar escrito:** onde NÃO há linha de custo,
`custo_orcado_por_servico` cai para `valor_orcado` (`services/custo_orcado.py:125`) e
continua devolvendo venda. **O regime 2 não é curável no consumo** — só na origem, que
a Decisão 3 de 03/08 adiou.

**Esforço:** M.

---

### Task B2.1: `projecao_de_custo_por_servico` — o ponto único onde mora `a_realizar_efetivo`

**Files:** Modify `services/custo_orcado.py` — novo helper ao lado de
`custo_orcado_por_servico` (`:93-128`), reaproveitando a agregação de `:113-122`

**Comportamento novo.** `projecao_de_custo_por_servico(obra_id, admin_id) ->
{osc_id: {'orcado','tem_linhas','realizado','a_realizar_efetivo','projetado','saldo'}}`.
Regra: `orcado` é o que `custo_orcado_por_servico` já devolve (linha vence agregado);
`tem_linhas` é a soma das linhas > 0; **`a_realizar_efetivo = max(orcado - realizado, 0)`
quando há linhas** (porque nesse caso o `a_realizar_total` gravado É o próprio orçado) e
`= a_realizar_total` quando não há (fluxo manual, onde o gestor mantém o campo à mão);
`projetado = realizado + a_realizar_efetivo`; `saldo = orcado - projetado`. **Uma query
por obra**, nada por serviço.

**Teste que prova:** unidade — serviço com duas linhas (68.100 `veks` + 87.882,64
`fat_direto` = 155.982,64) e `valor_orcado=173.747,83`, com `realizado=20.000`:
`a_realizar_efetivo == 135.982,64` e `projetado == 155.982,64` (não 175.982,64).

**Risco → mitigação.** Sem o `a_realizar_efetivo` a troca da base vira **avalanche**:
com linhas, `realizado + a_realizar` = `realizado + orcado`, então QUALQUER realizado > 0
passaria a estourar. É a armadilha central do item. Manter o try/except do módulo
(`:88`, `:126`) devolvendo dict vazio — e o chamador trata dict vazio como "não sei",
nunca como zero.

- [x] **Step 1:** o helper
- [x] **Step 2:** teste de unidade dos dois regimes
- [x] **Step 3:** commit

**Status: ✅ entregue em 05/08. Primeira Task do B2.** Entregue como o recorte
mandava, com dois desvios pequenos e um método aplicado:

1. **A agregação virou `_servicos_e_somas`, e `custo_orcado_por_servico` passou a
   chamá-la.** O recorte dizia "reaproveitando a agregação de `:113-122`"; copiá-la
   seria criar o segundo lugar onde "linha vence agregado" mora — que é exatamente
   o defeito que este módulo nasceu para acabar. Extração pura, sem mudança de
   comportamento; o único consumidor vivo de `custo_orcado_por_servico` é
   `services/cronograma_fisico_financeiro.py:288`.
2. **O teste foi para `tests/test_p3_p9_orcado_e_contrato.py`**, não para arquivo
   novo: mesmo módulo sob teste, mesmos helpers, e o teste de convergência do p3
   já mora lá.
3. **Os dois regimes foram cobrados por SABOTAGEM, não por leitura.** Os cinco
   testes passaram de primeira, e nesta rodada isso não conta como prova (lição de
   04/08, noite, item 3). Trocando o helper pelo ramo errado, um por vez:
   *sempre* `a_realizar_total` → caem os dois de linhas; *sempre*
   `max(orcado − realizado, 0)` → cai o de fluxo manual. **Cada ramo tem quem o
   cobre**, e nenhum dos cinco é vacuoso.

**O que o teste da obra Baia trava, e é a razão do item inteiro:** com linhas, o
`a_realizar_total` gravado É o orçado (155.982,64) — identidade de
`recalcular_osc_dos_itens`. `projetado = realizado + a_realizar_total` daria
**175.982,64** para uma etapa que orçou 155.982,64 e gastou 20.000. Qualquer
realizado > 0 estoura. É a avalanche que o §11.3 previu, e agora ela tem um teste
com o número dela dentro.

---

### Task B2.2: o alerta de estouro passa a comparar custo com custo

**Files:** Modify `utils/notifications.py` — `servico_estourou` (`:33-59`; leitura
`:40`, comparação `:46-49`) e `verificar_estouros_obra` (`:126-166`, chamada `:151`);
Modify `views/planejamento_custos_views.py:88-108` (após `:98`, antes do render de
`:101-108`)

**Comportamento novo.** `verificar_estouros_obra` chama
`projecao_de_custo_por_servico(obra_id, tenant_admin_id)` **uma vez**, antes do loop de
`:150`, e repassa a entrada do serviço para `servico_estourou(svc, projecao=None)`. Sem
`projecao`, comportamento de hoje (compatibilidade). Com `projecao`, o estouro é
`projetado > orcado` com os números do helper, e o dict devolvido (`:50-59`) troca
`valor_orcado` por custo e `a_realizar` por `a_realizar_efetivo`. A mensagem de `:73-77`
passa a dizer "custo orçado". A rota calcula a projeção e passa ao template — é o mesmo
número que o card "Valor Custo Orç." do cabeçalho já usa via `calcular_resumo_obra`
(`:93` → `services/resumo_custos_obra.py:262-263`).

**Efeito concreto:** etapa Fundação da Baia — hoje alerta a partir de R$ 17.766 de
realizado; passa a alertar a partir de R$ 155.982,64.

**Teste que prova:** `tests/test_a13_orcado_de_custo_no_consumo.py`, **nível rota**.
`ObraServicoCusto` 'Fundação' com `valor_orcado=173747.83` e DUAS
`ObraServicoCustoItem` (68100 `veks` + 87882.64 `fat_direto`), reproduzindo o estado que
`recalcular_osc_dos_itens` grava (`mao_obra_a_realizar=68100`,
`material_a_realizar=87882.64`, `outros_a_realizar=0`), `override_realizado_manual=True`
e `realizado_mao_obra=20000`. Então
`cliente_de(a.admin_id).get(f'/obras/{a.obra_id}/planejamento-custos/')`.

- **1º GET:** `NotificacaoOrcamento.filter_by(obra_id, ativa=True).count() == 0` — 20.000
  está dentro dos 155.982,64. **Hoje esse mesmo GET grava UMA notificação ativa**
  (projetado = 20.000 + 155.982,64 = 175.982,64 > 173.747,83); é esse registro no banco
  que prova o defeito. **É também a asserção de não-avalanche**, a que protege contra a
  correção ingênua.
- **2º GET** (após `realizado_mao_obra = 160000`): exatamente uma `NotificacaoOrcamento`
  ativa, com `valor_orcado == Decimal('155982.64')` (custo, não os 173.747,83),
  `valor_projetado == Decimal('160000.00')`, `valor_excesso == Decimal('4017.36')`.
- **Tenant:** GET de B na obra de A → 404, e nenhuma `NotificacaoOrcamento` de A criada
  ou apagada.

**Por que o atual não pegava.** Os testes do p3
(`tests/test_p3_p9_orcado_e_contrato.py:68-101`) chamam
`custo_orcado_da_obra`/`custo_orcado_por_servico` **direto**, em nível de serviço:
provam que a fonte nova calcula certo e não fazem uma única afirmação sobre quem ainda
lê a fonte velha. O resto do arquivo é pior — `:146-165` abre o arquivo e roda regex no
TEXTO. Não existe no repo nenhum teste que faça GET em `/obras/<id>/planejamento-custos/`
nem que instancie `NotificacaoOrcamento`; `tests/test_resumo_custos_obra.py` chama os
serviços em processo e seus serviços **nunca têm `ObraServicoCustoItem`** (`:516-521`),
que é justamente o divisor entre os dois regimes.

**Riscos → mitigação.**
1. O gate de `:41` (`if valor_orcado <= 0: return None`) tem que continuar valendo
   **sobre o custo**, senão serviço sem orçado nenhum começa a alertar.
2. Se o mapa vier vazio (exceção engolida em `custo_orcado.py:126`), **NÃO** cair para
   zero: logar WARNING e usar o caminho antigo, senão falha de query vira estouro
   universal.
3. A rota é GET e **já grava** (o commit está dentro de `verificar_estouros_obra`,
   `utils/notifications.py:158`) → não acrescentar um segundo commit.
4. As `NotificacaoOrcamento` já gravadas se corrigem sozinhas: `_upsert_notificacao`
   (`:62-103`) reescreve a linha e `_resolver_notificacao` (`:106-123`) desativa quem
   deixou de estourar, ambas no primeiro GET. **Nenhum backfill.**

- [ ] **Step 1:** escrever o teste e vê-lo VERMELHO no 1º GET (hoje acha uma notificação ativa)
- [ ] **Step 2:** `utils/notifications.py` + a leitura na rota
- [ ] **Step 3:** teste verde nos três blocos de asserção
- [ ] **Step 4:** commit — `fix(custo): alerta de estouro compara custo com custo, não com preço de venda`

---

### Task B2.3: a coluna "Orçado" da tela de planejamento passa a fechar com o cabeçalho

**Files:** Modify `views/planejamento_custos_views.py:101-108`;
`templates/obras/planejamento_custos/lista.html:95` (e `:98` se a **D4** (§10) já
tiver saído)

**Comportamento novo.** A coluna Orçado renderiza `projecao[s.id].orcado` (fallback
para `s.valor_orcado` quando a chave faltar) e o cabeçalho vira **"Custo Orçado"**. Se
a decisão do Saldo já existir, `:98` renderiza `projecao[s.id].saldo`. Na Baia, a linha
Fundação cai de R$ 173.747,83 para R$ 155.982,64 (−R$ 17.765,19, −10,2%) e a soma da
coluna passa a bater com o card de `:46`.

**Teste que prova:** asserção complementar do teste de B2.2 — no corpo do 1º GET, a
string do "Orçado" da linha é 155.982,64 e não 173.747,83.

**Risco → mitigação.** Com a regra do helper, o Saldo de serviço com linhas fica 0,00
enquanto se está dentro do orçamento e só fica negativo no estouro — uma coluna de
zeros. Entregar a coluna Orçado e deixar Saldo como está é aceitável, **mas aí a linha
não fecha** (orçado − realizado − a_realizar dá negativo por construção). **Não deixar
as duas metades em regras diferentes**: ou sai com a **D4** respondida, ou o
cabeçalho renomeado deixa explícito que Saldo ainda é a régua antiga.

- [ ] **Step 1:** rota passa `projecao`
- [ ] **Step 2:** coluna Orçado + cabeçalho
- [ ] **Step 3:** commit — `fix(ui): coluna Orçado da tela de planejamento passa a exibir custo`

---

### Task B2.4: remover a property `ObraServicoCusto.saldo`

**Files:** Modify `models.py:7198-7200` (junto de `realizado_total` `:7190-7192` e
`a_realizar_total` `:7194-7196`)

**Comportamento novo.** Depois de B2.3, esta property fica **sem nenhum leitor no
repo** (`grep -rn '\.saldo\b'` só devolve `lista.html:98`, e depois `ContaReceber`,
`GestaoCustoPai` e `ContaContabil`, que são outras classes). Remover. Se a remoção
assustar, trocar o corpo por um docstring dizendo que `valor_orcado` é venda na cadeia
comercial e que custo se pede a `services/custo_orcado.py` — mas a preferência é
remover: property em modelo é o convite mais barato para o vício voltar.

**Teste que prova:** `bash run_tests.sh --gate` verde e grep vazio.

**Risco → mitigação.** **Não** trocar o corpo por uma chamada a
`custo_orcado_por_servico`: property de modelo que dispara duas queries por linha
renderizada é N+1 garantido na lista. E remover antes de B2.3 quebra a tela.

- [ ] **Step 1:** grep de confirmação
- [ ] **Step 2:** remoção
- [ ] **Step 3:** commit — `chore(models): remove ObraServicoCusto.saldo (sem leitor após A13)`

---

### Task B2.5: histórico do serviço no catálogo compara realizado contra custo

**Files:** Modify `views/catalogo_views.py` — `servico_historico` (`:658-715`), loop
`:673-700` (`orcado` `:675`, `delta_pct` `:676`, agregados `:702-711`)

**Comportamento novo.** O "Orçado (R$)" por obra e o Δ% passam a ser o custo orçado
daquele serviço naquela obra.

**Efeito, e é o mais desconfortável do item:** para um serviço vendido com 11,4% de
markup e realizado em 90% do custo, a tela mostra hoje Δ ≈ −19% (verde, "saiu abaixo do
orçado"); passa a mostrar ≈ −10% e, quando o realizado passa o custo sem passar a venda,
**muda de verde para vermelho**. É a tela que o usuário usa para precificar proposta
nova.

**Teste que prova:** GET em `/catalogo/servico/<id>/historico` com a mesma semente de
B2.2, afirmando o Δ% no corpo.

**Riscos → mitigação.**
1. N+1: o loop varre `ObraServicoCusto` de VÁRIAS obras (`:663-667`) e já faz um SELECT
   de quantidade por linha (`:679-683`) → **uma chamada por obra**, memoizada num dict
   fora do loop, no padrão que `services/cronograma_fisico_financeiro.py:287-288` já usa.
2. Manter o fallback `mapa.get(c.id, float(c.valor_orcado or 0))` — nunca
   `mapa.get(id, 0)`.

- [ ] **Step 1:** memoização por obra + troca da base
- [ ] **Step 2:** teste de rota do Δ%
- [ ] **Step 3:** commit — `fix(catalogo): histórico do serviço compara realizado contra custo orçado`

---

### Task B2.6: o rateio do realizado não vinculado passa a pesar por custo

**Files:** Modify `services/resumo_custos_obra.py` — `recalcular_obra`, pesos
`:192-204` (`total_orcado` `:192`, `w` `:198`) e docstring `:115-120`

**Comportamento novo.** O peso do rateio do realizado NÃO vinculado passa a ser
custo orçado / total de custo orçado dos alvos, via
`custo_orcado_por_servico(obra_id, admin_id)`. O TOTAL distribuído **não muda**
(Σw = 1 nos dois casos) — muda a distribuição entre serviços, e só quando a razão
venda/custo difere entre etapas.

**Onde muda e onde não muda.** Na importação físico-financeira **não** difere:
`services/importacao_fisico_financeiro.py:538` faz `venda_item = valor_venda × peso_pct`
e `peso_pct` é a fatia de CUSTO da etapa (conferido no payload da Baia:
51.159,69/1.351.734,33 = 0,0378) — lá a redistribuição é ruído de arredondamento. Onde
muda de verdade é na **cadeia comercial normal, com margem por item** — e é onde importa,
porque o realizado por serviço alimenta o alerta de estouro e o "custo médio realizado
por unidade" do catálogo (`views/catalogo_views.py:707`), que é o número usado para
precificar a próxima proposta.

**Teste que prova:** duas etapas com razão venda/custo diferente, realizado não
vinculado conhecido; afirmar a distribuição nova e que a **soma** não mudou.

**Riscos → mitigação.**
1. `recalcular_obra` roda dentro de `after_flush_postexec` (`models.py:7386-7435`,
   chamada em `:7420`) → a query nova entra no mesmo ponto onde `:130-155` já consultam,
   mas **não pode disparar flush novo** nem escapar do guard de reentrância de
   `:7404-7406`.
2. Mapa vazio → `total_orcado` daria 0 e o rateio cairia silenciosamente para uniforme
   (`:199-200`) → manter o fallback, **mas logar**.
3. Peso MISTO: obra com etapa importada (peso = custo) ao lado de etapa manual (peso =
   `valor_orcado` digitado) mistura unidades — hoje já mistura venda com custo do mesmo
   jeito, então não é regressão, mas precisa estar no docstring de `:115-120`. A
   referência a `resumo_custos_obra.py:191` no docstring de `services/destino_custo.py:24`
   fica desatualizada.
4. **É o que reescreve `realizado_material/mao_obra/outros` no banco**, alimentando
   B2.2, B2.3 e B2.5 → vai **por último** no A13, senão os testes das Tasks anteriores
   mudam de resposta no meio do caminho.

- [ ] **Step 1:** trocar o peso + docstring
- [ ] **Step 2:** teste da distribuição e da soma
- [ ] **Step 3:** `bash run_tests.sh --gate`
- [ ] **Step 4:** commit — `fix(custo): rateio do realizado não vinculado pesa por custo orçado`

> **Fecho obrigatório do A13, para não esconder metade do problema:** *o consumo está
> fechado onde existe linha de custo; o serviço sem linha continua com venda no lugar de
> custo e só a correção na origem (Decisão 3 de 03/08) resolve.*

---

### 5.2 A19 — a família V1 de progresso: sete call-sites, e um que deve morrer em vez de convergir

> **Contradição registrada (ver §9, nº 2).** A reconferência (§7, linha A19) manda
> consolidar a família V1 em `_progresso_fallback_subatividades`. **O recorte derruba
> isso, e adotamos o recorte.** `_progresso_fallback_subatividades` existe
> (`utils/cronograma_engine.py:1024-1041`) e tem exatamente um consumidor,
> `progresso_geral_para_kpi` (`:1117`). Ela responde "média simples das subatividades do
> ÚLTIMO RDO da obra" — um retrato de um dia. **Nenhum dos sete pergunta isso.** Mandar
> os sete para lá trocaria acumulados por um número de um dia só, que decresce quando o
> apontador corrige para baixo.

As variantes, abertas uma a uma:

| Var. | Onde | Chave de agrupamento | Agregador | Problema |
|---|---|---|---|---|
| **A** | `views/rdo.py:1302-1345` (`GET /rdo/<id>`) | `f"{servico_id}_{nome}"` | percentual do RDO mais recente | Numerador e denominador de universos diferentes: `total_subatividades_obra` (`:1252-1266`) conta TODA `SubatividadeMestre` ativa — **o catálogo planejado, não o apontado**. Pode passar de 100%; e nunca chega a 100 com a obra pronta. Query de `:1310-1316` **sem `RDO.admin_id`**, `.desc()` sem desempate por `RDO.id` |
| **B** | `views/rdo.py:2519-2538` (consolidada) | `nome_subatividade` **só** | `MAX(percentual)` com teto de data, filtra `admin_id` | Monotônico. Homônimos de serviços diferentes **colidem** |
| **B'** | `views/rdo.py:2653-2670` (o `except` de `:2613`) | idem B | idem B | **A ordem dos ramos está invertida**: o principal testa `if obra_em_v2:` (`:2510`), o fallback testa `if total_subatividades > 0:` (`:2653`). Obra híbrida devolve V2 no caminho feliz e V1 no fallback — mesma rota, mesma obra, dois números |
| **C** | `views/rdo.py:219-236` **e** `:381-398` (duas cópias em `rdos()`) | `nome_subatividade` | valor do RDO de **data mais recente** | **Não é monotônico** — correção para baixo derruba o número, ao contrário do que o comentário de `:217-218` promete. E o cache é por `obra_id` (`:219`, `:382`), **sem teto de data**: toda linha da lista mostra o mesmo número |
| **D** | `crud_rdo_completo.py:130-136` | — | `sum/len` do RDO da linha | Não acumula. Obra V1 a 80% cujo RDO do dia não teve subatividade mostra **0** |
| **E** | `services/rdo_pdf_service.py:179-205` (chamada `:524`) | idem B | idem B | A detecção V2 de `:185-191` consulta `TarefaCronograma` **sem `ativa`, sem `is_cliente=False` e sem `is_v2_active()`**, enquanto `views/rdo.py:1383-1389` exige `is_v2_active()`. Uma tarefa cópia-cliente joga o PDF para V2 enquanto a tela fica em V1 |
| **F** | `views/obras.py:727-770` | — | `AVG` sobre `MAX(rss2.id)` por nome | **Não é progresso de obra — é por SERVIÇO.** Usa `MAX(id)` como proxy de data (o comentário de `:735` admite). E **o resultado é jogado fora**: `:826`/`:878` gravam em `servico['progresso']`, `editar_obra` guarda só os ids (`:1105`) e `detalhes_obra_profissional.html` **nunca lê `servicos_obra`** |

**O que cada um alimenta — nenhum alimenta dinheiro.** A → `templates/rdo/visualizar_rdo_moderno.html:1256`;
B/B' → cards da consolidada; C → lista de RDOs; D → segunda lista;
E → o **PDF** baixado em `views/rdo.py:1659-1691`, o documento por trás do ato de
ciência do cliente — **o mais pesado dos sete**, não por mover dinheiro, mas por virar
papel assinado; F → **nada**.

**O sexto gerador de medição** (`services/medicao_service.py:197-198`,
`Σ valor_executado_acumulado / valor_contrato × 100`) **não entra neste item**: é
ponderação por VALOR sobre itens comerciais, universo disjunto de
`RDOServicoSubatividade`, e `medicao.valor_medido` sai de `total_medido_periodo`
(`:193`), que já virou `ContaReceber` via `recalcular_medicao_obra` (`:206`). Isso é
A15 + Decisão 4 — consolidá-lo aqui seria mexer em dinheiro já emitido.

**A Decisão 4 (`PLANO-NUCLEO.md:541`) não trava este item.** Confirmado percorrendo os
consumidores: nenhum dos sete escreve em `MedicaoObra`, `MedicaoObraItem`,
`ItemMedicaoComercial` ou `ContaReceber`. Os dois pontos que multiplicam
`valor_contrato` são `portal_obras_views.py:772-773` e
`services/medicao_service.py:160-162`, ambos fora deste recorte. **A família V1 é 100%
leitura, para tela e PDF.**

> **Confiança:** a reconferência marca A19 como **média-alta** — alta nas omissões
> verificadas, **média** em afirmar que não existe um sétimo caminho, porque o app não
> foi executado. Este recorte abriu os sete e não achou o oitavo; a ressalva permanece.

**Esforço:** G.

---

### Task B2.7: `progresso_v1_acumulado` + `obra_em_modo_v2` no engine

**Files:** Modify `utils/cronograma_engine.py` — nova função irmã entre
`_progresso_fallback_subatividades` (termina em `:1041`) e
`progresso_ponderado_armazenado` (`:1043`); e o predicado ao lado (ou em `utils/tenant.py`,
casa de `is_v2_active`)

**Comportamento novo.**

`progresso_v1_acumulado(obra_id, admin_id, ate_data) -> float`: para cada chave
`(servico_id, nome_subatividade)` da obra, o MAIOR `percentual_conclusao` registrado em
qualquer RDO com `RDO.data_relatorio <= ate_data` e `RDO.admin_id == admin_id`; média
simples desses máximos, arredondada a 1 casa; zero quando não há chave. **Uma única SQL**
com `GROUP BY servico_id, nome_subatividade` e `MAX(...)` — sem loop em Python, sem N+1.

Cada escolha, e o porquê: **MAX** e não "último por data", porque é a única forma
monotônica no tempo, propriedade que os comentários de `views/rdo.py:2520-2524` e
`:217-218` já prometem e só B entrega; **chave COMPOSTA com `servico_id`**, porque
B/C/E colapsam homônimos e sub-contam; **`admin_id` obrigatório**, porque A e F não
filtram; **`ate_data` obrigatório**, porque C não tem teto.

`obra_em_modo_v2(obra_id, admin_id) -> bool`: `is_v2_active()` **E** existe
`TarefaCronograma` da obra com `ativa is True` e `is_cliente=False`. Passa a ser o único
jeito de responder "esta obra é V2?".

**Teste que prova:** unidade sobre as duas funções (parte do arquivo da Task B2.8).

**Riscos → mitigação.**
1. Não reaproveitar `_progresso_fallback_subatividades` como destino (motivo acima) e
   **não a tocar** — ela segue servindo `progresso_geral_para_kpi` em `:1117`.
2. **Não** filtrar por `RDOServicoSubatividade.ativo`: A, B, C, D e E hoje **não**
   filtram (só F filtra, `views/obras.py:748`, `:754`); acrescentar agora mudaria número
   por um motivo que não é este item.
3. Hoje há **quatro** predicados V2 vivos e diferentes (`views/rdo.py:1383-1389`,
   `:2497-2502`, `crud_rdo_completo.py:110-116`, `services/rdo_pdf_service.py:185-191`).
   Adotar o estrito muda de ramo obras que hoje caem em V2 por causa de uma tarefa
   cópia-cliente — **intencional, e é metade da convergência**, mas é mudança de número
   visível e precisa entrar no mesmo commit que a fórmula em cada call-site.

- [ ] **Step 1:** as duas funções + teste de unidade
- [ ] **Step 2:** nenhum call-site trocado ainda — nada muda em produção
- [ ] **Step 3:** commit — `feat(cronograma): progresso_v1_acumulado e obra_em_modo_v2 como ponto único`

---

### Task B2.8: apagar `calcular_progresso_real_servico` — a que deve morrer

**Files:** Modify `views/obras.py` — `calcular_progresso_real_servico` (`:727-770`) e
os dois laços (`:825-827`, `:877-879`), dentro de `obter_servicos_da_obra` (`:776`);
Delete `tests/test_cronograma_engine_unificado.py:87-114`

**Comportamento novo.** A função e os dois laços saem. `servico['progresso']` conserva
o valor já atribuído antes — `round(float(servico_obra_real.percentual_concluido), 1)`
em `:816` no caminho principal, `0.0` em `:866` no fallback. **Nada muda na tela**,
porque nada renderiza essa chave. Some uma SQL por serviço a cada `GET /obras/<id>` e a
cada `GET /obras/<id>/editar`.

**Vem PRIMEIRO entre os call-sites, e é remoção, não consolidação:** F é a única que
pergunta "progresso deste SERVIÇO", e forçá-la a virar progresso de obra seria trocar um
número por outro que responde outra coisa. Deixá-la para depois é convidar quem executa
a fundi-la por engano com as outras seis.

**Teste que prova:** `bash run_tests.sh --gate` verde após remover o teste de
caracterização, e o T4 da Task B1.13 continua verde (o valor 40.0 vem do outro caminho).

> **Colisão com B1.13.** B1.13 acrescenta `admin_id` a esta mesma função. As duas Tasks
> tocam `views/obras.py:727-770`. **Ordem obrigatória: B1.13 antes de B2.8** — o filtro
> entra, é validado pelo T4, e depois a função inteira sai. Fazer B2.8 primeiro
> invalida o T4. Ver §7.

**Riscos → mitigação.**
1. Se algum consumidor novo (endpoint JSON, parcial, htmx) tiver passado a ler
   `servicos_obra` depois desta conferência, ele passa a ver
   `ServicoObraReal.percentual_concluido` em vez do derivado →
   `grep -rn 'servicos_obra\|obter_servicos_da_obra' templates/ static/` **imediatamente
   antes de apagar**. Hoje o resultado é `templates/obra_form.html:663,666`,
   `templates/obras/detalhes_obra.html:245,261` (template que nenhuma rota renderiza) e
   os dois chamadores Python.
2. O docstring de `tests/test_cronograma_engine_unificado.py:1-14` nomeia a função em
   `:5` → corrigir junto, registrando **por que** (número descartado, não migrado).

- [ ] **Step 1:** grep de confirmação em `templates/` e `static/`
- [ ] **Step 2:** remover função, laços e o teste de caracterização; corrigir o docstring
- [ ] **Step 3:** commit — `chore(obras): remove calcular_progresso_real_servico — o número era descartado`

---

### Task B2.9: PDF do RDO e detalhe do RDO convergem, NO MESMO COMMIT

**Files:** Modify `services/rdo_pdf_service.py` — `_progresso_geral` (`:179-205`),
chamada `:524`; Modify `views/rdo.py` — `visualizar_rdo` (`:1091`): bloco `try` de
`:1236-1363` e bloco de sobrescrita V2 `:1371-1406`

**Comportamento novo.**
- `_progresso_geral` vira duas linhas: se `obra_em_modo_v2(rdo.obra_id, admin_id)`,
  devolve `calcular_progresso_geral_obra_v2(...)['progresso_geral_pct']`; senão
  `progresso_v1_acumulado(rdo.obra_id, admin_id, rdo.data_relatorio)`. O parâmetro
  `subatividades_count` deixa de decidir ramo (a função nova já devolve 0 sem chave) e
  some da assinatura, junto com o argumento em `:524`.
- Em `visualizar_rdo`, os dois blocos colapsam em um. O `except Exception` de
  `:1349-1363`, que reimplementa a fórmula uma terceira vez dentro da mesma função,
  some.

**Consequência declarada:** o denominador do ramo V1 deixa de ser o catálogo planejado
e passa a ser o nº de chaves apontadas — **o percentual desta tela sobe** para obras
com `SubatividadeMestre` cadastrada e não apontada, e deixa de poder passar de 100%.
É a **D5** (§10).

**Riscos → mitigação.**
1. **Separar PDF e tela abre uma janela em que o papel que o cliente assina e a tela do
   apontador mostram números diferentes** → mesmo commit, sem exceção.
2. `total_subatividades_obra` **não pode sair junto**: o template lê em
   `templates/rdo/visualizar_rdo_moderno.html:1258` ("N subatividades total"). Preservar
   o cálculo de `:1240-1266` SÓ para esse rótulo, desacoplado do percentual — senão o
   rótulo muda de significado no mesmo commit em que o número muda e ninguém consegue
   atribuir a diferença.
3. Na sobrescrita V2 atual, `:1395-1400` conta TODA `TarefaCronograma` da obra para
   virar `total_subatividades_obra` — com o predicado estrito essa contagem também
   precisa ganhar `ativa`/`is_cliente=False`, senão o rótulo passa a contar cópia-cliente.
4. `peso_por_subatividade` (`:1304`, passado em `:1635`) não é lido por template nenhum
   → pode sair do `render_template` junto.
5. O `try/except Exception: pass` de `services/rdo_pdf_service.py:184-193` hoje engole
   falha de import e cai em V1 silenciosamente → ao substituir, deixar a exceção subir ou
   logar. **PDF que mente o percentual é pior que PDF que falha.**

**Teste:** ver Task B2.12.

- [ ] **Step 1:** `_progresso_geral` + `visualizar_rdo`, juntos
- [ ] **Step 2:** conferir o rótulo de `:1258` preservado
- [ ] **Step 3:** commit — `fix(rdo): PDF e detalhe do RDO usam a mesma fórmula de progresso V1`

---

### Task B2.10: consolidada — caminho feliz e fallback alinhados

**Files:** Modify `views/rdo.py` — `funcionario_rdo_consolidado` (`:2382`): caminho
principal `:2508-2541` e o gêmeo do `except` `:2648-2682`

**Comportamento novo.** Ambos chamam as mesmas duas funções, e o ramo
`if obra_em_modo_v2(...)` vem **primeiro nos DOIS**. Os caches `_cache_prog_v1`
(`:2461`) e `_fb_cache_prog_v1` (`:2624`) continuam, chaveados por
`(obra_id, data_relatorio)`, guardando o retorno da função nova.

**Riscos → mitigação.**
1. A inversão de ramo entre `:2510` e `:2653` **é bug que muda número**, não estilo:
   obra híbrida devolve V2 no feliz e V1 no fallback.
2. **Não deletar o bloco de fallback inteiro** na mesma passada — ele é o que segura a
   rota quando o schema está atrás da migração 48 (o `except` de `:2545-2554` é explícito).
3. Inserir `except HTTPException: raise` antes do catch-all de `:2613`, que hoje
   engoliria um `abort()`.

- [ ] **Step 1:** as duas metades
- [ ] **Step 2:** commit — `fix(rdo): consolidada — mesmo ramo e mesma fórmula no caminho feliz e no fallback`

---

### Task B2.11: as duas cópias em `rdos()` ganham teto de data

**Files:** Modify `views/rdo.py` — `rdos()` (`:52`, rotas `/rdo`, `/rdo/`, `/rdo/lista`):
cópias em `:204-236` e `:366-398`

**Comportamento novo.** As duas viram a mesma chamada, com `ate_data=rdo.data_relatorio`.
Os caches `_cache_prog_v1` (`:169`) e `_cprog_v1` (`:382`) mudam de chave `obra_id` para
`(obra_id, data_relatorio)`.

**Consequência declarada:** cada linha da lista passa a mostrar o acumulado até a data
DAQUELA linha, em vez de todas as linhas da mesma obra mostrarem o mesmo número; e o
número deixa de cair quando o RDO mais recente traz correção para baixo.

**Riscos → mitigação.**
1. São duas cópias na mesma função, com nomes de cache diferentes e destinos diferentes
   (`progresso_real` × `rdo.progresso_total`) → **trocar as duas ou nenhuma**: deixar uma
   é reintroduzir a divergência dentro de uma única rota.
2. `views/rdo.py:398` atribui `rdo.progresso_total` num objeto ORM vivo na sessão →
   **conferir em `models.py` se `RDO.progresso_total` é coluna**. Se for, trocar por um
   dicionário paralelo `{rdo.id: pct}` passado ao template, como o caminho gêmeo de
   `:236` já faz com a variável local; qualquer `commit()` posterior tentaria persistir,
   e se não for coluna, apenas suja a identity map.

- [ ] **Step 1:** as duas cópias + chave de cache
- [ ] **Step 2:** conferir `RDO.progresso_total` em `models.py`
- [ ] **Step 3:** commit — `fix(rdo): lista de RDOs mostra o acumulado até a data da própria linha`

---

### Task B2.12: `crud_rdo_completo.listar_rdos` + o teste de convergência

**Files:** Modify `crud_rdo_completo.py` — `listar_rdos` (`:45`): detecção V2 `:110-117`
e cálculo `:121-136`; Create `tests/test_a19_progresso_v1_convergencia.py`

**Comportamento novo.** Detecção passa por `obra_em_modo_v2`; o ramo V1 (`:131-134`)
troca a média das subatividades do próprio RDO por
`progresso_v1_acumulado(rdo.obra_id, admin_id, rdo.data_relatorio)`. RDO cujo dia não
teve subatividade deixa de exibir 0 para uma obra que está a 80%. O `elif subatividades:`
de `:131` vira chamada **incondicional** no ramo não-V2 — mantê-lo como guarda anula
metade da correção.

**O teste — escrito na Task B2.7 e vermelho até aqui.** É ele que diz quando o item
acabou. Um tenant de `dois_tenants('a19')`, obra **sem nenhuma `TarefaCronograma`** (o
que força o ramo V1 nos sete pontos de uma vez). Dois `Servico` do mesmo admin, S1 e S2,
cada um com uma subatividade chamada 'Preparação' (o homônimo é deliberado). Três RDOs
com datas **ancoradas na semente** — 2026-06-10/11/12, dentro do mês fixo que
`dois_tenants` usa, nunca `date.today()`. Linhas: (S1,'Preparação') 30 no dia 10, 60 no
dia 11, **40 no dia 12** (a correção para baixo, que separa MAX de "último");
(S2,'Preparação') 20 só no dia 10; (S1,'Corte') 100 no dia 11.

| # | Asserção |
|---|---|
| 1 — **Convergência** | O percentual até 11/06 é o mesmo em `/rdo/<id_11>`, `/rdo/<id_11>/pdf`, `/funcionario/rdo/consolidado` e `/rdo/lista`. Com a fórmula nova é **60.0** — média dos máximos de três chaves compostas: (S1,'Preparação')=60, (S2,'Preparação')=20, (S1,'Corte')=100 → 180/3. **Hoje nenhuma das quatro devolve isso**: o detalhe divide pelo catálogo mestre; a consolidada e o PDF fundem os dois 'Preparação' num MAX=60 e devolvem (60+100)/2=**80**; `/rdo/lista` ignora o teto e usa o 40 do dia 12 |
| 2 — **Monotonicidade** | o percentual até 12/06 é `>=` o de 11/06, apesar da correção de 60 para 40 |
| 3 — **Estado do banco** | `SELECT id, percentual_conclusao FROM rdo_servico_subatividade` ordenado por id, coletado antes dos quatro GETs, idêntico depois; e `count(*) FROM medicao_obra WHERE obra_id=<obra>` continua 0. Este item é 100% leitura — a asserção é a NEGATIVA, e ela precisa existir porque um `commit()` acidental num caminho de listagem é a classe de regressão que ninguém vê (vale especialmente para `views/rdo.py:398`) |
| 4 — **Cross-tenant** | GET do admin B em `/rdo/<id_11>` responde **302** com `Location` para `/funcionario/rdo/consolidado`, e o corpo seguido do redirect não contém o número da obra de A. **Afirmar 302, não 404:** `views/rdo.py:1111-1113` usa `flash` + `redirect`. Isso contraria a regra da casa e é achado real, mas é anterior a este item — o teste registra o comportamento vigente e a correção vira item separado |

O número do PDF sai chamando `services.rdo_pdf_service._progresso_geral` com o mesmo
`rdo` (os bytes não são inspecionáveis, mas é a mesma função que `:524` usa); o da tela
sai do HTML renderizado (`templates/rdo/visualizar_rdo_moderno.html:1256`).

**Por que o atual não pegava.** `tests/test_p4_formula_unica_progresso.py` não exercita
nenhuma rota da família V1: `:141-146` abre `portal_obras_views.py` e checa
`'progresso_ponderado_armazenado' in texto`; `:154-160` abre
`templates/obras/cronograma.html`; `:163-171` abre `views/dashboard.py`; `:174-181` abre
`cronograma_views.py`. Um assert de substring vira verdadeiro assim que o nome aparece
EM QUALQUER LUGAR — inclusive num comentário ou num ramo morto. Não vê ramo, não vê
ordem de `if`, não vê chave de agrupamento, não vê filtro de `admin_id` — e sobretudo
**o teste só abre quatro arquivos**: `views/rdo.py`, `services/rdo_pdf_service.py` e
`crud_rdo_completo.py` **não são abertos por teste nenhum do p4**. Foi assim que o
pacote pôde declarar "cinco fórmulas viram uma" com o gate verde.

**Riscos → mitigação (do item inteiro).**
1. **O percentual do detalhe do RDO SOBE** para obras V1 com `SubatividadeMestre`
   cadastrada e não apontada → preservar o rótulo de `:1258` ao lado; e antes do deploy,
   script só-leitura listando as N obras V1 com maior delta entre a fórmula velha e a
   nova, avisando quem olha essas telas.
2. **O predicado estrito tira do ramo V2** obras que hoje entram nele por uma tarefa
   cópia-cliente ou desativada; se não tiverem `RDOServicoSubatividade`, caem para 0 →
   **medir primeiro, não presumir vazio**: contar em produção obras que passam no
   predicado frouxo e falham no estrito, e quantas delas têm zero linha. Se a interseção
   for não-vazia, o ramo V1 precisa de um degrau extra (tratar como V2 quando existir
   QUALQUER `RDOApontamentoCronograma`) antes de devolver 0.
3. Oito substituições em cinco arquivos, quase todas dentro de `try/except Exception`
   amplo: uma errar nome de argumento e cair no `except` devolve 0 em produção sem erro
   visível → a chamada nova fica FORA do `try` do bloco, ou o `except` ganha
   `logger.exception`. E a asserção 1 (mesmo número nas quatro rotas) faz a igualdade
   falhar em vez de passar em silêncio.

- [ ] **Step 1:** `crud_rdo_completo.py` — detecção + ramo V1 incondicional
- [ ] **Step 2:** rodar o teste de convergência inteiro — as quatro asserções verdes
- [ ] **Step 3:** `bash run_tests.sh --gate`
- [ ] **Step 4:** commit — `fix(rdo): família V1 de progresso converge nos seis call-sites vivos`

---

### 5.3 A24a — o `× 0.7` dos encargos patronais é BUG, não premissa

`services/folha_service.py:966-990` (`calcular_encargos_patronais`) devolve
`fgts = bruto × aliquota/100` (a alíquota vem de `_obter_aliquota_fgts`, `:159-171`, que
lê `ParametrosLegais.fgts_percentual` — `models.py:2985`, default 8.0) e
`inss_patronal = bruto × Decimal('0.20')` (`:981`), com `'total' = fgts + inss_patronal`
(`:983`). `processar_folha_funcionario` repassa só duas chaves — `'fgts'` (`:1091`) e
`'encargos_patronais'` (`:1092`) — e **não** repassa `inss_patronal`, que existe no dict
de origem (`:987`). Em `salvar_folha_processada`, os dois ramos gravam
`encargos_inss_patronal = Decimal(str(dados_folha['encargos_patronais'])) * Decimal('0.7')`
— UPDATE em `:1142`, INSERT em `:1171` (conferido hoje). O 0.7 é uma tentativa de
reextrair o INSS de dentro do total, e a razão verdadeira é **20/28 = 0,714285…**, não
0,7. Grava 19,6% do bruto em vez de 20%; somado ao FGTS de `:1141`/`:1170`, a linha
persiste **27,6%** contra os 28% calculados.

**Três provas de que não é premissa deliberada:**
(a) nenhum comentário, docstring ou doc do repo menciona 0.7 —
`git log -L 1142,1142:services/folha_service.py` devolve um único commit (`b30923b5`,
entrada do arquivo inteiro), sem racional;
(b) **contradição DENTRO da própria linha gravada**: `custo_total_empresa`
(`:1143`/`:1172`) vem de `float(salario_bruto) + encargos['total']` (`:1093`), isto é
bruto + 28% — logo `encargos_fgts + encargos_inss_patronal` (27,6%) ≠
`custo_total_empresa − salario_bruto` (28%) **na mesma linha**; premissa deliberada não
produz linha internamente incoerente;
(c) um segundo escritor independente da MESMA coluna diz o contrário:
`scripts/seed_demo_alfa.py:3395-3412` grava `_inss_pat = Decimal("560.00")` com o
comentário `# 20 % encargo patronal` sobre bruto de 2.800.

**Número certo:** `encargos_patronais − fgts` (exatamente `bruto × 0.20`, e robusto se o
tenant configurar `fgts_percentual` ≠ 8, caso em que **qualquer fator fixo — inclusive
0,714285 — erra**). Efeito, bruto R$ 3.000: hoje 240 + 588 = 828; correto 240 + 600 =
840 (R$ 12/funcionário/mês, 0,4% do bruto, linear).

**Alcance hoje:** `salvar_folha_processada` (`:1105`) tem um só chamador, `:1415`, dentro
de `processar_e_salvar_folha_obra` (`:1378`), que não tem chamador nenhum. O erro está
**latente** — mas o leitor a jusante já está vivo: `obter_dados_folha_obra` (`:1195`)
soma `encargos_fgts + encargos_inss_patronal` em `:1266` e é consumida por
`views/obras.py:1908-1914`. No dia em que A24 ligar o pipeline, o subfaturamento entra
direto no painel de custo da obra. **Corrigir agora custa duas linhas; depois custa
reprocessar folha.**

**Esta correção NÃO é a entrega do A24.** O pipeline segue sem chamador e o rateio por
obra segue travado na Decisão 6. A mensagem de commit e a spec nomeiam só a aritmética.

**Esforço:** P.

---

### Task B2.13: consulta somente-leitura do invariante em produção

**Files:** nenhum — é medição

**Comportamento.** Contar `SELECT count(*) FROM folha_processada WHERE encargos_inss_patronal > 0`
e, entre essas, quantas violam
`ROUND(encargos_fgts + encargos_inss_patronal, 2) <> ROUND(custo_total_empresa - salario_bruto, 2)`.
**O invariante é o detector exato de linha antiga.**

**Expectativa fundamentada:** zero, porque o único chamador de `salvar_folha_processada`
está dentro de uma função órfã. Se vier zero, nada a fazer. Se vier diferente de zero, a
correção do histórico abre como **item próprio** — não é escopo deste recorte, e é o
único fato que pode transformar este recorte P num item com migração.

- [ ] **Step 1:** rodar a consulta em produção e guardar o número

---

### Task B2.14: variável única, os dois ramos, e a chave `inss_patronal` no dict

**Files:** Modify `services/folha_service.py` — `salvar_folha_processada`: após a
consulta `folha_existente` (`:1125-1130`) e antes do `if folha_existente:` (`:1132`);
ramo UPDATE `:1142`; ramo INSERT `:1171`; e `processar_folha_funcionario` entre `:1091` e
`:1092`

**Comportamento novo.** Passa a existir UMA expressão local, calculada uma só vez, para
o INSS patronal a gravar: usa `dados_folha['inss_patronal']` quando a chave existir e, na
falta dela, `Decimal(str(encargos_patronais)) - Decimal(str(fgts))`. Os dois ramos leem
essa variável, **sem o `* Decimal('0.7')`**. E `processar_folha_funcionario` passa a
devolver `'inss_patronal': encargos['inss_patronal']`, que `:987` já produz e hoje é
jogado fora — com isso o consumidor não precisa mais reconstituir a parcela por
aritmética inversa: **a fonte do defeito desaparece, não só o sintoma**.

**Teste que prova:** `tests/test_encargos_e_agendamento_honestos.py`, TESTE A (nível
serviço). Monta `dados_folha` na mesma forma de `:1069-1093`: `salario_bruto=3000.00`,
`fgts=240.00`, `encargos_patronais=840.00`, `custo_total_empresa=3840.00`. Três chamadas
a `salvar_folha_processada(func.id, obra.id, 2026, 3, dados, admin.id)`:

| Passo | Exercita | Asserção sobre a linha lida do banco |
|---|---|---|
| 1 | ramo INSERT (`:1156-1182`) | `encargos_inss_patronal == Decimal('600.00')` (hoje **588.00**); `encargos_fgts == Decimal('240.00')`; **e o invariante:** `encargos_fgts + encargos_inss_patronal == custo_total_empresa - salario_bruto == Decimal('840.00')` — hoje 828 ≠ 840 dentro da MESMA linha |
| 2 | ramo UPDATE (`:1132-1152`) | as três repetidas: o UPDATE grava o mesmo número que o INSERT (uma correção pela metade faz o valor mudar entre a 1ª e a 2ª gravação) |
| 3 | alíquota de FGTS não-padrão (`fgts=255.00` = 8,5%, `encargos_patronais=855.00`) | `encargos_inss_patronal == Decimal('600.00')` de novo — **um fator fixo de 20/28 gravaria 610,71**. Esta é a asserção que separa "consertaram a aritmética" de "trocaram um número mágico por outro" |

Ano/mês são literais da própria semente (2026/3): sem `date.today()` em lugar nenhum.

**Por que o textual não pegaria nem se existisse.** Grep em `tests/` por
`salvar_folha_processada`, `FolhaProcessada`, `encargos_inss_patronal`, `exportacao` e
`agendar` devolve dois arquivos, e em nenhum por causa destes símbolos — **zero
cobertura**. Mas o ponto de método vai além: um guarda no molde dos pacotes,
`assert "Decimal('0.20')" in open('services/folha_service.py').read()`, **passa VERDE
hoje** — a constante certa está mesmo em `:981`; o erro nasce 160 linhas abaixo, na
aritmética que reconstrói o valor. **Texto de arquivo não sabe multiplicar.**

**Riscos → mitigação.**
1. **Não** trocar o `0.7` por `0.714285` nem por outro fator: a alíquota de FGTS é
   configurável por tenant, então só a subtração é exata.
2. Manter `Decimal(str(...))` — o dict vem com `float` (`:1091-1093`) e `Decimal(float)`
   introduz cauda binária. Aplicar `.get(chave, 0)` nas duas parcelas, porque
   `salvar_folha_processada` é pública e recebe dict arbitrário.
3. **Não encostar** em `:1141`/`:1170` (`encargos_fgts`) nem em `:1143`/`:1172`
   (`custo_total_empresa`): já estão certos, e mexer neles quebraria o invariante que o
   teste afirma.
4. `'inss_patronal'` é **acréscimo, nunca renomeação**: `folha_pagamento_views.py:172-189`
   lê o dict chave a chave por nome e quebraria se `'fgts'` ou `'encargos_patronais'`
   mudassem. Conferido: não há iteração sobre `.items()`.

- [ ] **Step 1:** escrever o TESTE A e vê-lo VERMELHO em `588.00`
- [ ] **Step 2:** variável única após `:1130` + os dois ramos + a chave em `:1091`
- [ ] **Step 3:** teste verde nos três passos
- [ ] **Step 4:** commit — `fix(folha): INSS patronal gravado por subtração, não por fator 0.7`

---

### 5.4 E12a — a rota que responde `success: True` para um agendamento inexistente

`exportacao_relatorios.py:806-840` (`agendar_relatorio`, `POST /relatorios/exportacao/agendar`;
prefixo `:46`, blueprint registrado em `main.py:157-158` — conferido hoje em `:804-830`).
`:823` instancia `SistemaAgendamentoRelatorios()` **nova a cada request**; `__init__`
(`:762-763`) cria `self.jobs_agendados = {}`; `agendar_relatorio_periodico` (`:765-793`)
escreve uma chave nesse dict e devolve `job_id`; **o objeto morre no fim da requisição**.
`jobs_agendados` não é lido por nenhuma linha do repositório (grep: só `:763` e `:781`).
Não há modelo de agendamento em `models.py` (`grep 'class .*Agend'`: zero). Não há envio:
o único `smtplib` vivo está em `:530-591` com `MAIL_SERVER` default `'localhost'` e
nenhum `MAIL_*` configurado em `app.py`/`main.py`. Mesmo assim `:826-831` responde
`{'success': True, 'job_id': ..., 'message': 'Relatório agendado com sucesso'}`.

**Quem chama: ninguém dentro do produto.** Grep por `relatorios/exportacao` e
`exportacao_relatorios.` em `templates/`, `static/` e `.py` (fora de `archive/`, `docs/`,
`__pycache__`) devolve apenas as referências internas do próprio módulo (`:604`, `:637`,
`:642`, `:674`, `:679`) e `MODULOS.md:104`. O painel que seria o hospedeiro da UI
(`GET /relatorios/exportacao/`, `:597-604`) renderiza `relatorios/exportacao/painel.html`
— o diretório `exportacao/` não existe em `templates/relatorios/`: a rota dá 500.

**Por isso a opção "esconder a UI" é NO-OP:** não existe UI para esconder, e o defeito
continuaria armado para o próximo que ligar um botão nela.

**Recomendação adotada: erro honesto (501), e deleção da máquina falsa.** Motivo de
preferir 501 a desligar (404): a decisão SMTP × n8n pode nunca vir, e a diferença
prática é o que o próximo desenvolvedor encontra. 404 é indistinguível de erro de rota e
apaga o registro de que o recurso foi prometido; 501 devolve uma frase que explica o
porquê, custa quatro linhas, é reversível e — o ponto principal — **é correta em
qualquer desfecho da Decisão 7**.

**Esforço:** P. Commit **separado** do A24a: são arquivos, módulos e riscos distintos, e
o de folha pode precisar voltar atrás sozinho se a Task B2.13 surpreender.

---

### Task B2.15: `agendar_relatorio` devolve 501 com `success: False`

**Files:** Modify `exportacao_relatorios.py` — corpo de `agendar_relatorio`, `:810-840`
(decoradores de `:806-808` preservados)

**Comportamento novo.** Primeira instrução após a docstring: `logger.warning` nomeando o
chamador e devolução de `jsonify({'success': False, 'implementado': False, 'error':
'Agendamento de relatórios não implementado: não há envio de e-mail configurado nem
persistência de agenda. Nenhum relatório será enviado.'}), 501`. Somem o `try/except`, a
instanciação de `:823` e o ramo `if job_id:` de `:826-831`. O formato de payload
(`success` booleano + `error`) é o mesmo das outras rotas do arquivo.

**Teste que prova:** TESTE B do mesmo arquivo de B2.14, **nível rota**:
`cliente_de(admin_id).post('/relatorios/exportacao/agendar', json={'frequencia':
'semanal', 'formato': 'pdf', 'destinatarios': ['contato@exemplo.local'],
'incluir_graficos': True})`, autenticado como ADMIN para atravessar `auth.py:21-34`.
Asserções: `status_code == 501`, `payload['success'] is False`, `'job_id' not in payload`
— **e a asserção sobre o banco é a AUSÊNCIA**, que é justamente o que a rota nega hoje:
`models.py` não declara nenhuma tabela de agendamento (nada a contar porque nada existe),
e a contagem de `WebhookEntrega` (a única tabela de saída externa do sistema) é idêntica
antes e depois do POST. O teste amarra o contrato da resposta ao vazio do banco — o par
que hoje está mentindo.

**Riscos → mitigação.**
1. Manter `@login_required` e `@admin_required` (`:807-808`) — sem eles a rota vira ponto
   anônimo de reconhecimento do que não existe; `auth.py:21-34` responde com `redirect`
   para não-admin, e o teste precisa contar com isso.
2. O `return` fica ANTES de qualquer `try`. A casa já pagou por `except Exception` amplo
   engolindo resposta de erro; aqui a forma segura é **não haver `try` nenhum**.
3. **Não** trocar por 503: 503 promete que volta; 501 é o que se afirma com honestidade
   enquanto a Decisão 7 não vem.
4. Integrador externo que já POSTa e recebia 200 passa a receber 501 → o 200 de hoje não
   corresponde a efeito nenhum; quem depende dele depende de uma alucinação, e o 501 é a
   primeira informação verdadeira que recebe.

- [ ] **Step 1:** o corpo novo
- [ ] **Step 2:** TESTE B verde
- [ ] **Step 3:** commit — `fix(relatorios): agendamento responde 501 em vez de fingir sucesso`

---

### Task B2.16: remover `SistemaAgendamentoRelatorios`

**Files:** Modify `exportacao_relatorios.py` — classe `:759-804` (bloco inteiro,
incluindo `_calcular_proximo_envio` em `:794-804`) e o import de `timedelta` na `:16`

**Comportamento novo.** A classe some. Depois disso não sobra no repositório nenhuma
estrutura que aceite um agendamento e o descarte em silêncio.

**Teste que prova:** `bash run_tests.sh --gate` verde; TESTE B continua verde.

**Riscos → mitigação.**
1. Conferido: a única referência à classe em todo o repo (fora de `archive/`) é `:823`,
   que B2.15 já apagou — nenhum teste a importa. **Ordem: a rota antes da classe**;
   invertida, a ordem quebra o import por um instante.
2. `timedelta` (`:16`) só é usado em `:798-804`, dentro da classe → sai junto, preservando
   `datetime`, usado no arquivo inteiro.
3. **Não remover o blueprint nem as outras rotas:** `main.py:157-158` continua
   registrando, e `GET /` (`:597-604`), `gerar-pdf` (`:606`), `gerar-excel` (`:644`),
   `enviar-email` (`:681`) e `api/preview-dados` (`:729`) são de E12 completo, fora deste
   recorte. O painel que dá 500 e o SMTP não configurado continuam como estão, sob a
   Decisão 7 — este recorte **não a antecipa**.

- [ ] **Step 1:** remover classe + `timedelta`
- [ ] **Step 2:** gate verde
- [ ] **Step 3:** commit — `chore(relatorios): remove SistemaAgendamentoRelatorios (agenda em memória sem leitor)`

---

### 5.5 A06 — replanejar a curva planejada após os recálculos de data do editor v2

**Uma premissa do enunciado está DESMENTIDA.** O que fica obsoleto é UMA coisa só:
`RDOApontamentoCronograma.percentual_planejado` — o snapshot do planejado gravado por
apontamento. A curva de **desembolso não** fica obsoleta, e portanto **o EVM do p10 não
sofre com A06**: `services/evm.py:87` chama `montar_fisico_financeiro(obra_id, admin_id)`,
e `services/cronograma_fisico_financeiro.py:218-240` recarrega `TarefaCronograma` do banco
e faseia em `:337` a CADA requisição — nada é persistido. PV já nasce com as datas novas;
EV vem de `progresso_ponderado_armazenado` e AC de `curva_realizado`, e nenhum toca
`percentual_planejado`.

**Quem lê a curva podre:** (1) `views/obras.py:2841-2848` — rota
`/obras/<id>/curva-avanco` (`:2781`), campo `'planejado'`, que sai de
`calcular_progresso_geral_obra_v2(..., com_arquivadas_historicas=True)['progresso_planejado_pct']`,
que em `utils/cronograma_engine.py:939` agrega `prog['percentual_planejado']` — a linha
azul da Curva S em `templates/obras/detalhes_obra_profissional.html:2060-2082`. **Vítima
principal.** (2) `services/rdo_pdf_service.py:679`. (3) `cronograma_views.py:2808` e
`rdo_editar_sistema.py:136`. **NÃO afetados:** o portal do cliente (nenhum template lê
planejado), a coluna "planejado" da grade (`cronograma_views.py:2458`/`:2461` usam
`calcular_progresso_rdo`, ao vivo) e o EVM.

**São SETE pontos de inserção, não seis** — o backlog fundiu os dois últimos:
`:866-872` (`criar_tarefa` plano), `:1149-1162` (`atualizar_tarefa` v2), `:1172-1177`
(`atualizar_tarefa` legado), `:1259-1266` (`excluir_tarefa`), `:1305-1316`
(`/obra/<id>/recalcular`, dois ramos), `:1411-1421` (`_recalc_e_resposta_vinculo`, que
serve `criar_vinculo` `:1499`, `atualizar_vinculo` `:1534` e `excluir_vinculo` `:1556`) e
`:1680-1687` (`_aplicar_hierarquia`, que serve `criar_tarefa` posicionado `:857`,
`recuar` `:1785`, `desrecuar` `:1855` e `mover` `:1945`).

**O custo — medido, e é onde mora a decisão de projeto.** O replanejamento em si é
BARATO: `utils/cronograma_engine.py:1142-1177` faz 2 SELECTs + laço puro em Python + 1
commit; `_planejado_na_data` (`:368-389`) chama `dias_uteis_entre` (`:73-82`), laço
limitado à janela da tarefa — 5.000 apontamentos × janela de 60 dias ≈ 300k iterações
triviais, dezenas de ms. **Inline, sem problema.** O CARO é o RELATÓRIO: `:1136-1138` e
`:1180-1181` chamam `calcular_progresso_geral_obra_v2` DUAS vezes só para preencher
`progresso_antes`/`progresso_depois`, e essa função é N+1 assumido (`:938` roda
`calcular_progresso_rdo` por folha, e cada chamada faz `TarefaCronograma.query.get` +
`get_calendario` (`:89-92`, **sem cache**) + o SUM (`:778-789`): 3 a 5 queries por folha;
obra de 300 folhas = 900-1500 queries, **vezes dois**). E o segundo perigoso: `:1178`
chama `sincronizar_percentuais_obra`, que em `:553-554` faz
`tarefa.percentual_concluido = 0.0` para toda folha sem apontamento e commita em `:577`.

**Conclusão: INLINE, sim — desde que num modo enxuto, sem relatório e sem
sincronização. Não precisa ser assíncrono.**

**Esforço:** M.

---

### Task B2.17: `replanejar_curvas_obra` ganha modo enxuto

**Files:** Modify `utils/cronograma_engine.py` — `replanejar_curvas_obra`, def `:1120`,
corpo `:1136-1188`

**Comportamento novo.** Dois keyword-only com default que preserva o comportamento de
hoje byte-a-byte: `com_relatorio=True` e `sincronizar=True`. Com `com_relatorio=False`
pula as duas chamadas a `calcular_progresso_geral_obra_v2` (`:1136-1138` e `:1180-1181`) e
devolve `progresso_antes`/`progresso_depois` como None. Com `sincronizar=False` pula
`sincronizar_percentuais_obra` (`:1178`). O commit de `:1177` e o laço `:1157-1175` ficam
idênticos. `services/cronograma_versao_service.py:443` continua chamando sem argumentos.

**Teste que prova:** `tests/test_replanejamento.py` e
`tests/test_cronograma_versao_service.py` rodam **sem tocar em uma linha deles** e
continuam verdes. Verde ali é a prova de que `aplicar_versao`/`restaurar_versao`
(`services/cronograma_versao_service.py:443`, `:703`) não sentiram nada.

**Risco → mitigação.** **Não** trocar os defaults nem inverter para `leve=True`:
`tests/test_replanejamento.py:95,115,121,136,152` assertam `progresso_antes`/
`progresso_depois` como float e a idempotência do contador; qualquer default novo quebra
o gate do M06 sem que a regressão seja de A06.

- [ ] **Step 1:** os dois keyword-only
- [ ] **Step 2:** rodar os dois arquivos de teste, intocados
- [ ] **Step 3:** commit — `feat(cronograma): replanejar_curvas_obra com modo enxuto (sem relatório, sem sincronização)`

---

### Task B2.18: `_replanejar_pos_commit` — o ponto único onde o editor toca a curva

**Files:** Modify `cronograma_views.py` — novo helper privado logo depois de
`_editor_v2_on` (`:109-117`), antes de `_com_undo` (`:120`)

**Comportamento novo.** `_replanejar_pos_commit(obra_id, admin_id, cliente_mode)`:
sai imediatamente (no-op) se `cliente_mode`; senão chama
`replanejar_curvas_obra(obra_id, admin_id, com_relatorio=False, sincronizar=False)`
dentro de try/except que faz `db.session.rollback()` e `logger.exception(...)` — falha
aqui **NUNCA** desfaz a edição já commitada, exatamente a postura de
`services/cronograma_versao_service.py:432-457`. Não devolve nada: o replanejamento não
entra na resposta HTTP.

**Por que concentrar aqui:** três armadilhas, resolvidas UMA vez. Sete call-sites
repetindo try/except são sete chances de errar.

**Riscos → mitigação.**
1. `except HTTPException: raise` **antes** do catch-all — regra da casa. O guard de
   tenancy já rodou bem antes (`_guard_editar_obra`, `:76`) e o helper é pós-commit, mas
   a ordem das cláusulas não custa nada e fecha a classe inteira.
2. O guard de `cliente_mode` não é cosmético: `replanejar_curvas_obra` filtra tarefas com
   `is_cliente=False` fixo (`utils/cronograma_engine.py:1146`) mas varre **TODOS** os
   apontamentos da obra (`:1150-1156`) — no modo cliente seria uma varredura inteira que
   não replaneja nada.
3. O `rollback()` do except expira os objetos ORM → o helper é chamado ANTES de qualquer
   serialização da resposta, para que `_tarefa_to_dict`/`_mapas_vinculos` re-hidratem do
   banco já commitado.

- [ ] **Step 1:** o helper
- [ ] **Step 2:** commit — `feat(cronograma): _replanejar_pos_commit — ponto único do replanejamento no editor`

---

### Task B2.19: ligar em `atualizar_tarefa` primeiro, com os três testes

**Files:** Modify `cronograma_views.py` — `atualizar_tarefa` (`:892`): ramo v2 DEPOIS de
`:1162`; ramo legado DEPOIS de `:1177`. Create `tests/test_replanejamento_editor_v2.py`

**Comportamento novo.** Chamar `_replanejar_pos_commit(obra_id, admin_id, cliente_mode)`
no fim de cada ramo, e **somente quando houve recálculo de data**: no ramo v2, guardado
por `if precisa_recalc`; no legado, dentro do `if _SCHEDULING_FIELDS & set(data.keys())`
já existente (`:1172`). **Renomear uma tarefa não paga o replanejamento.**

**A ORDEM é o núcleo do item.** Se a chamada entrar antes de `:1160-1162` (ou de
`:1175-1177` no legado) e alguém deixar `sincronizar=True`,
`sincronizar_percentuais_obra` reescreve `percentual_concluido` a partir do último
apontamento e **o percentual manual que o usuário acabou de digitar some** — é o contrato
dessas quatro linhas que está sendo protegido. Depois de `:1162` e com
`sincronizar=False`, o risco fecha dos dois lados.

**Teste que prova** (harness já existente: `_ambiente()`/`_tarefa()` de
`tests/test_cronograma_versao_service.py`, `_client_como` de
`tests/test_cronograma_endpoints_m05.py`, `_flag_editor_v2` no molde de
`tests/test_cronograma_grade_api.py:67-75`):

| Teste | Semente / ação | Asserção |
|---|---|---|
| 1 — **o defeito** | folha 'Alvenaria', `duracao_dias=10`, 2026-07-01→07-14; RDO em 2026-07-08 com apontamento (`quantidade_executada_dia=30`, `quantidade_acumulada=30`, `percentual_realizado=30`) e `percentual_planejado=60.0` (o valor CORRETO do plano antigo); flag v2; `PUT /cronograma/obra/<id>/tarefa/<id>` com `{"data_inicio": "2026-08-03"}` | recarregando do banco: `percentual_planejado == 0.0` (o RDO de 08/07 é anterior ao novo início) **e** a tupla (`quantidade_executada_dia`, `quantidade_acumulada`, `percentual_realizado`, `percentual_acumulado`) byte-idêntica à semente — **o realizado é intocável** |
| 2 — **a armadilha do sincronizar** | mesmo PUT com `{"data_inicio": "2026-08-03", "percentual_concluido": 77.0}` numa tarefa cujo apontamento diz 30% | `TarefaCronograma.percentual_concluido == 77.0` no banco: prova que o replanejamento não arrastou `sincronizar_percentuais_obra` (que devolveria 30.0 via `utils/cronograma_engine.py:557`) |
| 3 — **o custo** | mesmo PUT do teste 1, com contador via `sqlalchemy.event.listen(db.engine, 'before_cursor_execute', ...)` | nº de queries abaixo de um teto fixo folgado (ex.: 60) — trava a volta do N+1 dos dois `calcular_progresso_geral_obra_v2` |

**Por que o atual não pegava.** `tests/test_replanejamento.py` chama
`replanejar_curvas_obra(obra.id, admin.id)` **diretamente** nas linhas 95, 115, 121, 136
e 152: prova que a função está certa e **nunca que alguém a chama** — a mesma cegueira
dos guardas textuais, só que por acoplamento de import em vez de leitura de arquivo; o
efeito é o mesmo, o gate fica verde com ZERO call-sites de produção no editor. E nenhum
teste do repositório emite `PUT /cronograma/obra/<id>/tarefa/<id>` e depois olha
`rdo_apontamento_cronograma.percentual_planejado`;
`tests/test_cronograma_grade_api.py` exercita as rotas mas assere sobre datas, ordem e
`predecessoras_texto`. **Sobre data:** a semente é 07/2026 e o alvo 08/2026, e a asserção
é sobre a data do próprio RDO — `_planejado_na_data` (`:368-389`) não consulta
`date.today()`; o único `date.today()` de `replanejar_curvas_obra` está em `:1135-1138`/
`:1180-1181`, que `com_relatorio=False` desliga. **O teste roda igual em qualquer dia do
mês.**

- [ ] **Step 1:** escrever os três testes
- [ ] **Step 2:** ligar os dois ramos de `atualizar_tarefa`
- [ ] **Step 3:** testes verdes — se o desenho estiver errado, aparece aqui e não depois de sete edições
- [ ] **Step 4:** commit — `fix(cronograma): atualizar_tarefa replaneja a curva após o recálculo de datas`

---

### Task B2.20: propagar aos outros seis pontos

**Files:** Modify `cronograma_views.py` — `_aplicar_hierarquia` (entre o
`except ErroCiclo` de `:1685-1687` e o `return resultado, None` de `:1688`);
`_recalc_e_resposta_vinculo` (entre o `except ErroCiclo` de `:1420-1422` e o
`_mapas_vinculos` de `:1424`); `criar_tarefa` (entre o `except ErroCiclo` de `:872` e o
`logger.info` de `:874`); `excluir_tarefa` (depois do bloco `:1259-1266`, antes da query
`todas` de `:1269`); `recalcular` (depois do if/else de `:1307-1316`, antes da query
`tarefas` de `:1318`)

**Comportamento novo.** `_aplicar_hierarquia` e `_recalc_e_resposta_vinculo` primeiro,
porque **cobrem sete rotas com duas linhas**. Depois `criar_tarefa`, `excluir_tarefa` e
`/recalcular` — esta última é o **gatilho manual**: sem ela o replanejamento não tem como
ser acionado pela UI e um dado velho fica sem conserto.

**Riscos → mitigação.**
1. **Toda chamada fica FORA do try que captura `ErroCiclo`** (`:866-872`, `:1149-1156`,
   `:1418-1422`, `:1683-1687`). Dentro dele, o commit interno de
   `utils/cronograma_engine.py:1177` rodaria antes do `db.session.rollback()`, e a edição
   que deveria ser desfeita por ciclo ficaria gravada. **A revisão deve conferir ponto a
   ponto.**
2. `excluir_tarefa`: o `except` de `:1263-1266` **NÃO retorna** — só loga e segue.
   Chamar incondicionalmente depois do bloco replanejaria por cima de um recálculo
   abortado e revertido → precisa de um sinalizador local (`recalculou = True` dentro do
   try).
3. `recalcular`: no ramo v2 o `return` do `except ErroCiclo` (`:1312`) já protege; no
   legado, só quando `ok` for verdadeiro (`:1314-1316` já retorna 500 quando falso).
4. As quatro rotas servidas por `_aplicar_hierarquia` passam por `@_com_undo`
   (`:120-163`) — com `sincronizar=False` o replanejamento escreve só em
   `rdo_apontamento_cronograma`, que **não** está no snapshot de
   `services/cronograma_undo.py:52-58`, então o diff da pilha de desfazer continua limpo.
   Com `sincronizar=True` o `percentual_concluido` reescrito entraria como ruído.
5. `_recalc_e_resposta_vinculo`: antes do `_mapas_vinculos` de `:1424`, não depois — se o
   replanejamento falhar e rolar back, a serialização re-consulta o banco em vez de ler
   objetos expirados.
6. **Semântica.** Replanejar torna a linha "planejado" da Curva S (`views/obras.py:2848`)
   um **plano corrente**, não um compromisso: depois de A06 a curva nunca mais mostra
   atraso contra o plano original. É o comportamento **certo** para a curva viva (o que a
   spec M06 §4.3 pede e o que `services/cronograma_versao_service.py:432` já faz desde
   M05), e é por isso que a `CronogramaBaseline` existe. O que falta é uma curva planejada
   **derivada da baseline** — item novo, fora de A06. **Registrar como pendência para não
   descobrir isso em produção.**

- [ ] **Step 1:** `_aplicar_hierarquia` e `_recalc_e_resposta_vinculo`
- [ ] **Step 2:** `criar_tarefa`, `excluir_tarefa` (com o sinalizador), `/recalcular`
- [ ] **Step 3:** revisão ponto a ponto: cada chamada FORA do try do `ErroCiclo`
- [ ] **Step 4:** `bash run_tests.sh --gate`
- [ ] **Step 5:** commit — `fix(cronograma): os sete pontos de recálculo do editor replanejam a curva`

---

## 6. B3 — Fechar os elos que morrem a um passo

**Por que existe.** Peças construídas, testadas e vivas que não se tocam: o CRM manda os
IDs e o receptor os descarta; a FK do lead existe, está indexada, e **nada** a escreve; o
lado pagar grava `FluxoCaixa` e o lado receber não; a CR de medição nasce sem conta
contábil e o gate a pula **sem log**.

**Esforço:** M. **Migração:** nenhuma. **Depende de:** B0.

---

### 6.1 A07 + A22(select) + E05 + A14 — a cadeia CRM → Proposta → Obra → Lead

**A interdependência do A07 está CONFIRMADA na perna da proposta e DERRUBADA na perna
da obra.** `crm_views.py:936-939` monta
`url_for('propostas.nova_proposta', cliente_id=..., lead_id=...)`; o alias
`nova_proposta()` em `propostas_consolidated.py:1186-1188` é
`return redirect(url_for('propostas.nova'))` — **sem query string**; e `nova()`
(`:510-545`) não lê `request.args` em lugar nenhum (as únicas variáveis que chegam ao
`render_template` de `:536-540` são `templates_proposta`, `config` e `engenheiros`).
Aqui as duas linhas são inseparáveis. **Já a perna da obra não depende delas:**
`crm_views.py:974-977` aponta para `main.nova_obra` = `views/obras.py:292-294`, rota
direta, sem alias — a query string chega íntegra e é descartada no ramo GET (`:498-523`).
São duas peças, não três acopladas.

**E05 confirmado ABERTO.** `handlers/propostas_handlers.py:263` é
`Lead.query.filter_by(proposta_id=proposta_id, admin_id=admin_id).all()`; o único
escritor de `obra_id` é `:274-275`, dentro do `for lead in leads` de `:265`.
`grep -rn "\.proposta_id\s*=" --include=*.py` fora de `archive/`/`tests/` devolve só
`propostas_consolidated.py:2821` (outro modelo) e três linhas de SQL de comparação em
`migrations.py`. **A lista de `:263` é sempre vazia; `:275` nunca executa.** As colunas
existem e estão indexadas (`models.py:8043-8046` e `:8047-8050`, ambas
`ondelete='SET NULL'`) — falta escritor, não esquema.

**A14 confirmado.** `handlers/propostas_handlers.py:378-385` (conferido hoje em
`:376-388`): `if valor_total <= 0 or skip_contabil:` chama `_propagar_proposta_para_obra`
(`:383`) e `_materializar_cronograma_se_houver` (`:384`) e dá `return` em `:385` — **não**
chama `_semear_servicos_reais` (`:179-243`) nem `_fechar_lead_da_proposta` (`:246-281`),
que só aparecem em `:427-428` e `:493-494`. Por ali passam a importação
físico-financeira (`services/importacao_fisico_financeiro.py:572-578`, que **já grava**
`proposta.obra_id` no construtor de `:522-526`, antes do emit — então
`_semear_servicos_reais` teria obra para semear) e toda proposta de valor zero.

**A22, só o select** — o recorte é menor do que parece.
`templates/propostas/nova_proposta.html:78` é `<input type="text" name="cliente_nome"
required>`; não existe `<select name="cliente_id">` no arquivo. `criar()` lê
`cliente_nome/email/telefone/endereco` em `:556-560` e monta a `Proposta` em `:647-659`
sem nunca atribuir `cliente_id` — a FK existe (`models.py:3571`). **Mas o caminho do
Orçamento já faz certo:** `views/orcamentos_views.py:633` grava
`proposta.cliente_id = orc.cliente_id`, e a revisão herda em
`propostas_consolidated.py:1287`. O buraco é exclusivo do formulário manual legado — e
custa dinheiro adiante: `event_manager.py:1014-1020` passa
`cliente_id=getattr(proposta, 'cliente_id', None)` ao `obter_ou_criar_cliente`; com
`cliente_id` nulo o resolver cai no dedup por nome/e-mail
(`services/cliente_resolver.py:79-125`) e, se o nome digitado divergir do cadastro, cria
um Cliente **DUPLICADO** (`:128-135`) — e a obra nasce amarrada nele.

**Números do banco de dev** (leitura de hoje, `admin_id=1`, o tenant do seed demo): 128
propostas, **123 sem `cliente_id`**; 65 com `obra_id`; **64 dessas obras sem uma única
linha em `servico_obra_real`**; **36** propostas cujos itens têm `servico_id` e cuja obra
está sem `ServicoObraReal` — 36 é o rendimento real de um backfill. 12 leads, 1 com
`proposta_id`, e esse 1 é o que `scripts/seed_demo_alfa.py:2509` semeia de propósito.
Globalmente o banco tem 41.519 obras e 5.224 propostas `FF-%`: **é lixo de suíte, não
serve de estimativa de produção.**

**O teste do bloco:** `tests/test_cadeia_crm_proposta_obra_lead.py`, seis casos, todos
por rota ou por evento, com `dois_tenants('cadeia')` e `cliente_de(admin_id)`. Semente
comum: no tenant A, um `Servico` ativo e um `Lead` com `cliente_id = a.cliente_id`,
status ENVIADO.

| # | Ação | Asserção (banco, após `expire_all`) |
|---|---|---|
| T1 | `GET /crm/{lead.id}/gerar_proposta` com `follow_redirects=True` (atravessa CRM → alias → `/propostas/nova`) | o HTML final contém `name="cliente_id"`, a option do Cliente de A vem `selected`, e existe `name="lead_id"` com value == `lead.id` |
| T2 | `GET /propostas/nova?cliente_id={b.cliente_id}&lead_id=999999` como A | 200 e `b.marca` **ausente** do corpo, nenhum `selected`. **Não esperar 404** — ver risco 3 |
| T3 | `POST /propostas/criar` com `cliente_id`, `lead_id`, item com `item_servico_id` | `Proposta.cliente_id == a.cliente_id` (hoje None) **e** `Lead.proposta_id == pid` (hoje None — é este assert que faz `:263` deixar de devolver lista vazia) |
| T4 | `POST /propostas/aprovar/<id>` sobre a de T3 | `obra_id` não nulo; `ServicoObraReal.count() >= 1`; `lead.status == APROVADO`; `lead.obra_id == proposta.obra_id` (hoje as duas últimas falham) |
| T5 | Semeia Proposta com `obra_id` + item com `servico_id` + Lead com `proposta_id`; `EventManager.emit('proposta_aprovada', {...,'skip_contabil': True}, admin_id, raise_on_error=True)`; e o gêmeo com `valor_total=0` | `ServicoObraReal.count() == 1` (hoje **0**); `lead.status == APROVADO`; `lead.obra_id == a.obra_id`. **Reemitir e reafirmar `count() == 1`** — idempotência pela porta do evento, não pela chamada direta |
| T6 | `GET /crm/{lead2.id}/criar_obra`, depois `POST /obras/nova` com `lead_id` | hidden `cliente_id` traz `a.cliente_id`; e `Lead.obra_id == <obra criada>` (hoje None) |

**Por que o atual não pegava.** `tests/test_p5_aprovacao_semeia_obra.py:210-219` abre
`handlers/propostas_handlers.py` como TEXTO e afirma
`texto.count('_semear_servicos_reais(proposta_id, admin_id)') == 2`. **A contagem de
ocorrências não sabe distinguir EM QUAL ramo elas estão:** as duas que ele conta são
`:427-428` e `:493-494`. O ramo que o docstring de `:211-213` diz cobrir — "o de
importação (skip_contabil)" — é `:378-385`, e **nunca teve nenhuma das duas**. O teste
afirma no próprio docstring aquilo que não verifica, e passa verde.

O segundo falso verde é mais sutil e é a raiz de E05: os testes de lead (`:175-207`)
chamam `_fechar_lead_da_proposta(p.id, t.admin_id)` **direto** e o fixture `_lead`
(`:167-172`) semeia `Lead(..., proposta_id=proposta.id)` **à mão**. Semear à mão
justamente o campo que nenhum código de produção escreve faz o filtro de `:263` casar
dentro do teste e nunca casar em runtime.

**Esforço:** M.

---

### Task B3.1: perna da obra do A07 — `nova_obra` GET lê os args (independente)

**Files:** Modify `views/obras.py` — `nova_obra()` ramo GET: bloco try `:498-514` e
render `:516-523`; Modify `templates/obra_form.html:389-400`

**Comportamento novo.** O GET lê `request.args`: carrega o Cliente por
(`cliente_id`, `admin_id`) e `lead_id` como inteiro, e manda `cliente_pre` e
`lead_id_pre` ao render de `:518-523`. Nada muda quando os args não vêm. No template, os
dois campos caem para `cliente_pre` **quando `obra` é None**: `value` de `cliente_busca`
vira `obra.cliente_ref.nome if obra ... else (cliente_pre.nome if cliente_pre else '')` e
o hidden `cliente_id` idem; entra
`<input type="hidden" name="lead_id" value="{{ lead_id_pre or '' }}">`.

**Faz primeiro por ser independente** — `crm_views.py:974-977` aponta para
`main.nova_obra` sem alias no meio. Entrega sozinha: o botão "criar obra" do CRM passa a
chegar com o cliente escolhido.

**Teste que prova:** T6 (primeira metade).

**Riscos → mitigação.**
1. **O template é COMPARTILHADO** entre nova obra (`views/obras.py:518`, `obra=None`) e
   edição. A pré-seleção **só pode valer no ramo `obra is None`** — se vazar para a
   edição, abrir `/obras/editar/<id>?cliente_id=<outro>` troca o cliente da obra
   existente na primeira gravação.
2. O autocomplete JS de `:830-857` escreve em `inputId`/`inputBusca` por
   `getElementById`: sobrescreve os valores assim que o usuário digita — **é o
   comportamento desejado**, não tentar "proteger" o valor pré-carregado.
3. Cliente de outro tenant: filtrar por `admin_id` e, se não achar, **não pré-selecionar
   e NÃO abortar** — o `except Exception` de `:493-496` e o try de `:499-514` têm a mesma
   patologia e transformariam um 404 em redirect. Manter as duas queries **fora** do try
   de `:499`, em bloco próprio: se dentro, uma falha zera funcionários e serviços junto
   (o fallback de `:513-514`).

- [ ] **Step 1:** GET lê os args + render
- [ ] **Step 2:** template com fallback e hidden `lead_id`
- [ ] **Step 3:** commit — `feat(obras): nova obra pré-preenche o cliente que o CRM manda`

---

### Task B3.2: perna da proposta do A07 — as duas linhas acopladas, no MESMO commit

**Files:** Modify `propostas_consolidated.py` — alias `nova_proposta()` `:1183-1188`; e
`nova()` `:510-540`, bloco entre a query de `templates_proposta` (`:528-534`) e o
`render_template` (`:536-540`)

**Comportamento novo.**
1. O redirect passa a preservar `cliente_id` e `lead_id` quando presentes em
   `request.args`.
2. `nova()` carrega a lista de Clientes do tenant
   (`Cliente.query.filter_by(admin_id=admin_id).order_by(Cliente.nome)`) e resolve dois
   hints opcionais: `cliente_id` (Cliente com escopo de `admin_id`, ou None) e `lead_id`
   (só o inteiro). Manda os três ao template: `clientes`, `cliente_pre`, `lead_id_pre`.
   **Isto atende A07 e A22 no MESMO ponto** — a lista existe para o select, o
   `cliente_pre` existe para marcar `selected`.

**A interdependência é absoluta:** `:1188` sozinho é no-op porque `nova()` não lê args;
`:510-540` sozinho só serve URL digitada à mão, e o único chamador de produção continua
perdendo tudo no 302. **Separar produz um commit que passa em revisão e não muda nada.**

**Teste que prova:** T1 e T2.

**Riscos → mitigação.**
1. **NÃO usar `**request.args`.** É um `MultiDict` e `url_for` anexaria QUALQUER
   parâmetro colado na URL — inclusive `_external`, `_anchor`, `_scheme` ou `_method`,
   que `url_for` interpreta como **diretiva de construção**, não como query, abrindo
   redirect para host externo. Montar um dict explícito com **allowlist de duas chaves**,
   só quando o valor for dígito. O alias `criar_proposta()` logo abaixo (`:1193-1198`)
   **não** precisa de mudança — não mexer nele.
2. Cliente de outro tenant: filtrar por `admin_id` e, se não achar, **não pré-selecionar
   e NÃO chamar `abort(404)`** — o `except Exception as e` de `:542-545` engoliria o
   abort e devolveria 302 para `propostas.index`, escondendo o vazamento em vez de
   expô-lo. **O tenant se prova pelo conteúdo renderizado, não pelo status** (é por isso
   que T2 espera 200 com `b.marca` ausente).
3. Usar o mesmo `safe_db_operation(lambda: ..., [])` que as outras queries do bloco usam,
   para não derrubar o formulário se a tabela `cliente` estiver indisponível.
4. Reescrever no mesmo commit o flash de `crm_views.py:930-934`, que hoje diz "Após
   salvar, vincule esta proposta ao lead pela edição do lead" — texto que descreve o
   mundo em que o vínculo não existia. É uma linha, e deixá-la para depois significa
   nunca.

- [ ] **Step 1:** allowlist no alias + leitura em `nova()`
- [ ] **Step 2:** flash de `crm_views.py:930-934`
- [ ] **Step 3:** T1 e T2 verdes
- [ ] **Step 4:** commit — `feat(propostas): nova proposta recebe cliente_id e lead_id do CRM`

---

### Task B3.3: A22 (só o select) — `cliente_id` na proposta manual

**Files:** Modify `templates/propostas/nova_proposta.html:76-79` e o `<form>` de `:33`;
Modify `propostas_consolidated.py` — leitura `:556-560` e construção `:647-659`

**Comportamento novo.** O input de texto `cliente_nome` vira
`<select name="cliente_id" required data-testid="proposta-cliente-id">` populado por
`clientes`, com a option de `cliente_pre` marcada `selected`; dentro do form entra
`<input type="hidden" name="lead_id" value="{{ lead_id_pre or '' }}">`. Na rota,
`criar()` carrega o Cliente com `filter_by(id=..., admin_id=admin_id)`; se achou, grava
`proposta.cliente_id` e usa `cliente.nome`/`email`/`telefone` como fonte de
`cliente_nome`/`cliente_email`/`cliente_telefone` **quando os campos de texto vierem
vazios**. O campo `cliente_cpf_cnpj` de `:94` fica intocado nesta rodada (ver **D8**, §10).

**Vem depois de B3.2** porque a pré-seleção precisa de `cliente_pre`.

**Teste que prova:** T3 (primeira metade — `Proposta.cliente_id == a.cliente_id`).

**Riscos → mitigação.**
1. **`criar()` em `:556` e `:567-569` ainda VALIDA `cliente_nome` como obrigatório** e o
   grava em `proposta.cliente_nome` (`:651`), NOT NULL no modelo (`models.py:3572`). Se
   você simplesmente apagar o input, toda criação cai no flash "Nome do cliente é
   obrigatório" de `:568`. **Template e rota no mesmo commit** — esta é a metade da cadeia
   que quebra produção se sair pela metade.
2. O `except Exception` de `:873-879` redireciona para `propostas.nova` **SEM args**: se a
   validação falhar, o usuário perde o vínculo com o lead e refaz tudo → repassar
   `cliente_id`/`lead_id` nesse redirect e nos de `:569`, `:573` e `:595` também.

- [ ] **Step 1:** select + hidden no template
- [ ] **Step 2:** leitura e atribuição em `criar()`; redirects preservando os args
- [ ] **Step 3:** T3 verde na metade do `cliente_id`
- [ ] **Step 4:** commit — `feat(propostas): select de cliente no formulário manual grava proposta.cliente_id`

---

### Task B3.4: E05 — os dois escritores que faltam

**Files:** Modify `propostas_consolidated.py` — `criar()`, após o `flush()` de `:693`
(que já garante `proposta.id`) e antes do commit; Modify `views/obras.py` — `nova_obra`
ramo POST, após o `flush()` de `:443` e antes do commit de `:488`

**Comportamento novo.**
- Em `criar()`: carrega o Lead com `filter_by(id=lead_id, admin_id=admin_id)` e grava
  `lead.proposta_id = proposta.id`. **É o escritor que E05 acusa faltar**, e o que torna
  `handlers/propostas_handlers.py:263-275` alcançável.
- Em `nova_obra` POST: carrega o Lead e grava `lead.obra_id = nova_obra.id`. **É o segundo
  escritor**: o botão "criar obra" do CRM (`crm_views.py:945-980`) cria a obra DIRETO, sem
  passar por proposta nenhuma, então o caminho pelo handler nunca cobre esse lead.

**Depende de B3.1-B3.3** porque o `lead_id` só chega ao form se o hidden existir e se os
args tiverem sobrevivido ao redirect. **Escrever o writer antes disso é repetir
literalmente o defeito de `handlers/propostas_handlers.py:275`: linha existe, nunca
executa.**

**Teste que prova:** T3 (segunda metade) e T6 (segunda metade).

**Riscos → mitigação.**
1. **NÃO mexer em `lead.status` em nenhum dos dois pontos.** Criar rascunho de proposta
   não fecha lead; criar obra não é a mesma decisão que "proposta aprovada". Quem fecha é
   `_fechar_lead_da_proposta`, na **aprovação**, e é lá que está a guarda de não reabrir
   lead PERDIDO (`handlers/propostas_handlers.py:266-269`), que estes pontos não têm. Se
   um dia quiser fechar por aqui, replicar a guarda.
2. O lead pode já ter `proposta_id` de uma proposta anterior — sobrescrever é o
   comportamento certo (o lead segue a proposta viva), **mas registrar em log**, porque
   isso desamarra a proposta antiga em silêncio.
3. A escrita de `nova_obra` fica dentro do try de `:297-496`, logo participa do rollback
   de `:494` — que é o certo: obra e vínculo commitam juntos ou nenhum dos dois.

- [ ] **Step 1:** `lead.proposta_id` em `criar()`
- [ ] **Step 2:** `lead.obra_id` em `nova_obra` POST
- [ ] **Step 3:** T3 e T6 verdes
- [ ] **Step 4:** commit — `feat(crm): lead ganha proposta_id e obra_id — as FKs deixam de ser letra morta`

---

### Task B3.5: A14 — as duas chamadas no terceiro caminho do handler

**Files:** Modify `handlers/propostas_handlers.py` — ramo
`if valor_total <= 0 or skip_contabil:`, entre a chamada de `:384` e o `return` de `:385`

**Comportamento novo.** As duas chamadas que já existem nos outros dois ramos passam a
existir aqui: `_semear_servicos_reais(proposta_id, admin_id)` e
`_fechar_lead_da_proposta(proposta_id, admin_id)`, **nesta ordem**, antes do `return`.
Obra nascida por importação físico-financeira e proposta de valor zero passam a nascer
com `ServicoObraReal` (pronta para RDO) e com o lead do CRM fechado e amarrado. As duas
funções já são idempotentes (`_semear` por (obra, servico) em `:205-217`; `_fechar` por
comparação campo a campo em `:270-277`) e **nenhuma commita** (`:192-193`, `:254-255`) —
a rota/importador segue dono da transação.

**Por último no bloco**, e não por ser difícil: a metade `_semear_servicos_reais` é
genuinamente independente, mas a metade `_fechar_lead_da_proposta` só tem efeito
observável depois de B3.4 (sem escritor de `proposta_id`, o filtro de `:263` devolve
lista vazia e a chamada nova é tão inerte quanto a antiga). Colocando por último, **um
único teste — T4/T5 — cobre a cadeia inteira de ponta a ponta** em vez de afirmar que uma
linha foi escrita.

**Teste que prova:** T5 (e T4 fecha o circuito). O T5 passa por `EventManager.emit`, que
só acha o handler pelo registro — **se o decorador adotar a função errada, T5 fica
vermelho na hora.**

**Riscos → mitigação.**
1. **ARMADILHA DO DECORADOR.** O `@event_handler('proposta_aprovada')` está na linha
   **284** e adota a função imediatamente abaixo, `handle_proposta_aprovada` em `:285`
   (`event_manager.py:75-80`: o decorator só faz `EventManager.register(event_name, func)`
   e devolve `func` — quem estiver logo abaixo VIRA o handler). Inserir qualquer `def`
   entre 284 e 285 substitui o handler em silêncio, e um teste que chame
   `handle_proposta_aprovada()` direto continua verde. **Nesta mudança você NÃO precisa
   criar função nenhuma** — são duas linhas dentro de um corpo que já existe, na altura de
   `:385`. Se ainda assim um helper for necessário, o único lugar seguro é **antes da
   linha 284** (entre o fim de `_fechar_lead_da_proposta` em `:281` e `:282-283`); helper
   aninhado dentro do próprio handler também é seguro (padrão de
   `_materializar_cronograma_se_houver`, `:329`).
2. **NÃO reordenar as quatro chamadas.** `_propagar_proposta_para_obra` (`:383`) e
   `_materializar_cronograma_se_houver` (`:384`) têm de continuar antes, porque
   `_semear_servicos_reais` lê `proposta.obra_id` (`:198`) e `_fechar_lead_da_proposta`
   também (`:274`) — e quem grava esse campo é o handler VIZINHO,
   `propagar_proposta_para_obra` em `event_manager.py:973`, que roda antes por ordem de
   registro (`EventManager.emit` itera a lista em ordem de append, `event_manager.py:44`).
   No caminho da importação o `obra_id` já vem gravado de
   `services/importacao_fisico_financeiro.py:525` — os dois emissores estão cobertos.
3. Reaprovar revisão reemite o evento e `_fechar_lead_da_proposta` passa a rodar de
   verdade → já coberto: `:266-269` não reabre PERDIDO e `:270-277` só conta o que de fato
   mudou, devolvendo 0 na repetição. T5 emite duas vezes exatamente para travar isso.
   **Não "melhorar" essa função nesta rodada.**
4. As duas chamadas rodam dentro da transação longa do importador; reimportar cria uma
   proposta `FF-<obra.id>` nova e chama a semeadura de novo → não há duplicação:
   `ja_existem` é montado por (obra, servico) lendo `ServicoObraReal` da obra (`:205-208`),
   e a obra é a mesma.

- [ ] **Step 1:** as duas linhas em `:385`, sem criar função nenhuma
- [ ] **Step 2:** T5 verde (as duas variantes: `skip_contabil` e valor zero), reemitindo para idempotência
- [ ] **Step 3:** T4 verde — a cadeia fecha
- [ ] **Step 4:** commit — `fix(propostas): valor zero e importação também semeiam serviços e fecham o lead`

**Backfill — o que fazer com o que já nasceu sem os IDs.** São dois problemas distintos e
a resposta é diferente para cada um.

- **(B1) `ServicoObraReal` faltando — SIM, precisa, e é SCRIPT, não migração.** É
  determinístico: para cada Proposta com `obra_id`, chamar
  `_semear_servicos_reais(p.id, p.admin_id)`, já idempotente e sem commit. Rendimento
  real medido: **36** propostas no tenant do seed. Por que script e não migração 279:
  (a) não há DDL; (b) **`is_migration_executed` PULA EM SILÊNCIO** um número já
  registrado (`migrations.py:68-86`) — um backfill que você não pode reexecutar depois de
  corrigir o código não vale nada, e este é do tipo que se roda duas vezes; (c) um laço
  com N+1 no runner de boot é a família de problema que a 277 teve de resolver com retry
  e log de cadência (`migrations.py:5845`, `:5957`). Pôr em `scripts/`, ao lado de
  `init_planejamento_custos_cli.py`, com `--admin-id` e `--dry-run`. **Fazer B3.5 ANTES** —
  senão a próxima importação recria o buraco.
- **(B2) `Lead.proposta_id`/`Lead.obra_id` dos leads antigos — NÃO backfille.** Não
  existe chave: nada jamais registrou qual proposta veio de qual lead, e qualquer
  casamento por cliente + data + nome erra. Um casamento errado não é cosmético — na
  próxima reaprovação daquela proposta o `_fechar_lead_da_proposta` marca o lead alheio
  como APROVADO e o amarra à obra errada, em silêncio. O volume dispensa o risco: **30
  leads no total** no banco de dev, e dos 19 com `proposta_id` preenchido todos vieram de
  semeadura de teste — em produção são **zero, por construção**. Dezenas de leads um
  humano relinka pela tela do CRM em uma tarde, com a certeza que o script não tem. O que
  vale fazer no lugar: o flash já corrigido em B3.2 e — fora deste recorte — o select de
  proposta no formulário de lead (`crm_views.py:577-603` +
  `templates/crm/lead_form.html`), que dá o caminho manual explícito.

---

### 6.2 A02 + A03 — o recebimento de medição entra no caixa e na contabilidade

**Duas mudanças, separadas de propósito, nesta ordem.** O motivo não é tamanho, é
natureza do erro e de quem revisa: **A02 é caixa** (regime de caixa, tela de fluxo, risco
de dupla contagem) e não depende de julgamento contábil nenhum; **A03 é competência**
(DRE, partida dobrada) e carrega uma pergunta que precisa de resposta humana. Empacotar
junto significa segurar um conserto pronto esperando ratificação de contador — e
misturar, no mesmo diff, duas formas diferentes de contar o mesmo dinheiro, que é o tipo
de mistura que produziu o defeito do p1. **Acoplamento técnico entre eles: zero.**

**A02.** Lado PAGAR: `financeiro_views.py:391` lê `criar_fluxo_caixa` e `:402-420` grava
`FluxoCaixa(tipo_movimento='SAIDA', referencia_tabela='conta_pagar')`. Lado RECEBER:
`receber_conta` (`:631-672`) lê só valor/data/forma/banco (`:641-647`), chama
`FinanceiroService.baixar_recebimento` (`:649-656`) e vai direto ao flash (`:658`) —
**nenhum FluxoCaixa**. `baixar_recebimento` (`financeiro_service.py:297-393`) atualiza a
CR, mexe em `banco.saldo_atual` (`:325`) e tenta lançamento contábil (`:332-385`), mas
nunca toca FluxoCaixa. **A leitura existe e está sem alimentação:**
`financeiro_service.py:684-708` (`rr_query`, `referencia_tabela='conta_receber'`).

**O efeito na tela está ERRADO, não incompleto.** Ao baixar a CR: (a) ela sai de
PENDENTE/PARCIAL e some das entradas previstas (`financeiro_service.py:460-475`); (b) não
nasce linha realizada, porque `rr_query` não acha nada; (c) o KPI "Realizado Líquido"
(`:807`, template `templates/financeiro/fluxo_caixa.html:136`) passa a somar só saídas, a
coluna "Entradas" da tabela mensal (`:322`) fica zerada e a `var_acum_real` do gráfico
(`:641`) só desce. **O dinheiro sai do previsto e não entra no realizado.** O único
número que reage é o saldo do banco (`:457`) — e só se o operador escolher um banco; o
template oferece "— Não registrar no banco —" como primeira opção, e nesse caminho o
recebimento fica invisível em TODOS os números da tela.

**A03, e aqui o candidato do documento está ERRADO.**
`services/medicao_service.py:368-384` (criação) e `:390-409` (update) nunca preenchem
`conta_contabil_codigo`; com o campo NULL, o gate `if conta.conta_contabil_codigo:`
(`financeiro_service.py:332` — conferido hoje) pula as partidas `:333-385` **sem `else` e
sem log** — o silêncio que escondeu o problema. Não depende da Decisão 5: a Decisão 5 é o
DÉBITO da despesa geral; no recebimento o débito já é fixo `1.1.01.001`
(`financeiro_service.py:357`) e o que falta é só o crédito. **MAS** preencher com
`4.1.01.001` (o candidato da reconferência, §3 linha A03) **DUPLICA RECEITA no DRE**:
`handlers/propostas_handlers.py:466-478` já credita `4.1.01.001` contra débito em
`1.1.02.001` pelo valor inteiro do contrato na aprovação, e
`calcular_valor_contas(['4.1.01','4.1.02'],'CREDITO')` (`contabilidade_utils.py:634`)
somaria contrato + todo recebimento. **A receita já foi reconhecida por competência; o
recebimento tem de LIQUIDAR o cliente: crédito em `1.1.02.001` (Clientes)**, que também
já está semeado e aceita lançamento (`contabilidade_utils.py:36`, `_V2_CONTAS_SEED`,
`financeiro_seeds.py:23`). Ver §9, nº 3.

**Esforço:** M.

---

### Task B3.6: o gate contábil deixa de ser mudo

**Files:** Modify `financeiro_service.py:332` (`if conta.conta_contabil_codigo:`)

**Comportamento novo.** Ganha um `else` com `logger.warning` nomeando `conta_id`,
`origem_tipo`, `numero_documento` e valor: "partida dobrada pulada — CR sem
`conta_contabil_codigo`". O silêncio acaba, e qualquer CR que continue fora da
contabilidade passa a deixar rastro no log.

**É a única parte de A03 que não depende de escolha contábil nenhuma — vale sozinha e
entra PRIMEIRO.** Dez minutos, e o log passa a mostrar quantas CRs estão fora da
contabilidade: é diagnóstico para as etapas seguintes.

**Teste que prova:** `caplog` numa baixa de CR sem `conta_contabil_codigo`.

**Risco → mitigação.** **Não mexer no `except` de `:380-385`**: o rollback ali é
intencional e só descarta o lançamento (o recebimento já foi commitado em `:329`).

- [ ] **Step 1:** o `else` com warning
- [ ] **Step 2:** commit — `fix(financeiro): gate de partida dobrada loga quando pula por falta de conta contábil`

---

### Task B3.7: guarda de re-baixa em `receber_conta`

**Files:** Modify `financeiro_views.py` — `receber_conta`, logo após o `first_or_404()`
de `:637`, antes do `if request.method == 'POST'` de `:639`

**Comportamento novo.** Se a conta já está liquidada (saldo <= 0 tratando NULL como
`valor_original`, ou status em `('RECEBIDO','QUITADA','CANCELADO')`), o POST não baixa
nada: flash de aviso e redirect para a listagem.

**Vem ANTES da escrita do FluxoCaixa**, e essa ordem é a mitigação principal do risco de
dupla contagem: é ela que impede que a escrita nova vire dinheiro contado duas vezes.
Fecha o caminho mais plausível — baixar à mão uma CR que o import de extrato já criou
como RECEBIDO (`services/importacao_excel.py:2478`).

**Teste que prova:** terceiro POST do teste de B3.8 — contagem de `FluxoCaixa` não muda e
`conta.valor_recebido` continua 1.000.

**Riscos → mitigação.**
1. `saldo` pode ser NULL em registros legados — o próprio fluxo trata isso em
   `financeiro_service.py:566`.
2. **O status `QUITADA` não pode ficar de fora:** quem quita a CR de medição é
   `services/medicao_service.py:400`, que grava `'QUITADA'`, enquanto
   `baixar_recebimento` grava `'RECEBIDO'` (`financeiro_service.py:315`). Testar os dois.

- [ ] **Step 1:** a guarda
- [ ] **Step 2:** commit — `fix(financeiro): conta a receber já liquidada não aceita nova baixa`

---

### Task B3.8: A02 — o recebimento grava `FluxoCaixa` ENTRADA

**Files:** Modify `financeiro_views.py` — `receber_conta`: ler os dois campos junto de
`banco_id` (`:647`), gravar entre `baixar_recebimento` (`:649-656`) e o flash (`:658`);
ramo GET `:665-672`; Modify `templates/financeiro/receber_conta.html`;
Create `tests/test_a02_recebimento_grava_fluxo_caixa.py`

**Comportamento novo.**
1. A rota lê `criar_fluxo_caixa` (`== '1'`) e `categoria_fluxo_caixa_id`, exatamente como
   `:390-391`. Com o checkbox marcado, após a baixa cria um `FluxoCaixa` com
   `tipo_movimento='ENTRADA'`, `categoria='receita'`, `data_movimento=data_recebimento`,
   `valor=valor_recebido`, `descricao=f'Recebimento: {conta.descricao[:150]}'`,
   `banco_id`, `categoria_fluxo_caixa_id` validado por tenant (padrão de `:403-406`),
   `referencia_tabela='conta_receber'`, `referencia_id=conta_id` e — **diferente do lado
   pagar** — `obra_id=conta.obra_id`.
2. O GET carrega as categorias de fluxo do tenant, só as de tipo ENTRADA (query de
   `:431-434` mais o filtro que `importacao_views.py:485` já usa), e passa `categorias_fc`.
3. O template ganha o checkbox `criar_fluxo_caixa` **value="1"** marcado por padrão e o
   select `categoria_fluxo_caixa_id`, copiando a marcação de
   `templates/financeiro/pagar_conta.html:92-120` — **inclusive o texto "desmarque se já
   foi registrado por outro meio"**, que é o controle de dedup que a casa já adotou no
   lado pagar.

**Teste que prova.** Tenant próprio (admin ADMIN v2 + Cliente + Obra + `BancoEmpresa`) e
uma `ContaReceber` PENDENTE de R$ 1.000 com `obra_id` e vencimento em 2026-02-10. Login
por `POST /login` (padrão de `tests/test_compras_nova_dropdown.py:133-139`) e
`POST /financeiro/contas-receber/<cr_id>/receber`:

| # | Ação | Asserção |
|---|---|---|
| 1 | 400 com `criar_fluxo_caixa=1` | UMA linha `FluxoCaixa` ENTRADA, `referencia_tabela='conta_receber'`, `referencia_id=cr.id`, `valor=400`, **`obra_id=cr.obra_id`**, `data_movimento=2026-02-10` |
| 2 | — | `calcular_fluxo_caixa(admin_id, date(2026,2,1), date(2026,2,28))` — **janela ancorada na semente, nunca `date.today()`** — devolve Σ ENTRADA realizado == 400,00 e a CR ainda PARCIAL contribuindo 600,00 de previsto: total 1.000, **sem dupla contagem** |
| 3 | 2º POST de 600 | DUAS linhas, soma 1.000, CR RECEBIDO |
| 4 | 3º POST de 100 | contagem NÃO muda; `valor_recebido` continua 1.000 (guarda de B3.7) |
| 5 | POST sem o checkbox | nenhuma linha criada |

**Por que o atual não pegava.** `tests/test_fluxo_entradas_realizadas.py:51-57`
**FABRICA à mão** as linhas de `FluxoCaixa` ENTRADA com
`referencia_tabela='conta_receber'` e depois afirma que o leitor as soma. Prova o leitor
(`financeiro_service.py:684-708`) e nunca chega perto do escritor: **nenhum teste da
suíte faz POST em `/financeiro/contas-receber/<id>/receber`**. O teste construiu
justamente a linha que a rota não escreve.

**Riscos → mitigação.**
1. **`obra_id` é obrigatório aqui e o modelo de `:407-418` NÃO o preenche:** `rr_query`
   filtra `FluxoCaixa.obra_id == obra_id` (`financeiro_service.py:695-696`) e sem ele o
   recebimento some do fluxo filtrado por obra.
2. `baixar_recebimento` **já deu commit** em `financeiro_service.py:329` antes de voltar
   — se a criação do FluxoCaixa estourar, o `except Exception` de `:661-663` flasha "Erro
   ao registrar recebimento" com o dinheiro JÁ baixado, **mentindo para o operador** e
   levando-o a repetir. → envolver só o bloco do FluxoCaixa em try próprio, logar, e
   flashar mensagem distinta ("recebimento registrado; o lançamento no fluxo de caixa
   falhou"). A guarda de B3.7 impede o dano caso ele repita mesmo assim.
3. **Não usar `abort()` dentro do try do POST:** o `except Exception` de `:661` engole
   HTTPException e devolve 200 → validar banco/categoria por query e cair para None, como
   `:403-406`.
4. O checkbox precisa de **`value="1"` explícito**: a view compara `== '1'` (`:391`); sem
   o value o navegador manda `'on'` e o lançamento nunca é criado — falha silenciosa
   idêntica à que se está consertando.
5. **DUPLA CONTAGEM CRUZADA** — o defeito que o p1 levou três semanas fechando no custo.
   `services/importacao_excel.py:2469-2503` cria a SUA PRÓPRIA `ContaReceber` e pendura
   nela um `FluxoCaixa` ENTRADA. O dedup do import, `_ja_existe_entrada` (`:2205-2214`),
   compara (`cliente_nome`, `valor_original`, `data_emissao`) contra CRs existentes: a CR
   OBR-MED tem `cliente_nome` do efetivo da obra, `valor_original` = medido acumulado
   (não o recebido) e `data_emissao` do dia em que foi criada — **não casa NUNCA** com uma
   linha de extrato. Hoje não dói porque a baixa manual não escreve nada; a partir de A02,
   o tenant que baixa à mão E importa o extrato conta o mesmo dinheiro duas vezes. Não é
   dedupável por `referencia_id`, porque os dois FluxoCaixa apontam para CRs diferentes.
   → **Três camadas:** o checkbox com o texto do lado pagar (controle explícito do
   operador, padrão já estabelecido); a guarda de B3.7; e **NOMEAR o resíduo em vez de
   fingir que sumiu** — quem concilia por import de extrato tem de desmarcar o checkbox.
   Fechar de vez (fazer `_ja_existe_entrada` olhar também `FluxoCaixa` ENTRADA por
   (valor, data) antes de cunhar CR nova) é **item PRÓPRIO, fora deste recorte**: mexer no
   dedup do import junto com esta mudança é o jeito de repetir a história do p1.

- [ ] **Step 1:** escrever o teste e vê-lo vermelho (zero linhas após o 1º POST)
- [ ] **Step 2:** GET com `categorias_fc`
- [ ] **Step 3:** template com checkbox `value="1"` e select
- [ ] **Step 4:** escrita do FluxoCaixa no POST, em try próprio
- [ ] **Step 5:** os cinco casos verdes; verificar que remover o checkbox ou o `obra_id` deixa o teste VERMELHO
- [ ] **Step 6:** commit — `feat(financeiro): baixa de conta a receber grava FluxoCaixa ENTRADA`

---

### Task B3.9: A03 — a CR OBR-MED nasce com conta contábil

**Files:** Modify `services/medicao_service.py` — `recalcular_medicao_obra`: ramo de
criação `:368-384` e ramo de update `:390-409`, antes do commit de `:411`

**Comportamento novo.** A CR OBR-MED passa a nascer com `conta_contabil_codigo`
preenchido, e o ramo de update preenche **quando estiver NULL** — o que **cura as CRs já
existentes sem migração**, porque esse trecho roda a cada RDO finalizado da obra. Regra:
obra oriunda de proposta (`obra.proposta_origem_id`, já lido em `:359`) → **`1.1.02.001`
(Clientes)**, porque a receita foi reconhecida na aprovação; obra sem proposta (IMC
lançado à mão em `medicao_views.py:199`) → `4.1.01.001`, porque nesse caso nada foi
reconhecido antes.

**Teste que prova:** ver Task B3.10.

**Riscos → mitigação.**
1. **PERIGO REAL.** `ContaReceber` tem **FK COMPOSTA** (`admin_id`,
   `conta_contabil_codigo`) → `plano_contas` (`models.py:2413-2425`). Tenant sem plano
   semeado ⇒ IntegrityError no commit de `:411`, que é chamado pelo handler
   `recalcular_medicao_apos_rdo` (`event_manager.py:1518-1535`); o `except` de
   `:1533-1535` loga mas **NÃO faz rollback**, e `EventManager.emit`
   (`event_manager.py:44-52`) engole — **a sessão fica suja e os handlers seguintes de
   `rdo_finalizado` quebram com `PendingRollbackError`**. → antes de atribuir, chamar
   `seed_plano_contas_if_needed(admin_id)` (`contabilidade_utils.py:1597`, idempotente,
   usa flush e não commit) **E** confirmar
   `PlanoContas.query.filter_by(admin_id=..., codigo=..., aceita_lancamento=True).first()`;
   se não houver, **deixar NULL e logar warning**. Nunca atribuir às cegas.
2. **Não sobrescrever** código já preenchido à mão pelo usuário — só preencher quando NULL.
3. Obras paradas seguem sem conta — e o warning de B3.6 torna isso visível em vez de
   silencioso.

- [ ] **Step 1:** seed + verificação em `PlanoContas` + atribuição nos dois ramos
- [ ] **Step 2:** commit — `fix(medicao): CR de medição nasce com conta contábil (liquidação de cliente)`

---

### Task B3.10: teste de evento do A03 — e a asserção que prova a conta certa

**Files:** Create `tests/test_a03_cr_medicao_conta_contabil.py`

**Cenário.** Reusar a receita de semeadura de
`tests/test_ciclo_proposta_obra_medido_cr.py:55-145` — Proposta + `PropostaItem`
R$ 1.000, `EventManager.emit('proposta_aprovada', ...)`, `TarefaCronograma`
`percentual_concluido=50` + `ItemMedicaoCronogramaTarefa` — e então disparar
`EventManager.emit('rdo_finalizado', {'obra_id': obra.id}, admin_id)`, **que é o caminho
de produção** (`event_manager.py:1518-1535`). Em seguida chamar a ROTA de recebimento
sobre a CR OBR-MED resultante.

**Asserções.**
1. A `ContaReceber` `origem_tipo='OBRA_MEDICAO'` nasce com
   `conta_contabil_codigo='1.1.02.001'` e existe `PlanoContas` (admin_id, '1.1.02.001').
2. Após o recebimento, existe UM `LancamentoContabil` `origem='FINANCEIRO_RECEBER'`,
   `origem_id=cr.id`, com duas `PartidaContabil` de mesmo valor — DEBITO `1.1.01.001` e
   CREDITO `1.1.02.001`.
3. **A asserção que decide se a conta certa foi escolhida:** `calcular_dre_mensal` do
   tenant no período mantém `receita_bruta` igual ao valor do contrato (1.000) **DEPOIS**
   do recebimento — o recebimento não inventou receita nova. É o cão de guarda contra o
   `4.1.01.001` do documento.
4. Tenant sem plano de contas semeado: a CR fica com `conta_contabil_codigo` NULL, o emit
   de `rdo_finalizado` **não deixa a sessão suja** (uma query simples logo depois
   funciona) e o log traz o warning de B3.6.

**Por que o atual não pegava.** `tests/test_ciclo_proposta_obra_medido_cr.py:147-212`
chama `recalcular_medicao_obra` **direto** (nem passa pelo evento, então não cobre a
armadilha do decorador nem a de emitir sem `obra_id`) e só afirma
`valor_medido`/`saldo`/`status` da CR — **nunca olha `conta_contabil_codigo`, nunca olha
`LancamentoContabil`, nunca olha o DRE**.

- [ ] **Step 1:** o arquivo com as quatro asserções
- [ ] **Step 2:** verde
- [ ] **Step 3:** `bash run_tests.sh --gate`
- [ ] **Step 4:** commit — `test(medicao): recebimento de medição liquida cliente sem inventar receita`

---

## 7. B4 — Aposentadorias

**Por que existe, e por último.** As cinco foram reabertas no código vivo e as cinco
continuam mortas — mas **a conclusão prática do enunciado muda: nenhuma das cinco precisa
de DROP, e quatro não precisam de migração alguma.** O que consultei no Postgres desmonta
a premissa de que "aposentar = DROP".

> **Método, e é o que E03/E11 ensinaram:** "grep por instanciação" não prova morte. Nos
> dois casos derrubados o consumo estava em template ou em serviço novo. **E10 quase caiu
> na mesma armadilha:** `templates/obras/detalhes_obra_profissional.html:2276` renderiza
> `{{ cronograma_cliente_items|length }}` e `models.py:7007` declara um backref com
> EXATAMENTE esse nome. Fui ver quem alimenta a variável: `views/obras.py:1983` consulta
> `TarefaCronograma` com `is_cliente=True`, **não** `CronogramaCliente`, e passa como
> variável local em `:2283`. É **homonímia, não leitor**.

**O que o banco decide (consultado agora):**

| Item | Fato do banco | Consequência |
|---|---|---|
| E02 | as **quatro** FKs de `notificacao_cliente` são `confdeltype='a'` (**NO ACTION**) | com linha na tabela, remover os DELETEs faz a exclusão de RDO estourar violação de FK |
| E06 | `folha_pagamento.adiantamentos` é `is_nullable='YES'`, `column_default=None` | tirar do modelo **não** exige DROP: o INSERT sem a coluna funciona |
| E10 | `cronograma_cliente_obra_id_fkey` é `confdeltype='c'` (**ON DELETE CASCADE**) | tabela parada não trava exclusão de obra |

**O teste do bloco:** `tests/test_estruturas_mortas_removidas.py`, quatro cenários, todos
por HTTP com `dois_tenants('mortas')` e `cliente_de(a.admin_id)`, fixture no padrão de
`tests/test_cronograma_endpoints_m05.py:29-36`. Datas ancoradas em `date(2026,1,1)`,
nunca `date.today()`.

| Cenário | Ação | Asserção (banco, após `expire_all`) |
|---|---|---|
| 1 — exclusão de RDO | RDO da obra de A com `RDOMaoObra`, `RDOServicoSubatividade` e `CustoObra`; `POST /rdo/excluir/<id>` | `RDO.query.get(id) is None` **E** as três contagens filhas == 0. **A resposta 200/302 sozinha não vale**: a rota engole exceção e redireciona com flash de erro do mesmo jeito |
| 2 — cronograma do cliente | três `TarefaCronograma` `is_cliente=False` (uma filha via `tarefa_pai_id`, uma com `predecessora_id`); `POST /obras/<id>/cronograma-cliente/gerar`; depois `POST /obras/<id>/cronograma-cliente/1/editar` | `TarefaCronograma(is_cliente=True).count() == 3`, e entre esses um com `tarefa_pai_id` apontando para **outro clone cliente** (não para a tarefa interna) e um com `predecessora_id` idem — prova que o remapeamento das duas passagens sobreviveu; a rota removida devolve **404** |
| 3 — saída de almoxarifado | `AlmoxarifadoItem` + lote com saldo; `POST /almoxarifado/processar-saida` | `AlmoxarifadoMovimento(SAIDA).count() == 1` e o lote teve `quantidade_disponivel` reduzida — a saída física continua sem o evento |
| 4 — registro de eventos | sem rota: ler `EventManager._handlers` (`event_manager.py:17`) após importar `main` | `'material_saida' not in _handlers`; `'nota_fiscal_paga' not in _handlers`; **e a que fecha a armadilha:** `[f.__name__ for f in _handlers['material_entrada']] == ['criar_conta_pagar_entrada_material']` — **um único** handler |

Em 1 e 3, assertar também que a marca do tenant B não aparece e que os registros de B
seguem com a contagem original.

**Por que o formato dos pacotes não serve aqui, e falha nos dois sentidos.** Contra uma
REMOÇÃO, um teste textual é pior que inútil: um `assert "EventManager.emit('material_saida'"
in texto` fica **VERMELHO ao apagar código morto** — reprova a limpeza correta, e o
reflexo de quem vê vermelho é desfazer a remoção. E, pior, **se a remoção quebrar de
verdade** (o decorador solto de `event_manager.py:87` adotando
`criar_conta_pagar_entrada_material`, ou a exclusão de RDO estourando FK), nenhum grep vê:
o texto que sobrou está sintaticamente perfeito. O primeiro só aparece inspecionando
`EventManager._handlers`; o segundo só exercitando `POST /rdo/excluir/<id>` e contando
linhas — a rota captura a exceção, faz rollback e redireciona, então **302 sai igual no
sucesso e no fracasso**.

**Esforço:** M. **Ordenado por risco crescente:** o que sai sem migração primeiro, o que
toca banco por último. Cada passo é commitável sozinho e o teste cresce junto.

---

### Task B4.1: E01 — remover `handlers/financeiro_handlers.py` e o import do boot

**Files:** Delete `handlers/financeiro_handlers.py` (186 linhas: `@event_handler` `:15`,
`handle_nota_fiscal_paga` `:16-115`, `determinar_conta_despesa` `:118`,
`obter_nome_categoria` `:143`, `gerar_numero_lancamento` `:168`);
Modify `app.py:427-431` (o `import handlers.financeiro_handlers` de `:428`)

**Comportamento novo.** Nenhum handler de `'nota_fiscal_paga'` é registrado no boot.
Comportamento de usuário: **zero** — não havia emissor. `grep nota_fiscal_paga` fora de
`archive/`/`docs/`: só o próprio arquivo; zero `emit`; o único emissor dinâmico
(`utils/catalogo_eventos.py:114`, `_safe_emit`) só serve os 7 eventos `dominio.acao`.

**Teste que prova:** cenário 4 (`'nota_fiscal_paga' not in _handlers`). Escrever esta
asserção primeiro — é barata e já monta o arquivo que os passos seguintes usam.

**Riscos → mitigação.**
1. **Não** deletar `gerar_numero_lancamento` achando que propostas depende dela:
   `handlers/propostas_handlers.py` tem a SUA PRÓPRIA definição em `:499` e a chama em
   `:446`. São duas cópias independentes. `handlers/__init__.py` é só docstring.
2. Remover o arquivo **sem** tirar o bloco de `app.py` faz o `except Exception` engolir o
   `ModuleNotFoundError` e o boot passa a logar um WARN permanente — o vício que o
   comentário de `app.py:415-419` registra ter sido corrigido para `folha_handlers`. →
   **arquivo e bloco no mesmo commit.** O bloco irmão de propostas (`:421-425`) fica intacto.

- [ ] **Step 1:** asserção do cenário 4 no arquivo de teste
- [ ] **Step 2:** remover arquivo + bloco de `app.py`
- [ ] **Step 3:** commit — `chore(handlers): remove handler órfão de nota_fiscal_paga`

---

### Task B4.2: E08 — remover o handler `material_saida` (a armadilha do decorador)

**Files:** Modify `event_manager.py` — do decorador `:87` até a última linha do corpo,
`:125`

**Comportamento novo.** `'material_saida'` deixa de ter handler registrado. Como o
handler só logava (`:121`, sem `add`/`commit`), nenhuma escrita muda.

**Teste que prova:** cenário 4 — e **a asserção que fecha a armadilha**:
`[f.__name__ for f in EventManager._handlers['material_entrada']]` com um único elemento.
**Rodar este teste ANTES de tocar nos emissores**: se o corte tiver ficado errado, ele
falha aqui, isolado.

**Riscos → mitigação.**
1. **ARMADILHA DO DECORADOR.** A linha `:128` é `@event_handler('material_entrada')` e
   `:129` é o `def criar_conta_pagar_entrada_material` (conferido hoje em `:123-131`). O
   corte tem que terminar em `:125` e **preservar as duas linhas em branco** — se sobrar o
   decorador de `:87` sem função abaixo, ele adota `criar_conta_pagar_entrada_material` e
   **a entrada de material passa a rodar DUAS vezes**, criando `GestaoCustoPai` duplicado
   a cada entrada. Teste que chama a função direto **não vê isso**.
2. Tirar dois eventos do registro muda a contagem logada no boot (`app.py:411`,
   `event_manager.py:1539`) → nenhuma ação: `list_events()` só alimenta esses dois logs e
   nenhum teste ou rota assere o número.

- [ ] **Step 1:** cortar `:87-125`, preservando as linhas em branco
- [ ] **Step 2:** cenário 4 verde, com a asserção do handler único
- [ ] **Step 3:** commit — `chore(eventos): remove handler write-nothing de material_saida`

---

### Task B4.3: E08 — remover os dois emissores de `material_saida`

**Files:** Modify `views/almoxarifado/movimentos.py` — bloco try/except do emit
`:599-610` (em `processar_saida`, rota `:444`) e `:887-901` (em
`processar_saida_multipla`, rota `:623`)

**Comportamento novo.** As duas rotas param de emitir. Continuam criando
`AlmoxarifadoMovimento`, baixando lote e comitando exatamente como hoje — **o commit
acontece ANTES do bloco removido nos dois casos** (`:597` e `:885`).

**Por que os emissores eram inertes:** `:600` usa `'movimento_id': movimento.id if
movimento else 0`, e `movimento` é a variável do loop de lotes (`:580`) — carrega o id do
**último lote**, não o da saída; `:891` usa `'movimento_id': 0` literal. Como `0` é
falsy, o handler retornava em `:106-107`. E `material_saida` **não está** em
`WEBHOOK_EVENT_ALLOWLIST` (`utils/webhook_dispatcher.py:59-75`, dez eventos, todos
`proposta.*`/`obra.*`), então também não tinha efeito externo via n8n.

**Teste que prova:** cenário 3.

**Riscos → mitigação.**
1. No segundo bloco o `for item_validado in itens_validados:` (`:888`) existe só para
   emitir — sai junto. **Conferir que `item` e `quantidade` rebindados ali não são lidos
   depois:** não são, o `jsonify` de `:902-907` usa `total_processados` e
   `funcionario.nome`.
2. **NÃO remover** o `from event_manager import EventManager` de `:8` — os quatro emits
   de `'material_entrada'` (`:138`, `:189`, `:347`, `:391`) continuam vivos.

- [ ] **Step 1:** remover os dois blocos
- [ ] **Step 2:** cenário 3 verde
- [ ] **Step 3:** commit — `chore(almox): rotas de saída deixam de emitir evento sem handler`

---

### Task B4.4: E06 — remover o atributo `FolhaPagamento.adiantamentos`

**Files:** Modify `models.py:2818`

**Comportamento novo.** O modelo deixa de mapear a coluna. **A coluna continua existindo
no banco, inerte:** é nullable sem default de banco, então todo INSERT novo grava NULL e
nenhuma escrita quebra. Nenhum dado de folha é apagado. Único escritor vivo estava em
`archive/legacy_cleanup/passo_9/folha_pagamento_utils.py:510`; os relatórios que enumeram
descontos listam coluna por coluna e não a incluem (`folha_pagamento_views.py:1066`,
`:1096`, `:1257`, `:1259`); o escritor vivo (`:176-189`) não a passa.

**Teste que prova:** `bash run_tests.sh --gate` verde e a rota de processamento de folha
continua criando `FolhaPagamento`.

**Riscos → mitigação.**
1. **NÃO tocar em `models.py:2903`** (`funcionario = db.relationship('Funcionario',
   backref='adiantamentos')`, dentro da classe `Adiantamento`) — é homônimo e é usado de
   verdade pela rota `/folha/adiantamentos` (`folha_pagamento_views.py:709`, template
   `templates/folha_pagamento/adiantamentos.html`). Todos os hits de "adiantamentos" em
   `templates/` são dessa entidade.
2. **Não escrever DROP COLUMN.** Folha de pagamento é registro legal e o ganho de tirar a
   coluna do banco é zero. Escrever no commit, em uma linha, que a coluna fica no banco de
   propósito.

- [ ] **Step 1:** remover a linha
- [ ] **Step 2:** gate verde
- [ ] **Step 3:** commit — `chore(models): FolhaPagamento.adiantamentos sai do modelo (coluna fica inerte no banco)`

---

### Task B4.5: E10 — remover a rota órfã `editar_cronograma_cliente`

**Files:** Modify `views/obras.py:3200-3250` (decorador `:3200`, def `:3203`)

**Comportamento novo.** `POST /obras/<id>/cronograma-cliente/<item_id>/editar` deixa de
existir e passa a responder 404. É POST **órfão**: grep de `editar_cronograma_cliente` e
de `cronograma-cliente/.../editar` em `templates/` e `static/` → vazio.

**Primeiro entre as três peças do E10, e a ordem interna importa:** removida a rota e
rodado o cenário 2, se algo quebrar o passo culpado é óbvio.

**Teste que prova:** cenário 2 (404 na URL removida **e** regeneração intacta).

**Risco → mitigação.** Nenhum `url_for('main.editar_cronograma_cliente')` existe em
`templates/`/`static/` (conferido), então não há `BuildError`. A rota
`gerar_cronograma_cliente` continua referenciada em
`templates/obras/detalhes_obra_profissional.html:2326` — **essa NÃO sai**.

- [ ] **Step 1:** remover a rota
- [ ] **Step 2:** cenário 2 verde
- [ ] **Step 3:** commit — `chore(obras): remove rota órfã de edição do cronograma do cliente`

---

### Task B4.6: E10 — remover o delete da tabela legada

**Files:** Modify `views/obras.py:3133-3140` (bloco `# Legacy: limpa também a tabela
antiga`, dentro de `gerar_cronograma_cliente`, `:3094-3197`)

**Comportamento novo.** `gerar_cronograma_cliente` continua idêntica menos a limpeza da
tabela legada — segue apagando e reclonando `TarefaCronograma(is_cliente=True)` e
chamando `deduplicar_tarefas_cronograma`.

**Teste que prova:** cenário 2 de novo (as três tarefas cliente e os dois remapeamentos).

**Risco → mitigação.** O `try/except Exception: pass` de `:3134-3140` é o que hoje engole
erro na tabela legada; ao removê-lo, conferir que nada mais no bloco depende dele.

- [ ] **Step 1:** remover o bloco
- [ ] **Step 2:** cenário 2 verde
- [ ] **Step 3:** commit — `chore(obras): geração do cronograma do cliente deixa de limpar a tabela legada`

---

### Task B4.7: E10 — remover o modelo `CronogramaCliente`

**Files:** Modify `models.py:6988-7010` (inclui o backref
`Obra.cronograma_cliente_items` em `:7007`); Modify `views/obras.py:4` (token
`CronogramaCliente` na lista de import)

**Comportamento novo.** O modelo deixa de ser carregado. **A tabela `cronograma_cliente`
fica no banco**, sem modelo e sem escritor — preservando qualquer cronograma legado que
exista em algum tenant, e seguro porque a FK é ON DELETE CASCADE. Nada cria linhas: grep
por `CronogramaCliente(` devolve só a declaração; a geração migrou para
`TarefaCronograma(is_cliente=True)`.

**Teste que prova:** cenário 2 + gate verde.

**Risco → mitigação.** O backref removido tem o **MESMO NOME** da variável de contexto
lida em `templates/obras/detalhes_obra_profissional.html:2276`. Confirmar (feito) que a
variável vem de `views/obras.py:1983-1990` (consulta `TarefaCronograma`) e é passada em
`:2283`. **Se alguém reapontar o template para o atributo do objeto, o badge zera
silenciosamente** — a asserção do cenário 2 é o que fixa o comportamento correto.

- [ ] **Step 1:** remover modelo + token do import
- [ ] **Step 2:** cenário 2 e gate verdes
- [ ] **Step 3:** commit — `chore(models): remove CronogramaCliente (tabela fica parada no banco)`

---

### Task B4.8: E02 — GATE de produção e limpeza dos três pontos vivos

**Files (só após o gate):** Modify `crud_rdo_completo.py` (token no import `:6`; linha
`:530`); `views/rdo.py` (token no import `:4`; linha `:565`; e o comentário `:537-544`);
`services/importacao_fisico_financeiro.py` (import local `:346`; linhas `:368-369`;
comentário `:357-361`)

**GATE ABSOLUTO — antes de escrever qualquer linha:** rodar
`SELECT count(*) FROM notificacao_cliente` no banco de **PRODUÇÃO**. Neste ambiente a
contagem é **0**, mas este não é o banco de produção e essa contagem não vale como
evidência.

- **count == 0** → o E02 entra inteiro (esta Task e a B4.9).
- **count > 0** → **o E02 sai deste plano.** As quatro FKs são NO ACTION e os DELETEs de
  `crud_rdo_completo.py:530` e `views/rdo.py:565` são o que hoje sustenta a exclusão de
  RDO; a remoção quebraria produção. E a decisão de descartar ou preservar aviso de
  cliente é **de dado, não de schema**.

**Comportamento novo (com o gate liberado).** A exclusão de RDO deixa de limpar a tabela
morta e passa direto para `RDOFoto` (`crud_rdo_completo.py:531`); os demais deletes e
nulificações (`:531-541`) ficam intactos. A rematerialização de RDOs na importação deixa
de anular a FK (`services/importacao_fisico_financeiro.py:368-369` era UPDATE, não
DELETE); `CustoObra`, `MovimentacaoEstoque` e `AlocacaoEquipe` continuam tratados igual.

**Ordem interna obrigatória:** `crud_rdo_completo.py:530` → `views/rdo.py:565` →
`services/importacao_fisico_financeiro.py:368-369`, **rodando o cenário 1 depois de cada
um**; depois os três tokens de import; depois o modelo `models.py:3057-3094`.

**Teste que prova:** cenário 1, repetido a cada passo.

**Riscos → mitigação.**
1. O terceiro ponto é **o mais fácil de esquecer**: está num serviço, não numa rota, e o
   import é **local dentro da função** (`:345-347`), então grep por `from models import`
   no topo do arquivo não o encontra.
2. O comentário de `views/rdo.py:537-544` nomeia `notificacao_cliente` entre as quatro
   FKs sem ON DELETE e explica o porquê — é o registro de um bug caro (RDO ficando OCO).
   **Reescrevê-lo para três FKs, não apagá-lo**, senão vira documentação mentirosa.
3. `crud_rdo_completo.py` usa flash+redirect, não `abort` — **não introduzir abort** nesta
   passagem.

- [ ] **Step 1:** contagem em produção
- [ ] **Step 2 (se 0):** os três pontos, na ordem, com o cenário 1 entre cada
- [ ] **Step 3:** os três tokens de import + o modelo + o comentário corrigido
- [ ] **Step 4:** commit — `chore(models): remove NotificacaoCliente e os três pontos de limpeza`

---

### Task B4.9: E02 — migração 279, auto-guardada pela contagem

**Files:** Modify `migrations.py` — `_migration_279_drop_notificacao_cliente`, registrada
na lista de `:6343` logo abaixo da 278, no padrão de `_migration_278_baseline_bac`
(`:6032`)

**Comportamento novo.** A migração **CONTA antes de dropar**:
`SELECT count(*) FROM notificacao_cliente` e, se > 0, `raise` com mensagem explícita.

**Por que isso a torna segura por construção:** `run_migration_safe` grava status
`'failed'` (`migrations.py:194`), `is_migration_executed` só considera `'success'`
(`:86`) e a migração **retenta no boot seguinte** em vez de ficar marcada como aplicada;
e `executar_migracoes` não derruba o boot (retorna False, `:200`). Assim ela nunca
destrói dado de cliente, e só passa quando a tabela está provadamente vazia. Se ficar
`failed`, o E02 volta para decisão humana.

**Teste que prova:** rodar em dev (tabela vazia → sucesso) e, num banco de teste com uma
linha semeada, confirmar `failed` sem `DROP`.

**Risco → mitigação.** Dropar tabela vazia não é remover dado. Se a contagem em produção
divergir entre a Task B4.8 e o deploy, o guard da própria migração pega.

- [ ] **Step 1:** escrever a migração com o guard de contagem
- [ ] **Step 2:** registrar em `migrations.py:6343`
- [ ] **Step 3:** testar os dois caminhos (vazia → sucesso; com linha → failed)
- [ ] **Step 4:** commit — `feat(migrations): 279 — drop de notificacao_cliente com guard de contagem`

---

## 8. O que foi CORTADO e o que foi ADIADO

Esta seção é **obrigatória e não pode ser resumida**. Quem retomar daqui a um mês
precisa saber que cada omissão abaixo foi **decisão**, não esquecimento. As duas listas
são diferentes em natureza: **cortado** significa "não voltamos a isto sem fato novo";
**adiado** significa "volta quando a trava sair".

### 8.1 Cortados

| Item | Razão do corte |
|---|---|
| **A20** — pré-preencher pedido com o vencedor da cotação | Era **P, virou M**: `MapaFornecedor` guarda o fornecedor só como `nome` (String(200)), **sem FK para `Fornecedor`** (`models.py:6887-6904`; o mapa v1 idem, `models.py:6793`). Custa coluna + migração + tela de amarração para poupar **um preenchimento**. Casamento por nome seria frágil. Custo maior que o benefício |
| **A21** — FK de frota no equipamento do RDO + "TypeError de kwargs" | Duas metades, as duas fracas. O TypeError (`crud_rdo_completo.py:428`, `:429`, `:449`) está dentro de `salvar_rdo()`, **função sem rota** desde `b30923b5` (`crud_rdo_completo.py:237-254` documenta) — é **código morto catalogado como incidente de produção sem ser**. Os dois caminhos vivos (`views/rdo.py:865-866`, `rdo_editar_sistema.py:509-510`) usam `replace_equipamentos_ocorrencias`, com os kwargs corretos (`utils/rdo_equip_ocorr.py:82-88`, `:106-112`). A FK de frota é integração **sem dor relatada** |
| **A23** — aviso interno de comprovante e decisão de compra do portal | **Não existe canal interno para plugar.** `NotificacaoOrcamento` (`models.py:7438`) é específica de estouro por `ObraServicoCusto`, e `NotificacaoCliente` (`models.py:3061`) está na própria lista de mortas (E02, ver B4). Construir um canal é **feature**, não automação — e a decisão de qual canal (Decisão 7 do `PLANO-NUCLEO.md`) **nem foi tomada** |
| **Fase 7 / folga livre no scheduler** | Último resíduo de fase declarada obsoleta em `PLANO-NUCLEO.md:106` e §8. O sistema **já tem** folga total e caminho crítico (`services/cronograma_scheduler.py:307-457`). **Corte com efeito colateral útil: libera a faixa de migração 280-283** (ver §12) |
| **E03** — `ObraSignatarioCliente.email` | **Sai da lista de estruturas mortas: não está morta.** Exibição existe e é visível ao usuário — `templates/obras/_signatarios_cliente.html:74` renderiza `{% if s.email %} · {{ s.email }}{% endif %}`, incluído por `templates/obra_form.html:550`, alimentado por `views/obras.py:1137-1141`. E o leitor é de `1fbc97c0` (29/07), **dois dias antes** do documento que a declarou morta: a linha estava errada quando foi escrita. Nada a aposentar |
| **B1.14** — dedup de XML por tenant + guarda de `chave_acesso` (cortada em **05/08**) | **Primeira Task deste plano a ser cortada, e a razão é que consertá-la piora.** A função inteira que ela toca — `almoxarifado_utils.py:250` `processar_xml_nfe` — **não tem chamador vivo**: `grep` fora de `archive/` devolve a definição de `:250` e mais nada (reconferido em 05/08; o único outro acerto é um docstring de teste que registra justamente a morte). Impacto em produção hoje: **zero**. E a metade mecânica da Task — pôr `admin_id` no `filter_by` de `:257` — **troca uma mensagem amigável errada por um 500**: com o `xml_hash` escopado, o fluxo passa a alcançar o `db.session.add` de `:328` + `flush()` de `:329` e estoura `IntegrityError` contra o UNIQUE **global** de `NotaFiscal.chave_acesso` (`models.py:2626`, `unique=True` na coluna). O defeito de verdade é esse UNIQUE, e trocá-lo por `UNIQUE (admin_id, chave_acesso)` **não é decisão de execução** (§12). **Volta se, e só se, `processar_xml_nfe` ganhar chamador — e aí junto com a decisão sobre o UNIQUE**, nunca antes |
| **E11** — `subatividade_mestre_id` como ponte | **Sai da lista: não está morta.** O p8 (`ecf7f3a9`) entregou o leitor — `services/progresso_subatividade.py:41` e `:66` —, com consumidor real em `services/medicao_service.py:279-284`. Não é aposentadoria, é o oposto; o resto do p8 segue aberto como A18 (adiado) |

**Consequência de método, que vale para a próxima lista de estruturas mortas:** "grep por
instanciação" **não prova morte**. Nos dois casos derrubados (E03, E11) o consumo estava
em template ou em serviço novo, e nos dois a busca por `Classe(` devolveria vazio. Foi
essa mesma armadilha que E10 quase repetiu (ver a nota de homonímia no B4).

### 8.2 Adiados — voltam quando a trava sair

| Item | Trava | Quando volta |
|---|---|---|
| **A17** — pré-carregar a mão de obra do RDO da presença do dia | Toca exatamente a superfície que A05, A10 e A16 estão consertando (`views/rdo.py:622-714`, `RegistroPonto`/`AllocationEmployee` do dia). Pré-carregar sobre um custo instável multiplicaria o defeito em vez de expô-lo | Depois de B1 estabilizado e com o arreio de B0 verde nas rotas de RDO e ponto |
| **A12** — reprocesso de folha estornar antes de recriar | **Sem fatia segura.** `folha_pagamento_views.py:148-153` faz `delete()` + commit e nada mais; os efeitos (`:226-266` Pai/Filho, `:198-200` evento → `event_manager.py:1235-1236`, `:281-288` agregado) não são estornados. Estorno parcial duplica de outro jeito | Decisão de contador + negócio: estornar lançamento emitido × lançar contrapartida, e o que fazer com pai da Gestão de Custos já **pago** |
| **A15** — unificar a medição do portal com o trilho ponderado | Mexer no percentual do portal mexe em `valor_medido`. Os dois geradores escrevem a **mesma tabela com semânticas diferentes**: `portal_obras_views.py:782-783` grava acumulado, `services/medicao_service.py:195` grava o valor do período | Decisão 4 do `PLANO-NUCLEO.md` (medições históricas) + a dualidade de fonte do p8/A18 |
| **A24 completo** — ligar o pipeline de encargos | O pipeline (`services/folha_service.py:1378-1444`) está completo e **sem chamador**; ligá-lo exige a regra de rateio por obra para funcionário em várias obras no mês | Decisão 6 do `PLANO-NUCLEO.md`. **A fatia aritmética (o `× 0.7`) NÃO está adiada** — é B2.13/B2.14 |
| **A16, segunda metade** — emitir `ponto_registrado` do ramo do plano | **D6** (§10). E, mesmo respondida, tem de vir depois de B1.9-B1.11: emitir do ramo de preenchimento antes da guarda existir seria emitir custo por cima de um atestado | Resposta da D6 |
| **A18** — derivar progresso entre trilhos | Escrita segue dual em ~15 pontos; unificá-la muda o número que multiplica `valor_contrato` em `portal_obras_views.py:768` | Decisão 4 do `PLANO-NUCLEO.md` |
| **A01, A04, A08, A25** | A01 é P e independente, mas não é dinheiro perdido nem número errado — não coube na espinha desta rodada. A04 espera a conta do contador (Decisão 5). A08 espera a regra de rateio (`PLANO-NUCLEO.md:489`). A25 espera credencial e infra (Decisão 7) | Próxima rodada / decisões respectivas |
| **E04** — `AlocacaoEquipe` + FK `rdo_gerado_id` | Conferência em base de **produção** antes do DROP; dev mediu 33 linhas com `rdo_gerado_id` vazio e ninguém provou o mesmo em produção. Além disso os pontos vivos são **três**, não dois (`views/rdo.py:561-563`, `crud_rdo_completo.py:539`, `services/importacao_fisico_financeiro.py:372-373`) | Contagem em produção, junto do gate de E02 |
| **E12 completo** — SMTP + painel de exportação | Infra. **A fatia honesta (a rota que mente) NÃO está adiada** — é B2.15/B2.16. O painel que dá 500 (`exportacao_relatorios.py:597-604`, template inexistente) e o SMTP não configurado (`:530-591`) seguem como estão | Decisão 7 do `PLANO-NUCLEO.md` |
| **Fase 8** | O A2 dela precisa ser **reprojetado**, não ajustado | Reprojeto |
| **Fase 9a (resto) e 9b** | 9b só depois da Fase 6, por decisão de 03/08 | Fase 6 executada |

---

## 9. Contradições registradas

Onde dois recortes divergiram, **não escolhemos em silêncio**. Cada linha diz qual foi
adotada e por quê.

**1 — Os testes-guarda textuais: apagar ou rebaixar?**
O recorte de **A05** (ordem interna, item 7) diz que os dois testes textuais de
`tests/test_p1_dedup_cross_origem.py:151-165` "podem ir embora, o teste de rota novo cobre
o que eles fingiam cobrir". O recorte de **B0** diz o oposto: "não delete os textuais;
custam milissegundos e pegam uma classe real — alguém reintroduzir a chamada direta 'só
aqui', que foi como a assimetria nasceu (mensagem do commit `31aed041`)".
**Adotado: B0 — manter e rebaixar** (Task B0.6). Razão: o erro deles nunca foi existir, é
serem os ÚNICOS; e o custo de mantê-los é milissegundos contra uma classe de regressão
que o teste de rota, sozinho, não previne — ele detecta a chamada direta **depois** de
ela produzir efeito, o textual a detecta na revisão.

**2 — O destino da família V1 de progresso.**
A reconferência (§7, linha A19) manda consolidar a família V1 em
`_progresso_fallback_subatividades`, e chama isso de fatia que "não depende de decisão
nenhuma". O recorte de **A19 derruba o destino**: aquela função
(`utils/cronograma_engine.py:1024-1041`) responde "média simples das subatividades do
ÚLTIMO RDO da obra" — um retrato de um dia —, e nenhum dos sete call-sites pergunta isso.
**Adotado: o recorte** — nasce `progresso_v1_acumulado`, função irmã, e
`_progresso_fallback_subatividades` **não é tocada** (segue servindo
`progresso_geral_para_kpi` em `:1117`). Razão: mandar os sete para lá trocaria quatro
números acumulados por um número de um dia só, que **decresce** quando o apontador corrige
para baixo. A parte da reconferência que se mantém é a conclusão: a consolidação não
depende de decisão de negócio.

**3 — A conta de crédito do recebimento de medição (A03).**
A reconferência (§3, linha A03) sugere `4.1.01.001 Receita de Serviços` como candidato. O
recorte de **A02+A03 mostra que isso duplica receita no DRE**:
`handlers/propostas_handlers.py:466-478` já credita `4.1.01.001` contra débito em
`1.1.02.001` pelo valor inteiro do contrato na aprovação, e
`contabilidade_utils.py:634` somaria contrato + todo recebimento.
**Adotado: crédito em `1.1.02.001` (Clientes)** — liquidação do recebível, não receita
nova (Task B3.9), com a asserção do DRE (B3.10, item 3) como cão de guarda. **A
reconferência precisa ser corrigida nesse ponto.**

**4 — Quantos pontos de recálculo o editor v2 tem (A06).**
A reconferência (§3, linha A06) diz "seis chamadas"; o recorte, ao abrir
`cronograma_views.py`, encontra **sete pontos de inserção** — o backlog fundiu
`_recalc_e_resposta_vinculo` (`:1411-1421`) com `_aplicar_hierarquia` (`:1680-1687`), que
são funções distintas servindo sete rotas.
**Adotado: sete** (Tasks B2.19 e B2.20), mais três pontos deixados de fora com decisão
própria (**D12**, §10).

**5 — Quantos caminhos de RDO estão vivos.**
A manchete da reconferência fala em "três payloads". O recorte de B0 mede e o de A05
confirma: **dos três, só DOIS estão vivos** — `crud_rdo_completo.py:475` está dentro de
`salvar_rdo()`, função sem rota (`crud_rdo_completo.py:243-254`). E o inventário completo
de caminhos que gravam custo de RDO é **seis**, não quatro.
**Adotado: dois emissores vivos com payload truncado; seis caminhos no total** — e o
`:475` recebe o payload corrigido por consistência, com comentário, sem contar como
caminho vivo em métrica nenhuma (Task B1.4).

**6 — `depende_de` do recorte A09.**
O recorte declara `depende_de: ["A09"]`, o que é autorreferência e não pode ser lido
literalmente. **Adotado: o bloco não depende de nada** além de B0 — a ordem interna
(vazamento primeiro, dedup por último) é a que o próprio recorte argumenta e está nas
Tasks B1.12→B1.16.

---

## 10. Decisões que este plano precisa

Doze, numeradas. Cada uma traz: a pergunta em uma frase, quem responde, o que trava, e
**o default recomendado se a resposta não vier** — de modo que nenhuma delas seja motivo
para o plano parar.

As decisões **4, 5, 6 e 7 do `PLANO-NUCLEO.md` §7** seguem valendo como estão e **não são
repetidas aqui**; onde travam algo deste plano, o item está na §8.2 (adiados).

---

### D1 — `lancar_custos_rdo` ganha fallback de horista, ou os três caminhos voltam à chamada direta? E qual mecanismo de custo é canônico?

**A constatação que amarra as duas metades: A05 e A11 são a MESMA decisão.** Escolher se
o handler passa a saber calcular custo de horista, e escolher qual dos dois mecanismos
(`event_manager.lancar_custos_rdo` × `services/rdo_custos.gerar_custos_mao_obra_rdo`) é
canônico, são a mesma pergunta vista de dois lados. O backlog classificava **A11 como
travado em negócio** (`PLANO-NUCLEO.md` §7, e a §7 da reconferência); **não está — é
técnica, e A05 a força.**

**Quem responde:** ninguém de fora. **A leitura já decide**, e este plano a executa: (a)
o **evento é canônico**, porque `gerar_custos_mao_obra_rdo` não grava `CustoObra` (lida
por seis telas) e recusa tenant v1 (`services/rdo_custos.py:337-341`); (b) o handler
**para de calcular valor** e passa a **ler `RDOCustoDiario`**, porque escrever a fórmula à
mão dentro dele seria a sexta cópia — o pecado que o p4 acabou de consertar no progresso.

**O que trava:** nada — a decisão está tomada e registrada aqui. **Fica documentada como
decisão porque o backlog a listava como bloqueio de negócio, e riscar esse bloqueio é
resultado.**

**Default:** o adotado acima (Tasks B1.1-B1.5).

---

### D2 — Depois da divisão do guard, os dois ledgers podem carregar valores diferentes para o mesmo dia?

**A pergunta.** Feita a Task B1.3, no dia em que um mensalista tem ponto E RDO, o
`CustoObra` fica sendo o do **ponto**, calculado com hora extra a 1,5×
(`event_manager.py:504-507`), e o `GestaoCustoFilho` passa a ser o do **RDO**, sem hora
extra nenhuma porque a Task #5 removeu extra do RDO
(`services/custo_funcionario_dia.py:11-14`). Dashboard de custo mede uma coisa, Contas a
Pagar mede outra. Isso é aceitável?

**Quem responde:** negócio (Cássio). **É decisão de negócio de verdade** — as outras do
A05 se resolveram na leitura.

**O que trava:** nada. A alternativa (fazer `gravar_custo_funcionario_rdo` ler
`RegistroPonto` quando ele existir) é **item próprio, bem maior que este**.

**Default se não vier:** executar como especificado. **A divergência ainda é melhor que o
zero de hoje** — hoje o mensalista com ponto não tem `GestaoCustoFilho` nenhum.

---

### D3 — O arreio (B0) entra em `main` com testes vermelhos, ou sai junto de B1?

**A pergunta.** B0 nasce vermelho nos casos que dependem de A05/A10/A16. Se entrar assim,
o gate deixa de ser verde e a equipe perde o sinal — justamente o que se quer consertar.

**Quem responde:** quem opera o gate (Cássio / quem revisa).

**O que trava:** a granularidade da entrega. No primeiro caso **B0 é entregável sozinho
hoje**; no segundo, B0 vira o Step 0 de B1 e sai junto.

**Default recomendado: entrar sozinho, com `@pytest.mark.xfail(strict=True,
reason='<item>')` nos casos que dependem de B1, e SÓ neles.** `strict=True` faz o teste
falhar quando o defeito for corrigido e alguém esquecer de tirar a marca — **o xfail vira
o checklist de B1**. Os que já passam (idempotência, isolamento, paridade da rota
flexível) entram sem marca e viram a rede contra a próxima regressão. É o melhor dos dois
mundos e é o que as Tasks B0.3-B0.5 já assumem.

---

### D4 — O que a coluna "Saldo" da tela de planejamento passa a significar?

**A pergunta.** Depois que "Orçado" virar custo
(`templates/obras/planejamento_custos/lista.html:98`): (a) `orçado − realizado` = "quanto
ainda posso gastar nesta etapa", coluna informativa e sempre viva; ou (b)
`orçado − projetado` = folga contra o plano, que em serviço com linhas dá **0,00** enquanto
se está dentro do orçamento e só fica negativa no estouro.

**Quem responde:** produto (Cássio).

**O que trava:** **só a coluna Saldo.** As duas dão exatamente o mesmo gatilho de alerta,
então a decisão **não bloqueia** `utils/notifications.py`, `views/catalogo_views.py` nem
`services/resumo_custos_obra.py`.

**Default recomendado: (a)** — é a pergunta que o gestor faz olhando a tela. Se a resposta
não vier a tempo da Task B2.3, entregar só a coluna Orçado com o cabeçalho renomeado para
"Custo Orçado", deixando explícito que Saldo ainda é a régua antiga; **o que não pode é
deixar as duas metades em regras diferentes sem dizer.**

---

### D5 — O percentual do detalhe do RDO pode subir?

**A pergunta.** Em obra V1, `views/rdo.py:1335` (exibido em
`templates/rdo/visualizar_rdo_moderno.html:1256`) passa a ser calculado sobre as
subatividades **APONTADAS**, não sobre o catálogo de `SubatividadeMestre` cadastrado. É o
que faz essa tela convergir com a lista, a consolidada e o PDF, e o que elimina a
possibilidade de passar de 100%. Em troca, obra que cadastrou 10 subatividades mestre e
apontou 2 delas a 100% deixa de mostrar 20% e passa a mostrar 100%. Aceitável?

**Quem responde:** produto (quem lê essa tela).

**O que trava:** só o call-site A. Se a resposta for não, o item ainda se faz — a
convergência é de **seis** pontos, não de sete.

**Default recomendado: sim, aceitável**, sabendo que o rótulo "N subatividades total" de
`:1258` continua exibindo o catálogo planejado **logo ao lado** (a Task B2.9 exige que ele
seja preservado exatamente por isso).

---

### D6 — Ponto SEMEADO pelo plano (turno previsto, sem batida) deve gerar custo?

**A pergunta.** Hoje `services/rdo_custos.py:367-373` pula o lançamento do RDO
justificando "já tem ponto — o custo virá pelo handler `ponto_registrado`", e **nada em
`models.py` emite esse evento** (`grep EventManager models.py`: vazio). O dia perde o
custo **pelos dois lados**. Emitir do ramo do plano faz o sistema faturar previsão como se
fosse realizado; não emitir mantém o buraco.

**Quem responde:** negócio. **O código é pequeno nos dois casos; a resposta não.**

**O que trava:** a segunda metade do A16 (§8.2). **Não trava a fatia deste plano** — as
Tasks B1.9-B1.11 entregam a guarda e valem sozinhas.

**Default se não vier:** manter como está (não emitir) e executar só a guarda. Registrar
que o buraco continua aberto e nomeado.

**Segunda pergunta acoplada:** falta gerada automaticamente pelo cron
(`models.py:4783`) deve poder ser convertida em dia trabalhado quando a alocação é criada
retroativamente, ou toda ausência exige correção manual? **Default: a versão conservadora
— toda ausência protegida**, com WARNING no log para o caso aparecer.

---

### D7 — Qual é a chave de dedup de NF quando a entrada não tem fornecedor?

**A pergunta.** Proposta: (`nota_fiscal`, `admin_id`, `fornecedor_id IS NULL`). Se o
negócio preferir bloquear NF repetida independentemente do fornecedor, a chave cai para
(`nota_fiscal`, `admin_id`) e o comportamento visível ao almoxarife muda.

**Quem responde:** negócio / almoxarifado.

**O que trava:** só o comportamento de borda da Task B1.16.

**Default recomendado:** a proposta com `fornecedor_id`. Colapsar para
(`nota_fiscal`, `admin_id`) faz o mesmo número de NF de dois fornecedores diferentes
colidir, e recusa entrada legítima.

---

### D8 — O CPF/CNPJ da proposta é ponteiro para o cadastro ou snapshot congelado no ato?

**A pergunta não é "`Cliente.cnpj` ou coluna nova".** É: **o documento na proposta é um
ponteiro ou um snapshot?** Se ponteiro, lê-se `Cliente.cnpj` (`models.py:3354`) via
`proposta.cliente_id` e não se guarda nada — mas corrigir o cadastro reescreve
retroativamente o documento de propostas já emitidas e assinadas. Se snapshot, precisa de
coluna nova em `propostas_comerciais` mais migração, e cadastro e proposta passam a poder
divergir de propósito.

**Quem responde:** quem responde pelo documento contratual — Cássio + contador. **Não é
decisão de código.**

**Dois fatos que a decisão precisa ter na mesa, conferidos agora:**
(1) `templates/propostas/detalhes_proposta.html:159-160` e
`templates/propostas/editar.html:97` **já leem** `proposta.cliente_cpf_cnpj`, atributo que
não existe em `models.py:3563-3580` — o Jinja resolve como Undefined e o bloco não
aparece; hoje o usuário digita em `templates/propostas/nova_proposta.html:94`,
`propostas_consolidated.py:559` lê em `cliente_documento`, **a variável morre ali e o dado
some sem uma linha de erro**. Se for "ponteiro", esses dois templates passam a ler
`proposta.cliente_ref.cnpj`; se "snapshot", o nome da coluna nova já está escolhido por
eles.
(2) `services/cliente_resolver.py:79-125` desduplica Cliente por **nome e e-mail e NUNCA
por CNPJ** — logo, hoje, dois Clientes com o mesmo CNPJ e nomes escritos diferente são
duas linhas, e um documento guardado como ponteiro apontaria para um dos dois
arbitrariamente.

**O que trava:** só a segunda metade do A22. **O select de cliente e o
`proposta.cliente_id` (Task B3.3) NÃO dependem dela.**

**Default se não vier:** entregar só o select. O documento continua sendo digitado e
descartado, como hoje — sem regressão, e com o buraco nomeado.

---

### D9 — Ratificação contábil: o recebimento da medição apenas liquida o cliente?

**A pergunta, em uma frase, para o contador:** "a receita já é reconhecida por competência
na aprovação da proposta (`handlers/propostas_handlers.py:466-478` credita `4.1.01.001`
pelo contrato inteiro) — confirma-se que o recebimento da medição deve apenas **LIQUIDAR o
cliente** (D `1.1.01.001` / C `1.1.02.001`), sem gerar receita nova?"

**Quem responde:** contador.

**O que trava:** só a Task B3.9. **Não é a Decisão 5 do `PLANO-NUCLEO.md`** (aquela é o
débito da despesa geral; aqui o débito já é fixo e o que falta é o crédito).

**Default se não vier:** entrar assim mesmo com a parte que não depende dela e já é ganho
— o `else` com `logger.warning` no gate de `financeiro_service.py:332` (Task B3.6). **Foi
o silêncio que escondeu o problema.** A02 (Tasks B3.7/B3.8) **não tem decisão pendente
nenhuma** e anda sozinha.

---

### D10 — Existe operação real de um funcionário em DUAS obras no mesmo dia que precise virar custo separado por obra?

**A pergunta.** O código responde **não** em todos os caminhos
(`ponto_service.py:105-110` reusa o registro do dia **ignorando `obra_id`**; o modelo tem
um único conjunto de horários) — **mas o código nunca foi perguntado ao negócio.**

**Quem responde:** negócio.

**O que trava:** nada da Task B1.6/B1.7 — elas consertam a perda de hoje. Se a resposta
for **sim**, o suporte a rateio por obra vira **item próprio**, com coluna de turno em
`RegistroPonto`, e aí sim uma migração.

**Default:** executar como especificado. **Ele assume o não, que é o que o sistema inteiro
já assume.**

---

### D11 — Qual é a contagem de `notificacao_cliente` no banco de PRODUÇÃO?

**Quem responde:** ops (uma consulta).

**O que trava:** o E02 inteiro (Tasks B4.8 e B4.9). Os outros quatro itens do B4 **não
dependem dela**.

**Default se não vier:** **não fazer o E02.** Não há default seguro do outro lado: as
quatro FKs são NO ACTION e os DELETEs de `crud_rdo_completo.py:530` e `views/rdo.py:565`
são o que hoje sustenta a exclusão de RDO. Neste ambiente a contagem é 0, **e essa
contagem não vale como evidência.**

---

### D12 — Os três pontos de recálculo fora dos sete entram no A06?

**A pergunta**, em três partes, cada uma com trade-off próprio:
1. **`cronograma_views.py:2339`** — `/cronograma/calendario` com `recalcular_tudo=1`
   (def `:2322`) itera TODAS as obras ativas do tenant. É o **pior caso de correção**:
   alternar sábado/domingo muda `dias_uteis_entre` (`utils/cronograma_engine.py:73-82`) e
   portanto invalida TODO `percentual_planejado` já gravado no parque inteiro, não só o de
   uma obra. Mas é O(N obras) e já é lento; o replanejamento enxuto acrescenta ~2 queries +
   1 commit por obra. Vale um POST de administrador mais demorado para não deixar a curva
   de todas as obras podre?
2. **`cronograma_views.py:3704`** — `aplicar_template` (def `:3580`). Aplicar template numa
   obra que JÁ tem RDO muda datas e suja a curva. **Leitura recomendada: entra** (mesmo
   defeito, custo idêntico) — mas é caminho de `flash`/redirect e não de JSON, então o
   tratamento de falha muda de forma.
3. **`desfazer_acao` (`:2003`) e `refazer_acao` (`:2026`)** — restauram `data_inicio`/
   `data_fim` via `services/cronograma_undo.py:52-58` + `aplicar_payload` e
   **deliberadamente não recalculam** (`:178`). Depois de A06, a curva volta replanejada
   para as datas **desfeitas** — divergência que hoje não existe porque a curva nunca é
   replanejada.

**Quem responde:** quem opera o cronograma (produto).

**Default recomendado:** incluir o item 3 **no mesmo PR** (é barato e coerente: as datas
mudaram, a curva acompanha — e a alternativa cria um estado que nenhum caminho conserta),
incluir o item 2, e deixar o item 1 fora até haver resposta.

**Fora de decisão, para registro:** `views/obras.py:2678` e
`services/cronograma_proposta.py:782` também recalculam, mas são **criação de obra** — não
existe apontamento de RDO para replanejar. Ficam de fora com segurança.

**Pendência a registrar junto (não é decisão, é item futuro):** depois de A06 a linha
"planejado" da Curva S vira **plano corrente**, não compromisso. Falta uma curva planejada
**derivada da `CronogramaBaseline`** — item novo, fora de A06, e é melhor registrá-lo aqui
do que descobri-lo em produção.

---

## 11. Sequenciamento

### 11.1 A regra de ouro

**B0 antes de tudo.** Não por processo: porque uma regressão de custo já foi aprovada por
um gate de 1778 asserções verdes, e repetir a correção sem trocar o instrumento de medida
é repetir o método que produziu o defeito. Dentro de B0, a ordem é a das Tasks: helpers →
coletores → **RDO primeiro** (é o único com dinheiro comprovadamente perdido hoje e
esforço P) → ponto → sync do plano (o mais caro de montar) → aprovação → aperto dos `<=`.

### 11.2 O que pode andar em paralelo

| Trilha | Blocos/Tasks | Por que é independente |
|---|---|---|
| **T1 — custo do RDO** | B1.1 → B1.5 | Toca `event_manager.py` (handler `rdo_finalizado`), `services/rdo_custos.py`, `views/rdo.py`, `crud_rdo_completo.py`, `rdo_editar_sistema.py` |
| **T2 — presença** | B1.6 → B1.11 | Toca `event_manager.py` (handler `ponto_registrado`), `views/admin.py`, `models.py` (`AllocationEmployee`) |
| **T3 — tenant + almoxarifado** | B1.12 → B1.16 | Toca `views/obras.py`, `almoxarifado_utils.py`, `views/almoxarifado/movimentos.py` |
| **T4 — custo orçado** | B2.1 → B2.6 | Toca `services/custo_orcado.py`, `utils/notifications.py`, `views/catalogo_views.py`, `services/resumo_custos_obra.py`, `models.py` (property) |
| **T5 — progresso V1** | B2.7 → B2.12 | Toca `utils/cronograma_engine.py`, `views/rdo.py`, `services/rdo_pdf_service.py`, `crud_rdo_completo.py`, `views/obras.py` |
| **T6 — números honestos** | B2.13 → B2.16 | `services/folha_service.py` e `exportacao_relatorios.py` — não colidem com nada |
| **T7 — curvas** | B2.17 → B2.20 | `utils/cronograma_engine.py` (outra função) e `cronograma_views.py` |
| **T8 — cadeia CRM** | B3.1 → B3.5 | `propostas_consolidated.py`, `views/obras.py`, `handlers/propostas_handlers.py`, templates |
| **T9 — financeiro** | B3.6 → B3.10 | `financeiro_views.py`, `financeiro_service.py`, `services/medicao_service.py` |
| **T10 — aposentadorias** | B4.1 → B4.9 | Por último, e por definição |

**T1, T2, T3 podem andar em paralelo entre si.** **T4, T6, T7, T8, T9 idem.** As
restrições reais são poucas e estão abaixo — e todas têm motivo técnico, não de gosto.

### 11.3 O que NÃO pode andar em paralelo, e por quê

**Ponto de serialização nº 1 — `event_manager.py`.** É o arquivo mais disputado do plano.
Três trilhas escrevem nele, em regiões diferentes:

| Trilha | Região | Colisão |
|---|---|---|
| T1 (A05) | `lancar_custos_rdo` `:649-969`; `recalcular_medicao_apos_rdo` `:1526-1531` | — |
| T2 (A10) | `calcular_horas_folha` `:302-566` | — |
| **T1 ∩ T2** | **o guard inverso `:379-390`** | **Task B1.2 muda `:379-390` (dentro de `calcular_horas_folha`, território de T2) porque a chave de origem do RDO mudou.** É a única sobreposição de linha entre as duas trilhas |
| T4 (E08) | handler `material_saida` `:87-125` | Não colide com T1/T2 — **mas ver a armadilha do decorador abaixo** |

**Regra:** B1.2 e o `in_` do guard inverso saem **no mesmo commit** — separados, existe
uma janela em que batida tardia de diarista volta a duplicar. E T2 não deve tocar
`:379-390`: quem mexe lá é T1.

**Armadilha do decorador — vale para todo mundo que abrir `event_manager.py` ou
`handlers/propostas_handlers.py`.** `@event_handler` adota a função inserida logo ABAIXO
dele (`event_manager.py:75-80`). Três lugares deste plano são especialmente sensíveis:
- `event_manager.py:87` (decorador de `material_saida`) e `:128-129` (`material_entrada`):
  o corte da Task B4.2 tem que terminar em `:125` — sobrar o decorador de `:87` sem função
  abaixo faz a entrada de material rodar **duas vezes**;
- `event_manager.py:649-650`: não extrair helper novo entre o decorador e
  `def lancar_custos_rdo` (Task B1.1);
- `event_manager.py:302`: a mudança da Task B1.6 é toda dentro do corpo;
- `handlers/propostas_handlers.py:284-285`: a Task B3.5 são **duas linhas dentro de um
  corpo que já existe** — se um helper for mesmo necessário, o único lugar seguro é antes
  de `:284`.
**Nenhum teste que chame a função direto pega isso.** Só inspeção de
`EventManager._handlers` pega (cenário 4 do B4).

**Ponto de serialização nº 2 — `migrations.py`.** Este plano propõe **uma única**
migração, a 279 (Task B4.9). Se qualquer outro trabalho em curso — Fase 6, p10 — precisar
de número, **a alocação tem que ser combinada antes de o arquivo ser tocado**, porque o
registro é uma tupla única em `:6343` e dois PRs concorrentes escolhendo 279 produzem
merge silencioso com número repetido — e `is_migration_executed` **PULA EM SILÊNCIO** um
número já registrado (`:68-86`). Ver §12.

**Ponto de serialização nº 3 — `views/obras.py:727-770`.**
**B1.13 (acrescenta `admin_id` a `calcular_progresso_real_servico`) precisa vir ANTES de
B2.8 (apaga a função inteira).** O filtro entra, é validado pelo T4 do arreio de
almoxarifado, e depois a função sai. Fazer B2.8 primeiro invalida o T4. É a única
colisão entre B1 e B2 — e é entre trilhas que, sem ela, seriam paralelas.

**Outras dependências de ordem, todas internas a um bloco:**

| Depende | De | Motivo técnico |
|---|---|---|
| B1.5 | B1.2 | Remover as chamadas diretas antes da chave nova = perder a chave que `remover_custos_rdo` reconhece; a edição de RDO fica sem caminho de correção |
| **B1.5b** | **B1.5 — MESMO commit, sem exceção** | Escrito como "depende de", e **medido como inseparável**: a B1.5 troca o guard que decide (estreita do serviço → larga do handler) e, sozinha, colapsa os RDOs do dia num lançamento só — mensalista de 4h+4h perde metade do dia. Entre os dois commits o parque ficaria com custo a menos. Corrigido no lugar: as duas saem juntas |
| B1.3 | B1.2 | A cláusula de resíduo em `remover_custos_rdo` precisa da chave certa para casar |
| **B1.7** | **B1.6** | **Contraintuitivo, e é o mais importante da §11:** se `/novo_ponto` for corrigido antes da chave, o cenário da troca de obra fica **pior que hoje** — 1 `RegistroPonto` de 4h com 2 `CustoObra` de 4h, o dia cobrado em dobro sem linha que justifique. Com a chave estreitada primeiro, o pior caso intermediário é o custo de hoje |
| B1.11 | B1.9, B1.10 | É a única que pode gerar registro duplicado; separada para ser descartável sem desfazer o resto |
| B2.4 | B2.3 | Remover a property antes de a tela mudar de fonte quebra a tela |
| B2.6 | B2.2, B2.3, B2.5 | É o que reescreve `realizado_*` no banco, alimentando as três; trocar o critério antes faz os testes delas mudarem de resposta no meio do caminho |
| B2.8 | B2.7 | A função nova precisa existir antes de a velha sair (e ver a colisão com B1.13) |
| **B2.9 (PDF) ⟂ B2.9 (tela)** | — | **Mesmo commit, sem exceção.** Separar abre uma janela em que o papel que o cliente assina e a tela do apontador mostram números diferentes |
| B2.19 | B2.17, B2.18 | O helper concentra as três armadilhas; ligar `atualizar_tarefa` primeiro isola o único ponto onde a ordem relativa importa (o `perc_manual`) |
| B2.20 | B2.19 | Propagar só depois de o desenho estar provado por teste |
| B3.2 (as duas linhas) | — | **Mesmo commit.** `:1188` sozinho é no-op; `:510-540` sozinho só serve URL digitada à mão |
| B3.3 (template + rota) | — | **Mesmo commit.** `cliente_nome` é NOT NULL: só o template quebra toda criação |
| B3.4 | B3.1, B3.2, B3.3 | O `lead_id` só chega ao form se o hidden existir e os args sobreviverem ao redirect. Escrever o writer antes é repetir o defeito de `handlers/propostas_handlers.py:275` |
| B3.5 | B3.4 | Sem escritor de `proposta_id`, o filtro de `:263` devolve lista vazia e a chamada nova é tão inerte quanto a antiga |
| B3.8 | B3.7 | A guarda de re-baixa é o freio; escrever no fluxo de caixa antes dela é criar dupla contagem |
| B3.10 | B3.9, B3.6 | O teste só existe depois da atribuição, e a asserção do tenant sem plano depende do warning |
| ~~B1.14 (as duas edições)~~ | — | ~~**Mesmo commit.** A `:257` sozinha troca recusa amigável por IntegrityError 500~~ — **Task CORTADA em 05/08 (§8.1).** O par continua verdadeiro e é parte da razão do corte: não havia como entregar metade |
| B4.3 | B4.2 | Rodar o teste do registro de handlers antes de tocar nos emissores isola a armadilha do decorador |
| B4.7 | B4.5, B4.6 | Rota → bloco legado → modelo: nessa ordem, se algo quebrar o passo culpado é óbvio |
| B4.9 | B4.8, D11 | Gate de produção primeiro |

### 11.4 Ordem recomendada de entrega

**Onde a entrega está, em 05/08:** **passos 1 e 2 fechados.** Da T3 saíram B1.12,
B1.13, B1.15 e B1.16; a B1.14 foi **cortada** (§8.1). **O próximo trabalho é o
passo 3 — o B2 —, e ele não espera nada.**

1. ~~**B0**~~ ✅ (a D3 foi respondida pelos fatos: entrou sozinho, com xfail strict —
   o default recomendado, e os oito xfail funcionaram como checklist até o fim:
   sete caíram cobrados pelo próprio mecanismo que corrigiram).
2. ~~**B1 inteiro**~~ ✅ **A05, A10, A16-a e A09 fechados.** T1 (B1.1-B1.5b), T2
   (B1.6-B1.11) e T3 (B1.12, B1.13, B1.15, B1.16), com a **B1.14 cortada** (§8.1).
   A serialização do guard inverso
   foi consumida pela T1 (a B1.2 mudou `:379-390`) e a T2 nunca precisou esperar —
   foi o principal efeito prático de A05 ter fechado primeiro.
   *Fica aberto de T2 só o que depende de gente: rodar a `q7` em PRODUÇÃO (B1.8
   Step 2) e a segunda metade do A16, travada pela D6.*
3. **B2**, com T4/T5/T6/T7 em paralelo — lembrando **B1.13 antes de B2.8**.
4. **B3**, T8 e T9 em paralelo.
5. **B4**, por último, com o gate de produção de D11 antes do E02.

### 11.5 A armadilha de construção que apareceu quatro vezes, agora com mecanismo

**"O segundo cliente no mesmo `app_context` não completa"** está registrado três
vezes neste documento como fato observado, sem explicação. Em **05/08 o mecanismo
foi isolado, e ele não é o que a frase sugere** — o segundo cliente completa muito
bem; ele completa **como o primeiro usuário**.

**`g` pertence ao APP context, não ao request.** O Flask-Login guarda o usuário
resolvido em `g._login_user`, e dentro de um único `with app.app_context():` esse
cache sobrevive de uma requisição de teste para a seguinte. O segundo
`cliente_de(...)` monta a sessão certa, mas a rota nunca chega a resolvê-la:
`current_user` já está preenchido com quem entrou primeiro. Medido: dois clientes
no mesmo contexto, `g._login_user.id` == admin de **A** depois do GET de A, e o
GET seguinte de B na obra de A responde **200**; o mesmo GET, com o cliente de B
sozinho, responde **404** — a rota está certa, o instrumento é que mentia.

**O perigo real é o falso VERDE, não o vermelho.** Um teste de isolamento escrito
assim afirma "B não enxerga o dado de A" enquanto na verdade A está olhando os
próprios dados — e passa. Foi por sorte que as três ocorrências anteriores
falharam em vez de passarem.

**Varredura do repositório em 05/08: quatro blocos** usam dois ou mais clientes no
mesmo `app_context` (`test_clausulas_configuraveis.py:192`,
`test_cronograma_revisao_obra_gate.py:200`,
`test_e2e_proposta_aprovacao_cliente.py:230`, `test_orcamento_formato_br.py:110`).
**Nenhum está contaminado:** os quatro usam o par "logado + anônimo" contra rota
pública por token que não lê `current_user` em lugar nenhum (conferido em
`propostas_consolidated.py:2507`). Não há dívida a pagar — há uma regra a seguir.

**A regra: um request AUTENTICADO por `app_context`. O resto é precondição
semeada no banco.** É o que a B1.16 já tinha feito por tentativa e erro
(`test_arreio_almoxarifado_e_tenant.py:167`); daqui em diante se faz sabendo
por quê. O achado saiu do teste de tenant da **B2.2**, que deu vermelho por
motivo falso e mandou investigar em vez de "consertar" a rota — que estava certa.

---

## 12. Migrações

**Este plano propõe UMA migração: a 279**, e ela é condicional.

| Nº | Item | Condição | Status |
|---|---|---|---|
| **279** | `_migration_279_drop_notificacao_cliente` (Task B4.9) | Só se **D11** (contagem em produção) devolver **0**. A própria migração **conta antes de dropar** e faz `raise` se > 0 | Proposta |

**Registro conferido agora em `migrations.py`:** a maior registrada é a **278**
(`_migration_278_baseline_bac`, `migrations.py:6032`, registrada em `:6343`); a 277 está
em `:6342`. **279 está livre.**

### Avisos que custam uma fase se ignorados

- **O número 270 está QUEIMADO.** A migração do editor v2 consta sob **270 e 277**, e
  `is_migration_executed` **PULA EM SILÊNCIO** um número já registrado
  (`migrations.py:68-86`) — quem reusar o 270 escreve uma migração que nunca roda e nunca
  avisa.
- **A faixa 271-276 é RESERVADA da Fase 6** (`docs/superpowers/plans/2026-07-21-fase-6-*`,
  Tasks 1, 3, 4, 6, 10 e 12). **Não usar.**
- **A faixa 280-283 está LIBERADA** — era da Fase 7, cortada nesta rodada (§8.1). Quem
  precisar de número depois do 279 pode usá-la, e é o primeiro efeito prático do corte.
- **Antes de cravar qualquer número, conferir o registro em `migrations.py`.** Dois PRs
  concorrentes escolhendo o mesmo número produzem merge silencioso.

### O que NÃO vira migração, e por quê

| Tentação | Por que não |
|---|---|
| Índice único em `RegistroPonto(funcionario_id, data)` (A10) | Semanticamente certo — o modelo não comporta dois registros no dia e os nove outros criadores já o presumem — **mas produção quase certamente já tem linhas que o violam** (foi `/novo_ponto` que as criou), e o `CREATE UNIQUE INDEX` falharia, ou pior, exigiria deletar histórico dentro de uma migração. **Só depois que `q7` (Task B1.8) devolver zero ou um número consolidável.** Aí seria a 280 |
| `DROP COLUMN folha_pagamento.adiantamentos` (E06) | Coluna nullable sem default de banco: tirar do modelo basta. **Folha de pagamento é registro legal** e o ganho de tirar do banco é zero |
| `DROP TABLE cronograma_cliente` (E10) | A FK é ON DELETE CASCADE: tabela parada não trava nada, e ficar parada **preserva cronograma legado** de algum tenant. É o "parar de gravar e deixar quieta" que a regra manda preferir |
| `UNIQUE (admin_id, chave_acesso)` em `NotaFiscal` (A09) | `models.py:2550` é UNIQUE **global**. Trocar é decisão de negócio, não de execução, e **sem urgência**: nenhuma rota chama `processar_xml_nfe` hoje. Se vier, é ≥ 279 (isto é, 280+) |
| Backfill de `ServicoObraReal` (B3.5) | É **script**, não migração: não há DDL, e um backfill que você não pode reexecutar depois de corrigir o código não vale nada — `is_migration_executed` pularia em silêncio na segunda tentativa |
| Backfill de `conta_contabil_codigo` nas CRs OBR-MED (A03) | O ramo de update de `recalcular_medicao_obra` (`services/medicao_service.py:390-409`) roda a cada RDO finalizado e **cura a base sozinho** |
| Correção do histórico de `encargos_inss_patronal` (A24a) | Só se a Task B2.13 devolver número diferente de zero — e aí é **item próprio**, com número a partir de 280 |

---

## 13. O que este plano NÃO cobre

Este documento é um recorte de execução, não um substituto do mapa. **As fases e os
pacotes abaixo seguem existindo e valendo.**

| O que | Onde vive | Relação com este plano |
|---|---|---|
| **§4 do `PLANO-NUCLEO.md`** — os dez pacotes p1..p10 e as seis ondas | `PLANO-NUCLEO.md:190-455` | **Intacta.** Este plano substitui só a §5 (backlog de 25) |
| **§7 do `PLANO-NUCLEO.md`** — as decisões 1 a 7 | `PLANO-NUCLEO.md:530-548` | **Intacta.** As decisões 4, 5, 6 e 7 seguem travando os itens da §8.2. As doze decisões da §10 aqui são **outras**, e são de execução |
| **Fase 6** — orçamento versionado e aditivo | `docs/superpowers/plans/2026-07-21-fase-6-orcamento-versionado-aditivo.md` | Válida; executa no p9. **Reserva as migrações 271-276.** Nenhuma Task deste plano encosta em `ObraContratoVersao`, `AditivoContrato` ou `Obra.valor_contrato` |
| **Fase 7** | `docs/superpowers/plans/2026-07-21-fase-7-*` | **Obsoleta como escrita**, substituída pelo p10. O último resíduo (folga livre) foi **cortado** aqui (§8.1), liberando 280-283 |
| **Fase 8** | `docs/superpowers/plans/2026-07-21-fase-8-*` | **Adiada:** o A2 dela precisa ser reprojetado, não ajustado |
| **Fase 9a (resto) e 9b** | `docs/superpowers/plans/2026-07-21-fase-9-*` | 9a parcial (ciência entregue; `PortalAcesso` inexistente). **9b só depois da Fase 6**, por decisão de 03/08 |
| **p2** — rollout das flags restantes | `PLANO-NUCLEO.md` §4 | `cronograma_mpp_ativo` e `rdo_percentual_livre` seguem manuais; falta a validação de uma semana do editor v2 no parque. **A06 saiu do p2 e virou B2.17-B2.20 aqui** |
| **p6** — reconciliar regimes de peso | `PLANO-NUCLEO.md` §4 | Intacto. A15 (dentro dele) está adiado (§8.2) |
| **p7** — presença única | `PLANO-NUCLEO.md` §4 | **A16-a saiu dele e virou B1.9-B1.11 aqui.** A17 e a aposentadoria de `AlocacaoEquipe` (E04) seguem no pacote, adiados |
| **p8** — convergência da gravação do progresso | `PLANO-NUCLEO.md` §4 | Intacto = A18, adiado pela Decisão 4. **A19 aqui é a família V1 de LEITURA**, disjunta do p8 |
| **p10** — EVM sobre o editor v2 | `PLANO-NUCLEO.md` §4 | Intacto. **Confirmado neste plano que A06 não o afeta**: PV/EV/AC são recalculados a cada requisição e nenhum lê `percentual_planejado` |
| **A reconferência de 04/08** | `docs/reconferencia-backlog-2026-08-04.md` | É a base factual deste plano. **Precisa de três correções**, todas registradas na §9: a conta contábil do A03, o destino da família V1 do A19, e a contagem de pontos do A06 |

---

## Histórico

- **2026-08-05** — **O BLOCO B1 FECHOU**, com a B1.15 entregue. Sai *"o sistema
  está perdendo dado"*; o próximo é o B2, *"o número exibido mente"*.

  **A B1.15 era uma linha, e o que ela ensinou não foi sobre a linha.** 403 vira
  404 em `views/almoxarifado/movimentos.py:278`, e o dado nunca vazou — a consulta
  já filtrava `admin_id`. O que vazava era o **código**: 403 e 404 respondem
  perguntas diferentes para quem enumera `fornecedor_id`.

  🔴 **O teste que a prova — o T5 — não existia, e a B1.12 tinha o Step 1 marcado
  dizendo que sim** (`[x] arreio vermelho (T1, T2, T4, T5)`). `grep` pelo nome da
  rota em `tests/` devolvia vazio: o arreio da T3 nasceu com T1-T4. **É o oitavo
  instrumento defeituoso da rodada, e o primeiro de um tipo novo** — os sete
  anteriores mediam o vazio; este estava ausente com a caixa marcada. A lição de
  método é mais barata que as anteriores: *antes de marcar o checkbox de um
  arreio, `grep` pelo nome da rota.* Escrito agora antes da correção e visto
  vermelho pelo motivo certo (403 ≠ 404, zero movimentos gravados).

  **O Step 2 virou asserção em vez de conferência de olho.** O `fetch` de
  `entrada.html:428` não ramifica por `response.status` — decide por
  `result.success`; nenhum JS do repositório ramifica por 403. Mas ele **exige**
  JSON no corpo, e um 404 que caísse no handler do Flask devolveria HTML e mataria
  a mensagem. O teste passou a afirmar isso.

  ✅ **GATE VERDE ANTES do commit, desta vez:** `1865 passed, 6 skipped,
  3 xfailed`, zero falhas, 18m54s. Contra o gate de 04/08: **+1 teste, e é o T5** —
  a diferença bate com a entrega, item por item. **Nenhum `.py` foi tocado entre o
  início do gate e o commit**, então o resultado vale para a árvore commitada.
  Ontem foi ao contrário (commit primeiro, gate depois, ressalva no corpo que
  ninguém relê); a ordem certa custou espera e mais nada.

- **2026-08-05** — **B1.14 CORTADA**, por decisão do Cássio sobre a recomendação
  que a sessão anterior deixou pendurada. É o **primeiro corte de uma Task deste
  plano** (a §8.1 até aqui só tinha itens `A`/`E` e uma fase inteira), e a razão
  merece ficar: não é "não vale a pena", é **"consertar piora"**. A função está
  morta (`processar_xml_nfe`, zero chamadores fora de `archive/` — reconferido
  hoje), então a Task tinha impacto zero em produção; e a metade mecânica dela
  transformaria uma mensagem amigável errada em `IntegrityError` 500, porque o
  UNIQUE de `NotaFiscal.chave_acesso` é **global** (`models.py:2626`) e escopar o
  `xml_hash` só faz o fluxo chegar mais fundo antes de estourar. O defeito de
  verdade é o UNIQUE, e ele é decisão de negócio.

  **Contagem depois do corte: 61 Tasks, 21 entregues, 40 abertas.** O B1 fica com
  16 e uma única aberta.

- **2026-08-04, fecho da sessão** — **A09 fechado e a T3 quase**: B1.12, B1.13 e
  B1.16 entregues; B1.15 aberta sem impedimento; B1.14 com recomendação de corte.

  ✅ **GATE CONFIRMADO VERDE, depois do commit:** `1864 passed, 6 skipped,
  3 xfailed`, zero falhas, em 25m52s. O commit `bbe74f00` foi feito com o gate
  ainda em execução e diz isso no corpo — **aquela ressalva está superada**, e
  fica registrada aqui porque commit ninguém reescreve. Contra o gate anterior:
  +5 testes (o arreio novo da T3) e o mesmo número de xfail.

  Nenhum arquivo `.py` mudou entre o início do gate e o commit, então o resultado
  vale para a árvore commitada — a única exceção é a correção do *rótulo* de um
  xfail, feita depois e que não altera resultado de teste (só a `reason`).

  As três premissas do §4.4 foram todas reconferidas no código, e **a terceira
  estava errada, sendo do próprio plano**: o `Servico` alheio sai da consulta mas
  **não chega à tela** — template de detalhes não usa a variável, e a edição
  reduz a lista a ids que nunca casam. Reclassificado como defesa em profundidade,
  e o commit renomeado de `fix(tenant)` para `chore(tenant)`.

  **Sexto e sétimo instrumentos vacuosos**, fechando o padrão da sessão em sete:
  um teste por corpo de resposta que teria passado antes e depois da correção
  (por isso a asserção foi para o nível da função), e o terceiro caso de "duas
  rotas no mesmo `app_context`" — o segundo cliente não completa. Reescrito com
  um POST só e a precondição semeada.

- **2026-08-04, noite** — **A10 e A16-a FECHADOS** (B1.6-B1.11). Com isso a trilha
  T2 inteira sai, e o bloco B1 fica só com a T3.
  1. **O plano se contradizia sobre o ponto partido, e a contradição foi levada ao
     Cássio.** A §1 dizia que o dia de 8h "vira metade"; o recorte da B1.7 mandava
     um merge que produziria 4h — coerente e mentindo sobre a jornada. Decisão:
     **turno partido**, com a regra de sobreposição distinguindo correção de
     segunda metade. É a primeira decisão de NEGÓCIO desta execução; as demais
     saíram por leitura.
  2. **A B1.10 piora a B1.11 antes de consertá-la.** Com a guarda nova, um
     atestado de outro tenant passaria a proteger o dia deste. As duas saíram
     juntas por isso — segundo par inseparável da rodada, depois de B1.5/B1.5b.
  3. **Quarto e quinto instrumentos medindo o vazio.** O coletor `custos_obra`
     preso a `tenant.obra_id` num teste cuja invariante é ENTRE obras; e um teste
     de tenant cujo docstring afirmava uma colisão que não existia, porque cada
     tenant tem o seu funcionário com id próprio. **Os dois só apareceram porque
     desligar a correção para ver o teste falhar virou hábito.** Vale como método:
     teste novo que passa de primeira não provou nada até falhar uma vez.
  4. **A B1.11 foi decidida por consulta, não por opinião:** zero divergências de
     `admin_id` em 90 pares casados. Era o risco que a tornava descartável.
- **2026-08-04, fim do dia** — **A05 FECHADO** com B1.5 + B1.5b no mesmo commit.
  Arreio de RDO verde, sem nenhum `xfail` restante no arquivo. O que esta entrega
  ensinou, e que não estava em recorte nenhum:
  1. **A B1.5, sozinha, era uma regressão de dinheiro.** Ela não muda quem escreve
     o custo — muda **qual guard decide**, da chave estreita do serviço para a
     chave larga do handler, e as duas não são equivalentes. Mensalista de 4h+4h
     no mesmo dia passava de R$ 124,00 para R$ 62,00. Só apareceu porque o arreio
     mede dinheiro por rota; um gate de asserção estrutural teria deixado passar.
  2. **A B1.5b não era "comparar valor".** Era distinguir origem **e** comparar
     valor. O guard tem de continuar cego a origem para o PONTO (invariante do p1)
     e passar a enxergar origem para as IRMÃS — outro RDO do mesmo dia não é
     duplicata, é a outra metade do dia. A formulação certa é "o razão do dia
     espelha o conjunto de `RDOCustoDiario`", e ela só ficou visível medindo.
  3. **Terceiro teste vacuoso da mesma família**, e o padrão agora está nomeado: o
     teste posta num formulário que a rota não parseia e mede o vazio. Os três
     casos: dois cenários no mesmo `app_context` (B0.3, duas vezes) e chaves de
     formulário da rota errada (`/rdo/salvar`, aqui).
  4. **Um teste estava vermelho desde `cefba5e7` e ninguém viu** —
     `test_auto_link_servico_rdo.py` procurava a chave de origem antiga. O gate não
     foi re-rodado naquele commit. **Re-rodar o gate no commit que muda uma chave
     não é zelo, é o mínimo.**
- **2026-08-04, tarde** — **B0 fechado (6/6) e B1.1-B1.4 entregues**, em `test/b0-arreio`,
  commits `88d3f924`..`060146ac`. Arreio: 29 passed, 6 xfailed. Três coisas que a
  execução ensinou e que não estavam no plano da manhã:
  1. **Um defeito que eu havia relatado não existia** — o suposto dobro de custo do
     mensalista em dois RDOs do mesmo dia. Medido nos três arranjos, o sistema custeia
     fielmente as horas reportadas. O teste virou congelamento da regra (Status da B0.3).
  2. **No lugar, o arreio achou um defeito real e mais preciso** — o razão não acompanha
     o recálculo cruzado da diária, R$ 75,00 de divergência. Virou a **Task B1.5b**, e é
     o primeiro item deste plano que veio do instrumento de medida, não da leitura. Foi
     para isso que o B0 existiu.
  3. **Duas Tasks foram fundidas em um commit por motivo técnico** (B1.1+B1.2), porque
     separá-las abria uma janela de dupla contagem que o plano não tinha previsto — só
     havia previsto a janela entre B1.2 e B1.3.
  Três XPASS(strict) cobraram remoção de marca obsoleta durante o trabalho: mensalista
  com ponto, segundo andar do razão e a sentinela da medição. **O xfail strict funcionou
  como checklist, exatamente como a D3 supôs.**
- **2026-08-04** — primeira versão. Onze recortes aprofundados no código vivo contra
  `a723babe`, consolidados em cinco blocos e 61 Tasks. Nenhum recorte foi descartado na
  leitura. Três medições feitas rodando o código (não lendo): a perda de R$ 124,00 por
  mensalista por dia nas rotas `/rdo/editar` e `/rdo/finalizar`, a perda de metade do
  custo do dia em ponto partido, e o atestado virando 8h no sync do plano. Seis
  contradições entre recortes registradas e resolvidas na §9.












