#!/usr/bin/env python3
"""Capturas de tela do manual do cronograma (Fase 5, editor v2).

Gera os PNGs de `docs/img/manual-cronograma/` que o
`scripts/manual_cronograma_pdf.py` embute em
`static/docs/manual-cronograma.pdf`. Rodar de novo quando a UI mudar,
depois regerar o PDF.

O que ele faz, na ordem:
  1. semeia um tenant de demonstração ("Vale Verde Engenharia", obra
     "Residencial Vila Verde") com hierarquia, vínculos TI/II/TT com lag,
     avanço real de RDO (tarefas ancoradas), caminho crítico e linha de
     base ativa — flags `cronograma_mpp` e `cronograma_editor_v2` ligadas;
  2. aplica um atraso via a rota PUT real (passa por `_com_undo`, então o
     botão Desfazer aparece habilitado e a coluna Desvio ganha valores);
  3. sobe o app em 127.0.0.1:5100 numa thread;
  4. loga e captura as telas com Playwright, usando o chromium do nix
     store (`CHROMIUM_BIN` para apontar outro binário);
  5. REMOVE o tenant de demonstração (use `--manter` para inspecionar).

O Playwright do projeto não tem navegadores baixados (falta libnspr4.so
para o `playwright install`), por isso o `executable_path` explícito.

Uso:
    python scripts/manual_cronograma_capturas.py [--manter]
"""
from __future__ import annotations

import os
import sys
import argparse
import socket
import threading
import time
import uuid
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('SCHEDULER_ENABLED', '0')

PORTA = 5100
BASE = f'http://127.0.0.1:{PORTA}'
SENHA = 'Manual!2026'
CHROMIUM_BIN = os.environ.get('CHROMIUM_BIN') or (
    '/nix/store/43y6k6fj85l4kcd1yan43hpdld6nmjmp-'
    'ungoogled-chromium-131.0.6778.204/bin/chromium'
)
DEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'docs', 'img', 'manual-cronograma')

# Índices de coluna da grade (Fase 2): 2=nome, 3=duração, 6=predecessoras.
COL_NOME, COL_PRED = 2, 6


