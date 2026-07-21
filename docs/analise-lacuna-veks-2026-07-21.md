# Análise de lacuna — rascunho de arquitetura × SIGE atual

> Data: 2026-07-21. Método: varredura de código em quatro frentes paralelas
> (Comercial, Operação, Suprimentos/Financeiro/Jurídico, Transversal), com
> as alegações mais graves reverificadas manualmente. Regra adotada:
> template sem backend ou rota morta **não** conta como existente.

## Veredito de uma linha

O rascunho está majoritariamente errado sobre o *estado*: o SIGE já
implementa 7 dos 8 módulos propostos, vários com maturidade acima do que
o rascunho imagina. Mas está certo sobre o *destino*: **as quatro regras
de negócio que ele quer codificar não existem** — e nenhuma delas pode
existir antes de resolver uma lacuna comum que ele não menciona.

## Correções factuais ao rascunho

1. **`dashboard_baias.html` não existe no repositório** (zero ocorrências).
   O protótipo real, já generalizado para qualquer obra, é
   `templates/obras/detalhes_obra_profissional.html` (7 abas).
   `templates/dashboard_executivo_obra.html` existe como arquivo mas
   nenhuma rota o renderiza — é template morto.
2. **`veks_classificador` não existe com esse nome.** O classificador real
   é `services/classificador_cadastro.py`, e é *mais* capaz do que o
   rascunho supõe: regras com prioridade, exceções, condição AND, condição
   por obra, memória exata (`CorrecaoClassificacao`) e loop de aprendizado
   (`PalavraChaveSugestao`), com 5 arquivos de teste.
3. **Não existe classe `Oportunidade`.** O funil é `Lead` + `LeadStatus`
   (`models.py:6626`), com Kanban de 8 colunas, histórico campo-a-campo e
   gate de validação por supervisor.

## Estado por módulo

| Módulo | Estado | Observação |
|---|---|---|
| CRM / Comercial | **Maduro** | Kanban, dedupe de cliente por telefone/e-mail, histórico, import/export CSV |
| Orçamento | **Maduro (base própria)** | Insumos, composições, preço versionado por vigência, BDI por dentro, histórico de coeficiente |
| Projetos (técnico) | **Fraco** | Arquivos só na Proposta; sem repositório na Obra |
| Obra / Operação | **O mais maduro** | Cronograma .mpp, versionamento, RDO, medição, portal do cliente, motor unificado (M01–M10) |
| Compras | **Parcial** | Mapa de concorrência V1+V2 e cotações existem; falta a requisição |
| Financeiro | **Maduro** | Contas a pagar/receber, fluxo de caixa, classificador, orçado×real, contabilidade própria |
| Jurídico | **Ausente** | Confirmado — a única lacuna de módulo que o rascunho identificou corretamente |
| Dashboard geral | **Parcial** | Existe e é operacional; margem e caixa são calculados no backend e nunca renderizados |

### Ausências reais (greenfield)

- **Google Drive** — nenhuma integração. O único vestígio é `Lead.pasta`,
  um `String(500)` de texto livre digitado à mão.
- **Jurídico inteiro** — sem `Contrato`, sem aditivo, sem locação. Sem
  entidade com vigência, não há o que alertar de vencimento.
- **DXF / BIM** — duas ocorrências no repo, ambas triviais (extensão na
  allowlist de upload e escolha de ícone). Nenhuma biblioteca CAD/BIM.
- **Revisões de desenho** — `PropostaArquivo` não tem `revisao`, `versao`
  nem `status_aprovacao`.
- **Agenda / follow-up ativo** — só semáforo passivo (`Lead.prazo_cor`,
  `dias_parado`). Não há entidade de compromisso agendado nem job de
  lembrete. `CrmCadencia` é rótulo de dropdown, sem motor.
- **SINAPI** — só em documentação. Hoje é transcrição manual via Excel.
- **Ponte com o Domínio** — ausente. Existe contabilidade interna de
  partidas dobradas; a tela `/contabilidade/sped` é vazia por construção
  (nada instancia `SpedContabil`).

## As quatro regras de negócio: nenhuma está codificada

### 1. Handoff Comercial → GP — **AUSENTE**

| Peça | Realidade |
|---|---|
| Estado da obra | `Obra.status` é `String(20)` de texto livre (`models.py:257`), alimentado por dropdown editável pelo tenant. Não existe "vendida" nem "em execução" |
| Dono da obra | `Obra.responsavel_id` existe (`models.py:258`) mas **todos** os usos são exibir nome. Zero uso em autorização |
| Aceite formal | Inexistente. Proposta aprovada → obra criada e já operável, sem intervenção |

Agravante estrutural: `responsavel_id` aponta para `Funcionario` (cadastro
de RH), e **`Funcionario` não tem FK para `Usuario`** — a ligação hoje é
comparação de e-mail em runtime (`views/rdo.py:2149`). O responsável da
obra não é um usuário logável.

