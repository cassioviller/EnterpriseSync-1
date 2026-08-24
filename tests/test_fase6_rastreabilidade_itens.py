"""Fase 6 / Task 12 — diff entre duas versões, de proposta e de orçamento.

O aditivo pergunta "o que mudou da versão que o cliente aprovou para esta?".
Sem um diff, a resposta é ler duas listas lado a lado e confiar na memória —
que é exatamente como um item suprimido passa despercebido até a medição.

**O pareamento é por LINHAGEM, nunca por descrição.** Casar por texto produz
falso "mantido" quando alguém corrige uma vírgula no nome do serviço, e falso
"suprimido + incluído" quando renomeia de verdade. As duas tabelas guardam
linhagem, mas em convenções diferentes, e o diff tem de saber disso:

- `PropostaItem.proposta_item_origem_id` aponta para a **raiz** (o clone
  propaga a raiz, não o pai imediato) — `handlers/propostas_handlers.py:50`;
- `OrcamentoItem.item_origem_id` aponta para o **elo** (a revisão
  imediatamente anterior) — criado na migration 275.

Elo carrega mais informação que raiz: dá para reconstruir a raiz subindo a
corrente, e não o contrário. Por isso o diff do orçamento sobe.
"""
import os
import sys
from datetime import datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (Orcamento, OrcamentoItem, Proposta, PropostaItem,
                    TipoUsuario, Usuario)
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.integration

SITUACOES = {'mantido', 'alterado', 'incluido', 'suprimido'}


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


