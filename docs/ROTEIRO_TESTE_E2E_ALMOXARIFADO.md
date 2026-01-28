# Roteiro de Cadastro para Teste E2E - Módulo Almoxarifado

## Objetivo

Fornecer os dados fictícios e a ordem correta de cadastro para realizar um teste E2E completo no módulo de Almoxarifado, respeitando as dependências entre os formulários.

## Ordem de Execução (Respeitando Dependências)

1.  **Cadastrar Categorias** (não depende de nada)
2.  **Cadastrar Fornecedores** (não depende de nada)
3.  **Cadastrar Itens** (depende de Categorias)
4.  **Registrar Entradas** (depende de Itens e Fornecedores)
5.  **Registrar Saídas** (depende de Entradas, Funcionários e Obras)
6.  **Registrar Devoluções** (depende de Saídas)

---

## Passo 1: Cadastrar Categorias

**URL:** `/almoxarifado/categorias/criar`

| Nome | Tipo de Controle | Permite Devolução |
| :--- | :--- | :--- |
| Materiais de Construção | CONSUMIVEL | Não |
| Ferramentas Manuais | SERIALIZADO | Sim |
| Equipamentos de Segurança | SERIALIZADO | Sim |
| EPIs Descartáveis | CONSUMIVEL | Não |
| Equipamentos Elétricos | SERIALIZADO | Sim |

---

## Passo 2: Cadastrar Fornecedores

**URL:** `/almoxarifado/fornecedores/criar`

| Nome | CNPJ | Cidade/UF |
| :--- | :--- | :--- |
| Materiais Construção ABC Ltda | 11.111.111/0001-11 | São Paulo/SP |
| Ferramentas Brasil SA | 22.222.222/0001-22 | Campinas/SP |
| EPI Segurança Total Ltda | 33.333.333/0001-33 | Rio de Janeiro/RJ |
| Ferragens e Parafusos Ltda | 44.444.444/0001-44 | Belo Horizonte/MG |
| Equipamentos Industriais ME | 55.555.555/0001-55 | Curitiba/PR |

---

## Passo 3: Cadastrar Itens

**URL:** `/almoxarifado/itens/criar`

| Código | Nome | Categoria | Tipo | Unidade | Estoque Mínimo |
| :--- | :--- | :--- | :--- | :--- | :--- |
| MAT001 | Cimento CP-II 50kg | Materiais de Construção | CONSUMIVEL | sc | 20 |
| MAT002 | Areia Média m3 | Materiais de Construção | CONSUMIVEL | m3 | 5 |
| MAT003 | Brita 1 m3 | Materiais de Construção | CONSUMIVEL | m3 | 5 |
| MAT004 | Tijolo Cerâmico 6 furos | Materiais de Construção | CONSUMIVEL | un | 500 |
| MAT005 | Vergalhão CA-50 10mm | Materiais de Construção | CONSUMIVEL | kg | 100 |
| EPI001 | Luva Descartável | EPIs Descartáveis | CONSUMIVEL | cx | 10 |
| EPI002 | Máscara PFF2 | EPIs Descartáveis | CONSUMIVEL | un | 50 |
| FER001 | Furadeira Bosch 500W | Ferramentas Manuais | SERIALIZADO | un | 1 |
| FER002 | Martelete Makita 800W | Ferramentas Manuais | SERIALIZADO | un | 1 |
| SEG001 | Cinto Paraquedista | Equipamentos de Segurança | SERIALIZADO | un | 2 |
| SEG002 | Capacete com Jugular | Equipamentos de Segurança | SERIALIZADO | un | 5 |
| ELE001 | Extensão Elétrica 20m | Equipamentos Elétricos | SERIALIZADO | un | 3 |
| ELE002 | Lixadeira Orbital | Equipamentos Elétricos | SERIALIZADO | un | 1 |

---

## Passo 4: Registrar Entradas

**URL:** `/almoxarifado/entrada`

| Fornecedor | Item | Quantidade/Séries | Preço Unitário | Nota Fiscal |
| :--- | :--- | :--- | :--- | :--- |
| Materiais Construção ABC | Cimento CP-II 50kg | 100 | 35.00 | NF-001 |
| Materiais Construção ABC | Areia Média m3 | 10 | 120.00 | NF-001 |
| Materiais Construção ABC | Tijolo Cerâmico 6 furos | 2000 | 0.80 | NF-002 |
| Ferramentas Brasil SA | Furadeira Bosch 500W | FUR-001, FUR-002, FUR-003 | 250.00 | NF-003 |
| Ferramentas Brasil SA | Martelete Makita 800W | MRT-001, MRT-002 | 600.00 | NF-003 |
| EPI Segurança Total Ltda | Cinto Paraquedista | CINTO-001, CINTO-002 | 150.00 | NF-004 |
| EPI Segurança Total Ltda | Capacete com Jugular | CAP-001, CAP-002, CAP-003, CAP-004, CAP-005 | 40.00 | NF-004 |
| EPI Segurança Total Ltda | Luva Descartável | 20 | 15.00 | NF-005 |

---

## Passo 5: Registrar Saídas

**URL:** `/almoxarifado/saida`

| Funcionário | Obra | Item | Quantidade/Série |
| :--- | :--- | :--- | :--- |
| José da Silva | Residencial Vista Verde | Cimento CP-II 50kg | 20 |
| José da Silva | Residencial Vista Verde | Tijolo Cerâmico 6 furos | 500 |
| Pedro Oliveira | Comercial Centro | Furadeira Bosch 500W | FUR-001 |
| José da Silva | Residencial Vista Verde | Martelete Makita 800W | MRT-001 |
| José da Silva | Residencial Vista Verde | Cinto Paraquedista | CINTO-001 |
| Maria Santos | Residencial Vista Verde | Cinto Paraquedista | CINTO-002 |
| Ana Costa | Industrial Zona Norte | Luva Descartável | 2 |

---

## Passo 6: Registrar Devoluções

**URL:** `/almoxarifado/devolucao`

| Funcionário | Item | Série | Condição |
| :--- | :--- | :--- | :--- |
| Pedro Oliveira | Furadeira Bosch 500W | FUR-001 | Bom |
| José da Silva | Cinto Paraquedista | CINTO-001 | Regular |
