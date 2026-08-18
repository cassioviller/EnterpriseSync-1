# Plano — Manual visual da requisição de compras — 2026-08-18

**O que é.** O plano para produzir um manual do fluxo de compras **do início ao fim**, com
print de cada tela, os campos marcados por caixas numeradas e o passo a passo do que
preencher. Público: quem vai *usar* o sistema na obra e no escritório — não é documento
técnico.

**Por que agora.** O ciclo de compras tem cinco fases entregues e 🔴 **nenhuma delas foi
rodada pela tela por um humano** (`ESTADO-ATUAL.md`, item 1 de quem retomar). Produzir este
manual **é** rodar o runbook: não dá para fotografar uma tela que não abre. 🔬 18/08, em
meia hora de varredura das 18 telas do fluxo, já apareceu um 500 em
`/financeiro/fechamento-pagamentos` que estava lá desde 22/07. O manual é o pretexto; a
conferência é o produto.

## O que já existe, e não deve ser reinventado

| Peça | Onde | Estado |
|---|---|---|
| Captura por Playwright | 📖 `scripts/capturar_manual_ciclo.py` (85 linhas) | Funciona, mas **não roda hoje** — ver a armadilha nº 1 |
| Montagem do PDF | 📖 `scripts/gerar_manual_pdf.py` (351 linhas, reportlab) | Capa + passos com imagem, descrição e URL. Reaproveitável quase inteiro |
| 15 screenshots do ciclo | 📖 `docs/manual_ciclo/screenshots/` | Do commit de 22/07. **Anteriores à governança de compras** — nenhum mostra requisição |
| Manual em PDF para o cliente | 📖 `services/manual_ciencia_pdf.py` (13/08) | O precedente de tom e de formato. Duas páginas, sem marca, números tirados do código |
| Manual por módulo, em texto | 📖 `manual/*.md` (18 arquivos) | 🔬 `manual/imagens/` está **vazio** — o manual textual nunca teve print |

**Nada disso anota campo.** A caixa numerada sobre o campo é a parte que não existe, e é o
coração deste plano.

## As duas armadilhas do que já existe

1. 🔴 **A captura de 22/07 não é reproduzível, e falha em silêncio.** 📖
   `capturar_manual_ciclo.py:9-16` fixa `ORCAMENTO_ID = 132`, `PROPOSTA_ID = 1222`,
   `OBRA_ID = 1276` e um token de portal — IDs de um tenant de teste de julho, que não
   existem mais. Pior: 📖 `:76-79` engole a exceção (`except Exception: print("ERRO em
   ...")`) e segue. Como o gerador do PDF lê a pasta **por nome de arquivo**, uma captura
   que falha deixa o PNG **velho** no disco e o PDF sai montado com a tela errada, sem um
   único aviso. **Regra deste plano: captura que falha derruba o processo inteiro, com
   código de saída ≠ 0.**
2. ⚠️ **Print anotado por coordenada de pixel envelhece na primeira mudança de CSS.**
   Marcar "caixa em x=340,y=210" é escrever um número sem procedência — o defeito de
   fabricação que abre o `ESTADO-ATUAL.md`, na forma de imagem. A âncora tem de ser o
   **seletor do campo**, não o pixel.

## A decisão técnica que sustenta o resto

**As caixas são desenhadas no DOM, pelo Playwright, antes do `screenshot()` — não por cima
do PNG depois.**

Para cada campo a marcar, o roteiro declara um seletor (`[name="obra_id"]`). O motor pega o
elemento, injeta um `<div>` absoluto com contorno e um badge numerado no canto, e só então
fotografa. Três consequências, e as três importam:

- **Sobrevive a mudança de layout.** O contorno acompanha o campo porque é medido do campo.
- **Resolução livre.** A anotação é CSS; sai nítida em qualquer viewport ou DPI.
- **O número da imagem e o número do texto são o mesmo dado.** O roteiro é uma lista em
  Python: cada entrada tem `(seletor, número, rótulo, obrigatório?)`. Dela saem **as duas
  coisas** — a caixa desenhada e a legenda numerada embaixo da figura. **Não há como a
  legenda dizer "3 — Obra" enquanto a caixa 3 está na justificativa**, porque não existem
  duas listas para divergir.

