#!/usr/bin/env python3
"""Migração de `rdo_foto` de base64 no banco para arquivo em disco.

═══════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE (medido em 2026-07-21, banco de desenvolvimento)
═══════════════════════════════════════════════════════════════════════

    pg_database_size(current_database())  = 16 GB
    pg_total_relation_size('rdo_foto')    = 16 GB   ← praticamente tudo
    pg_relation_size('rdo_foto') (heap)   = 11 MB
    TOAST de rdo_foto                     = 16 GB   ← as três base64
    28.870 fotos em 5.532 RDOs
    28.860 já com arquivo em disco · 10 só em base64
    linha típica: 313.615 + 122.983 + 16.203 chars ≈ 442 KB

Isso define o RPO real do backup: um dump completo é de 16 GB e não cabe
em janela curta. As colunas de caminho (`arquivo_original`,
`arquivo_otimizado`, `thumbnail`) já existem e já estão preenchidas.

═══════════════════════════════════════════════════════════════════════
DUAS PASSADAS, PORQUE A PRIMEIRA É REVERSÍVEL E A SEGUNDA NÃO
═══════════════════════════════════════════════════════════════════════

  Passada 1 — `migrar_para_disco()`
      Garante que o arquivo existe em disco (escrevendo a partir da
      base64 quando faltar), VERIFICA que ele abre como imagem, e marca
      `armazenamento='disco'`. A base64 continua no banco.
      Rollback: `reverter()`, um comando.

  Passada 2 — `liberar_base64()`  ⚠️ DESTRUTIVA
      Para cada foto marcada 'disco', reverifica os três arquivos e só
      então zera as três colunas TEXT. Recusa qualquer foto cujo arquivo
      não abra. Depois disso, a foto SÓ existe no volume — se o volume
      não for persistente, o próximo deploy destrói o acervo.

PRÉ-REQUISITOS DA PASSADA 2 (ver docs/fase-5-rollout.md):
  volume persistente montado · UPLOADS_PATH definido · Task 13 aplicada ·
  dump completo guardado fora do servidor · snapshot do volume ·
  janela de manutenção para o VACUUM FULL.

Uso:
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --aplicar
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --liberar
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --liberar --aplicar
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --reverter --aplicar
"""
from __future__ import annotations

import argparse
import base64
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('migrar_fotos_rdo')

LOTE_PADRAO = 200


def _decodificar(valor):
    """Bytes de uma coluna base64 (com ou sem prefixo data URI)."""
    if not valor:
        return None
    texto = valor.split(',', 1)[1] if ',' in valor[:64] else valor
    try:
        return base64.b64decode(texto)
    except Exception:
        logger.warning('base64 ilegível — ignorada')
        return None


def _escrever(caminho_absoluto_alvo, dados):
    os.makedirs(os.path.dirname(caminho_absoluto_alvo), exist_ok=True)
    temporario = caminho_absoluto_alvo + '.parcial'
    with open(temporario, 'wb') as fh:
        fh.write(dados)
    os.replace(temporario, caminho_absoluto_alvo)


def _arquivo_valido(caminho):
    """True se o arquivo existe, tem bytes e abre como imagem."""
    if not caminho or not os.path.exists(caminho):
        return False
    try:
        if os.path.getsize(caminho) <= 0:
            return False
        from PIL import Image
        with Image.open(caminho) as img:
            img.verify()
        return True
    except Exception:
        return False


# Mapa: coluna de caminho → coluna base64 correspondente + sufixo do nome.
_TRIO = (
    ('arquivo_original', 'imagem_original_base64', '_original.webp'),
    ('arquivo_otimizado', 'imagem_otimizada_base64', '.webp'),
    ('thumbnail', 'thumbnail_base64', '_thumb.webp'),
)


