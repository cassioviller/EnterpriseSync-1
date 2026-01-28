# GUIA DE NAVEGACAO DETALHADO - MODULO ALMOXARIFADO
## SIGE v9.0 - Janeiro/2026 - Para Criacao de Scripts de Teste

===============================================================================
                              INDICE
===============================================================================
1. DASHBOARD
2. CATEGORIAS (Lista + Formulario)
3. ITENS (Lista + Formulario + Detalhes)
4. FORNECEDORES (Lista + Formulario)
5. ENTRADA DE MATERIAIS
6. SAIDA DE MATERIAIS
7. DEVOLUCAO DE MATERIAIS
8. DADOS FICTICIOS PARA TESTE

===============================================================================
                         1. DASHBOARD
===============================================================================
URL: /almoxarifado/

+-------------------------------------------------------------------------+
|                    ALMOXARIFADO - DASHBOARD                              |
|  Visao geral do estoque e movimentacoes                                 |
+-------------------------------------------------------------------------+

+------------------+ +------------------+ +------------------+ +------------------+
|  TOTAL DE ITENS  | |  ESTOQUE BAIXO   | | MOVIMENTOS HOJE  | |   VALOR TOTAL    |
|       {{ N }}    | |       {{ N }}    | |       {{ N }}    | |  R$ {{ N.NN }}   |
+------------------+ +------------------+ +------------------+ +------------------+

+-------------------------------------------------------------------------+
|                         ACOES RAPIDAS                                    |
+-------------------------------------------------------------------------+
| [+ Nova Entrada]  [- Nova Saida]  [Devolucao]  [Ver Catalogo]           |
| [Categorias]      [Fornecedores]                                         |
+-------------------------------------------------------------------------+

BOTOES E DESTINOS:
------------------
| Botao              | Destino                              |
|--------------------|--------------------------------------|
| + Nova Entrada     | /almoxarifado/entrada                |
| - Nova Saida       | /almoxarifado/saida                  |
| Devolucao          | /almoxarifado/devolucao              |
| Ver Catalogo       | /almoxarifado/itens                  |
| Categorias         | /almoxarifado/categorias             |
| Fornecedores       | /almoxarifado/fornecedores           |

ALERTAS (quando existem):
-------------------------
- Itens com Estoque Baixo (badge vermelho)
- Itens Vencendo nos Proximos 30 Dias (badge amarelo)
- Itens em Manutencao (badge azul)

TABELA ULTIMAS MOVIMENTACOES:
-----------------------------
| Data/Hora | Tipo    | Item          | Quantidade/Serial | Funcionario | Acao |
|-----------|---------|---------------|-------------------|-------------|------|
| DD/MM HH:MM| ENTRADA| Nome do Item  | 10 un ou S/N:XXX | Nome        | [Ver]|


===============================================================================
                         2. CATEGORIAS
===============================================================================

-------------------------------------------------------------------------------
2.1 LISTA DE CATEGORIAS
-------------------------------------------------------------------------------
URL: /almoxarifado/categorias

+-------------------------------------------------------------------------+
|                    CATEGORIAS DE MATERIAIS                              |
|                                               [+ Nova Categoria]         |
+-------------------------------------------------------------------------+

TABELA:
+-------------------------------------------------------------------------+
| Nome           | Tipo de Controle Padrao | Permite Devolucao | Acoes   |
|----------------|-------------------------|-------------------|---------|
| {{nome}}       | [Serializado] ou [Consumivel] | Sim/Nao     | [E] [X] |
+-------------------------------------------------------------------------+

BOTOES:
-------
| Botao              | Destino                                      |
|--------------------|----------------------------------------------|
| + Nova Categoria   | /almoxarifado/categorias/criar               |
| [E] Editar         | /almoxarifado/categorias/editar/<id>         |
| [X] Excluir        | Modal confirmacao -> POST /categorias/deletar/<id> |


-------------------------------------------------------------------------------
2.2 FORMULARIO CATEGORIA (Criar/Editar)
-------------------------------------------------------------------------------
URL Criar: /almoxarifado/categorias/criar
URL Editar: /almoxarifado/categorias/editar/<id>

+-------------------------------------------------------------------------+
|                    NOVA CATEGORIA / EDITAR CATEGORIA                     |
+-------------------------------------------------------------------------+

+---------------------------------------------+
| FORMULARIO                                  |
+---------------------------------------------+
| Nome da Categoria *                         |
| +----------------------------------------+ |
| |                                        | |
| +----------------------------------------+ |
|   Texto livre, OBRIGATORIO                  |
|                                             |
| Tipo de Controle Padrao *                   |
| +----------------------------------------+ |
| | [v] Serializado (itens unicos com NS)  | |
| |     Consumivel (materiais por qtd)     | |
| +----------------------------------------+ |
|   SELECT, OBRIGATORIO                       |
|   Valores: SERIALIZADO, CONSUMIVEL          |
|                                             |
| [ ] Permite devolucao por padrao            |
|   CHECKBOX, opcional                        |
|   Nota: Serializados sempre permitem        |
|                                             |
| [Criar/Atualizar]  [Cancelar]               |
+---------------------------------------------+

