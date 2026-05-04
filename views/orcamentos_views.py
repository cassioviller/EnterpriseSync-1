"""
views/orcamentos_views.py — Task #115

Blueprint do módulo de Orçamentos (camada interna que gera Propostas).
Apenas usuários administradores podem ver/editar orçamentos.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc

from app import db
from auth import admin_required
from models import (
    Orcamento, OrcamentoItem, Servico, Cliente, Proposta, PropostaItem,
    PropostaHistorico, ConfiguracaoEmpresa, CronogramaTemplate,
    PropostaTemplate, PropostaClausula,
)
from services.orcamento_view_service import (
    snapshot_from_servico, recalcular_item, recalcular_orcamento,
)

logger = logging.getLogger(__name__)

orcamentos_bp = Blueprint('orcamentos', __name__, url_prefix='/orcamentos')


def _admin_id() -> int:
    return current_user.admin_id if getattr(current_user, 'admin_id', None) else current_user.id


def _parse_br_number(raw, default=0.0) -> float:
    """Task #165: aceita valores em pt-BR ('1.234,56') ou en-US ('1234.56').

    Regras:
      - None / '' → default
      - Números (int/float/Decimal) → float()
      - Se contém vírgula: assume pt-BR. Remove '.' (milhar) e troca ',' → '.'.
      - Se só tem ponto: trata como decimal en-US.
      - Em qualquer falha de parse, devolve default (não levanta).
    """
    if raw is None:
        return float(default)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, Decimal):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return float(default)
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except (TypeError, ValueError):
        return float(default)


def _parse_br_decimal(raw, default='0') -> Decimal:
    """Task #165: versão Decimal de _parse_br_number, para colunas Numeric."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return Decimal(str(default))
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    s = str(raw).strip()
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return Decimal(s)
    except Exception:
        return Decimal(str(default))


def _parse_template_override(raw: Optional[str], admin_id: int) -> Optional[int]:
    """Task #118: valida e devolve um cronograma_template_override_id seguro.

    Vazio/None → None (= usa o template padrão do serviço).
    Valida ownership pelo admin_id (multi-tenant). ID inválido → None silencioso.
    """
    if not raw:
        return None
    try:
        tid = int(raw)
    except (TypeError, ValueError):
        return None
    if tid <= 0:
        return None
    exists = db.session.query(CronogramaTemplate.id).filter_by(
        id=tid, admin_id=admin_id
    ).first()
    return tid if exists else None


def _gerar_numero(admin_id: int) -> str:
    ano = date.today().year
    base = f"ORC-{ano}-"
    count = Orcamento.query.filter_by(admin_id=admin_id).count() + 1
    while True:
        candidato = f"{base}{count:04d}"
        if not Orcamento.query.filter_by(admin_id=admin_id, numero=candidato).first():
            return candidato
        count += 1


# ───────────────────────────── LISTAR ─────────────────────────────
@orcamentos_bp.route('/')
@login_required
@admin_required
def listar():
    admin_id = _admin_id()
    orcamentos = Orcamento.query.filter_by(admin_id=admin_id) \
        .order_by(desc(Orcamento.criado_em)).all()
    return render_template('orcamentos/listar.html', orcamentos=orcamentos)


# ───────────────────────────── NOVO ─────────────────────────────
@orcamentos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo():
    admin_id = _admin_id()
    if request.method == 'POST':
        try:
            titulo = (request.form.get('titulo') or '').strip()
            if not titulo:
                flash('Título é obrigatório', 'error')
                return redirect(url_for('orcamentos.novo'))
            cliente_id = request.form.get('cliente_id') or None
            cliente_nome = (request.form.get('cliente_nome') or '').strip()
            if cliente_id:
                cli = Cliente.query.filter_by(id=int(cliente_id), admin_id=admin_id).first()
                if not cli:
                    flash('Cliente inválido.', 'error')
                    return redirect(url_for('orcamentos.novo'))
                if not cliente_nome:
                    cliente_nome = cli.nome
            cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
            imp_g = request.form.get('imposto_pct_global') or (cfg.imposto_pct_padrao if cfg else None)
            mar_g = request.form.get('margem_pct_global') or (cfg.lucro_pct_padrao if cfg else None)

            orc = Orcamento(
                admin_id=admin_id,
                numero=_gerar_numero(admin_id),
                titulo=titulo,
                descricao=request.form.get('descricao') or None,
                cliente_id=int(cliente_id) if cliente_id else None,
                cliente_nome=cliente_nome or None,
                imposto_pct_global=_parse_br_decimal(imp_g, '0') if imp_g not in (None, '') else None,
                margem_pct_global=_parse_br_decimal(mar_g, '0') if mar_g not in (None, '') else None,
                criado_por=current_user.id,
                status='rascunho',
            )
            db.session.add(orc)
            db.session.commit()
            flash(f'Orçamento {orc.numero} criado.', 'success')
            return redirect(url_for('orcamentos.editar', id=orc.id))
        except Exception as e:
            db.session.rollback()
            logger.exception('erro ao criar orcamento')
            flash(f'Erro ao criar: {e}', 'error')
            return redirect(url_for('orcamentos.novo'))

    clientes = Cliente.query.filter_by(admin_id=admin_id).order_by(Cliente.nome).all()
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    return render_template('orcamentos/novo.html', clientes=clientes, config=cfg)


