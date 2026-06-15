"""Regressão do bug: editar um RDO V2 perdia RDOMaoObra.tarefa_cronograma_id.

Causa: o template emitia o campo da equipe de cronograma como
`sub_func_<tarefaId>_<funcId>_horas`; o handler de edição (rdo_editar_sistema.py)
tratava o 1º número como sub_mestre_id, então gravava RDOMaoObra com
subatividade_id=None e SEM tarefa_cronograma_id — o vínculo da atividade sumia.

Correção: o template passa a emitir `cron_tarefa_<tarefaId>_func_<funcId>_horas`
(espelho de views/rdo.py:salvar_rdo_flexivel) e o handler de edição parseia esse
padrão, gravando tarefa_cronograma_id.
"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
import main  # noqa: F401 — registra os blueprints (rota /rdo/editar) no app
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, TarefaCronograma,
)
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        s = _sfx()
        admin = Usuario(
            username=f'edit_rdo_{s}', email=f'edit_rdo_{s}@sige.test',
            nome='Edit RDO', tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-ED-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra ED {s}', codigo=f'OED{s[:6]}',
            data_inicio=date(2026, 1, 1), admin_id=admin.id,
            cliente_id=cli.id, valor_contrato=100000,
        )
        db.session.add(obra); db.session.flush()
        tarefa = TarefaCronograma(
            obra_id=obra.id, nome_tarefa='Alvenaria', ordem=1,
            duracao_dias=5, quantidade_total=100.0, percentual_concluido=0.0,
            admin_id=admin.id,
        )
        db.session.add(tarefa)
        func = Funcionario(
            nome=f'Func ED {s}', cpf=f'222{s}'.ljust(14, '0')[:14],
            codigo=f'FE{s[:8]}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, tipo_remuneracao='salario', salario=3000.0,
            ativo=True,
        )
        db.session.add(func)
        rdo = RDO(
            numero_rdo=f'RDO-ED-{s}', obra_id=obra.id,
            data_relatorio=date(2026, 2, 10), admin_id=admin.id,
            status='Finalizado', criado_por_id=admin.id,
        )
        db.session.add(rdo); db.session.commit()

        ambiente.admin_id = admin.id
        ambiente.obra_id = obra.id
        ambiente.rdo_id = rdo.id
        ambiente.tarefa_id = tarefa.id
        ambiente.func_id = func.id
        yield


def test_edicao_preserva_tarefa_cronograma_id():
    with app.app_context():
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(ambiente.admin_id)
                sess['_fresh'] = True
            resp = c.post(
                f'/rdo/editar/{ambiente.rdo_id}',
                data={
                    'data_relatorio': '2026-02-10',
                    'obra_id': str(ambiente.obra_id),
                    f'cron_tarefa_{ambiente.tarefa_id}_func_{ambiente.func_id}_horas': '8',
                },
                follow_redirects=False,
            )
        assert resp.status_code in (200, 302), resp.status_code

        linhas = RDOMaoObra.query.filter_by(rdo_id=ambiente.rdo_id).all()
        ligadas = [m for m in linhas if m.tarefa_cronograma_id == ambiente.tarefa_id]
        assert ligadas, (
            'edição não gravou tarefa_cronograma_id — bug não corrigido. '
            f'linhas={[(m.tarefa_cronograma_id, m.subatividade_id) for m in linhas]}'
        )
        assert all(m.subatividade_id is None for m in ligadas)
