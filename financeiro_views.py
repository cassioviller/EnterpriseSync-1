"""
Blueprint Financeiro v9.0
Rotas para gestão financeira completa
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta, date
from decimal import Decimal
from app import db
from models import (
    ContaPagar, ContaReceber, BancoEmpresa, Fornecedor, 
    PlanoContas, Obra, CentroCusto, GestaoCustoPai, FluxoCaixa
)
from utils.tenant import is_v2_active
from financeiro_service import FinanceiroService
from multitenant_helper import get_admin_id
import logging

logger = logging.getLogger(__name__)

financeiro_bp = Blueprint('financeiro', __name__, url_prefix='/financeiro')


def _parse_valor(raw: str) -> float:
    """Converte string de valor em float suportando formatos BRL e internacionais.
    
    Suporta: '100.00', '100,00', '1.234,56', '1,234.56'
    """
    raw = raw.strip().replace(' ', '').replace('R$', '').replace('\xa0', '')
    if not raw:
        return 0.0
    # Formato BRL: separador de milhar = '.', decimal = ',' (ex: 1.234,56)
    if ',' in raw and '.' in raw:
        if raw.rfind(',') > raw.rfind('.'):
            # último separador é vírgula → BRL (1.234,56)
            raw = raw.replace('.', '').replace(',', '.')
        else:
            # último separador é ponto → EN (1,234.56)
            raw = raw.replace(',', '')
    elif ',' in raw:
        # somente vírgula → substituir por ponto
        raw = raw.replace(',', '.')
    return float(raw)


# ==================== DASHBOARD ====================

@financeiro_bp.route('/')
@login_required
def dashboard():
    """Dashboard financeiro com KPIs"""
    try:
        admin_id = get_admin_id()
        
        hoje = date.today()
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        if data_inicio:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        else:
            data_inicio = date(hoje.year, hoje.month, 1)
        
        if data_fim:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        else:
            data_fim = hoje
        
        # KPIs principais
        kpis = FinanceiroService.obter_kpis_financeiros(admin_id)
        
        # Alertas de vencimento (próximos 7 dias)
        alertas_pagar = FinanceiroService.alertas_vencimento_pagar(admin_id, dias=7)
        
        # Contas vencidas
        vencidas_pagar = FinanceiroService.listar_contas_pagar(admin_id, vencidas=True)
        vencidas_receber = FinanceiroService.listar_contas_receber(admin_id, vencidas=True)
        
        # Receitas recentes (últimas 10 contas a receber)
        receitas_recentes = ContaReceber.query.filter_by(admin_id=admin_id).order_by(
            ContaReceber.data_vencimento.desc()
        ).limit(10).all()
        
        # Centros de custo
        centros_custo = []
        try:
            centros_custo = CentroCusto.query.filter_by(admin_id=admin_id).all()
        except Exception:
            pass
        
        return render_template(
            'financeiro/dashboard.html',
            kpis=kpis,
            alertas_pagar=alertas_pagar,
            vencidas_pagar=vencidas_pagar,
            vencidas_receber=vencidas_receber,
            receitas_recentes=receitas_recentes,
            centros_custo=centros_custo,
            data_inicio=data_inicio.strftime('%Y-%m-%d'),
            data_fim=data_fim.strftime('%Y-%m-%d')
        )
    except Exception as e:
        logger.error(f"Erro no dashboard financeiro: {str(e)}")
        flash('Erro ao carregar dashboard financeiro', 'danger')
        return redirect(url_for('main.index'))


# ==================== CONTAS A PAGAR ====================

@financeiro_bp.route('/contas-pagar')
@login_required
def listar_contas_pagar():
    """Lista contas a pagar"""
    admin_id = get_admin_id()
    
    # Filtros
    status = request.args.get('status')
    obra_id = request.args.get('obra_id', type=int)
    
    contas = FinanceiroService.listar_contas_pagar(
        admin_id, 
        status=status, 
        obra_id=obra_id
    )
    
    # Obras para filtro
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    # Bancos para dropdown de baixa
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    # Resumo financeiro
    hoje = date.today()
    vencidas = sum(c.saldo for c in ContaPagar.query.filter_by(admin_id=admin_id).filter(
        ContaPagar.data_vencimento < hoje,
        ContaPagar.status.in_(['PENDENTE', 'PARCIAL'])
    ).all())
    
    a_vencer = sum(c.saldo for c in ContaPagar.query.filter_by(admin_id=admin_id).filter(
        ContaPagar.data_vencimento >= hoje,
        ContaPagar.data_vencimento <= hoje + timedelta(days=7),
        ContaPagar.status.in_(['PENDENTE', 'PARCIAL'])
    ).all())
    
    pendentes = sum(c.saldo for c in ContaPagar.query.filter_by(admin_id=admin_id, status='PENDENTE').all())
    
    pagas_mes = sum(c.valor_pago for c in ContaPagar.query.filter_by(admin_id=admin_id).filter(
        ContaPagar.data_pagamento >= date(hoje.year, hoje.month, 1),
        ContaPagar.data_pagamento <= hoje
    ).all())
    
    # Gestão de Custos V2 — mostrar pendentes/autorizados no contas a pagar
    v2 = is_v2_active()
    custos_v2 = []
    if v2:
        custos_v2 = GestaoCustoPai.query.filter(
            GestaoCustoPai.admin_id == admin_id,
            GestaoCustoPai.status.in_(['SOLICITADO', 'AUTORIZADO'])
        ).order_by(GestaoCustoPai.data_criacao.desc()).all()

    # Incorporar custos V2 nos KPI cards usando regra canônica (valor_solicitado tem prioridade)
    valor_v2 = sum(float(c.valor_solicitado or c.valor_total) for c in custos_v2)
    semana = hoje + timedelta(days=7)
    # "a vencer": data_vencimento (se existir) ou data_criacao no intervalo [hoje, hoje+7d]
    def _data_ref_v2(c):
        return c.data_vencimento if c.data_vencimento else (c.data_criacao.date() if c.data_criacao else None)
    v2_a_vencer = sum(
        float(c.valor_solicitado or c.valor_total) for c in custos_v2
        if _data_ref_v2(c) and hoje <= _data_ref_v2(c) <= semana
    )
    # "vencidas": data_vencimento (ou data_criacao) < hoje (overdue)
    v2_vencidas = sum(
        float(c.valor_solicitado or c.valor_total) for c in custos_v2
        if _data_ref_v2(c) and _data_ref_v2(c) < hoje
    )

    resumo = {
        'vencidas': float(vencidas) + v2_vencidas,
        'a_vencer': float(a_vencer) + v2_a_vencer,
        'pendentes': float(pendentes) + valor_v2,
        'pagas_mes': pagas_mes
    }

    return render_template(
        'financeiro/contas_pagar.html',
        contas=contas,
        obras=obras,
        bancos=bancos,
        resumo=resumo,
        status_selecionado=status,
        obra_selecionada=obra_id,
        datetime=datetime,
        custos_v2=custos_v2,
        is_v2=v2,
    )


@financeiro_bp.route('/contas-pagar/criar', methods=['POST'])
@login_required
def criar_conta_pagar():
    """Redireciona criação de conta a pagar para Gestão de Custos"""
    flash('O lançamento de novas despesas é feito pela Gestão de Custos. Use o botão "Novo Lançamento" abaixo.', 'info')
    return redirect(url_for('gestao_custos.novo'))


@financeiro_bp.route('/contas-pagar/nova', methods=['GET', 'POST'])
@login_required
def nova_conta_pagar():
    """Redireciona para Gestão de Custos"""
    flash('O lançamento de novas despesas é feito pela Gestão de Custos.', 'info')
    return redirect(url_for('gestao_custos.novo'))


@financeiro_bp.route('/contas-pagar/<int:conta_id>/pagar', methods=['GET', 'POST'])
@login_required
def pagar_conta(conta_id):
    """Registrar pagamento de conta"""
    admin_id = get_admin_id()
    
    conta = ContaPagar.query.filter_by(id=conta_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            valor_pago = Decimal(request.form.get('valor_pago'))
            data_pagamento = datetime.strptime(
                request.form.get('data_pagamento'),
                '%Y-%m-%d'
            ).date()
            forma_pagamento = request.form.get('forma_pagamento')
            banco_id = request.form.get('banco_id', type=int) or None
            
            FinanceiroService.baixar_pagamento(
                conta_id=conta_id,
                admin_id=admin_id,
                valor_pago=valor_pago,
                data_pagamento=data_pagamento,
                forma_pagamento=forma_pagamento,
                banco_id=banco_id
            )
            
            flash(f'Pagamento de R$ {valor_pago} registrado com sucesso!', 'success')
            return redirect(url_for('financeiro.listar_contas_pagar'))
            
        except Exception as e:
            logger.error(f"Erro ao registrar pagamento: {str(e)}")
            flash('Erro ao registrar pagamento', 'danger')
    
    # GET - exibir formulário
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template(
        'financeiro/pagar_conta.html',
        conta=conta,
        bancos=bancos
    )


# ==================== CONTAS A RECEBER ====================

@financeiro_bp.route('/contas-receber')
@login_required
def listar_contas_receber():
    """Lista contas a receber"""
    admin_id = get_admin_id()
    
    # Filtros
    status = request.args.get('status')
    obra_id = request.args.get('obra_id', type=int)
    
    contas = FinanceiroService.listar_contas_receber(
        admin_id,
        status=status,
        obra_id=obra_id
    )
    
    # Obras para filtro
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    # Bancos para dropdown de baixa
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    # Resumo financeiro
    hoje = date.today()
    vencidas = sum(c.saldo for c in ContaReceber.query.filter_by(admin_id=admin_id).filter(
        ContaReceber.data_vencimento < hoje,
        ContaReceber.status.in_(['PENDENTE', 'PARCIAL'])
    ).all())
    
    a_vencer = sum(c.saldo for c in ContaReceber.query.filter_by(admin_id=admin_id).filter(
        ContaReceber.data_vencimento >= hoje,
        ContaReceber.data_vencimento <= hoje + timedelta(days=7),
        ContaReceber.status.in_(['PENDENTE', 'PARCIAL'])
    ).all())
    
    pendentes = sum(c.saldo for c in ContaReceber.query.filter_by(admin_id=admin_id, status='PENDENTE').all())
    
    recebidas_mes = sum(c.valor_recebido for c in ContaReceber.query.filter_by(admin_id=admin_id).filter(
        ContaReceber.data_recebimento >= date(hoje.year, hoje.month, 1),
        ContaReceber.data_recebimento <= hoje
    ).all())
    
    resumo = {
        'vencidas': vencidas,
        'a_vencer': a_vencer,
        'pendentes': pendentes,
        'recebidas_mes': recebidas_mes
    }
    
    return render_template(
        'financeiro/contas_receber.html',
        contas=contas,
        obras=obras,
        bancos=bancos,
        resumo=resumo,
        status_selecionado=status,
        obra_selecionada=obra_id,
        datetime=datetime
    )


@financeiro_bp.route('/contas-receber/criar', methods=['POST'])
@login_required
def criar_conta_receber():
    """Criar conta a receber via formulário modal"""
    try:
        admin_id = get_admin_id()
        
        cliente_nome = request.form.get('cliente_nome')
        cliente_cpf_cnpj = request.form.get('cliente_cpf_cnpj') or None
        obra_id_input = request.form.get('obra_id', type=int) or None
        descricao = request.form.get('descricao')
        valor = Decimal(request.form.get('valor'))
        data_vencimento = datetime.strptime(
            request.form.get('data_vencimento'), 
            '%Y-%m-%d'
        ).date()
        numero_documento = request.form.get('numero_documento') or None
        conta_contabil_codigo = request.form.get('conta_contabil_codigo') or None
        
        # SEGURANÇA: Validar que obra_id pertence ao admin atual
        obra_id = None
        if obra_id_input:
            obra = Obra.query.filter_by(id=obra_id_input, admin_id=admin_id).first()
            if obra:
                obra_id = obra_id_input
            else:
                logger.warning(f"⚠️ Tentativa de vincular obra {obra_id_input} de outro tenant pelo admin {admin_id}")
        
        # Criar conta com obra_id validado
        conta = ContaReceber(
            admin_id=admin_id,
            cliente_nome=cliente_nome,
            cliente_cpf_cnpj=cliente_cpf_cnpj,
            obra_id=obra_id,
            numero_documento=numero_documento,
            descricao=descricao,
            valor_original=valor,
            valor_recebido=Decimal('0'),
            saldo=valor,
            data_emissao=date.today(),
            data_vencimento=data_vencimento,
            status='PENDENTE',
            conta_contabil_codigo=conta_contabil_codigo
        )
        
        db.session.add(conta)
        db.session.commit()
        
        flash(f'Conta a receber criada com sucesso!', 'success')
        return redirect(url_for('financeiro.listar_contas_receber'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar conta a receber: {str(e)}")
        flash('Erro ao criar conta a receber', 'danger')
        return redirect(url_for('financeiro.listar_contas_receber'))


@financeiro_bp.route('/contas-receber/nova', methods=['GET', 'POST'])
@login_required
def nova_conta_receber():
    """Criar nova conta a receber"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            cliente_nome = request.form.get('cliente_nome')
            cliente_cpf_cnpj = request.form.get('cliente_cpf_cnpj') or None
            obra_id = request.form.get('obra_id', type=int) or None
            descricao = request.form.get('descricao')
            valor = Decimal(request.form.get('valor'))
            data_vencimento = datetime.strptime(
                request.form.get('data_vencimento'),
                '%Y-%m-%d'
            ).date()
            numero_documento = request.form.get('numero_documento') or None
            conta_contabil_codigo = request.form.get('conta_contabil_codigo') or None
            
            conta = FinanceiroService.criar_conta_receber(
                admin_id=admin_id,
                cliente_nome=cliente_nome,
                descricao=descricao,
                valor=valor,
                data_vencimento=data_vencimento,
                cliente_cpf_cnpj=cliente_cpf_cnpj,
                obra_id=obra_id,
                numero_documento=numero_documento,
                conta_contabil_codigo=conta_contabil_codigo
            )
            
            flash(f'Conta a receber criada com sucesso! Vencimento: {data_vencimento}', 'success')
            return redirect(url_for('financeiro.listar_contas_receber'))
            
        except Exception as e:
            logger.error(f"Erro ao criar conta a receber: {str(e)}")
            flash('Erro ao criar conta a receber', 'danger')
    
    # GET - exibir formulário
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    contas_contabeis = PlanoContas.query.filter_by(
        admin_id=admin_id,
        tipo_conta='RECEITA',
        aceita_lancamento=True
    ).all()
    
    return render_template(
        'financeiro/nova_conta_receber.html',
        obras=obras,
        contas_contabeis=contas_contabeis
    )


