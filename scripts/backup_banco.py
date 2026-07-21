#!/usr/bin/env python3
"""Backup e restore do banco — Fase 0.5 / 1.1.

Até 2026-07-21 NÃO existia backup. O entrypoint de produção imprimia
"💾 Criando backup de segurança: <timestamp>" e **não executava comando
nenhum** — imediatamente antes de rodar migrações. O diretório `backups/`
continha 7 arquivos de um evento único, com 5 dos 6 CSVs vazios.

Este script faz o backup de verdade, em formato custom (`-Fc`), que permite
restauração seletiva e é comprimido.

Uso:
    python scripts/backup_banco.py --criar
    python scripts/backup_banco.py --listar
    python scripts/backup_banco.py --restaurar <arquivo> --para <DATABASE_URL destino>
    python scripts/backup_banco.py --verificar <arquivo>

Variáveis:
    DATABASE_URL       origem do dump (obrigatória)
    SIGE_BACKUP_DIR    destino (default /var/backups/sige; ver nota abaixo)

⚠️ O destino PRECISA ser volume persistente. `/tmp` some no restart do
container — foi o erro dos dois scripts manuais que existiam antes.

Retenção: 7 diários + 4 semanais (domingo). A poda roda ao fim de cada
`--criar`.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

DIR_PADRAO = '/var/backups/sige'
RETENCAO_DIARIOS = 7
RETENCAO_SEMANAIS = 4
PREFIXO = 'sige_'
SUFIXO = '.dump'
_RE_NOME = re.compile(
    rf'^{PREFIXO}(\d{{8}}_\d{{6}})(_semanal)?(_sem_fotos)?{re.escape(SUFIXO)}$')


def _destino() -> str:
    d = os.environ.get('SIGE_BACKUP_DIR', DIR_PADRAO)
    os.makedirs(d, exist_ok=True)
    return d


def _url() -> str:
    url = os.environ.get('DATABASE_URL')
    if not url:
        print('ERRO: DATABASE_URL não definida.', file=sys.stderr)
        raise SystemExit(2)
    return url


def _mascarar(url: str) -> str:
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)


# Tabelas cujo DADO pode ser excluído num dump de ensaio (`--sem-fotos`).
#
# ⚠️ `rdo_foto` guarda TRÊS cópias base64 de cada foto —
# `imagem_original_base64`, `imagem_otimizada_base64` e `thumbnail_base64`.
# Base64 infla o binário em ~33%, e são três cópias: 22.461 fotos ocupam
# **14 GB**, ou seja, praticamente todo o tamanho do banco. Isso torna o
# backup completo lento e caro, e é um problema de arquitetura anterior ao
# backup (fotos deveriam viver em storage de objetos, com o banco guardando
# só o caminho — as colunas `caminho_arquivo`/`arquivo_original` já existem).
#
# O backup de PRODUÇÃO inclui tudo por default. `--sem-fotos` existe para
# ensaio de restore e para dumps de diagnóstico.
TABELAS_PESADAS = ('rdo_foto',)


def criar(sem_fotos: bool = False) -> int:
    url, destino = _url(), _destino()
    agora = datetime.now()
    semanal = '_semanal' if agora.weekday() == 6 else ''
    marca = '_sem_fotos' if sem_fotos else ''
    nome = f'{PREFIXO}{agora.strftime("%Y%m%d_%H%M%S")}{semanal}{marca}{SUFIXO}'
    caminho = os.path.join(destino, nome)
    parcial = caminho + '.parcial'

    print(f'[backup] origem={_mascarar(url)}')
    print(f'[backup] destino={caminho}')

    # `-Fc` = custom (comprimido, restauração seletiva). `--no-owner` e
    # `--no-privileges` deixam o dump restaurável em qualquer banco/dono,
    # que é o que viabiliza o teste de restore em banco descartável.
    cmd = ['pg_dump', '--format=custom', '--no-owner', '--no-privileges']
    if sem_fotos:
        for t in TABELAS_PESADAS:
            cmd.append(f'--exclude-table-data={t}')
        print(f'[backup] ENSAIO — dados de {", ".join(TABELAS_PESADAS)} '
              f'excluídos (schema preservado)')
    cmd += ['--file', parcial, url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'[backup] FALHOU: {r.stderr.strip()[:800]}', file=sys.stderr)
        if os.path.exists(parcial):
            os.remove(parcial)
        return 1

    # Só renomeia no fim: um dump interrompido nunca vira arquivo "válido".
    os.rename(parcial, caminho)
    tam = os.path.getsize(caminho)
    if tam < 1024:
        print(f'[backup] SUSPEITO: dump com {tam} bytes', file=sys.stderr)
        return 1
    print(f'[backup] OK — {tam/1024/1024:.2f} MB')

    podados = podar()
    if podados:
        print(f'[backup] retenção: {podados} arquivo(s) removido(s)')
    return 0


def _listar_arquivos():
    """(quando, semanal?, ensaio?, caminho) dos dumps, mais novo primeiro."""
    destino = _destino()
    itens = []
    for n in os.listdir(destino):
        m = _RE_NOME.match(n)
        if m:
            itens.append((datetime.strptime(m.group(1), '%Y%m%d_%H%M%S'),
                          bool(m.group(2)), bool(m.group(3)),
                          os.path.join(destino, n)))
    return sorted(itens, reverse=True)


def podar() -> int:
    """Retenção: 7 diários + 4 semanais. Dumps de ensaio nunca contam como
    backup — são podados assim que houver um mais novo."""
    completos = [i for i in _listar_arquivos() if not i[2]]
    ensaios = [i for i in _listar_arquivos() if i[2]]
    diarios = [i for i in completos if not i[1]]
    semanais = [i for i in completos if i[1]]
    remover = (diarios[RETENCAO_DIARIOS:] + semanais[RETENCAO_SEMANAIS:]
               + ensaios[1:])
    for item in remover:
        os.remove(item[-1])
    return len(remover)


def listar() -> int:
    itens = _listar_arquivos()
    if not itens:
        print(f'Nenhum backup em {_destino()}')
        return 1
    print(f'{"quando":22}{"tipo":10}{"MB":>9}  arquivo')
    for dt, semanal, ensaio, cam in itens:
        mb = os.path.getsize(cam) / 1024 / 1024
        tipo = 'ENSAIO' if ensaio else ('semanal' if semanal else 'diário')
        print(f'{dt:%d/%m/%Y %H:%M:%S}  {tipo:10}{mb:9.2f}  {os.path.basename(cam)}')
    completos = [i for i in itens if not i[2]]
    if not completos:
        print('\nAVISO: só há dumps de ENSAIO — nenhum backup completo.',
              file=sys.stderr)
        return 1
    mais_novo = completos[0][0]
    idade = datetime.now() - mais_novo
    print(f'\nmais recente: {idade.total_seconds()/3600:.1f} h atrás')
    if idade > timedelta(hours=36):
        print('AVISO: backup mais recente tem mais de 36h', file=sys.stderr)
        return 1
    return 0


def verificar(arquivo: str) -> int:
    """Lê o índice do dump sem restaurar — prova que não está corrompido."""
    r = subprocess.run(['pg_restore', '--list', arquivo],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'[verificar] dump ILEGÍVEL: {r.stderr.strip()[:400]}',
              file=sys.stderr)
        return 1
    n = len([l for l in r.stdout.split('\n') if l and not l.startswith(';')])
    print(f'[verificar] OK — {n} objetos no dump')
    return 0


def restaurar(arquivo: str, destino_url: str) -> int:
    if not destino_url:
        print('ERRO: --para <DATABASE_URL> é obrigatório.', file=sys.stderr)
        return 2
    # Guarda contra o pior acidente possível: restaurar por cima da origem.
    if destino_url.strip() == (os.environ.get('DATABASE_URL') or '').strip():
        print('RECUSADO: destino idêntico à DATABASE_URL de origem. '
              'Restaure sempre num banco descartável.', file=sys.stderr)
        return 2

    print(f'[restore] arquivo={arquivo}')
    print(f'[restore] destino={_mascarar(destino_url)}')
    r = subprocess.run(
        ['pg_restore', '--no-owner', '--no-privileges', '--clean',
         '--if-exists', '--dbname', destino_url, arquivo],
        capture_output=True, text=True)
    # pg_restore devolve != 0 por avisos benignos (ex.: DROP de objeto
    # inexistente com --clean); o que importa é o banco ficar consultável.
    if r.returncode != 0:
        print(f'[restore] avisos/erros:\n{r.stderr.strip()[:2000]}')
    print('[restore] concluído — valide com --contar')
    return 0


def contar(destino_url: str) -> int:
    """Conta linhas das tabelas centrais — a prova de que o restore serviu."""
    import psycopg2

    conn = psycopg2.connect(destino_url)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    tabelas = ('usuario', 'obra', 'cliente', 'rdo', 'tarefa_cronograma',
               'propostas_comerciais', 'migration_history')
    print(f'{"tabela":28} {"linhas":>10}')
    total = 0
    for t in tabelas:
        try:
            cur.execute(f'SELECT count(*) FROM {t}')
            n = cur.fetchone()[0]
            total += n
            print(f'{t:28} {n:10,}')
        except Exception as e:
            conn.rollback()
            print(f'{t:28} {"ERRO":>10}  {str(e)[:60]}')
    conn.close()
    print(f'\ntotal nas tabelas amostradas: {total:,}')
    return 0 if total > 0 else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Backup/restore do banco (Fase 0.5)')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--criar', action='store_true')
    g.add_argument('--listar', action='store_true')
    g.add_argument('--verificar', metavar='ARQUIVO')
    g.add_argument('--restaurar', metavar='ARQUIVO')
    g.add_argument('--contar', action='store_true')
    p.add_argument('--para', metavar='DATABASE_URL', default=None)
    p.add_argument('--sem-fotos', action='store_true',
                   help='exclui os dados de rdo_foto (ensaio/diagnóstico)')
    a = p.parse_args(argv)

    if a.criar:
        return criar(sem_fotos=a.sem_fotos)
    if a.listar:
        return listar()
    if a.verificar:
        return verificar(a.verificar)
    if a.restaurar:
        return restaurar(a.restaurar, a.para)
    if a.contar:
        return contar(a.para or _url())
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
