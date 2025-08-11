#!/usr/bin/env python3
"""
Teste completo do sistema DSR (Descanso Semanal Remunerado) em modo estrito
Lei 605/49 - Cálculo semana a semana

Teste baseado no exemplo do Carlos Alberto com múltiplos cenários
"""

from datetime import date, datetime, timedelta
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

def _round2(x: float) -> float:
    """Arredondar para 2 casas decimais (meio para cima)"""
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _particionar_semanas(inicio: date, fim: date, semana_comeca_em: str = "domingo"):
    """Particiona período em semanas (domingo-sábado por padrão)"""
    semanas = []
    cur = inicio
    
    # Alinhar início conforme configuração
    if semana_comeca_em == "domingo":
        # Ir para o domingo anterior/igual
        cur -= timedelta(days=(cur.weekday() + 1) % 7)
    else:  # segunda-feira
        cur -= timedelta(days=cur.weekday())
    
    while cur <= fim:
        ini_sem = cur
        fim_sem = cur + timedelta(days=6)
        
        semanas.append((max(ini_sem, inicio), min(fim_sem, fim)))
        cur = fim_sem + timedelta(days=1)
    
    return semanas

def calcular_dsr_modo_estrito_completo(salario_mensal: float, faltas_datas: list, data_inicio: date, data_fim: date, horas_dia_padrao: float = 8.8):
    """
    Calcula DSR em modo estrito (Lei 605/49) - semana a semana
    Versão completa com detalhamento por semana
    
    Args:
        salario_mensal: Salário mensal do funcionário
        faltas_datas: Lista de datas com faltas injustificadas
        data_inicio: Data início do período
        data_fim: Data fim do período
        horas_dia_padrao: Horas padrão por dia
    
    Returns:
        Dict com cálculo detalhado
    """
    if salario_mensal <= 0 or horas_dia_padrao <= 0:
        return {"desconto_total": 0, "faltas_total": 0, "semanas_com_perda": 0}
    
    valor_dia = salario_mensal / 30.0
    
    # Indexar faltas injustificadas por data
    injust_por_dia = defaultdict(float)
    for data_falta in faltas_datas:
        if data_falta < data_inicio or data_falta > data_fim:
            continue
        # Assumir falta de dia inteiro (pode ser expandido para frações)
        injust_por_dia[data_falta] = 1.0
    
    # Particionar em semanas (domingo-sábado)
    semanas = _particionar_semanas(data_inicio, data_fim, "domingo")
    
    faltas_injustificadas_total = 0.0
    semanas_com_perda_dsr = 0
    detalhes_semanas = []
    
    for (ini_sem, fim_sem) in semanas:
        soma_semana = 0.0
        faltas_na_semana = []
        data_atual = ini_sem
        
        while data_atual <= fim_sem:
            falta_dia = injust_por_dia.get(data_atual, 0.0)
            if falta_dia > 0:
                faltas_na_semana.append(data_atual)
                soma_semana += falta_dia
            data_atual += timedelta(days=1)
        
        # Se houve falta na semana, perde DSR
        perdeu_dsr = soma_semana > 0
        if perdeu_dsr:
            semanas_com_perda_dsr += 1
        
        faltas_injustificadas_total += soma_semana
        
        detalhes_semanas.append({
            "semana_inicio": ini_sem.strftime("%Y-%m-%d"),
            "semana_fim": fim_sem.strftime("%Y-%m-%d"),
            "faltas_injustificadas": _round2(soma_semana),
            "perdeu_dsr": perdeu_dsr,
            "datas_faltas": [d.strftime("%Y-%m-%d") for d in faltas_na_semana]
        })
    
    desconto_por_faltas = _round2(valor_dia * faltas_injustificadas_total)
    desconto_por_dsr = _round2(valor_dia * semanas_com_perda_dsr)
    desconto_total = _round2(desconto_por_faltas + desconto_por_dsr)
    
    return {
        "valor_dia": _round2(valor_dia),
        "faltas_injustificadas_total": _round2(faltas_injustificadas_total),
        "semanas_com_perda_dsr": semanas_com_perda_dsr,
        "desconto_por_faltas": desconto_por_faltas,
        "desconto_por_dsr": desconto_por_dsr,
        "desconto_total_mes": desconto_total,
        "por_semana": detalhes_semanas,
        "ui": {
            "kpi_faltas_numero": _round2(faltas_injustificadas_total),
            "kpi_valor_abaixo": f"-R$ {desconto_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "observacoes": "Base legal: Lei 605/49 art.6º; CLT art.64; Súmula 13/TST. Modo: estrito semanal."
        }
    }

