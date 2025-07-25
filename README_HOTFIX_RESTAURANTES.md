# 🚨 HOTFIX URGENTE - RESTAURANTES PRODUÇÃO

## PROBLEMA
Erro 500 ao acessar `/restaurantes` em produção devido a colunas faltantes no banco.

## SOLUÇÃO RÁPIDA

### 🎯 Opção 1: SQL Direto (MAIS RÁPIDO)
Execute no banco PostgreSQL de produção:
```sql
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS responsavel VARCHAR(100);
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_almoco FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_jantar FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_lanche FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS observacoes TEXT;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS admin_id INTEGER;

UPDATE restaurante 
SET admin_id = (SELECT id FROM usuario WHERE tipo_usuario = 'ADMIN' LIMIT 1)
WHERE admin_id IS NULL OR admin_id = 0;
```

### 🐍 Opção 2: Script Python
No terminal de produção:
```bash
python fix_restaurantes_producao.py
```

### 📁 Opção 3: Arquivo SQL
Execute o arquivo `hotfix_restaurantes_simples.sql` completo.

## VERIFICAÇÃO
Após executar qualquer opção:
1. ✅ Acesse `/restaurantes` - deve funcionar
2. ✅ Menu "Alimentação > Restaurantes" acessível  
3. ✅ CRUD completo operacional

## CAUSA RAIZ
O código foi atualizado com novos campos no modelo `Restaurante`, mas o banco de produção não foi migrado automaticamente.

---
**Status:** 🚨 CORREÇÃO URGENTE NECESSÁRIA  
**Tempo estimado:** 2-5 minutos  
**Impacto:** Módulo de restaurantes inacessível