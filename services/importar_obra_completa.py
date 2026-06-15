"""Importador auto-wiring: Orçamento → Proposta → Obra → Cronograma → IMC.

Objetivo: ao importar um orçamento, o sistema cria TODA a cadeia já vinculada,
sem nenhuma configuração manual — pronto para apontar RDO e ver o "Resultado por
Atividade". Idempotente: rodar de novo não duplica.

Estratégia de cronograma (o ponto que faz "funcionar sem config"):
  - Se o serviço do item tem CronogramaTemplate, usa o caminho do sistema
    (montar_arvore_preview + materializar_cronograma).
  - Se NÃO tem template (catálogo vazio, ex.: Baia), **sintetiza** uma atividade
    por item (serviço = atividade), com peso 100% no ItemMedicaoComercial.
    Assim a venda agregada, o custo orçado (via composicao_snapshot) e o
    apontamento por atividade funcionam imediatamente.

Tudo numa transação; o caller (view/script) faz commit/rollback ou usa o
parâmetro commit=True.
"""
import logging
import secrets
from datetime import date, datetime
from decimal import Decimal

from app import db
from models import (
    Orcamento, Proposta, PropostaItem, Obra, Cliente,
    ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, TarefaCronograma,
)

logger = logging.getLogger(__name__)


def _proximo_codigo_obra(admin_id):
    ultimo = (
        db.session.query(db.func.max(Obra.codigo))
        .filter(Obra.admin_id == admin_id, Obra.codigo.like('OBR%'))
        .scalar()
    )
    if ultimo and ultimo.startswith('OBR'):
        try:
            return f"OBR{int(ultimo[3:]) + 1:04d}"
        except ValueError:
            pass
    return "OBR0001"


def _resolver_cliente_id(orc, admin_id):
    if orc.cliente_id:
        return orc.cliente_id
    cli = Cliente(nome=(orc.cliente_nome or 'Cliente')[:255], admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    return cli.id


def _criar_proposta(orc, admin_id):
    proposta = Proposta(
        admin_id=admin_id,
        numero=f"PROP-{orc.numero}",
        cliente_id=orc.cliente_id,
        cliente_nome=orc.cliente_nome or 'Cliente',
        titulo=orc.titulo,
        descricao=orc.descricao,
        status='aprovada',
        valor_total=orc.venda_total or 0,
        orcamento_id=orc.id,
        criado_por=admin_id,
        versao=1,
    )
    db.session.add(proposta)
    db.session.flush()

    for idx, it in enumerate(orc.itens, start=1):
        pi = PropostaItem(
            admin_id=admin_id,
            proposta_id=proposta.id,
            item_numero=idx,
            ordem=idx,
            descricao=it.descricao,
            quantidade=it.quantidade,
            unidade=it.unidade,
            preco_unitario=it.preco_venda_unitario or 0,
            subtotal=it.venda_total or 0,
            servico_id=it.servico_id,
            quantidade_medida=it.quantidade,
            cronograma_template_override_id=getattr(it, 'cronograma_template_override_id', None),
            composicao_snapshot=it.composicao_snapshot or [],   # custo orçado por atividade (DC5)
        )
        db.session.add(pi)
    db.session.flush()
    return proposta


def _resolver_ou_criar_obra(proposta, orc, admin_id):
    if proposta.obra_id:
        obra = Obra.query.filter_by(id=proposta.obra_id, admin_id=admin_id).first()
        if obra:
            return obra
    obra = Obra.query.filter_by(proposta_origem_id=proposta.id, admin_id=admin_id).first()
    if obra:
        proposta.obra_id = obra.id
        return obra
    obra = Obra(
        nome=f"Obra - {orc.titulo or orc.numero}"[:100],
        codigo=_proximo_codigo_obra(admin_id),
        cliente_id=_resolver_cliente_id(orc, admin_id),
        data_inicio=date.today(),
        valor_contrato=float(orc.venda_total or 0),
        status='Em andamento',
        proposta_origem_id=proposta.id,
        admin_id=admin_id,
        ativo=True,
        token_cliente=secrets.token_urlsafe(32),
        cronograma_revisado_em=datetime.utcnow(),
    )
    db.session.add(obra)
    db.session.flush()
    proposta.obra_id = obra.id
    proposta.convertida_em_obra = True
    return obra


def _criar_imc(proposta, obra, admin_id):
    """ItemMedicaoComercial 1:1 por PropostaItem (idempotente). Retorna
    {proposta_item_id: ItemMedicaoComercial}."""
    itens = PropostaItem.query.filter_by(proposta_id=proposta.id).all()
    existentes = {
        imc.proposta_item_id: imc
        for imc in ItemMedicaoComercial.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
        if imc.proposta_item_id is not None
    }
    mapa = {}
    for it in itens:
        imc = existentes.get(it.id)
        if imc is None:
            nome = (it.descricao or f'Item {it.item_numero or it.ordem or it.id}').strip()[:200]
            imc = ItemMedicaoComercial(
                admin_id=admin_id,
                obra_id=obra.id,
                nome=nome,
                valor_comercial=Decimal(str(it.subtotal or 0)),
                servico_id=it.servico_id,
                quantidade=(Decimal(str(it.quantidade)) if it.quantidade is not None else None),
                proposta_item_id=it.id,
                status='PENDENTE',
            )
            db.session.add(imc)
            db.session.flush()
        mapa[it.id] = imc
    return mapa


def _sintetizar_atividade(it, imc, obra, admin_id, ordem):
    """Cria 1 TarefaCronograma (serviço = atividade) + vínculo peso 100% no IMC,
    quando o serviço não tem template. Idempotente por gerada_por_proposta_item_id."""
    tarefa = TarefaCronograma.query.filter_by(
        gerada_por_proposta_item_id=it.id, obra_id=obra.id
    ).first()
    if tarefa is None:
        tarefa = TarefaCronograma(
            obra_id=obra.id,
            nome_tarefa=(it.descricao or f'Atividade {ordem}')[:200],
            ordem=ordem,
            duracao_dias=1,
            quantidade_total=(float(it.quantidade) if it.quantidade is not None else None),
            unidade_medida=it.unidade,
            servico_id=it.servico_id,
            percentual_concluido=0.0,
            admin_id=admin_id,
            gerada_por_proposta_item_id=it.id,
        )
        db.session.add(tarefa)
        db.session.flush()

    vinculo = ItemMedicaoCronogramaTarefa.query.filter_by(
        item_medicao_id=imc.id, cronograma_tarefa_id=tarefa.id
    ).first()
    if vinculo is None:
        db.session.add(ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc.id,
            cronograma_tarefa_id=tarefa.id,
            peso=Decimal('100'),
            admin_id=admin_id,
        ))
        db.session.flush()
    return tarefa


