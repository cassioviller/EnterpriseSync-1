"""
Reembolsos V2 — CRUD completo de reembolsos para funcionários
Blueprint: /reembolsos
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from datetime import datetime, date
from decimal import Decimal
import os, uuid
from sqlalchemy import func as sa_func
from app import db
from models import ReembolsoFuncionario, Funcionario, Obra, GestaoCustoPai, GestaoCustoFilho
from multitenant_helper import get_admin_id
from utils.tenant import is_v2_active
from utils.financeiro_integration import registrar_custo_automatico
import logging

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'webp'}
CATEGORIAS = [
    ('alimentacao', 'Alimentação'),
    ('transporte', 'Transporte'),
    ('hospedagem', 'Hospedagem'),
    ('equipamentos', 'Equipamentos'),
    ('outros', 'Outros'),
]

logger = logging.getLogger(__name__)

reembolso_bp = Blueprint('reembolso', __name__, url_prefix='/reembolsos')


def _guard():
    if not is_v2_active():
        flash('Este módulo está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main_bp.dashboard'))
    return None


# ──────────────────────────────────────────────────────────
# LISTAR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/')
@login_required
def index():
    g = _guard()
    if g:
        return g

    admin_id = get_admin_id()

    # Filtros
    filtro_status = request.args.get('status', '')
    func_id = request.args.get('funcionario_id', type=int)
    obra_id = request.args.get('obra_id', type=int)

    q = ReembolsoFuncionario.query.filter_by(admin_id=admin_id)
    if func_id:
        q = q.filter_by(funcionario_id=func_id)
    if obra_id:
        q = q.filter_by(obra_id=obra_id)

    reembolsos_raw = q.order_by(ReembolsoFuncionario.data_despesa.desc()).all()

    # Buscar status do GestaoCustoPai para todos os reembolsos (single query)
    pai_ids = [r.gestao_custo_pai_id or r.origem_id for r in reembolsos_raw
               if (r.gestao_custo_pai_id or (r.origem_tabela == 'gestao_custo_pai' and r.origem_id))]
    pai_ids = list(filter(None, pai_ids))
    status_map = {}
    if pai_ids:
        gcps = GestaoCustoPai.query.filter(
            GestaoCustoPai.id.in_(pai_ids),
            GestaoCustoPai.admin_id == admin_id,
        ).all()
        status_map = {g.id: g.status for g in gcps}

    # Injetar gestao_status e aplicar filtro de status
    reembolsos = []
    for r in reembolsos_raw:
        pid = r.gestao_custo_pai_id or (r.origem_id if r.origem_tabela == 'gestao_custo_pai' else None)
        r.gestao_status = status_map.get(pid, 'PENDENTE') if pid else 'PENDENTE'
        if filtro_status and r.gestao_status != filtro_status.upper():
            continue
        reembolsos.append(r)

    total_valor = sum(float(r.valor) for r in reembolsos)

    funcionarios = (Funcionario.query
                    .filter_by(admin_id=admin_id, ativo=True)
                    .order_by(Funcionario.nome).all())
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    STATUS_OPCOES = [
        ('', '— Todos os status —'),
        ('PENDENTE', 'Pendente'),
        ('SOLICITADO', 'Solicitado'),
        ('AUTORIZADO', 'Autorizado'),
        ('PAGO', 'Pago'),
    ]

    return render_template(
        'reembolsos/index.html',
        reembolsos=reembolsos,
        funcionarios=funcionarios,
        obras=obras,
        total_valor=total_valor,
        filtro_func=func_id,
        filtro_obra=obra_id,
        filtro_status=filtro_status,
        status_opcoes=STATUS_OPCOES,
    )


# ──────────────────────────────────────────────────────────
# CRIAR
# ──────────────────────────────────────────────────────────
def _salvar_comprovante(arquivo):
    """Salva comprovante e retorna URL relativa ou None."""
    if not arquivo or arquivo.filename == '':
        return None
    ext = arquivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'comprovantes')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    arquivo.save(os.path.join(upload_dir, filename))
    return f"/static/uploads/comprovantes/{filename}"


@reembolso_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    g = _guard()
    if g:
        return g

    admin_id = get_admin_id()
    funcionarios = (Funcionario.query
                    .filter_by(admin_id=admin_id, ativo=True)
                    .order_by(Funcionario.nome).all())
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    if request.method == 'POST':
        try:
            func_id = request.form.get('funcionario_id', type=int)
            if not func_id:
                flash('Selecione um funcionário.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       categorias=CATEGORIAS, reembolso=None)

            # Validação multi-tenant: garante que funcionario_id pertence ao mesmo admin
            funcionario = Funcionario.query.filter_by(id=func_id, admin_id=admin_id).first()
            if not funcionario:
                flash('Funcionário inválido.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       categorias=CATEGORIAS, reembolso=None)

            valor_str = request.form.get('valor', '0').replace(',', '.')
            valor = Decimal(valor_str)
            if valor <= 0:
                flash('Valor deve ser maior que zero.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       categorias=CATEGORIAS, reembolso=None)

            data_str = request.form.get('data_despesa')
            data_despesa = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()

            descricao = request.form.get('descricao', '').strip()
            if not descricao:
                flash('Descrição é obrigatória.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       categorias=CATEGORIAS, reembolso=None)

            categoria = request.form.get('categoria', 'outros')
            if categoria not in [k for k, _ in CATEGORIAS]:
                categoria = 'outros'

            obra_id_raw = request.form.get('obra_id', type=int)
            obra_id = None
            if obra_id_raw:
                obra = Obra.query.filter_by(id=obra_id_raw, admin_id=admin_id).first()
                if obra:
                    obra_id = obra_id_raw

            comprovante_url = _salvar_comprovante(request.files.get('comprovante'))

            reembolso = ReembolsoFuncionario(
                funcionario_id=func_id,
                valor=valor,
                data_despesa=data_despesa,
                descricao=descricao,
                categoria=categoria,
                obra_id=obra_id,
                comprovante_url=comprovante_url,
                admin_id=admin_id,
            )
            db.session.add(reembolso)
            db.session.flush()  # Gera reembolso.id

            # Integrar ao Gestão de Custos V2 via registrar_custo_automatico()
            filho = registrar_custo_automatico(
                admin_id=admin_id,
                tipo_categoria='REEMBOLSO',
                entidade_nome=funcionario.nome,
                entidade_id=func_id,
                data=data_despesa,
                descricao=f'Reembolso ({categoria}): {descricao}',
                valor=valor,
                obra_id=obra_id,
                origem_tabela='reembolso_funcionario',
                origem_id=reembolso.id,
            )

            if not filho:
                db.session.rollback()
                flash('Erro ao integrar com Gestão de Custos V2. Reembolso não salvo.', 'danger')
                return redirect(url_for('reembolso.novo'))

            # Persistir referência ao GestaoCustoPai para consulta de status
            reembolso.gestao_custo_pai_id = filho.pai_id
            reembolso.origem_tabela = 'gestao_custo_pai'
            reembolso.origem_id = filho.pai_id

            db.session.commit()
            flash('Reembolso registrado com sucesso!', 'success')
            return redirect(url_for('reembolso.index'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Criar reembolso: {e}")
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('reembolsos/form.html',
                           funcionarios=funcionarios, obras=obras,
                           categorias=CATEGORIAS, reembolso=None)


# ──────────────────────────────────────────────────────────
# EDITAR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/<int:reembolso_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(reembolso_id):
    g = _guard()
    if g:
        return g

    admin_id = get_admin_id()
    reembolso = ReembolsoFuncionario.query.filter_by(id=reembolso_id, admin_id=admin_id).first_or_404()

    funcionarios = (Funcionario.query
                    .filter_by(admin_id=admin_id, ativo=True)
                    .order_by(Funcionario.nome).all())
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    if request.method == 'POST':
        try:
            valor_str = request.form.get('valor', '0').replace(',', '.')
            valor = Decimal(valor_str)
            if valor <= 0:
                flash('Valor deve ser maior que zero.', 'danger')
                return render_template('reembolsos/form.html',
                                       funcionarios=funcionarios, obras=obras,
                                       categorias=CATEGORIAS, reembolso=reembolso)

            data_str = request.form.get('data_despesa')
            reembolso.data_despesa = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else reembolso.data_despesa
            reembolso.valor = valor
            reembolso.descricao = request.form.get('descricao', '').strip()

            cat = request.form.get('categoria', 'outros')
            reembolso.categoria = cat if cat in [k for k, _ in CATEGORIAS] else 'outros'

            obra_id_raw = request.form.get('obra_id', type=int)
            reembolso.obra_id = None
            if obra_id_raw:
                obra = Obra.query.filter_by(id=obra_id_raw, admin_id=admin_id).first()
                if obra:
                    reembolso.obra_id = obra_id_raw

            # Upload de novo comprovante (substitui o anterior se enviado)
            novo_comp = _salvar_comprovante(request.files.get('comprovante'))
            if novo_comp:
                reembolso.comprovante_url = novo_comp

            # Atualizar GestaoCustoPai associado se existir.
            #
            # O `GestaoCustoPai` é COMPARTILHADO entre os reembolsos do
            # mesmo funcionário (`models.py:7203`, cascade
            # `all, delete-orphan` em `itens`): sobrescrever
            # `gcp.valor_total = valor` com o valor de UM reembolso apagava
            # os irmãos do total. Disciplina copiada de
            # `transporte_views.py:565-579` — atualiza o FILHO deste
            # reembolso e recalcula o total do pai pela SOMA dos filhos.
            if reembolso.origem_tabela == 'gestao_custo_pai' and reembolso.origem_id:
                gcp = GestaoCustoPai.query.filter_by(id=reembolso.origem_id, admin_id=admin_id).first()
                if gcp and gcp.status == 'PENDENTE':
                    filho = GestaoCustoFilho.query.filter_by(
                        pai_id=gcp.id, origem_tabela='reembolso_funcionario',
                        origem_id=reembolso.id, admin_id=admin_id).first()
                    if filho:
                        # Só o valor: `obra_id`/`centro_custo_id` tem check
                        # constraint de destino obrigatório
                        # (`models.py:7261`) e não é regravado aqui — mudar
                        # a obra do filho é decisão de
                        # `services/destino_custo.py`, fora do escopo desta
                        # correção.
                        filho.valor = valor
                        filho.descricao = f'Reembolso ({reembolso.categoria}): {reembolso.descricao}'
                        filho.data_referencia = reembolso.data_despesa

                    novo_total = db.session.query(
                        sa_func.coalesce(sa_func.sum(GestaoCustoFilho.valor), 0)
                    ).filter(GestaoCustoFilho.pai_id == gcp.id).scalar()
                    gcp.valor_total = Decimal(str(novo_total))
                    gcp.valor_solicitado = gcp.valor_total
                    gcp.observacoes = f'Reembolso ({reembolso.categoria}): {reembolso.descricao}'

            db.session.commit()
            flash('Reembolso atualizado com sucesso!', 'success')
            return redirect(url_for('reembolso.index'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Editar reembolso {reembolso_id}: {e}")
            flash(f'Erro ao atualizar: {e}', 'danger')

    return render_template('reembolsos/form.html',
                           funcionarios=funcionarios, obras=obras,
                           categorias=CATEGORIAS, reembolso=reembolso)


# ──────────────────────────────────────────────────────────
# EXCLUIR
# ──────────────────────────────────────────────────────────
@reembolso_bp.route('/<int:reembolso_id>/excluir', methods=['POST'])
@login_required
def excluir(reembolso_id):
    g = _guard()
    if g:
        return redirect(url_for('reembolso.index'))

    admin_id = get_admin_id()
    reembolso = ReembolsoFuncionario.query.filter_by(id=reembolso_id, admin_id=admin_id).first_or_404()

    try:
        # O `GestaoCustoPai` é COMPARTILHADO entre os reembolsos do mesmo
        # funcionário, e `GestaoCustoPai.itens` é `cascade='all,
        # delete-orphan'` (`models.py:7203`): apagá-lo levava junto os
        # filhos de TODOS os outros reembolsos dele.
        #
        # Disciplina copiada de `transporte_views.py:565-579`: apaga o
        # FILHO deste reembolso, recalcula o total do pai, e só mata o pai
        # se não sobrar filho nenhum — contando filhos, nunca somando
        # valor. Soma zero não é ausência de filho.
        if reembolso.origem_tabela == 'gestao_custo_pai' and reembolso.origem_id:
            gcp = GestaoCustoPai.query.filter_by(
                id=reembolso.origem_id, admin_id=admin_id
            ).first()
            if gcp:
                GestaoCustoFilho.query.filter_by(
                    pai_id=gcp.id, origem_tabela='reembolso_funcionario',
                    origem_id=reembolso.id, admin_id=admin_id).delete()
                db.session.flush()

                novo_total = db.session.query(
                    sa_func.coalesce(sa_func.sum(GestaoCustoFilho.valor), 0)
                ).filter(GestaoCustoFilho.pai_id == gcp.id).scalar()
                gcp.valor_total = Decimal(str(novo_total))

                restantes = db.session.query(
                    sa_func.count(GestaoCustoFilho.id)
                ).filter(GestaoCustoFilho.pai_id == gcp.id).scalar() or 0
                if restantes == 0 and gcp.status == 'PENDENTE':
                    db.session.delete(gcp)

        db.session.delete(reembolso)
        db.session.commit()
        flash('Reembolso excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Excluir reembolso {reembolso_id}: {e}")
        flash(f'Erro ao excluir: {e}', 'danger')

    return redirect(url_for('reembolso.index'))
