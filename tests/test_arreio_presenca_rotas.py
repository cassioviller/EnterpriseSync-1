"""Arreio: presença por ROTA — ponto manual e sincronização do plano.

Task B0.4 do `docs/superpowers/plans/2026-08-04-plano-consolidado.md`.

Duas rotas, dois defeitos de naturezas opostas:

* ``POST /novo_ponto`` (`views/admin.py:97`) — **perde custo**. Cria
  ``RegistroPonto`` incondicionalmente (`:150`), enquanto os outros criadores do
  sistema reusam o registro do dia (`ponto_service.py:105-109`). Dois
  lançamentos manuais no mesmo dia/obra caem no ramo de UPDATE da guarda de
  idempotência (`event_manager.py:532`), e o segundo **sobrescreve** o custo do
  primeiro em vez de somar. Duas meias-jornadas viram meia jornada.
* ``POST /equipe/api/sync-ponto`` (`equipe_views.py:1213`) — **destrói dado do
  usuário**. A guarda do plano é ``tem_batida_real = bool(hora_entrada or
  hora_saida)`` (`models.py:4580-4581`), e ausência classificada não tem hora
  nenhuma: atestado e falta justificada caem no ramo de preenchimento
  (`models.py:4600-4616`) e viram ``trabalho_normal`` com 8h, em silêncio.

**Por que o teste atual não pegava.** ``tests/test_p1_fallback_e_idempotencia.py:119-135``
(``_bater_ponto``) busca o ``RegistroPonto`` já semeado e **muta esse objeto** —
por construção nunca existe mais de um registro no dia, que é a **precondição do
defeito**. Depois emite o evento à mão, pulando ``POST /novo_ponto`` inteiro, e
afirma ``len(custos) == 1`` (`:152`) — asserção que o defeito **satisfaz**. Uma
linha de custo é o sintoma, não a cura: o que faltava era relacionar horas
GRAVADAS com horas CUSTEADAS.

**Cuidado de calendário.** ``processar_lancamentos_automaticos``
(`models.py:4745`) usa ``date.today() - 1`` quando não recebe data. Todo POST
daqui manda ``data_processamento`` explícito, ancorado na semente — senão o
teste passa ou falha conforme o dia em que roda, que é a armadilha nº 13 do
`ESTADO-ATUAL.md`.
"""
import os
import sys
from datetime import date, time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import Allocation, AllocationEmployee, RegistroPonto

from helpers_dinheiro import custos_obra, soma
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

DIA = date(2026, 6, 15)
CATEGORIA_PONTO = 'PONTO_ELETRONICO'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-arreio-presenca'
    yield


def _cenario(prefixo, **perfil):
    """Tenant SEM fatos.

    ``com_fatos=False`` é obrigatório aqui por um motivo diferente do arreio de
    RDO: a rota de sync varre **todos** os funcionários ativos do tenant
    (`models.py:4760`), então um tenant com fatos pré-semeados faria a asserção
    pegar registro alheio ao cenário.
    """
    perfil.setdefault('tipo_remuneracao', 'salario')
    perfil.setdefault('valor_diaria', 0.0)
    return um_tenant(prefixo, data_ref=DIA, com_fatos=False, **perfil)


def _lancar_ponto(tenant, entrada, saida, dia=DIA):
    """``POST /novo_ponto`` — responde JSON, então o status é significativo aqui
    (ao contrário das rotas de RDO, que redirecionam com flash)."""
    cli = cliente_de(tenant.admin_id)
    return cli.post('/novo_ponto', data={
        'funcionario_id': str(tenant.funcionario_id),
        'obra_id': str(tenant.obra_id),
        'data': dia.isoformat(),
        'hora_entrada': entrada,
        'hora_saida': saida,
        'tipo_lancamento': 'trabalho_normal',
    })


def _sincronizar(tenant, dia=DIA):
    cli = cliente_de(tenant.admin_id)
    return cli.post('/equipe/api/sync-ponto',
                    json={'data_processamento': dia.isoformat()})


def _alocar(tenant, dia=DIA):
    """Allocation + AllocationEmployee do dia — a entrada do sync."""
    aloc = Allocation(admin_id=tenant.admin_id, obra_id=tenant.obra_id,
                      data_alocacao=dia, turno_inicio=time(8, 0),
                      turno_fim=time(17, 0))
    db.session.add(aloc)
    db.session.flush()
    vinculo = AllocationEmployee(
        admin_id=tenant.admin_id, allocation_id=aloc.id,
        funcionario_id=tenant.funcionario_id, turno_inicio=time(8, 0),
        turno_fim=time(17, 0), tipo_lancamento='trabalho_normal')
    db.session.add(vinculo)
    db.session.commit()
    return aloc, vinculo


def _pontos(tenant, dia=DIA):
    db.session.expire_all()
    return RegistroPonto.query.filter_by(
        funcionario_id=tenant.funcionario_id, data=dia,
        admin_id=tenant.admin_id).all()


# ---------------------------------------------------------------------------
# (a) e (b) — /novo_ponto
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason='A10 — views/admin.py:150 cria registro '
                                       'incondicional e event_manager.py:532 '
                                       'sobrescreve em vez de somar')
