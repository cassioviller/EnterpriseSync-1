#!/usr/bin/env python3
"""
ASSOCIAR DANILO AO ADMIN VALE VERDE
Garante que Danilo José de Oliveira está associado ao admin Vale Verde
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario, Usuario

def associar_danilo_valverde():
    """Associa Danilo ao admin Vale Verde"""
    
    with app.app_context():
        print("ASSOCIANDO DANILO AO ADMIN VALE VERDE")
        print("=" * 50)
        
        # Buscar Danilo
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return False
        
        # Buscar admin Vale Verde
        admin_valverde = Usuario.query.filter(
            Usuario.nome.like('%Vale Verde%')
        ).first()
        
        if not admin_valverde:
            print("❌ Admin Vale Verde não encontrado")
            print("Buscando por username valverde...")
            admin_valverde = Usuario.query.filter(
                Usuario.username.like('%valverde%')
            ).first()
        
        if not admin_valverde:
            print("❌ Nenhum admin Vale Verde encontrado")
            return False
        
        print(f"✅ Danilo encontrado: {danilo.codigo} - {danilo.nome}")
        print(f"✅ Admin encontrado: {admin_valverde.username} - {admin_valverde.nome}")
        
        # Verificar associação atual
        if danilo.admin_id == admin_valverde.id:
            print("✅ Danilo já está associado ao admin Vale Verde")
            return True
        
        # Fazer associação
        danilo.admin_id = admin_valverde.id
        
        try:
            db.session.commit()
            print(f"✅ Danilo associado ao admin {admin_valverde.nome}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao associar: {e}")
            return False

def verificar_funcionarios_valverde():
    """Verifica todos os funcionários do admin Vale Verde"""
    
    with app.app_context():
        print("\nFUNCIONÁRIOS DO ADMIN VALE VERDE")
        print("=" * 40)
        
        # Buscar admin Vale Verde
        admin_valverde = Usuario.query.filter(
            Usuario.nome.like('%Vale Verde%')
        ).first()
        
        if not admin_valverde:
            admin_valverde = Usuario.query.filter(
                Usuario.username.like('%valverde%')
            ).first()
        
        if not admin_valverde:
            print("❌ Admin Vale Verde não encontrado")
            return
        
        # Buscar funcionários deste admin
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_valverde.id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        print(f"Admin: {admin_valverde.nome} (ID: {admin_valverde.id})")
        print(f"Funcionários associados: {len(funcionarios)}")
        
        for func in funcionarios:
            print(f"  • {func.codigo} - {func.nome}")
        
        # Verificar se Danilo está na lista
        danilo_na_lista = any('Danilo José' in f.nome for f in funcionarios)
        if danilo_na_lista:
            print("\n✅ Danilo José de Oliveira está na lista do Vale Verde")
        else:
            print("\n❌ Danilo José de Oliveira NÃO está na lista do Vale Verde")

if __name__ == "__main__":
    print("ASSOCIAÇÃO DANILO ↔ VALE VERDE")
    print("=" * 50)
    
    # Fazer associação
    sucesso = associar_danilo_valverde()
    
    if sucesso:
        # Verificar resultado
        verificar_funcionarios_valverde()
        
        print("\n" + "=" * 50)
        print("✅ ASSOCIAÇÃO CONCLUÍDA!")
        print("✅ Danilo agora aparece no perfil Vale Verde")
        print("✅ Lançamentos de Danilo visíveis para admin Vale Verde")
    else:
        print("\n❌ FALHA na associação")