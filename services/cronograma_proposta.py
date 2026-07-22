"""
Task #102 — Cronograma automático na aprovação da proposta.
Task #34  — Preview de cronograma diretamente na tela do orçamento.

Funções:
    - montar_arvore_preview(proposta, admin_id): monta a árvore consolidada
      Serviço → Grupo → Subatividade derivada do CronogramaTemplate vinculado a
      cada Serviço (Servico.template_padrao_id), com flag `marcado=True` por
      padrão. Opera sobre PropostaItem.
    - montar_arvore_preview_orcamento(orcamento, admin_id): mesma lógica de
      montar_arvore_preview, mas opera sobre OrcamentoItem — permite exibir o
      preview do cronograma diretamente na tela de edição do orçamento, antes
      de gerar a proposta. Respeita a precedência override > padrão do serviço
      (Task #118). Retorna estrutura idêntica, porém com chave
      `orcamento_item_id` em vez de `proposta_item_id`.
    - materializar_cronograma(proposta, admin_id, obra_id, arvore_marcada=None):
      cria TarefaCronograma (3 níveis) + ItemMedicaoCronogramaTarefa com peso
      por horas para cada nó marcado. Idempotente: nunca duplica para o mesmo
      proposta_item_id (chave gerada_por_proposta_item_id).
    - tem_conteudo_para_revisar(proposta, admin_id): True se ao menos um
      PropostaItem tem servico com template_padrao_id.

Decisões:
    - Peso é calculado por `duracao_estimada_horas` da SubatividadeMestre
      vinculada (fallback: divisão igual entre folhas marcadas).
    - PropostaItem/OrcamentoItem sem servico/template é exibido na árvore como
      `sem_template=True` e marcação default = False. Se o admin MARCAR o nó,
      ele materializa uma tarefa-esqueleto de nível 0 (sem filhos) com o
      quantitativo do próprio item — antes o nó era descartado em silêncio e a
      obra podia nascer sem nenhuma tarefa.
    - Atomicidade é responsabilidade do caller (handler) — funções operam
      via db.session sem commit explícito.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from app import db
from models import (
    CronogramaTemplate,
    ItemMedicaoComercial,
    ItemMedicaoCronogramaTarefa,
    PropostaItem,
    Servico,
    SubatividadeMestre,
    TarefaCronograma,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _expandir_template_para_arvore(template: CronogramaTemplate, admin_id: int) -> list[dict]:
    """Converte itens do template em árvore de nós {grupo|subatividade}.
    Cada nó traz: nome, tipo, subatividade_mestre_id, duracao_dias,
    horas_estimadas, quantidade_prevista, unidade_medida, marcado=True, filhos.
    """
    itens = list(template.itens)
    by_id: dict[int, dict] = {}
    for item in itens:
        sub = item.subatividade if item.subatividade and item.subatividade.admin_id == admin_id else None
        horas = float(sub.duracao_estimada_horas) if (sub and sub.duracao_estimada_horas) else 0.0
        by_id[item.id] = {
            'template_item_id': item.id,
            'tipo': (sub.tipo if sub and getattr(sub, 'tipo', None) else 'subatividade'),
            'nome': item.nome_tarefa,
            'subatividade_mestre_id': sub.id if sub else None,
            'duracao_dias': item.duracao_dias or 1,
            'horas_estimadas': horas,
            'quantidade_prevista': item.quantidade_prevista,
            'unidade_medida': sub.unidade_medida if sub else None,
            'responsavel': item.responsavel or 'empresa',
            'marcado': True,
            'parent_item_id': getattr(item, 'parent_item_id', None),
            'ordem': item.ordem or 0,
            'filhos': [],
        }
    raizes: list[dict] = []
    for node in by_id.values():
        pid = node['parent_item_id']
        if pid and pid in by_id:
            by_id[pid]['filhos'].append(node)
        else:
            raizes.append(node)

    def _ord(nodes: list[dict]) -> None:
        nodes.sort(key=lambda n: n['ordem'])
        for n in nodes:
            _ord(n['filhos'])
            if n['filhos']:
                n['tipo'] = 'grupo'

    _ord(raizes)
    return raizes


def _index_preconfig(preconfig: list[dict] | None) -> dict:
    """Indexa o snapshot `cronograma_default_json` por proposta_item_id e,
    dentro de cada item, por (subatividade_mestre_id, nome) para reaplicação
    de marcações/horas/dias quando o admin já pré-configurou."""
    if not preconfig:
        return {}
    out = {}
    for it in preconfig:
        pi = it.get('proposta_item_id')
        if pi is None:
            continue
        out[pi] = it
    return out


def _aplicar_overrides(no_default: dict, no_pre: dict | None) -> dict:
    """Mescla um nó default da árvore com os campos do snapshot pré-configurado
    (marcado, horas_estimadas, duracao_dias). Mantém demais campos do default."""
    if not no_pre:
        return no_default
    if 'marcado' in no_pre:
        no_default['marcado'] = bool(no_pre.get('marcado'))
    if no_pre.get('horas_estimadas') is not None:
        no_default['horas_estimadas'] = float(no_pre.get('horas_estimadas') or 0)
    if no_pre.get('duracao_dias') is not None:
        try:
            no_default['duracao_dias'] = int(no_pre.get('duracao_dias') or 1)
        except (TypeError, ValueError):
            pass
    # recursivo nos filhos casando por (subatividade_mestre_id, nome)
    filhos_default = no_default.get('filhos') or []
    filhos_pre = no_pre.get('filhos') or []
    if filhos_default and filhos_pre:
        # casamento por chave (subatividade_mestre_id, nome) — fallback ordem
        key = lambda n: (n.get('subatividade_mestre_id'), n.get('nome'))
        pre_idx = {key(n): n for n in filhos_pre}
        for i, fd in enumerate(filhos_default):
            fp = pre_idx.get(key(fd)) or (filhos_pre[i] if i < len(filhos_pre) else None)
            _aplicar_overrides(fd, fp)
    return no_default


def montar_arvore_preview(proposta, admin_id: int) -> list[dict]:
    """Monta a árvore consolidada Serviço→Grupo→Subatividade da proposta.

    Se `proposta.cronograma_default_json` estiver presente (admin já
    pré-configurou via "Salvar pré-configuração"), os campos `marcado`,
    `horas_estimadas` e `duracao_dias` do snapshot SÃO APLICADOS sobre a
    árvore default — assim a tela de revisão e o portal cliente reabrem
    fielmente a configuração salva.

    Estrutura retornada (lista, uma entrada por PropostaItem):
        [{
            'proposta_item_id': int,
            'servico_id': int | None,   # já filtrado por admin_id
            'servico_nome': str,
            'sem_template': bool,   # True quando não há template
            'horas_totais_estimadas': float,
            'marcado': bool,
            'filhos': [ ...nós do template... ]
        }, ...]

    Nós com `sem_template=True` trazem ainda `duracao_dias`,
    `quantidade_prevista`, `unidade_medida` e `responsavel`: sem filhos, a
    própria raiz é a tarefa, então ela carrega o quantitativo do PropostaItem.
    Se marcada, vira uma tarefa-esqueleto de nível 0 em
    `materializar_cronograma` — não é mais descartada.

    Fix #6: O filtro `CronogramaTemplate.ativo == True` foi removido desta
    função. O campo `ativo` controla a exibição do template nos seletores de
    NOVA proposta/orçamento, mas NÃO deve impedir que o template seja
    resolvido para itens de propostas existentes na tela de revisão inicial.
    Templates desativados continuam acessíveis para revisão de propostas que
    já os referenciam via Servico.template_padrao_id.
    """
    preconfig_idx = _index_preconfig(getattr(proposta, 'cronograma_default_json', None))
    itens = (
        PropostaItem.query
        .filter_by(proposta_id=proposta.id)
        .order_by(PropostaItem.ordem.asc(), PropostaItem.id.asc())
        .all()
    )
    if not itens:
        logger.debug(
            f"montar_arvore_preview: proposta={proposta.id} não tem PropostaItem — "
            "retornando árvore vazia"
        )
        return []

    # Cache servico → template (filtro de tenant obrigatório)
    serv_ids = {it.servico_id for it in itens if it.servico_id}
    servicos = {s.id: s for s in Servico.query.filter(
        Servico.id.in_(serv_ids), Servico.admin_id == admin_id
    ).all()} if serv_ids else {}

    # Diagnóstico: IDs de serviço ausentes no cache indicam possível admin_id incorreto.
    # Uso de set para deduplicar (um serviço pode aparecer em múltiplos itens).
    _sem_cache = sorted({it.servico_id for it in itens if it.servico_id and it.servico_id not in servicos})
    if _sem_cache:
        logger.debug(
            f"montar_arvore_preview: proposta={proposta.id} — "
            f"{len(_sem_cache)} servico_id(s) distintos não encontrados para admin_id={admin_id}: "
            f"{_sem_cache}. Itens correspondentes resultarão em sem_template=True."
        )

    # Task #118: precedência override → padrão. Coleta TODOS os IDs candidatos
    # (overrides por linha + padrões dos serviços) numa única query.
    # Fix #6: NÃO filtrar por ativo — templates desativados ainda devem ser
    # resolvidos para propostas existentes (ativo só filtra novos seletores).
    tmpl_ids = {s.template_padrao_id for s in servicos.values() if s.template_padrao_id}
    tmpl_ids |= {
        getattr(it, 'cronograma_template_override_id', None)
        for it in itens
        if getattr(it, 'cronograma_template_override_id', None)
    }
    templates = {t.id: t for t in CronogramaTemplate.query.filter(
        CronogramaTemplate.id.in_(tmpl_ids),
        CronogramaTemplate.admin_id == admin_id,
        # ativo NÃO é filtrado aqui: templates desativados permanecem acessíveis
        # para revisão de propostas que já os referenciam.
    ).all()} if tmpl_ids else {}

    logger.debug(
        f"montar_arvore_preview: proposta={proposta.id} admin={admin_id} — "
        f"{len(itens)} item(ns), {len(servicos)} serviço(s) em cache, "
        f"{len(tmpl_ids)} template_id(s) candidatos, {len(templates)} template(s) carregados"
    )

    arvore: list[dict] = []
    for it in itens:
        servico = servicos.get(it.servico_id) if it.servico_id else None
        # Task #118: override por linha tem precedência sobre o padrão do serviço.
        override_id = getattr(it, 'cronograma_template_override_id', None)
        template_efetivo_id = override_id or (servico.template_padrao_id if servico else None)
        tmpl = templates.get(template_efetivo_id) if template_efetivo_id else None
        origem_template = ('override' if override_id and tmpl else
                           ('padrao' if tmpl else None))

        # Log por item para facilitar diagnóstico em produção.
        if tmpl:
            logger.debug(
                f"  PI={it.id} servico_id={it.servico_id} "
                f"→ template={tmpl.id!r} ({tmpl.nome!r}) "
                f"origem={origem_template} ativo={tmpl.ativo}"
            )
        else:
            _reason = (
                'sem servico_id' if not it.servico_id else
                'servico não encontrado (admin_id mismatch?)' if not servico else
                'servico sem template_padrao_id e sem override' if not template_efetivo_id else
                f'template_id={template_efetivo_id} não carregado (admin_id mismatch ou deletado?)'
            )
            logger.debug(
                f"  PI={it.id} servico_id={it.servico_id} → sem_template=True ({_reason})"
            )

        nome_serv = (servico.nome if servico else (it.descricao or f'Item {it.item_numero or it.id}'))
        pre = preconfig_idx.get(it.id)
        if tmpl:
            filhos = _expandir_template_para_arvore(tmpl, admin_id)
            entrada = {
                'proposta_item_id': it.id,
                'servico_id': servico.id if servico else None,
                'servico_nome': nome_serv,
                'template_id': tmpl.id,
                'template_nome': tmpl.nome,
                'origem_template': origem_template,  # 'override' | 'padrao'
                'sem_template': False,
                'horas_totais_estimadas': 0.0,  # será recalculado após overrides
                'marcado': True,
                'filhos': filhos,
            }
            if pre:
                # Mescla overrides nas folhas/grupos e na raiz
                if 'marcado' in pre:
                    entrada['marcado'] = bool(pre.get('marcado'))
                pre_filhos = pre.get('filhos') or []
                if pre_filhos and filhos:
                    key = lambda n: (n.get('subatividade_mestre_id'), n.get('nome'))
                    pre_idx = {key(n): n for n in pre_filhos}
                    for i, fd in enumerate(filhos):
                        fp = pre_idx.get(key(fd)) or (pre_filhos[i] if i < len(pre_filhos) else None)
                        _aplicar_overrides(fd, fp)
            entrada['horas_totais_estimadas'] = _somar_horas_folhas(filhos)
            arvore.append(entrada)
        else:
            # Nó sem template: o único quantitativo disponível é o do próprio
            # PropostaItem. Damos corpo a ele (duração/quantidade/unidade) para
            # que, se o admin marcá-lo, `materializar_cronograma` consiga criar
            # uma tarefa-esqueleto apontável em vez de descartar o item.
            arvore.append({
                'proposta_item_id': it.id,
                # `servico.id`, não `it.servico_id`: `servicos` já passou pelo
                # filtro de admin_id (:181). Devolver o ID cru expunha um
                # serviço de OUTRO tenant quando o PropostaItem apontava para
                # fora do próprio.
                'servico_id': servico.id if servico else None,
                'servico_nome': nome_serv,
                'template_id': None,
                'template_nome': None,
                'origem_template': None,
                'sem_template': True,
                'duracao_dias': 1,
                # float(), não o Decimal cru: esta árvore é persistida em
                # `Proposta.cronograma_default_json` (coluna JSON) e Decimal
                # não é serializável — o ramo com template já usa Float (:76).
                'quantidade_prevista': float(it.quantidade) if it.quantidade is not None else None,
                'unidade_medida': it.unidade or (servico.unidade_medida if servico else None),
                'responsavel': 'empresa',
                'horas_totais_estimadas': 0.0,
                'marcado': bool(pre.get('marcado')) if pre else False,
                'filhos': [],
            })
    return arvore


def _somar_horas_folhas(nos: list[dict]) -> float:
    """Soma horas_estimadas considerando apenas folhas (subatividades)."""
    total = 0.0
    for n in nos:
        if n['filhos']:
            total += _somar_horas_folhas(n['filhos'])
        else:
            total += float(n.get('horas_estimadas') or 0)
    return total


def montar_arvore_preview_orcamento(orcamento, admin_id: int) -> list[dict]:
    """Task #34 — Monta a árvore Serviço→Grupo→Subatividade a partir do Orçamento.

    Opera sobre OrcamentoItem em vez de PropostaItem, permitindo exibir o preview
    do cronograma diretamente na tela de edição do orçamento, antes de gerar uma
    proposta. Mesma lógica de precedência override→padrão de montar_arvore_preview.

    Estrutura retornada (lista, uma entrada por OrcamentoItem):
        [{
            'orcamento_item_id': int,
            'servico_id': int | None,
            'servico_nome': str,
            'template_id': int | None,
            'template_nome': str | None,
            'origem_template': 'override' | 'padrao' | None,
            'sem_template': bool,
            'horas_totais_estimadas': float,
            'marcado': bool,
            'filhos': [ ...nós do template... ]
        }, ...]

    Como em `montar_arvore_preview`, nós `sem_template=True` trazem também
    `duracao_dias`/`quantidade_prevista`/`unidade_medida`/`responsavel`. Aqui
    são informativos: esta árvore é preview e nunca é materializada.
    """
    from models import OrcamentoItem

    itens = (
        OrcamentoItem.query
        .filter_by(orcamento_id=orcamento.id)
        .order_by(OrcamentoItem.ordem.asc(), OrcamentoItem.id.asc())
        .all()
    )
    if not itens:
        logger.debug(
            f"montar_arvore_preview_orcamento: orc={orcamento.id} sem itens — árvore vazia"
        )
        return []

    serv_ids = {it.servico_id for it in itens if it.servico_id}
    servicos = {s.id: s for s in Servico.query.filter(
        Servico.id.in_(serv_ids), Servico.admin_id == admin_id
    ).all()} if serv_ids else {}

    tmpl_ids = {s.template_padrao_id for s in servicos.values() if s.template_padrao_id}
    tmpl_ids |= {
        getattr(it, 'cronograma_template_override_id', None)
        for it in itens
        if getattr(it, 'cronograma_template_override_id', None)
    }
    tmpl_ids.discard(None)
    templates = {t.id: t for t in CronogramaTemplate.query.filter(
        CronogramaTemplate.id.in_(tmpl_ids),
        CronogramaTemplate.admin_id == admin_id,
    ).all()} if tmpl_ids else {}

    logger.debug(
        f"montar_arvore_preview_orcamento: orc={orcamento.id} admin={admin_id} — "
        f"{len(itens)} item(ns), {len(servicos)} serviço(s), "
        f"{len(tmpl_ids)} template_id(s) candidatos, {len(templates)} carregados"
    )

    arvore: list[dict] = []
    for it in itens:
        servico = servicos.get(it.servico_id) if it.servico_id else None
        override_id = getattr(it, 'cronograma_template_override_id', None)
        template_efetivo_id = override_id or (servico.template_padrao_id if servico else None)
        tmpl = templates.get(template_efetivo_id) if template_efetivo_id else None
        origem_template = ('override' if override_id and tmpl else
                           ('padrao' if tmpl else None))
        nome_serv = (servico.nome if servico else (it.descricao or f'Item {it.ordem}'))
        if tmpl:
            filhos = _expandir_template_para_arvore(tmpl, admin_id)
            arvore.append({
                'orcamento_item_id': it.id,
                'servico_id': servico.id if servico else None,
                'servico_nome': nome_serv,
                'template_id': tmpl.id,
                'template_nome': tmpl.nome,
                'origem_template': origem_template,
                'sem_template': False,
                'horas_totais_estimadas': _somar_horas_folhas(filhos),
                'marcado': True,
                'filhos': filhos,
            })
        else:
            arvore.append({
                'orcamento_item_id': it.id,
                # Mesmo filtro de tenant do ramo com template (:376): `servicos`
                # já é filtrado por admin_id, `it.servico_id` não.
                'servico_id': servico.id if servico else None,
                'servico_nome': nome_serv,
                'template_id': None,
                'template_nome': None,
                'origem_template': None,
                'sem_template': True,
                # Paridade com `montar_arvore_preview` (:299): mesmo shape de nó
                # sem template nas duas árvores. Aqui os campos são informativos
                # — esta árvore é PREVIEW (renderizada em orcamentos/editar.html
                # e servida por /orcamentos/<id>/preview-cronograma), nunca é
                # persistida nem passa por `materializar_cronograma`, que lê
                # `proposta_item_id`. Divergir do shape faria a tela do orçamento
                # prometer um cronograma diferente do que a proposta gera.
                'duracao_dias': 1,
                # float(): `OrcamentoItem.quantidade` é Numeric → Decimal, e este
                # dict vai direto para `jsonify`. Mesmo motivo de :300.
                'quantidade_prevista': float(it.quantidade) if it.quantidade is not None else None,
                'unidade_medida': it.unidade or (servico.unidade_medida if servico else None),
                'responsavel': 'empresa',
                'horas_totais_estimadas': 0.0,
                'marcado': False,
                'filhos': [],
            })
    return arvore


def tem_conteudo_para_revisar(proposta, admin_id: int) -> bool:
    """True se há pelo menos um PropostaItem com template efetivo e acessível:
    override por linha (Task #118) OU padrão do serviço (Task #102).

    Fix #6: agora junta CronogramaTemplate para garantir que o template
    referenciado realmente existe e pertence ao mesmo tenant (admin_id).
    O campo `ativo` NÃO é verificado — alinhado com montar_arvore_preview
    que também aceita templates desativados para propostas existentes.
    """
    # Task #118: override tem precedência → basta um item com override acessível.
    has_override = (
        db.session.query(PropostaItem.id)
        .join(
            CronogramaTemplate,
            CronogramaTemplate.id == PropostaItem.cronograma_template_override_id,
        )
        .filter(
            PropostaItem.proposta_id == proposta.id,
            PropostaItem.cronograma_template_override_id.isnot(None),
            CronogramaTemplate.admin_id == admin_id,
        )
        .limit(1)
        .first()
    )
    if has_override:
        return True
    # Template padrão do serviço: verifica que o template existe e é do mesmo tenant.
    q = (
        db.session.query(Servico.id)
        .join(PropostaItem, PropostaItem.servico_id == Servico.id)
        .join(
            CronogramaTemplate,
            CronogramaTemplate.id == Servico.template_padrao_id,
        )
        .filter(
            PropostaItem.proposta_id == proposta.id,
            Servico.admin_id == admin_id,
            Servico.template_padrao_id.isnot(None),
            CronogramaTemplate.admin_id == admin_id,
        )
        .limit(1)
    )
    return q.first() is not None


# ─────────────────────────────────────────────────────────────────────────────
# Materialização
# ─────────────────────────────────────────────────────────────────────────────

def materializar_cronograma(
    proposta,
    admin_id: int,
    obra_id: int,
    arvore_marcada: list[dict] | None = None,
) -> int:
    """Materializa árvore de cronograma + pesos como TarefaCronograma +
    ItemMedicaoCronogramaTarefa para a obra.

    Idempotente por proposta_item_id: se já existe TarefaCronograma com
    `gerada_por_proposta_item_id == it.id`, todo o subtree dessa proposta é
    pulado (no-op).

    Retorna número de TarefaCronograma criadas.
    """
    if arvore_marcada is None:
        # Fallback: usa cronograma_default_json salvo na proposta, ou
        # constrói árvore default (tudo marcado).
        arvore_marcada = (
            getattr(proposta, 'cronograma_default_json', None)
            or montar_arvore_preview(proposta, admin_id)
        )
    if not arvore_marcada:
        return 0

    # Idempotência (camada 1): descobrir quais proposta_item_id já materializados
    pi_ids = [n.get('proposta_item_id') for n in arvore_marcada if n.get('proposta_item_id')]
    if pi_ids:
        ja_existem = {
            row[0] for row in db.session.query(
                TarefaCronograma.gerada_por_proposta_item_id
            ).filter(
                TarefaCronograma.obra_id == obra_id,
                TarefaCronograma.admin_id == admin_id,
                TarefaCronograma.gerada_por_proposta_item_id.in_(pi_ids),
            ).all()
        }
    else:
        ja_existem = set()

    # Task #144 — Idempotência (camada 2): chave natural por
    # (subatividade_mestre_id | nome_tarefa, tarefa_pai_id) para o caso onde
    # `gerada_por_proposta_item_id` é nulo (snapshot antigo, re-materialização
    # via `arvore_marcada` sem PI vinculado, propagação proposta→obra etc).
    # Se um nó já existe pelo natural key, REUSAMOS a tarefa existente em vez
    # de inserir uma nova; oportunisticamente preenchemos
    # `gerada_por_proposta_item_id` para reforçar a idempotência futura.
    from services.cronograma_dedup import natural_key_index, _key_for
    nat_idx = natural_key_index(obra_id, admin_id, is_cliente=False)

    # Mapa proposta_item_id -> ItemMedicaoComercial (para vincular pesos)
    imc_por_pi = {
        imc.proposta_item_id: imc for imc in ItemMedicaoComercial.query.filter(
            ItemMedicaoComercial.obra_id == obra_id,
            ItemMedicaoComercial.admin_id == admin_id,
            ItemMedicaoComercial.proposta_item_id.in_(pi_ids) if pi_ids else False,
        ).all()
    }

    # Offset de ordem para não colidir com tarefas existentes (mesmo modo)
    max_ordem = (
        db.session.query(db.func.max(TarefaCronograma.ordem))
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .scalar()
    ) or 0
    ordem_seq = [int(max_ordem) + 10]

    # Data inicial = obra.data_inicio (ou hoje); detalhamento de datas
    # sequenciais é delegado a `utils.cronograma_engine.recalcular_cronograma`
    # ao final desta função para respeitar calendário de empresa, predecessoras
    # etc. Aqui apenas seedamos a data_inicio das folhas com a referência da obra.
    from models import Obra as _Obra
    _obra = _Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    data_corrente = (_obra.data_inicio if _obra and _obra.data_inicio else date.today())
    data_seed = data_corrente

    # Mesmo default por obra que `cronograma_views.criar_tarefa:471` aplica:
    # numa obra que fatura pelo % físico apurado no RDO, exigir quantitativo
    # por tarefa é contraditório. Aquele commit (0ad1822) só cobriu o caminho
    # de criação MANUAL — tarefa nascida de proposta ficava com a coluna NULL e
    # `modo_da_tarefa` deduzia 'quantidade' a partir do quantitativo comercial,
    # contradizendo o regime da obra.
    # `'fixa'` (default do schema) deixa NULL e mantém a dedução legada, então
    # nada muda nas obras existentes. Escolha explícita não existe aqui: a
    # árvore de preview não carrega modo por nó — quem quiser divergir edita a
    # tarefa depois, e aí a escolha vence (modo_da_tarefa:135).
    modo_padrao_obra = (
        'percentual'
        if _obra and (_obra.regime_medicao or '').strip().lower() == 'percentual'
        else None
    )
    total_criadas = 0

    for nivel0 in arvore_marcada:
        pi_id = nivel0.get('proposta_item_id')
        if not nivel0.get('marcado'):
            continue
        # `sem_template` NÃO é mais motivo de descarte. Até 2026-07-21 havia um
        # `continue` aqui: uma proposta cujos serviços não tinham
        # `template_padrao_id` aprovava, criava a obra e a deixava com ZERO
        # tarefa — sem erro e sem mensagem. Agora o nó vira uma tarefa-esqueleto
        # de nível 0 (sem filhos), com o quantitativo do PropostaItem, que o
        # admin detalha depois no Gantt. Continua valendo o default
        # `marcado=False` de `montar_arvore_preview` — nada é materializado
        # sem marcação explícita.
        sem_template = bool(nivel0.get('sem_template'))
        if pi_id in ja_existem:
            logger.info(f"#102: proposta_item_id={pi_id} já materializado em obra={obra_id} — skip")
            continue

        # Nível 0 = nó raiz "Serviço" (grupo agregador)
        nome_serv = nivel0.get('servico_nome') or 'Serviço'
        # Task #4 — servico_id da raiz e propagado para todas as tarefas-filhas
        # (vem da árvore montada por montar_arvore_preview, que carrega
        # servico_id do PropostaItem). Necessário para que a UI/serviço de
        # custos por serviço funcione e para o auto-vínculo Função→Composição.
        servico_id_no = nivel0.get('servico_id')
        chave_serv = _key_for(None, nome_serv, None)
        existente_serv = nat_idx.get(chave_serv)
        if existente_serv is not None:
            # Reusar tarefa existente (Task #144) — preenche PI se faltar
            tarefa_serv = existente_serv
            if tarefa_serv.gerada_por_proposta_item_id is None and pi_id:
                tarefa_serv.gerada_por_proposta_item_id = pi_id
            if tarefa_serv.servico_id is None and servico_id_no:
                tarefa_serv.servico_id = servico_id_no
            logger.info(
                f"#144: nó-raiz {nome_serv!r} já existia em obra={obra_id} "
                f"(id={tarefa_serv.id}) — reuso (skip insert)"
            )
        else:
            # Com template a raiz é um GRUPO agregador: quantitativo mora nas
            # folhas e a duração é sobrescrita pelo somatório mais abaixo. Sem
            # template a raiz é a ÚNICA tarefa, então ela mesma carrega o
            # quantitativo do PropostaItem — é o que faz `modo_da_tarefa`
            # deduzir 'quantidade' em vez do fallback percentual (a não ser
            # que a obra seja de regime percentual: aí `modo_padrao_obra`
            # grava a escolha e vence a dedução).
            tarefa_serv = TarefaCronograma(
                obra_id=obra_id,
                nome_tarefa=nome_serv,
                duracao_dias=max(1, int(nivel0.get('duracao_dias') or 1)) if sem_template else 1,
                data_inicio=data_seed,
                quantidade_total=nivel0.get('quantidade_prevista') if sem_template else None,
                unidade_medida=nivel0.get('unidade_medida') if sem_template else None,
                modo_apontamento=modo_padrao_obra,
                tarefa_pai_id=None,
                ordem=ordem_seq[0],
                admin_id=admin_id,
                is_cliente=False,
                responsavel=(nivel0.get('responsavel') or 'empresa') if sem_template else 'empresa',
                gerada_por_proposta_item_id=pi_id,
                servico_id=servico_id_no,
            )
            ordem_seq[0] += 10
            db.session.add(tarefa_serv)
            db.session.flush()
            nat_idx[chave_serv] = tarefa_serv
            total_criadas += 1

        # IMC para vincular pesos
        imc = imc_por_pi.get(pi_id)

        # Coletar folhas marcadas com horas para cálculo de peso
        folhas_marcadas: list[tuple[TarefaCronograma, float]] = []

        # Esqueleto: sem filhos, a própria raiz é a folha. Sem isto ela não
        # entraria no vínculo ItemMedicaoCronogramaTarefa abaixo e o avanço da
        # tarefa não moveria a medição comercial do item.
        if sem_template:
            folhas_marcadas.append((tarefa_serv, 0.0))

        # Recursivo nos filhos (grupos e subatividades).
        # NOTA: data_inicio das folhas é setada apenas como SEED (igual à da
        # obra). O cálculo sequencial real (respeitando calendário/predecessoras)
        # é responsabilidade de `recalcular_cronograma` chamado ao final.
        def _rec(nos: list[dict], pai_id: int) -> None:
            nonlocal total_criadas
            for n in nos:
                if not n.get('marcado'):
                    continue
                is_grupo = bool(n.get('filhos'))
                sub_id = n.get('subatividade_mestre_id')
                if sub_id:
                    sm = SubatividadeMestre.query.filter_by(id=sub_id, admin_id=admin_id).first()
                    if not sm:
                        sub_id = None
                duracao = max(1, int(n.get('duracao_dias') or 1))
                qty = n.get('quantidade_prevista')
                nome_n = n.get('nome') or 'Tarefa'
                chave_n = _key_for(sub_id, nome_n, pai_id)
                existente = nat_idx.get(chave_n)
                if existente is not None:
                    # Task #144 — tarefa equivalente já existe; reusar
                    tarefa = existente
                    if tarefa.gerada_por_proposta_item_id is None and pi_id:
                        tarefa.gerada_por_proposta_item_id = pi_id
                    # Task #4 — preencher servico_id quando faltar
                    if tarefa.servico_id is None and servico_id_no:
                        tarefa.servico_id = servico_id_no
                    logger.info(
                        f"#144: tarefa {nome_n!r} (sub={sub_id}, pai={pai_id}) "
                        f"já existia em obra={obra_id} (id={tarefa.id}) — reuso"
                    )
                else:
                    tarefa = TarefaCronograma(
                        obra_id=obra_id,
                        nome_tarefa=nome_n,
                        duracao_dias=duracao,
                        data_inicio=data_seed if not is_grupo else None,
                        quantidade_total=None if is_grupo else qty,
                        unidade_medida=None if is_grupo else n.get('unidade_medida'),
                        # Grupo é agregador (não se aponta), mas gravar o modo
                        # nele é inofensivo e mantém o subtree coerente se
                        # virar folha depois.
                        modo_apontamento=modo_padrao_obra,
                        responsavel=n.get('responsavel') or 'empresa',
                        tarefa_pai_id=pai_id,
                        ordem=ordem_seq[0],
                        admin_id=admin_id,
                        is_cliente=False,
                        subatividade_mestre_id=sub_id,
                        gerada_por_proposta_item_id=pi_id,
                        servico_id=servico_id_no,
                    )
                    ordem_seq[0] += 10
                    db.session.add(tarefa)
                    db.session.flush()
                    nat_idx[chave_n] = tarefa
                    total_criadas += 1

                if is_grupo:
                    _rec(n['filhos'], tarefa.id)
                else:
                    horas = float(n.get('horas_estimadas') or 0)
                    folhas_marcadas.append((tarefa, horas))

        _rec(nivel0.get('filhos') or [], tarefa_serv.id)

        # Atualizar duracao do nó-raiz para somatório
        if folhas_marcadas:
            try:
                duracao_total = sum(int(t.duracao_dias or 1) for t, _ in folhas_marcadas)
                tarefa_serv.duracao_dias = max(1, duracao_total)
            except Exception:
                pass

        # ── Vincular pesos via ItemMedicaoCronogramaTarefa ──
        if imc and folhas_marcadas:
            soma_horas = sum(h for _, h in folhas_marcadas)
            n_folhas = len(folhas_marcadas)
            # `sem_template` fica fora do aviso abaixo: ali a folha única é a
            # própria tarefa-esqueleto, e 100% nela é o resultado correto — não
            # um fallback que o operador precise corrigir.
            if soma_horas <= 0 and not sem_template:
                # Task #102: aviso explícito quando NENHUMA folha marcada tem
                # `duracao_estimada_horas` configurada — peso é distribuído
                # igualmente entre as folhas (fallback). Operador deve revisar
                # SubatividadeMestre para garantir cálculo de medição correto.
                logger.warning(
                    f"#102 FALLBACK: proposta_item_id={pi_id} (obra={obra_id}) "
                    f"— {n_folhas} folha(s) sem horas estimadas; aplicando "
                    f"divisão igual de peso (100/{n_folhas} = "
                    f"{round(100.0 / n_folhas, 2)}%). Configure "
                    f"SubatividadeMestre.duracao_estimada_horas para usar "
                    f"peso ponderado por horas."
                )
            for tarefa_folha, horas in folhas_marcadas:
                if soma_horas > 0:
                    peso = (horas / soma_horas) * 100.0
                else:
                    peso = 100.0 / n_folhas
                # Arredonda para 2 decimais
                peso_dec = Decimal(str(round(peso, 2)))
                # Task #144: se a folha foi REUSADA (tarefa pré-existente),
                # pode já existir vínculo IMC↔tarefa (UniqueConstraint
                # `uq_item_tarefa`) — neste caso só atualiza o peso.
                vinculo = ItemMedicaoCronogramaTarefa.query.filter_by(
                    item_medicao_id=imc.id,
                    cronograma_tarefa_id=tarefa_folha.id,
                ).first()
                if vinculo:
                    vinculo.peso = peso_dec
                else:
                    vinculo = ItemMedicaoCronogramaTarefa(
                        item_medicao_id=imc.id,
                        cronograma_tarefa_id=tarefa_folha.id,
                        peso=peso_dec,
                        admin_id=admin_id,
                    )
                    db.session.add(vinculo)

    if total_criadas:
        db.session.flush()
        # Recalcular datas via engine oficial (respeita calendário, predecessoras
        # e propaga datas dos pais a partir das folhas). Task #102 (rev):
        # falha aqui DEVE propagar — sessão será revertida pelo caller, evitando
        # cronograma persistido com datas seed inconsistentes.
        from utils.cronograma_engine import recalcular_cronograma
        recalcular_cronograma(obra_id, admin_id, cliente=False)
        logger.info(
            f"#102: {total_criadas} TarefaCronograma + pesos materializados "
            f"para obra={obra_id} proposta={proposta.id}"
        )
    return total_criadas
