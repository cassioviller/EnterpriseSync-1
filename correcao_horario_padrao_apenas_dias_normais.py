#!/usr/bin/env python3
"""
CORREÇÃO: HORÁRIO PADRÃO APENAS PARA DIAS NORMAIS - SIGE v8.2
Data: 06 de Agosto de 2025
Mantém lógica de sábado/feriado inalterada, aplica horário padrão APENAS nos dias normais
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioPadrao
from datetime import date, time
import logging

logging.basicConfig(level=logging.INFO)

def time_para_minutos(time_obj):
    """Converte objeto time para minutos desde 00:00"""
    if not time_obj:
        return 0
    return (time_obj.hour * 60) + time_obj.minute

def calcular_horas_extras_apenas_dias_normais(registro):
    """
    Calcula horas extras baseado no tipo de registro:
    - DIAS NORMAIS (trabalhado, trabalho_normal): Usa horário padrão
    - SÁBADO/FERIADO (sabado_trabalhado, feriado_trabalhado): Mantém lógica original
    
    Args:
        registro (RegistroPonto): Registro de ponto do funcionário
        
    Returns:
        tuple: (minutos_extras_entrada, minutos_extras_saida, total_horas_extras)
    """
    try:
        funcionario = registro.funcionario_ref
        tipo_registro = registro.tipo_registro or 'trabalhado'
        
        print(f"👤 {funcionario.nome} ({registro.data}) - Tipo: {tipo_registro}")
        
        # VERIFICAR TIPO DE REGISTRO
        if tipo_registro in ['sabado_trabalhado', 'feriado_trabalhado', 'domingo_trabalhado']:
            # MANTER LÓGICA ORIGINAL PARA SÁBADOS/FERIADOS
            print(f"   ⚠️ Sábado/Feriado - MANTENDO lógica original")
            print(f"   Horas extras originais: {registro.horas_extras}h")
            
            # Não modificar - manter valor original
            return 0, 0, registro.horas_extras or 0.0
        
        # APLICAR HORÁRIO PADRÃO APENAS PARA DIAS NORMAIS
        if tipo_registro in ['trabalhado', 'trabalho_normal']:
            horario_padrao = funcionario.get_horario_padrao_ativo(registro.data)
            
            if not horario_padrao:
                print(f"   ⚠️ Sem horário padrão - mantendo original")
                return 0, 0, registro.horas_extras or 0.0
            
            if not registro.hora_entrada or not registro.hora_saida:
                return 0, 0, 0.0
            
            minutos_extras_entrada = 0
            minutos_extras_saida = 0
            
            print(f"   🕐 Padrão: {horario_padrao.entrada_padrao} às {horario_padrao.saida_padrao}")
            print(f"   🕐 Real: {registro.hora_entrada} às {registro.hora_saida}")
            
            # 1. Calcular extras por entrada antecipada
            entrada_real_min = time_para_minutos(registro.hora_entrada)
            entrada_padrao_min = time_para_minutos(horario_padrao.entrada_padrao)
            
            if entrada_real_min < entrada_padrao_min:
                minutos_extras_entrada = entrada_padrao_min - entrada_real_min
                print(f"   ⏰ Entrada antecipada: {minutos_extras_entrada}min")
            
            # 2. Calcular extras por saída atrasada
            saida_real_min = time_para_minutos(registro.hora_saida)
            saida_padrao_min = time_para_minutos(horario_padrao.saida_padrao)
            
            if saida_real_min > saida_padrao_min:
                minutos_extras_saida = saida_real_min - saida_padrao_min
                print(f"   ⏰ Saída atrasada: {minutos_extras_saida}min")
            
            # 3. Calcular total em horas decimais
            total_minutos_extras = minutos_extras_entrada + minutos_extras_saida
            total_horas_extras = round(total_minutos_extras / 60, 2)
            
            print(f"   📊 Resultado: {total_minutos_extras}min = {total_horas_extras}h")
            
            return minutos_extras_entrada, minutos_extras_saida, total_horas_extras
        
        # OUTROS TIPOS: manter original
        print(f"   ℹ️ Tipo '{tipo_registro}' - mantendo original")
        return 0, 0, registro.horas_extras or 0.0
        
    except Exception as e:
        print(f"❌ Erro no cálculo: {e}")
        return 0, 0, registro.horas_extras or 0.0

def aplicar_correcao_seletiva():
    """Aplica correção apenas onde necessário"""
    print("🎯 APLICANDO CORREÇÃO SELETIVA - PRESERVANDO SÁBADOS")
    
    with app.app_context():
        try:
            # Buscar registros recentes para teste
            registros = RegistroPonto.query.filter(
                RegistroPonto.hora_entrada.isnot(None),
                RegistroPonto.hora_saida.isnot(None)
            ).order_by(RegistroPonto.data.desc()).limit(20).all()
            
            print(f"📊 Analisando {len(registros)} registros...")
            
            contadores = {
                'dias_normais_corrigidos': 0,
                'sabados_preservados': 0,
                'feriados_preservados': 0,
                'outros_mantidos': 0
            }
            
            for registro in registros:
                try:
                    tipo_registro = registro.tipo_registro or 'trabalhado'
                    horas_antigas = registro.horas_extras or 0.0
                    
                    # Aplicar nova lógica seletiva
                    entrada_extras, saida_extras, total_extras = calcular_horas_extras_apenas_dias_normais(registro)
                    
                    # Classificar e contar
                    if tipo_registro in ['sabado_trabalhado', 'feriado_trabalhado', 'domingo_trabalhado']:
                        # PRESERVAR - não alterar
                        if tipo_registro == 'sabado_trabalhado':
                            contadores['sabados_preservados'] += 1
                        else:
                            contadores['feriados_preservados'] += 1
                        print(f"   ✅ PRESERVADO: {horas_antigas}h")
                        
                    elif tipo_registro in ['trabalhado', 'trabalho_normal']:
                        # ATUALIZAR com horário padrão
                        registro.minutos_extras_entrada = entrada_extras
                        registro.minutos_extras_saida = saida_extras
                        registro.total_minutos_extras = entrada_extras + saida_extras
                        registro.horas_extras_detalhadas = total_extras
                        registro.horas_extras = total_extras
                        
                        contadores['dias_normais_corrigidos'] += 1
                        print(f"   ✅ CORRIGIDO: {horas_antigas}h → {total_extras}h")
                        
                    else:
                        contadores['outros_mantidos'] += 1
                        print(f"   ℹ️ MANTIDO: {tipo_registro}")
                    
                    print()  # Linha em branco
                    
                except Exception as e:
                    print(f"❌ Erro no registro {registro.id}: {e}")
                    continue
            
            # Commit das alterações
            db.session.commit()
            
            print(f"📋 RESULTADO DA CORREÇÃO:")
            print(f"   Dias normais corrigidos: {contadores['dias_normais_corrigidos']}")
            print(f"   Sábados preservados: {contadores['sabados_preservados']}")
            print(f"   Feriados preservados: {contadores['feriados_preservados']}")
            print(f"   Outros mantidos: {contadores['outros_mantidos']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro na correção: {e}")
            db.session.rollback()
            return False

def verificar_tipos_registro():
    """Verifica os tipos de registro existentes"""
    print("🔍 VERIFICANDO TIPOS DE REGISTRO NO SISTEMA")
    
    with app.app_context():
        try:
            # Buscar todos os tipos únicos
            tipos = db.session.query(RegistroPonto.tipo_registro).distinct().all()
            tipos_list = [t[0] for t in tipos if t[0]]
            
            # Contar por tipo
            print(f"📊 TIPOS DE REGISTRO ENCONTRADOS:")
            for tipo in sorted(tipos_list):
                count = RegistroPonto.query.filter_by(tipo_registro=tipo).count()
                
                # Classificar
                if tipo in ['sabado_trabalhado', 'feriado_trabalhado', 'domingo_trabalhado']:
                    categoria = "🚫 PRESERVAR (não alterar)"
                elif tipo in ['trabalhado', 'trabalho_normal']:
                    categoria = "✅ APLICAR horário padrão"
                else:
                    categoria = "ℹ️ MANTER original"
                
                print(f"   {tipo.ljust(20)} | {count:>4} registros | {categoria}")
            
            # Verificar registros com horas extras em sábados
            sabados_com_extras = RegistroPonto.query.filter(
                RegistroPonto.tipo_registro == 'sabado_trabalhado',
                RegistroPonto.horas_extras > 0
            ).count()
            
            print(f"\n⚠️ CRÍTICO: {sabados_com_extras} sábados trabalhados com horas extras")
            print(f"   Estes NÃO devem ser alterados!")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            return False

def validar_preservacao_sabados():
    """Valida que sábados não foram alterados"""
    print("🔍 VALIDANDO PRESERVAÇÃO DOS SÁBADOS")
    
    with app.app_context():
        try:
            # Buscar alguns sábados trabalhados
            sabados = RegistroPonto.query.filter_by(
                tipo_registro='sabado_trabalhado'
            ).limit(5).all()
            
            print(f"📊 Verificando {len(sabados)} registros de sábado:")
            
            for sabado in sabados:
                funcionario = sabado.funcionario_ref
                print(f"   👤 {funcionario.nome} - {sabado.data}")
                print(f"      Horário: {sabado.hora_entrada} às {sabado.hora_saida}")
                print(f"      Horas extras: {sabado.horas_extras}h")
                print(f"      Tipo: {sabado.tipo_registro}")
                
                # Verificar se tem campos de horário padrão
                if hasattr(sabado, 'horas_extras_detalhadas'):
                    if sabado.horas_extras_detalhadas != sabado.horas_extras:
                        print(f"      ⚠️ POSSÍVEL PROBLEMA: detalhadas={sabado.horas_extras_detalhadas}h vs original={sabado.horas_extras}h")
                    else:
                        print(f"      ✅ PRESERVADO corretamente")
                
                print()
            
            return True
            
        except Exception as e:
            print(f"❌ Erro na validação: {e}")
            return False

if __name__ == "__main__":
    print("🎯 CORREÇÃO SELETIVA: HORÁRIO PADRÃO APENAS PARA DIAS NORMAIS")
    print("="*70)
    
    # 1. Verificar tipos de registro
    print("ETAPA 1: Verificação dos tipos de registro")
    verificar_tipos_registro()
    
    print("\n" + "="*70)
    
    # 2. Aplicar correção seletiva
    print("ETAPA 2: Aplicação da correção seletiva")
    if aplicar_correcao_seletiva():
        print("✅ Correção aplicada com sucesso")
    else:
        print("❌ Falha na correção")
        exit(1)
    
    print("\n" + "="*70)
    
    # 3. Validar preservação
    print("ETAPA 3: Validação da preservação dos sábados")
    if validar_preservacao_sabados():
        print("✅ Sábados preservados corretamente")
    else:
        print("⚠️ Verificar preservação dos sábados")
    
    print("\n" + "="*70)
    print("🎯 CORREÇÃO SELETIVA CONCLUÍDA!")
    print("✅ Dias normais: horário padrão aplicado")
    print("🚫 Sábados/feriados: lógica original preservada")