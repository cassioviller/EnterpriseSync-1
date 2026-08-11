"""O percentual do portal do cliente é o mesmo do RDO/cronograma interno.

Critério global 11 — "cronograma, RDO, detalhes e portal exibem o mesmo
percentual". O portal é o único dos quatro que não lê o percentual da própria
tarefa: a cópia-cliente (`is_cliente=True`) é uma FOTO tirada por
`gerar_cronograma_cliente` (views/obras.py:3196) e nunca mais recebe sync de
RDO, então `portal_obra` reflete o percentual da tarefa INTERNA correspondente.

O "correspondente" era `nome_tarefa` puro, num dict — e nome de tarefa não é
único. Numa EAP por pavimento cada atividade existe uma vez por andar, então o
dict guardava só a ÚLTIMA de cada nome e todo andar exibia o percentual do
último. Obra da Angela (carga de 11/08): 53 das 159 tarefas em colisão de nome
("Térreo" 6×, "1° Andar" 5×). O portal mostrava 100/100/100/70 nos DOIS andares
enquanto o RDO do Térreo dizia 5/5/90/95, e o pai "1° Andar" exibia 0% logo
acima de quatro filhas em 100%.

A EAP montada aqui é a daquela obra, reduzida aos dois pavimentos.
"""
import os
import secrets
import sys
import uuid
from datetime import date

import pytest
from flask import template_rendered
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario

pytestmark = pytest.mark.integration

# Atividades de fechamento, na ordem do .mpp. O nome se repete pavimento a
# pavimento — é exatamente essa repetição que o índice por nome não resolvia.
ATIVIDADES = [
    'Instalação de lã entre as placas',
    'Execução de plaqueamento interno',
    'Aplicação de massa na parte interna, juntas e parafusos',
    'Execução de forro de gesso acartonado',
]
# Percentuais VIGENTES no cronograma interno (o que o RDO mostra).
PCT_TERREO = [5.0, 5.0, 90.0, 95.0]
PCT_1_ANDAR = [100.0, 100.0, 100.0, 70.0]
ROLLUP_TERREO = 48.75
ROLLUP_1_ANDAR = 92.5
# Os MESMOS pavimentos existem sob o outro serviço, mais adiante na ordem — é
# o que fazia o dict por nome guardar ESTES valores para "Térreo"/"1° Andar".
# 39.7 e 0.0 são os números que o portal da Angela exibia nos dois pais.
ROLLUP_ELETRICA_TERREO = 39.7
ROLLUP_ELETRICA_1_ANDAR = 0.0


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-portal-cronograma-pct'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'pcp_{suf}', email=f'pcp_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True, portal_ativo=True,
             token_cliente=secrets.token_urlsafe(32))
    db.session.add(o)
    db.session.commit()
    return o


def _tarefa(obra, nome, ordem, *, pai=None, pct=0.0, cliente=False):
    t = TarefaCronograma(
        obra_id=obra.id, admin_id=obra.admin_id, nome_tarefa=nome,
        ordem=ordem, duracao_dias=10, percentual_concluido=pct,
        responsavel='empresa', is_cliente=cliente, ativa=True,
        tarefa_pai_id=(pai.id if pai else None),
        data_inicio=date(2026, 5, 5), data_fim=date(2026, 7, 31))
    db.session.add(t)
    db.session.commit()
    return t


