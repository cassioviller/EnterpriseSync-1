from models import db
#!/usr/bin/env python3
"""
MÓDULO 3: GESTÃO DE EQUIPES - Funções Utilitárias
Sistema de alocação com interface Kanban/Calendário
"""

from datetime import datetime, date, timedelta
from flask_login import current_user
from models import AlocacaoEquipe, Funcionario, Obra, RDO, RegistroPonto
from sqlalchemy import func, and_, or_

def pode_alocar_funcionario(funcionario_id, data_alocacao, admin_id=None):
    """
    Verifica se um funcionário pode ser alocado em uma data específica
    """
    admin_id = admin_id or current_user.id
    
    # Verifica se já existe alocação na data
    alocacao_existente = AlocacaoEquipe.query.filter(
        AlocacaoEquipe.funcionario_id == funcionario_id,
        AlocacaoEquipe.data_alocacao == data_alocacao,
        AlocacaoEquipe.admin_id == admin_id,
        AlocacaoEquipe.status != 'Cancelado'
    ).first()
    
    return alocacao_existente is None

def criar_alocacao_equipe(funcionario_id, obra_id, data_alocacao, tipo_local='campo', 
                         turno='matutino', observacoes=None, admin_id=None):
    """
    Cria uma nova alocação de equipe com validações
    """
    admin_id = admin_id or current_user.id
    
    # Validar se funcionário pode ser alocado
    if not pode_alocar_funcionario(funcionario_id, data_alocacao, admin_id):
        return False, "Funcionário já possui alocação para esta data"
    
    # Validar funcionário ativo
    funcionario = Funcionario.query.filter_by(
        id=funcionario_id, 
        admin_id=admin_id,
        ativo=True
    ).first()
    
    if not funcionario:
        return False, "Funcionário não encontrado ou inativo"
    
    # Validar obra ativa
    obra = Obra.query.filter_by(
        id=obra_id,
        admin_id=admin_id
    ).filter(Obra.status.in_(['Planejamento', 'Em Andamento'])).first()
    
    if not obra:
        return False, "Obra não encontrada ou não está em andamento"
    
    try:
        nova_alocacao = AlocacaoEquipe()
        nova_alocacao.funcionario_id = funcionario_id
        nova_alocacao.obra_id = obra_id
        nova_alocacao.data_alocacao = data_alocacao
        nova_alocacao.tipo_local = tipo_local
        nova_alocacao.turno = turno
        nova_alocacao.criado_por_id = current_user.id
        nova_alocacao.observacoes = observacoes
        nova_alocacao.admin_id = admin_id
        
        db.session.add(nova_alocacao)
        db.session.commit()
        
        return True, nova_alocacao
        
    except Exception as e:
        db.session.rollback()
        return False, f"Erro ao criar alocação: {str(e)}"

def obter_alocacoes_periodo(data_inicio, data_fim, admin_id=None):
    """
    Retorna todas as alocações de um período para interface Kanban/Calendário
    """
    admin_id = admin_id or current_user.id
    
    alocacoes = AlocacaoEquipe.query.filter(
        AlocacaoEquipe.admin_id == admin_id,
        AlocacaoEquipe.data_alocacao >= data_inicio,
        AlocacaoEquipe.data_alocacao <= data_fim
    ).join(Funcionario).join(Obra).all()
    
    return [alocacao.to_dict() for alocacao in alocacoes]

def obter_funcionarios_disponiveis(data_consulta, admin_id=None):
    """
    Lista funcionários disponíveis para alocação em uma data específica
    """
    admin_id = admin_id or current_user.id
    
    # Funcionários ativos
    funcionarios_ativos = Funcionario.query.filter_by(
        admin_id=admin_id,
        ativo=True
    ).all()
    
    # IDs dos funcionários já alocados na data
    alocados_ids = [a.funcionario_id for a in AlocacaoEquipe.query.filter(
        AlocacaoEquipe.admin_id == admin_id,
        AlocacaoEquipe.data_alocacao == data_consulta,
        AlocacaoEquipe.status != 'Cancelado'
    ).all()]
    
    # Funcionários disponíveis
    disponiveis = []
    for funcionario in funcionarios_ativos:
        if funcionario.id not in alocados_ids:
            disponiveis.append({
                'id': funcionario.id,
                'nome': funcionario.nome,
                'cargo': funcionario.cargo,
                'especialidade': funcionario.especialidade
            })
    
    return disponiveis

def gerar_rdo_automatico(alocacao_id, admin_id=None):
    """
    Gera RDO automaticamente para alocação do tipo 'campo'
    """
    admin_id = admin_id or current_user.id
    
    alocacao = AlocacaoEquipe.query.filter_by(
        id=alocacao_id,
        admin_id=admin_id
    ).first()
    
    if not alocacao:
        return False, "Alocação não encontrada"
    
    if alocacao.tipo_local != 'campo':
        return False, "RDO só é gerado para alocações em campo"
    
    if alocacao.rdo_gerado:
        return False, "RDO já foi gerado para esta alocação"
    
    try:
        # Criar RDO básico (simplificado para alocação)
        novo_rdo = RDO()
        novo_rdo.obra_id = alocacao.obra_id
        novo_rdo.data_relatorio = alocacao.data_alocacao
        novo_rdo.criado_por_id = current_user.id
        novo_rdo.tempo_manha = 'Bom'
        novo_rdo.observacoes = f'RDO gerado automaticamente pela alocação de equipe #{alocacao.id}'
        novo_rdo.admin_id = admin_id
        # Definir número do RDO
        import secrets
        novo_rdo.numero_rdo = f'RDO-{alocacao.data_alocacao.strftime("%Y%m%d")}-{secrets.token_hex(3).upper()}'
        
        db.session.add(novo_rdo)
        db.session.flush()  # Para obter o ID
        
        # Atualizar alocação
        alocacao.rdo_gerado = True
        alocacao.rdo_gerado_id = novo_rdo.id
        alocacao.status = 'Executado'
        
        db.session.commit()
        
        return True, novo_rdo
        
    except Exception as e:
        db.session.rollback()
        return False, f"Erro ao gerar RDO: {str(e)}"

