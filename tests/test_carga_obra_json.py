"""Carga única por JSON (services/carga_obra_json.py + tela da obra).

O que estes testes travam:

  • cronograma: casada por nome ÚNICO preserva o id (RDOs/medições
    intactos) e ganha `mpp_uid`; nova insere; ausente vira `ativa=False` —
    a contagem total NUNCA encolhe; `percentual_concluido` não é tocado
    pela fase de cronograma;
  • versionamento: a ativa anterior é arquivada com snapshot e a nova
    versão ativa nasce com snapshot — sempre há a que restaurar;
  • prévia (dry_run) reverte AS DUAS fases;
  • JSON de outra obra é recusado antes de escrever; fotos_base com
    travessia é recusada;
  • fluxo completo pela TELA: preparar_carga_obra gera o carga_obra_*.json
    e o upload na rota aplica cronograma + RDOs + apontamentos de % de
    uma vez (o caso real Angela/OB004).
"""
import io
import json
import os
import re
import sys
import uuid
import zipfile

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../scripts'))

from datetime import date                                # noqa: E402

import pytest                                            # noqa: E402
from werkzeug.security import generate_password_hash     # noqa: E402

import main  # noqa: F401,E402
from app import app, db                                  # noqa: E402

import preparar_carga_obra                               # noqa: E402


def _tenant_obra(codigo=None, nomes=('Estrutura', 'Tarefa Antiga')):
    from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario
    tag = uuid.uuid4().hex[:10]
    admin = Usuario(username=f'cj_{tag}', email=f'cj_{tag}@test.local',
                    nome=f'Admin CJ {tag}',
                    password_hash=generate_password_hash('senha123'),
                    tipo_usuario=TipoUsuario.ADMIN, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()
    cliente = Cliente(admin_id=admin.id, nome=f'Cli {tag}',
                      email=f'cli_cj_{tag}@test.local', telefone='11966660000')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra CJ {tag}', codigo=codigo, admin_id=admin.id,
                cliente_id=cliente.id, status='Em andamento',
                data_inicio=date(2026, 5, 1))
    db.session.add(obra)
    db.session.commit()
    tarefas = {}
    for i, nome in enumerate(nomes, start=1):
        t = TarefaCronograma(obra_id=obra.id, admin_id=admin.id,
                             nome_tarefa=nome, ordem=i, duracao_dias=5,
                             percentual_concluido=12.0)
        db.session.add(t)
        tarefas[nome] = t
    db.session.commit()
    return admin, obra, tarefas


def _payload(obra, **extra):
    base = {
        '_meta': {'formato': 'carga-obra/1.0'},
        'obra': {'id': obra.id, 'codigo': obra.codigo, 'nome': obra.nome},
        'cronograma_tarefas': [
            {'uid': 1, 'nome': 'Raiz', 'outline': 1,
             'inicio': '2026-05-01', 'fim': '2026-06-30', 'dias': 40,
             'resumo': True},
            {'uid': 2, 'nome': 'Estrutura', 'outline': 2,
             'inicio': '2026-05-01', 'fim': '2026-05-20', 'dias': 14,
             'resumo': False},
            {'uid': 3, 'nome': 'Nova Frente', 'outline': 2,
             'inicio': '2026-05-21', 'fim': '2026-06-30', 'dias': 26,
             'resumo': False},
        ],
        'mapa_nomes': {},
        'rdos': [],
    }
    base.update(extra)
    return base


