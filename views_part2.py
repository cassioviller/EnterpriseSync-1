                    
                    if descricao and percentual:
                        from models import RDOAtividade
                        atividade = RDOAtividade(
                            rdo_id=rdo.id,
                            descricao_atividade=descricao,
                            percentual_conclusao=float(percentual),
                            observacoes_tecnicas=observacoes if observacoes else None
                        )
                        db.session.add(atividade)
        
        db.session.commit()
        
        flash('RDO criado com sucesso!', 'success')
        return redirect(url_for('main.visualizar_rdo', id=rdo.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar RDO: {str(e)}', 'error')
        return redirect(url_for('main.novo_rdo'))

@main_bp.route('/rdo/<int:id>')
@login_required
def visualizar_rdo(id):
    """Visualizar detalhes de um RDO"""
    rdo = RDO.query.get_or_404(id)
    return render_template('rdo/visualizar_rdo.html', rdo=rdo)

@main_bp.route('/rdo/<int:id>/editar')
@login_required
def editar_rdo(id):
    """Formulário para editar RDO"""
    rdo = RDO.query.get_or_404(id)
    obras = Obra.query.all()
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('rdo/formulario_rdo.html', 
                         rdo=rdo,
                         obras=obras,
                         funcionarios=funcionarios,
                         modo='editar')

@main_bp.route('/api/rdo/atividades-anteriores/<int:obra_id>')
@login_required
def api_atividades_anteriores(obra_id):
    """API para buscar atividades da RDO anterior de uma obra"""
    try:
        # Buscar RDO mais recente da obra (excluindo a data atual)
        data_hoje = request.args.get('data_atual')
        query = RDO.query.filter_by(obra_id=obra_id)
        
        # Excluir a data atual se fornecida
        if data_hoje:
            query = query.filter(RDO.data_relatorio < datetime.strptime(data_hoje, '%Y-%m-%d').date())
        
        rdo_anterior = query.order_by(RDO.data_relatorio.desc()).first()
        
        if not rdo_anterior or not rdo_anterior.atividades:
            return jsonify({
                'success': True,
                'atividades': [],
                'message': 'Nenhuma atividade anterior encontrada'
            })
        
        atividades = [{
            'descricao': atividade.descricao_atividade,
            'percentual': atividade.percentual_conclusao,
            'observacoes': atividade.observacoes_tecnicas or '',
            'rdo_anterior': rdo_anterior.numero_rdo,
            'data_anterior': rdo_anterior.data_relatorio.strftime('%d/%m/%Y')
        } for atividade in rdo_anterior.atividades]
        
        return jsonify({
            'success': True,
            'atividades': atividades,
            'rdo_anterior': rdo_anterior.numero_rdo,
            'data_anterior': rdo_anterior.data_relatorio.strftime('%d/%m/%Y'),
            'message': f'{len(atividades)} atividades encontradas do RDO {rdo_anterior.numero_rdo}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar atividades anteriores: {str(e)}'
        }), 500

@main_bp.route('/rdo/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_rdo(id):
    """Excluir RDO"""
    try:
        rdo = RDO.query.get_or_404(id)
        db.session.delete(rdo)
        db.session.commit()
        
        flash('RDO excluído com sucesso!', 'success')
        return redirect(url_for('main.lista_rdos'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir RDO: {str(e)}', 'error')
        return redirect(url_for('main.lista_rdos'))

@main_bp.route('/financeiro/centros-custo/novo', methods=['GET', 'POST'])
@login_required
def novo_centro_custo():
    """Criar novo centro de custo"""
    from financeiro import gerar_codigo_centro_custo
    
    if request.method == 'POST':
        try:
            centro = CentroCusto(
                codigo=request.form.get('codigo'),
                nome=request.form.get('nome'),
                descricao=request.form.get('descricao'),
                tipo=request.form.get('tipo'),
                obra_id=int(request.form.get('obra_id')) if request.form.get('obra_id') != '0' else None,
                departamento_id=int(request.form.get('departamento_id')) if request.form.get('departamento_id') != '0' else None,
                ativo=bool(request.form.get('ativo'))
            )
            
            db.session.add(centro)
            db.session.commit()
            flash('Centro de custo cadastrado com sucesso!', 'success')
            return redirect(url_for('main.centros_custo'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar centro de custo: {str(e)}', 'error')
    
    # Dados para formulário
    obras = Obra.query.all()
    departamentos = Departamento.query.all()
    codigo_padrao = gerar_codigo_centro_custo()
    
    return render_template('financeiro/centro_custo_form.html', 
                         titulo='Novo Centro de Custo',
                         codigo_padrao=codigo_padrao,
                         obras=obras,
                         departamentos=departamentos)

@main_bp.route('/financeiro/sincronizar-fluxo', methods=['POST'])
@login_required
def sincronizar_fluxo():
    """Sincronizar dados do fluxo de caixa"""
    try:
        from financeiro import sincronizar_fluxo_caixa
        sincronizar_fluxo_caixa()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Fluxo de caixa sincronizado com sucesso!'})
        else:
            flash('Fluxo de caixa sincronizado com sucesso!', 'success')
            return redirect(url_for('main.fluxo_caixa'))
    except Exception as e:
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)})
        else:
            flash(f'Erro ao sincronizar fluxo de caixa: {str(e)}', 'error')
            return redirect(url_for('main.fluxo_caixa'))

@main_bp.route('/horarios')
@login_required
def horarios():
    """Página de gestão de horários de trabalho"""
    horarios = HorarioTrabalho.query.all()
    return render_template('horarios.html', horarios=horarios)

@main_bp.route('/horarios/novo', methods=['POST'])
@login_required
def novo_horario():
    """Criar novo horário de trabalho"""
    try:
        nome = request.form.get('nome')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        retorno_almoco = request.form.get('retorno_almoco')
        saida = request.form.get('saida')
        dias_semana = request.form.get('dias_semana')
        
        # Verificar se já existe horário com o mesmo nome
        horario_existente = HorarioTrabalho.query.filter_by(nome=nome).first()
        if horario_existente:
            flash('Já existe um horário com este nome!', 'error')
            return redirect(url_for('main.horarios'))
        
        # Calcular horas diárias
        entrada_time = datetime.strptime(entrada, '%H:%M').time()
        saida_almoco_time = datetime.strptime(saida_almoco, '%H:%M').time()
        retorno_almoco_time = datetime.strptime(retorno_almoco, '%H:%M').time()
        saida_time = datetime.strptime(saida, '%H:%M').time()
        
        # Calcular horas trabalhadas (manhã + tarde)
        manha_inicio = datetime.combine(date.today(), entrada_time)
        manha_fim = datetime.combine(date.today(), saida_almoco_time)
        tarde_inicio = datetime.combine(date.today(), retorno_almoco_time)
        tarde_fim = datetime.combine(date.today(), saida_time)
        
        horas_manha = (manha_fim - manha_inicio).total_seconds() / 3600
        horas_tarde = (tarde_fim - tarde_inicio).total_seconds() / 3600
        horas_diarias = horas_manha + horas_tarde
        
        # Calcular valor da hora (baseado no salário mínimo padrão)
        valor_hora = 12.00  # Valor padrão, pode ser ajustado
        
        # Criar horário
        horario = HorarioTrabalho(
            nome=nome,
            entrada=entrada_time,
            saida_almoco=saida_almoco_time,
            retorno_almoco=retorno_almoco_time,
            saida=saida_time,
            dias_semana=dias_semana,
            horas_diarias=horas_diarias,
            valor_hora=valor_hora
        )
        
        db.session.add(horario)
        db.session.commit()
        
        flash('Horário de trabalho criado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

@main_bp.route('/horarios/editar/<int:id>', methods=['POST'])
@login_required
def editar_horario(id):
    """Editar horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        
        nome = request.form.get('nome')
        entrada = request.form.get('entrada')
        saida_almoco = request.form.get('saida_almoco')
        retorno_almoco = request.form.get('retorno_almoco')
        saida = request.form.get('saida')
        dias_semana = request.form.get('dias_semana')
        
        # Verificar se já existe outro horário com o mesmo nome
        horario_existente = HorarioTrabalho.query.filter(
            HorarioTrabalho.nome == nome,
            HorarioTrabalho.id != id
        ).first()
        if horario_existente:
            flash('Já existe um horário com este nome!', 'error')
            return redirect(url_for('main.horarios'))
        
        # Calcular horas diárias
        entrada_time = datetime.strptime(entrada, '%H:%M').time()
        saida_almoco_time = datetime.strptime(saida_almoco, '%H:%M').time()
        retorno_almoco_time = datetime.strptime(retorno_almoco, '%H:%M').time()
        saida_time = datetime.strptime(saida, '%H:%M').time()
        
        # Calcular horas trabalhadas (manhã + tarde)
        manha_inicio = datetime.combine(date.today(), entrada_time)
        manha_fim = datetime.combine(date.today(), saida_almoco_time)
        tarde_inicio = datetime.combine(date.today(), retorno_almoco_time)
        tarde_fim = datetime.combine(date.today(), saida_time)
        
        horas_manha = (manha_fim - manha_inicio).total_seconds() / 3600
        horas_tarde = (tarde_fim - tarde_inicio).total_seconds() / 3600
        horas_diarias = horas_manha + horas_tarde
        
        # Atualizar horário
        horario.nome = nome
        horario.entrada = entrada_time
        horario.saida_almoco = saida_almoco_time
        horario.retorno_almoco = retorno_almoco_time
        horario.saida = saida_time
        horario.dias_semana = dias_semana
        horario.horas_diarias = horas_diarias
        
        db.session.commit()
        
        flash('Horário de trabalho atualizado com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

@main_bp.route('/horarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_horario(id):
    """Excluir horário de trabalho"""
    try:
        horario = HorarioTrabalho.query.get_or_404(id)
        
        # Verificar se há funcionários usando este horário
        funcionarios_usando = Funcionario.query.filter_by(horario_trabalho_id=id).count()
        if funcionarios_usando > 0:
            flash(f'Não é possível excluir. Existem {funcionarios_usando} funcionários usando este horário.', 'error')
            return redirect(url_for('main.horarios'))
        
        db.session.delete(horario)
        db.session.commit()
        
        flash('Horário de trabalho excluído com sucesso!', 'success')
        return redirect(url_for('main.horarios'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir horário: {str(e)}', 'error')
        return redirect(url_for('main.horarios'))

# ==========================================
# MÓDULOS CRUD - CONTROLE DE PONTO, OUTROS CUSTOS E ALIMENTAÇÃO
# ==========================================

@main_bp.route('/controle-ponto')
@login_required
def controle_ponto():
    """Página principal do controle de ponto"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_registro = request.args.get('tipo_registro')
    
    # Query base com filtro de tenant - CORREÇÃO CRÍTICA para multi-tenancy
    query = RegistroPonto.query.join(Funcionario).filter(
        Funcionario.admin_id == current_user.id
    )
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
    
    if data_inicio:
        query = query.filter(RegistroPonto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroPonto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo_registro:
        query = query.filter(RegistroPonto.tipo_registro == tipo_registro)
    
    # Buscar registros com joins
    registros = query.options(
        joinedload(RegistroPonto.funcionario),
        joinedload(RegistroPonto.obra)
    ).order_by(RegistroPonto.data.desc()).all()
    
    # Dados para formulário - também com filtro de tenant
    funcionarios = Funcionario.query.filter_by(
        admin_id=current_user.id, 
        ativo=True
    ).order_by(Funcionario.nome).all()
    
    obras = Obra.query.filter_by(
        admin_id=current_user.id,
        status='Em andamento'
    ).order_by(Obra.nome).all()
    
    # Calcular valor total das horas extras com base na legislação brasileira
    from calendar import monthrange
    total_valor_extras = 0.0
    
    for registro in registros:
        if registro.horas_extras and registro.horas_extras > 0 and registro.funcionario:
            funcionario = registro.funcionario
            
            if funcionario.salario:
                # Calcular dias úteis reais do mês do registro
                ano = registro.data.year
                mes = registro.data.month
                
                # Contar dias úteis (seg-sex) no mês específico
                import calendar
                dias_uteis = 0
                primeiro_dia, ultimo_dia = monthrange(ano, mes)
                
                for dia in range(1, ultimo_dia + 1):
                    data_check = registro.data.replace(day=dia)
                    # 0=segunda, 1=terça, ..., 6=domingo
                    if data_check.weekday() < 5:  # Segunda a sexta
                        dias_uteis += 1
                
                # Usar horário específico do funcionário
                if funcionario.horario_trabalho and funcionario.horario_trabalho.horas_diarias:
                    horas_diarias = funcionario.horario_trabalho.horas_diarias
                else:
                    horas_diarias = 8.8  # Padrão Carlos Alberto
                
                # Horas mensais = horas/dia × dias úteis do mês
                horas_mensais = horas_diarias * dias_uteis
                valor_hora_normal = funcionario.salario / horas_mensais
                
                # Multiplicador conforme legislação brasileira (CLT)
                if registro.tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                    multiplicador = 2.0  # 100% adicional
                else:
                    multiplicador = 1.5  # 50% adicional padrão
                
                valor_extras_registro = registro.horas_extras * valor_hora_normal * multiplicador
                total_valor_extras += valor_extras_registro
    
    return render_template('controle_ponto.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         obras=obras,
                         total_valor_extras=total_valor_extras)

@main_bp.route('/ponto/registro', methods=['POST'])
@login_required
def criar_registro_ponto():
    """Criar novo registro de ponto com suporte completo a fins de semana"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_registro = request.form.get('tipo_registro', 'trabalho_normal')
        obra_id = request.form.get('obra_id') or None
        
        # ✅ PERMITIR LANÇAMENTOS EM QUALQUER DIA DA SEMANA
        # Verificar se já existe registro para esta data e funcionário
        registro_existente = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data
        ).first()
        
        if registro_existente:
            return jsonify({'error': 'Já existe um registro de ponto para esta data.'}), 400
        
        print(f"🎯 Criando registro para {data.strftime('%d/%m/%Y')} - Tipo: {tipo_registro}")
        
        # Criar registro
        registro = RegistroPonto(
            funcionario_id=funcionario_id,
            data=data,
            tipo_registro=tipo_registro,
            obra_id=obra_id
        )
        
        # Adicionar horários se não for falta
        if tipo_registro not in ['falta', 'falta_justificada']:
            entrada = request.form.get('entrada')
            saida_almoco = request.form.get('saida_almoco')
            retorno_almoco = request.form.get('retorno_almoco')
            saida = request.form.get('saida')
            
            if entrada:
                registro.hora_entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.hora_almoco_saida = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.hora_almoco_retorno = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.hora_saida = datetime.strptime(saida, '%H:%M').time()
        
        # Percentual de extras baseado no tipo
        if tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
            registro.percentual_extras = 50.0
        elif tipo_registro in ['domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
            registro.percentual_extras = 100.0
        else:
            percentual_extras = request.form.get('percentual_extras')
            registro.percentual_extras = float(percentual_extras) if percentual_extras else 0.0
        
        # Observações
        registro.observacoes = request.form.get('observacoes')
        
        # ✅ APLICAR LÓGICA ESPECIAL PARA FINS DE SEMANA
        dia_semana = data.weekday()  # 0=segunda, 5=sábado, 6=domingo
        
        if dia_semana == 5 and tipo_registro in ['trabalho_normal', 'sabado_trabalhado']:
            # Sábado trabalhado
            print("✅ CONFIGURANDO SÁBADO TRABALHADO")
            registro.tipo_registro = 'sabado_trabalhado'
            registro.percentual_extras = 50.0
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            
        elif dia_semana == 6 and tipo_registro in ['trabalho_normal', 'domingo_trabalhado']:
            # Domingo trabalhado
            print("✅ CONFIGURANDO DOMINGO TRABALHADO")
            registro.tipo_registro = 'domingo_trabalhado'
            registro.percentual_extras = 100.0
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
        
        db.session.add(registro)
        db.session.commit()
        
        print(f"✅ Registro criado com sucesso: {registro.id} - {tipo_registro}")
        
        return jsonify({
            'success': True,
            'message': f'Registro de ponto criado para {data.strftime("%d/%m/%Y")}',
            'registro_id': registro.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['GET', 'PUT'])
@login_required
def editar_registro_ponto(registro_id):
    """Sistema completo de edição de registros de ponto"""
    try:
        registro = RegistroPonto.query.get_or_404(registro_id)
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        # Verificar permissões
        if not verificar_permissao_edicao_ponto(registro, current_user):
            print(f"❌ Permissão negada para {current_user.email} editar registro {registro_id}")
            return jsonify({'error': 'Sem permissão para editar este registro'}), 403
        
        if request.method == 'GET':
            # Retornar dados para edição
            return jsonify({
                'success': True,
                'registro': serializar_registro_completo(registro, funcionario),
                'obras_disponiveis': obter_obras_usuario(current_user),
                'tipos_registro': obter_tipos_registro_validos()
            })
            
        elif request.method == 'PUT':
            # Processar edição
            dados = request.get_json()
            
            # Validar dados de entrada
            validacao = validar_dados_edicao_ponto(dados, registro)
            if not validacao['valido']:
                return jsonify({'success': False, 'error': validacao['erro']})
            
            # Aplicar alterações
            aplicar_edicao_registro(registro, dados)
            
            # Recalcular valores baseado no tipo
            recalcular_registro_automatico(registro)
            
            # Salvar alterações
            db.session.commit()
            
            print(f"✅ Registro {registro_id} editado por {current_user.email}")
            
            return jsonify({
                'success': True,
                'message': 'Registro atualizado com sucesso!',
                'registro': serializar_registro_completo(registro, funcionario)
            })
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao editar registro {registro_id}: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

def verificar_permissao_edicao_ponto(registro, usuario):
    """Verifica permissões para editar registro"""
    print(f"🔍 Verificando permissão: usuário {usuario.email} ({usuario.tipo_usuario})")
    
    # Usar o enum corretamente
    from models import TipoUsuario
    
    if usuario.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        print("✅ Permissão concedida: SUPER_ADMIN")
        return True
    elif usuario.tipo_usuario == TipoUsuario.ADMIN:
        # Admin pode editar registros de funcionários sob sua gestão
        funcionario = Funcionario.query.get(registro.funcionario_id)
        if funcionario:
            pode_editar = funcionario.admin_id == usuario.id
            print(f"🔍 Admin {usuario.id} vs Funcionário admin_id {funcionario.admin_id}: {'✅' if pode_editar else '❌'}")
            return pode_editar
        else:
            print("❌ Funcionário não encontrado")
            return False
    else:
        print(f"❌ Tipo de usuário {usuario.tipo_usuario} não pode editar")
        return False

def serializar_registro_completo(registro, funcionario):
    """Serializa registro completo para frontend"""
    # Mapear tipos do banco para frontend
    tipo_frontend = mapear_tipo_para_frontend(registro.tipo_registro)
    
    return {
        'id': registro.id,
        'funcionario': {
            'id': funcionario.id,
            'nome': funcionario.nome,
            'codigo': funcionario.codigo
        },
        'data': registro.data.strftime('%Y-%m-%d'),
        'data_formatada': registro.data.strftime('%d/%m/%Y'),
        'dia_semana': registro.data.strftime('%A'),
        'tipo_registro': tipo_frontend,
        'horarios': {
            'entrada': registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else '',
            'almoco_saida': registro.hora_almoco_saida.strftime('%H:%M') if registro.hora_almoco_saida else '',
            'almoco_retorno': registro.hora_almoco_retorno.strftime('%H:%M') if registro.hora_almoco_retorno else '',
            'saida': registro.hora_saida.strftime('%H:%M') if registro.hora_saida else ''
        },
        'valores_calculados': {
            'horas_trabalhadas': float(registro.horas_trabalhadas or 0),
            'horas_extras': float(registro.horas_extras or 0),
            'percentual_extras': float(registro.percentual_extras or 0),
            'total_atraso_horas': float(registro.total_atraso_horas or 0),
            'total_atraso_minutos': int(registro.total_atraso_minutos or 0)
        },
        'obra_id': registro.obra_id,
        'observacoes': registro.observacoes or '',
        'horario_padrao': obter_horario_padrao_funcionario(funcionario)
    }

def mapear_tipo_para_frontend(tipo_banco):
    """Mapeia tipos do banco para o frontend"""
    mapeamento = {
        'trabalhado': 'trabalho_normal',
        'sabado_horas_extras': 'sabado_trabalhado',
        'domingo_horas_extras': 'domingo_trabalhado',
        'feriado': 'feriado_folga',
        'feriado_trabalhado': 'feriado_trabalhado',
        'falta_justificada': 'falta_justificada',
        'falta': 'falta',
        'ferias': 'ferias'
    }
    return mapeamento.get(tipo_banco, tipo_banco)

def mapear_tipo_para_banco(tipo_frontend):
    """Mapeia tipos do frontend para o banco"""
    mapeamento = {
        'trabalho_normal': 'trabalhado',
        'sabado_trabalhado': 'sabado_horas_extras',
        'domingo_trabalhado': 'domingo_horas_extras',
        'feriado_folga': 'feriado',
        'feriado_trabalhado': 'feriado_trabalhado',
        'falta_justificada': 'falta_justificada',
        'falta': 'falta',
        'ferias': 'ferias'
    }
    return mapeamento.get(tipo_frontend, tipo_frontend)

def obter_horario_padrao_funcionario(funcionario):
    """Retorna horário padrão do funcionário"""
    if funcionario.horario_trabalho_id:
        horario = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
        if horario:
            return {
                'entrada': horario.entrada.strftime('%H:%M') if horario.entrada else '08:00',
                'saida': horario.saida.strftime('%H:%M') if horario.saida else '17:00',
                'almoco_saida': horario.saida_almoco.strftime('%H:%M') if horario.saida_almoco else '12:00',
                'almoco_retorno': horario.retorno_almoco.strftime('%H:%M') if horario.retorno_almoco else '13:00'
            }
    return {
        'entrada': '08:00',
        'saida': '17:00', 
        'almoco_saida': '12:00',
        'almoco_retorno': '13:00'
    }

# ===== EXCLUSÃO EM LOTE =====
@main_bp.route('/ponto/preview-exclusao', methods=['POST'])
@login_required
def preview_exclusao_periodo():
    """Preview dos registros que serão excluídos"""
    try:
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        funcionario_id = request.form.get('funcionario_id')
        
        if not data_inicio or not data_fim:
            return jsonify({'success': False, 'message': 'Datas são obrigatórias'})
        
        # Converter datas
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Query com filtro de tenant
        query = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == current_user.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        )
        
        # Filtro adicional por funcionário se especificado
        if funcionario_id:
            query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
            funcionario = Funcionario.query.get(funcionario_id)
            nome_funcionario = funcionario.nome if funcionario else 'Funcionário não encontrado'
        else:
            nome_funcionario = None
        
        registros = query.all()
        
        # Tipos de registro encontrados
        tipos_registro = list(set([r.tipo_registro for r in registros]))
        
        return jsonify({
            'success': True,
            'data_inicio': data_inicio.strftime('%d/%m/%Y'),
            'data_fim': data_fim.strftime('%d/%m/%Y'),
            'funcionario': nome_funcionario,
            'total_registros': len(registros),
            'tipos_registro': tipos_registro
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

@main_bp.route('/ponto/excluir-periodo', methods=['POST'])
@login_required
def excluir_registros_periodo():
    """Excluir registros de ponto por período"""
    try:
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        funcionario_id = request.form.get('funcionario_id')
        
        if not data_inicio or not data_fim:
            return jsonify({'success': False, 'message': 'Datas são obrigatórias'})
        
        # Converter datas
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Query com filtro de tenant
        query = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == current_user.id,
            RegistroPonto.data >= data_inicio,
            RegistroPonto.data <= data_fim
        )
        
        # Filtro adicional por funcionário se especificado
        if funcionario_id:
            query = query.filter(RegistroPonto.funcionario_id == funcionario_id)
        
        # Buscar registros para excluir
        registros = query.all()
        total_registros = len(registros)
        
        # Excluir registros
        for registro in registros:
            db.session.delete(registro)
        
        db.session.commit()
        
        print(f"✅ {total_registros} registros excluídos por {current_user.email} (período: {data_inicio} a {data_fim})")
        
        return jsonify({
            'success': True,
            'message': f'{total_registros} registros excluídos com sucesso',
            'registros_excluidos': total_registros
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao excluir registros: {e}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

# ===== SCRIPT DE MIGRAÇÃO PARA PRODUÇÃO =====

def obter_obras_usuario(usuario):
    """Retorna obras disponíveis para o usuário"""
    from models import TipoUsuario
    
    if usuario.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        obras = Obra.query.filter_by(ativo=True).all()
    else:
        obras = Obra.query.filter_by(admin_id=usuario.id, ativo=True).all()
    
    return [{'id': obra.id, 'nome': obra.nome} for obra in obras]

def obter_tipos_registro_validos():
    """Retorna tipos de registro válidos"""
    return [
        {'valor': 'trabalho_normal', 'nome': 'Trabalho Normal'},
        {'valor': 'sabado_trabalhado', 'nome': 'Sábado - Horas Extras'},
        {'valor': 'domingo_trabalhado', 'nome': 'Domingo - Horas Extras'},
        {'valor': 'feriado_trabalhado', 'nome': 'Feriado Trabalhado'},
        {'valor': 'meio_periodo', 'nome': 'Meio Período'},
        {'valor': 'falta', 'nome': 'Falta'},
        {'valor': 'falta_justificada', 'nome': 'Falta Justificada'},
        {'valor': 'ferias', 'nome': 'Férias'},
        {'valor': 'feriado_folga', 'nome': 'Feriado Normal'},
        {'valor': 'sabado_folga', 'nome': 'Sábado - Folga'},
        {'valor': 'domingo_folga', 'nome': 'Domingo - Folga'}
    ]

def validar_dados_edicao_ponto(dados, registro):
    """Valida dados de edição com regras robustas"""
    erros = []
    
    # Validar tipo de registro (pode vir como tipo_lancamento ou tipo_registro)
    tipos_validos = [t['valor'] for t in obter_tipos_registro_validos()]
    tipo_recebido = dados.get('tipo_lancamento') or dados.get('tipo_registro')
    
    print(f"🔍 Validando tipo: recebido='{tipo_recebido}', válidos={tipos_validos}")
    
    if tipo_recebido not in tipos_validos:
        erros.append(f'Tipo de registro inválido: {tipo_recebido}')
    
    # Validar horários para tipos que trabalham
    tipos_trabalhados = ['trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado', 'meio_periodo']
    
    if tipo_recebido in tipos_trabalhados:
        if not dados.get('hora_entrada') or not dados.get('hora_saida'):
            erros.append('Horários de entrada e saída são obrigatórios')
        
        # Validar formato de horários
        for campo in ['hora_entrada', 'hora_saida', 'hora_almoco_saida', 'hora_almoco_retorno']:
            valor = dados.get(campo)
            if valor and not validar_formato_hora(valor):
                erros.append(f'Formato inválido para {campo}')
        
        # Validar sequência lógica
        if dados.get('hora_entrada') and dados.get('hora_saida'):
            if not validar_sequencia_horarios_edicao(dados):
                erros.append('Sequência de horários inválida')
    
    return {
        'valido': len(erros) == 0,
        'erro': '; '.join(erros) if erros else None
    }

def validar_formato_hora(hora_str):
    """Valida formato HH:MM"""
    try:
        datetime.strptime(hora_str, '%H:%M')
        return True
    except ValueError:
        return False

def validar_sequencia_horarios_edicao(dados):
    """Valida se horários estão em sequência lógica"""
    try:
        horarios = []
        
        for campo in ['hora_entrada', 'hora_almoco_saida', 'hora_almoco_retorno', 'hora_saida']:
            valor = dados.get(campo)
            if valor:
                horarios.append(datetime.strptime(valor, '%H:%M').time())
        
        # Verificar ordem crescente
        for i in range(1, len(horarios)):
            if horarios[i] <= horarios[i-1]:
                return False
        
        return True
    except ValueError:
        return False

def aplicar_edicao_registro(registro, dados):
    """Aplica edições ao registro"""
    # Mapear tipo para banco (pode vir como tipo_lancamento ou tipo_registro)
    tipo_recebido = dados.get('tipo_lancamento') or dados.get('tipo_registro')
    tipo_banco = mapear_tipo_para_banco(tipo_recebido)
    registro.tipo_registro = tipo_banco
    
    print(f"🔄 Aplicando edição: tipo '{tipo_recebido}' → banco '{tipo_banco}'")
    
    # Atualizar horários
    for campo_front, campo_banco in [
        ('hora_entrada', 'hora_entrada'),
        ('hora_almoco_saida', 'hora_almoco_saida'),
        ('hora_almoco_retorno', 'hora_almoco_retorno'),
        ('hora_saida', 'hora_saida')
    ]:
        valor = dados.get(campo_front)
        if valor:
            setattr(registro, campo_banco, datetime.strptime(valor, '%H:%M').time())
        else:
            setattr(registro, campo_banco, None)
    
    # Atualizar outros campos
    registro.obra_id = dados.get('obra_id')
    registro.observacoes = dados.get('observacoes', '')

def recalcular_registro_automatico(registro):
    """Recalcula registro com lógica automática baseada no tipo"""
    tipo = registro.tipo_registro
    
    # Resetar valores
    registro.horas_trabalhadas = 0.0
    registro.horas_extras = 0.0
    registro.total_atraso_horas = 0.0
    registro.total_atraso_minutos = 0
    registro.minutos_atraso_entrada = 0
    registro.minutos_atraso_saida = 0
    registro.percentual_extras = 0.0
    
    # Tipos sem trabalho
    tipos_sem_trabalho = ['falta', 'sabado_folga', 'domingo_folga', 'feriado']
    if tipo in tipos_sem_trabalho:
        return
    
    # Tipos especiais sem horários
    if tipo in ['falta_justificada', 'ferias']:
        registro.horas_trabalhadas = 8.0
        return
    
    # Calcular para tipos com horários
    if not registro.hora_entrada or not registro.hora_saida:
        return
    
    # Calcular horas trabalhadas
    horas = calcular_horas_trabalhadas_edicao(registro)
    registro.horas_trabalhadas = horas
    
    # Aplicar lógica por tipo
    if tipo == 'sabado_horas_extras':
        # Sábado: todas as horas são extras (50%)
        registro.horas_extras = horas
        registro.percentual_extras = 50.0
        # Sem atrasos
        
    elif tipo in ['domingo_horas_extras', 'feriado_trabalhado']:
        # Domingo/Feriado: todas as horas são extras (100%)
        registro.horas_extras = horas
        registro.percentual_extras = 100.0
        # Sem atrasos
        
    elif tipo == 'trabalhado':
        # Trabalho normal: calcular extras baseado no horário padrão
        calcular_horas_extras_baseado_horario_padrao(registro)
        
        # Calcular atrasos apenas em dias normais
        calcular_atrasos_trabalho_normal(registro)

def calcular_horas_trabalhadas_edicao(registro):
    """Calcula horas trabalhadas considerando almoço"""
    entrada = datetime.combine(registro.data, registro.hora_entrada)
    saida = datetime.combine(registro.data, registro.hora_saida)
    
    total_minutos = (saida - entrada).total_seconds() / 60
    
    # Subtrair almoço se definido
    if registro.hora_almoco_saida and registro.hora_almoco_retorno:
        almoco_saida = datetime.combine(registro.data, registro.hora_almoco_saida)
        almoco_retorno = datetime.combine(registro.data, registro.hora_almoco_retorno)
        minutos_almoco = (almoco_retorno - almoco_saida).total_seconds() / 60
        total_minutos -= minutos_almoco
    
    return total_minutos / 60.0

def calcular_atrasos_trabalho_normal(registro):
    """Calcula atrasos apenas para trabalho normal"""
    funcionario = Funcionario.query.get(registro.funcionario_id)
    if not funcionario or not funcionario.horario_trabalho_id:
        return
    
    horario_padrao = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
    if not horario_padrao:
        return
    
    # Calcular atraso de entrada
    if registro.hora_entrada and horario_padrao.entrada:
        entrada_esperada = datetime.combine(registro.data, horario_padrao.entrada)
        entrada_real = datetime.combine(registro.data, registro.hora_entrada)
        
        if entrada_real > entrada_esperada:
            minutos_atraso = (entrada_real - entrada_esperada).total_seconds() / 60
            registro.minutos_atraso_entrada = int(minutos_atraso)
            registro.total_atraso_minutos += int(minutos_atraso)
    
    # Converter total para horas
    registro.total_atraso_horas = registro.total_atraso_minutos / 60.0

def calcular_horas_extras_baseado_horario_padrao(registro):
    """Calcula horas extras baseado no horário padrão do funcionário"""
    funcionario = Funcionario.query.get(registro.funcionario_id)
    if not funcionario or not funcionario.horario_trabalho_id:
        # Sem horário padrão, usar 8h como base
        if registro.horas_trabalhadas > 8:
            registro.horas_extras = registro.horas_trabalhadas - 8
            registro.percentual_extras = 50.0
        return
    
    horario_padrao = HorarioTrabalho.query.get(funcionario.horario_trabalho_id)
    if not horario_padrao:
        # Sem horário padrão, usar 8h como base
        if registro.horas_trabalhadas > 8:
            registro.horas_extras = registro.horas_trabalhadas - 8
            registro.percentual_extras = 50.0
        return
    
    # Calcular horas padrão baseado no horário
    if horario_padrao.entrada and horario_padrao.saida:
        entrada_padrao = datetime.combine(registro.data, horario_padrao.entrada)
        saida_padrao = datetime.combine(registro.data, horario_padrao.saida)
        
        # Subtrair almoço padrão
        minutos_padrao = (saida_padrao - entrada_padrao).total_seconds() / 60
        if horario_padrao.saida_almoco and horario_padrao.retorno_almoco:
            almoco_saida_padrao = datetime.combine(registro.data, horario_padrao.saida_almoco)
            almoco_retorno_padrao = datetime.combine(registro.data, horario_padrao.retorno_almoco)
            minutos_almoco = (almoco_retorno_padrao - almoco_saida_padrao).total_seconds() / 60
            minutos_padrao -= minutos_almoco
        
        horas_padrao = minutos_padrao / 60.0
        
        # Calcular extras apenas se trabalhou mais que o padrão
        if registro.horas_trabalhadas > horas_padrao:
            registro.horas_extras = registro.horas_trabalhadas - horas_padrao
            registro.percentual_extras = 50.0
    else:
        # Fallback para 8h se não conseguir calcular
        if registro.horas_trabalhadas > 8:
            registro.horas_extras = registro.horas_trabalhadas - 8
            registro.percentual_extras = 50.0

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['GET'])
@login_required  
def obter_registro_ponto(registro_id):
    """Método GET separado para compatibilidade"""
    return editar_registro_ponto(registro_id)

@main_bp.route('/ponto/registro/<int:registro_id>/legacy', methods=['PUT', 'POST'])
@login_required
def atualizar_registro_ponto_legacy(registro_id):
    """Atualizar um registro de ponto individual"""
    try:
        print(f"✏️ Atualizando registro {registro_id}")
        
        # Buscar registro específico
        registro = RegistroPonto.query.get_or_404(registro_id)
        
        # Buscar funcionário
        funcionario = Funcionario.query.get(registro.funcionario_id)
        if not funcionario:
            return jsonify({'error': 'Funcionário não encontrado'}), 404
        
        # Obter dados do request
        if request.is_json:
            data_source = request.json
        else:
            data_source = request.form
        
        print(f"📝 Dados recebidos: {data_source}")
        
        # Validar e processar dados básicos
        data_str = data_source.get('data')
        if not data_str:
            return jsonify({'error': 'Data é obrigatória'}), 400
            
        data = datetime.strptime(data_str, '%Y-%m-%d').date()
        tipo_frontend = data_source.get('tipo_registro', 'trabalho_normal')
        obra_id = data_source.get('obra_id') or None
        observacoes = data_source.get('observacoes', '')
        
        # Converter tipo frontend para banco
        tipo_banco = tipo_frontend
        if tipo_frontend == 'trabalho_normal':
            tipo_banco = 'trabalhado'
        elif tipo_frontend == 'sabado_trabalhado':
            tipo_banco = 'sabado_horas_extras'
        elif tipo_frontend == 'domingo_trabalhado':
            tipo_banco = 'domingo_horas_extras'
        elif tipo_frontend == 'feriado_folga':
            tipo_banco = 'feriado'
        
        # Processar horários baseado no tipo
        if tipo_frontend in ['trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
            # Tipos que requerem horários
            entrada_str = data_source.get('hora_entrada', '')
            saida_almoco_str = data_source.get('hora_almoco_saida', '')
            retorno_almoco_str = data_source.get('hora_almoco_retorno', '')
            saida_str = data_source.get('hora_saida', '')
            
            # Converter horários
            hora_entrada = datetime.strptime(entrada_str, '%H:%M').time() if entrada_str else None
            hora_almoco_saida = datetime.strptime(saida_almoco_str, '%H:%M').time() if saida_almoco_str else None
            hora_almoco_retorno = datetime.strptime(retorno_almoco_str, '%H:%M').time() if retorno_almoco_str else None
            hora_saida = datetime.strptime(saida_str, '%H:%M').time() if saida_str else None
            
            # Calcular horas trabalhadas
            horas_trabalhadas = 0.0
            if hora_entrada and hora_saida:
                # Calcular total de horas
                entrada_minutos = hora_entrada.hour * 60 + hora_entrada.minute
                saida_minutos = hora_saida.hour * 60 + hora_saida.minute
                
                # Ajustar se passou da meia-noite
                if saida_minutos < entrada_minutos:
                    saida_minutos += 24 * 60
                
                total_minutos = saida_minutos - entrada_minutos
                
                # Subtrair almoço se ambos horários estiverem definidos
                if hora_almoco_saida and hora_almoco_retorno:
                    almoco_saida_min = hora_almoco_saida.hour * 60 + hora_almoco_saida.minute
                    almoco_retorno_min = hora_almoco_retorno.hour * 60 + hora_almoco_retorno.minute
                    
                    if almoco_retorno_min > almoco_saida_min:
                        total_minutos -= (almoco_retorno_min - almoco_saida_min)
                
                horas_trabalhadas = total_minutos / 60.0
            
            # Calcular horas extras baseado no tipo
            horas_extras = 0.0
            percentual_extras = 0.0
            
            if tipo_frontend in ['sabado_trabalhado', 'domingo_trabalhado', 'feriado_trabalhado']:
                # Para fim de semana/feriado: TODAS as horas são extras
                horas_extras = horas_trabalhadas
                if tipo_frontend == 'sabado_trabalhado':
                    percentual_extras = 50.0
                else:  # domingo_trabalhado, feriado_trabalhado
                    percentual_extras = 100.0
            elif tipo_frontend == 'trabalho_normal' and horas_trabalhadas > 0:
                # Para trabalho normal: apenas horas acima da jornada
                horas_jornada = funcionario.horario_trabalho.horas_diarias if funcionario.horario_trabalho else 8.0
                horas_extras = max(0, horas_trabalhadas - horas_jornada)
                if horas_extras > 0:
                    percentual_extras = 50.0
            
        else:
            # Tipos sem horários (faltas, férias, etc.)
            hora_entrada = None
            hora_almoco_saida = None
            hora_almoco_retorno = None
            hora_saida = None
            horas_trabalhadas = 0.0
            horas_extras = 0.0
            percentual_extras = 0.0
        
        # Atualizar registro
        registro.data = data
        registro.tipo_registro = tipo_banco
        registro.obra_id = int(obra_id) if obra_id else None
        registro.hora_entrada = hora_entrada
        registro.hora_almoco_saida = hora_almoco_saida
        registro.hora_almoco_retorno = hora_almoco_retorno
        registro.hora_saida = hora_saida
        registro.horas_trabalhadas = horas_trabalhadas
        registro.horas_extras = horas_extras
        registro.percentual_extras = percentual_extras
        registro.observacoes = observacoes
        
        db.session.commit()
        
        print(f"✅ Registro {registro_id} atualizado: {tipo_banco}, {horas_trabalhadas}h, {horas_extras}h extras")
        
        return jsonify({
            'success': True,
            'message': 'Registro atualizado com sucesso',
            'registro': {
                'id': registro.id,
                'tipo_registro': tipo_banco,
                'horas_trabalhadas': horas_trabalhadas,
                'horas_extras': horas_extras,
                'percentual_extras': percentual_extras
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao atualizar registro {registro_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao salvar: {str(e)}'}), 500
        
        if obra_id == '':
            obra_id = None
        elif obra_id:
            obra_id = int(obra_id)
        
        # Atualizar dados básicos
        registro.data = data
        registro.tipo_registro = tipo_registro
        registro.obra_id = obra_id
        
        # Limpar horários primeiro
        registro.hora_entrada = None
        registro.hora_almoco_saida = None
        registro.hora_almoco_retorno = None
        registro.hora_saida = None
        registro.horas_trabalhadas = 0
        registro.horas_extras = 0
        
        # Adicionar horários se não for falta ou feriado
        if tipo_registro not in ['falta', 'falta_justificada', 'feriado']:
            entrada = data_source.get('hora_entrada') or data_source.get('hora_entrada_ponto')
            saida_almoco = data_source.get('hora_almoco_saida') or data_source.get('hora_almoco_saida_ponto')
            retorno_almoco = data_source.get('hora_almoco_retorno') or data_source.get('hora_almoco_retorno_ponto')
            saida = data_source.get('hora_saida') or data_source.get('hora_saida_ponto')
            
            if entrada:
                registro.hora_entrada = datetime.strptime(entrada, '%H:%M').time()
            if saida_almoco:
                registro.hora_almoco_saida = datetime.strptime(saida_almoco, '%H:%M').time()
            if retorno_almoco:
                registro.hora_almoco_retorno = datetime.strptime(retorno_almoco, '%H:%M').time()
            if saida:
                registro.hora_saida = datetime.strptime(saida, '%H:%M').time()
                
        # Percentual de extras baseado no tipo
        if tipo_registro == 'sabado_horas_extras':
            registro.percentual_extras = 50.0
        elif tipo_registro in ['domingo_horas_extras', 'feriado_trabalhado']:
            registro.percentual_extras = 100.0
        else:
            percentual_extras = data_source.get('percentual_extras')
            registro.percentual_extras = float(percentual_extras) if percentual_extras else 0.0
        
        # Observações
        registro.observacoes = data_source.get('observacoes') or data_source.get('observacoes_ponto', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Registro atualizado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/ponto/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_ponto(registro_id):
    """Excluir um registro de ponto"""
    try:
        registro = RegistroPonto.query.get_or_404(registro_id)
        
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Registro excluído com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos')
@login_required
def controle_outros_custos():
    """Página principal do controle de outros custos"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo = request.args.get('tipo')
    
    # Query base
    query = OutroCusto.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(OutroCusto.funcionario_id == funcionario_id)
    
    if data_inicio:
        query = query.filter(OutroCusto.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(OutroCusto.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo:
        query = query.filter(OutroCusto.tipo == tipo)
    
    # Buscar registros com joins
    custos = query.options(
        joinedload(OutroCusto.funcionario)
    ).order_by(OutroCusto.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    
    return render_template('controle_outros_custos.html',
                         custos=custos,
                         funcionarios=funcionarios)

@main_bp.route('/outros-custos/custo', methods=['POST'])
@login_required
def criar_outro_custo_crud():
    """Criar novo custo"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo = request.form.get('tipo')
        valor = float(request.form.get('valor'))
        descricao = request.form.get('descricao')
        
        # Criar custo
        custo = OutroCusto(
            funcionario_id=funcionario_id,
            data=data,
            tipo=tipo,
            valor=valor,
            descricao=descricao
        )
        
        db.session.add(custo)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['GET'])
@login_required
def obter_outro_custo_crud(custo_id):
    """Obter dados de um custo"""
    custo = OutroCusto.query.get_or_404(custo_id)
    
    return jsonify({
        'id': custo.id,
        'funcionario_id': custo.funcionario_id,
        'data': custo.data.isoformat(),
        'tipo': custo.tipo,
        'valor': custo.valor,
        'descricao': custo.descricao
    })

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['PUT'])
@login_required
def atualizar_outro_custo_crud(custo_id):
    """Atualizar custo"""
    try:
        custo = OutroCusto.query.get_or_404(custo_id)
        
        custo.funcionario_id = request.form.get('funcionario_id')
        custo.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        custo.tipo = request.form.get('tipo')
        custo.valor = float(request.form.get('valor'))
        custo.descricao = request.form.get('descricao')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/outros-custos/custo/<int:custo_id>', methods=['DELETE'])
@login_required
def excluir_outro_custo_crud(custo_id):
    """Excluir custo"""
    try:
        custo = OutroCusto.query.get_or_404(custo_id)
        db.session.delete(custo)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao')
@login_required
def controle_alimentacao():
    """Página principal do controle de alimentação"""
    # Filtros
    funcionario_id = request.args.get('funcionario_id')
    restaurante_id = request.args.get('restaurante_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_refeicao = request.args.get('tipo_refeicao')
    
    # Query base
    query = RegistroAlimentacao.query
    
    # Aplicar filtros
    if funcionario_id:
        query = query.filter(RegistroAlimentacao.funcionario_id == funcionario_id)
    
    if restaurante_id:
        query = query.filter(RegistroAlimentacao.restaurante_id == restaurante_id)
    
    if data_inicio:
        query = query.filter(RegistroAlimentacao.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    
    if data_fim:
        query = query.filter(RegistroAlimentacao.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    if tipo_refeicao:
        query = query.filter(RegistroAlimentacao.tipo_refeicao == tipo_refeicao)
    
    # Buscar registros com joins
    registros = query.options(
        joinedload(RegistroAlimentacao.funcionario),
        joinedload(RegistroAlimentacao.restaurante)
    ).order_by(RegistroAlimentacao.data.desc()).all()
    
    # Dados para formulário
    funcionarios = Funcionario.query.filter_by(ativo=True).order_by(Funcionario.nome).all()
    restaurantes = Restaurante.query.filter_by(ativo=True).order_by(Restaurante.nome).all()
    
    return render_template('controle_alimentacao.html',
                         registros=registros,
                         funcionarios=funcionarios,
                         restaurantes=restaurantes)

@main_bp.route('/alimentacao/registro', methods=['POST'])
@login_required
def criar_registro_alimentacao():
    """Criar novo registro de alimentação"""
    try:
        funcionario_id = request.form.get('funcionario_id')
        restaurante_id = request.form.get('restaurante_id')
        data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        tipo_refeicao = request.form.get('tipo_refeicao')
        valor = float(request.form.get('valor'))
        quantidade = int(request.form.get('quantidade', 1))
        observacoes = request.form.get('observacoes')
        
        # Criar registro
        registro = RegistroAlimentacao(
            funcionario_id=funcionario_id,
            restaurante_id=restaurante_id,
            data=data,
            tipo_refeicao=tipo_refeicao,
            valor=valor,
            quantidade=quantidade,
            observacoes=observacoes
        )
        
        db.session.add(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['GET'])
@login_required
def obter_registro_alimentacao(registro_id):
    """Obter dados de um registro de alimentação"""
    registro = RegistroAlimentacao.query.get_or_404(registro_id)
    
    return jsonify({
        'id': registro.id,
        'funcionario_id': registro.funcionario_id,
        'restaurante_id': registro.restaurante_id,
        'data': registro.data.isoformat(),
        'tipo_refeicao': registro.tipo_refeicao,
        'valor': registro.valor,
        'quantidade': registro.quantidade,
        'observacoes': registro.observacoes
    })

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['PUT'])
@login_required
def atualizar_registro_alimentacao(registro_id):
    """Atualizar registro de alimentação"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(registro_id)
        
        registro.funcionario_id = request.form.get('funcionario_id')
        registro.restaurante_id = request.form.get('restaurante_id')
        registro.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        registro.tipo_refeicao = request.form.get('tipo_refeicao')
        registro.valor = float(request.form.get('valor'))
        registro.quantidade = int(request.form.get('quantidade', 1))
        registro.observacoes = request.form.get('observacoes')
        
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/alimentacao/registro/<int:registro_id>', methods=['DELETE'])
@login_required
def excluir_registro_alimentacao(registro_id):
    """Excluir registro de alimentação"""
    try:
        registro = RegistroAlimentacao.query.get_or_404(registro_id)
        db.session.delete(registro)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500



# API Endpoints para RDO
@main_bp.route("/api/obras/autocomplete")
@login_required
def api_obras_autocomplete():
    """API para autocomplete de obras"""
    try:
        q = request.args.get("q", "").strip()
        
        # Query base - obras ativas
        query = Obra.query.filter(Obra.ativo == True)
        
        # Se tem termo de busca, filtrar
        if q:
            query = query.filter(
                or_(
                    Obra.nome.ilike(f"%{q}%"),
                    Obra.codigo.ilike(f"%{q}%"),
                    Obra.endereco.ilike(f"%{q}%")
                )
            )
        
        # Limitar resultados e ordenar
        obras = query.order_by(Obra.nome).limit(20).all()
        
        # Debug - log para verificar
        print(f"Buscando obras com termo: '{q}' - Encontradas: {len(obras)}")
        
        resultado = []
        for obra in obras:
            resultado.append({
                "id": obra.id,
                "nome": obra.nome,
                "codigo": obra.codigo or "S/C",
                "endereco": obra.endereco or "Endereço não informado",
                "area_total_m2": float(obra.area_total_m2) if obra.area_total_m2 else 0,
                "status": obra.status or "Em andamento"
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint obras_autocomplete: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/obras/todas")
@login_required
def api_obras_todas():
    """API para carregar todas as obras (fallback)"""
    try:
        obras = Obra.query.filter(Obra.ativo == True).order_by(Obra.nome).all()
        
        return jsonify([{
            "id": obra.id,
            "nome": obra.nome,
            "codigo": obra.codigo or "S/C",
            "endereco": obra.endereco or "Endereço não informado"
        } for obra in obras])
        
    except Exception as e:
        print(f"Erro ao carregar todas as obras: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/funcionarios/rdo-autocomplete")
@login_required
def api_funcionarios_rdo_autocomplete():
    """API para autocomplete de funcionários com dados de ponto"""
    try:
        q = request.args.get("q", "").strip()
        data_rdo = request.args.get("data_rdo")
        
        # Query base - funcionários ativos
        query = Funcionario.query.filter(Funcionario.ativo == True)
        
        # Se tem termo de busca
        if q:
            query = query.filter(
                or_(
                    Funcionario.nome.ilike(f"%{q}%"),
                    Funcionario.codigo.ilike(f"%{q}%"),
                    Funcionario.cpf.ilike(f"%{q}%")
                )
            )
        
        funcionarios = query.order_by(Funcionario.nome).limit(20).all()
        
        print(f"Buscando funcionários: '{q}' - Encontrados: {len(funcionarios)}")
        
        resultado = []
        for func in funcionarios:
            # Buscar dados do ponto para a data
            presente_hoje = False
            horas_trabalhadas = 0
            
            if data_rdo:
                try:
                    data_consulta = datetime.strptime(data_rdo, "%Y-%m-%d").date()
                    registro_ponto = RegistroPonto.query.filter_by(
                        funcionario_id=func.id,
                        data=data_consulta
                    ).first()
                    
                    if registro_ponto:
                        presente_hoje = bool(registro_ponto.hora_entrada)
                        horas_trabalhadas = registro_ponto.horas_trabalhadas or 0
                except:
                    pass
            
            resultado.append({
                "id": func.id,
                "nome": func.nome,
                "codigo": func.codigo or f"F{func.id:03d}",
                "funcao": func.funcao.nome if func.funcao else "Não definida",
                "salario": float(func.salario) if func.salario else 0,
                "presente_hoje": presente_hoje,
                "horas_trabalhadas": horas_trabalhadas
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro no endpoint funcionarios_rdo_autocomplete: {str(e)}")
        return jsonify([]), 500

@main_bp.route("/api/funcionarios/todos")
@login_required
def api_funcionarios_todos():
    """API para carregar todos os funcionários (fallback)"""
    try:
        funcionarios = Funcionario.query.filter(Funcionario.ativo == True).order_by(Funcionario.nome).all()
        
        return jsonify([{
            "id": func.id,
            "nome": func.nome,
            "codigo": func.codigo or f"F{func.id:03d}",
            "funcao": func.funcao.nome if func.funcao else "Não definida"
        } for func in funcionarios])
        
    except Exception as e:
        print(f"Erro ao carregar funcionários: {str(e)}")
        return jsonify([]), 500

@main_bp.route('/api/servicos/autocomplete')
@login_required  
def api_servicos_autocomplete():
    """API para autocomplete de serviços"""
    q = request.args.get("q", "")
    ativo = request.args.get("ativo", "true").lower() == "true"
    
    # Query específica para evitar erro categoria_id
    query = db.session.query(
        Servico.id,
        Servico.nome,
        Servico.categoria,
        Servico.unidade_medida,
        Servico.unidade_simbolo,
        Servico.custo_unitario
    ).filter(Servico.ativo == ativo)
    
    if q:
        query = query.filter(
            or_(
                Servico.nome.ilike(f"%{q}%"),
                Servico.categoria.ilike(f"%{q}%")
            )
        )
    
    servicos_data = query.limit(10).all()
    
    return jsonify([{
        "id": row.id,
        "nome": row.nome,
        "categoria": row.categoria,
        "unidade_medida": row.unidade_medida,
        "unidade_simbolo": row.unidade_simbolo,
        "custo_unitario": float(row.custo_unitario) if row.custo_unitario else 0
    } for row in servicos_data])

@main_bp.route("/api/servicos/<int:servico_id>")
@login_required
def api_servico_detalhes(servico_id):
    """API para detalhes de um serviço específico com subatividades"""
    servico = Servico.query.get_or_404(servico_id)
    
    subatividades = SubAtividade.query.filter_by(servico_id=servico_id).all()
    
    return jsonify({
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
        "unidade_medida": servico.unidade_medida,
        "unidade_simbolo": servico.unidade_simbolo,
        "custo_unitario": float(servico.custo_unitario) if servico.custo_unitario else 0,
        "subatividades": [{
            "id": sub.id,
            "nome": sub.nome,
            "descricao": sub.descricao
        } for sub in subatividades]
    })

@main_bp.route("/api/equipamentos/autocomplete")
@login_required
def api_equipamentos_autocomplete():
    """API para autocomplete de equipamentos/veículos"""
    q = request.args.get("q", "")
    ativo = request.args.get("ativo", "true").lower() == "true"
    
    query = Veiculo.query.filter(Veiculo.ativo == ativo)
    
    if q:
        query = query.filter(
            or_(
                Veiculo.marca.ilike(f"%{q}%"),
                Veiculo.modelo.ilike(f"%{q}%"),
                Veiculo.placa.ilike(f"%{q}%"),
                Veiculo.tipo.ilike(f"%{q}%")
            )
        )
    
    veiculos = query.limit(10).all()
    
    return jsonify([{
        "id": veiculo.id,
        "nome": f"{veiculo.marca} {veiculo.modelo}",
        "placa": veiculo.placa,
        "tipo": veiculo.tipo,
        "status": veiculo.status
    } for veiculo in veiculos])

@main_bp.route("/api/ponto/funcionario/<int:funcionario_id>/data/<string:data>")
@login_required
def api_ponto_funcionario_data(funcionario_id, data):
    """API para buscar dados de ponto de um funcionário em uma data específica"""
    try:
        funcionario = Funcionario.query.get_or_404(funcionario_id)
        data_consulta = datetime.strptime(data, "%Y-%m-%d").date()
        
        registro_ponto = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data_consulta
        ).first()
        
        if registro_ponto:
            return jsonify({
                "success": True,
                "funcionario": {
                    "id": funcionario.id,
                    "nome": funcionario.nome,
                    "codigo": funcionario.codigo,
                    "funcao": funcionario.funcao.nome if funcionario.funcao else "Sem função"
                },
                "registro_ponto": {
                    "hora_entrada": registro_ponto.hora_entrada.strftime("%H:%M") if registro_ponto.hora_entrada else None,
                    "hora_saida": registro_ponto.hora_saida.strftime("%H:%M") if registro_ponto.hora_saida else None,
                    "horas_trabalhadas": registro_ponto.horas_trabalhadas or 0,
                    "tipo_registro": registro_ponto.tipo_registro
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": "Nenhum registro de ponto encontrado para esta data"
            })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erro ao buscar dados: {str(e)}"
        }), 500

@main_bp.route("/api/rdo/salvar", methods=["POST"])
@login_required
def api_rdo_salvar():
    """API para salvar RDO como rascunho"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get("data_relatorio") or not dados.get("obra_id"):
            return jsonify({
                "success": False,
                "message": "Data do relatório e obra são obrigatórios"
            }), 400
        
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(dados["data_relatorio"], "%Y-%m-%d").date(),
            obra_id=dados["obra_id"],
            criado_por_id=current_user.id,
            tempo_manha=dados.get("tempo_manha", ""),
            tempo_tarde=dados.get("tempo_tarde", ""),
            tempo_noite=dados.get("tempo_noite", ""),
            observacoes_meteorologicas=dados.get("observacoes_meteorologicas", ""),
            comentario_geral=dados.get("comentario_geral", ""),
            status="Rascunho"
        )
        
        db.session.add(rdo)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "RDO salvo como rascunho com sucesso",
            "rdo_id": rdo.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Erro ao salvar RDO: {str(e)}"
        }), 500

@main_bp.route("/api/rdo/finalizar", methods=["POST"])
@login_required
def api_rdo_finalizar():
    """API para finalizar RDO"""
    try:
        dados = request.get_json()
        
        # Validações obrigatórias
        if not dados.get("data_relatorio") or not dados.get("obra_id"):
            return jsonify({
                "success": False,
                "message": "Data do relatório e obra são obrigatórios"
            }), 400
        
        # Gerar número único do RDO
        import uuid
        numero_rdo = f"RDO-{datetime.now().year}-{str(uuid.uuid4())[:8].upper()}"
        
        rdo = RDO(
            numero_rdo=numero_rdo,
            data_relatorio=datetime.strptime(dados["data_relatorio"], "%Y-%m-%d").date(),
            obra_id=dados["obra_id"],
            criado_por_id=current_user.id,
            tempo_manha=dados.get("tempo_manha", ""),
            tempo_tarde=dados.get("tempo_tarde", ""),
            tempo_noite=dados.get("tempo_noite", ""),
            observacoes_meteorologicas=dados.get("observacoes_meteorologicas", ""),
            comentario_geral=dados.get("comentario_geral", ""),
            status="Finalizado"
        )
        
        db.session.add(rdo)
        db.session.flush()  # Para obter o ID do RDO
        
        # Salvar dados de mão de obra
        for func_data in dados.get("funcionarios", []):
            if func_data.get("funcionario_id"):
                rdo_mao_obra = RDOMaoObra(
                    rdo_id=rdo.id,
                    funcionario_id=func_data["funcionario_id"],
                    horas_trabalhadas=float(func_data.get("horas", 0)),
                    funcao_exercida=func_data.get("funcao_exercida", ""),
                    presente=func_data.get("presente", True)
                )
                db.session.add(rdo_mao_obra)
        
        # Salvar atividades
        for ativ_data in dados.get("atividades", []):
            if ativ_data.get("servico_id"):
                rdo_atividade = RDOAtividade(
                    rdo_id=rdo.id,
                    servico_id=ativ_data["servico_id"],
                    quantidade=float(ativ_data.get("quantidade", 0)),
                    tempo_execucao=float(ativ_data.get("tempo", 0)),
                    observacoes=ativ_data.get("observacoes", "")
                )
                db.session.add(rdo_atividade)
        
        # Salvar equipamentos
        for equip_data in dados.get("equipamentos", []):
            if equip_data.get("equipamento_id"):
                rdo_equipamento = RDOEquipamento(
                    rdo_id=rdo.id,
                    veiculo_id=equip_data["equipamento_id"],
                    horas_uso=float(equip_data.get("horas_uso", 0)),
                    status=equip_data.get("status", "operando"),
                    observacoes=equip_data.get("observacoes", "")
                )
                db.session.add(rdo_equipamento)
        
        # Salvar ocorrências
        for ocorr_data in dados.get("ocorrencias", []):
            if ocorr_data.get("tipo") and ocorr_data.get("descricao"):
                rdo_ocorrencia = RDOOcorrencia(
                    rdo_id=rdo.id,
                    tipo=ocorr_data["tipo"],
                    gravidade=ocorr_data.get("gravidade", "media"),
                    descricao=ocorr_data["descricao"]
                )
                db.session.add(rdo_ocorrencia)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "RDO finalizado com sucesso",
            "rdo_id": rdo.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Erro ao finalizar RDO: {str(e)}"
        }), 500

# API para carregar serviços de uma obra específica
@main_bp.route('/api/obras/<int:obra_id>/servicos')
@login_required
def api_servicos_obra(obra_id):
    """API para carregar serviços associados a uma obra"""
    try:
        servicos_obra = db.session.query(
            Servico.id,
            Servico.nome,
            Servico.categoria,
            Servico.unidade_medida,
            ServicoObra.quantidade_planejada,
            ServicoObra.observacoes
        ).join(
            ServicoObra, Servico.id == ServicoObra.servico_id
        ).filter(
            ServicoObra.obra_id == obra_id,
            Servico.ativo == True
        ).order_by(Servico.nome).all()
        
        servicos_data = []
        for servico in servicos_obra:
            servicos_data.append({
                'id': servico.id,
                'nome': servico.nome,
                'categoria': servico.categoria,
                'unidade_medida': servico.unidade_medida,
                'unidade_simbolo': get_simbolo_unidade(servico.unidade_medida),
                'quantidade_planejada': float(servico.quantidade_planejada) if servico.quantidade_planejada else 0,
                'observacoes': servico.observacoes
            })
        
        return jsonify({
            'success': True,
            'servicos': servicos_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API para buscar último RDO de uma obra
@main_bp.route('/api/obras/<int:obra_id>/ultimo-rdo')
@login_required
def api_ultimo_rdo_obra(obra_id):
    """API para buscar o último RDO de uma obra para pré-popular valores"""
    try:
        # Buscar o RDO mais recente desta obra
        ultimo_rdo = RDO.query.filter_by(
            obra_id=obra_id
        ).order_by(RDO.data.desc()).first()
        
        if not ultimo_rdo:
            return jsonify({
                'success': False,
                'message': 'Nenhum RDO anterior encontrado'
            })
        
        # Extrair atividades do JSON armazenado
        atividades = {}
        if ultimo_rdo.dados_atividades:
            try:
                atividades_json = json.loads(ultimo_rdo.dados_atividades)
                for atividade in atividades_json:
                    if atividade.get('servico_id'):
                        atividades[str(atividade['servico_id'])] = {
                            'quantidade': atividade.get('quantidade', 0),
                            'percentual': atividade.get('percentual', 0),
                            'observacoes': atividade.get('observacoes', ''),
                            'tempo': atividade.get('tempo', 0)
                        }
            except json.JSONDecodeError:
                pass
        
        return jsonify({
            'success': True,
            'rdo_id': ultimo_rdo.id,
            'data_relatorio': ultimo_rdo.data_relatorio.isoformat(),
            'atividades': atividades
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500







# ================================
# MÓDULO 2: PORTAL DO CLIENTE
# ================================

@main_bp.route("/cliente/obra/<token>")
def cliente_obra_dashboard(token):
    """Portal do cliente para acompanhar progresso da obra"""
    try:
        obra = Obra.query.filter_by(token_cliente=token).first()
        if not obra:
            return "Token inválido", 404
        
        rdos = RDO.query.filter_by(obra_id=obra.id).count()
        progresso = min(100, (rdos * 10))
        
        return f"""
        <h1>Obra: {obra.nome}</h1>
        <p>Endereço: {obra.endereco}</p>
        <p>Progresso: {progresso}%</p>
        <p>RDOs executados: {rdos}</p>
        """
    except Exception as e:
        return f"Erro: {str(e)}", 500

@main_bp.route("/cliente/proposta/<token>/aprovar", methods=["POST"])
def cliente_aprovar_proposta_v2(token):
    """Cliente aprova proposta e gera obra"""
    try:
        proposta = PropostaComercial.query.filter_by(token_acesso=token).first()
        if not proposta:
            return jsonify({"success": False, "message": "Proposta não encontrada"}), 404
        
        proposta.status = StatusProposta.APROVADA
        
        import secrets
        obra_codigo = f"OBR-{datetime.now().year}-{Obra.query.count() + 1:03d}"
        cliente_token = secrets.token_urlsafe(16)
        
        nova_obra = Obra(
            nome=f"Obra - {proposta.titulo_projeto}",
            codigo=obra_codigo,
            endereco=proposta.endereco_execucao or "Não informado",
            data_inicio=datetime.now().date(),
            orcamento=proposta.valor_total,
            valor_contrato=proposta.valor_total,
            status="Planejamento",
            cliente_nome=proposta.cliente_nome,
            token_cliente=cliente_token,
            proposta_origem_id=proposta.id,
            admin_id=proposta.admin_id
        )
        
        db.session.add(nova_obra)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Obra {obra_codigo} criada!",
            "cliente_token": cliente_token
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# ================================
# MÓDULO 3: GESTÃO DE EQUIPES
# ================================

@main_bp.route("/equipes")
@login_required
@admin_required
def gestao_equipes():
    """Interface para gestão de equipes"""
    try:
        funcionarios = Funcionario.query.filter_by(
            ativo=True,
            admin_id=current_user.id
        ).all()
        
        obras = Obra.query.filter_by(
            ativo=True,
            admin_id=current_user.id
        ).all()
        
        alocacoes = AlocacaoEquipe.query.filter_by(
            admin_id=current_user.id
        ).order_by(AlocacaoEquipe.data_alocacao.desc()).limit(20).all()
        
        return render_template("equipes/gestao_equipes.html",
                             funcionarios=funcionarios,
                             obras=obras,
                             alocacoes=alocacoes)
        
    except Exception as e:
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/equipes/alocar", methods=["POST"])
@login_required
@admin_required
def alocar_funcionario():
    """Alocar funcionário em obra"""
    try:
        funcionario_id = request.form["funcionario_id"]
        obra_id = request.form["obra_id"]
        data_alocacao = datetime.strptime(request.form["data_alocacao"], "%Y-%m-%d").date()
        local_trabalho = request.form.get("local_trabalho", "campo")
        
        nova_alocacao = AlocacaoEquipe(
            funcionario_id=funcionario_id,
            obra_id=obra_id,
            data_alocacao=data_alocacao,
            local_trabalho=local_trabalho,
            admin_id=current_user.id
        )
        
        db.session.add(nova_alocacao)
        db.session.commit()
        
        flash("Funcionário alocado com sucesso!", "success")
        return redirect(url_for("main.gestao_equipes"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for("main.gestao_equipes"))



# ================================
# MÓDULO 4: ALMOXARIFADO COMPLETO
# ================================

@main_bp.route("/materiais")
@login_required
@admin_required
def lista_materiais():
    """Lista todos os materiais do almoxarifado"""
    try:
        materiais = Material.query.filter_by(
            admin_id=current_user.id,
            ativo=True
        ).order_by(Material.descricao).all()
        
        return render_template("almoxarifado/lista_materiais.html",
                             materiais=materiais)
        
    except Exception as e:
        flash(f"Erro ao carregar materiais: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/materiais/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_material():
    """Cadastrar novo material"""
    if request.method == "POST":
        try:
            novo_material = Material(
                descricao=request.form["descricao"],
                categoria=request.form["categoria"],
                unidade_medida=request.form["unidade_medida"],
                estoque_minimo=float(request.form.get("estoque_minimo", 0)),
                localizacao=request.form.get("localizacao", ""),
                codigo_barras=request.form.get("codigo_barras", ""),
                admin_id=current_user.id
            )
            
            db.session.add(novo_material)
            db.session.commit()
            
            flash("Material cadastrado com sucesso!", "success")
            return redirect(url_for("main.lista_materiais"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar material: {str(e)}", "danger")
    
    return render_template("almoxarifado/material_form.html")

@main_bp.route("/movimentacoes-material")
@login_required
@admin_required
def movimentacoes_material():
    """Lista movimentações de materiais"""
    try:
        movimentacoes = MovimentacaoMaterial.query.filter_by(
            admin_id=current_user.id
        ).order_by(MovimentacaoMaterial.created_at.desc()).limit(50).all()
        
        return render_template("almoxarifado/movimentacoes.html",
                             movimentacoes=movimentacoes)
        
    except Exception as e:
        flash(f"Erro ao carregar movimentações: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/movimentacoes-material/nova", methods=["POST"])
@login_required
@admin_required
def nova_movimentacao():
    """Registrar nova movimentação de material"""
    try:
        nova_mov = MovimentacaoMaterial(
            material_id=request.form["material_id"],
            tipo_movimento=request.form["tipo_movimento"],
            quantidade=float(request.form["quantidade"]),
            valor_unitario=float(request.form.get("valor_unitario", 0)),
            data_movimento=datetime.strptime(request.form["data_movimento"], "%Y-%m-%d").date(),
            observacoes=request.form.get("observacoes", ""),
            admin_id=current_user.id
        )
        
        # Calcular valor total
        nova_mov.valor_total = nova_mov.quantidade * nova_mov.valor_unitario
        
        # Atualizar estoque do material
        material = Material.query.get(nova_mov.material_id)
        if nova_mov.tipo_movimento == "entrada":
            material.estoque_atual += nova_mov.quantidade
        elif nova_mov.tipo_movimento == "saida":
            material.estoque_atual -= nova_mov.quantidade
        
        db.session.add(nova_mov)
        db.session.commit()
        
        flash("Movimentação registrada com sucesso!", "success")
        return redirect(url_for("main.movimentacoes_material"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao registrar movimentação: {str(e)}", "danger")
        return redirect(url_for("main.movimentacoes_material"))



# ===== MÓDULO 1: SISTEMA DE PROPOSTAS =====
# ROTAS ADMINISTRATIVAS

import secrets
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from sqlalchemy import func

@main_bp.route("/propostas")
@login_required
@admin_required
def lista_propostas():
    """Lista todas as propostas do admin atual"""
    try:
        propostas = Proposta.query.filter_by(
            admin_id=current_user.id
        ).order_by(Proposta.created_at.desc()).all()
        
        return render_template("propostas/lista_propostas.html", propostas=propostas)
        
    except Exception as e:
        flash(f"Erro ao carregar propostas: {str(e)}", "danger")
        return redirect(url_for("main.dashboard"))

@main_bp.route("/propostas/nova", methods=["GET", "POST"])
@login_required
@admin_required
def nova_proposta():
    """Criar nova proposta"""
    if request.method == "POST":
        try:
            # Gerar número automático da proposta
            ultimo_numero = db.session.query(func.max(Proposta.numero_proposta)).scalar()
            if ultimo_numero:
                numero = int(ultimo_numero.split("-")[-1]) + 1
            else:
                numero = 1
            numero_proposta = f"PROP-{datetime.now().year}-{numero:03d}"
            
            # Criar proposta
            proposta = Proposta(
                numero_proposta=numero_proposta,
                cliente_nome=request.form["cliente_nome"],
                cliente_email=request.form["cliente_email"],
                cliente_telefone=request.form.get("cliente_telefone"),
                cliente_cpf_cnpj=request.form.get("cliente_cpf_cnpj"),
                endereco_obra=request.form["endereco_obra"],
                descricao_obra=request.form["descricao_obra"],
                area_total_m2=float(request.form["area_total_m2"]) if request.form.get("area_total_m2") else None,
                valor_proposta=float(request.form["valor_proposta"]),
                prazo_execucao=int(request.form.get("prazo_execucao", 30)),
                admin_id=current_user.id,
                criado_por_id=current_user.id
            )
            
            db.session.add(proposta)
            db.session.flush()  # Para obter o ID
            
            # Processar serviços
            servicos_json = request.form.get("servicos_json", "[]")
            if servicos_json:
                try:
                    servicos_data = json.loads(servicos_json)
                    valor_total_servicos = 0
                    
                    for i, servico_data in enumerate(servicos_data):
                        quantidade = float(servico_data["quantidade"])
                        valor_unitario = float(servico_data["valor_unitario"])
                        valor_total = quantidade * valor_unitario
                        valor_total_servicos += valor_total
                        
                        servico = PropostaServico(
                            proposta_id=proposta.id,
                            descricao_servico=servico_data["descricao"],
                            quantidade=quantidade,
                            unidade=servico_data["unidade"],
                            valor_unitario=valor_unitario,
                            valor_total=valor_total,
                            observacoes=servico_data.get("observacoes"),
                            ordem=i + 1
                        )
                        db.session.add(servico)
                    
                    # Atualizar valor total da proposta
                    proposta.valor_proposta = valor_total_servicos
                    
                except json.JSONDecodeError:
                    pass  # Manter valor manual se JSON inválido
            
            # Log da criação
            log = PropostaLog(
                proposta_id=proposta.id,
                acao="criada",
                usuario_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                observacoes=f"Proposta criada"
            )
            db.session.add(log)
            
            db.session.commit()
            flash(f"Proposta {numero_proposta} criada com sucesso!", "success")
            return redirect(url_for("main.lista_propostas"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar proposta: {str(e)}", "danger")
    
    return render_template("propostas/nova_proposta.html")

@main_bp.route("/propostas/<int:id>")
@login_required
@admin_required
def detalhes_proposta(id):
    """Ver detalhes da proposta"""
    proposta = Proposta.query.get_or_404(id)
    
    # Verificar permissão
    if proposta.admin_id != current_user.id:
        abort(403)
    
    return render_template("propostas/detalhes_proposta.html", proposta=proposta)

@main_bp.route("/propostas/<int:id>/enviar", methods=["POST"])
@login_required
@admin_required
def enviar_proposta(id):
    """Enviar proposta para cliente"""
    proposta = Proposta.query.get_or_404(id)
    
    # Verificar permissão
    if proposta.admin_id != current_user.id:
        abort(403)
    
    # Verificar se pode enviar
    if proposta.status not in ["Rascunho"]:
        flash("Esta proposta não pode ser enviada.", "warning")
        return redirect(url_for("main.detalhes_proposta", id=id))
    
    try:
        # Gerar credenciais do cliente
        login_cliente = f"cliente{proposta.id:04d}"
        senha_temp = secrets.token_urlsafe(8)  # Senha temporária
        token_acesso = secrets.token_urlsafe(32)  # Token para acesso direto
        
        # Atualizar proposta
        proposta.login_cliente = login_cliente
        proposta.senha_cliente = generate_password_hash(senha_temp)
        proposta.token_acesso = token_acesso
        proposta.data_envio = datetime.utcnow()
        proposta.data_expiracao = datetime.utcnow() + timedelta(days=30)
        proposta.status = "Enviada"
        
        # Log do envio
        log = PropostaLog(
            proposta_id=proposta.id,
            acao="enviada",
            usuario_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            observacoes=f"Credenciais geradas: {login_cliente}"
        )
        db.session.add(log)
        
        db.session.commit()
        
        # Mostrar credenciais para o admin
        flash(f"Proposta enviada! Credenciais do cliente:", "success")
        flash(f"Login: {login_cliente}", "info")
        flash(f"Senha: {senha_temp}", "info")
        flash(f"Link direto: {request.url_root}cliente/proposta/{token_acesso}", "info")
        
        return redirect(url_for("main.detalhes_proposta", id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao enviar proposta: {str(e)}", "danger")
        return redirect(url_for("main.detalhes_proposta", id=id))

# ===== PORTAL DO CLIENTE - SEM AUTENTICAÇÃO =====

@main_bp.route("/cliente/proposta/<token>")
def cliente_proposta(token):
    """Portal do cliente para visualizar proposta"""
    proposta = Proposta.query.filter_by(token_acesso=token).first_or_404()
    
    # Verificar expiração
    if proposta.data_expiracao and datetime.utcnow() > proposta.data_expiracao:
        proposta.status = "Expirada"
        db.session.commit()
    
    # Log da visualização
    log = PropostaLog(
        proposta_id=proposta.id,
        acao="visualizada",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        observacoes="Cliente acessou portal"
    )
    db.session.add(log)
    db.session.commit()
    
    return render_template("cliente/proposta_detalhes.html", proposta=proposta)

@main_bp.route("/cliente/proposta/<token>/aprovar", methods=["POST"])
def cliente_aprovar_proposta_final(token):
    """Cliente aprova a proposta"""
    proposta = Proposta.query.filter_by(token_acesso=token).first_or_404()
    
    if proposta.status != "Enviada":
        flash("Esta proposta não pode mais ser aprovada.", "danger")
        return redirect(url_for("main.cliente_proposta", token=token))
    
    try:
        # Atualizar proposta
        proposta.status = "Aprovada"
        proposta.data_resposta = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get("observacoes", "")
        proposta.ip_assinatura = request.remote_addr
        proposta.user_agent_assinatura = request.headers.get("User-Agent")
        
        # Log da aprovação
        log = PropostaLog(
            proposta_id=proposta.id,
            acao="aprovada",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            observacoes=proposta.observacoes_cliente
        )
        db.session.add(log)
        
        # CONVERTER PROPOSTA EM OBRA AUTOMATICAMENTE
        ultimo_codigo = db.session.query(func.max(Obra.codigo)).scalar()
        if ultimo_codigo and ultimo_codigo.startswith("OB-"):
            numero = int(ultimo_codigo.split("-")[-1]) + 1
        else:
            numero = 1
        codigo_obra = f"OB-{numero:04d}"
        
        # Criar obra baseada na proposta
        obra = Obra(
            nome=f"Obra - {proposta.cliente_nome}",
            codigo=codigo_obra,
            endereco=proposta.endereco_obra,
            data_inicio=datetime.now().date(),
            orcamento=proposta.valor_proposta,
            valor_contrato=proposta.valor_proposta,
            area_total_m2=proposta.area_total_m2,
            status="Planejamento",
            admin_id=proposta.admin_id
        )
        db.session.add(obra)
        
        db.session.commit()
        
        flash("Proposta aprovada com sucesso! A obra foi criada automaticamente.", "success")
        return redirect(url_for("main.cliente_proposta", token=token))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao aprovar proposta: {str(e)}", "danger")
        return redirect(url_for("main.cliente_proposta", token=token))

@main_bp.route("/cliente/proposta/<token>/rejeitar", methods=["POST"])
def cliente_rejeitar_proposta(token):
    """Cliente rejeita a proposta"""
    proposta = Proposta.query.filter_by(token_acesso=token).first_or_404()
    
    if proposta.status != "Enviada":
        flash("Esta proposta não pode mais ser rejeitada.", "danger")
        return redirect(url_for("main.cliente_proposta", token=token))
    
    try:
        # Atualizar proposta
        proposta.status = "Rejeitada"
        proposta.data_resposta = datetime.utcnow()
        proposta.observacoes_cliente = request.form.get("observacoes", "")
        proposta.ip_assinatura = request.remote_addr
        proposta.user_agent_assinatura = request.headers.get("User-Agent")
        
        # Log da rejeição
        log = PropostaLog(
            proposta_id=proposta.id,
            acao="rejeitada",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            observacoes=proposta.observacoes_cliente
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash("Proposta rejeitada. Obrigado pelo seu tempo.", "info")
        return redirect(url_for("main.cliente_proposta", token=token))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao rejeitar proposta: {str(e)}", "danger")
        return redirect(url_for("main.cliente_proposta", token=token))
