"""Task #62 — testes pytest do auto-vínculo Funcao→ComposicaoServico em
RDOMaoObra e da auto-criação de SubatividadeMestre via cronograma.

Cobre:
  - Migração 150: colunas/tabela existem.
  - Listener auto-link: status auto / sem_funcao / funcao_fora_composicao /
    subatividade_sem_composicoes / ambiguo (NULL id) / manual preservado.
  - garantir_subatividade: reusa por (admin, lower(nome), servico_id) e
    NÃO reusa entre serviços distintos; cria com flags de revisão.
  - _sync_composicoes_subatividade: idempotência + bloqueio cross-tenant +
    filtro MAO_OBRA.
"""
import os
import sys
from datetime import date, datetime

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from models import (  # noqa: E402
    Usuario, TipoUsuario, Funcionario, Funcao, Insumo,
    Servico, ComposicaoServico,
    SubatividadeMestre, SubatividadeMaoObra,
    RDO, RDOMaoObra, RDOServicoSubatividade,
    Obra, Cliente, TarefaCronograma,
)


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


# ───────────────────────────── fixtures ─────────────────────────────────────

@pytest.fixture()
def app_ctx():
    with app.app_context():
        yield


@pytest.fixture()
def tenant(app_ctx):
    """Cria um tenant inteiro (admin+insumos+serviço+composições+obra+rdo).

    Faz commit para que o listener before_flush seja exercitado de fato.
    Limpa tudo no teardown (FK ON DELETE CASCADE / DELETE explícito).
    """
    s = _suffix()
    admin = Usuario(
        username=f't62_{s}', email=f't62_{s}@test.local',
        nome='Task62', password_hash=generate_password_hash('x'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin); db.session.flush()
    ins_mo = Insumo(admin_id=admin.id, nome=f'Pedreiro Hora {s}',
                    tipo='MAO_OBRA', unidade='h', ativo=True)
    ins_mo2 = Insumo(admin_id=admin.id, nome=f'Servente Hora {s}',
                     tipo='MAO_OBRA', unidade='h', ativo=True)
    ins_mat = Insumo(admin_id=admin.id, nome=f'Cimento {s}',
                     tipo='MATERIAL', unidade='kg', ativo=True)
    db.session.add_all([ins_mo, ins_mo2, ins_mat]); db.session.flush()
    funcao_ok = Funcao(nome=f'Pedreiro {s}', admin_id=admin.id,
                       salario_base=2500.0, insumo_id=ins_mo.id)
    funcao_orfa = Funcao(nome=f'Aux {s}', admin_id=admin.id, salario_base=1800.0)
    db.session.add_all([funcao_ok, funcao_orfa]); db.session.flush()
    f1 = Funcionario(codigo=f'A{admin.id}', nome=f'Func OK {s}',
                     cpf=f'X{admin.id:011d}'[:14], data_admissao=date.today(),
                     tipo_remuneracao='diaria', valor_diaria=200.0, ativo=True,
                     admin_id=admin.id, funcao_id=funcao_ok.id)
    f2 = Funcionario(codigo=f'B{admin.id}', nome=f'Func Orfao {s}',
                     cpf=f'Y{admin.id:011d}'[:14], data_admissao=date.today(),
                     tipo_remuneracao='diaria', valor_diaria=180.0, ativo=True,
                     admin_id=admin.id, funcao_id=funcao_orfa.id)
    db.session.add_all([f1, f2]); db.session.flush()

    servico = Servico(nome=f'Alvenaria {s}', admin_id=admin.id, ativo=True,
                      unidade_medida='m2', categoria='estrutura')
    db.session.add(servico); db.session.flush()
    comp_mo = ComposicaoServico(admin_id=admin.id, servico_id=servico.id,
                                insumo_id=ins_mo.id, coeficiente=1.5, unidade='h')
    comp_mo2 = ComposicaoServico(admin_id=admin.id, servico_id=servico.id,
                                 insumo_id=ins_mo2.id, coeficiente=2.0, unidade='h')
    comp_mat = ComposicaoServico(admin_id=admin.id, servico_id=servico.id,
                                 insumo_id=ins_mat.id, coeficiente=20.0, unidade='kg')
    db.session.add_all([comp_mo, comp_mo2, comp_mat]); db.session.flush()
    sub = SubatividadeMestre(servico_id=servico.id, tipo='subatividade',
                             nome=f'Levantar parede {s}', unidade_medida='m2',
                             meta_produtividade=2.0, ordem_padrao=0,
                             obrigatoria=False, admin_id=admin.id, ativo=True)
    db.session.add(sub); db.session.flush()

    cli = Cliente(nome=f'Cli {s}', email=f'c_{s}@x.local', admin_id=admin.id)
    db.session.add(cli); db.session.flush()
    obra = Obra(nome=f'Obra {s}', codigo=f'O{s[-6:]}', admin_id=admin.id,
                cliente_id=cli.id, ativo=True, data_inicio=date.today(),
                area_total_m2=100.0)
    db.session.add(obra); db.session.flush()
    rdo = RDO(numero_rdo=f'RDO-T62-{s[-6:]}', obra_id=obra.id,
              data_relatorio=date.today(), admin_id=admin.id, status='Rascunho')
    db.session.add(rdo); db.session.flush()
    sub_rdo = RDOServicoSubatividade(
        rdo_id=rdo.id, servico_id=servico.id, subatividade_mestre_id=sub.id,
        nome_subatividade=sub.nome, percentual_conclusao=10.0, admin_id=admin.id,
    )
    db.session.add(sub_rdo); db.session.commit()

    ctx = dict(
        admin=admin, ins_mo=ins_mo, ins_mo2=ins_mo2, ins_mat=ins_mat,
        funcao_ok=funcao_ok, funcao_orfa=funcao_orfa, f1=f1, f2=f2,
        servico=servico, comp_mo=comp_mo, comp_mo2=comp_mo2, comp_mat=comp_mat,
        sub=sub, obra=obra, rdo=rdo, sub_rdo=sub_rdo,
    )
    yield ctx

    # teardown
    try:
        db.session.rollback()
        RDOMaoObra.query.filter_by(rdo_id=rdo.id).delete()
        RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).delete()
        db.session.delete(rdo)
        db.session.commit()
        SubatividadeMaoObra.query.filter_by(admin_id=admin.id).delete()
        for cls in (TarefaCronograma, SubatividadeMestre, ComposicaoServico,
                    Servico, Funcionario, Funcao, Insumo, Obra, Cliente):
            cls.query.filter_by(admin_id=admin.id).delete()
        Usuario.query.filter_by(id=admin.id).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