def teste_completo():
    """Executa bateria de testes do sistema DSR"""
    print("🧪 TESTE COMPLETO - SISTEMA DSR ESTRITO (Lei 605/49)")
    print("=" * 60)
    
    # Dados do Carlos Alberto
    salario_carlos = 2106.0
    
    print(f"👤 Funcionário: Carlos Alberto")
    print(f"💰 Salário mensal: R$ {salario_carlos:,.2f}")
    print(f"📅 Período: Julho 2025")
    print()
    
    # Período de teste - Julho 2025
    inicio = date(2025, 7, 1)
    fim = date(2025, 7, 31)
    
    # CENÁRIO 1: Uma falta (Carlos real)
    print("📋 CENÁRIO 1: 1 falta injustificada (caso real Carlos)")
    faltas_1 = [date(2025, 7, 15)]  # Uma falta
    
    resultado_1 = calcular_dsr_modo_estrito_completo(salario_carlos, faltas_1, inicio, fim)
    
    print(f"   Faltas total: {resultado_1['faltas_injustificadas_total']}")
    print(f"   Semanas com perda DSR: {resultado_1['semanas_com_perda_dsr']}")
    print(f"   Desconto faltas: R$ {resultado_1['desconto_por_faltas']:.2f}")
    print(f"   Desconto DSR: R$ {resultado_1['desconto_por_dsr']:.2f}")
    print(f"   🎯 TOTAL: {resultado_1['ui']['kpi_valor_abaixo']}")
    print()
    
    # CENÁRIO 2: Múltiplas faltas, mesma semana
    print("📋 CENÁRIO 2: 3 faltas na mesma semana")
    faltas_2 = [
        date(2025, 7, 14),  # Segunda-feira
        date(2025, 7, 15),  # Terça-feira
        date(2025, 7, 16),  # Quarta-feira
    ]
    
    resultado_2 = calcular_dsr_modo_estrito_completo(salario_carlos, faltas_2, inicio, fim)
    
    print(f"   Faltas total: {resultado_2['faltas_injustificadas_total']}")
    print(f"   Semanas com perda DSR: {resultado_2['semanas_com_perda_dsr']}")
    print(f"   Desconto faltas: R$ {resultado_2['desconto_por_faltas']:.2f}")
    print(f"   Desconto DSR: R$ {resultado_2['desconto_por_dsr']:.2f}")
    print(f"   🎯 TOTAL: {resultado_2['ui']['kpi_valor_abaixo']}")
    print()
    
    # CENÁRIO 3: Múltiplas faltas, semanas diferentes
    print("📋 CENÁRIO 3: 4 faltas em 3 semanas diferentes")
    faltas_3 = [
        date(2025, 7, 8),   # Semana 2
        date(2025, 7, 15),  # Semana 3
        date(2025, 7, 16),  # Semana 3
        date(2025, 7, 29),  # Semana 5
    ]
    
    resultado_3 = calcular_dsr_modo_estrito_completo(salario_carlos, faltas_3, inicio, fim)
    
    print(f"   Faltas total: {resultado_3['faltas_injustificadas_total']}")
    print(f"   Semanas com perda DSR: {resultado_3['semanas_com_perda_dsr']}")
    print(f"   Desconto faltas: R$ {resultado_3['desconto_por_faltas']:.2f}")
    print(f"   Desconto DSR: R$ {resultado_3['desconto_por_dsr']:.2f}")
    print(f"   🎯 TOTAL: {resultado_3['ui']['kpi_valor_abaixo']}")
    print()
    
    # Comparação com método simplificado
    print("📊 COMPARAÇÃO DOS MÉTODOS:")
    print("-" * 40)
    
    valor_dia = salario_carlos / 30
    
    for i, (cenario, faltas, resultado) in enumerate([
        ("1 falta", faltas_1, resultado_1),
        ("3 faltas mesma semana", faltas_2, resultado_2),
        ("4 faltas 3 semanas", faltas_3, resultado_3)
    ], 1):
        simplificado = len(faltas) * (2 * valor_dia)  # Método atual
        estrito = resultado['desconto_total_mes']
        diferenca = simplificado - estrito
        
        print(f"Cenário {i} ({cenario}):")
        print(f"   Simplificado: -R$ {simplificado:.2f}")
        print(f"   Estrito:      -R$ {estrito:.2f}")
        print(f"   Diferença:     R$ {diferenca:.2f}")
        print()
    
    # Detalhamento semanal do cenário 3
    print("📅 DETALHAMENTO SEMANAL (Cenário 3):")
    print("-" * 40)
    for semana in resultado_3['por_semana']:
        status_dsr = "❌ Perdeu DSR" if semana['perdeu_dsr'] else "✅ Mantém DSR"
        print(f"   {semana['semana_inicio']} a {semana['semana_fim']}")
        print(f"   Faltas: {semana['faltas_injustificadas']:.1f} | {status_dsr}")
        if semana['datas_faltas']:
            print(f"   Datas: {', '.join(semana['datas_faltas'])}")
        print()

if __name__ == "__main__":
    teste_completo()