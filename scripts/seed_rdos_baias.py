"""Popula a obra Baias Kabod (FF) com RDOs realistas até a data de hoje.

O que faz (idempotente, tenant-scoped):
  • cria 1 RDO por dia útil entre o início do cronograma e hoje, com mão de obra
    (todos os funcionários ativos × 8h) e clima;
  • para cada folha do cronograma INTERNO ativa no dia, grava um
    RDOApontamentoCronograma com o % realizado acumulado daquele dia — a última
    leitura por tarefa vira o % exibido no painel físico-financeiro (a view
    sincroniza percentual_concluido pelo último apontamento);
  • ajusta percentual_concluido das folhas do cronograma do CLIENTE (is_cliente=
    True) direto + rollup dos pais (o portal lê esse campo direto, sem RDO).

Uso:
    PYTHONPATH=/home/runner/workspace python3 scripts/seed_rdos_baias.py [admin_id] [obra_codigo] [data_hoje]
Defaults: admin_id=1  obra_codigo='10'  data_hoje=2026-06-26
"""
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (Obra, Funcionario, TarefaCronograma, ItemMedicaoCronogramaTarefa,
                    RDO, RDOMaoObra, RDOApontamentoCronograma)

CLIMAS = ['Ensolarado', 'Nublado', 'Ensolarado', 'Parcialmente nublado', 'Chuvoso']


def _dias_uteis(ini, fim):
    d = ini
    while d <= fim:
        if d.weekday() < 5:  # seg..sex
            yield d
        d += timedelta(days=1)


def _fator_realismo(tid):
    """Fator determinístico 0.85..1.00 por tarefa (obra ligeiramente atrasada)."""
    return 0.85 + (tid % 16) / 100.0


def _pct_no_dia(dia, ini, fim, tid):
    """% executado acumulado de uma folha na data `dia` (0..100)."""
    if not ini or not fim:
        return None
    if dia < ini:
        return 0.0
    if dia >= fim:
        return 100.0
    total = max((fim - ini).days, 1)
    frac = ((dia - ini).days + 1) / (total + 1)
    return round(min(100.0, frac * 100.0) * _fator_realismo(tid), 2)


