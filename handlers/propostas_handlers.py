"""
Handler de Eventos - Propostas Comerciais
Integração automática: Propostas → Contabilidade → Contas a Receber
"""

from event_manager import event_handler
from models import db, LancamentoContabil, PartidaContabil
from decimal import Decimal
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


def _linhagem_de_proposta(proposta, admin_id: int) -> list:
    """Fase 0.6 / D1 — a proposta e todas as versões que a antecederam.

    Uma revisão é uma linha NOVA em `propostas_comerciais`, ligada à anterior
    por `proposta_origem_id` (`propostas_consolidated.py:1310`). Sem percorrer
    a cadeia, cada aprovação parecia a primeira.
    """
    from models import Proposta
    linhagem, atual, vistos = [], proposta, set()
    while atual is not None and atual.id not in vistos:
        vistos.add(atual.id)
        linhagem.append(atual)
        origem_id = getattr(atual, 'proposta_origem_id', None)
        atual = (Proposta.query.filter_by(id=origem_id, admin_id=admin_id).first()
                 if origem_id else None)
    return linhagem


def _chaves_de_linhagem(item) -> list:
    """Identidades de um item ATRAVÉS das versões da proposta, em ordem de
    confiança.

    1. **Raiz da linhagem.** `proposta_item_origem_id` aponta sempre para o
       item ORIGINAL (o clone propaga a raiz, não o pai imediato), então a
       raiz é `proposta_item_origem_id or id`. Para o item da v1 isso dá o
       próprio id; para o clone dele na v2, o mesmo id. É o que faz as duas
       versões casarem.
    2. **`item_numero`.** Fallback para as revisões criadas ANTES da Fase 0.6,
       cujo `proposta_item_origem_id` é NULL nos dois lados — a raiz de cada
       um seria o próprio id e nunca casariam. O clone sempre copiou o
       `item_numero` fielmente.

    Devolver as duas e casar na ordem evita o erro sutil de usar chaves de
    tipos diferentes nos dois lados da comparação.
    """
    raiz = getattr(item, 'proposta_item_origem_id', None) or item.id
    return [('raiz', raiz), ('numero', item.item_numero)]


