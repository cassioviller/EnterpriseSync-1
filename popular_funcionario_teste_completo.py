#!/usr/bin/env python3
"""
Script para criar funcionário de teste na Vale Verde com todos os tipos de lançamentos
e gerar relatório completo dos KPIs
"""

from app import app, db
from kpis_engine import KPIsEngine
from datetime import date, datetime, time, timedelta
import random

# Import models explicitly
from models import (
    Funcionario, RegistroPonto, RegistroAlimentacao, 
    Obra, Usuario
)

def criar_funcionario_teste():
    """Criar funcionário de teste"""
    with app.app_context():
        # Verificar se funcionário já existe
        funcionario_existente = Funcionario.query.filter_by(
            nome='Teste Completo KPIs'
        ).first()
        
        if funcionario_existente:
            print(f"✓ Funcionário teste já existe (ID: {funcionario_existente.id})")
            return funcionario_existente
        
        # Buscar um admin para associar o funcionário
        admin = Usuario.query.filter_by(tipo_usuario='admin').first()
        
        # Gerar código único
        ultimo_funcionario = Funcionario.query.order_by(Funcionario.id.desc()).first()
        proximo_numero = (ultimo_funcionario.id + 1) if ultimo_funcionario else 1
        codigo = f"F{proximo_numero:04d}"
        
        # Criar funcionário
        funcionario = Funcionario(
            codigo=codigo,
            nome='Teste Completo KPIs',
            email='teste.kpis@empresa.com.br',
            telefone='(11) 99999-8888',
            cpf='000.000.000-99',
            salario=4500.00,
            data_admissao=date(2025, 1, 1),
            admin_id=admin.id if admin else None,
            ativo=True
        )
        
        db.session.add(funcionario)
        db.session.commit()
        
        print(f"✓ Funcionário criado: {funcionario.nome} (ID: {funcionario.id})")
        return funcionario

