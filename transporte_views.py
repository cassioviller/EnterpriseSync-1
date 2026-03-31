import logging
import os
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from models import (CategoriaTransporte, CentroCusto, CustoObra,
                    Funcionario, LancamentoTransporte, Obra, Vehicle)
from utils.tenant import get_tenant_admin_id, is_v2_active

logger = logging.getLogger(__name__)

transporte_bp = Blueprint('transporte', __name__, url_prefix='/transporte')

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'comprovantes')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_admin_id():
    return get_tenant_admin_id()


def _seed_categorias(admin_id):
    """Cria categorias padrão caso o tenant não tenha nenhuma."""
    count = CategoriaTransporte.query.filter_by(admin_id=admin_id).count()
    if count == 0:
        defaults = [
            ('Vale Transporte', 'fas fa-bus'),
            ('Combustível', 'fas fa-gas-pump'),
            ('Aplicativo/Uber', 'fas fa-car'),
            ('Passagem Aérea', 'fas fa-plane'),
            ('Passagem Rodoviária', 'fas fa-ticket-alt'),
        ]
        for nome, icone in defaults:
            db.session.add(CategoriaTransporte(nome=nome, icone=icone, admin_id=admin_id))
        db.session.commit()
        logger.info(f"[OK] Categorias de transporte criadas para admin_id={admin_id}")


def _check_v2():
    """Retorna resposta de erro se o tenant não for V2, ou None para continuar."""
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


# ─────────────────────────────────────────────
# LISTA
# ─────────────────────────────────────────────
@transporte_bp.route('/')
@login_required
def index():
    guard = _check_v2()
    if guard:
        return guard
    admin_id = _get_admin_id()
    _seed_categorias(admin_id)

    # Filtros
    filtro_data_inicio = request.args.get('data_inicio')
    filtro_data_fim = request.args.get('data_fim')
    filtro_funcionario = request.args.get('funcionario_id', type=int)
    filtro_centro_custo = request.args.get('centro_custo_id', type=int)
    filtro_categoria = request.args.get('categoria_id', type=int)

    query = (
        LancamentoTransporte.query
        .filter_by(admin_id=admin_id)
        .order_by(LancamentoTransporte.data_lancamento.desc())
    )

    if filtro_data_inicio:
        query = query.filter(LancamentoTransporte.data_lancamento >= filtro_data_inicio)
    if filtro_data_fim:
        query = query.filter(LancamentoTransporte.data_lancamento <= filtro_data_fim)
    if filtro_funcionario:
        query = query.filter_by(funcionario_id=filtro_funcionario)
    if filtro_centro_custo:
        query = query.filter_by(centro_custo_id=filtro_centro_custo)
    if filtro_categoria:
        query = query.filter_by(categoria_id=filtro_categoria)

    lancamentos = query.limit(200).all()
    total_valor = sum(float(l.valor) for l in lancamentos)

    categorias = CategoriaTransporte.query.filter_by(admin_id=admin_id).order_by('nome').all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    centros_custo = CentroCusto.query.filter_by(admin_id=admin_id).order_by('nome').all()

    return render_template(
        'transporte/index.html',
        lancamentos=lancamentos,
        total_valor=total_valor,
        categorias=categorias,
        funcionarios=funcionarios,
        centros_custo=centros_custo,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim,
        filtro_funcionario=filtro_funcionario,
        filtro_centro_custo=filtro_centro_custo,
        filtro_categoria=filtro_categoria,
    )


