-- ================================================================================
-- SCRIPT DE VALIDAÇÃO PRÉ-MIGRAÇÃO 48 - PRODUÇÃO EASYPANEL
-- ================================================================================
-- Data: 30/10/2025
-- Objetivo: Verificar quais tabelas JÁ TÊM admin_id antes de executar migração 48
-- ================================================================================

-- 1. VERIFICAR QUAIS TABELAS JÁ TÊM COLUNA admin_id
SELECT 
    c.table_name,
    CASE 
        WHEN c.column_name = 'admin_id' THEN '✅ JÁ TEM'
        ELSE '❌ FALTA'
    END as status_admin_id
FROM information_schema.tables t
LEFT JOIN information_schema.columns c 
    ON c.table_name = t.table_name AND c.column_name = 'admin_id'
WHERE t.table_schema = 'public'
  AND t.table_name IN (
    'departamento', 'funcao', 'horario_trabalho',
    'servico_obra', 'historico_produtividade_servico',
    'tipo_ocorrencia', 'ocorrencia', 'calendario_util',
    'centro_custo', 'receita', 'orcamento_obra',
    'fluxo_caixa', 'registro_alimentacao',
    'rdo_mao_obra', 'rdo_equipamento', 'rdo_ocorrencia', 'rdo_foto',
    'notificacao_cliente', 'proposta_itens', 'proposta_arquivos'
  )
ORDER BY 
    CASE WHEN c.column_name = 'admin_id' THEN 0 ELSE 1 END,
    t.table_name;

-- 2. CONTAR REGISTROS EM CADA TABELA (para estimar impacto da migração)
SELECT 
    'departamento' as tabela, COUNT(*) as total_registros FROM departamento
UNION ALL
SELECT 'funcao', COUNT(*) FROM funcao
UNION ALL
SELECT 'horario_trabalho', COUNT(*) FROM horario_trabalho
UNION ALL
SELECT 'servico_obra', COUNT(*) FROM servico_obra
UNION ALL
SELECT 'historico_produtividade_servico', COUNT(*) FROM historico_produtividade_servico
UNION ALL
SELECT 'tipo_ocorrencia', COUNT(*) FROM tipo_ocorrencia
UNION ALL
SELECT 'ocorrencia', COUNT(*) FROM ocorrencia
UNION ALL
SELECT 'calendario_util', COUNT(*) FROM calendario_util
UNION ALL
SELECT 'centro_custo', COUNT(*) FROM centro_custo
UNION ALL
SELECT 'receita', COUNT(*) FROM receita
UNION ALL
SELECT 'orcamento_obra', COUNT(*) FROM orcamento_obra
UNION ALL
SELECT 'fluxo_caixa', COUNT(*) FROM fluxo_caixa
UNION ALL
SELECT 'registro_alimentacao', COUNT(*) FROM registro_alimentacao
UNION ALL
SELECT 'rdo_mao_obra', COUNT(*) FROM rdo_mao_obra
UNION ALL
SELECT 'rdo_equipamento', COUNT(*) FROM rdo_equipamento
UNION ALL
SELECT 'rdo_ocorrencia', COUNT(*) FROM rdo_ocorrencia
UNION ALL
SELECT 'rdo_foto', COUNT(*) FROM rdo_foto
UNION ALL
SELECT 'notificacao_cliente', COUNT(*) FROM notificacao_cliente
UNION ALL
SELECT 'proposta_itens', COUNT(*) FROM proposta_itens
UNION ALL
SELECT 'proposta_arquivos', COUNT(*) FROM proposta_arquivos
ORDER BY total_registros DESC;

-- 3. VERIFICAR ADMINS ATIVOS NO SISTEMA
SELECT 
    id,
    nome as nome_usuario,
    email,
    tipo_usuario,
    ativo
FROM usuario
WHERE tipo_usuario IN ('administrador', 'ADMIN', 'SUPER_ADMIN')
ORDER BY id;

-- 4. VERIFICAR SE HÁ REGISTROS ÓRFÃOS POTENCIAIS
-- (Funcionários sem admin válido)
SELECT 
    COUNT(*) as funcionarios_sem_admin_valido
FROM funcionario f
WHERE NOT EXISTS (
    SELECT 1 FROM usuario u 
    WHERE u.id = f.admin_id 
    AND u.tipo_usuario IN ('administrador', 'ADMIN', 'SUPER_ADMIN')
);

-- 5. VERIFICAR OBRAS E SEUS ADMIN_IDS
SELECT 
    admin_id,
    COUNT(*) as total_obras,
    COUNT(DISTINCT id) as obras_distintas
FROM obra
GROUP BY admin_id
ORDER BY admin_id;

-- 6. VERIFICAR FUNCIONÁRIOS E SEUS ADMIN_IDS
SELECT 
    admin_id,
    COUNT(*) as total_funcionarios,
    COUNT(CASE WHEN ativo = true THEN 1 END) as funcionarios_ativos
FROM funcionario
GROUP BY admin_id
ORDER BY admin_id;

-- ================================================================================
-- NOTAS IMPORTANTES:
-- ================================================================================
-- 1. Execute este script ANTES de fazer deploy da migração 48
-- 2. Faça BACKUP COMPLETO do banco antes de executar a migração
-- 3. A migração 48 é IDEMPOTENTE: pode executar múltiplas vezes
-- 4. Se detectar órfãos, corrija manualmente antes de executar migração
-- ================================================================================
