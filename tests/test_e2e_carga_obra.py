"""E2E da carga não-destrutiva: rota de export → zip do WhatsApp →
CLI de mescla/distribuição → CLI de aplicação → banco.

Nada é simulado por atalho: o zip de export sai da ROTA HTTP real, o
WhatsApp é um export iOS sintético mas no formato byte-a-byte do iPhone
(cabeçalho `[DD/MM/AAAA, HH:MM:SS]`, `<anexado:>`, fotos de verdade), o
cronograma entra como MSPDI (.xml — mesmo parser do .mpp, sem JVM), e a
aplicação passa pelas DUAS CLIs (`preparar_carga_obra.main` e
`atualizar_rdos_obra.main`, esta exercitando o fallback obra-sem-código).

Cenário A (obra nova, estilo Angela): codigo=None, zero RDOs, tarefas já
com mpp_uid (estado pós-import do cronograma pela tela). Verifica RDOs
criados, comentário sem a linha do marcador, fotos anexadas com legenda,
typo de ano corrigido, % do cronograma distribuído pelas datas certas e
idempotência da reaplicação.

Cenário B (obra em andamento, estilo OB004): dia vazio é enriquecido; dia
com texto divergente fica INTACTO (conflito segurado); RDO assinado fica
intacto; dia com foto no banco preserva a foto; data DUPLICADA recebe o
texto no PRIMEIRO RDO (o mesmo que o export novo retrata).
"""
import io
import json
import os
import sys
import uuid
import zipfile

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../scripts'))

from datetime import date                                # noqa: E402

import pytest                                            # noqa: E402
from werkzeug.security import generate_password_hash     # noqa: E402

import main  # noqa: F401,E402 — registra os blueprints
from app import app, db                                  # noqa: E402

import atualizar_rdos_obra                               # noqa: E402
import preparar_carga_obra                               # noqa: E402

MARCADOR = 'Obra Itu'  # marcador conhecido — reaproveita a lista real


# ── construção do ambiente ────────────────────────────────────────────
def _tenant_obra(codigo=None, uids=(101, 102, 103)):
    from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario
    tag = uuid.uuid4().hex[:10]
    admin = Usuario(username=f'e2e_{tag}', email=f'e2e_{tag}@test.local',
                    nome=f'Admin E2E {tag}',
                    password_hash=generate_password_hash('senha123'),
                    tipo_usuario=TipoUsuario.ADMIN, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()
    cliente = Cliente(admin_id=admin.id, nome=f'Cli {tag}',
                      email=f'cli_{tag}@test.local', telefone='11977770000')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra E2E {tag}', codigo=codigo, admin_id=admin.id,
                cliente_id=cliente.id, status='Em andamento',
                data_inicio=date(2026, 5, 1))
    db.session.add(obra)
    db.session.commit()

    raiz = TarefaCronograma(obra_id=obra.id, admin_id=admin.id,
                            nome_tarefa='Raiz', ordem=1, duracao_dias=30,
                            mpp_uid=100)
    db.session.add(raiz)
    db.session.commit()
    tarefas = {}
    for i, uid in enumerate(uids, start=2):
        t = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, tarefa_pai_id=raiz.id,
            nome_tarefa=f'Tarefa {uid}', ordem=i, duracao_dias=10,
            data_inicio=date(2026, 6, 1), data_fim=date(2026, 6, 10),
            mpp_uid=uid)
        db.session.add(t)
        tarefas[uid] = t
    db.session.commit()
    return admin, obra, tarefas


def _jpg():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buf, 'JPEG')
    return buf.getvalue()


def _wa_zip(caminho, blocos, fotos=()):
    """Export iOS sintético: blocos = [(hora_header, corpo)], fotos = nomes."""
    linhas = []
    for header, corpo in blocos:
        primeira, *resto = corpo.split('\n')
        linhas.append(f'[{header}] Abel: {primeira}')
        linhas.extend(resto)
    with zipfile.ZipFile(caminho, 'w') as zf:
        zf.writestr('_chat.txt', '\n'.join(linhas) + '\n')
        for nome in fotos:
            zf.writestr(nome, _jpg())


