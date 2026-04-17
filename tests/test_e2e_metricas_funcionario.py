"""
Teste E2E — Serviço único de Métricas/KPIs de Funcionários (Task #98).

Cobre:
  • Modo SALARIO (v1) — fórmula horas × valor_hora + extras × 1.5.
  • Modo DIARIA (v2) — valor_diaria × dias_pagos + extras equivalentes.
  • Override por funcionário em ambas as direções (tenant v1 com diarista,
    tenant v2 com salarista).
  • Composição completa de custo: MO + VA + VT + Alimentação real
    (RegistroAlimentacao + AlimentacaoLancamento) + Reembolsos
    + Almoxarifado em posse (consumível e serializado).

Executa com:  python tests/test_e2e_metricas_funcionario.py
"""
import os
import sys
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra,
    RegistroPonto, RegistroAlimentacao,
    AlimentacaoLancamento, AlimentacaoLancamentoItem, Restaurante,
    ReembolsoFuncionario,
    AlmoxarifadoCategoria, AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
)
from services.funcionario_metrics import (
    calcular_metricas_funcionario,
    calcular_metricas_lista,
    agregar_kpis_geral,
    get_modo_remuneracao,
    calcular_valor_hora,
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def _suffix():
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


class MetricasTestRunner:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.created_admin_ids = []

    def _assert(self, cond, label):
        if cond:
            self.passed.append(label)
            logger.info(f"PASS: {label}")
        else:
            self.failed.append(label)
            logger.error(f"FAIL: {label}")

    def _almost(self, a, b, tol=0.01):
        return abs(float(a) - float(b)) <= tol

    # ── Fixtures ─────────────────────────────────────────────────────────
    def _criar_admin(self, versao):
        sfx = _suffix()
        adm = Usuario(
            username=f'metr_{versao}_{sfx}',
            email=f'metr_{versao}_{sfx}@test.local',
            nome=f'Admin Metricas {versao}',
            password_hash=generate_password_hash('Teste@2025'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema=versao,
        )
        db.session.add(adm)
        db.session.flush()
        self.created_admin_ids.append(adm.id)
        return adm

    def _criar_funcionario(self, admin, *, tipo, salario=None, valor_diaria=None,
                          valor_va=0, valor_vt=0, nome_extra=''):
        sfx = _suffix()
        f = Funcionario(
            codigo=f'FM{admin.id}{sfx[-4:]}',
            nome=f'Func {tipo} {nome_extra} {sfx[-6:]}',
            cpf=f'{admin.id:03d}{sfx[-8:]}'[:14],
            data_admissao=date.today() - timedelta(days=30),
            tipo_remuneracao=tipo,
            salario=salario,
            valor_diaria=valor_diaria,
            valor_va=valor_va,
            valor_vt=valor_vt,
            ativo=True,
            admin_id=admin.id,
        )
        db.session.add(f)
        db.session.flush()
        return f

    def _criar_obra(self, admin):
        sfx = _suffix()
        o = Obra(
            nome=f'Obra Met {sfx[-6:]}',
            codigo=f'OM{admin.id}{sfx[-4:]}',
            data_inicio=date.today(),
            admin_id=admin.id,
            ativo=True,
        )
        db.session.add(o)
        db.session.flush()
        return o

    def _registrar_dias_trabalhados(self, funcionario, obra, datas, *,
                                    horas=8.0, extras=0.0):
        for d in datas:
            r = RegistroPonto(
                funcionario_id=funcionario.id,
                obra_id=obra.id,
                admin_id=funcionario.admin_id,
                data=d,
                hora_entrada=time(8, 0),
                hora_saida=time(17, 0),
                horas_trabalhadas=horas,
                horas_extras=extras,
                tipo_registro='trabalhado',
            )
            db.session.add(r)
        db.session.flush()

    # ── Cenário 1: SALARIO em tenant v1 ─────────────────────────────────
    def cenario_salarista_v1(self):
        adm = self._criar_admin('v1')
        func = self._criar_funcionario(
            adm, tipo='salario', salario=2200.00, valor_va=15.00, valor_vt=8.00
        )
        obra = self._criar_obra(adm)
        di = date.today().replace(day=1)
        df = date.today()
        # 5 dias trabalhados, 1 com 2h extras
        dias = [di + timedelta(days=i) for i in range(5)]
        self._registrar_dias_trabalhados(func, obra, dias[:4])
        self._registrar_dias_trabalhados(func, obra, [dias[4]], extras=2.0)
        db.session.commit()

        m = calcular_metricas_funcionario(func, di, df, adm.id)
        self._assert(m['modo_remuneracao'] == 'salario',
                     f"v1 salarista: modo='salario' (got {m['modo_remuneracao']})")
        self._assert(m['horas_trabalhadas'] == 40.0,
                     f"v1 salarista: 40h trabalhadas (got {m['horas_trabalhadas']})")
        self._assert(m['horas_extras'] == 2.0,
                     f"v1 salarista: 2h extras (got {m['horas_extras']})")
        self._assert(m['dias_pagos'] == 5,
                     f"v1 salarista: 5 dias pagos (got {m['dias_pagos']})")
        # VA/VT aplicados em salarista também (Task #98 — soma TUDO)
        self._assert(self._almost(m['custo_va'], 5 * 15.0),
                     f"v1 salarista: VA=5×15=75 (got {m['custo_va']})")
        self._assert(self._almost(m['custo_vt'], 5 * 8.0),
                     f"v1 salarista: VT=5×8=40 (got {m['custo_vt']})")
        self._assert(m['valor_hora_atual'] > 0,
                     f"v1 salarista: valor_hora_atual > 0 (got {m['valor_hora_atual']})")
        # custo_total = MO + VA + VT (sem alim/reemb/almox neste cenário)
        esperado_min = m['custo_mao_obra'] + m['custo_va'] + m['custo_vt']
        self._assert(self._almost(m['custo_total'], esperado_min),
                     f"v1 salarista: custo_total=MO+VA+VT")

    # ── Cenário 1b: DIARISTA OVERRIDE em tenant v1 (override vence) ─────
    def cenario_diarista_override_em_v1(self):
        """Tenant v1 — funcionário com tipo_remuneracao='diaria' deve
        aplicar modo diarista (override por funcionário vence o tenant).
        """
        adm = self._criar_admin('v1')  # tenant v1
        diarista = self._criar_funcionario(
            adm, tipo='diaria', valor_diaria=200.00,
            valor_va=10.00, valor_vt=5.00, nome_extra='override_v1',
        )
        obra = self._criar_obra(adm)
        di = date.today().replace(day=1)
        df = date.today()
        dias = [di + timedelta(days=i) for i in range(4)]
        # 3 dias trabalhados + 1 falta_justificada (diarista NÃO paga essa)
        self._registrar_dias_trabalhados(diarista, obra, dias[:3])
        db.session.add(RegistroPonto(
            funcionario_id=diarista.id, obra_id=obra.id, admin_id=adm.id,
            data=dias[3], horas_trabalhadas=0, horas_extras=0,
            tipo_registro='falta_justificada',
        ))
        db.session.commit()

        m = calcular_metricas_funcionario(diarista, di, df, adm.id)
        self._assert(m['modo_remuneracao'] == 'diaria',
                     f"v1+override diarista: modo='diaria' (got {m['modo_remuneracao']})")
        self._assert(m['dias_pagos'] == 3,
                     f"v1+override diarista: dias_pagos=3 (NÃO paga falta_just) (got {m['dias_pagos']})")
        self._assert(m['faltas_justificadas'] == 1,
                     f"v1+override diarista: 1 falta justificada contada (got {m['faltas_justificadas']})")
        self._assert(self._almost(m['custo_mao_obra'], 3 * 200.0),
                     f"v1+override diarista: MO=3×200=600 (got {m['custo_mao_obra']})")
        self._assert(self._almost(m['custo_va'], 3 * 10.0),
                     f"v1+override diarista: VA=3×10=30, NÃO 4×10 (got {m['custo_va']})")
        self._assert(self._almost(m['custo_vt'], 3 * 5.0),
                     f"v1+override diarista: VT=3×5=15, NÃO 4×5 (got {m['custo_vt']})")
        self._assert(get_modo_remuneracao(diarista) == 'diaria',
                     "v1+override: helper retorna 'diaria' apesar do tenant v1")

    # ── Cenário 2: DIARIA em tenant v2 + override + componentes ─────────
    def cenario_diarista_v2_completo(self):
        adm = self._criar_admin('v2')
        diarista = self._criar_funcionario(
            adm, tipo='diaria', valor_diaria=180.00, valor_va=20.00, valor_vt=12.00,
            nome_extra='diarista'
        )
        # Override invertido: salarista em tenant v2
        salarista = self._criar_funcionario(
            adm, tipo='salario', salario=3000.00, valor_va=10.00, valor_vt=5.00,
            nome_extra='salarista_override'
        )
        obra = self._criar_obra(adm)
        di = date.today().replace(day=1)
        df = date.today()
        dias = [di + timedelta(days=i) for i in range(6)]
        # Diarista: 5 dias normais + 1 falta
        self._registrar_dias_trabalhados(diarista, obra, dias[:5])
        db.session.add(RegistroPonto(
            funcionario_id=diarista.id, obra_id=obra.id, admin_id=adm.id,
            data=dias[5], horas_trabalhadas=0, horas_extras=0,
            tipo_registro='falta',
        ))
        # Salarista override: 4 dias trabalhados
        self._registrar_dias_trabalhados(salarista, obra, dias[:4])

        # Alimentação real V1 (RegistroAlimentacao) para diarista
        rest = Restaurante(
            nome=f'Restaurante T {_suffix()[-6:]}',
            admin_id=adm.id,
        )
        db.session.add(rest)
        db.session.flush()
        for d in dias[:3]:
            db.session.add(RegistroAlimentacao(
                funcionario_id=diarista.id, obra_id=obra.id, admin_id=adm.id,
                restaurante_id=rest.id, data=d, tipo='almoco', valor=25.00,
            ))

        # Alimentação real V2 (AlimentacaoLancamento + item) para diarista
        from sqlalchemy import text as _sql_text
        lanc = AlimentacaoLancamento(
            data=dias[3], obra_id=obra.id, admin_id=adm.id,
            restaurante_id=rest.id, valor_total=60.00,
        )
        db.session.add(lanc)
        db.session.flush()
        db.session.execute(
            _sql_text(
                'INSERT INTO alimentacao_funcionarios_assoc '
                '(lancamento_id, funcionario_id, admin_id) '
                'VALUES (:lid, :fid, :aid) ON CONFLICT DO NOTHING'
            ),
            {'lid': lanc.id, 'fid': diarista.id, 'aid': adm.id},
        )
        db.session.add(AlimentacaoLancamentoItem(
            lancamento_id=lanc.id, funcionario_id=diarista.id, admin_id=adm.id,
            nome_item='Almoço', preco_unitario=60.00, quantidade=1, subtotal=60.00,
        ))

        # Reembolso aprovado para diarista
        db.session.add(ReembolsoFuncionario(
            funcionario_id=diarista.id, admin_id=adm.id,
            data_despesa=dias[2], descricao='Combustível', categoria='COMBUSTIVEL',
            valor=Decimal('45.00'),
        ))

        # Almoxarifado em posse — item consumível
        cat = AlmoxarifadoCategoria(
            admin_id=adm.id, nome=f'PPE {_suffix()[-6:]}',
            tipo_controle_padrao='CONSUMIVEL',
        )
        db.session.add(cat)
        db.session.flush()
        item_cons = AlmoxarifadoItem(
            admin_id=adm.id, codigo=f'CN{_suffix()[-6:]}', nome='Bota PPE',
            categoria_id=cat.id, tipo_controle='CONSUMIVEL', unidade='UN',
        )
        db.session.add(item_cons)
        db.session.flush()
        db.session.add(AlmoxarifadoMovimento(
            admin_id=adm.id, usuario_id=adm.id, item_id=item_cons.id,
            funcionario_id=diarista.id, tipo_movimento='SAIDA',
            quantidade=Decimal('2'), valor_unitario=Decimal('80.00'),
            data_movimento=datetime.utcnow(),
        ))

        db.session.commit()

        # Verificações DIARISTA
        md = calcular_metricas_funcionario(diarista, di, df, adm.id)
        self._assert(md['modo_remuneracao'] == 'diaria',
                     f"v2 diarista: modo='diaria' (got {md['modo_remuneracao']})")
        self._assert(md['dias_pagos'] == 5,
                     f"v2 diarista: 5 dias pagos (got {md['dias_pagos']})")
        self._assert(md['faltas'] == 1,
                     f"v2 diarista: 1 falta (got {md['faltas']})")
        self._assert(self._almost(md['custo_mao_obra'], 5 * 180.0),
                     f"v2 diarista: MO=5×180=900 (got {md['custo_mao_obra']})")
        self._assert(self._almost(md['custo_va'], 5 * 20.0),
                     f"v2 diarista: VA=5×20=100 (got {md['custo_va']})")
        self._assert(self._almost(md['custo_vt'], 5 * 12.0),
                     f"v2 diarista: VT=5×12=60 (got {md['custo_vt']})")
        # alim real = 3×25 (V1) + 60 (V2 item) = 135
        self._assert(self._almost(md['custo_alimentacao_real'], 135.0),
                     f"v2 diarista: alim real=135 (got {md['custo_alimentacao_real']})")
        self._assert(self._almost(md['custo_reembolsos'], 45.0),
                     f"v2 diarista: reemb=45 (got {md['custo_reembolsos']})")
        self._assert(self._almost(md['custo_almoxarifado_posse'], 160.0),
                     f"v2 diarista: almox=2×80=160 (got {md['custo_almoxarifado_posse']})")
        esperado = 900 + 100 + 60 + 135 + 45 + 160  # = 1400
        self._assert(self._almost(md['custo_total'], esperado),
                     f"v2 diarista: custo_total={esperado} (got {md['custo_total']})")

        # Verificações SALARISTA (override em tenant v2)
        ms = calcular_metricas_funcionario(salarista, di, df, adm.id)
        self._assert(ms['modo_remuneracao'] == 'salario',
                     f"v2 salarista override: modo='salario' (got {ms['modo_remuneracao']})")
        self._assert(ms['horas_trabalhadas'] == 32.0,
                     f"v2 salarista override: 32h (got {ms['horas_trabalhadas']})")
        self._assert(ms['custo_mao_obra'] > 0,
                     f"v2 salarista override: MO calculada (got {ms['custo_mao_obra']})")

        # get_modo_remuneracao helper
        self._assert(get_modo_remuneracao(diarista) == 'diaria',
                     "helper get_modo_remuneracao(diarista) == 'diaria'")
        self._assert(get_modo_remuneracao(salarista) == 'salario',
                     "helper get_modo_remuneracao(salarista) == 'salario'")

        # calcular_valor_hora: salarista > 0, diarista 0
        self._assert(calcular_valor_hora(salarista, di) > 0,
                     "valor_hora salarista > 0")
        self._assert(calcular_valor_hora(diarista) == 0.0,
                     "valor_hora diarista (do serviço) = 0 — usar valor_diaria/8")

        # Agregação geral
        lista = calcular_metricas_lista([diarista, salarista], di, df, adm.id)
        agg = agregar_kpis_geral(lista, 2)
        self._assert(agg['total_funcionarios'] == 2,
                     f"agg: 2 funcionários (got {agg['total_funcionarios']})")
        self._assert(agg['total_custo_geral'] >= md['custo_total'] + ms['custo_total'] - 0.01,
                     f"agg: total_custo soma todos (got {agg['total_custo_geral']})")

    # ── Teardown ─────────────────────────────────────────────────────────
    def teardown(self):
        from sqlalchemy import text as _t
        for aid in self.created_admin_ids:
            try:
                AlmoxarifadoMovimento.query.filter_by(admin_id=aid).delete()
                AlmoxarifadoEstoque.query.filter_by(admin_id=aid).delete()
                AlmoxarifadoItem.query.filter_by(admin_id=aid).delete()
                AlmoxarifadoCategoria.query.filter_by(admin_id=aid).delete()
                ReembolsoFuncionario.query.filter_by(admin_id=aid).delete()
                # Limpa itens, M2M e lançamentos de alimentação V2
                lancs = AlimentacaoLancamento.query.filter_by(admin_id=aid).all()
                for l in lancs:
                    AlimentacaoLancamentoItem.query.filter_by(lancamento_id=l.id).delete()
                    db.session.execute(
                        _t('DELETE FROM alimentacao_funcionarios_assoc WHERE lancamento_id=:lid'),
                        {'lid': l.id},
                    )
                    db.session.delete(l)
                # Funcionários e seus dependentes
                func_ids = [f.id for f in Funcionario.query.filter_by(admin_id=aid).all()]
                if func_ids:
                    RegistroAlimentacao.query.filter(
                        RegistroAlimentacao.funcionario_id.in_(func_ids)
                    ).delete(synchronize_session=False)
                    RegistroPonto.query.filter(
                        RegistroPonto.funcionario_id.in_(func_ids)
                    ).delete(synchronize_session=False)
                Restaurante.query.filter_by(admin_id=aid).delete()
                Funcionario.query.filter_by(admin_id=aid).delete()
                Obra.query.filter_by(admin_id=aid).delete()
                Usuario.query.filter_by(id=aid).delete()
                db.session.commit()
            except Exception as e:
                logger.warning(f"Teardown admin {aid}: {e}")
                db.session.rollback()

    # ── Runner ───────────────────────────────────────────────────────────
    def run(self):
        with app.app_context():
            try:
                self.cenario_salarista_v1()
                self.cenario_diarista_override_em_v1()
                self.cenario_diarista_v2_completo()
            finally:
                self.teardown()

        print('=' * 72)
        print('MÉTRICAS FUNCIONÁRIO v1+v2 — RESULTADOS')
        print('=' * 72)
        print(f'PASS: {len(self.passed)}')
        print(f'FAIL: {len(self.failed)}')
        for ok in self.passed:
            print(f'  ✔ {ok}')
        for bad in self.failed:
            print(f'  ✖ {bad}')
        print('=' * 72)
        return 0 if not self.failed else 1


if __name__ == '__main__':
    sys.exit(MetricasTestRunner().run())
