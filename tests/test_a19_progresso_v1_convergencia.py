"""A19 — os quatro consumidores da família V1 devolvem O MESMO número.

Enquanto `test_a19_progresso_v1_ponto_unico.py` prova que a função nova calcula
certo, este arquivo prova que **os consumidores a chamam** — que é outra coisa, e
é a que o pacote p4 não provou quando declarou "cinco fórmulas viram uma" com o
gate verde. Os testes do p4 abrem arquivos e procuram o nome da função como
substring: `views/rdo.py`, `services/rdo_pdf_service.py` e `crud_rdo_completo.py`
**não são abertos por teste nenhum de lá**, e um `in texto` fica verdadeiro assim
que o nome aparece num comentário ou num ramo morto.

## A semente, e por que cada peça dela é assim

Obra **sem nenhuma `TarefaCronograma`**, o que força o ramo V1 nos quatro pontos
de uma vez. Dois serviços, S1 e S2, **cada um com uma subatividade chamada
'Preparação'** — o homônimo é deliberado: é o que separa a chave composta da
chave só por nome. Datas ancoradas na semente (10, 11 e 12 de junho de 2026),
nunca `date.today()`.

| Chave | 10/06 | 11/06 | 12/06 |
|---|---|---|---|
| (S1, 'Preparação') | 30 | 60 | **40** ← correção para baixo |
| (S2, 'Preparação') | 20 | — | — |
| (S1, 'Corte') | — | 100 | — |

**Até 11/06 o número certo é 60.0** — média dos máximos de TRÊS chaves compostas:
60, 20 e 100, sobre 3. Antes desta trilha, nenhum dos quatro devolvia isso: o
detalhe dividia pelo catálogo mestre, o PDF e a consolidada fundiam os dois
'Preparação' num MAX=60 e davam (60+100)/2 = **80**, e a lista ignorava o teto de
data e usava o 40 do dia 12.
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import RDO, RDOServicoSubatividade, Servico

from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

D10, D11, D12 = date(2026, 6, 10), date(2026, 6, 11), date(2026, 6, 12)

# Média dos máximos de (S1,'Preparação')=60, (S2,'Preparação')=20, (S1,'Corte')=100.
ESPERADO_ATE_11 = 60.0


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a19-conv'
    yield


def _semear(marca):
    """Tenant + dois serviços homônimos + três RDOs. Devolve (tenant, rdos)."""
    t = um_tenant(marca, data_ref=D11, com_fatos=False)

    s1 = Servico(nome=f'S1 {t.marca}', categoria='geral', unidade_medida='m2',
                 custo_unitario=10.0, ativo=True, admin_id=t.admin_id)
    s2 = Servico(nome=f'S2 {t.marca}', categoria='geral', unidade_medida='m2',
                 custo_unitario=10.0, ativo=True, admin_id=t.admin_id)
    db.session.add_all([s1, s2])
    db.session.flush()

    rdos = {}
    for dia in (D10, D11, D12):
        r = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:8]}', obra_id=t.obra_id,
                data_relatorio=dia, admin_id=t.admin_id,
                criado_por_id=t.admin_id)
        db.session.add(r)
        db.session.flush()
        rdos[dia] = r

    def _sub(dia, servico, nome, pct):
        db.session.add(RDOServicoSubatividade(
            rdo_id=rdos[dia].id, servico_id=servico.id,
            nome_subatividade=nome, percentual_conclusao=pct,
            admin_id=t.admin_id))

    _sub(D10, s1, 'Preparação', 30.0)
    _sub(D11, s1, 'Preparação', 60.0)
    _sub(D12, s1, 'Preparação', 40.0)   # a correção para baixo
    _sub(D10, s2, 'Preparação', 20.0)   # homônimo, outro serviço
    _sub(D11, s1, 'Corte', 100.0)
    db.session.commit()
    return t, rdos


def _pct_da_tela(corpo):
    """O percentual do card, de `visualizar_rdo_moderno.html:1256`."""
    import re
    m = re.search(r'stat-number">([\d.,]+)%</div>\s*<div class="stat-label">'
                  r'Progresso da Obra', corpo)
    assert m, 'o card "Progresso da Obra" não foi encontrado no corpo'
    return float(m.group(1).replace(',', '.'))


# ---------------------------------------------------------------------------
# B2.9 — PDF e tela
# ---------------------------------------------------------------------------

def test_pdf_e_tela_do_mesmo_rdo_nao_divergem():
    """A razão de a B2.9 ser um commit só, e não dois.

    Este PDF é o documento por trás do ato de ciência do cliente. Separar as duas
    correções abriria uma janela — de horas ou de semanas — em que o papel que o
    cliente assina e a tela que o apontador vê mostram percentuais diferentes
    para o mesmo RDO, e ninguém saberia qual dos dois está certo.

    O número do PDF sai chamando `_progresso_geral` com o mesmo `rdo` (os bytes
    do PDF não são inspecionáveis, mas é exatamente a função que a geração usa);
    o da tela sai do HTML renderizado.
    """
    from services.rdo_pdf_service import _progresso_geral

    with app.app_context():
        t, rdos = _semear('a19pdf')
        rdo_11 = rdos[D11]

        r = cliente_de(t.admin_id).get(f'/rdo/{rdo_11.id}')
        assert r.status_code == 200, f'a tela respondeu {r.status_code}'
        da_tela = _pct_da_tela(r.get_data(as_text=True))
        do_pdf = round(_progresso_geral(rdo_11), 1)

        assert da_tela == pytest.approx(do_pdf), (
            f'tela diz {da_tela}% e PDF diz {do_pdf}% para o MESMO RDO')
        assert da_tela == pytest.approx(ESPERADO_ATE_11), (
            f'os dois convergiram em {da_tela}%, mas o certo é '
            f'{ESPERADO_ATE_11}% — 80.0 é o sintoma de homônimos fundidos '
            f'((60+100)/2), e convergir no número errado não resolve nada')


def test_a_correcao_para_baixo_nao_derruba_o_numero_do_pdf():
    """Monotonicidade na ponta que vira papel.

    No dia 12 a (S1,'Preparação') foi corrigida de 60 para 40. O percentual do
    dia 12 não pode ser menor que o do dia 11 — nada foi desfeito na obra.
    """
    from services.rdo_pdf_service import _progresso_geral

    with app.app_context():
        _t, rdos = _semear('a19mon')

        ate_11 = _progresso_geral(rdos[D11])
        ate_12 = _progresso_geral(rdos[D12])

        assert ate_12 >= ate_11, (
            f'PDF do dia 12 diz {ate_12}% e o do dia 11 diz {ate_11}% — a '
            f'correção de 60 para 40 derrubou o progresso da obra')


# ---------------------------------------------------------------------------
# B2.11 — a lista de RDOs
# ---------------------------------------------------------------------------

def test_cada_linha_da_lista_mostra_o_acumulado_da_propria_data():
    """O cache era por `obra_id`, sem teto de data.

    Consequência: **toda linha da lista de RDOs da mesma obra exibia o mesmo
    número** — o de hoje. Um RDO de 10/06 mostrava o progresso de 12/06, o que
    torna a lista inútil justamente para o que ela serve: ver a evolução.

    Pior, a consulta pegava "o mais recente por nome" em vez do máximo, então a
    correção de 60 para 40 no dia 12 derrubava o número de **todas** as linhas
    de uma vez, inclusive as de dias anteriores, onde 40 nunca foi verdade.

    As três datas da semente têm acumulados distintos, e é isso que se afirma:

    * até 10/06 — (S1,'Prep')=30 e (S2,'Prep')=20 → **25.0**
    * até 11/06 — mais (S1,'Corte')=100, e 'Prep' de S1 sobe a 60 → **60.0**
    * até 12/06 — o 40 não derruba o 60 → **60.0**
    """
    from utils.cronograma_engine import progresso_v1_acumulado

    with app.app_context():
        t, _rdos = _semear('a19lista')

        ate_10 = progresso_v1_acumulado(t.obra_id, t.admin_id, D10)
        ate_11 = progresso_v1_acumulado(t.obra_id, t.admin_id, D11)
        ate_12 = progresso_v1_acumulado(t.obra_id, t.admin_id, D12)

        assert ate_10 == pytest.approx(25.0), (
            f'até 10/06 deu {ate_10} — as três datas têm de ser distinguíveis, '
            f'senão o teto de data não está sendo respeitado')
        assert ate_11 == pytest.approx(ESPERADO_ATE_11)
        assert ate_12 == pytest.approx(ESPERADO_ATE_11), (
            f'até 12/06 deu {ate_12} — o 40 do dia 12 derrubou o 60 do dia 11')

        # A lista responde, e responde com o número da data mais recente
        # visível — a asserção fina por linha exige parsear a tabela inteira;
        # o que trava a regressão de cache é a distinção acima.
        r = cliente_de(t.admin_id).get('/rdo/lista')
        assert r.status_code == 200, f'a lista respondeu {r.status_code}'


# ---------------------------------------------------------------------------
# B2.12 — o sétimo call-site, e a convergência das quatro pontas
# ---------------------------------------------------------------------------

def test_rdo_de_dia_sem_subatividade_nao_exibe_zero_numa_obra_avancada():
    """O defeito da variante D, e o que o `elif subatividades:` causava.

    `crud_rdo_completo.listar_rdos` fazia `sum(...)/len(...)` sobre as
    subatividades **daquele RDO**: não acumulava nada. Uma obra V1 a 60% cujo
    RDO do dia não teve subatividade nenhuma aparecia com **0** na lista.

    🔴 **`listar_rdos` está SOMBREADA, e isso foi descoberto escrevendo este
    teste.** `views/rdo.py:rdos()` registra `/rdos`, `/rdo`, `/rdo/` **e**
    `/rdo/lista` no `main_bp`, e as três URLs do prefixo resolvem para ela —
    `rdo_crud.listar_rdos` existe no `url_map` e nunca recebe requisição. Ver o
    Status da B2.12 no plano.

    Por isso o teste chama a função **dentro de um request context**, em vez de
    fingir que um GET a alcança: fingir seria o instrumento medindo o vazio de
    novo, e mais insidioso, porque passaria.
    """
    import re

    from flask_login import login_user

    from crud_rdo_completo import listar_rdos
    from models import Usuario
    from utils.cronograma_engine import progresso_v1_acumulado

    with app.app_context():
        t, _rdos = _semear('a19vazio')

        d13 = date(2026, 6, 13)
        vazio = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:8]}', obra_id=t.obra_id,
                    data_relatorio=d13, admin_id=t.admin_id,
                    criado_por_id=t.admin_id)
        db.session.add(vazio)
        db.session.commit()

        assert RDOServicoSubatividade.query.filter_by(rdo_id=vazio.id).count() == 0, (
            'cenário quebrado — o RDO do dia 13 tem de estar sem subatividade')
        assert progresso_v1_acumulado(
            t.obra_id, t.admin_id, d13) == pytest.approx(ESPERADO_ATE_11), (
            'o acumulado da obra até 13/06 não é o esperado — cenário quebrado')

        admin = db.session.get(Usuario, t.admin_id)
        with app.test_request_context('/rdo/'):
            login_user(admin)
            corpo = listar_rdos()

        percentuais = {float(p) for p in
                       re.findall(r'<strong>([\d.]+)%</strong>', corpo)}
        assert percentuais, 'nenhum percentual foi renderizado pela listar_rdos'
        assert 0.0 not in percentuais, (
            f'apareceu 0.0% ({sorted(percentuais)}) — é o RDO sem subatividade '
            f'mostrando o progresso DO DIA numa obra que está a '
            f'{ESPERADO_ATE_11}%')
        assert 'Progresso do dia' not in corpo, (
            'o rótulo ainda diz "do dia", descrevendo o cálculo antigo')


def test_a_tela_do_rdo_nao_grava_nada():
    """Item 100% de LEITURA — e a asserção é a negativa.

    Um `commit()` acidental num caminho de listagem ou de visualização é a
    classe de regressão que ninguém vê: a tela continua certa, e o banco muda.
    """
    with app.app_context():
        t, rdos = _semear('a19ro')

        antes = [(s.id, s.percentual_conclusao) for s in
                 RDOServicoSubatividade.query
                 .join(RDO, RDOServicoSubatividade.rdo_id == RDO.id)
                 .filter(RDO.obra_id == t.obra_id)
                 .order_by(RDOServicoSubatividade.id).all()]

        cliente_de(t.admin_id).get(f'/rdo/{rdos[D11].id}')

        db.session.expire_all()
        depois = [(s.id, s.percentual_conclusao) for s in
                  RDOServicoSubatividade.query
                  .join(RDO, RDOServicoSubatividade.rdo_id == RDO.id)
                  .filter(RDO.obra_id == t.obra_id)
                  .order_by(RDOServicoSubatividade.id).all()]

        assert antes == depois, 'o GET do RDO alterou percentuais no banco'
