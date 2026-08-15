"""Financeiro da compra — o chokepoint da Fase 2 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md

Até aqui a `ContaPagar` de uma compra nascia em `compras_views.py:305`, no mesmo
request do formulário de emissão: sem material, sem nota, sem conferente. Este
módulo é o único lugar por onde a obrigação de compra passa a nascer, ser
liberada e ser baixada — no molde de `services/recebimento_pedido.py` (Fase 1) e
`services/requisicao_compra.py` (Fase 3).

Nesta etapa (F2) mora aqui só a leitura do regime. O documento, as validações e
a liberação chegam na F3; a tríade que barra o pagamento, na F4.
"""

# Os dois fluxos, como valor carimbado em `pedido_compra.fluxo_pagamento`.
# São strings e não Enum nativo pelo mesmo motivo que `situacao_recebimento` da
# Fase 1: estender enum nativo no Postgres é migration própria (a 245 foi a
# primeira do repositório a fazer isso), e o ganho não paga o custo para um
# domínio de dois valores.
FATURADO = 'faturado'
ADIANTAMENTO = 'adiantamento'
FLUXOS_VALIDOS = {FATURADO, ADIANTAMENTO}


def fluxo_do_tenant(admin_id):
    """O tenant está no regime de dois fluxos AGORA?

    Uma função só, para que os pontos que criam `PedidoCompra` não leiam a flag
    por conta própria — dois lugares lendo a mesma regra é dois lugares onde ela
    pode divergir. Espelha `services.recebimento_pedido.regime_do_tenant`.

    O valor devolvido decide o que é CARIMBADO em `pedido_compra.fluxo_pagamento`
    e nunca mais é reconsultado para aquele pedido: desligar a flag depois não
    reinterpreta adiantamento já pago como compra faturada.

    Falha FECHADA para o regime antigo — ver o docstring do script da flag.
    """
    from scripts.flag_financeiro_dois_fluxos import financeiro_dois_fluxos_ativo
    return bool(financeiro_dois_fluxos_ativo(admin_id))


def fluxo_do_pedido_novo(admin_id, escolha=None):
    """O valor a carimbar num pedido que nasce agora.

    Com o regime desligado o resultado é sempre `faturado`, **inclusive quando
    alguém manda `escolha='adiantamento'`**: a tela não oferece a opção fora do
    regime novo, e um POST forjado não pode ser a porta de entrada de um fluxo
    que o tenant não ligou.

    Com o regime ligado, respeita a escolha de quem emite; escolha ausente ou
    desconhecida cai em `faturado`, que é o caso comum e o menos surpreendente.
    """
    if not fluxo_do_tenant(admin_id):
        return FATURADO
    if escolha in FLUXOS_VALIDOS:
        return escolha
    return FATURADO


# ── Erros do domínio ─────────────────────────────────────────────────
# Exceções e não `(False, motivo)`: quem chama de dentro de uma transação
# precisa que o caminho de erro aborte, e não que ele dependa de alguém
# lembrar de conferir o retorno.

class ErroFinanceiroCompra(Exception):
    """Raiz — permite `except ErroFinanceiroCompra` numa rota só."""


class NotaDuplicada(ErroFinanceiroCompra):
    """Mesma nota (fornecedor + número + série) já lançada neste tenant."""


class TriadeIncompleta(ErroFinanceiroCompra):
    """Falta pelo menos uma das três pernas para liberar o pagamento."""


def _d(valor):
    from decimal import Decimal
    if valor is None:
        return Decimal('0')
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def situacao_liberacao_inicial(pedido):
    """Como a `ContaPagar` deste pedido nasce: 'bloqueada' ou 'liberada'.

    Só o Fluxo A do regime novo nasce bloqueada. O Fluxo B nasce liberada por
    definição — o adiantamento existe justamente para ser pago antes de haver o
    que atestar; o que fica pendente nele é a ENTREGA, e isso mora em
    `AdiantamentoFornecedor` (F6).

    Pedido do regime antigo nasce liberada, sempre: é o comportamento de hoje, e
    é o que a paridade com a flag desligada tem de provar.
    """
    if getattr(pedido, 'fluxo_pagamento', FATURADO) != FATURADO:
        return 'liberada'
    if not fluxo_do_tenant(pedido.admin_id):
        return 'liberada'
    return 'bloqueada'


