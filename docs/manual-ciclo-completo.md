# Manual do Ciclo Completo do Sistema (SIGE v10.0)

> **Para você que vai usar o sistema no dia a dia** — engenheiro, dono
> de obra, administrador de empresa de construção. Este manual não
> exige conhecimento de informática nem de programação. Todos os passos
> têm um exemplo real preenchido (a empresa fictícia **Construtora
> Alfa**, o cliente **João da Silva**, a obra **Residencial Bela
> Vista**) para você seguir junto.

---

## Changelog (atualização de abril/2026 — Tasks #119 → #202)

> Em cima da base v10.0 (Tasks #102 → #118), entre fevereiro e abril
> de 2026 entraram mais 5 mudanças que afetam o uso diário. As seções
> abaixo do manual já refletem o comportamento novo; este resumo é só
> para quem já conhecia a versão anterior.

| Bloco | O que mudou | Por que importa para você |
| --- | --- | --- |
| **Gate de revisão inicial do cronograma na obra (Task #200)** | Quando o cliente aprova a proposta sem que o admin tenha pré-configurado o cronograma, a Obra nasce em estado "cronograma pendente" e a **primeira visita** ao detalhe da obra **redireciona automaticamente** para uma tela `Revisar cronograma inicial` — onde você marca/desmarca subatividades e clica **Confirmar**. Só depois disso a obra abre normalmente. Existe também botão **"Revisar de novo"** na aba Cronograma, que apaga só as tarefas vindas da proposta (preserva tarefas que você criou manualmente) e reabre o gate. | Você nunca mais é jogado dentro de uma obra com cronograma "default" indesejado. Se o cliente aprovou pelo portal sem você ter marcado nada antes, a primeira coisa que você vê é a tela de revisão. Se preferir começar do zero, é só desmarcar tudo e confirmar — a obra fica revisada (sem tarefas) e você cria as etapas manualmente depois. Coberto por `tests/test_cronograma_revisao_obra_gate.py`. |
| **Busca por digitação no fornecedor da Compra (Task #202)** | Em `/compras/nova` os dropdowns de Fornecedor e Obra agora têm **busca por digitação** (Select2). Você clica no campo, digita parte do nome e o sistema filtra. Quando a empresa **ainda não tem nenhum fornecedor cadastrado**, o select é substituído por um aviso amarelo com o link direto para "Cadastrar primeiro fornecedor". O backend rejeita com mensagem clara qualquer fornecedor/obra que não pertença ao seu tenant (proteção contra erro de seleção e contra acesso indevido). | Empresas com 100+ fornecedores podem finalmente encontrar o certo digitando — antes era preciso rolar a lista nativa do navegador. E quem está abrindo o sistema pela primeira vez vê um caminho óbvio para destravar a primeira compra (botão direto pra cadastro de fornecedor). Coberto por `tests/test_compras_nova_dropdown.py`. |
| **Tema visual configurável (Task #191)** | Em **Configurações da Empresa** apareceu uma nova aba "Tema" com 3 presets prontos (Azul Profundo SaaS — padrão; Verde Construção; Grafite Premium) e a opção de ajustar livremente as 4 cores principais (primária, secundária, header/nav e fundo do app). A cor escolhida vale para todas as páginas do sistema, do login ao portal cliente. | Cada empresa pode adaptar o sistema à sua identidade visual sem mexer em código. A escolha fica salva em `ConfiguracaoEmpresa` por tenant — você pode trocar a qualquer momento e a alteração aparece imediatamente. |
| **Portal do cliente mais resistente (Task #195)** | Duas correções no fluxo `POST /propostas/cliente/<token>/aprovar`: (a) o portal não quebra mais se a proposta tiver título vazio (antes dava erro 500 e o cliente não conseguia aprovar); (b) se na proposta o nome do cliente estiver em branco e não houver `cliente_id` válido, o sistema cria automaticamente um cliente sintético (nomeado pelo número da proposta) para que a Obra consiga ser criada — em vez de falhar a aprovação. | Propostas legadas migradas de outros sistemas, sem todos os campos preenchidos, agora podem ser aprovadas normalmente pelo cliente. Aparece um aviso (warning) no log para o admin corrigir o cadastro depois, mas o fluxo do cliente nunca é interrompido. |
| **Limpeza das tabelas legadas de propostas (Task #201)** | A migração 141 dropou 8 tabelas órfãs do antigo modelo de proposta (`proposta`, `proposta_servico`, `item_proposta`, etc.) que existiam no banco mas não eram usadas por nenhum código vivo. As 10 linhas remanescentes da tabela `proposta` foram salvas em `backups/legacy_proposta_2026-04-27.csv` antes do drop. | Mudança 100% interna — invisível pra você. O sistema agora tem **um único** modelo de proposta (`Proposta` em `propostas_comerciais`, com 700+ propostas em produção), eliminando confusão sobre "qual tabela é a verdadeira". Coberto por `tests/test_legacy_propostas_drop.py`. |

### Validação ponta-a-ponta (Task #208)

Todo o ciclo descrito neste manual — Catálogo → Orçamento → Proposta
→ Envio → Portal cliente → Aprovação → Obra → Revisão de cronograma
→ Compra → RDO — foi validado em sessão real de navegador no dia
27/04/2026, exercitando login, formulários, dropdowns Select2,
gate de revisão de cronograma, criação de pedido de compra (R$
760,00 = 20 × 38,00) e geração de RDO. Os 8 contadores finais
fecharam (insumos=2, serviços=1, composições=2, orçamento=1,
proposta=1, obra=1, compra=1, RDO=1). Se algum dos passos abaixo
mostrar comportamento diferente do descrito, é um bug regressivo —
abra um chamado para o time técnico.

---

## Changelog anterior (Tasks #102 → #118)

> A versão anterior do manual documentou o sistema na Task #102
> (cronograma automático na aprovação). Esta versão (v10.0) cobre tudo
> o que entrou entre a #103 e a #118.

| Bloco | O que mudou | Por que importa para você |
| --- | --- | --- |
| **Orçamento (novo capítulo, E06)** | Apareceu uma tela intermediária entre Catálogo e Proposta. Você monta o cálculo internamente, ajusta linha a linha, e só então clica "Gerar proposta". | Você fecha preço com tranquilidade antes de exportar PDF para o cliente. Pode duplicar orçamentos, manter histórico interno. |
| **Override de cronograma por linha do orçamento (Task #118)** | Cada linha do orçamento tem um seletor "Cronograma para esta linha", ao lado do template padrão do serviço. | Quando o serviço do catálogo tem 5 grupos mas esta obra específica só usa 3, você troca o template direto na linha — sem precisar criar um serviço novo. A escolha é propagada para a proposta e materializada quando a obra é criada. |
| **Composição customizada por linha (Task #118)** | Cada linha do orçamento agora abre uma tabelinha onde você pode adicionar/remover insumos e mexer no coeficiente, **sem alterar o catálogo**. | Quando este cliente tem desconto especial num insumo, ou inclui um item extra que não estava na receita-padrão, você ajusta só nesta proposta. Botão "Voltar à composição padrão" desfaz tudo. |
| **Modal "Novo serviço" inline (Task #118)** | Dentro do orçamento, botão "+" abre um pop-up para cadastrar um serviço novo do catálogo sem perder o orçamento aberto. | Se você descobriu no meio do orçamento que falta um serviço (ex.: "Pintura latex"), cria ali e o orçamento já recarrega com o item disponível. |
| **Recálculo em tempo real do orçamento (Task #124)** | Mexeu em coeficiente/preço/quantidade? A coluna "Subtotal/un." e os totais Custo/Venda/Lucro atualizam na hora. | Acabou aquele caso de "alterei o coeficiente mas o subtotal não mexeu" — agora bate na mesma linha. |
| **Alimentação v2 (E13)** | Tela mobile-first com lançamento multi-item, busca de funcionário e rateio entre obras. | Dispara `alimentacao_lancamento_criado` → cria conta a pagar automática. Acabou o lançamento manual em Excel. |
| **Reembolsos v2 (E15)** | CRUD completo para reembolsos integrado ao painel "Gestão de Custos V2". | Cada reembolso aprovado vira conta a pagar sem digitação dupla. |
| **Compras v2 (E16)** | Pedido de compra (PO) com tabela dinâmica de itens; rota separada "Registrar Recebimento". | Receber a mercadoria gera 3 coisas de uma vez: entrada no almoxarifado, conta a pagar para o fornecedor e custo lançado na obra. |
| **Mapa de Concorrência v2 (E18)** | Grade N itens × N fornecedores com edição inline; mínimo destacado em verde. | Comparar 5 fornecedores ficou possível na mesma tela. Cliente pode escolher pelo portal. |
| **Catálogo paramétrico (E04)** | Cada serviço pode ter composição (insumo × coeficiente) versionada e o preço calculado fica visível no rodapé. | Foi a base para o Orçamento. O preço de venda do serviço é calculado a partir dos insumos + imposto + lucro. |
| **Fluxo de Caixa novo (E21)** | Coluna `banco_id` opcional, tela de import preview com categorias agrupadas, edição inline e modal "Novo movimento". | Você importa o extrato bancário, confere as categorias sugeridas, edita o que precisar e confirma. |
| **Ponto Facial (E12)** | Sistema compartilhado de ponto eletrônico por foto, com GPS e geofencing. | Disparado por bater ponto, o evento `ponto_registrado` chama `calcular_horas_folha`, que consolida a folha mensal e gera contas a pagar. |
| Regras herdadas | Continuam valendo: aprovar **não** cria conta a receber. Existe **uma única** conta a receber por obra (`OBR-MED-#####`), alimentada pelas medições. | Se você abrir Contas a Receber e ver só uma linha por obra, é o esperado. |

---

## Como o sistema pensa (leitura obrigatória — 2 minutos)

> *Tudo que você cadastra hoje vai virar dinheiro depois — ou no caixa
> de entrada (cliente paga você) ou no caixa de saída (você paga
> funcionário e fornecedor). Cada cadastro existe para que o sistema
> consiga, sozinho, somar e classificar esse dinheiro nos lugares
> certos.*

A jornada agora passa por **três fases**, com Orçamento entre Catálogo
e Proposta:

```
PRÉ-OBRA ─────────────────────────────────────────────────────────────────
  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐  ┌──────┐
  │ Catálogo │─▶│ Orçamento  │─▶│ Proposta │─▶│ Aprovação  │─▶│ Obra │
  │ (insumos │  │ (interno,  │  │ (PDF p/  │  │ + revisão  │  │ nasce│
  │ + servi- │  │  override  │  │ cliente) │  │ cronograma │  │ com  │
  │ ços)     │  │  + custom) │  │          │  │ (Task #102)│  │tudo)│
  └──────────┘  └────────────┘  └──────────┘  └────────────┘  └───┬──┘
                                                                  │
DURANTE A OBRA ───────────────────────────────────────────────────┼──────
            ┌─────────┬──────────┬─────────────┬─────────┬───────┤
            ▼         ▼          ▼             ▼         ▼       ▼
        ┌───────┐ ┌───────┐ ┌──────────┐ ┌──────────┐ ┌────┐ ┌─────────┐
        │ RDO   │ │ Ponto │ │Alimenta- │ │Transporte│ │Reem│ │Compras  │
        │       │ │facial │ │ção v2    │ │   (VT)   │ │bol-│ │/Almoxa- │
        │       │ │       │ │          │ │          │ │so  │ │rifado   │
        └───┬───┘ └───┬───┘ └────┬─────┘ └────┬─────┘ └─┬──┘ └────┬────┘
            │         │          │            │         │         │
            ▼         ▼          ▼            ▼         ▼         ▼
        ┌────────────────────────────────────────────────────────────┐
        │           CONTAS A PAGAR (consolida todas as origens)      │
        │  evento → handler → CP/CustoObra automático                │
        └────────────────────────────────┬───────────────────────────┘
                                         │
            ┌────────────┐               │
            │  Medição   │   Conta a     │
            │ quinzenal  │──Receber única│      ┌──────────────────┐
            │ (% × valor)│  OBR-MED-####─┴─────▶│  Fluxo de Caixa  │
            └────────────┘                      └──────────────────┘

VISÃO & ANÁLISE ──────────────────────────────────────────────────────────
  ┌────────────┐         ┌──────────────────────────┐
  │ Dashboards │         │ Relatórios (folha,       │
  │ (geral, RH,│         │  horas extras, holerite, │
  │ obra, fin) │         │  extrato medição PDF)    │
  └────────────┘         └──────────────────────────┘
```

**Em uma frase:** você cadastra "receitas prontas" no Catálogo (insumos
e serviços com composição). Monta o **Orçamento** internamente (com
overrides). Gera a **Proposta** para o cliente. Aprova → nasce a
**Obra** com cronograma já montado. Durante a obra, RDO, Ponto Facial,
Alimentação, Transporte, Reembolso, Compras e Almoxarifado disparam
automaticamente **Contas a Pagar**. As Medições quinzenais alimentam
a **única Conta a Receber** da obra. Tudo cai no Fluxo de Caixa.

**Por que importa entender isso:** se em algum momento um número
estiver "errado", quase sempre o sistema fez exatamente o esperado —
só que a intuição do usuário antigo era de um fluxo diferente. O que
vale é o desenho acima.

---

## Sequência completa do ciclo — 25 etapas em 3 partes

> **Cenário-mãe que vai aparecer em todos os passos:**
>
> *A Construtora Alfa fechou com o senhor João da Silva a obra do
> "Residencial Bela Vista" — reforma residencial de 250 m², início em
> 01/05/2026, contrato de R$ 250.000,00. A Alfa tem dois pedreiros:
> Carlos (mensalista, R$ 2.800/mês) e Pedro (diarista, R$ 180/dia).
> Vai usar dois serviços do catálogo (alvenaria e contrapiso), cobrar
> uma taxa de mobilização avulsa e ainda colocar R$ 5.000,00 de
> honorário de projeto.*

Cada etapa abaixo segue o mesmo formato fixo de **8 blocos**:

1. *O que você está fazendo de verdade.*
2. *Por que o sistema pede isso.*
3. *Onde clicar.*
4. *O que aparece na tela.*
5. *Cada campo do formulário (com exemplo).*
6. *Botões disponíveis.*
7. *O que muda depois que você clica.*
8. *Notas de atenção.*

---

# PARTE I — PRÉ-OBRA (E01–E09)

A "fase fria" — você está no escritório, com café, montando a base
para a obra existir.

---

### Etapa 1 — Login do administrador

**1. O que você está fazendo de verdade.** Está dizendo ao sistema que
é o administrador da Construtora Alfa, para que ele libere só os dados
dela.

**2. Por que o sistema pede isso.** Várias empresas usam o mesmo
sistema (multi-tenant). O e-mail e senha são a chave da "sala" da Alfa.

**3. Onde clicar.** Abrir o sistema no navegador → tela de login que
aparece sozinha quando você ainda não está logado.

**4. O que aparece na tela.** Cartão centralizado: logo no topo, dois
campos verticais (e-mail e senha), botão azul largo embaixo, link
"Esqueci a senha" abaixo do botão.


![Tela de login do SIGE](img/manual-ciclo/e01-login.jpg)

**5. Cada campo do formulário.**

| Campo | Tipo | Obrigatório? | Exemplo | Se ficar vazio |
| --- | --- | :---: | --- | --- |
| E-mail | Texto | Sim | `admin@construtoraalfa.com.br` | Volta com aviso "Por favor, faça login para acessar esta página" |
| Senha | Senha (oculta) | Sim | `Alfa@2026` | Idem |

**6. Botões disponíveis.**

- **Entrar** (azul, largura total): se o login bater, leva ao
  Dashboard. Se errar, mostra "Usuário ou senha inválidos".

**7. O que muda depois que você clica em Entrar.** O sistema carrega o
Dashboard com os indicadores da Construtora Alfa do mês atual.
Todos os menus laterais ficam liberados.

**8. Notas de atenção.**

- A sessão fecha sozinha por inatividade.
- "Sessão expirada. Por favor, tente novamente." → faça login de
  novo, nada foi perdido.

---

### Etapa 2 — Catálogos básicos (insumos, fornecedores, clientes)

> *Antes de orçar, a Alfa precisa cadastrar os "ingredientes" que
> entram nos serviços (cimento, bloco cerâmico, hora de pedreiro), os
> fornecedores e os clientes.*

**1. O que você está fazendo de verdade.** Está montando os três
catálogos básicos que alimentam o resto: **Insumos** (matérias-primas
com preço e versionamento), **Fornecedores** (cadastros para Compras,
Cotação e Almoxarifado) e **Clientes** (para as propostas e portais).

**2. Por que o sistema pede isso.** Sem insumos, o serviço não tem
composição → o preço de venda não é calculado. Sem fornecedor, o
pedido de compra não tem para quem ir. Sem cliente, a proposta não
tem destinatário.

**3. Onde clicar.**

- **Insumos:** menu lateral → "Catálogo" → "Insumos" → botão verde
  "+ Novo insumo".
- **Fornecedores:** menu lateral → "Almoxarifado" → "Fornecedores" →
  botão verde "+ Novo fornecedor".
- **Clientes:** menu lateral → "Clientes" → botão verde "+ Novo
  cliente".

**4. O que aparece na tela do insumo.** Form simples com nome,
unidade, categoria, preço base. Após salvar, o histórico de preços
aparece na ficha (cada alteração vira uma versão `PrecoBaseInsumo`).


![Catálogo de insumos](img/manual-ciclo/e02-catalogos-insumos.jpg)

**5. Cada campo do insumo (exemplo "Bloco cerâmico 9x19x19").**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Nome | Texto | Sim | `Bloco cerâmico 9x19x19` |
| Unidade | Dropdown | Sim | `un` |
| Categoria | Dropdown/Texto | Sim | `Material` |
| Preço base (R$) | Numérico | Sim | `1,80` |
| Fornecedor preferencial | Dropdown | Não | `Cerâmica Forte` |

Para fornecedor: nome/razão, CNPJ, contato, e-mail, telefone,
condições padrão de pagamento. Para cliente: nome, CPF/CNPJ, contato,
endereço.

**6. Botões disponíveis.**

- **Salvar** (verde) e **Cancelar** (cinza).
- Na ficha do insumo: **Atualizar preço** (azul) — gera uma versão
  nova do preço sem perder o histórico.

**7. O que muda depois que você salva.**

- O insumo passa a aparecer no autocomplete da composição de
  serviços e da edição de orçamento.
- O fornecedor passa a aparecer em Compras, Mapa de Concorrência
  v2 e Almoxarifado.
- O cliente passa a aparecer em Propostas e Orçamentos.

**8. Notas de atenção.**

- Atualizar preço **não** muda orçamentos antigos — o cálculo é
  congelado por linha quando você grava a composição customizada.
- CNPJ duplicado é rejeitado (regra de unicidade por tenant).

---

### Etapa 3 — Templates de cronograma

> *A Alfa quer reutilizar o "passo a passo" da alvenaria em várias
> obras. Em vez de redesenhar para cada serviço, cria um template
> "Alvenaria — passo a passo" que vira a base do cronograma.*

**1. O que você está fazendo de verdade.** Está criando um molde
hierárquico **Grupo → Subatividade** que será reutilizado por
serviços (e, mais tarde, materializado dentro da obra).

**2. Por que o sistema pede isso.** A Task #102 trouxe a regra
"aprovar a proposta gera o cronograma da obra". Para isso funcionar,
cada serviço precisa apontar para um template. Templates ficam no
nível do tenant — o mesmo template serve para vários serviços.

**3. Onde clicar.** Menu lateral → "Cronograma" → "Templates" → botão
"+ Novo template" (rota `/cronograma/templates/novo`).

**4. O que aparece na tela.** Form com campo de nome e construtor
visual abaixo (lista de grupos arrastáveis, cada um com lista de
subatividades arrastáveis).


![Templates de cronograma](img/manual-ciclo/e03-templates-cronograma.jpg)

**5. Cada campo (exemplo "Alvenaria — passo a passo").**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Nome do template | Texto | Sim | `Alvenaria — passo a passo` |
| Descrição | Textarea | Não | `Aplicado a alvenaria padrão de bloco cerâmico` |
| Grupo (nó) | Inline | Sim | `Preparação` / `Execução` |
| Subatividade (folha) | Inline | Sim | `Marcar bloco` / `Levantar paredes` |
| Horas estimadas/folha | Numérico | Recomendado | `8` |
| Dias estimados/folha | Numérico | Recomendado | `1` |

**6. Botões disponíveis.**

- **Salvar template** (verde): grava a árvore.
- **+ Novo grupo** / **+ Nova subatividade** (azul claro): adiciona
  itens à árvore.
- **Excluir nó** (vermelho ao passar o mouse).
- **Duplicar** (cinza, na lista de templates).

**7. O que muda depois que você salva.**

- O template passa a aparecer no dropdown "Template padrão" ao
  cadastrar/editar serviço (E04) e no dropdown "Cronograma para esta
  linha" do orçamento (E06).
- Templates são **versionáveis na prática**: depois de usados em
  uma obra, o ideal é não editar — duplique e crie uma versão nova.

**8. Notas de atenção.**

- Folha sem horas estimadas → o sistema divide o peso da medição em
  partes iguais entre as folhas marcadas (warning aparece na
  aprovação).
- O mesmo template pode ser usado por vários serviços diferentes —
  reutilize.

---

### Etapa 4 — Catálogo de serviços (composição + template padrão)

> *Cada serviço da Alfa tem três coisas: a "receita" de quanto custa
> fazer 1 m² (composição de insumos), a faixa de imposto/lucro e o
> cronograma-padrão que esse serviço vira quando uma proposta é
> aprovada.*

**1. O que você está fazendo de verdade.** Está montando o
"cardápio" da empresa: para cada serviço, está dizendo (a) quanto
custa fazer 1 m² (a partir dos insumos), (b) qual é a margem e (c)
qual é o cronograma-padrão.

**2. Por que o sistema pede isso.** Sem catálogo, cada proposta vira
trabalho braçal de digitação. Com catálogo + composição + template,
fazer um orçamento novo vira escolher do dropdown e deixar o sistema
calcular tudo.

**3. Onde clicar.**

- Para cadastrar serviço: menu lateral → "Catálogo" → "Serviços" →
  botão verde "+ Novo Serviço".
- Para editar a composição: na lista, clicar no nome → tela
  `/catalogo/servicos/<id>/composicao`.

**4. O que aparece na tela do serviço.**

- **Topo** — dados básicos (nome, unidade, categoria, imposto%, lucro%).
- **Meio** — bloco "Composição": tabela de insumos com coeficiente
  (ex.: para 1 m² de alvenaria, 14 blocos, 0,02 m³ de argamassa, 0,75
  h de pedreiro).
- **Bloco "Cronograma":** campo **"Template padrão"** (dropdown com
  busca) + botões **"Editar template"** e **"Criar novo template"**
  (abrem o construtor em outra aba).
- **Rodapé** — preço calculado: custo unitário, imposto, lucro,
  **preço de venda**.


![Catálogo de serviços](img/manual-ciclo/e04-catalogo-servicos.jpg)

**5. Cada campo (exemplos do "Alvenaria de bloco cerâmico").**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Nome | Texto | Sim | `Alvenaria de bloco cerâmico 9x19x19` |
| Unidade | Dropdown | Sim | `m²` |
| Categoria | Texto/Dropdown | Sim | `Estrutura` |
| Imposto (%) | Numérico | Não | `8` |
| Margem de lucro (%) | Numérico | Não | `15` |
| Composição (insumos) | Tabela | Recomendado | `Bloco × 14 un/m²; Argamassa × 0,02 m³/m²; Pedreiro × 0,75 h/m²` |
| **Template padrão** | Dropdown com busca | **Recomendado** | `Alvenaria — passo a passo` |

**6. Botões disponíveis.**

- **Salvar** (verde): grava e volta para a lista.
- **Recalcular preço** (azul claro): refaz o "Preço de venda
  unitário" com base na composição.
- **+ Adicionar insumo** (verde claro, na composição).
- **Editar/Criar template** (azuis): abrem o construtor em outra aba.

**7. O que muda depois que você salva.**

- O serviço aparece nos autocompletes de Orçamento, Proposta e
  Medição.
- Quando uma proposta com esse serviço for aprovada, o sistema usa
  o "Template padrão" para sugerir o cronograma da obra (a menos
  que o orçamento tenha override).

**8. Notas de atenção.**

- Imposto + Lucro ≥ 100% → erro matemático, preço sai zero.
- Serviço sem template padrão → a obra nasce sem cronograma desse
  ramo (apenas item de medição).
- O mesmo template pode ser usado por vários serviços.

---

### Etapa 5 — Cadastro de funcionários

> *Para tocar o Bela Vista, a Alfa precisa cadastrar Carlos
> (mensalista, R$ 2.800/mês) e Pedro (diarista, R$ 180/dia). Os dois
> recebem por PIX e têm vale-alimentação de R$ 25/dia trabalhado e
> vale-transporte de R$ 12/dia.*

**1. O que você está fazendo de verdade.** Cadastrando as pessoas que
vão trabalhar nas obras, junto com a forma de pagamento de cada uma.

**2. Por que o sistema pede isso.** O cadastro do funcionário é o
ponto de partida para tudo que envolve mão de obra: ponto, RDO,
folha, VT, VA e PIX.

**3. Onde clicar.** Menu lateral → "Funcionários" → botão verde
"+ Novo Funcionário" no canto superior direito (modal `#funcionarioModal`).

**4. O que aparece na tela.** Modal em duas colunas, agrupado em
quatro blocos: Dados pessoais, Dados profissionais, Pagamento e
Foto.


![Lista de funcionários com modal de cadastro](img/manual-ciclo/e05-funcionarios.jpg)

**5. Cada campo do formulário.**

| Campo | Tipo | Obrigatório? | Exemplo Carlos | Exemplo Pedro |
| --- | --- | :---: | --- | --- |
| Nome | Texto | Sim | `Carlos da Silva` | `Pedro Oliveira` |
| CPF | Texto | Sim | `123.456.789-00` | `987.654.321-00` |
| Data de admissão | Data | Sim | `01/05/2026` | `01/05/2026` |
| Tipo de remuneração | Dropdown | Sim | `Salário` | `Diária` |
| Salário | Numérico (R$) | Só se "Salário" | `R$ 2.800,00` | — |
| Valor da diária | Numérico (R$) | Só se "Diária" | — | `R$ 180,00` |
| Função | Dropdown (FK) | Sim | `Pedreiro` | `Pedreiro` |
| Horário de trabalho | Dropdown (FK) | Recomendado | `08h–17h` | `08h–17h` |

**6. Botões disponíveis.** **Salvar** (verde) / **Cancelar** (cinza).

**7. O que muda depois que você clica em Salvar.**

- O funcionário aparece na lista com etiqueta "Mensalista" ou
  "Diarista".
- Já pode ser escolhido como mão de obra em RDO, Ponto Facial,
  Alimentação, Transporte e Reembolso.

**8. Notas de atenção.**

- Diarista sem "Valor da diária" → custo sai zero. Erro mais comum.
- VA/VT são por dia trabalhado: o sistema multiplica automaticamente
  conforme o ponto.
- VA, VT e chave PIX existem como colunas de `funcionario` mas o
  modal não os expõe — preencha via tela de detalhe ou serviço.
- CPF é único por sistema.

---

### Etapa 6 — Orçamento (interno: override + composição customizada)

> *Antes de mandar a proposta para o senhor João, a Alfa monta um
> orçamento interno com 4 itens: 250 m² de alvenaria (com cronograma
> herdado do serviço), 250 m² de contrapiso, uma "Mobilização de obra"
> (cadastrada no modal inline porque não existia no catálogo) e
> R$ 5.000 de honorário de projeto. No item da alvenaria, ela troca
> o template para uma versão expressa e remove um insumo da composição
> (porque negociou com fornecedor próprio).*

**1. O que você está fazendo de verdade.** Está montando o cálculo
interno da venda. O orçamento serve para você fechar o preço com
calma — mexendo em margem, override de cronograma e composição
customizada — antes de gerar o PDF para o cliente.

**2. Por que o sistema pede isso.** Antes do v10, ir direto da
proposta para o cliente impedia ajustes finos. O orçamento
intermediário separa "fechar o preço" de "mostrar para o cliente".

**3. Onde clicar.** Menu lateral → "Orçamentos" → botão verde
"+ Novo orçamento" (rota `/orcamentos/novo`). Após criar, abre a tela
de edição em `/orcamentos/<id>/editar`.

**4. O que aparece na tela.**

- **Topo** — cabeçalho (cliente, número, data, observações, imposto
  global, margem global).
- **Meio** — tabela de itens, com colunas: Serviço, Descrição, Qtd,
  Unidade, Preço unit., **Subtotal/un.**, Imposto%, Margem%,
  **Composição** (sub-tabela expansível), **Cronograma para esta
  linha** (override).
- **Rodapé** — totais: Custo total / Venda total / Lucro total
  (recalculam em tempo real).


![Tela de edição do orçamento](img/manual-ciclo/e06-orcamento-editar.jpg)

**5. Cada campo do item.**

| Campo | Tipo | Exemplo (alvenaria) | Exemplo (mobilização) |
| --- | --- | --- | --- |
| Serviço | Combobox com busca | `Alvenaria de bloco cerâmico` | `Mobilização` (criado pelo modal) |
| Descrição | Texto | preenchida automaticamente | preenchida automaticamente |
| Quantidade | Numérico | `250` | `1` |
| Unidade | Dropdown | `m²` (auto) | `un` (auto) |
| Preço unit. | Numérico (R$) | `145,00` (auto, recalcula) | `1.500,00` |
| Imposto% | Numérico | `8` (herda do serviço) | `8` |
| Margem% | Numérico | `15` (herda do serviço) | `15` |
| **Cronograma para esta linha** | Dropdown com busca | `Alvenaria — versão expressa` (override) | `(usar padrão do serviço)` |

**Composição customizada por linha:** clique no botão "▾ Composição"
da linha. Aparece uma sub-tabela com os insumos do serviço. Você pode:

- **+ Adicionar insumo** (verde claro): inclui um insumo extra só
  nesta linha (ex.: "Aditivo plastificante").
- **Remover insumo** (vermelho na linha): retira o insumo desta
  linha. Pede confirmação.
- **Editar coeficiente**: numérico. Mexer aqui recalcula
  Subtotal/un. e os totais na hora (Task #124).
- **Voltar à composição padrão** (cinza): desfaz todas as alterações
  e volta à composição do catálogo. Pede confirmação.

**6. Botões disponíveis.**

- **Salvar orçamento** (verde): grava o cabeçalho.
- **+ Adicionar item** (verde claro): adiciona linha vazia.
- **+ Novo serviço** (modal inline, azul): abre pop-up com o form
  de novo serviço (`/servicos/novo?embedded=1`). Após salvar,
  o orçamento recarrega e o serviço já aparece no autocomplete.
- **Duplicar item** (cinza): copia a linha atual.
- **Remover item** (vermelho): apaga a linha. Pede confirmação.
- **Duplicar orçamento** (azul, no topo): cria uma cópia inteira
  para variantes.
- **Excluir orçamento** (vermelho, no topo): apaga o orçamento.
- **Gerar proposta** (verde grande, no topo): leva à E07.

**7. O que muda depois que você salva ou edita um item.**

- Cada `OrcamentoItem` guarda o `cronograma_template_override_id`
  (se você escolheu um diferente do padrão do serviço) e o
  `composicao_snapshot` (se você mexeu na composição).
- O preço unit. é recalculado por trás (a partir da composição
  customizada × preço base do insumo na data + imposto + margem).
- Subtotal/un. e os totais Custo/Venda/Lucro atualizam em tempo
  real (Task #124).

**8. Notas de atenção.**

- Modal "+ Novo serviço" usa form aninhado resolvido com o atributo
  HTML5 `form=` — você pode salvar o serviço sem perder o orçamento.
- Override de cronograma é **por linha** — duas linhas do mesmo
  serviço podem ter cronogramas diferentes.
- "Voltar à composição padrão" desfaz add/remove/coeficiente desta
  linha. Não afeta override.
- Mudar preço base do insumo no catálogo **depois** **não** muda
  orçamentos já salvos — o snapshot está congelado.
- Coberto por `tests/test_e2e_orcamento_proposta.py` e
  `tests/test_orcamento_override_e2e.py`.

---

### Etapa 7 — Gerar Proposta a partir do Orçamento

> *A Alfa fechou o preço internamente. Agora clica "Gerar proposta"
> para virar o documento que vai por e-mail para o senhor João.*

**1. O que você está fazendo de verdade.** Está convertendo o
orçamento interno em uma proposta comercial — com PDF, link público
do cliente e número oficial.

**2. Por que o sistema pede isso.** A proposta é o documento
contratual; congelar o cálculo no momento da geração garante que
mudanças futuras de preço não bagunçam propostas antigas.

**3. Onde clicar.** Na tela do orçamento → botão verde **"Gerar
proposta"** no topo (POST `/orcamentos/<id>/gerar-proposta`).

**4. O que aparece na tela.** Após o POST, o sistema redireciona
para o detalhe da proposta recém-criada (`/propostas/<id>`), com
status "Rascunho" ou "Enviada".


![Proposta comercial gerada](img/manual-ciclo/e07-proposta-gerada.jpg)

**5. O que é propagado do orçamento para a proposta.**

| Campo do `OrcamentoItem` | Vai para `PropostaItem` |
| --- | --- |
| `servico_id`, `descricao`, `quantidade`, `unidade`, `preco_unitario` | Idem |
| `cronograma_template_override_id` | Mesmo nome (preserva override) |
| `composicao_snapshot` | Mesmo nome (preserva add/remove/coef) |
| `imposto_pct`, `margem_pct` | Idem |

**6. Botões disponíveis na proposta.**

- **Editar proposta** (azul).
- **Enviar ao cliente** (azul forte): libera o link público.
- **Gerar PDF** (cinza): exporta o documento.
- **Aprovar** (verde): leva à E08.

**7. O que muda depois que você gera.**

- Nasce uma `Proposta` vinculada ao orçamento.
- O cliente pode receber o link e visualizar (sem login).
- O orçamento original continua existindo (auditoria) e fica
  marcado como "convertido em proposta".

**8. Notas de atenção.**

- Gerar de novo a partir do mesmo orçamento cria uma proposta
  **nova**, não substitui a anterior — confira antes de duplicar.
- Itens com serviço de catálogo geram cronograma na hora da
  aprovação (E08); itens **sem serviço** ou **sem template** não
  geram tarefas.

---

### Etapa 8 — Aprovação da proposta + revisão do cronograma

> *O senhor João topou. A Alfa quer ajustar o cronograma sugerido
> antes de fechar — tirar uma subtarefa que não cabe e aumentar as
> horas de outra.*

**1. O que você está fazendo de verdade.** Está dizendo: "Pode criar
a obra, gerar o cronograma deste jeito específico e abrir o portal."

**2. Por que o sistema pede tela de revisão.** Cada serviço tem uma
receita-padrão (ou override do orçamento). Mas cada obra é única.
Esta é sua chance de ajustar antes de tudo virar pedra.

**3. Onde clicar.**

- **Caminho admin:** menu → "Propostas" → linha → botão verde
  **"Aprovar e gerar cronograma"** (rota
  `/propostas/<id>/cronograma-revisar`).
- **Caminho cliente (João):** ele recebe o link público e clica
  "Aprovar proposta" no rodapé. Se você (admin) tinha
  pré-configurado, o sistema usa essa configuração; senão usa a
  default (tudo marcado).

**4. O que aparece na tela de revisão.**

```
┌──────────────────────────────────────────────────────────────────┐
│ Revisão do cronograma — Proposta #2026-001 / João da Silva       │
├──────────────────────────────────────────────────────────────────┤
│ ▼ ☑ Alvenaria de bloco cerâmico  (250 m²) [override: expressa]   │
│       ▼ ☑ Grupo: Preparação                                       │
│             ☑ Marcar bloco e linha de prumo  | 2 dias | 16 h     │
│             ☑ Argamassa de assentamento      | 1 dia  |  8 h     │
│       ▼ ☑ Grupo: Execução                                         │
│             ☑ Levantar paredes               | 5 dias | 40 h     │
│             ☐ Reforço de vergas              | 1 dia  |  8 h     │
│             ☑ Limpeza pós-execução           | 1 dia  |  8 h     │
│ ▼ ☑ Contrapiso desempenado (250 m²) [padrão]                      │
│       ▼ ☑ Grupo: Execução                                         │
│             ☑ Nivelamento / Lançamento / Acabamento               │
│ ⚠ Mobilização de obra — sem template                              │
│       Apenas item de medição será criado.                         │
│ ⓘ Honorário de projeto — sem serviço                              │
│       Não vai virar tarefa do cronograma.                         │
├──────────────────────────────────────────────────────────────────┤
│  [ Cancelar ]  [ Salvar pré-configuração ]  [ Confirmar aprovação│
│                                                e gerar cronograma]│
└──────────────────────────────────────────────────────────────────┘
```


![Tela de revisão do cronograma](img/manual-ciclo/e08-cronograma-revisar.jpg)

**5. Cada elemento.**

| Elemento | Como funciona | Exemplo |
| --- | --- | --- |
| Checkbox do Serviço (raiz) | Desmarcar tira o ramo todo | Desmarque "Contrapiso" e a obra nasce só com alvenaria |
| Checkbox do Grupo | Cascata: desmarca subtarefas | Desmarque "Execução" e somem 3 folhas |
| Checkbox da Subtarefa | Marca/desmarca uma folha | Desmarque "Reforço de vergas" |
| Campo "dias" / "horas" | Numérico inline | De `1` para `2` |
| Tag "[override: ...]" | Indica que veio do orçamento | "expressa" no exemplo da alvenaria |
| Aviso amarelo | Folha sem horas → sistema divide o peso por igual | — |
| Aviso laranja | Serviço sem template → só item de medição | "Mobilização" |
| Aviso azul | Item sem serviço → não gera tarefa | "Honorário" |

**6. Botões disponíveis.**

- **Cancelar** (cinza).
- **Salvar pré-configuração** (azul claro): grava a árvore para
  que, se o cliente aprovar pelo portal, herde esta configuração.
- **Confirmar aprovação e gerar cronograma** (verde grande):
  executa tudo de uma vez (criar obra + itens de medição +
  cronograma 3 níveis + lançamento contábil). Operação **única e
  indivisível** — se algo falhar, tudo é desfeito.

**7. O que muda depois que você confirma.**

- Proposta vira "Aprovada".
- Nasce uma **Obra** com código `OBR-####`, vinculada à proposta,
  link público do portal já ativo.
- Nasce **um item de medição** por item de proposta.
- Nasce o **cronograma de 3 níveis** (Serviço → Grupo →
  Subatividade), respeitando o override do orçamento por linha.
- Cada item de medição ganha vínculo de peso para suas folhas.
- O sistema lança contabilmente a aprovação — mas **não** cria
  conta a receber neste momento.

**8. Notas de atenção.**

- Aprovação é **única e indivisível** — não existe "obra criada
  mas cronograma vazio".
- Reaprovar a mesma proposta não duplica tarefas (tarefas excluídas
  manualmente **não** são recriadas).
- Aprovação pelo portal sem pré-configuração → árvore default.
- Coberto por `tests/test_cronograma_automatico_aprovacao.py` e
  `tests/test_orcamento_override_e2e.py`.

---

### Etapa 9 — Pós-aprovação: verificação da obra

**1. O que você está fazendo de verdade.** Conferindo se tudo o que
era para ser criado realmente foi criado.

**2. Por que importa.** É seu checklist para garantir que o
engenheiro de campo vai abrir a obra e encontrar tudo certo.

**3. Onde clicar.** Menu lateral → "Obras" → linha "Residencial Bela
Vista".

> **⚠️ Atenção (Task #200): gate de revisão de cronograma na 1ª
> visita.** Se você **não** tiver pré-configurado o cronograma na
> Etapa 8 (botão "Salvar pré-configuração" antes do cliente aprovar),
> a primeira vez que você clicar na obra o sistema **redireciona
> automaticamente** para a tela `Revisar cronograma inicial` —
> mesma árvore da Etapa 8, com tudo marcado por padrão. Marque/
> desmarque conforme a obra real e clique **"Confirmar e gerar
> cronograma"** no rodapé. Só **depois disso** o detalhe da obra
> abre normalmente. Se o cliente aprovou pelo portal sem que você
> tenha pré-configurado, esse gate é seu primeiro contato — e é
> intencional. Para revisar de novo no futuro, use o botão
> **"Revisar de novo"** na aba Cronograma da obra (apaga só as
> tarefas vindas da proposta, preserva as que você criou
> manualmente, e reabre o gate).

**4. O que aparece na tela.** Painel da obra com várias abas:
Resumo, Cronograma, Medição comercial, Custos, Contas a Receber,
RDOs, Almoxarifado, Cotação, Compras, Portal.


![Painel da obra](img/manual-ciclo/e09-obra-detalhe.jpg)

**5. Cada aba e o que conferir.**

| Aba | O que conferir | O que esperar |
| --- | --- | --- |
| Resumo | Cliente, valor, código, link | Cliente "João da Silva", valor de contrato, `OBR-####`, link preenchido |
| Cronograma | Tarefas em 3 níveis com etiqueta "📋 do contrato" | Datas começando em 01/05/2026, alvenaria com template "expressa" (override do orçamento) |
| Medição comercial | 4 itens, com vínculo de peso para folhas | Alvenaria/contrapiso ligados; mobilização/honorário sem cronograma |
| Custos | Zerada — não há lançamentos ainda | Tabela vazia |
| Contas a Receber | Zerada (aprovação não cria CR) | Tabela vazia (nascerá só na 1ª medição) |

**6. Botões disponíveis.** **Editar obra** / **Abrir portal do
cliente** / **+ Novo RDO** / **Reaprovar proposta** (idempotente).

**7. O que muda depois.** Nada — esta etapa só lê.

**8. Notas de atenção.**

- "Honorário" aparece como item de medição mas sem cronograma. Se
  quiser cobrar por etapa, lance tarefa avulsa e vincule manual.
- Reaprovar não duplica tarefas existentes; tarefas excluídas
  manualmente **não** são recriadas.

---

# PARTE II — DURANTE A OBRA (E10–E23)

A "fase quente" — pessoas no campo, dinheiro entrando e saindo.

---

### Etapa 10 — Funcionários (alocação e métricas v1/v2)

**1. O que você está fazendo de verdade.** Conferindo as métricas
mensais de cada funcionário (custo, horas, dias trabalhados,
extras, alimentação, reembolsos, almoxarifado em posse).

**2. Por que importa.** É a única tela que mostra o "custo real
total" de cada funcionário, agregando todas as origens.

**3. Onde clicar.** Menu lateral → "Funcionários" → clique no nome
do Carlos ou Pedro → aba "Métricas".

**4. O que aparece na tela.** Cards de KPI no topo (horas trabalhadas,
horas extras, dias pagos, custo MO, custo total) e tabela
detalhando cada origem do custo.


![Perfil do funcionário com métricas](img/manual-ciclo/e10-funcionario-perfil.jpg)

**5. Cada KPI.**

| KPI | Cálculo (modo `salario`) | Cálculo (modo `diaria`) |
| --- | --- | --- |
| Custo mão de obra | `horas × valor_hora + HE × valor_hora × 1,5` | `valor_diaria × dias_pagos + (HE/8) × valor_diaria × 1,5` |
| VA | `valor_va × dias_pagos` | idem |
| VT | `valor_vt × dias_pagos` | idem |
| Alimentação real | Soma de `RegistroAlimentacao` + `AlimentacaoLancamento` + rateio M2M | idem |
| Reembolsos | Soma de reembolsos aprovados | idem |
| Almoxarifado em posse | Saldo de itens consumíveis e serializados em posse | idem |
| **Custo total** | MO + VA + VT + Alimentação + Reembolsos + Almoxarifado | idem |

**6. Botões disponíveis.** **Gerar PDF** (relatório do mês) /
**Filtrar por mês**.

**7. O que muda depois.** Nada — só leitura. Os cálculos rodam
sob demanda em `services/funcionario_metrics.py`.

**8. Notas de atenção.**

- O modo (salário vs diária) respeita override do funcionário sobre
  o tenant (`is_v2_active()`).
- Para evitar double-count, o dashboard usa só `custo_mao_obra` no
  loop por funcionário e agrega os outros componentes via
  agregações de tenant.
- Coberto por `tests/test_e2e_metricas_funcionario.py`.

---

### Etapa 11 — RDO (lança custo de mão de obra automático)

> *Hoje é 02/05/2026. Carlos e Pedro trabalharam 8 h cada na
> subtarefa "Marcar bloco e linha de prumo". Produziram 30 m².*

**1. O que você está fazendo de verdade.** O encarregado preenche
o "Relatório Diário de Obra" — quem trabalhou, em qual subtarefa,
por quantas horas e quanto produziu.

**2. Por que importa.** O RDO é o gatilho que faz o sistema
recalcular medição (e, portanto, conta a receber) e custos da obra
automaticamente.

**3. Onde clicar.** Menu lateral → "RDO" → botão verde "+ Novo
RDO" (rota `/rdo/novo`, form `#formNovoRDO`, action POST
`/salvar-rdo-flexivel`).

**4. O que aparece na tela.** Cabeçalho com data + obra; **Mão de
obra** (lista de funcionários com horas) e **Avanço de
subatividade** (lista de tarefas com quantidade produzida no dia).


![Relatório Diário de Obra (RDO)](img/manual-ciclo/e11-rdo-detalhe.jpg)

**5. Cada campo.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Data | Data | Sim | `02/05/2026` |
| Obra | Dropdown | Sim | `Residencial Bela Vista` |
| Funcionário | Dropdown | Sim | `Carlos da Silva` |
| Horas trabalhadas | Numérico | Sim | `8` |
| Hora extra | Numérico | Não | `0` |
| Subatividade | Dropdown | Sim | `Marcar bloco e linha de prumo` |
| Quantidade produzida | Numérico | Sim | `30` (m²) |

**6. Botões disponíveis.** **Salvar rascunho** / **Finalizar**
(POST `/rdo/<id>/finalizar`) / **Cancelar**.

**7. O que muda depois de finalizar o RDO.**

```
RDO finalizado
    │
    ▼
evento "rdo_finalizado"
    │
    ▼
handler "lancar_custos_rdo" (event_manager.py)
    │
    ├─▶ cria CustoObra (MO) com vínculo ao serviço
    ├─▶ cria entrada em Gestão de Custos V2 (CP) por funcionário
    └─▶ recalcula medição da obra
    │
    ▼
handler "recalcular_medicao_apos_rdo"
    │
    └─▶ atualiza Conta a Receber única OBR-MED-#####
```

- O sistema cria custo de MO para cada funcionário do RDO.
- A subtarefa avança em % conforme produção.
- Conta a receber única da obra é atualizada — sem nova linha.

**8. Notas de atenção.**

- RDO em rascunho não dispara nada. Só "Finalizado" dispara.
- Funcionário sem salário/diária → custo zero.
- Coberto por `tests/test_agrupamento_diarias_rdo.py`.

---

### Etapa 12 — Ponto Facial (folha → conta a pagar)

> *Carlos chega na obra às 7h58, abre o app no celular do encarregado,
> bate ponto pela foto. O sistema reconhece, valida GPS, registra
> entrada. No fim do mês, a folha consolida todas as marcações em
> contas a pagar.*

**1. O que você está fazendo de verdade.** Está usando o sistema de
ponto eletrônico compartilhado: um único dispositivo (tablet/celular
da obra) registra a entrada e saída de qualquer funcionário pela
foto do rosto.

**2. Por que importa.** O ponto é a fonte oficial das horas
trabalhadas para a folha mensal — diferente do RDO, que registra
**execução por tarefa**, o ponto registra a **jornada de presença**.
Os dois alimentam contas a pagar, mas por caminhos diferentes:

| Origem | O que mede | Vira CP por… |
| --- | --- | --- |
| **RDO finalizado** | Horas alocadas a uma subtarefa específica | `lancar_custos_rdo` (cria CP por funcionário, vinculado à obra/serviço) |
| **Ponto facial** | Horas de presença na empresa (ou em uma obra específica) | `calcular_horas_folha` no fechamento mensal (cria lançamento de folha → CP consolidado) |

Em construtoras pequenas, RDO sozinho costuma bastar. Em
construtoras com folha CLT robusta, os dois rodam juntos.

**3. Onde clicar.**

- **Bater ponto:** `/ponto/facial` no dispositivo compartilhado
  (mobile-first).
- **Configurar GPS/geofencing por obra:** `/ponto/configuracao/obra/<obra_id>`.
- **Ver registros:** `/ponto/funcionario/<funcionario_id>` ou
  `/ponto/obra/<obra_id>`.
- **Gerar folha mensal:** menu → "Folha de Pagamento" → "Dashboard"
  (rota `/folha/dashboard`).

**4. O que aparece na tela do ponto facial.** Visão de câmera ao
vivo, retângulo verde no rosto detectado, botão grande "Bater ponto",
indicador de GPS (verde dentro do raio, vermelho fora).


![Tela do ponto facial](img/manual-ciclo/e12-ponto-facial.jpg)

**5. Cada elemento.**

| Elemento | Função |
| --- | --- |
| Visor da câmera | Captura imagem para reconhecimento (DeepFace) |
| Indicador GPS | Verde se dentro do geofence da obra, vermelho fora |
| Botão "Bater ponto" | POST `/ponto/api/registrar-facial` com a foto |
| Mensagem "Carlos da Silva — entrada registrada às 07:58" | Confirmação |

**6. Botões disponíveis.** **Bater ponto** / **Tirar nova foto**.

**7. O que muda depois que você bate o ponto.**

```
Ponto registrado
    │
    ▼
evento "ponto_registrado"
    │
    ▼
(ao fechar o mês) handler "calcular_horas_folha"
    │
    ├─▶ cria FolhaPagamento por funcionário
    └─▶ chama "criar_lancamento_folha_pagamento"
            │
            └─▶ cria CP consolidado (salário + VA + VT + extras)
```

- A foto fica salva como evidência (auditoria).
- O sistema recusa a foto se a qualidade for baixa ou se o GPS
  estiver fora do geofence (configurável por obra).

**8. Notas de atenção.**

- Geofencing é opcional — desligado por padrão, configure em
  `/ponto/configuracao/obra/<obra_id>`.
- O Ponto Facial **não substitui** o RDO — eles convivem (ponto
  para a jornada CLT, RDO para a alocação por tarefa).
- Funcionário precisa ter pelo menos 1 foto facial cadastrada
  (rota `/ponto/funcionario/<id>/fotos-faciais`).

---

### Etapa 13 — Alimentação v2 (multi-item → CP)

> *Na semana, Carlos e Pedro almoçaram 5 vezes no Restaurante do
> Zé (R$ 22 cada refeição). A Alfa lança tudo de uma vez no fim da
> semana.*

**1. O que você está fazendo de verdade.** Lançando refeições
fornecidas pela empresa (almoço, café, jantar) com rateio entre
obras e/ou funcionários, e gerando a conta a pagar para o
restaurante.

**2. Por que importa.** Sem essa tela, o lançamento de alimentação
ficava em planilha solta. O sistema agora consolida tudo, calcula
o rateio e gera a CP automática.

**3. Onde clicar.** Menu lateral → "Alimentação" → "Lançamentos" →
"+ Novo lançamento" (rota `/alimentacao/lancamentos/novo-v2`, a v2
mobile-first).

**4. O que aparece na tela.** Topo: data, restaurante (autocomplete),
obra (autocomplete). Meio: lista dinâmica de itens, cada item com
funcionário (busca), tipo (almoço/café/etc), quantidade e
valor unitário.


![Lançamento de alimentação v2](img/manual-ciclo/e13-alimentacao-novo-v2.jpg)

**5. Cada campo do item.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Data | Data | Sim | `08/05/2026` |
| Restaurante | Dropdown | Sim | `Restaurante do Zé` |
| Obra (rateio) | Dropdown | Sim | `Residencial Bela Vista` |
| Funcionário | Combobox com busca | Sim | `Carlos da Silva` |
| Tipo | Dropdown | Sim | `Almoço` |
| Quantidade | Numérico | Sim | `5` |
| Valor unitário (R$) | Numérico | Sim | `22,00` |

**6. Botões disponíveis.**

- **+ Adicionar item** (verde claro).
- **Remover item** (vermelho).
- **Salvar** (verde): efetiva o lançamento.

**7. O que muda depois que você salva.**

```
AlimentacaoLancamento criado
    │
    ▼
evento "alimentacao_lancamento_criado"
    │
    ▼
handler "criar_conta_pagar_alimentacao" (event_manager.py:1084)
    │
    ├─▶ cria CP no nome do restaurante
    └─▶ rateia o custo entre obras/funcionários
```

- A despesa entra no custo agregado de cada funcionário envolvido
  (E10).
- O restaurante vira credor automático em "Contas a Pagar".

**8. Notas de atenção.**

- O modal aceita rateio M2M (vários funcionários no mesmo
  lançamento).
- Restaurante novo? Cadastre antes em `/alimentacao/restaurantes/novo`.
- A v1 (`/alimentacao/lancamentos/novo`) ainda existe, mas para
  novos lançamentos use a v2.

---

### Etapa 14 — Transporte (vale-transporte → CP)

**1. O que você está fazendo de verdade.** Lançando o
vale-transporte mensal ou diário dos funcionários (por obra ou em
massa).

**2. Por que importa.** O VT vira despesa fixa que entra na folha e
nas contas a pagar.

**3. Onde clicar.** Menu lateral → "Transporte" → "+ Novo
lançamento" (`/transporte/novo`) ou "+ Novo em massa"
(`/transporte/novo-massa`) para lançar várias linhas de uma vez.

**4. O que aparece na tela.** Cabeçalho com data, mês de
competência, obra (opcional). Tabela com funcionário, dias úteis,
valor/dia, total.


![Lançamento de transporte](img/manual-ciclo/e14-transporte-novo.jpg)

**5. Cada campo.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Data | Data | Sim | `01/05/2026` |
| Mês de competência | Dropdown | Sim | `Mai/2026` |
| Funcionário | Dropdown | Sim | `Carlos da Silva` |
| Dias úteis | Numérico | Sim | `22` |
| Valor/dia (R$) | Numérico | Sim | `12,00` |
| Categoria | Dropdown (CRUD em `/transporte/categorias`) | Sim | `VT mensal` |

**6. Botões disponíveis.** **Salvar** / **Cancelar** /
**Excluir** (POST `/transporte/excluir/<id>`).

**7. O que muda depois.**

- Cria entrada em Gestão de Custos V2 vinculada ao funcionário e
  ao mês.
- Vira CP consolidada quando a folha é fechada.
- Aparece no card de "VT" da E10 (métricas do funcionário).

**8. Notas de atenção.**

- Lançamento "em massa" copia o mesmo valor/dia para vários
  funcionários — útil no início do mês.
- Mudar a categoria depois de pago não muda a CP; cancele e
  refaça.

---

### Etapa 15 — Reembolsos v2 (workflow aprovação → CP)

> *Pedro pegou Uber para buscar peça urgente — R$ 45. A Alfa quer
> reembolsar.*

**1. O que você está fazendo de verdade.** Está registrando uma
despesa pessoal que o funcionário pagou em nome da empresa, com
aprovação em duas etapas, e gerando a conta a pagar.

**2. Por que importa.** Workflow auditável (rascunho → solicitado →
autorizado → pago) evita pagamento esquecido ou duplicado.

**3. Onde clicar.** Menu lateral → "Reembolsos" → "+ Novo"
(`/reembolso/novo`).

**4. O que aparece na tela.** Form simples: funcionário, data,
descrição, valor, anexo (foto/recibo), obra (opcional), categoria.


![Novo reembolso](img/manual-ciclo/e15-reembolso-novo.jpg)

**5. Cada campo.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Funcionário | Dropdown | Sim | `Pedro Oliveira` |
| Data | Data | Sim | `12/05/2026` |
| Descrição | Texto | Sim | `Uber p/ buscar válvula urgente` |
| Valor (R$) | Numérico | Sim | `45,00` |
| Obra | Dropdown | Recomendado | `Residencial Bela Vista` |
| Categoria | Dropdown | Sim | `Transporte (urgência)` |
| Anexo | Upload | Recomendado | foto do recibo |

**6. Botões disponíveis.** **Salvar** / **Solicitar aprovação** /
**Editar** (POST `/reembolso/<id>/editar`) / **Excluir** (POST
`/reembolso/<id>/excluir`).

**7. O que muda depois que você aprova/paga.**

- A entrada vai para Gestão de Custos V2 (4 etapas: solicitar →
  autorizar → pagar).
- Quando paga, vira CP no nome do funcionário (PIX cadastrado em
  E05).
- Entra no card "Reembolsos" da E10.

**8. Notas de atenção.**

- Sem anexo, fica no rascunho (regra interna recomendada, não
  obrigatória pelo sistema).
- Reembolso recusado pode ser editado e reenviado.

---

### Etapa 16 — Compras de Materiais v2 (PO + Recebimento → CP + Custo + Estoque)

> *A Alfa precisa de 5.000 blocos. Faz o pedido na Cerâmica Forte
> (R$ 1,80/un, prazo 10 dias). Quando chega, registra o
> recebimento — o sistema gera CP, entrada no almoxarifado e custo
> da obra de uma vez.*

**1. O que você está fazendo de verdade.** Está gerando um pedido
de compra (PO) com tabela dinâmica de itens, e depois registrando
o recebimento físico.

**2. Por que importa.** É o único caminho do v10 que gera, **em uma
única operação**, três coisas: entrada no estoque, CP para o
fornecedor e custo lançado na obra.

**3. Onde clicar.**

- **Novo pedido:** menu lateral → "Compras" → "+ Nova"
  (`/compras/nova`).
- **Aprovação:** `/compras/aprovacao`.
- **Registrar recebimento:** `/compras/<pedido_id>` → botão
  "Registrar recebimento" (POST `/compras/receber/<pedido_id>`).

**4. O que aparece na tela do pedido.** Cabeçalho (fornecedor, obra,
data, condições). Tabela dinâmica de itens (insumo, quantidade,
preço unitário, subtotal). Total no rodapé.

> **Atualização (Task #202).** Os campos **Fornecedor** e **Obra**
> agora têm **busca por digitação**: clique no campo, digite parte
> do nome (ex.: "cerâmi") e a lista filtra na hora. Antes era um
> select nativo do navegador, em que você tinha que rolar a lista
> inteira. Quando a sua empresa **ainda não tem nenhum fornecedor
> cadastrado**, o select de Fornecedor é substituído por um aviso
> amarelo com link direto para "Cadastrar primeiro fornecedor" —
> nesse caso, cadastre o fornecedor primeiro e volte aqui.


![Pedido de compra novo](img/manual-ciclo/e16-compras-nova.jpg)

**5. Cada campo.**

| Campo | Tipo | Exemplo |
| --- | --- | --- |
| Fornecedor | Dropdown com busca por digitação (Select2) — obrigatório | `Cerâmica Forte` |
| Obra | Dropdown com busca por digitação (Select2) | `Residencial Bela Vista` |
| Data | Data | `05/05/2026` |
| Condições de pagamento | Texto | `30 dias` |
| Item — insumo | Combobox com busca | `Bloco cerâmico 9x19x19` |
| Item — quantidade | Numérico | `5000` |
| Item — preço unit. | Numérico | `1,80` |

**6. Botões disponíveis.**

- **+ Adicionar item** (verde claro).
- **Salvar pedido** (verde).
- **Solicitar aprovação** (azul).
- **Registrar recebimento** (verde, na tela do pedido aprovado).
- **Excluir pedido** (vermelho, POST `/compras/excluir/<id>`).

**7. O que muda depois de Registrar Recebimento.**

```
Recebimento registrado
    │
    ├─▶ Almoxarifado: cria entrada de estoque
    │       └─ evento "estoque_entrada_material"
    │           └─▶ handler "lancar_custo_material_obra" (custo na obra)
    │           └─▶ handler "criar_conta_pagar_entrada_material" (CP)
    │
    └─▶ Pedido fica com status "Recebido"
```

- Estoque do almoxarifado cresce (entrada).
- CP do fornecedor é criada com vencimento conforme as condições.
- Custo da obra recebe lançamento vinculado ao serviço.

**8. Notas de atenção.**

- Recebimento parcial: registre só a quantidade que chegou; o
  pedido continua aberto para o restante.
- Excluir um pedido **recebido** não desfaz CP nem estoque —
  cancele a CP e a movimentação manualmente se for o caso.

---

### Etapa 17 — Almoxarifado (saída → custo da obra)

> *O encarregado tirou 14 sacos de cimento do estoque para a obra.
> Cada saco custou R$ 30,00.*

**1. O que você está fazendo de verdade.** Está retirando material
do estoque e vinculando à obra. O sistema gera o custo da obra
automaticamente.

**2. Por que importa.** Sem este lançamento, a margem da obra fica
no chute. Com ele, o custo cai automaticamente em "Gestão de
Custos V2".

**3. Onde clicar.** Menu lateral → "Almoxarifado" → "Saída"
(`/almoxarifado/saida`) → submit POST `/almoxarifado/processar-saida`
(ou `/almoxarifado/processar-saida-multipla` para várias linhas).

**4. O que aparece na tela.** Cabeçalho (data, obra, serviço da
obra, funcionário responsável). Tabela de itens com seleção de
lote/serial quando aplicável.


![Saída de almoxarifado](img/manual-ciclo/e17-almoxarifado-saida.jpg)

**5. Cada campo.**

| Campo | Tipo | Obrigatório? | Exemplo |
| --- | --- | :---: | --- |
| Obra | Dropdown | Sim | `Residencial Bela Vista` |
| Serviço da obra | Dropdown | Recomendado | `Alvenaria de bloco cerâmico` |
| Funcionário (em posse) | Dropdown | Não | `Carlos da Silva` |
| Item | Combobox com busca | Sim | `Cimento CP-II 50 kg` |
| Quantidade | Numérico | Sim | `14` |
| Lote/Serial | Dropdown | Se item lotado/serializado | seleção do lote |

**6. Botões disponíveis.** **Salvar saída** / **+ Nova linha**
(saída múltipla) / **Cancelar**.

**7. O que muda depois.**

- Estoque diminui (com locking otimista para evitar conflito).
- Cria custo de material vinculado à obra/serviço.
- Se for "em posse de funcionário", entra no card "Almoxarifado em
  posse" da E10.

**8. Notas de atenção.**

- Saída sem serviço da obra → custo entra sem vínculo de serviço
  (existe plano de melhoria para corrigir).
- Devolução: rota `/almoxarifado/devolucao`.
- Para CRUD completo de fornecedores: `/almoxarifado/fornecedores`.
- Guia detalhado: `docs/GUIA_NAVEGACAO_ALMOXARIFADO.md`.

---

### Etapa 18 — Cotação + Mapa de Concorrência v2 (N×N + portal)

> *A Alfa quer cotar 5.000 blocos com três fornecedores e mostrar
> para o senhor João escolher qual prefere.*

**1. O que você está fazendo de verdade.** Está montando uma grade
**N itens × N fornecedores** com preços e prazos. O mínimo de cada
linha é destacado em verde. O cliente pode até escolher pelo portal.

**2. Por que importa.** Sem mapa, a escolha fica em e-mail/WhatsApp.
Com ele, há histórico auditável e cliente participa.

**3. Onde clicar.** Aba da obra → "Cotação" → botão "+ Novo mapa
v2" (POST `/obras/<obra_id>/mapa-v2/criar`). Editar:
`/obras/<obra_id>/mapa-v2/<mapa_id>/editar`.

**4. O que aparece na tela.** Tabela com linhas (itens) e colunas
(fornecedores). Cada célula tem preço unit. e prazo (dias). Mínimo
da linha em verde.


![Painel da obra (entrada para o mapa de concorrência)](img/manual-ciclo/e18-obra-mapa-concorrencia.jpg)

**5. Cada campo.**

| Campo | Tipo | Exemplo |
| --- | --- | --- |
| Item | Dropdown / texto | `Bloco cerâmico 9x19x19` |
| Quantidade | Numérico | `5000` |
| Fornecedor 1/2/3 | Dropdown + R$ + dias | `Cerâmica Forte / R$ 1,75 / 10 d` |
| Observação por célula | Texto | `Frete CIF incluído` |

**6. Botões disponíveis.**

- **+ Item** / **+ Fornecedor** (verde claro).
- **Salvar** (verde).
- **Liberar para cliente** (azul): habilita o link do portal.
- **Aprovar fornecedor** (verde escuro).
- **Excluir mapa** (vermelho, POST `/obras/<obra_id>/mapa-v2/<id>/deletar`).

**7. O que muda depois que você aprova.**

- O fornecedor escolhido vira pedido de compra (E16).
- Se foi pelo portal, o cliente recebe confirmação e o admin é
  notificado.

**8. Notas de atenção.**

- O Mapa v1 ainda existe em `/obras/<obra_id>/mapa-concorrencia/novo`
  — para novos mapas, use sempre o v2.
- Cliente escolhe pelo portal via POST
  `/portal/obra/<token>/mapa-v2/<id>/selecionar`.

---

### Etapa 19 — Contas a Pagar (consolida todas as origens)

> *No final do mês, a Alfa abre Contas a Pagar para conferir tudo o
> que precisa ser quitado. Ela vê CP da Cerâmica Forte (compra), do
> Restaurante do Zé (alimentação), do Pedro (reembolso), de cada
> funcionário (folha do ponto facial) e de cada RDO finalizado.*

**1. O que você está fazendo de verdade.** Está visualizando a
consolidação automática de tudo o que virou CP nas etapas
anteriores, e seguindo o workflow de 4 etapas (rascunho →
solicitado → autorizado → pago).

**2. Por que importa.** Em construtoras com vários departamentos, a
pessoa que lança nem sempre é quem aprova nem quem paga. As 4 etapas
travam o fluxo.

**3. Onde clicar.**

- **Lista consolidada:** menu → "Financeiro" → "Contas a Pagar"
  (`/financeiro/contas-pagar`).
- **Painel Gestão de Custos V2 (workflow):** menu → "Custos" →
  "Gestão de Custos V2" (`/gestao-custos/`).
- **Pagar uma conta:** `/financeiro/contas-pagar/<id>/pagar`.
- **Aprovar/Pagar/Estornar no V2:** botões na linha do pai
  (`/gestao-custos/<pai_id>/solicitar`, `/autorizar`, `/pagar`).

**4. O que aparece na tela.** Painel kanban com 4 colunas
(Rascunho / Solicitado / Autorizado / Pago). Cada cartão mostra
valor, fornecedor/funcionário, obra e origem.


![Painel de contas a pagar](img/manual-ciclo/e19-contas-pagar.jpg)

**5. Tabela "origem → conta a pagar" (referência rápida).**

| Origem (etapa) | Evento disparado | Handler | O que vira CP |
| --- | --- | --- | --- |
| RDO finalizado (E11) | `rdo_finalizado` | `lancar_custos_rdo` | CP de MO por funcionário |
| Ponto facial (E12) | `ponto_registrado` (no fechamento mensal) | `calcular_horas_folha` → `criar_lancamento_folha_pagamento` | CP consolidado da folha |
| Alimentação v2 (E13) | `alimentacao_lancamento_criado` | `criar_conta_pagar_alimentacao` | CP no nome do restaurante |
| Transporte (E14) | (no fechamento mensal) | folha consolida | CP no nome do funcionário |
| Reembolso (E15) | aprovação no V2 | workflow Gestão Custos | CP no nome do funcionário |
| Compra recebida (E16) | `estoque_entrada_material` | `criar_conta_pagar_entrada_material` | CP no nome do fornecedor |

**6. Botões disponíveis.**

- **Solicitar** / **Autorizar** / **Pagar** / **Estornar**
  (kanban).
- **Editar** / **Excluir** (só rascunhos).
- **Filtros** por obra, fornecedor, mês, categoria.

**7. O que muda depois que você aprova/paga.**

- Aprovar: o lançamento aparece na previsão do Fluxo de Caixa.
- Pagar: sai da previsão e entra no realizado, baixando do banco.

**8. Notas de atenção.**

- CP sem `banco_id` ainda paga normalmente — o `banco_id` é
  opcional e usado para conciliar com extrato bancário.
- Excluir uma CP que tem origem em RDO/Compra/Alimentação **não**
  desfaz a entrada original — desfaça pela tela de origem.

---

### Etapa 20 — Contas a Receber (única `OBR-MED-#####`)

**1. O que você está fazendo de verdade.** Conferindo a única conta
a receber viva da obra, atualizada automaticamente pelas medições.

**2. Por que importa.** É a regra mais importante do sistema:
**uma e apenas uma** CR por obra, alimentada cumulativamente.

**3. Onde clicar.** Menu → "Financeiro" → "Contas a Receber"
(`/financeiro/contas-receber`). Para registrar recebimento parcial:
`/financeiro/contas-receber/<id>/receber`.

**4. O que aparece na tela.** Tabela com 1 linha por obra
(`OBR-MED-####`), com valor original (acumulado medido), saldo,
status e histórico de recebimentos.


![Painel de contas a receber](img/manual-ciclo/e20-contas-receber.jpg)

**5. Cada coluna.**

| Coluna | O que mostra |
| --- | --- |
| Número | `OBR-MED-####` |
| Cliente | Nome do cliente da obra |
| Valor original | Soma medida acumulada |
| Recebido | Soma dos pagamentos parciais |
| Saldo | `max(0, valor_original − recebido)` |
| Status | PENDENTE → PARCIAL → QUITADA (transição automática) |

**6. Botões disponíveis.** **Receber pagamento** / **Editar** /
**Histórico**.

**7. O que muda depois que você registra recebimento.**

- Saldo diminui.
- Status anda automaticamente.
- Aparece no Fluxo de Caixa (E21) como entrada realizada.

**8. Notas de atenção.**

- Se você ver duas linhas para a mesma obra, é bug — abra ticket.
- Coberto por `tests/test_ciclo_proposta_obra_medido_cr.py`.

---

### Etapa 21 — Fluxo de Caixa (entradas + saídas + import)

**1. O que você está fazendo de verdade.** Olhando o caixa
consolidado: tudo o que entrou (CR pagas pelo cliente) e tudo o
que saiu (CP pagas).

**2. Por que importa.** É o único lugar onde "saldo de caixa" é
real — Contas a Pagar/Receber são previsões, Fluxo é o realizado.

**3. Onde clicar.** Menu → "Financeiro" → "Fluxo de Caixa"
(`/financeiro/fluxo-caixa`).

**4. O que aparece na tela.** Tabela cronológica com
data/origem/categoria/banco/valor. Filtros por banco, categoria,
período. Gráfico mensal no topo.


![Fluxo de caixa](img/manual-ciclo/e21-fluxo-caixa.jpg)

**5. Funcionalidades novas.**

| Funcionalidade | Onde usar |
| --- | --- |
| Filtro por banco | Dropdown no topo (campo `banco_id` opcional na tabela) |
| Modal "Novo movimento" | Botão "+ Novo movimento" → POST `/financeiro/fluxo-caixa/novo` |
| Edição inline | Clique no campo, edite, salva via POST `/financeiro/fluxo-caixa/<id>/editar` |
| Import preview | Menu → "Importação" → "Fluxo de caixa upload" → POST `/importacao/fluxo-caixa/upload` |
| Import confirmar | Após preview, POST `/importacao/fluxo-caixa/confirmar` |
| Rollback de import | POST `/importacao/fluxo-caixa/rollback/<batch_id>` |

**6. Botões disponíveis.** **+ Novo movimento** / **Importar
extrato** / **Editar inline** / **Excluir**.

**7. O que muda depois.**

- Movimento manual entra no realizado.
- Import gera lote (`batch_id`) que pode ser revertido.
- Edição inline atualiza categoria/descrição sem recarregar a página.

**8. Notas de atenção.**

- Formato BRL obrigatório (R$ 1.234,56 com vírgula decimal e ponto
  milhar).
- Import preview agrupa por categoria sugerida — confira antes de
  confirmar.

---

### Etapa 22 — Medição quinzenal (% × valor → atualiza CR)

> *15/05/2026, primeira medição: 70 m² de alvenaria executados.*

**1. O que você está fazendo de verdade.** Consolidando quanto da
obra foi executado nestes 15 dias e gerando a fatura para o cliente.

**2. Por que importa.** A medição é o que vira fatura. E **atualiza
a única conta a receber viva** — não cria nova.

**3. Onde clicar.** Aba "Medição" da obra
(`/obras/<obra_id>/medicao` ou alias `/medicao/obra/<obra_id>`).

**4. O que aparece na tela.** Lista de itens de medição com colunas:
contratada, % desta medição, valor desta medição, % acumulado, valor
acumulado.


![Medição quinzenal da obra](img/manual-ciclo/e22-medicao-quinzenal.jpg)

**5. Cada coluna (exemplo alvenaria).**

| Coluna | Tipo | Exemplo |
| --- | --- | --- |
| Item | Texto | `Alvenaria de bloco cerâmico` |
| Quantidade contratada | Numérico | `250 m²` |
| Quantidade desta medição | Numérico (editável) | `70` |
| % desta medição | Calculado | `28%` |
| Valor desta medição | Calculado (R$) | `R$ 10.150,00` |
| % acumulado | Calculado | `28%` |
| Valor executado acumulado | Calculado (R$) | `R$ 10.150,00` |

**6. Botões disponíveis.**

- **Configurar período da obra:** POST `/obras/<obra_id>/medicao/config`.
- **Gerar medição:** POST `/obras/<obra_id>/medicao/fechar`.
- **Aprovar medição:** POST
  `/obras/<obra_id>/medicao/<medicao_id>/aprovar`.
- **Gerar PDF** (extrato).

**7. O que muda depois de aprovar a medição.**

- Soma o valor medido acumulado de todos os itens.
- A CR única `OBR-MED-####` é atualizada (UPSERT — atualiza, não
  duplica).
- Status anda PENDENTE → PARCIAL → QUITADA conforme o cliente paga.

**8. Notas de atenção.**

- *"Lancei medição mas não vi CR nova."* É o esperado — a linha
  única teve o valor aumentado.
- O extrato PDF tem cabeçalho personalizado com o logo da empresa.

---

### Etapa 23 — Portal do Cliente (token: cronograma + mapa + recibos)

**1. O que você está fazendo de verdade.** Validando o que o senhor
João vê no link público que recebeu por e-mail.

**2. Por que importa.** É o "rosto" da Alfa para o cliente — e o
canal pelo qual ele aprova compras, escolhe fornecedores e envia
comprovantes.

**3. Onde acessar.** Link gerado na aprovação (E08), copiável do
"Resumo" da obra. Rota base: `/portal/obra/<token>`.

**4. O que aparece para o cliente.** Página única vertical:
cabeçalho da obra, cronograma com %, mapa de concorrência (se
liberado), histórico de evolução, medições, painel estratégico,
**aprovação de compras** (novo), **upload de comprovante** (novo).


![Portal do cliente (token público)](img/manual-ciclo/e23-portal-cliente.jpg)

**5. Cada seção e ação.**

| Seção | Interação |
| --- | --- |
| Cabeçalho | Apenas leitura |
| Cronograma | Apenas leitura |
| Mapa de Concorrência v2 | POST `/portal/obra/<token>/mapa-v2/<id>/selecionar` |
| Mapa v1 (legado) | POST `/portal/obra/<token>/mapa/<id>/aprovar` |
| Compras | POST `/portal/obra/<token>/compra/<id>/aprovar` ou `/recusar` |
| Comprovante de pagamento | POST `/portal/obra/<token>/compra/<id>/comprovante` (upload) |
| Medições | Botão "Baixar PDF" |
| RDO público | GET `/portal/obra/<token>/rdo/<id>` |

**6. Botões disponíveis para o cliente.** Aprovar/Recusar compra,
Selecionar fornecedor, Upload de comprovante, Baixar PDF.

**7. O que muda quando o cliente interage.**

- Aprovação de compra → notificação para o admin, libera para
  recebimento (E16).
- Comprovante → fica anexo na CR e dispara fluxo de baixa.

**8. Notas de atenção.**

- O link é único e não exige login do cliente — não compartilhe em
  grupos abertos.
- Para ligar/desligar o portal: POST
  `/portal/obra/<obra_id>/portal-toggle`.

---

# PARTE III — VISÃO E ANÁLISE (E24–E25)

A "fase de leitura" — onde você toma decisão a partir dos números.

---

### Etapa 24 — Dashboards (geral, financeiro, RH, obra)

**1. O que você está fazendo de verdade.** Lendo os indicadores
consolidados da empresa, da obra e dos funcionários.

**2. Por que importa.** Sem dashboard, decisões viram opinião. Com
dashboard, viram dados.

**3. Onde clicar (cada dashboard tem sua rota).**

| Dashboard | Rota | O que mostra |
| --- | --- | --- |
| **Geral** | `/dashboard` | KPIs do tenant: faturamento, custos, propostas em aberto, obras ativas |
| **Financeiro** | `/financeiro/contas-pagar` (filtros) e `/financeiro/fluxo-caixa` | CP/CR, fluxo realizado vs previsto |
| **Folha** | `/folha/dashboard` | Custo de folha por mês, comparativo |
| **Alimentação** | `/alimentacao/dashboard` | Gasto por restaurante / por funcionário |
| **Frota** | `/frota/dashboard` | TCO por veículo, alertas de manutenção |
| **Almoxarifado** | `/almoxarifado/` | Saldo de itens, itens em posse, estoque mínimo |
| **Contabilidade** | `/contabilidade/dashboard` | Lançamentos contábeis, balancete |
| **Custos** | `/gestao-custos/` | Workflow 4 etapas, filtros por obra |

**4. O que aparece em cada um.** Cards de KPI no topo + gráficos +
tabela detalhada com filtros.


![Dashboard geral](img/manual-ciclo/e24-dashboard.jpg)

**5. Cada KPI principal do dashboard geral.**

| KPI | De onde vem | Atualização |
| --- | --- | --- |
| Faturamento do mês | Soma das CR recebidas | Tempo real |
| Custos do mês | Soma das CP pagas | Tempo real |
| Propostas em aberto | Contagem de propostas com status `enviada` ou `rascunho` | Tempo real |
| Obras ativas | Contagem de obras com status `em_andamento` | Tempo real |
| Margem do mês | Faturamento − Custos | Tempo real |

**6. Botões disponíveis.** Filtros por mês, obra, funcionário.
Exportações (alguns dashboards têm botão "Exportar Excel").

**7. O que muda depois.** Nada — dashboards são leitura.

**8. Notas de atenção.**

- O dashboard geral usa apenas `custo_mao_obra` no loop por
  funcionário e agrega VA/VT/Alimentação/Almoxarifado em camada
  separada (evita double-count).
- Coberto pela proteção `UnboundLocalError: propostas_aprovadas`
  (correção em planejamento na lista de tarefas atuais).

---

### Etapa 25 — Relatórios (existentes + a criar)

**1. O que você está fazendo de verdade.** Gerando documentos
oficiais (PDF/Excel) que vão para o cliente, contador ou auditoria.

**2. Por que importa.** Relatório é a saída formal — diferente do
dashboard, ele tem cabeçalho, assinatura e versão arquivada.

**3. Relatórios que já existem.**

| Relatório | Rota | O que entrega |
| --- | --- | --- |
| **Holerite individual** | `/folha/relatorios/holerite/<folha_id>` | PDF do holerite mensal do funcionário |
| **Folha analítica** | `/folha/relatorios/analitico/<ano>/<mes>` | Excel com todos os funcionários |
| **Folha — listagem** | `/folha/relatorios` | Painel para escolher mês e funcionário |
| **Extrato de medição** | botão "Gerar PDF" na E22 | PDF assinável com fotos e itens medidos |
| **Almoxarifado — relatórios** | `/almoxarifado/relatorios` | Saldo, movimentação, em posse |
| **Ponto — relatório por obra** | `/ponto/relatorio/obra/<obra_id>` | Marcações + horas no período |
| **Contabilidade** | `/contabilidade/relatorios` | DRE, balancete, livro diário |
| **Horas extras (funcional)** | `relatorios_funcionais.py` | Horas extras por funcionário no período |

**4. Relatórios a criar (TODO — escopo definido, falta implementar).**

| Relatório | Justificativa | Status |
| --- | --- | --- |
| **Análise de margem por obra (PDF)** | Hoje só existe o dashboard; cliente final pede PDF arquivável | TODO |
| **Comparativo orçado vs realizado por serviço** | Existe a tela de custos mas não o PDF assinável | TODO |
| **Resumo de medições do ano** | Hoje só medição por medição; falta o agregado anual | TODO |
| **Conciliação bancária por banco** | Fluxo já tem `banco_id` mas não o relatório dedicado | TODO |
| **Auditoria do portal do cliente** | Quando o cliente aprovou o quê, no portal | TODO |


![Painel de relatórios da folha](img/manual-ciclo/e25-relatorios-folha.jpg)

**5. Cada campo do gerador.** Cada relatório tem seus filtros (mês,
obra, funcionário, período). PDFs são gerados via
`pdf_generator.py` com cabeçalho dinâmico (logo + cores da empresa).

**6. Botões disponíveis.** **Gerar PDF** / **Gerar Excel** /
**Filtrar**.

**7. O que muda depois.** Nada (geração é leitura).

**8. Notas de atenção.**

- PDFs ficam no servidor por algum tempo, mas é boa prática salvar
  uma cópia local depois de baixar.
- Para criar um relatório novo, o caminho é via `relatorios.html`
  ou subdiretório `templates/relatorios/`.

---

## FAQ — Perguntas reais que aparecem no dia a dia

**1. Lancei o RDO mas o custo de mão de obra não apareceu, e agora?**

Verifique se o RDO foi efetivamente colocado em **"Finalizado"** (não
basta salvar como rascunho). Só essa transição dispara o lançamento
(evento `rdo_finalizado` → handler `lancar_custos_rdo`). Se o RDO já
está finalizado e o custo continua zerado, abra o funcionário e
confirme: para mensalistas, precisa ter "Salário"; para diaristas,
precisa ter "Valor da diária".

**2. Por que a medição não criou uma conta a receber nova?**

Porque é o esperado. Existe **uma única** CR viva por obra
(`OBR-MED-####`). A medição **atualiza** essa linha — não cria
outra.

**3. Aprovei a proposta sem revisar o cronograma — como ajustar
depois?**

A obra já foi criada com a árvore default. Vá na aba "Cronograma" da
obra, exclua as tarefas que não fazem sentido (com a etiqueta
"📋 do contrato" o sistema pede confirmação extra) e/ou crie tarefas
novas. Mudanças não desfazem o vínculo de medição já criado.

**4. Cliente aprovou pelo portal antes de eu revisar — o que
acontece?**

A obra é criada com a árvore default. Da próxima vez, use "Salvar
pré-configuração" na tela de revisão **antes** de mandar o link.

**5. Tentei aprovar e apareceu "Falha ao aprovar a proposta. Nada
foi gravado." — perdi tudo?**

Não. A aprovação é atômica: como algum passo falhou (subatividade
sumiu, template excluído, etc.), o sistema desfez tudo. A proposta
continua em aberto.

**6. Mudei o preço de um insumo no catálogo e propostas antigas
ficaram com valor errado?**

Não ficaram. O sistema guarda uma "foto" do cálculo no momento da
gravação. Mudar agora afeta apenas propostas novas.

**7. Onde vejo "quanto recebi" desta obra?**

Aba "Medição comercial" da obra → coluna "Valor recebido". Ou
"Financeiro → Contas a Receber" → linha `OBR-MED-####` → "Valor
recebido".

**8. Cadastrei o template, mas a aprovação não criou tarefas para
um serviço específico — por quê?**

Três motivos: (a) o serviço **não tem "Template padrão"** preenchido;
(b) você **desmarcou tudo** desse serviço na tela de revisão; (c) o
item da proposta foi digitado livre, sem escolher serviço.

**9. (Novo) Mexi na composição customizada por linha do orçamento e
quero voltar ao padrão do catálogo. Como faço?**

Na linha do orçamento → expanda a sub-tabela "Composição" → botão
**"Voltar à composição padrão"** (cinza). Pede confirmação. Desfaz
todas as alterações de add/remove/coeficiente **só dessa linha**.
Não afeta override de cronograma nem outras linhas.

**10. (Novo) Por que o RDO e o Ponto Facial geram contas a pagar?
São lançamentos duplicados?**

Não, são complementares:

- **RDO** (E11) = custo da **execução por tarefa**: dispara CP por
  funcionário/serviço. Útil para saber "quanto custou cada
  subatividade".
- **Ponto Facial** (E12) = custo da **jornada de presença**: vai
  para a folha mensal e dispara CP consolidado da folha (salário +
  VA + VT + extras). Útil para a contabilidade CLT.

Construtoras pequenas costumam usar só RDO. Construtoras com folha
robusta usam os dois — sem double-count, porque o handler de folha
consolida a jornada e o handler de RDO consolida a alocação por
obra.

**11. (Novo) Recebi parcial uma compra (chegaram 3.000 dos 5.000
blocos). Como registrar?**

Em "Compras" → entre no pedido → "Registrar recebimento": informe
**3.000** como quantidade recebida. O pedido continua aberto para
os 2.000 restantes. Cada recebimento gera entrada de estoque + CP
parcial + custo da obra parcial.

**12. (Novo) Lancei uma saída de almoxarifado mas não virou conta a
pagar — está errado?**

Não. **Saída de almoxarifado é custo da obra, não conta a pagar.**
A CP foi gerada lá atrás, no recebimento da compra (E16). A saída
apenas tira do estoque e lança como custo na obra. Quem virou CP
para o fornecedor foi o recebimento.

**13. Como faço a Alfa importar 30 funcionários de uma vez?**

Menu → "Importação" → baixe o template oficial, preencha em casa,
suba o arquivo, confira a pré-visualização e "Confirmar importação".
Linhas com erro vêm destacadas em vermelho.

**14. Excluí uma tarefa "📋 do contrato" sem querer. Quebrei o
sistema?**

Não. A medição daquele serviço pode ficar com peso desbalanceado
(menos folhas, peso da folha excluída se redistribui). Reaprove a
proposta — mas atenção: a regra de não duplicação só vale para o
que ainda existe; tarefas excluídas **não** são recriadas.

---

## Anexo técnico (opcional, para o time de TI)

> Este bloco é referência rápida para administradores técnicos;
> **não é necessário ler para usar o sistema**.

### Eventos automáticos do sistema (`event_manager.py`)

| Quando acontece | Evento | Handler | O que o sistema faz |
| --- | --- | --- | --- |
| Aprovação confirmada (E08) | `proposta_aprovada` | `propagar_proposta_para_obra` | Cria Obra (`OBR-####`), token cliente, valor de contrato, abre portal, cria itens de medição, cronograma 3 níveis. **Não cria CR.** |
| RDO finalizado (E11) | `rdo_finalizado` | `lancar_custos_rdo` | Cria custo MO automático; vincula ao serviço. |
| RDO finalizado (E11) | `rdo_finalizado` | `recalcular_medicao_apos_rdo` | Atualiza CR única (UPSERT). |
| Ponto registrado (E12) | `ponto_registrado` | `calcular_horas_folha` (no fechamento) | Consolida horas → folha. |
| Folha gerada | `folha_pagamento_criada` | `criar_lancamento_folha_pagamento` | CP consolidada (salário + VA + VT + extras). |
| Alimentação criada (E13) | `alimentacao_lancamento_criado` | `criar_conta_pagar_alimentacao` | CP no nome do restaurante; rateio M2M. |
| Compra recebida (E16) | `estoque_entrada_material` | `lancar_custo_material_obra` | Custo na obra (vinculado ao serviço). |
| Compra recebida (E16) | `estoque_entrada_material` | `criar_conta_pagar_entrada_material` | CP no nome do fornecedor. |
| Combustível lançado | `combustivel_lancado` | `lancar_custo_combustivel` | Custo na obra/veículo. |

### Conta a receber única

- Uma e apenas uma por obra: `origem_tipo='OBRA_MEDICAO'`,
  `numero_documento='OBR-MED-####'`.
- `valor_original` = valor medido acumulado.
- `saldo = max(0, valor_medido − valor_recebido)`.
- `status` flui PENDENTE → PARCIAL → QUITADA.

### Métricas de funcionários (`services/funcionario_metrics.py`)

| Modo | Mão de obra |
| --- | --- |
| `salario` (v1) | `horas × valor_hora + HE × valor_hora × 1.5` |
| `diaria` (v2) | `valor_diaria × dias_pagos + (HE / 8) × valor_diaria × 1.5` |

**Custo total** = MO + VA × dias_pagos + VT × dias_pagos +
Alimentação real (híbrida v1+v2+M2M) + Reembolsos + Almoxarifado em
posse.

### Cobertura de teste do ciclo

- `tests/test_cronograma_automatico_aprovacao.py` — cronograma
  automático na aprovação.
- `tests/test_ciclo_proposta_obra_medido_cr.py` — ciclo financeiro
  pós-aprovação, regra da CR única.
- `tests/test_e2e_orcamento_proposta.py` — catálogo paramétrico →
  aprovação cliente.
- `tests/test_orcamento_override_e2e.py` — override + composição
  customizada (Tasks #118/#120).
- `tests/test_e2e_metricas_funcionario.py` — métricas v1+v2.
- `tests/test_agrupamento_diarias_rdo.py` — agrupamento de diárias
  por RDO.

---

# Anexo A — Modo Agente (operação dirigida via dataset Alfa)

> **Propósito.** Permitir que um operador (humano ou agente
> automatizado) reproduza o ciclo de ponta a ponta a partir de um
> estado conhecido. O dataset "Construtora Alfa" é semeado por
> `scripts/seed_demo_alfa.py`.

## A.1 — Como rodar o seed

### Em desenvolvimento (Replit / local)
```bash
# Plantar (no-op se admin Alfa já existe)
python3 scripts/seed_demo_alfa.py

# Forçar replantio
python3 scripts/seed_demo_alfa.py --reset
```

### Em produção (acionamento consciente)
Auto-seed em produção está **desligado por padrão** desde a Task #108.
Para acionar manualmente:
```bash
SIGE_ALLOW_PROD_SEED=1 \
  python3 /app/scripts/seed_demo_alfa.py --ambiente prod
```
Se o admin Alfa já existir e `--reset` não for passado, o script aborta
com **exit 2**.

## A.2 — Credenciais publicadas (Construtora Alfa)

| Campo               | Valor                                  |
|---------------------|----------------------------------------|
| URL de login (dev)  | `http://localhost:5000/login`          |
| URL de login (prod) | `https://construtoraalfa.estruturasdoval.com.br/login` |
| E-mail              | `admin@construtoraalfa.com.br`         |
| Senha               | `Alfa@2026`                            |
| Cliente PF          | João da Silva — CPF `123.456.789-09`   |
| Funcionário 1       | Carlos Pereira — mensalista R$ 2.800   |
| Funcionário 2       | Pedro Souza   — diarista  R$ 180/dia   |
| Proposta            | nº `001.26`                            |
| Obra                | `OBR-2026-001` — Residencial Bela Vista|

## A.3 — URL por etapa (25 etapas do ciclo)

| # | Etapa                            | Método | URL                                               |
|---|----------------------------------|--------|----------------------------------------------------|
| 1 | Login                            | GET/POST | `/login`                                       |
| 2 | Catálogos básicos                | GET    | `/catalogo/insumos` ; `/almoxarifado/fornecedores` ; `/clientes` |
| 3 | Templates de cronograma          | GET    | `/cronograma/templates` (criar: `/cronograma/templates/novo`) |
| 4 | Catálogo de serviços             | GET    | `/catalogo/servicos` (composição: `/catalogo/servicos/<id>/composicao`) |
| 5 | Cadastro de funcionário          | POST   | `/funcionarios` (modal `#funcionarioModal`)        |
| 6 | Orçamento                        | GET/POST | `/orcamentos/` ; `/orcamentos/novo` ; `/orcamentos/<id>/editar` |
| 7 | Gerar Proposta                   | POST   | `/orcamentos/<id>/gerar-proposta`                  |
| 8 | Aprovação + revisão              | GET/POST | `/propostas/<id>/cronograma-revisar` ; `/propostas/aprovar/<id>` |
| 9 | Obra criada                      | GET    | `/obras/<obra_id>`                                 |
|10 | Métricas funcionário             | GET    | `/funcionarios/<id>` (aba métricas)                |
|11 | RDO                              | GET/POST | `/rdo/novo` ; `/salvar-rdo-flexivel` ; `/rdo/<id>/finalizar` |
|12 | Ponto Facial                     | GET/POST | `/ponto/facial` ; `/ponto/api/registrar-facial`  |
|13 | Alimentação v2                   | GET/POST | `/alimentacao/lancamentos/novo-v2`               |
|14 | Transporte                       | GET/POST | `/transporte/novo` ou `/transporte/novo-massa`   |
|15 | Reembolso                        | GET/POST | `/reembolso/novo`                                |
|16 | Compra (PO + Recebimento)        | GET/POST | `/compras/nova` ; `/compras/receber/<pedido_id>` |
|17 | Almoxarifado — saída             | GET/POST | `/almoxarifado/saida` ; `/almoxarifado/processar-saida` |
|18 | Mapa de Concorrência v2          | POST   | `/obras/<obra_id>/mapa-v2/criar`                   |
|19 | Contas a Pagar                   | GET    | `/financeiro/contas-pagar` ; `/gestao-custos/`     |
|20 | Contas a Receber                 | GET    | `/financeiro/contas-receber`                       |
|21 | Fluxo de Caixa                   | GET/POST | `/financeiro/fluxo-caixa` ; `/financeiro/fluxo-caixa/novo` |
|22 | Medição quinzenal                | GET/POST | `/obras/<obra_id>/medicao` ; `/obras/<obra_id>/medicao/fechar` ; `/obras/<obra_id>/medicao/<med_id>/aprovar` |
|23 | Portal do Cliente                | GET/POST | `/portal/obra/<token>` (ações: `/compra/<id>/aprovar`, `/mapa-v2/<id>/selecionar`, `/compra/<id>/comprovante`) |
|24 | Dashboards                       | GET    | `/dashboard` ; `/folha/dashboard` ; `/alimentacao/dashboard` ; `/almoxarifado/` |
|25 | Relatórios                       | GET    | `/folha/relatorios` ; `/almoxarifado/relatorios` ; `/contabilidade/relatorios` ; `/ponto/relatorio/obra/<id>` |

## A.4 — Mapas "Rótulo → name/id → tipo" para os formulários centrais

### A.4.1 — Funcionário (modal `#funcionarioModal`, action `POST /funcionarios`, `enctype=multipart/form-data`)

| Rótulo                        | `name`                     | Tipo                 |
|-------------------------------|----------------------------|----------------------|
| Nome completo                 | `nome`                     | `text` required      |
| CPF                           | `cpf`                      | `text` required      |
| Foto                          | `foto`                     | `file`               |
| Data de admissão              | `data_admissao`            | `date`               |
| **Tipo de remuneração**       | `tipo_remuneracao`         | `select`             |
| Salário fixo                  | `salario`                  | `number step=0.01`   |
| Valor da diária               | `valor_diaria`             | `number step=0.01`   |
| Função                        | `funcao_id`                | `select` (FK)        |
| Horário de trabalho           | `horario_trabalho_id`      | `select` (FK)        |
| Ativo                         | `ativo`                    | `checkbox`           |

> `valor_va`, `valor_vt` e `chave_pix` existem na tabela mas não no
> modal — preencha via service ou edição posterior.

### A.4.2 — Serviço (`templates/servicos/editar.html`, `POST /servicos`)

| Rótulo                         | `name`                      | Tipo            |
|--------------------------------|-----------------------------|-----------------|
| Nome                           | `nome`                      | `text` required |
| Categoria                      | `categoria`                 | `select`        |
| **Template padrão (cronograma)** | `template_padrao_id`      | `select`        |
| Composição (insumo × coef)     | via `/catalogo/servicos/<id>/composicao/add` | `text` |

### A.4.3 — Orçamento (`templates/orcamentos/editar.html`)

| Rótulo (cabeçalho)            | `name`                      | Tipo           |
|-------------------------------|-----------------------------|----------------|
| Cliente                       | `cliente_id`                | `select` (FK)  |
| Número                        | `numero`                    | `text`         |
| Data                          | `data`                      | `date`         |
| Imposto global %              | `imposto_global`            | `number`       |
| Margem global %               | `margem_global`             | `number`       |

| Rótulo (item, linha repetida) | `name`                                  | Tipo                |
|-------------------------------|-----------------------------------------|---------------------|
| Serviço                       | `item_servico_id`                       | `select`            |
| Descrição                     | `item_descricao`                        | `text`              |
| Quantidade                    | `item_quantidade`                       | `number step=0.01`  |
| Unidade                       | `item_unidade`                          | `select`            |
| Preço unit.                   | `item_preco_unitario`                   | `number step=0.01`  |
| Imposto%                      | `item_imposto`                          | `number`            |
| Margem%                       | `item_margem`                           | `number`            |
| **Cronograma para esta linha**| `cronograma_template_override_id`       | `select`            |
| Composição (insumo)           | `comp_insumo_<i>`                       | `select`            |
| Composição (coeficiente)      | `comp_coef_<i>`                         | `number step=0.0001`|
| Subtotal/un. (coluna calculada) | `<td class="js-subtotal-unit">`        | leitura             |
| **Voltar à composição padrão**| `POST /orcamentos/itens/<id>/reset-composicao` | submit       |
| Modal "+ Novo serviço"        | `embedded=1` no GET, hidden no POST     | iframe modal        |

### A.4.4 — Cronograma (revisão pré-aprovação, `templates/propostas/cronograma_revisar.html`)

| Rótulo                      | `name`                                       | Tipo       |
|-----------------------------|----------------------------------------------|------------|
| Marcar / desmarcar nó       | `marcado_<proposta_item_id>_<no_id>`         | `checkbox` |
| Horas estimadas (override)  | `horas_<proposta_item_id>_<no_id>`           | `number`   |
| Duração em dias (override)  | `duracao_<proposta_item_id>_<no_id>`         | `number`   |
| Confirmar e aprovar         | `button[name=acao][value=aprovar]`           | `submit`   |

### A.4.5 — RDO (`templates/rdo/novo.html`, form `#formNovoRDO`, `POST /salvar-rdo-flexivel`)

| Rótulo                                 | `name` / `id`                                  | Tipo                |
|----------------------------------------|------------------------------------------------|---------------------|
| Funcionário logado (oculto)            | `funcionario_id`                               | `hidden`            |
| Obra                                   | `obra_id` (`select#obra_id`)                   | `select`            |
| Data do relatório                      | `data_relatorio` (`input#data_relatorio`)      | `date`              |
| Tarefas do cronograma                  | `cronograma_tarefa_<tarefa_id>`                | `checkbox`/`number` |
| Horas por funcionário × subatividade   | `func_<subId>_<funcId>_horas`                  | `number step=0.5`   |
| Fotos                                  | `fotos[]`                                      | `file multiple`     |

Finalizar: POST `/rdo/<rdo_id>/finalizar` (sem corpo).

### A.4.6 — Medição quinzenal (`templates/medicao/gestao_itens.html`)

| Rótulo / ação                     | Selector                                                        | Endpoint Flask                          |
|-----------------------------------|-----------------------------------------------------------------|------------------------------------------|
| Período — início (gerar)          | `form[action*="/medicao/fechar"] input[name=periodo_inicio]`    | POST `/obras/<obra_id>/medicao/fechar`  |
| Período — fim (gerar)             | `form[action*="/medicao/fechar"] input[name=periodo_fim]`       | idem                                    |
| Botão "Gerar medição"             | `form[action*="/medicao/fechar"] button[type=submit]`           | idem                                    |
| Botão "Aprovar medição #N"        | `form[action*="/medicao/<medicao_id>/aprovar"] button[type=submit]` | POST `/obras/<obra_id>/medicao/<medicao_id>/aprovar` |
| Configuração da obra              | `form[action*="/medicao/config"]`                               | POST `/obras/<obra_id>/medicao/config` |

### A.4.7 — Compras v2 (`/compras/nova`)

| Rótulo                        | `name`                       | Tipo                |
|-------------------------------|------------------------------|---------------------|
| Fornecedor                    | `fornecedor_id`              | `select` (FK)       |
| Obra                          | `obra_id`                    | `select` (FK)       |
| Data                          | `data`                       | `date`              |
| Item — insumo                 | `item_insumo_<i>`            | `select`            |
| Item — quantidade             | `item_quantidade_<i>`        | `number step=0.01`  |
| Item — preço unit.            | `item_preco_<i>`             | `number step=0.01`  |
| Recebimento (qtd recebida)    | `qtd_recebida_<item_id>`     | `number step=0.01`  |

### A.4.8 — Alimentação v2 (`/alimentacao/lancamentos/novo-v2`)

| Rótulo                        | `name`                       | Tipo               |
|-------------------------------|------------------------------|--------------------|
| Data                          | `data`                       | `date`             |
| Restaurante                   | `restaurante_id`             | `select` (FK)      |
| Obra                          | `obra_id`                    | `select` (FK)      |
| Item — funcionário            | `item_funcionario_<i>`       | `select` (busca)   |
| Item — tipo                   | `item_tipo_<i>`              | `select`           |
| Item — quantidade             | `item_qtd_<i>`               | `number`           |
| Item — valor unit.            | `item_valor_<i>`             | `number step=0.01` |

### A.4.9 — Reembolso v2 (`/reembolso/novo`)

| Rótulo                        | `name`                       | Tipo               |
|-------------------------------|------------------------------|--------------------|
| Funcionário                   | `funcionario_id`             | `select` (FK)      |
| Data                          | `data`                       | `date`             |
| Descrição                     | `descricao`                  | `text`             |
| Valor (R$)                    | `valor`                      | `number step=0.01` |
| Obra                          | `obra_id`                    | `select` (FK)      |
| Categoria                     | `categoria`                  | `select`           |
| Anexo                         | `anexo`                      | `file`             |

### A.4.10 — Almoxarifado — saída (`/almoxarifado/saida`)

| Rótulo                        | `name`                       | Tipo               |
|-------------------------------|------------------------------|--------------------|
| Obra                          | `obra_id`                    | `select` (FK)      |
| Serviço da obra               | `servico_obra_id`            | `select` (FK)      |
| Funcionário (em posse)        | `funcionario_id`             | `select` (FK)      |
| Item                          | `item_id`                    | `select` (FK)      |
| Quantidade                    | `quantidade`                 | `number step=0.01` |
| Lote / Serial (quando aplica) | `lote_id` / `serial_id`      | `select`           |

## A.5 — Critério de aceite verificável por etapa

Cada etapa pode ser validada por **uma consulta SQL** (no banco do
tenant Alfa) **ou** por **um seletor CSS** (em testes E2E). A coluna
`admin_id` deve sempre ser filtrada pelo ID do admin Alfa impresso no
bloco `DEMO PRONTA`.

| # | Etapa                  | Critério SQL                                                          | Seletor CSS / DOM (alternativa) |
|---|------------------------|-----------------------------------------------------------------------|-----------------------------------|
| 1 | Login                  | `SELECT 1 FROM usuario WHERE email='admin@construtoraalfa.com.br'`    | URL final = `/dashboard` |
| 2 | Catálogos              | `SELECT count(*) FROM insumo WHERE admin_id=:a` ≥ 3 ; `SELECT count(*) FROM fornecedor WHERE admin_id=:a` ≥ 1 | linha de insumo + linha de fornecedor |
| 3 | Templates              | `SELECT count(*) FROM cronograma_template WHERE admin_id=:a` ≥ 2     | árvore Grupo→Subatividade |
| 4 | Serviços com template  | `SELECT template_padrao_id IS NOT NULL FROM servico WHERE admin_id=:a` retorna `t` ≥ 2 | bloco "Template padrão" preenchido |
| 5 | Funcionário diarista   | `SELECT tipo_remuneracao,valor_diaria FROM funcionario WHERE cpf='987.654.321-00'` retorna `('diaria',180.00)` | toast após POST `/funcionarios` |
| 6 | Orçamento com override | `SELECT count(*) FROM orcamento_item WHERE cronograma_template_override_id IS NOT NULL` ≥ 1 ; `SELECT composicao_snapshot IS NOT NULL FROM orcamento_item WHERE id=:i` retorna `t` | linha do orçamento com tag override |
| 7 | Proposta gerada        | `SELECT count(*) FROM propostas_comerciais WHERE orcamento_origem_id=:o` ≥ 1 | redireciona para `/propostas/<id>` |
| 8 | Aprovação + cronograma | `SELECT id FROM obra WHERE proposta_origem_id=:p` retorna 1 ; `SELECT count(*) FROM tarefa_cronograma WHERE obra_id=:obra` ≥ 6 | redireciona para `/obras/<id>` |
| 9 | Obra com cronograma    | `SELECT count(*) FROM tarefa_cronograma WHERE obra_id=:obra AND gerada_por_proposta_item_id IS NOT NULL` ≥ 4 | tarefas com etiqueta "📋 do contrato" |
|10 | Métricas funcionário   | `services/funcionario_metrics.calcular_metricas(funcionario_id, mes)` retorna dict não vazio | cards de KPI ≥ 5 |
|11 | RDO + custo MO         | `SELECT count(*) FROM custo_obra WHERE origem='RDO' AND obra_id=:obra` ≥ 1 | toast de sucesso após finalizar |
|12 | Ponto + folha          | `SELECT count(*) FROM ponto_registro WHERE funcionario_id=:f AND data=:d` ≥ 1 ; após fechamento, `SELECT count(*) FROM folha_pagamento WHERE mes=:m` ≥ 1 | mensagem "entrada registrada" |
|13 | Alimentação v2 + CP    | `SELECT count(*) FROM alimentacao_lancamento WHERE admin_id=:a` ≥ 1 ; `SELECT count(*) FROM gestao_custo_pai WHERE origem='ALIMENTACAO'` ≥ 1 | linha em `/alimentacao/lancamentos` |
|14 | Transporte             | `SELECT count(*) FROM transporte_lancamento WHERE admin_id=:a` ≥ 1   | linha em `/transporte/` |
|15 | Reembolso              | `SELECT count(*) FROM reembolso WHERE admin_id=:a` ≥ 1               | linha em `/reembolso/` |
|16 | Compra recebida        | `SELECT count(*) FROM compra_pedido WHERE status='RECEBIDO'` ≥ 1 ; `SELECT count(*) FROM almoxarifado_movimentacao WHERE tipo='ENTRADA'` ≥ 1 ; CP do fornecedor criada | toast "Recebimento registrado" |
|17 | Saída almoxarifado     | `SELECT count(*) FROM almoxarifado_movimentacao WHERE tipo='SAIDA' AND obra_id=:obra` ≥ 1 ; `SELECT count(*) FROM custo_obra WHERE origem='ALMOXARIFADO'` ≥ 1 | toast de sucesso |
|18 | Mapa Concorrência v2   | `SELECT count(*) FROM mapa_concorrencia_v2 WHERE obra_id=:obra` ≥ 1  | grade N×N renderizada |
|19 | Contas a Pagar         | `SELECT count(*) FROM gestao_custo_pai WHERE admin_id=:a` ≥ 3 (RDO+Compra+Alimentação) | painel kanban com cartões |
|20 | Contas a Receber única | `SELECT count(*) FROM conta_receber WHERE obra_id=:obra AND origem_tipo='OBRA_MEDICAO'` = 1 | linha `OBR-MED-####` única |
|21 | Fluxo de Caixa         | `SELECT count(*) FROM fluxo_caixa WHERE admin_id=:a` ≥ 1             | tabela com movimentos |
|22 | Medição aprovada       | `SELECT status FROM medicao WHERE id=:m` = `'APROVADO'` ; CR atualizada | linha de medição com badge "Aprovado" |
|23 | Portal do cliente      | GET `/portal/obra/<token>` retorna 200                                 | botão "Aprovar compra" visível |
|24 | Dashboard              | n/a (visual)                                                          | cards de KPI ≥ 4 em `/dashboard` |
|25 | Relatórios             | n/a (visual)                                                          | botão "Gerar PDF" funcional em E22 |

## A.6 — Ordem recomendada para um agente E2E

```
E01 Login
  ↓
PRÉ-OBRA
E02 Catálogos básicos → E03 Templates → E04 Serviços → E05 Funcionários
  ↓
E06 Orçamento (com 1 linha override + 1 linha composição customizada)
  ↓
E07 Gerar Proposta → E08 Aprovar (revisão) → E09 Verificar obra
  ↓
DURANTE A OBRA (paralelo, ordem recomendada)
E11 RDO finalizado → checa CP/CR
E12 Ponto facial → fecha mês → checa folha
E13 Alimentação v2 → checa CP
E14 Transporte
E15 Reembolso → aprovar → checa CP
E16 Compra → Recebimento → checa CP/Estoque/Custo
E17 Almoxarifado saída → checa Custo
E18 Mapa Concorrência v2 → cliente escolhe pelo portal
E22 Medição quinzenal → aprovar → checa CR única atualizada
E20 Contas a Receber → registrar pagamento parcial
E19 Contas a Pagar → autorizar e pagar
E21 Fluxo de Caixa → conferir saldo
E23 Portal do cliente → conferir aprovações e comprovantes
  ↓
VISÃO E ANÁLISE
E10 Métricas funcionário → conferir custo total
E24 Dashboards → conferir KPIs batem com somatórios
E25 Relatórios → gerar holerite + extrato medição PDF
```


  ---

  ## Apêndice B — Teste E2E automatizado (Task #132): insumo → serviço → proposta → cliente → cronograma → obra

  > Esta seção documenta o **teste end-to-end automatizado** que percorre,
  > sem intervenção manual, o fluxo principal do sistema, da criação dos
  > catálogos até a obra nascer com cronograma materializado. Os
  > screenshots abaixo (pasta `docs/img/manual 2/`) foram capturados na
  > execução real do teste — eles mostram o que o usuário vê em cada
  > ponto do ciclo.

  ### B.1 — Visão geral do fluxo testado

  ```
  1. Login admin (Construtora Alfa)
          ↓
  2. Criar insumo no catálogo                            (UI: /catalogo/insumos/novo)
          ↓
  3. Criar serviço com composição (insumo + coeficiente) (UI: /catalogo/servicos/novo + /composicao)
     + amarrar template de cronograma                    (atualmente via DB — ver B.4)
          ↓
  4. Visualizar template de cronograma                   (UI: /cronograma/templates)
          ↓
  5. Criar proposta com item vinculado ao serviço        (UI: /propostas/nova + /editar)
          ↓
  6. Admin revisa e SALVA o cronograma da proposta       (UI: /propostas/<id>/cronograma-revisar)
          ↓
  7. Cliente abre link público e APROVA                  (UI: /propostas/cliente/<token>)
     — cliente NÃO vê nenhuma validação de cronograma
          ↓
  8. Sistema cria a obra automaticamente
     + materializa o cronograma a partir do snapshot
          ↓
  9. Admin abre o cronograma da obra recém-aprovada      (UI: /cronograma/obra/<obra_id>)
     — esta é a tela onde o admin valida/ajusta as tarefas (badge "📋 do contrato")
  ```

  ### B.2 — Sequência ilustrada

  | Passo | Tela | Screenshot |
  | --- | --- | --- |
  | 1 | Login do administrador | ![Login](img/manual%202/m2-01-login.jpg) |
  | 2 | Cadastro do insumo | ![Insumo](img/manual%202/m2-02-insumo-form.jpg) |
  | 3 | Composição do serviço (insumo + coeficiente) | ![Composição](img/manual%202/m2-03-servico-composicao.jpg) |
  | 3b | Template de cronograma associado ao serviço | ![Template](img/manual%202/m2-04-template-cronograma.jpg) |
  | 5 | Proposta sendo criada com o item do catálogo | ![Proposta](img/manual%202/m2-05-proposta-form.jpg) |
  | 6 | Admin revisando o cronograma da proposta | ![Revisão](img/manual%202/m2-06-cronograma-revisar.jpg) |
  | 7 | Portal público do cliente — só **Aprovar/Rejeitar** | ![Cliente](img/manual%202/m2-07-cliente-portal.jpg) |
  | 9 | Admin abre o cronograma da obra criada (validação) | ![Cronograma da obra](img/manual%202/m2-08-cronograma-obra-admin.jpg) |
  | 9b | Tela de detalhes da obra criada automaticamente | ![Obra](img/manual%202/m2-09-obra-detalhes.jpg) |

  ### B.3 — Onde fica a validação do cronograma (resumo objetivo)

  - **Cliente** (`/propostas/cliente/<token>`): **NÃO existe** validação
    do cronograma. O cliente vê apenas a proposta comercial e os botões
    **Aprovar Proposta** / **Rejeitar Proposta**. Não há nenhum
    checkbox/passo de "validar cronograma" para o cliente.
  - **Admin — pré-aprovação** (`/propostas/<id>/cronograma-revisar`):
    o admin marca/desmarca os nós da árvore Serviço → Grupo →
    Subatividade e clica **Salvar pré-configuração**. Isso grava o
    snapshot em `Proposta.cronograma_default_json`.
  - **Admin — pós-aprovação** (`/cronograma/obra/<obra_id>`): assim que
    o cliente aprova, a obra nasce e o cronograma já vem materializado
    (tarefas com o badge **📋 do contrato**). Esta é a tela onde o admin
    faz a validação/ajuste final (mover datas, atribuir responsável,
    alterar duração) antes do cronograma virar oficial. **Não existe um
    wizard separado de "primeira abertura"** — é a tela normal do
    cronograma da obra, com os itens vindos do contrato sinalizados
    pelo badge.

  ### B.4 — Lacunas observadas durante o teste E2E (Task #132)

  O teste rodou de ponta a ponta, mas para chegar até o final foi
  preciso contornar três lacunas de UI. Estão documentadas aqui para
  que sejam tratadas em uma próxima task:

  1. **Sem campo "Template de cronograma" no cadastro de serviço.** O
     modelo `Servico` tem `template_padrao_id`, e o sistema usa esse
     campo para montar a árvore em `/cronograma-revisar`, mas nem
     `/catalogo/servicos/novo` nem `/catalogo/servicos/<id>/composicao`
     expõem o seletor. Hoje, amarrar template a serviço só é possível
     via banco (ou via seed). **Sugestão:** adicionar um `<select>` com
     os `cronograma_template` do tenant logo abaixo do bloco
     "Composição".
  2. **`/propostas/nova` não envia `item_servico_id`.** O formulário de
     nova proposta cria itens só com descrição/quantidade/preço, sem
     vincular ao serviço do catálogo. O vínculo só existe em
     `/propostas/<id>/editar` (datalist com busca). Resultado: se o
     usuário criar a proposta direto pela tela "Nova" e aprovar, o
     cronograma-revisar fica vazio. **Sugestão:** portar a busca do
     catálogo (datalist + hidden `item_servico_id`) para a tela "Nova".
  3. **Não existe botão "Enviar para o cliente".** A proposta nasce em
     status `rascunho`. O portal do cliente bloqueia aprovação até o
     status virar `enviada`. Hoje, mudar o status só é possível por
     `POST /propostas/<id>/status` (JSON) — não há botão visível.
     **Sugestão:** adicionar um botão **Enviar ao cliente** na tela
     `/propostas/<id>` que faça essa transição e copie o link público.
  4. **Bug pequeno no portal do cliente:** `portal_cliente.html`
     linha 559 quebra com `unsupported format string passed to
     NoneType.__format__` quando `item.subtotal` é `NULL`. Item criado
     pela tela "Nova" pode cair nesse caso porque o subtotal só é
     calculado em alguns ramos. **Sugestão:** trocar por
     `{{ '%.2f'|format(item.subtotal or 0) }}`.

  ### B.4.x — Como rodar o teste E2E

O teste é um script Python autossuficiente que cria seu próprio
tenant (admin + cliente + insumo + serviço + template + proposta) com
um identificador único por execução, e dirige o sistema **via Flask
test client** (HTTP real, não service layer):

```bash
python tests/test_e2e_proposta_aprovacao_cliente.py
```

Também está registrado como workflow no Replit:
**`test-e2e-proposta-aprovacao-cliente`**.

Saída esperada (resumo):

```
PASS login admin (HTTP 302)
PASS GET cronograma-revisar (HTTP 200)
PASS tela cronograma-revisar lista o serviço seedado
PASS GET cronograma-preview JSON (HTTP 200)
PASS preview JSON retorna árvore não-vazia
PASS POST cronograma-default (HTTP 302)
PASS snapshot cronograma_default_json gravado na proposta
PASS POST status ENVIADA (HTTP 200)
PASS proposta.status = ENVIADA
PASS GET portal cliente (HTTP 200)
PASS portal cliente não expõe rota cronograma-revisar
PASS portal cliente não expõe formulário de validação de cronograma
PASS POST cliente/aprovar (HTTP 200)
PASS proposta.obra_id setado (NNN)
PASS cronograma materializado: N tarefas para obra NNN
PASS N tarefas com gerada_por_proposta_item_id (📋 do contrato)
PASS GET /cronograma/obra (HTTP 200)
PASS página do cronograma da obra exibe badge '📋 do contrato'

E2E Task #132 (E2E132-XXXXXX) — 18 PASS / 0 FAIL
```

Exit code: `0` para sucesso, `1` se qualquer assert falhar — pronto
para CI.

### B.5 — Critério de aceite do teste E2E

  O teste é considerado **passou** quando, após o cliente aprovar pelo
  portal público:

  - `propostas_comerciais.obra_id` deixa de ser `NULL` (a obra foi
    criada);
  - `tarefa_cronograma` tem pelo menos uma linha com `obra_id` igual à
    obra criada e `gerada_por_proposta_item_id` preenchido;
  - `/cronograma/obra/<obra_id>` mostra o card "Total de Tarefas" > 0;
  - pelo menos uma tarefa exibe o badge **📋 do contrato**;
  - o portal do cliente em `/propostas/cliente/<token>` continua sem
    qualquer controle interativo de cronograma (somente Aprovar/Rejeitar).

  Na execução real, com a Construtora Alfa, o teste produziu:
  - obra **OBR0003 — Reforma residencial E2E**, criada
    automaticamente;
  - 5 tarefas materializadas no cronograma da obra (todas marcadas
    como "📋 do contrato");
  - portal do cliente sem nenhum widget de validação.
  