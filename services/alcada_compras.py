"""Motor de alçada de compras — Fase 3.

Responde a três perguntas, e só a essas três:
  1. Em que faixa cai este valor, neste tenant?   → faixa_para_valor
  2. Esta pessoa pode aprovar esta requisição?    → pode_aprovar
  3. Ainda falta alguma coisa para aprovar?       → pendencias_de_aprovacao

A Fase 3 do CICLO DE COMPRAS acrescentou uma quarta, e ela mora ACIMA da
primeira, nunca dentro dela:
  4. O valor é a única pergunta desta requisição? → faixa_efetiva

`faixa_para_valor` segue INTOCADA e segue sendo a resposta para "que faixa
cobre este valor". `faixa_efetiva` é quem sabe que fornecedor novo, compra sem
concorrência, preço que não é o menor e etapa estourada sobem um degrau — e
quem sabe que nada disso vale quando a requisição foi carimbada `'simples'`.
Duas funções e não uma porque é assim que a paridade fica demonstrável: com a
regra nova desligada, o caminho de decisão é literalmente o mesmo objeto de
antes (📖 spec 2026-08-15-alcadas-design.md, "O motor ganha uma pergunta, não
um segundo motor").

O registro da aprovação em si é uma RequisicaoTransicao com
`para_estado=AGUARDANDO_APROVACAO` e motivo prefixado — ver
`registrar_aprovacao`. Reutilizar a trilha existente evita uma segunda
tabela de histórico que teria de ser mantida em sincronia com a primeira.
"""
import logging
from collections import namedtuple
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func

from models import (ConfiguracaoEmpresa, EstadoRequisicao, FaixaAlcada,
                    MapaConcorrenciaV2, PedidoCompra, RequisicaoCompra,
                    RequisicaoTransicao, TipoUsuario, db)

logger = logging.getLogger('alcada_compras')

# Prefixo que marca uma RequisicaoTransicao como "voto de aprovação"
# (transição AGUARDANDO_APROVACAO → AGUARDANDO_APROVACAO) em vez de uma
# mudança de estado de verdade. É o que permite N aprovações sem N estados.
MARCA_APROVACAO = '[aprovacao]'

# Faixas RECOMENDADAS (Fase 3, decisão D1). Um só lugar: a migration 243
# importa desta constante, e `garantir_faixas_do_tenant` também — assim
# mudar a recomendação é mudar uma lista.
#
# `minimo_cotacoes` entrou na Fase 3 do ciclo de compras. O número semeado é
# 2, não 3, pelo mesmo motivo do backfill da migration 297: o seed PRESERVA o
# comportamento que o código aplicava (`>= 2`). Subir a faixa de topo para 3 é
# a decisão D6, feita por UPDATE no passo 1 do runbook — semear 3 aqui faria
# tenant novo e tenant antigo divergirem sem que ninguém tivesse decidido isso.
FAIXAS_RECOMENDADAS = [
    # (ordem, valor_ate, aprovacoes, exige_admin, exige_mapa, minimo_cotacoes)
    (1, Decimal('5000.00'), 1, False, False, 0),
    (2, Decimal('30000.00'), 2, True, False, 0),
    (3, None, 2, True, True, 2),
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
    # 0 e não 2: a faixa de segurança exige o MÁXIMO do que ela consegue
    # cobrar, e mapa de concorrência não é algo que ela consiga cobrar — um
    # tenant sem faixa nenhuma também não tem quem monte mapa. Exigir aqui
    # seria travar a compra em vez de endurecê-la.
    minimo_cotacoes = 0
    condicoes_ativas = ''
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
         minimo_cotacoes) in FAIXAS_RECOMENDADAS:
        db.session.add(FaixaAlcada(
            admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
            aprovacoes_necessarias=aprov, exige_admin=exige_admin,
            exige_mapa_concorrencia=exige_mapa,
            minimo_cotacoes=minimo_cotacoes, ativo=True))
    db.session.flush()
    logger.info('faixas de alçada semeadas para o tenant %s', admin_id)
    return True


REGIME_SIMPLES = 'simples'
REGIME_AVANCADO = 'avancado'


def regime_alcada_do_tenant(admin_id):
    """O regime de alçada que uma requisição nascida AGORA carregaria.

    Uma função só, para que o ponto que cria requisição não leia a flag por
    conta própria — hoje o ponto é um (`requisicao_nova_post`), e é justamente
    por isso que a indireção precisa existir antes de ser dois.

    O valor devolvido é CARIMBADO em `requisicao_compra.regime_alcada` e nunca
    mais reconsultado para aquela requisição: desligar a flag depois não muda
    o regime do que já nasceu. Ver o spec 2026-08-15-alcadas-design.md, seção
    "Regime de virada".
    """
    from scripts.flag_alcadas_avancadas import alcadas_avancadas_ativa
    return REGIME_AVANCADO if alcadas_avancadas_ativa(admin_id) else REGIME_SIMPLES


