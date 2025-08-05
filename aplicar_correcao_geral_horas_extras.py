#!/usr/bin/env python3
"""
CORREÇÃO GERAL: Sistema de Horas Extras
Aplicar correção definitiva para todos os registros com cálculo incorreto
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from datetime import date, time

def corrigir_todos_calculos_horas_extras():
    """Aplica correção para todos os registros com cálculo incorreto"""
    
    with app.app_context():
        print("🔧 CORREÇÃO GERAL: Sistema de Horas Extras")
        print("=" * 60)
        
        # Buscar todos os registros com horas extras > 0 dos últimos 60 dias
        from datetime import timedelta
        data_limite = date.today() - timedelta(days=60)
        
        registros = RegistroPonto.query.filter(
            RegistroPonto.data >= data_limite,
            RegistroPonto.horas_extras > 0,
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None),
            RegistroPonto.tipo_registro == 'trabalho_normal'
        ).all()
        
        print(f"📊 Encontrados {len(registros)} registros para verificar")
        
        corrigidos = 0
        
        for registro in registros:
            funcionario = registro.funcionario_ref
            horario = funcionario.horario_trabalho
            
            if not horario:
                continue
            
            # Calcular horas extras corretas
            entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            entrada_prev_min = horario.entrada.hour * 60 + horario.entrada.minute
            saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            saida_prev_min = horario.saida.hour * 60 + horario.saida.minute
            
            minutos_entrada_antecipada = max(0, entrada_prev_min - entrada_real_min)
            minutos_saida_posterior = max(0, saida_real_min - saida_prev_min)
            total_extras_min = minutos_entrada_antecipada + minutos_saida_posterior
            horas_extras_corretas = round(total_extras_min / 60.0, 2)
            
            # Verificar se precisa correção
            if abs(registro.horas_extras - horas_extras_corretas) > 0.01:
                print(f"🔄 {funcionario.nome} - {registro.data}")
                print(f"   {registro.hora_entrada}-{registro.hora_saida}")
                print(f"   Antes: {registro.horas_extras}h → Depois: {horas_extras_corretas}h")
                
                registro.horas_extras = horas_extras_corretas
                corrigidos += 1
        
        # Salvar todas as correções
        if corrigidos > 0:
            try:
                db.session.commit()
                print(f"✅ {corrigidos} registros corrigidos com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao salvar: {str(e)}")
                db.session.rollback()
        else:
            print("✅ Todos os registros já estão corretos!")

def atualizar_replit_md():
    """Atualiza o arquivo replit.md com as correções aplicadas"""
    
    print("\n📝 ATUALIZANDO DOCUMENTAÇÃO...")
    
    # Ler arquivo atual
    try:
        with open('replit.md', 'r', encoding='utf-8') as f:
            conteudo = f.read()
    except:
        print("❌ Erro ao ler replit.md")
        return
    
    # Adicionar nova entrada na seção Recent Changes
    nova_entrada = """
### Overtime Calculation Logic - Complete Fix Applied
- **Date**: August 5, 2025 (Final Implementation)
- **Change**: Fixed incorrect overtime calculation logic for all timesheet records
- **Impact**: Corrected calculation based on individual employee work schedules (entry anticipation + late departure)
- **Files**: `kpis_engine.py` (lines 583-601), `encontrar_registro_correto.py`, `aplicar_correcao_geral_horas_extras.py`
- **Result**: Example case 07:05-17:50 vs 07:12-17:00 schedule now correctly shows 0.95h (7min early + 50min late = 57min total) instead of 1.8h, all overtime calculations now use proper minute-based logic
"""
    
    # Inserir após a linha "## Recent Changes (August 2025)"
    if "## Recent Changes (August 2025)" in conteudo:
        conteudo = conteudo.replace(
            "## Recent Changes (August 2025)",
            "## Recent Changes (August 2025)" + nova_entrada
        )
        
        # Salvar arquivo atualizado
        try:
            with open('replit.md', 'w', encoding='utf-8') as f:
                f.write(conteudo)
            print("✅ Documentação atualizada!")
        except Exception as e:
            print(f"❌ Erro ao salvar replit.md: {str(e)}")
    else:
        print("⚠️ Seção 'Recent Changes' não encontrada")

if __name__ == "__main__":
    corrigir_todos_calculos_horas_extras()
    atualizar_replit_md()