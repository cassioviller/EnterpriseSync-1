#!/usr/bin/env python3

from main import app
from models import *
from datetime import date, datetime, timedelta
import random

def criar_dados_simples():
    with app.app_context():
        try:
            print("🚀 CRIANDO DADOS DE TESTE SIMPLES")
            print("Verificando existência de dados duplicados...")
            
            # Usar CPFs únicos baseados em timestamp
            import time
            timestamp_suffix = str(int(time.time()))[-4:]  # Últimos 4 dígitos do timestamp
            
            # ====== FUNCIONÁRIOS ======
            print("\n👥 CRIANDO FUNCIONÁRIOS:")
            funcionarios_criados = []
            
            funcionarios_data = [
                {"nome": "Lucas Pereira Silva", "cpf": "800.741.01-01", "salario": 4200.00},
                {"nome": "Marina Santos Costa", "cpf": "800.742.01-02", "salario": 3900.00},
                {"nome": "Rafael Oliveira", "cpf": "800.743.01-03", "salario": 3600.00},
                {"nome": "Juliana Ferreira", "cpf": "800.744.01-04", "salario": 4100.00},
                {"nome": "Carlos Eduardo", "cpf": "800.745.01-05", "salario": 3700.00}
            ]
            
            for i, func_data in enumerate(funcionarios_data, 1):
                funcionario = Funcionario(
                    codigo=f"T{i:03d}",
                    nome=func_data["nome"],
                    cpf=func_data["cpf"],
                    data_admissao=date.today(),
                    salario=func_data["salario"],
                    admin_id=10
                )
                db.session.add(funcionario)
                funcionarios_criados.append(funcionario)
                print(f"   ✓ {func_data['nome']}")
            
            # ====== OBRAS ======
            print("\n🏗️ CRIANDO OBRAS:")
            obras_criadas = []
            
            obras_data = [
                {"nome": f"Obra Teste {timestamp_suffix} - Fase A", "endereco": "Rua das Flores, 100"},
                {"nome": f"Obra Teste {timestamp_suffix} - Fase B", "endereco": "Av. Principal, 200"}
            ]
            
            for i, obra_data in enumerate(obras_data, 1):
                obra = Obra(
                    codigo=f"OBR{i:03d}",
                    nome=obra_data["nome"],
                    endereco=obra_data["endereco"],
                    cliente_nome="Cliente Teste",
                    data_inicio=date.today(),
                    status="Em andamento",
                    admin_id=10
                )
                db.session.add(obra)
                obras_criadas.append(obra)
                print(f"   ✓ {obra_data['nome']}")
            
            db.session.commit()
            
            # ====== RDOs ======
            print("\n📊 CRIANDO RDOs:")
            
            rdo = RDO(
                numero_rdo=f"RDO-TESTE-{timestamp_suffix}",
                data_relatorio=date.today(),
                obra_id=obras_criadas[0].id,
                criado_por_id=10,
                status="Em andamento",
                comentario_geral="RDO de teste para validação do sistema",
                admin_id=10
            )
            db.session.add(rdo)
            db.session.commit()
            
            # Alocar funcionários no RDO
            for i, funcionario in enumerate(funcionarios_criados[:3]):
                mao_obra = RDOMaoObra(
                    rdo_id=rdo.id,
                    funcionario_id=funcionario.id,
                    funcao_exercida=f"Função Teste {i+1}",
                    horas_trabalhadas=8.0
                )
                db.session.add(mao_obra)
                print(f"   ✓ RDO: {funcionario.nome} (8h)")
            
            db.session.commit()
            
            print(f"""
✅ DADOS DE TESTE CRIADOS COM SUCESSO!

📊 RESUMO:
   👥 {len(funcionarios_criados)} Funcionários
   🏗️ {len(obras_criadas)} Obras
   📋 1 RDO ativo
   
🎯 IDENTIFICAÇÃO DOS DADOS:
   Sufixo timestamp: {timestamp_suffix}
   CPFs: 800.{timestamp_suffix}.001-XX
   
✅ PRONTO PARA TESTES!
            """)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    criar_dados_simples()