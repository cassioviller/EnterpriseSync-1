"""Task #173 / #178 — testes para EngenheiroResponsavel + helper de PDF.

Cobertura:
  T1. Schema: tabela engenheiro_responsavel + colunas FK em
      configuracao_empresa.engenheiro_padrao_id e propostas_comerciais.engenheiro_id
      (migração 133 aplicada). Os campos legados engenheiro_* da
      configuracao_empresa foram removidos (migração 135 — Task #178).
  T2. Helper services.engenheiro_service.obter_engenheiro_dados:
       a. Sem nada configurado → fonte=vazio.
       b. Config sem engenheiro_padrao_id → fonte=vazio (campos legados
          foram removidos pela Task #178; não há mais fallback textual).
       c. ConfiguracaoEmpresa.engenheiro_padrao_id apontando para um registro →
          fonte=engenheiro_responsavel.
       d. Proposta.engenheiro_id sobrescreve o padrão da empresa.
       e. Editar telefone do engenheiro padrão reflete no resultado seguinte.
       e2. Engenheiro padrão inativo → fonte=vazio.
       f. listar_engenheiros_ativos respeita ativo=False.
  T3. _parse_engenheiro_id (propostas_consolidated):
       a. Vazio → None.
       b. ID inexistente → None.
       c. ID de outro tenant → None.
       d. ID válido do mesmo tenant → eng.id.
  T4. PDF paginado/final usam engenheiro_dados (override) e não vazam
      PropostaTemplate.engenheiro_*.
"""
from __future__ import annotations

import os
import sys
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

logging.basicConfig(level=logging.WARNING)

from app import app, db
from models import (
    Usuario, TipoUsuario, ConfiguracaoEmpresa, Proposta,
    EngenheiroResponsavel,
)
from services.engenheiro_service import (
    obter_engenheiro_dados, listar_engenheiros_ativos,
)
from werkzeug.security import generate_password_hash


PASS = []
FAIL = []


def record(label, ok, evidence=''):
    (PASS if ok else FAIL).append((label, evidence))
    prefix = 'PASS' if ok else 'FAIL'
    print(f"  {prefix}: {label}{(' — ' + evidence) if evidence else ''}")


def make_admin(tag_suffix=''):
    tag = datetime.utcnow().strftime('%H%M%S%f') + tag_suffix
    u = Usuario(
        username=f't173_{tag}',
        email=f't173_{tag}@test.local',
        nome=f'Admin T173 {tag}',
        password_hash=generate_password_hash('senha123'),
        tipo_usuario=TipoUsuario.ADMIN,
    )
    db.session.add(u)
    db.session.flush()
    return u


def make_proposta(admin_id, engenheiro_id=None):
    tag = datetime.utcnow().strftime('%H%M%S%f')
    p = Proposta(
        admin_id=admin_id,
        numero=f'PROP-T173-{tag}',
        cliente_nome=f'Cliente T173 {tag}',
        cliente_email=f'cli_{tag}@x.test',
        engenheiro_id=engenheiro_id,
    )
    db.session.add(p)
    db.session.flush()
    return p


def t1_schema():
    res = db.session.execute(db.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name='engenheiro_responsavel'"
    )).fetchone()
    record('T1a — tabela engenheiro_responsavel existe', res is not None,
           evidence=f"tab={res[0] if res else None}")

    res = db.session.execute(db.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='configuracao_empresa' "
        "AND column_name='engenheiro_padrao_id'"
    )).fetchone()
    record('T1b — coluna configuracao_empresa.engenheiro_padrao_id existe',
           res is not None, evidence=f"col={res[0] if res else None}")

    res = db.session.execute(db.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='propostas_comerciais' "
        "AND column_name='engenheiro_id'"
    )).fetchone()
    record('T1c — coluna propostas_comerciais.engenheiro_id existe',
           res is not None, evidence=f"col={res[0] if res else None}")


