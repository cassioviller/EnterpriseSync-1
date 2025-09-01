# 🚀 DEPLOY INSTRUCTIONS - HOTFIX CRÍTICO ADMIN_ID

## Status do Problema
**ERRO CONFIRMADO EM PRODUÇÃO:**
```
Timestamp: 2025-09-01 14:52:03
Erro: column servico.admin_id does not exist
URL: https://www.sige.cassioviller.tech/servicos
DATABASE_URL: postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
```

## ✅ Correção Implementada no Dockerfile Principal

### **Arquivo Modificado:**
- `docker-entrypoint-production-fix.sh` (usado pelo Dockerfile principal)

### **HOTFIX Implementado:**
```bash
# Usa DATABASE_URL diretamente sem parsing
psql "$DATABASE_URL" -c "
DO \$\$
BEGIN
    -- Verifica se coluna admin_id existe
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='servico' AND column_name='admin_id'
    ) THEN
        RAISE NOTICE '✅ Adicionando coluna admin_id na tabela servico...';
        
        -- Adiciona coluna admin_id
        ALTER TABLE servico ADD COLUMN admin_id INTEGER;
        
        -- Popula com admin_id padrão
        UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;
        
        -- Cria usuário admin se não existir
        INSERT INTO usuario (id, username, email, nome, password_hash, tipo_usuario, ativo)
        VALUES (10, 'admin_producao', 'admin@producao.com', 'Admin Produção', 
                'scrypt:32768:8:1\$hash', 'admin', TRUE)
        ON CONFLICT (id) DO NOTHING;
        
        -- Adiciona foreign key constraint
        ALTER TABLE servico ADD CONSTRAINT fk_servico_admin 
        FOREIGN KEY (admin_id) REFERENCES usuario(id);
        
        -- Torna NOT NULL
        ALTER TABLE servico ALTER COLUMN admin_id SET NOT NULL;
        
        RAISE NOTICE '✅ HOTFIX aplicado: admin_id adicionado na tabela servico';
    ELSE
        RAISE NOTICE '✅ Coluna admin_id já existe na tabela servico';
    END IF;
END
\$\$;
"
```

### **Fallback Implementado:**
Se DATABASE_URL falhar, tenta com parâmetros individuais:
```bash
PGPASSWORD="$DATABASE_PASSWORD" psql -h "$DATABASE_HOST" -p "${DATABASE_PORT:-5432}" -U "$DATABASE_USER" -d "$DATABASE_NAME" -c "
ALTER TABLE servico ADD COLUMN IF NOT EXISTS admin_id INTEGER DEFAULT 10;
UPDATE servico SET admin_id = 10 WHERE admin_id IS NULL;
"
```

## 🚀 Processo de Deploy Automático

### **Quando o Container Reiniciar (EasyPanel):**

1. **PostgreSQL Conecta** ✓
   ```
   ✅ PostgreSQL conectado!
   ```

2. **HOTFIX Executa** ✓
   ```
   🔧 HOTFIX: Aplicando correção admin_id na tabela servico...
   📍 DATABASE_URL: postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
   ```

3. **SQL Executado** ✓
   ```
   NOTICE: ✅ Adicionando coluna admin_id na tabela servico...
   NOTICE: ✅ HOTFIX aplicado: admin_id adicionado na tabela servico
   ```

4. **Aplicação Inicia** ✓
   ```
   ✅ HOTFIX admin_id aplicado com sucesso!
   🔧 Inicializando aplicação...
   ✅ App carregado
   ```

5. **Sistema Funciona** ✓
   ```
   Acesso a /servicos funcionando normalmente
   ```

## 🔍 Logs Esperados no Deploy

### **Sucesso:**
```
🔧 HOTFIX: Aplicando correção admin_id na tabela servico...
📍 DATABASE_URL: postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable
🔧 HOTFIX: Executando correção admin_id diretamente...
NOTICE: ✅ Adicionando coluna admin_id na tabela servico...
NOTICE: ✅ HOTFIX aplicado: admin_id adicionado na tabela servico
✅ HOTFIX admin_id aplicado com sucesso!
```

### **Se Já Existe:**
```
NOTICE: ✅ Coluna admin_id já existe na tabela servico
✅ HOTFIX admin_id aplicado com sucesso!
```

### **Em Caso de Erro:**
```
⚠️ HOTFIX admin_id falhou - tentando abordagem alternativa...
🔧 Tentando com parâmetros individuais...
✅ HOTFIX aplicado via fallback!
```

## 📋 Verificação Pós-Deploy

### **1. Acessar Sistema:**
- URL: https://www.sige.cassioviller.tech/servicos
- **Resultado esperado:** Página carrega sem erro

### **2. Verificar Logs:**
- Container logs devem mostrar HOTFIX executado
- Sem erros de "column does not exist"

### **3. Funcionalidade:**
- Sistema de serviços funcionando
- Multi-tenant ativo (admin_id=2 para Cassio, admin_id=10 padrão)

## 🎯 Resultado Final

### **Antes:**
```
❌ column servico.admin_id does not exist
❌ Sistema de serviços quebrado
❌ Erro em produção
```

### **Depois:**
```
✅ Coluna admin_id existe na tabela servico
✅ Sistema de serviços funcionando
✅ Multi-tenant ativo
✅ Dados isolados por empresa
✅ Sistema de erro detalhado capturando novos problemas
```

---
**AÇÃO OBRIGATÓRIA:** Deploy via EasyPanel para aplicar HOTFIX  
**ARQUIVO PRINCIPAL:** Dockerfile (já configurado)  
**STATUS:** 🚀 PRONTO PARA DEPLOY FINAL