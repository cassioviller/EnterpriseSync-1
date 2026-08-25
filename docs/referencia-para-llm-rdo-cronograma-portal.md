# RDO, Cronograma e Portal do Cliente — referência funcional de um sistema em produção

> **Como ler este documento.** Ele descreve, em detalhe, como três módulos de um
> sistema de gestão de obras em produção (SIGE) funcionam e se integram: o RDO
> (Relatório Diário de Obra), o Cronograma e o Portal do Cliente. Ele foi
> escrito para servir de **referência e fonte de ideias** para um sistema
> similar que já está em construção — **não é um gabarito para seguir à
> risca**. Cada seção mostra o que existe, por que existe (muitas decisões aqui
> nasceram de bugs reais em produção) e, ao final, o que vale considerar como
> melhoria no seu sistema. Adote o que fizer sentido para o seu contexto,
> adapte nomes e simplifique onde seu produto não precisa da complexidade.

---

## 1. Visão geral — os três módulos e o fluxo entre eles

```
                    (aponta produção diária)
        RDO ────────────────────────────────► CRONOGRAMA
         │        percentual/quantidade         │
         │        por tarefa, por dia           │  progresso físico
         │                                      │  alimenta medição,
         │  (vitrine + "ciência")               │  curva S e EVM
         ▼                                      ▼
     PORTAL DO CLIENTE ◄──────────── cópia congelada do cronograma
     (token público por obra)        + progresso real "por cima"
```

Papéis:

- **RDO** — o documento diário da obra: quem trabalhou, o que foi executado,
  equipamentos, ocorrências, clima, fotos. É a **fonte primária do avanço
  físico**: cada atividade apontada no RDO vira uma linha de produção diária
  ligada a uma tarefa do cronograma.
- **Cronograma** — o plano da obra: hierarquia de tarefas (fases → grupos →
  folhas), dependências, datas, baseline, curva S e EVM. **Consome** o que o
  RDO aponta e devolve percentuais agregados (por tarefa, por obra).
- **Portal do Cliente** — a vitrine externa: o cliente acompanha a obra por um
  link com token (sem login), vê cronograma, RDOs com fotos, medições, e
  interage em pontos específicos (aprovar compras, escolher fornecedor em
  mapa de concorrência, dar "ciência" em RDOs com assinatura eletrônica leve).

A ideia central que amarra os três: **o dado nasce uma vez (no RDO), o
cronograma o agrega, e o portal o exibe** — cada módulo com sua própria regra
de visibilidade e imutabilidade.

---

## 2. Módulo RDO

### 2.1 Modelo de dados (entidades e papéis)

| Entidade | Papel |
|---|---|
| `RDO` | Cabeçalho do dia: obra, data, número, clima (condições, temperatura, umidade, vento, precipitação), local (Campo/Oficina), comentário geral, **estado do ciclo de vida** |
| `RDOServicoSubatividade` | Uma linha por subatividade executada no dia: % anterior, % atual, incremento do dia, observações técnicas, ordem de execução; snapshots de meta de produtividade e unidade |
| `RDOMaoObra` | Uma linha por (funcionário × atividade): função exercida, horas trabalhadas, produtividade calculada, peso de distribuição de horas |
| `RDOEquipamento` | Equipamentos usados: nome, quantidade, horas de uso, estado de conservação |
| `RDOOcorrencia` | Ocorrências do dia: tipo (Problema/Observação/Melhoria/Segurança), severidade, descrição, ação corretiva, responsável, prazo, status de resolução |
| `RDOFoto` | Fotos com descrição, versões otimizada/thumbnail, ordem; limite por foto (5 MB) e por RDO (20 fotos) |
| `RDOApontamentoCronograma` | **A ponte com o cronograma**: produção diária de UMA tarefa (quantidade do dia, acumulado, % realizado, % planejado na data) |
| `RDOSubempreitadaApontamento` | Produção de equipes terceirizadas na mesma tarefa: nº de pessoas, horas, quantidade produzida, homem-hora calculado automaticamente |
| `RDOCustoDiario` | Snapshot **imutável** do custo de mão de obra do dia por funcionário (protege contra mudança retroativa de salário e dupla contagem) |
| `RDOTransicaoEstado` | Trilha de auditoria do ciclo de vida: estado anterior → novo, quem, quando, IP, motivo |
| `RDOAssinatura` | Assinatura eletrônica: papel (executor/gestor/cliente), hash SHA-256 do conteúdo, IP, carimbo do servidor |

Regras de unicidade que valem a pena conhecer:

- **1 RDO por (obra, data)** — validado na aplicação; ao tentar criar um
  segundo, o sistema redireciona para editar o existente.
