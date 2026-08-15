# Plano de execução — Alçadas — 2026-08-15

**O que é.** O plano de execução do spec
`docs/superpowers/specs/2026-08-15-alcadas-design.md`. As decisões e o diagnóstico vivem
lá e não são repetidos aqui; **quando divergirem, o spec vence**.

**Contexto.** Fase 3 de 5 do ciclo de compras. As Fases 1 e 2 são pré-requisito **de
símbolo**: este plano lê `pedido_compra.situacao_recebimento` (Fase 1) e escreve em
`conta_pagar.situacao_liberacao` (Fase 2, migration 288). Se algum não existir, **pare —
a fase anterior não está mesclada.** Do núcleo, depende de `services/alcada_compras.py`
inteiro e de `models.FaixaAlcada`.

**As fronteiras:**
1. **`main` não anda.** Tudo em `feat/alcadas-avancadas`; merge e push esperam o Cássio.
2. **Âncoras por símbolo + literal**, nunca por número de linha.
3. **Red-first**: nenhum passo de implementação sem ver o teste vermelho antes.
4. **Nada de comportamento novo sem a flag.** Com `alcadas_avancadas_ativa` desligada, o
   sistema tem que se comportar exatamente como hoje, faixa a faixa — e o teste de paridade
   é quem prova isso, não a leitura do diff.
5. **Alçada é dado, não código.** Nenhum número desta fase entra num `if`. Teto, mínimo de
   cotações, janela e quais condições valem são linha de tabela, por tenant. O invariante é
   de 21/07 e esta fase não é a que o quebra.
6. **As sete decisões estão fechadas** — 🔬 15/08, todas na recomendação (spec, seção
   "Decisões"). Nenhuma task espera resposta. O que **não** fechou junto é se as regras
   descrevem a operação real: elas são desenho nosso, ratificado. Divergência que aparecer
   ao executar volta para o spec como 📌, não vira ajuste silencioso no código.

**Onde ficam os testes.** `tests/test_alcadas_avancadas.py`, no molde de
`tests/test_financeiro_dois_fluxos.py`: fixtures locais, `pytestmark =
pytest.mark.integration`, tenant por `uuid4()`, sem depender de seed. As fixtures ligam
`escopo_obra_ativo` **e** `compras_governanca_ativa` — sem as duas, todo autenticado é
GESTOR e nenhum teste de papel distingue ninguém.

---

## Ordem e independência

```
A1 (colunas + migrations 297/298/299)
 └─> A2 (flag + carimbo do regime na requisição)
      ├─> A3 (corte de cotações vira dado + o campo do mapa na tela)
      │    └─> A4 (faixa_efetiva: as 4 condições)   ← o conserto que dá nome à fase
      │         ├─> A5 (anti-fracionamento: acumulado nos dois chokepoints)
      │         └─> A6 (rito de emergência 48h + a conta que não libera)
      └─> A7 (tela de faixas — CRUD)
           └─> A8 (sensor, teste-guarda e runbook)
```

A1→A4 é caminho crítico e serial. A5 e A6 são irmãs: nenhuma depende da outra, e A6 é a
única que toca em `financeiro_views`. A7 só depende de A2 (precisa das colunas e da flag,
não do motor) — pode ser feita em paralelo por quem estiver livre, e é a única cortável.

**A4 é o gate de merge**, e A3 vai obrigatoriamente antes dela. O motivo é o 🔴 do spec:
enquanto `mapa_v2_id` não tiver input em template nenhum, a faixa de topo é bloqueio
permanente — subir alguém para ela por condição, sem A3, é entregar requisição que o
usuário não consegue destravar. A5 a A8 podem entrar depois do merge; **A6 não deve ser
ligada em tenant real antes de A8**, porque o sensor é o que enxerga emergência vencida.

---

## A1 — Colunas e migrations 297/298/299

- [x] **Step 0:** conferir `migration_history` no dev **antes** de fixar número. O spec diz
  297-299 e o repositório termina em 296 — mas essa conferência já falhou duas vezes (B6.1
  e R1). Se o dev estiver à frente, renumerar aqui **e no spec**, e não seguir com dois
  documentos discordando.
