#!/usr/bin/env python3
"""
CRIAR LANÇAMENTOS COMPLETOS PARA VALE VERDE
Cria lançamentos de sábado, domingo e feriado (14) para funcionários Vale Verde
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario, RegistroPonto
from datetime import datetime, date
from sqlalchemy import text

def criar_lancamentos_vale_verde():
    """Cria lançamentos para funcionários Vale Verde"""
    
    with app.app_context():
        print("CRIANDO LANÇAMENTOS VALE VERDE")
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
        
        # Definir datas para julho 2025
        datas_sabado = [
            date(2025, 7, 5),   # Sábado 1
            date(2025, 7, 12),  # Sábado 2  
            date(2025, 7, 19),  # Sábado 3
            date(2025, 7, 26),  # Sábado 4
        ]
        
        datas_domingo = [
            date(2025, 7, 6),   # Domingo 1
            date(2025, 7, 13),  # Domingo 2
            date(2025, 7, 20),  # Domingo 3
            date(2025, 7, 27),  # Domingo 4
        ]
        
        # Feriado dia 14 (segunda-feira)
        data_feriado = date(2025, 7, 14)
        
        registros_criados = 0
        
        # Criar lançamentos para cada funcionário
        for funcionario in funcionarios_vale_verde:
            print(f"\n🔄 Processando: {funcionario.nome}")
            
            # SÁBADOS TRABALHADOS
            for i, data_sabado in enumerate(datas_sabado, 1):
                # Verificar se já existe
                existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_sabado
                ).first()
                
                if not existente:
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_sabado,
                        tipo_registro='sabado_trabalhado',
                        entrada=datetime.strptime('07:00', '%H:%M').time(),
                        saida_almoco=datetime.strptime('12:00', '%H:%M').time(),
                        retorno_almoco=datetime.strptime('13:00', '%H:%M').time(),
                        saida=datetime.strptime('16:00', '%H:%M').time(),
                        horas_trabalhadas=8.0,
                        horas_extras=0.0,
                        percentual_extras=50.0,
                        observacoes=f'Sábado trabalhado {i} - Vale Verde'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                    print(f"  ✅ Sábado {data_sabado.strftime('%d/%m')} - Trabalhado")
            
            # DOMINGOS TRABALHADOS  
            for i, data_domingo in enumerate(datas_domingo, 1):
                # Verificar se já existe
                existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_domingo
                ).first()
                
                if not existente:
                    registro = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_domingo,
                        tipo_registro='domingo_trabalhado',
                        entrada=datetime.strptime('07:00', '%H:%M').time(),
                        saida_almoco=datetime.strptime('12:00', '%H:%M').time(),
                        retorno_almoco=datetime.strptime('13:00', '%H:%M').time(),
                        saida=datetime.strptime('16:00', '%H:%M').time(),
                        horas_trabalhadas=8.0,
                        horas_extras=0.0,
                        percentual_extras=100.0,
                        observacoes=f'Domingo trabalhado {i} - Vale Verde'
                    )
                    db.session.add(registro)
                    registros_criados += 1
                    print(f"  ✅ Domingo {data_domingo.strftime('%d/%m')} - Trabalhado")
            
            # FERIADO TRABALHADO (14/07)
            existente_feriado = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_feriado
            ).first()
            
            if not existente_feriado:
                registro_feriado = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_feriado,
                    tipo_registro='feriado_trabalhado',
                    entrada=datetime.strptime('07:00', '%H:%M').time(),
                    saida_almoco=datetime.strptime('12:00', '%H:%M').time(),
                    retorno_almoco=datetime.strptime('13:00', '%H:%M').time(),
                    saida=datetime.strptime('16:00', '%H:%M').time(),
                    horas_trabalhadas=8.0,
                    horas_extras=0.0,
                    percentual_extras=100.0,
                    observacoes='Feriado trabalhado - Vale Verde'
                )
                db.session.add(registro_feriado)
                registros_criados += 1
                print(f"  ✅ Feriado {data_feriado.strftime('%d/%m')} - Trabalhado")
        
        # Salvar todas as alterações
        try:
            db.session.commit()
            print(f"\n✅ SUCESSO: {registros_criados} registros criados!")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO ao salvar: {e}")
            return False

def verificar_registros_criados():
    """Verifica os registros criados"""
    
    with app.app_context():
        print("\nVERIFICANDO REGISTROS CRIADOS")
        print("=" * 50)
        
        # Contar por tipo
        tipos_contagem = {}
        
        funcionarios_vale_verde = Funcionario.query.filter(
            Funcionario.nome.like('%Vale Verde%')
        ).all()
        
        for funcionario in funcionarios_vale_verde:
            registros = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id
            ).filter(
                RegistroPonto.data >= date(2025, 7, 1),
                RegistroPonto.data <= date(2025, 7, 31)
            ).all()
            
            for registro in registros:
                tipo = registro.tipo_registro
                if tipo not in tipos_contagem:
                    tipos_contagem[tipo] = 0
                tipos_contagem[tipo] += 1
        
        print("CONTAGEM POR TIPO:")
        for tipo, count in sorted(tipos_contagem.items()):
            print(f"  • {tipo}: {count} registros")
        
        # Verificar especificamente sábados, domingos e feriado
        sabados = sum(1 for t, c in tipos_contagem.items() if 'sabado' in t)
        domingos = sum(1 for t, c in tipos_contagem.items() if 'domingo' in t) 
        feriados = sum(1 for t, c in tipos_contagem.items() if 'feriado' in t)
        
        print(f"\nRESUMO FINAL:")
        print(f"📅 Total Sábados: {sabados}")
        print(f"📅 Total Domingos: {domingos}")
        print(f"🎉 Total Feriados: {feriados}")

if __name__ == "__main__":
    # Criar lançamentos
    sucesso = criar_lancamentos_vale_verde()
    
    if sucesso:
        # Verificar resultado
        verificar_registros_criados()
        
        print("\n" + "=" * 60)
        print("✅ LANÇAMENTOS VALE VERDE CRIADOS!")
        print("✅ Sábados, domingos e feriado (14) lançados")
        print("✅ Badges na tabela mostrarão os tipos corretamente")
    else:
        print("\n❌ FALHA na criação dos lançamentos")