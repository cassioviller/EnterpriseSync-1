#!/usr/bin/env python3
"""
Script final para criar obra no Vale Verde sem RDO
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Obra
from datetime import date

def criar_obra_vale_verde():
    """Criar obra simples no Vale Verde"""
    
    with app.app_context():
        print("=== CRIANDO OBRA DE CONCRETAGEM VALE VERDE ===\n")
        
        # Criar obra de concretagem
        obra = Obra(
            nome="Edifício Residencial Torres do Vale - Concretagem",
            codigo="VV-CONC-001",
            endereco="Av. Central, 1200 - Jardim das Flores, Vale Verde/MG",
            data_inicio=date(2025, 7, 22),
            data_previsao_fim=date(2025, 12, 15),
            orcamento=2800000.00,
            area_total_m2=4500.0,
            status="Em andamento",
            admin_id=10  # Vale Verde
        )
        
        db.session.add(obra)
        db.session.commit()
        
        print(f"✅ OBRA CRIADA COM SUCESSO!")
        print(f"")
        print(f"📋 Detalhes da Obra:")
        print(f"• Nome: {obra.nome}")
        print(f"• ID: {obra.id}")
        print(f"• Código: {obra.codigo}")
        print(f"• Endereço: {obra.endereco}")
        print(f"• Orçamento: R$ {obra.orcamento:,.2f}")
        print(f"• Período: {obra.data_inicio} a {obra.data_previsao_fim}")
        print(f"• Área Total: {obra.area_total_m2} m²")
        print(f"• Status: {obra.status}")
        print(f"• Admin ID: {obra.admin_id} (Vale Verde)")
        
        print(f"\n🧪 COMO TESTAR RDO:")
        print(f"")
        print(f"1. LOGIN COMO ADMIN VALE VERDE:")
        print(f"   • Usuário: valeverde")
        print(f"   • Senha: admin123")
        print(f"   • Vá para 'Obras' e veja a obra de concretagem")
        print(f"   • Vá para 'RDOs' para ver/criar RDOs")
        print(f"")
        print(f"2. CRIAR FUNCIONÁRIO COM ACESSO:")
        print(f"   • Em 'Configurações' > 'Acessos'")
        print(f"   • Clique 'Novo Funcionário'")
        print(f"   • Crie login para um dos funcionários Vale Verde")
        print(f"")
        print(f"3. TESTAR CRIAÇÃO DE RDO:")
        print(f"   • Faça login como funcionário criado")
        print(f"   • Vá para 'RDO' > 'Novo RDO'")
        print(f"   • Selecione a obra de concretagem")
        print(f"   • Preencha o formulário RDO")
        print(f"   • Salve e veja se aparece no dashboard")
        print(f"")
        print(f"4. VERIFICAR NO SISTEMA ADMIN:")
        print(f"   • Faça logout e entre como valeverde/admin123")
        print(f"   • Veja se RDO aparece na lista de RDOs da empresa")
        print(f"   • Verifique isolamento: outros admins NÃO veem este RDO")

if __name__ == "__main__":
    criar_obra_vale_verde()