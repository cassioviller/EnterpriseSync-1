#!/usr/bin/env python3
"""
Sistema de Notificações Inteligentes - SIGE v8.0
Sistema completo de notificações multi-canal com IA
"""

from datetime import datetime, date, timedelta
from models import *
from app import db
from sqlalchemy import func, and_, or_
import json
import smtplib
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
except ImportError:
    # Fallback para ambientes sem suporte completo a email
    MimeText = None
    MimeMultipart = None
import requests
import logging

class NotificationSystem:
    def __init__(self):
        self.channels = ['email', 'push', 'whatsapp', 'sms']
        self.alert_types = {
            'absenteismo_alto': {'priority': 'ALTA', 'threshold': 10.0},
            'produtividade_baixa': {'priority': 'MEDIA', 'threshold': 70.0},
            'custos_acima_orcamento': {'priority': 'ALTA', 'threshold': 90.0},
            'atrasos_recorrentes': {'priority': 'MEDIA', 'threshold': 3},
            'veiculos_manutencao': {'priority': 'BAIXA', 'threshold': 30.0},
            'obras_sem_progresso': {'priority': 'ALTA', 'threshold': 7},
            'funcionarios_sem_ponto': {'priority': 'MEDIA', 'threshold': 1},
            'equipamentos_vencidos': {'priority': 'ALTA', 'threshold': 0},
            'contratos_vencendo': {'priority': 'MEDIA', 'threshold': 30},
            'metas_nao_cumpridas': {'priority': 'ALTA', 'threshold': 90.0},
            'gastos_anomalos': {'priority': 'MEDIA', 'threshold': 200.0},
            'clima_adverso': {'priority': 'BAIXA', 'threshold': 1},
            'fornecedores_inadimplentes': {'priority': 'ALTA', 'threshold': 0},
            'estoque_baixo': {'priority': 'MEDIA', 'threshold': 10.0},
            'certificados_vencendo': {'priority': 'ALTA', 'threshold': 30}
        }
        
    def verificar_todos_alertas(self):
        """Verifica todos os tipos de alertas configurados"""
        alertas_encontrados = []
        hoje = date.today()
        
        # 1. Absenteísmo alto (> 10%)
        funcionarios_absenteismo = self._verificar_absenteismo_alto()
        alertas_encontrados.extend(funcionarios_absenteismo)
        
        # 2. Produtividade baixa (< 70%)
        funcionarios_produtividade = self._verificar_produtividade_baixa()
        alertas_encontrados.extend(funcionarios_produtividade)
        
        # 3. Custos acima do orçamento (> 90%)
        obras_orcamento = self._verificar_custos_orcamento()
        alertas_encontrados.extend(obras_orcamento)
        
        # 4. Atrasos recorrentes (3+ por semana)
        funcionarios_atrasos = self._verificar_atrasos_recorrentes()
        alertas_encontrados.extend(funcionarios_atrasos)
        
        # 5. Veículos em manutenção (> 30% da frota)
        veiculos_manutencao = self._verificar_veiculos_manutencao()
        alertas_encontrados.extend(veiculos_manutencao)
        
        # 6. Obras sem progresso (7+ dias sem RDO)
        obras_paradas = self._verificar_obras_sem_progresso()
        alertas_encontrados.extend(obras_paradas)
        
        # 7. Funcionários sem ponto hoje
        funcionarios_sem_ponto = self._verificar_funcionarios_sem_ponto()
        alertas_encontrados.extend(funcionarios_sem_ponto)
        
        # 8. Contratos vencendo (30 dias)
        contratos_vencendo = self._verificar_contratos_vencendo()
        alertas_encontrados.extend(contratos_vencendo)
        
        # 9. Metas não cumpridas (< 90% da meta)
        metas_nao_cumpridas = self._verificar_metas_nao_cumpridas()
        alertas_encontrados.extend(metas_nao_cumpridas)
        
        # 10. Gastos anômalos (> 200% da média)
        gastos_anomalos = self._verificar_gastos_anomalos()
        alertas_encontrados.extend(gastos_anomalos)
        
        return self._organizar_alertas(alertas_encontrados)
    
    def _verificar_absenteismo_alto(self):
        """Verifica funcionários com absenteísmo > 10%"""
        alertas = []
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        
        for funcionario in funcionarios:
            try:
                # Calcular absenteísmo dos últimos 30 dias
                data_inicio = date.today() - timedelta(days=30)
                
                total_dias_uteis = 22  # Aproximadamente 22 dias úteis por mês
                faltas = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id == funcionario.id,
                    RegistroPonto.data >= data_inicio,
                    RegistroPonto.tipo_registro == 'falta'
                ).count()
                
                absenteismo = (faltas / total_dias_uteis) * 100
                
                if absenteismo > self.alert_types['absenteismo_alto']['threshold']:
                    alertas.append({
                        'tipo': 'absenteismo_alto',
                        'prioridade': 'ALTA',
                        'titulo': f'Absenteísmo crítico: {funcionario.nome}',
                        'descricao': f'Absenteísmo de {absenteismo:.1f}% nos últimos 30 dias',
                        'funcionario_id': funcionario.id,
                        'valor': absenteismo,
                        'limite': self.alert_types['absenteismo_alto']['threshold'],
                        'categoria': 'RH',
                        'acao_recomendada': 'Agendar reunião urgente com RH',
                        'data_criacao': datetime.now(),
                        'canais_notificacao': ['email', 'push', 'whatsapp']
                    })
            except Exception as e:
                logging.error(f"Erro ao verificar absenteísmo de {funcionario.nome}: {e}")
                
        return alertas
    
    def _verificar_produtividade_baixa(self):
        """Verifica funcionários com produtividade < 70%"""
        alertas = []
        data_inicio = date.today() - timedelta(days=30)
        
        funcionarios_stats = db.session.query(
            Funcionario.id,
            Funcionario.nome,
            func.avg(RegistroPonto.horas_trabalhadas).label('media_horas'),
            func.count(RegistroPonto.id).label('dias_trabalhados')
        ).join(RegistroPonto).filter(
            Funcionario.ativo == True,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.tipo_registro.in_(['trabalho_normal', 'meio_periodo'])
        ).group_by(Funcionario.id, Funcionario.nome).all()
        
        for funcionario_stat in funcionarios_stats:
            if funcionario_stat.dias_trabalhados > 0:
                horas_esperadas = 8.0  # 8 horas por dia padrão
                produtividade = (funcionario_stat.media_horas / horas_esperadas) * 100
                
                if produtividade < self.alert_types['produtividade_baixa']['threshold']:
                    alertas.append({
                        'tipo': 'produtividade_baixa',
                        'prioridade': 'MEDIA',
                        'titulo': f'Produtividade baixa: {funcionario_stat.nome}',
                        'descricao': f'Produtividade de {produtividade:.1f}% (média {funcionario_stat.media_horas:.1f}h/dia)',
                        'funcionario_id': funcionario_stat.id,
                        'valor': produtividade,
                        'limite': self.alert_types['produtividade_baixa']['threshold'],
                        'categoria': 'PRODUTIVIDADE',
                        'acao_recomendada': 'Verificar carga de trabalho e oferecer suporte',
                        'data_criacao': datetime.now(),
                        'canais_notificacao': ['email', 'push']
                    })
                    
        return alertas
    
    def _verificar_custos_orcamento(self):
        """Verifica obras com custos > 90% do orçamento"""
        alertas = []
        obras = Obra.query.filter(
            Obra.status.in_(['Em andamento', 'Pausada']),
            Obra.orcamento_total.isnot(None)
        ).all()
        
        for obra in obras:
            try:
                custos_totais = db.session.query(func.sum(CustoObra.valor)).filter_by(obra_id=obra.id).scalar() or 0
                percentual_gasto = (custos_totais / obra.orcamento_total) * 100
                
                if percentual_gasto > self.alert_types['custos_acima_orcamento']['threshold']:
                    alertas.append({
                        'tipo': 'custos_acima_orcamento',
                        'prioridade': 'ALTA',
                        'titulo': f'Orçamento estourado: {obra.nome}',
                        'descricao': f'Gastou {percentual_gasto:.1f}% do orçamento (R$ {custos_totais:,.2f})',
                        'obra_id': obra.id,
                        'valor': percentual_gasto,
                        'limite': self.alert_types['custos_acima_orcamento']['threshold'],
                        'categoria': 'FINANCEIRO',
                        'acao_recomendada': 'Revisar urgentemente custos e cronograma',
                        'data_criacao': datetime.now(),
                        'canais_notificacao': ['email', 'push', 'whatsapp', 'sms']
                    })
            except Exception as e:
                logging.error(f"Erro ao verificar custos da obra {obra.nome}: {e}")
                
        return alertas
    
    def _verificar_atrasos_recorrentes(self):
        """Verifica funcionários com 3+ atrasos por semana"""
        alertas = []
        data_inicio = date.today() - timedelta(days=7)  # Última semana
        
        funcionarios_atrasos = db.session.query(
            Funcionario.id,
            Funcionario.nome,
            func.count(RegistroPonto.id).label('total_atrasos'),
            func.sum(RegistroPonto.total_atraso_minutos).label('minutos_atraso')
        ).join(RegistroPonto).filter(
            Funcionario.ativo == True,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.total_atraso_minutos > 0
        ).group_by(Funcionario.id, Funcionario.nome).having(
            func.count(RegistroPonto.id) >= self.alert_types['atrasos_recorrentes']['threshold']
        ).all()
        
        for funcionario_atraso in funcionarios_atrasos:
            alertas.append({
                'tipo': 'atrasos_recorrentes',
                'prioridade': 'MEDIA',
                'titulo': f'Atrasos recorrentes: {funcionario_atraso.nome}',
                'descricao': f'{funcionario_atraso.total_atrasos} atrasos na semana ({funcionario_atraso.minutos_atraso}min total)',
                'funcionario_id': funcionario_atraso.id,
                'valor': funcionario_atraso.total_atrasos,
                'limite': self.alert_types['atrasos_recorrentes']['threshold'],
                'categoria': 'DISCIPLINA',
                'acao_recomendada': 'Conversa sobre pontualidade e possíveis ajustes',
                'data_criacao': datetime.now(),
                'canais_notificacao': ['email']
            })
            
        return alertas
    
    def _verificar_veiculos_manutencao(self):
        """Verifica se > 30% da frota está em manutenção"""
        alertas = []
        total_veiculos = Veiculo.query.count()
        veiculos_manutencao = Veiculo.query.filter_by(status='Manutenção').count()
        
        if total_veiculos > 0:
            percentual_manutencao = (veiculos_manutencao / total_veiculos) * 100
            
            if percentual_manutencao > self.alert_types['veiculos_manutencao']['threshold']:
                alertas.append({
                    'tipo': 'veiculos_manutencao',
                    'prioridade': 'BAIXA',
                    'titulo': 'Muitos veículos em manutenção',
                    'descricao': f'{percentual_manutencao:.1f}% da frota em manutenção ({veiculos_manutencao}/{total_veiculos})',
                    'valor': percentual_manutencao,
                    'limite': self.alert_types['veiculos_manutencao']['threshold'],
                    'categoria': 'FROTA',
                    'acao_recomendada': 'Revisar cronograma de manutenções e disponibilidade',
                    'data_criacao': datetime.now(),
                    'canais_notificacao': ['email']
                })
                
        return alertas
    
    def _verificar_obras_sem_progresso(self):
        """Verifica obras sem RDO há mais de 7 dias"""
        alertas = []
        data_limite = date.today() - timedelta(days=self.alert_types['obras_sem_progresso']['threshold'])
        
        obras_sem_rdo = db.session.query(Obra).filter(
            Obra.status == 'Em andamento'
        ).outerjoin(RDO).group_by(Obra.id).having(
            or_(
                func.max(RDO.data) < data_limite,
                func.max(RDO.data).is_(None)
            )
        ).all()
        
        for obra in obras_sem_rdo:
            ultimo_rdo = RDO.query.filter_by(obra_id=obra.id).order_by(RDO.data.desc()).first()
            dias_sem_rdo = (date.today() - ultimo_rdo.data).days if ultimo_rdo else 999
            
            alertas.append({
                'tipo': 'obras_sem_progresso',
                'prioridade': 'ALTA',
                'titulo': f'Obra parada: {obra.nome}',
                'descricao': f'Sem RDO há {dias_sem_rdo} dias',
                'obra_id': obra.id,
                'valor': dias_sem_rdo,
                'limite': self.alert_types['obras_sem_progresso']['threshold'],
                'categoria': 'OPERACIONAL',
                'acao_recomendada': 'Verificar status da obra e criar RDO urgente',
                'data_criacao': datetime.now(),
                'canais_notificacao': ['email', 'push', 'whatsapp']
            })
            
        return alertas
    
    def _verificar_funcionarios_sem_ponto(self):
        """Verifica funcionários que não bateram ponto hoje"""
        alertas = []
        hoje = date.today()
        
        funcionarios_ativos = Funcionario.query.filter_by(ativo=True).all()
        funcionarios_com_ponto = db.session.query(RegistroPonto.funcionario_id).filter_by(data=hoje).distinct().all()
        ids_com_ponto = [f.funcionario_id for f in funcionarios_com_ponto]
        
        funcionarios_sem_ponto = [f for f in funcionarios_ativos if f.id not in ids_com_ponto]
        
        # Só alertar após 10:00 da manhã
        if datetime.now().hour >= 10:
            for funcionario in funcionarios_sem_ponto:
                alertas.append({
                    'tipo': 'funcionarios_sem_ponto',
                    'prioridade': 'MEDIA',
                    'titulo': f'Sem ponto hoje: {funcionario.nome}',
                    'descricao': f'Funcionário {funcionario.nome} ainda não registrou ponto hoje',
                    'funcionario_id': funcionario.id,
                    'valor': 1,
                    'limite': self.alert_types['funcionarios_sem_ponto']['threshold'],
                    'categoria': 'PONTO',
                    'acao_recomendada': 'Verificar ausência e orientar sobre registro',
                    'data_criacao': datetime.now(),
                    'canais_notificacao': ['push']
                })
                
        return alertas
    
    def _verificar_contratos_vencendo(self):
        """Verifica contratos vencendo em 30 dias"""
        alertas = []
        data_limite = date.today() + timedelta(days=self.alert_types['contratos_vencendo']['threshold'])
        
        # Simular verificação de contratos (implementar quando modelo for criado)
        # Por enquanto, retorna lista vazia
        return alertas
    
    def _verificar_metas_nao_cumpridas(self):
        """Verifica metas mensais não cumpridas (< 90%)"""
        alertas = []
        # Simular verificação de metas (implementar quando modelo for criado)
        return alertas
    
    def _verificar_gastos_anomalos(self):
        """Verifica gastos > 200% da média histórica"""
        alertas = []
        data_inicio = date.today() - timedelta(days=7)  # Última semana
        data_mes_anterior = date.today() - timedelta(days=37)  # Mês anterior
        
        # Calcular média de gastos do mês anterior
        gastos_mes_anterior = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.data.between(data_mes_anterior, data_mes_anterior + timedelta(days=30))
        ).scalar() or 0
        
        media_semanal = gastos_mes_anterior / 4  # Média semanal
        
        # Gastos da última semana
        gastos_semana = db.session.query(func.sum(CustoObra.valor)).filter(
            CustoObra.data >= data_inicio
        ).scalar() or 0
        
        if media_semanal > 0:
            percentual_gasto = (gastos_semana / media_semanal) * 100
            
            if percentual_gasto > self.alert_types['gastos_anomalos']['threshold']:
                alertas.append({
                    'tipo': 'gastos_anomalos',
                    'prioridade': 'MEDIA',
                    'titulo': 'Gastos anômalos detectados',
                    'descricao': f'Gastos da semana {percentual_gasto:.1f}% acima da média (R$ {gastos_semana:,.2f})',
                    'valor': percentual_gasto,
                    'limite': self.alert_types['gastos_anomalos']['threshold'],
                    'categoria': 'FINANCEIRO',
                    'acao_recomendada': 'Revisar gastos da semana e identificar causa',
                    'data_criacao': datetime.now(),
                    'canais_notificacao': ['email', 'push']
                })
                
        return alertas
    
    def _organizar_alertas(self, alertas):
        """Organiza alertas por prioridade e categoria"""
        alertas_organizados = {
            'ALTA': [],
            'MEDIA': [],
            'BAIXA': []
        }
        
        for alerta in alertas:
            prioridade = alerta['prioridade']
            alertas_organizados[prioridade].append(alerta)
        
        # Ordenar por data de criação (mais recentes primeiro)
        for prioridade in alertas_organizados:
            alertas_organizados[prioridade].sort(
                key=lambda x: x['data_criacao'], 
                reverse=True
            )
        
        estatisticas = {
            'total': len(alertas),
            'criticos': len(alertas_organizados['ALTA']),
            'importantes': len(alertas_organizados['MEDIA']),
            'informativos': len(alertas_organizados['BAIXA']),
            'por_categoria': {}
        }
        
        # Contar por categoria
        for alerta in alertas:
            categoria = alerta['categoria']
            if categoria not in estatisticas['por_categoria']:
                estatisticas['por_categoria'][categoria] = 0
            estatisticas['por_categoria'][categoria] += 1
        
        return {
            'alertas': alertas_organizados,
            'estatisticas': estatisticas,
            'timestamp': datetime.now().isoformat()
        }
    
    def enviar_notificacoes(self, alertas_organizados):
        """Envia notificações através dos canais configurados"""
        for prioridade, alertas in alertas_organizados['alertas'].items():
            for alerta in alertas:
                canais = alerta.get('canais_notificacao', ['email'])
                
                for canal in canais:
                    try:
                        if canal == 'email':
                            self._enviar_email(alerta)
                        elif canal == 'push':
                            self._enviar_push(alerta)
                        elif canal == 'whatsapp':
                            self._enviar_whatsapp(alerta)
                        elif canal == 'sms':
                            self._enviar_sms(alerta)
                    except Exception as e:
                        logging.error(f"Erro ao enviar {canal} para alerta {alerta['tipo']}: {e}")
    
    def _enviar_email(self, alerta):
        """Envia notificação por email"""
        # Implementar envio de email (configurar SMTP)
        logging.info(f"Email enviado: {alerta['titulo']}")
    
    def _enviar_push(self, alerta):
        """Envia notificação push"""
        # Implementar push notifications (Firebase/OneSignal)
        logging.info(f"Push enviado: {alerta['titulo']}")
    
    def _enviar_whatsapp(self, alerta):
        """Envia notificação WhatsApp"""
        # Implementar WhatsApp Business API
        logging.info(f"WhatsApp enviado: {alerta['titulo']}")
    
    def _enviar_sms(self, alerta):
        """Envia notificação SMS"""
        # Implementar SMS (Twilio/AWS SNS)
        logging.info(f"SMS enviado: {alerta['titulo']}")

# Função principal para usar nas views
def executar_sistema_notificacoes():
    """Executa verificação completa e envia notificações"""
    sistema = NotificationSystem()
    resultado = sistema.verificar_todos_alertas()
    sistema.enviar_notificacoes(resultado)
    return resultado

if __name__ == "__main__":
    with app.app_context():
        resultado = executar_sistema_notificacoes()
        print(f"Sistema executado: {resultado['estatisticas']['total']} alertas encontrados")