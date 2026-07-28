#!/usr/bin/env python3
"""Assinatura e aprovação de RDO — SIGE Fase 5.

Concentra as operações que mudam o estado terminal do RDO:
`assinar` e `aprovar` (o retificador entra na Task 9). A AUTORIZAÇÃO
fica na rota (utils/autorizacao.py, Fase 1); aqui mora a regra de
negócio e a gravação da evidência.

Identidade: SEMPRE por `utils.identidade.funcionario_do_usuario()`. Antes
da Fase 1 este módulo teria que adivinhar quem é a pessoa — por e-mail
sem `admin_id`, por substring de nome, e no último fallback CRIANDO um
`Funcionario` chamado "Administrador Sistema" (heurística removida na
Fase 1; só o comentário histórico sobrevive em views/rdo.py:2560-2575).
Assinatura em cima de palpite não é assinatura; por isso, sem vínculo,
este módulo se recusa a assinar.
"""
from __future__ import annotations

import logging

from models import RDOAssinatura, db
from services.rdo_ciclo_vida import (APROVADO, ASSINADO, CicloVidaInvalido,
                                     PREENCHIDO, estado_de, transicionar)
from services.rdo_hash import calcular_hash

logger = logging.getLogger('rdo.assinatura')


class AssinaturaInvalida(CicloVidaInvalido):
    """Mensagem apta à UI para recusa de assinatura."""


class SemIdentidade(AssinaturaInvalida):
    """Usuário sem `Usuario.funcionario_id` — não há autoria a registrar."""


def _contexto_request():
    """(ip, user_agent) do request atual, ou (None, None) fora de request."""
    try:
        from flask import request
        return (request.remote_addr,
                (request.headers.get('User-Agent') or '')[:400] or None)
    except Exception:
        return None, None


def assinar(rdo, usuario, *, papel=RDOAssinatura.PAPEL_EXECUTOR,
            observacao=None):
    """Registra a assinatura e leva o RDO de `preenchido` a `assinado`.

    Não faz commit — quem chama decide a transação. Levanta
    `AssinaturaInvalida` (ou subclasse) em qualquer recusa.
    """
    from utils.identidade import funcionario_do_usuario

    if papel not in RDOAssinatura.PAPEIS:
        raise AssinaturaInvalida(f'Papel de assinatura inválido: {papel!r}')

    atual = estado_de(rdo)
    if atual != PREENCHIDO:
        raise AssinaturaInvalida(
            f'Só um RDO preenchido pode ser assinado — este está em '
            f'"{atual}". Submeta o RDO antes de assinar.')

    funcionario = funcionario_do_usuario(usuario)
    if funcionario is None:
        raise SemIdentidade(
            'Seu login não está vinculado a um cadastro de funcionário. '
            'Sem esse vínculo não é possível registrar a autoria da '
            'assinatura. Peça ao administrador para vincular seu usuário '
            '(Fase 1 — utils/identidade.py).')

    if RDOAssinatura.query.filter_by(rdo_id=rdo.id, papel=papel).first():
        raise AssinaturaInvalida(
            f'Este RDO já tem assinatura de {papel}. Para corrigir, emita '
            f'um RDO retificador.')

    ip, user_agent = _contexto_request()
    cargo = None
    funcao_ref = getattr(funcionario, 'funcao_ref', None)
    if funcao_ref is not None:
        cargo = getattr(funcao_ref, 'nome', None)
    cargo = cargo or getattr(funcionario, 'cargo', None)

    assinatura = RDOAssinatura(
        rdo_id=rdo.id,
        admin_id=rdo.admin_id or rdo.obra.admin_id,
        usuario_id=usuario.id,
        funcionario_id=funcionario.id,
        papel=papel,
        nome_signatario=(funcionario.nome or usuario.nome or
                         usuario.username)[:200],
        cargo_signatario=(cargo or '')[:120] or None,
        hash_conteudo=calcular_hash(rdo),
        algoritmo='sha256',
        provedor='interno',
        ip=ip,
        user_agent=user_agent,
        observacao=observacao,
    )
    db.session.add(assinatura)
    db.session.flush()

    transicionar(rdo, ASSINADO, usuario=usuario, funcionario=funcionario,
                 motivo=observacao, ip=ip,
                 detalhes={'assinatura_id': assinatura.id, 'papel': papel})

    logger.info('[assinatura] rdo=%s papel=%s usuario=%s funcionario=%s '
                'hash=%s ip=%s', rdo.id, papel, usuario.id, funcionario.id,
                assinatura.hash_conteudo[:12], ip)
    return assinatura