CAMPOS DO FORMULARIO:
---------------------
| Campo                    | Tipo     | Obrig | Valores                    |
|--------------------------|----------|-------|----------------------------|
| nome                     | text     | SIM   | texto livre                |
| tipo_controle_padrao     | select   | SIM   | SERIALIZADO, CONSUMIVEL    |
| permite_devolucao_padrao | checkbox | NAO   | on/off                     |

DADOS FICTICIOS:
----------------
| nome                      | tipo_controle_padrao | permite_devolucao_padrao |
|---------------------------|----------------------|--------------------------|
| Materiais de Construcao   | CONSUMIVEL           | off                      |
| Ferramentas Manuais       | SERIALIZADO          | on                       |
| Equipamentos de Seguranca | SERIALIZADO          | on                       |
| EPIs Descartaveis         | CONSUMIVEL           | off                      |
| Equipamentos Eletricos    | SERIALIZADO          | on                       |


===============================================================================
                              3. ITENS
===============================================================================

-------------------------------------------------------------------------------
3.1 LISTA DE ITENS
-------------------------------------------------------------------------------
URL: /almoxarifado/itens

+-------------------------------------------------------------------------+
|                    ITENS DO ALMOXARIFADO                                |
|                                                        [+ Novo Item]     |
+-------------------------------------------------------------------------+

FILTROS:
+-------------------------------------------------------------------------+
| Buscar                    | Categoria        | Tipo de Controle         |
| +----------------------+  | +-------------+  | +-------------------+    |
| | Codigo ou nome...   |  | | Todas    [v]|  | | Todos          [v]|    |
| +----------------------+  | +-------------+  | +-------------------+    |
|                                                          [Filtrar]      |
+-------------------------------------------------------------------------+

TABELA:
+-------------------------------------------------------------------------+
| Codigo | Nome    | Categoria | Tipo        | Estoque | Devolucao | Acoes|
|--------|---------|-----------|-------------|---------|-----------|------|
| MAT001 | Cimento | Materiais | [Consumivel]| 100 sc  | Sim       |[V][H][E][X]|
+-------------------------------------------------------------------------+

BOTOES:
-------
| Botao           | Destino                                 |
|-----------------|-----------------------------------------|
| + Novo Item     | /almoxarifado/itens/criar               |
| [V] Ver         | /almoxarifado/itens/<id>                |
| [H] Historico   | /almoxarifado/itens/<id>/movimentacoes  |
| [E] Editar      | /almoxarifado/itens/editar/<id>         |
| [X] Excluir     | Modal -> POST /itens/deletar/<id>       |


-------------------------------------------------------------------------------
3.2 FORMULARIO ITEM (Criar/Editar)
-------------------------------------------------------------------------------
URL Criar: /almoxarifado/itens/criar
URL Editar: /almoxarifado/itens/editar/<id>

+-------------------------------------------------------------------------+
|                    NOVO ITEM / EDITAR ITEM                              |
+-------------------------------------------------------------------------+

+---------------------------------------------+
| FORMULARIO                                  |
+---------------------------------------------+
| Codigo *              | Nome do Item *      |
| +------------------+  | +----------------+  |
| | MAT001           |  | | Cimento 50kg   |  |
| +------------------+  | +----------------+  |
|   text, OBRIGATORIO   |   text, OBRIGATORIO |
|                                             |
| Categoria *           | Tipo de Controle *  |
| +------------------+  | +----------------+  |
| | [v] Selecione... |  | | Serializado    |  |
| +------------------+  | | Consumivel  [v]|  |
|   select, OBRIGATORIO | +----------------+  |
|                       |   select, OBRIGATORIO|
|                                             |
| Estoque Minimo  | Unidade    | Permite Dev. |
| +------------+  | +--------+ | [X] on       |
| | 10         |  | | sc     | |              |
| +------------+  | +--------+ |              |
|   number, opc.  |   text, opc |  checkbox    |
|                                             |
| [Criar/Atualizar]  [Cancelar]               |
+---------------------------------------------+

CAMPOS DO FORMULARIO:
---------------------
| Campo             | Tipo     | Obrig | Valores/Exemplo           |
|-------------------|----------|-------|---------------------------|
| codigo            | text     | SIM   | MAT001, EPI001, FER001    |
| nome              | text     | SIM   | Cimento 50kg, Capacete    |
| categoria_id      | select   | SIM   | IDs das categorias        |
| tipo_controle     | select   | SIM   | SERIALIZADO, CONSUMIVEL   |
| estoque_minimo    | number   | NAO   | 0, 10, 100                |
| unidade           | text     | NAO   | un, kg, m, pc, lt, sc, cx |
| permite_devolucao | checkbox | NAO   | on/off (forcado para SERIALIZADO)|

