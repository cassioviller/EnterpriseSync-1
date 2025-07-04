#!/usr/bin/env python3
"""
Script para criar dados de teste demonstrando meio período/saída antecipada
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time, datetime, timedelta
import random

def criar_dados_meio_periodo():
    """
    Cria dados de teste para demonstrar a lógica de meio período
    """
    with app.app_context():
        # Buscar funcionários ativos
        funcionarios = Funcionario.query.filter_by(ativo=True).limit(3).all()
        
        if not funcionarios:
            print("❌ Nenhum funcionário encontrado!")
            return
        
        # Data base para criar os registros (últimos 5 dias úteis)
        hoje = date.today()
        
        # Criar registros variados para demonstrar a lógica
        registros_criados = 0
        
        for funcionario in funcionarios:
            print(f"\n📋 Criando registros para: {funcionario.nome}")
            
            # Registros dos últimos 5 dias úteis
            for i in range(5):
                data_registro = hoje - timedelta(days=i)
                
                # Pular fins de semana
                if data_registro.weekday() >= 5:
                    continue
                
                # Verificar se já existe registro para esta data
                registro_existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_registro
                ).first()
                
                if registro_existente:
                    print(f"   ⚠️  Registro já existe para {data_registro.strftime('%d/%m/%Y')}")
                    continue
                
                # Criar diferentes cenários
                cenario = i % 4
                
                if cenario == 0:
                    # CENÁRIO 1: Meio período - saída antecipada (como no exemplo)
                    entrada = time(8, 0)      # 08:00
                    saida = time(14, 30)      # 14:30 (saída antecipada)
                    almoco_saida = time(12, 0)
                    almoco_retorno = time(13, 0)
                    
                    # Calcular horas trabalhadas
                    entrada_dt = datetime.combine(data_registro, entrada)
                    saida_dt = datetime.combine(data_registro, saida)
                    almoco_total = 1.0  # 1 hora
                    
                    total_minutos = (saida_dt - entrada_dt).total_seconds() / 60
                    horas_trabalhadas = (total_minutos - (almoco_total * 60)) / 60
                    
                    print(f"   ✅ Meio período: {entrada.strftime('%H:%M')}-{saida.strftime('%H:%M')} = {horas_trabalhadas:.1f}h")
                    
                elif cenario == 1:
                    # CENÁRIO 2: Atraso
                    entrada = time(8, 45)     # 08:45 (45 min de atraso)
                    saida = time(17, 0)       # 17:00
                    almoco_saida = time(12, 0)
                    almoco_retorno = time(13, 0)
                    
                    # Calcular horas trabalhadas
                    entrada_dt = datetime.combine(data_registro, entrada)
                    saida_dt = datetime.combine(data_registro, saida)
                    almoco_total = 1.0
                    
                    total_minutos = (saida_dt - entrada_dt).total_seconds() / 60
                    horas_trabalhadas = (total_minutos - (almoco_total * 60)) / 60
                    
                    print(f"   ⏰ Atraso: {entrada.strftime('%H:%M')}-{saida.strftime('%H:%M')} = {horas_trabalhadas:.1f}h")
                    
                elif cenario == 2:
                    # CENÁRIO 3: Dia normal
                    entrada = time(8, 0)      # 08:00
                    saida = time(17, 0)       # 17:00
                    almoco_saida = time(12, 0)
                    almoco_retorno = time(13, 0)
                    
                    # Calcular horas trabalhadas
                    entrada_dt = datetime.combine(data_registro, entrada)
                    saida_dt = datetime.combine(data_registro, saida)
                    almoco_total = 1.0
                    
                    total_minutos = (saida_dt - entrada_dt).total_seconds() / 60
                    horas_trabalhadas = (total_minutos - (almoco_total * 60)) / 60
                    
                    print(f"   ✅ Normal: {entrada.strftime('%H:%M')}-{saida.strftime('%H:%M')} = {horas_trabalhadas:.1f}h")
                    
                else:
                    # CENÁRIO 4: Falta (sem registro)
                    print(f"   ❌ Falta: {data_registro.strftime('%d/%m/%Y')} (sem registro)")
                    continue
                
                # Criar o registro no banco
                novo_registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_registro,
                    hora_entrada=entrada,
                    hora_saida=saida,
                    hora_almoco_saida=almoco_saida,
                    hora_almoco_retorno=almoco_retorno,
                    horas_trabalhadas=horas_trabalhadas,
                    horas_extras=max(0, horas_trabalhadas - 8),
                    observacoes=f"Teste - {['Meio período', 'Atraso', 'Normal'][cenario]}"
                )
                
                db.session.add(novo_registro)
                registros_criados += 1
        
        # Salvar tudo no banco
        try:
            db.session.commit()
            print(f"\n✅ {registros_criados} registros criados com sucesso!")
            print("\n📊 Exemplos criados:")
            print("   • Meio período: Funcionário sai 14:30 (1.5h perdidas)")
            print("   • Atraso: Funcionário chega 08:45 (45 min atraso)")
            print("   • Normal: Funcionário trabalha 08:00-17:00")
            print("   • Falta: Dias sem registro")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao salvar: {e}")

def testar_calculo_meio_periodo():
    """
    Testa o cálculo de meio período com exemplo prático
    """
    from utils import processar_meio_periodo_exemplo
    
    exemplo = processar_meio_periodo_exemplo()
    
    print("\n🧮 Exemplo de Cálculo de Meio Período:")
    print(f"   Entrada: {exemplo['entrada']}")
    print(f"   Saída: {exemplo['saida']}")
    print(f"   Horas Trabalhadas: {exemplo['horas_trabalhadas']:.1f}h")
    print(f"   Horas Perdidas: {exemplo['horas_perdidas']:.1f}h")
    print(f"   Situação: {exemplo['situacao']}")

if __name__ == "__main__":
    print("🚀 Criando dados de teste para meio período...")
    criar_dados_meio_periodo()
    testar_calculo_meio_periodo()
    print("\n✅ Pronto! Agora você pode visualizar na página de perfil do funcionário.")