# ───────────────────────────── tests ────────────────────────────────────────

def test_migration_150_columns(app_ctx):
    from sqlalchemy import inspect
    insp = inspect(db.engine)
    cols_mo = {c['name'] for c in insp.get_columns('rdo_mao_obra')}
    assert 'composicao_servico_id' in cols_mo
    assert 'vinculo_status' in cols_mo
    assert 'insumo_id' in {c['name'] for c in insp.get_columns('funcao')}
    cols_sub = {c['name'] for c in insp.get_columns('subatividade_mestre')}
    assert 'criada_via_cronograma' in cols_sub
    assert 'precisa_revisao' in cols_sub
    assert 'servico_id' in {c['name'] for c in insp.get_columns('tarefa_cronograma')}
    assert 'subatividade_mao_obra' in set(insp.get_table_names())


def test_listener_status_auto(tenant):
    """Sub COM 1 link N:N para o insumo do funcionário → status='auto'."""
    db.session.add(SubatividadeMaoObra(
        admin_id=tenant['admin'].id,
        subatividade_mestre_id=tenant['sub'].id,
        composicao_servico_id=tenant['comp_mo'].id,
    ))
    db.session.commit()
    mo = RDOMaoObra(
        rdo_id=tenant['rdo'].id, funcionario_id=tenant['f1'].id,
        funcao_exercida=tenant['funcao_ok'].nome, horas_trabalhadas=8.0,
        admin_id=tenant['admin'].id, subatividade_id=tenant['sub_rdo'].id,
    )
    db.session.add(mo); db.session.commit(); db.session.refresh(mo)
    assert mo.vinculo_status == 'auto'
    assert mo.composicao_servico_id == tenant['comp_mo'].id


def test_listener_sem_funcao(tenant):
    mo = RDOMaoObra(
        rdo_id=tenant['rdo'].id, funcionario_id=tenant['f2'].id,
        funcao_exercida=tenant['funcao_orfa'].nome, horas_trabalhadas=4.0,
        admin_id=tenant['admin'].id, subatividade_id=tenant['sub_rdo'].id,
    )
    db.session.add(mo); db.session.commit(); db.session.refresh(mo)
    assert mo.vinculo_status == 'sem_funcao'
    assert mo.composicao_servico_id is None


