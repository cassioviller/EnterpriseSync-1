"""
Engine de alertas para Entregas / Terceiros.

Avalia tarefas de cronograma com responsavel='terceiros' (entregas, subempreitadas)
e produz mensagens contextuais por urgencia para o Painel Estrategico da Obra.
"""
from datetime import date, timedelta
import logging

from app import db
from models import TarefaCronograma
from sqlalchemy import exists, and_, not_

logger = logging.getLogger(__name__)


NIVEIS = {
    'verde':     {'ordem': 90, 'bg': '#dcfce7', 'border': '#22c55e', 'text': '#166534', 'icon': 'fa-check-circle'},
    'azul':      {'ordem': 60, 'bg': '#dbeafe', 'border': '#3b82f6', 'text': '#1e40af', 'icon': 'fa-info-circle'},
    'cinza':     {'ordem': 99, 'bg': '#f1f5f9', 'border': '#94a3b8', 'text': '#475569', 'icon': 'fa-minus-circle'},
    'amarelo':   {'ordem': 30, 'bg': '#fef3c7', 'border': '#f59e0b', 'text': '#92400e', 'icon': 'fa-exclamation-circle'},
    'laranja':   {'ordem': 20, 'bg': '#ffedd5', 'border': '#f97316', 'text': '#9a3412', 'icon': 'fa-fire'},
    'vermelho':  {'ordem': 10, 'bg': '#fee2e2', 'border': '#ef4444', 'text': '#991b1b', 'icon': 'fa-exclamation-triangle'},
    'sem_dados': {'ordem': 100, 'bg': '#f1f5f9', 'border': '#94a3b8', 'text': '#64748b', 'icon': 'fa-minus-circle'},
}


def _format_data(d):
    return d.strftime('%d/%m/%Y') if d else '—'


def _classificar_tarefa(tarefa, hoje=None):
    """
    Aplica regras temporais e retorna dict com:
        nivel, mensagem, ordem_urgencia, dias_para_inicio, dias_para_fim
    """
    if hoje is None:
        hoje = date.today()

    di = tarefa.data_inicio
    df = tarefa.data_fim
    dr = tarefa.data_entrega_real
    pct = float(tarefa.percentual_concluido or 0)
    entregue = (dr is not None) or (pct >= 100)

    dias_inicio = (di - hoje).days if di else None
    dias_fim = (df - hoje).days if df else None

    # 1) Entregue (verde)
    if entregue:
        msg = f"Entregue em {_format_data(dr)}" if dr else f"Concluído (100%)"
        if df and dr and dr > df:
            msg = f"Entregue em {_format_data(dr)} (com atraso, prazo era {_format_data(df)})"
        return {
            'nivel': 'verde',
            'mensagem': msg,
            'ordem_urgencia': NIVEIS['verde']['ordem'],
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': dias_fim,
        }

    # 2) Sem prazo definido
    if not df:
        return {
            'nivel': 'cinza',
            'mensagem': "Sem prazo definido",
            'ordem_urgencia': NIVEIS['cinza']['ordem'],
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': None,
        }

    # 3) Atrasada (vermelho)
    if dias_fim < 0:
        return {
            'nivel': 'vermelho',
            'mensagem': f"ATRASADA há {abs(dias_fim)} dia(s) — prazo era {_format_data(df)}",
            'ordem_urgencia': NIVEIS['vermelho']['ordem'] - min(abs(dias_fim), 9),
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': dias_fim,
        }

    # 4) Vence HOJE (laranja)
    if dias_fim == 0:
        return {
            'nivel': 'laranja',
            'mensagem': f"VENCE HOJE — confirmar entrega imediata ({pct:.0f}% executado)",
            'ordem_urgencia': NIVEIS['laranja']['ordem'],
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': 0,
        }

    # 5) Vence amanhã (amarelo) - urgência de VENCIMENTO
    if dias_fim == 1:
        return {
            'nivel': 'amarelo',
            'motivo': 'vence_amanha',
            'mensagem': f"Vence AMANHÃ ({_format_data(df)}) — confirmar conclusão",
            'ordem_urgencia': NIVEIS['amarelo']['ordem'],
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': 1,
        }

    # 6) Início amanhã (amarelo no item, mas NÃO conta como urgência de vencimento no painel)
    if di and dias_inicio == 1:
        return {
            'nivel': 'amarelo',
            'motivo': 'inicio_amanha',
            'mensagem': f"Início AMANHÃ ({_format_data(di)}) — confirmar com fornecedor",
            'ordem_urgencia': NIVEIS['amarelo']['ordem'] + 1,
            'dias_para_inicio': 1,
            'dias_para_fim': dias_fim,
        }

    # 7) Em execução, dentro da janela (azul)
    if di and dias_inicio <= 0 <= dias_fim:
        return {
            'nivel': 'azul',
            'mensagem': f"Em execução ({pct:.0f}%) — entrega prevista em {dias_fim} dia(s) ({_format_data(df)})",
            'ordem_urgencia': NIVEIS['azul']['ordem'] - min(dias_fim, 30),
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': dias_fim,
        }

    # 8) Pré-pedido / janela de 7 dias antes do início (azul)
    if di and 0 < dias_inicio <= 7:
        return {
            'nivel': 'azul',
            'mensagem': f"Pedido feito? — início em {dias_inicio} dia(s) ({_format_data(di)})",
            'ordem_urgencia': NIVEIS['azul']['ordem'] - (8 - dias_inicio),
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': dias_fim,
        }

    # 9) Aguardando início mais distante (cinza)
    if di and dias_inicio > 7:
        return {
            'nivel': 'cinza',
            'mensagem': f"Aguardando início em {dias_inicio} dia(s) ({_format_data(di)})",
            'ordem_urgencia': NIVEIS['cinza']['ordem'] - 1,
            'dias_para_inicio': dias_inicio,
            'dias_para_fim': dias_fim,
        }

    # 10) Sem data_inicio mas com prazo futuro
    return {
        'nivel': 'azul',
        'mensagem': f"Prazo em {dias_fim} dia(s) ({_format_data(df)}) — {pct:.0f}% executado",
        'ordem_urgencia': NIVEIS['azul']['ordem'],
        'dias_para_inicio': dias_inicio,
        'dias_para_fim': dias_fim,
    }