- Número do RDO no formato `RDO-{empresa}-{ano}-{seq}` com retry em colisão.
- Assinatura: **um** assinante interno por papel por RDO, mas **N** assinaturas
  de cliente distintas por RDO (implementado com índices únicos parciais).

### 2.2 Ciclo de vida do RDO (máquina de estados explícita)

```
rascunho ──(Submeter)──► preenchido ──(Assinar)──► assinado ──► aprovado
   ▲                          │                        │
   └──────(Reabrir)───────────┘                        └──► retificado
                                                 aprovado ──► retificado
```

- **rascunho** — edição livre; **não lança custo nenhum**.
- **preenchido** — submetido; é AQUI que os custos de mão de obra são lançados
  no financeiro (via evento `rdo_finalizado`), e um webhook `rdo_publicado` é
  emitido. Ainda pode voltar a rascunho (com motivo obrigatório).
- **assinado** — autoria registrada; **imutável** dali em diante.
- **aprovado** — aceite do gestor; imutável e terminal.
- **retificado** — substituído por outro RDO; terminal.

Três decisões de arquitetura que se pagaram:

1. **Imutabilidade por listener de sessão do ORM, não por checagem em cada
   rota.** Um único guard `before_flush` barra qualquer insert/update/delete
   no RDO ou em qualquer filho quando o estado persistido é imutável. Motivo
   documentado no código: "um ponto só é auditável; oito não são". As tabelas
   de transição e assinatura ficam de fora (são o próprio registro do ato).
2. **Rascunho não lança custo.** Houve bug real: salvar sem submeter já
   lançava custo (R$ 277 duplicados em produção). A correção virou teste de
   guarda permanente. Separar "documento salvo" de "documento com efeito
   financeiro" é uma fronteira que vale desenhar cedo.
3. **Retificação em vez de edição do imutável.** O RDO é um documento de
   DATA: corrigir um RDO assinado = emitir OUTRO RDO da mesma data que diz o
   que o primeiro deveria ter dito, com o original preservado e marcado
   `retificado`, e motivo obrigatório. O retificador copia cabeçalho,
   atividades, mão de obra, equipamentos e ocorrências — mas **não copia
   fotos** (custo de armazenamento) **nem apontamentos de cronograma** (são
   acumulativos; copiar somaria produção duas vezes — quem retifica reaponta).
   Os custos do original são estornados antes (senão o Realizado da obra
   dobra — foi medido: R$ 124 viravam R$ 248).

Há também um **"Duplicar"** distinto de retificar: cria um RDO novo com a data
de hoje usando o anterior como ponto de partida (copia só clima e comentário),
sem substituir nada e sem emitir eventos.

### 2.3 Autorização (separação fina de papéis)

- `pode_apontar_na_obra` (gestor OU apontador): criar, submeter, **assinar**.
- `pode_editar_obra` (só gestor/admin): **aprovar, reabrir, retificar**.

Ou seja: um apontador pode assinar o próprio trabalho, mas nunca aprová-lo —
dupla checagem deliberada. E o acesso cross-tenant devolve **404, não 403**:
nem a existência do RDO de outra empresa vaza.

### 2.4 Assinatura eletrônica (leve, com trilha probatória)

Escopo jurídico deliberado: **autoria + integridade** (assinatura eletrônica
simples, estilo MP 2.200-2/2001 no Brasil), não certificado digital — com o
campo `provedor` já previsto para plugar um provedor externo depois sem
migração.

- `hash_conteudo` — SHA-256 de um **payload canônico** do RDO: cobre só o que
  a pessoa declarou (exclui bytes de foto, metadados de sistema e campos
  derivados). Detalhe fino: as coleções são ordenadas pela **linha inteira**,
  não por chave parcial — duas linhas empatadas em chave mas com conteúdo
  diferente geravam hash instável conforme a ordem devolvida pelo banco, e um
  RDO intacto "acusava" adulteração.
- Carimbo de hora sempre do **servidor**; IP sempre de `request.remote_addr`
  com ProxyFix — **nunca** lendo `X-Forwarded-For` na mão (o assinante poderia
  forjar o próprio IP registrado como prova).
- Assinar exige identidade real vinculada (usuário ↔ funcionário); sem
  vínculo, o sistema **recusa** em vez de inventar autoria (antes, criava um
  funcionário fantasma "Administrador Sistema" — heurística removida).

### 2.5 Produtividade

- Catálogo de subatividades (`SubatividadeMestre`) com unidade de medida e
  **meta de produtividade**; ao apontar, a meta e a unidade são copiadas como
  **snapshot** na linha do RDO — mudar a meta no catálogo depois não
  reinterpreta o histórico.
