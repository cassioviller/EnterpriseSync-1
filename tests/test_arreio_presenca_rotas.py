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
from models import Allocation, AllocationEmployee, Obra, RegistroPonto

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

def test_dois_lancamentos_no_mesmo_dia_custeiam_as_horas_das_duas_metades():
    """Manhã de 4h + tarde de 4h. O dia custeado tem de valer 8h.

    Esta é a asserção que faltava: relacionar horas GRAVADAS com horas
    CUSTEADAS. Antes da B1.6/B1.7 ficavam 2 ``RegistroPonto`` (4h + 4h) e **um**
    ``CustoObra`` de meia jornada — o segundo lançamento sobrescrevia o primeiro.

    🔬 **A regra que este teste congela foi uma decisão, não uma dedução.** O
    mesmo formulário serve à correção e ao turno partido, e só os horários os
    distinguem: lançamento que COMEÇA depois de o registrado terminar é a
    segunda metade do dia; lançamento que se sobrepõe é correção (é o teste
    seguinte). A alternativa descartada era tratar tudo como correção — o
    sistema ficaria coerente consigo mesmo dizendo que o dia teve 4h, e a manhã
    sumiria do registro do trabalhador.
    """
    with app.app_context():
        tenant = _cenario('duasmetades')

        _lancar_ponto(tenant, '08:00', '12:00')
        custo_da_manha = soma(custos_obra(tenant, DIA, CATEGORIA_PONTO))

        _lancar_ponto(tenant, '13:00', '17:00')
        custo_do_dia = soma(custos_obra(tenant, DIA, CATEGORIA_PONTO))

        registros = _pontos(tenant)
        horas_gravadas = sum(float(r.horas_trabalhadas or 0) for r in registros)

        assert len(registros) == 1, (
            f'o dia deveria ter UM registro com almoço, e tem {len(registros)}')
        assert horas_gravadas == pytest.approx(8.0), (
            f'precondição falhou: as duas metades gravaram {horas_gravadas}h')
        assert custo_do_dia == pytest.approx(custo_da_manha * 2), (
            f'o dia gravou {horas_gravadas}h mas custeou o equivalente a '
            f'R$ {custo_do_dia:.2f}, contra R$ {custo_da_manha:.2f} da primeira '
            f'metade sozinha — a segunda sobrescreveu a primeira')

        r = registros[0]
        assert (r.hora_entrada.strftime('%H:%M'),
                r.hora_almoco_saida.strftime('%H:%M'),
                r.hora_almoco_retorno.strftime('%H:%M'),
                r.hora_saida.strftime('%H:%M')) == ('08:00', '12:00', '13:00', '17:00'), (
            f'o turno partido não virou almoço: {r.hora_entrada}-'
            f'{r.hora_almoco_saida} / {r.hora_almoco_retorno}-{r.hora_saida}')


def test_trocar_a_obra_do_dia_nao_cobra_o_dia_duas_vezes():
    """Lançar na obra 1 e depois na obra 2, no mesmo dia.

    Era o pior dos dois cenários do A10, e o menos citado: a chave do custo
    incluía ``obra_id``, então os dois lançamentos não se enxergavam e viravam
    DOIS ``CustoObra`` — o dia cobrado em dobro por horas que ninguém trabalhou.

    A regra agora é: um custo de ponto por (funcionário, dia), na obra que o
    registro do dia aponta. Corrigir a obra MOVE o custo; não deixa órfão atrás.
    """
    with app.app_context():
        tenant = _cenario('trocaobra')

        outra = Obra(nome=f'Obra 2 {tenant.marca}', codigo=f'{tenant.marca[:8]}2',
                     admin_id=tenant.admin_id, cliente_id=tenant.cliente_id,
                     data_inicio=DIA)
        db.session.add(outra)
        db.session.commit()

        _lancar_ponto(tenant, '08:00', '17:00')

        cli = cliente_de(tenant.admin_id)
        cli.post('/novo_ponto', data={
            'funcionario_id': str(tenant.funcionario_id),
            'obra_id': str(outra.id),
            'data': DIA.isoformat(),
            'hora_entrada': '08:00',
            'hora_saida': '17:00',
            'tipo_lancamento': 'trabalho_normal',
        })

        registros = _pontos(tenant)
        # `qualquer_obra=True` é o ponto do teste: a invariante é ENTRE obras.
        linhas = custos_obra(tenant, DIA, CATEGORIA_PONTO, qualquer_obra=True)

        assert len(registros) == 1, (
            f'a troca de obra criou registro novo: {len(registros)} no dia')
        assert len(linhas) == 1, (
            f'o dia foi cobrado {len(linhas)} vezes — uma por obra. A chave do '
            f'custo voltou a incluir obra_id')
        assert linhas[0].obra_id == registros[0].obra_id == outra.id, (
            f'o custo ficou na obra {linhas[0].obra_id} e o registro aponta '
            f'{registros[0].obra_id} — o custo não seguiu a correção')


