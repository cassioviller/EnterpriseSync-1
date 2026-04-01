"""
Motor de agendamento para o Módulo de Cronograma de Obras (MS Project style).
Calcula datas de início/fim respeitando dias úteis e cadeia de predecessoras.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de dias úteis
# ─────────────────────────────────────────────────────────────────────────────

def _is_dia_util(d: date, considerar_sabado: bool, considerar_domingo: bool) -> bool:
    wd = d.weekday()  # 0=Seg … 6=Dom
    if wd == 5 and not considerar_sabado:
        return False
    if wd == 6 and not considerar_domingo:
        return False
    return True


def proximo_dia_util(d: date, considerar_sabado: bool, considerar_domingo: bool) -> date:
    """Retorna o próximo dia útil estritamente após `d`."""
    d = d + timedelta(days=1)
    while not _is_dia_util(d, considerar_sabado, considerar_domingo):
        d += timedelta(days=1)
    return d


def calcular_data_fim(data_inicio: date, duracao_dias: int,
                      considerar_sabado: bool, considerar_domingo: bool) -> date:
    """Soma `duracao_dias` dias úteis a partir de data_inicio (inclusive)."""
    if duracao_dias <= 0:
        return data_inicio
    d = data_inicio
    contados = 1
    while contados < duracao_dias:
        d += timedelta(days=1)
        if _is_dia_util(d, considerar_sabado, considerar_domingo):
            contados += 1
    return d


def dias_uteis_entre(inicio: date, fim: date,
                     considerar_sabado: bool, considerar_domingo: bool) -> int:
    """Conta dias úteis entre inicio e fim (inclusive em ambos os extremos)."""
    total = 0
    d = inicio
    while d <= fim:
        if _is_dia_util(d, considerar_sabado, considerar_domingo):
            total += 1
        d += timedelta(days=1)
    return total


# ─────────────────────────────────────────────────────────────────────────────
# Configuração do calendário
# ─────────────────────────────────────────────────────────────────────────────

def get_calendario(admin_id: int):
    """Retorna CalendarioEmpresa para admin_id (cria padrão se não existir)."""
    from models import CalendarioEmpresa, db
    cal = CalendarioEmpresa.query.filter_by(admin_id=admin_id).first()
    if not cal:
        cal = CalendarioEmpresa(
            admin_id=admin_id,
            considerar_sabado=False,
            considerar_domingo=False,
        )
        db.session.add(cal)
        db.session.commit()
    return cal


# ─────────────────────────────────────────────────────────────────────────────
# Detecção de ciclos
# ─────────────────────────────────────────────────────────────────────────────

def verificar_ciclo(tarefa_id: int, proposta_pred_id: int, admin_id: int) -> bool:
    """
    Retorna True se definir predecessora_id=proposta_pred_id na tarefa_id
    criaria uma referência circular.
    """
    from models import TarefaCronograma
    visited: set = set()
    cur = proposta_pred_id
    while cur is not None:
        if cur == tarefa_id:
            return True
        if cur in visited:
            return True
        visited.add(cur)
        t = TarefaCronograma.query.get(cur)
        if not t or t.admin_id != admin_id:
            break
        cur = t.predecessora_id
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Motor principal de recálculo
# ─────────────────────────────────────────────────────────────────────────────

def recalcular_cronograma(obra_id: int, admin_id: int) -> bool:
    """
    Recalcula as datas de todas as tarefas de uma obra.

    Algoritmo (topological):
    1. Busca CalendarioEmpresa para saber sab/dom úteis.
    2. Processa tarefas folha (sem filhas) em ordem de dependência.
       - Sem predecessora: mantém data_inicio, calcula data_fim.
       - Com predecessora: data_inicio = próximo dia útil após data_fim da pred.
    3. Atualiza tarefas pai: data_inicio = min(filhas), data_fim = max(filhas).
    4. Persiste alterações.

    Retorna True em sucesso, False em erro.
    """
    from models import TarefaCronograma, db

    try:
        cal = get_calendario(admin_id)
        sab = cal.considerar_sabado
        dom = cal.considerar_domingo

        tarefas = (
            TarefaCronograma.query
            .filter_by(obra_id=obra_id, admin_id=admin_id)
            .order_by(TarefaCronograma.ordem)
            .all()
        )
        if not tarefas:
            return True

        tarefa_map = {t.id: t for t in tarefas}

        # Identificar IDs que são pais
        pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}

        # Tarefas folha = não são pais de nenhuma outra
        folhas = [t for t in tarefas if t.id not in pai_ids]
        pais = [t for t in tarefas if t.id in pai_ids]

        # Processar folhas em ordem topológica via predecessoras
        processadas: set = set()
        pendentes = list(folhas)
        max_iter = len(pendentes) * 3 + 10

        for _ in range(max_iter):
            if not pendentes:
                break
            progrediu = False
            for tarefa in list(pendentes):
                pred_ok = (
                    tarefa.predecessora_id is None
                    or tarefa.predecessora_id in processadas
                    or tarefa.predecessora_id not in tarefa_map
                )
                if not pred_ok:
                    continue

                pred = tarefa_map.get(tarefa.predecessora_id)
                if pred is not None and pred.data_fim:
                    tarefa.data_inicio = proximo_dia_util(pred.data_fim, sab, dom)
                elif tarefa.data_inicio is None:
                    tarefa.data_inicio = date.today()

                if tarefa.data_inicio:
                    dur = max(tarefa.duracao_dias or 1, 1)
                    tarefa.data_fim = calcular_data_fim(tarefa.data_inicio, dur, sab, dom)

                processadas.add(tarefa.id)
                pendentes.remove(tarefa)
                progrediu = True

            if not progrediu:
                # Forçar processamento de tarefas restantes (ciclos quebrados)
                for tarefa in list(pendentes):
                    if tarefa.data_inicio:
                        dur = max(tarefa.duracao_dias or 1, 1)
                        tarefa.data_fim = calcular_data_fim(tarefa.data_inicio, dur, sab, dom)
                    processadas.add(tarefa.id)
                pendentes.clear()

        # Atualizar tarefas pai a partir das filhas (de folhas para raiz)
        for pai in sorted(pais, key=lambda t: t.ordem, reverse=True):
            filhas = [t for t in tarefas if t.tarefa_pai_id == pai.id]
            com_datas = [f for f in filhas if f.data_inicio and f.data_fim]
            if com_datas:
                pai.data_inicio = min(f.data_inicio for f in com_datas)
                pai.data_fim = max(f.data_fim for f in com_datas)
                pai.duracao_dias = dias_uteis_entre(
                    pai.data_inicio, pai.data_fim, sab, dom
                )

        db.session.commit()
        logger.info(
            f"[OK] Cronograma recalculado: obra_id={obra_id}, "
            f"{len(tarefas)} tarefas processadas"
        )
        return True

    except Exception as e:
        logger.error(f"[ERROR] recalcular_cronograma obra_id={obra_id}: {e}")
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return False
