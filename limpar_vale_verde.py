"""
Script para limpar todos os dados do Vale Verde e criar população nova
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import *
import os

def limpar_vale_verde():
    """Limpar dados do Vale Verde (admin_id = 10)"""
    
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
            print("🧹 Iniciando limpeza dos dados do Vale Verde...")
            
            # Remover RDOs e relacionamentos
            rdos_vv = RDO.query.filter_by(admin_id=10).all()
            for rdo in rdos_vv:
                # Remover subatividades do RDO
                RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
                # Remover mão de obra
                RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
                # Remover o RDO
                db.session.delete(rdo)
            
            # Remover funcionários e suas dependências
            funcionarios_vv = Funcionario.query.filter_by(admin_id=10).all()
            for func in funcionarios_vv:
                # Remover registros de ponto
                RegistroPonto.query.filter_by(funcionario_id=func.id).delete()
                # Remover outros custos
                OutroCusto.query.filter_by(funcionario_id=func.id).delete()
                # Remover alimentação se existir
                try:
                    RegistroAlimentacao.query.filter_by(funcionario_id=func.id).delete()
                except:
                    pass
                # Remover horários padrão
                try:
                    HorarioPadrao.query.filter_by(funcionario_id=func.id).delete()
                except:
                    pass
                # Remover uso de veículo
                try:
                    UsoVeiculo.query.filter_by(funcionario_id=func.id).delete()
                except:
                    pass
                # Remover funcionário
                db.session.delete(func)
            
            # Remover obras
            obras_vv = Obra.query.filter_by(admin_id=10).all()
            for obra in obras_vv:
                db.session.delete(obra)
            
            # Remover serviços da obra
            ServicoObra.query.filter_by(admin_id=10).delete()
            
            # Remover subatividades mestre
            SubatividadeMestre.query.filter_by(admin_id=10).delete()
            
            db.session.commit()
            print("✅ Limpeza concluída com sucesso!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na limpeza: {e}")
            import traceback
            traceback.print_exc()

def criar_populacao_teste():
    """Criar população nova para testes"""
    
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
            print("🏗️ Criando população de teste...")
            
            # 1. CRIAR FUNCIONÁRIOS
            funcionarios_data = [
                {"nome": "João Silva Santos", "cpf": "123.456.789-01", "salario": 8500.00},
                {"nome": "Maria Santos Oliveira", "cpf": "234.567.890-12", "salario": 7800.00},
                {"nome": "Pedro Oliveira Costa", "cpf": "345.678.901-23", "salario": 4200.00},
                {"nome": "Ana Costa Lima", "cpf": "456.789.012-34", "salario": 3800.00},
                {"nome": "Carlos Lima Silva", "cpf": "567.890.123-45", "salario": 2800.00}
            ]
            
            funcionarios = []
            for i, func_data in enumerate(funcionarios_data, 1):
                funcionario = Funcionario(
                    codigo=f"F{i:04d}",  # F0001, F0002, etc
                    nome=func_data["nome"],
                    cpf=func_data["cpf"],
                    data_admissao=date.today(),
                    salario=func_data["salario"],
                    admin_id=10
                )
                db.session.add(funcionario)
                funcionarios.append(funcionario)
                print(f"   ✓ Funcionário: {func_data['nome']}")
            
            # 2. CRIAR OBRAS
            obras_data = [
                {"nome": "Galpão Industrial ABC", "endereco": "Rua Industrial, 100", "cliente": "Empresa ABC Ltda"},
                {"nome": "Residencial Bela Vista", "endereco": "Av. Principal, 500", "cliente": "Construtora XYZ"},
                {"nome": "Reforma Comercial", "endereco": "Centro, 200", "cliente": "Loja 123"}
            ]
            
            obras = []
            for i, obra_data in enumerate(obras_data, 1):
                obra = Obra(
                    nome=obra_data["nome"],
                    codigo=f"OBR{i:03d}",  # OBR001, OBR002, etc
                    endereco=obra_data["endereco"],
                    cliente_nome=obra_data["cliente"],  # Usar cliente_nome em vez de cliente
                    data_inicio=date.today(),
                    admin_id=10
                )
                db.session.add(obra)
                obras.append(obra)
                print(f"   ✓ Obra: {obra_data['nome']}")
            
            # 3. CRIAR SERVIÇOS
            servicos_data = [
                {"nome": "Estrutura Metálica", "descricao": "Montagem de estruturas em aço"},
                {"nome": "Soldagem Especializada", "descricao": "Soldagem de peças estruturais"},
                {"nome": "Pintura Industrial", "descricao": "Pintura anticorrosiva e acabamento"},
                {"nome": "Montagem Mecânica", "descricao": "Instalação de equipamentos"}
            ]
            
            servicos = []
            for servico_data in servicos_data:
                servico = Servico(
                    nome=servico_data["nome"],
                    descricao=servico_data["descricao"]
                )
                db.session.add(servico)
                servicos.append(servico)
                print(f"   ✓ Serviço: {servico_data['nome']}")
            
            db.session.commit()  # Commit para ter IDs
            
            # 4. CRIAR SUBATIVIDADES MESTRE (realistas)
            subatividades_por_servico = {
                servicos[0].id: ["Preparação da base", "Montagem de pilares", "Instalação de vigas", "Contraventamento"],
                servicos[1].id: ["Preparação das peças", "Soldagem de topo", "Soldagem de filete", "Inspeção visual"],
                servicos[2].id: ["Preparação da superfície", "Primer anticorrosivo", "Tinta intermediária", "Tinta de acabamento"],
                servicos[3].id: ["Posicionamento", "Fixação mecânica", "Alinhamento", "Teste funcional"]
            }
            
            for servico_id, subatividades in subatividades_por_servico.items():
                for nome_sub in subatividades:
                    subatividade = SubatividadeMestre(
                        nome=nome_sub,
                        servico_id=servico_id,
                        admin_id=10
                    )
                    db.session.add(subatividade)
                    print(f"      → {nome_sub}")
            
            # 5. VINCULAR SERVIÇOS ÀS OBRAS
            for i, obra in enumerate(obras):
                # Cada obra terá 2-3 serviços diferentes
                servicos_obra = servicos[i:i+2]  # 2 serviços por obra
                for servico in servicos_obra:
                    servico_obra = ServicoObra(
                        servico_id=servico.id,
                        obra_id=obra.id,
                        admin_id=10
                    )
                    db.session.add(servico_obra)
                    print(f"   ✓ {obra.nome} ← {servico.nome}")
            
            db.session.commit()
            print("✅ População de teste criada com sucesso!")
            
            # Estatísticas finais
            total_funcionarios = Funcionario.query.filter_by(admin_id=10).count()
            total_obras = Obra.query.filter_by(admin_id=10).count()
            total_servicos = len(servicos)
            total_subatividades = SubatividadeMestre.query.filter_by(admin_id=10).count()
            
            print(f"""
📊 RESUMO DA POPULAÇÃO CRIADA:
   • {total_funcionarios} Funcionários
   • {total_obras} Obras 
   • {total_servicos} Serviços
   • {total_subatividades} Subatividades
            """)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na criação: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Iniciando processo de limpeza e população...")
    limpar_vale_verde()
    criar_populacao_teste()
    print("🎉 Processo concluído!")