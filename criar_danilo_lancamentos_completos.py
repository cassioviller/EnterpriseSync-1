#!/usr/bin/env python3
"""
CRIAR DANILO E LANÇAMENTOS COMPLETOS JULHO 2025
Cria funcionário Danilo José de Oliveira e lançamentos completos para testar badges
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import Funcionario, RegistroPonto
from datetime import datetime, date
import calendar

def criar_funcionario_danilo():
    """Cria o funcionário Danilo José de Oliveira"""
    
    with app.app_context():
        # Verificar se já existe
        danilo_existente = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if danilo_existente:
            print(f"✅ Danilo já existe: {danilo_existente.codigo} - {danilo_existente.nome}")
            return danilo_existente
        
        # Criar novo funcionário
        danilo = Funcionario(
            codigo='F0126',
            nome='Danilo José de Oliveira',
            cpf='98765432100',
            data_admissao=date(2025, 6, 15),
            salario=2800.0,
            ativo=True
        )
        
        db.session.add(danilo)
        db.session.commit()
        
        print(f"✅ Danilo criado: {danilo.codigo} - {danilo.nome}")
        return danilo

def criar_lancamentos_julho_completo(funcionario):
    """Cria lançamentos completos para julho 2025"""
    
    print(f"\n🔄 Criando lançamentos para {funcionario.nome}")
    print("=" * 50)
    
    # Obter todos os dias de julho 2025
    ano = 2025
    mes = 7
    dias_mes = calendar.monthrange(ano, mes)[1]
    
    registros_criados = 0
    
    for dia in range(1, dias_mes + 1):
        data_lancamento = date(ano, mes, dia)
        dia_semana = data_lancamento.weekday()  # 0=segunda, 6=domingo
        
        # Verificar se já existe
        existente = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=data_lancamento
        ).first()
        
        if existente:
            print(f"  ⚠️  {data_lancamento.strftime('%d/%m')} já existe")
            continue
        
        # Definir tipo baseado no dia da semana
        if dia_semana == 5:  # Sábado
            tipo_registro = 'sabado_folga'
            observacoes = 'Sábado - Folga (não trabalhado)'
            horas_trabalhadas = 0.0
            horas_extras = 0.0
            percentual_extras = 0.0
            entrada = None
            almoco_saida = None
            almoco_retorno = None
            saida = None
            
        elif dia_semana == 6:  # Domingo
            tipo_registro = 'domingo_folga'
            observacoes = 'Domingo - Folga (não trabalhado)'
            horas_trabalhadas = 0.0
            horas_extras = 0.0
            percentual_extras = 0.0
            entrada = None
            almoco_saida = None
            almoco_retorno = None
            saida = None
            
        else:  # Segunda a sexta (dias úteis)
            tipo_registro = 'trabalho_normal'
            observacoes = 'Trabalho normal - horário completo'
            horas_trabalhadas = 8.0
            horas_extras = 0.0
            percentual_extras = 0.0
            entrada = datetime.strptime('07:00', '%H:%M').time()
            almoco_saida = datetime.strptime('12:00', '%H:%M').time()
            almoco_retorno = datetime.strptime('13:00', '%H:%M').time()
            saida = datetime.strptime('16:00', '%H:%M').time()
        
        # Criar registro
        registro = RegistroPonto(
            funcionario_id=funcionario.id,
            data=data_lancamento,
            tipo_registro=tipo_registro,
            hora_entrada=entrada,
            hora_almoco_saida=almoco_saida,
            hora_almoco_retorno=almoco_retorno,
            hora_saida=saida,
            horas_trabalhadas=horas_trabalhadas,
            horas_extras=horas_extras,
            percentual_extras=percentual_extras,
            observacoes=observacoes
        )
        
        db.session.add(registro)
        registros_criados += 1
        
        # Mostrar progresso
        nome_dia = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM'][dia_semana]
        if tipo_registro == 'trabalho_normal':
            print(f"  ✅ {data_lancamento.strftime('%d/%m')} ({nome_dia}): Trabalho Normal")
        elif tipo_registro == 'sabado_folga':
            print(f"  🏠 {data_lancamento.strftime('%d/%m')} ({nome_dia}): Sábado Folga")
        elif tipo_registro == 'domingo_folga':
            print(f"  🏠 {data_lancamento.strftime('%d/%m')} ({nome_dia}): Domingo Folga")
    
    try:
        db.session.commit()
        print(f"\n✅ {registros_criados} lançamentos criados para {funcionario.nome}")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Erro ao salvar: {e}")
        return False

def verificar_badges_danilo():
    """Verifica se as badges estão corretas para Danilo"""
    
    with app.app_context():
        print("\nVERIFICANDO BADGES PARA DANILO")
        print("=" * 50)
        
        danilo = Funcionario.query.filter(
            Funcionario.nome.like('%Danilo José%')
        ).first()
        
        if not danilo:
            print("❌ Danilo não encontrado")
            return
        
        # Buscar registros de julho
        registros = RegistroPonto.query.filter_by(
            funcionario_id=danilo.id
        ).filter(
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data).all()
        
        print(f"✅ Encontrados {len(registros)} registros para Danilo")
        
        # Contar por tipo
        tipos_count = {}
        for registro in registros:
            tipo = registro.tipo_registro
            if tipo not in tipos_count:
                tipos_count[tipo] = 0
            tipos_count[tipo] += 1
        
        print("\nCONTAGEM POR TIPO:")
        for tipo, count in sorted(tipos_count.items()):
            badge_info = ""
            if tipo == 'trabalho_normal':
                badge_info = "👷 BADGE VERDE (success)"
            elif tipo == 'sabado_folga':
                badge_info = "📅 BADGE CINZA CLARO (light)"
            elif tipo == 'domingo_folga':
                badge_info = "📅 BADGE CINZA CLARO (light)"
            
            print(f"  • {tipo}: {count} registros - {badge_info}")
        
        # Mostrar alguns exemplos específicos
        print("\nEXEMPLOS DE BADGES NA TABELA:")
        exemplos = [
            date(2025, 7, 12),  # Sábado
            date(2025, 7, 13),  # Domingo
            date(2025, 7, 14),  # Segunda
            date(2025, 7, 19),  # Sábado
            date(2025, 7, 20),  # Domingo
        ]
        
        for data_exemplo in exemplos:
            registro = next((r for r in registros if r.data == data_exemplo), None)
            if registro:
                dia_semana = data_exemplo.strftime('%A')
                if registro.tipo_registro == 'trabalho_normal':
                    print(f"  📅 {data_exemplo.strftime('%d/%m')} ({dia_semana}): SEM badge na data + 'Trabalho Normal' no tipo")
                elif registro.tipo_registro == 'sabado_folga':
                    print(f"  📅 {data_exemplo.strftime('%d/%m')} ({dia_semana}): badge 'SÁBADO' na data + 'Sábado - Folga' no tipo")
                elif registro.tipo_registro == 'domingo_folga':
                    print(f"  📅 {data_exemplo.strftime('%d/%m')} ({dia_semana}): badge 'DOMINGO' na data + 'Domingo - Folga' no tipo")

if __name__ == "__main__":
    print("CRIANDO DANILO E LANÇAMENTOS COMPLETOS")
    print("=" * 60)
    
    with app.app_context():
        # Criar funcionário
        danilo = criar_funcionario_danilo()
        
        # Criar lançamentos
        sucesso = criar_lancamentos_julho_completo(danilo)
        
        if sucesso:
            # Verificar badges
            verificar_badges_danilo()
            
            print("\n" + "=" * 60)
            print("✅ DANILO CRIADO COM SUCESSO!")
            print("✅ Lançamentos completos julho 2025")
            print("✅ Trabalho normal: segunda a sexta")
            print("✅ Folgas: sábados e domingos")
            print("\nNa tabela de controle de ponto você verá:")
            print("- Dias úteis: badge verde 'Trabalho Normal'")
            print("- Sábados: badge 'SÁBADO' na data + 'Sábado - Folga' no tipo")
            print("- Domingos: badge 'DOMINGO' na data + 'Domingo - Folga' no tipo")
        else:
            print("\n❌ FALHA na criação dos lançamentos")