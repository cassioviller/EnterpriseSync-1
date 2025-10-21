from models import db
"""
Views para o Módulo 7 - Sistema Contábil Completo
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models import SpedContabil, DREMensal, BalancoPatrimonial, LancamentoContabil, PlanoContas, BalanceteMensal, AuditoriaContabil, TipoUsuario, PartidaContabil, CentroCustoContabil, db
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from decimal import Decimal
import calendar

contabilidade_bp = Blueprint('contabilidade', __name__)

def get_admin_id():
    """
    Retorna admin_id correto independente do tipo de usuário
    """
    if not current_user.is_authenticated:
        return None
    
    if current_user.tipo_usuario == TipoUsuario.ADMIN:
        return current_user.id
    elif hasattr(current_user, 'admin_id'):
        return current_user.admin_id
    
    return None

def admin_required(f):
    """Decorator simples para admin - implementação temporária"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        # Verificação simplificada para Admin
        if hasattr(current_user, 'tipo_usuario') and current_user.tipo_usuario and current_user.tipo_usuario.name in ['ADMIN', 'SUPER_ADMIN']:
            return f(*args, **kwargs)
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('main.dashboard'))
    return decorated_function

@contabilidade_bp.route('/dashboard')
@admin_required
def dashboard_contabil():
    """Dashboard principal da contabilidade"""
    from contabilidade_utils import calcular_saldo_conta
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    hoje = date.today()
    mes_atual = hoje.replace(day=1)
    
    # Buscar DRE do mês atual
    dre_atual = DREMensal.query.filter_by(
        admin_id=admin_id,
        mes_referencia=mes_atual
    ).first()
    
    # Buscar último balanço
    balanco_atual = BalancoPatrimonial.query.filter_by(
        admin_id=admin_id
    ).order_by(BalancoPatrimonial.data_referencia.desc()).first()
    
    # Estatísticas rápidas
    total_lancamentos = LancamentoContabil.query.filter_by(admin_id=admin_id).count()
    
    # Saldos principais
    saldo_caixa = calcular_saldo_conta('1.1.01.001', admin_id)
    saldo_bancos = calcular_saldo_conta('1.1.01.002', admin_id)
    saldo_clientes = calcular_saldo_conta('1.1.02.001', admin_id)
    
    return render_template('contabilidade/dashboard.html',
                         dre_atual=dre_atual,
                         balanco_atual=balanco_atual,
                         total_lancamentos=total_lancamentos,
                         saldo_caixa=saldo_caixa,
                         saldo_bancos=saldo_bancos,
                         saldo_clientes=saldo_clientes,
                         mes_atual=mes_atual)

@contabilidade_bp.route('/plano-contas')
@admin_required
def plano_de_contas():
    """Exibir plano de contas"""
    from contabilidade_utils import criar_plano_contas_padrao
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Criar plano de contas se não existir
    if not PlanoContas.query.filter_by(admin_id=admin_id).first():
        criar_plano_contas_padrao(admin_id)
        flash('Plano de contas padrão criado automaticamente.', 'success')
    
    contas = PlanoContas.query.filter_by(admin_id=admin_id).order_by(PlanoContas.codigo).all()
    
    return render_template('contabilidade/plano_contas.html',
                         contas=contas)

