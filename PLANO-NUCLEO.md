# Plano do núcleo — cronograma e RDO no centro

> Documento vivo. Primeira versão: **2026-07-31**. Última atualização:
> **2026-08-03** (o editor v2 saiu do piloto e foi para o parque inteiro —
> ver o p2 e o Histórico).
>
> **O que é:** a rearquitetura do plano de evolução do SIGE depois de duas
> rodadas de levantamento de 31/07 — a **conferência adversarial** dos achados
> que sustentavam o plano (12 verificadores tentando refutar cada um no código
> vivo) e o **levantamento de conexões** (o tecido de eventos, 8 arestas da
> jornada rastreadas ponta-a-ponta, e a matriz de fluxo de dados).
>
> **Decisão de produto que ordena tudo:** o centro do sistema é o par
> **cronograma ↔ RDO** — a parte aprovada. Todo o resto se ordena pela distância
> até ele: o que o alimenta (montante), o que quebra dentro dele (núcleo), o que
> vive do que ele produz (jusante).
>
> **Fontes:** `docs/estudo-fluxo/conferencia-2026-07-31.json` (12 vereditos com
> evidência `arquivo:linha` viva) e `docs/estudo-fluxo/conexoes-2026-07-31.json`
> (tecido + arestas + matriz + backlog). O diagnóstico de fundo é
> `FLUXO-IDEAL.md` (30/07) e os planos `docs/superpowers/plans/2026-07-21-fase-{6,7,8,9}-*`.
>
> **A regra da casa continua valendo:** nada aqui vira mudança sem spec própria
> em `docs/superpowers/specs/`, seguindo spec → plano → fases atrás de flag.
> A diferença é que agora cada item já foi reconferido no código — os vereditos
> substituem os achados estáticos onde divergem.

---

## 1. O que os levantamentos mudaram, em uma página

**Nenhum dos 12 achados foi refutado** (10 confirmados, 2 parciais). Mas quatro
descobertas mudam o desenho do plano, e o deslocamento geral é de **construir**
para **convergir e reaproveitar**:

### Duas coisas que o plano mandava construir já existem

1. **A Fase 7 como escrita está estruturalmente obsoleta.** O plano é de 21/07;
   o editor de cronograma v2 entregou em **24/07** — três dias depois — o núcleo
   estrutural dela: `TarefaVinculo` com N predecessoras tipadas TI/II/TT/IT e lag
   em dias úteis (`models.py:5952-5978`), motor com passe direto e inverso, folga
   total, `is_critica` e detecção de ciclo (`services/cronograma_scheduler.py:307-457`),
   e `CronogramaBaseline` com itens congelados e coluna Desvio na UI
   (`models.py:6036-6102`). **Implementar o plano de 21/07 criaria uma segunda
   rede de predecessoras e uma segunda baseline.** O que sobra da fase é o EVM
   inteiro — e as três séries dele já existem vivas.

2. **O auto-casamento item de medição ↔ tarefa roda desde abril.** Task #102,
   commit `9e647988` (18/04): a aprovação da proposta já cria
   `ItemMedicaoCronogramaTarefa` pela linhagem, com peso somando 100 por
   construção (`services/cronograma_proposta.py:758-773`). O estudo de 21/07 já
   nasceu desatualizado nesse ponto. E o M07 já havia removido a dupla digitação
   de progresso da UI do RDO ("campo ÚNICO por modo — nunca dois campos",
   `templates/rdo/novo.html:1170`).

### Duas coisas são piores do que o diagnóstico dizia

3. **A dupla contagem de custo é maior.** Não é só ponto × RDO em `CustoObra`:
   atinge também `GestaoCustoFilho` (dedups intra-origem que não se cruzam), o
   ponto emite custo **a cada batida** sem idempotência para horista
   (`ponto_service.py:142-150` → `event_manager.py:487-503`), e a própria
   finalização do RDO roda **dois mecanismos de custo no mesmo request**
   (`views/rdo.py:2145-2153`) cujo dedup não cruza as origens
   `rdo_custo_diario` × `rdo_mao_obra`. Agravante novo: **metade dos caminhos de
   salvar RDO não emite `rdo_finalizado`** — gera custo e **não recalcula a
   medição**.

4. **Nada sai do sistema.** Todo canal externo converge para um único listener —
   o webhook n8n — que sem `N8N_WEBHOOK_URL` vira no-op silencioso **sem
   persistir nada** (`utils/webhook_dispatcher.py:228-231`). Correção ao estudo
   de 30/07: os emissores n8n antes órfãos **ganharam callers** em
   `views/obras.py`; o gargalo migrou do código para a infraestrutura.

