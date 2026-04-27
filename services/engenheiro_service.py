"""
services/engenheiro_service.py — Task #173 / #178

Helper para resolver os dados do engenheiro responsável que aparece no
rodapé/PDF de uma proposta. Após Task #178 a única fonte de verdade é
o cadastro `EngenheiroResponsavel` (Task #173). A regra de prioridade
ficou:

  1. Proposta.engenheiro_id          (override por proposta)
  2. ConfiguracaoEmpresa.engenheiro_padrao_id  (padrão da empresa)
  3. (vazio) — sem engenheiro configurado.

Os campos legados `engenheiro_*` da `ConfiguracaoEmpresa` foram
removidos do schema e não são mais consultados.

Mantém os templates PDF agnósticos: todos consomem `engenheiro_dados`,
um dict simples com nome/crea/email/telefone/endereco/website e a
imagem opcional `assinatura_base64`.
"""
from typing import Optional, Dict, Any


def _vazio(d: Dict[str, Any]) -> bool:
    """True se o dict não tem nenhum dado textual relevante."""
    chaves = ('nome', 'crea', 'email', 'telefone', 'endereco', 'website')
    return not any((d.get(k) or '').strip() for k in chaves)


def _from_engenheiro(engenheiro) -> Dict[str, Any]:
    return {
        'nome': (engenheiro.nome or '').strip(),
        'crea': (engenheiro.crea or '').strip(),
        'email': (engenheiro.email or '').strip(),
        'telefone': (engenheiro.telefone or '').strip(),
        'endereco': (engenheiro.endereco or '').strip(),
        'website': (engenheiro.website or '').strip(),
        'assinatura_base64': (engenheiro.assinatura_base64 or '').strip(),
        'fonte': 'engenheiro_responsavel',
        'engenheiro_id': engenheiro.id,
    }


def _vazio_payload() -> Dict[str, Any]:
    return {
        'nome': '', 'crea': '', 'email': '', 'telefone': '',
        'endereco': '', 'website': '', 'assinatura_base64': '',
        'fonte': 'vazio', 'engenheiro_id': None,
    }


def obter_engenheiro_dados(proposta=None, config_empresa=None) -> Dict[str, Any]:
    """Retorna o dict de dados do engenheiro a usar no PDF/rodapé.

    Args:
        proposta: instância de Proposta (ou None). Se tiver engenheiro_id,
            tem prioridade absoluta (override por proposta).
        config_empresa: instância de ConfiguracaoEmpresa (ou None). Se
            tiver engenheiro_padrao_id, é o segundo nível.

    Sempre devolve um dict (nunca None) com chaves estáveis para o
    template; valores podem ser strings vazias quando nada está
    configurado.
    """
    # Import local para evitar ciclo no import-time
    from models import EngenheiroResponsavel

    # admin_id de defesa: usado para garantir que NUNCA resolveremos um
    # engenheiro de outro tenant (mesmo se um id manual sobrar no banco).
    admin_id = (
        getattr(proposta, 'admin_id', None)
        or getattr(config_empresa, 'admin_id', None)
    )

    def _buscar(eng_id):
        if not eng_id or admin_id is None:
            return None
        return EngenheiroResponsavel.query.filter_by(
            id=eng_id, admin_id=admin_id
        ).first()

    # 1) Override da proposta — respeita ativo=True (engenheiro inativado
    # cai automaticamente no padrão da empresa).
    if proposta is not None:
        eng = _buscar(getattr(proposta, 'engenheiro_id', None))
        if eng is not None and eng.ativo:
            return _from_engenheiro(eng)

    # 2) Padrão da empresa — também respeita ativo=True.
    if config_empresa is not None:
        eng = _buscar(getattr(config_empresa, 'engenheiro_padrao_id', None))
        if eng is not None and eng.ativo:
            return _from_engenheiro(eng)

    # 3) Sem engenheiro configurado.
    return _vazio_payload()


def listar_engenheiros_ativos(admin_id: int):
    """Util para popular selects (apenas ativos do tenant, ordem alfabética)."""
    from models import EngenheiroResponsavel
    return (
        EngenheiroResponsavel.query
        .filter_by(admin_id=admin_id, ativo=True)
        .order_by(EngenheiroResponsavel.nome.asc())
        .all()
    )


def listar_engenheiros(admin_id: int, incluir_inativos: bool = True):
    """Lista para CRUD: todos do tenant (default) ou só ativos."""
    from models import EngenheiroResponsavel
    q = EngenheiroResponsavel.query.filter_by(admin_id=admin_id)
    if not incluir_inativos:
        q = q.filter_by(ativo=True)
    return q.order_by(
        EngenheiroResponsavel.ativo.desc(),
        EngenheiroResponsavel.nome.asc(),
    ).all()
