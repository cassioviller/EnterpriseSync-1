#!/usr/bin/env python3
"""
Correção de dados de tenant para lançamentos múltiplos
Vou corrigir as associações de admin_id nos funcionários e obras
"""

from app import app, db
from models import *
from werkzeug.security import generate_password_hash

def corrigir_dados_tenant():
    """Corrigir dados de tenant"""
    
    with app.app_context():
        print("🔧 CORREÇÃO: Dados de Tenant para Lançamentos Múltiplos")
        print("=" * 60)
        
        # 1. Verificar/criar admin padrão
        admin_padrao = Usuario.query.filter_by(
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True
        ).first()
        
        if not admin_padrao:
            print("🏗️ Criando admin padrão...")
            admin_padrao = Usuario(
                username='admin',
                email='admin@sige.com',
                password_hash=generate_password_hash('admin123'),
                nome='Administrador Sistema',
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True
            )
            db.session.add(admin_padrao)
            db.session.commit()
            print(f"✅ Admin criado: {admin_padrao.nome} (ID: {admin_padrao.id})")
        else:
            print(f"✅ Admin encontrado: {admin_padrao.nome} (ID: {admin_padrao.id})")
        
        # 2. Associar funcionários sem admin_id ao admin padrão
        funcionarios_sem_admin = Funcionario.query.filter_by(admin_id=None).all()
        print(f"\n👥 Funcionários sem admin_id: {len(funcionarios_sem_admin)}")
        
        for funcionario in funcionarios_sem_admin:
            funcionario.admin_id = admin_padrao.id
            print(f"   ✅ {funcionario.nome} -> Admin ID: {admin_padrao.id}")
        
        # 3. Associar obras sem admin_id ao admin padrão
        obras_sem_admin = Obra.query.filter_by(admin_id=None).all()
        print(f"\n🏗️ Obras sem admin_id: {len(obras_sem_admin)}")
        
        for obra in obras_sem_admin:
            obra.admin_id = admin_padrao.id
            print(f"   ✅ {obra.nome} -> Admin ID: {admin_padrao.id}")
        
        # 4. Commit das alterações
        try:
            db.session.commit()
            print(f"\n💾 Alterações salvas com sucesso!")
        except Exception as e:
            print(f"\n❌ Erro ao salvar: {e}")
            db.session.rollback()
            return False
        
        # 5. Verificação final
        print(f"\n🔍 Verificação final:")
        total_funcionarios = Funcionario.query.count()
        funcionarios_com_admin = Funcionario.query.filter(Funcionario.admin_id.isnot(None)).count()
        total_obras = Obra.query.count()
        obras_com_admin = Obra.query.filter(Obra.admin_id.isnot(None)).count()
        
        print(f"Funcionários: {funcionarios_com_admin}/{total_funcionarios} com admin_id")
        print(f"Obras: {obras_com_admin}/{total_obras} com admin_id")
        
        # 6. Testar lançamento múltiplo agora
        print(f"\n🧪 Testando lançamento múltiplo...")
        funcionario_teste = Funcionario.query.filter(
            Funcionario.admin_id == admin_padrao.id
        ).first()
        
        obra_teste = Obra.query.filter(
            Obra.admin_id == admin_padrao.id
        ).first()
        
        if funcionario_teste and obra_teste:
            print(f"✅ Dados de teste:")
            print(f"   Funcionário: {funcionario_teste.nome} (ID: {funcionario_teste.id})")
            print(f"   Obra: {obra_teste.nome} (ID: {obra_teste.id})")
            print(f"   Admin: {admin_padrao.nome} (ID: {admin_padrao.id})")
            
            # Dados de teste que devem funcionar agora
            dados_teste = {
                'funcionario_id': funcionario_teste.id,
                'obra_id': obra_teste.id,
                'admin_id': admin_padrao.id
            }
            print(f"📋 Dados para usar no teste: {dados_teste}")
            
            return True
        else:
            print(f"❌ Não foi possível encontrar dados de teste válidos")
            return False

if __name__ == "__main__":
    resultado = corrigir_dados_tenant()
    if resultado:
        print(f"\n🎉 CORREÇÃO CONCLUÍDA COM SUCESSO!")
    else:
        print(f"\n🔧 CORREÇÃO PARCIAL - Revisar manualmente")