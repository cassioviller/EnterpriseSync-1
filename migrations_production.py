#!/usr/bin/env python3
"""
MIGRATIONS PRODUCTION - SIGE v10.0 Digital Mastery
Implementação Joris Kuypers - "Kaipa da primeira vez certo"
Sistema de migração automática para produção EasyPanel
"""

import os
import logging
from datetime import datetime
from sqlalchemy import text

# Configurar logging para observabilidade
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - PRODUCTION_MIGRATION - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ProductionMigration')

def executar_migracoes_producao():
    """
    Executa todas as migrações necessárias para produção
    Implementa princípios de Digital Mastery com observabilidade completa
    """
    logger.info("🚀 INICIANDO MIGRAÇÕES PRODUÇÃO - DIGITAL MASTERY")
    
    try:
        from app import app, db
        
        with app.app_context():
            logger.info("📊 Conectado ao banco de dados produção")
            
            # 1. Verificar e corrigir estrutura RDO
            _corrigir_estrutura_rdo(db)
            
            # 2. Verificar e corrigir servico_obra
            _corrigir_servico_obra(db)
            
            # 3. Aplicar correções específicas para RDO
            _aplicar_correcoes_rdo_sistema(db)
            
            # 4. Validar integridade do sistema
            _validar_integridade_sistema(db)
            
            logger.info("✅ MIGRAÇÕES PRODUÇÃO CONCLUÍDAS COM SUCESSO")
            
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO NAS MIGRAÇÕES: {e}")
        import traceback
        traceback.print_exc()
        raise

