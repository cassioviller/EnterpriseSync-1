# Plano de Implementação — ciência do RDO com rota própria

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — entregue; 🔬 todos os arquivos prometidos existem. 🔬 3/3 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


Spec: `docs/superpowers/specs/2026-07-29-ciencia-rdo-portal-ux-design.md`
(aprovado 2026-07-29, abordagem B). **Sem migração** — nenhuma coluna nova,
nenhum índice novo. Rollback é reverter código.

## Contexto verificado no código

- **`portal_obras` NÃO está na lista de isenção de CSRF** (`app.py:1051-1062`
  — lá estão `main`, `propostas` e outros 28). Todas as rotas novas nascem
  protegidas, e os formulários precisam do `csrf_token()` como os de hoje.
- **O `limiter` já é importado** em `portal_obras_views.py:25` e a chave
  `_chave_limite_assinatura` (l.1011) já normaliza o `signatario_id` com
  `int()`. Ela migra **sem alteração** de `/entrar` para `POST /ciencia`.
- **O bloco de ciência abre a página do RDO**
  (`portal_rdo_detalhe.html:133`), não o rodapé. `_portal_ciencia_rdo.html`
  tem 369 linhas e dois `<script>` inline (`cienciaMostrarTrocaSenha`,
  `cienciaEsqueci`) — ambos morrem com os formulários que serviam.
- **`registrar_ciencia` já valida tudo o que importa** (obra do signatário,
  ativo, senha temporária, `motivo_inelegivel`, `ja_assinou`) e **não faz
  commit**. Não precisa mudar — só passa a ser chamada logo depois de
  `autenticar` em vez de depois de `exigir_sessao`.
- **`RDOAssinatura` guarda tudo o que o recibo mostra** e tem
  `assinado_em`; o índice parcial `uq_rdo_assin_cliente` é quem garante a
  unicidade.
- **`gerar_pdf_rdo` já tem os blocos reaproveitáveis**: `_logo_image`
  (l.72), `_build_styles` (l.210), `_Footer` (l.336). São privados por
  convenção (underscore), mas estão no mesmo pacote `services/`.
- **A tela de detalhes da obra não carrega signatários.** `detalhes_obra`
  (`views/obras.py:1487`, render em l.2204) passa 30+ variáveis e nenhuma é
  `ObraSignatarioCliente`. O bloco do convite precisa dessa consulta nova.
  Quem carrega hoje é `editar_obra` (l.1120).
- **Testes:** `tests/test_rdo_ciencia_cliente.py` tem 50 testes; o
  acoplamento à sessão está no helper `_login` (l.140) e em ~35 chamadas de
  `POST /assinar` com corpo vazio. `tests/test_fase3_portal_seguranca.py`
  não toca a sessão do signatário.

## Decisão de implementação 1: a marca do comprovante vive em `portal_obras_views`

Não em `portal_signatario_auth`. Aquele módulo passa a ser só credencial —
sem estado de navegação nenhum, que é o ponto de D1. A marca é detalhe de
apresentação da view e mora ao lado de `_registrar_acesso`, com o mesmo
formato de `_guardar_senha_gerada`/`_consumir_senha_gerada`.

## Decisão de implementação 2: o parcial vira três

`_portal_ciencia_rdo.html` (369 linhas, quatro estados) se desfaz em:

- `portal/_ciencia_faixa.html` — a faixa de estado + botão, incluída na
  leitura;
- `portal/_ciencia_placar.html` — o placar nominal, que desce para o fim do
  relatório;
- `portal/ciencia_ato.html`, `portal/ciencia_senha.html`,
  `portal/ciencia_comprovante.html` — as telas, cada uma estendendo
  `portal/_base.html`.

Os dois `<script>` inline somem: não sobra nenhum estado a mostrar/esconder.

## Step A — o POST atômico (sem tocar em template)

Fazer o back primeiro deixa a suíte verde antes de mexer em UI.

1. `portal_obras_views.py`: nova rota `GET/POST
   /obra/<token>/rdo/<int:rdo_id>/ciencia` → `ciencia_ato`.
   - `@limiter.limit('5 per 15 minutes', key_func=_chave_limite_assinatura)`
     **só no POST** (checar `request.method` ou separar em duas funções — o
     decorator do flask-limiter aplica à rota inteira; separar é mais claro).
   - ordem: token → RDO → `autenticar` → desvio de senha temporária →
     `registrar_ciencia` → trilha → commit → marca → redirect.
2. Mover `ciencia_trocar_senha` para `.../ciencia/senha` e `ciencia_esqueci`
   para `.../ciencia/esqueci`; ambos passam a ler `signatario_id` do corpo e
   a senha atual, sem `exigir_sessao`.
