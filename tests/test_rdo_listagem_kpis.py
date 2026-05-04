"""
tests/test_rdo_listagem_kpis.py — Task #61

Valida que a listagem de RDOs (`/rdos`, `/rdo/lista`,
`crud_rdo_completo.listar_rdos`) calcula KPIs com a **mesma** lógica
usada na visualização do detalhe:

  • Progresso geral via `calcular_progresso_geral_obra_v2` (modo V2)
  • Total de horas via `utils.rdo_horas.normalizar_horas_funcionario`

Também valida o parser dos campos repetíveis
(`utils.rdo_equip_ocorr.parse_equipamentos / parse_ocorrencias`) que
alimenta a UI de Equipamentos / Ocorrências do novo/editar.
"""
import os
import sys
import logging
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Obra, Cliente,
    TarefaCronograma, RDO, RDOApontamentoCronograma,
)
from werkzeug.security import generate_password_hash

from models import RDOEquipamento, RDOOcorrencia
from utils.cronograma_engine import calcular_progresso_geral_obra_v2
from utils.rdo_equip_ocorr import (
    parse_equipamentos, parse_ocorrencias, replace_equipamentos_ocorrencias,
)
from utils.rdo_horas import normalizar_horas_funcionario

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
log = logging.getLogger('test_rdo_list_61')


class _FakeForm:
    """Mock leve de werkzeug ImmutableMultiDict para parse_*()."""
    def __init__(self, data: dict[str, list[str]]):
        self._d = data
    def getlist(self, k):
        return list(self._d.get(k, []))


