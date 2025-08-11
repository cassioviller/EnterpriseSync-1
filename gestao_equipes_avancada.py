#!/usr/bin/env python3
"""
MÓDULO 3 - GESTÃO DE EQUIPES AVANÇADA
Implementação baseada na reunião técnica especializada
Funcionalidades refinadas conforme especificações técnicas
"""

from app import db
from models import AlocacaoEquipe, RDO, Funcionario, Obra, Usuario
from flask_login import current_user
from datetime import date, datetime, timedelta
from collections import defaultdict
import secrets
import logging

# ================================
# SISTEMA DE DETECÇÃO DE CONFLITOS
# ================================

def verificar_conflitos_alocacao(funcionario_id, data_alocacao, admin_id, alocacao_id=None):
    """
    Verifica conflitos de alocação conforme especificação da reunião técnica.
    Evita dupla alocação do mesmo funcionário na mesma data.
    """
    try:
        query = AlocacaoEquipe.query.filter(
            AlocacaoEquipe.funcionario_id == funcionario_id,
            AlocacaoEquipe.data_alocacao == data_alocacao,
            AlocacaoEquipe.admin_id == admin_id,
            AlocacaoEquipe.status != 'Cancelado'
        )
        
        # Se estamos editando uma alocação, excluir ela da verificação
        if alocacao_id:
            query = query.filter(AlocacaoEquipe.id != alocacao_id)
        
        conflito = query.first()
        
        if conflito:
            return {
                'tem_conflito': True,
                'conflito_detalhes': {
                    'obra_nome': conflito.obra.nome,
                    'tipo_local': conflito.tipo_local,
                    'status': conflito.status,
                    'data_criacao': conflito.created_at.strftime('%d/%m/%Y %H:%M')
                }
            }
        
        return {'tem_conflito': False}
        
    except Exception as e:
        logging.error(f"Erro ao verificar conflitos: {str(e)}")
        return {'tem_conflito': False, 'erro': str(e)}

# ================================
# GERAÇÃO AUTOMÁTICA DE RDO
# ================================

def gerar_numero_rdo_automatico(obra_id, data_relatorio):
    """
    Gera número de RDO automaticamente conforme padrão da reunião técnica:
    Formato: RDO-OBRA001-20251122-001
    """
    try:
        obra = Obra.query.get(obra_id)
        if not obra:
            return None
        
        data_str = data_relatorio.strftime('%Y%m%d')
        codigo_obra = obra.codigo or f'OBR{obra.id:03d}'
        
        # Buscar último RDO do dia para esta obra
        ultimo_rdo = RDO.query.filter(
            RDO.obra_id == obra_id,
            RDO.numero_rdo.like(f'RDO-{codigo_obra}-{data_str}%')
        ).order_by(RDO.numero_rdo.desc()).first()
        
        if ultimo_rdo:
            try:
                ultimo_numero = int(ultimo_rdo.numero_rdo.split('-')[-1])
                novo_numero = ultimo_numero + 1
            except:
                novo_numero = 1
        else:
            novo_numero = 1
        
        return f"RDO-{codigo_obra}-{data_str}-{novo_numero:03d}"
        
    except Exception as e:
        logging.error(f"Erro ao gerar número RDO: {str(e)}")
        return None

def criar_rdo_automatico_avancado(alocacao_id):
    """
    Cria RDO automaticamente para alocações de campo conforme reunião técnica.
    Implementa lógica avançada de vinculação e numeração automática.
    """
    try:
        alocacao = AlocacaoEquipe.query.get(alocacao_id)
        if not alocacao:
            return False, "Alocação não encontrada"
        
        # Só criar RDO para campo
        if alocacao.tipo_local != 'campo':
            return False, "RDO só é criado automaticamente para alocações de campo"
        
        # Verificar se já existe RDO para esta obra/data
        rdo_existente = RDO.query.filter_by(
            obra_id=alocacao.obra_id,
            data_relatorio=alocacao.data_alocacao,
            admin_id=alocacao.admin_id
        ).first()
        
        if rdo_existente:
            # Vincular alocação ao RDO existente
            alocacao.rdo_gerado_id = rdo_existente.id
            alocacao.rdo_gerado = True
            alocacao.validacao_conflito = True
            db.session.commit()
            
            return True, rdo_existente
        
        # Criar novo RDO
        numero_rdo = gerar_numero_rdo_automatico(alocacao.obra_id, alocacao.data_alocacao)
        if not numero_rdo:
            return False, "Erro ao gerar número do RDO"
        
        novo_rdo = RDO()
        novo_rdo.numero_rdo = numero_rdo
        novo_rdo.obra_id = alocacao.obra_id
        novo_rdo.data_relatorio = alocacao.data_alocacao
        novo_rdo.criado_por_id = current_user.id
        novo_rdo.status = 'Rascunho'
        novo_rdo.tempo_manha = 'Bom'
        novo_rdo.observacoes = f'RDO gerado automaticamente pela alocação de equipe #{alocacao.id}'
        novo_rdo.admin_id = alocacao.admin_id
        
        db.session.add(novo_rdo)
        db.session.flush()  # Para obter o ID
        
        # Vincular alocação ao RDO criado
        alocacao.rdo_gerado_id = novo_rdo.id
        alocacao.rdo_gerado = True
        alocacao.validacao_conflito = True
        
        db.session.commit()
        
        return True, novo_rdo
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar RDO automático: {str(e)}")
        return False, f"Erro interno: {str(e)}"

