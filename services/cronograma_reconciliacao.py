"""Reconciliação determinística do cronograma (M05, Task 1).

Compara as tarefas VIVAS de uma obra com o ``json_normalizado`` do M04 e
produz um ``RelatorioDiff`` (dict puro) classificando cada diferença por
uma cascata determinística de matching. NÃO decide nada: ambíguos e
split/merge são apenas SUGESTÕES — a aplicação (Task 2/4) exige decisão
manual registrada.

Módulo PURO: entrada dict/list, saída dict, zero I/O e zero acesso a
banco/ORM. Proibido importar models/app/flask/sqlalchemy/db — há teste de
import-lint garantindo isso. Único import de projeto permitido é
``services.cronograma_normalizacao`` (outro módulo puro), usado só se for
preciso re-normalizar nomes; hoje o chamador já entrega tudo normalizado.

Determinismo (mesma entrada ⇒ mesma saída, bit a bit): nenhum ``set`` é
iterado sem ``sorted`` na saída; as tarefas atuais são varridas em ordem
de ``id`` crescente; empates de score caem para a menor ordem de arquivo.

Plano: docs/superpowers/plans/2026-07-20-modulo-05-implementacao-reconciliacao.md
Contrato RelatorioDiff e cascata §4.1: em conflito, o plano bite-sized vence.
"""
from __future__ import annotations

import difflib
from collections import Counter
from typing import Any, Optional, TypedDict

# Bump quando qualquer regra que altere a saída mudar (fórmula do score,
# limiares, formato do RelatorioDiff).
RECONCILIADOR_VERSAO = '1.0'

# Limiares do nível 6 (score composto). Ver docstring de ``_score``.
SCORE_MATCH = 0.85    # >= e único ⇒ correspondência provável
SCORE_AMBIGUO = 0.60  # [AMBIGUO, MATCH) ⇒ ambígua (decisão manual)


class TarefaAtual(TypedDict, total=False):
    """Shape de cada item de ``tarefas_atuais`` (o chamador extrai do banco).

    O serviço é PURO: quem chama lê ``TarefaCronograma`` VIVAS da obra
    (``ativa=True``) e monta estes dicts — o serviço nunca toca no ORM.

    Campos:
      id: PK da TarefaCronograma (int, obrigatório e único).
      mpp_uid: uid do MS Project (BigInt) ou None. uid 0 é válido.
      wbs_codigo: código WBS (str) ou None/'' (vazio = ausente).
      nome_normalizado: nome já passado por ``normalizar_nome`` (o chamador
        normaliza — o serviço compara como está).
      caminho: caminho hierárquico normalizado ('PAI/FILHO/...').
      fingerprint: fingerprint do M04 (str) ou None.
      tarefa_pai_id: id (desta mesma lista) da tarefa-pai, ou None (raiz).
      data_inicio / data_fim: date, datetime ou str ISO 'YYYY-MM-DD', ou None.
      duracao_dias: número (int/float) ou None.
      quantidade_total: número ou None.
      unidade_medida: str ou None.
      predecessoras: lista de ids (desta mesma lista) das predecessoras.
    """
    id: int
    mpp_uid: Optional[int]
    wbs_codigo: Optional[str]
    nome_normalizado: str
    caminho: str
    fingerprint: Optional[str]
    tarefa_pai_id: Optional[int]
    data_inicio: Any
    data_fim: Any
    duracao_dias: Any
    quantidade_total: Any
    unidade_medida: Optional[str]
    predecessoras: list


# ---------------------------------------------------------------------------
# Helpers de comparação (tolerantes a date/datetime/str/None)
# ---------------------------------------------------------------------------

def _iso(valor) -> Optional[str]:
    """Normaliza data para 'YYYY-MM-DD' comparável. None fica None.

    Aceita date/datetime (via ``isoformat``) ou string ISO já pronta; nunca
    importa datetime (duck-typing) para manter o módulo mínimo.
    """
    if valor is None:
        return None
    if hasattr(valor, 'isoformat'):
        return valor.isoformat()[:10]
    return str(valor)[:10]


