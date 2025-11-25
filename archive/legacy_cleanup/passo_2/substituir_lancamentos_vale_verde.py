#!/usr/bin/env python3
"""
SUBSTITUIR LANÇAMENTOS VALE VERDE - DIAS ESPECÍFICOS
Substitui lançamentos nos dias 12, 13, 19 e 20/07/2025 para funcionários Vale Verde
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario, RegistroPonto
from datetime import datetime, date
from sqlalchemy import text

def substituir_lancamentos_vale_verde():
    """Substitui lançamentos específicos para funcionários Vale Verde"""
    
    with app.app_context():
        print("SUBSTITUINDO LANÇAMENTOS VALE VERDE")
        print("=" * 60)
        
        # Buscar funcionários Vale Verde
        funcionarios_vale_verde = Funcionario.query.filter(
            Funcionario.nome.like('%Vale Verde%')
        ).all()
        
        if not funcionarios_vale_verde:
            print("❌ Nenhum funcionário Vale Verde encontrado")
            return False
        
        print(f"✅ Encontrados {len(funcionarios_vale_verde)} funcionários Vale Verde:")
        for func in funcionarios_vale_verde:
            print(f"  • {func.codigo} - {func.nome}")
        
        # Datas específicas solicitadas
        datas_substituir = [
            {'data': date(2025, 7, 12), 'tipo': 'sabado_trabalhado', 'dia': 'SÁBADO'},    # 12/07 - Sábado
            {'data': date(2025, 7, 13), 'tipo': 'domingo_trabalhado', 'dia': 'DOMINGO'},  # 13/07 - Domingo
            {'data': date(2025, 7, 19), 'tipo': 'sabado_trabalhado', 'dia': 'SÁBADO'},    # 19/07 - Sábado  
            {'data': date(2025, 7, 20), 'tipo': 'domingo_trabalhado', 'dia': 'DOMINGO'},  # 20/07 - Domingo
        ]
        
        registros_alterados = 0
        
        for funcionario in funcionarios_vale_verde:
            print(f"\n🔄 Processando: {funcionario.nome}")
            
            for config in datas_substituir:
                data_lancamento = config['data']
                tipo_lancamento = config['tipo']
                dia_nome = config['dia']
                
                # Verificar se já existe registro na data
                registro_existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_lancamento
                ).first()
                
                if registro_existente:
                    # Atualizar registro existente
                    print(f"  🔄 Atualizando {dia_nome} {data_lancamento.strftime('%d/%m')}")
                    
                    registro_existente.tipo_registro = tipo_lancamento
                    registro_existente.hora_entrada = datetime.strptime('07:00', '%H:%M').time()
                    registro_existente.hora_almoco_saida = datetime.strptime('12:00', '%H:%M').time()
                    registro_existente.hora_almoco_retorno = datetime.strptime('13:00', '%H:%M').time()
                    registro_existente.hora_saida = datetime.strptime('16:00', '%H:%M').time()
                    registro_existente.horas_trabalhadas = 8.0
                    registro_existente.horas_extras = 8.0 if tipo_lancamento != 'trabalho_normal' else 0.0
                    
                    if tipo_lancamento == 'sabado_trabalhado':
                        registro_existente.percentual_extras = 50.0
                        registro_existente.observacoes = 'Sábado trabalhado - todas as horas com 50% adicional'
                    elif tipo_lancamento == 'domingo_trabalhado':
                        registro_existente.percentual_extras = 100.0
                        registro_existente.observacoes = 'Domingo trabalhado - todas as horas com 100% adicional'
                    
                    registros_alterados += 1
                    
                else:
                    # Criar novo registro
                    print(f"  ✅ Criando {dia_nome} {data_lancamento.strftime('%d/%m')}")
                    
                    novo_registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_lancamento,
                        tipo_registro=tipo_lancamento,
                        hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                        hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
                        hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
                        hora_saida=datetime.strptime('16:00', '%H:%M').time(),
                        horas_trabalhadas=8.0,
                        horas_extras=8.0 if tipo_lancamento != 'trabalho_normal' else 0.0,
                        percentual_extras=50.0 if tipo_lancamento == 'sabado_trabalhado' else 100.0,
                        observacoes=f'{dia_nome} trabalhado - Vale Verde'
                    )
                    db.session.add(novo_registro)
                    registros_alterados += 1
        
        # Salvar alterações
        try:
            db.session.commit()
            print(f"\n✅ SUCESSO: {registros_alterados} registros alterados/criados!")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO ao salvar: {e}")
            return False

def verificar_resultados():
    """Verifica se os lançamentos estão corretos"""
    
    with app.app_context():
        print("\nVERIFICANDO RESULTADOS")
        print("=" * 50)
        
        # Buscar registros específicos
        datas_verificar = [
            date(2025, 7, 12),  # Sábado
            date(2025, 7, 13),  # Domingo
            date(2025, 7, 19),  # Sábado
            date(2025, 7, 20),  # Domingo
        ]
        
        funcionarios_vale_verde = Funcionario.query.filter(
            Funcionario.nome.like('%Vale Verde%')
        ).all()
        
        print("REGISTROS POR DATA:")
        for data_verif in datas_verificar:
            dia_semana = "SÁBADO" if data_verif.weekday() == 5 else "DOMINGO" if data_verif.weekday() == 6 else "OUTRO"
            
            registros_data = RegistroPonto.query.filter(
                RegistroPonto.data == data_verif,
                RegistroPonto.funcionario_id.in_([f.id for f in funcionarios_vale_verde])
            ).all()
            
            print(f"\n📅 {data_verif.strftime('%d/%m/%Y')} ({dia_semana}):")
            for registro in registros_data:
                tipo_badge = ""
                if registro.tipo_registro == 'sabado_trabalhado':
                    tipo_badge = "📅 BADGE VERDE (warning)"
                elif registro.tipo_registro == 'domingo_trabalhado':
                    tipo_badge = "📅 BADGE VERMELHA (danger)"
                
                print(f"  • {registro.funcionario.nome}: {registro.tipo_registro} - {tipo_badge}")
        
        print(f"\nRESUMO:")
        print(f"✅ {len(funcionarios_vale_verde)} funcionários Vale Verde")
        print(f"✅ 4 datas específicas processadas")
        print(f"✅ Badges na tabela mostrarão:")
        print(f"   - Coluna Data: SÁBADO/DOMINGO")
        print(f"   - Coluna Tipo: Sábado Trabalhado/Domingo Trabalhado")

if __name__ == "__main__":
    print("SUBSTITUINDO LANÇAMENTOS VALE VERDE - DIAS ESPECÍFICOS")
    print("=" * 70)
    
    # Substituir lançamentos
    sucesso = substituir_lancamentos_vale_verde()
    
    if sucesso:
        # Verificar resultados
        verificar_resultados()
        
        print("\n" + "=" * 70)
        print("✅ LANÇAMENTOS VALE VERDE ATUALIZADOS!")
        print("✅ Dias 12, 13, 19, 20/07 configurados")
        print("✅ Sábados: tipo 'sabado_trabalhado' - badge VERDE")
        print("✅ Domingos: tipo 'domingo_trabalhado' - badge VERMELHA")
        print("\nNa tabela de controle de ponto você verá:")
        print("- 12/07: SÁBADO na data, 'Sábado Trabalhado' no tipo")
        print("- 13/07: DOMINGO na data, 'Domingo Trabalhado' no tipo")
        print("- 19/07: SÁBADO na data, 'Sábado Trabalhado' no tipo")
        print("- 20/07: DOMINGO na data, 'Domingo Trabalhado' no tipo")
    else:
        print("\n❌ FALHA na substituição dos lançamentos")