- [x] **Step 1 (red):** testes do esqueleto: `FaixaAlcada.minimo_cotacoes` nasce 0 e
  `condicoes_ativas` nasce `''`; `RequisicaoCompra.regime_alcada` nasce `'simples'`,
  `emergencial` False, `ratificada_em` None, `degrau_aplicado` `''`;
  `ConfiguracaoEmpresa.alcadas_avancadas_ativa` nasce False e `janela_fracionamento_dias`
  nasce 30. Rodar e **ver os cinco vermelhos**.
- [x] **Step 2:** as colunas em `models.py`, cada uma junto do modelo a que pertence.
  Docstring no padrão da casa em `condicoes_ativas` (por que texto e não quatro booleanos)
  e em `regime_alcada` (por que o regime é carimbado na linha), com ponteiro para o spec.
- [x] **Step 3:** `_migration_297_faixa_condicoes` — as duas colunas de `faixa_alcada` mais
  o backfill `minimo_cotacoes = 2` onde `exige_mapa_concorrencia` é true. **O backfill
  preserva o comportamento de hoje** (`>= 2`), não o desejado (3): subir para 3 é D6, por
  UPDATE, depois de o Cássio confirmar.
- [x] **Step 4:** `_migration_298_requisicao_alcada` — as quatro colunas de
  `requisicao_compra` e os dois índices do acumulado
  (`ix_requisicao_obra_etapa_criada`, `ix_pedido_admin_fornecedor_data`). Todos os defaults
  descrevem o registro histórico: requisição antiga é `'simples'`, não emergencial, sem
  degrau.
- [x] **Step 5:** `_migration_299_flag_e_janela` — a flag (default FALSE) e
  `janela_fracionamento_dias` (default 30). Registrar as três na lista de tuplas, com a
  descrição explicando o salto de 296 para 297 e por que 290-295 e 300-307 seguem
  reservadas.
- [x] **Step 6 (green):** rodar os cinco. Verdes.
- [x] **Step 7:** commit — `feat(compras): colunas de alcada avancada e migrations 297-299`

## A2 — A flag e o carimbo do regime

- [x] **Step 1 (red):** flag nasce OFF; `--ligar` **recusa** tenant sem
  `compras_governanca_ativa` e a mensagem termina com o comando exato que falta; `--ligar`
  **avisa e não recusa** quando falta `financeiro_dois_fluxos_ativo`; flag ilegível é
  tratada como OFF; requisição criada com a flag ON nasce `regime_alcada = 'avancado'` e
  **não muda** depois do `--desligar`.
- [x] **Step 2:** `scripts/flag_alcadas_avancadas.py`, molde de
  `scripts/flag_financeiro_dois_fluxos.py`: `alcadas_avancadas_ativa(admin_id)` com
  `except → False`, `definir_flag`, `pode_ligar(admin_id) → (bool, motivo)` importando
  `governanca_ativa` de `scripts/flag_compras_governanca.py`, `main()` com `--ligar` /
  `--desligar` / `--forcar`. Docstring com o bloco `Uso:` e a nota de que o regime é
  carimbado na linha.
- [x] **Step 3:** a distinção entre recusa e aviso mora em `pode_ligar` e é **comentada
  lá**: governança é dependência dura (sem ela o degrau não tem sobre o que agir); dois
  fluxos é dependência parcial (só a sanção da emergência depende dela). Quem ler o script
  daqui a um ano precisa achar o porquê sem abrir o spec.
- [x] **Step 4:** `regime_alcada_do_tenant(admin_id)` em `services/alcada_compras.py`, e a
  indireção `_regime_alcada(admin_id)` em `compras_views.py`, no molde de
  `_regime_recebimento` e `_fluxo_pagamento`. Aplicada em `requisicao_nova_post` — hoje o
  único ponto que cria requisição.
- [x] **Step 5 (green):** rodar. Verdes.
- [x] **Step 6:** commit — `feat(compras): flag de alcadas avancadas e o carimbo do regime`

