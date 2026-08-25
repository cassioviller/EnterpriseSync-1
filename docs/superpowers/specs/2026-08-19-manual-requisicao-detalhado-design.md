# O manual da requisição de material, em detalhe — spec

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **REALIZADA** — Fases 1–3 do ciclo de compras, entregues com runbook rodado por script. **Leia os 📌 no corpo** — são as divergências que a execução descobriu contra o plano. ⚠️ o code review de 25/08 achou defeitos vivos neste módulo.
>
> Veredito dado por **existência de código na árvore**, não por checkbox nem por
> mensagem de commit. Índice completo em `docs/planos-em-aberto-2026-08-25.md`.


> **Data:** 2026-08-19 · **Origem:** pedido do Cássio — *"atualizar com mais
> detalhes e prints o manual da requisição de material"*.
> **O que ele estende:** `docs/manual_compras/`, entregue em 18/08
> (plano `2026-08-18-plano-manual-requisicao-compras.md`).

## O que existe hoje

16 telas do ciclo inteiro, de login a lote de pagamento, com ~48 campos marcados
por caixa numerada. **A requisição ocupa quatro delas** — lista, preencher,
rascunho, enviar —, e o resto do documento é o que acontece *depois* que ela sai
das mãos de quem pediu.

A arquitetura que este spec preserva, e que é a razão de o manual ser confiável:

* 📖 `scripts/roteiro_manual_compras.py` é a **fonte única**. Dele saem a caixa
  desenhada na figura, a legenda numerada embaixo dela e a ordem dos passos.
  Não existem duas listas para divergir.
* 📖 `scripts/anotar_captura.py` desenha as caixas **no DOM, ancoradas ao
  seletor**, antes do screenshot — não coladas por pixel depois.
* **Seletor que não casa derruba o processo.** 📖 A captura de 22/07
  (`capturar_manual_ciclo.py:76-79`) faz o oposto: engole o erro e segue, e como
  o gerador lê a pasta por nome de arquivo, o PDF sai montado com a foto velha.
  Um manual que aponta a seta para o campo errado é pior que manual nenhum.

## O problema

Três dos quatro casos que faltam **não existem em rota nenhuma**. A recusa da
tela, o aviso de quantas aprovações a alçada vai exigir e o selo do rito de
emergência aparecem como *flash na resposta de um POST*. A captura de hoje é
puramente navegacional — `goto` → marcar → foto —, então esses três são
invisíveis para ela.

E são justamente os que geram chamado de suporte: ninguém consegue imaginar uma
tela de erro que nunca viu.

## Decisão 1 — ações declarativas, no roteiro

Rejeitadas: (b) funções de preparo dentro do capturador, que tirariam metade da
verdade do roteiro e recriariam as duas listas que divergem; (c) descrever as
recusas em texto, que entrega menos do que foi pedido.

`anotar_captura.py` ganha:

```python
@dataclass
class Acao:
    tipo: str      # 'preencher' | 'escolher' | 'marcar' | 'submeter'
    seletor: str
    valor: str = ''
```

e `Tela` ganha `acoes: list = _field(default_factory=list)`.

O capturador executa a lista **depois do `goto` e antes de `marcar`**. Duas
regras, herdadas do que já existe:

1. **Seletor de ação que não casa derruba o processo**, igual ao seletor de
   campo. Ação que falha em silêncio produz a foto da tela *anterior* à recusa —
   uma foto plausível e errada, que é o modo de falha que este desenho inteiro
   existe para evitar.
2. **A tela da recusa é fotografada com o flash marcado como campo.** O `.alert`
   vira a caixa nº 1 e a legenda diz o que o sistema recusou e por quê. Foto de
   recusa sem o flash marcado é print sem legenda.

## Decisão 2 — as recusas são as que a rota realmente aplica

Levantadas do código, não imaginadas. 📖 `compras_views.py`, rota de criação:

