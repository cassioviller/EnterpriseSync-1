"""
tests/test_importar_composicoes.py

Valida o importador de Composições via Excel
(``services.catalogo_excel.importar_composicoes_xlsx``):

- planilha válida cria Serviço + Composições;
- insumo inexistente rejeita a linha (não cria serviço órfão);
- coeficiente inválido rejeita a linha;
- reimportação com coeficiente novo atualiza e grava histórico;
- reimportação idêntica não altera nada.

Como o importador faz ``commit`` interno, os dados de teste são limpos no
teardown por prefixo de nome (não dá para confiar só em rollback).
"""
import io
import os
import sys
from decimal import Decimal

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db
from models import (
    ComposicaoServico,
    ComposicaoServicoHistorico,
    Insumo,
    PrecoBaseInsumo,
    Servico,
    Usuario,
)
from services.catalogo_excel import importar_composicoes_xlsx

PREFIX = '__test_compimp_'
HEADER = [
    'servico_nome', 'servico_unidade', 'categoria',
    'insumo_nome', 'coeficiente', 'unidade_insumo', 'observacao',
]


def _pick_admin_id():
    u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
    if u is None:
        pytest.skip('Sem usuário no banco')
    return u.id


def _cleanup(aid):
    svc_ids = [s.id for s in Servico.query.filter(
        Servico.admin_id == aid, Servico.nome.like(PREFIX + '%')).all()]
    ins_ids = [i.id for i in Insumo.query.filter(
        Insumo.admin_id == aid, Insumo.nome.like(PREFIX + '%')).all()]
    if svc_ids:
        ComposicaoServicoHistorico.query.filter(
            ComposicaoServicoHistorico.servico_id.in_(svc_ids)
        ).delete(synchronize_session=False)
        ComposicaoServico.query.filter(
            ComposicaoServico.servico_id.in_(svc_ids)
        ).delete(synchronize_session=False)
        Servico.query.filter(Servico.id.in_(svc_ids)).delete(synchronize_session=False)
    if ins_ids:
        PrecoBaseInsumo.query.filter(
            PrecoBaseInsumo.insumo_id.in_(ins_ids)
        ).delete(synchronize_session=False)
        Insumo.query.filter(Insumo.id.in_(ins_ids)).delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture(scope='function')
def admin_id():
    with app.app_context():
        aid = _pick_admin_id()
        _cleanup(aid)  # garante estado limpo antes
        try:
            yield aid
        finally:
            _cleanup(aid)


def _mk_insumo(aid, nome, tipo='MATERIAL', unidade='kg'):
    ins = Insumo(admin_id=aid, nome=nome, tipo=tipo, unidade=unidade)
    db.session.add(ins)
    db.session.commit()
    return ins


def _xlsx(rows, header=HEADER):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Composicoes'
    ws.append(header)
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def _svc(aid, nome):
    return Servico.query.filter_by(admin_id=aid, nome=nome).first()


# ──────────────────────────────────────────────────────────────────────

def test_planilha_valida_cria_servico_e_composicoes(admin_id):
    _mk_insumo(admin_id, PREFIX + 'aco', tipo='MATERIAL', unidade='kg')
    _mk_insumo(admin_id, PREFIX + 'montador', tipo='MAO_OBRA', unidade='h')
    svc_nome = PREFIX + 'estrutura_lsf'

    arq = _xlsx([
        [svc_nome, 'kg', 'Estrutura', PREFIX + 'aco', '1,05', 'kg', 'perda 5%'],
        [svc_nome, 'kg', 'Estrutura', PREFIX + 'montador', '0,014', 'h', 'h/kg'],
    ])
    res = importar_composicoes_xlsx(arq, admin_id)

    assert res['servicos_created'] == 1
    assert res['servicos_updated'] == 0
    assert res['composicoes_created'] == 2
    assert res['composicoes_updated'] == 0
    assert res['rejected'] == []

    svc = _svc(admin_id, svc_nome)
    assert svc is not None
    assert svc.unidade_medida == 'kg'
    assert svc.categoria == 'Estrutura'
    comps = {c.insumo.nome: c for c in svc.composicoes}
    assert comps[PREFIX + 'aco'].coeficiente == Decimal('1.05')
    assert comps[PREFIX + 'montador'].coeficiente == Decimal('0.014')
    assert comps[PREFIX + 'aco'].observacao == 'perda 5%'


def test_insumo_inexistente_rejeita_linha(admin_id):
    svc_nome = PREFIX + 'svc_sem_insumo'
    arq = _xlsx([
        [svc_nome, 'kg', 'Estrutura', PREFIX + 'nao_existe', '1,0', 'kg', ''],
    ])
    res = importar_composicoes_xlsx(arq, admin_id)

    assert res['composicoes_created'] == 0
    assert res['servicos_created'] == 0  # não cria serviço órfão
    assert len(res['rejected']) == 1
    assert 'não encontrado' in res['rejected'][0]['motivo']
    assert _svc(admin_id, svc_nome) is None


def test_coeficiente_invalido_rejeita_linha(admin_id):
    _mk_insumo(admin_id, PREFIX + 'aco', tipo='MATERIAL', unidade='kg')
    arq = _xlsx([
        [PREFIX + 'svc_x', 'kg', 'Estrutura', PREFIX + 'aco', 'abc', 'kg', ''],
    ])
    res = importar_composicoes_xlsx(arq, admin_id)

    assert res['composicoes_created'] == 0
    assert len(res['rejected']) == 1
    assert 'coeficiente inválido' in res['rejected'][0]['motivo']


def test_reimportacao_atualiza_coeficiente_e_grava_historico(admin_id):
    _mk_insumo(admin_id, PREFIX + 'aco', tipo='MATERIAL', unidade='kg')
    svc_nome = PREFIX + 'estrutura_lsf'

    importar_composicoes_xlsx(
        _xlsx([[svc_nome, 'kg', 'Estrutura', PREFIX + 'aco', '1,05', 'kg', '']]),
        admin_id,
    )
    res2 = importar_composicoes_xlsx(
        _xlsx([[svc_nome, 'kg', 'Estrutura', PREFIX + 'aco', '1,10', 'kg', '']]),
        admin_id,
    )

    assert res2['servicos_created'] == 0
    assert res2['composicoes_created'] == 0
    assert res2['composicoes_updated'] == 1

    svc = _svc(admin_id, svc_nome)
    comp = svc.composicoes[0]
    assert comp.coeficiente == Decimal('1.10')

    hist = ComposicaoServicoHistorico.query.filter_by(
        composicao_servico_id=comp.id
    ).all()
    assert len(hist) == 1
    assert hist[0].coeficiente_anterior == Decimal('1.05')
    assert hist[0].coeficiente_novo == Decimal('1.10')


def test_reimportacao_identica_nao_altera(admin_id):
    _mk_insumo(admin_id, PREFIX + 'aco', tipo='MATERIAL', unidade='kg')
    svc_nome = PREFIX + 'estrutura_lsf'
    linha = [[svc_nome, 'kg', 'Estrutura', PREFIX + 'aco', '1,05', 'kg', '']]

    importar_composicoes_xlsx(_xlsx(linha), admin_id)
    res2 = importar_composicoes_xlsx(_xlsx(linha), admin_id)

    assert res2['composicoes_created'] == 0
    assert res2['composicoes_updated'] == 0

    svc = _svc(admin_id, svc_nome)
    comp = svc.composicoes[0]
    hist = ComposicaoServicoHistorico.query.filter_by(
        composicao_servico_id=comp.id
    ).count()
    assert hist == 0
