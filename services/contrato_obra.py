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
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_

from app import db
from models import ObraContratoVersao

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

ORIGENS = (ORIGEM_PROPOSTA, ORIGEM_ADITIVO, ORIGEM_CADASTRO, ORIGEM_EDICAO,
           ORIGEM_IMPORTACAO)

# origem (vocabulário de log) → origem_tipo (coluna de ObraContratoVersao).
# Identidade deliberada — ver "Mapeamento origem → origem_tipo" acima.
ORIGEM_TIPO = {o: o for o in ORIGENS}


def abrir_versao(obra, valor, origem_tipo: str, *, origem_proposta_id=None,
                 aditivo_id=None, motivo=None, criado_por_id=None,
                 vigente_de=None) -> ObraContratoVersao:
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
        abrir_versao(obra, novo, origem_tipo, motivo=motivo or None,
                    criado_por_id=usuario_id)
        # abrir_versao já gravou obra.valor_contrato = float(nova.valor).

    logger.info(
        '[p9] obra %s: valor_contrato %.2f → %.2f (origem=%s, motivo=%s, '
        'usuario=%s)', getattr(obra, 'codigo', None) or getattr(obra, 'id', '?'),
        anterior, novo, origem, motivo or '—', usuario_id or '—')
    return novo
