# Ciência do RDO no portal do cliente — design de percurso

Data: 2026-07-29. Aprovado em conversa com o usuário (abordagem B —
"a página da assinatura").

## Resumo

O ato de dar ciência num RDO sai de dentro da página de leitura e passa a
ter **rota própria**, com começo, meio e comprovante. A sessão de login do
signatário é **removida**: a senha deixa de ser pedágio para navegar e volta
a ser o gesto de assinar, conferida no mesmo POST que grava a assinatura. Do
lado da construtora, link do portal e senha temporária param de nascer em
telas diferentes e passam a sair juntos, como mensagem pronta para o canal
que já é usado (WhatsApp).

Fora de escopo: notificação automática por qualquer canal (n8n/webhook),
assinatura em lote, fila pessoal do responsável ("o que depende de mim"),
expiração do token da obra, provedor externo de assinatura (ICP-Brasil,
Clicksign) e qualquer mudança de schema — não há migração neste design.

## Por que agora

A Fase 9a entregou a ciência funcionando, mas desenhada como um ato
excepcional: login, sessão de 15 minutos e um cartão único que acumula quatro
estados. O uso real é **diário e de um RDO por vez**, disparado por cobrança
da construtora no WhatsApp. Um ato que se repete todo dia não pode custar o
percurso de um ato raro.

O levantamento do percurso atual foi feito em 29/07: nove estações entre
cadastrar o responsável e a primeira assinatura, duas metades do convite
nascendo em telas diferentes, e o ato terminando sem devolver nada a quem
assinou. O mapa visual e os mockups das telas estão em artefatos publicados
na mesma data (ver seção 3).

> **Correção de 29/07, registrada de propósito.** A primeira versão deste
> levantamento afirmava que o bloco de ciência ficava no rodapé do RDO e que
> a pessoa precisava rolar a página inteira para achá-lo. **É falso.** O
> `{% include %}` é a primeira linha do `{% block content %}`
> (`templates/portal/portal_rdo_detalhe.html:133`), com um comentário do
> próprio commit da Fase 9a explicando a escolha. O erro veio de ler o
> parcial isolado e deduzir a posição pelo tamanho da página, em vez de
> conferir onde ele é incluído. Quem retomar este design não deve
> reintroduzir "mover para o topo" como ganho: esse ganho não existe.

## Contexto atual (verificado no código)

- **O portal é anônimo por construção** (`portal_obras_views.py:3`). A
  identidade é o token na URL. Este design **não muda isso**: continua sendo
  possível navegar o portal inteiro sem se identificar.
- **O bloco de ciência já é a primeira coisa da página do RDO**
  (`templates/portal/portal_rdo_detalhe.html:133`, dentro de
  `{% block content %}`). Ele acumula quatro estados decididos por uma cadeia
  de `if` no template: placar nominal, formulário de login, formulário de
  troca de senha e formulário de assinar — 369 linhas em
  `_portal_ciencia_rdo.html`, incluindo dois `<script>` inline.
- **A sessão do signatário** (`services/portal_signatario_auth.py`) vive numa
  chave própria (`portal_sig`), 15 minutos de inatividade, teto de 12 horas,
  com impressão da credencial no cookie para permitir revogação por troca de
  senha. Foi ela que produziu o achado 5 da revisão de 29/07 (gerar senha
  nova não derrubava o intruso).
- **`RDOAssinatura` já guarda tudo o que um recibo precisa**:
  `nome_signatario`, `cargo_signatario`, `assinado_em`, `hash_conteudo`,
  `algoritmo`, `ip`, `user_agent`, `observacao`, `signatario_cliente_id`.
  Snapshot de nome e cargo desde a Fase 5. **Nenhuma coluna nova.**
- **A unicidade é do banco**, não da aplicação: índice parcial
  `uq_rdo_assin_cliente` (migração 268). `ja_assinou` é conveniência de
  mensagem.
- **`gerar_pdf_rdo` já renderiza um quadro de ciência do cliente**
  (`_ciencia_cliente_block`), com o denominador e quem falta, e marca as
  assinaturas cujo hash não bate mais. Esse PDF **nunca foi exposto ao
  portal** — só existe em `views/rdo.py:1670`.