- Produtividade real = quantidade produzida / horas totais da equipe da
  subatividade; índice = real / meta. É taxa de **equipe**, a mesma para todos
  os funcionários da subatividade.
- Distribuição de horas com **peso** opcional por linha: se qualquer linha do
  funcionário no dia tiver peso, a jornada-base é distribuída
  proporcionalmente entre todas as linhas dele.
- Subempreitada: várias equipes terceirizadas podem apontar na mesma tarefa no
  mesmo RDO; homem-hora é calculado por listener, nunca digitado.

### 2.6 Outros recursos do módulo

- **Listagem "obra-first"**: sem obra selecionada, mostra cards de obras
  ativas com contagem de RDOs e data do último; com obra, lista paginada.
  O progresso mostrado em cada linha é o acumulado **até a data daquela
  linha** (houve bug: cache por obra sem teto de data fazia toda linha
  mostrar o número de hoje).
- **PDF do RDO** (layout A4 com KPI de progresso, omissão de seções vazias).
- **Exportação em lote** (zip de RDOs da obra) e **carga por JSON** com
  Prévia/Aplicar — a carga administrativa **pula** RDOs
  assinados/aprovados/retificados (respeita a imutabilidade mesmo em lote).
- **Anti-dupla-contagem com ponto eletrônico**: o custo do dia só é abatido se
  existe ponto **produtivo** (horas > 0 e obra preenchida) — antes, a mera
  existência da linha de ponto (mesmo falta/feriado) fazia RDO e ponto se
  absterem citando um ao outro, e o dia ficava sem custo nenhum.
- Hora extra **não existe** no RDO — vive só no ponto eletrônico/folha.
  Decisão deliberada de fonte única.

### 2.7 Ideias de melhoria que este módulo sugere para um sistema similar

- Separe **estado do documento** (rascunho→…→aprovado) de **efeitos
  financeiros** (lançados só na submissão) desde o início.
- Prefira **retificação com trilha** a permitir editar documento assinado.
- Implemente imutabilidade em **um ponto central** (guard no ORM/camada de
  persistência), não checagem espalhada por rota.
- Se houver assinatura, defina um **hash canônico estável** (ordenação
  determinística, só campos declarados) e capture IP/hora de forma não
  forjável.
- Snapshots de metas/preços na linha histórica, nunca referência viva.
- Cuidado com fotos em banco (base64): aqui, 16 GB de TOAST com 28 mil fotos
  duplicadas motivaram migração para disco + colunas deferred. Planeje
  armazenamento de mídia fora do banco desde o começo.

---

## 3. Módulo Cronograma

### 3.1 Modelo de dados

| Entidade | Papel |
|---|---|
| `TarefaCronograma` | Tabela central: hierarquia por `tarefa_pai_id` (fases → grupos → folhas), ordem entre irmãos, datas (início/fim/duração), quantitativo físico (quantidade + unidade), `percentual_concluido` persistido, responsável (empresa/terceiros), marco, **arquivamento lógico** (`ativa=False`, nunca delete), flag `is_cliente` (a mesma tabela guarda o cronograma interno E a cópia do cliente) |
| `TarefaVinculo` | Dependências tipadas N:N no vocabulário MS Project: FS/SS/FF/SF (aqui TI/II/TT/IT) com lag em dias úteis (pode ser negativo) |
| `CronogramaBaseline` + itens | Linha de base: congela datas de cada tarefa + **BAC (orçamento) congelado junto**; revisões numeradas sequenciais por obra, com motivo ("Aditivo 01"); só UMA ativa por obra (índice único parcial como rede de segurança) |
| `RDOApontamentoCronograma` | Produção diária por tarefa (ver módulo RDO) |
| `CronogramaImportacao` / `Versao` / `TarefaSnapshot` / `Mapeamento` | Pipeline de importação de MS Project (.mpp/.xml): estados `recebido → parseado → normalizado → reconciliado → aguardando_revisao → aplicado`, snapshot integral de cada tarefa em cada versão, reconciliação com score de confiança e tipos de correspondência (exata, provável, nova, removida, renomeada, movida, dividida, fundida…) |
| `CronogramaAcao` | Pilha de desfazer/refazer com **diff por campo** (não a linha inteira) |
| `CronogramaTemplate` + itens | Modelos reutilizáveis de conjunto de tarefas ("Fundação", "Fachada") aplicáveis a qualquer obra |
| `ItemMedicaoCronogramaTarefa` | Liga item de medição comercial a N tarefas do cronograma com pesos (normalizados) |

