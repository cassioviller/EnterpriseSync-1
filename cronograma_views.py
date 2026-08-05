"""
Blueprint do Módulo de Cronograma de Obras — MS Project style (V2).
Rotas JSON para CRUD de tarefas + recálculo automático de datas.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, url_for, flash
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from models import (
    db, Obra, TarefaCronograma, TarefaVinculo, RDOApontamentoCronograma,
    CronogramaBaseline, CronogramaBaselineItem,
    CronogramaTemplate, CronogramaTemplateItem, SubatividadeMestre, Servico,
    RDO, RDOMaoObra, RDOServicoSubatividade, Funcionario,
    ComposicaoServico, SubatividadeMaoObra,
)
from services.cronograma_undo import (
    MSG_NADA_DESFAZER,
    MSG_NADA_REFAZER,
    desfazer as undo_desfazer,
    estado_pilha,
    refazer as undo_refazer,
    registrar_acao,
    snapshot_obra,
)
from services.cronograma_predecessor_parser import (
    ErroParsePredecessora,
    formatar_predecessoras,
    parsear_predecessoras,
)
from services.cronograma_scheduler import (
    TIPOS_VINCULO,
    ErroCiclo,
    ids_tarefas_iniciadas,
    recalcular_obra,
)
from utils.cronograma_engine import (
    recalcular_cronograma,
    verificar_ciclo,
    get_calendario,
    calcular_data_fim,
    calcular_progresso_rdo,
    calcular_progresso_geral_obra_v2,
    atualizar_percentual_tarefa,
    sincronizar_percentuais_obra,
    ordenar_arvore_visual,
)

logger = logging.getLogger(__name__)

cronograma_bp = Blueprint('cronograma', __name__, url_prefix='/cronograma')


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_v2():
    """Retorna redirect/abort se o usuário não for V2."""
    from utils.tenant import is_v2_active
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


def _admin_id() -> int:
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


def _guard_editar_obra(obra_id: int):
    """Fase 1 — segundo eixo de autorização nas rotas que MEXEM na obra.

    Devolve uma resposta JSON 404 quando o usuário não pode editar aquela
    obra, ou None quando pode. 404 e não 403 é deliberado: a mesma escolha
    já travada por `tests/test_cronograma_permissoes.py` — a existência de
    uma obra fora do alcance não vaza.

    Com `configuracao_empresa.escopo_obra_ativo` DESLIGADA (o default),
    `papel_na_obra` devolve GESTOR para todo usuário do tenant
    (utils/autorizacao.py:107-121) e este guard é transparente. É o que torna
    esta mudança reversível sem rollback.
    """
    from utils.autorizacao import pode_editar_obra
    if not pode_editar_obra(obra_id):
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada'}), 404
    return None


def _guard_apontar_obra(obra_id: int):
    """Fase 1 — mesmo guard, para as rotas de APONTAMENTO.

    GESTOR e APONTADOR passam; LEITOR não. Separado de `_guard_editar_obra`
    porque lançar produção e reestruturar o cronograma são permissões
    diferentes (PAPEIS_QUE_APONTAM vs PAPEIS_QUE_EDITAM_OBRA em
    utils/autorizacao.py).
    """
    from utils.autorizacao import pode_apontar_na_obra
    if not pode_apontar_na_obra(obra_id):
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada'}), 404
    return None


def _editor_v2_on() -> bool:
    """Flag do editor de cronograma v2 no tenant atual (Fase 1).

    Import tardio (padrão deste módulo para utils.tenant): nunca levanta,
    default False — com a flag desligada TODAS as rotas se comportam
    exatamente como antes.
    """
    from utils.tenant import cronograma_editor_v2_ativo
    return cronograma_editor_v2_ativo()


def _replanejar_pos_commit(obra_id: int, admin_id: int, cliente_mode: bool) -> None:
    """Ponto ÚNICO onde o editor v2 replaneja a curva planejada (A06, B2.18).

    ## O que isto conserta

    O editor recalcula datas o dia inteiro e **nunca tocava
    `RDOApontamentoCronograma.percentual_planejado`**. A curva planejada dos
    apontamentos já gravados continuava apontando para um plano que não existe
    mais, e quem a lê — a curva de avanço da obra, o PDF do RDO, o EVM — comparava
    o realizado com um planejado órfão.

    ## Por que um helper, e não sete chamadas

    São sete call-sites, e cada um repetiria as mesmas três armadilhas. Sete
    cópias de um try/except são sete chances de errar uma:

    1. **`cliente_mode` é no-op, e não por elegância.** `replanejar_curvas_obra`
       filtra tarefas com `is_cliente=False` fixo, mas varre **TODOS** os
       apontamentos da obra — no modo cliente seria uma varredura inteira que não
       replaneja coisa nenhuma.
    2. **Falha aqui NUNCA desfaz a edição já commitada.** É pós-commit: o
       `rollback()` do `except` desfaz apenas o que este helper tentou. Mesma
       postura de `services/cronograma_versao_service._motor_pos_commit`.
    3. **`except HTTPException: raise` antes do catch-all** — regra da casa. O
       guard de tenancy já rodou muito antes e o helper é pós-commit, mas a ordem
       das cláusulas não custa nada e fecha a classe inteira.

    **Chame ANTES de serializar a resposta.** O `rollback()` do `except` expira os
    objetos ORM; chamando antes, `_tarefa_to_dict`/`_mapas_vinculos` re-hidratam do
    banco já commitado em vez de tocarem instância expirada.

    Não devolve nada: o replanejamento não entra na resposta HTTP.
    """
    if cliente_mode:
        return
    try:
        from utils.cronograma_engine import replanejar_curvas_obra
        replanejar_curvas_obra(obra_id, admin_id,
                               com_relatorio=False, sincronizar=False)
    except HTTPException:
        raise
    except Exception:
        from models import db
        db.session.rollback()
        logger.exception(
            '[A06] replanejamento pós-commit falhou (obra=%s) — a edição já '
            'commitada NÃO foi desfeita', obra_id)


def _com_undo(tipo_acao: str):
    """Fase 3 — empilha a ação da rota na pilha de desfazer/refazer.

    Envolve a view por FORA (fica logo abaixo de `@login_required`): tira um
    snapshot da obra antes, deixa a rota rodar, e compara depois. Nenhuma
    rota precisa saber que existe histórico.

    Duas propriedades vêm de graça do diff:

    * rota que devolveu 400/404 fez rollback ⇒ o diff é vazio ⇒ **nada é
      empilhado**, sem tratamento caso a caso;
    * a cascata de datas do motor entra no payload porque realmente mudou.

    Com a flag desligada o decorator é transparente (chama a view e sai).
    Falha ao gravar o histórico é logada e engolida: a edição já commitou e
    não pode cair por causa do registro.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(obra_id: int, *args, **kwargs):
            if not _editor_v2_on():
                return view(obra_id, *args, **kwargs)
            admin_id = _admin_id()
            cliente_mode = _modo_cliente()
            try:
                antes = snapshot_obra(obra_id, admin_id, cliente_mode)
            except Exception:
                logger.exception('[undo] falha no snapshot inicial de %s — '
                                 'ação seguirá sem histórico', obra_id)
                return view(obra_id, *args, **kwargs)

            resposta = view(obra_id, *args, **kwargs)

            try:
                registrar_acao(obra_id, admin_id, current_user.id, cliente_mode,
                               tipo_acao, antes)
            except Exception:
                db.session.rollback()
                logger.exception('[undo] falha ao empilhar ação %r da obra %s '
                                 '(a edição foi preservada)', tipo_acao, obra_id)
            return resposta
        return wrapper
    return decorator


def _mapas_vinculos(obra_id: int, admin_id: int, cliente_mode: bool,
                    tarefas: list | None = None):
    """Mapas do editor v2 para a obra — uma query de vínculos, zero N+1.

    Devolve `(vinculos_por_sucessora, linha_para_tarefa, tarefa_para_linha,
    ids_resumo)`. A numeração de linhas (1-based) vem de
    `ordenar_arvore_visual` — a MESMA da grade e do parser de predecessoras,
    para os números nunca divergirem. Vínculos com qualquer ponta fora da
    grade (outro modo cliente/interno ou dado sujo) ficam fora dos mapas,
    então `formatar_predecessoras` nunca levanta na serialização.
    """
    if tarefas is None:
        tarefas = (
            TarefaCronograma.query
            .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
            .filter(TarefaCronograma.ativa.is_(True))
            .order_by(TarefaCronograma.ordem, TarefaCronograma.id)
            .all()
        )
    ordenadas = ordenar_arvore_visual(tarefas)
    linha_para_tarefa = {i + 1: t.id for i, t in enumerate(ordenadas)}
    tarefa_para_linha = {t.id: i + 1 for i, t in enumerate(ordenadas)}
    ids_resumo = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}

    vinculos_por_sucessora: dict[int, list] = {}
    vincs = (
        TarefaVinculo.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(TarefaVinculo.id)
        .all()
    )
    for v in vincs:
        if v.predecessora_id in tarefa_para_linha and v.sucessora_id in tarefa_para_linha:
            vinculos_por_sucessora.setdefault(v.sucessora_id, []).append(v)
    return vinculos_por_sucessora, linha_para_tarefa, tarefa_para_linha, ids_resumo


def _dual_write_vinculo_legado(tarefa: TarefaCronograma, admin_id: int) -> None:
    """Flag OFF — espelha silenciosamente o `predecessora_id` legado em
    `TarefaVinculo` TI/0 (removendo antes os vínculos da sucessora), para a
    tabela não ficar obsoleta enquanto a flag não liga (plano C3/Riscos).
    NUNCA falha a request: qualquer erro vira rollback + warning.
    """
    try:
        TarefaVinculo.query.filter_by(
            sucessora_id=tarefa.id, obra_id=tarefa.obra_id, admin_id=admin_id
        ).delete(synchronize_session=False)
        if tarefa.predecessora_id:
            db.session.add(TarefaVinculo(
                admin_id=admin_id,
                obra_id=tarefa.obra_id,
                predecessora_id=tarefa.predecessora_id,
                sucessora_id=tarefa.id,
                tipo='TI',
                lag_dias=0,
            ))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning('[editor-v2] dual-write de vínculo falhou (tarefa %s): %s',
                       tarefa.id, exc)


def _tarefa_to_dict(t: TarefaCronograma, percentual_planejado: float = 0.0, *,
                    vinculos_por_sucessora: dict | None = None,
                    tarefa_para_linha: dict | None = None) -> dict:
    sub_nome = None
    if getattr(t, 'subatividade_mestre', None):
        sub_nome = t.subatividade_mestre.nome
    # Fase 1 (editor v2) — `predecessoras_texto` só é montado quando o
    # chamador passa os mapas da obra (`_mapas_vinculos`); sem mapas, ''
    # barato — nunca há query por tarefa aqui (sem N+1).
    predecessoras_texto = ''
    if vinculos_por_sucessora is not None and tarefa_para_linha is not None:
        vincs = vinculos_por_sucessora.get(t.id) or []
        if vincs:
            predecessoras_texto = formatar_predecessoras(vincs, tarefa_para_linha)
    return {
        'id': t.id,
        'obra_id': t.obra_id,
        'tarefa_pai_id': t.tarefa_pai_id,
        'predecessora_id': t.predecessora_id,
        'ordem': t.ordem,
        'nome_tarefa': t.nome_tarefa,
        'duracao_dias': t.duracao_dias,
        'data_inicio': t.data_inicio.isoformat() if t.data_inicio else None,
        'data_fim': t.data_fim.isoformat() if t.data_fim else None,
        'quantidade_total': t.quantidade_total,
        'unidade_medida': t.unidade_medida,
        # Escolha explícita de modo (migration 220). None = automático:
        # `modo_da_tarefa` deduz de quantidade_total + unidade_medida como
        # sempre fez. A UI do Gantt usa este campo para posicionar o seletor.
        'modo_apontamento': getattr(t, 'modo_apontamento', None),
        'subatividade_mestre_id': getattr(t, 'subatividade_mestre_id', None),
        'subatividade_mestre_nome': sub_nome,
        'servico_id': getattr(t, 'servico_id', None),
        'percentual_concluido': t.percentual_concluido or 0.0,
        'percentual_planejado': round(percentual_planejado, 1),
        'responsavel': getattr(t, 'responsavel', 'empresa') or 'empresa',
        # Task #102: marcador para o front exibir aviso ao editar/excluir tarefas
        # geradas automaticamente pela aprovação de proposta.
        'gerada_por_proposta_item_id': getattr(t, 'gerada_por_proposta_item_id', None),
        # Fase 1 (editor v2) — campos aditivos, inofensivos com a flag off.
        'is_critica': bool(getattr(t, 'is_critica', False)),
        'folga_dias': getattr(t, 'folga_dias', None),
        'predecessoras_texto': predecessoras_texto,
    }


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parse_modo_apontamento(data, tarefa_is_marco=False):
    """Lê `modo_apontamento` do corpo. Devolve (valor, erro).

    Contrato:
      * chave ausente  → (None, None)  — não mexer no que já está gravado;
      * '' / None      → ('', None)    — LIMPAR (voltar ao automático);
      * valor válido   → (valor, None);
      * qualquer outra → (None, mensagem de erro).

    O sentinel '' distingue "não mandou" de "mandou vazio para limpar" —
    sem ele não haveria como voltar uma tarefa ao modo automático pela UI.
    """
    from services.cronograma_apontamento_service import MODOS_APONTAMENTO

    if 'modo_apontamento' not in data:
        return None, None

    bruto = data.get('modo_apontamento')
    if bruto in (None, ''):
        return '', None

    valor = str(bruto).strip().lower()
    if valor not in MODOS_APONTAMENTO:
        return None, (
            f'modo_apontamento inválido: {bruto!r}. '
            f'Use um de {", ".join(MODOS_APONTAMENTO)}, ou vazio para automático.')
    if tarefa_is_marco and valor == 'quantidade':
        return None, ('Um marco só admite apontamento percentual (0% ou 100%) '
                      '— modo_apontamento="quantidade" é inválido para marco.')
    return valor, None


def _modo_cliente() -> bool:
    """
    Retorna True quando a operação está no modo "cronograma do cliente".
    Acionado por ?cliente=1 (querystring) OU pelo campo cliente=1 no body
    (form/JSON). Em modo cliente, todas as queries operam apenas sobre
    TarefaCronograma com is_cliente=True; o plano interno fica intocado.
    """
    val = request.values.get('cliente')
    if val is None:
        try:
            payload = request.get_json(silent=True) or {}
            val = payload.get('cliente')
        except Exception:
            val = None
    return str(val or '').strip() in ('1', 'true', 'True', 'on')


def _qs_cliente(cliente: bool) -> str:
    """Sufixo de querystring para preservar o modo entre redirects/links."""
    return '?cliente=1' if cliente else ''


# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICE — Lista de obras com cronograma
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/')
@login_required
def index():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()

    from sqlalchemy import func as sqlfunc
    # Otimização N+1: uma agregação por obra_id (count + avg) em vez de duas queries
    # por obra dentro do loop.
    #
    # p4 — a agregação tinha dois defeitos que faziam este índice discordar do
    # detalhe da obra:
    #
    #   1. **contava a cópia-cliente** (`is_cliente=True`) e as arquivadas,
    #      diluindo a média com um plano paralelo parado;
    #   2. **contava tarefa-pai junto com as filhas** — o pai entra com o
    #      próprio percentual e as filhas entram de novo, então uma etapa com
    #      muitas subtarefas pesa mais do que deveria.
    #
    # Agora a média é sobre FOLHAS do cronograma interno vivo, ponderada por
    # duração — a mesma regra dominante de `calcular_progresso_geral_obra_v2`.
    # Não é bit-idêntica à do detalhe quando todas as folhas têm
    # `quantidade_total` (lá a quantidade governa o peso); o número exato da
    # obra continua sendo o do detalhe, e é ele que vira dinheiro.
    _pais = (
        db.session.query(TarefaCronograma.tarefa_pai_id)
        .filter(TarefaCronograma.admin_id == admin_id,
                TarefaCronograma.tarefa_pai_id.isnot(None))
        .distinct()
    )
    _peso = sqlfunc.coalesce(TarefaCronograma.duracao_dias, 1)
    _agg_rows = (
        db.session.query(
            TarefaCronograma.obra_id,
            sqlfunc.count(TarefaCronograma.id),
            (sqlfunc.sum(
                sqlfunc.coalesce(TarefaCronograma.percentual_concluido, 0)
                * _peso) / sqlfunc.nullif(sqlfunc.sum(_peso), 0)),
        )
        .filter(TarefaCronograma.admin_id == admin_id,
                TarefaCronograma.is_cliente.is_(False),
                TarefaCronograma.ativa.is_(True),
                TarefaCronograma.id.notin_(_pais))
        .group_by(TarefaCronograma.obra_id)
        .all()
    )
    _agg_por_obra = {r[0]: (r[1], r[2]) for r in _agg_rows}
    # Monta sumário por obra
    resumos = []
    for obra in obras:
        total, perc_medio = _agg_por_obra.get(obra.id, (0, 0.0))
        perc_medio = perc_medio or 0.0
        resumos.append({
            'obra': obra,
            'total_tarefas': total,
            'perc_medio': round(float(perc_medio), 1),
            'tem_cronograma': total > 0,
        })

    cal = get_calendario(admin_id)
    return render_template(
        'cronograma/index.html',
        resumos=resumos,
        calendario=cal,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>')
@login_required
def cronograma_obra(obra_id: int):
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    cliente_mode = _modo_cliente()

    # Sincroniza percentual_concluido com o último apontamento do RDO antes de exibir
    # (No modo cliente, sincroniza apenas o bottom-up dos pais; RDO não toca tarefas-cliente)
    sincronizar_percentuais_obra(obra_id, admin_id, cliente=cliente_mode)

    tarefas_raw = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    # Tree-flatten (recursive DFS) extraído para helper compartilhado
    # (`ordenar_arvore_visual`): define a ordem visual das linhas e o mapa de
    # profundidade para indentação — mesma numeração usada pelo parser de
    # predecessoras.
    tarefas, nivel_map = ordenar_arvore_visual(tarefas_raw, com_nivel=True)

    cal = get_calendario(admin_id)

    # Fase 1 (editor v2): com a flag ligada, os dicts levam
    # `predecessoras_texto` real (mapas da obra em uma query — sem N+1).
    from utils.tenant import rdo_percentual_livre_on
    flag_on = _editor_v2_on()
    _kw_v2: dict = {}
    if flag_on:
        vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode,
                                          tarefas=tarefas)
        _kw_v2 = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)

    # Calcula progresso planejado de hoje para cada tarefa
    hoje = date.today()
    tarefas_dict = []
    planejados_map: dict[int, float] = {}
    for t in tarefas:
        prog = calcular_progresso_rdo(t.id, hoje, admin_id)
        planejado = prog['percentual_planejado']
        planejados_map[t.id] = planejado
        tarefas_dict.append(_tarefa_to_dict(t, planejado, **_kw_v2))

    # Build lookup maps for rendering
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    tarefas_pred_map = {t.id: t.predecessora_id for t in tarefas}

    # Nome da empresa para o campo "Responsável"
    from models import ConfiguracaoEmpresa
    config_empresa = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config_empresa.nome_empresa if config_empresa else 'Empresa'

    # Progresso Geral (header + linha raiz "OBRA"): mesma métrica do card de RDO —
    # média das FOLHAS ponderada por duração, acumulada até hoje
    # (calcular_progresso_geral_obra_v2), em vez da média simples de todas as
    # tarefas (que dupla-conta os pais) ou do rollup hierárquico (que superestima).
    # Só no cronograma da empresa; o modo cliente mantém a média do template.
    # Fase 3 — estado inicial da pilha de desfazer/refazer deste usuário
    # nesta obra e neste modo.
    pode_desfazer = pode_refazer = False
    if flag_on:
        pode_desfazer, pode_refazer = estado_pilha(obra_id, current_user.id,
                                                   cliente_mode)

    # Fase 4 — linha de base ativa. Só na visão interna (spec §5: "o portal
    # do cliente não muda"); sem baseline o `baseline_map` fica vazio e nem a
    # coluna Desvio nem as barras cinzas são renderizadas.
    baseline_ativa = None
    baseline_map: dict = {}
    if flag_on and not cliente_mode:
        _bl = _baseline_ativa(obra_id, admin_id, cliente_mode)
        if _bl is not None:
            baseline_ativa = _baseline_to_dict(_bl)
            baseline_map = _itens_da_baseline(_bl)

    progresso_geral_header = None
    if cliente_mode:
        # p4 — no modo cliente o header ficava None e o TEMPLATE calculava a
        # média simples em Jinja (`perc_total`) — a quinta fórmula de
        # progresso do sistema, escondida numa expressão de template. O
        # conjunto de tarefas aqui é o plano do CLIENTE (`is_cliente=True`),
        # que o motor não cobre; então a média sai daqui, em Python, com a
        # mesma regra do motor: só FOLHAS, ponderadas por duração.
        _pais_cliente = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
        _folhas = [t for t in tarefas if t.id not in _pais_cliente]
        _peso_total = sum(float(t.duracao_dias or 1) for t in _folhas)
        if _peso_total > 0:
            progresso_geral_header = round(sum(
                float(t.percentual_concluido or 0) * float(t.duracao_dias or 1)
                for t in _folhas) / _peso_total, 1)
        else:
            progresso_geral_header = 0.0
    else:
        progresso_geral_header = calcular_progresso_geral_obra_v2(
            obra_id, hoje, admin_id)['progresso_geral_pct']
        # Alinha a linha raiz (OBRA, sem tarefa_pai_id) ao mesmo número no array
        # do front (JS/gantt). Só exibição — não persiste no banco.
        for d in tarefas_dict:
            if not d.get('tarefa_pai_id'):
                d['percentual_concluido'] = progresso_geral_header

    return render_template(
        'obras/cronograma.html',
        obra=obra,
        tarefas=tarefas,
        tarefas_dict=tarefas_dict,
        calendario=cal,
        pai_ids=pai_ids,
        tarefas_pred_map=tarefas_pred_map,
        planejados_map=planejados_map,
        nivel_map=nivel_map,
        hoje=hoje,
        nome_empresa=nome_empresa,
        progresso_geral_header=progresso_geral_header,
        modo_cliente=cliente_mode,
        # Fase 1 (editor v2): o Step D define `const EDITOR_V2` a partir daqui.
        editor_v2=flag_on,
        # Fase 3: estado inicial dos botões Desfazer/Refazer. Com a flag off
        # nem a toolbar existe, então nem se consulta a pilha.
        pode_desfazer=pode_desfazer,
        pode_refazer=pode_refazer,
        # Fase 4: barra cinza no Gantt + coluna "Desvio (dias)".
        baseline_ativa=baseline_ativa,
        baseline_map=baseline_map,
        # RDO em porcentagem livre: com a flag ligada não existe escolha de
        # modo — toda tarefa é apontada em % —, então o seletor "Como apontar
        # no RDO" some dos modais. A API segue aceitando `modo_apontamento`
        # (inerte enquanto a flag estiver ligada), o que mantém a coluna
        # intacta para quando/se a flag for desligada.
        rdo_percentual_livre=rdo_percentual_livre_on(admin_id),
        base_template='base_iframe.html' if cliente_mode else 'base_completo.html',
    )


