"""Escritor único de `Obra.valor_contrato` — p9 do `PLANO-NUCLEO.md`.

## A decisão de 03/08

> Cássio, 03/08: o dono é a **Fase 6** — `ObraContratoVersao` +
> `services/contrato_obra.py` como cadeia única. A Fase 9b vira camada
> documental (PDF, assinatura, vencimento), sem listener concorrente.

Isto ratifica o que a própria 9b já assumia na premissa P1: o aditivo se
subordina à cadeia de versões, não cria uma segunda.

## Por que este módulo já existe, antes da Fase 6

Hoje **quatro** lugares escrevem o campo, cada um com sua regra:

| Onde | Quando |
|---|---|
| `event_manager.py:1195` | aprovação da proposta (e aditivo: congela medições já emitidas antes de trocar a base) |
| `views/obras.py:418` | criação manual da obra |
| `views/obras.py:955` | edição manual pelo formulário |
| `services/importacao_fisico_financeiro.py:754` | import de JSON físico-financeiro (`valor_venda`) |

O último estava **omitido do inventário da Fase 6** — quem executasse aquele
plano fecharia três portas e deixaria a quarta aberta.

Rotear os quatro por aqui **agora** torna "um único ponto de escrita"
verdadeiro antes da Fase 6 existir, e transforma a fase num acréscimo
(gravar `ObraContratoVersao` dentro desta função) em vez de uma caça a
chamadores espalhados.

## Fase 6 / Task 2 — o campo passa a ser cache do baseline versionado

`ObraContratoVersao` (models.py, Task 1) é a fonte de verdade a partir daqui.
`obra.valor_contrato` continua existindo — dezenas de templates e queries
legadas leem ele direto — mas vira um **cache** escrito só por `abrir_versao`
(chamada de dentro de `definir_valor_contrato`, nunca pelos 5 chamadores
diretamente): o valor gravado no campo é sempre `float(versão vigente.valor)`,
nunca um valor solto sem versão por trás.

### Mapeamento origem → origem_tipo

`ORIGEM_*` (abaixo) já era o vocabulário fechado de **log** deste módulo
desde a era pré-Fase 6 (p9). Em vez de inventar um segundo vocabulário para
`ObraContratoVersao.origem_tipo`, usamos o mesmo texto — `ORIGEM_TIPO` é a
identidade sobre `ORIGENS`. Isso mantém uma auditoria e a outra sincronizadas
por construção (mudar o texto de uma origem muda as duas ao mesmo tempo) e
evita a pergunta "por que o log diz X mas a versão diz Y para a mesma
escrita?". Os 5 chamadores continuam livres para escolher `ORIGEM_PROPOSTA`
vs `ORIGEM_ADITIVO` como já faziam (ex.: `event_manager.py`, que usa
`ORIGEM_ADITIVO` quando já havia contrato e `ORIGEM_PROPOSTA` quando a obra
está nascendo) — este módulo não decide isso, só espelha a escolha do
chamador no `origem_tipo` da versão. Uma origem desconhecida (5º escritor
não cadastrado) não é bloqueada nem cai num rótulo genérico: vira o próprio
texto recebido, para nada ficar oculto — a anomalia já sai logada como
warning antes disso.

## Fase 6 / Task 5 — o congelamento de base também mora no escritor único

`congelar_base_medicoes_recebidas` (Fase 0.6/D1c, extraída na Task 4) passou
a ser chamada de DENTRO de `definir_valor_contrato`, antes da escrita: toda
porta que muda o valor por aqui congela a medição já recebida no valor
antigo — a chamada explícita que morava em `event_manager.py` saiu (era a
única porta que congelava; a edição manual, por exemplo, nunca congelou).
`aprovar_aditivo` mantém a própria chamada porque não passa por
`definir_valor_contrato` (delta-zero, ver a seção do aditivo).

## Idempotência: mesmo valor não abre versão nova

`definir_valor_contrato` só chama `abrir_versao` quando o valor novo é
DIFERENTE do valor atual de `obra.valor_contrato`. Sem essa guarda, reabrir o
formulário de edição da obra e salvar sem tocar no valor (ou uma reconciliação
que roda `definir_valor_contrato` de novo com o mesmo número) abriria uma
versão por save — poluindo a régua com "mudanças" que não mudaram nada e
tornando `contrato_vigente()` incapaz de distinguir uma reprecificação real
de um clique em "salvar".
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_

from app import db
from models import AditivoContrato, MedicaoContrato, ObraContratoVersao

logger = logging.getLogger(__name__)

# Origens reconhecidas. Não é enum de banco de propósito: é vocabulário de
# log (e, desde a Task 2, também o `origem_tipo` de `ObraContratoVersao` —
# ver docstring do módulo) — vocabulário fechado é o que permite auditar
# depois "quem mudou o contrato desta obra, e por quê".
ORIGEM_PROPOSTA = 'proposta_aprovada'
ORIGEM_ADITIVO = 'aditivo'
ORIGEM_CADASTRO = 'cadastro_manual'
ORIGEM_EDICAO = 'edicao_manual'
ORIGEM_IMPORTACAO = 'importacao_fisico_financeiro'
# Fase 6 / Task 5 — obra sem NENHUMA versão cujo valor entra pelo formulário
# de edição: não é reprecificação (edicao_manual), é o contrato original
# chegando atrasado ao baseline. Distinguir os dois na régua é o que permite
# ler depois "esta obra nasceu com contrato X" vs "alguém editou para X".
ORIGEM_CONTRATO_ORIGINAL = 'contrato_original'

ORIGENS = (ORIGEM_PROPOSTA, ORIGEM_ADITIVO, ORIGEM_CADASTRO, ORIGEM_EDICAO,
           ORIGEM_IMPORTACAO, ORIGEM_CONTRATO_ORIGINAL)

# origem (vocabulário de log) → origem_tipo (coluna de ObraContratoVersao).
# Identidade deliberada — ver "Mapeamento origem → origem_tipo" acima.
ORIGEM_TIPO = {o: o for o in ORIGENS}


def abrir_versao(obra, valor, origem_tipo: str, *, origem_proposta_id=None,
                 aditivo_id=None, motivo=None, criado_por_id=None,
                 vigente_de=None, prazo_dias=None) -> ObraContratoVersao:
    """Abre uma nova versão do contrato, fechando a vigente atual.

    Ordem (é o que garante nunca haver 2 versões vigentes ao mesmo tempo,
    nem uma janela sem nenhuma vigente):
      1. fecha a versão vigente de hoje, se houver — `vigente_ate` recebe o
         `vigente_de` da nova (a janela da antiga termina exatamente onde a
         da nova começa, sem gap nem overlap);
      2. insere a nova versão, com `versao = max(versão existente da obra) +
         1` (não `atual.versao + 1` — se a obra não tinha nenhuma versão
         ainda, `atual` é `None` e isto teria que ser 1 de qualquer forma;
         usar o `max` cobre os dois casos com a mesma conta);
      3. só ENTÃO atualiza `obra.valor_contrato = float(nova.valor)` — o
         campo é cache da versão vigente, nunca escrito antes dela existir.

    Não commita — mesma regra de `definir_valor_contrato` (hoje o único
    chamador direto; ver o motivo no docstring dela).

    `obra.id` pode ainda ser `None` aqui: em pelo menos 2 dos 5 chamadores
    (a criação de obra em `event_manager.py`/`views/obras.py`, e o ramo
    "obra nova" de `services/importacao_fisico_financeiro.py`) o objeto é
    construído e `definir_valor_contrato` é chamada **antes** do próprio
    `db.session.add`/`flush` do chamador. Pior: em `importacao_fisico_...`,
    a obra já foi ADICIONADA à sessão neste ponto mas ainda está incompleta
    — `cliente_id` (NOT NULL) só é atribuído DEPOIS desta chamada. Se
    disparássemos um flush aqui (explícito ou por autoflush de uma query
    comum), a sessão tentaria inserir essa obra pela metade e estouraria a
    constraint. Por isso:
      - as duas consultas ao banco abaixo rodam dentro de `no_autoflush`,
        para não forçar a sessão a gravar a obra ainda incompleta só porque
        este módulo precisou fazer um SELECT;
      - `nova` é ligada por `obra=obra` (relationship), não por
        `obra_id=obra.id` — o SQLAlchemy resolve o FK sozinho na hora do
        flush de verdade (do chamador), na ordem certa, mesmo que `obra.id`
        seja `None` agora;
      - este módulo nunca chama `db.session.flush()` — quem decide a hora
        de gravar continua sendo o chamador, inclusive para obras novas.

    Efeito colateral do `no_autoflush` acima (achado em revisão de código,
    24/08): como as consultas SQL não veem linhas ainda não flushadas, DUAS
    chamadas a `definir_valor_contrato` para a MESMA obra dentro da MESMA
    transação, sem commit/flush entre elas, faziam a 2ª chamada não enxergar
    a versão que a 1ª tinha acabado de criar em memória — resultado: 2
    linhas `versao=1`, ambas `vigente_ate=None`, só descobertas no commit
    (ou nunca, se nada mais na mesma transação disparar autoflush antes).
    Por isso, além da consulta ao banco, esta função também varre
    `db.session.new` por `ObraContratoVersao` pendentes desta MESMA obra
    (`o.obra is obra`, comparação de identidade — funciona porque o mapa de
    identidade do SQLAlchemy garante que a mesma linha, na mesma sessão, é
    sempre o mesmo objeto Python) e reconcilia contra elas: fecha a
    pendente vigente, se houver, e usa o maior número de versão entre banco
    e pendentes. Isso cobre o caso do bug; o índice único parcial
    `uq_contrato_versao_vigente` (migration 271 / models.py) é a rede de
    segurança de banco para qualquer regressão futura deste raciocínio —
    pega no nível de constraint, não só de leitura em memória.

    Nada disso muda o resultado do caso comum — obra já existente (id !=
    None), uma única chamada por transação, os 5 chamadores de hoje: as
    mesmas consultas acertam a versão vigente e o próximo número de versão
    normalmente.

    `prazo_dias` (fix round 1 da Task 3): o prazo contratual vigente, em
    dias. Quando NÃO é passado (todos os chamadores exceto
    `aprovar_aditivo`), a versão nova HERDA o `prazo_dias` da versão que
    está fechando — sem a herança, o prazo gravado por um aditivo de prazo
    evaporaria na primeira reprecificação/proposta seguinte, que não sabe
    de prazo. Quem muda prazo passa o valor novo explicitamente.
    """
    vigente_de = vigente_de or datetime.utcnow()

    pendentes = [
        o for o in db.session.new
        if isinstance(o, ObraContratoVersao)
        and (o.obra is obra or (obra.id is not None and o.obra_id == obra.id))
    ]

    with db.session.no_autoflush:
        atual_no_banco = ObraContratoVersao.query.filter_by(
            obra_id=obra.id, admin_id=obra.admin_id, vigente_ate=None).first()

        ultima_versao_no_banco = db.session.query(
            db.func.max(ObraContratoVersao.versao)
        ).filter_by(obra_id=obra.id, admin_id=obra.admin_id).scalar()

    if prazo_dias is None:
        # Herança do prazo — ver docstring. Capturada ANTES de fechar as
        # janelas abaixo (depois delas não há mais como saber quem era a
        # vigente). Pendente vigente tem precedência sobre a do banco: se
        # ambas existissem, a pendente é a mais recente.
        anterior_vigente = next(
            (p for p in pendentes if p.vigente_ate is None), None) or atual_no_banco
        if anterior_vigente is not None:
            prazo_dias = anterior_vigente.prazo_dias

    if atual_no_banco is not None:
        atual_no_banco.vigente_ate = vigente_de

    for pendente in pendentes:
        if pendente.vigente_ate is None:
            pendente.vigente_ate = vigente_de

    ultima_versao_pendente = max((p.versao for p in pendentes), default=0)
    proxima_versao = max(ultima_versao_no_banco or 0, ultima_versao_pendente) + 1

    nova = ObraContratoVersao(
        obra=obra,
        admin_id=obra.admin_id,
        versao=proxima_versao,
        valor=Decimal(str(valor or 0)),
        prazo_dias=prazo_dias,
        vigente_de=vigente_de,
        vigente_ate=None,
        origem_tipo=origem_tipo,
        origem_proposta_id=origem_proposta_id,
        aditivo_id=aditivo_id,
        motivo=motivo,
        criado_por_id=criado_por_id,
    )
    db.session.add(nova)

    obra.valor_contrato = float(nova.valor)
    return nova


def contrato_vigente(obra_id: int, admin_id: int) -> ObraContratoVersao | None:
    """A versão vigente (`vigente_ate IS NULL`) da obra, ou `None` se a obra
    ainda não tem nenhuma versão — obra órfã de tenant (ver guarda em
    `definir_valor_contrato`) ou nunca teve `valor_contrato > 0`."""
    return ObraContratoVersao.query.filter_by(
        obra_id=obra_id, admin_id=admin_id, vigente_ate=None).first()


def valor_vigente_em(obra_id: int, admin_id: int, quando: datetime) -> Decimal:
    """O valor do contrato em vigor no instante `quando` — não necessariamente
    o vigente HOJE. `Decimal('0')` se a obra não tinha nenhuma versão àquela
    altura (antes da primeira, ou obra sem nenhuma versão)."""
    versao = ObraContratoVersao.query.filter(
        ObraContratoVersao.obra_id == obra_id,
        ObraContratoVersao.admin_id == admin_id,
        ObraContratoVersao.vigente_de <= quando,
        or_(ObraContratoVersao.vigente_ate.is_(None),
            ObraContratoVersao.vigente_ate > quando),
    ).order_by(ObraContratoVersao.versao.desc()).first()
    return versao.valor if versao is not None else Decimal('0')


def definir_valor_contrato(obra, valor, origem: str, motivo: str = '',
                           usuario_id=None) -> float:
    """Grava `obra.valor_contrato`. **Único** caminho de escrita do campo.

    Não commita: quem chama decide a transação — a aprovação de proposta, por
    exemplo, escreve o contrato no meio de uma transação que também cria
    itens de medição e cronograma, e um commit aqui a partiria no meio.

    `origem` deve ser uma das constantes deste módulo. Origem desconhecida
    não é bloqueada (não é papel deste módulo derrubar um cadastro), mas sai
    no log como anomalia — é assim que um quinto escritor aparece.

    Fase 6 / Task 2 — quando o valor muda de fato, esta função também abre
    uma `ObraContratoVersao` nova (via `abrir_versao`), fechando a vigente
    anterior: é assim que os 5 chamadores ganham o baseline versionado sem
    precisar saber que ele existe. Valor igual ao vigente é NO-OP na régua —
    ver "Idempotência" no docstring do módulo.

    Devolve o valor gravado.
    """
    anterior = float(getattr(obra, 'valor_contrato', 0) or 0)
    novo = float(valor or 0)

    if origem not in ORIGENS:
        logger.warning(
            '[p9] valor_contrato da obra %s escrito com origem desconhecida '
            '%r — se apareceu um escritor novo, ele precisa entrar em '
            'services/contrato_obra.py', getattr(obra, 'id', '?'), origem)

    if anterior == novo:
        # Nada mudou de fato — nem versiona, nem loga (mesmo comportamento
        # de antes da Task 2). Reatribuir o campo aqui é inofensivo (mesmo
        # valor) e mantém o formato antigo da função: sempre devolve com
        # `obra.valor_contrato` já sincronizado.
        obra.valor_contrato = novo
        return novo

    # Fase 6 / Task 5 — o congelamento de `valor_base` (Fase 0.6/D1c) sobe
    # para DENTRO do escritor único, como o repontamento subiu na Task 4:
    # medição JÁ RECEBIDA congela no valor ANTIGO do contrato (`anterior`,
    # capturado na entrada) ANTES de a escrita acontecer — qualquer porta
    # que mude o valor por aqui (edição manual inclusive, que nunca
    # congelou nada) para de reprecificar retroativamente o que o cliente
    # já pagou. Idempotente e no-op onde não há medição recebida (filtros
    # `valor_base IS NULL` / `recebido_no_mes` preenchido), então rodar em
    # todas as portas é barato. `aprovar_aditivo` não passa por aqui
    # (chama `abrir_versao` direto, pela razão do delta-zero) e mantém a
    # própria chamada.
    congelar_base_medicoes_recebidas(obra, anterior)

    if getattr(obra, 'admin_id', None) is None:
        # Obra órfã de tenant: ObraContratoVersao.admin_id é NOT NULL (a
        # migração 271 fez a mesma guarda no backfill — `admin_id IS NOT
        # NULL`), então não há como abrir versão aqui. Não é papel deste
        # módulo derrubar um cadastro por isso: grava só o campo, como o
        # comportamento pré-Task 2, e loga a anomalia.
        logger.warning(
            '[p9] obra %s sem admin_id — valor_contrato gravado sem versão '
            'em ObraContratoVersao', getattr(obra, 'id', '?'))
        obra.valor_contrato = novo
    else:
        origem_tipo = ORIGEM_TIPO.get(origem, origem)
        nova = abrir_versao(obra, novo, origem_tipo, motivo=motivo or None,
                            criado_por_id=usuario_id)
        # abrir_versao já gravou obra.valor_contrato = float(nova.valor).
        #
        # Fase 6 / Task 4 (fix round 1) — repontamento em TODAS as portas
        # que abrem versão por aqui (proposta, cadastro, edição, import),
        # não só no aditivo: a trilha `MedicaoContrato.contrato_versao_id`
        # tem de significar a MESMA coisa qualquer que seja a porta. Pelo
        # OBJETO `nova`, não por nova consulta: numa transação sem flush,
        # um SELECT (`contrato_vigente`) não enxergaria a versão
        # recém-criada — a mesma classe de problema que `abrir_versao`
        # reconcilia via `db.session.new`.
        _repontar_medicoes_nao_recebidas(obra, nova)

    logger.info(
        '[p9] obra %s: valor_contrato %.2f → %.2f (origem=%s, motivo=%s, '
        'usuario=%s)', getattr(obra, 'codigo', None) or getattr(obra, 'id', '?'),
        anterior, novo, origem, motivo or '—', usuario_id or '—')
    return novo


def congelar_base_medicoes_recebidas(obra, valor_anterior) -> int:
    """Congela `valor_base` das medições de contrato JÁ RECEBIDAS
    (`recebido_no_mes` preenchido) com o valor de contrato ANTERIOR, antes
    de o contrato mudar. Fase 0.6/D1c, extraída de `event_manager.py` na
    Fase 6/Task 4 — porque `aprovar_aditivo` (abaixo) precisa da MESMA
    regra: sem ela, a porta nova reprecificava retroativamente até o que o
    cliente já pagou (medição de 10% recebida sobre contrato de 100k valia
    10.000 e passava a valer 12.000, em silêncio).

    Mesma regra e mesmos filtros do bloco original:
      - só medição RECEBIDA (`recebido_no_mes` não nulo E não vazio) — a
        não recebida segue o contrato novo, que é o que aditivo significa;
      - só `valor_base IS NULL` — base já congelada não recongela: o marco
        vale o contrato da época em que foi recebido, para sempre;
      - `valor_anterior <= 0` é no-op — sem contrato anterior não há base
        para congelar (o primeiro contrato da obra não é aditivo).

    UPDATE em lote dentro de `no_autoflush` — a disciplina do módulo:
    executar SQL aqui não pode flushar objetos alheios pela metade (ver
    `abrir_versao`). Devolve a contagem congelada. Não commita.
    """
    anterior = float(valor_anterior or 0)
    if anterior <= 0 or getattr(obra, 'id', None) is None:
        return 0
    with db.session.no_autoflush:
        congeladas = MedicaoContrato.query.filter(
            MedicaoContrato.obra_id == obra.id,
            MedicaoContrato.admin_id == obra.admin_id,
            MedicaoContrato.valor_base.is_(None),
            MedicaoContrato.recebido_no_mes.isnot(None),
            MedicaoContrato.recebido_no_mes != '',
        ).update({'valor_base': anterior}, synchronize_session=False)
    if congeladas:
        # Rastro operacional de produção — preservado da extração.
        logger.info(
            "🔒 Obra %s: %d medição(ões) já emitida(s) congelada(s) "
            "na base %.2f antes do aditivo",
            obra.codigo, congeladas, anterior)
    return congeladas


# ---------------------------------------------------------------------------
# Fase 6 / Task 3 — transições do aditivo contratual.
#
# Ciclo: rascunho → aprovado | cancelado. Só a APROVAÇÃO toca o baseline
# (via `abrir_versao`, nunca por escrita direta) — abrir e cancelar um
# rascunho deixam `ObraContratoVersao` e `obra.valor_contrato` intactos.
#
# D2 do plano: o que caracteriza aditivo é a EXISTÊNCIA de contrato vigente,
# não o delta de valor. Aditivo de valor zero (prazo puro, ou supressão que
# compensa acréscimo) É aditivo: por isso `aprovar_aditivo` chama
# `abrir_versao` DIRETO, e não `definir_valor_contrato` — a guarda de
# idempotência desta última ("mesmo valor não abre versão") transformaria a
# aprovação de um aditivo delta-zero em no-op silencioso, e o baseline
# perderia o registro de que houve um aditivo ali.
#
# Mesma regra do módulo inteiro: nenhuma destas funções commita.
# ---------------------------------------------------------------------------

_NUMERO_ADITIVO_RE = re.compile(r'^AD-(\d+)$')


def _versao_vigente_da_obra(obra):
    """Versão vigente da obra: a do banco (consultada em `no_autoflush`) ou,
    se a mesma transação acabou de abrir uma e ainda não flushou, a pendente
    em `db.session.new` — a mesma reconciliação de `abrir_versao`."""
    vigente = None
    if obra.id is not None and obra.admin_id is not None:
        with db.session.no_autoflush:
            vigente = ObraContratoVersao.query.filter_by(
                obra_id=obra.id, admin_id=obra.admin_id,
                vigente_ate=None).first()
    if vigente is None:
        vigente = next(
            (v for v in db.session.new
             if isinstance(v, ObraContratoVersao) and v.vigente_ate is None
             and (v.obra is obra or (obra.id is not None and v.obra_id == obra.id))),
            None)
    return vigente


def _pendentes_da_obra(obra):
    """`AditivoContrato` ainda não flushados desta obra, em `db.session.new`.

    Mesmo raciocínio da varredura de pendentes em `abrir_versao` (ver o
    docstring dela): as consultas destas transições rodam em `no_autoflush`
    (para não flushar objetos alheios pela metade), então linhas criadas na
    MESMA transação sem flush não aparecem no SELECT — a checagem "só um
    rascunho por obra" e a numeração sequencial precisam enxergá-las por
    aqui."""
    return [
        a for a in db.session.new
        if isinstance(a, AditivoContrato)
        and (a.obra is obra or (obra.id is not None and a.obra_id == obra.id))
    ]


def _proximo_numero_aditivo(obra, pendentes):
    """`AD-{n:03d}`, com n = maior sequencial já usado + 1 — inclui os
    cancelados (número não recicla: o AD-002 depois de um AD-001 cancelado
    continua sendo AD-002) e os pendentes na sessão. Números fora do padrão
    `AD-\\d+` (não deveriam existir — só este módulo grava `numero`) são
    ignorados na conta; a `UNIQUE (obra_id, numero)` é a rede de segurança
    contra qualquer colisão que sobre."""
    with db.session.no_autoflush:
        numeros = [n for (n,) in db.session.query(AditivoContrato.numero)
                   .filter_by(obra_id=obra.id, admin_id=obra.admin_id).all()]
    numeros += [p.numero for p in pendentes if p.numero]
    maior = 0
    for numero in numeros:
        m = _NUMERO_ADITIVO_RE.match(numero or '')
        if m:
            maior = max(maior, int(m.group(1)))
    return f'AD-{maior + 1:03d}'


def _repontar_medicoes_nao_recebidas(obra, versao) -> int:
    """Fase 6 / Task 4 — marcos de `MedicaoContrato` ainda NÃO recebidos
    (`recebido_no_mes` nulo ou vazio) passam a apontar para `versao`
    (rastreabilidade: `contrato_versao_id`). Marco já recebido fica na
    versão em que nasceu — não se move.

    Pela relationship (`contrato_versao = versao`), não por UPDATE em lote:
    `versao` pode ainda não ter id (aberta na mesma transação, sem flush) —
    o SQLAlchemy resolve o FK no flush de verdade, do chamador. A consulta
    roda em `no_autoflush` pela disciplina do módulo. Devolve a contagem."""
    if obra.id is None:
        return 0
    with db.session.no_autoflush:
        nao_recebidas = MedicaoContrato.query.filter(
            MedicaoContrato.obra_id == obra.id,
            MedicaoContrato.admin_id == obra.admin_id,
            or_(MedicaoContrato.recebido_no_mes.is_(None),
                MedicaoContrato.recebido_no_mes == ''),
        ).all()
    for medicao in nao_recebidas:
        medicao.contrato_versao = versao
    return len(nao_recebidas)


def abrir_aditivo(obra, tipo: str, motivo: str, *, valor_novo=None,
                  prazo_delta_dias=None, proposta_id=None,
                  criado_por_id=None) -> AditivoContrato:
    """Abre um aditivo em `rascunho` para a obra. NÃO toca no baseline.

    Exige contrato vigente (D2: sem versão vigente não existe "aditar" —
    o valor inicial entra por `definir_valor_contrato`, não por aditivo) e
    `motivo` não-vazio. `valor_anterior` congela o valor vigente NA ABERTURA
    — é o "de quanto" do documento, imune a edições posteriores do contrato.

    `valor_novo`:
      - `tipo='prazo'` pode omitir (fica igual ao anterior — delta zero,
        que É aditivo, ver cabeçalho da seção);
      - demais tipos exigem o valor explícito — um acréscimo sem valor é
        erro de preenchimento, não um delta-zero intencional.

    Só um aditivo em `rascunho` por obra de cada vez — checagem de serviço
    (o brief descarta constraint parcial de propósito; a supressão parcial
    de concorrência é aceitável aqui).

    Não commita nem flusha — quem chama decide a transação.
    """
    if tipo not in AditivoContrato.TIPOS:
        raise ValueError(
            f'tipo de aditivo desconhecido: {tipo!r} — use um de '
            f'{AditivoContrato.TIPOS}')
    if not (motivo or '').strip():
        raise ValueError(
            'aditivo exige motivo — aditivo sem motivo é exatamente o que '
            'a Fase 6 elimina')

    vigente = _versao_vigente_da_obra(obra)
    if vigente is None:
        raise ValueError(
            f'obra {getattr(obra, "id", "?")} não tem contrato vigente — '
            'aditivo pressupõe contrato; o valor inicial entra por '
            'definir_valor_contrato')

    pendentes = _pendentes_da_obra(obra)

    with db.session.no_autoflush:
        rascunho_no_banco = AditivoContrato.query.filter_by(
            obra_id=obra.id, admin_id=obra.admin_id,
            status=AditivoContrato.STATUS_RASCUNHO).first()
    rascunho = rascunho_no_banco or next(
        (p for p in pendentes if p.status == AditivoContrato.STATUS_RASCUNHO),
        None)
    if rascunho is not None:
        raise ValueError(
            f'obra {obra.id} já tem o aditivo {rascunho.numero} em rascunho '
            '— aprove ou cancele antes de abrir outro')

    valor_anterior = Decimal(str(vigente.valor))
    if valor_novo is None:
        if tipo != 'prazo':
            raise ValueError(
                f'aditivo de tipo {tipo!r} exige valor_novo — só o de prazo '
                'puro pode omitir (mantém o valor vigente)')
        valor_novo_dec = valor_anterior
    else:
        valor_novo_dec = Decimal(str(valor_novo))

    aditivo = AditivoContrato(
        obra=obra,
        admin_id=obra.admin_id,
        numero=_proximo_numero_aditivo(obra, pendentes),
        tipo=tipo,
        status=AditivoContrato.STATUS_RASCUNHO,
        motivo=motivo.strip(),
        valor_anterior=valor_anterior,
        valor_novo=valor_novo_dec,
        prazo_delta_dias=prazo_delta_dias,
        proposta_id=proposta_id,
        criado_por_id=criado_por_id,
        criado_em=datetime.utcnow(),
    )
    db.session.add(aditivo)
    logger.info(
        '[fase6] obra %s: aditivo %s aberto (%s, %.2f → %.2f, prazo %s, '
        'usuario=%s)', obra.id, aditivo.numero, tipo, valor_anterior,
        valor_novo_dec, prazo_delta_dias if prazo_delta_dias is not None else '—',
        criado_por_id or '—')
    return aditivo


def aprovar_aditivo(aditivo, *, aprovado_por_id=None,
                    vigente_de=None) -> ObraContratoVersao | None:
    """`rascunho` → `aprovado`: o ÚNICO ponto em que o aditivo toca o
    baseline — abre a versão seguinte de `ObraContratoVersao` (fechando a
    vigente) com `origem_tipo='aditivo'` e `aditivo_id` preenchido, mesmo
    com delta zero (ver cabeçalho da seção). Devolve a versão aberta.

    Idempotente: aprovar um aditivo já `aprovado` é no-op — devolve a versão
    que a aprovação original abriu (sem recarimbar `aprovado_em` nem abrir
    outra versão). Aprovar um `cancelado` é erro: cancelado é terminal.

    `prazo_dias` da versão nova (fix round 1 — ruling: a propagação do
    prazo é desta task, porque só aqui o delta e a versão aberta se
    encontram): `base + (prazo_delta_dias or 0)`, onde `base` é o
    `prazo_dias` da versão vigente; se ela não tem (todo o parque hoje — o
    backfill da 271 deixou NULL), a base deriva de
    `(obra.data_previsao_fim - obra.data_inicio).days`. Sem
    `data_previsao_fim` também, a versão nova fica com `prazo_dias = None`
    — base desconhecida + delta é desconhecida; nunca inventar um zero. O
    delta segue auditável no próprio `AditivoContrato`. Prazo RESULTANTE
    negativo é contrato impossível (obra de duração negativa): a aprovação
    recusa com `ValueError` em vez de gravar ou clampar em silêncio, e o
    rascunho fica intacto para correção. Fora de escopo por decisão
    explícita: NÃO tocamos `Obra.data_previsao_fim` — a versão registra o
    prazo, mexer na data da obra é efeito de negócio de outra alçada.

    Não commita — quem chama decide a transação.
    """
    if aditivo.status == AditivoContrato.STATUS_CANCELADO:
        raise ValueError(
            f'aditivo {aditivo.numero} está cancelado — cancelado é '
            'terminal, abra um aditivo novo')
    if aditivo.status == AditivoContrato.STATUS_APROVADO:
        versao = None
        # Guarda `aditivo.id is not None`: com id None o filtro viraria
        # `aditivo_id IS NULL` e casaria qualquer versão SEM aditivo (o
        # backfill da 271, por exemplo) — a versão errada.
        if aditivo.id is not None:
            with db.session.no_autoflush:
                versao = ObraContratoVersao.query.filter_by(
                    aditivo_id=aditivo.id, admin_id=aditivo.admin_id).first()
        if versao is None:
            versao = next(
                (v for v in db.session.new
                 if isinstance(v, ObraContratoVersao)
                 and v.aditivo is aditivo),
                None)
        return versao

    # `aditivo.obra` pode ser lazy-load (aditivo vindo do banco): resolver
    # FORA de `no_autoflush` dispararia autoflush — a classe de bug da
    # regressão da Task 2, que o resto do módulo blinda.
    with db.session.no_autoflush:
        obra = aditivo.obra

    # Prazo da versão nova — computado ANTES de mutar o aditivo, para a
    # recusa do prazo negativo não deixar um aditivo meio-aprovado.
    vigente = _versao_vigente_da_obra(obra)
    base = vigente.prazo_dias if vigente is not None else None
    if base is None and obra.data_previsao_fim is not None:
        # data_inicio é NOT NULL no banco; só data_previsao_fim é opcional.
        base = (obra.data_previsao_fim - obra.data_inicio).days
    prazo_novo = None
    if base is not None:
        prazo_novo = base + (aditivo.prazo_delta_dias or 0)
        if prazo_novo < 0:
            raise ValueError(
                f'aditivo {aditivo.numero}: prazo resultante negativo '
                f'({base} {(aditivo.prazo_delta_dias or 0):+d} = {prazo_novo} dias) '
                '— contrato de duração negativa é impossível; corrija o '
                'delta no rascunho')
    # prazo_novo None cai na herança de abrir_versao — que herda o None da
    # vigente: mesmo resultado, nenhum valor inventado.

    # Task 4 — a MESMA proteção que a porta da proposta (event_manager) já
    # tinha desde a Fase 0.6/D1c: medição JÁ RECEBIDA congela na base
    # anterior ANTES de o contrato mudar. O valor anterior é o da versão
    # vigente NESTE momento — não `aditivo.valor_anterior`, congelado na
    # abertura: o contrato pode ter mudado entre abertura e aprovação.
    # Depois das validações acima, de propósito: uma recusa (prazo negativo)
    # não pode deixar o UPDATE do congelamento aplicado na transação.
    valor_anterior = (float(vigente.valor) if vigente is not None
                      else float(obra.valor_contrato or 0))
    congelar_base_medicoes_recebidas(obra, valor_anterior)

    aditivo.status = AditivoContrato.STATUS_APROVADO
    aditivo.aprovado_por_id = aprovado_por_id
    aditivo.aprovado_em = datetime.utcnow()

    versao = abrir_versao(
        obra, aditivo.valor_novo, ORIGEM_TIPO[ORIGEM_ADITIVO],
        aditivo_id=aditivo.id, motivo=aditivo.motivo,
        criado_por_id=aprovado_por_id, vigente_de=vigente_de,
        prazo_dias=prazo_novo)
    # `aditivo.id` pode ser None (aberto e aprovado na mesma transação, sem
    # flush): a relationship resolve o FK na hora do flush de verdade.
    versao.aditivo = aditivo

    # Task 4 — repontamento: marco não recebido passa a apontar para a
    # versão nova (rastreabilidade); o recebido fica na versão em que
    # nasceu. O VALOR do marco não muda por esta coluna — quem o muda é o
    # cache `obra.valor_contrato` (já atualizado por abrir_versao), via
    # property `MedicaoContrato.valor`.
    repontadas = _repontar_medicoes_nao_recebidas(obra, versao)

    logger.info(
        '[fase6] obra %s: aditivo %s aprovado (%.2f → %.2f, prazo %s, '
        'versão %s, %d marco(s) repontado(s), usuario=%s)',
        aditivo.obra_id or getattr(obra, 'id', '?'),
        aditivo.numero, aditivo.valor_anterior, aditivo.valor_novo,
        prazo_novo if prazo_novo is not None else '—',
        versao.versao, repontadas, aprovado_por_id or '—')
    return versao


def cancelar_aditivo(aditivo) -> AditivoContrato:
    """`rascunho` → `cancelado`. NÃO toca no baseline — cancelar desiste do
    documento antes de ele produzir efeito; a linha fica na tabela como
    registro do que foi cogitado (o número não recicla).

    Idempotente: cancelar um já `cancelado` é no-op. Cancelar um `aprovado`
    é erro — aprovado já mexeu no baseline; desfazer exige um aditivo novo
    em sentido contrário, nunca apagar história.

    Não commita — quem chama decide a transação.
    """
    if aditivo.status == AditivoContrato.STATUS_APROVADO:
        raise ValueError(
            f'aditivo {aditivo.numero} já foi aprovado e mexeu no baseline '
            '— para reverter, abra um aditivo novo em sentido contrário')
    if aditivo.status == AditivoContrato.STATUS_CANCELADO:
        return aditivo

    aditivo.status = AditivoContrato.STATUS_CANCELADO
    logger.info('[fase6] obra %s: aditivo %s cancelado em rascunho',
                aditivo.obra_id or getattr(aditivo.obra, 'id', '?'),
                aditivo.numero)
    return aditivo
