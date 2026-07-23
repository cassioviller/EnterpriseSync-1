#!/usr/bin/env python3
"""Centro de custo administrativo do tenant — SIGE Fase 4.

O sistema tem DOIS modelos de centro de custo, sem relação entre si:

  * `CentroCusto` (models.py:706) — eixo financeiro. É o usado por
    `GestaoCustoFilho.centro_custo_id` (models.py:5303), `FluxoCaixa`
    (models.py:793), `CustoObra` (models.py:669) e `Receita`.
  * `CentroCustoContabil` (models.py:2541) — eixo contábil, de partidas
    dobradas. `contabilidade_utils.py:164-173` cria um por obra na aprovação
    da proposta.

Esta fase mexe apenas no PRIMEIRO. Unificar os dois é decisão de outra fase;
misturá-los aqui esconderia o problema em vez de resolvê-lo.

O centro administrativo é o destino legítimo do custo que não pertence a
obra nenhuma: folha, estoque, escritório. Antes da Fase 4 esse custo não
tinha destino — ficava com `obra_id IS NULL` e sumia do orçado×real sem
erro e sem alerta (`DEVOLUTIVA.md` R4).

Nota sobre o nome: `DEVOLUTIVA.md:236` propõe "Veks Adm". Deliberadamente
não usamos isso — "Veks" é o nome de UM tenant, e o SIGE é multi-tenant. O
nome é derivado da empresa de cada tenant.
"""
import logging

logger = logging.getLogger('centro_custo')

CODIGO_ADMINISTRATIVO = 'ADM'
TIPO_ADMINISTRATIVO = 'administrativo'


def _nome_da_empresa(admin_id):
    """Nome legível do tenant, para rotular o centro."""
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config and (config.nome_empresa or '').strip():
        return config.nome_empresa.strip()
    admin = db.session.get(Usuario, admin_id)
    return (getattr(admin, 'nome', None) or f'Empresa {admin_id}').strip()


def centro_custo_administrativo(admin_id, criar=True):
    """Devolve o `CentroCusto` administrativo do tenant.

    `criar=True` (padrão) cria na primeira chamada e faz `flush` — NÃO faz
    `commit`: quem chamou decide a transação, como o resto do módulo de
    custos (`utils/financeiro_integration.py:216`).

    `criar=False` só consulta — usado por relatório e por validação, que não
    podem ter efeito colateral.

    Falha fechada: `admin_id` vazio devolve None. Nunca "acha o mais
    provável".
    """
    if not admin_id:
        return None

    from app import db
    from models import CentroCusto

    centro = CentroCusto.query.filter_by(
        admin_id=admin_id, tipo=TIPO_ADMINISTRATIVO).first()
    if centro or not criar:
        return centro

    centro = CentroCusto(
        admin_id=admin_id,
        codigo=CODIGO_ADMINISTRATIVO,
        nome=f'Administração — {_nome_da_empresa(admin_id)}'[:100],
        descricao=('Destino dos custos que não pertencem a nenhuma obra: '
                   'folha administrativa, estoque, despesas de escritório. '
                   'Criado pela Fase 4 (centro de custo obrigatório).'),
        tipo=TIPO_ADMINISTRATIVO,
        obra_id=None,
        ativo=True,
    )
    db.session.add(centro)
    db.session.flush()
    logger.info('Centro administrativo criado para tenant %s (id=%s)',
                admin_id, centro.id)
    return centro


def id_do_centro_administrativo(admin_id, criar=True):
    """Atalho: só o id, ou None."""
    centro = centro_custo_administrativo(admin_id, criar=criar)
    return centro.id if centro else None
