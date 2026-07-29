"""Fase 9a — ciência do cliente sobre o RDO, com N responsáveis por obra.

O portal da obra é anônimo por construção (`portal_obras_views.py:3`) e
`PortalAcessoEvento` diz textualmente que identificar pessoa "é a Fase 9a".
Esta suíte cobre justamente isso: responsáveis nomeados por obra, senha
pedida SÓ no ato de assinar, e o placar "todos precisam assinar".

Redesenho de 29/07 (spec 2026-07-29-ciencia-rdo-portal-ux-design.md): NÃO HÁ
MAIS SESSÃO DE LOGIN. A senha é conferida no mesmo POST que grava a ciência
(`POST .../ciencia`), e as rotas `/entrar`, `/sair` e `/assinar` morreram —
`test_rotas_de_sessao_morreram_de_verdade` garante que continuem mortas.

O caso mais importante daqui não é nenhuma funcionalidade nova, e sim a
REGRESSÃO da migração 268: trocar `UNIQUE (rdo_id, papel)` por dois índices
parciais não pode ter afrouxado o "um executor por RDO" que a Fase 5 travou.
Ver `test_papeis_internos_continuam_unicos_por_rdo`.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Obra, ObraSignatarioCliente, RDO, RDOAssinatura,
                    TipoUsuario, Usuario)
from services.rdo_ciclo_vida import APROVADO, ASSINADO, PREENCHIDO, RASCUNHO

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase9a-ciencia'
    # O rate-limit é global e vive na memória do processo: todo teste sai do
    # mesmo 127.0.0.1, então sem desligar aqui os testes que repetem login
    # falhariam por 429. `limiter.enabled` (atributo de instância), e NÃO
    # `app.config['RATELIMIT_ENABLED']` — a config só é lida na construção do
    # Limiter, que já aconteceu no import do app. O limite EM SI é coberto por
    # `test_rate_limit_barra_forca_bruta_por_signatario`, que o religa.
    from app import limiter
    limiter.enabled = False
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


def _sfx():
    return uuid.uuid4().hex[:8]


# Caminho até cada estado terminal. Gravar `RDO.estado` direto seria mais
# curto, mas `test_fase5_rdo_ciclo_vida.py` verifica no banco INTEIRO que não
# existe RDO 'assinado' sem trilha de transição — autoria forjada. Um helper
# de teste que burla a máquina de estados quebra esse invariante de verdade,
# e é o tipo de dado sujo que sobrevive à suíte que o criou.
_CAMINHO = {
    RASCUNHO: [],
    PREENCHIDO: [PREENCHIDO],
    ASSINADO: [PREENCHIDO, ASSINADO],
    APROVADO: [PREENCHIDO, ASSINADO, APROVADO],
}


def _levar_ao_estado(rdo, estado, usuario):
    from services.rdo_ciclo_vida import transicionar
    for passo in _CAMINHO[estado]:
        transicionar(rdo, passo, usuario=usuario, motivo='setup de teste')
    db.session.flush()


def _cenario(*, n_signatarios=3, estado=ASSINADO, senha='Senha@2026'):
    """Tenant + obra com portal ativo + RDO no estado pedido + N responsáveis.

    Todos já nascem com senha DEFINITIVA (`senha_temporaria=False`): o regime
    temporário é exercitado nos testes que tratam dele, e não vale carregar
    esse passo em todos os outros.
    """
    with app.app_context():
        suf = _sfx()
        admin = Usuario(
            username=f'f9a_{suf}', email=f'f9a_{suf}@test.local',
            nome=f'Admin F9A {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()

        cli = Cliente(nome=f'CLI-F9A-{suf}', admin_id=admin.id)
        db.session.add(cli)
        db.session.flush()

        obra = Obra(
            nome=f'Obra F9A {suf}', codigo=f'O9A{suf[:6].upper()}',
            data_inicio=date(2026, 1, 1), admin_id=admin.id,
            cliente_id=cli.id, valor_contrato=250000,
            portal_ativo=True, token_cliente=f'tok-{suf}-{_sfx()}',
        )
        db.session.add(obra)
        db.session.flush()

        rdo = RDO(
            numero_rdo=f'RDO-F9A-{suf}', data_relatorio=date(2026, 6, 22),
            obra_id=obra.id, admin_id=admin.id, estado=RASCUNHO,
            comentario_geral='Concretagem das vigas baldrame.',
        )
        db.session.add(rdo)
        db.session.flush()
        _levar_ao_estado(rdo, estado, admin)

        ids = []
        for i in range(n_signatarios):
            s = ObraSignatarioCliente(
                obra_id=obra.id, admin_id=admin.id,
                nome=f'Responsável {i + 1} {suf}',
                cargo=['Eng. responsável', 'Fiscal de obra', 'Diretor'][i % 3],
                email=f'resp{i}_{suf}@cliente.local',
                password_hash=generate_password_hash(senha),
                senha_temporaria=False, ativo=True,
            )
            db.session.add(s)
            db.session.flush()
            ids.append(s.id)

        db.session.commit()
        return {'admin_id': admin.id, 'obra_id': obra.id, 'rdo_id': rdo.id,
                'token': obra.token_cliente, 'sig_ids': ids, 'senha': senha}


def _url(ctx, sufixo=''):
    return f"/portal/obra/{ctx['token']}/rdo/{ctx['rdo_id']}{sufixo}"


def _assinar(c, ctx, sig_id=None, senha=None, observacao=None, rdo_id=None,
             **kw):
    """O POST atômico: identidade + senha + (observação) numa requisição só.

    Substitui o antigo par `_login` + POST /assinar — não existe mais "estar
    logado", existe assinar.
    """
    dados = {
        'signatario_id': sig_id if sig_id is not None else ctx['sig_ids'][0],
        'senha': senha if senha is not None else ctx['senha'],
    }
    if observacao is not None:
        dados['observacao'] = observacao
    rid = rdo_id if rdo_id is not None else ctx['rdo_id']
    return c.post(f"/portal/obra/{ctx['token']}/rdo/{rid}/ciencia",
                  data=dados, follow_redirects=False, **kw)


def _rdos_extras(ctx, n=1):
    """Mais N RDOs assinados na mesma obra — com trilha, como o principal."""
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        admin = db.session.get(Usuario, ctx['admin_id'])
        ids = []
        for i in range(n):
            r = RDO(numero_rdo=f'RDO-EXTRA-{_sfx()}',
                    data_relatorio=date(2026, 6, 23 + i), obra_id=obra.id,
                    admin_id=obra.admin_id, estado=RASCUNHO)
            db.session.add(r)
            db.session.flush()
            _levar_ao_estado(r, ASSINADO, admin)
            ids.append(r.id)
        db.session.commit()
        return ids


def _assinaturas(rdo_id):
    with app.app_context():
        return RDOAssinatura.query.filter_by(
            rdo_id=rdo_id, papel=RDOAssinatura.PAPEL_CLIENTE).all()


def _sig(sid):
    with app.app_context():
        return db.session.get(ObraSignatarioCliente, sid)


def _placar(ctx):
    with app.app_context():
        from services.rdo_ciencia_cliente import placar
        return placar(db.session.get(RDO, ctx['rdo_id']))


# ---------------------------------------------------------------------------
# Placar: todos precisam assinar
# ---------------------------------------------------------------------------

def test_tres_responsaveis_assinam_e_o_placar_fecha_so_no_terceiro():
    ctx = _cenario(n_signatarios=3)

    for i, sid in enumerate(ctx['sig_ids'], start=1):
        c = app.test_client()
        r = _assinar(c, ctx, sid)
        assert r.status_code == 302
        # O destino do ato é o comprovante, não a página de leitura.
        assert '/ciencia/comprovante' in r.headers.get('Location', '')

        p = _placar(ctx)
        assert p['assinados'] == i
        assert p['total'] == 3
        assert p['completo'] is (i == 3)

    assert len(_assinaturas(ctx['rdo_id'])) == 3


def test_placar_sem_responsavel_cadastrado_nao_anuncia_conclusao():
    """Zero cadastrados não é "todos assinaram" — é "não há o que assinar"."""
    ctx = _cenario(n_signatarios=0)
    p = _placar(ctx)
    assert (p['total'], p['assinados'], p['completo']) == (0, 0, False)


def test_mesmo_responsavel_nao_assina_duas_vezes():
    ctx = _cenario(n_signatarios=2)
    c = app.test_client()
    assert _assinar(c, ctx).status_code == 302
    r = _assinar(c, ctx)
    # A repetição não é falha: leva ao comprovante do ato que já existe.
    assert r.status_code == 302
    assert '/ciencia/comprovante' in r.headers.get('Location', '')
    assert len(_assinaturas(ctx['rdo_id'])) == 1


def test_indice_parcial_barra_ciencia_duplicada_no_banco():
    """A garantia real é do banco, não da checagem da aplicação."""
    from sqlalchemy.exc import IntegrityError

    ctx = _cenario(n_signatarios=1)
    with app.app_context():
        for _ in range(2):
            db.session.add(RDOAssinatura(
                rdo_id=ctx['rdo_id'], admin_id=ctx['admin_id'],
                signatario_cliente_id=ctx['sig_ids'][0],
                papel=RDOAssinatura.PAPEL_CLIENTE,
                nome_signatario='Duplicata', hash_conteudo='x' * 64))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_papeis_internos_continuam_unicos_por_rdo():
    """REGRESSÃO da migração 268 — o teste que justifica os índices parciais.

    `signatario_cliente_id` é NULL nos papéis internos. Se a unicidade tivesse
    virado UNIQUE (rdo_id, papel, signatario_cliente_id), o NULL distinto do
    PostgreSQL deixaria dois executores no mesmo RDO — afrouxando em silêncio
    o que a Fase 5 travou.
    """
    from sqlalchemy.exc import IntegrityError

    ctx = _cenario(n_signatarios=1)
    with app.app_context():
        for _ in range(2):
            db.session.add(RDOAssinatura(
                rdo_id=ctx['rdo_id'], admin_id=ctx['admin_id'],
                papel=RDOAssinatura.PAPEL_EXECUTOR,
                nome_signatario='Executor', hash_conteudo='y' * 64))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_ciencia_nao_altera_o_estado_do_rdo():
    """Ciência é ORTOGONAL ao ciclo de vida interno."""
    ctx = _cenario(n_signatarios=1, estado=ASSINADO)
    c = app.test_client()
    _assinar(c, ctx)
    with app.app_context():
        assert db.session.get(RDO, ctx['rdo_id']).estado == ASSINADO


def test_assinatura_grava_hash_ip_e_nome_em_snapshot():
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    _assinar(c, ctx, observacao='Conferido em campo.',
             environ_overrides={'REMOTE_ADDR': '203.0.113.9'})

    a = _assinaturas(ctx['rdo_id'])[0]
    assert a.papel == RDOAssinatura.PAPEL_CLIENTE
    assert a.signatario_cliente_id == ctx['sig_ids'][0]
    assert a.usuario_id is None and a.funcionario_id is None
    assert len(a.hash_conteudo) == 64 and a.algoritmo == 'sha256'
    assert a.provedor == 'interno'
    assert a.ip == '203.0.113.9'
    assert a.observacao == 'Conferido em campo.'
    assert a.nome_signatario == _sig(ctx['sig_ids'][0]).nome


# ---------------------------------------------------------------------------
# Elegibilidade pelo estado do RDO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('estado', [RASCUNHO, PREENCHIDO])
def test_rdo_ainda_editavel_recusa_ciencia(estado):
    ctx = _cenario(n_signatarios=1, estado=estado)
    c = app.test_client()
    _assinar(c, ctx)
    assert _assinaturas(ctx['rdo_id']) == []


@pytest.mark.parametrize('estado', [ASSINADO, APROVADO])
def test_rdo_imutavel_aceita_ciencia(estado):
    ctx = _cenario(n_signatarios=1, estado=estado)
    c = app.test_client()
    _assinar(c, ctx)
    assert len(_assinaturas(ctx['rdo_id'])) == 1


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def test_senha_errada_nao_assina_e_conta_a_falha():
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    _assinar(c, ctx, senha='errada')
    assert _sig(ctx['sig_ids'][0]).falhas_login == 1
    assert _assinaturas(ctx['rdo_id']) == []


def test_dez_falhas_travam_o_signatario_e_a_senha_certa_para_de_valer():
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    for _ in range(ObraSignatarioCliente.MAX_FALHAS):
        _assinar(c, ctx, senha='errada')
    assert _sig(ctx['sig_ids'][0]).travado is True

    _assinar(c, ctx)                      # agora com a senha CERTA
    assert _assinaturas(ctx['rdo_id']) == []


def test_gerar_senha_temporaria_destrava_e_limpa_o_pedido():
    from services.portal_signatario_auth import (gerar_senha_temporaria,
                                                 pedir_recuperacao)

    ctx = _cenario(n_signatarios=1)
    with app.app_context():
        s = db.session.get(ObraSignatarioCliente, ctx['sig_ids'][0])
        s.falhas_login = ObraSignatarioCliente.MAX_FALHAS
        pedir_recuperacao(s)
        db.session.commit()

        s = db.session.get(ObraSignatarioCliente, ctx['sig_ids'][0])
        senha = gerar_senha_temporaria(s)
        db.session.commit()

    s = _sig(ctx['sig_ids'][0])
    assert s.travado is False
    assert s.recuperacao_pedida_em is None
    assert s.senha_temporaria is True
    assert len(senha) == 10

    # A senha temporária autentica — e o POST desvia para a troca.
    c = app.test_client()
    r = _assinar(c, ctx, senha=senha)
    assert r.status_code == 302
    assert '/ciencia/senha' in r.headers.get('Location', '')


def test_senha_temporaria_autentica_mas_nao_assina_antes_da_troca():
    """Senha que a construtora conhece não identifica ninguém."""
    from services.portal_signatario_auth import gerar_senha_temporaria

    ctx = _cenario(n_signatarios=1)
    with app.app_context():
        s = db.session.get(ObraSignatarioCliente, ctx['sig_ids'][0])
        senha = gerar_senha_temporaria(s)
        db.session.commit()

    c = app.test_client()
    r = _assinar(c, ctx, senha=senha)
    assert '/ciencia/senha' in r.headers.get('Location', '')
    assert _assinaturas(ctx['rdo_id']) == []

    # Define a senha própria — a atual autentica no próprio POST — e assina.
    c.post(_url(ctx, '/ciencia/senha'),
           data={'signatario_id': ctx['sig_ids'][0], 'senha_atual': senha,
                 'nova_senha': 'MinhaSenha!9',
                 'confirma_senha': 'MinhaSenha!9'})
    assert _sig(ctx['sig_ids'][0]).senha_temporaria is False
    _assinar(c, ctx, senha='MinhaSenha!9')
    assert len(_assinaturas(ctx['rdo_id'])) == 1


def test_senha_temporaria_vencida_nao_autentica():
    from services.portal_signatario_auth import gerar_senha_temporaria

    ctx = _cenario(n_signatarios=1)
    with app.app_context():
        s = db.session.get(ObraSignatarioCliente, ctx['sig_ids'][0])
        senha = gerar_senha_temporaria(s)
        s.senha_expira_em = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

    c = app.test_client()
    _assinar(c, ctx, senha=senha)
    assert _assinaturas(ctx['rdo_id']) == []


def test_troca_de_senha_recusa_senha_curta_e_confirmacao_diferente():
    from services.portal_signatario_auth import SENHA_MIN

    ctx = _cenario(n_signatarios=1)
    c = app.test_client()

    base = {'signatario_id': ctx['sig_ids'][0], 'senha_atual': ctx['senha']}
    c.post(_url(ctx, '/ciencia/senha'),
           data={**base, 'nova_senha': 'abc', 'confirma_senha': 'abc'})
    c.post(_url(ctx, '/ciencia/senha'),
           data={**base, 'nova_senha': 'senhaboa123',
                 'confirma_senha': 'outracoisa'})
    # Nenhuma das duas passou: a senha original continua assinando.
    c2 = app.test_client()
    _assinar(c2, ctx)
    assert len(_assinaturas(ctx['rdo_id'])) == 1
    assert SENHA_MIN == 8


def test_troca_de_senha_sem_a_senha_atual_certa_nao_passa():
    """Sem sessão, a senha ATUAL é o que autentica a troca. Sem ela, qualquer
    um trocaria a senha de qualquer nome da lista pública."""
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    antes = _sig(ctx['sig_ids'][0]).password_hash

    c.post(_url(ctx, '/ciencia/senha'),
           data={'signatario_id': ctx['sig_ids'][0],
                 'senha_atual': 'chute-errado',
                 'nova_senha': 'DoAtacante!9',
                 'confirma_senha': 'DoAtacante!9'})

    s = _sig(ctx['sig_ids'][0])
    assert s.password_hash == antes, 'senha trocada sem provar a atual'
    assert s.falhas_login == 1


def test_rate_limit_barra_forca_bruta_por_signatario():
    """O limite existe — e é por (IP, signatário), não por IP puro.

    Os responsáveis de um cliente costumam sair do mesmo IP. Chave em IP puro
    faria o erro de um travar o outro; aqui o segundo continua entrando
    enquanto o primeiro já levou 429.
    """
    from app import limiter

    ctx = _cenario(n_signatarios=2)
    limiter.enabled = True
    limiter.reset()
    try:
        c = app.test_client()
        alvo = ctx['sig_ids'][0]
        for _ in range(5):
            _assinar(c, ctx, alvo, senha='errada')
        assert _assinar(c, ctx, alvo, senha='errada').status_code == 429

        # O colega, mesmo IP, não foi punido pelo erro do primeiro — e a
        # prova mais forte possível: ele ASSINA.
        assert _assinar(c, ctx, ctx['sig_ids'][1]).status_code == 302
        assert len(_assinaturas(ctx['rdo_id'])) == 1
    finally:
        limiter.enabled = False
        limiter.reset()


def test_esqueci_senha_marca_pendencia_sem_revelar_quem_existe():
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()

    r = c.post(_url(ctx, '/ciencia/esqueci'),
               data={'signatario_id': ctx['sig_ids'][0]})
    assert r.status_code == 302
    assert _sig(ctx['sig_ids'][0]).recuperacao_pedida_em is not None

    # Id inexistente responde igual — a rota não vira verificador de cadastro.
    r2 = c.post(_url(ctx, '/ciencia/esqueci'), data={'signatario_id': 999_999})
    assert r2.status_code == 302


# ---------------------------------------------------------------------------
# Escopo — sem sessão, a credencial vale para UMA obra e o token manda
# ---------------------------------------------------------------------------

def test_credencial_de_uma_obra_nao_assina_em_outra():
    """`autenticar` resolve o signatário DENTRO da obra do token — o id e a
    senha da obra A são lixo na obra B."""
    a = _cenario(n_signatarios=1)
    b = _cenario(n_signatarios=1)

    c = app.test_client()
    _assinar(c, b, sig_id=a['sig_ids'][0], senha=a['senha'])
    assert _assinaturas(b['rdo_id']) == []
    assert _assinaturas(a['rdo_id']) == []


def test_cada_rdo_exige_a_senha_e_tres_atos_seguidos_funcionam():
    """O contrato do redesenho: sem senha nada assina; com senha, assinar
    três RDOs em sequência são três POSTs — nenhum estado entre eles."""
    ctx = _cenario(n_signatarios=1)
    outros = _rdos_extras(ctx, n=2)
    c = app.test_client()

    # Sem senha (corpo vazio), nenhum RDO assina — não há sessão que ajude.
    for rid in [ctx['rdo_id']] + outros:
        c.post(f"/portal/obra/{ctx['token']}/rdo/{rid}/ciencia", data={})
        assert _assinaturas(rid) == []

    for rid in [ctx['rdo_id']] + outros:
        _assinar(c, ctx, rdo_id=rid)
    for rid in [ctx['rdo_id']] + outros:
        assert len(_assinaturas(rid)) == 1


def test_desativado_some_do_placar_mas_a_assinatura_dele_permanece():
    ctx = _cenario(n_signatarios=2)
    c = app.test_client()
    _assinar(c, ctx, ctx['sig_ids'][0])

    with app.app_context():
        s = db.session.get(ObraSignatarioCliente, ctx['sig_ids'][0])
        s.ativo = False
        db.session.commit()

    p = _placar(ctx)
    assert p['total'] == 1                 # só o remanescente conta
    assert p['assinados'] == 0
    assert len(p['extras']) == 1           # o ato aconteceu e continua visível
    assert len(_assinaturas(ctx['rdo_id'])) == 1


def test_desativado_nao_autentica_mais():
    ctx = _cenario(n_signatarios=1)
    with app.app_context():
        db.session.get(ObraSignatarioCliente, ctx['sig_ids'][0]).ativo = False
        db.session.commit()

    c = app.test_client()
    _assinar(c, ctx)
    assert _assinaturas(ctx['rdo_id']) == []


def test_token_de_outra_obra_nao_alcanca_este_rdo():
    a = _cenario(n_signatarios=1)
    b = _cenario(n_signatarios=1)
    c = app.test_client()
    r = c.post(f"/portal/obra/{b['token']}/rdo/{a['rdo_id']}/ciencia",
               data={'signatario_id': a['sig_ids'][0], 'senha': a['senha']})
    assert r.status_code == 404
    assert _assinaturas(a['rdo_id']) == []


def test_rotas_de_sessao_morreram_de_verdade():
    """Guarda contra ressurreição (spec §6): as rotas da sessão respondem 404
    e o cookie não carrega identidade nenhuma depois de assinar. Transforma
    "removemos a sessão" numa propriedade verificada, não numa promessa."""
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()

    for sufixo in ('/entrar', '/sair', '/assinar'):
        r = c.post(_url(ctx, sufixo), data={
            'signatario_id': ctx['sig_ids'][0], 'senha': ctx['senha']})
        assert r.status_code == 404, f'{sufixo} respondeu {r.status_code}'
    assert _assinaturas(ctx['rdo_id']) == []

    _assinar(c, ctx)
    with c.session_transaction() as sess:
        assert 'portal_sig' not in sess, 'a sessão de login ressuscitou'
        # O que sobra é a marca do comprovante — id de assinatura + validade,
        # nada de identidade.
        marca = sess.get('portal_comprovante')
        assert marca is not None
        assert set(marca.keys()) == {'assinatura_id', 'exp'}

    # E a marca não autentica: outro RDO continua exigindo a senha.
    extra = _rdos_extras(ctx, n=1)[0]
    c.post(f"/portal/obra/{ctx['token']}/rdo/{extra}/ciencia", data={})
    assert _assinaturas(extra) == []


def test_rdo_bloqueado_ainda_permite_trocar_a_propria_senha():
    """Regressão da 1ª versão da Fase 9a, preservada no redesenho: o bloqueio
    da ciência não pode deixar o responsável sem caminho para a troca de
    senha. Hoje o caminho é a rota própria, não um formulário na leitura."""
    ctx = _cenario(n_signatarios=2, estado=PREENCHIDO)
    c = app.test_client()

    html = c.get(_url(ctx)).get_data(as_text=True)
    assert 'ainda está sendo finalizado' in html      # o motivo, na faixa
    assert 'Dar ciência' not in html                  # sem botão de assinar

    # A tela do ato recusa e devolve à leitura…
    r = c.get(_url(ctx, '/ciencia'))
    assert r.status_code == 302

    # …mas trocar a senha continua funcionando, autenticada pelo POST.
    antes = _sig(ctx['sig_ids'][0]).password_hash
    r = c.post(_url(ctx, '/ciencia/senha'),
               data={'signatario_id': ctx['sig_ids'][0],
                     'senha_atual': ctx['senha'],
                     'nova_senha': 'OutraSenha!7',
                     'confirma_senha': 'OutraSenha!7'})
    assert r.status_code == 302
    assert _sig(ctx['sig_ids'][0]).password_hash != antes


def test_rdo_alterado_depois_de_assinado_marca_a_ciencia_como_nao_integra():
    """O hash guardado só vale se for conferido — este é o teste que o cobra."""
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    _assinar(c, ctx)

    p = _placar(ctx)
    assert p['itens'][0]['integra'] is True
    assert p['alteradas'] == []

    # Altera o conteúdo POR FORA da aplicação — UPDATE cru, sem passar pela
    # sessão do ORM. A guarda de imutabilidade da Fase 5 recusa a alteração
    # pelo caminho normal (levanta `RDOImutavel`), e é justamente por isso que
    # o hash existe: cobrir o que a guarda não alcança, como um acesso direto
    # ao banco ou uma restauração de backup adulterada.
    with app.app_context():
        db.session.execute(
            db.text('UPDATE rdo SET comentario_geral = :t WHERE id = :i'),
            {'t': 'Texto trocado por fora da aplicação.', 'i': ctx['rdo_id']})
        db.session.commit()

    p = _placar(ctx)
    assert p['itens'][0]['integra'] is False
    assert len(p['alteradas']) == 1
    # A ciência não some — ela aconteceu; o que muda é o alerta.
    assert p['assinados'] == 1

    html = c.get(_url(ctx)).get_data(as_text=True)
    assert 'foi alterado depois de assinado' in html


def test_placar_por_rdo_e_o_da_listagem_batem_com_o_detalhado():
    """A listagem usa um caminho em lote (2 queries); não pode divergir."""
    from services.rdo_ciencia_cliente import placar_por_rdo

    ctx = _cenario(n_signatarios=3)
    c = app.test_client()
    _assinar(c, ctx, ctx['sig_ids'][0])

    with app.app_context():
        rdo = db.session.get(RDO, ctx['rdo_id'])
        lote = placar_por_rdo(ctx['obra_id'], [rdo])
        det = _placar(ctx)
    assert lote[ctx['rdo_id']]['assinados'] == det['assinados'] == 1
    assert lote[ctx['rdo_id']]['total'] == det['total'] == 3
    assert lote[ctx['rdo_id']]['completo'] is det['completo'] is False


def test_placar_da_listagem_ignora_rdo_que_nao_aceita_ciencia():
    """Mostrar "0/3" num RDO que a construtora nem finalizou cobraria do
    cliente algo que ele não pode fazer."""
    from services.rdo_ciencia_cliente import placar_por_rdo

    ctx = _cenario(n_signatarios=2, estado=PREENCHIDO)
    with app.app_context():
        rdo = db.session.get(RDO, ctx['rdo_id'])
        assert placar_por_rdo(ctx['obra_id'], [rdo]) == {}


def test_listagem_do_portal_mostra_o_placar_em_miniatura():
    ctx = _cenario(n_signatarios=2)
    c = app.test_client()
    _assinar(c, ctx, ctx['sig_ids'][0])

    html = c.get(f"/portal/obra/{ctx['token']}").get_data(as_text=True)
    assert 'rdo-ciencia' in html
    assert '1/2' in html


def _texto_do_pdf(rdo_id):
    """Texto do PDF gerado, via `pypdf` (já instalado no projeto).

    Os streams do reportlab saem comprimidos com FlateDecode, então não dá
    para varrer os literais no bruto — a primeira versão deste helper tentou
    e leu binário.
    """
    from io import BytesIO

    from pypdf import PdfReader

    with app.app_context():
        from services.rdo_pdf_service import gerar_pdf_rdo
        blob = gerar_pdf_rdo(db.session.get(RDO, rdo_id))
    assert blob[:5] == b'%PDF-'
    leitor = PdfReader(BytesIO(blob))
    return '\n'.join((p.extract_text() or '') for p in leitor.pages)


def test_pdf_do_rdo_traz_a_ciencia_com_quem_falta():
    """Num PDF anexado a medição, "2 de 3" e o nome de quem falta são a
    diferença entre "duas pessoas assinaram" e "falta o diretor"."""
    ctx = _cenario(n_signatarios=3)
    c = app.test_client()
    _assinar(c, ctx, ctx['sig_ids'][0])

    # `_section_rule` faz `label.upper()`: o título sai "CIÊNCIA DO CLIENTE".
    texto = _texto_do_pdf(ctx['rdo_id']).lower()
    assert 'ciência do cliente' in texto
    assert '1 de 3' in texto
    assert 'aguardando ciência' in texto
    # quem assinou e quem falta, ambos nomeados
    assert _sig(ctx['sig_ids'][0]).nome.lower() in texto
    assert _sig(ctx['sig_ids'][2]).nome.lower() in texto


def test_pdf_sem_responsaveis_nao_ganha_secao_de_ciencia():
    ctx = _cenario(n_signatarios=0)
    assert 'ciência do cliente' not in _texto_do_pdf(ctx['rdo_id']).lower()


def test_pdf_alerta_quando_o_rdo_mudou_depois_de_assinado():
    """Um PDF que lista assinaturas de um documento alterado parece prova e
    não é. O papel tem de dizer."""
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    _assinar(c, ctx)

    texto = _texto_do_pdf(ctx['rdo_id']).lower()
    assert 'atenção' not in texto                 # íntegro: sem alerta
    assert 'alterado depois' not in texto

    with app.app_context():
        db.session.execute(
            db.text('UPDATE rdo SET comentario_geral = :t WHERE id = :i'),
            {'t': 'Alterado por fora.', 'i': ctx['rdo_id']})
        db.session.commit()

    texto = _texto_do_pdf(ctx['rdo_id']).lower()
    assert 'atenção' in texto
    assert 'integridade' in texto
    assert 'não deve ser usado como evidência' in texto
    assert 'alterado depois' in texto             # marca na linha da pessoa


def test_tela_interna_mostra_quem_falta_dar_ciencia():
    """O lado da construtora: a tabela de assinaturas diz quem assinou, o
    placar diz quem falta — é o que serve para cobrar o cliente."""
    ctx = _cenario(n_signatarios=3)
    c = app.test_client()
    _assinar(c, ctx, ctx['sig_ids'][0])

    interno = app.test_client()
    with interno.session_transaction() as sess:
        sess['_user_id'] = str(ctx['admin_id'])
        sess['_fresh'] = True
    html = interno.get(f"/rdo/{ctx['rdo_id']}").get_data(as_text=True)

    assert 'Ciência do cliente' in html
    assert '1 de 3' in html
    assert 'Aguardando' in html
    for sid in ctx['sig_ids'][1:]:
        assert _sig(sid).nome in html          # os dois que faltam, nomeados


def test_pagina_do_rdo_mostra_faixa_e_placar_e_a_tela_do_ato_o_seletor():
    """A leitura tem o estado (faixa + placar nominal); o formulário mora na
    tela do ato. Cada tela com um trabalho — decisão D2 do redesenho."""
    ctx = _cenario(n_signatarios=2)
    c = app.test_client()

    html = c.get(_url(ctx)).get_data(as_text=True)
    assert 'Ciência do cliente' in html               # placar nominal, no fim
    assert '0 de 2' in html
    assert 'Dar ciência' in html                      # a chamada, na faixa
    assert 'Selecione seu nome' not in html           # formulário: só no ato
    for sid in ctx['sig_ids']:
        assert _sig(sid).nome in html                 # quem falta, nomeado

    ato = c.get(_url(ctx, '/ciencia')).get_data(as_text=True)
    assert 'Selecione seu nome' in ato
    assert 'Confirmar minha ciência' in ato
    assert 'Você está confirmando' in ato             # o resumo do documento


# ---------------------------------------------------------------------------
# Segurança — achados da revisão de 29/07 (RELATORIO-REVISAO-2026-07-29.md)
# ---------------------------------------------------------------------------

def _client_admin(admin_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    return c


def test_admin_de_outro_tenant_nao_ve_os_signatarios_da_obra():
    """Vazamento entre tenants: `editar_obra` usava `Obra.query.get_or_404`
    sem filtro de admin_id, e a Fase 9a pendurou ali a lista de contatos do
    CLIENTE — nome, e-mail, último acesso, estado da senha."""
    dono = _cenario(n_signatarios=2)
    vizinho = _cenario(n_signatarios=1)

    c = _client_admin(vizinho['admin_id'])
    r = c.get(f"/obras/editar/{dono['obra_id']}")

    # 404 opaco (não 403): obra fora do alcance não vaza nem a existência.
    assert r.status_code == 404, r.status_code
    html = r.get_data(as_text=True)
    for sid in dono['sig_ids']:
        assert _sig(sid).nome not in html


def test_dono_da_obra_continua_vendo_os_proprios_signatarios():
    """O contrapeso do teste acima — a correção não pode fechar a porta certa."""
    ctx = _cenario(n_signatarios=2)
    c = _client_admin(ctx['admin_id'])
    r = c.get(f"/obras/editar/{ctx['obra_id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for sid in ctx['sig_ids']:
        assert _sig(sid).nome in html


def test_rotas_de_signatario_recusam_obra_de_outro_tenant():
    """As três rotas de mutação, pelo mesmo eixo."""
    dono = _cenario(n_signatarios=1)
    vizinho = _cenario(n_signatarios=1)
    c = _client_admin(vizinho['admin_id'])
    alvo = dono['sig_ids'][0]
    antes = _sig(alvo).password_hash

    for url, dados in [
        (f"/obras/{dono['obra_id']}/signatarios", {'nome': 'Intruso'}),
        (f"/obras/{dono['obra_id']}/signatarios/{alvo}/senha", {}),
        (f"/obras/{dono['obra_id']}/signatarios/{alvo}/toggle", {}),
    ]:
        c.post(url, data=dados)

    with app.app_context():
        assert ObraSignatarioCliente.query.filter_by(
            obra_id=dono['obra_id']).count() == 1     # nada criado
    s = _sig(alvo)
    assert s.password_hash == antes                    # senha intacta
    assert s.ativo is True                             # não desativado


def test_rotas_de_signatario_exigem_csrf():
    """O blueprint `main` é isento de CSRF em bloco (app.py:1051), então estas
    rotas — que cunham credencial de assinatura — precisam reativar a trava
    explicitamente. Sem isso, um POST forjado de outra aba troca a senha do
    responsável do cliente usando o cookie do funcionário logado."""
    ctx = _cenario(n_signatarios=2)
    alvo = ctx['sig_ids'][0]

    # CSRF LIGADO — é o estado de produção. A fixture desliga por conveniência
    # dos outros testes; aqui é justamente o que está sob teste.
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        c = _client_admin(ctx['admin_id'])
        antes = _sig(alvo).password_hash

        for url in [f"/obras/{ctx['obra_id']}/signatarios/{alvo}/senha",
                    f"/obras/{ctx['obra_id']}/signatarios/{alvo}/toggle"]:
            r = c.post(url, data={})          # sem token
            assert r.status_code in (302, 400), (url, r.status_code)

        s = _sig(alvo)
        assert s.password_hash == antes, 'senha trocada por POST sem CSRF'
        assert s.ativo is True, 'signatário desativado por POST sem CSRF'

        r = c.post(f"/obras/{ctx['obra_id']}/signatarios",
                   data={'nome': 'Forjado'})
        with app.app_context():
            assert ObraSignatarioCliente.query.filter_by(
                obra_id=ctx['obra_id'], nome='Forjado').first() is None
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


def test_rotas_de_signatario_funcionam_com_csrf_valido():
    """Contrapeso: a trava não pode quebrar o caminho legítimo."""
    ctx = _cenario(n_signatarios=1)
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        c = _client_admin(ctx['admin_id'])
        import re as _re
        html = c.get(f"/obras/editar/{ctx['obra_id']}").get_data(as_text=True)
        m = _re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
        assert m, 'a tela não expõe o meta csrf-token que o JS usa'

        antes = _sig(ctx['sig_ids'][0]).password_hash
        r = c.post(f"/obras/{ctx['obra_id']}/signatarios/{ctx['sig_ids'][0]}/senha",
                   data={'csrf_token': m.group(1)})
        assert r.status_code == 302
        assert _sig(ctx['sig_ids'][0]).password_hash != antes
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


def test_drop_constraint_nao_remove_indice_e_a_269_remove():
    """O DEFEITO em si, isolado numa tabela de rascunho.

    A migração 268 removeu a unicidade antiga com `DROP CONSTRAINT IF EXISTS`,
    assumindo que `uq_rdo_assinatura_papel` era sempre uma constraint. Numa
    instalação NOVA ele é um ÍNDICE: `db.create_all()` roda antes das migrações
    (app.py:562) e a tabela nasce sem a constraint, então a migração 262
    (migrations.py:5234) instala `CREATE UNIQUE INDEX IF NOT EXISTS` com aquele
    nome. Contra índice, `DROP CONSTRAINT` é no-op silencioso — a unicidade
    global sobrevivia e a ciência do 2º responsável estourava IntegrityError.

    Não dá para reproduzir na `rdo_assinatura` real deste banco: ele já tem
    RDOs com duas assinaturas de cliente (a feature funciona aqui, porque este
    banco veio pelo caminho da constraint), então recriar o índice global
    falharia no setup. A tabela de rascunho isola exatamente a mecânica.
    """
    with app.app_context():
        with db.engine.begin() as c:
            c.execute(db.text('DROP TABLE IF EXISTS _t269'))
            c.execute(db.text('CREATE TABLE _t269 (id serial primary key, a int, b text)'))
            c.execute(db.text('CREATE UNIQUE INDEX uq_t269 ON _t269 (a, b)'))

            # O que a 268 fazia:
            c.execute(db.text('ALTER TABLE _t269 DROP CONSTRAINT IF EXISTS uq_t269'))
            apos_constraint = c.execute(db.text(
                "SELECT count(*) FROM pg_class WHERE relname='uq_t269'")).scalar()

            # O que a 269 acrescenta:
            c.execute(db.text('DROP INDEX IF EXISTS uq_t269'))
            apos_indice = c.execute(db.text(
                "SELECT count(*) FROM pg_class WHERE relname='uq_t269'")).scalar()
            c.execute(db.text('DROP TABLE _t269'))

    assert apos_constraint == 1, 'DROP CONSTRAINT removeu o índice — premissa da 268 seria válida'
    assert apos_indice == 0, 'DROP INDEX deveria remover'


def test_migracao_269_deixa_a_tabela_no_estado_alvo_e_e_idempotente():
    """Pós-condição na tabela REAL: o nome antigo não existe sob forma
    nenhuma e os dois índices parciais estão de pé. Rodar duas vezes não
    muda nada — migração tem de poder repetir."""
    from migrations import _migration_269_remover_indice_unico_antigo_de_assinatura as m269

    with app.app_context():
        for _ in range(2):
            m269()
        with db.engine.begin() as c:
            antigo = c.execute(db.text(
                "SELECT count(*) FROM pg_class "
                "WHERE relname='uq_rdo_assinatura_papel'")).scalar()
            idx = {r[0] for r in c.execute(db.text(
                "SELECT indexname FROM pg_indexes WHERE tablename='rdo_assinatura'"))}

    assert antigo == 0
    assert 'uq_rdo_assin_papel_interno' in idx
    assert 'uq_rdo_assin_cliente' in idx


def test_migracao_269_esta_registrada_no_executor():
    """Uma migração que existe mas não está na lista nunca roda."""
    import inspect

    import migrations
    fonte = inspect.getsource(migrations.executar_migracoes)
    assert '_migration_269_remover_indice_unico_antigo_de_assinatura' in fonte
    assert '(269,' in fonte


def test_rate_limit_nao_e_contornavel_variando_a_grafia_do_id():
    """`autenticar` normaliza com `int()`, então '5', '05' e ' 5' são a MESMA
    conta — e precisam cair no mesmo balde do limitador. Antes não caíam, e
    bastava variar a grafia para travar todos os responsáveis da obra."""
    from app import limiter

    ctx = _cenario(n_signatarios=2)
    alvo = ctx['sig_ids'][0]
    grafias = [str(alvo), f'0{alvo}', f'00{alvo}', f' {alvo}', f'+{alvo}',
               f'{alvo} ']

    limiter.enabled = True
    limiter.reset()
    try:
        c = app.test_client()
        codigos = []
        for g in grafias:
            r = c.post(_url(ctx, '/ciencia'),
                       data={'signatario_id': g, 'senha': 'errada'})
            codigos.append(r.status_code)
        assert 429 in codigos, (
            f'nenhuma grafia bateu no limite: {list(zip(grafias, codigos))}')
    finally:
        limiter.enabled = False
        limiter.reset()

    # E a trava por conta não foi atingida pelo caminho contornável: com o
    # limite valendo, as tentativas param antes de MAX_FALHAS.
    assert _sig(alvo).falhas_login < ObraSignatarioCliente.MAX_FALHAS


def test_gerar_senha_nova_invalida_a_credencial_antiga_imediatamente():
    """O cliente liga dizendo que a senha vazou; a construtora gera outra.
    Sem sessão não há mais nada para "revogar" — o corte é a própria
    credencial: o intruso com a senha antiga não assina mais NADA a partir do
    POST seguinte."""
    ctx = _cenario(n_signatarios=1)
    extra = _rdos_extras(ctx, n=1)[0]

    intruso = app.test_client()
    _assinar(intruso, ctx)                # com a senha vazada, ainda vale
    assert len(_assinaturas(ctx['rdo_id'])) == 1

    # Construtora gera senha nova pela tela da obra.
    admin = _client_admin(ctx['admin_id'])
    import re as _re
    html = admin.get(f"/obras/editar/{ctx['obra_id']}").get_data(as_text=True)
    tok = _re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)
    admin.post(f"/obras/{ctx['obra_id']}/signatarios/{ctx['sig_ids'][0]}/senha",
               data={'csrf_token': tok})

    # A senha antiga morreu na hora — o próximo RDO não sai.
    _assinar(intruso, ctx, rdo_id=extra)
    assert _assinaturas(extra) == []


def test_trocar_a_propria_senha_e_assinar_em_seguida_funciona():
    """Contrapeso: quem troca a própria senha não pode ficar pior do que
    estava. O redirect volta ao ato com o nome já escolhido, e a senha nova
    assina."""
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    r = c.post(_url(ctx, '/ciencia/senha'),
               data={'signatario_id': ctx['sig_ids'][0],
                     'senha_atual': ctx['senha'],
                     'nova_senha': 'NovaSenha!2026',
                     'confirma_senha': 'NovaSenha!2026'})
    assert r.status_code == 302
    destino = r.headers.get('Location', '')
    assert '/ciencia' in destino and f"quem={ctx['sig_ids'][0]}" in destino

    _assinar(c, ctx, senha='NovaSenha!2026')
    assert len(_assinaturas(ctx['rdo_id'])) == 1


def test_senha_errada_nao_revela_conta_travada_nem_senha_vencida():
    """O dropdown de nomes é público. Se o motivo real vier antes da
    conferência do hash, qualquer um mapeia quais responsáveis estão travados
    e quais têm senha da construtora não reivindicada — as contas que valem
    atacar."""
    from services.portal_signatario_auth import (AutenticacaoInvalida,
                                                 autenticar,
                                                 gerar_senha_temporaria)

    ctx = _cenario(n_signatarios=2)
    travado, vencido = ctx['sig_ids']

    with app.app_context():
        s = db.session.get(ObraSignatarioCliente, travado)
        s.falhas_login = ObraSignatarioCliente.MAX_FALHAS
        v = db.session.get(ObraSignatarioCliente, vencido)
        senha_temp = gerar_senha_temporaria(v)
        v.senha_expira_em = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

        obra = db.session.get(Obra, ctx['obra_id'])

        # Senha ERRADA: mensagem genérica nos dois casos.
        for sid in (travado, vencido):
            with pytest.raises(AutenticacaoInvalida) as e:
                autenticar(obra, sid, 'chute-errado')
            assert str(e.value) == 'Nome ou senha inválidos.', str(e.value)

        # Senha CERTA: aí sim o dono descobre o motivo real.
        with pytest.raises(AutenticacaoInvalida) as e:
            autenticar(obra, travado, ctx['senha'])
        assert 'bloqueado' in str(e.value)

        with pytest.raises(AutenticacaoInvalida) as e:
            autenticar(obra, vencido, senha_temp)
        assert 'venceu' in str(e.value)


def test_ciencia_duplicada_pelo_indice_vira_comprovante_e_nao_500():
    """`ja_assinou` não é atômica: em duplo-toque os dois POSTs passam por ela
    antes de qualquer commit e o índice parcial barra o segundo no flush.
    Isso é IntegrityError, não CienciaInvalida — e escapava como 500 cru.

    Simula a corrida fazendo a checagem mentir nas DUAS leituras que o
    caminho novo faz (a da view e a de `registrar_ciencia`), gravando a
    assinatura concorrente na primeira — que é o efeito observável do outro
    request vencendo a corrida.
    """
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()

    import services.rdo_ciencia_cliente as mod
    real = mod.ja_assinou
    estado = {'mentiras': 2}

    def _mente(rdo, signatario):
        if estado['mentiras'] > 0:
            estado['mentiras'] -= 1
            if estado['mentiras'] == 1:      # 1ª leitura: o rival grava
                with app.app_context():
                    db.session.add(RDOAssinatura(
                        rdo_id=rdo.id, admin_id=ctx['admin_id'],
                        signatario_cliente_id=signatario.id,
                        papel=RDOAssinatura.PAPEL_CLIENTE,
                        nome_signatario='Corrida', hash_conteudo='z' * 64))
                    db.session.commit()
            return False          # mente: diz que ainda não assinou
        return real(rdo, signatario)

    mod.ja_assinou = _mente
    try:
        r = _assinar(c, ctx)
    finally:
        mod.ja_assinou = real

    assert r.status_code == 302, f'virou {r.status_code} (500 = não tratado)'
    # O banco decidiu certo, e o destino é o comprovante do ato que existe.
    assert '/ciencia/comprovante' in r.headers.get('Location', '')
    assert len(_assinaturas(ctx['rdo_id'])) == 1

    # E a sessão do banco não ficou suja: a próxima operação funciona.
    assert c.get(_url(ctx)).status_code == 200


def test_senha_temporaria_nunca_aparece_na_url():
    """A senha em claro na query string vazava por três canais que ninguém
    controla depois: histórico do navegador, log de acesso do proxy e header
    Referer. O desenho de `gerar_senha_temporaria` — mostrar UMA vez porque
    depois não há como recuperar — ficava sem efeito."""
    ctx = _cenario(n_signatarios=1)
    c = _client_admin(ctx['admin_id'])

    r = c.post(f"/obras/{ctx['obra_id']}/signatarios",
               data={'nome': 'Novo Responsável', 'cargo': 'Eng.'})
    assert r.status_code == 302
    destino = r.headers.get('Location', '')
    assert 'senha_gerada' not in destino, f'senha na URL: {destino}'
    assert 'senha_para' not in destino
    assert '?' not in destino, f'querystring inesperada: {destino}'

    # Mas a tela seguinte MOSTRA a senha — vinda da sessão.
    html = c.get(f"/obras/editar/{ctx['obra_id']}").get_data(as_text=True)
    assert 'Novo Responsável' in html
    import re as _re
    m = _re.search(r'id="senhaGerada"\s+value="([^"]+)"', html)
    assert m, 'a senha não chegou à tela pela sessão'
    senha = m.group(1)
    assert len(senha) == 10

    # E some depois: um F5 não a mostra de novo.
    html2 = c.get(f"/obras/editar/{ctx['obra_id']}").get_data(as_text=True)
    assert senha not in html2, 'senha persistiu entre renderizações'


def test_regerar_senha_tambem_nao_usa_a_url():
    ctx = _cenario(n_signatarios=1)
    c = _client_admin(ctx['admin_id'])
    r = c.post(f"/obras/{ctx['obra_id']}/signatarios/{ctx['sig_ids'][0]}/senha",
               data={})
    assert 'senha_gerada' not in r.headers.get('Location', '')
    html = c.get(f"/obras/editar/{ctx['obra_id']}").get_data(as_text=True)
    assert 'id="senhaGerada"' in html


def test_ip_da_ciencia_nao_aceita_x_forwarded_for_forjado():
    """O IP é campo probatório: se o próprio assinante puder escolhê-lo, não
    prova nada. `ProxyFix(x_for=1)` (app.py:94) já resolve o IP real em
    `remote_addr`; ler o header à mão pegava o primeiro salto, que é o que o
    cliente digita."""
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()

    # O cliente manda a cadeia com um IP inventado à ESQUERDA. Num request
    # real, o proxy confiável APENDA o IP que ele observou, à direita — e é
    # esse que `ProxyFix(x_for=1)` promove a `remote_addr`. Tudo à esquerda é
    # texto que o próprio requisitante escreveu.
    _assinar(c, ctx, headers={'X-Forwarded-For': '8.8.8.8, 198.51.100.4'})

    a = _assinaturas(ctx['rdo_id'])[0]
    assert a.ip != '8.8.8.8', 'gravou o salto forjável (leitura à esquerda)'
    assert a.ip == '198.51.100.4', (
        f'esperado o salto do proxy confiável, veio {a.ip}')


# ---------------------------------------------------------------------------
# Comprovante e recibo — redesenho de 29/07 (spec §§3-4, D3)
# ---------------------------------------------------------------------------

def test_comprovante_mostra_o_registro_para_quem_acabou_de_assinar():
    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    r = _assinar(c, ctx, observacao='Conferido em campo.',
                 environ_overrides={'REMOTE_ADDR': '203.0.113.9'})

    html = c.get(r.headers['Location']).get_data(as_text=True)
    assert 'Ciência registrada' in html
    assert _sig(ctx['sig_ids'][0]).nome in html
    assert '203.0.113.9' in html                  # o IP é da própria pessoa
    assert 'Conferido em campo.' in html
    assert 'Baixar recibo' in html


def test_comprovante_sem_marca_nao_revela_nome_ip_nem_hash():
    """Quem só tem o link da obra não vê o comprovante — ele carrega o IP,
    que o placar público não expõe (D3)."""
    ctx = _cenario(n_signatarios=1)
    dono = app.test_client()
    _assinar(dono, ctx, environ_overrides={'REMOTE_ADDR': '203.0.113.9'})

    curioso = app.test_client()                   # outro navegador, sem marca
    r = curioso.get(_url(ctx, '/ciencia/comprovante'))
    assert r.status_code == 302                   # devolvido à leitura
    r2 = curioso.get(_url(ctx, '/ciencia/recibo.pdf'))
    assert r2.status_code == 302
    assert '203.0.113.9' not in r.get_data(as_text=True)


def test_marca_de_um_rdo_nao_abre_comprovante_de_outro():
    """A marca aponta UMA assinatura; o token e o rdo da URL continuam
    mandando. Sem esta guarda, assinar o RDO de hoje abriria o comprovante
    de qualquer outro documento."""
    ctx = _cenario(n_signatarios=1)
    extra = _rdos_extras(ctx, n=1)[0]
    c = app.test_client()
    _assinar(c, ctx, environ_overrides={'REMOTE_ADDR': '203.0.113.9'})

    r = c.get(f"/portal/obra/{ctx['token']}/rdo/{extra}/ciencia/comprovante")
    assert r.status_code == 302, 'marca de um RDO abriu comprovante de outro'


def test_recibo_pdf_sai_valido_com_nome_e_hash_completo():
    """O recibo existe para provar: o hash sai COMPLETO, não abreviado como
    na tela (spec §4)."""
    from io import BytesIO

    from pypdf import PdfReader

    ctx = _cenario(n_signatarios=1)
    c = app.test_client()
    r = _assinar(c, ctx, environ_overrides={'REMOTE_ADDR': '203.0.113.9'})
    assert r.status_code == 302

    pdf = c.get(_url(ctx, '/ciencia/recibo.pdf'))
    assert pdf.status_code == 200
    assert pdf.data[:5] == b'%PDF-'
    assert pdf.headers['Cache-Control'] == 'no-store'

    texto = '\n'.join((p.extract_text() or '')
                      for p in PdfReader(BytesIO(pdf.data)).pages)
    a = _assinaturas(ctx['rdo_id'])[0]
    assert _sig(ctx['sig_ids'][0]).nome in texto
    assert '203.0.113.9' in texto
    # O extrator pode quebrar linha no meio do hash — compara sem espaços.
    assert a.hash_conteudo in texto.replace('\n', '').replace(' ', '')


# ---------------------------------------------------------------------------
# O convite, num lugar só — lado da construtora (spec D4, Step F)
# ---------------------------------------------------------------------------

def test_detalhes_da_obra_mostram_responsaveis_e_cobranca_com_link_direto():
    """A tela de DETALHES (não a de edição) lista quem assina e oferece a
    cobrança com link direto para o RDO pendente — é o link que apaga duas
    telas do percurso do cliente."""
    ctx = _cenario(n_signatarios=2)
    c = _client_admin(ctx['admin_id'])

    html = c.get(f"/obras/{ctx['obra_id']}").get_data(as_text=True)
    assert 'Quem assina os RDOs' in html
    for sid in ctx['sig_ids']:
        assert _sig(sid).nome in html
    # Os dois têm RDO pendente: o botão de cobrar carrega o link DIRETO.
    assert html.count(f"/portal/obra/{ctx['token']}/rdo/{ctx['rdo_id']}") >= 2
    assert 'Cobrar' in html

    # Um assina; para ele a cobrança dá lugar ao "em dia".
    cliente = app.test_client()
    _assinar(cliente, ctx, ctx['sig_ids'][0])
    html = c.get(f"/obras/{ctx['obra_id']}").get_data(as_text=True)
    assert 'em dia' in html
    assert html.count(f"/portal/obra/{ctx['token']}/rdo/{ctx['rdo_id']}") == 1


def test_convite_nasce_na_tela_de_detalhes_com_mensagem_inteira():
    """Gerar a senha pelo bloco do convite volta para DETALHES e entrega a
    mensagem pronta — link e senha juntos, uma vez só."""
    import re as _re

    ctx = _cenario(n_signatarios=1)
    c = _client_admin(ctx['admin_id'])

    r = c.post(f"/obras/{ctx['obra_id']}/signatarios/{ctx['sig_ids'][0]}/senha",
               data={'voltar': 'detalhes'})
    assert r.status_code == 302
    destino = r.headers.get('Location', '')
    assert '/obras/' in destino and 'editar' not in destino
    assert 'senha_gerada' not in destino          # a senha nunca viaja na URL

    html = c.get(f"/obras/{ctx['obra_id']}").get_data(as_text=True)
    assert 'Convite pronto para' in html
    m = _re.search(r'Sua senha temporária: (\S+)', html)
    assert m, 'a mensagem do convite não trouxe a senha'
    assert len(m.group(1)) == 10
    # A mensagem carrega o link do portal — as duas metades juntas.
    assert f"portal/obra/{ctx['token']}" in html

    # E some no F5: a senha aparece UMA vez.
    html2 = c.get(f"/obras/{ctx['obra_id']}").get_data(as_text=True)
    assert m.group(1) not in html2
    assert 'Convite pronto para' not in html2