def _propagar_proposta_para_obra(proposta_id: int, admin_id: int):
    """Task #82: ao aprovar proposta, materializar cada PropostaItem como
    ItemMedicaoComercial na obra vinculada (se houver). O listener after_insert
    em ItemMedicaoComercial cria automaticamente o ObraServicoCusto pareado
    (valor_orcado = valor_comercial; servico_catalogo_id = servico_id).

    Fase 0.6 / D1 — **a revisão reconcilia, não acumula.**

    A idempotência era por `proposta_item_id`. Criar uma revisão CLONA os
    itens com ids novos, então a chave nunca casava com os itens da versão
    anterior: aprovar a v2 criava um SEGUNDO conjunto completo de itens de
    medição, e o listener criava o custo pareado de cada um. Medido em 21/07
    com v1 de R$ 100k e v2 de R$ 120k: 2 itens somando R$ 220.000 para um
    contrato de R$ 120.000, e saldo de -R$ 100.000 em `medicao_views.py:72`.

    Agora o item da revisão ATUALIZA o item de medição que já existe (mesmo
    `id`, então as medições já feitas contra ele continuam válidas) e só cria
    o que é genuinamente novo no escopo.
    """
    from models import Proposta, PropostaItem, ItemMedicaoComercial
    proposta = Proposta.query.filter_by(id=proposta_id, admin_id=admin_id).first()
    if not proposta or not getattr(proposta, 'obra_id', None):
        logger.info(f"#82: proposta {proposta_id} sem obra vinculada — pular propagação")
        return 0
    obra_id = proposta.obra_id

    itens = PropostaItem.query.filter_by(proposta_id=proposta_id).all()
    if not itens:
        return 0

    # Itens de TODAS as versões desta proposta, indexados pela identidade que
    # atravessa versões.
    ids_linhagem = [p.id for p in _linhagem_de_proposta(proposta, admin_id)]
    itens_linhagem = PropostaItem.query.filter(
        PropostaItem.proposta_id.in_(ids_linhagem)).all()
    item_por_id = {i.id: i for i in itens_linhagem}

    # ItemMedicaoComercial já materializados a partir de qualquer versão.
    imcs = ItemMedicaoComercial.query.filter(
        ItemMedicaoComercial.admin_id == admin_id,
        ItemMedicaoComercial.obra_id == obra_id,
        ItemMedicaoComercial.proposta_item_id.in_(list(item_por_id)),
    ).all()
    # Cada IMC é indexado por TODAS as chaves do item que o originou, para
    # que o casamento funcione tanto na linhagem explícita quanto no
    # fallback por item_numero das revisões antigas.
    imc_por_chave = {}
    for imc in imcs:
        origem = item_por_id.get(imc.proposta_item_id)
        if origem is None:
            continue
        for chave in _chaves_de_linhagem(origem):
            imc_por_chave.setdefault(chave, imc)

    def _casar(item):
        for chave in _chaves_de_linhagem(item):
            achado = imc_por_chave.get(chave)
            if achado is not None:
                return achado
        return None

    criados = atualizados = 0
    for it in itens:
        # Strict 1:1: um ItemMedicaoComercial por PropostaItem.
        # Se nome estiver vazio, fallback para "Item N"; se valor for 0,
        # materializa assim mesmo (operador pode ajustar depois).
        nome_item = (getattr(it, 'descricao', None) or getattr(it, 'item', None) or '').strip()
        if not nome_item:
            nome_item = f'Item {getattr(it, "item_numero", None) or getattr(it, "ordem", None) or it.id}'
        valor_total = Decimal(str(it.subtotal or 0))
        if valor_total < 0:
            valor_total = Decimal('0')
        quantidade = (Decimal(str(it.quantidade or 0))
                      if getattr(it, 'quantidade', None) is not None else None)

        existente = _casar(it)
        if existente is not None:
            if existente.proposta_item_id == it.id:
                continue  # mesma versão reaprovada — nada a fazer
            existente.nome = nome_item[:200]
            existente.valor_comercial = valor_total
            existente.servico_id = getattr(it, 'servico_id', None)
            existente.quantidade = quantidade
            existente.proposta_item_id = it.id
            atualizados += 1
            continue

        db.session.add(ItemMedicaoComercial(
            admin_id=admin_id,
            obra_id=obra_id,
            nome=nome_item[:200],
            valor_comercial=valor_total,
            servico_id=getattr(it, 'servico_id', None),
            quantidade=quantidade,
            proposta_item_id=it.id,
            status='PENDENTE',
        ))
        criados += 1

    # Itens que existiam numa versão anterior e sumiram desta NÃO são
    # apagados: podem ter medição executada contra eles, e retirar escopo já
    # medido é decisão de negócio (Fase 6 — orçamento versionado e aditivo).
    # Mas o silêncio seria pior do que o aviso.
    imcs_atuais = {id(_casar(i)) for i in itens} - {id(None)}
    orfaos = {id(imc): imc for imc in imc_por_chave.values()
              if id(imc) not in imcs_atuais}
    orfaos = list(orfaos.values())
    if orfaos:
        logger.warning(
            f"#82/D1: proposta {proposta_id} (obra {obra_id}) removeu "
            f"{len(orfaos)} item(ns) que existiam na versão anterior: "
            f"{[i.id for i in orfaos]}. Mantidos — retirar escopo já medido "
            f"é decisão de negócio, não do handler."
        )

    if criados or atualizados:
        db.session.flush()
        logger.info(
            f"#82: obra {obra_id} (proposta {proposta_id}) — "
            f"{criados} ItemMedicaoComercial criado(s), "
            f"{atualizados} atualizado(s) pela revisão"
        )
    return criados


