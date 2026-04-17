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
    explodir_servico_para_quantidade,
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
    if atual:
        if atual.vigencia_inicio < vig:
            atual.vigencia_fim = vig - timedelta(days=1)
        else:
            # Mesma data ou retroativa: fecha imediatamente o anterior na
            # própria data (evita sobreposição/ambiguidade histórica).
            atual.vigencia_fim = atual.vigencia_inicio
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
@catalogo_bp.route('/servicos')
@login_required
def servicos_list():
    """Catálogo de Serviços — lista paramétrica com preço de venda."""
    aid = _admin_id()
    q = (request.args.get('q') or '').strip()
    qry = Servico.query.filter_by(admin_id=aid, ativo=True)
    if q:
        qry = qry.filter(Servico.nome.ilike(f'%{q}%'))
    servicos = qry.order_by(Servico.nome).all()
    return render_template('catalogo/servicos_list.html', servicos=servicos, q=q)


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


@catalogo_bp.route('/servicos/<int:servico_id>/composicao/<int:comp_id>/editar', methods=['POST'])
@login_required
def servico_composicao_editar(servico_id, comp_id):
    """Task #89: edita o coeficiente / observação de uma linha de composição."""
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    comp = ComposicaoServico.query.filter_by(
        id=comp_id, servico_id=svc.id, admin_id=aid
    ).first_or_404()
    coef = _to_decimal(request.form.get('coeficiente'), '0')
    if coef <= 0:
        flash('Coeficiente deve ser > 0.', 'error')
        return redirect(url_for('catalogo.servico_composicao', servico_id=svc.id))
    comp.coeficiente = coef
    obs = request.form.get('observacao')
    if obs is not None:
        comp.observacao = obs.strip() or None
    db.session.flush()
    recalcular_servico_preco(svc)
    db.session.commit()
    flash('Coeficiente atualizado.', 'success')
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
    soma_realizado = 0.0
    soma_orcado = 0.0
    soma_qtd = 0.0  # soma de quantidade total (de medições) por obra para custo médio por unidade
    for c in custos:
        realizado = float(c.realizado_material or 0) + float(c.realizado_mao_obra or 0) + float(c.realizado_outros or 0)
        orcado = float(c.valor_orcado or 0)
        delta_pct = ((realizado - orcado) / orcado * 100.0) if orcado > 0 else None
        # quantidade da obra: soma quantidade dos ItemMedicaoComercial vinculados ao serviço naquela obra
        from models import ItemMedicaoComercial
        qtd_obra = db.session.query(db.func.coalesce(db.func.sum(ItemMedicaoComercial.quantidade), 0)).filter(
            ItemMedicaoComercial.admin_id == aid,
            ItemMedicaoComercial.obra_id == c.obra_id,
            ItemMedicaoComercial.servico_id == svc.id,
        ).scalar() or 0
        try:
            qtd_obra_f = float(qtd_obra)
        except Exception:
            qtd_obra_f = 0.0
        custo_unit = (realizado / qtd_obra_f) if qtd_obra_f > 0 else None
        linhas.append({
            'obra': obras_map.get(c.obra_id),
            'custo': c,
            'realizado': realizado,
            'orcado': orcado,
            'delta_pct': delta_pct,
            'quantidade': qtd_obra_f,
            'custo_unitario_realizado': custo_unit,
        })
        soma_realizado += realizado
        soma_orcado += orcado
        soma_qtd += qtd_obra_f

    medias = {
        'total_obras': len(linhas),
        'soma_realizado': soma_realizado,
        'soma_orcado': soma_orcado,
        'soma_quantidade': soma_qtd,
        'custo_medio_realizado_por_unidade': (soma_realizado / soma_qtd) if soma_qtd > 0 else None,
        'realizado_medio_por_obra': (soma_realizado / len(linhas)) if linhas else 0.0,
        'orcado_medio_por_obra': (soma_orcado / len(linhas)) if linhas else 0.0,
        'delta_pct_global': ((soma_realizado - soma_orcado) / soma_orcado * 100.0) if soma_orcado > 0 else None,
    }
    return render_template(
        'catalogo/servico_historico.html',
        servico=svc, linhas=linhas, medias=medias,
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


@catalogo_bp.route('/api/servicos/<int:servico_id>/explodir')
@login_required
def api_explodir_servico(servico_id):
    """Task #89: explosão paramétrica de um serviço para uma quantidade.

    Query params:
        quantidade (float, default 1)
        data_ref   (YYYY-MM-DD, opcional — default hoje)
    Retorna o dict de `explodir_servico_para_quantidade` em JSON.
    """
    from datetime import datetime as _dt
    aid = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404()
    try:
        qtd = float(request.args.get('quantidade', '1') or '1')
    except (TypeError, ValueError):
        qtd = 1.0
    data_ref = None
    dr = (request.args.get('data_ref') or '').strip()
    if dr:
        try:
            data_ref = _dt.strptime(dr, '%Y-%m-%d').date()
        except ValueError:
            data_ref = None
    r = explodir_servico_para_quantidade(svc, qtd, data_ref)

    def _f(v):
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    return jsonify({
        'servico_id': svc.id,
        'servico_nome': svc.nome,
        'unidade': svc.unidade_medida,
        'quantidade': _f(r['quantidade']),
        'custo_unitario': _f(r['custo_unitario']),
        'preco_unitario': _f(r['preco_unitario']),
        'lucro_unitario': _f(r['lucro_unitario']),
        'subtotal': _f(r['subtotal']),
        'custo_total': _f(r['custo_total']),
        'lucro_total': _f(r['lucro_total']),
        'imposto_pct': _f(r.get('imposto_pct')),
        'margem_lucro_pct': _f(r.get('margem_lucro_pct')),
        'erro': r.get('erro'),
        'categorias': {
            k: {
                'custo_unitario': _f(v['custo_unitario']),
                'custo_total': _f(v['custo_total']),
                'itens': v['itens'],
            } for k, v in r['categorias'].items()
        },
        'detalhamento': r['detalhamento'],
    })


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
    """Vincula um PropostaItem (legado) a um Servico do catálogo.

    Form params:
        servico_id (int, obrigatório p/ vincular; vazio para desvincular)
        atualizar_preco (bool/'1','true','on'): se truthy, recalcula
            snapshot do item (preco_unitario = servico.preco_venda_unitario,
            unidade do servico) — útil ao mover item legado para o catálogo.
    """
    aid = _admin_id()
    it = PropostaItem.query.get_or_404(item_id)
    if not it.proposta or getattr(it.proposta, 'admin_id', None) != aid:
        abort(403)
    servico_id = request.form.get('servico_id', type=int)
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404() if servico_id else None
    it.servico_id = svc.id if svc else None

    atualizar = (request.form.get('atualizar_preco') or '').strip().lower() in ('1', 'true', 'on', 'yes')
    if atualizar and svc is not None:
        if svc.preco_venda_unitario is not None:
            it.preco_unitario = svc.preco_venda_unitario
        if getattr(svc, 'unidade_medida', None):
            it.unidade = svc.unidade_medida
    db.session.commit()
    return jsonify({
        'ok': True, 'servico_id': it.servico_id,
        'preco_unitario': float(it.preco_unitario or 0),
        'unidade': it.unidade,
        'atualizado': bool(atualizar and svc is not None),
    })


@catalogo_bp.route('/medicao-itens/<int:item_id>/vincular-servico', methods=['POST'])
@login_required
def vincular_medicao_item(item_id):
    """Vincula um ItemMedicaoComercial (legado) a um Servico do catálogo.

    Form params:
        servico_id (int)
        atualizar_preco (bool): se truthy E o item tem `quantidade>0`,
            recalcula valor_comercial = quantidade × servico.preco_venda_unitario.
    """
    from decimal import Decimal as _D
    aid = _admin_id()
    it = ItemMedicaoComercial.query.filter_by(id=item_id, admin_id=aid).first_or_404()
    servico_id = request.form.get('servico_id', type=int)
    svc = Servico.query.filter_by(id=servico_id, admin_id=aid).first_or_404() if servico_id else None
    it.servico_id = svc.id if svc else None

    atualizar = (request.form.get('atualizar_preco') or '').strip().lower() in ('1', 'true', 'on', 'yes')
    valor_atualizado = False
    if atualizar and svc is not None and it.quantidade and svc.preco_venda_unitario:
        qtd = _D(str(it.quantidade))
        preco = _D(str(svc.preco_venda_unitario))
        if qtd > 0 and preco > 0:
            it.valor_comercial = (qtd * preco).quantize(_D('0.01'))
            valor_atualizado = True

    par = ObraServicoCusto.query.filter_by(
        item_medicao_comercial_id=it.id, admin_id=aid
    ).first()
    if par:
        par.servico_catalogo_id = it.servico_id
        if valor_atualizado:
            par.valor_orcado = it.valor_comercial
    db.session.commit()
    return jsonify({
        'ok': True, 'servico_id': it.servico_id,
        'valor_comercial': float(it.valor_comercial or 0),
        'atualizado': valor_atualizado,
    })


# ──────────────────────────────────────────────────────────────────────
# Alias /api/catalogo/* — endpoints AJAX padronizados
# (mantém compatibilidade com o spec original da Task #82)
# ──────────────────────────────────────────────────────────────────────
catalogo_api_bp = Blueprint('catalogo_api', __name__, url_prefix='/api/catalogo')


@catalogo_api_bp.route('/servicos/buscar')
@login_required
def api_alias_servicos():
    return api_buscar_servicos()


@catalogo_api_bp.route('/insumos/buscar')
@login_required
def api_alias_insumos():
    return api_buscar_insumos()


# ──────────────────────────────────────────────────────────────────────
# Aliases sob /propostas/* e /medicao/obra/* (alinhamento com spec original)
# ──────────────────────────────────────────────────────────────────────
catalogo_legacy_bp = Blueprint('catalogo_legacy', __name__)


@catalogo_legacy_bp.route(
    '/propostas/<int:id>/itens/<int:item_id>/vincular-servico', methods=['POST']
)
@login_required
def alias_vincular_proposta_item_spec(id, item_id):
    """Alias EXATO do spec Task #82: /propostas/<id>/itens/<item_id>/vincular-servico"""
    return vincular_proposta_item(item_id)


@catalogo_legacy_bp.route(
    '/medicao/obra/<int:id>/itens/<int:item_id>/vincular-servico', methods=['POST']
)
@login_required
def alias_vincular_medicao_item_spec(id, item_id):
    """Alias EXATO do spec Task #82: /medicao/obra/<id>/itens/<item_id>/vincular-servico"""
    return vincular_medicao_item(item_id)


# Aliases curtos (extras, mantidos por compatibilidade com revs anteriores)
@catalogo_legacy_bp.route(
    '/propostas/itens/<int:item_id>/vincular-servico', methods=['POST']
)
@login_required
def alias_vincular_proposta_item(item_id):
    return vincular_proposta_item(item_id)


@catalogo_legacy_bp.route(
    '/medicao/obra/itens/<int:item_id>/vincular-servico', methods=['POST']
)
@login_required
def alias_vincular_medicao_item(item_id):
    return vincular_medicao_item(item_id)
