"""A24 — o rateio de encargos por obra liga atrás de flag por tenant.

Flag OFF (default): processar a folha muda ZERO no que existe hoje —
nenhuma linha de `FolhaProcessada` por obra nasce. Flag ON: o MESMO
processamento também grava a folha rateada por obra, com encargos — o
pipeline de `services/folha_service.py:1699`
(`processar_e_salvar_folha_obra`), correto e testado desde a Onda 3,
finalmente ganha chamador de produção. A flag segue o padrão exato da
`rdo_percentual_livre` (migração 226 + leitor em `utils/tenant.py` +
script por tenant); migração desta: 318, default FALSE.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §A24.
"""
import calendar
import os
import sys
from datetime import date, time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

ANO_REF = 2026
MES_REF = 6  # mês do data_ref default do arreio (2026-06-15), como na Onda 3


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a24-rateio'
    yield


# ── Cenário copiado de tests/test_onda3_folha.py (não importar entre
#    arquivos de teste: quebra isolamento) ─────────────────────────────────

def _segunda_obra(admin_id, cliente_id, marca):
    """Uma segunda obra no MESMO tenant — o arreio só semeia uma."""
    from models import Obra
    obra = Obra(nome=f'Obra 2 {marca}', codigo=f'{marca[:8]}B2',
                data_inicio=date(2026, 1, 1), admin_id=admin_id,
                cliente_id=cliente_id, valor_contrato=100000,
                orcamento=100000, status='Em andamento')
    db.session.add(obra)
    db.session.commit()
    return obra.id


def _seed_parametros_legais(admin_id):
    """Sem ParametrosLegais do ano a folha nem processa — o teste ficaria
    verde por vazio, não por a flag funcionar."""
    from models import ParametrosLegais
    params = ParametrosLegais(admin_id=admin_id, ano_vigencia=ANO_REF, ativo=True)
    db.session.add(params)
    db.session.commit()


def _seed_horario_trabalho(admin_id, funcionario_id, marca):
    """Segunda a sexta, 08:00–17:00 com 1h de pausa = 8h contratuais/dia."""
    from models import Funcionario, HorarioDia, HorarioTrabalho
    horario = HorarioTrabalho(nome=f'Comercial {marca}', admin_id=admin_id,
                              ativo=True, horas_diarias=8.0)
    db.session.add(horario)
    db.session.flush()
    for dia_semana in range(0, 5):  # segunda a sexta
        db.session.add(HorarioDia(
            horario_id=horario.id, dia_semana=dia_semana,
            entrada=time(8, 0), saida=time(17, 0),
            pausa_horas=1.0, trabalha=True, admin_id=admin_id))
    funcionario = db.session.get(Funcionario, funcionario_id)
    funcionario.horario_trabalho_id = horario.id
    db.session.commit()


def _seed_ponto_dividido_entre_obras(admin_id, funcionario_id,
                                     obra_a, obra_b, dias_na_obra_a):
    """Mês cheio em 8h/dia: os primeiros `dias_na_obra_a` dias úteis na
    obra A, o resto na obra B."""
    from models import RegistroPonto
    ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
    uteis = 0
    for dia in range(1, ultimo_dia + 1):
        data = date(ANO_REF, MES_REF, dia)
        if data.weekday() >= 5:
            continue
        uteis += 1
        obra_id = obra_a if uteis <= dias_na_obra_a else obra_b
        db.session.add(RegistroPonto(
            funcionario_id=funcionario_id, obra_id=obra_id, admin_id=admin_id,
            data=data, horas_trabalhadas=8.0, horas_extras=0.0))
    db.session.commit()


@pytest.fixture()
def cenario_folha():
    """Admin + funcionário + ponto do mês inteiro dividido em duas obras."""
    with app.app_context():
        t = um_tenant('a24_rateio', com_fatos=False)
        admin_id = t.admin_id
        obra_a = t.obra_id
        obra_b = _segunda_obra(admin_id, t.cliente_id, t.marca)
        _seed_parametros_legais(admin_id)
        _seed_horario_trabalho(admin_id, t.funcionario_id, t.marca)
        _seed_ponto_dividido_entre_obras(
            admin_id, t.funcionario_id, obra_a, obra_b, dias_na_obra_a=7)
    yield {'admin_id': admin_id, 'funcionario_id': t.funcionario_id,
           'obra_a': obra_a, 'obra_b': obra_b,
           'ano': ANO_REF, 'mes': MES_REF}