Há dois padrões maduros no próprio repo para copiar: o state machine de
`CronogramaImportacao` (transições + trilha auditada) e o gate de uso
único `Obra.cronograma_revisado_em` (`views/obras.py:2375`), que já tem a
forma de um aceite — só carimba data, não pessoa.

### 2. Aval do GP em toda compra — **AUSENTE**

- **Não existe requisição.** Zero ocorrências de "requisic" no repositório.
  O fluxo proposto não tem sequer o primeiro estado.
- **A compra é efetivada no mesmo request.** `compras_views.py:708`:
  `processar_compra_normal(...)` já cria `GestaoCustoPai`, as `ContaPagar`
  parceladas e a entrada no almoxarifado. Aperta salvar → custo,
  obrigação e estoque existem.
- **O único gate aprova o CLIENTE, não o GP** — via portal com token
  (`portal_obras_views.py:343`). É gate comercial, não governança interna.
- **Não existe papel de Gerente de Projeto** para receber o aval.

O que mais se aproxima e não serve: `GestaoCustoPai.status`
PENDENTE→SOLICITADO→AUTORIZADO→PAGO. É *a jusante* (o custo já existe
quando o fluxo começa), não valida papel, e barra o desembolso — não a
compra.

### 3. Centro de custo travado na obra — **FALSA no modelo**

O eixo de planejamento tem `obra_id` NOT NULL; o eixo **transacional** é
100% nullable — exatamente o inverso do necessário.

| Classe | `obra_id` | Arquivo |
|---|---|---|
| `PedidoCompra` | **nullable** | `models.py:4736` |
| `ContaPagar` | **nullable** | `models.py:1746` |
| `ContaReceber` | **nullable** | `models.py:1793` |
| `FluxoCaixa` | **nullable** | `models.py:792` |
| `GestaoCustoPai` | **campo não existe** | `models.py:5210` |
| `GestaoCustoFilho` | **nullable** | `models.py:5302` |
| `ObraServicoCusto` (orçado) | NOT NULL | `models.py:5854` |
| `MapaConcorrenciaV2` | NOT NULL | `models.py:5604` |
| `MedicaoContrato` | NOT NULL | `models.py:5574` |

E o código *explora* a opcionalidade: `compras_views.py:583` faz
`request.form.get('obra_id') or None`; `gestao_custos_views.py:467`
permite **apagar** a obra de um custo já lançado.

Consequência: todo lançamento sem `obra_id` some do orçado×real sem erro
e sem alerta. `services/resumo_custos_obra.py:190` implementa um rateio
proporcional ao orçado como paliativo — o furo é conhecido e hoje é
compensado por estimativa, não por dado.

### 4. Orçamento dono da versão vigente / aditivo — **INVERTIDA, e com bug**

Quem versiona é a **Proposta** (`Proposta.versao` + `substituida_por_id`,
`models.py:3022`), não o `Orcamento`. O `Orcamento` não tem `versao`,
`revisao` nem `origem_id`: o único mecanismo é `duplicar()`
(`views/orcamentos_views.py:527`), que cria um orçamento novo **sem FK de
volta** — não há como reconstruir a cadeia R00→R01→R02.

**E aprovar uma revisão de proposta cria uma obra duplicada.** Cadeia
verificada linha a linha:

1. `propostas_consolidated.py:1224` — editar proposta com status ≠ rascunho
   (o comentário diz explicitamente "enviada/**aprovada**/etc.") leva à
   tela de criar nova versão. Caminho intencional.
2. `criar_nova_versao` (`:1245`) copia ~25 campos — `titulo`, `cliente_id`,
   `valor_total`, `orcamento_id`, itens, cláusulas — mas **não copia
   `obra_id`**. A v2 nasce órfã da obra.
3. `event_manager.py:947` busca a obra por `proposta.obra_id` (None na v2)
   e depois por `proposta_origem_id == id_da_v2` — mas a obra existente
   aponta para a **v1**. Nenhum match.
4. `event_manager.py:955` gera novo código `OBR####` e **cria uma segunda
   `Obra`**; `handlers/propostas_handlers.py:15` replica todos os
   `ItemMedicaoComercial` e `ObraServicoCusto` nela.

O cenário é exatamente o aditivo: cliente pede mudança → revisa a proposta
→ aprova → duas obras para o mesmo contrato, cada uma com cronograma,
medições e centro de custo próprios.

Complemento: mesmo achando a obra, o valor não subiria —
`event_manager.py:1009` só grava `valor_contrato` se ele estiver zerado.
Hoje o valor de contrato muda por **digitação manual**
(`views/obras.py:871`), sem histórico, sem autor, sem vínculo à versão —
e é a base de todo o faturamento (`MedicaoContrato.valor = pct ×
obra.valor_contrato`).

