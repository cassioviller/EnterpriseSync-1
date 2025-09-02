# RDO SYSTEM - VERSÃO OTIMIZADA E REFINADA
# Sistema consolidado sem redundâncias

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, RDO, RDOMaoObra, RDOServicoSubatividade, Obra, Funcionario, Servico, SubAtividade, RDOAtividade
from bypass_auth import obter_admin_id
from datetime import datetime, date
import logging
from sqlalchemy import desc

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

rdo_bp = Blueprint('rdo_optimized', __name__)

# ================================
# UTILITÁRIOS COMUNS
# ================================

def gerar_numero_rdo():
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

def obter_dados_obra(obra_id, admin_id):
    """Obtém dados da obra com todos os relacionamentos necessários"""
    return Obra.query.filter_by(
        id=obra_id, 
        admin_id=admin_id, 
        ativo=True
    ).first()

def obter_funcionarios_disponiveis(admin_id):
    """Obtém funcionários ativos para o admin"""
    return Funcionario.query.filter_by(
        admin_id=admin_id, 
        ativo=True
    ).all()

def obter_servicos_obra(obra_id, admin_id):
    """Obtém serviços disponíveis para uma obra"""
    return Servico.query.filter_by(ativo=True).all()

def obter_ultimo_rdo_obra(obra_id, data_atual, admin_id):
    """Obtém o último RDO da obra para herança de percentuais"""
    return RDO.query.filter(
        RDO.obra_id == obra_id,
        RDO.admin_id == admin_id,
        RDO.data_relatorio < data_atual
    ).order_by(RDO.data_relatorio.desc()).first()

# ================================
# ROTAS PRINCIPAIS
# ================================

@rdo_bp.route('/rdo/novo')
def novo_rdo():
    """Tela para criar novo RDO"""
    admin_id = obter_admin_id()
    
    # Obter dados necessários
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    funcionarios = obter_funcionarios_disponiveis(admin_id)
    
    return render_template('funcionario/rdo_consolidado.html',
                         obras=obras,
                         funcionarios=funcionarios,
                         modo_edicao=False,
                         dados_salvos={})

@rdo_bp.route('/rdo/editar/<int:rdo_id>')
def editar_rdo(rdo_id):
    """Tela para editar RDO existente"""
    admin_id = obter_admin_id()
    
    # Buscar RDO
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        flash('RDO não encontrado', 'error')
        return redirect(url_for('funcionario_dashboard'))
    
    # Obter dados necessários
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    funcionarios = obter_funcionarios_disponiveis(admin_id)
    
    # Preparar dados salvos do RDO
    dados_salvos = carregar_dados_rdo(rdo)
    
    return render_template('funcionario/rdo_consolidado.html',
                         obras=obras,
                         funcionarios=funcionarios,
                         rdo=rdo,
                         modo_edicao=True,
                         dados_salvos=dados_salvos)

@rdo_bp.route('/api/ultimo-rdo-dados/<int:obra_id>')
def api_ultimo_rdo_dados(obra_id):
    """API para obter dados do último RDO de uma obra"""
    try:
        admin_id = obter_admin_id()
        print(f"✅ API ÚLTIMO RDO: obra_id={obra_id}, admin_id={admin_id}")
        
        # Buscar último RDO da obra
        ultimo_rdo = obter_ultimo_rdo_obra(obra_id, date.today(), admin_id)
        
        if not ultimo_rdo:
            return jsonify({
                'success': False,
                'message': 'Nenhum RDO anterior encontrado para esta obra',
                'ultimo_rdo': None
            })
        
        # Buscar serviços do último RDO
        servicos_rdo = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo_rdo.id).all()
        servicos_dados = []
        
        for servico_rdo in servicos_rdo:
            if servico_rdo.servico:
                servicos_dados.append({
                    'id': servico_rdo.servico.id,
                    'nome': servico_rdo.servico.nome,
                    'percentual': servico_rdo.percentual_executado or 0,
                    'subatividades': [
                        {
                            'id': sa.id,
                            'nome': sa.nome,
                            'percentual': servico_rdo.percentual_executado or 0
                        } for sa in servico_rdo.servico.subatividades if hasattr(servico_rdo.servico, 'subatividades')
                    ]
                })
        
        # Buscar funcionários do último RDO
        funcionarios_rdo = RDOMaoObra.query.filter_by(rdo_id=ultimo_rdo.id).all()
        funcionarios_dados = []
        
        for func_rdo in funcionarios_rdo:
            if func_rdo.funcionario:
                funcionarios_dados.append({
                    'id': func_rdo.funcionario.id,
                    'nome': func_rdo.funcionario.nome,
                    'funcao': func_rdo.funcionario.funcao.nome if func_rdo.funcionario.funcao else 'Não informado',
                    'horas_trabalhadas': float(func_rdo.horas_trabalhadas) if func_rdo.horas_trabalhadas else 8.0
                })
        
        resultado = {
            'success': True,
            'ultimo_rdo': {
                'id': ultimo_rdo.id,
                'numero_rdo': ultimo_rdo.numero_rdo,
                'data_relatorio': ultimo_rdo.data_relatorio.strftime('%Y-%m-%d'),
                'servicos': servicos_dados,
                'funcionarios': funcionarios_dados,
                'total_servicos': len(servicos_dados),
                'total_funcionarios': len(funcionarios_dados)
            }
        }
        
        print(f"✅ ÚLTIMO RDO ENCONTRADO: {ultimo_rdo.numero_rdo} com {len(servicos_dados)} serviços e {len(funcionarios_dados)} funcionários")
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ ERRO API ÚLTIMO RDO: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'ultimo_rdo': None
        }), 500