def _processar_o_mes(admin_id, ano, mes):
    """Dispara o MESMO caminho da rota `folha.processar_folha_mes` — via
    cliente HTTP logado como o admin. A rota real é
    `POST /folha/processar/<ano>/<mes>` (folha_pagamento_views.py:144),
    ano/mês na URL, não em campo de form."""
    return cliente_de(admin_id).post(
        f'/folha/processar/{ano}/{mes}',
        data={'reprocessar': 'false'}, follow_redirects=True)


# ── Os testes ─────────────────────────────────────────────────────────────

def test_leitor_da_flag_falha_seguro_sem_tenant():
    with app.app_context():
        from utils.tenant import folha_rateio_encargos_on
        assert folha_rateio_encargos_on(None) is False
        assert folha_rateio_encargos_on(999999999) is False


def test_a_flag_liga_e_desliga_por_script():
    with app.app_context():
        from scripts.flag_folha_rateio_encargos import definir_flag, status_flag
        from models import Usuario, TipoUsuario
        import uuid
        from werkzeug.security import generate_password_hash
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'a24{marca}', email=f'a24{marca}@t.local', nome='A24',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.commit()
        # `status_flag` devolve dict, como no script-espelho da 226.
        assert status_flag(admin.id)['folha_rateio_encargos'] is False  # default
        definir_flag(admin.id, True)
        assert status_flag(admin.id)['folha_rateio_encargos'] is True
        definir_flag(admin.id, False)
        assert status_flag(admin.id)['folha_rateio_encargos'] is False


def test_flag_off_processar_folha_nao_grava_rateio(cenario_folha):
    c = cenario_folha
    resposta = _processar_o_mes(c['admin_id'], c['ano'], c['mes'])
    assert resposta.status_code == 200
    with app.app_context():
        from models import FolhaPagamento, FolhaProcessada
        processadas = FolhaPagamento.query.filter_by(
            admin_id=c['admin_id'],
            mes_referencia=date(c['ano'], c['mes'], 1)).count()
        assert processadas > 0, (
            'pré-condição: a folha do mês tem de ter processado — sem isso '
            'o teste ficaria verde por vazio')
        linhas = FolhaProcessada.query.filter_by(
            admin_id=c['admin_id'], ano=c['ano'], mes=c['mes']).all()
        com_obra = [l.obra_id for l in linhas if l.obra_id is not None]
        assert com_obra == [], (
            'flag OFF (default) tem de manter o comportamento de hoje: '
            f'nenhuma linha rateada por obra, veio {com_obra}')


def test_flag_on_processar_folha_grava_rateio_com_encargos(cenario_folha):
    c = cenario_folha
    with app.app_context():
        from scripts.flag_folha_rateio_encargos import definir_flag
        definir_flag(c['admin_id'], True)
    resposta = _processar_o_mes(c['admin_id'], c['ano'], c['mes'])
    assert resposta.status_code == 200
    with app.app_context():
        from models import FolhaProcessada
        obras_gravadas = {
            l.obra_id for l in FolhaProcessada.query.filter_by(
                admin_id=c['admin_id'], ano=c['ano'], mes=c['mes'])
            if l.obra_id is not None}
        assert obras_gravadas == {c['obra_a'], c['obra_b']}, (
            'com a flag ON, cada obra com ponto no mês ganha sua fatia — '
            f'veio {obras_gravadas}')
        uma = FolhaProcessada.query.filter_by(
            admin_id=c['admin_id'], ano=c['ano'], mes=c['mes'],
            obra_id=c['obra_a']).first()
        assert (uma.encargos_fgts or 0) > 0 or (
            uma.encargos_inss_patronal or 0) > 0, (
            'a fatia da obra tem de carregar encargos — é o ~28% que faltava')