# ================================
# SISTEMA DE ALOCAÇÃO AVANÇADA
# ================================

def criar_alocacao_equipe_avancada(funcionario_id, obra_id, data_alocacao, tipo_local='campo', 
                                 turno='matutino', prioridade='Normal', observacoes=None):
    """
    Cria alocação com validações avançadas conforme reunião técnica.
    Inclui verificação de conflitos, criação automática de RDO e logs de auditoria.
    """
    try:
        # Validar se funcionário está ativo
        funcionario = Funcionario.query.filter_by(
            id=funcionario_id,
            admin_id=current_user.id,
            ativo=True
        ).first()
        
        if not funcionario:
            return False, "Funcionário não encontrado ou inativo"
        
        # Validar se obra está ativa
        obra = Obra.query.filter_by(
            id=obra_id,
            admin_id=current_user.id,
            ativo=True
        ).filter(Obra.status.in_(['Em andamento', 'Planejamento'])).first()
        
        if not obra:
            return False, "Obra não encontrada ou não está em andamento"
        
        # Verificar conflitos
        conflito = verificar_conflitos_alocacao(funcionario_id, data_alocacao, current_user.id)
        if conflito['tem_conflito']:
            detalhes = conflito['conflito_detalhes']
            return False, f"Funcionário já alocado para {detalhes['obra_nome']} ({detalhes['tipo_local']}) nesta data"
        
        # Criar alocação
        nova_alocacao = AlocacaoEquipe()
        nova_alocacao.funcionario_id = funcionario_id
        nova_alocacao.obra_id = obra_id
        nova_alocacao.data_alocacao = data_alocacao
        nova_alocacao.tipo_local = tipo_local
        nova_alocacao.turno = turno
        nova_alocacao.prioridade = prioridade
        nova_alocacao.criado_por_id = current_user.id
        nova_alocacao.observacoes = observacoes
        nova_alocacao.admin_id = current_user.id
        nova_alocacao.validacao_conflito = True
        
        db.session.add(nova_alocacao)
        db.session.flush()  # Para obter o ID
        
        # Se for campo, criar RDO automaticamente
        if tipo_local == 'campo':
            sucesso_rdo, resultado_rdo = criar_rdo_automatico_avancado(nova_alocacao.id)
            if not sucesso_rdo:
                logging.warning(f"Não foi possível criar RDO automaticamente: {resultado_rdo}")
        
        db.session.commit()
        
        logging.info(f"Alocação criada: {funcionario.nome} → {obra.nome} ({data_alocacao})")
        return True, nova_alocacao
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar alocação: {str(e)}")
        return False, f"Erro interno: {str(e)}"

# ================================
# ANALYTICS E RELATÓRIOS AVANÇADOS
# ================================

