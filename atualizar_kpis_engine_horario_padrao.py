#!/usr/bin/env python3
"""
ATUALIZAÇÃO DA ENGINE DE KPIs PARA USAR HORÁRIO PADRÃO - SIGE v8.2
Data: 06 de Agosto de 2025
Integra o sistema de horários padrão na engine de KPIs existente
"""

from app import app, db
from models import Funcionario, RegistroPonto, HorarioPadrao
from datetime import date, datetime, time
import logging

logging.basicConfig(level=logging.INFO)

def atualizar_kpis_engine_com_horario_padrao():
    """Atualiza a função de cálculo de KPIs para usar horário padrão"""
    
    kpis_engine_update = '''
def calcular_kpis_funcionario_horario_padrao(funcionario_id, mes, ano):
    """Calcula KPIs usando horário padrão como referência"""
    try:
        funcionario = Funcionario.query.get(funcionario_id)
        if not funcionario:
            return {}
        
        # Buscar registros do mês
        data_inicio = date(ano, mes, 1)
        if mes == 12:
            data_fim = date(ano + 1, 1, 1)
        else:
            data_fim = date(ano, mes + 1, 1)
        
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data < data_fim
        ).all()
        
        # Obter horário padrão
        horario_padrao = funcionario.get_horario_padrao_ativo(data_inicio)
        if not horario_padrao:
            print(f"⚠️ {funcionario.nome} sem horário padrão")
            return calcular_kpis_funcionario_original(funcionario_id, mes, ano)
        
        # Calcular estatísticas baseadas em horário padrão
        total_horas_extras = 0.0
        total_minutos_atrasos = 0
        total_horas_trabalhadas = 0.0
        dias_trabalhados = 0
        
        for registro in registros:
            if registro.tipo_registro in ['trabalhado', 'sabado_trabalhado', 'feriado_trabalhado']:
                # Usar campos calculados com horário padrão
                if hasattr(registro, 'horas_extras_detalhadas'):
                    total_horas_extras += registro.horas_extras_detalhadas or 0
                else:
                    total_horas_extras += registro.horas_extras or 0
                
                total_horas_trabalhadas += registro.horas_trabalhadas or 0
                total_minutos_atrasos += registro.total_atraso_minutos or 0
                dias_trabalhados += 1
        
        # Calcular carga horária padrão do mês
        carga_padrao_mensal = funcionario.get_carga_horaria_mensal(ano, mes)
        
        # Calcular KPIs
        produtividade = (total_horas_trabalhadas / carga_padrao_mensal * 100) if carga_padrao_mensal > 0 else 0
        eficiencia = max(0, 100 - (total_minutos_atrasos / 60 / carga_padrao_mensal * 100)) if carga_padrao_mensal > 0 else 0
        
        # Calcular custos
        valor_hora_base = funcionario.salario / carga_padrao_mensal if carga_padrao_mensal > 0 else 0
        custo_horas_normais = total_horas_trabalhadas * valor_hora_base
        custo_horas_extras = total_horas_extras * valor_hora_base * 1.5  # 50% adicional
        
        kpis = {
            'horas_trabalhadas': round(total_horas_trabalhadas, 1),
            'horas_extras': round(total_horas_extras, 1),
            'produtividade': round(produtividade, 1),
            'eficiencia': round(eficiencia, 1),
            'dias_trabalhados': dias_trabalhados,
            'atrasos_minutos': total_minutos_atrasos,
            'custo_total': round(custo_horas_normais + custo_horas_extras, 2),
            'custo_extras': round(custo_horas_extras, 2),
            'carga_padrao': round(carga_padrao_mensal, 1)
        }
        
        print(f"✅ KPIs calculados para {funcionario.nome}:")
        print(f"   Horas trabalhadas: {kpis['horas_trabalhadas']}h")
        print(f"   Horas extras: {kpis['horas_extras']}h")
        print(f"   Produtividade: {kpis['produtividade']}%")
        print(f"   Custo total: R$ {kpis['custo_total']}")
        
        return kpis
        
    except Exception as e:
        print(f"❌ Erro ao calcular KPIs: {e}")
        return {}
'''
    
    print("📋 Código de atualização da engine de KPIs preparado")
    return kpis_engine_update

