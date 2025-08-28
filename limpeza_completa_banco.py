"""
Script para limpeza completa do banco de dados
Mantém apenas usuários administradores e super administradores
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from models import *
import os

def limpeza_completa():
    """Limpar todo o banco exceto administradores"""
    
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🗑️ LIMPEZA COMPLETA DO BANCO DE DADOS")
            print("Mantendo apenas administradores...")
            
            # Desabilitar constraints temporariamente
            db.session.execute(text("SET session_replication_role = replica;"))
            
            # Lista das tabelas para limpar completamente (exceto usuario)
            tabelas_completa_limpeza = [
                'rdo_servico_subatividade',
                'rdo_mao_obra',
                'rdo',
                'registro_ponto',
                'outro_custo',
                'registro_alimentacao',
                'horarios_padrao',
                'uso_veiculo',
                'funcionario',
                'proposta_itens',
                'proposta_templates',
                'propostas_comerciais',
                'custo_obra',
                'servico_obra',
                'obra',
                'subatividade_mestre',
                'servico',
                'empresas',
                'configuracoes_empresa'
            ]
            
            print("\n📊 Estatísticas antes da limpeza:")
            for tabela in tabelas_completa_limpeza:
                try:
                    result = db.session.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
                    print(f"   {tabela}: {result} registros")
                except Exception as e:
                    print(f"   {tabela}: Erro - {e}")
            
            # Contar usuários antes
            total_usuarios = db.session.execute(text("SELECT COUNT(*) FROM usuario")).scalar()
            admins = db.session.execute(text("SELECT COUNT(*) FROM usuario WHERE tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')")).scalar()
            print(f"   usuario: {total_usuarios} total ({admins} administradores)")
            
            print("\n🧹 Iniciando limpeza...")
            
            # Limpar todas as tabelas
            for tabela in tabelas_completa_limpeza:
                try:
                    result = db.session.execute(text(f"DELETE FROM {tabela}"))
                    print(f"   ✅ {tabela}: {result.rowcount} registros removidos")
                except Exception as e:
                    print(f"   ❌ {tabela}: Erro - {e}")
            
            # Limpar usuários não-administradores
            try:
                result = db.session.execute(text("DELETE FROM usuario WHERE tipo_usuario NOT IN ('ADMIN', 'SUPER_ADMIN')"))
                print(f"   ✅ usuario (não-admins): {result.rowcount} registros removidos")
            except Exception as e:
                print(f"   ❌ usuario: Erro - {e}")
            
            # Restaurar constraints
            db.session.execute(text("SET session_replication_role = DEFAULT;"))
            db.session.commit()
            
            print("\n📊 Estatísticas após limpeza:")
            for tabela in tabelas_completa_limpeza:
                try:
                    result = db.session.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
                    print(f"   {tabela}: {result} registros")
                except:
                    pass
            
            # Verificar administradores restantes
            admins_restantes = db.session.execute(text("SELECT id, nome, email, tipo_usuario FROM usuario ORDER BY id")).fetchall()
            print(f"\n👤 Administradores preservados ({len(admins_restantes)}):")
            for admin in admins_restantes:
                print(f"   ID {admin[0]}: {admin[1]} ({admin[2]}) - {admin[3]}")
            
            print("\n✅ LIMPEZA COMPLETA FINALIZADA!")
            print("Banco de dados limpo. Apenas administradores foram mantidos.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na limpeza: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    limpeza_completa()