# SIGE — Relatório de Evolução V2

**Data de geração:** 15 Abril 2026
**Ciclo:** V2 — desenvolvimento completo
**Status:** Ciclo em andamento · última entrega registrada em 15 Abr 2026

---

## Sumário por Módulo

| Módulo | O que foi feito em V2 |
|---|---|
| Transporte e Frota | Unificação dos módulos + integração com Gestão de Custos |
| Gestão de Custos | Extensão completa do modelo, extinção do ContaPagar, fluxo de aprovação |
| Fluxo de Caixa | **Módulo criado** — importação inteligente de Excel, movimentações manuais, banco |
| Contas a Receber | **Criação** — gerado automaticamente pelas medições de obra |
| Ponto e RH | Custo automático de diaristas ao bater ponto |
| Reembolsos | **Módulo criado** — CRUD completo com integração financeira |
| Cronograma | **Módulo criado** — Gantt, predecessoras, catálogo, templates |
| RDO | Mão de obra por subatividade, custo automático, produtividade |
| Produtividade | **Módulo criado** — dashboard e perfil por funcionário |
| Suprimentos e Almoxarifado | Reengenharia do fluxo de custo de material |
| Importação de Dados | **Módulo criado** — 5 módulos de importação Excel + Fluxo de Caixa |
| Dashboard | Custos por competência vs orçamento |
| Portal do Cliente | **Módulo criado** — portal público por obra, aprovações, medição quinzenal |
| Documentação | Atualização dos manuais do sistema |

---

## Módulo: Transporte e Frota

### Tarefa #1 — Transporte V2 Unificado: Frota + Deslocamentos
**Data de merge:** 01 Abr 2026

Os módulos de Frota (veículos próprios) e de Transporte (deslocamentos de funcionários) foram unificados em um único ponto de acesso na barra de navegação para usuários V2. O menu passa a ter dois grupos: Deslocamentos e Frota Própria. Usuários V1 continuam com os links separados, sem nenhuma alteração. Os custos registrados em Frota passaram a ser lançados automaticamente na Gestão de Custos, com categoria distinta da de deslocamento pessoal.

---

## Módulo: Gestão de Custos

### Tarefa #2 — Gestão de Custos → Fluxo de Caixa Financeiro
**Data de merge:** 02 Abr 2026

Os custos operacionais registrados pela Gestão de Custos (alimentação, transporte, reembolsos, salários de diaristas) passaram a ser incluídos no dashboard financeiro como saídas previstas. O fluxo de aprovação foi reestruturado em 3 etapas bem definidas: Solicitar → Autorizar → Pagar, cada uma com ação específica na tela. Os lançamentos da Gestão de Custos aparecem diferenciados na listagem do módulo financeiro.

### Tarefa #7 — Despesas Gerais via Gestão de Custos V2
**Data de merge:** 05 Abr 2026

Despesas avulsas sem módulo próprio (aluguel, energia, IPTU, honorários, etc.) passaram a ser lançadas pela Gestão de Custos, com campos extras de fornecedor, data de vencimento e número do documento. Essas despesas percorrem o mesmo fluxo de aprovação dos demais custos. O Fluxo de Caixa passou a usar a data de vencimento para posicionar os lançamentos no mês correto das projeções.

### Tarefa #8 — Extensão do Modelo de Gestão de Custos
**Data de merge:** 06 Abr 2026

O formulário de lançamento de custo foi estendido para suportar todos os dados necessários de uma saída financeira: fornecedor, forma de pagamento, data de emissão, número do documento e controle de parcelas. As categorias de custo foram reorganizadas em grupos que refletem os padrões da indústria da construção civil: Custo Direto de Obra, Custo Indireto de Obra e Despesa Administrativa.

### Tarefa #9 — Unificação Financeira: Extinção do ContaPagar
**Data de merge:** 07 Abr 2026

O módulo de Contas a Pagar foi desativado como ponto de criação de despesas. Toda nova saída financeira passa agora pela Gestão de Custos. O fluxo de caixa foi corrigido para não duplicar saídas. O menu lateral e o dashboard financeiro não exibem mais "Contas a Pagar" como módulo separado. Pagamentos parciais passaram a ser gerenciados dentro da própria Gestão de Custos.

### Tarefa #10 — Hotfix: Colunas Faltantes em Produção
**Data de merge:** 07 Abr 2026

Correção emergencial: as novas colunas adicionadas ao cadastro de custos na Tarefa #8 não existiam na base de dados de produção, causando erro que impedia o acesso ao módulo. A migração corretiva foi criada e o processo de subida da aplicação em produção foi ajustado para aplicar migrações pendentes automaticamente antes de iniciar.