def carregar_dados_rdo(rdo):
    """Carrega dados do RDO para edição"""
    dados = {
        'obra_id': rdo.obra_id,
        'data_relatorio': rdo.data_relatorio.isoformat(),
        'clima_geral': rdo.clima_geral,
        'condicoes_trabalho': rdo.condicoes_trabalho,
        'comentario_geral': rdo.comentario_geral,
        'equipe': {},
        'subatividades': {}
    }
    
    # Carregar equipe
    for mao_obra in rdo.mao_obra:
        dados['equipe'][str(mao_obra.funcionario_id)] = {
            'horas': mao_obra.horas_trabalhadas,
            'funcao': mao_obra.funcao
        }
    
    # Carregar subatividades
    for sub_ativ in rdo.servico_subatividades:
        dados['subatividades'][str(sub_ativ.subatividade_id)] = {
            'percentual': sub_ativ.percentual,
            'observacoes': sub_ativ.observacoes or ''
        }
    
    return dados

@rdo_bp.route('/rdo/salvar', methods=['POST'])
def salvar_rdo():
    """Salva ou atualiza RDO - VERSÃO OTIMIZADA"""
    admin_id = obter_admin_id()
    
    try:
        # Obter dados do formulário
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
            rdo.numero_rdo = gerar_numero_rdo()
            rdo.criado_por_id = admin_id
            rdo.admin_id = admin_id
        
        # Atualizar dados básicos
        data_relatorio = dados.get('data_relatorio')
        if data_relatorio:
            rdo.data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
        rdo.obra_id = int(dados.get('obra_id')) if dados.get('obra_id') else None
        rdo.clima_geral = dados.get('clima_geral', '')
        rdo.condicoes_trabalho = dados.get('condicoes_trabalho', '')
        rdo.comentario_geral = dados.get('comentario_geral', '')
        rdo.status = dados.get('status', 'Rascunho')
        
        # Salvar RDO primeiro
        if not rdo_id:
            db.session.add(rdo)
        db.session.commit()
        
        # Processar equipe (mão de obra)
        processar_equipe_rdo(rdo, dados)
        
        # Processar subatividades
        processar_subatividades_rdo(rdo, dados)
        
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

def processar_equipe_rdo(rdo, dados):
    """Processa dados da equipe (mão de obra) do RDO"""
    # Limpar registros anteriores em modo edição
    if rdo.id:
        RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
    
    # Processar funcionários
    for key, value in dados.items():
        if key.startswith('funcionario_') and key.endswith('_horas'):
            funcionario_id = key.replace('funcionario_', '').replace('_horas', '')
            horas = float(value) if value else 0
            
            if horas > 0:
                funcao = dados.get(f'funcionario_{funcionario_id}_funcao', 'Funcionário')
                
                mao_obra = RDOMaoObra()
                mao_obra.rdo_id = rdo.id
                mao_obra.funcionario_id = int(funcionario_id)
                mao_obra.funcao = funcao
                mao_obra.horas_trabalhadas = horas
                db.session.add(mao_obra)

