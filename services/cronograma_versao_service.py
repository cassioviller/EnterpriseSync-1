"""Aplicação transacional de versão de cronograma (M05, Task 2).

`aplicar_versao(importacao_id, decisoes, usuario_id)` pega uma importação
`aguardando_revisao` (relatorio_diff do M05 Task 1 + json_normalizado do
M04) e aplica a nova versão sobre o cronograma vivo da obra:

- casadas → UPDATE in-place (IDs preservados ⇒ RDOs/medições intactos);
- novas → INSERT com `versao_criacao_id` da nova versão;
- removidas/divididas/fundidas → arquivamento lógico (`ativa=False`) —
  NUNCA DELETE (FKs CASCADE de RDOApontamentoCronograma etc. destruiriam
  apontamentos; há assert anti-DELETE no fim);
- `percentual_concluido` NUNCA é sobrescrito em casadas; `pct_project` só
  vira realizado se a obra não tem NENHUM RDO (carga inicial);
- quantidade/unidade só atualizam quando o arquivo novo traz valor (o M04
  hoje entrega sempre None — nunca apagamos quantidade preenchida na UI);
- a versão ativa anterior é arquivada NA MESMA transação (índice parcial
  uq_cron_versao_uma_ativa) e ganha snapshot integral se ainda não tinha;
  a nova versão ativa ganha snapshot do estado recém-aplicado.

Decisões (`decisoes`: dict id_temp → {'acao': ..., 'chave_nova': ...?}):
todo mapeamento com `decisao_requerida=true` (ambigua/revisao_manual/
dividida/fundida e as novas envolvidas em split/merge) PRECISA de decisão:
  - {'acao': 'casar', 'chave_nova': K} — casa a tarefa atual com K;
  - {'acao': 'arquivar'} — confirma remoção (arquiva);
  - {'acao': 'nova'} — confirma inserção de uma tarefa nova.
Uma 'nova' cuja chave foi consumida por um 'casar' fica satisfeita
implicitamente (o par virou correspondência). Decisão sobre mapeamento
sem pendência é erro (`DecisaoInvalida`) — auto-matches não se
sobrescrevem nesta versão.

Transação: todo o trabalho estrutural (snapshot, arquivamentos, updates,
inserts, versão, eventos, status) faz flush numa transação única com
`SELECT FOR UPDATE` na obra (anti-concorrência) e UM commit no fim.
`recalcular_cronograma`/`sincronizar_percentuais_obra` comitam
internamente (motor legado), então rodam APÓS o commit estrutural: falha
de recálculo não desfaz a aplicação (o estado fica consistente e
re-recalculável); qualquer exceção antes disso ⇒ rollback total.

Plano: docs/superpowers/plans/2026-07-20-modulo-05-implementacao-reconciliacao.md (Task 2).
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime

from sqlalchemy import func

from app import db
from models import (
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    CronogramaTarefaSnapshot,
    CronogramaVersao,
    Obra,
    RDO,
    TarefaCronograma,
)
from utils.cronograma_engine import (
    recalcular_cronograma,
    sincronizar_percentuais_obra,
)

logger = logging.getLogger(__name__)


class AplicacaoVersaoError(Exception):
    """Base dos erros de aplicação (mensagem já apta a ir para a UI)."""


class EstadoInvalido(AplicacaoVersaoError):
    """Importação inexistente, status errado ou diff desatualizado."""


class PendenciasSemDecisao(AplicacaoVersaoError):
    """Há mapeamentos com decisao_requerida sem decisão registrada."""

    def __init__(self, id_temps):
        self.id_temps = sorted(id_temps)
        super().__init__(
            f'{len(self.id_temps)} pendência(s) sem decisão: '
            f'id_temp {self.id_temps}')


class DecisaoInvalida(AplicacaoVersaoError):
    """Decisão malformada, conflitante ou sobre mapeamento sem pendência."""


# ---------------------------------------------------------------------------
# Helpers puros de conversão
# ---------------------------------------------------------------------------

def _data(valor):
    return date.fromisoformat(valor[:10]) if valor else None


def _duracao(dias, fallback):
    """dias (float|None) do normalizado → duracao_dias (int NOT NULL)."""
    return int(round(dias)) if dias is not None else fallback


def _primeira_fs(n):
    """Chave da primeira predecessora FS do normalizado (contrato M05:
    `predecessora_id` única sem tipo/lag; a lista tipada completa vive só
    no snapshot)."""
    for p in n.get('predecessoras') or []:
        if p.get('tipo') == 'FS':
            return p['chave']
    return None


# ---------------------------------------------------------------------------
# Snapshot integral de um conjunto de tarefas numa versão
# ---------------------------------------------------------------------------

def _snapshot_versao(versao, tarefas, admin_id, preds_tipadas=None):
    """Fotografa `tarefas` (vivas) em CronogramaTarefaSnapshot da `versao`.

    `preds_tipadas`: dict tarefa_id → lista {tarefa_id, uid, tipo, lag_dias}
    (disponível ao aplicar um normalizado); sem ela, deriva da
    `predecessora_id` única como FS/lag 0. `is_resumo` é inferido (tem
    filhas), como no resto do sistema.
    """
    preds_tipadas = preds_tipadas or {}
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    por_id = {t.id: t for t in tarefas}

    snaps = {}
    for t in tarefas:
        if t.id in preds_tipadas:
            preds = preds_tipadas[t.id]
        elif t.predecessora_id and t.predecessora_id in por_id:
            pred = por_id[t.predecessora_id]
            preds = [{'tarefa_id': pred.id, 'uid': pred.mpp_uid,
                      'tipo': 'FS', 'lag_dias': 0}]
        else:
            preds = []
        snap = CronogramaTarefaSnapshot(
            versao_id=versao.id,
            admin_id=admin_id,
            tarefa_id=t.id,
            mpp_uid=t.mpp_uid,
            wbs_codigo=t.wbs_codigo,
            nome_tarefa=t.nome_tarefa,
            predecessoras_json=preds,
            ordem=t.ordem,
            data_inicio=t.data_inicio,
            data_fim=t.data_fim,
            duracao_dias=t.duracao_dias,
            quantidade_total=t.quantidade_total,
            unidade_medida=t.unidade_medida,
            is_marco=t.is_marco,
            is_resumo=t.id in pai_ids,
            percentual_concluido_no_momento=t.percentual_concluido,
            # fingerprint não tem coluna própria no snapshot — vai no
            # payload_extra para a restauração devolver a identidade M04.
            payload_extra={'fingerprint': t.fingerprint},
        )
        db.session.add(snap)
        snaps[t.id] = snap
    db.session.flush()  # ids dos snapshots, para o self-FK de pai
    for t in tarefas:
        if t.tarefa_pai_id and t.tarefa_pai_id in snaps:
            snaps[t.id].tarefa_pai_snapshot_id = snaps[t.tarefa_pai_id].id
    db.session.flush()
    return snaps


# ---------------------------------------------------------------------------
# Resolução mapeamentos + decisões → plano final (matches/inserir/arquivar)
# ---------------------------------------------------------------------------

def _resolver_plano(rel, novos, vivas_por_id, decisoes):
    matches = {}      # tarefa_atual_id → chave_nova
    inserir = []      # chaves a inserir (ordem do relatório = ordem do arquivo)
    arquivar = []     # tarefa ids a arquivar
    pendencias = []

    mapeamentos = rel['mapeamentos']
    ids_no_diff = {m['tarefa_atual_id'] for m in mapeamentos
                   if m['tarefa_atual_id'] is not None}
    if ids_no_diff != set(vivas_por_id):
        raise EstadoInvalido(
            'O cronograma mudou depois da reconciliação — execute a '
            'reconciliação novamente antes de aplicar.')

    # 1ª passada: decisões 'casar' (consomem chaves e satisfazem 'nova').
    chaves_casadas_por_decisao = set()
    for m in mapeamentos:
        dec = decisoes.get(m['id_temp'])
        if dec is None:
            continue
        if not m['decisao_requerida']:
            raise DecisaoInvalida(
                f"id_temp {m['id_temp']} não requer decisão")
        if dec.get('acao') == 'casar':
            chave = dec.get('chave_nova')
            if m['tarefa_atual_id'] is None:
                raise DecisaoInvalida(
                    f"id_temp {m['id_temp']}: 'casar' só vale para "
                    f'mapeamento com tarefa atual')
            if chave not in novos:
                raise DecisaoInvalida(
                    f"id_temp {m['id_temp']}: chave_nova {chave!r} não "
                    f'existe no arquivo importado')
            if chave in chaves_casadas_por_decisao:
                raise DecisaoInvalida(
                    f'chave_nova {chave!r} usada em mais de uma decisão')
            chaves_casadas_por_decisao.add(chave)

    # 2ª passada: monta o plano.
    chaves_usadas = set(chaves_casadas_por_decisao)
    for m in mapeamentos:
        id_temp, tipos = m['id_temp'], m['tipo']
        dec = decisoes.get(id_temp)
        ta_id, chave = m['tarefa_atual_id'], m['chave_nova']

        if not m['decisao_requerida']:
            if ta_id is not None and chave is not None:      # casada auto
                if chave in chaves_usadas:
                    raise DecisaoInvalida(
                        f'chave_nova {chave!r} consumida por decisão manual '
                        f'conflita com correspondência automática')
                chaves_usadas.add(chave)
                matches[ta_id] = chave
            elif chave is not None:                          # nova simples
                # Chave consumida por um 'casar' manual (ex.: ambígua
                # resolvida para um dos candidatos): não insere de novo.
                if chave not in chaves_casadas_por_decisao:
                    chaves_usadas.add(chave)
                    inserir.append(chave)
            else:                                            # removida
                arquivar.append(ta_id)
            continue

        # Pendência: 'nova' cuja chave foi consumida por 'casar' está
        # implicitamente resolvida (virou correspondência manual).
        if dec is None:
            if ta_id is None and chave in chaves_casadas_por_decisao:
                continue
            pendencias.append(id_temp)
            continue

        acao = dec.get('acao')
        if acao == 'casar':
            matches[ta_id] = dec['chave_nova']               # validada acima
        elif acao == 'arquivar':
            if ta_id is None:
                raise DecisaoInvalida(
                    f"id_temp {id_temp}: 'arquivar' exige tarefa atual")
            arquivar.append(ta_id)
        elif acao == 'nova':
            if chave is None:
                raise DecisaoInvalida(
                    f"id_temp {id_temp}: 'nova' só vale para mapeamento "
                    f'de tarefa nova')
            if chave in chaves_usadas:
                raise DecisaoInvalida(
                    f"id_temp {id_temp}: chave {chave!r} já consumida por "
                    f"decisão 'casar' — conflito")
            chaves_usadas.add(chave)
            inserir.append(chave)
        else:
            raise DecisaoInvalida(
                f'id_temp {id_temp}: ação desconhecida {acao!r}')

    if pendencias:
        raise PendenciasSemDecisao(pendencias)
    return matches, inserir, arquivar


# ---------------------------------------------------------------------------
# Fusão quantitativa (sugestão confirmada pelas decisões)
# ---------------------------------------------------------------------------

def _transferir_fusao(rel, novos_ids, vivas_por_id, arquivar, inserir):
    """Se uma sugestão 'fundida' foi integralmente confirmada (todas as
    antigas arquivadas + a nova inserida) e TODAS as antigas têm a mesma
    unidade e quantidade, a nova herda quantidade somada e o realizado
    ponderado — o avanço físico não zera com a fusão."""
    arquivadas = set(arquivar)
    inseridas = set(inserir)
    for s in rel.get('sugestoes_split_merge') or []:
        if s['tipo'] != 'fundida':
            continue
        if s['nova_chave'] not in inseridas:
            continue
        if not set(s['antigas_ids']) <= arquivadas:
            continue
        antigas = [vivas_por_id[i] for i in s['antigas_ids']]
        unidades = {t.unidade_medida for t in antigas}
        if len(unidades) != 1 or unidades == {None}:
            continue
        if any(not t.quantidade_total for t in antigas):
            continue
        nova = novos_ids[s['nova_chave']]
        soma = sum(t.quantidade_total for t in antigas)
        executado = sum(
            (t.percentual_concluido or 0.0) / 100.0 * t.quantidade_total
            for t in antigas)
        nova.quantidade_total = soma
        nova.unidade_medida = unidades.pop()
        nova.percentual_concluido = round(min(100.0, executado / soma * 100), 2)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def aplicar_versao(importacao_id: int, decisoes: dict | None,
                   usuario_id: int | None) -> CronogramaVersao:
    """Aplica a importação como nova versão ativa do cronograma da obra.

    Levanta EstadoInvalido / PendenciasSemDecisao / DecisaoInvalida (sempre
    com rollback total). Devolve a CronogramaVersao criada (já commitada).
    """
    decisoes = {int(k): v for k, v in (decisoes or {}).items()}
    try:
        versao, obra_id, admin_id, tem_rdo = _aplicar(
            importacao_id, decisoes, usuario_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # Pós-commit: motor legado comita internamente (ver docstring do módulo).
    # Obra sem NENHUM RDO: o motor não roda — recalcular/sincronizar zeram
    # folhas sem apontamento, o que apagaria a carga inicial de pct_project;
    # as datas ficam fielmente as do arquivo (o MS Project já as calculou).
    # Assim que a obra tem RDO, o motor local volta a ser a fonte de verdade.
    if tem_rdo:
        if not recalcular_cronograma(obra_id, admin_id, cliente=False):
            logger.warning('recalcular_cronograma falhou após aplicar versão '
                           '%s da obra %s (estado aplicado permanece válido)',
                           versao.numero, obra_id)
        sincronizar_percentuais_obra(obra_id, admin_id, cliente=False)
    return versao


def _aplicar(importacao_id, decisoes, usuario_id):
    imp = db.session.get(CronogramaImportacao, importacao_id)
    if imp is None:
        raise EstadoInvalido(f'Importação {importacao_id} não encontrada.')
    admin_id = imp.admin_id

    # Lock anti-concorrência: segunda aplicação simultânea bloqueia aqui e,
    # ao acordar, encontra status != aguardando_revisao ⇒ falha limpa.
    obra = (db.session.query(Obra)
            .filter_by(id=imp.obra_id, admin_id=admin_id)
            .with_for_update().first())
    if obra is None:
        raise EstadoInvalido('Obra da importação não encontrada.')
    db.session.refresh(imp)
    if imp.status != 'aguardando_revisao':
        raise EstadoInvalido(
            f"Importação {imp.id} está '{imp.status}' — só se aplica em "
            f"'aguardando_revisao'.")
    rel = imp.relatorio_diff
    norm = imp.json_normalizado
    if not rel or not norm:
        raise EstadoInvalido(
            f'Importação {imp.id} sem relatório de reconciliação.')

    novos = {t['chave']: t for t in norm['tarefas']}
    vivas = (TarefaCronograma.query
             .filter_by(obra_id=obra.id, admin_id=admin_id, is_cliente=False)
             .filter(TarefaCronograma.ativa.is_(True))
             .all())
    vivas_por_id = {t.id: t for t in vivas}

    matches, inserir, arquivar = _resolver_plano(
        rel, novos, vivas_por_id, decisoes)

    n_tarefas_antes = (db.session.query(func.count(TarefaCronograma.id))
                       .filter_by(obra_id=obra.id, admin_id=admin_id,
                                  is_cliente=False)
                       .scalar())

    # Snapshot da versão ativa atual, se existir e ainda não fotografada.
    versao_atual = (CronogramaVersao.query
                    .filter_by(obra_id=obra.id, status='ativa')
                    .first())
    if versao_atual is not None:
        tem_snapshot = (db.session.query(CronogramaTarefaSnapshot.id)
                        .filter_by(versao_id=versao_atual.id)
                        .first() is not None)
        if not tem_snapshot and vivas:
            _snapshot_versao(versao_atual, vivas, admin_id)

    # Arquiva a versão ativa e cria a nova NA MESMA transação (índice
    # parcial uq_cron_versao_uma_ativa é checado por statement).
    maior = (db.session.query(func.max(CronogramaVersao.numero))
             .filter_by(obra_id=obra.id).scalar()) or 0
    if versao_atual is not None:
        versao_atual.status = 'arquivada'
        db.session.flush()
    nova_versao = CronogramaVersao(
        obra_id=obra.id,
        admin_id=admin_id,
        numero=maior + 1,
        status='ativa',
        importacao_id=imp.id,
        aplicada_em=datetime.utcnow(),
        aplicada_por_id=usuario_id,
        observacao=f'importação #{imp.id} ({imp.arquivo_nome})',
    )
    db.session.add(nova_versao)
    db.session.flush()

    # INSERTs primeiro (sem pai/predecessora — resolvidos após o flush,
    # quando toda chave tem id), depois UPDATEs in-place, depois arquivamento.
    novos_ids = {}    # chave → TarefaCronograma inserida
    for chave in inserir:
        n = novos[chave]
        t = TarefaCronograma(
            obra_id=obra.id,
            admin_id=admin_id,
            is_cliente=False,
            nome_tarefa=(n['nome_original'] or n['nome_normalizado'])[:200],
            ordem=n['ordem'],
            duracao_dias=_duracao(n['dias'], 1),
            data_inicio=_data(n['inicio']),
            data_fim=_data(n['fim']),
            quantidade_total=n['quantidade_total'],
            unidade_medida=n['unidade'],
            mpp_uid=n['uid'],
            wbs_codigo=n['wbs'],
            fingerprint=n['fingerprint'],
            is_marco=n['is_marco'],
            versao_criacao_id=nova_versao.id,
            percentual_concluido=0.0,
        )
        db.session.add(t)
        novos_ids[chave] = t
    db.session.flush()

    id_por_chave = {chave: t.id for chave, t in novos_ids.items()}
    aplicadas = dict(novos_ids)          # chave → tarefa (novas + casadas)
    for ta_id, chave in matches.items():
        t = vivas_por_id[ta_id]
        n = novos[chave]
        t.nome_tarefa = (n['nome_original'] or n['nome_normalizado'])[:200]
        t.ordem = n['ordem']
        t.duracao_dias = _duracao(n['dias'], t.duracao_dias)
        t.data_inicio = _data(n['inicio'])
        t.data_fim = _data(n['fim'])
        # Identidade espelha o arquivo aplicado (inclusive None): é ela que
        # alimenta a PRÓXIMA reconciliação.
        t.mpp_uid = n['uid']
        t.wbs_codigo = n['wbs']
        t.fingerprint = n['fingerprint']
        t.is_marco = n['is_marco']
        # M04 nunca inventa quantidade/unidade (hoje sempre None): só
        # atualiza quando o arquivo trouxer valor — nunca apaga o que o
        # usuário preencheu na UI. percentual_concluido NUNCA é tocado.
        if n['quantidade_total'] is not None:
            t.quantidade_total = n['quantidade_total']
        if n['unidade'] is not None:
            t.unidade_medida = n['unidade']
        id_por_chave[chave] = t.id
        aplicadas[chave] = t

    # Hierarquia e predecessora única (primeira FS) com o mapa completo.
    for chave, t in aplicadas.items():
        n = novos[chave]
        t.tarefa_pai_id = id_por_chave.get(n['pai_chave'])
        fs = _primeira_fs(n)
        t.predecessora_id = id_por_chave.get(fs) if fs else None

    agora = datetime.utcnow()
    for ta_id in arquivar:
        t = vivas_por_id[ta_id]
        t.ativa = False
        t.arquivada_em = agora

    _transferir_fusao(rel, novos_ids, vivas_por_id, arquivar, inserir)

    # Carga inicial de pct_project SOMENTE se a obra nunca teve RDO.
    tem_rdo = (db.session.query(RDO.id)
               .filter_by(obra_id=obra.id).first() is not None)
    if not tem_rdo:
        for chave, t in aplicadas.items():
            pct = novos[chave].get('pct_project')
            if pct:
                t.percentual_concluido = float(pct)

    db.session.flush()

    # Assert anti-DELETE: aplicar versão só cria/atualiza/arquiva — se a
    # contagem total (viva+arquivada) encolheu, é bug interno: aborta tudo.
    n_tarefas_depois = (db.session.query(func.count(TarefaCronograma.id))
                        .filter_by(obra_id=obra.id, admin_id=admin_id,
                                   is_cliente=False)
                        .scalar())
    if n_tarefas_depois < n_tarefas_antes:
        raise AssertionError(
            f'aplicar_versao deletou tarefas ({n_tarefas_antes} → '
            f'{n_tarefas_depois}) — proibido')

    # Snapshot do estado novo, com predecessoras tipadas do normalizado.
    preds_tipadas = {
        t.id: [{'tarefa_id': id_por_chave.get(p['chave']),
                'uid': novos.get(p['chave'], {}).get('uid'),
                'tipo': p['tipo'], 'lag_dias': p['lag_dias']}
               for p in novos[chave].get('predecessoras') or []]
        for chave, t in aplicadas.items()
    }
    _snapshot_versao(nova_versao, list(aplicadas.values()), admin_id,
                     preds_tipadas)

    imp.status = 'aplicado'
    imp.aplicado_em = agora

    niveis = Counter(m['nivel_match'] for m in rel['mapeamentos'])
    db.session.add(CronogramaImportacaoEvento(
        importacao_id=imp.id,
        admin_id=admin_id,
        evento='aplicado',
        detalhes={
            'versao_id': nova_versao.id,
            'versao_numero': nova_versao.numero,
            'resumo': rel['resumo'],
            'matching_por_nivel': dict(sorted(niveis.items())),
            'decisoes_manuais': len(decisoes),
            'antes': {'n_tarefas_vivas': len(vivas)},
            'depois': {'n_tarefas_vivas': len(aplicadas),
                       'arquivadas': len(arquivar),
                       'inseridas': len(inserir)},
        },
        usuario_id=usuario_id,
    ))
    return nova_versao, obra.id, admin_id, tem_rdo


# ---------------------------------------------------------------------------
# Restauração de versão (rollback por snapshot) — M05 Task 3
# ---------------------------------------------------------------------------

def restaurar_versao(versao_id: int, usuario_id: int | None) -> CronogramaVersao:
    """Restaura o cronograma da obra ao estado fotografado em `versao_id`.

    Reconstrói a partir de CronogramaTarefaSnapshot: tarefas vivas casadas
    por `tarefa_id` recebem UPDATE, arquivadas voltam (`ativa=True`),
    tarefas criadas depois da versão alvo são arquivadas — NUNCA DELETE.
    Vira uma NOVA versão ativa (`observacao='rollback da vN'`); a versão
    alvo permanece 'arquivada' e imutável. Mesma política pós-commit do
    aplicar: motor só roda se a obra tem RDO.
    """
    try:
        versao, obra_id, admin_id, tem_rdo = _restaurar(versao_id, usuario_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if tem_rdo:
        if not recalcular_cronograma(obra_id, admin_id, cliente=False):
            logger.warning('recalcular_cronograma falhou após restaurar '
                           'versão %s da obra %s', versao.numero, obra_id)
        sincronizar_percentuais_obra(obra_id, admin_id, cliente=False)
    return versao


def _restaurar(versao_id, usuario_id):
    alvo = db.session.get(CronogramaVersao, versao_id)
    if alvo is None:
        raise EstadoInvalido(f'Versão {versao_id} não encontrada.')
    admin_id = alvo.admin_id

    obra = (db.session.query(Obra)
            .filter_by(id=alvo.obra_id, admin_id=admin_id)
            .with_for_update().first())
    if obra is None:
        raise EstadoInvalido('Obra da versão não encontrada.')
    db.session.refresh(alvo)
    if alvo.status == 'ativa':
        raise EstadoInvalido(
            f'Versão {alvo.numero} já é a versão ativa — nada a restaurar.')

    snaps = (CronogramaTarefaSnapshot.query
             .filter_by(versao_id=alvo.id)
             .order_by(CronogramaTarefaSnapshot.ordem,
                       CronogramaTarefaSnapshot.id)
             .all())
    if not snaps:
        raise EstadoInvalido(
            f'Versão {alvo.numero} não tem snapshot — não é restaurável.')

    todas = (TarefaCronograma.query
             .filter_by(obra_id=obra.id, admin_id=admin_id, is_cliente=False)
             .all())
    por_id = {t.id: t for t in todas}
    vivas_antes = [t for t in todas if t.ativa]
    n_tarefas_antes = len(todas)

    # Fotografa a versão ativa corrente antes de mexer (se ainda sem foto).
    versao_atual = (CronogramaVersao.query
                    .filter_by(obra_id=obra.id, status='ativa')
                    .first())
    if versao_atual is not None:
        tem_snapshot = (db.session.query(CronogramaTarefaSnapshot.id)
                        .filter_by(versao_id=versao_atual.id)
                        .first() is not None)
        if not tem_snapshot and vivas_antes:
            _snapshot_versao(versao_atual, vivas_antes, admin_id)

    maior = (db.session.query(func.max(CronogramaVersao.numero))
             .filter_by(obra_id=obra.id).scalar()) or 0
    if versao_atual is not None:
        versao_atual.status = 'arquivada'
        db.session.flush()
    nova_versao = CronogramaVersao(
        obra_id=obra.id,
        admin_id=admin_id,
        numero=maior + 1,
        status='ativa',
        importacao_id=alvo.importacao_id,
        aplicada_em=datetime.utcnow(),
        aplicada_por_id=usuario_id,
        observacao=f'rollback da v{alvo.numero}',
    )
    db.session.add(nova_versao)
    db.session.flush()

    # 1ª passada: conteúdo. UPDATE nas casadas por tarefa_id (reativando
    # arquivadas); INSERT quando a tarefa da foto não existe mais no banco
    # (tarefa_id NULL — só possível em dados legados; nunca deletamos).
    restauradas = {}      # snap.id → TarefaCronograma
    for s in snaps:
        t = por_id.get(s.tarefa_id)
        extra = s.payload_extra or {}
        if t is None:
            t = TarefaCronograma(
                obra_id=obra.id,
                admin_id=admin_id,
                is_cliente=False,
                nome_tarefa=s.nome_tarefa or '(sem nome)',
                ordem=s.ordem or 0,
                duracao_dias=s.duracao_dias if s.duracao_dias is not None else 1,
                percentual_concluido=s.percentual_concluido_no_momento or 0.0,
                versao_criacao_id=nova_versao.id,
            )
            db.session.add(t)
        else:
            t.nome_tarefa = s.nome_tarefa or t.nome_tarefa
            t.ordem = s.ordem if s.ordem is not None else t.ordem
            if s.duracao_dias is not None:
                t.duracao_dias = s.duracao_dias
            if s.percentual_concluido_no_momento is not None:
                t.percentual_concluido = s.percentual_concluido_no_momento
        t.data_inicio = s.data_inicio
        t.data_fim = s.data_fim
        t.quantidade_total = s.quantidade_total
        t.unidade_medida = s.unidade_medida
        t.is_marco = bool(s.is_marco)
        t.mpp_uid = s.mpp_uid
        t.wbs_codigo = s.wbs_codigo
        if 'fingerprint' in extra:
            t.fingerprint = extra['fingerprint']
        t.ativa = True
        t.arquivada_em = None
        restauradas[s.id] = t
    db.session.flush()

    # 2ª passada: hierarquia (self-FK entre snapshots) e predecessora única
    # (primeira FS da lista tipada; ids da foto ainda existem — anti-DELETE).
    for s in snaps:
        t = restauradas[s.id]
        if s.tarefa_pai_snapshot_id and s.tarefa_pai_snapshot_id in restauradas:
            t.tarefa_pai_id = restauradas[s.tarefa_pai_snapshot_id].id
        else:
            t.tarefa_pai_id = None
        pred_id = None
        for p in s.predecessoras_json or []:
            if p.get('tipo') == 'FS' and p.get('tarefa_id') in por_id:
                pred_id = p['tarefa_id']
                break
        t.predecessora_id = pred_id

    # Tarefas fora da foto (criadas depois da versão alvo) são arquivadas.
    agora = datetime.utcnow()
    ids_restaurados = {t.id for t in restauradas.values()}
    arquivadas = 0
    for t in todas:
        if t.id not in ids_restaurados and t.ativa:
            t.ativa = False
            t.arquivada_em = agora
            arquivadas += 1
    db.session.flush()

    n_tarefas_depois = (db.session.query(func.count(TarefaCronograma.id))
                        .filter_by(obra_id=obra.id, admin_id=admin_id,
                                   is_cliente=False)
                        .scalar())
    if n_tarefas_depois < n_tarefas_antes:
        raise AssertionError(
            f'restaurar_versao deletou tarefas ({n_tarefas_antes} → '
            f'{n_tarefas_depois}) — proibido')

    # Foto da nova versão preservando as predecessoras tipadas da alvo.
    preds_tipadas = {restauradas[s.id].id: list(s.predecessoras_json or [])
                     for s in snaps}
    _snapshot_versao(nova_versao, list(restauradas.values()), admin_id,
                     preds_tipadas)

    # Trilha de auditoria: evento exige importacao_id — usa o da versão
    # alvo ou o da versão que estava ativa; sem nenhum (backfill puro),
    # não há importação para auditar e o evento é omitido.
    imp_id = alvo.importacao_id or (
        versao_atual.importacao_id if versao_atual is not None else None)
    if imp_id is not None:
        db.session.add(CronogramaImportacaoEvento(
            importacao_id=imp_id,
            admin_id=admin_id,
            evento='rollback',
            detalhes={
                'versao_alvo_id': alvo.id,
                'versao_alvo_numero': alvo.numero,
                'versao_nova_id': nova_versao.id,
                'versao_nova_numero': nova_versao.numero,
                'restauradas': len(restauradas),
                'arquivadas': arquivadas,
            },
            usuario_id=usuario_id,
        ))

    tem_rdo = (db.session.query(RDO.id)
               .filter_by(obra_id=obra.id).first() is not None)
    return nova_versao, obra.id, admin_id, tem_rdo
