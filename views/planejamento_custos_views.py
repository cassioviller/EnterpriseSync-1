"""Task #70 — Rotas do Planejamento de Custos da Obra.

Blueprint `planejamento_custos_bp` com 7 rotas sob
`/obras/<obra_id>/planejamento-custos/...`:

  1. GET  /               — lista de serviços de custo
  2. GET/POST /novo       — criar serviço
  3. GET/POST /<id>/editar — editar serviço (3 blocos: orçado/realizado/a realizar)
  4. GET/POST /<id>/equipe — CRUD equipe planejada
  5. GET/POST /<id>/cotacoes — CRUD cotação interna
  6. POST /<id>/excluir   — remover serviço
  7. POST /<id>/vincular-item-comercial — (des)vincular a ItemMedicaoComercial

Todas as operações são rigorosamente filtradas por admin_id.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    abort,
)
from flask_login import login_required, current_user

from models import (
    db,
    Obra,
    Funcionario,
    Fornecedor,
    ItemMedicaoComercial,
    ObraServicoCusto,
    ObraServicoEquipePlanejada,
    ObraServicoCotacaoInterna,
    ObraServicoCotacaoInternaLinha,
)
from services.resumo_custos_obra import (
    recalcular_servico,
    recalcular_obra,
    calcular_resumo_obra,
)
from utils.tenant import get_tenant_admin_id


logger = logging.getLogger(__name__)

planejamento_custos_bp = Blueprint(
    'planejamento_custos',
    __name__,
    url_prefix='/obras/<int:obra_id>/planejamento-custos',
)


def _get_obra(obra_id, admin_id):
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        abort(404)
    return obra


def _get_servico(obra_id, svc_id, admin_id):
    svc = ObraServicoCusto.query.filter_by(
        id=svc_id, obra_id=obra_id, admin_id=admin_id
    ).first()
    if not svc:
        abort(404)
    return svc


def _dec(v, default='0'):
    if v in (None, ''):
        return Decimal(default)
    try:
        return Decimal(str(v).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal(default)


# ─────────────────────────────────────────────────────────────────────────
# 1. Lista
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/', methods=['GET'])
@login_required
def lista(obra_id):
    admin_id = get_tenant_admin_id()
    obra = _get_obra(obra_id, admin_id)
    resumo = calcular_resumo_obra(obra_id, admin_id=admin_id)
    servicos = ObraServicoCusto.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).order_by(ObraServicoCusto.id).all()
    return render_template(
        'obras/planejamento_custos/lista.html',
        obra=obra,
        servicos=servicos,
        resumo=resumo,
    )


# ─────────────────────────────────────────────────────────────────────────
# 2. Novo
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo(obra_id):
    admin_id = get_tenant_admin_id()
    obra = _get_obra(obra_id, admin_id)
    itens_medicao = ItemMedicaoComercial.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).all()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Nome do serviço é obrigatório.', 'warning')
            return redirect(url_for('planejamento_custos.novo', obra_id=obra_id))

        item_id = request.form.get('item_medicao_comercial_id', type=int) or None
        # Valida ownership (tenant + obra) ANTES de persistir e checa duplicata FK UNIQUE
        if item_id:
            item = ItemMedicaoComercial.query.filter_by(
                id=item_id, obra_id=obra_id, admin_id=admin_id
            ).first()
            if not item:
                flash('Item comercial inválido para esta obra.', 'danger')
                return redirect(url_for('planejamento_custos.novo', obra_id=obra_id))
            ja = ObraServicoCusto.query.filter_by(
                item_medicao_comercial_id=item_id
            ).first()
            if ja:
                flash('Este item comercial já possui serviço de custo vinculado.', 'warning')
                return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=ja.id))

        svc = ObraServicoCusto(
            admin_id=admin_id,
            obra_id=obra_id,
            nome=nome,
            item_medicao_comercial_id=item_id,
            valor_orcado=_dec(request.form.get('valor_orcado')),
            material_a_realizar=_dec(request.form.get('material_a_realizar')),
            outros_a_realizar=_dec(request.form.get('outros_a_realizar')),
        )
        db.session.add(svc)
        db.session.commit()
        recalcular_obra(obra_id, admin_id=admin_id)
        db.session.commit()
        flash('Serviço de custo criado.', 'success')
        return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))

    return render_template(
        'obras/planejamento_custos/editar.html',
        obra=obra,
        svc=None,
        itens_medicao=itens_medicao,
        funcionarios=[],
    )


# ─────────────────────────────────────────────────────────────────────────
# 3. Editar
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/<int:svc_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(obra_id, svc_id):
    admin_id = get_tenant_admin_id()
    obra = _get_obra(obra_id, admin_id)
    svc = _get_servico(obra_id, svc_id, admin_id)

    if request.method == 'POST':
        svc.nome = (request.form.get('nome') or svc.nome).strip()

        # Vincular / desvincular item comercial com checagem de unicidade
        novo_item_id = request.form.get('item_medicao_comercial_id', type=int) or None
        if novo_item_id != svc.item_medicao_comercial_id:
            if novo_item_id:
                item = ItemMedicaoComercial.query.filter_by(
                    id=novo_item_id, obra_id=obra_id, admin_id=admin_id
                ).first()
                if not item:
                    flash('Item comercial não encontrado.', 'danger')
                    return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))
                ja = ObraServicoCusto.query.filter(
                    ObraServicoCusto.item_medicao_comercial_id == novo_item_id,
                    ObraServicoCusto.id != svc.id,
                ).first()
                if ja:
                    flash('Outro serviço já está vinculado a esse item comercial.', 'warning')
                    return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))
            svc.item_medicao_comercial_id = novo_item_id

        svc.valor_orcado = _dec(request.form.get('valor_orcado'))
        svc.material_a_realizar = _dec(request.form.get('material_a_realizar'))
        svc.outros_a_realizar = _dec(request.form.get('outros_a_realizar'))
        svc.override_realizado_manual = bool(request.form.get('override_realizado_manual'))
        if svc.override_realizado_manual:
            svc.realizado_material = _dec(request.form.get('realizado_material'))
            svc.realizado_mao_obra = _dec(request.form.get('realizado_mao_obra'))
            svc.realizado_outros = _dec(request.form.get('realizado_outros'))
        svc.observacoes = request.form.get('observacoes') or None
        db.session.commit()
        recalcular_servico(svc.id)
        db.session.commit()
        flash('Serviço atualizado.', 'success')
        return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))

    itens_medicao = ItemMedicaoComercial.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).all()
    funcionarios = Funcionario.query.filter_by(
        admin_id=admin_id, ativo=True
    ).order_by(Funcionario.nome).all()
    return render_template(
        'obras/planejamento_custos/editar.html',
        obra=obra,
        svc=svc,
        itens_medicao=itens_medicao,
        funcionarios=funcionarios,
    )


# ─────────────────────────────────────────────────────────────────────────
# 4. Equipe planejada
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/<int:svc_id>/equipe', methods=['GET', 'POST'])
@login_required
def equipe(obra_id, svc_id):
    admin_id = get_tenant_admin_id()
    obra = _get_obra(obra_id, admin_id)
    svc = _get_servico(obra_id, svc_id, admin_id)

    if request.method == 'POST':
        acao = request.form.get('acao', 'add')

        if acao == 'del':
            linha_id = request.form.get('linha_id', type=int)
            linha = ObraServicoEquipePlanejada.query.filter_by(
                id=linha_id, obra_servico_custo_id=svc.id, admin_id=admin_id
            ).first()
            if linha:
                db.session.delete(linha)
                db.session.commit()
                recalcular_servico(svc.id)
                db.session.commit()
                flash('Linha removida.', 'success')
            return redirect(url_for('planejamento_custos.equipe', obra_id=obra_id, svc_id=svc.id))

        funcionario_id = request.form.get('funcionario_id', type=int) or None
        funcionario = None
        if funcionario_id:
            funcionario = Funcionario.query.filter_by(
                id=funcionario_id, admin_id=admin_id
            ).first()

        # snapshot a partir do funcionário
        nome = (request.form.get('funcionario_nome') or
                (funcionario.nome if funcionario else '')).strip()
        if not nome:
            flash('Informe o funcionário ou um nome livre.', 'warning')
            return redirect(url_for('planejamento_custos.equipe', obra_id=obra_id, svc_id=svc.id))

        diaria = _dec(request.form.get('diaria'))
        almoco = _dec(request.form.get('almoco_e_cafe'))
        transporte = _dec(request.form.get('transporte'))
        if funcionario:
            if float(diaria) == 0.0:
                diaria = _dec(funcionario.valor_diaria)
            if float(almoco) == 0.0:
                almoco = _dec(funcionario.valor_va)
            if float(transporte) == 0.0:
                transporte = _dec(funcionario.valor_vt)

        linha = ObraServicoEquipePlanejada(
            admin_id=admin_id,
            obra_servico_custo_id=svc.id,
            funcionario_id=funcionario.id if funcionario else None,
            funcionario_nome=nome,
            quantidade_dias=_dec(request.form.get('quantidade_dias')),
            diaria=diaria,
            almoco_e_cafe=almoco,
            transporte=transporte,
            observacoes=request.form.get('observacoes') or None,
        )
        db.session.add(linha)
        db.session.commit()
        recalcular_servico(svc.id)
        db.session.commit()
        flash('Linha de equipe adicionada.', 'success')
        return redirect(url_for('planejamento_custos.equipe', obra_id=obra_id, svc_id=svc.id))

    funcionarios = Funcionario.query.filter_by(
        admin_id=admin_id, ativo=True
    ).order_by(Funcionario.nome).all()
    return render_template(
        'obras/planejamento_custos/equipe.html',
        obra=obra, svc=svc, funcionarios=funcionarios,
    )


# ─────────────────────────────────────────────────────────────────────────
# 5. Cotações internas
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/<int:svc_id>/cotacoes', methods=['GET', 'POST'])
@login_required
def cotacoes(obra_id, svc_id):
    admin_id = get_tenant_admin_id()
    obra = _get_obra(obra_id, admin_id)
    svc = _get_servico(obra_id, svc_id, admin_id)

    if request.method == 'POST':
        acao = request.form.get('acao', 'add')

        if acao == 'del':
            cid = request.form.get('cotacao_id', type=int)
            cot = ObraServicoCotacaoInterna.query.filter_by(
                id=cid, obra_servico_custo_id=svc.id, admin_id=admin_id
            ).first()
            if cot:
                if svc.cotacao_selecionada_id == cot.id:
                    svc.cotacao_selecionada_id = None
                db.session.delete(cot)
                db.session.commit()
                recalcular_servico(svc.id)
                db.session.commit()
                flash('Cotação removida.', 'success')
            return redirect(url_for('planejamento_custos.cotacoes', obra_id=obra_id, svc_id=svc.id))

        if acao == 'selecionar':
            cid = request.form.get('cotacao_id', type=int)
            ObraServicoCotacaoInterna.query.filter_by(
                obra_servico_custo_id=svc.id, admin_id=admin_id
            ).update({'selecionada': False})
            cot = ObraServicoCotacaoInterna.query.filter_by(
                id=cid, obra_servico_custo_id=svc.id, admin_id=admin_id
            ).first()
            if cot:
                cot.selecionada = True
                svc.cotacao_selecionada_id = cot.id
            db.session.commit()
            recalcular_servico(svc.id)
            db.session.commit()
            flash('Cotação selecionada — material A Realizar atualizado.', 'success')
            return redirect(url_for('planejamento_custos.cotacoes', obra_id=obra_id, svc_id=svc.id))

        # Nova cotação (acao == 'add')
        cot = ObraServicoCotacaoInterna(
            admin_id=admin_id,
            obra_servico_custo_id=svc.id,
            fornecedor_nome=(request.form.get('fornecedor_nome') or '').strip() or 'Sem nome',
            fornecedor_id=request.form.get('fornecedor_id', type=int) or None,
            prazo_entrega=request.form.get('prazo_entrega') or None,
            condicao_pagamento=request.form.get('condicao_pagamento') or None,
            observacoes=request.form.get('observacoes') or None,
            selecionada=False,
        )
        db.session.add(cot)
        db.session.flush()

        descricoes = request.form.getlist('linha_descricao[]')
        unidades = request.form.getlist('linha_unidade[]')
        quantidades = request.form.getlist('linha_quantidade[]')
        valores = request.form.getlist('linha_valor_unitario[]')
        for desc, uni, qtd, vu in zip(descricoes, unidades, quantidades, valores):
            desc = (desc or '').strip()
            if not desc:
                continue
            linha = ObraServicoCotacaoInternaLinha(
                admin_id=admin_id,
                cotacao_id=cot.id,
                descricao=desc,
                unidade=uni or None,
                quantidade=_dec(qtd),
                valor_unitario=_dec(vu),
            )
            db.session.add(linha)
        db.session.commit()
        flash('Cotação criada.', 'success')
        return redirect(url_for('planejamento_custos.cotacoes', obra_id=obra_id, svc_id=svc.id))

    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id).order_by(Fornecedor.nome).all()
    return render_template(
        'obras/planejamento_custos/cotacoes.html',
        obra=obra, svc=svc, fornecedores=fornecedores,
    )


# ─────────────────────────────────────────────────────────────────────────
# 6. Excluir
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/<int:svc_id>/excluir', methods=['POST'])
@login_required
def excluir(obra_id, svc_id):
    admin_id = get_tenant_admin_id()
    _get_obra(obra_id, admin_id)
    svc = _get_servico(obra_id, svc_id, admin_id)
    db.session.delete(svc)
    db.session.commit()
    flash('Serviço removido.', 'success')
    return redirect(url_for('planejamento_custos.lista', obra_id=obra_id))


# ─────────────────────────────────────────────────────────────────────────
# 7. Vincular / desvincular item comercial
# ─────────────────────────────────────────────────────────────────────────
@planejamento_custos_bp.route('/<int:svc_id>/vincular-item-comercial', methods=['POST'])
@login_required
def vincular_item_comercial(obra_id, svc_id):
    admin_id = get_tenant_admin_id()
    _get_obra(obra_id, admin_id)
    svc = _get_servico(obra_id, svc_id, admin_id)
    item_id = request.form.get('item_medicao_comercial_id', type=int) or None
    if item_id:
        item = ItemMedicaoComercial.query.filter_by(
            id=item_id, obra_id=obra_id, admin_id=admin_id
        ).first()
        if not item:
            flash('Item comercial não encontrado.', 'danger')
            return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))
        ja = ObraServicoCusto.query.filter(
            ObraServicoCusto.item_medicao_comercial_id == item_id,
            ObraServicoCusto.id != svc.id,
        ).first()
        if ja:
            flash('Outro serviço já está vinculado a esse item comercial.', 'warning')
            return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))
        svc.item_medicao_comercial_id = item_id
    else:
        svc.item_medicao_comercial_id = None
    db.session.commit()
    flash('Vínculo atualizado.', 'success')
    return redirect(url_for('planejamento_custos.editar', obra_id=obra_id, svc_id=svc.id))
