# 🚨 HOTFIX PRODUÇÃO - RESTAURANTES

## PROBLEMA IDENTIFICADO
❌ Ambiente de produção com erro 500 ao acessar `/restaurantes`  
❌ Colunas faltantes na tabela `restaurante`

## SOLUÇÃO URGENTE

### 1. Execute o script de correção:
```bash
python fix_restaurantes_producao.py
```

### 2. OU execute manualmente no banco:
```sql
-- Adicionar colunas faltantes
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS responsavel VARCHAR(100);
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_almoco FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_jantar FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_lanche FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS observacoes TEXT;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS admin_id INTEGER;

-- Associar restaurantes ao primeiro admin
UPDATE restaurante 
SET admin_id = (SELECT id FROM usuario WHERE tipo_usuario = 'ADMIN' LIMIT 1)
WHERE admin_id IS NULL OR admin_id = 0;
```

### 3. Reiniciar aplicação:
```bash
# No EasyPanel ou servidor
sudo systemctl restart sige
# OU
docker restart sige-container
```

## VERIFICAÇÃO
Após executar, acesse:
- ✅ `/restaurantes` deve carregar sem erro
- ✅ Menu "Alimentação > Restaurantes" funcional
- ✅ CRUD completo operacional

## CAUSA RAIZ
O modelo foi atualizado mas o banco de produção não foi migrado automaticamente.

**Status:** 🚨 CORREÇÃO URGENTE NECESSÁRIA