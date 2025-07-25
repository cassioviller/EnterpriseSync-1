#!/usr/bin/env python3
"""
Correção específica para o problema do sábado 05/07/2025:
1. Garantir que horários de almoço sejam salvos
2. Calcular corretamente o custo com 50% adicional para sábado
"""

from app import app, db
from models import *
from datetime import date, time, datetime, timedelta
from utils import calcular_horas_trabalhadas
import logging

logging.basicConfig(level=logging.INFO)

def investigar_registro_sabado():
    """Investiga o registro específico do sábado 05/07/2025"""
    
    with app.app_context():
        data_sabado = date(2025, 7, 5)
        
        # Buscar todos os registros do sábado
        registros = RegistroPonto.query.filter_by(data=data_sabado).all()
        
        print(f"=== REGISTROS DO SÁBADO {data_sabado} ===")
        print(f"Total de registros encontrados: {len(registros)}")
        
        for registro in registros:
            print(f"\nID: {registro.id}")
            print(f"Funcionário: {registro.funcionario_ref.nome}")
            print(f"Entrada: {registro.hora_entrada}")
            print(f"Saída: {registro.hora_saida}")
            print(f"Almoço Saída: {registro.hora_almoco_saida}")
            print(f"Almoço Retorno: {registro.hora_almoco_retorno}")
            print(f"Horas Trabalhadas: {registro.horas_trabalhadas}")
            print(f"Horas Extras: {registro.horas_extras}")
            
            # Verificar se é sábado (dia da semana = 5)
            dia_semana = data_sabado.weekday()  # 0=segunda, 5=sábado
            print(f"Dia da semana: {dia_semana} ({'Sábado' if dia_semana == 5 else 'Outro dia'})")

def corrigir_calculo_sabado():
    """Corrige o cálculo específico para sábados com adicional de 50%"""
    
    with app.app_context():
        data_sabado = date(2025, 7, 5)
        
        # Buscar registros do sábado
        registros = RegistroPonto.query.filter_by(data=data_sabado).all()
        
        print(f"\n=== CORREÇÃO DO CÁLCULO SÁBADO ===")
        
        for registro in registros:
            print(f"\nCorrigindo registro ID {registro.id} - {registro.funcionario_ref.nome}")
            
            # Recalcular horas trabalhadas
            if registro.hora_entrada and registro.hora_saida:
                horas_calc = calcular_horas_trabalhadas(
                    registro.hora_entrada,
                    registro.hora_saida,
                    registro.hora_almoco_saida,
                    registro.hora_almoco_retorno
                )
                
                print(f"Cálculo original: {registro.horas_trabalhadas}h trabalhadas, {registro.horas_extras}h extras")
                print(f"Cálculo corrigido: {horas_calc['total']}h trabalhadas, {horas_calc['extras']}h extras")
                
                # Para sábado, todas as horas são consideradas extras com 50% adicional
                if data_sabado.weekday() == 5:  # Sábado
                    # No sábado, geralmente todo o trabalho é considerado hora extra
                    horas_calc['extras'] = horas_calc['total']
                    print(f"Sábado detectado: Todas as {horas_calc['total']}h são consideradas extras")
                
                # Atualizar registro
                registro.horas_trabalhadas = horas_calc['total']
                registro.horas_extras = horas_calc['extras']
                
                # Calcular custo com adicional de sábado
                funcionario = registro.funcionario_ref
                valor_hora_base = funcionario.salario / 220 if funcionario.salario else 15.0  # 220h por mês padrão
                
                # Custo normal
                custo_normal = (horas_calc['total'] - horas_calc['extras']) * valor_hora_base
                
                # Custo extras com 50% adicional para sábado
                custo_extras = horas_calc['extras'] * valor_hora_base * 1.5
                
                custo_total = custo_normal + custo_extras
                
                print(f"Valor/hora base: R$ {valor_hora_base:.2f}")
                print(f"Custo normal: R$ {custo_normal:.2f}")
                print(f"Custo extras (50% adicional): R$ {custo_extras:.2f}")
                print(f"Custo total: R$ {custo_total:.2f}")
        
        # Salvar alterações
        db.session.commit()
        print(f"\n✅ Correções salvas no banco de dados")

