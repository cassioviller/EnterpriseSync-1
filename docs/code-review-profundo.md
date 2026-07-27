# Code review profundo — estrutura e registro de achados

> Aberto em **2026-07-27**. Documento vivo: a estrutura é fixa, os achados
> entram por varredura concluída. Se a sessão cair, o que está registrado
> aqui está verificado.

## Por que revisar por PADRÃO e não por arquivo

O repositório tem ~150 arquivos de teste e dezenas de milhares de linhas de
serviço. Ler arquivo por arquivo não converge, e cansa antes de chegar no
que importa.

Mas esta sessão produziu uma evidência melhor: **os defeitos encontrados têm
formas recorrentes**, e cada forma é varrível pelo código inteiro. Dos seis
defeitos reais achados hoje — três no meu próprio código, um numa premissa da
entrega de 24/07, dois nos guards das flags — nenhum foi surpresa isolada:
todos são instâncias de um padrão que já tinha mordido antes.

Um exemplo do porquê isso funciona: o filtro `is_cliente` esquecido no
`IndiceTarefas` é **exatamente** o mesmo defeito que a Task #147 já corrigira
no endpoint `tarefas-rdo`. Uma varredura pelo padrão teria achado os dois de
uma vez; uma leitura por arquivo achou um em julho e o outro em setembro.

## Os seis padrões, derivados de defeitos reais

| # | Padrão | Instância confirmada | Como varrer |
|---|---|---|---|
| P1 | **Filtro de escopo esquecido** — query sem `admin_id`, `is_cliente` ou `ativa` | `IndiceTarefas` (27/07) e Task #147 no `tarefas-rdo` | grep de `.query.filter_by(` e `.filter(` sobre modelos multi-tenant, conferindo as chaves |
| P2 | **Premissa documentada que o dado desmente** | "a linha quantitativa antiga já grava `percentual_realizado`" — 148 linhas provam o contrário | extrair afirmações de continuidade/equivalência dos docs e commits e **medir cada uma** |
| P3 | **Guard depois do efeito** | as duas flags gravavam e avisavam depois | grep de `definir_flag`/`commit` seguido de `print("AVISO` ou validação |
| P4 | **Silêncio onde deveria haver erro** | `tarefa_mpp` desconhecido descartado; parser em locale estranho; foto ausente | grep de `except Exception: pass`, `continue` sem log, `or []`, `.get(...)` sem checagem |
| P5 | **Commit alheio dentro de transação** | `get_calendario` comita no meio de `registrar_apontamento` | grep de `session.commit()` em funções utilitárias/leitura |
| P6 | **Duas implementações da mesma convenção** | duas ordenações de foto numerada divergindo | grep de constantes/regras duplicadas (ordenação, normalização, parsing de data) |

## Severidade — o critério

| Nível | Definição | Exemplo desta sessão |
|---|---|---|
| 🔴 | Dado errado gravado, ou vazamento entre tenants, **sem sinal visível** | apontamento na cópia do cliente: o físico não se move e nada acusa |
| 🟠 | Perda ou corrupção visível, mas detectável | tarefas caindo a 0% ao ligar a flag |
| 🟡 | Comportamento confuso, recuperável | parser devolvendo "0 dias" em vez de erro |
| ⚪ | Manutenção: duplicação, nome ruim, comentário mentiroso | as duas ordenações de foto |

Um achado só entra neste documento **depois de confirmado com evidência** —
uma query no banco, uma execução, ou `arquivo:linha` lido. Suspeita sem
confirmação vai para "a investigar", não para "achados".

## Ordem das varreduras

Por severidade potencial, não por facilidade:

1. **P1 — escopo esquecido** 🔴 (multi-tenant é o ativo mais crítico)
2. **P5 — commit alheio** 🔴 (corrompe transação silenciosamente)
3. **P2 — premissa desmentida** 🟠 (cada uma pode virar rollout errado)
4. **P4 — silêncio** 🟡
5. **P3 — guard tardio** 🟡
6. **P6 — convenção duplicada** ⚪

---

# Achados

> Vazio até a primeira varredura fechar. Cada achado traz evidência e
> severidade; o que não foi confirmado fica em "a investigar".

## Varredura 1 — P1: filtro de escopo esquecido ✅ 27/07

**Método:** grep de `TarefaCronograma.query.filter_by(` e `.filter(` em
`*.py`, `services/`, `utils/`, `views/`, `scripts/`, separando as buscas por
`id=` (PK + tenant, onde `is_cliente` é irrelevante) das buscas **por obra**,
que devolvem conjuntos. 26 ocorrências sem `is_cliente`; 5 são por obra.