def criar_obrigacao(pedido):
    """Cria as `ContaPagar` da compra — o único lugar que faz isso.

    Reproduz campo a campo o que `compras_views.processar_compra_normal` fazia
    inline, com UMA diferença: `situacao_liberacao`. Fora do regime novo o
    resultado é idêntico ao de antes, e é isso que o teste de paridade mede.

    **O valor é o do PEDIDO, não o do atestado.** No instante da emissão o
    atestado vale zero — nada chegou. Uma conta de R$ 0,00 desaparece de toda
    projeção de caixa, e o financeiro perderia a previsão, que é metade do valor
    do módulo. O reajuste para o que de fato chegou acontece em `liberar()`.

    NÃO commita — o chamador cuida do commit, como todo o resto deste caminho.
    """
    from app import db
    from models import ContaPagar, Fornecedor
    from compras_views import _vencimentos

    fornecedor = Fornecedor.query.get(pedido.fornecedor_id)
    forn_nome = fornecedor.nome if fornecedor else 'Fornecedor'

    vencimentos = _vencimentos(
        pedido.data_compra, pedido.condicao_pagamento, pedido.parcelas,
        primeira_parcela=pedido.data_vencimento_primeira_parcela,
        intervalo_dias=pedido.intervalo_parcelas_dias,
    )
    n_parcelas = len(vencimentos)
    valor_total = float(pedido.valor_total or 0)
    valor_parcela = round(valor_total / n_parcelas, 2) if n_parcelas else 0.0
    situacao = situacao_liberacao_inicial(pedido)

    criadas = []
    for idx, (data_venc, _) in enumerate(vencimentos, start=1):
        v = (valor_parcela if idx < n_parcelas
             else round(valor_total - valor_parcela * (n_parcelas - 1), 2))
        desc = f"Compra{(' NF ' + pedido.numero) if pedido.numero else ''} - {forn_nome}"
        if n_parcelas > 1:
            desc += f" - Parcela {idx}/{n_parcelas}"

        cp = ContaPagar(
            admin_id=pedido.admin_id,
            fornecedor_id=pedido.fornecedor_id,
            obra_id=pedido.obra_id,
            numero_documento=pedido.numero,
            descricao=desc[:500],
            valor_original=v,
            valor_pago=0,
            saldo=v,
            status='PENDENTE',
            data_emissao=pedido.data_compra,
            data_vencimento=data_venc,
            origem_tipo='COMPRA',
            origem_id=pedido.id,
            pedido_compra_id=pedido.id,
            parcela_numero=idx,
            parcela_total=n_parcelas,
            responsavel_id=pedido.responsavel_id,
            situacao_liberacao=situacao,
        )
        db.session.add(cp)
        criadas.append(cp)

    db.session.flush()
    return criadas


def lancar_nota(pedido, *, numero, serie='1', valor_total, data_emissao,
                data_vencimento=None, chave_acesso=None, arquivo_path=None,
                usuario=None):
    """Registra uma nota do pedido. Levanta `NotaDuplicada`.

    A duplicidade é conferida ANTES do INSERT, e não só pelo UNIQUE do banco:
    `IntegrityError` aborta a transação inteira, e quem está no meio de um
    lançamento perderia o resto do trabalho por causa de um número repetido.
    O UNIQUE continua lá como última linha de defesa — o que não pode é ele ser
    a PRIMEIRA.
    """
    from app import db
    from models import NotaFiscalPedido

    ja_existe = NotaFiscalPedido.query.filter_by(
        admin_id=pedido.admin_id, fornecedor_id=pedido.fornecedor_id,
        numero=numero, serie=serie).first()
    if ja_existe is not None:
        raise NotaDuplicada(
            f'a nota {numero}/{serie} deste fornecedor já foi lançada no '
            f'pedido {ja_existe.pedido_id}. Se for outra nota, confira o '
            f'número e a série no papel.')

    nf = NotaFiscalPedido(
        pedido_id=pedido.id, admin_id=pedido.admin_id,
        fornecedor_id=pedido.fornecedor_id,
        numero=numero, serie=serie, chave_acesso=chave_acesso,
        valor_total=_d(valor_total), data_emissao=data_emissao,
        data_vencimento=data_vencimento, arquivo_path=arquivo_path,
        lancada_por_id=getattr(usuario, 'id', None))
    db.session.add(nf)
    db.session.flush()
    return nf


def valor_das_notas(pedido):
    """Σ do valor das notas lançadas no pedido."""
    from models import NotaFiscalPedido
    notas = NotaFiscalPedido.query.filter_by(pedido_id=pedido.id).all()
    total = _d(0)
    for n in notas:
        total += _d(n.valor_total)
    return total


