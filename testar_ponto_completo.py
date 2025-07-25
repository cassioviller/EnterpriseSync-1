#!/usr/bin/env python3
"""
Script para testar completamente o sistema de controle de ponto
Testa todos os tipos de lançamentos e valida cálculos
"""

from app import app, db
from models import *
from utils import calcular_horas_trabalhadas
from datetime import date, time, datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def testar_calculos_horas():
    """Testa os cálculos de horas trabalhadas com diferentes cenários"""
    
    print("=== TESTE DE CÁLCULOS DE HORAS ===")
    
    # Cenário 1: Dia normal com almoço
    entrada = time(8, 0)
    saida = time(17, 0)
    almoco_saida = time(12, 0)
    almoco_retorno = time(13, 0)
    
    resultado = calcular_horas_trabalhadas(entrada, saida, almoco_saida, almoco_retorno)
    print(f"Cenário 1 - Dia normal (8h-17h, almoço 12h-13h): {resultado}")
    
    # Cenário 2: Sábado com horas extras (sem almoço)
    entrada2 = time(8, 0)
    saida2 = time(14, 0)
    
    resultado2 = calcular_horas_trabalhadas(entrada2, saida2, None, None)
    print(f"Cenário 2 - Sábado sem almoço (8h-14h): {resultado2}")
    
    # Cenário 3: Dia com almoço mais longo
    entrada3 = time(7, 0)
    saida3 = time(18, 0)
    almoco_saida3 = time(12, 0)
    almoco_retorno3 = time(14, 0)
    
    resultado3 = calcular_horas_trabalhadas(entrada3, saida3, almoco_saida3, almoco_retorno3)
    print(f"Cenário 3 - Dia longo com almoço de 2h (7h-18h, almoço 12h-14h): {resultado3}")

def testar_criacao_registros():
    """Testa a criação de registros de ponto com diferentes tipos"""
    
    print("\n=== TESTE DE CRIAÇÃO DE REGISTROS ===")
    
    with app.app_context():
        try:
            # Buscar primeiro funcionário ativo
            funcionario = Funcionario.query.filter_by(ativo=True).first()
            if not funcionario:
                print("❌ Nenhum funcionário ativo encontrado")
                return
            
            print(f"✓ Testando com funcionário: {funcionario.nome}")
            
            # Buscar primeira obra
            obra = Obra.query.first()
            obra_id = obra.id if obra else None
            
            # Data de teste
            data_teste = date.today() - timedelta(days=1)
            
            # 1. Teste: Dia normal com almoço
            registro1 = RegistroPonto(
                funcionario_id=funcionario.id,
                obra_id=obra_id,
                data=data_teste,
                hora_entrada=time(8, 0),
                hora_saida=time(17, 0),
                hora_almoco_saida=time(12, 0),
                hora_almoco_retorno=time(13, 0),
                observacoes="Teste: Dia normal com almoço"
            )
            
            # Calcular horas
            if registro1.hora_entrada and registro1.hora_saida:
                horas_trabalhadas = calcular_horas_trabalhadas(
                    registro1.hora_entrada, registro1.hora_saida,
                    registro1.hora_almoco_saida, registro1.hora_almoco_retorno
                )
                registro1.horas_trabalhadas = horas_trabalhadas['total']
                registro1.horas_extras = horas_trabalhadas['extras']
            
            db.session.add(registro1)
            db.session.commit()
            
            print(f"✓ Registro 1 criado: {registro1.horas_trabalhadas}h trabalhadas, {registro1.horas_extras}h extras")
            print(f"  Almoço: {registro1.hora_almoco_saida} - {registro1.hora_almoco_retorno}")
            
            # 2. Teste: Sábado sem almoço
            data_sabado = data_teste + timedelta(days=1)
            registro2 = RegistroPonto(
                funcionario_id=funcionario.id,
                obra_id=obra_id,
                data=data_sabado,
                hora_entrada=time(8, 0),
                hora_saida=time(14, 0),
                hora_almoco_saida=None,
                hora_almoco_retorno=None,
                observacoes="Teste: Sábado sem almoço"
            )
            
            # Calcular horas
            if registro2.hora_entrada and registro2.hora_saida:
                horas_trabalhadas = calcular_horas_trabalhadas(
                    registro2.hora_entrada, registro2.hora_saida,
                    registro2.hora_almoco_saida, registro2.hora_almoco_retorno
                )
                registro2.horas_trabalhadas = horas_trabalhadas['total']
                registro2.horas_extras = horas_trabalhadas['extras']
            
            db.session.add(registro2)
            db.session.commit()
            
            print(f"✓ Registro 2 criado: {registro2.horas_trabalhadas}h trabalhadas, {registro2.horas_extras}h extras") 
            print(f"  Almoço: {registro2.hora_almoco_saida} - {registro2.hora_almoco_retorno}")
            
            return [registro1.id, registro2.id]
            
        except Exception as e:
            print(f"❌ Erro ao criar registros: {e}")
            db.session.rollback()
            return None

def verificar_registros_salvos(ids_registros):
    """Verifica se os registros foram salvos corretamente"""
    
    print("\n=== VERIFICAÇÃO DE REGISTROS SALVOS ===")
    
    with app.app_context():
        for id_registro in ids_registros:
            registro = RegistroPonto.query.get(id_registro)
            if registro:
                print(f"✓ Registro ID {id_registro}:")
                print(f"  - Data: {registro.data}")
                print(f"  - Entrada: {registro.hora_entrada}")
                print(f"  - Saída: {registro.hora_saida}")
                print(f"  - Almoço Saída: {registro.hora_almoco_saida}")
                print(f"  - Almoço Retorno: {registro.hora_almoco_retorno}")
                print(f"  - Horas Trabalhadas: {registro.horas_trabalhadas}")
                print(f"  - Horas Extras: {registro.horas_extras}")
                print(f"  - Observações: {registro.observacoes}")
                print()
            else:
                print(f"❌ Registro ID {id_registro} não encontrado")

def limpar_registros_teste():
    """Remove registros de teste criados"""
    
    print("=== LIMPEZA DE REGISTROS DE TESTE ===")
    
    with app.app_context():
        registros_teste = RegistroPonto.query.filter(
            RegistroPonto.observacoes.like('Teste:%')
        ).all()
        
        for registro in registros_teste:
            print(f"Removendo registro teste ID {registro.id}")
            db.session.delete(registro)
        
        db.session.commit()
        print(f"✓ {len(registros_teste)} registros de teste removidos")

if __name__ == "__main__":
    print("Iniciando teste completo do sistema de ponto...")
    
    # 1. Testar cálculos básicos
    testar_calculos_horas()
    
    # 2. Testar criação de registros
    ids_criados = testar_criacao_registros()
    
    if ids_criados:
        # 3. Verificar se foram salvos corretamente
        verificar_registros_salvos(ids_criados)
        
        # 4. Limpar registros de teste
        # limpar_registros_teste()
    
    print("\n✅ Teste completo finalizado!")