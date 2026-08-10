"""Prepara a carga local de RDOs de uma obra: export do sistema + WhatsApp.

A metade SEM banco das fases 2+4 do plano
docs/superpowers/plans/2026-08-10-carga-nao-destrutiva-cronograma-rdos.md.
Consome dois zips que o Cássio coloca na raiz do repo:

  1. o zip do botão "Exportar RDOs (.zip)" da página da obra
     (obra.json + rdos.json + mapa_nomes.json — o retrato de produção);
  2. o export da conversa do WhatsApp (o mesmo de whatsapp_para_rdos).

E produz o material de aplicação:

  <saida-dir>/payload_rdos.json   payload-DELTA para scripts/atualizar_rdos_obra.py
                                  (só os dias que mudam: novos ou enriquecidos);
  <saida-dir>/relatorio.txt       o que entrou, o que foi pulado e por quê;
  <fotos-base>/<data>/N.<ext>     fotos extraídas do WhatsApp, numa base POR
                                  OBRA (fotos_rdos/obras/<codigo|id>/) — a base
                                  legada fotos_rdos/<data>/ é da Baia e não é
                                  tocada.

Regras da mescla (por dia, por campo — nada é decidido em silêncio):

  * dia só no WhatsApp                → item NOVO no payload;
  * dia nos dois, campo vazio no
    sistema e preenchido no WhatsApp  → item DELTA só com o que muda
                                        (o upsert não toca no resto);
  * dia nos dois, campo preenchido
    NOS DOIS e diferente              → `_conflito` no item + PENDÊNCIA no
                                        relatório; o campo NÃO entra no delta
                                        até você resolver no JSON;
  * "Não informado" (clima/precipitação que o WhatsApp não reporta) conta
    como vazio: nunca sobrescreve valor real nem gera conflito;
  * RDO do sistema em estado imutável (`_estado` assinado/aprovado/
    retificado) → dia PULADO com pendência (o updater o recusaria);
  * apontamento cuja chave não existe no mapa_nomes.json → pendência;
  * dia com foto já no banco (`_fotos_no_banco` > 0) → aviso: o updater
    preserva as fotos existentes e ignora as novas.

Uso:
    python scripts/preparar_carga_obra.py \
        --export rdos_43_2026-08-10.zip \
        --whatsapp "Conversa do WhatsApp com ... (2).zip" \
        --obra-marcador "Obra a Angela" \
        [--saida-dir cargas/obra-43] [--fotos-base fotos_rdos/obras/43] \
        [--regras regras.json --aplicar-sugestoes] [--dry-run]

Sem banco e sem Flask: roda em qualquer lugar. A aplicação em produção
continua sendo scripts/atualizar_rdos_obra.py (upsert não-destrutivo):

    python scripts/atualizar_rdos_obra.py <admin> <obra> payload_rdos.json \
        --fotos-base <fotos-base> --dry-run
"""
import argparse
import io
import json
import os
import sys
import zipfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, 'scripts'))

# Estados que o updater recusa (services/rdo_ciclo_vida.ESTADOS_IMUTAVEIS).
# Copiados como literal para o script continuar sem imports do app.
ESTADOS_IMUTAVEIS = {'assinado', 'aprovado', 'retificado'}

# Valor que whatsapp_para_rdos emite quando o chat não reporta clima.
_VAZIO = (None, '', 'Não informado')

CAMPOS_TEXTO = ('clima', 'precipitacao', 'comentario')

# Todos os marcadores vistos no grupo real (scan de 2026-08-10 do export
# iOS completo). Os MAIS ESPECÍFICOS vêm primeiro: o casamento é por
# substring no cabeçalho do bloco.
MARCADORES_CONHECIDOS = (
    'Obra GESPI Sala de Controle', 'Obra GESPI Refeitório',
    'Obra Casa Ana e Pablo', 'Obra casa Angela', 'Obra a Angela',
    'Obra Angela', 'Obra Vila velha', 'Obra Anderson', 'Obra Vereda',
    'Obra Dona Gilda', 'Obra Gabriel', 'Obra Clinica DGM', 'Obra Larissa',
    'Obra Itu',
)


def _vazio(valor):
    return valor in _VAZIO or (isinstance(valor, str) and not valor.strip())