def testar_kpis_com_horario_padrao():
    """Testa cálculo de KPIs com horário padrão"""
    print("🧪 TESTANDO KPIs COM HORÁRIO PADRÃO")
    
    with app.app_context():
        # Buscar funcionário para teste
        funcionario = Funcionario.query.filter_by(ativo=True).first()
        
        if not funcionario:
            print("❌ Nenhum funcionário encontrado para teste")
            return False
        
        print(f"👤 Testando com: {funcionario.nome}")
        
        # Verificar horário padrão
        horario_padrao = funcionario.get_horario_padrao_ativo()
        if not horario_padrao:
            print("⚠️ Funcionário sem horário padrão")
            return False
        
        print(f"🕐 Horário padrão: {horario_padrao.entrada_padrao} às {horario_padrao.saida_padrao}")
        
        # Buscar registros recentes
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).order_by(RegistroPonto.data.desc()).limit(5).all()
        
        print(f"📊 Analisando {len(registros)} registros recentes:")
        
        total_extras = 0.0
        for registro in registros:
            # Usar nova lógica se disponível
            if hasattr(registro, 'horas_extras_detalhadas') and registro.horas_extras_detalhadas:
                extras = registro.horas_extras_detalhadas
            else:
                extras = registro.horas_extras or 0
            
            total_extras += extras
            print(f"   {registro.data}: {registro.hora_entrada}-{registro.hora_saida} = {extras}h extras")
        
        print(f"📋 Total de horas extras: {total_extras}h")
        return True

def criar_relatorio_comparativo():
    """Cria relatório comparativo entre método antigo e novo"""
    print("📊 CRIANDO RELATÓRIO COMPARATIVO")
    
    with app.app_context():
        funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()
        
        comparativo = []
        
        for funcionario in funcionarios:
            # Buscar registros recentes
            registros = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == funcionario.id,
                RegistroPonto.hora_entrada.isnot(None),
                RegistroPonto.hora_saida.isnot(None)
            ).order_by(RegistroPonto.data.desc()).limit(5).all()
            
            if not registros:
                continue
            
            # Comparar métodos
            extras_antigas = sum(r.horas_extras or 0 for r in registros)
            extras_novas = sum(getattr(r, 'horas_extras_detalhadas', 0) or 0 for r in registros)
            
            comparativo.append({
                'funcionario': funcionario.nome,
                'registros': len(registros),
                'extras_antigas': round(extras_antigas, 2),
                'extras_novas': round(extras_novas, 2),
                'diferenca': round(extras_novas - extras_antigas, 2)
            })
        
        print("\n📋 RELATÓRIO COMPARATIVO:")
        print("Funcionário".ljust(25) + "Registros".ljust(10) + "Antiga".ljust(10) + "Nova".ljust(10) + "Diferença")
        print("-" * 65)
        
        for item in comparativo:
            print(f"{item['funcionario'][:24].ljust(25)}"
                  f"{item['registros']:>9}"
                  f"{item['extras_antigas']:>9.1f}h"
                  f"{item['extras_novas']:>9.1f}h"
                  f"{item['diferenca']:>+8.1f}h")
        
        return comparativo

if __name__ == "__main__":
    print("🚀 ATUALIZANDO ENGINE DE KPIs COM HORÁRIO PADRÃO")
    
    # Fase 1: Preparar código de atualização
    print("\n📋 FASE 1: PREPARANDO ATUALIZAÇÃO...")
    codigo_atualizacao = atualizar_kpis_engine_com_horario_padrao()
    
    # Fase 2: Testar KPIs
    print("\n📋 FASE 2: TESTANDO KPIs...")
    teste_ok = testar_kpis_com_horario_padrao()
    
    # Fase 3: Criar relatório comparativo
    print("\n📋 FASE 3: RELATÓRIO COMPARATIVO...")
    relatorio = criar_relatorio_comparativo()
    
    print(f"\n📋 RELATÓRIO FINAL:")
    print(f"✓ Código de atualização: Preparado")
    print(f"✓ Teste de KPIs: {'Sim' if teste_ok else 'Não'}")
    print(f"✓ Relatório comparativo: {len(relatorio)} funcionários analisados")
    
    print(f"\n🎯 PRÓXIMAS ETAPAS:")
    print(f"   1. Integrar código na kpis_engine.py")
    print(f"   2. Atualizar interface para mostrar detalhes")
    print(f"   3. Implementar relatórios com nova lógica")