# ── serviço: cronograma não-destrutivo + versionamento ────────────────
@pytest.mark.integration
def test_cronograma_casa_insere_arquiva_sem_apagar():
    from models import CronogramaTarefaSnapshot, CronogramaVersao, \
        TarefaCronograma
    from services.carga_obra_json import aplicar_carga_obra
    with app.app_context():
        admin, obra, tarefas = _tenant_obra()
        id_estrutura = tarefas['Estrutura'].id
        id_antiga = tarefas['Tarefa Antiga'].id

        rel = aplicar_carga_obra(obra, admin.id, _payload(obra),
                                 dry_run=False)
        c = rel['cronograma']
        assert (c['casadas_nome'], c['inseridas']) == (1, 2)
        assert c['arquivadas'] == ['Tarefa Antiga']

        estrutura = db.session.get(TarefaCronograma, id_estrutura)
        assert estrutura.mpp_uid == 2, 'casada ganha o uid (backfill)'
        assert estrutura.data_fim == date(2026, 5, 20)
        assert estrutura.percentual_concluido == pytest.approx(12.0), \
            'fase de cronograma NUNCA toca o percentual'
        antiga = db.session.get(TarefaCronograma, id_antiga)
        assert antiga is not None and antiga.ativa is False, \
            'ausente do JSON é arquivada, jamais apagada'

        raiz = TarefaCronograma.query.filter_by(
            obra_id=obra.id, mpp_uid=1).one()
        nova = TarefaCronograma.query.filter_by(
            obra_id=obra.id, mpp_uid=3).one()
        assert nova.tarefa_pai_id == raiz.id, 'hierarquia pela pilha de outline'

        versao = CronogramaVersao.query.filter_by(
            obra_id=obra.id, status='ativa').one()
        assert CronogramaTarefaSnapshot.query.filter_by(
            versao_id=versao.id).count() == 3, 'nova versão com snapshot'


@pytest.mark.integration
def test_previa_reverte_as_duas_fases():
    from models import CronogramaVersao, TarefaCronograma
    from services.carga_obra_json import aplicar_carga_obra
    with app.app_context():
        admin, obra, tarefas = _tenant_obra()
        payload = _payload(obra, rdos=[{'data': '2026-05-10',
                                        'comentario': 'dia de prévia'}])
        rel = aplicar_carga_obra(obra, admin.id, payload, dry_run=True)
        assert rel['dry_run'] is True

        db.session.expire_all()
        assert TarefaCronograma.query.filter_by(obra_id=obra.id).count() == 2
        assert tarefas['Tarefa Antiga'].ativa is True
        assert CronogramaVersao.query.filter_by(obra_id=obra.id).count() == 0
        from models import RDO
        assert RDO.query.filter_by(obra_id=obra.id).count() == 0


@pytest.mark.integration
def test_json_de_outra_obra_e_recusado():
    from services.carga_obra_json import CargaInvalida, aplicar_carga_obra
    with app.app_context():
        admin, obra, _ = _tenant_obra()
        _, outra, _ = _tenant_obra()
        payload = _payload(outra)
        with pytest.raises(CargaInvalida):
            aplicar_carga_obra(obra, admin.id, payload, dry_run=True)


@pytest.mark.integration
def test_fotos_base_com_travessia_e_recusada():
    from services.carga_obra_json import CargaInvalida, aplicar_carga_obra
    with app.app_context():
        admin, obra, _ = _tenant_obra()
        for ruim in ('../fora', '/abs/fora', 'fotos_rdos/../segredo'):
            with pytest.raises(CargaInvalida):
                aplicar_carga_obra(obra, admin.id,
                                   _payload(obra, fotos_base=ruim),
                                   dry_run=True)


# ── fluxo completo pela tela ──────────────────────────────────────────
def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c


def _csrf_de(cli, url):
    pagina = cli.get(url)
    assert pagina.status_code == 200
    m = re.search(rb'name="csrf_token" value="([^"]+)"', pagina.data)
    assert m, 'página sem csrf_token'
    return m.group(1).decode()


