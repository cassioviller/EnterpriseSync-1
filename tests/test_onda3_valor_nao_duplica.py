"""Onda 3 — o valor para de duplicar ou sumir.

O arreio de tenant é `tests/helpers_tenant.py`. Aqui o que se prova é
aritmética de saldo e disciplina de pai×filho, não isolamento.
"""
import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant  # noqa: F401

pytestmark = pytest.mark.integration

_QUANDO = datetime(2026, 6, 15, 8, 0)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-valor'
    yield


def _item_consumivel(admin_id):
    # ⚠️ Duas armadilhas do schema: o campo é `unidade` (`models.py:5531`), não
    # `unidade_medida`; e `almoxarifado_item.categoria_id` é NOT NULL no banco,
    # então o item precisa de categoria própria do tenant.
    from models import AlmoxarifadoCategoria, AlmoxarifadoItem
    suf = uuid.uuid4().hex[:8]
    categoria = AlmoxarifadoCategoria(
        admin_id=admin_id, nome=f'Materiais {suf}',
        tipo_controle_padrao='CONSUMIVEL')
    db.session.add(categoria)
    db.session.flush()
    item = AlmoxarifadoItem(
        admin_id=admin_id, nome=f'Cimento {suf}', codigo=f'CIM{suf}',
        categoria_id=categoria.id,
        tipo_controle='CONSUMIVEL', unidade='SC',
        permite_devolucao=True)
    db.session.add(item)
    db.session.flush()
    return item


# ---------------------------------------------------------------------------
# Task 1 — a unidade sai uma vez só
# ---------------------------------------------------------------------------

def test_lote_novo_nasce_com_as_tres_colunas_coerentes():
    """🔴 A entrada manual criava lote com `quantidade_disponivel = NULL`.

    A saída valida em `func.sum(quantidade_disponivel)`
    (`views/almoxarifado/movimentos.py:597`): com NULL, a guarda vê 0 e
    RECUSA material que existe.
    """
    from services.estoque_saldo import criar_lote

    with app.app_context():
        t = um_tenant('onda3_lote', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('100'), t.admin_id)
        db.session.flush()

        assert lote.quantidade == Decimal('100')
        assert lote.quantidade_inicial == Decimal('100')
        assert lote.quantidade_disponivel == Decimal('100')


def test_debitar_baixa_as_duas_colunas_juntas():
    """🔴 A saída manual zerava `quantidade` e deixava `quantidade_disponivel`.

    As mesmas unidades saíam de novo.
    """
    from services.estoque_saldo import criar_lote, debitar

    with app.app_context():
        t = um_tenant('onda3_deb', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('100'), t.admin_id)
        db.session.flush()

        debitar(lote, Decimal('40'))
        assert lote.quantidade == Decimal('60')
        assert lote.quantidade_disponivel == Decimal('60'), (
            'quantidade_disponivel ficou para trás — a unidade sairia de novo')
        # `quantidade_inicial` é histórico: não se mexe
        assert lote.quantidade_inicial == Decimal('100')


def test_debitar_alem_do_saldo_levanta():
    from services.estoque_saldo import SaldoInsuficiente, criar_lote, debitar

    with app.app_context():
        t = um_tenant('onda3_ins', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('10'), t.admin_id)
        db.session.flush()
        with pytest.raises(SaldoInsuficiente):
            debitar(lote, Decimal('11'))


def test_creditar_sobe_as_duas():
    from services.estoque_saldo import creditar, criar_lote

    with app.app_context():
        t = um_tenant('onda3_cred', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('10'), t.admin_id)
        db.session.flush()
        creditar(lote, Decimal('5'))
        assert lote.quantidade == Decimal('15')
        assert lote.quantidade_disponivel == Decimal('15')


