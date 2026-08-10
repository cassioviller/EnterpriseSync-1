"""Exportação de RDOs (services/exportacao_rdos.py + rota do zip).

O que estes testes travam:

  • round-trip: o rdos.json exportado, aplicado por `atualizar_rdos` numa
    obra clone, reproduz clima/comentário/pct — o export emite EXATAMENTE
    o payload que o updater consome;
  • obra sem `mpp_uid` exporta chave NEGATIVA (-id) + mapa_nomes que o
    fallback por nome resolve — id positivo colidiria com uid real;
  • RDO imutável sai com `_estado` e o reimport o PULA (não derruba);
  • duas linhas na mesma data → exporta a mais recente COM aviso;
  • a rota é do tenant: obra alheia é 404, e o zip traz os três JSONs.
"""
import io
import json
import os
import sys
import uuid
import zipfile

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from datetime import date, datetime                      # noqa: E402

import pytest                                            # noqa: E402
from werkzeug.security import generate_password_hash     # noqa: E402

import main  # noqa: F401,E402 — registra os blueprints
from app import app, db                                  # noqa: E402


# ── ambiente: mesmo desenho de test_atualizacao_rdos ──────────────────
def _ambiente(com_mpp_uid=True):
    from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario

    tag = uuid.uuid4().hex[:10]
    admin = Usuario(username=f'ex_{tag}', email=f'ex_{tag}@test.local',
                    nome=f'Admin EX {tag}',
                    password_hash=generate_password_hash('senha123'),
                    tipo_usuario=TipoUsuario.ADMIN, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cliente = Cliente(admin_id=admin.id, nome=f'Cli {tag}',
                      email=f'cli_ex_{tag}@test.local', telefone='11988880000')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra Export {tag}', codigo=f'EX{tag[-6:]}',
                admin_id=admin.id, cliente_id=cliente.id,
                status='Em andamento', data_inicio=date(2026, 7, 1))
    db.session.add(obra)
    db.session.commit()

    def _tarefa(nome, ordem, pai_id=None, uid=None):
        t = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, tarefa_pai_id=pai_id,
            nome_tarefa=nome, ordem=ordem, duracao_dias=10,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 20),
            mpp_uid=uid if com_mpp_uid else None)
        db.session.add(t)
        db.session.commit()
        return t

    raiz = _tarefa('Casa', 1, uid=1)
    estrutura = _tarefa('Estrutura', 2, raiz.id, uid=2)
    folha = _tarefa('Execução de Forro', 3, estrutura.id, uid=59)
    return admin.id, obra, {'raiz': raiz, 'estrutura': estrutura,
                            'folha': folha}


def _mapa_para(tarefas, com_mpp_uid=True):
    chave = 59 if com_mpp_uid else -tarefas['folha'].id
    return {chave: {'nome': 'Execução de Forro', 'pai': 'Estrutura',
                    'caminho': ['Casa', 'Estrutura']}}


def _criar_rdo_via_updater(obra, admin_id, tarefas, data='2026-07-14',
                           pct=40, com_mpp_uid=True):
    from services.atualizacao_rdos import atualizar_rdos
    chave = 59 if com_mpp_uid else -tarefas['folha'].id
    payload = [{'data': data, 'clima': 'Nublado',
                'precipitacao': 'Sem chuva',
                'comentario': 'Execução do forro da suíte 2.',
                'apontamentos': [{'tarefa_mpp': chave, 'pct': pct}]}]
    rel = atualizar_rdos(obra, admin_id, payload, com_fotos=False,
                         mapa_mpp_nome=_mapa_para(tarefas, com_mpp_uid))
    assert rel['pendencias'] == []
    return rel


