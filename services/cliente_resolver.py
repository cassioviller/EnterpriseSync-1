"""Task #172 — Helper para resolver/criar Cliente a partir de texto livre.

Centraliza a lógica de "obter ou criar Cliente" para que todos os pontos
que hoje guardam apenas o nome/e-mail/telefone do cliente como texto
(criação manual de Obra, edição, importação, aprovação de Proposta) passem
a apontar para o cadastro real via FK.

Política CONSERVADORA de deduplicação (por tenant `admin_id`),
desenhada para nunca mesclar pessoas distintas que compartilham nome:

  1. `cliente_id` explícito vence sempre (id pertence ao tenant).
  2. Match estrito por NOME + E-MAIL (case-insensitive, trim) — só quando
     ambos os lados têm os dois campos.
  3. Match por E-MAIL único (case-insensitive) — quando o e-mail informado
     bate com EXATAMENTE 1 Cliente do tenant.
  4. Match por NOME único — apenas quando:
       - o input NÃO traz e-mail; E
       - o Cliente candidato tem `email IS NULL`; E
       - existe EXATAMENTE 1 Cliente do tenant com esse nome (case-insensitive).
     Isso evita mesclar homônimos quando um deles tem e-mail cadastrado.
  5. Caso nada bata, cria um novo Cliente.

A função NUNCA commita por conta própria — o chamador é dono da transação.
Faz `db.session.flush()` apenas quando precisa do `id` do Cliente recém criado.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func

from app import db
from models import Cliente

logger = logging.getLogger(__name__)


def _norm(valor: Optional[str]) -> str:
    if valor is None:
        return ''
    return str(valor).strip()


def obter_ou_criar_cliente(
    admin_id: int,
    nome: Optional[str],
    email: Optional[str] = None,
    telefone: Optional[str] = None,
    cliente_id: Optional[int] = None,
) -> Optional[Cliente]:
    """Resolve (ou cria) um Cliente para o tenant `admin_id`.

    Retorna o objeto Cliente já com `id` populado, ou None quando não há
    informação suficiente (sem nome e sem e-mail).
    """
    if not admin_id:
        return None

    # 1. cliente_id explícito vence sempre.
    if cliente_id:
        cli = Cliente.query.filter_by(id=cliente_id, admin_id=admin_id).first()
        if cli:
            return cli

    nome_n = _norm(nome)
    email_n = _norm(email)
    telefone_n = _norm(telefone)

    if not nome_n and not email_n:
        # Sem nada que identifique — não dá para criar/encontrar com segurança.
        return None

    base_q = Cliente.query.filter(Cliente.admin_id == admin_id)
    nome_lower = nome_n.lower() if nome_n else None
    email_lower = email_n.lower() if email_n else None

    # 2. Match ESTRITO por nome + e-mail (ambos presentes dos dois lados).
    if nome_n and email_n:
        cli = (
            base_q
            .filter(func.lower(func.trim(Cliente.nome)) == nome_lower)
            .filter(func.lower(Cliente.email) == email_lower)
            .first()
        )
        if cli:
            if not cli.telefone and telefone_n:
                cli.telefone = telefone_n[:20]
            return cli

    # 3. Match por e-mail único no tenant.
    if email_n:
        candidatos_email = (
            base_q
            .filter(func.lower(Cliente.email) == email_lower)
            .limit(2)
            .all()
        )
        if len(candidatos_email) == 1:
            cli = candidatos_email[0]
            # Atualiza campos vazios oportunisticamente (sem sobrescrever).
            if not cli.nome and nome_n:
                cli.nome = nome_n[:200]
            if not cli.telefone and telefone_n:
                cli.telefone = telefone_n[:20]
            return cli
        # Se há ambiguidade (>1 com mesmo e-mail) ou nenhum, cai pro próximo passo.

    # 4. Match por nome único — APENAS quando o input não tem e-mail
    #    E o cliente candidato também tem email IS NULL (evita mesclar
    #    homônimos onde um já tem identidade por e-mail).
    if nome_n and not email_n:
        candidatos_nome = (
            base_q
            .filter(func.lower(func.trim(Cliente.nome)) == nome_lower)
            .filter(Cliente.email.is_(None))
            .limit(2)
            .all()
        )
        if len(candidatos_nome) == 1:
            cli = candidatos_nome[0]
            if not cli.telefone and telefone_n:
                cli.telefone = telefone_n[:20]
            return cli
        # Ambíguo (>1) ou todos os homônimos têm e-mail → cria novo.

    # 5. Nada encontrado com segurança — cria.
    novo = Cliente(
        nome=(nome_n or email_n)[:200],
        email=email_n[:120] if email_n else None,
        telefone=telefone_n[:20] if telefone_n else None,
        admin_id=admin_id,
    )
    db.session.add(novo)
    db.session.flush()
    logger.info(
        "[Task #172] Cliente criado automaticamente id=%s nome=%r admin_id=%s",
        novo.id, novo.nome, admin_id,
    )
    return novo