@financeiro_bp.route('/contas-receber/<int:conta_id>/receber', methods=['GET', 'POST'])
@login_required
def receber_conta(conta_id):
    """Registrar recebimento de conta"""
    admin_id = get_admin_id()
    
    conta = ContaReceber.query.filter_by(id=conta_id, admin_id=admin_id).first_or_404()
    
    if request.method == 'POST':
        try:
            valor_recebido = Decimal(request.form.get('valor_recebido'))
            data_recebimento = datetime.strptime(
                request.form.get('data_recebimento'),
                '%Y-%m-%d'
            ).date()
            forma_recebimento = request.form.get('forma_recebimento')
            banco_id = request.form.get('banco_id', type=int) or None
            
            FinanceiroService.baixar_recebimento(
                conta_id=conta_id,
                admin_id=admin_id,
                valor_recebido=valor_recebido,
                data_recebimento=data_recebimento,
                forma_recebimento=forma_recebimento,
                banco_id=banco_id
            )
            
            flash(f'Recebimento de R$ {valor_recebido} registrado com sucesso!', 'success')
            return redirect(url_for('financeiro.listar_contas_receber'))
            
        except Exception as e:
            logger.error(f"Erro ao registrar recebimento: {str(e)}")
            flash('Erro ao registrar recebimento', 'danger')
    
    # GET - exibir formulário
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    return render_template(
        'financeiro/receber_conta.html',
        conta=conta,
        bancos=bancos
    )


