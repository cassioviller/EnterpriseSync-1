"""Carga única de obra por JSON — cronograma + RDOs, sem apagar nada.

O upload da página da obra (aba RDOs → "Atualizar por JSON") consome o
arquivo que `scripts/preparar_carga_obra.py` gera: um JSON autossuficiente
com o cronograma do .mpp, os RDOs mesclados do WhatsApp e o mapa de nomes.
É a versão em uma etapa do fluxo do RDO.md §6 (que antes exigia importar
o .mpp pela tela E rodar o script no servidor).

Disciplina — a mesma do M05 e do `atualizar_rdos`, nunca DELETE:

  * tarefa do JSON casada com viva (por `mpp_uid`, senão por nome único
    entre as ainda não casadas) → UPDATE in-place: id preservado (RDOs e
    medições intactos), `mpp_uid` backfillado, datas/duração/ordem/pai do
    JSON; `percentual_concluido` NUNCA é tocado aqui — o % entra pelos
    apontamentos dos RDOs (fonte de verdade física);
  * tarefa do JSON sem par → INSERT;
  * viva sem par no JSON → `ativa=False` (arquivamento lógico M05);
  * versão: a ativa anterior ganha snapshot (se não tinha), é arquivada, e
    a nova versão ativa nasce com snapshot do estado aplicado — há sempre
    a que restaurar;
  * RDOs: upsert por data via `services/atualizacao_rdos.py` (imutável é
    pulado, foto existente preservada, retrocesso vira pendência);
  * assert anti-DELETE: a contagem total de tarefas (vivas+arquivadas)
    nunca encolhe;
  * `dry_run=True`: tudo roda e a transação inteira (cronograma + RDOs)
    é revertida pelo rollback do `atualizar_rdos` — relatório igual,
    banco intacto.

Transação: a fase de cronograma NÃO comita; `atualizar_rdos` fecha a
transação (commit ou rollback) levando as duas fases juntas.
"""
from __future__ import annotations

import logging
import os
import unicodedata
from datetime import date, datetime

logger = logging.getLogger(__name__)

FORMATO_CARGA = 'carga-obra/1.0'


class CargaInvalida(Exception):
    """Payload inaceitável — mensagem pronta para a UI."""


def _sem_acento(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto or '')
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


def _data(valor):
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def validar_payload(payload, obra):
    """Formato e destino. O JSON diz de que obra é — subir na obra errada
    é o erro mais provável do fluxo, e tem que falhar ANTES de escrever."""
    formato = str((payload.get('_meta') or {}).get('formato', ''))
    if not formato.startswith('carga-obra/1.'):
        raise CargaInvalida(
            f'formato desconhecido: {formato!r} — gere o arquivo com '
            f'scripts/preparar_carga_obra.py')
    alvo = payload.get('obra') or {}
    if alvo.get('id') != obra.id and (
            not alvo.get('codigo') or alvo.get('codigo') != obra.codigo):
        raise CargaInvalida(
            f'este JSON é da obra {alvo.get("codigo") or alvo.get("id")} '
            f'("{alvo.get("nome")}"), não desta '
            f'({obra.codigo or obra.id} — "{obra.nome}")')
    if not payload.get('rdos') and not payload.get('cronograma_tarefas'):
        raise CargaInvalida('JSON sem "cronograma_tarefas" e sem "rdos" — '
                            'nada a aplicar')


def _fotos_base_segura(payload):
    """Base de fotos declarada no JSON, presa dentro de fotos_rdos/."""
    rel = (payload.get('fotos_base') or '').strip()
    if not rel:
        return None
    raiz = os.getcwd()
    candidato = os.path.normpath(os.path.join(raiz, rel))
    base_fotos = os.path.normpath(os.path.join(raiz, 'fotos_rdos'))
    if os.path.isabs(rel) or not candidato.startswith(base_fotos + os.sep):
        raise CargaInvalida(f'fotos_base inválida: {rel!r} — precisa ser '
                            f'relativa e dentro de fotos_rdos/')
    return candidato


