"""
utils/rdo_equip_ocorr.py — Task #61

Parser dos campos repetíveis de Equipamentos e Ocorrências enviados
pelos formulários (novo.html / editar_rdo.html).

Convenção:
  Equipamentos:  equip_nome[]  equip_quantidade[]  equip_horas_uso[]  equip_estado[]
  Ocorrências:   ocorr_tipo[]  ocorr_severidade[]  ocorr_descricao[]  ocorr_status[]

Persistência idempotente: callers devem fazer DELETE (filter_by rdo_id=…)
antes de chamar `persistir_*` em modo edição.
"""
from __future__ import annotations

import logging
from typing import Iterable

from app import db
from models import RDOEquipamento, RDOOcorrencia

logger = logging.getLogger(__name__)


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_equipamentos(form) -> list[dict]:
    """Retorna lista de dicts {nome, quantidade, horas_uso, estado}."""
    nomes = form.getlist('equip_nome[]')
    qtds = form.getlist('equip_quantidade[]')
    horas = form.getlist('equip_horas_uso[]')
    estados = form.getlist('equip_estado[]')
    out: list[dict] = []
    for i, nome in enumerate(nomes):
        nome = (nome or '').strip()
        if not nome:
            continue
        out.append({
            'nome': nome,
            'quantidade': max(1, _to_int(qtds[i] if i < len(qtds) else None, 1)),
            'horas_uso': max(0.0, _to_float(horas[i] if i < len(horas) else None, 0.0)),
            'estado': (estados[i] if i < len(estados) else 'Bom') or 'Bom',
        })
    return out


def parse_ocorrencias(form) -> list[dict]:
    """Retorna lista de dicts {tipo, severidade, descricao, status}."""
    tipos = form.getlist('ocorr_tipo[]')
    sevs = form.getlist('ocorr_severidade[]')
    descs = form.getlist('ocorr_descricao[]')
    stats = form.getlist('ocorr_status[]')
    out: list[dict] = []
    for i, desc in enumerate(descs):
        desc = (desc or '').strip()
        if not desc:
            continue
        out.append({
            'tipo': (tipos[i] if i < len(tipos) else 'Outros') or 'Outros',
            'severidade': (sevs[i] if i < len(sevs) else 'Baixa') or 'Baixa',
            'descricao': desc,
            'status': (stats[i] if i < len(stats) else 'Pendente') or 'Pendente',
        })
    return out


def persistir_equipamentos(rdo_id: int, admin_id: int, items: Iterable[dict]) -> int:
    n = 0
    for it in items:
        eq = RDOEquipamento(
            rdo_id=rdo_id,
            nome_equipamento=it['nome'],
            quantidade=it['quantidade'],
            horas_uso=it['horas_uso'],
            estado_conservacao=it['estado'],
        )
        # admin_id pode não existir em algumas instalações — tenta best-effort
        if hasattr(eq, 'admin_id'):
            try:
                eq.admin_id = admin_id
            except Exception:
                pass
        db.session.add(eq)
        n += 1
    return n


def persistir_ocorrencias(rdo_id: int, admin_id: int, items: Iterable[dict]) -> int:
    n = 0
    for it in items:
        oc = RDOOcorrencia(
            rdo_id=rdo_id,
            tipo_ocorrencia=it['tipo'],
            severidade=it['severidade'],
            descricao_ocorrencia=it['descricao'],
            status_resolucao=it['status'],
        )
        if hasattr(oc, 'admin_id'):
            try:
                oc.admin_id = admin_id
            except Exception:
                pass
        db.session.add(oc)
        n += 1
    return n


def replace_equipamentos_ocorrencias(rdo_id: int, admin_id: int, form) -> tuple[int, int]:
    """Apaga linhas existentes e regrava a partir do form. Retorna (n_eq, n_oc)."""
    RDOEquipamento.query.filter_by(rdo_id=rdo_id).delete()
    RDOOcorrencia.query.filter_by(rdo_id=rdo_id).delete()
    n_eq = persistir_equipamentos(rdo_id, admin_id, parse_equipamentos(form))
    n_oc = persistir_ocorrencias(rdo_id, admin_id, parse_ocorrencias(form))
    logger.info(f"[Task#61] RDO {rdo_id}: regravados {n_eq} equipamento(s) e {n_oc} ocorrência(s)")
    return n_eq, n_oc
