"""
Motor universal de dropdowns.

Para slugs CRM (crm_*), as operações são sincronizadas bidirecionalmente
com os modelos legados (CrmOrigem etc.) para manter compatibilidade com
as FKs em Lead.  DropdownOpcao é sempre a fonte de verdade do motor.

Uso em formulários CRM:
    get_dropdown_options('crm_origem', admin_id, for_form=True)
    → retorna wrappers com .id = ext_id (= crm_origem.id) para que os
      selects do formulário gravem o FK correto em Lead.origem_id.

Uso em templates / views não-CRM:
    get_opcoes_valores('obra_status', admin_id)
    → retorna ['Em Andamento', 'Concluída', ...] (strings, com fallback)

Uso em WTForms (choices):
    get_dropdown_choices('veiculo_tipo', admin_id)
    → retorna [('Carro','Carro'), ('Caminhão','Caminhão'), ...]

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

# ---------------------------------------------------------------------------
# Metadata para todos os novos módulos
# ---------------------------------------------------------------------------
NOVOS_GRUPOS_META: list[dict] = [
    # Módulo Obras
    {'slug': 'obra_status',              'label': 'Status de Obra',             'modulo': 'obras',        'editavel': True},
    {'slug': 'cronograma_categoria',     'label': 'Categorias de Cronograma',   'modulo': 'obras',        'editavel': True},
    {'slug': 'cronograma_responsavel',   'label': 'Responsáveis de Cronograma', 'modulo': 'obras',        'editavel': True},
    {'slug': 'orcamento_obra_categoria', 'label': 'Categorias de Orçamento',    'modulo': 'obras',        'editavel': True},
    # Módulo RDO
    {'slug': 'rdo_tempo',                'label': 'Condições de Tempo',         'modulo': 'rdo',          'editavel': True},
    {'slug': 'rdo_condicao_trabalho',    'label': 'Condições de Trabalho',      'modulo': 'rdo',          'editavel': True},
    {'slug': 'rdo_status_equipamento',   'label': 'Status de Equipamento',      'modulo': 'rdo',          'editavel': True},
    # Módulo Serviços
    {'slug': 'servico_categoria',        'label': 'Categorias de Serviço',      'modulo': 'servicos',     'editavel': True},
    {'slug': 'servico_unidade_medida',   'label': 'Unidades de Medida (Serviço)', 'modulo': 'servicos',   'editavel': True},
    # Módulo Frota
    {'slug': 'veiculo_tipo',             'label': 'Tipos de Veículo',           'modulo': 'frota',        'editavel': True},
    {'slug': 'veiculo_status',           'label': 'Status de Veículo',          'modulo': 'frota',        'editavel': True},
    {'slug': 'veiculo_combustivel',      'label': 'Tipos de Combustível',       'modulo': 'frota',        'editavel': True},
    {'slug': 'custo_veiculo_tipo',       'label': 'Tipos de Custo de Veículo',  'modulo': 'frota',        'editavel': True},
    {'slug': 'manutencao_tipo',          'label': 'Tipos de Manutenção',        'modulo': 'frota',        'editavel': True},
    {'slug': 'manutencao_prioridade',    'label': 'Prioridades de Manutenção',  'modulo': 'frota',        'editavel': True},
    # Módulo Financeiro
    {'slug': 'lancamento_forma_recebimento', 'label': 'Formas de Recebimento',  'modulo': 'financeiro',   'editavel': True},
    {'slug': 'lancamento_status',        'label': 'Status de Lançamento',       'modulo': 'financeiro',   'editavel': True},
    # Módulo Almoxarifado
    {'slug': 'almoxarifado_categoria',   'label': 'Categorias de Almoxarifado', 'modulo': 'almoxarifado', 'editavel': True},
    {'slug': 'almoxarifado_unidade',     'label': 'Unidades de Medida (Almox)', 'modulo': 'almoxarifado', 'editavel': True},
    {'slug': 'almoxarifado_tipo_movimento', 'label': 'Tipos de Movimento',      'modulo': 'almoxarifado', 'editavel': True},
    # Módulo Alimentação
    {'slug': 'alimentacao_tipo',         'label': 'Tipos de Refeição',          'modulo': 'alimentacao',  'editavel': True},
    # Módulo Funcionários
    {'slug': 'funcionario_tipo',         'label': 'Tipos de Funcionário',       'modulo': 'funcionarios', 'editavel': True},
]

# Metadados combinados (CRM + todos os módulos)
TODOS_GRUPOS_META: list[dict] = CRM_GRUPOS_META + NOVOS_GRUPOS_META

# ---------------------------------------------------------------------------
# Valores padrão para seed de cada slug
# ---------------------------------------------------------------------------
_SLUG_DEFAULTS: dict[str, list[str]] = {
    'obra_status':              ['Em Andamento', 'Concluída', 'Pausada', 'Cancelada'],
    'cronograma_categoria':     ['Fundação', 'Estrutura', 'Alvenaria', 'Cobertura', 'Fachada', 'Instalações', 'Acabamento'],
    'cronograma_responsavel':   ['Empresa', 'Terceiros', 'Subempreitada'],
    'orcamento_obra_categoria': ['Mão de Obra', 'Material', 'Equipamento', 'Serviços de Terceiros', 'Alimentação', 'Transporte', 'Outros'],
    'rdo_tempo':                ['Ensolarado', 'Nublado', 'Chuvoso', 'Parcialmente Nublado', 'Garoa', 'Tempestade'],
    'rdo_condicao_trabalho':    ['Ideais', 'Adequadas', 'Difíceis', 'Inapropriadas'],
    'rdo_status_equipamento':   ['Bom', 'Regular', 'Ruim', 'Inoperante'],
    'servico_categoria':        ['Alvenaria', 'Pintura', 'Elétrica', 'Hidráulica', 'Estrutura', 'Revestimento', 'Acabamento', 'Instalações', 'Outros'],
    'servico_unidade_medida':   ['m²', 'm³', 'm', 'kg', 'ton', 'un', 'h'],
    'veiculo_tipo':             ['Carro', 'Caminhão', 'Moto', 'Van', 'Utilitário', 'Outro'],
    'veiculo_status':           ['Disponível', 'Em Uso', 'Manutenção', 'Indisponível'],
    'veiculo_combustivel':      ['Gasolina', 'Etanol', 'Diesel', 'Flex', 'GNV', 'Elétrico'],
    'custo_veiculo_tipo':       ['Combustível', 'Manutenção', 'Seguro', 'Multa', 'Lavagem', 'IPVA', 'Licenciamento', 'Pneus', 'Outros'],
    'manutencao_tipo':          ['Preventiva', 'Corretiva', 'Emergencial', 'Recall/Campanha'],
    'manutencao_prioridade':    ['Baixa', 'Média', 'Alta', 'Urgente'],
    'lancamento_forma_recebimento': ['Dinheiro', 'Cartão', 'Transferência', 'PIX', 'Boleto'],
    'lancamento_status':        ['Pendente', 'Recebido', 'Cancelado'],
    'almoxarifado_categoria':   ['Ferramentas', 'EPIs', 'Materiais de Construção', 'Elétrico', 'Hidráulico', 'Outros'],
    'almoxarifado_unidade':     ['un', 'kg', 'm', 'm²', 'm³', 'l', 'cx', 'pç'],
    'almoxarifado_tipo_movimento': ['ENTRADA', 'SAIDA', 'DEVOLUCAO', 'AJUSTE'],
    'alimentacao_tipo':         ['Café da Manhã', 'Almoço', 'Jantar', 'Lanche', 'Marmita', 'Refeição Local', 'Outros'],
    'funcionario_tipo':         ['CLT', 'PJ', 'Terceirizado', 'Estagiário'],
}

# Módulos com labels em português para exibição no hub
MODULOS_LABELS: dict[str, str] = {
    'crm':          'CRM',
    'obras':        'Obras',
    'rdo':          'RDO',
    'servicos':     'Serviços / Catálogo',
    'frota':        'Frota / Veículos',
    'financeiro':   'Financeiro',
    'almoxarifado': 'Almoxarifado',
    'alimentacao':  'Alimentação',
    'funcionarios': 'Funcionários',
}


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

    meta = next((m for m in TODOS_GRUPOS_META if m['slug'] == slug), None)
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


def get_opcoes_valores(slug: str, admin_id: int,
                       fallback: list[str] | None = None) -> list[str]:
    """Retorna lista de strings (valores) para uso em templates Jinja.

    Usa os padrões hardcoded de _SLUG_DEFAULTS como fallback quando o
    grupo não existe ou está vazio no banco (ex: tenant recém-criado
    antes da migration 175 rodar).
    """
    opcoes = get_dropdown_options(slug, admin_id)
    if opcoes:
        return [o.valor for o in opcoes]
    if fallback is not None:
        return fallback
    return list(_SLUG_DEFAULTS.get(slug, []))


def get_dropdown_choices(slug: str, admin_id: int,
                         blank_label: str | None = None) -> list[tuple[str, str]]:
    """Retorna lista de (valor, valor) para SelectField do WTForms.

    Usa defaults se o grupo não existir ou estiver vazio.
    Quando blank_label é fornecido, insere ('', blank_label) como primeiro item.
    """
    valores = get_opcoes_valores(slug, admin_id)
    choices = [(v, v) for v in valores]
    if blank_label is not None:
        choices = [('', blank_label)] + choices
    return choices


def seed_grupos_sistema(admin_id: int, commit: bool = False) -> int:
    """Cria todos os grupos de dropdown + opções padrão para um tenant.

    Idempotente: ignora grupos/opções que já existem.
    Retorna o total de opções inseridas.
    """
    from models import DropdownGrupo, DropdownOpcao
    criadas = 0

    for meta in NOVOS_GRUPOS_META:
        slug = meta['slug']
        grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
        if not grupo:
            grupo = DropdownGrupo(
                admin_id=admin_id,
                slug=slug,
                label=meta['label'],
                modulo=meta['modulo'],
                editavel=meta['editavel'],
            )
            db.session.add(grupo)
            db.session.flush()

        defaults = _SLUG_DEFAULTS.get(slug, [])
        for i, valor in enumerate(defaults, 1):
            exists = DropdownOpcao.query.filter_by(
                grupo_id=grupo.id, admin_id=admin_id, valor=valor
            ).first()
            if not exists:
                opcao = DropdownOpcao(
                    admin_id=admin_id,
                    grupo_id=grupo.id,
                    valor=valor,
                    ordem=i * 10,
                    ativo=True,
                )
                db.session.add(opcao)
                criadas += 1

    if commit:
        db.session.commit()
    else:
        db.session.flush()

    logger.info(f'[seed_grupos_sistema] admin_id={admin_id}: {criadas} opção(ões) inserida(s)')
    return criadas


def get_grupos_por_modulo(admin_id: int) -> dict[str, list[dict]]:
    """Retorna todos os grupos organizados por módulo para o hub de catálogos.

    Formato retornado:
        {
            'obras': [{'slug': 'obra_status', 'label': '...', 'total': 4}, ...],
            'rdo':   [...],
            ...
        }
    """
    from models import DropdownGrupo, DropdownOpcao
    result: dict[str, list[dict]] = {}

    for meta in TODOS_GRUPOS_META:
        slug = meta['slug']
        modulo = meta['modulo']
        grupo = DropdownGrupo.query.filter_by(slug=slug, admin_id=admin_id).first()
        total = 0
        if grupo:
            total = DropdownOpcao.query.filter_by(
                grupo_id=grupo.id, admin_id=admin_id, ativo=True
            ).count()

        entry = {
            'slug':    slug,
            'label':   meta['label'],
            'modulo':  modulo,
            'total':   total,
            'editavel': meta['editavel'],
        }
        result.setdefault(modulo, []).append(entry)

    return result


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
# Mapeamento slug → campos em Lead que referenciam o modelo legado CRM via FK
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

# ---------------------------------------------------------------------------
# Mapeamento slug → (NomeModelo, campo_string) para campos não-FK.
# Cada tupla indica qual model e campo armazena o valor como string simples.
# contar_uso_opcao usa isso para contar registros; migrar_e_excluir_opcao usa
# para atualizar strings de origem → destino antes da exclusão física.
# ---------------------------------------------------------------------------
_SLUG_STRING_FIELD_MAP: dict[str, list[tuple[str, str]]] = {
    # Obras
    'obra_status':               [('Obra', 'status')],
    'cronograma_categoria':      [('TarefaCronograma', 'categoria')],
    'cronograma_responsavel':    [('TarefaCronograma', 'responsavel')],
    'orcamento_obra_categoria':  [('OrcamentoObra', 'categoria')],
    # RDO
    'rdo_tempo':                 [('RDO', 'clima_geral')],
    'rdo_condicao_trabalho':     [('RDO', 'condicoes_trabalho')],
    'rdo_status_equipamento':    [('RDOEquipamento', 'estado_conservacao')],
    # Serviços
    'servico_categoria':         [('Servico', 'categoria')],
    'servico_unidade_medida':    [('Servico', 'unidade_medida')],
    # Frota
    'veiculo_tipo':              [('Veiculo', 'tipo')],
    'veiculo_status':            [],  # Veiculo não possui campo status string
    'veiculo_combustivel':       [('Veiculo', 'combustivel')],
    'custo_veiculo_tipo':        [('CustoVeiculo', 'tipo_custo')],
    'manutencao_tipo':           [('ManutencaoVeiculo', 'tipo_manutencao')],
    'manutencao_prioridade':     [],  # ManutencaoVeiculo não possui campo prioridade
    # Financeiro
    'lancamento_status':         [('Receita', 'status')],
    'lancamento_forma_recebimento': [('Receita', 'forma_recebimento')],
    # Almoxarifado — categorias são FK; tipo_movimento armazena código interno
    'almoxarifado_categoria':    [],
    'almoxarifado_unidade':      [],
    'almoxarifado_tipo_movimento': [],
    # Alimentação
    'alimentacao_tipo':          [('Alimentacao', 'tipo')],
    # Funcionários
    'funcionario_tipo':          [],  # Funcionario não possui campo tipo string
}


def _get_model_class(model_name: str):
    """Retorna a classe do model pelo nome, ou None se não encontrado."""
    import models as _m
    return getattr(_m, model_name, None)


def contar_uso_opcao(slug: str, opcao_id: int, admin_id: int) -> int:
    """Conta quantos registros referenciam a opção.

    Para slugs CRM, conta via ext_id (FK em Lead).
    Para slugs não-CRM, conta registros onde o campo string == opcao.valor.
    Retorna 0 quando o slug não tem mapeamento (exclusão direta permitida).
    """
    from models import DropdownOpcao, Lead
    opcao = DropdownOpcao.query.filter_by(id=opcao_id, admin_id=admin_id).first()
    if not opcao:
        return 0

    total = 0

    campos_fk = _SLUG_LEAD_FIELDS.get(slug, [])
    if campos_fk and opcao.ext_id:
        for campo in campos_fk:
            col = getattr(Lead, campo, None)
            if col is None:
                continue
            total += Lead.query.filter(
                Lead.admin_id == admin_id,
                col == opcao.ext_id,
            ).count()

    for model_name, field_name in _SLUG_STRING_FIELD_MAP.get(slug, []):
        cls = _get_model_class(model_name)
        if cls is None:
            continue
        col = getattr(cls, field_name, None)
        admin_col = getattr(cls, 'admin_id', None)
        if col is None or admin_col is None:
            continue
        try:
            total += cls.query.filter(
                admin_col == admin_id,
                col == opcao.valor,
            ).count()
        except Exception as _e:
            logger.warning('contar_uso_opcao %s.%s: %s', model_name, field_name, _e)

    return total


def migrar_e_excluir_opcao(slug: str, opcao_id: int,
                            opcao_destino_id: int, admin_id: int):
    """Migra todos os registros de opcao_id para opcao_destino_id e exclui fisicamente.

    Para slugs CRM, migra FKs em Lead.
    Para slugs não-CRM, atualiza o campo string de origem → destino.
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

    campos_fk = _SLUG_LEAD_FIELDS.get(slug, [])
    if campos_fk and opcao_origem.ext_id and opcao_destino.ext_id:
        for campo in campos_fk:
            col = getattr(Lead, campo, None)
            if col is None:
                continue
            Lead.query.filter(
                Lead.admin_id == admin_id,
                col == opcao_origem.ext_id,
            ).update({campo: opcao_destino.ext_id}, synchronize_session='fetch')

    for model_name, field_name in _SLUG_STRING_FIELD_MAP.get(slug, []):
        cls = _get_model_class(model_name)
        if cls is None:
            continue
        col = getattr(cls, field_name, None)
        admin_col = getattr(cls, 'admin_id', None)
        if col is None or admin_col is None:
            continue
        try:
            cls.query.filter(
                admin_col == admin_id,
                col == opcao_origem.valor,
            ).update({field_name: opcao_destino.valor}, synchronize_session='fetch')
        except Exception as _e:
            logger.warning('migrar_e_excluir_opcao %s.%s: %s', model_name, field_name, _e)

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