# ───────────────────────────── EDITAR ─────────────────────────────
@orcamentos_bp.route('/<int:id>/editar', methods=['GET'])
@login_required
@admin_required
def editar(id):
    admin_id = _admin_id()
    orc = Orcamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True) \
        .order_by(Servico.nome).all()
    # Task #118: templates do tenant para o seletor de override por linha e
    # para o modal embedado de "Novo serviço" (campo Template padrão).
    templates_cronograma = (
        CronogramaTemplate.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(CronogramaTemplate.nome)
        .all()
    )
    # Calcula, por item, a composição "padrão do serviço" para detecção de
    # customização (snapshot != padrão → linha customizada).
    composicao_padrao_por_item = {}
    for it in orc.itens:
        if it.servico:
            composicao_padrao_por_item[it.id] = snapshot_from_servico(it.servico)

    # Task #31 — modelos de proposta disponíveis para seleção no momento de
    # gerar a Proposta a partir deste orçamento (modal "Escolher modelo").
    templates_proposta = (
        PropostaTemplate.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(PropostaTemplate.nome)
        .all()
    )

    # Task #63 — banner: lista obras vinculadas a este orçamento que já têm
    # Orçamento Operacional separado (edições aqui não afetam o operacional).
    from models import Obra, Proposta, ObraOrcamentoOperacional
    obras_com_operacional = (
        db.session.query(Obra)
        .join(Proposta, Proposta.id == Obra.proposta_origem_id)
        .join(ObraOrcamentoOperacional, ObraOrcamentoOperacional.obra_id == Obra.id)
        .filter(Proposta.orcamento_id == orc.id, Obra.admin_id == admin_id)
        .all()
    )

    return render_template(
        'orcamentos/editar.html',
        orcamento=orc,
        servicos=servicos,
        templates_cronograma=templates_cronograma,
        composicao_padrao_por_item=composicao_padrao_por_item,
        templates_proposta=templates_proposta,
        obras_com_operacional=obras_com_operacional,
    )


