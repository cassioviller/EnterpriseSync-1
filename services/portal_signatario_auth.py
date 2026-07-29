#!/usr/bin/env python3
"""Autenticação do responsável do cliente no portal — SIGE Fase 9a.

O portal da obra é ANÔNIMO por construção (`portal_obras_views.py:3`): quem
tem o link `/portal/obra/<token>` navega sem login. Este módulo NÃO muda
isso. Ele existe para o único ato em que identidade tem consequência: dar
ciência num RDO.

Por que sessão própria e não Flask-Login: `login_manager.user_loader`
carrega `Usuario` (app.py:521), e toda a autorização interna parte daí.
Autenticar um signatário de cliente pelo mesmo mecanismo colocaria uma
pessoa de fora dentro do mesmo espaço de identidade do sistema — a um bug
de distância de enxergar o resto. A sessão daqui vive numa chave própria e
é validada contra a obra do token em toda ação.

A sessão é curta e presa a UMA obra:

    session['portal_sig'] = {'sid': <id>, 'obra_id': <id>, 'exp': <iso>}

15 minutos de INATIVIDADE (renovados a cada ação), para o responsável que
sumiu uma semana assinar os RDOs atrasados em sequência sem redigitar a
senha a cada um — sem virar um login persistente, que é justamente o que o
cliente não quis.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from models import ObraSignatarioCliente, db

logger = logging.getLogger('portal.signatario')

# Inatividade tolerada antes de pedir a senha de novo.
MINUTOS_SESSAO = 15
# Teto absoluto desde o login, independente de atividade. A janela de
# inatividade se renova a cada page view; sem este teto, uma aba deixada
# aberta (ou sequestrada) mantém a sessão viva indefinidamente.
HORAS_SESSAO_MAXIMA = 12
CHAVE_SESSAO = 'portal_sig'

# Alfabeto da senha temporária: sem 0/O/1/l/I, que viram erro de digitação
# quando alguém dita a senha por telefone — e ditar por telefone é
# exatamente o canal previsto (não há SMTP configurado no sistema).
_ALFABETO_SENHA = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'

SENHA_MIN = 8


class AutenticacaoInvalida(Exception):
    """Recusa de login, com mensagem apta à UI."""


class SessaoInvalida(Exception):
    """Sessão ausente, expirada ou de outra obra."""


# ─────────────────────────────────────────────────────────────────────────────
# Senha
# ─────────────────────────────────────────────────────────────────────────────

def gerar_senha_temporaria(signatario, *, tamanho: int = 10) -> str:
    """Sorteia uma senha, grava só o HASH e devolve a senha em claro.

    O retorno é a ÚNICA vez que a senha existe legível — quem chama mostra
    na tela e a construtora entrega pelo canal que já usa. Não há como
    recuperá-la depois, por construção.

    Limpa a trava e o pedido de recuperação: gerar senha nova é exatamente a
    resposta ao "esqueci"/"travei".
    """
    senha = ''.join(secrets.choice(_ALFABETO_SENHA) for _ in range(tamanho))
    signatario.password_hash = generate_password_hash(senha)
    signatario.senha_temporaria = True
    signatario.senha_expira_em = datetime.utcnow() + timedelta(
        hours=ObraSignatarioCliente.HORAS_SENHA_TEMPORARIA)
    signatario.falhas_login = 0
    signatario.recuperacao_pedida_em = None
    logger.info('[signatario] senha temporária gerada — signatario=%s obra=%s',
                signatario.id, signatario.obra_id)
    return senha


def definir_senha(signatario, senha: str) -> None:
    """Troca definitiva, feita pelo próprio responsável.

    Sai do regime temporário: `senha_temporaria=False` e sem validade. É o
    que destrava as rotas de assinatura para ele.
    """
    senha = (senha or '').strip()
    if len(senha) < SENHA_MIN:
        raise AutenticacaoInvalida(
            f'A senha precisa ter pelo menos {SENHA_MIN} caracteres.')
    signatario.password_hash = generate_password_hash(senha)
    signatario.senha_temporaria = False
    signatario.senha_expira_em = None
    signatario.falhas_login = 0
    logger.info('[signatario] senha redefinida pelo próprio — signatario=%s',
                signatario.id)


def pedir_recuperacao(signatario) -> None:
    """Marca o "esqueci minha senha" para a construtora ver na tela da obra.

    Não envia nada: não existe SMTP no sistema (só o canal n8n, opt-in por
    `N8N_WEBHOOK_URL`). O pedido vira pendência e a construtora gera a senha
    temporária. Idempotente de propósito — clicar de novo não empilha
    pedidos, só atualiza o carimbo.
    """
    signatario.recuperacao_pedida_em = datetime.utcnow()
    logger.info('[signatario] recuperação pedida — signatario=%s obra=%s',
                signatario.id, signatario.obra_id)


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

def signatarios_da_obra(obra_id: int, *, apenas_ativos: bool = True) -> list:
    """Lista para o seletor de "quem é você" e para o placar de assinaturas."""
    q = ObraSignatarioCliente.query.filter_by(obra_id=obra_id)
    if apenas_ativos:
        q = q.filter(ObraSignatarioCliente.ativo.is_(True))
    return q.order_by(ObraSignatarioCliente.nome).all()


def autenticar(obra, signatario_id, senha: str):
    """Confere a senha e devolve o signatário. Não faz commit.

    Levanta `AutenticacaoInvalida` com mensagem GENÉRICA em toda recusa de
    credencial: quem está tentando adivinhar não descobre por aqui se o nome
    existe, se está inativo ou se a senha é que estava errada.

    ORDEM IMPORTA, e a primeira versão errou nela. Trava e senha temporária
    vencida eram reportadas ANTES da conferência do hash, com a justificativa
    de que "o atacante já teria acertado a senha para chegar lá" — o que
    simplesmente não era verdade, porque a checagem vinha antes. O dropdown
    `#cienciaQuem` do portal é público: bastava percorrer os nomes com senha
    qualquer para mapear quais responsáveis estão travados e quais estão
    sentados sobre uma senha da construtora ainda não reivindicada — ou seja,
    exatamente as contas que valem atacar.

    Agora a senha é conferida PRIMEIRO. Só quem prova conhecê-la recebe a
    explicação de por que ainda assim não entrou — aí sim a frase original
    vale, e o dono da conta entende o que fazer sem abrir chamado.
    """
    generica = AutenticacaoInvalida('Nome ou senha inválidos.')

    try:
        sid = int(signatario_id)
    except (TypeError, ValueError):
        raise generica

    signatario = ObraSignatarioCliente.query.filter_by(
        id=sid, obra_id=obra.id).first()
    if signatario is None or not signatario.ativo or not signatario.password_hash:
        raise generica

    if not check_password_hash(signatario.password_hash, senha or ''):
        signatario.falhas_login = (signatario.falhas_login or 0) + 1
        logger.warning('[signatario] senha errada — signatario=%s obra=%s '
                       'falhas=%s', signatario.id, obra.id,
                       signatario.falhas_login)
        raise generica

    # Senha CORRETA daqui para baixo — só então o motivo real é revelado.
    if signatario.travado:
        raise AutenticacaoInvalida(
            'Este acesso foi bloqueado por tentativas seguidas. Use '
            '"Esqueci minha senha" para que a construtora libere uma nova.')

    if signatario.senha_expirada:
        raise AutenticacaoInvalida(
            'A senha temporária venceu. Use "Esqueci minha senha" para pedir '
            'outra à construtora.')

    signatario.falhas_login = 0
    signatario.ultimo_acesso_em = datetime.utcnow()
    logger.info('[signatario] autenticado — signatario=%s obra=%s',
                signatario.id, obra.id)
    return signatario


# ─────────────────────────────────────────────────────────────────────────────
# Sessão
# ─────────────────────────────────────────────────────────────────────────────

def _impressao_credencial(signatario) -> str:
    """Marca curta e irreversível do hash de senha vigente.

    É o que permite REVOGAR uma sessão trocando a senha. A sessão é um dict
    autocontido no cookie (`{sid, obra_id, exp}`); sem esta marca, gerar senha
    nova pela tela da obra trocava o `password_hash` e **não derrubava** quem
    já estava dentro — exatamente o contrário do que a construtora acredita
    estar fazendo quando o cliente liga dizendo que a senha vazou.

    Deriva do hash, nunca da senha, e é truncada: não reintroduz o material
    da credencial dentro do cookie.
    """
    import hashlib
    base = (signatario.password_hash or '').encode('utf-8')
    return hashlib.sha256(base).hexdigest()[:16]


def abrir_sessao(signatario, *, inicio=None) -> None:
    """Abre (ou renova) a sessão do signatário.

    `inicio` preserva o instante do login original através das renovações —
    é o que sustenta o teto absoluto de `HORAS_SESSAO_MAXIMA`.
    """
    from flask import session
    agora = datetime.utcnow()
    session[CHAVE_SESSAO] = {
        'sid': signatario.id,
        'obra_id': signatario.obra_id,
        'exp': (agora + timedelta(minutes=MINUTOS_SESSAO)).isoformat(),
        # Teto absoluto: sem ele, a janela de inatividade se renova a cada
        # page view e uma aba deixada aberta mantém a sessão viva para sempre.
        'ini': (inicio or agora).isoformat(),
        'cred': _impressao_credencial(signatario),
    }
    session.modified = True


def fechar_sessao() -> None:
    from flask import session
    session.pop(CHAVE_SESSAO, None)
    session.modified = True


def sessao_atual(obra):
    """Signatário logado PARA ESTA OBRA, ou None.

    Devolve None (em vez de levantar) porque a maioria dos chamadores é
    renderização: sem sessão, a tela mostra o formulário de login. Renova a
    validade a cada consulta — é o que faz a janela ser de INATIVIDADE.

    Uma sessão de outra obra é tratada como ausente, não como erro: o mesmo
    navegador pode ter aberto duas obras, e a segunda simplesmente pede
    senha.
    """
    from flask import session

    dados = session.get(CHAVE_SESSAO)
    if not isinstance(dados, dict):
        return None
    if dados.get('obra_id') != obra.id:
        return None

    agora = datetime.utcnow()
    try:
        if datetime.fromisoformat(dados['exp']) < agora:
            fechar_sessao()
            return None
        # Teto absoluto desde o login. A janela de inatividade sozinha nunca
        # expira numa aba que fica sendo usada — e uma sessão sequestrada
        # sobreviveria indefinidamente por isso.
        inicio = datetime.fromisoformat(dados['ini'])
        if agora - inicio > timedelta(hours=HORAS_SESSAO_MAXIMA):
            fechar_sessao()
            return None
    except (KeyError, TypeError, ValueError):
        # Sessão de formato antigo ou corrompida: derruba. Custa um login.
        fechar_sessao()
        return None

    signatario = ObraSignatarioCliente.query.filter_by(
        id=dados.get('sid'), obra_id=obra.id).first()
    # Desativado no meio da sessão perde o acesso na ação seguinte.
    if signatario is None or not signatario.ativo:
        fechar_sessao()
        return None

    # REVOGAÇÃO por troca de senha: a construtora gerar uma senha temporária
    # (ou o próprio responsável trocar a dele) invalida toda sessão aberta com
    # a credencial anterior. Sem esta comparação, "gerar senha nova" não
    # expulsava o intruso — só dava a ele mais uma senha para ignorar.
    if dados.get('cred') != _impressao_credencial(signatario):
        logger.info('[signatario] sessão revogada por troca de credencial — '
                    'signatario=%s obra=%s', signatario.id, obra.id)
        fechar_sessao()
        return None

    # Renova a janela de inatividade PRESERVANDO o início, senão o teto
    # absoluto se moveria junto e não seria teto nenhum.
    abrir_sessao(signatario, inicio=inicio)
    return signatario


def exigir_sessao(obra):
    """Igual a `sessao_atual`, mas levanta — para as rotas que MUTAM."""
    signatario = sessao_atual(obra)
    if signatario is None:
        raise SessaoInvalida(
            'Sua sessão expirou. Informe a senha novamente para assinar.')
    return signatario
