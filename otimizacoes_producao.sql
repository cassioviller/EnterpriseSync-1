-- OTIMIZAÇÕES PRODUÇÃO - SIGE v8.0

-- Índices para multi-tenant
CREATE INDEX IF NOT EXISTS idx_funcionario_admin_ativo ON funcionario(admin_id, ativo);
CREATE INDEX IF NOT EXISTS idx_obra_admin_ativo ON obra(admin_id, ativo);
CREATE INDEX IF NOT EXISTS idx_veiculo_admin_ativo ON veiculo(admin_id, ativo);

-- Índices para registros de ponto
CREATE INDEX IF NOT EXISTS idx_registro_ponto_data ON registro_ponto(data);
CREATE INDEX IF NOT EXISTS idx_registro_ponto_funcionario_data ON registro_ponto(funcionario_id, data);

-- Índices para custos
CREATE INDEX IF NOT EXISTS idx_custo_obra_data ON custo_obra(data);
CREATE INDEX IF NOT EXISTS idx_registro_alimentacao_data ON registro_alimentacao(data);

-- Índices para RDOs
CREATE INDEX IF NOT EXISTS idx_rdo_data ON rdo(data_relatorio);
CREATE INDEX IF NOT EXISTS idx_rdo_obra_data ON rdo(obra_id, data_relatorio);

-- Views otimizadas
CREATE OR REPLACE VIEW vw_funcionarios_ativos AS
SELECT 
    f.id, f.nome, f.codigo, f.admin_id, f.salario,
    d.nome as departamento,
    h.nome as horario_trabalho
FROM funcionario f
LEFT JOIN departamento d ON f.departamento_id = d.id
LEFT JOIN horario_trabalho h ON f.horario_trabalho_id = h.id
WHERE f.ativo = true;

-- Atualizar estatísticas
ANALYZE funcionario;
ANALYZE obra;
ANALYZE registro_ponto;
ANALYZE custo_obra;