@orcamentos_bp.route('/<int:id>/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar(id):
    admin_id = _admin_id()
    orc = Orcamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    try:
        orc.titulo = (request.form.get('titulo') or orc.titulo).strip()
        orc.descricao = request.form.get('descricao') or None
        cliente_id = request.form.get('cliente_id') or None
        if cliente_id:
            cli = Cliente.query.filter_by(id=int(cliente_id), admin_id=admin_id).first()
            if not cli:
                raise ValueError('Cliente inválido')
            orc.cliente_id = cli.id
        else:
            orc.cliente_id = None
        orc.cliente_nome = (request.form.get('cliente_nome') or orc.cliente_nome or '').strip() or None
        imp_g = request.form.get('imposto_pct_global')
        mar_g = request.form.get('margem_pct_global')
        orc.imposto_pct_global = _parse_br_decimal(imp_g, '0') if imp_g not in (None, '') else None
        orc.margem_pct_global = _parse_br_decimal(mar_g, '0') if mar_g not in (None, '') else None
        recalcular_orcamento(orc)
        db.session.commit()
        flash('Orçamento atualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao atualizar orcamento')
        flash(f'Erro: {e}', 'error')
    return redirect(url_for('orcamentos.editar', id=id))


# ───────────────────────────── ITENS ─────────────────────────────
@orcamentos_bp.route('/<int:id>/itens', methods=['POST'])
@login_required
@admin_required
def adicionar_item(id):
    admin_id = _admin_id()
    orc = Orcamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    try:
        servico_id = request.form.get('servico_id') or None
        quantidade = _parse_br_decimal(request.form.get('quantidade'), '1')
        servico = None
        snap = []
        descricao = (request.form.get('descricao') or '').strip()
        unidade = (request.form.get('unidade') or 'un').strip()
        if servico_id:
            servico = Servico.query.filter_by(id=int(servico_id), admin_id=admin_id).first()
            if servico:
                snap = snapshot_from_servico(servico)
                if not descricao:
                    descricao = servico.nome
                unidade = servico.unidade_medida or unidade
        if not descricao:
            flash('Descrição obrigatória.', 'error')
            return redirect(url_for('orcamentos.editar', id=id))

        ordem = (db.session.query(db.func.coalesce(db.func.max(OrcamentoItem.ordem), 0))
                 .filter_by(orcamento_id=orc.id).scalar() or 0) + 1
        # Task #118: override de cronograma (opcional, NULL = padrão do serviço)
        override_id = _parse_template_override(
            request.form.get('cronograma_template_override_id'), admin_id
        )
        item = OrcamentoItem(
            admin_id=admin_id,
            orcamento_id=orc.id,
            ordem=ordem,
            servico_id=servico.id if servico else None,
            descricao=descricao,
            unidade=unidade,
            quantidade=quantidade,
            composicao_snapshot=snap,
            cronograma_template_override_id=override_id,
        )
        db.session.add(item)
        db.session.flush()
        recalcular_item(item, orc)
        recalcular_orcamento(orc)
        db.session.commit()
        flash('Item adicionado.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao adicionar item')
        flash(f'Erro: {e}', 'error')
    return redirect(url_for('orcamentos.editar', id=id))


@orcamentos_bp.route('/itens/<int:item_id>/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar_item(item_id):
    admin_id = _admin_id()
    item = OrcamentoItem.query.filter_by(id=item_id, admin_id=admin_id).first_or_404()
    orc = item.orcamento
    try:
        item.descricao = (request.form.get('descricao') or item.descricao).strip()
        item.unidade = (request.form.get('unidade') or item.unidade).strip()
        item.quantidade = _parse_br_decimal(request.form.get('quantidade'), '0')
        imp = request.form.get('imposto_pct')
        mar = request.form.get('margem_pct')
        item.imposto_pct = _parse_br_decimal(imp, '0') if imp not in (None, '') else None
        item.margem_pct = _parse_br_decimal(mar, '0') if mar not in (None, '') else None
        item.observacao = request.form.get('observacao') or None

        # Composição (campos paralelos)
        tipos = request.form.getlist('comp_tipo')
        nomes = request.form.getlist('comp_nome')
        unids = request.form.getlist('comp_unidade')
        coefs = request.form.getlist('comp_coeficiente')
        precos = request.form.getlist('comp_preco_unitario')
        ins_ids = request.form.getlist('comp_insumo_id')
        snap = []
        for i in range(len(nomes)):
            nm = (nomes[i] or '').strip()
            if not nm:
                continue
            try:
                snap.append({
                    'tipo': (tipos[i] if i < len(tipos) else 'MATERIAL') or 'MATERIAL',
                    'insumo_id': int(ins_ids[i]) if i < len(ins_ids) and ins_ids[i] else None,
                    'nome': nm,
                    'unidade': (unids[i] if i < len(unids) else 'un') or 'un',
                    'coeficiente': _parse_br_number(coefs[i] if i < len(coefs) else 0, 0.0),
                    'preco_unitario': _parse_br_number(precos[i] if i < len(precos) else 0, 0.0),
                    'subtotal_unitario': 0.0,
                })
            except (ValueError, IndexError):
                continue
        item.composicao_snapshot = snap
        # Task #18 — inclusos/exclusos por serviço (texto livre, 1 item/linha)
        if 'itens_inclusos' in request.form:
            item.itens_inclusos = (request.form.get('itens_inclusos') or '').strip() or None
        if 'itens_exclusos' in request.form:
            item.itens_exclusos = (request.form.get('itens_exclusos') or '').strip() or None
        # Task #118: override de cronograma na linha
        if 'cronograma_template_override_id' in request.form:
            item.cronograma_template_override_id = _parse_template_override(
                request.form.get('cronograma_template_override_id'), admin_id
            )
        recalcular_item(item, orc)
        recalcular_orcamento(orc)
        db.session.commit()
        flash('Item atualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao atualizar item')
        flash(f'Erro: {e}', 'error')
    return redirect(url_for('orcamentos.editar', id=orc.id))


@orcamentos_bp.route('/itens/<int:item_id>/reset-composicao', methods=['POST'])
@login_required
@admin_required
def reset_composicao(item_id):
    """Task #118: reverte composicao_snapshot do item para a composição padrão
    do serviço vinculado no Catálogo. Não toca no Servico nem em outros itens.
    """
    admin_id = _admin_id()
    item = OrcamentoItem.query.filter_by(id=item_id, admin_id=admin_id).first_or_404()
    if not item.servico_id or not item.servico:
        flash('Este item não está vinculado a um serviço do catálogo.', 'warning')
        return redirect(url_for('orcamentos.editar', id=item.orcamento_id))
    try:
        item.composicao_snapshot = snapshot_from_servico(item.servico)
        recalcular_item(item, item.orcamento)
        recalcular_orcamento(item.orcamento)
        db.session.commit()
        flash('Composição revertida ao padrão do serviço.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao resetar composicao')
        flash(f'Erro: {e}', 'error')
    return redirect(url_for('orcamentos.editar', id=item.orcamento_id))


@orcamentos_bp.route('/itens/<int:item_id>/remover', methods=['POST'])
@login_required
@admin_required
def remover_item(item_id):
    admin_id = _admin_id()
    item = OrcamentoItem.query.filter_by(id=item_id, admin_id=admin_id).first_or_404()
    orc_id = item.orcamento_id
    orc = item.orcamento
    db.session.delete(item)
    db.session.flush()
    recalcular_orcamento(orc)
    db.session.commit()
    flash('Item removido.', 'success')
    return redirect(url_for('orcamentos.editar', id=orc_id))


# ───────────────────────────── EXCLUIR ─────────────────────────────
@orcamentos_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir(id):
    admin_id = _admin_id()
    orc = Orcamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    db.session.delete(orc)
    db.session.commit()
    flash('Orçamento excluído.', 'success')
    return redirect(url_for('orcamentos.listar'))


# ───────────────────── DUPLICAR ─────────────────────
@orcamentos_bp.route('/<int:id>/duplicar', methods=['POST'])
@login_required
@admin_required
def duplicar(id):
    """Cria uma cópia integral do orçamento (rev) preservando composições e overrides.

    Útil para gerar revisões V2/V3 antes de uma nova proposta.
    """
    admin_id = _admin_id()
    orc = Orcamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    try:
        novo = Orcamento(
            admin_id=admin_id,
            numero=_gerar_numero(admin_id),
            titulo=f"{orc.titulo} (cópia)",
            descricao=orc.descricao,
            cliente_id=orc.cliente_id,
            cliente_nome=orc.cliente_nome,
            imposto_pct_global=orc.imposto_pct_global,
            margem_pct_global=orc.margem_pct_global,
            criado_por=current_user.id,
            status='rascunho',
        )
        db.session.add(novo)
        db.session.flush()

        for it in orc.itens:
            novo_it = OrcamentoItem(
                admin_id=admin_id,
                orcamento_id=novo.id,
                ordem=it.ordem,
                servico_id=it.servico_id,
                descricao=it.descricao,
                unidade=it.unidade,
                quantidade=it.quantidade,
                imposto_pct=it.imposto_pct,
                margem_pct=it.margem_pct,
                composicao_snapshot=it.composicao_snapshot or [],
                observacao=it.observacao,
                cronograma_template_override_id=it.cronograma_template_override_id,
                # Task #18: copia inclusos/exclusos por serviço na revisão
                itens_inclusos=it.itens_inclusos,
                itens_exclusos=it.itens_exclusos,
            )
            db.session.add(novo_it)
        db.session.flush()
        recalcular_orcamento(novo)
        db.session.commit()
        flash(f'Orçamento duplicado como {novo.numero}.', 'success')
        return redirect(url_for('orcamentos.editar', id=novo.id))
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao duplicar orcamento')
        flash(f'Erro ao duplicar: {e}', 'error')
        return redirect(url_for('orcamentos.editar', id=id))


# ───────────────────── GERAR PROPOSTA ─────────────────────
@orcamentos_bp.route('/<int:id>/gerar-proposta', methods=['POST'])
@login_required
@admin_required
def gerar_proposta(id):
    """Cria uma Proposta cliente-facing a partir do orçamento.

    Apenas descricao/quantidade/unidade/preco_venda são propagados.
    Custos, composição, margem e imposto NÃO são copiados para a Proposta.

    Task #31 — aceita ``template_id`` (PropostaTemplate do tenant) no form
    para pré-popular cláusulas/condições. Quando vem de template, marca
    todos os campos copiados como ``pendentes de revisão`` (cláusulas com
    ``revisado_em=NULL`` e lista ``campos_pendentes_revisao``); o admin
    precisa revisar/marcar antes de poder enviar.
    """
    admin_id = _admin_id()
    orc = Orcamento.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    # Task #31 — template opcional escolhido no modal "Gerar Proposta".
    template_id_raw = (request.form.get('template_id') or '').strip()
    template = None
    if template_id_raw:
        try:
            template_id = int(template_id_raw)
            template = PropostaTemplate.query.filter_by(
                id=template_id, admin_id=admin_id, ativo=True
            ).first()
            if not template:
                flash('Modelo de proposta inválido ou desativado.', 'warning')
        except (TypeError, ValueError):
            template = None

    try:
        recalcular_orcamento(orc)

        proposta = Proposta()
        proposta.titulo = orc.titulo
        proposta.descricao = orc.descricao
        proposta.cliente_id = orc.cliente_id
        proposta.cliente_nome = orc.cliente_nome or 'Cliente'
        proposta.admin_id = admin_id
        proposta.criado_por = current_user.id
        proposta.status = 'rascunho'
        proposta.valor_total = orc.venda_total or 0
        proposta.orcamento_id = orc.id  # vínculo 1→N (Task #115 v2)
        proposta.versao = 1
        # Task #31 — aplicar campos numéricos / textuais do template (se
        # houver). Em paralelo, registra na lista de revisão pendente.
        campos_pendentes = []
        if template:
            proposta.proposta_template_id = template.id
            if template.prazo_entrega_dias:
                proposta.prazo_entrega_dias = template.prazo_entrega_dias
                campos_pendentes.append('prazo_entrega_dias')
            if template.validade_dias:
                proposta.validade_dias = template.validade_dias
                campos_pendentes.append('validade_dias')
            if template.percentual_nota_fiscal is not None:
                proposta.percentual_nota_fiscal = template.percentual_nota_fiscal
            if template.itens_inclusos:
                # Itens inclusos no template ficam como string com '\n'.
                # Proposta.itens_inclusos é JSON (list[str]).
                _inc = [
                    ln.strip() for ln in str(template.itens_inclusos).splitlines()
                    if ln and ln.strip()
                ]
                if _inc:
                    proposta.itens_inclusos = _inc
                    campos_pendentes.append('itens_inclusos')
            if template.itens_exclusos:
                _exc = [
                    ln.strip() for ln in str(template.itens_exclusos).splitlines()
                    if ln and ln.strip()
                ]
                if _exc:
                    proposta.itens_exclusos = _exc
                    campos_pendentes.append('itens_exclusos')
        proposta.campos_pendentes_revisao = campos_pendentes

        db.session.add(proposta)
        db.session.flush()

        # Task #31 — copiar cláusulas do template (se houver). Usa o helper
        # canônico de propostas_consolidated (skip "Condições de Entrega" /
        # "Validade da Proposta" — esses são derivados de campos numéricos).
        if template:
            from propostas_consolidated import (
                _copiar_clausulas_template_para_proposta,
            )
            n_copiadas = _copiar_clausulas_template_para_proposta(
                template, proposta, admin_id
            )
            try:
                template.uso_contador = (template.uso_contador or 0) + 1
            except Exception:
                pass
            # Garante NULL para tudo vindo de template (default já é,
            # mas explicitar evita ambiguidade pós-flush).
            for cl in proposta.clausulas:
                cl.revisado_em = None

            # Task #31 — Carry-over de campos textuais do PropostaTemplate
            # que NÃO estão modelados como cláusulas configuráveis (legacy
            # / texto livre). Cada um vira uma cláusula extra na proposta,
            # também marcada como pendente de revisão. Pula títulos que já
            # vieram via _copiar_clausulas_template_para_proposta para não
            # duplicar (heurística por título normalizado).
            from propostas_consolidated import _normalizar_titulo_clausula
            from models import PropostaClausula as _PCl
            ja_titulos = {
                _normalizar_titulo_clausula(c.titulo or '')
                for c in proposta.clausulas
            }
            ordem_base = (max(
                (c.ordem or 0) for c in proposta.clausulas
            ) if proposta.clausulas else 0) + 1
            extras_textuais = [
                ('Apresentação', getattr(template, 'texto_apresentacao', None)),
                ('Objeto', getattr(template, 'secao_objeto', None)),
                ('Condições de Pagamento', getattr(template, 'condicoes_pagamento', None)),
                ('Garantias', getattr(template, 'garantias', None)),
                ('Considerações Gerais', getattr(template, 'consideracoes_gerais', None)),
                ('Condições', getattr(template, 'condicoes', None)),
            ]
            for titulo, texto in extras_textuais:
                if not (texto or '').strip():
                    continue
                if _normalizar_titulo_clausula(titulo) in ja_titulos:
                    continue
                db.session.add(_PCl(
                    proposta_id=proposta.id,
                    admin_id=admin_id,
                    titulo=titulo[:200],
                    texto=str(texto).strip(),
                    ordem=ordem_base,
                    revisado_em=None,
                ))
                ordem_base += 1
                ja_titulos.add(_normalizar_titulo_clausula(titulo))

        for idx, it in enumerate(orc.itens, start=1):
            pi = PropostaItem(
                admin_id=admin_id,
                proposta_id=proposta.id,
                item_numero=idx,
                ordem=idx,
                descricao=it.descricao,
                quantidade=it.quantidade,
                unidade=it.unidade,
                preco_unitario=it.preco_venda_unitario or 0,
                subtotal=it.venda_total or 0,
                # vínculo com catálogo preservado para cronograma (Task #102)
                servico_id=it.servico_id,
                quantidade_medida=it.quantidade,
                # Task #118: propaga override de cronograma e snapshot de composição
                # para a Proposta. Override toma precedência sobre o template padrão
                # do serviço na materialização. composicao_snapshot preserva eventuais
                # add/remove/coeficientes feitos na linha do orçamento.
                cronograma_template_override_id=it.cronograma_template_override_id,
                composicao_snapshot=it.composicao_snapshot or [],
                # Task #18: propaga inclusos/exclusos por serviço
                itens_inclusos=it.itens_inclusos,
                itens_exclusos=it.itens_exclusos,
            )
            db.session.add(pi)

        db.session.add(PropostaHistorico(
            proposta_id=proposta.id,
            usuario_id=current_user.id,
            acao='criada',
            observacao=f'Proposta gerada do Orçamento {orc.numero}',
            admin_id=admin_id,
        ))

        # Mantém referência informativa da última proposta gerada,
        # mas NÃO bloqueia gerar novas (1 orçamento → N propostas).
        orc.ultima_proposta_id = proposta.id
        if orc.status == 'rascunho':
            orc.status = 'fechado'
        db.session.commit()
        # Task #31 — após gerar a proposta, sempre cair na tela de
        # revisão (editar) — é onde o admin confere/marca cláusulas e
        # campos vindos do modelo antes de enviar ao cliente. A tela
        # de visualização permanece acessível pelo botão "Visualizar".
        if template:
            flash(
                f'Proposta {proposta.numero} gerada a partir do modelo '
                f'"{template.nome}". Revise os itens marcados como '
                'pendentes antes de enviar ao cliente.',
                'success',
            )
        else:
            flash(
                f'Proposta {proposta.numero} gerada a partir do orçamento. '
                'Revise antes de enviar.',
                'success',
            )
        return redirect(url_for('propostas.editar', id=proposta.id))
    except Exception as e:
        db.session.rollback()
        logger.exception('erro ao gerar proposta do orcamento')
        flash(f'Erro ao gerar proposta: {e}', 'error')
        return redirect(url_for('orcamentos.editar', id=id))


# ───────────────────── API: composição prévia do serviço ─────────────────────
@orcamentos_bp.route('/api/servicos/<int:servico_id>/composicao')
@login_required
@admin_required
def api_composicao_servico(servico_id):
    admin_id = _admin_id()
    svc = Servico.query.filter_by(id=servico_id, admin_id=admin_id).first_or_404()
    return jsonify({
        'servico_id': svc.id,
        'nome': svc.nome,
        'unidade': svc.unidade_medida,
        'imposto_pct': float(svc.imposto_pct) if svc.imposto_pct is not None else None,
        'margem_pct': float(svc.margem_lucro_pct) if svc.margem_lucro_pct is not None else None,
        'composicao': snapshot_from_servico(svc),
    })
