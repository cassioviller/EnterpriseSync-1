#!/usr/bin/env python3
"""Credencial do responsável do cliente no portal — SIGE Fase 9a.

O portal da obra é ANÔNIMO por construção (`portal_obras_views.py:3`): quem
tem o link `/portal/obra/<token>` navega sem login. Este módulo NÃO muda
isso. Ele existe para o único ato em que identidade tem consequência: dar
ciência num RDO.

NÃO HÁ SESSÃO — e já houve. A primeira versão mantinha um login próprio no
cookie (15 min de inatividade, teto de 12 h, impressão da credencial para
poder revogar). O redesenho de 29/07 (spec
`docs/superpowers/specs/2026-07-29-ciencia-rdo-portal-ux-design.md`, D1)
removeu tudo isso: a senha é conferida no MESMO POST que grava a ciência.
O uso real é diário e de um RDO por vez, então o custo digitado é idêntico
— e a assinatura passa a repousar sobre a credencial, não sobre um cookie.
A máquina de revogação foi junto: ela existia só para consertar um problema
que a própria sessão criava (achado 5 da revisão de 29/07).

Se o ritmo real um dia virar "vários RDOs numa sentada", o caminho é
assinar em LOTE (um POST, uma senha, N RDOs) — não ressuscitar a sessão.
O spec §7 registra essa decisão de propósito.

Este módulo é, portanto, só credencial: gerar/definir/conferir senha e
listar quem assina. Quem orquestra o ato é `portal_obras_views`.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from models import ObraSignatarioCliente, db

logger = logging.getLogger('portal.signatario')

# Alfabeto da senha temporária: sem 0/O/1/l/I, que viram erro de digitação
# quando alguém dita a senha por telefone — e ditar por telefone é
# exatamente o canal previsto (não há SMTP configurado no sistema).
_ALFABETO_SENHA = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'

SENHA_MIN = 8


class AutenticacaoInvalida(Exception):
    """Recusa de credencial, com mensagem apta à UI."""


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