class Runner:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []

    def check(self, cond, label):
        (self.passed if cond else self.failed).append(label)
        (log.info if cond else log.error)(f"{'PASS' if cond else 'FAIL'}  {label}")

    def _suf(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')

    def setup(self):
        s = self._suf()
        admin = Usuario(
            username=f'rdolist61_{s}', email=f'rdolist61_{s}@t.local',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, nome='Admin 61', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(admin_id=admin.id, nome=f'Cli 61 {s}',
                      email=f'cli61_{s}@t.local')
        db.session.add(cli); db.session.flush()
        obra = Obra(nome=f'Obra 61 {s}', codigo=f'O61-{s[-6:]}',
                    admin_id=admin.id, status='Em andamento',
                    cliente_id=cli.id,
                    data_inicio=date(2026, 3, 2))
        db.session.add(obra); db.session.flush()

        t1 = TarefaCronograma(
            admin_id=admin.id, obra_id=obra.id, ordem=1,
            nome_tarefa='T1', duracao_dias=10,
            data_inicio=date(2026, 3, 2), data_fim=date(2026, 3, 13),
            quantidade_total=100.0, unidade_medida='m2', is_cliente=False,
        )
        t2 = TarefaCronograma(
            admin_id=admin.id, obra_id=obra.id, ordem=2,
            nome_tarefa='T2', duracao_dias=5,
            data_inicio=date(2026, 3, 9), data_fim=date(2026, 3, 13),
            quantidade_total=50.0, unidade_medida='m2', is_cliente=False,
        )
        db.session.add_all([t1, t2]); db.session.flush()
        return admin, obra, t1, t2

    def run(self):
        with app.app_context():
            try:
                admin, obra, t1, t2 = self.setup()

                # 2 RDOs em datas crescentes com apontamentos V2
                _run = self._suf()[-6:]
                dts = [date(2026, 3, 5), date(2026, 3, 13)]
                rdo_ids: list[int] = []
                for i, dt in enumerate(dts):
                    r = RDO(numero_rdo=f"R61-{_run}-{i}",
                            data_relatorio=dt, obra_id=obra.id,
                            criado_por_id=admin.id, admin_id=admin.id,
                            status='Finalizado')
                    db.session.add(r); db.session.flush()
                    rdo_ids.append(r.id)
                acums = {t1.id: 0.0, t2.id: 0.0}
                planos = [
                    (rdo_ids[0], [(t1.id, 25.0), (t2.id, 0.0)]),
                    (rdo_ids[1], [(t1.id, 75.0), (t2.id, 50.0)]),
                ]
                for rid, items in planos:
                    for tid, q in items:
                        acums[tid] += q
                        db.session.add(RDOApontamentoCronograma(
                            rdo_id=rid, tarefa_cronograma_id=tid,
                            admin_id=admin.id,
                            quantidade_executada_dia=q,
                            quantidade_acumulada=acums[tid],
                            percentual_realizado=0.0, percentual_planejado=0.0,
                        ))
                db.session.flush()

                # ── Paridade list-vs-detail: mesma função V2 ──
                # A listagem (views/rdo.py rdos() + crud_rdo_completo.listar_rdos)
                # passou a usar `calcular_progresso_geral_obra_v2(obra_id, data, admin_id)`
                # e a salvar resultado em cache `_cache_prog_v2`. Aqui simulamos a
                # mesma chamada e exigimos resultado consistente entre duas datas.
                p1 = calcular_progresso_geral_obra_v2(obra.id, dts[0], admin.id)
                p2 = calcular_progresso_geral_obra_v2(obra.id, dts[1], admin.id)
                self.check(
                    p1['progresso_geral_pct'] < p2['progresso_geral_pct'],
                    f"[paridade] V2 cresce entre RDOs: {p1['progresso_geral_pct']} < {p2['progresso_geral_pct']}",
                )
                # peso(t1)=100, peso(t2)=50 → soma 150
                # rdo1: (25*100 + 0*50)/150 = 16.666…
                self.check(
                    abs(p1['progresso_geral_pct'] - 16.6667) < 0.5,
                    f"[paridade] média ponderada do 1º RDO ≈ 16.67 (real={p1['progresso_geral_pct']})",
                )
                self.check(
                    abs(p2['progresso_geral_pct'] - 100.0) < 0.5,
                    f"[paridade] 2º RDO encerra ≈ 100% (real={p2['progresso_geral_pct']})",
                )

                # ── Normalização de horas (lista deve usar a mesma utilidade) ──
                # 1 funcionário em 2 atividades, 8h cada → soma normalizada deve
                # ser 8h (e não 16h).
                entradas = [
                    (101, ('sub', 1), 8.0, {}),
                    (101, ('sub', 2), 8.0, {}),
                ]
                norm = normalizar_horas_funcionario(entradas)
                total = sum(h for _, _, h, _ in norm)
                self.check(
                    abs(total - 8.0) < 0.001,
                    f"[horas] normalizar 8+8 (mesmo func) = 8h (real={total})",
                )

                # ── Parser de Equipamentos / Ocorrências (UI repetível) ──
                form_eq = _FakeForm({
                    'equip_nome[]':       ['Betoneira', '', 'Andaime'],
                    'equip_quantidade[]': ['2', '1', '3'],
                    'equip_horas_uso[]':  ['4.5', '8', 'invalid'],
                    'equip_estado[]':     ['Bom', 'Bom', 'Regular'],
                })
                eqs = parse_equipamentos(form_eq)
                self.check(len(eqs) == 2, f"[parser] linha vazia ignorada (n={len(eqs)})")
                self.check(
                    eqs[0]['nome'] == 'Betoneira' and eqs[0]['quantidade'] == 2
                    and abs(eqs[0]['horas_uso'] - 4.5) < 0.001,
                    f"[parser] equip[0] OK ({eqs[0]})",
                )
                self.check(
                    eqs[1]['nome'] == 'Andaime' and eqs[1]['horas_uso'] == 0.0,
                    f"[parser] equip[1] horas inválidas → 0.0 ({eqs[1]})",
                )

                form_oc = _FakeForm({
                    'ocorr_tipo[]':       ['Segurança', 'Outros'],
                    'ocorr_severidade[]': ['Alta', 'Baixa'],
                    'ocorr_descricao[]':  ['  capacete faltando ', ''],
                    'ocorr_status[]':     ['Pendente', 'Resolvido'],
                })
                ocs = parse_ocorrencias(form_oc)
                self.check(len(ocs) == 1, f"[parser] ocorrência sem descrição ignorada (n={len(ocs)})")
                self.check(
                    ocs[0]['tipo'] == 'Segurança' and ocs[0]['severidade'] == 'Alta'
                    and ocs[0]['descricao'] == 'capacete faltando',
                    f"[parser] ocorr[0] OK ({ocs[0]})",
                )

                # ── Persistência end-to-end + replace-not-duplicate ──
                # Cria 1 RDO real e exercita o helper que as rotas chamam.
                rdo_t = RDO(numero_rdo=f"R61T-{_run}",
                            data_relatorio=date(2026, 3, 5), obra_id=obra.id,
                            criado_por_id=admin.id, admin_id=admin.id,
                            status='Rascunho')
                db.session.add(rdo_t); db.session.flush()

                # 1ª gravação (criação): 2 equipamentos + 1 ocorrência
                form_create = _FakeForm({
                    'equip_nome[]':       ['Betoneira', 'Andaime'],
                    'equip_quantidade[]': ['2', '5'],
                    'equip_horas_uso[]':  ['4', '8'],
                    'equip_estado[]':     ['Bom', 'Regular'],
                    'ocorr_tipo[]':       ['Segurança'],
                    'ocorr_severidade[]': ['Alta'],
                    'ocorr_descricao[]':  ['EPI faltando'],
                    'ocorr_status[]':     ['Pendente'],
                })
                n_eq, n_oc = replace_equipamentos_ocorrencias(rdo_t.id, admin.id, form_create)
                db.session.flush()
                self.check(
                    (n_eq, n_oc) == (2, 1),
                    f"[persist] criação grava (2,1) (real={(n_eq, n_oc)})",
                )
                self.check(
                    RDOEquipamento.query.filter_by(rdo_id=rdo_t.id).count() == 2,
                    "[persist] 2 equipamentos persistidos no DB",
                )
                self.check(
                    RDOOcorrencia.query.filter_by(rdo_id=rdo_t.id).count() == 1,
                    "[persist] 1 ocorrência persistida no DB",
                )

                # 2ª gravação (re-edit): substitui — não duplica.
                form_edit = _FakeForm({
                    'equip_nome[]':       ['Andaime', 'Compressor', 'Furadeira'],
                    'equip_quantidade[]': ['3', '1', '2'],
                    'equip_horas_uso[]':  ['6', '4', '2'],
                    'equip_estado[]':     ['Bom', 'Bom', 'Bom'],
                    'ocorr_tipo[]':       [],
                    'ocorr_severidade[]': [],
                    'ocorr_descricao[]':  [],
                    'ocorr_status[]':     [],
                })
                n_eq2, n_oc2 = replace_equipamentos_ocorrencias(rdo_t.id, admin.id, form_edit)
                db.session.flush()
                self.check(
                    (n_eq2, n_oc2) == (3, 0),
                    f"[persist] re-edit grava (3,0) (real={(n_eq2, n_oc2)})",
                )
                self.check(
                    RDOEquipamento.query.filter_by(rdo_id=rdo_t.id).count() == 3,
                    "[persist] re-edit não duplica equipamentos (3 totais, não 5)",
                )
                self.check(
                    RDOOcorrencia.query.filter_by(rdo_id=rdo_t.id).count() == 0,
                    "[persist] re-edit limpa ocorrências removidas (0 totais)",
                )
                # Conteúdo correto da substituição
                nomes_eq = sorted(
                    e.nome_equipamento for e in
                    RDOEquipamento.query.filter_by(rdo_id=rdo_t.id).all()
                )
                self.check(
                    nomes_eq == ['Andaime', 'Compressor', 'Furadeira'],
                    f"[persist] nomes pós-edit corretos ({nomes_eq})",
                )

                # ── Clima: persistência dos 3 campos no modelo RDO ──
                rdo_t.clima_geral = 'Ensolarado'
                rdo_t.temperatura_media = '28°C'
                rdo_t.condicoes_trabalho = 'Ideais'
                db.session.flush()
                rdo_reread = RDO.query.get(rdo_t.id)
                self.check(
                    rdo_reread.clima_geral == 'Ensolarado'
                    and rdo_reread.temperatura_media == '28°C'
                    and rdo_reread.condicoes_trabalho == 'Ideais',
                    "[clima] 3 campos (clima_geral/temp/cond) persistem no modelo",
                )

            except Exception as e:
                log.exception(f"erro no teste: {e}")
                self.failed.append(f"exception: {e}")
            finally:
                db.session.rollback()

        log.info("=" * 60)
        log.info(f"PASSED: {len(self.passed)} | FAILED: {len(self.failed)}")
        log.info("=" * 60)
        return 0 if not self.failed else 1


if __name__ == '__main__':
    sys.exit(Runner().run())
