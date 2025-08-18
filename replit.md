# SIGE - Sistema de Gestão Empresarial

## Overview
Sistema multi-tenant de gestão empresarial com foco em propostas comerciais, gestão de funcionários, controle de obras e folha de pagamento automatizada.

## Arquitetura
- **Backend**: Flask + SQLAlchemy + PostgreSQL
- **Frontend**: Templates Jinja2 + Bootstrap
- **Deploy**: Docker via Replit
- **Database**: PostgreSQL com migrações automáticas

## Migrações Automáticas
Sistema implementado para resolver problemas de schema entre ambientes de desenvolvimento e produção:

### Como Funciona
- Arquivo `migrations.py` contém todas as migrações automáticas
- Executado automaticamente na inicialização da aplicação (app.py)
- Verifica se tabelas/colunas existem antes de criar
- Logs detalhados de todas as operações

### Problema Resolvido
- Ambiente de produção tinha tabela `proposta_templates` incompleta
- Sistema agora detecta e cria automaticamente todas as colunas necessárias:
  - categoria, itens_padrao, prazo_entrega_dias, validade_dias
  - percentual_nota_fiscal, itens_inclusos, itens_exclusos
  - condicoes, condicoes_pagamento, garantias
  - ativo, publico, uso_contador, admin_id, criado_por
  - criado_em, atualizado_em

### Logs de Migração
```
INFO:migrations:🔄 Iniciando migrações automáticas do banco de dados...
INFO:migrations:✅ Tabela proposta_templates já existe
INFO:migrations:✅ Coluna 'categoria' já existe na tabela proposta_templates
INFO:migrations:✅ Migrações automáticas concluídas com sucesso!
```

## Módulos Principais

### 1. Gestão de Propostas
- Templates reutilizáveis (`PropostaTemplate`)
- Propostas comerciais com itens e cálculos automáticos
- Sistema de categorização e filtros

### 2. Gestão de Funcionários
- Cadastro completo com fotos (base64)
- Controle de ponto automatizado
- Cálculo de horas extras e atrasos

### 3. Gestão de Obras
- Controle de obras e projetos
- RDO (Relatório Diário de Obra)
- Alocação de funcionários e equipamentos

### 4. Folha de Pagamento
- Cálculo automático baseado em registros de ponto
- Configuração salarial por funcionário
- Relatórios mensais detalhados

### 5. Sistema Multi-tenant
- Isolamento de dados por admin_id
- Controle de acesso baseado em roles
- Bypass de autenticação para desenvolvimento

## Recent Changes (18/08/2025)

### Migração de Schema Automática - RESOLVIDO ✅
- Implementado sistema de migrações automáticas completo
- Resolvido problema de colunas faltantes na tabela proposta_templates
- Sistema detecta e cria automaticamente tabela completa se necessário
- Migrações executadas automaticamente no deploy via Docker
- **Status**: Funcionando em produção

### Correção Admin ID - RESOLVIDO ✅
- Corrigido erro "null value in column admin_id" na tabela configuracao_empresa
- Adicionado admin_id ao MockCurrentUser no sistema de bypass
- Implementada verificação segura de admin_id nas views
- **Status**: Configurações da empresa funcionando normalmente

### Arquivos Adicionados
- `migrations.py` - Sistema de migrações automáticas
- `bypass_auth.py` - Atualizado com admin_id para desenvolvimento
- `configuracoes_views.py` - Corrigido para tratar admin_id adequadamente

## User Preferences
- Priorizar soluções automáticas que funcionem no deploy
- Evitar intervenção manual no banco de produção
- Implementar logs detalhados para debugging
- Sistema deve ser resiliente a diferenças entre ambientes

## Development Guidelines
- Usar sistema de migrações automáticas para mudanças de schema
- Testar localmente antes do deploy
- Manter logs informativos
- Implementar verificações de segurança antes de alterações no banco