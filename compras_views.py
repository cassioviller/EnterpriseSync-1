import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from models import (AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
                    ContaPagar, EstadoRequisicao, Fornecedor, Funcionario,
                    MapaConcorrenciaV2, Obra, ObraServicoCusto, PedidoCompra,
                    PedidoCompraItem, RequisicaoCompra, RequisicaoCompraItem,
                    GestaoCustoPai, GestaoCustoFilho, Usuario)
from utils.tenant import get_tenant_admin_id, is_v2_active

# Fase 3 — governança de compras. Imports no topo de propósito: estes
# módulos não importam compras_views de volta, então não há ciclo.
from services.alcada_compras import (MOTIVO_FRACIONAMENTO, ROTULOS_DEGRAU,
                                     acumulado_da_etapa,
                                     acumulado_do_fornecedor,
                                     decisao_de_alcada,
                                     esta_totalmente_aprovada,
                                     garantir_faixas_do_tenant, faixa_efetiva,
                                     irmas_da_janela, janela_de_fracionamento,
                                     pendencias_de_aprovacao, pode_aprovar,
                                     registrar_aprovacao)
from services.requisicao_compra import (TransicaoInvalida, proximo_numero,
                                        recalcular_valor, transicionar)
from utils.autorizacao import (obras_visiveis, pode_comprar_na_obra,
                               pode_receber_na_obra, pode_requisitar_na_obra,
                               pode_ver_obra)

logger = logging.getLogger(__name__)

compras_bp = Blueprint('compras', __name__, url_prefix='/compras')

UPLOAD_FOLDER = os.path.join('static', 'uploads', 'compras')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'xml', 'webp'}

# Fase 4 — os rótulos das quatro situações de `PedidoCompra.situacao_recebimento`.
# O valor persistido é o do serviço (services/recebimento_pedido); aqui é só
# como ele aparece na tela.
SITUACOES_RECEBIMENTO = {
    'nao_recebido': 'Não recebido',
    'parcial': 'Recebido parcialmente',
    'recebido': 'Recebido',
    'encerrado_com_saldo': 'Encerrado com saldo',
}

CONDICOES = {
    'a_vista': 'À Vista',
    '30d': 'Boleto 30 dias',
    '60d': 'Boleto 60 dias',
    '90d': 'Boleto 90 dias',
    'cartao': 'Cartão de Crédito',
    'parcelado': 'Parcelado',
}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_v2():
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


def _admin_id():
    return get_tenant_admin_id()


def _regime_recebimento(admin_id):
    """O regime de recebimento a carimbar num pedido que nasce agora.

    Indireção de uma linha de propósito: os DOIS pontos que criam
    `PedidoCompra` (o POST avulso e a emissão a partir de requisição) chamam
    esta função em vez de ler a flag cada um por si. Duas leituras são duas
    chances de divergirem na regra — e a regra aqui decide se o estoque entra
    na emissão ou só no atesto.
    """
    from services.recebimento_pedido import regime_do_tenant
    return regime_do_tenant(admin_id)


def _fluxo_pagamento(admin_id, escolha=None):
    """O FLUXO de pagamento a carimbar num pedido que nasce agora.

    Irmã de `_regime_recebimento` acima, e pelo mesmo motivo: os dois pontos que
    criam `PedidoCompra` neste arquivo chamam uma função só, para que a regra não
    possa divergir entre eles.

    Fora do regime de dois fluxos devolve sempre `faturado` — inclusive se o POST
    trouxer 'adiantamento'. Ver services/financeiro_compra.fluxo_do_pedido_novo.
    """
    from services.financeiro_compra import fluxo_do_pedido_novo
    return fluxo_do_pedido_novo(admin_id, escolha)


def _regime_alcada(admin_id):
    """O regime de alçada a carimbar numa requisição que nasce agora.

    Terceira da série, e pelo mesmo motivo das duas de cima: quem cria a linha
    chama uma função, não lê a flag. Hoje o único ponto que cria
    `RequisicaoCompra` é `requisicao_nova_post` — a indireção existe para o dia
    em que for dois, que é exatamente o dia em que a regra divergiria.

    Import tardio como nas irmãs: a leitura da flag mora em `scripts/`, que
    não é importável no boot, e quem faz a ponte é
    `services.alcada_compras.regime_alcada_do_tenant`.
    """
    from services.alcada_compras import regime_alcada_do_tenant
    return regime_alcada_do_tenant(admin_id)


def _fornecedor_do_form(admin_id):
    """O `Fornecedor` ativo do tenant escolhido no formulário, ou None.

    Leniente de propósito: NÃO recusa, NÃO faz flash, NÃO redireciona. Existe
    porque a guarda 2 de `requisicao_emitir_pedido` precisa saber QUEM é o
    fornecedor antes de a validação estrita rodar — é o fornecedor que torna
    `fornecedor_novo` avaliável, e ela é a única das quatro condições que não
    existe no momento do envio (a requisição não tem fornecedor).

    Quem recusa continua sendo o bloco de validação da rota, no lugar em que
    sempre esteve e com as duas mensagens que sempre teve.
    """
    bruto = (request.form.get('fornecedor_id') or '').strip()
    try:
        fornecedor_id = int(bruto)
    except (TypeError, ValueError):
        return None
    return Fornecedor.query.filter_by(
        id=fornecedor_id, admin_id=admin_id, ativo=True).first()


def _mapas_elegiveis(admin_id, obra_ids):
    """Os MapaConcorrenciaV2 que podem servir de concorrência a uma requisição.

    Concluídos (mapa aberto é cotação em andamento, não concorrência fechada),
    do tenant, e SÓ das obras passadas — que já vêm filtradas por
    `obras_visiveis`, o predicado do escopo de obra da Fase 1.

    O `admin_id` entra no filtro mesmo quando as obras já são do tenant: é
    cinto e suspensório sobre o defeito mais caro deste repositório, e o custo
    é uma coluna a mais no WHERE. A rota que GRAVA o vínculo repete a
    conferência — oferecer certo e gravar sem checar seria confiar no HTML.
    """
    if not obra_ids:
        return []
    return (MapaConcorrenciaV2.query
            .filter(MapaConcorrenciaV2.admin_id == admin_id,
                    MapaConcorrenciaV2.obra_id.in_(obra_ids),
                    MapaConcorrenciaV2.status == 'concluido')
            .order_by(MapaConcorrenciaV2.obra_id,
                      MapaConcorrenciaV2.created_at.desc())
            .all())


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS DE PROCESSAMENTO — dois fluxos de compra
# ═════════════════════════════════════════════════════════════════════════════
#
# Fluxo 1 — `processar_compra_normal`:
#   - Gera GestaoCustoPai com tipo_categoria='MATERIAL' (uma por parcela)
#   - TODOS os GCPs nascem como status='PENDENTE', independente da condição de
#     pagamento (inclusive 'a_vista'). A baixa é feita manualmente em Contas a Pagar.
#   - Cria entrada no almoxarifado (AlmoxarifadoMovimento + AlmoxarifadoEstoque)
#     para itens vinculados ao catálogo.
#   - Usado tanto no POST inicial (tipo_compra='normal') como em compras
#     aprovação_cliente que tenham sido marcadas para esse fluxo alternativo
#     futuramente (hoje, só 'normal' dispara este helper).
#
# Fluxo 2 — `processar_compra_aprovada_cliente`:
#   - Só roda DEPOIS de o cliente aprovar no portal.
#   - Gera UM GestaoCustoPai com tipo_categoria='FATURAMENTO_DIRETO', status='PAGO',
#     valor_pago=valor_total, saldo=0. Esse GCP NÃO gera FluxoCaixa porque o
#     dinheiro vai direto do cliente ao fornecedor (faturamento direto).
#   - Cria entrada NO ALMOXARIFADO (movimento ENTRADA + lote de estoque) para
#     itens vinculados ao catálogo e uma SAÍDA imediata contra a obra (obra_id
#     do pedido, sem funcionario), reconhecendo o material como já consumido
#     no centro de custo da obra.
#   - Protegido por `processada_apos_aprovacao` — idempotente.
#
# Regras de segurança comuns:
#   - admin_id SEMPRE = pedido.admin_id (multi-tenant)
#   - todas as operações em uma única transação; rollback em exceção
#   - pedido_compra_id é setado em todos os AlmoxarifadoMovimento para o
#     handler de material_entrada do EventManager ignorar esses movimentos
#     (ele dedup por pedido_compra_id).
# ═════════════════════════════════════════════════════════════════════════════

def _gerar_entrada_almoxarifado(pedido, itens_validos, admin_id, usuario_id):
    """Cria AlmoxarifadoMovimento ENTRADA + AlmoxarifadoEstoque (lote) para cada
    item do pedido que esteja vinculado ao catálogo do almoxarifado.

    NÃO commita — o chamador é responsável pelo commit/rollback.
    Retorna lista de tuplas (movimento, estoque) criadas.

    Fase 4 — pedido com `exige_atesto` NÃO passa por aqui: o estoque dele
    nasce do atesto (services/recebimento_pedido.registrar_recebimento), com a
    quantidade que fisicamente chegou. Emitir não é receber; o caminhão ainda
    nem saiu quando esta função rodaria.

    O guard mora AQUI, e não nos dois chamadores, porque é aqui que a escrita
    acontece: um terceiro chamador nascer no futuro não reabre a dupla
    escrita por esquecimento. Ver o spec, seção "Como fica".
    """
    if getattr(pedido, 'exige_atesto', False):
        logger.info(
            f"[emissão] pedido={pedido.id} exige atesto — estoque não entra "
            f"agora, entra no recebimento")
        return []

    itens_catalogo = [(desc, qtd, preco, almox_id, subtotal)
                      for desc, qtd, preco, almox_id, subtotal in itens_validos
                      if almox_id]
    lote_ref = pedido.numero or f"PC-{pedido.id}"
    resultado = []
    for desc_item, qtd_item, preco_item, almox_id, _ in itens_catalogo:
        mov = AlmoxarifadoMovimento(
            item_id=almox_id,
            tipo_movimento='ENTRADA',
            quantidade=qtd_item,
            valor_unitario=preco_item,
            nota_fiscal=pedido.numero,
            observacao=f"Entrada automática compra {lote_ref}: {desc_item[:100]}",
            estoque_id=None,
            fornecedor_id=pedido.fornecedor_id,
            admin_id=admin_id,
            usuario_id=usuario_id,
            obra_id=pedido.obra_id,
            pedido_compra_id=pedido.id,
        )
        db.session.add(mov)
        db.session.flush()
        estq = AlmoxarifadoEstoque(
            item_id=almox_id,
            quantidade=qtd_item,
            quantidade_inicial=qtd_item,
            quantidade_disponivel=qtd_item,
            entrada_movimento_id=mov.id,
            valor_unitario=preco_item,
            status='DISPONIVEL',
            lote=lote_ref,
            obra_id=pedido.obra_id,
            admin_id=admin_id,
        )
        db.session.add(estq)
        db.session.flush()
        mov.estoque_id = estq.id
        resultado.append((mov, estq))
    return resultado


def _gerar_saida_almoxarifado(pedido, movs_entrada, admin_id, usuario_id, descricao):
    """Gera SAÍDA imediata para os estoques criados pela ENTRADA, baixando o
    saldo e marcando o lote como CONSUMIDO. Usado tanto em 'normal com obra'
    (consumo direto na obra) quanto em 'aprovacao_cliente' (faturamento direto).

    NÃO commita — o chamador cuida do commit.
    Retorna número de saídas geradas.
    """
    from datetime import datetime as _dt
    saidas = 0
    for mov_in, estq in movs_entrada:
        estq.quantidade_disponivel = 0
        estq.status = 'CONSUMIDO'
        estq.updated_at = _dt.utcnow()

        mov_out = AlmoxarifadoMovimento(
            item_id=mov_in.item_id,
            tipo_movimento='SAIDA',
            quantidade=mov_in.quantidade,
            valor_unitario=mov_in.valor_unitario,
            funcionario_id=None,
            obra_id=pedido.obra_id,
            observacao=descricao,
            estoque_id=estq.id,
            lote=estq.lote,
            admin_id=admin_id,
            usuario_id=usuario_id,
            pedido_compra_id=pedido.id,
        )
        db.session.add(mov_out)
        saidas += 1
    return saidas


