"""Módulo 01 / passo 5 — a rota POST /rdo/salvar tem dono único e determinístico.

Antes deste passo, `/rdo/salvar` tinha DUAS regras no url_map:
`main.rdo_salvar_unificado` (registrada por app.py:463) e
`rdo_crud.salvar_rdo` (registrada por main.py:24). A primeira sempre
vencia — ambas são estáticas e têm os mesmos métodos, então o Werkzeug
decide por ordem de inserção. A segunda era inalcançável por construção.
"""
from app import app


def test_post_rdo_salvar_resolve_para_rdo_salvar_unificado():
    """O dono de POST /rdo/salvar não pode mudar sem quebrar este teste."""
    adapter = app.url_map.bind('localhost')
    endpoint, _args = adapter.match('/rdo/salvar', method='POST')
    assert endpoint == 'main.rdo_salvar_unificado'


def test_salvar_rdo_flexivel_tem_url_propria():
    """O fluxo principal NÃO colide com /rdo/salvar — URL distinta."""
    adapter = app.url_map.bind('localhost')
    endpoint, _args = adapter.match('/salvar-rdo-flexivel', method='POST')
    assert endpoint == 'main.salvar_rdo_flexivel'


def test_rdo_salvar_tem_exatamente_uma_regra():
    """Uma segunda regra em /rdo/salvar é inalcançável e engana quem lê o código."""
    regras = [r for r in app.url_map.iter_rules() if r.rule == '/rdo/salvar']
    endpoints = sorted(r.endpoint for r in regras)
    assert endpoints == ['main.rdo_salvar_unificado'], (
        f'esperava dono único, encontrei {endpoints}'
    )