### Tarefa #12 — Gestão de Custos: Fluxo de Aprovação em 2 Etapas
**Data de merge:** 08 Abr 2026

O fluxo de aprovação foi simplificado de 3 para 2 etapas: Solicitar → Aprovar. A aprovação passou a executar o pagamento diretamente, com campos de data de pagamento e conta bancária de origem. O botão de recusa retorna o custo para o estado inicial (Pendente). Pagamentos parciais continuam funcionando: quando há valor restante, o ciclo de solicitação recomeça automaticamente.

### Tarefa #16 — Gestão de Custos: Resumo por Obra
**Data de merge:** 11 Abr 2026

Quando um lançamento engloba itens de mais de uma obra, a coluna de identificação na listagem passou a exibir todas as obras envolvidas. Ao expandir o lançamento, aparece um quadro resumido com o total por obra antes da tabela de itens.

---

## Módulo: Fluxo de Caixa
**Criado em V2**

O módulo de Fluxo de Caixa foi construído do zero neste ciclo, com importação inteligente de planilhas Excel, movimentações manuais e controle de bancos.

### Tarefa #32 — Importação do Fluxo de Caixa via Excel
**Data de merge:** 09 Abr 2026

Foi criado um sistema completo de importação do histórico financeiro a partir de planilha Excel. O motor de classificação usa dois níveis de regras: mapeamento direto por plano de contas e reconhecimento por palavras-chave nas descrições, com busca aproximada de nomes de fornecedores e funcionários. Saídas pagas geram lançamento na Gestão de Custos e no Fluxo de Caixa; saídas em aberto geram apenas a Gestão de Custos; entradas pagas geram Conta a Receber e Fluxo de Caixa. Toda importação recebe um código de lote que permite desfazê-la por completo com um clique. A página de histórico lista todas as importações com data, totais por categoria e botão de reversão.

### Tarefa #34 — Modo "Apenas Pagamento" na Importação
**Data de merge:** 10 Abr 2026

Foi adicionada a opção "Apenas pagamento" por linha no preview da importação: quando marcada, o sistema registra apenas o movimento de caixa, sem criar um novo lançamento na Gestão de Custos (evitando duplicação de custos de diárias e compras já lançados por outros módulos). O sistema pré-marca automaticamente as linhas de funcionários e fornecedores de material com compras registradas no período.

### Tarefa #35 — Categoria "Retirada de Sócios" e Modo Fluxo Direto
**Data de merge:** 10 Abr 2026

A categoria "Retirada de Sócios" foi adicionada à Gestão de Custos e à importação. O modo "Apenas Fluxo" passou a criar exclusivamente o registro no Fluxo de Caixa, sem Gestão de Custos nem Conta a Pagar, adequado para saídas de caixa que não representam custo operacional.

### Tarefa #36 — Transferências Internas e Saldo Inicial de Bancos
**Data de merge:** 11 Abr 2026

A importação passou a tratar transferências entre contas bancárias como movimentos duplos (saída no banco origem e entrada no banco destino), ao invés de simplesmente ignorá-las. O preview exibe a seção "Transferências Internas" com checkbox de confirmação individual. Os saldos iniciais de cada banco presentes na planilha são detectados e apresentados para confirmação antes de serem aplicados ao cadastro bancário do sistema.

### Tarefa #37 — Baixa de Conta a Pagar sem novo lançamento no Fluxo de Caixa
**Data de merge:** 11 Abr 2026

Quando uma conta já existente é paga via tela de aprovação, o sistema passou a verificar se já existe um lançamento correspondente no Fluxo de Caixa para evitar duplicação. Contas baixadas que vieram de importação não geram um segundo registro de saída.

### Tarefa #39 — Fluxo de Caixa: Nova Movimentação e Edição Inline
**Data de merge:** 14 Abr 2026

A tela do Fluxo de Caixa ganhou botão "Nova Movimentação" para criar lançamentos diretamente (entrada ou saída), com campos de data, valor, descrição, categoria, banco e obra. Os campos de data, valor e descrição de cada linha existente passaram a ser editáveis diretamente na listagem, sem necessidade de abrir outra tela. O preview da importação também ganhou edição inline dos dados antes de confirmar, além de colunas de banco e marcação de reembolso por linha.

---

## Módulo: Ponto e Recursos Humanos

### Tarefa #3 — Diaristas: Custo Automático ao Bater Ponto
**Data de merge:** 03 Abr 2026