def _seed():
    """Cria o tenant de demonstração e devolve (admin_id, username, obra_id,
    id da tarefa a atrasar)."""
    from werkzeug.security import generate_password_hash
    from app import db
    from models import (
        Cliente, CronogramaBaseline, CronogramaBaselineItem, Obra,
        RDO, RDOApontamentoCronograma, TarefaCronograma, TarefaVinculo,
        TipoUsuario, Usuario,
    )
    from services.cronograma_scheduler import recalcular_obra
    from scripts.flag_cronograma_mpp import definir_flag as _flag_mpp
    from scripts.flag_cronograma_editor_v2 import definir_flag as _flag_v2

    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'engenharia_{suf[:4]}',
        email=f'manual_{suf}@demo.local',
        nome='Vale Verde Engenharia',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    cliente = Cliente(admin_id=admin.id, nome='Condomínio Vila Verde',
                      email=f'cli_{suf}@demo.local', telefone='11999990000')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome='Residencial Vila Verde', codigo=f'MAN-{suf}',
                admin_id=admin.id, cliente_id=cliente.id,
                status='Em andamento', data_inicio=date(2026, 7, 6))
    db.session.add(obra)
    db.session.commit()

    _flag_mpp(admin.id, True)
    _flag_v2(admin.id, True)

    from models import ConfiguracaoEmpresa
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    if cfg:
        cfg.nome_empresa = 'Vale Verde Engenharia'
        db.session.commit()

    def T(nome, ordem, pai=None, dur=5, ini=date(2026, 7, 6), fim=None):
        t = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id, nome_tarefa=nome,
            ordem=ordem, duracao_dias=dur, data_inicio=ini,
            data_fim=fim or ini, is_cliente=False,
            tarefa_pai_id=pai.id if pai else None,
        )
        db.session.add(t)
        db.session.flush()
        return t

    # Estrutura DFS (numeração visual entre parênteses):
    prelim = T('Serviços Preliminares', 1)                       # (1)
    limpeza = T('Limpeza do terreno', 2, prelim, 3,              # (2)
                date(2026, 7, 6), date(2026, 7, 8))
    canteiro = T('Instalação do canteiro', 3, prelim, 4,         # (3)
                 date(2026, 7, 9), date(2026, 7, 14))
    fund = T('Fundações', 4)                                     # (4)
    escav = T('Escavação das sapatas', 5, fund, 5,               # (5)
              date(2026, 7, 15), date(2026, 7, 21))
    armacao = T('Armação e formas', 6, fund, 6,                  # (6)
                date(2026, 7, 17), date(2026, 7, 24))
    concret = T('Concretagem das sapatas', 7, fund, 4)           # (7)
    estr = T('Estrutura', 8)                                     # (8)
    pilares = T('Pilares do térreo', 9, estr, 8)                 # (9)
    laje = T('Vigas e laje do térreo', 10, estr, 10)             # (10)
    alv = T('Alvenaria e instalações', 11)                       # (11)
    alvenaria = T('Alvenaria do térreo', 12, alv, 12)            # (12)
    instal = T('Instalações elétricas e hidráulicas',            # (13)
               13, alv, 10)
    acab = T('Acabamento', 14)                                   # (14)
    reboco = T('Reboco interno', 15, acab, 8)                    # (15)
    pintura = T('Pintura', 16, acab, 6)                          # (16)

    def V(pred, suc, tipo='TI', lag=0):
        db.session.add(TarefaVinculo(
            admin_id=admin.id, obra_id=obra.id,
            predecessora_id=pred.id, sucessora_id=suc.id,
            tipo=tipo, lag_dias=lag))

    V(limpeza, canteiro)
    V(canteiro, escav)
    V(escav, armacao, 'II', 2)
    V(armacao, concret, 'TI', 1)
    V(concret, pilares)
    V(pilares, laje)
    V(laje, alvenaria, 'TI', 2)
    V(alvenaria, instal, 'II', 3)
    V(alvenaria, reboco)
    V(reboco, pintura, 'TI', 1)
    V(instal, pintura, 'TT', 2)
    db.session.commit()

    def RDOap(tarefa, pct, dia):
        rdo = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:12]}',
                  data_relatorio=dia, obra_id=obra.id, admin_id=admin.id)
        db.session.add(rdo)
        db.session.flush()
        db.session.add(RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id,
            quantidade_executada_dia=pct, quantidade_acumulada=pct,
            percentual_realizado=pct, admin_id=admin.id))
        db.session.commit()

    # Tarefas iniciadas ficam ANCORADAS: o motor não as move, mas elas
    # empurram as sucessoras — exatamente o que o manual descreve.
    RDOap(limpeza, 100.0, date(2026, 7, 8))
    RDOap(canteiro, 100.0, date(2026, 7, 14))
    RDOap(escav, 100.0, date(2026, 7, 21))
    RDOap(armacao, 60.0, date(2026, 7, 23))

    recalcular_obra(obra.id, admin.id)

    # Linha de base do plano recém-calculado (mesma semântica da rota).
    baseline = CronogramaBaseline(
        obra_id=obra.id, admin_id=admin.id,
        nome='Plano aprovado — julho/2026',
        criada_por=admin.id, ativa=True, is_cliente=False)
    db.session.add(baseline)
    db.session.flush()
    datadas = (TarefaCronograma.query
               .filter_by(obra_id=obra.id, admin_id=admin.id, is_cliente=False)
               .filter(TarefaCronograma.ativa.is_(True))
               .filter(TarefaCronograma.data_inicio.isnot(None))
               .filter(TarefaCronograma.data_fim.isnot(None))
               .all())
    for t in datadas:
        db.session.add(CronogramaBaselineItem(
            baseline_id=baseline.id, tarefa_id=t.id, admin_id=admin.id,
            data_inicio=t.data_inicio, data_fim=t.data_fim,
            duracao_dias=t.duracao_dias))
    db.session.commit()

    return admin.id, admin.username, obra.id, concret.id


def _atrasar_via_rota(app, username, obra_id, tarefa_id):
    """PUT real (test client): passa por `_com_undo`, habilita o Desfazer e
    gera desvio contra a baseline (4 → 7 dias na concretagem)."""
    c = app.test_client()
    r = c.post('/login', data={'username': username, 'password': SENHA})
    assert r.status_code in (302, 200), r.status_code
    r = c.put(f'/cronograma/obra/{obra_id}/tarefa/{tarefa_id}',
              json={'duracao_dias': 7})
    assert r.status_code == 200, r.get_data(as_text=True)[:400]


def _subir_servidor(app):
    th = threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=PORTA, debug=False,
                               use_reloader=False, threaded=True),
        daemon=True)
    th.start()
    for _ in range(100):
        try:
            with socket.create_connection(('127.0.0.1', PORTA), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f'Servidor não subiu na porta {PORTA}')