def _mspdi(caminho, tarefas):
    """MSPDI mínimo: tarefas = [(uid, nome, pct, fim, resumo)]."""
    ts = []
    for i, (uid, nome, pct, fim, resumo) in enumerate(tarefas, start=1):
        ts.append(
            f'<Task><UID>{uid}</UID><ID>{i}</ID><Name>{nome}</Name>'
            f'<OutlineLevel>{1 if resumo else 2}</OutlineLevel>'
            f'<Start>2026-05-01T08:00:00</Start>'
            f'<Finish>{fim}T17:00:00</Finish>'
            f'<Duration>PT80H0M0S</Duration>'
            f'<PercentComplete>{pct}</PercentComplete>'
            f'<Summary>{1 if resumo else 0}</Summary>'
            f'<Milestone>0</Milestone></Task>')
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<Project xmlns="http://schemas.microsoft.com/project">'
           f'<Name>E2E</Name><Tasks>{"".join(ts)}</Tasks></Project>')
    with open(caminho, 'w', encoding='utf-8') as fh:
        fh.write(xml)


def _exportar_zip_via_rota(admin_id, obra_id, destino):
    cli = app.test_client()
    with cli.session_transaction() as s:
        s['_user_id'] = str(admin_id)
        s['_fresh'] = True
    resp = cli.get(f'/obras/{obra_id}/rdos/exportar')
    assert resp.status_code == 200, resp.status_code
    with open(destino, 'wb') as fh:
        fh.write(resp.data)


