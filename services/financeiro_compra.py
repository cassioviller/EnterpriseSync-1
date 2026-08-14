"""Financeiro da compra — o chokepoint da Fase 2 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-14-financeiro-dois-fluxos-design.md

Até aqui a `ContaPagar` de uma compra nascia em `compras_views.py:305`, no mesmo
request do formulário de emissão: sem material, sem nota, sem conferente. Este
módulo é o único lugar por onde a obrigação de compra passa a nascer, ser
liberada e ser baixada — no molde de `services/recebimento_pedido.py` (Fase 1) e
`services/requisicao_compra.py` (Fase 3).

Nesta etapa (F2) mora aqui só a leitura do regime. O documento, as validações e
a liberação chegam na F3; a tríade que barra o pagamento, na F4.
"""

# Os dois fluxos, como valor carimbado em `pedido_compra.fluxo_pagamento`.
# São strings e não Enum nativo pelo mesmo motivo que `situacao_recebimento` da
# Fase 1: estender enum nativo no Postgres é migration própria (a 245 foi a
# primeira do repositório a fazer isso), e o ganho não paga o custo para um
# domínio de dois valores.
FATURADO = 'faturado'
ADIANTAMENTO = 'adiantamento'
FLUXOS_VALIDOS = {FATURADO, ADIANTAMENTO}


def fluxo_do_tenant(admin_id):
    """O tenant está no regime de dois fluxos AGORA?

    Uma função só, para que os pontos que criam `PedidoCompra` não leiam a flag
    por conta própria — dois lugares lendo a mesma regra é dois lugares onde ela
    pode divergir. Espelha `services.recebimento_pedido.regime_do_tenant`.

    O valor devolvido decide o que é CARIMBADO em `pedido_compra.fluxo_pagamento`
    e nunca mais é reconsultado para aquele pedido: desligar a flag depois não
    reinterpreta adiantamento já pago como compra faturada.

    Falha FECHADA para o regime antigo — ver o docstring do script da flag.
    """
    from scripts.flag_financeiro_dois_fluxos import financeiro_dois_fluxos_ativo
    return bool(financeiro_dois_fluxos_ativo(admin_id))


def fluxo_do_pedido_novo(admin_id, escolha=None):
    """O valor a carimbar num pedido que nasce agora.

    Com o regime desligado o resultado é sempre `faturado`, **inclusive quando
    alguém manda `escolha='adiantamento'`**: a tela não oferece a opção fora do
    regime novo, e um POST forjado não pode ser a porta de entrada de um fluxo
    que o tenant não ligou.

    Com o regime ligado, respeita a escolha de quem emite; escolha ausente ou
    desconhecida cai em `faturado`, que é o caso comum e o menos surpreendente.
    """
    if not fluxo_do_tenant(admin_id):
        return FATURADO
    if escolha in FLUXOS_VALIDOS:
        return escolha
    return FATURADO
