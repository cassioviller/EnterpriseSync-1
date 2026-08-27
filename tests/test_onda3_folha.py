"""Onda 3 — a folha para de dobrar quando é reprocessada.

O arreio de tenant é `tests/helpers_tenant.py`. Task 8 fecha a automação A12:
`reprocessar` apagava só `FolhaPagamento` — o `GestaoCustoPai`/`Filho` e o
`LancamentoContabil` da rodada anterior sobreviviam e eram recriados, e a
folha dobrava no contas a pagar e no razão.
"""
import calendar
import os
import sys
from datetime import date, time
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant  # noqa: F401

pytestmark = pytest.mark.integration

ANO_REF = 2026
MES_REF = 6  # bate com o data_ref default de `um_tenant` (2026-06-15) — é o
             # mês em que o RegistroPonto semeado por `com_fatos=True` existe.


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-folha'
    yield


def _seed_ponto_mes_completo(admin_id, funcionario_id, obra_id):
    """`um_tenant(com_fatos=True)` só semeia UM RegistroPonto (2026-06-15).

    A lógica legada de `calcular_horas_mes` (sem `HorarioTrabalho`) conta
    falta em todo dia útil sem ponto — com um único dia batido, os ~21 dias
    úteis restantes viram falta e o líquido fica NEGATIVO
    (`salario_liq > 0` nunca é satisfeito em `folha_pagamento_views.py`, e
    nem GestaoCustoPai/Filho nem o lançamento contábil chegam a nascer).
    Bater o ponto em todo dia útil do mês é o que dá líquido positivo, para
    o teste exercitar de fato o caminho que A12 quebra."""
    from models import RegistroPonto
    ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
    for dia in range(1, ultimo_dia + 1):
        data = date(ANO_REF, MES_REF, dia)
        if data.weekday() >= 5:  # sábado/domingo
            continue
        db.session.add(RegistroPonto(
            funcionario_id=funcionario_id, obra_id=obra_id, admin_id=admin_id,
            data=data, horas_trabalhadas=8.0, horas_extras=0.0))
    db.session.commit()


def _seed_horario_trabalho(admin_id, funcionario_id, marca):
    """Segunda a sexta, 08:00–17:00 com 1h de pausa = 8h contratuais/dia.

    Sem `HorarioTrabalho` cadastrado, `calcular_horas_mes` cai na lógica
    legada (`_calcular_horas_mes_legado`), que NÃO compara ponto com horário
    contratual e por isso nunca põe as horas do atraso dentro de
    `horas_falta`. O caminho que dobra o desconto é o novo
    (`_calcular_horas_mes_novo`) — e ele só existe com horário configurado.
    """
    from models import Funcionario, HorarioDia, HorarioTrabalho
    horario = HorarioTrabalho(nome=f'Comercial {marca}', admin_id=admin_id,
                              ativo=True, horas_diarias=8.0)
    db.session.add(horario)
    db.session.flush()
    for dia_semana in range(0, 5):  # segunda a sexta
        db.session.add(HorarioDia(
            horario_id=horario.id, dia_semana=dia_semana,
            entrada=time(8, 0), saida=time(17, 0),
            pausa_horas=1.0, trabalha=True, admin_id=admin_id))
    funcionario = Funcionario.query.get(funcionario_id)
    funcionario.horario_trabalho_id = horario.id
    db.session.commit()
    return horario.id


def _seed_parametros_legais(admin_id):
    """A folha só processa com ParametrosLegais do ano cadastrado
    (`services/folha_service.py:_obter_parametros_legais`); sem isso
    `processar_folha_funcionario` levanta e o funcionário vira erro, e nem
    FolhaPagamento nem GestaoCusto nascem — o teste ficaria verde por vazio,
    não por a duplicação estar corrigida."""
    from models import ParametrosLegais
    params = ParametrosLegais(admin_id=admin_id, ano_vigencia=ANO_REF, ativo=True)
    db.session.add(params)
    db.session.commit()


