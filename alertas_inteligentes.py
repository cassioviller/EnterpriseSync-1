#!/usr/bin/env python3
"""
Sistema de Alertas Inteligentes - SIGE v6.5
Monitora métricas críticas e gera notificações automáticas
"""

from datetime import datetime, date, timedelta
from models import *
from kpis_engine import calcular_kpis_funcionario
from app import db
import json

class AlertaInteligente:
    def __init__(self):
        self.alertas = []
        self.limites = {
            'absenteismo_critico': 15.0,  # %
            'produtividade_baixa': 60.0,  # %
            'horas_extras_excessivas': 50.0,  # horas/mês
            'atrasos_recorrentes': 120,  # minutos/mês
            'custo_acima_orcamento': 110.0,  # % do orçamento
            'faltas_consecutivas': 3,  # dias
        }
    
    def verificar_metricas_funcionarios(self, periodo_dias=30):
        """Verifica métricas críticas de funcionários"""
        alertas = []
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=periodo_dias)
        
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        
        for funcionario in funcionarios:
            try:
                kpis = calcular_kpis_funcionario(funcionario.id, data_inicio, data_fim)
                
                # Verificar absenteísmo crítico
                if kpis.get('absenteismo', 0) > self.limites['absenteismo_critico']:
                    alertas.append({
                        'tipo': 'ABSENTEISMO_CRITICO',
                        'prioridade': 'ALTA',
                        'funcionario': funcionario.nome,
                        'valor': f"{kpis['absenteismo']:.1f}%",
                        'limite': f"{self.limites['absenteismo_critico']}%",
                        'descricao': f'{funcionario.nome} tem absenteísmo de {kpis["absenteismo"]:.1f}%, acima do limite de {self.limites["absenteismo_critico"]}%',
                        'acao_recomendada': 'Agendar reunião com RH para avaliação',
                        'data': datetime.now(),
                        'categoria': 'RH'
                    })
                
                # Verificar produtividade baixa
                if kpis.get('produtividade', 100) < self.limites['produtividade_baixa']:
                    alertas.append({
                        'tipo': 'PRODUTIVIDADE_BAIXA',
                        'prioridade': 'MEDIA',
                        'funcionario': funcionario.nome,
                        'valor': f"{kpis['produtividade']:.1f}%",
                        'limite': f"{self.limites['produtividade_baixa']}%",
                        'descricao': f'{funcionario.nome} tem produtividade de {kpis["produtividade"]:.1f}%, abaixo do esperado',
                        'acao_recomendada': 'Verificar carga de trabalho e treinamento',
                        'data': datetime.now(),
                        'categoria': 'PRODUTIVIDADE'
                    })
                
                # Verificar horas extras excessivas
                if kpis.get('horas_extras', 0) > self.limites['horas_extras_excessivas']:
                    alertas.append({
                        'tipo': 'HORAS_EXTRAS_EXCESSIVAS',
                        'prioridade': 'MEDIA',
                        'funcionario': funcionario.nome,
                        'valor': f"{kpis['horas_extras']:.1f}h",
                        'limite': f"{self.limites['horas_extras_excessivas']}h",
                        'descricao': f'{funcionario.nome} acumulou {kpis["horas_extras"]:.1f}h extras no período',
                        'acao_recomendada': 'Avaliar distribuição de carga de trabalho',
                        'data': datetime.now(),
                        'categoria': 'GESTAO'
                    })
                
                # Verificar atrasos recorrentes
                total_atrasos = kpis.get('total_atrasos_minutos', 0)
                if total_atrasos > self.limites['atrasos_recorrentes']:
                    alertas.append({
                        'tipo': 'ATRASOS_RECORRENTES',
                        'prioridade': 'BAIXA',
                        'funcionario': funcionario.nome,
                        'valor': f"{total_atrasos}min",
                        'limite': f"{self.limites['atrasos_recorrentes']}min",
                        'descricao': f'{funcionario.nome} acumulou {total_atrasos}min de atrasos no período',
                        'acao_recomendada': 'Conversar sobre pontualidade',
                        'data': datetime.now(),
                        'categoria': 'DISCIPLINA'
                    })
                    
            except Exception as e:
                print(f"Erro ao calcular KPIs para {funcionario.nome}: {e}")
                continue
        
        return alertas
    
    def verificar_metricas_obras(self):
        """Verifica métricas críticas de obras"""
        alertas = []
        obras = Obra.query.filter_by(status='Em andamento').all()
        
        for obra in obras:
            try:
                # Verificar custos acima do orçamento
                custos_totais = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
                if obra.orcamento_total and custos_totais > (obra.orcamento_total * self.limites['custo_acima_orcamento'] / 100):
                    percentual_gasto = (custos_totais / obra.orcamento_total) * 100
                    alertas.append({
                        'tipo': 'CUSTO_ACIMA_ORCAMENTO',
                        'prioridade': 'ALTA',
                        'obra': obra.nome,
                        'valor': f"R$ {custos_totais:,.2f}",
                        'orcamento': f"R$ {obra.orcamento_total:,.2f}",
                        'percentual': f"{percentual_gasto:.1f}%",
                        'descricao': f'Obra {obra.nome} gastou {percentual_gasto:.1f}% do orçamento',
                        'acao_recomendada': 'Revisar custos e cronograma',
                        'data': datetime.now(),
                        'categoria': 'FINANCEIRO'
                    })
                
                # Verificar obras sem RDO recente (últimos 7 dias)
                ultimo_rdo = RDO.query.filter_by(obra_id=obra.id).order_by(RDO.data.desc()).first()
                if not ultimo_rdo or ultimo_rdo.data < (date.today() - timedelta(days=7)):
                    alertas.append({
                        'tipo': 'OBRA_SEM_RDO',
                        'prioridade': 'MEDIA',
                        'obra': obra.nome,
                        'ultimo_rdo': ultimo_rdo.data.strftime('%d/%m/%Y') if ultimo_rdo else 'Nunca',
                        'descricao': f'Obra {obra.nome} sem RDO há mais de 7 dias',
                        'acao_recomendada': 'Verificar status da obra e criar RDO',
                        'data': datetime.now(),
                        'categoria': 'OPERACIONAL'
                    })
                    
            except Exception as e:
                print(f"Erro ao verificar métricas da obra {obra.nome}: {e}")
                continue
        
        return alertas
    
    def verificar_metricas_veiculos(self):
        """Verifica métricas críticas de veículos"""
        alertas = []
        veiculos = Veiculo.query.filter_by(status='Ativo').all()
        
        for veiculo in veiculos:
            try:
                # Verificar veículos sem uso recente (últimos 30 dias)
                ultimo_uso = UsoVeiculo.query.filter_by(veiculo_id=veiculo.id).order_by(UsoVeiculo.data.desc()).first()
                if not ultimo_uso or ultimo_uso.data < (date.today() - timedelta(days=30)):
                    alertas.append({
                        'tipo': 'VEICULO_SEM_USO',
                        'prioridade': 'BAIXA',
                        'veiculo': f"{veiculo.modelo} - {veiculo.placa}",
                        'ultimo_uso': ultimo_uso.data.strftime('%d/%m/%Y') if ultimo_uso else 'Nunca',
                        'descricao': f'Veículo {veiculo.modelo} sem uso há mais de 30 dias',
                        'acao_recomendada': 'Verificar necessidade do veículo ou realizar manutenção preventiva',
                        'data': datetime.now(),
                        'categoria': 'FROTA'
                    })
                
                # Verificar custos elevados de combustível (últimos 30 dias)
                data_inicio = date.today() - timedelta(days=30)
                custos_combustivel = db.session.query(func.sum(CustoVeiculo.valor)).filter(
                    CustoVeiculo.veiculo_id == veiculo.id,
                    CustoVeiculo.tipo == 'combustivel',
                    CustoVeiculo.data >= data_inicio
                ).scalar() or 0
                
                if custos_combustivel > 2000:  # Limite de R$ 2000/mês
                    alertas.append({
                        'tipo': 'CUSTO_COMBUSTIVEL_ALTO',
                        'prioridade': 'MEDIA',
                        'veiculo': f"{veiculo.modelo} - {veiculo.placa}",
                        'valor': f"R$ {custos_combustivel:,.2f}",
                        'descricao': f'Veículo {veiculo.modelo} gastou R$ {custos_combustivel:,.2f} em combustível nos últimos 30 dias',
                        'acao_recomendada': 'Verificar eficiência do veículo e padrão de uso',
                        'data': datetime.now(),
                        'categoria': 'FROTA'
                    })
                    
            except Exception as e:
                print(f"Erro ao verificar métricas do veículo {veiculo.modelo}: {e}")
                continue
        
        return alertas
    
    def gerar_relatorio_completo(self):
        """Gera relatório completo de todos os alertas"""
        todos_alertas = []
        
        # Coletar todos os alertas
        todos_alertas.extend(self.verificar_metricas_funcionarios())
        todos_alertas.extend(self.verificar_metricas_obras())
        todos_alertas.extend(self.verificar_metricas_veiculos())
        
        # Organizar por prioridade
        alertas_organizados = {
            'ALTA': [a for a in todos_alertas if a['prioridade'] == 'ALTA'],
            'MEDIA': [a for a in todos_alertas if a['prioridade'] == 'MEDIA'],
            'BAIXA': [a for a in todos_alertas if a['prioridade'] == 'BAIXA']
        }
        
        # Estatísticas
        estatisticas = {
            'total_alertas': len(todos_alertas),
            'alertas_criticos': len(alertas_organizados['ALTA']),
            'alertas_importantes': len(alertas_organizados['MEDIA']),
            'alertas_informativos': len(alertas_organizados['BAIXA']),
            'categorias': {}
        }
        
        # Contar por categoria
        for alerta in todos_alertas:
            categoria = alerta['categoria']
            if categoria not in estatisticas['categorias']:
                estatisticas['categorias'][categoria] = 0
            estatisticas['categorias'][categoria] += 1
        
        return {
            'alertas': alertas_organizados,
            'estatisticas': estatisticas,
            'data_geracao': datetime.now(),
            'periodo_analise': '30 dias'
        }
    
    def salvar_alertas_json(self, arquivo='alertas_sistema.json'):
        """Salva alertas em arquivo JSON para histórico"""
        relatorio = self.gerar_relatorio_completo()
        
        try:
            with open(arquivo, 'w', encoding='utf-8') as f:
                json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)
            print(f"Relatório de alertas salvo em {arquivo}")
        except Exception as e:
            print(f"Erro ao salvar relatório: {e}")
        
        return relatorio