def seed(admin_id=1, codigo='10', hoje=date(2026, 6, 26)):
    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if not obra:
        raise SystemExit(f'Obra codigo={codigo} admin={admin_id} não encontrada')

    funcs = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).all()
    if not funcs:
        raise SystemExit('Nenhum funcionário ativo no tenant — RDO precisa de mão de obra')

    # Folhas do cronograma INTERNO ligadas a IMC (são as apontáveis)
    vinc_ids = {v.cronograma_tarefa_id for v in
                ItemMedicaoCronogramaTarefa.query.filter_by(admin_id=admin_id).all()}
    folhas_int = (TarefaCronograma.query
                  .filter_by(obra_id=obra.id, admin_id=admin_id, is_cliente=False)
                  .filter(TarefaCronograma.id.in_(vinc_ids))
                  .all())

    # Janela: do início da 1ª folha até hoje
    inicios = [f.data_inicio for f in folhas_int if f.data_inicio]
    ini_obra = min(inicios) if inicios else obra.data_inicio or hoje
    dias = list(_dias_uteis(ini_obra, hoje))

    # ── Idempotência: apaga RDOs anteriores desta obra (cascata limpa filhos) ──
    antigos = RDO.query.filter_by(obra_id=obra.id, admin_id=admin_id).all()
    for r in antigos:
        db.session.delete(r)
    db.session.flush()

    # ── Cria RDOs dia a dia ────────────────────────────────────────────────
    seq = 0
    for dia in dias:
        seq += 1
        rdo = RDO(
            numero_rdo=f'RDO-{admin_id}-{obra.id}-{dia.strftime("%Y%m%d")}',
            obra_id=obra.id, admin_id=admin_id, criado_por_id=admin_id,
            data_relatorio=dia, local='Campo', status='Finalizado',
            clima_geral=CLIMAS[seq % len(CLIMAS)],
            temperatura_media='26°C', condicoes_trabalho='Adequadas',
            precipitacao='Sem chuva' if CLIMAS[seq % len(CLIMAS)] != 'Chuvoso' else 'Chuva fraca',
            observacoes_climaticas='Condições normais de trabalho.',
            comentario_geral=f'Frente de serviço ativa — {obra.nome} ({dia.strftime("%d/%m/%Y")}).',
        )
        db.session.add(rdo)
        db.session.flush()

        for f in funcs:
            funcao_nome = getattr(getattr(f, 'funcao_ref', None), 'nome', None) \
                or getattr(f, 'funcao', None) or 'Operário'
            db.session.add(RDOMaoObra(
                rdo_id=rdo.id, admin_id=admin_id, funcionario_id=f.id,
                funcao_exercida=str(funcao_nome)[:100], horas_trabalhadas=8.0))

        for t in folhas_int:
            if not t.data_inicio or t.data_inicio > dia:
                continue
            pct_hoje = _pct_no_dia(dia, t.data_inicio, t.data_fim, t.id)
            pct_ontem = _pct_no_dia(dia - timedelta(days=1), t.data_inicio, t.data_fim, t.id)
            if pct_hoje is None or pct_hoje == 0.0:
                continue
            delta = max(0.0, round(pct_hoje - (pct_ontem or 0.0), 2))
            total_dias = max((t.data_fim - t.data_inicio).days, 1) if t.data_fim else 1
            planejado = min(100.0, round(((dia - t.data_inicio).days + 1) / (total_dias + 1) * 100, 2))
            db.session.add(RDOApontamentoCronograma(
                rdo_id=rdo.id, tarefa_cronograma_id=t.id, admin_id=admin_id,
                quantidade_executada_dia=delta, quantidade_acumulada=pct_hoje,
                percentual_realizado=pct_hoje, percentual_planejado=planejado))

    # ── % das folhas do CLIENTE (portal lê direto) + rollup dos pais ───────
    cliente = (TarefaCronograma.query
               .filter_by(obra_id=obra.id, admin_id=admin_id, is_cliente=True).all())
    by_id = {t.id: t for t in cliente}
    for t in cliente:
        if t.tarefa_pai_id is None:
            continue  # folha
        if by_id.get(t.id) and any(c.tarefa_pai_id == t.id for c in cliente):
            continue  # é pai, calcula depois
        p = _pct_no_dia(hoje, t.data_inicio, t.data_fim, t.id)
        if p is not None:
            t.percentual_concluido = p
    # rollup pais (média ponderada por duração)
    for pai in sorted([t for t in cliente if any(c.tarefa_pai_id == t.id for c in cliente)],
                      key=lambda t: (t.ordem or 0), reverse=True):
        filhas = [c for c in cliente if c.tarefa_pai_id == pai.id]
        tot = sum(max(c.duracao_dias or 1, 1) for c in filhas) or 1
        pai.percentual_concluido = round(
            sum((c.percentual_concluido or 0) * max(c.duracao_dias or 1, 1) for c in filhas) / tot, 2)

    db.session.commit()

    n_rdos = RDO.query.filter_by(obra_id=obra.id, admin_id=admin_id).count()
    n_ap = RDOApontamentoCronograma.query.filter_by(admin_id=admin_id).count()
    return {'obra_id': obra.id, 'rdos': n_rdos, 'apontamentos': n_ap,
            'dias': len(dias), 'janela': (ini_obra.isoformat(), hoje.isoformat())}


if __name__ == '__main__':
    aid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cod = sys.argv[2] if len(sys.argv) > 2 else '10'
    hj = datetime.fromisoformat(sys.argv[3]).date() if len(sys.argv) > 3 else date(2026, 6, 26)
    with app.app_context():
        r = seed(aid, cod, hj)
    print(f"[seed_rdos_baias] obra_id={r['obra_id']}  janela={r['janela']}  "
          f"dias_uteis={r['dias']}")
    print(f"  RDOs criados: {r['rdos']}  |  apontamentos de cronograma: {r['apontamentos']}")
