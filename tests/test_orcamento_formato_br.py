"""
Task #165 — Teste de regressão: editar orçamento sem TypeError Decimal x float
e formatação pt-BR (R$ X.XXX,XX) presente na página de edição.

Cobre:
  1. Filtros Jinja `|brl` e `|num(N)` retornam string pt-BR para
     Decimal / float / int / None (sem TypeError).
  2. GET /orcamentos/<id>/editar retorna HTTP 200 quando o item tem
     composição com mistura de Decimal (do banco) e float (do JSON
     `composicao_snapshot`), e a página contém pelo menos um valor
     no formato `R$ N.NNN,NN`.

Roda com:  python tests/test_orcamento_formato_br.py
"""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, brl_filter, num_filter  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from models import (  # noqa: E402
    Orcamento,
    OrcamentoItem,
    TipoUsuario,
    Usuario,
)
from views.orcamentos_views import _parse_br_number, _parse_br_decimal  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


PADRAO_BRL = re.compile(r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}')


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _check(cond: bool, label: str, falhas: list[str]):
    if cond:
        logger.info(f'PASS: {label}')
    else:
        logger.error(f'FAIL: {label}')
        falhas.append(label)


def teste_filtros_brl_num(falhas: list[str]):
    """Filtros aceitam Decimal/float/int/None sem TypeError."""
    _check(brl_filter(Decimal('1540.00')) == 'R$ 1.540,00',
           'brl(Decimal 1540) → R$ 1.540,00', falhas)
    _check(brl_filter(1234567.89) == 'R$ 1.234.567,89',
           'brl(float 1234567.89) → R$ 1.234.567,89', falhas)
    _check(brl_filter(None) == 'R$ 0,00', 'brl(None) → R$ 0,00', falhas)
    _check(brl_filter(0) == 'R$ 0,00', 'brl(0) → R$ 0,00', falhas)
    _check(num_filter(Decimal('0.04'), 4) == '0,0400',
           'num(Decimal 0.04, 4) → 0,0400', falhas)
    _check(num_filter(25, 4) == '25,0000', 'num(25, 4) → 25,0000', falhas)
    _check(num_filter(None, 2) == '0,00', 'num(None, 2) → 0,00', falhas)

    # Caso crítico do bug: multiplicar float (do JSON) com Decimal (do banco)
    # e formatar — não pode dar TypeError.
    coef_float = 0.04
    qtd_decimal = Decimal('25')
    try:
        # No template real isto era `coef|float * qtd|float`. O filtro |num
        # também precisa aceitar o resultado direto sem quebrar.
        produto = float(coef_float) * float(qtd_decimal)
        out = num_filter(produto, 4)
        _check(out == '1,0000', f'num(float*Decimal coerced, 4) → 1,0000 (got {out})', falhas)
    except TypeError as e:
        _check(False, f'multiplicação float*Decimal não pode levantar TypeError ({e})', falhas)


def teste_parse_br_input(falhas: list[str]):
    """Backend aceita valores em pt-BR ('1.234,56') e en-US ('1234.56')."""
    _check(_parse_br_number('1.234,56') == 1234.56,
           "_parse_br_number('1.234,56') → 1234.56", falhas)
    _check(_parse_br_number('1234.56') == 1234.56,
           "_parse_br_number('1234.56') → 1234.56", falhas)
    _check(_parse_br_number('0,04') == 0.04,
           "_parse_br_number('0,04') → 0.04", falhas)
    _check(_parse_br_number('') == 0.0, "_parse_br_number('') → 0.0", falhas)
    _check(_parse_br_number(None) == 0.0, "_parse_br_number(None) → 0.0", falhas)
    _check(_parse_br_number('lixo') == 0.0,
           "_parse_br_number('lixo') → 0.0 (não levanta)", falhas)
    _check(_parse_br_decimal('1.234,56') == Decimal('1234.56'),
           "_parse_br_decimal('1.234,56') → Decimal 1234.56", falhas)
    _check(_parse_br_decimal('25') == Decimal('25'),
           "_parse_br_decimal('25') → Decimal 25", falhas)


