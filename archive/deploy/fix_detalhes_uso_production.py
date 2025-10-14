#!/usr/bin/env python3
"""
🔧 CORREÇÃO AUTOMÁTICA: Modal Detalhes Uso Veículos - Produção
==============================================================
Corrige problemas de admin_id e relacionamentos em UsoVeiculo
Deploy: Hostinger EasyPanel via docker-entrypoint-easypanel-auto.sh
Data: 22/09/2025 - 14:30
==============================================================
"""

import os
import sys
import traceback
from datetime import datetime

# Adicionar diretório raiz ao path
sys.path.insert(0, '/app')
sys.path.insert(0, '/workspace')
sys.path.insert(0, '.')

def fix_detalhes_uso_production():
    """Corrige problemas com detalhes de uso em produção"""
    
    print("🔧 INICIANDO CORREÇÃO: Modal Detalhes Uso Veículos")
    print("=" * 60)
    
    try:
        # Configurar o ambiente Flask
        os.environ['FLASK_ENV'] = 'production'
        os.environ['DIGITAL_MASTERY_MODE'] = 'true'
        
        # Importar componentes do Flask
        from app import app, db
        
        with app.app_context():
            # 1. Verificar UsoVeiculo sem admin_id
            print("🔍 Verificando UsoVeiculo sem admin_id...")
            
            # Query SQL crua para verificar dados
            result = db.session.execute(db.text("""
                SELECT 
                    uv.id,
                    uv.veiculo_id,
                    v.admin_id as veiculo_admin_id,
                    uv.admin_id as uso_admin_id
                FROM uso_veiculo uv 
                LEFT JOIN veiculo v ON uv.veiculo_id = v.id
                WHERE uv.admin_id IS NULL OR uv.admin_id != v.admin_id
                LIMIT 10
            """)).fetchall()
            
            if result:
                print(f"⚠️ Encontrados {len(result)} registros de uso com admin_id inconsistente")
                
                # Corrigir admin_id em uso_veiculo
                db.session.execute(db.text("""
                    UPDATE uso_veiculo 
                    SET admin_id = (
                        SELECT admin_id 
                        FROM veiculo 
                        WHERE veiculo.id = uso_veiculo.veiculo_id
                    )
                    WHERE admin_id IS NULL 
                       OR admin_id != (
                           SELECT admin_id 
                           FROM veiculo 
                           WHERE veiculo.id = uso_veiculo.veiculo_id
                       )
                """))
                
                print("✅ Admin_id corrigido em uso_veiculo")
            else:
                print("✅ Todos os registros de uso têm admin_id correto")
            
            # 2. Verificar PassageiroVeiculo
            print("🔍 Verificando PassageiroVeiculo...")
            
            passageiro_result = db.session.execute(db.text("""
                SELECT COUNT(*) as count
                FROM passageiro_veiculo pv
                LEFT JOIN uso_veiculo uv ON pv.uso_veiculo_id = uv.id
                WHERE pv.admin_id IS NULL OR pv.admin_id != uv.admin_id
            """)).fetchone()
            
            if passageiro_result and passageiro_result[0] > 0:
                print(f"⚠️ Encontrados {passageiro_result[0]} registros de passageiro com admin_id inconsistente")
                
                # Corrigir admin_id em passageiro_veiculo
                db.session.execute(db.text("""
                    UPDATE passageiro_veiculo 
                    SET admin_id = (
                        SELECT admin_id 
                        FROM uso_veiculo 
                        WHERE uso_veiculo.id = passageiro_veiculo.uso_veiculo_id
                    )
                    WHERE admin_id IS NULL 
                       OR admin_id != (
                           SELECT admin_id 
                           FROM uso_veiculo 
                           WHERE uso_veiculo.id = passageiro_veiculo.uso_veiculo_id
                       )
                """))
                
                print("✅ Admin_id corrigido em passageiro_veiculo")
            else:
                print("✅ Todos os registros de passageiro têm admin_id correto")
            
            # 3. Verificar integridade geral
            print("🔍 Verificando integridade geral...")
            
            integrity_check = db.session.execute(db.text("""
                SELECT 
                    (SELECT COUNT(*) FROM uso_veiculo) as total_usos,
                    (SELECT COUNT(*) FROM uso_veiculo WHERE admin_id IS NOT NULL) as usos_com_admin,
                    (SELECT COUNT(*) FROM passageiro_veiculo) as total_passageiros,
                    (SELECT COUNT(*) FROM passageiro_veiculo WHERE admin_id IS NOT NULL) as passageiros_com_admin
            """)).fetchone()
            
            if integrity_check:
                print(f"📊 RELATÓRIO DE INTEGRIDADE:")
                print(f"   • Total usos: {integrity_check[0]}")
                print(f"   • Usos com admin_id: {integrity_check[1]}")
                print(f"   • Total passageiros: {integrity_check[2]}")
                print(f"   • Passageiros com admin_id: {integrity_check[3]}")
            else:
                print("⚠️ Não foi possível verificar integridade")
            
            # 4. Testar uma consulta de detalhes
            print("🧪 Testando consulta de detalhes...")
            
            test_result = db.session.execute(db.text("""
                SELECT uv.id, v.placa, f.nome
                FROM uso_veiculo uv
                LEFT JOIN veiculo v ON uv.veiculo_id = v.id
                LEFT JOIN funcionario f ON uv.funcionario_id = f.id
                WHERE uv.admin_id IS NOT NULL
                LIMIT 1
            """)).fetchone()
            
            if test_result:
                print(f"✅ Consulta teste funcionando: Uso {test_result[0]}, Placa {test_result[1]}, Condutor {test_result[2]}")
            else:
                print("⚠️ Nenhum dado encontrado na consulta teste")
            
            # Commit das mudanças
            db.session.commit()
            print("💾 Mudanças salvas no banco de dados")
            
            print("🎉 CORREÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ ERRO na correção: {str(e)}")
        print("📍 Traceback completo:")
        traceback.print_exc()
        
        # Rollback em caso de erro
        try:
            # Importar novamente se necessário
            if 'db' not in locals():
                from app import db
            db.session.rollback()
            print("🔄 Rollback executado")
        except Exception as rollback_error:
            print(f"⚠️ Erro no rollback: {rollback_error}")
        
        return False

if __name__ == "__main__":
    success = fix_detalhes_uso_production()
    if success:
        print("✅ Script executado com sucesso")
        sys.exit(0)
    else:
        print("❌ Script falhou")
        sys.exit(1)