def t2_helper_obter_engenheiro_dados():
    admin = make_admin('a')
    aid = admin.id

    # 2a — vazio total
    dados = obter_engenheiro_dados(proposta=None, config_empresa=None)
    record('T2a — sem nada → fonte=vazio',
           dados['fonte'] == 'vazio' and dados['nome'] == '',
           evidence=f"fonte={dados['fonte']}, nome={dados['nome']!r}")

    # Setup config sem engenheiro_padrao_id (Task #178: campos legados removidos)
    cfg = ConfiguracaoEmpresa(
        admin_id=aid,
        nome_empresa='Empresa T173',
    )
    db.session.add(cfg)
    db.session.flush()

    # 2b — sem padrão e sem legado (legado removido em Task #178)
    dados = obter_engenheiro_dados(proposta=None, config_empresa=cfg)
    record('T2b — config sem padrão → fonte=vazio (sem legado pós #178)',
           dados['fonte'] == 'vazio'
           and dados['nome'] == ''
           and dados['crea'] == '',
           evidence=f"fonte={dados['fonte']}, nome={dados['nome']!r}")

    # Cria engenheiro próprio e marca como padrão
    eng_padrao = EngenheiroResponsavel(
        admin_id=aid,
        nome='Eng. Padrão',
        crea='CREA-PAD-1',
        email='padrao@empresa.test',
        telefone='11 1111-1111',
        endereco='Rua Padrão, 1',
        website='https://padrao.test',
        ativo=True,
    )
    db.session.add(eng_padrao)
    db.session.flush()
    cfg.engenheiro_padrao_id = eng_padrao.id
    db.session.flush()

    # 2c — padrão da empresa ignora legado
    dados = obter_engenheiro_dados(proposta=None, config_empresa=cfg)
    record('T2c — padrão da empresa → fonte=engenheiro_responsavel',
           dados['fonte'] == 'engenheiro_responsavel'
           and dados['nome'] == 'Eng. Padrão'
           and dados['crea'] == 'CREA-PAD-1'
           and dados['engenheiro_id'] == eng_padrao.id,
           evidence=f"fonte={dados['fonte']}, nome={dados['nome']!r}, id={dados['engenheiro_id']}")

    # Cria engenheiro de override e proposta apontando para ele
    eng_override = EngenheiroResponsavel(
        admin_id=aid,
        nome='Eng. Override',
        crea='CREA-OVR-1',
        email='override@empresa.test',
        telefone='11 2222-2222',
        ativo=True,
    )
    db.session.add(eng_override)
    db.session.flush()

    prop = make_proposta(aid, engenheiro_id=eng_override.id)

    # 2d — proposta sobrescreve padrão
    dados = obter_engenheiro_dados(proposta=prop, config_empresa=cfg)
    record('T2d — proposta sobrescreve padrão',
           dados['fonte'] == 'engenheiro_responsavel'
           and dados['engenheiro_id'] == eng_override.id
           and dados['nome'] == 'Eng. Override',
           evidence=f"id={dados['engenheiro_id']}, nome={dados['nome']!r}")

    # Proposta sem override volta a usar o padrão
    prop_sem_override = make_proposta(aid, engenheiro_id=None)
    dados = obter_engenheiro_dados(proposta=prop_sem_override, config_empresa=cfg)
    record('T2d2 — proposta sem override usa padrão da empresa',
           dados['engenheiro_id'] == eng_padrao.id
           and dados['nome'] == 'Eng. Padrão',
           evidence=f"id={dados['engenheiro_id']}, nome={dados['nome']!r}")

    # 2e — editar telefone do padrão reflete no próximo PDF
    eng_padrao.telefone = '11 9999-9999'
    db.session.flush()
    dados = obter_engenheiro_dados(proposta=prop_sem_override, config_empresa=cfg)
    record('T2e — alterar telefone do padrão reflete no helper',
           dados['telefone'] == '11 9999-9999',
           evidence=f"telefone={dados['telefone']!r}")

    # 2e2 — engenheiro inativado deixa de ser usado pelo helper
    # (Task #178: sem fallback legado — vai direto para fonte=vazio)
    eng_padrao.ativo = False
    db.session.flush()
    dados = obter_engenheiro_dados(proposta=prop_sem_override, config_empresa=cfg)
    record('T2e2 — engenheiro padrão inativo → fonte=vazio',
           dados['fonte'] == 'vazio'
           and dados['nome'] == '',
           evidence=f"fonte={dados['fonte']}, nome={dados['nome']!r}")
    # Reativa para o resto dos testes
    eng_padrao.ativo = True
    db.session.flush()

    # 2e3 — proposta com override apontando para outro tenant é ignorada
    outro_admin = make_admin('xtenant')
    eng_outro = EngenheiroResponsavel(
        admin_id=outro_admin.id, nome='Eng OUTRO TENANT', ativo=True,
    )
    db.session.add(eng_outro)
    db.session.flush()
    # Força um id de outro tenant na proposta (cenário malicioso/legado).
    prop_outro = make_proposta(aid, engenheiro_id=eng_outro.id)
    dados = obter_engenheiro_dados(proposta=prop_outro, config_empresa=cfg)
    record('T2e3 — engenheiro_id de outro tenant é ignorado (cai no padrão)',
           dados['nome'] == 'Eng. Padrão'
           and dados['engenheiro_id'] == eng_padrao.id,
           evidence=f"nome={dados['nome']!r}, id={dados['engenheiro_id']}")

    # 2f — listar_engenheiros_ativos
    eng_inativo = EngenheiroResponsavel(
        admin_id=aid, nome='Eng. Inativo', crea='X', ativo=False,
    )
    db.session.add(eng_inativo)
    db.session.flush()

    ativos = listar_engenheiros_ativos(aid)
    nomes_ativos = sorted(e.nome for e in ativos)
    record('T2f — listar_engenheiros_ativos ignora inativos',
           'Eng. Inativo' not in nomes_ativos
           and 'Eng. Padrão' in nomes_ativos
           and 'Eng. Override' in nomes_ativos,
           evidence=f"ativos={nomes_ativos}")


