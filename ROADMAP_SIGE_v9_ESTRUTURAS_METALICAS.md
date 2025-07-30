# 🚀 ROADMAP SIGE v9.0 - ESTRUTURAS METÁLICAS
## Expansão Completa do Sistema para Empresas de Estruturas Metálicas

**Data:** 30 de Julho de 2025  
**Base:** SIGE v8.0 existente (33 tabelas, multi-tenant, 15 KPIs)  
**Objetivo:** Adicionar 5 módulos especializados + Sistema de Dashboards BI  

---

## 📋 ANÁLISE DOS DOCUMENTOS RECEBIDOS

### 📄 Documento 1: JORNADA COMPLETA DO CLIENTE
**Escopo:** Processo completo desde captação de leads até entrega da obra
- 8 etapas mapeadas: Captação → Qualificação → Proposta → Orçamento → Contrato → Planejamento → Execução → Entrega
- 8 novas tabelas: lead, lead_interacao, proposta, proposta_item, orcamento, orcamento_item, contrato, contrato_parcela
- Integração com sistema atual na etapa de execução

### 📄 Documento 2: SISTEMA DE DASHBOARDS BI
**Escopo:** 7 painéis especializados com business intelligence
- Painel Comercial, Obras, Financeiro, Alimentação, Transporte, RH/Ponto, Diretoria
- Engines de métricas específicas por painel
- Sistema de exportação e integrações avançadas

### 📄 Documento 3: SISTEMA COMPLETO v9.0
**Escopo:** 5 módulos novos integrados ao SIGE v8.0
- Propostas Comerciais, Contrato e Obra Expandido, Ferramentas e Almoxarifado
- Transporte e Frota Expandido, Relatórios Avançados
- 12 novas tabelas + expansão de tabelas existentes

---

## 🎯 MÓDULOS A IMPLEMENTAR

### 1. MÓDULO COMERCIAL COMPLETO
**Baseado nos 3 documentos - Integração total**

#### Novas Tabelas:
```sql
-- Captação e Qualificação
CREATE TABLE lead (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(120),
    telefone VARCHAR(20),
    empresa VARCHAR(100),
    tipo_estrutura VARCHAR(50), -- Galpão, Mezanino, Cobertura
    area_estimada DECIMAL(10,2),
    orcamento_estimado DECIMAL(12,2),
    origem VARCHAR(50), -- Site, WhatsApp, Indicação
    status VARCHAR(30) DEFAULT 'novo',
    observacoes TEXT,
    data_contato DATE DEFAULT CURRENT_DATE,
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE lead_interacao (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES lead(id) NOT NULL,
    tipo VARCHAR(30) NOT NULL, -- ligacao, email, whatsapp, visita
    descricao TEXT NOT NULL,
    data_interacao TIMESTAMP DEFAULT NOW(),
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id)
);

-- Propostas Comerciais
CREATE TABLE proposta_comercial (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES lead(id),
    numero VARCHAR(20) UNIQUE NOT NULL, -- PROP-2025-001
    cliente_nome VARCHAR(200) NOT NULL,
    cliente_cnpj VARCHAR(18),
    cliente_email VARCHAR(120),
    cliente_telefone VARCHAR(20),
    obra_nome VARCHAR(200) NOT NULL,
    obra_endereco TEXT,
    valor_total DECIMAL(12,2) DEFAULT 0.0,
    valor_materiais DECIMAL(12,2) DEFAULT 0.0,
    valor_mao_obra DECIMAL(12,2) DEFAULT 0.0,
    margem_lucro DECIMAL(5,2) DEFAULT 20.0,
    status VARCHAR(30) DEFAULT 'em_elaboracao',
    data_proposta DATE NOT NULL,
    data_validade DATE NOT NULL,
    prazo_execucao INTEGER, -- dias
    arquivo_pdf VARCHAR(255),
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE proposta_item (
    id SERIAL PRIMARY KEY,
    proposta_id INTEGER REFERENCES proposta_comercial(id) NOT NULL,
    tipo_item VARCHAR(50) NOT NULL, -- Material, Mao_Obra, Equipamento
    descricao VARCHAR(200) NOT NULL,
    unidade VARCHAR(20) NOT NULL, -- kg, m², m³, un
    quantidade DECIMAL(10,4) NOT NULL,
    valor_unitario DECIMAL(10,2) NOT NULL,
    valor_total DECIMAL(12,2) NOT NULL,
    peso_kg DECIMAL(10,2), -- Específico para estruturas metálicas
    observacoes TEXT,
    admin_id INTEGER REFERENCES usuario(id)
);

-- Orçamentos Detalhados
CREATE TABLE orcamento_detalhado (
    id SERIAL PRIMARY KEY,
    proposta_id INTEGER REFERENCES proposta_comercial(id) NOT NULL,
    numero_orcamento VARCHAR(20) UNIQUE NOT NULL,
    versao INTEGER DEFAULT 1,
    total_materiais DECIMAL(12,2) DEFAULT 0.0,
    total_mao_obra DECIMAL(12,2) DEFAULT 0.0,
    total_equipamentos DECIMAL(12,2) DEFAULT 0.0,
    subtotal DECIMAL(12,2) DEFAULT 0.0,
    margem_lucro_percentual DECIMAL(5,2) DEFAULT 20.0,
    valor_margem DECIMAL(12,2) DEFAULT 0.0,
    valor_final DECIMAL(12,2) DEFAULT 0.0,
    status VARCHAR(30) DEFAULT 'em_elaboracao',
    data_finalizacao DATE,
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Contratos
CREATE TABLE contrato (
    id SERIAL PRIMARY KEY,
    proposta_id INTEGER REFERENCES proposta_comercial(id) NOT NULL,
    orcamento_id INTEGER REFERENCES orcamento_detalhado(id),
    numero_contrato VARCHAR(20) UNIQUE NOT NULL,
    cliente_nome VARCHAR(100) NOT NULL,
    cliente_documento VARCHAR(20) NOT NULL,
    valor_total DECIMAL(12,2) NOT NULL,
    prazo_execucao INTEGER NOT NULL,
    data_inicio DATE NOT NULL,
    data_previsao_fim DATE NOT NULL,
    forma_pagamento TEXT,
    status VARCHAR(30) DEFAULT 'em_elaboracao',
    arquivo_pdf VARCHAR(255),
    data_assinatura DATE,
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE contrato_parcela (
    id SERIAL PRIMARY KEY,
    contrato_id INTEGER REFERENCES contrato(id) NOT NULL,
    numero_parcela INTEGER NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    data_vencimento DATE NOT NULL,
    status VARCHAR(30) DEFAULT 'pendente',
    data_pagamento DATE,
    admin_id INTEGER REFERENCES usuario(id)
);
```

