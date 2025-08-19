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

### Sistema de Numeração Customizável - IMPLEMENTADO ✅
- **Campo editável na criação**: Usuários podem definir números personalizados para propostas
- **Campo editável na edição**: Possibilidade de alterar números existentes
- **Backend atualizado**: Processamento correto do campo numero_proposta
- **Validação implementada**: Campo obrigatório com orientações claras
- **Interface intuitiva**: Placeholders e textos de ajuda para facilitar uso
- **Status**: Funcional em desenvolvimento, pronto para produção

### Sistema de PDF Personalizado Estruturas do Vale - IMPLEMENTADO ✅
- **Novo formato profissional**: Template PDF seguindo exatamente modelo da Estruturas do Vale
- **Design corporativo**: Header verde/cinza, logo personalizado, layout formal
- **Carta de apresentação**: Página inicial com dados formais do cliente
- **Sumário numerado**: Página com índice e numeração das seções
- **Estrutura completa**: 9 seções numeradas conforme padrão da empresa
- **Sistema de alternância**: Dropdown para escolher entre formato Estruturas do Vale e formato simples
- **Correção de bugs**: Corrigido erro de atributo 'valor_total' para 'subtotal'
- **Status**: Funcional em produção, testado e aprovado

## Recent Changes (19/08/2025)

### Sistema de Header PDF Personalizado - IMPLEMENTADO ✅
- **Campo header_pdf_base64**: Novo campo para upload de header completo do PDF
- **Substituição inteligente**: Header personalizado substitui logo+texto quando configurado
- **Dimensões recomendadas**: 800-1200px × 80-120px (proporção 10:1)
- **Validação JavaScript**: Alerta sobre dimensões ideais durante upload
- **Preview dinâmico**: Visualização em tempo real do header carregado
- **Aplicação automática**: Header aplicado em todas as páginas do PDF estruturado
- **Migração automática**: Campo adicionado via sistema de migrações
- **Status**: FUNCIONANDO EM DESENVOLVIMENTO 🚀

### Sistema de Personalização da Empresa - FUNCIONAL EM PRODUÇÃO ✅
- **Configurações visuais completas**: Upload de logo e seleção de cores personalizadas
- **Portal do cliente personalizado**: Cores e logo aplicadas dinamicamente nas propostas públicas
- **Campos implementados**: logo_base64, logo_pdf_base64, header_pdf_base64, cor_primaria, cor_secundaria, cor_fundo_proposta
- **Interface atualizada**: Link "Empresa" adicionado no dropdown Configurações
- **Carregamento dinâmico**: Configurações aplicadas em tempo real, inclusive em propostas existentes
- **Fallbacks implementados**: Sistema robusto para ambientes de produção
- **Scripts de migração**: Criados para garantir funcionamento em produção
- **Status**: FUNCIONANDO EM DESENVOLVIMENTO E PRODUÇÃO 🚀

### Sistema de Propostas - COMPLETO E TESTADO ✅
- **Debug completo realizado**: Todos os problemas identificados e corrigidos
- **Campo 'ordem' corrigido**: Adicionado valor padrão e setado corretamente no código
- **Rotas funcionando**: 20+ rotas do blueprint propostas registradas e testadas
- **Formulários processando**: Campos name corretos, valores salvos no banco
- **Templates funcionais**: listar.html, nova_proposta.html, visualizar.html
- **Fluxo completo testado**: Criação, listagem, cálculo de valores automático
- **Status**: PRONTO PARA DEPLOY EM PRODUÇÃO 🚀

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