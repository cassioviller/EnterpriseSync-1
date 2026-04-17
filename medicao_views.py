import logging
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for, make_response
from flask_login import current_user, login_required

from app import db
from models import (
    Obra, MedicaoObra, MedicaoObraItem, ItemMedicaoComercial,
    ItemMedicaoCronogramaTarefa, TarefaCronograma, ConfiguracaoEmpresa,
    ContaReceber,
)

logger = logging.getLogger(__name__)

medicao_bp = Blueprint('medicao', __name__)


def _admin_id():
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


def _check_v2():
    from utils.tenant import is_v2_active
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


def _calc_realtime_perc(item):
    from services.medicao_service import calcular_percentual_item
    return float(calcular_percentual_item(item))


@medicao_bp.route('/obras/<int:obra_id>/medicao/')
@medicao_bp.route('/obras/<int:obra_id>/medicao')
@medicao_bp.route('/medicao/obra/<int:obra_id>')
@login_required
def gestao_itens(obra_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    itens = ItemMedicaoComercial.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).order_by(ItemMedicaoComercial.id).all()

    tarefas = TarefaCronograma.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).order_by(TarefaCronograma.ordem).all()

    medicoes = MedicaoObra.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).order_by(MedicaoObra.numero.desc()).all()

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()

    # Task #82: catálogo de serviços para o select do modal "Novo Item"
    from models import Servico
    servicos_catalogo = Servico.query.filter_by(
        admin_id=admin_id, ativo=True
    ).order_by(Servico.nome).all()

    valor_contrato = float(obra.valor_contrato or 0)
    soma_itens = sum(float(i.valor_comercial or 0) for i in itens)
    saldo = valor_contrato - soma_itens

    item_realtime_perc = {}
    item_peso_total = {}
    for item in itens:
        item_realtime_perc[item.id] = _calc_realtime_perc(item)
        vinc = ItemMedicaoCronogramaTarefa.query.filter_by(item_medicao_id=item.id).all()
        item_peso_total[item.id] = float(sum(Decimal(str(v.peso)) for v in vinc))

    medicao_contas = {}
    for m in medicoes:
        if m.conta_receber_id:
            cr = ContaReceber.query.get(m.conta_receber_id)
            if cr:
                medicao_contas[m.id] = cr

    return render_template(
        'medicao/gestao_itens.html',
        obra=obra,
        itens=itens,
        tarefas=tarefas,
        medicoes=medicoes,
        config=config,
        valor_contrato=valor_contrato,
        soma_itens=soma_itens,
        saldo=saldo,
        item_realtime_perc=item_realtime_perc,
        item_peso_total=item_peso_total,
        medicao_contas=medicao_contas,
        servicos_catalogo=servicos_catalogo,
    )


@medicao_bp.route('/obras/<int:obra_id>/medicao/itens', methods=['GET'])
@login_required
def listar_itens(obra_id):
    admin_id = _admin_id()
    Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    itens = ItemMedicaoComercial.query.filter_by(
        obra_id=obra_id, admin_id=admin_id
    ).order_by(ItemMedicaoComercial.id).all()
    result = []
    for item in itens:
        vinc = ItemMedicaoCronogramaTarefa.query.filter_by(item_medicao_id=item.id).all()
        result.append({
            'id': item.id,
            'nome': item.nome,
            'valor_comercial': float(item.valor_comercial or 0),
            'percentual_executado_acumulado': float(item.percentual_executado_acumulado or 0),
            'status': item.status,
            'tarefas': [{'id': v.id, 'tarefa_id': v.cronograma_tarefa_id, 'peso': float(v.peso)} for v in vinc],
        })
    return jsonify(result)


