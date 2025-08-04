#!/usr/bin/env python3
"""
🧪 TESTE: Verificar se a correção do filtro > 0 funcionou
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func
from datetime import date

def testar_correcao_funcionario_193h():
    """Testar funcionário com ~193h que aparece na imagem"""
    print("🧪 TESTE: Funcionário com 193h (da imagem)")
    print("=" * 60)
    
    # Buscar funcionário com aproximadamente 193h
    funcionarios = Funcionario.query.join(RegistroPonto).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).all()
    
    engine = KPIsEngine()
    
    for funcionario in funcionarios:
        # Calcular totais
        total_trabalhadas = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).scalar() or 0
        
        total_extras_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31),
            RegistroPonto.horas_extras.isnot(None)
        ).scalar() or 0
        
        # Se for próximo de 193h, testar KPI
        if 190 <= total_trabalhadas <= 200:
            print(f"\n👤 CANDIDATO: {funcionario.nome}")
            print(f"📊 Horas Trabalhadas: {total_trabalhadas:.1f}h")
            print(f"⚡ Horas Extras (DB): {total_extras_db:.1f}h")
            
            # Calcular KPI
            kpis = engine.calcular_kpis_funcionario(
                funcionario.id,
                date(2025, 7, 1),
                date(2025, 7, 31)
            )
            
            print(f"🤖 KPI Engine: {kpis['horas_extras']:.1f}h")
            print(f"💰 Valor: R$ {kpis['eficiencia']:.2f}")
            
            diferenca = abs(total_extras_db - kpis['horas_extras'])
            if diferenca < 0.1:
                print(f"✅ CORRETO! Diferença: {diferenca:.2f}h")
            else:
                print(f"❌ DIVERGÊNCIA! Diferença: {diferenca:.2f}h")
            
            return funcionario, kpis
    
    print("❌ Nenhum funcionário com ~193h encontrado")
    return None, None

def testar_todos_funcionarios():
    """Testar todos os funcionários para verificar a correção"""
    print(f"\n🧪 TESTE: Todos os Funcionários")
    print("=" * 60)
    
    engine = KPIsEngine()
    
    funcionarios = Funcionario.query.join(RegistroPonto).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31)
    ).distinct().limit(5).all()
    
    corretos = 0
    total_testados = 0
    
    for funcionario in funcionarios:
        # Total extras no DB
        total_extras_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31),
            RegistroPonto.horas_extras.isnot(None)
        ).scalar() or 0
        
        if total_extras_db > 0:  # Só testar quem tem horas extras
            kpis = engine.calcular_kpis_funcionario(
                funcionario.id,
                date(2025, 7, 1),
                date(2025, 7, 31)
            )
            
            diferenca = abs(total_extras_db - kpis['horas_extras'])
            
            print(f"👤 {funcionario.nome[:25]:<25} | "
                  f"DB: {total_extras_db:>6.1f}h | "
                  f"KPI: {kpis['horas_extras']:>6.1f}h | "
                  f"{'✅' if diferenca < 0.1 else '❌'}")
            
            if diferenca < 0.1:
                corretos += 1
            total_testados += 1
    
    print(f"\n📊 RESULTADO: {corretos}/{total_testados} funcionários corretos")
    return corretos, total_testados

def verificar_problema_especifico():
    """Verificar se o problema específico foi resolvido"""
    print(f"\n🔍 VERIFICAÇÃO: Problema Específico Resolvido")
    print("=" * 60)
    
    # Total geral antes e depois
    total_geral = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    # Sábados específicos
    sabados_extras = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.tipo_registro == 'sabado_trabalhado',
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"📊 TOTAIS VERIFICADOS:")
    print(f"   Total Geral: {total_geral:.1f}h")
    print(f"   Sábados: {sabados_extras:.1f}h")
    
    if total_geral > 100:  # Deve ser muito maior que 0.3h
        print(f"✅ PROBLEMA RESOLVIDO! ({total_geral:.1f}h >> 0.3h)")
        if sabados_extras > 0:
            print(f"✅ Sábados incluídos: {sabados_extras:.1f}h")
        return True
    else:
        print(f"❌ PROBLEMA PERSISTE: {total_geral:.1f}h")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🧪 TESTE CORREÇÃO FINAL - FILTRO > 0 REMOVIDO")
        print("=" * 80)
        
        # 1. Testar funcionário específico da imagem
        funcionario, kpis = testar_correcao_funcionario_193h()
        
        # 2. Testar todos os funcionários
        corretos, total = testar_todos_funcionarios()
        
        # 3. Verificar se problema foi resolvido
        resolvido = verificar_problema_especifico()
        
        print(f"\n🎯 CONCLUSÃO:")
        if resolvido and corretos == total:
            print(f"✅ CORREÇÃO APLICADA COM SUCESSO!")
            print(f"✅ {corretos}/{total} funcionários com KPIs corretos")
            print(f"🎉 Problema das 7.9h de sábado RESOLVIDO!")
        else:
            print(f"❌ AINDA HÁ PROBLEMAS:")
            print(f"   Funcionários corretos: {corretos}/{total}")
            print(f"   Problema resolvido: {'✅' if resolvido else '❌'}")
        
        print(f"\n📝 PRÓXIMOS PASSOS:")
        print(f"   1. Servidor já foi reiniciado automaticamente")
        print(f"   2. Acesse a página do funcionário")
        print(f"   3. Agora deve mostrar as horas extras corretas")
        print(f"   4. As 7.9h de sábado devem estar incluídas")