DADOS FICTICIOS - CONSUMIVEIS:
------------------------------
| codigo  | nome                   | categoria               | unidade | est_min |
|---------|------------------------|-------------------------|---------|---------|
| MAT001  | Cimento CP-II 50kg     | Materiais de Construcao | sc      | 20      |
| MAT002  | Areia Media m3         | Materiais de Construcao | m3      | 5       |
| MAT003  | Brita 1 m3             | Materiais de Construcao | m3      | 5       |
| MAT004  | Tijolo Ceramico 6 fur. | Materiais de Construcao | un      | 500     |
| MAT005  | Vergalhao CA-50 10mm   | Materiais de Construcao | kg      | 100     |
| EPI001  | Luva Descartavel caixa | EPIs Descartaveis       | cx      | 10      |
| EPI002  | Mascara PFF2 caixa     | EPIs Descartaveis       | cx      | 5       |

DADOS FICTICIOS - SERIALIZADOS:
-------------------------------
| codigo  | nome                        | categoria                 | unidade |
|---------|-----------------------------|---------------------------|---------|
| FER001  | Furadeira Bosch 500W        | Equipamentos Eletricos    | un      |
| FER002  | Martelete Makita 800W       | Equipamentos Eletricos    | un      |
| FER003  | Serra Circular DeWalt       | Equipamentos Eletricos    | un      |
| FER004  | Chave de Impacto Pneumatica | Ferramentas Manuais       | un      |
| SEG001  | Cinto Seguranca Paraquedista| Equipamentos de Seguranca | un      |
| SEG002  | Capacete c/ Jugular         | Equipamentos de Seguranca | un      |


===============================================================================
                           4. FORNECEDORES
===============================================================================

-------------------------------------------------------------------------------
4.1 LISTA DE FORNECEDORES
-------------------------------------------------------------------------------
URL: /almoxarifado/fornecedores

+-------------------------------------------------------------------------+
|                         FORNECEDORES                                    |
|  Gerencie os fornecedores de materiais            [+ Novo Fornecedor]   |
+-------------------------------------------------------------------------+

FILTRO:
+-------------------------------------------------------------------------+
| Buscar por Razao Social, Nome Fantasia ou CNPJ...           [Buscar]   |
+-------------------------------------------------------------------------+

TABELA:
+-------------------------------------------------------------------------+
| Razao Social      | Nome Fantasia | CNPJ           | Cidade/UF | Acoes  |
|-------------------|---------------|----------------|-----------|--------|
| Empresa LTDA      | ABC Materiais | 11.111.111/0001| SP/SP     | [E][X] |
+-------------------------------------------------------------------------+

BOTOES:
-------
| Botao               | Destino                                    |
|---------------------|--------------------------------------------|
| + Novo Fornecedor   | /almoxarifado/fornecedores/criar           |
| [E] Editar          | /almoxarifado/fornecedores/editar/<id>     |
| [X] Desativar       | Modal -> POST /fornecedores/deletar/<id>   |


-------------------------------------------------------------------------------
4.2 FORMULARIO FORNECEDOR (Criar/Editar)
-------------------------------------------------------------------------------
URL Criar: /almoxarifado/fornecedores/criar
URL Editar: /almoxarifado/fornecedores/editar/<id>

+-------------------------------------------------------------------------+
|                    NOVO FORNECEDOR / EDITAR FORNECEDOR                  |
+-------------------------------------------------------------------------+

+----------------------------------+  +----------------------------------+
| DADOS DA EMPRESA                 |  | ENDERECO                         |
+----------------------------------+  +----------------------------------+
| Razao Social *                   |  | Endereco Completo                |
| +------------------------------+ |  | +------------------------------+ |
| | Distribuidora ABC Ltda       | |  | | Rua das Flores, 100, Centro  | |
| +------------------------------+ |  | +------------------------------+ |
|                                  |  |                                  |
| Nome Fantasia                    |  | Cidade        | UF   | CEP       |
| +------------------------------+ |  | +-----------+ | +--+ | +-------+ |
| | ABC Materiais                | |  | | Sao Paulo | | |SP| | |01234- | |
| +------------------------------+ |  | +-----------+ | +--+ | +-------+ |
|                                  |  +----------------------------------+
| CNPJ *            | Insc. Estad. |  
| +---------------+ | +-----------+|  +----------------------------------+
| |11.111.111/0001| | |123456789  ||  | CONTATO                          |
| +---------------+ | +-----------+|  +----------------------------------+
+----------------------------------+  | Telefone                         |
                                      | +------------------------------+ |
                                      | | (11) 99999-9999              | |
                                      | +------------------------------+ |
                                      |                                  |
                                      | E-mail                           |
                                      | +------------------------------+ |
                                      | | contato@abc.com.br           | |
                                      | +------------------------------+ |
                                      |                                  |
                                      | Nome do Responsavel              |
                                      | +------------------------------+ |
                                      | | Joao Silva                   | |
                                      | +------------------------------+ |
                                      +----------------------------------+