def faixa_para_valor(admin_id, valor):
    """A faixa ativa de menor teto que ainda cobre `valor`.

    Ordena por `valor_ate` com NULLs por último (o teto aberto é sempre a
    última opção) e devolve a primeira que cobre. Sem faixa ativa alguma,
    devolve `_FaixaSeguranca`.
    """
    valor = Decimal(str(valor or 0))
    faixas = (FaixaAlcada.query
              .filter_by(admin_id=admin_id, ativo=True)
              .order_by(FaixaAlcada.valor_ate.asc().nullslast(),
                        FaixaAlcada.ordem.asc())
              .all())
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


def mapa_da_requisicao(requisicao):
    """O MapaConcorrenciaV2 vinculado, se ele PUDER servir de concorrência.

    Devolve None — e não o mapa — quando o vínculo existe mas não vale:
    outro tenant, outra obra, ou mapa ainda aberto (cotação em andamento não
    é concorrência fechada). Os dois primeiros são isolamento e por isso são
    conferidos aqui E na rota que grava o vínculo: o serviço protege quem
    chama, a rota impede que a linha errada chegue a existir.
    """
    if not requisicao.mapa_v2_id:
        return None
    mapa = db.session.get(MapaConcorrenciaV2, requisicao.mapa_v2_id)
    if mapa is None:
        return None
    if mapa.obra_id != requisicao.obra_id or mapa.admin_id != requisicao.admin_id:
        return None
    if mapa.status != 'concluido':
        return None
    return mapa


def cotacoes_da_requisicao(requisicao):
    """Quantas cotações o mapa vinculado traz. 0 = não há mapa que sirva.

    Uma cotação é um fornecedor do mapa (`MapaFornecedor`, a coluna da
    tabela comparativa). É este número que a faixa compara com
    `minimo_cotacoes`, e é ele que a pendência mostra ao aprovador.
    """
    mapa = mapa_da_requisicao(requisicao)
    return len(mapa.fornecedores) if mapa is not None else 0


def _mapa_serve_de_concorrencia(requisicao, faixa):
    """A requisição atende à exigência de concorrência DESTA faixa?

    O corte era `len(mapa.fornecedores) >= 2`, literal no código — a única
    regra de alçada que não era dado (📖 spec 2026-08-15-alcadas-design.md,
    "O que já existe"). Agora quem diz quantas cotações bastam é
    `faixa.minimo_cotacoes`, linha de tabela por tenant.

    `minimo_cotacoes = 0` dispensa: a faixa não exige mapa nenhum, e a
    resposta é True mesmo sem vínculo. Nunca 1 — um fornecedor só não é
    concorrência, é orçamento; quem garante isso é a validação da tela de
    faixas (A7), porque um SQL manual continua sendo possível.

    `exige_mapa_concorrencia` NÃO é mais lida aqui. Ela permanece na tabela e
    passa a ser derivada (`minimo_cotacoes > 0`) — ver o comentário em
    `models.FaixaAlcada`.
    """
    minimo = int(getattr(faixa, 'minimo_cotacoes', 0) or 0)
    if minimo <= 0:
        return True
    return cotacoes_da_requisicao(requisicao) >= minimo


# ---------------------------------------------------------------------------
# As quatro condições que sobem um degrau — Fase 3 do ciclo de compras
#
# 📖 spec 2026-08-15-alcadas-design.md, "As quatro condições" e decisão D1.
#
# Os códigos são DADO: eles aparecem em `faixa_alcada.condicoes_ativas`, texto
# separado por vírgula, e quem decide se cada um vale neste tenant é a linha da
# tabela — não o código. Condição que o tenant não ativou não roda: o custo de
# query também é comportamento, e três das quatro consultam o banco.
# ---------------------------------------------------------------------------

CONDICAO_FORNECEDOR_NOVO = 'fornecedor_novo'
CONDICAO_SEM_COTACAO = 'sem_cotacao'
CONDICAO_NAO_MENOR_PRECO = 'nao_menor_preco'
CONDICAO_FORA_DO_ORCAMENTO = 'fora_do_orcamento'

# A ordem é canônica e vale para a avaliação E para a trilha: dois tenants com
# as mesmas condições disparadas gravam a mesma string em `degrau_aplicado`,
# em qualquer ordem que o texto de `condicoes_ativas` esteja.
CONDICOES_CONHECIDAS = (
    CONDICAO_FORNECEDOR_NOVO,
    CONDICAO_SEM_COTACAO,
    CONDICAO_NAO_MENOR_PRECO,
    CONDICAO_FORA_DO_ORCAMENTO,
)

# O motivo em PORTUGUÊS, para a tela. Pendência sem motivo visível é pendência
# que vira ligação para o suporte — quem abre o detalhe da requisição precisa
# ler por que ela subiu sem abrir o spec.
ROTULOS_CONDICAO = {
    CONDICAO_FORNECEDOR_NOVO:
        'fornecedor sem nenhum pedido anterior nesta empresa',
    CONDICAO_SEM_COTACAO:
        'sem mapa de concorrência que atenda ao mínimo de cotações da faixa',
    CONDICAO_NAO_MENOR_PRECO:
        'o fornecedor escolhido no mapa não é o de menor preço do item',
    CONDICAO_FORA_DO_ORCAMENTO:
        'sem etapa apontada, ou a soma da etapa passa o custo previsto',
}

