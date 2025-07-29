#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import *
from datetime import datetime, date
from sqlalchemy import func

def debug_custos_obra():
    with app.app_context():
        # Buscar uma obra que tenha custos
        obra_com_custos = None
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 29)
        
        print("=== BUSCANDO OBRA COM CUSTOS ===")
        obras = Obra.query.all()
        for obra in obras:
            # Verificar se tem custos
            custos_total = 0
            custos_total += db.session.query(func.sum(CustoVeiculo.valor)).filter(
                CustoVeiculo.obra_id == obra.id,
                CustoVeiculo.data_custo.between(data_inicio, data_fim)
            ).scalar() or 0.0
            custos_total += db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
                RegistroAlimentacao.obra_id == obra.id,
                RegistroAlimentacao.data.between(data_inicio, data_fim)
            ).scalar() or 0.0
            custos_total += db.session.query(func.sum(CustoObra.valor)).filter(
                CustoObra.obra_id == obra.id,
                CustoObra.data.between(data_inicio, data_fim)
            ).scalar() or 0.0
            
            if custos_total > 0:
                print(f"Obra com custos: {obra.id} - {obra.nome} - Total: R$ {custos_total:.2f}")
                obra_com_custos = obra
                break
        
        if not obra_com_custos:
            print("Nenhuma obra com custos encontrada no período!")
            return
        
        obra_id = obra_com_custos.id
        
        print(f"=== DEBUG CUSTOS OBRA {obra_id} ===")
        print(f"Período: {data_inicio} a {data_fim}")
        
        # CÁLCULO EXATO DA PÁGINA DE DETALHES (linhas 2002-2042)
        
        # 1. Custos de Transporte (Veículos) - apenas desta obra específica
        custo_transporte = db.session.query(func.sum(CustoVeiculo.valor)).filter(
            CustoVeiculo.obra_id == obra_id,
            CustoVeiculo.data_custo.between(data_inicio, data_fim)
        ).scalar() or 0.0
        print(f"1. Custo Transporte: R$ {custo_transporte:.2f}")
        
        # 2. Custos de Alimentação
        custo_alimentacao = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.obra_id == obra_id,
            RegistroAlimentacao.data.between(data_inicio, data_fim)
        ).scalar() or 0.0
        print(f"2. Custo Alimentação: R$ {custo_alimentacao:.2f}")
        
        # 3. Custos de Mão de Obra
        registros_ponto = db.session.query(RegistroPonto).join(Funcionario).filter(
            RegistroPonto.obra_id == obra_id,
            RegistroPonto.data.between(data_inicio, data_fim),
            RegistroPonto.hora_entrada.isnot(None)  # Só dias trabalhados
        ).all()
        
        custo_mao_obra = 0.0
        print(f"3. Registros de ponto encontrados: {len(registros_ponto)}")
        
        for registro in registros_ponto:
            if registro.hora_entrada and registro.hora_saida:
                # Calcular horas trabalhadas
                entrada = datetime.combine(registro.data, registro.hora_entrada)
                saida = datetime.combine(registro.data, registro.hora_saida)
                
                # Subtrair tempo de almoço (1 hora padrão)
                horas_dia = (saida - entrada).total_seconds() / 3600 - 1
                horas_dia = max(0, horas_dia)  # Não pode ser negativo
                
                # Calcular custo baseado no salário do funcionário
                if registro.funcionario_ref.salario:
                    valor_hora = registro.funcionario_ref.salario / 220  # 220 horas/mês aprox
                    custo_dia = horas_dia * valor_hora
                    custo_mao_obra += custo_dia
                    print(f"   {registro.data}: {registro.funcionario_ref.nome} - {horas_dia:.2f}h × R${valor_hora:.2f} = R${custo_dia:.2f}")
        
        print(f"3. Custo Mão de Obra TOTAL: R$ {custo_mao_obra:.2f}")
        
        # 4. Custo Total da Obra (EXATAMENTE linha 2042)
        custo_total = custo_transporte + custo_alimentacao + custo_mao_obra
        print(f"\n=== RESULTADO FINAL ===")
        print(f"Custo Total (página detalhes): R$ {custo_total:.2f}")
        print(f"Fórmula: R$ {custo_transporte:.2f} + R$ {custo_alimentacao:.2f} + R$ {custo_mao_obra:.2f}")
        
        # Verificar se há outros custos sendo incluídos
        print(f"\n=== VERIFICAÇÃO DE OUTROS CUSTOS ===")
        custos_obra = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.obra_id == obra_id,
            CustoObra.data.between(data_inicio, data_fim)
        ).scalar() or 0.0
        print(f"Custos Obra (CustoObra): R$ {custos_obra:.2f}")
        
        outros_custos = db.session.query(func.sum(OutroCusto.valor)).filter(
            OutroCusto.obra_id == obra_id,
            OutroCusto.data.between(data_inicio, data_fim)
        ).scalar() or 0.0
        print(f"Outros Custos (OutroCusto): R$ {outros_custos:.2f}")
        
        print(f"Total com outros custos: R$ {custo_total + custos_obra + outros_custos:.2f}")

if __name__ == "__main__":
    debug_custos_obra()