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

## Recent Changes (21/08/2025)

### ✅ Sistema de Paginação A4 Profissional - IMPLEMENTADO
- **Template completo**: `pdf_estruturas_vale_paginado.html` com 4 páginas estruturadas
- **Header fixo no topo**: Posicionamento absoluto em todas as páginas
- **Quebras de página**: CSS forçado com `!important` e propriedades CSS3
- **Arrays JSON processados**: Listas formatadas corretamente do banco de dados
- **Dimensões A4 exatas**: 210mm x 297mm com aproveitamento máximo do espaço
- **Estrutura profissional**: Baseada no PDF de referência da Estruturas do Vale
- **Status**: FUNCIONAL - Ready para deploy automático

## Recent Changes (21/08/2025)

### ✅ CORREÇÃO COMPLETA: Admin ID Dinâmico Implementado
- **Problema resolvido**: Sistema usava admin_id fixo/hardcoded em várias rotas
- **Headers PDF funcionando**: PDFs agora carregam configurações da empresa correta
- **Configurações carregando**: Formulários não ficam mais vazios, puxam dados do admin correto
- **Sistema verdadeiramente multitenant**: Cada usuário vê apenas dados da sua empresa
- **Lógica implementada**: Funcionários usam admin_id do chefe, administradores usam próprio ID
- **Fallback seguro**: Sistema continua funcionando mesmo em desenvolvimento
- **Status**: FUNCIONANDO - Headers PDF e configurações operacionais

### 🚨 HOTFIX: Foreign Key Violation RESOLVIDO ✅
- **Problema crítico em produção**: Foreign key violation para admin_id=10 não existir na tabela usuario
- **Sistema multitenant correto**: Problema era apenas usuário faltante em produção vs desenvolvimento
- **Dockerfile corrigido**: Script de deploy agora cria usuários com IDs específicos (4, 10)
- **Migrações automáticas**: Sistema garante usuários necessários existem antes de operações
- **Configurações robustas**: Substituído session.add() por session.merge() para prevenir conflitos
- **Deploy automático**: Hotfix pronto para aplicação em produção via Docker
- **Status**: Corrigido em desenvolvimento, aguardando deploy em produção

## Recent Changes (20/08/2025)

### Sistema de Organização Drag-and-Drop - IMPLEMENTADO ✅
- **Interface completa**: Sistema avançado para organizar propostas por arrastar e soltar
- **Múltiplos templates**: Carregamento de vários templates onde cada um vira uma categoria separada
- **Campos de banco**: categoria_titulo, template_origem_id/nome, grupo_ordem, item_ordem_no_grupo
- **API completa**: Endpoints para listar templates, carregar múltiplos e salvar organização
- **PDF dinâmico**: Template atualizado para exibir múltiplas categorias com subtotais
- **Interface moderna**: Design profissional com Sortable.js e Bootstrap
- **Botão na listagem**: Link "Organizar" adicionado na lista de propostas
- **Status**: FUNCIONAL - Sistema completo implementado

### Correção de Quebras de Linha PDF - IMPLEMENTADO ✅
- **Problema identificado**: PDF não quebrava linhas com vírgulas como separador
- **Solução aplicada**: Template atualizado para quebrar tanto ; quanto , seguidos de <br>
- **Seções corrigidas**: Itens inclusos e exclusos agora quebram corretamente
- **Status**: CORRIGIDO

### Sistema de Header PDF Personalizado - LÓGICA FINAL ✅
- **Especificação do cliente**: APENAS header da imagem cadastrada, sem header fixo verde
- **Lógica implementada**: SE existe header_pdf_base64 MOSTRA ele, SENÃO fica vazio
- **Template final**: `pdf_estruturas_vale_final.html` - sem fallback para header verde
- **Comportamento**: Sem imagem cadastrada = PDF sem header (conforme solicitado)
- **Deploy automático**: Correção aplicada automaticamente via Docker
- **Status**: IMPLEMENTADO CONFORME ESPECIFICAÇÃO 🚀

### Sistema de Header PDF Personalizado - IMPLEMENTADO ✅
- **Campo header_pdf_base64**: Campo para upload de header completo do PDF
- **Substituição completa**: Header personalizado substitui totalmente header verde
- **Dimensões recomendadas**: 800-1200px × 80-120px (proporção 10:1)
- **Aplicação automática**: Header aplicado em todas as páginas do PDF estruturado
- **Migração automática**: Campo adicionado via sistema de migrações

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