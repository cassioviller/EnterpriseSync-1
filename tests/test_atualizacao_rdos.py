"""Atualização NÃO-DESTRUTIVA de RDOs (services/atualizacao_rdos.py) e o
parser do export do WhatsApp (scripts/whatsapp_para_rdos.py).

O que estes testes travam:

  • o caminho novo NÃO apaga nada — é a razão de ele existir (o reimport
    físico-financeiro apaga tarefas, propostas, medições e todos os RDOs);
  • RDO imutável da Fase 5 é pulado SEM derrubar os outros dias;
  • `tarefa_mpp` que não resolve vira pendência no relatório, não silêncio;
  • `dry_run` não grava;
  • o parser data o RDO pelo TEXTO, não pela mensagem, e não deixa vazar
    RDO de outra obra do mesmo grupo.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from datetime import date, datetime, timedelta          # noqa: E402

import pytest                                            # noqa: E402
from werkzeug.security import generate_password_hash     # noqa: E402

from app import app, db                                  # noqa: E402


# ── ambiente mínimo: um tenant, uma obra, duas tarefas ────────────────
def _ambiente(com_mpp_uid=True):
    """Obra com a hierarquia real da Baia, em miniatura:

        Baias > Galpão A|B > Fundação > Execução de Ferragens Para Fundação

    O nome repetido nas duas pontas não é enfeite — é a ambiguidade do
    cronograma real, e o pai imediato ("Fundação") é o MESMO nos dois ramos.
    Quem desempata é o avô.
    """
    from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario

    tag = datetime.utcnow().strftime('%H%M%S%f')
    admin = Usuario(username=f'ar_{tag}', email=f'ar_{tag}@test.local',
                    nome=f'Admin AR {tag}',
                    password_hash=generate_password_hash('senha123'),
                    tipo_usuario=TipoUsuario.ADMIN, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cliente = Cliente(admin_id=admin.id, nome=f'Kabod {tag}',
                      email=f'cli_ar_{tag}@test.local', telefone='11999990000')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Baias Kabod {tag}', codigo=f'AR{tag[-6:]}',
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

    raiz = _tarefa('Baias', 1, uid=1)
    tarefas = {}
    # 14 é do Galpão B e 59 é do Galpão A — a ordem dos ids no cronograma
    # real é essa mesma, e trocar os dois é o erro que este ambiente pega.
    for nome_galpao, uid_galpao, uid in (('Galpão B', 200, 14),
                                         ('Galpão A', 100, 59)):
        galpao = _tarefa(nome_galpao, uid_galpao, raiz.id, uid_galpao)
        fundacao = _tarefa('Fundação', uid_galpao + 1, galpao.id, uid_galpao + 1)
        tarefas[uid] = _tarefa('Execução de Ferragens Para Fundação', uid,
                               fundacao.id, uid)
    return admin.id, obra, tarefas


_MAPA = {
    14: {'nome': 'Execução de Ferragens Para Fundação',
         'pai': 'Fundação', 'caminho': ['Baias', 'Galpão B', 'Fundação']},
    59: {'nome': 'Execução de Ferragens Para Fundação',
         'pai': 'Fundação', 'caminho': ['Baias', 'Galpão A', 'Fundação']},
}


def _payload(data='2026-07-14', pct=40, mpp=59, **extra):
    item = {'data': data, 'clima': 'Não informado',
            'precipitacao': 'Não informado',
            'comentario': 'Efetivo: 05 colaboradores\n\nAtividades executadas:\n'
                          '• Armação da primeira viga longitudinal.',
            'mao_de_obra': 0,
            'apontamentos': [{'tarefa_mpp': mpp, 'pct': pct}]}
    item.update(extra)
    return [item]


def _contagens(obra_id):
    from models import MedicaoContrato, RDO, TarefaCronograma
    return (TarefaCronograma.query.filter_by(obra_id=obra_id).count(),
            RDO.query.filter_by(obra_id=obra_id).count(),
            MedicaoContrato.query.filter_by(obra_id=obra_id).count())


# ── criação e atualização ─────────────────────────────────────────────
@pytest.mark.integration
def test_dia_novo_cria_rdo_preenchido():
    from services.atualizacao_rdos import atualizar_rdos
    from services.rdo_ciclo_vida import PREENCHIDO
    from models import RDO
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        rel = atualizar_rdos(obra, admin_id, _payload(), com_fotos=False,
                             mapa_mpp_nome=_MAPA)
        assert rel['criados'] == ['2026-07-14']
        assert rel['apontamentos'] == 1
        assert rel['pendencias'] == []

        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        assert rdo.data_relatorio == date(2026, 7, 14)
        # RDO importado nasce consolidado, não rascunho: rascunho faria a UI
        # oferecer "Submeter", e submeter lançaria custo em dobro.
        assert rdo.estado == PREENCHIDO
        assert rdo.status == 'Finalizado'
        assert rdo.numero_rdo == f'RDO-{obra.id}-20260714'


@pytest.mark.integration
def test_reexecucao_atualiza_sem_duplicar():
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO, RDOApontamentoCronograma
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        atualizar_rdos(obra, admin_id, _payload(pct=40), com_fotos=False,
                       mapa_mpp_nome=_MAPA)
        rel = atualizar_rdos(obra, admin_id, _payload(pct=70), com_fotos=False,
                             mapa_mpp_nome=_MAPA)

        assert rel['criados'] == []
        assert rel['atualizados'] == ['2026-07-14']
        assert RDO.query.filter_by(obra_id=obra.id).count() == 1
        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        aps = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).all()
        assert len(aps) == 1
        assert aps[0].percentual_realizado == pytest.approx(70.0)


@pytest.mark.integration
def test_nao_destrutivo_preserva_cronograma_e_dias_vizinhos():
    """O motivo de existir deste módulo. Se este teste cair, voltamos ao
    reimport destrutivo sem perceber."""
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        atualizar_rdos(obra, admin_id, _payload(data='2026-07-13', pct=30),
                       com_fotos=False, mapa_mpp_nome=_MAPA)
        antes = _contagens(obra.id)
        rdo_antigo = RDO.query.filter_by(obra_id=obra.id).one()
        id_antigo, comentario_antigo = rdo_antigo.id, rdo_antigo.comentario_geral

        atualizar_rdos(obra, admin_id, _payload(data='2026-07-14', pct=55),
                       com_fotos=False, mapa_mpp_nome=_MAPA)

        tarefas, rdos, medicoes = _contagens(obra.id)
        assert (tarefas, medicoes) == (antes[0], antes[2])
        assert rdos == antes[1] + 1
        sobrevivente = RDO.query.get(id_antigo)
        assert sobrevivente is not None
        assert sobrevivente.comentario_geral == comentario_antigo


@pytest.mark.integration
def test_rdo_imutavel_e_pulado_e_os_outros_dias_gravam():
    from services.atualizacao_rdos import atualizar_rdos
    from services.rdo_ciclo_vida import ASSINADO, transicionar
    from models import RDO
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        atualizar_rdos(obra, admin_id, _payload(data='2026-07-14', pct=40),
                       com_fotos=False, mapa_mpp_nome=_MAPA)
        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        # Pela máquina de estados, não no braço: `rdo.estado = ASSINADO` cria
        # assinatura SEM trilha, que é justamente o que
        # test_backfill_marcou_os_rdos_historicos_como_preenchido varre o banco
        # inteiro para proibir.
        transicionar(rdo, ASSINADO, detalhes={'origem': 'teste_atualizacao_rdos'})
        db.session.commit()

        rel = atualizar_rdos(
            obra, admin_id,
            _payload(data='2026-07-14', pct=90) + _payload(data='2026-07-15', pct=60),
            com_fotos=False, mapa_mpp_nome=_MAPA)

        assert [p['data'] for p in rel['pulados']] == ['2026-07-14']
        assert 'retificador' in rel['pulados'][0]['motivo']
        assert rel['criados'] == ['2026-07-15']          # o dia bom entrou
        assert RDO.query.get(rdo.id).estado == ASSINADO   # intocado


@pytest.mark.integration
def test_tarefa_nao_resolvida_vira_pendencia_nao_silencio():
    from services.atualizacao_rdos import atualizar_rdos
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        rel = atualizar_rdos(obra, admin_id, _payload(mpp=9999), com_fotos=False,
                             mapa_mpp_nome=_MAPA)
        assert rel['apontamentos'] == 0
        assert len(rel['pendencias']) == 1
        assert '9999' in rel['pendencias'][0]
        assert rel['criados'] == ['2026-07-14']   # o RDO em si foi criado


@pytest.mark.integration
def test_apontamento_sem_valor_vira_pendencia():
    from services.atualizacao_rdos import atualizar_rdos
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        rel = atualizar_rdos(
            obra, admin_id,
            [{'data': '2026-07-14', 'apontamentos': [{'tarefa_mpp': 59}]}],
            com_fotos=False, mapa_mpp_nome=_MAPA)
        assert rel['apontamentos'] == 0
        assert 'exatamente um' in rel['pendencias'][0]


@pytest.mark.integration
def test_retrocesso_sem_justificativa_vira_pendencia_com_mensagem_do_servico():
    from services.atualizacao_rdos import atualizar_rdos
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        atualizar_rdos(obra, admin_id, _payload(data='2026-07-14', pct=60),
                       com_fotos=False, mapa_mpp_nome=_MAPA)
        rel = atualizar_rdos(obra, admin_id, _payload(data='2026-07-15', pct=20),
                             com_fotos=False, mapa_mpp_nome=_MAPA)
        assert rel['apontamentos'] == 0
        assert 'menor que o anterior' in rel['pendencias'][0]


@pytest.mark.integration
def test_dry_run_nao_grava():
    """Tenant NOVO de propósito: `get_calendario` cria o calendário padrão e
    **comita** na primeira chamada, lá dentro de `registrar_apontamento`. Esse
    commit alheio levava junto o RDO pendente e o dry-run gravava."""
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO, RDOApontamentoCronograma
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        rel = atualizar_rdos(obra, admin_id, _payload(), com_fotos=False,
                             dry_run=True, mapa_mpp_nome=_MAPA)
        assert rel['criados'] == ['2026-07-14']
        assert rel['apontamentos'] == 1
        assert RDO.query.filter_by(obra_id=obra.id).count() == 0
        assert RDOApontamentoCronograma.query.filter_by(
            tarefa_cronograma_id=tarefas[59].id).count() == 0


@pytest.mark.integration
def test_dry_run_nao_processa_foto(tmp_path):
    """Foto em dry-run deixaria arquivo otimizado em disco, que o rollback
    não desfaz."""
    from PIL import Image
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDOFoto
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        pasta = tmp_path / '2026-07-14'
        pasta.mkdir(parents=True)
        Image.new('RGB', (20, 20), (5, 5, 5)).save(pasta / '1.jpg')
        rel = atualizar_rdos(
            obra, admin_id,
            _payload(fotos=[{'arquivo': '1.jpg', 'legenda': 'x'}]),
            base_fotos=str(tmp_path), dry_run=True, mapa_mpp_nome=_MAPA)
        assert rel['fotos'] == 0
        assert any('NÃO processadas' in a for a in rel['avisos'])
        assert RDOFoto.query.filter_by(admin_id=admin_id).count() == 0


@pytest.mark.integration
def test_percentual_sincroniza_na_tarefa():
    from services.atualizacao_rdos import atualizar_rdos
    from models import TarefaCronograma
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        tid = tarefas[59].id
        atualizar_rdos(obra, admin_id, _payload(pct=65), com_fotos=False,
                       mapa_mpp_nome=_MAPA)
        assert TarefaCronograma.query.get(tid).percentual_concluido == \
            pytest.approx(65.0)


@pytest.mark.integration
def test_fallback_por_nome_desambigua_pelo_avo():
    """Obra sem `mpp_uid` (nasceu do import JSON): a resolução cai no nome. As
    duas candidatas têm o mesmo nome E o mesmo pai — quem separa é o avô."""
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDOApontamentoCronograma, RDO
    with app.app_context():
        admin_id, obra, tarefas = _ambiente(com_mpp_uid=False)
        rel = atualizar_rdos(obra, admin_id, _payload(mpp=59, pct=45),
                             com_fotos=False, mapa_mpp_nome=_MAPA)
        assert rel['pendencias'] == []
        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        ap = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).one()
        assert ap.tarefa_cronograma_id == tarefas[59].id   # Galpão A, não B


@pytest.mark.integration
def test_ignora_a_copia_do_cronograma_do_cliente():
    """O cronograma do CLIENTE é uma cópia com os mesmos nomes e não recebe
    sync (`sincronizar_percentuais_obra` roda com cliente=False). Se ele
    entrasse no índice, a resolução por nome empataria — e no pior caso o
    apontamento iria para a cópia onde o físico nunca se move."""
    from services.atualizacao_rdos import IndiceTarefas, atualizar_rdos
    from models import RDOApontamentoCronograma, RDO, TarefaCronograma
    with app.app_context():
        admin_id, obra, tarefas = _ambiente(com_mpp_uid=False)
        alvo = tarefas[59]
        # cópia-cliente idêntica em nome, pai e mpp_uid
        clone = TarefaCronograma(
            obra_id=obra.id, admin_id=admin_id,
            tarefa_pai_id=alvo.tarefa_pai_id,
            nome_tarefa=alvo.nome_tarefa, ordem=alvo.ordem + 500,
            duracao_dias=alvo.duracao_dias, data_inicio=alvo.data_inicio,
            data_fim=alvo.data_fim, is_cliente=True)
        db.session.add(clone)
        db.session.commit()

        assert clone.id not in IndiceTarefas(obra.id, _MAPA)._por_id
        rel = atualizar_rdos(obra, admin_id, _payload(mpp=59, pct=45),
                             com_fotos=False, mapa_mpp_nome=_MAPA)
        assert rel['pendencias'] == []
        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        ap = RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).one()
        assert ap.tarefa_cronograma_id == alvo.id
        assert TarefaCronograma.query.get(clone.id).percentual_concluido == 0.0


def test_parser_ordena_pasta_existente_por_numero_e_nao_por_tamanho(tmp_path):
    """Com extensões misturadas, ordenar por (len, nome) põe `2.jpg` antes de
    `1.jpeg` e as legendas grudam nas fotos erradas."""
    base = tmp_path / 'fotos'
    (base / '2026-07-07').mkdir(parents=True)
    for nome in ('1.jpeg', '2.jpg', '10.jpg'):
        (base / '2026-07-07' / nome).write_bytes(b'x')
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, _ = _converter(txt=str(txt), base_fotos=str(base))
    assert [f['arquivo'] for f in payload['rdos'][0]['fotos']] == \
        ['1.jpeg', '2.jpg', '10.jpg']
    # a 1ª legenda do chat tem de ficar no 1.jpeg
    assert payload['rdos'][0]['fotos'][0]['legenda'] == 'Limpeza nas valas'


def test_parser_recusa_export_em_formato_desconhecido(tmp_path):
    """Export em locale US não casa o cabeçalho. Devolver 0 dias em silêncio
    pareceria "não teve RDO" em vez de "não entendi o arquivo"."""
    import pytest as _pytest
    txt = tmp_path / 'conversa.txt'
    txt.write_text('7/8/26, 8:59 AM - Alan: Obra Itu - RDO – 07/07/2026\n',
                   encoding='utf-8')
    with _pytest.raises(ValueError, match='Nenhuma mensagem reconhecida'):
        _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'))


@pytest.mark.integration
def test_fallback_ambiguo_sem_caminho_vira_pendencia_listando_candidatos():
    from services.atualizacao_rdos import atualizar_rdos
    with app.app_context():
        admin_id, obra, _ = _ambiente(com_mpp_uid=False)
        mapa = {59: {'nome': 'Execução de Ferragens Para Fundação',
                     'pai': None, 'caminho': []}}
        rel = atualizar_rdos(obra, admin_id, _payload(mpp=59), com_fotos=False,
                             mapa_mpp_nome=mapa)
        assert rel['apontamentos'] == 0
        assert 'Galpão A' in rel['pendencias'][0]
        assert 'Galpão B' in rel['pendencias'][0]


@pytest.mark.integration
def test_fotos_nao_duplicam_na_segunda_rodada(tmp_path):
    from PIL import Image
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO, RDOFoto
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        pasta = tmp_path / '2026-07-14'
        pasta.mkdir(parents=True)
        for n in (1, 2):
            Image.new('RGB', (40, 30), (10 * n, 20, 30)).save(pasta / f'{n}.jpg')

        item = _payload(fotos=[{'arquivo': '1.jpg', 'legenda': 'armação'},
                               {'arquivo': '2.jpg', 'legenda': 'concretagem'}])
        rel = atualizar_rdos(obra, admin_id, item, base_fotos=str(tmp_path),
                             mapa_mpp_nome=_MAPA)
        assert rel['fotos'] == 2
        rdo = RDO.query.filter_by(obra_id=obra.id).one()
        assert RDOFoto.query.filter_by(rdo_id=rdo.id).count() == 2
        assert {f.legenda for f in RDOFoto.query.filter_by(rdo_id=rdo.id)} == \
            {'armação', 'concretagem'}

        rel2 = atualizar_rdos(obra, admin_id, item, base_fotos=str(tmp_path),
                              mapa_mpp_nome=_MAPA)
        assert rel2['fotos'] == 0
        assert RDOFoto.query.filter_by(rdo_id=rdo.id).count() == 2
        assert any('álbum preservado' in a for a in rel2['avisos'])


@pytest.mark.integration
def test_percentual_livre_ligado_aceita_pct_em_tarefa_quantitativa():
    """Com a flag da migração 226 ligada todo apontamento é percentual —
    inclusive em tarefa com quantitativo cadastrado."""
    from services.atualizacao_rdos import atualizar_rdos
    from models import ConfiguracaoEmpresa
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        t = tarefas[59]
        t.quantidade_total, t.unidade_medida = 48, 'un'
        t.modo_apontamento = 'quantidade'
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        if cfg is None:
            cfg = ConfiguracaoEmpresa(admin_id=admin_id,
                                      nome_empresa=f'Veks {admin_id}')
            db.session.add(cfg)
        cfg.rdo_percentual_livre = True
        db.session.commit()

        rel = atualizar_rdos(obra, admin_id, _payload(pct=62), com_fotos=False,
                             mapa_mpp_nome=_MAPA)
        assert rel['pendencias'] == []
        assert rel['apontamentos'] == 1


# ── parser do WhatsApp (sem banco) ────────────────────────────────────
_CONVERSA = """06/05/2026 09:43 - As mensagens são protegidas com criptografia.
08/07/2026 08:59 - Eng. Alan Santos: Obra Itu - RDO – 07/07/2026

