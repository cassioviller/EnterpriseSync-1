"""Guard de rollout da flag `cronograma_editor_v2`.

O script existia desde 24/07 sem teste nenhum. Ele *avisava* que o calendário
do tenant divergia do motor novo (seg–sex fixo nesta fase) — mas o aviso saía
DEPOIS de gravar a flag, então quem o lesse já estava com o motor novo ligado
e o recálculo já teria movido as datas. O guard passou a vir antes.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from datetime import datetime                             # noqa: E402

import pytest                                             # noqa: E402
from werkzeug.security import generate_password_hash      # noqa: E402

from app import app, db                                   # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture()
def ctx():
    from models import (CalendarioEmpresa, ConfiguracaoEmpresa, TipoUsuario,
                        Usuario)
    with app.app_context():
        suf = datetime.utcnow().strftime('%H%M%S%f')
        admin = Usuario(username=f'ev2_{suf}', email=f'ev2_{suf}@test.local',
                        nome=f'Editor V2 {suf}',
                        password_hash=generate_password_hash('Senha@2026'),
                        tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                        versao_sistema='v2')
        db.session.add(admin)
        db.session.flush()
        db.session.add(ConfiguracaoEmpresa(
            admin_id=admin.id, nome_empresa=f'Empresa EV2 {suf}',
            cronograma_editor_v2=False))
        db.session.add(CalendarioEmpresa(
            admin_id=admin.id, considerar_sabado=False,
            considerar_domingo=False))
        db.session.commit()
        yield {'admin_id': admin.id}


def _ligada(admin_id):
    from scripts.flag_cronograma_editor_v2 import status_flag
    with app.app_context():
        return status_flag(admin_id)['cronograma_editor_v2']


def _calendario_com_fim_de_semana(admin_id):
    from models import CalendarioEmpresa
    with app.app_context():
        cal = CalendarioEmpresa.query.filter_by(admin_id=admin_id).first()
        cal.considerar_sabado = True
        db.session.commit()


def test_liga_quando_o_calendario_nao_diverge(ctx):
    from scripts.flag_cronograma_editor_v2 import main
    assert main([str(ctx['admin_id']), '--ligar']) == 0
    assert _ligada(ctx['admin_id']) is True


def test_recusa_ligar_com_calendario_divergente_e_nao_grava(ctx):
    """O ponto do guard: recusar ANTES de gravar."""
    from scripts.flag_cronograma_editor_v2 import main
    _calendario_com_fim_de_semana(ctx['admin_id'])
    assert main([str(ctx['admin_id']), '--ligar']) == 1
    assert _ligada(ctx['admin_id']) is False


def test_forcar_liga_mesmo_com_calendario_divergente(ctx):
    from scripts.flag_cronograma_editor_v2 import main
    _calendario_com_fim_de_semana(ctx['admin_id'])
    assert main([str(ctx['admin_id']), '--ligar', '--forcar']) == 0
    assert _ligada(ctx['admin_id']) is True


def test_desligar_nunca_e_barrado_pelo_guard(ctx):
    """O guard só olha o `--ligar`. Desligar é sempre o caminho de volta."""
    from scripts.flag_cronograma_editor_v2 import main
    _calendario_com_fim_de_semana(ctx['admin_id'])
    assert main([str(ctx['admin_id']), '--ligar', '--forcar']) == 0
    assert main([str(ctx['admin_id']), '--desligar']) == 0
    assert _ligada(ctx['admin_id']) is False


def test_status_nunca_grava(ctx):
    from scripts.flag_cronograma_editor_v2 import main
    assert main([str(ctx['admin_id']), '--status']) == 0
    assert _ligada(ctx['admin_id']) is False


def test_admin_inexistente_devolve_1(ctx):
    from scripts.flag_cronograma_editor_v2 import main
    assert main([str(ctx['admin_id'] + 999_999), '--ligar']) == 1


def _obra_com_cronograma(admin_id, n=3):
    """Obra com tarefas ativas e datadas — o que o motor novo recalcularia."""
    from datetime import date
    from models import Cliente, Obra, TarefaCronograma
    with app.app_context():
        cli = Cliente(nome='Cliente EV2', admin_id=admin_id)
        db.session.add(cli)
        db.session.flush()
        obra = Obra(nome='Obra com datas', admin_id=admin_id,
                    cliente_id=cli.id, data_inicio=date(2026, 7, 1))
        db.session.add(obra)
        db.session.flush()
        for i in range(n):
            db.session.add(TarefaCronograma(
                obra_id=obra.id, admin_id=admin_id, ordem=i,
                nome_tarefa=f'Tarefa {i}', ativa=True, is_cliente=False,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10),
                duracao_dias=8))
        db.session.commit()
        return obra.id


def test_recusa_ligar_sem_linha_de_base_e_nao_grava(ctx):
    """O rollback desta flag é assimétrico: desligar devolve o motor, não as
    datas que ele já recalculou. Sem linha de base, ligar é porta só de ida —
    e o runbook mandava tirar o snapshot sem ninguém poder conferir.
    """
    from scripts.flag_cronograma_editor_v2 import main
    _obra_com_cronograma(ctx['admin_id'])
    assert main([str(ctx['admin_id']), '--ligar']) == 1
    assert _ligada(ctx['admin_id']) is False


def test_criar_baseline_congela_as_datas_e_destrava_o_ligar(ctx):
    from datetime import date
    from models import CronogramaBaseline, CronogramaBaselineItem
    from scripts.flag_cronograma_editor_v2 import main
    obra_id = _obra_com_cronograma(ctx['admin_id'])

    assert main([str(ctx['admin_id']), '--criar-baseline', '--status']) == 0
    assert _ligada(ctx['admin_id']) is False, '--status não pode ligar nada'

    with app.app_context():
        bl = CronogramaBaseline.query.filter_by(
            obra_id=obra_id, admin_id=ctx['admin_id'], ativa=True).one()
        itens = CronogramaBaselineItem.query.filter_by(baseline_id=bl.id).all()
        assert len(itens) == 3
        assert all(i.data_inicio == date(2026, 7, 1)
                   and i.data_fim == date(2026, 7, 10) for i in itens)

    assert main([str(ctx['admin_id']), '--ligar']) == 0
    assert _ligada(ctx['admin_id']) is True


def test_forcar_liga_sem_linha_de_base(ctx):
    """Perder o plano atual pode ser aceitável — mas tem de ser dito."""
    from scripts.flag_cronograma_editor_v2 import main
    _obra_com_cronograma(ctx['admin_id'])
    assert main([str(ctx['admin_id']), '--ligar', '--forcar']) == 0
    assert _ligada(ctx['admin_id']) is True


def test_obra_sem_datas_nao_exige_linha_de_base(ctx):
    """Sem datas não há o que congelar nem o que o recálculo reescreva."""
    from datetime import date
    from models import Cliente, Obra, TarefaCronograma
    from scripts.flag_cronograma_editor_v2 import main
    with app.app_context():
        cli = Cliente(nome='Cliente EV2 sem datas', admin_id=ctx['admin_id'])
        db.session.add(cli)
        db.session.flush()
        obra = Obra(nome='Obra sem datas', admin_id=ctx['admin_id'],
                    cliente_id=cli.id, data_inicio=date(2026, 7, 1))
        db.session.add(obra)
        db.session.flush()
        db.session.add(TarefaCronograma(
            obra_id=obra.id, admin_id=ctx['admin_id'], ordem=0,
            nome_tarefa='Sem plano', ativa=True, is_cliente=False))
        db.session.commit()
    assert main([str(ctx['admin_id']), '--ligar']) == 0
    assert _ligada(ctx['admin_id']) is True


def test_desligar_segue_livre_mesmo_sem_linha_de_base(ctx):
    """O caminho de volta nunca é barrado — inclusive por este guard."""
    from scripts.flag_cronograma_editor_v2 import main
    _obra_com_cronograma(ctx['admin_id'])
    assert main([str(ctx['admin_id']), '--ligar', '--forcar']) == 0
    assert main([str(ctx['admin_id']), '--desligar']) == 0
    assert _ligada(ctx['admin_id']) is False
