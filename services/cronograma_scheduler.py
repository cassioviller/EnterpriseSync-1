"""Motor de agendamento do cronograma editável — Fase 1 (`cronograma_editor_v2`).

Motor PURO (sem DB) + camada fina de persistência. Implementa o passe para
frente com vínculos tipados TI/II/TT/IT + lag em dias úteis, âncoras de
tarefa iniciada, roll-up de pais e o passe para trás (folga total / caminho
crítico). Substitui, atrás da flag `cronograma_editor_v2`, o motor antigo
`utils/cronograma_engine.recalcular_cronograma` (FS simples, predecessora
única) — que permanece intocado para tenants com a flag desligada.

CALENDÁRIO: fixo segunda–sexta nesta fase. `CalendarioEmpresa`
(considerar_sabado/considerar_domingo) é DELIBERADAMENTE ignorado — decisão
da spec `docs/superpowers/specs/2026-07-24-cronograma-editavel-design.md`;
o suporte a calendário do tenant é fase futura. Consequência documentada:
num tenant com sábado útil, o 1º recálculo com a flag ligada pode deslocar
datas calculadas pelo motor antigo (o script de flag avisa).

Vocabulário dos vínculos (pt-BR do MS Project):
  TI (término→início, FS) · II (início→início, SS) ·
  TT (término→término, FF) · IT (início→término, SF).

Estrutura do módulo:
  * B1 — matemática de dias úteis (funções puras);
  * B2 — dataclasses `NoTarefa`/`VinculoSpec`, grafo, ciclo, ordem topológica;
  * B4/B5 — `calcular_agendamento` (passe p/ frente + roll-up + folga), puro;
  * B3/B6 — predicado de âncora e persistência (`recalcular_obra`,
    `sincronizar_vinculos_de_predecessora_id`) — únicos pontos que tocam DB
    (imports de models são tardios, dentro das funções: o módulo importa
    limpo em testes unitários sem app/DB).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

logger = logging.getLogger(__name__)

TIPOS_VINCULO = ('TI', 'II', 'TT', 'IT')


# ─────────────────────────────────────────────────────────────────────────────
# B1 — Matemática de dias úteis (seg–sex fixo; funções puras)
# ─────────────────────────────────────────────────────────────────────────────

def eh_dia_util(d: date) -> bool:
    """Segunda a sexta. Calendário fixo da Fase 1 (ver docstring do módulo)."""
    return d.weekday() < 5


def proximo_dia_util(d: date) -> date:
    """O próprio `d` se for útil; senão rola PARA FRENTE até o próximo útil.

    Atenção: semântica diferente do homônimo em `utils/cronograma_engine`
    (que devolve o útil estritamente APÓS `d`).
    """
    while not eh_dia_util(d):
        d += timedelta(days=1)
    return d


def dia_util_anterior(d: date) -> date:
    """O próprio `d` se for útil; senão rola PARA TRÁS até o útil anterior."""
    while not eh_dia_util(d):
        d -= timedelta(days=1)
    return d


def somar_dias_uteis(d: date, n: int) -> date:
    """Anda `n` dias úteis a partir de `d` (n>0 p/ frente, n<0 p/ trás).

    n=0 apenas normaliza: `proximo_dia_util(d)` (sábado → segunda).
    Cada passo pousa num dia útil: somar_dias_uteis(sexta, 1) = segunda.
    """
    if n == 0:
        return proximo_dia_util(d)
    passo = 1 if n > 0 else -1
    restantes = abs(n)
    while restantes > 0:
        d += timedelta(days=passo)
        if eh_dia_util(d):
            restantes -= 1
    return d


def fim_por_duracao(inicio: date, duracao: int) -> date:
    """Data de fim de uma tarefa que começa em `inicio` e dura `duracao`
    dias úteis (inclusivos). Marco/duração 0 → o próprio `inicio`."""
    if duracao <= 0:
        return inicio
    return somar_dias_uteis(inicio, duracao - 1)


def duracao_util_entre(inicio: date, fim: date) -> int:
    """Nº de dias úteis entre `inicio` e `fim`, inclusivo nos dois extremos.
    `fim < inicio` → 0."""
    total = 0
    d = inicio
    while d <= fim:
        if eh_dia_util(d):
            total += 1
        d += timedelta(days=1)
    return total


# ─────────────────────────────────────────────────────────────────────────────
# B2 — Estruturas, grafo, ciclo e ordem topológica
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NoTarefa:
    """Projeção pura de `TarefaCronograma` — o motor nunca vê o modelo."""
    id: int
    nome: str
    duracao: int
    inicio: date | None = None
    fim: date | None = None
    pai_id: int | None = None
    is_marco: bool = False
    ancorada: bool = False


@dataclass
class VinculoSpec:
    """Projeção pura de `TarefaVinculo`. `lag` em dias úteis (pode ser <0)."""
    predecessora_id: int
    sucessora_id: int
    tipo: str = 'TI'
    lag: int = 0


@dataclass
class ResultadoTarefa:
    """Saída do motor para UMA tarefa (folha ou pai)."""
    inicio: date | None
    fim: date | None
    duracao: int
    folga_dias: int | None = None
    is_critica: bool = False


@dataclass
class ResultadoAgendamento:
    """Saída de `recalcular_obra`. `tarefas_afetadas` traz SÓ as
    `TarefaCronograma` cujos campos data_inicio/data_fim/duracao_dias/
    folga_dias/is_critica realmente mudaram — já persistidas."""
    tarefas_afetadas: list = field(default_factory=list)
    total_tarefas: int = 0


class ErroCiclo(ValueError):
    """Vínculos formam referência circular. Mensagem em português com os
    NOMES das tarefas e o caminho do ciclo, pronta para a UI, ex.:

        Vínculo inválido: "Alvenaria" já depende de "Reboco"
        (ciclo: Alvenaria → Reboco → Alvenaria).
    """

    def __init__(self, mensagem: str, ciclo: list[int] | None = None):
        super().__init__(mensagem)
        self.ciclo = ciclo or []


def montar_grafo(nos: list[NoTarefa], vinculos: list[VinculoSpec]) -> dict[int, list[VinculoSpec]]:
    """Adjacência de saída: predecessora_id → vínculos que partem dela.

    Vínculo cuja ponta (qualquer uma) não está em `nos` é IGNORADO com
    warning — cobre o dado sujo real de `predecessora_id` cruzando obra e
    vínculos apontando para pais/resumo (validação dura fica no Step C).
    """
    ids = {n.id for n in nos}
    sucessores: dict[int, list[VinculoSpec]] = {n.id: [] for n in nos}
    for v in vinculos:
        if v.predecessora_id not in ids:
            logger.warning(
                '[scheduler] vínculo %s→%s ignorado: predecessora %s fora do '
                'conjunto de tarefas-folha consideradas',
                v.predecessora_id, v.sucessora_id, v.predecessora_id)
            continue
        if v.sucessora_id not in ids:
            logger.warning(
                '[scheduler] vínculo %s→%s ignorado: sucessora %s fora do '
                'conjunto de tarefas-folha consideradas',
                v.predecessora_id, v.sucessora_id, v.sucessora_id)
            continue
        if v.tipo not in TIPOS_VINCULO:
            logger.warning(
                "[scheduler] vínculo %s→%s ignorado: tipo inválido '%s'",
                v.predecessora_id, v.sucessora_id, v.tipo)
            continue
        sucessores[v.predecessora_id].append(v)
    return sucessores


def detectar_ciclo(nos: list[NoTarefa],
                   sucessores: dict[int, list[VinculoSpec]]) -> list[int] | None:
    """DFS iterativo (sem recursão — cronogramas grandes não estouram a
    pilha). Devolve o caminho do ciclo como lista de ids com o primeiro nó
    repetido no fim ([a, b, a]), ou None se o grafo é acíclico."""
    BRANCO, CINZA, PRETO = 0, 1, 2
    cor = {n.id: BRANCO for n in nos}
    for raiz in [n.id for n in nos]:
        if cor[raiz] != BRANCO:
            continue
        cor[raiz] = CINZA
        caminho = [raiz]
        pilha = [iter(sucessores.get(raiz, []))]
        while pilha:
            avancou = False
            for v in pilha[-1]:
                s = v.sucessora_id
                if s not in cor:
                    continue  # vínculo para fora do conjunto (já avisado)
                if cor[s] == CINZA:
                    return caminho[caminho.index(s):] + [s]
                if cor[s] == BRANCO:
                    cor[s] = CINZA
                    caminho.append(s)
                    pilha.append(iter(sucessores.get(s, [])))
                    avancou = True
                    break
            if not avancou:
                cor[caminho.pop()] = PRETO
                pilha.pop()
    return None


def ordenar_topologicamente(nos: list[NoTarefa],
                            sucessores: dict[int, list[VinculoSpec]]) -> list[int]:
    """Kahn. Determinística: desempata pela ordem de entrada de `nos`.
    Pré-condição: grafo acíclico (chame `detectar_ciclo` antes)."""
    from collections import deque

    ids = [n.id for n in nos]
    grau = {i: 0 for i in ids}
    for lista in sucessores.values():
        for v in lista:
            if v.sucessora_id in grau:
                grau[v.sucessora_id] += 1

    fila = deque(i for i in ids if grau[i] == 0)
    ordem: list[int] = []
    while fila:
        atual = fila.popleft()
        ordem.append(atual)
        for v in sucessores.get(atual, []):
            s = v.sucessora_id
            if s in grau:
                grau[s] -= 1
                if grau[s] == 0:
                    fila.append(s)
    return ordem


def _mensagem_ciclo(ciclo: list[int], por_id: dict[int, NoTarefa]) -> str:
    nomes = [por_id[i].nome if i in por_id else f'#{i}' for i in ciclo]
    caminho = ' → '.join(nomes)
    sucessora = nomes[-1]
    predecessora = nomes[-2] if len(nomes) >= 2 else nomes[-1]
    return (f'Vínculo inválido: "{sucessora}" já depende de "{predecessora}" '
            f'(ciclo: {caminho}).')


# ─────────────────────────────────────────────────────────────────────────────
# B4/B5 — Passe para frente + roll-up + passe para trás (puro)
# ─────────────────────────────────────────────────────────────────────────────

def _restricao_inicio(v: VinculoSpec, pred_inicio: date | None,
                      pred_fim: date | None, recuo_sucessora: int) -> date | None:
    """Início mínimo imposto à sucessora por UM vínculo (tabela do B4).
    `recuo_sucessora` = duração da sucessora - 1 (0 para marco/duração ≤1),
    usado para derivar o início nas restrições de FIM (TT/IT).
    Devolve None quando a data necessária da predecessora não existe."""
    if v.tipo == 'TI':                       # S.inicio ≥ P.fim + 1 + L
        if pred_fim is None:
            return None
        return somar_dias_uteis(pred_fim, 1 + v.lag)
    if v.tipo == 'II':                       # S.inicio ≥ P.inicio + L
        if pred_inicio is None:
            return None
        return somar_dias_uteis(pred_inicio, v.lag)
    if v.tipo == 'TT':                       # S.fim ≥ P.fim + L
        if pred_fim is None:
            return None
        fim_min = somar_dias_uteis(pred_fim, v.lag)
        return somar_dias_uteis(fim_min, -recuo_sucessora)
    if v.tipo == 'IT':                       # S.fim ≥ P.inicio + L
        if pred_inicio is None:
            return None
        fim_min = somar_dias_uteis(pred_inicio, v.lag)
        return somar_dias_uteis(fim_min, -recuo_sucessora)
    return None


def _profundidade(no: NoTarefa, por_id: dict[int, NoTarefa]) -> int:
    """Distância até a raiz da hierarquia. Defensivo contra pai órfão e
    ciclo de pais (mesma postura de `rollup_realizado` do engine antigo)."""
    nivel, visto, atual = 0, {no.id}, no
    while atual is not None and atual.pai_id:
        if atual.pai_id in visto:
            break
        visto.add(atual.pai_id)
        nivel += 1
        atual = por_id.get(atual.pai_id)
    return nivel


def calcular_agendamento(nos: list[NoTarefa], vinculos: list[VinculoSpec],
                         hoje: date | None = None) -> dict[int, ResultadoTarefa]:
    """Passe para frente + roll-up + folga/caminho crítico. 100% puro.

    Regras (plano Fase 1, B4/B5):
      * só FOLHAS entram no grafo de vínculos; pais são roll-up
        (inicio=min, fim=max, duracao=dias úteis inclusivos) de baixo p/ cima;
      * folha ANCORADA (iniciada) nunca tem datas alteradas, mas as datas
        reais dela alimentam as restrições das sucessoras;
      * folha sem predecessora e não ancorada é âncora "não começar antes
        de": mantém a própria data_inicio (normalizada p/ dia útil); sem
        data_inicio, recebe proximo_dia_util(hoje);
      * com predecessoras: data_inicio = MAX das restrições dos vínculos;
        predecessora sem as datas necessárias = restrição ignorada c/ warning;
      * passe para trás: folga total em dias úteis (≥0); is_critica = folga 0;
        folha ancorada participa normalmente (pode ser crítica); pai herda
        folga = min(filhas) e is_critica = any(filhas).

    Levanta `ErroCiclo` (mensagem pt-BR com nomes) se os vínculos formarem
    referência circular.
    """
    if hoje is None:
        hoje = date.today()

    por_id = {n.id: n for n in nos}
    pai_ids = {n.pai_id for n in nos if n.pai_id}
    folhas = [n for n in nos if n.id not in pai_ids]

    sucessores = montar_grafo(folhas, vinculos)
    ciclo = detectar_ciclo(folhas, sucessores)
    if ciclo:
        raise ErroCiclo(_mensagem_ciclo(ciclo, por_id), ciclo)
    ordem = ordenar_topologicamente(folhas, sucessores)

    predecessores: dict[int, list[VinculoSpec]] = {}
    for lista in sucessores.values():
        for v in lista:
            predecessores.setdefault(v.sucessora_id, []).append(v)

    resultados: dict[int, ResultadoTarefa] = {}
    # Datas "efetivas" usadas na propagação: para ancoradas, as reais
    # (com fim derivado da duração quando ausente); o RESULTADO delas
    # preserva as datas originais byte-idênticas (nunca gera diff).
    efetivas: dict[int, tuple[date | None, date | None]] = {}

    # ── Passe para frente (folhas, ordem topológica) ──
    for tid in ordem:
        no = por_id[tid]
        dur = int(no.duracao or 0)
        dur_span = 0 if no.is_marco else dur  # marco agenda como duração 0

        if no.ancorada:
            # As datas GRAVADAS da ancorada nunca mudam (é o que ancorar
            # significa) — `resultados` abaixo devolve `no.inicio`/`no.fim`
            # crus. Mas o início EFETIVO, do qual se deriva o fim quando ele
            # não existe, tem de ser dia útil: `fim_por_duracao` conta a
            # partir do dia em que se trabalha.
            #
            # Sem normalizar, um início em fim de semana perdia um dia útil:
            # sábado + 2 dias dava segunda, quando o trabalho começa segunda
            # e termina terça. Em dev, 2.952 tarefas ativas começam em fim de
            # semana — e como `efetivas` alimenta as restrições das
            # sucessoras, o erro escorria para a cadeia inteira.
            ini_ef = proximo_dia_util(no.inicio) if no.inicio else None
            fim_ef = no.fim or (fim_por_duracao(ini_ef, dur_span) if ini_ef else None)
            if ini_ef is None:
                logger.warning(
                    '[scheduler] tarefa ancorada %s ("%s") sem data_inicio — '
                    'não alimenta restrições das sucessoras', no.id, no.nome)
            resultados[tid] = ResultadoTarefa(inicio=no.inicio, fim=no.fim, duracao=dur)
            efetivas[tid] = (ini_ef, fim_ef)
            continue

        recuo = max(dur_span, 1) - 1
        candidatos: list[date] = []
        for v in predecessores.get(tid, []):
            pi, pf = efetivas.get(v.predecessora_id, (None, None))
            restricao = _restricao_inicio(v, pi, pf, recuo)
            if restricao is None:
                logger.warning(
                    '[scheduler] vínculo %s %s→%s ignorado: predecessora sem '
                    'as datas necessárias (dado legado)',
                    v.tipo, v.predecessora_id, v.sucessora_id)
            else:
                candidatos.append(restricao)
        if not candidatos:
            # Âncora "não começar antes de": a própria data_inicio (ou hoje),
            # normalizada para dia útil.
            candidatos.append(proximo_dia_util(no.inicio or hoje))

        inicio = max(candidatos)
        fim = fim_por_duracao(inicio, dur_span)
        resultados[tid] = ResultadoTarefa(inicio=inicio, fim=fim, duracao=dur)
        efetivas[tid] = (inicio, fim)

    # ── Passe para trás: folga total e caminho crítico (folhas) ──
    fins = [f for (_, f) in efetivas.values() if f is not None]
    if fins:
        fim_projeto = max(fins)
        tardias: dict[int, tuple[date, date]] = {}  # id → (late_start, late_finish)
        for tid in reversed(ordem):
            ini_ef, fim_ef = efetivas[tid]
            if ini_ef is None or fim_ef is None:
                continue  # sem datas: folga fica None, não restringe ninguém
            span = max(duracao_util_entre(ini_ef, fim_ef), 1)
            candidatos_lf: list[date] = []
            for v in sucessores.get(tid, []):
                tarde_suc = tardias.get(v.sucessora_id)
                if tarde_suc is None:
                    continue
                ls_s, lf_s = tarde_suc
                if v.tipo == 'TI':      # P.fim ≤ S.late_start - (1+L)
                    candidatos_lf.append(somar_dias_uteis(ls_s, -(1 + v.lag)))
                elif v.tipo == 'II':    # P.inicio ≤ S.late_start - L
                    ls_u = somar_dias_uteis(ls_s, -v.lag)
                    candidatos_lf.append(fim_por_duracao(ls_u, span))
                elif v.tipo == 'TT':    # P.fim ≤ S.late_finish - L
                    candidatos_lf.append(somar_dias_uteis(lf_s, -v.lag))
                elif v.tipo == 'IT':    # P.inicio ≤ S.late_finish - L
                    ls_u = somar_dias_uteis(lf_s, -v.lag)
                    candidatos_lf.append(fim_por_duracao(ls_u, span))
            lf = min(candidatos_lf) if candidatos_lf else fim_projeto
            ls = somar_dias_uteis(lf, -(span - 1)) if span > 1 else lf
            tardias[tid] = (ls, lf)
            folga = max(duracao_util_entre(ini_ef, ls) - 1, 0)
            resultados[tid].folga_dias = folga
            resultados[tid].is_critica = (folga == 0)

    # ── Roll-up dos pais (qualquer profundidade, de baixo para cima) ──
    filhos_por_pai: dict[int, list[int]] = {}
    for n in nos:
        if n.pai_id:
            filhos_por_pai.setdefault(n.pai_id, []).append(n.id)
    pais = [n for n in nos if n.id in pai_ids]
    for pai in sorted(pais, key=lambda n: _profundidade(n, por_id), reverse=True):
        filhas_res = [resultados[c] for c in filhos_por_pai.get(pai.id, [])
                      if c in resultados]
        com_datas = [r for r in filhas_res if r.inicio and r.fim]
        if com_datas:
            ini = min(r.inicio for r in com_datas)
            fim = max(r.fim for r in com_datas)
            dur = duracao_util_entre(ini, fim)
        else:
            # Nenhuma filha com datas (dado legado): mantém as do pai.
            ini, fim, dur = pai.inicio, pai.fim, int(pai.duracao or 0)
        folgas = [r.folga_dias for r in filhas_res if r.folga_dias is not None]
        resultados[pai.id] = ResultadoTarefa(
            inicio=ini, fim=fim, duracao=dur,
            folga_dias=min(folgas) if folgas else None,
            is_critica=any(r.is_critica for r in filhas_res),
        )

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# B3 — Predicado de âncora ("tarefa iniciada")
# ─────────────────────────────────────────────────────────────────────────────

def _ids_com_apontamento(tarefa_ids: list[int], admin_id: int) -> set[int]:
    """Tarefas com pelo menos 1 `RDOApontamentoCronograma` — UMA query IN."""
    from models import RDOApontamentoCronograma, db

    if not tarefa_ids:
        return set()
    linhas = (
        db.session.query(RDOApontamentoCronograma.tarefa_cronograma_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id.in_(tarefa_ids),
            RDOApontamentoCronograma.admin_id == admin_id,
        )
        .distinct()
        .all()
    )
    return {linha[0] for linha in linhas}


def _iniciadas_de(tarefas: list, com_apontamento: set[int]) -> set[int]:
    """Aplica o predicado B3 sobre tarefas já carregadas (só folhas):
    apontamento de RDO OU data_entrega_real OU percentual_concluido > 0."""
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    iniciadas: set[int] = set()
    for t in tarefas:
        if t.id in pai_ids:
            continue  # âncora é conceito de folha; pai é roll-up
        if (t.id in com_apontamento
                or t.data_entrega_real is not None
                or (t.percentual_concluido or 0) > 0):
            iniciadas.add(t.id)
    return iniciadas


def ids_tarefas_iniciadas(obra_id: int, admin_id: int, cliente: bool = False) -> set[int]:
    """IDs das tarefas-FOLHA "iniciadas" (ancoradas) da obra — plano B3:
      1. existe apontamento de RDO (`RDOApontamentoCronograma`), OU
      2. `data_entrega_real` preenchida (terceiros/entregas), OU
      3. `percentual_concluido > 0` (cobre subempreitada e edição manual,
         sem depender da origem).
    Duas queries no total (tarefas + apontamentos IN) — nunca N+1.
    """
    from models import TarefaCronograma

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente)
        .filter(TarefaCronograma.ativa.is_(True))
        .all()
    )
    return _iniciadas_de(tarefas, _ids_com_apontamento([t.id for t in tarefas], admin_id))


# ─────────────────────────────────────────────────────────────────────────────
# B6 — Orquestração e persistência
# ─────────────────────────────────────────────────────────────────────────────

def recalcular_obra(obra_id: int, admin_id: int, *, cliente: bool = False,
                    commit: bool = True) -> ResultadoAgendamento:
    """Recalcula a obra inteira com o motor novo e persiste SÓ os diffs.

    Carga em 3 queries (tarefas ativas do modo, vínculos, apontamentos IN);
    depois reaproveita o rollup de percentual do engine antigo
    (`utils.cronograma_engine.rollup_percentual_pos_recalculo` — mesma
    fórmula, não duplicada; internamente ele consulta o último apontamento
    por folha, comportamento herdado). Commit único no fim (`commit=True`);
    com `commit=False` apenas dá flush e o caller controla a transação.

    `ErroCiclo` propaga SEM commitar (com `commit=True` faz rollback também
    do que o caller tenha deixado pendente na sessão — ex.: vínculo recém-
    criado que fecha o ciclo).
    """
    from models import TarefaCronograma, TarefaVinculo, db
    from utils.cronograma_engine import rollup_percentual_pos_recalculo

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente)
        .filter(TarefaCronograma.ativa.is_(True))
        .order_by(TarefaCronograma.ordem)
        .all()
    )
    if not tarefas:
        return ResultadoAgendamento(tarefas_afetadas=[], total_tarefas=0)

    vinculos = (
        TarefaVinculo.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .order_by(TarefaVinculo.id)
        .all()
    )
    iniciadas = _iniciadas_de(
        tarefas, _ids_com_apontamento([t.id for t in tarefas], admin_id))

    nos = [
        NoTarefa(
            id=t.id,
            nome=t.nome_tarefa,
            duracao=int(t.duracao_dias or 0),
            inicio=t.data_inicio,
            fim=t.data_fim,
            pai_id=t.tarefa_pai_id,
            is_marco=bool(t.is_marco),
            ancorada=(t.id in iniciadas),
        )
        for t in tarefas
    ]
    specs = [
        VinculoSpec(
            predecessora_id=v.predecessora_id,
            sucessora_id=v.sucessora_id,
            tipo=v.tipo,
            lag=int(v.lag_dias or 0),
        )
        for v in vinculos
    ]

    try:
        resultados = calcular_agendamento(nos, specs, hoje=date.today())
    except ErroCiclo:
        if commit:
            db.session.rollback()
        raise

    afetadas: list = []
    for t in tarefas:
        r = resultados.get(t.id)
        if r is None:
            continue
        mudou = False
        if t.data_inicio != r.inicio:
            t.data_inicio = r.inicio
            mudou = True
        if t.data_fim != r.fim:
            t.data_fim = r.fim
            mudou = True
        if int(t.duracao_dias or 0) != int(r.duracao or 0):
            t.duracao_dias = int(r.duracao or 0)
            mudou = True
        if t.folga_dias != r.folga_dias:
            t.folga_dias = r.folga_dias
            mudou = True
        if bool(t.is_critica) != bool(r.is_critica):
            t.is_critica = bool(r.is_critica)
            mudou = True
        if mudou:
            afetadas.append(t)

    # Percentuais: mesma rotina do engine antigo (folhas ← último apontamento;
    # pais ← média ponderada pela duração) — helper compartilhado, sem commit.
    pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    rollup_percentual_pos_recalculo(tarefas, pai_ids, admin_id)

    if commit:
        db.session.commit()
    else:
        db.session.flush()

    logger.info(
        '[scheduler] obra %s recalculada: %d tarefa(s), %d afetada(s)',
        obra_id, len(tarefas), len(afetadas))
    return ResultadoAgendamento(tarefas_afetadas=afetadas, total_tarefas=len(tarefas))


def sincronizar_vinculos_de_predecessora_id(obra_id: int, admin_id: int) -> int:
    """Materializa em `TarefaVinculo` (TI, lag 0) os `predecessora_id` legados
    da obra que ainda não têm vínculo — mesma regra da migração 223, escopo
    de UMA obra. Usada pelo pós-importação .mpp e pela geração por proposta
    (Step C5), para a tabela não ficar obsoleta com a flag desligada.

    Pula (com warning) auto-referência e predecessora fora da obra/tenant
    (dado sujo conhecido). Devolve o nº de vínculos criados; commita quando
    cria algum.
    """
    from models import TarefaCronograma, TarefaVinculo, db

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .all()
    )
    por_id = {t.id: t for t in tarefas}
    existentes = {
        (v.predecessora_id, v.sucessora_id)
        for v in TarefaVinculo.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()
    }

    criados = 0
    for t in tarefas:
        pred_id = t.predecessora_id
        if not pred_id or pred_id == t.id:
            continue
        if pred_id not in por_id:
            logger.warning(
                '[scheduler] predecessora_id=%s da tarefa %s fora da obra '
                '%s/tenant %s — vínculo NÃO materializado (dado sujo)',
                pred_id, t.id, obra_id, admin_id)
            continue
        if (pred_id, t.id) in existentes:
            continue
        db.session.add(TarefaVinculo(
            admin_id=admin_id,
            obra_id=obra_id,
            predecessora_id=pred_id,
            sucessora_id=t.id,
            tipo='TI',
            lag_dias=0,
        ))
        existentes.add((pred_id, t.id))
        criados += 1

    if criados:
        db.session.commit()
        logger.info(
            '[scheduler] obra %s: %d vínculo(s) TI/0 materializados de '
            'predecessora_id', obra_id, criados)
    return criados