### 3.2 Motor de agendamento

Existem dois motores atrás de feature flag (transição legado → novo), o que em
si é uma lição de rollout. O motor **novo** é o interessante como referência:

- **Puro** (sem acesso a banco): recebe tarefas + vínculos, devolve datas.
- Só **folhas** entram no grafo; pais são roll-up (mín/máx/duração).
- Passe para frente com as 4 restrições clássicas:
  - FS: `início_sucessora ≥ fim_predecessora + 1 + lag`
  - SS: `início_s ≥ início_p + lag`
  - FF: `fim_s ≥ fim_p + lag`
  - SF: `fim_s ≥ início_p + lag`
- Passe para trás: folga total em dias úteis; `crítica = (folga == 0)`;
  pai herda `folga = min(filhas)` e é crítico se qualquer filha for.
- **Âncoras**: tarefa que já começou (tem apontamento de RDO) nunca tem as
  datas movidas pelo recálculo — mas as datas efetivas dela alimentam as
  restrições das sucessoras. Isso evita o motor "reescrever o passado".
- Ciclo de dependências → erro claro **nomeando as tarefas do ciclo** (o
  motor legado apenas "forçava processamento" silenciosamente — pior).
- Persistência separada do cálculo: grava só o que mudou.

### 3.3 Percentual de avanço — as fórmulas (o coração do módulo)

Regra de ouro do código-fonte: **"views nunca implementam fórmula"** — todas
as fórmulas de progresso vivem num único módulo, consumido por telas, PDF,
portal e medição. Tabela normativa:

| Caso | Peso na agregação | Planejado | Realizado |
|---|---|---|---|
| Folha quantitativa (todas com qtd e MESMA unidade) | quantidade | linear por dias úteis | Σ qtd_dia / total |
| Folha sem quantitativo (ou mix de unidades) | duração (piso 1) | linear por dias úteis | último acumulado % |
| Pai/resumo | excluído (é rollup das filhas) | rollup | rollup |
| Marco (ou duração 0) | 0 | degrau na data de início | binário 0/100 |
| Responsável = terceiros | igual às demais | linear | **manual** (nunca sobrescrito pelo RDO) |
| Sem datas/duração | duração/1 | `None` ("sem plano"), nunca 0 | normal |
| Arquivada | 0 no presente/futuro | — | mantido para datas anteriores ao arquivamento |

Pontos finos que evitaram bugs reais:

- **Nunca somar m + un + dias**: peso por quantidade só quando TODAS as
  folhas têm quantidade e a mesma unidade; senão cai para duração; senão
  média simples.
- **`None` ≠ 0%** no planejado: `None` = "tarefa sem plano calculável" e a UI
  mostra "—"; 0% pareceria atraso.
- Rollup dos pais processado por **profundidade real na árvore** (mais fundo
  primeiro), não pelo campo `ordem` — a ordem de exibição não é ordem
  topológica, e confundi-las fazia o pai calcular antes do subgrupo e ler 0.
- **Modo de apontamento por tarefa** (quantidade × percentual) é uma escolha
  explícita, resolvida em cascata: marco (sempre %) → flag do tenant
  "percentual livre" → escolha explícita da tarefa → dedução legada. E o
  histórico manda: **uma** linha apontada em percentual torna a tarefa
  percentual para sempre (cadastrar quantidade depois reinterpretaria
  retroativamente todas as linhas antigas — houve caso medido: tarefa em 80%
  passava a marcar 40% ou 100% conforme o total cadastrado). O sistema
  bloqueia cadastrar quantitativo em tarefa com histórico percentual.
- Retrocesso de percentual exige confirmação explícita + justificativa;
  sobre-execução (>100%) idem; marco só aceita 0 ou 100.
- **Duas fontes de percentual coexistem** e o sistema é honesto sobre isso: a
  coluna persistida (alimentada por RDO, import de .mpp e edição direta) e a
  derivação ao vivo dos apontamentos de RDO (monotônica, tarefa sem
  apontamento = 0). A medição/EVM usa a persistida (senão obra que avança por
  import teria medição zerada); o "progresso ao vivo" usa a derivada.
  Unificar as duas é dívida declarada. *Se o seu sistema puder nascer com uma
  fonte única, melhor.*
- Existe uma **decisão de produto documentada como pendente**: rollup por
  média ponderada por duração vs. média simples por item (inserir 5 tarefas
  de 1 dia numa fase de 300 dias em 98% → 96% ponderado vs. ~80% simples).
  A troca cascateia em curva S, EVM e medição. Lição: **a fórmula de rollup é
  uma decisão de produto, não de engenharia** — exponha-a cedo ao dono do
  produto.