[Cadastrar/Atualizar Fornecedor]  [Cancelar]

CAMPOS DO FORMULARIO:
---------------------
| Campo              | Tipo   | Obrig | Exemplo                      |
|--------------------|--------|-------|------------------------------|
| razao_social       | text   | SIM   | Distribuidora ABC Ltda       |
| nome_fantasia      | text   | NAO   | ABC Materiais                |
| cnpj               | text   | SIM   | 11.111.111/0001-11 (mascara) |
| inscricao_estadual | text   | NAO   | 123456789                    |
| endereco           | text   | NAO   | Rua das Flores, 100          |
| cidade             | text   | NAO   | Sao Paulo                    |
| estado             | select | NAO   | SP (lista de UFs)            |
| cep                | text   | NAO   | 01234-567 (mascara)          |
| telefone           | text   | NAO   | (11) 99999-9999 (mascara)    |
| email              | email  | NAO   | contato@abc.com.br           |
| contato_responsavel| text   | NAO   | Joao Silva                   |

DADOS FICTICIOS:
----------------
| razao_social                | cnpj               | cidade        | estado |
|-----------------------------|--------------------|---------------|--------|
| Materiais Construcao ABC    | 11.111.111/0001-11 | Sao Paulo     | SP     |
| Ferramentas Brasil SA       | 22.222.222/0001-22 | Campinas      | SP     |
| EPI Seguranca Total Ltda    | 33.333.333/0001-33 | Rio de Janeiro| RJ     |
| Ferragens e Parafusos Ltda  | 44.444.444/0001-44 | Belo Horizonte| MG     |
| Equipamentos Industriais ME | 55.555.555/0001-55 | Curitiba      | PR     |


===============================================================================
                      5. ENTRADA DE MATERIAIS
===============================================================================
URL: /almoxarifado/entrada

+-------------------------------------------------------------------------+
|                    ENTRADA DE MATERIAIS                     [<- Voltar] |
|  Registrar entrada de itens no almoxarifado                             |
+-------------------------------------------------------------------------+

+---------------------------------------------+  +------------------------+
| FORMULARIO                                  |  | COMO FUNCIONA?         |
+---------------------------------------------+  +------------------------+
| Item *                                      |  | ITENS SERIALIZADOS:    |
| +----------------------------------------+ |  | - Informe cada N/S     |
| | [v] Selecione um item...               | |  | - Separe por virgula   |
| |     MAT001 - Cimento CP-II 50kg        | |  | - Cadastro individual  |
| |     FER001 - Furadeira Bosch 500W      | |  |                        |
| +----------------------------------------+ |  | ITENS CONSUMIVEIS:     |
|   select, OBRIGATORIO                       |  | - Informe quantidade   |
|                                             |  | - Use ponto p/ decimal |
| +------------------------------------------+|  | - Controle por saldo   |
| | Tipo: Consumivel | Unidade: sc | Est: 80 ||  +------------------------+
| +------------------------------------------+|
|   (exibido apos selecionar item)            |
|                                             |
| *** SE SERIALIZADO: ***                     |
| Numeros de Serie *                          |
| +----------------------------------------+ |
| | FUR-001                                | |
| | FUR-002                                | |
| | FUR-003                                | |
| +----------------------------------------+ |
|   textarea, OBRIGATORIO para serializado    |
|   Separar por virgula ou quebra de linha    |
|                                             |
| *** SE CONSUMIVEL: ***                      |
| Quantidade *                                |
| +--------------------------------+ +-----+  |
| | 100.00                         | | sc  |  |
| +--------------------------------+ +-----+  |
|   number step=0.01, OBRIGATORIO             |
|                                             |
| Nota Fiscal                                 |
| +----------------------------------------+ |
| | NF-001234                              | |
| +----------------------------------------+ |
|   text, opcional                            |
|                                             |
| Fornecedor                                  |
| +----------------------------------------+ |
| | [v] Selecione um fornecedor (opcional) | |
| +----------------------------------------+ |
|   select, opcional                          |
|                                             |
| Valor Unitario (R$) *                       |
| +----------------------------------------+ |
| | 35.00                                  | |
| +----------------------------------------+ |
|   number step=0.01, OBRIGATORIO             |
|                                             |
| Observacoes                                 |
| +----------------------------------------+ |
| | Compra mensal                          | |
| +----------------------------------------+ |
|   textarea, opcional                        |
|                                             |
| [+ Adicionar ao Carrinho]  [Limpar]         |
+---------------------------------------------+

