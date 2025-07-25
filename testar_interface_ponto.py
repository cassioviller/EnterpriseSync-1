#!/usr/bin/env python3
"""
Teste específico para verificar problema de interface do ponto
Reproduz o cenário da imagem anexada
"""

from app import app, db
from models import *
from datetime import date, time, datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)

def criar_registro_sabado_teste():
    """Cria um registro de sábado igual ao da imagem para testar"""
    
    with app.app_context():
        try:
            # Buscar funcionário
            funcionario = Funcionario.query.filter_by(ativo=True).first()
            if not funcionario:
                print("❌ Nenhum funcionário encontrado")
                return
            
            print(f"✓ Funcionário: {funcionario.nome}")
            
            # Data 05/07/2025 (sábado da imagem)
            data_sabado = date(2025, 7, 5)
            
            # Verificar se já existe registro para esta data
            registro_existente = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_sabado
            ).first()
            
            if registro_existente:
                print(f"⚠️ Registro já existe para {data_sabado}, removendo...")
                db.session.delete(registro_existente)
                db.session.commit()
            
            # Criar registro de sábado com horários de almoço
            registro = RegistroPonto(
                funcionario_id=funcionario.id,
                obra_id=None,  # Sem obra específica
                data=data_sabado,
                hora_entrada=time(7, 7),  # 07:07 como na imagem
                hora_saida=time(16, 2),   # 16:02 como na imagem
                hora_almoco_saida=time(12, 0),    # Definir horário de almoço
                hora_almoco_retorno=time(13, 0),  # Definir retorno almoço
                observacoes="Teste sábado - reproduzindo cenário da imagem"
            )
            
            # Calcular horas usando a função do sistema
            from utils import calcular_horas_trabalhadas
            
            horas_calc = calcular_horas_trabalhadas(
                registro.hora_entrada,
                registro.hora_saida,
                registro.hora_almoco_saida,
                registro.hora_almoco_retorno
            )
            
            registro.horas_trabalhadas = horas_calc['total']
            registro.horas_extras = horas_calc['extras']
            
            db.session.add(registro)
            db.session.commit()
            
            print(f"✅ Registro criado com ID: {registro.id}")
            print(f"  - Data: {registro.data}")
            print(f"  - Entrada: {registro.hora_entrada}")
            print(f"  - Saída: {registro.hora_saida}")
            print(f"  - Almoço Saída: {registro.hora_almoco_saida}")
            print(f"  - Almoço Retorno: {registro.hora_almoco_retorno}")
            print(f"  - Horas Trabalhadas: {registro.horas_trabalhadas}")
            print(f"  - Horas Extras: {registro.horas_extras}")
            
            return registro.id
            
        except Exception as e:
            print(f"❌ Erro ao criar registro: {e}")
            db.session.rollback()
            return None

def verificar_exibicao_registro(registro_id):
    """Verifica como o registro está sendo exibido"""
    
    with app.app_context():
        registro = db.session.get(RegistroPonto, registro_id)
        
        if not registro:
            print("❌ Registro não encontrado")
            return
        
        print("\n=== DADOS DO REGISTRO NO BANCO ===")
        print(f"ID: {registro.id}")
        print(f"Funcionário: {registro.funcionario_ref.nome}")
        print(f"Data: {registro.data.strftime('%d/%m/%Y')}")
        print(f"Entrada: {registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else 'None'}")
        print(f"Saída: {registro.hora_saida.strftime('%H:%M') if registro.hora_saida else 'None'}")
        print(f"Almoço Saída: {registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else 'None'}")
        print(f"Almoço Retorno: {registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else 'None'}")
        print(f"Horas Trabalhadas: {registro.horas_trabalhadas}")
        print(f"Horas Extras: {registro.horas_extras}")
        
        # Simular a lógica do template para ver se o problema está na exibição
        print("\n=== SIMULAÇÃO DO TEMPLATE ===")
        
        # Lógica igual ao template ponto.html
        almoco_saida_display = registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else '-'
        almoco_retorno_display = registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else '-'
        
        print(f"Saída Almoço (template): {almoco_saida_display}")
        print(f"Retorno Almoço (template): {almoco_retorno_display}")
        
        # Verificar se o badge seria exibido
        if registro.hora_almoco_saida:
            print(f"Badge Saída Almoço: <span class='badge bg-warning'>{registro.hora_almoco_saida.strftime('%H:%M')}</span>")
        else:
            print("Badge Saída Almoço: <span class='text-muted'>-</span>")
            
        if registro.hora_almoco_retorno:
            print(f"Badge Retorno Almoço: <span class='badge bg-info'>{registro.hora_almoco_retorno.strftime('%H:%M')}</span>")
        else:
            print("Badge Retorno Almoço: <span class='text-muted'>-</span>")

def testar_formulario():
    """Testa se o formulário está processando os campos corretamente"""
    
    print("\n=== TESTE DO FORMULÁRIO ===")
    
    from forms import RegistroPontoForm
    from flask import Flask
    from werkzeug.datastructures import MultiDict
    
    # Simular dados do formulário
    form_data = MultiDict([
        ('funcionario_id', '1'),
        ('obra_id', ''),
        ('data', '2025-07-05'),
        ('hora_entrada', '07:07'),
        ('hora_saida', '16:02'),
        ('hora_almoco_saida', '12:00'),
        ('hora_almoco_retorno', '13:00'),
        ('observacoes', 'Teste formulário')
    ])
    
    with app.app_context():
        form = RegistroPontoForm(form_data)
        
        print(f"Form válido: {form.validate()}")
        print(f"Erros: {form.errors}")
        
        if form.validate():
            print("✅ Dados do formulário:")
            print(f"  - hora_entrada: {form.hora_entrada.data}")
            print(f"  - hora_saida: {form.hora_saida.data}")
            print(f"  - hora_almoco_saida: {form.hora_almoco_saida.data}")
            print(f"  - hora_almoco_retorno: {form.hora_almoco_retorno.data}")
        else:
            print("❌ Formulário inválido")

if __name__ == "__main__":
    print("=== TESTE DE INTERFACE DO PONTO ===")
    print("Reproduzindo cenário da imagem anexada...")
    
    # 1. Criar registro de teste igual ao da imagem
    registro_id = criar_registro_sabado_teste()
    
    if registro_id:
        # 2. Verificar como está sendo exibido
        verificar_exibicao_registro(registro_id)
        
        # 3. Testar formulário
        testar_formulario()
    
    print("\n✅ Teste de interface finalizado!")