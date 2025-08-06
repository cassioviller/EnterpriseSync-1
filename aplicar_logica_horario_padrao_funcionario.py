#!/usr/bin/env python3
"""
APLICAR LÓGICA DE HORAS EXTRAS BASEADA NO HORÁRIO PADRÃO DO FUNCIONÁRIO
Implementação específica para usar horários cadastrados em 'horários de trabalho'
APENAS para dias normais - não afeta sábados, domingos ou feriados
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import time, date

def aplicar_nova_logica_horario_funcionario():
    """
    Aplica lógica correta de horas extras baseada no horário cadastrado do funcionário
    """
    with app.app_context():
        print("🕐 APLICANDO LÓGICA DE HORAS EXTRAS BASEADA EM HORÁRIO DO FUNCIONÁRIO")
        print("=" * 70)
        
        # Buscar registros de dias normais recentes
        registros = RegistroPonto.query.filter(
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None),
            RegistroPonto.tipo_registro == 'trabalho_normal',
            RegistroPonto.data >= date(2025, 7, 20)
        ).order_by(RegistroPonto.data.desc()).limit(20).all()
        
        print(f"📊 PROCESSANDO {len(registros)} REGISTROS")
        
        corrigidos = 0
        
        for registro in registros:
            try:
                funcionario = registro.funcionario_ref
                print(f"\n👤 {funcionario.nome} - {registro.data}")
                print(f"   Horário real: {registro.hora_entrada} às {registro.hora_saida}")
                
                # Obter horário padrão
                if hasattr(funcionario, 'horario_trabalho_ref') and funcionario.horario_trabalho_ref:
                    entrada_padrao = funcionario.horario_trabalho_ref.entrada
                    saida_padrao = funcionario.horario_trabalho_ref.saida
                    print(f"   Horário padrão: {entrada_padrao} às {saida_padrao} (cadastrado)")
                else:
                    entrada_padrao = time(7, 12)
                    saida_padrao = time(17, 0)
                    print(f"   Horário padrão: 07:12 às 17:00 (sistema)")
                
                # Converter para minutos
                entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                entrada_padrao_min = entrada_padrao.hour * 60 + entrada_padrao.minute
                saida_padrao_min = saida_padrao.hour * 60 + saida_padrao.minute
                
                # CALCULAR HORAS EXTRAS: chegou antes OU saiu depois
                extra_entrada_min = max(0, entrada_padrao_min - entrada_real_min)  # Chegou antes
                extra_saida_min = max(0, saida_real_min - saida_padrao_min)       # Saiu depois
                total_extra_min = extra_entrada_min + extra_saida_min
                total_extra_h = round(total_extra_min / 60.0, 2)
                
                # Valores antigos
                extras_antigas = registro.horas_extras or 0
                
                print(f"   Extras entrada: {extra_entrada_min}min")
                print(f"   Extras saída: {extra_saida_min}min")
                print(f"   Total: {total_extra_min}min = {total_extra_h}h")
                print(f"   Antes: {extras_antigas}h → Depois: {total_extra_h}h")
                
                # Aplicar nova lógica
                registro.horas_extras = total_extra_h
                
                if abs(extras_antigas - total_extra_h) > 0.01:
                    corrigidos += 1
                    print(f"   ✅ CORRIGIDO!")
                else:
                    print(f"   ℹ️ Sem alteração")
                
            except Exception as e:
                print(f"   ❌ ERRO: {e}")
                continue
        
        # Salvar alterações
        try:
            db.session.commit()
            print(f"\n📋 RESULTADO FINAL:")
            print(f"   Registros processados: {len(registros)}")
            print(f"   Registros corrigidos: {corrigidos}")
            print("   ✅ ALTERAÇÕES SALVAS!")
        except Exception as e:
            print(f"   ❌ ERRO AO SALVAR: {e}")
            db.session.rollback()

if __name__ == "__main__":
    aplicar_nova_logica_horario_funcionario()