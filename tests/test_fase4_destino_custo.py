"""Fase 4 — derivação do destino do custo.

O ESTADO-ATUAL.md dizia que `gestao_custo_pai` tinha "1.118 linhas 100%
órfãs". Conferido no banco em 2026-07-21: são 1.246 linhas, e 1.169 delas
(93,8%) têm a obra recuperável por UNANIMIDADE dos filhos. "100%
estruturalmente órfãs" (DOSSIE-REPO.md:512) queria dizer "a coluna não
existe", não "a informação se perdeu".

Estes testes travam a cascata R1→R5 e o comportamento dry-run do backfill.
"""
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import (Cliente, GestaoCustoFilho, GestaoCustoPai, Obra,
                    TipoUsuario, Usuario)

pytestmark = pytest.mark.integration

_CK_DESTINO = 'ck_gestao_custo_filho_destino'


@contextmanager
def _sem_check_destino():
    """Permite semear o mundo pré-Fase-4 — filho órfão, sem obra e sem centro —
    mesmo com o CHECK `ck_gestao_custo_filho_destino` já ativo no banco.

    Espelha o arco real da fase: migration 253 cria o CHECK em `NOT VALID`
    (trava a escrita nova), o backfill limpa o histórico, migration 254 valida.
    Aqui o CHECK é dropado na entrada e re-adicionado JÁ VALIDADO na saída — o
    que exige que o corpo do `with` tenha deixado a tabela SEM nenhum órfão (o
    `aplicar_filhos` resolve, ou o teste apaga o que semeou). Se um órfão
    sobrar, o re-ADD falha de propósito: é a mesma invariante da migration 254.

    Seguro porque a suíte roda serialmente (sem pytest-xdist): dropar a
    constraint global no escopo de um teste não colide com teste concorrente.
    """
    db.session.rollback()
    db.session.execute(text(
        f'ALTER TABLE gestao_custo_filho DROP CONSTRAINT IF EXISTS {_CK_DESTINO}'))
    db.session.commit()
    try:
        yield
    finally:
        db.session.rollback()
        db.session.execute(text(
            f'ALTER TABLE gestao_custo_filho ADD CONSTRAINT {_CK_DESTINO} '
            'CHECK (obra_id IS NOT NULL OR centro_custo_id IS NOT NULL)'))
        db.session.commit()


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase4-destino'
    yield


def _limpar_tenant(admin_id):
    """Apaga custos de um tenant para que o CHECK possa ser revalidado na saída
    de `_sem_check_destino` — usado pelos testes que semeiam um órfão e não o
    corrigem (diagnóstico e conformidade são read-only por contrato)."""
    GestaoCustoFilho.query.filter_by(admin_id=admin_id).delete()
    GestaoCustoPai.query.filter_by(admin_id=admin_id).delete()
    db.session.commit()


def _admin():
    suf = uuid.uuid4().hex[:10]
    u = Usuario(
        username=f'f4d_{suf}', email=f'f4d_{suf}@test.local',
        nome=f'Empresa {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cli = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra {suf}', codigo=f'F4D{suf[:6].upper()}',
             cliente_id=cli.id, admin_id=admin_id,
             data_inicio=date(2026, 1, 1), ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _pai_com_filhos(admin_id, obras_dos_filhos, origem='manual'):
    """Cria um pai e um filho por elemento de `obras_dos_filhos` (None = sem obra)."""
    pai = GestaoCustoPai(
        admin_id=admin_id, tipo_categoria='MATERIAL', entidade_nome='Forn',
        valor_total=0, status='PENDENTE')
    db.session.add(pai)
    db.session.flush()
    for i, oid in enumerate(obras_dos_filhos):
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=admin_id, data_referencia=date(2026, 6, 1),
            descricao=f'Linha {i}', valor=10, obra_id=oid,
            origem_tabela=origem))
    db.session.commit()
    return pai


# --- regras puras ----------------------------------------------------------

