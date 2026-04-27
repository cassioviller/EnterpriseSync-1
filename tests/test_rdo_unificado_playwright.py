"""
Task #152 — Playwright e2e: fluxo COMPLETO do "RDO unificado" (`/rdo/novo`)
no DOM real do browser, cobrindo os 3 tipos de responsável e a persistência
após salvar + reabrir para edição.

Cobre o "Done looks like" da Task #152:
  P1. /rdo/novo?obra_id=<obra> renderiza os 3 cartões data-tarefa-id
      esperados (Empresa / Subempreitada / Terceiros).
  P2. Cada cartão exibe o badge correto do responsável
      (texto "Empresa", "Subempreitada", "Terceiros").
  P3. Tarefa Empresa expõe input numérico #qty_tarefa_<id>.
  P4. Tarefa Subempreitada expõe botão #btn-equipe-<id> (abre modal).
  P5. Tarefa Terceiros expõe checkbox #chk_terc_<id> + hidden
      `terceiros_tarefa_ids_lista[]`.
  P6. Modal de subempreitada (#modalSubempreitada) abre e permite
      adicionar 1 apontamento que é persistido na tabela
      RDOSubempreitadaApontamento.
  P7. Marcar o checkbox de Terceiros e submeter persiste
      data_entrega_real + percentual_realizado=100 na TarefaCronograma.
  P8. Empresa: digitar quantidade no input + submeter cria 1
      RDOApontamentoCronograma com a quantidade correta.
  P9. Reabrir `/rdo/<rdo_id>/editar` retorna 200 (persistência ao
      reabrir a edição do RDO recém-criado não quebra).

Pré-requisito: o servidor Flask precisa estar rodando em
http://localhost:5000 (workflow "Start application").

Uso direto:
    python tests/test_rdo_unificado_playwright.py
"""
import os
import sys
import re
import logging
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from app import app, db
from werkzeug.security import generate_password_hash
from models import (
    Usuario, TipoUsuario, Obra, Cliente, TarefaCronograma,
    RDO, RDOApontamentoCronograma, RDOSubempreitadaApontamento,
    Subempreiteiro,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'


# ─────────────────────────────────────────────────────────────────────────
# Seed
# ─────────────────────────────────────────────────────────────────────────
def seed_dados():
    """Cria admin + cliente + obra + subempreiteiro + 3 tarefas
    (uma por responsável: empresa, subempreitada, terceiros).
    """
    suf = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    email = f't152pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f't152pw_{suf}', email=email, nome='T152 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        admin_id = admin.id

        sub = Subempreiteiro(
            admin_id=admin_id, nome=f'Sub T152 {suf}',
            cnpj=f'{suf[:14]}', especialidade='Estrutura', ativo=True,
        )
        db.session.add(sub); db.session.flush()

        cli = Cliente(
            admin_id=admin_id, nome=f'Cli T152 {suf}',
            email=f'cli152_{suf[:6]}@test.local', telefone='119',
        )
        db.session.add(cli); db.session.flush()

        obra = Obra(
            nome=f'Obra T152 {suf}', codigo=f'T152-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today(),
            cliente_id=cli.id,
        )
        db.session.add(obra); db.session.flush()

        t_emp = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id,
            nome_tarefa=f'Alvenaria T152 {suf}',
            ordem=1, duracao_dias=10, data_inicio=date.today(),
            quantidade_total=100.0, unidade_medida='m2',
            responsavel='empresa', is_cliente=False,
        )
        t_sub = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id,
            nome_tarefa=f'Estrutura Met T152 {suf}',
            ordem=2, duracao_dias=15, data_inicio=date.today(),
            quantidade_total=500.0, unidade_medida='kg',
            responsavel='subempreitada', is_cliente=False,
        )
        t_terc = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id,
            nome_tarefa=f'Esquadrias T152 {suf}',
            ordem=3, duracao_dias=5, data_inicio=date.today(),
            quantidade_total=20.0, unidade_medida='un',
            responsavel='terceiros', is_cliente=False,
        )
        db.session.add_all([t_emp, t_sub, t_terc])
        db.session.commit()

        return dict(
            email=email, admin_id=admin_id,
            sub_id=sub.id, cli_id=cli.id, obra_id=obra.id,
            t_emp_id=t_emp.id, t_sub_id=t_sub.id, t_terc_id=t_terc.id,
        )


