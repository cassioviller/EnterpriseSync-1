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
    
    # Corrigir as 6 tabelas críticas
    results.append(("rdo_mao_obra", fix_rdo_mao_obra_auto(db.engine)))
    results.append(("funcao", fix_funcao_auto(db.engine)))
    results.append(("registro_alimentacao", fix_registro_alimentacao_auto(db.engine)))
    results.append(("horario_trabalho", fix_horario_trabalho_auto(db.engine)))
    results.append(("departamento", fix_departamento_auto(db.engine)))
    results.append(("custo_obra", fix_custo_obra_auto(db.engine)))
    
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
