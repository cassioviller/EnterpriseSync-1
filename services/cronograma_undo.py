"""Pilha de desfazer/refazer do editor de cronograma (Fase 3).

Spec: `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md` §6.
Plano: `docs/superpowers/plans/2026-07-24-cronograma-fase3-plano.md`.

Como funciona
-------------
Cada ação do usuário na grade é capturada por comparação de dois snapshots
da obra (antes e depois da rota rodar). O diff é feito **por campo**: o
payload guarda só o que aquela ação mudou, nunca a linha inteira.

Isso é a decisão central do módulo. Com payload de linha inteira, esta
sequência destruiria dado real: o usuário renomeia uma tarefa (o snapshot
grava `percentual_concluido=40` junto) → um RDO aponta progresso (`60`) →
o usuário dá Ctrl+Z → o desfazer restauraria `40`, apagando progresso
apurado que não fazia parte da ação desfeita. Com diff por campo, desfazer
um rename escreve `nome_tarefa` e mais nada.

A cascata de datas do motor entra no payload normalmente, porque ela de
fato mudou naquela ação — que é o que o spec pede ("payloads guardam o
estado de todas as tarefas e vínculos afetados, incluindo as datas
alteradas pela cascata do recálculo").

Identidade
----------
* **Tarefas** — por `id`. Com a flag ligada a exclusão é lógica
  (`ativa=False`), então criar/excluir viram mutação de campo e nenhum id
  precisa ser recriado: apontamentos de RDO e itens de medição continuam
  apontando para a linha certa.
* **Vínculos** — pelo par natural `(predecessora_id, sucessora_id)`, que já
  é UNIQUE. Vínculo é hard delete mesmo; recriá-lo com id novo é seguro
  porque nada referencia `tarefa_vinculo.id`. Assim o desfazer nunca força
  PK nem mexe em sequence do Postgres.

Invariante da pilha
-------------------
Toda ação nova apaga as `desfeita=True` do escopo (ação nova descarta o
refazer pendente), então a pilha é sempre um bloco de `desfeita=False`
embaixo e um bloco de `desfeita=True` em cima. Desfazer e refazer são, por
isso, as duas pontas de um `ORDER BY id`. Escopo = (obra, usuário, modo).
"""
import logging
from datetime import date, datetime

from models import db, CronogramaAcao, TarefaCronograma, TarefaVinculo

logger = logging.getLogger(__name__)

# Campos de tarefa versionados pela pilha. Fora daqui ficam de propósito:
# id/obra_id/admin_id/is_cliente (identidade), created_at e os campos de
# proposta/versão (linhagem, não são editáveis pela grade).
CAMPOS_TAREFA = (
    'tarefa_pai_id', 'predecessora_id', 'ordem', 'nome_tarefa',
    'duracao_dias', 'data_inicio', 'data_fim', 'quantidade_total',
    'unidade_medida', 'responsavel', 'percentual_concluido',
    'modo_apontamento', 'subatividade_mestre_id', 'servico_id',
    'is_critica', 'folga_dias', 'ativa', 'arquivada_em',
)
CAMPOS_VINCULO = ('tipo', 'lag_dias')

LIMITE_PILHA = 50

MSG_NADA_DESFAZER = 'Não há nada para desfazer'
MSG_NADA_REFAZER = 'Não há nada para refazer'


# ─────────────────────────────────────────────────────────────────────────────
# Serialização
# ─────────────────────────────────────────────────────────────────────────────

def _serializar(valor):
    """Datas viram ISO para caber em JSON; o resto passa direto."""
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _desserializar(campo: str, valor):
    """Inverso de `_serializar`, guiado pelo tipo declarado da coluna."""
    if valor is None:
        return None
    if campo in ('data_inicio', 'data_fim'):
        return date.fromisoformat(valor) if isinstance(valor, str) else valor
    if campo == 'arquivada_em':
        return datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    return valor