def aprovar(rdo, usuario, *, observacao=None):
    """Aceite do gestor: `assinado` → `aprovado` + assinatura de gestor.

    Não faz commit.
    """
    from utils.identidade import funcionario_do_usuario

    atual = estado_de(rdo)
    if atual != ASSINADO:
        raise AssinaturaInvalida(
            f'Só um RDO assinado pode ser aprovado — este está em '
            f'"{atual}".')

    funcionario = funcionario_do_usuario(usuario)
    ip, user_agent = _contexto_request()

    ja_existe = RDOAssinatura.query.filter_by(
        rdo_id=rdo.id, papel=RDOAssinatura.PAPEL_GESTOR).first()
    assinatura = ja_existe
    if ja_existe is None:
        assinatura = RDOAssinatura(
            rdo_id=rdo.id,
            admin_id=rdo.admin_id or rdo.obra.admin_id,
            usuario_id=usuario.id,
            funcionario_id=getattr(funcionario, 'id', None),
            papel=RDOAssinatura.PAPEL_GESTOR,
            nome_signatario=(getattr(funcionario, 'nome', None) or
                             usuario.nome or usuario.username)[:200],
            cargo_signatario='Gestor da obra',
            hash_conteudo=calcular_hash(rdo),
            algoritmo='sha256',
            provedor='interno',
            ip=ip,
            user_agent=user_agent,
            observacao=observacao,
        )
        db.session.add(assinatura)
        db.session.flush()

    transicionar(rdo, APROVADO, usuario=usuario, funcionario=funcionario,
                 motivo=observacao, ip=ip,
                 detalhes={'assinatura_id': assinatura.id,
                           'papel': RDOAssinatura.PAPEL_GESTOR})

    logger.info('[assinatura] rdo=%s APROVADO por usuario=%s ip=%s',
                rdo.id, usuario.id, ip)
    return assinatura


# Campos do cabeçalho do RDO que o retificador herda. `status` fica de
# fora porque é preenchido pelo default ('Finalizado'); `estado` fica de
# fora porque o retificador nasce em rascunho.
_CAMPOS_CABECALHO = (
    'clima_geral', 'temperatura_media', 'umidade_relativa',
    'vento_velocidade', 'precipitacao', 'condicoes_trabalho',
    'observacoes_climaticas', 'local', 'comentario_geral',
)


