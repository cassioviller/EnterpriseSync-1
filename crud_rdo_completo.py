# CRUD COMPLETO DO RDO COM CARREGAMENTO CORRETO DAS SUBATIVIDADES
# Sistema moderno e robusto para gerenciamento de RDOs

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, RDO, Obra, Funcionario, RDOServicoSubatividade, RDOMaoObra, RDOEquipamento, RDOOcorrencia, SubatividadeMestre, NotificacaoCliente, RDOFoto
from datetime import datetime, date
import json

# Blueprint para RDO CRUD
rdo_crud_bp = Blueprint('rdo_crud', __name__, url_prefix='/rdo')

def get_admin_id():
    """Obter admin_id correto baseado no usuário atual"""
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        return current_user.admin_id
    elif hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario.name == 'FUNCIONARIO':
        # Para funcionários, buscar o admin_id através do email
        email_busca = "funcionario@valeverde.com" if current_user.email == "123@gmail.com" else current_user.email
        funcionario = Funcionario.query.filter_by(email=email_busca).first()
        if funcionario:
            return funcionario.admin_id
    return 10  # Fallback padrão

@rdo_crud_bp.route('/')
@login_required
def listar_rdos():
    """Listar RDOs com paginação e filtros"""
    try:
        admin_id = get_admin_id()
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtros
        obra_id = request.args.get('obra_id', type=int)
        status = request.args.get('status')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        # Query base
        query = db.session.query(RDO, Obra).join(
            Obra, RDO.obra_id == Obra.id
        ).filter(Obra.admin_id == admin_id)
        
        # Aplicar filtros
        if obra_id:
            query = query.filter(RDO.obra_id == obra_id)
        if status:
            query = query.filter(RDO.status == status)
        if data_inicio:
            query = query.filter(RDO.data_relatorio >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
        if data_fim:
            query = query.filter(RDO.data_relatorio <= datetime.strptime(data_fim, '%Y-%m-%d').date())
        
        # Ordenação
        query = query.order_by(RDO.data_relatorio.desc())
        
        # Paginação
        rdos_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Processar dados dos RDOs
        rdos_processados = []
        for rdo, obra in rdos_paginated.items:
            # Contadores
            total_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).count()
            total_funcionarios = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
            
            # FÓRMULA SIMPLES PROGRESSO
            subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()
            if subatividades:
                soma_perc = sum(s.percentual_conclusao for s in subatividades)
                total_sub = len(subatividades)
                progresso_medio = round(soma_perc / total_sub, 1)
                print(f"🎯 CRUD PROGRESSO RDO {rdo.id}: {soma_perc}÷{total_sub} = {progresso_medio}%")
            else:
                progresso_medio = 0
            
            rdos_processados.append({
                'rdo': rdo,
                'obra': obra,
                'total_subatividades': total_subatividades,
                'total_funcionarios': total_funcionarios,
                'progresso_medio': round(progresso_medio, 1),
                'status_cor': {
                    'Rascunho': 'warning',
                    'Finalizado': 'success',
                    'Aprovado': 'info'
                }.get(rdo.status, 'secondary')
            })
        
        # Dados para filtros
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
        
        return render_template('rdo_lista_unificada.html',
                             rdos=rdos_processados,
                             pagination=rdos_paginated,
                             total_rdos=rdos_paginated.total,
                             page=page,
                             admin_id=admin_id,
                             obras=obras,
                             funcionarios=[],
                             filters={
                                 'obra_id': obra_id,
                                 'status': status,
                                 'data_inicio': data_inicio,
                                 'data_fim': data_fim,
                                 'funcionario_id': None,
                                 'order_by': 'data_desc'
                             })
        
    except Exception as e:
        print(f"ERRO LISTAR RDOs: {str(e)}")
        flash('Erro ao carregar lista de RDOs.', 'error')
        return redirect(url_for('main.dashboard'))