def test_ponto_de_funcionario_de_outro_tenant_e_recusado():
    """A rota é `@login_required` **sem** `@admin_required` (`views/admin.py:99`),
    então o isolamento depende inteiramente do filtro por `admin_id` de `:118`.
    Com o merge da B1.7, um vazamento aqui passaria a ALTERAR registro alheio em
    vez de só criar um — o que torna esta asserção mais necessária que antes."""
    with app.app_context():
        a = _cenario('tenantA')
        b = _cenario('tenantB')

        cli = cliente_de(a.admin_id)
        r = cli.post('/novo_ponto', data={
            'funcionario_id': str(b.funcionario_id),
            'obra_id': str(a.obra_id),
            'data': DIA.isoformat(),
            'hora_entrada': '08:00',
            'hora_saida': '17:00',
        })

        assert r.status_code == 404, (
            f'a rota respondeu {r.status_code} para funcionário de outro tenant')
        assert len(_pontos(b)) == 0, (
            'o tenant A gravou ponto no funcionário do tenant B')


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

@pytest.mark.parametrize('tipo', ['atestado', 'ATESTADO', 'FALTA_J', 'ferias',
                                  'licenca_inventada_2026'])
def test_o_sync_do_plano_nao_sobrescreve_ausencia_classificada(tipo):
    """Uma ausência lançada à mão não pode virar dia trabalhado de 8h.

    ``ponto_service.py:330-360`` cria a ausência **sem hora nenhuma**, então a
    guarda antiga (``bool(hora_entrada or hora_saida)``) era False e o registro
    caía no ramo de preenchimento: ``models.py:4602`` gravava a obra do plano,
    ``:4614`` devolvia ``tipo_registro`` para ``'trabalho_normal'`` e ``:4616``
    punha 8h.

    Perda de dado do usuário, em silêncio — e alcançável tanto pelo cron
    (`models.py:4772-4774`) quanto por esta rota.

    🔬 A parametrização é o teste de verdade aqui, e cada valor cobre um caminho
    de entrada diferente: minúscula é a rota de falta, CAIXA ALTA é o importador
    de Excel (`services/ponto_importacao.py:598-599`), e o último é string livre
    — `ponto_views.py:1016` persiste `motivo` cru, sem allowlist, então tipo
    desconhecido não é hipótese, é entrada normal. Ele prova o **fail-closed**:
    a guarda protege o que não sabe interpretar.
    """
    with app.app_context():
        tenant = _cenario(f'aus{abs(hash(tipo)) % 10000}')
        db.session.add(RegistroPonto(
            funcionario_id=tenant.funcionario_id, admin_id=tenant.admin_id,
            data=DIA, tipo_registro=tipo, horas_trabalhadas=0.0))
        db.session.commit()
        aloc, vinculo = _alocar(tenant)

        _sincronizar(tenant)

        registros = _pontos(tenant)
        assert len(registros) == 1, (
            f'esperava um registro no dia, achou {len(registros)}')
        registro = registros[0]
        assert registro.tipo_registro == tipo, (
            f"a ausência '{tipo}' virou '{registro.tipo_registro}' com "
            f'{registro.horas_trabalhadas}h — o plano sobrescreveu a ausência')
        assert float(registro.horas_trabalhadas or 0) == pytest.approx(0.0)
        assert registro.hora_entrada is None and registro.hora_saida is None, (
            f'o plano carimbou horário sobre a ausência: '
            f'{registro.hora_entrada}-{registro.hora_saida}')
        assert registro.obra_id is None, (
            f'o plano vinculou a ausência à obra {registro.obra_id}')

        db.session.expire_all()
        assert vinculo.sincronizado_ponto is True, (
            'a alocação protegida não foi marcada como sincronizada — o cron '
            'vai reprocessá-la todo dia (o defeito que o p7 travou)')


