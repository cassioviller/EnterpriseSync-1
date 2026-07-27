"""Anexo de fotos de RDO a partir da pasta `fotos_rdos/<AAAA-MM-DD>/`.

Extraído de `services/importacao_fisico_financeiro.py` em 27/07/2026 para
ser usado também por `services/atualizacao_rdos.py` (o caminho não-destrutivo
de atualização de RDOs). A lógica é a mesma de sempre — o único ajuste é que
a **base das fotos vem por parâmetro**: o módulo de importação tem seu próprio
`FOTOS_RDO_BASE` de módulo, que os testes trocam por uma pasta temporária, e
esse ponteiro precisa continuar valendo na hora da chamada.

Convenção da pasta (documentada em `fotos_rdos/README.md`): uma subpasta por
dia, imagens numeradas `1.jpg`, `2.png`… na ordem em que aparecem no RDO — a
mesma ordem das legendas que vêm no JSON.
"""
from __future__ import annotations

import glob
import logging
import os

logger = logging.getLogger(__name__)

# Base padrão. Cada caller mantém a SUA (o import físico-financeiro expõe
# `FOTOS_RDO_BASE` de módulo, trocado nos testes) e a passa na chamada.
FOTOS_RDO_BASE_PADRAO = os.environ.get('FOTOS_RDO_BASE', 'fotos_rdos')


def resolver_arquivo_foto(pasta, indice, nome):
    """Localiza o arquivo de uma foto dentro de `pasta` (fotos_rdos/<data>/).

    - Se `nome` foi informado no JSON, usa-o direto.
    - Senão, aplica a convenção posicional: a i-ésima foto da lista é o arquivo
      `(indice+1).<ext>` (1.jpg, 2.png…), na ordem em que o usuário numerou.
    Retorna o caminho absoluto/relativo do arquivo, ou None se não existir.
    """
    if nome:
        cam = os.path.join(pasta, nome)
        return cam if os.path.isfile(cam) else None
    achados = sorted(glob.glob(os.path.join(pasta, f"{indice + 1}.*")))
    return achados[0] if achados else None


def listar_imagens_ordenadas(pasta):
    """Lista os arquivos de imagem de `pasta`, em ordem numérica quando os nomes
    forem 1.jpg, 2.png… (senão por nome). Usado para anexar as fotos de um RDO que
    tem imagens na pasta mas NÃO trouxe legendas no JSON (dia sem legenda)."""
    if not os.path.isdir(pasta):
        return []
    achados = set()
    for e in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        achados.update(glob.glob(os.path.join(pasta, f'*.{e}')))
        achados.update(glob.glob(os.path.join(pasta, f'*.{e.upper()}')))

    def _chave(p):
        base = os.path.splitext(os.path.basename(p))[0]
        return (0, int(base)) if base.isdigit() else (1, os.path.basename(p).lower())
    return sorted(achados, key=_chave)


def materializar_fotos_rdo(rdo, admin_id, dia, fotos, base=None, prefixo_log='FF_IMPORT'):
    """Anexa as fotos de um RDO.

    Com lista `fotos` no JSON, cada item pode ser:
      - uma STRING → só a legenda; o arquivo é inferido pela ordem na pasta
        `fotos_rdos/<data>/` (1.<ext>, 2.<ext>…);
      - um OBJETO `{"arquivo": "1.jpg", "legenda": "..."}` → nome explícito.

    SEM lista `fotos` (dia com fotos na pasta mas sem legendas), anexa TODAS as
    imagens da pasta em ordem numérica, com legenda vazia — assim dias sem legenda
    também importam as fotos.

    Reusa `salvar_foto_rdo` (mesma otimização WebP + base64 do upload da tela), de
    modo que a foto fica persistida no banco (sobrevive a deploy/restart). Fotos
    ausentes na pasta viram warning — NÃO quebram o import. Retorna nº de fotos
    criadas.

    Idempotência: no reimport destrutivo o RDO é recriado e a FK ON DELETE CASCADE
    remove as RDOFoto antigas junto. No caminho NÃO-destrutivo
    (`services/atualizacao_rdos.py`) não há recriação — lá o caller pula o RDO que
    já tem foto anexada, senão a reexecução duplicaria o álbum.
    """
    base = base or FOTOS_RDO_BASE_PADRAO
    pasta = os.path.join(base, dia.isoformat())
    if not fotos:
        auto = listar_imagens_ordenadas(pasta)
        if not auto:
            return 0
        fotos = [{'arquivo': os.path.basename(p), 'legenda': ''} for p in auto]

    from app import db
    from models import RDOFoto
    from services.rdo_foto_service import salvar_foto_rdo
    from werkzeug.datastructures import FileStorage

    criadas = 0
    for i, f in enumerate(fotos):
        if isinstance(f, str):
            nome, legenda = None, f
        elif isinstance(f, dict):
            nome, legenda = f.get('arquivo'), (f.get('legenda') or '')
        else:
            continue
        caminho = resolver_arquivo_foto(pasta, i, nome)
        if caminho is None:
            logger.warning(
                "[%s] RDO %s: foto %s não encontrada em %s (pulada)",
                prefixo_log, dia.isoformat(), nome or (i + 1), pasta)
            continue
        try:
            with open(caminho, 'rb') as fh:
                fs = FileStorage(stream=fh, filename=os.path.basename(caminho))
                res = salvar_foto_rdo(fs, admin_id, rdo.id)
        except Exception as e:  # foto inválida/corrompida não derruba o import
            logger.warning("[%s] RDO %s: falha ao processar %s: %s",
                           prefixo_log, dia.isoformat(), caminho, e)
            continue
        db.session.add(RDOFoto(
            admin_id=admin_id, rdo_id=rdo.id,
            # campos legados NOT NULL
            nome_arquivo=res['nome_original'],
            caminho_arquivo=res['arquivo_otimizado'],
            legenda=legenda, descricao=legenda,
            # v9.0 (arquivos físicos, backup)
            arquivo_original=res['arquivo_original'],
            arquivo_otimizado=res['arquivo_otimizado'],
            thumbnail=res['thumbnail'],
            nome_original=res['nome_original'],
            tamanho_bytes=res['tamanho_bytes'],
            ordem=i,
            # Fase 5 — política (só disco × disco+base64) em salvar_foto_rdo:
            # sem volume persistente a base64 vem preenchida e é a cópia
            # durável, com volume vem None e o arquivo é a fonte de verdade.
            imagem_original_base64=res.get('imagem_original_base64'),
            imagem_otimizada_base64=res.get('imagem_otimizada_base64'),
            thumbnail_base64=res.get('thumbnail_base64'),
            armazenamento=res.get('armazenamento', 'disco'),
        ))
        criadas += 1
    return criadas