# ─────────────────────────────────────────────────────────────────────────────
# CRIAR TAREFA
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefa', methods=['POST'])
@login_required
@_com_undo('criar_tarefa')
def criar_tarefa(obra_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
    cliente_mode = _modo_cliente()

    data = request.get_json(silent=True) or request.form.to_dict()

    nome = (data.get('nome_tarefa') or '').strip()
    if not nome:
        return jsonify({'status': 'error', 'msg': 'Nome da tarefa é obrigatório'}), 400

    try:
        duracao = int(data.get('duracao_dias') or 1)
    except (ValueError, TypeError):
        duracao = 1

    data_inicio = _parse_date(data.get('data_inicio'))
    tarefa_pai_id = data.get('tarefa_pai_id') or None
    if tarefa_pai_id:
        tarefa_pai_id = int(tarefa_pai_id)
        # Validar que a tarefa pai existe e pertence à mesma obra/tenant/modo
        pai = TarefaCronograma.query.filter_by(
            id=tarefa_pai_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
        ).first()
        if not pai:
            return jsonify({
                'status': 'error',
                'msg': f'Tarefa pai id={tarefa_pai_id} não encontrada nesta obra.'
            }), 400

    predecessora_id = data.get('predecessora_id') or None
    if predecessora_id:
        predecessora_id = int(predecessora_id)
        # Validar que a predecessora existe e pertence à mesma obra/tenant/modo
        pred_check = TarefaCronograma.query.filter_by(
            id=predecessora_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
        ).first()
        if not pred_check:
            return jsonify({
                'status': 'error',
                'msg': f'Tarefa predecessora id={predecessora_id} não encontrada nesta obra.'
            }), 400
        if verificar_ciclo(0, predecessora_id, admin_id):
            return jsonify({'status': 'error', 'msg': 'Referência circular detectada'}), 400

    # Próxima ordem
    ultima = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem.desc())
        .first()
    )
    nova_ordem = (ultima.ordem + 1) if ultima else 0

    if data_inicio is None:
        if predecessora_id:
            pred = TarefaCronograma.query.get(predecessora_id)
            if pred and pred.data_fim:
                from utils.cronograma_engine import proximo_dia_util
                cal = get_calendario(admin_id)
                data_inicio = proximo_dia_util(
                    pred.data_fim, cal.considerar_sabado, cal.considerar_domingo
                )
        if data_inicio is None:
            data_inicio = date.today()

    cal = get_calendario(admin_id)
    data_fim = calcular_data_fim(
        data_inicio, duracao, cal.considerar_sabado, cal.considerar_domingo
    )

    from services.dropdown_service import get_opcoes_valores as _get_resp_opcoes
    _resp_validos = [v.lower() for v in _get_resp_opcoes('cronograma_responsavel', admin_id)] or ['empresa', 'terceiros', 'subempreitada']
    responsavel = (data.get('responsavel') or _resp_validos[0]).strip().lower()
    if responsavel not in _resp_validos:
        responsavel = _resp_validos[0]

    sub_mestre_id = data.get('subatividade_mestre_id')
    try:
        sub_mestre_id = int(sub_mestre_id) if sub_mestre_id else None
    except (ValueError, TypeError):
        sub_mestre_id = None
    if sub_mestre_id is not None:
        sub_obj = SubatividadeMestre.query.filter_by(
            id=sub_mestre_id, admin_id=admin_id, ativo=True
        ).first()
        if sub_obj is None:
            sub_mestre_id = None

    # Task #116 — servico_id é opcional. Aceita id explícito; senão tenta
    # resolver pelo nome da tarefa (case-insensitive). Se nada bater, a tarefa
    # é salva com servico_id=None (sem vínculo de serviço).
    raw_servico_id = data.get('servico_id')
    servico_id = None
    try:
        servico_id = int(raw_servico_id) if raw_servico_id else None
    except (ValueError, TypeError):
        servico_id = None
    if servico_id is not None:
        svc = Servico.query.filter_by(
            id=servico_id, admin_id=admin_id, ativo=True
        ).first()
        if not svc:
            servico_id = None
    if servico_id is None:
        # Fallback por nome (caso template/seed antigos)
        svc_nome = (data.get('servico_nome') or '').strip()
        if svc_nome:
            svc = (
                Servico.query
                .filter(
                    Servico.admin_id == admin_id,
                    Servico.ativo.is_(True),
                    db.func.lower(Servico.nome) == svc_nome.lower(),
                )
                .first()
            )
            if svc:
                servico_id = svc.id
    if servico_id is None:
        logger.info("[cronograma] Tarefa criada sem vínculo de serviço (servico_id=None é permitido)")

    # Task #62 — auto-criação de SubatividadeMestre por nome quando não veio explícito
    if sub_mestre_id is None:
        try:
            from services.auto_subatividade_cronograma import garantir_subatividade
            sub_obj, _criada = garantir_subatividade(nome, admin_id, servico_id)
            if sub_obj is not None:
                sub_mestre_id = sub_obj.id
        except Exception as _e_sub:
            logger.warning(f"[Task#62] auto-subatividade falhou: {_e_sub}")
    else:
        # Task #62 — consistência: tarefa.servico_id deve bater com a sub.servico_id
        sub_existente = SubatividadeMestre.query.filter_by(
            id=sub_mestre_id, admin_id=admin_id
        ).first()
        if sub_existente and sub_existente.servico_id and sub_existente.servico_id != servico_id:
            return jsonify({
                'status': 'error',
                'msg': (
                    f'Inconsistência: a subatividade pertence ao serviço '
                    f'#{sub_existente.servico_id}, mas a tarefa foi enviada com serviço #{servico_id}.'
                ),
            }), 400

    # Modo de apontamento escolhido (migration 220). Ausente ⇒ None, e a
    # dedução legada (`_modo_deduzido`) continua no comando — exatamente o
    # comportamento anterior à coluna.
    modo_apontamento, erro_modo = _parse_modo_apontamento(data)
    if erro_modo:
        return jsonify({'status': 'error', 'msg': erro_modo}), 400
    modo_apontamento = modo_apontamento or None

    # Default por obra: `regime_medicao == 'percentual'` significa que a obra
    # fatura pelo % físico apurado via RDO (models.py, coluna regime_medicao)
    # — exigir quantitativo por tarefa nessa obra é contraditório. Só vale
    # quando o usuário NÃO escolheu: escolha explícita sempre vence.
    # 'fixa' (o default do schema) deixa NULL e mantém a dedução legada, para
    # que nada mude nas obras existentes.
    if modo_apontamento is None and (obra.regime_medicao or '').lower() == 'percentual':
        modo_apontamento = 'percentual'

    tarefa = TarefaCronograma(
        obra_id=obra_id,
        tarefa_pai_id=tarefa_pai_id,
        predecessora_id=predecessora_id,
        ordem=nova_ordem,
        nome_tarefa=nome,
        duracao_dias=duracao,
        data_inicio=data_inicio,
        data_fim=data_fim,
        quantidade_total=float(data.get('quantidade_total') or 0) or None,
        unidade_medida=(data.get('unidade_medida') or '').strip() or None,
        modo_apontamento=modo_apontamento,
        subatividade_mestre_id=sub_mestre_id,
        servico_id=servico_id,
        percentual_concluido=0.0,
        responsavel=responsavel,
        admin_id=admin_id,
        is_cliente=cliente_mode,
    )
    db.session.add(tarefa)

    flag_on = _editor_v2_on()
    if not flag_on:
        # Caminho legado intocado + dual-write silencioso do vínculo TI/0.
        db.session.commit()
        logger.info(f"[OK] TarefaCronograma criada id={tarefa.id} obra_id={obra_id}")
        if predecessora_id:
            _dual_write_vinculo_legado(tarefa, admin_id)
        return jsonify({'status': 'ok', 'tarefa': _tarefa_to_dict(tarefa)}), 201

    # ── Editor v2 (flag ON) — plano C3 ──
    db.session.flush()  # garante tarefa.id para os vínculos
    if predecessora_id:
        # Modal legado: o predecessora_id da criação vira vínculo TI/0 (a
        # coluna gravada acima fica congelada — o motor lê só tarefa_vinculo).
        db.session.add(TarefaVinculo(
            admin_id=admin_id, obra_id=obra_id,
            predecessora_id=predecessora_id, sucessora_id=tarefa.id,
            tipo='TI', lag_dias=0))
    if (data.get('predecessoras_texto') or '').strip():
        _, linha_para_tarefa, _, ids_resumo = _mapas_vinculos(
            obra_id, admin_id, cliente_mode)
        try:
            vincs = parsear_predecessoras(
                str(data.get('predecessoras_texto') or ''),
                linha_para_tarefa,
                sucessora_id=tarefa.id,
                ids_resumo=ids_resumo,
            )
        except ErroParsePredecessora as exc:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(exc)}), 400
        # O texto vence o predecessora_id legado: substitui os vínculos
        # da sucessora (delete + insert).
        TarefaVinculo.query.filter_by(
            sucessora_id=tarefa.id, obra_id=obra_id, admin_id=admin_id
        ).delete(synchronize_session=False)
        for v in vincs:
            db.session.add(TarefaVinculo(
                admin_id=admin_id, obra_id=obra_id,
                predecessora_id=v.predecessora_id, sucessora_id=tarefa.id,
                tipo=v.tipo, lag_dias=v.lag_dias))

    # ── Fase 2 (Step B): inserir acima/abaixo de uma linha de referência ──
    # Campos ausentes ⇒ comportamento de sempre (anexa no fim). Só este
    # branch flag-ON conhece `ref_tarefa_id`/`posicao` — com a flag OFF o
    # caminho legado já retornou lá em cima e os campos são ignorados.
    ref_raw = data.get('ref_tarefa_id')
    if ref_raw not in (None, ''):
        try:
            ref_id = int(ref_raw)
        except (ValueError, TypeError):
            ref_id = None
        ref = None
        if ref_id:
            ref = TarefaCronograma.query.filter_by(
                id=ref_id, obra_id=obra_id, admin_id=admin_id,
                is_cliente=cliente_mode,
            ).filter(TarefaCronograma.ativa.is_(True)).first()
        if ref is None or ref.id == tarefa.id:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'msg': 'Tarefa de referência não encontrada nesta obra',
            }), 400
        posicao = str(data.get('posicao') or '').strip().lower()
        if posicao not in ('acima', 'abaixo', 'dentro'):
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'msg': "Posição inválida: use 'acima', 'abaixo' ou 'dentro'",
            }), 400

        _, _nivel_map, filhas_map = _estrutura_visual(
            obra_id, admin_id, cliente_mode)
        # A nova tarefa (já em sessão, anexada no fim) sai de onde caiu.
        atuais = filhas_map.get(tarefa.tarefa_pai_id or None, [])
        atuais[:] = [t for t in atuais if t.id != tarefa.id]

        if posicao == 'dentro':
            # Fase 6 — "Nova subtarefa dentro desta": a nova nasce FILHA da
            # referência (última), em vez de irmã. Poupa o inserir-e-recuar,
            # mas transforma a referência em resumo — então passa pelo MESMO
            # guard do indent, senão criar seria a porta dos fundos do recuar.
            erro_resumo = _guard_vira_resumo(
                ref, filhas_map, obra_id, admin_id, cliente_mode,
                sufixo=' de criar a subtarefa')
            if erro_resumo:
                db.session.rollback()
                return erro_resumo
            tarefa.tarefa_pai_id = ref.id
            filhas_map.setdefault(ref.id, []).append(tarefa)
        else:
            # 'acima'/'abaixo' — vira IRMÃ da referência, herda o pai dela.
            tarefa.tarefa_pai_id = ref.tarefa_pai_id
            irmas = filhas_map.setdefault(ref.tarefa_pai_id or None, [])
            pos_ref = next((i for i, t in enumerate(irmas) if t.id == ref.id),
                           len(irmas) - 1)
            # 'abaixo' = irmã seguinte: no DFS cai DEPOIS da subárvore inteira
            # da referência; 'acima' cai imediatamente antes dela.
            irmas.insert(pos_ref if posicao == 'acima' else pos_ref + 1, tarefa)

        resultado, erro = _aplicar_hierarquia(obra_id, admin_id, cliente_mode,
                                              filhas_map)
        if erro:
            return erro
        logger.info(f"[OK] TarefaCronograma criada id={tarefa.id} "
                    f"obra_id={obra_id} (editor v2, {posicao} de {ref.id})")
        return _resposta_grade(obra_id, admin_id, cliente_mode, tarefa,
                               resultado.tarefas_afetadas, status_http=201)

    try:
        resultado = recalcular_obra(obra_id, admin_id, cliente=cliente_mode,
                                    commit=False)
        db.session.commit()
    except ErroCiclo as exc:
        db.session.rollback()
        return jsonify({'status': 'error', 'msg': str(exc)}), 400

    # A06/B2.20 — FORA do try acima, e por um motivo concreto: lá dentro o
    # commit interno do replanejamento (utils/cronograma_engine) rodaria ANTES
    # do `db.session.rollback()`, e a criação que o ciclo mandou desfazer
    # ficaria gravada.
    _replanejar_pos_commit(obra_id, admin_id, cliente_mode)
    logger.info(f"[OK] TarefaCronograma criada id={tarefa.id} obra_id={obra_id} (editor v2)")
    vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode)
    _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)
    return jsonify({
        'status': 'ok',
        'tarefa': _tarefa_to_dict(tarefa, **_kw),
        'tarefas_afetadas': [_tarefa_to_dict(t, **_kw)
                             for t in resultado.tarefas_afetadas],
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# ATUALIZAR TAREFA (inline edit via AJAX)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>', methods=['PUT', 'PATCH'])
@login_required
@_com_undo('editar_tarefa')
def atualizar_tarefa(obra_id: int, tarefa_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).first_or_404()

    flag_on = _editor_v2_on()
    data = request.get_json(silent=True) or {}

    if 'nome_tarefa' in data:
        nome = str(data['nome_tarefa']).strip()
        if nome:
            tarefa.nome_tarefa = nome

    if 'duracao_dias' in data:
        try:
            tarefa.duracao_dias = max(1, int(data['duracao_dias']))
        except (ValueError, TypeError):
            pass

    if 'data_inicio' in data:
        d = _parse_date(data['data_inicio'])
        if d:
            # Editor v2: tarefa ancorada (iniciada) tem o início congelado —
            # o motor novo nunca mexe nas datas dela (plano C3/B3).
            if flag_on and tarefa.id in ids_tarefas_iniciadas(
                    obra_id, admin_id, cliente=cliente_mode):
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'msg': ('Tarefa já iniciada por apontamento de RDO — '
                            'o início não pode ser alterado'),
                }), 400
            tarefa.data_inicio = d

    if 'quantidade_total' in data:
        # Tarefa com histórico em percentual não vira quantitativa: os
        # próximos apontamentos viriam em unidades e o avanço passaria a
        # valer o da última linha, descartando o acumulado em %. Ver
        # `impedimento_para_cadastrar_quantitativo` para a medição.
        from utils.cronograma_engine import (
            impedimento_para_cadastrar_quantitativo)
        _impedimento = impedimento_para_cadastrar_quantitativo(
            tarefa, data['quantidade_total'], admin_id)
        if _impedimento:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': _impedimento}), 400
        try:
            tarefa.quantidade_total = float(data['quantidade_total']) or None
        except (ValueError, TypeError):
            tarefa.quantidade_total = None

    if 'unidade_medida' in data:
        tarefa.unidade_medida = str(data['unidade_medida']).strip() or None

    if 'modo_apontamento' in data:
        # '' significa "voltar ao automático" (grava NULL); valor válido
        # significa "o usuário escolheu". Ver _parse_modo_apontamento.
        novo_modo, erro_modo = _parse_modo_apontamento(
            data, tarefa_is_marco=bool(getattr(tarefa, 'is_marco', False)))
        if erro_modo:
            return jsonify({'status': 'error', 'msg': erro_modo}), 400
        tarefa.modo_apontamento = novo_modo or None

    if 'subatividade_mestre_id' in data:
        try:
            val = data['subatividade_mestre_id']
            parsed_id = int(val) if val else None
        except (ValueError, TypeError):
            parsed_id = None
        if parsed_id is not None:
            sub_obj = SubatividadeMestre.query.filter_by(
                id=parsed_id, admin_id=admin_id, ativo=True
            ).first()
            tarefa.subatividade_mestre_id = sub_obj.id if sub_obj else None
        else:
            tarefa.subatividade_mestre_id = None

    if 'servico_id' in data:
        try:
            svc_val = data['servico_id']
            svc_id = int(svc_val) if svc_val else None
        except (ValueError, TypeError):
            svc_id = None
        if svc_id is not None:
            svc_obj = Servico.query.filter_by(id=svc_id, admin_id=admin_id, ativo=True).first()
            tarefa.servico_id = svc_obj.id if svc_obj else None
        else:
            tarefa.servico_id = None

    # Consistency check (mirrors criar_tarefa): subatividade must belong to the declared serviço
    if 'subatividade_mestre_id' in data or 'servico_id' in data:
        new_sub_id = tarefa.subatividade_mestre_id
        new_svc_id = tarefa.servico_id
        if new_sub_id is not None and new_svc_id is not None:
            sub_check = SubatividadeMestre.query.filter_by(
                id=new_sub_id, admin_id=admin_id
            ).first()
            if sub_check and sub_check.servico_id and sub_check.servico_id != new_svc_id:
                return jsonify({
                    'status': 'error',
                    'msg': (
                        f'Inconsistência: a subatividade pertence ao serviço '
                        f'#{sub_check.servico_id}, mas a tarefa foi enviada com serviço #{new_svc_id}.'
                    ),
                }), 400

    if 'responsavel' in data:
        from services.dropdown_service import get_opcoes_valores as _get_resp_opcoes2
        _resp_ok = [v.lower() for v in _get_resp_opcoes2('cronograma_responsavel', admin_id)] or ['empresa', 'terceiros', 'subempreitada']
        resp = str(data['responsavel']).strip().lower()
        if resp in _resp_ok:
            tarefa.responsavel = resp

    if 'percentual_concluido' in data:
        try:
            tarefa.percentual_concluido = min(100.0, max(0.0, float(data['percentual_concluido'])))
        except (ValueError, TypeError):
            pass
        # Auto-sync data_entrega_real para tarefas de terceiros
        if (tarefa.responsavel or '').lower() == 'terceiros':
            from datetime import date as _date_today
            if tarefa.percentual_concluido >= 100.0 and not tarefa.data_entrega_real:
                tarefa.data_entrega_real = _date_today.today()
            elif tarefa.percentual_concluido < 100.0:
                tarefa.data_entrega_real = None

    if 'data_entrega_real' in data:
        d = _parse_date(data['data_entrega_real']) if data.get('data_entrega_real') else None
        tarefa.data_entrega_real = d

    # Editor v2 (flag ON): `predecessora_id` fica CONGELADO — a fonte de
    # verdade passa a ser `tarefa_vinculo` (campo `predecessoras_texto`
    # abaixo). Com a flag OFF o bloco legado roda intocado.
    if 'predecessora_id' in data and not flag_on:
        pred_val = data['predecessora_id']
        if pred_val in (None, '', '0', 0):
            tarefa.predecessora_id = None
        else:
            try:
                pred_id = int(pred_val)
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'msg': 'predecessora_id inválido'}), 400
            # Validar existência e pertencimento à obra/modo (igual a criar_tarefa)
            pred_tarefa = TarefaCronograma.query.filter_by(
                id=pred_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
            ).first()
            if not pred_tarefa:
                return jsonify({
                    'status': 'error',
                    'msg': f'Tarefa predecessora id={pred_id} não encontrada nesta obra.'
                }), 400
            if verificar_ciclo(tarefa_id, pred_id, admin_id):
                return jsonify({
                    'status': 'error',
                    'msg': 'Referência circular: A depende de B e B depende de A'
                }), 400
            tarefa.predecessora_id = pred_id

    if flag_on and 'predecessoras_texto' in data:
        # Formato Project ("12;15TT+1") sobre a numeração VISUAL da grade —
        # aplica diff em TarefaVinculo (delete + insert); `predecessora_id`
        # legado não é mais gravado (congelado).
        _, linha_para_tarefa, _, ids_resumo = _mapas_vinculos(
            obra_id, admin_id, cliente_mode)
        if tarefa.id in ids_resumo:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'msg': ('Tarefa-resumo não pode ter predecessoras — '
                        'vincule apenas tarefas-folha'),
            }), 400
        try:
            vincs = parsear_predecessoras(
                str(data.get('predecessoras_texto') or ''),
                linha_para_tarefa,
                sucessora_id=tarefa.id,
                ids_resumo=ids_resumo,
            )
        except ErroParsePredecessora as exc:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(exc)}), 400
        TarefaVinculo.query.filter_by(
            sucessora_id=tarefa.id, obra_id=obra_id, admin_id=admin_id
        ).delete(synchronize_session=False)
        for v in vincs:
            db.session.add(TarefaVinculo(
                admin_id=admin_id, obra_id=obra_id,
                predecessora_id=v.predecessora_id, sucessora_id=tarefa.id,
                tipo=v.tipo, lag_dias=v.lag_dias))

    if 'tarefa_pai_id' in data:
        pai_val = data['tarefa_pai_id']
        novo_pai_id = int(pai_val) if pai_val else None
        if novo_pai_id is not None:
            # Evitar ciclo hierárquico: percorrer a cadeia ascendente do novo pai
            # e garantir que tarefa_id não aparece como ancestral.
            visitados = set()
            cursor_id = novo_pai_id
            ciclo = False
            while cursor_id is not None:
                if cursor_id == tarefa_id:
                    ciclo = True
                    break
                if cursor_id in visitados:
                    break  # cadeia corrompida, não loop infinito
                visitados.add(cursor_id)
                anc = TarefaCronograma.query.filter_by(id=cursor_id, admin_id=admin_id).first()
                cursor_id = anc.tarefa_pai_id if anc else None
            if ciclo:
                return jsonify({
                    'status': 'error',
                    'msg': 'Hierarquia circular: uma tarefa não pode ser pai de seu próprio ancestral.',
                }), 400
        tarefa.tarefa_pai_id = novo_pai_id

    if 'ordem' in data:
        try:
            tarefa.ordem = int(data['ordem'])
        except (ValueError, TypeError):
            pass

    # Recalcular data_fim se data_inicio ou duração mudou
    cal = get_calendario(admin_id)
    if tarefa.data_inicio and tarefa.duracao_dias:
        tarefa.data_fim = calcular_data_fim(
            tarefa.data_inicio, tarefa.duracao_dias,
            cal.considerar_sabado, cal.considerar_domingo,
        )

    # Recálculo em cadeia apenas quando campos de agendamento foram alterados.
    # Se percentual_concluido foi passado explicitamente, reaplicar APÓS o recálculo
    # (recalcular_cronograma chama atualizar_percentual_tarefa que pode sobrescrevê-lo).
    _SCHEDULING_FIELDS = {'duracao_dias', 'predecessora_id', 'data_inicio'}
    perc_manual = None
    if 'percentual_concluido' in data:
        try:
            perc_manual = min(100.0, max(0.0, float(data['percentual_concluido'])))
        except (ValueError, TypeError):
            pass

    afetadas: list = []
    if flag_on:
        # Editor v2: motor novo (services/cronograma_scheduler) em commit
        # único — mutações + vínculos + diffs do recálculo entram juntos;
        # ErroCiclo desfaz TUDO (inclusive os vínculos recém-criados).
        precisa_recalc = bool(
            (_SCHEDULING_FIELDS | {'predecessoras_texto'}) & set(data.keys()))
        resultado = None
        try:
            if precisa_recalc:
                resultado = recalcular_obra(obra_id, admin_id,
                                            cliente=cliente_mode, commit=False)
            db.session.commit()
        except ErroCiclo as exc:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(exc)}), 400
        logger.info(f"[OK] TarefaCronograma atualizada id={tarefa_id} (editor v2)")
        if resultado is not None:
            afetadas = resultado.tarefas_afetadas
        if perc_manual is not None and precisa_recalc:
            tarefa.percentual_concluido = perc_manual
            db.session.commit()
        # A06/B2.19 — DEPOIS de reaplicar `perc_manual`, e só quando houve
        # recálculo de data. A ordem é o núcleo do item: antes daqui, com
        # `sincronizar=True`, o percentual que o usuário acabou de digitar seria
        # reescrito a partir do último apontamento. Renomear não paga a varredura.
        if precisa_recalc:
            _replanejar_pos_commit(obra_id, admin_id, cliente_mode)
    else:
        db.session.commit()
        logger.info(f"[OK] TarefaCronograma atualizada id={tarefa_id}")

        # Dual-write silencioso (plano C3): espelha o predecessora_id legado
        # em TarefaVinculo TI/0 para quando a flag ligar.
        if 'predecessora_id' in data:
            _dual_write_vinculo_legado(tarefa, admin_id)

        if _SCHEDULING_FIELDS & set(data.keys()):
            recalcular_cronograma(obra_id, admin_id, cliente=cliente_mode)
            # Re-aplicar o percentual manual caso o recálculo tenha sobrescrito
            if perc_manual is not None:
                tarefa.percentual_concluido = perc_manual
                db.session.commit()
            # A06/B2.19 — o gêmeo do ramo v2, mesma posição relativa: depois de
            # reaplicar `perc_manual`, dentro da guarda de campo de agendamento.
            _replanejar_pos_commit(obra_id, admin_id, cliente_mode)

    # Devolver tarefa atualizada + lista completa após recalc para redesenho do Gantt
    db.session.refresh(tarefa)
    todas = TarefaCronograma.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).filter(TarefaCronograma.ativa.is_(True)).order_by(
        TarefaCronograma.ordem, TarefaCronograma.id).all()
    if flag_on:
        vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode,
                                          tarefas=todas)
        _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)
        return jsonify({
            'status': 'ok',
            'tarefa': _tarefa_to_dict(tarefa, **_kw),
            'tarefas': [_tarefa_to_dict(t, **_kw) for t in todas],
            'tarefas_afetadas': [_tarefa_to_dict(t, **_kw) for t in afetadas],
        })
    return jsonify({
        'status': 'ok',
        'tarefa': _tarefa_to_dict(tarefa),
        'tarefas': [_tarefa_to_dict(t) for t in todas],
    })