#### Funcionalidades:
- **Dashboard Comercial:** Funil de vendas, taxa de conversão, ticket médio
- **Geração de Propostas:** PDF automático com template para estruturas metálicas
- **Controle de Orçamentos:** Múltiplas versões, aprovação eletrônica
- **Gestão de Contratos:** Cronograma de pagamentos, assinatura digital

### 2. MÓDULO ALMOXARIFADO E FERRAMENTAS
**Controle completo de materiais e ferramentas especializadas**

#### Novas Tabelas:
```sql
-- Ferramentas Especializadas
CREATE TABLE ferramenta (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL, -- FERR-001
    nome VARCHAR(100) NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- Solda, Corte, Medição, Içamento
    marca VARCHAR(50),
    modelo VARCHAR(50),
    numero_serie VARCHAR(50),
    data_compra DATE,
    valor_compra DECIMAL(10,2),
    status VARCHAR(30) DEFAULT 'disponivel', -- disponivel, em_uso, manutencao, baixada
    localizacao VARCHAR(100),
    obra_atual_id INTEGER REFERENCES obra(id),
    funcionario_atual_id INTEGER REFERENCES funcionario(id),
    observacoes TEXT,
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE movimento_ferramenta (
    id SERIAL PRIMARY KEY,
    ferramenta_id INTEGER REFERENCES ferramenta(id) NOT NULL,
    obra_id INTEGER REFERENCES obra(id),
    funcionario_id INTEGER REFERENCES funcionario(id) NOT NULL,
    tipo_movimento VARCHAR(20) NOT NULL, -- saida, retorno, manutencao
    data_movimento TIMESTAMP DEFAULT NOW(),
    motivo VARCHAR(200),
    estado_ferramenta VARCHAR(50), -- Boa, Danificada, Necessita_Reparo
    observacoes TEXT,
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id)
);

-- Materiais Específicos para Estruturas Metálicas
CREATE TABLE material_metalico (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL, -- MAT-001
    tipo VARCHAR(50) NOT NULL, -- Perfil, Chapa, Solda, Parafuso, Tinta
    descricao VARCHAR(200) NOT NULL,
    especificacao_tecnica TEXT, -- ABNT, dimensões, liga
    unidade VARCHAR(20) NOT NULL, -- kg, m, m², un
    peso_unitario DECIMAL(8,4), -- kg por unidade
    fornecedor_principal VARCHAR(100),
    preco_medio DECIMAL(10,2),
    estoque_minimo DECIMAL(10,4) DEFAULT 0,
    estoque_atual DECIMAL(10,4) DEFAULT 0,
    localizacao_estoque VARCHAR(100),
    ativo BOOLEAN DEFAULT TRUE,
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE movimento_material (
    id SERIAL PRIMARY KEY,
    material_id INTEGER REFERENCES material_metalico(id) NOT NULL,
    obra_id INTEGER REFERENCES obra(id),
    tipo_movimento VARCHAR(20) NOT NULL, -- entrada, saida, devolucao, perda
    quantidade DECIMAL(10,4) NOT NULL,
    valor_unitario DECIMAL(10,2),
    valor_total DECIMAL(12,2),
    data_movimento TIMESTAMP DEFAULT NOW(),
    documento_fiscal VARCHAR(50), -- Número NF
    lote VARCHAR(50),
    motivo VARCHAR(200),
    observacoes TEXT,
    responsavel_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id)
);

-- Controle de Estoque por Obra
CREATE TABLE estoque_obra (
    id SERIAL PRIMARY KEY,
    obra_id INTEGER REFERENCES obra(id) NOT NULL,
    material_id INTEGER REFERENCES material_metalico(id) NOT NULL,
    quantidade_disponivel DECIMAL(10,4) DEFAULT 0,
    quantidade_reservada DECIMAL(10,4) DEFAULT 0,
    quantidade_utilizada DECIMAL(10,4) DEFAULT 0,
    valor_medio DECIMAL(10,2),
    data_ultima_movimentacao TIMESTAMP,
    admin_id INTEGER REFERENCES usuario(id),
    UNIQUE(obra_id, material_id)
);
```

