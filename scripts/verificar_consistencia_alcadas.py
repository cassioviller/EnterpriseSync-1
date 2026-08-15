#!/usr/bin/env python3
"""Consistência das alçadas de um tenant — Fase 3 do ciclo de compras.

📖 spec `docs/superpowers/specs/2026-08-15-alcadas-design.md`; plano A8.

Molde de `scripts/verificar_consistencia_financeiro.py`, e pelo mesmo motivo:
o sensor reusa as MESMAS funções que decidem — `faixa_efetiva`,
`pendencias_de_aprovacao`, `ratificacao_vencida`, `pernas_faltantes`,
`diagnosticar`. Um sensor que reimplementa a regra que vigia não vigia nada:
ele passa a ter os próprios defeitos, e os dois erram juntos exatamente onde
erram igual.

**Seis achados**, e todos são da mesma família — estado que só poderia ter
chegado ali por fora do serviço, ou regra que deixou de descrever o que o
sistema faz:

1. **APROVADA sem a alçada fechada.** A rota confere `esta_totalmente_aprovada`
   antes de transicionar. Menos votos do que a faixa EFETIVA exige significa
   UPDATE na marra, script de correção, ou rota nova que esqueceu do
   chokepoint. Emergência ainda não ratificada NÃO entra aqui: estar APROVADA
   sem voto é o ponto do rito, e ela tem achado próprio.
2. **Emergência vencida sem ratificação.** As 48h passaram e ninguém assinou.
   É o motivo pelo qual a A6 não deve ser ligada em tenant real antes deste
   script existir: ninguém mais enxerga essa requisição.
3. ⚠️ **A janela residual.** Conta liberada DENTRO das 48h cuja emergência
   venceu DEPOIS. Ela já está `liberada` e nada a rebloqueia — reescrever
   `situacao_liberacao` de fora de `liberar()` seria o segundo caminho de
   escrita que a Fase 2 recusou, e a segunda porta em `pagar_conta` que o
   desenho proíbe. É conhecida, é estreita (nota + atesto + liberação em menos
   de 48h) e o lugar certo de ela aparecer é aqui (📖 spec, o ⚠️ nº 3 do 📌 da
   A6). O sinal de que a liberação foi legítima é `liberada_em` preenchido:
   quem passou por `liberar()` passou por `pernas_faltantes`, que recusa a
   emergência já vencida.
4. **Emergência vencida com conta liberada SEM `liberada_em`.** A mesma foto,
   outra causa: a conta não passou por `liberar()`. É a que prova que a sanção
   da A6 está ligada de verdade — se ela aparecer, alguém escreveu
   `situacao_liberacao` por fora.
5. **Faixa com `minimo_cotacoes = 1`.** Uma cotação não é concorrência, é
   orçamento — e 1 é justamente o que se digita achando que se exige "pelo
   menos uma". A tela da A7 recusa; um SQL manual continua sendo possível.
6. **Escada fora do invariante** (zero ou duas faixas de teto aberto, teto
   aberto no meio, teto que não cresce) e **`degrau_aplicado` citando condição
   que faixa nenhuma do tenant ativa** — trilha que explica uma exigência que o
   tenant não faz.

E um MODO à parte, que não procura defeito nenhum: `--simular`. Ver `simular`.

Não altera nada — a varredura roda dentro de um SAVEPOINT que é sempre
desfeito, porque `faixa_efetiva` grava `degrau_aplicado` na sessão por
contrato e medir não pode mudar o que se mede.

Exit code 0 = consistente, 1 = drift, 2 = erro de uso. `--simular` sai 0
sempre: medir não é achar.

Uso:
    python scripts/verificar_consistencia_alcadas.py <admin_id>
        [--json]              # saída legível por máquina
    python scripts/verificar_consistencia_alcadas.py <admin_id> --simular
        [--dias 30] [--json]  # o passo 0a do runbook, com a flag desligada
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@contextmanager
def _sem_escrever():
    """SAVEPOINT que é sempre desfeito. O sensor lê; ele não decide.

    `faixa_efetiva` (e portanto `pendencias_de_aprovacao`) grava
    `degrau_aplicado` na sessão — é o contrato dela, e é certo: quem persiste é
    a rota. Só que aqui não há rota, e uma varredura de auditoria que sujasse a
    sessão do chamador acabaria gravando degrau em requisição antiga na
    primeira vez que alguém rodasse o sensor de dentro de um request.
    """
    from app import db
    sp = db.session.begin_nested()
    try:
        yield
    finally:
        if sp.is_active:
            sp.rollback()


def _horas(delta):
    return round(delta.total_seconds() / 3600.0, 1)


# ---------------------------------------------------------------------------
# Os seis achados
# ---------------------------------------------------------------------------

def inconsistencias(admin_id):
    """Lista de dicionários descrevendo cada drift. Vazia = consistente.

    Não levanta e não escreve: dá para chamar de dentro de um teste, de um
    cron ou de uma tela sem efeito colateral nenhum.
    """
    from datetime import datetime

    from models import (ContaPagar, EstadoRequisicao, FaixaAlcada, PedidoCompra,
                        RequisicaoCompra)
    from services.alcada_compras import (CONDICOES_CONHECIDAS,
                                         MOTIVO_FRACIONAMENTO,
                                         condicoes_ativas_da_faixa,
                                         pendencias_de_aprovacao,
                                         prazo_de_ratificacao,
                                         ratificacao_vencida,
                                         transicao_da_emergencia)
    from services.faixa_alcada_admin import diagnosticar
    from services.financeiro_compra import situacao_liberacao_inicial

    achados = []
    agora = datetime.utcnow()

    with _sem_escrever():
        # 1. APROVADA com menos aprovações do que a faixa EFETIVA exige.
        aprovadas = (RequisicaoCompra.query
                     .filter(RequisicaoCompra.admin_id == admin_id,
                             RequisicaoCompra.estado ==
                             EstadoRequisicao.APROVADA)
                     .all())
        for req in aprovadas:
            # A emergência ainda não ratificada está APROVADA sem voto DE
            # PROPÓSITO — é o ponto inteiro do rito. Cobrá-la aqui seria
            # relatar como defeito o comportamento que a fase construiu; ela
            # tem os achados 2 a 4, que falam do prazo e não da alçada.
            if (transicao_da_emergencia(req) is not None
                    and req.ratificada_em is None):
                continue
            pendencias = pendencias_de_aprovacao(req)
            if pendencias:
                achados.append({
                    'tipo': 'aprovada_sem_a_alcada_fechada',
                    'requisicao_id': req.id,
                    'requisicao_numero': req.numero,
                    'valor_estimado': str(req.valor_estimado or 0),
                    'pendencias': pendencias,
                })

        # 2-4. O rito de emergência: o prazo e a sanção.
        emergenciais = (RequisicaoCompra.query
                        .filter(RequisicaoCompra.admin_id == admin_id,
                                RequisicaoCompra.emergencial.is_(True),
                                RequisicaoCompra.ratificada_em.is_(None))
                        .all())
        for req in emergenciais:
            if not ratificacao_vencida(req, agora=agora):
                continue
            prazo = prazo_de_ratificacao(req)
            achados.append({
                'tipo': 'emergencia_vencida_sem_ratificacao',
                'requisicao_id': req.id,
                'requisicao_numero': req.numero,
                'valor_estimado': str(req.valor_estimado or 0),
                'prazo': str(prazo),
                'horas_de_atraso': _horas(agora - prazo),
            })
            achados.extend(_achados_da_conta(req, prazo, admin_id, ContaPagar,
                                             PedidoCompra,
                                             situacao_liberacao_inicial))

        # 5. Faixa com o mínimo de cotações em 1.
        for faixa in (FaixaAlcada.query
                      .filter(FaixaAlcada.admin_id == admin_id,
                              FaixaAlcada.minimo_cotacoes == 1).all()):
            achados.append({
                'tipo': 'faixa_com_uma_cotacao',
                'faixa_id': faixa.id,
                'ordem': faixa.ordem,
                'valor_ate': str(faixa.valor_ate) if faixa.valor_ate else None,
            })

        # 6a. Os invariantes da escada — o MESMO julgamento da tela da A7.
        for violacao in diagnosticar(admin_id):
            achados.append({
                'tipo': 'escada_fora_do_invariante',
                'violacao': violacao,
            })

        # 6b. `degrau_aplicado` citando condição que faixa nenhuma ativa.
        ativas_no_tenant = set()
        for faixa in FaixaAlcada.query.filter_by(admin_id=admin_id).all():
            ativas_no_tenant.update(condicoes_ativas_da_faixa(faixa))
        # `fracionamento` nunca é citação indevida: ele é a regra do acumulado
        # e por desenho NÃO mora em `condicoes_ativas` (📖 spec, D1).
        toleradas = ativas_no_tenant | {MOTIVO_FRACIONAMENTO}

        com_degrau = (RequisicaoCompra.query
                      .filter(RequisicaoCompra.admin_id == admin_id,
                              RequisicaoCompra.degrau_aplicado != '')
                      .all())
        for req in com_degrau:
            gravados = [c.strip() for c in
                        (req.degrau_aplicado or '').split(',') if c.strip()]
            indevidos = [c for c in gravados if c not in toleradas]
            if not indevidos:
                continue
            ordem = {c: i for i, c in enumerate(CONDICOES_CONHECIDAS)}
            achados.append({
                'tipo': 'degrau_cita_condicao_inativa',
                'requisicao_id': req.id,
                'requisicao_numero': req.numero,
                'degrau_aplicado': req.degrau_aplicado,
                'codigos': sorted(set(indevidos),
                                  key=lambda c: (ordem.get(c, 99), c)),
            })

    return achados


def _achados_da_conta(requisicao, prazo, admin_id, ContaPagar, PedidoCompra,
                      situacao_liberacao_inicial):
    """Os achados 3 e 4: a conta derivada de uma emergência já vencida.

    O RECORTE é o mesmo de `pernas_faltantes`: só pedido cuja conta NASCERIA
    bloqueada (Fluxo A do regime novo). Fora dele a sanção não tem onde morder
    — a conta nasce `liberada` e sempre nasceu —, e relatar isso como drift
    faria o sensor gritar em todo tenant sem a Fase 2 ligada.

    A diferença entre os dois achados é `liberada_em`. Uma conta com ele
    preenchido passou por `liberar()`, que recusa por `pernas_faltantes` —
    isto é, que teria recusado se a emergência já estivesse vencida. Logo a
    liberação aconteceu DENTRO das 48h: é a janela residual, conhecida e
    aceita. Sem `liberada_em` não houve `liberar()` nenhum, e aí a foto é de
    escrita por fora.
    """
    achados = []
    pedidos = PedidoCompra.query.filter_by(
        admin_id=admin_id, requisicao_id=requisicao.id).all()
    for pedido in pedidos:
        if situacao_liberacao_inicial(pedido) != 'bloqueada':
            continue
        contas = ContaPagar.query.filter_by(
            admin_id=admin_id, pedido_compra_id=pedido.id).all()
        for cp in contas:
            if (cp.situacao_liberacao or 'liberada') == 'bloqueada':
                continue    # a sanção pegou: é o estado esperado
            comum = {
                'requisicao_id': requisicao.id,
                'requisicao_numero': requisicao.numero,
                'pedido_id': pedido.id,
                'pedido_numero': pedido.numero,
                'conta_pagar_id': cp.id,
                'prazo': str(prazo),
                'liberada_em': str(cp.liberada_em) if cp.liberada_em else None,
            }
            if cp.liberada_em is not None:
                achados.append(dict(comum, tipo='janela_residual_emergencia'))
            else:
                achados.append(
                    dict(comum, tipo='emergencia_vencida_com_conta_liberada'))
    return achados


# ---------------------------------------------------------------------------
# `--simular` — o passo 0a do runbook
# ---------------------------------------------------------------------------

class _FaixaComAsQuatroCondicoes:
    """A faixa real, com as QUATRO condições ligadas. Só para simular.

    A simulação existe para responder "o que aconteceria se eu ligasse a
    condição X" — e `condicoes_disparadas` só avalia o que a faixa já ativa.
    Medir o que já está ligado não ajuda ninguém a decidir o que ligar, então a
    faixa entra por este proxy: `condicoes_ativas` passa a ser as quatro, e
    todo o resto (`minimo_cotacoes`, `id`, `ordem`) continua sendo o da linha
    de verdade — `sem_cotacao` pergunta o mínimo de cotações DA FAIXA, e
    inventá-lo aqui inventaria o número que a simulação promete medir.

    Proxy, e não um `setattr` na faixa carregada: escrever no objeto mapeado
    sujaria a sessão com uma alteração que ninguém pediu.
    """

    def __init__(self, faixa):
        self._faixa = faixa

    @property
    def condicoes_ativas(self):
        from services.alcada_compras import CONDICOES_CONHECIDAS
        return ','.join(CONDICOES_CONHECIDAS)

    def __getattr__(self, nome):
        return getattr(self._faixa, nome)


def simular(admin_id, dias=30):
    """Quantas requisições dos últimos `dias` subiriam de faixa, e por quê.

    **Roda com a flag DESLIGADA e não a consulta.** É possível porque os
    primitivos do motor (`faixa_para_valor`, `valor_para_alcada`,
    `condicoes_disparadas`) não consultam flag nem regime por contrato — quem
    decide se eles valem é `decisao_de_alcada`, e é justamente ela que a
    simulação NÃO chama, porque ela grava `degrau_aplicado`.

    É a resposta operacional ao ⚠️ da decisão D1: `fora_do_orcamento` dispara
    em toda requisição sem etapa apontada, e em tenant que ainda não preenche
    etapa com disciplina isso sobe quase tudo um degrau. Com o número na mão,
    deixar a condição fora de `condicoes_ativas` na primeira volta deixa de ser
    palpite.

    `fornecedor_novo` aparece como NÃO AVALIÁVEL, e não como "não disparou": a
    requisição não tem fornecedor — ele só é escolhido na emissão —, e a
    resposta honesta antes dela é que não dá para saber. É desenho, não
    limitação da simulação (📖 spec, o 📌 da A4).

    O fracionamento é contado SEPARADO das quatro: ele move a faixa de
    partida, não é uma condição da linha, e não é ligável por tenant.
    """
    from datetime import datetime, timedelta
    from decimal import Decimal

    from models import FaixaAlcada, RequisicaoCompra
    from scripts.flag_alcadas_avancadas import alcadas_avancadas_ativa
    from services.alcada_compras import (CONDICOES_CONHECIDAS,
                                         _cond_fornecedor_novo,
                                         _mesma_faixa, condicoes_disparadas,
                                         faixa_para_valor, valor_para_alcada)

    corte = datetime.utcnow() - timedelta(days=dias)
    resumo = {
        'dias': dias,
        'flag_ligada': alcadas_avancadas_ativa(admin_id),
        'total': 0,
        'subiriam': 0,
        'fracionamento': 0,
        'por_condicao': {c: 0 for c in CONDICOES_CONHECIDAS},
        'nao_avaliaveis': {c: 0 for c in CONDICOES_CONHECIDAS},
    }

    with _sem_escrever():
        escada = (FaixaAlcada.query
                  .filter_by(admin_id=admin_id, ativo=True)
                  .order_by(FaixaAlcada.ordem.asc())
                  .all())
        requisicoes = (RequisicaoCompra.query
                       .filter(RequisicaoCompra.admin_id == admin_id,
                               RequisicaoCompra.created_at >= corte)
                       .all())

        for req in requisicoes:
            resumo['total'] += 1
            base = faixa_para_valor(admin_id, req.valor_estimado)

            # (1) o acumulado da janela move a faixa de PARTIDA
            partida = base
            valor = valor_para_alcada(req)
            if valor > Decimal(str(req.valor_estimado or 0)):
                por_acumulado = faixa_para_valor(admin_id, valor)
                if not _mesma_faixa(por_acumulado, base):
                    partida = por_acumulado
                    resumo['fracionamento'] += 1

            # (2) as condições, a partir dali — as quatro, ligadas ou não
            disparadas = condicoes_disparadas(
                req, _FaixaComAsQuatroCondicoes(partida))
            for codigo in disparadas:
                resumo['por_condicao'][codigo] += 1
            if _cond_fornecedor_novo(req, None) is None:
                resumo['nao_avaliaveis']['fornecedor_novo'] += 1

            try:
                posicao = escada.index(partida)
            except ValueError:
                # `_FaixaSeguranca`: tenant sem faixa nenhuma. O degrau é
                # sempre saturado, e "subiria" é o que o acumulado já disse.
                if not _mesma_faixa(partida, base):
                    resumo['subiriam'] += 1
                continue

            efetiva = escada[min(posicao + len(disparadas), len(escada) - 1)]
            if not _mesma_faixa(efetiva, base):
                resumo['subiriam'] += 1

    return resumo


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _imprimir_achados(admin_id, achados):
    print(f'tenant {admin_id}: {len(achados)} inconsistência(s).\n')
    for a in achados:
        tipo = a['tipo']
        if tipo == 'aprovada_sem_a_alcada_fechada':
            print(f"  Requisição {a['requisicao_numero']} está APROVADA mas a "
                  f"alçada não fecha: {'; '.join(a['pendencias'])}")
        elif tipo == 'emergencia_vencida_sem_ratificacao':
            print(f"  Requisição {a['requisicao_numero']} foi aprovada pelo "
                  f"rito de emergência e está {a['horas_de_atraso']}h além do "
                  f"prazo de ratificação (venceu em {a['prazo']})")
        elif tipo == 'janela_residual_emergencia':
            print(f"  ContaPagar {a['conta_pagar_id']} (pedido "
                  f"{a['pedido_numero'] or a['pedido_id']}) foi LIBERADA em "
                  f"{a['liberada_em']}, dentro das 48h, e só depois a "
                  f"emergência da requisição {a['requisicao_numero']} venceu "
                  f"(em {a['prazo']}). É a JANELA RESIDUAL: a liberação foi "
                  f"legítima e nada a rebloqueia — rebloquear de fora de "
                  f"liberar() seria a segunda porta que o desenho proíbe. "
                  f"Cobre a ratificação pela tela da requisição")
        elif tipo == 'emergencia_vencida_com_conta_liberada':
            print(f"  ContaPagar {a['conta_pagar_id']} (pedido "
                  f"{a['pedido_numero'] or a['pedido_id']}) está LIBERADA sem "
                  f"nunca ter passado por liberar() e a emergência da "
                  f"requisição {a['requisicao_numero']} venceu em "
                  f"{a['prazo']} — a sanção da A6 não pegou nesta conta")
        elif tipo == 'faixa_com_uma_cotacao':
            print(f"  Faixa de ordem {a['ordem']} (id {a['faixa_id']}) exige "
                  f"minimo_cotacoes = 1. Uma cotação não é concorrência, é "
                  f"orçamento: use 0 (não exige mapa) ou 2 ou mais")
        elif tipo == 'escada_fora_do_invariante':
            print(f"  Escada de alçada: {a['violacao']}")
        else:
            print(f"  Requisição {a['requisicao_numero']} tem "
                  f"degrau_aplicado = {a['degrau_aplicado']!r}, que cita "
                  f"{', '.join(a['codigos'])} — condição que faixa nenhuma "
                  f"deste tenant ativa. A trilha está explicando uma "
                  f"exigência que o tenant não faz")
    print('\nNenhum destes estados sai do serviço, com uma exceção nomeada: a '
          'janela residual, que é conhecida e fica registrada em vez de '
          'fechada (📖 spec, o 📌 da A6).')


def _imprimir_simulacao(admin_id, r):
    from services.alcada_compras import ROTULOS_CONDICAO

    print(f'tenant {admin_id}: simulação dos últimos {r["dias"]} dias '
          f'(flag alcadas_avancadas_ativa: '
          f'{"LIGADA" if r["flag_ligada"] else "DESLIGADA"}).\n')
    print(f'  requisições no período: {r["total"]}')
    if not r['total']:
        print('\n  Sem requisição no período — nada a medir. Amplie a janela '
              'com --dias antes de decidir.')
        return
    pct = 100.0 * r['subiriam'] / r['total']
    print(f'  subiriam de faixa com as QUATRO condições ligadas: '
          f'{r["subiriam"]} ({pct:.0f}%)')
    print(f'  subiriam por fracionamento (acumulado da janela): '
          f'{r["fracionamento"]}\n')
    print('  por condição — quantas DISPARARIAM cada uma, se ligada:')
    for codigo, quantas in r['por_condicao'].items():
        nao_avaliaveis = r['nao_avaliaveis'].get(codigo, 0)
        pct_c = 100.0 * quantas / r['total']
        linha = (f'    {codigo:<20} {quantas:>5}  ({pct_c:.0f}% das '
                 f'requisições do período)')
        if nao_avaliaveis:
            linha += (f'  — {nao_avaliaveis} não avaliável(is): só a EMISSÃO '
                      f'conhece o fornecedor')
        print(linha)
        print(f'      {ROTULOS_CONDICAO.get(codigo, codigo)}')

    print('\n  O que fazer com o número: quem decide se cada condição roda '
          'neste tenant é\n  `faixa_alcada.condicoes_ativas`, editável na tela '
          '(Configurações › Alçadas de\n  Compra) sem deploy. Se '
          '`fora_do_orcamento` estiver subindo quase tudo, é sinal\n  de que o '
          'tenant ainda não preenche etapa com disciplina: deixe-a fora da '
          'primeira\n  volta e ligue depois de medir de novo (📖 spec, o ⚠️ '
          'da decisão D1).')


def main():
    parser = argparse.ArgumentParser(
        description='Consistência das alçadas de compra (Fase 3)')
    parser.add_argument('admin_id', type=int)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--simular', action='store_true',
                        help='não procura drift: mede quantas requisições dos '
                             'últimos N dias subiriam de faixa e por qual '
                             'condição. Roda com a flag desligada.')
    parser.add_argument('--dias', type=int, default=30,
                        help='a janela da simulação (padrão: 30)')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.simular:
            resumo = simular(args.admin_id, dias=args.dias)
            if args.json:
                print(json.dumps(resumo, ensure_ascii=False, indent=2))
            else:
                _imprimir_simulacao(args.admin_id, resumo)
            # Medir não é achar: a simulação sai 0 mesmo quando o número
            # assusta. O número é o insumo da decisão, não a decisão.
            return 0

        achados = inconsistencias(args.admin_id)

    if args.json:
        print(json.dumps(achados, ensure_ascii=False, indent=2))
    elif not achados:
        print(f'tenant {args.admin_id}: sem drift nas alçadas de compra.')
    else:
        _imprimir_achados(args.admin_id, achados)

    return 1 if achados else 0


if __name__ == '__main__':
    sys.exit(main())