def test_listener_subatividade_sem_composicoes(tenant):
    """Sub SEM nenhum link N:N → status='subatividade_sem_composicoes'
    (NÃO faz fallback automático para todas as composições do serviço)."""
    mo = RDOMaoObra(
        rdo_id=tenant['rdo'].id, funcionario_id=tenant['f1'].id,
        funcao_exercida=tenant['funcao_ok'].nome, horas_trabalhadas=8.0,
        admin_id=tenant['admin'].id, subatividade_id=tenant['sub_rdo'].id,
    )
    db.session.add(mo); db.session.commit(); db.session.refresh(mo)
    assert mo.vinculo_status == 'subatividade_sem_composicoes'
    assert mo.composicao_servico_id is None


def test_listener_funcao_fora_composicao(tenant):
    """Sub com link só de material → função (mo) fora da composição."""
    db.session.add(SubatividadeMaoObra(
        admin_id=tenant['admin'].id,
        subatividade_mestre_id=tenant['sub'].id,
        composicao_servico_id=tenant['comp_mat'].id,
    ))
    db.session.commit()
    mo = RDOMaoObra(
        rdo_id=tenant['rdo'].id, funcionario_id=tenant['f1'].id,
        funcao_exercida=tenant['funcao_ok'].nome, horas_trabalhadas=2.0,
        admin_id=tenant['admin'].id, subatividade_id=tenant['sub_rdo'].id,
    )
    db.session.add(mo); db.session.commit(); db.session.refresh(mo)
    assert mo.vinculo_status == 'funcao_fora_composicao'
    assert mo.composicao_servico_id is None


def test_listener_ambiguo_nao_grava_id(tenant):
    """Múltiplas composições candidatas para o mesmo insumo → 'ambiguo' E
    composicao_servico_id permanece NULL (gestor decide manualmente)."""
    # Cria uma 2a composição com o MESMO insumo do funcionário, garantindo
    # ambiguidade. Vincula AMBAS na sub via N:N.
    comp_dup = ComposicaoServico(
        admin_id=tenant['admin'].id, servico_id=tenant['servico'].id,
        insumo_id=tenant['ins_mo'].id, coeficiente=2.5, unidade='h',
    )
    # UNIQUE(servico_id, insumo_id) impede 2 com mesma chave; ajusta servico
    # criando outra composição mas no MESMO insumo via outro Servico+Sub não
    # ajuda (sub está em 1 servico). Em vez disso, simulamos ambiguidade
    # criando 2 composições: uma do ins_mo e outra do ins_mo2 e fingindo que
    # o Funcionario está vinculado via insumo de função genérica. Como o
    # resolver filtra por insumo_id == funcao.insumo_id, precisamos REALMENTE
    # ter 2 candidatos. Solução: dropar a unique constraint do tenant não é
    # viável; em vez disso, marcamos AMBOS comp_mo e comp_mo2 na sub e damos
    # ao funcionário uma função cujo insumo_id seja COMPATÍVEL com ambos —
    # impossível pelo modelo atual (só 1 insumo_id por função).
    # Como não conseguimos reproduzir ambiguidade real sem alterar o schema,
    # validamos diretamente o resolver com um stub: sub com 2 links onde
    # ambos pertencem ao mesmo insumo_id → não factível. Em vez disso,
    # exercitamos a função `_candidatos_para_servico` retornando lista de
    # 2 itens via patch.
    from services import vinculo_mao_obra as svc
    from unittest.mock import patch

    db.session.add(SubatividadeMaoObra(
        admin_id=tenant['admin'].id,
        subatividade_mestre_id=tenant['sub'].id,
        composicao_servico_id=tenant['comp_mo'].id,
    ))
    db.session.commit()

    mo = RDOMaoObra(
        rdo_id=tenant['rdo'].id, funcionario_id=tenant['f1'].id,
        funcao_exercida=tenant['funcao_ok'].nome, horas_trabalhadas=1.0,
        admin_id=tenant['admin'].id, subatividade_id=tenant['sub_rdo'].id,
    )
    fake_candidatas = [tenant['comp_mo'], comp_dup]
    with patch.object(svc, '_candidatos_para_servico',
                       return_value=fake_candidatas):
        comp_id, status = svc.resolver_vinculo(mo)
    assert status == 'ambiguo'
    assert comp_id is None


