#!/usr/bin/env python3
"""
Script simplificado para criar obra de concretagem no Vale Verde
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Obra, RDO, Usuario, TipoUsuario
from datetime import datetime, date

def criar_obra_concretagem():
    """Criar obra de concretagem no Vale Verde"""
    
    with app.app_context():
        print("=== CRIANDO OBRA DE CONCRETAGEM - VALE VERDE ===\n")
        
        # 1. Criar obra de concretagem
        obra = Obra(
            nome="Edifício Residencial Torres do Vale - Concretagem",
            codigo="VV-CONC-2025-01",
            endereco="Av. Central, 1200 - Bairro Jardim das Flores, Vale Verde/MG",
            data_inicio=date(2025, 7, 15),
            data_previsao_fim=date(2025, 11, 30),
            orcamento=2800000.00,
            area_total_m2=4500.0,
            status="Em andamento",
            admin_id=10  # Vale Verde
        )
        
        db.session.add(obra)
        db.session.commit()
        
        print(f"✅ Obra criada: {obra.nome} (ID: {obra.id})")
        print(f"   Código: {obra.codigo}")
        print(f"   Orçamento: R$ {obra.orcamento:,.2f}")
        print(f"   Período: {obra.data_inicio} a {obra.data_previsao_fim}")
        print(f"   Área: {obra.area_total_m2} m²")
        
        # 2. Buscar usuário funcionário Vale Verde para criar RDO
        usuario_funcionario = Usuario.query.filter_by(
            tipo_usuario=TipoUsuario.FUNCIONARIO,
            admin_id=10,
            ativo=True
        ).first()
        
        if not usuario_funcionario:
            print("\n⚠️ NENHUM USUÁRIO FUNCIONÁRIO VALE VERDE ENCONTRADO")
            print("Para testar RDO, siga os passos:")
            print("1. Entre como Vale Verde: valeverde/admin123")
            print("2. Vá em Configurações > Acessos")
            print("3. Crie um funcionário com acesso ao sistema")
            print("4. Depois faça login com o funcionário criado")
        else:
            # Criar RDO de exemplo
            numero_rdo = f"RDO-{date.today().strftime('%Y%m%d')}-001"
            rdo = RDO(
                numero_rdo=numero_rdo,
                obra_id=obra.id,
                data_relatorio=date.today(),
                tempo_manha='Ensolarado',
                tempo_tarde='Ensolarado', 
                tempo_noite='Nublado',
                observacoes_meteorologicas='Clima favorável para concretagem. Temperatura 25°C.',
                comentario_geral='Início da concretagem da fundação. Equipe de 8 funcionários trabalhando. Concretagem programada para blocos B1 a B5. Concreto FCK 25 MPa conforme projeto.',
                criado_por_id=usuario_funcionario.id,
                status='Finalizado'
            )
            
            db.session.add(rdo)
            db.session.commit()
            
            print(f"\n✅ RDO CRIADO:")
            print(f"   Criado por: {usuario_funcionario.nome} ({usuario_funcionario.username})")
            print(f"   Número: {rdo.numero_rdo}")
            print(f"   Data: {rdo.data_relatorio}")
            print(f"   Status: {rdo.status}")
            
        print(f"\n=== OBRA DE CONCRETAGEM CRIADA COM SUCESSO! ===")
        print(f"\n📋 DADOS PARA TESTE:")
        print(f"• Obra: {obra.nome}")
        print(f"• ID da Obra: {obra.id}")
        print(f"• Admin ID: 10 (Vale Verde)")
        
        if usuario_funcionario:
            print(f"• Funcionário: {usuario_funcionario.username}/123456")
        
        print(f"\n🧪 COMO TESTAR RDO:")
        print(f"1. Login Vale Verde Admin: valeverde/admin123")
        print(f"   - Ver obra na lista de obras")
        print(f"   - Ver RDO na lista de RDOs")
        print(f"")
        
        if usuario_funcionario:
            print(f"2. Login Funcionário: {usuario_funcionario.username}/123456")
            print(f"   - Criar novo RDO para obra de concretagem")
            print(f"   - Verificar se aparece no dashboard do funcionário")
        else:
            print(f"2. Criar funcionário com acesso primeiro!")
            print(f"   - Configurações > Acessos > Novo Funcionário")
            print(f"   - Depois testar criação de RDO")

if __name__ == "__main__":
    criar_obra_concretagem()