def criar_retificador(rdo, usuario, *, motivo):
    """Emite um RDO retificador do `rdo` e marca o original.

    O retificador nasce em `rascunho`, no MESMO dia do original, com uma
    cópia do conteúdo (cabeçalho, subatividades, mão de obra,
    equipamentos, ocorrências). Fotos e apontamentos de cronograma NÃO
    são copiados de propósito:

      * fotos custam três cópias base64 por unidade no banco —
        duplicá-las por retificação dobra o custo do problema que a
        Task 15 existe para resolver;
      * apontamentos de cronograma são acumulativos entre RDOs
        (services/cronograma_apontamento_service.py). Copiar somaria
        produção duas vezes. Quem retifica reaponta o que mudou.

    Não faz commit. Devolve o RDO novo.
    """
    from models import (RDO, RDOEquipamento, RDOMaoObra, RDOOcorrencia,
                        RDOServicoSubatividade)
    from services.rdo_ciclo_vida import (ESTADOS_IMUTAVEIS, RASCUNHO,
                                         RETIFICADO)

    motivo = (motivo or '').strip()
    if not motivo:
        raise AssinaturaInvalida(
            'Informe o motivo da retificação — ele fica no documento.')

    atual = estado_de(rdo)
    if atual not in ESTADOS_IMUTAVEIS or atual == RETIFICADO:
        raise AssinaturaInvalida(
            f'Só um RDO assinado ou aprovado pode ser retificado — este '
            f'está em "{atual}". Se ele ainda é editável, corrija-o '
            f'direto.')

    from views.rdo import _gerar_numero_rdo_unico

    admin_id = rdo.admin_id or rdo.obra.admin_id

    # O custo do RDO retificado sai ANTES de a cópia existir. O retificador
    # nasce com a mesma mão de obra e, quando for salvo, lança o custo dela
    # de novo — sem isto a mesma jornada era contada duas vezes. Medido:
    # R$ 124,00 viravam R$ 248,00 no Realizado da obra ao salvar o
    # retificador, com os dois RDOs alimentando o MESMO GestaoCustoPai.
    #
    # `remover_custos_rdo` e não `cancelar_custos_rdo`: o cancelamento é no
    # nível do PAI, e o pai é compartilhado entre os dois RDOs — cancelá-lo
    # mataria junto o custo do retificador. A remoção é por FILHO (casa por
    # `origem_tabela`/`origem_id` das linhas do original) e recalcula o total
    # do pai. É o mesmo que o fluxo de edição faz antes de regravar
    # (rdo_editar_sistema.py:357), e retificar é editar para um documento
    # novo.
    #
    # O `RDOCustoDiario` do original fica: nenhum consumidor o agrega por
    # obra (o job de cobertura ociosa procura dia SEM RDO), então removê-lo
    # seria mexer no que não foi medido. A duplicação medida está no
    # GestaoCustoFilho.
    #
    # A trilha da retificação fica em `rdo_transicao_estado`, não no
    # financeiro — o custo de um documento substituído não é histórico a
    # preservar, é lançamento a desfazer.
    from services.rdo_custos import remover_custos_rdo
    removidos = remover_custos_rdo(rdo, admin_id)
    if removidos:
        logger.info('[assinatura] rdo=%s retificado: %d lançamento(s) de '
                    'custo removido(s) antes da cópia', rdo.id, removidos)

    novo = RDO(
        obra_id=rdo.obra_id,
        data_relatorio=rdo.data_relatorio,
        admin_id=admin_id,
        criado_por_id=usuario.id,
        numero_rdo=_gerar_numero_rdo_unico(rdo.obra_id, rdo.data_relatorio,
                                           admin_id),
        estado=RASCUNHO,
        rdo_retificado_id=rdo.id,
        motivo_retificacao=motivo,
    )
    for campo in _CAMPOS_CABECALHO:
        setattr(novo, campo, getattr(rdo, campo, None))
    db.session.add(novo)
    db.session.flush()

    for sub in RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOServicoSubatividade(
            rdo_id=novo.id, admin_id=admin_id, servico_id=sub.servico_id,
            nome_subatividade=sub.nome_subatividade,
            descricao_subatividade=sub.descricao_subatividade,
            percentual_conclusao=sub.percentual_conclusao,
            percentual_anterior=sub.percentual_anterior,
            incremento_dia=sub.incremento_dia,
            observacoes_tecnicas=sub.observacoes_tecnicas,
            ordem_execucao=sub.ordem_execucao,
            subatividade_mestre_id=sub.subatividade_mestre_id,
            quantidade_produzida=sub.quantidade_produzida,
            meta_produtividade_snapshot=sub.meta_produtividade_snapshot,
            unidade_medida_snapshot=sub.unidade_medida_snapshot,
        ))

    for mo in RDOMaoObra.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOMaoObra(
            rdo_id=novo.id, admin_id=admin_id,
            funcionario_id=mo.funcionario_id,
            funcao_exercida=mo.funcao_exercida,
            horas_trabalhadas=mo.horas_trabalhadas,
            tarefa_cronograma_id=mo.tarefa_cronograma_id,
            peso_distribuicao=mo.peso_distribuicao,
        ))

    for eq in RDOEquipamento.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOEquipamento(
            rdo_id=novo.id, admin_id=admin_id,
            nome_equipamento=eq.nome_equipamento, quantidade=eq.quantidade,
            horas_uso=eq.horas_uso,
            estado_conservacao=eq.estado_conservacao,
        ))

    for oc in RDOOcorrencia.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOOcorrencia(
            rdo_id=novo.id, admin_id=admin_id,
            tipo_ocorrencia=oc.tipo_ocorrencia, severidade=oc.severidade,
            descricao_ocorrencia=oc.descricao_ocorrencia,
            problemas_identificados=oc.problemas_identificados,
            acoes_corretivas=oc.acoes_corretivas,
            responsavel_acao=oc.responsavel_acao,
            prazo_resolucao=oc.prazo_resolucao,
            status_resolucao=oc.status_resolucao,
        ))

    ip, _ua = _contexto_request()
    transicionar(rdo, RETIFICADO, usuario=usuario, motivo=motivo, ip=ip,
                 detalhes={'rdo_retificador_id': novo.id})
    # No-op de estado (o retificador já nasce em rascunho): documentação
    # executável de que ele nasce editável, sem gravar trilha.
    transicionar(novo, RASCUNHO, usuario=usuario, motivo=motivo, ip=ip,
                 detalhes={'rdo_retificado_id': rdo.id})

    logger.info('[assinatura] rdo=%s RETIFICADO por rdo=%s usuario=%s '
                'motivo=%r', rdo.id, novo.id, usuario.id, motivo)
    return novo
