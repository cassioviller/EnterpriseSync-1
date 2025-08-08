# 🚀 INSTRUÇÕES DE DEPLOY - Correção admin_id

## 📋 **PROBLEMA IDENTIFICADO**

Na produção, a tabela `outro_custo` não possui a coluna `admin_id`, causando:
- ❌ Erro 500: `UndefinedColumn: admin_id does not exist`
- ❌ Falha no carregamento de perfis de funcionários
- ❌ Sistema multi-tenant não funciona

## 🔧 **SOLUÇÃO AUTOMATIZADA**

### **Opção 1: Script de Deploy Direto**

Execute no servidor de produção:

```bash
# Fazer upload do script
python deploy_admin_id_fix.py
```

### **Opção 2: Docker com Entrypoint Automatizado**

O Dockerfile foi atualizado para executar automaticamente:

```dockerfile
# Novo entrypoint que executa migrações
ENTRYPOINT ["/app/entrypoint.sh"]
```

### **Opção 3: Execução Manual SQL**

Se precisar executar diretamente no banco:

```sql
-- 1. Adicionar coluna admin_id
ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER;

-- 2. Atualizar registros existentes
UPDATE outro_custo 
SET admin_id = (
    SELECT admin_id 
    FROM funcionario 
    WHERE funcionario.id = outro_custo.funcionario_id
    LIMIT 1
)
WHERE admin_id IS NULL;

-- 3. Verificar resultado
SELECT COUNT(*) FROM outro_custo WHERE admin_id IS NOT NULL;
```

## 📁 **ARQUIVOS CRIADOS PARA DEPLOY**

1. **`deploy_admin_id_fix.py`** - Script principal de correção
2. **`migrations/add_admin_id_to_outro_custo.py`** - Migração automática
3. **`scripts/deploy_migrations.py`** - Executor de migrações
4. **`entrypoint.sh`** - Script de entrada do container
5. **`Dockerfile`** - Atualizado com processo de deploy

## ✅ **VERIFICAÇÃO PÓS-DEPLOY**

### **Estrutura Esperada:**
```
Tabela outro_custo (12 colunas):
1. id
2. funcionario_id
3. data
4. tipo
5. categoria
6. valor
7. descricao
8. obra_id
9. percentual
10. created_at
11. kpi_associado
12. admin_id ← NOVA COLUNA
```

### **Teste de Funcionalidade:**
```bash
# Testar acesso ao perfil (deve retornar 200 ou 302, nunca 500)
curl -I http://localhost:5000/funcionarios/96/perfil

# Verificar logs (não deve ter erros de UndefinedColumn)
docker logs [container_id]
```

## 🎯 **PROCESSO COMPLETO DE DEPLOY**

### **Para Hostinger EasyPanel:**

1. **Upload dos arquivos:**
   - Todos os scripts de migração
   - Dockerfile atualizado
   - entrypoint.sh

2. **Build do container:**
   ```bash
   docker build -t sige:v8.1 .
   ```

3. **Deploy automático:**
   - O entrypoint.sh executa migrações automaticamente
   - Verifica integridade do sistema
   - Inicia aplicação somente se tudo estiver correto

### **Para outros ambientes:**

1. **Execute o script direto:**
   ```bash
   python deploy_admin_id_fix.py
   ```

2. **Ou execute via Docker:**
   ```bash
   docker run -e DATABASE_URL="..." sige:v8.1
   ```

## 🔒 **VARIÁVEIS DE AMBIENTE NECESSÁRIAS**

- `DATABASE_URL` - String de conexão PostgreSQL
- `SESSION_SECRET` - Chave secreta do Flask (opcional)

## 📊 **LOGS ESPERADOS**

```
🚀 INICIANDO DEPLOY - Correção admin_id
🔍 Verificando existência da coluna admin_id...
🔧 Adicionando coluna admin_id...
✅ Coluna admin_id adicionada
🔄 Atualizando registros existentes...
✅ 58 registros atualizados com admin_id
💾 Mudanças salvas no banco
🎯 DEPLOY CONCLUÍDO COM SUCESSO
```

## ⚠️ **IMPORTANTE**

- Este processo é **idempotente** - pode ser executado múltiplas vezes
- Não afeta dados existentes
- Backup automático não é necessário (apenas adiciona coluna)
- Compatível com PostgreSQL 10+

---

**🚀 PRONTO PARA DEPLOY EM PRODUÇÃO**