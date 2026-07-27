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
