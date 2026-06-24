"""Importa o JSON físico-financeiro (snapshot Planilha1 + cronograma) e deixa a
obra inteira planejada: cronograma, custo por etapa, vinculação atividade↔custo,
medições de contrato e snapshot de caixa. Idempotente e tenant-scoped.
Reaproveita os modelos existentes (Abordagem A — derivado)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


def _parse_date(s):
    if not s:
        return None
    return date.fromisoformat(s[:10])


def importar_fisico_financeiro(payload: dict, admin_id: int) -> dict:
    from app import db
    from models import Obra
    from services.cliente_resolver import obter_ou_criar_cliente

    obra_j = payload['obra']
    contrato = payload.get('contrato', {})

    cliente = obter_ou_criar_cliente(nome=obra_j.get('cliente'), admin_id=admin_id)
    codigo = obra_j.get('codigo_obra') or obra_j.get('nome')

    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if obra is None:
        obra = Obra(codigo=codigo, admin_id=admin_id, nome=obra_j.get('nome'),
                    data_inicio=_parse_date(contrato.get('data_inicio')) or date.today())
        db.session.add(obra)
    obra.nome = obra_j.get('nome')
    obra.valor_contrato = float(contrato.get('valor_venda') or 0)
    obra.data_inicio = _parse_date(contrato.get('data_inicio')) or obra.data_inicio
    obra.data_previsao_fim = _parse_date(contrato.get('data_fim_cronograma'))
    if cliente is not None:
        obra.cliente_id = cliente.id
    db.session.flush()

    avisos: list[str] = []

    # ------------------------------------------------------------------
    # Etapas → cronograma (raiz + folhas) + IMC + vínculo + custo (OSC)
    # ------------------------------------------------------------------
    from models import (TarefaCronograma, ItemMedicaoComercial,
                        ItemMedicaoCronogramaTarefa, ObraServicoCusto)

    tarefas_mpp = {t['id']: t for t in payload.get('cronograma_tarefas', [])}

    # Limpa coleções derivadas da obra (idempotência) — ordem respeita FKs
    ids_imc = [r[0] for r in db.session.query(ItemMedicaoComercial.id)
               .filter_by(obra_id=obra.id).all()]
    if ids_imc:
        ItemMedicaoCronogramaTarefa.query.filter(
            ItemMedicaoCronogramaTarefa.item_medicao_id.in_(ids_imc)).delete(synchronize_session=False)
    ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    ItemMedicaoComercial.query.filter_by(obra_id=obra.id).delete(synchronize_session=False)
    TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    db.session.flush()

    valor_venda = Decimal(str(contrato.get('valor_venda') or 0))

    for etapa in payload.get('eap', []):
        cron = etapa.get('cronograma', {})
        custo = etapa.get('custo', {})
        di = _parse_date(cron.get('inicio'))
        df = _parse_date(cron.get('fim'))

        raiz = TarefaCronograma(obra_id=obra.id, admin_id=admin_id,
                                nome_tarefa=etapa['nome'], tarefa_pai_id=None,
                                data_inicio=di, data_fim=df,
                                percentual_concluido=0)
        db.session.add(raiz)
        db.session.flush()

        folhas_ids = cron.get('tarefas_mpp') or []
        folhas = []
        if folhas_ids:
            for tid in folhas_ids:
                t = tarefas_mpp.get(tid, {})
                fdi = _parse_date(t.get('inicio')) or di
                fdf = _parse_date(t.get('fim')) or df
                folhas.append((t.get('nome') or etapa['nome'], fdi, fdf,
                               int(t.get('dias') or 1)))
        else:
            dias = (df - di).days + 1 if (di and df) else 1
            folhas.append((etapa['nome'], di, df, max(1, dias)))

        peso_pct = Decimal(str(custo.get('peso_pct') or 0))
        imc = ItemMedicaoComercial(
            obra_id=obra.id, admin_id=admin_id, nome=etapa['nome'],
            valor_comercial=(valor_venda * peso_pct).quantize(Decimal('0.01')))
        db.session.add(imc)
        # Ao inserir o IMC, um listener (after_insert) cria automaticamente o
        # ObraServicoCusto pareado (UNIQUE em item_medicao_comercial_id). Por isso
        # NÃO criamos a OSC manualmente: buscamos a auto-criada e a atualizamos com
        # os valores físico-financeiros (veks/fat_direto e respectivas fontes).
        db.session.flush()

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

        # Recupera a OSC auto-criada pelo listener e preenche o custo da etapa.
        osc = ObraServicoCusto.query.filter_by(
            item_medicao_comercial_id=imc.id).first()
        if osc is None:
            osc = ObraServicoCusto(
                obra_id=obra.id, admin_id=admin_id, nome=etapa['nome'],
                item_medicao_comercial_id=imc.id)
            db.session.add(osc)
        osc.obra_id = obra.id
        osc.admin_id = admin_id
        osc.nome = etapa['nome']
        osc.valor_orcado = Decimal(str(custo.get('total') or 0))
        osc.mao_obra_a_realizar = Decimal(str(custo.get('veks') or 0))
        osc.fonte_mao_obra = 'veks'
        osc.material_a_realizar = Decimal(str(custo.get('fat_direto') or 0))
        osc.fonte_material = 'fat_direto'
        osc.outros_a_realizar = Decimal('0')
        osc.fonte_outros = 'veks'
        osc.realizado_material = 0
        osc.realizado_mao_obra = 0
        osc.realizado_outros = 0

    # ------------------------------------------------------------------
    # Medições de contrato + snapshot do fluxo de caixa da planilha
    # ------------------------------------------------------------------
    from models import MedicaoContrato

    MedicaoContrato.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    for i, med in enumerate(payload.get('medicoes', [])):
        db.session.add(MedicaoContrato(
            obra_id=obra.id, admin_id=admin_id, nome=med.get('nome'),
            data=_parse_date(med.get('data')),
            pct=Decimal(str(med.get('pct') or 0)),
            recebido_no_mes=med.get('recebido_no_mes'),
            obs=med.get('obs'), ordem=i))

    obra.fluxo_caixa_planilha = payload.get('fluxo_caixa_mensal')

    db.session.commit()
    return {'obra_id': obra.id, 'avisos': avisos}
