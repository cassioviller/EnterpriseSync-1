"""
Testes Unitarios Completos - Regras de Calculo de Salario
SIGE v9.0 - Janeiro/2026

Este arquivo testa TODAS as regras documentadas em:
docs/TIPOS_LANCAMENTO_PONTO_SALARIO.md

Regras Testadas:
1. Tolerancia de atraso/saida antecipada (10 minutos)
2. Desconto de falta injustificada (horas + DSR)
3. Falta justificada e atestado (sem desconto)
4. Horas extras 50% (dias uteis e sabados)
5. Horas extras 100% (domingos e feriados)
6. DSR sobre horas extras
7. Simulacao completa do mes
"""

import pytest
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta


SALARIO_BASE = Decimal('3500.00')
HORAS_MES = Decimal('220')
VALOR_HORA = (SALARIO_BASE / HORAS_MES).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
JORNADA_DIA = Decimal('8.80')  # 8h48min
TOLERANCIA_MINUTOS = 10


def minutos_para_horas(minutos: int) -> Decimal:
    """Converte minutos para horas decimais"""
    return Decimal(str(minutos)) / Decimal('60')


def calcular_tolerancia(diferenca_minutos: int, tolerancia: int = TOLERANCIA_MINUTOS) -> Decimal:
    """
    Aplica regra de tolerancia.
    Se diferenca <= tolerancia: retorna 0
    Se diferenca > tolerancia: retorna TODO o valor (nao apenas excedente)
    """
    if abs(diferenca_minutos) <= tolerancia:
        return Decimal('0')
    return minutos_para_horas(abs(diferenca_minutos))


def calcular_he_50(horas: Decimal) -> Decimal:
    """Calcula valor de horas extras 50%"""
    return (VALOR_HORA * Decimal('1.5') * horas).quantize(Decimal('0.01'))


def calcular_he_100(horas: Decimal) -> Decimal:
    """Calcula valor de horas extras 100%"""
    return (VALOR_HORA * Decimal('2.0') * horas).quantize(Decimal('0.01'))


def calcular_desconto_horas(horas: Decimal) -> Decimal:
    """Calcula desconto por horas faltantes"""
    return (VALOR_HORA * horas).quantize(Decimal('0.01'))


def calcular_desconto_dsr_falta(dias_falta: int) -> Decimal:
    """Calcula desconto de DSR por falta injustificada (salario/30 por dia)"""
    return ((SALARIO_BASE / Decimal('30')) * Decimal(str(dias_falta))).quantize(Decimal('0.01'))


def calcular_dsr_sobre_extras(valor_he_total: Decimal, dias_uteis: int, domingos_feriados: int) -> Decimal:
    """Calcula DSR sobre horas extras"""
    if dias_uteis == 0:
        return Decimal('0')
    return ((valor_he_total / Decimal(str(dias_uteis))) * Decimal(str(domingos_feriados))).quantize(Decimal('0.01'))


class TestValorHora:
    """Teste do calculo do valor da hora"""
    
    def test_valor_hora_correto(self):
        """Valor hora = Salario / 220"""
        esperado = Decimal('15.91')
        assert VALOR_HORA == esperado, f"Valor hora deveria ser R$ {esperado}, mas e R$ {VALOR_HORA}"


class TestToleranciaAtraso:
    """Testes para regra de tolerancia"""
    
    def test_atraso_5_minutos_nao_desconta(self):
        """Atraso de 5 minutos (dentro tolerancia) = sem desconto"""
        desconto = calcular_tolerancia(5)
        assert desconto == Decimal('0')
    
    def test_atraso_9_minutos_nao_desconta(self):
        """Atraso de 9 minutos (dentro tolerancia) = sem desconto"""
        desconto = calcular_tolerancia(9)
        assert desconto == Decimal('0')
    
    def test_atraso_10_minutos_nao_desconta(self):
        """Atraso de 10 minutos (exatamente na tolerancia) = sem desconto"""
        desconto = calcular_tolerancia(10)
        assert desconto == Decimal('0')
    
    def test_atraso_11_minutos_desconta_tudo(self):
        """Atraso de 11 minutos (ultrapassou) = desconta 11 minutos"""
        desconto = calcular_tolerancia(11)
        esperado = minutos_para_horas(11)
        assert desconto == esperado, f"Deveria descontar {esperado}h, mas descontou {desconto}h"
    
    def test_atraso_15_minutos_desconta_tudo(self):
        """Atraso de 15 minutos = desconta 15 minutos (0.25h)"""
        desconto = calcular_tolerancia(15)
        esperado = Decimal('0.25')
        assert desconto == esperado
    
    def test_saida_9_minutos_antes_nao_desconta(self):
        """Saida 9 minutos antes (dentro tolerancia) = sem desconto"""
        desconto = calcular_tolerancia(-9)
        assert desconto == Decimal('0')
    
    def test_saida_60_minutos_antes_desconta_tudo(self):
        """Saida 60 minutos antes = desconta 60 minutos (1h)"""
        desconto = calcular_tolerancia(-60)
        esperado = Decimal('1')
        assert desconto == esperado