def _emergencia_nao_ratificada(pedido):
    """Frase da emergência vencida da requisição de origem, ou None.

    ── A PONTE COM A FASE 3 (alçadas avançadas, A6) ────────────────────────
    A sanção da emergência 48h não ratificada é **a conta não liberar** (📖
    spec 2026-08-15-alcadas-design.md, decisão D5). O material já chegou;
    reverter a requisição puniria a obra por um ato administrativo e chegaria
    tarde. O dinheiro é onde ainda dá para parar.

    Ela entra AQUI, e não em `financeiro_views.pagar_conta`, e isso é o ponto:
    `pagar_conta` recusa por **um** critério, `situacao_liberacao`, e é ele que
    a Fase 2 registrou como porta única (ver o ⚠️ do bloco F5, acima). Uma
    segunda guarda lá recusaria o mesmo pagamento por dois motivos diferentes e
    dobraria as formas de o usuário ficar preso, sem acrescentar controle
    nenhum. `pernas_faltantes` é o lugar por onde a Fase 2 já responde "por que
    esta conta não libera", e é consumida pelos três pontos que importam:
    `liberar()` (que recusa), `fechar_lote()` (que pula a conta) e a mensagem
    da recusa da baixa. Uma perna a mais é uma frase a mais na mesma resposta.

    Consequência ASSIMÉTRICA, e ela é decidida: com `financeiro_dois_fluxos_
    ativo` desligado a `ContaPagar` nasce `liberada`, `pernas_faltantes` volta
    vazia no primeiro `return` e a sanção não tem onde morder. É por isso que o
    `--ligar` da flag de alçadas avançadas AVISA sem recusar quando falta a
    Fase 2 — as outras três regras da fase funcionam sem ela.
    """
    from app import db
    from models import RequisicaoCompra
    from services.alcada_compras import (motivo_da_emergencia_vencida,
                                         ratificacao_vencida)

    requisicao_id = getattr(pedido, 'requisicao_id', None)
    if not requisicao_id:
        return None
    requisicao = db.session.get(RequisicaoCompra, requisicao_id)
    if requisicao is None or not ratificacao_vencida(requisicao):
        return None
    return motivo_da_emergencia_vencida(requisicao)


def pernas_faltantes(pedido):
    """Quais pernas da tríade faltam. Lista de frases em português.

    É esta função que a tela e a mensagem de recusa consomem — recusar sem
    dizer o que falta é o que faz o usuário procurar o caminho de fora do
    sistema. Ela não escreve nada: dá para chamar de dentro de um template sem
    medo.

    Pedido fora do Fluxo A do regime novo não tem tríade — devolve lista vazia.

    Desde a Fase 3 (alçadas avançadas, A6) a lista tem uma perna que não é da
    tríade: a emergência 48h não ratificada. Ver `_emergencia_nao_ratificada`
    para por que ela entra por aqui e não por uma segunda porta em
    `pagar_conta`.
    """
    from services.recebimento_pedido import valor_atestado

    if situacao_liberacao_inicial(pedido) != 'bloqueada':
        return []

    faltam = []
    if valor_das_notas(pedido) <= 0:
        faltam.append('sem nota fiscal lançada')

    atestado = _d(valor_atestado(pedido))
    if atestado <= 0:
        faltam.append('sem atesto de recebimento — nada foi conferido ainda')

    emergencia = _emergencia_nao_ratificada(pedido)
    if emergencia:
        faltam.append(emergencia)
    return faltam


def divergencia_nota_atestado(pedido):
    """(diferenca, pct, dentro_da_tolerancia) entre as notas e o atestado.

    Decisão D1: acima da tolerância do tenant isto AVISA, não bloqueia. Frete,
    arredondamento e tributo por dentro produzem divergência legítima toda
    semana; bloquear ensinaria o time a lançar nota com o valor do atestado, que
    é perder a conferência inteira.
    """
    from decimal import Decimal
    from models import ConfiguracaoEmpresa
    from services.recebimento_pedido import valor_atestado

    notas = valor_das_notas(pedido)
    atestado = _d(valor_atestado(pedido))
    diferenca = notas - atestado
    if atestado <= 0:
        return diferenca, Decimal('0'), True

    pct = abs(diferenca) / atestado * Decimal('100')
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=pedido.admin_id).first()
    limite = _d(getattr(cfg, 'tolerancia_divergencia_nf_pct', None) or 0)
    return diferenca, pct, pct <= limite


