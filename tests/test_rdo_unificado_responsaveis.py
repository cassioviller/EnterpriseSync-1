"""
Task #149 — E2E: lista unificada de tarefas no RDO (Empresa | Subempreitada | Terceiros).

Cobre via Flask test client (HTTP real) o fluxo do "Apontamento de Produção —
Cronograma" do NOVO RDO contemplando os 3 tipos de responsável:

  - Empresa:        cron_tarefa_<id>_func_<fid>_horas → RDOApontamentoCronograma
  - Subempreitada:  sub_apt_<i>_*                     → RDOSubempreitadaApontamento
  - Terceiros:      entrega_tarefa_ids[] +
                    terceiros_tarefa_ids_lista[]      → TarefaCronograma.percentual=100
                                                        + data_entrega_real preenchida

Cenários:
  S1. Setup: cria obra com 3 tarefas (uma de cada responsável) + 1 funcionário
      + 1 subempreiteiro.
  S2. POST /salvar-rdo-flexivel envia campos dos 3 tipos.
  S3. Asserções:
       a) RDO criado.
       b) RDOApontamentoCronograma criado para tarefa Empresa (>=1).
       c) RDOSubempreitadaApontamento criado para tarefa Sub (>=1).
       d) TarefaCronograma da terceiros tem percentual_realizado=100 e
          data_entrega_real preenchida.
  S4. Toggle reverso terceiros: 2º POST sem checkbox marcado mas com
      terceiros_tarefa_ids_lista[] presente → percentual volta a 0,
      data_entrega_real volta a None.

Executar com:
    python tests/test_rdo_unificado_responsaveis.py
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
    Usuario, TipoUsuario, Obra, Cliente, Funcionario, Departamento, HorarioTrabalho,
    TarefaCronograma, RDO, RDOApontamentoCronograma,
    RDOSubempreitadaApontamento, Subempreiteiro, SubatividadeMestre,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.local', 'rdo_unificado_responsaveis_report.json',
)


class RDOUnificadoRunner:
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.report = {
            'iniciado_em': datetime.utcnow().isoformat() + 'Z',
            'http_calls': [],
            'asserts': [],
            'evidencias': [],
        }
        self.client = None

    def _assert(self, cond, label, evidencia=None):
        (self.passed if cond else self.failed).append(label)
        self.report['asserts'].append({'label': label, 'ok': bool(cond)})
        if evidencia is not None:
            self.report['evidencias'].append({'label': label, 'evidencia': evidencia})
        (logger.info if cond else logger.error)(f"{'PASS' if cond else 'FAIL'}: {label}")

    def _http(self, step, method, path, **kw):
        m = getattr(self.client, method.lower())
        r = m(path, **kw)
        self.report['http_calls'].append({
            'step': step, 'method': method, 'path': path,
            'status': r.status_code,
            'ok': r.status_code in (200, 302, 303),
        })
        return r

    def _suffix(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    # ──────────────────────────────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────────────────────────────
    def setup(self):
        suf = self._suffix()
        self.admin = Usuario(
            username=f'rdo149_{suf}',
            email=f'rdo149_{suf}@test.local',
            nome='RDO 149 Admin',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(self.admin)
        db.session.flush()
        admin_id = self.admin.id

        # Departamento + Horário (FKs requeridas em Funcionario)
        depto = Departamento(nome=f'Obra {suf}', admin_id=admin_id)
        horario = HorarioTrabalho(
            nome=f'Padrão {suf}',
            entrada=datetime.strptime('07:00', '%H:%M').time(),
            saida_almoco=datetime.strptime('12:00', '%H:%M').time(),
            retorno_almoco=datetime.strptime('13:00', '%H:%M').time(),
            saida=datetime.strptime('17:00', '%H:%M').time(),
            dias_semana='1,2,3,4,5',
            horas_diarias=8.0,
            valor_hora=20.0,
            admin_id=admin_id,
        )
        db.session.add_all([depto, horario])
        db.session.flush()

        self.func = Funcionario(
            codigo=f'F{suf[:8]}',
            nome=f'Pedreiro Teste {suf}',
            cpf=suf[-11:],
            ativo=True,
            admin_id=admin_id,
            departamento_id=depto.id,
            horario_trabalho_id=horario.id,
            salario=2500.0,
            data_admissao=date.today(),
        )
        db.session.add(self.func)

        self.subempreiteiro = Subempreiteiro(
            nome=f'Sub Teste {suf}', cnpj=f'{suf[:14]}',
            especialidade='Estrutura', ativo=True, admin_id=admin_id,
        )
        db.session.add(self.subempreiteiro)

        self.cliente = Cliente(
            nome=f'Cliente Task149 {suf}',
            email=f'cli_task149_{suf[:6]}@example.com',
            admin_id=admin_id,
        )
        db.session.add(self.cliente)
        db.session.flush()

        self.obra = Obra(
            nome=f'Obra Task149 {suf}', codigo=f'T149-{suf[:6]}',
            admin_id=admin_id, status='Em andamento',
            data_inicio=date.today(),
            cliente_id=self.cliente.id,
        )
        db.session.add(self.obra)
        db.session.flush()

        sub_a = SubatividadeMestre(
            admin_id=admin_id, nome=f'Alvenaria {suf}', unidade_medida='m2'
        )
        sub_b = SubatividadeMestre(
            admin_id=admin_id, nome=f'Estrutura Met {suf}', unidade_medida='kg'
        )
        sub_c = SubatividadeMestre(
            admin_id=admin_id, nome=f'Esquadrias {suf}', unidade_medida='un'
        )
        db.session.add_all([sub_a, sub_b, sub_c])
        db.session.flush()

        # 3 tarefas — uma para cada responsável
        self.tarefa_emp = TarefaCronograma(
            obra_id=self.obra.id, admin_id=admin_id,
            nome_tarefa=f'Alvenaria interna {suf}',
            ordem=1, duracao_dias=10, quantidade_total=100.0,
            unidade_medida='m2', responsavel='empresa',
            subatividade_mestre_id=sub_a.id,
            data_inicio=date.today(),
        )
        self.tarefa_sub = TarefaCronograma(
            obra_id=self.obra.id, admin_id=admin_id,
            nome_tarefa=f'Estrutura metálica {suf}',
            ordem=2, duracao_dias=15, quantidade_total=500.0,
            unidade_medida='kg', responsavel='subempreitada',
            subatividade_mestre_id=sub_b.id,
            data_inicio=date.today(),
        )
        self.tarefa_terc = TarefaCronograma(
            obra_id=self.obra.id, admin_id=admin_id,
            nome_tarefa=f'Esquadrias de alumínio {suf}',
            ordem=3, duracao_dias=5, quantidade_total=20.0,
            unidade_medida='un', responsavel='terceiros',
            subatividade_mestre_id=sub_c.id,
            data_inicio=date.today(),
        )
        db.session.add_all([self.tarefa_emp, self.tarefa_sub, self.tarefa_terc])
        db.session.commit()

        self.client = self.app.test_client()
        r = self._http('login admin', 'POST', '/login',
                       data={'email': self.admin.email, 'password': 'Senha@2026'},
                       follow_redirects=False)
        self._assert(r.status_code in (302, 303),
                     f'login admin OK (status={r.status_code})')

    # ──────────────────────────────────────────────────────────────────
    # S2/S3 — POST inicial com 3 responsáveis
    # ──────────────────────────────────────────────────────────────────
    def teste_post_unificado_3_responsaveis(self):
        form = {
            'obra_id': str(self.obra.id),
            'admin_id_form': str(self.admin.id),
            'data_relatorio': date.today().isoformat(),
            'observacoes_gerais': 'RDO Task #149 — 3 tipos',
            'condicoes_climaticas': 'Bom',

            # Empresa: horas alocadas a 1 funcionário na tarefa Empresa
            f'cron_tarefa_{self.tarefa_emp.id}_func_{self.func.id}_horas': '4',
            # Quantidade executada hoje (empresa)
            f'cronograma_tarefa_{self.tarefa_emp.id}': '12.5',

            # Subempreitada: 1 apontamento em batch
            'sub_apt_0_tarefa_id': str(self.tarefa_sub.id),
            'sub_apt_0_subempreiteiro_id': str(self.subempreiteiro.id),
            'sub_apt_0_qtd_pessoas': '5',
            'sub_apt_0_horas': '8',
            'sub_apt_0_quantidade_produzida': '120',
            'sub_apt_0_observacoes': 'Equipe completa',

            # Terceiros: marca como concluído + lista para toggle reverso
            'entrega_tarefa_ids': [str(self.tarefa_terc.id)],
            'terceiros_tarefa_ids_lista': [str(self.tarefa_terc.id)],
        }
        r = self._http('S2 salvar-rdo-flexivel', 'POST',
                       '/salvar-rdo-flexivel', data=form,
                       follow_redirects=False)
        self._assert(r.status_code in (200, 302, 303),
                     f'S2 — POST salvar-rdo-flexivel (status={r.status_code})')

        rdo = (RDO.query
               .filter_by(obra_id=self.obra.id)
               .order_by(RDO.id.desc())
               .first())
        self._assert(rdo is not None, 'S3a — RDO criado para a obra',
                     evidencia={'rdo_id': rdo.id if rdo else None})

        # b) Apontamento empresa
        ap_emp = RDOApontamentoCronograma.query.filter_by(
            rdo_id=rdo.id, tarefa_cronograma_id=self.tarefa_emp.id
        ).all()
        total_q = sum(float(a.quantidade_executada_dia or 0) for a in ap_emp)
        self._assert(
            len(ap_emp) >= 1 and total_q > 0,
            f'S3b — RDOApontamentoCronograma criado p/ Empresa '
            f'(n={len(ap_emp)}, qtd={total_q})',
            evidencia=[{
                'id': a.id,
                'qtd_dia': float(a.quantidade_executada_dia or 0),
                'qtd_acum': float(a.quantidade_acumulada or 0),
                'perc_real': float(a.percentual_realizado or 0),
            } for a in ap_emp],
        )

        # c) Apontamento subempreitada
        ap_sub = RDOSubempreitadaApontamento.query.filter_by(
            rdo_id=rdo.id, tarefa_cronograma_id=self.tarefa_sub.id
        ).all()
        self._assert(
            len(ap_sub) >= 1,
            f'S3c — RDOSubempreitadaApontamento criado p/ Sub (n={len(ap_sub)})',
            evidencia=[{
                'id': a.id,
                'sub_id': a.subempreiteiro_id,
                'qtd_pessoas': a.qtd_pessoas,
                'horas': float(a.horas_trabalhadas or 0),
                'quantidade_produzida': float(a.quantidade_produzida or 0),
            } for a in ap_sub],
        )

        # d) Terceiros: percentual=100 e data_entrega_real preenchida
        db.session.refresh(self.tarefa_terc)
        perc = float(self.tarefa_terc.percentual_concluido or 0)
        data_real = self.tarefa_terc.data_entrega_real
        self._assert(
            perc >= 100 and data_real is not None,
            f'S3d — Terceiros marcado concluído '
            f'(percentual={perc}, data_entrega_real={data_real})',
            evidencia={'percentual': perc,
                       'data_entrega_real': str(data_real) if data_real else None},
        )

        self._rdo_id = rdo.id

    # ──────────────────────────────────────────────────────────────────
    # S4 — Toggle reverso terceiros (POST de novo RDO sem checkbox)
    # ──────────────────────────────────────────────────────────────────
    def teste_terceiros_toggle_reverso(self):
        form = {
            'obra_id': str(self.obra.id),
            'admin_id_form': str(self.admin.id),
            'data_relatorio': date.today().isoformat(),
            'observacoes_gerais': 'RDO Task #149 — toggle reverso',
            'condicoes_climaticas': 'Bom',
            # checkbox AUSENTE; lista informa que terceiros estava na tela
            'terceiros_tarefa_ids_lista': [str(self.tarefa_terc.id)],
        }
        r = self._http('S4 salvar-rdo-flexivel toggle reverso', 'POST',
                       '/salvar-rdo-flexivel', data=form,
                       follow_redirects=False)
        self._assert(r.status_code in (200, 302, 303),
                     f'S4 — POST toggle reverso (status={r.status_code})')

        db.session.refresh(self.tarefa_terc)
        perc = float(self.tarefa_terc.percentual_concluido or 0)
        data_real = self.tarefa_terc.data_entrega_real
        self._assert(
            perc == 0 and data_real is None,
            f'S4 — Terceiros revertido para pendente '
            f'(percentual={perc}, data_entrega_real={data_real})',
            evidencia={'percentual': perc,
                       'data_entrega_real': str(data_real) if data_real else None},
        )

    # ──────────────────────────────────────────────────────────────────
    # S5 — Task #150: editar e excluir apontamento de subempreitada via API
    # ──────────────────────────────────────────────────────────────────
    def teste_subempreitada_edit_delete(self):
        rdo_id = getattr(self, '_rdo_id', None)
        if not rdo_id:
            self._assert(False, 'S5 — RDO inexistente para teste de edição/exclusão sub')
            return

        # Lista inicial: deve ter ao menos 1 apontamento da etapa S2
        r = self._http('S5 listar apt sub', 'GET',
                       f'/cronograma/rdo/{rdo_id}/apontamentos-subempreitada')
        self._assert(r.status_code == 200,
                     f'S5a — GET apontamentos-subempreitada (status={r.status_code})')
        body = r.get_json() or {}
        apts = body.get('apontamentos', [])
        self._assert(len(apts) >= 1,
                     f'S5b — lista inicial contém apontamento (n={len(apts)})',
                     evidencia=apts)
        if not apts:
            return
        apt0 = apts[0]
        apt_id = apt0['id']

        # Editar (PUT-like via POST /apontar-subempreitada com id) — altera qtd_pessoas
        nova_qtd_pessoas = (apt0.get('qtd_pessoas') or 0) + 2
        novas_horas = 6.5
        nova_prod = 200.0
        r = self._http('S5 editar apt sub', 'POST',
                       f'/cronograma/rdo/{rdo_id}/apontar-subempreitada',
                       json={
                           'id': apt_id,
                           'tarefa_cronograma_id': self.tarefa_sub.id,
                           'subempreiteiro_id': self.subempreiteiro.id,
                           'qtd_pessoas': nova_qtd_pessoas,
                           'horas_trabalhadas': novas_horas,
                           'quantidade_produzida': nova_prod,
                           'observacoes': 'Editado via teste #150',
                       })
        self._assert(r.status_code == 200,
                     f'S5c — POST editar apontamento (status={r.status_code})')
        edited = (r.get_json() or {}).get('apontamento') or {}
        self._assert(
            edited.get('qtd_pessoas') == nova_qtd_pessoas
            and float(edited.get('horas_trabalhadas') or 0) == novas_horas
            and float(edited.get('quantidade_produzida') or 0) == nova_prod
            and (edited.get('observacoes') or '') == 'Editado via teste #150',
            'S5d — apontamento retornado reflete a edição',
            evidencia=edited,
        )

        # Releitura via GET — confere que persistiu no banco
        r = self._http('S5 relistar apt sub pós-edit', 'GET',
                       f'/cronograma/rdo/{rdo_id}/apontamentos-subempreitada')
        body = r.get_json() or {}
        apts_after_edit = body.get('apontamentos', [])
        match = next((a for a in apts_after_edit if a['id'] == apt_id), None)
        self._assert(
            match is not None
            and match.get('qtd_pessoas') == nova_qtd_pessoas
            and float(match.get('quantidade_produzida') or 0) == nova_prod,
            'S5e — releitura via GET confirma edição persistida',
            evidencia=match,
        )

        # Excluir (DELETE)
        r = self._http('S5 excluir apt sub', 'DELETE',
                       f'/cronograma/rdo/apontamento-subempreitada/{apt_id}')
        self._assert(r.status_code == 200,
                     f'S5f — DELETE apontamento (status={r.status_code})')

        # Releitura final: o id excluído não deve mais aparecer
        r = self._http('S5 relistar apt sub pós-delete', 'GET',
                       f'/cronograma/rdo/{rdo_id}/apontamentos-subempreitada')
        body = r.get_json() or {}
        apts_after_del = body.get('apontamentos', [])
        ids_apos = [a['id'] for a in apts_after_del]
        self._assert(
            apt_id not in ids_apos,
            f'S5g — apontamento {apt_id} não consta após DELETE (restantes={ids_apos})',
            evidencia=apts_after_del,
        )

    # ──────────────────────────────────────────────────────────────────
    def gravar_relatorio(self):
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        self.report['terminado_em'] = datetime.utcnow().isoformat() + 'Z'
        self.report['passed_count'] = len(self.passed)
        self.report['failed_count'] = len(self.failed)
        self.report['failed_labels'] = self.failed
        with open(REPORT_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False, default=str)

    def run(self):
        with self.app.app_context():
            try:
                self.setup()
                self.teste_post_unificado_3_responsaveis()
                self.teste_subempreitada_edit_delete()
                self.teste_terceiros_toggle_reverso()
            except Exception as e:
                logger.exception('Erro fatal no runner')
                self.failed.append(f'EXCEPTION: {e}')
            finally:
                self.gravar_relatorio()
                logger.info('=' * 70)
                logger.info(f'PASSED: {len(self.passed)}  FAILED: {len(self.failed)}')
                for lbl in self.failed:
                    logger.error(f'  FAIL: {lbl}')
                logger.info(f'Relatório: {REPORT_PATH}')
                logger.info('=' * 70)
        return 0 if not self.failed else 1


if __name__ == '__main__':
    sys.exit(RDOUnificadoRunner().run())
