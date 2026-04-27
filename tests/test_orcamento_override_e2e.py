"""
Task #120 — Teste E2E: Orçamento com override de cronograma → Proposta →
Aprovação → Cronograma materializado corretamente.

Cobre o fluxo introduzido pela Task #118:

  1. Cria Orçamento com 4 cenários (mesmo formato do seed Construtora Alfa):
     (a) padrão herdado — sem override, usa Servico.template_padrao_id
     (b) serviço novo (criado "como se fosse" pelo modal) — template padrão
     (c) override por linha — cronograma_template_override_id ≠ padrão do serviço
     (d) composição customizada (1 add + 1 remove) — sem override de cronograma
  2. Gera a Proposta a partir do Orçamento (rota gerar_proposta) e valida
     que cada PropostaItem recebeu `cronograma_template_override_id` e
     `composicao_snapshot` propagados do OrcamentoItem original.
  3. Aprova a proposta (Obra criada + handler proposta_aprovada disparado) e
     valida que TarefaCronograma foi materializado a partir do template do
     OVERRIDE para o item (c) e do template PADRÃO do serviço para os
     itens (a)/(b)/(d).

Roda com:  python tests/test_orcamento_override_e2e.py
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from models import (  # noqa: E402
    Cliente,
    ComposicaoServico,
    CronogramaTemplate,
    CronogramaTemplateItem,
    Insumo,
    Obra,
    Orcamento,
    OrcamentoItem,
    PrecoBaseInsumo,
    Proposta,
    PropostaItem,
    Servico,
    TarefaCronograma,
    TipoUsuario,
    Usuario,
)
from event_manager import EventManager  # noqa: E402
from handlers.propostas_handlers import handle_proposta_aprovada  # noqa: F401,E402
from services.cronograma_proposta import montar_arvore_preview  # noqa: E402
from services.orcamento_view_service import (  # noqa: E402
    recalcular_item,
    recalcular_orcamento,
    snapshot_from_servico,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OverrideE2ERunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.passed: list[str] = []
        self.failed: list[str] = []

        self.admin: Usuario | None = None
        self.cliente: Cliente | None = None
        self.tmpl_alv: CronogramaTemplate | None = None
        self.tmpl_pis: CronogramaTemplate | None = None
        self.tmpl_alv_expresso: CronogramaTemplate | None = None
        self.serv_alv: Servico | None = None
        self.serv_pis: Servico | None = None
        self.serv_reboco: Servico | None = None
        self.orcamento: Orcamento | None = None
        self.it_a: OrcamentoItem | None = None
        self.it_b: OrcamentoItem | None = None
        self.it_c: OrcamentoItem | None = None
        self.it_d: OrcamentoItem | None = None
        self.proposta: Proposta | None = None

    # ── Helpers ──────────────────────────────────────────────────────────
    def _assert(self, cond: bool, label: str):
        (self.passed if cond else self.failed).append(label)
        (logger.info if cond else logger.error)(
            f"{'PASS' if cond else 'FAIL'}: {label}"
        )

    def _suffix(self) -> str:
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def _make_template(self, nome: str, etapas: list[str], aid: int) -> CronogramaTemplate:
        """Cria um template com 1 grupo raiz + N folhas (subatividades)."""
        tpl = CronogramaTemplate(
            nome=nome, descricao=f'tpl {nome}',
            categoria='Teste', ativo=True, admin_id=aid,
        )
        db.session.add(tpl); db.session.flush()
        grupo = CronogramaTemplateItem(
            template_id=tpl.id, parent_item_id=None,
            nome_tarefa=f'{nome} — grupo', ordem=1, duracao_dias=1,
            admin_id=aid,
        )
        db.session.add(grupo); db.session.flush()
        for i, et in enumerate(etapas, start=1):
            db.session.add(CronogramaTemplateItem(
                template_id=tpl.id, parent_item_id=grupo.id,
                nome_tarefa=et, ordem=i, duracao_dias=2,
                admin_id=aid,
            ))
        db.session.flush()
        return tpl

    # ── Setup ────────────────────────────────────────────────────────────
    def setup(self):
        suf = self._suffix()
        self.admin = Usuario(
            username=f'ovr_admin_{suf}',
            email=f'ovr_admin_{suf}@test.local',
            nome='Override E2E Admin',
            password_hash=generate_password_hash('Teste@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(self.admin); db.session.flush()
        aid = self.admin.id

        self.cliente = Cliente(
            admin_id=aid,
            nome=f'Cliente Override {suf}',
            email=f'cli_ovr_{suf}@test.local',
        )
        db.session.add(self.cliente); db.session.flush()

        # Templates padrão para 2 serviços + 1 template "expresso" (override).
        self.tmpl_alv = self._make_template(
            f'Alvenaria padrao {suf}',
            ['Marcação', 'Elevação', 'Encunhamento'],
            aid,
        )
        self.tmpl_pis = self._make_template(
            f'Contrapiso padrao {suf}',
            ['Regularização', 'Cura'],
            aid,
        )
        self.tmpl_alv_expresso = self._make_template(
            f'Alvenaria expressa {suf}',
            ['Marcação + 1ª fiada', 'Elevação até cinta'],
            aid,
        )

        # Serviços com template padrão.
        self.serv_alv = Servico(
            admin_id=aid, nome=f'Alvenaria {suf}',
            categoria='Vedação', unidade_medida='m2',
            unidade_simbolo='m²', custo_unitario=50.0, ativo=True,
            template_padrao_id=self.tmpl_alv.id,
        )
        self.serv_pis = Servico(
            admin_id=aid, nome=f'Contrapiso {suf}',
            categoria='Piso', unidade_medida='m2',
            unidade_simbolo='m²', custo_unitario=40.0, ativo=True,
            template_padrao_id=self.tmpl_pis.id,
        )
        # Serviço criado "no modal" — também tem template padrão.
        self.serv_reboco = Servico(
            admin_id=aid, nome=f'Reboco modal {suf}',
            categoria='Acabamento', unidade_medida='m2',
            unidade_simbolo='m²', custo_unitario=38.0, ativo=True,
            template_padrao_id=self.tmpl_pis.id,
        )
        db.session.add_all([self.serv_alv, self.serv_pis, self.serv_reboco])
        db.session.flush()

        # Insumo + composição para serv_pis (necessário para o cenário D
        # exercitar a remoção: snapshot_from_servico precisa retornar ≥1 item).
        ins = Insumo(admin_id=aid, nome=f'Cimento CP II {suf}', tipo='MATERIAL', unidade='kg')
        db.session.add(ins); db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=aid, insumo_id=ins.id,
            valor=Decimal('0.85'), vigencia_inicio=date.today(),
        ))
        db.session.add(ComposicaoServico(
            admin_id=aid, servico_id=self.serv_pis.id,
            insumo_id=ins.id, coeficiente=Decimal('0.5'),
        ))
        db.session.flush()

        # Orçamento + 4 itens cobrindo os 4 cenários do seed.
        self.orcamento = Orcamento(
            admin_id=aid, numero=f'ORC-T120-{suf[-8:]}',
            titulo='Orçamento override (Task #120)',
            descricao='4 cenários: padrão, modal, override, composição custom',
            cliente_id=self.cliente.id, cliente_nome=self.cliente.nome,
            criado_por=aid, status='rascunho',
        )
        db.session.add(self.orcamento); db.session.flush()

        # (a) padrão herdado — sem override
        self.it_a = OrcamentoItem(
            admin_id=aid, orcamento_id=self.orcamento.id, ordem=1,
            servico_id=self.serv_alv.id,
            descricao='Cenário A — padrão herdado',
            unidade='m2', quantidade=Decimal('100'),
            composicao_snapshot=snapshot_from_servico(self.serv_alv),
            cronograma_template_override_id=None,
        )
        # (b) "novo serviço criado no modal" — template padrão escolhido
        self.it_b = OrcamentoItem(
            admin_id=aid, orcamento_id=self.orcamento.id, ordem=2,
            servico_id=self.serv_reboco.id,
            descricao='Cenário B — serviço criado no modal',
            unidade='m2', quantidade=Decimal('80'),
            composicao_snapshot=snapshot_from_servico(self.serv_reboco),
            cronograma_template_override_id=None,
        )
        # (c) override por linha — template ≠ padrão do serviço
        self.it_c = OrcamentoItem(
            admin_id=aid, orcamento_id=self.orcamento.id, ordem=3,
            servico_id=self.serv_alv.id,
            descricao='Cenário C — cronograma override (expresso)',
            unidade='m2', quantidade=Decimal('60'),
            composicao_snapshot=snapshot_from_servico(self.serv_alv),
            cronograma_template_override_id=self.tmpl_alv_expresso.id,
        )
        # (d) composição customizada — 1 add + 1 remove vs catálogo
        original_d = list(snapshot_from_servico(self.serv_pis)) or []
        snap_d = list(original_d)
        self._removido_nome_d = None
        if snap_d:
            self._removido_nome_d = (snap_d[0].get('nome') or '').strip()
            snap_d.pop(0)  # remove o primeiro insumo do catálogo
        snap_d.append({
            'tipo': 'MATERIAL', 'insumo_id': None,
            'nome': 'Insumo extra (cenário D)',
            'unidade': 'kg', 'coeficiente': 0.5,
            'preco_unitario': 1.0, 'subtotal_unitario': 0.5,
        })
        self.it_d = OrcamentoItem(
            admin_id=aid, orcamento_id=self.orcamento.id, ordem=4,
            servico_id=self.serv_pis.id,
            descricao='Cenário D — composição customizada',
            unidade='m2', quantidade=Decimal('120'),
            composicao_snapshot=snap_d,
            cronograma_template_override_id=None,
        )
        db.session.add_all([self.it_a, self.it_b, self.it_c, self.it_d])
        db.session.flush()
        for it in (self.it_a, self.it_b, self.it_c, self.it_d):
            recalcular_item(it, self.orcamento)
        recalcular_orcamento(self.orcamento)
        db.session.commit()

    # ── Etapas do teste ──────────────────────────────────────────────────
    def teste_gerar_proposta_via_rota(self):
        """Testa a rota POST /orcamentos/<id>/gerar-proposta autenticada."""
        with self.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(self.admin.id)
                sess['_fresh'] = True
            resp = c.post(
                f'/orcamentos/{self.orcamento.id}/gerar-proposta',
                follow_redirects=False,
            )
        # Aceita 302 (redirect para visualizar/editar) — ambos confirmam
        # execução da rota (sem 4xx/5xx).
        self._assert(
            resp.status_code in (302, 303),
            f'rota gerar_proposta retorna redirect (status={resp.status_code})',
        )

        # Localiza a Proposta criada para este orçamento.
        self.proposta = (
            Proposta.query
            .filter_by(orcamento_id=self.orcamento.id, admin_id=self.admin.id)
            .order_by(Proposta.id.desc())
            .first()
        )
        self._assert(
            self.proposta is not None,
            'Proposta criada vinculada ao orçamento',
        )
        if not self.proposta:
            return

        itens = (
            PropostaItem.query
            .filter_by(proposta_id=self.proposta.id)
            .order_by(PropostaItem.ordem.asc())
            .all()
        )
        self._assert(
            len(itens) == 4,
            f'Proposta tem 4 itens (achou {len(itens)})',
        )
        if len(itens) != 4:
            return
        pi_a, pi_b, pi_c, pi_d = itens

        # Override de cronograma propagado (Task #118).
        self._assert(
            pi_a.cronograma_template_override_id is None,
            f'PI(a) sem override (achou {pi_a.cronograma_template_override_id})',
        )
        self._assert(
            pi_b.cronograma_template_override_id is None,
            f'PI(b) sem override (achou {pi_b.cronograma_template_override_id})',
        )
        self._assert(
            pi_c.cronograma_template_override_id == self.tmpl_alv_expresso.id,
            f'PI(c) override = expresso (achou {pi_c.cronograma_template_override_id})',
        )
        self._assert(
            pi_d.cronograma_template_override_id is None,
            f'PI(d) sem override (achou {pi_d.cronograma_template_override_id})',
        )

        # composicao_snapshot propagado.
        self._assert(
            isinstance(pi_a.composicao_snapshot, list),
            'PI(a) composicao_snapshot é lista',
        )
        snap_d_pi = pi_d.composicao_snapshot or []
        self._assert(
            isinstance(pi_d.composicao_snapshot, list)
            and any('cenário d' in (i.get('nome') or '').lower() for i in snap_d_pi),
            'PI(d) composicao_snapshot preserva insumo ADICIONADO no orçamento',
        )
        # Remove deve ter sido propagado: o insumo removido em snap_d
        # NÃO pode aparecer no PropostaItem.
        if self._removido_nome_d:
            nomes_pi_d = {(i.get('nome') or '').strip() for i in snap_d_pi}
            self._assert(
                self._removido_nome_d not in nomes_pi_d,
                f'PI(d) composicao_snapshot preserva REMOÇÃO ({self._removido_nome_d!r} ausente)',
            )

    def teste_aprovar_e_materializar_cronograma(self):
        """Aprova a proposta e valida que TarefaCronograma materializa
        o template correto por item (override → expresso, sem override → padrão)."""
        if not self.proposta:
            self._assert(False, 'precondição: proposta criada na etapa anterior')
            return

        aid = self.admin.id

        # Snapshot da árvore (precedência override→padrão), tudo marcado.
        arvore = montar_arvore_preview(self.proposta, aid)
        self._assert(
            len(arvore) == 4,
            f'preview tem 4 entradas (achou {len(arvore)})',
        )
        # Origem do template por item.
        by_pi = {n['proposta_item_id']: n for n in arvore}
        # Mapa ordem→propostaItem para identificar A/B/C/D.
        pi_por_ordem = {
            it.ordem: it for it in PropostaItem.query.filter_by(
                proposta_id=self.proposta.id
            ).all()
        }
        n_c = by_pi.get(pi_por_ordem[3].id)
        n_a = by_pi.get(pi_por_ordem[1].id)
        self._assert(
            n_c is not None and n_c.get('origem_template') == 'override',
            f"preview do item C origem=override (achou {n_c and n_c.get('origem_template')})",
        )
        self._assert(
            n_a is not None and n_a.get('origem_template') == 'padrao',
            f"preview do item A origem=padrao (achou {n_a and n_a.get('origem_template')})",
        )
        self._assert(
            n_c and n_c.get('template_id') == self.tmpl_alv_expresso.id,
            'preview do item C aponta para tmpl_alv_expresso',
        )
        self._assert(
            n_a and n_a.get('template_id') == self.tmpl_alv.id,
            'preview do item A aponta para tmpl_alv (padrão do serviço)',
        )

        # Persiste o snapshot de revisão (com tudo marcado) para o handler
        # materializar o cronograma.
        self.proposta.cronograma_default_json = arvore
        self.proposta.status = 'aprovada'

        # Cria a Obra associada (mesma lógica da rota de aprovação).
        obra = Obra(
            nome=f'Obra E2E #{self.proposta.id} — Task #120',
            codigo=f'E2E120-{self.proposta.id}',
            admin_id=aid, status='Em andamento',
            data_inicio=date.today(),
            proposta_origem_id=self.proposta.id,
            cliente_id=self.cliente.id,
        )
        db.session.add(obra); db.session.flush()
        self.proposta.obra_id = obra.id
        db.session.flush()

        try:
            EventManager.emit('proposta_aprovada', {
                'proposta_id': self.proposta.id,
                'admin_id': aid,
                'cliente_nome': self.proposta.cliente_nome,
                'valor_total': float(self.proposta.valor_total or 0),
                'data_aprovacao': date.today().isoformat(),
            }, aid)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self._assert(False, f'evento proposta_aprovada sem erro (erro: {e})')
            return
        self._assert(True, 'evento proposta_aprovada disparado sem erro')

        # ── Validação da materialização ──
        tarefas = TarefaCronograma.query.filter_by(
            obra_id=obra.id, admin_id=aid,
        ).all()
        self._assert(
            len(tarefas) > 0,
            f'TarefaCronograma materializadas (total={len(tarefas)})',
        )

        # Agrupa tarefas por proposta_item_id.
        por_pi: dict[int, list[TarefaCronograma]] = {}
        for t in tarefas:
            por_pi.setdefault(t.gerada_por_proposta_item_id, []).append(t)

        pi_a = pi_por_ordem[1]
        pi_b = pi_por_ordem[2]
        pi_c = pi_por_ordem[3]
        pi_d = pi_por_ordem[4]

        # Cenário C — origem do override (template expresso).
        nomes_c = {t.nome_tarefa for t in por_pi.get(pi_c.id, [])}
        nomes_expresso = {
            ci.nome_tarefa for ci in CronogramaTemplateItem.query.filter_by(
                template_id=self.tmpl_alv_expresso.id
            ).all()
        }
        # Cada folha do template-override deve aparecer entre as tarefas do item C.
        intersec_c = nomes_c & nomes_expresso
        self._assert(
            len(intersec_c) >= 2,
            f'cenário C: tarefas vêm do template OVERRIDE (folhas em comum={len(intersec_c)})',
        )
        # E NÃO devem vir do template padrão (alv) — nomes distintos.
        nomes_padrao_alv = {
            ci.nome_tarefa for ci in CronogramaTemplateItem.query.filter_by(
                template_id=self.tmpl_alv.id
            ).all()
        }
        leak_c = nomes_c & (nomes_padrao_alv - nomes_expresso)
        self._assert(
            len(leak_c) == 0,
            f'cenário C: nenhuma tarefa vazada do padrão alv (vazadas={leak_c})',
        )

        # Cenário A — origem do template padrão do serviço.
        nomes_a = {t.nome_tarefa for t in por_pi.get(pi_a.id, [])}
        intersec_a = nomes_a & nomes_padrao_alv
        self._assert(
            len(intersec_a) >= 2,
            f'cenário A: tarefas vêm do template PADRÃO do serviço (em comum={len(intersec_a)})',
        )
        leak_a = nomes_a & (nomes_expresso - nomes_padrao_alv)
        self._assert(
            len(leak_a) == 0,
            f'cenário A: nenhuma tarefa vazada do template expresso (vazadas={leak_a})',
        )

        # Cenário B/D — origem do template padrão (não há override).
        nomes_padrao_pis = {
            ci.nome_tarefa for ci in CronogramaTemplateItem.query.filter_by(
                template_id=self.tmpl_pis.id
            ).all()
        }
        nomes_b = {t.nome_tarefa for t in por_pi.get(pi_b.id, [])}
        nomes_d = {t.nome_tarefa for t in por_pi.get(pi_d.id, [])}
        self._assert(
            len(nomes_b & nomes_padrao_pis) >= 1,
            f'cenário B: tarefas vêm do template padrão (pis) — em comum={len(nomes_b & nomes_padrao_pis)}',
        )
        self._assert(
            len(nomes_d & nomes_padrao_pis) >= 1,
            f'cenário D: tarefas vêm do template padrão (pis) — em comum={len(nomes_d & nomes_padrao_pis)}',
        )

    # ── Cleanup ──────────────────────────────────────────────────────────
    def cleanup(self):
        """Remove todos os dados criados pelo runner para evitar poluição
        do banco persistente. Identifica registros pelo admin_id de teste."""
        if not self.admin or not self.admin.id:
            return
        aid = self.admin.id
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            from models import (
                ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
                LancamentoContabil, PartidaContabil,
                ObraServicoCusto, PropostaHistorico,
            )
            # Ordem importa por FKs.
            for model in (ItemMedicaoCronogramaTarefa, PartidaContabil):
                model.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            for model in (
                TarefaCronograma, ItemMedicaoComercial, ObraServicoCusto,
                LancamentoContabil, PropostaHistorico, PropostaItem,
                OrcamentoItem,
            ):
                model.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Proposta.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Orcamento.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Obra.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Servico.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            CronogramaTemplateItem.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            CronogramaTemplate.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            ComposicaoServico.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            PrecoBaseInsumo.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Insumo.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Cliente.query.filter_by(admin_id=aid).delete(synchronize_session=False)
            Usuario.query.filter_by(id=aid).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('cleanup falhou — registros podem ter ficado')

    # ── Run ──────────────────────────────────────────────────────────────
    def run(self) -> int:
        with self.app.app_context():
            try:
                self.setup()
                self.teste_gerar_proposta_via_rota()
                self.teste_aprovar_e_materializar_cronograma()
            except Exception:
                logger.exception('Falha inesperada no runner Task #120')
                self.failed.append('runner sem exceção inesperada')
            finally:
                self.cleanup()

        print('=' * 80)
        print('TASK #120 — ORÇAMENTO COM OVERRIDE → PROPOSTA → CRONOGRAMA')
        print('=' * 80)
        print(f'PASS: {len(self.passed)}')
        print(f'FAIL: {len(self.failed)}')
        for p in self.passed:
            print(f'  ✔ {p}')
        for f in self.failed:
            print(f'  ✘ {f}')
        print('=' * 80)
        return 0 if not self.failed else 1


if __name__ == '__main__':
    sys.exit(OverrideE2ERunner().run())
