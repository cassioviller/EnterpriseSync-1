#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstrói o canônico da Baia a partir do CRONOGRAMA 06.07.mpp no FORMATO do app
(1 raiz -> nesting por nivel; eap mapeando tarefas->etapas de custo), preservando
contrato/custos/rdos/medições/fluxo/resumo da base de produção (main)."""
import json, subprocess, re, unicodedata
from datetime import date
import sys; sys.path.insert(0, 'scripts')
from dump_mpp import dump

OUT = "/home/runner/workspace/cronograma_fisico_financeiro_baias.json"
main = json.loads(subprocess.check_output(['git','show','origin/main:cronograma_fisico_financeiro_baias.json']))
mpp = dump('CRONOGRAMA 06.07.mpp')

def na(s):
    return unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()

# ---- classificador etapa por keyword (ordem importa) ----
def etapa_de(nome):
    n = na(nome)
    if n.startswith('fazenda') or n.startswith('ajr') or 'limpeza geral' in n \
       or 'desmobiliza' in n or 'preenchimento' in n:
        return None  # físico-puro: entra no cronograma, sem custo/etapa
    if 'hidraulica' in n or 'hidraulico' in n:            return 'HIDRO'
    if 'eletrica' in n or 'iluminacao' in n:               return 'ELET'
    if 'estudo de solo' in n or 'projetos' in n or 'mobilizacao equipe' in n or 'gabarito' in n:
        return 'PRELIM'
    if 'moledo' in n:                                      return 'MOLEDO'
    if 'portao' in n or 'portoes' in n:                    return 'PORTAO'
    if 'pintura' in n:                                     return 'PINT'
    if 'plaqueamento' in n or 'basecoat' in n:             return 'FECHA'
    if 'lsf' in n:                                         return 'ESTLSF'
    if 'telhado shingle' in n or 'telhado single' in n:    return 'COBERT'
    if 'estrutura metalica' in n or 'aco para telhado' in n: return 'ESTMET'
    if any(k in n for k in ('baldrame','broca','ferragen','concretagem','concreto magro',
        'chapas base','calcada','sapata','alvenaria','icamento','conduite',
        'marcacao dos pilares')):
        return 'FUND'
    return '??'

# ---- 1) cronograma_tarefas (nivel=outline+1 -> raiz única) ----
FERRAGENS_KEY = 'ferragens para fundacao'
ferragens_ids = []
tarefas = []
for t in mpp:
    o = int(t.get('outline', 0))
    row = {
        'id': t['id'], 'nivel': o + 1,
        'nome': t['nome'],
        'inicio': t.get('inicio'), 'fim': t.get('fim'),
        'dias': t.get('dias') or 1,
        'pct_fisico': 0,
        'predecessoras': t.get('predecessoras', []),
        'resumo': bool(t.get('resumo')),
    }
    if not t.get('resumo') and FERRAGENS_KEY in na(t['nome']):
        ferragens_ids.append(t['id'])
    tarefas.append(row)
# quantidade_total=48 na 1ª ferragens (recebe o apontamento dos rdos da main)
FERR_ALVO = min(ferragens_ids) if ferragens_ids else None
for row in tarefas:
    if row['id'] == FERR_ALVO:
        row['quantidade_total'] = 48; row['unidade'] = 'un'

# ---- 2) classificar folhas -> etapa ----
por_etapa = {}
fisico_puro = []; naoclass = []
tid_nome = {t['id']: t['nome'] for t in mpp}
for t in mpp:
    if t.get('resumo'): continue
    et = etapa_de(t['nome'])
    if et is None: fisico_puro.append(t['id'])
    elif et == '??': naoclass.append((t['id'], t['nome']))
    else: por_etapa.setdefault(et, []).append(t['id'])

# ---- 3) eap: custo/itens da MAIN + tarefas_mpp classificadas ----
def datas_de(ids):
    ds = [tid_nome and mpp_by[i].get('inicio') for i in ids if mpp_by[i].get('inicio')]
    fs = [mpp_by[i].get('fim') for i in ids if mpp_by[i].get('fim')]
    return (min(ds) if ds else None, max(fs) if fs else None)
mpp_by = {t['id']: t for t in mpp}
for e in main['eap']:
    cod = e['codigo']
    ids = sorted(por_etapa.get(cod, []))
    ini, fim = datas_de(ids) if ids else (e['cronograma'].get('inicio'), e['cronograma'].get('fim'))
    e['cronograma'] = {'inicio': ini, 'fim': fim, 'pct_fisico': 0,
                       'tarefas_mpp': ids,
                       'transversal': e['cronograma'].get('transversal', False)}
    # custo/itens permanecem os da main

# ---- 4) rdos: main + apontamentos remapeados p/ ids 06.07 ----
REMAP = {3: 2, 4: 3, 6: 5, 9: 7, 15: FERR_ALVO}
for r in main.get('rdos', []):
    for a in r.get('apontamentos', []):
        a['tarefa_mpp'] = REMAP.get(a['tarefa_mpp'], a['tarefa_mpp'])

# ---- 5) cronograma_tarefas + _meta ----
main['cronograma_tarefas'] = tarefas
main['_meta']['fontes'] = [
    "CRONOGRAMA 06.07.mpp (MS Project — cronograma físico, 101 tarefas c/ split Galpão A/B)",
    "Planilha de Custos REV01 (custos por etapa — preservados da base de produção)"]
main['_meta']['cronograma_atualizado_em'] = "2026-07-08"
main['_meta']['obs_cronograma'] = ("Reconstruído do CRONOGRAMA 06.07.mpp no formato do app "
    "(1 raiz, nesting por nível; eap mapeia tarefas->etapas de custo). Contrato, custos, RDOs, "
    "medições, fluxo e resumo preservados da produção.")

json.dump(main, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---- relatório ----
print(f"tarefas={len(tarefas)} | ferragens_alvo=id{FERR_ALVO} qtot=48")
print(f"físico-puro (sem etapa): {len(fisico_puro)} tarefas")
print(f"NÃO CLASSIFICADAS: {naoclass or 'nenhuma ✓'}")
print("=== etapa -> nº tarefas ===")
for e in main['eap']:
    print(f"  {e['codigo']:9} {len(e['cronograma']['tarefas_mpp']):2} tarefas  custo={e['custo']['total']}")
print("=== físico-puro ===")
for i in fisico_puro: print('  -', tid_nome[i][:50])