+---------------------------------------------+
| ITENS NO CARRINHO ({{ N }})                 |
+---------------------------------------------+
| MAT001 - Cimento 50kg                       |
| Quantidade: 100 sc                          |
| Valor Unit.: R$ 35.00 | Total: R$ 3500.00   |
| [Remover]                                   |
+---------------------------------------------+
| [Limpar Carrinho]  [Finalizar Entrada]      |
+---------------------------------------------+

CAMPOS DO FORMULARIO:
---------------------
| Campo          | Tipo     | Obrig | Condicao        | Exemplo            |
|----------------|----------|-------|-----------------|-------------------|
| item_id        | select   | SIM   | sempre          | ID do item        |
| tipo_controle  | hidden   | SIM   | preenchido auto | SERIALIZADO/CONSUMIVEL |
| numeros_serie  | textarea | SIM*  | se SERIALIZADO  | FUR-001, FUR-002  |
| quantidade     | number   | SIM*  | se CONSUMIVEL   | 100.00            |
| nota_fiscal    | text     | NAO   | sempre          | NF-001234         |
| fornecedor_id  | select   | NAO   | sempre          | ID do fornecedor  |
| valor_unitario | number   | SIM   | sempre          | 35.00             |
| observacoes    | textarea | NAO   | sempre          | Compra mensal     |

DADOS FICTICIOS - ENTRADAS CONSUMIVEIS:
---------------------------------------
| item                  | quantidade | valor_unit | fornecedor        | nota_fiscal |
|-----------------------|------------|------------|-------------------|-------------|
| Cimento CP-II 50kg    | 100        | 35.00      | Mat. Constr. ABC  | NF-001      |
| Areia Media m3        | 20         | 150.00     | Mat. Constr. ABC  | NF-001      |
| Tijolo Ceramico       | 2000       | 0.85       | Mat. Constr. ABC  | NF-002      |
| Vergalhao CA-50       | 500        | 8.50       | Ferragens Ltda    | NF-003      |
| Luva Descartavel cx   | 20         | 45.00      | EPI Seguranca     | NF-004      |

DADOS FICTICIOS - ENTRADAS SERIALIZADOS:
----------------------------------------
| item                   | numeros_serie                    | valor_unit | fornecedor       |
|------------------------|----------------------------------|------------|------------------|
| Furadeira Bosch 500W   | FUR-001, FUR-002, FUR-003        | 350.00     | Ferramentas BR   |
| Martelete Makita 800W  | MRT-001, MRT-002                 | 890.00     | Ferramentas BR   |
| Serra Circular DeWalt  | SER-001                          | 650.00     | Ferramentas BR   |
| Cinto Paraquedista     | CINTO-001, CINTO-002, CINTO-003, CINTO-004 | 280.00 | EPI Seguranca |
| Capacete c/ Jugular    | CAP-001, CAP-002, CAP-003, CAP-004, CAP-005 | 85.00  | EPI Seguranca |


===============================================================================
                       6. SAIDA DE MATERIAIS
===============================================================================
URL: /almoxarifado/saida

+-------------------------------------------------------------------------+
|                    SAIDA DE MATERIAIS                       [<- Voltar] |
|  Registrar saida de itens do almoxarifado                               |
+-------------------------------------------------------------------------+

+---------------------------------------------+  +------------------------+
| FORMULARIO                                  |  | COMO FUNCIONA?         |
+---------------------------------------------+  +------------------------+
| Funcionario *                               |  | SISTEMA DE CARRINHO:   |
| +----------------------------------------+ |  | - Selecione func/obra  |
| | [v] Selecione um funcionario...        | |  | - Adicione varios itens|
| |     001 - Jose da Silva                | |  | - Finalize de uma vez  |
| |     002 - Maria Santos                 | |  |                        |
| +----------------------------------------+ |  | SERIALIZADOS:          |
|   select, OBRIGATORIO                       |  | - Selecione itens      |
|                                             |  | - Status -> EM_USO     |
| Obra (opcional)                             |  |                        |
| +----------------------------------------+ |  | CONSUMIVEIS:           |
| | [v] Nenhuma obra especifica            | |  | - Informe quantidade   |
| |     001 - Residencial Vista Verde      | |  | - FIFO automatico      |
| +----------------------------------------+ |  +------------------------+
|   select, opcional                          |
|                                             |
| Item *                                      |
| +----------------------------------------+ |
| | [v] Selecione um item...               | |
| +----------------------------------------+ |
|   select, OBRIGATORIO                       |
|                                             |
| +------------------------------------------+|
| | Tipo: Serializado | Un: - | Disp: 3 un  ||
| +------------------------------------------+|
|                                             |
| *** SE SERIALIZADO: ***                     |
| Selecione os Itens para Saida *             |
| +----------------------------------------+ |
| | [ ] FUR-001 - Entrada em 15/01/2026    | |
| | [X] FUR-002 - Entrada em 15/01/2026    | |
| | [ ] FUR-003 - Entrada em 15/01/2026    | |
| +----------------------------------------+ |
|   checkbox list, OBRIGATORIO                |
|                                             |
| *** SE CONSUMIVEL: ***                      |
| Quantidade *                                |
| +--------------------------------+ +-----+  |
| | 20.00                          | | sc  |  |
| +--------------------------------+ +-----+  |
|   number step=0.01, max=disponivel          |
|                                             |
| +------------------------------------------+|
| | SELECIONE OS LOTES PARA SAIDA            ||
| +------------------------------------------+|
| |[ ]| Lote/NF   | Data    | Disp | V.Unit ||
| |[X]| NF-001    | 15/01   | 80   | 35.00  ||
| |[ ]| NF-002    | 20/01   | 20   | 36.00  ||
| | Qtd necessaria: 20.00 | Alocado: 20.00  ||
| +------------------------------------------+|
|   Selecao manual de lotes                   |
|                                             |
| [+ Adicionar ao Carrinho]  [Limpar]         |
+---------------------------------------------+