### 3.4 Baseline, curva S e EVM

- **Baseline**: congela datas + BAC num ato explícito, com revisão numerada e
  motivo. Editar a tarefa depois muda a tarefa, nunca a baseline — é isso que
  torna o desvio honesto. Comparação entre duas revisões lista só as tarefas
  cujo fim mudou.
- **BAC congelado junto com as datas**: comparar custo real contra orçamento
  VIVO esvazia o EVM (revisar o orçamento para cima "melhora" o CPI sem nada
  mudar na obra).
- **Replanejamento da curva**: quando as datas mudam (edição ou nova versão
  importada), o sistema recalcula o `% planejado` de TODOS os apontamentos
  históricos com as datas vigentes — e **nunca toca o realizado**.
- **Curva S** física e financeira (série mensal acumulada), painel com
  previsto × realizado por etapa, fluxo de caixa e export Excel.
- **EVM** composto de peças que já existem (nada reinventado):
  - BAC = baseline ativa (ou orçamento vivo como fallback sinalizado);
  - PV = desembolso previsto acumulado até o mês corrente;
  - AC = custo realizado;
  - **EV = BAC × progresso físico** (nunca financeiro — medir por dinheiro
    gasto mede esforço, não entrega, e faz o SPI mentir exatamente quando a
    obra atrasa gastando);
  - CV, SV, CPI, SPI, EAC, ETC, VAC derivados; divisões por zero devolvem
    `None`/"sem dados", nunca 0 (0 significaria desempenho nulo, que é outra
    afirmação).
  - Armadilha documentada: BAC **não é** valor de contrato (venda) — usar
    venda daria CPI sempre favorável.

### 3.5 Importação de MS Project e versionamento

- Upload de .xml/.mpp entra num pipeline com estados e trilha de eventos;
  cada versão guarda snapshot integral de cada tarefa (permite diff e
  rollback).
- **Reconciliação** entre a versão importada e o cronograma vivo: casa
  tarefas por UID/WBS/fingerprint, classifica cada uma (exata, provável,
  nova, removida, renomeada, movida, datas alteradas, dividida, fundida,
  ambígua) com score, e o gestor revisa as ambíguas antes de aplicar.
- Tarefa removida por reimportação é **arquivada**, nunca deletada — os
  apontamentos de RDO ligados a ela não podem ficar órfãos.
- Avanço importado (`% do Project`) não é sobrescrito pelo primeiro RDO de
  presença: se não há apontamento nem produção, o rollup **não escreve nada**.

### 3.6 Undo/redo

Pilha por (obra, usuário, modo) com payload em **diff por campo** —
deliberadamente não a linha inteira: um Ctrl+Z não pode restaurar um
percentual antigo por cima de um apontamento de RDO que aconteceu no meio.
Exclusão com editor novo é lógica (arquivar), então desfazer "excluir"
restaura tarefa + vínculos + apontamentos. Pilha podada (50 ações); ação nova
descarta os redo pendentes.

### 3.7 Ideias de melhoria que este módulo sugere

- Motor de datas **puro e testável** separado da persistência.
- Âncora para tarefa iniciada: recálculo nunca reescreve o passado.
- Fórmulas de progresso em **módulo único** consumido por todas as telas.
- `None` ≠ 0 em percentual planejado; unidades incompatíveis nunca somadas.
- Baseline com revisão numerada + motivo + orçamento congelado junto.
- EV sempre sobre progresso físico; "sem dados" ≠ "zero".
- Importação com reconciliação revisável e arquivamento lógico.
- Modo de apontamento como escolha explícita da tarefa, com guarda de
  histórico contra reinterpretação retroativa.

---

## 4. Portal do Cliente

### 4.1 Modelo de acesso

- **Token público por obra, sem login**: `token_cliente` (32 bytes urlsafe)
  na obra; o link é `/portal/obra/<token>`. Navegar é anônimo por construção.
- **Expiração longa deliberada** (180 dias, recarimbada ao reativar o
  portal): token curto gera chamado de suporte e a equipe acaba desligando a
  expiração — pior. Token expirado/inexistente → 404.
- Toggle `portal_ativo` por obra: desativado, as rotas de leitura mostram uma
  página "portal pausado" (com o mínimo de informação); as rotas de **ação**
  (POST) devolvem 404 — leitura degrada com mensagem, mutação não.
- **Reativar não troca o link** (mesmo token, validade nova); revogação real
  de um link vazado exige zerar o token. *Ideia de melhoria: um botão
  explícito "gerar novo link" resolveria isso melhor do que aqui.*
