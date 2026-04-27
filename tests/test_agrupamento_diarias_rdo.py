"""
Teste end-to-end do agrupamento de custos entre Importação por planilha e RDO.

Cobre as regras restauradas pela Task #60:
  - Diárias importadas via planilha (SALARIO/MAO_OBRA_DIRETA, ALIMENTACAO,
    TRANSPORTE) e diárias lançadas pelo handler de RDO devem cair no MESMO
    GestaoCustoPai (1 cartão por categoria + funcionário, enquanto aberto).
  - Após marcar o pai como PAGO, um novo lançamento abre OUTRO grupo.

Executa com:  python tests/test_agrupamento_diarias_rdo.py
"""
import os
import sys
import logging
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra,
    GestaoCustoPai, GestaoCustoFilho,
)
from werkzeug.security import generate_password_hash
from flask_login import login_user

from utils.financeiro_integration import registrar_custo_automatico
from event_manager import lancar_custos_rdo
from services.importacao_excel import ImportacaoDiarias

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CATEGORIAS_NORMALIZADAS = {
    'SALARIO': 'MAO_OBRA_DIRETA',
    'ALIMENTACAO': 'ALIMENTACAO',
    'TRANSPORTE': 'TRANSPORTE',
}


class AgrupamentoTestRunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.passed = []
        self.failed = []
        self.admin = None
        self.func = None
        self.obra = None

    # ── Asserções ─────────────────────────────────────────────────────────────
    def _assert(self, cond, label):
        if cond:
            self.passed.append(label)
            logger.info(f"PASS: {label}")
        else:
            self.failed.append(label)
            logger.error(f"FAIL: {label}")

    # ── Setup / Teardown ──────────────────────────────────────────────────────
    def _unique_suffix(self):
        from datetime import datetime
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup_fixtures(self):
        suffix = self._unique_suffix()
        admin = Usuario(
            username=f'agrup_admin_{suffix}',
            email=f'agrup_admin_{suffix}@test.local',
            nome='Agrupamento Test Admin',
            password_hash=generate_password_hash('Teste@2025'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()

        func = Funcionario(
            codigo=f'AG{admin.id:04d}',
            nome=f'Funcionario Agrupamento {suffix}',
            cpf=f'AG{admin.id:011d}'[:14],
            data_admissao=date.today(),
            tipo_remuneracao='diaria',
            valor_diaria=150.00,
            valor_va=20.00,
            valor_vt=10.00,
            ativo=True,
            admin_id=admin.id,
        )
        db.session.add(func)

        cliente = Cliente(
            nome=f'Cliente Agrupamento {suffix}',
            email=f'cliente_ag_{suffix}@example.com',
            admin_id=admin.id,
        )
        db.session.add(cliente)
        db.session.flush()

        obra = Obra(
            nome=f'Obra Agrupamento {suffix}',
            codigo=f'OAG{admin.id}',
            data_inicio=date.today(),
            admin_id=admin.id,
            cliente_id=cliente.id,
            ativo=True,
        )
        db.session.add(obra)
        db.session.commit()

        self.admin = admin
        self.func = func
        self.obra = obra

    def teardown_fixtures(self):
        if not self.admin:
            return
        try:
            admin_id = self.admin.id
            # Apaga filhos primeiro, depois pais; ramos de RDO em cascata.
            pai_ids = [p.id for p in GestaoCustoPai.query.filter_by(admin_id=admin_id).all()]
            if pai_ids:
                GestaoCustoFilho.query.filter(GestaoCustoFilho.pai_id.in_(pai_ids)).delete(
                    synchronize_session=False)
                GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pai_ids)).delete(
                    synchronize_session=False)
            from models import CustoObra
            CustoObra.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            RDO.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Funcionario.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Obra.query.filter_by(admin_id=admin_id).delete(synchronize_session=False)
            Usuario.query.filter_by(id=admin_id).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Erro no teardown (ignorado): {e}")

    # ── Helpers de query ──────────────────────────────────────────────────────
    def _pais_abertos(self, categorias_legadas):
        """Retorna pais NÃO PAGO/RECUSADO da entidade (func) para uma categoria
        considerando o mapeamento legado→normalizado."""
        if isinstance(categorias_legadas, str):
            categorias_legadas = [categorias_legadas]
        equivalentes = set()
        legada_map = GestaoCustoPai._CATEGORIA_LEGADA_MAP
        for cat in categorias_legadas:
            normalizada = legada_map.get(cat, cat)
            equivalentes.add(normalizada)
            for legada, nova in legada_map.items():
                if nova == normalizada:
                    equivalentes.add(legada)
        return (GestaoCustoPai.query
                .filter(GestaoCustoPai.admin_id == self.admin.id)
                .filter(GestaoCustoPai.entidade_id == self.func.id)
                .filter(GestaoCustoPai.tipo_categoria.in_(list(equivalentes)))
                .filter(GestaoCustoPai.status.notin_(['PAGO', 'RECUSADO']))
                .all())

    def _todos_pais(self, categorias_legadas):
        if isinstance(categorias_legadas, str):
            categorias_legadas = [categorias_legadas]
        equivalentes = set()
        legada_map = GestaoCustoPai._CATEGORIA_LEGADA_MAP
        for cat in categorias_legadas:
            normalizada = legada_map.get(cat, cat)
            equivalentes.add(normalizada)
            for legada, nova in legada_map.items():
                if nova == normalizada:
                    equivalentes.add(legada)
        return (GestaoCustoPai.query
                .filter(GestaoCustoPai.admin_id == self.admin.id)
                .filter(GestaoCustoPai.entidade_id == self.func.id)
                .filter(GestaoCustoPai.tipo_categoria.in_(list(equivalentes)))
                .all())

    # ── Cenário ───────────────────────────────────────────────────────────────
    def importar_duas_diarias(self):
        """Usa ImportacaoDiarias.importar com rows pré-construídas (sem Excel)."""
        d1 = date.today() - timedelta(days=2)
        d2 = date.today() - timedelta(days=1)
        rows = []
        for i, data_ref in enumerate([d1, d2], start=1):
            rows.append({
                'linha': i,
                'data': data_ref,
                'nome': self.func.nome,
                'funcionario_id': self.func.id,
                'obra_id': self.obra.id,
                'tipo_lancamento': 'diaria_completa',
                'valor_diaria': float(self.func.valor_diaria or 0),
                'valor_va': float(self.func.valor_va or 0),
                'valor_vt': float(self.func.valor_vt or 0),
            })
        resultado = ImportacaoDiarias().importar(rows, self.admin.id)
        return resultado

    def finalizar_rdo(self):
        rdo = RDO(
            numero_rdo=f'RDO-AG-{self.admin.id}',
            data_relatorio=date.today(),
            obra_id=self.obra.id,
            admin_id=self.admin.id,
            criado_por_id=self.admin.id,
            status='Finalizado',
        )
        db.session.add(rdo)
        db.session.flush()

        mo = RDOMaoObra(
            admin_id=self.admin.id,
            rdo_id=rdo.id,
            funcionario_id=self.func.id,
            funcao_exercida='Diarista',
            horas_trabalhadas=8.0,
        )
        db.session.add(mo)
        db.session.commit()

        # Chama o handler diretamente — emula 'rdo_finalizado'
        lancar_custos_rdo({'rdo_id': rdo.id}, self.admin.id)
        return rdo

    def run(self):
        with self.app.test_request_context('/'):
            self.setup_fixtures()
            try:
                # autenticação para is_v2_active()
                login_user(self.admin)

                # 1) Importação de 2 diárias completas (cria 3 pais: SAL/ALI/TRA)
                resultado_import = self.importar_duas_diarias()
                self._assert(resultado_import.get('criados') == 2,
                             f"Importação criou 2 diárias (criados={resultado_import.get('criados')}, erros={resultado_import.get('erros')})")

                for cat in ('SALARIO', 'ALIMENTACAO', 'TRANSPORTE'):
                    pais = self._pais_abertos(cat)
                    self._assert(len(pais) == 1,
                                 f"Após importação, 1 único pai aberto para {cat} (achou {len(pais)})")
                    if pais:
                        filhos = GestaoCustoFilho.query.filter_by(pai_id=pais[0].id).count()
                        self._assert(filhos == 2,
                                     f"Pai aberto de {cat} tem 2 filhos da importação (achou {filhos})")

                # 2) Finaliza um RDO com o mesmo funcionário → SALARIO deve agrupar
                rdo = self.finalizar_rdo()

                pais_sal = self._pais_abertos('SALARIO')
                self._assert(len(pais_sal) == 1,
                             f"Após RDO, AINDA 1 único pai aberto para SALARIO (achou {len(pais_sal)})")
                if pais_sal:
                    filhos_sal = GestaoCustoFilho.query.filter_by(pai_id=pais_sal[0].id).count()
                    self._assert(filhos_sal == 3,
                                 f"Pai SALARIO agora tem 3 filhos (2 importação + 1 RDO; achou {filhos_sal})")

                # ALIMENTACAO e TRANSPORTE permanecem com 1 pai e 2 filhos
                for cat in ('ALIMENTACAO', 'TRANSPORTE'):
                    pais = self._pais_abertos(cat)
                    self._assert(len(pais) == 1,
                                 f"RDO não criou novo pai para {cat} (achou {len(pais)})")

                # 3) Marca pais como PAGO — novo lançamento deve abrir OUTRO grupo
                for cat in ('SALARIO', 'ALIMENTACAO', 'TRANSPORTE'):
                    pais_abertos = self._pais_abertos(cat)
                    for p in pais_abertos:
                        p.status = 'PAGO'
                        p.data_pagamento = date.today()
                    db.session.commit()

                    # Novo lançamento da MESMA categoria/funcionário
                    novo_filho = registrar_custo_automatico(
                        admin_id=self.admin.id,
                        tipo_categoria=cat,
                        entidade_nome=self.func.nome,
                        entidade_id=self.func.id,
                        data=date.today(),
                        descricao=f'Pós-PAGO {cat}',
                        valor=50.00,
                        obra_id=self.obra.id,
                        origem_tabela='teste_pos_pago',
                        origem_id=self.func.id,
                    )
                    db.session.commit()

                    self._assert(novo_filho is not None,
                                 f"Novo lançamento pós-PAGO criou filho para {cat}")

                    pais_abertos_apos = self._pais_abertos(cat)
                    todos_pais = self._todos_pais(cat)
                    self._assert(len(pais_abertos_apos) == 1,
                                 f"Após PAGO+novo lançamento, há 1 NOVO pai aberto para {cat} (achou {len(pais_abertos_apos)})")
                    self._assert(len(todos_pais) >= 2,
                                 f"Total de pais (PAGO + novo) ≥ 2 para {cat} (achou {len(todos_pais)})")
                    if pais_abertos_apos and pais_abertos:
                        self._assert(pais_abertos_apos[0].id != pais_abertos[0].id,
                                     f"Novo pai de {cat} é diferente do anterior (PAGO)")

            finally:
                self.teardown_fixtures()

        return self.report()

    def report(self):
        print("\n" + "=" * 80)
        print("AGRUPAMENTO IMPORTAÇÃO + RDO — RESULTADOS")
        print("=" * 80)
        print(f"PASS: {len(self.passed)}")
        print(f"FAIL: {len(self.failed)}")
        for p in self.passed:
            print(f"  ✔ {p}")
        for f in self.failed:
            print(f"  ✘ {f}")
        print("=" * 80)
        return len(self.failed) == 0


def test_agrupamento_diarias_rdo_e2e():
    """Entry point pytest: agrupamento Importação + RDO end-to-end."""
    with app.app_context():
        runner = AgrupamentoTestRunner()
        ok = runner.run()
    assert ok, f"Falhas: {runner.failed}"


if __name__ == '__main__':
    with app.app_context():
        ok = AgrupamentoTestRunner().run()
    sys.exit(0 if ok else 1)