# ── Cenário A: obra nova, estilo Angela ───────────────────────────────
@pytest.mark.integration
def test_e2e_obra_nova_fluxo_completo(tmp_path):
    from models import RDO, RDOApontamentoCronograma, RDOFoto

    with app.app_context():
        admin, obra, tarefas = _tenant_obra(codigo=None)
        admin_id, obra_id, username = admin.id, obra.id, admin.username

        _exportar_zip_via_rota(admin_id, obra_id, tmp_path / 'export.zip')

        _wa_zip(
            tmp_path / 'wa.zip',
            blocos=[
                ('10/06/2026, 17:00:00',
                 f'*10/06/2026*\n*{MARCADOR}*\n\nEfetivo:\n- Abel\n\n'
                 f'Atividade:\nPlaqueamento do forro'),
                ('10/06/2026, 17:01:00', '<anexado: IMG-1.jpg>\nForro pronto'),
                ('10/06/2026, 17:02:00', '<anexado: IMG-2.jpg>'),
                # typo de ano — o RDO real é de 05/06/2026
                ('06/06/2026, 08:00:00',
                 f'*05/06/2016*\n*{MARCADOR}*\n\nEfetivo:\n- Abel\n\n'
                 f'Atividade:\nMontagem de andaimes'),
            ],
            fotos=['IMG-1.jpg', 'IMG-2.jpg'])

        _mspdi(tmp_path / 'crono.xml', [
            (100, 'Raiz', 100, '2026-06-10', True),      # resumo: fora
            (101, 'Tarefa 101', 100, '2026-06-03', False),  # → 06-05
            (102, 'Tarefa 102', 100, '2026-09-01', False),  # → último (06-10)
            (103, 'Tarefa 103', 40, '2026-06-20', False),   # parcial → último
        ])

        rc = preparar_carga_obra.main([
            '--export', str(tmp_path / 'export.zip'),
            '--whatsapp', str(tmp_path / 'wa.zip'),
            '--obra-marcador', MARCADOR,
            '--corrigir-data', '2016-06-05=2026-06-05',
            '--mpp', str(tmp_path / 'crono.xml'),
            '--saida-dir', str(tmp_path / 'saida'),
            '--fotos-base', str(tmp_path / 'fotos'),
        ])
        assert rc == 0
        payload = json.load(open(tmp_path / 'saida' / f'carga_obra_{obra_id}.json'))
        assert [i['data'] for i in payload['rdos']] == \
            ['2026-06-05', '2026-06-10']

        # aplicação pela CLI real — obra SEM código: fallback por id
        rc = atualizar_rdos_obra.main([
            username, str(obra_id),
            str(tmp_path / 'saida' / f'carga_obra_{obra_id}.json'),
            '--fotos-base', str(tmp_path / 'fotos')])
        assert rc == 0

        rdos = (RDO.query.filter_by(obra_id=obra_id)
                .order_by(RDO.data_relatorio).all())
        assert [r.data_relatorio.isoformat() for r in rdos] == \
            ['2026-06-05', '2026-06-10']
        # marcador não vaza; conteúdo verbatim
        assert rdos[0].comentario_geral.startswith('Efetivo:')
        assert 'Montagem de andaimes' in rdos[0].comentario_geral

        fotos = (RDOFoto.query.filter_by(rdo_id=rdos[1].id)
                 .order_by(RDOFoto.ordem).all())
        assert len(fotos) == 2
        assert fotos[0].legenda == 'Forro pronto'

        # % do .mpp distribuído: 101→100 no 06-05; 102→100 e 103→40 no 06-10
        def _pcts(rdo):
            return {a.tarefa_cronograma_id: a.percentual_realizado
                    for a in RDOApontamentoCronograma.query
                    .filter_by(rdo_id=rdo.id)}
        from models import TarefaCronograma
        por_uid = {t.mpp_uid: t.id for t in TarefaCronograma.query
                   .filter_by(obra_id=obra_id)}
        assert _pcts(rdos[0]) == {por_uid[101]: 100.0}
        assert _pcts(rdos[1]) == {por_uid[102]: 100.0, por_uid[103]: 40.0}

        # idempotência: reaplicar não duplica nada
        antes = (RDO.query.filter_by(obra_id=obra_id).count(),
                 RDOApontamentoCronograma.query.join(RDO)
                 .filter(RDO.obra_id == obra_id).count(),
                 RDOFoto.query.join(RDO).filter(RDO.obra_id == obra_id).count())
        rc = atualizar_rdos_obra.main([
            username, str(obra_id),
            str(tmp_path / 'saida' / f'carga_obra_{obra_id}.json'),
            '--fotos-base', str(tmp_path / 'fotos')])
        assert rc == 0
        depois = (RDO.query.filter_by(obra_id=obra_id).count(),
                  RDOApontamentoCronograma.query.join(RDO)
                  .filter(RDO.obra_id == obra_id).count(),
                  RDOFoto.query.join(RDO).filter(RDO.obra_id == obra_id).count())
        assert depois == antes


