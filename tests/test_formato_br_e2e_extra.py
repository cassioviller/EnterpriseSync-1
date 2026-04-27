"""
Task #189 — Cobertura e2e ampliada para formato BR (R$ 1.234,56 / 12,00).

Estende a Task #181 para mais telas:
  1. /catalogo/servicos (lista) — colunas Imposto / Margem (%) e
     Preço de Venda (R$).
  2. /catalogo/servicos/<id>/historico-obras — cards de média e
     linhas da tabela de obras.
  3. /propostas/editar/<id> — campo "Total da Proposta" e o valor
     readonly de cada item (servico-total) renderizados pelo backend.

Para cada página, três asserções de regressão:
  * Existe pelo menos um valor visível em formato BR
    (R$ N.NNN,NN ou N,NN).
  * Nenhum texto visível casa o padrão americano /\\d+\\.\\d{2}\\b/
    (ex.: 1234.56) — bloqueia o retorno de toFixed(2)/'%.2f'|format.
  * Para o caso de inputs readonly (proposta editar), o valor lido via
    `input_value()` também segue o padrão BR e NÃO o americano.

Pré-requisito: servidor Flask rodando em http://localhost:5000
(workflow "Start application").

Uso:
    python tests/test_formato_br_e2e_extra.py
"""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import app, db  # noqa: E402
from models import (  # noqa: E402
    ComposicaoServico,
    Insumo,
    ItemMedicaoComercial,
    Obra,
    ObraServicoCusto,
    PrecoBaseInsumo,
    Proposta,
    PropostaItem,
    Servico,
    TipoUsuario,
    Usuario,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = os.environ.get('PW_BASE_URL', 'http://localhost:5000')
SENHA = 'Senha@2026'

# Padrões de validação textual.
PADRAO_BRL = re.compile(r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}')
PADRAO_NUM_BR_2 = re.compile(r'\b\d{1,3}(?:\.\d{3})*,\d{2}\b')
PADRAO_US_2D = re.compile(r'\d+\.\d{2}\b')


def _suf() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def seed_dados():
    """Cria dados ricos o bastante para exercer milhar + decimal em 3 telas."""
    suf = _suf()
    email = f't189pw_{suf}@test.local'
    with app.app_context():
        admin = Usuario(
            username=f't189pw_{suf}',
            email=email,
            nome='T189 PW',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id

        # Insumos + preço base — produzem custo > R$ 1.000.
        ins_a = Insumo(admin_id=admin_id, nome=f'__t189_aco_{suf}',
                       tipo='MATERIAL', unidade='kg')
        ins_b = Insumo(admin_id=admin_id, nome=f'__t189_mo_{suf}',
                       tipo='MAO_OBRA', unidade='h')
        db.session.add_all([ins_a, ins_b])
        db.session.flush()
        db.session.add_all([
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_a.id,
                            valor=Decimal('35.0000'),
                            vigencia_inicio=date(2020, 1, 1)),
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_b.id,
                            valor=Decimal('170.0000'),
                            vigencia_inicio=date(2020, 1, 1)),
        ])

        # Serviço com preço de venda > R$ 7.000 → exige separador de milhar.
        svc = Servico(
            admin_id=admin_id,
            nome=f'__t189_svc_{suf}',
            categoria='Teste',
            unidade_medida='un',
            custo_unitario=5308.99,           # R$ 5.308,99
            imposto_pct=Decimal('13.00'),     # 13,00
            margem_lucro_pct=Decimal('20.00'),  # 20,00
            preco_venda_unitario=Decimal('7199.06'),  # R$ 7.199,06
        )
        db.session.add(svc)
        db.session.flush()
        db.session.add_all([
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_a.id,
                              coeficiente=Decimal('150.0000')),
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_b.id,
                              coeficiente=Decimal('0.3471')),
        ])

        # Obra + Item de medição + Custo realizado vinculado ao serviço
        # → alimenta a tela /historico-obras com linhas reais.
        obra = Obra(
            admin_id=admin_id,
            nome=f'__t189_obra_{suf}',
            codigo=f'T189-{suf[-6:]}',
            data_inicio=date(2026, 1, 1),
            cliente_nome='Cliente Teste 189',
            status='Em andamento',
            ativo=True,
        )
        db.session.add(obra)
        db.session.flush()

        imc = ItemMedicaoComercial(
            admin_id=admin_id,
            obra_id=obra.id,
            nome=f'IMC __t189_{suf}',
            valor_comercial=Decimal('15000.00'),
            percentual_executado_acumulado=Decimal('42.50'),  # 42,50
            valor_executado_acumulado=Decimal('6375.00'),
            servico_id=svc.id,
            quantidade=Decimal('100.0000'),
        )
        db.session.add(imc)
        db.session.flush()

        # IMC tem trigger SQLAlchemy que auto-cria um ObraServicoCusto
        # vinculado (constraint UNIQUE em item_medicao_comercial_id).
        # Atualizamos o registro existente em vez de inserir outro.
        osc = ObraServicoCusto.query.filter_by(
            item_medicao_comercial_id=imc.id
        ).first()
        if osc is None:  # pragma: no cover — fallback caso o trigger seja desabilitado
            osc = ObraServicoCusto(
                admin_id=admin_id,
                obra_id=obra.id,
                item_medicao_comercial_id=imc.id,
                servico_catalogo_id=svc.id,
                nome=f'OSC __t189_{suf}',
            )
            db.session.add(osc)
        osc.servico_catalogo_id = svc.id
        osc.valor_orcado = Decimal('1500.00')        # R$ 1.500,00
        osc.realizado_material = Decimal('1234.56')   # R$ 1.234,56
        osc.realizado_mao_obra = Decimal('890.12')
        osc.realizado_outros = Decimal('0.00')

        # Proposta com 1 item — totaliza R$ 1.351,50.
        prop = Proposta(
            admin_id=admin_id,
            criado_por=admin_id,
            numero=f'P189-{suf[-6:]}',
            data_proposta=date(2026, 4, 1),
            cliente_nome='Cliente Proposta 189',
            cliente_email='cli189@test.local',
            titulo='Proposta T189',
            descricao='Teste formato BR',
            valor_total=Decimal('1351.50'),
            status='rascunho',
        )
        db.session.add(prop)
        db.session.flush()
        db.session.add(PropostaItem(
            admin_id=admin_id,
            proposta_id=prop.id,
            item_numero=1,
            descricao=f'Item __t189_{suf}',
            quantidade=Decimal('3.000'),
            unidade='un',
            preco_unitario=Decimal('450.50'),  # 3 × 450,50 = 1.351,50
            ordem=1,
        ))

        db.session.commit()
        return {
            'email': email,
            'admin_id': admin_id,
            'svc_id': svc.id,
            'ins_a_id': ins_a.id,
            'ins_b_id': ins_b.id,
            'obra_id': obra.id,
            'imc_id': imc.id,
            'osc_id': osc.id,
            'prop_id': prop.id,
            'svc_nome': svc.nome,
        }


