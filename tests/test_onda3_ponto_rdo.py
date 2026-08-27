"""Onda 3 — o ponto que não vira hora, e o RDO que cobra quem saiu.

Quatro defeitos de UM tema só: **um lançamento que entra e não sai, ou uma
hora que entra e não vira número.** O arreio de tenant é
`tests/helpers_tenant.py` e o de dinheiro é `tests/helpers_dinheiro.py` — o
banco de desenvolvimento é compartilhado, então TODA contagem aqui é escopada
pelo `admin_id` do tenant do próprio teste. Contagem global mediria o mundo.
"""
import os
import sys
from datetime import date, time
from io import BytesIO

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant  # noqa: F401

pytestmark = pytest.mark.integration

# Dia sem nenhum RegistroPonto semeado — ver o docstring de `um_tenant`.
DIA = date(2026, 6, 15)
OUTRO_DIA = date(2026, 6, 16)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-ponto-rdo'
    yield


def _registro(tenant, data):
    """O RegistroPonto do tenant naquele dia — escopado, sempre relido."""
    from models import RegistroPonto
    db.session.expire_all()
    return RegistroPonto.query.filter_by(
        admin_id=tenant.admin_id, funcionario_id=tenant.funcionario_id,
        data=data).first()


# ---------------------------------------------------------------------------
# Defeito 1 — a importação Excel que nunca calculava hora (ponto_views.py:1487)
# ---------------------------------------------------------------------------

def _planilha_de_ponto(codigo, linhas):
    """Uma planilha no formato que `PontoExcelService.validar_e_importar` lê.

    Colunas: A=Data, B=tipo, C=obra_id, D=entrada, E=saída, F=almoço início,
    G=almoço fim (`services/ponto_importacao.py:576-595`). O nome da aba
    precisa de ' - ' e do código antes dele — é assim que o parser acha o
    funcionário. O sufixo é curto de propósito: openpyxl recusa título de aba
    com mais de 31 caracteres.
    """
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = f'{codigo} - F'
    ws.cell(row=1, column=1, value='Data')
    for i, (dia, tipo, obra_id, ent, sai, alm_i, alm_f) in enumerate(linhas):
        linha = 2 + i
        ws.cell(row=linha, column=1, value=dia.strftime('%d/%m/%Y'))
        ws.cell(row=linha, column=2, value=tipo)
        ws.cell(row=linha, column=3, value=obra_id)
        ws.cell(row=linha, column=4, value=ent)
        ws.cell(row=linha, column=5, value=sai)
        ws.cell(row=linha, column=6, value=alm_i)
        ws.cell(row=linha, column=7, value=alm_f)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def test_importacao_excel_calcula_horas_e_preserva_obra_no_update():
    """🔴 O mês importado marcava 0h — nos dois ramos da rota.

    `processar_importacao` (`ponto_views.py:1496-1516`) gravava os horários e
    commitava sem passar por `PontoService._calcular_horas`: a folha lia
    `horas_trabalhadas = 0` e cobrava todo dia como falta cheia, e nenhum
    custo de obra saía. O ramo de ATUALIZAÇÃO ainda descartava `obra_id` e
    `tipo_registro` — reimportar a planilha corrigida apagava a obra do
    registro que já existia.
    """
    from models import Funcionario, RegistroPonto

    with app.app_context():
        t = um_tenant('onda3_imp', data_ref=DIA, com_fatos=False)
        codigo = db.session.get(Funcionario, t.funcionario_id).codigo

        # O dia que já tem registro (sem obra e sem horário): o ramo de update.
        db.session.add(RegistroPonto(
            funcionario_id=t.funcionario_id, admin_id=t.admin_id,
            data=OUTRO_DIA))
        db.session.commit()

        planilha = _planilha_de_ponto(codigo, [
            (DIA, 'TRAB', t.obra_id, '08:00', '17:00', '12:00', '13:00'),
            (OUTRO_DIA, 'TRAB', t.obra_id, '08:00', '17:00', '12:00', '13:00'),
        ])

        resposta = cliente_de(t.admin_id).post(
            '/ponto/importar/processar',
            data={'arquivo': (planilha, 'ponto.xlsx')},
            content_type='multipart/form-data')
        assert resposta.status_code in (200, 302), (
            f'rota respondeu {resposta.status_code}')

        novo = _registro(t, DIA)
        assert novo is not None, 'o registro novo não foi importado'
        assert novo.hora_entrada == time(8, 0)
        assert novo.horas_trabalhadas == pytest.approx(8.0), (
            f'8h-17h com 1h de almoço são 8h; veio '
            f'{novo.horas_trabalhadas} — a folha cobraria falta cheia')

        atualizado = _registro(t, OUTRO_DIA)
        assert atualizado is not None
        assert atualizado.hora_entrada == time(8, 0)
        assert atualizado.horas_trabalhadas == pytest.approx(8.0), (
            f'o ramo de atualização também precisa calcular; veio '
            f'{atualizado.horas_trabalhadas}')
        assert atualizado.obra_id == t.obra_id, (
            'o ramo de atualização descartou a obra da planilha — sem obra '
            'não há custo de obra')
        assert atualizado.tipo_registro == 'TRAB', (
            f'o ramo de atualização descartou o tipo; veio '
            f'{atualizado.tipo_registro!r}')
