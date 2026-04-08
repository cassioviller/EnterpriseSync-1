"""
gestao_custos_views.py
Blueprint V2: Gestão de Custos — hierarquia Pai/Filho + fluxo de aprovação.
Rota base: /gestao-custos
"""

import logging
from datetime import datetime, date
from decimal import Decimal

from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from models import (GestaoCustoPai, GestaoCustoFilho,
                    FluxoCaixa, Obra, TipoUsuario, ContaPagar, Fornecedor, BancoEmpresa)
from utils.tenant import is_v2_active

logger = logging.getLogger(__name__)

gestao_custos_bp = Blueprint('gestao_custos', __name__,
                              url_prefix='/gestao-custos')

CATEGORIA_LABELS = {
    # ── Custo Direto de Obra ────────────────────────────────────────
    'MATERIAL':           ('Material de Obra',         'fas fa-boxes',               'warning'),
    'MAO_OBRA_DIRETA':    ('Mão de Obra Direta',       'fas fa-hard-hat',            'primary'),
    'EQUIPAMENTO':        ('Equipamento / Frota',      'fas fa-truck',               'dark'),
    'SUBEMPREITADA':      ('Subempreitada',            'fas fa-hammer',              'info'),
    # ── Custo Indireto de Obra ──────────────────────────────────────
    'ALIMENTACAO':        ('Alimentação',              'fas fa-utensils',            'success'),
    'TRANSPORTE':         ('Transporte',               'fas fa-route',               'info'),
    'CANTEIRO':           ('Canteiro / Instalações',   'fas fa-hard-hat',            'secondary'),
    'TAXAS_LICENCAS':     ('Taxas e Licenças',         'fas fa-file-signature',      'danger'),
    # ── Despesa Administrativa ──────────────────────────────────────
    'SALARIO_ADMIN':      ('Salário Administrativo',   'fas fa-user-tie',            'primary'),
    'ALUGUEL_UTILITIES':  ('Aluguel / Utilities',      'fas fa-building',            'purple'),
    'TRIBUTOS':           ('Tributos / Impostos',      'fas fa-landmark',            'danger'),
    'DESPESA_FINANCEIRA': ('Despesa Financeira',       'fas fa-percentage',          'dark'),
    'OUTROS':             ('Outros',                   'fas fa-receipt',             'secondary'),
    # ── Categorias legadas (retrocompatibilidade — lidas mas não oferecidas no dropdown) ──
    'SALARIO':            ('Pagamento Salário (legado)','fas fa-user-tie',           'primary'),
    'VEICULO':            ('Despesa de Frota (legado)', 'fas fa-truck',              'dark'),
    'COMPRA':             ('Compra de Material (legado)','fas fa-shopping-cart',     'warning'),
    'REEMBOLSO':          ('Reembolso a Pagar (legado)','fas fa-undo',              'danger'),
    'DESPESA_GERAL':      ('Despesa Geral (legado)',   'fas fa-file-invoice-dollar', 'secondary'),
}

# Agrupamento para exibição no dropdown de criação
CATEGORIAS_GRUPOS = [
    ('Custo Direto de Obra',    ['MATERIAL', 'MAO_OBRA_DIRETA', 'EQUIPAMENTO', 'SUBEMPREITADA']),
    ('Custo Indireto de Obra',  ['ALIMENTACAO', 'TRANSPORTE', 'CANTEIRO', 'TAXAS_LICENCAS']),
    ('Despesa Administrativa',  ['SALARIO_ADMIN', 'ALUGUEL_UTILITIES', 'TRIBUTOS', 'DESPESA_FINANCEIRA', 'OUTROS']),
]

# Mapeamento reverso: nova → lista de categorias legadas que representam o mesmo conceito
_LEGADO_PARA_NOVA = {
    'MATERIAL':       ['COMPRA'],
    'EQUIPAMENTO':    ['VEICULO'],
    'MAO_OBRA_DIRETA':['SALARIO'],
    'OUTROS':         ['REEMBOLSO', 'DESPESA_GERAL'],
}