# Que estados de requisição CONSOMEM o orçamento de uma etapa. É a mesma lista
# do acumulado do anti-fracionamento (📖 spec, "Casos de borda"): rejeitada e
# cancelada não gastaram nada, e contá-las faria uma requisição morta segurar
# o orçamento da etapa para sempre.
ESTADOS_QUE_CONSOMEM_ORCAMENTO = (
    EstadoRequisicao.RASCUNHO,
    EstadoRequisicao.AGUARDANDO_APROVACAO,
    EstadoRequisicao.APROVADA,
    EstadoRequisicao.CONVERTIDA,
)


def _cond_fornecedor_novo(requisicao, fornecedor=None):
    """O fornecedor não tem nenhum pedido emitido neste tenant.

    Devolve **None** — "condição NÃO AVALIADA" — quando não há fornecedor, e
    isso não é o mesmo que False. A requisição não tem fornecedor: ele só é
    escolhido na emissão (📖 `PedidoCompra.fornecedor_id` é NOT NULL e a
    requisição não tem a coluna). Devolver False no envio faria a tela afirmar
    que o fornecedor é conhecido quando ninguém ainda o escolheu — a única
    resposta honesta ali é "não dá para saber".

    `fornecedor` aceita o objeto ou o id, porque os dois chamadores existem: a
    rota tem o objeto, o script de simulação da A8 vai ter o id.
    """
    fornecedor_id = getattr(fornecedor, 'id', fornecedor)
    if not fornecedor_id:
        return None
    # Conta pedidos JÁ EMITIDOS. Na emissão a guarda roda antes de o
    # `PedidoCompra` desta compra existir — por isso o primeiro pedido de um
    # fornecedor dispara e o segundo, ainda que no mesmo dia, não (📖 spec,
    # "Casos de borda").
    return PedidoCompra.query.filter_by(
        admin_id=requisicao.admin_id, fornecedor_id=fornecedor_id).count() == 0


def _cond_sem_cotacao(requisicao, faixa):
    """A faixa exige mapa e a requisição não tem um que sirva.

    Recebe a FAIXA porque o mínimo de cotações é dela (`minimo_cotacoes`, A3)
    — esta é a única das quatro em que o critério mora na faixa e não na
    requisição.

    Não substitui a pendência de mapa: a pendência continua, e a compra não
    sai sem mapa. A condição existe para o caso de DISPENSA — fornecedor
    único, item sem concorrente — que hoje não tem caminho nenhum e por isso
    vira requisição travada. Com o degrau, dispensar passa a ser possível
    **e** a custar uma aprovação a mais, registrada.
    """
    minimo = int(getattr(faixa, 'minimo_cotacoes', 0) or 0)
    if minimo <= 0:
        return False
    return not _mapa_serve_de_concorrencia(requisicao, faixa)


def _fornecedor_escolhido_do_item(item):
    """id do `MapaFornecedor` escolhido para este item do mapa, ou None.

    Duas fontes, e a ordem importa. `MapaItemCotacao.fornecedor_escolhido_id`
    é a fonte canônica desde a Task #21 — é o que a tela do mapa e o portal do
    cliente escrevem hoje (📖 `views/obras.py`, `portal_obras_views.py`).
    `MapaCotacao.selecionado` é o campo antigo, que a migration 142 usou como
    origem do backfill e que nenhum caminho de escrita alimenta mais; ele fica
    como segunda leitura para os mapas anteriores àquela migration.
    """
    escolhido = getattr(item, 'fornecedor_escolhido_id', None)
    if escolhido:
        return escolhido
    for cotacao in item.cotacoes:
        if cotacao.selecionado:
            return cotacao.fornecedor_id
    return None


def _cond_nao_menor_preco(requisicao):
    """O mapa tem escolha, e a escolha não é a mais barata do item.

    Sem mapa vinculado devolve False, e não None: quem cobre a ausência de
    concorrência é `sem_cotacao`. O risco que ESTA condição descreve — pagar
    mais caro tendo cotação melhor na mão — só existe quando há mapa.

    Cotação com valor zerado é fornecedor que não cotou o item, e não o menor
    preço do mundo; por isso o mínimo é calculado só sobre valores positivos.
    """
    mapa = mapa_da_requisicao(requisicao)
    if mapa is None:
        return False

    for item in mapa.itens:
        escolhido_id = _fornecedor_escolhido_do_item(item)
        if not escolhido_id:
            continue
        valores = {}
        for cotacao in item.cotacoes:
            valor = Decimal(str(cotacao.valor_unitario or 0))
            if valor > 0:
                valores[cotacao.fornecedor_id] = valor
        if len(valores) < 2 or escolhido_id not in valores:
            continue
        if valores[escolhido_id] > min(valores.values()):
            return True
    return False