def processar_compra_normal(pedido, itens_validos, admin_id, usuario_id):
    """Processa compra tipo='normal':
       - Cria GestaoCustoPai MATERIAL (N parcelas conforme condicao_pagamento)
       - Cria GestaoCustoFilho vinculado à obra (se obra_id)
       - Cria ENTRADA no almoxarifado para itens do catálogo
       - Se obra_id está definido → também cria SAÍDA imediata contra a obra
         (material reconhecido como consumido na obra).
         Sem obra_id → material fica em estoque (entrada only).

    NÃO commita — o chamador cuida do commit.
    """
    fornecedor = Fornecedor.query.get(pedido.fornecedor_id)
    obra = Obra.query.get(pedido.obra_id) if pedido.obra_id else None
    vencimentos = _vencimentos(
        pedido.data_compra, pedido.condicao_pagamento, pedido.parcelas,
        primeira_parcela=pedido.data_vencimento_primeira_parcela,
        intervalo_dias=pedido.intervalo_parcelas_dias,
    )
    n_parcelas = len(vencimentos)
    valor_total = float(pedido.valor_total)
    valor_parcela = round(valor_total / n_parcelas, 2)
    forn_nome = fornecedor.nome if fornecedor else 'Fornecedor'
    entidade_nome = obra.nome if obra else 'Sem obra'
    entidade_id = pedido.obra_id

    for idx, (data_venc, _) in enumerate(vencimentos, start=1):
        v = valor_parcela if idx < n_parcelas else round(valor_total - valor_parcela * (n_parcelas - 1), 2)
        desc_cp = f"Compra{(' NF ' + pedido.numero) if pedido.numero else ''} - {forn_nome}"
        if n_parcelas > 1:
            desc_cp += f" - Parcela {idx}/{n_parcelas}"

        gcp = GestaoCustoPai(
            admin_id=admin_id,
            tipo_categoria='MATERIAL',
            entidade_nome=entidade_nome,
            entidade_id=entidade_id,
            fornecedor_id=pedido.fornecedor_id,
            valor_total=v,
            valor_pago=0,
            saldo=v,
            status='PENDENTE',
            data_emissao=pedido.data_compra,
            data_vencimento=data_venc,
            data_pagamento=None,
            numero_documento=pedido.numero,
            numero_parcela=idx,
            total_parcelas=n_parcelas,
            observacoes=desc_cp[:300],
            responsavel_id=pedido.responsavel_id,
        )
        db.session.add(gcp)
        db.session.flush()

        # Fase 4 — `pedido.obra_id` é nullable e a rota aceita ausência com
        # `or None`. Compra de material de escritório é legítima; o que não
        # pode é o custo ficar sem destino.
        from utils.centro_custo import id_do_centro_administrativo
        gcf = GestaoCustoFilho(
            pai_id=gcp.id,
            admin_id=admin_id,
            data_referencia=pedido.data_compra,
            descricao=desc_cp[:300],
            valor=v,
            obra_id=pedido.obra_id,
            centro_custo_id=(None if pedido.obra_id
                             else id_do_centro_administrativo(admin_id, criar=True)),
            obra_servico_custo_id=pedido.obra_servico_custo_id,
            origem_tabela='pedido_compra',
            origem_id=pedido.id,
        )
        db.session.add(gcf)
        gcp.obra_id = pedido.obra_id

        # Task #11 — Arquitetura de duas camadas (sem dupla contagem):
        #   GCP (acima)  = camada de CUSTO: centro de custo da obra, DRE, relatórios.
        #   ContaPagar   = camada de OBRIGAÇÃO FINANCEIRA (payables): contas a pagar,
        #                  ~~fluxo de caixa~~, Fechamento de Pagamentos.
        # A tela de Contas a Pagar exclui GCPs de pedido_compra de custos_v2
        # porque esses já aparecem como ContaPagar na tabela principal.
        # Assim, cada tela consulta apenas sua camada e não há soma duplicada.
        #
        # ⚠️ REVOGADO EM PARTE — 06/08, D-B5.1(a) + D-B5.7(2) (apenso §10 de
        # docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md): a parte
        # "fluxo de caixa" desta divisão NUNCA valeu no código
        # (`calcular_fluxo_caixa` não lê ContaPagar em ponta nenhuma) e foi
        # revogada por decisão: `GestaoCustoPai` é a ÚNICA fonte da SAÍDA do
        # fluxo — previsto E realizado. Consequência declarada: compra paga
        # pela tela de Contas a Pagar NÃO gera realizado no fluxo de caixa; o
        # realizado de compra entra só quando paga pela Gestão de Custos.
        # ⚠️ Fase 2 do ciclo de compras — a construção da `ContaPagar` SAIU
        # deste laço. Ela agora nasce em
        # `services.financeiro_compra.criar_obrigacao`, chamada logo abaixo,
        # que reproduz campo a campo o que estava aqui e acrescenta uma coisa
        # só: `situacao_liberacao`. Com o regime desligado o resultado é
        # idêntico ao de antes — é o que o teste de paridade mede.
        #
        # O laço continua criando GCP e GCF: a camada de CUSTO não muda nesta
        # fase, e misturar as duas coisas num mesmo commit é o que torna
        # impossível dizer depois qual delas quebrou.

    # A camada de OBRIGAÇÃO, num lugar só. Ter dois pontos criando ContaPagar
    # de compra seria dois pontos onde a regra de liberação pode divergir.
    from services.financeiro_compra import criar_obrigacao
    criar_obrigacao(pedido)

    # Entrada automática no almoxarifado (ENTRADA + lote)
    movs_entrada = _gerar_entrada_almoxarifado(pedido, itens_validos, admin_id, usuario_id)

    # Se a compra tem obra, o material é imediatamente consumido nela
    # (saída automática contra a obra). Sem obra, fica em estoque.
    saidas = 0
    if pedido.obra_id and movs_entrada:
        lote_ref = pedido.numero or f"PC-{pedido.id}"
        saidas = _gerar_saida_almoxarifado(
            pedido, movs_entrada, admin_id, usuario_id,
            descricao=f"Consumo direto na obra — compra {lote_ref}",
        )

    logger.info(
        f"[compra normal] pedido={pedido.id} parcelas={n_parcelas} "
        f"entradas_almox={len(movs_entrada)} saidas_obra={saidas}"
    )


def processar_compra_aprovada_cliente(pedido, usuario_id):
    """Processa compra tipo='aprovacao_cliente' APÓS aprovação do cliente.

    Cria:
      - UM GestaoCustoPai com tipo_categoria='FATURAMENTO_DIRETO', status='PAGO'
        (NÃO gera FluxoCaixa — o dinheiro do cliente vai direto ao fornecedor)
      - UM GestaoCustoFilho vinculado à obra
      - ENTRADA no almoxarifado para itens de catálogo
      - SAÍDA imediata contra a obra (consumo reconhecido no centro de custo)

    Idempotente: se `pedido.processada_apos_aprovacao` já é True, retorna
    imediatamente sem fazer nada.

    NÃO commita — o chamador cuida do commit/rollback.
    Levanta exceção em caso de erro (chamador faz rollback).
    """

    if pedido.processada_apos_aprovacao:
        logger.info(f"[compra aprovada cliente] pedido={pedido.id} já processado, noop")
        return

    if pedido.tipo_compra != 'aprovacao_cliente':
        raise ValueError(
            f"processar_compra_aprovada_cliente chamado com pedido tipo_compra="
            f"{pedido.tipo_compra} (esperado 'aprovacao_cliente')"
        )

    admin_id = pedido.admin_id
    fornecedor = Fornecedor.query.get(pedido.fornecedor_id)
    obra = Obra.query.get(pedido.obra_id) if pedido.obra_id else None
    forn_nome = fornecedor.nome if fornecedor else 'Fornecedor'
    entidade_nome = obra.nome if obra else 'Sem obra'

    desc_cp = (
        f"Faturamento direto cliente"
        f"{(' NF ' + pedido.numero) if pedido.numero else ''} — {forn_nome}"
    )

    # 1) GestaoCustoPai FATURAMENTO_DIRETO (status=PAGO, não gera FluxoCaixa)
    gcp = GestaoCustoPai(
        admin_id=admin_id,
        tipo_categoria='FATURAMENTO_DIRETO',
        entidade_nome=entidade_nome,
        entidade_id=pedido.obra_id,
        fornecedor_id=pedido.fornecedor_id,
        valor_total=pedido.valor_total,
        valor_pago=pedido.valor_total,
        saldo=0,
        status='PAGO',
        data_emissao=pedido.data_compra,
        data_vencimento=pedido.data_compra,
        data_pagamento=pedido.data_compra,
        numero_documento=pedido.numero,
        numero_parcela=1,
        total_parcelas=1,
        observacoes=desc_cp[:300],
        responsavel_id=pedido.responsavel_id,
    )
    db.session.add(gcp)
    db.session.flush()

    # Fase 4 — FATURAMENTO_DIRETO é material que o CLIENTE paga direto ao
    # fornecedor DA OBRA. Sem obra ele não significa nada, então aqui não há
    # fallback administrativo: recusa. Exceção, não redirect: este é um
    # helper ("Levanta exceção em caso de erro (chamador faz rollback)"),
    # chamado inclusive pelo portal (portal_obras_views.py).
    if not pedido.obra_id:
        from services.destino_custo import DestinoIndefinido
        raise DestinoIndefinido(
            'Faturamento direto exige uma obra: é material que o cliente '
            'paga direto ao fornecedor da obra.')

    gcf = GestaoCustoFilho(
        pai_id=gcp.id,
        admin_id=admin_id,
        data_referencia=pedido.data_compra,
        descricao=desc_cp[:300],
        valor=pedido.valor_total,
        obra_id=pedido.obra_id,
        obra_servico_custo_id=pedido.obra_servico_custo_id,
        origem_tabela='pedido_compra',
        origem_id=pedido.id,
    )
    db.session.add(gcf)
    gcp.obra_id = pedido.obra_id

    # 2) Reconstituir itens_validos a partir dos PedidoCompraItem para gerar movimentos
    itens_pedido = PedidoCompraItem.query.filter_by(pedido_id=pedido.id).all()
    itens_validos = [
        (i.descricao, float(i.quantidade), float(i.preco_unitario),
         i.almoxarifado_item_id, float(i.subtotal))
        for i in itens_pedido
    ]
    movs_entrada = _gerar_entrada_almoxarifado(pedido, itens_validos, admin_id, usuario_id)

    # 3) SAÍDA imediata contra a obra (reconhecendo consumo faturamento direto)
    lote_ref = pedido.numero or f"PC-{pedido.id}"
    saidas = _gerar_saida_almoxarifado(
        pedido, movs_entrada, admin_id, usuario_id,
        descricao=f"Consumo faturamento direto — compra {lote_ref}",
    )

    pedido.processada_apos_aprovacao = True
    db.session.flush()

    logger.info(
        f"[compra aprovada cliente] pedido={pedido.id} GCP#{gcp.id} FATURAMENTO_DIRETO "
        f"criado; entradas={len(movs_entrada)} saidas={saidas}"
    )


def _vencimentos(data_compra, condicao, parcelas, primeira_parcela=None, intervalo_dias=None):
    """Gera lista de (data_vencimento, valor_parcela) para ContaPagar / GCP.

    Args:
        primeira_parcela: date opcional — data do primeiro vencimento (Task #11).
        intervalo_dias: int opcional — dias entre parcelas (default 30).
    """
    if not isinstance(data_compra, date):
        data_compra = date.today()

    mapa_dias = {'a_vista': 0, '30d': 30, '60d': 60, '90d': 90, 'cartao': 30}

    if condicao in mapa_dias:
        dias = mapa_dias[condicao]
        # Se data personalizada foi fornecida, usá-la; senão calcular como antes
        data_venc = primeira_parcela if primeira_parcela else (data_compra + timedelta(days=dias))
        return [(data_venc, None)]

    # parcelado → N datas
    parcelas = max(1, int(parcelas or 1))
    intervalo = int(intervalo_dias) if intervalo_dias else 30
    datas = []
    for i in range(1, parcelas + 1):
        if primeira_parcela:
            data_venc = primeira_parcela + timedelta(days=intervalo * (i - 1))
        else:
            data_venc = data_compra + timedelta(days=intervalo * i)
        datas.append((data_venc, None))
    return datas


