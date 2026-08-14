#!/usr/bin/env python3
"""Liga/desliga o recebimento com atesto por tenant — Fase 4.

Uso:
    python scripts/flag_recebimento_atesto.py <admin_id> --ligar
    python scripts/flag_recebimento_atesto.py <admin_id> --desligar
    python scripts/flag_recebimento_atesto.py <admin_id>          # consulta

Ligar a flag muda comportamento de produção: os pedidos criados A PARTIR DAÍ
nascem com `exige_atesto=True`, e neles o estoque deixa de entrar na emissão —
passa a entrar só quando alguém atesta o recebimento na obra.

Pedido já criado NÃO muda de regime. O regime é carimbado na linha
(`pedido_compra.exige_atesto`), então desligar a flag depois não reescreve o
passado: o que nasceu no regime novo continua exigindo atesto, e o que nasceu
no antigo continua com o estoque que já entrou. É de propósito — ver o spec
2026-08-11-recebimento-atesto-design.md, seção "Regime de virada".
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def recebimento_atesto_ativo(admin_id):
    """True se o tenant tem o recebimento com atesto ligado.

    Falha FECHADA para o comportamento ANTIGO: qualquer erro devolve False.
    Numa flag que muda de onde o estoque recebe entrada, o modo de falha
    seguro é o que já estava rodando ontem.
    """
    if not admin_id:
        return False
    try:
        from models import ConfiguracaoEmpresa
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cfg and cfg.recebimento_atesto_ativo)
    except Exception:
        return False


def definir_flag(admin_id, valor):
    """Grava a flag, criando a ConfiguracaoEmpresa se ela não existir.

    `nome_empresa` é NOT NULL; num tenant que nunca abriu a tela de
    configurações a linha não existe, e é preciso criá-la com um nome
    provisório em vez de estourar. Mesma forma de
    scripts/flag_compras_governanca.definir_flag.
    """
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        usuario = db.session.get(Usuario, admin_id)
        cfg = ConfiguracaoEmpresa(
            admin_id=admin_id,
            nome_empresa=(usuario.nome if usuario else f'Tenant {admin_id}'))
        db.session.add(cfg)
    cfg.recebimento_atesto_ativo = bool(valor)
    db.session.commit()
    return cfg.recebimento_atesto_ativo


def pode_ligar(admin_id):
    """(bool, motivo). O motivo é lido por humano — escreva para humano.

    Guard único: tenant SEM nenhum item de almoxarifado cadastrado. No regime
    novo o estoque só entra pelo atesto, e o atesto só gera movimento para item
    vinculado ao catálogo (`PedidoCompraItem.almoxarifado_item_id`). Ligar num
    tenant sem catálogo é desligar a entrada de estoque sem colocar nada no
    lugar — o pedido passa a exigir um atesto que não movimenta nada.
    """
    try:
        from models import AlmoxarifadoItem
        tem_catalogo = AlmoxarifadoItem.query.filter_by(
            admin_id=admin_id).count() > 0
    except Exception as e:
        return False, f'não foi possível conferir o almoxarifado do tenant: {e}'

    if not tem_catalogo:
        return False, (
            'este tenant não tem nenhum item de almoxarifado cadastrado. No '
            'regime novo o estoque só entra pelo atesto, e o atesto só gera '
            'movimento para item do catálogo — ligar aqui tiraria a entrada '
            'de estoque sem pôr nada no lugar. Cadastre o catálogo antes, ou '
            'use --forcar se as compras deste tenant não controlam estoque.')
    return True, ''


def main():
    parser = argparse.ArgumentParser(
        description='Flag do recebimento com atesto (Fase 4)')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo sem catálogo de almoxarifado')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.ligar:
            ok, motivo = pode_ligar(args.admin_id)
            if not ok and not args.forcar:
                print(f'RECUSADO: {motivo}')
                return 1
            definir_flag(args.admin_id, True)
            print(f'tenant {args.admin_id}: recebimento com atesto LIGADO')
            print('  pedidos NOVOS nascem com exige_atesto=True; os que já '
                  'existem seguem no regime antigo, de propósito.')
        elif args.desligar:
            definir_flag(args.admin_id, False)
            print(f'tenant {args.admin_id}: recebimento com atesto DESLIGADO')
            print('  os pedidos que já nasceram no regime novo CONTINUAM '
                  'exigindo atesto — o regime é carimbado na linha.')
        else:
            estado = ('LIGADO' if recebimento_atesto_ativo(args.admin_id)
                      else 'DESLIGADO')
            print(f'tenant {args.admin_id}: recebimento com atesto {estado}')
        return 0


if __name__ == '__main__':
    sys.exit(main())