## A3 — O corte de cotações vira dado, e a faixa de topo destrava

> Esta task fecha um 🔴 **aberto desde a Fase 3 do núcleo**, não só prepara a A4.

- [x] **Step 1 (red):** `_mapa_serve_de_concorrencia` passa a exigir
  `faixa.minimo_cotacoes` fornecedores, não 2 fixos: mapa com 2 fornecedores **passa** na
  faixa de `minimo_cotacoes = 2` e **falha** na de 3; `minimo_cotacoes = 0` dispensa o mapa;
  e o teste de tela — POST de requisição com `mapa_v2_id` **vindo do form renderizado**
  grava o vínculo.
- [x] **Step 2:** trocar o literal `len(mapa.fornecedores) >= 2` pela leitura da faixa. A
  assinatura de `_mapa_serve_de_concorrencia` ganha a faixa; `pendencias_de_aprovacao`
  passa a dizer **quantas** cotações faltam, não só que falta mapa.
- [x] **Step 3:** `exige_mapa_concorrencia` deixa de ser lida e vira derivada
  (`minimo_cotacoes > 0`). **A coluna não é removida** — há tenant com faixa editada por
  SQL, e coluna não se remove no mesmo release que muda o leitor. Comentário no modelo
  dizendo isso, para que a remoção seja uma decisão futura e não um esquecimento.
- [x] **Step 4:** o campo do mapa em `templates/compras/requisicao_nova.html`: select das
  `MapaConcorrenciaV2` da mesma obra com `status = 'concluido'`, opcional, com texto curto
  explicando quando é exigido. E em `requisicao_detalhe.html`, quando a pendência de mapa
  aparece, o link para criar o mapa da obra — a pendência precisa ter saída na própria tela.
- [x] **Step 5:** a rota `requisicao_detalhe` passa a carregar os mapas elegíveis; a
  validação do `mapa_v2_id` confere `obra_id` e `admin_id` **na rota**, não só no serviço.
- [x] **Step 6 (green):** rodar. Verdes. Conferir na tela que uma requisição acima de 30k
  agora tem caminho até APROVADA.
- [x] **Step 7:** commit — `feat(compras): minimo de cotacoes vira dado da faixa e o mapa ganha campo na tela`

## A4 — `faixa_efetiva` e as quatro condições ← gate de merge

> ✅ **D1 fechada em 15/08:** as quatro são `fornecedor_novo`, `sem_cotacao`,
> `nao_menor_preco`, `fora_do_orcamento`. A última é a ruidosa (etapa é nullable) — ela
> entra no código igual às outras; quem decide se roda em cada tenant é
> `faixa.condicoes_ativas`, e o sensor da A8 mede o volume antes de alguém ligar.

- [ ] **Step 1 (red):** paridade primeiro — com a flag OFF, `faixa_efetiva` devolve o mesmo
  objeto de `faixa_para_valor` numa grade de valores que cruza os três tetos (0, 4999, 5000,
  5001, 29999, 30000, 30001, 1e6). Depois: uma condição sobe uma faixa; duas sobem duas; na
  faixa de topo satura **e mesmo assim grava** `degrau_aplicado`; requisição em regime
  `'simples'` ignora as condições ainda que a flag esteja ON.
- [ ] **Step 2:** os quatro avaliadores em `services/alcada_compras.py`, um por função
  pequena e testável isoladamente: `_cond_fornecedor_novo`, `_cond_sem_cotacao`,
  `_cond_nao_menor_preco`, `_cond_fora_do_orcamento`. Cada um recebe a requisição (e o
  fornecedor, quando só existe na emissão) e devolve bool. Nenhum deles consulta flag —
  quem decide se valem é o chamador.
- [ ] **Step 3:** `condicoes_disparadas(requisicao, faixa, fornecedor=None)` — intersecta os
  avaliadores com `faixa.condicoes_ativas`. Condição que o tenant não ativou não roda: o
  custo de query também é comportamento.