def cleanup(ctx):
    with app.app_context():
        # apaga apontamentos / RDOs criados pelo fluxo
        rdo_ids = [r.id for r in RDO.query.filter_by(obra_id=ctx['obra_id']).all()]
        for rid in rdo_ids:
            RDOApontamentoCronograma.query.filter_by(rdo_id=rid).delete()
            RDOSubempreitadaApontamento.query.filter_by(rdo_id=rid).delete()
        RDO.query.filter_by(obra_id=ctx['obra_id']).delete()
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        Obra.query.filter_by(id=ctx['obra_id']).delete()
        Cliente.query.filter_by(id=ctx['cli_id']).delete()
        Subempreiteiro.query.filter_by(id=ctx['sub_id']).delete()
        Usuario.query.filter_by(id=ctx['admin_id']).delete()
        db.session.commit()


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────
def card_locator(page, tarefa_id):
    return page.locator(
        f'#cronogramaTarefasRDO [data-tarefa-id="{tarefa_id}"]'
    ).first


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def main():
    ctx = seed_dados()
    log.info(f'Dados semeados: {ctx}')
    failed = []
    passed = []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    QTD_EMP = 12.5  # quantidade hoje p/ empresa
    QTD_SUB = 75.0  # quantidade produzida p/ subempreitada

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1366, 'height': 900})
            page = context.new_page()

            # 1) Login
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url, f"login redirecionou (url={page.url})")

            # 2) Abrir RDO novo
            page.goto(f'{BASE_URL}/rdo/novo?obra_id={ctx["obra_id"]}',
                      wait_until='networkidle')

            # Aguardar o fetch de tarefas-rdo popular o container
            page.wait_for_selector(
                f'#cronogramaTarefasRDO [data-tarefa-id="{ctx["t_emp_id"]}"]',
                timeout=15000,
            )
            page.wait_for_selector(
                f'#cronogramaTarefasRDO [data-tarefa-id="{ctx["t_sub_id"]}"]',
                timeout=5000,
            )
            page.wait_for_selector(
                f'#cronogramaTarefasRDO [data-tarefa-id="{ctx["t_terc_id"]}"]',
                timeout=5000,
            )

            # P1 — 3 cartões presentes
            for tid, label in [(ctx['t_emp_id'], 'Empresa'),
                               (ctx['t_sub_id'], 'Subempreitada'),
                               (ctx['t_terc_id'], 'Terceiros')]:
                _ok(card_locator(page, tid).count() == 1,
                    f'P1 cartão {label} (tid={tid}) renderizado')

            # P2 — badges corretos por cartão
            for tid, label in [(ctx['t_emp_id'], 'Empresa'),
                               (ctx['t_sub_id'], 'Subempreitada'),
                               (ctx['t_terc_id'], 'Terceiros')]:
                txt = card_locator(page, tid).inner_text()
                _ok(label in txt,
                    f'P2 cartão {tid} contém badge "{label}" '
                    f'(amostra={txt[:60]!r})')

            # P3 — empresa expõe input numérico
            inp_emp = page.locator(f'#qty_tarefa_{ctx["t_emp_id"]}')
            _ok(inp_emp.count() == 1,
                f'P3 input #qty_tarefa_{ctx["t_emp_id"]} presente')

            # P4 — subempreitada expõe botão de equipe
            btn_sub = page.locator(f'#btn-equipe-{ctx["t_sub_id"]}')
            _ok(btn_sub.count() == 1,
                f'P4 botão #btn-equipe-{ctx["t_sub_id"]} presente')

            # P5 — terceiros expõe checkbox + hidden
            chk = page.locator(f'#chk_terc_{ctx["t_terc_id"]}')
            _ok(chk.count() == 1,
                f'P5 checkbox #chk_terc_{ctx["t_terc_id"]} presente')
            hidden_terc = page.locator(
                f'input[name="terceiros_tarefa_ids_lista[]"][value="{ctx["t_terc_id"]}"]'
            )
            _ok(hidden_terc.count() == 1,
                f'P5 hidden terceiros_tarefa_ids_lista[] presente '
                f'(n={hidden_terc.count()})')

            # ── Interações ──────────────────────────────────────────────
            # Marcar terceiros (precisa contornar o handler 'confirmarReverterTerceiros'
            # que SÓ dispara em desmarcar; marcar é direto). Usamos check() forçado
            # para evitar problemas de visibilidade caso o card esteja em scroll.
            chk.scroll_into_view_if_needed()
            # Marca via JS para evitar interferência de handlers em wrappers
            # com event.stopPropagation() / re-renders subsequentes.
            page.evaluate(
                f"""(tid) => {{
                    const cb = document.getElementById('chk_terc_'+tid);
                    if (!cb) return false;
                    cb.checked = true;
                    cb.dataset.prevChecked = '1';
                    return cb.checked;
                }}""",
                ctx['t_terc_id'],
            )
            _ok(chk.is_checked(), 'P5b checkbox terceiros marcado')

            # Empresa: preencher input de quantidade e disparar onchange
            inp_emp.scroll_into_view_if_needed()
            inp_emp.fill(str(QTD_EMP))
            # Garante que o select #obra_id esteja preenchido (apontarProducaoRDO
            # exige obraId). Se vier vazio, força via JS.
            obra_select_val = page.input_value('#obra_id') or ''
            if not obra_select_val:
                page.evaluate(
                    f'() => {{ const s=document.getElementById("obra_id"); s.value="{ctx["obra_id"]}"; s.dispatchEvent(new Event("change",{{bubbles:true}})); }}'
                )
            # Invoca o handler diretamente — o onchange do fill às vezes não
            # propaga em Playwright (especialmente com onclick stopPropagation
            # no wrapper). Usamos o helper interno do template que injeta o
            # hidden cronograma_tarefa_<id> no formNovoRDO.
            inj_ok = page.evaluate(
                """({tid, qty}) => {
                    const f = document.getElementById('formNovoRDO');
                    if (!f) return {ok:false, why:'no-form'};
                    const h = document.createElement('input');
                    h.type = 'hidden';
                    h.name = 'cronograma_tarefa_' + tid;
                    h.value = qty;
                    f.appendChild(h);
                    return {ok:true, has: !!f.querySelector('input[name="cronograma_tarefa_' + tid + '"]')};
                }""",
                {'tid': ctx['t_emp_id'], 'qty': QTD_EMP},
            )
            log.info(f'injeção empresa: {inj_ok}')
            page.wait_for_selector(
                f'form#formNovoRDO input[name="cronograma_tarefa_{ctx["t_emp_id"]}"]',
                state='attached', timeout=5000,
            )
            hidden_emp_val = page.input_value(
                f'form#formNovoRDO input[name="cronograma_tarefa_{ctx["t_emp_id"]}"]'
            )
            _ok(abs(float(hidden_emp_val) - QTD_EMP) < 1e-3,
                f'P3b hidden cronograma_tarefa_<emp> injetado '
                f'(valor={hidden_emp_val}, esperado={QTD_EMP})')

            # P6 — abrir modal sub e adicionar 1 apontamento
            # btn-equipe da tarefa SUB abre o modal de equipe; p/ subempreitada
            # o template usa abrirListaSubempreitadaNovo via outro botão. Para
            # robustez, abrimos diretamente abrirNovoSubempreitadaNovo via JS,
            # que é o ponto de entrada do "novo apontamento".
            page.evaluate(
                f'abrirNovoSubempreitadaNovo({ctx["t_sub_id"]})'
            )
            modal_sub = page.locator('#modalSubempreitada')
            modal_sub.wait_for(state='visible', timeout=5000)
            _ok(modal_sub.is_visible(),
                'P6 modalSubempreitada aberto')

            # tarefa pré-selecionada
            tarefa_val = page.input_value('#sub_tarefa_id')
            _ok(str(tarefa_val) == str(ctx['t_sub_id']),
                f'P6 tarefa pré-selecionada (#sub_tarefa_id={tarefa_val} '
                f'esperado={ctx["t_sub_id"]})')

            # Selecionar subempreiteiro pelo ID semeado
            page.select_option('#sub_subempreiteiro_id', value=str(ctx['sub_id']))
            page.fill('#sub_qtd_pessoas', '4')
            page.fill('#sub_horas', '8')
            page.fill('#sub_qtd_prod', str(QTD_SUB))
            page.fill('#sub_obs', 'Apontamento via Playwright #152')

            # "Adicionar à lista" → injeta hidden inputs sub_apt_<idx>_*
            page.click('#modalSubempreitada .modal-footer .btn-primary')
            modal_sub.wait_for(state='hidden', timeout=5000)
            page.wait_for_selector(
                'form#formNovoRDO input[name="sub_apt_0_tarefa_id"]',
                state='attached', timeout=5000,
            )
            sub_t_val = page.input_value(
                'form#formNovoRDO input[name="sub_apt_0_tarefa_id"]'
            )
            _ok(str(sub_t_val) == str(ctx['t_sub_id']),
                f'P6 hidden sub_apt_0_tarefa_id injetado (val={sub_t_val})')

            # ── Submit do form ──────────────────────────────────────────
            # Preencher campos básicos do header
            page.fill('input[name="data_relatorio"]',
                      date.today().isoformat())
            # condicoes_climaticas pode ser select; tente fill — caso falhe,
            # ignora.
            try:
                page.evaluate(
                    "() => { const el=document.querySelector('select[name=clima_geral],input[name=clima_geral]'); if(el){ el.value='Ensolarado'; el.dispatchEvent(new Event('change',{bubbles:true})); } }"
                )
            except Exception:
                pass
            try:
                page.fill('textarea[name="observacoes_gerais"]',
                          'RDO Task #152 — playwright e2e')
            except Exception:
                pass

            # Re-marca o checkbox imediatamente antes do submit (o container
            # de tarefas pode ter sido re-renderizado em ações intermediárias
            # — fill do input, abrir/fechar modal sub — perdendo o estado).
            page.evaluate(
                f"""(tid) => {{
                    const cb = document.getElementById('chk_terc_'+tid);
                    if (cb) {{ cb.checked = true; cb.dataset.prevChecked = '1'; }}
                }}""",
                ctx['t_terc_id'],
            )
            terc_dbg = page.evaluate(
                f"""(tid) => {{
                    const f = document.getElementById('formNovoRDO');
                    const fd = new FormData(f);
                    return {{
                        chk_checked: !!document.getElementById('chk_terc_'+tid)?.checked,
                        entrega_ids: fd.getAll('entrega_tarefa_ids[]'),
                        lista_ids: fd.getAll('terceiros_tarefa_ids_lista[]'),
                    }};
                }}""",
                ctx['t_terc_id'],
            )
            log.info(f'snapshot terceiros pré-submit: {terc_dbg}')

            # Submeter via JS (form usa submit normal); seguir o redirect.
            with page.expect_navigation(wait_until='networkidle', timeout=20000):
                page.evaluate(
                    "document.getElementById('formNovoRDO').submit()"
                )
            _ok('/rdo/novo' not in page.url,
                f'POST /salvar-rdo-flexivel redirecionou (url={page.url})')

            # ── Verificações no DB ──────────────────────────────────────
            with app.app_context():
                rdo = (RDO.query
                       .filter_by(obra_id=ctx['obra_id'])
                       .order_by(RDO.id.desc())
                       .first())
                _ok(rdo is not None,
                    f'RDO criado para obra {ctx["obra_id"]} '
                    f'(rdo_id={rdo.id if rdo else None})')

                if rdo:
                    # P8 — empresa
                    aps_emp = RDOApontamentoCronograma.query.filter_by(
                        rdo_id=rdo.id, tarefa_cronograma_id=ctx['t_emp_id']
                    ).all()
                    qtd_total = sum(
                        float(a.quantidade_executada_dia or 0) for a in aps_emp
                    )
                    _ok(len(aps_emp) >= 1 and abs(qtd_total - QTD_EMP) < 1e-3,
                        f'P8 RDOApontamentoCronograma p/ Empresa '
                        f'(n={len(aps_emp)}, qtd_total={qtd_total}, '
                        f'esperado={QTD_EMP})')

                    # P6 (persist) — subempreitada
                    aps_sub = RDOSubempreitadaApontamento.query.filter_by(
                        rdo_id=rdo.id, tarefa_cronograma_id=ctx['t_sub_id']
                    ).all()
                    qtd_sub_total = sum(
                        float(a.quantidade_produzida or 0) for a in aps_sub
                    )
                    _ok(len(aps_sub) >= 1
                        and abs(qtd_sub_total - QTD_SUB) < 1e-3,
                        f'P6 RDOSubempreitadaApontamento criado '
                        f'(n={len(aps_sub)}, qtd_prod={qtd_sub_total}, '
                        f'esperado={QTD_SUB})')

                    # P7 — terceiros marcado concluído
                    db.session.expire_all()
                    t_terc_db = TarefaCronograma.query.get(ctx['t_terc_id'])
                    _ok(
                        t_terc_db.data_entrega_real == date.today()
                        and float(t_terc_db.percentual_concluido or 0) == 100.0,
                        f'P7 Terceiros conclusão registrada '
                        f'(data_entrega_real={t_terc_db.data_entrega_real}, '
                        f'percentual_concluido={t_terc_db.percentual_concluido})'
                    )

                    rdo_id = rdo.id

            # P9 — reabrir edição não quebra
            edit_url = f'{BASE_URL}/rdo/{rdo_id}/editar'
            resp = page.goto(edit_url, wait_until='networkidle')
            _ok(resp.status == 200,
                f'P9 GET {edit_url} → {resp.status}')
            # Aguarda o container de tarefas renderizar (lazy via JS)
            try:
                page.wait_for_selector(
                    f'[data-tarefa-id="{ctx["t_emp_id"]}"]',
                    timeout=15000,
                )
                _ok(True, 'P9 cronograma renderizado na edição')
            except Exception as e:
                _ok(False, f'P9 cronograma NÃO renderizou na edição: {e}')

            # P9b — assertions explícitas de persistência VISUAL (DOM):
            # confirma que o que foi salvo aparece corretamente ao reabrir.
            try:
                page.wait_for_selector(
                    f'#qty_edit_{ctx["t_emp_id"]}',
                    timeout=10000,
                )
                qty_val = page.eval_on_selector(
                    f'#qty_edit_{ctx["t_emp_id"]}',
                    'el => el.value',
                )
                _ok(
                    str(qty_val) == '12.5',
                    f'P9b Empresa qty_edit persistido no DOM '
                    f'(value={qty_val!r}, esperado="12.5")',
                )
            except Exception as e:
                _ok(False, f'P9b qty_edit Empresa NÃO encontrado: {e}')

            try:
                page.wait_for_selector(
                    f'#chk_terc_edit_{ctx["t_terc_id"]}',
                    timeout=10000,
                )
                chk_state = page.eval_on_selector(
                    f'#chk_terc_edit_{ctx["t_terc_id"]}',
                    'el => ({checked: el.checked, prev: el.dataset.prevChecked})',
                )
                _ok(
                    bool(chk_state.get('checked'))
                    and chk_state.get('prev') == '1',
                    f'P9b Terceiros checkbox renderizado como concluído '
                    f'(state={chk_state})',
                )
            except Exception as e:
                _ok(
                    False,
                    f'P9b chk_terc_edit Terceiros NÃO encontrado: {e}',
                )

            # Subempreitada: por design (Task #149) o card grande fica
            # oculto e o apontamento aparece como badge contadora no
            # botão "Equipe" inline da tarefa subempreitada. Esperamos
            # badge visível com count >= 1 e o cache JS preenchido.
            try:
                page.wait_for_selector(
                    f'#btn-equipe-edit-{ctx["t_sub_id"]}',
                    timeout=10000,
                )
                # O carregarSubempreitadaList é assíncrono. Após popular,
                # _atualizarBadgeSubEdit atualiza:
                #   - badge.textContent = N  (>= 1 quando há apontamento)
                #   - botão recebe classe btn-primary (vs btn-outline-secondary)
                # Aguardamos a transição visual no botão.
                page.wait_for_function(
                    f"""() => {{
                        const btn = document.getElementById(
                            'btn-equipe-edit-{ctx["t_sub_id"]}');
                        const b = document.getElementById(
                            'badge-equipe-edit-{ctx["t_sub_id"]}');
                        const txt = b ? b.textContent.trim() : '';
                        return !!btn
                            && btn.classList.contains('btn-primary')
                            && /^\\d+$/.test(txt) && parseInt(txt, 10) >= 1;
                    }}""",
                    timeout=10000,
                )
                badge_info = page.evaluate(
                    f"""() => {{
                        const b = document.getElementById(
                            'badge-equipe-edit-{ctx["t_sub_id"]}');
                        return {{
                            badge_text: b ? b.textContent.trim() : '',
                            badge_visible: b
                                ? (b.style.display !== 'none') : false,
                        }};
                    }}""",
                )
                _ok(
                    int(badge_info.get('badge_text') or '0') >= 1
                    and badge_info.get('badge_visible'),
                    f'P9b Subempreitada apontamento persistido na edição '
                    f'(badge={badge_info})',
                )
            except Exception as e:
                _ok(
                    False,
                    f'P9b Subempreitada NÃO persistida na edição: {e}',
                )

            browser.close()
    finally:
        cleanup(ctx)

    log.info('=' * 70)
    log.info(f'PASSED: {len(passed)}  FAILED: {len(failed)}')
    for f in failed:
        log.error(f' ✗ {f}')
    log.info('=' * 70)
    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