# ─────────────────────────────────────────────────────────────────────────────
# EXCLUIR TAREFA
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>', methods=['DELETE'])
@login_required
@_com_undo('excluir_tarefa')
def excluir_tarefa(obra_id: int, tarefa_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).first_or_404()

    # Filhas: ao excluir um grupo intermediário, re-parentar os filhos para o
    # avô (tarefa_pai_id do grupo excluído), preservando a hierarquia.
    # Se o grupo excluído era raiz (sem pai), os filhos viram raiz também.
    novo_pai = tarefa.tarefa_pai_id  # None se grupo raiz, id do avô se subgrupo
    TarefaCronograma.query.filter_by(tarefa_pai_id=tarefa_id).update({'tarefa_pai_id': novo_pai})
    TarefaCronograma.query.filter_by(predecessora_id=tarefa_id).update({'predecessora_id': None})

    flag_on = _editor_v2_on()
    if flag_on:
        # ── Fase 3: exclusão LÓGICA (spec §6) ──
        # O hard delete levaria junto os apontamentos de RDO da tarefa e
        # impediria o desfazer de restaurá-los. Arquivando, a linha nunca sai
        # da tabela: desfazer é só `ativa=True`, e nenhum id ressuscita — os
        # apontamentos e itens de medição continuam apontando para ela.
        # Os vínculos, esses, morrem mesmo (o motor não pode enxergar ponta
        # arquivada); o par natural fica no payload e o desfazer os recria.
        tarefa.ativa = False
        tarefa.arquivada_em = datetime.utcnow()
        TarefaVinculo.query.filter(
            TarefaVinculo.obra_id == obra_id,
            TarefaVinculo.admin_id == admin_id,
            db.or_(TarefaVinculo.predecessora_id == tarefa_id,
                   TarefaVinculo.sucessora_id == tarefa_id),
        ).delete(synchronize_session=False)
        db.session.commit()
        logger.info(f"[OK] TarefaCronograma arquivada id={tarefa_id} "
                    f"cliente={cliente_mode} (editor v2)")
    else:
        db.session.delete(tarefa)
        db.session.commit()
        logger.info(f"[OK] TarefaCronograma excluída id={tarefa_id} cliente={cliente_mode}")

    # Editor v2: o recálculo reflui as ex-sucessoras. Excluir não cria ciclo —
    # o guard é só defensivo (dado sujo pré-existente não pode derrubar a
    # exclusão).
    afetadas: list = []
    recalculou = False
    if flag_on:
        try:
            resultado = recalcular_obra(obra_id, admin_id, cliente=cliente_mode)
            afetadas = resultado.tarefas_afetadas
            recalculou = True
        except ErroCiclo as exc:
            db.session.rollback()
            logger.warning('[editor-v2] recálculo pós-exclusão pulado '
                           '(ciclo pré-existente na obra %s): %s', obra_id, exc)

    # A06/B2.20 — guardado pelo sinalizador, e não incondicional: este `except`
    # é o único do módulo que faz rollback e **segue** (não retorna). Replanejar
    # depois de um recálculo abortado gravaria uma curva planejada derivada de
    # datas que o rollback acabou de descartar.
    if recalculou:
        _replanejar_pos_commit(obra_id, admin_id, cliente_mode)

    # Devolver lista atualizada para o frontend re-renderizar hierarquia
    todas = TarefaCronograma.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).filter(TarefaCronograma.ativa.is_(True)).order_by(
        TarefaCronograma.ordem, TarefaCronograma.id).all()
    if flag_on:
        vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode,
                                          tarefas=todas)
        _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)
        return jsonify({
            'status': 'ok',
            'tarefas': [_tarefa_to_dict(t, **_kw) for t in todas],
            'tarefas_afetadas': [_tarefa_to_dict(t, **_kw) for t in afetadas],
        })
    return jsonify({'status': 'ok', 'tarefas': [_tarefa_to_dict(t) for t in todas]})


# ─────────────────────────────────────────────────────────────────────────────
# RECALCULAR TODAS AS DATAS
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/recalcular', methods=['POST'])
@login_required
def recalcular(obra_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403

    admin_id = _admin_id()
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
    cliente_mode = _modo_cliente()
    Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    # Editor v2 (flag ON): motor novo. Flag OFF: engine antigo, intocado.
    flag_on = _editor_v2_on()
    afetadas: list = []
    if flag_on:
        try:
            resultado = recalcular_obra(obra_id, admin_id, cliente=cliente_mode)
            afetadas = resultado.tarefas_afetadas
        except ErroCiclo as exc:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(exc)}), 400
    else:
        ok = recalcular_cronograma(obra_id, admin_id, cliente=cliente_mode)
        if not ok:
            return jsonify({'status': 'error', 'msg': 'Erro ao recalcular cronograma'}), 500

    # A06/B2.20 — o **gatilho manual**: é a única rota que conserta uma curva
    # planejada envelhecida sem exigir uma edição. Depois do if/else, e não
    # dentro do `if flag_on`: os dois ramos só chegam aqui em caso de sucesso
    # (o v2 retorna 400 no ErroCiclo, o legado retorna 500 quando `ok` é falso),
    # então uma linha cobre os dois — inclusive o parque ainda não migrado.
    _replanejar_pos_commit(obra_id, admin_id, cliente_mode)

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem)
        .all()
    )
    if flag_on:
        vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode,
                                          tarefas=tarefas)
        _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)
        return jsonify({
            'status': 'ok',
            'tarefas': [_tarefa_to_dict(t, **_kw) for t in tarefas],
            'tarefas_afetadas': [_tarefa_to_dict(t, **_kw) for t in afetadas],
        })
    return jsonify({'status': 'ok', 'tarefas': [_tarefa_to_dict(t) for t in tarefas]})


# ─────────────────────────────────────────────────────────────────────────────
# VÍNCULOS TIPADOS (editor v2) — CRUD explícito (plano C4)
# ─────────────────────────────────────────────────────────────────────────────

def _vinculo_to_dict(v: TarefaVinculo) -> dict:
    return {
        'id': v.id,
        'obra_id': v.obra_id,
        'predecessora_id': v.predecessora_id,
        'sucessora_id': v.sucessora_id,
        'tipo': v.tipo,
        'lag_dias': v.lag_dias,
    }