def _num_igual(a, b) -> bool:
    """Igualdade numérica None-safe (18 == 18.0; None só == None)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= 1e-9


def _tokens(nome: str) -> frozenset:
    return frozenset((nome or '').split())


def _pred_set_atual(a: dict, id_para_chave: dict) -> frozenset:
    """Predecessoras da tarefa atual traduzidas para chaves do lado novo.

    Ids que não casaram (predecessora removida) somem do conjunto — o
    vínculo de fato mudou, então isso conta como diferença.
    """
    return frozenset(
        id_para_chave[p] for p in (a.get('predecessoras') or []) if p in id_para_chave)


def _pred_set_novo(n: dict) -> frozenset:
    return frozenset(p['chave'] for p in (n.get('predecessoras') or []))


# ---------------------------------------------------------------------------
# Score composto (nível 6)
# ---------------------------------------------------------------------------

def _mesmo_pai(a: dict, n: dict, id_para_chave: dict) -> bool:
    """True se o pai da atual (traduzido) coincide com o pai_chave do novo.

    Duas raízes (ambos os pais None) contam como mesmo pai. Pai atual não
    casado ⇒ traduz para None (pode falsear igualdade só quando o novo
    também é raiz — impacto de 0.2 num caso de borda, documentado).
    """
    pai_id = a.get('tarefa_pai_id')
    a_pai_chave = id_para_chave.get(pai_id) if pai_id is not None else None
    return a_pai_chave == n.get('pai_chave')


def _datas_sobrepoem(a: dict, n: dict) -> bool:
    ai, af = _iso(a.get('data_inicio')), _iso(a.get('data_fim'))
    ni, nf = _iso(n.get('inicio')), _iso(n.get('fim'))
    if None in (ai, af, ni, nf):
        return False
    return ai <= nf and ni <= af


def _duracao_proxima(a: dict, n: dict) -> bool:
    da, db = a.get('duracao_dias'), n.get('dias')
    if da is None or db is None:
        return False
    return abs(float(da) - float(db)) <= 1


def _score(a: dict, n: dict, id_para_chave: dict) -> float:
    """Score composto determinístico ∈ [0, 1] (§4.1):

    ``0.5*difflib.ratio(nome_a, nome_b) + 0.2*(mesmo pai) +
      0.15*(sobreposição de datas>0) + 0.1*(|dur_a-dur_b|<=1) +
      0.05*(mesmas predecessoras como conjunto)``.

    O mapa id→chave usado nos sinais de pai/predecessora é o dos níveis
    1-5 (congelado antes do nível 6), para o resultado não depender da
    ordem em que os pares de score são fechados.
    """
    ratio = difflib.SequenceMatcher(
        None, a['nome_normalizado'], n['nome_normalizado']).ratio()
    mesmas_pred = _pred_set_atual(a, id_para_chave) == _pred_set_novo(n)
    return (0.5 * ratio
            + 0.2 * _mesmo_pai(a, n, id_para_chave)
            + 0.15 * _datas_sobrepoem(a, n)
            + 0.1 * _duracao_proxima(a, n)
            + 0.05 * mesmas_pred)


# ---------------------------------------------------------------------------
# Matching por chave (níveis 1-3 e 5) e por nome único (nível 4)
# ---------------------------------------------------------------------------

def _match_por_chave(atuais, novos, a_cas, n_cas, chave_atual, chave_novo, nivel):
    """Casa não-casados dos dois lados por uma chave exata (primeiro vence).

    ``atuais`` já vem ordenada por id; para uma chave com vários candidatos
    do lado novo, vence a menor ordem de arquivo (lista consumida por
    ``pop(0)``). Chave ``None`` nunca casa (uid 0 é válido, '' vira None no
    extractor da chave).
    """
    por_chave: dict = {}
    for j, n in enumerate(novos):
        if j in n_cas:
            continue
        k = chave_novo(n)
        if k is None:
            continue
        por_chave.setdefault(k, []).append(j)
    pares = []
    for i, a in enumerate(atuais):
        if i in a_cas:
            continue
        k = chave_atual(a)
        if k is None:
            continue
        candidatos = por_chave.get(k)
        if not candidatos:
            continue
        j = candidatos.pop(0)
        a_cas.add(i)
        n_cas.add(j)
        pares.append((i, j, nivel))
    return pares


def _match_nome_unico(atuais, novos, a_cas, n_cas):
    """Nível 4: nome_normalizado que é ÚNICO entre os NÃO-casados dos dois
    lados. Nome que se repete em qualquer lado é pulado (cai para 5/6)."""
    cont_a = Counter(a['nome_normalizado']
                     for i, a in enumerate(atuais) if i not in a_cas)
    cont_n = Counter(n['nome_normalizado']
                     for j, n in enumerate(novos) if j not in n_cas)
    novo_por_nome = {}
    for j, n in enumerate(novos):
        if j in n_cas:
            continue
        nome = n['nome_normalizado']
        if cont_a[nome] == 1 and cont_n[nome] == 1:
            novo_por_nome[nome] = j
    pares = []
    for i, a in enumerate(atuais):
        if i in a_cas:
            continue
        nome = a['nome_normalizado']
        if cont_a[nome] == 1 and cont_n[nome] == 1 and nome in novo_por_nome:
            j = novo_por_nome[nome]
            a_cas.add(i)
            n_cas.add(j)
            pares.append((i, j, 'nome_unico'))
    return pares


# ---------------------------------------------------------------------------
# Classificação cumulativa de um par casado
# ---------------------------------------------------------------------------

def _classificar_par(a: dict, n: dict, id_para_chave: dict):
    """Tipo (LISTA) e detalhes de/para de um par casado (níveis 1-6).

    Base: 'exata' (nome igual) ou 'renomeada' (nome difere — só possível
    nos níveis 1-3/5/6; o nível 4 casa por nome idêntico). Acrescenta
    cumulativamente movida_hierarquia / datas_alteradas / duracao_alterada
    / predecessoras_alteradas / quantidade_alterada / unidade_alterada.
    """
    tipo = []
    detalhes: dict = {}

    if a['nome_normalizado'] == n['nome_normalizado']:
        tipo.append('exata')
    else:
        tipo.append('renomeada')
        detalhes['nome_de'] = a['nome_normalizado']
        detalhes['nome_para'] = n['nome_normalizado']

    pai_id = a.get('tarefa_pai_id')
    a_pai_chave = id_para_chave.get(pai_id) if pai_id is not None else None
    if a_pai_chave != n.get('pai_chave'):
        tipo.append('movida_hierarquia')
        detalhes['pai_de'] = a_pai_chave
        detalhes['pai_para'] = n.get('pai_chave')

    datas_de = [_iso(a.get('data_inicio')), _iso(a.get('data_fim'))]
    datas_para = [_iso(n.get('inicio')), _iso(n.get('fim'))]
    if datas_de != datas_para:
        tipo.append('datas_alteradas')
        detalhes['datas_de'] = datas_de
        detalhes['datas_para'] = datas_para

    if not _num_igual(a.get('duracao_dias'), n.get('dias')):
        tipo.append('duracao_alterada')
        detalhes['duracao_de'] = a.get('duracao_dias')
        detalhes['duracao_para'] = n.get('dias')

    pred_de = _pred_set_atual(a, id_para_chave)
    pred_para = _pred_set_novo(n)
    if pred_de != pred_para:
        tipo.append('predecessoras_alteradas')
        detalhes['predecessoras_de'] = sorted(pred_de)
        detalhes['predecessoras_para'] = sorted(pred_para)

    if not _num_igual(a.get('quantidade_total'), n.get('quantidade_total')):
        tipo.append('quantidade_alterada')
        detalhes['quantidade_de'] = a.get('quantidade_total')
        detalhes['quantidade_para'] = n.get('quantidade_total')

    if (a.get('unidade_medida') or None) != (n.get('unidade') or None):
        tipo.append('unidade_alterada')
        detalhes['unidade_de'] = a.get('unidade_medida')
        detalhes['unidade_para'] = n.get('unidade')

    return tipo, detalhes


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def reconciliar(tarefas_atuais: list, normalizado: dict) -> dict:
    """Compara tarefas VIVAS com o json_normalizado ⇒ RelatorioDiff (dict).

    ``tarefas_atuais``: lista de dicts no shape de ``TarefaAtual``.
    ``normalizado``: saída do M04 (``services.cronograma_normalizacao``),
    com chave 'tarefas' — cada tarefa tem chave/uid/wbs/nome_normalizado/
    caminho/fingerprint/pai_chave/inicio/fim/dias/quantidade_total/unidade/
    predecessoras[{chave,tipo,lag_dias}]/ordem.

    Devolve ``{versao, resumo, mapeamentos, sugestoes_split_merge}`` (ver
    "Contrato RelatorioDiff" no plano). Puro e determinístico.
    """
    # Ordem estável de varredura: id crescente (None por último, defensivo).
    atuais = sorted(tarefas_atuais, key=lambda a: (a.get('id') is None, a.get('id')))
    novos = list(normalizado.get('tarefas') or [])

    a_cas: set = set()  # índices (em `atuais`) já casados/resolvidos
    n_cas: set = set()  # índices (em `novos`) já casados

    # Níveis 1-3: chave exata.
    casados = []
    casados += _match_por_chave(
        atuais, novos, a_cas, n_cas,
        lambda a: a.get('mpp_uid'), lambda n: n.get('uid'), 'mpp_uid')
    casados += _match_por_chave(
        atuais, novos, a_cas, n_cas,
        lambda a: a.get('wbs_codigo') or None, lambda n: n.get('wbs') or None, 'wbs')
    casados += _match_por_chave(
        atuais, novos, a_cas, n_cas,
        lambda a: a.get('caminho') or None, lambda n: n.get('caminho') or None, 'caminho')
    # Nível 4: nome único.
    casados += _match_nome_unico(atuais, novos, a_cas, n_cas)
    # Nível 5: fingerprint.
    casados += _match_por_chave(
        atuais, novos, a_cas, n_cas,
        lambda a: a.get('fingerprint') or None,
        lambda n: n.get('fingerprint') or None, 'fingerprint')

    # Mapa id→chave dos níveis 1-5 (congelado para o score do nível 6).
    mapa_1a5 = {atuais[i]['id']: novos[j]['chave'] for i, j, _ in casados}

    # Nível 6: score composto. Varre atuais restantes em ordem de id.
    score_matches = []   # (i, j, score)
    ambiguas = []        # (i, [(score, j), ...])
    for i, a in enumerate(atuais):
        if i in a_cas:
            continue
        candidatos = [(_score(a, novos[j], mapa_1a5), j)
                      for j in range(len(novos)) if j not in n_cas]
        if not candidatos:
            continue
        candidatos.sort(key=lambda t: (-t[0], t[1]))  # empate: menor ordem de arquivo
        altos = [c for c in candidatos if c[0] >= SCORE_MATCH]
        melhor = candidatos[0]
        if len(altos) == 1:
            s, j = altos[0]
            a_cas.add(i)
            n_cas.add(j)
            score_matches.append((i, j, s))
        elif len(altos) >= 2:
            a_cas.add(i)
            ambiguas.append((i, altos))
        elif SCORE_AMBIGUO <= melhor[0] < SCORE_MATCH:
            a_cas.add(i)
            meio = [c for c in candidatos if c[0] >= SCORE_AMBIGUO]
            ambiguas.append((i, meio))
        # senão: fica não-casado ⇒ removida/revisao_manual no fecho.

    matched = list(casados) + [(i, j, 'score') for i, j, _ in score_matches]
    score_por_i = {i: s for i, j, s in score_matches}
    id_para_chave = {atuais[i]['id']: novos[j]['chave'] for i, j, _ in matched}

    removidas_idx = [i for i in range(len(atuais)) if i not in a_cas]
    novas_idx = [j for j in range(len(novos)) if j not in n_cas]

    # -- Split/merge (só sugestão; decisão sempre manual na Task 2/4) --------
    sugestoes = []
    dividida_antiga: set = set()
    dividida_nova: set = set()
    fundida_antiga: set = set()
    fundida_nova: set = set()

    def _pai_esperado(a):
        pai_id = a.get('tarefa_pai_id')
        return id_para_chave.get(pai_id) if pai_id is not None else None

    # Divisão: 1 removida cujo nome é subconjunto próprio de tokens de >=2
    # novas irmãs sob o pai onde a antiga estava.
    for i in removidas_idx:
        a = atuais[i]
        a_tok = _tokens(a['nome_normalizado'])
        if not a_tok:
            continue
        pai = _pai_esperado(a)
        filhas = [j for j in novas_idx
                  if novos[j].get('pai_chave') == pai
                  and _tokens(novos[j]['nome_normalizado']) > a_tok]
        if len(filhas) >= 2:
            sugestoes.append({'tipo': 'dividida', 'antiga_id': a['id'],
                              'novas_chaves': sorted(novos[j]['chave'] for j in filhas)})
            dividida_antiga.add(i)
            dividida_nova.update(filhas)

    # Fusão (espelho): >=2 removidas cujos nomes são subconjunto próprio de 1
    # nova, sob o mesmo pai. Nunca reusa envolvidas numa divisão.
    for j in novas_idx:
        if j in dividida_nova:
            continue
        n = novos[j]
        n_tok = _tokens(n['nome_normalizado'])
        if not n_tok:
            continue
        antigas = [i for i in removidas_idx
                   if i not in dividida_antiga
                   and _pai_esperado(atuais[i]) == n.get('pai_chave')
                   and _tokens(atuais[i]['nome_normalizado']) < n_tok]
        if len(antigas) >= 2:
            sugestoes.append({'tipo': 'fundida', 'nova_chave': n['chave'],
                              'antigas_ids': sorted(atuais[i]['id'] for i in antigas)})
            fundida_nova.add(j)
            fundida_antiga.update(antigas)

    sugestoes.sort(key=lambda s: (s['tipo'], s.get('antiga_id') or 0,
                                  s.get('nova_chave') or ''))

    # Nomes colididos (repetidos em qualquer lado): uma removida assim não
    # some silenciosa como 'removida' — vira 'revisao_manual' (decisão manual).
    cont_nome_a = Counter(a['nome_normalizado'] for a in atuais)
    cont_nome_n = Counter(n['nome_normalizado'] for n in novos)

    def _colide(nome):
        return cont_nome_a[nome] > 1 or cont_nome_n[nome] > 1

    # -- Montagem dos mapeamentos --------------------------------------------
    # Cada entrada carrega uma chave de ordenação privada '_sort':
    #   ('a', ordem_do_novo) para os que têm lado novo (casados/novas);
    #   ('b', id_atual)      para os só-atual (ambigua/removida/etc).
    entradas = []

    for i, j, nivel in matched:
        a, n = atuais[i], novos[j]
        tipo, detalhes = _classificar_par(a, n, id_para_chave)
        entradas.append((('a', j), {
            'tarefa_atual_id': a['id'], 'chave_nova': n['chave'],
            'nivel_match': nivel,
            'score': round(score_por_i[i], 6) if i in score_por_i else None,
            'decisao_requerida': False, 'candidatos': [],
            'tipo': tipo, 'detalhes': detalhes}))

    for j in novas_idx:
        n = novos[j]
        entradas.append((('a', j), {
            'tarefa_atual_id': None, 'chave_nova': n['chave'],
            'nivel_match': 'none', 'score': None,
            'decisao_requerida': j in dividida_nova or j in fundida_nova,
            'candidatos': [], 'tipo': ['nova'],
            'detalhes': {'nome_para': n['nome_normalizado']}}))

    for i, cands in ambiguas:
        a = atuais[i]
        entradas.append((('b', a['id']), {
            'tarefa_atual_id': a['id'], 'chave_nova': None,
            'nivel_match': 'score', 'score': round(cands[0][0], 6),
            'decisao_requerida': True,
            'candidatos': [{'chave_nova': novos[j]['chave'], 'score': round(s, 6)}
                           for s, j in cands],
            'tipo': ['ambigua'], 'detalhes': {'nome_de': a['nome_normalizado']}}))

    for i in removidas_idx:
        a = atuais[i]
        if i in dividida_antiga:
            tipo, dr = ['dividida'], True
        elif i in fundida_antiga:
            tipo, dr = ['fundida'], True
        elif _colide(a['nome_normalizado']):
            tipo, dr = ['revisao_manual'], True
        else:
            tipo, dr = ['removida'], False
        entradas.append((('b', a['id']), {
            'tarefa_atual_id': a['id'], 'chave_nova': None,
            'nivel_match': 'none', 'score': None, 'decisao_requerida': dr,
            'candidatos': [], 'tipo': tipo,
            'detalhes': {'nome_de': a['nome_normalizado']}}))

    entradas.sort(key=lambda e: e[0])
    mapeamentos = []
    for id_temp, (_, m) in enumerate(entradas):
        mapeamentos.append({'id_temp': id_temp, **m})

    # -- Resumo (derivado dos mapeamentos ⇒ sempre bate com a contagem) ------
    def _contar(rotulo):
        return sum(1 for m in mapeamentos if rotulo in m['tipo'])

    resumo = {
        'exatas': _contar('exata'),
        'renomeadas': _contar('renomeada'),
        'novas': _contar('nova'),
        'removidas': _contar('removida'),
        'ambiguas': _contar('ambigua'),
        'revisao_manual': _contar('revisao_manual'),
        'alteracoes': {
            'datas': _contar('datas_alteradas'),
            'duracao': _contar('duracao_alterada'),
            'predecessoras': _contar('predecessoras_alteradas'),
        },
    }

    return {
        'versao': RECONCILIADOR_VERSAO,
        'resumo': resumo,
        'mapeamentos': mapeamentos,
        'sugestoes_split_merge': sugestoes,
    }