# ─────────────────────────────────────────────
# LISTA
# ─────────────────────────────────────────────
@compras_bp.route('/')
@login_required
def index():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    filtro_fornecedor = request.args.get('fornecedor_id', type=int)
    filtro_data_inicio = request.args.get('data_inicio')
    filtro_data_fim = request.args.get('data_fim')

    query = PedidoCompra.query.filter_by(admin_id=admin_id).order_by(PedidoCompra.data_compra.desc())

    if filtro_fornecedor:
        query = query.filter_by(fornecedor_id=filtro_fornecedor)
    if filtro_data_inicio:
        query = query.filter(PedidoCompra.data_compra >= filtro_data_inicio)
    if filtro_data_fim:
        query = query.filter(PedidoCompra.data_compra <= filtro_data_fim)

    pedidos = query.limit(200).all()
    total_valor = sum(float(p.valor_total) for p in pedidos)

    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()

    return render_template(
        'compras/index.html',
        pedidos=pedidos,
        total_valor=total_valor,
        fornecedores=fornecedores,
        filtro_fornecedor=filtro_fornecedor,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim,
        CONDICOES=CONDICOES,
        SITUACOES_RECEBIMENTO=SITUACOES_RECEBIMENTO,
    )


# ─────────────────────────────────────────────
# APROVAÇÃO DO CLIENTE — lista de compras aguardando
# ─────────────────────────────────────────────
@compras_bp.route('/aprovacao')
@login_required
def aprovacao():
    """Lista compras do tipo 'aprovacao_cliente' agrupadas por status:
       - PENDENTE  : aguardando cliente aprovar no portal
       - APROVADO  : cliente aprovou (já processadas)
       - RECUSADO  : cliente recusou
    """
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    base = (
        PedidoCompra.query
        .filter_by(admin_id=admin_id, tipo_compra='aprovacao_cliente')
        .order_by(PedidoCompra.created_at.desc())
    )

    # Pendentes: AGUARDANDO_APROVACAO_CLIENTE (novo) + PENDENTE (legado) + NULL
    pendentes = base.filter(
        db.or_(
            PedidoCompra.status_aprovacao_cliente == 'AGUARDANDO_APROVACAO_CLIENTE',
            PedidoCompra.status_aprovacao_cliente == 'PENDENTE',
            PedidoCompra.status_aprovacao_cliente.is_(None),
        )
    ).all()
    aprovadas = base.filter(PedidoCompra.status_aprovacao_cliente == 'APROVADO').all()
    recusadas = base.filter(
        PedidoCompra.status_aprovacao_cliente.in_(['RECUSADO', 'REJEITADO'])
    ).all()

    total_pendente = sum(float(p.valor_total) for p in pendentes)
    total_aprovada = sum(float(p.valor_total) for p in aprovadas)

    return render_template(
        'compras/aprovacao.html',
        pendentes=pendentes,
        aprovadas=aprovadas,
        recusadas=recusadas,
        total_pendente=total_pendente,
        total_aprovada=total_aprovada,
        CONDICOES=CONDICOES,
    )