- [ ] **Step 4:** `faixa_efetiva(requisicao, fornecedor=None)` — base, degrau, saturação no
  topo, e a gravação de `degrau_aplicado`. **Não commita**, no mesmo contrato de
  `registrar_aprovacao`: quem persiste é a rota.
- [ ] **Step 5:** trocar as chamadas de `faixa_para_valor` por `faixa_efetiva` nos quatro
  pontos que decidem (`services/alcada_compras.py` em `pendencias_de_aprovacao`,
  `compras_views.py` em `requisicao_nova_post`, `requisicao_detalhe` e a guarda 2 de
  `requisicao_emitir_pedido`). O ponto de **exibição** do flash na criação também passa a
  usar a efetiva — senão a tela promete uma faixa e o envio cobra outra.
- [ ] **Step 6:** `requisicao_detalhe.html` mostra **por que** subiu: a faixa base, a
  efetiva e os códigos em português. Pendência sem motivo visível é pendência que vira
  ligação para o suporte.
- [ ] **Step 7 (green):** rodar a suíte da fase inteira. Verdes.
- [ ] **Step 8:** commit — `feat(compras): as quatro condicoes que sobem um degrau na alcada`

## A5 — Anti-fracionamento

- [ ] **Step 1 (red):** três requisições de R$ 4.900 na mesma `(obra, etapa)` dentro da
  janela → a terceira cai na faixa de 30k e grava `fracionamento`; a mesma terceira **fora**
  da janela fica na faixa de 5k; requisição REJEITADA e CANCELADA **não** entram no
  acumulado; o acumulado por fornecedor aparece **só** na emissão, nunca no envio; janela
  configurada em 7 dias no tenant muda o resultado sem tocar em código.
- [ ] **Step 2:** `acumulado_da_etapa(requisicao, dias)` e
  `acumulado_do_fornecedor(admin_id, obra_id, fornecedor_id, dias)` em
  `services/alcada_compras.py`. Duas queries agregadas, cada uma pousando num dos índices
  da A1 — e um comentário nomeando qual índice cada uma usa, para que quem mexer no índice
  saiba o que quebra.
- [ ] **Step 3:** `valor_para_alcada(requisicao, fornecedor=None)` — `max(valor da linha,
  acumulado aplicável)`. É o único ponto que sabe escolher entre os dois acumulados, e o
  critério é de onde veio a chamada, não um parâmetro solto.
- [ ] **Step 4:** ligar em `requisicao_enviar` (acumulado de etapa) e em
  `requisicao_emitir_pedido` (acumulado de fornecedor). Na emissão, o degrau por
  fracionamento **não** invalida a aprovação já dada — ele recusa a emissão com mensagem
  que diz o que fazer (voltar para aprovação na faixa nova). Reaprovar é caminho; emitir
  calado, não.
- [ ] **Step 5:** a listagem de requisições ganha o marcador de quem subiu por acumulado, e
  o detalhe mostra as irmãs da janela com número e valor. Sem isso o aprovador vê uma
  exigência e não vê o fato que a gerou.
- [ ] **Step 6 (green):** rodar. Verdes. Conferir por SQL cru, num tenant de dev, que o
  acumulado bate com a soma manual da janela.
- [ ] **Step 7:** commit — `feat(compras): o acumulado da janela passa a definir a faixa`

## A6 — O rito de emergência 48h

- [ ] **Step 1 (red):** emergencial sem justificativa é recusada; emergencial vai de
  RASCUNHO a APROVADA sem voto e a trilha registra o motivo; ratificação dentro de 48h
  carimba `ratificada_em`; quem invocou **não** ratifica; passadas 48h sem ratificação, a
  `ContaPagar` derivada fica `bloqueada`; ratificar depois **libera**; e com
  `financeiro_dois_fluxos_ativo` OFF nada disso derruba nada (a conta nasce liberada e o
  teste **nomeia** que é assim de propósito).
- [ ] **Step 2:** o campo na tela de nova requisição — checkbox mais textarea de
  justificativa que só aparece marcado, com o texto do que a emergência dispensa e do que
  ela **não** dispensa. O usuário decide sabendo do prazo.
