#!/usr/bin/env python3
"""
Script para debug dos tipos de registro do Cássio
"""

from app import app
from models import Funcionario, RegistroPonto
from datetime import date

def debug_tipos_registro():
    """
    Debug dos tipos de registro do Cássio
    """
    
    with app.app_context():
        # Buscar funcionário Cássio
        cassio = Funcionario.query.filter_by(nome="Cássio Viller Silva de Azevedo").first()
        if not cassio:
            print("Funcionário Cássio não encontrado!")
            return
        
        # Buscar registros de junho/2025
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == cassio.id,
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).order_by(RegistroPonto.data).all()
        
        print(f"Total de registros: {len(registros)}")
        print("\nTipos de registro por data:")
        
        # Contar tipos
        tipos_count = {}
        for registro in registros:
            tipo = registro.tipo_registro
            if tipo not in tipos_count:
                tipos_count[tipo] = 0
            tipos_count[tipo] += 1
            
            print(f"{registro.data.strftime('%d/%m/%Y')} - {tipo}")
        
        print(f"\nResumo por tipo:")
        for tipo, count in tipos_count.items():
            print(f"- {tipo}: {count}")
        
        # Contar dias programados (excluindo sábados e domingos não trabalhados)
        tipos_programados = [
            'trabalho_normal', 'sabado_horas_extras', 'domingo_horas_extras',
            'feriado_trabalhado', 'meio_periodo', 'falta', 'falta_justificada',
            'atraso', 'saida_antecipada'
        ]
        
        registros_programados = [
            r for r in registros 
            if r.tipo_registro in tipos_programados
        ]
        
        dias_programados = set(r.data for r in registros_programados)
        
        print(f"\nDias programados (excluindo sábados/domingos não trabalhados): {len(dias_programados)}")
        print("Dias programados:")
        for data in sorted(dias_programados):
            registro = next(r for r in registros if r.data == data)
            print(f"- {data.strftime('%d/%m/%Y (%A)')} - {registro.tipo_registro}")
        
        # Contar apenas dias úteis (nova correção)
        tipos_dias_uteis = [
            'trabalho_normal', 'feriado_trabalhado', 'meio_periodo', 
            'falta', 'falta_justificada', 'atraso', 'saida_antecipada'
        ]
        
        registros_dias_uteis = [
            r for r in registros 
            if r.tipo_registro in tipos_dias_uteis
        ]
        
        dias_uteis = set(r.data for r in registros_dias_uteis)
        
        print(f"\nDias úteis (CORREÇÃO - excluindo fins de semana): {len(dias_uteis)}")
        print("Dias úteis:")
        for data in sorted(dias_uteis):
            registro = next(r for r in registros if r.data == data)
            print(f"- {data.strftime('%d/%m/%Y (%A)')} - {registro.tipo_registro}")

if __name__ == "__main__":
    debug_tipos_registro()