def test_obra_unanime_devolve_a_obra_quando_todas_iguais():
    from services.destino_custo import obra_unanime

    assert obra_unanime([7, 7, 7]) == 7
    assert obra_unanime([7, None, 7]) == 7
    assert obra_unanime([7]) == 7


def test_obra_unanime_devolve_none_quando_diverge_ou_vazio():
    from services.destino_custo import obra_unanime

    assert obra_unanime([7, 8]) is None
    assert obra_unanime([None, None]) is None
    assert obra_unanime([]) is None


def test_classificar_pai_nomeia_os_tres_casos():
    from services.destino_custo import classificar_pai

    assert classificar_pai([5, 5]) == ('unanime', 5)
    assert classificar_pai([5, 6]) == ('multiobra', None)
    assert classificar_pai([None]) == ('sem_obra', None)
    assert classificar_pai([]) == ('sem_filho', None)


def test_origem_administrativa_reconhece_folha_e_almoxarifado():
    from services.destino_custo import (ORIGENS_ADMINISTRATIVAS,
                                        ORIGENS_COM_OBRA)

    assert 'folha_pagamento' in ORIGENS_ADMINISTRATIVAS
    assert 'almoxarifado_movimento' in ORIGENS_ADMINISTRATIVAS
    assert 'pedido_compra' in ORIGENS_COM_OBRA
    assert 'reembolso_funcionario' in ORIGENS_COM_OBRA
    assert 'folha_pagamento' not in ORIGENS_COM_OBRA


# --- relatório dry-run -----------------------------------------------------

def test_diagnosticar_conta_unanimes_multiobra_e_orfaos():
    from scripts.backfill_destino_custo import diagnosticar

    with app.app_context(), _sem_check_destino():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        _pai_com_filhos(a.id, [o1.id, o1.id])   # unânime
        _pai_com_filhos(a.id, [o1.id, o2.id])   # multi-obra
        _pai_com_filhos(a.id, [None])           # sem obra
        pai_vazio = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='X',
            valor_total=0, status='PENDENTE')
        db.session.add(pai_vazio)
        db.session.commit()

        rel = diagnosticar(admin_id=a.id)

        assert rel['pai']['total'] == 4
        assert rel['pai']['unanime'] == 1
        assert rel['pai']['multiobra'] == 1
        assert rel['pai']['sem_obra'] == 1
        assert rel['pai']['sem_filho'] == 1
        assert rel['filho']['sem_destino'] == 1
        _limpar_tenant(a.id)  # diagnosticar é dry-run: o órfão semeado fica


def test_diagnosticar_nao_grava_nada():
    from scripts.backfill_destino_custo import diagnosticar

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id, o.id])
        pid = pai.id

        diagnosticar(admin_id=a.id)
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pid).obra_id is None, (
            'diagnosticar() gravou — o dry-run tem de ser read-only')


# ---------------------------------------------------------------------------
# R1 — pai.obra_id por unanimidade dos filhos
# ---------------------------------------------------------------------------

def test_aplicar_pais_preenche_unanime_e_deixa_multiobra_null():
    from scripts.backfill_destino_custo import aplicar_pais

    with app.app_context(), _sem_check_destino():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        pai_u = _pai_com_filhos(a.id, [o1.id, o1.id])
        pai_m = _pai_com_filhos(a.id, [o1.id, o2.id])
        pai_s = _pai_com_filhos(a.id, [None])
        ids = (pai_u.id, pai_m.id, pai_s.id)

        resultado = aplicar_pais(admin_id=a.id)
        db.session.commit()

        assert resultado['atualizados'] == 1
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, ids[0]).obra_id == o1.id
        assert db.session.get(GestaoCustoPai, ids[1]).obra_id is None
        assert db.session.get(GestaoCustoPai, ids[2]).obra_id is None
        _limpar_tenant(a.id)  # aplicar_pais não toca no filho: pai_s fica órfão