def t4_pdf_paginado_nao_vaza_template_engenheiro():
    """Render paginated PDF: deve usar engenheiro_dados (override) e jamais
    cair no PropostaTemplate.engenheiro_*."""
    from flask import render_template
    from models import PropostaTemplate

    admin = make_admin('pdf')
    aid = admin.id

    # Engenheiro padrão da empresa + config
    eng_padrao = EngenheiroResponsavel(
        admin_id=aid, nome='ENG_PADRAO_T173', crea='CREA-PAD-99',
        email='padrao_pdf@x.test', telefone='11 PAD-7777', ativo=True,
    )
    db.session.add(eng_padrao)
    db.session.flush()

    cfg = ConfiguracaoEmpresa(
        admin_id=aid, nome_empresa='Empresa T173 PDF',
        engenheiro_padrao_id=eng_padrao.id,
    )
    db.session.add(cfg)
    db.session.flush()

    # Template antigo com defaults — não deve aparecer no PDF de jeito nenhum
    tpl = PropostaTemplate(
        nome='Tpl T173',
        categoria='estrutura',
        engenheiro_nome='TPL_NAO_DEVE_APARECER',
        engenheiro_crea='TPL_CREA_NAO',
        engenheiro_email='tpl_nao@x.test',
        engenheiro_telefone='99 TPL-NAO',
        engenheiro_endereco='Rua TPL Não',
        engenheiro_website='https://tpl-nao.test',
    )
    db.session.add(tpl)
    db.session.flush()

    # Override por proposta
    eng_override = EngenheiroResponsavel(
        admin_id=aid, nome='ENG_OVERRIDE_T173', crea='CREA-OVR-99',
        email='ovr_pdf@x.test', telefone='11 OVR-8888', ativo=True,
    )
    db.session.add(eng_override)
    db.session.flush()

    prop = make_proposta(aid, engenheiro_id=eng_override.id)
    # paginated template trata itens_inclusos/exclusos como string (split('\n')).
    # Para o teste de PDF, força-os a string para não estourar com o default JSON list.
    prop.itens_inclusos = ''
    prop.itens_exclusos = ''
    db.session.flush()

    dados = obter_engenheiro_dados(proposta=prop, config_empresa=cfg)

    with app.test_request_context('/'):
        html = render_template(
            'propostas/pdf_estruturas_vale_paginado.html',
            proposta=prop,
            template=tpl,
            config=cfg,
            config_empresa=cfg,
            engenheiro_dados=dados,
            total_geral=0,
        )

    record('T4a — PDF paginado contém engenheiro de override',
           'ENG_OVERRIDE_T173' in html and 'CREA-OVR-99' in html,
           evidence=f"override_no_html={'ENG_OVERRIDE_T173' in html}")
    record('T4b — PDF paginado NÃO usa PropostaTemplate.engenheiro_*',
           'TPL_NAO_DEVE_APARECER' not in html
           and 'TPL_CREA_NAO' not in html
           and 'tpl_nao@x.test' not in html
           and '99 TPL-NAO' not in html
           and 'Rua TPL Não' not in html
           and 'https://tpl-nao.test' not in html,
           evidence='nenhum dado de PropostaTemplate vazou')
    # T4c removido em Task #178: campos legados engenheiro_* da
    # configuracao_empresa foram dropados — não há mais como vazar.

    # Sanity: também valida o template "final" (outra variante reescrita)
    with app.test_request_context('/'):
        html_final = render_template(
            'propostas/pdf_estruturas_vale_final.html',
            proposta=prop,
            template=tpl,
            config=cfg,
            config_empresa=cfg,
            engenheiro_dados=dados,
            total_geral=0,
        )
    record('T4d — PDF "final" também usa override e ignora template',
           'ENG_OVERRIDE_T173' in html_final
           and 'TPL_NAO_DEVE_APARECER' not in html_final,
           evidence=f"override={'ENG_OVERRIDE_T173' in html_final}")


