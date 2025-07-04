#!/usr/bin/env python3
"""
Script para corrigir os KPIs do funcionário Pedro Lima Sousa
Recalcula atrasos e verifica faltas conforme especificação
"""

from app import app, db
from kpis_engine_v3 import atualizar_calculos_ponto, identificar_faltas_periodo
from models import RegistroPonto, Funcionario
from datetime import datetime, date
from sqlalchemy import and_

def corrigir_kpis_pedro():
    """Corrige os KPIs do Pedro Lima Sousa"""
    
    with app.app_context():
        print("🔄 Iniciando correção dos KPIs do Pedro Lima Sousa...")
        
        # Buscar Pedro Lima Sousa
        pedro = Funcionario.query.filter_by(nome="Pedro Lima Sousa").first()
        if not pedro:
            print("❌ Pedro Lima Sousa não encontrado!")
            return
        
        print(f"✅ Pedro encontrado: ID {pedro.id}, Código {pedro.codigo}")
        print(f"📅 Horário de trabalho: {pedro.horario_trabalho.nome if pedro.horario_trabalho else 'Não definido'}")
        
        # Período de junho 2025
        data_inicio = date(2025, 6, 1)
        data_fim = date(2025, 6, 30)
        
        print(f"📊 Analisando período: {data_inicio} a {data_fim}")
        
        # Buscar registros de ponto do Pedro em junho
        registros = RegistroPonto.query.filter(
            and_(
                RegistroPonto.funcionario_id == pedro.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim
            )
        ).order_by(RegistroPonto.data.desc()).all()
        
        print(f"📋 Encontrados {len(registros)} registros de ponto")
        
        # Recalcular cada registro
        print("\n🔄 Recalculando atrasos...")
        for registro in registros:
            print(f"📅 {registro.data}: ", end="")
            
            if registro.hora_entrada:
                # Calcular atraso manualmente para verificar
                if pedro.horario_trabalho and pedro.horario_trabalho.entrada:
                    entrada_esperada = pedro.horario_trabalho.entrada
                    entrada_real = registro.hora_entrada
                    
                    if entrada_real > entrada_esperada:
                        entrada_dt_esperada = datetime.combine(registro.data, entrada_esperada)
                        entrada_dt_real = datetime.combine(registro.data, entrada_real)
                        atraso_entrada = (entrada_dt_real - entrada_dt_esperada).total_seconds() / 60
                        print(f"Entrada {entrada_real} (atraso: {atraso_entrada:.0f}min)", end="")
                    else:
                        print(f"Entrada {entrada_real} (pontual)", end="")
                
                # Verificar saída antecipada
                if pedro.horario_trabalho and pedro.horario_trabalho.saida and registro.hora_saida:
                    saida_esperada = pedro.horario_trabalho.saida
                    saida_real = registro.hora_saida
                    
                    if saida_real < saida_esperada:
                        saida_dt_esperada = datetime.combine(registro.data, saida_esperada)
                        saida_dt_real = datetime.combine(registro.data, saida_real)
                        atraso_saida = (saida_dt_esperada - saida_dt_real).total_seconds() / 60
                        print(f" - Saída {saida_real} (antecipada: {atraso_saida:.0f}min)")
                    else:
                        print(f" - Saída {saida_real} (normal)")
                else:
                    print("")
            else:
                print("FALTA")
            
            # Recalcular usando o engine
            atualizar_calculos_ponto(registro.id)
        
        print("\n📊 Verificando faltas...")
        
        # Identificar faltas usando a função do engine
        faltas_identificadas = identificar_faltas_periodo(pedro.id, data_inicio, data_fim)
        print(f"📈 Faltas identificadas: {len(faltas_identificadas)} dias")
        
        for falta in sorted(faltas_identificadas):
            print(f"   - {falta}")
        
        # Verificar atrasos calculados
        print("\n📊 Verificando atrasos calculados...")
        
        registros_com_atraso = RegistroPonto.query.filter(
            and_(
                RegistroPonto.funcionario_id == pedro.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim,
                RegistroPonto.total_atraso_minutos > 0
            )
        ).all()
        
        total_atrasos_minutos = sum(r.total_atraso_minutos for r in registros_com_atraso)
        total_atrasos_horas = total_atrasos_minutos / 60
        
        print(f"📈 Registros com atraso: {len(registros_com_atraso)}")
        print(f"📈 Total atrasos: {total_atrasos_minutos:.0f} minutos ({total_atrasos_horas:.2f} horas)")
        
        for r in registros_com_atraso:
            print(f"   - {r.data}: {r.total_atraso_minutos:.0f}min")
        
        print("\n✅ Correção concluída!")
        print(f"📊 Resumo final:")
        print(f"   - Faltas: {len(faltas_identificadas)}")
        print(f"   - Atrasos: {total_atrasos_horas:.2f} horas")

if __name__ == "__main__":
    corrigir_kpis_pedro()