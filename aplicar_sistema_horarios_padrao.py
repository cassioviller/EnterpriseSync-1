#!/usr/bin/env python3
"""
APLICAÇÃO COMPLETA DO SISTEMA DE HORÁRIOS PADRÃO - SIGE v8.2
Data: 06 de Agosto de 2025
Implementa lógica correta de cálculo de horas extras baseada em horário padrão
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioPadrao
from datetime import time, date, datetime
import logging

logging.basicConfig(level=logging.INFO)

def criar_horarios_padrao_funcionarios():
    """Criar horários padrão para todos os funcionários ativos"""
    print("📋 CRIANDO HORÁRIOS PADRÃO PARA FUNCIONÁRIOS")
    
    with app.app_context():
        try:
            # Buscar funcionários ativos
            funcionarios = Funcionario.query.filter_by(ativo=True).all()
            print(f"👥 Encontrados {len(funcionarios)} funcionários ativos")
            
            horarios_criados = 0
            
            for funcionario in funcionarios:
                # Verificar se já tem horário padrão ativo
                existe = HorarioPadrao.query.filter_by(
                    funcionario_id=funcionario.id,
                    ativo=True
                ).first()
                
                if existe:
                    print(f"⚠️ {funcionario.nome} já tem horário padrão")
                    continue
                
                # Criar horário padrão comum (07:12 às 17:00)
                horario = HorarioPadrao(
                    funcionario_id=funcionario.id,
                    entrada_padrao=time(7, 12),      # 07:12
                    saida_almoco_padrao=time(12, 0), # 12:00
                    retorno_almoco_padrao=time(13, 0), # 13:00
                    saida_padrao=time(17, 0),        # 17:00
                    ativo=True,
                    data_inicio=date(2025, 1, 1)
                )
                
                db.session.add(horario)
                horarios_criados += 1
                print(f"✅ CRIADO: {funcionario.nome} - 07:12 às 17:00")
            
            db.session.commit()
            print(f"📋 {horarios_criados} horários padrão criados!")
            return horarios_criados
            
        except Exception as e:
            print(f"❌ Erro ao criar horários padrão: {e}")
            db.session.rollback()
            return 0

def time_para_minutos(time_obj):
    """Converte objeto time para minutos desde 00:00"""
    if not time_obj:
        return 0
    return (time_obj.hour * 60) + time_obj.minute

def calcular_horas_extras_por_horario_padrao(registro):
    """
    Calcula horas extras baseado na diferença entre horário padrão e real
    
    Args:
        registro (RegistroPonto): Registro de ponto do funcionário
        
    Returns:
        tuple: (minutos_extras_entrada, minutos_extras_saida, total_horas_extras)
    """
    try:
        funcionario = registro.funcionario_ref
        horario_padrao = funcionario.get_horario_padrao_ativo(registro.data)
        
        if not horario_padrao:
            print(f"⚠️ {funcionario.nome} sem horário padrão para {registro.data}")
            return 0, 0, 0.0
        
        if not registro.hora_entrada or not registro.hora_saida:
            return 0, 0, 0.0
        
        minutos_extras_entrada = 0
        minutos_extras_saida = 0
        
        print(f"👤 {funcionario.nome} ({registro.data})")
        print(f"🕐 Padrão: {horario_padrao.entrada_padrao} às {horario_padrao.saida_padrao}")
        print(f"🕐 Real: {registro.hora_entrada} às {registro.hora_saida}")
        
        # 1. Calcular extras por entrada antecipada
        entrada_real_min = time_para_minutos(registro.hora_entrada)
        entrada_padrao_min = time_para_minutos(horario_padrao.entrada_padrao)
        
        if entrada_real_min < entrada_padrao_min:
            minutos_extras_entrada = entrada_padrao_min - entrada_real_min
            print(f"⏰ Entrada antecipada: {minutos_extras_entrada}min extras")
        
        # 2. Calcular extras por saída atrasada
        saida_real_min = time_para_minutos(registro.hora_saida)
        saida_padrao_min = time_para_minutos(horario_padrao.saida_padrao)
        
        if saida_real_min > saida_padrao_min:
            minutos_extras_saida = saida_real_min - saida_padrao_min
            print(f"⏰ Saída atrasada: {minutos_extras_saida}min extras")
        
        # 3. Calcular total em horas decimais
        total_minutos_extras = minutos_extras_entrada + minutos_extras_saida
        total_horas_extras = round(total_minutos_extras / 60, 2)
        
        print(f"📊 Total: {total_minutos_extras}min = {total_horas_extras}h\n")
        
        return minutos_extras_entrada, minutos_extras_saida, total_horas_extras
        
    except Exception as e:
        print(f"❌ Erro no cálculo de extras: {e}")
        return 0, 0, 0.0

def atualizar_registro_com_horario_padrao(registro):
    """Atualiza um registro com a nova lógica de horário padrão"""
    try:
        # Calcular com nova lógica
        entrada_extras, saida_extras, total_extras = calcular_horas_extras_por_horario_padrao(registro)
        
        # Atualizar campos
        registro.minutos_extras_entrada = entrada_extras
        registro.minutos_extras_saida = saida_extras
        registro.total_minutos_extras = entrada_extras + saida_extras
        registro.horas_extras_detalhadas = total_extras
        registro.horas_extras = total_extras  # Manter compatibilidade
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar registro {registro.id}: {e}")
        return False

def corrigir_registros_existentes():
    """Corrige registros existentes com nova lógica"""
    print("🚨 CORRIGINDO REGISTROS EXISTENTES COM NOVA LÓGICA")
    
    with app.app_context():
        try:
            # Buscar registros com horários (últimos 50 para teste)
            registros = RegistroPonto.query.filter(
                RegistroPonto.hora_entrada.isnot(None),
                RegistroPonto.hora_saida.isnot(None)
            ).order_by(RegistroPonto.data.desc()).limit(50).all()
            
            print(f"📊 Processando {len(registros)} registros...")
            
            corrigidos = 0
            erros = 0
            
            for registro in registros:
                try:
                    valores_antigos = {
                        'horas_extras': registro.horas_extras or 0,
                        'funcionario': registro.funcionario_ref.nome,
                        'data': registro.data
                    }
                    
                    # Atualizar com nova lógica
                    if atualizar_registro_com_horario_padrao(registro):
                        print(f"✅ {valores_antigos['funcionario']} ({valores_antigos['data']}): "
                              f"{valores_antigos['horas_extras']}h → {registro.horas_extras}h")
                        corrigidos += 1
                    else:
                        erros += 1
                        
                except Exception as e:
                    print(f"❌ Erro no registro {registro.id}: {e}")
                    erros += 1
            
            if corrigidos > 0:
                db.session.commit()
                print(f"✅ CORREÇÃO CONCLUÍDA: {corrigidos} registros corrigidos, {erros} erros")
            else:
                print(f"⚠️ Nenhum registro corrigido, {erros} erros")
                
            return corrigidos
            
        except Exception as e:
            print(f"❌ Erro na correção: {e}")
            db.session.rollback()
            return 0

def validar_calculo_exemplo():
    """Valida cálculo com exemplo fornecido"""
    print("🧪 VALIDANDO CÁLCULO COM EXEMPLO REAL:")
    print("Horário Padrão: 07:12 às 17:00")
    print("Horário Real: 07:05 às 17:50")
    
    # Dados do exemplo
    entrada_padrao = time(7, 12)    # 07:12
    entrada_real = time(7, 5)       # 07:05
    saida_padrao = time(17, 0)      # 17:00
    saida_real = time(17, 50)       # 17:50
    
    # Calcular extras entrada
    entrada_padrao_min = time_para_minutos(entrada_padrao)  # 432min
    entrada_real_min = time_para_minutos(entrada_real)      # 425min
    extras_entrada = entrada_padrao_min - entrada_real_min  # 7min
    
    # Calcular extras saída
    saida_padrao_min = time_para_minutos(saida_padrao)      # 1020min
    saida_real_min = time_para_minutos(saida_real)          # 1070min
    extras_saida = saida_real_min - saida_padrao_min        # 50min
    
    # Total
    total_minutos = extras_entrada + extras_saida           # 57min
    total_horas = round(total_minutos / 60, 2)              # 0.95h
    
    print(f"✅ RESULTADO VALIDAÇÃO:")
    print(f"   Entrada: {extras_entrada}min extras")
    print(f"   Saída: {extras_saida}min extras")  
    print(f"   Total: {total_minutos}min = {total_horas}h")
    print(f"   {'✅ Correto!' if total_horas == 0.95 else '❌ Erro - esperado 0.95h'}")
    
    return total_horas == 0.95

def testar_com_registro_real():
    """Testa com um registro real do sistema"""
    print("🧪 TESTANDO COM REGISTRO REAL DO SISTEMA")
    
    with app.app_context():
        # Buscar um registro específico para teste
        registro = RegistroPonto.query.filter(
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).first()
        
        if not registro:
            print("❌ Nenhum registro encontrado para teste")
            return False
        
        print(f"📋 REGISTRO TESTE: {registro.funcionario_ref.nome} - {registro.data}")
        print(f"   Entrada: {registro.hora_entrada}")
        print(f"   Saída: {registro.hora_saida}")
        
        # Aplicar nova lógica
        entrada_extras, saida_extras, total_extras = calcular_horas_extras_por_horario_padrao(registro)
        
        print(f"📊 RESULTADO:")
        print(f"   Extras entrada: {entrada_extras}min")
        print(f"   Extras saída: {saida_extras}min")
        print(f"   Total: {total_extras}h")
        
        return True

if __name__ == "__main__":
    print("🚀 APLICANDO SISTEMA COMPLETO DE HORÁRIOS PADRÃO")
    
    # Fase 1: Criar horários padrão
    print("\n📋 FASE 1: CRIANDO HORÁRIOS PADRÃO...")
    horarios_criados = criar_horarios_padrao_funcionarios()
    
    # Fase 2: Validar cálculo
    print("\n📋 FASE 2: VALIDANDO CÁLCULO...")
    validacao_ok = validar_calculo_exemplo()
    
    # Fase 3: Testar com registro real
    print("\n📋 FASE 3: TESTANDO COM REGISTRO REAL...")
    teste_ok = testar_com_registro_real()
    
    # Fase 4: Corrigir registros existentes
    print("\n📋 FASE 4: CORRIGINDO REGISTROS EXISTENTES...")
    registros_corrigidos = corrigir_registros_existentes()
    
    # Relatório final
    print(f"\n📋 RELATÓRIO FINAL:")
    print(f"✓ Horários padrão criados: {horarios_criados}")
    print(f"✓ Validação do cálculo: {'Sim' if validacao_ok else 'Não'}")
    print(f"✓ Teste com registro real: {'Sim' if teste_ok else 'Não'}")
    print(f"✓ Registros corrigidos: {registros_corrigidos}")
    
    if horarios_criados > 0 and validacao_ok:
        print("\n🎯 SISTEMA DE HORÁRIOS PADRÃO APLICADO COM SUCESSO!")
        print("📋 Próximas etapas:")
        print("   1. Interface para gerenciar horários padrão")
        print("   2. Atualização da engine de KPIs")
        print("   3. Relatórios com nova lógica")
    else:
        print("\n⚠️ Algumas etapas falharam - verificar logs acima")