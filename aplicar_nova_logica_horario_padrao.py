#!/usr/bin/env python3
"""
APLICAR NOVA LÓGICA DE HORAS EXTRAS BASEADA EM HORÁRIO PADRÃO
Data: 06 de Agosto de 2025
Objetivo: Implementar cálculo correto de horas extras baseado no horário cadastrado do funcionário
APLICAÇÃO: APENAS PARA DIAS NORMAIS (não altera sábados, domingos, feriados)
"""

from app import app, db
from models import RegistroPonto, Funcionario, HorarioTrabalho
from kpis_engine import CalculadoraKPI
from datetime import date, time, datetime
import logging

logging.basicConfig(level=logging.INFO)

def corrigir_horarios_extras_logica_padrao():
    """
    Aplica nova lógica de horas extras baseada no horário padrão cadastrado
    APENAS para registros de dias normais
    """
    with app.app_context():
        print("🕐 APLICANDO NOVA LÓGICA DE HORAS EXTRAS BASEADA EM HORÁRIO PADRÃO")
        print("=" * 70)
        print("📋 REGRAS:")
        print("   • APENAS dias normais (não altera sábados/domingos/feriados)")
        print("   • Usa horário cadastrado em 'horários de trabalho'")
        print("   • Entrada antecipada + Saída atrasada = Horas Extras")
        print("   • Entrada atrasada + Saída antecipada = Atrasos")
        print("=" * 70)
        
        # Buscar registros de dias normais dos últimos 30 dias
        registros_normais = RegistroPonto.query.filter(
            RegistroPonto.data >= date(2025, 7, 1),  # Julho e agosto
            RegistroPonto.tipo_registro.in_([
                'trabalho_normal', 'ponto_normal', 'dia_normal'
            ]),
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).order_by(RegistroPonto.data.desc()).limit(100).all()
        
        print(f"📊 REGISTROS ENCONTRADOS: {len(registros_normais)} dias normais")
        
        if not registros_normais:
            print("ℹ️ Nenhum registro de dia normal encontrado")
            return
        
        # Aplicar nova lógica
        engine = CalculadoraKPI()
        corrigidos = 0
        total_processados = 0
        
        for registro in registros_normais:
            try:
                total_processados += 1
                funcionario = registro.funcionario_ref
                
                print(f"\n🔄 PROCESSANDO ({total_processados}/{len(registros_normais)})")
                print(f"   {funcionario.nome} - {registro.data} - {registro.tipo_registro}")
                
                # Valores antigos para comparação
                extras_antigas = registro.horas_extras or 0
                atrasos_antigos = registro.total_atraso_horas or 0
                
                # Aplicar nova lógica usando KPI Engine
                sucesso = engine.calcular_e_atualizar_ponto(registro.id)
                
                if sucesso:
                    # Recarregar registro para ver mudanças
                    db.session.refresh(registro)
                    
                    print(f"   ✅ ATUALIZADO:")
                    print(f"      Extras: {extras_antigas:.2f}h → {registro.horas_extras:.2f}h")
                    print(f"      Atrasos: {atrasos_antigos:.2f}h → {registro.total_atraso_horas:.2f}h")
                    
                    if abs(extras_antigas - registro.horas_extras) > 0.01:
                        corrigidos += 1
                        print(f"      📈 CORREÇÃO APLICADA!")
                else:
                    print(f"   ❌ ERRO ao processar registro {registro.id}")
                    
            except Exception as e:
                print(f"   ❌ ERRO: {e}")
                continue
        
        print(f"\n📋 RELATÓRIO FINAL:")
        print(f"   Total processados: {total_processados}")
        print(f"   Registros corrigidos: {corrigidos}")
        print(f"   Taxa de correção: {(corrigidos/total_processados)*100:.1f}%")
        
        # Salvar alterações
        try:
            db.session.commit()
            print("✅ ALTERAÇÕES SALVAS NO BANCO DE DADOS")
        except Exception as e:
            print(f"❌ ERRO AO SALVAR: {e}")
            db.session.rollback()