def listar_tarefas_terceiros(obra_id, admin_id=None):
    """
    Retorna apenas tarefas-folha (sem filhas) com responsavel='terceiros'.
    Defesa em profundidade multi-tenant: se admin_id for informado,
    filtra também por admin_id (além do escopo natural por obra_id).
    """
    TarefaFilha = db.aliased(TarefaCronograma)
    subq_tem_filha = exists().where(and_(
        TarefaFilha.tarefa_pai_id == TarefaCronograma.id,
        TarefaFilha.obra_id == obra_id,
    ))
    q = TarefaCronograma.query.filter(
        TarefaCronograma.obra_id == obra_id,
        TarefaCronograma.responsavel == 'terceiros',
        not_(subq_tem_filha),
    )
    if admin_id is not None:
        q = q.filter(TarefaCronograma.admin_id == admin_id)
    return q.order_by(TarefaCronograma.data_fim.asc().nulls_last(),
                      TarefaCronograma.ordem.asc()).all()


def listar_tarefas_terceiros_pendentes(obra_id, admin_id=None):
    """Tarefas terceiros ainda nao entregues (para dropdown no RDO)."""
    todas = listar_tarefas_terceiros(obra_id, admin_id=admin_id)
    return [t for t in todas if t.data_entrega_real is None and float(t.percentual_concluido or 0) < 100]


def calcular_alertas_terceiros(obra_id, hoje=None, admin_id=None):
    """
    Retorna dict:
        {
            'detalhe': [ {tarefa, nivel, mensagem, ...}, ... ] ordenado por urgencia,
            'painel':  {status, label, qtd_total, qtd_atrasadas, qtd_vence_hoje,
                        qtd_amanha, qtd_pendentes, qtd_entregues}
        }
    """
    if hoje is None:
        hoje = date.today()

    tarefas = listar_tarefas_terceiros(obra_id, admin_id=admin_id)
    detalhe = []
    qtd_atrasadas = 0
    qtd_vence_hoje = 0
    qtd_amanha = 0
    qtd_pendentes = 0
    qtd_entregues = 0

    for t in tarefas:
        cls = _classificar_tarefa(t, hoje=hoje)
        item = {
            'tarefa': t,
            'id': t.id,
            'nome': t.nome_tarefa,
            'data_inicio': t.data_inicio,
            'data_fim': t.data_fim,
            'data_entrega_real': t.data_entrega_real,
            'percentual': float(t.percentual_concluido or 0),
            'entregue': (t.data_entrega_real is not None) or (float(t.percentual_concluido or 0) >= 100),
            **cls,
        }
        detalhe.append(item)

        if item['entregue']:
            qtd_entregues += 1
        else:
            qtd_pendentes += 1
            if cls['nivel'] == 'vermelho':
                qtd_atrasadas += 1
            elif cls['nivel'] == 'laranja':
                qtd_vence_hoje += 1
            elif cls['nivel'] == 'amarelo' and cls.get('motivo') == 'vence_amanha':
                # Painel: amarelo SO conta itens cujo motivo é vencimento amanhã.
                # "Início amanhã" segue amarelo no detalhe do item (urgência operacional)
                # mas NÃO escala o painel — não há vencimento crítico ainda.
                qtd_amanha += 1

    detalhe.sort(key=lambda d: d['ordem_urgencia'])

    qtd_total = len(tarefas)
    if qtd_total == 0:
        painel = {
            'status': 'sem_dados',
            'label': 'Sem entregas/terceiros',
            'qtd_total': 0, 'qtd_atrasadas': 0, 'qtd_vence_hoje': 0,
            'qtd_amanha': 0, 'qtd_pendentes': 0, 'qtd_entregues': 0,
        }
    elif qtd_atrasadas > 0:
        painel = {
            'status': 'vermelho',
            'label': f'{qtd_atrasadas} entrega(s) atrasada(s)',
            'qtd_total': qtd_total, 'qtd_atrasadas': qtd_atrasadas,
            'qtd_vence_hoje': qtd_vence_hoje, 'qtd_amanha': qtd_amanha,
            'qtd_pendentes': qtd_pendentes, 'qtd_entregues': qtd_entregues,
        }
    elif qtd_vence_hoje > 0 or qtd_amanha > 0:
        # Spec: "vence hoje" + "vence amanhã" sem confirmação => amarelo no painel.
        # (No detalhe item, "vence hoje" segue laranja como urgência individual.)
        if qtd_vence_hoje > 0 and qtd_amanha > 0:
            label = f'{qtd_vence_hoje} entrega(s) vencendo HOJE e {qtd_amanha} amanhã'
        elif qtd_vence_hoje > 0:
            label = f'{qtd_vence_hoje} entrega(s) vencendo HOJE'
        else:
            label = f'{qtd_amanha} entrega(s) para amanhã'
        painel = {
            'status': 'amarelo',
            'label': label,
            'qtd_total': qtd_total, 'qtd_atrasadas': 0,
            'qtd_vence_hoje': qtd_vence_hoje, 'qtd_amanha': qtd_amanha,
            'qtd_pendentes': qtd_pendentes, 'qtd_entregues': qtd_entregues,
        }
    elif qtd_pendentes > 0:
        painel = {
            'status': 'verde',
            'label': f'{qtd_entregues}/{qtd_total} entregue(s) — sem urgência',
            'qtd_total': qtd_total, 'qtd_atrasadas': 0, 'qtd_vence_hoje': 0,
            'qtd_amanha': 0,
            'qtd_pendentes': qtd_pendentes, 'qtd_entregues': qtd_entregues,
        }
    else:
        painel = {
            'status': 'verde',
            'label': f'Todas as {qtd_total} entregas concluídas',
            'qtd_total': qtd_total, 'qtd_atrasadas': 0, 'qtd_vence_hoje': 0,
            'qtd_amanha': 0, 'qtd_pendentes': 0, 'qtd_entregues': qtd_entregues,
        }

    return {'detalhe': detalhe, 'painel': painel}