def migrar_para_disco(admin_id=None, aplicar=False, lote=LOTE_PADRAO,
                      limite=None):
    """Passada 1 — REVERSÍVEL. Garante o arquivo em disco e marca 'disco'."""
    from app import app, db
    from models import RDOFoto
    from services.rdo_foto_service import caminho_absoluto

    relatorio = {'analisadas': 0, 'migradas': 0, 'ja_em_disco': 0,
                 'falhas': [], 'aplicar': aplicar}

    with app.app_context():
        query = RDOFoto.query.filter(RDOFoto.armazenamento == 'banco')
        if admin_id is not None:
            query = query.filter(RDOFoto.admin_id == admin_id)
        query = query.order_by(RDOFoto.id.asc())
        if limite:
            query = query.limit(limite)

        pendentes = query.all()
        logger.info('%s foto(s) marcadas "banco"%s', len(pendentes),
                    f' no tenant {admin_id}' if admin_id else '')

        for indice, foto in enumerate(pendentes, start=1):
            relatorio['analisadas'] += 1
            base_relativa = f'uploads/rdo/{foto.admin_id}/{foto.rdo_id}'
            nome_base = os.path.splitext(
                os.path.basename(foto.arquivo_otimizado
                                 or foto.nome_arquivo
                                 or f'foto{foto.id}'))[0]

            caminhos_ok = True
            atualizacoes = {}
            for coluna_caminho, coluna_b64, sufixo in _TRIO:
                relativo = getattr(foto, coluna_caminho, None)
                if not relativo:
                    relativo = f'{base_relativa}/{nome_base}{sufixo}'
                    atualizacoes[coluna_caminho] = relativo
                alvo = caminho_absoluto(relativo)
                if alvo is None:
                    caminhos_ok = False
                    relatorio['falhas'].append(
                        {'foto_id': foto.id, 'motivo': 'caminho_invalido',
                         'caminho': relativo})
                    break
                if _arquivo_valido(alvo):
                    continue
                dados = _decodificar(getattr(foto, coluna_b64, None))
                if dados is None:
                    caminhos_ok = False
                    relatorio['falhas'].append(
                        {'foto_id': foto.id, 'motivo': 'sem_origem',
                         'coluna': coluna_b64})
                    break
                if aplicar:
                    _escrever(alvo, dados)
                    if not _arquivo_valido(alvo):
                        caminhos_ok = False
                        relatorio['falhas'].append(
                            {'foto_id': foto.id, 'motivo': 'escrita_invalida',
                             'caminho': relativo})
                        break

            if not caminhos_ok:
                continue

            relatorio['migradas'] += 1
            if aplicar:
                for coluna, valor in atualizacoes.items():
                    setattr(foto, coluna, valor)
                foto.armazenamento = 'disco'
                if indice % lote == 0:
                    db.session.commit()
                    logger.info('… %s/%s', indice, len(pendentes))

        if aplicar:
            db.session.commit()

    logger.info('passada 1: %s analisada(s), %s migrada(s), %s falha(s) '
                '[%s]', relatorio['analisadas'], relatorio['migradas'],
                len(relatorio['falhas']),
                'APLICADO' if aplicar else 'DRY-RUN')
    return relatorio


