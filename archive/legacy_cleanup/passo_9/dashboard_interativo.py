#!/usr/bin/env python3
"""
Dashboard Interativo Avançado - SIGE v6.5
Implementa funcionalidades avançadas de dashboard com drill-down e filtros
"""

from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_
import json
from models import *
from app import db

class DashboardAvancado:
    def __init__(self):
        self.cache_dados = {}
        self.periodo_padrao = 30  # dias
    
    def obter_kpis_executivos(self, data_inicio=None, data_fim=None):
        """Calcula KPIs executivos para dashboard"""
        if not data_inicio:
            data_inicio = date.today() - timedelta(days=self.periodo_padrao)
        if not data_fim:
            data_fim = date.today()
        
        # KPIs básicos
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).count()
        obras_ativas = Obra.query.filter_by(status='Em andamento').count()
        veiculos_ativos = Veiculo.query.filter_by(status='Ativo').count()
        
        # KPIs financeiros do período
        custos_periodo = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.data.between(data_inicio, data_fim)
        ).scalar() or 0
        
        alimentacao_periodo = db.session.query(func.sum(RegistroAlimentacao.valor)).filter(
            RegistroAlimentacao.data.between(data_inicio, data_fim)
        ).scalar() or 0
        
        # Produtividade média do período
        registros_ponto = RegistroPonto.query.filter(
            RegistroPonto.data.between(data_inicio, data_fim)
        ).all()
        
        horas_trabalhadas_total = sum([r.horas_trabalhadas or 0 for r in registros_ponto])
        horas_extras_total = sum([r.horas_extras or 0 for r in registros_ponto])
        
        # Alertas críticos
        from alertas_inteligentes import AlertaInteligente
        alerta_system = AlertaInteligente()
        relatorio_alertas = alerta_system.gerar_relatorio_completo()
        alertas_criticos = relatorio_alertas['estatisticas']['alertas_criticos']
        
        return {
            'basicos': {
                'funcionarios_ativos': funcionarios_ativos,
                'obras_ativas': obras_ativas,
                'veiculos_ativos': veiculos_ativos,
                'alertas_criticos': alertas_criticos
            },
            'financeiros': {
                'custos_periodo': custos_periodo,
                'alimentacao_periodo': alimentacao_periodo,
                'custo_medio_funcionario': custos_periodo / funcionarios_ativos if funcionarios_ativos > 0 else 0
            },
            'produtividade': {
                'horas_trabalhadas_total': horas_trabalhadas_total,
                'horas_extras_total': horas_extras_total,
                'media_horas_funcionario': horas_trabalhadas_total / funcionarios_ativos if funcionarios_ativos > 0 else 0
            },
            'periodo': {
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'dias': (data_fim - data_inicio).days
            }
        }
    
    def obter_dados_grafico_custos_timeline(self, data_inicio=None, data_fim=None):
        """Dados para gráfico de evolução de custos por dia"""
        if not data_inicio:
            data_inicio = date.today() - timedelta(days=30)
        if not data_fim:
            data_fim = date.today()
        
        # Consulta agrupada por data
        custos_por_dia = db.session.query(
            CustoObra.data,
            func.sum(CustoObra.valor).label('total')
        ).filter(
            CustoObra.data.between(data_inicio, data_fim)
        ).group_by(CustoObra.data).order_by(CustoObra.data).all()
        
        # Preparar dados para Chart.js
        labels = []
        dados = []
        total_acumulado = 0
        
        for custo in custos_por_dia:
            labels.append(custo.data.strftime('%d/%m'))
            total_acumulado += float(custo.total)
            dados.append(total_acumulado)
        
        return {
            'labels': labels,
            'datasets': [{
                'label': 'Custos Acumulados',
                'data': dados,
                'borderColor': '#007bff',
                'backgroundColor': 'rgba(0, 123, 255, 0.1)',
                'fill': True,
                'tension': 0.4
            }]
        }
    
    def obter_dados_grafico_produtividade_departamentos(self):
        """Dados para gráfico de produtividade por departamento"""
        # Buscar departamentos com funcionários ativos
        departamentos = db.session.query(
            Departamento.nome,
            func.count(Funcionario.id).label('funcionarios'),
            func.avg(RegistroPonto.horas_trabalhadas).label('media_horas')
        ).join(
            Funcionario, Funcionario.departamento_id == Departamento.id
        ).join(
            RegistroPonto, RegistroPonto.funcionario_id == Funcionario.id
        ).filter(
            Funcionario.ativo == True,
            RegistroPonto.data >= (date.today() - timedelta(days=30))
        ).group_by(Departamento.id, Departamento.nome).all()
        
        labels = [d.nome for d in departamentos]
        dados_funcionarios = [d.funcionarios for d in departamentos]
        dados_produtividade = [float(d.media_horas or 0) for d in departamentos]
        
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Funcionários',
                    'data': dados_funcionarios,
                    'backgroundColor': '#28a745',
                    'yAxisID': 'y'
                },
                {
                    'label': 'Média Horas/Dia',
                    'data': dados_produtividade,
                    'backgroundColor': '#ffc107',
                    'type': 'line',
                    'yAxisID': 'y1'
                }
            ]
        }
    
    def obter_dados_grafico_obras_status(self):
        """Dados para gráfico de pizza - obras por status"""
        obras_por_status = db.session.query(
            Obra.status,
            func.count(Obra.id).label('quantidade')
        ).group_by(Obra.status).all()
        
        cores = {
            'Em andamento': '#28a745',
            'Concluída': '#007bff',
            'Pausada': '#ffc107',
            'Cancelada': '#dc3545'
        }
        
        labels = [o.status for o in obras_por_status]
        dados = [o.quantidade for o in obras_por_status]
        backgrounds = [cores.get(o.status, '#6c757d') for o in obras_por_status]
        
        return {
            'labels': labels,
            'datasets': [{
                'data': dados,
                'backgroundColor': backgrounds,
                'borderWidth': 2,
                'borderColor': '#ffffff'
            }]
        }
    
    def obter_top_funcionarios_produtivos(self, limite=10):
        """Top funcionários mais produtivos do mês"""
        data_inicio = date.today().replace(day=1)  # Primeiro dia do mês
        
        funcionarios_stats = db.session.query(
            Funcionario.nome,
            Funcionario.codigo,
            func.sum(RegistroPonto.horas_trabalhadas).label('total_horas'),
            func.sum(RegistroPonto.horas_extras).label('total_extras'),
            func.count(RegistroPonto.id).label('dias_trabalhados')
        ).join(
            RegistroPonto, RegistroPonto.funcionario_id == Funcionario.id
        ).filter(
            Funcionario.ativo == True,
            RegistroPonto.data >= data_inicio
        ).group_by(
            Funcionario.id, Funcionario.nome, Funcionario.codigo
        ).order_by(
            desc('total_horas')
        ).limit(limite).all()
        
        return [{
            'nome': f.nome,
            'codigo': f.codigo,
            'horas_trabalhadas': float(f.total_horas or 0),
            'horas_extras': float(f.total_extras or 0),
            'dias_trabalhados': f.dias_trabalhados,
            'produtividade': (float(f.total_horas or 0) / (f.dias_trabalhados * 8)) * 100 if f.dias_trabalhados > 0 else 0
        } for f in funcionarios_stats]
    
    def obter_obras_criticas(self, limite=5):
        """Obras que precisam de atenção"""
        data_limite = date.today() - timedelta(days=7)
        
        # Obras sem RDO recente
        obras_sem_rdo = db.session.query(Obra).filter(
            Obra.status == 'Em andamento'
        ).outerjoin(RDO).group_by(Obra.id).having(
            or_(
                func.max(RDO.data) < data_limite,
                func.max(RDO.data).is_(None)
            )
        ).limit(limite).all()
        
        obras_info = []
        for obra in obras_sem_rdo:
            # Calcular custos atuais
            custos_totais = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
            
            # Último RDO
            ultimo_rdo = RDO.query.filter_by(obra_id=obra.id).order_by(RDO.data.desc()).first()
            
            obras_info.append({
                'nome': obra.nome,
                'status': obra.status,
                'orcamento': float(obra.orcamento_total or 0),
                'custos_atuais': float(custos_totais),
                'percentual_gasto': (custos_totais / obra.orcamento_total * 100) if obra.orcamento_total else 0,
                'ultimo_rdo': ultimo_rdo.data.strftime('%d/%m/%Y') if ultimo_rdo else 'Nunca',
                'dias_sem_rdo': (date.today() - ultimo_rdo.data).days if ultimo_rdo else 999,
                'alerta': 'SEM_RDO' if not ultimo_rdo or ultimo_rdo.data < data_limite else 'OK'
            })
        
        return obras_info
    
    def obter_metricas_comparativas(self, periodo_atual=30, periodo_anterior=30):
        """Métricas comparativas com período anterior"""
        hoje = date.today()
        
        # Período atual
        inicio_atual = hoje - timedelta(days=periodo_atual)
        fim_atual = hoje
        
        # Período anterior
        inicio_anterior = inicio_atual - timedelta(days=periodo_anterior)
        fim_anterior = inicio_atual
        
        def calcular_metricas_periodo(data_inicio, data_fim):
            custos = db.session.query(func.sum(CustoObra.valor)).filter(
                CustoObra.data.between(data_inicio, data_fim)
            ).scalar() or 0
            
            horas = db.session.query(func.sum(RegistroPonto.horas_trabalhadas)).filter(
                RegistroPonto.data.between(data_inicio, data_fim)
            ).scalar() or 0
            
            funcionarios_trabalharam = db.session.query(func.count(func.distinct(RegistroPonto.funcionario_id))).filter(
                RegistroPonto.data.between(data_inicio, data_fim)
            ).scalar() or 0
            
            return {
                'custos': float(custos),
                'horas': float(horas),
                'funcionarios': funcionarios_trabalharam
            }
        
        atual = calcular_metricas_periodo(inicio_atual, fim_atual)
        anterior = calcular_metricas_periodo(inicio_anterior, fim_anterior)
        
        def calcular_variacao(atual_val, anterior_val):
            if anterior_val == 0:
                return 0
            return ((atual_val - anterior_val) / anterior_val) * 100
        
        return {
            'atual': atual,
            'anterior': anterior,
            'variacoes': {
                'custos': calcular_variacao(atual['custos'], anterior['custos']),
                'horas': calcular_variacao(atual['horas'], anterior['horas']),
                'funcionarios': calcular_variacao(atual['funcionarios'], anterior['funcionarios'])
            }
        }
    
    def gerar_dashboard_completo(self, data_inicio=None, data_fim=None):
        """Gera dados completos para dashboard interativo"""
        return {
            'kpis_executivos': self.obter_kpis_executivos(data_inicio, data_fim),
            'grafico_custos': self.obter_dados_grafico_custos_timeline(data_inicio, data_fim),
            'grafico_departamentos': self.obter_dados_grafico_produtividade_departamentos(),
            'grafico_obras': self.obter_dados_grafico_obras_status(),
            'top_funcionarios': self.obter_top_funcionarios_produtivos(),
            'obras_criticas': self.obter_obras_criticas(),
            'metricas_comparativas': self.obter_metricas_comparativas(),
            'timestamp': datetime.now().isoformat()
        }

# Função utilitária para uso nas views
def obter_dados_dashboard_json(data_inicio=None, data_fim=None):
    """Retorna dados do dashboard em formato JSON para AJAX"""
    dashboard = DashboardAvancado()
    dados = dashboard.gerar_dashboard_completo(data_inicio, data_fim)
    return json.dumps(dados, default=str, ensure_ascii=False)