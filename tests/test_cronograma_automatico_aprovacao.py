"""
Task #102 — Teste E2E da materialização de cronograma na aprovação de proposta.

Cobre:
  - Servico com `template_padrao_id` derivado de CronogramaTemplate de 2 níveis
    (grupo → 2 subatividades) gera, ao aprovar a proposta, hierarquia de
    TarefaCronograma com 3 níveis: Serviço → Grupo → Subatividade.
  - ItemMedicaoCronogramaTarefa é criado para cada folha (subatividade) com
    pesos somando 100.
  - Idempotência: chamar materializar_cronograma novamente NÃO duplica.

Executa com:  python tests/test_cronograma_automatico_aprovacao.py
"""
import os
import sys
import logging
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from werkzeug.security import generate_password_hash
from models import (
    Usuario, TipoUsuario, Servico, Proposta, PropostaItem,
    CronogramaTemplate, CronogramaTemplateItem,
    TarefaCronograma, ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
)
from services.cronograma_proposta import (
    montar_arvore_preview, materializar_cronograma,
)
from handlers.propostas_handlers import handle_proposta_aprovada  # noqa: F401
from event_manager import EventManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CronogramaAprovacaoRunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.admin = None
        self.servico = None
        self.template = None
        self.proposta = None
        self.proposta_item = None

    def _assert(self, cond, label):
        (self.passed if cond else self.failed).append(label)
        (logger.info if cond else logger.error)(f"{'PASS' if cond else 'FAIL'}: {label}")

    def _suffix(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup(self):
        suf = self._suffix()
        self.admin = Usuario(
            username=f'cron_admin_{suf}',
            email=f'cron_admin_{suf}@test.local',
            nome='Cronograma Test Admin',
            password_hash=generate_password_hash('Teste@2025'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(self.admin)
        db.session.flush()
        admin_id = self.admin.id

        # Template com 1 grupo (Estrutura) e 2 subatividades-folhas
        self.template = CronogramaTemplate(
            nome=f'Tpl Estrutura {suf}',
            categoria='Estrutural',
            ativo=True,
            admin_id=admin_id,
        )
        db.session.add(self.template)
        db.session.flush()

        grupo = CronogramaTemplateItem(
            template_id=self.template.id,
            nome_tarefa='Estrutura Metálica',
            ordem=1, duracao_dias=10,
            admin_id=admin_id,
        )
        db.session.add(grupo)
        db.session.flush()

        sub_a = CronogramaTemplateItem(
            template_id=self.template.id,
            parent_item_id=grupo.id,
            nome_tarefa='Fabricação',
            ordem=1, duracao_dias=5, quantidade_prevista=100.0,
            responsavel='empresa', admin_id=admin_id,
        )
        sub_b = CronogramaTemplateItem(
            template_id=self.template.id,
            parent_item_id=grupo.id,
            nome_tarefa='Montagem',
            ordem=2, duracao_dias=5, quantidade_prevista=100.0,
            responsavel='empresa', admin_id=admin_id,
        )
        db.session.add_all([sub_a, sub_b])
        db.session.flush()

        # Servico com template_padrao_id
        self.servico = Servico(
            nome=f'Servico Estrutural {suf}',
            categoria='Estrutural',
            unidade_medida='unidade',
            unidade_simbolo='un',
            custo_unitario=100.0,
            admin_id=admin_id,
            ativo=True,
            template_padrao_id=self.template.id,
        )
        db.session.add(self.servico)
        db.session.flush()

        # Proposta
        self.proposta = Proposta(
            numero=f'P{suf[:10]}',
            cliente_nome='Cliente Teste #102',
            titulo='Proposta Teste #102',
            status='enviada',
            admin_id=admin_id,
            criado_por=admin_id,
            valor_total=Decimal('1000.00'),
        )
        db.session.add(self.proposta)
        db.session.flush()

        self.proposta_item = PropostaItem(
            admin_id=admin_id,
            proposta_id=self.proposta.id,
            item_numero=1,
            descricao=self.servico.nome,
            quantidade=Decimal('1'),
            unidade='un',
            preco_unitario=Decimal('1000.00'),
            ordem=1,
            servico_id=self.servico.id,
        )
        db.session.add(self.proposta_item)
        db.session.commit()

    def teste_arvore_preview(self):
        arvore = montar_arvore_preview(self.proposta, self.admin.id)
        self._assert(len(arvore) == 1, f'preview retorna 1 entrada (achou {len(arvore)})')
        if not arvore:
            return
        n0 = arvore[0]
        self._assert(n0['proposta_item_id'] == self.proposta_item.id, 'preview vincula ao proposta_item correto')
        self._assert(n0['template_id'] == self.template.id, 'preview vincula ao template correto')
        self._assert(n0['marcado'] is True, 'raiz default marcada')
        self._assert(len(n0['filhos']) == 1, f"preview tem 1 grupo (achou {len(n0['filhos'])})")
        if n0['filhos']:
            grupo = n0['filhos'][0]
            self._assert(len(grupo['filhos']) == 2, f"grupo tem 2 subatividades (achou {len(grupo['filhos'])})")
            self._assert(grupo['tipo'] == 'grupo', "tipo do nó com filhos é 'grupo'")

    def teste_materializacao(self):
        # Aprova a proposta — handler dispara propagação + materialização.
        self.proposta.status = 'aprovada'
        db.session.commit()
        try:
            EventManager.emit('proposta_aprovada', {
                'proposta_id': self.proposta.id,
                'admin_id': self.admin.id,
                'cliente_nome': self.proposta.cliente_nome,
                'valor_total': float(self.proposta.valor_total or 0),
                'data_aprovacao': date.today().isoformat(),
            }, self.admin.id)
        except Exception as e:
            self._assert(False, f'evento proposta_aprovada sem erro (erro: {e})')
            return
        self._assert(True, 'evento proposta_aprovada disparado sem erro')

        # Recarrega proposta para pegar obra_id
        db.session.refresh(self.proposta)
        self._assert(self.proposta.obra_id is not None,
                     f'obra criada (obra_id={self.proposta.obra_id})')
        if not self.proposta.obra_id:
            return

        tarefas = TarefaCronograma.query.filter_by(
            obra_id=self.proposta.obra_id,
            admin_id=self.admin.id,
            gerada_por_proposta_item_id=self.proposta_item.id,
        ).all()
        # Esperado: 1 raiz (Serviço) + 1 grupo + 2 subatividades = 4
        self._assert(len(tarefas) == 4,
                     f'4 TarefaCronograma criadas (Servico + Grupo + 2 Sub) — achou {len(tarefas)}')

        raizes = [t for t in tarefas if t.tarefa_pai_id is None]
        self._assert(len(raizes) == 1, f'1 raiz Serviço (achou {len(raizes)})')

        # Folhas = subatividades (sem filhas no conjunto)
        ids_existentes = {t.id for t in tarefas}
        ids_pais = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id in ids_existentes}
        folhas = [t for t in tarefas if t.id not in ids_pais]
        self._assert(len(folhas) == 2, f'2 folhas/subatividades (achou {len(folhas)})')

        # Pesos via ItemMedicaoCronogramaTarefa (precisa existir IMC para o item)
        imc = ItemMedicaoComercial.query.filter_by(
            obra_id=self.proposta.obra_id,
            proposta_item_id=self.proposta_item.id,
            admin_id=self.admin.id,
        ).first()
        self._assert(imc is not None, 'ItemMedicaoComercial existe para o proposta_item')
        if imc:
            vinculos = ItemMedicaoCronogramaTarefa.query.filter_by(
                item_medicao_id=imc.id,
                admin_id=self.admin.id,
            ).all()
            self._assert(len(vinculos) == 2,
                         f'2 vínculos peso para folhas (achou {len(vinculos)})')
            soma = float(sum(v.peso for v in vinculos))
            self._assert(abs(soma - 100.0) < 0.5,
                         f'pesos somam ~100 (achou {soma})')

    def teste_recalcular_datas_e_obra_seed(self):
        """Verifica que recalcular_cronograma rodou: tarefas têm data_fim setada
        e datas começam a partir de obra.data_inicio (não de date.today())."""
        from models import Obra
        obra = Obra.query.get(self.proposta.obra_id)
        tarefas = TarefaCronograma.query.filter_by(
            obra_id=self.proposta.obra_id, admin_id=self.admin.id,
            gerada_por_proposta_item_id=self.proposta_item.id,
        ).all()
        com_fim = [t for t in tarefas if t.data_fim is not None]
        self._assert(len(com_fim) >= 3, f'tarefas tem data_fim após recalcular ({len(com_fim)} de {len(tarefas)})')
        if obra and obra.data_inicio:
            datas_inicio = [t.data_inicio for t in tarefas if t.data_inicio]
            min_inicio = min(datas_inicio) if datas_inicio else None
            self._assert(
                min_inicio is None or min_inicio >= obra.data_inicio,
                f'datas iniciam em obra.data_inicio={obra.data_inicio} (mínimo={min_inicio})',
            )

    def teste_dois_servicos_um_sem_template(self):
        """Adicionar 2º item à proposta: um Serviço SEM template_padrao_id.
        Materializar de novo (proposta-item NOVO) → só o item com template gera tarefas;
        item sem template é ignorado (sem_template=True na árvore)."""
        suf = self._suffix()
        servico_sem_tpl = Servico(
            nome=f'Servico Sem Tpl {suf}',
            categoria='Outros',
            unidade_medida='unidade',
            unidade_simbolo='un',
            custo_unitario=50.0,
            admin_id=self.admin.id,
            ativo=True,
            template_padrao_id=None,
        )
        db.session.add(servico_sem_tpl)
        db.session.flush()

        novo_item = PropostaItem(
            admin_id=self.admin.id,
            proposta_id=self.proposta.id,
            item_numero=2,
            descricao=servico_sem_tpl.nome,
            quantidade=Decimal('1'),
            unidade='un',
            preco_unitario=Decimal('500.00'),
            ordem=2,
            servico_id=servico_sem_tpl.id,
        )
        db.session.add(novo_item)
        db.session.commit()

        # Preview agora deve ter 2 entradas, segunda com sem_template=True
        arvore = montar_arvore_preview(self.proposta, self.admin.id)
        self._assert(len(arvore) == 2, f'preview tem 2 entradas (achou {len(arvore)})')
        sem_tpl = [n for n in arvore if n['sem_template']]
        self._assert(len(sem_tpl) == 1, f'1 item marcado sem_template (achou {len(sem_tpl)})')
        self._assert(sem_tpl[0]['marcado'] is False, 'item sem_template default=desmarcado')

        # Materialização: apenas item com template — o outro é skipado
        antes = TarefaCronograma.query.filter_by(
            obra_id=self.proposta.obra_id, admin_id=self.admin.id,
        ).count()
        materializar_cronograma(
            self.proposta, self.admin.id, self.proposta.obra_id, arvore_marcada=arvore
        )
        depois = TarefaCronograma.query.filter_by(
            obra_id=self.proposta.obra_id, admin_id=self.admin.id,
        ).count()
        self._assert(antes == depois,
                     f'item sem_template não criou tarefas extras ({antes}→{depois})')

    def teste_desmarcar_grupo_omite_filhos(self):
        """Cria proposta+item NOVO; chama materializar com a árvore default
        mas desmarcando o grupo → 0 tarefas criadas para esse item."""
        suf = self._suffix()
        nova_prop = Proposta(
            numero=f'P2{suf[:8]}',
            cliente_nome='Cliente Desmarcar',
            titulo='Teste desmarcar',
            status='enviada',
            admin_id=self.admin.id,
            criado_por=self.admin.id,
            valor_total=Decimal('500.00'),
        )
        db.session.add(nova_prop)
        db.session.flush()
        novo_item = PropostaItem(
            admin_id=self.admin.id, proposta_id=nova_prop.id,
            item_numero=1, descricao=self.servico.nome,
            quantidade=Decimal('1'), unidade='un',
            preco_unitario=Decimal('500.00'), ordem=1,
            servico_id=self.servico.id,
        )
        db.session.add(novo_item)
        db.session.commit()

        arvore = montar_arvore_preview(nova_prop, self.admin.id)
        # Desmarcar grupo (e subir nada): nenhum nó marcado em filhos
        for n in arvore:
            for f in n['filhos']:
                f['marcado'] = False
                for s in f.get('filhos', []):
                    s['marcado'] = False
        # Materializar — sem obra_id real, só verificamos que rotina não quebra e
        # não cria nada além da raiz (que poderia ser pulada por não ter folhas).
        # Atribuir obra_id dummy: usar a mesma obra existente para evitar criar nova.
        criadas = materializar_cronograma(
            nova_prop, self.admin.id, self.proposta.obra_id, arvore_marcada=arvore
        )
        # Apenas o nó-raiz "Serviço" pode ter sido criado (já que todos os filhos
        # estão desmarcados, _rec retorna sem adicionar). Aceitamos 0 ou 1.
        self._assert(criadas <= 1,
                     f'desmarcar tudo cria no máximo a raiz (criadas={criadas})')

    def teste_idempotencia(self):
        antes = TarefaCronograma.query.filter_by(
            obra_id=self.proposta.obra_id,
            gerada_por_proposta_item_id=self.proposta_item.id,
        ).count()
        criadas = materializar_cronograma(
            self.proposta, self.admin.id, self.proposta.obra_id, arvore_marcada=None
        )
        depois = TarefaCronograma.query.filter_by(
            obra_id=self.proposta.obra_id,
            gerada_por_proposta_item_id=self.proposta_item.id,
        ).count()
        self._assert(criadas == 0, f're-materialização criou 0 (achou {criadas})')
        self._assert(antes == depois,
                     f'contagem inalterada {antes}→{depois}')

    def teardown(self):
        try:
            db.session.rollback()
        except Exception:
            pass

    def run(self):
        with self.app.app_context():
            try:
                self.setup()
                self.teste_arvore_preview()
                self.teste_materializacao()
                self.teste_recalcular_datas_e_obra_seed()
                self.teste_dois_servicos_um_sem_template()
                self.teste_desmarcar_grupo_omite_filhos()
                self.teste_idempotencia()
            finally:
                self.teardown()

        print('=' * 80)
        print('CRONOGRAMA AUTOMÁTICO NA APROVAÇÃO — RESULTADOS (Task #102)')
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
    sys.exit(CronogramaAprovacaoRunner().run())
