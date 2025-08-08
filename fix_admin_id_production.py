#!/usr/bin/env python3
"""
Script para corrigir problema de admin_id em produção
Baseado na análise detalhada do erro UndefinedColumn
"""

from app import app, db
from models import OutroCusto, Funcionario
from sqlalchemy import text, inspect
import logging
import os

def setup_logging():
    """Configurar logging detalhado para debug"""
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    print("🔧 Logging do SQLAlchemy ativado")

def verify_database_connection():
    """Verificar conexão com banco de dados"""
    try:
        with app.app_context():
            result = db.session.execute(text('SELECT version()'))
            version = result.scalar()
            print(f"✅ Conexão com PostgreSQL: {version}")
            return True
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return False

def check_column_exists():
    """Verificar se colunas admin_id e kpi_associado existem no banco"""
    with app.app_context():
        try:
            # Verificar admin_id
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'admin_id'
            """))
            
            admin_column = result.fetchone()
            admin_exists = bool(admin_column)
            if admin_column:
                print(f"✅ Coluna admin_id existe: {admin_column[1]} (nullable: {admin_column[2]})")
            else:
                print("❌ Coluna admin_id NÃO EXISTE")
                
            # Verificar kpi_associado
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'kpi_associado'
            """))
            
            kpi_column = result.fetchone()
            kpi_exists = bool(kpi_column)
            if kpi_column:
                print(f"✅ Coluna kpi_associado existe: {kpi_column[1]} (nullable: {kpi_column[2]})")
            else:
                print("❌ Coluna kpi_associado NÃO EXISTE")
                
            return admin_exists, kpi_exists
                
        except Exception as e:
            print(f"❌ Erro ao verificar colunas: {e}")
            return False, False

def add_missing_columns(admin_exists, kpi_exists):
    """Adicionar colunas que faltam"""
    with app.app_context():
        try:
            success = True
            
            # Adicionar admin_id se não existir
            if not admin_exists:
                print("🔧 Adicionando coluna admin_id...")
                
                db.session.execute(text('ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER'))
                
                # Adicionar foreign key (opcional, pode falhar se tabela usuario não existe)
                try:
                    db.session.execute(text('''
                        ALTER TABLE outro_custo 
                        ADD CONSTRAINT fk_outro_custo_admin 
                        FOREIGN KEY (admin_id) REFERENCES usuario(id)
                    '''))
                    print("✅ Foreign key constraint admin_id adicionada")
                except Exception as fk_error:
                    print(f"⚠️  Foreign key admin_id não pôde ser adicionada: {fk_error}")
                
                # Atualizar registros existentes
                print("🔧 Atualizando registros admin_id...")
                updated = db.session.execute(text('''
                    UPDATE outro_custo 
                    SET admin_id = (
                        SELECT admin_id 
                        FROM funcionario 
                        WHERE funcionario.id = outro_custo.funcionario_id
                        LIMIT 1
                    )
                    WHERE admin_id IS NULL
                ''')).rowcount
                
                print(f"✅ Coluna admin_id adicionada e {updated} registros atualizados")
            else:
                print("✅ Coluna admin_id já existe")
            
            # Adicionar kpi_associado se não existir
            if not kpi_exists:
                print("🔧 Adicionando coluna kpi_associado...")
                
                db.session.execute(text("ALTER TABLE outro_custo ADD COLUMN kpi_associado VARCHAR(30) DEFAULT 'outros_custos'"))
                
                # Atualizar registros existentes
                print("🔧 Atualizando registros kpi_associado...")
                updated = db.session.execute(text('''
                    UPDATE outro_custo 
                    SET kpi_associado = 'outros_custos'
                    WHERE kpi_associado IS NULL
                ''')).rowcount
                
                print(f"✅ Coluna kpi_associado adicionada e {updated} registros atualizados")
            else:
                print("✅ Coluna kpi_associado já existe")
            
            db.session.commit()
            return success
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao adicionar colunas: {e}")
            return False

def clear_sqlalchemy_cache():
    """Limpar cache de metadados do SQLAlchemy"""
    with app.app_context():
        try:
            print("🔧 Limpando cache de metadados do SQLAlchemy...")
            
            # Limpar metadados
            db.metadata.clear()
            
            # Forçar reflexão
            db.metadata.reflect(bind=db.engine)
            
            print("✅ Cache de metadados limpo e refletido")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao limpar cache: {e}")
            return False

def test_model_functionality():
    """Testar funcionalidade do modelo OutroCusto"""
    with app.app_context():
        try:
            print("🔍 Testando funcionalidade do modelo...")
            
            # Teste básico de contagem
            total = OutroCusto.query.count()
            print(f"✅ Total de registros: {total}")
            
            # Teste com filtro admin_id
            with_admin = OutroCusto.query.filter(OutroCusto.admin_id.isnot(None)).count()
            print(f"✅ Registros com admin_id: {with_admin}")
            
            # Teste com filtro kpi_associado
            with_kpi = OutroCusto.query.filter(OutroCusto.kpi_associado.isnot(None)).count()
            print(f"✅ Registros com kpi_associado: {with_kpi}")
            
            # Teste de join com funcionário
            joined = OutroCusto.query.join(Funcionario).count()
            print(f"✅ Registros com join funcionário: {joined}")
            
            # Teste específico da query problemática
            result = OutroCusto.query.first()
            if result:
                print(f"✅ Query específica funcionou: ID {result.id}, Admin ID {result.admin_id}, KPI {result.kpi_associado}")
            else:
                print("⚠️  Nenhum registro encontrado")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no teste do modelo: {e}")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Detalhes: {str(e)}")
            return False

def main():
    """Função principal de correção"""
    print("🚀 INICIANDO CORREÇÃO DE COLUNAS EM PRODUÇÃO")
    print("=" * 60)
    
    # 1. Configurar logging
    setup_logging()
    
    # 2. Verificar conexão
    if not verify_database_connection():
        print("❌ FALHA: Não foi possível conectar ao banco de dados")
        return False
    
    # 3. Verificar se colunas existem
    admin_exists, kpi_exists = check_column_exists()
    
    # 4. Adicionar colunas se necessário
    if not admin_exists or not kpi_exists:
        if not add_missing_columns(admin_exists, kpi_exists):
            print("❌ FALHA: Não foi possível adicionar colunas faltantes")
            return False
    else:
        print("✅ Todas as colunas já existem")
    
    # 5. Limpar cache do SQLAlchemy
    if not clear_sqlalchemy_cache():
        print("⚠️  AVISO: Não foi possível limpar cache, mas pode não ser crítico")
    
    # 6. Testar funcionalidade
    if not test_model_functionality():
        print("❌ FALHA: Modelo ainda não está funcionando")
        return False
    
    print("=" * 60)
    print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
    print("   - Colunas admin_id e kpi_associado verificadas/criadas")
    print("   - Dados atualizados")
    print("   - Cache do SQLAlchemy limpo")
    print("   - Funcionalidade testada")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)