def executar_verificacao_completa():
    """Função principal para executar verificação completa"""
    print("🔍 Iniciando verificação de alertas inteligentes...")
    
    alerta_system = AlertaInteligente()
    relatorio = alerta_system.gerar_relatorio_completo()
    
    print(f"\n📊 RESUMO DOS ALERTAS:")
    print(f"Total de alertas: {relatorio['estatisticas']['total_alertas']}")
    print(f"Críticos (Alta prioridade): {relatorio['estatisticas']['alertas_criticos']}")
    print(f"Importantes (Média prioridade): {relatorio['estatisticas']['alertas_importantes']}")
    print(f"Informativos (Baixa prioridade): {relatorio['estatisticas']['alertas_informativos']}")
    
    print(f"\n📈 ALERTAS POR CATEGORIA:")
    for categoria, quantidade in relatorio['estatisticas']['categorias'].items():
        print(f"{categoria}: {quantidade} alertas")
    
    # Mostrar alertas críticos
    if relatorio['alertas']['ALTA']:
        print(f"\n🚨 ALERTAS CRÍTICOS:")
        for alerta in relatorio['alertas']['ALTA']:
            print(f"- {alerta['descricao']}")
            print(f"  Ação: {alerta['acao_recomendada']}")
    
    # Salvar relatório
    alerta_system.salvar_alertas_json()
    
    return relatorio

if __name__ == "__main__":
    # Executar apenas se chamado diretamente
    with app.app_context():
        executar_verificacao_completa()