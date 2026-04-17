"""
views/catalogo_views.py — Task #82

Blueprint do catálogo paramétrico:
  - CRUD de Insumos (com histórico de preços)
  - Gestão de Composição de Serviços (linhas insumo × coeficiente)
  - Recalcular preço de venda do serviço
  - APIs JSON p/ autocomplete em propostas e medição
  - Vincular PropostaItem / ItemMedicaoComercial a um Servico do catálogo
  - Histórico cross-obra de um serviço
"""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import logging

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    jsonify, abort,
)
from flask_login import login_required, current_user

from app import db
from models import (
    Servico, Insumo, PrecoBaseInsumo, ComposicaoServico,
    PropostaItem, ItemMedicaoComercial, ObraServicoCusto, Obra,
)
from services.orcamento_service import (
    calcular_precos_servico, recalcular_servico_preco,
)

logger = logging.getLogger(__name__)

catalogo_bp = Blueprint('catalogo', __name__, url_prefix='/catalogo')


def _admin_id():
    """Resolve admin_id do request (fallback robusto)."""
    try:
        if current_user and current_user.is_authenticated:
            return getattr(current_user, 'admin_id', None) or current_user.id
    except Exception:
        pass
    abort(401)


def _to_decimal(value, default='0'):
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal(default)


# ──────────────────────────────────────────────────────────────────────
# INSUMOS — CRUD
# ──────────────────────────────────────────────────────────────────────
@catalogo_bp.route('/insumos')
@login_required
def insumos_list():
    aid = _admin_id()
    q = (request.args.get('q') or '').strip()
    tipo = request.args.get('tipo') or ''
    query = Insumo.query.filter_by(admin_id=aid, ativo=True)
    if q:
        query = query.filter(Insumo.nome.ilike(f'%{q}%'))
    if tipo:
        query = query.filter_by(tipo=tipo)
    insumos = query.order_by(Insumo.nome).limit(500).all()
    return render_template(
        'catalogo/insumos_list.html',
        insumos=insumos, q=q, tipo=tipo,
    )


@catalogo_bp.route('/insumos/novo', methods=['GET', 'POST'])
@login_required
def insumo_novo():
    aid = _admin_id()
    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Nome é obrigatório', 'error')
            return redirect(url_for('catalogo.insumo_novo'))
        ins = Insumo(
            admin_id=aid,
            nome=nome,
            tipo=(request.form.get('tipo') or 'MATERIAL').upper(),
            unidade=(request.form.get('unidade') or 'un'),
            descricao=request.form.get('descricao') or None,
        )
        db.session.add(ins)
        db.session.flush()
        valor = _to_decimal(request.form.get('preco'), '0')
        if valor > 0:
            db.session.add(PrecoBaseInsumo(
                admin_id=aid, insumo_id=ins.id, valor=valor,
                vigencia_inicio=date.today(),
            ))
        db.session.commit()
        flash(f'Insumo "{ins.nome}" criado.', 'success')
        return redirect(url_for('catalogo.insumo_editar', insumo_id=ins.id))
    return render_template('catalogo/insumo_form.html', insumo=None)


@catalogo_bp.route('/insumos/<int:insumo_id>', methods=['GET', 'POST'])
@login_required
def insumo_editar(insumo_id):
    aid = _admin_id()
    ins = Insumo.query.filter_by(id=insumo_id, admin_id=aid).first_or_404()
    if request.method == 'POST':
        ins.nome = (request.form.get('nome') or ins.nome).strip()
        ins.tipo = (request.form.get('tipo') or ins.tipo).upper()
        ins.unidade = (request.form.get('unidade') or ins.unidade)
        ins.descricao = request.form.get('descricao') or None
        db.session.commit()
        flash('Insumo atualizado.', 'success')
        return redirect(url_for('catalogo.insumo_editar', insumo_id=ins.id))
    precos = sorted(ins.precos, key=lambda p: p.vigencia_inicio, reverse=True)
    return render_template('catalogo/insumo_form.html', insumo=ins, precos=precos)