# ── round-trip ────────────────────────────────────────────────────────
@pytest.mark.integration
def test_round_trip_export_reimport_em_obra_clone():
    from services.atualizacao_rdos import atualizar_rdos
    from services.exportacao_rdos import exportar_obra
    from models import RDO, RDOApontamentoCronograma
    with app.app_context():
        admin_a, obra_a, tarefas_a = _ambiente()
        _criar_rdo_via_updater(obra_a, admin_a, tarefas_a, pct=65)

        conteudo, avisos = exportar_obra(obra_a, admin_a)
        itens = conteudo['rdos.json']['rdos']
        assert [i['data'] for i in itens] == ['2026-07-14']
        item = itens[0]
        assert item['clima'] == 'Nublado'
        assert item['comentario'] == 'Execução do forro da suíte 2.'
        assert item['apontamentos'] == [{'tarefa_mpp': 59, 'pct': 65.0}]
        # contexto de revisão presente, com o prefixo que o updater ignora
        assert item['_estado'] == 'preenchido'
        assert item['_numero_rdo'].startswith('RDO-')

        # aplica o export VERBATIM numa obra clone de outro tenant
        admin_b, obra_b, _ = _ambiente()
        mapa = {int(k): v for k, v in conteudo['mapa_nomes.json'].items()}
        rel = atualizar_rdos(obra_b, admin_b, conteudo['rdos.json']['rdos'],
                             com_fotos=False, mapa_mpp_nome=mapa)
        assert rel['pendencias'] == []
        assert rel['criados'] == ['2026-07-14']

        rdo_b = RDO.query.filter_by(obra_id=obra_b.id).one()
        assert rdo_b.clima_geral == 'Nublado'
        assert rdo_b.comentario_geral == 'Execução do forro da suíte 2.'
        ap = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo_b.id).one()
        assert ap.percentual_realizado == pytest.approx(65.0)


@pytest.mark.integration
def test_reimport_na_mesma_obra_e_idempotente():
    """Exportar e reaplicar na PRÓPRIA obra não duplica nem muda nada —
    o ciclo exportar → revisar → upsert precisa ser seguro por default."""
    from services.atualizacao_rdos import atualizar_rdos
    from services.exportacao_rdos import exportar_obra
    from models import RDO
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        _criar_rdo_via_updater(obra, admin_id, tarefas)

        conteudo, _ = exportar_obra(obra, admin_id)
        mapa = {int(k): v for k, v in conteudo['mapa_nomes.json'].items()}
        rel = atualizar_rdos(obra, admin_id, conteudo['rdos.json']['rdos'],
                             com_fotos=False, mapa_mpp_nome=mapa)
        assert rel['criados'] == []
        assert rel['atualizados'] == ['2026-07-14']
        assert rel['pendencias'] == []
        assert RDO.query.filter_by(obra_id=obra.id).count() == 1


# ── obra sem mpp_uid: chave negativa + mapa ───────────────────────────
@pytest.mark.integration
def test_obra_sem_mpp_uid_usa_chave_negativa_e_mapa_resolve():
    from services.atualizacao_rdos import atualizar_rdos
    from services.exportacao_rdos import exportar_obra
    from models import RDOApontamentoCronograma
    with app.app_context():
        admin_id, obra, tarefas = _ambiente(com_mpp_uid=False)
        _criar_rdo_via_updater(obra, admin_id, tarefas, com_mpp_uid=False)

        conteudo, avisos = exportar_obra(obra, admin_id)
        chave = conteudo['rdos.json']['rdos'][0]['apontamentos'][0]['tarefa_mpp']
        assert chave == -tarefas['folha'].id, \
            'sem mpp_uid a chave DEVE ser negativa: id positivo colide com uid real'
        ref = conteudo['mapa_nomes.json'][str(chave)]
        assert ref['nome'] == 'Execução de Forro'
        assert ref['caminho'] == ['Casa', 'Estrutura']
        assert any('sem mpp_uid' in a for a in avisos)

        # o reimport resolve pelo mapa (uid negativo nunca casa _por_uid)
        rel = atualizar_rdos(obra, admin_id, conteudo['rdos.json']['rdos'],
                             com_fotos=False,
                             mapa_mpp_nome={int(k): v for k, v
                                            in conteudo['mapa_nomes.json'].items()})
        assert rel['pendencias'] == []
        assert rel['atualizados'] == ['2026-07-14']
        assert RDOApontamentoCronograma.query.count() >= 1


