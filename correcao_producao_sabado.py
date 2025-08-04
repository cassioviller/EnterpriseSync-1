#!/usr/bin/env python3
"""
🔧 CORREÇÃO ESPECÍFICA PARA PRODUÇÃO: Antonio e horas extras de sábado
Este script irá diagnosticar e corrigir especificamente o problema no ambiente de produção
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import date
from sqlalchemy import func, text

def diagnosticar_ambiente_producao():
    """Diagnosticar o ambiente de produção"""
    print("🔍 DIAGNÓSTICO: Ambiente de Produção")
    print("=" * 60)
    
    # 1. Buscar funcionário Antonio por diferentes critérios
    criterios = [
        ("salário 2153.26", Funcionario.salario == 2153.26),
        ("nome contém 'Antonio'", Funcionario.nome.ilike('%antonio%')),
        ("nome contém 'Fernandes'", Funcionario.nome.ilike('%fernandes%')),
        ("salário entre 2100-2200", (Funcionario.salario >= 2100) & (Funcionario.salario <= 2200))
    ]
    
    antonio = None
    for desc, criterio in criterios:
        funcionarios = Funcionario.query.filter(criterio).all()
        print(f"📊 Busca por {desc}: {len(funcionarios)} encontrados")
        
        for func in funcionarios:
            print(f"   → {func.nome} | R$ {func.salario:.2f} | ID: {func.id}")
            if 'antonio' in func.nome.lower() or func.salario == 2153.26:
                antonio = func
                print(f"   ★ ANTONIO IDENTIFICADO!")
    
    return antonio

def diagnosticar_registros_sabado(funcionario_id=None):
    """Diagnosticar registros de sábado no sistema"""
    print(f"\n🔍 DIAGNÓSTICO: Registros de Sábado")
    print("=" * 60)
    
    # Query básica para todos os sábados de julho
    base_query = RegistroPonto.query.filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    )
    
    if funcionario_id:
        base_query = base_query.filter(RegistroPonto.funcionario_id == funcionario_id)
    
    # Tipos de registro relacionados a sábado
    tipos_sabado = ['sabado_trabalhado', 'sabado_horas_extras', 'folga_sabado']
    
    for tipo in tipos_sabado:
        registros = base_query.filter(RegistroPonto.tipo_registro == tipo).all()
        print(f"📊 {tipo}: {len(registros)} registros")
        
        if len(registros) > 0 and len(registros) <= 10:
            for reg in registros:
                func = Funcionario.query.get(reg.funcionario_id)
                nome = func.nome[:20] + "..." if func and len(func.nome) > 20 else (func.nome if func else "N/A")
                print(f"   {reg.data} | {nome} | Trab: {reg.horas_trabalhadas:.1f}h | Extras: {reg.horas_extras or 0:.1f}h")

def aplicar_correcao_forcada():
    """Aplicar correção forçada para todos os registros de sábado"""
    print(f"\n🔧 CORREÇÃO FORÇADA: Sábados")
    print("=" * 60)
    
    # Buscar TODOS os registros de sábado trabalhado que precisam de correção
    registros = RegistroPonto.query.filter(
        RegistroPonto.tipo_registro.in_(['sabado_trabalhado', 'sabado_horas_extras']),
        RegistroPonto.horas_trabalhadas > 0
    ).all()
    
    print(f"📊 REGISTROS DE SÁBADO ENCONTRADOS: {len(registros)}")
    
    corrigidos = 0
    for registro in registros:
        # Forçar horas_extras = horas_trabalhadas para sábados
        if (registro.horas_extras or 0) < registro.horas_trabalhadas:
            print(f"   Corrigindo: {registro.data} | {registro.horas_trabalhadas:.1f}h → {registro.horas_trabalhadas:.1f}h extras")
            registro.horas_extras = registro.horas_trabalhadas
            registro.percentual_extras = 50.0  # 50% adicional para sábado
            corrigidos += 1
    
    if corrigidos > 0:
        db.session.commit()
        print(f"✅ {corrigidos} registros corrigidos e salvos!")
    else:
        print(f"✅ Todos os registros já estavam corretos")
    
    return corrigidos

def testar_kpis_pos_correcao(antonio):
    """Testar KPIs após correção"""
    if not antonio:
        print(f"\n❌ Antonio não encontrado para teste")
        return
    
    print(f"\n🧪 TESTE: KPIs do Antonio")
    print("=" * 60)
    
    print(f"👤 Testando: {antonio.nome}")
    print(f"💰 Salário: R$ {antonio.salario:.2f}")
    
    # Calcular KPIs
    engine = KPIsEngine()
    data_inicio = date(2025, 7, 1)
    data_fim = date(2025, 7, 31)
    
    try:
        kpis = engine.calcular_kpis_funcionario(antonio.id, data_inicio, data_fim)
        
        print(f"\n📊 RESULTADO:")
        print(f"   Horas Extras: {kpis['horas_extras']:.1f}h")
        print(f"   Valor Horas Extras: R$ {kpis['eficiencia']:.2f}")
        
        # Listar todos os registros com horas extras
        registros_extras = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == antonio.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim,
            RegistroPonto.horas_extras > 0
        ).all()
        
        print(f"\n📋 REGISTROS COM HORAS EXTRAS ({len(registros_extras)}):")
        total_manual = 0
        for reg in registros_extras:
            print(f"   {reg.data} | {reg.tipo_registro} | {reg.horas_extras:.1f}h")
            total_manual += reg.horas_extras or 0
        
        print(f"\n📈 VERIFICAÇÃO:")
        print(f"   Soma manual: {total_manual:.1f}h")
        print(f"   KPI calculado: {kpis['horas_extras']:.1f}h")
        
        if kpis['horas_extras'] >= 8.0:  # Esperamos pelo menos 7.9h do sábado + algo
            print(f"\n✅ SUCESSO! Sábados incluídos nos KPIs")
        else:
            print(f"\n❌ PROBLEMA PERSISTE")
            
    except Exception as e:
        print(f"\n❌ ERRO ao calcular KPIs: {e}")

def executar_sql_direto():
    """Executar correção via SQL direto"""
    print(f"\n💾 CORREÇÃO VIA SQL DIRETO")
    print("=" * 60)
    
    try:
        # SQL para corrigir todos os sábados de uma vez
        resultado = db.session.execute(text("""
            UPDATE registro_ponto 
            SET horas_extras = horas_trabalhadas,
                percentual_extras = 50.0
            WHERE tipo_registro IN ('sabado_trabalhado', 'sabado_horas_extras')
                AND horas_trabalhadas > 0
                AND (horas_extras < horas_trabalhadas OR horas_extras IS NULL)
        """))
        
        db.session.commit()
        print(f"✅ SQL executado: {resultado.rowcount} linhas afetadas")
        
    except Exception as e:
        print(f"❌ ERRO no SQL: {e}")
        db.session.rollback()

if __name__ == "__main__":
    with app.app_context():
        print("🔧 CORREÇÃO ESPECÍFICA - PRODUÇÃO - ANTONIO SÁBADO")
        print("=" * 80)
        
        # 1. Diagnosticar ambiente
        antonio = diagnosticar_ambiente_producao()
        
        # 2. Diagnosticar registros de sábado
        diagnosticar_registros_sabado(antonio.id if antonio else None)
        
        # 3. Aplicar correção via código
        corrigidos_codigo = aplicar_correcao_forcada()
        
        # 4. Se não funcionou, tentar SQL direto
        if corrigidos_codigo == 0:
            executar_sql_direto()
        
        # 5. Testar resultado
        if antonio:
            testar_kpis_pos_correcao(antonio)
        
        print(f"\n🎯 FINALIZADO!")
        print(f"   Reinicie o servidor e atualize a página")
        print(f"   As horas extras devem mostrar o valor correto agora")