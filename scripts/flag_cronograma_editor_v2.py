#!/usr/bin/env python3
"""Flag de rollout do editor de cronograma v2 por tenant (Fase 1).

O motor de agendamento novo (multi-predecessoras via `tarefa_vinculo`,
caminho crítico, recálculo em cascata) só liga para tenant V2 **com**
`configuracao_empresa.cronograma_editor_v2 = TRUE` (migração 222). Com a
flag desligada, cada rota do cronograma executa exatamente o código antigo.
Este é o instrumento do rollout: liga primeiro no tenant de homologação,
depois na obra piloto, por último no geral.

⚠️ **03/08/2026 — o "por último no geral" já aconteceu.** A migração 277
ligou a flag em TODOS os tenants (congelando a linha de base antes, como o
passo 4 do runbook manda) e virou o default da coluna para TRUE. Este script
deixou de ser o caminho de ligar e passou a ser o de **excluir alguém**:

    python scripts/flag_cronograma_editor_v2.py <admin_id> --desligar

O `--ligar` segue valendo para religar um excluído ou para ambiente novo — e
seus dois guards (calendário de fim de semana, linha de base ausente)
continuam intactos, porque é neles que o risco está escrito. Ver
`docs/cronograma-editor-v2-rollout.md`.

Uso (CLI):
    python scripts/flag_cronograma_editor_v2.py <admin_id> --status
    python scripts/flag_cronograma_editor_v2.py <admin_id> --ligar
    python scripts/flag_cronograma_editor_v2.py <admin_id> --desligar

Como módulo (testes/rollout):
    from scripts.flag_cronograma_editor_v2 import definir_flag, status_flag

Nota: o motor novo usa calendário FIXO seg–sex nesta fase — ao ligar a
flag num tenant cujo `CalendarioEmpresa` considera sábado/domingo, o
recálculo passa a ignorar essa configuração (aviso emitido pelo CLI).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _config_do_tenant(admin_id: int, criar: bool = False):
    """Devolve a ConfiguracaoEmpresa do tenant (criando o mínimo se pedido)."""
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config or not criar:
        return config

    admin = db.session.get(Usuario, admin_id)
    nome = getattr(admin, 'nome', None) or f'Empresa {admin_id}'
    config = ConfiguracaoEmpresa(admin_id=admin_id, nome_empresa=nome)
    db.session.add(config)
    db.session.flush()
    return config


def definir_flag(admin_id: int, ativo: bool) -> bool:
    """Liga/desliga a flag do tenant. Cria a configuração se não existir.

    Requer app_context. Devolve o estado gravado.
    """
    from app import db

    config = _config_do_tenant(admin_id, criar=True)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()
    return bool(config.cronograma_editor_v2)


def status_flag(admin_id: int) -> dict:
    """Estado da flag do tenant (sem escrever). Requer app_context."""
    from models import Usuario
    from app import db

    admin = db.session.get(Usuario, admin_id)
    config = _config_do_tenant(admin_id)
    return {
        'admin_id': admin_id,
        'admin_existe': admin is not None,
        'versao_sistema': getattr(admin, 'versao_sistema', None),
        'tem_configuracao': config is not None,
        'cronograma_editor_v2': bool(config and config.cronograma_editor_v2),
    }


def calendario_diverge(admin_id: int) -> bool:
    """True se o CalendarioEmpresa do tenant considera sábado ou domingo.

    O motor novo é seg–sex fixo nesta fase — nesse caso ligar a flag muda o
    calendário efetivo do recálculo. Requer app_context; nunca levanta.
    """
    try:
        from models import CalendarioEmpresa
        cal = CalendarioEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cal and (cal.considerar_sabado or cal.considerar_domingo))
    except Exception:
        return False


def obras_sem_linha_de_base(admin_id: int) -> list:
    """Obras do tenant com cronograma datado e SEM linha de base ativa.

    O rollback desta flag é assimétrico: desligar devolve o motor antigo, mas
    **não desfaz as datas que o motor novo já gravou** — o recálculo em
    cascata reescreve `data_inicio`/`data_fim` das tarefas, e não há de onde
    trazê-las de volta. A `CronogramaBaseline` é esse "de onde": congela as
    datas de hoje por tarefa (migração 225) e é o único registro que
    sobrevive ao recálculo.

    Por isso o runbook mandava tirar snapshot antes — instrução que ninguém
    conseguia verificar. Aqui ela vira condição do `--ligar`.

    Só entram obras com tarefa ativa e datada: sem datas não há o que
    congelar, e o recálculo também não tem o que reescrever. Requer
    app_context; nunca levanta.
    """
    try:
        from models import CronogramaBaseline, Obra, TarefaCronograma
        from app import db

        com_datas = (
            db.session.query(TarefaCronograma.obra_id,
                             db.func.count(TarefaCronograma.id))
            .filter(TarefaCronograma.admin_id == admin_id,
                    TarefaCronograma.ativa.is_(True),
                    TarefaCronograma.data_inicio.isnot(None),
                    TarefaCronograma.data_fim.isnot(None))
            .group_by(TarefaCronograma.obra_id)
            .all()
        )
        if not com_datas:
            return []
        protegidas = {
            oid for (oid,) in
            db.session.query(CronogramaBaseline.obra_id)
            .filter(CronogramaBaseline.admin_id == admin_id,
                    CronogramaBaseline.ativa.is_(True))
            .distinct()
        }
        pendentes = []
        for obra_id, n_tarefas in com_datas:
            if obra_id in protegidas:
                continue
            obra = db.session.get(Obra, obra_id)
            pendentes.append({
                'obra_id': obra_id,
                'nome': getattr(obra, 'nome', None) or f'obra {obra_id}',
                'tarefas': int(n_tarefas),
            })
        return sorted(pendentes, key=lambda o: -o['tarefas'])
    except Exception as e:  # pragma: no cover - defensivo, igual às irmãs
        print(f'AVISO: não foi possível conferir as linhas de base ({e})')
        return []


def criar_linha_de_base(obra_id: int, admin_id: int, nome=None) -> int:
    """Congela as datas atuais da obra numa `CronogramaBaseline` ATIVA.

    Mesmo conteúdo que a rota `POST /cronograma/obra/<id>/baseline` grava
    (cronograma_views.py) — repetido aqui porque o rollout roda por CLI, sem
    request nem `current_user`. Devolve o nº de tarefas congeladas.

    Só o cronograma INTERNO (`is_cliente=False`): é o que o motor novo
    recalcula. Requer app_context.
    """
    from datetime import date

    from models import CronogramaBaseline, CronogramaBaselineItem, TarefaCronograma
    from app import db

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .filter(TarefaCronograma.ativa.is_(True))
        .filter(TarefaCronograma.data_inicio.isnot(None))
        .filter(TarefaCronograma.data_fim.isnot(None))
        .all()
    )
    if not tarefas:
        return 0

    (CronogramaBaseline.query
     .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False, ativa=True)
     .update({'ativa': False}, synchronize_session=False))

    baseline = CronogramaBaseline(
        obra_id=obra_id, admin_id=admin_id, is_cliente=False, ativa=True,
        nome=(nome or f"Antes do editor v2 — {date.today().strftime('%d/%m/%Y')}")[:120])
    db.session.add(baseline)
    db.session.flush()
    for t in tarefas:
        db.session.add(CronogramaBaselineItem(
            baseline_id=baseline.id, tarefa_id=t.id, admin_id=admin_id,
            data_inicio=t.data_inicio, data_fim=t.data_fim,
            duracao_dias=t.duracao_dias))
    db.session.commit()
    return len(tarefas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Flag de rollout do editor de cronograma v2 (Fase 1)')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    grupo.add_argument('--status', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo com calendário divergente ou sem '
                             'linha de base')
    parser.add_argument('--criar-baseline', action='store_true',
                        help='congela as datas atuais das obras que ainda não '
                             'têm linha de base ativa (o snapshot que o '
                             'rollback do motor NÃO faz sozinho)')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        estado = status_flag(args.admin_id)
        if not estado['admin_existe']:
            print(f"admin_id {args.admin_id} não existe")
            return 1

        # Guard ANTES de gravar: a versão anterior chamava `definir_flag`
        # primeiro e só depois avisava — quem lesse o aviso já estaria com o
        # motor novo ligado, e o recálculo já teria outro calendário.
        diverge = args.ligar and calendario_diverge(args.admin_id)
        if diverge and not args.forcar:
            print(f'ABORTADO: o CalendarioEmpresa do tenant {args.admin_id} '
                  f'considera sábado e/ou domingo, mas o motor novo usa '
                  f'calendário fixo seg–sex nesta fase.')
            print('Ligar agora faria o recálculo IGNORAR essa configuração e '
                  'mover as datas do cronograma. Ajuste o calendário do '
                  'tenant, ou use --forcar se a mudança de datas for '
                  'aceitável. Desligar a flag reverte o motor, mas NÃO '
                  'desfaz um recálculo já aplicado.')
            return 1

        if args.criar_baseline:
            pendentes = obras_sem_linha_de_base(args.admin_id)
            if not pendentes:
                print('Nada a congelar: toda obra com cronograma datado já '
                      'tem linha de base ativa.')
            for obra in pendentes:
                n = criar_linha_de_base(obra['obra_id'], args.admin_id)
                print(f"  linha de base criada — obra {obra['obra_id']} "
                      f"({obra['nome']}): {n} tarefa(s) congelada(s)")

        # Segundo guard ANTES de gravar: sem linha de base, ligar a flag é
        # uma porta só de ida. O motor novo recalcula as datas em cascata e
        # desligar a flag devolve o motor, não as datas.
        if args.ligar and not args.forcar:
            pendentes = obras_sem_linha_de_base(args.admin_id)
            if pendentes:
                print(f'ABORTADO: {len(pendentes)} obra(s) do tenant '
                      f'{args.admin_id} têm cronograma datado e NENHUMA linha '
                      f'de base ativa:')
                for obra in pendentes[:10]:
                    print(f"  - obra {obra['obra_id']} ({obra['nome']}): "
                          f"{obra['tarefas']} tarefa(s) com datas")
                if len(pendentes) > 10:
                    print(f'  … e mais {len(pendentes) - 10}.')
                print('O motor novo recalcula datas em cascata, e DESLIGAR A '
                      'FLAG NÃO AS DEVOLVE — a linha de base é o único '
                      'registro do plano de hoje que sobrevive a isso.')
                print(f'Congele antes:  python {os.path.basename(__file__)} '
                      f'{args.admin_id} --criar-baseline --status')
                print('Ou use --forcar se perder o plano atual for aceitável.')
                return 1

        if not args.status:
            definir_flag(args.admin_id, args.ligar)
            estado = status_flag(args.admin_id)

    print(f"admin_id={estado['admin_id']} "
          f"versao_sistema={estado['versao_sistema']} "
          f"cronograma_editor_v2={estado['cronograma_editor_v2']}")
    if estado['cronograma_editor_v2'] and estado['versao_sistema'] != 'v2':
        print("AVISO: flag ligada mas o tenant não é V2 — o motor novo segue inativo.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
