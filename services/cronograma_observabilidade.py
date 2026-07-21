"""Observabilidade da importação de cronograma (M10 §4.3).

Duas responsabilidades, sem dependência nova:

1. **Log estruturado** — logger `cronograma.importacao`, uma linha por
   transição de status, sempre com `importacao_id` (e `obra_id` quando
   conhecido). É o rastro que o suporte lê quando a jornada trava.

2. **Consolidação de métricas** — `metricas_da_importacao` reconstrói a
   linha de métricas a partir de `cronograma_importacao_evento.detalhes`
   (a trilha de auditoria do M02 já é a fonte de verdade; não há tabela
   nova nem escrita duplicada). Consumida pela lista da aba Cronograma
   (M08) e pelos testes.

As chaves seguem a spec §4.3. `tempo_parse_ms`/`n_tarefas`/`n_avisos` vêm
do M03/M04; `matches_por_nivel`/`n_auto`/`n_conflitos` da reconciliação
(M05); `n_manuais`/`tempo_total_ms` da aplicação; `rollbacks` das
restaurações. Campos de "tempo de API/tokens/custo" da spec original não
se aplicam — o pipeline é determinístico e local.
"""
from __future__ import annotations

import logging

logger = logging.getLogger('cronograma.importacao')

# Eventos que marcam transição de status (os demais são informativos).
TRANSICOES = {
    'upload', 'parse_ok', 'parse_erro', 'normalizado', 'normalizacao_erro',
    'reconciliado', 'aplicado', 'cancelado', 'rollback',
}


def log_transicao(evento: str, importacao_id: int, obra_id=None,
                  erro: bool = False, **campos) -> None:
    """Uma linha estruturada por transição. Nunca levanta."""
    try:
        partes = [f'evento={evento}', f'importacao_id={importacao_id}']
        if obra_id is not None:
            partes.append(f'obra_id={obra_id}')
        partes.extend(f'{k}={v}' for k, v in sorted(campos.items())
                      if v is not None)
        linha = ' '.join(partes)
        if erro:
            logger.error(linha)
        else:
            logger.info(linha)
    except Exception:  # observabilidade nunca derruba o fluxo
        logger.debug('falha ao logar transição de importação', exc_info=True)


def metricas_da_importacao(importacao_id: int) -> dict:
    """Métricas §4.3 consolidadas dos eventos. Requer app_context.

    Chaves ausentes significam "a etapa ainda não aconteceu" — a linha é
    parcial por desenho (a importação pode estar no meio da jornada).
    """
    from models import CronogramaImportacaoEvento

    eventos = (CronogramaImportacaoEvento.query
               .filter_by(importacao_id=importacao_id)
               .order_by(CronogramaImportacaoEvento.id.asc())
               .all())
    por_evento = {}
    for ev in eventos:
        por_evento.setdefault(ev.evento, []).append(ev.detalhes or {})

    def _ultimo(nome, chave, padrao=None):
        lista = por_evento.get(nome)
        return lista[-1].get(chave, padrao) if lista else padrao

    metricas = {}

    tamanho = _ultimo('upload', 'tamanho')
    if tamanho is not None:
        metricas['tamanho_bytes'] = tamanho

    if 'parse_ok' in por_evento:
        metricas['tempo_parse_ms'] = _ultimo('parse_ok', 'tempo_parse_ms')
        metricas['n_tarefas'] = _ultimo('parse_ok', 'n_tarefas')

    if 'normalizado' in por_evento:
        det = por_evento['normalizado'][-1]
        if det.get('n_tarefas') is not None:
            metricas['n_tarefas'] = det['n_tarefas']
        avisos = det.get('n_avisos') or {}
        metricas['n_avisos'] = (sum(avisos.values())
                                if isinstance(avisos, dict) else avisos)
        metricas['avisos_por_codigo'] = avisos if isinstance(avisos, dict) else {}

    if 'reconciliado' in por_evento:
        det = por_evento['reconciliado'][-1]
        metricas['matches_por_nivel'] = det.get('matches_por_nivel', {})
        metricas['n_auto'] = det.get('n_auto')
        metricas['n_conflitos'] = det.get('n_conflitos',
                                          det.get('pendencias'))

    if 'aplicado' in por_evento:
        det = por_evento['aplicado'][-1]
        metricas['n_manuais'] = det.get('decisoes_manuais')
        metricas['tempo_total_ms'] = det.get('tempo_total_ms')
        # A aplicação recontabiliza o matching de fato aplicado.
        if det.get('matching_por_nivel'):
            metricas['matches_por_nivel'] = det['matching_por_nivel']

    metricas['rollbacks'] = len(por_evento.get('rollback', []))
    return metricas
