"""Uma FK vinda de formulário só entra se for do tenant de quem envia.

O padrão nasceu em `gestao_custos_views.py:550`, escrito para fechar um ataque
real: um POST forjado com `obra_id` de outra empresa prendia o custo lá, e
`sincronizar_obra_do_pai` propagava para o pai, disparando `recalcular_obra` no
snapshot orçado×real da vítima. A correção entrou naquela função e **não** nas
irmãs — `novo()` e `editar()` do mesmo arquivo ficaram de fora, e o mesmo
buraco existia em transporte, almoxarifado e financeiro.

Aqui o padrão vira helper, para não haver uma nona cópia com a nona variação.
"""
from flask import abort

__all__ = ['fk_do_tenant']


def fk_do_tenant(modelo, valor, admin_id, *, campo, obrigatorio=False):
    """Valida que `valor` é um id de `modelo` pertencente a `admin_id`.

    Devolve o id como `int`, ou `None` para valor vazio quando não obrigatório.
    Aborta com 400 e mensagem GENÉRICA quando o id não é do tenant: dizer
    "obra de outro tenant" confirmaria a existência dela. Mesma doutrina do
    404-em-vez-de-403 de `_rdo_do_tenant_ou_404` e de `obra_required`.
    """
    if valor in (None, '', b''):
        if obrigatorio:
            abort(400, f'{campo}: obrigatório.')
        return None

    try:
        ident = int(valor)
    except (TypeError, ValueError):
        abort(400, f'{campo} inválido.')

    if not admin_id:
        # Sem tenant resolvido não há como validar — falha fechada.
        abort(403)

    existe = modelo.query.filter_by(id=ident, admin_id=admin_id).first()
    if not existe:
        abort(400, f'{campo} inválido.')
    return ident