@contabilidade_bp.route('/lancamentos')
@admin_required
def lancamentos_contabeis():
    """Listar lançamentos contábeis com filtros"""
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filtros
    query = LancamentoContabil.query.filter_by(admin_id=admin_id)
    
    # Filtro por data
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    if data_inicio:
        query = query.filter(LancamentoContabil.data_lancamento >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(LancamentoContabil.data_lancamento <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    # Filtro por origem
    origem = request.args.get('origem')
    if origem:
        query = query.filter(LancamentoContabil.origem == origem)
    
    # Filtro por conta
    conta_codigo = request.args.get('conta_codigo')
    if conta_codigo:
        query = query.join(PartidaContabil).filter(PartidaContabil.conta_codigo == conta_codigo)
    
    lancamentos = query.order_by(LancamentoContabil.data_lancamento.desc(), 
                                LancamentoContabil.numero.desc())\
                      .paginate(page=page, per_page=per_page, error_out=False)
    
    # Contas para filtro
    contas = PlanoContas.query.filter_by(admin_id=admin_id, aceita_lancamento=True)\
                              .order_by(PlanoContas.codigo).all()
    
    return render_template('contabilidade/lancamentos.html',
                         lancamentos=lancamentos,
                         contas=contas)

@contabilidade_bp.route('/lancamentos/criar', methods=['GET', 'POST'])
@admin_required
def criar_lancamento():
    """Criar novo lançamento contábil"""
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Buscar contas analíticas (aceita_lancamento=True)
    contas_obj = PlanoContas.query.filter_by(admin_id=admin_id, aceita_lancamento=True)\
                              .order_by(PlanoContas.codigo).all()
    
    # Converter para dicionários JSON-serializáveis
    contas = [{'codigo': c.codigo, 'nome': c.nome} for c in contas_obj]
    
    # Buscar centros de custo
    centros_custo_obj = CentroCustoContabil.query.filter_by(admin_id=admin_id, ativo=True)\
                                             .order_by(CentroCustoContabil.codigo).all()
    
    # Converter para dicionários JSON-serializáveis
    centros_custo = [{'id': cc.id, 'codigo': cc.codigo, 'nome': cc.nome} for cc in centros_custo_obj]
    
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            data_lancamento = datetime.strptime(request.form.get('data_lancamento'), '%Y-%m-%d').date()
            historico = request.form.get('historico', '').strip()
            
            if not historico:
                flash('Histórico é obrigatório', 'danger')
                return redirect(url_for('contabilidade.criar_lancamento'))
            
            # Processar partidas
            partidas_data = []
            total_debito = Decimal('0')
            total_credito = Decimal('0')
            
            # Obter número de partidas
            num_partidas = int(request.form.get('num_partidas', 0))
            
            for i in range(num_partidas):
                tipo = request.form.get(f'partidas[{i}][tipo]')
                conta_codigo = request.form.get(f'partidas[{i}][conta]')
                valor = request.form.get(f'partidas[{i}][valor]')
                centro_custo_id = request.form.get(f'partidas[{i}][centro_custo]')
                historico_comp = request.form.get(f'partidas[{i}][historico_comp]', '')
                
                if not tipo or not conta_codigo or not valor:
                    continue
                
                valor_decimal = Decimal(valor.replace(',', '.'))
                
                # Verificar se conta aceita lançamento
                conta = PlanoContas.query.filter_by(codigo=conta_codigo, admin_id=admin_id).first()
                if not conta or not conta.aceita_lancamento:
                    flash(f'Conta {conta_codigo} não aceita lançamentos', 'danger')
                    return redirect(url_for('contabilidade.criar_lancamento'))
                
                partidas_data.append({
                    'tipo': tipo,
                    'conta': conta_codigo,
                    'valor': valor_decimal,
                    'centro_custo_id': int(centro_custo_id) if centro_custo_id else None,
                    'historico_comp': historico_comp
                })
                
                if tipo == 'DEBITO':
                    total_debito += valor_decimal
                else:
                    total_credito += valor_decimal
            
            # Validar partidas dobradas
            if len(partidas_data) < 2:
                flash('É necessário pelo menos 2 partidas (1 débito e 1 crédito)', 'danger')
                return redirect(url_for('contabilidade.criar_lancamento'))
            
            if abs(total_debito - total_credito) > Decimal('0.01'):
                flash(f'Erro: Débitos (R$ {total_debito}) devem ser iguais aos Créditos (R$ {total_credito})', 'danger')
                return redirect(url_for('contabilidade.criar_lancamento'))
            
            # Criar lançamento
            from contabilidade_utils import get_next_lancamento_numero
            
            lancamento = LancamentoContabil(
                numero=get_next_lancamento_numero(admin_id),
                data_lancamento=data_lancamento,
                historico=historico,
                valor_total=total_debito,
                origem='MANUAL',
                usuario_id=current_user.id,
                admin_id=admin_id
            )
            db.session.add(lancamento)
            db.session.flush()
            
            # Criar partidas
            for i, p in enumerate(partidas_data):
                partida = PartidaContabil(
                    lancamento_id=lancamento.id,
                    sequencia=i + 1,
                    conta_codigo=p['conta'],
                    centro_custo_id=p['centro_custo_id'],
                    tipo_partida=p['tipo'],
                    valor=p['valor'],
                    historico_complementar=p['historico_comp'],
                    admin_id=admin_id
                )
                db.session.add(partida)
            
            db.session.commit()
            flash(f'Lançamento #{lancamento.numero} criado com sucesso!', 'success')
            return redirect(url_for('contabilidade.ver_lancamento', id=lancamento.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar lançamento: {str(e)}', 'danger')
            return redirect(url_for('contabilidade.criar_lancamento'))
    
    return render_template('contabilidade/lancamento_form.html',
                         contas=contas,
                         centros_custo=centros_custo,
                         lancamento=None)

@contabilidade_bp.route('/lancamentos/<int:id>')
@admin_required
def ver_lancamento(id):
    """Visualizar detalhes do lançamento"""
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    lancamento = LancamentoContabil.query.filter_by(id=id, admin_id=admin_id).first()
    if not lancamento:
        flash('Lançamento não encontrado', 'danger')
        return redirect(url_for('contabilidade.lancamentos_contabeis'))
    
    # Verificar se foi estornado (histórico contém ESTORNADO)
    estornado = 'ESTORNADO' in lancamento.historico.upper()
    
    # Calcular totais
    total_debito = sum(p.valor for p in lancamento.partidas if p.tipo_partida == 'DEBITO')
    total_credito = sum(p.valor for p in lancamento.partidas if p.tipo_partida == 'CREDITO')
    
    return render_template('contabilidade/lancamento_detalhes.html',
                         lancamento=lancamento,
                         estornado=estornado,
                         total_debito=total_debito,
                         total_credito=total_credito)

@contabilidade_bp.route('/lancamentos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_lancamento(id):
    """Editar lançamento contábil"""
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    lancamento = LancamentoContabil.query.filter_by(id=id, admin_id=admin_id).first()
    if not lancamento:
        flash('Lançamento não encontrado', 'danger')
        return redirect(url_for('contabilidade.lancamentos_contabeis'))
    
    # Verificar se foi estornado
    if 'ESTORNADO' in lancamento.historico.upper():
        flash('Lançamento estornado não pode ser editado', 'warning')
        return redirect(url_for('contabilidade.ver_lancamento', id=id))
    
    # Buscar contas analíticas
    contas_obj = PlanoContas.query.filter_by(admin_id=admin_id, aceita_lancamento=True)\
                              .order_by(PlanoContas.codigo).all()
    
    # Converter para dicionários JSON-serializáveis
    contas = [{'codigo': c.codigo, 'nome': c.nome} for c in contas_obj]
    
    # Buscar centros de custo
    centros_custo_obj = CentroCustoContabil.query.filter_by(admin_id=admin_id, ativo=True)\
                                             .order_by(CentroCustoContabil.codigo).all()
    
    # Converter para dicionários JSON-serializáveis
    centros_custo = [{'id': cc.id, 'codigo': cc.codigo, 'nome': cc.nome} for cc in centros_custo_obj]
    
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            data_lancamento = datetime.strptime(request.form.get('data_lancamento'), '%Y-%m-%d').date()
            historico = request.form.get('historico', '').strip()
            
            if not historico:
                flash('Histórico é obrigatório', 'danger')
                return redirect(url_for('contabilidade.editar_lancamento', id=id))
            
            # Processar partidas
            partidas_data = []
            total_debito = Decimal('0')
            total_credito = Decimal('0')
            
            num_partidas = int(request.form.get('num_partidas', 0))
            
            for i in range(num_partidas):
                tipo = request.form.get(f'partidas[{i}][tipo]')
                conta_codigo = request.form.get(f'partidas[{i}][conta]')
                valor = request.form.get(f'partidas[{i}][valor]')
                centro_custo_id = request.form.get(f'partidas[{i}][centro_custo]')
                historico_comp = request.form.get(f'partidas[{i}][historico_comp]', '')
                
                if not tipo or not conta_codigo or not valor:
                    continue
                
                valor_decimal = Decimal(valor.replace(',', '.'))
                
                # Verificar se conta aceita lançamento
                conta = PlanoContas.query.filter_by(codigo=conta_codigo, admin_id=admin_id).first()
                if not conta or not conta.aceita_lancamento:
                    flash(f'Conta {conta_codigo} não aceita lançamentos', 'danger')
                    return redirect(url_for('contabilidade.editar_lancamento', id=id))
                
                partidas_data.append({
                    'tipo': tipo,
                    'conta': conta_codigo,
                    'valor': valor_decimal,
                    'centro_custo_id': int(centro_custo_id) if centro_custo_id else None,
                    'historico_comp': historico_comp
                })
                
                if tipo == 'DEBITO':
                    total_debito += valor_decimal
                else:
                    total_credito += valor_decimal
            
            # Validar partidas dobradas
            if len(partidas_data) < 2:
                flash('É necessário pelo menos 2 partidas', 'danger')
                return redirect(url_for('contabilidade.editar_lancamento', id=id))
            
            if abs(total_debito - total_credito) > Decimal('0.01'):
                flash(f'Erro: Débitos (R$ {total_debito}) devem ser iguais aos Créditos (R$ {total_credito})', 'danger')
                return redirect(url_for('contabilidade.editar_lancamento', id=id))
            
            # Atualizar lançamento
            lancamento.data_lancamento = data_lancamento
            lancamento.historico = historico
            lancamento.valor_total = total_debito
            
            # Remover partidas antigas
            PartidaContabil.query.filter_by(lancamento_id=lancamento.id).delete()
            
            # Criar novas partidas
            for i, p in enumerate(partidas_data):
                partida = PartidaContabil(
                    lancamento_id=lancamento.id,
                    sequencia=i + 1,
                    conta_codigo=p['conta'],
                    centro_custo_id=p['centro_custo_id'],
                    tipo_partida=p['tipo'],
                    valor=p['valor'],
                    historico_complementar=p['historico_comp'],
                    admin_id=admin_id
                )
                db.session.add(partida)
            
            db.session.commit()
            flash(f'Lançamento #{lancamento.numero} atualizado com sucesso!', 'success')
            return redirect(url_for('contabilidade.ver_lancamento', id=lancamento.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar lançamento: {str(e)}', 'danger')
            return redirect(url_for('contabilidade.editar_lancamento', id=id))
    
    return render_template('contabilidade/lancamento_form.html',
                         contas=contas,
                         centros_custo=centros_custo,
                         lancamento=lancamento)

@contabilidade_bp.route('/lancamentos/estornar/<int:id>', methods=['POST'])
@admin_required
def estornar_lancamento(id):
    """Estornar (reverter) lançamento contábil"""
    
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
    
    lancamento = LancamentoContabil.query.filter_by(id=id, admin_id=admin_id).first()
    if not lancamento:
        return jsonify({'success': False, 'message': 'Lançamento não encontrado'}), 404
    
    # Verificar se já foi estornado
    if 'ESTORNADO' in lancamento.historico.upper():
        return jsonify({'success': False, 'message': 'Lançamento já foi estornado'}), 400
    
    try:
        from contabilidade_utils import get_next_lancamento_numero
        
        # Criar lançamento de estorno (invertendo débitos e créditos)
        lancamento_estorno = LancamentoContabil(
            numero=get_next_lancamento_numero(admin_id),
            data_lancamento=date.today(),
            historico=f'ESTORNO do Lançamento #{lancamento.numero} - {lancamento.historico}',
            valor_total=lancamento.valor_total,
            origem='MANUAL',
            origem_id=lancamento.id,
            usuario_id=current_user.id,
            admin_id=admin_id
        )
        db.session.add(lancamento_estorno)
        db.session.flush()
        
        # Criar partidas invertidas
        for partida in lancamento.partidas:
            # Inverter débito <-> crédito
            tipo_invertido = 'CREDITO' if partida.tipo_partida == 'DEBITO' else 'DEBITO'
            
            partida_estorno = PartidaContabil(
                lancamento_id=lancamento_estorno.id,
                sequencia=partida.sequencia,
                conta_codigo=partida.conta_codigo,
                centro_custo_id=partida.centro_custo_id,
                tipo_partida=tipo_invertido,
                valor=partida.valor,
                historico_complementar=f'Estorno - {partida.historico_complementar or ""}',
                admin_id=admin_id
            )
            db.session.add(partida_estorno)
        
        # Marcar lançamento original como estornado
        lancamento.historico = f'{lancamento.historico} (ESTORNADO em {date.today().strftime("%d/%m/%Y")})'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Lançamento estornado com sucesso! Lançamento de estorno: #{lancamento_estorno.numero}',
            'estorno_id': lancamento_estorno.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao estornar: {str(e)}'}), 500

@contabilidade_bp.route('/balancete')
@admin_required
def balancete():
    """Gerar balancete de verificação mensal com drill-down"""
    from sqlalchemy import func
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Obter mês/ano dos parâmetros ou usar atual
    mes = request.args.get('mes', date.today().month, type=int)
    ano = request.args.get('ano', date.today().year, type=int)
    
    # Validar mês e ano
    if mes < 1 or mes > 12:
        mes = date.today().month
    if ano < 2020 or ano > 2030:
        ano = date.today().year
    
    # Definir período
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    fim_mes_anterior = primeiro_dia - timedelta(days=1)
    
    # Buscar TODAS as contas do plano de contas
    todas_contas = PlanoContas.query.filter_by(admin_id=admin_id).order_by(PlanoContas.codigo).all()
    
    contas_data = []
    total_debitos = Decimal('0')
    total_creditos = Decimal('0')
    total_saldo_devedor = Decimal('0')
    total_saldo_credor = Decimal('0')
    
    for conta in todas_contas:
        # Calcular saldo anterior (até último dia do mês anterior)
        partidas_anteriores = db.session.query(PartidaContabil).join(LancamentoContabil).filter(
            PartidaContabil.conta_codigo == conta.codigo,
            PartidaContabil.admin_id == admin_id,
            LancamentoContabil.data_lancamento <= fim_mes_anterior
        ).all()
        
        debito_anterior = sum(p.valor for p in partidas_anteriores if p.tipo_partida == 'DEBITO')
        credito_anterior = sum(p.valor for p in partidas_anteriores if p.tipo_partida == 'CREDITO')
        
        # Saldo anterior depende da natureza da conta
        if conta.natureza == 'DEVEDORA':
            saldo_anterior = debito_anterior - credito_anterior
        else:  # CREDORA
            saldo_anterior = credito_anterior - debito_anterior
        
        # Calcular movimentação do mês
        partidas_mes = db.session.query(PartidaContabil).join(LancamentoContabil).filter(
            PartidaContabil.conta_codigo == conta.codigo,
            PartidaContabil.admin_id == admin_id,
            LancamentoContabil.data_lancamento >= primeiro_dia,
            LancamentoContabil.data_lancamento <= ultimo_dia
        ).all()
        
        debitos_mes = sum(p.valor for p in partidas_mes if p.tipo_partida == 'DEBITO')
        creditos_mes = sum(p.valor for p in partidas_mes if p.tipo_partida == 'CREDITO')
        
        # Calcular saldo atual
        partidas_ate_hoje = db.session.query(PartidaContabil).join(LancamentoContabil).filter(
            PartidaContabil.conta_codigo == conta.codigo,
            PartidaContabil.admin_id == admin_id,
            LancamentoContabil.data_lancamento <= ultimo_dia
        ).all()
        
        debito_total = sum(p.valor for p in partidas_ate_hoje if p.tipo_partida == 'DEBITO')
        credito_total = sum(p.valor for p in partidas_ate_hoje if p.tipo_partida == 'CREDITO')
        
        if conta.natureza == 'DEVEDORA':
            saldo_atual = debito_total - credito_total
        else:  # CREDORA
            saldo_atual = credito_total - debito_total
        
        # Só mostrar contas com movimento (saldo anterior != 0 OU movimentos no período > 0)
        tem_movimento = (abs(saldo_anterior) > Decimal('0.01') or 
                        abs(debitos_mes) > Decimal('0.01') or 
                        abs(creditos_mes) > Decimal('0.01'))
        
        if tem_movimento:
            contas_data.append({
                'codigo': conta.codigo,
                'nome': conta.nome,
                'nivel': conta.nivel,
                'natureza': conta.natureza,
                'tipo_conta': conta.tipo_conta,
                'saldo_anterior': saldo_anterior,
                'debitos': debitos_mes,
                'creditos': creditos_mes,
                'saldo_atual': saldo_atual,
                'aceita_lancamento': conta.aceita_lancamento
            })
            
            # Acumular totais do período
            total_debitos += debitos_mes
            total_creditos += creditos_mes
            
            # Acumular saldos finais
            if saldo_atual > 0:
                total_saldo_devedor += saldo_atual
            else:
                total_saldo_credor += abs(saldo_atual)
    
    # Verificar equilíbrio contábil
    balanceado = abs(total_debitos - total_creditos) < Decimal('0.01')
    
    # Preparar dados para template
    totais = {
        'total_debitos': total_debitos,
        'total_creditos': total_creditos,
        'total_saldo_devedor': total_saldo_devedor,
        'total_saldo_credor': total_saldo_credor,
        'balanceado': balanceado
    }
    
    return render_template('contabilidade/balancete.html',
                         mes=mes,
                         ano=ano,
                         contas=contas_data,
                         totais=totais,
                         now=datetime.now())

@contabilidade_bp.route('/dre')
@admin_required
def dre():
    """Demonstração do Resultado do Exercício - Estrutura Completa Brasileira"""
    from contabilidade_utils import calcular_dre_mensal
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Obter parâmetros de mês e ano (padrão: mês atual)
    hoje = date.today()
    mes = request.args.get('mes', hoje.month, type=int)
    ano = request.args.get('ano', hoje.year, type=int)
    
    # Validar mês (1-12)
    if mes < 1 or mes > 12:
        mes = hoje.month
    
    # Calcular DRE do mês selecionado
    dre_data = calcular_dre_mensal(admin_id, ano, mes)
    
    # Calcular DRE do mês anterior para comparativo
    if mes == 1:
        mes_anterior = 12
        ano_anterior = ano - 1
    else:
        mes_anterior = mes - 1
        ano_anterior = ano
    
    dre_anterior = calcular_dre_mensal(admin_id, ano_anterior, mes_anterior)
    
    # Calcular variações percentuais (comparativo mês anterior)
    comparativo = {}
    if dre_data and dre_anterior:
        def calcular_variacao(valor_atual, valor_anterior):
            """Calcula variação percentual entre dois valores"""
            if valor_anterior and valor_anterior != 0:
                return ((valor_atual - valor_anterior) / abs(valor_anterior)) * 100
            elif valor_atual != 0:
                return 100.0  # Se não havia valor anterior e agora há, é 100% de crescimento
            else:
                return 0.0
        
        comparativo = {
            'receita_liquida': {
                'anterior': dre_anterior.get('receita_liquida', 0),
                'variacao': calcular_variacao(
                    dre_data.get('receita_liquida', 0),
                    dre_anterior.get('receita_liquida', 0)
                )
            },
            'lucro_bruto': {
                'anterior': dre_anterior.get('lucro_bruto', 0),
                'variacao': calcular_variacao(
                    dre_data.get('lucro_bruto', 0),
                    dre_anterior.get('lucro_bruto', 0)
                )
            },
            'ebitda': {
                'anterior': dre_anterior.get('ebitda', 0),
                'variacao': calcular_variacao(
                    dre_data.get('ebitda', 0),
                    dre_anterior.get('ebitda', 0)
                )
            },
            'lucro_liquido': {
                'anterior': dre_anterior.get('lucro_liquido', 0),
                'variacao': calcular_variacao(
                    dre_data.get('lucro_liquido', 0),
                    dre_anterior.get('lucro_liquido', 0)
                )
            }
        }
    
    # Se não houver dados, criar estrutura vazia
    if not dre_data:
        dre_data = {
            'mes': mes,
            'ano': ano,
            'receita_bruta': 0,
            'deducoes': 0,
            'receita_liquida': 0,
            'cmv': 0,
            'lucro_bruto': 0,
            'despesas_operacionais': {
                'pessoal': 0,
                'materiais': 0,
                'administrativas': 0,
                'comerciais': 0,
                'outras': 0,
                'total': 0
            },
            'ebitda': 0,
            'resultado_financeiro': {
                'receitas': 0,
                'despesas': 0,
                'total': 0
            },
            'resultado_antes_ir': 0,
            'provisao_ir_csll': {
                'ir': 0,
                'csll': 0,
                'total': 0
            },
            'lucro_liquido': 0,
            'percentuais': {
                'margem_bruta': 0,
                'margem_ebitda': 0,
                'margem_liquida': 0
            }
        }
    
    # Nomes dos meses para exibição
    meses_nomes = [
        '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    return render_template('contabilidade/dre.html',
                         dre=dre_data,
                         mes=mes,
                         ano=ano,
                         mes_nome=meses_nomes[mes],
                         mes_anterior=mes_anterior,
                         ano_anterior=ano_anterior,
                         comparativo=comparativo,
                         meses_nomes=meses_nomes)

@contabilidade_bp.route('/balanco-patrimonial')
@admin_required
def balanco_patrimonial():
    """Balanço Patrimonial"""
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    data_ref = request.args.get('data', date.today().isoformat())
    data_referencia = datetime.strptime(data_ref, '%Y-%m-%d').date()
    
    balanco = BalancoPatrimonial.query.filter_by(
        admin_id=admin_id,
        data_referencia=data_referencia
    ).first()
    
    if not balanco:
        # Criar balanço básico se não existir
        balanco = BalancoPatrimonial(
            data_referencia=data_referencia,
            admin_id=admin_id
        )
        db.session.add(balanco)
        db.session.commit()
        flash('Balanço Patrimonial criado automaticamente.', 'info')
    
    return render_template('contabilidade/balanco.html',
                         balanco=balanco,
                         data_referencia=data_referencia)

@contabilidade_bp.route('/auditoria')
@admin_required
def auditoria_contabil():
    """Sistema de auditoria contábil"""
    from contabilidade_utils import executar_auditoria_automatica
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    # Executar auditoria se solicitado
    if request.args.get('executar') == '1':
        try:
            alertas = executar_auditoria_automatica(admin_id)
            flash(f'Auditoria executada. {len(alertas)} alertas encontrados.', 'info')
        except Exception as e:
            flash(f'Erro na auditoria: {str(e)}', 'error')
    
    # Buscar alertas não corrigidos
    alertas = AuditoriaContabil.query.filter_by(
        admin_id=admin_id,
        corrigido=False
    ).order_by(AuditoriaContabil.data_auditoria.desc()).all()
    
    return render_template('contabilidade/auditoria.html',
                         alertas=alertas)

@contabilidade_bp.route('/relatorios')
@admin_required
def relatorios():
    """Central de relatórios contábeis"""
    flash('Central de relatórios em desenvolvimento.', 'info')
    return render_template('contabilidade/relatorios.html')

@contabilidade_bp.route('/sped')
@admin_required
def sped():
    """Geração de SPED Contábil"""
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    speds = SpedContabil.query.filter_by(admin_id=admin_id)\
                             .order_by(SpedContabil.data_geracao.desc()).all()
    
    return render_template('contabilidade/sped.html',
                         speds=speds)

# APIs para integração

@contabilidade_bp.route('/api/processar-integracao', methods=['POST'])
@admin_required
def processar_integracao():
    """API para processar integrações automáticas"""
    from contabilidade_utils import (contabilizar_proposta_aprovada, 
                                   contabilizar_entrada_material, 
                                   contabilizar_folha_pagamento)
    
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
    
    try:
        data = request.json or {}
        tipo = data.get('tipo')
        origem_id = data.get('origem_id')
        
        if tipo == 'proposta_aprovada':
            contabilizar_proposta_aprovada(origem_id)
        elif tipo == 'entrada_material':
            contabilizar_entrada_material(origem_id)
        elif tipo == 'folha_pagamento':
            mes_ref = datetime.strptime(data.get('mes_referencia'), '%Y-%m-%d').date()
            contabilizar_folha_pagamento(admin_id, mes_ref)
        
        return jsonify({'success': True, 'message': 'Integração processada com sucesso'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400