def test_listener_manual_preservado(tenant):
    db.session.add(SubatividadeMaoObra(
        admin_id=tenant['admin'].id,
        subatividade_mestre_id=tenant['sub'].id,
        composicao_servico_id=tenant['comp_mo'].id,
    ))
    db.session.commit()
    mo = RDOMaoObra(
        rdo_id=tenant['rdo'].id, funcionario_id=tenant['f1'].id,
        funcao_exercida=tenant['funcao_ok'].nome, horas_trabalhadas=1.0,
        admin_id=tenant['admin'].id, subatividade_id=tenant['sub_rdo'].id,
        composicao_servico_id=tenant['comp_mat'].id,
        vinculo_status='manual',
    )
    db.session.add(mo); db.session.commit(); db.session.refresh(mo)
    assert mo.vinculo_status == 'manual'
    assert mo.composicao_servico_id == tenant['comp_mat'].id


def test_garantir_subatividade_escopa_por_servico(tenant):
    from services.auto_subatividade_cronograma import garantir_subatividade
    nome = f'Pintura {_suffix()}'
    sub_a, criada_a = garantir_subatividade(
        nome, tenant['admin'].id, tenant['servico'].id
    )
    assert criada_a is True
    assert sub_a.criada_via_cronograma is True
    assert sub_a.precisa_revisao is True
    assert sub_a.servico_id == tenant['servico'].id

    # Reuso case-insensitive no MESMO serviço
    sub_b, criada_b = garantir_subatividade(
        '  ' + nome.upper() + ' ', tenant['admin'].id, tenant['servico'].id,
    )
    assert criada_b is False
    assert sub_b.id == sub_a.id

    # Outro serviço: NÃO deve reusar — cria nova
    outro_servico = Servico(nome=f'OutroSvc {_suffix()}',
                            admin_id=tenant['admin'].id, ativo=True,
                            unidade_medida='m2', categoria='x')
    db.session.add(outro_servico); db.session.commit()
    sub_c, criada_c = garantir_subatividade(
        nome, tenant['admin'].id, outro_servico.id,
    )
    assert criada_c is True
    assert sub_c.id != sub_a.id
    assert sub_c.servico_id == outro_servico.id
    db.session.commit()


def test_sync_composicoes_idempotente_e_filtra_cross_tenant(tenant):
    from cronograma_views import _sync_composicoes_subatividade
    sub = tenant['sub']
    admin_id = tenant['admin'].id

    assert SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id).count() == 0

    # adiciona apenas o MO (mat deve ser filtrado por NÃO ser MAO_OBRA)
    _sync_composicoes_subatividade(
        sub,
        [str(tenant['comp_mo'].id), str(tenant['comp_mat'].id)],
        admin_id,
    )
    db.session.commit()
    ids = {l.composicao_servico_id for l in SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id).all()}
    assert ids == {tenant['comp_mo'].id}, (
        "comp_mat (MATERIAL) deve ser filtrado; só MO entra"
    )

    # cria outro tenant e tenta injetar a composição dele → deve ser barrada
    s2 = _suffix()
    outro = Usuario(
        username=f't62b_{s2}', email=f't62b_{s2}@x.local', nome='Outro',
        password_hash=generate_password_hash('x'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(outro); db.session.flush()
    ins_x = Insumo(admin_id=outro.id, nome=f'IX {s2}', tipo='MAO_OBRA',
                   unidade='h', ativo=True)
    svc_x = Servico(nome=f'SX {s2}', admin_id=outro.id, ativo=True,
                    unidade_medida='m2', categoria='x')
    db.session.add_all([ins_x, svc_x]); db.session.flush()
    comp_x = ComposicaoServico(admin_id=outro.id, servico_id=svc_x.id,
                               insumo_id=ins_x.id, coeficiente=1.0, unidade='h')
    db.session.add(comp_x); db.session.commit()

    _sync_composicoes_subatividade(
        sub,
        [str(tenant['comp_mo'].id), str(comp_x.id)],
        admin_id,
    )
    db.session.commit()
    ids2 = {l.composicao_servico_id for l in SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id).all()}
    assert ids2 == {tenant['comp_mo'].id}, (
        "composição cross-tenant deve ser barrada por admin_id"
    )

    # idempotente: re-sync com mesma lista não muda nada
    _sync_composicoes_subatividade(sub, [str(tenant['comp_mo'].id)], admin_id)
    db.session.commit()
    assert SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id).count() == 1

    # remove tudo
    _sync_composicoes_subatividade(sub, [], admin_id)
    db.session.commit()
    assert SubatividadeMaoObra.query.filter_by(
        subatividade_mestre_id=sub.id).count() == 0

    # cleanup do outro tenant
    ComposicaoServico.query.filter_by(admin_id=outro.id).delete()
    Servico.query.filter_by(admin_id=outro.id).delete()
    Insumo.query.filter_by(admin_id=outro.id).delete()
    Usuario.query.filter_by(id=outro.id).delete()
    db.session.commit()
