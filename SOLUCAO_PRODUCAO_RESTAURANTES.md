# 🚨 SOLUÇÃO PARA PRODUÇÃO - MÓDULO RESTAURANTES

## PROBLEMA
O ambiente de produção está apresentando erro 500 ao acessar `/restaurantes` porque o banco de dados não tem as colunas necessárias que foram adicionadas no código.

## CAUSA
O modelo `Restaurante` foi atualizado no código com novos campos, mas o banco de produção não foi migrado.

## SOLUÇÃO URGENTE

### Opção 1: Script Automático (RECOMENDADO)
1. Acesse o terminal do servidor de produção
2. Navegue até o diretório da aplicação
3. Execute:
```bash
python fix_restaurantes_producao.py
```

### Opção 2: SQL Manual
Execute estas queries direto no banco PostgreSQL de produção:

```sql
-- Verificar colunas existentes
SELECT column_name FROM information_schema.columns WHERE table_name = 'restaurante';

-- Adicionar colunas faltantes
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS responsavel VARCHAR(100);
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_almoco FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_jantar FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_lanche FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS observacoes TEXT;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS admin_id INTEGER;

-- Associar restaurantes existentes ao admin
UPDATE restaurante 
SET admin_id = (SELECT id FROM usuario WHERE tipo_usuario = 'ADMIN' LIMIT 1)
WHERE admin_id IS NULL OR admin_id = 0;
```

### Opção 3: EasyPanel / Docker
Se usando Docker/container:
1. Pare o container
2. Execute o script de correção
3. Reinicie o container

## VERIFICAÇÃO
Após a correção, teste:
- ✅ Acesse `/restaurantes` - deve carregar sem erro
- ✅ Menu "Alimentação > Restaurantes" funcional
- ✅ Pode criar/editar/excluir restaurantes

## ARQUIVOS CRIADOS
- `fix_restaurantes_producao.py` - Script de correção automática
- `HOTFIX_PRODUCAO_RESTAURANTES.md` - Documentação do hotfix

## STATUS
🚨 **CORREÇÃO URGENTE NECESSÁRIA EM PRODUÇÃO**

O ambiente local está funcionando corretamente. O problema é específico do ambiente de produção que precisa da atualização do banco de dados.