@catalogo_bp.route('/insumos/<int:insumo_id>/preco', methods=['POST'])
@login_required
def insumo_novo_preco(insumo_id):
    """Cria nova vigência de preço; encerra a anterior automaticamente."""
    aid = _admin_id()
    ins = Insumo.query.filter_by(id=insumo_id, admin_id=aid).first_or_404()
    valor = _to_decimal(request.form.get('valor'), '0')
    vig_str = request.form.get('vigencia_inicio') or ''
    try:
        vig = datetime.strptime(vig_str, '%Y-%m-%d').date() if vig_str else date.today()
    except ValueError:
        vig = date.today()
    if valor <= 0:
        flash('Valor deve ser maior que zero.', 'error')
        return redirect(url_for('catalogo.insumo_editar', insumo_id=ins.id))
    # Encerra preço atual em D-1
    from datetime import timedelta
    atual = (
        PrecoBaseInsumo.query.filter_by(insumo_id=ins.id, vigencia_fim=None)
        .order_by(PrecoBaseInsumo.vigencia_inicio.desc()).first()
    )
    if atual and atual.vigencia_inicio < vig:
        atual.vigencia_fim = vig - timedelta(days=1)
    db.session.add(PrecoBaseInsumo(
        admin_id=aid, insumo_id=ins.id, valor=valor,
        vigencia_inicio=vig,
        observacao=(request.form.get('observacao') or None),
    ))
    db.session.commit()
    # Recalcula serviços afetados
    from services.orcamento_service import recalcular_servico_preco
    svc_ids = {c.servico_id for c in ins.composicoes}
    for sid in svc_ids:
        s = Servico.query.get(sid)
        if s:
            recalcular_servico_preco(s)
    db.session.commit()
    flash(f'Novo preço aplicado. {len(svc_ids)} serviço(s) recalculado(s).', 'success')
    return redirect(url_for('catalogo.insumo_editar', insumo_id=ins.id))


@catalogo_bp.route('/insumos/<int:insumo_id>/excluir', methods=['POST'])
@login_required
def insumo_excluir(insumo_id):
    aid = _admin_id()
    ins = Insumo.query.filter_by(id=insumo_id, admin_id=aid).first_or_404()
    if ins.composicoes:
        ins.ativo = False
        db.session.commit()
        flash('Insumo está em uso — desativado em vez de excluído.', 'warning')
    else:
        db.session.delete(ins)
        db.session.commit()
        flash('Insumo excluído.', 'success')
    return redirect(url_for('catalogo.insumos_list'))


# ──────────────────────────────────────────────────────────────────────
# SERVIÇOS — Composição + Preço
# ──────────────────────────────────────────────────────────────────────
@catalogo_bp.route('/servicos/<int:servico_id>/composicao', methods=['GET'])
@login_required
def servico_composicao(servico_id):
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    insumos_disp = Insumo.query.filter_by(admin_id=aid, ativo=True).order_by(Insumo.nome).all()
    calc = calcular_precos_servico(svc)
    return render_template(
        'catalogo/composicao_servico.html',
        servico=svc, insumos=insumos_disp, calc=calc,
    )


@catalogo_bp.route('/servicos/<int:servico_id>/composicao/add', methods=['POST'])
@login_required
def servico_composicao_add(servico_id):
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    insumo_id = request.form.get('insumo_id', type=int)
    coef = _to_decimal(request.form.get('coeficiente'), '0')
    if not insumo_id or coef <= 0:
        flash('Selecione insumo e informe coeficiente > 0.', 'error')
        return redirect(url_for('catalogo.servico_composicao', servico_id=svc.id))
    ins = Insumo.query.filter_by(id=insumo_id, admin_id=aid).first_or_404()
    existing = ComposicaoServico.query.filter_by(
        servico_id=svc.id, insumo_id=ins.id
    ).first()
    if existing:
        existing.coeficiente = coef
    else:
        db.session.add(ComposicaoServico(
            admin_id=aid, servico_id=svc.id, insumo_id=ins.id,
            coeficiente=coef,
            observacao=request.form.get('observacao') or None,
        ))
    db.session.flush()
    recalcular_servico_preco(svc)
    db.session.commit()
    flash('Composição atualizada.', 'success')
    return redirect(url_for('catalogo.servico_composicao', servico_id=svc.id))


@catalogo_bp.route('/servicos/<int:servico_id>/composicao/<int:comp_id>/excluir', methods=['POST'])
@login_required
def servico_composicao_excluir(servico_id, comp_id):
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    comp = ComposicaoServico.query.filter_by(
        id=comp_id, servico_id=svc.id, admin_id=aid
    ).first_or_404()
    db.session.delete(comp)
    db.session.flush()
    recalcular_servico_preco(svc)
    db.session.commit()
    flash('Linha removida.', 'success')
    return redirect(url_for('catalogo.servico_composicao', servico_id=svc.id))


