"""Arreio: custo de RDO por ROTA — as três rotas vivas, o mesmo cenário.

Task B0.3 do `docs/superpowers/plans/2026-08-04-plano-consolidado.md`.

**O que este arquivo mede que nenhum outro media.** A suíte sabia postar em rota
e sabia afirmar sobre banco, mas nunca ligou as duas coisas no caminho do
dinheiro. Aqui um MESMO funcionário mensalista, uma MESMA obra e um MESMO dia
passam pelas três rotas de RDO, e o teste pergunta a única coisa que importa:
**quanto custo sobrou no banco.**

A referência é `POST /salvar-rdo-flexivel` (`views/rdo.py:3612`) — a única das
três que chama `gerar_custos_mao_obra_rdo` (`:4489`) **e** emite o evento com
`obra_id` (`:4500-4504`). As outras duas se comparam a ela. O valor esperado
**não é chumbado**: sai do que a rota de referência produziu no próprio teste.
Chumbar R$ 124,00 amarraria o arreio ao mês em que foi escrito, porque o valor
sai de `salario / (dias_úteis × horas_diárias)`.

**Por que os testes atuais não pegavam.** `tests/test_p1_dedup_cross_origem.py:151-165`
abre `rdo_editar_sistema.py` e `crud_rdo_completo.py` como TEXTO e verifica se a
string ``"EventManager.emit('rdo_finalizado'"`` aparece — ela aparece, e o teste
fica verde enquanto o banco não recebe um centavo. Os dois testes de
comportamento do mesmo arquivo (`:98-114`, `:117-130`) emitem o evento à mão,
pulando a rota inteira, afirmam ``<= 1`` (verdadeiro para zero) e usam um tenant
que já traz `RegistroPonto` na data — o que faz `existe_ponto_no_dia`
(`event_manager.py:722-726`) pular o lançamento antes de o defeito ser
alcançado.

**Marcação.** Os casos que dependem de A05 entram com
``xfail(strict=True)``: `strict` faz o teste **falhar quando o defeito for
corrigido** e alguém esquecer de tirar a marca. É de propósito — o xfail é o
checklist de B1, não um TODO.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import ContaReceber, RDO

from helpers_dinheiro import (custo_diario, filhos_mao_de_obra,
                              linhas_mao_de_obra, mao_de_obra, form_rdo,
                              rdo_da_obra, soma, tarefa_da_obra)
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration

# Dia sem nenhum RegistroPonto semeado — ver o docstring de `um_tenant`.
DIA = date(2026, 6, 15)
# Segundo dia, para comparar rotas dentro do MESMO tenant — ver a nota de
# `test_finalizar_produz_o_mesmo_custo_que_a_rota_de_referencia`.
OUTRO_DIA = date(2026, 6, 16)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-arreio-rdo'
    yield


def _cenario(prefixo, **perfil):
    """Tenant limpo + tarefa de cronograma. Um por teste, de propósito:
    reaproveitar tenant entre casos faria a contagem de um vazar no outro."""
    perfil.setdefault('tipo_remuneracao', 'salario')
    perfil.setdefault('valor_diaria', 0.0)
    perfil.setdefault('salario', 3000.0)
    tenant = um_tenant(prefixo, data_ref=DIA, com_fatos=False, **perfil)
    tarefa = tarefa_da_obra(tenant)
    return tenant, tarefa


def _servico_do_tenant(tenant):
    """Um `Servico` ativo do tenant.

    🔬 Só `POST /rdo/salvar` precisa disto, e o motivo é uma armadilha da rota:
    quando o formulário não traz campo de subatividade, ela tenta um fallback
    (`views/rdo.py:3183-3199`) que pega o PRIMEIRO `Servico` do admin; sem
    nenhum, ela dá ``flash`` + ``redirect`` em `:3199` — **antes** de parsear a
    mão de obra (`:3354`) e antes do bloco de custo. O RDO já criado fica órfão,
    com `status='Finalizado'`, zero mão de obra e zero subatividade, e a rota
    responde 302 como se nada houvesse. Sem este serviço, qualquer assert de
    dinheiro sobre esta rota mede o abandono, não o lançamento.
    """
    from models import Servico
    s = Servico(nome=f'Servico {tenant.marca}', categoria='geral',
                unidade_medida='un', custo_unitario=100.0, ativo=True,
                admin_id=tenant.admin_id)
    db.session.add(s)
    db.session.commit()
    return s


def _ok(resposta):
    """Status é PRÉ-FILTRO, nunca prova.

    As rotas capturam quase tudo em `except` amplo e redirecionam com flash de
    erro (`crud_rdo_completo.py:487-509`, `rdo_editar_sistema.py:566-585`), então
    302 pode ser sucesso ou desastre. Quem decide é linha de banco — este helper
    só barra o 401/500 óbvio.
    """
    assert resposta.status_code in (200, 302), (
        f'rota respondeu {resposta.status_code} — nem sucesso nem redirect')


def _via_flexivel(tenant, tarefa, dia=DIA, horas=8.0):
    """A rota de REFERÊNCIA. Cria o RDO a partir do formulário."""
    cli = cliente_de(tenant.admin_id)
    form = form_rdo(tenant, dia, tarefa_id=tarefa.id, horas=horas)
    form['funcionario_id'] = str(tenant.funcionario_id)
    _ok(cli.post('/salvar-rdo-flexivel', data=form))


def _via_finalizar(tenant, tarefa, dia=DIA, horas=8.0):
    """`POST /rdo/finalizar/<id>`. Exige RDO com mão de obra ANTES do POST —
    sem isso a rota sai por `crud_rdo_completo.py:576-578` com flash+redirect."""
    rdo = rdo_da_obra(tenant, dia)
    mao_de_obra(rdo, tenant, horas=horas, tarefa=tarefa)
    cli = cliente_de(tenant.admin_id)
    _ok(cli.post(f'/rdo/finalizar/{rdo.id}',
                 data=form_rdo(tenant, dia, tarefa_id=tarefa.id, horas=horas)))
    return rdo


def _via_editar(tenant, tarefa, dia=DIA, horas=8.0):
    """`POST /rdo/editar/<id>`. A rota APAGA e reescreve a mão de obra a partir
    do formulário (`rdo_editar_sistema.py:445-491`) — por isso o form carrega as
    chaves `cron_tarefa_*`, e por isso o chamador confere `RDOMaoObra` depois."""
    rdo = rdo_da_obra(tenant, dia)
    mao_de_obra(rdo, tenant, horas=horas, tarefa=tarefa)
    cli = cliente_de(tenant.admin_id)
    _ok(cli.post(f'/rdo/editar/{rdo.id}',
                 data=form_rdo(tenant, dia, tarefa_id=tarefa.id, horas=horas)))
    return rdo


# ---------------------------------------------------------------------------
# A referência — o que a rota boa produz
# ---------------------------------------------------------------------------

def test_a_rota_de_referencia_gera_custo_para_mensalista():
    """Piso do arreio. Se ESTE quebrar, o problema não é A05 — é o cenário."""
    with app.app_context():
        tenant, tarefa = _cenario('ref')
        _via_flexivel(tenant, tarefa)

        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1, (
            f'a rota de referência não gerou custo — o cenário está errado, '
            f'não o código. Encontrou {len(linhas)} linha(s).')
        assert soma(linhas) > 0


# ---------------------------------------------------------------------------
# (a) e (b) — paridade entre as rotas
# ---------------------------------------------------------------------------

def test_finalizar_produz_o_mesmo_custo_que_a_rota_de_referencia():
    """Paridade em UM tenant, duas datas.

    🔬 A primeira versão usava dois tenants no mesmo ``app_context`` e media
    errado: o segundo POST não completava, e o teste acusava R$ 0,00 tanto na
    presença do defeito quanto na sua ausência. Duas datas isolam o custo sem
    precisar de segundo tenant — e sem a contaminação.
    """
    with app.app_context():
        tenant, tarefa = _cenario('parfin')

        _via_flexivel(tenant, tarefa, dia=DIA)
        esperado = soma(filhos_mao_de_obra(tenant, DIA))
        assert esperado > 0, 'a referência não gerou custo — cenário quebrado'

        _via_finalizar(tenant, tarefa, dia=OUTRO_DIA)

        obtido = soma(filhos_mao_de_obra(tenant, OUTRO_DIA))
        assert obtido == pytest.approx(esperado), (
            f'/rdo/finalizar rendeu R$ {obtido:.2f} onde a referência rendeu '
            f'R$ {esperado:.2f}')


def test_editar_produz_o_mesmo_custo_que_a_rota_de_referencia():
    """Mesma estrutura do teste acima: um tenant, duas datas."""
    with app.app_context():
        tenant, tarefa = _cenario('paredit')

        _via_flexivel(tenant, tarefa, dia=DIA)
        esperado = soma(filhos_mao_de_obra(tenant, DIA))
        assert esperado > 0, 'a referência não gerou custo — cenário quebrado'

        rdo = _via_editar(tenant, tarefa, dia=OUTRO_DIA)

        # A equipe tem de ter sobrevivido ao POST, senão o assert de dinheiro
        # abaixo seria vacuoso: zero custo porque zero gente.
        assert len(linhas_mao_de_obra(rdo.id)) == 1, (
            'o POST apagou a mão de obra — o formulário não carregava as '
            'chaves cron_tarefa_*, e este teste mediria o apagamento')

        obtido = soma(filhos_mao_de_obra(tenant, OUTRO_DIA))
        assert obtido == pytest.approx(esperado), (
            f'/rdo/editar rendeu R$ {obtido:.2f} onde a referência rendeu '
            f'R$ {esperado:.2f}')


# ---------------------------------------------------------------------------
# (c) — o payload carrega obra_id, provado pelo EFEITO
# ---------------------------------------------------------------------------

def _semear_cr_sentinela(tenant):
    """ContaReceber OBRA_MEDICAO com valor deliberadamente errado.

    `recalcular_medicao_obra` sobrescreve `valor_original` com o medido
    (`services/medicao_service.py:393`). Se o handler rodar, a sentinela some;
    se `recalcular_medicao_apos_rdo` sair por falta de `obra_id`
    (`event_manager.py:1529-1531`), ela fica. É o efeito observável mais barato
    — e não lê o dict do evento, que é o que o plano proíbe.
    """
    cr = ContaReceber(
        cliente_nome='Sentinela', obra_id=tenant.obra_id,
        numero_documento=f'OBR-MED-{tenant.obra_id:05d}',
        descricao='sentinela do arreio',
        valor_original=Decimal('777.00'), valor_recebido=Decimal('0'),
        saldo=Decimal('777.00'), data_emissao=DIA, data_vencimento=DIA,
        status='PENDENTE', origem_tipo='OBRA_MEDICAO',
        origem_id=tenant.obra_id, admin_id=tenant.admin_id)
    db.session.add(cr)
    db.session.commit()
    return cr


def _sentinela_intacta(tenant):
    db.session.expire_all()
    cr = ContaReceber.query.filter_by(
        admin_id=tenant.admin_id, origem_tipo='OBRA_MEDICAO',
        origem_id=tenant.obra_id).first()
    return cr is not None and float(cr.valor_original) == 777.00


def test_a_rota_de_referencia_dispara_o_recalculo_da_medicao():
    with app.app_context():
        tenant, tarefa = _cenario('medref')
        _semear_cr_sentinela(tenant)
        _via_flexivel(tenant, tarefa)

        assert not _sentinela_intacta(tenant), (
            'a sentinela sobreviveu: o recálculo de medição não rodou nem pela '
            'rota de referência')


# B1.4 — verde desde que os payloads levam obra_id e o handler resolve sozinho.

def test_finalizar_dispara_o_recalculo_da_medicao():
    with app.app_context():
        tenant, tarefa = _cenario('medfin')
        _semear_cr_sentinela(tenant)
        _via_finalizar(tenant, tarefa)

        assert not _sentinela_intacta(tenant), (
            'a sentinela sobreviveu: o evento chegou sem obra_id e '
            'recalcular_medicao_apos_rdo saiu antes de recalcular')


# ---------------------------------------------------------------------------
# (d) — reexecutar não duplica
# ---------------------------------------------------------------------------

def test_reexecutar_o_mesmo_rdo_nao_duplica_o_custo():
    """A idempotência que o p1 entregou não pode ser desfeita ao consertar A05.

    Usa diarista de propósito: é o único perfil que hoje gera custo pelas rotas
    de edição/finalização, então o teste mede a idempotência de verdade em vez
    de comparar zero com zero.
    """
    with app.app_context():
        tenant, tarefa = _cenario('idem', tipo_remuneracao='diaria',
                                  valor_diaria=150.0)
        rdo = rdo_da_obra(tenant, DIA)
        mao_de_obra(rdo, tenant, horas=8.0, tarefa=tarefa)
        cli = cliente_de(tenant.admin_id)
        form = form_rdo(tenant, DIA, tarefa_id=tarefa.id, horas=8.0)

        _ok(cli.post(f'/rdo/editar/{rdo.id}', data=form))
        depois_de_uma = filhos_mao_de_obra(tenant, DIA)

        _ok(cli.post(f'/rdo/editar/{rdo.id}', data=form))
        depois_de_duas = filhos_mao_de_obra(tenant, DIA)

        assert len(depois_de_uma) == 1
        assert len(depois_de_duas) == 1, (
            f'a segunda passada no MESMO RDO criou linha nova: '
            f'{len(depois_de_duas)} no total')
        assert soma(depois_de_duas) == pytest.approx(150.0)


def test_mensalista_em_dois_rdos_custeia_as_horas_reportadas():
    """Congela a regra do mensalista, que **não** tem teto diário — e não deveria ter.

    🔬 Medido nos três arranjos, para deixar a regra sem ambiguidade:
    8h em um RDO = R$ 124,00; 4h+4h em dois = R$ 62,00 + R$ 62,00 = R$ 124,00;
    8h+8h em dois = R$ 248,00. O custo é ``horas × valor_hora``
    (`services/custo_funcionario_dia.py:113-116`), e a soma do dia acompanha as
    horas **reportadas**.

    O ``proporcao`` de `:81` é aplicado ao diarista (`:97`) e a VA/VT (`:87-88`),
    onde a unidade é o DIA, e deliberadamente **não** ao mensalista, onde a
    unidade é a hora. Aplicá-lo ali quebraria o caso 4h+4h, que passaria a
    custar meia jornada por uma jornada inteira.

    Este teste existe porque a leitura ingênua do cabeçalho do módulo (`:9-11`,
    "rateio proporcional quando o funcionário aparece em >1 RDO no mesmo dia")
    sugere um teto que não existe para o mensalista. Se alguém "consertar" isso,
    o teste explica por que não era defeito.
    """
    with app.app_context():
        tenant, tarefa = _cenario('doisrdo')

        _via_flexivel(tenant, tarefa, horas=4.0)
        depois_do_primeiro = soma(filhos_mao_de_obra(tenant, DIA))

        _via_flexivel(tenant, tarefa, horas=4.0)
        linhas = filhos_mao_de_obra(tenant, DIA)
        total = soma(linhas)

        assert len(linhas) == 2, (
            f'dois RDOs deveriam render duas linhas de custo, achou {len(linhas)}')
        assert total == pytest.approx(depois_do_primeiro * 2), (
            f'as duas metades de 4h renderam R$ {total:.2f}, e a primeira '
            f'sozinha rendeu R$ {depois_do_primeiro:.2f} — o custo do '
            f'mensalista deve escalar com as horas reportadas')


def test_o_razao_acompanha_o_recalculo_cruzado_da_diaria():
    """Diarista em dois RDOs do mesmo dia: a fonte e o razão têm de fechar.

    A diária **tem** teto — é uma por dia, rateada entre os RDOs
    (`services/custo_funcionario_dia.py:95-97`), e o módulo promete recalcular os
    RDOs vizinhos quando a proporção muda (`:18-19`). Até a B1.5b a promessa era
    cumprida na tabela de origem e **não** no razão:

        RDOCustoDiario   = [75,00 · 75,00]  → R$ 150,00  ✅ uma diária
        GestaoCustoFilho = [150,00 · 75,00] → R$ 225,00  ❌ uma diária e meia

    O primeiro lançamento nascia com 150,00 quando era o único RDO do dia; quando
    o segundo chegava e a proporção virava 50/50, o vizinho era recalculado na
    origem, mas a guarda de idempotência encontrava o filho existente e fazia
    ``continue`` em vez de atualizar o valor. **Idempotência que ignora mudança
    de valor vira dado velho.**

    🔬 Este teste nasceu `xfail(strict=True)` no B0 e a marca saiu na B1.5b, que
    fez a chave larga de `event_manager.py:933` distinguir origem e reconciliar
    valor. Ele é irmão de `test_mensalista_em_dois_rdos_custeia_as_horas_reportadas`:
    os dois medem o mesmo dia partido em dois RDOs, e é a diferença entre eles
    que define a regra — o diarista tem teto diário, o mensalista não, porque a
    unidade de um é o DIA e a do outro é a HORA.
    """
    with app.app_context():
        tenant, tarefa = _cenario('razao', tipo_remuneracao='diaria',
                                  valor_diaria=150.0)

        _via_flexivel(tenant, tarefa, horas=8.0)
        _via_flexivel(tenant, tarefa, horas=8.0)

        no_razao = soma(filhos_mao_de_obra(tenant, DIA))
        rdos = RDO.query.filter_by(obra_id=tenant.obra_id,
                                   data_relatorio=DIA).all()
        na_origem = sum(soma(custo_diario(r.id), campo='componente_folha')
                        for r in rdos)

        assert no_razao == pytest.approx(na_origem), (
            f'a origem diz R$ {na_origem:.2f} e o razão diz R$ {no_razao:.2f} — '
            f'o recálculo cruzado não alcançou o GestaoCustoFilho já criado')

        _assert_pais_fecham_com_os_filhos(tenant)


def test_editar_as_horas_para_baixo_corrige_o_custo_e_o_total_do_pai():
    """Reprocessar o MESMO RDO com menos horas tem de reduzir o custo.

    8h → R$ 124,00; as mesmas 8h corrigidas para 4h → R$ 62,00. O que o teste
    exige é que os andares fechem: `GestaoCustoFilho` e `GestaoCustoPai.valor_total`.

    🔬 **O que este teste NÃO prova, para não enganar quem o ler.** Medido: a
    rota de edição APAGA o custo antes de reescrever
    (`rdo_editar_sistema.py:357-363`), então ela nunca entra no ramo de
    reconciliação da B1.5b — ela remove e insere. E, na inserção,
    `registrar_custo_automatico` recomputa `pai.valor_total` somando os filhos
    (`utils/financeiro_integration.py:177-181`), de modo que o pai se autocura
    aqui mesmo sem o ajuste por delta do handler. Confirmado desligando o
    ajuste: este teste continua verde.

    Ele vale pelo que afirma de fato — que corrigir horas para baixo corrige o
    dinheiro para baixo, nos dois andares — e o
    `_assert_pais_fecham_com_os_filhos` fica como invariante de casa, não como
    prova do delta.
    """
    with app.app_context():
        tenant, tarefa = _cenario('reproc')

        rdo = _via_editar(tenant, tarefa, horas=8.0)
        oito_horas = soma(filhos_mao_de_obra(tenant, DIA))
        assert oito_horas > 0, 'o cenário não gerou custo — nada a reprocessar'
        _assert_pais_fecham_com_os_filhos(tenant)

        cli = cliente_de(tenant.admin_id)
        _ok(cli.post(f'/rdo/editar/{rdo.id}',
                     data=form_rdo(tenant, DIA, tarefa_id=tarefa.id, horas=4.0)))

        quatro_horas = soma(filhos_mao_de_obra(tenant, DIA))
        assert quatro_horas == pytest.approx(oito_horas / 2), (
            f'corrigir 8h para 4h deveria levar o custo de R$ {oito_horas:.2f} '
            f'para R$ {oito_horas / 2:.2f}, e o razão diz R$ {quatro_horas:.2f} '
            f'— a idempotência voltou a ignorar mudança de valor')

        _assert_pais_fecham_com_os_filhos(tenant)


def _assert_pais_fecham_com_os_filhos(tenant):
    """`GestaoCustoPai.valor_total` tem de bater com a soma dos seus filhos.

    🔬 O total do pai **não é derivado**: é somatório mantido à mão a cada
    inserção (`utils/financeiro_integration.py:222`). Toda reconciliação de
    valor de filho tem de ajustá-lo pelo delta, senão a B1.5b consertaria a
    divergência entre origem e razão criando a mesma divergência um andar
    acima — entre o pai e os próprios filhos.

    Hoje a inserção que costuma vir logo depois recomputa o total somando os
    filhos (`:177-181`) e encobre o problema; por isso este assert é
    **invariante de casa**, não prova de um defeito atual. Ele existe para o
    dia em que alguém reconciliar valor sem inserir nada em seguida.
    """
    from models import GestaoCustoPai, GestaoCustoFilho
    db.session.expire_all()
    pais = GestaoCustoPai.query.filter_by(admin_id=tenant.admin_id).all()
    for pai in pais:
        filhos = GestaoCustoFilho.query.filter_by(pai_id=pai.id).all()
        if not filhos:
            continue
        soma_filhos = sum(float(f.valor or 0) for f in filhos)
        assert float(pai.valor_total or 0) == pytest.approx(soma_filhos), (
            f'pai {pai.id} ({pai.tipo_categoria}) diz R$ '
            f'{float(pai.valor_total or 0):.2f} e seus {len(filhos)} filho(s) '
            f'somam R$ {soma_filhos:.2f} — a reconciliação mexeu no filho e '
            f'esqueceu o total do pai')


# ---------------------------------------------------------------------------
# (e) — matriz de perfis
# ---------------------------------------------------------------------------

def test_diarista_gera_custo_pela_rota_de_finalizar():
    """O diarista passa porque `valor_diaria > 0` — é o único perfil que o
    handler do evento sabe custear (`event_manager.py:730-733`). Serve de
    controle: prova que a rota funciona e que o defeito é do PERFIL, não da rota."""
    with app.app_context():
        tenant, tarefa = _cenario('diarista', tipo_remuneracao='diaria',
                                  valor_diaria=150.0)
        _via_finalizar(tenant, tarefa)

        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1, (
            f'nem o diarista gerou custo por /rdo/finalizar — o defeito é maior '
            f'do que A05 descreve. Encontrou {len(linhas)}.')
        assert soma(linhas) == pytest.approx(150.0)


def test_mensalista_gera_custo_pela_rota_de_finalizar():
    """O espelho do anterior. A diferença entre os dois é UMA coluna do
    funcionário — e é ela que hoje decide se o dia custa ou não custa nada."""
    with app.app_context():
        tenant, tarefa = _cenario('mensal')
        _via_finalizar(tenant, tarefa)

        linhas = filhos_mao_de_obra(tenant, DIA)
        assert len(linhas) == 1, (
            f'mensalista não gerou custo por /rdo/finalizar: {len(linhas)} linha(s)')


# ---------------------------------------------------------------------------
# (g) — a assinatura estrutural do defeito
# ---------------------------------------------------------------------------

def test_custo_diario_gravado_implica_lancamento_na_gestao_de_custos():
    """A asserção mais barata de todas, e a que descreve o defeito com precisão:
    se `RDOCustoDiario.componente_folha > 0`, alguém calculou o custo do dia.
    Zero `GestaoCustoFilho` depois disso significa que o cálculo foi jogado fora
    entre uma tabela e outra."""
    with app.app_context():
        tenant, tarefa = _cenario('assin')
        rdo = _via_editar(tenant, tarefa)

        folha = soma(custo_diario(rdo.id), campo='componente_folha')
        filhos = filhos_mao_de_obra(tenant, DIA)

        if folha > 0:
            assert len(filhos) > 0, (
                f'RDOCustoDiario.componente_folha = R$ {folha:.2f} e nenhum '
                f'GestaoCustoFilho: o custo foi calculado e descartado')


# ---------------------------------------------------------------------------
# (f) — /rdo/salvar entra na regra comum
# ---------------------------------------------------------------------------

def test_rdo_salvar_unificado_gera_custo_e_recalcula_medicao():
    """`POST /rdo/salvar` (`views/rdo.py:2766`) depois da B1.5.

    🔬 Este teste nasceu ao contrário: até a B1.5 ele CONGELAVA o gap — a rota
    lançava custo e não emitia `rdo_finalizado`, e o teste afirmava que a
    sentinela sobrevivia, para que a correção de A05 não mudasse isso sem que
    alguém visse. A B1.5 mudou de propósito (`views/rdo.py:3422`, chamada direta
    → emit), e o teste foi virado junto, no mesmo commit.

    Era o último caminho vivo que gerava custo e nunca recalculava medição: o
    custo entrava no razão e a medição da obra ficava para trás em silêncio, até
    que outro RDO da mesma obra passasse por uma rota que emite.

    🔬 **A versão anterior deste teste era vacuosa e o nome mentia.** Ele postava
    com as chaves ``cron_tarefa_*``, que esta rota **não parseia**
    (`views/rdo.py:3292-3316` lê ``funcionario_<id>_nome``/``_horas``), então o
    RDO nascia sem mão de obra, `gerar_custos_mao_obra_rdo` saía em
    `services/rdo_custos.py:386-387` e não havia custo nenhum para gerar. A
    sentinela sobrevivia por ausência de fato, não por ausência de emit — e o
    "gera_custo" do nome nunca foi conferido por assert nenhum. Daí o
    ``flat_func=True`` abaixo, e daí o primeiro assert.
    """
    with app.app_context():
        tenant, tarefa = _cenario('unif')
        _semear_cr_sentinela(tenant)
        _servico_do_tenant(tenant)

        cli = cliente_de(tenant.admin_id)
        form = form_rdo(tenant, DIA, tarefa_id=tarefa.id, flat_func=True)
        form['funcionario_id'] = str(tenant.funcionario_id)
        _ok(cli.post('/rdo/salvar', data=form))

        assert len(filhos_mao_de_obra(tenant, DIA)) == 1, (
            '/rdo/salvar deixou de gerar custo: a chamada direta saiu na B1.5 e '
            'o emit que a substituiu não lançou no lugar dela')

        assert not _sentinela_intacta(tenant), (
            'a sentinela sobreviveu: /rdo/salvar ainda não recalcula medição — '
            'o emit da B1.5 não chegou em recalcular_medicao_apos_rdo')
