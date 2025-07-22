#!/usr/bin/env python3
"""
Script para popular registros de ponto completos para funcionários Vale Verde
Criar dados realistas para julho/2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Funcionario, RegistroPonto, Obra
from datetime import datetime, date, time
import random

def popular_ponto_vale_verde():
    """Popula registros de ponto para funcionários Vale Verde"""
    
    with app.app_context():
        print("=== POPULANDO REGISTROS DE PONTO VALE VERDE ===\n")
        
        # 1. Obter funcionários Vale Verde
        funcionarios_vv = Funcionario.query.filter(
            Funcionario.codigo.like('VV%')
        ).order_by(Funcionario.codigo).all()
        
        print(f"Funcionários Vale Verde encontrados: {len(funcionarios_vv)}")
        
        # 2. Obter obra Vale Verde
        obra_vv = Obra.query.filter_by(admin_id=10).first()
        if not obra_vv:
            print("❌ Nenhuma obra Vale Verde encontrada!")
            return
            
        print(f"Obra selecionada: {obra_vv.nome}")
        
        # 3. Limpar registros existentes para recriação
        funcionarios_ids = [f.id for f in funcionarios_vv]
        registros_existentes = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id.in_(funcionarios_ids)
        ).count()
        
        print(f"Registros existentes: {registros_existentes}")
        
        if registros_existentes > 0:
            print("Limpando registros existentes...")
            RegistroPonto.query.filter(
                RegistroPonto.funcionario_id.in_(funcionarios_ids)
            ).delete()
            db.session.commit()
        
        # 4. Gerar dados para julho/2025
        print(f"\n4. GERANDO REGISTROS PARA JULHO/2025:")
        
        # Dias úteis de julho/2025 (segunda a sexta)
        dias_uteis = []
        for dia in range(1, 32):  # julho tem 31 dias
            data_atual = date(2025, 7, dia)
            # Segunda=0, Domingo=6
            if data_atual.weekday() < 5:  # Segunda a sexta
                dias_uteis.append(data_atual)
        
        print(f"Dias úteis em julho: {len(dias_uteis)}")
        
        # Tipos de registro com probabilidades
        tipos_registro = [
            ('trabalho_normal', 0.75),  # 75% trabalho normal
            ('falta', 0.05),           # 5% faltas
            ('falta_justificada', 0.05),  # 5% faltas justificadas
            ('meio_periodo', 0.05),    # 5% meio período
            ('sabado_horas_extras', 0.05),  # 5% sábado extras
            ('domingo_horas_extras', 0.05)  # 5% domingo extras
        ]
        
        registros_criados = 0
        
        # Para cada funcionário
        for funcionario in funcionarios_vv:
            print(f"\n   Criando registros para {funcionario.nome} ({funcionario.codigo}):")
            
            # Para cada dia útil
            for data_trabalho in dias_uteis:
                # Determinar tipo de registro aleatoriamente
                rand = random.random()
                acumulado = 0
                tipo_registro = 'trabalho_normal'
                
                for tipo, probabilidade in tipos_registro:
                    acumulado += probabilidade
                    if rand <= acumulado:
                        tipo_registro = tipo
                        break
                
                # Horários padrão
                entrada = time(7, 30)
                saida_almoco = time(12, 0)
                retorno_almoco = time(13, 0)
                saida = time(17, 0)
                
                # Ajustar horários baseado no tipo
                horas_trabalhadas = 8.0
                horas_extras = 0.0
                observacoes = ""
                
                if tipo_registro == 'trabalho_normal':
                    # Algumas variações nos horários
                    if random.random() < 0.2:  # 20% chance de horas extras
                        saida = time(18, 0)  # 1h extra
                        horas_trabalhadas = 9.0
                        horas_extras = 1.0
                        observacoes = "1h extra trabalhada"
                    elif random.random() < 0.1:  # 10% chance de atraso
                        entrada = time(8, 0)  # 30min atraso
                        horas_trabalhadas = 7.5
                        observacoes = "Atraso de 30 minutos"
                
                elif tipo_registro == 'falta':
                    entrada = None
                    saida = None
                    saida_almoco = None
                    retorno_almoco = None
                    horas_trabalhadas = 0.0
                    observacoes = "Falta não justificada"
                
                elif tipo_registro == 'falta_justificada':
                    entrada = None
                    saida = None
                    saida_almoco = None
                    retorno_almoco = None
                    horas_trabalhadas = 0.0
                    observacoes = "Atestado médico"
                
                elif tipo_registro == 'meio_periodo':
                    saida = time(12, 0)
                    saida_almoco = None
                    retorno_almoco = None
                    horas_trabalhadas = 4.0
                    observacoes = "Meio período - manhã"
                
                elif tipo_registro == 'sabado_horas_extras':
                    # Trabalho em sábado - usar data original
                    entrada = time(8, 0)
                    saida = time(12, 0)
                    saida_almoco = None
                    retorno_almoco = None
                    horas_trabalhadas = 4.0
                    horas_extras = 4.0  # 100% extra no sábado
                    observacoes = "Sábado - horas extras 100%"
                    tipo_registro = 'sabado_horas_extras'
                
                elif tipo_registro == 'domingo_horas_extras':
                    # Trabalho em domingo - usar data original
                    entrada = time(8, 0)
                    saida = time(12, 0)
                    saida_almoco = None
                    retorno_almoco = None
                    horas_trabalhadas = 4.0
                    horas_extras = 4.0  # 100% extra no domingo
                    observacoes = "Domingo - horas extras 100%"
                    tipo_registro = 'domingo_horas_extras'
                
                # Criar registro
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    obra_id=obra_vv.id,
                    data=data_trabalho,
                    hora_entrada=entrada,
                    hora_saida=saida,
                    hora_almoco_saida=saida_almoco,
                    hora_almoco_retorno=retorno_almoco,
                    tipo_registro=tipo_registro,
                    horas_trabalhadas=horas_trabalhadas,
                    horas_extras=horas_extras,
                    observacoes=observacoes
                )
                
                db.session.add(registro)
                registros_criados += 1
                
                if registros_criados % 50 == 0:
                    print(f"     {registros_criados} registros criados...")
        
        # Commit final
        db.session.commit()
        
        print(f"\n5. RESULTADO FINAL:")
        print(f"   ✅ Total de registros criados: {registros_criados}")
        print(f"   ✅ Média por funcionário: {registros_criados // len(funcionarios_vv)} registros")
        
        # Verificação por tipo
        for tipo, _ in tipos_registro:
            count = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id.in_(funcionarios_ids),
                RegistroPonto.tipo_registro == tipo
            ).count()
            print(f"   - {tipo}: {count} registros")
        
        print(f"\n✅ REGISTROS DE PONTO VALE VERDE POPULADOS COM SUCESSO!")
        print(f"✅ Agora as KPIs devem mostrar dados realistas")
        print(f"\nLogin Vale Verde: valeverde/admin123")

if __name__ == "__main__":
    popular_ponto_vale_verde()