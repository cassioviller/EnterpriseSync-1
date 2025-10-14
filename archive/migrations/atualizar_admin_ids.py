#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para atualizar admin_id nos dados existentes
SIGE v8.0 - Sistema Multi-Tenant
"""

from app import app, db
from models import *

def main():
    with app.app_context():
        print("🔧 ATUALIZANDO ADMIN_IDs PARA MULTI-TENANT")
        print("=" * 60)
        
        # Obter admins
        admin_geral = Usuario.query.filter_by(username='admin').first()
        admin_valeverde = Usuario.query.filter_by(username='valeverde').first()
        
        if not admin_geral or not admin_valeverde:
            print("❌ Admins não encontrados!")
            return
        
        print(f"✅ Admin Geral ID: {admin_geral.id}")
        print(f"✅ Admin Vale Verde ID: {admin_valeverde.id}")
        print()
        
        # 1. Atualizar funcionários
        print("👥 Atualizando funcionários...")
        funcionarios_vv = Funcionario.query.filter(Funcionario.codigo.like('VV%')).all()
        funcionarios_outros = Funcionario.query.filter(~Funcionario.codigo.like('VV%')).all()
        
        for func in funcionarios_vv:
            func.admin_id = admin_valeverde.id
        
        for func in funcionarios_outros:
            func.admin_id = admin_geral.id
        
        print(f"   ✅ {len(funcionarios_vv)} funcionários VV → Admin Vale Verde")
        print(f"   ✅ {len(funcionarios_outros)} funcionários outros → Admin Geral")
        
        # 2. Atualizar obras
        print("🏗️ Atualizando obras...")
        obras_vv = Obra.query.filter(Obra.nome.like('%VV')).all()
        obras_outras = Obra.query.filter(~Obra.nome.like('%VV')).all()
        
        for obra in obras_vv:
            obra.admin_id = admin_valeverde.id
        
        for obra in obras_outras:
            obra.admin_id = admin_geral.id
            
        print(f"   ✅ {len(obras_vv)} obras VV → Admin Vale Verde")
        print(f"   ✅ {len(obras_outras)} obras outras → Admin Geral")
        
        # 3. Atualizar veículos
        print("🚗 Atualizando veículos...")
        veiculos_vv = Veiculo.query.filter(Veiculo.placa.like('VV-%')).all()
        veiculos_outros = Veiculo.query.filter(~Veiculo.placa.like('VV-%')).all()
        
        for veiculo in veiculos_vv:
            veiculo.admin_id = admin_valeverde.id
            
        for veiculo in veiculos_outros:
            veiculo.admin_id = admin_geral.id
            
        print(f"   ✅ {len(veiculos_vv)} veículos VV → Admin Vale Verde")
        print(f"   ✅ {len(veiculos_outros)} veículos outros → Admin Geral")
        
        # Salvar alterações
        db.session.commit()
        
        print()
        print("🎉 ATUALIZAÇÃO CONCLUÍDA!")
        print("   Multi-tenant configurado com admin_id")
        print("   Dados isolados por administrador")
        
        # Verificar resultado
        print()
        print("📊 VERIFICAÇÃO:")
        vv_funcs = Funcionario.query.filter_by(admin_id=admin_valeverde.id).count()
        vv_obras = Obra.query.filter_by(admin_id=admin_valeverde.id).count()
        vv_veics = Veiculo.query.filter_by(admin_id=admin_valeverde.id).count()
        
        print(f"   Vale Verde: {vv_funcs} funcionários, {vv_obras} obras, {vv_veics} veículos")
        
        geral_funcs = Funcionario.query.filter_by(admin_id=admin_geral.id).count()
        geral_obras = Obra.query.filter_by(admin_id=admin_geral.id).count()
        geral_veics = Veiculo.query.filter_by(admin_id=admin_geral.id).count()
        
        print(f"   Geral: {geral_funcs} funcionários, {geral_obras} obras, {geral_veics} veículos")

if __name__ == '__main__':
    main()