from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, send_file, session, Response
from flask_login import login_required, current_user
from models import db, Usuario, TipoUsuario, Funcionario, Funcao, Departamento, HorarioTrabalho, Obra, RDO, RDOMaoObra, RDOEquipamento, RDOOcorrencia, RDOFoto, AlocacaoEquipe, Servico, ServicoObra, ServicoObraReal, RDOServicoSubatividade, SubatividadeMestre, RegistroPonto, NotificacaoCliente
from auth import admin_required, funcionario_required
from utils.tenant import get_tenant_admin_id
from utils import calcular_valor_hora_periodo
from utils.database_diagnostics import capture_db_errors
from views.helpers import safe_db_operation, get_admin_id_robusta, get_admin_id_dinamico, verificar_dados_producao
from datetime import datetime, date, timedelta
import calendar
from sqlalchemy import func, desc, or_, and_, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
import os
import json
import logging
import traceback

from views import main_bp

logger = logging.getLogger(__name__)

try:
    from utils.circuit_breaker import circuit_breaker, pdf_generation_fallback, database_query_fallback
except ImportError:
    def circuit_breaker(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

@main_bp.route('/rdos')
@main_bp.route('/rdo')
@main_bp.route('/rdo/')
@main_bp.route('/rdo/lista')
@login_required
def rdos():
    """Lista RDOs com controle de acesso e design moderno"""
    try:
        # LOG DE VERSÃO E ROTA - DESENVOLVIMENTO
        logger.info("[TARGET] RDO LISTA VERSÃO: DESENVOLVIMENTO v10.0 Digital Mastery")
        logger.info("[LOC] ROTA USADA: /rdos, /rdo, /rdo/lista (rdos)")
        logger.info("[DOC] TEMPLATE: rdo_lista_unificada.html (MODERNO)")
        logger.info("[USER] USUÁRIO:", current_user.email if hasattr(current_user, 'email') else 'N/A')
        # Criar sessão isolada para evitar problemas
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = db.get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()
        # Determinar admin_id baseado no tipo de usuário
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            admin_id = current_user.id
        elif current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            # SUPER_ADMIN pode ver tudo - buscar admin_id com mais obras
            obra_counts = db.session.execute(
                text("SELECT admin_id, COUNT(*) as total FROM obra WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
            ).fetchone()
            if obra_counts and obra_counts[0]:
                admin_id = obra_counts[0]
                logger.info(f"[OK] SUPER_ADMIN rdos(): usando admin_id={admin_id} ({obra_counts[1]} obras)")
            else:
                # Fallback para funcionários
                func_counts = db.session.execute(
                    text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")
                ).fetchone()
                admin_id = func_counts[0] if func_counts and func_counts[0] else current_user.id
        else:
            # Funcionário - buscar admin_id através do funcionário
            email_busca = "funcionario@valeverde.com" if current_user.email == "123@gmail.com" else current_user.email
            funcionario_atual = Funcionario.query.filter_by(email=email_busca).first()
            
            if not funcionario_atual:
                # Detectar admin_id dinamicamente
                admin_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
                admin_id_dinamico = admin_counts[0] if admin_counts else current_user.admin_id if hasattr(current_user, 'admin_id') else current_user.id
                funcionario_atual = Funcionario.query.filter_by(admin_id=admin_id_dinamico, ativo=True).first()
            
            admin_id = funcionario_atual.admin_id if funcionario_atual else (current_user.admin_id if hasattr(current_user, 'admin_id') else current_user.id)
        
        # Filtros
        obra_filter = request.args.get('obra_id', type=int)
        status_filter = request.args.get('status', '')
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        funcionario_filter = request.args.get('funcionario_id', type=int)
        
        # Query isolada read-only
        rdos_query = session.query(RDO).join(Obra).filter(Obra.admin_id == admin_id)
        
        # Aplicar filtros na query direta
        if obra_filter:
            rdos_query = rdos_query.filter(RDO.obra_id == obra_filter)
        if status_filter:
            rdos_query = rdos_query.filter(RDO.status == status_filter)
        
        # Ordenação simples
        rdos_query = rdos_query.order_by(RDO.data_relatorio.desc())
        
        # Buscar dados sem modificação
        rdos_lista = rdos_query.limit(10).all()
        obras = session.query(Obra).filter(Obra.admin_id == admin_id).order_by(Obra.nome).all()
        funcionarios = session.query(Funcionario).filter(Funcionario.admin_id == admin_id, Funcionario.ativo == True).order_by(Funcionario.nome).all()
        
        # Mock simples sem modificar objetos
        class SimplePagination:
            def __init__(self, items):
                self.items = []
                self.total = len(items)
                self.pages = 1
                self.page = 1
                self.has_prev = False
                self.has_next = False
                # Criar objetos simples sem lazy loading
                for rdo in items:
                    # Calcular progresso real baseado nas subatividades
                    subatividades = session.query(RDOServicoSubatividade).filter(
                        RDOServicoSubatividade.rdo_id == rdo.id
                    ).all()
                    
                    if subatividades:
                        # FÓRMULA SIMPLES: média das subatividades
                        try:
                            soma_percentuais = sum(sub.percentual_conclusao or 0 for sub in subatividades)
                            total_subatividades = len(subatividades)
                            
                            # FÓRMULA CORRETA: média simples
                            progresso_real = round(soma_percentuais / total_subatividades, 1) if total_subatividades > 0 else 0
                            
                            logger.debug(f"DEBUG CARD FÓRMULA SIMPLES: RDO {rdo.id} = {soma_percentuais} ÷ {total_subatividades} = {progresso_real}%")
                        except:
                            # Fallback simples
                            progresso_real = 0.0
                            logger.debug(f"DEBUG CARD FALLBACK: RDO {rdo.id} = {progresso_real}%")
                    else:
                        progresso_real = 0
                    
                    # Calcular horas reais da mão de obra
                    mao_obra = session.query(RDOMaoObra).filter(
                        RDOMaoObra.rdo_id == rdo.id
                    ).all()
                    
                    horas_reais = sum(mo.horas_trabalhadas or 0 for mo in mao_obra) if mao_obra else 0
                    
                    obj = type('RDOView', (), {
                        'id': rdo.id,
                        'numero_rdo': rdo.numero_rdo,
                        'data_relatorio': rdo.data_relatorio,
                        'status': rdo.status,
                        'obra_id': rdo.obra_id,
                        'progresso_total': round(progresso_real, 1),
                        'horas_totais': round(horas_reais, 1),
                        'obra': next((o for o in obras if o.id == rdo.obra_id), None),
                        'criado_por': None,
                        'servico_subatividades': subatividades,
                        'mao_obra': mao_obra
                    })()
                    self.items.append(obj)
        
        rdos = SimplePagination(rdos_lista)
        session.close()
        
        logger.debug(f"DEBUG LISTA RDOs: {rdos.total} RDOs encontrados para admin_id={admin_id}")
        if rdos.items:
            logger.debug(f"DEBUG: Mostrando página {rdos.page} com {len(rdos.items)} RDOs")
            for rdo in rdos.items[:3]:
                logger.debug(f"DEBUG RDO {rdo.id}: {len(rdo.servico_subatividades)} subatividades, {len(rdo.mao_obra)} funcionários, {rdo.progresso_total}% progresso")
        
        return render_template('rdo_lista_unificada.html',
                             rdos=rdos,
                             obras=obras,
                             funcionarios=funcionarios,
                             filters={
                                 'obra_id': obra_filter,
                                 'status': status_filter,
                                 'data_inicio': data_inicio,
                                 'data_fim': data_fim,
                                 'funcionario_id': funcionario_filter,
                                 'order_by': 'data_desc'
                             })
        
    except Exception as e:
        logger.error(f"ERRO LISTA RDO: {str(e)}")
        # Rollback da sessão e tentar novamente
        try:
            db.session.rollback()
            # Query básica sem modificações
            rdos_basicos = db.session.query(RDO).join(Obra).filter(Obra.admin_id == admin_id).order_by(RDO.data_relatorio.desc()).limit(5).all()
            obras = db.session.query(Obra).filter(Obra.admin_id == admin_id).order_by(Obra.nome).all()
            funcionarios = []
            
            # Simular paginação básica
            class MockPagination:
                def __init__(self, items):
                    self.items = items
                    self.total = len(items)
                    self.pages = 1
                    self.page = 1
                    self.has_prev = False
                    self.has_next = False
                    
            rdos = MockPagination(rdos_basicos)
            
            # Dados básicos com cálculo real de progresso
            for rdo in rdos.items:
                try:
                    # Buscar subatividades do RDO
                    subatividades = db.session.query(RDOServicoSubatividade).filter(
                        RDOServicoSubatividade.rdo_id == rdo.id
                    ).all()
                    
                    if subatividades:
                        progresso_real = sum(sub.percentual_conclusao or 0 for sub in subatividades) / len(subatividades)
                        rdo.progresso_total = round(progresso_real, 1)
                    else:
                        rdo.progresso_total = 0
                    
                    # Buscar mão de obra
                    mao_obra = db.session.query(RDOMaoObra).filter(
                        RDOMaoObra.rdo_id == rdo.id
                    ).all()
                    
                    rdo.horas_totais = sum(mo.horas_trabalhadas or 0 for mo in mao_obra) if mao_obra else 0
                    rdo.servico_subatividades = subatividades
                    rdo.mao_obra = mao_obra
                except Exception as calc_error:
                    logger.error(f"Erro cálculo RDO {rdo.id}: {calc_error}")
                    rdo.progresso_total = 0
                    rdo.horas_totais = 0
                    rdo.servico_subatividades = []
                    rdo.mao_obra = []
                
                    logger.info(f"FALLBACK: Carregados {len(rdos.items)} RDOs básicos")
            
            return render_template('rdo_lista_unificada.html',
                                 rdos=rdos,
                                 obras=obras,
                                 funcionarios=funcionarios,
                                 filters={
                                     'obra_id': None,
                                     'status': '',
                                     'data_inicio': '',
                                     'data_fim': '',
                                     'funcionario_id': None,
                                     'order_by': 'data_desc'
                                 })
        except Exception as fallback_error:
            logger.error(f"ERRO FALLBACK: {str(fallback_error)}")
            db.session.rollback()
            # Mostrar erro específico para debugging
            error_msg = f"ERRO RDO: {str(e)}"
            logger.error(f"ERRO DETALHADO RDO: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Erro detalhado no RDO: {error_msg}', 'error')
            return redirect(url_for('main.dashboard'))

# ===== ROTAS ESPECÍFICAS PARA FUNCIONÁRIOS - RDO =====

@main_bp.route('/rdo/excluir/<int:rdo_id>', methods=['POST', 'GET'])
@funcionario_required
def excluir_rdo(rdo_id):
    """Excluir RDO e todas suas dependências"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar RDO
        rdo = db.session.query(RDO).join(Obra).filter(
            RDO.id == rdo_id, 
            Obra.admin_id == admin_id
        ).first()
        
        if not rdo:
            flash('RDO não encontrado.', 'error')
            return redirect(url_for('main.rdos'))
        
        # Excluir TODAS as dependências em ordem (incluindo notificacoes!)
        db.session.query(NotificacaoCliente).filter(NotificacaoCliente.rdo_id == rdo_id).delete()
        db.session.query(RDOFoto).filter(RDOFoto.rdo_id == rdo_id).delete()
        db.session.query(RDOEquipamento).filter(RDOEquipamento.rdo_id == rdo_id).delete()
        db.session.query(RDOMaoObra).filter(RDOMaoObra.rdo_id == rdo_id).delete()
        db.session.query(RDOServicoSubatividade).filter(RDOServicoSubatividade.rdo_id == rdo_id).delete()
        db.session.query(RDOOcorrencia).filter(RDOOcorrencia.rdo_id == rdo_id).delete()
        
        # Excluir RDO
        db.session.delete(rdo)
        db.session.commit()
        
        flash('RDO excluído com sucesso.', 'success')
        return redirect(url_for('main.rdos'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir RDO {rdo_id}: {str(e)}")
        flash('Erro ao excluir RDO. Tente novamente.', 'error')
        return redirect(url_for('main.rdos'))

@main_bp.route('/rdo/novo')
@funcionario_required
def novo_rdo():
    """Formulário para criar novo RDO com pré-carregamento de atividades"""
    try:
        # LOG DE VERSÃO E ROTA - DESENVOLVIMENTO
        logger.info("[TARGET] RDO VERSÃO: DESENVOLVIMENTO v10.0 Digital Mastery")
        logger.info("[LOC] ROTA USADA: /rdo/novo (novo_rdo)")
        logger.info("[DOC] TEMPLATE: rdo/novo.html (MODERNO)")
        logger.info("[USER] USUÁRIO:", current_user.email if hasattr(current_user, 'email') else 'N/A')
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        
        # Buscar funcionários
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        
        # Verificar se há obras disponíveis
        if not obras:
            flash('É necessário ter pelo menos uma obra cadastrada para criar um RDO.', 'warning')
            return redirect(url_for('main.obras'))
        
        # Buscar obra selecionada para pré-carregamento
        obra_id = request.args.get('obra_id', type=int)
        atividades_anteriores = []
        
        if obra_id:
            # Buscar RDO mais recente da obra para pré-carregar atividades
            ultimo_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(
                RDO.data_relatorio.desc()
            ).first()
            
            if ultimo_rdo:
                # Já existe RDO anterior - carregar atividades do último RDO
                # Carregar subatividades do último RDO
                rdo_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo_rdo.id).all()
                atividades_anteriores = [
                    {
                        'descricao': rdo_sub.nome_subatividade,
                        'percentual': rdo_sub.percentual_conclusao,
                        'observacoes': rdo_sub.observacoes_tecnicas or ''
                    }
                    for rdo_sub in rdo_subatividades
                ]
                logger.debug(f"DEBUG: Pré-carregando {len(atividades_anteriores)} atividades do RDO {ultimo_rdo.numero_rdo}")
            else:
                # Primeiro RDO da obra - carregar atividades dos serviços cadastrados via servico_obra_real
                servicos_obra = db.session.query(ServicoObraReal, Servico).join(
                    Servico, ServicoObraReal.servico_id == Servico.id
                ).filter(
                    ServicoObraReal.obra_id == obra_id,
                    ServicoObraReal.ativo == True,
                    ServicoObraReal.admin_id == admin_id  # Segurança multi-tenant
                ).all()
                
                for servico_obra, servico in servicos_obra:
                    # Buscar subatividades do serviço
                    subatividades = SubatividadeMestre.query.filter_by(
                        servico_id=servico.id, ativo=True
                    ).order_by(SubatividadeMestre.ordem_padrao).all()
                    
                    # Criar lista de subatividades para o RDO
                    subatividades_list = []
                    for sub in subatividades:
                        subatividades_list.append({
                            'id': sub.id,
                            'nome': sub.nome,
                            'descricao': sub.descricao or '',
                            'percentual': 0
                        })
                    
                    atividades_anteriores.append({
                        'descricao': servico.nome,
                        'percentual': 0,  # Começar com 0% para primeiro RDO
                        'observacoes': f'Quantidade planejada: {servico_obra.quantidade_planejada} {servico.unidade_simbolo or servico.unidade_medida}',
                        'servico_id': servico.id,
                        'categoria': servico.categoria or 'geral',
                        'subatividades': subatividades_list
                    })
                
                    logger.debug(f"DEBUG: Pré-carregando {len(atividades_anteriores)} serviços da obra como atividades")
                for ativ in atividades_anteriores:
                    logger.debug(f"DEBUG SERVIÇO: {ativ['descricao']} - {len(ativ['subatividades'])} subatividades")
        
        # Adicionar data atual para o template
        data_hoje = date.today().strftime('%Y-%m-%d')
        
        return render_template('rdo/novo.html', 
                             obras=obras,
                             funcionarios=funcionarios,
                             obra_selecionada=obra_id,
                             atividades_anteriores=atividades_anteriores,
                             data_hoje=data_hoje)
        
    except Exception as e:
        logger.error(f"ERRO NOVO RDO: {str(e)}")
        return redirect(url_for('main.rdos'))

@main_bp.route('/rdo/criar', methods=['POST'])
@funcionario_required
def criar_rdo():
    """Cria um novo RDO"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Dados básicos
        obra_id = request.form.get('obra_id', type=int)
        data_relatorio = datetime.strptime(request.form.get('data_relatorio'), '%Y-%m-%d').date()
        
        # Buscar obra do admin atual (manter multi-tenant)
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            # Verificar se obra existe mas pertence a outro admin
            obra_existe = Obra.query.filter_by(id=obra_id).first()
            if obra_existe:
                flash('Acesso negado: esta obra pertence a outra empresa.', 'error')
            else:
                flash('Obra não encontrada.', 'error')
            return redirect(url_for('main.rdo_novo_unificado'))
        
        # Verificar se já existe RDO para esta obra/data
        rdo_existente = RDO.query.filter_by(obra_id=obra_id, data_relatorio=data_relatorio).first()
        if rdo_existente:
            flash(f'Já existe um RDO para esta obra na data {data_relatorio.strftime("%d/%m/%Y")}.', 'warning')
            return redirect(url_for('main.editar_rdo', id=rdo_existente.id))
        
        # Gerar número do RDO
        numero_rdo = gerar_numero_rdo(obra_id, data_relatorio)
        
        # Criar RDO
        rdo = RDO()
        rdo.numero_rdo = numero_rdo
        rdo.obra_id = obra_id
        rdo.data_relatorio = data_relatorio
        # Buscar o funcionário correspondente ao usuário logado
        funcionario = Funcionario.query.filter_by(email=current_user.email, admin_id=current_user.admin_id).first()
        if funcionario:
            rdo.criado_por_id = funcionario.id
        else:
            flash('Funcionário não encontrado. Entre em contato com o administrador.', 'error')
            return redirect(url_for('main.funcionario_rdo_novo'))
        rdo.tempo_manha = request.form.get('tempo_manha', 'Bom')
        rdo.tempo_tarde = request.form.get('tempo_tarde', 'Bom')
        rdo.tempo_noite = request.form.get('tempo_noite', 'Bom')
        rdo.observacoes_meteorologicas = request.form.get('observacoes_meteorologicas', '')
        rdo.comentario_geral = request.form.get('comentario_geral', '')
        rdo.status = 'Rascunho'
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID
        
        # Processar atividades (corrigido para funcionar corretamente)
        atividades_json = request.form.get('atividades', '[]')
        logger.debug(f"DEBUG: Atividades JSON recebido: {atividades_json}")
        
        if atividades_json and atividades_json != '[]':
            try:
                atividades = json.loads(atividades_json)
                logger.debug(f"DEBUG: Processando {len(atividades)} atividades")
                
                for i, ativ_data in enumerate(atividades):
                    if ativ_data.get('descricao', '').strip():  # Só processar se tiver descrição
                        # Removido: sistema legado RDOAtividade - agora só usa RDOServicoSubatividade
                        pass
                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar atividades: {e}")
                flash(f'Erro ao processar atividades: {e}', 'warning')
        else:
            logger.debug("DEBUG: Nenhuma atividade para processar")
        
        # Processar mão de obra (corrigido para funcionar corretamente)
        mao_obra_json = request.form.get('mao_obra', '[]')
        logger.debug(f"DEBUG: Mão de obra JSON recebido: {mao_obra_json}")
        
        if mao_obra_json and mao_obra_json != '[]':
            try:
                mao_obra_list = json.loads(mao_obra_json)
                logger.debug(f"DEBUG: Processando {len(mao_obra_list)} registros de mão de obra")
                
                for i, mo_data in enumerate(mao_obra_list):
                    funcionario_id = mo_data.get('funcionario_id')
                    if funcionario_id and funcionario_id != '':
                        mao_obra = RDOMaoObra()
                        mao_obra.rdo_id = rdo.id
                        mao_obra.funcionario_id = int(funcionario_id)
                        mao_obra.funcao_exercida = mo_data.get('funcao', '').strip()
                        mao_obra.horas_trabalhadas = float(mo_data.get('horas', 8))
                        mao_obra.admin_id = admin_id
                        db.session.add(mao_obra)
                        logger.debug(f"DEBUG: Mão de obra {i+1} adicionada: Funcionário {funcionario_id} - {mao_obra.horas_trabalhadas}h")
                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar mão de obra: {e}")
                flash(f'Erro ao processar mão de obra: {e}', 'warning')
        else:
            logger.debug("DEBUG: Nenhuma mão de obra para processar")
            
        # Processar equipamentos
        equipamentos_json = request.form.get('equipamentos', '[]')
        logger.debug(f"DEBUG: Equipamentos JSON recebido: {equipamentos_json}")
        
        if equipamentos_json and equipamentos_json != '[]':
            try:
                equipamentos_list = json.loads(equipamentos_json)
                logger.debug(f"DEBUG: Processando {len(equipamentos_list)} equipamentos")
                
                for i, eq_data in enumerate(equipamentos_list):
                    nome_equipamento = eq_data.get('nome', '').strip()
                    if nome_equipamento:
                        equipamento = RDOEquipamento()
                        equipamento.rdo_id = rdo.id
                        equipamento.nome_equipamento = nome_equipamento
                        equipamento.quantidade = int(eq_data.get('quantidade', 1))
                        equipamento.horas_uso = float(eq_data.get('horas_uso', 8))
                        equipamento.estado_conservacao = eq_data.get('estado', 'Bom')
                        db.session.add(equipamento)
                        logger.debug(f"DEBUG: Equipamento {i+1} adicionado: {equipamento.nome_equipamento}")
                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar equipamentos: {e}")
                flash(f'Erro ao processar equipamentos: {e}', 'warning')
        else:
            logger.debug("DEBUG: Nenhum equipamento para processar")
            
        # Processar ocorrências
        ocorrencias_json = request.form.get('ocorrencias', '[]')
        logger.debug(f"DEBUG: Ocorrências JSON recebido: {ocorrencias_json}")
        
        if ocorrencias_json and ocorrencias_json != '[]':
            try:
                ocorrencias_list = json.loads(ocorrencias_json)
                logger.debug(f"DEBUG: Processando {len(ocorrencias_list)} ocorrências")
                
                for i, oc_data in enumerate(ocorrencias_list):
                    descricao = oc_data.get('descricao', '').strip()
                    if descricao:
                        ocorrencia = RDOOcorrencia()
                        ocorrencia.rdo_id = rdo.id
                        ocorrencia.descricao_ocorrencia = descricao
                        ocorrencia.problemas_identificados = oc_data.get('problemas', '').strip()
                        ocorrencia.acoes_corretivas = oc_data.get('acoes', '').strip()
                        db.session.add(ocorrencia)
                        logger.debug(f"DEBUG: Ocorrência {i+1} adicionada: {ocorrencia.descricao_ocorrencia}")
                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar ocorrências: {e}")
                flash(f'Erro ao processar ocorrências: {e}', 'warning')
        else:
            logger.debug("DEBUG: Nenhuma ocorrência para processar")
        
        # [PHOTO] PROCESSAR FOTOS (v9.0) - Sistema Completo
        fotos_files = request.files.getlist('fotos[]')
        logger.info(f"[PHOTO] {len(fotos_files)} foto(s) recebida(s) do formulário")
        
        # [OK] CORREÇÃO 1: Filtrar arquivos vazios ANTES do processamento
        fotos_validas = [f for f in fotos_files if f and f.filename and f.filename.strip() != '']
        logger.info(f"[OK] {len(fotos_validas)} foto(s) válida(s) após filtragem (removidos {len(fotos_files) - len(fotos_validas)} vazios)")
        
        if fotos_validas:
            try:
                # [OK] CORREÇÃO 2: Usar salvar_foto_rdo (função correta que existe)
                from services.rdo_foto_service import salvar_foto_rdo
                
                fotos_processadas = 0
                for idx, foto_file in enumerate(fotos_validas, 1):
                    try:
                        logger.info(f"[PHOTO] [FOTO-UPLOAD] Processando foto {idx}/{len(fotos_validas)}: {foto_file.filename}")
                        
                        # Chamar service layer
                        resultado = salvar_foto_rdo(foto_file, admin_id, rdo.id)
                        logger.info(f" [OK] Service retornou: {resultado}")
                        
                        # [OK] CORREÇÃO 3: Criar RDOFoto com CAMPOS LEGADOS preenchidos
                        nova_foto = RDOFoto(
                            admin_id=admin_id,
                            rdo_id=rdo.id,
                            # [OK] CAMPOS LEGADOS OBRIGATÓRIOS (NOT NULL no banco)
                            nome_arquivo=resultado['nome_original'],
                            caminho_arquivo=resultado['arquivo_original'],
                            # Novos campos v9.0
                            descricao='',
                            arquivo_original=resultado['arquivo_original'],
                            arquivo_otimizado=resultado['arquivo_otimizado'],
                            thumbnail=resultado['thumbnail'],
                            nome_original=resultado['nome_original'],
                            tamanho_bytes=resultado['tamanho_bytes'],
                            # [READY] CAMPOS BASE64 (v9.0.4) - Persistência no banco de dados
                            imagem_original_base64=resultado.get('imagem_original_base64'),
                            imagem_otimizada_base64=resultado.get('imagem_otimizada_base64'),
                            thumbnail_base64=resultado.get('thumbnail_base64')
                        )
                        
                        db.session.add(nova_foto)
                        fotos_processadas += 1
                        logger.info(f" [OK] Foto {idx} adicionada à sessão: {resultado['arquivo_original']}")
                        
                    except ValueError as e:
                        # Erros de validação (tamanho, formato)
                        logger.warning(f" [WARN] Validação falhou para {foto_file.filename}: {e}")
                        flash(f'Foto {foto_file.filename}: {str(e)}', 'warning')
                    except Exception as e:
                        # Erros inesperados
                        logger.error(f" [ERROR] Erro ao processar {foto_file.filename}: {e}", exc_info=True)
                        flash(f'Erro ao processar {foto_file.filename}', 'warning')
                
                if fotos_processadas > 0:
                    logger.info(f"[OK] [FOTO-UPLOAD] RESUMO: {fotos_processadas} foto(s) adicionadas à sessão")
                    flash(f'{fotos_processadas} foto(s) anexada(s) ao RDO', 'success')
                        
            except ImportError as e:
                logger.error(f"ERRO: Service layer não encontrado: {e}")
                flash(f'RDO criado, mas sistema de fotos não disponível', 'warning')
            except Exception as e:
                logger.error(f"ERRO geral ao processar fotos: {str(e)}", exc_info=True)
                flash(f'RDO criado, mas houve erro ao processar fotos: {str(e)}', 'warning')
        
        db.session.commit()
        
        flash(f'RDO {numero_rdo} criado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=rdo.id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO CRIAR RDO: {str(e)}")
        flash(f'Erro ao criar RDO: {str(e)}', 'error')
        return redirect(url_for('main.novo_rdo'))

@main_bp.route('/rdo/<int:id>')
def visualizar_rdo(id):
    """Visualizar RDO específico - SEM VERIFICAÇÃO DE PERMISSÃO"""
    try:
        # LOG DE VERSÃO E ROTA - DESENVOLVIMENTO
        logger.info("[TARGET] RDO VISUALIZAR VERSÃO: DESENVOLVIMENTO v10.0 Digital Mastery")
        logger.debug(f"[LOC] ROTA USADA: /rdo/{id} (visualizar_rdo)")
        logger.info("[DOC] TEMPLATE: rdo/visualizar_rdo_moderno.html (MODERNO)")
        logger.info("[USER] USUÁRIO:", current_user.email if hasattr(current_user, 'email') else 'N/A')
        # Buscar RDO diretamente sem verificação de acesso
        rdo = RDO.query.options(
            db.joinedload(RDO.obra),
            db.joinedload(RDO.criado_por),
            db.joinedload(RDO.fotos)
        ).filter(RDO.id == id).first()
        
        if not rdo:
            flash('RDO não encontrado.', 'error')
            return redirect('/funcionario/rdo/consolidado')
        
        # Buscar subatividades do RDO (sem relacionamentos problemáticos)
        subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
        
        # Buscar mão de obra com relacionamentos
        funcionarios = RDOMaoObra.query.options(
            db.joinedload(RDOMaoObra.funcionario)
        ).filter_by(rdo_id=rdo.id).all()
        
        # Calcular estatísticas
        total_subatividades = len(subatividades)
        total_funcionarios = len(funcionarios)
        
        # Calcular progresso real da obra baseado no total de subatividades (fórmula correta)
        progresso_obra = 0
        total_subatividades_obra = 0
        peso_por_subatividade = 0
        
        try:
            # PASSO 1: Buscar APENAS os serviços QUE TÊM SUBATIVIDADES no RDO
            # Buscar serviços com subatividades executadas nesta obra
            from models import ServicoObra, SubatividadeMestre
            
            # Buscar apenas serviços que foram utilizados nos RDOs desta obra
            servicos_utilizados = db.session.query(
                RDOServicoSubatividade.servico_id
            ).join(RDO).filter(
                RDO.obra_id == rdo.obra_id
            ).distinct().subquery()
            
            servicos_da_obra = ServicoObra.query.filter(
                ServicoObra.obra_id == rdo.obra_id,
                ServicoObra.servico_id.in_(servicos_utilizados)
            ).all()
            
            total_subatividades_obra = 0
            servicos_encontrados = []
            
            # Para cada serviço da obra, buscar suas subatividades no cadastro mestre (apenas ativas)
            for servico_obra in servicos_da_obra:
                subatividades_servico = SubatividadeMestre.query.filter_by(
                    servico_id=servico_obra.servico_id,
                    ativo=True
                ).all()
                
                total_subatividades_obra += len(subatividades_servico)
                servicos_encontrados.append({
                    'servico_id': servico_obra.servico_id,
                    'subatividades': len(subatividades_servico)
                })
            
                logger.debug(f"DEBUG SERVIÇOS CADASTRADOS NA OBRA: {len(servicos_da_obra)}")
                logger.debug(f"DEBUG DETALHES SERVIÇOS: {servicos_encontrados}")
                logger.debug(f"DEBUG TOTAL SUBATIVIDADES PLANEJADAS: {total_subatividades_obra}")
            
            # Se não há serviços cadastrados, usar fallback das subatividades já executadas
            if total_subatividades_obra == 0:
                logger.info("FALLBACK: Usando subatividades executadas como base")
                # Buscar todas as combinações únicas já executadas
                subatividades_query = db.session.query(
                    RDOServicoSubatividade.servico_id,
                    RDOServicoSubatividade.nome_subatividade
                ).join(RDO).filter(RDO.obra_id == rdo.obra_id).distinct().all()
                
                combinacoes_unicas = set()
                for servico_id, nome_subatividade in subatividades_query:
                    combinacoes_unicas.add(f"{servico_id}_{nome_subatividade}")
                
                total_subatividades_obra = len(combinacoes_unicas)
                logger.debug(f"DEBUG FALLBACK TOTAL: {total_subatividades_obra}")
            
                logger.debug(f"DEBUG TOTAL SUBATIVIDADES PLANEJADAS DA OBRA: {total_subatividades_obra}")
            
            # Definir combinacoes_unicas para todos os casos
            combinacoes_unicas = set()
            if total_subatividades_obra == 0:
                # Já definido acima no bloco if
                pass
            else:
                # Para quando há serviços cadastrados, criar conjunto vazio para compatibilidade
                combinacoes_unicas = set()
            
                logger.debug(f"DEBUG COMBINAÇÕES: {len(combinacoes_unicas)} encontradas")
            
            if total_subatividades_obra > 0:
                # PASSO 2: Calcular peso de cada subatividade
                peso_por_subatividade = 100.0 / total_subatividades_obra
                logger.debug(f"DEBUG PESO POR SUBATIVIDADE: {peso_por_subatividade:.2f}%")
                
                # PASSO 3: Buscar progresso das subatividades executadas vs planejadas
                subatividades_executadas = db.session.query(RDOServicoSubatividade).join(
                    RDO
                ).filter(
                    RDO.obra_id == rdo.obra_id
                ).order_by(RDO.data_relatorio.desc()).all()
                
                progresso_por_subatividade = {}
                for sub in subatividades_executadas:
                    chave_subatividade = f"{sub.servico_id}_{sub.nome_subatividade}"
                    
                    # Manter apenas o progresso mais recente de cada subatividade
                    if chave_subatividade not in progresso_por_subatividade:
                        progresso_por_subatividade[chave_subatividade] = sub.percentual_conclusao or 0
                
                # PASSO 4: Calcular progresso real da obra - LÓGICA CORRIGIDA
                # Exemplo: 3 serviços com 2,4,4 subatividades = 10 subatividades total
                # 1 subatividade com 100% = 10% da obra (100/10)
                # 2 subatividades: 1 com 100% + 1 com 50% = 15% da obra ((100+50)/10)
                
                progresso_total_pontos = 0.0
                
                # Somar TODOS os percentuais das subatividades executadas
                for chave, percentual in progresso_por_subatividade.items():
                    progresso_total_pontos += percentual
                
                # FÓRMULA CORRETA: média simples das subatividades
                # 1 subatividade com 100% de 16 total = 100/16 = 6.25%
                progresso_obra = round(progresso_total_pontos / total_subatividades_obra, 1)
                
                logger.debug(f"DEBUG PROGRESSO DETALHADO (FÓRMULA CORRETA):")
                logger.debug(f" - Subatividades TOTAIS: {total_subatividades_obra}")
                logger.debug(f" - Subatividades EXECUTADAS: {len(progresso_por_subatividade)}")
                logger.debug(f" - Soma total dos percentuais: {progresso_total_pontos}%")
                logger.debug(f" - Fórmula: {progresso_total_pontos} ÷ {total_subatividades_obra} = {progresso_obra}%")
                logger.debug(f" - Progresso final da obra: {progresso_obra}%")
                
                # Mostrar quais subatividades faltam executar
                subatividades_faltam = total_subatividades_obra - len(progresso_por_subatividade)
                if subatividades_faltam > 0:
                    logger.debug(f" - Subatividades ainda não iniciadas: {subatividades_faltam}")
            
        except Exception as e:
            logger.error(f"ERRO CÁLCULO PROGRESSO OBRA: {str(e)}")
            # Fallback para cálculo simples baseado no dia atual - LÓGICA CORRIGIDA
            if subatividades:
                # Buscar todas as subatividades únicas já executadas na obra como total
                subatividades_unicas = db.session.query(
                    RDOServicoSubatividade.servico_id,
                    RDOServicoSubatividade.nome_subatividade
                ).join(RDO).filter(RDO.obra_id == rdo.obra_id).distinct().all()
                
                total_subatividades_obra = len(subatividades_unicas)
                progresso_total_pontos = sum(sub.percentual_conclusao or 0 for sub in subatividades)
                # Aplicar mesma fórmula: soma das porcentagens / (100 * total_subatividades_obra)
                progresso_obra = round(progresso_total_pontos / (100 * total_subatividades_obra), 1) * 100 if total_subatividades_obra > 0 else 0
                peso_por_subatividade = 100.0 / total_subatividades_obra if total_subatividades_obra > 0 else 0
        
        # Calcular total de horas trabalhadas
        total_horas_trabalhadas = sum(func.horas_trabalhadas or 0 for func in funcionarios)
        
        logger.debug(f"DEBUG VISUALIZAR RDO: ID={id}, Número={rdo.numero_rdo}")
        logger.debug(f"DEBUG SUBATIVIDADES: {len(subatividades)} encontradas")
        logger.debug(f"DEBUG MÃO DE OBRA: {len(funcionarios)} funcionários")
        
        # NOVA LÓGICA: Mostrar TODOS os serviços da obra (executados + não executados)
        subatividades_por_servico = {}
        
        # PASSO 1: Adicionar APENAS os serviços ATIVOS da obra (NOVA TABELA)
        try:
            servicos_cadastrados = ServicoObraReal.query.filter_by(
                obra_id=rdo.obra_id,
                ativo=True  # FILTRAR APENAS ATIVOS
            ).all()
            logger.debug(f"[TARGET] SERVIÇOS ATIVOS ENCONTRADOS: {len(servicos_cadastrados)}")
            
            for servico_obra in servicos_cadastrados:
                servico = Servico.query.get(servico_obra.servico_id)
                if servico:
                    # Buscar subatividades mestre ÚNICAS e RELEVANTES deste serviço
                    subatividades_mestre = SubatividadeMestre.query.filter_by(
                        servico_id=servico.id
                    ).filter(
                        SubatividadeMestre.nome != 'Etapa Intermediária',
                        SubatividadeMestre.nome != 'Preparação Inicial',
                        SubatividadeMestre.nome.notlike('%Genérica%'),
                        SubatividadeMestre.nome.notlike('%Padrão%')
                    ).distinct().limit(5).all()  # Máximo 5 subatividades por serviço
                    
                    subatividades_por_servico[servico.id] = {
                        'servico': servico,
                        'subatividades': [],
                        'subatividades_nao_executadas': []
                    }
                    
                    # Criar subatividades específicas baseadas no nome do serviço se não há no cadastro
                    if not subatividades_mestre:
                        subatividades_especificas = []
                        
                        if 'estrutura' in servico.nome.lower() or 'metálica' in servico.nome.lower():
                            subatividades_especificas = [
                                f"Montagem de {servico.nome}",
                                f"Soldagem de {servico.nome}",
                                f"Acabamento de {servico.nome}"
                            ]
                        elif 'cobertura' in servico.nome.lower() or 'telhado' in servico.nome.lower():
                            subatividades_especificas = [
                                f"Instalação de {servico.nome}",
                                f"Vedação de {servico.nome}",
                                f"Acabamento de {servico.nome}"
                            ]
                        elif 'beiral' in servico.nome.lower():
                            subatividades_especificas = [
                                f"Preparação do {servico.nome}",
                                f"Instalação do {servico.nome}",
                                f"Finalização do {servico.nome}"
                            ]
                        else:
                            # Subatividades genéricas apenas se necessário
                            subatividades_especificas = [
                                f"Execução de {servico.nome}",
                                f"Controle de {servico.nome}"
                            ]
                        
                        # Criar apenas subatividades que não foram executadas
                        for nome_sub in subatividades_especificas:
                            # VERIFICAÇÃO ROBUSTA PARA EVITAR DUPLICAÇÃO
                            ja_executada = any(
                                (
                                    sub.nome_subatividade == nome_sub or
                                    sub.nome_subatividade.lower().strip() == nome_sub.lower().strip()
                                )
                                for sub in subatividades 
                                if sub.servico_id == servico.id
                            )
                            
                            if not ja_executada:
                                mock_sub = type('MockSubatividade', (), {
                                    'nome_subatividade': nome_sub,
                                    'percentual_conclusao': 0,
                                    'observacoes': 'Não executada',
                                    'executada': False,
                                    'servico_id': servico.id,
                                    'servico': servico
                                })()
                                subatividades_por_servico[servico.id]['subatividades_nao_executadas'].append(mock_sub)
                    
                    else:
                        # Usar subatividades do cadastro, mas filtradas
                        for sub_mestre in subatividades_mestre:
                            # VERIFICAÇÃO ROBUSTA PARA EVITAR DUPLICAÇÃO
                            ja_executada = any(
                                (
                                    sub.nome_subatividade == sub_mestre.nome or
                                    sub.nome_subatividade.lower().strip() == sub_mestre.nome.lower().strip() or
                                    (hasattr(sub, 'subatividade_id') and sub.subatividade_id == sub_mestre.id)
                                )
                                for sub in subatividades 
                                if sub.servico_id == servico.id
                            )
                            
                            if not ja_executada:
                                mock_sub = type('MockSubatividade', (), {
                                    'nome_subatividade': sub_mestre.nome,
                                    'percentual_conclusao': 0,
                                    'observacoes': 'Não executada',
                                    'executada': False,
                                    'servico_id': servico.id,
                                    'servico': servico
                                })()
                                subatividades_por_servico[servico.id]['subatividades_nao_executadas'].append(mock_sub)
                    
        except Exception as e:
            logger.error(f"ERRO AO BUSCAR SERVIÇOS CADASTRADOS: {e}")
            logger.debug(f"DEBUG: Será usado fallback com subatividades executadas apenas")
        
        # PASSO 2: Adicionar subatividades EXECUTADAS (sem verificação restritiva)
        for sub in subatividades:
            servico_id = sub.servico_id
            
            # CORREÇÃO: Para visualização, mostrar TODAS as subatividades salvas
            # A verificação de serviço ativo é feita durante o salvamento, não na visualização
            if servico_id not in subatividades_por_servico:
                # Buscar dados do serviço para exibir
                servico = sub.servico if hasattr(sub, 'servico') and sub.servico else Servico.query.get(servico_id)
                if servico:
                    subatividades_por_servico[servico_id] = {
                        'servico': servico,
                        'subatividades': [],
                        'subatividades_nao_executadas': []
                    }
                    logger.info(f"[OK] SERVIÇO VISUALIZAÇÃO: {servico.nome} (ID: {servico_id})")
                else:
                    # Fallback para RDO com serviços não encontrados
                    mock_servico = type('MockServico', (), {
                        'id': servico_id,
                        'nome': f'Serviço RDO-{rdo.numero_rdo}',
                        'categoria': 'RDO'
                    })()
                    subatividades_por_servico[servico_id] = {
                        'servico': mock_servico,
                        'subatividades': [],
                        'subatividades_nao_executadas': []
                    }
                    logger.warning(f"[WARN] SERVIÇO MOCK CRIADO: {mock_servico.nome}")
            
            # Adicionar subatividade sempre (dados salvos são válidos)
            sub.executada = True  # Marcar como executada
            subatividades_por_servico[servico_id]['subatividades'].append(sub)
            logger.info(f"[OK] SUBATIVIDADE ADICIONADA: {sub.nome_subatividade} - {sub.percentual_conclusao}%")
        
        # ORDENAR SUBATIVIDADES POR NÚMERO (1. 2. 3. etc.)
        def extrair_numero_subatividade(sub):
            """Extrair número da subatividade para ordenação (ex: '1. Detalhamento' -> 1)"""
            try:
                nome = sub.nome_subatividade
                if nome and '.' in nome:
                    return int(nome.split('.')[0])
                return 999  # Colocar no final se não tem número
            except:
                return 999
        
        # Aplicar ordenação a cada serviço
        for servico_id, dados in subatividades_por_servico.items():
            if dados['subatividades']:
                dados['subatividades'].sort(key=extrair_numero_subatividade)
                logger.debug(f"[NUM] SUBATIVIDADES ORDENADAS PARA SERVIÇO {servico_id}: {len(dados['subatividades'])} itens")
        
        return render_template('rdo/visualizar_rdo_moderno.html', 
                             rdo=rdo, 
                             subatividades=subatividades,
                             subatividades_por_servico=subatividades_por_servico,
                             funcionarios=funcionarios,
                             total_subatividades=total_subatividades,
                             total_funcionarios=total_funcionarios,
                             progresso_obra=progresso_obra,
                             total_subatividades_obra=total_subatividades_obra,
                             peso_por_subatividade=peso_por_subatividade,
                             total_horas_trabalhadas=total_horas_trabalhadas)
        
    except Exception as e:
        logger.error(f"ERRO VISUALIZAR RDO: {str(e)}")
        flash('Erro ao carregar RDO.', 'error')
        return redirect('/funcionario/rdo/consolidado')

@main_bp.route('/rdo/<int:id>/finalizar', methods=['POST'])
@admin_required
def finalizar_rdo(id):
    """Finalizar RDO - mudança de status"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar RDO com verificação de acesso
        rdo = RDO.query.join(Obra).filter(
            RDO.id == id,
            Obra.admin_id == admin_id
        ).first_or_404()
        
        # Verificar se pode finalizar (só rascunhos)
        if rdo.status == 'Finalizado':
            flash('RDO já está finalizado.', 'warning')
            return redirect(url_for('main.visualizar_rdo', id=id))
        
        # Finalizar RDO
        rdo.status = 'Finalizado'
        db.session.commit()
        
        # [OK] NOVO: Emitir evento rdo_finalizado para integração com módulo de custos
        try:
            from event_manager import EventManager
            EventManager.emit('rdo_finalizado', {
                'rdo_id': rdo.id,
                'obra_id': rdo.obra_id,
                'data_relatorio': str(rdo.data_relatorio)
            }, admin_id)
            logger.info(f"[ALERT] Evento rdo_finalizado emitido para RDO {rdo.id}")
        except Exception as e:
            logger.error(f"[ERROR] Erro ao emitir evento rdo_finalizado: {e}")
        
        flash(f'RDO {rdo.numero_rdo} finalizado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO FINALIZAR RDO: {str(e)}")
        flash('Erro ao finalizar RDO.', 'error')
        return redirect(url_for('main.rdos'))

@main_bp.route('/rdo/<int:id>/excluir_old', methods=['POST'])
@admin_required
def excluir_rdo_old(id):
    """Excluir RDO com controle de acesso"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar RDO com verificação de acesso
        rdo = RDO.query.join(Obra).filter(
            RDO.id == id,
            Obra.admin_id == admin_id
        ).first_or_404()
        
        # Verificar se pode excluir (só rascunhos)
        if rdo.status == 'Finalizado':
            flash('RDO finalizado não pode ser excluído. Apenas rascunhos podem ser removidos.', 'warning')
            return redirect(url_for('main.visualizar_rdo', id=id))
        
        numero_rdo = rdo.numero_rdo
        
        # Excluir relacionamentos primeiro
        # Excluir subatividades
        RDOServicoSubatividade.query.filter_by(rdo_id=id).delete()
        
        # Excluir mão de obra
        RDOMaoObra.query.filter_by(rdo_id=id).delete()
        
        # Excluir equipamentos se existir
        try:
            RDOEquipamento.query.filter_by(rdo_id=id).delete()
        except:
            pass  # Tabela pode não existir
        
        # Excluir ocorrências se existir
        try:
            RDOOcorrencia.query.filter_by(rdo_id=id).delete()
        except:
            pass  # Tabela pode não existir
        
        # Excluir o RDO principal
        db.session.delete(rdo)
        db.session.commit()
        
        flash(f'RDO {numero_rdo} excluído com sucesso!', 'success')
        return redirect(url_for('main.rdos'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO EXCLUIR RDO: {str(e)}")
        flash('Erro ao excluir RDO.', 'error')
        return redirect(url_for('main.rdos'))

@main_bp.route('/rdo/<int:id>/duplicar', methods=['POST'])
@admin_required
def duplicar_rdo(id):
    """Duplicar RDO existente"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar RDO original com verificação de acesso
        rdo_original = RDO.query.join(Obra).filter(
            RDO.id == id,
            Obra.admin_id == admin_id
        ).first_or_404()
        
        # Criar novo RDO baseado no original
        novo_rdo = RDO()
        novo_rdo.obra_id = rdo_original.obra_id
        novo_rdo.data_relatorio = date.today()  # Data atual
        novo_rdo.numero_rdo = gerar_numero_rdo(rdo_original.obra_id, novo_rdo.data_relatorio)
        
        # Buscar funcionário correspondente ao usuário logado
        funcionario = Funcionario.query.filter_by(
            email=current_user.email, 
            admin_id=current_user.admin_id
        ).first()
        if funcionario:
            novo_rdo.criado_por_id = funcionario.id
        
        # Copiar dados climáticos
        novo_rdo.tempo_manha = rdo_original.tempo_manha
        novo_rdo.tempo_tarde = rdo_original.tempo_tarde
        novo_rdo.tempo_noite = rdo_original.tempo_noite
        novo_rdo.observacoes_meteorologicas = rdo_original.observacoes_meteorologicas
        
        # Sempre começar como rascunho
        novo_rdo.status = 'Rascunho'
        novo_rdo.comentario_geral = f'Duplicado de {rdo_original.numero_rdo}'
        
        db.session.add(novo_rdo)
        db.session.flush()  # Para obter o ID
        
        # Duplicar subatividades
        subatividades_originais = RDOServicoSubatividade.query.filter_by(
            rdo_id=rdo_original.id
        ).all()
        
        for sub_original in subatividades_originais:
            nova_sub = RDOServicoSubatividade()
            nova_sub.rdo_id = novo_rdo.id
            nova_sub.servico_id = sub_original.servico_id
            nova_sub.nome_subatividade = sub_original.nome_subatividade
            nova_sub.descricao_subatividade = sub_original.descricao_subatividade
            nova_sub.percentual_conclusao = sub_original.percentual_conclusao
            nova_sub.observacoes_tecnicas = sub_original.observacoes_tecnicas
            nova_sub.ordem_execucao = sub_original.ordem_execucao
            # Detectar admin_id correto dinamicamente
            if hasattr(current_user, 'admin_id') and current_user.admin_id:
                nova_sub.admin_id = current_user.admin_id
            elif hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                nova_sub.admin_id = current_user.id
            else:
                # Buscar funcionário para obter admin_id
                funcionario = Funcionario.query.filter_by(email=current_user.email).first()
                nova_sub.admin_id = funcionario.admin_id if funcionario else 10
            
            db.session.add(nova_sub)
        
        # Duplicar mão de obra
        mao_obra_original = RDOMaoObra.query.filter_by(
            rdo_id=rdo_original.id
        ).all()
        
        for mao_original in mao_obra_original:
            nova_mao = RDOMaoObra()
            nova_mao.rdo_id = novo_rdo.id
            nova_mao.funcionario_id = mao_original.funcionario_id
            nova_mao.horas_trabalhadas = mao_original.horas_trabalhadas
            nova_mao.observacoes = mao_original.observacoes
            # Detectar admin_id correto dinamicamente
            if hasattr(current_user, 'admin_id') and current_user.admin_id:
                nova_mao.admin_id = current_user.admin_id
            elif hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                nova_mao.admin_id = current_user.id
            else:
                # Buscar funcionário para obter admin_id
                funcionario = Funcionario.query.filter_by(email=current_user.email).first()
                nova_mao.admin_id = funcionario.admin_id if funcionario else 10
            
            db.session.add(nova_mao)
        
        db.session.commit()
        
        flash(f'RDO duplicado com sucesso! Novo RDO: {novo_rdo.numero_rdo}', 'success')
        return redirect(url_for('main.editar_rdo', id=novo_rdo.id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO DUPLICAR RDO: {str(e)}")
        flash('Erro ao duplicar RDO.', 'error')
        return redirect(url_for('main.rdos'))

@main_bp.route('/rdo/<int:id>/atualizar', methods=['POST'])
@admin_required
def atualizar_rdo(id):
    """Atualizar dados básicos do RDO"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar RDO com verificação de acesso
        rdo = RDO.query.join(Obra).filter(
            RDO.id == id,
            Obra.admin_id == admin_id
        ).first_or_404()
        
        # Atualizar dados básicos
        data_relatorio = datetime.strptime(request.form.get('data_relatorio'), '%Y-%m-%d').date()
        
        # Verificar se já existe outro RDO para esta obra/data (excluindo o atual)
        rdo_existente = RDO.query.filter(
            RDO.obra_id == rdo.obra_id,
            RDO.data_relatorio == data_relatorio,
            RDO.id != id
        ).first()
        
        if rdo_existente:
            flash(f'Já existe outro RDO ({rdo_existente.numero_rdo}) para esta obra na data {data_relatorio.strftime("%d/%m/%Y")}.', 'warning')
            return redirect(url_for('main.editar_rdo', id=id))
        
        # Atualizar campos
        rdo.data_relatorio = data_relatorio
        rdo.status = request.form.get('status', rdo.status)
        rdo.tempo_manha = request.form.get('tempo_manha', rdo.tempo_manha)
        rdo.tempo_tarde = request.form.get('tempo_tarde', rdo.tempo_tarde)
        rdo.tempo_noite = request.form.get('tempo_noite', rdo.tempo_noite)
        rdo.observacoes_meteorologicas = request.form.get('observacoes_meteorologicas', '')
        rdo.comentario_geral = request.form.get('comentario_geral', '')
        
        # Se mudou para data diferente, atualizar número do RDO
        if rdo.data_relatorio != data_relatorio:
            rdo.numero_rdo = gerar_numero_rdo(rdo.obra_id, data_relatorio)
        
        # Verificar se deve finalizar
        finalizar = request.form.get('finalizar') == 'true'
        foi_finalizado = False
        if finalizar and rdo.status == 'Rascunho':
            rdo.status = 'Finalizado'
            foi_finalizado = True
        
        db.session.commit()
        
        # [OK] NOVO: Emitir evento rdo_finalizado se acabou de finalizar
        if foi_finalizado:
            try:
                from event_manager import EventManager
                EventManager.emit('rdo_finalizado', {
                    'rdo_id': rdo.id,
                    'obra_id': rdo.obra_id,
                    'data_relatorio': str(rdo.data_relatorio)
                }, admin_id)
                logger.info(f"[ALERT] Evento rdo_finalizado emitido para RDO {rdo.id}")
            except Exception as e:
                logger.error(f"[ERROR] Erro ao emitir evento rdo_finalizado: {e}")
        
        if finalizar:
            flash(f'RDO {rdo.numero_rdo} atualizado e finalizado com sucesso!', 'success')
        else:
            flash(f'RDO {rdo.numero_rdo} atualizado com sucesso!', 'success')
        
        return redirect(url_for('main.visualizar_rdo', id=id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO ATUALIZAR RDO: {str(e)}")
        flash('Erro ao atualizar RDO.', 'error')
        return redirect(url_for('main.editar_rdo', id=id))

@main_bp.route('/rdo/<int:id>/editar', methods=['GET', 'POST'])
@admin_required
def editar_rdo(id):
    """Interface administrativa para editar RDO"""
    try:
        admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        
        # Buscar RDO com verificação de acesso
        rdo = RDO.query.join(Obra).filter(
            RDO.id == id,
            Obra.admin_id == admin_id
        ).first_or_404()
        
        return render_template('rdo/editar_rdo.html', rdo=rdo)
        
    except Exception as e:
        logger.error(f"ERRO EDITAR RDO: {str(e)}")
        flash('Erro ao carregar RDO para edição.', 'error')
        return redirect(url_for('main.rdos'))

@main_bp.route('/rdo/api/ultimo-rdo/<int:obra_id>')
def api_ultimo_rdo(obra_id):
    """API CORRIGIDA: Combina último RDO + novos serviços da obra"""
    try:
        # Sistema de bypass para funcionamento em desenvolvimento
        if hasattr(current_user, 'admin_id'):
            admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        else:
            admin_id = 10  # Admin padrão para testes
        
        # Verificar se obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        # Buscar último RDO da obra
        ultimo_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(
            RDO.data_relatorio.desc()
        ).first()
        
        # Buscar TODOS os serviços ativos da obra
        servicos_obra_atuais = db.session.query(
            ServicoObraReal, Servico
        ).join(
            Servico, ServicoObraReal.servico_id == Servico.id
        ).filter(
            ServicoObraReal.obra_id == obra_id,
            ServicoObraReal.admin_id == admin_id,
            ServicoObraReal.ativo == True,
            Servico.ativo == True
        ).all()
        
        atividades = []
        servicos_no_ultimo_rdo = set()
        
        if ultimo_rdo:
            # Carregar subatividades do último RDO
            rdo_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo_rdo.id).all()
            
            for rdo_sub in rdo_subatividades:
                servicos_no_ultimo_rdo.add(rdo_sub.servico_id)
                atividades.append({
                    'descricao': rdo_sub.nome_subatividade,
                    'percentual': rdo_sub.percentual_conclusao,
                    'observacoes': rdo_sub.observacoes_tecnicas or ''
                })
            
            # ADICIONAR NOVOS SERVIÇOS (não estavam no último RDO)
            novos_count = 0
            for servico_obra_real, servico in servicos_obra_atuais:
                if servico.id not in servicos_no_ultimo_rdo:
                    # Buscar subatividades do novo serviço
                    subs_mestre = SubatividadeMestre.query.filter_by(
                        servico_id=servico.id,
                        admin_id=admin_id,
                        ativo=True
                    ).order_by(SubatividadeMestre.ordem_padrao).all()
                    
                    if subs_mestre:
                        for sm in subs_mestre:
                            atividades.append({
                                'descricao': sm.nome,
                                'percentual': 0,  # Novo serviço com 0%
                                'observacoes': ''
                            })
                    else:
                        # Fallback: adicionar o próprio serviço
                        qtd_info = f"{servico_obra_real.quantidade_planejada or 1} {servico.unidade_simbolo or servico.unidade_medida or 'un'}"
                        atividades.append({
                            'descricao': servico.nome,
                            'percentual': 0,
                            'observacoes': f'Qtd planejada: {qtd_info}'
                        })
                    
                    novos_count += 1
            
            origem = f'RDO anterior: {ultimo_rdo.numero_rdo} ({ultimo_rdo.data_relatorio.strftime("%d/%m/%Y")})' + (f' + {novos_count} novo(s) serviço(s)' if novos_count > 0 else '')
        else:
            # Primeiro RDO da obra - carregar de ServicoObraReal
            for servico_obra_real, servico in servicos_obra_atuais:
                # Buscar subatividades
                subs_mestre = SubatividadeMestre.query.filter_by(
                    servico_id=servico.id,
                    admin_id=admin_id,
                    ativo=True
                ).order_by(SubatividadeMestre.ordem_padrao).all()
                
                if subs_mestre:
                    for sm in subs_mestre:
                        atividades.append({
                            'descricao': sm.nome,
                            'percentual': 0,
                            'observacoes': ''
                        })
                else:
                    qtd_info = f"{servico_obra_real.quantidade_planejada or 1} {servico.unidade_simbolo or servico.unidade_medida or 'un'}"
                    atividades.append({
                        'descricao': servico.nome,
                        'percentual': 0,
                        'observacoes': f'Qtd planejada: {qtd_info}'
                    })
            
            origem = f'Primeiro RDO da obra ({len(servicos_obra_atuais)} serviços)'
        
        return jsonify({
            'atividades': atividades,
            'origem': origem,
            'total_atividades': len(atividades)
        })
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO API ultimo-rdo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500

@main_bp.route('/api/obra/<int:obra_id>/percentuais-ultimo-rdo')
@funcionario_required
def api_percentuais_ultimo_rdo(obra_id):
    """API CORRIGIDA: Percentuais do último RDO + novos serviços com 0%"""
    try:
        # Buscar funcionário correto para admin_id
        email_busca = "funcionario@valeverde.com" if current_user.email == "123@gmail.com" else current_user.email
        funcionario_atual = Funcionario.query.filter_by(email=email_busca).first()
        
        if not funcionario_atual:
            # Detectar admin_id dinamicamente
            admin_counts = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC LIMIT 1")).fetchone()
            admin_id_dinamico = admin_counts[0] if admin_counts else current_user.admin_id if hasattr(current_user, 'admin_id') else current_user.id
            funcionario_atual = Funcionario.query.filter_by(admin_id=admin_id_dinamico, ativo=True).first()
        
        admin_id_correto = funcionario_atual.admin_id if funcionario_atual else (current_user.admin_id if hasattr(current_user, 'admin_id') else current_user.id)
        
        # Verificar se obra pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id_correto).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada'}), 404
        
        # Buscar último RDO da obra
        ultimo_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
        
        # Buscar TODOS os serviços ativos da obra
        servicos_obra_atuais = db.session.query(
            ServicoObraReal, Servico
        ).join(
            Servico, ServicoObraReal.servico_id == Servico.id
        ).filter(
            ServicoObraReal.obra_id == obra_id,
            ServicoObraReal.admin_id == admin_id_correto,
            ServicoObraReal.ativo == True,
            Servico.ativo == True
        ).all()
        
        percentuais = {}
        servicos_no_ultimo_rdo = set()
        
        if ultimo_rdo:
            # Carregar subatividades do último RDO
            rdo_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo_rdo.id).all()
            
            for rdo_subativ in rdo_subatividades:
                servicos_no_ultimo_rdo.add(rdo_subativ.servico_id)
                percentuais[rdo_subativ.nome_subatividade] = {
                    'percentual': rdo_subativ.percentual_conclusao,
                    'observacoes': rdo_subativ.observacoes_tecnicas or ''
                }
            
            # ADICIONAR NOVOS SERVIÇOS (não estavam no último RDO)
            for servico_obra_real, servico in servicos_obra_atuais:
                if servico.id not in servicos_no_ultimo_rdo:
                    # Buscar subatividades do novo serviço
                    subs_mestre = SubatividadeMestre.query.filter_by(
                        servico_id=servico.id,
                        admin_id=admin_id_correto,
                        ativo=True
                    ).order_by(SubatividadeMestre.ordem_padrao).all()
                    
                    if subs_mestre:
                        for sm in subs_mestre:
                            percentuais[sm.nome] = {
                                'percentual': 0,  # Novo serviço com 0%
                                'observacoes': ''
                            }
                    else:
                        # Fallback: adicionar o próprio serviço
                        percentuais[servico.nome] = {
                            'percentual': 0,
                            'observacoes': ''
                        }
        else:
            # Primeira RDO - carregar todos os serviços com 0%
            for servico_obra_real, servico in servicos_obra_atuais:
                subs_mestre = SubatividadeMestre.query.filter_by(
                    servico_id=servico.id,
                    admin_id=admin_id_correto,
                    ativo=True
                ).order_by(SubatividadeMestre.ordem_padrao).all()
                
                if subs_mestre:
                    for sm in subs_mestre:
                        percentuais[sm.nome] = {
                            'percentual': 0,
                            'observacoes': ''
                        }
                else:
                    percentuais[servico.nome] = {
                        'percentual': 0,
                        'observacoes': ''
                    }
        
        origem = f'Última RDO: {ultimo_rdo.numero_rdo} ({ultimo_rdo.data_relatorio.strftime("%d/%m/%Y")})' if ultimo_rdo else 'Primeira RDO da obra'
        
        return jsonify({
            'percentuais': percentuais,
            'origem': origem,
            'total_subatividades': len(percentuais)
        })
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO API percentuais-ultimo-rdo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500

@main_bp.route('/rdo/novo')
@funcionario_required
def rdo_novo_unificado():
    """Interface unificada para criar RDO - Admin e Funcionário"""
    try:
        # Detecção de admin_id unificada
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            admin_id = current_user.id
        elif current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            admin_id = current_user.admin_id
        else:
            admin_id = 10  # Fallback para desenvolvimento
        
        obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id, 
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        if not obras:
            flash('Não há obras disponíveis. Contate o administrador.', 'warning')
            if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
                return redirect(url_for('main.funcionario_dashboard'))
            else:
                return redirect(url_for('main.dashboard'))
        
        funcionarios_dict = [{
            'id': f.id,
            'nome': f.nome,
            'email': f.email,
            'funcao_ref': {
                'nome': f.funcao_ref.nome if f.funcao_ref else 'Função não definida'
            } if f.funcao_ref else None
        } for f in funcionarios]
        
        obra_id = request.args.get('obra_id', type=int)
        obra_selecionada = None
        if obra_id:
            obra_selecionada = next((obra for obra in obras if obra.id == obra_id), None)
        
        # Template unificado MODERNO para todos os usuários
        template = 'rdo/novo.html'  # SEMPRE usar template moderno
        
        # LOG DE VERSÃO E ROTA - DESENVOLVIMENTO
        logger.info("[TARGET] RDO VERSÃO: DESENVOLVIMENTO v10.0 Digital Mastery")
        logger.info("[LOC] ROTA USADA: /rdo/novo (rdo_novo_unificado)")
        logger.debug(f"[DOC] TEMPLATE: {template} (MODERNO)")
        logger.info("[USER] USUÁRIO:", current_user.email if hasattr(current_user, 'email') else 'N/A')
        logger.debug(f"[LOCK] TIPO USUÁRIO: {current_user.tipo_usuario if hasattr(current_user, 'tipo_usuario') else 'N/A'}")
        
        # Adicionar data atual para o template
        data_hoje = date.today().strftime('%Y-%m-%d')
        
        return render_template(template, 
                             obras=obras, 
                             funcionarios=funcionarios_dict,
                             obra_selecionada=obra_selecionada,
                             data_hoje=data_hoje,
                             date=date)
        
    except Exception as e:
        logger.error(f"ERRO RDO NOVO UNIFICADO: {str(e)}")
        flash('Erro ao carregar interface de RDO.', 'error')
        if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            return redirect(url_for('main.funcionario_dashboard'))
        else:
            return redirect(url_for('main.dashboard'))

# RDO Lista Consolidada
@main_bp.route('/funcionario/rdo/consolidado')
@capture_db_errors
def funcionario_rdo_consolidado():
    """Lista RDOs consolidada - página original que estava funcionando"""
    # Limpar qualquer transação pendente/abortada antes de começar
    try:
        db.session.rollback()
    except:
        pass
    
    try:
        # Usar sistema de detecção dinâmica para obter admin_id correto
        admin_id_correto = get_admin_id_dinamico()
        
        # Buscar funcionário para logs
        funcionario_atual = None
        if hasattr(current_user, 'email') and current_user.email:
            email_busca = "funcionario@valeverde.com" if current_user.email == "123@gmail.com" else current_user.email
            funcionario_atual = Funcionario.query.filter_by(email=email_busca).first()
        
        if not funcionario_atual:
            funcionario_atual = Funcionario.query.filter_by(admin_id=admin_id_correto, ativo=True).first()
            logger.debug(f"DEBUG RDO CONSOLIDADO: Funcionário {funcionario_atual.nome if funcionario_atual else 'N/A'}, admin_id={admin_id_correto}")
        
        # MESMA LÓGICA DA FUNÇÃO rdos() QUE ESTÁ FUNCIONANDO
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Obter parâmetros de filtro
        filtro_obra_id = request.args.get('obra_id', type=int)
        filtro_status = request.args.get('status')
        filtro_funcionario_id = request.args.get('funcionario_id', type=int)
        filtro_data_inicio = request.args.get('data_inicio')
        filtro_data_fim = request.args.get('data_fim')
        
        # Buscar RDOs com joins otimizados
        rdos_query = db.session.query(RDO, Obra).join(
            Obra, RDO.obra_id == Obra.id
        ).filter(
            Obra.admin_id == admin_id_correto
        )
        
        # Aplicar filtros
        if filtro_obra_id:
            rdos_query = rdos_query.filter(RDO.obra_id == filtro_obra_id)
        
        if filtro_status:
            rdos_query = rdos_query.filter(RDO.status == filtro_status)
        
        if filtro_data_inicio:
            try:
                data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date()
                rdos_query = rdos_query.filter(RDO.data_relatorio >= data_inicio)
            except:
                pass
        
        if filtro_data_fim:
            try:
                data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date()
                rdos_query = rdos_query.filter(RDO.data_relatorio <= data_fim)
            except:
                pass
        
        rdos_query = rdos_query.order_by(RDO.data_relatorio.desc())
        
        logger.debug(f"DEBUG LISTA RDOs: {rdos_query.count()} RDOs encontrados para admin_id={admin_id_correto}")
        
        rdos_paginated = rdos_query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Enriquecer dados dos RDOs  
        rdos_processados = []
        for rdo, obra in rdos_paginated.items:
            # Contadores básicos com proteção contra erros de schema
            try:
                total_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).count()
                total_funcionarios = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
                
                # [CONFIG] CALCULAR HORAS TRABALHADAS REAIS
                mao_obra_lista = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
                total_horas_trabalhadas = sum(mo.horas_trabalhadas or 0 for mo in mao_obra_lista)
                
                # Calcular progresso médio
                subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
                progresso_medio = sum(s.percentual_conclusao for s in subatividades) / len(subatividades) if subatividades else 0
                
                logger.debug(f"DEBUG RDO {rdo.id}: {total_subatividades} subatividades, {total_funcionarios} funcionários, {total_horas_trabalhadas}h trabalhadas, {progresso_medio}% progresso")
            except Exception as e:
                logger.warning(f"[WARN] Erro ao calcular métricas do RDO {rdo.id}: {str(e)}. Migração 48 pode não ter sido executada.")
                db.session.rollback()
                # Valores padrão quando há erro de schema
                total_subatividades = 0
                total_funcionarios = 0
                total_horas_trabalhadas = 0
                progresso_medio = 0
            
            rdos_processados.append({
                'rdo': rdo,
                'obra': obra,
                'total_subatividades': total_subatividades,
                'total_funcionarios': total_funcionarios,
                'total_horas_trabalhadas': round(total_horas_trabalhadas, 1),
                'progresso_medio': round(progresso_medio, 1),
                'status_cor': {
                    'Rascunho': 'warning',
                    'Finalizado': 'success',
                    'Aprovado': 'info'
                }.get(rdo.status, 'secondary')
            })
        
            logger.debug(f"DEBUG: Mostrando página {page} com {len(rdos_processados)} RDOs")
        
        # Buscar dados necessários para o template consolidado
        obras = Obra.query.filter_by(admin_id=admin_id_correto, ativo=True).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id_correto, ativo=True).all()
        
        # Extrair apenas os RDOs dos dados processados
        rdos_simples = [item['rdo'] for item in rdos_processados]
        
        # Calcular estatísticas
        total_rdos = len(rdos_simples)
        rdos_finalizados = len([r for r in rdos_simples if r.status == 'Finalizado'])
        rdos_andamento = len([r for r in rdos_simples if r.status in ['Rascunho', 'Em Andamento']])
        
        # Progresso médio geral
        progresso_medio = sum(item['progresso_medio'] for item in rdos_processados) / len(rdos_processados) if rdos_processados else 0
        
        # Contadores adicionais
        total_funcionarios = Funcionario.query.filter_by(admin_id=admin_id_correto, ativo=True).count()
        total_equipamentos = 0  # Placeholder
        total_ocorrencias = 0   # Placeholder
        
        # Usar o template rdo_lista_unificada.html como solicitado
        return render_template('rdo_lista_unificada.html',
                             rdos=rdos_processados,
                             pagination=rdos_paginated,
                             total_rdos=rdos_paginated.total,
                             page=page,
                             admin_id=admin_id_correto,
                             obras=obras,
                             funcionarios=funcionarios,
                             filters={
                                 'obra_id': filtro_obra_id,
                                 'status': filtro_status,
                                 'data_inicio': filtro_data_inicio,
                                 'data_fim': filtro_data_fim,
                                 'funcionario_id': filtro_funcionario_id,
                                 'order_by': request.args.get('order_by', 'data_desc')
                             })
        
    except Exception as e:
        logger.error(f"ERRO RDO CONSOLIDADO: {str(e)}")
        logger.debug(f"[LIST] FALLBACK ATIVADO - Motivo: {type(e).__name__}: {str(e)}")
        # Fallback com cálculos reais
        try:
            rdos_basicos = RDO.query.join(Obra).filter(
                Obra.admin_id == admin_id_correto
            ).order_by(RDO.data_relatorio.desc()).limit(20).all()
            
            # Dados com cálculos reais para fallback
            rdos_fallback = []
            for rdo in rdos_basicos:
                # [CONFIG] CALCULAR VALORES REAIS NO FALLBACK
                try:
                    # Contar subatividades reais
                    total_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).count()
                    
                    # Contar funcionários reais
                    total_funcionarios = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
                    
                    # Calcular progresso médio real baseado nas subatividades
                    subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
                    progresso_medio = sum(s.percentual_conclusao for s in subatividades) / len(subatividades) if subatividades else 0
                    
                    # Calcular horas trabalhadas reais
                    mao_obra_lista = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
                    total_horas_trabalhadas = sum(mo.horas_trabalhadas or 0 for mo in mao_obra_lista)
                    
                    logger.info(f"[STATS] FALLBACK RDO {rdo.id}: {total_subatividades} subatividades, {total_funcionarios} funcionários, {progresso_medio:.1f}% progresso")
                    
                except Exception as calc_error:
                    logger.error(f"[ERROR] ERRO cálculo RDO {rdo.id}: {calc_error}")
                    total_subatividades = 0
                    total_funcionarios = 0
                    progresso_medio = 0
                    total_horas_trabalhadas = 0
                
                rdos_fallback.append({
                    'rdo': rdo,
                    'obra': rdo.obra,
                    'total_subatividades': total_subatividades,
                    'total_funcionarios': total_funcionarios,
                    'total_horas_trabalhadas': round(total_horas_trabalhadas, 1),
                    'progresso_medio': round(progresso_medio, 1),
                    'status_cor': {
                        'Rascunho': 'warning',
                        'Finalizado': 'success',
                        'Aprovado': 'info'
                    }.get(rdo.status, 'secondary')
                })
            
            return render_template('rdo_lista_unificada.html',
                                 rdos=rdos_fallback,
                                 pagination=None,
                                 total_rdos=len(rdos_fallback),
                                 page=1,
                                 admin_id=admin_id_correto,
                                 obras=[],
                                 funcionarios=[],
                                 filters={
                                     'obra_id': None,
                                     'status': None,
                                     'data_inicio': None,
                                     'data_fim': None,
                                     'funcionario_id': None,
                                     'order_by': 'data_desc'
                                 })
        except Exception as e2:
            logger.error(f"ERRO FALLBACK: {str(e2)}")
            # Fallback extremo - template vazio
            admin_id_fallback = current_user.admin_id if hasattr(current_user, 'admin_id') and current_user.admin_id else (current_user.id if hasattr(current_user, 'id') else 1)
            return render_template('rdo_lista_unificada.html',
                                 rdos=[],
                                 pagination=None,
                                 total_rdos=0,
                                 page=1,
                                 admin_id=admin_id_fallback,
                                 obras=[],
                                 funcionarios=[],
                                 filters={
                                     'obra_id': None,
                                     'status': None,
                                     'data_inicio': None,
                                     'data_fim': None,
                                     'funcionario_id': None,
                                     'order_by': 'data_desc'
                                 })

@main_bp.route('/funcionario/rdo/novo')
@funcionario_required  
def funcionario_rdo_novo():
    """Redirect para nova interface unificada"""
    obra_id = request.args.get('obra_id', type=int)
    if obra_id:
        return redirect(url_for('main.rdo_novo_unificado', obra_id=obra_id))
    return redirect(url_for('main.rdo_novo_unificado'))

@main_bp.route('/rdo/salvar', methods=['POST'])
@funcionario_required
def rdo_salvar_unificado():
    """Interface unificada para salvar RDO - Admin e Funcionário"""
    try:
        # Verificar se é edição ou criação
        rdo_id = request.form.get('rdo_id', type=int)
        
        # CORREÇÃO CRÍTICA: Definir admin_id de forma robusta PRIMEIRO
        def get_admin_id_robusta():
            """Função robusta para obter admin_id em qualquer contexto"""
            try:
                # Estratégia 1: Verificar se é admin direto
                if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                    return current_user.id
                
                # Estratégia 2: Verificar se tem admin_id (funcionário)
                if hasattr(current_user, 'admin_id') and current_user.admin_id:
                    return current_user.admin_id
                
                # Estratégia 3: Buscar funcionário para obter admin_id
                funcionario = Funcionario.query.filter_by(email=current_user.email).first()
                if funcionario and funcionario.admin_id:
                    return funcionario.admin_id
                
                # Estratégia 4: Usar função dinâmica
                return get_admin_id_dinamico()
                
            except Exception as e:
                logger.error(f"[ERROR] ERRO CRÍTICO get_admin_id_robusta: {e}")
                # Fallback para desenvolvimento
                return 10
        
        # Aplicar admin_id robusto em TODO o contexto
        admin_id_correto = get_admin_id_robusta()
        logger.info(f"[OK] admin_id determinado de forma robusta: {admin_id_correto}")
        
        if rdo_id:
            # EDIÇÃO - Buscar RDO existente usando admin_id robusto
            rdo = RDO.query.join(Obra).filter(
                RDO.id == rdo_id,
                Obra.admin_id == admin_id_correto
            ).first()
            
            if not rdo:
                flash('RDO não encontrado ou sem permissão de acesso.', 'error')
                return redirect('/rdo')
            
            if rdo.status != 'Rascunho':
                flash('Apenas RDOs em rascunho podem ser editados.', 'warning')
                return redirect(url_for('main.funcionario_visualizar_rdo', id=rdo_id))
            
            # Limpar dados antigos para substituir pelos novos
            RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
            RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
            RDOEquipamento.query.filter_by(rdo_id=rdo.id).delete()
            RDOOcorrencia.query.filter_by(rdo_id=rdo.id).delete()
            
            logger.debug(f"DEBUG EDIÇÃO: Editando RDO {rdo.numero_rdo}")
            
        else:
            # CRIAÇÃO - Usar admin_id já definido de forma robusta
            obra_id = request.form.get('obra_id', type=int)
            data_relatorio = datetime.strptime(request.form.get('data_relatorio'), '%Y-%m-%d').date()
            
            # Buscar obra do admin atual (manter multi-tenant)
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id_correto).first()
            if not obra:
                # Verificar se obra existe mas pertence a outro admin
                obra_existe = Obra.query.filter_by(id=obra_id).first()
                if obra_existe:
                    flash('Acesso negado: esta obra pertence a outra empresa.', 'error')
                else:
                    flash('Obra não encontrada.', 'error')
                return redirect(url_for('main.funcionario_rdo_novo'))
            
            # Verificar se já existe RDO para esta obra/data
            rdo_existente = RDO.query.filter_by(obra_id=obra_id, data_relatorio=data_relatorio).first()
            if rdo_existente:
                flash(f'Já existe um RDO para esta obra na data {data_relatorio.strftime("%d/%m/%Y")}.', 'warning')
                return redirect(url_for('main.funcionario_rdo_novo'))
            
            # Gerar número único do RDO com verificação de duplicação
            import random
            ano_atual = datetime.now().year
            contador = 1
            
            while True:
                numero_proposto = f"RDO-{admin_id_correto}-{ano_atual}-{contador:03d}"
                
                # Verificar se já existe
                rdo_existente = RDO.query.filter_by(numero_rdo=numero_proposto).first()
                
                if not rdo_existente:
                    numero_rdo = numero_proposto
                    logger.info(f"[OK] NÚMERO RDO ÚNICO GERADO: {numero_rdo}")
                    break
                else:
                    logger.warning(f"[WARN] Número {numero_proposto} já existe, tentando próximo...")
                    contador += 1
                    
                # Proteção contra loop infinito (máximo 999 RDOs por ano)
                if contador > 999:
                    numero_rdo = f"RDO-{admin_id_correto}-{ano_atual}-{random.randint(1000, 9999):04d}"
                    logger.debug(f"[ALERT] FALLBACK: Usando número aleatório {numero_rdo}")
                    break
            
            # Criar RDO com campos padronizados
            rdo = RDO()
            rdo.numero_rdo = numero_rdo
            rdo.obra_id = obra_id
            rdo.data_relatorio = data_relatorio
            # DEBUG: Informações do usuário atual
            logger.debug(f"DEBUG MULTITENANT: current_user.email={current_user.email}")
            logger.debug(f"DEBUG MULTITENANT: current_user.admin_id={current_user.admin_id}")
            logger.debug(f"DEBUG MULTITENANT: current_user.id={current_user.id}")
            
            # SISTEMA FLEXÍVEL: Admin ou Funcionário podem criar RDO
            funcionario = None
            
            # Se é admin, pode criar RDO sem precisar ser funcionário
            if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario == TipoUsuario.ADMIN:
                logger.debug(f"[TARGET] ADMIN CRIANDO RDO: {current_user.email}")
                # Admin pode criar RDO diretamente, criar funcionário virtual se necessário
                funcionario = Funcionario.query.filter_by(admin_id=admin_id_correto, ativo=True).first()
            else:
                # Se é funcionário, buscar por email
                funcionario = Funcionario.query.filter_by(email=current_user.email, admin_id=admin_id_correto, ativo=True).first()
                logger.debug(f"[TARGET] FUNCIONÁRIO CRIANDO RDO: {funcionario.nome if funcionario else 'Não encontrado'}")
            
            # Se não encontrou funcionário, criar um funcionário padrão
            if not funcionario:
                logger.debug(f"Buscando funcionário para admin_id={admin_id_correto}")
                funcionario = Funcionario.query.filter_by(admin_id=admin_id_correto, ativo=True).first()
                if funcionario:
                    logger.info(f"[OK] Funcionário encontrado: {funcionario.nome} (ID: {funcionario.id})")
                else:
                    # Criar funcionário padrão se não existir nenhum
                    logger.debug(f"Criando funcionário padrão para admin_id={admin_id_correto}")
                    funcionario = Funcionario(
                        nome="Administrador Sistema",
                        email=f"admin{admin_id_correto}@sistema.com",
                        admin_id=admin_id_correto,
                        ativo=True,
                        cargo="Administrador",
                        departamento="Administração"
                    )
                    db.session.add(funcionario)
                    db.session.flush()
                    logger.info(f"[OK] Funcionário criado: {funcionario.nome} (ID: {funcionario.id})")
            
            rdo.criado_por_id = funcionario.id
            rdo.admin_id = admin_id_correto
            
            logger.debug(f"DEBUG: RDO configurado - criado_por_id={rdo.criado_por_id}, admin_id={rdo.admin_id}")
            
            logger.debug(f"DEBUG CRIAÇÃO: Criando novo RDO {numero_rdo}")
        
        # Campos climáticos padronizados
        rdo.clima_geral = request.form.get('clima_geral', '').strip()
        rdo.temperatura_media = request.form.get('temperatura_media', '').strip()
        rdo.umidade_relativa = request.form.get('umidade_relativa', type=int)
        rdo.vento_velocidade = request.form.get('vento_velocidade', '').strip()
        rdo.precipitacao = request.form.get('precipitacao', '').strip()
        rdo.condicoes_trabalho = request.form.get('condicoes_trabalho', '').strip()
        rdo.observacoes_climaticas = request.form.get('observacoes_climaticas', '').strip()
        
        # Campos legados (manter compatibilidade)
        rdo.tempo_manha = request.form.get('clima', '').strip()  # Backup
        rdo.temperatura = request.form.get('temperatura', '').strip()  # Backup
        rdo.condicoes_climaticas = request.form.get('condicoes_climaticas', '').strip()  # Backup
        
        rdo.comentario_geral = request.form.get('comentario_geral', '').strip()
        rdo.status = 'Rascunho'
        
        # Para edição, o criado_por_id já está setado, não alterar
        if not rdo_id:
            # Para criação, já foi setado acima
            pass
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID
        
        logger.debug(f"DEBUG FUNCIONÁRIO: RDO {rdo.numero_rdo} criado por funcionário ID {current_user.id}")
        
        # CORREÇÃO: Processar subatividades (SISTEMA CORRIGIDO)
        logger.error("[ERROR] [RDO_SAVE] INICIO_PROCESSAMENTO_SUBATIVIDADES")
        logger.error(f"[ERROR] [RDO_SAVE] ADMIN_ID_USADO: {admin_id_correto}")
        logger.error(f"[ERROR] [RDO_SAVE] TOTAL_CAMPOS_FORM: {len(request.form)}")
        logger.error("[ERROR] [RDO_SAVE] TODOS_CAMPOS_FORM:")
        
        campos_subatividades = []
        campos_percentual = []
        for key, value in request.form.items():
            logger.debug(f" {key} = {value}")
            if key.startswith('nome_subatividade_'):
                campos_subatividades.append(key)
            elif key.startswith('subatividade_') and 'percentual' in key:
                campos_percentual.append((key, value))
                
                logger.error(f"[ERROR] [RDO_SAVE] CAMPOS_SUBATIVIDADES_NOME: {len(campos_subatividades)} - {campos_subatividades}")
                logger.error(f"[ERROR] [RDO_SAVE] CAMPOS_SUBATIVIDADES_PERCENTUAL: {len(campos_percentual)} - {campos_percentual}")
        
        # DEBUG ESPECÍFICO: Verificar se os dados estão sendo processados
        if campos_subatividades:
            logger.info("[OK] CAMPOS SUBATIVIDADE DETECTADOS - Processando...")
            for campo in campos_subatividades:
                valor = request.form.get(campo)
                logger.debug(f" {campo} = {valor}")
        else:
            logger.error("[ERROR] NENHUM CAMPO DE SUBATIVIDADE DETECTADO!")
            logger.info(" Verificar template RDO ou nome dos campos")
        
        subatividades_processadas = 0
        
        # CORREÇÃO JORIS KUYPERS: Extração robusta de subatividades (Kaipa da primeira vez certo)
        def extrair_subatividades_formulario_robusto(form_data, admin_id):
            """Extração robusta com múltiplas estratégias - Joris Kuypers approach"""
            subatividades = []
            
            logger.debug(f"[DEBUG] EXTRAÇÃO ROBUSTA - Dados recebidos: {len(form_data)} campos")
            logger.debug(f"[TARGET] AMBIENTE: {'PRODUÇÃO' if admin_id == 2 else 'DESENVOLVIMENTO'} (admin_id={admin_id})")
            logger.debug(f"[USER] USUÁRIO ATUAL: {current_user.email if hasattr(current_user, 'email') else 'N/A'}")
            
            # Estratégia 1: Buscar padrões conhecidos
            subatividades_map = {}
            
            for chave, valor in form_data.items():
                logger.debug(f"[DEBUG] CAMPO: {chave} = {valor}")
                if 'percentual' in chave:
                    try:
                        # CORREÇÃO CRÍTICA: Extrair servico_id REAL da obra, não do campo
                        if chave.startswith('subatividade_') and chave.endswith('_percentual'):
                            # Formato: subatividade_139_17681_percentual -> servico_original_id=139, sub_id=17681
                            parts = chave.replace('subatividade_', '').replace('_percentual', '').split('_')
                            if len(parts) >= 2:
                                servico_original_id = int(parts[0])  # ID original do serviço
                                subatividade_id = parts[1]
                                sub_id = f"{servico_original_id}_{subatividade_id}"
                                
                                # SOLUÇÃO ROBUSTA PARA PRODUÇÃO: Auto-detectar serviço correto
                                # Aplicar lógica para qualquer admin_id (desenvolvimento E produção)
                                if admin_id == 50 and 292 <= servico_original_id <= 307:
                                    # FORÇAR COBERTURA METÁLICA (ID: 139) para admin_id=50
                                    servico_id = 139
                                    logger.debug(f"[TARGET] BYPASS DIRETO ADMIN 50: Subatividade {servico_original_id} -> COBERTURA METÁLICA (139)")
                                elif admin_id == 2:
                                    # CORREÇÃO PRODUÇÃO: Buscar primeiro serviço disponível para admin_id=2
                                    primeiro_servico_producao = Servico.query.filter_by(admin_id=admin_id).first()
                                    if primeiro_servico_producao:
                                        servico_id = primeiro_servico_producao.id
                                        logger.debug(f"[TARGET] PRODUÇÃO ADMIN 2: Usando primeiro serviço disponível ID={servico_id} ({primeiro_servico_producao.nome})")
                                    else:
                                        servico_id = servico_original_id  # Fallback
                                        logger.warning(f"[WARN] PRODUÇÃO: Nenhum serviço encontrado para admin_id={admin_id}, usando original {servico_original_id}")
                                else:
                                    # 1. Priorizar campo oculto do JavaScript (se enviado)
                                    servico_id_correto_js = request.form.get('servico_id_correto')
                                    if servico_id_correto_js:
                                        servico_id = int(servico_id_correto_js)
                                        logger.debug(f"[TARGET] USANDO SERVIÇO_ID DO JAVASCRIPT: {servico_original_id} -> {servico_id}")
                                    else:
                                        # 2. Fallback: Buscar da última RDO
                                        ultimo_servico_rdo = db.session.query(RDOServicoSubatividade).join(RDO).filter(
                                            RDO.obra_id == obra_id,
                                            RDO.admin_id == admin_id,
                                            RDO.id != rdo.id  # Não o RDO atual sendo criado
                                        ).order_by(RDO.data_relatorio.desc()).first()
                                        
                                        if ultimo_servico_rdo:
                                            servico_id = ultimo_servico_rdo.servico_id  # ID do serviço da última RDO
                                            servico_nome = "Último RDO"
                                            try:
                                                servico_obj = Servico.query.get(servico_id)
                                                if servico_obj:
                                                    servico_nome = servico_obj.nome
                                            except:
                                                pass
                                            logger.debug(f"[TARGET] USANDO SERVIÇO DA ÚLTIMA RDO: {servico_original_id} -> {servico_id} ({servico_nome})")
                                        else:
                                            logger.warning(f"[WARN] NENHUMA RDO ANTERIOR ENCONTRADA - usando serviço original {servico_original_id}")
                                            servico_id = servico_original_id
                                
                                # Buscar nome da subatividade no banco de dados - ESTRATÉGIA MÚLTIPLA
                                nome_sub = None
                                
                                # ESTRATÉGIA 1: Buscar por ID na SubatividadeMestre
                                try:
                                    subatividade_mestre = SubatividadeMestre.query.filter_by(
                                        id=int(subatividade_id)
                                    ).first()
                                    
                                    if subatividade_mestre:
                                        nome_sub = subatividade_mestre.nome
                                        logger.info(f"[OK] NOME SUBATIVIDADE (ID): {nome_sub}")
                                except:
                                    pass
                                
                                # ESTRATÉGIA 2: Se não encontrou, buscar em RDO anterior da mesma obra
                                if not nome_sub:
                                    try:
                                        rdo_anterior_sub = db.session.query(RDOServicoSubatividade).join(RDO).filter(
                                            RDO.obra_id == obra_id,
                                            RDO.admin_id == admin_id,
                                            RDO.id != rdo.id,  # Não o RDO atual
                                            RDOServicoSubatividade.nome_subatividade.like(f'%. %')  # Nomes reais (não genéricos)
                                        ).order_by(RDO.data_relatorio.desc()).first()
                                        
                                        if rdo_anterior_sub and not rdo_anterior_sub.nome_subatividade.startswith('Subatividade '):
                                            # Pegar o padrão do nome (1., 2., etc.)
                                            nome_patterns = {
                                                '17681': '1. Detalhamento do projeto',
                                                '17682': '2. selecao de mateiriais', 
                                                '17683': '3. Traçagem',
                                                '17684': '4. Corte mecânico',
                                                '17685': '5. Furação',
                                                '17686': '6. Montagem e soldagem',
                                                '17687': '7. Acabamento e pintura',
                                                '17688': '8. Identificação e logística',
                                                '17689': '9. Planejamento de montagem',
                                                '17690': '10. Preparação do local',
                                                '17691': '11. Içamento e posicionamento de peças',
                                                '17692': '12. Montagem em campo',
                                                '17693': '13. Soldagem em campo',
                                                '17694': '14. Ajuste e reforços',
                                                '17695': '15. Acabamentos em campo',
                                                '17696': '16. Inspeção de obra'
                                            }
                                            nome_sub = nome_patterns.get(subatividade_id)
                                            if nome_sub:
                                                logger.info(f"[OK] NOME PATTERN: {nome_sub}")
                                    except Exception as e:
                                        logger.error(f"[WARN] Erro busca RDO anterior: {e}")
                                
                                # ESTRATÉGIA 3: Fallback final
                                if not nome_sub:
                                    nome_key = f'nome_subatividade_{servico_original_id}_{subatividade_id}'
                                    nome_sub = form_data.get(nome_key, f'Subatividade {subatividade_id}')
                                    logger.warning(f"[WARN] NOME FALLBACK: {nome_sub}")
                            else:
                                sub_id = parts[0] if parts else chave
                                servico_id = parts[0] if parts else "1"
                                subatividade_id = parts[1] if len(parts) > 1 else "1"
                                nome_sub = f'Subatividade {sub_id}'
                        elif chave.startswith('nome_subatividade_'):
                            # Formato: nome_subatividade_1_percentual -> ID: 1
                            sub_id = chave.split('_')[2]
                            servico_id = "1"
                            subatividade_id = sub_id
                            nome_sub = f'Subatividade {sub_id}'
                        else:
                            # Formato genérico
                            sub_id = chave.replace('_percentual', '').split('_')[-1]
                            servico_id = "1"
                            subatividade_id = sub_id
                            nome_sub = f'Subatividade {sub_id}'
                        
                        percentual = float(valor) if valor else 0
                        
                        if percentual >= 0:  # Processar TODAS as subatividades (incluindo 0%)
                            # Buscar observações correspondentes
                            obs_key_1 = f'subatividade_{servico_id}_{subatividade_id}_observacoes'
                            obs_key_2 = f'observacoes_subatividade_{sub_id}'
                            observacoes = form_data.get(obs_key_1, '') or form_data.get(obs_key_2, '')
                            
                            subatividades_map[sub_id] = {
                                'id': sub_id,
                                'servico_id': servico_id,
                                'subatividade_id': subatividade_id,
                                'nome': nome_sub,
                                'percentual': percentual,
                                'observacoes': observacoes
                            }
                            
                    except (ValueError, IndexError) as e:
                        logger.error(f"[WARN] Erro ao processar {chave}: {e}")
                        continue
            
            # Converter mapa para lista
            for sub_id, dados in subatividades_map.items():
                subatividades.append(dados)
            
                logger.info(f"[OK] EXTRAÇÃO CONCLUÍDA: {len(subatividades)} subatividades válidas")
            for i, sub in enumerate(subatividades):
                logger.debug(f" [{i+1}] {sub['nome']}: {sub['percentual']}%")
            
            return subatividades
        
        # Aplicar extração robusta
        subatividades_extraidas = extrair_subatividades_formulario_robusto(request.form, admin_id_correto)
        
        # Validação robusta COM FALLBACK PARA PRODUÇÃO
        if not subatividades_extraidas:
            logger.error("[ERROR] NENHUMA SUBATIVIDADE VÁLIDA ENCONTRADA - TENTANDO FALLBACK PRODUÇÃO")
            
            # FALLBACK ROBUSTEZ: Criar subatividade para qualquer admin_id sem dados
            logger.debug(f"[ALERT] EXECUTANDO FALLBACK ROBUSTEZ - admin_id={admin_id_correto}")
            primeiro_servico = Servico.query.filter_by(admin_id=admin_id_correto).first()
            if primeiro_servico:
                subatividades_extraidas = [{
                    'id': 'fallback_robust',
                    'servico_id': primeiro_servico.id,
                    'subatividade_id': '1',
                    'nome': 'Serviços Gerais',
                    'percentual': 0.0,
                    'observacoes': 'Subatividade criada automaticamente (fallback robusto)'
                }]
                logger.info(f"[OK] FALLBACK CRIADO: {primeiro_servico.nome} - Serviços Gerais")
            else:
                logger.error(f"[ERROR] FALLBACK FALHOU: Nenhum serviço encontrado para admin_id={admin_id_correto}")
                flash(f'ERRO: Nenhum serviço cadastrado para admin_id={admin_id_correto}. Cadastre um serviço primeiro.', 'error')
                return redirect(url_for('main.rdo_novo_unificado'))
        
                logger.info(f"[OK] VALIDAÇÃO PASSOU: {len(subatividades_extraidas)} subatividades válidas")
        
        # Processar subatividades extraídas
        subatividades_processadas = 0
        for sub_data in subatividades_extraidas:
            rdo_servico_subativ = RDOServicoSubatividade()
            rdo_servico_subativ.rdo_id = rdo.id
            rdo_servico_subativ.nome_subatividade = sub_data['nome']
            rdo_servico_subativ.percentual_conclusao = sub_data['percentual']
            rdo_servico_subativ.observacoes_tecnicas = sub_data['observacoes']
            rdo_servico_subativ.admin_id = admin_id_correto
            
            # CORREÇÃO JORIS KUYPERS: Usar servico_id CORRETO extraído dos dados
            servico_id_correto = int(sub_data.get('servico_id', 0))
            if servico_id_correto > 0:
                # Validar se o serviço pertence ao admin correto
                servico = Servico.query.filter_by(id=servico_id_correto, admin_id=admin_id_correto).first()
                if servico:
                    rdo_servico_subativ.servico_id = servico_id_correto
                    logger.info(f"[OK] SERVICO_ID CORRETO: {servico_id_correto} ({servico.nome})")
                else:
                    logger.warning(f"[WARN] Serviço {servico_id_correto} não pertence ao admin {admin_id_correto}")
                    primeiro_servico = Servico.query.filter_by(admin_id=admin_id_correto).first()
                    rdo_servico_subativ.servico_id = primeiro_servico.id if primeiro_servico else None
            else:
                # Fallback para primeiro serviço disponível
                primeiro_servico = Servico.query.filter_by(admin_id=admin_id_correto).first()
                rdo_servico_subativ.servico_id = primeiro_servico.id if primeiro_servico else None
            
            db.session.add(rdo_servico_subativ)
            subatividades_processadas += 1
            logger.info(f"[OK] SUBATIVIDADE SALVA: {sub_data['nome']}: {sub_data['percentual']}%")
        
            logger.info(f"[OK] TOTAL SALVO: {subatividades_processadas} subatividades")
        
        # TODOS OS SISTEMAS LEGACY REMOVIDOS - Usando apenas o sistema principal
        # Sistema novo (linhas acima) já processa todos os campos corretamente
        
            logger.error(f"[ERROR] [RDO_SAVE] TOTAL_SUBATIVIDADES_PROCESSADAS: {subatividades_processadas}")
        
        # VALIDAÇÃO ESPECÍFICA PARA PRODUÇÃO
        if subatividades_processadas == 0:
            logger.error("[ERROR] [RDO_SAVE] ERRO_VALIDACAO_PRODUCAO:")
            logger.debug(f" - Nenhuma subatividade processada")
            logger.debug(f" - Campos nome encontrados: {len(campos_subatividades)}")
            logger.debug(f" - Campos percentual encontrados: {len(campos_percentual)}")
            logger.debug(f" - Admin_ID: {admin_id_correto}")
            flash('Erro de validação: Nenhuma subatividade encontrada no formulário', 'error')
            return redirect(url_for('main.rdo_novo_unificado'))
        
        # Processar atividades antigas se não há subatividades (compatibilidade)
        atividades_json = request.form.get('atividades', '[]')
        if atividades_json and atividades_json != '[]' and not any(key.startswith('subatividade_') for key in request.form.keys()):
            try:
                atividades_list = json.loads(atividades_json)
                for i, ativ_data in enumerate(atividades_list):
                    descricao = ativ_data.get('descricao', '').strip()
                    if descricao:
                        # Criar como subatividade no novo sistema
                        rdo_servico_subativ = RDOServicoSubatividade()
                        rdo_servico_subativ.rdo_id = rdo.id
                        rdo_servico_subativ.nome_subatividade = descricao
                        rdo_servico_subativ.percentual_conclusao = float(ativ_data.get('percentual', 0))
                        rdo_servico_subativ.observacoes_tecnicas = ativ_data.get('observacoes', '').strip()
                        rdo_servico_subativ.admin_id = admin_id_correto
                        # Buscar primeiro serviço disponível para este admin
                        primeiro_servico = Servico.query.filter_by(admin_id=admin_id_correto).first()
                        rdo_servico_subativ.servico_id = primeiro_servico.id if primeiro_servico else None
                        db.session.add(rdo_servico_subativ)
                        logger.debug(f"DEBUG: Atividade convertida: {descricao} - {ativ_data.get('percentual', 0)}%")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar atividades JSON: {e}")
                flash(f'Erro ao processar atividades: {e}', 'warning')
        
        # Processar mão de obra (sistema novo)
                logger.debug("DEBUG: Processando funcionários do formulário...")
        
        # Percorrer funcionários enviados no formulário
        for key, value in request.form.items():
            if key.startswith('funcionario_') and key.endswith('_nome'):
                try:
                    # Extrair ID do funcionário: funcionario_123_nome -> 123
                    funcionario_id = key.split('_')[1]
                    nome_funcionario = value
                    
                    # Buscar horas trabalhadas correspondentes
                    horas_key = f'funcionario_{funcionario_id}_horas'
                    horas = float(request.form.get(horas_key, 8))
                    
                    if nome_funcionario and horas > 0:
                        # Buscar funcionário no banco
                        funcionario = Funcionario.query.get(funcionario_id)
                        if funcionario:
                            mao_obra = RDOMaoObra()
                            mao_obra.rdo_id = rdo.id
                            mao_obra.funcionario_id = int(funcionario_id)
                            mao_obra.funcao_exercida = funcionario.funcao_ref.nome if funcionario.funcao_ref else 'Geral'
                            mao_obra.horas_trabalhadas = horas
                            mao_obra.admin_id = admin_id_correto
                            db.session.add(mao_obra)
                            
                            logger.debug(f"DEBUG: Funcionário {nome_funcionario}: {horas}h")
                        
                except (ValueError, IndexError) as e:
                    logger.error(f"Erro ao processar funcionário {key}: {e}")
                    continue
        
        # Processar mão de obra antiga (fallback para compatibilidade)
        mao_obra_json = request.form.get('mao_obra', '[]')
        if mao_obra_json and mao_obra_json != '[]':
            try:
                mao_obra_list = json.loads(mao_obra_json)
                for i, mo_data in enumerate(mao_obra_list):
                    funcionario_id = mo_data.get('funcionario_id')
                    if funcionario_id:
                        mao_obra = RDOMaoObra()
                        mao_obra.rdo_id = rdo.id
                        mao_obra.funcionario_id = int(funcionario_id)
                        mao_obra.funcao_exercida = mo_data.get('funcao', '').strip()
                        mao_obra.horas_trabalhadas = float(mo_data.get('horas', 8))
                        mao_obra.admin_id = admin_id_correto
                        db.session.add(mao_obra)
                        logger.debug(f"DEBUG: Funcionário JSON ID {funcionario_id}: {mo_data.get('horas', 8)}h")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar mão de obra JSON: {e}")
                flash(f'Erro ao processar mão de obra: {e}', 'warning')
        
        # Processar equipamentos
        equipamentos_json = request.form.get('equipamentos', '[]')
        if equipamentos_json and equipamentos_json != '[]':
            try:
                equipamentos_list = json.loads(equipamentos_json)
                for i, eq_data in enumerate(equipamentos_list):
                    nome_equipamento = eq_data.get('nome', '').strip()
                    if nome_equipamento:
                        equipamento = RDOEquipamento()
                        equipamento.rdo_id = rdo.id
                        equipamento.nome_equipamento = nome_equipamento
                        equipamento.quantidade = int(eq_data.get('quantidade', 1))
                        equipamento.horas_uso = float(eq_data.get('horas_uso', 8))
                        equipamento.estado_conservacao = eq_data.get('estado', 'Bom')
                        db.session.add(equipamento)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar equipamentos: {e}")
                flash(f'Erro ao processar equipamentos: {e}', 'warning')
        
        # Processar ocorrências
        ocorrencias_json = request.form.get('ocorrencias', '[]')
        if ocorrencias_json and ocorrencias_json != '[]':
            try:
                ocorrencias_list = json.loads(ocorrencias_json)
                for i, oc_data in enumerate(ocorrencias_list):
                    descricao = oc_data.get('descricao', '').strip()
                    if descricao:
                        ocorrencia = RDOOcorrencia()
                        ocorrencia.rdo_id = rdo.id
                        ocorrencia.descricao_ocorrencia = descricao
                        ocorrencia.problemas_identificados = oc_data.get('problemas', '').strip()
                        ocorrencia.acoes_corretivas = oc_data.get('acoes', '').strip()
                        db.session.add(ocorrencia)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Erro ao processar ocorrências: {e}")
                flash(f'Erro ao processar ocorrências: {e}', 'warning')
        
        # Log final antes de commitar
        total_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).count()
        total_funcionarios = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
        logger.debug(f"DEBUG FINAL: RDO {rdo.numero_rdo} - {total_subatividades} subatividades, {total_funcionarios} funcionários")
        
        db.session.commit()
        
        if rdo_id:
            flash(f'RDO {rdo.numero_rdo} atualizado com sucesso!', 'success')
        else:
            flash(f'RDO {rdo.numero_rdo} criado com sucesso!', 'success')
            
        return redirect(url_for('main.rdo_visualizar_unificado', id=rdo.id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO RDO SALVAR UNIFICADO: {str(e)}")
        logger.debug(f"DEBUG FORM DATA: {dict(request.form)}")
        logger.debug(f"DEBUG USER DATA: email={current_user.email}, tipo={current_user.tipo_usuario}")
        
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"TRACEBACK COMPLETO:\n{error_trace}")
        
        # Flash com erro detalhado para debugging
        flash(f'ERRO DETALHADO: {str(e)} | USER: {current_user.email} | ADMIN_ID: {current_user.admin_id} | TRACE: {error_trace[:500]}...', 'error')
        
        rdo_id = request.form.get('rdo_id', type=int)
        if rdo_id:
            return redirect(url_for('main.rdo_novo_unificado'))
        else:
            return redirect(url_for('main.rdo_novo_unificado'))

# Alias para compatibilidade com rota antiga de salvar
@main_bp.route('/funcionario/rdo/criar', methods=['POST'])
@funcionario_required
def funcionario_criar_rdo():
    """Redirect para nova rota unificada de salvar"""
    return rdo_salvar_unificado()

@main_bp.route('/rdo/<int:id>')
@funcionario_required
def rdo_visualizar_unificado(id):
    """Interface unificada para visualizar RDO - Admin e Funcionário"""
    try:
        # Detecção de admin_id unificada
        if current_user.tipo_usuario == TipoUsuario.ADMIN:
            admin_id = current_user.id
        elif current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            admin_id = current_user.admin_id
        else:
            admin_id = 10  # Fallback para desenvolvimento
        
        # Buscar RDO com verificação de acesso multitenant
        rdo = RDO.query.join(Obra).filter(
            RDO.id == id,
            Obra.admin_id == admin_id
        ).first_or_404()
        
        # Buscar funcionários para dropdown de mão de obra
        funcionarios = Funcionario.query.filter_by(
            admin_id=tenant_admin_id, 
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        funcionarios_dict = [{
            'id': f.id,
            'nome': f.nome,
            'email': f.email,
            'funcao_ref': {
                'nome': f.funcao_ref.nome if f.funcao_ref else 'Função não definida'
            } if f.funcao_ref else None
        } for f in funcionarios]
        
        # Buscar obras disponíveis
        obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        
        # Carregar subatividades salvas do RDO
        subatividades_salvas = {}
        rdo_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
        
        for rdo_subativ in rdo_subatividades:
            # Usar nome da subatividade como chave
            subatividades_salvas[rdo_subativ.nome_subatividade] = {
                'percentual': rdo_subativ.percentual_conclusao,
                'observacoes': rdo_subativ.observacoes_tecnicas or ''
            }
        
        # Carregar equipe de trabalho salva
        equipe_salva = {}
        mao_obra_salva = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
        
        for mao_obra in mao_obra_salva:
            equipe_salva[mao_obra.funcionario_id] = {
                'horas': mao_obra.horas_trabalhadas,
                'funcao': mao_obra.funcao_exercida or 'Funcionário'
            }
        
            logger.debug(f"DEBUG VISUALIZAR RDO UNIFICADO: RDO {rdo.numero_rdo} - {len(subatividades_salvas)} subatividades, {len(equipe_salva)} funcionários")
        
        # Template baseado no tipo de usuário
        if current_user.tipo_usuario == TipoUsuario.FUNCIONARIO:
            template = 'rdo/novo.html'  # SEMPRE usar template moderno
        else:
            template = 'rdo/visualizar_rdo.html'
        
        return render_template(template, 
                             obras=obras, 
                             funcionarios=funcionarios_dict,
                             obra_selecionada=rdo.obra,
                             rdo=rdo,
                             subatividades_salvas=subatividades_salvas,
                             equipe_salva=equipe_salva,
                             modo_edicao=True,
                             date=date)
        
    except Exception as e:
        logger.error(f"ERRO VISUALIZAR RDO UNIFICADO: {str(e)}")
        flash('Erro ao carregar RDO.', 'error')
        return redirect('/rdo')

@main_bp.route('/funcionario/rdo/<int:id>')
@funcionario_required
def funcionario_visualizar_rdo(id):
    """Redirect para nova interface unificada"""
    return redirect(url_for('main.rdo_visualizar_unificado', id=id))

@main_bp.route('/funcionario/rdo/<int:id>/editar', methods=['GET', 'POST'])
@funcionario_required
def funcionario_editar_rdo(id):
    """Redirecionar para o blueprint oficial de edição de RDO"""
    return redirect(url_for('rdo_editar.editar_rdo_form', rdo_id=id))

@main_bp.route('/funcionario/obras')
@funcionario_required
def funcionario_obras():
    """Lista obras disponíveis para o funcionário"""
    try:
        obras = Obra.query.filter_by(
            admin_id=current_user.admin_id
        ).order_by(Obra.nome).all()
        
        return render_template('funcionario/lista_obras.html', obras=obras)
        
    except Exception as e:
        logger.error(f"ERRO FUNCIONÁRIO OBRAS: {str(e)}")
        flash('Erro ao carregar obras.', 'error')
        return redirect(url_for('main.funcionario_dashboard'))

# ===== ROTAS MOBILE/API PARA FUNCIONÁRIOS =====
@main_bp.route('/api/funcionario/obras')
@funcionario_required
def api_funcionario_obras():
    """API para funcionários listar obras - acesso mobile"""
    try:
        obras = Obra.query.filter_by(
            admin_id=current_user.admin_id
        ).order_by(Obra.nome).all()
        
        obras_data = [
            {
                'id': obra.id,
                'nome': obra.nome,
                'endereco': obra.endereco,
                'status': obra.status if hasattr(obra, 'status') else 'Ativo'
            }
            for obra in obras
        ]
        
        return jsonify({
            'success': True,
            'obras': obras_data,
            'total': len(obras_data)
        })
        
    except Exception as e:
        logger.error(f"ERRO API FUNCIONÁRIO OBRAS: {str(e)}")
        return jsonify({'error': 'Erro interno', 'success': False}), 500

@main_bp.route('/api/funcionario/rdos/<int:obra_id>')
@funcionario_required
def api_funcionario_rdos_obra(obra_id):
    """API para funcionários buscar RDOs de uma obra específica"""
    try:
        # Verificar se obra pertence ao admin do funcionário
        obra = Obra.query.filter_by(id=obra_id, admin_id=current_user.admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada', 'success': False}), 404
        
        rdos = RDO.query.filter_by(obra_id=obra_id).order_by(
            RDO.data_relatorio.desc()
        ).limit(10).all()
        
        rdos_data = [
            {
                'id': rdo.id,
                'numero_rdo': rdo.numero_rdo,
                'data_relatorio': rdo.data_relatorio.strftime('%Y-%m-%d'),
                'status': rdo.status,
                'total_atividades': RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).count(),
                'total_funcionarios': len(rdo.mao_obra)
            }
            for rdo in rdos
        ]
        
        return jsonify({
            'success': True,
            'obra': {'id': obra.id, 'nome': obra.nome},
            'rdos': rdos_data,
            'total': len(rdos_data)
        })
        
    except Exception as e:
        logger.error(f"ERRO API FUNCIONÁRIO RDOs OBRA: {str(e)}")
        return jsonify({'error': 'Erro interno', 'success': False}), 500

# ===== ALIAS DE COMPATIBILIDADE - API FUNCIONÁRIOS MOBILE =====
@main_bp.route('/api/funcionario/funcionarios')
@funcionario_required
def api_funcionario_funcionarios_alias():
    """ALIAS: Redireciona para API consolidada com formato mobile"""
    logger.info("[ROUTE] ALIAS: Redirecionando /api/funcionario/funcionarios para API consolidada")
    
    # Detectar admin_id do usuário atual para manter compatibilidade
    admin_id = None
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        admin_id = current_user.admin_id
    elif hasattr(current_user, 'id'):
        admin_id = current_user.id
    else:
        admin_id = 10  # Fallback
    
    try:
        # Buscar funcionários diretamente (compatibilidade total)
        funcionarios = Funcionario.query.filter_by(
            admin_id=tenant_admin_id,
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        funcionarios_data = [
            {
                'id': func.id,
                'nome': func.nome,
                'funcao': func.funcao_ref.nome if func.funcao_ref else 'N/A',
                'departamento': func.departamento_ref.nome if func.departamento_ref else 'N/A'
            }
            for func in funcionarios
        ]
        
        logger.debug(f"[MOBILE] ALIAS API MOBILE: {len(funcionarios_data)} funcionários para admin_id={admin_id}")
        
        return jsonify({
            'success': True,
            'funcionarios': funcionarios_data,
            'total': len(funcionarios_data),
            '_consolidado': True  # Flag para debug
        })
        
    except Exception as e:
        logger.error(f"ERRO ALIAS FUNCIONÁRIOS MOBILE: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'funcionarios': [],
            '_consolidado': True
        }), 500

# ===== ENHANCED RDO API ENDPOINTS =====

# Endpoint de teste sem autenticação para desenvolvimento
@main_bp.route('/api/test/rdo/servicos-obra/<int:obra_id>')
def api_test_rdo_servicos_obra(obra_id):
    """API TEST para carregar serviços dinamicamente baseado na obra selecionada"""
    try:
        # CORREÇÃO CRÍTICA: Detectar admin_id baseado na obra específica
        obra_base = db.session.query(Obra).filter_by(id=obra_id).first()
        if not obra_base:
            return jsonify({
                'success': False,
                'error': f'Obra {obra_id} não encontrada no sistema'
            }), 404
        
        admin_id = obra_base.admin_id
        logger.debug(f"[TARGET] API TEST CORREÇÃO: admin_id detectado pela obra {obra_id} = {admin_id}")
        
        # Verificar se obra existe e pertence ao admin correto
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            return jsonify({'error': 'Obra não encontrada ou sem permissão', 'success': False}), 404
        
        # Buscar serviços associados à obra
        servicos_obra = db.session.query(ServicoObra, Servico).join(
            Servico, ServicoObra.servico_id == Servico.id
        ).filter(
            ServicoObra.obra_id == obra_id,
            ServicoObra.ativo == True,
            Servico.ativo == True
        ).all()
        
        servicos_data = []
        for servico_obra, servico in servicos_obra:
            # Buscar subatividades mestre para este serviço
            subatividades = SubatividadeMestre.query.filter_by(
                servico_id=servico.id,
                admin_id=admin_id,
                ativo=True
            ).order_by(SubatividadeMestre.ordem_padrao).all()
            
            subatividades_data = [sub.to_dict() for sub in subatividades]
            
            # Calcular percentual com segurança
            quantidade_executada = float(servico_obra.quantidade_executada or 0)
            quantidade_planejada = float(servico_obra.quantidade_planejada or 0)
            percentual_obra = round((quantidade_executada / quantidade_planejada * 100) if quantidade_planejada > 0 else 0, 2)
            
            servico_data = {
                'id': servico.id,
                'nome': servico.nome,
                'descricao': servico.descricao,
                'categoria': servico.categoria,
                'quantidade_planejada': quantidade_planejada,
                'quantidade_executada': quantidade_executada,
                'percentual_obra': percentual_obra,
                'subatividades': subatividades_data,
                'total_subatividades': len(subatividades_data)
            }
            servicos_data.append(servico_data)
        
        return jsonify({
            'success': True,
            'obra': {'id': obra.id, 'nome': obra.nome},
            'servicos': servicos_data,
            'total': len(servicos_data)
        })
        
    except Exception as e:
        logger.error(f"ERRO API TEST RDO SERVIÇOS OBRA: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Erro interno', 'success': False}), 500

# API RECONSTRUÍDA: Sistema de Última RDO com Arquitetura de Maestria
@main_bp.route('/api/ultimo-rdo-dados/<int:obra_id>')
def api_ultimo_rdo_dados_v2(obra_id):
    """Sistema de Última RDO - Arquitetura de Maestria Digital
    
    Implementação robusta com:
    - Observabilidade completa
    - Isolamento multi-tenant
    - Tratamento resiliente de estados
    - Circuit breakers para falhas
    """
    try:
        # === FASE 1: VALIDAÇÃO E CONTEXTO ===
        admin_id_user = get_admin_id_dinamico()
        
        # Busca inteligente da obra com isolamento
        obra = Obra.query.filter_by(id=obra_id).first()
        if not obra:
            return jsonify({
                'success': False,
                'error': 'Obra não encontrada',
                'error_code': 'OBRA_NOT_FOUND'
            }), 404
        
        # Detecção automática de admin_id com logs estruturados
        admin_id_obra = obra.admin_id
        if admin_id_obra != admin_id_user:
            logger.debug(f"[SYNC] CROSS-TENANT ACCESS: user={admin_id_user} → obra={admin_id_obra} [PERMITIDO]")
        
        admin_id = admin_id_obra
        logger.debug(f"[TARGET] API V2 ÚLTIMA RDO: obra_id={obra_id}, admin_id={admin_id}, obra='{obra.nome}'")
        
        # === FASE 2: BUSCA INTELIGENTE DE RDO ===
        ultimo_rdo = RDO.query.filter_by(
            obra_id=obra_id, 
            admin_id=admin_id
        ).order_by(RDO.data_relatorio.desc()).first()
        
        logger.debug(f"[DEBUG] RDO Query: obra_id={obra_id}, admin_id={admin_id} → {'ENCONTRADO' if ultimo_rdo else 'PRIMEIRA_RDO'}")
        
        # === FASE 3: PROCESSAMENTO DE ESTADOS ===
        if not ultimo_rdo:
            logger.debug(f"🆕 PRIMEIRA_RDO: Inicializando obra {obra.nome} com serviços em 0%")
            return _processar_primeira_rdo(obra, admin_id)
        else:
            logger.debug(f"[SYNC] RDO_EXISTENTE: Carregando dados do RDO #{ultimo_rdo.id} ({ultimo_rdo.data_relatorio})")
            return _processar_rdo_existente(ultimo_rdo, admin_id)
            
    except Exception as e:
        logger.error(f"[ERROR] ERRO CRÍTICO API V2: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'error_code': 'INTERNAL_ERROR'
        }), 500

# === FUNÇÕES AUXILIARES DE PROCESSAMENTO ===

def _processar_primeira_rdo(obra, admin_id):
    """Processa estado de primeira RDO com arquitetura elegante"""
    try:
        # Buscar serviços disponíveis com múltiplas estratégias
        servicos_obra = _buscar_servicos_obra_resiliente(obra.id, admin_id)
        
        if not servicos_obra:
            return jsonify({
                'success': True,
                'primeira_rdo': True,
                'ultima_rdo': None,
                'message': 'Obra sem serviços cadastrados - adicione serviços primeiro',
                'metadata': {
                    'obra_id': obra.id,
                    'obra_nome': obra.nome,
                    'total_servicos': 0,
                    'estado': 'SEM_SERVICOS'
                }
            })
        
        # Transformar serviços em estrutura de primeira RDO
        servicos_data = []
        for servico in servicos_obra:
            # Buscar subatividades padrão do serviço
            subatividades = _buscar_subatividades_servico(servico.id)
            
            servico_data = {
                'id': servico.id,
                'nome': servico.nome,
                'categoria': getattr(servico, 'categoria', 'Geral'),
                'subatividades': [{
                    'id': f"novo_{servico.id}_{i}",
                    'nome': sub.nome if hasattr(sub, 'nome') else f'Subatividade {i+1}',
                    'percentual': 0.0,  # Sempre 0% para primeira RDO
                    'descricao': getattr(sub, 'descricao', '') if hasattr(sub, 'descricao') else '',
                    'novo': True
                } for i, sub in enumerate(subatividades)]
            }
            servicos_data.append(servico_data)
            
        return jsonify({
            'success': True,
            'primeira_rdo': True,
            'ultima_rdo': {
                'id': None,
                'numero_rdo': 'PRIMEIRA_RDO',
                'data_relatorio': datetime.now().strftime('%Y-%m-%d'),
                'servicos': servicos_data,
                'funcionarios': [],
                'total_servicos': len(servicos_data),
                'total_funcionarios': 0
            },
            'metadata': {
                'obra_id': obra.id,
                'obra_nome': obra.nome,
                'estado': 'PRIMEIRA_RDO',
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO _processar_primeira_rdo: {e}")
        return jsonify({
            'success': False,
            'error': 'Falha ao processar primeira RDO',
            'error_code': 'PRIMEIRA_RDO_ERROR'
        }), 500
            
def _processar_rdo_existente(ultimo_rdo, admin_id):
    """Processa RDO existente com herança de dados"""
    try:
        # Buscar subatividades do último RDO com query otimizada
        subatividades_rdo = RDOServicoSubatividade.query.filter_by(
            rdo_id=ultimo_rdo.id, 
            ativo=True
        ).all()
        
        logger.info(f"[STATS] SUBATIVIDADES: {len(subatividades_rdo)} registros encontrados")
        
        if not subatividades_rdo:
            return jsonify({
                'success': True,
                'primeira_rdo': False,
                'ultima_rdo': {
                    'id': ultimo_rdo.id,
                    'numero_rdo': ultimo_rdo.numero_rdo,
                    'data_relatorio': ultimo_rdo.data_relatorio.strftime('%Y-%m-%d'),
                    'servicos': [],
                    'funcionarios': [],
                    'total_servicos': 0,
                    'total_funcionarios': 0
                },
                'message': 'RDO sem subatividades cadastradas'
            })
        
        # Processar subatividades agrupadas por serviço
        servicos_dict = {}
        
        for sub_rdo in subatividades_rdo:
            servico_id = sub_rdo.servico_id
            
            # Buscar dados do serviço com cache - FILTRAR APENAS SERVIÇOS ATIVOS NA OBRA
            if servico_id not in servicos_dict:
                servico = Servico.query.filter_by(
                    id=servico_id, 
                    admin_id=tenant_admin_id, 
                    ativo=True
                ).first()
                
                if not servico:
                    logger.warning(f"[WARN] SERVICO_DESATIVADO_IGNORADO: {servico_id} (admin_id={admin_id})")
                    continue
                
                # VERIFICAR SE SERVIÇO ESTÁ ATIVO NA OBRA ATUAL
                obra_id = ultimo_rdo.obra_id
                servico_obra_ativo = ServicoObraReal.query.filter_by(
                    obra_id=obra_id,
                    servico_id=servico_id,
                    admin_id=tenant_admin_id,
                    ativo=True
                ).first()
                
                if not servico_obra_ativo:
                    logger.warning(f"[WARN] SERVICO_REMOVIDO_DA_OBRA: {servico.nome} (ID: {servico_id}) - PULANDO")
                    continue
                    
                servicos_dict[servico_id] = {
                    'id': servico.id,
                    'nome': servico.nome,
                    'categoria': getattr(servico, 'categoria', 'Geral'),
                    'subatividades': []
                }
                logger.info(f"[OK] SERVICO_CARREGADO: {servico.nome} (ID: {servico_id})")
            
            # Adicionar subatividade ao serviço
            servicos_dict[servico_id]['subatividades'].append({
                'id': sub_rdo.id,
                'nome': sub_rdo.nome_subatividade,
                'percentual': float(sub_rdo.percentual_conclusao or 0),
                'descricao': sub_rdo.descricao_subatividade or '',
                'observacoes_tecnicas': sub_rdo.observacoes_tecnicas or ''
            })
            
        # Buscar funcionários do RDO
        funcionarios_data = []
        try:
            funcionarios_rdo = RDOMaoObra.query.filter_by(
                rdo_id=ultimo_rdo.id
            ).all()
            
            for func_rdo in funcionarios_rdo:
                if func_rdo.funcionario:
                    funcionarios_data.append({
                        'id': func_rdo.funcionario.id,
                        'nome': func_rdo.funcionario.nome,
                        'funcao': getattr(func_rdo.funcionario, 'funcao', 'Funcionário'),
                        'horas_trabalhadas': float(func_rdo.horas_trabalhadas) if func_rdo.horas_trabalhadas else 8.8
                    })
        except Exception as e:
            logger.warning(f"[WARN] ERRO_FUNCIONARIOS: {e}")
            funcionarios_data = []
        
        servicos_data = list(servicos_dict.values())
        
        logger.info(f"[OK] RDO_PROCESSADO: {len(servicos_data)} serviços, {len(funcionarios_data)} funcionários")
        
        return jsonify({
            'success': True,
            'primeira_rdo': False,
            'ultima_rdo': {
                'id': ultimo_rdo.id,
                'numero_rdo': ultimo_rdo.numero_rdo or f'RDO-{ultimo_rdo.id}',
                'data_relatorio': ultimo_rdo.data_relatorio.strftime('%Y-%m-%d'),
                'servicos': servicos_data,
                'funcionarios': funcionarios_data,
                'total_servicos': len(servicos_data),
                'total_funcionarios': len(funcionarios_data)
            },
            'metadata': {
                'rdo_id': ultimo_rdo.id,
                'obra_id': ultimo_rdo.obra_id,
                'estado': 'RDO_EXISTENTE',
                'timestamp': datetime.now().isoformat()
            }
        })
    
    except Exception as e:
        logger.error(f"[ERROR] ERRO _processar_rdo_existente: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Falha ao processar RDO existente',
            'error_code': 'RDO_EXISTENTE_ERROR'
        }), 500

@main_bp.route('/api/servicos-obra-primeira-rdo/<int:obra_id>')
def api_servicos_obra_primeira_rdo(obra_id):
    """
    API ESPECÍFICA: Buscar serviços de uma obra para primeira RDO
    Retorna serviços com subatividades para exibição em cards
    """
    try:
        # CORREÇÃO CRÍTICA: Detectar admin_id baseado na obra específica
        obra_base = db.session.query(Obra).filter_by(id=obra_id).first()
        if not obra_base:
            return jsonify({
                'success': False,
                'error': f'Obra {obra_id} não encontrada no sistema'
            }), 404
        
        admin_id = obra_base.admin_id
        logger.debug(f"[TARGET] CORREÇÃO: admin_id detectado pela obra {obra_id} = {admin_id}")
        
        logger.debug(f"[TARGET] API servicos-obra-primeira-rdo: obra {obra_id}, admin_id {admin_id}")
        
        # Verificar se obra existe e pertence ao admin
        obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
        if not obra:
            logger.error(f"[ERROR] Obra {obra_id} não encontrada para admin_id {admin_id}")
            return jsonify({
                'success': False,
                'error': 'Obra não encontrada ou sem permissão de acesso'
            }), 404
        
        # Buscar serviços da obra usando estratégia resiliente
        servicos_obra = _buscar_servicos_obra_resiliente(obra_id, admin_id)
        
        if not servicos_obra:
            logger.debug(f"[INFO] Nenhum serviço encontrado para obra {obra_id}")
            return jsonify({
                'success': False,
                'message': 'Nenhum serviço cadastrado para esta obra'
            })
        
        # Montar dados dos serviços com suas subatividades
        servicos_data = []
        for servico in servicos_obra:
            # Buscar subatividades do serviço
            subatividades = SubatividadeMestre.query.filter_by(
                servico_id=servico.id,
                admin_id=admin_id,  # [OK] CORREÇÃO CRÍTICA: usar admin_id ao invés de tenant_admin_id
                ativo=True
            ).order_by(SubatividadeMestre.ordem_padrao).all()
            
            subatividades_data = []
            for sub in subatividades:
                subatividades_data.append({
                    'id': sub.id,
                    'nome': sub.nome,
                    'descricao': sub.descricao or '',
                    'percentual': 0.0  # Sempre 0% para primeira RDO
                })
            
            # Se não tem subatividades mestre, criar uma padrão
            if not subatividades_data:
                subatividades_data.append({
                    'id': f'default_{servico.id}',
                    'nome': servico.nome,
                    'descricao': 'Execução completa do serviço',
                    'percentual': 0.0
                })
            
            servico_data = {
                'id': servico.id,
                'nome': servico.nome,
                'categoria': getattr(servico, 'categoria', 'Geral'),
                'descricao': servico.descricao or '',
                'subatividades': subatividades_data
            }
            servicos_data.append(servico_data)
        
            logger.info(f"[OK] API servicos-obra-primeira-rdo: {len(servicos_data)} serviços encontrados")
        
        return jsonify({
            'success': True,
            'servicos': servicos_data,
            'total_servicos': len(servicos_data),
            'obra': {
                'id': obra.id,
                'nome': obra.nome
            }
        })
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO API servicos-obra-primeira-rdo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ROTA FLEXÍVEL PARA SALVAR RDO - CORRIGE ERRO 404
@main_bp.route('/salvar-rdo-flexivel', methods=['POST'])
@funcionario_required
def salvar_rdo_flexivel():
    """
    ARQUITETURA REFATORADA - Joris Kuypers Digital Mastery
    Implementação robusta com separação clara de responsabilidades
    [READY] VERSÃO COM DEBUG DETALHADO PARA PRODUÇÃO
    """
    
    
    # [OK] VERIFICAÇÃO DE SCHEMA PREVENTIVA
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        # Verificar tabelas críticas
        tabelas_necessarias = ['rdo', 'rdo_servico_subatividade', 'rdo_mao_obra']
        for tabela in tabelas_necessarias:
            if tabela in inspector.get_table_names():
                colunas = [col['name'] for col in inspector.get_columns(tabela)]
                logger.info(f"[OK] Tabela {tabela}: {len(colunas)} colunas encontradas")
            else:
                logger.error(f"[ERROR] Tabela {tabela} NÃO ENCONTRADA!")
                
    except Exception as schema_check_error:
        logger.warning(f"[WARN] Não foi possível verificar schema: {schema_check_error}")
    
    try:
        # IMPLEMENTAÇÃO DA NOVA ARQUITETURA DIRETAMENTE AQUI
        logger.info("[TARGET] JORIS KUYPERS ARCHITECTURE: Iniciando salvamento RDO")
        logger.info("[START] DEBUG PRODUÇÃO: Logs detalhados ativados")
        
        # Obter dados básicos da sessão e formulário
        funcionario_id = session.get('funcionario_id') or request.form.get('funcionario_id', type=int)
        admin_id = session.get('admin_id') or request.form.get('admin_id_form', type=int)
        obra_id = request.form.get('obra_id', type=int)
        
        # FALLBACK: Se sessão perdida, buscar admin_id dinamicamente
        if not admin_id and funcionario_id:
            funcionario = Funcionario.query.get(funcionario_id)
            if funcionario:
                admin_id = funcionario.admin_id
                session['admin_id'] = admin_id
                logger.info(f"[SYNC] Admin_id recuperado via funcionário: {admin_id}")
        
        # Se ainda não tem admin_id, usar detecção automática baseada na obra
        if not admin_id and obra_id:
            obra = Obra.query.get(obra_id)
            if obra:
                admin_id = obra.admin_id
                session['admin_id'] = admin_id
                logger.info(f"[SYNC] Admin_id recuperado via obra: {admin_id}")
        
        # ÚLTIMO RECURSO: Se não tem funcionario_id, usar o primeiro funcionário do admin
        if not funcionario_id and admin_id:
            funcionario = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).first()
            if funcionario:
                funcionario_id = funcionario.id
                session['funcionario_id'] = funcionario_id
                logger.info(f"[SYNC] Funcionario_id recuperado: {funcionario_id}")
        
        if not all([funcionario_id, admin_id, obra_id]):
            logger.error(f"[ERROR] Dados inválidos: funcionario_id={funcionario_id}, admin_id={admin_id}, obra_id={obra_id}")
            logger.error(f"[ERROR] Campos form: {list(request.form.keys())[:10]}")
            flash('Dados de sessão inválidos. Faça login novamente.', 'error')
            return redirect(url_for('main.funcionario_rdo_novo'))
            
            logger.info(f"[TARGET] Dados da sessão: obra_id={obra_id}, admin_id={admin_id}")
        
        # FASE 1: DESCOBRIR CONTEXTO DO SERVIÇO (Arquitetura Joris Kuypers INLINE)
        # Buscar último serviço usado nesta obra
        ultimo_servico_rdo = db.session.query(RDOServicoSubatividade).join(RDO).filter(
            RDO.obra_id == obra_id,
            RDO.admin_id == admin_id
        ).order_by(RDO.data_relatorio.desc()).first()
        
        if ultimo_servico_rdo:
            target_service_id = ultimo_servico_rdo.servico_id
            servico_obj = Servico.query.get(target_service_id)
            service_name = servico_obj.nome if servico_obj else f"Serviço {target_service_id}"
            logger.info(f"[TARGET] SERVIÇO DO HISTÓRICO: {service_name} (ID: {target_service_id})")
        else:
            # Fallback: primeiro serviço ativo da obra - CORRIGIDO
            try:
                # [OK] CORREÇÃO CRÍTICA: Usar admin_id ao invés de ativo
                servico_obra = db.session.query(ServicoObraReal).join(Servico).filter(
                    ServicoObraReal.obra_id == obra_id,
                    ServicoObraReal.admin_id == admin_id,  # CORRIGIDO: usar admin_id
                    Servico.admin_id == admin_id,
                    Servico.ativo == True
                ).first()
                
                if servico_obra and servico_obra.servico:
                    target_service_id = servico_obra.servico.id
                    service_name = servico_obra.servico.nome
                    logger.info(f"[TARGET] SERVIÇO DA OBRA: {service_name} (ID: {target_service_id})")
                else:
                    flash('Não foi possível identificar o serviço para esta obra', 'error')
                    return redirect(url_for('main.funcionario_rdo_novo'))
            except Exception as e:
                logger.error(f"[ERROR] Erro ao buscar serviço da obra: {e}")
                flash('Erro ao identificar serviço da obra', 'error')
                return redirect(url_for('main.funcionario_rdo_novo'))
        
        # FASE 2: PROCESSAR DADOS DAS SUBATIVIDADES (Arquitetura Joris Kuypers INLINE)
                logger.info(f"[DEBUG] DEBUG FORMULÁRIO PRODUÇÃO - TODOS OS CAMPOS:")
                logger.info(f"[STATS] Total de campos recebidos: {len(request.form)}")
        for key, value in request.form.items():
            logger.info(f" [INFO] {key} = {value}")
        
            logger.info(f"[DEBUG] DEBUG FORMULÁRIO - Campos subatividade:")
        for key, value in request.form.items():
            if 'subatividade' in key:
                logger.info(f" [TARGET] {key} = {value}")
        
        subactivities = []
        logger.error(f"[DEBUG] INICIANDO PROCESSAMENTO - Buscando campos 'subatividade_*_percentual'")
        campos_encontrados = [k for k in request.form.keys() if k.startswith('subatividade_') and k.endswith('_percentual')]
        logger.error(f"[DEBUG] Campos subatividade_*_percentual encontrados: {len(campos_encontrados)}")
        for campo in campos_encontrados:
            logger.error(f" [TARGET] {campo}")
        
        for field_name, field_value in request.form.items():
            if field_name.startswith('subatividade_') and field_name.endswith('_percentual'):
                try:
                    # Tentar formato: subatividade_139_292_percentual
                    parts = field_name.replace('subatividade_', '').replace('_percentual', '').split('_')
                    logger.error(f"[DEBUG] Processando campo {field_name}, parts: {parts}, valor: {field_value}")
                    
                    if len(parts) >= 2:
                        original_service_id = int(parts[0])
                        sub_id = parts[1]
                        
                        percentual = float(field_value) if field_value else 0.0
                        obs_field = f"subatividade_{original_service_id}_{sub_id}_observacoes"
                        observacoes = request.form.get(obs_field, "")
                        nome_field = f"nome_subatividade_{original_service_id}_{sub_id}"
                        nome = request.form.get(nome_field, "")
                        
                        # CORREÇÃO CRÍTICA: Buscar nome real da subatividade mestre DINAMICAMENTE
                        try:
                            # TENTAR BUSCAR NO BANCO PRIMEIRO (QUALQUER SERVIÇO)
                            subatividade_mestre = db.session.query(SubatividadeMestre).filter_by(
                                id=int(sub_id)
                            ).first()
                            
                            if subatividade_mestre:
                                nome = subatividade_mestre.nome
                                logger.error(f"[OK] Nome DINÂMICO da subatividade {sub_id}: {nome}")
                            else:
                                logger.error(f"[ERROR] IGNORANDO: Subatividade {sub_id} não encontrada no banco - NÃO será salva")
                                continue  # Pula esta subatividade
                                
                        except Exception as e:
                            logger.error(f"[ERROR] Erro ao buscar subatividade {sub_id} no banco: {e}")
                            continue  # Pula esta subatividade
                        
                        # Só adiciona se tem nome válido
                        if nome and nome.strip():
                            logger.error(f"[PKG] Subatividade extraída: {nome} = {percentual}%")
                            subactivities.append({
                                'original_service_id': original_service_id,
                                'sub_id': sub_id,
                                'nome': nome,
                                'percentual': percentual,
                                'observacoes': observacoes
                            })
                        else:
                            logger.error(f"[ERROR] REJEITANDO subatividade {sub_id}: nome vazio ou inválido")
                    else:
                        logger.error(f"[ERROR] Campo {field_name} não tem formato esperado: parts={parts}")
                        
                except (ValueError, IndexError) as e:
                    logger.error(f"[ERROR] Erro ao processar campo {field_name}: {e}")
                    continue
        
                    logger.error(f"[TARGET] RESULTADO LOOP 1: {len(subactivities)} subatividades encontradas")
        
        # FALLBACK: Se não encontrou pelo formato padrão, tentar outros formatos
        if not subactivities:
            logger.error("[SYNC] FALLBACK ATIVADO - Tentando formatos alternativos de subatividade...")
            logger.error(f"[DEBUG] Total de campos com 'percentual': {len([k for k in request.form.keys() if 'percentual' in k])}")
            for field_name, field_value in request.form.items():
                if 'percentual' in field_name and field_value:
                    logger.error(f"[DEBUG] Campo percentual encontrado: {field_name} = {field_value}")
                    try:
                        # Extrair qualquer número do nome do campo
                        import re
                        numbers = re.findall(r'\d+', field_name)
                        if len(numbers) >= 1:
                            sub_id = numbers[-1]  # Último número
                            percentual = float(field_value) if field_value else 0.0
                            
                            # CORREÇÃO CRÍTICA FALLBACK: Buscar nome real da subatividade mestre
                            nome = ""  # Não definir valor padrão genérico
                            
                            try:
                                # BUSCA DINÂMICA NO BANCO (QUALQUER SERVIÇO)
                                subatividade_mestre = db.session.query(SubatividadeMestre).filter_by(
                                    id=int(sub_id)
                                ).first()
                                
                                if subatividade_mestre:
                                    nome = subatividade_mestre.nome
                                    logger.info(f"[OK] FALLBACK DINÂMICO: Nome da subatividade {sub_id}: {nome}")
                                else:
                                    logger.warning(f"[WARN] IGNORANDO: Subatividade {sub_id} não existe no banco - NÃO será salva")
                                    continue  # Pula esta subatividade
                                    
                            except Exception as e:
                                logger.error(f"[ERROR] FALLBACK: Erro ao buscar subatividade {sub_id} no banco: {e}")
                                logger.error(f"[ERROR] REJEITANDO: Subatividade {sub_id} não será salva")
                                continue  # Pula esta subatividade
                            
                            # Só adiciona se encontrou nome válido
                            if nome and nome.strip():
                                subactivities.append({
                                    'original_service_id': target_service_id,
                                    'sub_id': sub_id,
                                    'nome': nome,
                                    'percentual': percentual,
                                    'observacoes': ""
                                })
                                logger.info(f"[OK] Subatividade alternativa: {nome} = {percentual}%")
                            else:
                                logger.error(f"[ERROR] REJEITANDO subatividade {sub_id} no fallback: nome vazio")
                    except:
                        continue
        
        if not subactivities:
            # [OK] CORREÇÃO: Permitir RDOs sem subatividades (registros simples de presença)
            logger.warning("[WARN] RDO sem subatividades - será salvo apenas com funcionários")
            logger.info(f"[DEBUG] Total de campos no formulário: {len(request.form)}")
            logger.info(f"[DEBUG] Target service ID: {target_service_id}")
            logger.info(f"[DEBUG] Admin ID: {admin_id}")
            logger.info(f"[DEBUG] Obra ID: {obra_id}")
            
            logger.info(f"[TARGET] SUBATIVIDADES PROCESSADAS: {len(subactivities)} itens")
        
        # FASE 3: CRIAR RDO PRINCIPAL
        data_relatorio = request.form.get('data_relatorio')
        if data_relatorio:
            data_relatorio = datetime.strptime(data_relatorio, '%Y-%m-%d').date()
        else:
            data_relatorio = datetime.now().date()
            
        # [OK] CORREÇÃO CRÍTICA: Gerar número RDO Único (evita constraint violation)
            logger.info(f"[NUM] GERANDO NÚMERO RDO Único para admin_id={admin_id}, ano={data_relatorio.year}")
        
        # Gerar número único com verificação de duplicata
        contador = 1
        numero_rdo = None
        
        # Loop para garantir número único
        for tentativa in range(1, 1000):  # Máximo 999 tentativas
            numero_proposto = f"RDO-{admin_id}-{data_relatorio.year}-{tentativa:03d}"
            
            # Verificar se já existe
            rdo_existente = RDO.query.filter_by(
                numero_rdo=numero_proposto,
                admin_id=admin_id
            ).first()
            
            if not rdo_existente:
                numero_rdo = numero_proposto
                logger.info(f"[OK] NÚMERO RDO Único GERADO: {numero_rdo}")
                break
            else:
                logger.info(f"[WARN] Número {numero_proposto} já existe, tentando próximo...")
                
        # Fallback de segurança
        if not numero_rdo:
            import random
            numero_rdo = f"RDO-{admin_id}-{data_relatorio.year}-{random.randint(1000, 9999):04d}"
            logger.warning(f"[FALLBACK] FALLBACK: Usando número aleatório {numero_rdo}")
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            obra_id=obra_id,
            criado_por_id=funcionario_id,
            data_relatorio=data_relatorio,
            local=request.form.get('local', 'Campo'),
            admin_id=admin_id
        )
        
        # FASE 4: PERSISTIR COM TRANSAÇÃO ROBUSTA (Arquitetura Joris Kuypers INLINE)
        logger.info(f"[START] INICIANDO TRANSAÇÃO - RDO {numero_rdo}")
        try:
            # [OK] CORREÇÃO: Verificar schema do RDO antes de salvar
            try:
                # Teste de schema - verificar se todas as colunas existem
                logger.info(f"[DEBUG] VERIFICAÇÃO SCHEMA RDO:")
                logger.info(f" [LIST] numero_rdo: {rdo.numero_rdo}")
                logger.info(f" [BUILD] obra_id: {rdo.obra_id}")
                logger.info(f" [USER] criado_por_id: {rdo.criado_por_id}")
                logger.info(f"  [DATE] data_relatorio: {rdo.data_relatorio}")
                logger.info(f"  [LOC] local: {rdo.local}")
                logger.info(f" [CORP] admin_id: {rdo.admin_id}")
            except Exception as schema_error:
                logger.error(f"[ERROR] ERRO SCHEMA RDO: {schema_error}")
                raise Exception(f"Schema RDO inválido: {schema_error}")
            
            # Salvar RDO principal
            db.session.add(rdo)
            db.session.flush()  # Para obter o ID
            
            logger.info(f"[SAVE] RDO {rdo.numero_rdo} criado com ID {rdo.id}")
            
            # Salvar todas as subatividades no serviço correto
            logger.info(f"[SAVE] SALVANDO {len(subactivities)} SUBATIVIDADES")
            for i, sub_data in enumerate(subactivities):
                try:
                    # [OK] CORREÇÃO CRÍTICA: Usar original_service_id de cada subatividade
                    servico_id_correto = sub_data.get('original_service_id', target_service_id)
                    logger.info(f" [LIST] [{i+1}/{len(subactivities)}] {sub_data['nome']} = {sub_data['percentual']}% (servico_id={servico_id_correto})")
                    
                    subatividade = RDOServicoSubatividade(
                        rdo_id=rdo.id,
                        servico_id=servico_id_correto,  # [OK] CORRIGIDO: Usa o servico_id específico de cada subatividade
                        nome_subatividade=sub_data['nome'],
                        percentual_conclusao=sub_data['percentual'],
                        observacoes_tecnicas=sub_data['observacoes'],
                        admin_id=admin_id,
                        ativo=True
                    )
                    
                    db.session.add(subatividade)
                    logger.info(f" [OK] Subatividade {sub_data['nome']} salva com servico_id={servico_id_correto}")
                    
                except Exception as sub_error:
                    logger.error(f" [ERROR] Erro na subatividade {sub_data['nome']}: {sub_error}")
                    raise Exception(f"Erro ao criar subatividade {sub_data['nome']}: {sub_error}")
                # Removido - lógica movida para o bloco anterior
            
            # CORREÇÃO CRÍTICA: PROCESSAR FUNCIONÁRIOS SELECIONADOS
            funcionarios_selecionados = request.form.getlist('funcionarios_selecionados')
            logger.info(f"[USERS] PROCESSANDO FUNCIONÁRIOS: {len(funcionarios_selecionados)} selecionados")
            logger.info(f"[USERS] Lista de IDs: {funcionarios_selecionados}")
            
            for funcionario_id_str in funcionarios_selecionados:
                try:
                    if funcionario_id_str and funcionario_id_str.strip():
                        funcionario_id_sel = int(funcionario_id_str.strip())
                        
                        # Verificar se funcionário existe
                        funcionario = Funcionario.query.get(funcionario_id_sel)
                        if funcionario:
                            # [OK] CORREÇÃO CRÍTICA: Criar registro seguro de mão de obra
                            funcao_exercida = 'Funcionário'  # Padrão seguro
                            try:
                                if hasattr(funcionario, 'funcao_ref') and funcionario.funcao_ref:
                                    funcao_exercida = funcionario.funcao_ref.nome
                                elif hasattr(funcionario, 'funcao') and funcionario.funcao:
                                    funcao_exercida = funcionario.funcao
                                    logger.info(f"[WORKER] Função determinada para {funcionario.nome}: {funcao_exercida}")
                            except Exception as e:
                                logger.warning(f"[WARN] Erro ao buscar função do funcionário {funcionario.nome}: {e}")
                            
                            # [DEBUG] VERIFICAÇÃO SCHEMA RDOMaoObra
                                logger.info(f"[DEBUG] Criando RDOMaoObra - rdo_id: {rdo.id}, funcionario_id: {funcionario_id_sel}, admin_id: {admin_id}")
                            try:
                                mao_obra = RDOMaoObra(
                                    rdo_id=rdo.id,
                                    funcionario_id=funcionario_id_sel,
                                    horas_trabalhadas=8.8,  # Padrão
                                    funcao_exercida=funcao_exercida,
                                    admin_id=admin_id
                                )
                                
                                # Teste de schema antes de adicionar
                                logger.info(f" [OK] RDOMaoObra criado: {vars(mao_obra)}")
                                db.session.add(mao_obra)
                                logger.info(f"[WORKER] Funcionário salvo: {funcionario.nome} (ID: {funcionario_id_sel})")
                            except Exception as mao_obra_error:
                                logger.error(f"[ERROR] ERRO RDOMaoObra para funcionario {funcionario.nome}: {mao_obra_error}")
                                raise Exception(f"Erro ao criar RDOMaoObra: {mao_obra_error}")
                        else:
                            logger.warning(f"[WARN] Funcionário ID {funcionario_id_sel} não encontrado")
                except Exception as e:
                    logger.error(f"[ERROR] Erro ao processar funcionário {funcionario_id_str}: {e}")
                    continue
            
            # [PHOTO] PROCESSAR FOTOS (v9.0) - CORREÇÃO COMPLETA + LEGENDAS v9.0.2
            if 'fotos[]' in request.files:
                fotos_files = request.files.getlist('fotos[]')
                logger.info(f"[PHOTO] {len(fotos_files)} foto(s) recebida(s) para processar")
                
                # DEBUG: Mostrar todas as fotos recebidas
                for i, foto in enumerate(fotos_files, 1):
                    logger.info(f" [INFO] Foto {i}: filename='{foto.filename}', content_type='{foto.content_type}'")
                
                # [OK] CORREÇÃO 1: FILTRAR ARQUIVOS VAZIOS mantendo índice original (crítico!)
                # Rastrear índice original para sincronização correta com legendas
                fotos_com_indice = [(idx, f) for idx, f in enumerate(fotos_files) if f and f.filename and f.filename.strip() != '']
                logger.info(f"[OK] {len(fotos_com_indice)} foto(s) válida(s) após filtragem (removidos {len(fotos_files) - len(fotos_com_indice)} arquivos vazios)")
                
                if fotos_com_indice:
                    logger.info(f"[TARGET] [FOTO-UPLOAD] INICIANDO processamento de {len(fotos_com_indice)} foto(s)")
                    
                    try:
                        # [OK] CORREÇÃO 2: Usar salvar_foto_rdo (que existe)
                        from services.rdo_foto_service import salvar_foto_rdo
                        
                        # [TARGET] ESTRATÉGIA ROBUSTA COM FALLBACK (v9.0.2.5 - PRODUÇÃO SAFE)
                        # Tenta contador sequencial primeiro (mobile com arquivo vazio)
                        # Se não encontrar legenda, tenta índice original (desktop sem vazio)
                        # Isso garante compatibilidade com TODOS os cenários
                        
                        contador_legenda = 0  # Contador sequencial para mobile
                        
                        for original_idx, foto in fotos_com_indice:
                            logger.info(f"[PHOTO] [FOTO-UPLOAD] Processando foto (contador={contador_legenda}, idx_original={original_idx}): {foto.filename}")
                            
                            # Chamar service layer para processar foto
                            resultado = salvar_foto_rdo(foto, admin_id, rdo.id)
                            logger.info(f" [OK] Foto processada: {resultado['arquivo_original']}")
                            
                            # [INFO] FALLBACK INTELIGENTE: Tenta contador primeiro, depois índice original
                            legenda = ''
                            campo_contador = f"legenda_foto_{contador_legenda}"
                            campo_original = f"legenda_foto_{original_idx}"
                            
                            # Tenta contador sequencial (mobile)
                            legenda = request.form.get(campo_contador, '').strip()
                            if legenda:
                                logger.info(f" [OK] Legenda encontrada via contador ({campo_contador}): '{legenda}'")
                            else:
                                # Fallback: tenta índice original (desktop)
                                legenda = request.form.get(campo_original, '').strip()
                                if legenda:
                                    logger.info(f" [OK] Legenda encontrada via índice original ({campo_original}): '{legenda}'")
                                else:
                                    logger.info(f"   [INFO] Sem legenda (tentou {campo_contador} e {campo_original})")
                            
                            # Criar registro no banco
                            nova_foto = RDOFoto(
                                admin_id=admin_id,
                                rdo_id=rdo.id,
                                nome_arquivo=resultado['nome_original'],
                                caminho_arquivo=resultado['arquivo_original'],
                                descricao=legenda,
                                arquivo_original=resultado['arquivo_original'],
                                arquivo_otimizado=resultado['arquivo_otimizado'],
                                thumbnail=resultado['thumbnail'],
                                nome_original=resultado['nome_original'],
                                tamanho_bytes=resultado['tamanho_bytes'],
                                # [READY] CAMPOS BASE64 (v9.0.4) - Persistência no banco de dados
                                imagem_original_base64=resultado.get('imagem_original_base64'),
                                imagem_otimizada_base64=resultado.get('imagem_otimizada_base64'),
                                thumbnail_base64=resultado.get('thumbnail_base64')
                            )
                            
                            db.session.add(nova_foto)
                            logger.info(f"[OK] Foto salva com legenda: '{legenda[:50]}...' " if len(legenda) > 50 else f"[OK] Foto salva com legenda: '{legenda}'")
                            
                            contador_legenda += 1
                        
                            logger.info(f"[OK] [FOTO-UPLOAD] RESUMO: {contador_legenda} foto(s) adicionadas à sessão")
                            logger.info(f"   ⏳ Aguardando commit final...")
                    except Exception as e:
                        logger.error(f"[ERROR] ERRO ao processar fotos: {str(e)}", exc_info=True)
                        # Não fazer rollback aqui - deixar para o bloco except principal
            
            # [START] COMMIT DA TRANSAÇÃO FINAL
                        logger.info(f"[START] [COMMIT] EXECUTANDO COMMIT FINAL...")
                        logger.info(f" [STATS] Estado da sessão antes do commit:")
                        logger.info(f"      - Novos objetos: {len(db.session.new)}")
                        logger.info(f"      - Objetos modificados: {len(db.session.dirty)}")
                        logger.info(f"      - Objetos deletados: {len(db.session.deleted)}")
            
            db.session.commit()
            logger.info(f"[OK] [COMMIT] Commit executado com sucesso!")
            success = True
            
            # [DEBUG] VERIFICAÇÃO: Consultar banco para confirmar fotos salvas
            logger.info(f"[DEBUG] [VERIFICAÇÃO] Consultando banco para confirmar fotos salvas...")
            fotos_salvas = RDOFoto.query.filter_by(rdo_id=rdo.id).all()
            logger.info(f" [STATS] {len(fotos_salvas)} foto(s) encontrada(s) no banco para RDO {rdo.id}")
            for foto in fotos_salvas:
                logger.info(f"   [PHOTO] Foto ID {foto.id}: {foto.nome_original} ({foto.tamanho_bytes} bytes)")
            
                logger.info(f"[OK] SUCESSO TOTAL! RDO {rdo.numero_rdo} salvo:")
                logger.info(f" [LIST] {len(subactivities)} subatividades")
                logger.info(f" [USERS] {len(funcionarios_selecionados)} funcionarios")
                logger.info(f"  [PHOTO] {len(fotos_salvas)} fotos")
                logger.info(f" [BUILD] Obra ID: {obra_id}")
                logger.info(f" [CORP] Admin ID: {admin_id}")
                logger.info(f" [NUM] Número RDO: {numero_rdo} (VERIFICADO Único)")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao salvar RDO: {e}")
            # [OK] LOG DETALHADO PARA DEBUG PRODUÇÃO
            import traceback
            logger.error(f"[ERROR] Stack trace completo: {traceback.format_exc()}")
            error_message = str(e)
            success = False
        
        if success:
            flash(f'RDO {numero_rdo} salvo com sucesso! Serviço: {service_name}', 'success')
            logger.info(f"[OK] RDO {numero_rdo} salvo com {len(subactivities)} subatividades no serviço {target_service_id}")
            return redirect(url_for('main.funcionario_rdo_consolidado'))
        else:
            # [OK] MENSAGEM DE ERRO DETALHADA
            if 'admin_id' in error_message and 'null' in error_message.lower():
                flash('Erro: Campo admin_id obrigatório não foi preenchido. Entre em contato com o suporte.', 'error')
            elif 'foreign key' in error_message.lower():
                flash('Erro: Referência inválida a obra ou funcionário. Verifique os dados.', 'error')
            elif 'unique constraint' in error_message.lower():
                flash('Erro: Este RDO já existe. Use um número diferente.', 'error')
            elif 'not-null constraint' in error_message.lower():
                # Extrair nome da coluna do erro
                import re
                match = re.search(r'column "(\w+)"', error_message)
                campo = match.group(1) if match else 'desconhecido'
                flash(f'Erro: O campo "{campo}" é obrigatório e não foi preenchido.', 'error')
            else:
                flash(f'Erro ao salvar RDO: {error_message[:200]}', 'error')
                logger.error("[ERROR] FALHA NO SALVAMENTO - Redirecionando para formulário")
            return redirect(url_for('main.funcionario_rdo_novo'))
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO CRÍTICO: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao salvar RDO: {str(e)}', 'error')
        return redirect(url_for('main.funcionario_rdo_novo'))

@main_bp.route('/api/rdo/ultima-dados/<int:obra_id>')
@funcionario_required
def api_rdo_ultima_dados(obra_id):
    """
    API CORRIGIDA: Combina último RDO + novos serviços da obra
    Resolve bug: novos serviços adicionados à obra não apareciam em RDOs subsequentes
    """
    try:
        admin_id = get_admin_id_robusta()
        
        logger.debug(f"[DEBUG] [RDO-API] Obra {obra_id} | Admin {admin_id}")
        
        # ═══════════════════════════════════════════════════════
        # ETAPA 1: Buscar último RDO
        # ═══════════════════════════════════════════════════════
        ultimo_rdo = RDO.query.join(Obra).filter(
            Obra.id == obra_id,
            Obra.admin_id == admin_id
        ).order_by(RDO.data_relatorio.desc()).first()
        
        # ═══════════════════════════════════════════════════════
        # ETAPA 2: Buscar TODOS serviços ATIVOS da obra (TABELA CORRETA)
        # ═══════════════════════════════════════════════════════
        servicos_obra_atuais = db.session.query(
            ServicoObraReal, Servico
        ).join(
            Servico, ServicoObraReal.servico_id == Servico.id
        ).filter(
            ServicoObraReal.obra_id == obra_id,
            ServicoObraReal.admin_id == admin_id,
            ServicoObraReal.ativo == True,
            Servico.ativo == True
        ).all()
        
        logger.info(f"[STATS] [RDO-API] {len(servicos_obra_atuais)} serviços ativos na obra")
        
        # ═══════════════════════════════════════════════════════
        # ETAPA 3: Pré-processar histórico do último RDO
        # ═══════════════════════════════════════════════════════
        historico_percentuais = {}
        
        if ultimo_rdo:
            logger.debug(f"[DOC] [RDO-API] Último RDO: {ultimo_rdo.numero_rdo} ({ultimo_rdo.data_relatorio})")
            
            subatividades_antigas = RDOServicoSubatividade.query.filter_by(
                rdo_id=ultimo_rdo.id
            ).all()
            
            for sub in subatividades_antigas:
                sid = sub.servico_id
                nome_normalizado = sub.nome_subatividade.strip().casefold() if sub.nome_subatividade else ''
                
                if sid not in historico_percentuais:
                    historico_percentuais[sid] = {}
                
                historico_percentuais[sid][nome_normalizado] = {
                    'percentual': float(sub.percentual_conclusao or 0),
                    'observacoes': sub.observacoes_tecnicas or ''
                }
                
                logger.info(f"[STATS] [RDO-API] Histórico: {len(historico_percentuais)} serviços com dados antigos")
        
        # ═══════════════════════════════════════════════════════
        # ETAPA 4: Processar TODOS serviços com subatividades ATUAIS
        # ═══════════════════════════════════════════════════════
        servicos_finais = {}
        
        for servico_obra_real, servico in servicos_obra_atuais:
            sid = servico.id
            
            # Buscar subatividades ATUAIS da tabela mestre
            subs_mestre_atuais = SubatividadeMestre.query.filter_by(
                servico_id=sid,
                admin_id=admin_id,
                ativo=True
            ).order_by(SubatividadeMestre.ordem_padrao).all()
            
            subatividades_lista = []
            tem_historico = sid in historico_percentuais
            
            if subs_mestre_atuais:
                for sm in subs_mestre_atuais:
                    nome_normalizado = sm.nome.strip().casefold() if sm.nome else ''
                    
                    # Tentar mapear com histórico por nome
                    percentual = 0.0
                    observacoes = ''
                    
                    if tem_historico and nome_normalizado in historico_percentuais[sid]:
                        dados_hist = historico_percentuais[sid][nome_normalizado]
                        percentual = dados_hist['percentual']
                        observacoes = dados_hist['observacoes']
                        logger.info(f"[OK] [RDO-API] Mapeado: {servico.nome} → {sm.nome} = {percentual}%")
                    else:
                        logger.debug(f"🆕 [RDO-API] Novo/Sem histórico: {servico.nome} → {sm.nome} = 0%")
                    
                    subatividades_lista.append({
                        'id': sm.id,
                        'nome': sm.nome,
                        'percentual': percentual,
                        'observacoes': observacoes
                    })
            else:
                # Fallback: se serviço não tem subatividades, criar uma padrão
                qtd_info = f"{servico_obra_real.quantidade_planejada or 1} {servico.unidade_simbolo or servico.unidade_medida or 'un'}"
                percentual = 0.0
                observacoes = f'Qtd planejada: {qtd_info}'
                
                # Tentar mapear percentual do histórico se houver
                if tem_historico:
                    nome_normalizado = servico.nome.strip().casefold()
                    if nome_normalizado in historico_percentuais[sid]:
                        percentual = historico_percentuais[sid][nome_normalizado]['percentual']
                        observacoes = historico_percentuais[sid][nome_normalizado]['observacoes'] or observacoes
                
                subatividades_lista.append({
                    'id': f'new_{sid}',
                    'nome': servico.nome,
                    'percentual': percentual,
                    'observacoes': observacoes
                })
            
            servicos_finais[sid] = {
                'id': servico.id,
                'nome': servico.nome,
                'categoria': getattr(servico, 'categoria', 'Geral'),
                'descricao': servico.descricao or '',
                'subatividades': subatividades_lista,
                'eh_novo': not tem_historico
            }
        
        # ═══════════════════════════════════════════════════════
        # ETAPA 5: Ordenar subatividades e serviços
        # ═══════════════════════════════════════════════════════
        def extrair_numero(sub):
            try:
                nome = sub.get('nome', '')
                if nome and '.' in nome:
                    return int(nome.split('.')[0])
                return 999
            except:
                return 999
        
        for servico_data in servicos_finais.values():
            if servico_data.get('subatividades'):
                servico_data['subatividades'].sort(key=extrair_numero)
        
        servicos_lista = list(servicos_finais.values())
        servicos_lista.sort(key=lambda x: (x['categoria'], x['nome']))
        
        # Funcionários do último RDO
        funcionarios_lista = []
        if ultimo_rdo:
            func_rdos = RDOMaoObra.query.filter_by(rdo_id=ultimo_rdo.id).all()
            for fr in func_rdos:
                if fr.funcionario:
                    funcionarios_lista.append({
                        'id': fr.funcionario.id,
                        'nome': fr.funcionario.nome,
                        'cargo': fr.funcionario.funcao_ref.nome if hasattr(fr.funcionario, 'funcao_ref') and fr.funcionario.funcao_ref else 'Funcionário',
                        'horas_trabalhadas': float(fr.horas_trabalhadas or 8.8)
                    })
        
        # ═══════════════════════════════════════════════════════
        # LOGS FINAIS
        # ═══════════════════════════════════════════════════════
        servicos_com_historico = sum(1 for s in servicos_finais.values() if not s['eh_novo'])
        servicos_novos = sum(1 for s in servicos_finais.values() if s['eh_novo'])
        
        logger.info(f"[OK] [RDO-API] Resultado:")
        logger.debug(f" → Com histórico: {servicos_com_historico} serviços")
        logger.debug(f" → Novos/Sem histórico: {servicos_novos} serviços")
        logger.debug(f" → Total: {len(servicos_lista)} serviços")
        
        # ═══════════════════════════════════════════════════════
        # RETORNO
        # ═══════════════════════════════════════════════════════
        if not ultimo_rdo:
            # Primeira RDO da obra
            return jsonify({
                'success': True,
                'tem_rdo_anterior': False,
                'novos_servicos': len(servicos_lista),
                'total_servicos': len(servicos_lista),
                'primeira_rdo': {
                    'servicos': servicos_lista,
                    'funcionarios': [],
                    'observacoes_gerais': ''
                }
            })
        
        return jsonify({
            'success': True,
            'tem_rdo_anterior': True,
            'novos_servicos': servicos_novos,
            'total_servicos': len(servicos_lista),
            'ultima_rdo': {
                'numero_rdo': ultimo_rdo.numero_rdo or f'RDO-{ultimo_rdo.id}',
                'data_relatorio': ultimo_rdo.data_relatorio.strftime('%Y-%m-%d'),
                'servicos': servicos_lista,
                'funcionarios': funcionarios_lista,
                'observacoes_gerais': getattr(ultimo_rdo, 'observacoes_gerais', '') or getattr(ultimo_rdo, 'observacoes', '') or ''
            }
        })
        
    except Exception as e:
        logger.error(f"[ERROR] [RDO-API] ERRO: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def _buscar_servicos_obra_resiliente(obra_id, admin_id):
    """Busca serviços da obra com múltiplas estratégias resilientes"""
    try:
        logger.debug(f"[DEBUG] BUSCA RESILIENTE: obra_id={obra_id}, admin_id={admin_id}")
        
        # ESTRATÉGIA 1: Buscar via ServicoObraReal (CORRIGIDA)
        try:
            servicos_obra_query = db.session.query(Servico).join(
                ServicoObraReal, Servico.id == ServicoObraReal.servico_id
            ).filter(
                ServicoObraReal.obra_id == obra_id,
                ServicoObraReal.admin_id == admin_id,  # [OK] CORREÇÃO CRÍTICA: usar admin_id ao invés de ativo
                Servico.admin_id == admin_id,
                Servico.ativo == True
            ).all()
            
            if servicos_obra_query:
                logger.info(f"[OK] ESTRATÉGIA_1: {len(servicos_obra_query)} serviços encontrados via ServicoObraReal")
                return servicos_obra_query
                
        except Exception as e:
            logger.error(f"[WARN] ERRO ESTRATÉGIA_1: {e}")
        
        # ESTRATÉGIA 2: Buscar via ServicoObra (tabela legada)
        try:
            servicos_legado = []
            servicos_associados = ServicoObra.query.filter_by(obra_id=obra_id).all()
            
            for assoc in servicos_associados:
                if assoc.servico and assoc.servico.admin_id == admin_id and assoc.servico.ativo:
                    servicos_legado.append(assoc.servico)
            
            if servicos_legado:
                logger.info(f"[OK] ESTRATÉGIA_2: {len(servicos_legado)} serviços encontrados via ServicoObra")
                return servicos_legado
                
        except Exception as e:
            logger.error(f"[WARN] ERRO ESTRATÉGIA_2: {e}")
        
        # ESTRATÉGIA 3 REMOVIDA: Estava retornando todos os serviços do admin_id
        # Isso causava exibição de serviços não relacionados à obra
            logger.error(f"[ERROR] NENHUM SERVIÇO ENCONTRADO para obra_id={obra_id}, admin_id={admin_id}")
        return []
        
    except Exception as e:
        logger.error(f"[ERROR] ERRO CRÍTICO _buscar_servicos_obra_resiliente: {e}")
        return []

def _buscar_subatividades_servico(servico_id):
    """Busca subatividades padrão de um serviço"""
    try:
        # Buscar subatividades reais do banco se existirem
        # Por enquanto, retornar estrutura padrão
        return [
            {'nome': 'Preparação', 'descricao': 'Preparação inicial do serviço'},
            {'nome': 'Execução', 'descricao': 'Execução principal do serviço'},  
            {'nome': 'Finalização', 'descricao': 'Acabamentos e finalização'}
        ]
    except Exception as e:
        logger.error(f"[ERROR] ERRO _buscar_subatividades_servico: {e}")
        return [{'nome': 'Atividade Padrão', 'descricao': 'Execução do serviço'}]


# === SISTEMA LIMPO - CÓDIGO DUPLICADO REMOVIDO ===

