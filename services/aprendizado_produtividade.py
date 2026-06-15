"""Fatia 5 — Loop de aprendizado de produtividade (DC10).

A produtividade real observada nos RDOs (`RDOMaoObra.produtividade_real`, já
calculada por `recalcular_produtividade_rdo`) é realimentada no catálogo
(`SubatividadeMestre.meta_produtividade`/`duracao_estimada_horas`), tornando o
próximo orçamento e os pesos da próxima materialização mais precisos. Fecha o
ciclo que hoje calcula o índice mas nunca volta ao catálogo. Sem migration.
"""
from decimal import Decimal

from app import db
from models import RDO, RDOMaoObra, RDOServicoSubatividade, SubatividadeMestre


def produtividade_observada(subatividade_mestre_id, admin_id):
    """Média (ponderada por horas) da produtividade real observada para uma
    SubatividadeMestre, a partir de RDOs finalizados. Retorna (media, n_amostras)
    — (None, 0) quando não há dados."""
    rows = (
        db.session.query(RDOMaoObra.produtividade_real, RDOMaoObra.horas_trabalhadas)
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .join(RDOServicoSubatividade, RDOServicoSubatividade.id == RDOMaoObra.subatividade_id)
        .filter(
            RDO.status == 'Finalizado',
            RDOMaoObra.admin_id == admin_id,
            RDOMaoObra.produtividade_real.isnot(None),
            RDOServicoSubatividade.subatividade_mestre_id == subatividade_mestre_id,
        )
        .all()
    )
    num = sum(Decimal(str(p or 0)) * Decimal(str(h or 0)) for p, h in rows)
    den = sum(Decimal(str(h or 0)) for _, h in rows)
    if den <= 0:
        return None, 0
    return (num / den), len(rows)


def atualizar_catalogo_produtividade(admin_id, min_amostras=3, peso_novo=Decimal('0.3')):
    """Realimenta `SubatividadeMestre.meta_produtividade` com a produtividade
    observada, via média móvel exponencial (conservador: só com amostras
    suficientes). Ajusta `duracao_estimada_horas` de forma coerente (inversa à
    produtividade). Idempotente em relação aos dados; retorna nº de catálogos
    atualizados."""
    peso_novo = Decimal(str(peso_novo))
    n_atualizadas = 0
    subs = SubatividadeMestre.query.filter_by(admin_id=admin_id, ativo=True).all()
    for s in subs:
        obs, n = produtividade_observada(s.id, admin_id)
        if obs is None or n < min_amostras:
            continue
        antiga = Decimal(str(s.meta_produtividade)) if s.meta_produtividade else obs
        nova = antiga * (Decimal('1') - peso_novo) + obs * peso_novo
        if nova <= 0:
            continue
        # duracao_estimada_horas é inversa à produtividade: mais rápido → menos horas
        if s.duracao_estimada_horas and antiga > 0:
            s.duracao_estimada_horas = float(
                Decimal(str(s.duracao_estimada_horas)) * (antiga / nova)
            )
        s.meta_produtividade = float(nova)
        n_atualizadas += 1
    db.session.commit()
    return n_atualizadas