O padrão a copiar já existe no repo: `ObraOrcamentoOperacionalItemVersao`
(`models.py:6985`) implementa janelas `[vigente_de, vigente_ate)` com
motivo. Nunca foi aplicado ao valor de contrato comercial.

## A lacuna que o rascunho não menciona — e que bloqueia as outras

O rascunho pendura toda a usabilidade por funcionário em "cada módulo tem
um dono e visibilidade definida". **Isso não tem nenhuma base no código.**

- **Papéis**: `TipoUsuario` tem 5 valores hierárquicos (`models.py:21`).
  Não existe `COMERCIAL`, `COMPRAS`, `FINANCEIRO`, `GERENTE_PROJETO`,
  `ENCARREGADO`. Gabriela e Cássio seriam ambos `FUNCIONARIO` ou ambos
  `ADMIN`.
- **Área/departamento**: `Departamento` existe, mas ligado a `Funcionario`
  (RH), não a `Usuario`. O sujeito da autorização não tem área.
- **Permissão por módulo**: nenhuma tabela, nenhum decorator, nenhuma
  função. CRM, Compras, Financeiro, Custos e Cronograma usam apenas o
  `login_required` do flask_login — **autenticação, sem papel**. Um
  encarregado abre `/financeiro/fluxo-caixa` sem obstáculo.
- **Restrição por obra**: inexistente para usuário interno. `views/rdo.py:2168`
  filtra só por `admin_id`. Alan e Abel veriam todas as obras da Veks.
- **Templates órfãos**: `admin_acessos.html` e `editar_funcionario_acesso.html`
  apontam para rotas que não existem — renderizar qualquer um levanta
  `BuildError`. Não contam como "gestão de acessos existente".

### E os decorators de papel são no-op

`decorators.py:47-60` — `admin_required` e `login_required` são
`return f(*args, **kwargs)` incondicional, com o comentário "Durante
desenvolvimento, bypass para todos". São consumidos por
`configuracoes_views.py` (21 usos) e `ponto_views.py` (10 usos). Ou seja:
qualquer funcionário autenticado grava as configurações da empresa.

Contraste: `decorators.py:6 cronograma_import_required` (escrito no M01)
valida de fato — autenticação, tipo e tenant. É o único do arquivo que
funciona, e o modelo a seguir.

**Sem resolver esta camada, nenhuma das quatro regras tem onde se apoiar.**

## Achados de segurança fora do escopo pedido

Encontrados durante a varredura. Não são a pergunta que você fez, mas são
graves demais para ficar num rodapé:

1. **Rota anônima que devolve dados de um tenant escolhido por heurística.**
   `views/rdo.py:2133` — `/funcionario/rdo/consolidado` tem apenas
   `@capture_db_errors`, **sem `@login_required`**. Confirmado que não há
   `before_request` global de autenticação. Ela chama
   `get_admin_id_dinamico()` (`views/helpers.py:409`), que sem usuário
   autenticado escolhe o admin com mais funcionários, depois com mais
   serviços, e por fim **`return 1`** (`helpers.py:464`).
2. **Edição de usuário atravessa tenant.** `views/users.py:71` —
   `Usuario.query.get_or_404(user_id)` sem predicado de `admin_id`.
   O `admin_required` aqui é o real (de `auth.py`), mas ele só checa tipo,
   não empresa: um admin do tenant A edita usuário do tenant B por ID.
3. **Relatório executivo sem filtro de tenant.**
   `relatorios_funcionais.py:289` — `Funcionario.query.filter_by(ativo=True).count()`,
   `Obra.query.filter_by(ativo=True).count()`, `sum(CustoObra.valor)` sem
   nenhum predicado de empresa.
4. **~211 rotas sem decorator de autenticação** (805 rotas, 594 com
   `@login_required`).

## Ordem recomendada

O rascunho propõe construir módulos. A ordem que o código pede é outra:

1. **Fundação de autorização** — sanear os no-ops de `decorators.py`;
   FK `Funcionario.usuario_id`; papéis funcionais em `TipoUsuario`;
   vínculo usuário↔obra. Sem isso, três das quatro regras são
   inimplementáveis e a quarta é contornável.
2. **Corrigir o bug da obra duplicada** — é perda de dados silenciosa, no
   fluxo que a empresa mais usa (aditivo).
3. **Travar o centro de custo** — `obra_id` NOT NULL no eixo transacional,
   com migração dos registros órfãos. É o que torna o orçado×real
   confiável, e o rateio paliativo desnecessário.
4. **Requisição + aval do GP** — depende de (1) para ter a quem pedir aval.
5. **Handoff formal** — depende de (1) para ter um GP, e conceitualmente
   fecha com (4).
6. **Aditivo com histórico** — depende de (2) estar corrigido.
7. **Só então** os módulos novos: Jurídico, Drive, agenda de follow-up.

Os três itens genuinamente greenfield (Drive, Jurídico, DXF/BIM) são os
mais visíveis e os menos urgentes: nenhum deles corrompe dado hoje.