@rdo_crud_bp.route('/novo')
@login_required
def novo_rdo():
    """Formulário para criar novo RDO"""
    try:
        admin_id = get_admin_id()
        
        # Dados necessários para o formulário
        obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        subatividades = SubatividadeMestre.query.order_by(SubatividadeMestre.servico_id, SubatividadeMestre.nome).all()
        
        # Obra pré-selecionada
        obra_id = request.args.get('obra_id', type=int)
        obra_selecionada = None
        if obra_id:
            obra_selecionada = next((obra for obra in obras if obra.id == obra_id), None)
        
        return render_template('rdo_form.html',
                             obras=obras,
                             funcionarios=funcionarios,
                             subatividades=subatividades,
                             obra_selecionada=obra_selecionada,
                             rdo=None,
                             acao='Criar')
        
    except Exception as e:
        print(f"ERRO NOVO RDO: {str(e)}")
        flash('Erro ao carregar formulário de RDO.', 'error')
        return redirect(url_for('rdo_crud.listar_rdos'))

@rdo_crud_bp.route('/editar/<int:rdo_id>')
@login_required
def editar_rdo(rdo_id):
    """Redirecionar para o blueprint oficial de edição de RDO"""
    return redirect(url_for('rdo_editar.editar_rdo_form', rdo_id=rdo_id))

@rdo_crud_bp.route('/visualizar/<int:rdo_id>')
@login_required
def visualizar_rdo(rdo_id):
    """Visualizar RDO em modo apenas leitura"""
    try:
        admin_id = get_admin_id()
        
        # Buscar RDO com dados completos
        rdo = RDO.query.join(Obra).filter(
            RDO.id == rdo_id,
            Obra.admin_id == admin_id
        ).first()
        
        if not rdo:
            flash('RDO não encontrado ou sem permissão de acesso.', 'error')
            return redirect(url_for('rdo_crud.listar_rdos'))
        
        # Carregar dados relacionados
        rdo_subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).all()
        rdo_funcionarios = db.session.query(RDOMaoObra, Funcionario).join(
            Funcionario, RDOMaoObra.funcionario_id == Funcionario.id
        ).filter(RDOMaoObra.rdo_id == rdo_id).all()
        rdo_equipamentos = RDOEquipamento.query.filter_by(rdo_id=rdo_id).all()
        rdo_ocorrencias = RDOOcorrencia.query.filter_by(rdo_id=rdo_id).all()
        
        # FÓRMULA SIMPLES ESTATÍSTICAS
        if rdo_subatividades:
            soma_perc = sum(s.percentual_conclusao for s in rdo_subatividades)
            total_sub = len(rdo_subatividades)
            progresso_total = round(soma_perc / total_sub, 1)
            print(f"🎯 CRUD VISUALIZAR PROGRESSO: {soma_perc}÷{total_sub} = {progresso_total}%")
        else:
            progresso_total = 0
        horas_totais = sum(mo.horas_trabalhadas for mo, _ in rdo_funcionarios)
        
        return render_template('rdo_visualizar.html',
                             rdo=rdo,
                             rdo_subatividades=rdo_subatividades,
                             rdo_funcionarios=rdo_funcionarios,
                             rdo_equipamentos=rdo_equipamentos,
                             rdo_ocorrencias=rdo_ocorrencias,
                             progresso_total=round(progresso_total, 1),
                             horas_totais=horas_totais)
        
    except Exception as e:
        print(f"ERRO VISUALIZAR RDO: {str(e)}")
        flash('Erro ao carregar RDO.', 'error')
        return redirect(url_for('rdo_crud.listar_rdos'))

