"""
Motor universal de dropdowns.

Para slugs CRM (crm_*), as operações são sincronizadas bidirecionalmente
com os modelos legados (CrmOrigem etc.) para manter compatibilidade com
as FKs em Lead.  DropdownOpcao é sempre a fonte de verdade do motor.

Uso em formulários CRM:
    get_dropdown_options('crm_origem', admin_id, for_form=True)
    → retorna wrappers com .id = ext_id (= crm_origem.id) para que os
      selects do formulário gravem o FK correto em Lead.origem_id.

Uso na tela de gestão (/cadastros/dropdowns/<slug>):
    get_dropdown_options('crm_origem', admin_id, incluir_inativos=True)
    → retorna DropdownOpcao "crus" com .id = opcao.id (usado nas rotas CRUD).
"""
from __future__ import annotations
import logging
from app import db

logger = logging.getLogger(__name__)

_CRM_MODELO_MAP: dict[str, str] = {
    'crm_responsavel':  'CrmResponsavel',
    'crm_origem':       'CrmOrigem',
    'crm_cadencia':     'CrmCadencia',
    'crm_situacao':     'CrmSituacao',
    'crm_tipo_material': 'CrmTipoMaterial',
    'crm_tipo_obra':    'CrmTipoObra',
    'crm_motivo_perda': 'CrmMotivoPerda',
}

CRM_GRUPOS_META: list[dict] = [
    {'slug': 'crm_responsavel',   'label': 'Responsáveis',      'modulo': 'crm', 'editavel': True},
    {'slug': 'crm_origem',        'label': 'Origens',            'modulo': 'crm', 'editavel': True},
    {'slug': 'crm_cadencia',      'label': 'Cadências',          'modulo': 'crm', 'editavel': True},
    {'slug': 'crm_situacao',      'label': 'Situações',          'modulo': 'crm', 'editavel': True},
    {'slug': 'crm_tipo_material', 'label': 'Tipos de Material',  'modulo': 'crm', 'editavel': True},
    {'slug': 'crm_tipo_obra',     'label': 'Tipos de Obra',      'modulo': 'crm', 'editavel': True},
    {'slug': 'crm_motivo_perda',  'label': 'Motivos de Perda',   'modulo': 'crm', 'editavel': True},
]


def _crm_model(slug: str):
    """Retorna a classe do modelo legado CRM para o slug, ou None."""
    class_name = _CRM_MODELO_MAP.get(slug)
    if not class_name:
        return None
    import models as _m
    return getattr(_m, class_name, None)


def is_crm_slug(slug: str) -> bool:
    return slug in _CRM_MODELO_MAP


def ensure_grupo(slug: str, admin_id: int):
    """Retorna (ou cria) o DropdownGrupo para (slug, admin_id)."""
    from models import DropdownGrupo
    grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
    if grupo:
        return grupo

    meta = next((m for m in CRM_GRUPOS_META if m['slug'] == slug), None)
    label    = meta['label']    if meta else slug.replace('_', ' ').title()
    modulo   = meta['modulo']   if meta else 'geral'
    editavel = meta['editavel'] if meta else True

    grupo = DropdownGrupo(
        admin_id=admin_id,
        slug=slug,
        label=label,
        modulo=modulo,
        editavel=editavel,
    )
    db.session.add(grupo)
    db.session.flush()
    return grupo


def _next_ordem(grupo_id: int) -> int:
    result = db.session.execute(
        db.text('SELECT COALESCE(MAX(ordem), 0) FROM dropdown_opcao WHERE grupo_id = :gid'),
        {'gid': grupo_id}
    ).scalar() or 0
    return result + 10