def test_o_sync_busca_o_registro_dentro_do_tenant():
    """O registro de outro tenant não pode nem proteger nem ser escrito.

    🔬 `funcionario_id` é global, e a busca de `sincronizar_com_ponto` era só
    (`funcionario_id`, `data`). Duas consequências opostas e ambas ruins: a
    guarda decidiria olhando o `tipo_registro` de um registro alheio, e o ramo de
    preenchimento escreveria nele.

    **A B1.10 piorou isso antes de a B1.11 consertar**, e é por isso que as duas
    andam juntas: com a guarda nova, um atestado de OUTRA empresa passaria a
    proteger o dia deste tenant, e o plano deixaria de converter sem ninguém
    entender a causa.

    🔬 **A primeira versão deste teste era vacuosa**, e vale registrar por quê:
    ela semeava o registro do funcionário de B, mas cada tenant tem o SEU
    funcionário, com id próprio — a colisão que ela dizia montar não existia, e
    o teste passava com e sem o filtro.

    O cenário verdadeiro é dado sujo: uma linha com o funcionário de A e o
    ``admin_id`` de B. É a divergência que a Task mandou contar antes de aplicar
    (zero em dev, 90 pares casados), e é a única forma de a busca antiga achar
    algo que não é dela.
    """
    with app.app_context():
        a = _cenario('syncA')
        b = _cenario('syncB')

        # Linha suja: funcionário de A, tenant de B, tipo que a guarda protege.
        alheio = RegistroPonto(
            funcionario_id=a.funcionario_id, admin_id=b.admin_id,
            data=DIA, tipo_registro='atestado', horas_trabalhadas=0.0)
        db.session.add(alheio)
        db.session.commit()
        alheio_id = alheio.id

        _alocar(a)
        _sincronizar(a)

        db.session.expire_all()
        sujo = RegistroPonto.query.get(alheio_id)
        assert sujo.tipo_registro == 'atestado', (
            f"o sync de A reescreveu a linha do tenant B: "
            f"'{sujo.tipo_registro}'")
        assert sujo.hora_entrada is None, (
            'o sync de A carimbou horário na linha do tenant B')

        registros_de_a = _pontos(a)
        assert len(registros_de_a) == 1, (
            f'o tenant A deveria ter um registro próprio no dia, tem '
            f'{len(registros_de_a)} — a busca achou a linha de B e a guarda '
            f'protegeu o dia errado')
        assert registros_de_a[0].hora_entrada == time(8, 0), (
            'o registro de A não foi preenchido pelo plano')


def test_o_sync_do_plano_preenche_o_registro_vazio_legitimo():
    """O contrapeso do teste acima: o caso legítimo não pode morrer.

    Registro neutro e vazio — semeado por outra rodada do plano — é exatamente o
    que o sync existe para preencher. Uma guarda estreita demais custa dado do
    usuário; uma guarda larga demais desliga a funcionalidade inteira, e sem
    barulho nenhum.
    """
    with app.app_context():
        tenant = _cenario('vazio')
        db.session.add(RegistroPonto(
            funcionario_id=tenant.funcionario_id, admin_id=tenant.admin_id,
            data=DIA, tipo_registro='trabalho_normal', horas_trabalhadas=0.0))
        db.session.commit()
        _alocar(tenant)

        _sincronizar(tenant)

        registro = _pontos(tenant)[0]
        assert registro.hora_entrada == time(8, 0), (
            f'o plano não preencheu a entrada: {registro.hora_entrada}')
        assert registro.hora_saida == time(17, 0)
        assert registro.obra_id == tenant.obra_id, (
            'o plano não vinculou o registro vazio à obra da alocação')


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