def test_aplicar_pais_e_idempotente():
    from scripts.backfill_destino_custo import aplicar_pais

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id, o.id])
        pid = pai.id

        primeira = aplicar_pais(admin_id=a.id)
        db.session.commit()
        segunda = aplicar_pais(admin_id=a.id)
        db.session.commit()

        assert primeira['atualizados'] == 1
        assert segunda['atualizados'] == 0
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pid).obra_id == o.id


def test_aplicar_pais_corrige_obra_errada_gravada_antes():
    """Se um filho mudou de obra, o pai acompanha — a coluna é derivada."""
    from scripts.backfill_destino_custo import aplicar_pais

    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        pai = _pai_com_filhos(a.id, [o1.id])
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        filho.obra_id = o2.id
        db.session.commit()

        aplicar_pais(admin_id=a.id)
        db.session.commit()
        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pai.id).obra_id == o2.id


# ---------------------------------------------------------------------------
# R2-R5 — destino dos filhos órfãos
# ---------------------------------------------------------------------------

def test_r2_filho_orfao_herda_obra_do_irmao_unanime():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais

    with app.app_context(), _sem_check_destino():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id, None])
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R2_irmao_unanime') == 1
        orfaos = GestaoCustoFilho.query.filter_by(
            pai_id=pai.id, obra_id=None).count()
        assert orfaos == 0


def test_r3_filho_orfao_herda_obra_da_origem():
    from models import Fornecedor, PedidoCompra
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais

    with app.app_context(), _sem_check_destino():
        a = _admin()
        o = _obra(a.id)
        forn = Fornecedor(admin_id=a.id, nome='Forn PC',
                          cnpj=f'{uuid.uuid4().int % 10**14:014d}', ativo=True)
        db.session.add(forn)
        db.session.flush()
        pedido = PedidoCompra(
            admin_id=a.id, obra_id=o.id, fornecedor_id=forn.id,
            numero=f'PC{uuid.uuid4().hex[:6]}',
            data_compra=date(2026, 6, 1), valor_total=100)
        db.session.add(pedido)
        db.session.flush()

        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn',
            valor_total=100, status='PENDENTE')
        db.session.add(pai)
        db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
            descricao='Compra', valor=100, obra_id=None,
            origem_tabela='pedido_compra', origem_id=pedido.id))
        db.session.commit()

        aplicar_pais(admin_id=a.id)
        db.session.commit()
        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R3_origem') == 1
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        assert filho.obra_id == o.id


def test_r4_folha_e_almoxarifado_vao_para_o_centro_administrativo():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context(), _sem_check_destino():
        a = _admin()
        pai = _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R4_natureza_origem') == 1
        adm = centro_custo_administrativo(a.id, criar=False)
        assert adm is not None
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        assert filho.obra_id is None
        assert filho.centro_custo_id == adm.id


def test_r5_resto_vai_para_administrativo_e_fica_carimbado():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais
    from services.destino_custo import MARCA_FALLBACK
    from utils.centro_custo import centro_custo_administrativo

    with app.app_context(), _sem_check_destino():
        a = _admin()
        pai = _pai_com_filhos(a.id, [None], origem='lancamento_periodo_manual')
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        r = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert r['por_regra'].get('R5_fallback') == 1
        adm = centro_custo_administrativo(a.id, criar=False)
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        assert filho.centro_custo_id == adm.id
        db.session.expire_all()
        assert MARCA_FALLBACK in (db.session.get(GestaoCustoPai, pai.id).observacoes or '')


def test_aplicar_filhos_e_idempotente():
    from scripts.backfill_destino_custo import aplicar_filhos, aplicar_pais

    with app.app_context(), _sem_check_destino():
        a = _admin()
        _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        aplicar_pais(admin_id=a.id)
        db.session.commit()

        primeira = aplicar_filhos(admin_id=a.id)
        db.session.commit()
        segunda = aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert primeira['atualizados'] == 1
        assert segunda['atualizados'] == 0


