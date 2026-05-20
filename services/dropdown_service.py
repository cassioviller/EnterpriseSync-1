"""
Motor universal de dropdowns.

Para slugs CRM (crm_*), as operações são roteadas para os modelos legados
(CrmOrigem, CrmTipoObra, etc.) que são a fonte de verdade das FKs em Lead.
Para slugs genéricos, usa DropdownOpcao.
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

_CRM_CAMPOS_LEAD: dict[str, list[str]] = {
    'crm_responsavel':  ['responsavel_id', 'vendedor_id', 'orcamentista_id'],
    'crm_origem':       ['origem_id'],
    'crm_cadencia':     ['cadencia_id'],
    'crm_situacao':     ['situacao_id'],
    'crm_tipo_material': ['tipo_material_id'],
    'crm_tipo_obra':    ['tipo_obra_id'],
    'crm_motivo_perda': ['motivo_perda_id'],
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


def _crm_model(slug):
    """Retorna a classe do modelo legado CRM para o slug, ou None."""
    class_name = _CRM_MODELO_MAP.get(slug)
    if not class_name:
        return None
    import models as _m
    return getattr(_m, class_name, None)


def ensure_grupo(slug: str, admin_id: int):
    """Retorna (ou cria) o DropdownGrupo para (slug, admin_id).
    Para slugs CRM, o label e modulo são recuperados de CRM_GRUPOS_META.
    """
    from models import DropdownGrupo
    grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
    if grupo:
        return grupo

    meta = next((m for m in CRM_GRUPOS_META if m['slug'] == slug), None)
    label   = meta['label']   if meta else slug.replace('_', ' ').title()
    modulo  = meta['modulo']  if meta else 'geral'
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


def get_dropdown_options(slug: str, admin_id: int, incluir_inativos: bool = False):
    """Retorna lista de opções para o grupo identificado por `slug`.

    Para slugs CRM: retorna objetos do modelo legado (id, nome, ativo).
    Para outros slugs: retorna DropdownOpcao (tem property .nome = .valor).
    """
    crm = _crm_model(slug)
    if crm:
        q = crm.query.filter_by(admin_id=admin_id)
        if not incluir_inativos:
            q = q.filter_by(ativo=True)
        return q.order_by(crm.nome.asc()).all()

    from models import DropdownGrupo, DropdownOpcao
    grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
    if not grupo:
        return []
    q = DropdownOpcao.query.filter_by(grupo_id=grupo.id, admin_id=admin_id)
    if not incluir_inativos:
        q = q.filter_by(ativo=True)
    return q.order_by(DropdownOpcao.ordem.asc(), DropdownOpcao.id.asc()).all()


def criar_opcao(slug: str, admin_id: int, valor: str, cor: str | None = None, ordem: int = 0):
    """Cria uma nova opção. Lança ValueError se já existir."""
    crm = _crm_model(slug)
    if crm:
        existing = crm.query.filter_by(admin_id=admin_id, nome=valor).first()
        if existing:
            raise ValueError(f'Já existe uma opção "{valor}" nesta lista.')
        obj = crm(admin_id=admin_id, nome=valor, ativo=True)
        db.session.add(obj)
        db.session.flush()
        return obj

    from models import DropdownOpcao
    grupo = ensure_grupo(slug, admin_id)
    existing = DropdownOpcao.query.filter_by(
        grupo_id=grupo.id, admin_id=admin_id, valor=valor
    ).first()
    if existing:
        raise ValueError(f'Já existe uma opção "{valor}" nesta lista.')
    opcao = DropdownOpcao(
        admin_id=admin_id,
        grupo_id=grupo.id,
        valor=valor,
        cor=cor,
        ordem=ordem,
        ativo=True,
    )
    db.session.add(opcao)
    db.session.flush()
    return opcao


def atualizar_opcao(slug: str, opcao_id: int, admin_id: int, novo_valor: str, cor: str | None = None):
    """Atualiza o rótulo (e cor) de uma opção."""
    crm = _crm_model(slug)
    if crm:
        obj = crm.query.filter_by(id=opcao_id, admin_id=admin_id).first()
        if not obj:
            raise ValueError('Opção não encontrada.')
        obj.nome = novo_valor
        db.session.flush()
        return obj

    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')
    opcao.valor = novo_valor
    if cor is not None:
        opcao.cor = cor
    db.session.flush()
    return opcao


def toggle_ativo_opcao(slug: str, opcao_id: int, admin_id: int):
    """Ativa ou desativa uma opção (toggle). Retorna o novo estado ativo."""
    crm = _crm_model(slug)
    if crm:
        obj = crm.query.filter_by(id=opcao_id, admin_id=admin_id).first()
        if not obj:
            raise ValueError('Opção não encontrada.')
        obj.ativo = not obj.ativo
        db.session.flush()
        return obj.ativo

    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')
    opcao.ativo = not opcao.ativo
    db.session.flush()
    return opcao.ativo


def desativar_opcao(slug: str, opcao_id: int, admin_id: int):
    """Desativa permanentemente uma opção (sem deleção física)."""
    crm = _crm_model(slug)
    if crm:
        obj = crm.query.filter_by(id=opcao_id, admin_id=admin_id).first()
        if not obj:
            raise ValueError('Opção não encontrada.')
        obj.ativo = False
        db.session.flush()
        return obj

    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')
    opcao.ativo = False
    db.session.flush()
    return opcao


def excluir_opcao(slug: str, opcao_id: int, admin_id: int):
    """Exclui fisicamente uma opção — bloqueado se estiver em uso (CRM) ou protegida."""
    crm = _crm_model(slug)
    if crm:
        from models import Lead
        campos = _CRM_CAMPOS_LEAD.get(slug, [])
        for campo in campos:
            uso = Lead.query.filter(
                Lead.admin_id == admin_id,
                getattr(Lead, campo) == opcao_id,
            ).first()
            if uso:
                raise ValueError(
                    'Esta opção está em uso em leads e não pode ser excluída. '
                    'Use "Desativar" para ocultá-la em novos registros.'
                )
        obj = crm.query.filter_by(id=opcao_id, admin_id=admin_id).first()
        if not obj:
            raise ValueError('Opção não encontrada.')
        db.session.delete(obj)
        db.session.flush()
        return True

    from models import DropdownOpcao
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        raise ValueError('Opção não encontrada.')
    if opcao.protegido:
        raise ValueError('Esta opção é protegida e não pode ser excluída.')
    db.session.delete(opcao)
    db.session.flush()
    return True


def is_crm_slug(slug: str) -> bool:
    return slug in _CRM_MODELO_MAP