def processar_subatividades_rdo(rdo, dados):
    """Processa dados das subatividades do RDO"""
    # Limpar registros anteriores em modo edição
    if rdo.id:
        RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
    
    # Processar subatividades
    for key, value in dados.items():
        if key.startswith('subatividade_') and key.endswith('_percentual'):
            subatividade_id = key.replace('subatividade_', '').replace('_percentual', '')
            percentual = float(value) if value else 0
            
            if percentual > 0:
                observacoes = dados.get(f'subatividade_{subatividade_id}_observacoes', '')
                
                # Obter serviço da subatividade
                subatividade = SubAtividade.query.get(int(subatividade_id))
                
                registro = RDOServicoSubatividade()
                registro.rdo_id = rdo.id
                registro.subatividade_id = int(subatividade_id)
                registro.servico_id = subatividade.servico_id if subatividade else None
                registro.percentual = percentual
                registro.observacoes = observacoes
                db.session.add(registro)

# ================================
# API ENDPOINTS
# ================================

@rdo_bp.route('/api/obra/<int:obra_id>/servicos')
def api_servicos_obra(obra_id):
    """API para carregar serviços de uma obra"""
    admin_id = obter_admin_id()
    
    obra = obter_dados_obra(obra_id, admin_id)
    if not obra:
        return jsonify({'error': 'Obra não encontrada'})
    
    servicos = obter_servicos_obra(obra_id, admin_id)
    
    resultado = []
    for servico in servicos:
        servico_data = {
            'id': servico.id,
            'nome': servico.nome,
            'categoria': servico.categoria,
            'subatividades': []
        }
        
        for subatividade in servico.subatividades:
            if subatividade.ativo:
                servico_data['subatividades'].append({
                    'id': subatividade.id,
                    'nome': subatividade.nome,
                    'descricao': subatividade.descricao,
                    'ordem_execucao': subatividade.ordem_execucao
                })
        
        resultado.append(servico_data)
    
    return jsonify({'servicos': resultado})

@rdo_bp.route('/api/obra/<int:obra_id>/ultimo-rdo')
def api_ultimo_rdo_obra(obra_id):
    """API para carregar percentuais do último RDO"""
    admin_id = obter_admin_id()
    
    ultimo_rdo = obter_ultimo_rdo_obra(obra_id, date.today(), admin_id)
    
    if not ultimo_rdo:
        return jsonify({'atividades': [], 'origem': 'Nenhum RDO anterior encontrado'})
    
    atividades = []
    for atividade in ultimo_rdo.atividades:
        atividades.append({
            'descricao': atividade.descricao_atividade,
            'percentual': atividade.percentual_conclusao
        })
    
    return jsonify({
        'atividades': atividades,
        'origem': f'RDO anterior: {ultimo_rdo.numero_rdo} ({ultimo_rdo.data_relatorio.strftime("%d/%m/%Y")})'
    })

# ================================
# LISTAGEM E VISUALIZAÇÃO
# ================================

@rdo_bp.route('/rdos')
def listar_rdos():
    """Lista todos os RDOs do admin"""
    admin_id = obter_admin_id()
    
    rdos = RDO.query.filter_by(admin_id=admin_id).order_by(RDO.data_relatorio.desc()).all()
    
    return render_template('funcionario/lista_rdos.html', rdos=rdos)

@rdo_bp.route('/rdo/<int:rdo_id>/visualizar')
def visualizar_rdo(rdo_id):
    """Visualiza RDO completo"""
    admin_id = obter_admin_id()
    
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        flash('RDO não encontrado', 'error')
        return redirect(url_for('rdo_optimized.listar_rdos'))
    
    return render_template('funcionario/visualizar_rdo.html', rdo=rdo)

@rdo_bp.route('/rdo/<int:rdo_id>/deletar', methods=['POST'])
def deletar_rdo(rdo_id):
    """Deleta RDO"""
    admin_id = obter_admin_id()
    
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'success': False, 'message': 'RDO não encontrado'})
    
    try:
        db.session.delete(rdo)
        db.session.commit()
        return jsonify({'success': True, 'message': 'RDO deletado com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao deletar: {str(e)}'})