+---------------------------------------------+
| ITENS NO CARRINHO ({{ N }})                 |
+---------------------------------------------+
| Observacoes Gerais                          |
| +----------------------------------------+ |
| | Entrega para obra Vista Verde          | |
| +----------------------------------------+ |
|                                             |
| FER001 - Furadeira Bosch                    |
| Serie: FUR-002                              |
| [Remover]                                   |
+---------------------------------------------+
| [Limpar Carrinho]  [Finalizar Saida]        |
+---------------------------------------------+

CAMPOS DO FORMULARIO:
---------------------
| Campo          | Tipo     | Obrig | Condicao        | Exemplo            |
|----------------|----------|-------|-----------------|-------------------|
| funcionario_id | select   | SIM   | sempre          | ID do funcionario |
| obra_id        | select   | NAO   | sempre          | ID da obra        |
| item_id        | select   | SIM   | sempre          | ID do item        |
| tipo_controle  | hidden   | SIM   | preenchido auto | SERIALIZADO/CONSUMIVEL |
| estoque_ids[]  | checkbox | SIM*  | se SERIALIZADO  | IDs dos estoques  |
| quantidade     | number   | SIM*  | se CONSUMIVEL   | 20.00             |
| lote_allocations| array   | NAO   | se CONSUMIVEL   | selecao manual    |
| observacoes    | textarea | NAO   | sempre          | texto livre       |

DADOS FICTICIOS - FUNCIONARIOS (pre-requisito):
-----------------------------------------------
| codigo | nome          | cargo           |
|--------|---------------|-----------------|
| 001    | Jose da Silva | Pedreiro        |
| 002    | Maria Santos  | Encarregada     |
| 003    | Pedro Oliveira| Eletricista     |
| 004    | Ana Costa     | Auxiliar        |
| 005    | Carlos Souza  | Mestre de Obras |

DADOS FICTICIOS - OBRAS (pre-requisito):
----------------------------------------
| codigo | nome                   | endereco                |
|--------|------------------------|-------------------------|
| 001    | Residencial Vista Verde| Rua das Flores, 100     |
| 002    | Comercial Centro       | Av. Brasil, 500         |
| 003    | Industrial Zona Norte  | Rod. Fernao Dias, km 50 |

DADOS FICTICIOS - SAIDAS CONSUMIVEIS:
-------------------------------------
| item              | qtd | funcionario    | obra                   |
|-------------------|-----|----------------|------------------------|
| Cimento CP-II     | 20  | Jose da Silva  | Residencial Vista Verde|
| Tijolo Ceramico   | 500 | Jose da Silva  | Residencial Vista Verde|
| Vergalhao CA-50   | 100 | Pedro Oliveira | Comercial Centro       |
| Luva Descartavel  | 2   | Ana Costa      | Industrial Zona Norte  |

DADOS FICTICIOS - SAIDAS SERIALIZADOS:
--------------------------------------
| item               | numero_serie | funcionario    | obra                   |
|--------------------|--------------|----------------|------------------------|
| Furadeira Bosch    | FUR-001      | Pedro Oliveira | Comercial Centro       |
| Martelete Makita   | MRT-001      | Jose da Silva  | Residencial Vista Verde|
| Cinto Paraquedista | CINTO-001    | Jose da Silva  | Residencial Vista Verde|
| Cinto Paraquedista | CINTO-002    | Maria Santos   | Residencial Vista Verde|
| Capacete c/ Jugular| CAP-001      | Jose da Silva  | Residencial Vista Verde|
| Capacete c/ Jugular| CAP-002      | Pedro Oliveira | Comercial Centro       |


===============================================================================
                      7. DEVOLUCAO DE MATERIAIS
===============================================================================
URL: /almoxarifado/devolucao

+-------------------------------------------------------------------------+
|                    DEVOLUCAO DE MATERIAIS                   [<- Voltar] |
|  Registrar devolucao de itens ao almoxarifado                           |
+-------------------------------------------------------------------------+