@pytest.mark.integration
def test_fluxo_completo_preparar_e_subir_pela_tela(tmp_path):
    from models import RDO, RDOApontamentoCronograma, TarefaCronograma

    with app.app_context():
        admin, obra, tarefas = _tenant_obra(codigo=None)
        admin_id, obra_id = admin.id, obra.id
        id_estrutura = tarefas['Estrutura'].id

        # export real pela rota
        cli = _cliente_de(admin_id)
        resp = cli.get(f'/obras/{obra_id}/rdos/exportar')
        assert resp.status_code == 200
        (tmp_path / 'export.zip').write_bytes(resp.data)

        # WhatsApp iOS mínimo: 1 dia de RDO
        with zipfile.ZipFile(tmp_path / 'wa.zip', 'w') as zf:
            zf.writestr('_chat.txt',
                        '[10/06/2026, 18:00:00] Abel: *10/06/2026*\n'
                        '*Obra Itu*\n\nEfetivo:\n- Abel\n\n'
                        'Atividade:\nMontagem da nova frente\n')

        # cronograma MSPDI: Estrutura 100% (fim antes do RDO), Nova 40%
        xml = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<Project xmlns="http://schemas.microsoft.com/project">'
               '<Name>CJ</Name><Tasks>'
               '<Task><UID>1</UID><ID>1</ID><Name>Raiz</Name>'
               '<OutlineLevel>1</OutlineLevel><Start>2026-05-01T08:00:00</Start>'
               '<Finish>2026-06-30T17:00:00</Finish><Duration>PT320H0M0S</Duration>'
               '<PercentComplete>70</PercentComplete><Summary>1</Summary>'
               '<Milestone>0</Milestone></Task>'
               '<Task><UID>2</UID><ID>2</ID><Name>Estrutura</Name>'
               '<OutlineLevel>2</OutlineLevel><Start>2026-05-01T08:00:00</Start>'
               '<Finish>2026-05-20T17:00:00</Finish><Duration>PT112H0M0S</Duration>'
               '<PercentComplete>100</PercentComplete><Summary>0</Summary>'
               '<Milestone>0</Milestone></Task>'
               '<Task><UID>3</UID><ID>3</ID><Name>Nova Frente</Name>'
               '<OutlineLevel>2</OutlineLevel><Start>2026-05-21T08:00:00</Start>'
               '<Finish>2026-06-30T17:00:00</Finish><Duration>PT208H0M0S</Duration>'
               '<PercentComplete>40</PercentComplete><Summary>0</Summary>'
               '<Milestone>0</Milestone>'
               '<PredecessorLink><PredecessorUID>2</PredecessorUID>'
               '<Type>1</Type><LinkLag>4800</LinkLag></PredecessorLink>'
               '</Task>'
               '</Tasks></Project>')
        (tmp_path / 'crono.xml').write_text(xml, encoding='utf-8')

        rc = preparar_carga_obra.main([
            '--export', str(tmp_path / 'export.zip'),
            '--whatsapp', str(tmp_path / 'wa.zip'),
            '--obra-marcador', 'Obra Itu',
            '--mpp', str(tmp_path / 'crono.xml'),
            '--saida-dir', str(tmp_path / 'saida'),
            '--fotos-base',
            os.path.join('fotos_rdos', 'obras', f'teste-{obra_id}'),
        ])
        assert rc == 0
        caminho = tmp_path / 'saida' / f'carga_obra_{obra_id}.json'
        carga = json.loads(caminho.read_text())
        assert carga['_meta']['formato'].startswith('carga-obra/1.')
        assert carga['obra']['id'] == obra_id
        assert len(carga['cronograma_tarefas']) == 3

        url = f'/obras/{obra_id}/rdos/carga'
        token = _csrf_de(cli, url)

        # PRÉVIA: relatório sai, banco intacto
        r = cli.post(url, data={
            'csrf_token': token, 'modo': 'previa',
            'arquivo': (io.BytesIO(caminho.read_bytes()), 'carga.json')},
            content_type='multipart/form-data')
        assert r.status_code == 200
        assert 'PRÉVIA'.encode() in r.data or b'previa' in r.data
        assert RDO.query.filter_by(obra_id=obra_id).count() == 0
        assert TarefaCronograma.query.filter_by(obra_id=obra_id).count() == 2

        # APLICAR
        token = _csrf_de(cli, url)
        r = cli.post(url, data={
            'csrf_token': token, 'modo': 'aplicar',
            'arquivo': (io.BytesIO(caminho.read_bytes()), 'carga.json')},
            content_type='multipart/form-data')
        assert r.status_code == 200

        estrutura = db.session.get(TarefaCronograma, id_estrutura)
        assert estrutura.mpp_uid == 2
        rdo = RDO.query.filter_by(obra_id=obra_id).one()
        assert rdo.data_relatorio == date(2026, 6, 10)
        assert rdo.comentario_geral.startswith('Efetivo:')
        pcts = {a.tarefa_cronograma_id: a.percentual_realizado
                for a in RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id)}
        nova = TarefaCronograma.query.filter_by(obra_id=obra_id,
                                                mpp_uid=3).one()
        assert pcts[estrutura.id] == pytest.approx(100.0)
        assert pcts[nova.id] == pytest.approx(40.0)
        assert estrutura.percentual_concluido == pytest.approx(100.0)

        # predecessora do MSPDI (Type 1 = FS, LinkLag 4800 = 1 dia útil)
        from models import TarefaVinculo
        v = TarefaVinculo.query.filter_by(obra_id=obra_id).one()
        assert (v.predecessora_id, v.sucessora_id) == (estrutura.id, nova.id)
        assert (v.tipo, v.lag_dias) == ('TI', 1)


