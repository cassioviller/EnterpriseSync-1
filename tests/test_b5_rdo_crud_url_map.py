"""B5.4 — o url_map do `rdo_crud` CONGELADO, para ninguém remedir no escuro.

Task B5.4 de `docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`.

**Por que este teste existe.** A dívida do sombreamento (§8.3 do plano
consolidado) quase virou "aposentar o blueprint inteiro" — e 🔬 9 das 13 rotas
são o ÚNICO handler do seu path, cinco delas o backend de foto de TODAS as
telas de RDO, consumidas por `fetch()` com path literal
(`templates/rdo/editar_rdo.html:1286/1333/1398/1419`) que nenhum grep por
símbolo encontra. Este arquivo afirma o placar medido — quem mudar o despacho
(registrar/desregistrar rota, mudar a ordem em `main.py`) fica sabendo na hora,
em vez de acordar uma função sombreada com defeito dentro ou matar o upload de
foto sem querer.

**Placar da rodada (antes do corte da B5.4): 4 sombreadas / 9 vencedoras /
1 sem rota.** A B5.4 corta as duas rotas de API mortas (`/rdo/api/...`), e o
placar passa a 4 / 7 / 1 — este arquivo nasce afirmando o estado PÓS-corte,
com as duas ausências afirmadas explicitamente.

⚠️ Medir o `url_map` exige os blueprints de `main.py` — `from app import app`
puro registra OUTRO conjunto de rotas (`main.py:11/:25`; nota da §2 da rodada).
O import de `main` abaixo não é cosmético.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — sem isto o url_map medido é o de outro app
from app import app


def _quem_atende(path, method='GET'):
    """Endpoint que VENCE o despacho para este path — o que o gunicorn faria."""
    adapter = app.url_map.bind('localhost')
    endpoint, _args = adapter.match(path, method=method)
    return endpoint


def _regras_do_endpoint(endpoint):
    return [r for r in app.url_map.iter_rules() if r.endpoint == endpoint]


def test_as_quatro_sombreadas_continuam_sombreadas():
    """As rotas do rdo_crud que existem no url_map e NUNCA recebem requisição.

    Se uma delas passar a vencer, quem venceu até hoje deixou de atender — ou
    alguém desregistrou a rota do main_bp e ACORDOU a função sombreada. As
    duas hipóteses merecem barulho (foi o caso do laço 302 latente de
    `rdo_crud.editar_rdo`, que só faz redirect para a URL que ela mesma
    atende).
    """
    assert _quem_atende('/rdo/') == 'main.rdos'
    assert _quem_atende('/rdo/novo') == 'main.novo_rdo'
    assert _quem_atende('/rdo/editar/1') == 'rdo_editar.editar_rdo_form'
    assert _quem_atende('/rdo/excluir/1', method='POST') == 'main.excluir_rdo'
    # ...e as quatro seguem REGISTRADAS (sombreada ≠ removida): url_for por
    # endpoint ainda constrói — `crud_rdo_completo.py:587/:595/:645/:651`
    # dependem disso.
    for ep in ('rdo_crud.listar_rdos', 'rdo_crud.novo_rdo',
               'rdo_crud.editar_rdo', 'rdo_crud.excluir_rdo'):
        assert _regras_do_endpoint(ep), f'{ep} sumiu do url_map'


def test_as_sete_vencedoras_continuam_vencendo():
    """As rotas do rdo_crud que SÃO o handler do seu path. As cinco de foto
    são o backend de upload/galeria/legenda/delete/serviço de imagem de todas
    as telas de RDO — aposentá-las derruba o subsistema de foto (6.647 fotos
    em disco em ⚠️ dev só renderizam por `servir_foto`)."""
    assert _quem_atende('/rdo/visualizar/1') == 'rdo_crud.visualizar_rdo'
    assert _quem_atende('/rdo/finalizar/1', method='POST') == 'rdo_crud.finalizar_rdo'
    assert _quem_atende('/rdo/1/fotos/upload', method='POST') == 'rdo_crud.upload_foto_rdo'
    assert _quem_atende('/rdo/foto/1/original') == 'rdo_crud.servir_foto'
    assert _quem_atende('/rdo/1/fotos') == 'rdo_crud.listar_fotos_rdo'
    assert _quem_atende('/rdo/foto/1/editar', method='POST') == 'rdo_crud.editar_descricao_foto'
    assert _quem_atende('/rdo/foto/1/deletar', method='POST') == 'rdo_crud.deletar_foto'


def test_as_duas_apis_cortadas_pela_b54_nao_existem():
    """`/rdo/api/subatividades/<id>` e `/rdo/api/funcionarios` venciam o
    despacho e tinham 🔬 zero consumidor em templates/static/views/services/
    docs/tests/n8n — inclusive por URL relativa. A B5.4 cortou os decoradores;
    as funções ficam (documentadas), as rotas não."""
    from werkzeug.exceptions import NotFound
    import pytest as _pytest

    adapter = app.url_map.bind('localhost')
    with _pytest.raises(NotFound):
        adapter.match('/rdo/api/subatividades/1')
    with _pytest.raises(NotFound):
        adapter.match('/rdo/api/funcionarios')
    assert not _regras_do_endpoint('rdo_crud.api_subatividades_por_servico')
    assert not _regras_do_endpoint('rdo_crud.api_funcionarios')


def test_salvar_rdo_segue_sem_rota():
    """`salvar_rdo()` perdeu o decorador em `b30923b5` e ficou como código
    documentado (`crud_rdo_completo.py:249-254`). Se alguém devolver a rota,
    `/rdo/salvar` tem dono vivo (`main.rdo_salvar_unificado`) e a colisão
    precisa ser decidida, não herdada."""
    assert _quem_atende('/rdo/salvar', method='POST') == 'main.rdo_salvar_unificado'
    assert not _regras_do_endpoint('rdo_crud.salvar_rdo')