def gerar_relatorio_produtividade_avancado(data_inicio, data_fim, admin_id):
    """
    Gera relatório avançado de produtividade conforme especificação da reunião técnica.
    Inclui métricas detalhadas por funcionário, obra e tipo de local.
    """
    try:
        alocacoes = AlocacaoEquipe.query.filter(
            AlocacaoEquipe.data_alocacao.between(data_inicio, data_fim),
            AlocacaoEquipe.admin_id == admin_id,
            AlocacaoEquipe.status.in_(['Planejado', 'Executado'])
        ).all()
        
        # Dados por funcionário
        dados_funcionarios = defaultdict(lambda: {
            'dias_trabalhados': 0,
            'dias_oficina': 0,
            'dias_campo': 0,
            'obras_atendidas': set(),
            'rdos_gerados': 0,
            'alocacoes_canceladas': 0,
            'taxa_execucao': 0.0
        })
        
        # Dados por obra
        dados_obras = defaultdict(lambda: {
            'funcionarios_alocados': set(),
            'dias_atividade': 0,
            'rdos_gerados': 0,
            'percentual_campo': 0.0
        })
        
        total_alocacoes = len(alocacoes)
        alocacoes_executadas = 0
        
        for alocacao in alocacoes:
            funcionario_nome = alocacao.funcionario.nome
            obra_nome = alocacao.obra.nome
            
            # Dados do funcionário
            dados_funcionarios[funcionario_nome]['dias_trabalhados'] += 1
            
            if alocacao.tipo_local == 'oficina':
                dados_funcionarios[funcionario_nome]['dias_oficina'] += 1
            else:
                dados_funcionarios[funcionario_nome]['dias_campo'] += 1
                dados_funcionarios[funcionario_nome]['obras_atendidas'].add(alocacao.obra_id)
            
            if alocacao.rdo_gerado:
                dados_funcionarios[funcionario_nome]['rdos_gerados'] += 1
            
            if alocacao.status == 'Cancelado':
                dados_funcionarios[funcionario_nome]['alocacoes_canceladas'] += 1
            elif alocacao.status == 'Executado':
                alocacoes_executadas += 1
            
            # Dados da obra
            dados_obras[obra_nome]['funcionarios_alocados'].add(alocacao.funcionario_id)
            dados_obras[obra_nome]['dias_atividade'] += 1
            
            if alocacao.rdo_gerado:
                dados_obras[obra_nome]['rdos_gerados'] += 1
        
        # Calcular métricas finais
        for funcionario in dados_funcionarios:
            dados = dados_funcionarios[funcionario]
            dados['obras_atendidas'] = len(dados['obras_atendidas'])
            
            total_dias = dados['dias_trabalhados']
            if total_dias > 0:
                dados['taxa_execucao'] = round(
                    (total_dias - dados['alocacoes_canceladas']) / total_dias * 100, 2
                )
        
        for obra in dados_obras:
            dados = dados_obras[obra]
            dados['funcionarios_alocados'] = len(dados['funcionarios_alocados'])
            
            if dados['dias_atividade'] > 0:
                campo_count = sum(1 for a in alocacoes 
                                if a.obra.nome == obra and a.tipo_local == 'campo')
                dados['percentual_campo'] = round(
                    campo_count / dados['dias_atividade'] * 100, 2
                )
        
        # Estatísticas gerais
        taxa_execucao_geral = round(alocacoes_executadas / total_alocacoes * 100, 2) if total_alocacoes > 0 else 0
        
        return {
            'periodo': {
                'inicio': data_inicio.isoformat(),
                'fim': data_fim.isoformat(),
                'dias': (data_fim - data_inicio).days + 1
            },
            'estatisticas_gerais': {
                'total_alocacoes': total_alocacoes,
                'alocacoes_executadas': alocacoes_executadas,
                'taxa_execucao_geral': taxa_execucao_geral,
                'rdos_gerados': sum(1 for a in alocacoes if a.rdo_gerado)
            },
            'funcionarios': dict(dados_funcionarios),
            'obras': dict(dados_obras)
        }
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório de produtividade: {str(e)}")
        return None