def _materializar_ou_sintetizar(proposta, obra, admin_id, imc_por_item):
    """Materializa via template onde houver; sintetiza atividade 1:1 onde não houver."""
    # 1) Caminho do sistema (itens cujo serviço tem CronogramaTemplate)
    try:
        from services.cronograma_proposta import montar_arvore_preview, materializar_cronograma
        arvore = montar_arvore_preview(proposta, admin_id)
        proposta.cronograma_default_json = arvore
        materializar_cronograma(proposta, admin_id, obra.id, arvore)
    except Exception as e:
        logger.warning(f"[import] materializar_cronograma via template falhou/sem template: {e}")

    # 2) Fallback: itens sem nenhuma TarefaCronograma → sintetizar atividade 1:1
    itens = PropostaItem.query.filter_by(proposta_id=proposta.id).order_by(PropostaItem.ordem).all()
    n_tarefas = 0
    for idx, it in enumerate(itens, start=1):
        ja_tem = TarefaCronograma.query.filter_by(
            gerada_por_proposta_item_id=it.id, obra_id=obra.id
        ).first()
        if ja_tem:
            n_tarefas += 1
            continue
        imc = imc_por_item.get(it.id)
        if imc is None:
            continue
        _sintetizar_atividade(it, imc, obra, admin_id, idx)
        n_tarefas += 1
    return n_tarefas


def importar_obra_completa(orcamento_id, admin_id, commit=True):
    """Cria a cadeia completa Orçamento→Proposta→Obra→Cronograma→IMC, vinculada,
    sem config manual. Idempotente. Retorna dict com ids e contagens."""
    orc = Orcamento.query.filter_by(id=orcamento_id, admin_id=admin_id).first()
    if not orc:
        raise ValueError(f"Orçamento {orcamento_id} não encontrado para admin {admin_id}")

    # idempotência: proposta já existe para este orçamento?
    proposta = Proposta.query.filter_by(orcamento_id=orc.id, admin_id=admin_id).first()
    criado = proposta is None
    if proposta is None:
        proposta = _criar_proposta(orc, admin_id)

    obra = _resolver_ou_criar_obra(proposta, orc, admin_id)
    imc_por_item = _criar_imc(proposta, obra, admin_id)
    n_tarefas = _materializar_ou_sintetizar(proposta, obra, admin_id, imc_por_item)

    if commit:
        db.session.commit()

    return {
        'criado': criado,
        'proposta_id': proposta.id,
        'obra_id': obra.id,
        'n_itens': len(imc_por_item),
        'n_tarefas': n_tarefas,
    }
