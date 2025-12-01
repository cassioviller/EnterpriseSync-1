# ================================
# SERVIÇO DE CONTROLE DE PONTO - CELULAR COMPARTILHADO
# Sistema de Ponto Eletrônico SIGE v8.0
# ================================

from datetime import date, datetime, time, timedelta
from app import db
from models import RegistroPonto, Funcionario, Obra, ConfiguracaoHorario, FuncionarioObrasPonto
from multitenant_helper import get_admin_id as get_tenant_admin_id
import logging

logger = logging.getLogger(__name__)


class PontoService:
    """Serviço centralizado para controle de ponto com celular compartilhado"""
    
    @staticmethod
    def obter_status_obra(obra_id, data=None):
        """
        Obtém status de todos os funcionários da obra para uma data específica
        
        Args:
            obra_id: ID da obra
            data: Data do ponto (default: hoje)
            
        Returns:
            Lista de dicionários com status de cada funcionário
        """
        if not data:
            data = date.today()
        
        admin_id = get_tenant_admin_id()
        
        # Buscar funcionários associados à obra via FuncionarioObrasPonto
        # ou todos os funcionários ativos se não houver configuração específica
        funcionarios_obra = FuncionarioObrasPonto.query.filter_by(
            obra_id=obra_id,
            admin_id=admin_id,
            ativo=True
        ).all()
        
        if funcionarios_obra:
            # Usar funcionários configurados para esta obra
            func_ids = [fo.funcionario_id for fo in funcionarios_obra]
            funcionarios = Funcionario.query.filter(
                Funcionario.id.in_(func_ids),
                Funcionario.admin_id == admin_id,
                Funcionario.ativo == True
            ).order_by(Funcionario.nome).all()
        else:
            # Fallback: mostrar todos os funcionários ativos (sem configuração específica)
            funcionarios = Funcionario.query.filter_by(
                admin_id=admin_id,
                ativo=True
            ).order_by(Funcionario.nome).all()
        
        status_funcionarios = []
        
        for funcionario in funcionarios:
            # Buscar registro do dia
            registro = RegistroPonto.query.filter_by(
                funcionario_id=funcionario.id,
                data=data,
                admin_id=admin_id
            ).first()
            
            # Determinar próximo ponto
            proximo_ponto = PontoService._determinar_proximo_ponto(registro)
            
            # Calcular horas trabalhadas até agora
            horas_ate_agora = PontoService._calcular_horas_ate_agora(registro)
            
            status_funcionarios.append({
                'funcionario': funcionario,
                'registro': registro,
                'proximo_ponto': proximo_ponto,
                'horas_ate_agora': horas_ate_agora,
                'status_visual': PontoService._obter_status_visual(registro, proximo_ponto)
            })
        
        return status_funcionarios
    
    @staticmethod
    def bater_ponto_obra(funcionario_id, tipo_ponto, obra_id, latitude=None, longitude=None):
        """
        Registra ponto de funcionário via celular da obra
        
        Args:
            funcionario_id: ID do funcionário
            tipo_ponto: 'entrada', 'saida_almoco', 'volta_almoco' ou 'saida'
            obra_id: ID da obra
            latitude: Latitude GPS (opcional)
            longitude: Longitude GPS (opcional)
            
        Returns:
            Dict com success, message e dados do ponto
        """
        try:
            admin_id = get_tenant_admin_id()
            hoje = date.today()
            agora = datetime.now().time()
            
            # Buscar ou criar registro do dia
            registro = RegistroPonto.query.filter_by(
                funcionario_id=funcionario_id,
                data=hoje,
                admin_id=admin_id
            ).first()
            
            if not registro:
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,
                    data=hoje,
                    admin_id=admin_id,
                    tipo_local='campo',  # Ponto batido em obra
                    tipo_registro='trabalhado'
                )
                db.session.add(registro)
            
            # Validar e registrar o ponto
            resultado_validacao = PontoService._validar_ponto(registro, tipo_ponto, agora)
            if not resultado_validacao['valido']:
                return resultado_validacao
            
            # Registrar o ponto baseado no tipo
            if tipo_ponto == 'entrada':
                registro.hora_entrada = agora
            elif tipo_ponto == 'saida_almoco':
                registro.hora_almoco_saida = agora
            elif tipo_ponto == 'volta_almoco':
                registro.hora_almoco_retorno = agora
            elif tipo_ponto == 'saida':
                registro.hora_saida = agora
            
            # Calcular horas trabalhadas e extras
            PontoService._calcular_horas(registro)
            
            db.session.commit()
            
            # Buscar nome do funcionário para resposta
            funcionario = Funcionario.query.get(funcionario_id)
            
            # Mapear tipo de ponto para mensagem
            tipos_msg = {
                'entrada': 'Entrada',
                'saida_almoco': 'Saída para Almoço',
                'volta_almoco': 'Volta do Almoço',
                'saida': 'Saída'
            }
            
            return {
                'success': True,
                'message': f'{funcionario.nome}: {tipos_msg[tipo_ponto]} registrada às {agora.strftime("%H:%M")}',
                'funcionario_nome': funcionario.nome,
                'horario': agora.strftime("%H:%M"),
                'proximo_ponto': PontoService._determinar_proximo_ponto(registro)
            }
            
        except Exception as e:
            logger.error(f"Erro ao bater ponto: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _determinar_proximo_ponto(registro):
        """Determina qual é o próximo ponto a ser batido"""
        if not registro:
            return 'entrada'
        
        if not registro.hora_entrada:
            return 'entrada'
        elif not registro.hora_almoco_saida:
            return 'saida_almoco'
        elif not registro.hora_almoco_retorno:
            return 'volta_almoco'
        elif not registro.hora_saida:
            return 'saida'
        else:
            return None  # Todos os pontos batidos
    
    @staticmethod
    def _obter_status_visual(registro, proximo_ponto):
        """Retorna status visual para interface"""
        if not registro or not registro.hora_entrada:
            return {'cor': 'secondary', 'icone': 'clock', 'texto': 'Não chegou'}
        elif proximo_ponto is None:
            return {'cor': 'success', 'icone': 'check-circle', 'texto': 'Concluído'}
        elif proximo_ponto == 'saida':
            return {'cor': 'primary', 'icone': 'play-circle', 'texto': 'Trabalhando'}
        else:
            return {'cor': 'warning', 'icone': 'pause-circle', 'texto': 'Em pausa'}
    
    @staticmethod
    def _calcular_horas_ate_agora(registro):
        """Calcula horas trabalhadas até o momento atual"""
        if not registro or not registro.hora_entrada:
            return timedelta()
        
        agora = datetime.now().time()
        entrada_dt = datetime.combine(date.today(), registro.hora_entrada)
        agora_dt = datetime.combine(date.today(), agora)
        
        # Se ainda não saiu para almoço, conta tudo
        if not registro.hora_almoco_saida:
            return agora_dt - entrada_dt
        
        # Se saiu para almoço mas não voltou, conta até a saída do almoço
        if not registro.hora_almoco_retorno:
            almoco_dt = datetime.combine(date.today(), registro.hora_almoco_saida)
            return almoco_dt - entrada_dt
        
        # Se voltou do almoço, conta entrada até almoço + volta até agora
        almoco_saida_dt = datetime.combine(date.today(), registro.hora_almoco_saida)
        almoco_volta_dt = datetime.combine(date.today(), registro.hora_almoco_retorno)
        
        periodo_manha = almoco_saida_dt - entrada_dt
        periodo_tarde = agora_dt - almoco_volta_dt
        
        return periodo_manha + periodo_tarde
    
    @staticmethod
    def _validar_ponto(registro, tipo_ponto, horario):
        """Valida se o ponto pode ser registrado"""
        if tipo_ponto == 'entrada' and registro.hora_entrada:
            return {'valido': False, 'error': 'Entrada já registrada hoje'}
        
        if tipo_ponto == 'saida_almoco':
            if not registro.hora_entrada:
                return {'valido': False, 'error': 'Registre a entrada primeiro'}
            if registro.hora_almoco_saida:
                return {'valido': False, 'error': 'Saída para almoço já registrada'}
        
        if tipo_ponto == 'volta_almoco':
            if not registro.hora_almoco_saida:
                return {'valido': False, 'error': 'Registre a saída para almoço primeiro'}
            if registro.hora_almoco_retorno:
                return {'valido': False, 'error': 'Volta do almoço já registrada'}
        
        if tipo_ponto == 'saida':
            if not registro.hora_entrada:
                return {'valido': False, 'error': 'Registre a entrada primeiro'}
            if registro.hora_saida:
                return {'valido': False, 'error': 'Saída já registrada hoje'}
        
        return {'valido': True}
    
    @staticmethod
    def _calcular_horas(registro):
        """Calcula horas trabalhadas, extras e atrasos"""
        try:
            # Buscar configuração de horário da obra
            config = ConfiguracaoHorario.query.filter_by(
                obra_id=registro.obra_id,
                ativo=True
            ).first()
            
            if not config:
                # Configuração padrão
                entrada_padrao = time(8, 0)
                saida_padrao = time(17, 0)
                tolerancia_atraso = 15
                carga_horaria_diaria = 480  # 8 horas
            else:
                entrada_padrao = config.entrada_padrao
                saida_padrao = config.saida_padrao
                tolerancia_atraso = config.tolerancia_atraso
                carga_horaria_diaria = config.carga_horaria_diaria
            
            # Calcular atraso na entrada
            if registro.hora_entrada and entrada_padrao:
                entrada_datetime = datetime.combine(registro.data, registro.hora_entrada)
                entrada_padrao_datetime = datetime.combine(registro.data, entrada_padrao)
                
                if entrada_datetime > entrada_padrao_datetime:
                    atraso_segundos = (entrada_datetime - entrada_padrao_datetime).total_seconds()
                    # Só considera atraso se passou da tolerância
                    if atraso_segundos > (tolerancia_atraso * 60):
                        registro.minutos_atraso_entrada = int((atraso_segundos - (tolerancia_atraso * 60)) / 60)
                        registro.total_atraso_minutos = registro.minutos_atraso_entrada
                        registro.total_atraso_horas = registro.total_atraso_minutos / 60.0
            
            # Calcular horas trabalhadas (só se tiver entrada e saída)
            if registro.hora_entrada and registro.hora_saida:
                entrada_dt = datetime.combine(registro.data, registro.hora_entrada)
                saida_dt = datetime.combine(registro.data, registro.hora_saida)
                
                # Calcular tempo de almoço
                tempo_almoco_minutos = 60  # Padrão 1 hora
                if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                    almoco_saida = datetime.combine(registro.data, registro.hora_almoco_saida)
                    almoco_volta = datetime.combine(registro.data, registro.hora_almoco_retorno)
                    tempo_almoco_minutos = (almoco_volta - almoco_saida).total_seconds() / 60
                
                horas_totais_minutos = (saida_dt - entrada_dt).total_seconds() / 60
                horas_trabalhadas_minutos = horas_totais_minutos - tempo_almoco_minutos
                registro.horas_trabalhadas = horas_trabalhadas_minutos / 60.0
                
                # Calcular horas extras
                if horas_trabalhadas_minutos > carga_horaria_diaria:
                    extras_minutos = horas_trabalhadas_minutos - carga_horaria_diaria
                    registro.horas_extras = extras_minutos / 60.0
                else:
                    registro.horas_extras = 0.0
                
        except Exception as e:
            logger.error(f"Erro ao calcular horas: {e}")
    
    @staticmethod
    def registrar_falta(funcionario_id, data_falta, motivo, observacoes=None, obra_id=None):
        """Registra falta de funcionário"""
        try:
            admin_id = get_tenant_admin_id()
            
            # Verificar se já existe registro
            registro = RegistroPonto.query.filter_by(
                funcionario_id=funcionario_id,
                data=data_falta,
                admin_id=admin_id
            ).first()
            
            if not registro:
                # Se obra_id não foi fornecido, tentar buscar da configuração do funcionário
                if not obra_id:
                    obra_config = FuncionarioObrasPonto.query.filter_by(
                        funcionario_id=funcionario_id,
                        admin_id=admin_id,
                        ativo=True
                    ).first()
                    if obra_config:
                        obra_id = obra_config.obra_id
                
                registro = RegistroPonto(
                    funcionario_id=funcionario_id,
                    obra_id=obra_id,  # Pode ser None se não houver configuração
                    data=data_falta,
                    admin_id=admin_id,
                    tipo_registro=motivo  # 'falta', 'falta_justificada', etc
                )
                db.session.add(registro)
            else:
                registro.tipo_registro = motivo
            
            if observacoes:
                registro.observacoes = observacoes
            
            db.session.commit()
            
            return {'success': True, 'message': 'Falta registrada com sucesso'}
            
        except Exception as e:
            logger.error(f"Erro ao registrar falta: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
