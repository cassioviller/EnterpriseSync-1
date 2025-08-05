#!/usr/bin/env python3
"""
🔍 DEBUG: Investigar e corrigir lógica incorreta de horas extras
Problema identificado: 34min → 1.4h (deveria ser 0.57h), 98min → 2.4h (deveria ser 1.63h)
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, datetime, time
from sqlalchemy import and_

def debug_calculo_horas_extras():
    """Investigar registros com valores suspeitos de horas extras"""
    
    with app.app_context():
        print("🔍 DEBUGANDO CÁLCULO DE HORAS EXTRAS...")
        print("=" * 60)
        
        # Buscar registros com horas extras suspeitas (valores como 1.4, 2.4, etc.)
        registros_suspeitos = RegistroPonto.query.filter(
            RegistroPonto.horas_extras.isnot(None),
            RegistroPonto.horas_extras > 0
        ).order_by(RegistroPonto.data.desc()).limit(20).all()
        
        print(f"\n📊 ANALISANDO {len(registros_suspeitos)} REGISTROS COM HORAS EXTRAS:")
        print("-" * 60)
        
        problemas_encontrados = []
        
        for i, registro in enumerate(registros_suspeitos, 1):
            print(f"\n{i}. REGISTRO ID {registro.id}:")
            print(f"   📅 Data: {registro.data}")
            print(f"   👤 Funcionário: {registro.funcionario_ref.nome if registro.funcionario_ref else 'N/A'}")
            print(f"   📝 Tipo: {registro.tipo_registro}")
            
            # Horários
            print(f"   🕐 Entrada: {registro.hora_entrada}")
            print(f"   🕕 Saída: {registro.hora_saida}")
            print(f"   🍽️  Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
            
            # Valores atuais
            print(f"   📈 Horas trabalhadas: {registro.horas_trabalhadas}")
            print(f"   ⏰ Horas extras (ATUAL): {registro.horas_extras}")
            print(f"   📊 Percentual extras: {registro.percentual_extras}%")
            print(f"   🔢 Tipo do campo: {type(registro.horas_extras)}")
            
            # INVESTIGAR SE É PROBLEMA DE CONCATENAÇÃO
            horas_extras_str = str(registro.horas_extras)
            if '.' in horas_extras_str:
                partes = horas_extras_str.split('.')
                if len(partes) == 2:
                    parte_inteira = partes[0] 
                    parte_decimal = partes[1]
                    
                    # Verificar se pode ser concatenação de horas.minutos
                    if len(parte_decimal) <= 2 and parte_decimal.isdigit():
                        minutos_suspeitos = int(parte_decimal)
                        if minutos_suspeitos < 60:  # Minutos válidos
                            print(f"   🚨 POSSÍVEL CONCATENAÇÃO: {horas_extras_str} pode ser {parte_inteira}h{parte_decimal}min")
                            
                            # Calcular o que deveria ser em decimal
                            horas_corretas = int(parte_inteira) + (minutos_suspeitos / 60.0)
                            print(f"   ✅ VALOR CORRETO: {horas_corretas:.2f}h")
                            
                            problemas_encontrados.append({
                                'id': registro.id,
                                'valor_atual': registro.horas_extras,
                                'valor_correto': horas_corretas,
                                'tipo_problema': 'concatenacao'
                            })
            
            # CALCULAR O QUE DEVERIA SER BASEADO NOS HORÁRIOS
            if registro.hora_entrada and registro.hora_saida:
                entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                
                # Considerar almoço
                almoco_min = 0
                if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                    almoco_saida_min = registro.hora_almoco_saida.hour * 60 + registro.hora_almoco_saida.minute
                    almoco_retorno_min = registro.hora_almoco_retorno.hour * 60 + registro.hora_almoco_retorno.minute
                    almoco_min = almoco_retorno_min - almoco_saida_min
                elif registro.tipo_registro == 'trabalho_normal':
                    almoco_min = 60  # 1h padrão
                
                total_minutos_trabalhados = saida_min - entrada_min - almoco_min
                horas_trabalhadas_corretas = max(0, total_minutos_trabalhados / 60.0)
                
                print(f"   🧮 CÁLCULO MANUAL:")
                print(f"      Entrada: {entrada_min}min, Saída: {saida_min}min, Almoço: {almoco_min}min")
                print(f"      Total trabalhado: {total_minutos_trabalhados}min = {horas_trabalhadas_corretas:.2f}h")
                
                # Para tipos especiais (sábado, domingo, feriado), todas as horas são extras
                if registro.tipo_registro in ['sabado_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                    extras_corretas = horas_trabalhadas_corretas
                    print(f"   🎯 Extras corretas ({registro.tipo_registro}): {extras_corretas:.2f}h (todas as horas)")
                else:
                    # Para trabalho normal, extras = trabalhadas - 8h
                    extras_corretas = max(0, horas_trabalhadas_corretas - 8.0)
                    print(f"   🎯 Extras corretas (trabalho normal): {extras_corretas:.2f}h")
                
                # Comparar com valor atual
                diferenca = abs(registro.horas_extras - extras_corretas)
                if diferenca > 0.1:  # Diferença significativa
                    print(f"   ❌ DIFERENÇA ENCONTRADA: {registro.horas_extras:.2f}h vs {extras_corretas:.2f}h")
                    problemas_encontrados.append({
                        'id': registro.id,
                        'valor_atual': registro.horas_extras,
                        'valor_correto': extras_corretas,
                        'tipo_problema': 'calculo_incorreto'
                    })
                else:
                    print(f"   ✅ VALOR CORRETO")
        
        # RESUMO DOS PROBLEMAS
        print("\n" + "=" * 60)
        print("📋 RESUMO DOS PROBLEMAS ENCONTRADOS:")
        print("=" * 60)
        
        if not problemas_encontrados:
            print("✅ NENHUM PROBLEMA ENCONTRADO nos registros analisados")
        else:
            concatenacao = [p for p in problemas_encontrados if p['tipo_problema'] == 'concatenacao']
            calculo = [p for p in problemas_encontrados if p['tipo_problema'] == 'calculo_incorreto']
            
            print(f"🚨 TOTAL DE PROBLEMAS: {len(problemas_encontrados)}")
            print(f"   📝 Concatenação: {len(concatenacao)} registros")
            print(f"   🧮 Cálculo incorreto: {len(calculo)} registros")
            
            print("\n📊 DETALHES DOS PROBLEMAS:")
            for problema in problemas_encontrados:
                print(f"   ID {problema['id']}: {problema['valor_atual']:.2f}h → {problema['valor_correto']:.2f}h ({problema['tipo_problema']})")
        
        return problemas_encontrados

def buscar_padrao_especifico():
    """Buscar especificamente por padrões como 1.4h, 2.4h mencionados pelo usuário"""
    
    with app.app_context():
        print("\n🔍 BUSCANDO PADRÕES ESPECÍFICOS (1.4h, 2.4h)...")
        print("=" * 50)
        
        # Buscar valores suspeitos (1.4, 2.4, etc.) - valores que podem ser concatenação
        registros_suspeitos = RegistroPonto.query.filter(
            RegistroPonto.horas_extras.isnot(None),
            RegistroPonto.horas_extras > 0
        ).all()
        
        padroes_suspeitos = []
        
        for r in registros_suspeitos:
            valor = float(r.horas_extras)
            # Verificar se o valor pode ser resultado de concatenação (ex: 1.4 = 1h4min)
            if valor > 0:
                valor_str = f"{valor:.1f}"
                if '.' in valor_str:
                    partes = valor_str.split('.')
                    if len(partes) == 2:
                        decimal = int(partes[1])
                        # Se a parte decimal for < 60, pode ser minutos concatenados
                        if decimal < 60 and decimal > 0:
                            padroes_suspeitos.append(r)
        
        print(f"📊 Registros com padrão suspeito: {len(padroes_suspeitos)}")
        for r in padroes_suspeitos[:10]:  # Mostrar apenas os primeiros 10
            print(f"   ID {r.id}: {r.horas_extras}h em {r.data} ({r.funcionario_ref.nome if r.funcionario_ref else 'N/A'})")
        
        # Buscar especificamente valores como 1.4 e 2.4
        valor_14 = RegistroPonto.query.filter(
            RegistroPonto.horas_extras >= 1.39,
            RegistroPonto.horas_extras <= 1.41
        ).all()
        
        valor_24 = RegistroPonto.query.filter(
            RegistroPonto.horas_extras >= 2.39,
            RegistroPonto.horas_extras <= 2.41
        ).all()
        
        print(f"\n🎯 Registros com ~1.4h: {len(valor_14)}")
        print(f"🎯 Registros com ~2.4h: {len(valor_24)}")

        return padroes_suspeitos

def corrigir_concatenacao(problemas):
    """Corrigir problemas de concatenação identificados"""
    
    if not problemas:
        return
        
    with app.app_context():
        print("\n🔧 CORRIGINDO PROBLEMAS DE CONCATENAÇÃO...")
        print("=" * 50)
        
        corrigidos = 0
        for problema in problemas:
            if problema['tipo_problema'] == 'concatenacao':
                registro = RegistroPonto.query.get(problema['id'])
                if registro:
                    valor_antigo = registro.horas_extras
                    registro.horas_extras = problema['valor_correto']
                    
                    print(f"   ✅ ID {problema['id']}: {valor_antigo:.2f}h → {problema['valor_correto']:.2f}h")
                    corrigidos += 1
        
        if corrigidos > 0:
            db.session.commit()
            print(f"\n✅ {corrigidos} registros corrigidos com sucesso!")
        else:
            print("\n❌ Nenhum registro de concatenação para corrigir")

def testar_casos_especificos():
    """Testar casos específicos mencionados: 34min → 1.4h, 98min → 2.4h"""
    
    print("\n🧪 TESTANDO CONVERSÕES CORRETAS:")
    print("=" * 40)
    
    casos = [
        {"minutos": 34, "esperado": 0.57},
        {"minutos": 98, "esperado": 1.63},
        {"minutos": 60, "esperado": 1.00},
        {"minutos": 30, "esperado": 0.50},
        {"minutos": 90, "esperado": 1.50},
    ]
    
    for caso in casos:
        horas_corretas = caso["minutos"] / 60.0
        print(f"   {caso['minutos']:2d}min → {horas_corretas:.2f}h (esperado: {caso['esperado']:.2f}h) {'✅' if abs(horas_corretas - caso['esperado']) < 0.01 else '❌'}")

if __name__ == "__main__":
    print("🚨 ANÁLISE COMPLETA DE HORAS EXTRAS")
    print("="*60)
    
    # 1. Testar conversões básicas
    testar_casos_especificos()
    
    # 2. Buscar padrões específicos
    buscar_padrao_especifico()
    
    # 3. Debug completo dos registros
    problemas = debug_calculo_horas_extras()
    
    # 4. Oferecer correção
    if problemas:
        resposta = input("\n🔧 Deseja corrigir os problemas encontrados? (s/n): ")
        if resposta.lower() in ['s', 'sim', 'y', 'yes']:
            corrigir_concatenacao(problemas)
    
    print("\n🎯 ANÁLISE CONCLUÍDA!")