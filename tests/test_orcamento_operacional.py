"""
tests/test_orcamento_operacional.py — Task #63

Valida o Orçamento Operacional da Obra (cópia editável separada com
versionamento temporal por item):

  • clonar_do_orcamento (idempotente, copia composicao_snapshot/margem/imposto)
  • obter_operacional_vigente em diferentes data_referencia (janela temporal)
  • editar_item modo='a_partir_de_hoje' (fecha vigente + abre nova)
  • editar_item modo='retroativo' (atualiza in-place + auditoria)
  • diff_com_original e atualizar_do_original
  • Auto-clone via SQLAlchemy after_insert listener no RDO
"""
import os
import sys
import logging
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Cliente, Obra, RDO,
    Orcamento, OrcamentoItem, Proposta,
    ObraOrcamentoOperacional, ObraOrcamentoOperacionalItem,
    ObraOrcamentoOperacionalItemVersao,
)
from werkzeug.security import generate_password_hash
from services.orcamento_operacional import (
    garantir_operacional, obter_operacional_vigente, editar_item,
    diff_com_original, atualizar_do_original, listar_versoes,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
log = logging.getLogger('test_op_63')


class Runner:
    def __init__(self):
        self.passed: list = []
        self.failed: list = []

    def check(self, cond, label):
        (self.passed if cond else self.failed).append(label)
        (log.info if cond else log.error)(f"{'PASS' if cond else 'FAIL'}  {label}")

    def _suf(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup(self):
        s = self._suf()
        admin = Usuario(
            username=f'op63_{s}', email=f'op63_{s}@t.local',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, nome='Admin 63', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(admin_id=admin.id, nome=f'Cli 63 {s}',
                      email=f'cli63_{s}@t.local')
        db.session.add(cli); db.session.flush()

        # Orçamento original com 2 itens + composicao_snapshot
        orc = Orcamento(
            admin_id=admin.id, numero=f'ORC-63-{s[-6:]}',
            titulo='Orc Teste 63', cliente_id=cli.id,
            status='fechado',
        )
        db.session.add(orc); db.session.flush()
        i1 = OrcamentoItem(
            admin_id=admin.id, orcamento_id=orc.id, ordem=1,
            descricao='Alvenaria m²', unidade='m2', quantidade=100,
            margem_pct=20, imposto_pct=10,
            composicao_snapshot=[
                {'tipo': 'MATERIAL', 'insumo_id': None, 'nome': 'Cimento',
                 'unidade': 'kg', 'coeficiente': 5.0, 'preco_unitario': 1.5,
                 'subtotal_unitario': 7.5},
                {'tipo': 'MAO_OBRA', 'insumo_id': None, 'nome': 'Pedreiro',
                 'unidade': 'h', 'coeficiente': 0.5, 'preco_unitario': 30.0,
                 'subtotal_unitario': 15.0},
            ],
        )
        i2 = OrcamentoItem(
            admin_id=admin.id, orcamento_id=orc.id, ordem=2,
            descricao='Pintura m²', unidade='m2', quantidade=80,
            margem_pct=25, imposto_pct=10,
            composicao_snapshot=[
                {'tipo': 'MATERIAL', 'insumo_id': None, 'nome': 'Tinta',
                 'unidade': 'L', 'coeficiente': 0.2, 'preco_unitario': 50.0,
                 'subtotal_unitario': 10.0},
            ],
        )
        db.session.add_all([i1, i2]); db.session.flush()

        # Proposta vinculando o orçamento → obra
        prop = Proposta(
            admin_id=admin.id,
            numero=f'PROP-63-{s[-6:]}',
            data_proposta=date(2026, 3, 1),
            titulo='Proposta 63',
            cliente_id=cli.id,
            cliente_nome=cli.nome,
            cliente_email=cli.email,
            orcamento_id=orc.id, status='aprovada',
        )
        db.session.add(prop); db.session.flush()

        obra = Obra(
            nome=f'Obra 63 {s}', codigo=f'O63-{s[-6:]}',
            admin_id=admin.id, status='Em andamento',
            cliente_id=cli.id, proposta_origem_id=prop.id,
            data_inicio=date(2026, 3, 1),
        )
        db.session.add(obra); db.session.flush()
        return admin, obra, orc, i1, i2

    def run(self):
        with app.app_context():
            try:
                admin, obra, orc, i1, i2 = self.setup()

                # ── 1) garantir_operacional clona itens + 1 versão por item ──
                op = garantir_operacional(obra.id, criado_por_id=admin.id)
                self.check(op is not None, "operacional criado")
                self.check(op.obra_id == obra.id, "operacional vinculado à obra")
                self.check(op.orcamento_origem_id == orc.id,
                           "orcamento_origem_id setado")

                itens = ObraOrcamentoOperacionalItem.query.filter_by(
                    operacional_id=op.id).all()
                self.check(len(itens) == 2,
                           f"clonou 2 itens (real={len(itens)})")

                versoes_i1 = ObraOrcamentoOperacionalItemVersao.query.filter_by(
                    item_id=itens[0].id).all()
                self.check(len(versoes_i1) == 1,
                           f"item 1 tem 1 versão inicial (real={len(versoes_i1)})")
                self.check(versoes_i1[0].vigente_ate is None,
                           "versão inicial tem vigente_ate=NULL")
                self.check(len(versoes_i1[0].composicao_snapshot or []) == 2,
                           "composicao_snapshot copiada")
                self.check(float(versoes_i1[0].margem_pct) == 20.0,
                           f"margem_pct copiada (real={versoes_i1[0].margem_pct})")

                # ── 2) Idempotência: chamar de novo NÃO duplica ──
                op2 = garantir_operacional(obra.id, criado_por_id=admin.id)
                self.check(op2.id == op.id, "idempotente: mesma op")
                itens_2 = ObraOrcamentoOperacionalItem.query.filter_by(
                    operacional_id=op.id).all()
                self.check(len(itens_2) == 2, "idempotente: itens não duplicaram")

                # ── 3) obter_operacional_vigente busca janela correta ──
                item_op = itens[0]
                hoje = datetime.utcnow()
                amanha = hoje + timedelta(days=1)
                vig_now = obter_operacional_vigente(obra.id, item_op.id, hoje)
                self.check(vig_now is not None, "vigente encontrada para hoje")
                self.check(float(vig_now['margem_pct']) == 20.0,
                           "vigente devolve margem original")

                # ── 4) editar_item modo='a_partir_de_hoje' ──
                nova_comp = list(versoes_i1[0].composicao_snapshot)
                nova_comp[0] = dict(nova_comp[0])
                nova_comp[0]['preco_unitario'] = 2.0  # cimento subiu
                ver_nova = editar_item(
                    item_id=item_op.id, nova_composicao=nova_comp,
                    nova_margem_pct=22, novo_imposto_pct=10,
                    modo='a_partir_de_hoje', criado_por_id=admin.id,
                    motivo='Aumento do cimento',
                )
                self.check(ver_nova.modo_aplicacao == 'a_partir_de_hoje',
                           "nova versão criada com modo correto")
                self.check(ver_nova.vigente_ate is None,
                           "nova versão tem vigente_ate=NULL")
                # A versão antiga deve ter sido fechada
                db.session.refresh(versoes_i1[0])
                self.check(versoes_i1[0].vigente_ate is not None,
                           "versão anterior fechada (vigente_ate setado)")

                # ── 5) Janela temporal: pré-edição → versão antiga ──
                pre_edit = versoes_i1[0].vigente_de + timedelta(seconds=1)
                vig_antiga = obter_operacional_vigente(obra.id, item_op.id, pre_edit)
                self.check(
                    abs(float(vig_antiga['margem_pct']) - 20.0) < 0.001,
                    f"data antes da edição usa margem antiga (20%) — real={vig_antiga['margem_pct']}",
                )
                vig_pos = obter_operacional_vigente(obra.id, item_op.id, amanha)
                self.check(
                    abs(float(vig_pos['margem_pct']) - 22.0) < 0.001,
                    f"data depois usa margem nova (22%) — real={vig_pos['margem_pct']}",
                )

                # ── 6) editar_item modo='retroativo' atualiza in-place ──
                vig_atual = (
                    ObraOrcamentoOperacionalItemVersao.query
                    .filter_by(item_id=item_op.id, vigente_ate=None).first()
                )
                versoes_antes = ObraOrcamentoOperacionalItemVersao.query.filter_by(
                    item_id=item_op.id).count()
                editar_item(
                    item_id=item_op.id, nova_composicao=nova_comp,
                    nova_margem_pct=23, novo_imposto_pct=10,
                    modo='retroativo', criado_por_id=admin.id,
                    motivo='correção',
                )
                db.session.refresh(vig_atual)
                self.check(float(vig_atual.margem_pct) == 23.0,
                           f"retroativo: vigente atualizada in-place ({vig_atual.margem_pct})")
                versoes_depois = ObraOrcamentoOperacionalItemVersao.query.filter_by(
                    item_id=item_op.id).count()
                self.check(versoes_depois == versoes_antes + 1,
                           f"retroativo: +1 linha auditoria ({versoes_antes}→{versoes_depois})")

                # ── 7) modo inválido levanta ──
                try:
                    editar_item(item_id=item_op.id, nova_composicao=[],
                                nova_margem_pct=0, novo_imposto_pct=0,
                                modo='xpto')
                    self.check(False, "modo inválido deveria levantar")
                except ValueError:
                    self.check(True, "modo inválido levanta ValueError")

                # ── 8) diff_com_original detecta mudanças ──
                # operacional foi editado (margem 23 ≠ 20), original não mudou
                diffs = diff_com_original(obra.id)
                self.check(len(diffs) >= 1,
                           f"diff detecta mudança (≥1, real={len(diffs)})")

                # ── 9) atualizar_do_original puxa de volta (a partir de hoje) ──
                n = atualizar_do_original(obra.id, criado_por_id=admin.id)
                self.check(n >= 1, f"atualizou ≥1 item do original (real={n})")
                # após atualizar, diff zera
                diffs_pos = diff_com_original(obra.id)
                self.check(len(diffs_pos) == 0,
                           f"após atualizar, diff vazio (real={len(diffs_pos)})")

                # ── 10) listar_versoes devolve histórico ordenado ──
                lst = listar_versoes(item_op.id)
                self.check(len(lst) >= 4,
                           f"histórico tem ≥4 versões (real={len(lst)})")

                # ── 11) Auto-clone via after_insert listener ──
                # Cria uma 2ª obra SEM operacional, insere RDO, verifica que
                # o operacional foi criado automaticamente após o commit.
                s2 = self._suf()
                obra2 = Obra(
                    nome=f'Obra63b {s2}', codigo=f'O63b-{s2[-6:]}',
                    admin_id=admin.id, status='Em andamento',
                    cliente_id=obra.cliente_id, proposta_origem_id=obra.proposta_origem_id,
                    data_inicio=date(2026, 4, 1),
                )
                db.session.add(obra2); db.session.commit()
                op_antes = ObraOrcamentoOperacional.query.filter_by(obra_id=obra2.id).first()
                self.check(op_antes is None, "obra2 começa sem operacional")
                rdo = RDO(
                    numero_rdo=f'RDO-63-{s2[-6:]}',
                    data_relatorio=date(2026, 4, 5), obra_id=obra2.id,
                    criado_por_id=admin.id, admin_id=admin.id,
                    status='Finalizado',
                )
                db.session.add(rdo); db.session.commit()
                # auto-clone roda em Timer thread separado — esperamos brevemente
                import time
                op_depois = None
                for _ in range(30):
                    time.sleep(0.1)
                    db.session.expire_all()
                    op_depois = ObraOrcamentoOperacional.query.filter_by(obra_id=obra2.id).first()
                    if op_depois:
                        break
                self.check(op_depois is not None,
                           "auto-clone após RDO (Timer): operacional criado")
                if op_depois:
                    n_itens = ObraOrcamentoOperacionalItem.query.filter_by(
                        operacional_id=op_depois.id).count()
                    self.check(n_itens == 2,
                               f"auto-clone copiou 2 itens (real={n_itens})")

            except Exception as e:
                log.exception("erro inesperado no runner")
                self.failed.append(f"exception: {e}")
            finally:
                db.session.rollback()

        log.info("=" * 70)
        log.info(f"PASS: {len(self.passed)}   FAIL: {len(self.failed)}")
        for f in self.failed:
            log.error(f"  ✗ {f}")
        return len(self.failed) == 0


def test_orcamento_operacional():
    """Pytest entry-point."""
    r = Runner()
    ok = r.run()
    assert ok, f"{len(r.failed)} checks falharam: {r.failed}"


if __name__ == '__main__':
    r = Runner()
    sys.exit(0 if r.run() else 1)