def ler_export(caminho_zip):
    """(obra_json, rdos_por_data, mapa_nomes) a partir do zip do sistema."""
    with zipfile.ZipFile(caminho_zip) as zf:
        obra = json.loads(zf.read('obra.json'))
        rdos = json.loads(zf.read('rdos.json'))['rdos']
        mapa = json.loads(zf.read('mapa_nomes.json'))
    formato = str(obra.get('_meta', {}).get('formato', ''))
    if formato.split('.')[0] != '1':
        raise SystemExit(f'formato de export desconhecido: {formato!r} — '
                         f'este script entende major 1')
    return obra, {r['data']: r for r in rdos}, mapa


def mesclar(rdos_sistema, rdos_whatsapp, mapa_nomes, datas_duplicadas=(),
            politica_conflito='pendencia'):
    """Payload-delta + relatório. Pura: dicionários entram, dicionários saem.

    `rdos_sistema`: {data: item} do rdos.json do export (com chaves `_`).
    `rdos_whatsapp`: lista de itens do whatsapp_para_rdos.
    `datas_duplicadas`: dias com MAIS DE UM RDO no sistema (avisos do
    export). Campo de texto nesses dias vira pendência em vez de delta:
    um export antigo pode ter retratado um RDO e o updater escrever no
    outro — decidir "estava vazio" olhando o RDO errado sobrescreveria
    texto real. Fotos e apontamentos passam (o updater tem guarda própria
    de foto, e apontamento é por tarefa, não por texto).

    `politica_conflito` — campo preenchido nos DOIS lados e diferente:
      * 'pendencia' (default): `_conflito` no item + pendência; ninguém
        decide por você;
      * 'sistema': o que já está no sistema VENCE (decisão do Cássio,
        2026-08-10: o que entrou manualmente é o registro curado; o chat
        só completa o que falta). O campo do chat é descartado com aviso
        — e dia duplicado também vira aviso, não pendência: a política
        já garante que nada existente é sobrescrito.

    Devolve (payload_itens, rel) com rel = {novos, enriquecidos,
    sem_mudanca, conflitos, pendencias, avisos}.
    """
    rel = {'novos': [], 'enriquecidos': [], 'sem_mudanca': [],
           'conflitos': [], 'pendencias': [], 'avisos': []}
    payload = []

    for item_w in sorted(rdos_whatsapp, key=lambda i: i['data']):
        data = item_w['data']

        # Typo de ano no chat ("09/03/2016") datar-ia um RDO dez anos no
        # passado. Ano implausível → pendência, nunca payload.
        if int(data[:4]) < 2020:
            rel['pendencias'].append(
                f'{data}: ano implausível — provável typo no texto do chat '
                f'(ex.: 2016 por 2026). Corrija a data e rode de novo; o '
                f'dia NÃO entrou no payload')
            continue

        base = rdos_sistema.get(data)

        # ── validação de apontamentos contra o mapa da obra ──
        apontamentos_ok = []
        for ap in item_w.get('apontamentos') or []:
            chave = ap.get('tarefa_mpp')
            if str(chave) not in mapa_nomes and chave not in mapa_nomes:
                rel['pendencias'].append(
                    f'{data}: apontamento com tarefa_mpp {chave} fora do '
                    f'mapa da obra — não entrou no payload')
                continue
            apontamentos_ok.append(ap)

        if base is None:
            # Só as chaves que o updater LÊ — `mao_de_obra` etc. seriam
            # ruído carregado de item em item.
            novo = {'data': data}
            for campo in CAMPOS_TEXTO:
                if not _vazio(item_w.get(campo)):
                    novo[campo] = item_w[campo]
            if item_w.get('fotos'):
                novo['fotos'] = item_w['fotos']
            if apontamentos_ok:
                novo['apontamentos'] = apontamentos_ok
            payload.append(novo)
            rel['novos'].append(data)
            continue

        # ── dia existe no sistema ──
        estado = base.get('_estado')
        if estado in ESTADOS_IMUTAVEIS:
            rel['pendencias'].append(
                f'{data}: RDO {base.get("_numero_rdo")} está {estado} — o '
                f'updater o pularia; para corrigir, emita retificador')
            continue

        delta, conflitos_dia = {'data': data}, []
        for campo in CAMPOS_TEXTO:
            v_w, v_s = item_w.get(campo), base.get(campo)
            if _vazio(v_w):
                continue
            if data in datas_duplicadas:
                msg = (f'{data}: {campo} do WhatsApp NÃO entrou — o dia tem '
                       f'mais de um RDO no sistema e o export pode ter '
                       f'retratado outro RDO que não o que o updater '
                       f'atualiza; re-exporte o zip (versão com "exportado '
                       f'o PRIMEIRO") e rode de novo')
                if politica_conflito == 'sistema':
                    rel['avisos'].append(msg)
                else:
                    rel['pendencias'].append(msg)
                continue
            if _vazio(v_s):
                delta[campo] = v_w
            elif str(v_s).strip() != str(v_w).strip():
                if politica_conflito == 'sistema':
                    rel['avisos'].append(
                        f'{data}: {campo} divergente — mantido o texto do '
                        f'SISTEMA (--conflito=sistema); o do chat foi '
                        f'descartado')
                else:
                    conflitos_dia.append({'campo': campo, 'sistema': v_s,
                                          'whatsapp': v_w})

        if apontamentos_ok:
            if base.get('apontamentos'):
                conflitos_dia.append({'campo': 'apontamentos',
                                      'sistema': base['apontamentos'],
                                      'whatsapp': apontamentos_ok})
            else:
                delta['apontamentos'] = apontamentos_ok

        if item_w.get('fotos'):
            if base.get('_fotos_no_banco'):
                rel['avisos'].append(
                    f'{data}: RDO já tem {base["_fotos_no_banco"]} foto(s) '
                    f'no banco — o updater preserva as existentes e ignora '
                    f'as do WhatsApp')
            else:
                delta['fotos'] = item_w['fotos']

        if conflitos_dia:
            delta['_conflito'] = conflitos_dia
            rel['conflitos'].append(data)
            for c in conflitos_dia:
                rel['pendencias'].append(
                    f'{data}: {c["campo"]} preenchido nos DOIS lados e '
                    f'diferente — resolva o _conflito no payload (o campo '
                    f'não entra até lá)')

        if len(delta) > 1 + (1 if '_conflito' in delta else 0):
            payload.append(delta)
            rel['enriquecidos'].append(data)
        elif conflitos_dia:
            payload.append(delta)  # só o conflito, para você resolver nele
        else:
            rel['sem_mudanca'].append(data)

    return payload, rel


