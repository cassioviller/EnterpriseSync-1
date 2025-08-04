#!/usr/bin/env python3
"""
🔧 CORRIGIR: Cálculo de custo de mão de obra - método _calcular_custo_mensal
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def buscar_funcionario_problema():
    """Buscar funcionário que está na imagem (Antonio)"""
    print("🔍 BUSCANDO FUNCIONÁRIO DA IMAGEM")
    print("=" * 60)
    
    # Buscar por variações do nome
    funcionarios = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            f.salario,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras,
            COUNT(CASE WHEN r.tipo_registro = 'falta' THEN 1 END) as faltas
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE (f.nome LIKE '%Antonio%' OR f.nome LIKE '%Antônio%')
            AND r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
    """)).fetchall()
    
    if not funcionarios:
        print("❌ Nenhum Antonio encontrado")
        return None
    
    for func in funcionarios:
        print(f"👤 {func.nome}")
        print(f"   ID: {func.id}")
        print(f"   Salário: R$ {func.salario:.2f}")
        print(f"   Horas trabalhadas: {func.total_trabalhadas:.1f}h")
        print(f"   Horas extras: {func.total_extras:.1f}h")
        print(f"   Faltas: {func.faltas}")
        
        if abs(func.total_trabalhadas - 193.0) < 5:  # Próximo de 193h
            print(f"   ✅ ESTE É O FUNCIONÁRIO DA IMAGEM!")
            return func
    
    return funcionarios[0] if funcionarios else None

def analisar_metodo_custo_atual():
    """Analisar o método _calcular_custo_mensal atual"""
    print(f"\n🔍 ANALISANDO MÉTODO _calcular_custo_mensal")
    print("=" * 60)
    
    # O método está nas linhas ~180-240 do kpis_engine.py
    print("📝 LÓGICA ATUAL:")
    print("   1. Calcula valor_hora = salario / (dias_uteis * horas_diarias)")
    print("   2. Soma custo de cada tipo de registro:")
    print("      - trabalho_normal: valor_hora normal")
    print("      - sabado_trabalhado: valor_hora * 1.5")
    print("      - domingo_trabalhado: valor_hora * 2.0")
    print("      - feriado_trabalhado: valor_hora * 2.0")
    print("      - ferias: valor_hora * 1.33")
    
    print(f"\n❌ PROBLEMAS IDENTIFICADOS:")
    print("   1. NÃO desconta faltas do salário base")
    print("   2. Calcula custo baseado em horas trabalhadas, não salário + extras")
    print("   3. Lógica incorreta para cálculo de custo mensal")
    
    return True

def implementar_logica_correta():
    """Implementar lógica correta de custo mensal"""
    print(f"\n🔧 IMPLEMENTANDO LÓGICA CORRETA")
    print("=" * 60)
    
    print("📝 LÓGICA CORRETA:")
    print("   1. Salário base mensal")
    print("   2. MENOS: desconto por faltas (valor_dia * dias_falta)")
    print("   3. MAIS: valor das horas extras com percentuais corretos")
    print("   4. = CUSTO TOTAL MENSAL")
    
    return True

def criar_metodo_custo_correto():
    """Criar novo método de cálculo de custo correto"""
    print(f"\n🔧 CRIANDO MÉTODO CORRETO")
    print("=" * 60)
    
    codigo_novo = '''
    def _calcular_custo_mensal(self, funcionario_id, data_inicio, data_fim):
        """Calcular custo mensal CORRETO: salário - faltas + valor horas extras"""
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario or not funcionario.salario:
            return 0.0
        
        salario_base = funcionario.salario
        
        # 1. Calcular dias úteis do período
        dias_uteis = self._calcular_dias_uteis_periodo(data_inicio, data_fim)
        valor_dia = salario_base / dias_uteis if dias_uteis > 0 else 0
        
        # 2. Contar faltas (descontar do salário)
        faltas = db.session.query(func.count(RegistroPonto.id)).filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.tipo_registro == 'falta'
        ).scalar() or 0
        
        desconto_faltas = valor_dia * faltas
        salario_liquido = salario_base - desconto_faltas
        
        # 3. Calcular valor das horas extras
        valor_horas_extras = self._calcular_valor_horas_extras(funcionario_id, data_inicio, data_fim)
        
        # 4. Custo total = salário líquido + horas extras
        custo_total = salario_liquido + valor_horas_extras
        
        return custo_total
    '''
    
    print("✅ Código do método correto criado")
    return codigo_novo