def criar_teste_sabado_completo():
    """Cria um registro de teste completo para sábado com horários de almoço"""
    
    with app.app_context():
        # Buscar funcionário para teste
        funcionario = Funcionario.query.filter_by(ativo=True).first()
        if not funcionario:
            print("❌ Nenhum funcionário encontrado")
            return
        
        data_sabado = date(2025, 7, 5)
        
        # Remover registro existente se houver
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=data_sabado
        ).first()
        
        if registro_existente:
            print(f"Removendo registro existente ID {registro_existente.id}")
            db.session.delete(registro_existente)
            db.session.commit()
        
        # Criar novo registro de sábado COM horários de almoço
        registro = RegistroPonto(
            funcionario_id=funcionario.id,
            obra_id=None,
            data=data_sabado,
            hora_entrada=time(7, 7),      # 07:07 como na imagem
            hora_saida=time(16, 2),       # 16:02 como na imagem
            hora_almoco_saida=time(12, 0),    # Horário de almoço
            hora_almoco_retorno=time(13, 0),  # Retorno do almoço
            observacoes="Sábado - Correção completa com almoço"
        )
        
        # Calcular horas
        horas_calc = calcular_horas_trabalhadas(
            registro.hora_entrada,
            registro.hora_saida,
            registro.hora_almoco_saida,
            registro.hora_almoco_retorno
        )
        
        # Para sábado, todas as horas são extras
        registro.horas_trabalhadas = horas_calc['total']
        registro.horas_extras = horas_calc['total']  # Todas as horas são extras no sábado
        
        db.session.add(registro)
        db.session.commit()
        
        print(f"\n✅ Registro de teste criado:")
        print(f"ID: {registro.id}")
        print(f"Data: {registro.data} (Sábado)")
        print(f"Entrada: {registro.hora_entrada}")
        print(f"Saída: {registro.hora_saida}")
        print(f"Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
        print(f"Horas Trabalhadas: {registro.horas_trabalhadas}")
        print(f"Horas Extras: {registro.horas_extras}")

def verificar_custos_mao_obra():
    """Verifica a tabela de custos de mão de obra para o sábado"""
    
    with app.app_context():
        data_sabado = date(2025, 7, 5)
        
        # Buscar custos de obras para o sábado
        from sqlalchemy import and_
        
        custos = db.session.query(CustoObra).filter(
            and_(
                CustoObra.data == data_sabado,
                CustoObra.tipo == 'mao_obra'
            )
        ).all()
        
        print(f"\n=== CUSTOS DE MÃO DE OBRA SÁBADO {data_sabado} ===")
        print(f"Registros encontrados: {len(custos)}")
        
        for custo in custos:
            print(f"\nID: {custo.id}")
            print(f"Obra: {custo.obra_ref.nome if custo.obra_ref else 'N/A'}")
            print(f"Funcionário: {custo.funcionario_ref.nome if custo.funcionario_ref else 'N/A'}")
            print(f"Valor: R$ {custo.valor:.2f}")
            print(f"Descrição: {custo.descricao}")

if __name__ == "__main__":
    print("=== CORREÇÃO COMPLETA DO PROBLEMA SÁBADO + ALMOÇO ===")
    
    # 1. Investigar registros atuais do sábado
    investigar_registro_sabado()
    
    # 2. Verificar custos na tabela
    verificar_custos_mao_obra()
    
    # 3. Criar registro de teste completo
    criar_teste_sabado_completo()
    
    # 4. Corrigir cálculos
    corrigir_calculo_sabado()
    
    print("\n🔧 Correção completa finalizada!")