def test_dois_lancamentos_no_mesmo_dia_custeiam_as_horas_das_duas_metades():
    """Manhã de 4h + tarde de 4h. O dia custeado tem de valer 8h.

    Esta é a asserção que faltava: relacionar horas GRAVADAS com horas
    CUSTEADAS. Hoje ficam 2 ``RegistroPonto`` (4h + 4h) e **um** ``CustoObra``
    de meia jornada — o segundo lançamento sobrescreveu o primeiro.
    """
    with app.app_context():
        tenant = _cenario('duasmetades')

        _lancar_ponto(tenant, '08:00', '12:00')
        custo_da_manha = soma(custos_obra(tenant, DIA, CATEGORIA_PONTO))

        _lancar_ponto(tenant, '13:00', '17:00')
        custo_do_dia = soma(custos_obra(tenant, DIA, CATEGORIA_PONTO))

        registros = _pontos(tenant)
        horas_gravadas = sum(float(r.horas_trabalhadas or 0) for r in registros)

        assert horas_gravadas == pytest.approx(8.0), (
            f'precondição falhou: as duas metades gravaram {horas_gravadas}h')
        assert custo_do_dia == pytest.approx(custo_da_manha * 2), (
            f'o dia gravou {horas_gravadas}h mas custeou o equivalente a '
            f'R$ {custo_do_dia:.2f}, contra R$ {custo_da_manha:.2f} da primeira '
            f'metade sozinha — a segunda sobrescreveu a primeira')


def test_corrigir_o_horario_do_mesmo_registro_continua_dando_uma_linha():
    """A idempotência que o p1 entregou não pode ser desfeita ao consertar (a).

    Duas correções do MESMO dia — o caso legítimo — seguem produzindo uma linha
    de custo. Se consertar A10 quebrar este teste, a correção trocou um defeito
    por outro.
    """
    with app.app_context():
        tenant = _cenario('correcao')

        _lancar_ponto(tenant, '08:00', '17:00')
        _lancar_ponto(tenant, '08:00', '18:00')

        linhas = custos_obra(tenant, DIA, CATEGORIA_PONTO)
        assert len(linhas) == 1, (
            f'a correção do horário criou linha nova: {len(linhas)} no total')


# ---------------------------------------------------------------------------
# (c) e (d) — sincronização do plano
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason='A16 — a guarda tem_batida_real '
                                       '(models.py:4580-4581) não cobre '
                                       'ausência classificada')
def test_o_sync_do_plano_nao_sobrescreve_atestado():
    """Um atestado lançado à mão não pode virar dia trabalhado de 8h.

    ``ponto_service.py:330-360`` cria a ausência **sem hora nenhuma**, então
    ``tem_batida_real`` é False e o registro cai no ramo de preenchimento:
    ``models.py:4602`` grava a obra do plano, ``:4614`` devolve
    ``tipo_registro`` para ``'trabalho_normal'`` e ``:4616`` põe 8h.

    Perda de dado do usuário, em silêncio — e alcançável tanto pelo cron
    (`models.py:4772-4774`) quanto por esta rota.
    """
    with app.app_context():
        tenant = _cenario('atestado')
        db.session.add(RegistroPonto(
            funcionario_id=tenant.funcionario_id, admin_id=tenant.admin_id,
            data=DIA, tipo_registro='atestado', horas_trabalhadas=0.0))
        db.session.commit()
        _alocar(tenant)

        _sincronizar(tenant)

        registros = _pontos(tenant)
        assert len(registros) == 1, (
            f'esperava um registro no dia, achou {len(registros)}')
        registro = registros[0]
        assert registro.tipo_registro == 'atestado', (
            f"o atestado virou '{registro.tipo_registro}' com "
            f'{registro.horas_trabalhadas}h — o plano sobrescreveu a ausência')
        assert float(registro.horas_trabalhadas or 0) == pytest.approx(0.0)


@pytest.mark.xfail(strict=True, reason='A16 — o ponto nascido do plano não '
                                       'emite ponto_registrado, e ainda suprime '
                                       'o custo que o RDO geraria')
def test_o_ponto_criado_pelo_sync_gera_custo():
    """O dia planejado que vira ponto tem de custar.

    E a consequência é pior que "entra sem custo": ``services/rdo_custos.py:368-373``
    pula o lançamento do RDO justificando *"já tem ponto, o custo virá pelo
    handler"* — handler que nunca roda, porque nada em ``models.py`` emite
    ``ponto_registrado`` no caminho do plano. Não é "entra sem custo", é
    **perde** o custo que o RDO teria gerado.
    """
    with app.app_context():
        tenant = _cenario('planocusto', tipo_remuneracao='diaria',
                          valor_diaria=150.0)
        _alocar(tenant)

        _sincronizar(tenant)

        registros = _pontos(tenant)
        assert len(registros) == 1, (
            f'o sync não criou o registro de ponto: {len(registros)}')

        linhas = custos_obra(tenant, DIA, CATEGORIA_PONTO)
        assert len(linhas) >= 1, (
            'o plano criou o ponto do dia e nenhum custo saiu dele')


# ---------------------------------------------------------------------------
# Piso do arreio
# ---------------------------------------------------------------------------

def test_um_lancamento_de_ponto_gera_um_custo():
    """Se ESTE quebrar, o problema é o cenário, não A10."""
    with app.app_context():
        tenant = _cenario('piso')
        resposta = _lancar_ponto(tenant, '08:00', '17:00')

        assert resposta.status_code == 200, (
            f'/novo_ponto respondeu {resposta.status_code}: '
            f'{resposta.get_data(as_text=True)[:200]}')
        assert len(_pontos(tenant)) == 1
        assert len(custos_obra(tenant, DIA, CATEGORIA_PONTO)) == 1