def test_apos_backfill_nao_sobra_filho_sem_destino():
    from scripts.backfill_destino_custo import (aplicar_filhos, aplicar_pais,
                                                diagnosticar)

    with app.app_context(), _sem_check_destino():
        a = _admin()
        o = _obra(a.id)
        _pai_com_filhos(a.id, [o.id, None])
        _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        _pai_com_filhos(a.id, [None], origem='lancamento_periodo_manual')

        aplicar_pais(admin_id=a.id)
        db.session.commit()
        aplicar_filhos(admin_id=a.id)
        db.session.commit()

        assert diagnosticar(admin_id=a.id)['filho']['sem_destino'] == 0


# ---------------------------------------------------------------------------
# Porta de escrita: registrar_custo_automatico
# ---------------------------------------------------------------------------

def test_registrar_custo_sem_obra_cai_no_centro_administrativo():
    from utils.centro_custo import centro_custo_administrativo
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        filho = registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='OUTROS',
            entidade_nome='Papelaria', entidade_id=None,
            data=date(2026, 6, 1), descricao='Resma de papel', valor=50,
            obra_id=None, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()

        assert filho is not None
        adm = centro_custo_administrativo(a.id, criar=False)
        assert adm is not None
        assert filho.obra_id is None
        assert filho.centro_custo_id == adm.id


def test_registrar_custo_com_obra_nao_toca_no_centro():
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        filho = registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='MATERIAL',
            entidade_nome='Forn', entidade_id=None,
            data=date(2026, 6, 1), descricao='Perfil', valor=100,
            obra_id=o.id, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()

        assert filho.obra_id == o.id
        assert filho.centro_custo_id is None


def test_registrar_custo_faturamento_direto_sem_obra_e_recusado():
    from services.destino_custo import DestinoIndefinido
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        with pytest.raises(DestinoIndefinido):
            registrar_custo_automatico(
                admin_id=a.id, tipo_categoria='FATURAMENTO_DIRETO',
                entidade_nome='Cliente', entidade_id=None,
                data=date(2026, 6, 1), descricao='Material do cliente',
                valor=100, obra_id=None, origem_tabela='teste_fase4',
                force_v2=True)
        db.session.rollback()


def test_registrar_custo_mantem_pai_obra_id_em_dia():
    from utils.financeiro_integration import registrar_custo_automatico

    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        f1 = registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn X',
            entidade_id=None, data=date(2026, 6, 1), descricao='L1', valor=10,
            obra_id=o1.id, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()
        pai_id = f1.pai_id
        assert db.session.get(GestaoCustoPai, pai_id).obra_id == o1.id

        registrar_custo_automatico(
            admin_id=a.id, tipo_categoria='MATERIAL', entidade_nome='Forn X',
            entidade_id=None, data=date(2026, 6, 2), descricao='L2', valor=10,
            obra_id=o2.id, origem_tabela='teste_fase4', force_v2=True)
        db.session.commit()

        db.session.expire_all()
        assert db.session.get(GestaoCustoPai, pai_id).obra_id is None, (
            'pai virou multi-obra e obra_id tem de voltar para NULL')


# ---------------------------------------------------------------------------
# Telas de gestão de custos
# ---------------------------------------------------------------------------