Funcionários com contrato de diária passaram a ter o custo do dia lançado automaticamente na Gestão de Custos no momento em que registram a entrada no ponto. O lançamento é vinculado à obra onde o ponto foi batido. O sistema evita lançamentos duplicados caso o funcionário registre entrada mais de uma vez no mesmo dia. O comportamento funciona tanto pelo aplicativo de ponto quanto pelo reconhecimento facial.

### Tarefa #11 — Hotfix: Diária no Ponto Manual
**Data de merge:** 08 Abr 2026

Correção de comportamento: quando o gestor lançava um ponto de entrada manualmente pela tela administrativa, o custo de diária do funcionário não era registrado automaticamente. O sistema passou a seguir o mesmo comportamento dos demais caminhos de registro de ponto.

---

## Módulo: Reembolsos
**Criado em V2**

### Tarefa #5 — CRUD Completo de Reembolsos V2
**Data de merge:** 04 Abr 2026

O módulo de reembolsos de funcionários foi criado do zero, com página de listagem com filtros por funcionário, obra e status, formulário de cadastro com campo para comprovante e integração automática com a Gestão de Custos. Ao salvar um reembolso, um lançamento de custo é criado automaticamente e o status de pagamento fica visível na listagem. O módulo está disponível apenas para usuários V2, com link próprio na barra de navegação.

---

## Módulo: Cronograma
**Criado em V2**

O módulo de Cronograma foi construído neste ciclo, evoluindo de um Gantt básico até uma ferramenta com catálogo de atividades, templates reutilizáveis e métricas de produtividade.

### Tarefa #4 — Cronograma: Predecessora Inline e Recálculo em Cadeia
**Data de merge:** 04 Abr 2026

A edição da coluna de predecessora no cronograma passou a usar um menu de seleção com as tarefas reais da obra, eliminando a possibilidade de informar uma referência inexistente. Ao confirmar uma predecessora ou alterar a duração de uma tarefa, todas as tarefas dependentes encadeadas são recalculadas automaticamente, respeitando o calendário da empresa. O Gantt é atualizado em tempo real sem recarregar a página.

### Tarefa #6 — Gantt Interativo com Drag & Drop
**Status: CANCELADA**

A funcionalidade de arrastar barras no gráfico Gantt para mover datas e alterar durações foi especificada, mas não implementada neste ciclo. Fica registrada como item para um ciclo futuro.

### Tarefa #17 — Catálogo de Produtividade e Templates de Cronograma
**Data de merge:** 11 Abr 2026

O catálogo de serviços foi estendido com campos de unidade de medida e meta de produtividade por unidade. Foi criada a funcionalidade de Templates de Cronograma: o gestor monta templates nomeados com atividades do catálogo e pode aplicá-los a uma obra para gerar as tarefas automaticamente, com ordem e quantidade prevista herdadas do template.

---

## Módulo: RDO — Relatório Diário de Obras

### Tarefa #13 — Mão de Obra por Subatividade e Custo Automático
**Data de merge:** 09 Abr 2026

O registro de equipe no RDO foi reformulado: cada funcionário é vinculado à subatividade específica em que trabalhou, com campo de horas por atividade. Ao finalizar o RDO, é criado automaticamente um único lançamento de custo por funcionário naquele dia na Gestão de Custos, independentemente de quantas subatividades ele tenha coberto. O sistema garante que re-finalizar um RDO não gere lançamentos repetidos.

### Tarefa #18 — Quantidade Produzida e Índice de Produtividade
**Data de merge:** 12 Abr 2026

O formulário de RDO passou a incluir o campo de quantidade produzida por subatividade. Ao finalizar, o sistema calcula automaticamente o índice de produtividade de cada funcionário alocado: quanto foi produzido por hora em relação à meta do catálogo. A visualização do RDO finalizado exibe badges coloridos de desempenho por funcionário.

---

## Módulo: Produtividade
**Criado em V2**

### Tarefa #19 — Dashboard de Produtividade por Funcionário
**Data de merge:** 13 Abr 2026

Foi criada uma página de acompanhamento de produtividade, com filtros por obra, tipo de serviço, período e funcionário. A tela exibe um ranking de desempenho dos funcionários, gráficos comparando produtividade real com a meta, e cards de resumo com os destaques positivos e negativos da equipe no período. O acesso é restrito a usuários V2.

### Tarefa #25 — Métricas de Produtividade por Funcionário (Perfil Individual)
**Data de merge:** 14 Abr 2026

