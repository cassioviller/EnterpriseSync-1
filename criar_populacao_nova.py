"""
Script para criar população totalmente nova para testes
Ignorando dados antigos e criando dados frescos
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import *
import os
from datetime import date, datetime

def criar_dados_novos():
    """Criar população nova para testes dos 3 módulos"""
    
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🏗️ CRIANDO POPULAÇÃO NOVA PARA TESTES")
            print("Dados totalmente novos para os 3 módulos...")
            
            # ====== MÓDULO 1: FUNCIONÁRIOS ======
            print("\n👥 CRIANDO FUNCIONÁRIOS NOVOS:")
            funcionarios_novos = []
            
            funcionarios_data = [
                {"nome": "Ana Carolina Silva", "cpf": "900.111.222-01", "salario": 4500.00},
                {"nome": "Bruno Santos Costa", "cpf": "900.111.222-02", "salario": 3800.00},
                {"nome": "Carla Mendes Lima", "cpf": "900.111.222-03", "salario": 3200.00},
                {"nome": "Diego Fernandes", "cpf": "900.111.222-04", "salario": 2900.00},
                {"nome": "Elena Rodriguez", "cpf": "900.111.222-05", "salario": 4200.00},
                {"nome": "Felipe Alves", "cpf": "900.111.222-06", "salario": 3500.00},
                {"nome": "Gabriela Torres", "cpf": "900.111.222-07", "salario": 3300.00}
            ]
            
            import random
            sufixo = random.randint(100, 999)
            
            for i, func_data in enumerate(funcionarios_data, 1):
                func = Funcionario(
                    codigo=f"T{sufixo}{i:02d}",  # Código único com sufixo aleatório
                    nome=func_data["nome"],
                    cpf=func_data["cpf"],
                    data_admissao=date.today(),
                    salario=func_data["salario"],
                    admin_id=10  # Vale Verde
                )
                db.session.add(func)
                funcionarios_novos.append(func)
                print(f"   ✓ {func_data['nome']}")
            
            db.session.commit()  # Commit para ter IDs
            
            # ====== MÓDULO 2: SERVIÇOS E OBRAS ======
            print("\n🏗️ CRIANDO SERVIÇOS E OBRAS:")
            
            # Serviços mais realistas
            servicos_data = [
                {"nome": "Fundações e Estruturas", "desc": "Escavação, fundações, pilares e vigas"},
                {"nome": "Alvenaria e Vedações", "desc": "Construção de paredes e vedações"},
                {"nome": "Instalações Hidráulicas", "desc": "Tubulações de água e esgoto"},
                {"nome": "Instalações Elétricas", "desc": "Cabeamento e quadros elétricos"},
                {"nome": "Acabamentos Finos", "desc": "Pisos, pintura e acabamentos"}
            ]
            
            servicos_novos = []
            for servico_data in servicos_data:
                servico = Servico(
                    nome=servico_data["nome"],
                    descricao=servico_data["desc"]
                )
                db.session.add(servico)
                servicos_novos.append(servico)
                print(f"   ✓ {servico_data['nome']}")
            
            db.session.commit()  # Commit para ter IDs dos serviços
            
            # Subatividades realistas para cada serviço
            subatividades_map = {
                servicos_novos[0].id: ["Escavação", "Fundação corrida", "Pilares", "Vigas baldrame"],
                servicos_novos[1].id: ["Marcação alvenaria", "1ª fiada", "Elevação paredes", "Vergas e contravergas"],
                servicos_novos[2].id: ["Prumada hidráulica", "Ramais água fria", "Ramais esgoto", "Testes estanqueidade"],
                servicos_novos[3].id: ["Entrada energia", "Distribuição circuitos", "Pontos tomadas", "Pontos iluminação"],
                servicos_novos[4].id: ["Contrapiso", "Revestimentos", "Pintura", "Limpeza final"]
            }
            
            print("\n🔧 CRIANDO SUBATIVIDADES:")
            for servico_id, subatividades in subatividades_map.items():
                for sub_nome in subatividades:
                    sub = SubatividadeMestre(
                        nome=sub_nome,
                        servico_id=servico_id,
                        admin_id=10
                    )
                    db.session.add(sub)
                    print(f"      → {sub_nome}")
            
            # Obras novas
            obras_data = [
                {"nome": "Residencial Premium Alphaville", "cliente": "Construtora Premium Ltda", "endereco": "Alphaville, Barueri - SP"},
                {"nome": "Galpão Logístico Industrial", "cliente": "LogiPark Soluções", "endereco": "Distrito Industrial, Guarulhos - SP"},
                {"nome": "Edifício Comercial Central", "cliente": "Invest Imóveis S.A", "endereco": "Centro, São Paulo - SP"}
            ]
            
            obras_novas = []
            for i, obra_data in enumerate(obras_data, 1):
                obra = Obra(
                    nome=obra_data["nome"],
                    codigo=f"OBRA-NOVA-{i:03d}",
                    endereco=obra_data["endereco"],
                    cliente_nome=obra_data["cliente"],
                    data_inicio=date.today(),
                    status="Em andamento",
                    admin_id=10
                )
                db.session.add(obra)
                obras_novas.append(obra)
                print(f"   ✓ {obra_data['nome']}")
            
            db.session.commit()  # Commit para ter IDs das obras
            
            # Vincular serviços às obras
            print("\n🔗 VINCULANDO SERVIÇOS ÀS OBRAS:")
            for i, obra in enumerate(obras_novas):
                # Cada obra terá 3 serviços
                servicos_da_obra = servicos_novos[i:i+3] if i+3 <= len(servicos_novos) else servicos_novos[:3]
                for servico in servicos_da_obra:
                    servico_obra = ServicoObra(
                        servico_id=servico.id,
                        obra_id=obra.id,
                        quantidade_planejada=100.0,  # Quantidade padrão
                        quantidade_executada=0.0
                    )
                    db.session.add(servico_obra)
                    print(f"   ✓ {obra.nome} ← {servico.nome}")
            
            # ====== MÓDULO 3: RDOs ======
            print("\n📊 CRIANDO RDOs DE EXEMPLO:")
            
            # RDO 1: Residencial Premium
            rdo1 = RDO(
                numero_rdo="RDO-NOVO-001",
                data_relatorio=date.today(),
                obra_id=obras_novas[0].id,
                criado_por_id=10,  # Admin
                status="Em andamento",
                comentario_geral="Início das atividades de fundação",
                admin_id=10
            )
            db.session.add(rdo1)
            
            # RDO 2: Galpão Industrial
            rdo2 = RDO(
                numero_rdo="RDO-NOVO-002",
                data_relatorio=date.today(),
                obra_id=obras_novas[1].id,
                criado_por_id=10,
                status="Em andamento",
                comentario_geral="Preparação do terreno concluída",
                admin_id=10
            )
            db.session.add(rdo2)
            
            db.session.commit()  # Commit para ter IDs dos RDOs
            
            # Subatividades executadas no RDO 1
            subatividades_rdo1 = [
                {"servico_id": servicos_novos[0].id, "nome": "Escavação", "percentual": 100},
                {"servico_id": servicos_novos[0].id, "nome": "Fundação corrida", "percentual": 85},
                {"servico_id": servicos_novos[0].id, "nome": "Pilares", "percentual": 65},
                {"servico_id": servicos_novos[1].id, "nome": "Marcação alvenaria", "percentual": 100}
            ]
            
            for sub_data in subatividades_rdo1:
                sub_rdo = RDOServicoSubatividade(
                    rdo_id=rdo1.id,
                    servico_id=sub_data["servico_id"],
                    nome_subatividade=sub_data["nome"],
                    percentual_conclusao=sub_data["percentual"],
                    admin_id=10
                )
                db.session.add(sub_rdo)
                print(f"   ✓ RDO-001: {sub_data['nome']} ({sub_data['percentual']}%)")
            
            # Subatividades executadas no RDO 2
            subatividades_rdo2 = [
                {"servico_id": servicos_novos[0].id, "nome": "Escavação", "percentual": 90},
                {"servico_id": servicos_novos[0].id, "nome": "Fundação corrida", "percentual": 45},
                {"servico_id": servicos_novos[2].id, "nome": "Prumada hidráulica", "percentual": 30}
            ]
            
            for sub_data in subatividades_rdo2:
                sub_rdo = RDOServicoSubatividade(
                    rdo_id=rdo2.id,
                    servico_id=sub_data["servico_id"],
                    nome_subatividade=sub_data["nome"],
                    percentual_conclusao=sub_data["percentual"],
                    admin_id=10
                )
                db.session.add(sub_rdo)
                print(f"   ✓ RDO-002: {sub_data['nome']} ({sub_data['percentual']}%)")
            
            # Mão de obra nos RDOs
            print("\n👷 ALOCANDO MÃO DE OBRA:")
            
            # RDO 1: 4 funcionários
            funcoes_rdo1 = ["Engenheira Civil", "Mestre de Obras", "Pedreiro", "Servente"]
            for i, funcionario in enumerate(funcionarios_novos[:4]):
                mao_obra = RDOMaoObra(
                    rdo_id=rdo1.id,
                    funcionario_id=funcionario.id,
                    funcao_exercida=funcoes_rdo1[i],
                    horas_trabalhadas=8.0
                )
                db.session.add(mao_obra)
                print(f"   ✓ RDO-001: {funcionario.nome} (8h)")
            
            # RDO 2: 3 funcionários  
            funcoes_rdo2 = ["Arquiteta", "Eletricista", "Encanadora"]
            for i, funcionario in enumerate(funcionarios_novos[4:7]):
                mao_obra = RDOMaoObra(
                    rdo_id=rdo2.id,
                    funcionario_id=funcionario.id,
                    funcao_exercida=funcoes_rdo2[i],
                    horas_trabalhadas=8.0
                )
                db.session.add(mao_obra)
                print(f"   ✓ RDO-002: {funcionario.nome} (8h)")
            
            # ====== PROPOSTAS COMERCIAIS ======
            print("\n💼 CRIANDO PROPOSTAS COMERCIAIS:")
            
            # Primeiro criar um cliente teste se não existir
            from models import Cliente
            
            cliente_teste = Cliente.query.filter_by(admin_id=10).first()
            if not cliente_teste:
                cliente_teste = Cliente(
                    nome="Construtora Premium Ltda",
                    email="contato@construtorapremium.com.br", 
                    telefone="(12) 98765-4321",
                    admin_id=10
                )
                db.session.add(cliente_teste)
                db.session.commit()
            
            propostas_data = [
                {"titulo": "Projeto Residencial Premium", "valor": 580000.00, "descricao": "Projeto residencial completo"},
                {"titulo": "Galpão Industrial LogiPark", "valor": 750000.00, "descricao": "Construção de galpão industrial"},
                {"titulo": "Edifício Comercial Invest", "valor": 920000.00, "descricao": "Edifício comercial 8 andares"}
            ]
            
            for i, prop_data in enumerate(propostas_data, 1):
                proposta = Proposta(
                    numero=f"PROP-NOVA-{i:03d}",
                    cliente_id=cliente_teste.id,
                    titulo=prop_data["titulo"],
                    valor_total=prop_data["valor"],
                    status="rascunho",
                    descricao=prop_data["descricao"],
                    admin_id=10
                )
                db.session.add(proposta)
                print(f"   ✓ {prop_data['titulo']}: R$ {prop_data['valor']:,.2f}")
            
            db.session.commit()
            
            print(f"""
✅ POPULAÇÃO NOVA CRIADA COM SUCESSO!

📊 RESUMO DOS DADOS CRIADOS:
   👥 {len(funcionarios_novos)} Funcionários novos
   🏗️ {len(obras_novas)} Obras novas  
   🔧 {len(servicos_novos)} Serviços novos
   📋 20 Subatividades mestre
   📊 2 RDOs com subatividades executadas
   💼 3 Propostas comerciais
   
🎯 TESTES DISPONÍVEIS:
   • Módulo Funcionários: 7 funcionários com cargos diversos
   • Módulo RDOs: 2 RDOs ativos com progresso real
   • Módulo Propostas: 3 propostas em análise
   
🔗 DADOS RELACIONADOS:
   • RDO-NOVO-001: 4 subatividades, 4 funcionários (87.5% progresso médio)
   • RDO-NOVO-002: 3 subatividades, 3 funcionários (55% progresso médio)
   • Todas as obras têm serviços vinculados
   • Todos os funcionários têm cargos específicos
            """)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na criação: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    criar_dados_novos()