"""Normalização determinística do cronograma bruto (M04).

Transforma o json_bruto do parser (M03) em json_normalizado validado por
JSON Schema versionado: nomes canônicos, chave estável (uid → wbs → fp),
caminho hierárquico, fingerprint, categoria sugerida por regras e avisos
de inconsistência. Decisão D1 do plano mestre: sem API externa — tudo
determinístico (mesma entrada ⇒ mesma saída, bit a bit).

Módulo PURO: entrada dict, saída dict, zero I/O além da leitura dos
schemas do próprio pacote. Proibido importar models/app/flask/sqlalchemy/
requests — há teste de import-lint garantindo isso.

Plano: docs/superpowers/plans/2026-07-20-modulo-04-implementacao-normalizacao.md
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata

import jsonschema

# Mudou qualquer regra que altere a saída (fórmula do fingerprint,
# normalização de nome, tabela de categorias) ⇒ bump desta versão.
NORMALIZADOR_VERSAO = '1.0'

_AQUI = os.path.dirname(os.path.abspath(__file__))


def _carregar_schema(nome):
    with open(os.path.join(_AQUI, 'schemas', nome), encoding='utf-8') as fh:
        return json.load(fh)


_SCHEMA_BRUTO = _carregar_schema('cronograma_bruto.schema.json')
_SCHEMA_NORMALIZADO = _carregar_schema('cronograma_normalizado.schema.json')

# Limites de sanitização (spec §4): truncar, nunca falhar.
_MAX_NOME = 255
_MAX_NOTAS = 2000

# Control chars C0/C1 + DEL. Em notas preservamos \n e \t (texto legítimo
# de várias linhas); em nomes tudo sai.
_RE_CONTROLE = re.compile(r'[\x00-\x1f\x7f-\x9f]')
_RE_CONTROLE_NOTAS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

# Sufixo de duplicata que o MS Project acrescenta ao colar tarefa: " (2)".
_RE_SUFIXO_DUPLICATA = re.compile(r'\s*\(\d+\)$')

# Tabela de categorias: generalizada de scripts/rebuild_baia_from_0607_mpp.py
# ::etapa_de(), SEM os casos específicos da obra (fazenda/ajr/moledo e as
# regras de "físico-puro" ficam fora — M09 mapeia manualmente). É DADO, não
# if-chain: lista ordenada de (palavras-chave normalizadas, categoria);
# o PRIMEIRO match vence (ex.: 'projetos' classifica PRELIM antes de 'lsf'
# ter chance). Sem match ⇒ None — nunca inventa.
CATEGORIAS = (
    (('hidraulica', 'hidraulico'), 'HIDRO'),
    (('eletrica', 'iluminacao'), 'ELET'),
    (('estudo de solo', 'projetos', 'mobilizacao equipe', 'gabarito'), 'PRELIM'),
    (('portao', 'portoes'), 'PORTAO'),
    (('pintura',), 'PINT'),
    (('plaqueamento', 'basecoat'), 'FECHA'),
    (('lsf',), 'ESTLSF'),
    (('telhado shingle', 'telhado single'), 'COBERT'),
    (('estrutura metalica', 'aco para telhado'), 'ESTMET'),
    (('baldrame', 'broca', 'ferragen', 'concretagem', 'concreto magro',
      'chapas base', 'calcada', 'sapata', 'alvenaria', 'icamento',
      'conduite', 'marcacao dos pilares'), 'FUND'),
)


class NormalizacaoError(Exception):
    """Payload inválido contra o schema (ou saída inválida = bug interno)."""


def _validar(payload, schema, origem):
    """Valida contra o schema; falha vira NormalizacaoError com o path."""
    validador = jsonschema.Draft202012Validator(schema)
    erro = jsonschema.exceptions.best_match(validador.iter_errors(payload))
    if erro is not None:
        raise NormalizacaoError(f'{origem} inválido em {erro.json_path}: {erro.message}')


def normalizar_nome(nome: str) -> str:
    """Nome canônico p/ matching entre versões do cronograma.

    Pipeline (ordem do plano): NFKD sem acento → remove control chars →
    pontuação vira espaço → colapsa espaços → casefold→UPPER → remove
    sufixo de duplicata ' (n)' no fim. Parênteses sobrevivem até o fim
    só para o sufixo ' (2)' ser reconhecível; depois também viram espaço.
    Dígitos significativos são preservados ('BAIA 01' ≠ 'BAIA 02').
    Idempotente: f(f(x)) == f(x).
    """
    s = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode('ascii')
    s = _RE_CONTROLE.sub(' ', s)
    s = re.sub(r'[^A-Za-z0-9\s()]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.casefold().upper()
    s = _RE_SUFIXO_DUPLICATA.sub('', s)
    s = re.sub(r'[()]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def caminho_hierarquico(nome_normalizado: str, caminho_pai: str | None) -> str:
    """'OBRA/FUNDACAO' + 'BROCAS' → 'OBRA/FUNDACAO/BROCAS'; raiz → só o nome.

    '/' é separador seguro: a normalização já trocou toda pontuação por espaço.
    """
    return f'{caminho_pai}/{nome_normalizado}' if caminho_pai else nome_normalizado


def fingerprint(nome_normalizado, caminho_pai=None, dias=None,
                unidade=None, quantidade=None) -> str:
    """sha256 hex[:16] de 'nome_normalizado|caminho_do_pai|dias|unidade|quantidade'.

    Campo ausente entra como '' na fórmula. SEM datas (mudam a cada
    replanejamento — a tarefa continua sendo a mesma) e SEM id/uid (o id
    do MS Project é reordenável, instável por definição). quantidade e
    unidade não existem no bruto do M03 (sempre '') mas ficam na fórmula
    para compatibilidade com o JSON de contingência. Mudar a fórmula ⇒
    bump de NORMALIZADOR_VERSAO.
    """
    def _s(v):
        return '' if v is None else str(v)
    base = '|'.join((nome_normalizado, _s(caminho_pai), _s(dias),
                     _s(unidade), _s(quantidade)))
    return hashlib.sha256(base.encode('utf-8')).hexdigest()[:16]


def classificar(tarefa: dict) -> dict:
    """{is_resumo, is_marco, categoria_sugerida} — flags vêm do parser;
    a categoria sai da tabela CATEGORIAS (primeiro match; sem match ⇒ None)."""
    nome = normalizar_nome(tarefa.get('nome') or '').casefold()
    categoria = None
    for palavras, cod in CATEGORIAS:
        if any(p in nome for p in palavras):
            categoria = cod
            break
    return {'is_resumo': bool(tarefa.get('resumo')),
            'is_marco': bool(tarefa.get('marco')),
            'categoria_sugerida': categoria}


def _aviso(codigo, tarefa_chave, mensagem):
    return {'codigo': codigo, 'tarefa_chave': tarefa_chave, 'mensagem': mensagem}


def _chave(uid, wbs, fp):
    """uid → wbs → fingerprint (spec §12); a mesma regra resolve pai_chave
    e predecessoras[].chave, e é a que o M05 usa na reconciliação."""
    if uid is not None:
        return f'uid:{uid}'
    if wbs:
        return f'wbs:{wbs}'
    return f'fp:{fp}'


def _sanear_nome(nome):
    return _RE_CONTROLE.sub('', nome or '').strip()[:_MAX_NOME]


def _sanear_notas(notas):
    if notas is None:
        return None
    return _RE_CONTROLE_NOTAS.sub('', notas)[:_MAX_NOTAS]


def detectar_inconsistencias(tarefas: list[dict]) -> list[dict]:
    """Avisos determinísticos sobre as tarefas JÁ normalizadas.

    (predecessora_inexistente é a exceção: emitido durante a montagem,
    porque o vínculo não-resolvido nem chega ao normalizado.)
    Nunca bloqueia: aviso é insumo de revisão humana no M05/M08.
    """
    avisos = []
    for i, t in enumerate(tarefas):
        ch = t['chave']
        if t['inicio'] and t['fim'] and t['fim'] < t['inicio']:
            avisos.append(_aviso('fim_antes_inicio', ch,
                                 f"fim {t['fim']} antes do início {t['inicio']}"))
        if not t['is_resumo'] and (t['inicio'] is None or t['fim'] is None):
            avisos.append(_aviso('folha_sem_datas', ch,
                                 f"folha '{t['nome_normalizado']}' sem data de início/fim"))
        if (t['dias'] == 0 and not t['is_marco'] and not t['is_resumo']):
            avisos.append(_aviso('duracao_zero_sem_marco', ch,
                                 f"'{t['nome_normalizado']}' tem duração 0 mas não é marco"))
        # nivel preserva o outline do arquivo: salto N → N+2 indica
        # estrutura quebrada no Project (pai já foi pendurado no último
        # nível menor durante a montagem).
        if i > 0 and t['nivel'] > tarefas[i - 1]['nivel'] + 1:
            avisos.append(_aviso('outline_salto', ch,
                                 f"outline saltou de {tarefas[i - 1]['nivel']} "
                                 f"para {t['nivel']}"))

    avisos.extend(_detectar_ciclos(tarefas))
    avisos.extend(_detectar_duplicados(tarefas))

    n_pct = sum(1 for t in tarefas if (t['pct_project'] or 0) > 0)
    if n_pct:
        avisos.append(_aviso(
            'pct_project_sera_ignorado', None,
            f'{n_pct} tarefa(s) com percentual no Project — o avanço físico '
            f'vem do RDO; pct_project será ignorado'))
    return avisos


def _detectar_ciclos(tarefas):
    """DFS iterativa com cores no grafo tarefa → predecessoras.

    Ordem de visita = ordem do arquivo (e predecessoras na ordem da lista),
    então o conjunto de avisos é determinístico. Um aviso por aresta de
    retorno (vínculo que fecha o ciclo).
    """
    grafo = {t['chave']: [p['chave'] for p in t['predecessoras']] for t in tarefas}
    avisos = []
    cor = {}  # ausente=branco, 1=cinza (na pilha), 2=preto (fechado)
    for raiz in grafo:
        if raiz in cor:
            continue
        cor[raiz] = 1
        pilha = [(raiz, iter(grafo[raiz]))]
        while pilha:
            u, vizinhos = pilha[-1]
            for v in vizinhos:
                if cor.get(v) == 1:
                    avisos.append(_aviso(
                        'ciclo_predecessoras', u,
                        f'vínculo {u} → {v} fecha um ciclo de predecessoras'))
                elif v not in cor and v in grafo:
                    cor[v] = 1
                    pilha.append((v, iter(grafo[v])))
                    break
            else:
                cor[u] = 2
                pilha.pop()
    return avisos


def _detectar_duplicados(tarefas):
    """Nomes iguais sob o mesmo pai.

    Se além do nome o fingerprint também colide (mesma duração etc.), o
    caso sobe para 'ambiguidade_potencial' — o M05 não terá NENHUM sinal
    para distinguir as tarefas e a resolução é manual (nunca merge
    silencioso). Caso contrário fica 'nomes_duplicados_mesmo_pai'.
    """
    grupos = {}
    for t in tarefas:
        grupos.setdefault((t['pai_chave'], t['nome_normalizado']), []).append(t)

    avisos = []
    for (_, nome), grupo in grupos.items():  # ordem de inserção: determinística
        if len(grupo) < 2:
            continue
        por_fp = {}
        for t in grupo:
            por_fp.setdefault(t['fingerprint'], []).append(t)
        colisoes = [ts for ts in por_fp.values() if len(ts) > 1]
        if colisoes:
            for ts in colisoes:
                chaves = ', '.join(t['chave'] for t in ts)
                avisos.append(_aviso(
                    'ambiguidade_potencial', ts[0]['chave'],
                    f"{len(ts)} tarefas '{nome}' sob o mesmo pai com o MESMO "
                    f'fingerprint ({chaves}) — indistinguíveis, revisar no M05'))
        else:
            chaves = ', '.join(t['chave'] for t in grupo)
            avisos.append(_aviso(
                'nomes_duplicados_mesmo_pai', grupo[0]['chave'],
                f"{len(grupo)} tarefas '{nome}' sob o mesmo pai ({chaves})"))
    return avisos


def normalizar(json_bruto: dict) -> dict:
    """Pipeline completo bruto → normalizado (contrato do M05).

    1. Valida a ENTRADA contra cronograma_bruto.schema.json.
    2. Monta as tarefas na ordem do arquivo: pai derivado por pilha de
       outline (o bruto não tem ponteiro de pai), nome canônico, caminho,
       fingerprint, chave, categoria.
    3. Resolve predecessoras pela chave da tarefa-alvo (uid, senão id);
       vínculo sem alvo é descartado com aviso.
    4. Detecta inconsistências e calcula contadores.
    5. Valida a PRÓPRIA SAÍDA contra cronograma_normalizado.schema.json —
       falha aqui é bug interno, não erro do usuário.
    """
    _validar(json_bruto, _SCHEMA_BRUTO, 'json_bruto')

    brutas = json_bruto['tarefas']
    tarefas = []
    avisos_montagem = []
    pilha = []            # [(outline, chave, caminho)] — ancestrais da atual
    por_uid, por_id = {}, {}

    for ordem, bt in enumerate(brutas):
        outline = bt['outline'] if bt['outline'] is not None else 0
        # pai = última tarefa vista com outline menor (cobre também o
        # salto N → N+2: pendura no último nível menor disponível).
        while pilha and pilha[-1][0] >= outline:
            pilha.pop()
        pai = pilha[-1] if pilha else None
        caminho_pai = pai[2] if pai else None

        nome_original = _sanear_nome(bt['nome'])
        nome_norm = normalizar_nome(nome_original)[:_MAX_NOME]
        fp = fingerprint(nome_norm, caminho_pai, bt['dias'])
        chave = _chave(bt['uid'], bt['wbs'], fp)
        cls = classificar(bt)

        tarefa = {
            'chave': chave,
            'uid': bt['uid'],
            'wbs': bt['wbs'],
            'id_arquivo': bt['id'],
            'nome_original': nome_original,
            'nome_normalizado': nome_norm,
            'caminho': caminho_hierarquico(nome_norm, caminho_pai),
            'fingerprint': fp,
            'nivel': outline,
            'pai_chave': pai[1] if pai else None,
            'ordem': ordem,
            'inicio': bt['inicio'],
            'fim': bt['fim'],
            'dias': bt['dias'],
            'is_resumo': cls['is_resumo'],
            'is_marco': cls['is_marco'],
            'categoria_sugerida': cls['categoria_sugerida'],
            'predecessoras': [],   # resolvidas na 2ª passada (podem apontar à frente)
            'quantidade_total': None,  # não existem no bruto do M03 — nunca inventa
            'unidade': None,
            'pct_project': bt['pct_project'],
            'notas': _sanear_notas(bt['notas']),
        }
        tarefas.append(tarefa)
        pilha.append((outline, chave, tarefa['caminho']))
        if bt['uid'] is not None:
            por_uid.setdefault(bt['uid'], tarefa)
        por_id.setdefault(bt['id'], tarefa)

    # 2ª passada: predecessoras — alvo por uid (identidade forte do MSPDI),
    # com fallback por id (JSON de contingência pode não ter uid).
    for bt, tarefa in zip(brutas, tarefas):
        for pred in bt['predecessoras']:
            alvo = por_uid.get(pred['uid']) if pred['uid'] is not None else None
            if alvo is None:
                alvo = por_id.get(pred['id'])
            if alvo is None:
                avisos_montagem.append(_aviso(
                    'predecessora_inexistente', tarefa['chave'],
                    f"predecessora id={pred['id']} uid={pred['uid']} "
                    f'não existe no arquivo — vínculo descartado'))
                continue
            tarefa['predecessoras'].append({
                'chave': alvo['chave'],
                'tipo': pred['tipo'],
                'lag_dias': pred['lag_dias'],
            })

    avisos = avisos_montagem + detectar_inconsistencias(tarefas)

    n_avisos = {}
    for a in avisos:
        n_avisos[a['codigo']] = n_avisos.get(a['codigo'], 0) + 1

    saida = {
        'versao': NORMALIZADOR_VERSAO,
        'projeto': {
            'nome': (_sanear_nome(json_bruto['projeto']['nome'])
                     if json_bruto['projeto']['nome'] is not None else None),
            'data_status': json_bruto['projeto']['data_status'],
        },
        'tarefas': tarefas,
        'avisos': avisos,
        'contadores': {
            'n_tarefas': len(tarefas),
            'n_folhas': sum(1 for t in tarefas if not t['is_resumo']),
            'n_avisos': {k: n_avisos[k] for k in sorted(n_avisos)},
        },
    }
    _validar(saida, _SCHEMA_NORMALIZADO,
             'json_normalizado (bug interno do normalizador)')
    return saida