def get_dropdown_options(slug: str, admin_id: int,
                         incluir_inativos: bool = False,
                         for_form: bool = False):
    """Retorna opções para o grupo+admin a partir de DropdownOpcao.

    for_form=True e slug CRM: retorna wrappers com .id = ext_id para que
    os selects gravem o FK correto em Lead (ex: Lead.origem_id).
    """
    from models import DropdownGrupo, DropdownOpcao
    grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
    if not grupo:
        return []

    q = DropdownOpcao.query.filter_by(grupo_id=grupo.id, admin_id=admin_id)
    if not incluir_inativos:
        q = q.filter_by(ativo=True)
    opcoes = q.order_by(DropdownOpcao.ordem.asc(), DropdownOpcao.id.asc()).all()

    if for_form and slug in _CRM_MODELO_MAP:
        from types import SimpleNamespace
        return [
            SimpleNamespace(
                id=o.ext_id if o.ext_id else o.id,
                nome=o.valor,
                ativo=o.ativo,
            )
            for o in opcoes
        ]
    return opcoes


def criar_opcao(slug: str, admin_id: int, valor: str,
                cor: str | None = None, ordem: int | None = None):
    """Cria nova opção no motor e, para slugs CRM, sincroniza no modelo legado."""
    from models import DropdownGrupo, DropdownOpcao
    grupo = ensure_grupo(slug, admin_id)

    existing = DropdownOpcao.query.filter_by(
        grupo_id=grupo.id, admin_id=admin_id, valor=valor
    ).first()
    if existing:
        raise ValueError(f'Já existe uma opção "{valor}" nesta lista.')

    if ordem is None:
        ordem = _next_ordem(grupo.id)

    ext_id = None
    crm = _crm_model(slug)
    if crm:
        leg = crm.query.filter_by(admin_id=admin_id, nome=valor).first()
        if leg:
            ext_id = leg.id
        else:
            leg = crm(admin_id=admin_id, nome=valor, ativo=True)
            db.session.add(leg)
            db.session.flush()
            ext_id = leg.id

    opcao = DropdownOpcao(
        admin_id=admin_id,
        grupo_id=grupo.id,
        valor=valor,
        cor=cor,
        ordem=ordem,
        ativo=True,
        ext_id=ext_id,
    )
    db.session.add(opcao)
    db.session.flush()
    return opcao


def atualizar_opcao(slug: str, opcao_id: int, admin_id: int,
                    novo_valor: str, cor: str | None = None):
    """Atualiza valor/cor e sincroniza no modelo legado (CRM)."""
    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')

    crm = _crm_model(slug)
    if crm and opcao.ext_id:
        leg = crm.query.filter_by(id=opcao.ext_id, admin_id=admin_id).first()
        if leg:
            leg.nome = novo_valor

    opcao.valor = novo_valor
    if cor is not None:
        opcao.cor = cor
    db.session.flush()
    return opcao


def toggle_ativo_opcao(slug: str, opcao_id: int, admin_id: int):
    """Ativa/desativa uma opção e sincroniza no modelo legado. Retorna novo estado."""
    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')

    novo = not opcao.ativo
    opcao.ativo = novo

    crm = _crm_model(slug)
    if crm and opcao.ext_id:
        leg = crm.query.filter_by(id=opcao.ext_id, admin_id=admin_id).first()
        if leg:
            leg.ativo = novo

    db.session.flush()
    return novo


def desativar_opcao(slug: str, opcao_id: int, admin_id: int):
    """Desativa permanentemente uma opção (sem exclusão física)."""
    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')

    opcao.ativo = False
    crm = _crm_model(slug)
    if crm and opcao.ext_id:
        leg = crm.query.filter_by(id=opcao.ext_id, admin_id=admin_id).first()
        if leg:
            leg.ativo = False

    db.session.flush()
    return opcao


def excluir_opcao(slug: str, opcao_id: int, admin_id: int):
    """Política: não há exclusão física — delega para desativar."""
    return desativar_opcao(slug, opcao_id, admin_id)


# ---------------------------------------------------------------------------
# Mapeamento slug → campos em Lead que referenciam o modelo legado CRM
# Cada entrada é uma lista de nomes de coluna em Lead que usam o ext_id do
# slug como FK.  Adicionar novos módulos aqui quando migrarem para o motor.
# ---------------------------------------------------------------------------
_SLUG_LEAD_FIELDS: dict[str, list[str]] = {
    'crm_responsavel':   ['responsavel_id', 'vendedor_id', 'orcamentista_id'],
    'crm_origem':        ['origem_id'],
    'crm_cadencia':      ['cadencia_id'],
    'crm_situacao':      ['situacao_id'],
    'crm_tipo_material': ['tipo_material_id'],
    'crm_tipo_obra':     ['tipo_obra_id'],
    'crm_motivo_perda':  ['motivo_perda_id'],
}


