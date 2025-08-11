#!/usr/bin/env python3
"""
MÓDULO 2: FUNÇÕES UTILITÁRIAS PARA PORTAL DO CLIENTE
Sistema SIGE v8.0 - Funções para cálculo de progresso e análise de obras
"""

from datetime import date, datetime, timedelta
from sqlalchemy import func, and_
from app import db
from models import Obra, RDO, RDOAtividade, RDOFoto, NotificacaoCliente
from collections import defaultdict
import statistics

def calcular_progresso_obra_cliente(obra_id):
    """
    Calcular progresso da obra baseado nos RDOs existentes
    Integra perfeitamente com sistema RDO atual
    """
    # Obter todas as atividades dos RDOs finalizados
    atividades_query = db.session.query(RDOAtividade, RDO).join(RDO).filter(
        RDO.obra_id == obra_id,
        RDO.status == 'Finalizado'  # Só considerar RDOs finalizados
    ).all()
    
    if not atividades_query:
        return {
            'percentual_geral': 0.0,
            'atividades_concluidas': 0,
            'atividades_total': 0,
            'ultima_atualizacao': None,
            'tendencia': 'estavel',
            'velocidade_media': 0.0
        }
    
    # Calcular estatísticas
    total_atividades = len(atividades_query)
    atividades_concluidas = 0
    soma_percentuais = 0.0
    ultima_atualizacao = None
    
    for atividade, rdo in atividades_query:
        soma_percentuais += atividade.percentual_conclusao or 0
        if atividade.percentual_conclusao >= 100:
            atividades_concluidas += 1
        
        if ultima_atualizacao is None or rdo.data_relatorio > ultima_atualizacao:
            ultima_atualizacao = rdo.data_relatorio
    
    # Percentual geral (média ponderada)
    percentual_geral = soma_percentuais / total_atividades if total_atividades > 0 else 0
    
    # Calcular tendência (últimos 7 dias vs 7 dias anteriores)
    tendencia = calcular_tendencia_progresso(obra_id)
    
    # Velocidade média (% por dia nos últimos 30 dias)
    velocidade_media = calcular_velocidade_progresso(obra_id)
    
    return {
        'percentual_geral': round(percentual_geral, 1),
        'atividades_concluidas': atividades_concluidas,
        'atividades_total': total_atividades,
        'ultima_atualizacao': ultima_atualizacao,
        'tendencia': tendencia,
        'velocidade_media': velocidade_media
    }

def obter_fotos_obra_recentes(obra_id, limite=6):
    """Obter fotos mais recentes da obra dos RDOs"""
    fotos_query = db.session.query(RDOFoto, RDO).join(RDO).filter(
        RDO.obra_id == obra_id,
        RDO.status == 'Finalizado'
    ).order_by(RDO.data_relatorio.desc(), RDOFoto.id.desc()).limit(limite).all()
    
    fotos_resultado = []
    for foto, rdo in fotos_query:
        fotos_resultado.append({
            'id': foto.id,
            'url': foto.caminho_foto,
            'descricao': foto.descricao or 'Foto da obra',
            'data': rdo.data_relatorio,
            'rdo_numero': rdo.numero_rdo,
            'thumbnail': gerar_thumbnail_url(foto.caminho_foto)
        })
    
    return fotos_resultado

def obter_timeline_obra(obra_id, limite=20):
    """Obter timeline completa da obra"""
    timeline = []
    
    # RDOs como eventos principais
    rdos = RDO.query.filter_by(obra_id=obra_id, status='Finalizado').order_by(RDO.data_relatorio.desc()).limit(limite).all()
    
    for rdo in rdos:
        # Contar atividades do RDO
        atividades_count = RDOAtividade.query.filter_by(rdo_id=rdo.id).count()
        atividades_concluidas = RDOAtividade.query.filter(
            RDOAtividade.rdo_id == rdo.id,
            RDOAtividade.percentual_conclusao >= 100
        ).count()
        
        # Contar fotos do RDO
        fotos_count = RDOFoto.query.filter_by(rdo_id=rdo.id).count()
        
        timeline.append({
            'tipo': 'rdo',
            'data': rdo.data_relatorio,
            'titulo': f'Relatório {rdo.numero_rdo}',
            'descricao': f'{atividades_count} atividades • {atividades_concluidas} concluídas • {fotos_count} fotos',
            'icone': 'fas fa-clipboard-list',
            'cor': 'primary',
            'detalhes': {
                'atividades_total': atividades_count,
                'atividades_concluidas': atividades_concluidas,
                'fotos_count': fotos_count,
                'rdo_id': rdo.id
            }
        })
    
    # Adicionar marcos importantes (atividades 100% concluídas)
    marcos = db.session.query(RDOAtividade, RDO).join(RDO).filter(
        RDO.obra_id == obra_id,
        RDOAtividade.percentual_conclusao >= 100,
        RDO.status == 'Finalizado'
    ).order_by(RDO.data_relatorio.desc()).limit(10).all()
    
    for atividade, rdo in marcos:
        timeline.append({
            'tipo': 'marco',
            'data': rdo.data_relatorio,
            'titulo': 'Atividade Concluída',
            'descricao': atividade.descricao_atividade,
            'icone': 'fas fa-check-circle',
            'cor': 'success',
            'detalhes': {
                'atividade_id': atividade.id,
                'percentual': atividade.percentual_conclusao
            }
        })
    
    # Ordenar por data (mais recente primeiro)
    timeline.sort(key=lambda x: x['data'], reverse=True)
    
    return timeline[:limite]

