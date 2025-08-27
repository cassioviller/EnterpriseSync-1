# SISTEMA COMPLETO DE VISUALIZAÇÃO E EDIÇÃO DE RDO
# Compatível com schema atual da base de dados

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, RDO, RDOMaoObra, RDOServicoSubatividade, Obra, Funcionario, Servico, SubAtividade
from bypass_auth import obter_admin_id
from datetime import datetime, date
from sqlalchemy import desc, and_
import logging

rdo_viewer_bp = Blueprint('rdo_viewer', __name__)
logger = logging.getLogger(__name__)

# ================================
# UTILITÁRIOS DE CARREGAMENTO
# ================================

def carregar_rdo_completo(rdo_id, admin_id):
    """Carrega RDO completo com todos os relacionamentos"""
    rdo = db.session.query(RDO).filter(
        and_(RDO.id == rdo_id, RDO.admin_id == admin_id)
    ).first()
    
    if not rdo:
        return None
    
    # Carregar dados relacionados
    rdo.mao_obra_dados = db.session.query(RDOMaoObra).filter(
        RDOMaoObra.rdo_id == rdo_id
    ).all()
    
    rdo.subatividades_dados = db.session.query(RDOServicoSubatividade).filter(
        RDOServicoSubatividade.rdo_id == rdo_id
    ).all()
    
    return rdo

def extrair_dados_edicao(rdo):
    """Extrai dados do RDO para modo edição (compatível com schema atual)"""
    dados = {
        'rdo_id': rdo.id,
        'numero_rdo': rdo.numero_rdo,
        'obra_id': rdo.obra_id,
        'data_relatorio': rdo.data_relatorio.isoformat() if rdo.data_relatorio else '',
        'clima_geral': rdo.clima_geral or '',
        'condicoes_trabalho': rdo.condicoes_trabalho or '',
        'comentario_geral': rdo.comentario_geral or '',
        'status': rdo.status or 'Rascunho',
        'equipe': {},
        'subatividades': {}
    }
    
    # Carregar equipe (usando schema atual com funcao_exercida)
    for mao_obra in getattr(rdo, 'mao_obra_dados', []):
        dados['equipe'][str(mao_obra.funcionario_id)] = {
            'horas': float(mao_obra.horas_trabalhadas),
            'funcao': mao_obra.funcao_exercida  # Schema atual usa funcao_exercida
        }
    
    # Carregar subatividades (usando schema atual)
    for sub_ativ in getattr(rdo, 'subatividades_dados', []):
        # Para o schema atual, usamos o nome da subatividade como chave
        dados['subatividades'][f"sub_{sub_ativ.id}"] = {
            'nome_subatividade': sub_ativ.nome_subatividade,
            'percentual': float(sub_ativ.percentual_conclusao or 0),
            'observacoes': sub_ativ.observacoes_tecnicas or '',
            'servico_id': sub_ativ.servico_id
        }
    
    return dados

def obter_historico_ultimo_rdo(obra_id, data_atual, admin_id):
    """Obtém dados do último RDO para herança de percentuais"""
    ultimo_rdo = db.session.query(RDO).filter(
        and_(
            RDO.obra_id == obra_id,
            RDO.admin_id == admin_id,
            RDO.data_relatorio < data_atual
        )
    ).order_by(desc(RDO.data_relatorio)).first()
    
    if not ultimo_rdo:
        return {'atividades': [], 'origem': 'Nenhum RDO anterior'}
    
    # Carregar subatividades do último RDO
    subatividades = db.session.query(RDOServicoSubatividade).filter(
        RDOServicoSubatividade.rdo_id == ultimo_rdo.id
    ).all()
    
    atividades = []
    for sub in subatividades:
        atividades.append({
            'descricao': sub.nome_subatividade,
            'percentual': float(sub.percentual_conclusao or 0)
        })
    
    return {
        'atividades': atividades,
        'origem': f'RDO {ultimo_rdo.numero_rdo} ({ultimo_rdo.data_relatorio.strftime("%d/%m/%Y")})'
    }

# ================================
# ROTAS DE VISUALIZAÇÃO
# ================================