def _montar_eap(obra, *, cliente, pct_terreo, pct_1_andar,
                pct_pai_terreo, pct_pai_1_andar,
                pct_eletrica_terreo, pct_eletrica_1_andar):
    """A EAP da obra real, reduzida a dois serviços e dois pavimentos:

        OBRA
        ├── Fechamento de Paredes Internas
        │   ├── Térreo    › 4 atividades homônimas
        │   └── 1° Andar  › as MESMAS 4 atividades
        └── Instalações Elétricas
            ├── Térreo    › atividades próprias
            └── 1° Andar  › atividades próprias

    Os dois serviços repetem os nomes dos pavimentos — por isso o pai também
    colidia, não só a folha. A elétrica vem depois na ordem de propósito: era
    o percentual DELA que vazava para os pavimentos do fechamento.
    """
    o = [0]

    def prox():
        o[0] += 1
        return o[0]

    raiz = _tarefa(obra, obra.nome, prox(), cliente=cliente)

    fech = _tarefa(obra, 'Fechamento de Paredes Internas', prox(),
                   pai=raiz, cliente=cliente)
    terreo = _tarefa(obra, 'Térreo', prox(), pai=fech, pct=pct_pai_terreo,
                     cliente=cliente)
    for nome, pct in zip(ATIVIDADES, pct_terreo):
        _tarefa(obra, nome, prox(), pai=terreo, pct=pct, cliente=cliente)
    andar = _tarefa(obra, '1° Andar', prox(), pai=fech, pct=pct_pai_1_andar,
                    cliente=cliente)
    for nome, pct in zip(ATIVIDADES, pct_1_andar):
        _tarefa(obra, nome, prox(), pai=andar, pct=pct, cliente=cliente)

    eletrica = _tarefa(obra, 'Instalações Elétricas', prox(), pai=raiz,
                       cliente=cliente)
    e_terreo = _tarefa(obra, 'Térreo', prox(), pai=eletrica,
                       pct=pct_eletrica_terreo, cliente=cliente)
    _tarefa(obra, 'Infra - conduíte, fixadores e caixinhas teto', prox(),
            pai=e_terreo, pct=pct_eletrica_terreo, cliente=cliente)
    e_andar = _tarefa(obra, '1° Andar', prox(), pai=eletrica,
                      pct=pct_eletrica_1_andar, cliente=cliente)
    _tarefa(obra, 'Acabamento e luminarias', prox(), pai=e_andar,
            pct=pct_eletrica_1_andar, cliente=cliente)
    return raiz


def _cenario():
    """Interno com os percentuais vigentes + cópia-cliente CONGELADA em 0.

    A cópia zerada é o caso real: a carga de 11/08 regenerou o cronograma do
    cliente e, desde então, nenhum RDO tocou nela.
    """
    admin = _admin()
    obra = _obra(admin.id)
    _montar_eap(obra, cliente=False, pct_terreo=PCT_TERREO,
                pct_1_andar=PCT_1_ANDAR, pct_pai_terreo=ROLLUP_TERREO,
                pct_pai_1_andar=ROLLUP_1_ANDAR,
                pct_eletrica_terreo=ROLLUP_ELETRICA_TERREO,
                pct_eletrica_1_andar=ROLLUP_ELETRICA_1_ANDAR)
    _montar_eap(obra, cliente=True, pct_terreo=[0.0] * 4,
                pct_1_andar=[0.0] * 4, pct_pai_terreo=0.0,
                pct_pai_1_andar=0.0, pct_eletrica_terreo=0.0,
                pct_eletrica_1_andar=0.0)
    return obra


def _arvore_do_portal(obra):
    """`cronograma_cliente_tree` como o template a recebe."""
    capturado = {}

    def _registrar(sender, template, context, **extra):
        if 'cronograma_cliente_tree' in context:
            capturado['tree'] = context['cronograma_cliente_tree']

    template_rendered.connect(_registrar, app)
    try:
        resp = app.test_client().get(f'/portal/obra/{obra.token_cliente}')
        assert resp.status_code == 200, resp.status_code
    finally:
        template_rendered.disconnect(_registrar, app)
    assert 'tree' in capturado, 'portal não expôs cronograma_cliente_tree'
    return capturado['tree']


def _por_nome(nos):
    return {n.nome_tarefa: n for n in nos}


def _pavimentos(tree, servico='Fechamento de Paredes Internas'):
    assert len(tree) == 1, f'esperava uma raiz, veio {len(tree)}'
    filhos = _por_nome(_por_nome(tree[0].filhos)[servico].filhos)
    return filhos['Térreo'], filhos['1° Andar']


def test_folha_homonima_leva_o_percentual_do_proprio_pavimento():
    """A colisão de nome: cada andar exibe o SEU percentual, não o do último.

    Antes, as quatro folhas do Térreo exibiam 100/100/100/70 — os valores do
    1° Andar, que vinha depois na ordem e sobrescrevia as chaves do dict.
    """
    with app.app_context():
        obra = _cenario()
        terreo, andar = _pavimentos(_arvore_do_portal(obra))

        assert [_por_nome(terreo.filhos)[n].percentual_apresentacao
                for n in ATIVIDADES] == PCT_TERREO
        assert [_por_nome(andar.filhos)[n].percentual_apresentacao
                for n in ATIVIDADES] == PCT_1_ANDAR