def distribuir_pct(payload, datas_sistema, folhas_mpp, imutaveis=()):
    """Distribui o % das FOLHAS do .mpp como apontamentos pelos dias de RDO.

    A regra — dita pelo que a data torna VERDADEIRO, nunca por estética:

      * tarefa 100%: apontamento no primeiro dia de RDO ≥ `data_fim` da
        tarefa ("na data X ela já estava pronta" é fato); sem dia
        posterior, cai no último dia disponível, com aviso;
      * tarefa parcial (0<pct<100): apontamento no ÚLTIMO dia de RDO — o
        .mpp é um snapshot ("está em X%"); afirmar X% numa data anterior
        inventaria história. No último registro a afirmação é segura
        (o real só pode ser ≥ X%);
      * resumos ficam de fora: o % deles deriva das folhas;
      * dia imutável nunca é alvo — pula para o próximo; sem próximo,
        pendência.

    As chaves são os `uid` do .mpp: elas SÓ resolvem depois que o
    cronograma for importado pela tela (que grava `mpp_uid`). A ordem —
    cronograma primeiro, payload depois — é obrigatória e sai no relatório.

    Pura: recebe listas/dicts, devolve (payload, rel_pct).
    """
    rel = {'apontados_100': 0, 'apontados_parciais': 0, 'dias_alvo': {},
           'avisos': [], 'pendencias': []}
    datas = sorted((set(datas_sistema) | {i['data'] for i in payload})
                   - set(imutaveis))
    if not datas:
        rel['pendencias'].append(
            'distribuição de %: nenhum dia de RDO disponível como alvo')
        return payload, rel

    por_data = {i['data']: i for i in payload}

    def _item(data):
        if data not in por_data:
            por_data[data] = {'data': data}
            payload.append(por_data[data])
        return por_data[data]

    for t in folhas_mpp:
        pct = t.get('pct_project') or 0
        if t.get('resumo') or pct <= 0:
            continue
        if pct >= 100:
            if not t.get('fim'):
                rel['avisos'].append(
                    f'tarefa {t["uid"]} ("{t["nome"][:40]}") a 100% sem '
                    f'data_fim no .mpp — registrada no primeiro RDO')
            alvo = next((d for d in datas if d >= str(t.get('fim') or '')),
                        None)
            if alvo is None:
                alvo = datas[-1]
                rel['avisos'].append(
                    f'tarefa {t["uid"]} ("{t["nome"][:40]}") termina '
                    f'{t.get("fim")} — depois do último RDO; 100% '
                    f'registrado em {alvo}')
            rel['apontados_100'] += 1
        else:
            alvo = datas[-1]
            rel['apontados_parciais'] += 1
        item = _item(alvo)
        item.setdefault('apontamentos', []).append(
            {'tarefa_mpp': int(t['uid']), 'pct': float(pct)})
        rel['dias_alvo'][alvo] = rel['dias_alvo'].get(alvo, 0) + 1

    payload.sort(key=lambda i: i['data'])
    return payload, rel