- **Não há SMTP.** O único canal automático é o n8n, opt-in por
  `N8N_WEBHOOK_URL`. O alfabeto da senha temporária exclui `0 O 1 l I`
  justamente porque ditar por telefone é o canal previsto.
- **O rate-limit** de `/entrar` é `5 per 15 minutes` com chave
  IP + `signatario_id` normalizado por `int()` — a normalização foi o achado
  4 da revisão de 29/07.

## As quatro decisões que sustentam o design

Registradas com o motivo, porque são elas que qualquer revisão futura vai
querer reabrir.

### D1 — Senha a cada assinatura; nenhuma sessão de login

A senha é o que torna a assinatura *daquela pessoa*. Com sessão, o ato
repousa sobre um cookie de 15 minutos; sem sessão, repousa sobre a
credencial. Num ritmo de 1 RDO por dia o custo digitado é **o mesmo** — uma
senha por dia nos dois modelos —, mas o atrito passa a estar no lugar certo
e some a janela entre autenticar e assinar.

Consequência: `abrir_sessao`, `fechar_sessao`, `sessao_atual`,
`exigir_sessao`, `_impressao_credencial`, `CHAVE_SESSAO`, `MINUTOS_SESSAO` e
`HORAS_SESSAO_MAXIMA` saem de `services/portal_signatario_auth.py`. Sai
junto toda a máquina de revogação — que existia só para consertar um problema
que a sessão criava.

O que **fica**: `autenticar` (com a ordem de conferência preservada — senha
primeiro, motivo real depois, achado 6 da revisão), `gerar_senha_temporaria`,
`definir_senha`, `pedir_recuperacao`, `signatarios_da_obra`, a trava de 10
falhas no modelo e o rate-limit.

### D2 — Na leitura fica o estado; o ato vai para a outra tela

O bloco de ciência **já abre a página** — isso não muda e não é ganho deste
design. O que muda é o que ele contém.

Hoje aquele cartão é uma máquina de quatro estados empilhados: o placar
nominal, o formulário de login, o formulário de troca de senha e o formulário
de assinar, decididos por uma cadeia de `if` no template. Numa página de
leitura, a primeira coisa que o cliente vê é um campo de senha.

Depois: uma faixa de estado (*falta a sua ciência* / *você já deu ciência* /
*ainda sendo finalizado pela construtora*) e um botão. O placar nominal
desce para o fim do relatório, onde ele é registro e não chamada. Os três
formulários somem daqui — cada um vira uma tela com um trabalho só.

A leitura mínima que de fato importa antes de assinar passa a estar na tela
do ato, no bloco "você está confirmando" — data, quantas atividades, quantas
fotos, quantas ocorrências e a impressão digital.

### D3 — O comprovante não é público

Ele exibe o IP de quem assinou. O placar nominal já expõe nome e horário
para qualquer um com o link da obra; o IP não. A tela de comprovante fica
disponível apenas para o navegador que acabou de assinar, por uma marca no
cookie do Flask — mesmo lugar que `_guardar_senha_gerada`
(`views/obras.py:3878`), com uma diferença deliberada de vida útil:

- a marca guarda `{assinatura_id, exp}` e vale **15 minutos**;
- ela **não é consumida na leitura**, senão o botão de baixar o recibo
  quebraria justamente na tela que o oferece;
- expira por tempo, e a assinatura seguinte simplesmente a substitui.

A marca **não é identidade e não autoriza nada** além de reabrir aquele
comprovante e baixar aquele recibo. Toda rota que a lê continua resolvendo a
obra pelo token e conferindo que a assinatura pertence ao RDO daquela obra —
a marca sozinha nunca é autoridade sobre o que mostrar.

O registro durável continua no relatório e no PDF do RDO.

### D4 — O convite é um artefato só

Link e senha param de nascer em telas separadas. O bloco "Acesso do cliente"
na tela de detalhes da obra passa a produzir a mensagem inteira, pronta para
colar. Isso é correção: as duas metades já existiam, só estavam partidas.

