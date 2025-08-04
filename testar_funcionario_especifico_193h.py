#!/usr/bin/env python3
"""
🎯 TESTE: Funcionário específico com maiores horas extras (que deveria aparecer na imagem)
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func
from datetime import date

def encontrar_funcionario_correto():
    """Encontrar funcionário que mais se aproxima do caso da imagem"""
    print("🎯 BUSCA: Funcionário com perfil da imagem")
    print("=" * 60)
    
    # Buscar funcionários com mais horas extras
    funcionarios = db.session.execute("""
        SELECT 
            f.id,
            f.nome,
            f.salario,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras,
            COUNT(CASE WHEN EXTRACT(DOW FROM r.data) = 6 AND r.horas_extras > 0 THEN 1 END) as sabados_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome, f.salario
        HAVING SUM(r.horas_extras) > 0
        ORDER BY total_extras DESC
        LIMIT 3
    """).fetchall()
    
    print(f"📊 TOP 3 FUNCIONÁRIOS COM MAIS HORAS EXTRAS:")
    for func in funcionarios:
        print(f"   {func.nome}: {func.total_trabalhadas:.1f}h trabalhadas, "
              f"{func.total_extras:.1f}h extras, {func.sabados_extras} sábados")
    
    return funcionarios[0] if funcionarios else None

def testar_kpi_completo(funcionario):
    """Testar KPI completo do funcionário"""
    print(f"\n🧪 TESTE KPI: {funcionario.nome}")
    print("=" * 60)
    
    engine = KPIsEngine()
    
    # KPI atual
    kpis = engine.calcular_kpis_funcionario(
        funcionario.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    # Soma direta do database
    total_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == funcionario.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"📊 COMPARAÇÃO:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras (KPI): {kpis['horas_extras']:.1f}h")
    print(f"   Horas Extras (DB): {total_db:.1f}h")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    
    diferenca = abs(kpis['horas_extras'] - total_db)
    if diferenca < 0.1:
        print(f"   ✅ CORRETO! Diferença: {diferenca:.2f}h")
        resultado = "CORRETO"
    else:
        print(f"   ❌ DIVERGÊNCIA! Diferença: {diferenca:.2f}h")
        resultado = "INCORRETO"
    
    return kpis, resultado

def listar_registros_detalhados(funcionario_id):
    """Listar todos os registros detalhados do funcionário"""
    print(f"\n📋 REGISTROS DETALHADOS:")
    print("=" * 60)
    
    registros = db.session.execute("""
        SELECT 
            data,
            tipo_registro,
            horas_trabalhadas,
            horas_extras,
            percentual_extras,
            EXTRACT(DOW FROM data) as dia_semana
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras IS NOT NULL
            AND horas_extras > 0
        ORDER BY data
    """, {'func_id': funcionario_id}).fetchall()
    
    print(f"📋 REGISTROS COM HORAS EXTRAS ({len(registros)}):")
    
    total_sabados = 0
    total_outros = 0
    
    for reg in registros:
        dias = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
        dia_nome = dias[int(reg.dia_semana)]
        
        print(f"   {reg.data} ({dia_nome}) | {reg.tipo_registro} | "
              f"Trab: {reg.horas_trabalhadas:.1f}h | "
              f"Extras: {reg.horas_extras:.1f}h | "
              f"Perc: {reg.percentual_extras or 0:.0f}%")
        
        if int(reg.dia_semana) == 6:  # Sábado
            total_sabados += reg.horas_extras
        else:
            total_outros += reg.horas_extras
    
    print(f"\n📊 RESUMO:")
    print(f"   Sábados: {total_sabados:.1f}h")
    print(f"   Outros dias: {total_outros:.1f}h")
    print(f"   Total: {total_sabados + total_outros:.1f}h")
    
    return total_sabados, total_outros

def simular_interface_usuario(funcionario, kpis):
    """Simular o que aparece na interface do usuário"""
    print(f"\n🖥️  SIMULAÇÃO: Interface do Usuário")
    print("=" * 60)
    
    print(f"👤 Funcionário: {funcionario.nome}")
    print(f"📊 DASHBOARD KPIs:")
    print(f"   Horas Trabalhadas: {kpis['horas_trabalhadas']:.1f}h")
    print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")  # Este deve ser o valor correto
    print(f"   Faltas: {kpis['faltas']}")
    print(f"   Atrasos: {kpis['atrasos']:.2f}h")
    print(f"   Produtividade: {kpis['produtividade']:.1f}%")
    print(f"   Absenteísmo: {kpis['absenteismo']:.1f}%")
    print(f"   Custo Alimentação: R$ {kpis['custo_alimentacao']:.2f}")
    print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
    print(f"   Custo Total: R$ {kpis['custo_total']:.2f}")
    
    if kpis['horas_extras'] > 20:
        print(f"\n✅ Este funcionário tem {kpis['horas_extras']:.1f}h extras - compatível com a imagem!")
    else:
        print(f"\n❌ Este funcionário tem apenas {kpis['horas_extras']:.1f}h extras - não é o da imagem")

if __name__ == "__main__":
    with app.app_context():
        print("🎯 TESTE FUNCIONÁRIO ESPECÍFICO - CASO DA IMAGEM")
        print("=" * 80)
        
        # 1. Encontrar funcionário correto
        funcionario = encontrar_funcionario_correto()
        
        if not funcionario:
            print("❌ Nenhum funcionário encontrado")
        else:
            # 2. Testar KPI
            kpis, resultado = testar_kpi_completo(funcionario)
            
            # 3. Listar registros detalhados
            sabados, outros = listar_registros_detalhados(funcionario.id)
            
            # 4. Simular interface
            simular_interface_usuario(funcionario, kpis)
            
            print(f"\n🎯 CONCLUSÃO:")
            print(f"   Funcionário: {funcionario.nome}")
            print(f"   KPI Status: {resultado}")
            print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
            print(f"   Sábados: {sabados:.1f}h")
            
            if resultado == "CORRETO" and kpis['horas_extras'] > 30:
                print(f"\n✅ ESTE É PROVAVELMENTE O FUNCIONÁRIO DA IMAGEM!")
                print(f"   O sistema deveria mostrar {kpis['horas_extras']:.1f}h e não 0.3h")
            else:
                print(f"\n🤔 Pode não ser o funcionário da imagem")
                print(f"   Verifique se as 0.3h da imagem são de outro funcionário")