def t3_parse_engenheiro_id():
    from propostas_consolidated import _parse_engenheiro_id

    admin1 = make_admin('p1')
    admin2 = make_admin('p2')

    eng1 = EngenheiroResponsavel(admin_id=admin1.id, nome='Eng A1', ativo=True)
    eng2 = EngenheiroResponsavel(admin_id=admin2.id, nome='Eng A2', ativo=True)
    db.session.add_all([eng1, eng2])
    db.session.flush()

    record('T3a — vazio → None', _parse_engenheiro_id('', admin1.id) is None)
    record('T3a2 — None → None', _parse_engenheiro_id(None, admin1.id) is None)
    record('T3b — id inexistente → None',
           _parse_engenheiro_id('999999', admin1.id) is None)
    record('T3c — id de outro tenant → None',
           _parse_engenheiro_id(str(eng2.id), admin1.id) is None,
           evidence=f"id={eng2.id} pertence a admin {admin2.id}")
    record('T3d — id válido do tenant → eng.id',
           _parse_engenheiro_id(str(eng1.id), admin1.id) == eng1.id,
           evidence=f"esperado={eng1.id}")


def main():
    print('=' * 80)
    print('TASK #173 — EngenheiroResponsavel + helper PDF')
    print('=' * 80)

    with app.app_context():
        try:
            t1_schema()
            t2_helper_obter_engenheiro_dados()
            t4_pdf_paginado_nao_vaza_template_engenheiro()
            t3_parse_engenheiro_id()
            db.session.rollback()
        except Exception as e:
            db.session.rollback()
            FAIL.append(('EXCEPTION', str(e)))
            import traceback
            traceback.print_exc()

    print('=' * 80)
    print(f'PASS: {len(PASS)}  FAIL: {len(FAIL)}')
    print('=' * 80)
    for label, ev in FAIL:
        print(f'  FAIL: {label} — {ev}')
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
