"""
Task #154 — RDO V2 deve tratar QUALQUER tarefa que seja "pai" no
cronograma (com filhos) também como subgrupo, inclusive subgrupos
ANINHADOS (grupo → subgrupo → folhas).

Cobre o contrato de `/cronograma/obra/<id>/tarefas-rdo`:
  T1. Endpoint devolve `is_pai=True` para o nó raiz E para o subgrupo
      intermediário aninhado.
  T2. Folhas devolvem `is_pai=False`.
  T3. `percentual_realizado` do subgrupo intermediário = média ponderada
      por duração das filhas (mesma fórmula do cronograma_engine), de
      forma que a barra agregada do RDO bata com a barra do cronograma.
  T4. `percentual_realizado` do grupo raiz propaga o agregado das
      subgrupos intermediárias (cascata bottom-up de N níveis).

Executar com:  python tests/test_rdo_subgrupo_aninhado.py
"""
import os
import sys
import json
import logging
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from werkzeug.security import generate_password_hash

from models import (
    Usuario, TipoUsuario, Obra, Cliente,
    TarefaCronograma, RDO, RDOApontamentoCronograma,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.local', 'rdo_subgrupo_aninhado_report.json',
)


class Runner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.report = {
            'iniciado_em': datetime.utcnow().isoformat() + 'Z',
            'asserts': [],
            'tarefas_endpoint': [],
        }

    def _assert(self, cond, label):
        (self.passed if cond else self.failed).append(label)
        self.report['asserts'].append({'label': label, 'ok': bool(cond)})
        (logger.info if cond else logger.error)(f"{'PASS' if cond else 'FAIL'}: {label}")

    def _suffix(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup(self):
        suf = self._suffix()
        admin = Usuario(
            username=f'sub_aninh_{suf}',
            email=f'sub_aninh_{suf}@test.local',
            nome='Sub Aninh Admin',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(admin); db.session.flush()
        self.admin = admin
        admin_id = admin.id

        cli = Cliente(admin_id=admin_id, nome=f'Cli {suf}',
                      email=f'cli_{suf}@test.local', telefone='11999')
        db.session.add(cli); db.session.flush()

        obra = Obra(
            nome=f'Obra #154 {suf}', codigo=f'O154-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today(), cliente_nome=cli.nome,
        )
        db.session.add(obra); db.session.flush()
        self.obra = obra

        # Cronograma:
        #   LSF (raiz, pai)
        #     └─ Estrutura (subgrupo aninhado, pai)
        #          ├─ Aço Laminado (folha)
        #          └─ Concretagem (folha)
        raiz = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id,
            nome_tarefa='LSF', ordem=1, duracao_dias=10,
            data_inicio=date.today(),
            responsavel='empresa', is_cliente=False,
        )
        db.session.add(raiz); db.session.flush()

        sub = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=raiz.id,
            nome_tarefa='Estrutura', ordem=2, duracao_dias=10,
            data_inicio=date.today(),
            responsavel='empresa', is_cliente=False,
        )
        db.session.add(sub); db.session.flush()

        folha_a = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=sub.id,
            nome_tarefa='Aço Laminado', ordem=3, duracao_dias=4,
            data_inicio=date.today(),
            quantidade_total=100.0, unidade_medida='kg',
            responsavel='empresa', is_cliente=False,
        )
        folha_b = TarefaCronograma(
            admin_id=admin_id, obra_id=obra.id, tarefa_pai_id=sub.id,
            nome_tarefa='Concretagem', ordem=4, duracao_dias=6,
            data_inicio=date.today(),
            quantidade_total=200.0, unidade_medida='m3',
            responsavel='empresa', is_cliente=False,
        )
        db.session.add_all([folha_a, folha_b]); db.session.flush()
        self.raiz, self.sub, self.fa, self.fb = raiz, sub, folha_a, folha_b

        # Apontamento: 50/100 em fa (50%) e 100/200 em fb (50%).
        # (Vamos criar via INSERT direto para não depender de auth)
        rdo = RDO(
            numero_rdo=f'RDO-T154-{suf}',
            obra_id=obra.id, criado_por_id=admin_id, admin_id=admin_id,
            data_relatorio=date.today(), local='Campo',
            clima_geral='Ensolarado',
        )
        db.session.add(rdo); db.session.flush()
        db.session.add_all([
            RDOApontamentoCronograma(
                admin_id=admin_id, rdo_id=rdo.id,
                tarefa_cronograma_id=folha_a.id,
                quantidade_executada_dia=50.0,
            ),
            RDOApontamentoCronograma(
                admin_id=admin_id, rdo_id=rdo.id,
                tarefa_cronograma_id=folha_b.id,
                quantidade_executada_dia=100.0,
            ),
        ])
        db.session.commit()
        self.rdo = rdo

        self.client = self.app.test_client()
        r = self.client.post('/login', data={
            'email': admin.email, 'password': 'Senha@2026'
        }, follow_redirects=False)
        self._assert(r.status_code in (302, 303),
                     f'login admin OK (status={r.status_code})')

    def run(self):
        self.setup()

        r = self.client.get(f'/cronograma/obra/{self.obra.id}/tarefas-rdo')
        self._assert(r.status_code == 200,
                     f'GET tarefas-rdo retorna 200 (status={r.status_code})')
        data = r.get_json()
        tarefas = data.get('tarefas', [])
        self.report['tarefas_endpoint'] = tarefas
        by_id = {t['id']: t for t in tarefas}

        # T1 — raiz e subgrupo aninhado têm is_pai=True
        self._assert(by_id[self.raiz.id].get('is_pai') is True,
                     f"T1 raiz LSF marcada como is_pai (achou {by_id[self.raiz.id].get('is_pai')})")
        self._assert(by_id[self.sub.id].get('is_pai') is True,
                     f"T1 subgrupo aninhado 'Estrutura' marcado como is_pai (achou {by_id[self.sub.id].get('is_pai')})")

        # T2 — folhas têm is_pai=False
        self._assert(by_id[self.fa.id].get('is_pai') is False,
                     f"T2 folha 'Aço Laminado' is_pai=False")
        self._assert(by_id[self.fb.id].get('is_pai') is False,
                     f"T2 folha 'Concretagem' is_pai=False")

        # T3 — % realizado agregado do subgrupo (média ponderada por duração)
        # fa: 50% peso 4 ; fb: 50% peso 6  →  (50*4 + 50*6)/10 = 50%
        sub_pr = by_id[self.sub.id].get('percentual_realizado') or 0
        self._assert(abs(sub_pr - 50.0) < 0.5,
                     f"T3 subgrupo agregado ≈ 50% (média ponderada por duração; achou {sub_pr})")

        # T4 — % realizado da raiz = agregado do subgrupo (cascata)
        # raiz tem 1 filho: 'Estrutura' (peso 10) → 50%
        raiz_pr = by_id[self.raiz.id].get('percentual_realizado') or 0
        self._assert(abs(raiz_pr - 50.0) < 0.5,
                     f"T4 raiz propaga agregado em N níveis ≈ 50% (achou {raiz_pr})")

        # Smoke: rota do RDO renderiza sem 500
        r2 = self.client.get(f'/rdo/novo?obra_id={self.obra.id}')
        self._assert(r2.status_code == 200,
                     f"GET /rdo/novo retorna 200 (status={r2.status_code})")

    def report_save(self):
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, 'w') as f:
            json.dump(self.report, f, default=str, indent=2)
        logger.info(f'Relatório salvo em {REPORT_PATH}')


def main():
    runner = Runner()
    with app.app_context():
        try:
            runner.run()
        finally:
            runner.report_save()
            db.session.rollback()
    logger.info('=' * 70)
    logger.info(f'PASSED: {len(runner.passed)}  FAILED: {len(runner.failed)}')
    for f in runner.failed:
        logger.error(f' ✗ {f}')
    logger.info('=' * 70)
    sys.exit(0 if not runner.failed else 1)


if __name__ == '__main__':
    main()
