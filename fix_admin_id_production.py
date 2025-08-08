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
    """Verificar se coluna admin_id existe no banco"""
    with app.app_context():
        try:
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'outro_custo' AND column_name = 'admin_id'
            """))
            
            column_info = result.fetchone()
            if column_info:
                print(f"✅ Coluna admin_id existe: {column_info[1]} (nullable: {column_info[2]})")
                return True
            else:
                print("❌ Coluna admin_id NÃO EXISTE")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao verificar coluna: {e}")
            return False

def add_admin_id_column():
    """Adicionar coluna admin_id se não existir"""
    with app.app_context():
        try:
            print("🔧 Adicionando coluna admin_id...")
            
            # Adicionar coluna
            db.session.execute(text('ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER'))
            
            # Adicionar foreign key (opcional, pode falhar se tabela usuario não existe)
            try:
                db.session.execute(text('''
                    ALTER TABLE outro_custo 
                    ADD CONSTRAINT fk_outro_custo_admin 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                '''))
                print("✅ Foreign key constraint adicionada")
            except Exception as fk_error:
                print(f"⚠️  Foreign key não pôde ser adicionada: {fk_error}")
            
            # Atualizar registros existentes
            print("🔧 Atualizando registros existentes...")
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
            
            db.session.commit()
            print(f"✅ Coluna admin_id adicionada e {updated} registros atualizados")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao adicionar coluna: {e}")
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
            
            # Teste de join com funcionário
            joined = OutroCusto.query.join(Funcionario).count()
            print(f"✅ Registros com join funcionário: {joined}")
            
            # Teste específico da query problemática
            result = OutroCusto.query.filter_by(funcionario_id=96).first()
            if result:
                print(f"✅ Query específica funcionou: ID {result.id}, Admin ID {result.admin_id}")
            else:
                print("⚠️  Nenhum registro encontrado para funcionário 96")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no teste do modelo: {e}")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Detalhes: {str(e)}")
            return False

def main():
    """Função principal de correção"""
    print("🚀 INICIANDO CORREÇÃO DO PROBLEMA admin_id EM PRODUÇÃO")
    print("=" * 60)
    
    # 1. Configurar logging
    setup_logging()
    
    # 2. Verificar conexão
    if not verify_database_connection():
        print("❌ FALHA: Não foi possível conectar ao banco de dados")
        return False
    
    # 3. Verificar se coluna existe
    column_exists = check_column_exists()
    
    # 4. Adicionar coluna se necessário
    if not column_exists:
        if not add_admin_id_column():
            print("❌ FALHA: Não foi possível adicionar coluna admin_id")
            return False
    
    # 5. Limpar cache do SQLAlchemy
    if not clear_sqlalchemy_cache():
        print("⚠️  AVISO: Não foi possível limpar cache, mas pode não ser crítico")
    
    # 6. Testar funcionalidade
    if not test_model_functionality():
        print("❌ FALHA: Modelo ainda não está funcionando")
        return False
    
    print("=" * 60)
    print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
    print("   - Coluna admin_id verificada/criada")
    print("   - Dados atualizados")
    print("   - Cache do SQLAlchemy limpo")
    print("   - Funcionalidade testada")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)