def _corrigir_estrutura_rdo(db):
    """Corrige estrutura das tabelas RDO"""
    logger.info("🔧 Corrigindo estrutura RDO...")
    
    try:
        # Verificar se tabela rdo_servico_subatividade existe
        result = db.session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'rdo_servico_subatividade'
        """))
        
        if not result.fetchone():
            logger.info("⚡ Criando tabela rdo_servico_subatividade...")
            db.session.execute(text("""
                CREATE TABLE rdo_servico_subatividade (
                    id SERIAL PRIMARY KEY,
                    rdo_id INTEGER REFERENCES rdo(id),
                    servico_id INTEGER,
                    nome_subatividade VARCHAR(255),
                    percentual_conclusao DECIMAL(5,2) DEFAULT 0.00,
                    descricao_subatividade TEXT,
                    observacoes_tecnicas TEXT,
                    admin_id INTEGER NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        # Verificar colunas necessárias na tabela rdo
        colunas_rdo = [
            ('admin_id', 'INTEGER'),
            ('local', 'VARCHAR(50)'),
            ('comentario_geral', 'TEXT')
        ]
        
        for coluna, tipo in colunas_rdo:
            result = db.session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rdo' AND column_name = '{coluna}'
            """))
            
            if not result.fetchone():
                logger.info(f"⚡ Adicionando coluna {coluna} na tabela rdo...")
                db.session.execute(text(f"ALTER TABLE rdo ADD COLUMN {coluna} {tipo}"))
        
        db.session.commit()
        logger.info("✅ Estrutura RDO corrigida")
        
    except Exception as e:
        logger.error(f"❌ Erro na correção estrutura RDO: {e}")
        db.session.rollback()
        raise

def _corrigir_servico_obra(db):
    """Corrige estrutura da tabela servico_obra"""
    logger.info("🔧 Corrigindo estrutura servico_obra...")
    
    try:
        # Verificar se tabela servico_obra existe
        result = db.session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'servico_obra'
        """))
        
        if not result.fetchone():
            logger.info("⚡ Criando tabela servico_obra...")
            db.session.execute(text("""
                CREATE TABLE servico_obra (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL,
                    servico_id INTEGER NOT NULL,
                    quantidade_planejada DECIMAL(10,4) DEFAULT 1.0000,
                    quantidade_executada DECIMAL(10,4) DEFAULT 0.0000,
                    observacoes TEXT,
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    admin_id INTEGER NOT NULL
                )
            """))
        else:
            # Verificar colunas necessárias
            colunas_necessarias = [
                ('quantidade_planejada', 'DECIMAL(10,4) DEFAULT 1.0000'),
                ('quantidade_executada', 'DECIMAL(10,4) DEFAULT 0.0000'),
                ('admin_id', 'INTEGER')
            ]
            
            for coluna, tipo in colunas_necessarias:
                result = db.session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'servico_obra' AND column_name = '{coluna}'
                """))
                
                if not result.fetchone():
                    logger.info(f"⚡ Adicionando coluna {coluna} na tabela servico_obra...")
                    db.session.execute(text(f"ALTER TABLE servico_obra ADD COLUMN {coluna} {tipo}"))
        
        # Atualizar registros NULL
        db.session.execute(text("""
            UPDATE servico_obra 
            SET quantidade_planejada = 1.0000 
            WHERE quantidade_planejada IS NULL
        """))
        
        db.session.execute(text("""
            UPDATE servico_obra 
            SET quantidade_executada = 0.0000 
            WHERE quantidade_executada IS NULL
        """))
        
        db.session.commit()
        logger.info("✅ Estrutura servico_obra corrigida")
        
    except Exception as e:
        logger.error(f"❌ Erro na correção servico_obra: {e}")
        db.session.rollback()
        raise

def _aplicar_correcoes_rdo_sistema(db):
    """Aplica correções específicas do sistema RDO"""
    logger.info("🔧 Aplicando correções específicas RDO...")
    
    try:
        # Corrigir admin_id em registros existentes se necessário
        result = db.session.execute(text("""
            UPDATE rdo 
            SET admin_id = 2 
            WHERE admin_id IS NULL AND id IN (
                SELECT DISTINCT r.id 
                FROM rdo r 
                WHERE r.admin_id IS NULL 
                LIMIT 100
            )
        """))
        
        if result.rowcount > 0:
            logger.info(f"✅ {result.rowcount} registros RDO corrigidos com admin_id=2")
        
        # Verificar se há subatividades órfãs e corrigir
        result = db.session.execute(text("""
            UPDATE rdo_servico_subatividade 
            SET admin_id = 2 
            WHERE admin_id IS NULL
        """))
        
        if result.rowcount > 0:
            logger.info(f"✅ {result.rowcount} subatividades corrigidas com admin_id=2")
        
        db.session.commit()
        logger.info("✅ Correções específicas RDO aplicadas")
        
    except Exception as e:
        logger.error(f"❌ Erro nas correções específicas RDO: {e}")
        db.session.rollback()
        raise

def _validar_integridade_sistema(db):
    """Valida integridade do sistema após migrações"""
    logger.info("🔍 Validando integridade do sistema...")
    
    try:
        # Contar registros principais
        rdos_count = db.session.execute(text("SELECT COUNT(*) FROM rdo")).scalar()
        subatividades_count = db.session.execute(text("SELECT COUNT(*) FROM rdo_servico_subatividade")).scalar()
        servicos_obra_count = db.session.execute(text("SELECT COUNT(*) FROM servico_obra")).scalar()
        
        logger.info(f"📊 ESTATÍSTICAS DO SISTEMA:")
        logger.info(f"   • RDOs: {rdos_count}")
        logger.info(f"   • Subatividades: {subatividades_count}")
        logger.info(f"   • Serviços/Obra: {servicos_obra_count}")
        
        # Verificar admin_ids
        admins_rdo = db.session.execute(text("""
            SELECT DISTINCT admin_id, COUNT(*) 
            FROM rdo 
            WHERE admin_id IS NOT NULL 
            GROUP BY admin_id
        """)).fetchall()
        
        logger.info(f"📊 ADMIN_IDS RDO: {dict(admins_rdo)}")
        
        logger.info("✅ Validação de integridade concluída")
        
    except Exception as e:
        logger.error(f"❌ Erro na validação de integridade: {e}")
        raise

if __name__ == "__main__":
    executar_migracoes_producao()