def _guard_rotas_vinculo(obra_id: int):
    """Guards comuns das rotas de vínculo — mesmo padrão das rotas irmãs
    (`atualizar_tarefa`): V2 → flag → tenant/obra → escopo de edição.

    Com a flag `cronograma_editor_v2` DESLIGADA as rotas "não existem"
    (404 opaco), como qualquer URL desconhecida — nada vaza para tenants
    fora do rollout. Devolve resposta de erro ou None (pode seguir).
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 apenas'}), 403
    if not _editor_v2_on():
        return jsonify({'status': 'error', 'msg': 'Não encontrado'}), 404
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada'}), 404
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
    return None


def _espelhar_no_campo_legado(obra_id: int, admin_id: int, sucessora_id: int):
    """Mantém `TarefaCronograma.predecessora_id` refletindo o vínculo, quando
    o campo legado consegue representá-lo.

    Achado P2 do code review de 27/07. A dupla escrita entre as duas
    representações só existia numa direção: com a flag `cronograma_editor_v2`
    DESLIGADA, gravar `predecessora_id` também criava um `TarefaVinculo` TI/0
    (`sincronizar_vinculos_de_predecessora_id`). Com a flag LIGADA, o CRUD
    novo gravava só a tabela nova — e o campo legado, que é o que o motor
    antigo lê, ficava NULL.

    Consequência: toda dependência criada com o editor v2 ligado sumia no
    rollback. 🔬 27/07 (dev): 517 de 722 vínculos (72%) não tinham reflexo no
    campo legado; 490 deles seriam representáveis.

    ⚠️ **O espelho é PARCIAL por natureza, e isso não é conserto de código.**
    `predecessora_id` guarda UMA predecessora, sempre TI com lag 0; a tabela
    nova guarda N, com tipo e lag. Uma tarefa com 3 predecessoras, ou com um
    vínculo II/TT/IT, ou com lag ≠ 0, **não cabe** no campo legado. Nesses
    casos o campo fica NULL de propósito — melhor perder a dependência no
    rollback do que reintroduzi-la com o tipo errado. O runbook
    `docs/cronograma-editor-v2-rollout.md` diz exatamente o que sobrevive.
    """
    vinculos = TarefaVinculo.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, sucessora_id=sucessora_id).all()
    tarefa = TarefaCronograma.query.filter_by(
        id=sucessora_id, obra_id=obra_id, admin_id=admin_id).first()
    if tarefa is None:
        return
    representaveis = [v for v in vinculos
                      if v.tipo == 'TI' and not (v.lag_dias or 0)]
    tarefa.predecessora_id = (representaveis[0].predecessora_id
                              if len(vinculos) == 1 and representaveis
                              else None)


def _recalc_e_resposta_vinculo(obra_id: int, admin_id: int, cliente_mode: bool,
                               vinculo: TarefaVinculo | None, status_http: int = 200):
    """Recalcula (motor novo, commit único) e monta a resposta padrão das
    rotas de vínculo: `{status, vinculo?, tarefas_afetadas}`. ErroCiclo →
    rollback (desfaz o vínculo pendente) + 400 com a mensagem pt-BR."""
    try:
        resultado = recalcular_obra(obra_id, admin_id, cliente=cliente_mode,
                                    commit=False)
        db.session.commit()
    except ErroCiclo as exc:
        db.session.rollback()
        return jsonify({'status': 'error', 'msg': str(exc)}), 400

    # A06/B2.20 — ponto único das três rotas de vínculo (criar/atualizar/
    # excluir). ANTES do `_mapas_vinculos`, não depois: se o replanejamento
    # falhar e rolar back, a serialização re-consulta o banco em vez de ler
    # objetos ORM expirados pelo rollback.
    _replanejar_pos_commit(obra_id, admin_id, cliente_mode)
    vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode)
    _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)
    corpo = {
        'status': 'ok',
        'tarefas_afetadas': [_tarefa_to_dict(t, **_kw)
                             for t in resultado.tarefas_afetadas],
    }
    if vinculo is not None:
        corpo['vinculo'] = _vinculo_to_dict(vinculo)
    return jsonify(corpo), status_http


@cronograma_bp.route('/obra/<int:obra_id>/vinculo', methods=['POST'])
@login_required
@_com_undo('criar_vinculo')
def criar_vinculo(obra_id: int):
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()

    data = request.get_json(silent=True) or {}
    try:
        pred_id = int(data.get('predecessora_id') or 0)
        suc_id = int(data.get('sucessora_id') or 0)
    except (ValueError, TypeError):
        return jsonify({'status': 'error',
                        'msg': 'predecessora_id e sucessora_id inválidos'}), 400
    if not pred_id or not suc_id:
        return jsonify({'status': 'error',
                        'msg': 'predecessora_id e sucessora_id são obrigatórios'}), 400
    if pred_id == suc_id:
        return jsonify({'status': 'error',
                        'msg': 'Uma tarefa não pode ser predecessora dela mesma'}), 400

    tipo = str(data.get('tipo') or 'TI').strip().upper()
    if tipo not in TIPOS_VINCULO:
        return jsonify({'status': 'error',
                        'msg': f"Tipo de vínculo inválido: '{tipo}' "
                               '(use TI, II, TT ou IT)'}), 400
    try:
        lag_dias = int(data.get('lag_dias') or 0)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'msg': 'lag_dias inválido'}), 400

    # Mesma obra/tenant/modo + ambas folhas — uma query (mapas da grade).
    _, _, tarefa_para_linha, ids_resumo = _mapas_vinculos(
        obra_id, admin_id, cliente_mode)
    for tid in (pred_id, suc_id):
        if tid not in tarefa_para_linha:
            return jsonify({'status': 'error',
                            'msg': f'Tarefa id={tid} não encontrada nesta obra.'}), 400
        if tid in ids_resumo:
            return jsonify({'status': 'error',
                            'msg': f'Tarefa id={tid} é uma tarefa-resumo — '
                                   'vincule apenas tarefas-folha'}), 400

    ja_existe = TarefaVinculo.query.filter_by(
        obra_id=obra_id, admin_id=admin_id,
        predecessora_id=pred_id, sucessora_id=suc_id,
    ).first()
    if ja_existe:
        return jsonify({'status': 'error',
                        'msg': 'Vínculo entre essas tarefas já existe'}), 400

    vinculo = TarefaVinculo(
        admin_id=admin_id, obra_id=obra_id,
        predecessora_id=pred_id, sucessora_id=suc_id,
        tipo=tipo, lag_dias=lag_dias,
    )
    db.session.add(vinculo)
    _espelhar_no_campo_legado(obra_id, admin_id, suc_id)
    # Ciclo é detectado ANTES do commit: recalcular_obra levanta ErroCiclo e
    # o rollback descarta o vínculo pendente.
    return _recalc_e_resposta_vinculo(obra_id, admin_id, cliente_mode,
                                      vinculo, status_http=201)


@cronograma_bp.route('/obra/<int:obra_id>/vinculo/<int:vid>', methods=['PUT', 'PATCH'])
@login_required
@_com_undo('editar_vinculo')
def atualizar_vinculo(obra_id: int, vid: int):
    """Edita tipo/lag de um vínculo existente (endpoints não mudam aqui —
    para religar tarefas, exclua e crie outro vínculo)."""
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()

    vinculo = TarefaVinculo.query.filter_by(
        id=vid, obra_id=obra_id, admin_id=admin_id).first()
    if not vinculo:
        return jsonify({'status': 'error', 'msg': 'Vínculo não encontrado'}), 404

    data = request.get_json(silent=True) or {}
    if 'tipo' in data:
        tipo = str(data.get('tipo') or '').strip().upper()
        if tipo not in TIPOS_VINCULO:
            return jsonify({'status': 'error',
                            'msg': f"Tipo de vínculo inválido: '{tipo}' "
                                   '(use TI, II, TT ou IT)'}), 400
        vinculo.tipo = tipo
    if 'lag_dias' in data:
        try:
            vinculo.lag_dias = int(data.get('lag_dias') or 0)
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'msg': 'lag_dias inválido'}), 400

    return _recalc_e_resposta_vinculo(obra_id, admin_id, cliente_mode, vinculo)


@cronograma_bp.route('/obra/<int:obra_id>/vinculo/<int:vid>', methods=['DELETE'])
@login_required
@_com_undo('excluir_vinculo')
def excluir_vinculo(obra_id: int, vid: int):
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()

    vinculo = TarefaVinculo.query.filter_by(
        id=vid, obra_id=obra_id, admin_id=admin_id).first()
    if not vinculo:
        return jsonify({'status': 'error', 'msg': 'Vínculo não encontrado'}), 404

    sucessora_id = vinculo.sucessora_id
    db.session.delete(vinculo)
    db.session.flush()
    _espelhar_no_campo_legado(obra_id, admin_id, sucessora_id)
    return _recalc_e_resposta_vinculo(obra_id, admin_id, cliente_mode, None)


# ─────────────────────────────────────────────────────────────────────────────
# HIERARQUIA DA GRADE (editor v2, Fase 2) — recuar/desrecuar (plano Step A)
# ─────────────────────────────────────────────────────────────────────────────

def _estrutura_visual(obra_id: int, admin_id: int, cliente_mode: bool):
    """Fase 2 — estrutura visual da grade em UMA query de tarefas.

    Devolve `(ordenadas, nivel_map, filhas_map)`:
      * `ordenadas` — tarefas na ordem VISUAL (DFS de `ordenar_arvore_visual`,
        a MESMA numeração da grade e do parser de predecessoras);
      * `nivel_map` — task_id → profundidade (0 = raiz);
      * `filhas_map` — pai_id (None = raiz) → filhas na ordem entre irmãs
        (`ORDER BY ordem, id`, como a grade).

    O frontend envia SÓ a ação (recuar/desrecuar/inserir); a fonte de verdade
    da estrutura é sempre o servidor.
    """
    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem, TarefaCronograma.id)
        .all()
    )
    ordenadas, nivel_map = ordenar_arvore_visual(tarefas, com_nivel=True)
    filhas_map: dict[int | None, list] = {}
    for t in tarefas:
        filhas_map.setdefault(t.tarefa_pai_id or None, []).append(t)
    return ordenadas, nivel_map, filhas_map


def _ciclo_hierarquico(novo_pai_id: int | None, tarefa_id: int,
                       por_id: dict) -> bool:
    """Check ascendente de ciclo hierárquico (defensivo — mesma lógica do
    bloco `tarefa_pai_id` de `atualizar_tarefa`): True quando `tarefa_id`
    aparece na cadeia de ancestrais do novo pai."""
    visitados: set[int] = set()
    cursor = novo_pai_id
    while cursor is not None:
        if cursor == tarefa_id:
            return True
        if cursor in visitados:
            break  # cadeia corrompida, não loop infinito
        visitados.add(cursor)
        anc = por_id.get(cursor)
        cursor = anc.tarefa_pai_id if anc else None
    return False


def _guard_vira_resumo(novo_pai, filhas_map: dict, obra_id: int,
                       admin_id: int, cliente_mode: bool,
                       sufixo: str = ''):
    """Fase 6 — recusa transformar em resumo uma folha que não pode virar uma.

    Extraído do corpo de `recuar_tarefa` (era inline): ganhar uma filha é a
    MESMA operação, venha do indent, do arrasto (`/mover`) ou do
    `posicao='dentro'`, e as três precisam recusar pelos mesmos motivos —
    senão o arrasto viraria a porta dos fundos para o que o indent barra.

    Só se aplica quando `novo_pai` ainda é FOLHA: quem já é resumo ganha mais
    uma filha sem consequência. Devolve a resposta 400 pronta ou None.

    `sufixo` completa a frase do erro de vínculo com o verbo de quem chamou
    ("… antes de recuar"); o texto de `recuar` é o que
    `tests/test_cronograma_grade_api.py` trava desde a Fase 2.
    """
    if filhas_map.get(novo_pai.id):
        return None  # já é resumo — nada muda de natureza

    tem_vinculo = db.session.query(TarefaVinculo.id).filter(
        TarefaVinculo.obra_id == obra_id,
        TarefaVinculo.admin_id == admin_id,
        db.or_(TarefaVinculo.predecessora_id == novo_pai.id,
               TarefaVinculo.sucessora_id == novo_pai.id),
    ).first() is not None
    if tem_vinculo:
        return jsonify({
            'status': 'error',
            'msg': (f'A tarefa "{novo_pai.nome_tarefa}" tem vínculos de '
                    'predecessora/sucessora e viraria uma tarefa-resumo — '
                    f'remova os vínculos dela antes{sufixo}'),
        }), 400

    if novo_pai.id in ids_tarefas_iniciadas(obra_id, admin_id,
                                            cliente=cliente_mode):
        return jsonify({
            'status': 'error',
            'msg': (f'A tarefa "{novo_pai.nome_tarefa}" já foi iniciada '
                    'e não pode virar tarefa-resumo'),
        }), 400
    return None


def _aplicar_hierarquia(obra_id: int, admin_id: int, cliente_mode: bool,
                        filhas_map: dict):
    """Fase 2 — persistência comum de recuar/desrecuar/inserir-posicionado.

    Recebe `filhas_map` JÁ com a mudança aplicada (`tarefa_pai_id` mutado nos
    objetos ORM + listas de irmãs reposicionadas) e:
      1. reconstrói a lista visual alvo (o MESMO DFS de
         `ordenar_arvore_visual`);
      2. renumera `ordem = idx` para TODAS as tarefas do modo — a estratégia
         flat do `/reordenar`, para nunca colidir com o drag & drop;
      3. `flush()` + `recalcular_obra(commit=False)` + commit ÚNICO.

    Devolve `(resultado, erro)`: com `ErroCiclo` o rollback desfaz TUDO
    (re-parent + renumeração) e `erro` é a resposta 400 pronta; senão
    `resultado` carrega as `tarefas_afetadas` do recálculo.
    """
    ordenadas: list = []

    def _dfs(node) -> None:
        ordenadas.append(node)
        for filha in filhas_map.get(node.id, []):
            _dfs(filha)

    for raiz in filhas_map.get(None, []):
        _dfs(raiz)

    for idx, t in enumerate(ordenadas):
        t.ordem = idx
    try:
        db.session.flush()
        resultado = recalcular_obra(obra_id, admin_id, cliente=cliente_mode,
                                    commit=False)
        db.session.commit()
    except ErroCiclo as exc:
        db.session.rollback()
        return None, (jsonify({'status': 'error', 'msg': str(exc)}), 400)
    # A06/B2.20 — duas linhas que cobrem QUATRO rotas (recuar, desrecuar,
    # mover e criar-posicionado): mudar hierarquia recalcula datas, e a curva
    # planejada dos apontamentos já gravados tem de acompanhar. FORA do try:
    # com ciclo, o rollback acima já desfez tudo e não há o que replanejar.
    _replanejar_pos_commit(obra_id, admin_id, cliente_mode)
    return resultado, None


def _resposta_grade(obra_id: int, admin_id: int, cliente_mode: bool,
                    tarefa: TarefaCronograma, afetadas: list,
                    status_http: int = 200):
    """Resposta padrão das rotas de hierarquia (plano A3) — o shape das rotas
    irmãs + `nivel`:

        {status:'ok', tarefa, tarefas (ordem visual completa), tarefas_afetadas}

    Serializa DEPOIS do commit com `_mapas_vinculos` — a numeração visual
    muda com a hierarquia e `predecessoras_texto` precisa sair fresco.
    `nivel` é injetado pós-serialização (`d['nivel'] = nivel_map...`).
    """
    todas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem, TarefaCronograma.id)
        .all()
    )
    vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode,
                                      tarefas=todas)
    ordenadas, nivel_map = ordenar_arvore_visual(todas, com_nivel=True)
    _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)

    def _com_nivel(t: TarefaCronograma) -> dict:
        d = _tarefa_to_dict(t, **_kw)
        d['nivel'] = nivel_map.get(t.id, 0)
        return d

    return jsonify({
        'status': 'ok',
        'tarefa': _com_nivel(tarefa),
        'tarefas': [_com_nivel(t) for t in ordenadas],
        'tarefas_afetadas': [_com_nivel(t) for t in afetadas],
    }), status_http


@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>/recuar',
                     methods=['POST'])
@login_required
@_com_undo('recuar_tarefa')
def recuar_tarefa(obra_id: int, tarefa_id: int):
    """Fase 2 — indent (semântica Project): o novo pai é a irmã ANTERIOR
    (tarefa mais próxima ACIMA na ordem visual com o mesmo `tarefa_pai_id`);
    X entra como ÚLTIMA filha, levando a própria subárvore junto.

    Rejeita com 400 quando não há irmã anterior, quando o novo pai é folha
    com vínculos (viraria resumo — a Fase 1 nunca muta vínculos em silêncio;
    auto-remover seria destrutivo antes do undo da Fase 3) ou folha já
    iniciada (âncora de apontamento não pode virar resumo).
    """
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).filter(TarefaCronograma.ativa.is_(True)).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404

    ordenadas, _nivel_map, filhas_map = _estrutura_visual(
        obra_id, admin_id, cliente_mode)
    irmas = filhas_map.get(tarefa.tarefa_pai_id or None, [])
    pos = next((i for i, t in enumerate(irmas) if t.id == tarefa.id), None)
    if not pos:  # None (dado sujo) ou 0 (primeira do nível)
        return jsonify({
            'status': 'error',
            'msg': ('Não é possível recuar: não há tarefa acima no mesmo '
                    'nível para ser o novo grupo'),
        }), 400
    novo_pai = irmas[pos - 1]

    # P é folha e VIRARIA resumo — decisão crítica do plano: rejeitar.
    # (Fase 6: o mesmo guard serve `/mover` e `posicao='dentro'`.)
    erro = _guard_vira_resumo(novo_pai, filhas_map, obra_id, admin_id,
                              cliente_mode, sufixo=' de recuar')
    if erro:
        return erro

    # Defesa: a irmã anterior nunca é descendente de X, mas o check ascendente
    # fica (mesmo padrão de `atualizar_tarefa`) contra dado sujo.
    por_id = {t.id: t for t in ordenadas}
    if _ciclo_hierarquico(novo_pai.id, tarefa.id, por_id):
        return jsonify({
            'status': 'error',
            'msg': 'Hierarquia circular: uma tarefa não pode ser pai de seu próprio ancestral.',
        }), 400

    irmas.pop(pos)
    tarefa.tarefa_pai_id = novo_pai.id
    filhas_map.setdefault(novo_pai.id, []).append(tarefa)

    resultado, erro = _aplicar_hierarquia(obra_id, admin_id, cliente_mode,
                                          filhas_map)
    if erro:
        return erro
    logger.info(f"[OK] Tarefa recuada id={tarefa_id} novo_pai={novo_pai.id} "
                f"obra={obra_id} (editor v2)")
    return _resposta_grade(obra_id, admin_id, cliente_mode, tarefa,
                           resultado.tarefas_afetadas)


@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>/desrecuar',
                     methods=['POST'])
@login_required
@_com_undo('desrecuar_tarefa')
def desrecuar_tarefa(obra_id: int, tarefa_id: int):
    """Fase 2 — outdent: X (com a subárvore) sobe para o nível do pai antigo
    e vira a PRÓXIMA irmã dele, logo após a subárvore inteira dele.

    Desvio deliberado do Project puro: as irmãs SEGUINTES de X permanecem no
    pai antigo (não são re-parentadas sob X) — a operação fica local e
    reversível por um recuar. O pai antigo que ficar sem filhas vira folha
    naturalmente (datas do último roll-up até o próximo recálculo); ele volta
    em `tarefas` para o front atualizar as classes.
    """
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).filter(TarefaCronograma.ativa.is_(True)).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404
    if tarefa.tarefa_pai_id is None:
        return jsonify({
            'status': 'error',
            'msg': 'A tarefa já está no nível raiz — não é possível desrecuar',
        }), 400

    ordenadas, _nivel_map, filhas_map = _estrutura_visual(
        obra_id, admin_id, cliente_mode)
    por_id = {t.id: t for t in ordenadas}
    pai = por_id.get(tarefa.tarefa_pai_id)
    if pai is None:
        # Pai fora da grade (inativo/dado sujo) — nada seguro a fazer.
        return jsonify({
            'status': 'error',
            'msg': 'Hierarquia inconsistente — recarregue o cronograma',
        }), 400
    avo_id = pai.tarefa_pai_id or None

    # Defesa (mesmo padrão de `atualizar_tarefa`): o avô é ancestral de X,
    # nunca descendente — o check só dispara com dado sujo.
    if _ciclo_hierarquico(avo_id, tarefa.id, por_id):
        return jsonify({
            'status': 'error',
            'msg': 'Hierarquia circular: uma tarefa não pode ser pai de seu próprio ancestral.',
        }), 400

    filhas_pai = filhas_map.get(pai.id, [])
    filhas_pai[:] = [t for t in filhas_pai if t.id != tarefa.id]
    tarefa.tarefa_pai_id = avo_id
    irmas_avo = filhas_map.setdefault(avo_id, [])
    pos_pai = next((i for i, t in enumerate(irmas_avo) if t.id == pai.id),
                   len(irmas_avo) - 1)
    # Irmã seguinte do pai antigo: no DFS isso cai DEPOIS da subárvore
    # inteira dele (que já não contém X).
    irmas_avo.insert(pos_pai + 1, tarefa)

    resultado, erro = _aplicar_hierarquia(obra_id, admin_id, cliente_mode,
                                          filhas_map)
    if erro:
        return erro
    logger.info(f"[OK] Tarefa desrecuada id={tarefa_id} novo_pai={avo_id} "
                f"obra={obra_id} (editor v2)")
    return _resposta_grade(obra_id, admin_id, cliente_mode, tarefa,
                           resultado.tarefas_afetadas)


@cronograma_bp.route('/obra/<int:obra_id>/tarefa/<int:tarefa_id>/mover',
                     methods=['POST'])
@login_required
@_com_undo('mover_tarefa')
def mover_tarefa(obra_id: int, tarefa_id: int):
    """Fase 6 — re-parent explícito: X (com a subárvore) vira a ÚLTIMA filha
    de `novo_pai_id`. Corpo: `{"novo_pai_id": <int|null>}`; `null` promove X
    para a raiz, como última irmã do nível.

    É o backend do arrastar-e-soltar SOBRE uma linha. Irmã de
    `recuar`/`desrecuar` em tudo — mesmos guards, mesma persistência
    (`_aplicar_hierarquia`), mesma resposta (`_resposta_grade`), mesmo undo —
    e existe separada porque aquelas duas são RELATIVAS (irmã anterior, avô)
    enquanto esta recebe o destino explícito que o mouse escolheu.

    Deliberadamente NÃO reaproveita o `tarefa_pai_id` de `atualizar_tarefa`
    (PUT): aquele bloco só checa ciclo, não aplica os guards de resumo nem
    renumera `ordem`. Arrastar entraria por uma porta mais frouxa que o
    indent, exatamente o que a Fase 2 decidiu barrar.
    """
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    tarefa = TarefaCronograma.query.filter_by(
        id=tarefa_id, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).filter(TarefaCronograma.ativa.is_(True)).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404

    data = request.get_json(silent=True) or {}
    pai_raw = data.get('novo_pai_id')
    novo_pai_id = None
    if pai_raw not in (None, '', 0, '0'):
        try:
            novo_pai_id = int(pai_raw)
        except (TypeError, ValueError):
            return jsonify({'status': 'error',
                            'msg': 'novo_pai_id inválido'}), 400
    if novo_pai_id == tarefa.id:
        return jsonify({'status': 'error',
                        'msg': 'Uma tarefa não pode ser filha de si mesma'}), 400

    ordenadas, _nivel_map, filhas_map = _estrutura_visual(
        obra_id, admin_id, cliente_mode)
    por_id = {t.id: t for t in ordenadas}

    novo_pai = None
    if novo_pai_id is not None:
        novo_pai = por_id.get(novo_pai_id)
        if novo_pai is None:
            # Mesmo 404 opaco das irmãs: destino fora do alcance não vaza.
            return jsonify({'status': 'error',
                            'msg': 'Tarefa não encontrada'}), 404

    # Soltar um pai dentro do próprio neto — aqui o check é o caso REAL, não
    # a defesa contra dado sujo que ele é em recuar/desrecuar.
    if _ciclo_hierarquico(novo_pai_id, tarefa.id, por_id):
        return jsonify({
            'status': 'error',
            'msg': 'Hierarquia circular: uma tarefa não pode ser pai de seu próprio ancestral.',
        }), 400

    if tarefa.tarefa_pai_id == novo_pai_id:
        # Já é filha desse pai: nada a fazer. Sem no-op o `_aplicar_hierarquia`
        # renumeraria e o undo empilharia uma ação vazia.
        return _resposta_grade(obra_id, admin_id, cliente_mode, tarefa, [])

    if novo_pai is not None:
        erro = _guard_vira_resumo(novo_pai, filhas_map, obra_id, admin_id,
                                  cliente_mode, sufixo=' de mover para dentro dela')
        if erro:
            return erro

    antigas = filhas_map.get(tarefa.tarefa_pai_id or None, [])
    antigas[:] = [t for t in antigas if t.id != tarefa.id]
    tarefa.tarefa_pai_id = novo_pai_id
    filhas_map.setdefault(novo_pai_id, []).append(tarefa)

    resultado, erro = _aplicar_hierarquia(obra_id, admin_id, cliente_mode,
                                          filhas_map)
    if erro:
        return erro
    logger.info(f"[OK] Tarefa movida id={tarefa_id} novo_pai={novo_pai_id} "
                f"obra={obra_id} (editor v2)")
    return _resposta_grade(obra_id, admin_id, cliente_mode, tarefa,
                           resultado.tarefas_afetadas)


# ─────────────────────────────────────────────────────────────────────────────
# DESFAZER / REFAZER (editor v2, Fase 3) — plano Step C2
# ─────────────────────────────────────────────────────────────────────────────

def _resposta_undo(obra_id: int, admin_id: int, cliente_mode: bool,
                   acao, afetadas: list):
    """Resposta de desfazer/refazer: o shape das rotas irmãs (com `nivel`)
    mais o estado da pilha, que a toolbar usa para habilitar os botões.

    `tarefa` vem `null` de propósito — desfazer não tem uma linha "foco";
    o front aplica `tarefas` inteiro.
    """
    todas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem, TarefaCronograma.id)
        .all()
    )
    vmap, _, t2l, _ = _mapas_vinculos(obra_id, admin_id, cliente_mode,
                                      tarefas=todas)
    ordenadas, nivel_map = ordenar_arvore_visual(todas, com_nivel=True)
    _kw = dict(vinculos_por_sucessora=vmap, tarefa_para_linha=t2l)

    def _com_nivel(t: TarefaCronograma) -> dict:
        d = _tarefa_to_dict(t, **_kw)
        d['nivel'] = nivel_map.get(t.id, 0)
        return d

    # Só as afetadas que continuam visíveis: uma tarefa que o desfazer
    # arquivou sai da grade pelo `tarefas` completo, não por `tarefas_afetadas`.
    visiveis = {t.id for t in todas}
    pode_desfazer, pode_refazer = estado_pilha(obra_id, current_user.id,
                                               cliente_mode)
    return jsonify({
        'status': 'ok',
        'tarefa': None,
        'tarefas': [_com_nivel(t) for t in ordenadas],
        'tarefas_afetadas': [_com_nivel(t) for t in afetadas
                             if t.id in visiveis],
        'tipo_acao': acao.tipo_acao,
        'pode_desfazer': pode_desfazer,
        'pode_refazer': pode_refazer,
    })


@cronograma_bp.route('/obra/<int:obra_id>/desfazer', methods=['POST'])
@login_required
def desfazer_acao(obra_id: int):
    """Fase 3 — desfaz a última ação do usuário nesta obra (e neste modo),
    com toda a cascata que ela provocou.

    Não é decorada com `_com_undo`: desfazer não é uma ação nova, ela move
    o ponteiro da pilha (`desfeita=True`) para o refazer poder reaplicá-la.
    """
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    acao, afetadas = undo_desfazer(obra_id, admin_id, current_user.id,
                                   cliente_mode)
    if acao is None:
        return jsonify({'status': 'error', 'msg': MSG_NADA_DESFAZER}), 400
    logger.info(f"[OK] Ação desfeita id={acao.id} tipo={acao.tipo_acao} "
                f"obra={obra_id} usuario={current_user.id} (editor v2)")
    return _resposta_undo(obra_id, admin_id, cliente_mode, acao, afetadas)


@cronograma_bp.route('/obra/<int:obra_id>/refazer', methods=['POST'])
@login_required
def refazer_acao(obra_id: int):
    """Fase 3 — reaplica a ação desfeita mais antiga (o topo da pilha de
    refazer). Uma ação NOVA descarta o refazer pendente — quem faz isso é
    `registrar_acao`, não esta rota."""
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    acao, afetadas = undo_refazer(obra_id, admin_id, current_user.id,
                                  cliente_mode)
    if acao is None:
        return jsonify({'status': 'error', 'msg': MSG_NADA_REFAZER}), 400
    logger.info(f"[OK] Ação refeita id={acao.id} tipo={acao.tipo_acao} "
                f"obra={obra_id} usuario={current_user.id} (editor v2)")
    return _resposta_undo(obra_id, admin_id, cliente_mode, acao, afetadas)


# ─────────────────────────────────────────────────────────────────────────────
# LINHA DE BASE (editor v2, Fase 4) — plano Step B
# ─────────────────────────────────────────────────────────────────────────────

def _baseline_ativa(obra_id: int, admin_id: int, cliente_mode: bool):
    return CronogramaBaseline.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode, ativa=True
    ).first()


def _itens_da_baseline(baseline) -> dict:
    """`tarefa_id → {data_inicio, data_fim, duracao_dias}` (datas em ISO).

    É o formato que o front consome direto: o Gantt desenha a barra cinza e
    a coluna Desvio subtrai as datas.
    """
    if baseline is None:
        return {}
    return {
        item.tarefa_id: {
            'data_inicio': item.data_inicio.isoformat() if item.data_inicio else None,
            'data_fim': item.data_fim.isoformat() if item.data_fim else None,
            'duracao_dias': item.duracao_dias,
        }
        for item in baseline.itens
    }


def _baseline_to_dict(baseline) -> dict:
    return {
        'id': baseline.id,
        'nome': baseline.nome,
        'ativa': baseline.ativa,
        'criada_em': baseline.criada_em.isoformat() if baseline.criada_em else None,
        'total_itens': baseline.itens.count(),
    }


def _desativar_baselines(obra_id: int, admin_id: int, cliente_mode: bool,
                         exceto_id: int | None = None) -> None:
    """Desativa as irmãs. O índice único parcial (`WHERE ativa`) garante a
    invariante no banco; isto é o mecanismo normal."""
    query = CronogramaBaseline.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode, ativa=True)
    if exceto_id is not None:
        query = query.filter(CronogramaBaseline.id != exceto_id)
    query.update({'ativa': False}, synchronize_session=False)


@cronograma_bp.route('/obra/<int:obra_id>/baseline', methods=['POST'])
@login_required
def criar_baseline(obra_id: int):
    """Fase 4 — congela o planejado atual como linha de base.

    Só entram tarefas ATIVAS que já têm início e fim; tarefa sem datas não
    tem o que congelar. Salvar de novo cria OUTRA baseline (o histórico é
    preservado) e, por padrão, passa a ser a ativa — `ativar: false` guarda
    sem trocar a comparação corrente.

    Não é decorada com `_com_undo`: baseline não altera nenhuma tarefa, então
    o diff seria vazio de qualquer forma.
    """
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    data = request.get_json(silent=True) or {}

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .filter(TarefaCronograma.ativa.is_(True))
        .filter(TarefaCronograma.data_inicio.isnot(None))
        .filter(TarefaCronograma.data_fim.isnot(None))
        .all()
    )
    if not tarefas:
        return jsonify({
            'status': 'error',
            'msg': 'Não há tarefas com datas para congelar na linha de base',
        }), 400

    nome = (data.get('nome') or '').strip() or \
        f"Linha de base {date.today().strftime('%d/%m/%Y')}"
    ativar = data.get('ativar')
    ativar = True if ativar is None else bool(ativar)

    if ativar:
        _desativar_baselines(obra_id, admin_id, cliente_mode)

    # p10 — congela o BAC junto com as datas. Sem isto, o EVM compara custo
    # real contra orçamento vivo, e revisar o orçamento para cima melhoraria
    # o CPI sozinho.
    from services.custo_orcado import custo_orcado_da_obra
    bac_congelado = custo_orcado_da_obra(obra_id, admin_id)

    baseline = CronogramaBaseline(
        obra_id=obra_id, admin_id=admin_id, nome=nome[:120],
        criada_por=current_user.id, ativa=ativar, is_cliente=cliente_mode,
        bac=bac_congelado or None)
    db.session.add(baseline)
    db.session.flush()
    for t in tarefas:
        db.session.add(CronogramaBaselineItem(
            baseline_id=baseline.id, tarefa_id=t.id, admin_id=admin_id,
            data_inicio=t.data_inicio, data_fim=t.data_fim,
            duracao_dias=t.duracao_dias))
    db.session.commit()

    logger.info(f"[OK] Linha de base criada id={baseline.id} obra={obra_id} "
                f"itens={len(tarefas)} ativa={ativar} (editor v2)")
    return jsonify({
        'status': 'ok',
        'baseline': _baseline_to_dict(baseline),
        'baseline_map': _itens_da_baseline(baseline) if ativar else {},
    }), 201


@cronograma_bp.route('/obra/<int:obra_id>/baselines')
@login_required
def listar_baselines(obra_id: int):
    """Fase 4 — histórico de linhas de base da obra, mais recente primeiro."""
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    baselines = (
        CronogramaBaseline.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .order_by(CronogramaBaseline.id.desc()).all()
    )
    return jsonify({'status': 'ok',
                    'baselines': [_baseline_to_dict(b) for b in baselines]})


@cronograma_bp.route('/obra/<int:obra_id>/baseline/<int:bid>/ativar',
                     methods=['POST'])
@login_required
def ativar_baseline(obra_id: int, bid: int):
    """Fase 4 — troca a linha de base usada na comparação."""
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    baseline = CronogramaBaseline.query.filter_by(
        id=bid, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).first()
    if baseline is None:
        return jsonify({'status': 'error',
                        'msg': 'Linha de base não encontrada'}), 404

    _desativar_baselines(obra_id, admin_id, cliente_mode, exceto_id=bid)
    baseline.ativa = True
    db.session.commit()
    logger.info(f"[OK] Linha de base ativada id={bid} obra={obra_id} (editor v2)")
    return jsonify({'status': 'ok', 'baseline': _baseline_to_dict(baseline),
                    'baseline_map': _itens_da_baseline(baseline)})


@cronograma_bp.route('/obra/<int:obra_id>/baseline/<int:bid>',
                     methods=['DELETE'])
@login_required
def excluir_baseline(obra_id: int, bid: int):
    """Fase 4 — remove uma linha de base (os itens caem por CASCADE)."""
    guard = _guard_rotas_vinculo(obra_id)
    if guard:
        return guard
    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    baseline = CronogramaBaseline.query.filter_by(
        id=bid, obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode
    ).first()
    if baseline is None:
        return jsonify({'status': 'error',
                        'msg': 'Linha de base não encontrada'}), 404
    db.session.delete(baseline)
    db.session.commit()
    logger.info(f"[OK] Linha de base excluída id={bid} obra={obra_id} (editor v2)")
    # Sem baseline ativa o front limpa as barras cinzas e a coluna Desvio.
    ativa = _baseline_ativa(obra_id, admin_id, cliente_mode)
    return jsonify({'status': 'ok',
                    'baseline_map': _itens_da_baseline(ativa)})


# ─────────────────────────────────────────────────────────────────────────────
# REORDENAR TAREFAS (drag & drop)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/reordenar', methods=['POST'])
@login_required
@_com_undo('reordenar')
def reordenar(obra_id: int):
    """
    Persiste a nova ordem dos itens do cronograma da obra. Espera JSON:
        {"ordem": [<id>, <id>, ...]}

    Task #19 — drag-and-drop com persistência: valida que a obra pertence
    ao tenant, que todos os IDs são inteiros únicos e que cada um pertence
    à mesma obra/admin (e ao mesmo modo cliente/interno). Escreve em uma
    única transação; em qualquer falha faz rollback e devolve erro para
    o front reverter visualmente.
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    escopo = _guard_editar_obra(obra_id)
    if escopo:
        return escopo
    cliente_mode = _modo_cliente()

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        return jsonify({'status': 'error', 'msg': 'Obra não encontrada.'}), 404

    data = request.get_json(silent=True) or {}
    ordem_raw = data.get('ordem')

    if not isinstance(ordem_raw, list) or not ordem_raw:
        return jsonify({
            'status': 'error',
            'msg': 'Campo "ordem" deve ser uma lista de IDs.',
        }), 400

    try:
        ordem_ids = [int(x) for x in ordem_raw]
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'IDs inválidos.'}), 400

    if len(set(ordem_ids)) != len(ordem_ids):
        return jsonify({'status': 'error', 'msg': 'IDs duplicados na ordem.'}), 400

    # Carrega TODAS as tarefas da nova ordem em UMA query e valida que
    # cada uma pertence à obra/admin e ao modo (cliente vs. interno) atual.
    # Tudo ou nada: se algum ID não bate, devolve 400 e nada é persistido.
    tarefas = TarefaCronograma.query.filter(
        TarefaCronograma.id.in_(ordem_ids),
        TarefaCronograma.obra_id == obra_id,
        TarefaCronograma.admin_id == admin_id,
        TarefaCronograma.is_cliente == cliente_mode,
        TarefaCronograma.ativa.is_(True),
    ).all()

    if len(tarefas) != len(ordem_ids):
        return jsonify({
            'status': 'error',
            'msg': 'Algumas tarefas não pertencem a esta obra.',
        }), 400

    by_id = {t.id: t for t in tarefas}
    try:
        for idx, tid in enumerate(ordem_ids):
            by_id[tid].ordem = idx
        db.session.commit()
    except Exception as exc:  # pragma: no cover - defensivo
        db.session.rollback()
        logger.exception(
            f"[ERROR] Falha ao reordenar cronograma obra={obra_id}: {exc}"
        )
        return jsonify({'status': 'error', 'msg': 'Falha ao salvar ordem.'}), 500

    logger.info(
        f"[OK] Cronograma reordenado obra={obra_id} cliente={cliente_mode} "
        f"qtd={len(ordem_ids)}"
    )
    return jsonify({'status': 'ok'})


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DO CALENDÁRIO
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/calendario', methods=['GET', 'POST'])
@login_required
def calendario():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    cal = get_calendario(admin_id)

    if request.method == 'POST':
        cal.considerar_sabado = bool(request.form.get('considerar_sabado'))
        cal.considerar_domingo = bool(request.form.get('considerar_domingo'))
        db.session.commit()

        recalcular_tudo = request.form.get('recalcular_tudo') == '1'
        if recalcular_tudo:
            obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
            for obra in obras:
                recalcular_cronograma(obra.id, admin_id)
            flash(
                f'Calendário salvo e {len(obras)} cronograma(s) recalculado(s).',
                'success',
            )
        else:
            flash('Configuração de calendário salva com sucesso.', 'success')

        return redirect(url_for('cronograma.calendario'))

    return render_template('configuracoes/calendario.html', calendario=cal)