@pytest.mark.integration
def test_rota_json_de_outra_obra_mostra_erro_e_tenant_alheio_404():
    with app.app_context():
        admin, obra, _ = _tenant_obra()
        _, outra, _ = _tenant_obra()
        admin_id, obra_id = admin.id, obra.id
        payload = _payload(outra)

    cli = _cliente_de(admin_id)
    url = f'/obras/{obra_id}/rdos/carga'
    token = _csrf_de(cli, url)
    r = cli.post(url, data={
        'csrf_token': token, 'modo': 'previa',
        'arquivo': (io.BytesIO(json.dumps(payload).encode()), 'carga.json')},
        content_type='multipart/form-data')
    assert r.status_code == 200
    assert 'não desta'.encode() in r.data

    with app.app_context():
        alheia = cli.get(f'/obras/{outra.id}/rdos/carga')
    assert alheia.status_code == 404


@pytest.mark.integration
def test_predecessoras_do_json_viram_tarefa_vinculo():
    from models import TarefaCronograma, TarefaVinculo
    from services.carga_obra_json import aplicar_carga_obra
    with app.app_context():
        admin, obra, _ = _tenant_obra()
        payload = _payload(obra)
        # Nova Frente depende de Estrutura: FS+2 (inglês do MPXJ) e um
        # vínculo com ponta em resumo, que TEM que ser pulado com registro
        payload['cronograma_tarefas'][2]['predecessoras'] = [
            {'uid': 2, 'tipo': 'FS', 'lag_dias': 2.0},
            {'uid': 1, 'tipo': 'SS', 'lag_dias': 0},   # uid 1 é resumo
        ]
        rel = aplicar_carga_obra(obra, admin.id, payload, dry_run=False)
        c = rel['cronograma']
        assert c['vinculos'] == 1
        assert any('resumo' in v for v in c['vinculos_pulados'])

        estrutura = TarefaCronograma.query.filter_by(
            obra_id=obra.id, mpp_uid=2).one()
        nova = TarefaCronograma.query.filter_by(
            obra_id=obra.id, mpp_uid=3).one()
        v = TarefaVinculo.query.filter_by(obra_id=obra.id).one()
        assert (v.predecessora_id, v.sucessora_id) == (estrutura.id, nova.id)
        assert (v.tipo, v.lag_dias) == ('TI', 2), 'FS vira TI; lag inteiro'
        assert nova.predecessora_id == estrutura.id, \
            'legado espelhado com a primeira TI'

        # reaplicar substitui (delete+insert), não duplica
        rel2 = aplicar_carga_obra(obra, admin.id, payload, dry_run=False)
        assert TarefaVinculo.query.filter_by(obra_id=obra.id).count() == 1
