"""
subempreiteiros_views.py
Blueprint para CRUD e dashboard de Subempreiteiros — Task 57.
Rota base: /subempreiteiros
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app import db
from models import (
    Subempreiteiro, RDOSubempreitadaApontamento, TarefaCronograma,
    RDO, Obra, GestaoCustoPai,
)

logger = logging.getLogger(__name__)

subempreiteiros_bp = Blueprint('subempreiteiros', __name__, url_prefix='/subempreiteiros')


def _admin_id():
    if not current_user.is_authenticated:
        return None
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        return current_user.admin_id
    return current_user.id


def _agregados_subempreiteiro(sub_id: int, admin_id: int) -> dict:
    """Calcula KPIs agregados para um subempreiteiro."""
    apt_q = (
        db.session.query(
            func.count(RDOSubempreitadaApontamento.id).label('n_apontamentos'),
            func.coalesce(func.sum(RDOSubempreitadaApontamento.quantidade_produzida), 0.0).label('qtd_total'),
            func.coalesce(func.sum(RDOSubempreitadaApontamento.qtd_pessoas * RDOSubempreitadaApontamento.horas_trabalhadas), 0.0).label('hh_total'),
            func.coalesce(func.avg(RDOSubempreitadaApontamento.homem_hora), 0.0).label('hh_medio'),
        )
        .filter(
            RDOSubempreitadaApontamento.subempreiteiro_id == sub_id,
            RDOSubempreitadaApontamento.admin_id == admin_id,
        )
        .first()
    )

    n_tarefas = (
        db.session.query(func.count(func.distinct(RDOSubempreitadaApontamento.tarefa_cronograma_id)))
        .filter(
            RDOSubempreitadaApontamento.subempreiteiro_id == sub_id,
            RDOSubempreitadaApontamento.admin_id == admin_id,
        )
        .scalar()
    ) or 0

    # Custo médio por unidade (custos lançados em GestaoCustos vinculados a este subempreiteiro)
    custo_total = (
        db.session.query(func.coalesce(func.sum(GestaoCustoPai.valor_total), 0))
        .filter(
            GestaoCustoPai.subempreiteiro_id == sub_id,
            GestaoCustoPai.admin_id == admin_id,
        )
        .scalar()
    ) or 0
    custo_total_f = float(custo_total)
    qtd_total_f = float(apt_q.qtd_total or 0) if apt_q else 0.0
    custo_unitario_medio = (custo_total_f / qtd_total_f) if qtd_total_f > 0 else 0.0

    # Última obra atendida
    ultima = (
        db.session.query(Obra.nome, RDO.data_relatorio)
        .join(RDO, RDO.obra_id == Obra.id)
        .join(RDOSubempreitadaApontamento, RDOSubempreitadaApontamento.rdo_id == RDO.id)
        .filter(
            RDOSubempreitadaApontamento.subempreiteiro_id == sub_id,
            RDOSubempreitadaApontamento.admin_id == admin_id,
        )
        .order_by(RDO.data_relatorio.desc())
        .first()
    )

    return {
        'n_apontamentos': int(apt_q.n_apontamentos or 0) if apt_q else 0,
        'n_tarefas': int(n_tarefas),
        'qtd_total': qtd_total_f,
        'hh_total': float(apt_q.hh_total or 0) if apt_q else 0.0,
        'produtividade_media': float(apt_q.hh_medio or 0) if apt_q else 0.0,
        'custo_total': custo_total_f,
        'custo_unitario_medio': custo_unitario_medio,
        'ultima_obra': ultima[0] if ultima else None,
        'ultima_data': ultima[1] if ultima else None,
    }


@subempreiteiros_bp.route('/')
@login_required
def listar():
    admin_id = _admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    busca = request.args.get('busca', '').strip()
    mostrar_inativos = request.args.get('inativos') == '1'

    q = Subempreiteiro.query.filter_by(admin_id=admin_id)
    if not mostrar_inativos:
        q = q.filter_by(ativo=True)
    if busca:
        like = f'%{busca}%'
        q = q.filter(or_(
            Subempreiteiro.nome.ilike(like),
            Subempreiteiro.cnpj.ilike(like),
            Subempreiteiro.especialidade.ilike(like),
        ))
    subs = q.order_by(Subempreiteiro.nome).all()

    indicadores = {s.id: _agregados_subempreiteiro(s.id, admin_id) for s in subs}

    return render_template(
        'subempreiteiros/listar.html',
        subs=subs,
        indicadores=indicadores,
        busca=busca,
        mostrar_inativos=mostrar_inativos,
    )


def _form_to_kwargs(form):
    return dict(
        nome=form.get('nome', '').strip(),
        cnpj=(form.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '').strip() or None),
        especialidade=form.get('especialidade', '').strip() or None,
        contato_responsavel=form.get('contato_responsavel', '').strip() or None,
        telefone=form.get('telefone', '').strip() or None,
        email=form.get('email', '').strip() or None,
        chave_pix=form.get('chave_pix', '').strip() or None,
        observacoes=form.get('observacoes', '').strip() or None,
    )


@subempreiteiros_bp.route('/criar', methods=['GET', 'POST'])
@login_required
def criar():
    admin_id = _admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        try:
            kwargs = _form_to_kwargs(request.form)
            if not kwargs['nome']:
                flash('Nome é obrigatório.', 'warning')
                return redirect(url_for('subempreiteiros.criar'))
            if kwargs['cnpj']:
                existe = Subempreiteiro.query.filter_by(cnpj=kwargs['cnpj'], admin_id=admin_id).first()
                if existe:
                    flash(f'Já existe um subempreiteiro com o CNPJ {kwargs["cnpj"]}.', 'danger')
                    return redirect(url_for('subempreiteiros.criar'))
            sub = Subempreiteiro(admin_id=admin_id, ativo=True, **kwargs)
            db.session.add(sub)
            db.session.commit()
            flash(f'Subempreiteiro "{sub.nome}" cadastrado com sucesso.', 'success')
            return redirect(url_for('subempreiteiros.listar'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar subempreiteiro: {e}')
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('subempreiteiros/form.html', sub=None)


@subempreiteiros_bp.route('/<int:sub_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(sub_id):
    admin_id = _admin_id()
    sub = Subempreiteiro.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()
    if request.method == 'POST':
        try:
            kwargs = _form_to_kwargs(request.form)
            if not kwargs['nome']:
                flash('Nome é obrigatório.', 'warning')
                return redirect(url_for('subempreiteiros.editar', sub_id=sub_id))
            if kwargs['cnpj']:
                existe = Subempreiteiro.query.filter(
                    Subempreiteiro.cnpj == kwargs['cnpj'],
                    Subempreiteiro.admin_id == admin_id,
                    Subempreiteiro.id != sub_id,
                ).first()
                if existe:
                    flash(f'Já existe outro subempreiteiro com o CNPJ {kwargs["cnpj"]}.', 'danger')
                    return redirect(url_for('subempreiteiros.editar', sub_id=sub_id))
            for k, v in kwargs.items():
                setattr(sub, k, v)
            sub.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Atualizado com sucesso.', 'success')
            return redirect(url_for('subempreiteiros.listar'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao editar subempreiteiro: {e}')
            flash(f'Erro ao salvar: {e}', 'danger')
    return render_template('subempreiteiros/form.html', sub=sub)


@subempreiteiros_bp.route('/<int:sub_id>/inativar', methods=['POST'])
@login_required
def inativar(sub_id):
    admin_id = _admin_id()
    sub = Subempreiteiro.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()
    sub.ativo = not sub.ativo
    sub.updated_at = datetime.utcnow()
    db.session.commit()
    estado = 'reativado' if sub.ativo else 'inativado'
    flash(f'Subempreiteiro "{sub.nome}" {estado}.', 'success')
    return redirect(url_for('subempreiteiros.listar'))


@subempreiteiros_bp.route('/<int:sub_id>')
@login_required
def detalhe(sub_id):
    admin_id = _admin_id()
    sub = Subempreiteiro.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()
    indicadores = _agregados_subempreiteiro(sub_id, admin_id)

    historico = (
        db.session.query(
            RDOSubempreitadaApontamento,
            RDO.data_relatorio,
            RDO.numero_rdo,
            Obra.nome.label('obra_nome'),
            TarefaCronograma.nome_tarefa,
            TarefaCronograma.unidade_medida,
        )
        .join(RDO, RDO.id == RDOSubempreitadaApontamento.rdo_id)
        .join(Obra, Obra.id == RDO.obra_id)
        .join(TarefaCronograma, TarefaCronograma.id == RDOSubempreitadaApontamento.tarefa_cronograma_id)
        .filter(
            RDOSubempreitadaApontamento.subempreiteiro_id == sub_id,
            RDOSubempreitadaApontamento.admin_id == admin_id,
        )
        .order_by(RDO.data_relatorio.desc())
        .limit(200)
        .all()
    )

    custos = (
        GestaoCustoPai.query
        .filter_by(subempreiteiro_id=sub_id, admin_id=admin_id)
        .order_by(GestaoCustoPai.data_criacao.desc())
        .limit(50)
        .all()
    )

    return render_template(
        'subempreiteiros/detalhe.html',
        sub=sub,
        indicadores=indicadores,
        historico=historico,
        custos=custos,
    )


# ────────────────────────────────────────────────────────────────────
# API JSON para uso no formulário do RDO
# ────────────────────────────────────────────────────────────────────

@subempreiteiros_bp.route('/api/lista')
@login_required
def api_lista():
    admin_id = _admin_id()
    subs = (Subempreiteiro.query
            .filter_by(admin_id=admin_id, ativo=True)
            .order_by(Subempreiteiro.nome).all())
    return jsonify({
        'status': 'ok',
        'subempreiteiros': [
            {'id': s.id, 'nome': s.nome, 'especialidade': s.especialidade or ''}
            for s in subs
        ],
    })
