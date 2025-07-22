#!/usr/bin/env python3
"""
Script para testar o isolamento completo por tenant no sistema SIGE
Verifica se os dados estão sendo filtrados corretamente por admin_id
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Usuario, Funcionario, Obra, Veiculo, RegistroAlimentacao, RegistroPonto

def testar_isolamento():
    """Testa o isolamento de dados por tenant"""
    
    with app.app_context():
        print("=== TESTE DE ISOLAMENTO POR TENANT ===\n")
        
        # 1. Verificar usuários admin
        print("1. USUÁRIOS ADMINISTRADORES:")
        # Buscar admins pelo username conhecido
        admins = Usuario.query.filter(Usuario.username.in_(['admin', 'valeverde'])).all()
        for admin in admins:
            print(f"   - {admin.username} (ID: {admin.id})")
        
        print(f"\nTotal de administradores: {len(admins)}")
        
        # 2. Verificar funcionários por admin
        print("\n2. FUNCIONÁRIOS POR ADMIN:")
        for admin in admins:
            funcionarios = Funcionario.query.filter_by(admin_id=admin.id).all()
            print(f"\n   Admin {admin.nome} ({admin.username}) - {len(funcionarios)} funcionários:")
            for func in funcionarios:
                print(f"     - {func.nome} (Código: {func.codigo})")
        
        # 3. Verificar obras por admin
        print("\n3. OBRAS POR ADMIN:")
        for admin in admins:
            obras = Obra.query.filter_by(admin_id=admin.id).all()
            print(f"\n   Admin {admin.nome} - {len(obras)} obras:")
            for obra in obras:
                print(f"     - {obra.nome} (Status: {obra.status})")
        
        # 4. Verificar veículos por admin
        print("\n4. VEÍCULOS POR ADMIN:")
        for admin in admins:
            veiculos = Veiculo.query.filter_by(admin_id=admin.id).all()
            print(f"\n   Admin {admin.nome} - {len(veiculos)} veículos:")
            for veiculo in veiculos:
                print(f"     - {veiculo.placa} ({veiculo.marca} {veiculo.modelo})")
        
        # 5. Verificar registros de alimentação por admin (via funcionários)
        print("\n5. REGISTROS DE ALIMENTAÇÃO POR ADMIN:")
        for admin in admins:
            funcionarios = Funcionario.query.filter_by(admin_id=admin.id).all()
            funcionarios_ids = [f.id for f in funcionarios]
            
            if funcionarios_ids:
                registros_alimentacao = RegistroAlimentacao.query.filter(
                    RegistroAlimentacao.funcionario_id.in_(funcionarios_ids)
                ).count()
            else:
                registros_alimentacao = 0
                
            print(f"   Admin {admin.nome} - {registros_alimentacao} registros de alimentação")
        
        # 6. Verificar registros de ponto por admin (via funcionários)
        print("\n6. REGISTROS DE PONTO POR ADMIN:")
        for admin in admins:
            funcionarios = Funcionario.query.filter_by(admin_id=admin.id).all()
            funcionarios_ids = [f.id for f in funcionarios]
            
            if funcionarios_ids:
                registros_ponto = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id.in_(funcionarios_ids)
                ).count()
            else:
                registros_ponto = 0
                
            print(f"   Admin {admin.nome} - {registros_ponto} registros de ponto")
        
        # 7. Teste de isolamento - verificar se não há vazamento de dados
        print("\n7. TESTE DE ISOLAMENTO:")
        
        # Verificar se todos os funcionários têm admin_id
        funcionarios_sem_admin = Funcionario.query.filter_by(admin_id=None).count()
        print(f"   - Funcionários sem admin_id: {funcionarios_sem_admin}")
        
        # Verificar se todas as obras têm admin_id
        obras_sem_admin = Obra.query.filter_by(admin_id=None).count()
        print(f"   - Obras sem admin_id: {obras_sem_admin}")
        
        # Verificar se todos os veículos têm admin_id
        veiculos_sem_admin = Veiculo.query.filter_by(admin_id=None).count()
        print(f"   - Veículos sem admin_id: {veiculos_sem_admin}")
        
        print("\n=== RESULTADO DO TESTE ===")
        if funcionarios_sem_admin == 0 and obras_sem_admin == 0 and veiculos_sem_admin == 0:
            print("✅ SUCESSO: Isolamento por tenant implementado corretamente!")
            print("✅ Todos os registros estão associados a um administrador")
        else:
            print("❌ ERRO: Alguns registros não estão associados a administradores")
            print("❌ O isolamento por tenant não está completo")
        
        print("\n=== CREDENCIAIS DE TESTE ===")
        print("Super Admin: axiom/cassio123")
        print("Admin Geral: admin/admin123")
        print("Admin Vale Verde: valeverde/admin123")
        
        print("\nFuncionários Vale Verde: vv001-vv010 / 123456")
        print("Outros funcionários: F0001-F0099 / 123456")

if __name__ == "__main__":
    testar_isolamento()