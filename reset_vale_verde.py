"""
Script para resetar completamente os dados do Vale Verde e criar população nova
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import *
import os
from datetime import date, datetime

def reset_complete():
    """Resetar dados completamente usando TRUNCATE para ignorar constraints"""
    
    # Criar aplicação temporária
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🗑️ Resetando dados do Vale Verde...")
            
            # Usar SQL direto para remover constraints temporariamente
            db.session.execute(text("SET session_replication_role = replica;"))
            
            # Remover dados do Vale Verde (admin_id = 10) por tabela
            tables_to_clean = [
                'rdo_servico_subatividade',
                'rdo_mao_obra', 
                'rdo',
                'registro_ponto',
                'outro_custo',
                'registro_alimentacao',
                'horarios_padrao',
                'uso_veiculo',
                'funcionario',
                'proposta_itens',
                'propostas_comerciais',
                'custo_obra',
                'servico_obra',
                'obra',
                'subatividade_mestre'
            ]
            
            for table in tables_to_clean:
                try:
                    db.session.execute(text(f"DELETE FROM {table} WHERE admin_id = 10"))
                    print(f"   ✓ Limpeza da tabela {table}")
                except Exception as e:
                    print(f"   ⚠️  Erro na tabela {table}: {e}")
            
            # Restaurar constraints
            db.session.execute(text("SET session_replication_role = DEFAULT;"))
            db.session.commit()
            
            print("✅ Limpeza concluída!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na limpeza: {e}")
            import traceback
            traceback.print_exc()

def criar_populacao_nova():
    """Criar população totalmente nova para testes"""
    
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🏗️ Criando população nova para testes...")
            
            # 1. FUNCIONÁRIOS LIMPOS
            funcionarios_data = [
                {"nome": "João Silva", "cpf": "100.200.300-01"},
                {"nome": "Maria Santos", "cpf": "100.200.300-02"}, 
                {"nome": "Pedro Costa", "cpf": "100.200.300-03"},
                {"nome": "Ana Lima", "cpf": "100.200.300-04"},
                {"nome": "Carlos Oliveira", "cpf": "100.200.300-05"}
            ]
            
            funcionarios_criados = []
            for i, func_data in enumerate(funcionarios_data, 1):
                func = Funcionario(
                    codigo=f"TESTE{i:03d}",
                    nome=func_data["nome"],
                    cpf=func_data["cpf"],
                    data_admissao=date.today(),
                    salario=5000.00,
                    admin_id=10
                )
                db.session.add(func)
                funcionarios_criados.append(func)
                print(f"   ✓ {func_data['nome']}")
            
            # 2. OBRAS LIMPAS
            obras_data = [
                {"nome": "Projeto Industrial Alpha", "cliente": "Empresa Alpha Ltd"},
                {"nome": "Residencial Beta", "cliente": "Construtora Beta"},
                {"nome": "Comercial Gamma", "cliente": "Grupo Gamma"}
            ]
            
            obras_criadas = []
            for i, obra_data in enumerate(obras_data, 1):
                obra = Obra(
                    nome=obra_data["nome"],
                    codigo=f"TESTE{i:03d}",
                    endereco=f"Endereço Teste {i}",
                    cliente_nome=obra_data["cliente"],
                    data_inicio=date.today(),
                    admin_id=10
                )
                db.session.add(obra)
                obras_criadas.append(obra)
                print(f"   ✓ {obra_data['nome']}")
            
            # 3. SERVIÇOS LIMPOS
            servicos_data = [
                {"nome": "Estrutura de Concreto", "desc": "Concretagem e estruturas"},
                {"nome": "Alvenaria", "desc": "Construção de paredes"},
                {"nome": "Instalações Elétricas", "desc": "Sistemas elétricos"},
                {"nome": "Acabamentos", "desc": "Pinturas e acabamentos"}
            ]
            
            servicos_criados = []
            for servico_data in servicos_data:
                servico = Servico(
                    nome=servico_data["nome"],
                    descricao=servico_data["desc"]
                )
                db.session.add(servico)
                servicos_criados.append(servico)
                print(f"   ✓ {servico_data['nome']}")
            
            db.session.commit()  # Commit para ter IDs
            
            # 4. SUBATIVIDADES REALISTAS
            subatividades_por_servico = {
                servicos_criados[0].id: ["Fundação", "Pilares", "Vigas", "Laje"],
                servicos_criados[1].id: ["Marcação", "Elevação", "Vergas", "Contravergas"],
                servicos_criados[2].id: ["Tubulação", "Fiação", "Quadros", "Testes"],
                servicos_criados[3].id: ["Massa corrida", "Pintura primer", "Pintura final", "Limpeza"]
            }
            
            for servico_id, subatividades in subatividades_por_servico.items():
                for sub_nome in subatividades:
                    sub = SubatividadeMestre(
                        nome=sub_nome,
                        servico_id=servico_id,
                        admin_id=10
                    )
                    db.session.add(sub)
                    print(f"      → {sub_nome}")
            
            # 5. VINCULAR SERVIÇOS ÀS OBRAS
            for i, obra in enumerate(obras_criadas):
                # Cada obra terá 2 serviços
                servicos_obra = servicos_criados[i:i+2]
                for servico in servicos_obra:
                    servico_obra = ServicoObra(
                        servico_id=servico.id,
                        obra_id=obra.id,
                        admin_id=10
                    )
                    db.session.add(servico_obra)
                    print(f"   ✓ {obra.nome} ← {servico.nome}")
            
            # 6. CRIAR RDO DE EXEMPLO
            rdo_exemplo = RDO(
                numero_rdo="RDO-NOVO-001",
                data_relatorio=date.today(),
                obra_id=obras_criadas[0].id,
                criado_por_id=10,  # Admin
                status="Em andamento",
                admin_id=10
            )
            db.session.add(rdo_exemplo)
            db.session.commit()
            
            # 7. SUBATIVIDADES DO RDO
            subatividades_rdo = [
                {"servico_id": servicos_criados[0].id, "nome": "Fundação", "percentual": 90},
                {"servico_id": servicos_criados[0].id, "nome": "Pilares", "percentual": 75},
                {"servico_id": servicos_criados[1].id, "nome": "Marcação", "percentual": 100},
                {"servico_id": servicos_criados[1].id, "nome": "Elevação", "percentual": 60}
            ]
            
            for sub_data in subatividades_rdo:
                sub_rdo = RDOServicoSubatividade(
                    rdo_id=rdo_exemplo.id,
                    servico_id=sub_data["servico_id"],
                    nome_subatividade=sub_data["nome"],
                    percentual_conclusao=sub_data["percentual"],
                    admin_id=10
                )
                db.session.add(sub_rdo)
            
            # 8. MÃO DE OBRA DO RDO
            for i, funcionario in enumerate(funcionarios_criados[:3]):
                mao_obra = RDOMaoObra(
                    rdo_id=rdo_exemplo.id,
                    funcionario_id=funcionario.id,
                    funcao_exercida=f"Função {i+1}",
                    horas_trabalhadas=8.0
                )
                db.session.add(mao_obra)
            
            db.session.commit()
            print("✅ População nova criada com sucesso!")
            
            # Estatísticas
            print(f"""
📊 NOVA POPULAÇÃO CRIADA:
   • {len(funcionarios_criados)} Funcionários
   • {len(obras_criadas)} Obras
   • {len(servicos_criados)} Serviços
   • 16 Subatividades mestre
   • 1 RDO de exemplo com 4 subatividades executadas
   • 3 funcionários alocados no RDO
            """)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na criação: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🚀 RESETAR VALE VERDE COMPLETO")
    reset_complete()
    criar_populacao_nova()
    print("🎉 Reset completo finalizado!")