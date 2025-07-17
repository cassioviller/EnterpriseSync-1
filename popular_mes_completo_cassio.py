#!/usr/bin/env python3
"""
Script para popular todos os dias do mês 6 (junho/2025) para o funcionário Cássio
com todos os tipos de lançamento possíveis, incluindo os novos tipos:
- sabado_nao_trabalhado
- domingo_nao_trabalhado
"""

from datetime import date, time, timedelta
from app import app, db
from models import Funcionario, RegistroPonto, Obra


def popular_mes_completo_cassio():
    """
    Popula todos os dias de junho/2025 para Cássio com tipos variados
    """
    with app.app_context():
        # Buscar Cássio
        cassio = Funcionario.query.filter_by(codigo='F0006').first()
        if not cassio:
            print("❌ Funcionário Cássio não encontrado")
            return
        
        # Buscar obra para os lançamentos
        obra = Obra.query.first()
        if not obra:
            print("❌ Nenhuma obra encontrada")
            return
        
        print(f"🔄 Populando mês completo para: {cassio.nome}")
        
        # Limpar registros existentes de junho/2025
        registros_existentes = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == cassio.id,
            RegistroPonto.data >= date(2025, 6, 1),
            RegistroPonto.data <= date(2025, 6, 30)
        ).all()
        
        for registro in registros_existentes:
            db.session.delete(registro)
        
        print(f"🗑️  Removidos {len(registros_existentes)} registros existentes")
        
        # Feriados em junho/2025
        feriados_junho = [
            date(2025, 6, 19),  # Corpus Christi
        ]
        
        # Criar registros para todos os dias do mês
        registros_criados = []
        data_atual = date(2025, 6, 1)
        
        while data_atual <= date(2025, 6, 30):
            dia_semana = data_atual.weekday()  # 0=Segunda, 6=Domingo
            
            # Determinar tipo de registro baseado no dia
            if data_atual in feriados_junho:
                # Feriado trabalhado (Corpus Christi)
                if data_atual == date(2025, 6, 19):
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='feriado_trabalhado',
                        hora_entrada=time(8, 0),
                        hora_saida=time(16, 0),
                        horas_trabalhadas=8.0,
                        horas_extras=8.0,  # 100% de horas extras
                        percentual_extras=100,
                        observacoes='Feriado trabalhado - Corpus Christi'
                    )
                    registros_criados.append(registro)
            
            elif dia_semana == 5:  # Sábado
                if data_atual.day in [7, 14]:  # Sábados trabalhados
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='sabado_horas_extras',
                        hora_entrada=time(8, 0),
                        hora_saida=time(12, 0),
                        horas_trabalhadas=4.0,
                        horas_extras=4.0,
                        percentual_extras=50,
                        observacoes='Sábado - Horas extras'
                    )
                    registros_criados.append(registro)
                else:  # Sábados não trabalhados
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='sabado_nao_trabalhado',
                        observacoes='Sábado de folga'
                    )
                    registros_criados.append(registro)
            
            elif dia_semana == 6:  # Domingo
                if data_atual.day == 15:  # Domingo trabalhado
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='domingo_horas_extras',
                        hora_entrada=time(8, 0),
                        hora_saida=time(12, 0),
                        horas_trabalhadas=4.0,
                        horas_extras=4.0,
                        percentual_extras=100,
                        observacoes='Domingo - Horas extras (100%)'
                    )
                    registros_criados.append(registro)
                else:  # Domingos não trabalhados
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='domingo_nao_trabalhado',
                        observacoes='Domingo de folga'
                    )
                    registros_criados.append(registro)
            
            else:  # Dias úteis (Segunda a Sexta)
                if data_atual.day == 10:  # Uma falta
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='falta',
                        observacoes='Falta não justificada'
                    )
                    registros_criados.append(registro)
                
                elif data_atual.day == 11:  # Uma falta justificada
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='falta_justificada',
                        observacoes='Falta justificada - Consulta médica'
                    )
                    registros_criados.append(registro)
                
                elif data_atual.day == 12:  # Meio período
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='meio_periodo',
                        hora_entrada=time(8, 0),
                        hora_saida=time(12, 0),
                        horas_trabalhadas=4.0,
                        observacoes='Meio período - Saída antecipada'
                    )
                    registros_criados.append(registro)
                
                elif data_atual.day == 13:  # Trabalho com atraso
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='trabalho_normal',
                        hora_entrada=time(8, 30),  # 30 min atraso
                        hora_saida=time(17, 0),
                        hora_almoco_saida=time(12, 0),
                        hora_almoco_retorno=time(13, 0),
                        horas_trabalhadas=7.5,
                        minutos_atraso_entrada=30,
                        total_atraso_minutos=30,
                        total_atraso_horas=0.5,
                        observacoes='Atraso de 30 minutos na entrada'
                    )
                    registros_criados.append(registro)
                
                elif data_atual.day == 16:  # Trabalho com saída antecipada
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='trabalho_normal',
                        hora_entrada=time(8, 0),
                        hora_saida=time(16, 45),  # 15 min mais cedo
                        hora_almoco_saida=time(12, 0),
                        hora_almoco_retorno=time(13, 0),
                        horas_trabalhadas=7.75,
                        minutos_atraso_saida=15,
                        total_atraso_minutos=15,
                        total_atraso_horas=0.25,
                        observacoes='Saída 15 minutos mais cedo'
                    )
                    registros_criados.append(registro)
                
                else:  # Trabalho normal
                    registro = RegistroPonto(
                        funcionario_id=cassio.id,
                        obra_id=obra.id,
                        data=data_atual,
                        tipo_registro='trabalho_normal',
                        hora_entrada=time(8, 0),
                        hora_saida=time(17, 0),
                        hora_almoco_saida=time(12, 0),
                        hora_almoco_retorno=time(13, 0),
                        horas_trabalhadas=8.0,
                        observacoes='Trabalho normal'
                    )
                    registros_criados.append(registro)
            
            data_atual += timedelta(days=1)
        
        # Salvar todos os registros
        for registro in registros_criados:
            db.session.add(registro)
        
        db.session.commit()
        
        print(f"✅ Criados {len(registros_criados)} registros para junho/2025")
        
        # Mostrar resumo por tipo
        tipos_resumo = {}
        for registro in registros_criados:
            tipo = registro.tipo_registro
            tipos_resumo[tipo] = tipos_resumo.get(tipo, 0) + 1
        
        print("\n📊 Resumo por tipo:")
        for tipo, count in sorted(tipos_resumo.items()):
            print(f"  - {tipo}: {count} registros")
        
        # Calcular totais
        total_horas_trabalhadas = sum(r.horas_trabalhadas or 0 for r in registros_criados)
        total_horas_extras = sum(r.horas_extras or 0 for r in registros_criados)
        total_atrasos = sum(r.total_atraso_horas or 0 for r in registros_criados)
        
        print(f"\n💼 Totais calculados:")
        print(f"  - Horas trabalhadas: {total_horas_trabalhadas}h")
        print(f"  - Horas extras: {total_horas_extras}h")
        print(f"  - Atrasos: {total_atrasos}h")
        
        print(f"\n🎯 Mês completo populado para {cassio.nome}!")


if __name__ == "__main__":
    popular_mes_completo_cassio()