@pytest.fixture
def admin_id():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        suf = _suffix()
        u = Usuario(
            username=f'diff_{suf}', email=f'diff_{suf}@test.local',
            nome='Diff Fase 6',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid


def _por_situacao(linhas):
    fora = {l['situacao'] for l in linhas} - SITUACOES
    assert not fora, f'situações fora do contrato: {fora}'
    d = {}
    for l in linhas:
        item = l['destino'] or l['origem']
        d[item.descricao] = l
    return d


# ═══════════════════════════════════════════════════════════════════════════
# Orçamento — linhagem por ELO
# ═══════════════════════════════════════════════════════════════════════════

def _orcamento_v1(admin_id):
    suf = _suffix()
    orc = Orcamento(admin_id=admin_id, numero=f'ORC-D{suf[-9:]}',
                    titulo='Galpão', status='rascunho', criado_por=admin_id)
    db.session.add(orc)
    db.session.flush()
    for i, (desc, qtd, custo) in enumerate([
            ('Estrutura', 10, '1000.00'),
            ('Cobertura', 20, '500.00'),
            ('Piso', 5, '300.00')], start=1):
        db.session.add(OrcamentoItem(
            admin_id=admin_id, orcamento_id=orc.id, ordem=i, descricao=desc,
            unidade='m2', quantidade=Decimal(str(qtd)),
            venda_total=Decimal(custo)))
    db.session.commit()
    return orc


def _espelhar_valores(origem, destino):
    """Copia `venda_total` da revisão anterior para a nova, item a item.

    `criar_revisao` chama `recalcular_orcamento`, que deriva `venda_total` da
    `composicao_snapshot` — e estas fixtures não têm composição, porque o
    assunto aqui é o DIFF e não o motor de preço. Sem espelhar, todo item
    "mantido" viria com 0 contra o valor da v1 e o diff o chamaria de
    "alterado" por um artefato do teste, não por uma mudança de verdade.

    Espelhar é o que o motor faria sozinho se houvesse composição: revisar não
    muda preço, quem muda preço é quem edita a revisão depois.
    """
    por_raiz = {i.item_origem_id: i for i in destino.itens}
    for it in origem.itens:
        novo = por_raiz.get(it.id)
        if novo is not None:
            novo.venda_total = it.venda_total
    db.session.flush()


def test_diff_de_orcamento_classifica_as_quatro_situacoes(admin_id):
    """v1 → v2 com um mantido, um alterado, um incluído e um suprimido."""
    from services.orcamento_versao import criar_revisao, diff_revisoes

    with app.app_context():
        v1 = _orcamento_v1(admin_id)
        v2 = criar_revisao(v1, admin_id, motivo='aditivo')
        _espelhar_valores(v1, v2)
        db.session.commit()

        itens_v2 = {i.descricao: i for i in v2.itens}
        # Estrutura: MANTIDA (nada muda)
        # Cobertura: ALTERADA (quantidade e valor)
        itens_v2['Cobertura'].quantidade = Decimal('30')
        itens_v2['Cobertura'].venda_total = Decimal('800.00')
        # Piso: SUPRIMIDO
        db.session.delete(itens_v2['Piso'])
        # Pintura: INCLUÍDA
        db.session.add(OrcamentoItem(
            admin_id=admin_id, orcamento_id=v2.id, ordem=9, descricao='Pintura',
            unidade='m2', quantidade=Decimal('7'),
            venda_total=Decimal('700.00')))
        db.session.commit()

        linhas = diff_revisoes(v1, v2)
        por_desc = _por_situacao(linhas)

        assert por_desc['Estrutura']['situacao'] == 'mantido'
        assert por_desc['Cobertura']['situacao'] == 'alterado'
        assert por_desc['Piso']['situacao'] == 'suprimido'
        assert por_desc['Pintura']['situacao'] == 'incluido'

        # Os deltas de quem mudou, e None de quem não tem os dois lados.
        assert por_desc['Cobertura']['delta_quantidade'] == Decimal('10')
        assert por_desc['Cobertura']['delta_valor'] == Decimal('300.00')
        assert por_desc['Estrutura']['delta_valor'] == Decimal('0')
        assert por_desc['Piso']['destino'] is None
        assert por_desc['Pintura']['origem'] is None

        # O delta total é a soma dos itens dos dois lados — o cabeçalho
        # `venda_total` do orçamento é derivado da composição (ausente aqui),
        # então a conferência é feita contra os itens, que é o que o diff lê.
        soma = sum((l['delta_valor'] or Decimal('0')) for l in linhas)
        tot_v1 = sum(Decimal(str(i.venda_total or 0)) for i in v1.itens)
        tot_v2 = sum(Decimal(str(i.venda_total or 0)) for i in v2.itens)
        incl_sup = sum(
            Decimal(str((l['destino'] or l['origem']).venda_total or 0))
            * (1 if l['situacao'] == 'incluido' else -1)
            for l in linhas if l['situacao'] in ('incluido', 'suprimido'))
        assert soma + incl_sup == tot_v2 - tot_v1, (
            f'os deltas ({soma}) mais incluídos/suprimidos ({incl_sup}) não '
            f'fecham com a diferença dos itens ({tot_v2 - tot_v1}) — o diff '
            'está perdendo ou duplicando linha')


def test_diff_de_orcamento_nao_casa_por_descricao(admin_id):
    """Renomear a linha não a transforma em "suprimida + incluída".

    É o erro que o pareamento por texto comete, e o motivo de a linhagem
    existir.
    """
    from services.orcamento_versao import criar_revisao, diff_revisoes

    with app.app_context():
        v1 = _orcamento_v1(admin_id)
        v2 = criar_revisao(v1, admin_id, motivo='renomeia')
        _espelhar_valores(v1, v2)
        db.session.commit()
        item = {i.descricao: i for i in v2.itens}['Estrutura']
        item.descricao = 'Estrutura metálica (revisada)'
        db.session.commit()

        linhas = diff_revisoes(v1, v2)
        renomeada = [l for l in linhas
                     if l['destino'] is not None
                     and l['destino'].descricao.startswith('Estrutura met')]
        assert len(renomeada) == 1, 'o item renomeado apareceu duas vezes'
        assert renomeada[0]['situacao'] == 'alterado', (
            'renomear é ALTERAR — casar por descrição chamaria de '
            'suprimido + incluído')
        assert renomeada[0]['origem'].descricao == 'Estrutura'


def test_diff_de_orcamento_atravessa_revisoes_nao_adjacentes(admin_id):
    """v1 contra v3: o elo é do vizinho, então o diff sobe a corrente.

    Sem subir, todo item da v3 pareceria "incluído" e todo item da v1
    "suprimido" — um aditivo inteiro classificado errado.
    """
    from services.orcamento_versao import criar_revisao, diff_revisoes

    with app.app_context():
        v1 = _orcamento_v1(admin_id)
        v2 = criar_revisao(v1, admin_id, motivo='r2')
        _espelhar_valores(v1, v2)
        db.session.commit()
        v3 = criar_revisao(v2, admin_id, motivo='r3')
        _espelhar_valores(v2, v3)
        db.session.commit()

        linhas = diff_revisoes(v1, v3)
        assert {l['situacao'] for l in linhas} == {'mantido'}, (
            'v1 → v3 sem nenhuma mudança de conteúdo tem de ser tudo '
            f'"mantido", veio {sorted({l["situacao"] for l in linhas})}')
        assert len(linhas) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Proposta — linhagem por RAIZ, com fallback por item_numero
# ═══════════════════════════════════════════════════════════════════════════

def _proposta_v1(admin_id):
    suf = _suffix()
    p = Proposta(admin_id=admin_id, numero=f'PROP-D{suf[-9:]}',
                 titulo='Galpão', cliente_nome='C', status='rascunho',
                 versao=1, valor_total=Decimal('1800.00'))
    db.session.add(p)
    db.session.flush()
    for i, (desc, qtd, sub) in enumerate([
            ('Estrutura', 10, '1000.00'),
            ('Cobertura', 20, '500.00'),
            ('Piso', 5, '300.00')], start=1):
        db.session.add(PropostaItem(
            proposta_id=p.id, admin_id=admin_id, item_numero=i,
            descricao=desc, quantidade=Decimal(str(qtd)), unidade='m2',
            preco_unitario=Decimal(sub) / Decimal(str(qtd)),
            subtotal=Decimal(sub)))
    db.session.commit()
    return p


def test_diff_de_proposta_classifica_as_quatro_situacoes(admin_id):
    """Mesmo contrato do diff de orçamento, para os dois templates serem
    simétricos — e a linhagem por RAIZ, que é a convenção da proposta."""
    from services.proposta_diff import diff_versoes

    with app.app_context():
        v1 = _proposta_v1(admin_id)
        itens_v1 = {i.descricao: i for i in v1.itens}
        suf = _suffix()
        v2 = Proposta(admin_id=admin_id, numero=f'PROP-E{suf[-9:]}',
                      titulo='Galpão', cliente_nome='C', status='rascunho',
                      versao=2, proposta_origem_id=v1.id,
                      valor_total=Decimal('2500.00'))
        db.session.add(v2)
        db.session.flush()
        db.session.add_all([
            # mantido
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=1,
                         proposta_item_origem_id=itens_v1['Estrutura'].id,
                         descricao='Estrutura', quantidade=Decimal('10'),
                         unidade='m2', preco_unitario=Decimal('100'),
                         subtotal=Decimal('1000.00')),
            # alterado
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=2,
                         proposta_item_origem_id=itens_v1['Cobertura'].id,
                         descricao='Cobertura', quantidade=Decimal('30'),
                         unidade='m2', preco_unitario=Decimal('26.6667'),
                         subtotal=Decimal('800.00')),
            # incluido (sem linhagem — item novo de verdade)
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=4,
                         descricao='Pintura', quantidade=Decimal('7'),
                         unidade='m2', preco_unitario=Decimal('100'),
                         subtotal=Decimal('700.00')),
        ])
        # 'Piso' não entra: SUPRIMIDO
        db.session.commit()

        linhas = diff_versoes(v1, v2)
        por_desc = _por_situacao(linhas)
        assert por_desc['Estrutura']['situacao'] == 'mantido'
        assert por_desc['Cobertura']['situacao'] == 'alterado'
        assert por_desc['Piso']['situacao'] == 'suprimido'
        assert por_desc['Pintura']['situacao'] == 'incluido'
        assert por_desc['Cobertura']['delta_valor'] == Decimal('300.00')
        assert por_desc['Cobertura']['delta_quantidade'] == Decimal('10')

        # `delta_valor` é None para incluído/suprimido POR CONTRATO (zero
        # diria "não mudou"), então o impacto financeiro da revisão sai de
        # `total_do_diff`, que soma o valor cheio de quem entrou e subtrai o de
        # quem saiu. É o número que o extrato de contrato mostra como impacto
        # do aditivo, e ele tem de fechar com a diferença dos totais.
        from services.proposta_diff import total_do_diff
        total = total_do_diff(linhas)
        esperado = (Decimal(str(v2.valor_total)) - Decimal(str(v1.valor_total)))
        assert total == esperado, (
            f'impacto do diff {total} != diferença dos totais {esperado} — o '
            'diff perdeu ou duplicou linha')