| Guarda | Texto do flash | Entra? |
|---|---|---|
| `:1987` sem obra | *"Toda requisição precisa de uma obra…"* | ✅ tela 05 |
| `:2030` sem item | *"Adicione pelo menos um item à requisição."* | ✅ tela 06 |
| `:2049` emergencial sem justificativa | *"…exige justificativa escrita — ela é o preço da dispensa de aprovação"* | ✅ tela 07 |
| `:1994` obra inválida | *"Obra inválida. Selecione uma obra pelo menu."* | ❌ só por POST forjado |
| `:2001` sem papel na obra | *"Você não tem papel de gestor ou comprador nesta obra…"* | ❌ ver "o que não entra" |

## Decisão 3 — as telas: 16 → 24

Oito novas, marcadas 🆕. A renumeração dos slugs é livre: a captura apaga a pasta
inteira a cada rodada, então não há foto órfã.

### Antes de tudo
| slug | papel | o que mostra |
|---|---|---|
| `01_login` | anon | (inalterada) |

### Ato 1 — quem precisa, pede
| slug | papel | o que mostra |
|---|---|---|
| `02_lista_requisicoes` | solicitante | **mais campos**: os selos de estado e o que cada coluna diz — hoje só marca o botão "Nova" |
| `03_nova_requisicao` | solicitante | **mais campos**: adicionar/remover linha e o total estimado, além dos 10 de hoje |
| `04_alcada_no_sucesso` 🆕 | solicitante | o flash do sucesso: *"vai precisar de N aprovação(ões)"*. **Criada na obra de janela limpa** (ver Decisão 4) |
| `05_recusa_sem_obra` 🆕 | solicitante | submeter sem escolher obra |
| `06_recusa_sem_item` 🆕 | solicitante | submeter sem nenhum item |
| `07_recusa_emergencia` 🆕 | solicitante | marcar emergência e deixar a justificativa vazia |
| `08_rascunho_itens` | solicitante | (era `04`) |
| `09_enviar` | solicitante | (era `05`) |
| `10_aguardando` 🆕 | solicitante | o que sobra depois de enviar: **sem botão de editar**, só acompanhar |
| `11_subiu_de_faixa` 🆕 | solicitante | *"Esta requisição subiu de faixa"* — o anti-fracionamento visível pela primeira vez. **Criada em `OB-MANUAL`**, cuja janela já está cheia |
| `12_emergencia` 🆕 | solicitante | o rito: aprovada na hora, com a ratificação das 48 h devendo |

> **Os campos novos das telas `02` e `03` saem do template, não da imaginação.**
> O plano os levanta contra `templates/compras/requisicao_lista.html` e
> `requisicao_nova.html`, e **campo que não existir é descartado, nunca inventado**
> — seletor que não casa derruba a captura, que é o comportamento certo.

### Ato 2 — o gestor decide
| slug | papel | o que mostra |
|---|---|---|
| `13_fila_aprovacao` | gestor | (era `06`) |
| `14_aprovar` | gestor | (era `07`) |
| `15_rejeitar` | gestor | (era `08`) |
| `16_corrigir` | solicitante | (era `09`) |
| `17_aprovada_emitir` 🆕 | solicitante | a requisição APROVADA e o bloco de emitir pedido — **é aqui que se descobre se você tem o papel**: quem não tem simplesmente não vê o bloco |

### Atos 3 e 4 — inalterados
`18_emitir_pedido`, `19_pedido_triade`, `20_recebimento`, `21_nota`,
`22_liberar`, `23_pagar`, `24_lote`.

## Decisão 4 — o cenário ganha uma segunda obra

🔬 **O achado que obriga a isso:** 📖 o formulário de nova requisição **não tem
campo de etapa** — os únicos campos são obra, data, justificativa, emergencial,
mapa e os itens. Mas 📖 `compras_views.py:2005-2015` lê e valida
`obra_servico_custo_id`. **Toda requisição criada pela tela cai no grupo de etapa
NULA, sempre.**