O botão **"Cobrar ciência"** — que monta a mensagem do dia com link direto
para o RDO pendente — é funcionalidade nova, e é ela que apaga duas estações
do percurso do cliente (a capa do portal e a rolagem até a lista). Aprovada
com essa consciência.

## 1. Rotas

| rota | o que faz |
|---|---|
| `GET /portal/obra/<token>/rdo/<id>` | leitura; ganha faixa de estado no topo |
| `GET /portal/obra/<token>/rdo/<id>/ciencia` | **nova** — a tela do ato |
| `POST /portal/obra/<token>/rdo/<id>/ciencia` | **nova** — autentica e registra |
| `POST /portal/obra/<token>/rdo/<id>/ciencia/senha` | troca de senha — **movida** de `.../rdo/<id>/senha` |
| `POST /portal/obra/<token>/rdo/<id>/ciencia/esqueci` | pedido de senha nova — **movida** de `.../rdo/<id>/esqueci` |
| `GET /portal/obra/<token>/rdo/<id>/ciencia/comprovante` | **nova** — o que ficou registrado |
| `GET /portal/obra/<token>/rdo/<id>/ciencia/recibo.pdf` | **nova** — o recibo |
| ~~`POST .../rdo/<id>/entrar`~~ | **removida** com a sessão |
| ~~`POST .../rdo/<id>/sair`~~ | **removida** com a sessão |

As rotas de senha e de "esqueci" deixam de exigir sessão: passam a carregar
`signatario_id` e a senha atual no próprio corpo. Continuam presas à obra
resolvida pelo token.

## 2. O POST atômico

Ordem de operações. É aqui que mora o risco, e cada passo tem dono:

1. resolve a obra pelo token — a sessão nunca foi autoridade sobre qual obra
   está em jogo, e agora nem existe;
2. resolve o RDO **dentro** daquela obra;
3. rate-limit, com a chave de hoje (IP + `signatario_id` normalizado por
   `int()`), migrada intacta de `/entrar` para cá — este passou a ser o
   ponto de autenticação;
4. `autenticar()`: senha conferida **antes** de qualquer explicação sobre
   trava ou vencimento;
5. se `senha_temporaria` → **não é erro**: desvia para a tela de definir
   senha;
6. `registrar_ciencia()`;
7. trilha, commit, marca do comprovante, redirect.

Os dois eventos de trilha continuam existindo — `ciencia_login` no sucesso
da autenticação e `ciencia_rdo` na assinatura. Parece redundante num POST
único, mas não é: existe o caso "senha certa, ciência recusada" (o RDO virou
retificado entre a tela e o envio), e esse rastro não pode desaparecer.

Todo `_registrar_acesso` grava o IP de `request.remote_addr` — ver
`RELATORIO-REVISAO-2026-07-29.md`, achados 10 e 11.

## 3. As cinco telas

1. **Leitura** (`/rdo/<id>`): o bloco que já abre a página encolhe para uma
   faixa de estado — *falta a sua ciência* / *você já deu ciência* / *ainda
   sendo finalizado pela construtora* — mais o botão. Os três formulários
   saem. Conteúdo do relatório intocado abaixo. O placar nominal desce para
   o fim.
2. **O ato** (`/ciencia`): resumo do que se está assinando, "quem é você",
   senha, observação opcional, o termo em português claro, botão. Links para
   reler o relatório e para "esqueci minha senha".
3. **Primeiro acesso** (`/ciencia`, outro estado): explica por que a senha da
   construtora não serve para assinar, pede a nova, e devolve ao ato com o
   nome já escolhido.
4. **Comprovante** (`/ciencia/comprovante`): responsável, cargo, data e hora,
   endereço, impressão digital, observação. Botão de baixar o recibo.
5. **Convite** (detalhes da obra, lado da construtora): link, responsáveis,
   *copiar convite*, *cobrar ciência*, e a mensagem montada à vista.

Artefatos visuais publicados em 29/07, ambos privados na conta do usuário:

- mapa do percurso atual com os atritos —
  <https://claude.ai/code/artifact/fd00887c-941f-4ea5-a973-f673348fc77f>