def test_diff_de_proposta_usa_item_numero_quando_nao_ha_linhagem(admin_id):
    """Revisão anterior à Fase 0.6: os dois lados com `origem_id` NULL.

    Sem o fallback por `item_numero`, cada lado seria raiz de si mesmo e
    NADA casaria — a revisão inteira apareceria como suprimida + incluída.
    É o mesmo fallback que `handlers/propostas_handlers._chaves_de_linhagem`
    já aplica na propagação para a obra.
    """
    from services.proposta_diff import diff_versoes

    with app.app_context():
        v1 = _proposta_v1(admin_id)
        suf = _suffix()
        v2 = Proposta(admin_id=admin_id, numero=f'PROP-L{suf[-9:]}',
                      titulo='Galpão', cliente_nome='C', status='rascunho',
                      versao=2, proposta_origem_id=v1.id,
                      valor_total=Decimal('2000.00'))
        db.session.add(v2)
        db.session.flush()
        db.session.add_all([
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=1,
                         descricao='Estrutura', quantidade=Decimal('10'),
                         unidade='m2', preco_unitario=Decimal('120'),
                         subtotal=Decimal('1200.00')),
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=2,
                         descricao='Cobertura', quantidade=Decimal('20'),
                         unidade='m2', preco_unitario=Decimal('25'),
                         subtotal=Decimal('500.00')),
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=3,
                         descricao='Piso', quantidade=Decimal('5'),
                         unidade='m2', preco_unitario=Decimal('60'),
                         subtotal=Decimal('300.00')),
        ])
        db.session.commit()

        linhas = diff_versoes(v1, v2)
        situacoes = {l['situacao'] for l in linhas}
        assert 'incluido' not in situacoes and 'suprimido' not in situacoes, (
            'sem linhagem explícita o fallback por item_numero tem de casar — '
            f'veio {sorted(situacoes)}')
        por_desc = _por_situacao(linhas)
        assert por_desc['Estrutura']['situacao'] == 'alterado'
        assert por_desc['Cobertura']['situacao'] == 'mantido'


