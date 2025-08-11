#!/usr/bin/env python3
"""
Implementar filtros avançados e melhorias no controle de ponto
"""

from app import app, db
from models import *
from datetime import datetime, date, timedelta

def implementar_filtros_avancados():
    """Implementar filtros avançados no controle de ponto"""
    
    with app.app_context():
        print("🔍 IMPLEMENTANDO FILTROS AVANÇADOS")
        print("=" * 50)
        
        # 1. Estatísticas por tipo de registro
        print("📊 Estatísticas por tipo de registro (Admin 4):")
        
        tipos_stats = db.session.query(
            RegistroPonto.tipo_registro,
            db.func.count(RegistroPonto.id).label('total')
        ).join(Funcionario).filter(
            Funcionario.admin_id == 4
        ).group_by(RegistroPonto.tipo_registro).all()
        
        for tipo, total in tipos_stats:
            print(f"   {tipo or 'NULL'}: {total}")
        
        # 2. Funcionários com mais registros
        print("\n👥 Top 5 funcionários com mais registros:")
        
        func_stats = db.session.query(
            Funcionario.nome,
            db.func.count(RegistroPonto.id).label('total_registros')
        ).join(RegistroPonto).filter(
            Funcionario.admin_id == 4
        ).group_by(Funcionario.id, Funcionario.nome).order_by(
            db.text('total_registros DESC')
        ).limit(5).all()
        
        for nome, total in func_stats:
            print(f"   {nome}: {total} registros")
        
        # 3. Registros por mês
        print("\n📅 Registros por mês (2025):")
        
        meses_stats = db.session.query(
            db.func.extract('month', RegistroPonto.data).label('mes'),
            db.func.count(RegistroPonto.id).label('total')
        ).join(Funcionario).filter(
            Funcionario.admin_id == 4,
            db.func.extract('year', RegistroPonto.data) == 2025
        ).group_by(db.text('mes')).order_by(db.text('mes')).all()
        
        meses_nomes = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        
        for mes, total in meses_stats:
            nome_mes = meses_nomes.get(int(mes), f'Mês {mes}')
            print(f"   {nome_mes}: {total} registros")
        
        # 4. Análise de fins de semana
        print("\n📅 Análise específica de fins de semana:")
        
        sabados = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['sabado_trabalhado', 'sabado_folga'])
        ).count()
        
        domingos = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['domingo_trabalhado', 'domingo_folga'])
        ).count()
        
        print(f"   Sábados (trabalhados + folgas): {sabados}")
        print(f"   Domingos (trabalhados + folgas): {domingos}")
        
        # 5. Verificar integridade dos horários
        print("\n⏰ Verificação de integridade dos horários:")
        
        registros_sem_horario = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == 4,
            RegistroPonto.tipo_registro.in_(['trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado']),
            db.or_(
                RegistroPonto.hora_entrada.is_(None),
                RegistroPonto.hora_saida.is_(None)
            )
        ).count()
        
        print(f"   Registros de trabalho sem horários: {registros_sem_horario}")
        
        if registros_sem_horario > 0:
            print("   ⚠️ Encontrados registros de trabalho sem horários definidos")
        else:
            print("   ✅ Todos os registros de trabalho têm horários")
        
        print("\n🎯 ANÁLISE DE FILTROS CONCLUÍDA!")
        
        return True

if __name__ == "__main__":
    implementar_filtros_avancados()