def liberar_base64(admin_id=None, aplicar=False, lote=LOTE_PADRAO,
                   limite=None):
    """Passada 2 — ⚠️ DESTRUTIVA. Zera as três colunas TEXT.

    Só libera a foto cujos TRÊS arquivos abram como imagem AGORA. Uma
    foto cujo arquivo sumiu mantém a base64 e entra em `recusadas`.
    """
    from app import app, db
    from models import RDOFoto
    from services.rdo_foto_service import caminho_absoluto

    relatorio = {'analisadas': 0, 'liberadas': 0, 'recusadas': 0,
                 'detalhe_recusas': [], 'aplicar': aplicar}

    with app.app_context():
        query = RDOFoto.query.filter(RDOFoto.armazenamento == 'disco')
        if admin_id is not None:
            query = query.filter(RDOFoto.admin_id == admin_id)
        query = query.order_by(RDOFoto.id.asc())
        if limite:
            query = query.limit(limite)

        candidatas = query.all()
        logger.info('%s foto(s) marcadas "disco"%s', len(candidatas),
                    f' no tenant {admin_id}' if admin_id else '')

        for indice, foto in enumerate(candidatas, start=1):
            relatorio['analisadas'] += 1
            faltando = [
                coluna for coluna, _b64, _s in _TRIO
                if not _arquivo_valido(caminho_absoluto(getattr(foto, coluna, None)))
            ]
            if faltando:
                relatorio['recusadas'] += 1
                relatorio['detalhe_recusas'].append(
                    {'foto_id': foto.id, 'rdo_id': foto.rdo_id,
                     'faltando': faltando})
                logger.warning('foto %s RECUSADA — arquivo ausente: %s',
                               foto.id, faltando)
                continue

            relatorio['liberadas'] += 1
            if aplicar:
                foto.imagem_original_base64 = None
                foto.imagem_otimizada_base64 = None
                foto.thumbnail_base64 = None
                if indice % lote == 0:
                    db.session.commit()
                    logger.info('… %s/%s', indice, len(candidatas))

        if aplicar:
            db.session.commit()

    logger.info('passada 2: %s analisada(s), %s liberada(s), %s recusada(s) '
                '[%s]', relatorio['analisadas'], relatorio['liberadas'],
                relatorio['recusadas'],
                'APLICADO' if aplicar else 'DRY-RUN')
    if relatorio['recusadas']:
        logger.error('⚠️ %s foto(s) recusadas — resolva ANTES de seguir',
                     relatorio['recusadas'])
    return relatorio


def reverter(admin_id=None, aplicar=False):
    """Rollback da passada 1: volta 'disco' → 'banco'.

    Só faz sentido enquanto a base64 ainda estiver lá. Fotos já liberadas
    (base64 nula) não são revertidas — não há para onde voltar.
    """
    from app import app, db
    from models import RDOFoto

    relatorio = {'revertidas': 0, 'sem_base64': 0, 'aplicar': aplicar}

    with app.app_context():
        query = RDOFoto.query.filter(RDOFoto.armazenamento == 'disco')
        if admin_id is not None:
            query = query.filter(RDOFoto.admin_id == admin_id)
        for foto in query.order_by(RDOFoto.id.asc()).all():
            if foto.imagem_otimizada_base64 is None:
                relatorio['sem_base64'] += 1
                continue
            relatorio['revertidas'] += 1
            if aplicar:
                foto.armazenamento = 'banco'
        if aplicar:
            db.session.commit()

    logger.info('reversão: %s revertida(s), %s sem base64 [%s]',
                relatorio['revertidas'], relatorio['sem_base64'],
                'APLICADO' if aplicar else 'DRY-RUN')
    return relatorio


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--admin-id', type=int, default=None,
                        help='limita a um tenant (recomendado)')
    parser.add_argument('--aplicar', action='store_true',
                        help='sem esta flag, roda em DRY-RUN')
    parser.add_argument('--liberar', action='store_true',
                        help='passada 2: zera a base64 (DESTRUTIVO)')
    parser.add_argument('--reverter', action='store_true',
                        help='rollback da passada 1')
    parser.add_argument('--lote', type=int, default=LOTE_PADRAO)
    parser.add_argument('--limite', type=int, default=None,
                        help='processa no máximo N fotos (ensaio)')
    args = parser.parse_args()

    if args.liberar and args.aplicar and not os.environ.get('UPLOADS_PATH'):
        logger.error('❌ UPLOADS_PATH não definido. Liberar a base64 sem '
                     'volume persistente montado APAGA as fotos no próximo '
                     'deploy. Abortado.')
        return 2

    if args.reverter:
        relatorio = reverter(admin_id=args.admin_id, aplicar=args.aplicar)
    elif args.liberar:
        relatorio = liberar_base64(admin_id=args.admin_id,
                                   aplicar=args.aplicar, lote=args.lote,
                                   limite=args.limite)
    else:
        relatorio = migrar_para_disco(admin_id=args.admin_id,
                                      aplicar=args.aplicar, lote=args.lote,
                                      limite=args.limite)

    print(relatorio)
    return 0


if __name__ == '__main__':
    sys.exit(main())
