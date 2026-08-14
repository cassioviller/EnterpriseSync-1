#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstrói o canônico da Baia a partir do CRONOGRAMA 12.08.mpp.

Sucessor de `rebuild_baia_from_1008_mpp.py`. Ao contrário daquele, esta
revisão NÃO é estrutural: as 109 tarefas, a hierarquia e os nomes são os
mesmos. O que muda é

  * a **renumeração** de 4 tarefas da Fundação do Galpão B — uma rotação:
    22->21, 23->22, 24->23, 21->24. Os nomes ficaram nos mesmos lugares da
    árvore, só os ids giraram. É a armadilha desta rodada: 16 apontamentos e
    10 regras do parser apontam para esses ids, e casar por id levaria a
    caixaria das calçadas para a escavação das valas;
  * o **replanejamento das datas** — 51 folhas deslocadas de 1 a 4 dias, fim
    da obra 19/10 -> 20/10;
  * o **físico**: as duas tarefas de drenagem (B e A) saem de 50%/0% para
    100% no Project.

E, do lado do diário, entram **5 RDOs novos (07 a 11/08)**, que é o que o
`ESTADO_ATUALIZACAO_BAIA.md` previa quando escreveu "o próximo export do
WhatsApp corrige as datas sozinho": os dois fechamentos ANTECIPADOS para
06/08 (tarefas 69 e drenagem do B) agora têm o dia real em que o serviço
aconteceu.

O que este script faz, na ordem:

  1. `cronograma_tarefas` reconstruído do .mpp;
  2. `eap[*].cronograma.tarefas_mpp` reclassificado pelo mesmo classificador
     por keyword do 1008 — custo e itens de cada etapa vêm intactos da
     produção;
  3. apontamentos e regras do parser remapeados **pelo caminho hierárquico**
     (Galpão X > Fundação > nome), que é o que desfaz a rotação sozinho;
  4. os 5 RDOs novos lidos do export do WhatsApp (texto + fotos);
  5. os fechamentos antecipados de 06/08 removidos e reapontados no dia real;
  6. o físico dos dias novos, do TEXTO do RDO, com o fechamento final pelo %
     do MS Project — a mesma divisão de fontes decidida em 11/08.

Contrato, custos, medições, fluxo de caixa e resumo são preservados da base
de produção (origin/main).

Uso:
    python scripts/rebuild_baia_from_1208_mpp.py
