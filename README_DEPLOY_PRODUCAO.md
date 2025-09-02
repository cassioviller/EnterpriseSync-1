# DEPLOY CRÍTICO - SIGE v8.0 Produção

## Problema Identificado
```
ERRO: (psycopg2.errors.UndefinedColumn) column obra.cliente does not exist
```

## Solução Implementada

### 🔧 Correções Automáticas
1. **Script Python:** `deploy_fix_producao.py` - Verificação e correção automática
2. **Script SQL:** `hotfix_obra_cliente.sql` - Correção direta no PostgreSQL  
3. **Docker Entrypoint:** Atualizado com hotfix automático

### 📋 Processo de Deploy

#### Opção 1: Deploy Docker Completo (Recomendado)
```bash
# Build da imagem com correções
docker build -t sige-v8-hotfix .

# Deploy (correções aplicadas automaticamente)
docker run -e DATABASE_URL=$DATABASE_URL sige-v8-hotfix
```

#### Opção 2: Correção Manual Rápida
```bash
# Conectar ao PostgreSQL de produção
psql $DATABASE_URL

# Executar correção
\i hotfix_obra_cliente.sql
```

#### Opção 3: Script Python Standalone
```bash
# No ambiente de produção
export DATABASE_URL="sua_url_postgresql"
python3 deploy_fix_producao.py
```

### ✅ Validação do Fix

Após aplicar, testar:
```sql
SELECT obra.id, obra.nome, obra.cliente 
FROM obra 
WHERE obra.admin_id = 2 
LIMIT 5;
```

### 📊 Logs Esperados
```
🚀 INICIANDO DEPLOY - CORREÇÃO CRÍTICA DE PRODUÇÃO
🔍 Verificando estrutura da tabela obra...
⚠️ Coluna ausente: cliente
🔧 Adicionando 1 colunas ausentes...
✅ Coluna cliente adicionada com sucesso!
🎉 DEPLOY CONCLUÍDO COM SUCESSO!
```

### 🚨 Arquivos Críticos
- `deploy_fix_producao.py` - Script principal de correção
- `hotfix_obra_cliente.sql` - SQL direto para correção
- `docker-entrypoint-production-fix.sh` - Entrypoint com hotfix
- `DEPLOY_HOTFIX_OBRA_CLIENTE.md` - Documentação detalhada

### 🔄 Status da Correção
- ✅ **Script Python:** Testado e funcional
- ✅ **Script SQL:** Validado para PostgreSQL
- ✅ **Docker Integration:** Entrypoint atualizado  
- ✅ **Documentação:** Completa
- 🚀 **Pronto para Deploy**

### 💡 Próximos Passos
1. Aplicar correção em produção (uma das 3 opções)
2. Verificar funcionamento da listagem de obras
3. Monitorar logs para confirmar sucesso
4. Sistema estará 100% operacional

---
**Data:** 02/09/2025 | **Status:** HOTFIX PRONTO | **Prioridade:** CRÍTICA