# ─────────────────────────────────────────────
# NOVA COMPRA — GET
# ─────────────────────────────────────────────
@compras_bp.route('/nova', methods=['GET'])
@login_required
def nova():
    guard = _check_v2()
    if guard:
        return guard

    from scripts.flag_compras_governanca import governanca_ativa

    if governanca_ativa(_admin_id()):
        flash('A governança de compras está ativa: comece pela requisição.',
              'info')
        return redirect(url_for('compras.requisicao_nova'))

    admin_id = _admin_id()
    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    itens_catalogo = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).order_by('nome').all()
    funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    funcionarios_json = [{'id': f.id, 'nome': f.nome} for f in funcionarios]
    # Usuários ativos do tenant para seleção de responsável
    usuarios = Usuario.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()

    return render_template(
        'compras/nova_compra.html',
        fornecedores=fornecedores,
        obras=obras,
        itens_catalogo=itens_catalogo,
        funcionarios=funcionarios,
        funcionarios_json=funcionarios_json,
        usuarios=usuarios,
        CONDICOES=CONDICOES,
        hoje=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# NOVA COMPRA — POST
# ─────────────────────────────────────────────
@compras_bp.route('/nova', methods=['POST'])
@login_required
def nova_post():
    guard = _check_v2()
    if guard:
        return guard

    # ── Fase 3 — governança de compras ────────────────────────────────────
    # Com `compras_governanca_ativa` ligada para o tenant, esta rota deixa
    # de ser um caminho para criar pedido: todo pedido tem que sair de uma
    # requisição aprovada (compras.requisicao_emitir_pedido), que grava
    # quem aprovou, quando e por quanto em requisicao_transicao.
    #
    # A flag existe porque desligar este atalho sem aviso travaria o
    # registro de compra de quem está em obra hoje. Default FALSE; liga-se
    # por tenant com scripts/flag_compras_governanca.py, e o runbook em
    # docs/fase-3-rollout.md diz em que ordem.
    from scripts.flag_compras_governanca import governanca_ativa

    if governanca_ativa(_admin_id()):
        flash('A governança de compras está ativa nesta empresa: todo pedido '
              'precisa sair de uma requisição aprovada. Abra a requisição, '
              'passe pela alçada e emita o pedido por lá.', 'warning')
        return redirect(url_for('compras.requisicao_nova'))

    admin_id = _admin_id()

    try:
        fornecedor_id_raw = request.form.get('fornecedor_id', '').strip()
        if not fornecedor_id_raw:
            flash('Selecione um fornecedor antes de salvar a compra. '
                  'Se nenhum aparece no menu, cadastre o primeiro fornecedor.', 'danger')
            return redirect(url_for('compras.nova'))
        try:
            fornecedor_id = int(fornecedor_id_raw)
        except (TypeError, ValueError):
            flash('Fornecedor inválido. Selecione um fornecedor pelo menu.', 'danger')
            return redirect(url_for('compras.nova'))

        # Defesa multi-tenant: garante que o fornecedor pertence ao admin logado
        from models import Fornecedor as _Fornecedor
        fornecedor_owner = _Fornecedor.query.filter_by(
            id=fornecedor_id, admin_id=admin_id, ativo=True
        ).first()
        if not fornecedor_owner:
            flash('Fornecedor não encontrado ou não pertence à sua conta. '
                  'Selecione um fornecedor da lista.', 'danger')
            return redirect(url_for('compras.nova'))

        data_compra = datetime.strptime(request.form.get('data_compra'), '%Y-%m-%d').date()
        condicao = request.form.get('condicao_pagamento', 'a_vista')
        parcelas = int(request.form.get('parcelas', 1))
        numero = request.form.get('numero', '').strip() or None
        observacoes = request.form.get('observacoes', '').strip() or None
        # Task #11 — Responsável e datas de parcela personalizadas
        responsavel_id_raw = request.form.get('responsavel_id', '').strip()
        responsavel_id = int(responsavel_id_raw) if responsavel_id_raw else None
        # Multi-tenant validation: responsavel must belong to this tenant
        if responsavel_id:
            resp_ok = Usuario.query.filter_by(id=responsavel_id, admin_id=admin_id).first()
            if not resp_ok:
                responsavel_id = None
        primeira_parcela_raw = request.form.get('data_primeira_parcela', '').strip()
        data_primeira_parcela = (
            datetime.strptime(primeira_parcela_raw, '%Y-%m-%d').date()
            if primeira_parcela_raw else None
        )
        intervalo_parcelas_raw = request.form.get('intervalo_parcelas_dias', '').strip()
        intervalo_parcelas_dias = int(intervalo_parcelas_raw) if intervalo_parcelas_raw else None
        obra_id = request.form.get('obra_id') or None
        if obra_id:
            try:
                obra_id = int(obra_id)
            except (TypeError, ValueError):
                flash('Obra inválida. Selecione uma obra pelo menu.', 'danger')
                return redirect(url_for('compras.nova'))
            # Defesa multi-tenant: garante que a obra pertence ao admin logado
            from models import Obra as _Obra
            obra_owner = _Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra_owner:
                flash('Obra não encontrada ou não pertence à sua conta. '
                      'Selecione uma obra da lista.', 'danger')
                return redirect(url_for('compras.nova'))

        # Etapa (ObraServicoCusto) opcional — só vale com obra; valida obra+tenant.
        osc_id = request.form.get('obra_servico_custo_id') or None
        if osc_id and obra_id:
            try:
                osc_id = int(osc_id)
            except (TypeError, ValueError):
                osc_id = None
            if osc_id:
                from models import ObraServicoCusto as _OSC
                if not _OSC.query.filter_by(
                        id=osc_id, obra_id=obra_id, admin_id=admin_id).first():
                    osc_id = None
        else:
            osc_id = None

        # Tipo de compra: 'normal' (default) ou 'aprovacao_cliente'
        tipo_compra = request.form.get('tipo_compra', 'normal').strip()
        if tipo_compra not in ('normal', 'aprovacao_cliente'):
            tipo_compra = 'normal'

        # Regra: 'aprovacao_cliente' EXIGE obra (o cliente aprova no portal da obra).
        if tipo_compra == 'aprovacao_cliente' and not obra_id:
            flash('Compras do tipo "Aprovação do Cliente" exigem uma obra '
                  '(o cliente aprova pelo portal da obra). Selecione uma obra.', 'danger')
            return redirect(url_for('compras.nova'))

        # Reembolso é incompatível com aprovação_cliente (o dinheiro vem do cliente,
        # ninguém está pagando do bolso)
        is_reembolso = request.form.get('is_reembolso') == 'true'
        if tipo_compra == 'aprovacao_cliente' and is_reembolso:
            flash('Compras com aprovação do cliente não podem ter reembolso. '
                  'Desmarque a opção de reembolso ou escolha tipo "Normal".', 'danger')
            return redirect(url_for('compras.nova'))

        # Itens da compra
        descricoes = request.form.getlist('item_descricao[]')
        quantidades = request.form.getlist('item_quantidade[]')
        precos = request.form.getlist('item_preco[]')
        almox_ids = request.form.getlist('item_almoxarifado_id[]')

        if not descricoes or not any(d.strip() for d in descricoes):
            flash('Adicione pelo menos um item à compra.', 'danger')
            return redirect(url_for('compras.nova'))

        # Upload do anexo
        anexo_url = None
        arquivo = request.files.get('anexo')
        if arquivo and arquivo.filename and _allowed_file(arquivo.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            nome_arquivo = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(arquivo.filename)}"
            caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
            arquivo.save(caminho)
            anexo_url = '/' + caminho.replace(os.sep, '/')

        # Calcular valor total
        valor_total = 0.0
        itens_validos = []
        for i, desc in enumerate(descricoes):
            desc = desc.strip()
            if not desc:
                continue
            qtd = float((quantidades[i] if i < len(quantidades) else '1').replace(',', '.') or '1')
            preco = float((precos[i] if i < len(precos) else '0').replace(',', '.') or '0')
            almox_id = almox_ids[i] if i < len(almox_ids) else ''
            almox_id = int(almox_id) if almox_id else None
            subtotal = round(qtd * preco, 2)
            valor_total += subtotal
            itens_validos.append((desc, qtd, preco, almox_id, subtotal))

        valor_total = round(valor_total, 2)

        # --- Pedido principal ---
        # Para tipo 'aprovacao_cliente', começa com status_aprovacao_cliente='PENDENTE'
        # e processada_apos_aprovacao=False; nenhuma GestaoCustoPai/movimento é criado
        # até o cliente aprovar no portal.
        pedido = PedidoCompra(
            numero=numero,
            fornecedor_id=fornecedor_id,
            data_compra=data_compra,
            obra_id=obra_id,
            obra_servico_custo_id=osc_id,
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=observacoes,
            anexo_url=anexo_url,
            tipo_compra=tipo_compra,
            processada_apos_aprovacao=False,
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE' if tipo_compra == 'aprovacao_cliente' else None,
            admin_id=admin_id,
            responsavel_id=responsavel_id,
            data_vencimento_primeira_parcela=data_primeira_parcela,
            intervalo_parcelas_dias=intervalo_parcelas_dias,
            # Fase 4 — o regime é carimbado no nascimento e não muda depois,
            # nem se a flag do tenant for desligada (services/recebimento_pedido).
            exige_atesto=_regime_recebimento(admin_id),
            # Fase 2 do ciclo de compras — mesmo contrato: o FLUXO de pagamento
            # é carimbado aqui e nunca reconsultado. Fora do regime novo a
            # escolha do formulário é ignorada (services/financeiro_compra), o
            # que impede um POST forjado de abrir um fluxo que o tenant não ligou.
            fluxo_pagamento=_fluxo_pagamento(
                admin_id, (request.form.get('fluxo_pagamento') or '').strip() or None),
        )
        db.session.add(pedido)
        db.session.flush()

        # --- Itens ---
        for desc, qtd, preco, almox_id, subtotal in itens_validos:
            item = PedidoCompraItem(
                pedido_id=pedido.id,
                almoxarifado_item_id=almox_id,
                descricao=desc,
                quantidade=qtd,
                preco_unitario=preco,
                subtotal=subtotal,
                admin_id=admin_id,
            )
            db.session.add(item)
        db.session.flush()

        # --- Bifurca por tipo_compra ---
        if tipo_compra == 'normal':
            processar_compra_normal(pedido, itens_validos, admin_id, current_user.id)
            db.session.commit()

            # Lançamento contábil automático V2 (só faz sentido p/ normal)
            try:
                from contabilidade_utils import gerar_lancamento_contabil_automatico
                forn = Fornecedor.query.get(fornecedor_id)
                gerar_lancamento_contabil_automatico(
                    admin_id=admin_id,
                    tipo_operacao='compra_material',
                    valor=float(valor_total),
                    data=data_compra,
                    descricao=f"Compra{(' NF ' + numero) if numero else ''} - {forn.nome if forn else 'Fornecedor'}",
                )
            except Exception as _e:
                logger.warning(f"[WARN] Lancamento contabil compra nao gerado: {_e}")

            # Reembolso a Funcionários V2 (só em compras normais)
            try:
                from utils.financeiro_integration import processar_reembolsos_form
                n_reimb = processar_reembolsos_form(
                    request_form=request.form,
                    admin_id=admin_id,
                    data_despesa=data_compra,
                    descricao_origem=f"Compra{(' NF ' + numero) if numero else ''}",
                    obra_id=obra_id,
                    centro_custo_id=(int(request.form.get('centro_custo_id'))
                                     if request.form.get('centro_custo_id') else None),
                    origem_tabela='pedido_compra',
                    origem_id=pedido.id,
                )
                if n_reimb:
                    db.session.commit()
                    logger.info(f"[OK] {n_reimb} reembolso(s) registrado(s) na compra {pedido.id}")
            except Exception as _re:
                logger.warning(f"[WARN] Reembolso compra nao processado: {_re}")

            if pedido.exige_atesto:
                # No regime novo o estoque NÃO entra aqui — entra no atesto.
                # Repetir a mensagem antiga faria quem lê não abrir a tela de
                # recebimento quando o caminhão chegasse, e o material ficaria
                # sem lançamento em lugar nenhum.
                flash('Compra registrada com sucesso! Custo e contas a pagar '
                      'gerados. O estoque entra quando o recebimento for '
                      'atestado na obra.', 'success')
            else:
                flash('Compra registrada com sucesso! Custo, contas a pagar e entrada no almoxarifado geradas.', 'success')

        else:  # tipo_compra == 'aprovacao_cliente'
            # Apenas persiste o pedido + itens. Custos e movimentos só serão criados
            # quando o cliente aprovar no portal (em portal_obras_views.aprovar_compra).
            db.session.commit()
            flash('Compra registrada e enviada para aprovação do cliente. '
                  'Nenhum custo ou movimento de estoque foi criado ainda — isso acontecerá '
                  'automaticamente quando o cliente aprovar no portal.', 'info')

        return redirect(url_for('compras.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao salvar pedido_compra: {e}")
        flash(f'Erro ao salvar compra: {str(e)}', 'danger')
        return redirect(url_for('compras.nova'))


# ─────────────────────────────────────────────
# DETALHE
# ─────────────────────────────────────────────
@compras_bp.route('/<int:pedido_id>')
@login_required
def detalhe(pedido_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()
    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido_id).all()
    custos_gestao = GestaoCustoFilho.query.filter_by(
        origem_tabela='pedido_compra', origem_id=pedido_id
    ).all()

    # Calcular quantidades já recebidas por almoxarifado_item_id
    from sqlalchemy import func as sqlfunc2
    rows_det = (
        db.session.query(
            AlmoxarifadoMovimento.item_id,
            sqlfunc2.sum(AlmoxarifadoMovimento.quantidade).label('qtd_tot'),
            sqlfunc2.max(AlmoxarifadoMovimento.id).label('last_mov_id'),
        )
        .filter_by(pedido_compra_id=pedido_id, tipo_movimento='ENTRADA', admin_id=admin_id)
        .group_by(AlmoxarifadoMovimento.item_id)
        .all()
    )
    qtd_recebida_detalhe = {r.item_id: float(r.qtd_tot or 0) for r in rows_det}
    last_mov_id_map = {r.item_id: r.last_mov_id for r in rows_det}
    # Carregar o movimento mais recente por item para mostrar data e qtd no template
    recebimento_por_item = {}
    for item_id, mov_id in last_mov_id_map.items():
        mov = AlmoxarifadoMovimento.query.get(mov_id)
        if mov:
            recebimento_por_item[item_id] = mov
    itens_recebidos_ids = set(qtd_recebida_detalhe.keys())

    # Itens do pedido que têm vínculo com o catálogo do almoxarifado
    tem_itens_almox = any(i.almoxarifado_item_id for i in itens)
    # todos_recebidos: baseado em quantidade total (suporta múltiplas linhas com mesmo item_id)
    qtd_total_por_item_pedido = {}
    for i in itens:
        if i.almoxarifado_item_id:
            qtd_total_por_item_pedido[i.almoxarifado_item_id] = (
                qtd_total_por_item_pedido.get(i.almoxarifado_item_id, 0.0) + float(i.quantidade or 0)
            )
    todos_recebidos = tem_itens_almox and all(
        qtd_recebida_detalhe.get(item_id, 0.0) >= qtd_total
        for item_id, qtd_total in qtd_total_por_item_pedido.items()
    )

    fornecedores = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by('nome').all()

    return render_template(
        'compras/detalhe.html',
        pedido=pedido,
        itens=itens,
        custos_gestao=custos_gestao,
        CONDICOES=CONDICOES,
        itens_recebidos_ids=itens_recebidos_ids,
        recebimento_por_item=recebimento_por_item,
        qtd_recebida_detalhe=qtd_recebida_detalhe,
        tem_itens_almox=tem_itens_almox,
        todos_recebidos=todos_recebidos,
        fornecedores=fornecedores,
        obras=obras,
        SITUACOES_RECEBIMENTO=SITUACOES_RECEBIMENTO,
        # A permissão é consultada AQUI, e não no template: botão verde que
        # responde 403 é pior que botão ausente, e é assim que os outros
        # botões desta tela já se comportam.
        pode_receber=pode_receber_na_obra(pedido.obra_id),
    )


@compras_bp.route('/<int:pedido_id>/comprovante')
@login_required
def comprovante(pedido_id):
    """Serve o comprovante ao usuário interno, escopado por tenant.

    Substitui o consumo de /persistent-uploads/<path> em compras/detalhe
    (triagem de 23/07, Anexo B — a rota aberta foi removida).
    """
    from flask import send_file
    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()
    from portal_obras_views import _arquivo_comprovante
    return send_file(_arquivo_comprovante(pedido))


# ─────────────────────────────────────────────
# RECEBIMENTO NA OBRA — Fase 4
# ─────────────────────────────────────────────
def _quantidade_do_form(valor):
    """Texto do formulário → `(Decimal, erro)`. Erro é mensagem para humano.

    Devolve o erro em vez de engolir. A versão anterior transformava tudo o
    que não entendia em `Decimal('0')` — e zero, nesta tela, significa "item
    que não veio nesta entrega". Um "3O" digitado com a letra O sumia da
    entrega, o recebimento era gravado sem aquele item, e o flash saía verde:
    quem estava no portão ia embora achando que tinha atestado o cimento.

    A vírgula é decimal, porque é o que o teclado brasileiro entrega. O ponto
    é decimal quando não pode ser milhar, milhar quando não pode ser decimal,
    e **recusado quando pode ser os dois**: "1.500" tanto vale mil e
    quinhentos quanto um e meio, e escolher errado entre eles erra por 1000×
    sem ninguém ver. Entre duas leituras dessas, perguntar é a única resposta
    honesta.

    Campo vazio continua sendo ausência, não erro: `(Decimal('0'), None)`.
    """
    from decimal import Decimal, InvalidOperation

    texto = (valor or '').strip()
    if not texto:
        return Decimal('0'), None

    bruto = texto.replace(' ', '').replace(' ', '')
    tem_virgula = ',' in bruto
    tem_ponto = '.' in bruto

    ilegivel = (Decimal('0'), (
        f'não deu para ler "{texto}" como quantidade. Digite só o número, '
        f'com vírgula no decimal (ex.: 30,5).'))

    if tem_virgula and tem_ponto:
        # "1.500,25" — com a vírgula presente, o ponto só pode ser milhar.
        inteiro, _, decimais = bruto.partition(',')
        if not _milhar_bem_formado(inteiro):
            return ilegivel
        normalizado = f'{inteiro.replace(".", "")}.{decimais}'
    elif tem_virgula:
        normalizado = bruto.replace(',', '.')
    elif tem_ponto:
        grupos = bruto.split('.')
        if len(grupos) > 2:
            # "1.500.000" é milhar; "30.5.0" não é número nenhum, e lê-lo
            # como 3050 seria a mesma adivinhação que este parser existe
            # para não fazer.
            if not _milhar_bem_formado(bruto):
                return ilegivel
            normalizado = bruto.replace('.', '')
        elif len(grupos[1]) == 3 and grupos[0].lstrip('+-').isdigit():
            # O caso ambíguo, e o único que recusamos por ambiguidade.
            milhar = _num_pt(bruto.replace('.', ''))
            decimal_ = _num_pt(bruto)
            return Decimal('0'), (
                f'"{texto}" pode ser {milhar} ou {decimal_}, e a diferença é '
                f'de mil vezes. Escreva {milhar} ou {decimal_} para não '
                f'restar dúvida.')
        else:
            normalizado = bruto
    else:
        normalizado = bruto

    try:
        quantidade = Decimal(normalizado)
    except InvalidOperation:
        return Decimal('0'), (
            f'não deu para ler "{texto}" como quantidade. Digite só o número, '
            f'com vírgula no decimal (ex.: 30,5).')

    if not quantidade.is_finite():
        # `Decimal('nan')` e `Decimal('inf')` não levantam no construtor, e
        # comparar NaN com zero levanta `InvalidOperation` lá adiante.
        return Decimal('0'), (
            f'"{texto}" não é uma quantidade. Digite só o número, com vírgula '
            f'no decimal (ex.: 30,5).')

    return quantidade, None


def _milhar_bem_formado(inteiro):
    """"1.500.000" sim, "30.5.0" não — os grupos depois do primeiro têm 3 dígitos.

    É o que separa milhar de digitação embolada. Sem esta checagem, "30.5.0"
    vira 3050 calado, que é o mesmo defeito que o parser existe para não ter.
    """
    grupos = inteiro.split('.')
    if len(grupos) < 2:
        return bool(grupos[0]) and grupos[0].lstrip('+-').isdigit()
    cabeca = grupos[0].lstrip('+-')
    return (cabeca.isdigit() and 1 <= len(cabeca) <= 3
            and all(g.isdigit() and len(g) == 3 for g in grupos[1:]))


def _num_pt(valor):
    """Decimal ou texto numérico → '1500' / '1,5', no formato de quem lê."""
    from decimal import Decimal, InvalidOperation
    try:
        return format(Decimal(str(valor)).normalize(), 'f').replace('.', ',')
    except InvalidOperation:
        return str(valor)


def _num_enxuto(valor):
    """Decimal('20.000') → '20'; Decimal('20.500') → '20.5'; zero → ''.

    A coluna é `Numeric(12,3)`, então tudo sai com três casas. Preencher o
    campo do celular com "20.000" faz quem recebe apagar caractere por
    caractere antes de digitar o número certo.
    """
    if not valor:
        return ''
    texto = format(Decimal(valor).normalize(), 'f')
    return texto


@compras_bp.route('/<int:pedido_id>/recebimento', methods=['GET', 'POST'])
@login_required
def recebimento(pedido_id):
    """A tela de quem recebe o caminhão no portão da obra.

    Substitui, para pedido do regime novo, o botão que hoje aceita o clique e
    não faz nada: o estoque desses pedidos já entrou na emissão, então a rota
    antiga calcula pendente=0 e sai calada. Aqui pedido legado é **recusado
    com a razão dita** — um no-op silencioso é pior que uma recusa, porque
    quem clicou acha que registrou.

    GET e POST na mesma rota porque é uma tela só, usada no celular: campo de
    quantidade por item já preenchido com o que falta, observação, e o par
    encerrar-saldo + motivo.
    """
    from flask import abort

    from services.recebimento_pedido import (RecebimentoInvalido,
                                             validar_estado_do_pedido,
                                             recebido_por_item,
                                             registrar_recebimento)

    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(
        id=pedido_id, admin_id=admin_id).first_or_404()

    if not pode_receber_na_obra(pedido.obra_id):
        abort(403)

    if not pedido.exige_atesto:
        flash('Este pedido é do regime antigo: o estoque dele já entrou na '
              'emissão da compra, e receber de novo o contaria em dobro. Use '
              'o botão de recebimento no estoque, na tela do pedido.', 'warning')
        return redirect(url_for('compras.detalhe', pedido_id=pedido_id))

    # A mesma regra do serviço, perguntada antes de a tela abrir: deixar
    # alguém preencher quantidade por item para levar a recusa no POST é
    # gastar o tempo de quem está com o caminhão parado no portão.
    try:
        validar_estado_do_pedido(pedido)
    except RecebimentoInvalido as e:
        flash(str(e), 'warning')
        return redirect(url_for('compras.detalhe', pedido_id=pedido_id))

    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido_id).all()
    acumulado = recebido_por_item(pedido)
    falta = {i.id: max(Decimal('0'), Decimal(str(i.quantidade or 0))
                       - acumulado.get(i.id, Decimal('0'))) for i in itens}

    if request.method == 'POST':
        linhas = []
        ilegiveis = []
        for i in itens:
            qtd, erro = _quantidade_do_form(request.form.get(f'qtd_{i.id}'))
            if erro:
                ilegiveis.append(f'"{i.descricao}": {erro}')
            elif qtd != 0:
                # Item ausente é item que não veio nesta entrega — e agora é
                # só isso: quantidade ilegível não vira mais zero e some.
                linhas.append((i.id, qtd))

        if ilegiveis:
            flash(' '.join(ilegiveis), 'danger')
            return redirect(url_for('compras.recebimento', pedido_id=pedido_id))

        data_txt = (request.form.get('data_recebimento') or '').strip()
        try:
            data_rec = (datetime.strptime(data_txt, '%Y-%m-%d').date()
                        if data_txt else date.today())
        except ValueError:
            data_rec = date.today()

        try:
            rec = registrar_recebimento(
                pedido, current_user, linhas, data_rec,
                observacao=(request.form.get('observacao') or '').strip() or None,
                encerra_saldo=bool(request.form.get('encerra_saldo')),
                motivo=(request.form.get('motivo_encerramento') or '').strip(),
                permitir_sobre_entrega=bool(
                    request.form.get('permitir_sobre_entrega')),
            )
        except RecebimentoInvalido as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('compras.recebimento', pedido_id=pedido_id))

        flash(f'Recebimento {rec.rotulo} registrado. Pedido agora: '
              f'{SITUACOES_RECEBIMENTO.get(pedido.situacao_recebimento, "—")}.',
              'success')
        return redirect(url_for('compras.detalhe', pedido_id=pedido_id))

    return render_template(
        'compras/recebimento.html',
        pedido=pedido,
        itens=itens,
        falta={item_id: _num_enxuto(qtd) for item_id, qtd in falta.items()},
        pedido_qtd={i.id: _num_enxuto(i.quantidade) for i in itens},
        recebido={item_id: _num_enxuto(qtd)
                  for item_id, qtd in acumulado.items()},
        recebimentos=pedido.recebimentos.all(),
        SITUACOES_RECEBIMENTO=SITUACOES_RECEBIMENTO,
        hoje=date.today().isoformat(),
    )


@compras_bp.route('/<int:pedido_id>/recebimento/<int:recebimento_id>/excluir',
                  methods=['POST'])
@login_required
def excluir_recebimento(pedido_id, recebimento_id):
    """Desfaz o ÚLTIMO recebimento do pedido, estornando o estoque que gerou.

    O serviço existe desde a R5 e não tinha por onde ser chamado: errar a
    quantidade é o erro mais comum de quem recebe caminhão no portão, e a
    única correção possível era acesso direto ao banco.

    Toda a regra (só o último, só enquanto o material estiver na prateleira,
    quem pode) vive em `services.recebimento_pedido.excluir_recebimento`. Esta
    rota só resolve o pedido, checa o tenant e mostra a mensagem que vier.
    """
    from flask import abort

    from models import RecebimentoPedido
    from services.recebimento_pedido import RecebimentoInvalido
    from services.recebimento_pedido import \
        excluir_recebimento as servico_excluir

    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(
        id=pedido_id, admin_id=admin_id).first_or_404()

    if not pode_receber_na_obra(pedido.obra_id):
        abort(403)

    recebimento = RecebimentoPedido.query.filter_by(
        id=recebimento_id, pedido_id=pedido.id, admin_id=admin_id).first_or_404()
    rotulo = recebimento.rotulo

    try:
        servico_excluir(recebimento, current_user)
    except RecebimentoInvalido as e:
        db.session.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('compras.recebimento', pedido_id=pedido_id))

    flash(f'Recebimento {rotulo} excluído, e o estoque que ele gerou foi '
          f'estornado. Pedido agora: '
          f'{SITUACOES_RECEBIMENTO.get(pedido.situacao_recebimento, "—")}.',
          'success')
    return redirect(url_for('compras.recebimento', pedido_id=pedido_id))