E o guarda que fecha a armadilha nº 1: **seletor que não casa é erro, não aviso.** Se
`[name="obra_id"]` sumir do formulário, a captura para e diz qual passo quebrou. Um manual
que aponta a seta para o campo errado é pior que manual nenhum.

## O fluxo, tela a tela — o inventário conferido

📖 Levantado em 18/08 do `url_map` e dos templates, não de memória. Estados conforme
📖 `services/requisicao_compra.py:74` (`TRANSICOES_VALIDAS`).

### Ato 1 — O solicitante pede (estado RASCUNHO)

| # | Tela | Rota | Campos a marcar |
|---|---|---|---|
| 1 | Login | `/login` | usuário, senha |
| 2 | Lista de requisições | `/compras/requisicoes` | filtros por estado, botão "Nova" |
| 3 | **Nova requisição** | `/compras/requisicoes/nova` | **obra\*** (`obra_id`), data de necessidade, justificativa, **emergencial** (checkbox), mapa de cotação, e a linha de item: descrição, unidade, quantidade, preço, almoxarifado |
| 4 | Detalhe em rascunho | `/compras/requisicoes/<id>` | bloco "Gravar itens", vincular mapa |
| 5 | Enviar para aprovação | botão no detalhe | — |

📖 O campo **justificativa é condicional**: `requisicao_nova.html:209-221` torna
`required` quando "emergencial" é marcado. Um manual que diz "opcional" mente para metade
dos casos — a caixa desse campo precisa de nota, não só de número.

⚠️ 📖 `/compras/nova` (pedido direto) **redireciona** para a requisição quando a governança
está ligada, com o aviso *"A governança de compras está ativa: comece pela requisição"*.
O manual começa onde o sistema começa.

### Ato 2 — O gestor decide (AGUARDANDO_APROVAÇÃO → APROVADA ou REJEITADA)

| # | Tela | Campos |
|---|---|---|
| 6 | Fila de aprovação | `/compras/aprovacao` |
| 7 | Aprovar | campo `observacao` + botão |
| 8 | Rejeitar | campo `motivo` (é o que o solicitante vai ler) + botão |
| 9 | **Rejeitada → corrigir** | 🆕 o botão de 17/08 (`e1e5dc63`). É a volta `REJEITADA → RASCUNHO`, e o manual precisa dela: sem ela o usuário acha que perdeu o pedido |

### Ato 3 — O comprador emite (APROVADA → CONVERTIDA)

| # | Tela | Campos |
|---|---|---|
| 10 | Emitir pedido | **fornecedor\***, número, data da compra, condição de pagamento, parcelas |
| 11 | O pedido nasce | `/compras/<pedido_id>` — e a requisição vira CONVERTIDA, estado **terminal** |

### Ato 4 — O dinheiro (só se a decisão D1 for "fluxo completo")

| # | Tela |
|---|---|
| 12 | Recebimento e atesto — `/compras/<id>/recebimento` |
| 13 | Lançar nota — `/compras/<id>/nota` 🆕 17/08 |
| 14 | Painel da tríade e **liberar** — `/compras/<id>` 🆕 17/08 |
| 15 | Conta a pagar e baixa — `/financeiro/contas-pagar` |
| 16 | Lote de pagamento, com **duas pessoas** — `/financeiro/fechamento-pagamentos` |

**16 telas**, ~45 campos numerados.

## Decisões suas — as quatro que mudam o tamanho do trabalho

| # | Decisão | Recomendação |
|---|---|---|
| **D1** | O manual vai até o **pedido emitido** (ato 3) ou até o **pagamento** (ato 4)? | **Até o pagamento.** "Requisição de compras" é o nome da porta, não do prédio: quem pede quer saber por que a nota ainda não foi paga. Custo: +5 telas e o manual passa a cruzar 4 papéis em vez de 3 |
| **D2** | Capturar com **alçadas avançadas ligadas ou desligadas**? | **Desligadas** — 🔬 é como o tenant está hoje (`flag_alcadas_avancadas.py 130329` → DESLIGADAS), e manual deve mostrar o que a pessoa vai ver. Com elas ligadas entram faixas, múltiplos aprovadores e anti-fracionamento: vira **outro** capítulo, não um parágrafo |
| **D3** | Cobrir o caminho **emergencial** e o **rejeitar → corrigir**? | **Sim, os dois.** São onde o usuário trava, e o segundo acabou de ganhar tela. Custo: 3 telas a mais |
| **D4** | Formato de entrega | **PDF** (precedente de 13/08) **+ o markdown fonte** versionado. O PDF é o que se manda para a obra; o markdown é o que se corrige |