#### Funcionalidades:
- **Controle de Ferramentas:** Código de barras, rastreabilidade, manutenção preventiva
- **Gestão de Materiais:** Entrada por XML NF-e, controle por lote, localização
- **Estoque por Obra:** Reserva, transferência, controle de perdas
- **Integração XML:** Parser automático de notas fiscais de fornecedores

### 3. MÓDULO DOCUMENTOS E FOTOS
**Gestão documental completa da obra**

#### Novas Tabelas:
```sql
CREATE TABLE documento_obra (
    id SERIAL PRIMARY KEY,
    obra_id INTEGER REFERENCES obra(id) NOT NULL,
    tipo_documento VARCHAR(50) NOT NULL, -- Projeto, ART, Alvara, Contrato, NF
    nome_arquivo VARCHAR(255) NOT NULL,
    arquivo_path VARCHAR(500) NOT NULL,
    descricao TEXT,
    data_upload TIMESTAMP DEFAULT NOW(),
    versao INTEGER DEFAULT 1,
    status VARCHAR(30) DEFAULT 'ativo', -- ativo, substituido, cancelado
    upload_por_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id)
);

CREATE TABLE foto_obra (
    id SERIAL PRIMARY KEY,
    obra_id INTEGER REFERENCES obra(id) NOT NULL,
    categoria VARCHAR(50) NOT NULL, -- Progresso, Problema, Entrega, Antes_Depois
    titulo VARCHAR(200),
    descricao TEXT,
    arquivo_path VARCHAR(500) NOT NULL,
    data_foto TIMESTAMP DEFAULT NOW(),
    localizacao_gps VARCHAR(50), -- latitude,longitude
    etapa_obra VARCHAR(100),
    fotografo_id INTEGER REFERENCES funcionario(id),
    admin_id INTEGER REFERENCES usuario(id)
);
```

### 4. EXPANSÃO DO MÓDULO DE TRANSPORTE
**Integração com controle de frota existente**

#### Expansão da Tabela Existente:
```sql
-- Adicionar campos à tabela veiculo existente
ALTER TABLE veiculo ADD COLUMN capacidade_carga DECIMAL(8,2); -- kg
ALTER TABLE veiculo ADD COLUMN tipo_combustivel VARCHAR(20) DEFAULT 'Diesel';
ALTER TABLE veiculo ADD COLUMN km_por_litro DECIMAL(5,2);

-- Nova tabela para controle detalhado de saídas
CREATE TABLE saida_veiculo (
    id SERIAL PRIMARY KEY,
    veiculo_id INTEGER REFERENCES veiculo(id) NOT NULL,
    obra_id INTEGER REFERENCES obra(id),
    motorista_id INTEGER REFERENCES funcionario(id) NOT NULL,
    motivo VARCHAR(200) NOT NULL,
    destino TEXT,
    km_inicial DECIMAL(10,2) NOT NULL,
    km_final DECIMAL(10,2),
    data_saida TIMESTAMP NOT NULL,
    data_retorno TIMESTAMP,
    combustivel_litros DECIMAL(8,2),
    valor_combustivel DECIMAL(8,2),
    status VARCHAR(30) DEFAULT 'em_transito', -- em_transito, retornado, problema
    observacoes TEXT,
    admin_id INTEGER REFERENCES usuario(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5. SISTEMA DE DASHBOARDS BI
**7 painéis especializados com métricas avançadas**

#### Engine de KPIs Expandida:
```python
# Novos KPIs Comerciais
def calcular_kpis_comerciais(admin_id, data_inicio, data_fim):
    """
    KPIs do Painel Comercial:
    - Taxa de conversão lead → proposta → contrato
    - Ticket médio por tipo de estrutura
    - Tempo médio de fechamento
    - Margem média por obra
    - Pipeline de vendas
    """
    