def _cond_fora_do_orcamento(requisicao):
    """A requisição não aponta etapa, ou a soma da etapa passa o previsto.

    ⚠️ É a mais RUIDOSA das quatro, e isso foi decidido de olhos abertos (D1
    do spec): `obra_servico_custo_id` é nullable, então requisição que
    simplesmente não aponta etapa dispara. É comportamento correto — compra
    sem centro de custo é o que a Fase 4 do núcleo passou a barrar — mas em
    tenant que ainda não preenche etapa com disciplina ela sobe quase tudo um
    degrau. É por isso que as condições são lista ligável uma a uma, e é por
    isso que o sensor da A8 mede o volume ANTES de alguém ligar esta.

    O "previsto" NÃO é `ObraServicoCusto.valor_orcado` lido direto: aquele
    campo guarda PREÇO DE VENDA nesta cadeia (herdado do item comercial), e
    lê-lo como custo é o defeito que a A13/B2.4 já pagou uma vez. O número
    certo vem de `services.custo_orcado.custo_orcado_por_servico`, que é o
    ponto único da regra "linha de custo vence agregado".

    A soma é das requisições da MESMA etapa que ainda consomem orçamento, mais
    o valor desta — somada em separado de propósito, para que uma requisição
    com valor alterado na sessão e ainda não gravada seja contada pelo valor
    que o chamador está decidendo, não pelo que está no banco.
    """
    if not requisicao.obra_servico_custo_id:
        return True

    from services.custo_orcado import custo_orcado_por_servico
    orcado_por_etapa = custo_orcado_por_servico(requisicao.obra_id,
                                                requisicao.admin_id)
    # Etapa de outra obra ou de outro tenant não aparece no dicionário: cai em
    # 0 e dispara, que é a leitura certa de um vínculo que não deveria existir.
    previsto = Decimal(str(orcado_por_etapa.get(
        requisicao.obra_servico_custo_id, 0) or 0))

    irmas = db.session.query(
        func.coalesce(func.sum(RequisicaoCompra.valor_estimado), 0)
    ).filter(
        RequisicaoCompra.admin_id == requisicao.admin_id,
        RequisicaoCompra.obra_servico_custo_id ==
        requisicao.obra_servico_custo_id,
        RequisicaoCompra.id != requisicao.id,
        RequisicaoCompra.estado.in_(ESTADOS_QUE_CONSOMEM_ORCAMENTO),
    ).scalar() or 0

    total = Decimal(str(irmas)) + Decimal(str(requisicao.valor_estimado or 0))
    return total > previsto


def condicoes_ativas_da_faixa(faixa):
    """Os códigos CONHECIDOS que esta faixa ativa, na ordem canônica.

    `condicoes_ativas` é texto editável — pela tela da A7, pelo script e por
    SQL manual. Código desconhecido é IGNORADO, com aviso no log: nem vira
    degrau silencioso (que ninguém saberia explicar) nem exceção no meio de
    uma aprovação (que travaria a compra por causa de um typo).
    """
    bruto = getattr(faixa, 'condicoes_ativas', '') or ''
    ativas = set()
    for pedaco in bruto.split(','):
        codigo = pedaco.strip().lower()
        if not codigo:
            continue
        if codigo not in CONDICOES_CONHECIDAS:
            logger.warning('faixa de alçada %s ativa condição desconhecida '
                           '%r — ignorada', getattr(faixa, 'id', None), codigo)
            continue
        ativas.add(codigo)
    return [c for c in CONDICOES_CONHECIDAS if c in ativas]


def condicoes_disparadas(requisicao, faixa, fornecedor=None):
    """Os códigos que dispararam NESTA requisição, para ESTA faixa.

    Interseção dos avaliadores com `faixa.condicoes_ativas`: o avaliador da
    condição que o tenant não ativou não é chamado — não é avaliado e
    descartado, é *não avaliado*. Três dos quatro consultam o banco, e num
    tenant grande a diferença aparece na conta.

    O despacho é explícito, um `if` por código, e não uma tabela de funções:
    os quatro avaliadores têm assinaturas diferentes (a faixa importa para um,
    o fornecedor para outro), e uma tabela obrigaria a uniformizá-las
    inventando parâmetros que três deles ignorariam.

    Nenhum avaliador consulta a flag nem o regime — quem decide se eles valem
    é o chamador (`faixa_efetiva`). É o que permite ao sensor da A8 rodar os
    mesmos avaliadores com a flag DESLIGADA, para medir antes de ligar.
    """
    ativas = condicoes_ativas_da_faixa(faixa)
    disparadas = []
    for codigo in CONDICOES_CONHECIDAS:
        if codigo not in ativas:
            continue
        if codigo == CONDICAO_FORNECEDOR_NOVO:
            resultado = _cond_fornecedor_novo(requisicao, fornecedor)
        elif codigo == CONDICAO_SEM_COTACAO:
            resultado = _cond_sem_cotacao(requisicao, faixa)
        elif codigo == CONDICAO_NAO_MENOR_PRECO:
            resultado = _cond_nao_menor_preco(requisicao)
        else:
            resultado = _cond_fora_do_orcamento(requisicao)
        # `is True` e não truthy: None é "não avaliada", e não pode virar
        # degrau por descuido de comparação.
        if resultado is True:
            disparadas.append(codigo)
    return disparadas


