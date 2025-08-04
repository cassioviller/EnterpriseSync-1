#!/usr/bin/env python3
"""
🔍 DEBUG: Verificar permissões de edição de ponto
"""

from app import app, db
from models import RegistroPonto, Funcionario, Usuario
from sqlalchemy import text

def debug_permissoes():
    """Debug das permissões de edição"""
    print("🔍 ANÁLISE: Permissões de edição de ponto")
    print("=" * 60)
    
    with app.app_context():
        # Buscar primeiro registro
        registro = RegistroPonto.query.first()
        if not registro:
            print("❌ Nenhum registro encontrado")
            return
        
        funcionario = registro.funcionario_ref
        print(f"📋 Registro: {registro.id}")
        print(f"👤 Funcionário: {funcionario.nome} (ID: {funcionario.id})")
        print(f"🏢 Admin do funcionário: {funcionario.admin_id}")
        
        # Buscar usuários admin
        admins = Usuario.query.filter_by(tipo_usuario='ADMIN').all()
        print(f"\n👥 USUÁRIOS ADMIN ENCONTRADOS:")
        for admin in admins:
            print(f"   • {admin.email} (ID: {admin.id})")
            
            # Verificar se pode editar este registro
            pode_editar = funcionario.admin_id == admin.id
            print(f"     Pode editar: {'✅ SIM' if pode_editar else '❌ NÃO'}")
        
        # Verificar super admin
        super_admin = Usuario.query.filter_by(tipo_usuario='SUPER_ADMIN').first()
        if super_admin:
            print(f"\n🔑 SUPER ADMIN: {super_admin.email}")
            print(f"   Pode editar qualquer: ✅ SIM")
        
        return registro, funcionario

def simular_verificacao_permissao():
    """Simular a função de verificação de permissão"""
    print(f"\n🧪 SIMULAÇÃO: Verificação de permissão")
    print("=" * 60)
    
    with app.app_context():
        registro, funcionario = debug_permissoes()
        
        # Testar com cada usuário
        usuarios = Usuario.query.all()
        
        for usuario in usuarios:
            print(f"\n👤 USUÁRIO: {usuario.email} ({usuario.tipo_usuario})")
            
            # Lógica de verificação (copiada do código)
            if usuario.tipo_usuario == 'SUPER_ADMIN':
                pode_editar = True
                motivo = "Super Admin pode editar tudo"
            elif usuario.tipo_usuario == 'ADMIN':
                pode_editar = funcionario.admin_id == usuario.id
                motivo = f"Admin {usuario.id} vs Funcionário Admin {funcionario.admin_id}"
            else:
                pode_editar = False
                motivo = "Funcionários não podem editar"
            
            status = "✅ PERMITIDO" if pode_editar else "❌ NEGADO"
            print(f"   {status}: {motivo}")

def verificar_relacionamento_admin_funcionario():
    """Verificar relacionamento entre admin e funcionário"""
    print(f"\n🔗 RELACIONAMENTO: Admin ↔ Funcionário")
    print("=" * 60)
    
    with app.app_context():
        # Buscar todos funcionários e seus admins
        funcionarios = db.session.execute(text("""
            SELECT 
                f.id as func_id,
                f.nome as func_nome,
                f.admin_id,
                u.email as admin_email,
                u.tipo_usuario
            FROM funcionario f
            LEFT JOIN usuario u ON f.admin_id = u.id
            ORDER BY f.nome
            LIMIT 10
        """)).fetchall()
        
        print("📋 FUNCIONÁRIOS E SEUS ADMINS:")
        for func in funcionarios:
            print(f"   • {func.func_nome} (ID: {func.func_id})")
            if func.admin_email:
                print(f"     Admin: {func.admin_email} (ID: {func.admin_id})")
            else:
                print(f"     ❌ SEM ADMIN DEFINIDO (admin_id: {func.admin_id})")

def corrigir_admin_ids():
    """Corrigir admin_ids se necessário"""
    print(f"\n🔧 CORREÇÃO: Admin IDs")
    print("=" * 60)
    
    with app.app_context():
        # Buscar funcionários sem admin válido
        funcionarios_sem_admin = db.session.execute(text("""
            SELECT f.id, f.nome
            FROM funcionario f
            LEFT JOIN usuario u ON f.admin_id = u.id
            WHERE u.id IS NULL OR u.tipo_usuario != 'ADMIN'
        """)).fetchall()
        
        if funcionarios_sem_admin:
            print(f"⚠️ FUNCIONÁRIOS SEM ADMIN VÁLIDO:")
            for func in funcionarios_sem_admin:
                print(f"   • {func.nome} (ID: {func.id})")
            
            # Buscar primeiro admin disponível
            primeiro_admin = Usuario.query.filter_by(tipo_usuario='ADMIN').first()
            if primeiro_admin:
                print(f"\n🔧 CORRIGINDO para admin: {primeiro_admin.email}")
                
                for func in funcionarios_sem_admin:
                    db.session.execute(text("""
                        UPDATE funcionario 
                        SET admin_id = :admin_id 
                        WHERE id = :func_id
                    """), {
                        'admin_id': primeiro_admin.id,
                        'func_id': func.id
                    })
                
                db.session.commit()
                print("✅ Admin IDs corrigidos")
            else:
                print("❌ Nenhum admin disponível para correção")
        else:
            print("✅ Todos funcionários têm admin válido")

if __name__ == "__main__":
    print("🔍 DEBUG COMPLETO: Permissões de edição")
    print("=" * 80)
    
    # 1. Debug básico
    debug_permissoes()
    
    # 2. Simulação
    simular_verificacao_permissao()
    
    # 3. Verificar relacionamentos
    verificar_relacionamento_admin_funcionario()
    
    # 4. Corrigir se necessário
    corrigir_admin_ids()
    
    print(f"\n🎯 RESUMO:")
    print("   1. Verificou permissões atuais")
    print("   2. Simulou verificação para todos usuários")
    print("   3. Analisou relacionamento admin-funcionário")
    print("   4. Corrigiu admin_ids se necessário")
    print(f"\n✅ Após correções, tente editar novamente")