@event_handler('proposta_aprovada')
def handle_proposta_aprovada(data: dict, admin_id: int):
    """
    Handler para proposta aprovada - Cria lançamentos contábeis e conta a receber
    
    Quando uma proposta é aprovada, este handler:
    1. Cria lançamento contábil com partidas dobradas (Clientes a Receber / Receita de Serviços)
    2. Cria entrada em Contas a Receber do módulo financeiro
    
    Args:
        data: Dados do evento contendo proposta_id, cliente_nome, valor_total, data_aprovacao
        admin_id: ID do administrador/tenant
    """
    
    # Task #102 (atomicidade real): este handler NÃO commita nem faz rollback.
    # A rota chamadora (propostas_consolidated.aprovar e .aprovar_proposta_cliente)
    # é dona da transação e só commita após `EventManager.emit(..., raise_on_error=True)`
    # retornar com sucesso. Qualquer exceção propaga para a rota fazer rollback
    # completo de Obra + IMC + lançamento contábil + cronograma — tudo ou nada.
    proposta_id = data.get('proposta_id')
    cliente_nome = data.get('cliente_nome')
    valor_total = Decimal(str(data.get('valor_total', 0)))
    data_aprovacao = data.get('data_aprovacao')
    # A importação físico-financeira reusa este caminho canônico (Obra + IMC + OSC),
    # mas NÃO é uma venda contábil: quando skip_contabil=True, pula lançamento/partidas.
    skip_contabil = bool(data.get('skip_contabil'))

    logger.info(f"🔔 Processando evento proposta_aprovada - Proposta: {proposta_id}, Cliente: {cliente_nome}")

    if not proposta_id:
        logger.warning(f"⚠️ proposta_id não fornecido no evento proposta_aprovada")
        return

    if not cliente_nome:
        logger.warning(f"⚠️ cliente_nome não fornecido no evento proposta_aprovada")
        cliente_nome = "Cliente não identificado"

    if isinstance(data_aprovacao, str):
        try:
            data_aprovacao = datetime.strptime(data_aprovacao, '%Y-%m-%d').date()
        except ValueError:
            data_aprovacao = date.today()
    elif not isinstance(data_aprovacao, date):
        data_aprovacao = date.today()

    def _materializar_cronograma_se_houver():
        """Materializa cronograma se proposta tem obra + snapshot revisado.

        Task #200: quando o admin pré-configurou `cronograma_default_json`
        ANTES da aprovação, a obra nasce com cronograma materializado E
        marcada como revisada (`cronograma_revisado_em = NOW()`), pulando
        o gate de revisão inicial. Quando NÃO há snapshot, a obra fica
        com `cronograma_revisado_em = NULL` e cai no gate na primeira
        visita aos detalhes.
        """
        from models import Proposta as _Proposta, Obra as _Obra
        from services.cronograma_proposta import materializar_cronograma
        from datetime import datetime as _dt
        _proposta_obj = _Proposta.query.filter_by(
            id=proposta_id, admin_id=admin_id
        ).first()
        if _proposta_obj and _proposta_obj.obra_id and _proposta_obj.cronograma_default_json:
            materializar_cronograma(
                _proposta_obj, admin_id, _proposta_obj.obra_id,
                arvore_marcada=_proposta_obj.cronograma_default_json,
            )
            # Versão nº1 do cronograma que acabou de nascer: sem ela o
            # primeiro import (.mpp/.xml) não teria estado anterior para
            # fotografar — e o rollback ficaria sem destino.
            from services.cronograma_versao_service import (
                registrar_versao_inicial,
            )
            registrar_versao_inicial(
                _proposta_obj.obra_id, admin_id,
                observacao='cronograma inicial (aprovação da proposta)',
            )
            # Task #200: obra nasce já revisada (admin pré-configurou).
            obra_obj = _Obra.query.filter_by(id=_proposta_obj.obra_id).first()
            if obra_obj and obra_obj.cronograma_revisado_em is None:
                obra_obj.cronograma_revisado_em = _dt.utcnow()
                logger.info(
                    f"#200: obra {obra_obj.id} marcada como cronograma_revisado_em "
                    f"(materializada via snapshot da proposta {proposta_id})"
                )
        elif _proposta_obj and _proposta_obj.obra_id:
            logger.info(
                f"#102/#200: proposta {proposta_id} aprovada SEM cronograma_default_json — "
                "obra criada em estado 'cronograma pendente'; gate de revisão inicial "
                "será disparado na primeira visita ao detalhe da obra."
            )

    # Task #94: lançamento contábil só faz sentido para valor > 0.
    # Para valor zerado (ou importação com skip_contabil), propaga itens
    # comerciais e cronograma sem lançamento.
    if valor_total <= 0 or skip_contabil:
        logger.info(
            f"⏭️ Proposta {proposta_id}: {'importação (skip_contabil)' if skip_contabil else 'valor zerado'} "
            f"— pulando lançamento contábil; propagação proposta→obra continua."
        )
        _propagar_proposta_para_obra(proposta_id, admin_id)
        _materializar_cronograma_se_houver()
        return

    # Garantir plano de contas antes de inserir PartidaContabil (FK constraint).
    # seed_plano_contas_if_needed usa flush (não commit) para não quebrar a
    # transação atômica gerenciada pela rota chamadora.
    try:
        from contabilidade_utils import seed_plano_contas_if_needed
        seed_plano_contas_if_needed(admin_id)
    except Exception as _se:
        logger.warning(f"[WARN] seed_plano_contas_if_needed falhou (proposta {proposta_id}): {_se}")

    # Fase 0.6 / D1b — a revisão lança o DELTA, não o valor cheio.
    #
    # Antes, aprovar a v2 de R$ 120.000 sobre a v1 de R$ 100.000 lançava
    # 120.000 de novo: R$ 220.000 de receita para um contrato de R$ 120.000
    # (medido em 21/07). Um aditivo não é uma segunda venda — é a mesma
    # venda, por outro preço.
    from models import Proposta as _Proposta
    _proposta_obj = _Proposta.query.filter_by(
        id=proposta_id, admin_id=admin_id).first()
    ids_linhagem = (
        [p.id for p in _linhagem_de_proposta(_proposta_obj, admin_id)]
        if _proposta_obj else [proposta_id]
    )
    ja_lancado = Decimal(str(
        db.session.query(db.func.sum(LancamentoContabil.valor_total)).filter(
            LancamentoContabil.admin_id == admin_id,
            LancamentoContabil.origem == 'PROPOSTAS',
            LancamentoContabil.origem_id.in_(ids_linhagem),
        ).scalar() or 0
    ))
    delta = valor_total - ja_lancado

    if delta == 0:
        logger.info(
            f"⏭️ Proposta {proposta_id}: revisão sem mudança de valor "
            f"(linhagem já lançou R$ {float(ja_lancado):.2f}) — nenhum "
            f"lançamento contábil. Propagação continua."
        )
        _propagar_proposta_para_obra(proposta_id, admin_id)
        _materializar_cronograma_se_houver()
        return

    # Delta negativo (revisão para baixo) inverte as partidas: estorna
    # receita e reduz o valor a receber do cliente.
    estorno = delta < 0
    valor_partida = float(abs(delta))
    if ja_lancado:
        historico = (
            f"Revisão de proposta #{proposta_id} - {cliente_nome} - "
            f"{'estorno' if estorno else 'aditivo'} sobre "
            f"R$ {float(ja_lancado):.2f}"
        )
    else:
        historico = f"Proposta aprovada #{proposta_id} - {cliente_nome}"

    # 1. Criar lançamento contábil
    lancamento = LancamentoContabil(
        numero=gerar_numero_lancamento(admin_id),
        data_lancamento=data_aprovacao,
        historico=historico,
        valor_total=float(delta),
        origem='PROPOSTAS',
        origem_id=proposta_id,
        admin_id=admin_id
    )
    db.session.add(lancamento)
    db.session.flush()
    logger.info(f"✅ Lançamento contábil #{lancamento.numero} criado")

    # 2. Partidas contábeis dobradas
    #
    # A contrapartida do estorno é `4.2.01.001` (Redução de Contrato), não um
    # débito em `4.1.01.001`: `calcular_dre_mensal` monta a receita bruta com
    # `calcular_valor_contas([...], 'CREDITO')` — só partidas CREDITO — e um
    # débito na conta de receita ficaria INVISÍVEL no DRE. As deduções 4.2.x
    # o DRE já subtrai. Contabilmente também é o certo: reduzir contrato é
    # dedução da receita bruta, não receita negativa.
    conta_resultado = '4.2.01.001' if estorno else '4.1.01.001'
    db.session.add(PartidaContabil(
        lancamento_id=lancamento.id, sequencia=1,
        conta_codigo='1.1.02.001',
        tipo_partida='CREDITO' if estorno else 'DEBITO',
        valor=valor_partida, admin_id=admin_id,
    ))
    db.session.add(PartidaContabil(
        lancamento_id=lancamento.id, sequencia=2,
        conta_codigo=conta_resultado,
        tipo_partida='DEBITO' if estorno else 'CREDITO',
        valor=valor_partida, admin_id=admin_id,
    ))
    logger.info(
        f"✅ Partidas contábeis criadas - "
        f"{'ESTORNO' if estorno else 'lançamento'} R$ {valor_partida:.2f} "
        f"(1.1.02.001 × {conta_resultado})"
    )

    # Task #82: propagar para obra (IMC → OSC). Falha propaga.
    _propagar_proposta_para_obra(proposta_id, admin_id)

    # Task #102: materializar cronograma. Falha propaga (rota faz rollback).
    _materializar_cronograma_se_houver()

    logger.info(f"✅ Handler proposta_aprovada executado - Proposta #{proposta_id} (commit pendente)")


def gerar_numero_lancamento(admin_id: int) -> int:
    """
    Gera número sequencial para lançamento contábil
    
    Args:
        admin_id: ID do administrador/tenant
        
    Returns:
        int: Próximo número sequencial
    """
    try:
        ultimo = LancamentoContabil.query.filter_by(
            admin_id=admin_id
        ).order_by(LancamentoContabil.numero.desc()).first()
        
        return (ultimo.numero + 1) if ultimo else 1
    except Exception as e:
        logger.error(f"❌ Erro ao gerar número de lançamento: {e}")
        return 1