3. `_marcar_comprovante(assinatura)` / `_consumir_marca_comprovante(rdo)` —
   `{assinatura_id, exp}` na sessão do Flask, 15 min, **não consumida na
   leitura**.
4. Rotas `ciencia_comprovante` e `ciencia_recibo_pdf`: leem a marca, mas
   **conferem a assinatura contra o RDO da obra do token** antes de mostrar
   qualquer coisa.
5. Apagar `ciencia_entrar` e `ciencia_sair`.

## Step B — `portal_signatario_auth` perde a sessão

Remover `abrir_sessao`, `fechar_sessao`, `sessao_atual`, `exigir_sessao`,
`_impressao_credencial`, `SessaoInvalida`, `CHAVE_SESSAO`, `MINUTOS_SESSAO`,
`HORAS_SESSAO_MAXIMA`. Reescrever o docstring do módulo — ele hoje explica
por que a sessão é própria e não Flask-Login; passa a explicar por que **não
há sessão**.

Fica intacto: `autenticar` (com a ordem senha-primeiro), `gerar_senha_
temporaria`, `definir_senha`, `pedir_recuperacao`, `signatarios_da_obra`,
`SENHA_MIN`.

## Step C — testes do back

1. Trocar `_login` por `_assinar(c, ctx, senha=…)` e varrer as ~35 chamadas.
2. Acrescentar os testes novos do spec §6 — incluindo a guarda contra
   ressurreição (`/entrar` e `/sair` = 404; cookie sem identidade depois de
   assinar) e a marca que não abre comprovante de outro RDO nem de outra obra.
3. **Cada teste novo roda contra o código anterior antes de valer** — regra
   da casa (`RELATORIO-REVISAO-2026-07-29.md`).

## Step D — as telas do cliente

1. Quebrar `_portal_ciencia_rdo.html` conforme a decisão 2.
2. `portal_rdo_detalhe.html`: trocar o include do topo pela faixa; incluir o
   placar no fim.
3. Escrever `ciencia_ato.html`, `ciencia_senha.html`,
   `ciencia_comprovante.html` sobre `portal/_base.html`, reaproveitando os
   tokens de `_portal_styles.html`.
4. O bloco "você está confirmando" precisa das contagens — atividades, fotos,
   ocorrências. A view do ato já resolve o RDO; contar é uma query por
   coleção, ou reaproveitar o que `portal_rdo_detalhe` já monta.

## Step E — o recibo

`services/rdo_recibo_ciencia.py` com `gerar_recibo_ciencia(assinatura) ->
bytes`. Importa `_logo_image`, `_build_styles`, `_Footer` de
`rdo_pdf_service`. Hash **completo**, não abreviado. Teste: bytes válidos,
começa com `%PDF`, e o texto extraído contém nome e hash.

## Step F — o convite (lado da construtora)

1. `views/obras.py:detalhes_obra` passa a carregar
   `ObraSignatarioCliente` da obra (mesma query de `editar_obra:1120`).
2. Bloco "Acesso do cliente" em `detalhes_obra_profissional.html`: link,
   lista de responsáveis com situação, **copiar convite** e **cobrar
   ciência**.
3. `copiar convite` gera a senha temporária e monta a mensagem no mesmo ato —
   reusa `main.gerar_senha_signatario_cliente`, que já existe e já guarda a
   senha na sessão em vez da querystring (achado 9 da revisão).
4. `cobrar ciência` monta a mensagem com link direto ao RDO pendente. Precisa
   saber **qual** RDO — usar o mais recente elegível sem a ciência daquele
   responsável (`placar_por_rdo` já faz isso em duas queries).
5. A senha temporária **continua aparecendo uma vez só**. A mensagem montada
   a inclui apenas quando acabou de ser gerada.

## Ordem e verificação

A → B → C fecham o back com a suíte verde. D → E → F são independentes entre
si depois disso; se der para partir o PR, o corte natural é depois de C.

Regressão obrigatória antes de fechar, no formato que o repositório usa:

```
pytest tests/ -k "(rdo or portal or obra or cronograma) and not playwright"
```

Baseline de hoje: **1137 passed, zero falhas**. Playwright continua sem
cobertura executável neste ambiente (`libnspr4.so` ausente) — os 5 fracassos
e 48 erros da rodada completa são todos dele.

## O que este plano NÃO faz

- Não mexe no token da obra (expiração, redação em log) — pendência anterior,
  agravada pela circulação maior do link, registrada no spec §7.
- Não cria notificação automática. O gatilho continua sendo a pessoa.
- Não expõe o PDF completo do RDO ao portal. É barato (o quadro de ciência já
  está lá) e ficou de fora de propósito: o usuário escolheu o recibo do ato,
  não o documento inteiro. Vale reabrir depois.
