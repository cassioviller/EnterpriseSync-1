#!/usr/bin/env python3
"""Liga/desliga o financeiro em dois fluxos por tenant — Fase 2 do ciclo de compras.

Uso:
    python scripts/flag_financeiro_dois_fluxos.py <admin_id> --ligar
    python scripts/flag_financeiro_dois_fluxos.py <admin_id> --desligar
    python scripts/flag_financeiro_dois_fluxos.py <admin_id>          # consulta

Ligar a flag muda comportamento de produção: os pedidos criados A PARTIR DAÍ
carregam o fluxo escolhido na emissão, e no Fluxo A a `ContaPagar` nasce
BLOQUEADA — só é pagável com a tríade completa (pedido + nota + atesto).

Pedido já criado NÃO muda de fluxo. O regime é carimbado na linha
(`pedido_compra.fluxo_pagamento`), então desligar a flag depois não reescreve o
passado: adiantamento já pago continua sendo adiantamento, e não vira compra
faturada por causa de um toggle. Mesmo contrato de `exige_atesto` da Fase 1 —
ver o spec 2026-08-14-financeiro-dois-fluxos-design.md, seção "Regime de virada".
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def financeiro_dois_fluxos_ativo(admin_id):
    """True se o tenant tem o financeiro em dois fluxos ligado.

    Falha FECHADA para o comportamento ANTIGO: qualquer erro devolve False.
    Numa flag que muda o momento em que a obrigação financeira nasce, o modo de
    falha seguro é o que já estava rodando ontem.
    """
    if not admin_id:
        return False
    try:
        from models import ConfiguracaoEmpresa
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cfg and cfg.financeiro_dois_fluxos_ativo)
    except Exception:
        return False


def definir_flag(admin_id, valor):
    """Grava a flag, criando a ConfiguracaoEmpresa se ela não existir.

    `nome_empresa` é NOT NULL; num tenant que nunca abriu a tela de
    configurações a linha não existe, e é preciso criá-la com um nome
    provisório em vez de estourar. Mesma forma de
    scripts/flag_recebimento_atesto.definir_flag.
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
    cfg.financeiro_dois_fluxos_ativo = bool(valor)
    db.session.commit()
    return cfg.financeiro_dois_fluxos_ativo


def pode_ligar(admin_id):
    """(bool, motivo). O motivo é lido por humano — escreva para humano.

    Guard único e DURO: tenant sem `recebimento_atesto_ativo`. A tríade tem três
    pernas, e uma delas é o atesto; sem o regime de recebimento ligado, a conta
    do Fluxo A nasceria BLOQUEADA sem caminho nenhum para liberar — o usuário
    veria uma conta que não paga e nenhuma tela que destrave.

    É a mesma classe de dependência que a governança de compras tem do escopo
    de obra (Fase 3), e a lição de lá é exatamente esta: a guarda precisa morar
    aqui, porque quem liga a flag por SQL direto não tem guarda nenhuma.
    """
    try:
        from scripts.flag_recebimento_atesto import recebimento_atesto_ativo
        tem_atesto = recebimento_atesto_ativo(admin_id)
    except Exception as e:
        return False, f'não foi possível conferir o regime de recebimento: {e}'

    if not tem_atesto:
        return False, (
            'este tenant está com o recebimento com atesto DESLIGADO. A tríade '
            'que libera o pagamento tem três pernas — pedido, nota e atesto — e '
            'sem a terceira toda conta do Fluxo A nasceria bloqueada sem '
            'caminho para liberar. Ligue primeiro: '
            'python scripts/flag_recebimento_atesto.py '
            f'{admin_id} --ligar')
    return True, ''


def main():
    parser = argparse.ArgumentParser(
        description='Flag do financeiro em dois fluxos (Fase 2 do ciclo de compras)')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo sem o recebimento com atesto (leia o '
                             'motivo antes: a conta nasce sem caminho para '
                             'liberar)')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.ligar:
            ok, motivo = pode_ligar(args.admin_id)
            if not ok and not args.forcar:
                print(f'RECUSADO: {motivo}')
                return 1
            definir_flag(args.admin_id, True)
            print(f'tenant {args.admin_id}: financeiro em dois fluxos LIGADO')
            print('  pedidos NOVOS carregam o fluxo escolhido na emissão; no '
                  'Fluxo A a ContaPagar nasce BLOQUEADA até a tríade fechar.')
            print('  os pedidos que já existem seguem no regime antigo, de '
                  'propósito.')
        elif args.desligar:
            definir_flag(args.admin_id, False)
            print(f'tenant {args.admin_id}: financeiro em dois fluxos DESLIGADO')
            print('  as contas que já nasceram bloqueadas CONTINUAM bloqueadas '
                  '— o regime é carimbado na linha. Libere-as pela tela antes '
                  'de considerar o rollback completo.')
        else:
            estado = ('LIGADO' if financeiro_dois_fluxos_ativo(args.admin_id)
                      else 'DESLIGADO')
            print(f'tenant {args.admin_id}: financeiro em dois fluxos {estado}')
        return 0


if __name__ == '__main__':
    sys.exit(main())