def populate_form_choices(form, admin_id: int) -> None:
    """Popula os SelectFields do form com choices do dropdown_service.

    Mapeia o nome do campo para o slug correspondente e preenche
    form.<campo>.choices com get_dropdown_choices(slug, admin_id).
    Deve ser chamado nas views GET antes de renderizar o formulário.
    """
    _FIELD_TO_SLUG: dict[str, str] = {
        'status':                   'obra_status',
        'tipo':                     'veiculo_tipo',
        'combustivel':              'veiculo_combustivel',
        'categoria':                'servico_categoria',
        'unidade_medida':           'servico_unidade_medida',
        'tipo_custo':               'custo_veiculo_tipo',
        'tipo_combustivel':         'veiculo_combustivel',
        'categoria_manutencao':     'manutencao_tipo',
        'tipo_manutencao':          'manutencao_tipo',
        'prioridade':               'manutencao_prioridade',
        'forma_recebimento':        'lancamento_forma_recebimento',
        'tempo_manha':              'rdo_tempo',
        'tempo_tarde':              'rdo_tempo',
        'tempo_noite':              'rdo_tempo',
    }
    for field_name, slug in _FIELD_TO_SLUG.items():
        field = getattr(form, field_name, None)
        if field is not None and hasattr(field, 'choices'):
            if not field.choices:
                field.choices = get_dropdown_choices(slug, admin_id)


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