### E uma confirmação que vale mais que as outras

**O rollout é a entrega mais barata do mapa.** As três flags do núcleo
(`cronograma_mpp_ativo`, `cronograma_editor_v2`, `rdo_percentual_livre`) têm
script, guard real e runbook — o guard do editor v2 é inclusive mais forte que
o documentado (recusa calendário com sábado/domingo **e** obra datada sem linha
de base, `scripts/flag_cronograma_editor_v2.py:221-263`). Nenhuma depende da
decisão de 27/07 sobre níveis de acesso. **O núcleo aprovado está construído e
invisível.**

> **03/08 — uma das três deixou de ser invisível.** O editor v2 foi ligado em
> todo o parque pela migração 277 (ver o p2). Os dois guards do script
> continuam intactos para quem religar depois; a migração assume o de
> calendário como aviso, deliberadamente, com a linha de base como apólice.
> Restam duas flags no estado "construído e invisível".

---

## 2. Os doze vereditos

| # | Achado conferido | Veredito | O que muda no plano |
|---|---|---|---|
| 1 | `OSC.valor_orcado` herda valor de **venda**, não custo | ✅ confirmado | Pré-requisito duro do EVM. Escopo cresce: `cronograma_fisico_financeiro.py:281-296` soma o valor cru, e há **dois re-syncs** que sobrescreveriam a correção |
| 2 | Vínculo item↔tarefa é manual | 🟡 parcial | **O mecanismo já existe** (Task #102). Sobra reconciliar dois regimes de peso e cobrir o legado |
| 3 | Dupla contagem de custo ponto × RDO | ✅ confirmado | **Ampliado:** duas tabelas, sem idempotência no horista, dois mecanismos no mesmo request |
| 4 | Duas fórmulas de progresso | ✅ confirmado | **São cinco**, em ~20 call-sites. A crítica é `gerar_medicao`, onde a média simples vira dinheiro |
| 5 | Progresso digitado 2× no mesmo formulário | 🟡 parcial | A UI já é entrada única (M07). Sobra a camada de dados e os caminhos backend mortos |
| 6 | Aprovação não semeia `ServicoObraReal` | ✅ confirmado | Confirmado, mais a dualidade `ServicoObra` legada × real que o RDO ainda concilia por fallback |
| 7 | Vazamento entre empresas nos relatórios | ✅ confirmado | Escopo fixo: **10 pontos** (7 relatórios + 3 exportações) e **5 fallbacks** "admin com mais dados" |
| 8 | Presença em três tabelas sem fonte de verdade | ✅ confirmado | **Encolhe:** `AlocacaoEquipe` é modelo órfão — aposentar, não integrar. O sync tem criação quebrada (viola NOT NULL) |
| 9 | Flags do núcleo prontas e desligadas | ✅ confirmado | Rollout puro — mas **não** zero-esforço: é trabalho operacional por tenant. 🔬 **03/08: o editor v2 saiu por migração, não por tenant** — as outras duas seguem manuais |
| 10 | Fases 6 e 9b disputam o dono do `valor_contrato` | ✅ confirmado | Nenhuma começou. A saída está na própria 9b (premissa P1). **4º escritor** omitido do inventário da Fase 6 |
| 11 | Fase 7 obsoleta pelo editor v2 | ✅ confirmado | **Reescrever a fase**, não sequenciá-la |
| 12 | As três séries do EVM já existem | ✅ confirmado | O EVM é aritmética de composição. Falta o `pct_fisico` do painel (hoje `None`) e o join tarefa↔custo |

---

## 3. A matriz de fluxo — 20 conexões entre módulos

Levantada aresta a aresta, com evidência dos dois lados.
**5 automáticas · 8 parciais · 4 manuais · 3 mortas.**

| Estado | Conexão | O que acontece hoje |
|---|---|---|
| 🟢 | Propostas → Obra + Cliente | Evento atômico com dedup, linhagem e rollback — **a espinha de referência** |
| 🟢 | Compras → custo + pagar + estoque | Commit único, contas por parcela, dedup por pedido — a transação modelo |
| 🟢 | RDO → Cronograma | Apontamento com UPSERT e rollup síncrono — **o elo mais sólido do núcleo** |
| 🟢 | Medição → ContaReceber | CR única OBR-MED com upsert idempotente |
| 🟢 | Ponto → custo | Diarista com idempotência dupla — **horista sem chave nenhuma** |
| 🟡 | Propostas → medição/custo/cronograma | Automáticos, mas orçado herda **venda** e o cronograma exige template pré-configurado |
| 🟡 | RDO → custo de mão de obra | Dois mecanismos no mesmo request, dedup que não cruza origens |
| 🟡 | Cronograma → medição comercial | Trilho ponderado convive com a média simples do portal que vira dinheiro |
| 🟡 | Alocação → Ponto | Sync manual, criação quebrada, e sobrescreve a batida real com o plano |
| 🟡 | Folha → contabilidade/custo | Reprocesso duplica sem estorno; encargos nunca chegam à obra |
| 🟡 | Obra → Portal do cliente | Leitura automática e ciência fechada; convite copiar-e-colar, comprovante sem aviso |
| 🟡 | Frota / equipamento do RDO → custo | Três camadas na mesma viagem; equipamento é string livre |
| 🟡 | SIGE → mundo externo | Canal único é o webhook n8n — sem a variável de ambiente, no-op sem persistir |
| 🔴 | CRM → Propostas | O redirect envia os IDs; a rota os descarta e o usuário redigita o cliente |
| 🔴 | Ponto/Alocação → RDO | O encarregado re-seleciona quem trabalhou; prefill vem do último RDO |
| 🔴 | Baixa financeira → caixa/contábil | Baixa da CR não cria FluxoCaixa; a CR de medição nasce sem conta contábil |
| 🔴 | Cotação → pedido de compra | O mapa só trava alçada; vencedor e preço são redigitados |
| ⚫ | Propostas → CRM (desfecho) | Aprovar/rejeitar não toca o lead; as FKs existem e nada as escreve |
| ⚫ | Propostas → serviços do RDO | Zero criadores de `ServicoObraReal` referenciam proposta |
| ⚫ | Almoxarifado (saída) → custo da obra | Handler write-nothing por decisão; custo central preso no administrativo |

**O padrão de risco, em três formas:** (1) duplicação estrutural por caminhos
concorrentes que não se enxergam; (2) exceção engolida como modo default —
quase todo handler e listener só loga; (3) estrutura morta carregada em todo
boot. **Os ganhos mais baratos são elos já construídos que morrem a um passo do
fim.**

---

## 4. Os dez pacotes

Cada pacote tem tamanho de uma spec. Pacotes na mesma onda podem andar em
paralelo.

```
Onda A   p1
Onda B   p2 ‖ p3 ‖ p9
Onda C   p4 ‖ p5 ‖ p6
Onda D   p7
Onda E   p8
Onda F   p10
```

### p1 — Estancar sangramento: tenant e dupla contagem *(onda A)*

**Objetivo:** fechar o vazamento entre empresas e eliminar a dupla contagem de
mão de obra nas duas tabelas de custo.

- `admin_id` nos 7 relatórios operacionais (`relatorios_funcionais.py:58-266`)
  e nas 3 exportações (`:456-572`)
- Remover/blindar os 5 fallbacks "admin com mais dados"
  (`views/obras.py:1520`, `views/rdo.py:70/78/92/2274`) → 403/404
- Dedup **cross-origem** de `CustoObra` de mão de obra por
  (funcionário, data, obra, admin) — o dedup do handler filtra por `rdo_id`
  e nunca enxerga o registro do ponto, que tem `rdo_id` NULL
- Dedup cross-origem de `GestaoCustoFilho` SALARIO/MAO_OBRA_DIRETA
- Idempotência no path horista do ponto (emitido a cada batida)
- Reusar a guarda `existe_ponto_no_dia` (`services/rdo_custos.py:50`) no handler
  `lancar_custos_rdo` — hoje só o caminho paralelo a usa
- **A05:** emitir `rdo_finalizado` nos 4 caminhos que só chamam
  `gerar_custos_mao_obra_rdo` — fecha a assimetria custo-sem-medição
- **A09:** dedup de NF na entrada manual de almoxarifado

**Pronto quando:** nenhuma query de `relatorios_funcionais.py` roda sem
`admin_id` (teste cross-tenant vermelho → verde); um dia simulado com batidas
múltiplas mais finalização de RDO, para horista e diarista, produz **exatamente
uma** linha de custo de mão de obra por (funcionário, data, obra) em cada
ledger; os 5 fallbacks respondem 403/404.

**Depende de:** nada. É o primeiro porque todo custo exibido hoje é
potencialmente inflado.

---

### p2 — Rollout das três flags do núcleo *(onda B — zero código novo)*

**Objetivo:** ligar `cronograma_mpp_ativo`, `cronograma_editor_v2` e
`rdo_percentual_livre`, seguindo os runbooks.

> ### ⚖️ 03/08 — o editor v2 saiu do piloto e foi para o parque inteiro
>
> Decisão do Cássio: *"todos cronogramas que já estão feitos no deploy virarem
> no novo formato, que pode editar no botão direito."* A migração **277**
> (`41f23403` + `ff94240d`) executa o runbook no boot, para todos os tenants: congela a
> linha de base de toda obra datada → cria `configuracao_empresa` para quem
> tem cronograma e não tinha linha → liga a flag em todas as linhas → vira o
> default da coluna para TRUE.
>
> Isto **muda a natureza deste pacote em três pontos**:
>
> 1. **Não há tenant piloto para o editor v2.** A validação deixa de ser "uma
>    obra piloto observada" e passa a ser "o parque observado" — o que torna a
>    linha de base do passo 1 a única rede, e não uma formalidade;
> 2. **O guard de calendário virou aviso.** O `--ligar` recusa tenant com
>    sábado/domingo; a 277 liga assim mesmo e denuncia nominalmente no log do
>    deploy. O gatilho de "calendário configurável" deixou de ser hipotético:
>    quem estiver nessa lista **vai** ver datas andarem na primeira edição;
> 3. **Tenant que não é `versao_sistema='v2'` fica com a flag ligada e
>    inerte** (`utils/tenant.py:139` exige V2 **e** a flag). A 277 conta
>    quantos são no log. Trocar a versão do sistema de um tenant é decisão
>    fora deste pacote — mas é ela que decide se "todo cronograma no formato
>    novo" é verdade ou só verdade para parte do parque.
>
> Um defeito que só apareceu executando, e que vale para toda migração futura
> que mexa em tabela quente: o `ALTER TABLE` do passo 4 pede ACCESS EXCLUSIVE,
> o `pre_start.py` sobe o app antes de migrar, e a sessão dele segurava a
> tabela — 20 minutos parado, com todo acesso a `configuracao_empresa`
> enfileirado atrás. Corrigido com `lock_timeout`, transação própria depois do
> flip já commitado, e degradação para aviso se o lock não vier.

- ~~Confirmar deploy e migrations em produção~~ → **é agora o pré-requisito de
  tudo**: a 277 só roda quando o commit chegar ao GitHub e o EasyPanel buildar
- **mpp:** pré-checagem por `scripts/diagnostico_cronograma_tenant.py` (a flag
  governa borda visual e não tem guard bloqueante, por design) + equivalência
  pós-import
- ~~**editor v2:** snapshot antes, `--criar-baseline`, decidir o calendário,
  ligar e comparar~~ ✅ **feito pela migração 277** (a linha de base entrou
  como passo 1 da própria migração; o calendário foi decidido como aviso).
  Resta **observar o parque** e, se preciso, excluir tenant com `--desligar`
- **percentual livre:** reapontar as tarefas legadas que o guard listar, ligar,
  observar uma semana
- **A06:** chamar `replanejar_curvas_obra` após os recálculos da UI do editor v2
  — a função existe e tem **um único caller**

**Pronto quando:** as três flags TRUE, uma semana de operação sem regressão de
físico nem reclamação de datas, evidências nos runbooks. Para o editor v2, o
"sem reclamação de datas" agora se mede no parque, não numa obra escolhida.

**Decisão pendente:** ~~tenant piloto e~~ calendário. A pergunta deixou de ser
"o piloto exige sábado?" e virou **"algum tenant da lista que o deploy imprimir
trabalha sábado de verdade?"** — se sim, calendário configurável vira código, e
a linha de base é o que segura o plano antigo até lá.

---

### p3 — Fonte única do custo orçado *(onda B)*

**Objetivo:** todo consumidor de "orçado" — inclusive o futuro BAC — ler custo
de composição, não preço de venda.

- Escolher o caminho: **(a)** padronizar o fallback já testado de
  `services/resumo_custos_obra.py:253-269` (soma de `ObraServicoCustoItem`)
  como fonte canônica, ou **(b)** corrigir a origem no listener
  (`models.py:7466`)
- Se (b): neutralizar os dois re-syncs venda → orçado
  (`medicao_views.py:302-315`, `views/catalogo_views.py:870-886`)
- Corrigir `services/cronograma_fisico_financeiro.py:281-296`, que soma o valor
  cru — fonte provável da curva PV
- Inventariar e migrar os demais consumidores

**Pronto quando:** `resumo_custos_obra` e `cronograma_fisico_financeiro`
devolvem o mesmo "orçado" para a mesma obra, e editar medição ou vincular preço
de catálogo não re-infla o valor.

**Decisão pendente:** (a) é menor e replica padrão testado; (b) é definitivo.

---

### p9 — Dono único do `Obra.valor_contrato` *(onda B — decisão + Fase 6)*

**Objetivo:** resolver a contradição entre as Fases 6 e 9b antes que qualquer
uma entre em execução.

- Ratificar **Fase 6 primeiro**: `ObraContratoVersao` + `services/contrato_obra.py`
  como escritor único — a própria 9b subordina o aditivo àquela cadeia
  (premissa P1, linha 4670)
- Reescrever 9b tasks 15-16 como **camada documental** (PDF, assinatura,
  vencimento), sem listener `after_flush` concorrente nem segundo serviço
- Fechar os **4** escritores vivos: `event_manager.py:1029` e `:1104`,
  `views/obras.py:417` e `:954`, mais `services/importacao_fisico_financeiro.py:754`
  — este último **omitido do inventário da Fase 6**
- Executar a Fase 6 pelo fluxo da casa

**Pronto quando:** decisão registrada; 9b reescrita; após a Fase 6, o grep
confirma um único ponto de escrita do campo.

**Decisão pendente:** ratificação do dono do produto.

---

### p4 — Uma fórmula de progresso *(onda C)*

**Objetivo:** consolidar as cinco fórmulas em ~20 call-sites.

- `portal_obras_views.py:745-758` (`gerar_medicao`) — **crítico**: a média
  simples vira `valor_medido` e `percentual_executado` persistido, que o cliente
  vê ao lado do anel ponderado
- `views/dashboard.py:444-453` e o derivado em `:987-988`
- `cronograma_views.py:354-373` (avg sobre todas as tarefas, dupla-contando pais)
- Fallback de template em `templates/obras/cronograma.html:124/158`
- Usar `progresso_geral_para_kpi` (`utils/cronograma_engine.py:1035-1054`) como
  ponto único — já trata obra sem cronograma

**Pronto quando:** anel do portal, dashboard, index do cronograma e medição nova
exibem o mesmo percentual para a mesma obra e data.

**Decisão pendente:** recalcular ou congelar as `MedicaoObra` históricas.

---

### p5 — A aprovação semeia a obra inteira *(onda C)*

**Objetivo:** a obra nascer pronta para o RDO, e o CRM saber o desfecho.

- `handle_proposta_aprovada` semeia `ServicoObraReal` dos PropostaItens, na mesma
  transação que já cria IMC/OSC/cronograma
- Fechar o Lead (ganho + `obra_id`) — as FKs existem e nada as escreve
- **A07:** `propostas.nova` lê `?cliente_id=&lead_id=`; **A22:** select de
  cliente no formulário manual e persistir o CPF/CNPJ (hoje descartado numa
  variável local)
- Definir o destino da válvula V2 (`views/rdo.py:3725-3742`) e do fallback dual
  `ServicoObra` legada × `ServicoObraReal` (`:4762-4790`)
- Garantir serviço/quantidade/peso equivalentes para o cronograma vindo de `.mpp`

**Pronto quando:** obra criada por aprovação permite criar RDO sem nenhuma
re-seleção manual de serviços; o lead correspondente fecha sozinho.

---

### p6 — Reconciliar os regimes de peso *(onda C)*

**Objetivo:** **não construir** o auto-casamento (existe desde Task #102) —
unificar os regimes de peso e cobrir os dados sem linhagem.

- Normalizar o peso do import JSON (`services/importacao_fisico_financeiro.py:227-242`
  grava peso=dias) **ou** adaptar o gate `==100` de `gerar_medicao_quinzenal`
  — hoje o import passa no cálculo e **quebra na geração da medição**
- Alinhar as validações: o manual só bloqueia soma > 100; o gerador exige == 100
- Backfill dos itens legados e manuais sem linhagem
- **A15:** unificar a medição do portal com o trilho ponderado

**Pronto quando:** `gerar_medicao_quinzenal` não recusa nenhum item de obra
criada por qualquer dos três caminhos; zero itens ativos com soma ≠ 100.

---

### p7 — Presença única *(onda D)*

**Objetivo:** uma fonte de verdade: a batida real nunca sobrescrita, o RDO
pré-carregado, e o modelo órfão aposentado.

- **Primeiro:** corrigir `AllocationEmployee.sincronizar_com_ponto`
  (`models.py:4543-4559`) — sobrescreve hora de entrada/saída/obra com o turno
  planejado, e a criação de registro novo está quebrada (viola NOT NULL de
  `admin_id`); registros criados não emitem `ponto_registrado`
- **A17:** RDO pré-carrega `RDOMaoObra` do ponto/alocação do dia + alerta de
  divergência — hoje o prefill vem do último RDO
- **Aposentar** `AlocacaoEquipe` e a FK `rdo_gerado_id` (modelo nunca instanciado
  em produção) em vez de integrá-los
- Consertar de carona o `funcionario_id` sempre nulo em
  `almoxarifado_utils.py:418-420`, único leitor da FK morta
- Convergir Allocation/AllocationEmployee × RegistroPonto × RDOMaoObra para
  planejada → confirmada → apontada

**Pronto quando:** batida real jamais alterada por sync de plano; RDO novo nasce
com a equipe do dia; `AlocacaoEquipe` sem referências vivas.

**Depende de p1:** pré-carregar o RDO a partir do ponto sem a dedup cross-origem
multiplicaria a dupla linha de custo por funcionário/dia.

---

### p8 — Convergência da gravação do progresso *(onda E)*

> 🔬 **03/08, achado do p4 — o p8 é maior do que parecia.** Não são só
> caminhos de gravação divergentes: são **duas FONTES de verdade** para
> progresso. `TarefaCronograma.percentual_concluido` é escrita por import de
> .mpp/JSON, pela grade do editor e pela sincronização vinda dos apontamentos;
> `calcular_progresso_geral_obra_v2` **ignora a coluna** e deriva tudo de
> `RDOApontamentoCronograma`, contando 0 para tarefa sem apontamento.
>
> Numa obra que avança por import ou pela grade, sem apontar RDO, a coluna
> mostra o avanço real e o motor devolve zero. Foi por isso que a medição do
> portal **não** pôde migrar para o motor no p4: trocar a fonte embaixo de um
> número que multiplica `valor_contrato` zeraria a medição dessas obras.
> `utils/cronograma_engine.progresso_ponderado_armazenado` existe por essa
> razão, e o comentário dela aponta para cá.

**Objetivo:** fechar a dualidade de destinos no backend — a UI já é entrada
única.

- Derivar `RDOServicoSubatividade.percentual_conclusao` dos apontamentos usando
  o elo `subatividade_mestre_id`, que existe dos dois lados e **nunca é lido**
  para progresso
- Repontar o fallback da medição (`services/medicao_service.py:207-250`) e o
  fallback V1 do KPI para a fonte única
- Decidir o destino dos caminhos backend que ainda aceitam
  `subatividade_*_percentual` (`salvar_rdo_flexivel`, `rdo_salvar_unificado`)

**Pronto quando:** um único apontamento atualiza cronograma, subatividade
(derivada) e medição com o mesmo número.

**Depende de p4 e p2:** a fonte única de leitura define para onde o fallback
aponta; o piloto diz quais caminhos legados seguem vivos.

---

### p10 — Fase 7 reescrita: EVM sobre o editor v2 *(onda F)*

**Objetivo:** entregar EVM e monetização da baseline **compondo** o que já
existe — jamais uma segunda rede de predecessoras ou segunda baseline.

**Reaproveitar:** `TarefaVinculo`, `services/cronograma_scheduler.py` (folga,
crítica, ciclo, roll-up), `CronogramaBaseline`/`Item` com a coluna Desvio, e a
flag `cronograma_editor_v2`.

**Descartar do plano de 21/07:** `TarefaPredecessora`, `utils/cpm.py`,
`cronograma_cpm_service`, `backfill_predecessoras_tipadas`, baseline como
`CronogramaVersao.is_baseline` (a separação foi decidida em código) e flag
própria de CPM.

**Construir:**
- Motor EVM das grandezas por composição — PV de `montar_curva_s`/`alocar_por_peso`,
  AC de `curva_realizado`, EV = progresso físico × BAC
- Preencher o `pct_fisico` do painel (hoje `None`,
  `services/cronograma_fisico_financeiro.py:263`)
- BAC congelado junto à baseline (hoje ela só congela datas)
- Costura tarefa ↔ `ObraServicoCusto` — o único join novo
- Folga livre no scheduler (o v2 só calcula folga total) e chave `evm` no
  endpoint `/obras/<id>/financeiro/dados` + UI

**Mudança de premissa:** o CPM vivo é um **agendador que reescreve datas**, não
a camada de análise não-destrutiva que o plano assumia — a validação "caminho
crítico bate com o MS Project" muda de natureza.

**Pronto quando:** curvas PV/EV/AC e índices servidos no endpoint financeiro e
na UI para a obra piloto, com BAC = custo (não venda), desvio monetizado contra
a baseline, e nenhum modelo novo duplicando `TarefaVinculo` ou
`CronogramaBaseline`.

**Depende de:** p3 (BAC = custo), p1 (AC sem dupla contagem), p6 (pesos), p9
(fonte estável do BAC), p2 (flag ligada e validada — ligada em todo o parque
desde 03/08; falta a validação de uma semana de operação).

---

## 5. Backlog de automação — 25 itens

Cada item rastreia a uma evidência da matriz. **E** = esforço.
Os de esforço **P** são elos já construídos que morrem a um passo do fim.

| # | E | Pacote | Automação |
|---|---|---|---|
| A01 | P | novo | Consumir as transferências do extrato no confirm do import — a detecção já existe e é descartada |
| A02 | P | novo | `FluxoCaixa` na baixa de ContaReceber — espelhar o lado pagar, que já faz |
| A03 | P | novo | Conta contábil na CR OBR-MED — hoje o gate pula a partida dobrada em silêncio |
| A04 | P | novo | `DESPESA_GERAL` no `MAPEAMENTO_CONTABIL` — pagamento pela Gestão de Custos falha em silêncio ⚖️ |
| A05 | P | **p1** | Emitir `rdo_finalizado` nos 4 caminhos que não emitem — custo sem recálculo de medição |
| A06 | P | **p2** | Replanejar curvas após recálculo do editor v2 — a função tem um único caller |
| A07 | P | **p5** | Pré-preencher proposta e obra com os IDs que o CRM já manda |
| A08 | P | novo | Import de alimentação gerar custo, como o formulário v2 ⚖️ |
| A09 | P | **p1** | Dedup de NF na entrada manual de almoxarifado |
| A10 | P | **p1** | Idempotência no custo de horista do ponto |
| A11 | M | **p1** | Unificar os dois mecanismos de custo do RDO (dedup cruzando origens) |
| A12 | M | **p1** | Reprocesso de folha estornar antes de recriar |
| A13 | M | **p3** | Orçado deixa de herdar venda |
| A14 | M | **p5** | Aprovação semeia serviços e fecha o lead |
| A15 | M | **p6** | Unificar a medição do portal com o trilho ponderado |
| A16 | M | **p7** | Consertar o sync alocação → ponto (criação quebrada, batida destruída, sem evento) |
| A17 | M | **p7** | Pré-carregar a mão de obra do RDO da presença do dia |
| A18 | M | **p8** | Derivar progresso entre trilhos via `subatividade_mestre_id` |
| A19 | M | **p4** | Fórmula única de progresso |
| A20 | P | novo | Pré-preencher o pedido com o vencedor da cotação |
| A21 | M | novo | FK de frota no equipamento do RDO + corrigir o TypeError de kwargs no salvamento |
| A22 | P | **p5** | Select de cliente na proposta manual + persistir CPF/CNPJ |
| A23 | P | novo | Aviso interno de comprovante enviado e decisão de compra do portal |
| A24 | M | novo | Ligar o pipeline de encargos patronais — completo e sem chamadores ⚖️ |
| A25 | P | novo | Ativar o canal externo: `N8N_WEBHOOK_URL` + cron do lembrete D-3 ⚖️ |

⚖️ = depende de decisão de negócio, não só de código.

---

## 6. Estruturas mortas — candidatas a aposentadoria

Carregadas em todo boot, sem uso em produção:

| Estrutura | Evidência |
|---|---|
| Handler `nota_fiscal_paga` órfão | `handlers/financeiro_handlers.py:15` — zero emissores |
| `NotificacaoCliente` | Nunca criada nem lida; único uso vivo é DELETE para não quebrar FK |
| `ObraSignatarioCliente.email` | Gravado e jamais consumido para envio, exibição ou payload |
| `AlocacaoEquipe` + FK `rdo_gerado_id` | Jamais instanciada em produção — **aposentar no p7** |
| `Lead.proposta_id` / `Lead.obra_id` | FKs sem nenhuma escrita nem campo no formulário — **reviver no p5** |
| `FolhaPagamento.adiantamentos` | Único escritor está em `archive/` |
| Pipeline de encargos patronais | `processar_e_salvar_folha_obra` sem chamador — **A24** |
| Evento `material_saida` | Handler write-nothing e emissor com `movimento_id=0` fixo |
| CPF/CNPJ da proposta | Lido para variável local e descartado na própria requisição |
| Tabela `CronogramaCliente` | O portal não a lê mais; a rota de edição ainda grava nela |
| `subatividade_mestre_id` como ponte | Presente nos dois trilhos e nunca usada — **base do p8** |
| SMTP + agendador de relatórios | MAIL_SERVER inexistente, painel dá 500, agenda em dict de memória |

---

## 7. O que espera decisão, não código

| # | Decisão | Trava |
|---|---|---|
| 1 | ~~**Tenant piloto do rollout**~~ **+ calendário** | 🔬 **03/08: metade decidida.** O editor v2 foi ligado em todo o parque (migração 277), então não há piloto a escolher para ele — só para as outras duas flags. O **calendário** continua aberto e agora com nome e sobrenome: o log do deploy imprime quais tenants consideram sábado/domingo, e é neles que as datas vão andar na primeira edição. Se algum deles trabalha sábado de verdade, calendário configurável vira código |
| 2 | ~~**Dono do `valor_contrato`**: Fase 6 (cadeia) × Fase 9b (deltas)~~ | ✅ **03/08: FASE 6**, como a própria 9b já assumia na premissa P1. `services/contrato_obra.py` já é o escritor único — os escritores eram **cinco**, não quatro: o quinto é o construtor `Obra(valor_contrato=…)` do handler de aprovação, que não aparece em grep por atribuição |
| 3 | ~~**Custo orçado: consertar no consumo ou na origem**~~ | ✅ **03/08: no CONSUMO.** `services/custo_orcado.py` virou a fonte única (regra "linha de custo vence agregado", extraída de `resumo_custos_obra`); `valor_orcado` segue gravado com venda, mas ninguém mais o lê como custo. Consertar na origem continua sendo a saída definitiva e está registrada na spec |
| 4 | **Medições históricas: recalcular ou congelar** | p4, a linha do tempo do portal e o EVM retroativo. 🔬 **03/08:** o p4 foi entregue "para frente" — medição NOVA usa a fórmula única; as já emitidas seguem congeladas até esta decisão |
| 5 | **Conta de débito da despesa geral** (contador) | A04 e a contabilização dos pagamentos da Gestão de Custos |
| 6 | **Rateio dos encargos patronais por obra** | A24 — hoje a mão de obra sai ~28% subestimada |
| 7 | **`N8N_WEBHOOK_URL` e cron** (infra) | A25 e **toda notificação do plano** |

Segue valendo a decisão de **27/07**: "por enquanto todos os perfis vão ter
acesso" — o que mantém desligadas as flags de escopo por obra e de governança de
compras. Não afeta o núcleo; afeta quem pode aprovar aditivo na Fase 6.

---

## 8. Como este documento se relaciona com os outros

| Documento | Relação |
|---|---|
| `FLUXO-IDEAL.md` (30/07) | O diagnóstico. As ondas 0-3 dele foram **reordenadas** nos pacotes p1-p10; onde os vereditos divergem, vale este documento |
| `docs/superpowers/plans/2026-07-21-fase-7-*` | **Obsoleto como escrito.** Substituído pelo p10 |
| `docs/superpowers/plans/2026-07-21-fase-6-*` | Válido; executa no p9, com o 4º escritor acrescentado |
| `docs/superpowers/plans/2026-07-21-fase-9-*` | 9a parcial (ciência entregue; `PortalAcesso` inexistente). 9b a reescrever após o p9 |
| `docs/superpowers/plans/2026-07-21-fase-8-*` | Dependências satisfeitas. A01-A04 já atacam parte da Parte A |
| `docs/rollout-consolidado.md` | O runbook do p2 |
| `docs/cronograma-editor-v2-rollout.md` | O runbook do editor v2 — desde 03/08 traz no topo a decisão do parque inteiro e o que a migração 277 faz por você |
| `ESTADO-ATUAL.md` | O mapa geral; ler primeiro ao retomar |
| `MODULOS.md` | Rastreio de rotas e modelos por blueprint |

---

## Histórico

- **2026-08-03** — o editor v2 saiu do p2 pela porta larga: ligado em **todo o
  parque** pela migração 277 (`41f23403` + `ff94240d`), com linha de base congelada antes,
  em vez do rollout tenant a tenant. O guard de calendário virou aviso
  nominal no log do deploy, e o gatilho de "calendário configurável" deixou de
  ser hipotético. Restam duas flags no p2 (`cronograma_mpp_ativo`,
  `rdo_percentual_livre`) e a validação de uma semana de operação.
- **2026-07-31** — primeira versão. Conferência adversarial (12 vereditos, 0
  refutados) e levantamento de conexões (tecido de eventos, 8 arestas, matriz de
  20 conexões, backlog de 25 automações). Plano rearquitetado em 10 pacotes e 6
  ondas, com o par cronograma ↔ RDO no centro por decisão de produto. Bruto em
  `docs/estudo-fluxo/conferencia-2026-07-31.json` e
  `docs/estudo-fluxo/conexoes-2026-07-31.json`.