@rdo_viewer_bp.route('/rdos/lista')
def listar_rdos():
    """Lista todos os RDOs do admin atual"""
    admin_id = obter_admin_id()
    
    try:
        # Query otimizada com join para obter dados da obra
        rdos = db.session.query(RDO).join(Obra).filter(
            RDO.admin_id == admin_id
        ).order_by(desc(RDO.data_relatorio)).all()
        
        # Enriquecer dados dos RDOs
        rdos_dados = []
        for rdo in rdos:
            rdo_data = {
                'id': rdo.id,
                'numero_rdo': rdo.numero_rdo,
                'data_relatorio': rdo.data_relatorio,
                'obra': rdo.obra,
                'status': rdo.status,
                'criado_por': rdo.criado_por,
                'total_funcionarios': len(rdo.mao_obra),
                'total_subatividades': len(rdo.servico_subatividades)
            }
            rdos_dados.append(rdo_data)
        
        return render_template('funcionario/lista_rdos.html', rdos=rdos_dados)
        
    except Exception as e:
        logger.error(f"Erro ao listar RDOs: {str(e)}")
        flash('Erro ao carregar lista de RDOs', 'error')
        return redirect(url_for('funcionario_dashboard'))

@rdo_viewer_bp.route('/rdo/<int:rdo_id>/visualizar')
def visualizar_rdo(rdo_id):
    """Visualiza RDO completo somente leitura"""
    admin_id = obter_admin_id()
    
    try:
        rdo = carregar_rdo_completo(rdo_id, admin_id)
        if not rdo:
            flash('RDO não encontrado', 'error')
            return redirect(url_for('rdo_viewer.listar_rdos'))
        
        return render_template('funcionario/visualizar_rdo.html', rdo=rdo)
        
    except Exception as e:
        logger.error(f"Erro ao visualizar RDO {rdo_id}: {str(e)}")
        flash('Erro ao carregar RDO', 'error')
        return redirect(url_for('rdo_viewer.listar_rdos'))

@rdo_viewer_bp.route('/rdo/<int:rdo_id>/editar')
def editar_rdo(rdo_id):
    """Edita RDO existente"""
    admin_id = obter_admin_id()
    
    try:
        rdo = carregar_rdo_completo(rdo_id, admin_id)
        if not rdo:
            flash('RDO não encontrado', 'error')
            return redirect(url_for('rdo_viewer.listar_rdos'))
        
        # Extrair dados para edição
        dados_salvos = extrair_dados_edicao(rdo)
        
        # Obter dados necessários para o formulário
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        return render_template('funcionario/rdo_consolidado.html',
                             obras=obras,
                             funcionarios=funcionarios,
                             rdo=rdo,
                             modo_edicao=True,
                             dados_salvos=dados_salvos)
        
    except Exception as e:
        logger.error(f"Erro ao carregar RDO para edição {rdo_id}: {str(e)}")
        flash('Erro ao carregar RDO para edição', 'error')
        return redirect(url_for('rdo_viewer.listar_rdos'))

# ================================
# ROTAS DE SALVAMENTO
# ================================

@rdo_viewer_bp.route('/rdo/salvar', methods=['POST'])
def salvar_rdo():
    """Salva ou atualiza RDO (compatível com schema atual)"""
    admin_id = obter_admin_id()
    
    try:
        dados = request.form.to_dict()
        rdo_id = dados.get('rdo_id')
        
        logger.debug(f"Salvando RDO - Dados recebidos: {dados}")
        
        # Modo edição ou criação
        if rdo_id:
            rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
            if not rdo:
                return jsonify({'success': False, 'message': 'RDO não encontrado'})
        else:
            rdo = RDO()
            rdo.numero_rdo = gerar_numero_rdo_unico()
            rdo.criado_por_id = admin_id
            rdo.admin_id = admin_id
        
        # Atualizar dados básicos
        if dados.get('data_relatorio'):
            rdo.data_relatorio = datetime.strptime(dados.get('data_relatorio'), '%Y-%m-%d').date()
        rdo.obra_id = int(dados.get('obra_id')) if dados.get('obra_id') else None
        rdo.clima_geral = dados.get('clima_geral', '')
        rdo.condicoes_trabalho = dados.get('condicoes_trabalho', '')
        rdo.comentario_geral = dados.get('comentario_geral', '')
        rdo.status = dados.get('status', 'Rascunho')
        
        # Salvar RDO primeiro
        if not rdo_id:
            db.session.add(rdo)
        db.session.commit()
        
        # Processar mão de obra (compatível com schema)
        processar_mao_obra_schema_atual(rdo, dados)
        
        # Processar subatividades (compatível com schema)
        processar_subatividades_schema_atual(rdo, dados)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'RDO salvo com sucesso!',
            'rdo_id': rdo.id,
            'numero_rdo': rdo.numero_rdo
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar RDO: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro ao salvar: {str(e)}'})

