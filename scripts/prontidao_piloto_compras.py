#!/usr/bin/env python3
"""Este tenant está pronto para ligar o ciclo de compras? — 2026-08-19

Uso:
    python scripts/prontidao_piloto_compras.py <ADMIN_ID>
    python scripts/prontidao_piloto_compras.py <ADMIN_ID> --json

Exit 0 = pronto. Exit 1 = falta coisa, e cada falta vem com o remédio.
Não altera NADA.

POR QUE ESTE SCRIPT EXISTE. Os runbooks das Fases 1, 2 e 3 têm passo 0, e os três
perguntam a mesma coisa: em que estado estão as flags. Nenhum pergunta se existe
GENTE para exercer o ciclo — e foi exatamente aí que o ensaio de rollout de 19/08
parou.

🔬 O tenant de demonstração (admin_id=1) tem 1260 obras, 5 itens de almoxarifado,
faixas de alçada semeadas... e **um único usuário de login**, com **zero vínculos
usuario_obra**. Ligar a cadeia ali produziria um ciclo em que uma pessoa faz tudo,
e a alçada travaria na segunda aprovação por não existir segunda pessoa. As flags
teriam ligado. O ciclo não funcionaria.

O QUE ELE CONFERE, e por que cada um derruba o piloto:

  1. PESSOAS  — o ciclo tem quatro papéis (requisita, aprova, compra, paga) e as
     regras de segregação são a razão de as fases existirem: solicitante ≠
     aprovador (Fase 3), aprovador ≠ emissor quando a faixa pede mais de uma
     assinatura, e quem monta o lote ≠ quem o fecha (Fase 2). Com um login só,
     nenhuma delas é exercível.
  2. VÍNCULOS — 📖 `papel_de_usuario_na_obra:144` devolve GESTOR ao ADMIN em
     qualquer obra do tenant, então o admin nunca se tranca. Todo NÃO-admin sem
     linha em `usuario_obra` fica sem papel, e 📖 `pode_comprar_na_obra` devolve
     False: o bloco de emitir pedido simplesmente NÃO É RENDERIZADO. Quem não está
     vinculado não vê o botão e conclui que o sistema quebrou.
  3. ALMOXARIFADO — o `--ligar` do recebimento já recusa tenant sem item, mas aqui
     a pergunta aparece ANTES, junto das outras.
  4. FORNECEDOR — sem ele não se emite pedido, e a recusa só aparece no formulário.
  5. FAIXAS DE ALÇADA — tenant sem faixa cai na `_FaixaSeguranca` (2 aprovações +
     ADMIN), que é falha fechada e não aparece em tela nenhuma.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def prontidao(admin_id):
    """Lista de dicts: cada um é um requisito, com `ok` e o remédio."""
    from models import (AlmoxarifadoItem, FaixaAlcada, Fornecedor, Obra,
                        TipoUsuario, Usuario, UsuarioObra)

    itens = []

    logins = Usuario.query.filter(
        (Usuario.admin_id == admin_id) | (Usuario.id == admin_id)).filter_by(
            ativo=True).all()
    nao_admin = [u for u in logins
                 if u.tipo_usuario not in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN)]
    itens.append({
        'requisito': 'pessoas com login',
        'ok': len(logins) >= 3,
        'medido': f'{len(logins)} login(s), {len(nao_admin)} não-admin',
        'remedio': 'o ciclo tem quatro papéis e três regras de segregação. Com '
                   'menos de três logins, solicitante ≠ aprovador e aprovador ≠ '
                   'emissor não são exercíveis — as fases ficam ligadas e inertes',
    })

    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).count()
    vinculos = UsuarioObra.query.filter_by(admin_id=admin_id, ativo=True).count()
    itens.append({
        'requisito': 'vínculos usuario_obra',
        'ok': vinculos > 0,
        'medido': f'{vinculos} vínculo(s) para {obras} obra(s) ativa(s)',
        'remedio': 'sem vínculo, todo NÃO-admin fica sem papel na obra e o bloco '
                   'de emitir pedido não é renderizado (pode_comprar_na_obra). O '
                   'ADMIN não se tranca — papel_de_usuario_na_obra devolve GESTOR '
                   'a ele —, o que faz o problema parecer inexistente em teste '
                   'feito com a conta de admin',
    })

    n_itens = AlmoxarifadoItem.query.filter_by(admin_id=admin_id).count()
    itens.append({
        'requisito': 'itens de almoxarifado',
        'ok': n_itens > 0,
        'medido': f'{n_itens} item(ns)',
        'remedio': 'sem catálogo o atesto não gera movimento de estoque — 📖 '
                   '"item de texto livre não chega aqui". A perna de estoque da '
                   'Fase 1 fica inerte, e o `--ligar` do recebimento recusa',
    })

    n_forn = Fornecedor.query.filter_by(admin_id=admin_id, ativo=True).count()
    itens.append({
        'requisito': 'fornecedores ativos',
        'ok': n_forn > 0,
        'medido': f'{n_forn} fornecedor(es)',
        'remedio': 'a emissão do pedido exige fornecedor, e a recusa só aparece '
                   'no formulário, depois de a requisição já estar aprovada',
    })

    n_faixas = FaixaAlcada.query.filter_by(admin_id=admin_id).count()
    itens.append({
        'requisito': 'faixas de alçada',
        'ok': n_faixas > 0,
        'medido': f'{n_faixas} faixa(s)',
        'remedio': 'tenant sem faixa cai na _FaixaSeguranca (2 aprovações + '
                   'ADMIN), que é falha fechada e não aparece em tela nenhuma. '
                   'Semeie em Configurações › Alçadas de Compra',
    })

    return itens


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('admin_id', type=int)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    from app import app
    with app.app_context():
        itens = prontidao(args.admin_id)

    faltam = [i for i in itens if not i['ok']]
    if args.json:
        print(json.dumps(itens, ensure_ascii=False, indent=2))
        return 1 if faltam else 0

    print(f'\ntenant {args.admin_id} — prontidão para o ciclo de compras\n')
    for i in itens:
        print(f"  [{'ok  ' if i['ok'] else 'FALTA'}] {i['requisito']:24s} {i['medido']}")
    if faltam:
        print(f'\n{len(faltam)} requisito(s) faltando — o remédio de cada um:\n')
        for i in faltam:
            print(f"  {i['requisito']}")
            print(f"    {i['remedio']}\n")
        print('Ligar as flags com isto faltando produz um ciclo que "funciona" e '
              'não roda: as telas abrem, e ninguém consegue percorrer o fluxo.')
    else:
        print('\nPronto para o rollout. Siga a ordem da cadeia: escopo_obra → '
              'compras_governanca → recebimento_atesto → financeiro_dois_fluxos, '
              'e alcadas_avancadas depois da governança.')
    return 1 if faltam else 0


if __name__ == '__main__':
    sys.exit(main())
