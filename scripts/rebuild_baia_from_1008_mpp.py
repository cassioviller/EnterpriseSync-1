#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstrói o canônico da Baia a partir do CRONOGRAMA BAIAS 10.08.mpp.

Sucessor de `rebuild_baia_from_0607_mpp.py`. O .mpp de 10/08 é a revisão
estrutural que o `ESTADO_ATUALIZACAO_BAIA.md` estava esperando desde 07/08:
entram as tarefas do reforço das vigas transversais (brocas, blocos de
coroamento, laje), a caixaria das calçadas como tarefa própria, e a inversão
de precedência decidida na reunião de 05/08 (valas de drenagem ANTES das
concretagens). São 109 tarefas contra as 101 do 06.07.

O que este script faz, na ordem:

  1. `cronograma_tarefas` reconstruído do .mpp (nivel = outline + 1);
  2. `eap[*].cronograma.tarefas_mpp` reclassificado pelo mesmo classificador
     por keyword do 0607 (estendido para os nomes novos) — custo e itens de
     cada etapa vêm intactos da produção;
  3. apontamentos dos RDOs remapeados dos ids do 06.07 para os do 10.08
     **pelo caminho hierárquico** (Galpão A/B > Fundação > nome), não pelo id
     nem pelo nome solto: 44 nomes se repetem entre os galpões;
  4. os dias que estavam com `apontamentos: []` por falta de tarefa (28/07 e
     04, 05 e 06/08) ganham o físico, estimado a partir do TEXTO do próprio
     RDO — ver `DE_PARA_MANUAL` e `APONTAMENTOS_NOVOS`, cada linha com a
     frase que a sustenta. O % do MS Project NÃO é usado como fonte.

Contrato, custos, medições, fluxo de caixa, resumo e o texto/fotos dos RDOs
são preservados da base de produção (origin/main).

Uso:
    python scripts/rebuild_baia_from_1008_mpp.py