- [ ] **Step 3:** `aprovar_emergencial(requisicao, usuario)` em
  `services/alcada_compras.py`: valida papel (GESTOR da obra ou ADMIN, D4), transiciona via
  `transicionar()` — **o chokepoint continua único** — com motivo marcado, e não grava voto
  nenhum. Emergência não é aprovação; é a ausência dela, registrada.
- [ ] **Step 4:** `ratificacao_vencida(requisicao)` e a integração com a Fase 2: no ponto em
  que a `ContaPagar` derivada é avaliada, emergência vencida entra como motivo de
  `situacao_liberacao = 'bloqueada'`. Reusar o caminho existente da Fase 2 — **não** criar
  segunda porta em `pagar_conta`, que já tem uma só por decisão registrada.
- [ ] **Step 5:** a mensagem de bloqueio diz o número da requisição e quem pode ratificar.
  Conta bloqueada sem dizer o que falta foi exatamente o defeito nº 8 da revisão da Fase 3.
- [ ] **Step 6 (green):** rodar. Verdes.
- [ ] **Step 7:** commit — `feat(compras): rito de emergencia 48h e a conta que espera a ratificacao`

## A7 — A tela de faixas

> ✅ **D7 fechada em 15/08: entra.** E deixou de ser cortável — o passo 1 do runbook
> depende dela, e é por ela que sai o UPDATE da D6 (faixa de topo para
> `minimo_cotacoes = 3`, que o backfill deliberadamente não fez).

- [ ] **Step 1 (red):** só ADMIN alcança a tela; editar faixa de outro tenant dá 404;
  salvar mantém o invariante de **exatamente uma** faixa com `valor_ate` NULL; tetos têm que
  ser crescentes por `ordem`; `minimo_cotacoes` aceita 0 ou ≥ 2, nunca 1.
- [ ] **Step 2:** rota em `configuracoes_views.py` e template, listando as faixas do tenant
  com os campos editáveis, incluindo os checkboxes das quatro condições.
- [ ] **Step 3:** as validações **no serviço**, não no template — a tela é a primeira
  consumidora, o script de flag é a segunda, e um SQL manual continua sendo possível. O
  invariante da faixa de teto aberto nunca teve constraint (📖 só docstring em
  `models.py:6239`); esta é a primeira vez que alguém o verifica em código.
- [ ] **Step 4 (green):** rodar. Verdes.
- [ ] **Step 5:** commit — `feat(compras): tela de faixas de alcada por tenant`

## A8 — Sensor, teste-guarda e runbook

- [ ] **Step 1 (red):** o teste-guarda que varre o repositório atrás de pontos que criam
  `RequisicaoCompra` e confere que todos carimbam `regime_alcada`, carregando por escrito a
  lista de pontos conhecidos (padrão da C9). Hoje é um; o teste existe para o dia em que for
  dois.
- [ ] **Step 2:** `scripts/verificar_consistencia_alcadas.py`, molde de
  `verificar_consistencia_financeiro.py`. Aponta: requisição APROVADA com menos aprovações
  que a faixa efetiva exige; emergencial vencida sem ratificação; emergencial vencida com
  conta **não** bloqueada (a que prova que a A6 está ligada de verdade); faixa com
  `minimo_cotacoes = 1`; tenant com zero ou duas faixas de teto aberto; `degrau_aplicado`
  citando condição que a faixa não ativa. Exit ≠ 0 com achado.
- [ ] **Step 2b:** o mesmo script ganha `--simular`, que roda **sem a flag ligada** e
  responde uma pergunta só: das requisições dos últimos 30 dias deste tenant, quantas
  subiriam de faixa, e por qual condição. É o que o runbook manda rodar antes do passo 1 —
  e é a resposta operacional ao ⚠️ da D1, porque `fora_do_orcamento` dispara em toda
  requisição sem etapa apontada. Número na mão, ligar a condição ou adiá-la deixa de ser
  palpite.
