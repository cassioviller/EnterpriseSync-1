"""Exportação dos RDOs de uma obra — o zip autossuficiente da carga local.

Par de leitura de `services/atualizacao_rdos.py`: este módulo produz, a
partir do banco, EXATAMENTE o payload que aquele consome — para o ciclo
exportar → revisar no repositório → mesclar com o WhatsApp → upsert de
volta. Plano: docs/superpowers/plans/2026-08-10-carga-nao-destrutiva-cronograma-rdos.md.

O zip carrega a identidade da obra (codigo, admin, tarefas) justamente para
que os scripts locais não precisem de acesso ao banco de produção nem de
parâmetros passados à mão.

Conteúdo:

  obra.json        identidade + versão ativa + contagens + tabela de tarefas
                   do cronograma interno vivo (a MESMA população que o
                   `IndiceTarefas` do updater resolve);
  rdos.json        {"rdos": [...]} no formato canônico do upsert, ordenado
                   por data; o que não round-tripa vai em chave `_`
                   (`_numero_rdo`, `_estado`, `_efetivo`…) — o updater as
                   ignora por contrato, então servem só à revisão humana;
  mapa_nomes.json  {tarefa_mpp: {nome, pai, caminho}} para TODAS as chaves
                   exportadas — o fallback por nome do `IndiceTarefas`
                   (mesmo formato de `mapa_nomes_do_json`);
  fotos/<data>/N.<ext>   opcional (`com_fotos=True`). Round-trip na MESMA
                   obra não precisa: as fotos já estão no banco e o updater
                   preserva RDO que já tem foto. Só vale para migrar RDOs
                   entre obras.

A chave `tarefa_mpp` de cada apontamento:

  * tarefa com `mpp_uid` → o próprio uid (resolução direta no reimport);
  * tarefa SEM `mpp_uid` (obra que nunca importou .mpp) → **-tarefa.id**
    (negativo). Usar o id positivo colidiria com uids reais do MS Project
    (`_por_uid` do updater casaria a tarefa errada em silêncio); negativo
    nunca casa uid e cai direto no fallback por nome via mapa_nomes.json.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import zipfile
from datetime import datetime

logger = logging.getLogger(__name__)

# Versão do formato do zip — os scripts locais recusam major desconhecido.
FORMATO_EXPORT = '1.0'


def _iso(valor):
    return valor.isoformat() if valor else None


def _tarefas_da_obra(obra_id, admin_id):
    """Tarefas do cronograma interno e vivo — mesma população do updater."""
    from models import TarefaCronograma
    return (TarefaCronograma.do_cronograma_interno(obra_id, admin_id)
            .order_by(TarefaCronograma.ordem, TarefaCronograma.id)
            .all())


def _chave_mpp(tarefa):
    """Chave `tarefa_mpp` estável para o reimport (uid, ou -id sem uid)."""
    if tarefa.mpp_uid is not None:
        return int(tarefa.mpp_uid)
    return -int(tarefa.id)


def _montar_mapa_nomes(tarefas):
    """`{chave: {nome, pai, caminho}}` — formato de `mapa_nomes_do_json`.

    O caminho traz TODOS os ancestrais (não só o pai): é o desempate do
    `IndiceTarefas` quando dois ramos repetem o mesmo nome de tarefa.
    """
    por_id = {t.id: t for t in tarefas}
    mapa = {}
    for t in tarefas:
        caminho, atual, visto = [], t, set()
        while atual is not None and atual.id not in visto:
            visto.add(atual.id)
            atual = por_id.get(atual.tarefa_pai_id)
            if atual is not None:
                caminho.append(atual.nome_tarefa)
        caminho.reverse()
        mapa[str(_chave_mpp(t))] = {
            'nome': t.nome_tarefa,
            'pai': caminho[-1] if caminho else None,
            'caminho': caminho,
        }
    return mapa


def _obra_json(obra, admin_id, tarefas, rdos):
    from models import CronogramaVersao, Usuario
    from services.rdo_ciclo_vida import estado_de

    versao = (CronogramaVersao.query
              .filter_by(obra_id=obra.id, status='ativa')
              .first())
    from app import db
    admin = db.session.get(Usuario, admin_id)

    estados = {}
    for r in rdos:
        estados[estado_de(r)] = estados.get(estado_de(r), 0) + 1

    return {
        '_meta': {
            'formato': FORMATO_EXPORT,
            'gerado_em': datetime.utcnow().isoformat(timespec='seconds'),
            'descricao': 'Export de RDOs para carga local não-destrutiva. '
                         'rdos.json é o payload de services/atualizacao_rdos.py; '
                         'mapa_nomes.json é o fallback por nome do IndiceTarefas. '
                         'Chave tarefa_mpp negativa = tarefa sem mpp_uid '
                         '(resolvida SEMPRE pelo mapa, nunca por uid).',
        },
        'obra': {
            'id': obra.id,
            'codigo': obra.codigo,
            'nome': obra.nome,
            'admin_id': admin_id,
            'admin_username': admin.username if admin else None,
            'status': obra.status,
            'data_inicio': _iso(obra.data_inicio),
            'data_previsao_fim': _iso(obra.data_previsao_fim),
            'cronograma_revisado_em': _iso(obra.cronograma_revisado_em),
        },
        'cronograma': {
            'versao_ativa': ({'numero': versao.numero,
                              'aplicada_em': _iso(versao.aplicada_em)}
                             if versao else None),
            'tarefas_vivas': len(tarefas),
            'tarefas_com_mpp_uid': sum(1 for t in tarefas
                                       if t.mpp_uid is not None),
        },
        'rdos': {
            'total': len(rdos),
            'por_estado': estados,
            'primeira_data': _iso(rdos[0].data_relatorio) if rdos else None,
            'ultima_data': _iso(rdos[-1].data_relatorio) if rdos else None,
        },
        'cronograma_tarefas': [
            {
                'tarefa_mpp': _chave_mpp(t),
                'id_banco': t.id,
                'mpp_uid': int(t.mpp_uid) if t.mpp_uid is not None else None,
                'nome': t.nome_tarefa,
                'pai_id_banco': t.tarefa_pai_id,
                'percentual_concluido': t.percentual_concluido,
                'quantidade_total': t.quantidade_total,
                'unidade_medida': t.unidade_medida,
                'data_inicio': _iso(t.data_inicio),
                'data_fim': _iso(t.data_fim),
            }
            for t in tarefas
        ],
    }


def _item_rdo(rdo, chave_por_tarefa_id):
    """Um item de `rdos` no formato canônico do upsert.

    Só entram como chave "viva" os campos que `atualizar_rdos` grava de
    volta; o resto vai em `_` — exportar como viva uma chave que o updater
    ignora criaria a ilusão de que ela round-tripa.
    """
    from models import RDOApontamentoCronograma, RDOMaoObra
    from services.rdo_ciclo_vida import estado_de

    item = {'data': rdo.data_relatorio.isoformat()}
    if rdo.clima_geral:
        item['clima'] = rdo.clima_geral
    if rdo.precipitacao:
        item['precipitacao'] = rdo.precipitacao
    if rdo.comentario_geral:
        item['comentario'] = rdo.comentario_geral

    apontamentos, sem_chave = [], []
    aps = (RDOApontamentoCronograma.query
           .filter_by(rdo_id=rdo.id)
           .order_by(RDOApontamentoCronograma.id)
           .all())
    for ap in aps:
        chave = chave_por_tarefa_id.get(ap.tarefa_cronograma_id)
        if chave is None:
            # Tarefa arquivada ou da cópia-cliente: fora da população viva
            # que o reimport resolve. Vira contexto, nunca payload.
            sem_chave.append({'tarefa_id_banco': ap.tarefa_cronograma_id,
                              'pct': ap.percentual_realizado})
            continue
        apontamentos.append({'tarefa_mpp': chave,
                             'pct': ap.percentual_realizado})
    if apontamentos:
        item['apontamentos'] = apontamentos

    # ── contexto de revisão (o updater ignora chaves `_`) ──
    item['_numero_rdo'] = rdo.numero_rdo
    item['_estado'] = estado_de(rdo)
    efetivo = RDOMaoObra.query.filter_by(rdo_id=rdo.id).count()
    if efetivo:
        item['_efetivo'] = efetivo
    if sem_chave:
        item['_apontamentos_fora_do_cronograma_vivo'] = sem_chave
    fotos = list(rdo.fotos)
    if fotos:
        item['_fotos_no_banco'] = len(fotos)
    return item


def _bytes_da_foto(foto):
    """Bytes da imagem, na ordem de preferência disco → base64 otimizada →
    base64 original. Devolve (bytes, extensão) ou (None, None)."""
    from services.rdo_foto_service import caminho_absoluto

    for rel in (foto.caminho_arquivo, foto.arquivo_otimizado,
                foto.arquivo_original):
        caminho = caminho_absoluto(rel)
        if caminho and os.path.exists(caminho):
            with open(caminho, 'rb') as fh:
                ext = os.path.splitext(caminho)[1].lstrip('.') or 'jpg'
                return fh.read(), ext

    for col, ext in (('imagem_otimizada_base64', 'webp'),
                     ('imagem_original_base64', 'jpg')):
        b64 = getattr(foto, col, None)  # deferred: só carrega aqui
        if b64:
            try:
                dados = base64.b64decode(b64.split(',', 1)[-1])
            except Exception:
                continue
            return dados, ext
    return None, None


def exportar_obra(obra, admin_id, com_fotos=False):
    """Monta o conteúdo do export.

    Devolve (conteudo, avisos):
      conteudo = {'obra.json': dict, 'rdos.json': dict,
                  'mapa_nomes.json': dict,
                  'fotos': [(caminho_no_zip, bytes), ...]}  # só com_fotos
    Read-only: nenhuma escrita em banco ou disco.
    """
    from models import RDO

    avisos = []
    tarefas = _tarefas_da_obra(obra.id, admin_id)
    chave_por_tarefa_id = {t.id: _chave_mpp(t) for t in tarefas}

    rdos = (RDO.query
            .filter_by(obra_id=obra.id)
            .order_by(RDO.data_relatorio, RDO.id)
            .all())

    # Duas linhas na mesma data (legado permite): o updater atualiza o
    # PRIMEIRO (menor id — `atualizar_rdos` avisa e usa `existentes[0]`),
    # então o export tem que retratar ESSE, senão a mescla decide olhando
    # um RDO e a aplicação escreve noutro. Avisa, nunca escolhe em silêncio.
    por_data = {}
    for r in rdos:
        if r.data_relatorio in por_data:
            avisos.append(
                f'{r.data_relatorio.isoformat()}: mais de um RDO nesta data '
                f'({por_data[r.data_relatorio].numero_rdo} e {r.numero_rdo}) '
                f'— exportado o PRIMEIRO ({por_data[r.data_relatorio].numero_rdo}), '
                f'o mesmo que o updater atualiza.')
            continue
        por_data[r.data_relatorio] = r
    unicos = [por_data[d] for d in sorted(por_data)]

    itens, fotos_zip = [], []
    for rdo in unicos:
        item = _item_rdo(rdo, chave_por_tarefa_id)
        if com_fotos:
            legendas = []
            for n, foto in enumerate(rdo.fotos, start=1):
                dados, ext = _bytes_da_foto(foto)
                if dados is None:
                    avisos.append(
                        f'{item["data"]}: foto {foto.id} sem bytes '
                        f'legíveis (disco e base64 vazios) — pulada.')
                    continue
                arquivo = f'{n}.{ext}'
                fotos_zip.append((f'fotos/{item["data"]}/{arquivo}', dados))
                legendas.append({'arquivo': arquivo,
                                 'legenda': foto.legenda or ''})
            if legendas:
                item['fotos'] = legendas
        itens.append(item)

    if not tarefas:
        avisos.append('Obra sem tarefa viva no cronograma interno — '
                      'apontamentos não puderam ser mapeados.')
    sem_uid = len(tarefas) - sum(1 for t in tarefas if t.mpp_uid is not None)
    if sem_uid:
        avisos.append(
            f'{sem_uid} tarefa(s) sem mpp_uid — exportadas com chave '
            f'negativa (-id); o reimport resolve pelo mapa_nomes.json.')

    conteudo = {
        'obra.json': _obra_json(obra, admin_id, tarefas, unicos),
        'rdos.json': {'rdos': itens},
        'mapa_nomes.json': _montar_mapa_nomes(tarefas),
        'fotos': fotos_zip,
    }
    if avisos:
        conteudo['obra.json']['_meta']['avisos'] = avisos
    return conteudo, avisos


def montar_zip(conteudo):
    """Serializa o conteúdo de `exportar_obra` num zip em memória."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nome in ('obra.json', 'rdos.json', 'mapa_nomes.json'):
            zf.writestr(nome, json.dumps(conteudo[nome], ensure_ascii=False,
                                         indent=2) + '\n')
        for caminho, dados in conteudo.get('fotos') or []:
            zf.writestr(caminho, dados)
    buf.seek(0)
    return buf
