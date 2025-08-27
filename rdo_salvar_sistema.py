# SISTEMA DE SALVAMENTO RDO COMPATÍVEL COM SCHEMA ATUAL
# Corrige problema de campos incompatíveis entre modelo e database

from flask import Blueprint, request, jsonify, redirect, url_for, flash, render_template
from models import db, RDO, RDOMaoObra, RDOServicoSubatividade, Obra, Funcionario, SubAtividade
from bypass_auth import obter_admin_id, obter_funcionario_atual
from datetime import datetime, date
from sqlalchemy import desc, and_
import logging

rdo_salvar_bp = Blueprint('rdo_salvar', __name__)
logger = logging.getLogger(__name__)

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

@rdo_salvar_bp.route('/funcionario-rdo-consolidado', methods=['GET', 'POST'])
def funcionario_rdo_consolidado():
    """Rota principal do RDO consolidado - GET para mostrar formulário, POST para salvar"""
    admin_id = obter_admin_id()
    
    if request.method == 'POST':
        # Processar salvamento
        return processar_salvamento_rdo()
    
    # GET - Mostrar formulário
    try:
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
        
        logger.debug(f"Carregando RDO: {len(obras)} obras, {len(funcionarios)} funcionários")
        
        return render_template('funcionario/rdo_consolidado.html',
                             obras=obras,
                             funcionarios=funcionarios,
                             modo_edicao=False,
                             dados_salvos={})
        
    except Exception as e:
        logger.error(f"Erro ao carregar formulário RDO: {str(e)}")
        flash('Erro ao carregar formulário RDO', 'error')
        return redirect(url_for('main.funcionario_dashboard'))

def processar_salvamento_rdo():
    """Processa salvamento do RDO usando schema compatível"""
    admin_id = obter_admin_id()
    
    try:
        dados = request.form.to_dict()
        logger.debug(f"Dados recebidos para salvamento: {list(dados.keys())}")
        
        # Verificar se é finalização ou rascunho
        finalizar = dados.get('finalizar_rdo') == 'true'
        status = 'Finalizado' if finalizar else 'Rascunho'
        
        # Criar novo RDO
        rdo = RDO()
        rdo.numero_rdo = gerar_numero_rdo_unico()
        rdo.admin_id = admin_id
        rdo.criado_por_id = obter_funcionario_atual()
        
        # Dados básicos
        if dados.get('data_relatorio'):
            rdo.data_relatorio = datetime.strptime(dados.get('data_relatorio'), '%Y-%m-%d').date()
        else:
            rdo.data_relatorio = date.today()
            
        rdo.obra_id = int(dados.get('obra_id')) if dados.get('obra_id') else None
        rdo.clima_geral = dados.get('clima_geral', '')
        rdo.condicoes_trabalho = dados.get('condicoes_trabalho', '')
        rdo.comentario_geral = dados.get('observacoes', '')  # Campo do form é 'observacoes'
        rdo.status = status
        
        # Salvar RDO primeiro para obter ID
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID sem commit completo
        
        logger.debug(f"RDO criado com ID: {rdo.id}, número: {rdo.numero_rdo}")
        
        # Processar equipe (compatível com schema atual)
        processar_equipe_schema_atual(rdo, dados)
        
        # Processar subatividades (compatível com schema atual)
        processar_subatividades_schema_atual(rdo, dados)
        
        # Commit final
        db.session.commit()
        
        if finalizar:
            flash(f'RDO {rdo.numero_rdo} finalizado com sucesso!', 'success')
        else:
            flash(f'RDO {rdo.numero_rdo} salvo como rascunho!', 'info')
        
        return redirect(url_for('main.funcionario_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar RDO: {str(e)}")
        flash(f'Erro ao salvar RDO: {str(e)}', 'error')
        return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))

def processar_equipe_schema_atual(rdo, dados):
    """Processa equipe usando schema atual (funcao_exercida)"""
    funcionarios_processados = 0
    
    for key, value in dados.items():
        if key.startswith('funcionario_') and key.endswith('_horas'):
            funcionario_id = key.replace('funcionario_', '').replace('_horas', '')
            
            try:
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
                    funcionarios_processados += 1
                    
                    logger.debug(f"Funcionário adicionado: ID={funcionario_id}, horas={horas}, função={funcao}")
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Erro ao processar funcionário {funcionario_id}: {e}")
                continue
    
    logger.debug(f"Total de funcionários processados: {funcionarios_processados}")