def test_entrada_manual_deixa_o_material_emitivel():
    """🔴 O defeito de ponta a ponta, pelo caminho real.

    `apply_movimento_manual` mantinha só `quantidade`. Uma ENTRADA de 100
    nascia com `quantidade_disponivel = NULL`, e a guarda de saída
    (`func.sum(quantidade_disponivel)`) via 0 — recusava material que existe.
    """
    from sqlalchemy import func

    from almoxarifado_utils import apply_movimento_manual
    from models import AlmoxarifadoEstoque, AlmoxarifadoMovimento

    with app.app_context():
        t = um_tenant('onda3_ent_e2e', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        db.session.flush()

        movimento = AlmoxarifadoMovimento(
            item_id=item.id, admin_id=t.admin_id, tipo_movimento='ENTRADA',
            quantidade=Decimal('100'), usuario_id=t.admin_id,
            data_movimento=_QUANDO)
        db.session.add(movimento)
        db.session.flush()

        resultado = apply_movimento_manual(movimento)
        assert resultado['sucesso'], resultado
        db.session.flush()

        disponivel = db.session.query(
            func.coalesce(func.sum(AlmoxarifadoEstoque.quantidade_disponivel), 0)
        ).filter(AlmoxarifadoEstoque.item_id == item.id).scalar()
        assert Decimal(str(disponivel)) == Decimal('100'), (
            f'entrou 100 e a guarda de saída enxerga {disponivel} — '
            'o material existe mas não pode ser emitido')


def _lote_bom(item_id, admin_id, quantidade):
    """Um lote com as três colunas coerentes, como o caminho de entrada por
    nota sempre fez (`views/almoxarifado/movimentos.py:400-406`).

    Serve para isolar o defeito da SAÍDA do defeito da ENTRADA: sem ele, a
    coluna nasce NULL e todo `coalesce(sum(...), 0)` devolve 0 — a asserção
    "ficou 0" passaria sem provar nada.
    """
    from models import AlmoxarifadoEstoque
    lote = AlmoxarifadoEstoque(
        item_id=item_id, admin_id=admin_id, status='DISPONIVEL',
        quantidade=quantidade, quantidade_inicial=quantidade,
        quantidade_disponivel=quantidade)
    db.session.add(lote)
    db.session.flush()
    return lote


def _disponivel_de(item_id):
    from sqlalchemy import func

    from models import AlmoxarifadoEstoque
    valor = db.session.query(
        func.coalesce(func.sum(AlmoxarifadoEstoque.quantidade_disponivel), 0)
    ).filter(AlmoxarifadoEstoque.item_id == item_id).scalar()
    return Decimal(str(valor))


def test_saida_manual_nao_deixa_a_unidade_sair_de_novo():
    """🔴 A saída baixava `quantidade` e deixava `quantidade_disponivel` cheia.

    A guarda da próxima saída soma `quantidade_disponivel` (`:597`): as MESMAS
    unidades saíam de novo. O lote parte COERENTE de propósito — é a única
    forma de a asserção falar da saída, e não do NULL da entrada.
    """
    from almoxarifado_utils import apply_movimento_manual
    from models import AlmoxarifadoMovimento

    with app.app_context():
        t = um_tenant('onda3_saida', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        _lote_bom(item.id, t.admin_id, Decimal('100'))
        assert _disponivel_de(item.id) == Decimal('100'), 'pré-condição'

        saida = AlmoxarifadoMovimento(
            item_id=item.id, admin_id=t.admin_id, tipo_movimento='SAIDA',
            quantidade=Decimal('40'), usuario_id=t.admin_id,
            data_movimento=_QUANDO)
        db.session.add(saida)
        db.session.flush()
        assert apply_movimento_manual(saida)['sucesso']
        db.session.flush()

        assert _disponivel_de(item.id) == Decimal('60'), (
            f'saíram 40 de 100 e o disponível é {_disponivel_de(item.id)} — '
            'as mesmas unidades sairiam de novo')


def test_rollback_da_entrada_devolve_as_duas_colunas():
    """A irmã da ida. Se o rollback desfizer só `quantidade`, a correção da
    ida cria o defeito na volta.
    """
    from almoxarifado_utils import (apply_movimento_manual,
                                    rollback_movimento_manual)
    from models import AlmoxarifadoMovimento

    with app.app_context():
        t = um_tenant('onda3_rb', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        _lote_bom(item.id, t.admin_id, Decimal('100'))

        entrada = AlmoxarifadoMovimento(
            item_id=item.id, admin_id=t.admin_id, tipo_movimento='ENTRADA',
            quantidade=Decimal('30'), usuario_id=t.admin_id,
            data_movimento=_QUANDO)
        db.session.add(entrada)
        db.session.flush()
        assert apply_movimento_manual(entrada)['sucesso']
        db.session.flush()
        assert _disponivel_de(item.id) == Decimal('130'), (
            f'entraram 30 sobre 100 e o disponível é {_disponivel_de(item.id)}')

        assert rollback_movimento_manual(entrada)['sucesso']
        db.session.flush()
        assert _disponivel_de(item.id) == Decimal('100'), (
            f'a entrada foi desfeita e o disponível é {_disponivel_de(item.id)}')


def test_almoxarifado_utils_nao_cria_lote_sem_quantidade_disponivel():
    """A guarda que impede o sexto caminho de nascer errado.

    É lint, não prova de comportamento: existe para que um construtor NOVO
    de `AlmoxarifadoEstoque` não repita a omissão. A Task 2 estende a mesma
    guarda a `views/almoxarifado/movimentos.py`.
    """
    import inspect

    import almoxarifado_utils

    fonte = inspect.getsource(almoxarifado_utils)
    for bloco in fonte.split('AlmoxarifadoEstoque(')[1:]:
        corpo = bloco.split(')')[0]
        if 'quantidade=' in corpo:
            assert 'quantidade_disponivel' in corpo, (
                'almoxarifado_utils: lote criado sem quantidade_disponivel'
                f' → {corpo[:200]}')


def test_lote_legado_com_disponivel_nulo_ainda_pode_sair():
    """A correção não pode RECUSAR material que existe.

    Produção tem lotes criados pelo caminho defeituoso: `quantidade = 100`,
    `quantidade_disponivel = NULL`. Se NULL fosse lido como zero, esta onda
    trocaria "a unidade sai duas vezes" por "a unidade não sai nenhuma".
    O lote se cura ao ser tocado.
    """
    from almoxarifado_utils import apply_movimento_manual
    from models import AlmoxarifadoEstoque, AlmoxarifadoMovimento

    with app.app_context():
        t = um_tenant('onda3_legado', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        legado = AlmoxarifadoEstoque(
            item_id=item.id, admin_id=t.admin_id, status='DISPONIVEL',
            quantidade=Decimal('100'), quantidade_disponivel=None)
        db.session.add(legado)
        db.session.flush()
        assert _disponivel_de(item.id) == Decimal('0'), (
            'pré-condição: o lote legado é invisível para a guarda')

        saida = AlmoxarifadoMovimento(
            item_id=item.id, admin_id=t.admin_id, tipo_movimento='SAIDA',
            quantidade=Decimal('40'), usuario_id=t.admin_id,
            data_movimento=_QUANDO)
        db.session.add(saida)
        db.session.flush()
        resultado = apply_movimento_manual(saida)
        assert resultado['sucesso'], (
            f'a saída recusou material que existe: {resultado}')
        db.session.flush()

        assert _disponivel_de(item.id) == Decimal('60'), (
            'o lote legado devia curar-se para 100 e baixar para 60, e ficou '
            f'{_disponivel_de(item.id)}')


# ---------------------------------------------------------------------------
# Task 2 — o material devolvido volta a existir
# ---------------------------------------------------------------------------

def test_devolucao_de_consumivel_volta_a_ser_emitivel():
    """🔴 `movimentos.py:1066` criava o lote de retorno só com `quantidade`.

    O devolvido ficava invisível para `sum(quantidade_disponivel)` — a guarda
    de saída (`:597`) via 0 e o material nunca mais podia ser emitido.
    """
    with app.app_context():
        t = um_tenant('onda3_dev', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        db.session.commit()
        item_id, admin_id, funcionario_id = item.id, t.admin_id, t.funcionario_id

    resposta = cliente_de(admin_id).post('/almoxarifado/processar-devolucao', data={
        'funcionario_id': str(funcionario_id),
        'tipo_controle': 'CONSUMIVEL',
        'item_id': str(item_id),
        'quantidade': '7',
        'condicao_devolucao': 'BOM',
    }, follow_redirects=True)
    assert resposta.status_code == 200

    with app.app_context():
        assert _disponivel_de(item_id) == Decimal('7'), (
            f'devolveu 7 e o disponível ficou {_disponivel_de(item_id)} — '
            'material devolvido some da guarda de saída')


def test_devolucao_multipla_de_consumivel_volta_a_ser_emitivel():
    """🔴 `movimentos.py:1330` tem a omissão idêntica."""
    import json

    with app.app_context():
        t = um_tenant('onda3_dev_mult', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        db.session.commit()
        item_id, admin_id, funcionario_id = item.id, t.admin_id, t.funcionario_id

    resposta = cliente_de(admin_id).post(
        '/almoxarifado/processar-devolucao-multipla',
        data=json.dumps({
            # ⚠️ `funcionario_id` e `condicao_item` vão DENTRO de cada item
            # (`movimentos.py:1202`), não na raiz do payload.
            'itens': [{'item_id': item_id, 'quantidade': 5,
                       'tipo_controle': 'CONSUMIVEL',
                       'funcionario_id': funcionario_id,
                       'condicao_item': 'Bom'}],
        }),
        content_type='application/json')
    assert resposta.status_code in (200, 302), resposta.data[:300]

    with app.app_context():
        assert _disponivel_de(item_id) == Decimal('5'), (
            f'devolveu 5 e o disponível ficou {_disponivel_de(item_id)}')


def test_movimentos_nao_cria_lote_sem_quantidade_disponivel():
    """A guarda da Task 1, estendida ao segundo módulo que cria lote."""
    import inspect

    import views.almoxarifado.movimentos as mov

    fonte = inspect.getsource(mov)
    for bloco in fonte.split('AlmoxarifadoEstoque(')[1:]:
        corpo = bloco.split(')')[0]
        if 'quantidade=' in corpo:
            assert 'quantidade_disponivel' in corpo, (
                'movimentos: lote criado sem quantidade_disponivel'
                f' → {corpo[:200]}')


# ---------------------------------------------------------------------------
# Task 3 — a obra 1 e a atomicidade
# ---------------------------------------------------------------------------

def _item_serializado(admin_id):
    from models import AlmoxarifadoCategoria, AlmoxarifadoItem
    suf = uuid.uuid4().hex[:8]
    categoria = AlmoxarifadoCategoria(
        admin_id=admin_id, nome=f'Ferramentas {suf}',
        tipo_controle_padrao='SERIALIZADO')
    db.session.add(categoria)
    db.session.flush()
    item = AlmoxarifadoItem(
        admin_id=admin_id, nome=f'Furadeira {suf}', codigo=f'FUR{suf}',
        categoria_id=categoria.id, tipo_controle='SERIALIZADO',
        unidade='un', permite_devolucao=True)
    db.session.add(item)
    db.session.flush()
    return item


def test_devolucao_serializada_preserva_a_obra_real():
    """🔴 `movimentos.py:1046` — `estoque.obra_id or 1`, com `obra_id` posto a
    None três linhas antes (`:1031`). A expressão era SEMPRE 1: toda devolução
    serializada era carimbada com a obra de id 1, arbitrária e possivelmente
    de outro tenant. `relatorios.py:214` (consumo por obra) lê essa coluna.
    """
    from models import AlmoxarifadoEstoque, AlmoxarifadoMovimento

    with app.app_context():
        t = um_tenant('onda3_obra1', com_fatos=False)
        item = _item_serializado(t.admin_id)
        lote = AlmoxarifadoEstoque(
            item_id=item.id, admin_id=t.admin_id, status='EM_USO',
            numero_serie=f'SN{uuid.uuid4().hex[:8]}',
            quantidade=Decimal('1'), quantidade_inicial=Decimal('1'),
            quantidade_disponivel=Decimal('0'),
            funcionario_atual_id=t.funcionario_id, obra_id=t.obra_id)
        db.session.add(lote)
        db.session.commit()
        admin_id, func_id = t.admin_id, t.funcionario_id
        obra_real, estoque_id = t.obra_id, lote.id

    resposta = cliente_de(admin_id).post(
        '/almoxarifado/processar-devolucao', data={
            'funcionario_id': str(func_id),
            'tipo_controle': 'SERIALIZADO',
            'estoque_ids[]': str(estoque_id),
            'condicao_devolucao': 'Bom',
        }, follow_redirects=True)
    assert resposta.status_code == 200

    with app.app_context():
        movimento = AlmoxarifadoMovimento.query.filter_by(
            estoque_id=estoque_id, tipo_movimento='DEVOLUCAO').first()
        assert movimento is not None, 'a devolução não gerou movimento'
        assert movimento.obra_id == obra_real, (
            f'a devolução foi carimbada com a obra {movimento.obra_id} em vez '
            f'da obra real {obra_real} — o consumo por obra se perde')


def test_entrada_em_lote_emite_depois_do_commit():
    """🔴 O emit dentro do laço tornava o rollback um no-op.

    O handler `criar_conta_pagar_entrada_material` commita
    (`event_manager.py:216`): emitido dentro do laço, o item 1 já estava
    commitado quando o item 3 falhava, e o `rollback()` do erro não desfazia
    nada — meia carga ficava no estoque com o chamador informado de que a
    operação falhou. A rota de item único (`:185`, `:236`) sempre emitiu
    depois do commit; esta divergiu, e o docstring dela promete
    'TRANSAÇÃO ATÔMICA'.
    """
    import inspect

    import views.almoxarifado.movimentos as mov

    fonte = inspect.getsource(mov.processar_entrada_multipla)
    pos_emit = fonte.find("EventManager.emit('material_entrada'")
    pos_commit = fonte.find('db.session.commit()')
    assert pos_emit > pos_commit > 0, (
        'o emit de material_entrada ainda acontece antes do commit da rota')


def test_saida_multipla_falha_quando_o_lote_sumiu():
    """O lote que não existe é recusado, e o estoque fica intacto.

    ⚠️ Este teste NÃO alcança o `continue` silencioso de `:872`: a rota valida
    os lotes adiantado (`:783-791`) e devolve 400 nomeando o lote. O `continue`
    só dispara na janela entre validação e aplicação, que exige outra conexão
    commitando no meio — não é montável daqui. O que este teste garante é que
    a recusa não mexe no estoque.
    """
    import json

    from models import AlmoxarifadoMovimento

    with app.app_context():
        t = um_tenant('onda3_saida_mult', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = _lote_bom(item.id, t.admin_id, Decimal('50'))
        db.session.commit()
        admin_id, func_id, obra_id = t.admin_id, t.funcionario_id, t.obra_id
        item_id, lote_id = item.id, lote.id
        # O lote some entre a montagem do carrinho e o POST.
        inexistente = lote_id + 10_000_000

    resposta = cliente_de(admin_id).post(
        '/almoxarifado/processar-saida-multipla',
        data=json.dumps({
            'itens': [{'item_id': item_id, 'quantidade': 10,
                       'funcionario_id': func_id, 'obra_id': obra_id,
                       'tipo_controle': 'CONSUMIVEL',
                       'lote_allocations': [
                           {'estoque_id': inexistente, 'quantidade': 10}]}],
        }),
        content_type='application/json')

    corpo = json.loads(resposta.data)
    assert corpo.get('success') is False, (
        f'o lote pedido não existe e a rota respondeu {corpo} — '
        'o usuário é informado de sucesso tendo saído zero')

    with app.app_context():
        movimentos = AlmoxarifadoMovimento.query.filter_by(
            item_id=item_id, tipo_movimento='SAIDA').count()
        assert movimentos == 0, 'não devia sobrar movimento de uma saída falha'
        assert _disponivel_de(item_id) == Decimal('50'), (
            'o estoque foi mexido numa saída que falhou')


def test_saida_multipla_baixa_as_duas_colunas():
    """A saída em lote passa pelo ponto único: `quantidade` e
    `quantidade_disponivel` andam juntas.

    Escrevia nas duas à mão, com `quantidade = quantidade_disponivel` — o que
    apaga a divergência em vez de subtrair.
    """
    import json

    from models import AlmoxarifadoEstoque

    with app.app_context():
        t = um_tenant('onda3_saida_ok', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = _lote_bom(item.id, t.admin_id, Decimal('50'))
        db.session.commit()
        admin_id, func_id, obra_id = t.admin_id, t.funcionario_id, t.obra_id
        item_id, lote_id = item.id, lote.id

    resposta = cliente_de(admin_id).post(
        '/almoxarifado/processar-saida-multipla',
        data=json.dumps({
            'itens': [{'item_id': item_id, 'quantidade': 20,
                       'funcionario_id': func_id, 'obra_id': obra_id,
                       'tipo_controle': 'CONSUMIVEL',
                       'lote_allocations': [
                           {'estoque_id': lote_id, 'quantidade': 20}]}],
        }),
        content_type='application/json')
    corpo = json.loads(resposta.data)
    assert corpo.get('success') is True, corpo

    with app.app_context():
        lote = db.session.get(AlmoxarifadoEstoque, lote_id)
        assert Decimal(str(lote.quantidade)) == Decimal('30')
        assert Decimal(str(lote.quantidade_disponivel)) == Decimal('30'), (
            'as duas colunas têm de andar juntas')