def calcular_previsao_conclusao(obra_id):
    """Calcular previsão de conclusão usando análise estatística"""
    progresso_atual = calcular_progresso_obra_cliente(obra_id)
    
    if progresso_atual['percentual_geral'] <= 0:
        return None
    
    # Obter histórico dos últimos 30 dias
    data_limite = date.today() - timedelta(days=30)
    historico = db.session.query(RDO.data_relatorio, func.avg(RDOAtividade.percentual_conclusao)).join(RDOAtividade).filter(
        RDO.obra_id == obra_id,
        RDO.data_relatorio >= data_limite,
        RDO.status == 'Finalizado'
    ).group_by(RDO.data_relatorio).order_by(RDO.data_relatorio).all()
    
    if len(historico) < 5:  # Mínimo 5 pontos de dados
        return {
            'data_previsao': None,
            'confianca': 'baixa',
            'dias_restantes': None,
            'velocidade_media': progresso_atual['velocidade_media']
        }
    
    # Calcular velocidade média (% por dia)
    velocidades = []
    for i in range(1, len(historico)):
        data_anterior, progresso_anterior = historico[i-1]
        data_atual, progresso_atual_hist = historico[i]
        
        dias_diff = (data_atual - data_anterior).days
        if dias_diff > 0:
            velocidade = (progresso_atual_hist - progresso_anterior) / dias_diff
            velocidades.append(velocidade)
    
    if not velocidades:
        return None
    
    velocidade_media = statistics.mean(velocidades)
    
    if velocidade_media <= 0:
        return {
            'data_previsao': None,
            'confianca': 'baixa',
            'dias_restantes': None,
            'velocidade_media': 0
        }
    
    # Calcular dias restantes
    percentual_restante = 100 - progresso_atual['percentual_geral']
    dias_restantes = int(percentual_restante / velocidade_media)
    data_previsao = date.today() + timedelta(days=dias_restantes)
    
    # Calcular confiança baseada na consistência da velocidade
    desvio_padrao = statistics.stdev(velocidades) if len(velocidades) > 1 else 0
    confianca = 'alta' if desvio_padrao < 0.5 else 'media' if desvio_padrao < 1.0 else 'baixa'
    
    return {
        'data_previsao': data_previsao,
        'confianca': confianca,
        'dias_restantes': dias_restantes,
        'velocidade_media': round(velocidade_media, 2)
    }

def calcular_tendencia_progresso(obra_id):
    """Calcular se o progresso está acelerando, estável ou desacelerando"""
    # Últimos 14 dias divididos em 2 períodos de 7 dias
    hoje = date.today()
    periodo_recente_inicio = hoje - timedelta(days=7)
    periodo_anterior_inicio = hoje - timedelta(days=14)
    
    # Progresso período recente (últimos 7 dias)
    progresso_recente = db.session.query(func.avg(RDOAtividade.percentual_conclusao)).join(RDO).filter(
        RDO.obra_id == obra_id,
        RDO.data_relatorio >= periodo_recente_inicio,
        RDO.status == 'Finalizado'
    ).scalar() or 0
    
    # Progresso período anterior (7-14 dias atrás)
    progresso_anterior = db.session.query(func.avg(RDOAtividade.percentual_conclusao)).join(RDO).filter(
        RDO.obra_id == obra_id,
        RDO.data_relatorio >= periodo_anterior_inicio,
        RDO.data_relatorio < periodo_recente_inicio,
        RDO.status == 'Finalizado'
    ).scalar() or 0
    
    diferenca = progresso_recente - progresso_anterior
    
    if diferenca > 2:
        return 'acelerando'
    elif diferenca < -2:
        return 'desacelerando'
    else:
        return 'estavel'