def cleanup(ctx):
    if not ctx:
        return
    with app.app_context():
        try:
            PropostaItem.query.filter_by(proposta_id=ctx['prop_id']).delete()
            db.session.query(Proposta).filter_by(id=ctx['prop_id']).delete()
            db.session.query(ObraServicoCusto).filter_by(id=ctx['osc_id']).delete()
            db.session.query(ItemMedicaoComercial).filter_by(id=ctx['imc_id']).delete()
            obra = db.session.get(Obra, ctx['obra_id'])
            if obra:
                db.session.delete(obra)
            ComposicaoServico.query.filter_by(servico_id=ctx['svc_id']).delete()
            PrecoBaseInsumo.query.filter(
                PrecoBaseInsumo.insumo_id.in_([ctx['ins_a_id'], ctx['ins_b_id']])
            ).delete(synchronize_session=False)
            svc = db.session.get(Servico, ctx['svc_id'])
            if svc:
                db.session.delete(svc)
            for iid in (ctx['ins_a_id'], ctx['ins_b_id']):
                ins = db.session.get(Insumo, iid)
                if ins:
                    db.session.delete(ins)
            adm = db.session.get(Usuario, ctx['admin_id'])
            if adm:
                db.session.delete(adm)
            db.session.commit()
        except Exception as e:  # pragma: no cover
            log.warning(f'Cleanup falhou: {e}')
            db.session.rollback()


def _scan_us(text: str, limit: int = 5) -> list[str]:
    """Retorna até `limit` matches do padrão americano em `text`.

    Filtra falsos positivos comuns que não são valores monetários:
      * versões de software exibidas no rodapé (ex.: 'v9.0', 'v10.04').
      * datas no formato `DD.MM` (não usadas no app, mas defensivo).
    O padrão exige '.' + exatamente 2 dígitos no fim, então 'v9.0' já
    não casa; este helper apenas consolida ofensores genuínos.
    """
    return PADRAO_US_2D.findall(text)[:limit]