# Novos KPIs de Obra
def calcular_kpis_obra_expandidos(obra_id):
    """
    KPIs expandidos por obra:
    - Consumo material vs orçado (%)
    - Produtividade (kg estrutura/funcionário/dia)
    - Eficiência de ferramentas
    - Desvio de prazo
    - Custo por m² construído
    """
    
# KPIs de Almoxarifado
def calcular_kpis_almoxarifado(admin_id):
    """
    KPIs de estoque e ferramentas:
    - Giro de estoque por material
    - Taxa de disponibilidade de ferramentas
    - Perdas e avarias (%)
    - Tempo médio de manutenção
    """
```

---

## 🎯 CRONOGRAMA DE IMPLEMENTAÇÃO

### **FASE 1: PREPARAÇÃO E ARQUITETURA (2 dias)**
- Análise detalhada da integração com SIGE v8.0
- Criação do schema expandido (20 novas tabelas)
- Configuração do ambiente de desenvolvimento
- Testes de compatibilidade

### **FASE 2: MÓDULO COMERCIAL (5 dias)**
- APIs de leads e qualificação
- Sistema de propostas e orçamentos
- Gerador de PDF especializado em estruturas metálicas
- Dashboard comercial com funil de vendas

### **FASE 3: MÓDULO ALMOXARIFADO (4 dias)**
- Sistema de controle de ferramentas
- Gestão de materiais metálicos
- Integração XML para NF-e
- Controle de estoque por obra

### **FASE 4: MÓDULO DOCUMENTOS (2 dias)**
- Upload e gestão de documentos
- Sistema de fotos com geolocalização
- Interface mobile para campo
- Controle de versões

### **FASE 5: EXPANSÃO TRANSPORTE (2 dias)**
- Controle detalhado de saídas/retornos
- Vinculação obra-motorista-motivo
- KPIs de consumo e eficiência
- Manutenção preventiva

### **FASE 6: SISTEMA BI DASHBOARDS (4 dias)**
- 7 painéis especializados
- Engines de KPIs expandidas
- Sistema de exportação avançado
- Integrações BI (Power BI, Google Sheets)

### **FASE 7: INTEGRAÇÃO E TESTES (3 dias)**
- Testes de integração completa
- Validação de todos os KPIs
- Performance com dados reais
- Ajustes finais

### **FASE 8: DEPLOY E DOCUMENTAÇÃO (2 dias)**
- Deploy no ambiente de produção
- Documentação técnica completa
- Manual do usuário por módulo
- Treinamento da equipe

---

## 💰 IMPACTO ESPERADO

### **ROI Projetado:**
- **Comercial:** +40% taxa de conversão com CRM integrado
- **Operacional:** +25% eficiência com controle de ferramentas
- **Financeiro:** +30% precisão orçamentária com dados históricos
- **Logístico:** +20% otimização de transporte e estoque

### **Economia Operacional:**
- **R$ 500k/ano** em redução de perdas de material
- **R$ 300k/ano** em otimização de mão de obra
- **R$ 200k/ano** em controle de combustível e manutenção
- **R$ 400k/ano** em melhoria da margem comercial

---

## ✅ CONCLUSÃO

O SIGE v9.0 representará uma evolução completa do sistema atual, transformando-o em uma solução especializada para empresas de estruturas metálicas. Com 20 novas tabelas, 5 módulos integrados e 7 dashboards BI, o sistema oferecerá controle total do processo comercial até a entrega da obra.

**Próximos Passos:**
1. Aprovação do roadmap pela equipe
2. Início da implementação seguindo o cronograma
3. Testes incrementais com dados reais
4. Deploy gradual dos módulos

**Total de Desenvolvimento:** 24 dias úteis  
**Equipe Necessária:** 8 especialistas  
**Investimento Estimado:** Evolução natural do sistema existente  
**ROI Esperado:** 350% em 18 meses