def _cliente_logado(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_lancamento_manual_sem_obra_grava_no_centro_administrativo():
    with app.app_context():
        a = _admin()
        aid = a.id

    cli = _cliente_logado(aid)
    resp = cli.post('/gestao-custos/novo', data={
        'tipo_categoria': 'OUTROS',
        'entidade_nome': 'Papelaria Central',
        'descricao': 'Resma A4',
        'valor': '75,50',
        'data_referencia': '2026-06-01',
        'obra_id': '',
    }, follow_redirects=False)
    assert resp.status_code in (302, 200)

    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo
        filho = (GestaoCustoFilho.query
                 .filter_by(admin_id=aid, descricao='Resma A4').one())
        adm = centro_custo_administrativo(aid, criar=False)
        assert adm is not None
        assert filho.obra_id is None
        assert filho.centro_custo_id == adm.id


def test_editar_filho_nao_pode_mais_deixar_a_linha_sem_destino():
    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [o.id])
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        aid, fid = a.id, filho.id

    cli = _cliente_logado(aid)
    resp = cli.post(f'/gestao-custos/filho/{fid}/editar', data={'obra_id': ''})
    assert resp.status_code == 200

    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo
        db.session.expire_all()
        recarregado = db.session.get(GestaoCustoFilho, fid)
        adm = centro_custo_administrativo(aid, criar=False)
        assert recarregado.obra_id is None
        assert recarregado.centro_custo_id == adm.id, (
            'esvaziar a obra deixou a linha sem destino — '
            'gestao_custos_views.py:467-470 continua aberto')


def test_editar_filho_trocando_obra_limpa_o_centro_administrativo():
    with app.app_context(), _sem_check_destino():
        a = _admin()
        o = _obra(a.id)
        pai = _pai_com_filhos(a.id, [None], origem='folha_pagamento')
        filho = GestaoCustoFilho.query.filter_by(pai_id=pai.id).one()
        from utils.centro_custo import centro_custo_administrativo
        filho.centro_custo_id = centro_custo_administrativo(a.id).id
        db.session.commit()
        aid, fid, oid = a.id, filho.id, o.id

    cli = _cliente_logado(aid)
    resp = cli.post(f'/gestao-custos/filho/{fid}/editar',
                    data={'obra_id': str(oid)})
    assert resp.status_code == 200

    with app.app_context():
        db.session.expire_all()
        recarregado = db.session.get(GestaoCustoFilho, fid)
        assert recarregado.obra_id == oid
        assert recarregado.centro_custo_id is None


def test_pagar_leva_obra_e_centro_para_o_fluxo_caixa():
    from models import BancoEmpresa, FluxoCaixa

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        banco = BancoEmpresa(admin_id=a.id, nome_banco='Banco F4',
                             agencia='0001', conta='12345-6', ativo=True)
        db.session.add(banco)
        pai = _pai_com_filhos(a.id, [o.id])
        pai.valor_total = 10
        pai.saldo = 10
        pai.status = 'AUTORIZADO'
        pai.obra_id = o.id
        db.session.commit()
        aid, pid, bid, oid = a.id, pai.id, banco.id, o.id

    cli = _cliente_logado(aid)
    resp = cli.post(f'/gestao-custos/{pid}/pagar', data={
        'valor_pago': '10',
        'data_pagamento': '2026-06-10',
        'banco_id': str(bid),
    })
    assert resp.status_code in (302, 200)

    with app.app_context():
        fc = (FluxoCaixa.query
              .filter_by(admin_id=aid, referencia_tabela='gestao_custo_pai',
                         referencia_id=pid).one())
        assert fc.obra_id == oid
        assert fc.centro_custo_id is None


# ---------------------------------------------------------------------------
# Produtores estruturais de órfão
# ---------------------------------------------------------------------------

def test_nenhum_criador_de_filho_grava_sem_destino():
    """Varredura estática: todo `GestaoCustoFilho(` de produção passa
    `obra_id` OU `centro_custo_id` no mesmo bloco de argumentos."""
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    alvos = [
        'gestao_custos_views.py', 'compras_views.py',
        'folha_pagamento_views.py', 'event_manager.py',
        'services/importacao_excel.py', 'utils/financeiro_integration.py',
    ]
    faltando = []
    for rel in alvos:
        texto = (raiz / rel).read_text(encoding='utf-8')
        for m in re.finditer(r'GestaoCustoFilho\((.*?)\)\s*\n', texto,
                             re.DOTALL):
            bloco = m.group(1)
            if 'obra_id' not in bloco and 'centro_custo_id' not in bloco:
                linha = texto[:m.start()].count('\n') + 1
                faltando.append(f'{rel}:{linha}')
    assert not faltando, (
        'GestaoCustoFilho criado sem destino em: ' + ', '.join(faltando))