+---------------------------------------------+  +------------------------+
| FORMULARIO                                  |  | COMO FUNCIONA?         |
+---------------------------------------------+  +------------------------+
| Funcionario *                               |  | SISTEMA DE CARRINHO:   |
| +----------------------------------------+ |  | - Selecione funcionario|
| | [v] Selecione um funcionario...        | |  | - Escolha itens        |
| +----------------------------------------+ |  | - Informe condicao     |
|   select, OBRIGATORIO                       |  | - Finalize de uma vez  |
|   Ao selecionar, carrega itens em posse     |  |                        |
|                                             |  | SERIALIZADOS:          |
| *** APOS SELECIONAR FUNCIONARIO: ***        |  | - Sempre devoluveis    |
|                                             |  | - Condicao por item    |
| ITENS SERIALIZADOS PARA DEVOLUCAO           |  | - Status atualizado    |
| +----------------------------------------+ |  |                        |
| | [X] Furadeira Bosch 500W               | |  | CONSUMIVEIS:           |
| |     N/S: FUR-001                        | |  | - Se permite devolucao |
| |     Obra: Comercial Centro              | |  | - Informe qtd e cond.  |
| |     Condicao: [v] Selecione...          | |  | - Volta ao estoque     |
| |               | Perfeito               | |  +------------------------+
| |               | Bom                    | |
| |               | Regular                | |
| |               | Danificado             | |
| |               | Inutilizado            | |
| +----------------------------------------+ |
|   checkbox + select condicao por item       |
|                                             |
| ITENS CONSUMIVEIS PARA DEVOLUCAO            |
| +----------------------------------------+ |
| | Luva Descartavel (em posse: 2 cx)      | |
| | Quantidade: [___] cx  Condicao: [___]  | |
| | [Devolver]  [Consumido]                | |
| +----------------------------------------+ |
|   Botao Devolver: devolve ao estoque        |
|   Botao Consumido: marca como usado         |
|                                             |
| [+ Adicionar ao Carrinho]  [Limpar]         |
+---------------------------------------------+

+---------------------------------------------+
| ITENS NO CARRINHO ({{ N }})                 |
+---------------------------------------------+
| Observacoes Gerais                          |
| +----------------------------------------+ |
| |                                        | |
| +----------------------------------------+ |
|                                             |
| Furadeira Bosch - FUR-001                   |
| Condicao: Bom                               |
| [Remover]                                   |
+---------------------------------------------+
| [Limpar Carrinho]  [Finalizar Devolucao]    |
+---------------------------------------------+

CAMPOS DO FORMULARIO:
---------------------
| Campo             | Tipo     | Obrig | Condicao        | Valores                    |
|-------------------|----------|-------|-----------------|----------------------------|
| funcionario_id    | select   | SIM   | sempre          | ID do funcionario          |
| estoque_ids[]     | checkbox | SIM*  | se SERIALIZADO  | IDs dos estoques selecionados|
| condicao_item     | select   | SIM   | por item        | Perfeito, Bom, Regular, Danificado, Inutilizado |
| item_id           | hidden   | SIM*  | se CONSUMIVEL   | ID do item                 |
| quantidade        | number   | SIM*  | se CONSUMIVEL   | max = qtd em posse         |
| observacoes       | textarea | NAO   | sempre          | texto livre                |

CONDICOES E STATUS RESULTANTE (SERIALIZADO):
--------------------------------------------
| Condicao    | Status Resultante |
|-------------|-------------------|
| Perfeito    | DISPONIVEL        |
| Bom         | DISPONIVEL        |
| Regular     | DISPONIVEL        |
| Danificado  | EM_MANUTENCAO     |
| Inutilizado | INUTILIZADO       |

DADOS FICTICIOS - DEVOLUCOES:
-----------------------------
| item             | numero_serie | funcionario    | condicao |
|------------------|--------------|----------------|----------|
| Furadeira Bosch  | FUR-001      | Pedro Oliveira | Bom      |
| Capacete c/Jugular| CAP-001     | Jose da Silva  | Regular  |


===============================================================================
                    8. FLUXO COMPLETO DE TESTE
===============================================================================

ORDEM DE EXECUCAO RECOMENDADA:
------------------------------

PASSO 1: CRIAR CATEGORIAS (5)
-----------------------------
1. Materiais de Construcao - CONSUMIVEL - Nao permite devolucao
2. Ferramentas Manuais - SERIALIZADO - Permite devolucao
3. Equipamentos de Seguranca - SERIALIZADO - Permite devolucao
4. EPIs Descartaveis - CONSUMIVEL - Nao permite devolucao
5. Equipamentos Eletricos - SERIALIZADO - Permite devolucao