def _capturar(username, obra_id):
    from playwright.sync_api import sync_playwright

    os.makedirs(DEST, exist_ok=True)

    def dest(nome):
        return os.path.join(DEST, nome)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROMIUM_BIN,
            args=['--no-sandbox', '--disable-gpu'])
        # device_scale_factor=2: PNG em 2x para o PDF impresso não serrilhar.
        page = browser.new_page(viewport={'width': 1600, 'height': 1150},
                                device_scale_factor=2)

        page.goto(f'{BASE}/login')
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', SENHA)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        page.goto(f'{BASE}/cronograma/obra/{obra_id}')
        page.wait_for_selector('#ganttContainer .gantt-bar', timeout=15000)
        page.wait_for_load_state('networkidle')

        # Grupos começam recolhidos — expande tudo para as capturas.
        page.evaluate("""() => {
          document.querySelectorAll('.toggle-btn[data-expanded="false"]')
            .forEach(b => b.click());
        }""")
        page.wait_for_timeout(400)

        # 01 — visão geral (grade + Gantt)
        page.screenshot(path=dest('01-visao-geral.png'))

        # 02 — toolbar do editor (grupo de botões do cabeçalho)
        page.locator('div.d-flex.gap-2.flex-wrap').first.screenshot(
            path=dest('02-toolbar.png'))

        # 03 — célula de nome em edição (F2)
        linha_alv = page.locator('tr[data-testid="cronograma-tarefa"]',
                                 has_text='Alvenaria do térreo').first
        linha_alv.locator('td').nth(COL_NOME).click()
        page.keyboard.press('F2')
        page.wait_for_timeout(300)
        page.locator('#leftPane').screenshot(path=dest('03-grade-edicao.png'))
        page.keyboard.press('Escape')

        # 04 — célula de predecessoras em edição (formato 15TI+1;13TT+2)
        linha_pin = page.locator('tr[data-testid="cronograma-tarefa"]',
                                 has_text='Pintura').first
        linha_pin.locator('td').nth(COL_PRED).click()
        page.keyboard.press('F2')
        page.wait_for_timeout(300)
        page.locator('#leftPane').screenshot(path=dest('04-predecessoras.png'))
        page.keyboard.press('Escape')

        # 05 — Gantt com caminho crítico (barras vermelhas) e baseline
        # (cinza). As tarefas críticas ficam no fim do projeto — rola o
        # Gantt até lá.
        page.eval_on_selector(
            '#ganttPane', 'el => el.scrollLeft = el.scrollWidth * 0.62')
        page.wait_for_timeout(300)
        page.locator('#ganttPane').screenshot(path=dest('05-gantt-critico.png'))
        page.eval_on_selector('#ganttPane', 'el => el.scrollLeft = 0')

        # 06 — coluna Desvio: rola a grade até o fim das colunas
        page.eval_on_selector('#leftScroll', 'el => el.scrollLeft = el.scrollWidth')
        page.wait_for_timeout(300)
        page.locator('#leftPane').screenshot(path=dest('06-desvio.png'))
        page.eval_on_selector('#leftScroll', 'el => el.scrollLeft = 0')

        browser.close()

    print(f'[OK] Capturas gravadas em {DEST}')


def _limpar(admin_id):
    from app import db
    from models import (
        CalendarioEmpresa, Cliente, ConfiguracaoEmpresa, CronogramaAcao,
        CronogramaBaseline, CronogramaBaselineItem, Obra, RDO,
        RDOApontamentoCronograma, TarefaCronograma, TarefaVinculo, Usuario,
    )
    db.session.rollback()
    for Model in (RDOApontamentoCronograma, RDO, TarefaVinculo,
                  CronogramaBaselineItem, CronogramaBaseline, CronogramaAcao,
                  TarefaCronograma, Obra, Cliente, CalendarioEmpresa,
                  ConfiguracaoEmpresa):
        (db.session.query(Model)
         .filter_by(admin_id=admin_id)
         .delete(synchronize_session=False))
    db.session.query(Usuario).filter_by(id=admin_id).delete(
        synchronize_session=False)
    db.session.commit()
    print(f'[OK] Tenant de demonstração {admin_id} removido')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manter', action='store_true',
                    help='não remove o tenant de demonstração ao final')
    opts = ap.parse_args()

    import main as _main  # noqa: F401 — registra todos os blueprints
    from app import app

    app.config['WTF_CSRF_ENABLED'] = False  # servidor local de captura apenas

    admin_id = None
    try:
        with app.app_context():
            admin_id, username, obra_id, tarefa_id = _seed()
            print(f'[OK] Tenant {admin_id} ({username}) obra {obra_id}')
        _atrasar_via_rota(app, username, obra_id, tarefa_id)
        _subir_servidor(app)
        _capturar(username, obra_id)
    finally:
        if admin_id is not None and not opts.manter:
            with app.app_context():
                _limpar(admin_id)
        elif admin_id is not None:
            print(f'[!] Tenant {admin_id} MANTIDO (--manter); '
                  f'login {username} / {SENHA} em {BASE}')


if __name__ == '__main__':
    main()