# ─────────────────────────────────────────────
# RECEBIMENTO NO ALMOXARIFADO — rota do regime antigo
# ─────────────────────────────────────────────
@compras_bp.route('/receber/<int:pedido_id>', methods=['POST'])
@login_required
def receber(pedido_id):
    """Registra o recebimento físico dos itens de um PedidoCompra no almoxarifado.

    Fase 4 — esta rota é do REGIME ANTIGO e não some: o estoque de pedido
    legado já entrou na emissão, e mudar isso reescreveria estoque histórico.
    Pedido com `exige_atesto` recebe pela tela nova (`compras.recebimento`).
    """
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()

    # A porta dos fundos da dupla escrita. O botão do detalhe já não aponta
    # para cá em pedido do regime novo, mas quem tiver a URL ainda pode
    # postar — e aqui a quantidade lançada é a INTEIRA, a mesma que o atesto
    # vai lançar quando o caminhão chegar.
    if pedido.exige_atesto:
        flash('Este pedido recebe por atesto: o estoque entra pela quantidade '
              'que chegar em cada entrega, na tela de recebimento.', 'warning')
        return redirect(url_for('compras.recebimento', pedido_id=pedido_id))

    itens = PedidoCompraItem.query.filter_by(pedido_id=pedido_id).all()
    itens_com_catalogo = [i for i in itens if i.almoxarifado_item_id]

    if not itens_com_catalogo:
        flash('Nenhum item deste pedido está vinculado ao catálogo do almoxarifado.', 'warning')
        return redirect(url_for('compras.detalhe', pedido_id=pedido_id))

    movimentos_criados = 0
    from sqlalchemy import func as sqlfunc
    # Quantidades já recebidas (somadas) por almoxarifado_item_id para este pedido
    rows_recebidos = (
        db.session.query(
            AlmoxarifadoMovimento.item_id,
            sqlfunc.sum(AlmoxarifadoMovimento.quantidade).label('qtd_recebida')
        )
        .filter_by(pedido_compra_id=pedido_id, tipo_movimento='ENTRADA', admin_id=admin_id)
        .group_by(AlmoxarifadoMovimento.item_id)
        .all()
    )
    qtd_recebida_por_item = {r.item_id: float(r.qtd_recebida or 0) for r in rows_recebidos}

    # Agregar quantidades totais pedidas por almoxarifado_item_id (suporta itens repetidos).
    # Usar último preço e primeira descrição do grupo para o movimento.
    from collections import OrderedDict
    itens_agregados = OrderedDict()
    for item in itens_com_catalogo:
        aid = item.almoxarifado_item_id
        if aid not in itens_agregados:
            itens_agregados[aid] = {
                'qtd_total': 0.0,
                'preco': float(item.preco_unitario or 0),
                'descricao': item.descricao,
            }
        itens_agregados[aid]['qtd_total'] += float(item.quantidade or 0)
        itens_agregados[aid]['preco'] = float(item.preco_unitario or 0)

    lote_ref = pedido.numero or f"PC-{pedido_id}"

    try:
        for almox_id, info in itens_agregados.items():
            qtd_total_pedido = info['qtd_total']
            qtd_ja_recebida = qtd_recebida_por_item.get(almox_id, 0.0)
            qtd_pendente = round(qtd_total_pedido - qtd_ja_recebida, 6)
            if qtd_pendente <= 0:
                logger.info(f"[SKIP] Item {almox_id}: já totalmente recebido ({qtd_ja_recebida}/{qtd_total_pedido})")
                continue

            preco_unit = info['preco']
            desc_item = info['descricao']

            # Um movimento por item_id consolidado
            movimento = AlmoxarifadoMovimento(
                item_id=almox_id,
                tipo_movimento='ENTRADA',
                quantidade=qtd_pendente,
                valor_unitario=preco_unit,
                nota_fiscal=pedido.numero,
                observacao=f"Recebimento Compra {lote_ref}: {desc_item[:100]}",
                estoque_id=None,
                fornecedor_id=pedido.fornecedor_id,
                admin_id=admin_id,
                usuario_id=current_user.id,
                obra_id=pedido.obra_id,
                pedido_compra_id=pedido_id,
            )
            db.session.add(movimento)
            db.session.flush()

            # Lote FIFO no estoque
            estoque = AlmoxarifadoEstoque(
                item_id=almox_id,
                quantidade=qtd_pendente,
                quantidade_inicial=qtd_pendente,
                quantidade_disponivel=qtd_pendente,
                entrada_movimento_id=movimento.id,
                valor_unitario=preco_unit,
                status='DISPONIVEL',
                lote=lote_ref,
                obra_id=pedido.obra_id,
                admin_id=admin_id,
            )
            db.session.add(estoque)
            db.session.flush()
            movimento.estoque_id = estoque.id
            movimentos_criados += 1

        db.session.commit()
        if movimentos_criados:
            flash(f'Recebimento registrado: {movimentos_criados} item(ns) lançado(s) no almoxarifado. '
                  f'Custo já reconhecido na compra — sem duplicação.', 'success')
        else:
            flash('Todos os itens já haviam sido recebidos anteriormente.', 'info')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Falha ao registrar recebimento do pedido {pedido_id}: {e}")
        flash(f'Erro ao registrar recebimento: {str(e)}', 'danger')

    return redirect(url_for('compras.detalhe', pedido_id=pedido_id))


