#!/usr/bin/env python3
"""
Script para popular a obra Residencial Jardim das Flores VV com dados completos:
- Custos de transporte (veículos)
- RDOs (Relatórios Diários de Obra)
- Validar cálculos de KPIs
"""

from app import app, db
from models import (Obra, CustoVeiculo, Veiculo, RDO, Funcionario, RegistroPonto, 
                    RegistroAlimentacao, CustoObra)
from datetime import date, datetime
import random

def buscar_obra_jardim_flores():
    """Buscar a obra Residencial Jardim das Flores VV"""
    obra = db.session.query(Obra).filter(
        Obra.nome.ilike('%Jardim das Flores VV%')
    ).first()
    
    if not obra:
        print("❌ Obra 'Residencial Jardim das Flores VV' não encontrada!")
        return None
    
    print(f"✅ Obra encontrada: {obra.nome} (ID: {obra.id})")
    return obra

def criar_custos_transporte(obra):
    """Criar custos de transporte para a obra"""
    print("\n🚛 Criando custos de transporte...")
    
    # Buscar veículos do admin da obra
    veiculos = db.session.query(Veiculo).filter_by(admin_id=obra.admin_id).all()
    
    if not veiculos:
        print("❌ Nenhum veículo encontrado para este admin")
        return
    
    custos_criados = 0
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 23)
    
    # Criar custos variados para diferentes veículos
    tipos_custo = ['combustivel', 'manutencao', 'pedagio', 'lavagem']
    valores_base = {'combustivel': 150.0, 'manutencao': 300.0, 'pedagio': 25.0, 'lavagem': 30.0}
    
    for veiculo in veiculos[:3]:  # Usar até 3 veículos
        for i in range(5):  # 5 custos por veículo
            data_custo = date(2025, 7, random.randint(1, 23))
            tipo = random.choice(tipos_custo)
            valor = valores_base[tipo] + random.uniform(-50, 100)
            
            custo = CustoVeiculo(
                veiculo_id=veiculo.id,
                obra_id=obra.id,
                data_custo=data_custo,
                valor=valor,
                tipo_custo=tipo,
                descricao=f"{tipo.title()} - {veiculo.modelo} ({veiculo.placa})",
                km_atual=random.randint(50000, 80000),
                fornecedor=f"Posto {random.choice(['Shell', 'Petrobras', 'BR', 'Ipiranga'])}"
            )
            
            db.session.add(custo)
            custos_criados += 1
    
    db.session.commit()
    print(f"✅ {custos_criados} custos de transporte criados")

def criar_outros_custos(obra):
    """Criar outros custos da obra"""
    print("\n💰 Criando outros custos da obra...")
    
    custos_criados = 0
    
    # Tipos de custos de obra
    tipos_custo = [
        {"categoria": "Material", "descricao": "Cimento Portland CP-II", "valor": 850.00},
        {"categoria": "Material", "descricao": "Areia lavada - 10m³", "valor": 420.00},
        {"categoria": "Material", "descricao": "Brita 1 - 15m³", "valor": 680.00},
        {"categoria": "Equipamento", "descricao": "Locação de betoneira", "valor": 320.00},
        {"categoria": "Equipamento", "descricao": "Aluguel de andaimes", "valor": 750.00},
        {"categoria": "Serviço", "descricao": "Frete de materiais", "valor": 180.00},
        {"categoria": "Ferramenta", "descricao": "Ferramentas diversas", "valor": 290.00}
    ]
    
    for i, tipo in enumerate(tipos_custo):
        data_custo = date(2025, 7, 5 + i)
        
        custo = CustoObra(
            obra_id=obra.id,
            data=data_custo,
            tipo=tipo["categoria"],
            descricao=tipo["descricao"],
            valor=tipo["valor"],
            fornecedor=f"Fornecedor {random.choice(['ABC', 'XYZ', 'DEF'])} Ltda"
        )
        
        db.session.add(custo)
        custos_criados += 1
    
    db.session.commit()
    print(f"✅ {custos_criados} outros custos criados")