**Duas medições que definiram a severidade** (🔬 27/07, banco de dev — ⚠️
dominado por carga de suíte; prova a forma, não o volume de produção):

| | |
|---|---|
| Obras com as **duas visões** (empresa + cliente) ativas | **141** |
| Tarefas **arquivadas** (`ativa=False`) | 217, em **187 obras** |

Eu tinha suposto que a cópia-cliente fosse rara — são 141 obras.

### 🔴 A1 · `gerar_medicao` calcula % e VALOR da medição sobre tarefas-cliente e arquivadas

`portal_obras_views.py:723`

```python
tarefas_empresa = TarefaCronograma.query.filter_by(
    obra_id=obra_id, admin_id=admin_id, responsavel='empresa'
).all()                                    # sem is_cliente, sem ativa
total = len(tarefas_empresa)
perc = sum(t.percentual_concluido or 0 for t in tarefas_empresa) / total
valor_medido = round(float(obra.valor_contrato) * perc / 100, 2)
```

O resultado vira uma linha de `MedicaoObra` com `percentual_executado` e
`valor_medido` — **documento de medição, dinheiro**.

As tarefas da cópia-cliente **nunca recebem sync**: `sincronizar_percentuais_obra`
é chamada com `cliente=False` em todos os pontos de produção
(`utils/cronograma_engine.py:884`, `services/atualizacao_rdos.py:337`,
`services/importacao_fisico_financeiro.py:674`); só `cronograma_views.py:402`
passa `cliente_mode`. Então elas entram na média com `percentual_concluido`
parado — **diluindo o percentual e subestimando o valor medido**.

🔬 **Impacto medido: 107 obras** teriam percentual de medição diferente com os
filtros postos. Amostra: **8,75% → 11,67%** — o valor medido sai **25% menor**
do que deveria.

> Achado secundário, do padrão P6: esta média é **simples**, enquanto
> `calcular_progresso_geral_obra_v2` pondera por duração. São **duas
> definições de "% da obra"** convivendo — e é a menos rigorosa que gera
> dinheiro.

**Não corrigido de propósito:** consertar muda números de medição já
apresentados ao cliente. É decisão do dono, não do revisor.

### 🟠 A2 · Tela de medição lista tarefa-cliente e arquivada

`medicao_views.py:54` — a lista que vai para `gestao_itens.html` (onde se
vinculam tarefas a itens de medição com peso) inclui a cópia-cliente e as
arquivadas. Consequência: **nomes duplicados na tela de vínculo** nas 141
obras, e possibilidade de vincular um item de medição a uma tarefa arquivada.

### 🟡 A3 · Contagem inflada no dossiê de handoff

`services/obra_handoff.py:121` — `total_tarefas` conta cópia-cliente e
arquivadas. Número errado num relatório de passagem de obra.

### 🟡 A4 · `obra_com_cronograma` pode ser verdade só com tarefa arquivada

`views/orcamentos_views.py:260` — `n_tarefas > 0` decide se a obra "já tem
cronograma". Uma obra cujo cronograma inteiro foi arquivado responde que sim.

### 🟡 A5 · Entregas de terceiros sem escopo, e com tenant condicional

`services/entregas_terceiros.py:165` — sem `is_cliente`, sem `ativa`, e o
`admin_id` só entra `if admin_id is not None`. Entrega de terceiro duplicada
nas obras com as duas visões.

### Conclusão da varredura 1

O padrão P1 é **real e sistêmico**: 5 ocorrências fora do código que eu
escrevi, uma delas gerando dinheiro. O `is_cliente` esquecido não é descuido
pontual — é uma convenção que o código **não tem como lembrar**, porque
depende de o autor saber que a cópia-cliente existe.

**Recomendação estrutural** (além de corrigir as 5): dar ao modelo um
_scope_ explícito — por exemplo `TarefaCronograma.do_cronograma_interno(obra_id, admin_id)`
como classmethod única — para que esquecer o filtro exija sair do caminho
padrão, em vez de ser o caminho padrão.

### Correções aplicadas — 27/07

Autorizadas pelo dono, inclusive a A1 (que muda número financeiro).

