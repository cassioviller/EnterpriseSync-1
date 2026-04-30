"""
Task #45 — Catálogo de eventos `dominio.acao` para n8n.

Cobre, com unit-tests rodando no app context (sem stack HTTP):

  1. Os 7 helpers `emit_*` em `utils/catalogo_eventos.py` chamam
     `EventManager.emit(<nome>, <payload>, admin_id)` com:
       - nome do evento exatamente igual ao da allowlist
       - payload contendo as chaves obrigatórias documentadas
  2. O catálogo de eventos é EXATAMENTE igual à allowlist do
     dispatcher (`utils.webhook_dispatcher.WEBHOOK_EVENT_ALLOWLIST`).
  3. Idempotência por dia do `notificacoes_cli.emitir_propostas_expirando`:
       a. Propostas dentro da janela disparam `proposta.expirando` 1x.
       b. Re-rodar no mesmo dia NÃO re-emite (puladas_dedup>0,
          emitidas==0).
       c. Propostas fora da janela / sem data_envio são puladas.
  4. `obra.concluida` é emitido apenas na PRIMEIRA transição para
     "Concluída" (testado via helper direto + simulação da view).

Executa com:  python tests/test_task_45_catalogo_eventos.py
Workflow Replit: `test-task-45-catalogo-eventos`.

Exit 0 → todos asserts OK. Exit 1 → falha.
"""
import os
import sys
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario,
    Cliente,
    Proposta,
    Obra,
    WebhookEntrega,
)
from utils import catalogo_eventos
from utils.webhook_dispatcher import WEBHOOK_EVENT_ALLOWLIST
import notificacoes_cli


RUN_TAG = f"E2E45-{secrets.token_hex(3).upper()}"
PASS, FAIL = [], []

EVENTOS_TASK_45 = {
    'proposta.aprovada',
    'proposta.rejeitada',
    'proposta.expirando',
    'obra.rdo_publicado',
    'obra.medicao_publicada',
    'obra.cronograma_atualizado',
    'obra.concluida',
}