# ═══════════════════════════════════════════════════════════════════════════
# As duas telas — template só se prova renderizando
# ═══════════════════════════════════════════════════════════════════════════

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_tela_de_comparacao_de_orcamento_renderiza(admin_id):
    """GET na rota de comparação devolve 200 e mostra as quatro situações.

    O `with app.app_context()` fecha ANTES do request de propósito: o
    `test_client` reusa o app context ativo, e com ele aberto a requisição
    rodaria na sessão do teste, lendo objetos do identity map em vez do banco.
    """
    from services.orcamento_versao import criar_revisao

    with app.app_context():
        v1 = _orcamento_v1(admin_id)
        v2 = criar_revisao(v1, admin_id, motivo='aditivo de cobertura')
        _espelhar_valores(v1, v2)
        db.session.flush()
        itens_v2 = {i.descricao: i for i in v2.itens}
        itens_v2['Cobertura'].quantidade = Decimal('30')
        itens_v2['Cobertura'].venda_total = Decimal('800.00')
        db.session.delete(itens_v2['Piso'])
        db.session.add(OrcamentoItem(
            admin_id=admin_id, orcamento_id=v2.id, ordem=9,
            descricao='Pintura', unidade='m2', quantidade=Decimal('7'),
            venda_total=Decimal('700.00')))
        db.session.commit()
        ids = (v1.id, v2.id)

    r = _cliente_de(admin_id).get(f'/orcamentos/{ids[0]}/comparar/{ids[1]}')
    assert r.status_code == 200, f'a tela não renderizou ({r.status_code})'
    html = r.get_data(as_text=True)
    for rotulo in ('Mantido', 'Alterado', 'Incluído', 'Suprimido'):
        assert rotulo in html, f'a tela não mostra "{rotulo}"'
    assert 'aditivo de cobertura' in html, 'o motivo da revisão não aparece'