- [ ] **Step 3:** o runbook no fim do spec conferido contra o que o código realmente faz —
  a ordem dos cinco elos, as cinco conferências do passo 3 e o que o `--desligar` faz **e
  não faz**.
- [ ] **Step 4 (green):** rodar. Verdes, sensor exit 0.
- [ ] **Step 5:** commit — `feat(compras): sensor de consistencia das alcadas e o teste-guarda do carimbo`

---

## Gate final

- [ ] Suíte da fase verde: `pytest tests/test_alcadas_avancadas.py -q`
- [ ] **Regressão dirigida** verde — é aqui que esta fase é mais arriscada que as duas
  anteriores, porque mexe em código que já tem 40+ testes escritos:
  `pytest tests/test_fase3_alcada.py tests/test_fase3_matriz_governanca.py
  tests/test_fase3_requisicao.py tests/test_recebimento_atesto.py
  tests/test_financeiro_dois_fluxos.py -q`
- [ ] Gate completo: `pytest tests/ -m "not browser"` — exit 0
- [ ] Ciclo em dev com a flag **desligada**: comportamento idêntico ao de hoje, conferido
  por SQL cru (faixa escolhida, votos exigidos, pendências)
- [ ] Ciclo em dev com a flag **ligada**: as cinco conferências do runbook (a–e)
- [ ] Ligar e desligar **não reescreve o passado**: requisição `'avancado'` continua
  avançada
- [ ] `scripts/verificar_consistencia_alcadas.py` exit 0
- [ ] Runbook no fim do spec: como ligar num tenant, o que conferir depois, e o que o
  `--desligar` faz e não faz
- [ ] As divergências entre spec e código registradas **no próprio spec**, como blockquote
  📌 no ponto exato, e resumidas em `ESTADO-ATUAL.md`

---

## Riscos

| Risco | Mitigação |
|---|---|
| **O requisito é desenho nosso.** Nenhum dos quatro elementos tem texto de origem — 🔬 15/08 as sete decisões foram ratificadas na sessão, o que fecha a dúvida sobre *o que fazer* e não sobre *se descreve a operação* | Tudo o que é número virou linha de tabela, editável sem deploy; as condições são lista, não colunas, e podem ser ligadas uma a uma; o sensor da A8 mede o impacto **antes** de a flag ser ligada em tenant real |
| **`escopo_obra_ativo` OFF esvazia a fase inteira** — todo autenticado vira GESTOR e resolve sozinho as pendências que o degrau criou | `--ligar` recusa tenant sem `compras_governanca_ativa`, que por sua vez já recusa sem escopo. A cadeia de cinco elos é a defesa, e o passo 0 do runbook a torna visível |
| **Regressão nos 40+ testes de alçada existentes** — esta fase reescreve o chamador de `faixa_para_valor` em quatro pontos | `faixa_para_valor` fica **intocada**; a regra nova é função acima dela. Regressão dirigida no gate, antes do gate completo |
| **A faixa de topo destravada expõe o mapa a mais gente** — `MapaConcorrenciaV2` nunca teve tráfego real vindo da requisição | A3 valida `obra_id` e `admin_id` do mapa **na rota**, não só no serviço; o select só oferece mapa da própria obra concluído |
| **O acumulado é query por envio de requisição** — pode ficar caro em tenant com muita requisição | Os dois índices são parte da A1, não otimização posterior; condição não ativada não roda query |
| **A sanção da emergência depende da Fase 2 ligada** — em tenant sem dois fluxos o rito não morde | Registrado no spec, avisado (sem recusar) pelo `--ligar`, e coberto por teste que **nomeia** o comportamento como intencional |
| 🔴 **A intermitente aberta de 14/08** (`test_rota_de_exclusao_repassa_a_recusa_do_servico`) pode contaminar a leitura do gate completo | Rodar a regressão dirigida **antes** do gate cheio; se a intermitente aparecer, ler o número de recebimentos que o assert passou a carregar e registrar qual das duas hipóteses ela indica — esta fase é a próxima chance de fechá-la |
