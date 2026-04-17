"""
Task #78 — Auto-vínculo custo→serviço quando o custo vem do RDO.

Cenários cobertos:
  - RDO finalizado em que o funcionário trabalhou em UM único serviço com
    ``ObraServicoCusto`` correspondente (via ``ServicoObraReal``):
    o ``GestaoCustoFilho`` gerado deve ter ``obra_servico_custo_id`` preenchido.
  - RDO em que o funcionário trabalhou em DOIS serviços distintos: o
    ``obra_servico_custo_id`` permanece ``None`` (sem chute) e o custo segue
    para o rateio normal de ``recalcular_obra``.

Executa com:  python tests/test_auto_link_servico_rdo.py
"""
import os
import sys
import logging
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Servico,
    RDO, RDOMaoObra, RDOServicoSubatividade,
    ServicoObraReal, ObraServicoCusto,
    GestaoCustoPai, GestaoCustoFilho,
)
from werkzeug.security import generate_password_hash
from flask_login import login_user

from event_manager import lancar_custos_rdo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoLinkRunner:
    def __init__(self):
        self.app = app
        self.passed = []
        self.failed = []

    def _assert(self, cond, label):
        if cond:
            self.passed.append(label)
            logger.info(f"PASS: {label}")
        else:
            self.failed.append(label)
            logger.error(f"FAIL: {label}")

    def _suffix(self):
        from datetime import datetime
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup(self):
        s = self._suffix()
        admin = Usuario(
            username=f'auto_link_{s}',
            email=f'auto_link_{s}@test.local',
            nome='Auto Link Admin',
            password_hash=generate_password_hash('Teste@2025'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()
        self.admin = admin

        self.func = Funcionario(
            codigo=f'AL{admin.id:04d}',
            nome=f'Func Auto Link {s}',
            cpf=f'AL{admin.id:011d}'[:14],
            data_admissao=date.today(),
            tipo_remuneracao='diaria',
            valor_diaria=200.00,
            ativo=True,
            admin_id=admin.id,
        )
        self.func2 = Funcionario(
            codigo=f'AL{admin.id:04d}B',
            nome=f'Func Auto Link 2 {s}',
            cpf=f'BL{admin.id:011d}'[:14],
            data_admissao=date.today(),
            tipo_remuneracao='diaria',
            valor_diaria=180.00,
            ativo=True,
            admin_id=admin.id,
        )
        db.session.add_all([self.func, self.func2])

        self.obra = Obra(
            nome=f'Obra Auto Link {s}',
            codigo=f'OAL{admin.id}',
            data_inicio=date.today(),
            admin_id=admin.id,
            ativo=True,
        )
        db.session.add(self.obra)
        db.session.flush()

        self.serv_a = Servico(
            nome=f'Alvenaria {s}', categoria='estrutura',
            unidade_medida='m2', unidade_simbolo='m²',
            ativo=True, admin_id=admin.id,
        )
        self.serv_b = Servico(
            nome=f'Pintura {s}', categoria='acabamento',
            unidade_medida='m2', unidade_simbolo='m²',
            ativo=True, admin_id=admin.id,
        )
        db.session.add_all([self.serv_a, self.serv_b])
        db.session.flush()

        self.sor_a = ServicoObraReal(
            obra_id=self.obra.id, servico_id=self.serv_a.id,
            quantidade_planejada=Decimal('100'),
            admin_id=admin.id,
        )
        self.sor_b = ServicoObraReal(
            obra_id=self.obra.id, servico_id=self.serv_b.id,
            quantidade_planejada=Decimal('50'),
            admin_id=admin.id,
        )
        db.session.add_all([self.sor_a, self.sor_b])
        db.session.flush()

        self.osc_a = ObraServicoCusto(
            admin_id=admin.id, obra_id=self.obra.id,
            servico_obra_real_id=self.sor_a.id,
            nome='Custo Alvenaria',
            valor_orcado=Decimal('5000'),
        )
        self.osc_b = ObraServicoCusto(
            admin_id=admin.id, obra_id=self.obra.id,
            servico_obra_real_id=self.sor_b.id,
            nome='Custo Pintura',
            valor_orcado=Decimal('3000'),
        )
        db.session.add_all([self.osc_a, self.osc_b])
        db.session.commit()

    def teardown(self):
        try:
            admin_id = self.admin.id
            pai_ids = [p.id for p in GestaoCustoPai.query.filter_by(admin_id=admin_id).all()]
            if pai_ids:
                GestaoCustoFilho.query.filter(GestaoCustoFilho.pai_id.in_(pai_ids)).delete(
                    synchronize_session=False)
                GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pai_ids)).delete(
                    synchronize_session=False)
            from models import CustoObra
            CustoObra.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            ObraServicoCusto.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            ServicoObraReal.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            RDO.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Servico.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Funcionario.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Obra.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Usuario.query.filter_by(id=admin_id).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Erro no teardown (ignorado): {e}")

    def _criar_rdo(self, numero, mo_specs):
        """mo_specs: lista de (funcionario, [servico, ...])"""
        rdo = RDO(
            numero_rdo=numero,
            data_relatorio=date.today(),
            obra_id=self.obra.id,
            admin_id=self.admin.id,
            criado_por_id=self.admin.id,
            status='Finalizado',
        )
        db.session.add(rdo)
        db.session.flush()

        for funcionario, servicos in mo_specs:
            for servico in servicos:
                sub = RDOServicoSubatividade(
                    rdo_id=rdo.id,
                    servico_id=servico.id,
                    nome_subatividade=f'Sub {servico.nome}',
                    percentual_conclusao=10.0,
                    admin_id=self.admin.id,
                )
                db.session.add(sub)
                db.session.flush()
                mo = RDOMaoObra(
                    admin_id=self.admin.id,
                    rdo_id=rdo.id,
                    funcionario_id=funcionario.id,
                    funcao_exercida='Diarista',
                    horas_trabalhadas=8.0,
                    subatividade_id=sub.id,
                )
                db.session.add(mo)
        db.session.commit()
        return rdo

    def run(self):
        with self.app.test_request_context('/'):
            self.setup()
            try:
                login_user(self.admin)

                # Cenário A: func trabalhou em UM único serviço (Alvenaria)
                rdo_a = self._criar_rdo(
                    f'RDO-A-{self.admin.id}',
                    [(self.func, [self.serv_a])],
                )
                lancar_custos_rdo({'rdo_id': rdo_a.id}, self.admin.id)

                filho = (
                    GestaoCustoFilho.query
                    .filter_by(
                        origem_tabela='rdo_mao_obra',
                        origem_id=rdo_a.id,
                        admin_id=self.admin.id,
                    )
                    .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
                    .filter(GestaoCustoPai.entidade_id == self.func.id)
                    .first()
                )
                self._assert(filho is not None,
                             "Cenário A: filho criado para a diária do RDO")
                if filho:
                    self._assert(filho.obra_servico_custo_id == self.osc_a.id,
                                 f"Cenário A: filho vinculado ao ObraServicoCusto da Alvenaria "
                                 f"(esperado={self.osc_a.id}, achou={filho.obra_servico_custo_id})")

                # Cenário B: func2 trabalhou em DOIS serviços diferentes
                rdo_b = self._criar_rdo(
                    f'RDO-B-{self.admin.id}',
                    [(self.func2, [self.serv_a, self.serv_b])],
                )
                lancar_custos_rdo({'rdo_id': rdo_b.id}, self.admin.id)

                filho_b = (
                    GestaoCustoFilho.query
                    .filter_by(
                        origem_tabela='rdo_mao_obra',
                        origem_id=rdo_b.id,
                        admin_id=self.admin.id,
                    )
                    .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
                    .filter(GestaoCustoPai.entidade_id == self.func2.id)
                    .first()
                )
                self._assert(filho_b is not None,
                             "Cenário B: filho criado para a diária do RDO multi-serviço")
                if filho_b:
                    self._assert(filho_b.obra_servico_custo_id is None,
                                 f"Cenário B: filho NÃO vinculado a serviço (multi-serviço sem chute) "
                                 f"(achou={filho_b.obra_servico_custo_id})")

            finally:
                self.teardown()
        return self.report()

    def report(self):
        print("\n" + "=" * 80)
        print("AUTO-VÍNCULO RDO → SERVIÇO — RESULTADOS")
        print("=" * 80)
        print(f"PASS: {len(self.passed)}")
        print(f"FAIL: {len(self.failed)}")
        for p in self.passed:
            print(f"  ✔ {p}")
        for f in self.failed:
            print(f"  ✘ {f}")
        print("=" * 80)
        return len(self.failed) == 0


def test_auto_link_servico_rdo_e2e():
    with app.app_context():
        runner = AutoLinkRunner()
        ok = runner.run()
    assert ok, f"Falhas: {runner.failed}"


if __name__ == '__main__':
    with app.app_context():
        ok = AutoLinkRunner().run()
    sys.exit(0 if ok else 1)