@rdo_crud_bp.route('/salvar', methods=['POST'])
@login_required
def salvar_rdo():
    """Salvar RDO (criar ou editar)"""
    try:
        admin_id = get_admin_id()
        rdo_id = request.form.get('rdo_id', type=int)
        
        if rdo_id:
            # EDITAR RDO EXISTENTE
            rdo = RDO.query.join(Obra).filter(
                RDO.id == rdo_id,
                Obra.admin_id == admin_id
            ).first()
            
            if not rdo:
                flash('RDO não encontrado ou sem permissão de acesso.', 'error')
                return redirect(url_for('rdo_crud.listar_rdos'))
            
            if rdo.status != 'Rascunho':
                flash('Apenas RDOs em rascunho podem ser editados.', 'warning')
                return redirect(url_for('rdo_crud.visualizar_rdo', rdo_id=rdo_id))
            
            # Limpar dados antigos
            RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
            RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
            RDOEquipamento.query.filter_by(rdo_id=rdo.id).delete()
            RDOOcorrencia.query.filter_by(rdo_id=rdo.id).delete()
            
            print(f"DEBUG: Editando RDO {rdo.numero_rdo}")
            
        else:
            # CRIAR NOVO RDO
            obra_id = request.form.get('obra_id', type=int)
            data_relatorio = datetime.strptime(request.form.get('data_relatorio'), '%Y-%m-%d').date()
            
            # Verificar se obra existe e pertence ao admin
            obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra:
                flash('Obra não encontrada ou sem permissão de acesso.', 'error')
                return redirect(url_for('rdo_crud.novo_rdo'))
            
            # Verificar se já existe RDO para esta obra/data
            rdo_existente = RDO.query.filter_by(obra_id=obra_id, data_relatorio=data_relatorio).first()
            if rdo_existente:
                flash(f'Já existe um RDO para a obra "{obra.nome}" na data {data_relatorio.strftime("%d/%m/%Y")}.', 'warning')
                return redirect(url_for('rdo_crud.editar_rdo', rdo_id=rdo_existente.id))
            
            # Gerar número do RDO
            ano_atual = data_relatorio.year
            ultimo_numero = db.session.query(func.max(RDO.sequencial_ano)).filter(
                RDO.ano == ano_atual
            ).scalar() or 0
            
            rdo = RDO(
                numero_rdo=f'RDO-{ano_atual}-{ultimo_numero + 1:03d}',
                sequencial_ano=ultimo_numero + 1,
                ano=ano_atual,
                obra_id=obra_id,
                data_relatorio=data_relatorio,
                admin_id=admin_id,
                criado_por_id=current_user.id
            )
            
            print(f"DEBUG: Criando novo RDO {rdo.numero_rdo}")
        
        # Atualizar dados básicos do RDO
        rdo.clima_geral = request.form.get('clima_geral', '').strip()
        rdo.temperatura_media = request.form.get('temperatura_media', '').strip()
        rdo.umidade_relativa = request.form.get('umidade_relativa', type=int)
        rdo.vento_velocidade = request.form.get('vento_velocidade', '').strip()
        rdo.precipitacao = request.form.get('precipitacao', '').strip()
        rdo.condicoes_trabalho = request.form.get('condicoes_trabalho', '').strip()
        rdo.observacoes_climaticas = request.form.get('observacoes_climaticas', '').strip()
        rdo.comentario_geral = request.form.get('comentario_geral', '').strip()
        rdo.status = 'Rascunho'
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID
        
        # Processar subatividades
        subatividades_salvas = 0
        for key, value in request.form.items():
            if key.startswith('subatividade_') and key.endswith('_percentual'):
                try:
                    subatividade_id = int(key.split('_')[1])
                    percentual = float(value) if value else 0
                    
                    if percentual > 0:
                        obs_key = f'subatividade_{subatividade_id}_observacoes'
                        observacoes = request.form.get(obs_key, '').strip()
                        
                        subatividade = SubatividadeMestre.query.get(subatividade_id)
                        if subatividade:
                            rdo_subativ = RDOServicoSubatividade(
                                rdo_id=rdo.id,
                                nome_subatividade=subatividade.nome,
                                percentual_conclusao=percentual,
                                observacoes_tecnicas=observacoes,
                                admin_id=admin_id,
                                servico_id=subatividade.servico_id
                            )
                            db.session.add(rdo_subativ)
                            subatividades_salvas += 1
                            
                except (ValueError, IndexError) as e:
                    print(f"Erro ao processar subatividade {key}: {e}")
        
        # Processar funcionários
        funcionarios_salvos = 0
        for key, value in request.form.items():
            if key.startswith('funcionario_') and key.endswith('_horas'):
                try:
                    funcionario_id = int(key.split('_')[1])
                    horas = float(value) if value else 0
                    
                    if horas > 0:
                        funcionario = Funcionario.query.get(funcionario_id)
                        if funcionario:
                            mao_obra = RDOMaoObra(
                                rdo_id=rdo.id,
                                funcionario_id=funcionario_id,
                                funcao_exercida=funcionario.funcao_ref.nome if funcionario.funcao_ref else 'Geral',
                                horas_trabalhadas=horas,
                                admin_id=admin_id
                            )
                            db.session.add(mao_obra)
                            funcionarios_salvos += 1
                            
                except (ValueError, IndexError) as e:
                    print(f"Erro ao processar funcionário {key}: {e}")
        
        # Processar equipamentos
        equipamentos_json = request.form.get('equipamentos', '[]')
        equipamentos_salvos = 0
        if equipamentos_json and equipamentos_json != '[]':
            try:
                equipamentos_list = json.loads(equipamentos_json)
                for eq_data in equipamentos_list:
                    nome = eq_data.get('nome', '').strip()
                    if nome:
                        equipamento = RDOEquipamento(
                            rdo_id=rdo.id,
                            nome_equipamento=nome,
                            quantidade=int(eq_data.get('quantidade', 1)),
                            horas_utilizacao=float(eq_data.get('horas', 0)),
                            observacoes=eq_data.get('observacoes', '').strip(),
                            admin_id=admin_id
                        )
                        db.session.add(equipamento)
                        equipamentos_salvos += 1
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Erro ao processar equipamentos: {e}")
        
        # Processar ocorrências
        ocorrencias_json = request.form.get('ocorrencias', '[]')
        ocorrencias_salvas = 0
        if ocorrencias_json and ocorrencias_json != '[]':
            try:
                ocorrencias_list = json.loads(ocorrencias_json)
                for oc_data in ocorrencias_list:
                    descricao = oc_data.get('descricao', '').strip()
                    if descricao:
                        ocorrencia = RDOOcorrencia(
                            rdo_id=rdo.id,
                            tipo_ocorrencia=oc_data.get('tipo', 'Outros'),
                            descricao_completa=descricao,
                            severidade=oc_data.get('severidade', 'Baixa'),
                            responsavel_acao=oc_data.get('responsavel', '').strip(),
                            prazo_resolucao=datetime.strptime(oc_data.get('prazo'), '%Y-%m-%d').date() if oc_data.get('prazo') else None,
                            status_resolucao='Pendente',
                            criado_em=datetime.utcnow(),
                            admin_id=admin_id
                        )
                        db.session.add(ocorrencia)
                        ocorrencias_salvas += 1
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Erro ao processar ocorrências: {e}")
        
        db.session.commit()
        
        # Mensagem de sucesso
        acao = "editado" if rdo_id else "criado"
        flash(f'RDO {rdo.numero_rdo} {acao} com sucesso! '
              f'{subatividades_salvas} subatividades, {funcionarios_salvos} funcionários, '
              f'{equipamentos_salvos} equipamentos, {ocorrencias_salvas} ocorrências.', 'success')
        
        return redirect(url_for('rdo_crud.visualizar_rdo', rdo_id=rdo.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO SALVAR RDO: {str(e)}")
        error_message = str(e)
        
        # ✅ MENSAGEM DE ERRO DETALHADA
        if 'admin_id' in error_message and 'null' in error_message.lower():
            flash('Erro: Campo admin_id obrigatório não foi preenchido. Entre em contato com o suporte.', 'error')
        elif 'foreign key' in error_message.lower():
            flash('Erro: Referência inválida a obra ou funcionário. Verifique os dados selecionados.', 'error')
        elif 'unique constraint' in error_message.lower():
            flash('Erro: Este RDO já existe. Use um número diferente ou edite o RDO existente.', 'error')
        elif 'not-null constraint' in error_message.lower():
            # Extrair nome da coluna do erro
            import re
            match = re.search(r'column "(\w+)"', error_message)
            campo = match.group(1) if match else 'desconhecido'
            flash(f'Erro: O campo "{campo}" é obrigatório e não foi preenchido. Verifique os dados do formulário.', 'error')
        else:
            flash(f'Erro ao salvar RDO: {error_message[:200]}', 'error')
        
        return redirect(url_for('rdo_crud.listar_rdos'))

@rdo_crud_bp.route('/excluir/<int:rdo_id>', methods=['POST'])
@login_required
def excluir_rdo(rdo_id):
    """Excluir RDO"""
    try:
        admin_id = get_admin_id()
        
        rdo = RDO.query.join(Obra).filter(
            RDO.id == rdo_id,
            Obra.admin_id == admin_id
        ).first()
        
        if not rdo:
            flash('RDO não encontrado ou sem permissão de acesso.', 'error')
            return redirect(url_for('rdo_crud.listar_rdos'))
        
        if rdo.status != 'Rascunho':
            flash('Apenas RDOs em rascunho podem ser excluídos.', 'warning')
            return redirect(url_for('rdo_crud.visualizar_rdo', rdo_id=rdo_id))
        
        numero_rdo = rdo.numero_rdo
        
        # Excluir TODOS os dados relacionados (incluindo notificacoes e fotos!)
        NotificacaoCliente.query.filter_by(rdo_id=rdo.id).delete()
        RDOFoto.query.filter_by(rdo_id=rdo.id).delete()
        RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
        RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
        RDOEquipamento.query.filter_by(rdo_id=rdo.id).delete()
        RDOOcorrencia.query.filter_by(rdo_id=rdo.id).delete()
        
        # Excluir RDO
        db.session.delete(rdo)
        db.session.commit()
        
        flash(f'RDO {numero_rdo} excluído com sucesso.', 'success')
        return redirect(url_for('rdo_crud.listar_rdos'))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO EXCLUIR RDO: {str(e)}")
        flash(f'Erro ao excluir RDO: {str(e)}', 'error')
        return redirect(url_for('rdo_crud.listar_rdos'))

@rdo_crud_bp.route('/finalizar/<int:rdo_id>', methods=['POST'])
@login_required
def finalizar_rdo(rdo_id):
    """Finalizar RDO (mudar status para Finalizado)"""
    try:
        admin_id = get_admin_id()
        
        rdo = RDO.query.join(Obra).filter(
            RDO.id == rdo_id,
            Obra.admin_id == admin_id
        ).first()
        
        if not rdo:
            flash('RDO não encontrado ou sem permissão de acesso.', 'error')
            return redirect(url_for('rdo_crud.listar_rdos'))
        
        if rdo.status != 'Rascunho':
            flash('Apenas RDOs em rascunho podem ser finalizados.', 'warning')
            return redirect(url_for('rdo_crud.visualizar_rdo', rdo_id=rdo_id))
        
        # Verificar se tem dados mínimos
        subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo_id).count()
        funcionarios = RDOMaoObra.query.filter_by(rdo_id=rdo_id).count()
        
        if subatividades == 0 and funcionarios == 0:
            flash('RDO deve ter pelo menos uma subatividade ou funcionário para ser finalizado.', 'warning')
            return redirect(url_for('rdo_crud.editar_rdo', rdo_id=rdo_id))
        
        rdo.status = 'Finalizado'
        rdo.finalizado_em = datetime.utcnow()
        rdo.finalizado_por_id = current_user.id
        
        db.session.commit()
        
        flash(f'RDO {rdo.numero_rdo} finalizado com sucesso.', 'success')
        return redirect(url_for('rdo_crud.visualizar_rdo', rdo_id=rdo_id))
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO FINALIZAR RDO: {str(e)}")
        flash(f'Erro ao finalizar RDO: {str(e)}', 'error')
        return redirect(url_for('rdo_crud.visualizar_rdo', rdo_id=rdo_id))

@rdo_crud_bp.route('/api/subatividades/<int:servico_id>')
@login_required
def api_subatividades_por_servico(servico_id):
    """API para buscar subatividades por serviço"""
    try:
        subatividades = SubatividadeMestre.query.filter_by(servico_id=servico_id).order_by(SubatividadeMestre.nome).all()
        return jsonify([{
            'id': s.id,
            'nome': s.nome,
            'unidade_medida': s.unidade_medida,
            'quantidade_estimada': s.quantidade_estimada
        } for s in subatividades])
    except Exception as e:
        print(f"ERRO API SUBATIVIDADES: {str(e)}")
        return jsonify({'erro': str(e)}), 500

@rdo_crud_bp.route('/api/funcionarios')
@login_required
def api_funcionarios():
    """API para buscar funcionários ativos"""
    try:
        admin_id = get_admin_id()
        funcionarios = Funcionario.query.filter_by(
            admin_id=admin_id, 
            ativo=True
        ).order_by(Funcionario.nome).all()
        
        return jsonify([{
            'id': f.id,
            'nome': f.nome,
            'codigo': f.codigo,
            'funcao': f.funcao_ref.nome if f.funcao_ref else 'Geral',
            'email': f.email
        } for f in funcionarios])
    except Exception as e:
        print(f"ERRO API FUNCIONÁRIOS: {str(e)}")
        return jsonify({'erro': str(e)}), 500