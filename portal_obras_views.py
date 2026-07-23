"""
Blueprint: Portal do Cliente por Obra
Acesso público via token — sem login necessário.
Permite que o cliente acompanhe progresso, aprove/recuse compras
e envie comprovantes de pagamento.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from flask import (
    Blueprint, abort, current_app, flash, redirect,
    render_template, request, url_for,
)
from flask_login import login_required
from werkzeug.utils import secure_filename

from models import (
    db, Obra, TarefaCronograma, PedidoCompra, MedicaoObra, ConfiguracaoEmpresa, RDO,
    RDOFoto, RDOServicoSubatividade, RDOMaoObra, RDOEquipamento, RDOOcorrencia,
    RDOApontamentoCronograma,
    MapaConcorrencia, OpcaoConcorrencia, MapaConcorrenciaV2, RelatorioCompraMapa,
    PortalAcessoEvento,
)

logger = logging.getLogger(__name__)

portal_obras_bp = Blueprint(
    'portal_obras', __name__, url_prefix='/portal'
)

_UPLOADS_PATH_ENV = os.environ.get('UPLOADS_PATH', '')
if _UPLOADS_PATH_ENV:
    _base = _UPLOADS_PATH_ENV if os.path.isabs(_UPLOADS_PATH_ENV) else os.path.join(os.getcwd(), _UPLOADS_PATH_ENV)
    UPLOAD_FOLDER = os.path.join(_base, 'comprovantes')
else:
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads', 'comprovantes')

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.pdf'}

# Fase 3 — prazo de validade do token do portal. 180 dias é deliberadamente
# longo: token curto gera chamado de suporte a cada obra, e a equipe acaba
# desligando a expiração. 180 dias fecha a janela do ex-cliente e do link
# vazado sem atrapalhar a obra em curso. Ver decisão D4 do plano da Fase 3.
PRAZO_TOKEN_DIAS = 180


def _ensure_upload_folder():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _get_obra_by_token(token: str) -> Obra:
    """Para rotas de ação (POST): retorna a Obra ativa ou aborta com 404.

    Portal desativado é tratado como ausência para evitar mutações.

    Fase 3 — token EXPIRADO também é ausência. Até 2026-07-21 o token não
    expirava nunca (`models.py:261` é só um String(255) unique), então
    qualquer URL vazada continuava aprovando compra indefinidamente.
    Token sem data (`token_cliente_expira_em IS NULL`) continua valendo:
    são os emitidos antes da migration 247, e derrubá-los tiraria o portal
    de obra em andamento.
    """
    obra = Obra.query.filter_by(token_cliente=token, portal_ativo=True).first()
    if not obra:
        abort(404)
    if obra.token_cliente_expira_em and \
            obra.token_cliente_expira_em < datetime.utcnow():
        logger.warning('[PORTAL] token expirado usado — obra %s (expirou em %s)',
                       obra.id, obra.token_cliente_expira_em)
        abort(404)
    return obra


def _resolve_obra_for_view(token: str):
    """Para rotas GET visíveis ao cliente: se o token existe mas o portal
    está desativado, devolve uma resposta renderizando portal_inativo.html
    com o branding do tenant. Se o token não existe, aborta com 404.
    Retorna (obra, response_or_none)."""
    obra = Obra.query.filter_by(token_cliente=token).first()
    if not obra:
        abort(404)
    if obra.token_cliente_expira_em and \
            obra.token_cliente_expira_em < datetime.utcnow():
        logger.warning('[PORTAL] token expirado (GET) — obra %s', obra.id)
        abort(404)
    if not obra.portal_ativo:
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=obra.admin_id).first()
        nome_empresa = config.nome_empresa if config else 'Construtora'
        response = render_template(
            'portal/portal_inativo.html',
            obra=obra,
            config_empresa=config,
            nome_empresa=nome_empresa,
        )
        return obra, response
    return obra, None


def _registrar_acesso(obra, acao, alvo_tipo=None, alvo_id=None, detalhes=None):
    """Grava PortalAcessoEvento com IP e user-agent. NÃO commita.

    Nunca levanta: uma falha de auditoria não pode impedir o cliente de
    aprovar uma compra — mas o log fica, para que a falha apareça.

    `X-Forwarded-For` vem primeiro porque a aplicação roda atrás de proxy
    (EasyPanel); sem isso, todo evento registraria o IP do proxy.
    """
    try:
        encaminhado = request.headers.get('X-Forwarded-For', '')
        ip = (encaminhado.split(',')[0].strip() if encaminhado
              else (request.remote_addr or ''))[:64]
        db.session.add(PortalAcessoEvento(
            obra_id=obra.id,
            admin_id=obra.admin_id,
            acao=acao,
            alvo_tipo=alvo_tipo,
            alvo_id=alvo_id,
            ip=ip or None,
            user_agent=(request.headers.get('User-Agent') or '')[:300] or None,
            detalhes=detalhes,
        ))
    except Exception as e:
        logger.error('[PORTAL] falha ao registrar trilha de acesso: %s', e)


@portal_obras_bp.route('/obra/<token>')
def portal_obra(token: str):
    obra, inactive_response = _resolve_obra_for_view(token)
    if inactive_response is not None:
        return inactive_response

    obra.ultima_visualizacao_cliente = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    admin_id = obra.admin_id

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    total_tarefas = len(tarefas)
    # Progresso geral: mesma métrica do cronograma/card de RDO —
    # calcular_progresso_geral_obra_v2 (média das FOLHAS ponderada por duração,
    # acumulada até hoje), em vez da média simples de todas as tarefas (que
    # dupla-conta os pais). Ver specs de 2026-06-30 (progresso-obra-no-card-rdo).
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    perc_geral = calcular_progresso_geral_obra_v2(
        obra.id, date.today(), admin_id)['progresso_geral_pct']

    # Cronograma do cliente: agora vive em TarefaCronograma com is_cliente=True
    # (migration #117). Constrói a árvore hierárquica (serviço → grupo →
    # subatividade) usando tarefa_pai_id e a expõe ao template já agrupada
    # para renderização com <details>/<summary> (collapse nativo).
    from types import SimpleNamespace
    _tarefas_cliente = (
        TarefaCronograma.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, is_cliente=True)
        .order_by(TarefaCronograma.ordem)
        .all()
    )

    # Progresso REAL das tarefas internas (is_cliente=False), sincronizado dos RDOs,
    # indexado por nome. O cronograma do cliente (is_cliente=True) NÃO recebe sync de
    # RDO — suas folhas ficariam congeladas (ex.: 0% mesmo com o serviço concluído).
    # Refletimos aqui o % da tarefa interna de mesmo nome para o portal mostrar o
    # avanço real; sem correspondente, mantém o próprio percentual.
    _sync_por_nome = {
        t.nome_tarefa: (t.percentual_concluido or 0.0)
        for t in tarefas if not t.is_cliente
    }

    def _make_node(t):
        return SimpleNamespace(
            id=t.id,
            tarefa_pai_id=t.tarefa_pai_id,
            nome_tarefa=t.nome_tarefa,
            percentual_apresentacao=_sync_por_nome.get(
                t.nome_tarefa, t.percentual_concluido or 0.0),
            data_inicio_apresentacao=t.data_inicio,
            data_fim_apresentacao=t.data_fim,
            ordem=t.ordem,
            filhos=[],
        )

    _nodes_by_id = {t.id: _make_node(t) for t in _tarefas_cliente}
    cronograma_cliente_tree = []
    for t in _tarefas_cliente:
        node = _nodes_by_id[t.id]
        if t.tarefa_pai_id and t.tarefa_pai_id in _nodes_by_id:
            _nodes_by_id[t.tarefa_pai_id].filhos.append(node)
        else:
            cronograma_cliente_tree.append(node)
    # Linha raiz do cronograma do portal mostra o MESMO número do anel
    # (perc_geral = calcular_progresso_geral_obra_v2), não o rollup hierárquico
    # persistido na raiz — consistente com o cronograma interno. Só quando há uma
    # única raiz (o nó "OBRA"); com múltiplos topos cada um mantém o seu.
    if len(cronograma_cliente_tree) == 1:
        cronograma_cliente_tree[0].percentual_apresentacao = perc_geral

    # Total de tarefas (folhas + nós) para o counter da seção; mantém compat.
    cronograma_cliente = list(_tarefas_cliente)

    compras_pendentes = (
        PedidoCompra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .filter(PedidoCompra.tipo_compra == 'aprovacao_cliente')
        .filter(
            db.or_(
                PedidoCompra.status_aprovacao_cliente == 'AGUARDANDO_APROVACAO_CLIENTE',
                PedidoCompra.status_aprovacao_cliente == 'PENDENTE',
                PedidoCompra.status_aprovacao_cliente.is_(None),
            )
        )
        .order_by(PedidoCompra.created_at.desc())
        .all()
    )

    compras_resolvidas = (
        PedidoCompra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .filter(PedidoCompra.status_aprovacao_cliente.in_(['APROVADO', 'RECUSADO']))
        .order_by(PedidoCompra.created_at.desc())
        .all()
    )

    rdos = (
        RDO.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, status='Finalizado')
        .order_by(RDO.data_relatorio.desc())
        .limit(20)
        .all()
    )

    medicoes = (
        MedicaoObra.query
        .filter_by(obra_id=obra.id, admin_id=admin_id)
        .order_by(MedicaoObra.numero.desc())
        .all()
    )

    from models import ContaReceber
    medicao_contas = {}
    for m in medicoes:
        if m.conta_receber_id:
            cr = ContaReceber.query.get(m.conta_receber_id)
            if cr:
                medicao_contas[m.id] = cr

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config.nome_empresa if config else 'Construtora'

    # Mapas V2 — separados em abertos (aguardando aprovação cliente) e concluídos
    mapas_v2_abertos = (
        MapaConcorrenciaV2.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, status='aberto')
        .order_by(MapaConcorrenciaV2.created_at.desc())
        .all()
    )
    mapas_v2_concluidos = (
        MapaConcorrenciaV2.query
        .filter_by(obra_id=obra.id, admin_id=admin_id, status='concluido')
        .order_by(MapaConcorrenciaV2.created_at.desc())
        .all()
    )
    # ── helpers para Mapa V2 ──────────────────────────────────────────────────
    def _prazo_to_days(prazo_str: str) -> float:
        """Normaliza prazo textual para número de dias (menor = melhor).
        Suporta: '15 dias', '2 semanas', '1 mês', '30', '2026-06-01', '15/06/2026'."""
        import re
        if not prazo_str:
            return float('inf')
        s = prazo_str.strip().lower()
        # Tentar data ISO ou BR → dias até hoje
        try:
            from datetime import date as _date
            if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
                d = _date.fromisoformat(s)
            elif re.match(r'^\d{2}/\d{2}/\d{4}$', s):
                day, month, year = s.split('/')
                d = _date(int(year), int(month), int(day))
            else:
                d = None
            if d:
                return max(0, (d - _date.today()).days)
        except Exception:
            pass
        # Extrair primeiro número
        nums = re.findall(r'\d+(?:[.,]\d+)?', s)
        if not nums:
            return float('inf')
        num = float(nums[0].replace(',', '.'))
        if 'semana' in s or 'week' in s:
            return num * 7
        if 'mes' in s or 'mês' in s or 'month' in s:
            return num * 30
        return num  # assume dias

    def _build_v2_context(mapa_list):
        """Constrói dicts de contexto para renderização de mapas V2.

        Task #21: prazo agora vive em MapaFornecedor.prazo_entrega.
        min_prazo_map = fornecedor com menor prazo (calculado uma vez por mapa).
        Cada item passa a referenciar fornecedor_escolhido_id.
        """
        result = []
        for mapa in mapa_list:
            cotacoes_map = {}
            for cot in mapa.cotacoes:
                cotacoes_map.setdefault(cot.item_id, {})[cot.fornecedor_id] = cot

            # Menor prazo entre fornecedores (válido para o mapa todo)
            best_prazo_days = None
            best_prazo_forn = None
            for forn in mapa.fornecedores:
                p = (forn.prazo_entrega or '').strip()
                if not p:
                    continue
                days = _prazo_to_days(p)
                if days < float('inf') and (best_prazo_days is None or days < best_prazo_days):
                    best_prazo_days = days
                    best_prazo_forn = forn.id

            min_val_map = {}    # {item_id: forn_id com menor valor}
            min_prazo_map = {}  # {item_id: forn_id com menor prazo (mesmo p/ todos)}

            for item in mapa.itens:
                item_cots = cotacoes_map.get(item.id, {})
                best_val = None
                best_val_forn = None
                for forn in mapa.fornecedores:
                    cot = item_cots.get(forn.id)
                    if not cot or not cot.valor_unitario:
                        continue
                    v = float(cot.valor_unitario)
                    if v > 0 and (best_val is None or v < best_val):
                        best_val = v
                        best_val_forn = forn.id
                if best_val_forn:
                    min_val_map[item.id] = best_val_forn
                if best_prazo_forn:
                    min_prazo_map[item.id] = best_prazo_forn

            relatorios = (
                RelatorioCompraMapa.query
                .filter_by(mapa_id=mapa.id)
                .order_by(RelatorioCompraMapa.versao.desc())
                .all()
            )

            result.append({
                'mapa': mapa,
                'fornecedores': mapa.fornecedores,
                'itens': mapa.itens,
                'cotacoes_map': cotacoes_map,
                'min_val_map': min_val_map,
                'min_prazo_map': min_prazo_map,
                'relatorios': relatorios,
            })
        return result

    mapas_v2_abertos_ctx = _build_v2_context(mapas_v2_abertos)
    mapas_v2_concluidos_ctx = _build_v2_context(mapas_v2_concluidos)

    return render_template(
        'portal/portal_obra.html',
        obra=obra,
        tarefas=tarefas,
        cronograma_cliente=cronograma_cliente,
        cronograma_cliente_tree=cronograma_cliente_tree,
        perc_geral=round(perc_geral, 1),
        compras_pendentes=compras_pendentes,
        compras_resolvidas=compras_resolvidas,
        rdos=rdos,
        medicoes=medicoes,
        medicao_contas=medicao_contas,
        nome_empresa=nome_empresa,
        config_empresa=config,
        hoje=date.today(),
        mapas_v2_abertos_ctx=mapas_v2_abertos_ctx,
        mapas_v2_concluidos_ctx=mapas_v2_concluidos_ctx,
    )


# Fase 0.6 / D2 — estados a partir dos quais o cliente ainda pode decidir.
# São exatamente os que a listagem de pendentes oferece (`:165-171`): se a
# compra não está numa destas, o portal não deveria estar mostrando botão.
_STATUS_COMPRA_DECIDIVEL = (None, 'PENDENTE', 'AGUARDANDO_APROVACAO_CLIENTE')


def _get_compra_do_portal(obra, compra_id: int) -> PedidoCompra:
    """Fase 0.6 / D2 — a compra tem que ser uma que o portal de fato oferece.

    Antes, `aprovar_compra` e `recusar_compra` filtravam só `id` e `obra_id`.
    Faltavam as duas restrições que a listagem já aplicava e que as rotas de
    mapa deste mesmo arquivo (`:436`, `:551`) sempre aplicaram:

    - **tenant**: `admin_id` da obra;
    - **tipo**: só `aprovacao_cliente` é apresentada ao cliente. Uma compra
      `tipo_compra='normal'` carimbada como APROVADO passava a aparecer em
      `compras_resolvidas` (`:177`), que não filtra tipo — compra interna
      vazando no portal do cliente.

    404 (e não 403) porque, para o portal, o que ele não oferece não existe:
    responder 403 confirmaria que aquele id pertence à obra.
    """
    return PedidoCompra.query.filter_by(
        id=compra_id,
        obra_id=obra.id,
        admin_id=obra.admin_id,
        tipo_compra='aprovacao_cliente',
    ).first_or_404()


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/aprovar', methods=['POST'])
def aprovar_compra(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = _get_compra_do_portal(obra, compra_id)

    # Fase 3 — trilha do POST anônimo (IP/UA). Persistida no commit adiante.
    _registrar_acesso(obra, 'compra_aprovar', 'pedido_compra', compra_id,
                      {'valor_total': str(compra.valor_total)})

    # Já aprovada? idempotente
    if compra.status_aprovacao_cliente == 'APROVADO':
        flash('Esta compra já foi aprovada.', 'info')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    # Fase 0.6 / D2 — desfazer a própria recusa não é ação de portal.
    # Sem esta guarda, um POST anônimo levava uma compra RECUSADA de volta a
    # APROVADO e, aí sim, `processar_compra_aprovada_cliente` criava
    # `GestaoCustoPai` com status='PAGO' e movimentava o almoxarifado
    # (medido em 21/07). Reabrir a decisão é ação de gestor, autenticada.
    if compra.status_aprovacao_cliente not in _STATUS_COMPRA_DECIDIVEL:
        logger.warning(
            f"[PORTAL] Tentativa de aprovar compra {compra_id} em estado "
            f"{compra.status_aprovacao_cliente!r} — obra {obra.id}. Recusado."
        )
        flash(
            'Esta compra já foi recusada. Fale com a empresa para reabri-la.',
            'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    try:
        compra.status_aprovacao_cliente = 'APROVADO'

        # ── Fase 3 ────────────────────────────────────────────────────────
        # Com a governança de compras ligada, a decisão do cliente é
        # CIÊNCIA, não lançamento. O que criava GestaoCustoPai com
        # status='PAGO' aqui era um POST sem autenticação nenhuma
        # (o portal é anônimo por construção — ver o docstring do módulo),
        # e o movimento de almoxarifado saía atribuído ao ADMIN do tenant,
        # que não fez a ação.
        #
        # Com a flag ligada, quem emite o custo é a cadeia interna de
        # alçada (compras.requisicao_emitir_pedido), onde existe usuário
        # autenticado, papel na obra e trilha em requisicao_transicao.
        from scripts.flag_compras_governanca import governanca_ativa

        sob_governanca = governanca_ativa(obra.admin_id)

        if sob_governanca:
            _registrar_acesso(
                obra, 'compra_aprovar', 'pedido_compra', compra_id,
                {'modo': 'ciencia', 'valor_total': str(compra.valor_total)})
            db.session.commit()
            logger.info('[PORTAL] Compra %s — ciência do cliente registrada '
                        '(governança ativa; custo NÃO gerado aqui). Obra %s',
                        compra_id, obra.id)
            flash('Sua aprovação foi registrada. A compra segue para '
                  'liberação interna antes de ser efetivada.', 'success')
            return redirect(url_for('portal_obras.portal_obra', token=token))

        # Comportamento anterior à Fase 3, preservado com a flag desligada.
        # Gera agora os custos (FATURAMENTO_DIRETO sem FluxoCaixa) + entrada
        # + saída no almoxarifado. O tipo já foi garantido na query.
        if compra.tipo_compra == 'aprovacao_cliente' and not compra.processada_apos_aprovacao:
            from compras_views import processar_compra_aprovada_cliente
            # usuario_id = admin do tenant: o portal é anônimo e não tem
            # current_user. A autoria fica atribuída a quem não agiu — só a
            # Fase 9a (identidade do portal) resolve isso de verdade.
            processar_compra_aprovada_cliente(compra, usuario_id=compra.admin_id)

        db.session.commit()
        logger.info(
            f"[PORTAL] Compra {compra_id} APROVADA pelo cliente — obra {obra.id} "
            f"tipo={compra.tipo_compra} processada={compra.processada_apos_aprovacao}"
        )
        flash('Compra aprovada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PORTAL] Erro ao aprovar compra {compra_id}: {e}", exc_info=True)
        flash(f'Erro ao aprovar compra: {e}', 'danger')

    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/recusar', methods=['POST'])
def recusar_compra(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = _get_compra_do_portal(obra, compra_id)

    _registrar_acesso(obra, 'compra_recusar', 'pedido_compra', compra_id)

    if compra.status_aprovacao_cliente == 'RECUSADO':
        flash('Esta compra já foi recusada.', 'info')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    # Fase 0.6 / D2 — mesma simetria da aprovação: uma compra já aprovada (e
    # possivelmente já custeada e baixada do almoxarifado) não é estornada por
    # POST anônimo. O estorno é operação de gestor.
    if compra.status_aprovacao_cliente not in _STATUS_COMPRA_DECIDIVEL:
        logger.warning(
            f"[PORTAL] Tentativa de recusar compra {compra_id} em estado "
            f"{compra.status_aprovacao_cliente!r} — obra {obra.id}. Recusado."
        )
        flash(
            'Esta compra já foi aprovada. Fale com a empresa para estorná-la.',
            'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    compra.status_aprovacao_cliente = 'RECUSADO'
    db.session.commit()
    logger.info(f"[PORTAL] Compra {compra_id} RECUSADA pelo cliente — obra {obra.id}")
    flash('Compra recusada.', 'warning')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/comprovante', methods=['POST'])
def upload_comprovante(token: str, compra_id: int):
    obra = _get_obra_by_token(token)
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()

    _registrar_acesso(obra, 'compra_comprovante', 'pedido_compra', compra_id)

    if compra.status_aprovacao_cliente != 'APROVADO':
        flash('Comprovante só pode ser enviado para compras aprovadas.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    arquivo = request.files.get('comprovante')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    ext = os.path.splitext(secure_filename(arquivo.filename))[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash('Tipo de arquivo não permitido. Envie imagem ou PDF.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    max_bytes = current_app.config.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)
    arquivo.seek(0, 2)
    file_size = arquivo.tell()
    arquivo.seek(0)
    if file_size > max_bytes:
        flash(f'Arquivo muito grande. O limite é {max_bytes // (1024 * 1024)} MB.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    _ensure_upload_folder()
    nome_seguro = f"comprovante_{compra_id}_{secrets.token_hex(8)}{ext}"
    caminho = os.path.join(UPLOAD_FOLDER, nome_seguro)
    arquivo.save(caminho)

    rel_path = os.path.relpath(caminho, os.getcwd()).replace('\\', '/')
    if rel_path.startswith('static/'):
        compra.comprovante_pagamento_url = '/' + rel_path
    else:
        filename_only = os.path.basename(caminho)
        compra.comprovante_pagamento_url = f'/persistent-uploads/comprovantes/{filename_only}'
    db.session.commit()
    logger.info(f"[PORTAL] Comprovante enviado para compra {compra_id} — obra {obra.id}")
    flash('Comprovante enviado com sucesso!', 'success')
    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/mapa/<int:mapa_id>/aprovar', methods=['POST'])
def aprovar_mapa_concorrencia(token: str, mapa_id: int):
    """O cliente seleciona a opção preferida no Mapa de Concorrência."""
    obra = _get_obra_by_token(token)
    mapa = MapaConcorrencia.query.filter_by(
        id=mapa_id, obra_id=obra.id, admin_id=obra.admin_id
    ).first_or_404()

    _registrar_acesso(obra, 'mapa_v1_aprovar', 'mapa_concorrencia', mapa_id)

    if mapa.status != 'pendente':
        flash('Este mapa de concorrência já foi concluído e não pode ser alterado.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    opcao_id = request.form.get('opcao_id', type=int)
    if not opcao_id:
        flash('Selecione uma opção de fornecedor.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    opcao = OpcaoConcorrencia.query.filter_by(id=opcao_id, mapa_id=mapa.id).first()
    if not opcao:
        flash('Opção não encontrada.', 'danger')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    for op in mapa.opcoes.all():
        op.selecionada = False

    opcao.selecionada = True
    mapa.status = 'concluido'
    try:
        db.session.commit()
        logger.info(f"[PORTAL] Mapa {mapa_id} aprovado pelo cliente — opção {opcao_id}, obra {obra.id}")
        flash(f'Fornecedor "{opcao.fornecedor_nome}" selecionado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PORTAL] Erro ao aprovar mapa {mapa_id}: {e}")
        flash('Erro ao registrar aprovação. Tente novamente.', 'danger')

    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<int:obra_id>/portal-toggle', methods=['POST'])
@login_required
def toggle_portal(obra_id: int):
    from utils.tenant import get_tenant_admin_id
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    obra.portal_ativo = not obra.portal_ativo

    if obra.portal_ativo:
        # Fase 3 — rotacionar o token e carimbar a validade a cada vez que
        # o portal é (re)aberto. Antes, o token era gerado uma vez e valia
        # para sempre; reabrir o portal reaproveitava a MESMA URL, o que
        # tornava o "desligar o portal" uma revogação apenas temporária.
        if not obra.token_cliente:
            obra.token_cliente = secrets.token_urlsafe(32)
        obra.token_cliente_expira_em = (
            datetime.utcnow() + timedelta(days=PRAZO_TOKEN_DIAS))

    db.session.commit()
    status = 'ativado' if obra.portal_ativo else 'desativado'
    logger.info(f"[PORTAL] Portal {status} para obra {obra_id}")
    flash(f'Portal do cliente {status}.', 'success')
    return redirect(url_for('main.detalhes_obra', id=obra_id))


@portal_obras_bp.route('/obra/<int:obra_id>/medicao/gerar', methods=['POST'])
@login_required
def gerar_medicao(obra_id: int):
    from utils.tenant import get_tenant_admin_id
    admin_id = get_tenant_admin_id()

    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    ultima = (
        MedicaoObra.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(MedicaoObra.numero.desc())
        .first()
    )
    proximo_numero = (ultima.numero + 1) if ultima else 1

    if date.today().day <= 15:
        data_inicio_med = date.today().replace(day=1)
        data_fim_med = date.today().replace(day=15)
    else:
        import calendar
        data_inicio_med = date.today().replace(day=16)
        ultimo_dia = calendar.monthrange(date.today().year, date.today().month)[1]
        data_fim_med = date.today().replace(day=ultimo_dia)

    tarefas_empresa = TarefaCronograma.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, responsavel='empresa'
    ).all()

    total = len(tarefas_empresa)
    perc = (sum(t.percentual_concluido or 0 for t in tarefas_empresa) / total) if total else 0.0

    valor_medido = 0
    if obra.valor_contrato and obra.valor_contrato > 0:
        valor_medido = round(float(obra.valor_contrato) * perc / 100, 2)

    med = MedicaoObra(
        obra_id=obra_id,
        numero=proximo_numero,
        data_medicao=date.today(),
        data_inicio=data_inicio_med,
        data_fim=data_fim_med,
        periodo_inicio=data_inicio_med,
        periodo_fim=data_fim_med,
        percentual_executado=round(perc, 2),
        valor_medido=valor_medido,
        status='PENDENTE',
        admin_id=admin_id,
    )
    db.session.add(med)
    db.session.commit()
    logger.info(f"[MEDICAO] #{proximo_numero} gerada para obra {obra_id}")
    flash(f'Medição #{proximo_numero} gerada com sucesso!', 'success')
    return redirect(url_for('main.detalhes_obra', id=obra_id))


@portal_obras_bp.route('/obra/<token>/mapa-v2/<int:mapa_id>/selecionar', methods=['POST'])
def selecionar_mapa_v2(token: str, mapa_id: int):
    """O cliente confirma a seleção de fornecedores para cada item do Mapa V2."""
    obra = _get_obra_by_token(token)
    mapa = MapaConcorrenciaV2.query.filter_by(
        id=mapa_id, obra_id=obra.id, admin_id=obra.admin_id
    ).first_or_404()

    _registrar_acesso(obra, 'mapa_v2_selecionar', 'mapa_concorrencia_v2', mapa_id)

    if mapa.status == 'concluido':
        flash('Este mapa já foi aprovado e não pode ser alterado.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    # Conjuntos de IDs válidos deste mapa (previne manipulação de form)
    itens_validos = {item.id for item in mapa.itens}
    forns_validos = {forn.id for forn in mapa.fornecedores}

    if not itens_validos:
        flash('Este mapa não possui itens cadastrados.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    # Coletar seleções do formulário e validar
    selecoes = {}  # {item_id: forn_id}
    for key, val in request.form.items():
        if key.startswith('sel_'):
            try:
                item_id = int(key[4:])
                forn_id = int(val)
            except (ValueError, TypeError):
                continue
            # Validar que item e fornecedor pertencem a este mapa
            if item_id in itens_validos and forn_id in forns_validos:
                selecoes[item_id] = forn_id

    # Exigir seleção para todos os itens com pelo menos uma cotação > 0
    itens_com_cotacao = set()
    for cot in mapa.cotacoes:
        if cot.valor_unitario and float(cot.valor_unitario) > 0:
            itens_com_cotacao.add(cot.item_id)

    itens_sem_selecao = itens_com_cotacao - selecoes.keys()
    if itens_sem_selecao:
        flash('Selecione um fornecedor para todos os itens antes de confirmar.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    try:
        # Aplicar seleções: desmarcar todas, marcar as escolhidas
        for cot in mapa.cotacoes:
            cot.selecionado = (
                cot.item_id in selecoes and cot.fornecedor_id == selecoes[cot.item_id]
            )

        # Task #21 — espelhar a escolha do cliente em
        # MapaItemCotacao.fornecedor_escolhido_id (fonte canônica nova).
        # Limpa explicitamente itens não selecionados para evitar estado obsoleto.
        for item in mapa.itens:
            item.fornecedor_escolhido_id = selecoes.get(item.id)

        mapa.status = 'concluido'
        db.session.commit()
        logger.info(
            f"[PORTAL] Mapa V2 {mapa_id} aprovado pelo cliente — obra {obra.id}, "
            f"{len(selecoes)} seleções registradas"
        )
        flash('Relatório gerado! Fornecedores selecionados registrados com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PORTAL] Erro ao selecionar mapa_v2 {mapa_id}: {e}")
        flash('Erro ao registrar seleção. Tente novamente.', 'danger')

    return redirect(url_for('portal_obras.portal_obra', token=token))


@portal_obras_bp.route('/obra/<token>/mapa-v2/<int:mapa_id>/relatorio/<int:rel_id>/baixar')
def baixar_relatorio_mapa_v2_portal(token: str, mapa_id: int, rel_id: int):
    """Download de PDF de Relatório de Compra pelo portal do cliente."""
    from flask import send_from_directory, abort, current_app
    obra = _get_obra_by_token(token)
    rel = (
        RelatorioCompraMapa.query
        .filter_by(id=rel_id, mapa_id=mapa_id, obra_id=obra.id, admin_id=obra.admin_id)
        .first()
    )
    if not rel:
        abort(404)
    static_root = os.path.join(current_app.root_path, 'static')
    abs_dir = os.path.dirname(os.path.join(static_root, rel.arquivo_path))
    return send_from_directory(
        abs_dir, os.path.basename(rel.arquivo_path),
        as_attachment=False, download_name=rel.arquivo_nome,
    )


@portal_obras_bp.route('/obra/<token>/rdo/<int:rdo_id>')
def portal_rdo_detalhe(token: str, rdo_id: int):
    obra, inactive_response = _resolve_obra_for_view(token)
    if inactive_response is not None:
        return inactive_response
    admin_id = obra.admin_id

    rdo = RDO.query.filter_by(id=rdo_id, obra_id=obra.id, admin_id=admin_id).first()
    if not rdo:
        abort(404)

    fotos = RDOFoto.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).order_by(RDOFoto.ordem).all()
    subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).order_by(RDOServicoSubatividade.ordem_execucao).all()

    # Fallback: RDOs criados via cronograma (import/seed) não têm
    # RDOServicoSubatividade — as atividades do dia ficam nos apontamentos do
    # cronograma. Deriva a mesma estrutura que o template espera (nome + % anterior/
    # incremento/atual) para a seção "Serviços / atividades" não aparecer vazia.
    if not subatividades:
        apontamentos = (
            RDOApontamentoCronograma.query
            .filter_by(rdo_id=rdo.id, admin_id=admin_id)
            .all()
        )
        derivadas = []
        for ap in apontamentos:
            tarefa = db.session.get(TarefaCronograma, ap.tarefa_cronograma_id)
            if tarefa is None:
                continue
            atual = (ap.percentual_acumulado
                     if ap.percentual_acumulado is not None
                     else (ap.percentual_realizado or 0.0))
            if ap.percentual_incremento_dia is not None:
                # M07: linhas novas trazem o incremento PERSISTIDO — a
                # derivação em memória fica só como fallback legado.
                incremento = max(0.0, round(float(ap.percentual_incremento_dia), 2))
                anterior = round(float(atual) - float(ap.percentual_incremento_dia), 2)
            else:
                # Fallback (linhas pré-M02 sem backfill): % anterior = último
                # acumulado da MESMA tarefa em um RDO anterior desta obra.
                ant_ap = (
                    RDOApontamentoCronograma.query
                    .join(RDO, RDOApontamentoCronograma.rdo_id == RDO.id)
                    .filter(
                        RDOApontamentoCronograma.tarefa_cronograma_id == ap.tarefa_cronograma_id,
                        RDOApontamentoCronograma.admin_id == admin_id,
                        RDO.obra_id == obra.id,
                        RDO.data_relatorio < rdo.data_relatorio,
                    )
                    .order_by(RDO.data_relatorio.desc())
                    .first()
                )
                anterior = (ant_ap.percentual_realizado or 0.0) if ant_ap else 0.0
                incremento = max(0.0, round(atual - anterior, 2))
            # Só entra no RDO do dia a atividade que efetivamente avançou; tarefas
            # que só arrastam o acumulado (incremento 0%) não são "atividade do dia".
            if incremento <= 0:
                continue
            derivadas.append(SimpleNamespace(
                nome_subatividade=tarefa.nome_tarefa,
                descricao_subatividade=None,
                observacoes_tecnicas=None,
                percentual_anterior=anterior,
                incremento_dia=incremento,
                percentual_conclusao=atual,
                ordem_execucao=tarefa.ordem or 0,
            ))
        subatividades = sorted(derivadas, key=lambda s: s.ordem_execucao)
    mao_obra = RDOMaoObra.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()
    equipamentos = RDOEquipamento.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()
    ocorrencias = RDOOcorrencia.query.filter_by(rdo_id=rdo.id, admin_id=admin_id).all()

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    nome_empresa = config.nome_empresa if config else 'Construtora'

    return render_template(
        'portal/portal_rdo_detalhe.html',
        obra=obra,
        rdo=rdo,
        fotos=fotos,
        subatividades=subatividades,
        mao_obra=mao_obra,
        equipamentos=equipamentos,
        ocorrencias=ocorrencias,
        nome_empresa=nome_empresa,
        config_empresa=config,
        token=token,
    )