def processar_mao_obra_schema_atual(rdo, dados):
    """Processa mão de obra usando schema atual (funcao_exercida)"""
    # Limpar registros anteriores
    if rdo.id:
        RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
    
    # Processar funcionários
    for key, value in dados.items():
        if key.startswith('funcionario_') and key.endswith('_horas'):
            funcionario_id = key.replace('funcionario_', '').replace('_horas', '')
            horas = float(value) if value else 0
            
            if horas > 0:
                funcao = dados.get(f'funcionario_{funcionario_id}_funcao', 'Funcionário')
                
                # Usar schema atual com funcao_exercida
                mao_obra = RDOMaoObra()
                mao_obra.rdo_id = rdo.id
                mao_obra.funcionario_id = int(funcionario_id)
                mao_obra.funcao_exercida = funcao  # Campo correto do schema
                mao_obra.horas_trabalhadas = horas
                db.session.add(mao_obra)

def processar_subatividades_schema_atual(rdo, dados):
    """Processa subatividades usando schema atual"""
    # Limpar registros anteriores
    if rdo.id:
        RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
    
    # Processar subatividades
    for key, value in dados.items():
        if key.startswith('subatividade_') and key.endswith('_percentual'):
            subatividade_id = key.replace('subatividade_', '').replace('_percentual', '')
            percentual = float(value) if value else 0
            
            if percentual > 0:
                observacoes = dados.get(f'subatividade_{subatividade_id}_observacoes', '')
                
                # Para schema atual, precisamos do nome da subatividade
                subatividade = SubAtividade.query.get(int(subatividade_id))
                
                # Usar schema atual
                registro = RDOServicoSubatividade()
                registro.rdo_id = rdo.id
                registro.servico_id = subatividade.servico_id if subatividade else None
                registro.nome_subatividade = subatividade.nome if subatividade else f'Subatividade {subatividade_id}'
                registro.percentual_conclusao = percentual  # Campo correto do schema
                registro.observacoes_tecnicas = observacoes  # Campo correto do schema
                registro.admin_id = obter_admin_id()
                db.session.add(registro)

def gerar_numero_rdo_unico():
    """Gera número único para RDO"""
    ano_atual = datetime.now().year
    
    # Buscar último RDO do ano
    ultimo_rdo = RDO.query.filter(
        RDO.numero_rdo.contains(f'RDO-{ano_atual}-')
    ).order_by(desc(RDO.numero_rdo)).first()
    
    if ultimo_rdo:
        try:
            ultimo_numero = int(ultimo_rdo.numero_rdo.split('-')[-1])
            proximo_numero = ultimo_numero + 1
        except:
            proximo_numero = 1
    else:
        proximo_numero = 1
    
    return f'RDO-{ano_atual}-{proximo_numero:03d}'

# ================================
# APIs PARA CARREGAMENTO DINÂMICO
# ================================

@rdo_viewer_bp.route('/api/rdo/<int:rdo_id>/dados')
def api_dados_rdo(rdo_id):
    """API para carregar dados de um RDO específico"""
    admin_id = obter_admin_id()
    
    try:
        rdo = carregar_rdo_completo(rdo_id, admin_id)
        if not rdo:
            return jsonify({'error': 'RDO não encontrado'})
        
        dados = extrair_dados_edicao(rdo)
        return jsonify({'success': True, 'dados': dados})
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados RDO {rdo_id}: {str(e)}")
        return jsonify({'error': 'Erro interno', 'success': False})

@rdo_viewer_bp.route('/api/obra/<int:obra_id>/ultimo-rdo')
def api_ultimo_rdo_obra(obra_id):
    """API para carregar percentuais do último RDO da obra"""
    admin_id = obter_admin_id()
    
    try:
        historico = obter_historico_ultimo_rdo(obra_id, date.today(), admin_id)
        return jsonify(historico)
        
    except Exception as e:
        logger.error(f"Erro ao carregar último RDO obra {obra_id}: {str(e)}")
        return jsonify({'atividades': [], 'origem': 'Erro ao carregar'})

@rdo_viewer_bp.route('/rdo/<int:rdo_id>/deletar', methods=['POST'])
def deletar_rdo(rdo_id):
    """Deleta RDO completamente"""
    admin_id = obter_admin_id()
    
    try:
        rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
        if not rdo:
            return jsonify({'success': False, 'message': 'RDO não encontrado'})
        
        # Deletar relacionados primeiro
        RDOMaoObra.query.filter_by(rdo_id=rdo_id).delete()
        RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).delete()
        
        # Deletar RDO
        db.session.delete(rdo)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'RDO deletado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar RDO {rdo_id}: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro ao deletar: {str(e)}'})