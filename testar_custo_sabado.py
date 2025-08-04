#!/usr/bin/env python3
"""
🧪 TESTE: Verificar se o cálculo de custo de mão de obra para sábado está correto
Deve contar apenas o valor das horas extras (1.5x), não duplicar
"""

from app import app, db
from models import Funcionario, RegistroPonto
from kpis_engine import KPIsEngine
from datetime import date

def testar_custo_sabado():
    """Testa o cálculo de custo para sábado trabalhado"""
    print("🧪 TESTE: Verificando cálculo de custo de sábado")
    print("=" * 50)
    
    # Buscar funcionário com registros de sábado
    funcionario = Funcionario.query.filter(
        Funcionario.salario.isnot(None),
        Funcionario.salario > 0
    ).first()
    
    if not funcionario:
        print("❌ Nenhum funcionário com salário encontrado")
        return False
    
    print(f"👤 Funcionário: {funcionario.nome}")
    print(f"💰 Salário: R$ {funcionario.salario}")
    
    # Buscar registro de sábado específico
    registro_sabado = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data == date(2025, 7, 5),  # Sábado conhecido
        RegistroPonto.tipo_registro == 'sabado_horas_extras'
    ).first()
    
    if not registro_sabado:
        print("❌ Registro de sábado 05/07/2025 não encontrado")
        return False
    
    print(f"📅 Data: {registro_sabado.data}")
    print(f"⏰ Horas trabalhadas: {registro_sabado.horas_trabalhadas}")
    print(f"⭐ Horas extras: {registro_sabado.horas_extras}")
    print(f"📊 Tipo: {registro_sabado.tipo_registro}")
    
    # Calcular KPIs para o período
    engine = KPIsEngine()
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    kpis = engine.calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
    
    if not kpis:
        print("❌ Erro ao calcular KPIs")
        return False
    
    custo_mao_obra = kpis['custo_mao_obra']
    print(f"💵 Custo mão de obra (julho): R$ {custo_mao_obra:.2f}")
    
    # Verificar cálculo manual
    print("\n🔍 VERIFICAÇÃO MANUAL:")
    
    # Buscar todos os registros do funcionário no período
    registros = RegistroPonto.query.filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= data_inicio,
        RegistroPonto.data <= data_fim
    ).all()
    
    # Classificar por tipo
    horas_por_tipo = {}
    for registro in registros:
        tipo = registro.tipo_registro or 'trabalho_normal'
        horas = float(registro.horas_trabalhadas or 0)
        
        if tipo not in horas_por_tipo:
            horas_por_tipo[tipo] = 0.0
        horas_por_tipo[tipo] += horas
    
    print("📊 Horas por tipo:")
    for tipo, horas in horas_por_tipo.items():
        print(f"   {tipo}: {horas}h")
    
    # Calcular valor/hora
    tipos_divisor = ['trabalho_normal', 'falta_justificada']
    horas_divisor = sum(horas_por_tipo.get(tipo, 0.0) for tipo in tipos_divisor)
    
    if horas_divisor > 0:
        valor_hora = float(funcionario.salario) / horas_divisor
    else:
        # Fallback: 220h/mês (padrão)
        valor_hora = float(funcionario.salario) / 220.0
    
    print(f"💱 Valor/hora calculado: R$ {valor_hora:.2f}")
    print(f"⚖️  Base de cálculo: {horas_divisor}h (horas normais + faltas justificadas)")
    
    # Verificar cálculo de sábado
    horas_sabado = (horas_por_tipo.get('sabado_trabalhado', 0.0) + 
                   horas_por_tipo.get('sabado_horas_extras', 0.0))
    
    custo_sabado_esperado = horas_sabado * valor_hora * 1.5
    
    print(f"\n💰 CÁLCULO DE SÁBADO:")
    print(f"   Horas sábado: {horas_sabado}h")
    print(f"   Valor/hora: R$ {valor_hora:.2f}")
    print(f"   Multiplicador: 1.5x (50% adicional)")
    print(f"   Custo sábado: {horas_sabado} × {valor_hora:.2f} × 1.5 = R$ {custo_sabado_esperado:.2f}")
    
    # Calcular custo total esperado
    custo_total_esperado = 0.0
    
    # 1. Horas normais
    horas_normais = (horas_por_tipo.get('trabalho_normal', 0.0) + 
                    horas_por_tipo.get('falta_justificada', 0.0))
    custo_normais = horas_normais * valor_hora
    custo_total_esperado += custo_normais
    
    # 2. Sábado (1.5x)
    custo_total_esperado += custo_sabado_esperado
    
    # 3. Domingo (2.0x)
    horas_domingo = horas_por_tipo.get('domingo_trabalhado', 0.0)
    custo_domingo = horas_domingo * valor_hora * 2.0
    custo_total_esperado += custo_domingo
    
    # 4. Feriado (2.0x)
    horas_feriado = horas_por_tipo.get('feriado_trabalhado', 0.0)
    custo_feriado = horas_feriado * valor_hora * 2.0
    custo_total_esperado += custo_feriado
    
    print(f"\n📊 COMPOSIÇÃO DO CUSTO TOTAL:")
    print(f"   Horas normais: {horas_normais}h × R$ {valor_hora:.2f} = R$ {custo_normais:.2f}")
    print(f"   Sábado: {horas_sabado}h × R$ {valor_hora:.2f} × 1.5 = R$ {custo_sabado_esperado:.2f}")
    print(f"   Domingo: {horas_domingo}h × R$ {valor_hora:.2f} × 2.0 = R$ {custo_domingo:.2f}")
    print(f"   Feriado: {horas_feriado}h × R$ {valor_hora:.2f} × 2.0 = R$ {custo_feriado:.2f}")
    print(f"   TOTAL ESPERADO: R$ {custo_total_esperado:.2f}")
    print(f"   TOTAL CALCULADO: R$ {custo_mao_obra:.2f}")
    
    # Verificar se há diferença significativa
    diferenca = abs(custo_mao_obra - custo_total_esperado)
    tolerancia = 0.01  # 1 centavo
    
    if diferenca <= tolerancia:
        print(f"✅ CÁLCULO CORRETO! Diferença: R$ {diferenca:.2f}")
        return True
    else:
        print(f"❌ CÁLCULO INCORRETO! Diferença: R$ {diferenca:.2f}")
        
        # Verificar se pode estar duplicando sábado
        if custo_mao_obra > custo_total_esperado:
            possivel_duplicacao = custo_mao_obra - custo_total_esperado
            print(f"⚠️  Possível duplicação de R$ {possivel_duplicacao:.2f}")
            
            # Verificar se a diferença é próxima do custo de sábado
            if abs(possivel_duplicacao - custo_sabado_esperado) < 1.0:
                print("🚨 PROVÁVEL DUPLICAÇÃO DE CUSTO DE SÁBADO!")
        
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🚀 TESTE DE CUSTO DE MÃO DE OBRA PARA SÁBADO")
        print("=" * 60)
        
        resultado = testar_custo_sabado()
        
        print("\n" + "=" * 60)
        if resultado:
            print("🎉 TESTE PASSOU!")
            print("✅ Cálculo de sábado está correto")
            print("✅ Não há duplicação de valores")
        else:
            print("❌ TESTE FALHOU!")
            print("⚠️  Verificar lógica de cálculo")
        
        print("=" * 60)