PASSO 2: CRIAR FORNECEDORES (5)
-------------------------------
1. Materiais Construcao ABC Ltda - 11.111.111/0001-11 - Sao Paulo/SP
2. Ferramentas Brasil SA - 22.222.222/0001-22 - Campinas/SP
3. EPI Seguranca Total Ltda - 33.333.333/0001-33 - Rio de Janeiro/RJ
4. Ferragens e Parafusos Ltda - 44.444.444/0001-44 - Belo Horizonte/MG
5. Equipamentos Industriais ME - 55.555.555/0001-55 - Curitiba/PR

PASSO 3: CRIAR ITENS (13)
-------------------------
Consumiveis (7):
1. MAT001 - Cimento CP-II 50kg - Materiais de Construcao - sc - min:20
2. MAT002 - Areia Media m3 - Materiais de Construcao - m3 - min:5
3. MAT003 - Brita 1 m3 - Materiais de Construcao - m3 - min:5
4. MAT004 - Tijolo Ceramico 6 furos - Materiais de Construcao - un - min:500
5. MAT005 - Vergalhao CA-50 10mm - Materiais de Construcao - kg - min:100
6. EPI001 - Luva Descartavel caixa - EPIs Descartaveis - cx - min:10
7. EPI002 - Mascara PFF2 caixa - EPIs Descartaveis - cx - min:5

Serializados (6):
1. FER001 - Furadeira Bosch 500W - Equipamentos Eletricos - un
2. FER002 - Martelete Makita 800W - Equipamentos Eletricos - un
3. FER003 - Serra Circular DeWalt - Equipamentos Eletricos - un
4. FER004 - Chave de Impacto Pneumatica - Ferramentas Manuais - un
5. SEG001 - Cinto Seguranca Paraquedista - Equipamentos de Seguranca - un
6. SEG002 - Capacete c/ Jugular - Equipamentos de Seguranca - un

PASSO 4: VERIFICAR FUNCIONARIOS/OBRAS NO SISTEMA
-------------------------------------------------
(Devem existir para fazer saidas - cadastrar se nao existirem)

PASSO 5: FAZER ENTRADAS (10)
----------------------------
Consumiveis (5):
1. Cimento - 100 sc - R$ 35.00 - NF-001 - Mat.Constr.ABC
2. Areia - 20 m3 - R$ 150.00 - NF-001 - Mat.Constr.ABC
3. Tijolo - 2000 un - R$ 0.85 - NF-002 - Mat.Constr.ABC
4. Vergalhao - 500 kg - R$ 8.50 - NF-003 - Ferragens Ltda
5. Luva - 20 cx - R$ 45.00 - NF-004 - EPI Seguranca

Serializados (5):
1. Furadeira - FUR-001,FUR-002,FUR-003 - R$ 350.00 - Ferramentas BR
2. Martelete - MRT-001,MRT-002 - R$ 890.00 - Ferramentas BR
3. Serra - SER-001 - R$ 650.00 - Ferramentas BR
4. Cinto - CINTO-001,CINTO-002,CINTO-003,CINTO-004 - R$ 280.00 - EPI Seg.
5. Capacete - CAP-001,CAP-002,CAP-003,CAP-004,CAP-005 - R$ 85.00 - EPI Seg.

PASSO 6: VERIFICAR DASHBOARD
----------------------------
- Total de itens atualizado
- Valor total atualizado
- Ultimas movimentacoes mostrando entradas

PASSO 7: FAZER SAIDAS (10)
--------------------------
Consumiveis (4):
1. Cimento - 20 sc - Jose da Silva - Residencial Vista Verde
2. Tijolo - 500 un - Jose da Silva - Residencial Vista Verde
3. Vergalhao - 100 kg - Pedro Oliveira - Comercial Centro
4. Luva - 2 cx - Ana Costa - Industrial Zona Norte

Serializados (6):
1. Furadeira FUR-001 - Pedro Oliveira - Comercial Centro
2. Martelete MRT-001 - Jose da Silva - Residencial Vista Verde
3. Cinto CINTO-001 - Jose da Silva - Residencial Vista Verde
4. Cinto CINTO-002 - Maria Santos - Residencial Vista Verde
5. Capacete CAP-001 - Jose da Silva - Residencial Vista Verde
6. Capacete CAP-002 - Pedro Oliveira - Comercial Centro

PASSO 8: FAZER DEVOLUCOES (2)
-----------------------------
1. Furadeira FUR-001 - Pedro Oliveira - Condicao: Bom
2. Capacete CAP-001 - Jose da Silva - Condicao: Regular

PASSO 9: REGISTRAR CONSUMO (opcional)
-------------------------------------
1. Luva 1 cx - Ana Costa - (material consumido, nao sera devolvido)

PASSO 10: VERIFICAR RELATORIOS
------------------------------
URL: /almoxarifado/relatorios
- Posicao de Estoque
- Movimentacoes por Periodo
- Itens por Funcionario
- Consumo por Obra
- Alertas e Pendencias

===============================================================================
                         FIM DO GUIA
===============================================================================
Documento gerado para SIGE v9.0 - Janeiro/2026
Para criacao de scripts de teste E2E