Efetivo: 05 colaboradores

Atividades Executadas
• Foi executada a armação de 11 vigas transversais do Galpão B.

Observações
• Vistoria técnica sem restrições.

Próximas Atividades Previstas (08/07)
• Concretagem das brocas.
08/07/2026 09:00 - Eng. Alan Santos: ‎VID-20260708-WA0010.mp4 (arquivo anexado)
08/07/2026 09:00 - Eng. Alan Santos: ‎IMG-20260708-WA0007.jpg (arquivo anexado)
Limpeza nas valas
08/07/2026 09:01 - Eng. Alan Santos: ‎IMG-20260708-WA0008.jpg (arquivo anexado)
Espaçadores nas brocas
09/07/2026 09:17 - Abel: *Obra a Angela - RDO 08/07/2026*

Efetivo: 03 colaboradores

Atividades
• Alvenaria do pavimento térreo.
09/07/2026 09:20 - Abel: ‎IMG-20260709-WA0007.jpg (arquivo anexado)
Alvenaria
22/07/2026 20:11 - Eng. Alan Santos: RDO – 22/07/2026

Efetivo: 06 colaboradores

Atividades Executadas
• Foi executada a compactação do solo das calçadas do Galpão B.
"""


def _converter(**kw):
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../scripts'))
    from whatsapp_para_rdos import converter
    return converter(caminho_txt=kw.pop('txt'), marcador_obra='Obra Itu',
                     marcadores_conhecidos=['Obra a Angela'],
                     dry_run=True, **kw)


def test_parser_data_o_rdo_pelo_texto_nao_pela_mensagem(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, meta = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'))
    datas = [i['data'] for i in payload['rdos']]
    # a mensagem é de 08/07; o RDO é o de 07/07. Datar pela mensagem
    # deslocaria a série inteira em um dia.
    assert datas == ['2026-07-07', '2026-07-22']


def test_parser_nao_deixa_vazar_rdo_de_outra_obra(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'))
    junto = ' '.join(i['comentario'] for i in payload['rdos'])
    assert 'Alvenaria' not in junto


def test_parser_legenda_gruda_no_anexo_certo_e_video_e_ignorado(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, meta = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'))
    dia = payload['rdos'][0]
    assert [f['legenda'] for f in dia['fotos']] == ['Limpeza nas valas',
                                                    'Espaçadores nas brocas']
    assert [f['arquivo'] for f in dia['fotos']] == ['1.jpg', '2.jpg']
    assert any('.mp4' in a for a in meta['avisos'])


def test_parser_normaliza_titulos_e_mantem_texto_verbatim(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'))
    comentario = payload['rdos'][0]['comentario']
    assert comentario.startswith('Efetivo: 05 colaboradores')
    assert 'Atividades executadas:' in comentario
    assert 'Observações:' in comentario
    assert 'Próximas atividades (08/07):' in comentario
    assert 'armação de 11 vigas transversais do Galpão B' in comentario
    # efetivo fica só no texto — mão de obra com funcionário arbitrário do
    # cadastro atribuiria nome errado a um dia real
    assert payload['rdos'][0]['mao_de_obra'] == 0


def test_parser_bloco_sem_marcador_herda_a_obra_com_aviso(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, meta = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'))
    assert '2026-07-22' in [i['data'] for i in payload['rdos']]
    assert any('sem marcador de obra' in a for a in meta['avisos'])


def test_parser_filtra_por_periodo(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'),
                            desde=date(2026, 7, 10))
    assert [i['data'] for i in payload['rdos']] == ['2026-07-22']


def test_parser_sugere_apontamento_pela_regra_e_aponta_pendencia(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    regras = {'regras': [{'id': 'ferragem-b', 'quando': ['armação', 'vigas'],
                          'galpao': 'B', 'tarefa_mpp': 59,
                          'tarefa_nome': 'Ferragens (Galpão B)',
                          'forma': 'pct', 'pct': 40}]}
    payload, meta = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'),
                               regras=regras)
    dia = payload['rdos'][0]
    assert dia['apontamentos'] == []          # sugestão não vira apontamento
    assert dia['_sugestoes'][0]['tarefa_mpp'] == 59
    assert dia['_sugestoes'][0]['pct'] == 40
    # o bullet do dia 22/07 não casa nenhuma regra e precisa aparecer
    assert any('bullet sem regra' in p for p in meta['pendencias'])


def test_parser_promove_sugestao_com_flag(tmp_path):
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    regras = {'regras': [{'id': 'ferragem-b', 'quando': ['armação', 'vigas'],
                          'galpao': 'B', 'tarefa_mpp': 59, 'forma': 'pct',
                          'pct': 40}]}
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'),
                            regras=regras, aplicar_sugestoes=True)
    assert payload['rdos'][0]['apontamentos'] == [{'tarefa_mpp': 59, 'pct': 40}]


def test_parser_fracao_vira_percentual(tmp_path):
    conversa = _CONVERSA.replace(
        '• Foi executada a armação de 11 vigas transversais do Galpão B.',
        '• Foi executada a armação de 37,50 m da primeira viga longitudinal '
        'do Galpão B, de um total de 57,50 m previstos para esta etapa.')
    txt = tmp_path / 'conversa.txt'
    txt.write_text(conversa, encoding='utf-8')
    regras = {'regras': [{'id': 'viga-long-b', 'quando': ['armação', 'viga'],
                          'galpao': 'B', 'tarefa_mpp': 59, 'forma': 'fracao'}]}
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'),
                            regras=regras)
    assert payload['rdos'][0]['_sugestoes'][0]['pct'] == pytest.approx(65.2, abs=0.1)


def test_parser_regra_de_galpao_vale_para_os_dois_quando_o_bullet_cita_ambos(tmp_path):
    """"…das brocas dos Galpões A e B" é UM bullet que vale para DUAS tarefas.
    Tratar "dois galpões" como "nenhum galpão" perdia a concretagem inteira."""
    conversa = _CONVERSA.replace(
        '• Foi executada a armação de 11 vigas transversais do Galpão B.',
        '• Foi realizada a concretagem de todas as brocas dos Galpões A e B.')
    txt = tmp_path / 'conversa.txt'
    txt.write_text(conversa, encoding='utf-8')
    regras = {'regras': [
        {'id': 'brocas-b', 'quando': ['concretagem', 'brocas'], 'galpao': 'B',
         'tarefa_mpp': 15, 'forma': 'marco'},
        {'id': 'brocas-a', 'quando': ['concretagem', 'brocas'], 'galpao': 'A',
         'tarefa_mpp': 60, 'forma': 'marco'}]}
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'),
                            regras=regras)
    sug = payload['rdos'][0]['_sugestoes']
    assert {s['tarefa_mpp'] for s in sug} == {15, 60}
    assert all(s['pct'] == 100 for s in sug)   # "todas as brocas"


def test_parser_nao_quando_derruba_regra_de_bullet_de_preparacao(tmp_path):
    """"limpeza das valas … para a execução da camada de concreto magro" é
    preparação: casaria a regra do magro e apontaria serviço não iniciado."""
    conversa = _CONVERSA.replace(
        '• Foi executada a armação de 11 vigas transversais do Galpão B.',
        '• Foi realizada a limpeza das valas das vigas baldrame do Galpão B, '
        'preparando a frente de serviço para a execução da camada de concreto magro.')
    txt = tmp_path / 'conversa.txt'
    txt.write_text(conversa, encoding='utf-8')
    base = {'id': 'magro-b', 'quando': ['concreto magro'], 'galpao': 'B',
            'tarefa_mpp': 16, 'forma': 'marco', 'pct_parcial': 60}
    sem_guarda, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'f1'),
                               regras={'regras': [base]})
    assert sem_guarda['rdos'][0]['_sugestoes'][0]['tarefa_mpp'] == 16

    com_guarda, _ = _converter(
        txt=str(txt), base_fotos=str(tmp_path / 'f2'),
        regras={'regras': [dict(base, nao_quando=['limpeza das valas'])]})
    assert com_guarda['rdos'][0].get('_sugestoes') is None


def test_regras_da_baia_sao_json_valido_e_consistentes():
    """O arquivo de regras é editado à mão pelo Cássio — um typo de campo
    silenciaria a regra em vez de quebrar."""
    import json
    caminho = os.path.join(os.path.dirname(__file__), '..', 'docs', 'rdo',
                           'regras_apontamento_baia.json')
    with open(caminho, encoding='utf-8') as fh:
        regras = json.load(fh)
    assert regras['regras']
    for r in regras['regras']:
        assert r['id'] and r['quando'] and isinstance(r['tarefa_mpp'], int)
        assert r['forma'] in ('pct', 'fracao', 'marco')
        assert (r.get('galpao') or 'A') in ('A', 'B')
    ids = [r['id'] for r in regras['regras']]
    assert len(ids) == len(set(ids))


def test_parser_ignora_proximas_atividades_na_sugestao(tmp_path):
    """'Próximas Atividades' é plano, não execução — apontar por ela
    adiantaria o físico da obra."""
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    regras = {'regras': [{'id': 'brocas', 'quando': ['concretagem das brocas'],
                          'tarefa_mpp': 60, 'forma': 'pct', 'pct': 100}]}
    payload, _ = _converter(txt=str(txt), base_fotos=str(tmp_path / 'fotos'),
                            regras=regras)
    assert payload['rdos'][0].get('_sugestoes') is None


def test_parser_preserva_pasta_de_foto_ja_preenchida(tmp_path):
    base = tmp_path / 'fotos'
    (base / '2026-07-07').mkdir(parents=True)
    (base / '2026-07-07' / '1.jpg').write_bytes(b'ja-estava-aqui')
    txt = tmp_path / 'conversa.txt'
    txt.write_text(_CONVERSA, encoding='utf-8')
    payload, meta = _converter(txt=str(txt), base_fotos=str(base))
    assert (base / '2026-07-07' / '1.jpg').read_bytes() == b'ja-estava-aqui'
    assert len(payload['rdos'][0]['fotos']) == 1
    assert any('use --forcar' in a for a in meta['avisos'])


# ── mapa de nomes a partir do JSON canônico ───────────────────────────
def test_mapa_nomes_deriva_o_pai_pelo_nivel():
    from services.atualizacao_rdos import mapa_nomes_do_json
    mapa = mapa_nomes_do_json({'cronograma_tarefas': [
        {'id': 10, 'nivel': 1, 'nome': 'BAIAS'},
        {'id': 11, 'nivel': 2, 'nome': 'Galpão A'},
        {'id': 14, 'nivel': 3, 'nome': 'Ferragens'},
        {'id': 12, 'nivel': 2, 'nome': 'Galpão B'},
        {'id': 59, 'nivel': 3, 'nome': 'Ferragens'},
    ]})
    assert mapa[14]['pai'] == 'Galpão A'
    assert mapa[59]['pai'] == 'Galpão B'
    assert mapa[14]['caminho'] == ['BAIAS', 'Galpão A']
    assert mapa[11]['pai'] == 'BAIAS'
    assert mapa[10]['caminho'] == []


def test_mapa_nomes_do_json_real_separa_os_dois_galpoes():
    """No cronograma real o pai imediato das duas é o MESMO ("Fundação") — o
    que separa é o avô. Se o mapa guardasse só o pai, o fallback por nome
    apontaria o galpão errado."""
    import json
    from services.atualizacao_rdos import mapa_nomes_do_json
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as fh:
        mapa = mapa_nomes_do_json(json.load(fh))
    assert mapa[14]['nome'] == 'Execução de Ferragens Para Fundação'
    assert mapa[59]['nome'] == 'Execução de Ferragens Para Fundação'
    assert mapa[14]['pai'] == mapa[59]['pai'] == 'Fundação'
    # 14 é do Galpão B e 59 é do Galpão A — sim, nesta ordem.
    assert 'Galpão B' in mapa[14]['caminho']
    assert 'Galpão A' in mapa[59]['caminho']


# ── garantia de que o import destrutivo continua intacto ──────────────
@pytest.mark.integration
def test_helper_de_fotos_compartilhado_respeita_a_base_do_importador(tmp_path):
    """A extração de `_materializar_fotos_rdo` para o módulo compartilhado não
    pode quebrar o `ff.FOTOS_RDO_BASE` que os testes do importador trocam."""
    from PIL import Image
    from services import importacao_fisico_financeiro as ff
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO, RDOFoto
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        pasta = tmp_path / '2026-07-14'
        pasta.mkdir(parents=True)
        Image.new('RGB', (30, 20), (1, 2, 3)).save(pasta / '1.jpg')
        atualizar_rdos(obra, admin_id, _payload(), com_fotos=False,
                       mapa_mpp_nome=_MAPA)
        rdo = RDO.query.filter_by(obra_id=obra.id).one()

        original = ff.FOTOS_RDO_BASE
        ff.FOTOS_RDO_BASE = str(tmp_path)
        try:
            criadas = ff._materializar_fotos_rdo(
                rdo, admin_id, date(2026, 7, 14), [{'arquivo': '1.jpg',
                                                    'legenda': 'x'}])
        finally:
            ff.FOTOS_RDO_BASE = original
        assert criadas == 1
        assert RDOFoto.query.filter_by(rdo_id=rdo.id).count() == 1


@pytest.mark.integration
def test_datas_fora_de_ordem_no_payload_entram_em_ordem_cronologica():
    """O acumulado depende da ordem: payload embaralhado não pode virar
    retrocesso falso."""
    from services.atualizacao_rdos import atualizar_rdos
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        fora_de_ordem = (_payload(data='2026-07-16', pct=80)
                         + _payload(data='2026-07-14', pct=30)
                         + _payload(data='2026-07-15', pct=55))
        rel = atualizar_rdos(obra, admin_id, fora_de_ordem, com_fotos=False,
                             mapa_mpp_nome=_MAPA)
        assert rel['pendencias'] == []
        assert rel['criados'] == ['2026-07-14', '2026-07-15', '2026-07-16']


@pytest.mark.integration
def test_dia_sem_comentario_nao_apaga_o_texto_existente():
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        atualizar_rdos(obra, admin_id, _payload(), com_fotos=False,
                       mapa_mpp_nome=_MAPA)
        texto = RDO.query.filter_by(obra_id=obra.id).one().comentario_geral
        atualizar_rdos(obra, admin_id,
                       [{'data': '2026-07-14', 'apontamentos': []}],
                       com_fotos=False, mapa_mpp_nome=_MAPA)
        assert RDO.query.filter_by(obra_id=obra.id).one().comentario_geral == texto


@pytest.mark.integration
def test_quantidade_acumula_entre_dias():
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDOApontamentoCronograma, TarefaCronograma
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        t = tarefas[59]
        t.quantidade_total, t.unidade_medida = 48, 'un'
        db.session.commit()
        tid = t.id

        dias = [
            {'data': '2026-07-14', 'apontamentos': [{'tarefa_mpp': 59,
                                                     'quantidade': 10}]},
            {'data': '2026-07-15', 'apontamentos': [{'tarefa_mpp': 59,
                                                     'quantidade': 14}]},
        ]
        rel = atualizar_rdos(obra, admin_id, dias, com_fotos=False,
                             mapa_mpp_nome=_MAPA)
        assert rel['pendencias'] == []
        acum = (RDOApontamentoCronograma.query
                .filter_by(tarefa_cronograma_id=tid)
                .order_by(RDOApontamentoCronograma.id.desc()).first())
        assert acum.quantidade_acumulada == pytest.approx(24.0)
        assert TarefaCronograma.query.get(tid).percentual_concluido == \
            pytest.approx(50.0)


@pytest.mark.integration
def test_relatorio_formatado_lista_pendencias():
    from services.atualizacao_rdos import atualizar_rdos, formatar_relatorio
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        rel = atualizar_rdos(obra, admin_id, _payload(mpp=9999), com_fotos=False,
                             mapa_mpp_nome=_MAPA)
        texto = formatar_relatorio(rel, obra)
        assert 'PENDÊNCIAS' in texto
        assert '9999' in texto


@pytest.mark.integration
def test_rdo_de_outra_obra_na_mesma_data_nao_e_tocado():
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDO
    with app.app_context():
        admin_id, obra, _ = _ambiente()
        outra_admin, outra_obra, _ = _ambiente()
        atualizar_rdos(outra_obra, outra_admin, _payload(data='2026-07-14'),
                       com_fotos=False, mapa_mpp_nome=_MAPA)
        antes = RDO.query.filter_by(obra_id=outra_obra.id).one()
        antes_texto, antes_id = antes.comentario_geral, antes.id

        atualizar_rdos(obra, admin_id,
                       [{'data': '2026-07-14', 'comentario': 'outro texto',
                         'apontamentos': []}],
                       com_fotos=False, mapa_mpp_nome=_MAPA)

        depois = RDO.query.get(antes_id)
        assert depois.comentario_geral == antes_texto
        assert RDO.query.filter_by(obra_id=outra_obra.id).count() == 1


@pytest.mark.integration
def test_dia_futuro_nao_e_recusado_mas_o_planejado_fica_coerente():
    """RDO datado à frente do cronograma continua entrando (o diário manda),
    e o `percentual_planejado` do apontamento acompanha a data."""
    from services.atualizacao_rdos import atualizar_rdos
    from models import RDOApontamentoCronograma
    with app.app_context():
        admin_id, obra, tarefas = _ambiente()
        futuro = (date.today() + timedelta(days=1)).isoformat()
        rel = atualizar_rdos(obra, admin_id, _payload(data=futuro, pct=10),
                             com_fotos=False, mapa_mpp_nome=_MAPA)
        assert rel['criados'] == [futuro]
        ap = RDOApontamentoCronograma.query.filter_by(
            tarefa_cronograma_id=tarefas[59].id).one()
        assert ap.percentual_realizado == pytest.approx(10.0)
