from models import db
"""
Views para o Módulo 7 - Sistema Contábil Completo
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models import SpedContabil, DREMensal, BalancoPatrimonial, LancamentoContabil, PlanoContas, BalanceteMensal, AuditoriaContabil, TipoUsuario, PartidaContabil, CentroCustoContabil, db
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
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
    
    # Gerar lista de competências
    mes_atual = date.today().replace(day=1)
    competencias = []
    for i in range(-12, 3):
        mes_comp = mes_atual + relativedelta(months=i)
        competencias.append({
            'ano': mes_comp.year,
            'mes': mes_comp.month,
            'label': mes_comp.strftime('%B/%Y').capitalize(),
            'valor': f"{mes_comp.year}-{mes_comp.month:02d}"
        })
    comp_selecionada = f"{ano}-{mes:02d}"
    
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
                         competencias=competencias,
                         comp_selecionada=comp_selecionada,
                         now=datetime.now())

@contabilidade_bp.route('/razao/<conta_codigo>')
@admin_required
def razao(conta_codigo):
    """Razão Analítico - Detailed ledger for a specific account"""
    from contabilidade_utils import gerar_razao_conta
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    
    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    else:
        data_inicio = date.today().replace(day=1)
    
    if data_fim_str:
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    else:
        data_fim = date.today()
    
    razao_data = gerar_razao_conta(admin_id, conta_codigo, data_inicio, data_fim)
    
    if not razao_data:
        flash(f'Conta {conta_codigo} não encontrada', 'danger')
        return redirect(url_for('contabilidade.balancete'))
    
    return render_template('contabilidade/razao.html',
                         razao=razao_data,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         conta_codigo=conta_codigo)

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
    
    # Gerar lista de competências
    mes_atual = date.today().replace(day=1)
    competencias = []
    for i in range(-12, 3):
        mes_comp = mes_atual + relativedelta(months=i)
        competencias.append({
            'ano': mes_comp.year,
            'mes': mes_comp.month,
            'label': mes_comp.strftime('%B/%Y').capitalize(),
            'valor': f"{mes_comp.year}-{mes_comp.month:02d}"
        })
    comp_selecionada = f"{ano}-{mes:02d}"
    
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
                         competencias=competencias,
                         comp_selecionada=comp_selecionada,
                         meses_nomes=meses_nomes)

# ==================== EXPORTAÇÕES PDF E EXCEL ====================

@contabilidade_bp.route('/balancete/pdf')
@admin_required
def balancete_pdf():
    """Exportar Balancete em PDF"""
    from flask import send_file
    from contabilidade_utils import gerar_balancete_pdf
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obter parâmetros
        mes = int(request.args.get('mes', date.today().month))
        ano = int(request.args.get('ano', date.today().year))
        
        # Validar
        if mes < 1 or mes > 12:
            mes = date.today().month
        if ano < 2020 or ano > 2030:
            ano = date.today().year
        
        # Gerar PDF
        buffer = gerar_balancete_pdf(admin_id, mes, ano)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'balancete_{mes:02d}_{ano}.pdf'
        )
        
    except Exception as e:
        flash(f'Erro ao gerar PDF do balancete: {str(e)}', 'danger')
        return redirect(url_for('contabilidade.balancete'))

@contabilidade_bp.route('/balancete/excel')
@admin_required
def balancete_excel():
    """Exportar Balancete em Excel"""
    from flask import send_file
    from contabilidade_utils import gerar_balancete_excel
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obter parâmetros
        mes = int(request.args.get('mes', date.today().month))
        ano = int(request.args.get('ano', date.today().year))
        
        # Validar
        if mes < 1 or mes > 12:
            mes = date.today().month
        if ano < 2020 or ano > 2030:
            ano = date.today().year
        
        # Gerar Excel
        buffer = gerar_balancete_excel(admin_id, mes, ano)
        
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'balancete_{mes:02d}_{ano}.xlsx'
        )
        
    except Exception as e:
        flash(f'Erro ao gerar Excel do balancete: {str(e)}', 'danger')
        return redirect(url_for('contabilidade.balancete'))

@contabilidade_bp.route('/dre/pdf')
@admin_required
def dre_pdf():
    """Exportar DRE em PDF"""
    from flask import send_file
    from contabilidade_utils import gerar_dre_pdf
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obter parâmetros
        mes = int(request.args.get('mes', date.today().month))
        ano = int(request.args.get('ano', date.today().year))
        
        # Validar
        if mes < 1 or mes > 12:
            mes = date.today().month
        if ano < 2020 or ano > 2030:
            ano = date.today().year
        
        # Gerar PDF
        buffer = gerar_dre_pdf(admin_id, mes, ano)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'dre_{mes:02d}_{ano}.pdf'
        )
        
    except Exception as e:
        flash(f'Erro ao gerar PDF da DRE: {str(e)}', 'danger')
        return redirect(url_for('contabilidade.dre'))

@contabilidade_bp.route('/dre/excel')
@admin_required
def dre_excel():
    """Exportar DRE em Excel"""
    from flask import send_file
    from contabilidade_utils import gerar_dre_excel
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obter parâmetros
        mes = int(request.args.get('mes', date.today().month))
        ano = int(request.args.get('ano', date.today().year))
        
        # Validar
        if mes < 1 or mes > 12:
            mes = date.today().month
        if ano < 2020 or ano > 2030:
            ano = date.today().year
        
        # Gerar Excel
        buffer = gerar_dre_excel(admin_id, mes, ano)
        
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'dre_{mes:02d}_{ano}.xlsx'
        )
        
    except Exception as e:
        flash(f'Erro ao gerar Excel da DRE: {str(e)}', 'danger')
        return redirect(url_for('contabilidade.dre'))

@contabilidade_bp.route('/balanco')
@admin_required
def balanco_patrimonial():
    """Balanço Patrimonial com cálculo dinâmico baseado em lançamentos"""
    from contabilidade_utils import gerar_balanco_patrimonial
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    data_ref = request.args.get('data', date.today().isoformat())
    data_referencia = datetime.strptime(data_ref, '%Y-%m-%d').date()
    
    balanco_data = gerar_balanco_patrimonial(admin_id, data_referencia)
    
    return render_template('contabilidade/balanco.html',
                         balanco=balanco_data,
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

# ==================== CENTROS DE CUSTO CONTÁBIL ====================

@contabilidade_bp.route('/centros-custo')
@admin_required
def centros_custo():
    """Lista de Centros de Custo Contábil com filtros"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Query base
    query = CentroCustoContabil.query.filter_by(admin_id=admin_id)
    
    # Filtro por tipo
    tipo = request.args.get('tipo')
    if tipo and tipo in ['OBRA', 'DEPARTAMENTO', 'PROJETO']:
        query = query.filter_by(tipo=tipo)
    
    # Filtro por ativo
    ativo = request.args.get('ativo')
    if ativo == '1':
        query = query.filter_by(ativo=True)
    elif ativo == '0':
        query = query.filter_by(ativo=False)
    
    # Ordenar e paginar
    centros = query.order_by(CentroCustoContabil.codigo).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('contabilidade/centros_custo.html',
                         centros=centros)