"""
import json
import subprocess
import sys
import unicodedata

sys.path.insert(0, 'scripts')
from dump_mpp import dump  # noqa: E402

MPP = 'CRONOGRAMA BAIAS 10.08.mpp'
OUT = '/home/runner/workspace/cronograma_fisico_financeiro_baias.json'
DATA_CRONOGRAMA = '2026-08-10'
FIM_CRONOGRAMA = '2026-10-19'


def na(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()


# ---------------------------------------------------------------- classificador
def etapa_de(nome):
    """Folha -> código de etapa da EAP. None = físico-puro (sem custo).

    Ordem importa. Estendido em 10/08 para os nomes que a revisão trouxe:
    'revisao do projeto' (antes caía em ESTLSF pelo 'LSF' do nome), 'fase de
    orcamento e fornecimento de aco', 'armacao de ferragem da nova fundacao',
    'caixaria' e 'aco para pilares'.
    """
    n = na(nome)
    # físico-puro: entra no cronograma, não tem custo de etapa
    if (n.startswith('fazenda') or n.startswith('ajr') or 'limpeza geral' in n
            or 'desmobiliza' in n or 'preenchimento' in n):
        return None
    # a revisão do projeto é fundação, apesar do 'LSF' no nome
    if 'revisao do projeto' in n:
        return 'FUND'
    if 'hidraulica' in n or 'hidraulico' in n:
        return 'HIDRO'
    if 'eletrica' in n or 'iluminacao' in n:
        return 'ELET'
    if 'estudo de solo' in n or 'projetos' in n or 'mobilizacao equipe' in n \
            or 'gabarito' in n:
        return 'PRELIM'
    if 'moledo' in n:
        return 'MOLEDO'
    if 'portao' in n or 'portoes' in n:
        return 'PORTAO'
    if 'pintura' in n:
        return 'PINT'
    if 'plaqueamento' in n or 'basecoat' in n:
        return 'FECHA'
    if 'lsf' in n:
        return 'ESTLSF'
    if 'telhado shingle' in n or 'telhado single' in n:
        return 'COBERT'
    if 'estrutura metalica' in n or 'aco para telhado' in n \
            or 'aco para pilares' in n or 'pilares metalicos' in n:
        return 'ESTMET'
    if any(k in n for k in (
            'baldrame', 'broca', 'ferragen', 'ferragem', 'concretagem',
            'concreto magro', 'chapas base', 'calcada', 'sapata', 'alvenaria',
            'icamento', 'conduite', 'marcacao dos pilares', 'caixaria',
            'fornecimento de aco', 'nova fundacao', 'vigas transversais')):
        return 'FUND'
    return '??'


# ------------------------------------------------------------------ de/para RDO
# Casos que o casamento por caminho NÃO resolve, porque a revisão renomeou ou
# retirou a tarefa. Chave = id no 06.07; valor = (id no 10.08 ou None, motivo).
DE_PARA_MANUAL = {
    # renomeadas, mesmo serviço e mesmo ramo
    20: (18, 'B "AJR ... Nivelamento Das Calçadas" -> "AJR ... Nivelamento e '
             'Compactação das Calçadas"'),
    65: (68, 'A idem'),
    21: (21, 'B "Execução Ferragem Calçada, Travamento Chapas Base" -> '
             '"Execução de Caixaria, Ferragem das Calçadas, posicionamento '
             'da armação" (a caixaria virou escopo da mesma tarefa)'),
    # sem sucessor: o serviço de 17 e 20/07 no Galpão A foi a armação das 12
    # sapatas dos pilares de tronco, que a "Execução de Ferragens Para
    # Fundação" (A) já fechou em 100% em 17/07. A ferragem das calçadas do
    # Galpão A foi REPROGRAMADA para 17-21/08 e está em 0% — herdar 60% ali
    # infla o físico do galpão. REVISAR.
    66: (None, 'A "Execução Ferragem Calçada, Travamento Chapas Base" — '
               'reprogramada para 17-21/08, ainda não começou'),
}

# Dias que estavam sem físico por falta de tarefa, agora com onde apontar.
# Cada linha traz a frase do RDO que a sustenta. Substitui o que houver no
# dia para a mesma tarefa. Ids são do 10.08.
APONTAMENTOS_NOVOS = {
    # --- t19 Revisão do Projeto Fundação e LSF (B, 28-30/07) ---
    '2026-07-28': [
        (19, 33, 'questionamentos técnicos da revisão encaminhados ao Eng. Gustavo'),
        (21, 50, 'lona sobre a calçada + posicionamento das armaduras das vigas '
                 'longitudinais nas valas do Galpão B'),
    ],
    '2026-07-29': [
        (19, 66, 'questionamentos esclarecidos e encaminhados aos projetistas '
                 'estrutural e de LSF'),
        (21, 55, 'início da montagem das armaduras da calçada (malhas inferior '
                 'e superior) — reescalado, ver REVISAR'),
    ],
    '2026-07-30': [
        (19, 100, 'ao fim do expediente a projetista encaminhou a revisão do '
                  'projeto estrutural das fundações'),
        (21, 60, 'continuidade do travamento das malhas da segunda calçada'),
    ],
    # --- t20 Fase de Orçamento e Fornecimento de aço (B, 31/07-04/08) ---
    '2026-07-31': [
        (20, 60, 'contratado o equipamento de perfuração e adquirida a ferragem '
                 'das novas brocas — entrega prevista 04/08'),
        (21, 65, 'concluído o travamento das armaduras da segunda calçada'),
    ],
    '2026-08-03': [
        (21, 70, 'armação e travamento da armadura longitudinal da calçada do '
                 'Galpão B — fecha a FERRAGEM; a caixaria começa em 04/08'),
    ],
    '2026-08-04': [
        (20, 100, 'recebido na obra o aço dos reforços das vigas transversais e '
                  'das novas brocas'),
        (23, 30, 'armação de 22 brocas de reforço (A e B) + início da armação '
                 'dos blocos de coroamento e da laje das vigas transversais (B)'),
        (70, 30, 'as mesmas 22 brocas cobrem também o Galpão A'),
        (21, 80, 'iniciada a caixaria das calçadas do Galpão B'),
    ],
    '2026-08-05': [
        (22, 50, 'executada a escavação das valas das novas lajes de reforço (B)'),
        (23, 60, 'armação de reforço de 08 vigas transversais do Galpão B'),
        (21, 90, 'executada a caixaria de uma das calçadas do Galpão B'),
    ],
    '2026-08-06': [
        (22, 75, 'escavação das valas concluída e perfuração das novas brocas '
                 'apenas INICIADA — o Project marca 100%, o texto não'),
        (23, 85, 'armação de reforço de mais 05 vigas transversais'),
        (21, 100, 'finalizada a caixaria da segunda calçada, concluindo a etapa'),
    ],
}

# Fechamento pelo % DO MS PROJECT (decisão do usuário em 11/08, depois de o
# engenheiro confirmar que a coluna %concluído do .mpp está atualizada).
#
# A curva INTERMEDIÁRIA continua vindo do texto dos RDOs — é ela que dá a forma
# do avanço dia a dia, e em 18 tarefas ela já fechava no mesmo valor do Project.
# Aqui só entra o VALOR FINAL de cada tarefa em que os dois discordavam.
#
# Data de cada fechamento: o RDO mais recente dentro da janela da tarefa. Quando
# a janela do Project é inteiramente POSTERIOR ao último RDO (06/08 — o export do
# WhatsApp termina aí), o fechamento é ANTECIPADO para 06/08 e marcado abaixo:
# o valor fica certo, a data adianta alguns dias até o próximo export corrigir.
#
# (tarefa, data, pct, antecipado, motivo)
FECHAMENTO_PROJECT = [
    (3, '2026-06-30', 100, False, 'projetos LSF/telhado/piso/baldrame — o RDO '
                                  'parou de citar em 30/06, o Project fecha'),
    (4, '2026-06-29', 100, False, 'Mobilização Equipe — 1 dia, 29/06'),
    (15, '2026-07-08', 100, False, 'concreto magro nas vigas baldrames (B)'),
    (17, '2026-07-17', 100, False, 'entrega das chapas base (B) — fornecimento, '
                                   'o diário não reporta'),
    (34, '2026-08-05', 100, False, 'fabricação de aço para pilares (B) — '
                                   'serviço de fornecedor, fora do diário'),
    (65, '2026-07-23', 100, False, 'concreto magro nas vigas baldrames (A)'),
    (67, '2026-07-31', 100, False, 'entrega das chapas base (A)'),
    (70, '2026-08-06', 100, False, 'armação da nova fundação (A) — o Project '
                                   'fecha em 10/08, sem RDO depois de 06/08'),
    (22, '2026-08-06', 100, False, 'novas valas e brocas (B) — o texto de 06/08 '
                                   'só dizia "iniciada" a perfuração'),
    (23, '2026-08-06', 100, False, 'armação da nova fundação (B) — idem, fecha '
                                   'em 10/08 no Project'),
    (69, '2026-08-06', 100, True, 'novas valas e brocas (A) — janela 07-10/08, '
                                  'INTEIRAMENTE depois do último RDO'),
    (24, '2026-08-06', 50, True, 'valas de drenagem (B) — janela 08-11/08; o '
                                 'RDO de 06/08 ainda esperava liberação do '
                                 'Grupo Mônica'),
]

# Tarefas em que o RDO diz MAIS que o Project. Não são rebaixadas: o RDO é
# documento assinado do que foi executado, e rebaixar seria retrocesso (o
# atualizador recusa). Ficam registradas para o engenheiro conciliar no .mpp.
CONFLITO_RDO_MAIOR = [
    (45, 'Instalação Infra Hidráulica (B)', 100, 0),
    (92, 'Instalação Infra Hidráulica (A)', 100, 0),
]

# Reescalonamento da t21 (B): a tarefa passou a cobrir ferragem + caixaria das
# calçadas, então a série antiga (que fechava 100% em 03/08, só com ferragem)
# não cabe mais. Ver REVISAR no relatório.
REESCALA_T21 = {'2026-07-24': 30, '2026-07-27': 45}


# ---------------------------------------------------------- regras do parser
REGRAS = 'docs/rdo/regras_apontamento_baia.json'

# Regras cujo destino NÃO é o sucessor da tarefa antiga. None = remover.
REGRAS_OVERRIDE = {
    # o reforço tem tarefa própria agora — não é mais "Ferragens Para Fundação"
    'blocos-coroamento-a': 70,
    # "Locação das Chapas Base com Topógrafo" saiu do cronograma revisado; o
    # que sobrou é "Entrega das Chapas Base", que é fornecimento e não aparece
    # no diário de obra. Sem tarefa para a locação -> regra removida.
    'chapas-base-b': None,
    'chapas-base-a': None,
    # a armação das sapatas dos pilares de tronco (17 e 20/07) também ficou sem
    # tarefa: a revisão não trouxe sucessora. Ver sem_tarefa_no_cronograma.
    'ferragem-calcada-sapatas-a': None,
}

# As regras de "armação + viga" (quantitativo de 48 un) não podem engolir os
# bullets do reforço estrutural, que têm tarefa própria desde a revisão.
REGRAS_NAO_QUANDO = {
    'ferragem-fundacao-b': ['reforço', 'blocos de coroamento',
                            'laje das vigas transversais'],
    'ferragem-fundacao-a': ['reforço', 'blocos de coroamento',
                            'laje das vigas transversais'],
}

# Vocabulário que a revisão estrutural trouxe e que ainda não tinha regra —
# são os bullets que caíram como "bullet sem regra" de 04 a 06/08.
REGRAS_NOVAS = [
    {'id': 'reforco-fundacao-b', 'quando': ['armação', 'reforço'], 'galpao': 'B',
     'tarefa_mpp': 23, 'forma': 'pct',
     'observacao': 'Brocas de reforço, blocos de coroamento e laje das vigas '
                   'transversais — escopo da revisão de 30/07.'},
    {'id': 'reforco-fundacao-a', 'quando': ['armação', 'reforço'], 'galpao': 'A',
     'tarefa_mpp': 70, 'forma': 'pct'},
    {'id': 'blocos-coroamento-b', 'quando': ['blocos de coroamento'],
     'galpao': 'B', 'tarefa_mpp': 23, 'forma': 'pct'},
    {'id': 'laje-vigas-transversais-b', 'quando': ['laje', 'vigas transversais'],
     'galpao': 'B', 'tarefa_mpp': 23, 'forma': 'pct'},
    {'id': 'laje-vigas-transversais-a', 'quando': ['laje', 'vigas transversais'],
     'galpao': 'A', 'tarefa_mpp': 70, 'forma': 'pct'},
    {'id': 'escavacao-valas-reforco-b', 'quando': ['escava', 'valas'],
     'nao_quando': ['esgoto', 'drenagem'], 'galpao': 'B', 'tarefa_mpp': 22,
     'forma': 'marco', 'pct_parcial': 50,
     'observacao': 'nao_quando separa das valas de esgoto (infra hidráulica) e '
                   'das valas de drenagem da Fazenda, que têm tarefa própria.'},
    {'id': 'escavacao-valas-reforco-a', 'quando': ['escava', 'valas'],
     'nao_quando': ['esgoto', 'drenagem'], 'galpao': 'A', 'tarefa_mpp': 69,
     'forma': 'marco', 'pct_parcial': 50},
    {'id': 'perfuracao-brocas-reforco-b', 'quando': ['perfuração', 'brocas'],
     'galpao': 'B', 'tarefa_mpp': 22, 'forma': 'marco', 'pct_parcial': 75},
    {'id': 'perfuracao-brocas-reforco-a', 'quando': ['perfuração', 'brocas'],
     'galpao': 'A', 'tarefa_mpp': 69, 'forma': 'marco', 'pct_parcial': 75},
    {'id': 'caixaria-calcada-b', 'quando': ['caixaria', 'calçada'],
     'galpao': 'B', 'tarefa_mpp': 21, 'forma': 'pct',
     'observacao': 'A caixaria virou escopo da mesma tarefa da ferragem das '
                   'calçadas — ver a série reescalada em ESTADO_ATUALIZACAO_BAIA.md.'},
    {'id': 'caixaria-calcada-a', 'quando': ['caixaria', 'calçada'],
     'galpao': 'A', 'tarefa_mpp': 73, 'forma': 'pct'},
    {'id': 'drenagem-valas-b', 'quando': ['drenagem'], 'galpao': 'B',
     'tarefa_mpp': 24, 'forma': 'marco', 'pct_parcial': 50,
     'observacao': 'Reunião de 05/08: a drenagem passou a vir ANTES das '
                   'concretagens. Tarefa da Fazenda — físico sem custo.'},
    {'id': 'drenagem-valas-a', 'quando': ['drenagem'], 'galpao': 'A',
     'tarefa_mpp': 72, 'forma': 'marco', 'pct_parcial': 50},
]

SEM_TAREFA_NOVOS = [
    'ATUALIZAÇÃO 11/08: "Locação das Chapas Base com Topógrafo" (17/62 no '
    '06.07) saiu do cronograma revisado — no lugar entrou "Entrega das Chapas '
    'Base" (17/67), que é fornecimento e não aparece no diário. As regras '
    'chapas-base-a/b foram removidas.',
    'ATUALIZAÇÃO 11/08: a armação das sapatas dos pilares de tronco (12 un, 17 '
    'e 20/07 no Galpão A) continua sem tarefa — a revisão não trouxe sucessora '
    'para a "Execução Ferragem Calçada, Travamento Chapas Base" (66) daqueles '
    'dias. A regra ferragem-calcada-sapatas-a foi removida e os 2 apontamentos '
    'históricos foram descartados no de-para.',
    'ATUALIZAÇÃO 11/08: o cocho em alvenaria em si segue sem tarefa própria; o '
    'que a revisão trouxe foi a "Revisão do Projeto Fundação e LSF - Execução '
    'de Cocho em Alvenaria" (19), que é a tarefa do PROJETO, não da execução.',
]


def _reescrever_regras(remap, relatorio):
    """Reaponta os `tarefa_mpp` das regras do parser para os ids do 10.08.

    Sem isto, a próxima rodada de WhatsApp sugeriria a tarefa errada em
    silêncio: no 06.07 o id 14 era "Ferragens Para Fundação (B)", no 10.08 é
    "Concretagem das Brocas (B)".
    """
    regras = json.load(open(REGRAS, encoding='utf-8'))
    saida = []
    for r in regras['regras']:
        rid = r['id']
        if rid in REGRAS_OVERRIDE:
            destino = REGRAS_OVERRIDE[rid]
        else:
            destino = remap.get(r['tarefa_mpp'])
        if destino is None:
            relatorio.append(f'  - regra {rid} REMOVIDA (sem tarefa no 10.08)')
            continue
        if destino != r['tarefa_mpp']:
            relatorio.append(f'  ~ regra {rid}: {r["tarefa_mpp"]} -> {destino}')
        r['tarefa_mpp'] = destino
        if rid in REGRAS_NAO_QUANDO:
            r['nao_quando'] = sorted(set(r.get('nao_quando', []))
                                     | set(REGRAS_NAO_QUANDO[rid]))
        saida.append(r)
    existentes = {r['id'] for r in saida}
    for nova in REGRAS_NOVAS:
        if nova['id'] in existentes:
            continue
        saida.append(dict(nova))
        relatorio.append(f'  + regra {nova["id"]} -> t{nova["tarefa_mpp"]}')
    regras['regras'] = saida
    for obs in SEM_TAREFA_NOVOS:
        if obs not in regras['sem_tarefa_no_cronograma']:
            regras['sem_tarefa_no_cronograma'].append(obs)
    return regras


def main():
    mpp = dump(MPP)
    base = json.loads(subprocess.check_output(
        ['git', 'show', 'origin/main:cronograma_fisico_financeiro_baias.json']))

    # ---- 1) cronograma_tarefas -------------------------------------------
    FERRAGENS_KEY = 'ferragens para fundacao'
    ferragens_ids = []
    tarefas = []
    for t in mpp:
        o = int(t.get('outline', 0))
        tarefas.append({
            'id': t['id'], 'nivel': o + 1, 'nome': t['nome'],
            'inicio': t.get('inicio'), 'fim': t.get('fim'),
            'dias': t.get('dias') or 1, 'pct_fisico': 0,
            'predecessoras': t.get('predecessoras', []),
            'resumo': bool(t.get('resumo')),
        })
        if not t.get('resumo') and FERRAGENS_KEY in na(t['nome']):
            ferragens_ids.append(t['id'])
    # quantidade_total=48 na 1ª ferragens (recebe os apontamentos por quantidade)
    ferr_alvo = min(ferragens_ids) if ferragens_ids else None
    for row in tarefas:
        if row['id'] == ferr_alvo:
            row['quantidade_total'] = 48
            row['unidade'] = 'un'

    # ---- 2) folhas -> etapa ----------------------------------------------
    mpp_by = {t['id']: t for t in mpp}
    por_etapa = {}
    fisico_puro = []
    naoclass = []
    for t in mpp:
        if t.get('resumo'):
            continue
        et = etapa_de(t['nome'])
        if et is None:
            fisico_puro.append(t['id'])
        elif et == '??':
            naoclass.append((t['id'], t['nome']))
        else:
            por_etapa.setdefault(et, []).append(t['id'])
    if naoclass:
        raise SystemExit(f'tarefas sem etapa: {naoclass}')

    # ---- 3) eap: custo da produção + tarefas do .mpp novo -----------------
    def datas_de(ids):
        ds = [mpp_by[i]['inicio'] for i in ids if mpp_by[i].get('inicio')]
        fs = [mpp_by[i]['fim'] for i in ids if mpp_by[i].get('fim')]
        return (min(ds) if ds else None, max(fs) if fs else None)

    raiz = mpp[0]
    for e in base['eap']:
        ids = sorted(por_etapa.get(e['codigo'], []))
        if ids:
            ini, fim = datas_de(ids)
        elif e['cronograma'].get('transversal'):
            # INDIRETOS não tem tarefa: roda o período da obra inteira, que a
            # revisão esticou de 08/10 para 19/10.
            ini, fim = raiz['inicio'], raiz['fim']
        else:
            ini, fim = e['cronograma'].get('inicio'), e['cronograma'].get('fim')
        e['cronograma'] = {'inicio': ini, 'fim': fim, 'pct_fisico': 0,
                           'tarefas_mpp': ids,
                           'transversal': e['cronograma'].get('transversal', False)}

    # ---- 4) de/para dos apontamentos, por caminho hierárquico -------------
    def caminhos(lst, chave_nivel, base_nivel):
        pilha = {}
        out = {}
        for t in lst:
            n = t[chave_nivel] - base_nivel
            for k in [x for x in pilha if x >= n]:
                del pilha[k]
            pilha[n] = t['nome'].strip()
            out[t['id']] = ' > '.join(pilha[k] for k in sorted(pilha))
        return out

    cam_antigo = caminhos(base['cronograma_tarefas'], 'nivel', 1)
    cam_novo = {v: k for k, v in caminhos(mpp, 'outline', 0).items()}

    remap = {}
    sem_par = []
    for old_id, cam in cam_antigo.items():
        if old_id in DE_PARA_MANUAL:
            novo, _motivo = DE_PARA_MANUAL[old_id]
            remap[old_id] = novo
        elif cam in cam_novo:
            remap[old_id] = cam_novo[cam]
        else:
            remap[old_id] = None
            sem_par.append((old_id, cam))

    perdidos = []
    for r in base.get('rdos', []):
        novos = []
        for a in r.get('apontamentos', []):
            destino = remap.get(a['tarefa_mpp'], None)
            if destino is None:
                perdidos.append((r['data'], a['tarefa_mpp'],
                                 cam_antigo.get(a['tarefa_mpp'], '?')))
                continue
            a['tarefa_mpp'] = destino
            novos.append(a)
        r['apontamentos'] = novos

    # ---- 4b) reescala da t21 e apontamentos novos -------------------------
    por_data = {r['data']: r for r in base.get('rdos', [])}
    for data, pct in REESCALA_T21.items():
        for a in por_data.get(data, {}).get('apontamentos', []):
            if a['tarefa_mpp'] == 21:
                a['pct'] = pct
    inseridos = 0
    for data, itens in APONTAMENTOS_NOVOS.items():
        rdo = por_data.get(data)
        if rdo is None:
            raise SystemExit(f'RDO {data} não existe na base')
        for tid, pct, _origem in itens:
            for a in rdo['apontamentos']:
                if a['tarefa_mpp'] == tid:
                    a['pct'] = pct
                    a.pop('quantidade', None)
                    break
            else:
                rdo['apontamentos'].append({'tarefa_mpp': tid, 'pct': pct})
            inseridos += 1

    # ---- 4c) fechamento pelo % do MS Project ------------------------------
    fechados = []
    for tid, data, pct, antecipado, motivo in FECHAMENTO_PROJECT:
        rdo = por_data.get(data)
        if rdo is None:
            raise SystemExit(f'RDO {data} não existe na base (fechamento t{tid})')
        for a in rdo['apontamentos']:
            if a['tarefa_mpp'] == tid:
                antes = a.get('pct', a.get('quantidade'))
                a['pct'] = pct
                a.pop('quantidade', None)
                break
        else:
            antes = None
            rdo['apontamentos'].append({'tarefa_mpp': tid, 'pct': pct})
        fechados.append((tid, data, antes, pct, antecipado, motivo))

    # ---- 5) cronograma + contrato + _meta ---------------------------------
    base['cronograma_tarefas'] = tarefas
    base['contrato']['data_fim_cronograma'] = FIM_CRONOGRAMA
    base['_meta']['fontes'] = [
        f'{MPP} (MS Project — cronograma físico revisado, 109 tarefas c/ split '
        'Galpão A/B e as tarefas do reforço estrutural de 30/07)',
        'Planilha de Custos REV01 (custos por etapa — preservados da produção)',
        'Textos dos RDOs (WhatsApp) — fonte do % físico dos dias 28/07 e '
        '04 a 06/08',
    ]
    base['_meta']['cronograma_atualizado_em'] = DATA_CRONOGRAMA
    base['_meta']['obs_cronograma'] = (
        f'Reconstruído do {MPP} no formato do app (1 raiz, nesting por nível; '
        'eap mapeia tarefas->etapas de custo). Entram as tarefas da revisão '
        'estrutural de 30/07 (brocas de reforço, blocos de coroamento, laje '
        'das vigas transversais, caixaria das calçadas como tarefa própria) e '
        'a inversão de precedência da reunião de 05/08 (valas de drenagem '
        'antes das concretagens). Fim do cronograma: 08/10 -> 19/10. '
        'Apontamentos remapeados por caminho hierárquico; o % dos dias que '
        'estavam vazios foi estimado do texto do RDO, não do MS Project. '
        'Contrato, custos, medições, fluxo e resumo preservados da produção.')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(base, f, ensure_ascii=False, indent=1)

    # ---- 6) regras do parser de WhatsApp, nos ids novos -------------------
    rel_regras = []
    regras = _reescrever_regras(remap, rel_regras)
    caminho_por_id = {v: k for k, v in cam_novo.items()}
    for r in regras['regras']:
        cam = caminho_por_id.get(r['tarefa_mpp'], '')
        nome = cam.split(' > ')[-1] if cam else '?'
        galpao = 'Galpão A' if 'Galpão A' in cam else (
            'Galpão B' if 'Galpão B' in cam else None)
        r['tarefa_nome'] = f'{nome} ({galpao})' if galpao else nome
    regras['descricao'] = [
        linha.replace('  11–52 = Galpão B     55–96 = Galpão A',
                      '  10–58 = Galpão B     59–105 = Galpão A')
        for linha in regras['descricao']]
    with open(REGRAS, 'w', encoding='utf-8') as f:
        json.dump(regras, f, ensure_ascii=False, indent=2)  # o arquivo é indent=2
        f.write('\n')

    # ---- relatório --------------------------------------------------------
    print(f'tarefas={len(tarefas)} (antes {len(cam_antigo)}) | '
          f'ferragens_alvo=id{ferr_alvo} qtot=48')
    print(f'físico-puro (sem etapa): {len(fisico_puro)}')
    print('=== etapa -> nº tarefas ===')
    for e in base['eap']:
        print(f"  {e['codigo']:9} {len(e['cronograma']['tarefas_mpp']):2} tarefas"
              f"  custo={e['custo']['total']}"
              f"  {e['cronograma']['inicio']}~{e['cronograma']['fim']}")
    print(f'=== de/para: {sum(1 for v in remap.values() if v is not None)} '
          f'casadas, {len(sem_par)} sem par ===')
    for oid, cam in sem_par:
        print(f'  - {oid} {cam[-70:]}')
    print(f'=== apontamentos: {inseridos} escritos, {len(perdidos)} perdidos ===')
    for data, tid, cam in perdidos:
        print(f'  ! {data} tarefa {tid}: {cam[-70:]}')
    dias = sum(1 for r in base['rdos'] if r['apontamentos'])
    print(f'RDOs: {len(base["rdos"])} | com físico: {dias} | '
          f'sem físico: {len(base["rdos"]) - dias}')
    print(f'=== fechamento pelo % do Project ({len(fechados)} tarefas) ===')
    for tid, data, antes, pct, antecipado, motivo in fechados:
        marca = ' [ANTECIPADO]' if antecipado else ''
        de = f'{antes}%' if antes is not None else 'sem apontamento'
        print(f'  t{tid:<3} {data}  {de} -> {pct}%{marca}  ({motivo})')
    print('=== RDO > Project (NÃO rebaixados — conciliar no .mpp) ===')
    for tid, nome, rdo_pct, proj_pct in CONFLITO_RDO_MAIOR:
        print(f'  t{tid:<3} {nome}: RDO {rdo_pct}% x Project {proj_pct}%')
    print(f'=== regras do parser ({len(regras["regras"])} no total) ===')
    for linha in rel_regras:
        print(linha)


if __name__ == '__main__':
    main()