Consequência para o manual: as telas `04` e `11` cairiam na **mesma janela** e
sairiam idênticas — o cenário do manual já chega com a janela cheia, então a
primeira requisição criada durante a captura já subiria de faixa. Como não dá
para separá-las por etapa, separam-se por **obra**:

* `seed_manual_compras.py` ganha uma segunda obra, de **janela limpa**, com
  vínculo `usuario_obra` para o solicitante;
* a tela `04` é criada nela — mostra a alçada falando **sem** o degrau;
* a tela `11` é criada em `OB-MANUAL` — mostra o degrau.

Efeito colateral bem-vindo: o campo "Obra" da tela `03` deixa de ser um select de
uma opção só, que não ensina nada.

**Dependência de ordem, escrita no roteiro:** a `11` só é verdadeira porque a
janela de `OB-MANUAL` está cheia. Isso vira comentário, não conhecimento tácito.

## O que as ações criam, e o que isso custa

| Tela | Grava? |
|---|---|
| `05`, `06`, `07` | **Não.** A rota redireciona antes de gravar |
| `04`, `11`, `12` | **Sim** — e é o que as torna honestas: o dado nasce pela tela, que é o caminho que a pessoa percorre |

Nada disso atrapalha os Atos 2 a 4: 📖 `roteiro_manual_compras.resolver_ids()`
acha as requisições do cenário **por número estável** (`RC-2026-0001` a
`RC-2026-0004`), nunca por "a última". E a alçada das que já existem foi
carimbada na criação, no seed — requisição nova não reescreve requisição velha.

## Testes

Nenhum precisa de browser nem de banco, como os de hoje
(`tests/test_manual_compras_roteiro.py`):

1. toda `Acao` tem tipo conhecido e seletor não vazio;
2. tela com `acoes` tem **pelo menos um campo marcado** — do contrário é print
   sem legenda;
3. `submeter` é a última ação de qualquer tela que o use — ação depois do POST
   agiria na página seguinte, que não é a que está sendo fotografada;
4. as invariantes de hoje seguem valendo: numeração única e contígua por tela,
   slugs únicos e ordenados, papel conhecido, resumo não vazio.

## O que NÃO entra

* **Consertar o campo de etapa ausente.** É defeito de produto, não do manual.
  Fica registrado no `ESTADO-ATUAL.md` com a pergunta que abre: ou o formulário
  passa a oferecer a etapa, ou a leitura na rota é vestigial e sai. Enquanto não
  for decidido, o agrupamento por etapa do anti-fracionamento é **inalcançável
  pela tela**.
* **A recusa por falta de papel na obra** (`:2001`). É a armadilha que derrubou a
  primeira captura do manual em 18/08 e merece figura — mas exige uma pessoa sem
  vínculo no cenário, e o cenário existe para ensinar o caminho certo. Fica como
  candidata à próxima rodada.
* **Mudar o gerador do PDF.** Ele já monta o que o roteiro disser.

## Como regenerar

```bash
python scripts/seed_manual_compras.py      # 1. o cenário
python scripts/capturar_manual_compras.py  # 2. as fotos (agora com ações)
python scripts/gerar_manual_compras.py     # 3. o markdown e o PDF
```

Pré-requisito: o app de pé em `http://localhost:5000`.

## Riscos

| Risco | Mitigação |
|---|---|
| Uma ação muda a tela e o campo marcado deixa de existir | O guarda: seletor que não casa **para o processo**, com o slug da tela |
| O flash não aparece (a rota mudou o texto) | O `.alert` é campo marcado; se sumir, a captura para. Texto que muda, porém, **não** é pego — a legenda é escrita no roteiro |
| As requisições criadas na captura poluem o cenário entre rodadas | O seed limpa requisições e pedidos a cada execução, e a ordem é sempre seed → capturar |