| Achado | Erro | Correção |
|---|---|---|
| 🔴 A1 | `portal_obras_views.py:723` — média incluía cópia-cliente (percentual parado) e arquivadas; o resultado virava `percentual_executado` e `valor_medido` | `+ is_cliente=False, ativa=True`, com o número medido registrado no comentário |
| 🟠 A2 | `medicao_views.py:54` — lista de vínculo com nomes duplicados e tarefa arquivada | mesmos dois filtros |
| 🟡 A3 | `services/obra_handoff.py:121` — `total_tarefas` inflado no dossiê | mesmos dois filtros |
| 🟡 A4 | `views/orcamentos_views.py:260` — obra "tem cronograma" só com tarefa arquivada | mesmos dois filtros |
| 🟡 A5 | `services/entregas_terceiros.py:165` — entrega duplicada no dropdown do RDO | `is_cliente.is_(False)` + `ativa.is_(True)` (o `admin_id` condicional foi mantido: é defesa em profundidade opcional documentada na própria docstring) |

**Prova de que o teste pega o defeito.** `tests/test_escopo_cronograma_interno.py`
monta a obra com as três populações (interna a 60%, cópia-cliente a 0%,
arquivada a 0%) e exige 60%. Revertendo a correção do A1, o teste falha com
**`assert 20.0 == 60.0`** — a diluição exata de (60+0+0)/3. Num contrato de
R$ 100.000, R$ 20.000 medidos em vez de R$ 60.000.

5 testes, todos verdes com a correção. Duas armadilhas de ambiente que o teste
precisou tratar e ficam registradas: sem `import main` os blueprints não estão
registrados (a rota devolve BuildError), e sem desligar `WTF_CSRF_ENABLED` o
POST é rejeitado com 302 — o teste passaria testando o redirect, não a regra.

## Varredura 2 — P5: commit alheio dentro de transação ✅ 27/07

**Método:** enumerar as funções de `services/` e `utils/` que chamam
`session.commit()` (48) e cruzar com quantos módulos as importam. Uma função
que comita e é usada como biblioteca é perigosa: **o chamador não vê o
commit**. A heurística por nome (`get_`, `calcular_`, `verificar_`) rendeu
pouco — o que rendeu foi olhar a *posição da chamada* dentro de fluxos que
montam trabalho antes de fechar.

### 🟠 B1 · O import físico-financeiro NÃO era atômico

`services/importacao_fisico_financeiro.py` — a ordem era:

```
_recusar_se_versionada_pelo_fluxo_novo(obra)
_limpar_derivados(obra, admin_id)        ← DESTRUTIVO: apaga tarefas,
                                            propostas, orçamentos, medições
_importar_comercial / _importar_cronograma / _importar_custos
_importar_medicoes
_importar_rdos(...)  →  sincronizar_percentuais_obra()  ← COMITA AQUI
_registrar_versao_inicial(...)
db.session.commit()                      ← o commit "de verdade"
```

`sincronizar_percentuais_obra` comita por conta própria. Chamada de dentro de
`_importar_rdos`, ela **fechava a transação no meio**: tudo o que veio antes —
inclusive a limpeza destrutiva — ficava gravado antes de
`_registrar_versao_inicial` rodar.

Uma falha ali deixava a obra com os derivados antigos **apagados**, os novos
gravados e **sem a `CronogramaVersao` nº1** — justamente o registro de que o
guard do M09 depende para decidir se um reimport é permitido.

**Correção:** a sincronização saiu de `_importar_rdos` e passou a rodar
**depois** do commit final, como já era em `services/atualizacao_rdos.py`. O
pior caso vira "obra importada com percentual dessincronizado" — recuperável
reimportando —, em vez de "derivados apagados e sem versão".

> ⚠️ **A primeira versão do teste não provava nada.** Ela comparava
> `count()` de tarefas e RDOs antes/depois — e o reimport recria a MESMA
> quantidade, então a contagem batia mesmo com a transação quebrada. O teste
> passava com o defeito de volta. A asserção correta é por **identidade**: o
> conjunto de ids tem de ser o mesmo. Com o defeito, ele acusa
> **"101 tarefa(s) e 26 RDO(s) sumiram"**.

### Não confirmados nesta varredura 2

- `utils/notifications.py::verificar_estouros_obra` comita, e o nome sugere
  leitura — mas a docstring **declara** o commit e o chamador é uma view de
  render (sem trabalho pendente). Nome ruim, não defeito.
- `event_manager.py::calcular_horas_folha` comita duas vezes; é handler de
  evento, escritor por natureza. Mesmo caso: nome de leitura, papel de escrita.