def test_entrada_de_almoxarifado_vai_para_o_centro_administrativo():
    from models import (AlmoxarifadoCategoria, AlmoxarifadoItem,
                        AlmoxarifadoMovimento, Fornecedor)

    with app.app_context():
        a = _admin()
        forn = Fornecedor(admin_id=a.id, nome='Forn Almox',
                          cnpj=f'{uuid.uuid4().int % 10**14:014d}', ativo=True)
        cat = AlmoxarifadoCategoria(admin_id=a.id, nome='Perfis',
                                    tipo_controle_padrao='CONSUMIVEL')
        db.session.add_all([forn, cat])
        db.session.flush()
        item = AlmoxarifadoItem(
            admin_id=a.id, codigo=f'IT{uuid.uuid4().hex[:6].upper()}',
            nome='Perfil U', categoria_id=cat.id,
            tipo_controle='CONSUMIVEL', unidade='un')
        db.session.add(item)
        db.session.flush()
        mov = AlmoxarifadoMovimento(
            admin_id=a.id, usuario_id=a.id, item_id=item.id,
            tipo_movimento='ENTRADA', quantidade=10, valor_unitario=5,
            fornecedor_id=forn.id, data_movimento=date(2026, 6, 1))
        db.session.add(mov)
        db.session.commit()
        aid, mid, fid = a.id, mov.id, forn.id

    with app.app_context():
        from event_manager import criar_conta_pagar_entrada_material
        criar_conta_pagar_entrada_material(
            {'movimento_id': mid, 'fornecedor_id': fid}, aid)

    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo
        adm = centro_custo_administrativo(aid, criar=False)
        filhos = GestaoCustoFilho.query.filter_by(
            admin_id=aid, origem_tabela='almoxarifado_movimento',
            origem_id=mid).all()
        assert filhos, 'nenhum GestaoCustoFilho criado para a entrada'
        for f in filhos:
            assert f.obra_id is None
            assert f.centro_custo_id == adm.id


# ---------------------------------------------------------------------------
# Listagem: filtro por obra e escopo da Fase 1
# ---------------------------------------------------------------------------

def test_filtro_por_obra_acha_pai_unanime_e_multiobra():
    with app.app_context():
        a = _admin()
        o1, o2 = _obra(a.id), _obra(a.id)
        pai_u = _pai_com_filhos(a.id, [o1.id])
        pai_m = _pai_com_filhos(a.id, [o1.id, o2.id])
        pai_outro = _pai_com_filhos(a.id, [o2.id])
        from scripts.backfill_destino_custo import aplicar_pais
        aplicar_pais(admin_id=a.id)
        db.session.commit()
        aid, oid = a.id, o1.id
        ids = (pai_u.id, pai_m.id, pai_outro.id)

    cli = _cliente_logado(aid)
    resp = cli.get(f'/gestao-custos/?obra_id={oid}')
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert f'/gestao-custos/{ids[0]}/' in corpo or str(ids[0]) in corpo
    assert str(ids[1]) in corpo, 'pai multi-obra sumiu do filtro por obra'


def test_dropdown_de_obras_respeita_o_escopo_da_fase_1():
    """A lista de obras da tela de custos sai de `obras_visiveis()`."""
    import inspect

    import gestao_custos_views

    fonte = inspect.getsource(gestao_custos_views)
    assert 'obras_visiveis' in fonte, (
        'gestao_custos_views ainda monta o dropdown com '
        'Obra.query.filter_by(admin_id=...) — ignora o escopo por obra da '
        'Fase 1')


# ---------------------------------------------------------------------------
# Relatório de conformidade
# ---------------------------------------------------------------------------

def test_conformidade_reporta_zero_quando_tudo_tem_destino():
    from scripts.relatorio_destino_custo import conformidade

    with app.app_context():
        a = _admin()
        o = _obra(a.id)
        _pai_com_filhos(a.id, [o.id, o.id])

        rel = conformidade(admin_id=a.id)
        assert rel['sem_destino'] == 0
        assert rel['pronto_para_constraint'] is True


