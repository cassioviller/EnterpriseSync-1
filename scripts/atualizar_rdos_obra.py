"""
Atualiza os RDOs de uma obra a partir de um payload JSON — SEM apagar nada.

É o par de `scripts/whatsapp_para_rdos.py`: aquele converte o export do
WhatsApp em payload, este grava no banco. Nenhum dos dois toca em cronograma,
proposta, orçamento ou medição — ao contrário do reimport físico-financeiro,
que é destrutivo e é recusado em obra já versionada por .mpp.

Uso:
    # 1) revisão: mostra o que faria, resolve as tarefas, não grava
    SIGE_ENABLE_DEMO_SEED=false python scripts/atualizar_rdos_obra.py \\
        <admin_id|username> <codigo_obra> payload_rdos.json --dry-run

    # 2) aplica
    SIGE_ENABLE_DEMO_SEED=false python scripts/atualizar_rdos_obra.py \\
        <admin_id|username> <codigo_obra> payload_rdos.json

Opções:
    --dry-run       roda tudo e dá rollback (nada é gravado)
    --sem-fotos     ignora a seção `fotos` dos itens
    --fotos-base P  raiz das pastas de foto (default: fotos_rdos/)
    --mapa P.json   JSON canônico da obra, para o fallback de resolução de
                    tarefa por NOME quando as tarefas não têm `mpp_uid`
                    (default: cronograma_fisico_financeiro_baias.json, se
                    existir na raiz)

Saída com **PENDÊNCIAS** significa apontamento que NÃO entrou: id de tarefa
que não resolve, `pct` que viola retrocesso/marco, item sem valor. Resolva o
payload e rode de novo — o script é idempotente por data.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app                                            # noqa: E402
from models import Obra, Usuario                                # noqa: E402
from services.atualizacao_rdos import (                         # noqa: E402
    atualizar_rdos, formatar_relatorio, mapa_nomes_do_json)

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAPA_PADRAO = os.path.join(_RAIZ, 'cronograma_fisico_financeiro_baias.json')


def _resolver_admin(arg):
    if str(arg).isdigit():
        return int(arg)
    u = Usuario.query.filter_by(username=arg).first()
    return u.id if u else None


def _carregar_mapa(caminho):
    if not caminho or not os.path.exists(caminho):
        return None
    with open(caminho, encoding='utf-8') as fh:
        return mapa_nomes_do_json(json.load(fh))


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Atualiza os RDOs de uma obra sem apagar nada.')
    p.add_argument('admin', help='admin_id ou username')
    p.add_argument('codigo_obra',
                   help='código da obra (Obra.codigo); obra sem código '
                        'aceita o id numérico como fallback')
    p.add_argument('payload', help='JSON com a seção "rdos"')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--sem-fotos', action='store_true')
    p.add_argument('--fotos-base')
    p.add_argument('--mapa', default=_MAPA_PADRAO)
    args = p.parse_args(argv)

    with open(args.payload, encoding='utf-8') as fh:
        payload = json.load(fh)
    rdos = payload.get('rdos') if isinstance(payload, dict) else payload
    if not rdos:
        print('payload sem seção "rdos" — nada a fazer')
        return 1

    with app.app_context():
        admin_id = _resolver_admin(args.admin)
        if not admin_id:
            print('admin não encontrado:', args.admin)
            return 1
        obra = Obra.query.filter_by(codigo=args.codigo_obra,
                                    admin_id=admin_id).first()
        if obra is None and str(args.codigo_obra).isdigit():
            # Obra sem `codigo` (ex.: Angela, id 43) não tem como ser
            # endereçada senão pelo id. Código vence; id é o fallback.
            obra = Obra.query.filter_by(id=int(args.codigo_obra),
                                        admin_id=admin_id).first()
        if obra is None:
            print(f'obra código/id={args.codigo_obra} não encontrada para '
                  f'admin_id={admin_id}')
            return 1

        rel = atualizar_rdos(
            obra, admin_id, rdos,
            dry_run=args.dry_run,
            com_fotos=not args.sem_fotos,
            base_fotos=args.fotos_base,
            mapa_mpp_nome=_carregar_mapa(args.mapa),
        )
        print(formatar_relatorio(rel, obra))
        if not args.dry_run:
            print(f'  Cronograma: /cronograma/obra/{obra.id}/fisico-financeiro')
        return 2 if rel['pendencias'] else 0


if __name__ == '__main__':
    sys.exit(main())