- as cinco telas propostas —
  <https://claude.ai/code/artifact/9748e567-6121-4284-b4b0-9f3a465c1d03>

## 4. O recibo

Módulo **novo**: `services/rdo_recibo_ciencia.py`, com
`gerar_recibo_ciencia(assinatura) -> bytes`. Importa `_logo_image`,
`_build_styles` e `_Footer` de `services/rdo_pdf_service.py`.

Vai em arquivo próprio porque `rdo_pdf_service` já tem 1076 linhas e produz
o documento inteiro; o recibo é outro documento, com outro propósito e outro
leitor. Gerado na hora, sem persistir arquivo.

Conteúdo: identificação da construtora e da obra, número e data do RDO, o
que foi confirmado, os dados do registro (com o hash **completo**, não
abreviado como na tela) e o termo.

## 5. Erros

| situação | o que a pessoa vê |
|---|---|
| senha errada | "Nome ou senha inválidos" — genérico; `falhas_login` +1 **persistido**; trilha `ciencia_login_falha` |
| 6ª tentativa em 15 min (mesmo IP + signatário) | "Muitas tentativas. Aguarde alguns minutos." |
| conta travada (10 falhas) ou senha temporária vencida | o motivo real, **só depois de acertar a senha** |
| senha temporária válida | não é erro — desvia para definir senha |
| RDO virou retificado entre a tela e o envio | volta à leitura com o motivo de `motivo_inelegivel` |
| duplo-toque no celular / duas abas | índice parcial barra o segundo; rollback e vai ao **comprovante da assinatura que existe** |
| signatário desativado no meio | "Este acesso foi desativado pela construtora." |
| comprovante sem a marca no cookie | volta ao relatório explicando que ele fica disponível logo após assinar; não vaza nome, IP nem hash |
| token da obra inválido ou portal desligado | 404 / página de portal inativo, como hoje |

O ramo de `IntegrityError` que a revisão de 29/07 acrescentou (achado 7)
continua, agora com destino melhor que um flash.

## 6. Testes

A suíte de ciência tem 50 testes e o acoplamento à sessão está concentrado:
um helper `_login` (`tests/test_rdo_ciencia_cliente.py:140`) e ~35 chamadas
de `POST /assinar` com corpo vazio. Vira um helper `_assinar(c, ctx,
senha=…)`. É reescrita mecânica, não redesenho da suíte.

Testes novos:

- assina com senha certa num POST único; senha errada não grava e incrementa
  `falhas_login`;
- senha temporária não assina e desvia para definir senha; definir e assinar
  em seguida funciona;
- RDO retificado entre o GET e o POST é recusado com o motivo certo;
- duplo-toque grava **uma** assinatura e a segunda requisição chega ao
  comprovante;
- comprovante sem a marca no cookie não revela nome, IP nem hash;
- a marca de uma assinatura **não** abre o comprovante de outro RDO nem de
  outra obra — o token continua mandando;
- o recibo em PDF sai com bytes válidos e carrega nome e hash completo;
- **guarda contra ressurreição:** `/entrar` e `/sair` respondem 404, e depois
  de assinar o cookie não carrega identidade nenhuma.

O último transforma "removemos a sessão" numa propriedade verificada em vez
de uma promessa.

## 7. Riscos conhecidos

- **A remoção da sessão é irreversível na prática.** Se o ritmo real virar
  "vários RDOs numa sentada", digitar a senha N vezes seguidas vai incomodar.
  O caminho de volta não é ressuscitar a sessão de login: é assinar em lote —
  um POST, uma senha, N RDOs. Fica registrado aqui para não se reabrir a
  discussão errada.
- **O link direto no WhatsApp carrega o token da obra**, que já vaza para
  logs hoje (`utils/auditoria_acesso.py:68-79` loga `request.path` inteiro e
  o access log do gunicorn repete). Este design não piora nem melhora isso —
  mas aumenta a circulação do link, o que reforça a pendência de expiração e
  redação de token que já está em `ESTADO-ATUAL.md`.
- **Nenhuma migração** significa que o rollback é reverter código. Bom.