# ---------------------------------------------------------------------------
# Anti-fracionamento — o acumulado da janela  (A5)
#
# 📖 spec 2026-08-15-alcadas-design.md, "`valor_para_alcada` — onde o acumulado
# entra" e decisões D2 (janela de 30 dias, por tenant) e D3 (degrau, não
# bloqueio).
#
# São DOIS acumulados, e eles não são o mesmo com filtro diferente:
#
#   * `acumulado_da_etapa` — a soma das requisições da mesma `(obra, etapa)`.
#     É o que vale no ENVIO, e o agrupamento é por etapa porque a REQUISIÇÃO
#     NÃO TEM FORNECEDOR: ele só é escolhido na emissão (📖
#     `PedidoCompra.fornecedor_id` é NOT NULL; `RequisicaoCompra` não tem a
#     coluna).
#   * `acumulado_do_fornecedor` — a soma dos pedidos do mesmo
#     `(admin, fornecedor)` na mesma obra. É o que vale na EMISSÃO, e é o
#     único momento em que o fracionamento por fornecedor pode aparecer.
#
# Quem escolhe entre os dois é `valor_para_alcada`, e o critério é DE ONDE VEIO
# A CHAMADA — presença de fornecedor —, não um parâmetro de configuração. Uma
# chamada com fornecedor só existe na emissão; uma sem fornecedor só existe
# antes dela.
# ---------------------------------------------------------------------------

MOTIVO_FRACIONAMENTO = 'fracionamento'

# Os estados que ENTRAM no acumulado. É deliberadamente a MESMA lista de
# `ESTADOS_QUE_CONSOMEM_ORCAMENTO`, e não uma cópia com outro nome: "consome
# orçamento da etapa" e "conta no acumulado da janela" são a mesma pergunta
# ("esta requisição ainda vale dinheiro?") feita por dois lugares. REJEITADA e
# CANCELADA ficam de fora — a requisição rejeitada e reenviada conta a rodada
# nova, não as duas (📖 spec, "Casos de borda").
ESTADOS_QUE_ACUMULAM = ESTADOS_QUE_CONSOMEM_ORCAMENTO

# O rótulo do fracionamento mora ao lado dos das quatro condições porque a
# TELA mostra uma lista só ("por que esta requisição subiu"), mas fora de
# `ROTULOS_CONDICAO`: fracionamento NÃO é uma das condições de
# `faixa.condicoes_ativas` e não pode ser ligado nem desligado por tenant — ele
# é a regra do acumulado, e ficou fora da lista de propósito (📖 spec, D1).
ROTULOS_DEGRAU = dict(ROTULOS_CONDICAO)
ROTULOS_DEGRAU[MOTIVO_FRACIONAMENTO] = (
    'o acumulado da janela (outras compras da mesma etapa, ou do mesmo '
    'fornecedor na emissão) passa o teto da faixa deste valor')


def janela_de_fracionamento(admin_id):
    """Quantos dias corridos a janela do acumulado cobre NESTE tenant.

    A janela é decisão D2 e é DADO: `configuracao_empresa.janela_fracionamento_
    dias`. Nenhum número desta fase entra num `if` — trocar 30 por 7 é UPDATE,
    não deploy, e há teste que prova que 7 muda o resultado sem tocar em
    código.

    O padrão sai do DEFAULT DA PRÓPRIA COLUNA, e não de um literal repetido
    aqui: tenant sem linha de configuração tem de decidir igual a tenant com a
    linha recém-criada, e duas fontes para o mesmo número é como elas passam a
    divergir. Leitura ilegível cai no padrão em vez de estourar — a alçada não
    pode travar uma compra por causa de uma linha de configuração ausente.
    """
    padrao = ConfiguracaoEmpresa.__table__.c.janela_fracionamento_dias.default.arg
    try:
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        dias = int(getattr(cfg, 'janela_fracionamento_dias', None) or 0)
    except Exception:
        logger.warning('janela de fracionamento ilegível no tenant %s — '
                       'aplicando o padrão de %s dias', admin_id, padrao)
        return padrao
    # 0 ou negativo desligaria o acumulado por acidente de digitação. O padrão
    # é o que já valia, e a A7 valida o campo na tela.
    return dias if dias > 0 else padrao


def _criterios_da_etapa_na_janela(requisicao, dias):
    """Os filtros da janela por `(obra, etapa)`. Um lugar só, dois usuários.

    ⚠️ ÍNDICE: esta lista de critérios foi escrita para pousar em
    `ix_requisicao_obra_etapa_criada (obra_id, obra_servico_custo_id,
    created_at)`, criado na migration 298 — igualdade nas duas primeiras
    colunas e faixa na terceira, exatamente na ordem do índice. Quem mexer
    naquele índice quebra o desempenho de `acumulado_da_etapa` e de
    `irmas_da_janela`, que são chamadas A CADA ENVIO de requisição e a cada
    abertura do detalhe. `admin_id` entra como filtro residual (defesa de
    tenant; `obra_id` já o implica) e `estado` também — os dois depois do
    índice, sobre pouquíssimas linhas.

    Etapa NULA é um grupo, não "todas as etapas": requisição sem centro de
    custo apontado acumula com as outras requisições sem centro de custo da
    mesma obra. É a leitura literal de "mesma (obra, etapa)" quando a etapa é
    NULL, e é a que o fracionamento precisa — omitir a etapa é a forma mais
    fácil de dividir uma compra.
    """
    criterios = [
        RequisicaoCompra.admin_id == requisicao.admin_id,
        RequisicaoCompra.obra_id == requisicao.obra_id,
        RequisicaoCompra.estado.in_(ESTADOS_QUE_ACUMULAM),
        RequisicaoCompra.created_at >= datetime.utcnow() - timedelta(days=dias),
    ]
    if requisicao.obra_servico_custo_id is None:
        criterios.append(RequisicaoCompra.obra_servico_custo_id.is_(None))
    else:
        criterios.append(RequisicaoCompra.obra_servico_custo_id ==
                         requisicao.obra_servico_custo_id)
    # Requisição ainda não persistida não tem id: aí não há linha nenhuma para
    # excluir, e o filtro sai da lista em vez de virar `id IS NOT NULL`.
    if requisicao.id is not None:
        criterios.append(RequisicaoCompra.id != requisicao.id)
    return criterios