# ---------------------------------------------------------------------------
# Task 8 — reprocessar a folha para de dobrá-la (automação A12)
# ---------------------------------------------------------------------------

def test_reprocessar_folha_nao_dobra_contas_a_pagar_nem_o_razao():
    """🔴 A12 — `folha_pagamento_views.py:148` apagava só `FolhaPagamento`.

    O GestaoCustoPai/Filho e o lançamento contábil da rodada anterior
    sobreviviam e eram recriados: a folha dobrava no contas a pagar
    (GestaoCustoFilho) e no razão (LancamentoContabil).
    """
    from models import FolhaPagamento, GestaoCustoFilho, LancamentoContabil

    with app.app_context():
        t = um_tenant('onda3_folha')
        admin_id = t.admin_id
        _seed_parametros_legais(admin_id)
        _seed_ponto_mes_completo(admin_id, t.funcionario_id, t.obra_id)

    cliente = cliente_de(admin_id)

    resp1 = cliente.post(f'/folha/processar/{ANO_REF}/{MES_REF}',
                          data={'reprocessar': 'false'}, follow_redirects=True)
    assert resp1.status_code == 200

    with app.app_context():
        folhas_1 = FolhaPagamento.query.filter_by(admin_id=admin_id).count()
        filhos_1 = GestaoCustoFilho.query.filter_by(admin_id=admin_id).count()
        lcs_1 = LancamentoContabil.query.filter_by(admin_id=admin_id).count()
        assert folhas_1 > 0, 'pré-condição: a primeira rodada precisa ter processado algo'
        assert filhos_1 > 0, 'pré-condição: a primeira rodada precisa ter gerado GestaoCusto'
        assert lcs_1 > 0, 'pré-condição: a primeira rodada precisa ter gerado LancamentoContabil'

    resp2 = cliente.post(f'/folha/processar/{ANO_REF}/{MES_REF}',
                          data={'reprocessar': 'true'}, follow_redirects=True)
    assert resp2.status_code == 200

    with app.app_context():
        folhas_2 = FolhaPagamento.query.filter_by(admin_id=admin_id).count()
        filhos_2 = GestaoCustoFilho.query.filter_by(admin_id=admin_id).count()
        lcs_2 = LancamentoContabil.query.filter_by(admin_id=admin_id).count()

    assert folhas_2 == folhas_1, (
        f'FolhaPagamento dobrou ao reprocessar: {folhas_1} → {folhas_2}')
    assert filhos_2 == filhos_1, (
        f'GestaoCustoFilho (contas a pagar) dobrou ao reprocessar: {filhos_1} → {filhos_2}')
    assert lcs_2 == lcs_1, (
        f'LancamentoContabil (razão) dobrou ao reprocessar: {lcs_1} → {lcs_2}')


