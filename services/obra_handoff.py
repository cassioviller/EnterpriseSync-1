"""Handoff do Gerente de Projeto — Fase 2.

O que existia antes: `Obra.responsavel_id`, uma FK para `Funcionario` sem
`relationship`, sem efeito em permissão nenhuma, e renderizada em quatro
templates que exibiam sempre vazio. Atribuir "responsável" não dava a
ninguém acesso a coisa alguma.

O handoff é uma transição PLANEJAMENTO → EM_EXECUCAO com três efeitos
colaterais indissociáveis, todos na mesma transação:

  1. `Obra.responsavel_id` = o Funcionario indicado;
  2. `UsuarioObra(usuario_do_GP, obra, GESTOR)` — a permissão de verdade, o
     que faz `services.obra_estado.pode_transitar_como` reconhecer o GP e o
     que as rotas de cronograma (Fase 1.5) consultam;
  3. resolução do gate de cronograma (`Obra.cronograma_revisado_em`).

Nada aqui commita — quem chama é dono da transação.
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger('obra.handoff')


class HandoffInvalido(ValueError):
    """Pré-condição do handoff não satisfeita."""


def _cronograma_pendente(obra) -> bool:
    """Há revisão inicial de cronograma pendente para esta obra?

    Reusa `views.obras._precisa_revisao_cronograma_inicial` (Task #200) em vez
    de reimplementar os três critérios. Uma segunda cópia divergiria da
    primeira no primeiro ajuste — e ela ANDOU: em 27c62bb o gate deixou de
    exigir template, passando a bastar existir PropostaItem. Um clone escrito
    antes disso ainda estaria cobrando template aqui.

    Import tardio e dentro de try: `views.obras` importa blueprints, e este
    serviço também é chamado de migração/seed, onde eles podem não estar
    carregados. Falha de leitura → assume "nada pendente", que é o
    comportamento pré-Fase 2 (o handoff não existia e a obra entrava em
    execução de qualquer jeito).
    """
    if obra.cronograma_revisado_em is not None:
        return False
    try:
        from views.obras import _precisa_revisao_cronograma_inicial
        return bool(_precisa_revisao_cronograma_inicial(obra, obra.admin_id))
    except Exception:
        logger.warning('não foi possível avaliar o gate de cronograma da obra %s',
                       getattr(obra, 'id', '?'), exc_info=True)
        return False


def bloqueios_do_handoff(obra, funcionario=None) -> list[str]:
    """Lista legível de tudo que impede o handoff agora. Vazia = liberado.

    Existe separada de `executar_handoff` para que a TELA possa mostrar todos
    os problemas de uma vez, em vez de o usuário descobrir um por submit.
    """
    from models import EstadoObra
    from services.obra_estado import estado_atual

    problemas: list[str] = []

    estado = estado_atual(obra)
    if estado is not EstadoObra.PLANEJAMENTO:
        problemas.append(
            f'A obra está em "{estado.value}" — o handoff só acontece a '
            'partir de "planejamento".')

    if _cronograma_pendente(obra):
        problemas.append(
            'O cronograma inicial ainda não foi revisado. Revise em '
            'Cronograma → Revisão inicial antes de entregar a obra ao GP.')

    if funcionario is not None:
        if funcionario.admin_id != obra.admin_id:
            problemas.append('O funcionário indicado pertence a outro tenant.')
        else:
            from utils.identidade import usuario_do_funcionario
            if usuario_do_funcionario(funcionario.id) is None:
                problemas.append(
                    f'{funcionario.nome} não tem login no sistema. Crie o '
                    'usuário e vincule ao funcionário antes do handoff.')

    return problemas


def dossie_handoff(obra) -> dict:
    """Pacote de contexto que o GP recebe junto com a obra.

    Serve à tela de handoff e ao payload do evento `obra.handoff`. Todos os
    lookups são defensivos: falta de proposta ou de cronograma não impede o
    dossiê de existir — ele é informativo, e derrubá-lo esconderia do usuário
    justamente a tela que explica o que falta.
    """
    from models import TarefaCronograma

    cliente = getattr(obra, 'cliente_ref', None)

    proposta = None
    try:
        from views.obras import _proposta_origem_obra
        p = _proposta_origem_obra(obra, obra.admin_id)
        if p is not None:
            proposta = {
                'id': p.id,
                'numero': p.numero,
                'versao': getattr(p, 'versao', 1) or 1,
                'titulo': getattr(p, 'titulo', None),
                'valor_total': float(getattr(p, 'valor_total', 0) or 0),
            }
    except Exception:
        logger.warning('dossiê: proposta de origem não resolvida (obra %s)',
                       obra.id, exc_info=True)

    try:
        total_tarefas = TarefaCronograma.query.filter_by(
            obra_id=obra.id, admin_id=obra.admin_id).count()
    except Exception:
        total_tarefas = 0

    bloqueios = bloqueios_do_handoff(obra)

    return {
        'obra': {
            'id': obra.id,
            'codigo': obra.codigo,
            'nome': obra.nome,
            'endereco': obra.endereco,
            'data_inicio': obra.data_inicio.isoformat() if obra.data_inicio else None,
            'data_previsao_fim': (obra.data_previsao_fim.isoformat()
                                  if obra.data_previsao_fim else None),
            'valor_contrato': float(obra.valor_contrato or 0),
            'area_total_m2': float(obra.area_total_m2 or 0),
            'estado': obra.estado,
        },
        'cliente': {
            'nome': getattr(cliente, 'nome', None),
            'email': getattr(cliente, 'email', None),
            'telefone': getattr(cliente, 'telefone', None),
        },
        'proposta': proposta,
        'cronograma': {
            'revisado': obra.cronograma_revisado_em is not None,
            'revisado_em': (obra.cronograma_revisado_em.isoformat()
                            if obra.cronograma_revisado_em else None),
            'total_tarefas': total_tarefas,
        },
        'bloqueios': bloqueios,
        'pode_entrar_em_execucao': not bloqueios,
    }


def executar_handoff(obra, funcionario, usuario_id=None, motivo: str = ''):
    """Entrega a obra ao GP. Devolve um dict com o que foi feito.

    Levanta `HandoffInvalido` para pré-condições de negócio e
    `services.obra_estado.TransicaoInvalida` quando a obra não está em
    PLANEJAMENTO — dois erros distintos de propósito: o primeiro o usuário
    conserta (crie o login, revise o cronograma), o segundo é estado errado.

    Não commita.
    """
    from models import EstadoObra, PapelObra, UsuarioObra, db
    from services.obra_estado import transitar
    from utils.identidade import usuario_do_funcionario

    if funcionario is None:
        raise HandoffInvalido('Indique o funcionário que será o Gerente de Projeto.')

    if funcionario.admin_id != obra.admin_id:
        raise HandoffInvalido(
            f'Funcionário {funcionario.id} é do tenant {funcionario.admin_id} '
            f'e a obra é do tenant {obra.admin_id} — handoff recusado.')

    usuario_gp = usuario_do_funcionario(funcionario.id)
    if usuario_gp is None:
        raise HandoffInvalido(
            f'{funcionario.nome} não tem login no sistema. Sem Usuario não há '
            'a quem atribuir o papel GESTOR da obra — crie o usuário e '
            'vincule ao funcionário antes do handoff.')

    if _cronograma_pendente(obra):
        raise HandoffInvalido(
            'O cronograma inicial desta obra ainda não foi revisado. '
            'Conclua a revisão antes de entregar a obra ao Gerente de Projeto.')

    # 1) responsável
    obra.responsavel_id = funcionario.id

    # 2) vínculo GESTOR — upsert, porque `usuario_obra` tem UNIQUE
    #    (usuario_id, obra_id) desde a Fase 1. Um INSERT cego quebraria o
    #    handoff de quem já era APONTADOR na obra.
    vinculo = UsuarioObra.query.filter_by(
        usuario_id=usuario_gp.id, obra_id=obra.id).first()
    if vinculo is None:
        vinculo = UsuarioObra(
            usuario_id=usuario_gp.id, obra_id=obra.id,
            papel=PapelObra.GESTOR, admin_id=obra.admin_id, ativo=True)
        db.session.add(vinculo)
        vinculo_criado = True
    else:
        vinculo.papel = PapelObra.GESTOR
        vinculo.ativo = True
        vinculo_criado = False
    db.session.flush()

    # 3) gate de cronograma: aqui só chegamos se não há nada a revisar.
    #    Obra criada à mão nunca dispara o gate da Task #200 (não tem proposta
    #    de origem) e ficaria com o carimbo NULL para sempre.
    carimbado_agora = False
    if obra.cronograma_revisado_em is None:
        obra.cronograma_revisado_em = datetime.utcnow()
        carimbado_agora = True

    registro = transitar(
        obra, EstadoObra.EM_EXECUCAO, usuario_id=usuario_id, motivo=motivo,
        detalhes={
            'tipo': 'handoff',
            'funcionario_id': funcionario.id,
            'funcionario_nome': funcionario.nome,
            'usuario_gp_id': usuario_gp.id,
            'vinculo_criado': vinculo_criado,
            'cronograma_carimbado_no_handoff': carimbado_agora,
        },
    )

    logger.info(
        'evento=handoff obra_id=%s admin_id=%s funcionario_id=%s '
        'usuario_gp_id=%s vinculo_criado=%s cronograma_carimbado=%s',
        obra.id, obra.admin_id, funcionario.id, usuario_gp.id,
        vinculo_criado, carimbado_agora)

    return {
        'obra_id': obra.id,
        'funcionario_id': funcionario.id,
        'usuario_gp_id': usuario_gp.id,
        'vinculo_id': vinculo.id,
        'vinculo_criado': vinculo_criado,
        'cronograma_carimbado_no_handoff': carimbado_agora,
        'transicao_id': registro.id,
    }