def processar_subatividades_schema_atual(rdo, dados):
    """Processa subatividades usando schema atual (sem subatividade_id)"""
    subatividades_processadas = 0
    
    for key, value in dados.items():
        if key.startswith('subatividade_') and key.endswith('_percentual'):
            subatividade_id = key.replace('subatividade_', '').replace('_percentual', '')
            
            try:
                percentual = float(value) if value else 0
                
                if percentual > 0:
                    # Obter dados da subatividade
                    subatividade = SubAtividade.query.get(int(subatividade_id))
                    
                    if subatividade:
                        # Usar schema atual - sem campo subatividade_id
                        registro = RDOServicoSubatividade()
                        registro.rdo_id = rdo.id
                        registro.servico_id = subatividade.servico_id
                        registro.nome_subatividade = subatividade.nome
                        registro.percentual_conclusao = percentual  # Campo correto do schema
                        registro.observacoes_tecnicas = ''  # Sem observações específicas
                        registro.admin_id = rdo.admin_id
                        
                        db.session.add(registro)
                        subatividades_processadas += 1
                        
                        logger.debug(f"Subatividade adicionada: {subatividade.nome} = {percentual}%")
                    else:
                        logger.warning(f"Subatividade ID={subatividade_id} não encontrada")
                        
            except (ValueError, TypeError) as e:
                logger.warning(f"Erro ao processar subatividade {subatividade_id}: {e}")
                continue
    
    logger.debug(f"Total de subatividades processadas: {subatividades_processadas}")

@rdo_salvar_bp.route('/api/rdo/salvar-rapido', methods=['POST'])
def salvar_rdo_rapido():
    """API endpoint para salvamento rápido via AJAX"""
    admin_id = obter_admin_id()
    
    try:
        dados = request.get_json()
        
        # Criar RDO simples
        rdo = RDO()
        rdo.numero_rdo = gerar_numero_rdo_unico()
        rdo.admin_id = admin_id
        rdo.criado_por_id = obter_funcionario_atual()
        rdo.data_relatorio = date.today()
        rdo.obra_id = dados.get('obra_id')
        rdo.status = 'Rascunho'
        
        db.session.add(rdo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'RDO salvo com sucesso',
            'rdo_id': rdo.id,
            'numero_rdo': rdo.numero_rdo
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar RDO rápido: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@rdo_salvar_bp.route('/funcionario-rdo-novo')
def funcionario_rdo_novo():
    """Redireciona para o formulário consolidado"""
    return redirect(url_for('rdo_salvar.funcionario_rdo_consolidado'))

@rdo_salvar_bp.route('/rdos')
def listar_rdos():
    """Lista RDOs do funcionário"""
    admin_id = obter_admin_id()
    
    try:
        rdos = RDO.query.filter_by(admin_id=admin_id).order_by(desc(RDO.data_relatorio)).all()
        return render_template('funcionario/lista_rdos.html', rdos=rdos)
        
    except Exception as e:
        logger.error(f"Erro ao listar RDOs: {str(e)}")
        flash('Erro ao carregar RDOs', 'error')
        return redirect(url_for('main.funcionario_dashboard'))

# Endpoint para teste
@rdo_salvar_bp.route('/rdo/teste-salvamento')
def teste_salvamento():
    """Endpoint para testar o sistema de salvamento"""
    admin_id = obter_admin_id()
    
    try:
        # Dados de teste
        dados_teste = {
            'data_relatorio': date.today().strftime('%Y-%m-%d'),
            'obra_id': '1',
            'clima_geral': 'Ensolarado',
            'condicoes_trabalho': 'Normais',
            'observacoes': 'Teste de salvamento automático',
            'funcionario_96_horas': '8',
            'funcionario_96_funcao': 'Engenheiro',
            'subatividade_1_percentual': '50'
        }
        
        # Simular request.form
        from werkzeug.datastructures import ImmutableMultiDict
        request.form = ImmutableMultiDict(dados_teste)
        
        resultado = processar_salvamento_rdo()
        
        return jsonify({
            'success': True,
            'message': 'Teste de salvamento executado',
            'admin_id': admin_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__
        })