def teste_editar_orcamento_http_200(falhas: list[str]):
    """GET /orcamentos/<id>/editar retorna 200 com composição mista
    Decimal/float e contém pelo menos um valor formatado em pt-BR.
    """
    suf = _suffix()
    with app.app_context():
        admin = Usuario(
            username=f'fmt_admin_{suf}',
            email=f'fmt_admin_{suf}@test.local',
            nome='Format BR Admin',
            password_hash=generate_password_hash('Teste@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()

        orc = Orcamento(
            admin_id=admin.id,
            numero=f'ORC-FMT-{suf[-6:]}',
            titulo='Orçamento Formato BR',
            cliente_nome='Cliente Teste',
            criado_por=admin.id,
            status='rascunho',
            custo_total=Decimal('1540.00'),
            venda_total=Decimal('2000.00'),
            lucro_total=Decimal('460.00'),
        )
        db.session.add(orc)
        db.session.flush()

        # Cenário do bug: composicao_snapshot com floats (origem JSON) e
        # OrcamentoItem.quantidade Decimal (origem do banco).
        snapshot_misto = [
            {
                'tipo': 'MATERIAL',
                'insumo_id': None,
                'nome': 'Bloco cerâmico 9x19x19',
                'unidade': 'un',
                'coeficiente': 25.0,            # float (do JSON)
                'preco_unitario': 1.54,         # float (do JSON)
                'subtotal_unitario': 38.5,      # float (do JSON)
            },
            {
                'tipo': 'MATERIAL',
                'insumo_id': None,
                'nome': 'Argamassa colante AC-II',
                'unidade': 'sc',
                'coeficiente': 0.04,            # float
                'preco_unitario': 30.0,         # float
                'subtotal_unitario': 1.2,       # float
            },
        ]
        item = OrcamentoItem(
            admin_id=admin.id,
            orcamento_id=orc.id,
            ordem=1,
            descricao='Alvenaria de bloco cerâmico',
            unidade='m2',
            quantidade=Decimal('100'),          # Decimal (do banco)
            composicao_snapshot=snapshot_misto,
            custo_unitario=Decimal('39.7000'),
            preco_venda_unitario=Decimal('51.5500'),
            custo_total=Decimal('3970.00'),
            venda_total=Decimal('5155.00'),
            lucro_total=Decimal('1185.00'),
        )
        db.session.add(item)
        db.session.commit()

        try:
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['_user_id'] = str(admin.id)
                    sess['_fresh'] = True
                resp = c.get(f'/orcamentos/{orc.id}/editar')

            _check(
                resp.status_code == 200,
                f'GET editar retorna 200 (status={resp.status_code})',
                falhas,
            )
            html = resp.get_data(as_text=True) if resp.status_code == 200 else ''
            _check(
                bool(PADRAO_BRL.search(html)),
                'HTML contém pelo menos um valor R$ N.NNN,NN (formato BR)',
                falhas,
            )
            # Valores específicos esperados do snapshot.
            _check(
                'R$ 1.540,00' in html or 'R$ 5.155,00' in html or 'R$ 3.970,00' in html,
                'HTML contém pelo menos um total esperado do orçamento',
                falhas,
            )
            # Algum número não-monetário formatado com vírgula decimal
            # (consumo total: coef 25 × qtd 100 = 2.500,0000).
            _check(
                '2.500,0000' in html or '4,0000' in html,
                'HTML contém número formatado em pt-BR (vírgula decimal)',
                falhas,
            )
            # POST com quantidade em pt-BR ('1.234,56') deve gravar como
            # Decimal('1234.56') sem ValueError (Task #165 — input BR).
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['_user_id'] = str(admin.id)
                    sess['_fresh'] = True
                resp_post = c.post(
                    f'/orcamentos/itens/{item.id}/atualizar',
                    data={
                        'descricao': item.descricao,
                        'unidade': item.unidade,
                        'quantidade': '1.234,56',
                        'imposto_pct': '0,00',
                        'margem_pct': '30,00',
                        'comp_tipo': ['MATERIAL'],
                        'comp_nome': ['Bloco BR'],
                        'comp_unidade': ['un'],
                        'comp_coeficiente': ['25,5'],
                        'comp_preco_unitario': ['1.540,00'],
                        'comp_insumo_id': [''],
                    },
                    follow_redirects=False,
                )
            _check(
                resp_post.status_code in (302, 303),
                f'POST atualizar com input BR retorna redirect (status={resp_post.status_code})',
                falhas,
            )
            db.session.expire_all()
            it_after = db.session.get(OrcamentoItem, item.id)
            _check(
                it_after.quantidade == Decimal('1234.56'),
                f'quantidade gravada como 1234.56 (got {it_after.quantidade})',
                falhas,
            )
            comp = it_after.composicao_snapshot or []
            _check(
                bool(comp) and abs(comp[0].get('coeficiente', 0) - 25.5) < 1e-6,
                f"composição coeficiente 25.5 (got {comp[0].get('coeficiente') if comp else None})",
                falhas,
            )
            _check(
                bool(comp) and abs(comp[0].get('preco_unitario', 0) - 1540.0) < 1e-6,
                f"composição preco_unitario 1540.0 (got {comp[0].get('preco_unitario') if comp else None})",
                falhas,
            )
        finally:
            # Limpeza
            try:
                db.session.delete(item)
                db.session.delete(orc)
                db.session.delete(admin)
                db.session.commit()
            except Exception:
                db.session.rollback()


def main():
    falhas: list[str] = []
    teste_filtros_brl_num(falhas)
    teste_parse_br_input(falhas)
    teste_editar_orcamento_http_200(falhas)
    print('\n' + '=' * 70)
    if falhas:
        print(f'❌ {len(falhas)} falha(s):')
        for f in falhas:
            print(f'  - {f}')
        sys.exit(1)
    print('✅ Todos os testes passaram (Task #165)')


if __name__ == '__main__':
    main()