- `services/orcamento_operacional.py::garantir_operacional` tem a MESMA forma
  do `get_calendario` (cria-se-não-existe), mas usa `flush()` + tratamento de
  `IntegrityError` — está correto.

## Varredura 3 — P2: premissa documentada que o dado desmente ✅ 27/07

**Método:** extrair dos docs e commits as afirmações de continuidade,
equivalência, idempotência e reversibilidade — as que sustentam decisão de
rollout — e **medir cada uma**. Foi o padrão que já tinha rendido o achado das
148 linhas legadas no `rdo_percentual_livre`.

### 🟠 C1 · O dual-write do editor v2 só existia numa direção

A afirmação, repetida no commit da Fase 1 e **no runbook que eu mesmo escrevi
horas antes** (`docs/cronograma-editor-v2-rollout.md`):

> "com a flag desligada o sistema volta a usar `predecessora_id` (TI/0), que
> o dual-write manteve alimentado"

**Falso.** A sincronização existe só no sentido
`predecessora_id → tarefa_vinculo` (`sincronizar_vinculos_de_predecessora_id`,
usada no pós-importação .mpp e na geração por proposta). O CRUD novo
(`cronograma_views.py::criar_vinculo`) gravava **apenas** `TarefaVinculo`; o
campo legado — que é o que o motor antigo lê — ficava NULL. Não há nenhum
código no repositório que faça o caminho inverso.

**Consequência:** toda dependência criada com o editor v2 ligado **sumia no
rollback**, em silêncio. O runbook prometia uma reversão que não acontecia.

🔬 **Medido (dev, 27/07): 517 de 722 vínculos (72%)** não tinham reflexo no
campo legado; **490** deles seriam representáveis por ele.

**Correção:** `_espelhar_no_campo_legado()` passa a manter `predecessora_id`
em dia na criação e na exclusão de vínculo. E o runbook foi corrigido com a
tabela do que sobrevive:

| Vínculo criado com o v2 ligado | Sobrevive ao rollback? |
|---|---|
| Única predecessora, TI, lag 0 | ✅ |
| Segunda predecessora da mesma tarefa | ❌ a coluna guarda UMA |
| Tipo II, TT ou IT | ❌ a coluna é sempre TI |
| Lag ≠ 0 | ❌ a coluna não tem lag |

Nos casos ❌ o campo fica **NULL de propósito**: perder a dependência no
rollback é melhor do que reintroduzi-la com o tipo errado. **O espelho é
parcial por natureza da coluna, não por limitação de implementação** — e o
runbook agora diz isso, em vez de prometer reversão completa.

4 testes novos em `tests/test_cronograma_vinculos_api.py`. Sem a correção,
falham com `assert None == <id>`.

### Premissas verificadas e CONFIRMADAS

Registradas para não serem re-investigadas:

| Premissa | Veredito |
|---|---|
| "flag `rdo_percentual_livre` desligada ⇒ comportamento byte-idêntico" | ✅ já coberto por teste dedicado em `test_rdo_percentual_livre.py` |
| "reimportar não duplica" (o import é upsert por `(codigo, admin_id)`) | ✅ coberto por `test_importacao_fisico_financeiro.py` |
| "assinado sem trilha de transição = 0" (Fase 5) | ✅ invariante global testado — e esta sessão provou que ele PEGA violação, ao acusar 4 RDOs que meu próprio teste tinha criado |

## Varredura 4 — P4: silêncio onde deveria haver erro ✅ 27/07

**Método:** varrer `except` que engole a exceção sem log, e `continue` que
descarta dado sem aviso. 205 ocorrências — mas **97 são em `migrations.py`**,
onde engolir "já existe" é o design idempotente, e boa parte do resto é
parsing defensivo de formulário (`float()`, `int()`, `strptime`), que é
legítimo.

O critério que separou ruído de defeito: **o silêncio descarta dado que o
usuário mandou, num caminho que grava?**

### 🟡 D1 · O import descartava apontamento de tarefa inexistente sem rastro

`services/importacao_fisico_financeiro.py::_materializar_rdos` — era:

```python
db_id = tid_to_db.get(tmpp)
if db_id is None:
    continue          # mudo
```

Um `tarefa_mpp` errado no JSON — um typo, ou um cronograma que mudou entre a
geração do arquivo e o import — **descartava o apontamento sem rastro nenhum**,
e o físico daquele dia simplesmente não entrava. Ninguém tinha como saber.