def _categorias_equivalentes(categoria: str) -> list:
    """Retorna a categoria informada + suas equivalências legadas para uso em filtros."""
    equivalentes = [categoria]
    equivalentes.extend(_LEGADO_PARA_NOVA.get(categoria, []))
    return equivalentes

STATUS_BADGES = {
    'PENDENTE':   'secondary',
    'SOLICITADO': 'warning',
    'AUTORIZADO': 'success',
    'PARCIAL':    'info',
    'PAGO':       'primary',
    'RECUSADO':   'danger',
}


def _check_v2():
    """Retorna (admin_id, None) ou (None, redirect_response) se não V2."""
    if not is_v2_active():
        flash('Módulo exclusivo da versão V2.', 'warning')
        return None, redirect(url_for('main.index'))
    admin_id = (current_user.id
                if current_user.tipo_usuario == TipoUsuario.ADMIN
                else current_user.admin_id)
    return admin_id, None


# ───────────────────────────────────────────────────────────────
# DASHBOARD / LISTAGEM
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/')
@login_required
def index():
    admin_id, err = _check_v2()
    if err:
        return err

    # Filtros
    filtro_status = request.args.get('status', '')
    filtro_categoria = request.args.get('categoria', '')
    filtro_busca = request.args.get('busca', '').strip()

    q = GestaoCustoPai.query.filter_by(admin_id=admin_id)
    if filtro_status:
        q = q.filter_by(status=filtro_status)
    if filtro_categoria:
        equivalentes = _categorias_equivalentes(filtro_categoria)
        q = q.filter(GestaoCustoPai.tipo_categoria.in_(equivalentes))
    if filtro_busca:
        q = q.filter(GestaoCustoPai.entidade_nome.ilike(f'%{filtro_busca}%'))

    registros = q.order_by(GestaoCustoPai.data_criacao.desc()).all()

    # Totais por status
    totais = (
        db.session.query(
            GestaoCustoPai.status,
            func.count(GestaoCustoPai.id),
            func.sum(GestaoCustoPai.valor_total),
        )
        .filter_by(admin_id=admin_id)
        .group_by(GestaoCustoPai.status)
        .all()
    )
    resumo = {row[0]: {'qtd': row[1], 'total': float(row[2] or 0)} for row in totais}

    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    bancos = BancoEmpresa.query.filter_by(admin_id=admin_id, ativo=True).order_by(BancoEmpresa.nome_banco).all()

    return render_template(
        'custos/gestao.html',
        registros=registros,
        resumo=resumo,
        categoria_labels=CATEGORIA_LABELS,
        categorias_grupos=CATEGORIAS_GRUPOS,
        status_badges=STATUS_BADGES,
        filtro_status=filtro_status,
        filtro_categoria=filtro_categoria,
        filtro_busca=filtro_busca,
        obras=obras,
        bancos=bancos,
    )