def atualizar_status_alocacao(alocacao_id, novo_status, admin_id=None):
    """
    Atualiza o status de uma alocação
    """
    admin_id = admin_id or current_user.id
    
    alocacao = AlocacaoEquipe.query.filter_by(
        id=alocacao_id,
        admin_id=admin_id
    ).first()
    
    if not alocacao:
        return False, "Alocação não encontrada"
    
    # Validar status
    status_validos = ['Planejado', 'Executado', 'Cancelado']
    if novo_status not in status_validos:
        return False, f"Status inválido. Use: {', '.join(status_validos)}"
    
    try:
        alocacao.status = novo_status
        db.session.commit()
        return True, alocacao
        
    except Exception as e:
        db.session.rollback()
        return False, f"Erro ao atualizar status: {str(e)}"

def sincronizar_com_ponto(alocacao_id, admin_id=None):
    """
    Sincroniza alocação com registro de ponto
    """
    admin_id = admin_id or current_user.id
    
    alocacao = AlocacaoEquipe.query.filter_by(
        id=alocacao_id,
        admin_id=admin_id
    ).first()
    
    if not alocacao:
        return False, "Alocação não encontrada"
    
    try:
        # Verificar se já existe registro de ponto
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=alocacao.funcionario_id,
            data=alocacao.data_alocacao
        ).first()
        
        if registro_existente:
            # Atualizar tipo_local se necessário
            if hasattr(registro_existente, 'tipo_local'):
                registro_existente.tipo_local = alocacao.tipo_local
                registro_existente.obra_id = alocacao.obra_id
        else:
            # Criar registro básico de ponto
            novo_registro = RegistroPonto()
            novo_registro.funcionario_id = alocacao.funcionario_id
            novo_registro.obra_id = alocacao.obra_id
            novo_registro.data = alocacao.data_alocacao
            novo_registro.tipo_local = alocacao.tipo_local
            db.session.add(novo_registro)
        
        db.session.commit()
        return True, "Sincronização realizada com sucesso"
        
    except Exception as e:
        db.session.rollback()
        return False, f"Erro na sincronização: {str(e)}"

def relatorio_alocacoes_periodo(data_inicio, data_fim, admin_id=None):
    """
    Gera relatório de alocações por período
    """
    admin_id = admin_id or current_user.id
    
    alocacoes = AlocacaoEquipe.query.filter(
        AlocacaoEquipe.admin_id == admin_id,
        AlocacaoEquipe.data_alocacao >= data_inicio,
        AlocacaoEquipe.data_alocacao <= data_fim
    ).join(Funcionario).join(Obra).all()
    
    # Agregar estatísticas
    total_alocacoes = len(alocacoes)
    por_status = {}
    por_local = {}
    por_funcionario = {}
    
    for alocacao in alocacoes:
        # Por status
        status = alocacao.status
        por_status[status] = por_status.get(status, 0) + 1
        
        # Por local
        local = alocacao.tipo_local
        por_local[local] = por_local.get(local, 0) + 1
        
        # Por funcionário
        func = alocacao.funcionario.nome
        por_funcionario[func] = por_funcionario.get(func, 0) + 1
    
    return {
        'periodo': {
            'inicio': data_inicio.isoformat(),
            'fim': data_fim.isoformat()
        },
        'total_alocacoes': total_alocacoes,
        'estatisticas': {
            'por_status': por_status,
            'por_local': por_local,
            'por_funcionario': por_funcionario
        },
        'alocacoes': [alocacao.to_dict() for alocacao in alocacoes]
    }

def obter_equipe_obra(obra_id, data_consulta=None, admin_id=None):
    """
    Retorna a equipe alocada para uma obra em uma data específica
    """
    admin_id = admin_id or current_user.id
    data_consulta = data_consulta or date.today()
    
    equipe = AlocacaoEquipe.query.filter(
        AlocacaoEquipe.admin_id == admin_id,
        AlocacaoEquipe.obra_id == obra_id,
        AlocacaoEquipe.data_alocacao == data_consulta,
        AlocacaoEquipe.status != 'Cancelado'
    ).join(Funcionario).all()
    
    return [{
        'alocacao_id': alocacao.id,
        'funcionario': {
            'id': alocacao.funcionario.id,
            'nome': alocacao.funcionario.nome,
            'cargo': alocacao.funcionario.cargo,
            'especialidade': alocacao.funcionario.especialidade
        },
        'tipo_local': alocacao.tipo_local,
        'turno': alocacao.turno,
        'status': alocacao.status,
        'rdo_gerado': alocacao.rdo_gerado
    } for alocacao in equipe]