def irmas_da_janela(requisicao, dias=None):
    """As OUTRAS requisições da mesma `(obra, etapa)` dentro da janela.

    Existe para a TELA, não para a decisão: o aprovador que vê "esta
    requisição subiu de faixa" sem ver quais irmãs somaram liga para o
    suporte. A soma que decide é `acumulado_da_etapa`, agregada no banco.
    """
    dias = janela_de_fracionamento(requisicao.admin_id) if dias is None else dias
    return (RequisicaoCompra.query
            .filter(*_criterios_da_etapa_na_janela(requisicao, dias))
            .order_by(RequisicaoCompra.created_at.desc())
            .limit(50).all())


def acumulado_da_etapa(requisicao, dias=None):
    """O que a `(obra, etapa)` desta requisição já pediu na janela, ela inclusa.

    A própria requisição entra somada EM SEPARADO, e não pela query: assim uma
    requisição com valor alterado na sessão e ainda não gravada é contada pelo
    valor que o chamador está decidindo, e não pelo que está no banco. Mesma
    escolha de `_cond_fora_do_orcamento`, pelo mesmo motivo.
    """
    dias = janela_de_fracionamento(requisicao.admin_id) if dias is None else dias
    irmas = db.session.query(
        func.coalesce(func.sum(RequisicaoCompra.valor_estimado), 0)
    ).filter(*_criterios_da_etapa_na_janela(requisicao, dias)).scalar() or 0
    return Decimal(str(irmas)) + Decimal(str(requisicao.valor_estimado or 0))


def acumulado_do_fornecedor(admin_id, obra_id, fornecedor_id, dias=None):
    """O que este fornecedor já levou DESTA OBRA na janela, em pedidos emitidos.

    Recebe ids e não a requisição de propósito: só a emissão consegue chamar
    esta função, porque só lá existe fornecedor — e a assinatura torna isso
    explícito para quem for reusá-la (o sensor da A8 é o próximo).

    O valor da compra que está sendo emitida AGORA não entra: ela ainda não é
    pedido. Quem junta os dois é `valor_para_alcada`, com o `max` — e é por
    isso que o `max` não é decoração.

    ⚠️ ÍNDICE, e aqui há DOIS candidatos — conferido por EXPLAIN em 15/08:
    `ix_pedido_admin_fornecedor_data (admin_id, fornecedor_id, data_compra)`,
    criado na migration 298 para esta query, e o `idx_pedido_compra_admin_obra
    (admin_id, obra_id)`, que já existia. As quatro condições abaixo casam com
    os dois pela esquerda, e quem escolhe é o planejador: no dev, com três
    linhas na tabela, ele preferiu o antigo. O da 298 é o que sustenta o caso
    que importa — tenant com MUITOS pedidos na mesma obra, em que filtrar por
    obra não seleciona quase nada e filtrar por fornecedor + janela seleciona.
    Quem mexer em qualquer um dos dois mexe no custo desta soma, que roda a
    cada emissão de pedido. Antes da 298 não havia índice NENHUM sobre
    `data_compra`.
    """
    dias = janela_de_fracionamento(admin_id) if dias is None else dias
    total = db.session.query(
        func.coalesce(func.sum(PedidoCompra.valor_total), 0)
    ).filter(
        PedidoCompra.admin_id == admin_id,
        PedidoCompra.fornecedor_id == fornecedor_id,
        PedidoCompra.data_compra >= date.today() - timedelta(days=dias),
        PedidoCompra.obra_id == obra_id,
    ).scalar() or 0
    return Decimal(str(total))


def valor_para_alcada(requisicao, fornecedor=None):
    """O valor que a faixa deve olhar: `max(linha, acumulado aplicável)`.

    O ÚNICO ponto que sabe escolher entre os dois acumulados, e o critério é de
    onde veio a chamada: com fornecedor é emissão (acumulado do fornecedor),
    sem fornecedor é envio/aprovação (acumulado da etapa). Não há parâmetro
    para forçar um ou outro, de propósito — a escolha é um fato do fluxo, não
    uma opção de quem chama.

    `max` e não soma: o acumulado NUNCA faz a faixa descer. Uma compra de
    R$ 40.000 num fornecedor que só tinha R$ 100 de histórico continua sendo
    uma compra de R$ 40.000.

    Não consulta a flag nem o regime — quem decide se o acumulado vale é o
    chamador (`decisao_de_alcada`), pelo mesmo contrato dos quatro avaliadores.
    É o que permite ao sensor da A8 medir com a flag desligada.
    """
    linha = Decimal(str(requisicao.valor_estimado or 0))
    fornecedor_id = getattr(fornecedor, 'id', fornecedor)
    if fornecedor_id:
        acumulado = acumulado_do_fornecedor(
            requisicao.admin_id, requisicao.obra_id, fornecedor_id)
    else:
        acumulado = acumulado_da_etapa(requisicao)
    return max(linha, acumulado)