def obter_dashboard_gestor_equipes(admin_id, data_referencia=None):
    """
    Gera dados para dashboard do gestor de equipes conforme reunião técnica.
    Visão diária com estatísticas, alertas e alocações.
    """
    try:
        if not data_referencia:
            data_referencia = date.today()
        
        # Alocações do dia
        alocacoes_dia = AlocacaoEquipe.query.filter_by(
            admin_id=admin_id,
            data_alocacao=data_referencia
        ).all()
        
        # Funcionários disponíveis (sem alocação no dia)
        funcionarios_alocados_ids = [a.funcionario_id for a in alocacoes_dia]
        funcionarios_disponiveis = Funcionario.query.filter(
            Funcionario.admin_id == admin_id,
            Funcionario.ativo == True,
            ~Funcionario.id.in_(funcionarios_alocados_ids)
        ).all()
        
        # Obras ativas
        obras_ativas = Obra.query.filter_by(
            admin_id=admin_id,
            ativo=True
        ).filter(Obra.status.in_(['Em andamento', 'Planejamento'])).all()
        
        # Estatísticas
        total_funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).count()
        funcionarios_alocados = len(funcionarios_alocados_ids)
        taxa_utilizacao = round(funcionarios_alocados / total_funcionarios * 100, 2) if total_funcionarios > 0 else 0
        
        # Alertas
        alertas = []
        
        # Funcionários sem alocação
        if len(funcionarios_disponiveis) > 0:
            alertas.append({
                'tipo': 'info',
                'titulo': 'Funcionários Disponíveis',
                'mensagem': f'{len(funcionarios_disponiveis)} funcionários sem alocação hoje',
                'acao': 'Considere alocar para obras pendentes'
            })
        
        # Obras sem equipe
        obras_sem_equipe = [obra for obra in obras_ativas 
                          if not any(a.obra_id == obra.id for a in alocacoes_dia)]
        
        if len(obras_sem_equipe) > 0:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Obras sem Equipe',
                'mensagem': f'{len(obras_sem_equipe)} obras sem funcionários alocados hoje',
                'acao': 'Verificar necessidade de alocação'
            })
        
        return {
            'data_referencia': data_referencia.isoformat(),
            'estatisticas': {
                'total_funcionarios': total_funcionarios,
                'funcionarios_alocados': funcionarios_alocados,
                'funcionarios_disponiveis': len(funcionarios_disponiveis),
                'taxa_utilizacao': taxa_utilizacao,
                'obras_ativas': len(obras_ativas),
                'alocacoes_campo': len([a for a in alocacoes_dia if a.tipo_local == 'campo']),
                'alocacoes_oficina': len([a for a in alocacoes_dia if a.tipo_local == 'oficina'])
            },
            'alocacoes_dia': [a.to_dict() for a in alocacoes_dia],
            'funcionarios_disponiveis': [{
                'id': f.id,
                'nome': f.nome,
                'cargo': f.cargo
            } for f in funcionarios_disponiveis],
            'obras_ativas': [{
                'id': o.id,
                'nome': o.nome,
                'codigo': o.codigo,
                'status': o.status
            } for o in obras_ativas],
            'alertas': alertas
        }
        
    except Exception as e:
        logging.error(f"Erro ao gerar dashboard: {str(e)}")
        return None

# ================================
# INTEGRAÇÃO COM SISTEMA DE PONTO
# ================================

def sincronizar_alocacao_com_ponto_avancado(alocacao_id):
    """
    Sincroniza alocação com sistema de ponto conforme reunião técnica.
    Integração automática quando funcionário bate ponto.
    """
    try:
        from models import RegistroPonto
        
        alocacao = AlocacaoEquipe.query.get(alocacao_id)
        if not alocacao:
            return False, "Alocação não encontrada"
        
        # Buscar registro de ponto do funcionário na data da alocação
        registro_ponto = RegistroPonto.query.filter_by(
            funcionario_id=alocacao.funcionario_id,
            data=alocacao.data_alocacao
        ).first()
        
        if registro_ponto:
            # Atualizar ponto com dados da alocação
            registro_ponto.obra_id = alocacao.obra_id
            if hasattr(registro_ponto, 'tipo_local'):
                registro_ponto.tipo_local = alocacao.tipo_local
            
            # Marcar alocação como executada
            alocacao.status = 'Executado'
            alocacao.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logging.info(f"Sincronização ponto-alocação realizada: {alocacao.funcionario.nome}")
            return True, "Sincronização realizada com sucesso"
        else:
            # Criar registro básico de ponto se não existir
            novo_registro = RegistroPonto()
            novo_registro.funcionario_id = alocacao.funcionario_id
            novo_registro.obra_id = alocacao.obra_id
            novo_registro.data = alocacao.data_alocacao
            if hasattr(novo_registro, 'tipo_local'):
                novo_registro.tipo_local = alocacao.tipo_local
            
            db.session.add(novo_registro)
            
            # Marcar alocação como executada
            alocacao.status = 'Executado'
            alocacao.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logging.info(f"Registro de ponto criado para alocação: {alocacao.funcionario.nome}")
            return True, "Registro de ponto criado automaticamente"
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro na sincronização ponto-alocação: {str(e)}")
        return False, f"Erro interno: {str(e)}"