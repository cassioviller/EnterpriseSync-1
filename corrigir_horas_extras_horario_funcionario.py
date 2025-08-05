#!/usr/bin/env python3
"""
CORREÇÃO: Cálculo de Horas Extras com Horário Específico do Funcionário
Sistema SIGE - Data: 05 de Agosto de 2025

PROBLEMA IDENTIFICADO:
- Sistema calculava horas extras fixas em 8h: horas_extras = horas_trabalhadas - 8.0
- INCORRETO: Deve usar o horário padrão específico de cada funcionário

CORREÇÃO:
- Usar HorarioTrabalho.horas_diarias específico de cada funcionário
- Recalcular todos os registros com o horário correto
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from sqlalchemy import text

def corrigir_calculo_horas_extras():
    """
    Corrige o cálculo de horas extras usando o horário específico de cada funcionário
    """
    print("🔧 INICIANDO CORREÇÃO: Horas Extras com Horário Específico do Funcionário")
    print("=" * 80)
    
    with app.app_context():
        # 1. Buscar todos os registros de ponto
        registros = db.session.query(RegistroPonto).join(Funcionario).all()
        
        registros_corrigidos = 0
        total_registros = len(registros)
        
        print(f"📊 Total de registros encontrados: {total_registros}")
        print()
        
        for registro in registros:
            funcionario = registro.funcionario_ref
            
            # 2. Obter horário de trabalho do funcionário
            horario_funcionario = funcionario.horario_trabalho
            horas_padrao = 8.0  # Default se não houver horário específico
            
            if horario_funcionario and horario_funcionario.horas_diarias:
                horas_padrao = horario_funcionario.horas_diarias
            
            # 3. Recalcular horas extras
            horas_trabalhadas = registro.horas_trabalhadas or 0.0
            horas_extras_antigas = registro.horas_extras or 0.0
            
            # CORREÇÃO: Usar horário específico do funcionário
            if registro.tipo_registro in ['trabalho_normal', 'trabalhado']:
                # Para trabalho normal, horas extras = trabalhadas - padrão
                horas_extras_novas = max(0, horas_trabalhadas - horas_padrao)
            elif registro.tipo_registro in ['sabado_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # Para sábado/domingo/feriado, todas as horas são extras
                horas_extras_novas = horas_trabalhadas
            else:
                # Outros tipos mantém cálculo atual
                horas_extras_novas = horas_extras_antigas
            
            # 4. Atualizar apenas se houve mudança
            if abs(horas_extras_novas - horas_extras_antigas) > 0.01:  # Diferença > 1 centésimo
                registro.horas_extras = round(horas_extras_novas, 2)
                registros_corrigidos += 1
                
                # Log da correção
                print(f"✅ ID {registro.id} - {funcionario.nome} ({registro.data})")
                print(f"   Horário padrão: {horas_padrao}h")
                print(f"   Horas trabalhadas: {horas_trabalhadas}h")
                print(f"   Horas extras: {horas_extras_antigas}h → {horas_extras_novas}h")
                print(f"   Tipo: {registro.tipo_registro}")
                print()
        
        # 5. Salvar alterações
        if registros_corrigidos > 0:
            db.session.commit()
            print(f"💾 {registros_corrigidos} registros corrigidos e salvos!")
        else:
            print("ℹ️ Nenhuma correção necessária - todos os cálculos já estão corretos!")
        
        print("=" * 80)
        print("🎯 CORREÇÃO FINALIZADA COM SUCESSO!")
        
        # 6. Relatório final
        print(f"\n📈 RELATÓRIO FINAL:")
        print(f"   • Total analisado: {total_registros} registros")
        print(f"   • Registros corrigidos: {registros_corrigidos}")
        print(f"   • Taxa de correção: {(registros_corrigidos/total_registros*100):.1f}%")

if __name__ == "__main__":
    corrigir_calculo_horas_extras()