def testar_com_funcionario(funcionario):
    """Testar cálculo com funcionário específico"""
    print(f"\n🧪 TESTE COM FUNCIONÁRIO: {funcionario.nome}")
    print("=" * 60)
    
    # Teste manual do cálculo correto
    salario_base = funcionario.salario
    print(f"💰 Salário base: R$ {salario_base:.2f}")
    
    # Contar faltas
    faltas = db.session.execute(text("""
        SELECT COUNT(*)
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND tipo_registro = 'falta'
    """), {'func_id': funcionario.id}).scalar() or 0
    
    print(f"❌ Faltas: {faltas} dias")
    
    # Dias úteis julho 2025
    dias_uteis = 23  # Julho tem 23 dias úteis
    valor_dia = salario_base / dias_uteis
    desconto_faltas = valor_dia * faltas
    salario_liquido = salario_base - desconto_faltas
    
    print(f"📅 Dias úteis: {dias_uteis}")
    print(f"💵 Valor por dia: R$ {valor_dia:.2f}")
    print(f"💸 Desconto faltas: R$ {desconto_faltas:.2f}")
    print(f"💰 Salário líquido: R$ {salario_liquido:.2f}")
    
    # Horas extras
    horas_extras = funcionario.total_extras
    
    # Assumindo horário 8.8h/dia para calcular valor hora
    horas_mensais = dias_uteis * 8.8
    valor_hora = salario_base / horas_mensais
    
    # Valor das horas extras (50% adicional padrão)
    valor_extras = horas_extras * valor_hora * 1.5
    
    print(f"⏰ Horas extras: {horas_extras:.1f}h")
    print(f"💲 Valor hora: R$ {valor_hora:.2f}")
    print(f"💰 Valor extras: R$ {valor_extras:.2f}")
    
    # Custo total correto
    custo_correto = salario_liquido + valor_extras
    print(f"\n🎯 CUSTO TOTAL CORRETO: R$ {custo_correto:.2f}")
    
    # Comparar com KPI atual
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"🤖 KPI atual: R$ {kpis['custo_mao_obra']:.2f}")
    print(f"📊 Diferença: R$ {abs(custo_correto - kpis['custo_mao_obra']):.2f}")
    
    return custo_correto, kpis['custo_mao_obra']

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO CUSTO MÃO DE OBRA")
        print("=" * 80)
        
        # 1. Buscar funcionário
        funcionario = buscar_funcionario_problema()
        
        if not funcionario:
            print("❌ Funcionário não encontrado")
            exit()
        
        # 2. Analisar método atual
        analisar_metodo_custo_atual()
        
        # 3. Implementar lógica correta
        implementar_logica_correta()
        
        # 4. Criar método correto
        codigo_novo = criar_metodo_custo_correto()
        
        # 5. Testar com funcionário
        custo_correto, custo_atual = testar_com_funcionario(funcionario)
        
        print(f"\n🎯 RESULTADO:")
        print(f"   Funcionário: {funcionario.nome}")
        print(f"   Custo correto: R$ {custo_correto:.2f}")
        print(f"   Custo atual: R$ {custo_atual:.2f}")
        
        if abs(custo_correto - custo_atual) > 100:
            print(f"   ❌ PRECISA CORREÇÃO!")
            print(f"   💡 Solução: Substituir método _calcular_custo_mensal")
        else:
            print(f"   ✅ Custo está próximo do correto")