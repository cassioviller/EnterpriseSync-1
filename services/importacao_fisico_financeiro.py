"""Importa o JSON físico-financeiro (snapshot Planilha1 + cronograma) e deixa a
obra inteira planejada — agora pela CADEIA COMERCIAL CANÔNICA completa:

    Insumo → Orçamento → Proposta → (aprovação) → Obra + ItemMedicaoComercial
           → ObraServicoCusto → cronograma físico-financeiro + medições + caixa.

Arquitetura híbrida (decisão 2026-06-24):
  • a cadeia comercial (Orçamento/Proposta/IMC/OSC) nasce do mesmo código de
    produção, disparando o evento `proposta_aprovada` com `skip_contabil=True`
    (importar NÃO gera lançamento contábil);
  • os específicos físico-financeiros (cronograma raiz+folhas COM as datas do
    .mpp, vínculos peso, custo veks/fat, MedicaoContrato e snapshot) ficam aqui,
    porque o materializador canônico de cronograma não carrega datas por tarefa.

Idempotente e tenant-scoped.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

CENTAVO = Decimal("0.01")


def _parse_date(s):
    if not s:
        return None
    return date.fromisoformat(s[:10])


# ----------------------------------------------------------------------
# Resolvers de catálogo (Serviço / Insumo / Composição)
# ----------------------------------------------------------------------
def _resolver_servico(nome: str, categoria, admin_id: int):
    """Encontra ou cria um Serviço do catálogo (tenant-scoped) por nome."""
    from app import db
    from models import Servico
    nome = (nome or "Serviço")[:100]
    serv = Servico.query.filter_by(admin_id=admin_id, nome=nome).first()
    if serv is None:
        serv = Servico(nome=nome, categoria=(categoria or "Steel Frame")[:50],
                       unidade_medida="un", admin_id=admin_id, ativo=True)
        db.session.add(serv)
        db.session.flush()
    return serv


def _resolver_insumo(nome: str, valor: Decimal, admin_id: int, data_vig):
    """Encontra ou cria um Insumo por nome (tenant-scoped). Se for novo e ainda
    sem preço, registra um PrecoBaseInsumo vigente com `valor` (fator_comercial=1,
    para que coef×preço_técnico reproduza o valor do item)."""
    from app import db
    from models import Insumo, PrecoBaseInsumo
    nome = (nome or "Item")[:200]
    ins = Insumo.query.filter_by(admin_id=admin_id, nome=nome).first()
    if ins is None:
        ins = Insumo(nome=nome, admin_id=admin_id, tipo="MATERIAL", unidade="un",
                     coeficiente_padrao=Decimal("1"), fator_comercial=Decimal("1"))
        db.session.add(ins)
        db.session.flush()
    if not PrecoBaseInsumo.query.filter_by(insumo_id=ins.id).first():
        db.session.add(PrecoBaseInsumo(
            insumo_id=ins.id, admin_id=admin_id,
            valor=Decimal(str(valor or 0)),
            vigencia_inicio=data_vig or date.today()))
        db.session.flush()
    return ins


def _compor_servico(servico, itens, admin_id: int, data_vig) -> list:
    """Para cada item de custo da etapa, casa com um Insumo do catálogo e cria a
    ComposicaoServico (coeficiente=1). Devolve o `composicao_snapshot` no formato
    que OrcamentoItem/PropostaItem usam. O custo técnico de cada linha reproduz o
    valor (veks+fat) do item."""
    from app import db
    from models import ComposicaoServico
    snap: list = []
    for it in itens or []:
        nome = it.get("item") or "Custo"
        valor = Decimal(str(it.get("veks") or 0)) + Decimal(str(it.get("fat") or 0))
        ins = _resolver_insumo(nome, valor, admin_id, data_vig)
        comp = ComposicaoServico.query.filter_by(
            servico_id=servico.id, insumo_id=ins.id, admin_id=admin_id).first()
        if comp is None:
            db.session.add(ComposicaoServico(
                servico_id=servico.id, insumo_id=ins.id, admin_id=admin_id,
                coeficiente=Decimal("1"), unidade="un"))
        snap.append({
            "insumo_id": ins.id, "descricao": ins.nome, "unidade": "un",
            "coeficiente": 1.0,
            "preco_unitario": float(valor), "preco_embalagem": float(valor),
            "preco_tecnico_unitario": float(valor),
            "subtotal_unitario": float(valor),
        })
    db.session.flush()
    return snap


# ----------------------------------------------------------------------
# Idempotência: limpa todos os derivados da obra (comercial + físico)
# ----------------------------------------------------------------------
def _limpar_derivados(obra, admin_id: int):
    from app import db
    from models import (Orcamento, OrcamentoItem, Proposta, PropostaItem,
                        ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
                        ObraServicoCusto, TarefaCronograma, MedicaoContrato)

    props = Proposta.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
    prop_ids = [p.id for p in props]
    orc_ids = [p.orcamento_id for p in props if p.orcamento_id]
    if prop_ids:
        PropostaItem.query.filter(
            PropostaItem.proposta_id.in_(prop_ids)).delete(synchronize_session=False)
        Proposta.query.filter(
            Proposta.id.in_(prop_ids)).delete(synchronize_session=False)
    if orc_ids:
        OrcamentoItem.query.filter(
            OrcamentoItem.orcamento_id.in_(orc_ids)).delete(synchronize_session=False)
        Orcamento.query.filter(
            Orcamento.id.in_(orc_ids)).delete(synchronize_session=False)

    ids_imc = [r[0] for r in db.session.query(ItemMedicaoComercial.id)
               .filter_by(obra_id=obra.id).all()]
    if ids_imc:
        ItemMedicaoCronogramaTarefa.query.filter(
            ItemMedicaoCronogramaTarefa.item_medicao_id.in_(ids_imc)).delete(synchronize_session=False)
    ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    ItemMedicaoComercial.query.filter_by(obra_id=obra.id).delete(synchronize_session=False)
    TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    MedicaoContrato.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    db.session.flush()


# ----------------------------------------------------------------------
# Cronograma físico-financeiro (raiz + folhas COM datas do .mpp) + vínculos
# ----------------------------------------------------------------------
def _materializar_cronograma_fisico(obra, admin_id, imc, etapa, mpp, data_default, avisos):
    from app import db
    from models import TarefaCronograma, ItemMedicaoCronogramaTarefa

    cron = etapa.get("cronograma", {})
    di = _parse_date(cron.get("inicio")) or data_default
    df = _parse_date(cron.get("fim"))

    raiz = TarefaCronograma(obra_id=obra.id, admin_id=admin_id,
                            nome_tarefa=etapa["nome"], tarefa_pai_id=None,
                            data_inicio=di, data_fim=df, percentual_concluido=0)
    db.session.add(raiz)
    db.session.flush()

    folhas_ids = cron.get("tarefas_mpp") or []
    folhas = []
    if folhas_ids:
        for tid in folhas_ids:
            t = mpp.get(tid, {})
            fdi = _parse_date(t.get("inicio")) or di
            fdf = _parse_date(t.get("fim")) or df
            folhas.append((t.get("nome") or etapa["nome"], fdi, fdf, int(t.get("dias") or 1)))
    else:
        dias = (df - di).days + 1 if (di and df) else 1
        folhas.append((etapa["nome"], di, df, max(1, dias)))
        avisos.append(
            f"Etapa '{etapa['nome']}' sem tarefas do cronograma — "
            "faseada pela data da etapa.")

    for nome_f, fdi, fdf, dias in folhas:
        folha = TarefaCronograma(obra_id=obra.id, admin_id=admin_id,
                                 nome_tarefa=nome_f, tarefa_pai_id=raiz.id,
                                 data_inicio=fdi, data_fim=fdf,
                                 duracao_dias=dias, percentual_concluido=0)
        db.session.add(folha)
        db.session.flush()
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc.id, cronograma_tarefa_id=folha.id,
            admin_id=admin_id, peso=max(1, dias)))
    db.session.flush()


# ----------------------------------------------------------------------
# Orquestrador
# ----------------------------------------------------------------------
def importar_fisico_financeiro(payload: dict, admin_id: int) -> dict:
    from app import db
    from event_manager import EventManager
    from models import (Obra, Orcamento, OrcamentoItem, Proposta, PropostaItem,
                        ItemMedicaoComercial, ObraServicoCusto)
    from services.cliente_resolver import obter_ou_criar_cliente

    obra_j = payload['obra']
    contrato = payload.get('contrato', {})
    data_inicio = _parse_date(contrato.get('data_inicio')) or date.today()

    cliente = obter_ou_criar_cliente(nome=obra_j.get('cliente'), admin_id=admin_id)
    if cliente is None:
        raise ValueError(
            "O arquivo precisa de 'obra.cliente' (nome do cliente) — "
            "obrigatório para criar a obra."
        )
    codigo = obra_j.get('codigo_obra') or (obra_j.get('nome') or '')[:20]

    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if obra is None:
        obra = Obra(codigo=codigo, admin_id=admin_id, nome=obra_j.get('nome'),
                    data_inicio=data_inicio)
        db.session.add(obra)
    obra.nome = obra_j.get('nome')
    obra.valor_contrato = float(contrato.get('valor_venda') or 0)
    obra.data_inicio = data_inicio
    obra.data_previsao_fim = _parse_date(contrato.get('data_fim_cronograma'))
    obra.cliente_id = cliente.id
    db.session.flush()

    valor_venda = Decimal(str(contrato.get('valor_venda') or 0))
    avisos: list[str] = []

    # Idempotência: zera os derivados (comercial + físico) desta obra.
    _limpar_derivados(obra, admin_id)

    titulo = f"Físico-financeiro — {obra.nome or codigo}"[:255]

    # 1) ORÇAMENTO (catálogo: serviços + insumos + composição) ---------------
    orc = Orcamento(admin_id=admin_id, numero=f'FF-{obra.id}', titulo=titulo,
                    cliente_id=cliente.id, cliente_nome=cliente.nome,
                    status='convertido', criado_por=admin_id)
    db.session.add(orc)
    db.session.flush()

    # 2) PROPOSTA (back-link da obra ANTES de aprovar; sem cronograma_default) -
    proposta = Proposta(admin_id=admin_id, numero=f'FF-{obra.id}',
                        data_proposta=data_inicio, cliente_id=cliente.id,
                        cliente_nome=cliente.nome, titulo=titulo,
                        valor_total=valor_venda, obra_id=obra.id, status='enviada',
                        orcamento_id=orc.id)
    db.session.add(proposta)
    db.session.flush()

    etapa_por_pi: dict = {}     # proposta_item_id -> {etapa, veks, fat}
    custo_total_orc = Decimal('0')
    venda_total_orc = Decimal('0')
    for ordem, etapa in enumerate(payload.get('eap', []), start=1):
        custo = etapa.get('custo', {})
        veks = Decimal(str(custo.get('veks') or 0))
        fat = Decimal(str(custo.get('fat_direto') or 0))
        peso_pct = Decimal(str(custo.get('peso_pct') or 0))
        venda_item = (valor_venda * peso_pct).quantize(CENTAVO)
        nome_etapa = etapa['nome']

        servico = _resolver_servico(nome_etapa, etapa.get('grupo'), admin_id)
        snap = _compor_servico(servico, etapa.get('itens'), admin_id, data_inicio)
        custo_comp = sum((Decimal(str(l['subtotal_unitario'])) for l in snap), Decimal('0'))
        if custo_comp == 0:
            custo_comp = veks + fat  # etapa sem itens detalhados

        db.session.add(OrcamentoItem(
            admin_id=admin_id, orcamento_id=orc.id, ordem=ordem,
            servico_id=servico.id, descricao=nome_etapa[:500], unidade='un',
            quantidade=Decimal('1'), composicao_snapshot=snap,
            custo_unitario=custo_comp, preco_venda_unitario=venda_item,
            custo_total=custo_comp, venda_total=venda_item,
            lucro_total=venda_item - custo_comp))

        pi = PropostaItem(
            admin_id=admin_id, proposta_id=proposta.id, item_numero=ordem, ordem=ordem,
            descricao=nome_etapa[:500], quantidade=Decimal('1'), unidade='un',
            preco_unitario=venda_item, subtotal=venda_item, servico_id=servico.id,
            custo_unitario=custo_comp, composicao_snapshot=snap)
        db.session.add(pi)
        db.session.flush()
        etapa_por_pi[pi.id] = {'etapa': etapa, 'veks': veks, 'fat': fat}
        custo_total_orc += custo_comp
        venda_total_orc += venda_item

    orc.custo_total = custo_total_orc
    orc.venda_total = venda_total_orc
    orc.lucro_total = venda_total_orc - custo_total_orc
    db.session.flush()

    # 3) APROVAÇÃO canônica (skip contábil) → liga Obra + cria IMC + OSC -------
    EventManager.emit('proposta_aprovada', {
        'proposta_id': proposta.id,
        'cliente_nome': cliente.nome,
        'valor_total': float(valor_venda),
        'data_aprovacao': data_inicio.isoformat(),
        'skip_contabil': True,
    }, admin_id, raise_on_error=True)

    # 4) recupera IMC/OSC por PropostaItem e preenche custo + cronograma físico -
    mpp = {t['id']: t for t in payload.get('cronograma_tarefas', [])}
    imcs = ItemMedicaoComercial.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
    imc_por_pi = {i.proposta_item_id: i for i in imcs if i.proposta_item_id}
    for pi_id, info in etapa_por_pi.items():
        imc = imc_por_pi.get(pi_id)
        if imc is None:
            avisos.append(f"Etapa '{info['etapa']['nome']}' sem IMC após aprovação.")
            continue
        osc = ObraServicoCusto.query.filter_by(
            item_medicao_comercial_id=imc.id, admin_id=admin_id).first()
        if osc is not None:
            # valor_orcado fica como valor_comercial (venda); o CUSTO previsto
            # vai nos *_a_realizar, classificado Veks/Fat Direto.
            osc.mao_obra_a_realizar = info['veks']
            osc.fonte_mao_obra = 'veks'
            osc.material_a_realizar = info['fat']
            osc.fonte_material = 'fat_direto'
            osc.outros_a_realizar = Decimal('0')
            osc.fonte_outros = 'veks'
            osc.realizado_material = 0
            osc.realizado_mao_obra = 0
            osc.realizado_outros = 0
        _materializar_cronograma_fisico(
            obra, admin_id, imc, info['etapa'], mpp, data_inicio, avisos)

    # 5) medições de contrato + snapshot do fluxo de caixa da planilha --------
    from models import MedicaoContrato
    for i, med in enumerate(payload.get('medicoes', [])):
        db.session.add(MedicaoContrato(
            obra_id=obra.id, admin_id=admin_id, nome=med.get('nome'),
            data=_parse_date(med.get('data')),
            pct=Decimal(str(med.get('pct') or 0)),
            recebido_no_mes=med.get('recebido_no_mes'),
            obs=med.get('obs'), ordem=i))

    obra.fluxo_caixa_planilha = payload.get('fluxo_caixa_mensal')

    db.session.commit()
    return {'obra_id': obra.id, 'orcamento_id': orc.id,
            'proposta_id': proposta.id, 'avisos': avisos}