A fórmula de cálculo de produtividade foi corrigida: o sistema passou a usar a taxa da equipe como base (quantidade produzida ÷ total de horas da equipe naquela subatividade), distribuída proporcionalmente pelas horas individuais de cada funcionário, em vez de dividir o total pela hora de cada pessoa isoladamente. O perfil de cada funcionário passou a exibir sua média ponderada pessoal por subatividade, comparada à média da empresa, com badge de desempenho. O dashboard ganhou linha de referência mostrando a média da empresa nos gráficos.

---

## Módulo: Suprimentos e Almoxarifado

### Tarefa #15 — Reengenharia Suprimentos: Compras + Almoxarifado + Financeiro
**Data de merge:** 10 Abr 2026

O fluxo de reconhecimento de custo de material foi consolidado: o custo passa a ser registrado no momento da compra, não no consumo. Ao registrar uma compra vinculada a uma obra, o sistema baixa o estoque e cria o lançamento financeiro automaticamente. A saída de material do almoxarifado é apenas rastreamento físico, sem novo impacto financeiro. O dashboard de custos passou a exibir material sem duplicações. A tela de compras ganhou painel de status de recebimento por item.

---

## Módulo: Importação de Dados
**Criado em V2**

### Tarefa #28 — Sistema de Importação Excel (5 Módulos)
**Data de merge:** 08 Abr 2026

Foi criado um sistema completo de importação via planilha Excel, cobrindo 5 módulos: Funcionários, Diárias, Alimentação, Transporte e Custos. A página central de importação oferece download do template, upload do arquivo, visualização prévia dos dados (com destaque para linhas válidas e erros) e confirmação da carga. Para funcionários, o sistema reconhece automaticamente dois formatos de planilha diferentes. Cada módulo de importação integra com os respectivos módulos do sistema (Gestão de Custos, Alimentação, Transporte, etc.) ao confirmar.

---

## Módulo: Dashboard

### Tarefa #14 — Dashboard: Custos por Competência
**Data de merge:** 10 Abr 2026

O gráfico de custos por obra foi reformulado para comparar o custo realizado com o orçamento da obra, com indicador percentual de consumo e destaque visual em vermelho quando o orçamento é ultrapassado. O painel de equipe passou a exibir número de funcionários e custo mensal de folha por departamento. O widget de custos recentes foi removido.

---

## Módulo: Portal do Cliente
**Criado em V2**

### Tarefa #45 — Portal do Cliente por Obra
**Data de merge:** 09 Abr 2026

Foi criado o Portal do Cliente, acessível via link único com token, sem necessidade de login. O cliente visualiza o progresso geral da obra, as tarefas do cronograma com percentual de conclusão, os RDOs finalizados e os pedidos de compra pendentes de aprovação. O cliente pode aprovar ou recusar pedidos diretamente pelo portal e fazer upload do comprovante de pagamento. O gestor acompanha o status de aprovação e o comprovante na tela do pedido. A tela de detalhes da obra ganhou card "Portal do Cliente" com link copiável e toggle de ativação.

### Tarefa #46 — Medição Quinzenal de Obra e Contas a Receber
**Data de merge:** 12 Abr 2026

Foi criado o motor de medição quinzenal que calcula automaticamente o valor a faturar com base no progresso registrado no cronograma. O gestor configura os itens comerciais da obra com seus valores, vincula as tarefas do cronograma a cada item com pesos percentuais, e ao fechar a quinzena o sistema calcula o delta de avanço, aplica o abatimento da entrada do cliente e gera o extrato de medição. Uma Conta a Receber é criada automaticamente com o valor a faturar do período. O extrato é gerado em PDF com tabela detalhada por item. O Portal do Cliente exibe as medições com link para download do PDF e status do recebimento.

---

## Módulo: Documentação

### Tarefa #20 — Atualização dos Manuais Financeiro e Almoxarifado
**Data de merge:** 14 Abr 2026

Os manuais do sistema foram atualizados para refletir as mudanças do ciclo V2: fluxo de aprovação em 2 etapas, extinção do módulo Contas a Pagar como entrada de despesas, reconhecimento de custo de material na compra (não na saída) e exibição de múltiplas obras por lançamento na Gestão de Custos.

---

## Em Andamento

### Tarefa #21 — Cronograma V2 Apresentável para Portal do Cliente
**Status:** Em andamento — iniciado em 15 Abr 2026

O gestor poderá gerar um cronograma de apresentação separado, editável livremente, para exibir no portal do cliente sem interferir nos dados internos de gestão. Nomes, datas e percentuais poderão ser ajustados de forma independente. O portal exibirá exclusivamente esse cronograma de apresentação; se não houver registros publicados, mostrará a mensagem "Cronograma em atualização".

---

*Documento gerado em 15/04/2026.*
