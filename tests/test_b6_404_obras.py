"""B6.7 — lote d: `views/obras.py`, a família A com o censo medido na frente.

**Estado medido em 01/09: a Task B6.7 nunca foi executada.** O plano
`docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md:703-715` manda trocar
os ramos `if not obra` por `abort(404)` e pôr `except HTTPException: raise` nos
excepts largos. 🔬 `grep -c 'except HTTPException' views/obras.py` = **1**, e o
único é o de `:2268`, que veio de outra onda.

## O censo do Step 0, e o que ele derrubou

O plano previa "11+ handlers, 13+ sítios" a partir de um scanner AST, e avisava
que o número era **piso**. Medido por comportamento — que é o que vale — o
número é **11 handlers**, e o AST tinha contado **treze**. Os dois que sobraram
são falso alarme, e é bom que sejam:

🔬 `alterar_estado_obra` (`views/obras.py:3702`) e `handoff_obra_post` (`:3831`)
**já respondem 404** para obra alheia e inexistente — `if obra is None: return
'Obra não encontrada', 404`, com ramo JSON próprio. O AST os pegou pelo `if not
pode_transitar_como(...)`, que é outra coisa: um 400/403 **depois** que o filtro
de tenant passou, deliberado e comentado no fonte (`:3725-3730`). Contá-los como
resíduo da família 404 seria pedir que a rota respondesse 404 a quem já provou
alcançar a obra.

## Não há oráculo de enumeração aqui

Medido nos onze, comparando status, `Location` e o flash: alheia e inexistente
respondem **o mesmo**. Nas duas rotas de deletar mapa o `Location` difere — mas
só porque ecoa o `obra_id` que o próprio chamador digitou (`/obras/detalhes/
<o-que-ele-mandou>`), e id que o atacante escolheu não é informação que ele
ganhou. Por isso a comparação de oráculo deste arquivo olha status e flash, e
não `Location`; está escrito aqui para o dia em que alguém achar que o teste
esqueceu de olhar.

O que se perde, então, não é sigilo: é semântica. POST a recurso ausente
responde "vá para a lista" em vez de dizer que não existe.

## A forma dos testes, e onde ela melhora a dos lotes c e e

Cada sítio tem **três**, não dois:

1. um **verde de precondição** — o dono passa da guarda. Sem ele, um `xfail` que
   estourasse no andaime (filho semeado errado, decorator barrando) contaria
   como defeito confirmado, e `xfail(strict=True)` não distingue os motivos.
2. um **verde sobre o dado** — o mapa/signatário de A continua lá, a obra de A
   não mudou de status. 🔴 Aqui este arquivo **diverge de propósito** de
   `test_b6_404_cauda.py` e `test_b6_404_frota.py`: lá a afirmação sobre o dado
   mora **dentro** do teste `xfail`, e um `xfail(strict)` engole a falha dela
   como se fosse a do status. Vazamento de dado é pior que 302 no lugar de 404 —
   não pode viajar dentro da marca que diz "sei que isto falha".
3. um **`xfail(strict=True)`** por caso (alheia, inexistente), só sobre o status.
   Quando a B6.7 rodar, ele falha por passar e a marca sai junto com o fix.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

INEXISTENTE = 999_999_999

RAZAO = ('B6.7 nunca executada (censo de 01/09) — views/obras.py responde '
         'flash + 302 onde deveria 404')


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-b6-404-obras'
    yield


# ---------------------------------------------------------------------------
# Semeadores de filho — o que a rota procura DENTRO da obra
# ---------------------------------------------------------------------------

def _sem_filho(_obra_id, _admin_id):
    """Rotas que só resolvem a obra. O `{filho}` do molde nunca é usado."""
    return None


def _mapa(obra_id, admin_id):
    from models import MapaConcorrencia

    m = MapaConcorrencia(obra_id=obra_id, admin_id=admin_id,
                         descricao_item=f'Vergalhao {uuid.uuid4().hex[:6]}')
    db.session.add(m)
    db.session.commit()
    return m.id


def _mapa_v2(obra_id, admin_id):
    from models import MapaConcorrenciaV2

    m = MapaConcorrenciaV2(obra_id=obra_id, admin_id=admin_id,
                           nome=f'Mapa {uuid.uuid4().hex[:6]}', status='aberto')
    db.session.add(m)
    db.session.commit()
    return m.id


def _signatario(obra_id, admin_id):
    from models import ObraSignatarioCliente

    s = ObraSignatarioCliente(obra_id=obra_id, admin_id=admin_id,
                              nome=f'Responsavel {uuid.uuid4().hex[:6]}',
                              ativo=True)
    db.session.add(s)
    db.session.commit()
    return s.id


def _existe(modelo, filho_id):
    from models import (MapaConcorrencia, MapaConcorrenciaV2,  # noqa: F401
                        ObraSignatarioCliente)

    return db.session.get(modelo, filho_id) is not None


# ---------------------------------------------------------------------------
# O censo — 11 sítios, medidos por comportamento em 01/09
# ---------------------------------------------------------------------------
# (molde, form do dono, mensagem da guarda, semeador de filho, modelo do filho)

SITIOS = {
    'toggle_status_obra': (
        '/obras/toggle-status/{obra}', {},
        'Obra não encontrada.', _sem_filho, None),
    'trocar_cliente_obra': (
        '/obras/{obra}/trocar-cliente', {'cliente_id': '{cliente}'},
        'Obra não encontrada.', _sem_filho, None),
    'nova_compra_obra': (
        '/obras/{obra}/compras/nova', {},
        'Obra não encontrada ou sem permissão de acesso.', _sem_filho, None),
    'nova_mapa_concorrencia': (
        '/obras/{obra}/mapa-concorrencia/novo', {},
        'Obra não encontrada ou sem permissão de acesso.', _sem_filho, None),
    'deletar_mapa_concorrencia': (
        '/obras/{obra}/mapa-concorrencia/{filho}/deletar', {},
        'Mapa de concorrência não encontrado.', _mapa, 'MapaConcorrencia'),
    'gerar_cronograma_cliente': (
        '/obras/{obra}/cronograma-cliente/gerar', {},
        'Obra não encontrada.', _sem_filho, None),
    'criar_mapa_v2': (
        '/obras/{obra}/mapa-v2/criar', {},
        'Obra não encontrada.', _sem_filho, None),
    'deletar_mapa_v2': (
        '/obras/{obra}/mapa-v2/{filho}/deletar', {},
        'Mapa não encontrado.', _mapa_v2, 'MapaConcorrenciaV2'),
    'criar_signatario_cliente': (
        '/obras/{obra}/signatarios', {'nome': 'Fulano'},
        'Obra não encontrada.', _sem_filho, None),
    'gerar_senha_signatario_cliente': (
        '/obras/{obra}/signatarios/{filho}/senha', {},
        'Obra não encontrada.', _signatario, 'ObraSignatarioCliente'),
    'toggle_signatario_cliente': (
        '/obras/{obra}/signatarios/{filho}/toggle', {},
        'Obra não encontrada.', _signatario, 'ObraSignatarioCliente'),
}

NOMES = sorted(SITIOS)


def _postar(cliente, url, form):
    """POST + os flashes que a rota deixou na sessão.

    Lê o flash da SESSÃO, não da página seguinte: o que interessa aqui é a
    mensagem que a rota escolheu, e não se o template a renderizou. Sem
    `follow_redirects`, para o flash chegar intacto.
    """
    resposta = cliente.post(url, data=form)
    with cliente.session_transaction() as sessao:
        avisos = [msg for _categoria, msg in sessao.get('_flashes', [])]
    return resposta, avisos


def _cenario(nome, prefixo):
    """Semeia A e B, e devolve as URLs dos três casos.

    O filho é semeado **na obra de A**: sem isso, o caso "alheia" das rotas de
    mapa e signatário mediria um filho que não existe em lugar nenhum, e o 302
    viria do sub-lookup em vez do tenant — passaria pelo motivo errado.
    """
    molde, form, guarda, semeador, modelo = SITIOS[nome]
    with app.app_context():
        a, b = dois_tenants(prefixo, com_fatos=False)
        filho_a = semeador(a.obra_id, a.admin_id)
        dados = {k: v.format(cliente=a.cliente_id) if isinstance(v, str) else v
                 for k, v in form.items()}
        contexto = {
            'admin_a': a.admin_id, 'admin_b': b.admin_id,
            'obra_a': a.obra_id, 'filho_a': filho_a, 'guarda': guarda,
            'modelo': modelo, 'form': dados,
            'url_dono': molde.format(obra=a.obra_id, filho=filho_a),
            'url_alheia': molde.format(obra=a.obra_id, filho=filho_a),
            'url_inexistente': molde.format(obra=INEXISTENTE, filho=filho_a or 1),
        }
    return contexto


# ---------------------------------------------------------------------------
# 1. Precondição — o dono passa da guarda
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome', NOMES)
def test_o_dono_passa_da_guarda_da_obra_precondicao(nome):
    """O dono não recebe a mensagem da guarda na própria obra.

    A afirmação não é "o dono teve sucesso" de propósito: metade destas rotas
    para logo depois, numa validação de formulário que este teste não quer
    encenar (fornecedor, descrição do item, nome do mapa). O que precisa ser
    verdade é só isto: **a requisição atravessou o lookup de obra**. É
    exatamente a precondição dos dois `xfail` abaixo, e nada além dela.
    """
    c = _cenario(nome, f'b6obras_pre_{nome[:12]}')

    _resposta, avisos = _postar(cliente_de(c['admin_a']), c['url_dono'],
                                c['form'])

    assert c['guarda'] not in avisos, (
        f'o dono bateu na guarda da própria obra em {nome}: {avisos} — o '
        f'andaime deste sítio está quebrado, e os xfail abaixo mediriam isso')


# ---------------------------------------------------------------------------
# 2. O dado de A sobrevive à tentativa de B — verde, e fora de qualquer xfail
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome', [n for n in NOMES if SITIOS[n][4]])
def test_o_filho_de_outra_obra_nao_e_destruido(nome):
    """🔴 A recusa é recusa de verdade: o mapa/signatário de A continua lá.

    Este teste é **verde e separado** dos `xfail` de propósito. Se a afirmação
    morasse dentro deles, `xfail(strict=True)` engoliria a falha dela junto com
    a do status — e um vazamento cross-tenant viajaria sob a marca que diz "sei
    que isto falha". O status errado é dívida; o dado alheio destruído é
    incidente.
    """
    import models

    c = _cenario(nome, f'b6obras_dado_{nome[:12]}')
    modelo = getattr(models, c['modelo'])

    cliente_de(c['admin_b']).post(c['url_alheia'], data=c['form'])

    with app.app_context():
        assert _existe(modelo, c['filho_a']), (
            f'🔴 o {c["modelo"]} de outra empresa foi apagado por {nome} — '
            f'isto é bem pior que o 404 que falta')


def test_o_status_da_obra_alheia_nao_muda():
    """`toggle-status` não tem filho, mas tem efeito observável na própria obra."""
    c = _cenario('toggle_status_obra', 'b6obras_status')
    from models import Obra

    with app.app_context():
        antes = db.session.get(Obra, c['obra_a']).status

    cliente_de(c['admin_b']).post(c['url_alheia'])

    with app.app_context():
        depois = db.session.get(Obra, c['obra_a']).status
    assert depois == antes, (
        f'🔴 o status da obra de A foi alternado por B: {antes} → {depois}')


def test_nenhum_signatario_nasce_na_obra_alheia():
    """`criar_signatario` não tem filho a destruir — tem filho a plantar."""
    c = _cenario('criar_signatario_cliente', 'b6obras_planta')
    from models import ObraSignatarioCliente

    cliente_de(c['admin_b']).post(c['url_alheia'], data=c['form'])

    with app.app_context():
        nascidos = ObraSignatarioCliente.query.filter_by(
            obra_id=c['obra_a']).count()
    assert nascidos == 0, (
        f'🔴 B cadastrou {nascidos} responsável(is) na obra de A — quem assina '
        f'RDO em nome do cliente passou a ser escolhido por outra empresa')


# ---------------------------------------------------------------------------
# 3. Ausência de oráculo — verde hoje, e o fix tem de mantê-la assim
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome', NOMES)
def test_alheia_e_inexistente_respondem_o_mesmo(nome):
    """As duas recusas são indistinguíveis — status e flash.

    Verde hoje: este lote nasceu sem oráculo de enumeração, ao contrário do
    `admin.py:441` do lote e. O teste existe para que o **fix** da B6.7 não
    introduza um: é fácil, ao trocar 302 por 404, escrever "obra de outra
    empresa" num ramo e "obra inexistente" no outro.

    `Location` fica fora da comparação, e por um motivo: nas duas rotas de
    deletar mapa ele ecoa o `obra_id` que o próprio chamador digitou. Id que o
    atacante escolheu não é informação que ele ganhou.
    """
    c = _cenario(nome, f'b6obras_orac_{nome[:12]}')

    alheia, aviso_alheia = _postar(cliente_de(c['admin_b']), c['url_alheia'],
                                   c['form'])
    inex, aviso_inex = _postar(cliente_de(c['admin_b']), c['url_inexistente'],
                               c['form'])

    assert alheia.status_code == inex.status_code, (
        f'{nome} distingue alheia ({alheia.status_code}) de inexistente '
        f'({inex.status_code}) no status')
    assert aviso_alheia == aviso_inex, (
        f'{nome} distingue as duas no texto que o usuário lê: '
        f'{aviso_alheia} × {aviso_inex} — isto é um oráculo de enumeração')


# ---------------------------------------------------------------------------
# 4. O 404 que falta — xfail(strict=True), só sobre o status
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=RAZAO)
@pytest.mark.parametrize('nome', NOMES)
def test_recurso_de_outro_tenant_da_404(nome):
    c = _cenario(nome, f'b6obras_alh_{nome[:12]}')

    resposta = cliente_de(c['admin_b']).post(c['url_alheia'], data=c['form'])

    assert resposta.status_code == 404, (
        f'{nome} respondeu {resposta.status_code} para recurso de outra '
        f'empresa (Location: {resposta.headers.get("Location")})')


@pytest.mark.xfail(strict=True, reason=RAZAO)
@pytest.mark.parametrize('nome', NOMES)
def test_obra_inexistente_da_404(nome):
    c = _cenario(nome, f'b6obras_inex_{nome[:12]}')

    resposta = cliente_de(c['admin_b']).post(c['url_inexistente'],
                                             data=c['form'])

    assert resposta.status_code == 404, (
        f'{nome} respondeu {resposta.status_code} para obra inexistente '
        f'(Location: {resposta.headers.get("Location")})')


# ---------------------------------------------------------------------------
# 5. Os dois que o censo AST contava e não são resíduo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('rota', ['/obras/{obra}/estado', '/obras/{obra}/handoff'])
@pytest.mark.parametrize('caso', ['alheia', 'inexistente'])
def test_estado_e_handoff_ja_respondem_404(rota, caso):
    """🔬 Estes dois **já estão certos** — e o teste é o que impede que a
    próxima varredura os conte como resíduo de novo.

    Foram listados no censo AST da B6.7 por causa do `if not
    pode_transitar_como(...)`, que é outra coisa: 400/403 **depois** que o
    filtro de tenant passou, deliberado e comentado em `views/obras.py:
    3725-3730`. A guarda de tenant deles já é `if obra is None: return 'Obra
    não encontrada', 404`.
    """
    with app.app_context():
        a, b = dois_tenants(f'b6obras_ok_{caso}', com_fatos=False)
        admin_b = b.admin_id
        alvo = a.obra_id if caso == 'alheia' else INEXISTENTE

    resposta = cliente_de(admin_b).post(rota.format(obra=alvo))

    assert resposta.status_code == 404, (
        f'{rota} respondeu {resposta.status_code} para obra {caso} — este '
        f'sítio ESTAVA certo e regrediu')
