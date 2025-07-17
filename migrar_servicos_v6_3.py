#!/usr/bin/env python3
"""
Script de migração para atualizar tabela de serviços para SIGE v6.3
Adiciona novos campos para coleta de dados reais via RDO
"""

import sys
import os
from datetime import datetime

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate_servicos_table():
    """Migra a tabela de serviços para SIGE v6.3"""
    
    with app.app_context():
        print("🔄 Migrando tabela de serviços para SIGE v6.3...")
        
        # Executar comandos SQL diretamente
        try:
            # Adicionar novas colunas à tabela servico
            db.session.execute(text("""
                ALTER TABLE servico 
                ADD COLUMN IF NOT EXISTS categoria VARCHAR(50) DEFAULT 'geral',
                ADD COLUMN IF NOT EXISTS unidade_medida VARCHAR(10) DEFAULT 'un',
                ADD COLUMN IF NOT EXISTS complexidade INTEGER DEFAULT 3,
                ADD COLUMN IF NOT EXISTS requer_especializacao BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            """))
            
            # Remover coluna preco_unitario (não mais necessária)
            db.session.execute(text("""
                ALTER TABLE servico DROP COLUMN IF EXISTS preco_unitario;
            """))
            
            # Atualizar registros existentes com valores padrão
            db.session.execute(text("""
                UPDATE servico 
                SET categoria = 'geral',
                    unidade_medida = 'un',
                    complexidade = 3,
                    requer_especializacao = FALSE,
                    ativo = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE categoria IS NULL;
            """))
            
            # Criar tabela sub_atividade
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS sub_atividade (
                    id SERIAL PRIMARY KEY,
                    servico_id INTEGER NOT NULL REFERENCES servico(id) ON DELETE CASCADE,
                    nome VARCHAR(100) NOT NULL,
                    descricao TEXT,
                    ordem_execucao INTEGER NOT NULL,
                    ferramentas_necessarias TEXT,
                    materiais_principais TEXT,
                    requer_aprovacao BOOLEAN DEFAULT FALSE,
                    pode_executar_paralelo BOOLEAN DEFAULT TRUE,
                    qualificacao_minima VARCHAR(50),
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Criar tabela historico_produtividade_servico
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS historico_produtividade_servico (
                    id SERIAL PRIMARY KEY,
                    servico_id INTEGER NOT NULL REFERENCES servico(id) ON DELETE CASCADE,
                    sub_atividade_id INTEGER REFERENCES sub_atividade(id) ON DELETE SET NULL,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    funcionario_id INTEGER NOT NULL REFERENCES funcionario(id) ON DELETE CASCADE,
                    data_execucao DATE NOT NULL,
                    quantidade_executada NUMERIC(10, 4) NOT NULL,
                    tempo_execucao_horas NUMERIC(8, 2) NOT NULL,
                    custo_mao_obra_real NUMERIC(10, 2) NOT NULL,
                    produtividade_hora NUMERIC(8, 4) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Criar índices para performance
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_sub_atividade_servico_id ON sub_atividade(servico_id);
                CREATE INDEX IF NOT EXISTS idx_sub_atividade_ordem ON sub_atividade(ordem_execucao);
                CREATE INDEX IF NOT EXISTS idx_historico_servico_id ON historico_produtividade_servico(servico_id);
                CREATE INDEX IF NOT EXISTS idx_historico_obra_id ON historico_produtividade_servico(obra_id);
                CREATE INDEX IF NOT EXISTS idx_historico_funcionario_id ON historico_produtividade_servico(funcionario_id);
                CREATE INDEX IF NOT EXISTS idx_historico_data ON historico_produtividade_servico(data_execucao);
            """))
            
            db.session.commit()
            
            print("✅ Migração concluída com sucesso!")
            print("   • Adicionadas colunas: categoria, unidade_medida, complexidade, requer_especializacao, ativo, updated_at")
            print("   • Removida coluna: preco_unitario")
            print("   • Criada tabela: sub_atividade")
            print("   • Criada tabela: historico_produtividade_servico")
            print("   • Criados índices de performance")
            
            # Verificar estrutura final
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'servico'
                ORDER BY ordinal_position;
            """)).fetchall()
            
            print("\n📊 Estrutura final da tabela servico:")
            for row in result:
                print(f"   • {row[0]} ({row[1]}) - Nullable: {row[2]} - Default: {row[3] or 'N/A'}")
            
            # Verificar contagem de registros
            count_servicos = db.session.execute(text("SELECT COUNT(*) FROM servico")).fetchone()[0]
            count_sub_atividades = db.session.execute(text("SELECT COUNT(*) FROM sub_atividade")).fetchone()[0]
            count_historico = db.session.execute(text("SELECT COUNT(*) FROM historico_produtividade_servico")).fetchone()[0]
            
            print(f"\n📈 Estatísticas:")
            print(f"   • Serviços: {count_servicos}")
            print(f"   • Subatividades: {count_sub_atividades}")
            print(f"   • Histórico de produtividade: {count_historico}")
            
        except Exception as e:
            print(f"❌ Erro durante a migração: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_servicos_table()