@contabilidade_bp.route('/centros-custo/criar', methods=['GET', 'POST'])
@admin_required
def criar_centro_custo():
    """Criar novo Centro de Custo"""
    from models import Obra
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo', '').strip().upper()
            nome = request.form.get('nome', '').strip()
            tipo = request.form.get('tipo', '').strip()
            descricao = request.form.get('descricao', '').strip()
            obra_id = request.form.get('obra_id')
            ativo = request.form.get('ativo') == 'on'
            
            # Validações
            if not codigo or not nome or not tipo:
                flash('Código, Nome e Tipo são obrigatórios', 'danger')
                return redirect(url_for('contabilidade.criar_centro_custo'))
            
            if tipo not in ['OBRA', 'DEPARTAMENTO', 'PROJETO']:
                flash('Tipo inválido', 'danger')
                return redirect(url_for('contabilidade.criar_centro_custo'))
            
            # Verificar unicidade do código
            existe = CentroCustoContabil.query.filter_by(
                codigo=codigo,
                admin_id=admin_id
            ).first()
            if existe:
                flash(f'Código {codigo} já existe. Escolha outro código.', 'danger')
                return redirect(url_for('contabilidade.criar_centro_custo'))
            
            # Validar obra_id se tipo=OBRA
            if tipo == 'OBRA' and obra_id:
                obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
                if not obra:
                    flash('Obra não encontrada', 'danger')
                    return redirect(url_for('contabilidade.criar_centro_custo'))
            elif tipo == 'OBRA':
                obra_id = None  # Tipo OBRA mas sem obra selecionada é permitido
            else:
                obra_id = None  # Outros tipos não têm obra
            
            # Criar centro de custo
            centro = CentroCustoContabil(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                descricao=descricao if descricao else None,
                obra_id=int(obra_id) if obra_id else None,
                ativo=ativo,
                admin_id=admin_id
            )
            db.session.add(centro)
            db.session.commit()
            
            flash(f'Centro de Custo {codigo} - {nome} criado com sucesso!', 'success')
            return redirect(url_for('contabilidade.centros_custo'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar Centro de Custo: {str(e)}', 'danger')
            return redirect(url_for('contabilidade.criar_centro_custo'))
    
    # GET - Sugerir próximo código
    ultimo_centro = CentroCustoContabil.query.filter_by(admin_id=admin_id)\
                                           .order_by(CentroCustoContabil.codigo.desc())\
                                           .first()
    if ultimo_centro and ultimo_centro.codigo.startswith('CC-'):
        try:
            num = int(ultimo_centro.codigo.split('-')[1])
            codigo_sugerido = f'CC-{num + 1:03d}'
        except:
            codigo_sugerido = 'CC-001'
    else:
        codigo_sugerido = 'CC-001'
    
    # Buscar obras para o dropdown
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True)\
                     .order_by(Obra.nome).all()
    
    return render_template('contabilidade/centro_custo_form.html',
                         centro=None,
                         codigo_sugerido=codigo_sugerido,
                         obras=obras)

@contabilidade_bp.route('/centros-custo/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_centro_custo(id):
    """Editar Centro de Custo existente"""
    from models import Obra
    
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    centro = CentroCustoContabil.query.filter_by(id=id, admin_id=admin_id).first()
    if not centro:
        flash('Centro de Custo não encontrado', 'danger')
        return redirect(url_for('contabilidade.centros_custo'))
    
    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo', '').strip().upper()
            nome = request.form.get('nome', '').strip()
            tipo = request.form.get('tipo', '').strip()
            descricao = request.form.get('descricao', '').strip()
            obra_id = request.form.get('obra_id')
            ativo = request.form.get('ativo') == 'on'
            
            # Validações
            if not codigo or not nome or not tipo:
                flash('Código, Nome e Tipo são obrigatórios', 'danger')
                return redirect(url_for('contabilidade.editar_centro_custo', id=id))
            
            if tipo not in ['OBRA', 'DEPARTAMENTO', 'PROJETO']:
                flash('Tipo inválido', 'danger')
                return redirect(url_for('contabilidade.editar_centro_custo', id=id))
            
            # Verificar se código mudou e se já existe
            if codigo != centro.codigo:
                # Verificar se o código está sendo usado em partidas
                partidas_count = PartidaContabil.query.filter_by(
                    centro_custo_id=centro.id,
                    admin_id=admin_id
                ).count()
                if partidas_count > 0:
                    flash('Não é possível alterar o código. Este Centro de Custo já possui lançamentos.', 'danger')
                    return redirect(url_for('contabilidade.editar_centro_custo', id=id))
                
                # Verificar unicidade do novo código
                existe = CentroCustoContabil.query.filter_by(
                    codigo=codigo,
                    admin_id=admin_id
                ).filter(CentroCustoContabil.id != id).first()
                if existe:
                    flash(f'Código {codigo} já existe. Escolha outro código.', 'danger')
                    return redirect(url_for('contabilidade.editar_centro_custo', id=id))
            
            # Validar obra_id se tipo=OBRA
            if tipo == 'OBRA' and obra_id:
                obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
                if not obra:
                    flash('Obra não encontrada', 'danger')
                    return redirect(url_for('contabilidade.editar_centro_custo', id=id))
            elif tipo == 'OBRA':
                obra_id = None
            else:
                obra_id = None
            
            # Atualizar centro de custo
            centro.codigo = codigo
            centro.nome = nome
            centro.tipo = tipo
            centro.descricao = descricao if descricao else None
            centro.obra_id = int(obra_id) if obra_id else None
            centro.ativo = ativo
            
            db.session.commit()
            
            flash(f'Centro de Custo {codigo} - {nome} atualizado com sucesso!', 'success')
            return redirect(url_for('contabilidade.centros_custo'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar Centro de Custo: {str(e)}', 'danger')
            return redirect(url_for('contabilidade.editar_centro_custo', id=id))
    
    # GET - Buscar obras para o dropdown
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True)\
                     .order_by(Obra.nome).all()
    
    return render_template('contabilidade/centro_custo_form.html',
                         centro=centro,
                         codigo_sugerido=None,
                         obras=obras)

@contabilidade_bp.route('/centros-custo/desativar/<int:id>', methods=['POST'])
@admin_required
def desativar_centro_custo(id):
    """Desativar Centro de Custo (soft delete)"""
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
    
    centro = CentroCustoContabil.query.filter_by(id=id, admin_id=admin_id).first()
    if not centro:
        return jsonify({'success': False, 'message': 'Centro de Custo não encontrado'}), 404
    
    try:
        # Verificar se há lançamentos ativos usando este centro de custo
        lancamentos_ativos = db.session.query(LancamentoContabil)\
            .join(PartidaContabil)\
            .filter(
                PartidaContabil.centro_custo_id == centro.id,
                LancamentoContabil.admin_id == admin_id,
                ~LancamentoContabil.historico.ilike('%ESTORNADO%')
            ).count()
        
        if lancamentos_ativos > 0:
            return jsonify({
                'success': False, 
                'message': f'Não é possível desativar. Existem {lancamentos_ativos} lançamentos ativos usando este Centro de Custo.'
            }), 400
        
        # Desativar
        centro.ativo = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Centro de Custo {centro.codigo} - {centro.nome} desativado com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@contabilidade_bp.route('/centros-custo/<int:id>/custos')
@admin_required
def centro_custo_custos(id):
    """Relatório de custos por Centro de Custo"""
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))
    
    centro = CentroCustoContabil.query.filter_by(id=id, admin_id=admin_id).first()
    if not centro:
        flash('Centro de Custo não encontrado', 'danger')
        return redirect(url_for('contabilidade.centros_custo'))
    
    # Filtros de data
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Query de partidas vinculadas ao centro de custo
    query = db.session.query(PartidaContabil, LancamentoContabil, PlanoContas)\
        .join(LancamentoContabil, PartidaContabil.lancamento_id == LancamentoContabil.id)\
        .join(PlanoContas, PartidaContabil.conta_codigo == PlanoContas.codigo)\
        .filter(
            PartidaContabil.centro_custo_id == centro.id,
            PartidaContabil.admin_id == admin_id
        )
    
    if data_inicio:
        query = query.filter(LancamentoContabil.data_lancamento >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(LancamentoContabil.data_lancamento <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    
    partidas = query.order_by(LancamentoContabil.data_lancamento.desc()).all()
    
    # Calcular totais
    total_debitos = sum(p.valor for p, l, c in partidas if p.tipo_partida == 'DEBITO')
    total_creditos = sum(p.valor for p, l, c in partidas if p.tipo_partida == 'CREDITO')
    
    # Agrupar por mês
    por_mes = {}
    for partida, lancamento, conta in partidas:
        mes_ref = lancamento.data_lancamento.replace(day=1)
        if mes_ref not in por_mes:
            por_mes[mes_ref] = {'debitos': Decimal('0'), 'creditos': Decimal('0'), 'total': Decimal('0')}
        
        if partida.tipo_partida == 'DEBITO':
            por_mes[mes_ref]['debitos'] += partida.valor
            por_mes[mes_ref]['total'] += partida.valor
        else:
            por_mes[mes_ref]['creditos'] += partida.valor
            por_mes[mes_ref]['total'] -= partida.valor
    
    # Ordenar por mês
    por_mes_ordenado = sorted(por_mes.items(), key=lambda x: x[0])
    
    return render_template('contabilidade/centro_custo_custos.html',
                         centro=centro,
                         partidas=partidas,
                         total_debitos=total_debitos,
                         total_creditos=total_creditos,
                         por_mes=por_mes_ordenado)

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