- Todo evento que muta estado pelo portal (aprovar/recusar compra, upload,
  seleção de mapa, ciência) vai para uma tabela de auditoria
  (`PortalAcessoEvento`: ação, alvo, IP, user-agent, JSON de detalhes) — e o
  registro de auditoria **nunca levanta exceção** ("uma falha de auditoria
  não pode impedir o cliente de aprovar; mas o log da falha fica").

### 4.2 O que o cliente vê (tela única com seções)

1. **Hero**: anel de progresso geral da obra, status, datas, endereço, e 4
   métricas (etapas, total de RDOs, medições, dias de obra).
2. **Cronograma**: árvore hierárquica colapsável (HTML `<details>`, sem JS),
   cada nó com período e barra de % colorida. É uma **fotografia** do
   cronograma interno (ver §5.2).
3. **Compras**: pendentes de aprovação (fornecedor, NF, valor, PIX) com
   botões Aprovar/Recusar; resolvidas com status, upload de comprovante de
   pagamento (quando aprovada) e link para vê-lo.
4. **Medições**: número, período, % executado, valores (medido / entrada
   abatida / a faturar), status, extrato em PDF, e status da conta a receber
   vinculada (pago/vencido…).
5. **Mapa de concorrência**: tabela item × fornecedor com cotações, destaque
   de menor preço (⭐) e menor prazo (⚡), seleção por item (ou o fornecedor
   inteiro de uma vez), e relatório final em PDF.
6. **RDOs**: lista paginada com thumbnail da 1ª foto, data, resumo, contador
   de fotos e placar de ciência ("2/3"); detalhe completo com clima,
   atividades agrupadas **pelo caminho na árvore do cronograma**, mão de obra,
   equipamentos, ocorrências, fotos com zoom.

### 4.3 O que o cliente pode FAZER

- **Aprovar/recusar compra** — idempotente; decisão não é reversível pelo
  portal (recusado não vira aprovado com outro clique — houve incidente real
  de compra recusada voltando a aprovada e gerando custo). Sob a flag de
  "governança de compras", o clique do cliente vale como **ciência** (o
  efeito financeiro sai da cadeia interna de alçadas); sem a flag, o clique
  gera custo/baixa direto — dois regimes atrás de flag de tenant.
- **Enviar comprovante** de pagamento (imagem/PDF, 5 MB, nome de arquivo
  aleatório — nunca o original).
- **Selecionar fornecedores** no mapa de concorrência (validação de que
  item/fornecedor pertencem ao mapa; exige cobrir todos os itens cotados).
- **Dar ciência em RDO** — o recurso mais elaborado (ver §4.4).
- Baixar PDFs: extrato de medição, relatório de compra, recibo de ciência.

### 4.4 "Ciência" de RDO — assinatura leve do lado do cliente

Única parte do portal com identidade nomeada, e desenhada **sem sessão de
login**:

- A construtora cadastra **signatários** por obra (nome, e-mail, cargo,
  senha) — deliberadamente numa tabela separada da de usuários internos, para
  que um signatário jamais herde, por bug, autorização interna (o
  login-manager interno nem conhece essa tabela).
- A senha é conferida **no mesmo POST que registra a ciência** — não há
  cookie de sessão de login; "a assinatura repousa sobre a credencial, não
  sobre um cookie, e não existe janela entre autenticar e assinar".
- A ciência grava uma assinatura com papel `cliente` na **mesma tabela** e
  com o **mesmo hash canônico** das assinaturas internas — se o RDO mudar
  depois, o placar recalcula o hash e marca a ciência como "alterada" na UI.
- Segurança operacional pensada para canteiro de obra:
  - senha temporária de 72 h com alfabeto **sem 0/O/1/l/I** (é ditada por
    telefone);
  - trava após 10 falhas, destravada pela construtora;
  - rate-limit por **IP + signatário** (não IP puro — a equipe inteira do
    cliente costuma estar atrás do mesmo IP na obra);
  - `autenticar()` confere a senha ANTES de revelar trava/expiração (a ordem
    inversa deixava enumerar quem estava travado);
  - "esqueci a senha" responde mensagem genérica sempre (sem oráculo de quem
    existe) e apenas marca o pedido para a construtora atender;
  - duplo clique/duas abas: a corrida é resolvida pelo índice único do banco
    e a segunda requisição é tratada como sucesso, não erro.
- Após assinar, um "passe" de 15 minutos na sessão permite rever o
  comprovante e baixar o recibo PDF sem reautenticar — mas toda rota que o lê
  reconfere a assinatura; o passe não é identidade.
- Decisão de produto interessante: o cliente **pode dar ciência num RDO que a
  construtora ainda não assinou internamente** (a exigência original travava
  a tela) — o único bloqueio é RDO retificado (o documento vigente é outro).
  A troca declarada: perde-se a garantia prévia de imutabilidade, mantém-se a
  prova (o hash detecta alteração posterior).

### 4.5 O que é escondido de propósito

- **Custos internos**: só o valor total da compra aparece; nunca markup,
  margem, custo unitário, plano de contas.
- **Marca da construtora** no portal de obra: nem logo nem nome — a
  identificação que importa para o cliente é a OBRA (decisão documentada em
  comentário no template). Em contraste, o **portal de propostas** (produto
  irmão, pré-obra, com token próprio) é white-label completo com logo e
  cores. *Para o seu sistema: decida conscientemente o branding de cada
  superfície externa.*
- **Tarefas arquivadas** do cronograma: filtradas em todo ponto de leitura.
- **Compras internas** (não destinadas ao cliente): nunca aparecem — houve
  vazamento real de compra interna aprovada aparecendo na lista, corrigido
  endurecendo o filtro por tipo.
- **IP/hash/user-agent** da ciência: só o próprio signatário vê, e só na
  janela do passe; o público vê apenas *que* houve ciência e quando.
- Arquivos servidos **só por basename validado contra diretórios fixos** —
  substituiu uma rota antiga que servia o volume de uploads inteiro por path
  adivinhável.
- Cross-tenant e id fora da obra: **404, nunca 403** ("o que o portal não
  oferece não existe; 403 confirmaria que o id pertence à obra").

### 4.6 Ideias de melhoria que este módulo sugere

- Token por obra com expiração longa + auditoria de ações + 404 para tudo
  que estiver fora do escopo do token.
- Assinatura do cliente sem conta/login completo: credencial simples, no ato,
  com trilha probatória (hash, IP real, carimbo do servidor).
- Placar de ciência por documento, com detecção de alteração posterior.
- Idempotência de cliques anônimos e irreversibilidade de decisões pelo
  portal (reversão só por canal interno).
- Paginação que **mostra o corte** ("os 20 mais recentes de 42") — o total
  vem de um COUNT separado, nunca do tamanho da página.
- Rate-limit composto (IP + identidade alvo) quando muitos usuários legítimos
  compartilham IP.

---

## 5. Como os três módulos se integram

### 5.1 RDO → Cronograma (avanço físico)

- Cada atividade apontada no RDO grava uma linha de produção diária ligada à
  tarefa do cronograma (quantidade OU percentual, conforme o modo da tarefa),
  com **dupla informação**: o valor do dia e o acumulado, mais o `% planejado
  na data` (para comparar realizado × planejado por dia).
- Um **serviço único de apontamento** é usado tanto pela tela do RDO quanto
  pela tela do cronograma — a fórmula foi extraída depois de viver duplicada
  nos dois lugares (e divergir). *Lição: a ponte entre dois módulos merece um
  serviço próprio, com os dois lados como meros callers.*
- Após cada lote de apontamentos, o rollup atualiza o `%` da tarefa e dos
  pais; a produção de subempreitada soma-se à da empresa nesse único ponto.
- Editar/apagar um apontamento no meio do histórico dispara **recomputação em
  cadeia** dos derivados a partir daquela data.
- Direção inversa (cronograma → RDO) é mínima de propósito: importar um
  cronograma pode criar entradas no **catálogo** de subatividades (marcadas
  "criada via cronograma, precisa revisão"), mas nunca cria RDOs.

### 5.2 Cronograma → Portal (fotografia + verdade ao vivo por cima)

O cliente não vê o cronograma interno ao vivo — vê uma **cópia congelada**
(`is_cliente=True`, na mesma tabela), gerada por um clique interno
("gerar cronograma do cliente" = apaga a cópia anterior e clona as tarefas
vivas do interno, preservando hierarquia e dependências com remapeamento de
IDs). Motivo: a construtora controla QUANDO o cliente passa a ver uma
reestruturação do plano.

Só que percentual congelado envelhece. A solução em produção: na renderização
do portal, um "sync de leitura" casa cada folha da cópia com a tarefa interna
**pelo caminho completo na árvore** ("Fechamento › Térreo › Plaqueamento") e
exibe o % real da interna por cima do congelado. Fallback por nome apenas
quando o nome é único na obra — casar por nome puro colidia em obras com EAP
repetida por pavimento ("Térreo" 6×) e mostrava o percentual de um andar no
outro (incidente real, com números documentados).

*Para um sistema novo, considere resolver isso por design: um snapshot
versionado com id estável de tarefa (aí o casamento é por id, não por
caminho), ou visibilidade ao vivo com campo "publicado".*

### 5.3 RDO → Portal (vitrine + ciência)

- A lista e o detalhe do RDO no portal são leitura direta, com as atividades
  agrupadas pelo caminho no cronograma (mesmo agrupador da tela interna).
- RDOs importados/legados sem linhas de atividade têm **fallback**: a tabela
  de atividades é derivada dos apontamentos de cronograma do próprio RDO.
- O placar de ciência da listagem usa uma **versão em lote** (2 queries para
  N RDOs) — a versão por RDO custaria 2×N (padrão N+1).

### 5.4 Cronograma → Dinheiro (medição, curva S, EVM)

- Medição comercial: itens do contrato ligados a N tarefas com pesos
  normalizados; % do item = média ponderada do % das tarefas vinculadas;
  valor medido = contrato × %.
- A medição usa o percentual **persistido** (para não zerar obras que avançam
  por import/edição, sem RDO); o progresso "ao vivo" do portal e do header
  usa a derivação por apontamentos. As duas fontes e o porquê estão em §3.3.
- EVM e curva S consomem baseline + físico-financeiro (§3.4).

---

## 6. Temas transversais que valem copiar (qualquer módulo)

1. **Multi-tenant em toda query** — todas as tabelas carregam o id da
   empresa, e todo acesso fora do escopo devolve **404** (nunca 403, nunca
   mensagem diferente para "existe mas não é seu" — isso vira oráculo de
   enumeração; aqui até a *mensagem* de erro foi unificada depois de um
   code review achar a diferença).
2. **Arquivamento lógico em vez de delete** para tudo que tem histórico
   pendurado (tarefas com apontamentos, RDOs com custos).
3. **Snapshot vs. referência viva**: metas, unidades, totais e orçamentos são
   copiados para a linha histórica no momento do fato.
4. **Eventos com efeito financeiro num ponto só**, disparados por transição
   de estado (não por "salvar").
5. **Trilha de auditoria como tabela**, não como log: transições de estado,
   ações do portal, eventos de importação — com IP, autor, motivo, JSON.
6. **Flags de tenant para rollout** de motor novo/comportamento novo, com os
   dois regimes coexistindo temporariamente e telemetria (`[LEGACY-*]` nos
   logs) para saber quando o legado morreu de verdade.
7. **Batch loading consciente**: listagens que derivam números por linha
   (progresso, placar) têm versão em lote com número fixo de queries — e
   testes que **contam queries** e travam que a contagem não cresce com o
   número de linhas.
8. **Idempotência via constraint de banco** (índices únicos parciais) com a
   corrida tratada como sucesso, em vez de locks aplicativos.
9. **Decisões de produto documentadas no código** (comentários com o porquê,
   a data e o incidente que motivou) — metade deste documento só foi possível
   porque o código conta a própria história.

---

## 7. Armadilhas reais (para o seu sistema evitar por design)

Todas aconteceram de verdade neste sistema e custaram correção:

- Salvar rascunho lançando custo → custo duplicado em produção.
- Retificação sem estorno por-filho → Realizado da obra dobrado.
- Cache de progresso por obra **sem teto de data** → toda linha histórica
  mostrando o número de hoje.
- Casamento de tarefas por **nome puro** → percentuais trocados entre
  pavimentos homônimos.
- Clone do cronograma-cliente sem filtrar arquivadas → tarefas fantasma no
  portal.
- Média misturando unidades (m + un + dias) e rollup em ordem errada da
  árvore → percentuais absurdos.
- Cadastrar quantitativo em tarefa com histórico percentual → passado
  reinterpretado (80% virando 40%).
- Hash de assinatura com ordenação instável → documento intacto acusando
  adulteração.
- IP lido de `X-Forwarded-For` cru → prova forjável pelo próprio assinante.
- Rota servindo uploads por path da URL → leitura arbitrária do volume.
- Compra interna vazando no portal por filtro frouxo de tipo.
- Reverter decisão do cliente por POST anônimo → compra recusada voltando a
  aprovada e gerando custo.
- Duas implementações da mesma fórmula em views diferentes → divergência
  silenciosa entre telas (a cura foi o serviço único).
- Fotos em base64 no banco → 16 GB de TOAST duplicando o que já estava em
  disco.

---

*Documento gerado em 23/08/2026 a partir de leitura direta do código-fonte do
sistema de referência (modelos, rotas, serviços, templates e testes). Os
nomes de entidades foram mantidos para dar concretude, mas são detalhes de
implementação — o valor está nos contratos, nas regras e nas lições.*
