"""
Correção automática de rdo_mao_obra.admin_id
Executa automaticamente no startup da aplicação
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

def fix_rdo_mao_obra_auto(db_engine):
    """
    Adiciona admin_id em rdo_mao_obra se não existir
    Executa automaticamente sem interação do usuário
    """
    try:
        with db_engine.connect() as connection:
            # Verificar se coluna admin_id existe
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_mao_obra' 
                  AND column_name = 'admin_id'
            """))
            
            column_exists = result.scalar() > 0
            
            if column_exists:
                logger.info("✅ rdo_mao_obra.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  rdo_mao_obra.admin_id NÃO EXISTE - corrigindo automaticamente...")
            
            # Executar correção SQL
            connection.execute(text("""
                BEGIN;
                
                -- 1. Adicionar coluna
                ALTER TABLE rdo_mao_obra ADD COLUMN admin_id INTEGER;
                
                -- 2. Backfill via obra
                UPDATE rdo_mao_obra rm
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE rm.rdo_id = r.id
                  AND rm.admin_id IS NULL
                  AND o.admin_id IS NOT NULL;
                
                -- 3. Backfill via funcionario (fallback)
                UPDATE rdo_mao_obra rm
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE rm.funcionario_id = f.id
                  AND rm.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- 4. Aplicar NOT NULL (só se não houver NULLs)
                DO $$
                DECLARE
                    count_nulls INTEGER;
                BEGIN
                    SELECT COUNT(*) INTO count_nulls
                    FROM rdo_mao_obra
                    WHERE admin_id IS NULL;
                    
                    IF count_nulls = 0 THEN
                        ALTER TABLE rdo_mao_obra ALTER COLUMN admin_id SET NOT NULL;
                    END IF;
                END $$;
                
                -- 5. Adicionar foreign key
                ALTER TABLE rdo_mao_obra
                ADD CONSTRAINT fk_rdo_mao_obra_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                -- 6. Criar índice
                CREATE INDEX IF NOT EXISTS idx_rdo_mao_obra_admin_id 
                ON rdo_mao_obra(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            
            logger.info("✅ rdo_mao_obra.admin_id adicionado com sucesso (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir rdo_mao_obra.admin_id: {e}")
        try:
            connection.rollback()
        except:
            pass
        return False

def fix_funcao_auto(db_engine):
    """Adiciona admin_id em funcao se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'funcao' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ funcao.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  funcao.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE funcao ADD COLUMN admin_id INTEGER;
                
                UPDATE funcao fu
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.funcao_id = fu.id
                  AND fu.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- Usar admin_id mais comum para NULLs restantes
                UPDATE funcao
                SET admin_id = (
                    SELECT admin_id 
                    FROM funcionario 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                )
                WHERE admin_id IS NULL;
                
                ALTER TABLE funcao 
                ADD CONSTRAINT fk_funcao_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_funcao_admin_id ON funcao(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ funcao.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir funcao: {e}")
        return False

def fix_registro_alimentacao_auto(db_engine):
    """Adiciona admin_id em registro_alimentacao se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'registro_alimentacao' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ registro_alimentacao.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  registro_alimentacao.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE registro_alimentacao ADD COLUMN admin_id INTEGER;
                
                UPDATE registro_alimentacao ra
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE ra.funcionario_id = f.id
                  AND ra.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                DO $$
                DECLARE
                    count_nulls INTEGER;
                BEGIN
                    SELECT COUNT(*) INTO count_nulls
                    FROM registro_alimentacao
                    WHERE admin_id IS NULL;
                    
                    IF count_nulls = 0 THEN
                        ALTER TABLE registro_alimentacao ALTER COLUMN admin_id SET NOT NULL;
                    END IF;
                END $$;
                
                ALTER TABLE registro_alimentacao
                ADD CONSTRAINT fk_registro_alimentacao_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_registro_alimentacao_admin_id 
                ON registro_alimentacao(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ registro_alimentacao.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir registro_alimentacao: {e}")
        return False

def fix_horario_trabalho_auto(db_engine):
    """Adiciona admin_id em horario_trabalho se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'horario_trabalho' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ horario_trabalho.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  horario_trabalho.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE horario_trabalho ADD COLUMN admin_id INTEGER;
                
                -- Backfill usando funcionario.horario_trabalho_id
                UPDATE horario_trabalho ht
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.horario_trabalho_id = ht.id
                  AND ht.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- Usar admin_id mais comum para NULLs restantes
                UPDATE horario_trabalho
                SET admin_id = (
                    SELECT admin_id 
                    FROM funcionario 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                )
                WHERE admin_id IS NULL;
                
                ALTER TABLE horario_trabalho 
                ADD CONSTRAINT fk_horario_trabalho_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_horario_trabalho_admin_id 
                ON horario_trabalho(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ horario_trabalho.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir horario_trabalho: {e}")
        return False

def fix_departamento_auto(db_engine):
    """Adiciona admin_id em departamento se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'departamento' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ departamento.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  departamento.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE departamento ADD COLUMN admin_id INTEGER;
                
                -- Backfill usando funcionario.departamento_id
                UPDATE departamento d
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.departamento_id = d.id
                  AND d.admin_id IS NULL
                  AND f.admin_id IS NOT NULL;
                
                -- Usar admin_id mais comum para NULLs restantes
                UPDATE departamento
                SET admin_id = (
                    SELECT admin_id 
                    FROM funcionario 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                )
                WHERE admin_id IS NULL;
                
                ALTER TABLE departamento 
                ADD CONSTRAINT fk_departamento_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_departamento_admin_id 
                ON departamento(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ departamento.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir departamento: {e}")
        return False

def fix_custo_obra_auto(db_engine):
    """Adiciona admin_id em custo_obra se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'custo_obra' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ custo_obra.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  custo_obra.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE custo_obra ADD COLUMN admin_id INTEGER;
                
                -- Backfill usando obra.admin_id
                UPDATE custo_obra co
                SET admin_id = o.admin_id
                FROM obra o
                WHERE co.obra_id = o.id
                  AND co.admin_id IS NULL
                  AND o.admin_id IS NOT NULL;
                
                -- Usar admin_id mais comum para NULLs restantes
                UPDATE custo_obra
                SET admin_id = (
                    SELECT admin_id 
                    FROM obra 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                )
                WHERE admin_id IS NULL;
                
                ALTER TABLE custo_obra 
                ADD CONSTRAINT fk_custo_obra_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_custo_obra_admin_id 
                ON custo_obra(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ custo_obra.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir custo_obra: {e}")
        return False

def fix_rdo_equipamento_auto(db_engine):
    """Adiciona admin_id em rdo_equipamento se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_equipamento' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ rdo_equipamento.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  rdo_equipamento.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE rdo_equipamento ADD COLUMN admin_id INTEGER;
                
                -- Backfill via RDO -> Obra
                UPDATE rdo_equipamento re
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE re.rdo_id = r.id
                  AND re.admin_id IS NULL;
                
                ALTER TABLE rdo_equipamento ALTER COLUMN admin_id SET NOT NULL;
                
                ALTER TABLE rdo_equipamento
                ADD CONSTRAINT fk_rdo_equipamento_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_rdo_equipamento_admin_id 
                ON rdo_equipamento(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ rdo_equipamento.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir rdo_equipamento: {e}")
        return False

def fix_rdo_ocorrencia_auto(db_engine):
    """Adiciona admin_id em rdo_ocorrencia se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_ocorrencia' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ rdo_ocorrencia.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  rdo_ocorrencia.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE rdo_ocorrencia ADD COLUMN admin_id INTEGER;
                
                -- Backfill via RDO -> Obra
                UPDATE rdo_ocorrencia ro
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE ro.rdo_id = r.id
                  AND ro.admin_id IS NULL;
                
                ALTER TABLE rdo_ocorrencia ALTER COLUMN admin_id SET NOT NULL;
                
                ALTER TABLE rdo_ocorrencia
                ADD CONSTRAINT fk_rdo_ocorrencia_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_rdo_ocorrencia_admin_id 
                ON rdo_ocorrencia(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ rdo_ocorrencia.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir rdo_ocorrencia: {e}")
        return False

def fix_rdo_servico_subatividade_auto(db_engine):
    """Adiciona admin_id em rdo_servico_subatividade se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_servico_subatividade' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ rdo_servico_subatividade.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  rdo_servico_subatividade.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE rdo_servico_subatividade ADD COLUMN admin_id INTEGER;
                
                -- Backfill via RDO -> Obra
                UPDATE rdo_servico_subatividade rss
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE rss.rdo_id = r.id
                  AND rss.admin_id IS NULL;
                
                ALTER TABLE rdo_servico_subatividade ALTER COLUMN admin_id SET NOT NULL;
                
                ALTER TABLE rdo_servico_subatividade
                ADD CONSTRAINT fk_rdo_servico_subatividade_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_rdo_servico_subatividade_admin_id 
                ON rdo_servico_subatividade(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ rdo_servico_subatividade.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir rdo_servico_subatividade: {e}")
        return False

def fix_rdo_foto_auto(db_engine):
    """Adiciona admin_id em rdo_foto se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_foto' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ rdo_foto.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  rdo_foto.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE rdo_foto ADD COLUMN admin_id INTEGER;
                
                -- Backfill via RDO -> Obra
                UPDATE rdo_foto rf
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE rf.rdo_id = r.id
                  AND rf.admin_id IS NULL;
                
                ALTER TABLE rdo_foto ALTER COLUMN admin_id SET NOT NULL;
                
                ALTER TABLE rdo_foto
                ADD CONSTRAINT fk_rdo_foto_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_rdo_foto_admin_id 
                ON rdo_foto(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ rdo_foto.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir rdo_foto: {e}")
        return False

def fix_allocation_employee_auto(db_engine):
    """Adiciona admin_id em allocation_employee se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'allocation_employee' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ allocation_employee.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  allocation_employee.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE allocation_employee ADD COLUMN admin_id INTEGER;
                
                -- Backfill via allocation
                UPDATE allocation_employee ae
                SET admin_id = a.admin_id
                FROM allocation a
                WHERE ae.allocation_id = a.id
                  AND ae.admin_id IS NULL;
                
                ALTER TABLE allocation_employee ALTER COLUMN admin_id SET NOT NULL;
                
                ALTER TABLE allocation_employee
                ADD CONSTRAINT fk_allocation_employee_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_allocation_employee_admin_id 
                ON allocation_employee(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ allocation_employee.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir allocation_employee: {e}")
        return False

def fix_notificacao_cliente_auto(db_engine):
    """Adiciona admin_id em notificacao_cliente se não existir"""
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'notificacao_cliente' 
                  AND column_name = 'admin_id'
            """))
            
            if result.scalar() > 0:
                logger.info("✅ notificacao_cliente.admin_id já existe - skip")
                return True
            
            logger.warning("⚠️  notificacao_cliente.admin_id NÃO EXISTE - corrigindo...")
            
            connection.execute(text("""
                BEGIN;
                
                ALTER TABLE notificacao_cliente ADD COLUMN admin_id INTEGER;
                
                -- Backfill via obra
                UPDATE notificacao_cliente nc
                SET admin_id = o.admin_id
                FROM obra o
                WHERE nc.obra_id = o.id
                  AND nc.admin_id IS NULL;
                
                ALTER TABLE notificacao_cliente ALTER COLUMN admin_id SET NOT NULL;
                
                ALTER TABLE notificacao_cliente
                ADD CONSTRAINT fk_notificacao_cliente_admin_id
                FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
                
                CREATE INDEX IF NOT EXISTS idx_notificacao_cliente_admin_id 
                ON notificacao_cliente(admin_id);
                
                COMMIT;
            """))
            
            connection.commit()
            logger.info("✅ notificacao_cliente.admin_id adicionado (automático)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir notificacao_cliente: {e}")
        return False

def auto_fix_migration_48():
    """
    Correção automática da Migration 48
    Chame esta função no startup da aplicação
    """
    from app import db
    
    logger.info("=" * 80)
    logger.info("🔧 AUTO-FIX: Verificando e corrigindo Migration 48...")
    logger.info("=" * 80)
    
    results = []
    
    # Corrigir as 12 tabelas críticas (6 originais + 4 RDO + 1 equipe + 1 portal)
    results.append(("rdo_mao_obra", fix_rdo_mao_obra_auto(db.engine)))
    results.append(("funcao", fix_funcao_auto(db.engine)))
    results.append(("registro_alimentacao", fix_registro_alimentacao_auto(db.engine)))
    results.append(("horario_trabalho", fix_horario_trabalho_auto(db.engine)))
    results.append(("departamento", fix_departamento_auto(db.engine)))
    results.append(("custo_obra", fix_custo_obra_auto(db.engine)))
    results.append(("rdo_equipamento", fix_rdo_equipamento_auto(db.engine)))
    results.append(("rdo_ocorrencia", fix_rdo_ocorrencia_auto(db.engine)))
    results.append(("rdo_servico_subatividade", fix_rdo_servico_subatividade_auto(db.engine)))
    results.append(("rdo_foto", fix_rdo_foto_auto(db.engine)))
    results.append(("allocation_employee", fix_allocation_employee_auto(db.engine)))
    results.append(("notificacao_cliente", fix_notificacao_cliente_auto(db.engine)))
    
    # Resumo
    success_count = sum(1 for _, success in results if success)
    total = len(results)
    
    logger.info("=" * 80)
    logger.info(f"📊 AUTO-FIX CONCLUÍDO: {success_count}/{total} tabelas OK")
    logger.info("=" * 80)
    
    if success_count == total:
        logger.info("✅ Todas as tabelas corrigidas com sucesso")
    else:
        logger.warning("⚠️  Algumas tabelas não foram corrigidas - verificar logs")
    
    return success_count == total