"""
import json
import os
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_mpp import dump  # noqa: E402
from rebuild_baia_from_1008_mpp import etapa_de  # noqa: E402
import whatsapp_para_rdos  # noqa: E402

MPP = 'CRONOGRAMA 12.08.mpp'
ZIP_WHATSAPP = ('Conversa do WhatsApp com 📝 Diário de Obras - '
                'Veks Engenharia (5).zip')
OUT = '/home/runner/workspace/cronograma_fisico_financeiro_baias.json'
REGRAS = 'docs/rdo/regras_apontamento_baia.json'
DATA_CRONOGRAMA = '2026-08-12'
FIM_CRONOGRAMA = '2026-10-20'
PRIMEIRO_RDO_NOVO = date(2026, 8, 7)

# ---------------------------------------------------------------------------
# 1) Os dois fechamentos que o 1008 marcou como ANTECIPADOS, mais o da t70.
#
# Todos os três foram lançados em 06/08 porque era o último RDO que existia —
# "o valor fica certo, a data adianta 1 a 4 dias" (ESTADO_ATUALIZACAO_BAIA.md,
# REVISAR nº 2). Os RDOs de 07 a 11/08 trazem o dia real de cada um, então o
# apontamento sai de 06/08 e volta na data certa, via APONTAMENTOS_NOVOS.
#
# Ids já no espaço do 12.08 (pós-rotação).
REMOVER_DE_06_08 = {
    69: 'escavação/perfuração das brocas do Galpão A — o RDO de 07 e 08/08 '
        'mostra o serviço acontecendo; era antecipação de até 2 dias',
    23: 'valas de drenagem do Galpão B — em 06/08 o RDO ainda registrava a '
        'espera pela liberação do Grupo Mônica; a escavação só saiu em 10/08',
    70: 'armação da nova fundação do Galpão A — o Project fechava em 10/08 e '
        'o RDO daquele dia confirma "finalizada a armação dos reforços"',
}

# ---------------------------------------------------------------------------
# 2) A CURVA DE AGOSTO INTEIRA, relida do texto dos RDOs.
#
# Enquanto o export terminava em 06/08, aquele dia era o último lugar onde dava
# para pendurar um fechamento — e três tarefas do Galpão B foram para 100% ali,
# num dia em que o diário dizia "INICIADA a perfuração" e "armação de reforço
# de 05 vigas transversais". Com os RDOs até 11/08, o avanço volta a ser
# distribuído pelos dias em que aconteceu.
#
# O que muda em relação ao que estava:
#   t21  06/08  100% -> 75%   e ganha o fechamento em 07/08
#   t22  06/08  100% -> 85%   e ganha 07/08 95% + fechamento em 10/08
#   t70               ganha 07/08 60%, entre os 30% de 04/08 e o fim em 10/08
#   t24  fica como está: em 06/08 o texto diz "finalizada [...] concluindo a
#        preparação desta etapa". Quando o diário fecha, o fechamento é dele.
#
# Cada linha traz a frase que a sustenta. Ids do 12.08.
APONTAMENTOS_NOVOS = {
    # --- recalibração dos dias que já existiam ---------------------------
    '2026-08-06': [
        (21, 75, 'RELIDO: "concluída a escavação das valas [...] sendo '
                 'INICIADA a perfuração das novas brocas" — a escavação '
                 'fecha, a perfuração começa. Estava 100% porque 06/08 era o '
                 'último RDO que existia'),
        (22, 85, 'RELIDO: "executada a armação de reforço de 05 vigas '
                 'transversais, dando CONTINUIDADE às adequações" — '
                 'continuidade não é fim. Estava 100% pelo mesmo motivo'),
        # t24 permanece 100%: "finalizada a execução da caixaria da segunda
        # calçada do Galpão B, concluindo a preparação desta etapa".
    ],
    # --- os 5 dias novos --------------------------------------------------
    '2026-08-07': [
        (69, 75, 'concluída a escavação das valas das novas lajes de reforço '
                 'do Galpão A e dada continuidade à perfuração das novas '
                 'brocas — mesmo patamar da regra perfuracao-brocas-reforco'),
        (21, 100, '"dada continuidade à perfuração das novas brocas": em '
                  '08/08 só restavam as do Galpão A, então as do B fecham '
                  'aqui. O Project também fecha a tarefa em 06-07/08'),
        (22, 95, '"foi dada continuidade à execução da armação dos reforços '
                 'das vigas transversais" — o bullet não diz o galpão, então '
                 'vale para os dois (ver t70 no mesmo dia)'),
        (70, 60, 'mesmo bullet de continuidade da armação dos reforços, do '
                 'lado do Galpão A — entre os 30% de 04/08 e o fim em 10/08'),
    ],
    '2026-08-08': [
        (69, 100, 'concluída a perfuração das brocas restantes do Galpão A '
                  '— fecha a tarefa, e o Project concorda'),
    ],
    # 2026-08-09: só rebaixamento interno das baias, que não tem tarefa no
    # cronograma. Ver SEM_TAREFA_NOVOS.
    '2026-08-10': [
        (70, 100, 'finalizada a armação dos reforços das vigas transversais '
                  'do Galpão A, conforme revisão do projeto estrutural'),
        (23, 50, 'executada a escavação das valas de drenagem das baias do '
                 'Galpão B, profundidade ~1,00 m — metade da tarefa, que '
                 'também cobre o preenchimento da 1ª camada drenante'),
    ],
    '2026-08-11': [
        (72, 50, 'finalizada a escavação das valas de drenagem das baias do '
                 'Galpão A, "concluindo a etapa de escavação dos drenos"'),
    ],
}

# ---------------------------------------------------------------------------
# 3) Fechamento pelo % do MS Project — a regra decidida em 11/08: a curva
#    intermediária é do texto do RDO, o valor final é o do Project.
#
#    As duas tarefas de drenagem são o caso desta rodada, e são a REVISAR nº 1
#    do relatório: o Project as dá por 100%, mas o nome delas é "Escavação das
#    Valas de Drenagem **e Preenchimento 1ª Camada de Material Drenante**", e
#    o RDO de 11/08 diz, com todas as letras, que o rachão da 1ª camada ainda
#    não tinha chegado na obra. O 100% entra porque o Project é a autoridade
#    de fechamento, mas quem precisa conciliar é a coluna %concluído do .mpp.
#
#    (tarefa, data, pct, antecipado, motivo)
FECHAMENTO_PROJECT = [
    (22, '2026-08-10', 100, False,
     'armação da nova fundação (B) — a curva do texto sobe até 95% em 07/08 e '
     'depois o diário só fala do Galpão A; o Project fecha a tarefa em 10/08, '
     'que é o fim da janela dela. Fechamento do Project, não do texto'),
    (23, '2026-08-11', 100, False,
     'valas de drenagem (B) — janela 08–11/08 no Project, fecha dentro da '
     'janela; ⚠️ a 1ª camada drenante NÃO começou (ver REVISAR nº 1)'),
    (72, '2026-08-11', 100, False,
     'valas de drenagem (A) — a janela do Project é 12–14/08, mas o RDO de '
     '11/08 já dá a escavação por finalizada: o .mpp é que está atrasado '
     'nesta linha; ⚠️ 1ª camada drenante idem'),
]

# ---------------------------------------------------------------------------
# 4) Serviços que os RDOs novos relatam e o cronograma não comporta.
SEM_TAREFA_NOVOS = [
    'ATUALIZAÇÃO 12/08: o REBAIXAMENTO de ~20 cm do nível interno de todas as '
    'baias (Galpões A e B), definido em 07/08 com a Eng. Ana Luísa (Fort '
    'Gerenciadora) e executado em 08 e 09/08, NÃO TEM TAREFA no cronograma de '
    '12.08 — é escopo novo, surgido depois da revisão. Dois dias de RDO '
    '(08 e 09/08) ficam sem físico por causa disso. Pedir ao engenheiro que '
    'inclua a tarefa na próxima revisão.',
    'ATUALIZAÇÃO 12/08: os serviços de preparação do RDO de 11/08 — carpintaria '
    'das laterais internas do Bloco B, locação das brocas para concretagem, '
    'recorte e preparo das vigas transversais, limpeza das valas longitudinais '
    'e retirada das lonas de proteção das calçadas — são preparação para as '
    'tarefas 25/71 (concreto magro e concretagem das brocas, 13/08) e 27 '
    '(caixaria e armação das vigas transversais, 11–18/08), todas em 0% no '
    'Project. Nenhum % foi inventado para elas.',
    'ATUALIZAÇÃO 12/08: a PAINELIZAÇÃO DE LSF em São José dos Campos/SP, que o '
    'RDO de 11/08 dá por INICIADA, tem tarefa (42, Galpão B, janela 11–17/08) '
    'mas está em 0% no .mpp de 12.08. Divergência RDO x Project no sentido '
    '"o diário sabe mais": nenhum % foi lançado, porque não há número no texto '
    '— confirmar o avanço com o engenheiro.',
]

# Nenhuma regra nova nesta rodada. O rebaixamento das baias seria candidato
# natural, mas uma regra só existe para apontar em ALGUMA tarefa, e essa não
# existe no cronograma de 12.08 — regra com `tarefa_mpp` nulo quebraria o
# relatório do próprio parser. Fica registrado em SEM_TAREFA_NOVOS até o
# engenheiro criar a tarefa.
REGRAS_NOVAS = []


def _caminhos(lst, chave_nivel, base_nivel):
    """id -> 'Raiz > Galpão X > Fundação > nome'."""
    pilha = {}
    out = {}
    for t in lst:
        n = t[chave_nivel] - base_nivel
        for k in [x for x in pilha if x >= n]:
            del pilha[k]
        pilha[n] = t['nome'].strip()
        out[t['id']] = ' > '.join(pilha[k] for k in sorted(pilha))
    return out


def _reescrever_regras(remap, caminho_por_id, relatorio):
    """Reaponta `tarefa_mpp` das regras para os ids do 12.08.

    Sem isto a rotação envenenaria a próxima rodada de WhatsApp em silêncio:
    a regra `caixaria-calcada-b` aponta para 21, que no 12.08 deixou de ser a
    caixaria das calçadas e virou a escavação das novas valas.
    """
    regras = json.load(open(REGRAS, encoding='utf-8'))
    for r in regras['regras']:
        antigo = r['tarefa_mpp']
        if antigo is None:
            continue
        destino = remap.get(antigo)
        if destino is None:
            relatorio.append(f'  - regra {r["id"]} sem tarefa no 12.08 '
                             f'(era {antigo}) — mantida como estava')
            continue
        if destino != antigo:
            relatorio.append(f'  ~ regra {r["id"]}: {antigo} -> {destino}')
        r['tarefa_mpp'] = destino

    existentes = {r['id'] for r in regras['regras']}
    for nova in REGRAS_NOVAS:
        if nova['id'] in existentes:
            continue
        regras['regras'].append(dict(nova))
        relatorio.append(f'  + regra {nova["id"]} -> t{nova["tarefa_mpp"]}')

    # nome legível da tarefa, para o arquivo continuar revisável a olho
    for r in regras['regras']:
        cam = caminho_por_id.get(r['tarefa_mpp'], '')
        nome = cam.split(' > ')[-1] if cam else '?'
        galpao = 'Galpão A' if 'Galpão A' in cam else (
            'Galpão B' if 'Galpão B' in cam else None)
        r['tarefa_nome'] = f'{nome} ({galpao})' if galpao else nome

    for obs in SEM_TAREFA_NOVOS:
        if obs not in regras['sem_tarefa_no_cronograma']:
            regras['sem_tarefa_no_cronograma'].append(obs)
    return regras


def main():
    mpp = dump(MPP)
    base = json.loads(subprocess.check_output(
        ['git', 'show', 'origin/main:cronograma_fisico_financeiro_baias.json']))

    # ---- 1) cronograma_tarefas -------------------------------------------
    antes_qtd = {t['id']: (t.get('quantidade_total'), t.get('unidade'))
                 for t in base['cronograma_tarefas']
                 if t.get('quantidade_total')}
    cam_antigo = _caminhos(base['cronograma_tarefas'], 'nivel', 1)
    cam_novo_por_caminho = {v: k for k, v in _caminhos(mpp, 'outline', 0).items()}
    caminho_por_id = {v: k for k, v in cam_novo_por_caminho.items()}

    tarefas = []
    for t in mpp:
        tarefas.append({
            'id': t['id'], 'nivel': int(t.get('outline', 0)) + 1,
            'nome': t['nome'], 'inicio': t.get('inicio'), 'fim': t.get('fim'),
            'dias': t.get('dias') or 1, 'pct_fisico': 0,
            'predecessoras': t.get('predecessoras', []),
            'resumo': bool(t.get('resumo')),
        })

    # ---- 2) de/para pelo caminho — é o que desfaz a rotação ---------------
    remap = {}
    sem_par = []
    for old_id, cam in cam_antigo.items():
        novo = cam_novo_por_caminho.get(cam)
        remap[old_id] = novo
        if novo is None:
            sem_par.append((old_id, cam))
    girados = sorted((o, n) for o, n in remap.items() if n is not None and o != n)

    # quantidade_total/unidade seguem a tarefa, não o id
    for row in tarefas:
        for old_id, (qtd, un) in antes_qtd.items():
            if remap.get(old_id) == row['id']:
                row['quantidade_total'] = qtd
                row['unidade'] = un

    # ---- 3) eap: custo da produção + tarefas do .mpp novo -----------------
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
            ini, fim = raiz['inicio'], raiz['fim']
        else:
            ini, fim = e['cronograma'].get('inicio'), e['cronograma'].get('fim')
        e['cronograma'] = {'inicio': ini, 'fim': fim, 'pct_fisico': 0,
                           'tarefas_mpp': ids,
                           'transversal': e['cronograma'].get('transversal', False)}

    # ---- 4) apontamentos existentes, nos ids novos ------------------------
    perdidos = []
    for r in base.get('rdos', []):
        novos = []
        for a in r.get('apontamentos', []):
            destino = remap.get(a['tarefa_mpp'])
            if destino is None:
                perdidos.append((r['data'], a['tarefa_mpp'],
                                 cam_antigo.get(a['tarefa_mpp'], '?')))
                continue
            a['tarefa_mpp'] = destino
            novos.append(a)
        r['apontamentos'] = novos

    # ---- 5) regras do parser nos ids novos, ANTES de ler o WhatsApp -------
    # A ordem importa: as regras precisam já estar no espaço do 12.08 para o
    # relatório de pendências do parser citar a tarefa certa.
    rel_regras = []
    regras = _reescrever_regras(remap, caminho_por_id, rel_regras)

    # ---- 6) os 5 RDOs novos, do export do WhatsApp ------------------------
    payload, rel_wa = whatsapp_para_rdos.converter(
        caminho_zip=ZIP_WHATSAPP, marcador_obra='Obra Itu',
        desde=PRIMEIRO_RDO_NOVO, regras=regras)
    novos_rdos = payload['rdos'] if isinstance(payload, dict) else payload
    ja_tem = {r['data'] for r in base['rdos']}
    acrescentados = []
    for r in novos_rdos:
        if r['data'] in ja_tem:
            continue
        # `_sugestoes` é material de revisão do parser, não do canônico: o
        # físico desta rodada vem de APONTAMENTOS_NOVOS, escrito à mão.
        r.pop('_sugestoes', None)
        r.setdefault('apontamentos', [])
        base['rdos'].append(r)
        acrescentados.append(r['data'])
    base['rdos'].sort(key=lambda r: r['data'])
    por_data = {r['data']: r for r in base['rdos']}

    # ---- 7) desfaz os fechamentos antecipados de 06/08 --------------------
    rdo_0608 = por_data['2026-08-06']
    removidos = []
    for tid in list(REMOVER_DE_06_08):
        for a in list(rdo_0608['apontamentos']):
            if a['tarefa_mpp'] == tid:
                rdo_0608['apontamentos'].remove(a)
                removidos.append((tid, a.get('pct'), REMOVER_DE_06_08[tid]))

    # ---- 8) físico dos dias novos, do texto do RDO ------------------------
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

    # ---- 9) fechamento pelo % do Project ----------------------------------
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

    # ---- 10) cronograma + contrato + _meta --------------------------------
    base['cronograma_tarefas'] = tarefas
    base['contrato']['data_fim_cronograma'] = FIM_CRONOGRAMA
    base['_meta']['fontes'] = [
        f'{MPP} (MS Project — replanejamento de 12/08: mesmas 109 tarefas, '
        '4 ids girados na Fundação do Galpão B, 51 folhas com datas '
        'deslocadas, drenagem A/B em 100%)',
        'Planilha de Custos REV01 (custos por etapa — preservados da produção)',
        'Textos dos RDOs (WhatsApp, export de 12/08) — RDOs de 07 a 11/08 e '
        'fonte do % físico desses dias',
    ]
    base['_meta']['cronograma_atualizado_em'] = DATA_CRONOGRAMA
    base['_meta']['obs_cronograma'] = (
        f'Reconstruído do {MPP} no formato do app (1 raiz, nesting por nível; '
        'eap mapeia tarefas->etapas de custo). Revisão NÃO estrutural: as 109 '
        'tarefas e a hierarquia são as mesmas do 10.08; mudaram as datas (51 '
        'folhas, fim 19/10 -> 20/10), o físico das duas tarefas de drenagem e '
        'os ids de 4 tarefas da Fundação do Galpão B, que giraram '
        '(22->21, 23->22, 24->23, 21->24). Apontamentos e regras do parser '
        'remapeados por caminho hierárquico. Entram os RDOs de 07 a 11/08, '
        'que dão o dia real dos fechamentos que o 10.08 tinha antecipado para '
        '06/08. Contrato, custos, medições, fluxo e resumo preservados da '
        'produção.')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(base, f, ensure_ascii=False, indent=1)

    # ---- 11) grava as regras já remapeadas no passo 5 ---------------------
    with open(REGRAS, 'w', encoding='utf-8') as f:
        json.dump(regras, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # ---- relatório --------------------------------------------------------
    print(f'tarefas={len(tarefas)} (antes {len(cam_antigo)}) | '
          f'fim do cronograma: {FIM_CRONOGRAMA}')
    print(f'físico-puro (sem etapa): {len(fisico_puro)}')
    print(f'=== ids que giraram ({len(girados)}) ===')
    for o, n in girados:
        print(f'  {o:3} -> {n:3}  {caminho_por_id[n].split(" > ")[-1][:66]}')
    if sem_par:
        print(f'=== {len(sem_par)} tarefa(s) sem par no 12.08 ===')
        for oid, cam in sem_par:
            print(f'  - {oid} {cam[-70:]}')
    print('=== etapa -> nº tarefas ===')
    for e in base['eap']:
        print(f"  {e['codigo']:9} {len(e['cronograma']['tarefas_mpp']):2} tarefas"
              f"  custo={e['custo']['total']}"
              f"  {e['cronograma']['inicio']}~{e['cronograma']['fim']}")
    print(f'=== RDOs novos ({len(acrescentados)}) ===')
    for d in acrescentados:
        r = por_data[d]
        print(f'  + {d}  fotos={len(r.get("fotos", []))}  '
              f'apontamentos={len(r["apontamentos"])}')
    print(f'=== fechamentos antecipados desfeitos em 06/08 ({len(removidos)}) ===')
    for tid, pct, motivo in removidos:
        print(f'  - t{tid:<3} tinha {pct}% em 06/08 — {motivo}')
    print(f'=== físico dos dias novos ({inseridos} apontamentos do texto) ===')
    for data, itens in APONTAMENTOS_NOVOS.items():
        for tid, pct, origem in itens:
            print(f'  {data}  t{tid:<3} {pct:>3}%  {origem}')
    print(f'=== fechamento pelo % do Project ({len(fechados)}) ===')
    for tid, data, antes, pct, antecipado, motivo in fechados:
        marca = ' [ANTECIPADO]' if antecipado else ''
        de = f'{antes}%' if antes is not None else 'sem apontamento'
        print(f'  t{tid:<3} {data}  {de} -> {pct}%{marca}  ({motivo})')
    if perdidos:
        print(f'=== apontamentos perdidos ({len(perdidos)}) ===')
        for data, tid, cam in perdidos:
            print(f'  ! {data} tarefa {tid}: {cam[-70:]}')
    dias = sum(1 for r in base['rdos'] if r['apontamentos'])
    print(f'RDOs: {len(base["rdos"])} | com físico: {dias} | '
          f'sem físico: {len(base["rdos"]) - dias}')
    print(f'=== regras do parser ({len(regras["regras"])} no total) ===')
    for linha in rel_regras:
        print(linha)
    pend = rel_wa.get('pendencias', [])
    if pend:
        print(f'=== bullets sem regra nos dias novos ({len(pend)}) ===')
        for linha in pend:
            print(f'  - {linha[:140]}')
    avisos = rel_wa.get('avisos', [])
    if avisos:
        print(f'=== avisos do parser ({len(avisos)}) ===')
        for linha in avisos:
            print(f'  - {linha[:140]}')


if __name__ == '__main__':
    main()