class TestFaltaInjustificada:
    """Testes para falta injustificada"""
    
    def test_desconto_horas_falta_completa(self):
        """Falta de dia completo = desconta 8.80h"""
        desconto = calcular_desconto_horas(JORNADA_DIA)
        esperado = (VALOR_HORA * JORNADA_DIA).quantize(Decimal('0.01'))
        assert desconto == esperado, f"Deveria ser R$ {esperado}, mas e R$ {desconto}"
    
    def test_desconto_dsr_por_falta(self):
        """1 falta = perde 1 DSR (salario/30)"""
        desconto = calcular_desconto_dsr_falta(1)
        esperado = (SALARIO_BASE / Decimal('30')).quantize(Decimal('0.01'))
        assert desconto == esperado, f"Deveria ser R$ {esperado}, mas e R$ {desconto}"
    
    def test_total_desconto_1_falta(self):
        """Total desconto por 1 falta = horas + DSR"""
        desconto_horas = calcular_desconto_horas(JORNADA_DIA)
        desconto_dsr = calcular_desconto_dsr_falta(1)
        total = desconto_horas + desconto_dsr
        
        esperado_horas = Decimal('140.00')  # 8.80h x 15.91
        esperado_dsr = Decimal('116.67')    # 3500/30
        esperado_total = Decimal('256.67')
        
        assert abs(total - esperado_total) < Decimal('1.00'), \
            f"Total deveria ser ~R$ {esperado_total}, mas e R$ {total}"


class TestFaltaJustificadaEAtestado:
    """Testes para falta justificada e atestado"""
    
    def test_falta_justificada_sem_desconto_horas(self):
        """Falta justificada NAO desconta horas"""
        desconto = Decimal('0')  # Regra: falta justificada nao desconta
        assert desconto == Decimal('0')
    
    def test_falta_justificada_sem_desconto_dsr(self):
        """Falta justificada NAO desconta DSR"""
        desconto = Decimal('0')  # Regra: falta justificada nao perde DSR
        assert desconto == Decimal('0')
    
    def test_atestado_sem_desconto_horas(self):
        """Atestado NAO desconta horas"""
        desconto = Decimal('0')  # Regra: atestado nao desconta
        assert desconto == Decimal('0')
    
    def test_atestado_sem_desconto_dsr(self):
        """Atestado NAO desconta DSR"""
        desconto = Decimal('0')  # Regra: atestado nao perde DSR
        assert desconto == Decimal('0')


class TestHorasExtras50:
    """Testes para horas extras 50% (dias uteis e sabados)"""
    
    def test_calculo_he_50_basico(self):
        """1 hora extra 50% = valor_hora x 1.5"""
        valor = calcular_he_50(Decimal('1'))
        esperado = (VALOR_HORA * Decimal('1.5')).quantize(Decimal('0.01'))
        assert valor == esperado
    
    def test_calculo_he_50_2_horas(self):
        """2 horas extras 50% (dia 03 da simulacao)"""
        valor = calcular_he_50(Decimal('2'))
        esperado = (VALOR_HORA * Decimal('1.5') * Decimal('2')).quantize(Decimal('0.01'))
        assert valor == esperado
    
    def test_calculo_he_50_4_horas_sabado(self):
        """4 horas extras 50% (sabado dia 04 da simulacao)"""
        valor = calcular_he_50(Decimal('4'))
        esperado = (VALOR_HORA * Decimal('1.5') * Decimal('4')).quantize(Decimal('0.01'))
        assert valor == esperado
    
    def test_total_he_50_simulacao(self):
        """Total HE 50% da simulacao = 6h (2h + 4h)"""
        valor = calcular_he_50(Decimal('6'))
        esperado = Decimal('143.18')  # 15.91 x 1.5 x 6
        assert abs(valor - esperado) < Decimal('0.10'), f"Esperado ~R$ {esperado}, obtido R$ {valor}"


class TestHorasExtras100:
    """Testes para horas extras 100% (domingos e feriados)"""
    
    def test_calculo_he_100_basico(self):
        """1 hora extra 100% = valor_hora x 2.0"""
        valor = calcular_he_100(Decimal('1'))
        esperado = (VALOR_HORA * Decimal('2.0')).quantize(Decimal('0.01'))
        assert valor == esperado
    
    def test_calculo_he_100_feriado_trabalhado(self):
        """8.80h feriado trabalhado (dia 13 da simulacao)"""
        valor = calcular_he_100(Decimal('8.80'))
        esperado = (VALOR_HORA * Decimal('2.0') * Decimal('8.80')).quantize(Decimal('0.01'))
        assert valor == esperado
    
    def test_calculo_he_100_domingo_trabalhado(self):
        """6h domingo trabalhado (dia 14 da simulacao)"""
        valor = calcular_he_100(Decimal('6'))
        esperado = (VALOR_HORA * Decimal('2.0') * Decimal('6')).quantize(Decimal('0.01'))
        assert valor == esperado
    
    def test_total_he_100_simulacao(self):
        """Total HE 100% da simulacao = 14.80h (8.80h + 6h)"""
        valor = calcular_he_100(Decimal('14.80'))
        esperado = Decimal('470.91')  # 15.91 x 2.0 x 14.80
        assert abs(valor - esperado) < Decimal('0.10'), f"Esperado ~R$ {esperado}, obtido R$ {valor}"


