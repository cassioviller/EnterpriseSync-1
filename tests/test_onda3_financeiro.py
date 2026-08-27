"""Onda 3 — o card e o detalhe da mesma tela param de discordar.

`FinanceiroService.calcular_fluxo_caixa` devolve, no MESMO dicionário, o KPI
(`saidas_previstas`, o card) e a lista `detalhes` (a tabela abaixo dele). Para
um `GestaoCustoPai` PARCIAL o KPI usa o `saldo` — o que ainda falta pagar — e o
laço dos filhos manuais somava cada filho pelo `valor` **cheio**, descartando em
silêncio o `resto` negativo. Dois filhos de R$ 500 com R$ 600 já pagos davam
card = R$ 400 e detalhe = R$ 1.000: os R$ 600 já pagos contados duas vezes na
mesma tela.

O oráculo aqui é a IGUALDADE entre as duas pontas, não um número escolhido a
dedo: é a discordância que o usuário vê. Todo tenant é próprio (`um_tenant`), e
`calcular_fluxo_caixa` recebe o `admin_id` dele — o banco de dev é compartilhado
com trabalho concorrente e nenhuma asserção aqui pode enxergar linha alheia.

**D2 (26/08) — os gêmeos de reembolso.** O segundo assunto do arquivo, na mesma
função: a exclusão dos gêmeos tirava o `GestaoCustoPai` de `saidas_previstas`
porque existe uma `ContaPagar` gêmea — só que `ContaPagar` **nunca** alimenta
essa soma. Enquanto a gêmea está PENDENTE a obrigação não muda de lado:
**evapora**. A exclusão passa a ser consciente de estado — o gêmeo sai da
projeção só quando a outra perna de fato entra nela (a baixa da CP, que debita
`banco.saldo_atual` = o `saldo_inicial` deste fluxo).
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import ContaPagar, GestaoCustoFilho, GestaoCustoPai

from financeiro_service import FinanceiroService
from helpers_tenant import um_tenant

pytestmark = pytest.mark.integration

HOJE = date(2026, 6, 15)
JANELA_FIM = HOJE + timedelta(days=30)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-financeiro'
    yield


def _pai_parcial(admin_id, obra_id, valores_filhos, saldo):
    """Um Pai com filhos MANUAIS — a forma que dispara o laço de `detalhes`.

    `origem_tabela='lancamento_periodo_manual'` é o que faz `calcular_fluxo_caixa`
    explodir o Pai em uma linha por filho (`financeiro_service.py:742`); sem ele
    o Pai sai como linha única e o defeito não aparece.
    """
    total = sum(Decimal(str(v)) for v in valores_filhos)
    saldo = Decimal(str(saldo))
    pai = GestaoCustoPai(
        tipo_categoria='MATERIAL',
        entidade_nome=f'ONDA3-{uuid.uuid4().hex[:6]}',
        valor_total=total, saldo=saldo, valor_pago=total - saldo,
        status='PARCIAL', data_vencimento=HOJE + timedelta(days=5),
        admin_id=admin_id, obra_id=obra_id)
    db.session.add(pai)
    db.session.flush()
    for i, v in enumerate(valores_filhos):
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=admin_id, obra_id=obra_id,
            descricao=f'lancamento {i}', valor=Decimal(str(v)),
            data_referencia=HOJE + timedelta(days=i),
            origem_tabela='lancamento_periodo_manual'))
    db.session.commit()
    return pai


def _previstas_do_detalhe(fluxo):
    """A soma que o usuário faz com o olho: as saídas ainda NÃO realizadas."""
    return sum(float(d['valor']) for d in fluxo['detalhes']
               if d['tipo'] == 'SAIDA' and not d.get('realizado'))


def test_card_e_detalhe_do_pai_parcial_batem():
    """🔴 `financeiro_service.py:759` — o `resto` negativo era descartado.

    Dois filhos de R$ 500, R$ 600 já pagos: o card usa o saldo (R$ 400) e o
    detalhe listava R$ 500 + R$ 500 = R$ 1.000.
    """
    with app.app_context():
        t = um_tenant('onda3_fin_parcial', com_fatos=False)
        _pai_parcial(t.admin_id, t.obra_id, [500, 500], saldo=400)

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        assert fluxo['saidas_previstas'] == pytest.approx(400.0)
        assert _previstas_do_detalhe(fluxo) == pytest.approx(400.0), (
            'o detalhe soma os filhos pelo valor cheio — os R$ 600 ja pagos '
            'aparecem de novo na mesma tela')


def test_rateio_nao_perde_centavo_em_divisao_inexata():
    """O rateio fecha na SOMA, não na divisão.

    Três filhos de R$ 100 com R$ 200 pagos: a fatia de cada um é R$ 33,33 e o
    arredondamento por linha entregaria R$ 99,99 — um centavo a menos que o
    card. O resíduo tem de cair na ÚLTIMA linha do rateio, e não sobrar para a
    linha agregada do `resto`: contar as linhas é o que separa as duas saídas,
    porque a soma fecha nas duas.
    """
    with app.app_context():
        t = um_tenant('onda3_fin_centavo', com_fatos=False)
        pai = _pai_parcial(t.admin_id, t.obra_id, [100, 100, 100], saldo=100)
        marca = pai.entidade_nome

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        previstas = [d for d in fluxo['detalhes']
                     if d['tipo'] == 'SAIDA' and not d.get('realizado')
                     and marca in (d['descricao'] or '')]
        assert fluxo['saidas_previstas'] == pytest.approx(100.0)
        assert sum(d['valor'] for d in previstas) == pytest.approx(100.0, abs=0.005)
        assert len(previstas) == 3, (
            'o centavo do arredondamento virou uma linha agregada de R$ 0,01')


def test_pai_com_saldo_maior_que_os_filhos_mantem_a_linha_de_resto():
    """Cão de guarda do caminho que já funcionava: quando o Pai vale MAIS que
    os filhos manuais, a diferença continua saindo como linha agregada — o
    rateio não pode comer o `resto` positivo."""
    with app.app_context():
        t = um_tenant('onda3_fin_resto', com_fatos=False)
        pai = _pai_parcial(t.admin_id, t.obra_id, [300], saldo=1000)
        marca = pai.entidade_nome

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        previstas = [d for d in fluxo['detalhes']
                     if d['tipo'] == 'SAIDA' and not d.get('realizado')
                     and marca in (d['descricao'] or '')]
        assert len(previstas) == 2, 'sumiu a linha do resto nao-manual'
        assert fluxo['saidas_previstas'] == pytest.approx(1000.0)
        assert _previstas_do_detalhe(fluxo) == pytest.approx(1000.0)


# ── D2 (26/08) — a exclusão dos gêmeos vira consciente de estado ───────────
#
# `_gemeos_reembolso` (`financeiro_service.py`) tira das previstas todo
# `GestaoCustoPai` que tenha `ContaPagar` gêmea (`origem_tipo`
# 'gestao_custo_pai', `origem_id` = id do Pai — a forma que o import de fluxo
# em modo reembolso grava). A pergunta que a exclusão passa a responder é
# "a outra perna JÁ entra na projeção?": ela entra pela baixa da CP, que debita
# `banco.saldo_atual` — o `saldo_inicial` deste mesmo fluxo. CP PENDENTE não
# entra em lugar nenhum, e a obrigação tem de continuar projetada.
#
# ⚠️ O marcador que o sistema tem é o `status`, e ele NÃO é equivalente ao
# débito bancário: `baixar_pagamento` escreve 'PAGO' sempre, e só debita banco
# `if banco_id` (a rota deixa o banco opcional). O resíduo da baixa sem banco
# está declarado no comentário do service; o teste de fixação no fim do arquivo
# é o que prende o caminho COMPLETO — baixa real, banco real, as duas pernas.


def _par_gemeo_reembolso(admin_id, obra_id, valor, status_cp):
    """GCP PENDENTE + a `ContaPagar` gêmea no estado pedido — devolve os dois.

    Espelha a montagem de `tests/test_b6_familia2_reembolso_import.py`: o
    `origem_tipo` vai MINÚSCULO como o import grava, e o filho nasce sem
    `origem_tabela` (é o que o torna invisível à exclusão da família 1).
    `valor_pago`/`saldo`/`data_pagamento` da CP acompanham o status porque é o
    que `FinanceiroService.baixar_pagamento` escreve na baixa — quem quer a
    baixa DE VERDADE monta o par PENDENTE e chama o service (ver o teste de
    fixação abaixo).
    """
    valor = Decimal(str(valor))
    pago = valor if status_cp == 'PAGO' else Decimal('0')
    pai = GestaoCustoPai(
        tipo_categoria='MATERIAL',
        entidade_nome=f'ONDA3-GEMEO-{uuid.uuid4().hex[:6]}',
        valor_total=valor, saldo=valor, status='PENDENTE',
        data_vencimento=HOJE + timedelta(days=5),
        admin_id=admin_id, obra_id=obra_id)
    db.session.add(pai)
    db.session.flush()
    db.session.add(GestaoCustoFilho(
        pai_id=pai.id, admin_id=admin_id, obra_id=obra_id,
        descricao='reembolso', valor=valor, data_referencia=HOJE,
        origem_tabela=None, origem_id=None))
    cp = ContaPagar(
        descricao=f'CP gemea {pai.entidade_nome}', valor_original=valor,
        valor_pago=pago, saldo=valor - pago, data_emissao=HOJE,
        data_vencimento=HOJE + timedelta(days=10),
        data_pagamento=(HOJE if status_cp == 'PAGO' else None),
        status=status_cp, origem_tipo='gestao_custo_pai', origem_id=pai.id,
        obra_id=obra_id, admin_id=admin_id)
    db.session.add(cp)
    db.session.commit()
    return pai, cp


def _linhas_previstas(fluxo, marca):
    return [d for d in fluxo['detalhes']
            if d['tipo'] == 'SAIDA' and not d.get('realizado')
            and marca in (d['descricao'] or '')]


def test_gemeo_com_conta_pagar_pendente_continua_previsto():
    """🔴 D2 — a obrigação de R$ 1.000 evaporava da projeção.

    A CP gêmea está PENDENTE: ninguém a debitou do banco e `ContaPagar` não
    alimenta `saidas_previstas`. Excluir o Pai aqui não muda a obrigação de
    lado — apaga ela. ⚠️ dev 06/08: 580 gêmeos, R$ 490.950, 24% do valor
    aberto do parque.
    """
    with app.app_context():
        t = um_tenant('onda3_gemeo_pend', com_fatos=False)
        pai, _ = _par_gemeo_reembolso(t.admin_id, t.obra_id, 1000, 'PENDENTE')

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        assert fluxo['saidas_previstas'] == pytest.approx(1000.0), (
            f"saidas_previstas={fluxo['saidas_previstas']}: a gemea esta "
            f'PENDENTE — a obrigacao nao entrou em projecao nenhuma, entao '
            f'excluir o Pai a faz evaporar')
        assert _linhas_previstas(fluxo, pai.entidade_nome), (
            'o gemeo sumiu dos detalhes → e dos buckets de agregar_fluxo_mensal')


def test_gemeo_com_conta_pagar_paga_sai_das_previstas():
    """Cão de guarda da B6.2 no outro estado: com a CP BAIXADA o dinheiro já
    saiu do banco (`banco.saldo_atual` = o `saldo_inicial` deste fluxo). Manter
    a prevista do Pai subtrairia a MESMA despesa duas vezes do
    `saldo_final_projetado` — é a exclusão que a B6.2 criou, e ela fica."""
    with app.app_context():
        t = um_tenant('onda3_gemeo_pago', com_fatos=False)
        pai, _ = _par_gemeo_reembolso(t.admin_id, t.obra_id, 700, 'PAGO')

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        assert fluxo['saidas_previstas'] == pytest.approx(0.0), (
            f"saidas_previstas={fluxo['saidas_previstas']}: a gemea ja foi "
            f'paga pelo banco e a prevista do Pai continua — dupla subtracao')
        assert not _linhas_previstas(fluxo, pai.entidade_nome)


def test_gemeo_com_conta_pagar_paga_de_outro_tenant_continua_previsto():
    """Cão de guarda do `admin_id` no estado novo: a CP gêmea PAGA mora em
    OUTRO tenant. Sem o guard na subquery, a baixa alheia apagaria a projeção
    daqui — o misjoin que a medição do WF-2 cometeu duas vezes."""
    with app.app_context():
        t = um_tenant('onda3_gemeo_ml', com_fatos=False)
        outro = um_tenant('onda3_gemeo_mlB', com_fatos=False)
        pai = GestaoCustoPai(
            tipo_categoria='MATERIAL',
            entidade_nome=f'ONDA3-GEMEO-{uuid.uuid4().hex[:6]}',
            valor_total=Decimal('500'), saldo=Decimal('500'), status='PENDENTE',
            data_vencimento=HOJE + timedelta(days=5),
            admin_id=t.admin_id, obra_id=t.obra_id)
        db.session.add(pai)
        db.session.flush()
        db.session.add(ContaPagar(
            descricao='CP gemea alheia', valor_original=Decimal('500'),
            valor_pago=Decimal('500'), saldo=Decimal('0'), data_emissao=HOJE,
            data_vencimento=HOJE + timedelta(days=10), data_pagamento=HOJE,
            status='PAGO', origem_tipo='gestao_custo_pai', origem_id=pai.id,
            obra_id=outro.obra_id, admin_id=outro.admin_id))
        db.session.commit()

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        assert fluxo['saidas_previstas'] == pytest.approx(500.0)
        assert _linhas_previstas(fluxo, pai.entidade_nome), (
            'GCP excluido por CP PAGA de OUTRO tenant — misjoin')


def test_baixa_real_com_banco_move_a_obrigacao_de_lado_sem_mudar_o_projetado():
    """Teste de FIXAÇÃO do caminho completo — dirige a baixa DE VERDADE.

    Os outros casos deste bloco escrevem `status`/`valor_pago` à mão, e por
    isso não veem a outra metade da correção: que o mesmo evento que tira o
    gêmeo das previstas é o que debita o banco. Aqui quem paga é
    `FinanceiroService.baixar_pagamento` com um `banco_id` real, e as DUAS
    pernas são afirmadas — a que sai (`saidas_previstas`) e a que entra
    (`banco.saldo_atual`, que vira o `saldo_inicial` do fluxo).

    ⚠️ Não nasce vermelho: o comportamento já funciona depois da correção da
    D2. Ele existe para PRENDER o par — quebrar qualquer uma das pernas
    (a exclusão parar de olhar o estado, ou a baixa parar de debitar o banco)
    derruba este teste.

    O oráculo forte é a última asserção: o `saldo_final_projetado` NÃO muda
    com a baixa. A obrigação muda de lado — sai das previstas e entra no saldo
    do banco — em vez de evaporar (que baixaria o previsto sem baixar o saldo)
    ou de ser contada duas vezes (que baixaria os dois).
    """
    with app.app_context():
        t = um_tenant('onda3_gemeo_baixa', com_fatos=False)
        banco = FinanceiroService.criar_banco(
            t.admin_id, 'Banco D2', '0001', f'CC-{uuid.uuid4().hex[:6]}',
            'CORRENTE', saldo_inicial=Decimal('5000'))
        pai, cp = _par_gemeo_reembolso(t.admin_id, t.obra_id, 700, 'PENDENTE')

        antes = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)
        assert antes['saldo_inicial'] == pytest.approx(5000.0)
        assert antes['saidas_previstas'] == pytest.approx(700.0)
        assert _linhas_previstas(antes, pai.entidade_nome)

        FinanceiroService.baixar_pagamento(
            cp.id, t.admin_id, Decimal('700'), HOJE, 'PIX',
            banco_id=banco.id)

        # Perna 1 — o dinheiro saiu do banco, e o banco É o saldo_inicial.
        assert float(banco.saldo_atual) == pytest.approx(4300.0), (
            f'banco.saldo_atual={banco.saldo_atual}: a baixa real nao debitou '
            f'o banco — sem isso a obrigacao nao entrou em projecao nenhuma')

        depois = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)
        assert depois['saldo_inicial'] == pytest.approx(4300.0)

        # Perna 2 — e por isso, e so por isso, o gemeo sai das previstas.
        assert depois['saidas_previstas'] == pytest.approx(0.0), (
            f"saidas_previstas={depois['saidas_previstas']}: a gemea foi "
            f'baixada pelo banco e a prevista do Pai continua — a mesma '
            f'despesa subtraida duas vezes do saldo projetado')
        assert not _linhas_previstas(depois, pai.entidade_nome)

        # As duas pernas juntas: a obrigacao MUDOU DE LADO, nao evaporou nem
        # foi contada duas vezes.
        assert depois['saldo_final_projetado'] == pytest.approx(
            antes['saldo_final_projetado']), (
            f"saldo_final_projetado foi de {antes['saldo_final_projetado']} "
            f"para {depois['saldo_final_projetado']}: a baixa mexeu em uma "
            f'perna so')
