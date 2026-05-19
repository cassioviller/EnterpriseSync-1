"""
views/quick_create_views.py — Task #30
Blueprint /api/quick-create/ — criação rápida de entidades a partir de dropdowns.
Cada rota POST valida campos obrigatórios e duplicatas, cria o registro com admin_id
do usuário logado e retorna JSON {id, label}. Erros retornam {erro: "msg"} HTTP 422.
"""
import logging
import uuid
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from app import db
from models import Insumo, Fornecedor, Cliente, SubatividadeMestre

logger = logging.getLogger(__name__)

quick_create_bp = Blueprint('quick_create', __name__, url_prefix='/api/quick-create')


def _admin_id():
    try:
        if current_user and current_user.is_authenticated:
            return getattr(current_user, 'admin_id', None) or current_user.id
    except Exception:
        pass
    abort(401)


def _get_json():
    return request.get_json(silent=True) or {}


@quick_create_bp.route('/insumo', methods=['POST'])
@login_required
def criar_insumo():
    aid = _admin_id()
    data = _get_json()
    nome = (data.get('nome') or '').strip()
    tipo = (data.get('tipo') or 'MATERIAL').strip().upper()
    unidade = (data.get('unidade') or 'un').strip() or 'un'

    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 422
    if tipo not in ('MATERIAL', 'MAO_OBRA', 'EQUIPAMENTO'):
        tipo = 'MATERIAL'

    existing = Insumo.query.filter_by(admin_id=aid, nome=nome, ativo=True).first()
    if existing:
        return jsonify({'erro': f'Insumo "{nome}" já existe'}), 422

    ins = Insumo(admin_id=aid, nome=nome, tipo=tipo, unidade=unidade)
    db.session.add(ins)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('quick_create/insumo erro ao salvar')
        return jsonify({'erro': 'Erro ao salvar insumo. Tente novamente.'}), 422

    return jsonify({
        'id': ins.id,
        'label': f'{ins.nome} ({ins.tipo} / {ins.unidade})',
        'nome': ins.nome,
        'tipo': ins.tipo,
        'unidade': ins.unidade,
    })


@quick_create_bp.route('/fornecedor', methods=['POST'])
@login_required
def criar_fornecedor():
    aid = _admin_id()
    data = _get_json()
    nome = (data.get('nome') or '').strip()
    cnpj = (data.get('cnpj') or '').strip()
    if not cnpj:
        cnpj = f'QC-{uuid.uuid4().hex[:12]}'

    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 422

    existing = Fornecedor.query.filter(
        Fornecedor.admin_id == aid,
        db.func.lower(Fornecedor.nome) == nome.lower(),
    ).first()
    if existing:
        return jsonify({'erro': f'Fornecedor "{nome}" já existe', 'id': existing.id, 'label': existing.nome}), 422

    forn = Fornecedor(admin_id=aid, nome=nome, cnpj=cnpj)
    db.session.add(forn)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('quick_create/fornecedor erro ao salvar')
        return jsonify({'erro': 'Erro ao salvar fornecedor. Tente novamente.'}), 422

    return jsonify({'id': forn.id, 'label': forn.nome})


@quick_create_bp.route('/cliente', methods=['POST'])
@login_required
def criar_cliente():
    aid = _admin_id()
    data = _get_json()
    nome = (data.get('nome') or '').strip()
    email = (data.get('email') or '').strip() or None

    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 422

    existing = Cliente.query.filter(
        Cliente.admin_id == aid,
        db.func.lower(Cliente.nome) == nome.lower(),
    ).first()
    if existing:
        return jsonify({'erro': f'Cliente "{nome}" já existe', 'id': existing.id, 'label': existing.nome}), 422

    cli = Cliente(admin_id=aid, nome=nome, email=email)
    db.session.add(cli)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('quick_create/cliente erro ao salvar')
        return jsonify({'erro': 'Erro ao salvar cliente. Tente novamente.'}), 422

    return jsonify({'id': cli.id, 'label': cli.nome})


@quick_create_bp.route('/subatividade-mestre', methods=['POST'])
@login_required
def criar_subatividade_mestre():
    aid = _admin_id()
    data = _get_json()
    nome = (data.get('nome') or '').strip()
    unidade_medida = (data.get('unidade_medida') or '').strip() or None

    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 422

    existing = SubatividadeMestre.query.filter(
        SubatividadeMestre.admin_id == aid,
        db.func.lower(SubatividadeMestre.nome) == nome.lower(),
    ).first()
    if existing:
        label = existing.nome
        if existing.unidade_medida:
            label += f' ({existing.unidade_medida})'
        return jsonify({'erro': f'Subatividade "{nome}" já existe', 'id': existing.id, 'label': label}), 422

    sub = SubatividadeMestre(
        admin_id=aid,
        nome=nome,
        unidade_medida=unidade_medida,
        tipo='subatividade',
    )
    db.session.add(sub)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('quick_create/subatividade-mestre erro ao salvar')
        return jsonify({'erro': 'Erro ao salvar subatividade. Tente novamente.'}), 422

    label = nome
    if unidade_medida:
        label += f' ({unidade_medida})'
    return jsonify({'id': sub.id, 'label': label, 'nome': sub.nome, 'unidade_medida': sub.unidade_medida})