def liberar(pedido, *, usuario=None):
    """Libera as contas do pedido para pagamento. Levanta `TriadeIncompleta`.

    **Aqui o valor da conta é reajustado para o que CHEGOU** — é o momento em
    que `valor_atestado` (Fase 1) finalmente é lido por alguém. Entrega parcial
    encerrada com saldo derruba a conta para o valor do que veio, e a diferença
    fica escrita na observação, não sumida.

    Conta já paga NÃO é reajustada nem retocada: reescrever obrigação liquidada
    é reescrever o passado financeiro, e o estorno é outro caminho.
    """
    from datetime import datetime
    from app import db
    from models import ContaPagar
    from services.recebimento_pedido import valor_atestado

    faltam = pernas_faltantes(pedido)
    if faltam:
        raise TriadeIncompleta(
            f'não dá para liberar o pagamento do pedido '
            f'{pedido.numero or pedido.id}: ' + '; '.join(faltam) + '.')

    contas = ContaPagar.query.filter_by(
        pedido_compra_id=pedido.id, admin_id=pedido.admin_id).order_by(
            ContaPagar.parcela_numero).all()
    abertas = [c for c in contas if (c.status or '').upper() not in ('PAGO',)]
    if not abertas:
        return []

    atestado = _d(valor_atestado(pedido))
    total_aberto = sum(_d(c.valor_original) for c in abertas)
    diferenca, pct, dentro = divergencia_nota_atestado(pedido)

    agora = datetime.utcnow()
    for idx, cp in enumerate(abertas, start=1):
        if total_aberto > 0 and atestado != total_aberto:
            proporcao = _d(cp.valor_original) / total_aberto
            novo = (atestado * proporcao).quantize(_d('0.01'))
            if idx == len(abertas):   # a última absorve o arredondamento
                novo = atestado - sum(_d(c.valor_original) for c in abertas[:-1])
            anterior = _d(cp.valor_original)
            cp.valor_original = novo
            cp.saldo = novo - _d(cp.valor_pago)
            obs = (f'[liberação] valor ajustado de {anterior} para {novo} '
                   f'— pago o que foi atestado, não o que foi pedido.')
            cp.observacoes = ((cp.observacoes or '') + '\n' + obs).strip()[:2000]
        if not dentro:
            aviso = (f'[divergência] notas somam {valor_das_notas(pedido)} e o '
                     f'atestado é {atestado} ({pct.quantize(_d("0.01"))}% de '
                     f'diferença, acima da tolerância do tenant).')
            cp.observacoes = ((cp.observacoes or '') + '\n' + aviso).strip()[:2000]
        cp.situacao_liberacao = 'liberada'
        cp.liberada_por_id = getattr(usuario, 'id', None)
        cp.liberada_em = agora

    db.session.flush()
    return abertas


class SegregacaoViolada(ErroFinanceiroCompra):
    """Quem montou o lote tentou fechá-lo."""


class LoteImutavel(ErroFinanceiroCompra):
    """Lote fechado que já tem pagamento não volta a ser rascunho."""


# ── F5 — o fechamento passa a ter efeito ─────────────────────────────
#
# `FechamentoPagamento` já existia e já tinha tela: selecionava contas,
# agrupava e mudava o status de ABERTO para FECHADO. O que faltava era o
# efeito — `pagar_conta` não consultava o lote em ponta nenhuma, `FECHADO`
# não autorizava nada e `reabrir` desfazia sem rastro.
#
# ⚠️ DESVIO DELIBERADO do spec, e vale saber por quê. O spec dizia que no
# regime novo `pagar_conta` exigiria a conta num lote FECHADO. Não foi
# feito assim: `pagar_conta` continua com UMA porta — `situacao_liberacao`.
# Duas guardas no mesmo ponto recusariam o mesmo pagamento por dois motivos
# diferentes e dobrariam as formas de o usuário ficar preso, sem acrescentar
# controle: fechar o lote é justamente o que muda a situação para 'liberada'.
# O estado mora num lugar só; o fechamento é quem o move.

