"""
Task #166 — Coeficiente padrão no cadastro do insumo.

Cobre:
  1. Criar um insumo com coeficiente padrão 0,04 → grava no banco.
  2. /catalogo/api/insumos/buscar retorna o coeficiente_padrao no JSON.
  3. Editar o insumo alterando para 0,06 → persiste no banco.
  4. Composições já existentes referentes a esse insumo NÃO são alteradas
     ao salvar o cadastro do insumo (independência cadastro × composição).

Roda com:  python tests/test_insumo_coeficiente_padrao.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from app import app, db  # noqa: E402

app.config['WTF_CSRF_ENABLED'] = False
from models import (  # noqa: E402
    ComposicaoServico,
    Insumo,
    PrecoBaseInsumo,
    Servico,
    TipoUsuario,
    Usuario,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _check(cond: bool, label: str, falhas: list[str]):
    if cond:
        logger.info(f'PASS: {label}')
    else:
        logger.error(f'FAIL: {label}')
        falhas.append(label)


def teste_coeficiente_padrao_fluxo_completo(falhas: list[str]):
    suf = _suffix()
    with app.app_context():
        admin = Usuario(
            username=f'coef_admin_{suf}',
            email=f'coef_admin_{suf}@test.local',
            nome='Coef Admin',
            password_hash=generate_password_hash('Teste@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()

        # Serviço + insumo já-existente + composição com coeficiente próprio
        # — usado para confirmar que mexer no cadastro do insumo NÃO
        # altera composições já cadastradas (Step 6 da spec).
        ins_pre = Insumo(
            admin_id=admin.id,
            nome=f'__coef_pre_{suf}',
            tipo='MATERIAL',
            unidade='sc',
            coeficiente_padrao=Decimal('1'),
        )
        db.session.add(ins_pre)
        db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=admin.id, insumo_id=ins_pre.id,
            valor=Decimal('25'), vigencia_inicio=date(2020, 1, 1),
        ))
        svc = Servico(
            admin_id=admin.id, nome=f'__coef_svc_{suf}',
            categoria='Teste', unidade_medida='m2',
            imposto_pct=Decimal('0'), margem_lucro_pct=Decimal('0'),
        )
        db.session.add(svc)
        db.session.flush()
        comp = ComposicaoServico(
            admin_id=admin.id, servico_id=svc.id, insumo_id=ins_pre.id,
            coeficiente=Decimal('0.123456'),
        )
        db.session.add(comp)
        db.session.commit()

        comp_id = comp.id
        coef_original_composicao = Decimal(str(comp.coeficiente))

        # ── Cliente autenticado como o admin ──
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin.id)
                sess['_fresh'] = True

            # 1. POST criar insumo com coeficiente padrão 0,04
            nome_novo = f'__coef_novo_{suf}'
            resp = c.post('/catalogo/insumos/novo', data={
                'nome': nome_novo,
                'tipo': 'MATERIAL',
                'unidade': 'sc',
                'coeficiente_padrao': '0,04',
                'preco': '0,00',
            }, follow_redirects=False)
            _check(
                resp.status_code in (302, 303),
                f'POST /catalogo/insumos/novo redireciona '
                f'(status={resp.status_code})',
                falhas,
            )
            ins_novo = (
                Insumo.query.filter_by(admin_id=admin.id, nome=nome_novo)
                .first()
            )
            _check(
                ins_novo is not None,
                f'Insumo "{nome_novo}" foi criado',
                falhas,
            )
            if ins_novo is not None:
                _check(
                    Decimal(str(ins_novo.coeficiente_padrao)) == Decimal('0.04'),
                    f'coeficiente_padrao gravado = 0,04 '
                    f'(obtido {ins_novo.coeficiente_padrao})',
                    falhas,
                )

            # 2. GET /catalogo/api/insumos/buscar retorna coeficiente_padrao
            resp_api = c.get(
                f'/catalogo/api/insumos/buscar?q={nome_novo}'
            )
            _check(
                resp_api.status_code == 200,
                f'GET api/insumos/buscar 200 (status={resp_api.status_code})',
                falhas,
            )
            data = json.loads(resp_api.get_data(as_text=True) or '[]')
            achados = [d for d in data if d.get('nome') == nome_novo]
            _check(
                len(achados) == 1,
                f'API retorna o insumo recém-criado (achados={len(achados)})',
                falhas,
            )
            if achados:
                _check(
                    'coeficiente_padrao' in achados[0],
                    'JSON inclui campo coeficiente_padrao',
                    falhas,
                )
                _check(
                    abs(float(achados[0].get('coeficiente_padrao', 0)) - 0.04)
                    < 1e-9,
                    f'API.coeficiente_padrao == 0.04 '
                    f'(obtido {achados[0].get("coeficiente_padrao")})',
                    falhas,
                )

            # 3. POST editar insumo alterando para 0,06
            if ins_novo is not None:
                resp_edit = c.post(
                    f'/catalogo/insumos/{ins_novo.id}',
                    data={
                        'nome': ins_novo.nome,
                        'tipo': ins_novo.tipo,
                        'unidade': ins_novo.unidade,
                        'descricao': '',
                        'coeficiente_padrao': '0,06',
                    },
                    follow_redirects=False,
                )
                _check(
                    resp_edit.status_code in (302, 303),
                    f'POST editar insumo redireciona '
                    f'(status={resp_edit.status_code})',
                    falhas,
                )
                db.session.expire_all()
                ins_atualizado = Insumo.query.get(ins_novo.id)
                _check(
                    Decimal(str(ins_atualizado.coeficiente_padrao))
                    == Decimal('0.06'),
                    f'coeficiente_padrao após edição = 0,06 '
                    f'(obtido {ins_atualizado.coeficiente_padrao})',
                    falhas,
                )

        # 4. A composição existente deve estar inalterada
        db.session.expire_all()
        comp_atual = ComposicaoServico.query.get(comp_id)
        _check(
            comp_atual is not None
            and Decimal(str(comp_atual.coeficiente))
            == coef_original_composicao,
            f'Composição existente NÃO foi alterada '
            f'(coef original {coef_original_composicao}, '
            f'atual {comp_atual.coeficiente if comp_atual else "removida"})',
            falhas,
        )

        # Cleanup — remove tudo o que foi criado neste teste
        try:
            ComposicaoServico.query.filter_by(admin_id=admin.id).delete()
            PrecoBaseInsumo.query.filter_by(admin_id=admin.id).delete()
            Servico.query.filter_by(admin_id=admin.id).delete()
            Insumo.query.filter_by(admin_id=admin.id).delete()
            Usuario.query.filter_by(id=admin.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()


def main() -> int:
    falhas: list[str] = []
    teste_coeficiente_padrao_fluxo_completo(falhas)

    if falhas:
        logger.error('=' * 60)
        logger.error(f'❌ {len(falhas)} verificação(ões) falharam:')
        for f in falhas:
            logger.error(f'  - {f}')
        return 1
    logger.info('=' * 60)
    logger.info('✅ Task #166: todos os checks passaram')
    return 0


if __name__ == '__main__':
    sys.exit(main())
