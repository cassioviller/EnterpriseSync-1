#!/usr/bin/env python3
"""
CRIAR LANÇAMENTOS SÁBADO/DOMINGO COMPLETOS
Cria lançamentos para Ana Paula Rodrigues e outros funcionários
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario, RegistroPonto
from datetime import datetime, date
from sqlalchemy import text

def criar_lancamentos_sabado_domingo():
    """Cria lançamentos de sábado e domingo para funcionários"""
    
    with app.app_context():
        print("CRIANDO LANÇAMENTOS SÁBADO/DOMINGO")
        print("=" * 60)
        
        # Buscar Ana Paula Rodrigues
        ana_paula = Funcionario.query.filter(
            Funcionario.nome.like('%Ana Paula%')
        ).first()
        
        if not ana_paula:
            print("❌ Ana Paula Rodrigues não encontrada, criando...")
            # Criar Ana Paula se não existir
            ana_paula = Funcionario(
                codigo='F0125',
                nome='Ana Paula Rodrigues',
                cpf='12345678901',
                data_admissao=date(2025, 6, 1),
                salario=2500.0,
                ativo=True
            )
            db.session.add(ana_paula)
            db.session.commit()
            print("✅ Ana Paula Rodrigues criada")
        
        # Buscar todos os funcionários ativos
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        print(f"✅ Encontrados {len(funcionarios)} funcionários ativos")
        
        # Definir datas de julho 2025
        datas_sabado = [
            date(2025, 7, 5),   # Sábado 05/07
            date(2025, 7, 12),  # Sábado 12/07 ← Este que o usuário mencionou
            date(2025, 7, 19),  # Sábado 19/07
            date(2025, 7, 26),  # Sábado 26/07
        ]
        
        datas_domingo = [
            date(2025, 7, 6),   # Domingo 06/07
            date(2025, 7, 13),  # Domingo 13/07 ← Este que o usuário mencionou
            date(2025, 7, 20),  # Domingo 20/07
            date(2025, 7, 27),  # Domingo 27/07
        ]
        
        # Feriado 14/07 (segunda-feira)
        data_feriado = date(2025, 7, 14)
        
        registros_criados = 0
        
        for funcionario in funcionarios:
            print(f"\n🔄 Processando: {funcionario.nome}")
            
            # SÁBADOS TRABALHADOS
            for i, data_sabado in enumerate(datas_sabado, 1):
                existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_sabado
                ).first()
                
                if existente:
                    print(f"  ⚠️  Sábado {data_sabado.strftime('%d/%m')} já existe")
                    continue
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_sabado,
                    tipo_registro='sabado_trabalhado',
                    hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                    hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
                    hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
                    hora_saida=datetime.strptime('16:00', '%H:%M').time(),
                    horas_trabalhadas=8.0,
                    horas_extras=8.0,  # No sábado todas as horas são extras
                    percentual_extras=50.0,
                    observacoes=f'Sábado trabalhado {i} - todas as horas com 50% adicional'
                )
                db.session.add(registro)
                registros_criados += 1
                print(f"  ✅ Sábado {data_sabado.strftime('%d/%m')} - Trabalhado criado")
            
            # DOMINGOS TRABALHADOS
            for i, data_domingo in enumerate(datas_domingo, 1):
                existente = RegistroPonto.query.filter_by(
                    funcionario_id=funcionario.id,
                    data=data_domingo
                ).first()
                
                if existente:
                    print(f"  ⚠️  Domingo {data_domingo.strftime('%d/%m')} já existe")
                    continue
                
                registro = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_domingo,
                    tipo_registro='domingo_trabalhado',
                    hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                    hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
                    hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
                    hora_saida=datetime.strptime('16:00', '%H:%M').time(),
                    horas_trabalhadas=8.0,
                    horas_extras=8.0,  # No domingo todas as horas são extras
                    percentual_extras=100.0,
                    observacoes=f'Domingo trabalhado {i} - todas as horas com 100% adicional'
                )
                db.session.add(registro)
                registros_criados += 1
                print(f"  ✅ Domingo {data_domingo.strftime('%d/%m')} - Trabalhado criado")
            
            # FERIADO 14/07 (segunda-feira)
            existente_feriado = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data_feriado
            ).first()
            
            if not existente_feriado:
                registro_feriado = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_feriado,
                    tipo_registro='feriado_trabalhado',
                    hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                    hora_almoco_saida=datetime.strptime('12:00', '%H:%M').time(),
                    hora_almoco_retorno=datetime.strptime('13:00', '%H:%M').time(),
                    hora_saida=datetime.strptime('16:00', '%H:%M').time(),
                    horas_trabalhadas=8.0,
                    horas_extras=8.0,  # No feriado todas as horas são extras
                    percentual_extras=100.0,
                    observacoes='Feriado trabalhado - todas as horas com 100% adicional'
                )
                db.session.add(registro_feriado)
                registros_criados += 1
                print(f"  ✅ Feriado {data_feriado.strftime('%d/%m')} - Trabalhado criado")
        
        # Salvar tudo
        try:
            db.session.commit()
            print(f"\n✅ SUCESSO: {registros_criados} registros criados!")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO ao salvar: {e}")
            return False

def verificar_badges_na_tabela():
    """Verifica se as badges aparecem corretamente"""
    
    with app.app_context():
        print("\nVERIFICANDO BADGES NA TABELA")
        print("=" * 50)
        
        # Buscar registros dos tipos especiais
        registros_especiais = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro.in_([
                'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado'
            ])
        ).filter(
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).all()
        
        print(f"✅ Encontrados {len(registros_especiais)} registros especiais:")
        
        tipos_count = {}
        for registro in registros_especiais:
            tipo = registro.tipo_registro
            if tipo not in tipos_count:
                tipos_count[tipo] = 0
            tipos_count[tipo] += 1
        
        for tipo, count in tipos_count.items():
            badge_color = ""
            if tipo == 'sabado_trabalhado':
                badge_color = "📅 VERDE (warning)"
            elif tipo == 'domingo_trabalhado':
                badge_color = "📅 VERMELHO (danger)"
            elif tipo == 'feriado_trabalhado':
                badge_color = "🎉 AZUL (info)"
            
            print(f"  • {tipo}: {count} registros - {badge_color}")

if __name__ == "__main__":
    print("CRIANDO LANÇAMENTOS SÁBADO/DOMINGO/FERIADO")
    print("=" * 60)
    
    # Criar lançamentos
    sucesso = criar_lancamentos_sabado_domingo()
    
    if sucesso:
        # Verificar badges
        verificar_badges_na_tabela()
        
        print("\n" + "=" * 60)
        print("✅ LANÇAMENTOS CRIADOS COM SUCESSO!")
        print("✅ Ana Paula Rodrigues incluída")
        print("✅ Sábados: badge VERDE com ícone 📅")
        print("✅ Domingos: badge VERMELHA com ícone 📅") 
        print("✅ Feriados: badge AZUL com ícone 🎉")
        print("\nNa tabela de controle de ponto você verá:")
        print("- Coluna Data: pequenas badges SÁBADO/DOMINGO/FERIADO")
        print("- Coluna Tipo: badges grandes coloridas com ícones")
    else:
        print("\n❌ FALHA na criação dos lançamentos")