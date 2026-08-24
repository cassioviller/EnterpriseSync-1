"""Fase 6 / Task 10 — cadeia de revisões do Orçamento.

Antes desta fase, revisar um orçamento era `duplicar`: uma cópia integral que
nascia órfã, com o título `"… (cópia)"` e nenhum vínculo com o original. O
custo copiado ficava correto e a HISTÓRIA se perdia — não havia como responder
"de qual revisão este preço veio" nem "quais são as revisões deste orçamento",
que é exatamente a pergunta que o aditivo faz quando o contrato muda.

A cadeia é dupla de propósito:

- ``revisao_de_id`` é o **elo**: a revisão imediatamente anterior. Guarda a
  ordem.
- ``origem_id`` é o **atalho**: a **raiz** da cadeia. Guarda o agrupamento —
  ``filter_by(origem_id=raiz.id)`` devolve a cadeia inteira sem subir a
  corrente elo a elo.

Nenhum dos dois substitui o outro, e os dois são uma coluna indexada.

A mesma ideia desce para o item (``orcamento_item.item_origem_id``): sem ela,
o diff entre duas revisões (Task 12) teria de casar item por **descrição** — e
descrição é texto editável, então "mantido" e "suprimido + incluído" ficariam
indistinguíveis assim que alguém corrigisse uma vírgula no nome do serviço.

Este módulo não commita: quem chama é dono da transação.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from models import Orcamento, OrcamentoItem, db

logger = logging.getLogger(__name__)

# "Galpão industrial (rev. 2)" → "Galpão industrial". Sem isto, a rev. 3 de uma
# rev. 2 viraria "… (rev. 2) (rev. 3)" e o título cresceria a cada revisão.
_SUFIXO_REV = re.compile(r'\s*\(rev\.\s*\d+\)\s*$', re.IGNORECASE)

# Campos do item que a revisão carrega. Extraída da rota `duplicar` original
# para que o dia em que alguém acrescentar uma coluna ao item exista UM lugar
# a atualizar — e não dois que divergem em silêncio.
_CAMPOS_DO_ITEM = (
    'ordem', 'servico_id', 'descricao', 'unidade', 'quantidade',
    'imposto_pct', 'margem_pct', 'observacao',
    'cronograma_template_override_id',
    # Task #18 — inclusos/exclusos por serviço
    'itens_inclusos', 'itens_exclusos',
    # Task #36 — medição dimensional
    'tipo_medicao_override', 'dim_largura', 'dim_comprimento',
    'dim_perimetro', 'dim_pe_direito', 'dim_area_manual',
)


def _gerar_numero(admin_id: int) -> str:
    """Número novo para a revisão, no formato do tenant.

    Espelha `views.orcamentos_views._gerar_numero`. Duplicado de propósito:
    importar a view a partir do serviço inverteria a dependência (view →
    serviço) e criaria ciclo de import com o blueprint.
    """
    ano = date.today().year
    base = f"ORC-{ano}-"
    count = Orcamento.query.filter_by(admin_id=admin_id).count() + 1
    while True:
        candidato = f"{base}{count:04d}"
        if not Orcamento.query.filter_by(
                admin_id=admin_id, numero=candidato).first():
            return candidato
        count += 1


def raiz_da_cadeia(orc: Orcamento) -> int:
    """Id da raiz da cadeia a que `orc` pertence.

    A raiz é ela mesma quando `origem_id` é NULL — é assim que todo orçamento
    pré-existente à migration 274 se comporta, sem backfill nenhum.
    """
    return orc.origem_id or orc.id


def criar_revisao(orc: Orcamento, admin_id: int, motivo: str | None = None
                  ) -> Orcamento:
    """Cria a próxima revisão de `orc`, copiando o conteúdo e gravando a cadeia.

    Faz tudo o que `duplicar` fazia (overrides, composição, dimensionais,
    template de cronograma) **mais** a linhagem: `origem_id`, `revisao_de_id`,
    `versao`, `motivo_revisao` no orçamento e `item_origem_id` em cada item.

    A revisão nasce em `rascunho` e **destravada**, mesmo que a anterior esteja
    travada — criar revisão é justamente o caminho oferecido a quem esbarra na
    trava da Task 11.

    `versao` conta a CADEIA, não os filhos diretos: a revisão de uma v2 é v3,
    ainda que a v2 já tenha outra revisão. Duas revisões da mesma versão podem
    empatar o número, e isso é aceito — o `numero` do documento é único e é ele
    que identifica; `versao` é ordem de leitura, não chave.

    Não commita. Devolve o orçamento novo, já com os itens e os totais
    recalculados.
    """
    from services.orcamento_view_service import recalcular_orcamento

    versao_nova = int(orc.versao or 1) + 1
    titulo_base = _SUFIXO_REV.sub('', orc.titulo or '').strip()

    novo = Orcamento(
        admin_id=admin_id,
        numero=_gerar_numero(admin_id),
        titulo=f"{titulo_base} (rev. {versao_nova})"[:255],
        descricao=orc.descricao,
        cliente_id=orc.cliente_id,
        cliente_nome=orc.cliente_nome,
        imposto_pct_global=orc.imposto_pct_global,
        margem_pct_global=orc.margem_pct_global,
        criado_por=getattr(orc, 'criado_por', None),
        status='rascunho',
        origem_id=raiz_da_cadeia(orc),
        revisao_de_id=orc.id,
        versao=versao_nova,
        motivo_revisao=(motivo or None),
        travado_em=None,
    )
    db.session.add(novo)
    db.session.flush()

    for it in orc.itens:
        campos = {c: getattr(it, c) for c in _CAMPOS_DO_ITEM}
        db.session.add(OrcamentoItem(
            admin_id=admin_id,
            orcamento_id=novo.id,
            # `or []` e não `getattr` direto: composicao_snapshot NULL em item
            # legado viraria None e quebraria o recálculo.
            composicao_snapshot=it.composicao_snapshot or [],
            item_origem_id=it.id,
            **campos,
        ))
    db.session.flush()
    recalcular_orcamento(novo)
    logger.info(
        "[fase6/T10] orcamento %s (v%s) revisado como %s (v%s) — raiz %s, "
        "motivo=%r", orc.id, orc.versao, novo.id, versao_nova,
        novo.origem_id, motivo)
    return novo