# ─────────────────────────────────────────────────────────────────────────────
# API RDO ↔ CRONOGRAMA — Apontamento de Produção Diária
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/tarefas-rdo')
@login_required
def tarefas_rdo(obra_id: int):
    """
    Retorna a árvore de tarefas do cronograma para apontamento em RDO.
    Query param: ?data=YYYY-MM-DD (data do RDO) e ?rdo_id=<id> (opcional)
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    data_str = request.args.get('data')
    rdo_id = request.args.get('rdo_id', type=int)

    try:
        data_rdo = date.fromisoformat(data_str) if data_str else date.today()
    except (ValueError, TypeError):
        data_rdo = date.today()

    # Task #147 — filtra explicitamente o cronograma INTERNO (is_cliente=False).
    # Sem esse filtro, obras que já tiveram o cronograma do cliente gerado
    # devolviam interno + clones do cliente juntos, dobrando cada item no card
    # "Apontamento de Produção — Cronograma" do Novo RDO.
    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    # Task #154 — usar o mesmo critério do cronograma para identificar pais
    # (qualquer tarefa cujo id apareça como tarefa_pai_id de outra) e
    # garantir que o agregado bate com a tela do cronograma.
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}

    # Montar dict com progresso
    from services.cronograma_apontamento_service import modo_da_tarefa
    from utils.tenant import rdo_percentual_livre_on
    # RDO em porcentagem livre: uma leitura da flag para a obra inteira, e o
    # booleano viaja para o resolvedor — senão seria uma consulta por tarefa
    # dentro do laço que monta a tela de apontamento.
    percentual_livre = rdo_percentual_livre_on(admin_id)
    resultado = []
    item_por_id: dict[int, dict] = {}
    for t in tarefas:
        progresso = calcular_progresso_rdo(t.id, data_rdo, admin_id,
                                           percentual_livre)

        # Buscar apontamento específico deste RDO para esta tarefa (se existir)
        qty_hoje = 0.0
        pct_hoje = None
        apontamento_id = None
        if rdo_id:
            ap = RDOApontamentoCronograma.query.filter_by(
                rdo_id=rdo_id, tarefa_cronograma_id=t.id
            ).first()
            if ap:
                qty_hoje = ap.quantidade_executada_dia
                pct_hoje = ap.percentual_acumulado
                apontamento_id = ap.id

        # M07: "Anterior X%" do preview = último acumulado ANTES da data do
        # RDO (exclui o apontamento do próprio dia).
        ant_row = (
            db.session.query(RDOApontamentoCronograma.percentual_acumulado,
                             RDOApontamentoCronograma.percentual_realizado)
            .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
            .filter(
                RDOApontamentoCronograma.tarefa_cronograma_id == t.id,
                RDOApontamentoCronograma.admin_id == admin_id,
                RDO.data_relatorio < data_rdo,
            )
            .order_by(RDO.data_relatorio.desc(),
                      RDOApontamentoCronograma.id.desc())
            .first()
        )
        pct_anterior = 0.0
        if ant_row is not None:
            pct_anterior = float(ant_row[0] if ant_row[0] is not None
                                 else (ant_row[1] or 0.0))
        tipo_modo = modo_da_tarefa(t, percentual_livre)
        saldo = None
        if tipo_modo == 'quantidade':
            saldo = round(float(t.quantidade_total or 0)
                          - float(progresso['quantidade_acumulada'] or 0), 2)

        item = {
            'id': t.id,
            'tarefa_pai_id': t.tarefa_pai_id,
            'nome_tarefa': t.nome_tarefa,
            'duracao_dias': t.duracao_dias,
            'data_inicio': t.data_inicio.isoformat() if t.data_inicio else None,
            'data_fim': t.data_fim.isoformat() if t.data_fim else None,
            'quantidade_total': t.quantidade_total,
            'unidade_medida': t.unidade_medida or '',
            'percentual_concluido': t.percentual_concluido,
            'percentual_planejado': progresso['percentual_planejado'],
            'percentual_realizado': progresso['percentual_realizado'],
            'quantidade_acumulada': progresso['quantidade_acumulada'],
            'quantidade_executada_hoje': qty_hoje,
            'apontamento_id': apontamento_id,
            # M07 — contrato de modos: a UI não decide fórmula, só exibe.
            'tipo_modo': tipo_modo,
            # Escolha explícita (None = automático). `tipo_modo` acima é o
            # modo EFETIVO já resolvido; este campo diz se veio de escolha
            # ou de dedução — a UI do Gantt precisa dos dois.
            'modo_apontamento': getattr(t, 'modo_apontamento', None),
            'is_marco': bool(getattr(t, 'is_marco', False)),
            'percentual_acumulado_anterior': pct_anterior,
            'percentual_acumulado_hoje': pct_hoje,
            'saldo': saldo,
            'responsavel': getattr(t, 'responsavel', 'empresa') or 'empresa',
            'is_pai': t.id in pai_ids,
            'data_entrega_real': (
                t.data_entrega_real.isoformat()
                if getattr(t, 'data_entrega_real', None) else None
            ),
        }
        resultado.append(item)
        item_por_id[t.id] = item

    # Bottom-up: % realizado dos pais — fórmula única do engine (M06).
    # Garante que o subgrupo no RDO mostra o mesmo valor agregado do
    # cronograma, mesmo se `percentual_concluido` ainda estiver desatualizado.
    from utils.cronograma_engine import rollup_realizado
    for pai_id, pct in rollup_realizado(resultado).items():
        item_por_id[pai_id]['percentual_realizado'] = pct
        item_por_id[pai_id]['percentual_concluido'] = pct

    return jsonify({'status': 'ok', 'tarefas': resultado})


# ─────────────────────────────────────────────────────────────────────────────
# SUBEMPREITADA — Apontamentos diários (pessoas × horas × quantidade)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/rdo/<int:rdo_id>/apontar-subempreitada', methods=['POST'])
@login_required
def apontar_subempreitada(rdo_id: int):
    """
    Cria/atualiza um apontamento de equipe de subempreitada para uma tarefa em um RDO.
    Body JSON: {
        id (opcional, para update), tarefa_cronograma_id, subempreiteiro_id,
        qtd_pessoas, horas_trabalhadas, quantidade_produzida, observacoes
    }
    Atualiza o percentual da tarefa do cronograma como soma dos apontamentos
    (homem-empresa + subempreitada).
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    from models import RDO, RDOSubempreitadaApontamento, Subempreiteiro

    admin_id = _admin_id()

    # Autorização ANTES de validar payload: quem não pode apontar nesta obra
    # não deve nem descobrir quais campos o endpoint exige. O escopo é da OBRA
    # do RDO — esta rota recebe rdo_id, não obra_id.
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404
    escopo = _guard_apontar_obra(rdo.obra_id)
    if escopo:
        return escopo

    data = request.get_json(silent=True) or {}

    apt_id = data.get('id')
    tarefa_id = data.get('tarefa_cronograma_id')
    sub_id = data.get('subempreiteiro_id')
    qtd_pessoas = int(data.get('qtd_pessoas', 0) or 0)
    horas = float(data.get('horas_trabalhadas', 0) or 0)
    qtd_prod = float(data.get('quantidade_produzida', 0) or 0)
    obs = (data.get('observacoes') or '').strip() or None

    if not tarefa_id or not sub_id:
        return jsonify({'status': 'error', 'msg': 'tarefa_cronograma_id e subempreiteiro_id obrigatórios'}), 400

    tarefa = TarefaCronograma.query.filter_by(id=tarefa_id, admin_id=admin_id).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404

    # Task #147 — apontamentos só podem ser criados na árvore INTERNA da obra.
    # Bloqueia tentativa (acidental ou maliciosa) de apontar em um clone do
    # cronograma do cliente, que geraria registros "fantasma" no portal.
    if tarefa.is_cliente:
        return jsonify({
            'status': 'error',
            'msg': 'Apontamentos não podem ser feitos em tarefas do cronograma do cliente'
        }), 400

    sub = Subempreiteiro.query.filter_by(id=sub_id, admin_id=admin_id).first()
    if not sub:
        return jsonify({'status': 'error', 'msg': 'Subempreiteiro não encontrado'}), 404

    if apt_id:
        apt = RDOSubempreitadaApontamento.query.filter_by(id=apt_id, admin_id=admin_id).first()
        if not apt:
            return jsonify({'status': 'error', 'msg': 'Apontamento não encontrado'}), 404
    else:
        apt = RDOSubempreitadaApontamento(
            rdo_id=rdo_id, admin_id=admin_id,
            tarefa_cronograma_id=tarefa_id, subempreiteiro_id=sub_id,
        )
        db.session.add(apt)

    apt.tarefa_cronograma_id = tarefa_id
    apt.subempreiteiro_id = sub_id
    apt.qtd_pessoas = qtd_pessoas
    apt.horas_trabalhadas = horas
    apt.quantidade_produzida = qtd_prod
    apt.observacoes = obs
    apt.calcular_homem_hora()

    db.session.commit()

    # Recalcular percentual da tarefa somando empresa + subempreitada (acumulado por data)
    _atualizar_percentual_com_subempreitada(tarefa_id, admin_id)

    return jsonify({
        'status': 'ok',
        'apontamento': {
            'id': apt.id,
            'tarefa_cronograma_id': apt.tarefa_cronograma_id,
            'subempreiteiro_id': apt.subempreiteiro_id,
            'subempreiteiro_nome': sub.nome,
            'qtd_pessoas': apt.qtd_pessoas,
            'horas_trabalhadas': apt.horas_trabalhadas,
            'quantidade_produzida': apt.quantidade_produzida,
            'homem_hora': apt.homem_hora,
            'observacoes': apt.observacoes,
        },
    })