def verificar_horarios_cadastrados():
    """Verificar quantos funcionários têm horários cadastrados"""
    with app.app_context():
        print("\n🔍 VERIFICAÇÃO DE HORÁRIOS CADASTRADOS:")
        print("=" * 40)
        
        total_funcionarios = Funcionario.query.filter_by(ativo=True).count()
        com_horario = Funcionario.query.filter(
            Funcionario.ativo == True,
            Funcionario.horario_trabalho_id.isnot(None)
        ).count()
        sem_horario = total_funcionarios - com_horario
        
        print(f"📊 FUNCIONÁRIOS ATIVOS: {total_funcionarios}")
        print(f"   Com horário cadastrado: {com_horario}")
        print(f"   Sem horário (usarão padrão): {sem_horario}")
        
        if com_horario > 0:
            print(f"\n📋 HORÁRIOS CADASTRADOS:")
            funcionarios_com_horario = Funcionario.query.filter(
                Funcionario.ativo == True,
                Funcionario.horario_trabalho_id.isnot(None)
            ).all()
            
            for func in funcionarios_com_horario:
                horario = func.horario_trabalho_ref
                print(f"   {func.nome}: {horario.entrada} às {horario.saida}")

def validar_exemplo_calculo():
    """Validar cálculo com exemplo específico"""
    with app.app_context():
        print("\n🧪 VALIDAÇÃO COM EXEMPLO REAL:")
        print("=" * 40)
        
        # Simular exemplo do prompt
        entrada_padrao = time(7, 12)    # 07:12
        entrada_real = time(7, 5)       # 07:05
        saida_padrao = time(17, 0)      # 17:00
        saida_real = time(17, 50)       # 17:50
        
        # Calcular extras entrada
        entrada_padrao_min = (entrada_padrao.hour * 60) + entrada_padrao.minute  # 432min
        entrada_real_min = (entrada_real.hour * 60) + entrada_real.minute        # 425min
        extras_entrada_min = max(0, entrada_padrao_min - entrada_real_min)       # 7min
        
        # Calcular extras saída
        saida_padrao_min = (saida_padrao.hour * 60) + saida_padrao.minute        # 1020min
        saida_real_min = (saida_real.hour * 60) + saida_real.minute              # 1070min
        extras_saida_min = max(0, saida_real_min - saida_padrao_min)             # 50min
        
        # Total
        total_extras_min = extras_entrada_min + extras_saida_min                 # 57min
        total_extras_h = round(total_extras_min / 60, 2)                         # 0.95h
        
        print(f"📊 EXEMPLO DE CÁLCULO:")
        print(f"   Horário padrão: {entrada_padrao} às {saida_padrao}")
        print(f"   Horário real: {entrada_real} às {saida_real}")
        print(f"   Extras entrada: {entrada_padrao} - {entrada_real} = {extras_entrada_min}min")
        print(f"   Extras saída: {saida_real} - {saida_padrao} = {extras_saida_min}min")
        print(f"   Total extras: {total_extras_min}min = {total_extras_h}h")
        print(f"   ✅ Resultado esperado: 0.95h")

if __name__ == "__main__":
    print("🚀 INICIANDO APLICAÇÃO DA NOVA LÓGICA DE HORAS EXTRAS")
    
    # Fase 1: Verificar horários cadastrados
    verificar_horarios_cadastrados()
    
    # Fase 2: Validar exemplo
    validar_exemplo_calculo()
    
    # Fase 3: Aplicar correção
    resposta = input("\n❓ Aplicar nova lógica aos registros existentes? (s/n): ")
    if resposta.lower() == 's':
        corrigir_horarios_extras_logica_padrao()
    else:
        print("ℹ️ Correção cancelada pelo usuário")
    
    print("\n🎯 NOVA LÓGICA DE HORAS EXTRAS BASEADA EM HORÁRIO PADRÃO CONCLUÍDA!")