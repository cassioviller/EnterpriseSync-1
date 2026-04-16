"""Testes de integração para os 2 tipos de PedidoCompra (Task #65).

Cobre as 4 cenarios comportamentais exigidos:
  1. Compra NORMAL sem obra
        → ENTRADA no almoxarifado, NENHUMA SAÍDA, GCP MATERIAL com obra=None.
  2. Compra NORMAL com obra
        → ENTRADA + SAÍDA imediata contra a obra + GCP MATERIAL.
  3. Compra APROVACAO_CLIENTE antes da aprovação
        → status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE',
          processada_apos_aprovacao=False, NENHUM GCP, NENHUM AlmoxarifadoMovimento.
  4. Compra APROVACAO_CLIENTE depois da aprovação (+ idempotência)
        → cria GCP FATURAMENTO_DIRETO status=PAGO, ENTRADA + SAÍDA, marca
          processada_apos_aprovacao=True. NUNCA cria FluxoCaixa.
        → segunda chamada de processar_compra_aprovada_cliente é no-op.

Executa com:  python tests/test_compras_tipo.py
"""
import os
import sys
import logging
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Usuario, TipoUsuario, Obra, Fornecedor,
    PedidoCompra, PedidoCompraItem,
    AlmoxarifadoItem, AlmoxarifadoCategoria,
    AlmoxarifadoMovimento, AlmoxarifadoEstoque,
    GestaoCustoPai, GestaoCustoFilho, FluxoCaixa,
)
from compras_views import (
    processar_compra_normal,
    processar_compra_aprovada_cliente,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ComprasTipoTestRunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.passed = []
        self.failed = []
        self.admin = None
        self.obra = None
        self.fornecedor = None
        self.item_almox = None

    def _assert(self, cond, label):
        if cond:
            self.passed.append(label)
            print(f"  PASS: {label}")
        else:
            self.failed.append(label)
            print(f"  FAIL: {label}")

    def _suffix(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup_fixtures(self):
        sfx = self._suffix()
        admin = Usuario(
            username=f'compras_admin_{sfx}',
            email=f'compras_admin_{sfx}@test.local',
            nome='Compras Tipo Test Admin',
            password_hash=generate_password_hash('Teste@2025'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()

        obra = Obra(
            nome=f'Obra Compras {sfx}',
            codigo=f'OCO{admin.id}',
            data_inicio=date.today(),
            admin_id=admin.id,
            ativo=True,
        )
        forn = Fornecedor(
            nome=f'Fornecedor Compras {sfx}',
            cnpj=f'CT{admin.id:012d}'[:18],
            admin_id=admin.id,
            ativo=True,
        )
        cat = AlmoxarifadoCategoria(
            nome=f'Materiais Compra {sfx}',
            tipo_controle_padrao='CONSUMIVEL',
            permite_devolucao_padrao=False,
            admin_id=admin.id,
        )
        db.session.add_all([obra, forn, cat])
        db.session.flush()
        item = AlmoxarifadoItem(
            codigo=f'IT{admin.id}{sfx[-4:]}',
            nome='Cimento CP-II 50kg',
            unidade='SC',
            categoria_id=cat.id,
            tipo_controle='CONSUMIVEL',
            admin_id=admin.id,
        )
        db.session.add(item)
        db.session.commit()
        self.admin, self.obra, self.fornecedor, self.item_almox = admin, obra, forn, item
        self.cat = cat

    def teardown_fixtures(self):
        if not self.admin:
            return
        try:
            aid = self.admin.id
            # Limpa TUDO que foi gerado
            AlmoxarifadoMovimento.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            AlmoxarifadoEstoque.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            FluxoCaixa.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            pai_ids = [p.id for p in GestaoCustoPai.query.filter_by(admin_id=aid).all()]
            if pai_ids:
                GestaoCustoFilho.query.filter(GestaoCustoFilho.pai_id.in_(pai_ids)).delete(
                    synchronize_session=False)
                GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pai_ids)).delete(
                    synchronize_session=False)
            ped_ids = [p.id for p in PedidoCompra.query.filter_by(admin_id=aid).all()]
            if ped_ids:
                PedidoCompraItem.query.filter(PedidoCompraItem.pedido_id.in_(ped_ids)).delete(
                    synchronize_session=False)
                PedidoCompra.query.filter(PedidoCompra.id.in_(ped_ids)).delete(
                    synchronize_session=False)
            AlmoxarifadoItem.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            AlmoxarifadoCategoria.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Fornecedor.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Obra.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Usuario.query.filter_by(id=aid).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"teardown error: {e}")

    # ── helpers ──────────────────────────────────────────────────────────────
    def _criar_pedido(self, tipo_compra, com_obra=True, numero_sufixo=''):
        ped = PedidoCompra(
            numero=f'TST-{tipo_compra}-{numero_sufixo}-{self.admin.id}',
            fornecedor_id=self.fornecedor.id,
            data_compra=date.today(),
            obra_id=self.obra.id if com_obra else None,
            condicao_pagamento='a_vista',
            parcelas=1,
            valor_total=Decimal('500.00'),
            tipo_compra=tipo_compra,
            processada_apos_aprovacao=False,
            status_aprovacao_cliente=(
                'AGUARDANDO_APROVACAO_CLIENTE' if tipo_compra == 'aprovacao_cliente' else None
            ),
            admin_id=self.admin.id,
        )
        db.session.add(ped)
        db.session.flush()
        item = PedidoCompraItem(
            pedido_id=ped.id,
            almoxarifado_item_id=self.item_almox.id,
            descricao='Cimento CP-II 50kg',
            quantidade=Decimal('10'),
            preco_unitario=Decimal('50.00'),
            subtotal=Decimal('500.00'),
            admin_id=self.admin.id,
        )
        db.session.add(item)
        db.session.flush()
        return ped, [(item.descricao, 10.0, 50.0, item.almoxarifado_item_id, 500.0)]

    # ── cenários ─────────────────────────────────────────────────────────────
    def cenario_1_normal_sem_obra(self):
        print("\n[CENÁRIO 1] Compra NORMAL sem obra → entrada-only")
        ped, itens = self._criar_pedido('normal', com_obra=False, numero_sufixo='c1')
        processar_compra_normal(ped, itens, self.admin.id, self.admin.id)
        db.session.commit()

        movs = AlmoxarifadoMovimento.query.filter_by(pedido_compra_id=ped.id).all()
        entradas = [m for m in movs if m.tipo_movimento == 'ENTRADA']
        saidas   = [m for m in movs if m.tipo_movimento == 'SAIDA']
        gcps = GestaoCustoPai.query.join(GestaoCustoFilho).filter(
            GestaoCustoFilho.origem_tabela == 'pedido_compra',
            GestaoCustoFilho.origem_id == ped.id,
        ).all()
        self._assert(len(entradas) == 1, 'C1: 1 ENTRADA criada')
        self._assert(len(saidas) == 0, 'C1: NENHUMA SAÍDA (sem obra)')
        self._assert(len(gcps) == 1 and gcps[0].tipo_categoria == 'MATERIAL',
                     'C1: GCP MATERIAL criado')
        self._assert(gcps[0].entidade_id is None, 'C1: GCP sem obra (entidade_id=None)')

    def cenario_2_normal_com_obra(self):
        print("\n[CENÁRIO 2] Compra NORMAL com obra → entrada + saida imediata")
        ped, itens = self._criar_pedido('normal', com_obra=True, numero_sufixo='c2')
        processar_compra_normal(ped, itens, self.admin.id, self.admin.id)
        db.session.commit()

        movs = AlmoxarifadoMovimento.query.filter_by(pedido_compra_id=ped.id).all()
        entradas = [m for m in movs if m.tipo_movimento == 'ENTRADA']
        saidas   = [m for m in movs if m.tipo_movimento == 'SAIDA']
        gcps = GestaoCustoPai.query.join(GestaoCustoFilho).filter(
            GestaoCustoFilho.origem_tabela == 'pedido_compra',
            GestaoCustoFilho.origem_id == ped.id,
        ).all()
        estqs = AlmoxarifadoEstoque.query.join(
            AlmoxarifadoMovimento, AlmoxarifadoMovimento.estoque_id == AlmoxarifadoEstoque.id
        ).filter(AlmoxarifadoMovimento.pedido_compra_id == ped.id,
                 AlmoxarifadoMovimento.tipo_movimento == 'ENTRADA').all()

        self._assert(len(entradas) == 1, 'C2: 1 ENTRADA criada')
        self._assert(len(saidas) == 1, 'C2: 1 SAÍDA imediata na obra')
        self._assert(saidas and saidas[0].obra_id == self.obra.id,
                     'C2: SAÍDA é contra a obra correta')
        self._assert(estqs and estqs[0].status == 'CONSUMIDO',
                     'C2: lote marcado CONSUMIDO')
        self._assert(estqs and estqs[0].quantidade_disponivel == 0,
                     'C2: quantidade_disponivel=0 após saida')
        self._assert(len(gcps) == 1 and gcps[0].tipo_categoria == 'MATERIAL',
                     'C2: GCP MATERIAL criado')
        self._assert(gcps[0].entidade_id == self.obra.id,
                     'C2: GCP vinculado à obra')

    def cenario_3_aprovacao_cliente_pendente(self):
        print("\n[CENÁRIO 3] Compra APROVACAO_CLIENTE antes da aprovação → nada deve acontecer")
        ped, _ = self._criar_pedido('aprovacao_cliente', com_obra=True, numero_sufixo='c3')
        db.session.commit()

        movs = AlmoxarifadoMovimento.query.filter_by(pedido_compra_id=ped.id).all()
        gcps = GestaoCustoPai.query.join(GestaoCustoFilho).filter(
            GestaoCustoFilho.origem_tabela == 'pedido_compra',
            GestaoCustoFilho.origem_id == ped.id,
        ).all()
        self._assert(ped.status_aprovacao_cliente == 'AGUARDANDO_APROVACAO_CLIENTE',
                     'C3: status_aprovacao_cliente = AGUARDANDO_APROVACAO_CLIENTE')
        self._assert(ped.processada_apos_aprovacao is False,
                     'C3: processada_apos_aprovacao=False')
        self._assert(len(movs) == 0, 'C3: NENHUM movimento de almoxarifado')
        self._assert(len(gcps) == 0, 'C3: NENHUM GestaoCustoPai criado')

    def cenario_4_aprovacao_cliente_aprovada_e_idempotencia(self):
        print("\n[CENÁRIO 4] Compra APROVACAO_CLIENTE aprovada → faturamento_direto + idempotência")
        ped, _ = self._criar_pedido('aprovacao_cliente', com_obra=True, numero_sufixo='c4')
        db.session.commit()

        # Snapshot: contar FluxoCaixa do tenant ANTES de aprovar
        fc_antes = FluxoCaixa.query.filter_by(admin_id=self.admin.id).count()

        # Cliente aprova → roda helper
        ped.status_aprovacao_cliente = 'APROVADO'
        processar_compra_aprovada_cliente(ped, usuario_id=self.admin.id)
        db.session.commit()

        # Asserts pós-aprovação
        movs = AlmoxarifadoMovimento.query.filter_by(pedido_compra_id=ped.id).all()
        entradas = [m for m in movs if m.tipo_movimento == 'ENTRADA']
        saidas   = [m for m in movs if m.tipo_movimento == 'SAIDA']
        gcps = GestaoCustoPai.query.join(GestaoCustoFilho).filter(
            GestaoCustoFilho.origem_tabela == 'pedido_compra',
            GestaoCustoFilho.origem_id == ped.id,
        ).all()
        fc_depois = FluxoCaixa.query.filter_by(admin_id=self.admin.id).count()

        self._assert(len(entradas) == 1, 'C4: 1 ENTRADA criada após aprovação')
        self._assert(len(saidas) == 1, 'C4: 1 SAÍDA criada após aprovação')
        self._assert(len(gcps) == 1, 'C4: 1 GCP criado após aprovação')
        self._assert(gcps and gcps[0].tipo_categoria == 'FATURAMENTO_DIRETO',
                     'C4: GCP é tipo_categoria=FATURAMENTO_DIRETO')
        self._assert(gcps and gcps[0].status == 'PAGO',
                     'C4: GCP status=PAGO')
        self._assert(gcps and float(gcps[0].saldo) == 0.0,
                     'C4: GCP saldo=0')
        self._assert(fc_depois == fc_antes,
                     f'C4: NENHUM FluxoCaixa criado (antes={fc_antes}, depois={fc_depois})')
        self._assert(ped.processada_apos_aprovacao is True,
                     'C4: processada_apos_aprovacao=True')

        # Segunda chamada deve ser no-op (idempotência)
        gcps_antes = GestaoCustoPai.query.count()
        movs_antes = AlmoxarifadoMovimento.query.filter_by(pedido_compra_id=ped.id).count()
        processar_compra_aprovada_cliente(ped, usuario_id=self.admin.id)
        db.session.commit()
        gcps_depois = GestaoCustoPai.query.count()
        movs_depois = AlmoxarifadoMovimento.query.filter_by(pedido_compra_id=ped.id).count()
        self._assert(gcps_antes == gcps_depois,
                     'C4: 2ª chamada idempotente — nenhum GCP novo')
        self._assert(movs_antes == movs_depois,
                     'C4: 2ª chamada idempotente — nenhum movimento novo')

    # ── runner ────────────────────────────────────────────────────────────────
    def run(self):
        with self.app.app_context():
            try:
                # smoke checks primeiro
                cols = [c.name for c in PedidoCompra.__table__.columns]
                self._assert('tipo_compra' in cols, 'modelo possui coluna tipo_compra')
                self._assert('processada_apos_aprovacao' in cols,
                             'modelo possui coluna processada_apos_aprovacao')
                rules = {r.endpoint for r in app.url_map.iter_rules()}
                self._assert('compras.aprovacao' in rules, 'rota compras.aprovacao registrada')

                self.setup_fixtures()
                self.cenario_1_normal_sem_obra()
                self.cenario_2_normal_com_obra()
                self.cenario_3_aprovacao_cliente_pendente()
                self.cenario_4_aprovacao_cliente_aprovada_e_idempotencia()
            finally:
                self.teardown_fixtures()

        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*70}\n RESULTADO: {len(self.passed)}/{total} passaram, "
              f"{len(self.failed)} falharam.\n{'='*70}")
        if self.failed:
            print("FALHAS:")
            for f in self.failed:
                print(f"  - {f}")
            sys.exit(1)
        print("✅ TODOS OS TESTES PASSARAM")


if __name__ == '__main__':
    ComprasTipoTestRunner().run()
