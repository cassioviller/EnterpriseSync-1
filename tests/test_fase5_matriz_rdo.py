"""Fase 5 — matriz papel × estado × ação, numa tabela só.

Cada linha do parametrize é uma frase de negócio verificável:
"um APONTADOR num RDO preenchido PODE assinar e NÃO PODE aprovar".
As tabelas do plano e o comportamento do código ficam presos um ao outro.

Duas adaptações do plano ao código real:

1. `_montar_cenario` liga `escopo_obra_ativo` (revisão de premissas
   23/07, item 20): com a flag OFF todo autenticado do tenant é GESTOR
   (`utils/autorizacao.py`, decisão da Fase 1) e as linhas
   LEITOR/APONTADOR da matriz falhariam pelo motivo errado.
2. O admin do cenário ganha `Funcionario` + vínculo próprio: `assinar`
   (services/rdo_assinatura.py) recusa usuário sem identidade — inclusive
   o admin que o plano usava para levar o RDO a 'assinado'.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, Obra, PapelObra, RDO, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-matriz'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _montar_cenario(papel_na_obra, estado_alvo):
    """Cria admin, obra, pessoa com `papel_na_obra` e um RDO em `estado_alvo`.

    Devolve (rdo_id, usuario_id).
    """
    from scripts.flag_escopo_obra import definir_flag
    from services.rdo_ciclo_vida import (ASSINADO, PREENCHIDO, RASCUNHO,
                                         transicionar)

    suf = _sfx()
    admin = Usuario(
        username=f'f5m_{suf}', email=f'f5m_{suf}@test.local',
        nome=f'Admin Matriz {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    # Item 20 da revisão de premissas: sem a flag, papel não distingue.
    definir_flag(admin.id, True)

    # O admin também precisa de identidade (Fase 1) para poder assinar
    # ao montar o cenário 'assinado'.
    func_admin = Funcionario(
        codigo=f'MA{suf[:6].upper()}', nome=f'Admin Pessoa {suf}',
        cpf=f'a{suf}'.ljust(14, '0')[:14], email=f'f5ma_{suf}@test.local',
        data_admissao=date(2025, 1, 1), admin_id=admin.id, ativo=True)
    db.session.add(func_admin)
    db.session.commit()
    admin.funcionario_id = func_admin.id
    db.session.commit()

    cli = Cliente(nome=f'CLI-M5-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra Matriz {suf}', codigo=f'OM5{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    func = Funcionario(
        codigo=f'M5{suf[:6].upper()}', nome=f'Pessoa {suf}',
        cpf=suf.ljust(14, '0')[:14], email=f'f5mf_{suf}@test.local',
        data_admissao=date(2025, 1, 1), admin_id=admin.id, ativo=True)
    db.session.add(func)
    db.session.commit()

    if papel_na_obra == 'admin':
        ator = admin
    else:
        ator = Usuario(
            username=f'f5mu_{suf}', email=f'f5mu_{suf}@test.local',
            nome=f'Ator {suf}', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, funcionario_id=func.id)
        db.session.add(ator)
        db.session.commit()
        db.session.add(UsuarioObra(
            usuario_id=ator.id, obra_id=obra.id, papel=papel_na_obra,
            admin_id=admin.id, ativo=True))
        db.session.commit()

    rdo = RDO(numero_rdo=f'RDO-M5-{suf}', data_relatorio=date(2026, 6, 22),
              obra_id=obra.id, admin_id=admin.id, criado_por_id=ator.id,
              comentario_geral='Conteúdo original do dia.')
    db.session.add(rdo)
    db.session.commit()

    if estado_alvo != RASCUNHO:
        transicionar(rdo, PREENCHIDO, usuario=admin)
        db.session.commit()
    if estado_alvo == ASSINADO:
        from services.rdo_assinatura import assinar
        assinar(rdo, admin)
        db.session.commit()

    return rdo.id, ator.id


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# (papel_na_obra, estado_inicial, acao, estado_esperado_depois)
MATRIZ = [
    # LEITOR não faz nada.
    (PapelObra.LEITOR, 'rascunho', 'finalizar', 'rascunho'),
    (PapelObra.LEITOR, 'preenchido', 'assinar', 'preenchido'),
    (PapelObra.LEITOR, 'preenchido', 'reabrir', 'preenchido'),

    # APONTADOR submete e assina; não aprova, não reabre, não retifica.
    (PapelObra.APONTADOR, 'preenchido', 'assinar', 'assinado'),
    (PapelObra.APONTADOR, 'preenchido', 'reabrir', 'preenchido'),
    (PapelObra.APONTADOR, 'assinado', 'aprovar', 'assinado'),
    (PapelObra.APONTADOR, 'assinado', 'retificar', 'assinado'),

    # GESTOR faz tudo.
    (PapelObra.GESTOR, 'preenchido', 'assinar', 'assinado'),
    (PapelObra.GESTOR, 'preenchido', 'reabrir', 'rascunho'),
    (PapelObra.GESTOR, 'assinado', 'aprovar', 'aprovado'),
    (PapelObra.GESTOR, 'assinado', 'retificar', 'retificado'),

    # ADMIN do tenant enxerga toda obra como GESTOR (Fase 1).
    ('admin', 'preenchido', 'assinar', 'assinado'),
    ('admin', 'assinado', 'aprovar', 'aprovado'),

    # Transições que a máquina de estados recusa, independente do papel.
    (PapelObra.GESTOR, 'rascunho', 'assinar', 'rascunho'),
    (PapelObra.GESTOR, 'rascunho', 'aprovar', 'rascunho'),
    (PapelObra.GESTOR, 'preenchido', 'aprovar', 'preenchido'),
    (PapelObra.GESTOR, 'rascunho', 'retificar', 'rascunho'),
    (PapelObra.GESTOR, 'assinado', 'reabrir', 'assinado'),
]

_ROTA = {
    'finalizar': '/rdo/{}/finalizar',
    'assinar': '/rdo/{}/assinar',
    'aprovar': '/rdo/{}/aprovar',
    'reabrir': '/rdo/{}/reabrir',
    'retificar': '/rdo/{}/retificar',
}


@pytest.mark.parametrize('papel,estado_inicial,acao,esperado', MATRIZ)
def test_matriz_papel_estado_acao(papel, estado_inicial, acao, esperado):
    nome_papel = papel if isinstance(papel, str) else papel.value

    with app.app_context():
        rdo_id, ator_id = _montar_cenario(papel, estado_inicial)

    dados = {'motivo': 'motivo de teste', 'observacao': 'obs de teste'}
    _cliente_de(ator_id).post(_ROTA[acao].format(rdo_id), data=dados,
                              follow_redirects=True)

    with app.app_context():
        atual = db.session.get(RDO, rdo_id).estado
        assert atual == esperado, (
            f'{nome_papel} em RDO {estado_inicial} tentando "{acao}": '
            f'estado ficou {atual!r}, esperado {esperado!r}')


def test_rdo_assinado_nunca_muda_de_conteudo_em_nenhum_caminho():
    """Fecho da fase: a frase que a Fase 5 existe para tornar verdadeira."""
    with app.app_context():
        rdo_id, ator_id = _montar_cenario(PapelObra.GESTOR, 'assinado')

    cliente = _cliente_de(ator_id)
    for rota, dados in (
        ('/salvar-rdo-flexivel', {'rdo_id': rdo_id,
                                  'comentario_geral': 'invasão 1'}),
        ('/rdo/salvar', {'rdo_id': rdo_id, 'comentario_geral': 'invasão 2'}),
        (f'/rdo/{rdo_id}/atualizar', {'data_relatorio': '2026-06-23'}),
        # rota real do sistema de edição: POST /rdo/editar/<rdo_id>
        # (rdo_editar_sistema.py:164 — o plano citava um '/salvar' que
        # não existe)
        (f'/rdo/editar/{rdo_id}', {'observacoes_gerais': 'invasão 3'}),
        (f'/rdo/excluir/{rdo_id}', {}),
    ):
        cliente.post(rota, data=dados, follow_redirects=True)

    with app.app_context():
        sobrevivente = db.session.get(RDO, rdo_id)
        assert sobrevivente is not None, 'o RDO assinado foi excluído'
        assert sobrevivente.comentario_geral == 'Conteúdo original do dia.', (
            'algum caminho de escrita alterou um RDO assinado')
        assert sobrevivente.data_relatorio == date(2026, 6, 22)
