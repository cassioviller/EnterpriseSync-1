#!/usr/bin/env python3
"""Resolver único de identidade — SIGE Fase 1.

ANTES desta fase, responder "qual Funcionario é o usuário logado?" tinha
seis implementações diferentes, todas erradas de formas distintas:

  * `views/employees.py:686` — `Funcionario.nome ILIKE '%username%'`, sem
    admin_id: casava pessoa de outro tenant por coincidência de nome.
  * `views/employees.py:693` — fallback para o e-mail literal
    "funcionario@valeverde.com".
  * `views/employees.py:697` — "o tenant com mais funcionários ativos".
  * `views/employees.py:704` — o PRIMEIRO funcionário ativo do banco inteiro.
  * `crud_rdo_completo.py:30` — mapa de e-mail chumbado em produção.
  * `views/rdo.py:2691-2705` — se nada casasse, CRIAVA um Funcionario
    chamado "Administrador Sistema".

Todas foram substituídas por este módulo. A regra aqui é uma só: a
identidade vem da FK `Usuario.funcionario_id` e de mais nada. Sem
vínculo, a resposta é `None` — nunca um palpite.
"""
import logging

from flask_login import current_user

from models import Funcionario, TipoUsuario, Usuario, db

logger = logging.getLogger('identidade')


class VinculoInvalido(ValueError):
    """Tentativa de vincular Usuario a Funcionario de outro tenant."""


def tenant_do_usuario(usuario):
    """Tenant (admin_id) de um Usuario qualquer.

    ADMIN/SUPER_ADMIN são o próprio tenant; os demais pertencem ao
    `admin_id`. Mesma regra de `utils.tenant.get_tenant_admin_id`, mas
    aplicável a um objeto arbitrário, não só ao `current_user`.
    """
    if usuario is None:
        return None
    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return usuario.id
    return usuario.admin_id


def vincular_funcionario(usuario, funcionario):
    """Liga login ↔ linha de RH, recusando cruzamento de tenant.

    A FK sozinha não consegue expressar o invariante "o Funcionario tem
    que ser do mesmo tenant do Usuario" (é uma condição entre duas
    tabelas). Este é o único caminho que deve escrever `funcionario_id`.
    Não faz commit — quem chama decide a transação.
    """
    if funcionario is None:
        usuario.funcionario_id = None
        return usuario

    tenant_usuario = tenant_do_usuario(usuario)
    if tenant_usuario is None or funcionario.admin_id != tenant_usuario:
        raise VinculoInvalido(
            f'Usuario {usuario.id} (tenant {tenant_usuario}) não pode ser '
            f'vinculado ao Funcionario {funcionario.id} '
            f'(tenant {funcionario.admin_id})')

    usuario.funcionario_id = funcionario.id
    return usuario


def funcionario_do_usuario(usuario=None):
    """O `Funcionario` do usuário logado, ou None.

    Falha FECHADA: sem vínculo devolve None. Quem chama decide o que
    fazer — o que não pode voltar a acontecer é adivinhar.
    """
    alvo = usuario
    if alvo is None:
        try:
            if not current_user.is_authenticated:
                return None
        except Exception:
            return None
        alvo = current_user

    funcionario_id = getattr(alvo, 'funcionario_id', None)
    if not funcionario_id:
        return None

    return db.session.get(Funcionario, funcionario_id)


def usuario_do_funcionario(funcionario_id):
    """Caminho inverso: o login de uma pessoa de RH, ou None."""
    if not funcionario_id:
        return None
    return Usuario.query.filter_by(funcionario_id=funcionario_id).first()