def aplicar_entregas_no_rdo(rdo, form_data, admin_id=None):
    """
    Processa form.getlist('entrega_tarefa_ids[]') marcando as tarefas terceiros
    como entregues (data_entrega_real = rdo.data_relatorio, percentual=100).

    Task #149 — quando o front também envia `terceiros_tarefa_ids_lista[]`
    (lista das tarefas terceiros mostradas inline na lista do cronograma),
    as tarefas presentes na lista mas NÃO marcadas em
    `entrega_tarefa_ids[]` são revertidas para pendente (percentual=0,
    data_entrega_real=None) — permitindo o toggle Concluído/Pendente.

    Retorna tupla (qtd_marcadas, qtd_revertidas). NAO faz commit (chamador commita).
    """
    try:
        def _getlist(name):
            if hasattr(form_data, 'getlist'):
                return form_data.getlist(f'{name}[]') or form_data.getlist(name)
            v = form_data.get(f'{name}[]') or form_data.get(name) or []
            return v if isinstance(v, list) else [v]

        ids_raw = _getlist('entrega_tarefa_ids')
        lista_raw = _getlist('terceiros_tarefa_ids_lista')

        def _to_int_set(seq):
            out = set()
            for raw in seq:
                try:
                    out.add(int(raw))
                except (TypeError, ValueError):
                    continue
            return out

        marcados = _to_int_set(ids_raw)
        visiveis = _to_int_set(lista_raw)

        data_ref = rdo.data_relatorio if rdo and rdo.data_relatorio else date.today()
        qtd = 0
        for tid in marcados:
            q = TarefaCronograma.query.filter_by(id=tid)
            if admin_id is not None:
                q = q.filter_by(admin_id=admin_id)
            t = q.first()
            if not t or (t.responsavel or '').lower() != 'terceiros':
                continue
            if t.obra_id != rdo.obra_id:
                continue
            t.percentual_concluido = 100.0
            t.data_entrega_real = data_ref
            qtd += 1

        # Toggle reverso: tarefas listadas na UI mas não marcadas → pendente
        para_desmarcar = visiveis - marcados
        qtd_revertidas = 0
        for tid in para_desmarcar:
            q = TarefaCronograma.query.filter_by(id=tid)
            if admin_id is not None:
                q = q.filter_by(admin_id=admin_id)
            t = q.first()
            if not t or (t.responsavel or '').lower() != 'terceiros':
                continue
            if t.obra_id != rdo.obra_id:
                continue
            mudou = (float(t.percentual_concluido or 0) != 0.0) or (t.data_entrega_real is not None)
            t.percentual_concluido = 0.0
            t.data_entrega_real = None
            if mudou:
                qtd_revertidas += 1
        return (qtd, qtd_revertidas)
    except Exception as e:
        logger.error(f"Erro aplicar_entregas_no_rdo: {e}")
        return (0, 0)