# ───────────────────────────────────────────────────────────────
# LANÇAMENTO MANUAL
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    admin_id, err = _check_v2()
    if err:
        return err

    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by(Fornecedor.nome).all()
    today = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        try:
            tipo_categoria = request.form.get('tipo_categoria', 'OUTROS')
            entidade_nome = request.form.get('entidade_nome', '').strip()
            descricao = request.form.get('descricao', '').strip()
            valor = Decimal(request.form.get('valor', '0').replace(',', '.'))
            data_ref_str = request.form.get('data_referencia')
            data_ref = datetime.strptime(data_ref_str, '%Y-%m-%d').date() if data_ref_str else date.today()
            obra_id = request.form.get('obra_id', type=int)

            # Campos opcionais para todos os tipos
            data_venc_str = request.form.get('data_vencimento', '').strip()
            data_venc = datetime.strptime(data_venc_str, '%Y-%m-%d').date() if data_venc_str else None
            numero_doc = request.form.get('numero_documento', '').strip() or None
            fornecedor_id = request.form.get('fornecedor_id', type=int)
            forma_pagamento = request.form.get('forma_pagamento', '').strip() or None
            data_emissao_str = request.form.get('data_emissao', '').strip()
            data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d').date() if data_emissao_str else None
            numero_parcela = request.form.get('numero_parcela', type=int) or 1
            total_parcelas = request.form.get('total_parcelas', type=int) or 1
            conta_contabil = request.form.get('conta_contabil_codigo', '').strip() or None

            if not entidade_nome or valor <= 0:
                flash('Entidade e valor são obrigatórios.', 'warning')
                return render_template('custos/gestao.html',
                                       modo='novo', obras=obras,
                                       fornecedores=fornecedores,
                                       categoria_labels=CATEGORIA_LABELS,
                                       categorias_grupos=CATEGORIAS_GRUPOS,
                                       status_badges=STATUS_BADGES,
                                       registros=[], resumo={})

            # Sincronizar entidade_nome com fornecedor se selecionado
            if fornecedor_id:
                forn = Fornecedor.query.get(fornecedor_id)
                if forn and not entidade_nome:
                    entidade_nome = forn.nome

            pai = GestaoCustoPai(
                admin_id=admin_id,
                tipo_categoria=tipo_categoria,
                entidade_nome=entidade_nome,
                entidade_id=None,
                valor_total=valor,
                valor_pago=Decimal('0'),
                saldo=valor,
                status='PENDENTE',
                data_vencimento=data_venc,
                numero_documento=numero_doc,
                fornecedor_id=fornecedor_id,
                forma_pagamento=forma_pagamento,
                data_emissao=data_emissao,
                numero_parcela=numero_parcela,
                total_parcelas=total_parcelas,
                conta_contabil_codigo=conta_contabil,
            )
            db.session.add(pai)
            db.session.flush()

            filho = GestaoCustoFilho(
                pai_id=pai.id,
                admin_id=admin_id,
                data_referencia=data_ref,
                descricao=descricao or entidade_nome,
                valor=valor,
                obra_id=obra_id,
                origem_tabela='manual',
            )
            db.session.add(filho)
            db.session.commit()
            flash(f'Custo "{entidade_nome}" lançado com sucesso.', 'success')
            return redirect(url_for('gestao_custos.index'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao criar custo manual: {e}")
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template(
        'custos/gestao.html',
        modo='novo',
        obras=obras,
        fornecedores=fornecedores,
        today=today,
        categoria_labels=CATEGORIA_LABELS,
        categorias_grupos=CATEGORIAS_GRUPOS,
        status_badges=STATUS_BADGES,
        registros=[],
        resumo={},
    )


# ───────────────────────────────────────────────────────────────
# DETALHES / FILHOS (AJAX)
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/filhos')
@login_required
def filhos(pai_id):
    admin_id, err = _check_v2()
    if err:
        return jsonify({'status': 'error', 'message': 'V2 only'}), 403

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()
    itens = GestaoCustoFilho.query.filter_by(pai_id=pai.id).order_by(
        GestaoCustoFilho.data_referencia.asc()).all()

    return jsonify({
        'status': 'ok',
        'itens': [
            {
                'id': f.id,
                'data': f.data_referencia.strftime('%d/%m/%Y'),
                'descricao': f.descricao,
                'valor': float(f.valor),
                'obra': f.obra.nome if f.obra else '—',
                'origem': f.origem_tabela or '—',
            }
            for f in itens
        ],
    })


# ───────────────────────────────────────────────────────────────
# SOLICITAR PAGAMENTO   PENDENTE → SOLICITADO
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/solicitar', methods=['POST'])
@login_required
def solicitar(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()

    if pai.status not in ('PENDENTE', 'PARCIAL'):
        flash('Apenas registros PENDENTES ou PARCIAIS podem ser solicitados.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    try:
        valor_sol_str = request.form.get('valor_solicitado', '').replace(',', '.')
        valor_sol = Decimal(valor_sol_str) if valor_sol_str else pai.valor_total
        pai.valor_solicitado = valor_sol
        pai.status = 'SOLICITADO'
        db.session.commit()
        flash(f'Pagamento de R$ {valor_sol:,.2f} solicitado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] solicitar pagamento: {e}")
        flash(f'Erro: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


# ───────────────────────────────────────────────────────────────
# APROVAR / RECUSAR    SOLICITADO → PAGO/PARCIAL ou PENDENTE
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/autorizar', methods=['POST'])
@login_required
def autorizar(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()

    if pai.status != 'SOLICITADO':
        flash('Apenas registros SOLICITADOS podem ser aprovados.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    acao = request.form.get('acao', 'autorizar')

    if acao == 'recusar':
        pai.status = 'PENDENTE'
        pai.valor_solicitado = None
        db.session.commit()
        flash('Não aprovado. Registro voltou para Não Solicitado.', 'info')
        return redirect(url_for('gestao_custos.index'))

    # ── Aprovação: executa o pagamento diretamente ──
    try:
        data_pgto_str = request.form.get('data_pagamento', '')
        data_pgto = (datetime.strptime(data_pgto_str, '%Y-%m-%d').date()
                     if data_pgto_str else date.today())

        banco_id_str = request.form.get('banco_id', '').strip()
        conta_bancaria_manual = request.form.get('conta_bancaria_manual', '').strip()
        if banco_id_str:
            banco = BancoEmpresa.query.filter_by(id=int(banco_id_str), admin_id=admin_id).first()
            conta = f'{banco.nome_banco} — Ag {banco.agencia} / C {banco.conta}' if banco else conta_bancaria_manual
        else:
            conta = conta_bancaria_manual

        valor_autorizado = Decimal(str(pai.valor_solicitado or pai.valor_total))
        valor_pago_anterior = Decimal(str(pai.valor_pago or 0))
        novo_valor_pago = valor_pago_anterior + valor_autorizado
        novo_saldo = Decimal(str(pai.valor_total)) - novo_valor_pago

        if novo_saldo <= Decimal('0.01'):
            novo_status = 'PAGO'
            novo_saldo = Decimal('0')
        else:
            novo_status = 'PARCIAL'

        cat_mapa = {
            'MATERIAL':           'custo_obra',
            'MAO_OBRA_DIRETA':    'salario',
            'EQUIPAMENTO':        'custo_obra',
            'SUBEMPREITADA':      'custo_obra',
            'ALIMENTACAO':        'alimentacao',
            'TRANSPORTE':         'custo_obra',
            'CANTEIRO':           'custo_obra',
            'TAXAS_LICENCAS':     'custo_obra',
            'SALARIO_ADMIN':      'salario',
            'ALUGUEL_UTILITIES':  'custo_obra',
            'TRIBUTOS':           'custo_obra',
            'DESPESA_FINANCEIRA': 'custo_obra',
            'OUTROS':             'custo_obra',
            'SALARIO':            'salario',
            'VEICULO':            'custo_obra',
            'COMPRA':             'custo_obra',
            'REEMBOLSO':          'custo_obra',
            'DESPESA_GERAL':      'custo_obra',
        }
        cat_fc = cat_mapa.get(pai.tipo_categoria, 'custo_obra')
        label = CATEGORIA_LABELS.get(pai.tipo_categoria, ('Custo',))[0]

        fc = FluxoCaixa(
            admin_id=admin_id,
            data_movimento=data_pgto,
            tipo_movimento='SAIDA',
            categoria=cat_fc,
            valor=float(valor_autorizado),
            descricao=f'{label} — {pai.entidade_nome}',
            referencia_id=pai.id,
            referencia_tabela='gestao_custo_pai',
            observacoes=conta or None,
        )
        db.session.add(fc)
        db.session.flush()

        pai.status = novo_status
        pai.valor_pago = novo_valor_pago
        pai.saldo = novo_saldo
        pai.data_pagamento = data_pgto
        pai.conta_bancaria = conta
        if novo_status == 'PAGO':
            pai.fluxo_caixa_id = fc.id
        db.session.commit()

        # Lançamento contábil (não crítico)
        try:
            from contabilidade_utils import gerar_lancamento_contabil_automatico
            gerar_lancamento_contabil_automatico(
                admin_id=admin_id,
                tipo_operacao='DESPESA_GERAL',
                valor=float(valor_autorizado),
                data=data_pgto,
                descricao=f'{label} — {pai.entidade_nome}',
            )
        except Exception as e_cont:
            logger.warning(f"[WARN] Lançamento contábil falhou (não crítico): {e_cont}")

        if novo_status == 'PAGO':
            flash(f'Aprovado e pago: R$ {valor_autorizado:,.2f}. Saldo zerado.', 'success')
        else:
            flash(
                f'Aprovado e pago: R$ {valor_autorizado:,.2f}. '
                f'Saldo restante: R$ {novo_saldo:,.2f}',
                'info'
            )
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] aprovar+pagar gestao_custo: {e}", exc_info=True)
        flash(f'Erro ao aprovar: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


# ───────────────────────────────────────────────────────────────
# EFETIVAR PAGAMENTO    AUTORIZADO → PAGO
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/pagar', methods=['POST'])
@login_required
def pagar(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()

    if pai.status != 'AUTORIZADO':
        flash('Apenas registros AUTORIZADOS podem ser efetivados como pagos.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    try:
        data_pgto_str = request.form.get('data_pagamento', '')
        data_pgto = (datetime.strptime(data_pgto_str, '%Y-%m-%d').date()
                     if data_pgto_str else date.today())
        conta = request.form.get('conta_bancaria', '').strip()

        # Valor autorizado (solicitado ou total)
        valor_autorizado = Decimal(str(pai.valor_solicitado or pai.valor_total))
        valor_pago_str = request.form.get('valor_pago', '').replace(',', '.')
        valor_pago_agora = Decimal(valor_pago_str) if valor_pago_str else valor_autorizado

        # Acumular pagamentos parciais
        valor_pago_anterior = Decimal(str(pai.valor_pago or 0))
        novo_valor_pago = valor_pago_anterior + valor_pago_agora
        novo_saldo = Decimal(str(pai.valor_total)) - novo_valor_pago

        # Determinar status após pagamento
        if novo_saldo <= Decimal('0.01'):
            novo_status = 'PAGO'
            novo_saldo = Decimal('0')
        else:
            novo_status = 'PARCIAL'

        # Mapear categoria → categoria FluxoCaixa
        cat_mapa = {
            'MATERIAL':           'custo_obra',
            'MAO_OBRA_DIRETA':    'salario',
            'EQUIPAMENTO':        'custo_obra',
            'SUBEMPREITADA':      'custo_obra',
            'ALIMENTACAO':        'alimentacao',
            'TRANSPORTE':         'custo_obra',
            'CANTEIRO':           'custo_obra',
            'TAXAS_LICENCAS':     'custo_obra',
            'SALARIO_ADMIN':      'salario',
            'ALUGUEL_UTILITIES':  'custo_obra',
            'TRIBUTOS':           'custo_obra',
            'DESPESA_FINANCEIRA': 'custo_obra',
            'OUTROS':             'custo_obra',
            'SALARIO':            'salario',
            'VEICULO':            'custo_obra',
            'COMPRA':             'custo_obra',
            'REEMBOLSO':          'custo_obra',
            'DESPESA_GERAL':      'custo_obra',
        }
        cat_fc = cat_mapa.get(pai.tipo_categoria, 'custo_obra')
        label = CATEGORIA_LABELS.get(pai.tipo_categoria, ('Custo',))[0]

        # Criar FluxoCaixa para o valor pago agora
        fc = FluxoCaixa(
            admin_id=admin_id,
            data_movimento=data_pgto,
            tipo_movimento='SAIDA',
            categoria=cat_fc,
            valor=float(valor_pago_agora),
            descricao=f'{label} — {pai.entidade_nome}',
            referencia_id=pai.id,
            referencia_tabela='gestao_custo_pai',
            observacoes=conta or None,
        )
        db.session.add(fc)
        db.session.flush()

        pai.status = novo_status
        pai.valor_pago = novo_valor_pago
        pai.saldo = novo_saldo
        # Registrar data do último pagamento para PAGO e PARCIAL (permite rastreio no FluxoCaixa)
        pai.data_pagamento = data_pgto
        if novo_status == 'PAGO':
            pai.fluxo_caixa_id = fc.id
        pai.conta_bancaria = conta
        db.session.commit()

        # Lançamento contábil (opcional, V2)
        try:
            from contabilidade_utils import gerar_lancamento_contabil_automatico
            gerar_lancamento_contabil_automatico(
                admin_id=admin_id,
                tipo_operacao='DESPESA_GERAL',
                valor=float(valor_pago_agora),
                data=data_pgto,
                descricao=f'{label} — {pai.entidade_nome}',
            )
        except Exception as e_cont:
            logger.warning(f"[WARN] Lançamento contábil falhou (não crítico): {e_cont}")

        if novo_status == 'PAGO':
            flash(f'Pagamento total de R$ {valor_pago_agora:,.2f} efetivado. Saldo zerado.', 'success')
        else:
            flash(
                f'Pagamento parcial de R$ {valor_pago_agora:,.2f} registrado. '
                f'Saldo restante: R$ {novo_saldo:,.2f}',
                'info'
            )
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] efetivar pagamento: {e}", exc_info=True)
        flash(f'Erro ao pagar: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


# ───────────────────────────────────────────────────────────────
# EXCLUIR PAI (apenas PENDENTE)
# ───────────────────────────────────────────────────────────────

@gestao_custos_bp.route('/<int:pai_id>/excluir', methods=['POST'])
@login_required
def excluir(pai_id):
    admin_id, err = _check_v2()
    if err:
        return err

    pai = GestaoCustoPai.query.filter_by(id=pai_id, admin_id=admin_id).first_or_404()
    if pai.status not in ('PENDENTE', 'RECUSADO'):
        flash('Apenas registros PENDENTES ou RECUSADOS podem ser excluídos.', 'warning')
        return redirect(url_for('gestao_custos.index'))

    try:
        # CRUD Integrado: excluir registros de origem vinculados nos filhos
        _excluir_origens_vinculadas(pai, admin_id)

        db.session.delete(pai)
        db.session.commit()
        flash('Registro excluído com sucesso (lançamentos de origem também removidos).', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))


def _excluir_origens_vinculadas(pai, admin_id):
    """Remove os registros de origem (transporte, alimentação, etc.) referenciados pelos filhos."""
    _TABELAS_SUPORTADAS = {
        'lancamento_transporte': ('models', 'LancamentoTransporte'),
        'lancamento_alimentacao': ('models', 'AlimentacaoLancamento'),
        'reembolso_funcionario': ('models', 'ReembolsoFuncionario'),
    }

    from models import GestaoCustoFilho
    filhos = GestaoCustoFilho.query.filter_by(pai_id=pai.id).all()

    for filho in filhos:
        tabela = filho.origem_tabela
        origem_id = filho.origem_id
        if not tabela or not origem_id:
            continue
        if tabela not in _TABELAS_SUPORTADAS:
            continue
        try:
            mod_name, class_name = _TABELAS_SUPORTADAS[tabela]
            import importlib
            mod = importlib.import_module(mod_name)
            ModelClass = getattr(mod, class_name)
            registro = ModelClass.query.filter_by(id=origem_id, admin_id=admin_id).first()
            if registro:
                db.session.delete(registro)
                logger.info(f"[OK] CRUD Integrado: {tabela} id={origem_id} excluído junto com GestaoCusto pai={pai.id}")
        except Exception as e:
            logger.warning(f"[WARN] CRUD Integrado: erro ao excluir {tabela} id={origem_id}: {e}")


# ─────────────────────────────────────────────
# MIGRAÇÃO: ContaPagar → GestaoCustoPai
# ─────────────────────────────────────────────
@gestao_custos_bp.route('/migrar-contas-pagar', methods=['POST'])
@login_required
def migrar_contas_pagar():
    """
    Migra registros ContaPagar PENDENTE/PARCIAL para GestaoCustoPai.
    Registros já PAGO são mantidos em ContaPagar como histórico.
    Idempotente: não duplica registros já migrados.
    """
    admin_id, err = _check_v2()
    if err:
        return err

    migrados = 0
    ignorados = 0
    erros = 0

    try:
        contas = ContaPagar.query.filter(
            ContaPagar.admin_id == admin_id,
            ContaPagar.status.in_(['PENDENTE', 'PARCIAL'])
        ).all()

        for conta in contas:
            # Verificar se já foi migrado pela referência de origem (idempotente)
            existente = GestaoCustoFilho.query.filter_by(
                admin_id=admin_id,
                origem_tabela='conta_pagar',
                origem_id=conta.id,
            ).first()
            if existente:
                ignorados += 1
                continue

            try:
                from models import Fornecedor as _Forn
                forn_nome = conta.descricao or f"Conta #{conta.id}"
                forn_id = conta.fornecedor_id
                if forn_id:
                    _forn = _Forn.query.get(forn_id)
                    if _forn:
                        forn_nome = _forn.razao_social or _forn.nome or forn_nome

                # Mapear categorias por origem_tipo ou por heurística de descrição
                _ORIGEM_CAT_MAP = {
                    'COMPRA': 'MATERIAL',
                    'FOLHA':  'MAO_OBRA_DIRETA',
                    'RDO':    'MAO_OBRA_DIRETA',
                }
                origem_tipo = getattr(conta, 'origem_tipo', None) or ''
                tipo_cat = _ORIGEM_CAT_MAP.get(origem_tipo.upper(), 'OUTROS')
                # Fallback por descrição
                if tipo_cat == 'OUTROS' and conta.descricao:
                    desc_lower = conta.descricao.lower()
                    if any(k in desc_lower for k in ('material', 'compra', 'nf ', 'fornec')):
                        tipo_cat = 'MATERIAL'
                    elif any(k in desc_lower for k in ('salário', 'salario', 'folha', 'funcionário')):
                        tipo_cat = 'MAO_OBRA_DIRETA'

                # Status mapping: PENDENTE → PENDENTE, PARCIAL → SOLICITADO
                status_gcp = 'PENDENTE' if conta.status == 'PENDENTE' else 'SOLICITADO'
                valor_original = float(conta.valor_original or 0)
                valor_pago_cp = float(conta.valor_pago or 0)
                saldo_cp = float(conta.saldo or (valor_original - valor_pago_cp))

                gcp = GestaoCustoPai(
                    admin_id=admin_id,
                    tipo_categoria=tipo_cat,
                    entidade_nome=forn_nome,
                    entidade_id=forn_id,
                    fornecedor_id=forn_id,
                    valor_total=valor_original,
                    valor_pago=valor_pago_cp,
                    saldo=saldo_cp,
                    status=status_gcp,
                    data_emissao=conta.data_emissao,
                    data_vencimento=conta.data_vencimento,
                    numero_documento=conta.numero_documento or str(conta.id),
                    observacoes=f"[Migrado de ContaPagar #{conta.id}] {conta.descricao or ''}",
                )
                db.session.add(gcp)
                db.session.flush()

                gcf = GestaoCustoFilho(
                    pai_id=gcp.id,
                    admin_id=admin_id,
                    data_referencia=conta.data_vencimento or date.today(),
                    descricao=conta.descricao or f"Conta a pagar #{conta.id}",
                    valor=saldo_cp,
                    obra_id=conta.obra_id if hasattr(conta, 'obra_id') else None,
                    origem_tabela='conta_pagar',
                    origem_id=conta.id,
                )
                db.session.add(gcf)
                migrados += 1
            except Exception as _e:
                logger.error(f"Erro ao migrar ContaPagar #{conta.id}: {_e}")
                erros += 1

        db.session.commit()
        flash(
            f'Migração concluída: {migrados} registro(s) migrado(s), '
            f'{ignorados} já existia(m), {erros} erro(s).',
            'success' if erros == 0 else 'warning'
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro na migração ContaPagar→GestaoCusto: {e}")
        flash(f'Erro durante migração: {e}', 'danger')

    return redirect(url_for('gestao_custos.index'))