def popular_julho_completo(funcionario_id):
    """Popular julho com todos os tipos de lançamentos"""
    with app.app_context():
        # Limpar lançamentos existentes do funcionário em julho
        RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).delete()
        
        RegistroAlimentacao.query.filter(
            RegistroAlimentacao.funcionario_id == funcionario_id,
            RegistroAlimentacao.data >= date(2025, 7, 1),
            RegistroAlimentacao.data <= date(2025, 7, 31)
        ).delete()
        
        db.session.commit()
        
        # Buscar uma obra qualquer
        obra = Obra.query.first()
        
        print(f"✓ Populando julho para funcionário ID: {funcionario_id}")
        
        # Definir padrão de lançamentos para julho (31 dias)
        lancamentos = []
        
        # Dias 1-5: Trabalho normal (segunda a sexta)
        for dia in range(1, 6):  # 1 a 5 de julho
            data_lancamento = date(2025, 7, dia)
            lancamentos.append({
                'data': data_lancamento,
                'tipo': 'trabalhado',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'descricao': 'Trabalho normal'
            })
        
        # Dia 6 (sábado): Trabalho no sábado com horas extras
        lancamentos.append({
            'data': date(2025, 7, 5),  # Corrigindo: 5 de julho é sábado
            'tipo': 'sabado_horas_extras',
            'entrada': time(8, 0),
            'saida': time(12, 0),
            'horas_trabalhadas': 4.0,
            'horas_extras': 4.0,
            'descricao': 'Trabalho sábado - horas extras'
        })
        
        # Dia 8-12: Trabalho normal com alguns atrasos
        for dia in range(8, 13):  # 8 a 12 de julho
            data_lancamento = date(2025, 7, dia)
            # Alguns dias com atraso
            if dia in [9, 11]:
                entrada = time(8, 30)  # 30 min de atraso
                atraso = 0.5
            else:
                entrada = time(8, 0)
                atraso = 0.0
                
            lancamentos.append({
                'data': data_lancamento,
                'tipo': 'trabalhado',
                'entrada': entrada,
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0 - atraso,
                'total_atraso_horas': atraso,
                'descricao': f'Trabalho normal{" com atraso" if atraso > 0 else ""}'
            })
        
        # Dia 13 (domingo): Trabalho no domingo
        lancamentos.append({
            'data': date(2025, 7, 13),
            'tipo': 'domingo_horas_extras',
            'entrada': time(8, 0),
            'saida': time(12, 0),
            'horas_trabalhadas': 4.0,
            'horas_extras': 4.0,
            'descricao': 'Trabalho domingo - horas extras'
        })
        
        # Dia 15: Falta não justificada
        lancamentos.append({
            'data': date(2025, 7, 15),
            'tipo': 'falta',
            'descricao': 'Falta não justificada'
        })
        
        # Dia 16: Falta justificada
        lancamentos.append({
            'data': date(2025, 7, 16),
            'tipo': 'falta_justificada',
            'descricao': 'Falta justificada - consulta médica'
        })
        
        # Dias 17-19: Trabalho normal com horas extras
        for dia in range(17, 20):
            data_lancamento = date(2025, 7, dia)
            lancamentos.append({
                'data': data_lancamento,
                'tipo': 'trabalhado',
                'entrada': time(8, 0),
                'saida': time(19, 0),  # 2 horas extras
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 10.0,
                'horas_extras': 2.0,
                'descricao': 'Trabalho normal + 2h extras'
            })
        
        # Dia 22: Meio período
        lancamentos.append({
            'data': date(2025, 7, 22),
            'tipo': 'meio_periodo',
            'entrada': time(8, 0),
            'saida': time(12, 0),
            'horas_trabalhadas': 4.0,
            'descricao': 'Meio período'
        })
        
        # Restante do mês: trabalho normal
        for dia in range(23, 32):
            if dia in [26, 27]:  # Pular fim de semana
                continue
            data_lancamento = date(2025, 7, dia)
            lancamentos.append({
                'data': data_lancamento,
                'tipo': 'trabalhado',
                'entrada': time(8, 0),
                'saida': time(17, 0),
                'almoco_inicio': time(12, 0),
                'almoco_fim': time(13, 0),
                'horas_trabalhadas': 8.0,
                'descricao': 'Trabalho normal'
            })
        
        # Criar registros de ponto
        for lanc in lancamentos:
            registro = RegistroPonto(
                funcionario_id=funcionario_id,
                obra_id=obra.id if obra else None,
                data=lanc['data'],
                tipo_registro=lanc['tipo'],
                hora_entrada=lanc.get('entrada'),
                hora_saida=lanc.get('saida'),
                hora_almoco_saida=lanc.get('almoco_inicio'),
                hora_almoco_retorno=lanc.get('almoco_fim'),
                horas_trabalhadas=lanc.get('horas_trabalhadas', 0.0),
                horas_extras=lanc.get('horas_extras', 0.0),
                total_atraso_horas=lanc.get('total_atraso_horas', 0.0),
                observacoes=lanc['descricao']
            )
            db.session.add(registro)
        
        # Adicionar alguns registros de alimentação
        datas_alimentacao = [date(2025, 7, d) for d in [1, 3, 5, 8, 10, 12, 17, 19, 24, 29]]
        for data_alim in datas_alimentacao:
            registro_alim = RegistroAlimentacao(
                funcionario_id=funcionario_id,
                obra_id=obra.id if obra else None,
                data=data_alim,
                valor=15.00,
                tipo='almoco',
                observacoes='Almoço no restaurante da obra'
            )
            db.session.add(registro_alim)
        
        db.session.commit()
        print(f"✓ Criados {len(lancamentos)} registros de ponto e {len(datas_alimentacao)} de alimentação")