O caso irmão já avisava: `_vincular_etapa_tarefas` (linha 237) acrescenta
`"Etapa X: tarefa N do .mpp não encontrada."` à lista `avisos`, que o import
devolve e a rota/CLI imprime. O caminho dos RDOs não.

**Correção:** `avisos` passou a ser encaminhado até `_materializar_rdos`, e o
descarte vira `"RDO <data>: tarefa N do .mpp não encontrada — apontamento
descartado."` Foi exatamente esse defeito que me fez, no serviço novo
(`services/atualizacao_rdos.py`), transformar tarefa não resolvida em
**pendência no relatório** desde o início.

### Avaliados e descartados como ruído

- `views/rdo.py` (14 ocorrências) — parsing defensivo de campo de formulário
  (`float(horas)`, `int(funcionario_id)`). Um campo malformado pula a linha;
  a primeira dessas ocorrências **já loga**. Sem evidência de perda real e a
  UI controla o formato: não é defeito, é guarda.
- `migrations.py` (97) — idempotência por construção.

## Varreduras 5 e 6 — P3 e P6 ✅ 27/07

Fechadas juntas porque as duas já tinham sido resolvidas no caminho, e a
varredura formal serviu para confirmar que não sobrou instância.

### P3 — guard depois do efeito

Universo fechado: existem **cinco** flags de tenant. Todas foram examinadas.

| Flag | Guard |
|---|---|
| `escopo_obra_ativo` | ✅ já recusava (`usuario_obra` vazia) |
| `compras_governanca_ativa` | ✅ já recusava (faixa de alçada + escopo) |
| `cronograma_mpp_ativo` | — governa borda visual; não há efeito a guardar |
| `cronograma_editor_v2` | ✅ corrigido em 27/07 (`15cac501`) |
| `rdo_percentual_livre` | ✅ corrigido em 27/07 (`15cac501`) |

**Nenhuma instância restante.** O padrão nasceu das duas flags mais novas —
as duas escritas depois que o costume de guardar antes já existia nas
antigas, e sem ninguém conferir contra elas.

### P6 — duas implementações da mesma convenção

| Instância | Situação |
|---|---|
| Duas ordenações de foto numerada (`(len, nome)` × chave numérica) | ✅ unificada em 27/07 (`991e0475`) |
| Filtro do cronograma interno repetido em 6 lugares | ✅ virou `TarefaCronograma.do_cronograma_interno` |
| **Duas definições de "% da obra"**: média simples (`gerar_medicao`) × ponderada por duração (`calcular_progresso_geral_obra_v2`) | ⏳ **em aberto — decisão de negócio** |

A terceira é a que importa e **não é minha para decidir**: a média simples é
a que gera `valor_medido`. Unificar muda dinheiro em obras com tarefas de
durações muito diferentes. Fica registrada como pergunta ao dono, não como
defeito a corrigir.

---

# Fecho da revisão — 27/07

| Varredura | Padrão | Achados | Corrigidos |
|---|---|---|---|
| 1 | P1 escopo esquecido | 5 (1 🔴) | 5 |
| 2 | P5 commit alheio | 1 🟠 | 1 |
| 3 | P2 premissa desmentida | 1 🟠 | 1 |
| 4 | P4 silêncio | 1 🟡 | 1 |
| 5 | P3 guard tardio | 0 restantes | (2 antes) |
| 6 | P6 convenção duplicada | 2 + 1 em aberto | 2 |

**Toda correção tem teste que prova o defeito** — cada uma foi verificada
revertendo o fix e confirmando a falha. Um teste chegou a passar com o
defeito de volta (o de atomicidade, que comparava `count()` em vez de
identidade) e foi corrigido.

## O que a revisão sugere sobre o repositório

Os defeitos não estavam espalhados ao acaso: **quatro dos oito nasceram de
uma convenção que o código não consegue lembrar sozinho** — filtrar
`is_cliente`, guardar antes de gravar, avisar em vez de descartar,
sincronizar depois do commit. A correção pontual resolve a instância; o que
impede a volta é mover a convenção para um lugar onde esquecê-la exija
esforço. Foi o que `do_cronograma_interno` fez com o P1.

Os outros quatro nasceram de **afirmar sem medir**. A defesa aqui não é
código: é o hábito de tratar toda frase de continuidade ("é preservado", "é
byte-idêntico", "o dual-write mantém") como hipótese até que uma query diga
o contrário. Duas dessas frases eram minhas.
