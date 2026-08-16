"""Motor de alçada de compras — Fase 3.

Responde a três perguntas, e só a essas três:
  1. Em que faixa cai este valor, neste tenant?   → faixa_para_valor
  2. Esta pessoa pode aprovar esta requisição?    → pode_aprovar
  3. Ainda falta alguma coisa para aprovar?       → pendencias_de_aprovacao

O registro da aprovação em si é uma RequisicaoTransicao com
`para_estado=AGUARDANDO_APROVACAO` e motivo prefixado — ver
`registrar_aprovacao`. Reutilizar a trilha existente evita uma segunda
tabela de histórico que teria de ser mantida em sincronia com a primeira.
"""
import logging
from decimal import Decimal

from models import (EstadoRequisicao, FaixaAlcada, MapaConcorrenciaV2,
                    RequisicaoTransicao, TipoUsuario, db)

logger = logging.getLogger('alcada_compras')

# Prefixo que marca uma RequisicaoTransicao como "voto de aprovação"
# (transição AGUARDANDO_APROVACAO → AGUARDANDO_APROVACAO) em vez de uma
# mudança de estado de verdade. É o que permite N aprovações sem N estados.
MARCA_APROVACAO = '[aprovacao]'

# Faixas RECOMENDADAS (Fase 3, decisão D1). Um só lugar: a migration 243
# importa desta constante, e `garantir_faixas_do_tenant` também — assim
# mudar a recomendação é mudar uma lista.
FAIXAS_RECOMENDADAS = [
    # (ordem, valor_ate, aprovacoes, exige_admin, exige_mapa, fornecedores_min)
    (1, Decimal('5000.00'), 1, False, False, 2),
    (2, Decimal('30000.00'), 2, True, False, 2),
    # A faixa aberta pede TRÊS cotações — é onde mora o corte de 3 do pedido
    # original (spec 2026-08-16). Trocar é UPDATE em `faixa_alcada`.
    (3, None, 2, True, True, 3),
]


class _FaixaSeguranca:
    """Faixa usada quando o tenant não tem NENHUMA faixa ativa.

    Falha FECHADA: exige o máximo (2 aprovações, uma de ADMIN), não o
    mínimo. Um tenant sem configuração não deve ser um tenant sem
    controle. Não é persistida — `id` é None de propósito, para que
    ninguém a confunda com uma faixa real ao debugar.
    """
    id = None
    ordem = 0
    valor_ate = None
    aprovacoes_necessarias = 2
    exige_admin = True
    exige_mapa_concorrencia = False
    ativo = True


def garantir_faixas_do_tenant(admin_id):
    """Semeia as faixas recomendadas se o tenant não tiver nenhuma.

    Idempotente: só age quando a contagem é zero. NÃO commita.
    Chamada pela migration 243 (para os tenants existentes) e pela rota de
    criação de requisição (para tenants criados depois da migração).
    """
    if FaixaAlcada.query.filter_by(admin_id=admin_id).count() > 0:
        return False
    for (ordem, valor_ate, aprov, exige_admin, exige_mapa,
         forn_min) in FAIXAS_RECOMENDADAS:
        db.session.add(FaixaAlcada(
            admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
            aprovacoes_necessarias=aprov, exige_admin=exige_admin,
            exige_mapa_concorrencia=exige_mapa,
            fornecedores_minimos=forn_min, ativo=True))
    db.session.flush()
    logger.info('faixas de alçada semeadas para o tenant %s', admin_id)
    return True


def faixas_ordenadas(admin_id):
    """As faixas ativas do tenant, da menor para a maior. Teto aberto por último.

    Extraída de `faixa_para_valor` quando a fase de alçadas avançadas ganhou um
    segundo consumidor: subir N degraus é andar nesta mesma lista.
    """
    return (FaixaAlcada.query
            .filter_by(admin_id=admin_id, ativo=True)
            .order_by(FaixaAlcada.valor_ate.asc().nullslast(),
                      FaixaAlcada.ordem.asc())
            .all())


def faixa_para_valor(admin_id, valor):
    """A faixa ativa de menor teto que ainda cobre `valor`.

    Ordena por `valor_ate` com NULLs por último (o teto aberto é sempre a
    última opção) e devolve a primeira que cobre. Sem faixa ativa alguma,
    devolve `_FaixaSeguranca`.
    """
    valor = Decimal(str(valor or 0))
    faixas = faixas_ordenadas(admin_id)
    if not faixas:
        logger.warning('tenant %s sem faixa de alçada ativa — faixa de '
                       'segurança aplicada', admin_id)
        return _FaixaSeguranca()

    for faixa in faixas:
        if faixa.valor_ate is None or valor <= faixa.valor_ate:
            return faixa

    # Só chega aqui se nenhuma faixa tem teto aberto e o valor passou de
    # todas. Também é falha fechada: a mais restritiva vale.
    logger.warning('tenant %s: valor %s acima de todas as faixas — aplicando '
                   'a de maior teto', admin_id, valor)
    return faixas[-1]


