#!/usr/bin/env python3
"""Liga/desliga as alçadas avançadas por tenant — Fase 3 do ciclo de compras.

Uso:
    python scripts/flag_alcadas_avancadas.py <admin_id> --ligar
    python scripts/flag_alcadas_avancadas.py <admin_id> --desligar
    python scripts/flag_alcadas_avancadas.py <admin_id>          # consulta

Ligar a flag muda comportamento de produção: as requisições criadas A PARTIR
DAÍ passam a valer no regime avançado — as quatro condições sobem um degrau na
faixa, o acumulado da janela conta contra o fracionamento e o rito de
emergência 48h existe.

Requisição já criada NÃO muda de regime. Ele é carimbado na linha
(`requisicao_compra.regime_alcada`), então desligar a flag depois não reescreve
o passado: quem já foi avisado de que precisa de duas aprovações continua
precisando de duas. Rebaixar a alçada de uma requisição em curso é o contrário
do que a fase faz. Mesmo contrato de `exige_atesto` (Fase 1) e de
`fluxo_pagamento` (Fase 2) — ver o spec 2026-08-15-alcadas-design.md, seção
"Regime de virada".
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def alcadas_avancadas_ativa(admin_id):
    """True se o tenant tem as alçadas avançadas ligadas.

    Falha FECHADA para o comportamento ANTIGO: qualquer erro devolve False.
    Numa flag que muda quantas aprovações uma compra exige, o modo de falha
    seguro é o que já estava rodando ontem — travar o canteiro por causa de uma
    coluna ilegível seria pior do que aprovar como se aprovava.
    """
    if not admin_id:
        return False
    try:
        from models import ConfiguracaoEmpresa
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cfg and cfg.alcadas_avancadas_ativa)
    except Exception:
        return False


def definir_flag(admin_id, valor):
    """Grava a flag, criando a ConfiguracaoEmpresa se ela não existir.

    `nome_empresa` é NOT NULL; num tenant que nunca abriu a tela de
    configurações a linha não existe, e é preciso criá-la com um nome
    provisório em vez de estourar. Mesma forma de
    scripts/flag_financeiro_dois_fluxos.definir_flag.
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
    cfg.alcadas_avancadas_ativa = bool(valor)
    db.session.commit()
    return cfg.alcadas_avancadas_ativa


def pode_ligar(admin_id):
    """(bool, motivo). O motivo é lido por humano — escreva para humano.

    São DUAS dependências, e elas não são da mesma natureza. A diferença entre
    recusar e avisar está aqui, e é deliberada:

    1. `compras_governanca_ativa` — dependência DURA, e por isso RECUSA.
       O que esta fase faz é subir uma requisição de faixa: mais aprovações,
       aprovação de admin, mapa de concorrência. Sem a governança ligada a
       requisição não passa pelo caminho de aprovação nenhum — o degrau não
       tem sobre o que agir. Pior: a governança, por sua vez, recusa tenant
       sem `escopo_obra_ativo`, e sem o escopo `papel_na_obra` devolve GESTOR
       a TODO autenticado do tenant (📖 utils/autorizacao.py, achado 🔴 nº 1
       da revisão de 23/07). Alçada avançada sobre esse chão não endurece
       nada: só multiplica pendências que a mesma pessoa resolve sozinha.
       A cadeia tem cinco elos e este é o elo imediatamente abaixo.

    2. `financeiro_dois_fluxos_ativo` — dependência PARCIAL, e por isso só
       AVISA. Dela depende UMA das quatro regras: a sanção da emergência não
       ratificada em 48h, que é a `ContaPagar` derivada não liberar. Com os
       dois fluxos desligados a conta nasce `liberada` e a não-ratificação
       não morde — o rito continua existindo e sendo registrado, só perde o
       dente. As outras três (as condições, o acumulado e o corte de
       cotações) funcionam sem ela. Recusar seria negar três quartos da fase
       por causa de um quarto.

    A guarda mora AQUI, e não só na tela, porque quem liga a flag por SQL
    direto não tem tela nenhuma.
    """
    try:
        from scripts.flag_compras_governanca import governanca_ativa
        tem_governanca = governanca_ativa(admin_id)
    except Exception as e:
        return False, f'não foi possível conferir a governança de compras: {e}'

    if not tem_governanca:
        return False, (
            'este tenant está com a governança de compras DESLIGADA. A alçada '
            'avançada só sabe subir uma requisição de faixa — sem a '
            'governança não existe caminho de aprovação nenhum sobre o qual o '
            'degrau possa agir, e a flag ligada não mudaria coisa alguma. '
            'Ligue primeiro (ela mesma vai exigir o escopo de obra): '
            'python scripts/flag_compras_governanca.py '
            f'{admin_id} --ligar')

    try:
        from scripts.flag_financeiro_dois_fluxos import \
            financeiro_dois_fluxos_ativo
        tem_dois_fluxos = financeiro_dois_fluxos_ativo(admin_id)
    except Exception:
        # Falha ao conferir a dependência PARCIAL não pode virar recusa: ela
        # não recusaria nem se a resposta fosse "desligado".
        tem_dois_fluxos = False

    if not tem_dois_fluxos:
        return True, (
            'AVISO (não impede ligar): este tenant está com o financeiro em '
            'dois fluxos DESLIGADO. O rito de emergência 48h continua '
            'valendo e continua sendo registrado, mas a sanção da '
            'não-ratificação não morde: a sanção é a ContaPagar derivada não '
            'liberar, e sem os dois fluxos toda conta nasce liberada. As '
            'outras três regras da fase não dependem disso. Para dar o dente '
            'de volta: python scripts/flag_financeiro_dois_fluxos.py '
            f'{admin_id} --ligar')

    return True, ''


def main():
    parser = argparse.ArgumentParser(
        description='Flag das alçadas avançadas (Fase 3 do ciclo de compras)')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo sem a governança de compras (leia o '
                             'motivo antes: o degrau não teria sobre o que '
                             'agir)')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.ligar:
            ok, motivo = pode_ligar(args.admin_id)
            if not ok and not args.forcar:
                print(f'RECUSADO: {motivo}')
                return 1
            if motivo:
                print(motivo)
            definir_flag(args.admin_id, True)
            print(f'tenant {args.admin_id}: alçadas avançadas LIGADAS')
            print('  requisições NOVAS nascem em regime avancado: as condições '
                  'ativas da faixa sobem degrau, o acumulado da janela conta e '
                  'a emergência 48h existe.')
            print('  as requisições que já existem seguem em regime simples, '
                  'de propósito.')
        elif args.desligar:
            definir_flag(args.admin_id, False)
            print(f'tenant {args.admin_id}: alçadas avançadas DESLIGADAS')
            print('  as requisições que já nasceram em regime avancado '
                  'CONTINUAM avançadas — o regime é carimbado na linha. '
                  'Emergência pendente continua contando as 48h.')
            print('  o que volta ao normal é a requisição NOVA.')
        else:
            estado = ('LIGADAS' if alcadas_avancadas_ativa(args.admin_id)
                      else 'DESLIGADAS')
            print(f'tenant {args.admin_id}: alçadas avançadas {estado}')
        return 0


if __name__ == '__main__':
    sys.exit(main())
