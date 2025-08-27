# SEÇÃO RDO DO ARQUIVO views.py (LINHAS 1560-1665)
# Esta é a implementação da rota /rdo que está funcionando corretamente
# O problema NÃO está aqui, está no template base.html com dark theme

# ===== SISTEMA UNIFICADO DE RDO =====

@main_bp.route('/rdo')
@main_bp.route('/rdo/')
@main_bp.route('/rdo/lista')
@login_required
def rdo_lista_unificada():
    """Lista RDOs com controle de acesso e design moderno"""
    try:
        # Determinar admin_id baseado no tipo de usuário
        if current_user.tipo_usuario == TipoUsuario.ADMIN or current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
            admin_id = current_user.id if current_user.tipo_usuario == TipoUsuario.ADMIN else current_user.admin_id
        else:
            # Funcionário - buscar admin_id através do funcionário
            email_busca = "funcionario@valeverde.com" if current_user.email == "123@gmail.com" else current_user.email
            funcionario_atual = Funcionario.query.filter_by(email=email_busca).first()
            
            if not funcionario_atual:
                funcionario_atual = Funcionario.query.filter_by(admin_id=10, ativo=True).first()
            
            admin_id = funcionario_atual.admin_id if funcionario_atual else 10
        
        # Filtros
        obra_filter = request.args.get('obra_id', type=int)
        status_filter = request.args.get('status', '')
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        funcionario_filter = request.args.get('funcionario_id', type=int)
        
        # Base query com carregamento dos relacionamentos
        query = RDO.query.options(
            db.joinedload(RDO.obra),
            db.joinedload(RDO.criado_por),
            db.joinedload(RDO.servico_subatividades),
            db.joinedload(RDO.mao_obra).joinedload(RDOMaoObra.funcionario)
        ).join(Obra).filter(Obra.admin_id == admin_id)
        
        # Aplicar filtros
        if obra_filter:
            query = query.filter(RDO.obra_id == obra_filter)
        if status_filter:
            query = query.filter(RDO.status == status_filter)
        if data_inicio:
            query = query.filter(RDO.data_relatorio >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
        if data_fim:
            query = query.filter(RDO.data_relatorio <= datetime.strptime(data_fim, '%Y-%m-%d').date())
        if funcionario_filter:
            query = query.filter(RDO.criado_por_id == funcionario_filter)
        
        # Ordenação
        order_by = request.args.get('order_by', 'data_desc')
        if order_by == 'data_asc':
            query = query.order_by(RDO.data_relatorio.asc())
        elif order_by == 'obra':
            query = query.join(Obra).order_by(Obra.nome.asc())
        elif order_by == 'status':
            query = query.order_by(RDO.status.asc())
        else:  # data_desc (padrão)
            query = query.order_by(RDO.data_relatorio.desc())
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        rdos = query.paginate(page=page, per_page=20, error_out=False)
        
        # Calcular progresso total para cada RDO
        for rdo in rdos.items:
            try:
                if rdo.servico_subatividades:
                    # Usar percentual_conclusao ou 0 se for None
                    progressos = [sub.percentual_conclusao or 0 for sub in rdo.servico_subatividades]
                    progresso_total = sum(progressos) / len(progressos) if progressos else 0
                    rdo.progresso_total = round(progresso_total, 1)
                else:
                    rdo.progresso_total = 0
                
                # Calcular horas totais
                if rdo.mao_obra:
                    rdo.horas_totais = sum(mo.horas_trabalhadas or 0 for mo in rdo.mao_obra)
                else:
                    rdo.horas_totais = 0
            except Exception as calc_error:
                print(f"Erro calculando progresso RDO {rdo.id}: {calc_error}")
                rdo.progresso_total = 0
                rdo.horas_totais = 0
        
        # Obras e funcionários para filtros
        obras = Obra.query.filter_by(admin_id=admin_id).order_by(Obra.nome).all()
        funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()
        
        print(f"DEBUG LISTA RDOs: {rdos.total} RDOs encontrados para admin_id={admin_id}")
        if rdos.items:
            print(f"DEBUG: Mostrando página {page} com {len(rdos.items)} RDOs")
            for rdo in rdos.items[:3]:
                print(f"DEBUG RDO {rdo.id}: {len(rdo.servico_subatividades)} subatividades, {len(rdo.mao_obra)} funcionários, {rdo.progresso_total}% progresso")
        
        # ESTA LINHA ESTÁ CORRETA - RENDERIZA O TEMPLATE CERTO
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
                                 'order_by': order_by
                             })
        
    except Exception as e:
        print(f"ERRO LISTA RDO: {str(e)}")
        flash('Erro ao carregar lista de RDOs.', 'error')
        return redirect(url_for('main.dashboard'))