## As tarefas, na ordem

**M1 — Cenário determinístico, em script versionado.**
Um `scripts/seed_manual_compras.py` que cria tenant, obra, fornecedor, insumos e as
**quatro requisições** nos estados que o manual precisa fotografar (rascunho, aguardando,
rejeitada, aprovada). Sem isso não há como refazer o manual daqui a três meses — é
exatamente o que faltou em 22/07. Nomes realistas (cimento, chapa, vergalhão), porque print
com "Item Teste 1" não convence ninguém na obra.
*Prova:* rodar duas vezes seguidas produz o mesmo cenário.

**M2 — O motor de anotação.**
`scripts/anotar_captura.py`: dado (url, lista de marcações), injeta o overlay, fotografa,
salva. Contorno de 3px, badge circular numerado, cor única e alta em contraste.
*Prova:* teste que roda o motor contra uma página fixa e confere que o PNG mudou nos
pixels da caixa — e que **seletor inexistente levanta exceção**, não aviso.

**M3 — O roteiro declarativo.**
`docs/manual_ciclo/roteiro_compras.py`: as 16 telas, cada uma com rota, papel de quem loga,
pré-condição de estado e a lista numerada de campos. **É a fonte única** dos números da
imagem e da legenda do texto.
*Prova:* rodar a captura inteira, ponta a ponta, exit 0.

**M4 — O texto.**
Para cada tela: o que a pessoa está tentando fazer, a legenda numerada dos campos, o que
acontece ao clicar, e o erro comum. Tom do `manual_ciencia_pdf.py`: frase curta, número
tirado do código.

**M5 — A montagem.**
Estender `gerar_manual_pdf.py` para consumir o roteiro em vez da lista fixa `STEPS`.

**M6 — A conferência humana.** O manual pronto na mão, você clica seguindo os passos. Se
travar em algum, o manual está errado **ou** o sistema está — e as duas descobertas valem.

## Riscos

1. 🔴 **Alguma tela do fluxo vai quebrar durante a captura.** Já aconteceu hoje, uma vez.
   Isso não é risco do plano, é o **rendimento** dele — mas cada tela quebrada vira um
   conserto com red-first antes de o manual seguir, e isso alarga o prazo de forma que não
   dá para estimar de antemão.
2. ⚠️ **Dado de dev.** Os prints sairão de um tenant semeado. Nenhum valor de tela pode ser
   citado no texto como se fosse número de produção.
3. ⚠️ **O manual envelhece na primeira mudança de tela.** Mitigação: refazer é **um
   comando**, e o guarda do seletor avisa qual passo quebrou. Sem os guardas, envelhece em
   silêncio — que é o que aconteceu com os 15 prints de julho.
4. 📖 **`docs/manual_ciclo/` já tem PDF e prints antigos.** Os novos vão para pasta própria
   (`docs/manual_compras/`), sem sobrescrever material que outro documento cita.

## Fronteiras

- **Não muda comportamento do sistema.** Defeito achado na captura vira commit próprio,
  com red-first, fora deste plano.
- **Nada de `main`** enquanto o conserto de hoje (`fix/fechamento-pagamentos-500`) não for
  decidido.
- **Sem marca da construtora** nos prints, pela mesma razão do manual de 13/08.

---

## Execução — 18/08

Decisões: **as quatro recomendações**, conforme o Cássio em 18/08. M1 a M5 entregues;
**M6 (a conferência humana) é o que resta.**

🔬 Pipeline completo, do zero, em **73 s**, três exit 0:

```
python scripts/seed_manual_compras.py        # cenário
python scripts/capturar_manual_compras.py    # 16 telas anotadas
python scripts/gerar_manual_compras.py       # PDF + markdown
```

