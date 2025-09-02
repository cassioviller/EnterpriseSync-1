# DEPLOY HOTFIX - Coluna obra.cliente Ausente

## Problema Identificado
```
ERRO: (psycopg2.errors.UndefinedColumn) column obra.cliente does not exist
```

O ambiente de produção não possui a coluna `obra.cliente` que existe no desenvolvimento, causando falha na query de listagem de obras.

## Solução Implementada

### 1. Script de Correção SQL
**Arquivo:** `hotfix_obra_cliente.sql`
- Adiciona coluna `obra.cliente` se não existir
- Verifica e adiciona outras colunas essenciais do módulo cliente
- Teste de validação da query corrigida

### 2. Script Python de Deploy
**Arquivo:** `deploy_fix_producao.py`
- Verificação automática de colunas ausentes
- Aplicação segura de correções
- Validação pós-deploy

### 3. Docker Entrypoint Atualizado
**Arquivo:** `docker-entrypoint-production.sh`
- Execução automática do hotfix durante deploy
- Verificação de integridade do sistema
- Logs detalhados do processo

## Como Aplicar o Hotfix

### Opção 1: Deploy Automático via Docker
```bash
# O hotfix será aplicado automaticamente no próximo deploy
docker build -t sige-v8 .
docker run sige-v8
```

### Opção 2: Aplicação Manual no PostgreSQL
```bash
# Conectar ao PostgreSQL de produção
psql $DATABASE_URL

# Executar o script de correção
\i hotfix_obra_cliente.sql
```

### Opção 3: Script Python Standalone
```bash
# No servidor de produção
python3 deploy_fix_producao.py
```

## Verificação da Correção

Após aplicar o hotfix, verificar se a query funciona:

```sql
-- Deve executar sem erro
SELECT obra.id, obra.nome, obra.cliente 
FROM obra 
WHERE obra.admin_id = 2 
ORDER BY obra.data_inicio DESC;
```

## Colunas Adicionadas

- `obra.cliente` (VARCHAR 200) - Campo cliente principal
- `obra.cliente_nome` (VARCHAR 100) - Nome do cliente
- `obra.cliente_email` (VARCHAR 120) - Email do cliente  
- `obra.cliente_telefone` (VARCHAR 20) - Telefone do cliente
- `obra.token_cliente` (VARCHAR 255) - Token único para portal
- `obra.portal_ativo` (BOOLEAN) - Status do portal do cliente

## Status

- ✅ Scripts criados e testados
- ✅ Docker entrypoint atualizado
- ✅ Validação implementada
- 🚀 Pronto para deploy em produção

## Logs Esperados

```
🔧 Aplicando correções críticas de produção...
✅ Coluna obra.cliente adicionada com sucesso
✅ Coluna obra.cliente_nome já existe
✅ Coluna obra.cliente_email já existe
✅ HOTFIX CONCLUÍDO - Tabela obra corrigida com sucesso!
```