def _atualizar_cronograma(obra, admin_id, tarefas_json):
    """Fase 1: aplica a estrutura do JSON sobre o cronograma vivo.

    Devolve o relatório da fase. Faz flush, NUNCA commit.
    """
    from app import db
    from models import TarefaCronograma

    rel = {'casadas_uid': 0, 'casadas_nome': 0, 'inseridas': 0,
           'arquivadas': [], 'avisos': []}

    vivas = TarefaCronograma.do_cronograma_interno(obra.id, admin_id).all()
    total_antes = (TarefaCronograma.query
                   .filter_by(obra_id=obra.id, admin_id=admin_id,
                              is_cliente=False).count())
    por_uid = {}
    por_nome = {}
    for t in vivas:
        if t.mpp_uid is not None:
            por_uid[int(t.mpp_uid)] = t
        por_nome.setdefault(_sem_acento(t.nome_tarefa), []).append(t)

    casadas_ids, aplicadas = set(), {}
    # ordem do arquivo = ordem do cronograma; pilha por nível dá o pai
    pilha = {}
    itens = [t for t in tarefas_json if int(t.get('outline') or 0) >= 1]
    for pos, tj in enumerate(itens, start=1):
        uid = int(tj['uid'])
        nome = (tj.get('nome') or '').strip() or f'Tarefa {uid}'
        nivel = int(tj.get('outline') or 1)

        alvo = por_uid.get(uid)
        if alvo is not None and alvo.id not in casadas_ids:
            rel['casadas_uid'] += 1
        else:
            alvo = None
            candidatos = [t for t in por_nome.get(_sem_acento(nome), [])
                          if t.id not in casadas_ids]
            if len(candidatos) == 1:
                alvo = candidatos[0]
                rel['casadas_nome'] += 1
            elif len(candidatos) > 1:
                rel['avisos'].append(
                    f'"{nome}": {len(candidatos)} tarefas vivas com esse '
                    f'nome — nenhuma casada (ambíguo); entrou como nova')

        if alvo is None:
            alvo = TarefaCronograma(
                obra_id=obra.id, admin_id=admin_id, nome_tarefa=nome,
                ordem=pos, duracao_dias=1)
            db.session.add(alvo)
            rel['inseridas'] += 1

        alvo.mpp_uid = uid
        alvo.nome_tarefa = nome
        alvo.ordem = pos
        alvo.data_inicio = _data(tj.get('inicio'))
        alvo.data_fim = _data(tj.get('fim'))
        if tj.get('dias'):
            alvo.duracao_dias = max(1, int(round(float(tj['dias']))))
        # percentual_concluido: NUNCA aqui — vem dos apontamentos dos RDOs.
        db.session.flush()
        casadas_ids.add(alvo.id)

        # pilha por nível de outline: o pai é o último nível ACIMA do meu
        for n in [n for n in pilha if n >= nivel]:
            del pilha[n]
        alvo.tarefa_pai_id = pilha[max(pilha)] if pilha else None
        pilha[nivel] = alvo.id

    agora = datetime.utcnow()
    for t in vivas:
        if t.id not in casadas_ids:
            t.ativa = False
            t.arquivada_em = agora
            rel['arquivadas'].append(t.nome_tarefa)

    db.session.flush()
    total_depois = (TarefaCronograma.query
                    .filter_by(obra_id=obra.id, admin_id=admin_id,
                               is_cliente=False).count())
    assert total_depois >= total_antes, \
        'carga JSON nunca remove tarefa — bug interno, abortando'
    return rel


def _versionar(obra, admin_id, usuario_id, observacao):
    """Arquiva a versão ativa (com snapshot, se faltava) e cria a nova
    ativa com snapshot do estado recém-aplicado. Flush, nunca commit."""
    from app import db
    from models import (CronogramaTarefaSnapshot, CronogramaVersao,
                        TarefaCronograma)
    from services.cronograma_versao_service import _snapshot_versao

    vivas = (TarefaCronograma.do_cronograma_interno(obra.id, admin_id)
             .order_by(TarefaCronograma.ordem).all())
    atual = (CronogramaVersao.query
             .filter_by(obra_id=obra.id, status='ativa').first())
    numero = 1
    if atual is not None:
        tem_snapshot = (CronogramaTarefaSnapshot.query
                        .filter_by(versao_id=atual.id).first() is not None)
        if not tem_snapshot:
            # o snapshot da anterior é o "antes" — sem ele não há restauro
            _snapshot_versao(atual, vivas, admin_id)
        atual.status = 'arquivada'
        # flush ANTES de criar a nova: o índice parcial uq (uma ativa por
        # obra) veria duas ativas se o INSERT fosse ao banco primeiro.
        db.session.flush()
        numero = (db.session.query(db.func.max(CronogramaVersao.numero))
                  .filter_by(obra_id=obra.id).scalar() or 0) + 1
    nova = CronogramaVersao(
        obra_id=obra.id, admin_id=admin_id, numero=numero, status='ativa',
        aplicada_em=datetime.utcnow(), aplicada_por_id=usuario_id,
        observacao=observacao)
    db.session.add(nova)
    db.session.flush()
    _snapshot_versao(nova, vivas, admin_id)
    return nova


