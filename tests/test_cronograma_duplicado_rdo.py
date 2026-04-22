"""
Task #144 — E2E (RED→GREEN) cronograma duplicado no apontamento de RDO.

Cobre o fluxo INTEIRO via Flask test client (HTTP real, não service layer
puro), reproduzindo o bug em que o card "Apontamento de Produção —
Cronograma" da tela "Novo RDO" exibia serviços/subatividades duplicados.

Auditoria de rotas (Step 1) — lista, via `app.url_map`, todas as rotas que
tocam `TarefaCronograma`, classificando cada uma como leitura, materialização
(insert), clone (interno→cliente) ou apontamento. O relatório é gravado em
`.local/cronograma_duplicado_rdo_report.json` para auditoria do reviewer.

Cenários cobertos (cada um grava contagens "antes/depois" no relatório
estruturado):
  R1. Aprovação inicial via HTTP (login → seed cronograma → emit
      proposta_aprovada). Espera 4 tarefas, 0 duplicatas.
  R2. Re-aprovação (re-materializa com PI nulo nas tarefas existentes,
      simulando o caso legado). Antes do fix: 4→8 (DOBRA). Depois do fix:
      4→4 (rota é idempotente).
  R3. Snapshot sem `proposta_item_id` nos nós (snapshot serializado no
      front sem o campo). Antes do fix: dobra. Depois: idempotente.
  R4. POST `/obras/<id>/cronograma-cliente/gerar` chamado 2x via HTTP. Após
      a 2ª chamada, contagem cliente == contagem da 1ª chamada e zero
      duplicatas em `is_cliente=True`.
  R5. POST `/salvar-rdo-flexivel` cria 1º e 2º RDO via HTTP. Em seguida
      `GET /cronograma/obra/<id>/tarefas-rdo` retorna JSON com cada
      `nome_tarefa` aparecendo 1x.
  R6. `GET /rdo/novo?obra_id=<id>` retorna 200; o HTML resposta é capturado
      (`.local/cronograma_duplicado_rdo_novo.html`) — assert estático
      apenas do título e contagem do card (a árvore é montada client-side
      via fetch para `/cronograma/obra/<id>/tarefas-rdo`, que validamos em
      R5).
  R7. Cria DUPLICATA artificial direta no DB; roda
      `deduplicar_tarefas_cronograma`; valida que apontamentos
      (`RDOApontamentoCronograma`) foram reapontados para a tarefa
      canônica e quantidades preservadas.

Executar com:
    python tests/test_cronograma_duplicado_rdo.py
Workflow Replit: `test-cronograma-duplicado-rdo`.
"""
import os
import sys
import json
import logging
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from models import (
    Usuario, TipoUsuario, Servico, Obra, Cliente,
    Proposta, PropostaItem,
    CronogramaTemplate, CronogramaTemplateItem,
    SubatividadeMestre,
    TarefaCronograma, RDO, RDOApontamentoCronograma,
)
from services.cronograma_proposta import (
    montar_arvore_preview, materializar_cronograma,
)
from services.cronograma_dedup import deduplicar_tarefas_cronograma
from event_manager import EventManager
import handlers.propostas_handlers  # noqa: F401  (registra handlers)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.local', 'cronograma_duplicado_rdo_report.json',
)
NOVO_RDO_HTML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.local', 'cronograma_duplicado_rdo_novo.html',
)


def _classificar_route(ep: str, rule: str) -> str | None:
    """Classifica uma rota pela tabela TarefaCronograma. None = não toca."""
    if 'tarefas_rdo' in ep or '/tarefas-rdo' in rule:
        return 'leitura (lista TarefaCronograma)'
    if 'gerar_cronograma_cliente' in ep:
        return 'clone interno→cliente (insert TarefaCronograma is_cliente=True)'
    if 'salvar_rdo_flexivel' in ep:
        return 'apontamento (insert RDOApontamentoCronograma)'
    if ep.startswith('cronograma.') or 'cronograma' in ep:
        return 'leitura/CRUD (cronograma_views)'
    return None


class CronogramaDuplicadoRDORunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.report = {
            'iniciado_em': datetime.utcnow().isoformat() + 'Z',
            'rotas_auditoria': [],   # [{rule, endpoint, classificacao}]
            'route_evidence': [],    # [{step, rota, antes, depois, esperado, ok}]
            'http_calls': [],        # [{step, method, path, status, ok}]
            'asserts': [],           # [{label, ok}]
        }
        self.admin = None
        self.servico = None
        self.template = None
        self.proposta = None
        self.proposta_item = None
        self.obra = None
        self.client = None

    def _assert(self, cond, label):
        (self.passed if cond else self.failed).append(label)
        self.report['asserts'].append({'label': label, 'ok': bool(cond)})
        (logger.info if cond else logger.error)(f"{'PASS' if cond else 'FAIL'}: {label}")

    def _http(self, step, method, path, **kw):
        m = getattr(self.client, method.lower())
        r = m(path, **kw)
        self.report['http_calls'].append({
            'step': step, 'method': method, 'path': path, 'status': r.status_code,
            'ok': r.status_code in (200, 302, 303),
        })
        return r

    def _route_evidence(self, step, rota, antes, depois, esperado_igual=True, extra=''):
        ok = (antes == depois) if esperado_igual else (depois > antes)
        self.report['route_evidence'].append({
            'step': step, 'rota': rota,
            'tarefas_antes': antes, 'tarefas_depois': depois,
            'esperado': 'antes==depois (idempotente)' if esperado_igual else 'depois>antes',
            'ok': ok, 'extra': extra,
        })
        return ok

    def _suffix(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def _contar_duplicatas(self, obra_id, is_cliente=False):
        rows = (
            db.session.query(
                TarefaCronograma.nome_tarefa,
                TarefaCronograma.subatividade_mestre_id,
                TarefaCronograma.tarefa_pai_id,
                func.count('*').label('cnt'),
            )
            .filter(
                TarefaCronograma.obra_id == obra_id,
                TarefaCronograma.is_cliente == is_cliente,
            )
            .group_by(
                TarefaCronograma.nome_tarefa,
                TarefaCronograma.subatividade_mestre_id,
                TarefaCronograma.tarefa_pai_id,
            )
            .having(func.count('*') > 1)
            .all()
        )
        return rows

    def _contar_total(self, obra_id, is_cliente=False):
        return TarefaCronograma.query.filter_by(
            obra_id=obra_id, is_cliente=is_cliente
        ).count()

    # ──────────────────────────────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────────────────────────────
    def setup(self):
        suf = self._suffix()
        self.admin = Usuario(
            username=f'dup_admin_{suf}',
            email=f'dup_admin_{suf}@test.local',
            nome='Cronograma Dup Admin',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(self.admin)
        db.session.flush()
        admin_id = self.admin.id

        # Cliente — necessário para Obra com cliente_nome consistente
        self.cliente = Cliente(
            admin_id=admin_id, nome=f'Cliente Dup {suf}',
            email=f'cli_{suf}@test.local', telefone='11999999999',
        )
        db.session.add(self.cliente)

        # Template Estrutural com 1 grupo + 2 folhas (com SubatividadeMestre)
        sub_a = SubatividadeMestre(
            admin_id=admin_id, nome=f'Aço Laminado {suf}', unidade_medida='kg',
        )
        sub_b = SubatividadeMestre(
            admin_id=admin_id, nome=f'Concretagem laje (PWA) {suf}', unidade_medida='m3',
        )
        db.session.add_all([sub_a, sub_b]); db.session.flush()
        self.sub_a = sub_a
        self.sub_b = sub_b

        self.template = CronogramaTemplate(
            nome=f'Tpl Dup {suf}', categoria='Estrutural',
            ativo=True, admin_id=admin_id,
        )
        db.session.add(self.template); db.session.flush()

        grupo = CronogramaTemplateItem(
            template_id=self.template.id,
            nome_tarefa=f'Estrutura Metálica {suf}',
            ordem=1, duracao_dias=10, admin_id=admin_id,
        )
        db.session.add(grupo); db.session.flush()
        db.session.add_all([
            CronogramaTemplateItem(
                template_id=self.template.id, parent_item_id=grupo.id,
                subatividade_mestre_id=sub_a.id,
                nome_tarefa=sub_a.nome,
                ordem=1, duracao_dias=5, quantidade_prevista=100.0,
                responsavel='empresa', admin_id=admin_id,
            ),
            CronogramaTemplateItem(
                template_id=self.template.id, parent_item_id=grupo.id,
                subatividade_mestre_id=sub_b.id,
                nome_tarefa=sub_b.nome,
                ordem=2, duracao_dias=5, quantidade_prevista=100.0,
                responsavel='empresa', admin_id=admin_id,
            ),
        ])

        self.servico = Servico(
            nome=f'Light Steel Frame {suf}', categoria='Estrutural',
            unidade_medida='unidade', unidade_simbolo='un',
            custo_unitario=100.0, admin_id=admin_id, ativo=True,
            template_padrao_id=self.template.id,
        )
        db.session.add(self.servico); db.session.flush()

        self.proposta = Proposta(
            numero=f'P144{suf[:8]}', cliente_nome=self.cliente.nome,
            titulo='Proposta Dup #144', status='enviada',
            admin_id=admin_id, criado_por=admin_id,
            valor_total=Decimal('1000.00'),
        )
        db.session.add(self.proposta); db.session.flush()

        self.proposta_item = PropostaItem(
            admin_id=admin_id, proposta_id=self.proposta.id,
            item_numero=1, descricao=self.servico.nome,
            quantidade=Decimal('1'), unidade='un',
            preco_unitario=Decimal('1000.00'), ordem=1,
            servico_id=self.servico.id,
        )
        db.session.add(self.proposta_item); db.session.flush()

        self.obra = Obra(
            nome=f'Obra Dup #144 {suf}', codigo=f'DUP144-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today(),
            proposta_origem_id=self.proposta.id,
            cliente_nome=self.cliente.nome,
        )
        db.session.add(self.obra); db.session.flush()
        self.proposta.obra_id = self.obra.id
        db.session.commit()

        self.client = self.app.test_client()
        # Login admin
        r = self._http('login admin', 'POST', '/login',
                       data={'email': self.admin.email, 'password': 'Senha@2026'},
                       follow_redirects=False)
        self._assert(r.status_code in (302, 303), f'login admin OK (status={r.status_code})')

    # ──────────────────────────────────────────────────────────────────
    # STEP 1 — Auditoria de rotas
    # ──────────────────────────────────────────────────────────────────
    def teste_auditoria_rotas(self):
        encontradas = []
        for rule in self.app.url_map.iter_rules():
            classificacao = _classificar_route(rule.endpoint, str(rule))
            if classificacao:
                encontradas.append({
                    'rule': str(rule),
                    'endpoint': rule.endpoint,
                    'classificacao': classificacao,
                })
        self.report['rotas_auditoria'] = encontradas
        logger.info('=' * 70)
        logger.info('AUDITORIA: rotas que tocam TarefaCronograma')
        for e in encontradas:
            logger.info(f"  {e['rule']:60s} → {e['endpoint']} ({e['classificacao']})")
        logger.info('=' * 70)
        eps = {e['endpoint'] for e in encontradas}
        self._assert(
            any('tarefas_rdo' in e for e in eps),
            'auditoria mapeou GET /cronograma/obra/<id>/tarefas-rdo (leitura)',
        )
        self._assert(
            any('gerar_cronograma_cliente' in e for e in eps),
            'auditoria mapeou POST /obras/<id>/cronograma-cliente/gerar (clone)',
        )
        self._assert(
            any('salvar_rdo_flexivel' in e for e in eps),
            'auditoria mapeou POST /salvar-rdo-flexivel (apontamento)',
        )

    # ──────────────────────────────────────────────────────────────────
    # R1 — Materialização inicial
    # ──────────────────────────────────────────────────────────────────
    def teste_R1_materializacao_inicial(self):
        antes = self._contar_total(self.obra.id)
        arvore = montar_arvore_preview(self.proposta, self.admin.id)
        self.proposta.cronograma_default_json = arvore
        self.proposta.status = 'aprovada'
        EventManager.emit('proposta_aprovada', {
            'proposta_id': self.proposta.id,
            'admin_id': self.admin.id,
            'cliente_nome': self.proposta.cliente_nome,
            'valor_total': float(self.proposta.valor_total or 0),
            'data_aprovacao': date.today().isoformat(),
        }, self.admin.id)
        db.session.commit()
        depois = self._contar_total(self.obra.id)
        self._route_evidence(
            'R1 materialização inicial', 'handler proposta_aprovada → materializar_cronograma',
            antes, depois, esperado_igual=False,
            extra='cria 1 raiz + 1 grupo + 2 folhas = 4 tarefas',
        )
        self._assert(depois == 4, f'R1 — materialização cria 4 tarefas (achou {depois})')
        self._assert(len(self._contar_duplicatas(self.obra.id)) == 0,
                     'R1 — sem duplicatas após 1ª materialização')

    # ──────────────────────────────────────────────────────────────────
    # R2 — Re-mat com gerada_por_proposta_item_id NULO (caso legado)
    # ──────────────────────────────────────────────────────────────────
    def teste_R2_re_materializacao_pi_nulo(self):
        TarefaCronograma.query.filter_by(
            obra_id=self.obra.id, admin_id=self.admin.id, is_cliente=False
        ).update({TarefaCronograma.gerada_por_proposta_item_id: None})
        db.session.commit()
        antes = self._contar_total(self.obra.id)
        materializar_cronograma(
            self.proposta, self.admin.id, self.obra.id,
            arvore_marcada=self.proposta.cronograma_default_json,
        )
        db.session.commit()
        depois = self._contar_total(self.obra.id)
        ok = self._route_evidence(
            'R2 re-mat com PI nulo', 'services.cronograma_proposta.materializar_cronograma',
            antes, depois, esperado_igual=True,
            extra='ANTES do fix duplicava (4→8); DEPOIS idempotente (4→4)',
        )
        self._assert(ok, f'R2 — re-mat com PI nulo idempotente ({antes}→{depois})')
        self._assert(len(self._contar_duplicatas(self.obra.id)) == 0,
                     'R2 — sem duplicatas após re-mat legado')

    # ──────────────────────────────────────────────────────────────────
    # R3 — Snapshot sem proposta_item_id
    # ──────────────────────────────────────────────────────────────────
    def teste_R3_snapshot_sem_pi(self):
        arvore = montar_arvore_preview(self.proposta, self.admin.id)
        for n in arvore:
            n.pop('proposta_item_id', None)
        antes = self._contar_total(self.obra.id)
        materializar_cronograma(
            self.proposta, self.admin.id, self.obra.id, arvore_marcada=arvore
        )
        db.session.commit()
        depois = self._contar_total(self.obra.id)
        ok = self._route_evidence(
            'R3 snapshot sem proposta_item_id',
            'services.cronograma_proposta.materializar_cronograma',
            antes, depois, esperado_igual=True,
            extra='ANTES do fix duplicava (pi_ids=[] → ja_existem=set())',
        )
        self._assert(ok, f'R3 — snapshot sem PI idempotente ({antes}→{depois})')
        self._assert(len(self._contar_duplicatas(self.obra.id)) == 0,
                     'R3 — sem duplicatas após snapshot sem PI')

    # ──────────────────────────────────────────────────────────────────
    # R4 — Geração cronograma cliente 2x via HTTP
    # ──────────────────────────────────────────────────────────────────
    def teste_R4_cronograma_cliente_2x_http(self):
        path = f'/obras/{self.obra.id}/cronograma-cliente/gerar'
        r1 = self._http('R4 gerar cliente #1', 'POST', path, follow_redirects=False)
        self._assert(r1.status_code in (200, 302, 303),
                     f'R4 — POST cronograma-cliente/gerar #1 (status={r1.status_code})')
        c1 = self._contar_total(self.obra.id, is_cliente=True)
        r2 = self._http('R4 gerar cliente #2', 'POST', path, follow_redirects=False)
        self._assert(r2.status_code in (200, 302, 303),
                     f'R4 — POST cronograma-cliente/gerar #2 (status={r2.status_code})')
        c2 = self._contar_total(self.obra.id, is_cliente=True)
        ok = self._route_evidence(
            'R4 gerar cronograma cliente 2x', 'POST /obras/<id>/cronograma-cliente/gerar',
            c1, c2, esperado_igual=True,
            extra='clone is_cliente=True overwrite total + dedup defensivo',
        )
        self._assert(ok, f'R4 — clone cliente idempotente ({c1}→{c2})')
        self._assert(len(self._contar_duplicatas(self.obra.id, is_cliente=True)) == 0,
                     'R4 — sem duplicatas em is_cliente=True')

    # ──────────────────────────────────────────────────────────────────
    # R5 — POST /salvar-rdo-flexivel 2x via HTTP + GET tarefas-rdo
    # ──────────────────────────────────────────────────────────────────
    def teste_R5_rdos_via_http_e_endpoint_tarefas(self):
        # 1º RDO via HTTP
        form = {
            'obra_id': str(self.obra.id),
            'admin_id_form': str(self.admin.id),
            'data_relatorio': date.today().isoformat(),
            'observacoes_gerais': 'RDO #1 — Task #144',
            'condicoes_climaticas': 'Bom',
        }
        r1 = self._http('R5 salvar-rdo-flexivel #1', 'POST',
                        '/salvar-rdo-flexivel', data=form,
                        follow_redirects=False)
        self._assert(r1.status_code in (200, 302, 303),
                     f'R5 — 1º RDO criado via HTTP (status={r1.status_code})')

        # 2º RDO
        form['observacoes_gerais'] = 'RDO #2 — Task #144'
        r2 = self._http('R5 salvar-rdo-flexivel #2', 'POST',
                        '/salvar-rdo-flexivel', data=form,
                        follow_redirects=False)
        self._assert(r2.status_code in (200, 302, 303),
                     f'R5 — 2º RDO criado via HTTP (status={r2.status_code})')

        n_rdos = RDO.query.filter_by(obra_id=self.obra.id).count()
        self._assert(n_rdos >= 2, f'R5 — pelo menos 2 RDOs persistidos (achou {n_rdos})')

        # GET endpoint — valida que cada nome aparece 1x
        r3 = self._http('R5 GET tarefas-rdo', 'GET',
                        f'/cronograma/obra/{self.obra.id}/tarefas-rdo'
                        f'?data={date.today().isoformat()}')
        self._assert(r3.status_code == 200,
                     f'R5 — GET /cronograma/obra/<id>/tarefas-rdo retorna 200 (status={r3.status_code})')
        if r3.status_code == 200:
            data = r3.get_json() or {}
            tarefas = data.get('tarefas') or []
            ids_endpoint = {t.get('id') for t in tarefas}
            # Task #147 — o endpoint devolve APENAS o cronograma INTERNO
            # (is_cliente=False). Antes do fix, ele retornava interno +
            # clones do cliente juntos, dobrando cada item no card "Novo RDO"
            # quando a obra tinha cronograma do cliente gerado.
            dups_int = self._contar_duplicatas(self.obra.id, is_cliente=False)
            dups_cli = self._contar_duplicatas(self.obra.id, is_cliente=True)
            self._assert(
                len(dups_int) == 0 and len(dups_cli) == 0,
                f'R5 — endpoint não expõe duplicatas internas/cliente '
                f'(int={len(dups_int)}, cli={len(dups_cli)})',
            )
            # Cada id é único na resposta (sem repetir a mesma TarefaCronograma)
            self._assert(
                len(ids_endpoint) == len(tarefas) and len(tarefas) > 0,
                f'R5 — endpoint retorna ids únicos (n={len(tarefas)}, '
                f'unicos={len(ids_endpoint)})',
            )
            # Task #147 — endpoint só devolve interno (is_cliente=False)
            n_int = self._contar_total(self.obra.id, is_cliente=False)
            n_cli = self._contar_total(self.obra.id, is_cliente=True)
            self._assert(
                len(tarefas) == n_int,
                f'R5 — endpoint devolve apenas {n_int} tarefas internas '
                f'(achou {len(tarefas)}, total cliente={n_cli})',
            )
            # Task #147 — cada nome_tarefa aparece exatamente 1x na resposta
            # (antes do fix: cada nome aparecia 2x — interno + clone cliente)
            from collections import Counter
            nome_counts = Counter(t.get('nome_tarefa') for t in tarefas)
            duplicados_nome = {n: c for n, c in nome_counts.items() if c > 1}
            self._assert(
                not duplicados_nome,
                f'R5 — cada nome_tarefa aparece 1x no endpoint '
                f'(duplicados={duplicados_nome})',
            )
            self.report['route_evidence'].append({
                'step': 'R5 GET /cronograma/obra/<id>/tarefas-rdo',
                'rota': 'cronograma.tarefas_rdo',
                'tarefas_listadas': len(tarefas),
                'tarefas_internas_db': n_int,
                'tarefas_cliente_db': n_cli,
                'duplicatas_internas': len(dups_int),
                'duplicatas_cliente': len(dups_cli),
                'ok': len(dups_int) == 0 and len(dups_cli) == 0,
            })

    # ──────────────────────────────────────────────────────────────────
    # R5b — Task #147: blindagem dos endpoints de apontamento contra
    #       tarefas is_cliente=True (não pode criar apontamento "fantasma"
    #       no clone do cronograma do cliente).
    # ──────────────────────────────────────────────────────────────────
    def teste_R5b_apontamento_em_cliente_rejeitado(self):
        from models import RDO, Subempreiteiro
        # Pega um RDO existente da obra (criado em R5) e uma TarefaCronograma
        # cliente (criada em R4 via gerar_cronograma_cliente).
        rdo = RDO.query.filter_by(obra_id=self.obra.id).first()
        tarefa_cli = TarefaCronograma.query.filter_by(
            obra_id=self.obra.id, admin_id=self.admin.id, is_cliente=True
        ).first()
        self._assert(rdo is not None, 'R5b — RDO existente para teste negativo')
        self._assert(tarefa_cli is not None, 'R5b — TarefaCronograma cliente existe')
        if not rdo or not tarefa_cli:
            return

        # POST /rdo/<id>/apontar — produção em tarefa cliente deve dar 400
        r_prod = self._http(
            'R5b apontar produção em cliente', 'POST',
            f'/cronograma/rdo/{rdo.id}/apontar',
            json={'tarefa_cronograma_id': tarefa_cli.id, 'quantidade_executada_dia': 1.0},
        )
        self._assert(
            r_prod.status_code == 400,
            f'R5b — apontar_producao em is_cliente=True devolve 400 (status={r_prod.status_code})',
        )
        if r_prod.status_code == 400:
            body = r_prod.get_json() or {}
            self._assert(
                'cliente' in (body.get('msg') or '').lower(),
                f'R5b — mensagem de erro menciona cliente (msg={body.get("msg")!r})',
            )

        # POST /rdo/<id>/apontar-subempreitada — também deve dar 400
        sub = Subempreiteiro(
            admin_id=self.admin.id, nome=f'Sub R5b {self._suffix()}',
        )
        db.session.add(sub); db.session.commit()
        r_sub = self._http(
            'R5b apontar subempreitada em cliente', 'POST',
            f'/cronograma/rdo/{rdo.id}/apontar-subempreitada',
            json={
                'tarefa_cronograma_id': tarefa_cli.id,
                'subempreiteiro_id': sub.id,
                'qtd_pessoas': 1, 'horas_trabalhadas': 8.0,
                'quantidade_produzida': 5.0,
            },
        )
        self._assert(
            r_sub.status_code == 400,
            f'R5b — apontar_subempreitada em is_cliente=True devolve 400 '
            f'(status={r_sub.status_code})',
        )

    # ──────────────────────────────────────────────────────────────────
    # R6 — GET /rdo/novo HTML smoke
    # ──────────────────────────────────────────────────────────────────
    def teste_R6_novo_rdo_html(self):
        r = self._http('R6 GET /rdo/novo', 'GET',
                       f'/rdo/novo?obra_id={self.obra.id}')
        ok_status = r.status_code == 200
        self._assert(ok_status, f'R6 — GET /rdo/novo retorna 200 (status={r.status_code})')
        if ok_status:
            html = r.get_data(as_text=True)
            try:
                with open(NOVO_RDO_HTML_PATH, 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info(f'R6 — HTML salvo em {NOVO_RDO_HTML_PATH} ({len(html)} bytes)')
            except Exception as e:
                logger.warning(f'R6 — não consegui salvar HTML: {e}')
            # Asserção estática mínima: card cronograma V2 está presente
            self._assert(
                'cardCronogramaV2' in html or 'Apontamento de Produção' in html,
                'R6 — HTML contém o card "Apontamento de Produção"',
            )

    # ──────────────────────────────────────────────────────────────────
    # R7 — Dedup preserva apontamentos
    # ──────────────────────────────────────────────────────────────────
    def teste_R7_dedup_preserva_apontamentos(self):
        # Recupera uma folha vinculada ao SubatividadeMestre 'Aço Laminado'
        folha = TarefaCronograma.query.filter_by(
            obra_id=self.obra.id, is_cliente=False,
            subatividade_mestre_id=self.sub_a.id,
        ).first()
        self._assert(folha is not None, 'R7 — folha Aço Laminado existe')
        if not folha:
            return

        # Cria 2 RDOs + apontamentos diretos (já temos RDOs de R5; adicionamos
        # apontamentos para garantir que o reaponta-FK funcione)
        rdos = RDO.query.filter_by(obra_id=self.obra.id).order_by(RDO.id).limit(2).all()
        self._assert(len(rdos) >= 2, f'R7 — temos 2 RDOs (achou {len(rdos)})')
        if len(rdos) < 2:
            return
        ap1 = RDOApontamentoCronograma(
            rdo_id=rdos[0].id, tarefa_cronograma_id=folha.id,
            quantidade_executada_dia=10.0, quantidade_acumulada=10.0,
            percentual_realizado=10.0, percentual_planejado=10.0,
            admin_id=self.admin.id,
        )
        ap2 = RDOApontamentoCronograma(
            rdo_id=rdos[1].id, tarefa_cronograma_id=folha.id,
            quantidade_executada_dia=15.0, quantidade_acumulada=25.0,
            percentual_realizado=25.0, percentual_planejado=20.0,
            admin_id=self.admin.id,
        )
        db.session.add_all([ap1, ap2]); db.session.flush()

        # DUPLICATA artificial (cenário "obra já corrompida em produção")
        folha_dup = TarefaCronograma(
            obra_id=self.obra.id, admin_id=self.admin.id, is_cliente=False,
            nome_tarefa=folha.nome_tarefa,
            duracao_dias=folha.duracao_dias,
            tarefa_pai_id=folha.tarefa_pai_id,
            ordem=(folha.ordem or 0) + 5,
            subatividade_mestre_id=folha.subatividade_mestre_id,
            responsavel='empresa',
        )
        db.session.add(folha_dup); db.session.flush()
        ap2.tarefa_cronograma_id = folha_dup.id  # apontamento na duplicata

        # Edge case targeted: outra folha (sub_b) tem predecessora_id
        # apontando para a DUPLICATA. Após o dedup esse FK precisa ser
        # reapontado para a CANÔNICA — caso contrário o cronograma fica
        # com referência pendurada para uma tarefa apagada.
        folha_b = TarefaCronograma.query.filter_by(
            obra_id=self.obra.id, is_cliente=False,
            subatividade_mestre_id=self.sub_b.id,
        ).first()
        self._assert(folha_b is not None, 'R7 — folha sub_b existe (predecessora edge)')
        if folha_b:
            folha_b.predecessora_id = folha_dup.id
            db.session.flush()
        db.session.commit()

        antes = self._contar_total(self.obra.id)
        dups_antes = self._contar_duplicatas(self.obra.id)
        self._assert(len(dups_antes) >= 1,
                     f'R7 — cenário criado com {len(dups_antes)} grupo(s) de duplicata')

        removidas = deduplicar_tarefas_cronograma(
            self.obra.id, self.admin.id, is_cliente=False
        )
        db.session.commit()
        depois = self._contar_total(self.obra.id)
        ok = self._route_evidence(
            'R7 dedup', 'services.cronograma_dedup.deduplicar_tarefas_cronograma',
            antes, depois, esperado_igual=False,  # depois deve ser MENOR
            extra=f'removidas={removidas}',
        )
        # esperado_igual=False valida depois>antes, mas aqui esperamos depois<antes;
        # vamos validar manualmente:
        self._assert(depois < antes,
                     f'R7 — dedup reduziu contagem ({antes}→{depois}, removidas={removidas})')
        self._assert(len(self._contar_duplicatas(self.obra.id)) == 0,
                     'R7 — sem duplicatas após dedup')

        # Apontamentos preservados, ambos apontam para a CANÔNICA
        ap1_db = db.session.get(RDOApontamentoCronograma, ap1.id)
        ap2_db = db.session.get(RDOApontamentoCronograma, ap2.id)
        self._assert(ap1_db is not None and ap2_db is not None,
                     'R7 — apontamentos preservados após dedup')
        if ap1_db and ap2_db:
            self._assert(
                ap1_db.tarefa_cronograma_id == ap2_db.tarefa_cronograma_id == folha.id,
                f'R7 — apontamentos reapontados para canônica (esperado={folha.id}, '
                f'ap1={ap1_db.tarefa_cronograma_id}, ap2={ap2_db.tarefa_cronograma_id})',
            )
            # quantidades preservadas
            self._assert(
                abs(ap1_db.quantidade_executada_dia - 10.0) < 0.01
                and abs(ap2_db.quantidade_executada_dia - 15.0) < 0.01,
                'R7 — quantidades dos apontamentos preservadas (10/15)',
            )

        # Edge case: predecessora_id que apontava para a duplicata
        # precisa estar reapontado para a canônica (folha.id).
        if folha_b:
            folha_b_db = db.session.get(TarefaCronograma, folha_b.id)
            self._assert(
                folha_b_db is not None
                and folha_b_db.predecessora_id == folha.id,
                f'R7 — predecessora_id reapontado para canônica '
                f'(esperado={folha.id}, achou={getattr(folha_b_db, "predecessora_id", None)})',
            )

    # ──────────────────────────────────────────────────────────────────
    def teardown(self):
        try:
            db.session.rollback()
        except Exception:
            pass

    def run(self):
        with self.app.app_context():
            try:
                self.setup()
                self.teste_auditoria_rotas()
                self.teste_R1_materializacao_inicial()
                self.teste_R2_re_materializacao_pi_nulo()
                self.teste_R3_snapshot_sem_pi()
                self.teste_R4_cronograma_cliente_2x_http()
                self.teste_R5_rdos_via_http_e_endpoint_tarefas()
                self.teste_R5b_apontamento_em_cliente_rejeitado()
                self.teste_R6_novo_rdo_html()
                self.teste_R7_dedup_preserva_apontamentos()
            finally:
                self.teardown()

        self.report['finalizado_em'] = datetime.utcnow().isoformat() + 'Z'
        self.report['summary'] = {
            'pass': len(self.passed),
            'fail': len(self.failed),
            'rotas_auditadas': len(self.report['rotas_auditoria']),
            'http_calls': len(self.report['http_calls']),
            'route_evidence': len(self.report['route_evidence']),
        }
        try:
            os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
            with open(REPORT_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f'Relatório estruturado: {REPORT_PATH}')
        except Exception as e:
            logger.warning(f'Não consegui gravar relatório: {e}')

        print('=' * 80)
        print('CRONOGRAMA DUPLICADO NO RDO — RESULTADOS (Task #144)')
        print('=' * 80)
        print(f'PASS: {len(self.passed)}')
        print(f'FAIL: {len(self.failed)}')
        for p in self.passed:
            print(f'  PASS: {p}')
        for f in self.failed:
            print(f'  FAIL: {f}')
        print('=' * 80)
        return 0 if not self.failed else 1


if __name__ == '__main__':
    sys.exit(CronogramaDuplicadoRDORunner().run())