def calcular_velocidade_progresso(obra_id):
    """Calcular velocidade média de progresso (% por dia)"""
    # Últimos 30 dias
    data_limite = date.today() - timedelta(days=30)
    
    historico = db.session.query(RDO.data_relatorio, func.avg(RDOAtividade.percentual_conclusao)).join(RDOAtividade).filter(
        RDO.obra_id == obra_id,
        RDO.data_relatorio >= data_limite,
        RDO.status == 'Finalizado'
    ).group_by(RDO.data_relatorio).order_by(RDO.data_relatorio).all()
    
    if len(historico) < 2:
        return 0.0
    
    # Calcular velocidade entre primeiro e último ponto
    primeiro_dia, primeiro_progresso = historico[0]
    ultimo_dia, ultimo_progresso = historico[-1]
    
    dias_total = (ultimo_dia - primeiro_dia).days
    if dias_total <= 0:
        return 0.0
    
    velocidade = (ultimo_progresso - primeiro_progresso) / dias_total
    return round(velocidade, 2)

def gerar_thumbnail_url(caminho_foto):
    """Gerar URL de thumbnail para foto (implementação básica)"""
    if not caminho_foto:
        return '/static/img/no-image.jpg'
    
    # Se for URL externa, retornar como está
    if caminho_foto.startswith('http'):
        return caminho_foto
    
    # Se for arquivo local, gerar thumbnail
    nome_arquivo = caminho_foto.split('/')[-1]
    nome_base = nome_arquivo.split('.')[0]
    extensao = nome_arquivo.split('.')[-1] if '.' in nome_arquivo else 'jpg'
    
    return f'/static/uploads/thumbnails/{nome_base}_thumb.{extensao}'

def criar_notificacao_cliente(obra_id, tipo, titulo, mensagem, rdo_id=None, atividade_id=None, prioridade='normal'):
    """Criar notificação para o cliente"""
    notificacao = NotificacaoCliente()
    notificacao.obra_id = obra_id
    notificacao.tipo = tipo
    notificacao.titulo = titulo
    notificacao.mensagem = mensagem
    notificacao.rdo_id = rdo_id
    notificacao.atividade_id = atividade_id
    notificacao.prioridade = prioridade
    
    db.session.add(notificacao)
    db.session.commit()
    
    return notificacao

def obter_notificacoes_nao_lidas(obra_id):
    """Obter notificações não lidas do cliente"""
    return NotificacaoCliente.query.filter_by(
        obra_id=obra_id,
        visualizada=False
    ).order_by(NotificacaoCliente.created_at.desc()).all()

def marcar_notificacoes_como_lidas(obra_id):
    """Marcar todas as notificações como lidas"""
    NotificacaoCliente.query.filter_by(
        obra_id=obra_id,
        visualizada=False
    ).update({
        'visualizada': True,
        'data_visualizacao': datetime.utcnow()
    })
    
    db.session.commit()

def gerar_token_cliente_obra(obra_id):
    """Gerar token único para acesso do cliente à obra"""
    import secrets
    import string
    
    # Gerar token seguro de 32 caracteres
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    # Verificar se token já existe
    while Obra.query.filter_by(token_cliente=token).first():
        token = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    # Atualizar obra com o token
    obra = Obra.query.get(obra_id)
    if obra:
        obra.token_cliente = token
        db.session.commit()
    
    return token

def atualizar_dados_cliente_obra(obra_id, proposta_id):
    """Atualizar dados do cliente na obra baseado na proposta"""
    from models import Proposta
    
    obra = Obra.query.get(obra_id)
    proposta = Proposta.query.get(proposta_id)
    
    if obra and proposta:
        obra.cliente_nome = proposta.cliente_nome
        obra.cliente_email = proposta.cliente_email
        obra.cliente_telefone = proposta.cliente_telefone
        obra.proposta_origem_id = proposta_id
        
        # Gerar token se não existir
        if not obra.token_cliente:
            obra.token_cliente = gerar_token_cliente_obra(obra_id)
        
        db.session.commit()
        
        # Criar notificação de boas-vindas
        criar_notificacao_cliente(
            obra_id=obra_id,
            tipo='obra_iniciada',
            titulo='Obra Iniciada!',
            mensagem=f'Sua obra "{obra.nome}" foi iniciada. Acompanhe o progresso através deste portal.',
            prioridade='alta'
        )
        
        return True
    
    return False