_LIMITE_DEGRAU = 200   # tamanho da coluna requisicao_compra.degrau_aplicado


def _gravar_degrau(requisicao, codigos):
    """Acrescenta os códigos a `degrau_aplicado`. NÃO commita, NÃO apaga.

    A trilha só CRESCE. Quem reabre a requisição seis meses depois precisa ver
    por que ela subiu sem recalcular uma janela que já passou (📖 spec,
    "Modelo de dados") — e recalcular daria outra resposta: depois da emissão o
    fornecedor novo já não é novo, e apagar o código apagaria justamente o
    motivo da exigência que a compra cumpriu.

    Preserva o que já estava lá, inclusive código que este módulo não conhece:
    `fracionamento` (A5) mora no mesmo campo e não pode ser varrido por uma
    passada de condições.
    """
    if not codigos:
        return
    atuais = [c.strip() for c in (requisicao.degrau_aplicado or '').split(',')
              if c.strip()]
    for codigo in codigos:
        if codigo in atuais:
            continue
        if len(','.join(atuais + [codigo])) > _LIMITE_DEGRAU:
            logger.warning('degrau_aplicado da requisicao %s cheio — %r não '
                           'coube', requisicao.numero, codigo)
            break
        atuais.append(codigo)
    texto = ','.join(atuais)
    # Só escreve quando muda: `faixa_efetiva` é chamada em rota de leitura
    # (o detalhe da requisição), e atribuir o mesmo texto sujaria a sessão
    # para nada — um UPDATE por página aberta.
    if texto != (requisicao.degrau_aplicado or ''):
        requisicao.degrau_aplicado = texto


DecisaoAlcada = namedtuple('DecisaoAlcada', 'base efetiva condicoes')


def _mesma_faixa(uma, outra):
    """As duas referências apontam para a MESMA linha de `faixa_alcada`?

    `is` não serve aqui: `faixa_para_valor` devolve uma `_FaixaSeguranca` NOVA
    a cada chamada quando o tenant não tem faixa nenhuma, e duas instâncias
    diferentes da mesma política diriam falsamente que a faixa mudou —
    inventando um fracionamento num tenant que sequer configurou faixas.
    """
    if uma is outra:
        return True
    id_uma = getattr(uma, 'id', None)
    return id_uma is not None and id_uma == getattr(outra, 'id', None)


