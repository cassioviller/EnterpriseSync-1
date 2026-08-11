"""Gera UM RDO que alinha o físico da obra ao %concluído de um `.mpp`.

O problema que resolve (achado na Angela em 11/08): ao aplicar um `.mpp` pela
aba Cronograma, `services/cronograma_versao_service.py` só carrega o
`pct_project` **se a obra nunca teve RDO** —

    tem_rdo = db.session.query(RDO.id).filter_by(obra_id=obra.id).first()
    if not tem_rdo:
        t.percentual_concluido = float(pct)   # entra e sobrevive
    ...
    if tem_rdo:
        _motor_pos_commit(...)                # recalcula e SINCRONIZA

— e a sincronização zera toda tarefa sem apontamento. Numa obra que já tem
RDO, então, os percentuais do Project são descartados E o resto é zerado: foi
o que aconteceu depois da carga da Angela, que criou 26 RDOs.

A saída aqui entra pelo canal sancionado: um RDO com um apontamento por
tarefa. Percentual que vem de apontamento sobrevive à sincronização, aparece
no histórico e dá para rastrear de que arquivo veio. É o mesmo desenho de
`_rdos_sinteticos_do_pct_fisico` (services/importacao_fisico_financeiro.py),
que o import canônico já usa quando o arquivo não traz seção `rdos` — este
script leva a ideia para o fluxo do `.mpp`.

Uso:
    python scripts/rdo_alinhamento_cronograma.py \\
        "Veks - Angela - Cronograma Atual  11-08-2026.mpp" \\
        --data 2026-08-11 --saida cargas/obra-43/rdo_alinhamento.json

    # revisar contra o banco (resolve as tarefas, não grava)
    SIGE_ENABLE_DEMO_SEED=false python scripts/atualizar_rdos_obra.py \\
        veks 43 cargas/obra-43/rdo_alinhamento.json --sem-fotos --dry-run

`--data` default: a `data_status` do `.mpp` (o dia a que o Project diz que os
percentuais se referem). Muitos arquivos não a preenchem — aí é obrigatório
passar à mão, porque adivinhar a data de um apontamento é adivinhar quando o
serviço foi feito.

RETROCESSO: `atualizar_rdos` recusa apontamento que faça uma tarefa andar para
trás e o reporta como pendência. Isso é proposital e este script não tenta
contornar — se o Project diz 48% onde o RDO já registrou 80%, a diferença é
uma decisão de engenharia, não de script.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mpp_parser import parse_cronograma  # noqa: E402

COMENTARIO_PADRAO = (
    'RDO de alinhamento do físico ao cronograma.\n\n'
    'Não descreve um dia de obra: existe para trazer o %concluído do arquivo '
    '{arquivo} para dentro dos apontamentos, que é onde o sistema guarda o '
    'avanço físico. Sem isto, a sincronização zera toda tarefa sem '
    'apontamento e o percentual do Project se perde.\n\n'
    '{n} tarefa(s) alinhada(s). Efetivo não se aplica.'
)


def montar(caminho_mpp, data=None, comentario=None):
    """→ (item_de_payload, relatorio). Um RDO, um apontamento por folha."""
    contrato = parse_cronograma(caminho_mpp)
    data = data or contrato['projeto'].get('data_status')
    if not data:
        raise SystemExit(
            f'{os.path.basename(caminho_mpp)} não tem data_status — passe '
            f'--data AAAA-MM-DD. A data do apontamento é a data em que o '
            f'serviço foi executado; não dá para inventar.')

    folhas = [t for t in contrato['tarefas'] if not t.get('resumo')]
    apontamentos = []
    for t in folhas:
        pct = float(t.get('pct_project') or 0)
        if pct <= 0:
            continue
        apontamentos.append({'tarefa_mpp': int(t['uid']),
                             'pct': round(pct, 2)})

    item = {
        'data': data,
        'clima': 'Não informado',
        'precipitacao': 'Não informado',
        'comentario': (comentario or COMENTARIO_PADRAO).format(
            arquivo=os.path.basename(caminho_mpp), n=len(apontamentos)),
        'mao_de_obra': 0,
        'apontamentos': apontamentos,
    }
    rel = {
        'arquivo': os.path.basename(caminho_mpp),
        'data': data,
        'tarefas': len(contrato['tarefas']),
        'folhas': len(folhas),
        'alinhadas': len(apontamentos),
        'folhas_em_zero': sum(1 for t in folhas
                              if not float(t.get('pct_project') or 0)),
        'parciais': [(int(t['uid']), t['nome'], float(t['pct_project']))
                     for t in folhas
                     if 0 < float(t.get('pct_project') or 0) < 100],
    }
    return item, rel


def envelopar(item, carga_ref):
    """Embrulha o RDO no formato `carga-obra/1.1`, para subir pela TELA
    (página da obra → aba RDOs → "Atualizar por JSON").

    Sem `cronograma_tarefas` de propósito: `aplicar_carga_obra` só roda a fase
    de cronograma `if tarefas_json`, então o arquivo entra como carga SÓ de
    RDO — não insere, não arquiva, não versiona nada. Só o apontamento.

    `carga_ref` é a carga da obra (cargas/obra-N/carga_obra_N.json), de onde
    saem o bloco `obra` (a tela recusa o arquivo se ele não disser de que obra
    é — subir na obra errada é o erro mais provável do fluxo) e o `mapa_nomes`
    (fallback de resolução por nome, para as tarefas sem `mpp_uid`).
    """
    with open(carga_ref, encoding='utf-8') as f:
        carga = json.load(f)
    return {
        '_meta': {
            'formato': 'carga-obra/1.1',
            'gerado_em': item['data'],
            'fontes': {'cronograma': carga.get('_meta', {})
                       .get('fontes', {}).get('cronograma')},
            'observacao': 'Carga SÓ de RDO: sem "cronograma_tarefas", a fase '
                          'de cronograma não roda.',
        },
        'obra': carga['obra'],
        'mapa_nomes': carga.get('mapa_nomes') or {},
        'rdos': [item],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('mpp', help='cronograma .mpp/.xml com os % vigentes')
    p.add_argument('--data', help='data do RDO (AAAA-MM-DD); default: a '
                                  'data_status do arquivo')
    p.add_argument('--saida', help='payload de saída; default: stdout')
    p.add_argument('--para-tela', metavar='CARGA.json',
                   help='embrulha em carga-obra/1.1 para subir pela aba RDOs '
                        'da obra, usando o bloco "obra" e o "mapa_nomes" '
                        'desta carga. Sem isto a saída é a LISTA que o '
                        'scripts/atualizar_rdos_obra.py consome — e que a '
                        'tela recusa')
    args = p.parse_args(argv)

    item, rel = montar(args.mpp, args.data)
    payload = envelopar(item, args.para_tela) if args.para_tela else [item]

    if args.saida:
        os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
        with open(args.saida, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=1)
        print()

    print(f"[rdo_alinhamento] {rel['arquivo']} → RDO de {rel['data']}",
          file=sys.stderr)
    print(f"  {rel['tarefas']} tarefas ({rel['folhas']} folhas) — "
          f"{rel['alinhadas']} com apontamento, "
          f"{rel['folhas_em_zero']} folhas em 0% (não entram)",
          file=sys.stderr)
    if rel['parciais']:
        print(f"  {len(rel['parciais'])} parcial(is) — confira se o valor do "
              f"Project é o que a obra executou:", file=sys.stderr)
        for uid, nome, pct in rel['parciais']:
            print(f"    {pct:>5.0f}%  uid={uid:<5} {nome[:52]}",
                  file=sys.stderr)
    if args.saida:
        print(f"  payload: {args.saida}", file=sys.stderr)
        if args.para_tela:
            print(f"  formato: carga-obra/1.1 (SÓ RDO — sem "
                  f"cronograma_tarefas, a fase de cronograma não roda)",
                  file=sys.stderr)
            print(f"  aplicar: página da obra → aba RDOs → 'Atualizar por "
                  f"JSON' → Prévia → Aplicar", file=sys.stderr)
        else:
            print(f"  formato: LISTA de RDOs (para o CLI; a TELA recusa — "
                  f"use --para-tela para o outro formato)", file=sys.stderr)
            print(f"  revisar: SIGE_ENABLE_DEMO_SEED=false python "
                  f"scripts/atualizar_rdos_obra.py <admin> <obra> "
                  f"{args.saida} --sem-fotos --dry-run", file=sys.stderr)


if __name__ == '__main__':
    main()