@catalogo_bp.route('/servicos/<int:servico_id>/preco', methods=['POST'])
@login_required
def servico_atualizar_preco(servico_id):
    """Atualiza imposto/lucro e recalcula preço de venda."""
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    imp = request.form.get('imposto_pct')
    luc = request.form.get('margem_lucro_pct')
    svc.imposto_pct = _to_decimal(imp) if imp not in (None, '') else None
    svc.margem_lucro_pct = _to_decimal(luc) if luc not in (None, '') else None
    db.session.flush()
    r = recalcular_servico_preco(svc)
    db.session.commit()
    if r.get('erro'):
        flash(f'Erro: {r["erro"]}', 'error')
    else:
        flash(
            f'Preço recalculado: custo R$ {r["custo_unitario"]} → '
            f'venda R$ {r["preco_venda"]}',
            'success',
        )
    return redirect(url_for('catalogo.servico_composicao', servico_id=svc.id))


# ──────────────────────────────────────────────────────────────────────
# Histórico cross-obra de um serviço
# ──────────────────────────────────────────────────────────────────────
@catalogo_bp.route('/servicos/<int:servico_id>/historico-obras')
@login_required
def servico_historico(servico_id):
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    custos = (
        ObraServicoCusto.query
        .filter_by(admin_id=aid, servico_catalogo_id=svc.id)
        .all()
    )
    obras_map = {o.id: o for o in Obra.query.filter_by(admin_id=aid).all()}
    linhas = []
    for c in custos:
        realizado = float(c.realizado_material or 0) + float(c.realizado_mao_obra or 0) + float(c.realizado_outros or 0)
        orcado = float(c.valor_orcado or 0)
        delta_pct = ((realizado - orcado) / orcado * 100.0) if orcado > 0 else None
        linhas.append({
            'obra': obras_map.get(c.obra_id),
            'custo': c,
            'realizado': realizado,
            'orcado': orcado,
            'delta_pct': delta_pct,
        })
    return render_template(
        'catalogo/servico_historico.html',
        servico=svc, linhas=linhas,
    )


# ──────────────────────────────────────────────────────────────────────
# APIs JSON
# ──────────────────────────────────────────────────────────────────────
@catalogo_bp.route('/api/servicos/buscar')
@login_required
def api_buscar_servicos():
    aid = _admin_id()
    q = (request.args.get('q') or '').strip()
    query = Servico.query.filter_by(admin_id=aid, ativo=True)
    if q:
        query = query.filter(Servico.nome.ilike(f'%{q}%'))
    rows = query.order_by(Servico.nome).limit(20).all()
    return jsonify([{
        'id': s.id, 'nome': s.nome,
        'unidade': s.unidade_medida,
        'preco_venda': float(s.preco_venda_unitario or 0),
        'custo': float(s.custo_unitario or 0),
        'categoria': s.categoria,
    } for s in rows])


@catalogo_bp.route('/api/insumos/buscar')
@login_required
def api_buscar_insumos():
    aid = _admin_id()
    q = (request.args.get('q') or '').strip()
    query = Insumo.query.filter_by(admin_id=aid, ativo=True)
    if q:
        query = query.filter(Insumo.nome.ilike(f'%{q}%'))
    rows = query.order_by(Insumo.nome).limit(20).all()
    return jsonify([{
        'id': i.id, 'nome': i.nome,
        'tipo': i.tipo, 'unidade': i.unidade,
        'preco': i.preco_vigente(),
    } for i in rows])


# ──────────────────────────────────────────────────────────────────────
# Vincular itens existentes (legado) a Servico do catálogo
# ──────────────────────────────────────────────────────────────────────
@catalogo_bp.route('/proposta-itens/<int:item_id>/vincular-servico', methods=['POST'])
@login_required
def vincular_proposta_item(item_id):
    aid = _admin_id()
    it = PropostaItem.query.get_or_404(item_id)
    # Validar tenancy via proposta
    if not it.proposta or getattr(it.proposta, 'admin_id', None) != aid:
        abort(403)
    servico_id = request.form.get('servico_id', type=int)
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404() if servico_id else None
    it.servico_id = svc.id if svc else None
    db.session.commit()
    return jsonify({'ok': True, 'servico_id': it.servico_id})


@catalogo_bp.route('/medicao-itens/<int:item_id>/vincular-servico', methods=['POST'])
@login_required
def vincular_medicao_item(item_id):
    aid = _admin_id()
    it = ItemMedicaoComercial.query.filter_by(id=item_id, admin_id=aid).first_or_404()
    servico_id = request.form.get('servico_id', type=int)
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404() if servico_id else None
    it.servico_id = svc.id if svc else None
    # Propaga para o ObraServicoCusto pareado
    par = ObraServicoCusto.query.filter_by(
        item_medicao_comercial_id=it.id, admin_id=aid
    ).first()
    if par:
        par.servico_catalogo_id = it.servico_id
    db.session.commit()
    return jsonify({'ok': True, 'servico_id': it.servico_id})
