"""
Limpeza total final - Remove tudo exceto administradores
"""
import os
import sys
sys.path.append('.')

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from models import db

def limpeza_total():
    """Limpeza final de tudo"""
    
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🗑️ LIMPEZA TOTAL FINAL")
            
            # Comando direto para truncar todas as tabelas (ignora constraints)
            tabelas = [
                'custo_veiculo',
                'registro_ponto', 
                'rdo_servico_subatividade',
                'rdo_mao_obra',
                'rdo',
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
                'configuracoes_empresa',
                'empresas'
            ]
            
            # Usar TRUNCATE CASCADE para forçar remoção
            for tabela in tabelas:
                try:
                    db.session.execute(text(f"TRUNCATE TABLE {tabela} CASCADE"))
                    print(f"   ✅ {tabela}")
                except Exception as e:
                    print(f"   ⚠️ {tabela}: {e}")
            
            # Remover usuários não-admin
            result = db.session.execute(text("DELETE FROM usuario WHERE tipo_usuario NOT IN ('ADMIN', 'SUPER_ADMIN')"))
            print(f"   ✅ usuario (não-admin): {result.rowcount} removidos")
            
            db.session.commit()
            
            # Verificação final
            print("\n📊 VERIFICAÇÃO FINAL:")
            verificacoes = [
                "SELECT COUNT(*) FROM funcionario",
                "SELECT COUNT(*) FROM obra", 
                "SELECT COUNT(*) FROM servico",
                "SELECT COUNT(*) FROM subatividade_mestre",
                "SELECT COUNT(*) FROM rdo",
                "SELECT COUNT(*) FROM propostas_comerciais",
                "SELECT COUNT(*) FROM usuario WHERE tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')"
            ]
            
            for sql in verificacoes:
                tabela = sql.split("FROM ")[1].split(" WHERE")[0] if " WHERE " in sql else sql.split("FROM ")[1]
                count = db.session.execute(text(sql)).scalar()
                print(f"   {tabela}: {count}")
            
            print("\n✅ LIMPEZA TOTAL CONCLUÍDA!")
            print("Banco limpo. Apenas administradores restaram.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    limpeza_total()