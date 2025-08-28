"""
Script para limpeza completa do banco de dados - versão simples
Mantém apenas usuários administradores
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from models import *
import os

def limpeza_simples():
    """Limpar todo o banco exceto administradores usando comandos simples"""
    
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🗑️ LIMPEZA COMPLETA - VERSÃO SIMPLES")
            
            # Lista de comandos de limpeza em ordem (das dependências para as principais)
            comandos_limpeza = [
                "DELETE FROM rdo_servico_subatividade",
                "DELETE FROM rdo_mao_obra", 
                "DELETE FROM rdo",
                "DELETE FROM registro_ponto",
                "DELETE FROM outro_custo",
                "DELETE FROM registro_alimentacao", 
                "DELETE FROM horarios_padrao",
                "DELETE FROM uso_veiculo",
                "DELETE FROM funcionario",
                "DELETE FROM proposta_itens",
                "DELETE FROM proposta_templates",
                "DELETE FROM propostas_comerciais",
                "DELETE FROM custo_obra",
                "DELETE FROM servico_obra",
                "DELETE FROM obra",
                "DELETE FROM subatividade_mestre",
                "DELETE FROM servico",
                "DELETE FROM configuracoes_empresa",
                "DELETE FROM empresas",
                "DELETE FROM usuario WHERE tipo_usuario NOT IN ('ADMIN', 'SUPER_ADMIN')"
            ]
            
            total_removidos = 0
            
            for comando in comandos_limpeza:
                try:
                    result = db.session.execute(text(comando))
                    removidos = result.rowcount
                    total_removidos += removidos
                    tabela = comando.split(" FROM ")[1].split(" WHERE")[0] if " WHERE " in comando else comando.split(" FROM ")[1]
                    if removidos > 0:
                        print(f"   ✅ {tabela}: {removidos} registros removidos")
                    else:
                        print(f"   ℹ️ {tabela}: já estava vazio")
                except Exception as e:
                    tabela = comando.split(" FROM ")[1] if " FROM " in comando else "comando"
                    print(f"   ❌ {tabela}: {e}")
            
            db.session.commit()
            
            print(f"\n📊 Total de {total_removidos} registros removidos")
            
            # Verificar administradores restantes
            admins = db.session.execute(text("SELECT id, nome, email, tipo_usuario FROM usuario ORDER BY id")).fetchall()
            print(f"\n👤 Administradores preservados ({len(admins)}):")
            for admin in admins:
                print(f"   ID {admin[0]}: {admin[1]} ({admin[2]}) - {admin[3]}")
            
            print("\n✅ LIMPEZA SIMPLES FINALIZADA!")
            print("Banco de dados limpo. Apenas administradores foram mantidos.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro geral na limpeza: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    limpeza_simples()