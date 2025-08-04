#!/usr/bin/env python3
"""
🔧 FORÇAR: Atualização completa dos KPIs de horas extras
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def forcar_recalculo_todos_sabados():
    """Forçar recálculo de TODOS os sábados"""
    print("🔧 RECÁLCULO FORÇADO: Todos os sábados")
    print("=" * 60)
    
    # Buscar TODOS os registros de sábado
    todos_sabados = db.session.execute(text("""
        SELECT 
            id,
            data,
            funcionario_id,
            tipo_registro,
            horas_trabalhadas,
            horas_extras
        FROM registro_ponto
        WHERE EXTRACT(DOW FROM data) = 6  -- Sábado
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
        ORDER BY data, funcionario_id
    """)).fetchall()
    
    print(f"📋 PROCESSANDO {len(todos_sabados)} REGISTROS DE SÁBADO:")
    
    sabados_corrigidos = 0
    folgas_zeradas = 0
    
    for sabado in todos_sabados:
        if sabado.tipo_registro == 'sabado_trabalhado' and sabado.horas_trabalhadas > 0:
            # Sábado trabalhado: 0h trabalhadas, manter extras
            db.session.execute(text("""
                UPDATE registro_ponto 
                SET horas_trabalhadas = 0,
                    horas_extras = :horas_extras,
                    percentual_extras = 50
                WHERE id = :reg_id
            """), {
                'horas_extras': sabado.horas_trabalhadas,  # Converter trabalhadas em extras
                'reg_id': sabado.id
            })
            sabados_corrigidos += 1
            
        elif sabado.tipo_registro == 'folga_sabado' and (sabado.horas_trabalhadas > 0 or sabado.horas_extras > 0):
            # Folga de sábado: zerar tudo
            db.session.execute(text("""
                UPDATE registro_ponto 
                SET horas_trabalhadas = 0,
                    horas_extras = 0,
                    percentual_extras = 0
                WHERE id = :reg_id
            """), {'reg_id': sabado.id})
            folgas_zeradas += 1
    
    db.session.commit()
    
    print(f"✅ {sabados_corrigidos} sábados trabalhados corrigidos")
    print(f"✅ {folgas_zeradas} folgas de sábado zeradas")
    
    return sabados_corrigidos + folgas_zeradas

def verificar_funcionario_especifico():
    """Verificar funcionário específico da imagem"""
    print(f"\n🔍 VERIFICAÇÃO: Funcionário da imagem")
    print("=" * 60)
    
    # Buscar funcionário com ~193h (mais próximo da imagem)
    funcionario_alvo = db.session.execute(text("""
        SELECT 
            f.id,
            f.nome,
            SUM(r.horas_trabalhadas) as total_trabalhadas,
            SUM(r.horas_extras) as total_extras
        FROM funcionario f
        JOIN registro_ponto r ON f.id = r.funcionario_id
        WHERE r.data >= '2025-07-01' 
            AND r.data <= '2025-07-31'
        GROUP BY f.id, f.nome
        HAVING SUM(r.horas_trabalhadas) BETWEEN 180 AND 210
        ORDER BY ABS(SUM(r.horas_trabalhadas) - 193.0)
        LIMIT 1
    """)).fetchone()
    
    if not funcionario_alvo:
        print("❌ Funcionário não encontrado")
        return None
    
    print(f"👤 {funcionario_alvo.nome} (ID: {funcionario_alvo.id})")
    print(f"📊 {funcionario_alvo.total_trabalhadas:.1f}h trabalhadas")
    print(f"📊 {funcionario_alvo.total_extras:.1f}h extras (DB)")
    
    # Testar KPIs
    engine = KPIsEngine()
    kpis = engine.calcular_kpis_funcionario(
        funcionario_alvo.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"🤖 {kpis['horas_extras']:.1f}h extras (KPI)")
    print(f"💰 R$ {kpis['eficiencia']:.2f} valor")
    
    # Verificar sábados
    sabados = db.session.execute(text("""
        SELECT COUNT(*), SUM(horas_extras)
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND EXTRACT(DOW FROM data) = 6
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras > 0
    """), {'func_id': funcionario_alvo.id}).fetchone()
    
    print(f"🗓️  {sabados[0] or 0} sábados, {sabados[1] or 0:.1f}h extras sábado")
    
    if abs(funcionario_alvo.total_extras - kpis['horas_extras']) < 0.1:
        print(f"✅ KPI está correto!")
        if kpis['horas_extras'] > 30:
            print(f"✅ Horas extras incluem sábados")
        else:
            print(f"⚠️  Poucas horas extras - verificar se há sábados")
    else:
        print(f"❌ KPI diverge do DB!")
        print(f"   Diferença: {abs(funcionario_alvo.total_extras - kpis['horas_extras']):.1f}h")
    
    return funcionario_alvo

def restart_servidor():
    """Reiniciar servidor para aplicar mudanças"""
    print(f"\n🔄 REINICIANDO SERVIDOR...")
    # O restart será feito automaticamente após o commit das mudanças
    pass

if __name__ == "__main__":
    with app.app_context():
        print("🔧 FORÇA TOTAL: Recálculo de KPIs e Sábados")
        print("=" * 80)
        
        # 1. Forçar recálculo de todos os sábados
        total_corrigidos = forcar_recalculo_todos_sabados()
        
        # 2. Verificar funcionário específico
        funcionario = verificar_funcionario_especifico()
        
        # 3. Status final
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Registros corrigidos: {total_corrigidos}")
        if funcionario:
            print(f"   Funcionário teste: {funcionario.nome}")
            print(f"   URL: /funcionarios/{funcionario.id}/perfil")
        
        print(f"\n🚀 PRÓXIMOS PASSOS:")
        print(f"   1. Servidor será reiniciado automaticamente")
        print(f"   2. Teste a interface em alguns minutos")
        print(f"   3. Os KPIs devem mostrar valores corretos")
        
        if total_corrigidos > 0:
            print(f"\n🎉 {total_corrigidos} REGISTROS CORRIGIDOS!")
            print(f"   Sistema deve funcionar agora")
        else:
            print(f"\n⚠️  NENHUMA CORREÇÃO APLICADA")
            print(f"   Dados já podem estar corretos")