# ── imutável ──────────────────────────────────────────────────────────
@pytest.mark.integration
def test_rdo_imutavel_exporta_estado_e_reimport_pula():
    from services.atualizacao_rdos import atualizar_rdos
    from services.exportacao_rdos import exportar_obra
    from models import RDO
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        _criar_rdo_via_updater(obra, admin_id, tarefas)
        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        db.session.execute(
            db.text('UPDATE rdo SET estado = :e WHERE id = :i'),
            {'e': 'assinado', 'i': rdo.id})
        db.session.commit()
        db.session.expire_all()

        conteudo, _ = exportar_obra(obra, admin_id)
        assert conteudo['rdos.json']['rdos'][0]['_estado'] == 'assinado'

        rel = atualizar_rdos(obra, admin_id, conteudo['rdos.json']['rdos'],
                             com_fotos=False)
        assert rel['atualizados'] == []
        assert [p['data'] for p in rel['pulados']] == ['2026-07-14']


# ── data duplicada ────────────────────────────────────────────────────
@pytest.mark.integration
def test_data_duplicada_exporta_o_primeiro_como_o_updater():
    """O updater atualiza `existentes[0]` (menor id) — o export retrata o
    MESMO RDO, senão a mescla decide olhando um e a aplicação escreve noutro."""
    from services.exportacao_rdos import exportar_obra
    from models import RDO
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        _criar_rdo_via_updater(obra, admin_id, tarefas)
        extra = RDO(numero_rdo=f'RDO-DUP-{obra.id}', obra_id=obra.id,
                    admin_id=admin_id, data_relatorio=date(2026, 7, 14),
                    comentario_geral='linha duplicada mais nova',
                    local='Campo', status='Finalizado', estado='preenchido')
        db.session.add(extra)
        db.session.commit()

        conteudo, avisos = exportar_obra(obra, admin_id)
        itens = conteudo['rdos.json']['rdos']
        assert len(itens) == 1
        assert itens[0]['comentario'] == 'Execução do forro da suíte 2.', \
            'tem que exportar o PRIMEIRO (o que o updater atualiza)'
        assert any('mais de um RDO nesta data' in a for a in avisos)


# ── obra.json e zip ───────────────────────────────────────────────────
@pytest.mark.integration
def test_obra_json_carrega_identidade_e_tarefas():
    from services.exportacao_rdos import exportar_obra, montar_zip
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        _criar_rdo_via_updater(obra, admin_id, tarefas)

        conteudo, _ = exportar_obra(obra, admin_id)
        oj = conteudo['obra.json']
        assert oj['obra']['codigo'] == obra.codigo
        assert oj['obra']['admin_id'] == admin_id
        assert oj['cronograma']['tarefas_vivas'] == 3
        assert oj['cronograma']['tarefas_com_mpp_uid'] == 3
        assert oj['rdos']['total'] == 1
        nomes = {t['nome'] for t in oj['cronograma_tarefas']}
        assert nomes == {'Casa', 'Estrutura', 'Execução de Forro'}

        buf = montar_zip(conteudo)
        with zipfile.ZipFile(buf) as zf:
            assert set(zf.namelist()) == {'obra.json', 'rdos.json',
                                          'mapa_nomes.json'}
            relido = json.loads(zf.read('rdos.json'))
            assert relido['rdos'][0]['data'] == '2026-07-14'


# ── rota: tenant e conteúdo ───────────────────────────────────────────
def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c


@pytest.mark.integration
def test_rota_devolve_zip_do_tenant_e_404_para_obra_alheia():
    with app.app_context():
        admin_a, obra_a, tarefas_a = _ambiente()
        _criar_rdo_via_updater(obra_a, admin_a, tarefas_a)
        admin_b, obra_b, _ = _ambiente()
        obra_a_id, obra_b_id = obra_a.id, obra_b.id

    cli = _cliente_de(admin_a)
    ok = cli.get(f'/obras/{obra_a_id}/rdos/exportar')
    assert ok.status_code == 200
    assert ok.headers['Content-Type'] == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(ok.data)) as zf:
        assert 'rdos.json' in zf.namelist()
        rdos = json.loads(zf.read('rdos.json'))['rdos']
        assert [i['data'] for i in rdos] == ['2026-07-14']

    alheia = cli.get(f'/obras/{obra_b_id}/rdos/exportar')
    assert alheia.status_code == 404, \
        'obra de outro tenant tem que ser 404 — nem existência vaza'
