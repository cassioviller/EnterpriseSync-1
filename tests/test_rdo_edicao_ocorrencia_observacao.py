"""Reprodução do bug reportado em produção (16/06): ao editar um RDO,
ocorrência + observação + funcionários adicionados "não salvam".

Este teste exercita o fluxo REAL de edição (POST /rdo/editar/<id>) com os três
campos de uma vez e verifica, individualmente, o que persiste:
  - RDOOcorrencia (campos repetíveis ocorr_*[])
  - rdo.comentario_geral (textarea observacoes_gerais)
  - RDOMaoObra com tarefa_cronograma_id (equipe por atividade V2)

Roda contra o código do branch. Se os três persistem aqui mas o usuário
relata falha em produção, a diferença está no ambiente (deploy/migração) ou
numa rota distinta — não no código deste handler.
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
    RDO, RDOMaoObra, RDOOcorrencia, TarefaCronograma,
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
            username=f'oc_rdo_{s}', email=f'oc_rdo_{s}@sige.test',
            nome='Ocorr RDO', tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-OC-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra OC {s}', codigo=f'OOC{s[:6]}',
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
            nome=f'Func OC {s}', cpf=f'333{s}'.ljust(14, '0')[:14],
            codigo=f'FO{s[:8]}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, tipo_remuneracao='salario', salario=3000.0,
            ativo=True,
        )
        db.session.add(func)
        rdo = RDO(
            numero_rdo=f'RDO-OC-{s}', obra_id=obra.id,
            data_relatorio=date(2026, 6, 10), admin_id=admin.id,
            status='Finalizado', criado_por_id=admin.id,
        )
        db.session.add(rdo); db.session.commit()

        ambiente.admin_id = admin.id
        ambiente.obra_id = obra.id
        ambiente.rdo_id = rdo.id
        ambiente.tarefa_id = tarefa.id
        ambiente.func_id = func.id
        yield


def test_edicao_salva_ocorrencia_observacao_e_funcionario():
    with app.app_context():
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(ambiente.admin_id)
                sess['_fresh'] = True
            resp = c.post(
                f'/rdo/editar/{ambiente.rdo_id}',
                data={
                    'data_relatorio': '2026-06-10',
                    'obra_id': str(ambiente.obra_id),
                    # Observação (textarea unificada)
                    'observacoes_gerais': 'Observação de teste — chuva à tarde.',
                    # Ocorrência (campos repetíveis)
                    'ocorr_tipo[]': 'Atraso',
                    'ocorr_severidade[]': 'Média',
                    'ocorr_descricao[]': 'Entrega de material atrasou 2h.',
                    'ocorr_status[]': 'Pendente',
                    # Equipe por atividade do cronograma (V2)
                    f'cron_tarefa_{ambiente.tarefa_id}_func_{ambiente.func_id}_horas': '8',
                },
                follow_redirects=False,
            )
        assert resp.status_code in (200, 302), resp.status_code

        rdo = RDO.query.get(ambiente.rdo_id)
        ocorrencias = RDOOcorrencia.query.filter_by(rdo_id=ambiente.rdo_id).all()
        mao_obra = RDOMaoObra.query.filter_by(rdo_id=ambiente.rdo_id).all()
        cron = [m for m in mao_obra if m.tarefa_cronograma_id == ambiente.tarefa_id]

        # Relatório explícito do que persistiu (aparece no -s do pytest)
        print(
            f"\n[REPRO] ocorrencias={len(ocorrencias)} "
            f"comentario_geral={rdo.comentario_geral!r} "
            f"mao_obra={len(mao_obra)} cron_ligadas={len(cron)}"
        )

        assert ocorrencias, 'OCORRÊNCIA não persistiu'
        assert ocorrencias[0].descricao_ocorrencia == 'Entrega de material atrasou 2h.'
        assert rdo.comentario_geral and 'chuva' in rdo.comentario_geral, \
            'OBSERVAÇÃO (comentario_geral) não persistiu'
        assert cron, 'FUNCIONÁRIO por atividade do cronograma não persistiu'