@medicao_bp.route('/obras/<int:obra_id>/medicao/itens', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/item', methods=['POST'])
@login_required
def criar_item(obra_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    nome = request.form.get('nome', '').strip()
    try:
        valor = Decimal((request.form.get('valor_comercial') or '0').replace(',', '.'))
    except Exception:
        valor = Decimal('0')

    # Task #82 — vínculo opcional com catálogo de serviços
    servico_id_raw = (request.form.get('servico_id') or '').strip()
    servico_id = None
    servico_obj = None
    if servico_id_raw:
        try:
            from models import Servico
            sid = int(servico_id_raw)
            servico_obj = Servico.query.filter_by(id=sid, admin_id=admin_id).first()
            if servico_obj:
                servico_id = sid
        except (ValueError, TypeError):
            servico_id = None
    quantidade_raw = (request.form.get('quantidade') or '').strip().replace(',', '.')
    quantidade = None
    if quantidade_raw:
        try:
            quantidade = Decimal(quantidade_raw)
        except Exception:
            quantidade = None

    # Task #82: se serviço + quantidade vieram e valor_comercial não foi preenchido,
    # calcular automaticamente valor_comercial = quantidade × preco_venda_unitario.
    if valor <= 0 and servico_obj is not None and quantidade and quantidade > 0:
        preco = Decimal(str(servico_obj.preco_venda_unitario or 0))
        if preco > 0:
            valor = (quantidade * preco).quantize(Decimal('0.01'))
    # Se ainda sem nome e veio serviço, herdar nome do serviço.
    if not nome and servico_obj is not None:
        nome = servico_obj.nome

    if not nome or valor <= 0:
        flash('Nome e valor comercial são obrigatórios (ou informe serviço + quantidade com preço de venda).', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    item = ItemMedicaoComercial(
        admin_id=admin_id,
        obra_id=obra_id,
        nome=nome,
        valor_comercial=valor,
        servico_id=servico_id,
        quantidade=quantidade,
    )
    db.session.add(item)
    db.session.commit()
    flash(f'Item "{nome}" criado com sucesso.', 'success')
    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/itens/<int:item_id>', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/item/<int:item_id>/editar', methods=['POST'])
@login_required
def editar_item(obra_id, item_id):
    admin_id = _admin_id()
    item = ItemMedicaoComercial.query.filter_by(
        id=item_id, obra_id=obra_id, admin_id=admin_id
    ).first_or_404()

    nome = request.form.get('nome', '').strip()
    try:
        valor = Decimal(request.form.get('valor_comercial', '0').replace(',', '.'))
    except Exception:
        flash('Valor comercial inválido.', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    if nome:
        item.nome = nome
    if valor > 0:
        item.valor_comercial = valor

    # Task #82 — atualização opcional do vínculo com catálogo
    if 'servico_id' in request.form:
        servico_id_raw = (request.form.get('servico_id') or '').strip()
        if not servico_id_raw:
            item.servico_id = None
        else:
            try:
                from models import Servico
                sid = int(servico_id_raw)
                if Servico.query.filter_by(id=sid, admin_id=admin_id).first():
                    item.servico_id = sid
            except (ValueError, TypeError):
                pass
    if 'quantidade' in request.form:
        q_raw = (request.form.get('quantidade') or '').strip().replace(',', '.')
        if not q_raw:
            item.quantidade = None
        else:
            try:
                item.quantidade = Decimal(q_raw)
            except Exception:
                pass

    db.session.commit()
    flash('Item atualizado.', 'success')
    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/itens/<int:item_id>', methods=['DELETE'])
@medicao_bp.route('/obras/<int:obra_id>/medicao/itens/<int:item_id>/excluir', methods=['POST', 'DELETE'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/item/<int:item_id>/excluir', methods=['POST', 'DELETE'])
@login_required
def excluir_item(obra_id, item_id):
    admin_id = _admin_id()
    item = ItemMedicaoComercial.query.filter_by(
        id=item_id, obra_id=obra_id, admin_id=admin_id
    ).first_or_404()

    db.session.delete(item)
    db.session.commit()
    if request.method == 'DELETE':
        return jsonify({'status': 'ok'}), 200
    flash('Item excluído.', 'success')
    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/itens/<int:item_id>/tarefas', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/item/<int:item_id>/vincular', methods=['POST'])
@login_required
def vincular_tarefa(obra_id, item_id):
    admin_id = _admin_id()
    item = ItemMedicaoComercial.query.filter_by(
        id=item_id, obra_id=obra_id, admin_id=admin_id
    ).first_or_404()

    tarefa_id = request.form.get('tarefa_id', type=int)
    try:
        peso = Decimal(request.form.get('peso', '0').replace(',', '.'))
    except Exception:
        peso = Decimal('0')

    if not tarefa_id or peso <= 0:
        flash('Tarefa e peso são obrigatórios.', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    if peso > Decimal('100'):
        flash('Peso não pode exceder 100%.', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id
    ).first()
    if not tarefa:
        flash('Tarefa não encontrada.', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    existente = ItemMedicaoCronogramaTarefa.query.filter_by(
        item_medicao_id=item_id, cronograma_tarefa_id=tarefa_id
    ).first()

    outros_pesos = sum(
        Decimal(str(v.peso)) for v in
        ItemMedicaoCronogramaTarefa.query.filter_by(item_medicao_id=item_id).all()
        if v.cronograma_tarefa_id != tarefa_id
    )
    if outros_pesos + peso > Decimal('100'):
        flash(f'A soma dos pesos excederia 100% (atual: {float(outros_pesos):.0f}% + {float(peso):.0f}% = {float(outros_pesos + peso):.0f}%).', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    if existente:
        existente.peso = peso
    else:
        vinculo = ItemMedicaoCronogramaTarefa(
            item_medicao_id=item_id,
            cronograma_tarefa_id=tarefa_id,
            peso=peso,
            admin_id=admin_id,
        )
        db.session.add(vinculo)

    db.session.commit()
    flash('Tarefa vinculada ao item.', 'success')
    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/itens/<int:item_id>/tarefas/<int:vinculo_id>/excluir', methods=['POST', 'DELETE'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/item/<int:item_id>/desvincular/<int:vinculo_id>', methods=['POST', 'DELETE'])
@login_required
def desvincular_tarefa(obra_id, item_id, vinculo_id):
    admin_id = _admin_id()
    ItemMedicaoComercial.query.filter_by(
        id=item_id, obra_id=obra_id, admin_id=admin_id
    ).first_or_404()

    vinculo = ItemMedicaoCronogramaTarefa.query.get(vinculo_id)
    if vinculo and vinculo.item_medicao_id == item_id:
        db.session.delete(vinculo)
        db.session.commit()
        if request.method == 'DELETE':
            return jsonify({'status': 'ok'}), 200
        flash('Tarefa desvinculada.', 'success')

    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/config', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/config', methods=['POST'])
@login_required
def config_obra_medicao(obra_id):
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    data_inicio = request.form.get('data_inicio_medicao')
    valor_entrada = request.form.get('valor_entrada', '0').replace(',', '.')
    data_entrada = request.form.get('data_entrada')

    if data_inicio:
        obra.data_inicio_medicao = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    try:
        obra.valor_entrada = Decimal(valor_entrada)
    except Exception:
        pass
    if data_entrada:
        obra.data_entrada = datetime.strptime(data_entrada, '%Y-%m-%d').date()

    db.session.commit()
    flash('Configurações de medição atualizadas.', 'success')
    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/fechar', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/gerar', methods=['POST'])
@login_required
def gerar_medicao(obra_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    periodo_inicio = request.form.get('periodo_inicio')
    periodo_fim = request.form.get('periodo_fim')
    obs = request.form.get('observacoes', '').strip()

    p_ini = None
    p_fim = None
    if periodo_inicio and periodo_fim:
        try:
            p_ini = datetime.strptime(periodo_inicio, '%Y-%m-%d').date()
            p_fim = datetime.strptime(periodo_fim, '%Y-%m-%d').date()
        except Exception:
            pass

    from services.medicao_service import gerar_medicao_quinzenal
    medicao, erro = gerar_medicao_quinzenal(obra_id, admin_id, p_ini, p_fim, obs or None)

    if erro:
        flash(f'Erro ao gerar medição: {erro}', 'danger')
    else:
        flash(f'Medição #{medicao.numero:03d} gerada com sucesso! Conta a receber criada automaticamente.', 'success')

    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/<int:medicao_id>/aprovar', methods=['POST'])
@medicao_bp.route('/medicao/obra/<int:obra_id>/fechar/<int:medicao_id>', methods=['POST'])
@login_required
def fechar(obra_id, medicao_id):
    admin_id = _admin_id()
    from services.medicao_service import fechar_medicao
    medicao, erro = fechar_medicao(medicao_id, admin_id)

    if erro:
        flash(f'Erro: {erro}', 'danger')
    else:
        flash(f'Medição #{medicao.numero:03d} aprovada.', 'success')

    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))


@medicao_bp.route('/obras/<int:obra_id>/medicao/<int:medicao_id>/pdf')
@medicao_bp.route('/medicao/obra/<int:obra_id>/pdf/<int:medicao_id>')
@medicao_bp.route('/medicao/<int:medicao_id>/pdf')
@login_required
def pdf_extrato(obra_id=None, medicao_id=None):
    admin_id = _admin_id()
    from services.medicao_service import gerar_pdf_extrato_medicao
    buf = gerar_pdf_extrato_medicao(medicao_id, admin_id)
    if not buf:
        abort(404)

    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=medicao_{medicao_id:03d}.pdf'
    return response


@medicao_bp.route('/medicao/portal/pdf/<int:medicao_id>')
def portal_pdf_extrato(medicao_id):
    token = request.args.get('token', '')
    if not token:
        abort(403)

    from models import Obra as ObraModel
    obra = ObraModel.query.filter_by(token_cliente=token, portal_ativo=True).first()
    if not obra:
        abort(403)

    medicao = MedicaoObra.query.filter_by(id=medicao_id, obra_id=obra.id).first()
    if not medicao:
        abort(404)

    from services.medicao_service import gerar_pdf_extrato_medicao
    buf = gerar_pdf_extrato_medicao(medicao_id, medicao.admin_id)
    if not buf:
        abort(404)

    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=medicao_{medicao_id:03d}.pdf'
    return response