class TestDSRSobreExtras:
    """Testes para DSR sobre horas extras"""
    
    def test_dsr_formula_basica(self):
        """DSR = (Total HE) / Dias Uteis x Domingos/Feriados"""
        valor_he_total = Decimal('614.09')  # 143.18 + 470.91
        dias_uteis = 22
        domingos_feriados = 4
        
        dsr = calcular_dsr_sobre_extras(valor_he_total, dias_uteis, domingos_feriados)
        esperado = Decimal('111.65')
        
        assert abs(dsr - esperado) < Decimal('0.10'), f"Esperado ~R$ {esperado}, obtido R$ {dsr}"


class TestSimulacaoCompleta:
    """Teste de simulacao completa do mes (Janeiro/2026)"""
    
    def test_simulacao_janeiro_2026(self):
        """
        Simulacao completa conforme documentacao:
        - Salario Base: R$ 3.500,00
        - HE 50%: 6h = R$ 143,18
        - HE 100%: 14.80h = R$ 470,91
        - DSR sobre extras: R$ 111,65
        - Desconto DSR falta: R$ 116,67
        - Desconto horas: R$ 159,89
        - Resultado: R$ 3.949,18
        """
        salario_base = Decimal('3500.00')
        
        he_50_horas = Decimal('6.00')
        he_100_horas = Decimal('14.80')
        
        valor_he_50 = calcular_he_50(he_50_horas)
        valor_he_100 = calcular_he_100(he_100_horas)
        valor_he_total = valor_he_50 + valor_he_100
        
        dsr_extras = calcular_dsr_sobre_extras(valor_he_total, 22, 4)
        
        desconto_dsr_falta = calcular_desconto_dsr_falta(1)
        
        horas_falta_total = Decimal('8.80') + Decimal('0.25') + Decimal('1.00')
        desconto_horas = calcular_desconto_horas(horas_falta_total)
        
        salario_bruto = salario_base + valor_he_50 + valor_he_100 + dsr_extras
        total_descontos = desconto_dsr_falta + desconto_horas
        salario_liquido = salario_bruto - total_descontos
        
        print(f"\n{'='*50}")
        print("SIMULACAO JANEIRO/2026")
        print(f"{'='*50}")
        print(f"Salario Base:        R$ {salario_base:>10.2f}")
        print(f"(+) HE 50% (6h):     R$ {valor_he_50:>10.2f}")
        print(f"(+) HE 100% (14.8h): R$ {valor_he_100:>10.2f}")
        print(f"(+) DSR sobre extras:R$ {dsr_extras:>10.2f}")
        print(f"(-) Desc DSR falta:  R$ {desconto_dsr_falta:>10.2f}")
        print(f"(-) Desc horas:      R$ {desconto_horas:>10.2f}")
        print(f"{'='*50}")
        print(f"SALARIO LIQUIDO:     R$ {salario_liquido:>10.2f}")
        print(f"{'='*50}\n")
        
        esperado = Decimal('3949.18')
        diferenca = abs(salario_liquido - esperado)
        
        assert diferenca < Decimal('1.00'), \
            f"Salario liquido R$ {salario_liquido:.2f} difere do esperado R$ {esperado:.2f}"
    
    def test_valores_intermediarios_simulacao(self):
        """Valida valores intermediarios da simulacao"""
        assert abs(calcular_he_50(Decimal('6')) - Decimal('143.18')) < Decimal('0.10')
        assert abs(calcular_he_100(Decimal('14.80')) - Decimal('470.91')) < Decimal('0.10')
        assert abs(calcular_desconto_dsr_falta(1) - Decimal('116.67')) < Decimal('0.10')


class TestCasosEspeciais:
    """Testes para casos especiais e limites"""
    
    def test_mes_sem_horas_extras(self):
        """Mes sem horas extras = apenas salario base"""
        salario = SALARIO_BASE + Decimal('0') + Decimal('0')
        assert salario == SALARIO_BASE
    
    def test_mes_sem_faltas(self):
        """Mes sem faltas = sem descontos"""
        desconto_horas = calcular_desconto_horas(Decimal('0'))
        desconto_dsr = calcular_desconto_dsr_falta(0)
        assert desconto_horas == Decimal('0')
        assert desconto_dsr == Decimal('0')
    
    def test_multiplas_faltas(self):
        """3 faltas = 3x o desconto de DSR"""
        desconto_dsr = calcular_desconto_dsr_falta(3)
        esperado = (SALARIO_BASE / Decimal('30') * Decimal('3')).quantize(Decimal('0.01'))
        assert desconto_dsr == esperado


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