def snapshot_obra(obra_id: int, admin_id: int, cliente: bool = False) -> dict:
    """Estado versionável da obra em DUAS queries.

    As tarefas vêm SEM filtro de `ativa` — o snapshot precisa enxergar o
    arquivamento (é assim que criar/excluir aparecem como mutação de campo).
    """
    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente)
        .all()
    )
    vinculos = (
        TarefaVinculo.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .all()
    )
    return {
        'tarefas': {
            str(t.id): {c: _serializar(getattr(t, c)) for c in CAMPOS_TAREFA}
            for t in tarefas
        },
        'vinculos': {
            f'{v.predecessora_id}-{v.sucessora_id}':
                {c: getattr(v, c) for c in CAMPOS_VINCULO}
            for v in vinculos
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Diff
# ─────────────────────────────────────────────────────────────────────────────

def diff_snapshots(antes: dict, depois: dict):
    """Diff por campo entre dois snapshots.

    Devolve `(payload_antes, payload_depois)`, ou `(None, None)` quando nada
    mudou — é esse `None` que faz uma rota que devolveu 400/404 (e portanto
    fez rollback) não sujar a pilha, sem nenhum tratamento por rota.
    """
    t_antes, t_depois = {}, {}
    tarefas_a, tarefas_d = antes['tarefas'], depois['tarefas']

    for tid, campos_d in tarefas_d.items():
        campos_a = tarefas_a.get(tid)
        if campos_a is None:
            # Tarefa criada nesta ação: desfazer = arquivar, refazer =
            # reativar. Os demais campos ficam intactos na linha, então
            # basta o par `ativa`.
            t_antes[tid] = {'ativa': False}
            t_depois[tid] = {'ativa': True}
            continue
        mudou_a = {c: campos_a[c] for c in CAMPOS_TAREFA if campos_a[c] != campos_d[c]}
        if mudou_a:
            t_antes[tid] = mudou_a
            t_depois[tid] = {c: campos_d[c] for c in mudou_a}

    for tid in tarefas_a:
        if tid not in tarefas_d:
            # Hard delete de tarefa: não é desfazível (o id não pode
            # ressuscitar sem quebrar apontamentos). Com a flag ligada a
            # exclusão é lógica, então isto não deve acontecer.
            logger.warning('[undo] tarefa %s sumiu da obra durante a ação '
                           '(hard delete) — não é desfazível', tid)

    v_antes, v_depois = {}, {}
    vinc_a, vinc_d = antes['vinculos'], depois['vinculos']
    for chave in set(vinc_a) | set(vinc_d):
        va, vd = vinc_a.get(chave), vinc_d.get(chave)
        if va != vd:
            v_antes[chave] = va      # None = "não deve existir"
            v_depois[chave] = vd

    if not (t_antes or v_antes):
        return None, None
    return ({'tarefas': t_antes, 'vinculos': v_antes},
            {'tarefas': t_depois, 'vinculos': v_depois})


# ─────────────────────────────────────────────────────────────────────────────
# Aplicação
# ─────────────────────────────────────────────────────────────────────────────

def aplicar_payload(obra_id: int, admin_id: int, cliente: bool,
                    payload: dict) -> list:
    """Escreve um payload e commita. Devolve as tarefas tocadas.

    NÃO chama `recalcular_obra`: o payload já carrega as datas pós-cascata
    daquela ação, e re-agendar poderia divergir do estado que está sendo
    restaurado.
    """
    afetadas = []
    for tid, campos in (payload.get('tarefas') or {}).items():
        tarefa = TarefaCronograma.query.filter_by(
            id=int(tid), obra_id=obra_id, admin_id=admin_id, is_cliente=cliente
        ).first()
        if tarefa is None:
            logger.warning('[undo] tarefa %s do payload não existe mais na '
                           'obra %s — item pulado', tid, obra_id)
            continue
        for campo, valor in campos.items():
            if campo in CAMPOS_TAREFA:
                setattr(tarefa, campo, _desserializar(campo, valor))
        afetadas.append(tarefa)

    for chave, dados in (payload.get('vinculos') or {}).items():
        try:
            pred_id, suc_id = (int(p) for p in chave.split('-'))
        except (ValueError, AttributeError):
            logger.warning('[undo] chave de vínculo inválida no payload: %r', chave)
            continue
        vinculo = TarefaVinculo.query.filter_by(
            obra_id=obra_id, admin_id=admin_id,
            predecessora_id=pred_id, sucessora_id=suc_id,
        ).first()
        if dados is None:
            if vinculo is not None:
                db.session.delete(vinculo)
        elif vinculo is not None:
            for campo in CAMPOS_VINCULO:
                setattr(vinculo, campo, dados.get(campo))
        else:
            db.session.add(TarefaVinculo(
                admin_id=admin_id, obra_id=obra_id,
                predecessora_id=pred_id, sucessora_id=suc_id,
                **{c: dados.get(c) for c in CAMPOS_VINCULO}))

    db.session.commit()
    return afetadas


# ─────────────────────────────────────────────────────────────────────────────
# Pilha
# ─────────────────────────────────────────────────────────────────────────────

def _pilha(obra_id: int, usuario_id: int, cliente: bool):
    return CronogramaAcao.query.filter_by(
        obra_id=obra_id, usuario_id=usuario_id, is_cliente=cliente)


def registrar_acao(obra_id: int, admin_id: int, usuario_id: int, cliente: bool,
                   tipo_acao: str, antes: dict) -> CronogramaAcao | None:
    """Fecha o par snapshot-antes/agora e empilha a ação, se houve mudança.

    Devolve a ação gravada, ou None quando a rota não mudou nada (erro
    validado, no-op) — nesse caso a pilha fica intocada.
    """
    depois = snapshot_obra(obra_id, admin_id, cliente)
    payload_antes, payload_depois = diff_snapshots(antes, depois)
    if payload_antes is None:
        return None

    # Ação nova descarta o refazer pendente (spec §6) — é o que mantém a
    # invariante "desfeitas sempre no topo" de que desfazer/refazer dependem.
    _pilha(obra_id, usuario_id, cliente).filter_by(desfeita=True).delete(
        synchronize_session=False)

    acao = CronogramaAcao(
        obra_id=obra_id, admin_id=admin_id, usuario_id=usuario_id,
        is_cliente=cliente, tipo_acao=tipo_acao[:32],
        payload_antes=payload_antes, payload_depois=payload_depois,
        desfeita=False,
    )
    db.session.add(acao)
    db.session.flush()

    excedentes = (
        _pilha(obra_id, usuario_id, cliente)
        .order_by(CronogramaAcao.id.desc())
        .offset(LIMITE_PILHA).all()
    )
    for velha in excedentes:
        db.session.delete(velha)
    db.session.commit()
    return acao


def desfazer(obra_id: int, admin_id: int, usuario_id: int, cliente: bool):
    """Aplica o `payload_antes` da ação mais recente ainda não desfeita.

    Devolve `(acao, afetadas)`, ou `(None, [])` com a pilha vazia.
    """
    acao = (_pilha(obra_id, usuario_id, cliente).filter_by(desfeita=False)
            .order_by(CronogramaAcao.id.desc()).first())
    if acao is None:
        return None, []
    afetadas = aplicar_payload(obra_id, admin_id, cliente, acao.payload_antes)
    acao.desfeita = True
    db.session.commit()
    return acao, afetadas


def refazer(obra_id: int, admin_id: int, usuario_id: int, cliente: bool):
    """Aplica o `payload_depois` da ação desfeita mais antiga (o topo da
    pilha de refazer). Devolve `(acao, afetadas)` ou `(None, [])`."""
    acao = (_pilha(obra_id, usuario_id, cliente).filter_by(desfeita=True)
            .order_by(CronogramaAcao.id.asc()).first())
    if acao is None:
        return None, []
    afetadas = aplicar_payload(obra_id, admin_id, cliente, acao.payload_depois)
    acao.desfeita = False
    db.session.commit()
    return acao, afetadas


def estado_pilha(obra_id: int, usuario_id: int, cliente: bool) -> tuple:
    """`(pode_desfazer, pode_refazer)` — o que a toolbar precisa saber."""
    pilha = _pilha(obra_id, usuario_id, cliente)
    return (
        db.session.query(pilha.filter_by(desfeita=False).exists()).scalar(),
        db.session.query(pilha.filter_by(desfeita=True).exists()).scalar(),
    )
