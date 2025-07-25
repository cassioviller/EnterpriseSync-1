-- HOTFIX URGENTE: Adicionar colunas faltantes na tabela restaurante
-- Execute este SQL diretamente no banco de produção

-- 1. Verificar estrutura atual
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'restaurante'
ORDER BY column_name;

-- 2. Adicionar colunas faltantes (IF NOT EXISTS evita erro se já existir)
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS responsavel VARCHAR(100);
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_almoco FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_jantar FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS preco_lanche FLOAT DEFAULT 0.0;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS observacoes TEXT;
ALTER TABLE restaurante ADD COLUMN IF NOT EXISTS admin_id INTEGER;

-- 3. Associar restaurantes existentes ao primeiro admin
UPDATE restaurante 
SET admin_id = (SELECT id FROM usuario WHERE tipo_usuario = 'ADMIN' LIMIT 1)
WHERE admin_id IS NULL OR admin_id = 0;

-- 4. Verificar resultado
SELECT 
    id, 
    nome,
    responsavel,
    preco_almoco,
    preco_jantar,
    preco_lanche,
    admin_id
FROM restaurante 
LIMIT 5;

-- 5. Contar restaurantes
SELECT COUNT(*) as total_restaurantes FROM restaurante;