def test_tela_de_comparacao_de_proposta_renderiza(admin_id):
    """Mesmo smoke do lado da proposta — os dois templates são simétricos."""
    with app.app_context():
        v1 = _proposta_v1(admin_id)
        itens_v1 = {i.descricao: i for i in v1.itens}
        suf = _suffix()
        v2 = Proposta(admin_id=admin_id, numero=f'PROP-T{suf[-9:]}',
                      titulo='Galpão', cliente_nome='C', status='rascunho',
                      versao=2, proposta_origem_id=v1.id,
                      valor_total=Decimal('2500.00'))
        db.session.add(v2)
        db.session.flush()
        db.session.add_all([
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=1,
                         proposta_item_origem_id=itens_v1['Estrutura'].id,
                         descricao='Estrutura', quantidade=Decimal('10'),
                         unidade='m2', preco_unitario=Decimal('100'),
                         subtotal=Decimal('1000.00')),
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=2,
                         proposta_item_origem_id=itens_v1['Cobertura'].id,
                         descricao='Cobertura', quantidade=Decimal('30'),
                         unidade='m2', preco_unitario=Decimal('26.67'),
                         subtotal=Decimal('800.00')),
            PropostaItem(proposta_id=v2.id, admin_id=admin_id, item_numero=4,
                         descricao='Pintura', quantidade=Decimal('7'),
                         unidade='m2', preco_unitario=Decimal('100'),
                         subtotal=Decimal('700.00')),
        ])
        db.session.commit()
        ids = (v1.id, v2.id)

    r = _cliente_de(admin_id).get(f'/propostas/{ids[0]}/comparar/{ids[1]}')
    assert r.status_code == 200, f'a tela não renderizou ({r.status_code})'
    html = r.get_data(as_text=True)
    for rotulo in ('Mantido', 'Alterado', 'Incluído', 'Suprimido'):
        assert rotulo in html, f'a tela não mostra "{rotulo}"'


def test_comparar_nao_atravessa_tenant(admin_id):
    """Comparar é leitura — e leitura cruzada entre tenants é vazamento."""
    from services.orcamento_versao import criar_revisao

    with app.app_context():
        v1 = _orcamento_v1(admin_id)
        v2 = criar_revisao(v1, admin_id, motivo='r2')
        db.session.commit()
        suf = _suffix()
        outro = Usuario(
            username=f'diff_x_{suf}', email=f'diff_x_{suf}@test.local',
            nome='Outro tenant',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(outro)
        db.session.commit()
        ids, outro_id = (v1.id, v2.id), outro.id

    r = _cliente_de(outro_id).get(f'/orcamentos/{ids[0]}/comparar/{ids[1]}')
    assert r.status_code == 404, (
        f'tenant alheio conseguiu comparar orçamento de outro ({r.status_code})')
