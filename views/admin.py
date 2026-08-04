from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, Usuario, TipoUsuario, Funcionario, RegistroPonto
from auth import super_admin_required, admin_required
from utils.tenant import get_tenant_admin_id
from datetime import datetime
import logging
import traceback

from views import main_bp

logger = logging.getLogger(__name__)

@main_bp.route('/super-admin')
@super_admin_required
def super_admin_dashboard():
    admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).all()
    total_admins = len(admins)
    
    return render_template('super_admin_dashboard.html', 
                         admins=admins, 
                         total_admins=total_admins)

@main_bp.route('/super-admin/criar-admin', methods=['POST'])
@super_admin_required
def criar_admin():
    """Cria novo administrador (apenas superadmin pode criar)"""
    try:
        nome = request.form.get('nome')
        username = request.form.get('username')
        email = request.form.get('email')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not all([nome, username, email, senha, confirmar_senha]):
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        if Usuario.query.filter_by(email=email).first():
            flash(f'Email {email} já está cadastrado.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        if Usuario.query.filter_by(username=username).first():
            flash(f'Username {username} já está cadastrado.', 'danger')
            return redirect(url_for('main.super_admin_dashboard'))
        
        versao_sistema = request.form.get('versao_sistema', 'v1')
        if versao_sistema not in ('v1', 'v2'):
            versao_sistema = 'v1'
        
        novo_admin = Usuario(
            nome=nome,
            username=username,
            email=email,
            password_hash=generate_password_hash(senha),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema=versao_sistema
        )
        
        db.session.add(novo_admin)
        db.session.commit()

        try:
            from models import CategoriaEscritorio, CategoriaFluxoCaixa, CategoriaFornecedor, CategoriaReembolso
            CategoriaEscritorio.seed_defaults(novo_admin.id)
            CategoriaFluxoCaixa.seed_defaults(novo_admin.id)
            CategoriaFornecedor.seed_defaults(novo_admin.id)
            CategoriaReembolso.seed_defaults(novo_admin.id)
            db.session.commit()
            logger.info(f"[OK] Categorias padrão criadas para admin {novo_admin.id}")
        except Exception as _seed_err:
            db.session.rollback()
            logger.warning(f"[WARN] Seed categorias falhou para admin {novo_admin.id}: {_seed_err}")

        try:
            from services.dropdown_service import seed_grupos_sistema
            seed_grupos_sistema(novo_admin.id, commit=True)
            logger.info(f"[OK] Grupos de dropdown seeded para admin {novo_admin.id}")
        except Exception as _ddseed_err:
            logger.warning(f"[WARN] Seed dropdown_service falhou para admin {novo_admin.id}: {_ddseed_err}")

        flash(f'Administrador {nome} criado com sucesso!', 'success')
        logger.info(f"[OK] SUPER ADMIN: Novo admin criado - {nome} ({email})")
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar administrador: {str(e)}', 'danger')
        logger.error(f"[ERROR] ERRO criar_admin: {e}")
    
    return redirect(url_for('main.super_admin_dashboard'))

@main_bp.route('/novo_ponto', methods=['POST'])
@login_required
def novo_ponto():
    """Cria novo registro de ponto"""
    try:
        data = request.form.to_dict()
        logger.debug(f"[CONFIG] DEBUG novo_ponto: Dados recebidos: {data}")
        
        funcionario_id = data.get('funcionario_id')
        if not funcionario_id:
            logger.error(f"[ERROR] DEBUG novo_ponto: funcionario_id não informado")
            return jsonify({'success': False, 'message': 'Funcionário não informado'}), 400
        
        admin_id = get_tenant_admin_id()
        if not admin_id:
            logger.error(f"[ERROR] DEBUG novo_ponto: admin_id não identificado")
            return jsonify({'success': False, 'message': 'Admin não identificado'}), 403
        
        logger.debug(f"[CONFIG] DEBUG novo_ponto: admin_id={admin_id}, funcionario_id={funcionario_id}")
        
        funcionario = Funcionario.query.filter_by(id=funcionario_id, admin_id=admin_id).first()
        if not funcionario:
            logger.error(f"[ERROR] DEBUG novo_ponto: funcionario não encontrado para id={funcionario_id}, admin_id={admin_id}")
            return jsonify({'success': False, 'message': 'Funcionário não encontrado'}), 404
        
        obra_id = data.get('obra_id')
        if obra_id and obra_id.strip():
            obra_id = int(obra_id)
        else:
            obra_id = None
        
        def parse_time(time_str):
            if not time_str:
                return None
            time_str = time_str.strip()
            for fmt in ['%H:%M', '%I:%M %p', '%I:%M%p']:
                try:
                    return datetime.strptime(time_str, fmt).time()
                except ValueError:
                    continue
            logger.warning(f"[WARN] DEBUG novo_ponto: Formato de hora inválido: {time_str}")
            return None
        
        logger.debug(f"[CONFIG] DEBUG novo_ponto: Processando horários...")
        hora_entrada = parse_time(data.get('hora_entrada'))
        hora_saida = parse_time(data.get('hora_saida'))
        hora_almoco_saida = parse_time(data.get('hora_almoco_saida'))
        hora_almoco_retorno = parse_time(data.get('hora_almoco_retorno'))
        
        logger.debug(f"[CONFIG] DEBUG novo_ponto: hora_entrada={hora_entrada}, hora_saida={hora_saida}")
        logger.debug(f"[CONFIG] DEBUG novo_ponto: hora_almoco_saida={hora_almoco_saida}, hora_almoco_retorno={hora_almoco_retorno}")
        
        data_registro = datetime.strptime(data.get('data'), '%Y-%m-%d').date()

        # ── B1.7 — a rota REUSA o registro do dia em vez de criar sempre ──────
        # Esta era a única de DEZ criadoras de `RegistroPonto` fora de
        # `archive/` e `tests/` que não consultava antes de criar. As outras
        # nove reusam (`ponto_service.py:105-118` e `:326-350`,
        # `ponto_views.py:1483-1500`, `:1642-1656`, `:2362-2382`,
        # `views/api.py:337-343` e `:732-737`, `models.py:4562` e `:4777`) — o
        # consenso delas é a prova de que a invariante da casa é UM registro por
        # (funcionário, data). O modelo diz o mesmo: há UM `hora_entrada`, UM
        # `hora_saida` e UM par de almoço (`models.py:759-763`); não existe
        # coluna de turno nem de sequência.
        registro = RegistroPonto.query.filter_by(
            funcionario_id=funcionario_id,
            data=data_registro,
            admin_id=admin_id,
        ).order_by(RegistroPonto.id).first()

        criado = registro is None
        merge_turno_partido = False

        if criado:
            registro = RegistroPonto(
                funcionario_id=funcionario_id,
                obra_id=obra_id,
                data=data_registro,
                hora_entrada=hora_entrada,
                hora_saida=hora_saida,
                hora_almoco_saida=hora_almoco_saida,
                hora_almoco_retorno=hora_almoco_retorno,
                observacoes=data.get('observacoes', ''),
                tipo_registro=data.get('tipo_lancamento', 'trabalho_normal'),
                admin_id=admin_id
            )
            db.session.add(registro)
        else:
            # ── Turno partido × correção ─────────────────────────────────────
            # O mesmo formulário serve aos dois casos, e só os HORÁRIOS os
            # distinguem. Se o lançamento novo COMEÇA depois de o registrado
            # terminar, ele é a segunda metade do dia — 08:00-12:00 seguido de
            # 13:00-17:00 são 8h com uma hora de almoço, não 4h que substituem
            # outras 4h. Se os horários se sobrepõem, é correção: 08:00-17:00
            # seguido de 08:00-18:00 é o mesmo dia reapontado, e vale o último.
            #
            # Sem esta distinção o dia de 8h viraria 4h no registro E no custo:
            # coerente consigo mesmo, e mentindo sobre a jornada. A perda hoje é
            # medida — `scripts/medir_producao.py` q7 mostra o padrão "8h
            # gravadas, 4h custeadas" repetido tenant a tenant.
            _cabe_almoco = not (registro.hora_almoco_saida
                                or registro.hora_almoco_retorno)
            _e_segunda_metade = (
                hora_entrada is not None
                and registro.hora_entrada is not None
                and registro.hora_saida is not None
                and hora_entrada >= registro.hora_saida
            )

            if _e_segunda_metade and _cabe_almoco:
                merge_turno_partido = True
                registro.hora_almoco_saida = registro.hora_saida
                registro.hora_almoco_retorno = hora_entrada
                if hora_saida is not None:
                    registro.hora_saida = hora_saida
                logger.info(
                    "[B1.7] Turno partido para funcionário %s em %s: "
                    "%s-%s + %s-%s vira %s-%s com almoço %s-%s",
                    funcionario_id, data_registro,
                    registro.hora_entrada, registro.hora_almoco_saida,
                    hora_entrada, hora_saida,
                    registro.hora_entrada, registro.hora_saida,
                    registro.hora_almoco_saida, registro.hora_almoco_retorno)
            else:
                if _e_segunda_metade and not _cabe_almoco:
                    # O modelo não comporta um segundo intervalo. Tratar como
                    # correção é a saída conservadora: estender a saída por cima
                    # do intervalo faria `calcular_horas_trabalhadas` contar o
                    # vão como trabalhado, e SUPERESTIMAR folha é pior que
                    # subestimar. O log existe para o caso aparecer de verdade.
                    logger.warning(
                        "[B1.7] Funcionário %s em %s já tem almoço gravado "
                        "(%s-%s) e recebeu um terceiro turno (%s-%s). O modelo "
                        "tem UM par de almoço: aplicado como CORREÇÃO, e o "
                        "intervalo novo não fica representado.",
                        funcionario_id, data_registro,
                        registro.hora_almoco_saida, registro.hora_almoco_retorno,
                        hora_entrada, hora_saida)
                # Correção — campo vazio no POST NÃO apaga valor já gravado.
                if hora_entrada is not None:
                    registro.hora_entrada = hora_entrada
                if hora_saida is not None:
                    registro.hora_saida = hora_saida
                if hora_almoco_saida is not None:
                    registro.hora_almoco_saida = hora_almoco_saida
                if hora_almoco_retorno is not None:
                    registro.hora_almoco_retorno = hora_almoco_retorno

            # `obra_id` vazio não pode zerar a obra: sem ela o handler sai em
            # `event_manager.py:326-328` ("sem obra vinculada") e o dia inteiro
            # perde custo.
            if obra_id is not None:
                registro.obra_id = obra_id
            if data.get('observacoes'):
                registro.observacoes = data.get('observacoes')
            # `tipo_lancamento` só se veio no POST: o default 'trabalho_normal'
            # rebaixaria um dia marcado `falta`, e
            # `services/funcionario_metrics.py:124-128` deixaria de contá-la.
            if data.get('tipo_lancamento'):
                registro.tipo_registro = data.get('tipo_lancamento')

        # O recálculo roda sobre o OBJETO, depois do merge — nunca sobre as
        # variáveis locais parseadas do POST, que só conhecem a metade recebida.
        if registro.hora_entrada and registro.hora_saida:
            from utils import calcular_horas_trabalhadas
            horas_calc = calcular_horas_trabalhadas(
                registro.hora_entrada,
                registro.hora_saida,
                registro.hora_almoco_saida,
                registro.hora_almoco_retorno,
                registro.data
            )
            registro.horas_trabalhadas = horas_calc['total']
            registro.horas_extras = horas_calc['extras']

        db.session.commit()

        logger.debug(
            "[OK] DEBUG novo_ponto: registro %s id=%s (%sh)",
            'CRIADO' if criado else 'ATUALIZADO', registro.id,
            registro.horas_trabalhadas)

        # Emitir evento após commit — integração com diaristas V2 e outros
        # módulos. Olha o OBJETO: num merge de tarde, `hora_entrada` local é
        # 13:00 mas o dia começou às 08:00, e é o dia que o custo precisa.
        tipo_ponto_canonico = 'entrada' if registro.hora_entrada else None
        if tipo_ponto_canonico:
            try:
                from event_manager import EventManager
                EventManager.emit('ponto_registrado', {
                    'registro_id': registro.id,
                    'tipo_ponto': tipo_ponto_canonico,
                }, admin_id=admin_id)
            except Exception as ev_err:
                logger.warning(f"[WARN] Evento ponto_registrado não emitido (manual): {ev_err}")

        if criado:
            mensagem = 'Registro de ponto criado com sucesso!'
        elif merge_turno_partido:
            mensagem = ('Turno partido: o registro do dia agora vai de '
                        f'{registro.hora_entrada:%H:%M} a '
                        f'{registro.hora_saida:%H:%M}, com almoço de '
                        f'{registro.hora_almoco_saida:%H:%M} a '
                        f'{registro.hora_almoco_retorno:%H:%M}.')
        else:
            mensagem = 'Registro do dia atualizado.'

        return jsonify({
            'success': True,
            'message': mensagem,
            'registro_id': registro.id,
            'criado': criado
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] DEBUG novo_ponto: ERRO: {str(e)}")
        logger.error(f"[ERROR] DEBUG novo_ponto: Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'}), 500

@main_bp.route('/admin/database-diagnostics')
@super_admin_required
def database_diagnostics():
    """
    Painel de diagnóstico de banco de dados - apenas para super_admin
    Mostra status da migração 48 e permite verificar estrutura de tabelas
    """
    try:
        from utils.database_diagnostics import DatabaseDiagnostics
        
        diagnostics = DatabaseDiagnostics()
        
        migration_status = diagnostics.check_migration_48_status()
        recent_errors = diagnostics.read_recent_diagnostics(max_entries=10)
        all_tables = diagnostics.get_all_tables()
        
        table_to_check = request.args.get('table')
        table_structure = None
        table_health = None
        
        if table_to_check:
            from utils.database_diagnostics import get_table_structure
            table_structure = get_table_structure(table_to_check)
            table_health = diagnostics.check_table_health(table_to_check)
        
        return render_template('admin/database_diagnostics.html',
                             migration_status=migration_status,
                             recent_errors=recent_errors,
                             all_tables=all_tables,
                             table_to_check=table_to_check,
                             table_structure=table_structure,
                             table_health=table_health)
    
    except Exception as e:
        logger.error(f"Erro no painel de diagnóstico: {e}")
        flash(f'Erro ao carregar diagnóstico: {str(e)}', 'danger')
        return redirect(url_for('main.dashboard'))


# ──────────────────────────────────────────────────────────────────────────
# Task #43 — Painel de webhooks para n8n.
# Lista as últimas N entregas (com filtros) e permite forçar nova tentativa
# em entregas com falha. Acessível a admin OU super_admin: o tenant admin
# vê SOMENTE suas próprias entregas (filtragem por admin_id), e o super_admin
# vê todas, de todos os tenants.
# ──────────────────────────────────────────────────────────────────────────
def _admin_can_see_entrega(entrega):
    """Tenant admin só pode mexer em entregas do próprio admin_id;
    super_admin pode tudo. Centraliza a regra para a listagem e o reenvio.
    """
    if current_user.tipo_usuario == TipoUsuario.SUPER_ADMIN:
        return True
    try:
        meu_admin_id = get_tenant_admin_id()
    except Exception:
        meu_admin_id = current_user.id
    return entrega.admin_id == meu_admin_id


@main_bp.route('/admin/webhooks')
@admin_required
def admin_webhooks_listar():
    try:
        from models import WebhookEntrega
        from utils.webhook_dispatcher import (
            WEBHOOK_EVENT_ALLOWLIST, is_enabled, get_webhook_url, MAX_TENTATIVAS,
        )

        status_filtro = (request.args.get('status') or '').strip().lower()
        event_filtro = (request.args.get('event') or '').strip()
        STATUS_VALIDOS = {'pendente', 'enviado', 'falha'}

        q = WebhookEntrega.query
        # Tenant scoping: admin tenant só enxerga as próprias entregas.
        if current_user.tipo_usuario != TipoUsuario.SUPER_ADMIN:
            try:
                meu_admin_id = get_tenant_admin_id()
            except Exception:
                meu_admin_id = current_user.id
            q = q.filter(WebhookEntrega.admin_id == meu_admin_id)

        if status_filtro in STATUS_VALIDOS:
            q = q.filter(WebhookEntrega.status == status_filtro)
        if event_filtro:
            q = q.filter(WebhookEntrega.event == event_filtro)
        entregas = q.order_by(WebhookEntrega.created_at.desc()).limit(200).all()

        eventos_q = db.session.query(WebhookEntrega.event).distinct()
        if current_user.tipo_usuario != TipoUsuario.SUPER_ADMIN:
            try:
                meu_admin_id = get_tenant_admin_id()
            except Exception:
                meu_admin_id = current_user.id
            eventos_q = eventos_q.filter(WebhookEntrega.admin_id == meu_admin_id)
        eventos_distintos = [row[0] for row in eventos_q.order_by(WebhookEntrega.event.asc()).all()]

        return render_template(
            'admin/webhooks.html',
            entregas=entregas,
            eventos_distintos=eventos_distintos,
            allowlist=sorted(WEBHOOK_EVENT_ALLOWLIST),
            webhook_ativo=is_enabled(),
            webhook_url=get_webhook_url(),
            max_tentativas=MAX_TENTATIVAS,
            status_filtro=status_filtro,
            event_filtro=event_filtro,
        )
    except Exception as e:
        logger.error(f"[admin_webhooks] erro: {e}", exc_info=True)
        flash(f'Erro ao carregar webhooks: {e}', 'danger')
        return redirect(url_for('main.dashboard'))


@main_bp.route('/admin/webhooks/<int:entrega_id>/reenviar', methods=['POST'])
@admin_required
def admin_webhooks_reenviar(entrega_id):
    try:
        from models import WebhookEntrega
        from utils.webhook_dispatcher import reentregar_uma, is_enabled
        if not is_enabled():
            flash('Webhook desligado (N8N_WEBHOOK_URL não configurado).', 'warning')
            return redirect(url_for('main.admin_webhooks_listar'))
        entrega = db.session.get(WebhookEntrega, entrega_id)
        if entrega is None:
            flash(f'Entrega #{entrega_id} não encontrada.', 'warning')
            return redirect(url_for('main.admin_webhooks_listar'))
        if not _admin_can_see_entrega(entrega):
            flash('Você não tem permissão para reenviar esta entrega.', 'danger')
            return redirect(url_for('main.admin_webhooks_listar'))
        ok = reentregar_uma(entrega_id)
        if ok:
            flash(f'Entrega #{entrega_id} reenviada com sucesso.', 'success')
        else:
            flash(f'Falha ao reenviar entrega #{entrega_id} — veja o log.', 'warning')
        return redirect(url_for('main.admin_webhooks_listar'))
    except Exception as e:
        logger.error(f"[admin_webhooks_reenviar] erro: {e}", exc_info=True)
        flash(f'Erro ao reenviar webhook: {e}', 'danger')
        return redirect(url_for('main.admin_webhooks_listar'))


@main_bp.route('/admin/database-diagnostics/check-table', methods=['POST'])
@super_admin_required
def check_table_structure():
    """API para verificar estrutura de uma tabela específica"""
    try:
        table_name = request.form.get('table_name', '').strip()
        
        if not table_name:
            flash('Nome da tabela é obrigatório', 'warning')
            return redirect(url_for('main.database_diagnostics'))
        
        return redirect(url_for('main.database_diagnostics', table=table_name))
    
    except Exception as e:
        logger.error(f"Erro ao verificar tabela: {e}")
        flash(f'Erro ao verificar tabela: {str(e)}', 'danger')
        return redirect(url_for('main.database_diagnostics'))