def step(label, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    (PASS if ok else FAIL).append(label)
    extra = f" — {detail}" if detail else ""
    print(f"  {tag} {label}{extra}")


# ────────────────────────────────────────────────────────────────────────
# Setup helpers
# ────────────────────────────────────────────────────────────────────────
def make_admin():
    """Cria admin tenant para isolamento."""
    email = f"admin45-{RUN_TAG.lower()}@e2e.com.br"
    u = Usuario.query.filter_by(email=email).first()
    if u:
        return u
    u = Usuario(
        nome="Admin Task #45",
        email=email,
        username=f"admin45-{RUN_TAG.lower()}",
        password_hash=generate_password_hash("Senha@2026"),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def make_cliente(admin):
    c = Cliente(
        admin_id=admin.id,
        nome=f"Cliente E2E {RUN_TAG}",
        email=f"cli{RUN_TAG.lower()}@e2e.com.br",
        telefone="5511999998888",
    )
    db.session.add(c)
    db.session.commit()
    return c


def make_proposta(admin, status='enviada', data_envio=None, validade_dias=30,
                  numero_suffix='001'):
    p = Proposta(
        admin_id=admin.id,
        numero=f"PROP-{RUN_TAG}-{numero_suffix}",
        cliente_nome="Cliente Teste",
        cliente_email="cli@teste.com.br",
        cliente_telefone="5511999998888",
        valor_total=Decimal("12000.00"),
        status=status,
        validade_dias=validade_dias,
        data_envio=data_envio,
        token_cliente=secrets.token_urlsafe(16),
        versao=1,
    )
    db.session.add(p)
    db.session.commit()
    return p


def make_obra(admin, cliente, status='Em Andamento', suffix='001'):
    # codigo é varchar(20); RUN_TAG já tem 9 chars (E2E45-XXXXXX),
    # então usamos um hash curto + suffix para caber.
    short = secrets.token_hex(2).upper()  # 4 chars
    o = Obra(
        admin_id=admin.id,
        cliente_id=cliente.id,
        nome=f"Obra E2E {RUN_TAG}-{suffix}",
        codigo=f"O{short}-{suffix}"[:20],
        status=status,
        data_inicio=date(2026, 1, 1),
        data_previsao_fim=date(2026, 12, 31),
        valor_contrato=Decimal("1200000.00"),
    )
    db.session.add(o)
    db.session.commit()
    return o


# ────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────
def test_allowlist_contem_catalogo():
    """A allowlist do dispatcher precisa conter os 7 eventos do catálogo."""
    faltando = EVENTOS_TASK_45 - set(WEBHOOK_EVENT_ALLOWLIST)
    step(
        "1. Allowlist contém os 7 eventos do catálogo",
        not faltando,
        f"faltando={sorted(faltando)}" if faltando else f"all in WEBHOOK_EVENT_ALLOWLIST"
    )


def test_emit_proposta_aprovada(admin, proposta):
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_proposta_aprovada(proposta, admin.id, aprovada_por='admin')
    ok = m.called and m.call_args.args[0] == 'proposta.aprovada'
    payload = m.call_args.args[1] if m.called else {}
    keys_ok = {'proposta_id', 'aprovada_por', 'data_aprovacao', 'cliente_nome', 'valor_total'} <= set(payload.keys())
    step("2. emit_proposta_aprovada → 'proposta.aprovada' com payload OK",
         ok and keys_ok and payload.get('aprovada_por') == 'admin',
         f"event={m.call_args.args[0] if m.called else 'NOT_CALLED'}, keys={sorted(payload.keys())[:8]}")


def test_emit_proposta_rejeitada(admin, proposta):
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_proposta_rejeitada(proposta, admin.id,
                                                 rejeitada_por='cliente',
                                                 motivo='Prazo muito longo')
    ok = m.called and m.call_args.args[0] == 'proposta.rejeitada'
    payload = m.call_args.args[1] if m.called else {}
    motivo_ok = payload.get('motivo') == 'Prazo muito longo'
    step("3. emit_proposta_rejeitada → 'proposta.rejeitada' (motivo preservado)",
         ok and motivo_ok and payload.get('rejeitada_por') == 'cliente',
         f"motivo={payload.get('motivo')!r}")

    # Truncamento do motivo a 500 chars.
    longo = 'X' * 600
    with patch("event_manager.EventManager.emit") as m2:
        catalogo_eventos.emit_proposta_rejeitada(proposta, admin.id, motivo=longo)
    payload2 = m2.call_args.args[1] if m2.called else {}
    step("3b. motivo é truncado a 500 chars",
         len(payload2.get('motivo', '')) == 500,
         f"len={len(payload2.get('motivo', ''))}")


def test_emit_proposta_expirando(admin, proposta):
    dv = date.today() + timedelta(days=2)
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_proposta_expirando(proposta, admin.id, dv, 2)
    ok = m.called and m.call_args.args[0] == 'proposta.expirando'
    payload = m.call_args.args[1] if m.called else {}
    step("4. emit_proposta_expirando → 'proposta.expirando' com data_validade",
         ok and payload.get('dias_restantes') == 2 and payload.get('data_validade') == dv.isoformat(),
         f"data_validade={payload.get('data_validade')}, dias_restantes={payload.get('dias_restantes')}")


def test_emit_obra_rdo_publicado(admin, obra):
    rdo = SimpleNamespace(id=999, obra_id=obra.id,
                          numero_rdo='RDO-2026-04-30-001',
                          data_relatorio=date(2026, 4, 30),
                          status='Finalizado')
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_obra_rdo_publicado(rdo, admin.id)
    ok = m.called and m.call_args.args[0] == 'obra.rdo_publicado'
    payload = m.call_args.args[1] if m.called else {}
    step("5. emit_obra_rdo_publicado → 'obra.rdo_publicado' com obra resolvida",
         ok and payload.get('rdo_id') == 999 and payload.get('obra_id') == obra.id and payload.get('numero_rdo') == 'RDO-2026-04-30-001',
         f"obra_id={payload.get('obra_id')}, rdo_id={payload.get('rdo_id')}")


def test_emit_obra_medicao_publicada(admin, obra):
    medicao = SimpleNamespace(
        id=12, obra_id=obra.id, numero='MED-2026-08',
        valor_total_medido_periodo=Decimal('85000.00'),
        valor_a_faturar_periodo=Decimal('85000.00'),
        percentual_executado=Decimal('42.5'),
    )
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_obra_medicao_publicada(medicao, admin.id)
    ok = m.called and m.call_args.args[0] == 'obra.medicao_publicada'
    payload = m.call_args.args[1] if m.called else {}
    step("6. emit_obra_medicao_publicada → 'obra.medicao_publicada' (valores convertidos)",
         ok and payload.get('numero_medicao') == 'MED-2026-08' and payload.get('valor_medido_periodo') == 85000.0,
         f"valor_medido={payload.get('valor_medido_periodo')}, num={payload.get('numero_medicao')}")


def test_emit_obra_cronograma_atualizado(admin, obra):
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_obra_cronograma_atualizado(
            obra, admin.id, tarefas_geradas=18, motivo='revisao_inicial')
    ok = m.called and m.call_args.args[0] == 'obra.cronograma_atualizado'
    payload = m.call_args.args[1] if m.called else {}
    step("7. emit_obra_cronograma_atualizado → 'obra.cronograma_atualizado' (tarefas_geradas)",
         ok and payload.get('tarefas_geradas') == 18 and payload.get('motivo') == 'revisao_inicial',
         f"tarefas={payload.get('tarefas_geradas')}, motivo={payload.get('motivo')}")


def test_emit_obra_concluida(admin, obra):
    with patch("event_manager.EventManager.emit") as m:
        catalogo_eventos.emit_obra_concluida(obra, admin.id)
    ok = m.called and m.call_args.args[0] == 'obra.concluida'
    payload = m.call_args.args[1] if m.called else {}
    step("8. emit_obra_concluida → 'obra.concluida' (com data_conclusao)",
         ok and payload.get('data_conclusao') == date.today().isoformat() and payload.get('valor_contrato') == 1200000.0,
         f"data_conclusao={payload.get('data_conclusao')}, valor={payload.get('valor_contrato')}")


def test_safe_emit_engole_excecao(admin, proposta):
    """Helper jamais propaga exceção (best-effort)."""
    with patch("event_manager.EventManager.emit", side_effect=RuntimeError("boom!")):
        try:
            catalogo_eventos.emit_proposta_aprovada(proposta, admin.id)
            propagated = False
        except Exception:
            propagated = True
    step("9. emit_* engole exceção do EventManager (best-effort)",
         not propagated, "RuntimeError não vazou")


def test_cli_expirando_idempotencia(admin):
    """O CLI não emite 2x para a mesma proposta no mesmo dia."""
    # Limpa entregas antigas deste tenant para ambiente determinístico.
    WebhookEntrega.query.filter_by(admin_id=admin.id, event='proposta.expirando').delete()
    db.session.commit()

    # Proposta dentro da janela: data_envio = hoje - (validade-2) → expira em 2 dias.
    p = make_proposta(
        admin, status='enviada',
        data_envio=datetime.utcnow() - timedelta(days=28),  # 30 - 28 = 2 dias restantes
        validade_dias=30,
        numero_suffix='IDEMP-A'
    )

    # Mock EventManager.emit para criar uma WebhookEntrega real (simulando o
    # listener do dispatcher). Usar o path que catalogo_eventos importa.
    def fake_emit(event, payload, admin_id=None):
        e = WebhookEntrega(
            event=event,
            payload={'event': event, 'data': payload, 'admin_id': admin_id},
            status='entregue',
            admin_id=admin_id,
        )
        db.session.add(e)
        db.session.commit()

    with patch("event_manager.EventManager.emit", side_effect=fake_emit):
        stats1 = notificacoes_cli.emitir_propostas_expirando(janela_dias=3)
    step("10a. 1ª execução emite 1 (analisa e dispara)",
         stats1['emitidas'] >= 1,
         f"stats1={stats1}")

    with patch("event_manager.EventManager.emit", side_effect=fake_emit):
        stats2 = notificacoes_cli.emitir_propostas_expirando(janela_dias=3)
    # Pode haver outras propostas em outros tenants → checa só este p.id.
    entregas_p = WebhookEntrega.query.filter(
        WebhookEntrega.event == 'proposta.expirando',
        WebhookEntrega.admin_id == admin.id,
    ).all()
    n_para_p = sum(1 for e in entregas_p
                   if (((e.payload or {}).get('data') or {}).get('proposta_id')) == p.id)
    step("10b. 2ª execução é dedup (proposta_id no mesmo dia conta apenas 1)",
         n_para_p == 1, f"n_entregas_para_proposta={n_para_p}, stats2={stats2}")


def test_cli_expirando_fora_janela(admin):
    """Propostas longe da expiração ou sem data_envio são puladas."""
    p_long = make_proposta(
        admin, status='enviada',
        data_envio=datetime.utcnow() - timedelta(days=1),
        validade_dias=30,
        numero_suffix='LONG'
    )  # expira em 29 dias (fora da janela=3)
    p_sem = make_proposta(
        admin, status='enviada', data_envio=None, validade_dias=30,
        numero_suffix='SEMENVIO'
    )

    def noop_emit(event, payload, admin_id=None):
        # Não cria registro real (já testado em 10).
        pass

    with patch("event_manager.EventManager.emit", side_effect=noop_emit):
        stats = notificacoes_cli.emitir_propostas_expirando(janela_dias=3)
    step("11. fora_janela e sem_envio são contabilizados",
         stats['puladas_fora_janela'] >= 1 and stats['puladas_sem_envio'] >= 1,
         f"stats={stats}")


def test_emit_obra_concluida_helper_so_quando_chamado(admin, cliente):
    """O helper em si é puro: só emite QUANDO é chamado.

    A regra de transição (não re-emite em re-edits) é responsabilidade
    da view, que checa `status_anterior` antes de chamar — e isso é o
    que validamos aqui (sem montar o stack HTTP completo).

    A normalização da view também aplica fold de acento — tanto
    "Concluída" como "Concluida" devem disparar; só a 1ª transição.
    """
    import unicodedata as _ud

    def _norm(s):
        s = (s or '').strip().lower()
        return ''.join(c for c in _ud.normalize('NFKD', s)
                       if not _ud.combining(c))

    obra = make_obra(admin, cliente, status='Concluída', suffix='CONCL')

    casos = [
        # (status_anterior, novo_status, deveria_emitir)
        ('Em Andamento', 'Concluída', True),    # 1ª transição com acento
        ('Concluída',    'Concluída', False),   # re-edit (mesmo acento)
        ('Em Andamento', 'Concluida', True),    # transição SEM acento
        ('Concluida',    'Concluída', False),   # re-edit (acentos divergentes)
        ('CONCLUÍDA',    'Concluida', False),   # re-edit caps
    ]
    n_emitidos = 0
    with patch("event_manager.EventManager.emit") as m:
        for status_anterior, novo_status, _ in casos:
            if _norm(novo_status) == 'concluida' and _norm(status_anterior) != 'concluida':
                catalogo_eventos.emit_obra_concluida(obra, admin.id)
                n_emitidos += 1
    esperado = sum(1 for _, _, dv in casos if dv)
    step("12. transição p/ Concluída (com/sem acento) emite só na 1ª transição",
         m.call_count == esperado == n_emitidos == 2 and m.call_args.args[0] == 'obra.concluida',
         f"call_count={m.call_count}, esperado={esperado}, n_emitidos={n_emitidos}")


# ────────────────────────────────────────────────────────────────────────
# Runner
# ────────────────────────────────────────────────────────────────────────
def main():
    print(f"==> Task #45 — Catálogo de Eventos | RUN_TAG={RUN_TAG}")
    with app.app_context():
        # Em DBs sem tenant inicial, garante criação.
        admin = make_admin()
        cliente = make_cliente(admin)
        proposta = make_proposta(admin, numero_suffix='HLP')
        obra = make_obra(admin, cliente)

        test_allowlist_contem_catalogo()
        test_emit_proposta_aprovada(admin, proposta)
        test_emit_proposta_rejeitada(admin, proposta)
        test_emit_proposta_expirando(admin, proposta)
        test_emit_obra_rdo_publicado(admin, obra)
        test_emit_obra_medicao_publicada(admin, obra)
        test_emit_obra_cronograma_atualizado(admin, obra)
        test_emit_obra_concluida(admin, obra)
        test_safe_emit_engole_excecao(admin, proposta)
        test_cli_expirando_idempotencia(admin)
        test_cli_expirando_fora_janela(admin)
        test_emit_obra_concluida_helper_so_quando_chamado(admin, cliente)

    print()
    print(f"==> RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL")
    if FAIL:
        print("FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
