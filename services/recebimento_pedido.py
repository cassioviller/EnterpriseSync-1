"""Recebimento e atesto de pedido de compra — Fase 4.

O caminho ÚNICO de escrita do recebimento, no molde do chokepoint que a Fase 3
usa em services/requisicao_compra.py. Quem grava recebimento passa por aqui;
quem quiser gravar por fora vai divergir do `situacao_recebimento` persistido, e
o scripts/verificar_consistencia_recebimento.py denuncia.

Spec: docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md
"""
import logging

logger = logging.getLogger('recebimento_pedido')


def regime_do_tenant(admin_id):
    """O pedido que nascer AGORA neste tenant exige atesto?

    Uma função só, chamada pelos dois pontos que criam `PedidoCompra` em
    compras_views.py — o POST avulso e a emissão a partir de requisição. Ter
    dois lugares lendo a flag por conta própria é como dois lugares divergirem
    na regra; ter um só é como isso não acontecer.

    O valor devolvido é CARIMBADO em `pedido_compra.exige_atesto` e nunca mais
    reconsultado para aquele pedido: desligar a flag depois não muda o regime
    do que já nasceu. Ver o spec, seção "Regime de virada".
    """
    from scripts.flag_recebimento_atesto import recebimento_atesto_ativo
    return bool(recebimento_atesto_ativo(admin_id))
