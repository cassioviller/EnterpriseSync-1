"""
Motor de agendamento e progresso do Módulo de Cronograma de Obras.

FONTE ÚNICA das fórmulas de progresso (M06): views nunca implementam
fórmula — consomem este módulo. Tabela normativa (spec M06 §12):

| Caso                                   | Peso agregado        | Planejado            | Realizado                |
|----------------------------------------|----------------------|----------------------|--------------------------|
| Folha quantitativa (TODAS c/ qtd e     | quantidade           | linear dias úteis    | Σqtd_dia/total           |
|   MESMA unidade)                       |                      |                      |                          |
| Folha sem qtd (ou mix de qtd/unidade)  | duração (>0) senão 1 | linear dias úteis    | último acumulado %       |
| Pai/resumo                             | excluído (rollup por | rollup               | rollup                   |
|                                        | duração das filhas)  |                      |                          |
| Marco (is_marco ou duração 0)          | 0                    | degrau na data_inicio| 0 ou 100 (binário)       |
| Terceiros (responsavel='terceiros')    | igual às demais      | linear               | manual (sem sync do RDO) |
| Sem datas/duração                      | duração/1            | None (agrega como 0) | normal                   |
| Arquivada (M05)                        | 0 no presente/futuro | —                    | mantido p/ data_ref <    |
|                                        |                      |                      | arquivada_em (curva)     |

Regras de peso do agregado (calcular_progresso_geral_obra_v2): quantidade
SÓ quando TODAS as folhas não-marco têm quantidade E a mesma unidade —
nunca soma m+un+dias; senão duração; senão 1. Arquivadas só entram via
`com_arquivadas_historicas=True` (curva de avanço) e apenas para datas em
que ainda estavam vivas.

Também calcula datas de início/fim respeitando dias úteis e cadeia de
predecessoras (FS simples — tipos SS/FF/SF e lag ficam preservados no
snapshot do M05 para evolução futura; limitação documentada).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de dias úteis
# ─────────────────────────────────────────────────────────────────────────────

def _is_dia_util(d: date, considerar_sabado: bool, considerar_domingo: bool) -> bool:
    wd = d.weekday()  # 0=Seg … 6=Dom
    if wd == 5 and not considerar_sabado:
        return False
    if wd == 6 and not considerar_domingo:
        return False
    return True


def proximo_dia_util(d: date, considerar_sabado: bool, considerar_domingo: bool) -> date:
    """Retorna o próximo dia útil estritamente após `d`."""
    d = d + timedelta(days=1)
    while not _is_dia_util(d, considerar_sabado, considerar_domingo):
        d += timedelta(days=1)
    return d


def calcular_data_fim(data_inicio: date, duracao_dias: int,
                      considerar_sabado: bool, considerar_domingo: bool) -> date:
    """Soma `duracao_dias` dias úteis a partir de data_inicio (inclusive)."""
    if duracao_dias <= 0:
        return data_inicio
    d = data_inicio
    contados = 1
    while contados < duracao_dias:
        d += timedelta(days=1)
        if _is_dia_util(d, considerar_sabado, considerar_domingo):
            contados += 1
    return d


def dias_uteis_entre(inicio: date, fim: date,
                     considerar_sabado: bool, considerar_domingo: bool) -> int:
    """Conta dias úteis entre inicio e fim (inclusive em ambos os extremos)."""
    total = 0
    d = inicio
    while d <= fim:
        if _is_dia_util(d, considerar_sabado, considerar_domingo):
            total += 1
        d += timedelta(days=1)
    return total


# ─────────────────────────────────────────────────────────────────────────────
# Configuração do calendário
# ─────────────────────────────────────────────────────────────────────────────

def get_calendario(admin_id: int):
    """Retorna CalendarioEmpresa para admin_id (cria padrão se não existir)."""
    from models import CalendarioEmpresa, db
    cal = CalendarioEmpresa.query.filter_by(admin_id=admin_id).first()
    if not cal:
        cal = CalendarioEmpresa(
            admin_id=admin_id,
            considerar_sabado=False,
            considerar_domingo=False,
        )
        db.session.add(cal)
        db.session.commit()
    return cal


# ─────────────────────────────────────────────────────────────────────────────
# Ordem visual da grade (tree-flatten)
# ─────────────────────────────────────────────────────────────────────────────

def caminho_ancestrais_tarefa(tarefa, cache=None):
    """Onde a tarefa mora no cronograma: ``'Baias › Galpão B › Fundação'``, do
    ancestral mais alto para o pai imediato — a mesma direção em que a pessoa
    lê a árvore do cronograma. A raiz (nome da obra) fica de fora: é igual
    para toda tarefa e só ocuparia espaço na tela.

    FONTE ÚNICA do rótulo de contexto da tarefa: a tela interna do RDO e o
    portal do cliente consomem esta função. Existe porque as duas mostravam
    só `nome_tarefa`, e no cronograma da Baia as mesmas atividades existem
    nos dois galpões (101 tarefas com split Galpão A/B) — dois cards
    idênticos lado a lado liam-se como lançamento em duplicidade. Relato de
    28/07/2026 no RDO de 22/07, onde "AJR - Maquinário: …" (Galpão B,
    60→80%) e "Ajr - Maquinário: …" (Galpão A, 0→60%) só se distinguiam por
    um acaso de grafia herdado do .mpp. Mesma informação que
    `_rotulo_ancestrais` usa em services/atualizacao_rdos.py:132 para
    desempatar nomes na importação.

    `cache` (dict opcional) evita reconsultar o mesmo pai a cada linha do
    RDO. O laço para em ciclo de `tarefa_pai_id` em vez de girar para sempre
    — a coluna é auto-referente e nada no banco garante aciclicidade.
    """
    from models import TarefaCronograma
    if tarefa is None:
        return ''
    if cache is None:
        cache = {}
    cadeia, vistos, atual = [], set(), tarefa
    while atual is not None and atual.id not in vistos:
        vistos.add(atual.id)
        pai_id = atual.tarefa_pai_id
        if pai_id is None:
            break
        if pai_id not in cache:
            cache[pai_id] = TarefaCronograma.query.get(pai_id)
        atual = cache[pai_id]
        if atual is not None:
            cadeia.append(atual.nome_tarefa)
    # `cadeia` sobe da folha para a raiz; a última entrada é a raiz (a obra) e
    # sai fora. O que resta é invertido para ler de cima para baixo.
    return ' › '.join(reversed(cadeia[:-1])) if len(cadeia) > 1 else ''


def historico_em_percentual(tarefa_id: int, admin_id: int, ate=None) -> bool:
    """A tarefa tem apontamento GRAVADO em percentual até `ate`?

    O modo de leitura de uma linha é um fato dela, não uma propriedade que a
    tarefa tem hoje. `RDOApontamentoCronograma.tipo_apontamento` (migração
    209) é onde esse fato mora, e é isto que se lê aqui.

    Existe porque `calcular_progresso_rdo` decidia pela `quantidade_total`
    **vigente**: bastava alguém cadastrar o quantitativo de uma tarefa já
    apontada em % para os PONTOS PERCENTUAIS de `quantidade_executada_dia`
    passarem a ser lidos como produção física, reescrevendo o avanço sem
    rastro. Medido na Baia em 28/07/2026, tarefa "AJR - Maquinário:
    Nivelamento das Calçadas", em 80% (60 pp + 20 pp lançados em 21 e 22/07):

        cadastrar quantidade_total = 200 un  →  a tarefa passava a marcar  40%
        cadastrar quantidade_total =  48 un  →  a tarefa passava a marcar 100%

    É a mesma doutrina que `recomputar_cadeia`
    (services/cronograma_apontamento_service.py) já aplicava do outro lado:
    linha antiga se lê pelo formato em que foi gravada, e nada que aconteça
    hoje muda a leitura do que já passou.

    Basta UMA linha percentual: a coluna `quantidade_executada_dia` daquela
    tarefa passa a misturar pp com unidades, e a soma deixa de ser produção
    física para sempre. `ate=None` olha o histórico inteiro.

    Linhas sem rótulo (`tipo_apontamento IS NULL`) não respondem nada — a
    migração 265 carimbou as que existiam, e toda escrita nova carimba.
    """
    from models import RDO, RDOApontamentoCronograma, db

    q = (
        db.session.query(RDOApontamentoCronograma.id)
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDOApontamentoCronograma.tipo_apontamento == 'percentual',
        )
    )
    if ate is not None:
        q = q.filter(RDO.data_relatorio <= ate)
    return db.session.query(q.exists()).scalar() or False


def ids_com_historico_percentual(admin_id: int, tarefa_ids) -> set:
    """Versão em lote de `historico_em_percentual`: uma consulta para o
    conjunto todo, em vez de uma por tarefa.

    Existe para `sincronizar_percentuais_obra`, que percorre a obra inteira
    — lá o custo de uma consulta por tarefa apareceria na tela.
    """
    from models import RDOApontamentoCronograma, db

    ids = [t for t in tarefa_ids if t]
    if not ids:
        return set()
    return {
        tid for (tid,) in
        db.session.query(RDOApontamentoCronograma.tarefa_cronograma_id)
        .filter(RDOApontamentoCronograma.admin_id == admin_id,
                RDOApontamentoCronograma.tarefa_cronograma_id.in_(ids),
                RDOApontamentoCronograma.tipo_apontamento == 'percentual')
        .distinct()
    }


def agrupar_atividades_por_caminho(itens, chave='caminho_tarefa'):
    """``[(título, [itens])]`` para as atividades do dia de um RDO, agrupadas
    por onde moram no cronograma (o rótulo de `caminho_ancestrais_tarefa`).

    A ordem de entrada manda: os grupos saem na ordem em que aparecem pela
    primeira vez, e dentro do grupo os itens mantêm a ordem recebida (o
    chamador já ordenou por `ordem`/`ordem_execucao`). Não reordena nada —
    a sequência das atividades no RDO é informação do cronograma.

    Devolve UM grupo com título ``None`` quando não há o que separar (nenhum
    item tem caminho, ou todos estão no mesmo): cabeçalho de grupo numa obra
    sem hierarquia é só ruído na tela.
    """
    grupos: dict = {}
    for item in itens:
        titulo = (getattr(item, chave, '') or '') if not isinstance(item, dict) \
            else (item.get(chave) or '')
        grupos.setdefault(titulo, []).append(item)
    if len(grupos) <= 1:
        return [(None, list(itens))]
    return [(titulo or None, membros) for titulo, membros in grupos.items()]


def ordenar_arvore_visual(tarefas: list, com_nivel: bool = False):
    """Tree-flatten (DFS recursivo): intercala cada tarefa com todas as suas
    descendentes, de modo que as linhas apareçam imediatamente após o pai na
    grade renderizada, em qualquer profundidade de aninhamento.

    FONTE ÚNICA da numeração visual de linhas (1-based na grade): usada pela
    view `cronograma_obra` e pelo parser de predecessoras — os números nunca
    podem divergir. A ordem relativa entre irmãos é a ordem da lista de
    entrada (o chamador consulta com `ORDER BY ordem`); tarefas cujo
    `tarefa_pai_id` aponta para um pai fora da lista não entram no resultado
    (mesmo comportamento do flatten original da view).

    Com `com_nivel=True`, devolve `(lista, nivel_map)` onde `nivel_map` é
    task_id → profundidade (0 = raiz), para indentação no template.
    """
    filhas_map: dict[int, list] = {}
    raiz: list = []
    for t in tarefas:
        if t.tarefa_pai_id:
            filhas_map.setdefault(t.tarefa_pai_id, []).append(t)
        else:
            raiz.append(t)

    ordenadas: list = []
    nivel_map: dict[int, int] = {}  # task_id → depth (0 = root)

    def _dfs(node, depth: int) -> None:
        ordenadas.append(node)
        nivel_map[node.id] = depth
        for child in filhas_map.get(node.id, []):
            _dfs(child, depth + 1)

    for t in raiz:
        _dfs(t, 0)

    if com_nivel:
        return ordenadas, nivel_map
    return ordenadas


# ─────────────────────────────────────────────────────────────────────────────
# Detecção de ciclos
# ─────────────────────────────────────────────────────────────────────────────

def verificar_ciclo(tarefa_id: int, proposta_pred_id: int, admin_id: int) -> bool:
    """
    Retorna True se definir predecessora_id=proposta_pred_id na tarefa_id
    criaria uma referência circular.
    """
    from models import TarefaCronograma
    visited: set = set()
    cur = proposta_pred_id
    while cur is not None:
        if cur == tarefa_id:
            return True
        if cur in visited:
            return True
        visited.add(cur)
        t = TarefaCronograma.query.get(cur)
        if not t or t.admin_id != admin_id:
            break
        cur = t.predecessora_id
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Motor principal de recálculo
# ─────────────────────────────────────────────────────────────────────────────

def _is_marco_efetivo(tarefa) -> bool:
    """Marco explícito (`is_marco`, M02) ou duração zero não-marco —
    tratada como marco para peso/planejado (spec M06 §4.2; o M04 emite
    aviso `duracao_zero_sem_marco` no import)."""
    if getattr(tarefa, 'is_marco', False):
        return True
    dur = getattr(tarefa, 'duracao_dias', None)
    return dur is not None and int(dur) == 0


def _planejado_na_data(data_inicio, data_fim, duracao_dias, marco,
                       data_ref: date, sab: bool, dom: bool):
    """Percentual planejado (0-100) na `data_ref`, ou None sem plano.

    Marco: degrau — 0 antes de `data_inicio`, 100 a partir dela (sem
    data_inicio → None). Demais: interpolação linear por dias úteis —
    mesma fórmula de calcular_progresso_rdo e do replanejamento (M06);
    mudou aqui, mudou nos dois.
    """
    if marco:
        if not data_inicio:
            return None
        return 100.0 if data_ref >= data_inicio else 0.0
    if not (data_inicio and duracao_dias and duracao_dias > 0):
        return None
    if data_ref < data_inicio:
        return 0.0
    fim = data_fim or calcular_data_fim(data_inicio, duracao_dias, sab, dom)
    if data_ref >= fim:
        return 100.0
    dias_passados = dias_uteis_entre(data_inicio, data_ref, sab, dom)
    return min(100.0, round(dias_passados / duracao_dias * 100, 2))


def _percentual_livre(admin_id) -> bool:
    """Flag `rdo_percentual_livre` do tenant (migração 226, default FALSE).

    PONTO ÚNICO de leitura no engine. Ligada, as funções de derivação abaixo
    param de calcular `quantidade_acumulada / quantidade_total` e passam a
    usar o `percentual_realizado` do apontamento mais recente para TODA
    tarefa — inclusive as que têm quantitativo cadastrado, que com a flag
    ligada é só referência de leitura na tela do RDO.

    Continuidade garantida pela dupla escrita do serviço de apontamento:
    linha quantitativa antiga já gravou `percentual_realizado`, então uma
    tarefa em 62% continua em 62% no instante em que a flag liga.
    """
    from utils.tenant import rdo_percentual_livre_on
    return rdo_percentual_livre_on(admin_id)


def _atualizar_percentual_sem_commit(tarefa, admin_id: int,
                                     percentual_livre=None,
                                     hist_pct=None) -> None:
    """
    Versão sem commit de atualizar_percentual_tarefa — para uso em batch.
    Usa o apontamento mais recente (por data_relatorio) de cada tarefa.

    `percentual_livre`: estado já resolvido da flag (ver `_percentual_livre`).
    `None` consulta — quem chama em laço passa o booleano para não consultar
    a configuração uma vez por tarefa.

    `hist_pct`: conjunto de ids com histórico em percentual, já resolvido
    (ver `ids_com_historico_percentual`). Mesma razão do parâmetro acima —
    `None` consulta esta tarefa; o laço resolve o lote de uma vez.
    """
    from models import RDOApontamentoCronograma, RDO, db

    ultimo = (
        db.session.query(
            RDOApontamentoCronograma.percentual_realizado,
            RDOApontamentoCronograma.quantidade_acumulada,
        )
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa.id,
            RDOApontamentoCronograma.admin_id == admin_id,
        )
        # Desempate ESTÁVEL: não há unicidade de RDO por obra+data, então
        # dois RDOs do mesmo dia apontando a mesma tarefa deixariam a
        # escolha a cargo do banco — e o avanço mudaria entre leituras.
        # Mesma ordem que `registrar_apontamento` já usava do lado da
        # escrita (services/cronograma_apontamento_service.py).
        .order_by(RDO.data_relatorio.desc(),
                  RDOApontamentoCronograma.id.desc())
        .first()
    )

    if percentual_livre is None:
        percentual_livre = _percentual_livre(admin_id)

    if ultimo is None:
        tarefa.percentual_concluido = 0.0
    elif (not percentual_livre
            and tarefa.quantidade_total and tarefa.quantidade_total > 0
            and not (historico_em_percentual(tarefa.id, admin_id)
                     if hist_pct is None else tarefa.id in hist_pct)):
        # `historico_em_percentual`: linha lançada em % grava
        # `quantidade_acumulada = 0` (o acumulado dela é percentual). Dividir
        # esse 0 por um total cadastrado depois ZERAVA a tarefa — e aqui o
        # estrago fica gravado em `percentual_concluido`, não só na leitura.
        tarefa.percentual_concluido = min(
            100.0,
            round(float(ultimo.quantidade_acumulada) / tarefa.quantidade_total * 100, 2)
        )
    else:
        tarefa.percentual_concluido = min(100.0, float(ultimo.percentual_realizado or 0))


def sincronizar_percentuais_obra(obra_id: int, admin_id: int, cliente: bool = False) -> None:
    """
    Sincroniza percentual_concluido de todas as tarefas da obra
    com o último apontamento do RDO, em uma única transação.
    Mais leve que recalcular_cronograma (não toca nas datas).

    `cliente=True` opera apenas em tarefas do cronograma do cliente
    (TarefaCronograma.is_cliente=True). Tarefas-cliente NÃO recebem sync
    do RDO (RDO aponta no cronograma interno apenas), então neste modo
    a função apenas recalcula bottom-up dos pais a partir dos filhos.
    """
    from models import TarefaCronograma, RDOApontamentoCronograma, RDO, db
    from sqlalchemy import func as sqlfunc

    tarefas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente)
        .filter(TarefaCronograma.ativa.is_(True))
        .all()
    )
    if not tarefas:
        return

    # Busca em batch: último apontamento por tarefa_cronograma_id
    tarefa_ids = [t.id for t in tarefas]

    # Subquery: max data_relatorio por tarefa
    subq = (
        db.session.query(
            RDOApontamentoCronograma.tarefa_cronograma_id,
            sqlfunc.max(RDO.data_relatorio).label('ultima_data'),
        )
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id.in_(tarefa_ids),
            RDOApontamentoCronograma.admin_id == admin_id,
        )
        .group_by(RDOApontamentoCronograma.tarefa_cronograma_id)
        .subquery()
    )

    # Apontamento correspondente à data máxima.
    #
    # A data máxima pode casar com MAIS DE UMA linha: não há unicidade de
    # RDO por obra+data, então dois RDOs do mesmo dia apontando a mesma
    # tarefa devolvem duas linhas aqui. O `mapa` abaixo é um dict — a
    # última linha de cada tarefa vence — e sem ordenação essa "última"
    # era a que o banco resolvesse devolver por último. Aqui o empate
    # decidia um `percentual_concluido` que fica GRAVADO.
    #
    # A ordenação ASCENDENTE é o que torna o "último vence" do dict
    # determinístico E correto: a linha de maior id dentro da data máxima
    # é a que sobra, mesmo critério de `registrar_apontamento`.
    rows = (
        db.session.query(
            RDOApontamentoCronograma.tarefa_cronograma_id,
            RDOApontamentoCronograma.quantidade_acumulada,
            RDOApontamentoCronograma.percentual_realizado,
        )
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .join(
            subq,
            (subq.c.tarefa_cronograma_id == RDOApontamentoCronograma.tarefa_cronograma_id)
            & (subq.c.ultima_data == RDO.data_relatorio),
        )
        .filter(RDOApontamentoCronograma.admin_id == admin_id)
        .order_by(RDO.data_relatorio.asc(), RDOApontamentoCronograma.id.asc())
        .all()
    )

    # Mapa tarefa_id → (quantidade_acumulada, percentual_realizado)
    mapa = {r.tarefa_cronograma_id: r for r in rows}

    # Uma consulta para a obra inteira, não uma por tarefa.
    percentual_livre = _percentual_livre(admin_id)
    # Idem para o histórico em percentual (ver `historico_em_percentual`).
    hist_pct = ids_com_historico_percentual(admin_id, [t.id for t in tarefas])

    for tarefa in tarefas:
        # Tarefas de terceiros: percentual é gerenciado manualmente (checkbox),
        # não deve ser sobrescrito pela sincronização com o RDO
        if getattr(tarefa, 'responsavel', 'empresa') == 'terceiros':
            continue
        r = mapa.get(tarefa.id)
        if r is None:
            tarefa.percentual_concluido = 0.0
        elif (not percentual_livre
                and tarefa.quantidade_total and tarefa.quantidade_total > 0
                and tarefa.id not in hist_pct):
            tarefa.percentual_concluido = min(
                100.0,
                round(float(r.quantidade_acumulada) / tarefa.quantidade_total * 100, 2)
            )
        else:
            tarefa.percentual_concluido = min(100.0, float(r.percentual_realizado or 0))

    # ── Bottom-up: % dos pais calculado a partir dos filhos (média ponderada por duração) ──
    pai_ids_set = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    tarefa_map_local = {t.id: t for t in tarefas}
    pais_lista = [t for t in tarefas if t.id in pai_ids_set]
    # Ordenar do mais profundo para a raiz usando a ordem reversa
    for pai in sorted(pais_lista, key=lambda t: t.ordem, reverse=True):
        filhas = [t for t in tarefas if t.tarefa_pai_id == pai.id]
        if not filhas:
            continue
        total_dur = sum(max(f.duracao_dias or 1, 1) for f in filhas)
        if total_dur > 0:
            pai.percentual_concluido = round(
                sum((f.percentual_concluido or 0) * max(f.duracao_dias or 1, 1) for f in filhas) / total_dur, 2
            )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def rollup_percentual_pos_recalculo(tarefas: list, pai_ids: set, admin_id: int) -> None:
    """Sincroniza `percentual_concluido` após um recálculo de datas — SEM commit.

    Extraído byte-idêntico de `recalcular_cronograma` (o bloco entre os dois
    commits) para ser REAPROVEITADO pelo motor novo
    (`services/cronograma_scheduler.recalcular_obra`) sem duplicar fórmula
    (Fase 1 do cronograma editável): folhas recebem o último apontamento do
    RDO (`_atualizar_percentual_sem_commit`); pais recebem média ponderada
    pela duração das filhas, de baixo para cima. O commit é do caller.
    """
    # Sincronizar percentual_concluido de folhas com o último apontamento do RDO
    percentual_livre = _percentual_livre(admin_id)  # uma consulta para o lote
    hist_pct = ids_com_historico_percentual(  # idem
        admin_id, [t.id for t in tarefas if t.id not in pai_ids])
    for tarefa in tarefas:
        if tarefa.id not in pai_ids:  # só folhas recebem sync do RDO
            _atualizar_percentual_sem_commit(tarefa, admin_id, percentual_livre,
                                             hist_pct)

    # Bottom-up: % dos pais calculado a partir dos filhos (média ponderada por duração)
    pais = [t for t in tarefas if t.id in pai_ids]
    for pai in sorted(pais, key=lambda t: t.ordem, reverse=True):
        filhas = [t for t in tarefas if t.tarefa_pai_id == pai.id]
        if not filhas:
            continue
        total_dur = sum(max(f.duracao_dias or 1, 1) for f in filhas)
        if total_dur > 0:
            pai.percentual_concluido = round(
                sum((f.percentual_concluido or 0) * max(f.duracao_dias or 1, 1) for f in filhas) / total_dur, 2
            )


def recalcular_cronograma(obra_id: int, admin_id: int, cliente: bool = False) -> bool:
    """
    Recalcula as datas de todas as tarefas de uma obra.

    Algoritmo (topological):
    1. Busca CalendarioEmpresa para saber sab/dom úteis.
    2. Processa tarefas folha (sem filhas) em ordem de dependência.
       - Sem predecessora: mantém data_inicio, calcula data_fim.
       - Com predecessora: data_inicio = próximo dia útil após data_fim da pred.
    3. Atualiza tarefas pai: data_inicio = min(filhas), data_fim = max(filhas).
    4. Persiste alterações.

    Retorna True em sucesso, False em erro.
    """
    from models import TarefaCronograma, db

    try:
        cal = get_calendario(admin_id)
        sab = cal.considerar_sabado
        dom = cal.considerar_domingo

        tarefas = (
            TarefaCronograma.query
            .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=cliente)
            .filter(TarefaCronograma.ativa.is_(True))
            .order_by(TarefaCronograma.ordem)
            .all()
        )
        if not tarefas:
            return True

        tarefa_map = {t.id: t for t in tarefas}

        # Identificar IDs que são pais
        pai_ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}

        # Tarefas folha = não são pais de nenhuma outra
        folhas = [t for t in tarefas if t.id not in pai_ids]
        pais = [t for t in tarefas if t.id in pai_ids]

        # Processar folhas em ordem topológica via predecessoras
        processadas: set = set()
        pendentes = list(folhas)
        max_iter = len(pendentes) * 3 + 10

        for _ in range(max_iter):
            if not pendentes:
                break
            progrediu = False
            for tarefa in list(pendentes):
                pred_ok = (
                    tarefa.predecessora_id is None
                    or tarefa.predecessora_id in processadas
                    or tarefa.predecessora_id not in tarefa_map
                )
                if not pred_ok:
                    continue

                pred = tarefa_map.get(tarefa.predecessora_id)
                if pred is not None and pred.data_fim:
                    tarefa.data_inicio = proximo_dia_util(pred.data_fim, sab, dom)
                elif tarefa.data_inicio is None:
                    tarefa.data_inicio = date.today()

                if tarefa.data_inicio:
                    dur = max(tarefa.duracao_dias or 1, 1)
                    tarefa.data_fim = calcular_data_fim(tarefa.data_inicio, dur, sab, dom)

                processadas.add(tarefa.id)
                pendentes.remove(tarefa)
                progrediu = True

            if not progrediu:
                # Forçar processamento de tarefas restantes (ciclos quebrados)
                for tarefa in list(pendentes):
                    if tarefa.data_inicio:
                        dur = max(tarefa.duracao_dias or 1, 1)
                        tarefa.data_fim = calcular_data_fim(tarefa.data_inicio, dur, sab, dom)
                    processadas.add(tarefa.id)
                pendentes.clear()

        # Atualizar tarefas pai a partir das filhas (de folhas para raiz)
        for pai in sorted(pais, key=lambda t: t.ordem, reverse=True):
            filhas = [t for t in tarefas if t.tarefa_pai_id == pai.id]
            com_datas = [f for f in filhas if f.data_inicio and f.data_fim]
            if com_datas:
                pai.data_inicio = min(f.data_inicio for f in com_datas)
                pai.data_fim = max(f.data_fim for f in com_datas)
                pai.duracao_dias = dias_uteis_entre(
                    pai.data_inicio, pai.data_fim, sab, dom
                )

        db.session.commit()

        rollup_percentual_pos_recalculo(tarefas, pai_ids, admin_id)

        db.session.commit()

        logger.info(
            f"[OK] Cronograma recalculado: obra_id={obra_id}, "
            f"{len(tarefas)} tarefas processadas"
        )
        return True

    except Exception as e:
        logger.error(f"[ERROR] recalcular_cronograma obra_id={obra_id}: {e}")
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Progresso RDO ↔ Cronograma
# ─────────────────────────────────────────────────────────────────────────────

def calcular_progresso_rdo(tarefa_id: int, data_rdo: date, admin_id: int,
                           percentual_livre=None) -> dict:
    """
    Retorna um dict com:
    - percentual_planejado: quanto deveria estar concluído até data_rdo (linear
        por dias úteis). Vale `None` quando a tarefa não tem `data_inicio` nem
        `duracao_dias` definidos — sinalizando "sem plano" para a UI (≠ 0%).
    - percentual_realizado: total acumulado de produção até data_rdo
    - quantidade_acumulada: soma de quantidade_executada_dia até data_rdo

    Casos de planejado:
      • data_rdo  < data_inicio              → 0.0   (ainda não começou no plano)
      • data_inicio ≤ data_rdo < data_fim    → interpolação linear (dias úteis)
      • data_rdo ≥ data_fim                  → 100.0
      • sem data_inicio ou sem duracao_dias  → None  (sem plano calculável)

    `percentual_livre`: estado já resolvido da flag `rdo_percentual_livre`
    (ver `_percentual_livre`). `None` consulta; quem chama em laço sobre a
    obra inteira passa o booleano.
    """
    from models import TarefaCronograma, RDOApontamentoCronograma, db

    tarefa = TarefaCronograma.query.get(tarefa_id)
    if not tarefa:
        return {'percentual_planejado': None, 'percentual_realizado': 0.0, 'quantidade_acumulada': 0.0}

    # ── Planejado ── marco = degrau na data_inicio; demais = interpolação
    # linear por dias úteis; None = "Sem plano" (a UI mostra "—", NÃO 0%,
    # que pareceria atraso).
    marco = _is_marco_efetivo(tarefa)
    cal = get_calendario(admin_id)
    perc_planejado = _planejado_na_data(
        tarefa.data_inicio, tarefa.data_fim, tarefa.duracao_dias, marco,
        data_rdo, cal.considerar_sabado, cal.considerar_domingo)

    # ── Realizado ──
    from sqlalchemy import func as sqlfunc
    from models import RDO

    # Linhas gravadas em PERCENTUAL guardam PONTOS PERCENTUAIS em
    # `quantidade_executada_dia` — somá-las como produção física é um erro de
    # unidade. Por isso a soma abaixo ignora essas linhas: sem o filtro, uma
    # tarefa apontada em % que ganhasse `quantidade_total` depois teria os
    # mesmos pp divididos pelo total (ver `historico_em_percentual`).
    acumulado = (
        db.session.query(sqlfunc.coalesce(sqlfunc.sum(RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
            RDO.data_relatorio <= data_rdo,
            sqlfunc.coalesce(
                RDOApontamentoCronograma.tipo_apontamento, '') != 'percentual',
        )
        .scalar()
    ) or 0.0

    if percentual_livre is None:
        percentual_livre = _percentual_livre(admin_id)

    perc_realizado = 0.0
    if (not percentual_livre
            and tarefa.quantidade_total and tarefa.quantidade_total > 0
            and not historico_em_percentual(tarefa_id, admin_id, data_rdo)):
        perc_realizado = min(100.0, round(acumulado / tarefa.quantidade_total * 100, 2))
    else:
        # Três casos caem aqui: tarefa sem quantidade física; QUALQUER tarefa
        # quando a flag `rdo_percentual_livre` está ligada; e a tarefa cujo
        # HISTÓRICO foi lançado em percentual, mesmo que alguém tenha
        # cadastrado `quantidade_total` depois. O avanço é o
        # `percentual_realizado` do ÚLTIMO apontamento até data_rdo (mesma
        # fonte que sincronizar_percentuais_obra). Antes esse caso devolvia
        # sempre 0.
        ultimo = (
            db.session.query(RDOApontamentoCronograma.percentual_realizado)
            .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
            .filter(
                RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
                RDOApontamentoCronograma.admin_id == admin_id,
                RDO.data_relatorio <= data_rdo,
            )
            # Desempate ESTÁVEL — ver nota em
            # `_atualizar_percentual_sem_commit`.
            .order_by(RDO.data_relatorio.desc(),
                      RDOApontamentoCronograma.id.desc())
            .first()
        )
        if ultimo is not None and ultimo[0] is not None:
            perc_realizado = min(100.0, float(ultimo[0]))
            if acumulado <= 0:
                # sinaliza apontamento p/ n_tarefas_apontadas em
                # calcular_progresso_geral_obra_v2 (testa quantidade_acumulada > 0)
                acumulado = perc_realizado

    # Marco é binário: só existe "não entregue" (0) ou "entregue" (100).
    if marco:
        perc_realizado = 100.0 if perc_realizado >= 100.0 else 0.0

    return {
        'percentual_planejado': perc_planejado,
        'percentual_realizado': perc_realizado,
        'quantidade_acumulada': acumulado,
    }


def calcular_progresso_geral_obra_v2(obra_id: int, data_ref: date,
                                     admin_id: int, *,
                                     com_arquivadas_historicas: bool = False) -> dict:
    """
    Calcula o **progresso geral acumulado da obra** (modo V2) até `data_ref`.

    Itera todas as `TarefaCronograma` FOLHA da obra (subtarefas — tarefas-pai
    não entram para evitar dupla contagem) e combina via **média ponderada**.

    Peso por tarefa:
       • `quantidade_total` SÓ quando TODAS as folhas o têm (unidade consistente);
       • senão `duracao_dias` (fatia temporal — unidade comparável entre todas);
       • senão `1` (último recurso: média simples).
    Se só algumas folhas têm `quantidade_total`, usá-la como peso misturaria
    unidades incomparáveis entre tarefas — por isso, nesse caso, ela governa apenas
    o % da própria tarefa, não o peso do agregado.

    Tarefas sem qualquer apontamento até `data_ref` contam como **0%**
    (puxam a média para baixo) — é por isso que o número não pode decrescer
    em ordem cronológica enquanto novos apontamentos forem adicionados.

    Returns dict:
      - progresso_geral_pct: float 0..100 (0 quando a obra não tem tarefas)
      - progresso_planejado_pct: float 0..100 (Task #141 — planejado da obra
        à data_ref, mesma média ponderada usando `percentual_planejado`).
        Tarefas "Sem plano" contam como 0 no agregado planejado (consistente
        com o comportamento de "realizado" para tarefas sem apontamento).
      - n_tarefas: int (folhas consideradas)
      - n_tarefas_apontadas: int (folhas com pelo menos 1 apontamento até data_ref)
    """
    from models import TarefaCronograma
    from sqlalchemy import and_, or_

    consulta = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id)
        .filter_by(is_cliente=False)
    )
    if com_arquivadas_historicas:
        # Curva histórica (M06 §4.2): tarefa arquivada DEPOIS de data_ref
        # ainda estava viva na data consultada — o trabalho feito nela não
        # some da curva. Arquivadas antes de data_ref ficam de fora (peso 0
        # no presente/futuro).
        consulta = consulta.filter(or_(
            TarefaCronograma.ativa.is_(True),
            and_(TarefaCronograma.arquivada_em.isnot(None),
                 TarefaCronograma.arquivada_em > data_ref),
        ))
    else:
        consulta = consulta.filter(TarefaCronograma.ativa.is_(True))
    folhas = consulta.all()
    if not folhas:
        return {
            'progresso_geral_pct': 0.0,
            'progresso_planejado_pct': 0.0,
            'n_tarefas': 0,
            'n_tarefas_apontadas': 0,
        }

    # Identificar IDs de tarefas-pai (que aparecem como tarefa_pai_id em outras)
    pais_ids = {t.tarefa_pai_id for t in folhas if t.tarefa_pai_id}
    folhas_efetivas = [t for t in folhas if t.id not in pais_ids]
    if not folhas_efetivas:
        return {
            'progresso_geral_pct': 0.0,
            'progresso_planejado_pct': 0.0,
            'n_tarefas': 0,
            'n_tarefas_apontadas': 0,
        }

    soma_real = 0.0
    soma_plan = 0.0
    soma_pesos = 0.0
    n_apontadas = 0

    # Peso: usa `quantidade_total` SÓ quando TODAS as folhas não-marco o têm
    # E com a MESMA unidade (M06 §4.2 — nunca soma m+un+dias). Se apenas
    # algumas têm (ex.: 48 brocas numa obra cujas demais tarefas não têm
    # quantitativo) ou as unidades divergem, usar qty como peso misturaria
    # unidades incomparáveis e distorceria a média — então cai para a duração
    # em todas. Nesse caso o `quantidade_total` governa apenas o % da própria
    # tarefa (calcular_progresso_rdo / sincronizar_percentuais_obra).
    # Marcos ficam fora do critério E do peso (peso 0 — tabela §12).
    nao_marcos = [t for t in folhas_efetivas if not _is_marco_efetivo(t)]
    usar_qtd = bool(nao_marcos) and all(
        t.quantidade_total and float(t.quantidade_total) > 0
        for t in nao_marcos
    ) and len({(t.unidade_medida or '').strip().lower()
               for t in nao_marcos}) == 1

    percentual_livre = _percentual_livre(admin_id)  # uma consulta para a obra

    for t in folhas_efetivas:
        prog = calcular_progresso_rdo(t.id, data_ref, admin_id, percentual_livre)
        perc_real = float(prog.get('percentual_realizado') or 0.0)
        # Sem plano calculável conta como 0 no agregado planejado.
        perc_plan = float(prog.get('percentual_planejado') or 0.0)

        # Escolha do peso (ver comentário acima). Marco pesa 0.
        if _is_marco_efetivo(t):
            peso = 0.0
        elif usar_qtd:
            peso = float(t.quantidade_total)
        elif t.duracao_dias and int(t.duracao_dias) > 0:
            peso = float(t.duracao_dias)
        else:
            peso = 1.0

        soma_real += perc_real * peso
        soma_plan += perc_plan * peso
        soma_pesos += peso
        if (prog.get('quantidade_acumulada') or 0) > 0:
            n_apontadas += 1

    progresso = (soma_real / soma_pesos) if soma_pesos > 0 else 0.0
    planejado = (soma_plan / soma_pesos) if soma_pesos > 0 else 0.0
    return {
        'progresso_geral_pct': round(progresso, 1),
        'progresso_planejado_pct': round(planejado, 1),
        'n_tarefas': len(folhas_efetivas),
        'n_tarefas_apontadas': n_apontadas,
    }


def rollup_realizado(itens: list) -> dict:
    """Percentual realizado dos PAIS: média ponderada pela duração das
    filhas, de baixo para cima (mesma fórmula do recálculo/sync — um só
    lugar, M06 §4.1).

    `itens`: dicts com `id`, `tarefa_pai_id`, `duracao_dias`,
    `percentual_realizado`. Um pai intermediário usa o valor JÁ agregado
    dos próprios filhos, então a ordem de processamento tem de ser
    bottom-up de verdade: os pais são ordenados pela PROFUNDIDADE real na
    árvore (mais fundo primeiro), não por `ordem`.

    A heurística antiga (`ordem` decrescente) silenciava em dois casos: se
    o caller não passasse `ordem` — todos viravam 0 e a raiz era calculada
    ANTES do subgrupo, lendo 0 em vez do agregado — ou se `ordem` não
    correlacionasse com profundidade. Era o caso do payload de
    `/cronograma/obra/<id>/tarefas-rdo`, que nunca teve a chave `ordem`.
    Devolve `{pai_id: pct}`.
    """
    filhas_por_pai: dict = {}
    for it in itens:
        if it.get('tarefa_pai_id'):
            filhas_por_pai.setdefault(it['tarefa_pai_id'], []).append(it)
    por_id = {it['id']: it for it in itens}

    def _profundidade(item_id) -> int:
        """Distância até a raiz. Defensivo contra ciclos e pai órfão."""
        nivel, visto, atual = 0, {item_id}, por_id.get(item_id)
        while atual is not None and atual.get('tarefa_pai_id'):
            pai_id = atual['tarefa_pai_id']
            if pai_id in visto:  # ciclo: para de subir
                break
            visto.add(pai_id)
            nivel += 1
            atual = por_id.get(pai_id)
        return nivel

    resultado: dict = {}
    pais = [por_id[p] for p in filhas_por_pai if p in por_id]
    for pai in sorted(pais, key=lambda x: _profundidade(x['id']), reverse=True):
        filhas = filhas_por_pai[pai['id']]
        total_dur = sum(max(int(f.get('duracao_dias') or 1), 1)
                        for f in filhas)
        if total_dur <= 0:
            continue
        agregado = sum(
            (resultado.get(f['id'], f.get('percentual_realizado')) or 0)
            * max(int(f.get('duracao_dias') or 1), 1)
            for f in filhas
        ) / total_dur
        resultado[pai['id']] = round(agregado, 2)
    return resultado


def _progresso_fallback_subatividades(obra_id: int) -> float:
    """Caminho C (legado, obras SEM cronograma): média simples de
    `percentual_conclusao` das subatividades do último RDO — a antiga
    "FÓRMULA SIMPLES" do KPI de detalhes da obra, preservada apenas como
    fallback documentado (spec M06 §4.1)."""
    from models import RDO, RDOServicoSubatividade

    ultimo = (RDO.query.filter_by(obra_id=obra_id)
              # `RDO.id` desempata: sem unicidade por obra+data, "o último
              # RDO" seria escolha do banco.
              .order_by(RDO.data_relatorio.desc(), RDO.id.desc()).first())
    if ultimo is None:
        return 0.0
    subs = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo.id).all()
    if not subs:
        return 0.0
    return round(sum(s.percentual_conclusao or 0 for s in subs) / len(subs), 1)


def progresso_geral_para_kpi(obra_id: int, admin_id: int) -> float:
    """Progresso geral para o KPI de detalhes da obra (M06 §4.1).

    Mesma bifurcação do card de RDO: obra com cronograma interno vivo →
    `calcular_progresso_geral_obra_v2` de hoje (converge com header,
    portal, card e curva); sem cronograma → fallback V1 por subatividades
    do último RDO.
    """
    from models import TarefaCronograma

    tem_cronograma = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .filter(TarefaCronograma.ativa.is_(True))
        .first() is not None
    )
    if tem_cronograma:
        return calcular_progresso_geral_obra_v2(
            obra_id, date.today(), admin_id)['progresso_geral_pct']
    return _progresso_fallback_subatividades(obra_id)


def replanejar_curvas_obra(obra_id: int, admin_id: int) -> dict:
    """Recalcula `RDOApontamentoCronograma.percentual_planejado` de TODOS os
    apontamentos da obra com as datas VIGENTES das tarefas (M06 §4.3).

    Chamado após aplicar/restaurar versão (M05): o planejado gravado em cada
    RDO é snapshot do plano da época e fica órfão quando as datas mudam.
    NUNCA toca o realizado — `quantidade_executada_dia`,
    `quantidade_acumulada`, `percentual_realizado` e `percentual_acumulado`
    permanecem byte-idênticos. Ao final, sincroniza percentuais (pais
    inclusive) e devolve o relatório:
    ``{apontamentos_replanejados, tarefas_sem_historico_reconciliado,
    progresso_antes, progresso_depois}`` — arquivadas com apontamento
    entram na lista para revisão manual (histórico não reconciliado).
    """
    from models import RDO, RDOApontamentoCronograma, TarefaCronograma, db

    hoje = date.today()
    progresso_antes = calcular_progresso_geral_obra_v2(
        obra_id, hoje, admin_id)['progresso_geral_pct']

    cal = get_calendario(admin_id)
    sab, dom = cal.considerar_sabado, cal.considerar_domingo
    # Inclui arquivadas: apontamentos delas também são replanejados com as
    # últimas datas conhecidas (e listados no relatório).
    tarefas = {t.id: t for t in (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .all())}

    linhas = (
        db.session.query(RDOApontamentoCronograma, RDO.data_relatorio)
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(RDO.obra_id == obra_id,
                RDOApontamentoCronograma.admin_id == admin_id)
        .order_by(RDO.data_relatorio.asc(), RDOApontamentoCronograma.id.asc())
        .all()
    )

    replanejados = 0
    arquivadas_com_apontamento = set()
    for ap, data_rdo in linhas:
        t = tarefas.get(ap.tarefa_cronograma_id)
        if t is None:
            continue
        if not t.ativa:
            arquivadas_com_apontamento.add(t.id)
        novo = _planejado_na_data(
            t.data_inicio, t.data_fim, t.duracao_dias,
            _is_marco_efetivo(t), data_rdo, sab, dom)
        antigo = ap.percentual_planejado
        mudou = ((antigo is None) != (novo is None)
                 or (antigo is not None and novo is not None
                     and abs(float(antigo) - float(novo)) > 1e-9))
        if mudou:
            ap.percentual_planejado = novo
            replanejados += 1

    db.session.commit()
    sincronizar_percentuais_obra(obra_id, admin_id, cliente=False)

    progresso_depois = calcular_progresso_geral_obra_v2(
        obra_id, hoje, admin_id)['progresso_geral_pct']
    return {
        'apontamentos_replanejados': replanejados,
        'tarefas_sem_historico_reconciliado':
            sorted(arquivadas_com_apontamento),
        'progresso_antes': progresso_antes,
        'progresso_depois': progresso_depois,
    }


def verificar_consistencia_progresso(obra_id: int, admin_id: int) -> dict:
    """Ferramenta de suporte (M06 §16): compara o `percentual_concluido`
    persistido de cada folha viva com o recalculado pelo engine e loga o
    drift. Não altera nada."""
    from models import TarefaCronograma

    folhas = (
        TarefaCronograma.query
        .filter_by(obra_id=obra_id, admin_id=admin_id, is_cliente=False)
        .filter(TarefaCronograma.ativa.is_(True))
        .all()
    )
    pais_ids = {t.tarefa_pai_id for t in folhas if t.tarefa_pai_id}
    divergencias = []
    verificadas = 0
    for t in folhas:
        if t.id in pais_ids or getattr(t, 'responsavel', 'empresa') == 'terceiros':
            continue  # pais são rollup; terceiros são manuais
        verificadas += 1
        recalc = calcular_progresso_rdo(t.id, date.today(), admin_id)[
            'percentual_realizado']
        persistido = float(t.percentual_concluido or 0.0)
        if abs(persistido - float(recalc)) > 0.01:
            divergencias.append({'tarefa_id': t.id,
                                 'persistido': persistido,
                                 'recalculado': float(recalc)})
    if divergencias:
        logger.warning(
            'drift de progresso na obra %s: %d tarefa(s) divergente(s): %s',
            obra_id, len(divergencias), divergencias)
    return {'tarefas_verificadas': verificadas, 'divergencias': divergencias}


def atualizar_percentual_tarefa(tarefa_id: int, admin_id: int) -> None:
    """
    Recalcula e persiste o percentual_concluido da TarefaCronograma.

    Usa o `percentual_realizado` do apontamento mais recente (por data_relatorio),
    que por sua vez é calculado com base em `quantidade_acumulada / quantidade_total`.
    Isso evita dupla contagem ao somar `quantidade_executada_dia` de múltiplos dias.

    Subempreitada (M06 §4.1): quando a tarefa é quantitativa e existem
    `RDOSubempreitadaApontamento`, a produção da sub soma-se à acumulada
    da empresa — este é o ÚNICO caminho (o helper da view delega aqui).
    """
    from models import (RDO, RDOApontamentoCronograma,
                        RDOSubempreitadaApontamento, TarefaCronograma, db)
    from sqlalchemy import func as sqlfunc

    tarefa = TarefaCronograma.query.get(tarefa_id)
    if not tarefa:
        return

    # Busca o apontamento mais recente (maior data_relatorio do RDO)
    ultimo = (
        db.session.query(
            RDOApontamentoCronograma.percentual_realizado,
            RDOApontamentoCronograma.quantidade_acumulada,
        )
        .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
        .filter(
            RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
            RDOApontamentoCronograma.admin_id == admin_id,
        )
        # Desempate ESTÁVEL: não há unicidade de RDO por obra+data, então
        # dois RDOs do mesmo dia apontando a mesma tarefa deixariam a
        # escolha a cargo do banco — e o avanço mudaria entre leituras.
        # Mesma ordem que `registrar_apontamento` já usava do lado da
        # escrita (services/cronograma_apontamento_service.py).
        .order_by(RDO.data_relatorio.desc(),
                  RDOApontamentoCronograma.id.desc())
        .first()
    )

    qtd_sub = (
        db.session.query(sqlfunc.coalesce(
            sqlfunc.sum(RDOSubempreitadaApontamento.quantidade_produzida), 0.0))
        .filter(RDOSubempreitadaApontamento.tarefa_cronograma_id == tarefa_id,
                RDOSubempreitadaApontamento.admin_id == admin_id)
        .scalar()
    ) or 0.0

    tem_total = bool(tarefa.quantidade_total and tarefa.quantidade_total > 0)
    percentual_livre = _percentual_livre(admin_id)

    if percentual_livre:
        # Flag ligada: a parcela da EMPRESA vem do percentual_realizado do
        # último apontamento (o quantitativo da tarefa é só referência).
        # A parcela da SUBEMPREITADA continua sendo quantidade produzida —
        # é o que a sub reporta — e só é conversível em % quando a tarefa
        # tem total cadastrado, exatamente como no ramo quantitativo abaixo
        # (sem total, `qtd_sub` já era ignorado hoje).
        pct_empresa = min(100.0, float(ultimo.percentual_realizado or 0)) if ultimo else 0.0
        pct_sub = (round(float(qtd_sub) / tarefa.quantidade_total * 100, 2)
                   if tem_total and qtd_sub else 0.0)
        tarefa.percentual_concluido = min(100.0, round(pct_empresa + pct_sub, 2))
    elif tem_total and not historico_em_percentual(tarefa_id, admin_id):
        # Empresa: quantidade_acumulada do último RDO (evita dupla contagem);
        # subempreitada: soma da produção registrada.
        #
        # `historico_em_percentual` porque a parcela da EMPRESA só é
        # quantidade quando foi lançada como tal — senão `quantidade_acumulada`
        # vale 0 e o total cadastrado depois zeraria a tarefa. A parcela da
        # SUB continua física (ela reporta produção), e o ramo percentual
        # abaixo já a converte pelo total, como no ramo da flag ligada.
        acum_empresa = float(ultimo.quantidade_acumulada) if ultimo else 0.0
        tarefa.percentual_concluido = min(
            100.0,
            round((acum_empresa + float(qtd_sub))
                  / tarefa.quantidade_total * 100, 2)
        )
    elif ultimo is None and not qtd_sub:
        # Sem apontamentos — mantém 0
        tarefa.percentual_concluido = 0.0
    else:
        # Sem quantidade_total, OU tarefa cujo histórico da empresa foi
        # lançado em percentual: o avanço da empresa é o percentual_realizado
        # do apontamento. A parcela da SUB só entra quando há total para
        # convertê-la — mesma regra do ramo `percentual_livre` acima.
        pct_empresa = min(100.0, float(ultimo.percentual_realizado or 0)) if ultimo else 0.0
        pct_sub = (round(float(qtd_sub) / tarefa.quantidade_total * 100, 2)
                   if tem_total and qtd_sub else 0.0)
        tarefa.percentual_concluido = min(100.0, round(pct_empresa + pct_sub, 2))

    db.session.add(tarefa)
    db.session.commit()