def aplicar_carga_obra(obra, admin_id, payload, usuario_id=None,
                       dry_run=True):
    """Aplica o JSON de carga na obra. Devolve o relatório combinado.

    `dry_run=True` roda TUDO (cronograma + RDOs) e reverte — o rollback
    de `atualizar_rdos` desfaz as duas fases, que dividem a transação.
    """
    from services.atualizacao_rdos import atualizar_rdos

    validar_payload(payload, obra)
    base_fotos = _fotos_base_segura(payload)

    # Aquece o calendário ANTES de abrir trabalho: `get_calendario` COMITA
    # quando não existe (mesma armadilha documentada em atualizar_rdos) —
    # sem isto, o commit alheio gravaria a fase de cronograma no meio de
    # um dry_run.
    from utils.cronograma_engine import get_calendario
    get_calendario(admin_id)

    rel = {'cronograma': None, 'rdos': None, 'dry_run': dry_run}

    tarefas_json = payload.get('cronograma_tarefas') or []
    if tarefas_json:
        rel['cronograma'] = _atualizar_cronograma(obra, admin_id,
                                                  tarefas_json)
        _versionar(obra, admin_id, usuario_id,
                   f'Carga JSON de {date.today().isoformat()} '
                   f'({len(tarefas_json)} tarefas do arquivo)')

    itens = payload.get('rdos') or []
    if itens:
        # atualizar_rdos fecha a transação (commit das DUAS fases, ou
        # rollback no dry_run) e roda a sincronização de % pós-commit —
        # regra geral do motor: com RDOs, o % vem dos apontamentos.
        mapa = {int(k): v
                for k, v in (payload.get('mapa_nomes') or {}).items()}
        rel['rdos'] = atualizar_rdos(
            obra, admin_id, itens,
            dry_run=dry_run, com_fotos=base_fotos is not None,
            base_fotos=base_fotos, mapa_mpp_nome=mapa or None)
    else:
        # Carga SÓ de cronograma: fecha a transação aqui e NÃO sincroniza
        # — a sincronização recalcula % a partir dos apontamentos e
        # zeraria tarefa sem apontamento (12% manual viraria 0).
        from app import db
        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()
        rel['rdos'] = {'criados': [], 'atualizados': [], 'pulados': [],
                       'apontamentos': 0, 'fotos': 0, 'pendencias': [],
                       'avisos': ['payload sem seção "rdos" — só o '
                                  'cronograma foi atualizado']
                       + (['dry-run: transação revertida, nada gravado']
                          if dry_run else [])}
    return rel


def formatar_relatorio_carga(rel, obra):
    from services.atualizacao_rdos import formatar_relatorio
    linhas = [f'[carga_obra_json] obra {obra.nome!r} '
              f'({obra.codigo or obra.id})'
              + ('  — PRÉVIA (nada gravado)' if rel['dry_run'] else '')]
    c = rel['cronograma']
    if c:
        linhas += [
            f'  cronograma: {c["casadas_uid"]} casada(s) por uid, '
            f'{c["casadas_nome"]} por nome, {c["inseridas"]} inserida(s), '
            f'{len(c["arquivadas"])} arquivada(s) — nada apagado',
        ]
        if c['arquivadas']:
            linhas.append('    arquivadas: ' + ', '.join(c['arquivadas'][:12])
                          + (' …' if len(c['arquivadas']) > 12 else ''))
        linhas += [f'    - {a}' for a in c['avisos']]
    else:
        linhas.append('  cronograma: (sem seção no JSON — não tocado)')
    linhas.append(formatar_relatorio(rel['rdos']))
    return '\n'.join(linhas)