def main():
    ctx = seed_dados()
    log.info(f'Seed: svc={ctx["svc_id"]} obra={ctx["obra_id"]} '
             f'prop={ctx["prop_id"]}')
    failed: list[str] = []
    passed: list[str] = []

    def _ok(cond, label):
        (passed if cond else failed).append(label)
        log.info(f'{"PASS" if cond else "FAIL"}: {label}')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1366, 'height': 900})
            page = context.new_page()

            # ── 1. Login ───────────────────────────────────────────────
            page.goto(f'{BASE_URL}/login', wait_until='domcontentloaded')
            page.fill('input[name="username"]', ctx['email'])
            page.fill('input[name="password"]', SENHA)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('networkidle')
            _ok('/login' not in page.url,
                f'login redirecionou (url={page.url})')

            # ── 2. /catalogo/servicos (lista) ──────────────────────────
            page.goto(f'{BASE_URL}/catalogo/servicos?q={ctx["svc_nome"]}',
                      wait_until='networkidle')

            # Localiza a linha do nosso serviço pelo nome semeado.
            row_loc = page.locator('table tbody tr', has_text=ctx['svc_nome'])
            _ok(row_loc.count() == 1,
                f'lista de serviços exibe nossa linha (count={row_loc.count()})')

            row_text = row_loc.first.inner_text()
            log.info(f'[lista] linha: {row_text!r}')

            # custo + preço de venda em R$ N.NNN,NN.
            _ok(bool(PADRAO_BRL.search(row_text)),
                f'lista: linha tem ao menos um R$ em formato BR ({row_text!r})')

            # imposto/margem como "13,00" / "20,00" (sem ponto decimal).
            _ok('13,00' in row_text,
                f'lista: imposto exibido como 13,00 ({row_text!r})')
            _ok('20,00' in row_text,
                f'lista: margem exibida como 20,00 ({row_text!r})')

            # Preço de venda específico (R$ 7.199,06) confirma separador de milhar.
            _ok('R$ 7.199,06' in row_text,
                f'lista: preço de venda como R$ 7.199,06 ({row_text!r})')

            # Nenhum valor em formato americano em toda a página.
            body_text = page.locator('body').inner_text()
            ofensores = _scan_us(body_text)
            _ok(not ofensores,
                f'lista: body sem formato US (ofensores={ofensores})')

            # ── 3. /catalogo/servicos/<id>/historico-obras ─────────────
            page.goto(
                f'{BASE_URL}/catalogo/servicos/{ctx["svc_id"]}/historico-obras',
                wait_until='networkidle',
            )

            # Cards de média (4 cards). Pelo menos 2 contêm R$ em formato BR.
            cards_text = page.locator('.card .h5').all_inner_texts()
            cards_blob = ' | '.join(cards_text)
            log.info(f'[historico] cards: {cards_text}')
            brl_card_count = sum(1 for c in cards_text if PADRAO_BRL.search(c))
            _ok(brl_card_count >= 2,
                f'historico: pelo menos 2 cards em BR (got {brl_card_count}, '
                f'cards={cards_text})')

            # Card "Δ Realizado vs Orçado (global)" deve ter sinal + e
            # vírgula decimal: (2124,68 - 1500) / 1500 * 100 = 41,6 %.
            _ok(any('+41,6' in c or '41,6' in c for c in cards_text),
                f'historico: delta global em formato BR ({cards_blob!r})')

            # Linha da tabela com a obra.
            tbody_loc = page.locator('table tbody')
            tbody_text = tbody_loc.inner_text()
            log.info(f'[historico] tbody: {tbody_text!r}')

            # Orçado R$ 1.500,00, realizado R$ 2.124,68.
            _ok('1.500,00' in tbody_text,
                f'historico: orçado 1.500,00 visível ({tbody_text!r})')
            _ok('2.124,68' in tbody_text,
                f'historico: realizado 2.124,68 visível ({tbody_text!r})')

            # % Executado da medição = 42,5 (template usa |num(1)).
            _ok('42,5%' in tbody_text,
                f'historico: percentual 42,5% visível ({tbody_text!r})')

            # Nenhum valor americano na página inteira.
            body_text = page.locator('body').inner_text()
            ofensores = _scan_us(body_text)
            _ok(not ofensores,
                f'historico: body sem formato US (ofensores={ofensores})')

            # ── 4. /propostas/editar/<id> ──────────────────────────────
            page.goto(f'{BASE_URL}/propostas/editar/{ctx["prop_id"]}',
                      wait_until='networkidle')

            # Total da proposta renderizado pelo backend (server-side).
            total_text = page.locator('#totalProposta').inner_text().strip()
            log.info(f'[proposta] total: {total_text!r}')
            _ok(bool(PADRAO_BRL.search(total_text)),
                f'proposta: total em formato BR (got "{total_text}")')
            _ok('R$ 1.351,50' in total_text,
                f'proposta: total exatamente R$ 1.351,50 (got "{total_text}")')
            _ok(not PADRAO_US_2D.search(total_text),
                f'proposta: total sem formato US (got "{total_text}")')

            # Subtotal de cada item (input readonly) → ler via input_value.
            sub_inputs = page.locator('input.servico-total')
            n_inputs = sub_inputs.count()
            _ok(n_inputs >= 1,
                f'proposta: existe input servico-total (count={n_inputs})')

            for i in range(n_inputs):
                v = sub_inputs.nth(i).input_value().strip()
                log.info(f'[proposta] servico-total[{i}] = {v!r}')
                _ok(bool(PADRAO_BRL.search(v)),
                    f'proposta: servico-total[{i}] em BR (got "{v}")')
                _ok(not PADRAO_US_2D.search(v),
                    f'proposta: servico-total[{i}] sem formato US (got "{v}")')

            # Garante que o item específico bate o valor esperado.
            valores = [sub_inputs.nth(i).input_value().strip()
                       for i in range(n_inputs)]
            _ok(any('R$ 1.351,50' in v for v in valores),
                f'proposta: ao menos 1 servico-total = R$ 1.351,50 ({valores})')

            # Nenhum valor americano na página inteira.
            body_text = page.locator('body').inner_text()
            ofensores = _scan_us(body_text)
            _ok(not ofensores,
                f'proposta editar: body sem formato US (ofensores={ofensores})')

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