def test_conformidade_lista_os_pendentes_com_valor():
    from scripts.relatorio_destino_custo import conformidade

    with app.app_context(), _sem_check_destino():
        a = _admin()
        _pai_com_filhos(a.id, [None])

        rel = conformidade(admin_id=a.id)
        assert rel['sem_destino'] == 1
        assert rel['pronto_para_constraint'] is False
        assert float(rel['valor_sem_destino']) == 10.0
        assert len(rel['amostra']) == 1
        assert rel['amostra'][0]['pai_id'] is not None
        _limpar_tenant(a.id)  # conformidade é read-only: o órfão semeado fica


# ---------------------------------------------------------------------------
# Constraint: todo lançamento novo tem destino
# ---------------------------------------------------------------------------

def test_banco_recusa_filho_novo_sem_destino():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        a = _admin()
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='X',
            valor_total=0, status='PENDENTE')
        db.session.add(pai)
        db.session.flush()
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
            descricao='Sem destino', valor=1,
            obra_id=None, centro_custo_id=None))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_banco_aceita_filho_com_obra_e_com_centro():
    with app.app_context():
        from utils.centro_custo import centro_custo_administrativo

        a = _admin()
        o = _obra(a.id)
        adm = centro_custo_administrativo(a.id)
        pai = GestaoCustoPai(
            admin_id=a.id, tipo_categoria='OUTROS', entidade_nome='X',
            valor_total=0, status='PENDENTE')
        db.session.add(pai)
        db.session.flush()
        db.session.add_all([
            GestaoCustoFilho(
                pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
                descricao='Com obra', valor=1, obra_id=o.id),
            GestaoCustoFilho(
                pai_id=pai.id, admin_id=a.id, data_referencia=date(2026, 6, 1),
                descricao='Com centro', valor=1, centro_custo_id=adm.id),
        ])
        db.session.commit()
        assert GestaoCustoFilho.query.filter_by(pai_id=pai.id).count() == 2


def test_constraint_existe_no_banco():
    from sqlalchemy import text

    with app.app_context():
        achado = db.session.execute(text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'gestao_custo_filho'::regclass
              AND conname = 'ck_gestao_custo_filho_destino'
        """)).fetchone()
        assert achado is not None, (
            'ck_gestao_custo_filho_destino não existe — a migration 253 não '
            'rodou')


def test_constraint_de_destino_esta_validada():
    from sqlalchemy import text

    with app.app_context():
        convalidated = db.session.execute(text("""
            SELECT convalidated FROM pg_constraint
            WHERE conrelid = 'gestao_custo_filho'::regclass
              AND conname = 'ck_gestao_custo_filho_destino'
        """)).scalar()
        assert convalidated is True, (
            'a constraint existe mas está NOT VALID — o histórico não foi '
            'validado (migration 254)')


def test_nao_sobrou_lancamento_sem_destino_no_banco():
    from scripts.relatorio_destino_custo import conformidade

    with app.app_context():
        rel = conformidade()
        assert rel['sem_destino'] == 0, (
            f"{rel['sem_destino']} lançamento(s) ainda sem destino: "
            f"{rel['por_origem']}")
        # NÃO se exige `tenants_sem_centro_administrativo == 0`. O invariante
        # da fase é POR FILHO (obra OU centro), travado pelo CHECK e provado
        # pela linha acima. Um tenant cujos custos apontam todos para obra
        # legitimamente nunca precisa de um centro administrativo — o centro é
        # criado sob demanda (`centro_custo_administrativo(criar=True)`) no
        # primeiro custo administrativo. Exigir um centro por tenant seria um
        # invariante mais forte que o schema, e falso num banco com tenants
        # só-de-obra (medido em 23/07: 30 tenants com custo só-de-obra e sem
        # centro administrativo, todos em conformidade).