Saída: `docs/manual_compras/Manual_Compras_SIGE.pdf` (1,9 MB, 16 telas, ~48 campos
numerados) e `manual-compras.md` ao lado. Testes: **9 passed**
(`tests/test_manual_compras_roteiro.py`), e o guarda provado load-bearing por mutação —
desligá-lo derruba 2 dos 9.

### O que a execução descobriu, e o plano não previa

1. 🔴 **O seed construiu o cenário por fora das regras — três vezes, o mesmo erro.**
   Ele gravou `compras_governanca_ativa = True` direto na coluna e assim passou por cima do
   guarda de 📖 `scripts/flag_compras_governanca.py:98-105`, que **RECUSA** ligar a
   governança em tenant com `escopo_obra_ativo` desligado. A recusa até diz o motivo por
   escrito — *"sem o escopo, ... só o ADMIN emite pedido"* — e 📖 `models.py:4482` descreve
   a cadeia dos cinco elos como "dependência DURA e não-óbvia".

   Consequência: as primeiras capturas saíram de **um estado que a ferramenta recusa**, no
   qual o passo de emitir pedido aparece como ato do administrador. Isso quase virou uma
   afirmação errada no manual e neste plano — a de que o papel COMPRADOR seria inerte e que
   haveria uma decisão pendente sobre isso. **Não há decisão pendente**: a regra existe, é
   aplicada pelo guarda, e o que faltava era o seed respeitá-la. 🔬 Com o escopo ligado,
   `papel_de_usuario_na_obra` devolve COMPRADOR e o bloco de emitir pedido aparece.

   Os outros dois casos do mesmo erro: `RequisicaoCompra(...)` criada pelo construtor **sem
   `regime_alcada`** (pego pelo teste-guarda no gate, com arquivo e linha), e o gênero
   errado no sufixo das flags. **A lição é uma só: seed que constrói o dado direto no modelo
   reproduz a FORMA e perde a REGRA** — e é justamente sobre a regra que um manual ensina.

2. ⚠️ **A captura falhou três vezes, e as três eram informação.** O guarda do seletor
   pagou-se na primeira rodada: `vincular-mapa` só existe quando a alçada pede cotação;
   `banco_id` some inteiro (`{% if bancos %}`) num tenant sem banco cadastrado — a tela de
   baixa abre sem lugar de onde tirar o dinheiro; e o bloco de emitir pedido some pelo
   item 1. Com o `except Exception` da captura de 22/07, as três teriam virado PNG velho
   no PDF.
3. ⚠️ **`import main` aborta o processo (SIGABRT, exit 134).** Ele carrega a pilha de
   reconhecimento facial via `ponto_views`, que estoura no encerramento **mesmo quando
   tudo deu certo**. Num pipeline cuja regra é "falhou, para", exit code mentiroso
   arruinaria o desenho. O seed não importa `main` — não usa rota nenhuma.
4. ⚠️ **`networkidle` não serve nesta interface.** A primeira captura esperou 30 s por
   tela e não produziu nenhuma foto: o SIGE mantém requisição de fundo e o evento nunca
   dispara. `domcontentloaded` + 1,6 s de acomodação.
5. ⚠️ **O Chromium do Playwright não sobe sem cinco bibliotecas do nix store**
   (`libnspr4`, `libnss3`, `libasound`, `libgbm`, `libxkbcommon`). Em CI o problema não
   existe (`playwright install --with-deps`); aqui não há root. Resolvidas por padrão —
   nunca por hash —, numa passada só sobre `/nix/store` e com cache em
   `.cache/sige_ld_library_path`. A primeira versão varria o store cinco vezes e **parecia
   travada**.
6. 📖 **Duas colunas de flag têm gênero diferente** — `compras_governanca_ativa` e
   `alcadas_avancadas_ativa` contra `recebimento_atesto_ativo` e
   `financeiro_dois_fluxos_ativo`. Errar o sufixo cria um atributo Python solto e a flag
   fica como estava, **em silêncio**. O seed confere depois de gravar.

### Desvio do plano

O roteiro ficou em `scripts/roteiro_manual_compras.py`, não em `docs/manual_ciclo/` como o
plano dizia: é código executável e o lugar de código é `scripts/`. Saídas em
`docs/manual_compras/`, como planejado.