def test_estorno_preserva_pai_compartilhado_com_outra_origem():
    """🔴 `GestaoCustoPai` é rotineiramente compartilhado entre origens —
    `utils/financeiro_integration.py:118-140` reaproveita o pai em aberto
    pela chave (admin_id, categoria, entidade_id), sem olhar
    `origem_tabela`. Se `estornar_folha_do_mes` apagar o pai só porque ele
    tinha UM filho de folha, filhos de outras origens penduradas no MESMO
    pai (`GestaoCustoPai.itens` é `cascade='all, delete-orphan'`) somem
    junto — a mesma classe de bug que a Task 4 já matou em
    `reembolso_views.py`.
    """
    from decimal import Decimal
    from models import GestaoCustoFilho, GestaoCustoPai
    from services.folha_service import estornar_folha_do_mes

    with app.app_context():
        t = um_tenant('onda3_folha_pai')
        admin_id = t.admin_id
        _seed_parametros_legais(admin_id)
        _seed_ponto_mes_completo(admin_id, t.funcionario_id, t.obra_id)

    cliente = cliente_de(admin_id)
    resp = cliente.post(f'/folha/processar/{ANO_REF}/{MES_REF}',
                         data={'reprocessar': 'false'}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        filho_folha = GestaoCustoFilho.query.filter_by(
            admin_id=admin_id, origem_tabela='folha_pagamento').first()
        assert filho_folha is not None, (
            'pré-condição: a folha precisa ter gerado o filho de origem folha')
        pai_id = filho_folha.pai_id

        # Um filho de OUTRA origem, no MESMO pai — é exatamente o que
        # `financeiro_integration.reaproveita_pai_em_aberto` produz.
        valor_outra_origem = Decimal('123.45')
        filho_rdo = GestaoCustoFilho(
            pai_id=pai_id, admin_id=admin_id,
            data_referencia=date(ANO_REF, MES_REF, 1),
            descricao='Diária RDO — não é folha',
            valor=valor_outra_origem,
            obra_id=t.obra_id,
            origem_tabela='rdo_mao_obra',
            origem_id=999999,
        )
        db.session.add(filho_rdo)
        db.session.commit()
        filho_rdo_id = filho_rdo.id

        estornar_folha_do_mes(admin_id=admin_id,
                               mes_referencia=date(ANO_REF, MES_REF, 1))
        db.session.commit()

    with app.app_context():
        # O filho de folha foi embora.
        assert GestaoCustoFilho.query.filter_by(
            admin_id=admin_id, origem_tabela='folha_pagamento').count() == 0

        # O filho de outra origem, e o pai que os agrupava, sobrevivem.
        filho_rdo_depois = GestaoCustoFilho.query.get(filho_rdo_id)
        assert filho_rdo_depois is not None, (
            'estorno da folha apagou filho de OUTRA origem no mesmo pai')

        pai_depois = GestaoCustoPai.query.get(pai_id)
        assert pai_depois is not None, (
            'estorno da folha apagou o pai compartilhado com outra origem')

        # E o total do pai foi recalculado — sobrou só o filho do RDO.
        assert pai_depois.valor_total == valor_outra_origem, (
            f'GestaoCustoPai.valor_total não foi recalculado: '
            f'{pai_depois.valor_total} != {valor_outra_origem}')


# ---------------------------------------------------------------------------
# Task 9 / dobra 1 — o atraso deixa de ser descontado duas vezes
# ---------------------------------------------------------------------------

def _seed_ponto_com_atraso(admin_id, funcionario_id, obra_id,
                            dia_do_atraso, horas_no_dia, minutos_atraso):
    """Mês inteiro batido em 8h, menos um dia útil com atraso.

    O dia do atraso é o que expõe a dobra: `_calcular_horas_mes_novo` mede a
    falta pelo delta contra as 8h contratuais (e portanto JÁ cobra a hora que
    faltou) e ainda assim devolve `total_minutos_atraso`, que
    `calcular_salario_bruto` cobra de novo.
    """
    from models import RegistroPonto
    ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
    for dia in range(1, ultimo_dia + 1):
        data = date(ANO_REF, MES_REF, dia)
        if data.weekday() >= 5:
            continue
        eh_dia_do_atraso = dia == dia_do_atraso
        db.session.add(RegistroPonto(
            funcionario_id=funcionario_id, obra_id=obra_id, admin_id=admin_id,
            data=data,
            horas_trabalhadas=horas_no_dia if eh_dia_do_atraso else 8.0,
            horas_extras=0.0,
            minutos_atraso_entrada=minutos_atraso if eh_dia_do_atraso else 0,
            total_atraso_minutos=minutos_atraso if eh_dia_do_atraso else 0,
            total_atraso_horas=(minutos_atraso / 60.0) if eh_dia_do_atraso else 0.0,
        ))
    db.session.commit()


def test_atraso_nao_e_descontado_duas_vezes():
    """🔴 dobra 1 — `services/folha_service.py:calcular_salario_bruto`.

    Quem chega 1h atrasado num dia de 8h contratuais trabalha 7h. O cálculo
    novo de horas põe essa 1h em `horas_falta` (delta contra o contratual) e
    o desconto de faltas já a cobra. `desconto_atrasos` cobrava a MESMA hora
    outra vez: o funcionário perdia 2h de salário por 1h de atraso.
    """
    from models import Funcionario
    from services.folha_service import calcular_horas_mes, calcular_salario_bruto

    with app.app_context():
        t = um_tenant('onda3_atraso', com_fatos=False)
        admin_id = t.admin_id
        _seed_parametros_legais(admin_id)
        _seed_horario_trabalho(admin_id, t.funcionario_id, t.marca)
        # 2026-06-02 é uma terça-feira: 7h batidas, 60min de atraso.
        _seed_ponto_com_atraso(admin_id, t.funcionario_id, t.obra_id,
                                dia_do_atraso=2, horas_no_dia=7.0,
                                minutos_atraso=60)

        horas_info = calcular_horas_mes(t.funcionario_id, ANO_REF, MES_REF)

        # Pré-condições: o teste só prova algo se as duas grandezas existirem
        # e apontarem para a MESMA hora perdida.
        assert horas_info['total_minutos_atraso'] == 60, (
            'pré-condição: o ponto do dia precisa registrar o atraso')
        assert horas_info['horas_falta'] == pytest.approx(1.0), (
            'pré-condição: a hora do atraso já entra em horas_falta')
        assert horas_info['faltas'] == 0, (
            'pré-condição: nenhum dia útil pode estar sem ponto')

        funcionario = Funcionario.query.filter_by(
            id=t.funcionario_id, admin_id=admin_id).first()
        ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
        resultado = calcular_salario_bruto(
            funcionario, horas_info,
            date(ANO_REF, MES_REF, 1), date(ANO_REF, MES_REF, ultimo_dia))

    valor_hora = resultado['valor_hora']
    esperado = valor_hora * Decimal('1')  # 1 hora perdida, cobrada UMA vez
    cobrado = resultado['desconto_faltas'] + resultado['desconto_atrasos']

    assert cobrado == esperado, (
        f'1h de atraso cobrada {cobrado / valor_hora}x '
        f'(faltas={resultado["desconto_faltas"]}, '
        f'atrasos={resultado["desconto_atrasos"]})')
    assert resultado['total_proventos'] == resultado['salario_bruto'] - esperado


# ---------------------------------------------------------------------------
# Task 9 / dobra 2 — a composição do custo para de somar HE e DSR duas vezes
# ---------------------------------------------------------------------------

def _seed_ponto_com_extras(admin_id, funcionario_id, obra_id):
    """Mês cheio em 8h, dois dias úteis de 10h (HE 50%) e um domingo de 4h
    (HE 100%). O domingo é o que faz o DSR sobre extras existir."""
    from models import RegistroPonto
    ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
    dias_com_he_50 = (3, 4)   # quarta e quinta
    domingo_trabalhado = 7    # 2026-06-07 é domingo
    for dia in range(1, ultimo_dia + 1):
        data = date(ANO_REF, MES_REF, dia)
        if data.weekday() >= 5 and dia != domingo_trabalhado:
            continue
        if dia == domingo_trabalhado:
            horas = 4.0
        elif dia in dias_com_he_50:
            horas = 10.0
        else:
            horas = 8.0
        db.session.add(RegistroPonto(
            funcionario_id=funcionario_id, obra_id=obra_id, admin_id=admin_id,
            data=data, horas_trabalhadas=horas, horas_extras=0.0))
    db.session.commit()


def test_composicao_do_custo_da_obra_nao_soma_he_e_dsr_duas_vezes():
    """🔴 dobra 2 — `services/folha_service.py:obter_dados_folha_obra`.

    `salario_bruto` JÁ É `salario_normal + horas extras + DSR`. A composição
    exibia esse bruto inteiro sob o rótulo "Salário Base" e ainda somava
    "HE 50%", "HE 100%" e "DSR s/ Extras" como fatias separadas: as fatias
    não fechavam com o custo total — passavam dele pelo valor das extras.
    """
    from models import Funcionario
    from services.folha_service import (obter_dados_folha_obra,
                                        processar_folha_funcionario,
                                        salvar_folha_processada)

    with app.app_context():
        t = um_tenant('onda3_composicao', com_fatos=False)
        admin_id = t.admin_id
        _seed_parametros_legais(admin_id)
        _seed_horario_trabalho(admin_id, t.funcionario_id, t.marca)
        _seed_ponto_com_extras(admin_id, t.funcionario_id, t.obra_id)

        funcionario = Funcionario.query.filter_by(
            id=t.funcionario_id, admin_id=admin_id).first()
        dados = processar_folha_funcionario(funcionario, ANO_REF, MES_REF)
        assert dados is not None, 'pré-condição: a folha precisa processar'
        assert dados['valor_he_50'] > 0, 'pré-condição: HE 50% precisa existir'
        assert dados['valor_he_100'] > 0, 'pré-condição: HE 100% precisa existir'
        assert dados['valor_dsr'] > 0, 'pré-condição: DSR sobre extras precisa existir'
        assert salvar_folha_processada(
            t.funcionario_id, t.obra_id, ANO_REF, MES_REF, dados, admin_id)

        ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
        painel = obter_dados_folha_obra(
            obra_id=t.obra_id,
            data_inicio=date(ANO_REF, MES_REF, 1),
            data_fim=date(ANO_REF, MES_REF, ultimo_dia),
            admin_id=admin_id)

    fatias = {c['categoria']: c['valor'] for c in painel['composicao']}
    custo_total = painel['totais']['custo_total']

    assert custo_total > 0, 'pré-condição: a obra precisa ter custo de folha'
    assert sum(fatias.values()) == pytest.approx(custo_total, abs=0.02), (
        f'a composição não fecha com o custo total: '
        f'{sum(fatias.values()):.2f} != {custo_total:.2f} — fatias={fatias}')

    # E a fatia "Salário Base" é o salário normal: o bruto SEM as extras e o
    # DSR que já aparecem em fatia própria.
    esperado_base = (dados['salario_bruto'] - dados['valor_he_50']
                     - dados['valor_he_100'] - dados['valor_dsr'])
    assert fatias['Salário Base'] == pytest.approx(esperado_base, abs=0.02)


# ---------------------------------------------------------------------------
# Task 9 / dobra 3 — a folha do mês é rateada entre as obras, não repetida
# ---------------------------------------------------------------------------

def _segunda_obra(admin_id, cliente_id, marca):
    """Uma segunda obra no MESMO tenant — o arreio só semeia uma."""
    from models import Obra
    obra = Obra(nome=f'Obra 2 {marca}', codigo=f'{marca[:8]}B2',
                data_inicio=date(2026, 1, 1), admin_id=admin_id,
                cliente_id=cliente_id, valor_contrato=100000,
                orcamento=100000, status='Em andamento')
    db.session.add(obra)
    db.session.commit()
    return obra.id


def _seed_ponto_dividido_entre_obras(admin_id, funcionario_id,
                                      obra_a, obra_b, dias_na_obra_a):
    """Mês cheio em 8h/dia: os primeiros `dias_na_obra_a` dias úteis na obra A,
    o resto na obra B. Devolve (horas_a, horas_b)."""
    from models import RegistroPonto
    ultimo_dia = calendar.monthrange(ANO_REF, MES_REF)[1]
    horas_a = horas_b = 0.0
    uteis = 0
    for dia in range(1, ultimo_dia + 1):
        data = date(ANO_REF, MES_REF, dia)
        if data.weekday() >= 5:
            continue
        uteis += 1
        obra_id = obra_a if uteis <= dias_na_obra_a else obra_b
        if obra_id == obra_a:
            horas_a += 8.0
        else:
            horas_b += 8.0
        db.session.add(RegistroPonto(
            funcionario_id=funcionario_id, obra_id=obra_id, admin_id=admin_id,
            data=data, horas_trabalhadas=8.0, horas_extras=0.0))
    db.session.commit()
    return horas_a, horas_b


def test_folha_do_mes_e_rateada_entre_as_obras_e_a_soma_fecha():
    """🔴 dobra 3 — `services/folha_service.py:processar_e_salvar_folha_obra`.

    Quem apontou em duas obras no mês tinha a folha INTEIRA gravada contra
    CADA uma delas: duas obras, duas folhas cheias, custo por obra e todo
    roll-up com o dobro do que a empresa pagou. O rateio é por horas
    apontadas em cada obra — e as partes precisam somar EXATAMENTE o total
    do mês, sem sobra nem falta de centavo.
    """
    from models import FolhaProcessada, Funcionario
    from services.folha_service import (processar_e_salvar_folha_obra,
                                        processar_folha_funcionario)

    with app.app_context():
        t = um_tenant('onda3_rateio', com_fatos=False)
        admin_id = t.admin_id
        obra_a, obra_b = t.obra_id, _segunda_obra(admin_id, t.cliente_id, t.marca)
        _seed_parametros_legais(admin_id)
        _seed_horario_trabalho(admin_id, t.funcionario_id, t.marca)
        # 7 dias na obra A e 15 na obra B: 56h/176h não é fração redonda —
        # é o caso em que o rateio precisa acertar o centavo do resíduo.
        horas_a, horas_b = _seed_ponto_dividido_entre_obras(
            admin_id, t.funcionario_id, obra_a, obra_b, dias_na_obra_a=7)

        funcionario = Funcionario.query.filter_by(
            id=t.funcionario_id, admin_id=admin_id).first()
        do_mes = processar_folha_funcionario(funcionario, ANO_REF, MES_REF)
        assert do_mes is not None, 'pré-condição: a folha precisa processar'

        processar_e_salvar_folha_obra(obra_a, ANO_REF, MES_REF, admin_id)
        processar_e_salvar_folha_obra(obra_b, ANO_REF, MES_REF, admin_id)

        folhas = FolhaProcessada.query.filter_by(
            admin_id=admin_id, ano=ANO_REF, mes=MES_REF).all()
        por_obra = {f.obra_id: f for f in folhas}

    assert set(por_obra) == {obra_a, obra_b}, (
        f'esperado uma linha por obra trabalhada, veio {sorted(por_obra)}')

    def _total(campo):
        return sum(getattr(f, campo) for f in por_obra.values())

    def _do_mes(campo):
        return Decimal(str(do_mes[campo])).quantize(Decimal('0.01'))

    # 1) Nenhuma obra carrega o mês inteiro.
    for obra_id, folha in por_obra.items():
        assert folha.custo_total_empresa < _do_mes('custo_total_empresa'), (
            f'obra {obra_id} recebeu a folha INTEIRA do mês: '
            f'{folha.custo_total_empresa} de {_do_mes("custo_total_empresa")}')

    # 2) As partes somam EXATAMENTE o total do mês — sem resíduo perdido.
    for campo_folha, campo_dados in (
            ('salario_bruto', 'salario_bruto'),
            ('salario_liquido', 'salario_liquido'),
            ('encargos_fgts', 'fgts'),
            ('horas_trabalhadas', 'horas_trabalhadas')):
        assert _total(campo_folha) == _do_mes(campo_dados), (
            f'{campo_folha}: rateio soma {_total(campo_folha)}, '
            f'mês inteiro é {_do_mes(campo_dados)}')

    # 2b) `custo_total_empresa` tem DUAS exatidões concorrentes, e nenhum
    #     arredondamento ao centavo satisfaz as duas ao mesmo tempo:
    #
    #       (a) POR LINHA (A24a/B2.14): `fgts + inss_patronal = custo − bruto`.
    #           `_folha_rateada_para_obra` a garante DERIVANDO o custo da soma
    #           das três fatias já arredondadas — a soma das partes é, então,
    #           Q(bruto) + Q(fgts) + Q(inss).
    #       (b) DO MÊS: `processar_folha_funcionario` soma antes de arredondar
    #           — Q(bruto + fgts + inss).
    #
    #     As duas diferem em um centavo sempre que os três arredondamentos se
    #     acumulam além de meio centavo (36% dos salários, medido com a
    #     aritmética do próprio módulo). O centavo é ESTRUTURAL, não defeito.
    #     Por isso a exatidão é cobrada comparando como com como — a soma das
    #     fatias contra a base derivada do mesmo jeito — e a distância para o
    #     total do mês do funcionário é cobrada como teto de um centavo.
    base_por_componentes = (_do_mes('salario_bruto') + _do_mes('fgts')
                            + _do_mes('inss_patronal'))
    assert _total('custo_total_empresa') == base_por_componentes, (
        f'custo_total_empresa: rateio soma {_total("custo_total_empresa")}, '
        f'a base pelos componentes do mês é {base_por_componentes}')
    assert abs(_total('custo_total_empresa')
               - _do_mes('custo_total_empresa')) <= Decimal('0.01'), (
        f'a soma das fatias ({_total("custo_total_empresa")}) se afastou mais '
        f'de um centavo do custo do mês ({_do_mes("custo_total_empresa")}) — '
        f'o centavo estrutural virou perda de rateio')

    # 3) Cada linha por obra respeita o invariante interno que a linha do mês
    #    respeita (A24a/B2.14): fgts + inss patronal = custo total − bruto.
    for obra_id, folha in por_obra.items():
        assert (folha.encargos_fgts + folha.encargos_inss_patronal
                == folha.custo_total_empresa - folha.salario_bruto), (
            f'a linha da obra {obra_id} viola o invariante dos encargos: '
            f'{folha.encargos_fgts} + {folha.encargos_inss_patronal} != '
            f'{folha.custo_total_empresa} - {folha.salario_bruto}')

    # 4) E cada parte é proporcional às horas apontadas naquela obra. A base é
    #    a mesma de (2b) — comparar com `Q(b+f+i)` reintroduziria o centavo
    #    estrutural na tolerância. A folga é de dois centavos porque a fatia da
    #    obra é a soma de TRÊS parcelas arredondadas, cada uma podendo andar
    #    meio centavo.
    horas_totais = Decimal(str(horas_a + horas_b))
    esperado_a = base_por_componentes * Decimal(str(horas_a)) / horas_totais
    assert abs(por_obra[obra_a].custo_total_empresa - esperado_a) <= Decimal('0.02'), (
        f'obra A ficou com {por_obra[obra_a].custo_total_empresa}, '
        f'proporcional a {horas_a}h de {horas_totais}h seria {esperado_a:.2f}')


def test_rateio_da_folha_nao_perde_o_centavo_do_arredondamento():
    """O resíduo do arredondamento tem destino fixo — e a soma fecha.

    Complementa o teste acima: com 56h/120h as fatias já caem redondas, e
    fechar a soma ali não prova que o centavo perdido no arredondamento tem
    para onde ir. Três obras com o mesmo peso é o caso em que ele sempre
    sobra (R$ 100,00 ÷ 3 = 33,33 × 3 = 99,99).
    """
    from services.folha_service import _ratear_valor_por_obra

    horas_iguais = {77: Decimal('8'), 12: Decimal('8'), 45: Decimal('8')}
    fatias = _ratear_valor_por_obra(Decimal('100.00'), horas_iguais)

    assert sum(fatias.values()) == Decimal('100.00'), (
        f'o rateio perdeu o resíduo: {fatias}')
    # Destino determinístico: maior peso, desempate pelo menor obra_id — não
    # depende da ordem em que as obras são processadas.
    assert fatias == {12: Decimal('33.34'), 45: Decimal('33.33'),
                      77: Decimal('33.33')}

    # E com peso desigual, o resíduo vai para a obra de maior peso.
    fatias = _ratear_valor_por_obra(
        Decimal('100.00'), {8: Decimal('1'), 3: Decimal('2')})
    assert sum(fatias.values()) == Decimal('100.00')
    assert fatias[3] == Decimal('66.67')


# ---------------------------------------------------------------------------
# Task 9 / dobra 4 — o R$/h do diarista bate com o que foi lançado
# ---------------------------------------------------------------------------

def test_custo_hora_do_diarista_bate_com_a_diaria_rateada():
    """🔴 dobra 4 — `services/custo_funcionario_dia.py:calcular_custo_funcionario_no_rdo`.

    Diarista que aparece em dois RDOs do mesmo dia tem a diária RATEADA entre
    eles (`componente_folha = valor_diaria * proporção`), mas o
    `custo_hora_normal` gravado era `valor_diaria / horas_no_rdo` — a diária
    CHEIA sobre as horas de um RDO só. A tela do RDO multiplica horas por
    esse R$/h e mostrava o dobro do que foi lançado.
    """
    from models import RDO, RDOCustoDiario, RDOMaoObra
    from services.custo_funcionario_dia import gravar_custo_funcionario_rdo

    valor_diaria = 200.0
    data_rdo = date(ANO_REF, MES_REF, 10)

    with app.app_context():
        t = um_tenant('onda3_diarista', com_fatos=False,
                      tipo_remuneracao='diaria', valor_diaria=valor_diaria)
        admin_id = t.admin_id
        obra_b = _segunda_obra(admin_id, t.cliente_id, t.marca)

        rdos = []
        for sufixo, obra_id in (('A', t.obra_id), ('B', obra_b)):
            rdo = RDO(numero_rdo=f'R{t.marca[-8:]}{sufixo}', obra_id=obra_id,
                      data_relatorio=data_rdo, admin_id=admin_id,
                      status='Finalizado', criado_por_id=admin_id)
            db.session.add(rdo)
            db.session.flush()
            db.session.add(RDOMaoObra(
                rdo_id=rdo.id, funcionario_id=t.funcionario_id,
                funcao_exercida='Pedreiro', horas_trabalhadas=4.0,
                admin_id=admin_id))
            rdos.append(rdo)
        db.session.commit()

        for rdo in rdos:
            gravar_custo_funcionario_rdo(rdo, admin_id)

        linhas = RDOCustoDiario.query.filter_by(
            admin_id=admin_id, funcionario_id=t.funcionario_id,
            data=data_rdo, tipo_lancamento='rdo').all()

        assert len(linhas) == 2, (
            f'pré-condição: um lançamento por RDO do dia, veio {len(linhas)}')

        # Pré-condição: a diária foi mesmo rateada — metade em cada RDO.
        for linha in linhas:
            assert float(linha.componente_folha) == pytest.approx(
                valor_diaria / 2, abs=0.01), (
                'pré-condição: a diária precisa estar rateada entre os RDOs')

        for linha in linhas:
            lancado = Decimal(str(linha.componente_folha))
            exibido = (Decimal(str(linha.horas_normais))
                       * Decimal(str(linha.custo_hora_normal)))
            assert exibido == pytest.approx(lancado, abs=Decimal('0.01')), (
                f'a tela mostra {exibido:.2f} para um lançamento de '
                f'{lancado:.2f} (R$/h={linha.custo_hora_normal} '
                f'x {linha.horas_normais}h)')
