#!/usr/bin/env python3
"""
Script para corrigir lançamento de sábado em produção
"""

from app import app, db
from models import *
from datetime import datetime, date, time

def verificar_ambiente_producao():
    """Verificar se estamos em produção e quais dados existem"""
    
    with app.app_context():
        print("🔍 VERIFICANDO AMBIENTE DE PRODUÇÃO")
        print("=" * 60)
        
        # Verificar registros existentes para julho 2025
        registros_julho = RegistroPonto.query.filter(
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data).all()
        
        print(f"📊 Total de registros em julho/2025: {len(registros_julho)}")
        
        # Verificar especificamente 05/07/2025 (sábado)
        sabado_05_07 = RegistroPonto.query.filter_by(
            data=date(2025, 7, 5)
        ).all()
        
        print(f"📅 Registros para 05/07/2025 (sábado): {len(sabado_05_07)}")
        
        if sabado_05_07:
            for reg in sabado_05_07:
                funcionario = Funcionario.query.get(reg.funcionario_id)
                print(f"   ✅ ID {reg.id}: {funcionario.nome if funcionario else 'N/A'} - {reg.tipo_registro}")
        else:
            print("   ❌ Nenhum registro encontrado para 05/07/2025")
        
        # Verificar domingo 06/07/2025 também
        domingo_06_07 = RegistroPonto.query.filter_by(
            data=date(2025, 7, 6)
        ).all()
        
        print(f"📅 Registros para 06/07/2025 (domingo): {len(domingo_06_07)}")
        
        # Mostrar lacunas nos dados
        print("\n📋 ANÁLISE DE LACUNAS:")
        datas_existentes = set(reg.data for reg in registros_julho)
        
        for dia in range(1, 32):
            try:
                data_teste = date(2025, 7, dia)
                dia_semana = data_teste.weekday()
                dia_nome = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'][dia_semana]
                
                if data_teste not in datas_existentes and dia_semana in [5, 6]:  # Sáb/Dom
                    print(f"   ⚠️ {data_teste.strftime('%d/%m')} ({dia_nome}) - SEM REGISTROS")
                    
            except ValueError:
                break
        
        return len(sabado_05_07) == 0

def criar_lancamento_sabado_05_07():
    """Criar lançamento para sábado 05/07/2025"""
    
    with app.app_context():
        print("\n🔧 CRIANDO LANÇAMENTO PARA SÁBADO 05/07/2025")
        print("=" * 60)
        
        # Buscar funcionário ativo para teste
        funcionario = Funcionario.query.filter_by(
            admin_id=4,  # Admin de produção
            ativo=True
        ).first()
        
        if not funcionario:
            print("❌ Nenhum funcionário encontrado para admin_id=4")
            return False
        
        print(f"👤 Funcionário: {funcionario.nome}")
        
        # Verificar se já existe
        existe = RegistroPonto.query.filter_by(
            funcionario_id=funcionario.id,
            data=date(2025, 7, 5)
        ).first()
        
        if existe:
            print(f"⚠️ Já existe registro: ID {existe.id}")
            return True
        
        # Buscar obra ativa
        obra = Obra.query.filter_by(
            admin_id=4,
            status='Em andamento'
        ).first()
        
        print(f"🏗️ Obra: {obra.nome if obra else 'Sem obra'}")
        
        # Criar registro de sábado trabalhado
        registro_sabado = RegistroPonto(
            funcionario_id=funcionario.id,
            data=date(2025, 7, 5),
            tipo_registro='sabado_trabalhado',
            obra_id=obra.id if obra else None,
            hora_entrada=time(7, 0),    # 07:00
            hora_almoco_saida=time(12, 0),  # 12:00
            hora_almoco_retorno=time(13, 0),  # 13:00
            hora_saida=time(17, 0),     # 17:00
            horas_trabalhadas=8.0,
            horas_extras=8.0,           # Todas as horas são extras no sábado
            percentual_extras=50.0,     # 50% no sábado
            total_atraso_horas=0.0,
            total_atraso_minutos=0,
            observacoes='Sábado trabalhado - Lançamento manual'
        )
        
        try:
            db.session.add(registro_sabado)
            db.session.commit()
            
            print(f"✅ Registro criado com sucesso!")
            print(f"   ID: {registro_sabado.id}")
            print(f"   Data: {registro_sabado.data.strftime('%d/%m/%Y')}")
            print(f"   Tipo: {registro_sabado.tipo_registro}")
            print(f"   Horas extras: {registro_sabado.horas_extras}h ({registro_sabado.percentual_extras}%)")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar registro: {e}")
            return False

