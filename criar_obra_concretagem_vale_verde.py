#!/usr/bin/env python3
"""
Script para criar obra de concretagem no Vale Verde e popular com dados realistas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Obra, Servico, SubAtividade, RDO, Usuario, TipoUsuario
from datetime import datetime, date
import random

def criar_obra_concretagem():
    """Criar obra de concretagem no Vale Verde com dados completos"""
    
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
        
        # 2. Criar serviços específicos de concretagem
        servicos_concretagem = [
            {
                'nome': 'Concretagem de Fundação',
                'descricao': 'Concretagem de sapatas e blocos de fundação',
                'unidade': 'm³',
                'valor_unitario': 450.00
            },
            {
                'nome': 'Concretagem de Pilares',
                'descricao': 'Concretagem de pilares estruturais',
                'unidade': 'm³', 
                'valor_unitario': 520.00
            },
            {
                'nome': 'Concretagem de Vigas',
                'descricao': 'Concretagem de vigas principais e secundárias',
                'unidade': 'm³',
                'valor_unitario': 480.00
            },
            {
                'nome': 'Concretagem de Lajes',
                'descricao': 'Concretagem de lajes dos pavimentos',
                'unidade': 'm³',
                'valor_unitario': 420.00
            },
            {
                'nome': 'Concretagem de Escadas',
                'descricao': 'Concretagem de escadas e patamares',
                'unidade': 'm³',
                'valor_unitario': 550.00
            }
        ]
        
        servicos_ids = []
        for servico_data in servicos_concretagem:
            servico = Servico(
                nome=servico_data['nome'],
                descricao=servico_data['descricao'],
                unidade=servico_data['unidade'],
                valor_unitario=servico_data['valor_unitario'],
                admin_id=10
            )
            db.session.add(servico)
            db.session.commit()
            servicos_ids.append(servico.id)
            print(f"   ✅ Serviço: {servico.nome} - R$ {servico.valor_unitario}/m³")
        
        # 3. Criar subatividades para cada serviço
        subatividades_por_servico = {
            'Concretagem de Fundação': [
                'Preparação da base',
                'Montagem de formas',
                'Colocação de armadura',
                'Lançamento do concreto',
                'Adensamento com vibrador',
                'Acabamento superficial'
            ],
            'Concretagem de Pilares': [
                'Montagem de formas',
                'Verificação de prumo',
                'Lançamento do concreto',
                'Adensamento',
                'Cura do concreto'
            ],
            'Concretagem de Vigas': [
                'Montagem de formas',
                'Colocação de armadura',
                'Lançamento do concreto',
                'Nivelamento',
                'Acabamento'
            ],
            'Concretagem de Lajes': [
                'Montagem de formas',
                'Colocação de armadura',
                'Instalações embutidas',
                'Lançamento do concreto',
                'Sarrafeamento',
                'Cura'
            ],
            'Concretagem de Escadas': [
                'Montagem de formas',
                'Armadura dos degraus',
                'Lançamento do concreto',
                'Acabamento dos degraus'
            ]
        }
        
        for i, servico_data in enumerate(servicos_concretagem):
            servico_nome = servico_data['nome']
            if servico_nome in subatividades_por_servico:
                for sub_nome in subatividades_por_servico[servico_nome]:
                    subatividade = SubAtividade(
                        nome=sub_nome,
                        servico_id=servicos_ids[i],
                        admin_id=10
                    )
                    db.session.add(subatividade)
        
        db.session.commit()
        print(f"   ✅ Subatividades criadas para todos os serviços")
        
        # 4. Criar RDO exemplo para testar
        # Buscar um usuário funcionário Vale Verde
        usuario_funcionario = Usuario.query.filter_by(
            tipo_usuario=TipoUsuario.FUNCIONARIO,
            admin_id=10,
            ativo=True
        ).first()
        
        if not usuario_funcionario:
            print("   ⚠️ Nenhum usuário funcionário Vale Verde encontrado para criar RDO")
            print("   ℹ️ Use a página de Acessos para criar um funcionário com login")
        else:
            # Criar RDO de exemplo
            numero_rdo = f"RDO-{obra.codigo}-{date.today().strftime('%Y%m%d')}-001"
            rdo = RDO(
                numero_rdo=numero_rdo,
                obra_id=obra.id,
                data_relatorio=date.today(),
                tempo_manha='Ensolarado',
                tempo_tarde='Ensolarado', 
                tempo_noite='Nublado',
                observacoes_meteorologicas='Clima favorável para concretagem',
                comentario_geral='Início da concretagem da fundação. Equipe de 8 funcionários trabalhando. Concretagem programada para blocos B1 a B5.',
                criado_por_id=usuario_funcionario.id,
                status='Finalizado'
            )
            
            db.session.add(rdo)
            db.session.commit()
            
            print(f"   ✅ RDO criado por: {usuario_funcionario.nome}")
            print(f"      Número: {rdo.numero_rdo}")
            print(f"      Data: {rdo.data_relatorio}")
            print(f"      Tempo: {rdo.tempo_manha}/{rdo.tempo_tarde}/{rdo.tempo_noite}")
            
        print(f"\n✅ OBRA DE CONCRETAGEM VALE VERDE CRIADA COM SUCESSO!")
        print(f"\n=== DADOS PARA TESTE ===")
        print(f"Obra: {obra.nome}")
        print(f"ID da Obra: {obra.id}")
        print(f"Serviços: {len(servicos_concretagem)} serviços de concretagem")
        print(f"Admin ID: 10 (Vale Verde)")
        
        if usuario_funcionario:
            print(f"RDO criado por: {usuario_funcionario.username}")
            print(f"Login funcionário: {usuario_funcionario.username}/123456")
        
        print(f"\n=== COMO TESTAR ===")
        print(f"1. Login como Vale Verde: valeverde/admin123")
        print(f"   - Verificar se obra aparece na lista de obras")
        print(f"   - Verificar se RDO aparece na página de RDOs")
        print(f"")
        if usuario_funcionario:
            print(f"2. Login como funcionário: {usuario_funcionario.username}/123456")
            print(f"   - Criar novo RDO na obra de concretagem")
            print(f"   - Verificar se aparece no perfil do funcionário")
            print(f"   - Fazer logout e entrar como admin para verificar")
        else:
            print(f"2. Criar funcionário com acesso em 'Configurações > Acessos'")
            print(f"   - Depois testar criação de RDO")

if __name__ == "__main__":
    criar_obra_concretagem()