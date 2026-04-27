"""
Blueprint de Cadastro de Clientes (Task #138)

Tela própria de CRUD para Clientes do admin logado, separada do
formulário de Proposta. Multi-tenant: cada admin vê apenas os seus.
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime
import logging

from app import db
from models import Cliente, Proposta, Orcamento, Obra

logger = logging.getLogger(__name__)


class _Valores:
    """Wrapper simples para preencher o formulário a partir de dict ou modelo."""
    def __init__(self, source=None):
        self._source = source or {}

    def __getattr__(self, item):
        if isinstance(self._source, dict):
            return self._source.get(item, '')
        return getattr(self._source, item, '') if self._source else ''

clientes_bp = Blueprint('clientes', __name__, url_prefix='/cadastros/clientes')


def get_admin_id():
    """Retorna admin_id do usuário atual (padrão consolidado do sistema)."""
    if not current_user.is_authenticated:
        return None
    if hasattr(current_user, 'admin_id') and current_user.admin_id:
        return current_user.admin_id
    return current_user.id


def _normalizar_cnpj(valor):
    if not valor:
        return None
    return ''.join(c for c in valor if c.isdigit()) or None


@clientes_bp.route('/')
@login_required
def listar():
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    busca = request.args.get('busca', '').strip()
    query = Cliente.query.filter_by(admin_id=admin_id)
    if busca:
        like = f'%{busca}%'
        query = query.filter(or_(
            Cliente.nome.ilike(like),
            Cliente.email.ilike(like),
            Cliente.telefone.ilike(like),
            Cliente.cnpj.ilike(like),
        ))
    clientes = query.order_by(Cliente.nome).all()
    return render_template('cadastros/clientes.html',
                           clientes=clientes, busca=busca)


@clientes_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def criar():
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Nome é obrigatório', 'danger')
            return render_template('cadastros/clientes_form.html', cliente=None,
                                   valores=_Valores(request.form.to_dict()))
        try:
            cliente = Cliente(
                nome=nome,
                email=(request.form.get('email') or '').strip() or None,
                telefone=(request.form.get('telefone') or '').strip() or None,
                cnpj=_normalizar_cnpj(request.form.get('cnpj')),
                endereco=(request.form.get('endereco') or '').strip() or None,
                admin_id=admin_id,
            )
            db.session.add(cliente)
            db.session.commit()
            flash(f'Cliente "{nome}" cadastrado com sucesso!', 'success')
            return redirect(url_for('clientes.listar'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao criar cliente: {e}')
            flash(f'Erro ao cadastrar cliente: {e}', 'danger')
            return render_template('cadastros/clientes_form.html', cliente=None,
                                   valores=_Valores(request.form.to_dict()))

    return render_template('cadastros/clientes_form.html', cliente=None,
                           valores=_Valores())


@clientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    cliente = Cliente.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Nome é obrigatório', 'danger')
            return render_template('cadastros/clientes_form.html',
                                   cliente=cliente,
                                   valores=_Valores(request.form.to_dict()))
        try:
            cliente.nome = nome
            cliente.email = (request.form.get('email') or '').strip() or None
            cliente.telefone = (request.form.get('telefone') or '').strip() or None
            cliente.cnpj = _normalizar_cnpj(request.form.get('cnpj'))
            cliente.endereco = (request.form.get('endereco') or '').strip() or None
            db.session.commit()
            flash(f'Cliente "{nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('clientes.listar'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao atualizar cliente: {e}')
            flash(f'Erro ao atualizar cliente: {e}', 'danger')

    return render_template('cadastros/clientes_form.html',
                           cliente=cliente, valores=_Valores(cliente))


@clientes_bp.route('/api/buscar', methods=['GET'])
@login_required
def api_buscar():
    """Endpoint JSON para autocomplete de cliente em formulário de Obra
    (Task #175). Retorna até 20 clientes do tenant filtrados por nome,
    e-mail, telefone ou CNPJ. Sempre escopo do admin_id atual.
    """
    admin_id = get_admin_id()
    if not admin_id:
        return jsonify({'results': []}), 401

    termo = (request.args.get('q') or '').strip()
    query = Cliente.query.filter_by(admin_id=admin_id)
    if termo:
        like = f'%{termo}%'
        query = query.filter(or_(
            Cliente.nome.ilike(like),
            Cliente.email.ilike(like),
            Cliente.telefone.ilike(like),
            Cliente.cnpj.ilike(like),
        ))
    clientes = (
        query.order_by(Cliente.nome.asc()).limit(20).all()
    )
    return jsonify({
        'results': [
            {
                'id': c.id,
                'nome': c.nome or '',
                'email': c.email or '',
                'telefone': c.telefone or '',
                'cnpj': c.cnpj or '',
                'endereco': c.endereco or '',
            }
            for c in clientes
        ]
    })


@clientes_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    admin_id = get_admin_id()
    if not admin_id:
        flash('Erro de autenticação', 'danger')
        return redirect(url_for('main.index'))

    cliente = Cliente.query.filter_by(id=id, admin_id=admin_id).first_or_404()

    propostas_count = Proposta.query.filter_by(cliente_id=cliente.id).count()
    orcamentos_count = Orcamento.query.filter_by(cliente_id=cliente.id).count()
    obras_count = Obra.query.join(
        Proposta, Proposta.id == Obra.proposta_origem_id
    ).filter(Proposta.cliente_id == cliente.id).count()
    if propostas_count or orcamentos_count or obras_count:
        partes = []
        if propostas_count:
            partes.append(f'{propostas_count} proposta(s)')
        if orcamentos_count:
            partes.append(f'{orcamentos_count} orçamento(s)')
        if obras_count:
            partes.append(f'{obras_count} obra(s)')
        flash(
            f'Não é possível excluir "{cliente.nome}" pois está vinculado a '
            + ', '.join(partes) + '.',
            'danger'
        )
        return redirect(url_for('clientes.listar'))

    try:
        nome = cliente.nome
        db.session.delete(cliente)
        db.session.commit()
        flash(f'Cliente "{nome}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao excluir cliente: {e}')
        flash(f'Erro ao excluir cliente: {e}', 'danger')

    return redirect(url_for('clientes.listar'))
