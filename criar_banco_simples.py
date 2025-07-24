#!/usr/bin/env python3
"""
Script MAIS SIMPLES para criar banco no EasyPanel
"""

import os
os.environ.setdefault('FLASK_APP', 'app.py')

print("🚀 CRIANDO BANCO DE DADOS SIGE v8.0")
print("=" * 45)

try:
    print("📋 Importando aplicação...")
    from app import app, db
    print("✅ App importado com sucesso")
    
    print("📋 Importando modelos...")
    import models
    print("✅ Modelos importados")
    
    print("📋 Criando tabelas...")
    with app.app_context():
        db.create_all()
        print("✅ Comando db.create_all() executado")
        
        # Verificar tabelas criadas
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📊 Total de tabelas: {len(tables)}")
        
        if len(tables) > 0:
            print("📋 Tabelas criadas:")
            for table in sorted(tables)[:10]:  # Mostrar só as primeiras 10
                print(f"   • {table}")
            if len(tables) > 10:
                print(f"   ... e mais {len(tables) - 10} tabelas")
                
            print("\n🎯 BANCO CRIADO COM SUCESSO!")
            print("Agora você pode acessar o sistema")
        else:
            print("❌ Nenhuma tabela foi criada")
            print("Verifique se os modelos estão corretos")

except Exception as e:
    print(f"❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
    print("\nTente executar manualmente:")
    print("python -c \"from app import app, db; import models; app.app_context().push(); db.create_all()\"")