def fechar_lote(fechamento, *, usuario=None):
    """Fecha o lote e libera as contas dele. Levanta `SegregacaoViolada`.

    A segregação só é EXIGIDA quando os dois lados são conhecidos: lote
    anterior à migration 296 não tem `criado_por_id`, e exigir com um lado
    ausente travaria todo lote histórico — cujo efeito prático seria o time
    desligar a regra. Regra que atrapalha sem proteger é regra que morre.

    Contas cujo pedido ainda não fechou a tríade são PULADAS, não estouram: um
    lote com dez contas não pode falhar inteiro porque uma delas está sem nota.
    O que fica de fora continua bloqueado, e é o sensor da F7 que o mostra.
    """
    from datetime import datetime
    from app import db
    from models import ContaPagar, PedidoCompra

    criado_por = getattr(fechamento, 'criado_por_id', None)
    quem_fecha = getattr(usuario, 'id', None)
    if criado_por is not None and quem_fecha is not None and criado_por == quem_fecha:
        raise SegregacaoViolada(
            'quem montou este lote não pode fechá-lo. A separação entre quem '
            'seleciona as contas e quem autoriza o pagamento é o que faz o '
            'lote valer alguma coisa — peça a outra pessoa que feche.')

    contas = ContaPagar.query.filter_by(fechamento_id=fechamento.id).all()
    liberadas = []
    for cp in contas:
        if cp.situacao_liberacao != 'bloqueada':
            continue
        pedido = (db.session.get(PedidoCompra, cp.pedido_compra_id)
                  if cp.pedido_compra_id else None)
        if pedido is None:
            continue
        try:
            liberadas.extend(liberar(pedido, usuario=usuario))
        except TriadeIncompleta:
            continue   # fica bloqueada, e o sensor da F7 a nomeia

    fechamento.status = 'FECHADO'
    fechamento.fechado_por_id = quem_fecha
    fechamento.fechado_em = datetime.utcnow()
    db.session.flush()
    return liberadas


def reabrir_lote(fechamento, *, usuario=None):
    """Reabre o lote. Levanta `LoteImutavel` se alguma conta já foi paga.

    Lote fechado com pagamento é documento: reabri-lo seria reescrever o
    registro de uma autorização que já produziu saída de dinheiro.
    """
    from app import db
    from models import ContaPagar

    pagas = ContaPagar.query.filter_by(fechamento_id=fechamento.id).filter(
        ContaPagar.status == 'PAGO').count()
    if pagas:
        raise LoteImutavel(
            f'este lote já tem {pagas} conta(s) paga(s) e não pode ser '
            f'reaberto — a autorização dele já virou saída de dinheiro. '
            f'Para corrigir um pagamento, estorne-o.')

    fechamento.status = 'ABERTO'
    fechamento.reaberto_por_id = getattr(usuario, 'id', None)
    db.session.flush()
    return fechamento


# ── F6 — Fluxo B: o adiantamento e a lista de espera ─────────────────

def registrar_adiantamento(pedido, *, valor, conta_pagar=None,
                           data_prevista_entrega=None, observacao=None):
    """Registra a pendência de ENTREGA de um adiantamento.

    O adiantamento em si JÁ é uma `ContaPagar` — paga-se por ela, ela vai ao
    fluxo de caixa, ela debita banco pela B5.6. Esta linha é a outra ponta, a
    que hoje não existe em lugar nenhum: o material ainda não chegou.

    N linhas por pedido, porque 50% na assinatura e 50% na entrega é o caso
    comum e não a exceção (D4).
    """
    from app import db
    from models import AdiantamentoFornecedor

    adto = AdiantamentoFornecedor(
        pedido_id=pedido.id, admin_id=pedido.admin_id,
        conta_pagar_id=getattr(conta_pagar, 'id', None),
        valor=_d(valor), data_prevista_entrega=data_prevista_entrega,
        observacao=observacao)
    db.session.add(adto)
    db.session.flush()
    return adto


def baixar_adiantamentos(pedido, *, usuario=None):
    """Baixa TODAS as pendências de entrega do pedido. Só o atesto chama isto.

    Baixa manual sem material é exatamente o buraco que a lista existe para
    tapar: se der para riscar a pendência sem nada ter chegado, a lista deixa
    de significar "aguardando entrega" e passa a significar "alguém lembrou de
    clicar".
    """
    from datetime import datetime
    from app import db
    from models import AdiantamentoFornecedor

    pendentes = AdiantamentoFornecedor.query.filter_by(
        pedido_id=pedido.id, baixado_em=None).all()
    if not pendentes:
        return []
    agora = datetime.utcnow()
    for a in pendentes:
        a.baixado_em = agora
        a.baixado_por_id = getattr(usuario, 'id', None)
    db.session.flush()
    return pendentes


def adiantamentos_pendentes(admin_id):
    """A lista "pago, aguardando entrega" do tenant."""
    from models import AdiantamentoFornecedor
    return (AdiantamentoFornecedor.query
            .filter_by(admin_id=admin_id, baixado_em=None)
            .order_by(AdiantamentoFornecedor.data_prevista_entrega).all())