# ── Cenário B: obra em andamento, estilo OB004 ────────────────────────
@pytest.mark.integration
def test_e2e_obra_em_andamento_protege_o_que_existe(tmp_path):
    from models import RDO, RDOFoto

    with app.app_context():
        admin, obra, _ = _tenant_obra(codigo='E2E-B')
        admin_id, obra_id, username = admin.id, obra.id, admin.username

        def _rdo(dia, comentario=None, estado='preenchido', numero=None):
            r = RDO(numero_rdo=numero or f'RDO-{obra_id}-{dia.strftime("%Y%m%d")}',
                    obra_id=obra_id, admin_id=admin_id, data_relatorio=dia,
                    comentario_geral=comentario, local='Campo',
                    status='Finalizado', estado='preenchido')
            db.session.add(r)
            db.session.commit()
            if estado != 'preenchido':
                # Pela máquina de estados, não no braço: um UPDATE direto
                # deixa o RDO 'assinado' SEM linha em rdo_transicao_estado, e
                # `test_fase5_rdo_ciclo_vida.test_backfill_marcou_os_rdos_
                # historicos_como_preenchido` lê isso — corretamente — como
                # autoria forjada. Num banco de dev compartilhado a linha fica
                # para sempre, então cada rodada desta suíte somava uma falha
                # ao gate de todo mundo.
                from services.rdo_ciclo_vida import transicionar
                transicionar(r, estado, motivo='setup de teste')
                db.session.commit()
            return r

        r_vazio = _rdo(date(2026, 6, 1))
        r_texto = _rdo(date(2026, 6, 2), 'Resumo já redigido.')
        r_assinado = _rdo(date(2026, 6, 3), 'Dia assinado.', estado='assinado')
        r_foto = _rdo(date(2026, 6, 4))
        foto_antiga = RDOFoto(admin_id=admin_id, rdo_id=r_foto.id,
                              nome_arquivo='antiga.jpg',
                              caminho_arquivo='uploads/rdo/x/antiga.jpg',
                              legenda='antiga', ordem=1)
        db.session.add(foto_antiga)
        # data duplicada: o PRIMEIRO (menor id) é o alvo do updater
        r_dup1 = _rdo(date(2026, 6, 5), None, numero=f'RDO-D1-{obra_id}')
        r_dup2 = _rdo(date(2026, 6, 5), 'Cópia mais nova.',
                      numero=f'RDO-D2-{obra_id}')
        db.session.commit()
        ids = {'vazio': r_vazio.id, 'texto': r_texto.id,
               'assinado': r_assinado.id, 'foto': r_foto.id,
               'dup1': r_dup1.id, 'dup2': r_dup2.id}

        _exportar_zip_via_rota(admin_id, obra_id, tmp_path / 'export.zip')

        def _bloco(d):
            return (f'{d.strftime("%d/%m/%Y")}, 18:00:00',
                    f'*{d.strftime("%d/%m/%Y")}*\n*{MARCADOR}*\n\n'
                    f'Texto do chat de {d.strftime("%d/%m")}')
        _wa_zip(tmp_path / 'wa.zip',
                blocos=[_bloco(date(2026, 6, d)) for d in (1, 2, 3, 4, 5)] + [
                    ('04/06/2026, 18:01:00', '<anexado: IMG-9.jpg>\nnova')],
                fotos=['IMG-9.jpg'])

        rc = preparar_carga_obra.main([
            '--export', str(tmp_path / 'export.zip'),
            '--whatsapp', str(tmp_path / 'wa.zip'),
            '--obra-marcador', MARCADOR,
            '--saida-dir', str(tmp_path / 'saida'),
            '--fotos-base', str(tmp_path / 'fotos')])
        assert rc == 0

        rc = atualizar_rdos_obra.main([
            username, 'E2E-B',
            str(tmp_path / 'saida' / 'carga_obra_E2E-B.json'),
            '--fotos-base', str(tmp_path / 'fotos')])
        assert rc == 0
        db.session.expire_all()

        get = lambda i: db.session.get(RDO, i)  # noqa: E731
        # dia vazio: enriquecido
        assert get(ids['vazio']).comentario_geral == 'Texto do chat de 01/06'
        # conflito: intacto
        assert get(ids['texto']).comentario_geral == 'Resumo já redigido.'
        # assinado: intacto
        assert get(ids['assinado']).comentario_geral == 'Dia assinado.'
        # foto antiga preservada; a do chat NÃO substitui
        fotos = RDOFoto.query.filter_by(rdo_id=ids['foto']).all()
        assert [f.legenda for f in fotos] == ['antiga']
        # texto do dia 04/06 entra mesmo assim (comentário estava vazio)
        assert get(ids['foto']).comentario_geral == 'Texto do chat de 04/06'
        # data duplicada com export novo: o texto vai para o PRIMEIRO
        assert get(ids['dup1']).comentario_geral == 'Texto do chat de 05/06'
        assert get(ids['dup2']).comentario_geral == 'Cópia mais nova.'
        # nenhum RDO novo
        assert RDO.query.filter_by(obra_id=obra_id).count() == 6