def test_pavimentos_homonimos_nao_exibem_o_mesmo_numero():
    """Guarda direta contra o sintoma: os dois andares mostravam a MESMA
    lista de percentuais, o que na tela lia-se como obra uniforme."""
    with app.app_context():
        obra = _cenario()
        terreo, andar = _pavimentos(_arvore_do_portal(obra))
        assert ([f.percentual_apresentacao for f in terreo.filhos]
                != [f.percentual_apresentacao for f in andar.filhos])


def test_pai_nao_fica_zerado_acima_de_filhas_concluidas():
    """"1° Andar" aparecia com 0% acima de quatro filhas em 100%, e "Térreo"
    com 39.7% acima de filhas em 5%: o nome do pavimento colide entre serviços
    (6× e 5× na obra da Angela), então os dois pais exibiam o rollup do MESMO
    pavimento da elétrica. Cada pai leva agora o rollup do seu próprio."""
    with app.app_context():
        obra = _cenario()
        tree = _arvore_do_portal(obra)
        terreo, andar = _pavimentos(tree)
        assert (terreo.percentual_apresentacao,
                andar.percentual_apresentacao) == (ROLLUP_TERREO,
                                                   ROLLUP_1_ANDAR)

        # E o serviço que emprestava os números continua com os seus.
        e_terreo, e_andar = _pavimentos(tree, 'Instalações Elétricas')
        assert (e_terreo.percentual_apresentacao,
                e_andar.percentual_apresentacao) == (ROLLUP_ELETRICA_TERREO,
                                                     ROLLUP_ELETRICA_1_ANDAR)


def test_nome_unico_ainda_casa_quando_a_eap_do_cliente_e_antiga():
    """Fallback por nome: cópia-cliente tirada ANTES de uma carga que remexeu
    a EAP tem caminho que não casa mais. Enquanto o nome for único no
    cronograma interno, ele ainda identifica a tarefa — e o portal mostra o
    percentual vivo em vez do congelado."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        raiz = _tarefa(obra, obra.nome, 1)
        grupo = _tarefa(obra, 'Cobertura', 2, pai=raiz)
        _tarefa(obra, 'Impermeabilização da laje', 3, pai=grupo, pct=64.0)

        # Cópia-cliente com OUTRA hierarquia (o grupo intermediário mudou de
        # nome na carga nova): o caminho diverge, o nome não.
        craiz = _tarefa(obra, obra.nome, 1, cliente=True)
        cgrupo = _tarefa(obra, 'Serviços de Cobertura', 2, pai=craiz,
                         cliente=True)
        _tarefa(obra, 'Impermeabilização da laje', 3, pai=cgrupo, pct=0.0,
                cliente=True)

        tree = _arvore_do_portal(obra)
        folha = tree[0].filhos[0].filhos[0]
        assert folha.percentual_apresentacao == 64.0


def test_nome_ambiguo_sem_caminho_mantem_o_congelado():
    """O oposto do teste acima: se o caminho não casa E o nome é ambíguo,
    exibir o percentual de um irmão sorteado é pior que exibir o valor
    congelado — parece certo. Mantém o próprio percentual."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        raiz = _tarefa(obra, obra.nome, 1)
        a = _tarefa(obra, 'Bloco A', 2, pai=raiz)
        b = _tarefa(obra, 'Bloco B', 3, pai=raiz)
        _tarefa(obra, 'Pintura', 4, pai=a, pct=10.0)
        _tarefa(obra, 'Pintura', 5, pai=b, pct=90.0)

        craiz = _tarefa(obra, obra.nome, 1, cliente=True)
        cbloco = _tarefa(obra, 'Bloco Único', 2, pai=craiz, cliente=True)
        _tarefa(obra, 'Pintura', 3, pai=cbloco, pct=33.0, cliente=True)

        tree = _arvore_do_portal(obra)
        folha = tree[0].filhos[0].filhos[0]
        assert folha.percentual_apresentacao == 33.0
