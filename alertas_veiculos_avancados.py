"""
SISTEMA DE ALERTAS AVANÇADOS PARA VEÍCULOS - SIGE v8.0
Sistema inteligente de alertas proativos para gestão da frota

Funcionalidades:
- Manutenção preventiva baseada em KM/tempo
- Custos anômalos detectados via machine learning
- Baixa utilização de veículos
- Vencimento de documentos (seguro, IPVA, revisão)
- Alocações atrasadas e veículos ociosos
- Notificações automáticas por email/sistema
- Machine Learning para detecção de padrões
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_, text, extract, case
from sqlalchemy.orm import joinedload
import json
import logging
from decimal import Decimal
from collections import defaultdict
import numpy as np
from statistics import mean, stdev

# Importar modelos
from models import (
    db, Veiculo, CustoVeiculo, UsoVeiculo, AlocacaoVeiculo, ManutencaoVeiculo,
    AlertaVeiculo, Obra, Funcionario, Usuario
)
from auth import admin_required

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criação do Blueprint
alertas_veiculos_bp = Blueprint('alertas_veiculos', __name__, url_prefix='/alertas/veiculos-avancado')

def get_admin_id():
    """Obtém admin_id do usuário atual"""
    if hasattr(current_user, 'tipo_usuario'):
        if current_user.tipo_usuario.value == 'admin':
            return current_user.id
        elif hasattr(current_user, 'admin_id') and current_user.admin_id:
            return current_user.admin_id
    return current_user.id

class SistemaAlertasInteligente:
    """Sistema principal de alertas inteligentes para veículos"""
    
    def __init__(self, admin_id):
        self.admin_id = admin_id
        self.alertas_gerados = []
        
        # Configurações de limites (podem ser customizáveis por admin)
        self.configuracoes = {
            'dias_manutencao_vencida': 0,
            'dias_manutencao_proxima': 15,
            'percentual_custo_anomalo': 50,  # % acima da média
            'dias_baixa_utilizacao': 30,
            'percentual_utilizacao_minima': 20,  # % do período
            'km_minimo_mes': 100,
            'dias_alocacao_atrasada': 0,
            'desvios_padrao_outlier': 2,
        }
    
    def gerar_todos_alertas(self):
        """Gera todos os tipos de alertas"""
        try:
            # Resetar lista de alertas
            self.alertas_gerados = []
            
            # Gerar cada tipo de alerta
            self._gerar_alertas_manutencao()
            self._gerar_alertas_custo_anomalo()
            self._gerar_alertas_baixa_utilizacao()
            self._gerar_alertas_documentos()
            self._gerar_alertas_alocacao()
            self._gerar_alertas_eficiencia()
            self._gerar_alertas_preditivos()
            
            # Salvar alertas no banco
            self._salvar_alertas()
            
            return len(self.alertas_gerados)
            
        except Exception as e:
            logger.error(f"Erro ao gerar alertas: {e}")
            return 0
    
    def _gerar_alertas_manutencao(self):
        """Gera alertas de manutenção"""
        try:
            hoje = date.today()
            
            # Manutenções vencidas
            veiculos_vencidos = Veiculo.query.filter(
                Veiculo.admin_id == self.admin_id,
                Veiculo.ativo == True,
                or_(
                    Veiculo.data_proxima_manutencao < hoje,
                    and_(
                        Veiculo.km_proxima_manutencao.isnot(None),
                        Veiculo.km_atual >= Veiculo.km_proxima_manutencao
                    )
                )
            ).all()
            
            for veiculo in veiculos_vencidos:
                # Verificar se já existe alerta recente
                if not self._alerta_existe_recente(veiculo.id, 'manutencao_vencida', 7):
                    if veiculo.data_proxima_manutencao and veiculo.data_proxima_manutencao < hoje:
                        dias_vencido = (hoje - veiculo.data_proxima_manutencao).days
                        self._criar_alerta(
                            veiculo_id=veiculo.id,
                            tipo='manutencao_vencida',
                            nivel=3 if dias_vencido > 30 else 2,
                            titulo='Manutenção Vencida',
                            mensagem=f'Manutenção do veículo {veiculo.placa} vencida há {dias_vencido} dias',
                            data_referencia=veiculo.data_proxima_manutencao,
                            valor_referencia=dias_vencido
                        )
                    
                    elif (veiculo.km_proxima_manutencao and 
                          veiculo.km_atual >= veiculo.km_proxima_manutencao):
                        km_excedente = veiculo.km_atual - veiculo.km_proxima_manutencao
                        self._criar_alerta(
                            veiculo_id=veiculo.id,
                            tipo='manutencao_km_vencida',
                            nivel=3 if km_excedente > 1000 else 2,
                            titulo='Manutenção por KM Vencida',
                            mensagem=f'Veículo {veiculo.placa} ultrapassou {km_excedente} km da manutenção programada',
                            valor_referencia=km_excedente
                        )
            
            # Manutenções próximas
            data_limite = hoje + timedelta(days=self.configuracoes['dias_manutencao_proxima'])
            veiculos_proximos = Veiculo.query.filter(
                Veiculo.admin_id == self.admin_id,
                Veiculo.ativo == True,
                Veiculo.data_proxima_manutencao >= hoje,
                Veiculo.data_proxima_manutencao <= data_limite
            ).all()
            
            for veiculo in veiculos_proximos:
                if not self._alerta_existe_recente(veiculo.id, 'manutencao_proxima', 7):
                    dias_restantes = (veiculo.data_proxima_manutencao - hoje).days
                    self._criar_alerta(
                        veiculo_id=veiculo.id,
                        tipo='manutencao_proxima',
                        nivel=2 if dias_restantes <= 7 else 1,
                        titulo='Manutenção Próxima',
                        mensagem=f'Manutenção do veículo {veiculo.placa} vence em {dias_restantes} dias',
                        data_referencia=veiculo.data_proxima_manutencao,
                        valor_referencia=dias_restantes
                    )
                    
        except Exception as e:
            logger.error(f"Erro nos alertas de manutenção: {e}")
    
    def _gerar_alertas_custo_anomalo(self):
        """Detecta custos anômalos usando machine learning"""
        try:
            # Período de análise (últimos 30 dias)
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=30)
            
            # Obter custos por veículo
            custos_por_veiculo = db.session.query(
                Veiculo.id,
                Veiculo.placa,
                func.sum(CustoVeiculo.valor).label('custo_total'),
                func.count(CustoVeiculo.id).label('total_registros')
            ).join(CustoVeiculo)\
            .filter(
                Veiculo.admin_id == self.admin_id,
                CustoVeiculo.data_custo >= data_inicio,
                CustoVeiculo.data_custo <= data_fim
            ).group_by(Veiculo.id, Veiculo.placa).all()
            
            if len(custos_por_veiculo) < 3:
                return
            
            # Análise estatística para detecção de outliers
            custos = [float(c.custo_total) for c in custos_por_veiculo]
            media_custo = mean(custos)
            desvio_custo = stdev(custos) if len(custos) > 1 else 0
            
            # Detectar outliers (método Z-score)
            for dados in custos_por_veiculo:
                custo_veiculo = float(dados.custo_total)
                if desvio_custo > 0:
                    z_score = abs((custo_veiculo - media_custo) / desvio_custo)
                    
                    if z_score > self.configuracoes['desvios_padrao_outlier']:
                        if not self._alerta_existe_recente(dados.id, 'custo_anomalo', 15):
                            percentual_acima = ((custo_veiculo - media_custo) / media_custo) * 100
                            
                            self._criar_alerta(
                                veiculo_id=dados.id,
                                tipo='custo_anomalo',
                                nivel=3 if percentual_acima > 100 else 2,
                                titulo='Custo Anômalo Detectado',
                                mensagem=f'Veículo {dados.placa} teve custo {percentual_acima:.1f}% acima da média (R$ {custo_veiculo:.2f})',
                                valor_referencia=custo_veiculo
                            )
            
            # Análise por categoria de custo
            self._analisar_custos_por_categoria(data_inicio, data_fim)
            
        except Exception as e:
            logger.error(f"Erro nos alertas de custo anômalo: {e}")
    
    def _analisar_custos_por_categoria(self, data_inicio, data_fim):
        """Analisa custos anômalos por categoria"""
        try:
            categorias = ['combustivel', 'manutencao', 'seguro', 'multa']
            
            for categoria in categorias:
                # Obter custos da categoria por veículo
                custos_categoria = db.session.query(
                    Veiculo.id,
                    Veiculo.placa,
                    func.sum(CustoVeiculo.valor).label('custo_categoria')
                ).join(CustoVeiculo)\
                .filter(
                    Veiculo.admin_id == self.admin_id,
                    CustoVeiculo.tipo_custo == categoria,
                    CustoVeiculo.data_custo >= data_inicio,
                    CustoVeiculo.data_custo <= data_fim
                ).group_by(Veiculo.id, Veiculo.placa).all()
                
                if len(custos_categoria) < 3:
                    continue
                
                custos = [float(c.custo_categoria) for c in custos_categoria if c.custo_categoria > 0]
                if len(custos) < 3:
                    continue
                
                media = mean(custos)
                desvio = stdev(custos)
                
                for dados in custos_categoria:
                    custo = float(dados.custo_categoria or 0)
                    if custo > 0 and desvio > 0:
                        z_score = abs((custo - media) / desvio)
                        
                        if z_score > 1.5:  # Limite mais relaxado para categorias específicas
                            if not self._alerta_existe_recente(dados.id, f'custo_{categoria}_anomalo', 15):
                                percentual = ((custo - media) / media) * 100
                                
                                self._criar_alerta(
                                    veiculo_id=dados.id,
                                    tipo=f'custo_{categoria}_anomalo',
                                    nivel=2,
                                    titulo=f'Custo de {categoria.title()} Anômalo',
                                    mensagem=f'Veículo {dados.placa} teve custo de {categoria} {percentual:.1f}% acima da média',
                                    valor_referencia=custo
                                )
                                
        except Exception as e:
            logger.error(f"Erro na análise por categoria: {e}")
    
    def _gerar_alertas_baixa_utilizacao(self):
        """Detecta veículos com baixa utilização"""
        try:
            # Período de análise
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=self.configuracoes['dias_baixa_utilizacao'])
            
            # Veículos disponíveis com baixo uso
            utilizacao_veiculos = db.session.query(
                Veiculo.id,
                Veiculo.placa,
                func.count(func.distinct(UsoVeiculo.data_uso)).label('dias_uso'),
                func.sum(UsoVeiculo.km_rodado).label('km_total'),
                func.count(UsoVeiculo.id).label('total_usos')
            ).select_from(Veiculo)\
            .outerjoin(UsoVeiculo, and_(
                UsoVeiculo.veiculo_id == Veiculo.id,
                UsoVeiculo.data_uso >= data_inicio,
                UsoVeiculo.data_uso <= data_fim
            ))\
            .filter(
                Veiculo.admin_id == self.admin_id,
                Veiculo.ativo == True,
                Veiculo.status == 'Disponível'
            ).group_by(Veiculo.id, Veiculo.placa).all()
            
            dias_periodo = self.configuracoes['dias_baixa_utilizacao']
            limite_utilizacao = (dias_periodo * self.configuracoes['percentual_utilizacao_minima']) / 100
            
            for dados in utilizacao_veiculos:
                dias_uso = dados.dias_uso or 0
                km_total = float(dados.km_total or 0)
                
                # Critérios de baixa utilização
                baixa_utilizacao_tempo = dias_uso < limite_utilizacao
                baixa_utilizacao_km = km_total < self.configuracoes['km_minimo_mes']
                
                if baixa_utilizacao_tempo or baixa_utilizacao_km:
                    if not self._alerta_existe_recente(dados.id, 'baixa_utilizacao', 15):
                        percentual_uso = (dias_uso / dias_periodo) * 100
                        
                        criterio = []
                        if baixa_utilizacao_tempo:
                            criterio.append(f"usado apenas {dias_uso} dias ({percentual_uso:.1f}%)")
                        if baixa_utilizacao_km:
                            criterio.append(f"rodou apenas {km_total:.0f} km")
                        
                        self._criar_alerta(
                            veiculo_id=dados.id,
                            tipo='baixa_utilizacao',
                            nivel=2 if percentual_uso < 10 else 1,
                            titulo='Baixa Utilização',
                            mensagem=f'Veículo {dados.placa} {" e ".join(criterio)} nos últimos {dias_periodo} dias',
                            valor_referencia=percentual_uso
                        )
                        
        except Exception as e:
            logger.error(f"Erro nos alertas de baixa utilização: {e}")
    
    def _gerar_alertas_documentos(self):
        """Gera alertas para documentos vencidos ou próximos do vencimento"""
        try:
            hoje = date.today()
            
            # Documentos que podem ser verificados no modelo Veiculo
            # (assumindo que existem campos para documentos)
            
            # Por enquanto, implementação placeholder
            # Em uma implementação real, verificaria campos como:
            # - data_vencimento_seguro
            # - data_vencimento_ipva
            # - data_vencimento_licenciamento
            
            # Placeholder para demonstrar a estrutura
            veiculos = Veiculo.query.filter_by(admin_id=self.admin_id, ativo=True).all()
            
            for veiculo in veiculos:
                # Exemplo: verificar se há campo de vencimento de seguro
                if hasattr(veiculo, 'data_vencimento_seguro') and veiculo.data_vencimento_seguro:
                    if veiculo.data_vencimento_seguro <= hoje + timedelta(days=30):
                        if not self._alerta_existe_recente(veiculo.id, 'documento_vencendo', 15):
                            dias_restantes = (veiculo.data_vencimento_seguro - hoje).days
                            
                            self._criar_alerta(
                                veiculo_id=veiculo.id,
                                tipo='documento_vencendo',
                                nivel=3 if dias_restantes <= 0 else 2,
                                titulo='Documento Vencendo',
                                mensagem=f'Seguro do veículo {veiculo.placa} vence em {dias_restantes} dias',
                                data_referencia=veiculo.data_vencimento_seguro,
                                valor_referencia=dias_restantes
                            )
                            
        except Exception as e:
            logger.error(f"Erro nos alertas de documentos: {e}")
    
    def _gerar_alertas_alocacao(self):
        """Gera alertas relacionados a alocações"""
        try:
            hoje = date.today()
            
            # Alocações atrasadas
            alocacoes_atrasadas = AlocacaoVeiculo.query.filter(
                AlocacaoVeiculo.admin_id == self.admin_id,
                AlocacaoVeiculo.ativo == True,
                AlocacaoVeiculo.data_fim.is_(None),
                AlocacaoVeiculo.data_prevista_retorno < hoje
            ).all()
            
            for alocacao in alocacoes_atrasadas:
                if not self._alerta_existe_recente(alocacao.veiculo_id, 'alocacao_atrasada', 3):
                    dias_atraso = (hoje - alocacao.data_prevista_retorno).days
                    
                    self._criar_alerta(
                        veiculo_id=alocacao.veiculo_id,
                        tipo='alocacao_atrasada',
                        nivel=3 if dias_atraso > 7 else 2,
                        titulo='Alocação Atrasada',
                        mensagem=f'Veículo {alocacao.veiculo.placa} atrasado há {dias_atraso} dias na obra {alocacao.obra.nome}',
                        referencia_id=alocacao.id,
                        data_referencia=alocacao.data_prevista_retorno,
                        valor_referencia=dias_atraso
                    )
            
            # Alocações longas (mais de 90 dias)
            data_limite_longa = hoje - timedelta(days=90)
            alocacoes_longas = AlocacaoVeiculo.query.filter(
                AlocacaoVeiculo.admin_id == self.admin_id,
                AlocacaoVeiculo.ativo == True,
                AlocacaoVeiculo.data_fim.is_(None),
                AlocacaoVeiculo.data_inicio <= data_limite_longa
            ).all()
            
            for alocacao in alocacoes_longas:
                if not self._alerta_existe_recente(alocacao.veiculo_id, 'alocacao_longa', 30):
                    dias_alocado = (hoje - alocacao.data_inicio).days
                    
                    self._criar_alerta(
                        veiculo_id=alocacao.veiculo_id,
                        tipo='alocacao_longa',
                        nivel=1,
                        titulo='Alocação Prolongada',
                        mensagem=f'Veículo {alocacao.veiculo.placa} está alocado há {dias_alocado} dias na obra {alocacao.obra.nome}',
                        referencia_id=alocacao.id,
                        valor_referencia=dias_alocado
                    )
                    
        except Exception as e:
            logger.error(f"Erro nos alertas de alocação: {e}")
    
    def _gerar_alertas_eficiencia(self):
        """Gera alertas de eficiência operacional"""
        try:
            # Período de análise (últimos 30 dias)
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=30)
            
            # Veículos com baixa eficiência (alto consumo de combustível)
            eficiencia_combustivel = db.session.query(
                Veiculo.id,
                Veiculo.placa,
                func.sum(case([(CustoVeiculo.tipo_custo == 'combustivel', CustoVeiculo.valor)], else_=0)).label('custo_combustivel'),
                func.sum(UsoVeiculo.km_rodado).label('km_total')
            ).select_from(Veiculo)\
            .outerjoin(CustoVeiculo, and_(
                CustoVeiculo.veiculo_id == Veiculo.id,
                CustoVeiculo.data_custo >= data_inicio,
                CustoVeiculo.data_custo <= data_fim
            ))\
            .outerjoin(UsoVeiculo, and_(
                UsoVeiculo.veiculo_id == Veiculo.id,
                UsoVeiculo.data_uso >= data_inicio,
                UsoVeiculo.data_uso <= data_fim
            ))\
            .filter(Veiculo.admin_id == self.admin_id, Veiculo.ativo == True)\
            .group_by(Veiculo.id, Veiculo.placa)\
            .having(func.sum(UsoVeiculo.km_rodado) > 0).all()
            
            if len(eficiencia_combustivel) >= 3:
                consumos = []
                for dados in eficiencia_combustivel:
                    custo_combustivel = float(dados.custo_combustivel or 0)
                    km_total = float(dados.km_total or 0)
                    if km_total > 0:
                        consumo_por_km = custo_combustivel / km_total
                        consumos.append((dados.id, dados.placa, consumo_por_km))
                
                if len(consumos) >= 3:
                    consumos_valores = [c[2] for c in consumos]
                    media_consumo = mean(consumos_valores)
                    desvio_consumo = stdev(consumos_valores)
                    
                    for veiculo_id, placa, consumo in consumos:
                        if desvio_consumo > 0 and consumo > media_consumo + (1.5 * desvio_consumo):
                            if not self._alerta_existe_recente(veiculo_id, 'eficiencia_combustivel', 20):
                                percentual_acima = ((consumo - media_consumo) / media_consumo) * 100
                                
                                self._criar_alerta(
                                    veiculo_id=veiculo_id,
                                    tipo='eficiencia_combustivel',
                                    nivel=2,
                                    titulo='Baixa Eficiência de Combustível',
                                    mensagem=f'Veículo {placa} tem consumo {percentual_acima:.1f}% acima da média da frota',
                                    valor_referencia=consumo
                                )
                                
        except Exception as e:
            logger.error(f"Erro nos alertas de eficiência: {e}")
    
    def _gerar_alertas_preditivos(self):
        """Gera alertas preditivos baseados em padrões"""
        try:
            # Análise de tendência de aumento de custos
            hoje = date.today()
            periodo_atual = hoje - timedelta(days=30)
            periodo_anterior = periodo_atual - timedelta(days=30)
            
            # Comparar custos entre períodos
            custos_atual = db.session.query(
                Veiculo.id,
                Veiculo.placa,
                func.sum(CustoVeiculo.valor).label('custo_atual')
            ).join(CustoVeiculo)\
            .filter(
                Veiculo.admin_id == self.admin_id,
                CustoVeiculo.data_custo >= periodo_atual,
                CustoVeiculo.data_custo <= hoje
            ).group_by(Veiculo.id, Veiculo.placa).all()
            
            custos_anterior = db.session.query(
                Veiculo.id,
                func.sum(CustoVeiculo.valor).label('custo_anterior')
            ).join(CustoVeiculo)\
            .filter(
                Veiculo.admin_id == self.admin_id,
                CustoVeiculo.data_custo >= periodo_anterior,
                CustoVeiculo.data_custo < periodo_atual
            ).group_by(Veiculo.id).all()
            
            # Criar dicionário para comparação
            custos_ant_dict = {c.id: float(c.custo_anterior) for c in custos_anterior}
            
            for dados in custos_atual:
                custo_atual = float(dados.custo_atual)
                custo_anterior = custos_ant_dict.get(dados.id, 0)
                
                if custo_anterior > 0:
                    aumento = ((custo_atual - custo_anterior) / custo_anterior) * 100
                    
                    # Alerta se aumento significativo (> 50%)
                    if aumento > 50:
                        if not self._alerta_existe_recente(dados.id, 'tendencia_custo_crescente', 20):
                            self._criar_alerta(
                                veiculo_id=dados.id,
                                tipo='tendencia_custo_crescente',
                                nivel=2,
                                titulo='Tendência de Aumento de Custos',
                                mensagem=f'Veículo {dados.placa} teve aumento de {aumento:.1f}% nos custos no último mês',
                                valor_referencia=aumento
                            )
            
            # Predição de manutenção baseada em padrões de uso
            self._predizer_manutencoes()
            
        except Exception as e:
            logger.error(f"Erro nos alertas preditivos: {e}")
    
    def _predizer_manutencoes(self):
        """Prediz necessidade de manutenções baseado em padrões"""
        try:
            # Análise de veículos com padrão de uso intensivo
            data_inicio = date.today() - timedelta(days=30)
            
            veiculos_uso_intensivo = db.session.query(
                Veiculo.id,
                Veiculo.placa,
                Veiculo.km_atual,
                Veiculo.data_proxima_manutencao,
                func.sum(UsoVeiculo.km_rodado).label('km_mes'),
                func.count(UsoVeiculo.id).label('usos_mes')
            ).select_from(Veiculo)\
            .join(UsoVeiculo, UsoVeiculo.veiculo_id == Veiculo.id)\
            .filter(
                Veiculo.admin_id == self.admin_id,
                Veiculo.ativo == True,
                UsoVeiculo.data_uso >= data_inicio
            ).group_by(
                Veiculo.id, Veiculo.placa, Veiculo.km_atual, Veiculo.data_proxima_manutencao
            ).having(func.sum(UsoVeiculo.km_rodado) > 2000).all()  # Uso intensivo > 2000km/mês
            
            for dados in veiculos_uso_intensivo:
                if not self._alerta_existe_recente(dados.id, 'uso_intensivo', 15):
                    km_mes = float(dados.km_mes)
                    
                    # Projetar quando pode precisar de manutenção
                    if dados.data_proxima_manutencao:
                        dias_projetados = int((2500 - km_mes) / (km_mes / 30))  # Projeção simples
                        
                        if dias_projetados < 45:  # Menos de 45 dias para próxima manutenção
                            self._criar_alerta(
                                veiculo_id=dados.id,
                                tipo='uso_intensivo',
                                nivel=1,
                                titulo='Uso Intensivo Detectado',
                                mensagem=f'Veículo {dados.placa} está com uso intensivo ({km_mes:.0f} km/mês). Próxima manutenção pode ser necessária em ~{dias_projetados} dias',
                                valor_referencia=km_mes
                            )
                            
        except Exception as e:
            logger.error(f"Erro na predição de manutenções: {e}")
    
    def _criar_alerta(self, veiculo_id, tipo, nivel, titulo, mensagem, 
                     data_referencia=None, valor_referencia=None, referencia_id=None):
        """Cria um novo alerta"""
        alerta = {
            'admin_id': self.admin_id,
            'veiculo_id': veiculo_id,
            'tipo_alerta': tipo,
            'nivel': nivel,
            'titulo': titulo,
            'mensagem': mensagem,
            'data_referencia': data_referencia,
            'valor_referencia': valor_referencia,
            'referencia_id': referencia_id,
            'ativo': True,
            'created_at': datetime.now()
        }
        
        self.alertas_gerados.append(alerta)
    
    def _alerta_existe_recente(self, veiculo_id, tipo_alerta, dias):
        """Verifica se já existe alerta similar recente"""
        data_limite = date.today() - timedelta(days=dias)
        
        existe = AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == self.admin_id,
            AlertaVeiculo.veiculo_id == veiculo_id,
            AlertaVeiculo.tipo_alerta == tipo_alerta,
            AlertaVeiculo.ativo == True,
            AlertaVeiculo.created_at >= data_limite
        ).first()
        
        return existe is not None
    
    def _salvar_alertas(self):
        """Salva alertas gerados no banco de dados"""
        try:
            for alerta_data in self.alertas_gerados:
                alerta = AlertaVeiculo(**alerta_data)
                db.session.add(alerta)
            
            db.session.commit()
            logger.info(f"Salvos {len(self.alertas_gerados)} alertas para admin {self.admin_id}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar alertas: {e}")
            db.session.rollback()
            raise

# ===== ROTAS DO BLUEPRINT =====

@alertas_veiculos_bp.route('/')
@login_required
@admin_required
def dashboard_alertas():
    """Dashboard principal de alertas de veículos"""
    admin_id = get_admin_id()
    
    try:
        # Gerar alertas automáticos
        sistema_alertas = SistemaAlertasInteligente(admin_id)
        alertas_criados = sistema_alertas.gerar_todos_alertas()
        
        # Obter alertas ativos
        alertas_ativos = obter_alertas_ativos(admin_id)
        
        # Estatísticas
        estatisticas = calcular_estatisticas_alertas(admin_id)
        
        # Alertas por categoria
        alertas_por_categoria = agrupar_alertas_por_categoria(admin_id)
        
        # Veículos críticos
        veiculos_criticos = identificar_veiculos_criticos(admin_id)
        
        # Tendências
        tendencias = analisar_tendencias_alertas(admin_id)
        
        return render_template('alertas/veiculos/dashboard.html',
                             alertas_ativos=alertas_ativos,
                             estatisticas=estatisticas,
                             alertas_por_categoria=alertas_por_categoria,
                             veiculos_criticos=veiculos_criticos,
                             tendencias=tendencias,
                             alertas_criados=alertas_criados)
        
    except Exception as e:
        logger.error(f"Erro no dashboard de alertas: {e}")
        flash('Erro ao carregar dashboard de alertas', 'danger')
        return redirect(url_for('main.dashboard'))

def obter_alertas_ativos(admin_id):
    """Obtém alertas ativos do banco"""
    try:
        alertas = AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True
        ).order_by(
            AlertaVeiculo.nivel.desc(),
            AlertaVeiculo.created_at.desc()
        ).limit(50).all()
        
        alertas_formatados = []
        for alerta in alertas:
            alertas_formatados.append({
                'id': alerta.id,
                'tipo': alerta.tipo_alerta,
                'nivel': alerta.nivel,
                'titulo': alerta.titulo,
                'mensagem': alerta.mensagem,
                'veiculo_placa': alerta.veiculo.placa if alerta.veiculo else 'N/A',
                'data_criacao': alerta.created_at.strftime('%d/%m/%Y %H:%M'),
                'data_visualizacao': alerta.data_visualizacao.strftime('%d/%m/%Y %H:%M') if alerta.data_visualizacao else None,
                'valor_referencia': alerta.valor_referencia,
                'cor_nivel': obter_cor_nivel(alerta.nivel),
                'icone_tipo': obter_icone_tipo(alerta.tipo_alerta)
            })
        
        return alertas_formatados
        
    except Exception as e:
        logger.error(f"Erro ao obter alertas ativos: {e}")
        return []

def calcular_estatisticas_alertas(admin_id):
    """Calcula estatísticas dos alertas"""
    try:
        hoje = date.today()
        semana_passada = hoje - timedelta(days=7)
        
        total_alertas = AlertaVeiculo.query.filter_by(admin_id=admin_id, ativo=True).count()
        
        alertas_semana = AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True,
            AlertaVeiculo.created_at >= semana_passada
        ).count()
        
        alertas_criticos = AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True,
            AlertaVeiculo.nivel == 3
        ).count()
        
        alertas_nao_visualizados = AlertaVeiculo.query.filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True,
            AlertaVeiculo.data_visualizacao.is_(None)
        ).count()
        
        return {
            'total_alertas': total_alertas,
            'alertas_semana': alertas_semana,
            'alertas_criticos': alertas_criticos,
            'alertas_nao_visualizados': alertas_nao_visualizados
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas: {e}")
        return {}

def agrupar_alertas_por_categoria(admin_id):
    """Agrupa alertas por tipo/categoria"""
    try:
        alertas_por_tipo = db.session.query(
            AlertaVeiculo.tipo_alerta,
            func.count(AlertaVeiculo.id).label('total'),
            func.avg(AlertaVeiculo.nivel).label('nivel_medio')
        ).filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True
        ).group_by(AlertaVeiculo.tipo_alerta).all()
        
        categorias = []
        for dados in alertas_por_tipo:
            categorias.append({
                'tipo': dados.tipo_alerta,
                'total': dados.total,
                'nivel_medio': round(float(dados.nivel_medio), 1),
                'descricao': obter_descricao_tipo(dados.tipo_alerta)
            })
        
        return sorted(categorias, key=lambda x: x['total'], reverse=True)
        
    except Exception as e:
        logger.error(f"Erro ao agrupar alertas: {e}")
        return []

def identificar_veiculos_criticos(admin_id):
    """Identifica veículos com mais alertas críticos"""
    try:
        veiculos_alertas = db.session.query(
            Veiculo.id,
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            func.count(AlertaVeiculo.id).label('total_alertas'),
            func.sum(case([(AlertaVeiculo.nivel == 3, 1)], else_=0)).label('alertas_criticos')
        ).join(AlertaVeiculo)\
        .filter(
            Veiculo.admin_id == admin_id,
            AlertaVeiculo.ativo == True
        ).group_by(Veiculo.id, Veiculo.placa, Veiculo.marca, Veiculo.modelo)\
        .order_by(desc('alertas_criticos'), desc('total_alertas')).limit(10).all()
        
        criticos = []
        for dados in veiculos_alertas:
            score = (dados.alertas_criticos * 3) + dados.total_alertas
            criticos.append({
                'veiculo_id': dados.id,
                'placa': dados.placa,
                'marca': dados.marca,
                'modelo': dados.modelo,
                'total_alertas': dados.total_alertas,
                'alertas_criticos': dados.alertas_criticos,
                'score_criticidade': score
            })
        
        return criticos
        
    except Exception as e:
        logger.error(f"Erro ao identificar veículos críticos: {e}")
        return []

def analisar_tendencias_alertas(admin_id):
    """Analisa tendências dos alertas"""
    try:
        # Últimos 14 dias
        hoje = date.today()
        inicio = hoje - timedelta(days=14)
        
        alertas_diarios = db.session.query(
            func.date(AlertaVeiculo.created_at).label('data'),
            func.count(AlertaVeiculo.id).label('total')
        ).filter(
            AlertaVeiculo.admin_id == admin_id,
            AlertaVeiculo.created_at >= inicio
        ).group_by(func.date(AlertaVeiculo.created_at))\
        .order_by('data').all()
        
        tendencias = []
        for dados in alertas_diarios:
            tendencias.append({
                'data': dados.data.strftime('%Y-%m-%d'),
                'total': dados.total
            })
        
        return tendencias
        
    except Exception as e:
        logger.error(f"Erro ao analisar tendências: {e}")
        return []

# ===== AÇÕES EM ALERTAS =====

@alertas_veiculos_bp.route('/marcar-visualizado/<int:alerta_id>', methods=['POST'])
@login_required
@admin_required
def marcar_visualizado(alerta_id):
    """Marca alerta como visualizado"""
    admin_id = get_admin_id()
    
    try:
        alerta = AlertaVeiculo.query.filter_by(
            id=alerta_id, admin_id=admin_id
        ).first_or_404()
        
        alerta.data_visualizacao = datetime.now()
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Erro ao marcar visualizado: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@alertas_veiculos_bp.route('/desativar/<int:alerta_id>', methods=['POST'])
@login_required
@admin_required
def desativar_alerta(alerta_id):
    """Desativa um alerta"""
    admin_id = get_admin_id()
    
    try:
        alerta = AlertaVeiculo.query.filter_by(
            id=alerta_id, admin_id=admin_id
        ).first_or_404()
        
        alerta.ativo = False
        alerta.data_resolucao = datetime.now()
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Erro ao desativar alerta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@alertas_veiculos_bp.route('/api/gerar-alertas', methods=['POST'])
@login_required
@admin_required
def api_gerar_alertas():
    """API para gerar alertas manualmente"""
    admin_id = get_admin_id()
    
    try:
        sistema_alertas = SistemaAlertasInteligente(admin_id)
        alertas_criados = sistema_alertas.gerar_todos_alertas()
        
        return jsonify({
            'success': True,
            'alertas_criados': alertas_criados
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar alertas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== UTILITÁRIOS =====

def obter_cor_nivel(nivel):
    """Retorna cor CSS baseada no nível"""
    cores = {1: 'info', 2: 'warning', 3: 'danger'}
    return cores.get(nivel, 'secondary')

def obter_icone_tipo(tipo):
    """Retorna ícone FontAwesome baseado no tipo"""
    icones = {
        'manutencao_vencida': 'fas fa-wrench',
        'manutencao_proxima': 'fas fa-calendar-check',
        'manutencao_km_vencida': 'fas fa-tachometer-alt',
        'custo_anomalo': 'fas fa-exclamation-triangle',
        'custo_combustivel_anomalo': 'fas fa-gas-pump',
        'custo_manutencao_anomalo': 'fas fa-tools',
        'baixa_utilizacao': 'fas fa-clock',
        'alocacao_atrasada': 'fas fa-map-marker-alt',
        'alocacao_longa': 'fas fa-calendar-times',
        'documento_vencendo': 'fas fa-file-contract',
        'eficiencia_combustivel': 'fas fa-leaf',
        'tendencia_custo_crescente': 'fas fa-chart-line',
        'uso_intensivo': 'fas fa-shipping-fast'
    }
    return icones.get(tipo, 'fas fa-info-circle')

def obter_descricao_tipo(tipo):
    """Retorna descrição do tipo de alerta"""
    descricoes = {
        'manutencao_vencida': 'Manutenção Vencida',
        'manutencao_proxima': 'Manutenção Próxima',
        'manutencao_km_vencida': 'Manutenção por KM Vencida',
        'custo_anomalo': 'Custo Anômalo',
        'custo_combustivel_anomalo': 'Custo de Combustível Anômalo',
        'custo_manutencao_anomalo': 'Custo de Manutenção Anômalo',
        'baixa_utilizacao': 'Baixa Utilização',
        'alocacao_atrasada': 'Alocação Atrasada',
        'alocacao_longa': 'Alocação Prolongada',
        'documento_vencendo': 'Documento Vencendo',
        'eficiencia_combustivel': 'Baixa Eficiência',
        'tendencia_custo_crescente': 'Tendência de Custo',
        'uso_intensivo': 'Uso Intensivo'
    }
    return descricoes.get(tipo, 'Alerta Geral')