def contar_uso_opcao(slug: str, opcao_id: int, admin_id: int) -> int:
    """Conta quantos registros referenciam a opção pelo seu ext_id.

    Retorna 0 quando o slug não tem mapeamento ainda (exclusão direta permitida).
    """
    from models import DropdownOpcao, Lead
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao or not opcao.ext_id:
        return 0

    campos = _SLUG_LEAD_FIELDS.get(slug)
    if not campos:
        return 0

    total = 0
    for campo in campos:
        col = getattr(Lead, campo, None)
        if col is None:
            continue
        total += Lead.query.filter(
            Lead.admin_id == admin_id,
            col == opcao.ext_id,
        ).count()
    return total


def migrar_e_excluir_opcao(slug: str, opcao_id: int,
                            opcao_destino_id: int, admin_id: int):
    """Migra todos os registros de opcao_id para opcao_destino_id e exclui fisicamente.

    Executa tudo em uma única transação (flush sem commit — caller faz o commit).
    Raises ValueError para entradas inválidas.
    """
    from models import DropdownOpcao, Lead

    opcao_origem = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao_origem:
        raise ValueError('Opção de origem não encontrada.')

    opcao_destino = DropdownOpcao.query.filter_by(id=opcao_destino_id, admin_id=admin_id).first()
    if not opcao_destino:
        raise ValueError('Opção de destino não encontrada.')

    if opcao_origem.id == opcao_destino.id:
        raise ValueError('Origem e destino não podem ser a mesma opção.')

    if opcao_origem.grupo_id != opcao_destino.grupo_id:
        raise ValueError('A opção de destino deve pertencer ao mesmo grupo que a opção excluída.')

    campos = _SLUG_LEAD_FIELDS.get(slug, [])

    if campos and opcao_origem.ext_id and opcao_destino.ext_id:
        for campo in campos:
            col = getattr(Lead, campo, None)
            if col is None:
                continue
            Lead.query.filter(
                Lead.admin_id == admin_id,
                col == opcao_origem.ext_id,
            ).update({campo: opcao_destino.ext_id}, synchronize_session='fetch')

    crm = _crm_model(slug)
    if crm and opcao_origem.ext_id:
        leg = crm.query.filter_by(id=opcao_origem.ext_id, admin_id=admin_id).first()
        if leg:
            db.session.delete(leg)

    db.session.delete(opcao_origem)
    db.session.flush()
    logger.info(
        'migrar_e_excluir_opcao slug=%s opcao_id=%s → destino=%s admin=%s',
        slug, opcao_id, opcao_destino_id, admin_id,
    )


def mover_opcao(slug: str, opcao_id: int, admin_id: int, direcao: str):
    """Troca a ordem de uma opção com a vizinha (direcao: 'cima' | 'baixo')."""
    from models import DropdownGrupo, DropdownOpcao
    grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
    if not grupo:
        raise ValueError('Grupo não encontrado.')

    todas = (DropdownOpcao.query
             .filter_by(grupo_id=grupo.id, admin_id=admin_id)
             .order_by(DropdownOpcao.ordem.asc(), DropdownOpcao.id.asc())
             .all())

    idx = next((i for i, o in enumerate(todas) if o.id == opcao_id), None)
    if idx is None:
        raise ValueError('Opção não encontrada.')

    if direcao == 'cima' and idx > 0:
        a, b = todas[idx], todas[idx - 1]
        a.ordem, b.ordem = b.ordem, a.ordem
    elif direcao == 'baixo' and idx < len(todas) - 1:
        a, b = todas[idx], todas[idx + 1]
        a.ordem, b.ordem = b.ordem, a.ordem

    db.session.flush()
