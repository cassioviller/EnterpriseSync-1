"""Teste de ciclo completo de RDO V2: criar -> editar -> editar de novo -> visualizar.

Cobre, num único fluxo realista, TODOS os campos principais e verifica:
  - persistência de cada campo (clima, observação, apontamento de cronograma,
    equipe por atividade, equipamento, ocorrência);
  - CÁLCULO correto do percentual realizado do apontamento (qtd/qtd_total);
  - NÃO-DUPLICAÇÃO ao editar duas vezes (mão de obra, ocorrência, custo diário,
    apontamento de cronograma);
  - VISUALIZAÇÃO renderiza os dados (HTTP 200 + conteúdo).

Roda contra o branch de hotfix (= origin/main + fix de edição).
"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
import main  # noqa: F401 — registra blueprints (rotas /salvar-rdo-flexivel, /rdo/editar)
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOOcorrencia, RDOEquipamento,
    RDOApontamentoCronograma, TarefaCronograma, RDOCustoDiario,
)
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


def _login(c, user_id):
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


@pytest.fixture(scope='module', autouse=True)
def amb():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        s = _sfx()
        admin = Usuario(
            username=f'ciclo_{s}', email=f'ciclo_{s}@sige.test',
            nome='Ciclo RDO', tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-CIC-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra CIC {s}', codigo=f'OCC{s[:6]}',
            data_inicio=date(2026, 1, 1), admin_id=admin.id,
            cliente_id=cli.id, valor_contrato=100000,
        )
        db.session.add(obra); db.session.flush()
        tarefa = TarefaCronograma(
            obra_id=obra.id, nome_tarefa='Alvenaria', ordem=1,
            duracao_dias=10, quantidade_total=100.0, percentual_concluido=0.0,
            unidade_medida='m2', data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 15), admin_id=admin.id,
        )
        db.session.add(tarefa)
        func = Funcionario(
            nome=f'Func CIC {s}', cpf=f'444{s}'.ljust(14, '0')[:14],
            codigo=f'FC{s[:8]}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, tipo_remuneracao='salario', salario=3000.0,
            ativo=True,
        )
        db.session.add(func); db.session.commit()

        amb.admin_id = admin.id
        amb.obra_id = obra.id
        amb.tarefa_id = tarefa.id
        amb.func_id = func.id
        yield


def _payload_base():
    return {
        'obra_id': str(amb.obra_id),
        'admin_id_form': str(amb.admin_id),
        'data_relatorio': '2026-06-12',
        'clima_geral': 'Ensolarado',
        'temperatura_media': '28',
        'condicoes_trabalho': 'Normais',
    }


def test_ciclo_completo_rdo_v2():
    # ---------- CRIAÇÃO ----------
    with app.app_context():
        with app.test_client() as c:
            _login(c, amb.admin_id)
            data = _payload_base()
            data.update({
                'observacoes_finais': 'Tudo certo na obra.',
                f'cronograma_tarefa_{amb.tarefa_id}': '20',
                f'cron_tarefa_{amb.tarefa_id}_func_{amb.func_id}_horas': '8',
                'equip_nome[]': 'Betoneira',
                'equip_quantidade[]': '1',
                'equip_horas_uso[]': '6',
                'equip_estado[]': 'Bom',
                'ocorr_tipo[]': 'Atraso',
                'ocorr_severidade[]': 'Média',
                'ocorr_descricao[]': 'Material atrasou na entrega.',
                'ocorr_status[]': 'Pendente',
            })
            resp = c.post('/salvar-rdo-flexivel', data=data, follow_redirects=False)
        assert resp.status_code in (200, 302), resp.status_code

        rdo = RDO.query.filter_by(obra_id=amb.obra_id).order_by(RDO.id.desc()).first()
        assert rdo is not None, 'RDO não foi criado'
        amb.rdo_id = rdo.id

        # Campos básicos / clima / observação
        assert rdo.clima_geral == 'Ensolarado'
        assert rdo.temperatura_media == '28'
        assert rdo.condicoes_trabalho == 'Normais'
        assert rdo.comentario_geral and 'Tudo certo' in rdo.comentario_geral, \
            f'observação não salvou: {rdo.comentario_geral!r}'

        # Apontamento de cronograma + CÁLCULO do percentual (20/100 = 20%)
        aps = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).all()
        assert len(aps) == 1, f'esperado 1 apontamento, veio {len(aps)}'
        assert aps[0].quantidade_executada_dia == 20.0
        assert aps[0].percentual_realizado == 20.0, \
            f'cálculo % errado: {aps[0].percentual_realizado} (esperado 20.0)'

        # Equipe por atividade do cronograma (8h, 1 atividade => não divide)
        mo = RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()
        cron = [m for m in mo if m.tarefa_cronograma_id == amb.tarefa_id]
        assert len(cron) == 1, f'esperado 1 mão de obra cronograma, veio {len(cron)}'
        assert abs((cron[0].horas_trabalhadas or 0) - 8.0) < 0.01, \
            f'horas erradas: {cron[0].horas_trabalhadas}'

        # Equipamento + Ocorrência
        assert RDOEquipamento.query.filter_by(rdo_id=rdo.id).count() == 1
        oc = RDOOcorrencia.query.filter_by(rdo_id=rdo.id).all()
        assert len(oc) == 1 and oc[0].descricao_ocorrencia == 'Material atrasou na entrega.'

        print(f"\n[CRIAR] rdo={rdo.id} ap%={aps[0].percentual_realizado} "
              f"mo={len(mo)} eq=1 oc=1")

    # ---------- EDIÇÃO 1 (altera observação e ocorrência) ----------
    with app.app_context():
        with app.test_client() as c:
            _login(c, amb.admin_id)
            data = _payload_base()
            data.update({
                'observacoes_gerais': 'Editado: choveu à tarde.',
                f'cron_tarefa_{amb.tarefa_id}_func_{amb.func_id}_horas': '8',
                'equip_nome[]': 'Betoneira',
                'equip_quantidade[]': '1',
                'equip_horas_uso[]': '6',
                'equip_estado[]': 'Bom',
                'ocorr_tipo[]': 'Atraso',
                'ocorr_severidade[]': 'Alta',
                'ocorr_descricao[]': 'Editado: atraso confirmado.',
                'ocorr_status[]': 'Em andamento',
            })
            resp = c.post(f'/rdo/editar/{amb.rdo_id}', data=data, follow_redirects=False)
        assert resp.status_code in (200, 302), resp.status_code

        rdo = RDO.query.get(amb.rdo_id)
        assert 'choveu' in (rdo.comentario_geral or ''), \
            f'observação editada não salvou: {rdo.comentario_geral!r}'
        oc = RDOOcorrencia.query.filter_by(rdo_id=amb.rdo_id).all()
        assert len(oc) == 1, f'ocorrência DUPLICOU na edição: {len(oc)}'
        assert oc[0].descricao_ocorrencia == 'Editado: atraso confirmado.'
        cron = [m for m in RDOMaoObra.query.filter_by(rdo_id=amb.rdo_id).all()
                if m.tarefa_cronograma_id == amb.tarefa_id]
        assert len(cron) == 1, f'mão de obra DUPLICOU na edição: {len(cron)}'

    # ---------- EDIÇÃO 2 (idêntica — testa idempotência / não-duplicação) ----------
    with app.app_context():
        with app.test_client() as c:
            _login(c, amb.admin_id)
            data = _payload_base()
            data.update({
                'observacoes_gerais': 'Editado: choveu à tarde.',
                f'cron_tarefa_{amb.tarefa_id}_func_{amb.func_id}_horas': '8',
                'ocorr_tipo[]': 'Atraso',
                'ocorr_severidade[]': 'Alta',
                'ocorr_descricao[]': 'Editado: atraso confirmado.',
                'ocorr_status[]': 'Em andamento',
            })
            resp = c.post(f'/rdo/editar/{amb.rdo_id}', data=data, follow_redirects=False)
        assert resp.status_code in (200, 302), resp.status_code

        n_oc = RDOOcorrencia.query.filter_by(rdo_id=amb.rdo_id).count()
        n_mo = RDOMaoObra.query.filter_by(rdo_id=amb.rdo_id).count()
        n_cd = RDOCustoDiario.query.filter_by(rdo_id=amb.rdo_id).count()
        n_ap = RDOApontamentoCronograma.query.filter_by(rdo_id=amb.rdo_id).count()
        print(f"[EDITAR x2] oc={n_oc} mo={n_mo} custo_diario={n_cd} apont={n_ap}")
        assert n_oc == 1, f'ocorrência duplicou após 2 edições: {n_oc}'
        assert n_mo == 1, f'mão de obra duplicou após 2 edições: {n_mo}'
        # custo diário: no máximo 1 por funcionário neste RDO
        assert n_cd <= 1, f'custo diário duplicou: {n_cd}'
        # apontamento de cronograma NÃO é tocado pela edição (fica o original)
        assert n_ap == 1, f'apontamento cronograma inesperado: {n_ap}'

    # ---------- VISUALIZAÇÃO ----------
    with app.app_context():
        with app.test_client() as c:
            _login(c, amb.admin_id)
            resp = c.get(f'/rdo/{amb.rdo_id}')
        assert resp.status_code == 200, resp.status_code
        html = resp.get_data(as_text=True)
        assert 'Ensolarado' in html, 'clima não aparece na visualização'
        assert 'atraso confirmado' in html, 'ocorrência não aparece na visualização'
        assert 'choveu' in html, 'observação não aparece na visualização'