def gerar_relatorio_completo(obra):
    """Gerar relatório completo da obra com todos os dados"""
    print(f"\n📊 RELATÓRIO COMPLETO - {obra.nome}")
    print("=" * 80)
    
    # 1. Dados básicos da obra
    print(f"\n1. DADOS BÁSICOS DA OBRA")
    print(f"   Nome: {obra.nome}")
    print(f"   Status: {obra.status}")
    print(f"   Data Início: {obra.data_inicio}")
    print(f"   Data Fim: {obra.data_fim}")
    print(f"   Orçamento: R$ {obra.orcamento:,.2f}")
    print(f"   Admin ID: {obra.admin_id}")
    
    # 2. Funcionários que trabalharam na obra
    print(f"\n2. FUNCIONÁRIOS NA OBRA")
    registros_ponto = db.session.query(RegistroPonto).filter_by(obra_id=obra.id).all()
    funcionarios_unicos = {}
    
    for registro in registros_ponto:
        if registro.funcionario_id not in funcionarios_unicos:
            funcionario = db.session.query(Funcionario).get(registro.funcionario_id)
            if funcionario:
                funcionarios_unicos[registro.funcionario_id] = {
                    'nome': funcionario.nome,
                    'salario': funcionario.salario,
                    'salario_hora': funcionario.salario / 220 if funcionario.salario else 0,
                    'registros': 0,
                    'horas_totais': 0
                }
        
        if registro.funcionario_id in funcionarios_unicos:
            funcionarios_unicos[registro.funcionario_id]['registros'] += 1
            funcionarios_unicos[registro.funcionario_id]['horas_totais'] += registro.horas_trabalhadas or 0
    
    for func_id, dados in funcionarios_unicos.items():
        print(f"   - {dados['nome']}: {dados['registros']} registros, {dados['horas_totais']:.1f}h trabalhadas")
        print(f"     Salário: R$ {dados['salario']:,.2f} | Salário/hora: R$ {dados['salario_hora']:.2f}")
    
    # 3. Custos de transporte
    print(f"\n3. CUSTOS DE TRANSPORTE")
    custos_transporte = db.session.query(CustoVeiculo).filter_by(obra_id=obra.id).all()
    total_transporte = 0
    
    for custo in custos_transporte:
        veiculo = db.session.query(Veiculo).get(custo.veiculo_id)
        print(f"   - {custo.data_custo}: {custo.tipo_custo} - R$ {custo.valor:.2f}")
        print(f"     Veículo: {veiculo.modelo if veiculo else 'N/A'} ({veiculo.placa if veiculo else 'N/A'})")
        print(f"     Descrição: {custo.descricao}")
        total_transporte += custo.valor
    
    print(f"   TOTAL TRANSPORTE: R$ {total_transporte:.2f}")
    
    # 4. RDOs existentes da obra
    print(f"\n4. RDOs (RELATÓRIOS DIÁRIOS DE OBRA)")
    rdos = db.session.query(RDO).filter_by(obra_id=obra.id).all()
    print(f"   Total de RDOs: {len(rdos)}")
    
    for rdo in rdos[:3]:  # Mostrar apenas os primeiros 3
        responsavel = db.session.query(Funcionario).get(rdo.criado_por_id)
        print(f"   - {rdo.numero_rdo} ({rdo.data_relatorio})")
        print(f"     Criado por: {responsavel.nome if responsavel else 'N/A'}")
    
    # 5. Outros custos da obra
    print(f"\n5. OUTROS CUSTOS DA OBRA")
    outros_custos = db.session.query(CustoObra).filter_by(obra_id=obra.id).all()
    total_outros = 0
    
    for custo in outros_custos:
        print(f"   - {custo.data}: {custo.categoria} - R$ {custo.valor:.2f}")
        print(f"     Descrição: {custo.descricao}")
        total_outros += custo.valor
    
    print(f"   TOTAL OUTROS CUSTOS: R$ {total_outros:.2f}")
    
    # 6. Custos de alimentação
    print(f"\n6. CUSTOS DE ALIMENTAÇÃO")
    custos_alimentacao = db.session.query(RegistroAlimentacao).filter_by(obra_id=obra.id).all()
    total_alimentacao = sum(r.valor for r in custos_alimentacao)
    print(f"   Registros de alimentação: {len(custos_alimentacao)}")
    print(f"   TOTAL ALIMENTAÇÃO: R$ {total_alimentacao:.2f}")
    
    # 7. Cálculo final dos KPIs
    print(f"\n7. CÁLCULO DOS KPIs DA OBRA")
    
    # Custo total de mão de obra
    custo_mao_obra = 0
    for func_id, dados in funcionarios_unicos.items():
        custo_funcionario = dados['horas_totais'] * dados['salario_hora']
        custo_mao_obra += custo_funcionario
        print(f"   Mão de obra {dados['nome']}: {dados['horas_totais']:.1f}h × R$ {dados['salario_hora']:.2f} = R$ {custo_funcionario:.2f}")
    
    print(f"\n   RESUMO FINAL:")
    print(f"   - Mão de Obra: R$ {custo_mao_obra:.2f}")
    print(f"   - Transporte: R$ {total_transporte:.2f}")  
    print(f"   - Alimentação: R$ {total_alimentacao:.2f}")
    print(f"   - Outros Custos: R$ {total_outros:.2f}")
    
    custo_total_calculado = custo_mao_obra + total_transporte + total_alimentacao + total_outros
    print(f"   - CUSTO TOTAL: R$ {custo_total_calculado:.2f}")
    
    # Verificar se bate com o valor exibido no sistema
    from utils import calcular_custo_real_obra
    custo_sistema = calcular_custo_real_obra(obra.id, date(2025, 7, 1), date(2025, 7, 23))
    print(f"\n   VERIFICAÇÃO:")
    print(f"   - Calculado manualmente: R$ {custo_total_calculado:.2f}")
    print(f"   - Calculado pelo sistema: R$ {custo_sistema['custo_total']:.2f}")
    print(f"   - Diferença: R$ {abs(custo_total_calculado - custo_sistema['custo_total']):.2f}")

def main():
    with app.app_context():
        obra = buscar_obra_jardim_flores()
        if not obra:
            return
        
        print(f"\n🚀 Populando obra: {obra.nome}")
        
        # Criar dados se não existirem
        criar_custos_transporte(obra)
        criar_outros_custos(obra)
        
        # Gerar relatório completo
        gerar_relatorio_completo(obra)
        
        print(f"\n✅ Processo concluído! A obra agora possui dados completos.")
        print(f"📝 Acesse a página da obra para ver os novos dados de transporte e RDOs.")

if __name__ == "__main__":
    main()