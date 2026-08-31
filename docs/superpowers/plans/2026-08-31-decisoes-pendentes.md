# Decisões pendentes — o que trava a Fase 8 e o Resgate da Espinha

> **Para quem decide.** Três perguntas. Cada uma trava um plano inteiro que já
> está escrito e pronto para executar. Nenhuma delas é técnica: são o
> significado de uma conta contábil, uma medição de produção, e uma regra de
> rateio de lucro.

## D6 — o de-para do plano de contas não pode ser chaveado só por código

**O que trava:** `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md`,
Task 4 em diante (10 tasks, 3 de 21 arquivos existem).

**O problema:** os dois seeders aposentados trocam entre si o significado de
`5.1.01` e `5.1.02`. Um de-para chaveado só pelo código da conta aplicaria o
significado errado à metade do parque, silenciosamente — e um lançamento
contábil mal classificado não se anuncia.

**A tabela que expõe a colisão**, extraída dos dois seeders concorrentes:

| Código | `contabilidade_utils.criar_plano_contas_padrao` | `financeiro_seeds.PLANO_CONTAS_CONSTRUCAO` |
|---|---|---|
| `5` | CUSTOS | DESPESAS |
| `5.1` | CUSTO DOS SERVIÇOS PRESTADOS | DESPESAS OPERACIONAIS |
| **`5.1.01`** | **Materiais Diretos** | **MÃO DE OBRA** |
| **`5.1.02`** | **Mão de Obra Direta** | **MATERIAIS** |

**O aperto:** a spec manda escrever o de-para conta a conta, **não** derivado
por heurística de nome, "porque os nomes são justamente o que está
inconsistente". Mas 🔬 **a única evidência sobrevivente de qual seeder rodou é
`plano_contas.nome`.** A spec proíbe usar o nome, e sem o nome a Task 4 não é
executável corretamente.

**As saídas:**

- **(a) Chavear em `(codigo, nome)` com igualdade exata** contra os dois
  conjuntos fechados que estão no repositório — *recomendada pelo plano*. Não é
  heurística: é reconhecer a assinatura de um dos dois seeders conhecidos.
  Qualquer par fora dos dois conjuntos **faz a migration falhar e nomear o
  par**. Preserva o "nunca chutar"; derivar por semelhança de string
  (`'MÃO DE OBRA' ≈ 'Mão de Obra Direta'`) segue proibido.
- **(b) Manter a regra literal da spec** (só `codigo`) — mandaria material para
  pessoal em metade do parque, **em silêncio**, porque a partida migra sem
  falhar.
- **(c) Adiar a Fase 8** até haver outra evidência de proveniência além do nome.

**O que muda em cada uma:** (a) destrava as 10 tasks e assume que os dois
conjuntos do repositório cobrem todo o parque — se algum tenant tiver um plano
de contas de terceira origem, a migration para e mostra qual. (b) é a única que
corrompe dado. (c) mantém o status quo: dois significados para o mesmo código,
e relatórios que não se comparam entre tenants.

## FASE8-T1 — medir o plano de contas em produção

**O que trava:** a mesma Fase 8, na raiz. A Task 4 estaria sendo decidida com
número de banco de **dev**, que é majoritariamente resíduo de suíte de teste.

**A pergunta:** se produção mostrar `5.x` dominante, a spec da Fase 8 está
errada e o canônico volta à mesa. Ninguém mediu.

**As saídas** (fonte: `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md`,
linhas 51 e 196-197 — o comentário de `q8_planos_de_contas`, a função que a
Task 1 daquele plano acrescenta a `scripts/medir_producao.py`):

- **(a) Produção mostra `5.x` residual** (o padrão esperado — dev é "99,9%
  resíduo de suíte"): a Task 4 segue como um de-para de algumas centenas de
  linhas, do tamanho que o plano já previu. A Fase 8 segue como está escrita.
- **(b) Produção mostra `5.x` dominante**: "a spec da Fase 8 está errada e o
  canônico tem de ser reavaliado ANTES de qualquer código" (citação literal do
  comentário da q8). A Task 4 deixa de ser um de-para e vira projeto próprio —
  o plano inteiro volta à mesa antes de a Task 4 começar.

**O que muda em cada uma:** (a) libera a Task 4 para rodar do jeito que está
escrita — nenhuma mudança de escopo. (b) para a Fase 8 na Task 4: o de-para
que a Task 4 assume (algumas centenas de linhas, revisável à mão) deixa de
valer, e antes de escrever a migration 316 é preciso redesenhar quantas
contas `5.x` têm de virar `6.x` em produção — que pode ser ordens de grandeza
maior do que o de-para pequeno que a spec assume. **Ninguém rodou
`python scripts/medir_producao.py` contra produção ainda — por isso a
pergunta segue aberta.**

## VIGA-I — a regra de verba/lucro do telhado viga I

**O que trava:** `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`
(10 tasks, 7 de 20 arquivos existem, porte de 2.542 linhas do PR #6).

**O que trava exatamente:** apenas a **Task 8 de 10** (migration 319: `verba`,
`lucro` e `pai` em `rdo_subempreitada_apontamento`). 🔬 As outras nove são porte
de código já escrito e testado, e estão sendo entregues pela Task 8 do plano de
fecho de 31/08 — **esta decisão não segura o resto.**

**A pergunta:** o "telhado viga I" precisa de **verba**, **lucro %** e a escolha
entre as **opções A/B/C**, mantendo a **venda total travada** em
**R$ 1.720.796,75**, no orçamento **ORC-BAIA-REV10 (id 98)** (fonte:
`docs/superpowers/plans/2026-06-15-fatia-2-custos-nao-mo-por-atividade-plan.md:482`).

**O que são A e B** (mesma fonte, linhas 478-480):

- **Opção A** — "reduzir margens dos demais proporcionalmente": os outros
  itens do orçamento absorvem o item novo do telhado, cada um cedendo margem
  na proporção do que já tem.
- **Opção B** — "markup uniforme": ajustar `orcamento.margem_pct_global` até
  `venda_total == 1720796.75` — um único percentual global se move até a
  venda total fechar de novo no valor travado.
- **Opção C** — 🔴 **referenciada mas nunca definida.** A fonte
  (`docs/superpowers/plans/2026-06-15-fatia-2-custos-nao-mo-por-atividade-plan.md:471`)
  cita "opção A/B/C de absorção" e aponta para um arquivo
  `ESPACO_telhado_viga_i_baia_rev10.md` como o lugar onde a decisão — inclusive
  o que é a opção C — seria registrada. 🔬 **esse arquivo não existe na
  árvore** (`find . -name "ESPACO_telhado_viga_i*"` não devolve nada; outros
  três documentos citam o mesmo arquivo faltante, nenhum o define). Definir o
  que é a opção C, ou descartá-la, faz parte desta decisão — não é um detalhe
  técnico a preencher depois.

**O que muda:** com a resposta, a migration 319 entra, o ramo de subempreitada
volta a `custo_nao_mo_atividade`, e os testes da Fatia 2
(`tests/test_resultado_fatia2_custo_nao_mo.py`) saem de `xfail`. Sem ela, o
resultado por atividade fica **sem o custo de subempreitada** — não erra, mas
mede menos do que promete, e o `xfail` é o registro disso.