# ─────────────────────────────────────────────
# NOVO LANÇAMENTO — GET
# ─────────────────────────────────────────────
@transporte_bp.route('/novo', methods=['GET'])
@login_required
def novo():
    guard = _check_v2()
    if guard:
        return guard
    admin_id = _get_admin_id()
    _seed_categorias(admin_id)

    categorias = CategoriaTransporte.query.filter_by(admin_id=admin_id).order_by('nome').all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    veiculos = Vehicle.query.filter_by(admin_id=admin_id).order_by('modelo').all()
    centros_custo = CentroCusto.query.filter_by(admin_id=admin_id).order_by('nome').all()
    obras = Obra.query.filter_by(admin_id=admin_id, status='em_andamento').order_by('nome').all()

    return render_template(
        'transporte/novo_lancamento.html',
        categorias=categorias,
        funcionarios=funcionarios,
        veiculos=veiculos,
        centros_custo=centros_custo,
        obras=obras,
        hoje=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# NOVO LANÇAMENTO — POST
# ─────────────────────────────────────────────
@transporte_bp.route('/novo', methods=['POST'])
@login_required
def novo_post():
    guard = _check_v2()
    if guard:
        return guard
    admin_id = _get_admin_id()

    try:
        categoria_id = int(request.form.get('categoria_id'))
        centro_custo_id = int(request.form.get('centro_custo_id'))
        data_lancamento = datetime.strptime(request.form.get('data_lancamento'), '%Y-%m-%d').date()
        valor = float(request.form.get('valor', '0').replace(',', '.'))
        descricao = request.form.get('descricao', '').strip()
        funcionario_id = request.form.get('funcionario_id') or None
        veiculo_id = request.form.get('veiculo_id') or None
        obra_id = request.form.get('obra_id') or None

        if funcionario_id:
            funcionario_id = int(funcionario_id)
        if veiculo_id:
            veiculo_id = int(veiculo_id)
        if obra_id:
            obra_id = int(obra_id)

        # Upload do comprovante
        comprovante_url = None
        arquivo = request.files.get('comprovante')
        if arquivo and arquivo.filename and _allowed_file(arquivo.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            nome_arquivo = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(arquivo.filename)}"
            caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
            arquivo.save(caminho)
            comprovante_url = '/' + caminho.replace(os.sep, '/')

        lancamento = LancamentoTransporte(
            categoria_id=categoria_id,
            funcionario_id=funcionario_id,
            veiculo_id=veiculo_id,
            centro_custo_id=centro_custo_id,
            obra_id=obra_id,
            data_lancamento=data_lancamento,
            valor=valor,
            descricao=descricao,
            comprovante_url=comprovante_url,
            admin_id=admin_id,
        )
        db.session.add(lancamento)
        db.session.flush()  # garante lancamento.id antes do CustoObra

        # Apropriação automática na Obra
        if obra_id:
            categoria = CategoriaTransporte.query.get(categoria_id)
            if funcionario_id:
                func = Funcionario.query.get(funcionario_id)
                detalhe = func.nome if func else 'Funcionário'
            elif veiculo_id:
                veic = Vehicle.query.get(veiculo_id)
                detalhe = veic.placa if veic else 'Veículo'
            else:
                detalhe = 'Geral'

            desc_custo = f"{categoria.nome if categoria else 'Transporte'} - {detalhe}"
            if descricao:
                desc_custo += f" - {descricao}"

            custo = CustoObra(
                obra_id=obra_id,
                centro_custo_id=centro_custo_id,
                tipo='veiculo',
                descricao=desc_custo[:200],
                valor=float(valor),
                data=data_lancamento,
                admin_id=admin_id,
                categoria='transporte',
            )
            db.session.add(custo)
            logger.info(f"[OK] CustoObra criado para obra_id={obra_id} via transporte")

        db.session.commit()
        flash('Lançamento de transporte registrado com sucesso!', 'success')
        return redirect(url_for('transporte.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao salvar lancamento_transporte: {e}")
        flash(f'Erro ao salvar lançamento: {str(e)}', 'danger')
        return redirect(url_for('transporte.novo'))


# ─────────────────────────────────────────────
# EXCLUSÃO
# ─────────────────────────────────────────────
@transporte_bp.route('/excluir/<int:lancamento_id>', methods=['POST'])
@login_required
def excluir(lancamento_id):
    admin_id = _get_admin_id()
    lancamento = LancamentoTransporte.query.filter_by(id=lancamento_id, admin_id=admin_id).first_or_404()
    try:
        db.session.delete(lancamento)
        db.session.commit()
        flash('Lançamento excluído.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {e}', 'danger')
    return redirect(url_for('transporte.index'))