@cronograma_bp.route('/rdo/<int:rdo_id>/apontamentos-subempreitada')
@login_required
def listar_apontamentos_subempreitada(rdo_id: int):
    """Lista todos os apontamentos de subempreitada deste RDO."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    from models import RDO, RDOSubempreitadaApontamento, Subempreiteiro

    admin_id = _admin_id()
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404

    # LEITURA: escopo de VER, não de apontar. Barrar um LEITOR aqui esconderia
    # dele o que ele tem direito de consultar — o eixo de escrita é o das
    # rotas de POST/DELETE abaixo.
    from utils.autorizacao import pode_ver_obra
    if not pode_ver_obra(rdo.obra_id):
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404

    rows = (
        db.session.query(RDOSubempreitadaApontamento, Subempreiteiro)
        .join(Subempreiteiro, Subempreiteiro.id == RDOSubempreitadaApontamento.subempreiteiro_id)
        .filter(RDOSubempreitadaApontamento.rdo_id == rdo_id,
                RDOSubempreitadaApontamento.admin_id == admin_id)
        .all()
    )

    return jsonify({
        'status': 'ok',
        'apontamentos': [
            {
                'id': apt.id,
                'tarefa_cronograma_id': apt.tarefa_cronograma_id,
                'subempreiteiro_id': apt.subempreiteiro_id,
                'subempreiteiro_nome': sub.nome,
                'qtd_pessoas': apt.qtd_pessoas,
                'horas_trabalhadas': apt.horas_trabalhadas,
                'quantidade_produzida': apt.quantidade_produzida,
                'homem_hora': apt.homem_hora,
                'observacoes': apt.observacoes,
            }
            for apt, sub in rows
        ],
    })


@cronograma_bp.route('/rdo/apontamento-subempreitada/<int:apt_id>', methods=['DELETE'])
@login_required
def excluir_apontamento_subempreitada(apt_id: int):
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    from models import RDOSubempreitadaApontamento

    admin_id = _admin_id()
    apt = RDOSubempreitadaApontamento.query.filter_by(id=apt_id, admin_id=admin_id).first()
    if not apt:
        return jsonify({'status': 'error', 'msg': 'Não encontrado'}), 404

    # Esta rota não traz obra_id NEM rdo_id na URL: o escopo sai do RDO do
    # próprio apontamento. Sem isto, apagar apontamento seria a única operação
    # de escrita do cronograma sem segundo eixo.
    from models import RDO as _RDO
    _rdo = db.session.get(_RDO, apt.rdo_id)
    escopo = _guard_apontar_obra(_rdo.obra_id) if _rdo else None
    if escopo:
        return escopo

    tarefa_id = apt.tarefa_cronograma_id
    db.session.delete(apt)
    db.session.commit()
    _atualizar_percentual_com_subempreitada(tarefa_id, admin_id)
    return jsonify({'status': 'ok'})


def _atualizar_percentual_com_subempreitada(tarefa_id: int, admin_id: int):
    """Delegação fina (M06): a soma empresa+subempreitada vive no engine,
    em `atualizar_percentual_tarefa` — fórmula num só lugar. Mantida pelas
    chamadas existentes nas rotas de apontamento."""
    from utils.cronograma_engine import atualizar_percentual_tarefa
    atualizar_percentual_tarefa(tarefa_id, admin_id)


@cronograma_bp.route('/rdo/<int:rdo_id>/apontar', methods=['POST'])
@login_required
def apontar_producao(rdo_id: int):
    """
    Salva ou atualiza a produção diária de uma tarefa do cronograma.
    Body JSON: { tarefa_cronograma_id, quantidade_executada_dia }
    """
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    data = request.get_json(silent=True) or {}
    tarefa_id = data.get('tarefa_cronograma_id')
    # M07: modo percentual quando o body traz percentual_acumulado;
    # senão modo quantitativo legado (quantidade_executada_dia).
    pct_acumulado = data.get('percentual_acumulado')
    qty_dia = float(data.get('quantidade_executada_dia', 0) or 0)

    if not tarefa_id:
        return jsonify({'status': 'error', 'msg': 'tarefa_cronograma_id obrigatório'}), 400

    # Verificar que o RDO pertence ao admin (isolamento multi-tenant)
    from models import RDO
    rdo = RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()
    if not rdo:
        return jsonify({'status': 'error', 'msg': 'RDO não encontrado'}), 404

    # O escopo é da OBRA do RDO — estas rotas recebem rdo_id, não obra_id.
    escopo = _guard_apontar_obra(rdo.obra_id)
    if escopo:
        return escopo

    tarefa = TarefaCronograma.query.filter_by(id=tarefa_id, admin_id=admin_id).first()
    if not tarefa:
        return jsonify({'status': 'error', 'msg': 'Tarefa não encontrada'}), 404

    # Task #147 — apontamentos só podem ser criados na árvore INTERNA da obra.
    # Bloqueia tentativa (acidental ou maliciosa) de apontar em um clone do
    # cronograma do cliente, que geraria registros "fantasma" no portal.
    if tarefa.is_cliente:
        return jsonify({
            'status': 'error',
            'msg': 'Apontamentos não podem ser feitos em tarefas do cronograma do cliente'
        }), 400

    # Módulo 1 (cronograma-mpp): acumulado + percentuais + UPSERT delegados ao
    # serviço único services/cronograma_apontamento_service.registrar_apontamento
    # (mesma semântica de antes — ver testes de caracterização). Task #142:
    # percentual_planejado fica `None` quando a tarefa não tem plano calculável
    # (sem data_inicio/duração); a UI usa esse `None` para mostrar "—" /
    # badge "Sem plano" em vez de 0%.
    from services.cronograma_apontamento_service import (
        ApontamentoInvalido,
        recomputar_cadeia,
        registrar_apontamento,
    )
    try:
        if pct_acumulado is not None:
            ap = registrar_apontamento(
                rdo, tarefa,
                percentual_acumulado=float(pct_acumulado),
                admin_id=admin_id,
                permitir_retrocesso=bool(data.get('permitir_retrocesso')),
                justificativa=(data.get('justificativa') or '').strip() or None,
                permitir_sobreexecucao=bool(data.get('permitir_sobreexecucao')),
            )
        else:
            ap = registrar_apontamento(
                rdo, tarefa,
                quantidade_dia=qty_dia,
                admin_id=admin_id,
            )
    except ApontamentoInvalido as exc:
        db.session.rollback()
        return jsonify({'status': 'error', 'msg': str(exc)}), 422
    plan_calculado = ap.percentual_planejado
    # Correção retroativa/edição: RDOs posteriores recalculados na MESMA
    # transação (M07 — recomputo em cadeia determinístico).
    db.session.flush()
    recalculados = recomputar_cadeia(tarefa_id, rdo.data_relatorio, admin_id)

    db.session.commit()

    # Atualizar percentual_concluido da tarefa
    atualizar_percentual_tarefa(tarefa_id, admin_id)

    return jsonify({
        'status': 'ok',
        'rdos_posteriores_recalculados': recalculados,
        'apontamento': {
            'id': ap.id,
            'quantidade_executada_dia': ap.quantidade_executada_dia,
            'quantidade_acumulada': ap.quantidade_acumulada,
            'percentual_realizado': ap.percentual_realizado,
            'percentual_planejado': plan_calculado,
        },
    })


@cronograma_bp.route('/rdo/<int:rdo_id>/apontamentos')
@login_required
def listar_apontamentos(rdo_id: int):
    """Retorna todos os apontamentos de um RDO com dados da tarefa."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error'}), 403

    admin_id = _admin_id()
    aps = (
        RDOApontamentoCronograma.query
        .filter_by(rdo_id=rdo_id, admin_id=admin_id)
        .all()
    )

    resultado = []
    for ap in aps:
        t = ap.tarefa
        resultado.append({
            'id': ap.id,
            'tarefa_id': ap.tarefa_cronograma_id,
            'nome_tarefa': t.nome_tarefa if t else '—',
            'unidade_medida': t.unidade_medida if t else '',
            'quantidade_total': t.quantidade_total if t else None,
            'quantidade_executada_dia': ap.quantidade_executada_dia,
            'quantidade_acumulada': ap.quantidade_acumulada,
            'percentual_realizado': ap.percentual_realizado,
            'percentual_planejado': ap.percentual_planejado,
        })

    return jsonify({'status': 'ok', 'apontamentos': resultado})


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO DE SUBATIVIDADES — CRUD SubatividadeMestre com unidade/meta
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/catalogo')
@login_required
def catalogo_subatividades():
    """Página de gestão do catálogo de subatividades com metas de produtividade."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
    todos = (
        SubatividadeMestre.query
        .filter_by(admin_id=admin_id)
        .order_by(SubatividadeMestre.nome)
        .all()
    )
    grupos = [s for s in todos if getattr(s, 'tipo', 'subatividade') == 'grupo']
    subatividades = [s for s in todos if getattr(s, 'tipo', 'subatividade') != 'grupo']
    return render_template(
        'cronograma/catalogo.html',
        servicos=servicos,
        subatividades=subatividades,
        grupos=grupos,
    )


@cronograma_bp.route('/catalogo/nova', methods=['POST'])
@login_required
def catalogo_nova_subatividade():
    """Criar nova subatividade no catálogo."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tipo = (request.form.get('tipo') or 'subatividade').strip()
    if tipo not in ('grupo', 'subatividade'):
        tipo = 'subatividade'
    nome = (request.form.get('nome') or '').strip()

    if not nome:
        flash('Nome é obrigatório.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    if tipo == 'grupo':
        sub = SubatividadeMestre(
            servico_id=None,
            tipo='grupo',
            nome=nome,
            descricao=(request.form.get('descricao') or '').strip() or None,
            obrigatoria=False,
            admin_id=admin_id,
        )
        db.session.add(sub)
        db.session.commit()
        flash(f'Grupo "{nome}" criado com sucesso.', 'success')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    # tipo == 'subatividade'
    descricao = (request.form.get('descricao') or '').strip()
    unidade_medida = (request.form.get('unidade_medida') or '').strip() or None
    meta_produtividade_str = (request.form.get('meta_produtividade') or '').strip()
    ordem_padrao = request.form.get('ordem_padrao', type=int, default=0)
    obrigatoria = request.form.get('obrigatoria') == '1'
    servico_id = request.form.get('servico_id', type=int)

    if not unidade_medida:
        flash('Unidade de Medida é obrigatória para subatividades.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    if not meta_produtividade_str:
        flash('Meta de Produtividade é obrigatória para subatividades.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    try:
        meta = float(meta_produtividade_str)
        if meta <= 0:
            raise ValueError("meta deve ser positiva")
    except ValueError:
        flash('Meta de Produtividade deve ser um número positivo.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    sub = SubatividadeMestre(
        servico_id=servico_id or None,
        tipo='subatividade',
        nome=nome,
        descricao=descricao or None,
        unidade_medida=unidade_medida,
        meta_produtividade=meta,
        ordem_padrao=ordem_padrao,
        obrigatoria=obrigatoria,
        admin_id=admin_id,
    )
    db.session.add(sub)
    db.session.flush()

    # Task #62 — vincular composições selecionadas (N:N SubatividadeMaoObra)
    _sync_composicoes_subatividade(sub, request.form.getlist('composicoes_ids'), admin_id)

    db.session.commit()
    flash(f'Subatividade "{nome}" criada com sucesso.', 'success')
    return redirect(url_for('cronograma.catalogo_subatividades'))


def _sync_composicoes_subatividade(sub: SubatividadeMestre, ids_raw: list, admin_id: int) -> None:
    """Task #62 — sincroniza SubatividadeMaoObra para a subatividade.

    ids_raw: lista de strings do form (composicoes_ids[]). Apenas IDs que
    pertencem ao admin e (quando sub.servico_id está setado) ao mesmo serviço
    são aceitos. Apaga os removidos e cria os novos. Idempotente.
    """
    novos_ids = set()
    for raw in (ids_raw or []):
        try:
            novos_ids.add(int(raw))
        except (ValueError, TypeError):
            continue

    if novos_ids:
        # Multi-tenant: SEMPRE filtra por admin_id; restringe ao serviço da sub
        # quando houver; aceita apenas composições de insumo MAO_OBRA.
        from models import Insumo as _Insumo
        q = (
            ComposicaoServico.query
            .join(_Insumo, ComposicaoServico.insumo_id == _Insumo.id)
            .filter(
                ComposicaoServico.id.in_(novos_ids),
                ComposicaoServico.admin_id == admin_id,
                _Insumo.tipo == 'MAO_OBRA',
            )
        )
        if sub.servico_id:
            q = q.filter(ComposicaoServico.servico_id == sub.servico_id)
        composicoes_validas = {c.id for c in q.all()}
        novos_ids = novos_ids & composicoes_validas

    atuais = SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id
    ).all()
    atuais_ids = {l.composicao_servico_id for l in atuais}

    for link in atuais:
        if link.composicao_servico_id not in novos_ids:
            db.session.delete(link)

    for new_id in (novos_ids - atuais_ids):
        db.session.add(SubatividadeMaoObra(
            admin_id=admin_id,
            subatividade_mestre_id=sub.id,
            composicao_servico_id=new_id,
        ))


@cronograma_bp.route('/catalogo/novo-grupo', methods=['POST'])
@login_required
def catalogo_novo_grupo():
    """Criar novo grupo no catálogo (sem vínculo com Serviço)."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    nome = (request.form.get('nome') or '').strip()
    if not nome:
        flash('Nome é obrigatório.', 'warning')
        return redirect(url_for('cronograma.catalogo_subatividades'))

    grupo = SubatividadeMestre(
        servico_id=None,
        tipo='grupo',
        nome=nome,
        descricao=(request.form.get('descricao') or '').strip() or None,
        obrigatoria=False,
        admin_id=admin_id,
    )
    db.session.add(grupo)
    db.session.commit()
    flash(f'Grupo "{nome}" criado com sucesso.', 'success')
    return redirect(url_for('cronograma.catalogo_subatividades'))


@cronograma_bp.route('/catalogo/<int:sub_id>/editar', methods=['GET', 'POST'])
@login_required
def catalogo_editar_subatividade(sub_id: int):
    """Editar subatividade do catálogo."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    sub = SubatividadeMestre.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'warning')
        else:
            tipo_atual = getattr(sub, 'tipo', 'subatividade')
            if tipo_atual == 'grupo':
                sub.nome = nome
                sub.descricao = (request.form.get('descricao') or '').strip() or None
                sub.ativo = request.form.get('ativo') == '1'
                db.session.commit()
                flash(f'Grupo "{sub.nome}" atualizado.', 'success')
                return redirect(url_for('cronograma.catalogo_subatividades'))
            else:
                meta_str = request.form.get('meta_produtividade') or ''
                try:
                    meta = float(meta_str) if meta_str else None
                except ValueError:
                    meta = None
                sub.nome = nome
                # Only update servico_id when the field is explicitly present in the submitted form
                if 'servico_id' in request.form:
                    sub.servico_id = request.form.get('servico_id', type=int) or None
                sub.descricao = (request.form.get('descricao') or '').strip() or None
                sub.unidade_medida = (request.form.get('unidade_medida') or '').strip() or None
                sub.meta_produtividade = meta
                sub.ordem_padrao = request.form.get('ordem_padrao', type=int, default=0)
                sub.obrigatoria = request.form.get('obrigatoria') == '1'
                sub.ativo = request.form.get('ativo') == '1'
                # Task #62 — flag de revisão (auto-marcada via cronograma)
                if 'precisa_revisao' in request.form:
                    sub.precisa_revisao = request.form.get('precisa_revisao') == '1'
                # Task #62 — sincroniza N:N composições
                if 'composicoes_ids' in request.form or any(
                    k.startswith('composicoes_ids') for k in request.form.keys()
                ):
                    _sync_composicoes_subatividade(
                        sub, request.form.getlist('composicoes_ids'), admin_id
                    )
                db.session.commit()
                flash(f'Subatividade "{sub.nome}" atualizada.', 'success')
                return redirect(url_for('cronograma.catalogo_subatividades'))

    servicos = Servico.query.filter_by(admin_id=admin_id, ativo=True).order_by(Servico.nome).all()
    # Task #62 — composições disponíveis (apenas MO, do serviço da sub, do admin)
    composicoes = []
    if sub.servico_id:
        from models import Insumo as _Insumo
        composicoes = (
            ComposicaoServico.query
            .join(_Insumo, ComposicaoServico.insumo_id == _Insumo.id)
            .filter(
                ComposicaoServico.servico_id == sub.servico_id,
                ComposicaoServico.admin_id == admin_id,
                _Insumo.tipo == 'MAO_OBRA',
            )
            .order_by(ComposicaoServico.id)
            .all()
        )
    composicoes_selecionadas_ids = {
        l.composicao_servico_id
        for l in SubatividadeMaoObra.query.filter_by(
            subatividade_mestre_id=sub.id
        ).all()
    }
    return render_template(
        'cronograma/catalogo_editar.html',
        sub=sub, servicos=servicos,
        composicoes=composicoes,
        composicoes_selecionadas_ids=composicoes_selecionadas_ids,
    )


@cronograma_bp.route('/catalogo/<int:sub_id>/excluir', methods=['POST'])
@login_required
def catalogo_excluir_subatividade(sub_id: int):
    """Excluir subatividade do catálogo."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    sub = SubatividadeMestre.query.filter_by(id=sub_id, admin_id=admin_id).first_or_404()
    nome = sub.nome
    try:
        db.session.delete(sub)
        db.session.commit()
        flash(f'Subatividade "{nome}" excluída.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO EXCLUIR SubatividadeMestre {sub_id}: {e}")
        flash('Erro ao excluir. Verifique se há itens vinculados.', 'error')
    return redirect(url_for('cronograma.catalogo_subatividades'))


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO — API JSON (painel esquerdo do template builder)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/api/catalogo')
@login_required
def api_catalogo():
    """Retorna grupos, subatividades e serviços do catálogo (para autocomplete e template builder)."""
    guard = _check_v2()
    if guard:
        return jsonify({'error': 'V2 required'}), 403

    admin_id = _admin_id()
    todos = (
        SubatividadeMestre.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(SubatividadeMestre.nome)
        .all()
    )

    def _sub_to_dict(s):
        return {
            'id': s.id,
            'nome': s.nome,
            'tipo': getattr(s, 'tipo', 'subatividade'),
            'unidade_medida': s.unidade_medida or '',
            'meta_produtividade': s.meta_produtividade,
            'servico_id': s.servico_id,
        }

    grupos = [_sub_to_dict(s) for s in todos if getattr(s, 'tipo', 'subatividade') == 'grupo']
    subatividades = [_sub_to_dict(s) for s in todos if getattr(s, 'tipo', 'subatividade') != 'grupo']

    servicos = (
        Servico.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(Servico.nome)
        .all()
    )
    servicos_list = [
        {'id': sv.id, 'nome': sv.nome, 'unidade_medida': sv.unidade_medida or ''}
        for sv in servicos
    ]

    return jsonify({'grupos': grupos, 'subatividades': subatividades, 'servicos': servicos_list})


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATES DE CRONOGRAMA — CRUD
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/templates')
@login_required
def listar_templates():
    """Lista todos os templates de cronograma do tenant."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    templates = (
        CronogramaTemplate.query
        .filter_by(admin_id=admin_id)
        .order_by(CronogramaTemplate.nome)
        .all()
    )
    return render_template('cronograma/templates.html', templates=templates)


@cronograma_bp.route('/templates/novo', methods=['GET', 'POST'])
@login_required
def novo_template():
    """Criar novo template de cronograma."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('O nome do template é obrigatório.', 'warning')
            return redirect(url_for('cronograma.novo_template'))

        tmpl = CronogramaTemplate(
            nome=nome,
            descricao=(request.form.get('descricao') or '').strip() or None,
            categoria=(request.form.get('categoria') or '').strip() or None,
            ativo=request.form.get('ativo', '1') == '1',
            admin_id=admin_id,
        )
        db.session.add(tmpl)
        db.session.flush()

        itens_json = request.form.get('itens_json')
        if itens_json:
            import json as _json
            try:
                arvore = _json.loads(itens_json)
                _salvar_arvore_template(tmpl, admin_id, arvore)
            except Exception as e:
                logger.warning(f"Erro ao parsear itens_json: {e}")
                _salvar_itens_template(tmpl, admin_id)
        else:
            _salvar_itens_template(tmpl, admin_id)

        db.session.commit()
        flash(f'Template "{tmpl.nome}" criado com sucesso.', 'success')
        return redirect(url_for('cronograma.detalhe_template', template_id=tmpl.id))

    return render_template(
        'cronograma/template_form.html',
        template=None,
        itens=[],
        itens_arvore=[],
    )


@cronograma_bp.route('/templates/<int:template_id>')
@login_required
def detalhe_template(template_id: int):
    """Exibe detalhes e itens de um template."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first_or_404()
    itens_arvore = _construir_arvore_itens(list(tmpl.itens))
    return render_template('cronograma/template_detalhe.html', template=tmpl, itens_arvore=itens_arvore)


@cronograma_bp.route('/templates/<int:template_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_template(template_id: int):
    """Editar template de cronograma."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first_or_404()

    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        if not nome:
            flash('O nome do template é obrigatório.', 'warning')
            return redirect(url_for('cronograma.editar_template', template_id=template_id))

        tmpl.nome = nome
        tmpl.descricao = (request.form.get('descricao') or '').strip() or None
        tmpl.categoria = (request.form.get('categoria') or '').strip() or None
        tmpl.ativo = request.form.get('ativo') == '1'

        # Remover itens antigos e recriar
        for item in list(tmpl.itens):
            db.session.delete(item)
        db.session.flush()

        itens_json = request.form.get('itens_json')
        if itens_json:
            import json as _json
            try:
                arvore = _json.loads(itens_json)
                _salvar_arvore_template(tmpl, admin_id, arvore)
            except Exception as e:
                logger.warning(f"Erro ao parsear itens_json: {e}")
                _salvar_itens_template(tmpl, admin_id)
        else:
            _salvar_itens_template(tmpl, admin_id)

        db.session.commit()
        flash(f'Template "{tmpl.nome}" atualizado.', 'success')
        return redirect(url_for('cronograma.detalhe_template', template_id=tmpl.id))

    # Montar árvore dos itens existentes para o template builder
    itens_arvore = _construir_arvore_itens(list(tmpl.itens))
    return render_template(
        'cronograma/template_form.html',
        template=tmpl,
        itens=list(tmpl.itens),
        itens_arvore=itens_arvore,
    )


# Task #23 — Modelo Excel para Templates de Cronograma (download/import)
@cronograma_bp.route('/templates/modelo-excel')
@login_required
def templates_modelo_excel():
    """Baixa o modelo `.xlsx` para cadastro de template + itens."""
    guard = _check_v2()
    if guard:
        return guard
    from services.catalogo_excel import gerar_modelo_cronograma_xlsx
    import io as _io
    bio = gerar_modelo_cronograma_xlsx()
    return send_file(
        _io.BytesIO(bio),
        as_attachment=True,
        download_name='modelo_cronograma.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@cronograma_bp.route('/templates/importar-excel', methods=['POST'])
@login_required
def templates_importar_excel():
    """Recebe um `.xlsx` preenchido e cria/atualiza um template."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        flash('Selecione um arquivo Excel para importar.', 'error')
        return redirect(url_for('cronograma.listar_templates'))
    if not arquivo.filename.lower().endswith(('.xlsx', '.xlsm')):
        flash('Envie um arquivo .xlsx (Excel).', 'error')
        return redirect(url_for('cronograma.listar_templates'))

    from services.catalogo_excel import importar_cronograma_xlsx
    try:
        resultado = importar_cronograma_xlsx(arquivo.stream, admin_id)
    except ValueError as e:
        flash(f'Erro ao importar: {e}', 'error')
        return redirect(url_for('cronograma.listar_templates'))
    except Exception as e:
        logger.exception('Erro inesperado importando template via Excel')
        flash(f'Erro inesperado: {e}', 'error')
        return redirect(url_for('cronograma.listar_templates'))

    acao = 'criado' if resultado['criado_ou_atualizado'] == 'created' else 'atualizado'
    flash(
        f'Template "{resultado["template_nome"]}" {acao} com '
        f'{resultado["itens_count"]} item(ns).',
        'success',
    )

    if resultado['rejected']:
        detalhes = '; '.join(
            f'linha {r["linha"]}: {r["motivo"]}'
            for r in resultado['rejected'][:15]
        )
        suffix = '' if len(resultado['rejected']) <= 15 else f' (+{len(resultado["rejected"]) - 15} outras)'
        flash(
            f'{len(resultado["rejected"])} linha(s) rejeitada(s): {detalhes}{suffix}',
            'warning',
        )

    return redirect(url_for('cronograma.listar_templates'))


@cronograma_bp.route('/templates/<int:template_id>/excluir', methods=['POST'])
@login_required
def excluir_template(template_id: int):
    """Excluir template de cronograma."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first_or_404()
    nome = tmpl.nome
    try:
        db.session.delete(tmpl)
        db.session.commit()
        flash(f'Template "{nome}" excluído.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO EXCLUIR TEMPLATE {template_id}: {e}")
        flash('Erro ao excluir o template.', 'error')
    return redirect(url_for('cronograma.listar_templates'))


def _salvar_itens_template(tmpl: CronogramaTemplate, admin_id: int) -> None:
    """
    Lê as listas de campos do formulário e salva os itens do template.
    Espera campos: item_nome[], item_ordem[], item_duracao_dias[],
                   item_quantidade_prevista[], item_responsavel[],
                   item_subatividade_mestre_id[]

    SEGURANÇA: cada subatividade_mestre_id é validado contra admin_id para
    garantir isolamento multi-tenant. IDs inválidos ou de outros tenants são
    silenciosamente descartados (item criado sem vínculo de catálogo).
    """
    nomes = request.form.getlist('item_nome')
    ordens = request.form.getlist('item_ordem')
    duracoes = request.form.getlist('item_duracao_dias')
    quantidades = request.form.getlist('item_quantidade_prevista')
    responsaveis = request.form.getlist('item_responsavel')
    sub_ids = request.form.getlist('item_subatividade_mestre_id')

    # Cache de SubatividadeMestre válidas para o tenant (evita N queries)
    sub_ids_validos: dict[int, bool] = {}

    for i, nome in enumerate(nomes):
        nome = (nome or '').strip()
        if not nome:
            continue
        try:
            ordem = int(ordens[i]) if i < len(ordens) else i
        except (ValueError, IndexError):
            ordem = i
        try:
            duracao = max(1, int(duracoes[i])) if i < len(duracoes) else 1
        except (ValueError, IndexError):
            duracao = 1
        try:
            qty_str = quantidades[i] if i < len(quantidades) else ''
            qty = float(qty_str) if qty_str and qty_str.strip() else None
        except (ValueError, IndexError):
            qty = None
        responsavel = (responsaveis[i] if i < len(responsaveis) else 'empresa') or 'empresa'

        # Validar subatividade_mestre_id pertence ao tenant
        sub_id: int | None = None
        try:
            sub_id_raw = sub_ids[i] if i < len(sub_ids) else ''
            raw_int = int(sub_id_raw) if sub_id_raw and sub_id_raw.strip() else None
            if raw_int is not None:
                if raw_int not in sub_ids_validos:
                    existe = SubatividadeMestre.query.filter_by(
                        id=raw_int, admin_id=admin_id
                    ).first() is not None
                    sub_ids_validos[raw_int] = existe
                sub_id = raw_int if sub_ids_validos[raw_int] else None
                if not sub_ids_validos.get(raw_int):
                    logger.warning(
                        f"SEGURANÇA: subatividade_mestre_id={raw_int} recusada "
                        f"(não pertence a admin_id={admin_id})"
                    )
        except (ValueError, IndexError):
            sub_id = None

        item = CronogramaTemplateItem(
            template_id=tmpl.id,
            subatividade_mestre_id=sub_id,
            nome_tarefa=nome,
            ordem=ordem,
            duracao_dias=duracao,
            quantidade_prevista=qty,
            responsavel=responsavel,
            admin_id=admin_id,
        )
        db.session.add(item)


def _salvar_arvore_template(tmpl: CronogramaTemplate, admin_id: int, arvore: list, parent_db_id: int | None = None, ordem_base: int = 0) -> int:
    """
    Salva recursivamente a árvore hierárquica de itens do template.
    Cada nó da arvore é um dict com:
      catalogo_id: int | None  (SubatividadeMestre.id)
      nome: str
      tipo: 'grupo' | 'subatividade'
      quantidade_prevista: float | None
      filhos: list  (apenas grupos podem ter filhos)

    Retorna a próxima ordem disponível.
    """
    ordem = ordem_base
    # Cache: catalogo_id → SubatividadeMestre (or None) for admin_id validation
    catalogo_cache: dict[int, object] = {}

    def _buscar_catalogo(cid: int):
        if cid not in catalogo_cache:
            catalogo_cache[cid] = SubatividadeMestre.query.filter_by(
                id=cid, admin_id=admin_id, ativo=True
            ).first()
        return catalogo_cache[cid]

    for no in arvore:
        catalogo_id = no.get('catalogo_id')
        nome = (no.get('nome') or '').strip()
        tipo_no = (no.get('tipo') or 'subatividade').strip()
        if tipo_no not in ('grupo', 'subatividade'):
            tipo_no = 'subatividade'
        if not nome:
            continue

        sub_id: int | None = None
        if catalogo_id:
            try:
                raw_int = int(catalogo_id)
                sm = _buscar_catalogo(raw_int)
                if sm is not None:
                    # Validate catalog item tipo matches tree node tipo
                    sm_tipo = getattr(sm, 'tipo', None) or 'subatividade'
                    if sm_tipo == tipo_no:
                        sub_id = raw_int
                    else:
                        logger.warning(
                            f"Template save: catalogo_id={raw_int} tipo={sm_tipo!r} "
                            f"não corresponde ao nó tipo={tipo_no!r} — referência ignorada"
                        )
            except (ValueError, TypeError):
                sub_id = None

        filhos = no.get('filhos') or []

        # Server-side rule: only grupos can have children
        if tipo_no == 'subatividade' and filhos:
            logger.warning(
                f"Template save: nó '{nome}' (tipo=subatividade) tem filhos — filhos ignorados"
            )
            filhos = []

        try:
            qty = float(no.get('quantidade_prevista') or 0) or None
        except (ValueError, TypeError):
            qty = None

        item = CronogramaTemplateItem(
            template_id=tmpl.id,
            subatividade_mestre_id=sub_id,
            parent_item_id=parent_db_id,
            nome_tarefa=nome,
            ordem=ordem,
            duracao_dias=1,
            quantidade_prevista=qty,
            responsavel='empresa',
            admin_id=admin_id,
        )
        db.session.add(item)
        db.session.flush()  # obtém item.id para usar como parent_item_id nos filhos

        ordem += 1
        if filhos:
            _salvar_arvore_template(tmpl, admin_id, filhos, parent_db_id=item.id, ordem_base=0)

    return ordem


def _construir_arvore_itens(itens: list) -> list:
    """
    Converte lista plana de CronogramaTemplateItem em árvore aninhada (JSON-serializable).
    Itens com filhos são automaticamente tratados como 'grupo'.
    """
    by_id = {item.id: {
        'id': item.id,
        'nome': item.nome_tarefa,
        'catalogo_id': item.subatividade_mestre_id,
        'tipo': (getattr(item.subatividade, 'tipo', None) or 'subatividade') if item.subatividade else 'subatividade',
        'quantidade_prevista': item.quantidade_prevista,
        'parent_item_id': getattr(item, 'parent_item_id', None),
        'ordem': item.ordem,
        'filhos': [],
    } for item in itens}

    raizes = []
    for node in by_id.values():
        parent_id = node['parent_item_id']
        if parent_id and parent_id in by_id:
            by_id[parent_id]['filhos'].append(node)
        else:
            raizes.append(node)

    def _fixar_e_ordenar(nodes):
        nodes.sort(key=lambda n: n['ordem'])
        for n in nodes:
            _fixar_e_ordenar(n['filhos'])
            if n['filhos']:
                n['tipo'] = 'grupo'

    _fixar_e_ordenar(raizes)
    return raizes


# ─────────────────────────────────────────────────────────────────────────────
# APLICAR TEMPLATE AO CRONOGRAMA DE UMA OBRA
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/aplicar-template', methods=['POST'])
@login_required
def aplicar_template(obra_id: int):
    """
    Aplica um template ao cronograma da obra, criando TarefaCronograma para
    cada item do template. As tarefas são inseridas sequencialmente após as
    já existentes, e o cronograma é recalculado ao final.
    """
    guard = _check_v2()
    if guard:
        flash('Funcionalidade disponível apenas no plano V2.', 'warning')
        return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id))

    admin_id = _admin_id()
    cliente_mode = _modo_cliente()
    qs = _qs_cliente(cliente_mode)
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    template_id = request.form.get('template_id', type=int)
    if not template_id:
        flash('Selecione um template.', 'warning')
        return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id) + qs)

    tmpl = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id).first()
    if not tmpl:
        flash('Template não encontrado.', 'error')
        return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id) + qs)

    # Data de início: form ou hoje
    data_inicio_str = request.form.get('data_inicio_template') or ''
    data_inicio = _parse_date(data_inicio_str) or date.today()

    # Offset de ordem para não sobrescrever tarefas existentes (no mesmo modo)
    max_ordem_row = (
        db.session.query(db.func.max(TarefaCronograma.ordem))
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente_mode)
        .scalar()
    )
    ordem_base = (max_ordem_row or 0) + 10

    try:
        from datetime import timedelta

        # Construir árvore hierárquica dos itens do template
        arvore_template = _construir_arvore_itens(list(tmpl.itens))

        # Mapa: CronogramaTemplateItem.id → TarefaCronograma.id (para setar tarefa_pai_id)
        item_id_para_tarefa_id: dict[int, int] = {}
        criadas = 0

        # Cache por id para acesso rápido a admin_id e subatividade
        item_by_id = {item.id: item for item in tmpl.itens}

        # Contador monotônico compartilhado: garante ordem única para cada tarefa
        # independente do nível de profundidade na hierarquia do template.
        ordem_seq = [0]

        def _criar_tarefas(nos: list, pai_tarefa_id, data_ref) -> object:
            """
            Cria TarefaCronograma recursivamente.
            Retorna data_após_último_filho.
            """
            nonlocal criadas
            data_corrente = data_ref
            for no in nos:
                item = item_by_id.get(no['id'])
                if item is None or item.admin_id != admin_id:
                    continue

                # Segurança: validar subatividade vinculada
                unidade = None
                quantidade = item.quantidade_prevista
                sub = item.subatividade
                if sub and sub.admin_id == admin_id:
                    unidade = sub.unidade_medida
                elif sub:
                    sub = None

                is_grupo = no['tipo'] == 'grupo'

                # Task #4 — propaga servico_id da SubatividadeMestre para
                # que tarefas criadas via "Aplicar template" também tenham
                # vínculo com o serviço (UI/custos por serviço, auto-vínculo
                # Função→Composição, etc).
                servico_id_no = sub.servico_id if sub else None
                tarefa = TarefaCronograma(
                    obra_id=obra_id,
                    nome_tarefa=item.nome_tarefa,
                    duracao_dias=item.duracao_dias,
                    data_inicio=data_corrente,
                    quantidade_total=None if is_grupo else quantidade,
                    unidade_medida=None if is_grupo else unidade,
                    responsavel=item.responsavel or 'empresa',
                    tarefa_pai_id=pai_tarefa_id,
                    ordem=ordem_base + ordem_seq[0] * 10,
                    admin_id=admin_id,
                    is_cliente=cliente_mode,
                    subatividade_mestre_id=(sub.id if sub else None),
                    servico_id=servico_id_no,
                )
                ordem_seq[0] += 1
                db.session.add(tarefa)
                db.session.flush()  # obtém tarefa.id para os filhos

                item_id_para_tarefa_id[item.id] = tarefa.id
                criadas += 1

                if no['filhos']:
                    # Filhos herdam data_corrente e têm pai = tarefa.id
                    _criar_tarefas(no['filhos'], tarefa.id, data_corrente)
                    # Data avança pela duração total dos filhos (soma)
                    duracao_filhos = sum(
                        item_by_id[f['id']].duracao_dias
                        for f in no['filhos']
                        if item_by_id.get(f['id'])
                    )
                    data_corrente = data_corrente + timedelta(days=max(duracao_filhos, item.duracao_dias))
                else:
                    data_corrente = data_corrente + timedelta(days=item.duracao_dias)

            return data_corrente

        _criar_tarefas(arvore_template, None, data_inicio)
        db.session.commit()

        # Recalcular datas do cronograma (no mesmo modo)
        recalcular_cronograma(obra_id, admin_id, cliente=cliente_mode)

        flash(
            f'Template "{tmpl.nome}" aplicado com sucesso! {criadas} tarefa(s) criada(s).',
            'success',
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO APLICAR TEMPLATE obra={obra_id} tmpl={template_id} cliente={cliente_mode}: {e}")
        flash(f'Erro ao aplicar template: {str(e)}', 'error')

    return redirect(url_for('cronograma.cronograma_obra', obra_id=obra_id) + qs)


@cronograma_bp.route('/api/templates/<int:template_id>')
@login_required
def api_template_arvore(template_id: int):
    """API JSON — retorna a árvore hierárquica de itens de um template."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    template = CronogramaTemplate.query.filter_by(id=template_id, admin_id=admin_id, ativo=True).first()
    if not template:
        return jsonify({'status': 'error', 'msg': 'Template não encontrado'}), 404

    arvore = _construir_arvore_itens(template.itens)

    def _serializar(itens):
        resultado = []
        for item in itens:
            node = {
                'id': item['id'],
                'tipo': item['tipo'],
                'nome': item['nome'],
                'ordem': item.get('ordem', 0),
                'quantidade_prevista': item.get('quantidade_prevista'),
                'catalogo_id': item.get('catalogo_id'),
                'filhos': _serializar(item.get('filhos', [])),
            }
            resultado.append(node)
        return resultado

    return jsonify({
        'status': 'ok',
        'template': {
            'id': template.id,
            'nome': template.nome,
            'categoria': template.categoria,
        },
        'arvore': _serializar(arvore),
    })


@cronograma_bp.route('/api/templates')
@login_required
def api_listar_templates():
    """API JSON — lista templates para o modal de aplicação."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()
    templates = (
        CronogramaTemplate.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(CronogramaTemplate.nome)
        .all()
    )
    return jsonify({
        'status': 'ok',
        'templates': [
            {
                'id': t.id,
                'nome': t.nome,
                'categoria': t.categoria,
                'total_itens': len(t.itens),
            }
            for t in templates
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard de Produtividade (V2)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/produtividade')
@login_required
def produtividade_dashboard():
    """Página do dashboard de produtividade de funcionários (V2)."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).order_by(Obra.nome).all()
    subatividades = (
        SubatividadeMestre.query
        .join(Servico, SubatividadeMestre.servico_id == Servico.id)
        .filter(Servico.admin_id == admin_id)
        .order_by(SubatividadeMestre.nome)
        .all()
    )
    funcionarios = (
        Funcionario.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(Funcionario.nome)
        .all()
    )
    from datetime import date as _date, timedelta as _td
    data_fim_default = _date.today()
    data_inicio_default = data_fim_default - _td(days=30)
    return render_template(
        'cronograma/produtividade.html',
        obras=obras,
        subatividades=subatividades,
        funcionarios=funcionarios,
        data_inicio_default=data_inicio_default.isoformat(),
        data_fim_default=data_fim_default.isoformat(),
    )


@cronograma_bp.route('/api/produtividade')
@login_required
def api_produtividade():
    """Endpoint JSON: agrega dados de produtividade por funcionário × subatividade."""
    guard = _check_v2()
    if guard:
        return jsonify({'status': 'error', 'msg': 'V2 only'}), 403

    admin_id = _admin_id()

    obra_id = request.args.get('obra_id', type=int)
    sub_mestre_id = request.args.get('subatividade_id', type=int)
    func_id_filtro = request.args.get('funcionario_id', type=int)
    data_inicio_str = request.args.get('data_inicio', '')
    data_fim_str = request.args.get('data_fim', '')

    from datetime import datetime as _dt

    try:
        data_inicio = _dt.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else None
    except ValueError:
        data_inicio = None
    try:
        data_fim = _dt.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else None
    except ValueError:
        data_fim = None

    # Base query: RDOMaoObra → subatividade com mestre_id → RDO finalizado
    q = (
        db.session.query(
            RDOMaoObra,
            RDOServicoSubatividade,
            RDO,
            Funcionario,
        )
        .join(RDOServicoSubatividade, RDOMaoObra.subatividade_id == RDOServicoSubatividade.id)
        .join(RDO, RDOMaoObra.rdo_id == RDO.id)
        .join(Funcionario, RDOMaoObra.funcionario_id == Funcionario.id)
        .filter(
            RDO.admin_id == admin_id,
            RDO.status == 'Finalizado',
            RDOServicoSubatividade.subatividade_mestre_id.isnot(None),
            RDOMaoObra.produtividade_real.isnot(None),
        )
    )

    if obra_id:
        q = q.filter(RDO.obra_id == obra_id)
    if sub_mestre_id:
        q = q.filter(RDOServicoSubatividade.subatividade_mestre_id == sub_mestre_id)
    if func_id_filtro:
        q = q.filter(RDOMaoObra.funcionario_id == func_id_filtro)
    if data_inicio:
        q = q.filter(RDO.data_relatorio >= data_inicio)
    if data_fim:
        q = q.filter(RDO.data_relatorio <= data_fim)

    rows = q.order_by(RDO.data_relatorio).all()

    # ── Query separada para média_empresa (sem filtro de funcionário) ──────
    # media_empresa deve refletir o desempenho de TODOS os funcionários da empresa,
    # independente do filtro de funcionario_id.
    from collections import defaultdict

    q_emp = (
        db.session.query(RDOMaoObra, RDOServicoSubatividade, RDO)
        .join(RDOServicoSubatividade, RDOMaoObra.subatividade_id == RDOServicoSubatividade.id)
        .join(RDO, RDOMaoObra.rdo_id == RDO.id)
        .filter(
            RDO.admin_id == admin_id,
            RDO.status == 'Finalizado',
            RDOServicoSubatividade.subatividade_mestre_id.isnot(None),
            RDOMaoObra.produtividade_real.isnot(None),
        )
    )
    if obra_id:
        q_emp = q_emp.filter(RDO.obra_id == obra_id)
    if sub_mestre_id:
        q_emp = q_emp.filter(RDOServicoSubatividade.subatividade_mestre_id == sub_mestre_id)
    if data_inicio:
        q_emp = q_emp.filter(RDO.data_relatorio >= data_inicio)
    if data_fim:
        q_emp = q_emp.filter(RDO.data_relatorio <= data_fim)

    rows_empresa = q_emp.all()

    # Calcular rdo_sub_totais a partir dos dados de TODA a empresa
    rdo_sub_totais: dict = {}
    for mo_e, sub_e, rdo_e in rows_empresa:
        day_key = (rdo_e.id, sub_e.id)
        if day_key not in rdo_sub_totais:
            rdo_sub_totais[day_key] = {
                'sub_mestre_id': sub_e.subatividade_mestre_id,
                'quantidade': sub_e.quantidade_produzida or 0.0,
                'horas_totais': 0.0,
            }
        rdo_sub_totais[day_key]['horas_totais'] += mo_e.horas_trabalhadas or 0.0

    # ── Agregação por (funcionario, subatividade_mestre) ──────────────────
    # Por funcionário × subatividade: média ponderada por horas individuais
    # prod_ponderada = Σ(produtividade_real × horas_pessoa) / Σ(horas_pessoa)
    agg = defaultdict(lambda: {
        'func_nome': '',
        'sub_nome': '',
        'sub_mestre_id': None,
        'meta': None,
        'unidade': '',
        'soma_prod_pond': 0.0,   # Σ(prod_real × horas_pessoa)
        'soma_indice_pond': 0.0, # Σ(indice × horas_pessoa)
        'total_horas': 0.0,      # Σ(horas_pessoa)
        'count': 0,
    })

    for mo, sub, rdo, func in rows:
        key = (func.id, sub.subatividade_mestre_id)
        h = mo.horas_trabalhadas or 0.0
        p = mo.produtividade_real or 0.0
        idx = mo.indice_produtividade or 0.0

        entry = agg[key]
        entry['func_nome'] = func.nome
        entry['sub_nome'] = sub.nome_subatividade
        entry['sub_mestre_id'] = sub.subatividade_mestre_id
        entry['meta'] = sub.meta_produtividade_snapshot
        entry['unidade'] = sub.unidade_medida_snapshot or ''
        entry['soma_prod_pond'] += p * h
        entry['soma_indice_pond'] += idx * h
        entry['total_horas'] += h
        entry['count'] += 1

    # ── Média da empresa por subatividade_mestre ───────────────────────────
    # media_empresa[sub_mestre_id] = Σ(quantidade) / Σ(horas_totais_equipe_por_dia)
    empresa_by_sub = defaultdict(lambda: {'total_qtd': 0.0, 'total_horas': 0.0})
    for d in rdo_sub_totais.values():
        k = d['sub_mestre_id']
        if k is None:
            continue
        empresa_by_sub[k]['total_qtd'] += d['quantidade']
        empresa_by_sub[k]['total_horas'] += d['horas_totais']

    media_empresa: dict = {
        str(sid): round(e['total_qtd'] / e['total_horas'], 3)
        for sid, e in empresa_by_sub.items()
        if e['total_horas'] > 0
    }

    # ── Montar ranking ─────────────────────────────────────────────────────
    ranking = []
    for (fid, sid), e in agg.items():
        h = e['total_horas']
        prod_pond = round(e['soma_prod_pond'] / h, 3) if h > 0 else 0.0
        indice_pond = round(e['soma_indice_pond'] / h, 3) if h > 0 else 0.0
        if indice_pond >= 1.0:
            badge = 'success'
        elif indice_pond >= 0.8:
            badge = 'warning'
        else:
            badge = 'danger'
        sub_mestre_str = str(sid) if sid else None
        media_emp = media_empresa.get(sub_mestre_str)
        # badge_vs_empresa: compara prod ponderada do funcionário vs média empresa
        if media_emp and media_emp > 0:
            ratio = prod_pond / media_emp
            if ratio >= 1.0:
                badge_empresa = 'success'
            elif ratio >= 0.85:
                badge_empresa = 'warning'
            else:
                badge_empresa = 'danger'
        else:
            ratio = None
            badge_empresa = 'secondary'
        ranking.append({
            'funcionario_id': fid,
            'funcionario': e['func_nome'],
            'subatividade': e['sub_nome'],
            'sub_mestre_id': sid,
            'meta': e['meta'],
            'unidade': e['unidade'],
            'total_horas': round(h, 1),
            'prod_media': prod_pond,
            'indice_medio': indice_pond,
            'media_empresa': media_emp,
            'ratio_empresa': round(ratio, 3) if ratio is not None else None,
            'badge': badge,
            'badge_empresa': badge_empresa,
            'registros': e['count'],
        })
    ranking.sort(key=lambda x: x['indice_medio'], reverse=True)

    # ── Gráfico de barras ─────────────────────────────────────────────────
    barra_labels = [r['funcionario'] for r in ranking]
    barra_prod = [r['prod_media'] for r in ranking]
    metas_distintas = {r['meta'] for r in ranking if r['meta'] is not None}
    meta_ref = metas_distintas.pop() if len(metas_distintas) == 1 else None
    # Média empresa no gráfico de barras: só faz sentido quando há uma única subatividade
    medias_empresa_distintas = {r['media_empresa'] for r in ranking if r['media_empresa'] is not None}
    media_empresa_ref = medias_empresa_distintas.pop() if len(medias_empresa_distintas) == 1 else None

    # ── Gráfico de linha: evolução diária da prod média (ponderada) ────────
    # Por dia: Σ(prod_real × horas) / Σ(horas) — para a seleção de filtros
    dia_agg = defaultdict(lambda: {'soma_pond': 0.0, 'soma_horas': 0.0})
    for mo, sub, rdo, func in rows:
        d = str(rdo.data_relatorio)
        h = mo.horas_trabalhadas or 0.0
        if mo.produtividade_real is not None and h > 0:
            dia_agg[d]['soma_pond'] += mo.produtividade_real * h
            dia_agg[d]['soma_horas'] += h

    linha_labels = sorted(dia_agg.keys())
    linha_valores = [
        round(dia_agg[d]['soma_pond'] / dia_agg[d]['soma_horas'], 3)
        if dia_agg[d]['soma_horas'] > 0 else 0
        for d in linha_labels
    ]

    # ── Agregação mensal para gráfico de evolução no perfil do funcionário ─
    mensal_agg = defaultdict(lambda: {'soma_pond': 0.0, 'soma_horas': 0.0})
    for mo, sub, rdo, func in rows:
        mes = rdo.data_relatorio.strftime('%Y-%m')
        h = mo.horas_trabalhadas or 0.0
        if mo.produtividade_real is not None and h > 0:
            mensal_agg[mes]['soma_pond'] += mo.produtividade_real * h
            mensal_agg[mes]['soma_horas'] += h

    mensal_labels = sorted(mensal_agg.keys())
    mensal_valores = [
        round(mensal_agg[m]['soma_pond'] / mensal_agg[m]['soma_horas'], 3)
        if mensal_agg[m]['soma_horas'] > 0 else 0
        for m in mensal_labels
    ]

    # ── Cards de resumo ───────────────────────────────────────────────────
    melhor = ranking[0] if ranking else None
    pior = ranking[-1] if ranking else None
    indices = [r['indice_medio'] for r in ranking if r['indice_medio'] > 0]
    media_equipe = round(sum(indices) / len(indices), 3) if indices else None

    return jsonify({
        'status': 'ok',
        'ranking': ranking,
        'media_empresa': media_empresa,
        'barra': {
            'labels': barra_labels,
            'prod': barra_prod,
            'meta': meta_ref,
            'media_empresa': media_empresa_ref,
        },
        'mensal': {
            'labels': mensal_labels,
            'valores': mensal_valores,
        },
        'linha': {
            'labels': linha_labels,
            'valores': linha_valores,
            'meta': meta_ref,
        },
        'resumo': {
            'melhor': melhor,
            'pior': pior,
            'media_equipe': media_equipe,
            'total_registros': len(rows),
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# FÍSICO-FINANCEIRO (derivado)
# ─────────────────────────────────────────────────────────────────────────────

@cronograma_bp.route('/obra/<int:obra_id>/fisico-financeiro')
@login_required
def fisico_financeiro(obra_id: int):
    # O painel agora vive na aba Financeiro da página da obra.
    from flask import redirect, url_for
    # '#financeiro' = data-hash da aba (o JS de hash→tab mapeia por data-hash, não pelo id da pane)
    return redirect(url_for('main.detalhes_obra', id=obra_id) + '#financeiro')


@cronograma_bp.route('/obra/<int:obra_id>/fisico-financeiro/export.xlsx')
@login_required
def fisico_financeiro_xlsx(obra_id: int):
    guard = _check_v2()
    if guard:
        return guard
    import io
    from services.cronograma_fisico_financeiro import (
        montar_fisico_financeiro, exportar_fisico_financeiro_xlsx,
    )
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    dados = montar_fisico_financeiro(obra_id, admin_id)
    wb = exportar_fisico_financeiro_xlsx(dados)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=f'cronograma_ff_obra_{obra_id}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