def gerar_relatorio_completo(funcionario_id):
    """Gerar relatório completo dos KPIs"""
    with app.app_context():
        funcionario = Funcionario.query.get(funcionario_id)
        engine = KPIsEngine()
        
        print(f"\n{'='*80}")
        print(f"RELATÓRIO COMPLETO DE KPIs - {funcionario.nome}")
        print(f"Período: Julho/2025 | Salário: R$ {funcionario.salario}")
        print(f"{'='*80}")
        
        # Calcular KPIs
        kpis = engine.calcular_kpis_funcionario(
            funcionario_id, 
            date(2025, 7, 1), 
            date(2025, 7, 31)
        )
        
        if not kpis:
            print("❌ Erro no cálculo dos KPIs")
            return
        
        # Mostrar todos os lançamentos
        registros = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31)
        ).order_by(RegistroPonto.data).all()
        
        print(f"\n📋 LANÇAMENTOS DO MÊS ({len(registros)} registros):")
        print("-" * 80)
        for r in registros:
            tipo_desc = {
                'trabalhado': 'TRABALHO NORMAL',
                'sabado_horas_extras': 'SÁBADO + EXTRAS',
                'domingo_horas_extras': 'DOMINGO + EXTRAS',
                'feriado_trabalhado': 'FERIADO TRABALHADO',
                'falta': 'FALTA',
                'falta_justificada': 'FALTA JUSTIFICADA',
                'meio_periodo': 'MEIO PERÍODO'
            }
            
            print(f"{r.data.strftime('%d/%m')} | {tipo_desc.get(r.tipo_registro, r.tipo_registro):20} | "
                  f"H.Trab: {r.horas_trabalhadas or 0:5.1f}h | "
                  f"H.Extra: {r.horas_extras or 0:4.1f}h | "
                  f"Atraso: {r.total_atraso_horas or 0:4.1f}h")
        
        # Mostrar KPIs calculados
        print(f"\n📊 KPIs CALCULADOS (15 indicadores):")
        print("-" * 80)
        
        kpi_descricoes = {
            'horas_trabalhadas': '1. Horas Trabalhadas',
            'custo_mao_obra': '2. Custo Mão de Obra',
            'faltas': '3. Faltas',
            'atrasos_horas': '4. Atrasos (horas)',
            'custo_faltas_justificadas': '5. Custo Faltas Justif.',
            'absenteismo': '6. Absenteísmo (%)',
            'media_horas_diarias': '7. Média Horas/Dia',
            'horas_perdidas': '8. Horas Perdidas',
            'produtividade': '9. Produtividade (%)',
            'custo_alimentacao': '10. Custo Alimentação',
            'horas_extras': '11. Horas Extras',
            'custo_transporte': '12. Custo Transporte',
            'outros_custos': '13. Outros Custos',
            'custo_total': '14. Custo Total',
            'eficiencia': '15. Eficiência (%)'
        }
        
        for chave, descricao in kpi_descricoes.items():
            valor = kpis.get(chave, 0)
            
            if 'custo' in chave and chave != 'custo_faltas_justificadas':
                print(f"{descricao:25} | R$ {valor:>10.2f}")
            elif chave in ['absenteismo', 'produtividade', 'eficiencia']:
                print(f"{descricao:25} | {valor:>10.1f}%")
            elif 'horas' in chave:
                print(f"{descricao:25} | {valor:>10.1f}h")
            else:
                print(f"{descricao:25} | {valor:>10}")
        
        # Informações do período
        print(f"\n📅 RESUMO DO PERÍODO:")
        print("-" * 80)
        periodo = kpis.get('periodo', {})
        print(f"Dias com lançamento: {periodo.get('dias_com_lancamento', 0)}")
        print(f"Data início: {periodo.get('data_inicio', 'N/A')}")
        print(f"Data fim: {periodo.get('data_fim', 'N/A')}")
        
        # Códigos de tipos utilizados
        tipos_utilizados = set(r.tipo_registro for r in registros)
        print(f"\n🏷️  CÓDIGOS DE TIPOS UTILIZADOS:")
        print("-" * 80)
        for tipo in sorted(tipos_utilizados):
            count = len([r for r in registros if r.tipo_registro == tipo])
            print(f"{tipo:20} | {count:2} ocorrências")
        
        print(f"\n{'='*80}")
        print("✅ RELATÓRIO CONCLUÍDO")
        print(f"{'='*80}")

if __name__ == "__main__":
    print("🚀 Iniciando criação de funcionário teste completo...")
    
    # Criar funcionário
    funcionario = criar_funcionario_teste()
    if not funcionario:
        exit(1)
    
    # Popular julho
    popular_julho_completo(funcionario.id)
    
    # Gerar relatório
    gerar_relatorio_completo(funcionario.id)
    
    print("\n✅ Processo concluído com sucesso!")