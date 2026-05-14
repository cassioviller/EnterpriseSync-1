"""
Blueprint Custos do Escritório — Task #6
Controle de despesas internas do escritório (aluguel, água, luz, etc.)
Lança automaticamente em ContaPagar; pagamento é feito de lá.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime
from decimal import Decimal
from calendar import monthrange
from app import db
from models import CategoriaEscritorio, DespesaEscritorio, DespesaEscritorioOcorrencia, ContaPagar
from multitenant_helper import get_admin_id
import logging

logger = logging.getLogger(__name__)

custos_escritorio_bp = Blueprint('custos_escritorio', __name__, url_prefix='/custos-escritorio')


# ─── helpers ──────────────────────────────────────────────────────────────────

def _criar_conta_pagar(admin_id, descricao, valor, data_vencimento):
    """Cria um registro ContaPagar (PENDENTE) e retorna o objeto persistido."""
    cp = ContaPagar(
        admin_id=admin_id,
        descricao=descricao,
        valor_original=valor,
        valor_pago=Decimal('0'),
        saldo=valor,
        data_emissao=date.today(),
        data_vencimento=data_vencimento,
        status='PENDENTE',
        origem_tipo='CUSTO_ESCRITORIO',
    )
    db.session.add(cp)
    db.session.flush()  # gera cp.id antes do commit
    return cp


# ─── CATEGORIAS ───────────────────────────────────────────────────────────────

@custos_escritorio_bp.route('/categorias')
@login_required
def categorias():
    admin_id = get_admin_id()
    cats = CategoriaEscritorio.query.filter_by(admin_id=admin_id).order_by(
        CategoriaEscritorio.nome
    ).all()
    return render_template('custos_escritorio/categorias.html', categorias=cats)


@custos_escritorio_bp.route('/categorias/nova', methods=['GET', 'POST'])
@login_required
def nova_categoria():
    admin_id = get_admin_id()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        cor = request.form.get('cor', '#6c757d').strip()
        if not nome:
            flash('O nome da categoria é obrigatório.', 'warning')
            return render_template('custos_escritorio/categoria_form.html', categoria=None)
        cat = CategoriaEscritorio(nome=nome, cor=cor, ativo=True, admin_id=admin_id)
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{nome}" criada com sucesso!', 'success')
        return redirect(url_for('custos_escritorio.categorias'))
    return render_template('custos_escritorio/categoria_form.html', categoria=None)


@custos_escritorio_bp.route('/categorias/<int:cat_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_categoria(cat_id):
    admin_id = get_admin_id()
    cat = CategoriaEscritorio.query.filter_by(id=cat_id, admin_id=admin_id).first_or_404()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        cor = request.form.get('cor', cat.cor).strip()
        if not nome:
            flash('O nome da categoria é obrigatório.', 'warning')
            return render_template('custos_escritorio/categoria_form.html', categoria=cat)
        cat.nome = nome
        cat.cor = cor
        db.session.commit()
        flash(f'Categoria "{nome}" atualizada!', 'success')
        return redirect(url_for('custos_escritorio.categorias'))
    return render_template('custos_escritorio/categoria_form.html', categoria=cat)


@custos_escritorio_bp.route('/categorias/<int:cat_id>/toggle', methods=['POST'])
@login_required
def toggle_categoria(cat_id):
    admin_id = get_admin_id()
    cat = CategoriaEscritorio.query.filter_by(id=cat_id, admin_id=admin_id).first_or_404()
    cat.ativo = not cat.ativo
    db.session.commit()
    estado = 'ativada' if cat.ativo else 'desativada'
    flash(f'Categoria "{cat.nome}" {estado}.', 'info')
    return redirect(url_for('custos_escritorio.categorias'))


# ─── DESPESAS ─────────────────────────────────────────────────────────────────

@custos_escritorio_bp.route('/despesas')
@login_required
def despesas():
    admin_id = get_admin_id()
    desps = DespesaEscritorio.query.filter_by(admin_id=admin_id).order_by(
        DespesaEscritorio.nome
    ).all()
    return render_template('custos_escritorio/despesas.html', despesas=desps)


@custos_escritorio_bp.route('/despesas/nova', methods=['GET', 'POST'])
@login_required
def nova_despesa():
    admin_id = get_admin_id()
    categorias = CategoriaEscritorio.query.filter_by(admin_id=admin_id, ativo=True).order_by(
        CategoriaEscritorio.nome
    ).all()
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', '').strip()
            categoria_id = int(request.form.get('categoria_id'))
            valor = Decimal(request.form.get('valor', '0').replace(',', '.'))
            dia_vencimento = int(request.form.get('dia_vencimento', 10))
            recorrente = request.form.get('recorrente') == '1'
            if not nome or valor <= 0 or not (1 <= dia_vencimento <= 28):
                flash('Preencha todos os campos corretamente (dia de vencimento entre 1 e 28).', 'warning')
                return render_template('custos_escritorio/despesa_form.html',
                                       despesa=None, categorias=categorias)
            # Validate categoria_id belongs to this tenant
            cat = CategoriaEscritorio.query.filter_by(id=categoria_id, admin_id=admin_id).first()
            if not cat:
                flash('Categoria inválida ou não pertence a este tenant.', 'danger')
                return render_template('custos_escritorio/despesa_form.html',
                                       despesa=None, categorias=categorias)
            desp = DespesaEscritorio(
                nome=nome, categoria_id=cat.id, valor=valor,
                dia_vencimento=dia_vencimento, recorrente=recorrente,
                ativo=True, admin_id=admin_id
            )
            db.session.add(desp)
            db.session.commit()
            flash(f'Despesa "{nome}" criada com sucesso!', 'success')
            return redirect(url_for('custos_escritorio.despesas'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar despesa: {e}')
            flash('Erro ao criar despesa. Verifique os dados e tente novamente.', 'danger')
    return render_template('custos_escritorio/despesa_form.html', despesa=None, categorias=categorias)


@custos_escritorio_bp.route('/despesas/<int:desp_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_despesa(desp_id):
    admin_id = get_admin_id()
    desp = DespesaEscritorio.query.filter_by(id=desp_id, admin_id=admin_id).first_or_404()
    categorias = CategoriaEscritorio.query.filter_by(admin_id=admin_id, ativo=True).order_by(
        CategoriaEscritorio.nome
    ).all()
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', '').strip()
            categoria_id = int(request.form.get('categoria_id'))
            valor = Decimal(request.form.get('valor', '0').replace(',', '.'))
            dia_vencimento = int(request.form.get('dia_vencimento', 10))
            recorrente = request.form.get('recorrente') == '1'
            if not nome or valor <= 0 or not (1 <= dia_vencimento <= 28):
                flash('Preencha todos os campos corretamente.', 'warning')
                return render_template('custos_escritorio/despesa_form.html',
                                       despesa=desp, categorias=categorias)
            # Validate categoria_id belongs to this tenant
            cat = CategoriaEscritorio.query.filter_by(id=categoria_id, admin_id=admin_id).first()
            if not cat:
                flash('Categoria inválida ou não pertence a este tenant.', 'danger')
                return render_template('custos_escritorio/despesa_form.html',
                                       despesa=desp, categorias=categorias)
            desp.nome = nome
            desp.categoria_id = cat.id
            desp.valor = valor
            desp.dia_vencimento = dia_vencimento
            desp.recorrente = recorrente
            db.session.commit()
            flash(f'Despesa "{nome}" atualizada!', 'success')
            return redirect(url_for('custos_escritorio.despesas'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao editar despesa: {e}')
            flash('Erro ao salvar alterações.', 'danger')
    return render_template('custos_escritorio/despesa_form.html', despesa=desp, categorias=categorias)


@custos_escritorio_bp.route('/despesas/<int:desp_id>/toggle', methods=['POST'])
@login_required
def toggle_despesa(desp_id):
    admin_id = get_admin_id()
    desp = DespesaEscritorio.query.filter_by(id=desp_id, admin_id=admin_id).first_or_404()
    desp.ativo = not desp.ativo
    db.session.commit()
    estado = 'ativada' if desp.ativo else 'desativada'
    flash(f'Despesa "{desp.nome}" {estado}.', 'info')
    return redirect(url_for('custos_escritorio.despesas'))


# ─── OCORRÊNCIA AVULSA ────────────────────────────────────────────────────────

@custos_escritorio_bp.route('/despesas/<int:desp_id>/criar-ocorrencia', methods=['POST'])
@login_required
def criar_ocorrencia_avulsa(desp_id):
    admin_id = get_admin_id()
    desp = DespesaEscritorio.query.filter_by(id=desp_id, admin_id=admin_id).first_or_404()
    if desp.recorrente:
        flash('Ocorrências avulsas só podem ser criadas para despesas do tipo Avulsa (não recorrentes).', 'warning')
        mes = request.form.get('mes_painel', date.today().month)
        ano = request.form.get('ano_painel', date.today().year)
        return redirect(url_for('custos_escritorio.painel_mensal', mes=mes, ano=ano))
    try:
        data_str = request.form.get('data_vencimento')
        valor_raw = request.form.get('valor', str(desp.valor)).replace(',', '.')
        data_venc = datetime.strptime(data_str, '%Y-%m-%d').date()
        valor = Decimal(valor_raw)
        ano, mes = data_venc.year, data_venc.month

        # Verifica unicidade
        existe = DespesaEscritorioOcorrencia.query.filter_by(
            despesa_id=desp.id, competencia_ano=ano, competencia_mes=mes
        ).first()
        if existe:
            flash(f'Já existe uma ocorrência para {mes:02d}/{ano}.', 'warning')
        else:
            cp = _criar_conta_pagar(
                admin_id=admin_id,
                descricao=f'{desp.nome} — {mes:02d}/{ano}',
                valor=valor,
                data_vencimento=data_venc,
            )
            oc = DespesaEscritorioOcorrencia(
                despesa_id=desp.id, competencia_ano=ano, competencia_mes=mes,
                data_vencimento=data_venc, valor=valor,
                conta_pagar_id=cp.id, admin_id=admin_id,
            )
            db.session.add(oc)
            db.session.commit()
            flash(f'Ocorrência avulsa de "{desp.nome}" criada em Contas a Pagar!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao criar ocorrência avulsa: {e}')
        flash('Erro ao criar ocorrência.', 'danger')

    mes = request.form.get('mes_painel', date.today().month)
    ano = request.form.get('ano_painel', date.today().year)
    return redirect(url_for('custos_escritorio.painel_mensal', mes=mes, ano=ano))


# ─── EXCLUIR OCORRÊNCIA ───────────────────────────────────────────────────────

@custos_escritorio_bp.route('/ocorrencias/<int:oc_id>/excluir', methods=['POST'])
@login_required
def excluir_ocorrencia(oc_id):
    admin_id = get_admin_id()
    oc = DespesaEscritorioOcorrencia.query.filter_by(id=oc_id, admin_id=admin_id).first_or_404()
    mes, ano = oc.competencia_mes, oc.competencia_ano

    if oc.conta_pagar_id:
        cp = ContaPagar.query.filter_by(id=oc.conta_pagar_id, admin_id=admin_id).first()
        if cp and cp.status != 'PENDENTE':
            flash('Só é possível excluir ocorrências com Conta a Pagar ainda PENDENTE.', 'warning')
            return redirect(url_for('custos_escritorio.painel_mensal', mes=mes, ano=ano))
        if cp:
            db.session.delete(cp)

    db.session.delete(oc)
    db.session.commit()
    flash('Ocorrência excluída com sucesso.', 'success')
    return redirect(url_for('custos_escritorio.painel_mensal', mes=mes, ano=ano))


# ─── PAINEL MENSAL ────────────────────────────────────────────────────────────

@custos_escritorio_bp.route('/painel')
@login_required
def painel_mensal():
    admin_id = get_admin_id()
    hoje = date.today()
    mes = int(request.args.get('mes', hoje.month))
    ano = int(request.args.get('ano', hoje.year))

    # Clamp
    if mes < 1: mes = 1
    if mes > 12: mes = 12

    ocorrencias = (
        DespesaEscritorioOcorrencia.query
        .filter_by(admin_id=admin_id, competencia_ano=ano, competencia_mes=mes)
        .join(DespesaEscritorio)
        .order_by(DespesaEscritorio.nome)
        .all()
    )

    # Enriquecer com status do ContaPagar
    ocs_rich = []
    total_pendente = Decimal('0')
    total_pago = Decimal('0')
    total_geral = Decimal('0')
    totais_por_categoria = {}  # {nome_categoria: {'total': Decimal, 'cor': str}}
    for oc in ocorrencias:
        status_cp = None
        cp_id = oc.conta_pagar_id
        if oc.conta_pagar:
            status_cp = oc.conta_pagar.status
        ocs_rich.append({
            'oc': oc,
            'status': status_cp or 'SEM_CP',
            'cp_id': cp_id,
        })
        total_geral += oc.valor
        if status_cp == 'PAGO':
            total_pago += oc.valor
        else:
            total_pendente += oc.valor
        # Aggregate by category
        cat_nome = oc.despesa.categoria.nome
        cat_cor = oc.despesa.categoria.cor
        if cat_nome not in totais_por_categoria:
            totais_por_categoria[cat_nome] = {'total': Decimal('0'), 'cor': cat_cor}
        totais_por_categoria[cat_nome]['total'] += oc.valor

    # Despesas avulsas ativas (para modal de criação avulsa)
    despesas_avulsas = DespesaEscritorio.query.filter_by(
        admin_id=admin_id, ativo=True, recorrente=False
    ).order_by(DespesaEscritorio.nome).all()

    # Navegação mês anterior / próximo
    if mes == 1:
        mes_ant, ano_ant = 12, ano - 1
    else:
        mes_ant, ano_ant = mes - 1, ano
    if mes == 12:
        mes_prox, ano_prox = 1, ano + 1
    else:
        mes_prox, ano_prox = mes + 1, ano

    MESES = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

    totais_categorias_sorted = sorted(
        totais_por_categoria.items(), key=lambda x: x[1]['total'], reverse=True
    )

    return render_template(
        'custos_escritorio/painel_mensal.html',
        ocorrencias=ocs_rich,
        mes=mes, ano=ano,
        mes_nome=MESES[mes],
        mes_ant=mes_ant, ano_ant=ano_ant,
        mes_prox=mes_prox, ano_prox=ano_prox,
        total_pendente=total_pendente,
        total_pago=total_pago,
        total_geral=total_geral,
        totais_categorias=totais_categorias_sorted,
        despesas_avulsas=despesas_avulsas,
        hoje=hoje,
    )


# ─── GERAR MÊS ────────────────────────────────────────────────────────────────

@custos_escritorio_bp.route('/painel/gerar-mes', methods=['POST'])
@login_required
def gerar_mes():
    admin_id = get_admin_id()
    mes = int(request.form.get('mes', date.today().month))
    ano = int(request.form.get('ano', date.today().year))

    despesas_rec = DespesaEscritorio.query.filter_by(
        admin_id=admin_id, recorrente=True, ativo=True
    ).all()

    criadas = 0
    ignoradas = 0
    erros = 0

    for desp in despesas_rec:
        existe = DespesaEscritorioOcorrencia.query.filter_by(
            despesa_id=desp.id, competencia_ano=ano, competencia_mes=mes
        ).first()
        if existe:
            ignoradas += 1
            continue
        try:
            # Calcular data de vencimento (respeitar fim de mês)
            ultimo_dia = monthrange(ano, mes)[1]
            dia = min(desp.dia_vencimento, ultimo_dia)
            data_venc = date(ano, mes, dia)

            cp = _criar_conta_pagar(
                admin_id=admin_id,
                descricao=f'{desp.nome} — {mes:02d}/{ano}',
                valor=desp.valor,
                data_vencimento=data_venc,
            )
            oc = DespesaEscritorioOcorrencia(
                despesa_id=desp.id, competencia_ano=ano, competencia_mes=mes,
                data_vencimento=data_venc, valor=desp.valor,
                conta_pagar_id=cp.id, admin_id=admin_id,
            )
            db.session.add(oc)
            criadas += 1
        except Exception as e:
            logger.error(f'Erro ao gerar ocorrência para despesa {desp.id}: {e}')
            erros += 1

    try:
        db.session.commit()
        if criadas:
            flash(
                f'{criadas} ocorrência(s) gerada(s) em Contas a Pagar para {mes:02d}/{ano}. '
                f'{ignoradas} já existiam.',
                'success'
            )
        elif ignoradas:
            flash(f'Todas as despesas recorrentes já têm ocorrência para {mes:02d}/{ano}.', 'info')
        else:
            flash('Nenhuma despesa recorrente ativa encontrada.', 'warning')
        if erros:
            flash(f'{erros} despesa(s) não puderam ser geradas — veja os logs.', 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao commitar geração de mês: {e}')
        flash('Erro ao gerar mês. Tente novamente.', 'danger')

    return redirect(url_for('custos_escritorio.painel_mensal', mes=mes, ano=ano))