def _relatorio(obra_json, meta_whats, payload, rel):
    o = obra_json['obra']
    linhas = [
        f'[preparar_carga_obra] obra {o.get("codigo") or o["id"]} — '
        f'{o["nome"]} (admin {o["admin_username"] or o["admin_id"]})',
        f'  sistema: {obra_json["rdos"]["total"]} RDO(s) '
        f'({obra_json["rdos"]["primeira_data"]} → '
        f'{obra_json["rdos"]["ultima_data"]}); '
        f'{obra_json["cronograma"]["tarefas_vivas"]} tarefa(s) viva(s), '
        f'{obra_json["cronograma"]["tarefas_com_mpp_uid"]} com mpp_uid',
        f'  whatsapp: {meta_whats["dias"]} dia(s) de RDO',
        f'  payload : {len(payload)} item(ns) — novos={len(rel["novos"])} '
        f'enriquecidos={len(rel["enriquecidos"])} '
        f'sem_mudanca={len(rel["sem_mudanca"])} '
        f'conflitos={len(rel["conflitos"])}',
    ]
    for rot, chave in (('novos', 'novos'), ('enriquecidos', 'enriquecidos'),
                       ('sem mudança', 'sem_mudanca')):
        if rel[chave]:
            linhas.append(f'    {rot}: {", ".join(rel[chave])}')
    avisos = list(meta_whats.get('avisos') or []) + rel['avisos']
    if avisos:
        linhas.append(f'  avisos ({len(avisos)}):')
        linhas.extend(f'    - {a}' for a in avisos)
    pendencias = list(meta_whats.get('pendencias') or []) + rel['pendencias']
    if pendencias:
        linhas.append(f'  PENDÊNCIAS ({len(pendencias)}) — resolver antes de aplicar:')
        linhas.extend(f'    - {p}' for p in pendencias)
    return '\n'.join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Mescla export do sistema + WhatsApp num payload-delta '
                    'de RDOs, com fotos em base isolada por obra.')
    p.add_argument('--export', required=True, help='zip do botão Exportar RDOs')
    p.add_argument('--whatsapp', help='zip do export da conversa do WhatsApp')
    p.add_argument('--obra-marcador',
                   help='marcador da obra no chat (ex.: "Obra a Angela")')
    p.add_argument('--saida-dir', help='default: cargas/obra-<codigo|id>')
    p.add_argument('--fotos-base',
                   help='default: fotos_rdos/obras/<codigo|id>')
    p.add_argument('--mpp',
                   help='cronograma .mpp/.xml com as %% novas: as FOLHAS com '
                        'pct>0 viram apontamentos distribuídos pelos dias de '
                        'RDO (100%% no primeiro dia >= data_fim; parciais no '
                        'último dia). Exige importar o MESMO arquivo pela aba '
                        'Cronograma ANTES de aplicar o payload')
    p.add_argument('--conflito', choices=('pendencia', 'sistema'),
                   default='pendencia',
                   help='campo preenchido nos dois lados e diferente: '
                        '"pendencia" (default) para revisar à mão; '
                        '"sistema" mantém o que já está no sistema e '
                        'descarta o do chat, com aviso')
    p.add_argument('--corrigir-data', action='append', default=[],
                   metavar='ERRADA=CERTA',
                   help='corrige typo de data do chat (ex.: '
                        '2016-03-09=2026-03-09); pode repetir. A correção '
                        'sai no relatório — nunca é silenciosa')
    p.add_argument('--regras', help='JSON de regras atividade→tarefa (opcional)')
    p.add_argument('--aplicar-sugestoes', action='store_true')
    p.add_argument('--forcar', action='store_true',
                   help='regrava pasta de foto que já tem arquivo')
    p.add_argument('--dry-run', action='store_true',
                   help='não grava payload nem fotos — só o relatório')
    args = p.parse_args(argv)

    obra_json, rdos_sistema, mapa_nomes = ler_export(args.export)
    o = obra_json['obra']
    slug = str(o.get('codigo') or o['id'])
    saida_dir = args.saida_dir or os.path.join(_RAIZ, 'cargas', f'obra-{slug}')
    fotos_base = args.fotos_base or os.path.join(
        _RAIZ, 'fotos_rdos', 'obras', slug)

    rdos_whats, meta_whats = [], {'dias': 0, 'avisos': [], 'pendencias': []}
    if args.whatsapp:
        if not args.obra_marcador:
            p.error('--whatsapp exige --obra-marcador')
        import whatsapp_para_rdos as w
        regras = None
        if args.regras:
            with open(args.regras, encoding='utf-8') as fh:
                regras = json.load(fh)
        apelidos = [m.strip() for m in args.obra_marcador.split(',')]
        payload_w, meta_whats = w.converter(
            caminho_zip=args.whatsapp,
            marcador_obra=apelidos if len(apelidos) > 1 else apelidos[0],
            marcadores_conhecidos=[m for m in MARCADORES_CONHECIDOS
                                   if m not in apelidos],
            base_fotos=fotos_base, regras=regras,
            aplicar_sugestoes=args.aplicar_sugestoes,
            dry_run=args.dry_run, forcar=args.forcar)
        rdos_whats = payload_w['rdos']

    correcoes = dict(c.split('=', 1) for c in args.corrigir_data)
    for item in rdos_whats:
        if item['data'] in correcoes:
            certa = correcoes[item['data']]
            meta_whats.setdefault('avisos', []).append(
                f'{item["data"]} CORRIGIDA para {certa} por --corrigir-data '
                f'(typo do chat)')
            # A pasta de fotos foi gravada com a data errada — acompanha.
            errada_dir = os.path.join(fotos_base, item['data'])
            certa_dir = os.path.join(fotos_base, certa)
            if os.path.isdir(errada_dir) and not os.path.isdir(certa_dir):
                os.rename(errada_dir, certa_dir)
            item['data'] = certa

    # Dias com mais de um RDO no sistema, exportados pela versão ANTIGA do
    # export (que retratava o mais recente; o updater escreve no primeiro).
    # Só nesses o texto vira pendência — o export novo diz "exportado o
    # PRIMEIRO" no aviso e aí a mescla olhou o RDO certo.
    import re
    duplicadas = {
        m.group(1)
        for a in (obra_json.get('_meta', {}).get('avisos') or [])
        if 'PRIMEIRO' not in a
        for m in [re.match(r'^(\d{4}-\d{2}-\d{2}): mais de um RDO', a)] if m}

    payload, rel = mesclar(rdos_sistema, rdos_whats, mapa_nomes, duplicadas,
                           politica_conflito=args.conflito)

    rel_pct = None
    if args.mpp:
        sys.path.insert(0, _RAIZ)
        from services.mpp_parser import parse_cronograma
        folhas = parse_cronograma(args.mpp)['tarefas']
        imutaveis = [d for d, r in rdos_sistema.items()
                     if r.get('_estado') in ESTADOS_IMUTAVEIS]
        payload, rel_pct = distribuir_pct(
            payload, list(rdos_sistema), folhas, imutaveis)
        rel['avisos'].extend(rel_pct['avisos'])
        rel['pendencias'].extend(rel_pct['pendencias'])

    print(_relatorio(obra_json, meta_whats, payload, rel))
    if rel_pct:
        dias = ', '.join(f'{d} ({n})'
                         for d, n in sorted(rel_pct['dias_alvo'].items()))
        print(f'  % .mpp  : {rel_pct["apontados_100"]} tarefa(s) a 100% + '
              f'{rel_pct["apontados_parciais"]} parcial(is) distribuídas '
              f'em: {dias}')
        print('  ⚠ ORDEM: importe o .mpp pela aba Cronograma da obra ANTES '
              'de aplicar este payload — as chaves são os uid do Project e '
              'só resolvem com o mpp_uid gravado pelo import.')

    if args.dry_run:
        print('  (--dry-run: payload e fotos NÃO gravados)')
        return 0

    os.makedirs(saida_dir, exist_ok=True)
    caminho_payload = os.path.join(saida_dir, 'payload_rdos.json')
    with open(caminho_payload, 'w', encoding='utf-8') as fh:
        json.dump({'rdos': payload}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    with open(os.path.join(saida_dir, 'relatorio.txt'), 'w',
              encoding='utf-8') as fh:
        fh.write(_relatorio(obra_json, meta_whats, payload, rel) + '\n')
    print(f'  payload : {caminho_payload}')
    print(f'  fotos   : {fotos_base}/')
    print(f'  aplicar : python scripts/atualizar_rdos_obra.py '
          f'{o["admin_username"] or o["admin_id"]} {slug} '
          f'{os.path.relpath(caminho_payload, _RAIZ)} '
          f'--fotos-base {os.path.relpath(fotos_base, _RAIZ)} --dry-run')
    return 0


if __name__ == '__main__':
    sys.exit(main())