def decisao_de_alcada(requisicao, fornecedor=None):
    """`(faixa base, faixa efetiva, motivos do degrau)` — o cálculo inteiro.

    Existe para que a TELA possa mostrar as três coisas sem pagar o cálculo
    duas vezes: `faixa_efetiva` devolve só a faixa, e o detalhe da requisição
    precisa também da base e do porquê. Ponto único do cálculo — quem decide e
    quem exibe leem daqui, e é isso que impede a tela de prometer uma faixa
    enquanto o envio cobra outra.

    A conta tem DOIS movimentos, nesta ordem, e eles não se somam duas vezes:

      1. o ACUMULADO da janela move a faixa de PARTIDA (`fracionamento`) — o
         valor que a faixa olha deixa de ser o da linha e passa a ser
         `valor_para_alcada`;
      2. cada CONDIÇÃO disparada anda uma posição a partir dali.

    `base` continua sendo a faixa DO VALOR DA LINHA, e é ela que a tela mostra
    como "pelo valor, cairia em" — sobrescrevê-la com a do acumulado faria a
    tela esconder justamente o fato que gerou a exigência.

    NÃO commita, no mesmo contrato de `registrar_aprovacao`: `degrau_aplicado`
    é escrito na sessão e quem persiste é a rota.
    """
    base = faixa_para_valor(requisicao.admin_id, requisicao.valor_estimado)

    # O REGIME manda, e não a flag. Requisição carimbada 'simples' segue no
    # motor de ontem ainda que a flag esteja ligada hoje; requisição carimbada
    # 'avancado' segue exigindo o que exigia ainda que a flag tenha sido
    # desligada. Ler a flag aqui faria o passado mudar toda vez que alguém
    # mexesse na configuração (📖 spec, "Regime de virada" e "Rollback").
    if getattr(requisicao, 'regime_alcada', REGIME_SIMPLES) != REGIME_AVANCADO:
        return DecisaoAlcada(base, base, [])

    motivos = []
    partida = base

    # (1) O acumulado da janela. Só mexe em alguma coisa quando cruza um teto
    # que a linha sozinha não cruzaria — é a definição do fracionamento no
    # spec, e é o que impede uma obra grande de virar faixa de topo só por ser
    # movimentada.
    valor = valor_para_alcada(requisicao, fornecedor)
    if valor > Decimal(str(requisicao.valor_estimado or 0)):
        por_acumulado = faixa_para_valor(requisicao.admin_id, valor)
        if not _mesma_faixa(por_acumulado, base):
            partida = por_acumulado
            motivos.append(MOTIVO_FRACIONAMENTO)
            logger.info('[fase3] requisicao %s: acumulado da janela %s move a '
                        'faixa de partida da %s para a %s', requisicao.numero,
                        valor, base.ordem, partida.ordem)

    # (2) As condições, a partir da faixa em que a requisição de fato está —
    # `sem_cotacao` pergunta o mínimo de cotações DA FAIXA, e depois do
    # fracionamento a faixa é outra.
    disparadas = condicoes_disparadas(requisicao, partida, fornecedor)
    motivos.extend(disparadas)

    if not motivos:
        return DecisaoAlcada(base, base, [])

    # A trilha é gravada MESMO quando o degrau satura na faixa de topo: que a
    # condição disparou é fato, e a única requisição sobre a qual ninguém
    # saberia disso seria justamente a de maior valor.
    _gravar_degrau(requisicao, motivos)

    escada = (FaixaAlcada.query
              .filter_by(admin_id=requisicao.admin_id, ativo=True)
              .order_by(FaixaAlcada.ordem.asc())
              .all())
    try:
        posicao = escada.index(partida)
    except ValueError:
        # `_FaixaSeguranca` não está na escada (tenant sem faixa nenhuma). Não
        # é erro: é o caso em que o degrau é sempre saturado, como no tenant
        # de faixa única (📖 spec, "Casos de borda").
        return DecisaoAlcada(base, partida, motivos)

    # O degrau anda POSIÇÕES na escada, não números de `ordem`. Somar à ordem
    # devolveria uma faixa inexistente em qualquer tenant cuja numeração tenha
    # buraco (1, 2, 9) — e nada impede que tenha, porque a ordem é digitada.
    # São `len(disparadas)` posições, e não `len(motivos)`: o fracionamento já
    # gastou o degrau dele ao mover a partida, e contá-lo de novo aqui subiria
    # duas faixas por um motivo só.
    efetiva = escada[min(posicao + len(disparadas), len(escada) - 1)]
    if not _mesma_faixa(efetiva, base):
        logger.info('[fase3] requisicao %s subiu da faixa %s para a %s por %s',
                    requisicao.numero, base.ordem, efetiva.ordem,
                    ','.join(motivos))
    else:
        logger.info('[fase3] requisicao %s já está na faixa de topo — degrau '
                    'saturado, motivos %s registrados', requisicao.numero,
                    ','.join(motivos))
    return DecisaoAlcada(base, efetiva, motivos)


def faixa_efetiva(requisicao, fornecedor=None):
    """A faixa que vale de verdade para esta requisição.

    Com a requisição em regime `'simples'` devolve **o mesmo objeto** que
    `faixa_para_valor` — é o que o teste de paridade prova, e é o que autoriza
    todo o resto da fase.
    """
    return decisao_de_alcada(requisicao, fornecedor).efetiva


def pendencias_de_aprovacao(requisicao, fornecedor=None):
    """Lista de textos do que ainda falta. Vazia = pode ir para APROVADA.

    Devolve texto porque é o que a tela mostra — e porque o motivo de uma
    requisição estar parada tem que ser legível sem ler código.

    A faixa é a EFETIVA: se o degrau subiu a exigência, é a exigência de cima
    que a requisição tem de cumprir. Cobrar a faixa do valor aqui faria o
    degrau ser decoração — a requisição subiria de faixa na tela e fecharia a
    alçada com as aprovações da faixa de baixo.
    """
    faixa = faixa_efetiva(requisicao, fornecedor)
    faltando = []

    registradas = aprovacoes_registradas(requisicao)
    if registradas < faixa.aprovacoes_necessarias:
        restam = faixa.aprovacoes_necessarias - registradas
        faltando.append(
            f'faltam {restam} aprovação(ões) de {faixa.aprovacoes_necessarias}')

    if faixa.exige_admin and not _tem_aprovacao_de_admin(requisicao):
        faltando.append('falta a aprovação de um administrador')

    # O número vem da faixa, não do código. E a pendência diz QUANTAS faltam:
    # "falta mapa" fez o aprovador anexar um mapa de duas cotações numa faixa
    # que pede três e voltar exatamente ao mesmo lugar.
    minimo = int(getattr(faixa, 'minimo_cotacoes', 0) or 0)
    if minimo > 0 and not _mapa_serve_de_concorrencia(requisicao, faixa):
        tem = cotacoes_da_requisicao(requisicao)
        if tem == 0:
            faltando.append(f'falta mapa de concorrência concluído com pelo '
                            f'menos {minimo} cotações vinculado a esta '
                            f'requisição')
        else:
            restam = minimo - tem
            faltando.append(f'o mapa vinculado tem {tem} de {minimo} cotações '
                            f'— falta{"m" if restam > 1 else ""} {restam}')

    return faltando


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
    return voto
