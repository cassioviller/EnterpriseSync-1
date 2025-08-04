#!/usr/bin/env python3
"""
🧪 TESTE: KPIs de Sábado com Dados de Exemplo
Criar dados similares ao Antonio para testar se o sistema funciona
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from kpis_engine import KPIsEngine
from datetime import date, datetime

def criar_funcionario_teste():
    """Criar funcionário de teste similar ao Antonio"""
    print("👤 CRIANDO FUNCIONÁRIO DE TESTE")
    print("=" * 50)
    
    # Verificar se já existe
    funcionario = Funcionario.query.filter_by(codigo='TESTE_ANTONIO').first()
    if funcionario:
        print(f"✅ Funcionário teste já existe: {funcionario.nome}")
        return funcionario
    
    # Criar novo funcionário
    funcionario = Funcionario(
        codigo='TESTE_ANTONIO',
        nome='Antonio Teste Silva',
        salario=2153.26,
        ativo=True,
        cargo='Auxiliar de Produção'
    )
    
    db.session.add(funcionario)
    db.session.commit()
    
    print(f"✅ Funcionário criado: {funcionario.nome} (ID: {funcionario.id})")
    return funcionario

def criar_registros_sabado_teste(funcionario_id):
    """Criar registros de sábado para teste"""
    print(f"\n📊 CRIANDO REGISTROS DE SÁBADO")
    print("=" * 50)
    
    # Limpar registros existentes
    RegistroPonto.query.filter_by(funcionario_id=funcionario_id).delete()
    
    registros = [
        # Registro normal (0.3h extras)
        {
            'data': date(2025, 7, 15),
            'tipo_registro': 'trabalho_normal',
            'horas_trabalhadas': 8.3,
            'horas_extras': 0.3,  # 0.3h extras normais
            'percentual_extras': 60.0
        },
        # Sábados trabalhados (7.9h extras total)
        {
            'data': date(2025, 7, 5),  # Sábado
            'tipo_registro': 'sabado_trabalhado',
            'horas_trabalhadas': 8.0,
            'horas_extras': 8.0,  # Todo sábado é extra
            'percentual_extras': 50.0
        },
        {
            'data': date(2025, 7, 12),  # Sábado  
            'tipo_registro': 'sabado_trabalhado',
            'horas_trabalhadas': 7.9,
            'horas_extras': 7.9,  # Todo sábado é extra
            'percentual_extras': 50.0
        }
    ]
    
    for reg_data in registros:
        registro = RegistroPonto(
            funcionario_id=funcionario_id,
            data=reg_data['data'],
            tipo_registro=reg_data['tipo_registro'],
            horas_trabalhadas=reg_data['horas_trabalhadas'],
            horas_extras=reg_data['horas_extras'],
            percentual_extras=reg_data['percentual_extras'],
            entrada=datetime.combine(reg_data['data'], datetime.min.time().replace(hour=7)),
            saida=datetime.combine(reg_data['data'], datetime.min.time().replace(hour=15, minute=30))
        )
        db.session.add(registro)
    
    db.session.commit()
    
    print(f"✅ Criados {len(registros)} registros:")
    for reg in registros:
        print(f"   {reg['data']} | {reg['tipo_registro']} | {reg['horas_extras']:.1f}h extras")
    
    # Calcular total esperado
    total_esperado = sum(reg['horas_extras'] for reg in registros)
    print(f"\n📈 TOTAL ESPERADO: {total_esperado:.1f}h (0.3 + 8.0 + 7.9)")
    
    return len(registros)

def testar_kpis_funcionario(funcionario_id):
    """Testar KPIs do funcionário"""
    print(f"\n🤖 TESTANDO KPIs")
    print("=" * 50)
    
    # Calcular KPIs
    engine = KPIsEngine()
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    kpis = engine.calcular_kpis_funcionario(funcionario_id, data_inicio, data_fim)
    
    print(f"📊 RESULTADO DOS KPIs:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    print(f"   Custo Mão de Obra: R$ {kpis['custo_mao_obra']:.2f}")
    
    # Análise
    if kpis['horas_extras'] >= 15.9:  # 0.3 + 8.0 + 7.9
        print(f"\n✅ TESTE PASSOU: Sábados estão sendo contabilizados!")
    else:
        print(f"\n❌ TESTE FALHOU: Faltam {15.9 - kpis['horas_extras']:.1f}h")
    
    return kpis

def verificar_registros_banco(funcionario_id):
    """Verificar registros no banco"""
    print(f"\n🗄️  VERIFICANDO BANCO DE DADOS")
    print("=" * 50)
    
    registros = RegistroPonto.query.filter_by(funcionario_id=funcionario_id).all()
    
    print(f"📊 REGISTROS NO BANCO ({len(registros)}):")
    total_extras_banco = 0
    for registro in registros:
        print(f"   {registro.data} | {registro.tipo_registro} | "
              f"Trab: {registro.horas_trabalhadas:.1f}h | Extras: {registro.horas_extras:.1f}h")
        total_extras_banco += registro.horas_extras or 0
    
    print(f"\n📈 TOTAL NO BANCO: {total_extras_banco:.1f}h")
    return total_extras_banco

if __name__ == "__main__":
    with app.app_context():
        print("🧪 TESTE COMPLETO - KPIs DE SÁBADO")
        print("=" * 80)
        
        # 1. Criar funcionário de teste
        funcionario = criar_funcionario_teste()
        
        # 2. Criar registros de teste
        criar_registros_sabado_teste(funcionario.id)
        
        # 3. Verificar no banco
        total_banco = verificar_registros_banco(funcionario.id)
        
        # 4. Testar KPIs
        kpis = testar_kpis_funcionario(funcionario.id)
        
        print(f"\n🎯 CONCLUSÃO:")
        print(f"   Registros no banco: {total_banco:.1f}h")
        print(f"   KPI calculado: {kpis['horas_extras']:.1f}h")
        print(f"   Match: {'✅ SIM' if abs(total_banco - kpis['horas_extras']) < 0.1 else '❌ NÃO'}")
        
        if abs(total_banco - kpis['horas_extras']) < 0.1 and kpis['horas_extras'] > 15:
            print(f"\n🎉 SISTEMA FUNCIONANDO CORRETAMENTE!")
            print(f"   O problema pode estar nos dados da produção,")
            print(f"   não na lógica do sistema.")
        else:
            print(f"\n⚠️  PROBLEMA NA LÓGICA DO SISTEMA")