# ─────────────────────────────────────────────
# EDIÇÃO DE LANÇAMENTO FINANCEIRO DE COMPRA
# ─────────────────────────────────────────────
@compras_bp.route('/lancamento/<int:gcp_id>/editar', methods=['POST'])
@login_required
def editar_lancamento(gcp_id):
    """Edita campos financeiros/vínculo de um GestaoCustoPai originado de compra,
    independentemente de estar PAGO ou PENDENTE.
    Campos permitidos: obra_id, data_vencimento, fornecedor_id, observacoes.
    """
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    gcp = GestaoCustoPai.query.filter_by(id=gcp_id, admin_id=admin_id).first_or_404()

    # Restrição de segurança: apenas GCPs originados de pedido_compra podem ser
    # editados por esta rota — evita edição acidental de outros lançamentos.
    filho_compra = GestaoCustoFilho.query.filter_by(
        pai_id=gcp_id, origem_tabela='pedido_compra'
    ).first()
    if not filho_compra:
        flash('Este lançamento não pode ser editado por esta rota.', 'danger')
        return redirect(request.referrer or url_for('compras.index'))

    try:
        obra_id_raw = request.form.get('obra_id', '').strip()
        obra_id = int(obra_id_raw) if obra_id_raw else None
        if obra_id:
            obra_check = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
            if not obra_check:
                flash('Obra não encontrada ou sem permissão.', 'danger')
                return redirect(request.referrer or url_for('compras.index'))
            gcp.entidade_nome = obra_check.nome
            gcp.entidade_id = obra_id
        else:
            gcp.entidade_nome = 'Sem obra'
            gcp.entidade_id = None

        data_venc_raw = request.form.get('data_vencimento', '').strip()
        if data_venc_raw:
            from datetime import datetime as _dt
            gcp.data_vencimento = _dt.strptime(data_venc_raw, '%Y-%m-%d').date()

        fornecedor_id_raw = request.form.get('fornecedor_id', '').strip()
        if fornecedor_id_raw:
            forn_id = int(fornecedor_id_raw)
            forn_check = Fornecedor.query.filter_by(id=forn_id, admin_id=admin_id).first()
            if forn_check:
                gcp.fornecedor_id = forn_id

        observacoes = request.form.get('observacoes', '').strip()
        gcp.observacoes = observacoes[:300] if observacoes else None

        # Sync GestaoCustoFilho obra_id
        for filho in gcp.itens:
            filho.obra_id = obra_id

        db.session.commit()
        flash('Lançamento atualizado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Falha ao editar lancamento GCP#{gcp_id}: {e}")
        flash('Não foi possível atualizar o lançamento. Tente novamente.', 'danger')

    return redirect(request.referrer or url_for('compras.index'))


# ─────────────────────────────────────────────
# EXCLUSÃO
# ─────────────────────────────────────────────
@compras_bp.route('/excluir/<int:pedido_id>', methods=['POST'])
@login_required
def excluir(pedido_id):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    pedido = PedidoCompra.query.filter_by(id=pedido_id, admin_id=admin_id).first_or_404()

    # Pedido com atesto gravado não é excluído por aqui. O cascade levaria a
    # trilha de recebimento junto (quem recebeu, quando, com que observação —
    # o controle compensatório pela ausência de segregação de funções),
    # enquanto ENTRADA, SAÍDA e lote sobreviveriam com `pedido_compra_id`
    # NULL, por ON DELETE SET NULL: estoque sem documento que explique de onde
    # veio. E todos os guards de `excluir_recebimento` — só o último, só
    # enquanto o material estiver na prateleira — ficariam contornados por
    # esta porta.
    quantos = pedido.recebimentos.count()
    if quantos:
        flash(f'Este pedido tem {quantos} recebimento(s) registrado(s), e o '
              f'estoque que eles geraram está no almoxarifado. Exclua os '
              f'recebimentos primeiro, do último para o primeiro — o estorno '
              f'acontece lá, com as conferências que ele faz.', 'danger')
        return redirect(url_for('compras.detalhe', pedido_id=pedido_id))

    try:
        # Remover GestaoCustoPai vinculados (criados via filho origem_tabela=pedido_compra)
        filhos = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=pedido_id
        ).all()
        pai_ids = list({f.pai_id for f in filhos})
        for pai_id in pai_ids:
            pai = GestaoCustoPai.query.get(pai_id)
            if pai and pai.status in ('PENDENTE', 'RECUSADO'):
                db.session.delete(pai)
        # Manter ContaPagar legados (histórico) mas não criar novos
        db.session.delete(pedido)
        db.session.commit()
        flash('Compra e custos vinculados foram excluídos.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {e}', 'danger')
    return redirect(url_for('compras.index'))


# ═════════════════════════════════════════════════════════════════════════════
# FASE 3 — REQUISIÇÃO DE COMPRA (requisição → aprovação → pedido)
# ═════════════════════════════════════════════════════════════════════════════
#
# Estas rotas existem SEMPRE. O que a flag `compras_governanca_ativa`
# muda é apenas se `POST /compras/nova` continua aceitando pedido sem
# requisição (Task 9). Com a flag desligada, este é um caminho opcional
# que não tira nada de ninguém.


def _requisicao_do_tenant(requisicao_id):
    """Carrega a requisição do tenant logado ou aborta com 404.

    404 e não 403, pela mesma razão do `obra_required` da Fase 1: não
    vazar sequer a existência de documento de outra empresa.
    """
    from flask import abort

    admin_id = _admin_id()
    if admin_id is None:
        abort(404)
    req = RequisicaoCompra.query.filter_by(
        id=requisicao_id, admin_id=admin_id).first()
    if req is None:
        abort(404)
    return req


def _itens_do_form():
    """Lê os itens do formulário. Devolve lista de dicts, ignorando linhas
    sem descrição (o formulário mantém uma linha-modelo vazia)."""
    descricoes = request.form.getlist('item_descricao[]')
    unidades = request.form.getlist('item_unidade[]')
    quantidades = request.form.getlist('item_quantidade[]')
    precos = request.form.getlist('item_preco[]')
    almox_ids = request.form.getlist('item_almoxarifado_id[]')

    itens = []
    for i, desc in enumerate(descricoes):
        desc = (desc or '').strip()
        if not desc:
            continue

        def _num(lista, idx, padrao='0'):
            bruto = (lista[idx] if idx < len(lista) else '') or padrao
            try:
                return float(str(bruto).replace('.', '').replace(',', '.')
                             if ',' in str(bruto) else str(bruto))
            except (TypeError, ValueError):
                # Entrada não-numérica ('abc', vazio malformado) não pode
                # virar HTTP 500 — vale 0 e a linha entra com valor zero,
                # que o usuário vê e corrige, em vez de perder o formulário.
                return 0.0

        almox_bruto = almox_ids[i] if i < len(almox_ids) else ''
        itens.append({
            'descricao': desc[:200],
            'unidade': ((unidades[i] if i < len(unidades) else '') or 'un')[:20],
            'quantidade': _num(quantidades, i, '1'),
            'preco': _num(precos, i, '0'),
            'almoxarifado_item_id': int(almox_bruto) if almox_bruto else None,
        })
    return itens