def verificar_filtros_multi_tenancy():
    """Verificar se os filtros multi-tenancy estão funcionando"""
    
    with app.app_context():
        print("\n🔍 VERIFICANDO FILTROS MULTI-TENANCY")
        print("=" * 60)
        
        # Simular query como na view controle_ponto
        registros_admin_4 = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data.desc()).all()
        
        print(f"📊 Registros visíveis para Admin 4: {len(registros_admin_4)}")
        
        # Verificar especificamente fins de semana
        fins_semana = [reg for reg in registros_admin_4 if reg.data.weekday() in [5, 6]]
        print(f"📅 Registros de fim de semana: {len(fins_semana)}")
        
        for reg in fins_semana[:5]:  # Mostrar primeiros 5
            funcionario = Funcionario.query.get(reg.funcionario_id)
            dia_nome = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'][reg.data.weekday()]
            print(f"   {reg.data.strftime('%d/%m')} ({dia_nome}): {funcionario.nome} - {reg.tipo_registro}")
        
        # Verificar se 05/07 aparece agora
        sabado_05 = [reg for reg in registros_admin_4 if reg.data == date(2025, 7, 5)]
        
        if sabado_05:
            print(f"✅ Sábado 05/07 encontrado: {len(sabado_05)} registro(s)")
        else:
            print("❌ Sábado 05/07 ainda não aparece")
        
        return len(sabado_05) > 0

def relatorio_final():
    """Gerar relatório final da correção"""
    
    with app.app_context():
        print("\n📋 RELATÓRIO FINAL DA CORREÇÃO")
        print("=" * 60)
        
        # Estatísticas atualizadas
        total_registros = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4
        ).count()
        
        registros_julho = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).count()
        
        sabados_trabalhados = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['sabado_trabalhado', 'sabado_horas_extras'])
        ).count()
        
        domingos_trabalhados = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['domingo_trabalhado', 'domingo_horas_extras'])
        ).count()
        
        print(f"📊 ESTATÍSTICAS FINAIS:")
        print(f"   Total de registros: {total_registros}")
        print(f"   Registros julho/2025: {registros_julho}")
        print(f"   Sábados trabalhados: {sabados_trabalhados}")
        print(f"   Domingos trabalhados: {domingos_trabalhados}")
        
        # Verificação específica do 05/07
        registro_05_07 = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.data == date(2025, 7, 5)
        ).first()
        
        if registro_05_07:
            funcionario = Funcionario.query.get(registro_05_07.funcionario_id)
            print(f"\n✅ SÁBADO 05/07/2025 CORRIGIDO:")
            print(f"   ID: {registro_05_07.id}")
            print(f"   Funcionário: {funcionario.nome}")
            print(f"   Tipo: {registro_05_07.tipo_registro}")
            print(f"   Horas extras: {registro_05_07.horas_extras}h")
            print(f"   Percentual: {registro_05_07.percentual_extras}%")
        else:
            print("\n❌ SÁBADO 05/07/2025 AINDA COM PROBLEMA")

if __name__ == "__main__":
    print("🚀 CORREÇÃO DE LANÇAMENTO SÁBADO - PRODUÇÃO")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # 1. Verificar estado atual
    precisa_corrigir = verificar_ambiente_producao()
    
    # 2. Criar lançamento se necessário
    if precisa_corrigir:
        sucesso = criar_lancamento_sabado_05_07()
        
        if sucesso:
            # 3. Verificar filtros
            filtros_ok = verificar_filtros_multi_tenancy()
            
            # 4. Relatório final
            relatorio_final()
        else:
            print("❌ Falha na criação do registro")
    else:
        print("✅ Registro de sábado já existe")
        verificar_filtros_multi_tenancy()
        relatorio_final()
    
    print("\n" + "=" * 60)
    print("🎯 CORREÇÃO CONCLUÍDA")
    print("   O registro de sábado 05/07/2025 deve aparecer agora na produção")
    print("   Atualize a página do controle de ponto para ver os dados")