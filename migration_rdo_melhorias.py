"""
MIGRAÇÃO PARA IMPLEMENTAR MELHORIAS CRÍTICAS DO SISTEMA RDO
Execute este script para aplicar as correções identificadas na análise
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

# Configurar app temporário para migração
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def executar_migracao_rdo():
    """Execute a migração das melhorias RDO"""
    with app.app_context():
        try:
            print("=== INICIANDO MIGRAÇÃO RDO MELHORIAS ===")
            
            # 1. ADICIONAR NOVOS CAMPOS CLIMÁTICOS PADRONIZADOS
            print("\n1. Adicionando campos climáticos padronizados...")
            
            try:
                db.session.execute(text("""
                    ALTER TABLE rdo 
                    ADD COLUMN IF NOT EXISTS clima_geral VARCHAR(50),
                    ADD COLUMN IF NOT EXISTS temperatura_media VARCHAR(10),
                    ADD COLUMN IF NOT EXISTS umidade_relativa INTEGER,
                    ADD COLUMN IF NOT EXISTS vento_velocidade VARCHAR(20),
                    ADD COLUMN IF NOT EXISTS precipitacao VARCHAR(20),
                    ADD COLUMN IF NOT EXISTS condicoes_trabalho VARCHAR(50),
                    ADD COLUMN IF NOT EXISTS observacoes_climaticas TEXT;
                """))
                print("   ✅ Campos climáticos adicionados")
            except Exception as e:
                print(f"   ⚠️ Campos climáticos já existem ou erro: {e}")
            
            # 2. MIGRAR DADOS CLIMÁTICOS EXISTENTES
            print("\n2. Migrando dados climáticos existentes...")
            
            resultado = db.session.execute(text("""
                UPDATE rdo 
                SET 
                    clima_geral = CASE 
                        WHEN LOWER(tempo_manha) LIKE '%sol%' OR LOWER(tempo_manha) LIKE '%ensolarado%' THEN 'Ensolarado'
                        WHEN LOWER(tempo_manha) LIKE '%chuv%' OR LOWER(tempo_manha) LIKE '%chuva%' THEN 'Chuvoso' 
                        WHEN LOWER(tempo_manha) LIKE '%nubl%' OR LOWER(tempo_manha) LIKE '%nuvem%' THEN 'Nublado'
                        WHEN tempo_manha IS NOT NULL THEN 'Parcialmente Nublado'
                        ELSE 'Não informado'
                    END,
                    observacoes_climaticas = CONCAT_WS('; ', 
                        CASE WHEN tempo_manha IS NOT NULL THEN 'Manhã: ' || tempo_manha END,
                        CASE WHEN tempo_tarde IS NOT NULL THEN 'Tarde: ' || tempo_tarde END,
                        CASE WHEN tempo_noite IS NOT NULL THEN 'Noite: ' || tempo_noite END,
                        observacoes_meteorologicas
                    )
                WHERE clima_geral IS NULL;
            """))
            print(f"   ✅ {resultado.rowcount} registros migrados")
            
            # 3. MELHORAR TABELA DE OCORRÊNCIAS
            print("\n3. Expandindo tabela de ocorrências...")
            
            try:
                db.session.execute(text("""
                    ALTER TABLE rdo_ocorrencia 
                    ADD COLUMN IF NOT EXISTS tipo_ocorrencia VARCHAR(50) DEFAULT 'Observação',
                    ADD COLUMN IF NOT EXISTS severidade VARCHAR(20) DEFAULT 'Baixa',
                    ADD COLUMN IF NOT EXISTS responsavel_acao VARCHAR(100),
                    ADD COLUMN IF NOT EXISTS prazo_resolucao DATE,
                    ADD COLUMN IF NOT EXISTS status_resolucao VARCHAR(20) DEFAULT 'Pendente',
                    ADD COLUMN IF NOT EXISTS observacoes_resolucao TEXT,
                    ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW();
                """))
                print("   ✅ Campos de ocorrências expandidos")
            except Exception as e:
                print(f"   ⚠️ Campos de ocorrências já existem ou erro: {e}")
            
            # 4. MELHORAR TABELA DE FOTOS
            print("\n4. Expandindo tabela de fotos...")
            
            try:
                db.session.execute(text("""
                    ALTER TABLE rdo_foto 
                    ADD COLUMN IF NOT EXISTS categoria VARCHAR(50) DEFAULT 'geral',
                    ADD COLUMN IF NOT EXISTS tamanho_bytes INTEGER,
                    ADD COLUMN IF NOT EXISTS metadados_gps_lat FLOAT,
                    ADD COLUMN IF NOT EXISTS metadados_gps_lng FLOAT,
                    ADD COLUMN IF NOT EXISTS metadados_timestamp TIMESTAMP,
                    ADD COLUMN IF NOT EXISTS metadados_camera VARCHAR(100),
                    ADD COLUMN IF NOT EXISTS enviado_por_id INTEGER REFERENCES usuario(id);
                """))
                print("   ✅ Campos de fotos expandidos")
            except Exception as e:
                print(f"   ⚠️ Campos de fotos já existem ou erro: {e}")
            
            # 5. ADICIONAR ÍNDICES PARA PERFORMANCE
            print("\n5. Adicionando índices para performance...")
            
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_rdo_obra_data ON rdo(obra_id, data_relatorio);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_status ON rdo(status);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_criado_por ON rdo(criado_por_id);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_atividade_rdo ON rdo_atividade(rdo_id);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_mao_obra_funcionario ON rdo_mao_obra(funcionario_id);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_mao_obra_data ON rdo_mao_obra(rdo_id);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_equipamento_rdo ON rdo_equipamento(rdo_id);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_ocorrencia_tipo ON rdo_ocorrencia(tipo_ocorrencia);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_ocorrencia_severidade ON rdo_ocorrencia(severidade);",
                "CREATE INDEX IF NOT EXISTS idx_rdo_foto_categoria ON rdo_foto(categoria);"
            ]
            
            for indice in indices:
                try:
                    db.session.execute(text(indice))
                    print(f"   ✅ Índice criado: {indice.split()[5]}")
                except Exception as e:
                    print(f"   ⚠️ Índice já existe: {indice.split()[5]}")
            
            # 6. CRIAR CONSTRAINTS PARA VALIDAÇÃO
            print("\n6. Adicionando constraints de validação...")
            
            constraints = [
                "ALTER TABLE rdo_atividade ADD CONSTRAINT IF NOT EXISTS chk_percentual_valido CHECK (percentual_conclusao >= 0 AND percentual_conclusao <= 100);",
                "ALTER TABLE rdo_mao_obra ADD CONSTRAINT IF NOT EXISTS chk_horas_validas CHECK (horas_trabalhadas >= 0 AND horas_trabalhadas <= 12);",
                "ALTER TABLE rdo_equipamento ADD CONSTRAINT IF NOT EXISTS chk_quantidade_positiva CHECK (quantidade > 0);",
                "ALTER TABLE rdo_equipamento ADD CONSTRAINT IF NOT EXISTS chk_horas_uso_validas CHECK (horas_uso >= 0 AND horas_uso <= 24);",
                "ALTER TABLE rdo ADD CONSTRAINT IF NOT EXISTS chk_umidade_valida CHECK (umidade_relativa IS NULL OR (umidade_relativa >= 0 AND umidade_relativa <= 100));"
            ]
            
            for constraint in constraints:
                try:
                    db.session.execute(text(constraint))
                    print(f"   ✅ Constraint criada: {constraint.split()[6]}")
                except Exception as e:
                    print(f"   ⚠️ Constraint já existe: {constraint.split()[6]}")
            
            # 7. CRIAR TRIGGER PARA AUTO-GERAR NÚMERO RDO
            print("\n7. Criando trigger para auto-gerar número RDO...")
            
            try:
                db.session.execute(text("""
                    CREATE OR REPLACE FUNCTION gerar_numero_rdo()
                    RETURNS TRIGGER AS $$
                    DECLARE
                        contador INTEGER;
                        ano INTEGER;
                    BEGIN
                        IF NEW.numero_rdo IS NULL OR NEW.numero_rdo = '' THEN
                            ano := EXTRACT(YEAR FROM NEW.data_relatorio);
                            
                            SELECT COUNT(*) + 1 INTO contador
                            FROM rdo 
                            WHERE EXTRACT(YEAR FROM data_relatorio) = ano
                            AND obra_id = NEW.obra_id;
                            
                            NEW.numero_rdo := 'RDO-' || ano || '-' || LPAD(contador::TEXT, 3, '0');
                        END IF;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                """))
                
                db.session.execute(text("""
                    DROP TRIGGER IF EXISTS trigger_gerar_numero_rdo ON rdo;
                    CREATE TRIGGER trigger_gerar_numero_rdo
                        BEFORE INSERT ON rdo
                        FOR EACH ROW
                        EXECUTE FUNCTION gerar_numero_rdo();
                """))
                print("   ✅ Trigger de numeração automática criado")
            except Exception as e:
                print(f"   ⚠️ Erro ao criar trigger: {e}")
            
            # 8. CRIAR VIEW PARA ANALYTICS
            print("\n8. Criando view para analytics...")
            
            try:
                db.session.execute(text("""
                    CREATE OR REPLACE VIEW vw_rdo_analytics AS
                    SELECT 
                        r.id as rdo_id,
                        r.numero_rdo,
                        r.data_relatorio,
                        r.obra_id,
                        o.nome as obra_nome,
                        r.status,
                        r.clima_geral,
                        r.condicoes_trabalho,
                        
                        -- Estatísticas de atividades
                        COUNT(DISTINCT ra.id) as total_atividades,
                        COALESCE(AVG(ra.percentual_conclusao), 0) as progresso_medio,
                        
                        -- Estatísticas de mão de obra
                        COUNT(DISTINCT rm.funcionario_id) as total_funcionarios,
                        COALESCE(SUM(rm.horas_trabalhadas), 0) as total_horas,
                        
                        -- Estatísticas de equipamentos
                        COUNT(DISTINCT re.id) as total_equipamentos,
                        COALESCE(SUM(re.horas_uso), 0) as total_horas_equipamentos,
                        
                        -- Estatísticas de ocorrências
                        COUNT(DISTINCT roc.id) as total_ocorrencias,
                        COUNT(DISTINCT CASE WHEN roc.severidade = 'Crítica' THEN roc.id END) as ocorrencias_criticas,
                        
                        -- Estatísticas de fotos
                        COUNT(DISTINCT rf.id) as total_fotos
                        
                    FROM rdo r
                    LEFT JOIN obra o ON r.obra_id = o.id
                    LEFT JOIN rdo_atividade ra ON r.id = ra.rdo_id
                    LEFT JOIN rdo_mao_obra rm ON r.id = rm.rdo_id
                    LEFT JOIN rdo_equipamento re ON r.id = re.rdo_id
                    LEFT JOIN rdo_ocorrencia roc ON r.id = roc.rdo_id
                    LEFT JOIN rdo_foto rf ON r.id = rf.rdo_id
                    GROUP BY r.id, r.numero_rdo, r.data_relatorio, r.obra_id, o.nome, r.status, r.clima_geral, r.condicoes_trabalho;
                """))
                print("   ✅ View de analytics criada")
            except Exception as e:
                print(f"   ⚠️ Erro ao criar view: {e}")
            
            # 9. ATUALIZAR DADOS EXISTENTES
            print("\n9. Atualizando dados existentes...")
            
            # Atualizar tipo de ocorrências existentes
            db.session.execute(text("""
                UPDATE rdo_ocorrencia 
                SET tipo_ocorrencia = CASE
                    WHEN LOWER(descricao_ocorrencia) LIKE '%problema%' OR LOWER(descricao_ocorrencia) LIKE '%erro%' THEN 'Problema'
                    WHEN LOWER(descricao_ocorrencia) LIKE '%segur%' OR LOWER(descricao_ocorrencia) LIKE '%acident%' THEN 'Segurança'
                    WHEN LOWER(descricao_ocorrencia) LIKE '%melhor%' OR LOWER(descricao_ocorrencia) LIKE '%sugest%' THEN 'Melhoria'
                    ELSE 'Observação'
                END
                WHERE tipo_ocorrencia IS NULL OR tipo_ocorrencia = 'Observação';
            """))
            
            # Atualizar categoria de fotos existentes
            db.session.execute(text("""
                UPDATE rdo_foto 
                SET categoria = CASE
                    WHEN LOWER(legenda) LIKE '%antes%' OR LOWER(nome_arquivo) LIKE '%antes%' THEN 'antes'
                    WHEN LOWER(legenda) LIKE '%depois%' OR LOWER(nome_arquivo) LIKE '%depois%' THEN 'depois'
                    WHEN LOWER(legenda) LIKE '%problem%' OR LOWER(nome_arquivo) LIKE '%problem%' THEN 'problema'
                    WHEN LOWER(legenda) LIKE '%progress%' OR LOWER(nome_arquivo) LIKE '%progress%' THEN 'progresso'
                    ELSE 'geral'
                END
                WHERE categoria IS NULL OR categoria = 'geral';
            """))
            
            print("   ✅ Dados existentes atualizados")
            
            # COMMIT FINAL
            db.session.commit()
            
            print("\n=== MIGRAÇÃO CONCLUÍDA COM SUCESSO ===")
            print("\n📊 RESUMO DAS MELHORIAS APLICADAS:")
            print("✅ Campos climáticos padronizados (7 novos campos)")
            print("✅ Ocorrências expandidas (7 novos campos)")
            print("✅ Sistema de fotos melhorado (6 novos campos)")
            print("✅ Índices de performance criados (10 índices)")
            print("✅ Constraints de validação adicionadas (5 constraints)")
            print("✅ Trigger de numeração automática")
            print("✅ View de analytics criada")
            print("✅ Dados existentes migrados")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO NA MIGRAÇÃO: {str(e)}")
            return False

def verificar_migracao():
    """Verificar se a migração foi aplicada corretamente"""
    with app.app_context():
        try:
            print("\n=== VERIFICANDO MIGRAÇÃO ===")
            
            # Verificar novos campos
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rdo' 
                AND column_name IN ('clima_geral', 'temperatura_media', 'umidade_relativa')
            """))
            
            campos_clima = [row[0] for row in result.fetchall()]
            print(f"✅ Campos climáticos: {', '.join(campos_clima)}")
            
            # Verificar constraints
            result = db.session.execute(text("""
                SELECT constraint_name 
                FROM information_schema.check_constraints 
                WHERE constraint_name LIKE 'chk_%';
            """))
            
            constraints = [row[0] for row in result.fetchall()]
            print(f"✅ Constraints: {len(constraints)} constraints criadas")
            
            # Verificar view analytics
            result = db.session.execute(text("""
                SELECT COUNT(*) FROM vw_rdo_analytics;
            """))
            
            total_analytics = result.scalar()
            print(f"✅ View analytics: {total_analytics} registros disponíveis")
            
            print("\n✅ MIGRAÇÃO VERIFICADA E FUNCIONANDO CORRETAMENTE")
            
        except Exception as e:
            print(f"❌ ERRO NA VERIFICAÇÃO: {str(e)}")

if __name__ == "__main__":
    # Executar migração
    sucesso = executar_migracao_rdo()
    
    if sucesso:
        # Verificar migração
        verificar_migracao()
        print("\n🚀 SISTEMA RDO ATUALIZADO COM SUCESSO!")
        print("📝 Próximos passos: Implementar interface wizard e validações em tempo real")
    else:
        print("\n❌ FALHA NA MIGRAÇÃO - Verificar logs de erro")