@compras_bp.route('/requisicoes')
@login_required
def requisicoes():
    """Lista de requisições do tenant, filtrada pelo escopo de obra."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    estado_filtro = (request.args.get('estado') or '').strip().upper()

    query = RequisicaoCompra.query.filter_by(admin_id=admin_id)

    # Fase 1 — escopo por obra. `obras_visiveis()` já aplica os dois eixos
    # (tenant sempre; obra só com a flag do tenant ligada). Sem isso, a
    # listagem repetiria o erro de `compras_views.py:421`, que filtra só
    # por admin_id.
    ids_visiveis = [o.id for o in obras_visiveis(admin_id).with_entities(Obra.id)]
    query = query.filter(RequisicaoCompra.obra_id.in_(ids_visiveis or [-1]))

    if estado_filtro in {e.name for e in EstadoRequisicao}:
        query = query.filter(RequisicaoCompra.estado ==
                             EstadoRequisicao[estado_filtro])

    requisicoes_lista = query.order_by(RequisicaoCompra.id.desc()).limit(200).all()

    # Contagem por estado vem de um agregado sobre TODAS as requisições
    # visíveis, não da lista limitada a 200 — senão os badges subcontam num
    # tenant com mais de 200 requisições. `query` já carrega os dois filtros
    # (tenant + escopo de obra); removo só o filtro de estado, se houver.
    from sqlalchemy import func
    contagem_base = (db.session.query(RequisicaoCompra.estado, func.count())
                     .filter(RequisicaoCompra.admin_id == admin_id)
                     .filter(RequisicaoCompra.obra_id.in_(ids_visiveis or [-1]))
                     .group_by(RequisicaoCompra.estado).all())
    contagem = {e.name: 0 for e in EstadoRequisicao}
    for estado, n in contagem_base:
        nome = estado.name if hasattr(estado, 'name') else str(estado)
        if nome in contagem:
            contagem[nome] = n

    return render_template(
        'compras/requisicoes.html',
        requisicoes=requisicoes_lista,
        contagem=contagem,
        estado_filtro=estado_filtro,
        estados=list(EstadoRequisicao),
    )


@compras_bp.route('/requisicoes/nova', methods=['GET'])
@login_required
def requisicao_nova():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = obras_visiveis(admin_id).filter(Obra.ativo.is_(True)).order_by(
        Obra.nome).all()
    itens_catalogo = AlmoxarifadoItem.query.filter_by(
        admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()

    return render_template(
        'compras/requisicao_nova.html',
        obras=obras,
        itens_catalogo=itens_catalogo,
        # Fase 3 — o campo que faltava. Sem ele, `exige_mapa_concorrencia`
        # tornava a faixa de topo um bloqueio permanente: a rota lia
        # `mapa_v2_id` do form e nenhum template tinha o input.
        mapas_elegiveis=_mapas_elegiveis(admin_id, [o.id for o in obras]),
        hoje=date.today().isoformat(),
    )


@compras_bp.route('/requisicoes/nova', methods=['POST'])
@login_required
def requisicao_nova_post():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    obra_id_bruto = (request.form.get('obra_id') or '').strip()
    if not obra_id_bruto:
        flash('Toda requisição precisa de uma obra. É o vínculo que faz o '
              'custo aparecer no lugar certo.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))
    try:
        obra_id = int(obra_id_bruto)
    except (TypeError, ValueError):
        flash('Obra inválida. Selecione uma obra pelo menu.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Defesa de tenant + escopo de obra (Fase 1) num só predicado.
    if not pode_ver_obra(obra_id):
        flash('Obra não encontrada ou fora do seu acesso.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))
    if not pode_requisitar_na_obra(obra_id):
        flash('Você não tem papel de gestor ou comprador nesta obra e não '
              'pode abrir requisição para ela.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Etapa opcional — mesma validação de pedido_compra (compras_views.py:597)
    osc_id_bruto = (request.form.get('obra_servico_custo_id') or '').strip()
    osc_id = None
    if osc_id_bruto:
        try:
            candidato = int(osc_id_bruto)
        except (TypeError, ValueError):
            candidato = None
        if candidato and ObraServicoCusto.query.filter_by(
                id=candidato, obra_id=obra_id, admin_id=admin_id).first():
            osc_id = candidato

    mapa_id_bruto = (request.form.get('mapa_v2_id') or '').strip()
    mapa_id = None
    if mapa_id_bruto:
        try:
            candidato = int(mapa_id_bruto)
        except (TypeError, ValueError):
            candidato = None
        if candidato and MapaConcorrenciaV2.query.filter_by(
                id=candidato, obra_id=obra_id, admin_id=admin_id).first():
            mapa_id = candidato

    itens = _itens_do_form()
    if not itens:
        flash('Adicione pelo menos um item à requisição.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    data_nec_bruta = (request.form.get('data_necessidade') or '').strip()
    try:
        data_necessidade = (datetime.strptime(data_nec_bruta, '%Y-%m-%d').date()
                            if data_nec_bruta else None)
    except ValueError:
        data_necessidade = None

    # Tenants criados depois da migration 243 não têm faixa; semeia aqui,
    # antes de existir requisição que dependa delas. COMMIT próprio: se o
    # loop de numeração abaixo der rollback numa colisão, o seed não pode ir
    # junto — senão a requisição persistiria sem faixa e cairia na faixa de
    # segurança, e o flash final anunciaria a alçada errada.
    if garantir_faixas_do_tenant(admin_id):
        db.session.commit()

    # Fase 3 (alçadas avançadas) — o regime é lido UMA vez, aqui, e carimbado
    # na linha. Fora do laço de retry de propósito: uma colisão de numeração
    # não é motivo para reconsultar a flag, e reler dentro do laço abriria a
    # porta para duas tentativas do MESMO request nascerem em regimes
    # diferentes.
    regime = _regime_alcada(admin_id)

    # Retry de numeração: o UNIQUE (admin_id, numero) fecha a corrida entre
    # dois requests simultâneos. Mesmo padrão de views/obras.py:3279.
    from sqlalchemy.exc import IntegrityError

    for tentativa in range(3):
        try:
            requisicao = RequisicaoCompra(
                numero=proximo_numero(admin_id),
                admin_id=admin_id,
                obra_id=obra_id,
                obra_servico_custo_id=osc_id,
                mapa_v2_id=mapa_id,
                solicitante_id=current_user.id,
                estado=EstadoRequisicao.RASCUNHO,
                regime_alcada=regime,
                justificativa=(request.form.get('justificativa') or '').strip() or None,
                data_necessidade=data_necessidade,
                valor_estimado=0,
            )
            db.session.add(requisicao)
            db.session.flush()

            for item in itens:
                db.session.add(RequisicaoCompraItem(
                    requisicao_id=requisicao.id,
                    admin_id=admin_id,
                    almoxarifado_item_id=item['almoxarifado_item_id'],
                    descricao=item['descricao'],
                    unidade=item['unidade'],
                    quantidade=item['quantidade'],
                    preco_estimado=item['preco'],
                ))
            db.session.flush()
            recalcular_valor(requisicao)
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            logger.warning('colisão de numeração de requisição no tenant %s '
                           '(tentativa %s)', admin_id, tentativa + 1)
    else:
        flash('Não foi possível gerar o número da requisição. Tente novamente.',
              'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Fase 3 (alçadas avançadas) — o ponto de EXIBIÇÃO lê a MESMA faixa que os
    # pontos de decisão vão cobrar. Anunciar aqui a faixa do valor e cobrar
    # depois a efetiva faria a tela prometer uma coisa e o envio exigir outra —
    # e o usuário descobriria a diferença já com a requisição parada.
    #
    # `faixa_efetiva` pode carimbar `degrau_aplicado` e NÃO commita, no mesmo
    # contrato de `registrar_aprovacao`: quem persiste é a rota, e é este
    # commit.
    faixa = faixa_efetiva(requisicao)
    db.session.commit()
    flash(f'Requisição {requisicao.numero} criada (R$ '
          f'{requisicao.valor_estimado}). Pela alçada configurada, ela vai '
          f'precisar de {faixa.aprovacoes_necessarias} aprovação(ões).',
          'success')
    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao.id))


@compras_bp.route('/requisicoes/<int:requisicao_id>')
@login_required
def requisicao_detalhe(requisicao_id):
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    from flask import abort
    if not pode_ver_obra(requisicao.obra_id):
        abort(404)

    # Fase 3 (alçadas avançadas) — as TRÊS coisas de uma vez só, do ponto
    # único de cálculo: a faixa pelo valor, a que vale de verdade e por que
    # elas diferem. Um cálculo só porque exibir e decidir têm de sair do mesmo
    # lugar; as três porque pendência sem motivo visível vira ligação para o
    # suporte.
    decisao = decisao_de_alcada(requisicao)
    faixa = decisao.efetiva
    pode, motivo_recusa = pode_aprovar(requisicao, current_user)

    # Fase 3 (A5) — o FATO que gerou a exigência, na mesma tela em que a
    # exigência aparece: as irmãs da janela, com número e valor. Aprovador que
    # lê "esta requisição subiu de faixa" e não vê quais compras somaram liga
    # para o suporte.
    #
    # Só em regime 'avancado': em requisição carimbada 'simples' o acumulado
    # não decide nada, e as duas queries seriam custo puro numa rota que é a
    # mais aberta do módulo.
    irmas, acumulado_etapa, janela_dias = [], None, None
    if requisicao.regime_alcada == 'avancado':
        janela_dias = janela_de_fracionamento(requisicao.admin_id)
        irmas = irmas_da_janela(requisicao, janela_dias)
        if irmas:
            acumulado_etapa = acumulado_da_etapa(requisicao, janela_dias)

    pedidos = PedidoCompra.query.filter_by(
        requisicao_id=requisicao.id).all() if hasattr(
            PedidoCompra, 'requisicao_id') else []

    return render_template(
        'compras/requisicao_detalhe.html',
        requisicao=requisicao,
        itens=requisicao.itens.all(),
        transicoes=requisicao.transicoes.all(),
        faixa=faixa,
        faixa_base=decisao.base,
        condicoes_do_degrau=decisao.condicoes,
        rotulos_degrau=ROTULOS_DEGRAU,
        # Fase 3 (A5) — as irmãs da janela e a soma delas.
        irmas_da_janela=irmas,
        acumulado_etapa=acumulado_etapa,
        janela_dias=janela_dias,
        pendencias=pendencias_de_aprovacao(requisicao),
        pode_aprovar=pode,
        motivo_recusa=motivo_recusa,
        pode_emitir=pode_comprar_na_obra(requisicao.obra_id),
        pedidos=pedidos,
        # Fase 3 — a pendência de mapa precisa ter saída NESTA tela: ou se
        # vincula um mapa concluído que já existe, ou se vai criar um na obra.
        # Quem descobre que falta mapa é quem abre o detalhe, não quem abriu o
        # formulário de criação.
        mapas_elegiveis=_mapas_elegiveis(requisicao.admin_id,
                                         [requisicao.obra_id]),
        EstadoRequisicao=EstadoRequisicao,
        fornecedores=Fornecedor.query.filter_by(
            admin_id=requisicao.admin_id, ativo=True).order_by(
                Fornecedor.nome).all(),
        CONDICOES=CONDICOES,
        hoje=date.today().isoformat(),
    )


@compras_bp.route('/requisicoes/<int:requisicao_id>/vincular-mapa',
                  methods=['POST'])
@login_required
def requisicao_vincular_mapa(requisicao_id):
    """Vincula (ou desvincula) o mapa de concorrência de uma requisição.

    Existe porque a pendência de mapa aparece no DETALHE, depois da criação:
    quem descobre que a faixa exige concorrência é o aprovador, e sem esta
    rota a única saída seria cancelar a requisição e abrir outra. Era metade
    do 🔴 da faixa de topo (📖 spec 2026-08-15-alcadas-design.md, "O que já
    existe", item 3).

    A conferência de `obra_id` e `admin_id` é feita AQUI, na rota, e não só em
    `services.alcada_compras.mapa_da_requisicao`: o serviço protege a decisão
    de alçada, mas quem impede que o vínculo indevido chegue a existir na
    linha é a rota. Isolamento entre empresas é o defeito mais caro deste
    repositório, e uma barreira só é uma barreira a menos do que o necessário.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Depois de virar pedido o mapa é registro histórico da decisão — trocá-lo
    # reescreveria a justificativa de uma compra já feita.
    if requisicao.estado not in (EstadoRequisicao.RASCUNHO,
                                 EstadoRequisicao.AGUARDANDO_APROVACAO):
        flash('O mapa só pode ser trocado enquanto a requisição está em '
              'rascunho ou aguardando aprovação.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    bruto = (request.form.get('mapa_v2_id') or '').strip()
    if not bruto:
        requisicao.mapa_v2_id = None
        db.session.commit()
        flash('Mapa de concorrência desvinculado da requisição.', 'info')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        candidato = int(bruto)
    except (TypeError, ValueError):
        candidato = None

    mapa = MapaConcorrenciaV2.query.filter_by(
        id=candidato, obra_id=requisicao.obra_id,
        admin_id=requisicao.admin_id, status='concluido').first() if candidato \
        else None

    if mapa is None:
        logger.warning('[fase3] vínculo de mapa recusado: requisicao=%s '
                       'mapa=%s tenant=%s obra=%s', requisicao_id, bruto,
                       requisicao.admin_id, requisicao.obra_id)
        flash('Mapa de concorrência não encontrado nesta obra, ou ainda não '
              'concluído. Só mapa concluído da própria obra serve de '
              'concorrência.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    requisicao.mapa_v2_id = mapa.id
    db.session.commit()
    flash(f'Mapa "{mapa.nome}" vinculado à requisição '
          f'({len(mapa.fornecedores)} cotações).', 'success')
    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/enviar', methods=['POST'])
@login_required
def requisicao_enviar(requisicao_id):
    """RASCUNHO → AGUARDANDO_APROVACAO."""
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Requisição sem item aprovada é assinatura em branco.
    if requisicao.itens.count() == 0:
        flash('Requisição sem itens não vai para aprovação.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    recalcular_valor(requisicao)

    # Fase 3 (A5) — o CHOKEPOINT do acumulado por etapa. Aqui a requisição
    # ainda não tem fornecedor (ele só é escolhido na emissão), e por isso o
    # acumulado que vale é o da `(obra, etapa)` na janela. `decisao_de_alcada`
    # carimba `fracionamento` em `degrau_aplicado` e NÃO commita — quem
    # persiste é o commit desta rota, junto com a transição, para que não haja
    # requisição enviada com trilha pela metade.
    decisao = decisao_de_alcada(requisicao)

    try:
        transicionar(requisicao, EstadoRequisicao.AGUARDANDO_APROVACAO,
                     current_user,
                     motivo=(request.form.get('motivo') or '').strip() or None)
        db.session.commit()
        aviso = ''
        if MOTIVO_FRACIONAMENTO in decisao.condicoes:
            dias = janela_de_fracionamento(requisicao.admin_id)
            # Quem envia precisa saber que a exigência mudou ANTES de sair
            # atrás de aprovação — descobrir depois é o que faz a requisição
            # parar sem ninguém entender por quê.
            aviso = (f' Atenção: o acumulado desta etapa nos últimos {dias} '
                     f'dias soma R$ {acumulado_da_etapa(requisicao):.2f}, e '
                     f'por isso ela passa a precisar de '
                     f'{decisao.efetiva.aprovacoes_necessarias} '
                     f'aprovação(ões).')
        flash(f'Requisição {requisicao.numero} enviada para aprovação.{aviso}',
              'warning' if aviso else 'success')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/cancelar', methods=['POST'])
@login_required
def requisicao_cancelar(requisicao_id):
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        transicionar(requisicao, EstadoRequisicao.CANCELADA, current_user,
                     motivo=(request.form.get('motivo') or '').strip() or None)
        db.session.commit()
        flash(f'Requisição {requisicao.numero} cancelada.', 'info')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/aprovar', methods=['POST'])
@login_required
def requisicao_aprovar(requisicao_id):
    """Registra UM voto de aprovação; move para APROVADA quando a alçada fecha.

    Um voto não é uma transição de estado: a faixa pode exigir dois. Por
    isso `registrar_aprovacao` grava a RequisicaoTransicao com
    `para_estado == estado atual` (voto) e só depois, se
    `esta_totalmente_aprovada`, é que `transicionar` roda de verdade.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    permitido, motivo = pode_aprovar(requisicao, current_user)
    if not permitido:
        flash(motivo, 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    observacao = (request.form.get('observacao') or '').strip() or None

    try:
        registrar_aprovacao(requisicao, current_user, observacao=observacao)

        if esta_totalmente_aprovada(requisicao):
            transicionar(requisicao, EstadoRequisicao.APROVADA, current_user,
                         motivo='alçada atendida')
            db.session.commit()
            flash(f'Requisição {requisicao.numero} APROVADA. Já pode virar '
                  f'pedido de compra.', 'success')
        else:
            db.session.commit()
            faltando = '; '.join(pendencias_de_aprovacao(requisicao))
            flash(f'Sua aprovação foi registrada. Ainda falta: {faltando}.',
                  'info')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error('[fase3] falha ao aprovar requisicao %s: %s',
                     requisicao_id, e, exc_info=True)
        flash('Não foi possível registrar a aprovação. Tente novamente.',
              'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/rejeitar', methods=['POST'])
@login_required
def requisicao_rejeitar(requisicao_id):
    """AGUARDANDO_APROVACAO → REJEITADA. Motivo obrigatório.

    Rejeitar sem motivo é a forma mais rápida de tornar a trilha inútil:
    seis meses depois ninguém sabe se a compra foi barrada por preço, por
    prazo ou por especificação errada.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    permitido, motivo_recusa = pode_aprovar(requisicao, current_user)
    if not permitido:
        flash(motivo_recusa, 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash('Informe o motivo da rejeição — sem ele o histórico não '
              'serve para nada.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        transicionar(requisicao, EstadoRequisicao.REJEITADA, current_user,
                     motivo=motivo[:2000])
        db.session.commit()
        flash(f'Requisição {requisicao.numero} rejeitada. O solicitante pode '
              f'corrigir e reenviar.', 'warning')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/emitir-pedido',
                  methods=['POST'])
@login_required
def requisicao_emitir_pedido(requisicao_id):
    """APROVADA → CONVERTIDA, criando o PedidoCompra.

    Este é o ponto em que a governança encontra o módulo que já existia: a
    partir daqui o fluxo é EXATAMENTE o de `compras.nova_post`
    (compras_views.py:668-711) — mesmo `PedidoCompra`, mesmos itens, mesmo
    `processar_compra_normal`. A diferença é que agora existe uma
    requisição aprovada por trás, com quem/quando/valor gravados.

    Três guardas, nesta ordem:
      1. estado APROVADA (senão a alçada não valeu de nada);
      2. quem emite não pode ter sido aprovador — quando a faixa exigiu
         mais de uma aprovação;
      3. o valor do pedido não pode ultrapassar o valor aprovado, senão
         aprova-se R$ 50 e compra-se R$ 5.000.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)
    admin_id = requisicao.admin_id

    if not pode_comprar_na_obra(requisicao.obra_id):
        flash('Você não tem papel de comprador nesta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Guarda 1 — só requisição aprovada vira pedido.
    if requisicao.estado != EstadoRequisicao.APROVADA:
        flash(f'A requisição está em {requisicao.estado.value}. Só se emite '
              f'pedido a partir de requisição aprovada.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Guarda 2 — separação de funções. Só vale quando a faixa exigiu mais
    # de uma aprovação: numa faixa de aprovação única, exigir uma terceira
    # pessoa para clicar em "emitir" travaria a compra de R$ 200 numa
    # equipe de três.
    #
    # Fase 3 (alçadas avançadas) — a faixa aqui é a EFETIVA, e este é o único
    # ponto do sistema que consegue avaliar `fornecedor_novo`: a requisição não
    # tem fornecedor, ele é escolhido neste formulário. A resolução abaixo é
    # deliberadamente LENIENTE (devolve None em vez de recusar) porque a
    # validação de verdade continua no lugar em que sempre esteve, mais
    # abaixo, com as duas mensagens que ela sempre teve — mudar a ordem das
    # recusas mudaria a mensagem que o usuário vê por um motivo que não é dele.
    from services.alcada_compras import votos_de_aprovacao

    fornecedor_escolhido = _fornecedor_do_form(admin_id)
    decisao = decisao_de_alcada(requisicao, fornecedor=fornecedor_escolhido)
    faixa = decisao.efetiva
    aprovadores = {v.usuario_id for v in votos_de_aprovacao(requisicao)}
    if faixa.aprovacoes_necessarias > 1 and current_user.id in aprovadores:
        flash('Você aprovou esta requisição e por isso não pode emitir o '
              'pedido dela. Peça a outra pessoa com papel de comprador.',
              'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Guarda 2b — anti-fracionamento POR FORNECEDOR (A5, decisão D3).
    #
    # É aqui, e só aqui, que o acumulado do fornecedor pode aparecer: a
    # requisição foi aprovada pela faixa do valor dela, sem saber de quem ia
    # vender. Se o que este fornecedor já levou desta obra na janela põe a
    # compra numa faixa mais exigente do que as aprovações que a requisição
    # tem, a emissão NÃO sai calada.
    #
    # D3 é DEGRAU, não bloqueio, e a diferença está em três coisas desta
    # guarda: a aprovação já dada continua valendo (o estado segue APROVADA,
    # nada é revertido); a trilha é gravada e COMMITADA, para que quem for
    # reaprovar veja o motivo; e a mensagem diz o que fazer. Recusar sem saída
    # empurra a compra para fora do sistema, que é exatamente o que a fase
    # quer evitar.
    #
    # Depois da guarda 2 de propósito: quando as duas valem, a separação de
    # funções é a recusa mais estrutural, e trocar a ordem trocaria a mensagem
    # que o usuário vê por um motivo que não é dele.
    # `fornecedor_escolhido is not None` não é defensividade: sem fornecedor
    # válido a decisão acima caiu no acumulado da ETAPA, e recusar aqui com uma
    # mensagem sobre fornecedor seria mentir. Quem trata o fornecedor inválido
    # é a validação de sempre, logo abaixo, com a mensagem de sempre.
    if fornecedor_escolhido is not None and \
            MOTIVO_FRACIONAMENTO in decisao.condicoes:
        pendentes = pendencias_de_aprovacao(
            requisicao, fornecedor=fornecedor_escolhido)
        if pendentes:
            dias = janela_de_fracionamento(admin_id)
            acumulado = acumulado_do_fornecedor(
                admin_id, requisicao.obra_id, fornecedor_escolhido.id, dias)
            # O carimbo do `fracionamento` fica gravado mesmo com a emissão
            # recusada: sem ele, quem abrir a requisição depois vê a exigência
            # e não vê o fato que a gerou.
            db.session.commit()
            flash(f'Este fornecedor já recebeu R$ {acumulado:.2f} desta obra '
                  f'nos últimos {dias} dias. Somada a esse acumulado, a compra '
                  f'cai numa faixa que pede '
                  f'{faixa.aprovacoes_necessarias} aprovação(ões) — a '
                  f'requisição {requisicao.numero} tem menos que isso, e '
                  f'segue APROVADA (a aprovação já dada continua valendo). '
                  f'Falta: {"; ".join(pendentes)}. Para seguir: rejeite a '
                  f'requisição, volte-a para rascunho e reenvie para aprovação '
                  f'na faixa nova, ou emita este pedido com outro fornecedor.',
                  'danger')
            logger.warning('[fase3] emissão recusada por fracionamento: '
                           'requisicao=%s fornecedor=%s acumulado=%s janela=%s',
                           requisicao.numero, fornecedor_escolhido.id,
                           acumulado, dias)
            return redirect(url_for('compras.requisicao_detalhe',
                                    requisicao_id=requisicao_id))

    # Idempotência — a requisição só produz um pedido.
    if PedidoCompra.query.filter_by(requisicao_id=requisicao.id).count() > 0:
        flash('Esta requisição já gerou um pedido de compra.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # ── Fornecedor (obrigatório, mesmo predicado de compras_views.py:552) ──
    forn_bruto = (request.form.get('fornecedor_id') or '').strip()
    try:
        fornecedor_id = int(forn_bruto)
    except (TypeError, ValueError):
        flash('Selecione um fornecedor para emitir o pedido.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))
    # Mesmo predicado de antes, resolvido uma vez só: `_fornecedor_do_form`
    # já procurou o fornecedor ativo deste tenant para a guarda 2.
    if fornecedor_escolhido is None:
        flash('Fornecedor não encontrado ou não pertence à sua conta.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    data_bruta = (request.form.get('data_compra') or '').strip()
    try:
        data_compra = (datetime.strptime(data_bruta, '%Y-%m-%d').date()
                       if data_bruta else date.today())
    except ValueError:
        data_compra = date.today()

    condicao = request.form.get('condicao_pagamento', 'a_vista')
    try:
        parcelas = max(1, int(request.form.get('parcelas', 1)))
    except (TypeError, ValueError):
        parcelas = 1

    # ── Itens: da requisição, com preço real opcional ──────────────────────
    # O comprador fecha o preço com o fornecedor; se o campo vier vazio,
    # vale o preço estimado da requisição.
    precos_reais = request.form.getlist('item_preco_real[]')
    itens_requisicao = requisicao.itens.order_by(RequisicaoCompraItem.id).all()

    itens_validos = []
    valor_total = 0.0
    for idx, item in enumerate(itens_requisicao):
        bruto = (precos_reais[idx] if idx < len(precos_reais) else '') or ''
        bruto = str(bruto).strip()
        if bruto:
            try:
                preco = float(bruto.replace('.', '').replace(',', '.')
                              if ',' in bruto else bruto)
            except ValueError:
                preco = float(item.preco_estimado or 0)
        else:
            preco = float(item.preco_estimado or 0)
        qtd = float(item.quantidade or 0)
        subtotal = round(qtd * preco, 2)
        valor_total += subtotal
        itens_validos.append((item.descricao, qtd, preco,
                              item.almoxarifado_item_id, subtotal))
    valor_total = round(valor_total, 2)

    # Guarda 3 — o pedido não pode estourar o que foi aprovado.
    from decimal import Decimal as _D
    aprovado = _D(str(requisicao.valor_estimado or 0))
    if _D(str(valor_total)) > aprovado:
        flash(f'O pedido soma R$ {valor_total:.2f}, acima dos R$ {aprovado} '
              f'aprovados. Volte a requisição para rascunho, corrija os '
              f'valores e passe pela alçada de novo.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        pedido = PedidoCompra(
            numero=(request.form.get('numero') or '').strip() or None,
            fornecedor_id=fornecedor_id,
            data_compra=data_compra,
            # Obra e etapa vêm da REQUISIÇÃO, não do formulário. É o que
            # torna o vínculo obrigatório de fato: não há campo para
            # esvaziar.
            obra_id=requisicao.obra_id,
            obra_servico_custo_id=requisicao.obra_servico_custo_id,
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=f'Emitido a partir da requisição {requisicao.numero}',
            tipo_compra='normal',
            processada_apos_aprovacao=False,
            status_aprovacao_cliente=None,
            admin_id=admin_id,
            responsavel_id=current_user.id,
            requisicao_id=requisicao.id,
            # Fase 4 — idem ao POST avulso: mesma função, mesmo carimbo.
            exige_atesto=_regime_recebimento(admin_id),
            # Fase 2 do ciclo de compras — idem. A escolha do fluxo vem do
            # formulário de emissão do pedido, não da requisição: quem requisita
            # pede material, quem emite negocia a forma de pagar.
            fluxo_pagamento=_fluxo_pagamento(
                admin_id, (request.form.get('fluxo_pagamento') or '').strip() or None),
        )
        db.session.add(pedido)
        db.session.flush()

        for desc, qtd, preco, almox_id, subtotal in itens_validos:
            db.session.add(PedidoCompraItem(
                pedido_id=pedido.id,
                almoxarifado_item_id=almox_id,
                descricao=desc,
                quantidade=qtd,
                preco_unitario=preco,
                subtotal=subtotal,
                admin_id=admin_id,
            ))
        db.session.flush()

        # Mesmíssimo processamento do fluxo antigo — GCP + ContaPagar por
        # parcela + entrada/saída de almoxarifado (compras_views.py:162).
        processar_compra_normal(pedido, itens_validos, admin_id, current_user.id)

        transicionar(requisicao, EstadoRequisicao.CONVERTIDA, current_user,
                     motivo=f'pedido de compra #{pedido.id} emitido')
        db.session.commit()

        flash(f'Pedido de compra emitido a partir da requisição '
              f'{requisicao.numero}. Custo, contas a pagar e entrada no '
              f'almoxarifado gerados.', 'success')
        return redirect(url_for('compras.detalhe', pedido_id=pedido.id))

    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error('[fase3] falha ao emitir pedido da requisicao %s: %s',
                     requisicao_id, e, exc_info=True)
        flash('Não foi possível emitir o pedido. Nada foi gravado.', 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))