# ==================== FLUXO DE CAIXA ====================

@financeiro_bp.route('/fluxo-caixa')
@login_required
def fluxo_caixa():
    """Projeção de fluxo de caixa"""
    admin_id = get_admin_id()
    
    # Período padrão: próximos 30 dias
    data_inicio = date.today()
    data_fim = data_inicio + timedelta(days=30)
    
    # Permitir customização via query params
    if request.args.get('data_inicio'):
        data_inicio = datetime.strptime(request.args.get('data_inicio'), '%Y-%m-%d').date()
    if request.args.get('data_fim'):
        data_fim = datetime.strptime(request.args.get('data_fim'), '%Y-%m-%d').date()
    
    obra_id = request.args.get('obra_id', type=int) or 0
    centro_custo_id = request.args.get('centro_custo_id', type=int) or 0
    tipo_movimento = request.args.get('tipo_movimento', '')
    
    # Criar objeto filtros para o template
    filtros = {
        'data_inicio': data_inicio.strftime('%Y-%m-%d') if data_inicio else '',
        'data_fim': data_fim.strftime('%Y-%m-%d') if data_fim else '',
        'obra_id': obra_id,
        'centro_custo_id': centro_custo_id,
        'tipo_movimento': tipo_movimento
    }
    
    # Buscar obras e centros de custo para os dropdowns
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    
    # Tentar buscar centros de custo se existir a tabela
    centros_custo = []
    try:
        from models import CentroCusto
        centros_custo = CentroCusto.query.filter_by(admin_id=admin_id, ativo=True).all()
    except Exception:
        pass
    
    fluxo = FinanceiroService.calcular_fluxo_caixa(admin_id, data_inicio, data_fim)

    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).order_by(BancoEmpresa.nome_banco).all()

    from gestao_custos_views import CATEGORIAS_GRUPOS as _CAT_GRUPOS, CATEGORIA_LABELS as _CAT_LABELS
    # Converter de (grupo, [KEY, KEY, ...]) para (grupo, [(val, label), ...])
    categorias_grupos = [
        (grupo_nome, [(k, _CAT_LABELS.get(k, (k,))[0]) for k in chaves])
        for grupo_nome, chaves in _CAT_GRUPOS
    ]
    
    return render_template(
        'financeiro/fluxo_caixa.html',
        fluxo=fluxo,
        filtros=filtros,
        obras=obras,
        centros_custo=centros_custo,
        bancos=bancos,
        categorias_grupos=categorias_grupos,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


@financeiro_bp.route('/fluxo-caixa/novo', methods=['POST'])
@login_required
def novo_fluxo_caixa():
    """Cria um lançamento direto no FluxoCaixa (sem GCP)"""
    admin_id = get_admin_id()
    try:
        from gestao_custos_views import CATEGORIA_LABELS as _CAT_LABELS
        TIPOS_VALIDOS = {'ENTRADA', 'SAIDA'}
        CATEGORIAS_VALIDAS = set(_CAT_LABELS.keys())
        tipo_movimento = request.form.get('tipo_movimento', 'SAIDA')
        if tipo_movimento not in TIPOS_VALIDOS:
            tipo_movimento = 'SAIDA'
        data_str = request.form.get('data_movimento', '').strip()
        data_mov = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
        valor = abs(_parse_valor(request.form.get('valor', '0')))
        descricao = request.form.get('descricao', '').strip()[:200]
        categoria = request.form.get('categoria', 'OUTROS')
        if categoria not in CATEGORIAS_VALIDAS:
            categoria = 'OUTROS'
        banco_id = request.form.get('banco_id', type=int) or None
        obra_id = request.form.get('obra_id', type=int) or None

        # Validar que banco e obra pertencem ao tenant
        if banco_id:
            bk = BancoEmpresa.query.filter_by(id=banco_id, admin_id=admin_id).first()
            if not bk:
                banco_id = None
        if obra_id:
            ob = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not ob:
                obra_id = None

        fc = FluxoCaixa(
            admin_id=admin_id,
            tipo_movimento=tipo_movimento,
            data_movimento=data_mov,
            valor=valor,
            descricao=descricao or 'Lançamento manual',
            categoria=categoria,
            banco_id=banco_id,
            obra_id=obra_id,
        )
        db.session.add(fc)
        db.session.commit()
        flash('Lançamento criado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar FluxoCaixa: {e}", exc_info=True)
        flash('Não foi possível criar o lançamento. Tente novamente ou contate o suporte.', 'danger')

    return redirect(url_for('financeiro.fluxo_caixa',
                            data_inicio=request.form.get('_filtro_inicio', ''),
                            data_fim=request.form.get('_filtro_fim', ''),
                            obra_id=request.form.get('_filtro_obra_id', ''),
                            centro_custo_id=request.form.get('_filtro_centro_custo_id', ''),
                            tipo_movimento=request.form.get('_filtro_tipo', '')))


@financeiro_bp.route('/fluxo-caixa/<int:fc_id>/editar', methods=['POST'])
@login_required
def editar_fluxo_caixa(fc_id):
    """Edita inline data, valor e descrição de um lançamento direto — retorna JSON"""
    from flask import jsonify
    admin_id = get_admin_id()
    # Qualquer FluxoCaixa pertencente ao tenant pode ser editado inline
    fc = FluxoCaixa.query.filter(
        FluxoCaixa.id == fc_id,
        FluxoCaixa.admin_id == admin_id,
    ).first_or_404()
    try:
        data_str = request.form.get('data_movimento', '').strip()
        if data_str:
            fc.data_movimento = datetime.strptime(data_str, '%Y-%m-%d').date()
        valor_str = request.form.get('valor', '').strip()
        if valor_str:
            fc.valor = abs(_parse_valor(valor_str))
        desc = request.form.get('descricao', '').strip()
        fc.descricao = desc[:200] if desc else fc.descricao
        db.session.commit()
        return jsonify({
            'ok': True,
            'data': fc.data_movimento.strftime('%d/%m/%Y'),
            'valor': round(fc.valor, 2),
            'descricao': fc.descricao,
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao editar FluxoCaixa {fc_id}: {e}", exc_info=True)
        return jsonify({'ok': False, 'error': 'Não foi possível salvar as alterações.'}), 400


# ==================== BANCOS ====================

@financeiro_bp.route('/bancos')
@login_required
def listar_bancos():
    """Lista bancos da empresa"""
    admin_id = get_admin_id()
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id).all()
    total_saldo = sum(b.saldo_atual for b in bancos if b.ativo)
    
    return render_template('financeiro/bancos.html', bancos=bancos, total_saldo=total_saldo)


@financeiro_bp.route('/bancos/criar', methods=['POST'])
@login_required
def criar_banco():
    """Criar banco via formulário modal"""
    try:
        admin_id = get_admin_id()
        
        nome_banco = request.form.get('nome_banco')
        tipo_conta = request.form.get('tipo_conta')
        agencia = request.form.get('agencia')
        conta = request.form.get('conta')
        saldo_inicial = Decimal(request.form.get('saldo_inicial', '0'))
        ativo = request.form.get('ativo', '1') == '1'
        
        banco = BancoEmpresa(
            admin_id=admin_id,
            nome_banco=nome_banco,
            tipo_conta=tipo_conta,
            agencia=agencia,
            conta=conta,
            saldo_inicial=saldo_inicial,
            saldo_atual=saldo_inicial,
            ativo=ativo
        )
        
        db.session.add(banco)
        db.session.commit()
        
        flash(f'Banco {nome_banco} cadastrado com sucesso!', 'success')
        return redirect(url_for('financeiro.listar_bancos'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar banco: {str(e)}")
        flash('Erro ao cadastrar banco', 'danger')
        return redirect(url_for('financeiro.listar_bancos'))


@financeiro_bp.route('/bancos/novo', methods=['GET', 'POST'])
@login_required
def novo_banco():
    """Criar novo banco"""
    admin_id = get_admin_id()
    
    if request.method == 'POST':
        try:
            nome_banco = request.form.get('nome_banco')
            agencia = request.form.get('agencia')
            conta = request.form.get('conta')
            tipo_conta = request.form.get('tipo_conta')
            saldo_inicial = Decimal(request.form.get('saldo_inicial', '0'))
            
            banco = FinanceiroService.criar_banco(
                admin_id=admin_id,
                nome_banco=nome_banco,
                agencia=agencia,
                conta=conta,
                tipo_conta=tipo_conta,
                saldo_inicial=saldo_inicial
            )
            
            flash(f'Banco {nome_banco} cadastrado com sucesso!', 'success')
            return redirect(url_for('financeiro.listar_bancos'))
            
        except Exception as e:
            logger.error(f"Erro ao criar banco: {str(e)}")
            flash('Erro ao cadastrar banco', 'danger')
    
    return render_template('financeiro/novo_banco.html')


# ==================== PLANO DE CONTAS ====================

@financeiro_bp.route('/plano-contas')
@login_required
def plano_contas():
    """Visualizar plano de contas"""
    admin_id = get_admin_id()
    
    contas = PlanoContas.query.filter_by(admin_id=admin_id).order_by(PlanoContas.codigo).all()
    
    return render_template('financeiro/plano_contas.html', contas=contas)


@financeiro_bp.route('/plano-contas/inicializar', methods=['POST'])
@login_required
def inicializar_plano_contas():
    """Inicializa plano de contas padrão"""
    from financeiro_seeds import criar_plano_contas_padrao
    
    admin_id = get_admin_id()
    
    try:
        contas_criadas = criar_plano_contas_padrao(admin_id)
        
        if contas_criadas > 0:
            flash(f'Plano de contas inicializado com {contas_criadas} contas!', 'success')
        else:
            flash('Plano de contas já existe para este usuário', 'warning')
            
    except Exception as e:
        logger.error(f"Erro ao inicializar plano de contas: {str(e)}")
        flash('Erro ao inicializar plano de contas', 'danger')
    
    return redirect(url_for('financeiro.plano_contas'))


# ==================== API JSON ====================

@financeiro_bp.route('/api/kpis')
@login_required
def api_kpis():
    """Retorna KPIs em JSON"""
    admin_id = get_admin_id()
    kpis = FinanceiroService.obter_kpis_financeiros(admin_id)
    return jsonify(kpis)