def _inicio_da_rodada_atual(requisicao):
    """id da transição que ENTROU na rodada de aprovação corrente.

    Um voto de aprovação é uma RequisicaoTransicao AGUARDANDO→AGUARDANDO
    (de == para). A ENTRADA numa rodada é uma transição REAL para
    AGUARDANDO_APROVACAO (de != para) — tipicamente RASCUNHO→AGUARDANDO.
    Rejeitar e reenviar (REJEITADA→RASCUNHO→AGUARDANDO) abre uma rodada
    nova; os votos da rodada anterior não podem contar para esta, senão a
    requisição reenviada fecha a alçada com menos aprovações reais do que
    a faixa exige. Devolve 0 quando ainda não houve entrada (a requisição
    nunca saiu de RASCUNHO)."""
    entrada = (RequisicaoTransicao.query
               .filter_by(requisicao_id=requisicao.id,
                          para_estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
               .filter(RequisicaoTransicao.de_estado !=
                       EstadoRequisicao.AGUARDANDO_APROVACAO)
               .order_by(RequisicaoTransicao.id.desc())
               .first())
    return entrada.id if entrada else 0


def votos_de_aprovacao(requisicao):
    """Os votos de aprovação DA RODADA ATUAL, em ordem.

    Escopado à rodada corrente (ver `_inicio_da_rodada_atual`): um voto
    gravado numa tentativa anterior, já rejeitada e reenviada, não conta
    aqui. A trilha inteira continua no banco — o que muda é só a contagem."""
    return (RequisicaoTransicao.query
            .filter_by(requisicao_id=requisicao.id)
            .filter(RequisicaoTransicao.motivo.like(f'{MARCA_APROVACAO}%'))
            .filter(RequisicaoTransicao.id > _inicio_da_rodada_atual(requisicao))
            .order_by(RequisicaoTransicao.id)
            .all())


def aprovacoes_registradas(requisicao):
    """Quantas PESSOAS DISTINTAS já aprovaram."""
    return len({v.usuario_id for v in votos_de_aprovacao(requisicao)})


def _tem_aprovacao_de_admin(requisicao):
    return any(v.papel_aplicado == 'ADMIN' for v in votos_de_aprovacao(requisicao))


def mapa_serve_de_concorrencia(requisicao, minimo=2):
    """Mapa V2 concluído, do mesmo tenant e da mesma obra, com >= `minimo`
    fornecedores. Um fornecedor só não é concorrência — é orçamento.

    `minimo` virou parâmetro na fase de alçadas avançadas: a condição que sobe
    degrau usa o piso fixo de 2 ("houve concorrência?") e a pendência da faixa
    usa o `fornecedores_minimos` dela — que é onde mora o corte de 3 cotações.
    """
    if not requisicao.mapa_v2_id:
        return False
    mapa = db.session.get(MapaConcorrenciaV2, requisicao.mapa_v2_id)
    if mapa is None:
        return False
    if mapa.obra_id != requisicao.obra_id or mapa.admin_id != requisicao.admin_id:
        return False
    if mapa.status != 'concluido':
        return False
    return len(mapa.fornecedores) >= minimo


def faixa_exigida(requisicao):
    """A faixa CARIMBADA; recalculada na leitura quando não houver carimbo.

    O fallback é o que mantém a SC anterior às alçadas avançadas funcionando
    sem backfill — carimbar retroativamente mudaria a régua de rodadas em
    curso, que é justamente o que o carimbo existe para impedir.
    """
    if getattr(requisicao, 'alcada_carimbada_em', None) and \
            getattr(requisicao, 'faixa_exigida_id', None):
        faixa = db.session.get(FaixaAlcada, requisicao.faixa_exigida_id)
        if faixa is not None:
            return faixa
    return faixa_para_valor(requisicao.admin_id, requisicao.valor_estimado)


def pendencias_da_faixa(requisicao):
    """O que a FAIXA exige e ainda não foi atendido — ignora a emergência.

    É o que o rito de emergência transforma em dívida, e o que
    `regularizar_se_couber` consulta para saber se a dívida foi paga.

    Devolve texto porque é o que a tela mostra — e porque o motivo de uma
    requisição estar parada tem que ser legível sem ler código.
    """
    faixa = faixa_exigida(requisicao)
    faltando = []

    registradas = aprovacoes_registradas(requisicao)
    if registradas < faixa.aprovacoes_necessarias:
        restam = faixa.aprovacoes_necessarias - registradas
        faltando.append(
            f'faltam {restam} aprovação(ões) de {faixa.aprovacoes_necessarias}')

    if faixa.exige_admin and not _tem_aprovacao_de_admin(requisicao):
        faltando.append('falta a aprovação de um administrador')

    minimo = getattr(faixa, 'fornecedores_minimos', 2) or 2
    if faixa.exige_mapa_concorrencia and not mapa_serve_de_concorrencia(
            requisicao, minimo=minimo):
        faltando.append(f'falta mapa de concorrência concluído com pelo menos '
                        f'{minimo} fornecedores vinculado a esta requisição')

    return faltando


def pendencias_de_aprovacao(requisicao):
    """O que BLOQUEIA a aprovação AGORA. Vazia = pode ir para APROVADA.

    Com emergência ativa, a faixa inteira dá lugar a uma exigência só — um
    administrador assumindo a compra. O resto segue devido, com prazo, em
    `dividas_de_emergencia`, mas não trava a SC: na emergência real o que
    precisa sair é justamente o pedido.
    """
    from services.alcada_regras import emergencia_ativa

    if emergencia_ativa(requisicao):
        if _tem_aprovacao_de_admin(requisicao):
            return []
        return ['emergência acionada: falta a aprovação de um administrador']
    return pendencias_da_faixa(requisicao)


def dividas_de_emergencia(requisicao):
    """O que a emergência adiou, para a tela mostrar junto com o prazo."""
    from services.alcada_regras import emergencia_ativa
    if not emergencia_ativa(requisicao):
        return []
    return pendencias_da_faixa(requisicao)


def esta_totalmente_aprovada(requisicao):
    return not pendencias_de_aprovacao(requisicao)


def pode_aprovar(requisicao, usuario):
    """(bool, motivo). O motivo é exibido ao usuário — escreva para humano.

    A ordem das checagens é do mais estrutural para o mais circunstancial,
    para que a mensagem seja a mais informativa possível.
    """
    if usuario is None or not getattr(usuario, 'id', None):
        return False, 'Usuário não identificado.'

    if requisicao.estado != EstadoRequisicao.AGUARDANDO_APROVACAO:
        return False, (f'A requisição está em {requisicao.estado.value} — '
                       f'só se aprova o que está aguardando aprovação.')

    # SEPARAÇÃO DE FUNÇÕES — sem exceção, nem para ADMIN. Numa empresa
    # pequena a mesma pessoa acumula papéis; é exatamente aí que a regra
    # precisa valer.
    if requisicao.solicitante_id == usuario.id:
        return False, ('Você é o solicitante desta requisição e não pode '
                       'aprová-la. Peça a outra pessoa com alçada.')

    if any(v.usuario_id == usuario.id for v in votos_de_aprovacao(requisicao)):
        return False, 'Você já aprovou esta requisição.'

    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        if usuario.id != requisicao.admin_id and \
                getattr(usuario, 'admin_id', None) != requisicao.admin_id:
            return False, 'Requisição de outra empresa.'
        return True, ''

    # Não-admin: precisa ser GESTOR da obra (Fase 1, usuario_obra).
    from utils.autorizacao import PAPEIS_QUE_EDITAM_OBRA, papel_na_obra
    papel = papel_na_obra(requisicao.obra_id)
    if papel in PAPEIS_QUE_EDITAM_OBRA:
        return True, ''
    return False, ('Você não é gestor desta obra e não tem alçada para '
                   'aprovar esta requisição.')


def papel_para_alcada(usuario, requisicao):
    """Com que chapéu o voto será registrado."""
    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return 'ADMIN'
    from utils.autorizacao import papel_na_obra
    papel = papel_na_obra(requisicao.obra_id)
    return papel.name if papel is not None else 'DESCONHECIDO'


def registrar_aprovacao(requisicao, usuario, papel=None, observacao=None):
    """Grava UM voto de aprovação. NÃO commita, NÃO muda o estado.

    Quem muda o estado para APROVADA é a rota, depois de checar
    `esta_totalmente_aprovada`. Separar as duas coisas é o que permite N
    aprovações antes de uma única transição de estado.
    """
    motivo = MARCA_APROVACAO
    if observacao:
        motivo = f'{MARCA_APROVACAO} {observacao}'

    voto = RequisicaoTransicao(
        requisicao_id=requisicao.id,
        admin_id=requisicao.admin_id,
        de_estado=requisicao.estado,
        para_estado=requisicao.estado,   # voto não move o estado
        usuario_id=usuario.id,
        papel_aplicado=papel or papel_para_alcada(usuario, requisicao),
        valor_no_momento=requisicao.valor_estimado,
        motivo=motivo,
    )
    db.session.add(voto)
    db.session.flush()
    logger.info('voto de aprovacao: requisicao=%s usuario=%s papel=%s valor=%s',
                requisicao.numero, usuario.id, voto.papel_aplicado,
                requisicao.valor_estimado)

    # A dívida de emergência se fecha sozinha quando as exigências da faixa
    # são atendidas — não há ação de tela para "regularizar".
    from services.alcada_regras import regularizar_se_couber
    regularizar_se_couber(requisicao)
    return voto
