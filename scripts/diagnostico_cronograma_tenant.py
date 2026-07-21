#!/usr/bin/env python3
"""Diagnóstico: por que o cronograma não aparece para este tenant?

Antes deste script, responder essa pergunta exigia abrir o banco. São pelo
menos cinco portas independentes, e a primeira delas esconde o módulo
INTEIRO:

  1. `Usuario.versao_sistema` do ADMIN do tenant precisa ser 'v2'
     (`utils/tenant.py:63-92`). Sem isso, `_check_v2()`
     (`cronograma_views.py:39-46`) faz flash + redirect para o dashboard em
     TODAS as rotas de cronograma, e o menu "Obras → Cronograma" some
     (`templates/base_completo.html:738-748`). Este é o bloqueio nº 1.
  2. `configuracao_empresa.cronograma_mpp_ativo` precisa ser TRUE para a
     aba de importação .mpp/.xml aparecer (`models.py:3620`,
     `templates/obras/detalhes_obra_profissional.html:2134`). Nasce FALSE.
  3. `configuracao_empresa.escopo_obra_ativo` (Fase 1): com a flag ligada,
     usuário sem linha em `usuario_obra` deixa de enxergar a obra.
  4. `obra.cronograma_revisado_em IS NULL` + proposta de origem: a obra cai
     no gate de revisão inicial (`views/obras.py:2339`).
  5. Catálogo: sem `Servico.template_padrao_id` não existe caminho
     automático proposta→obra (`services/cronograma_proposta.py:227`), e a
     obra nasce sem tarefa nenhuma.

Uso:
    python scripts/diagnostico_cronograma_tenant.py <admin_id>
    python scripts/diagnostico_cronograma_tenant.py <admin_id> --json

Como módulo (testes):
    from scripts.diagnostico_cronograma_tenant import diagnosticar
"""
from __future__ import annotations

import argparse
import json as _json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIMITE_AMOSTRA = 10


def diagnosticar(admin_id: int) -> dict:
    """Estado de todas as portas de cronograma do tenant. Requer app_context.

    Não escreve nada. Devolve dict com os valores brutos + a lista
    `bloqueios`, ordenada da porta mais grave (esconde o módulo inteiro)
    para a menos grave (esconde um recurso).
    """
    from app import db
    from models import (ConfiguracaoEmpresa, Obra, Servico, TarefaCronograma,
                        Usuario)

    admin = db.session.get(Usuario, admin_id)
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()

    versao = getattr(admin, 'versao_sistema', None)
    tipo = getattr(getattr(admin, 'tipo_usuario', None), 'name', None)
    v2_ativo = bool(admin is not None and tipo == 'ADMIN' and versao == 'v2')

    mpp_ativo = bool(config is not None
                     and getattr(config, 'cronograma_mpp_ativo', False))
    # Fase 1: a coluna pode não existir se a migration 216 ainda não rodou.
    escopo_existe = hasattr(ConfiguracaoEmpresa, 'escopo_obra_ativo')
    escopo_ativo = bool(escopo_existe and config is not None
                        and getattr(config, 'escopo_obra_ativo', False))

    obras = Obra.query.filter_by(admin_id=admin_id).all()
    obras_ids = [o.id for o in obras]

    com_tarefa = set()
    if obras_ids:
        com_tarefa = {
            row[0] for row in db.session.query(TarefaCronograma.obra_id)
            .filter(TarefaCronograma.obra_id.in_(obras_ids),
                    TarefaCronograma.admin_id == admin_id,
                    TarefaCronograma.is_cliente.is_(False),
                    TarefaCronograma.ativa.is_(True))
            .distinct().all()
        }

    sem_tarefa = [o for o in obras if o.id not in com_tarefa]
    presas_no_gate = [
        o for o in obras
        if getattr(o, 'cronograma_revisado_em', None) is None
        and getattr(o, 'proposta_origem_id', None)
    ]

    servicos = Servico.query.filter_by(admin_id=admin_id).all()
    servicos_com_template = [s for s in servicos if s.template_padrao_id]

    bloqueios = []
    if admin is None:
        bloqueios.append({
            'codigo': 'admin_inexistente',
            'gravidade': 'total',
            'mensagem': f'admin_id={admin_id} não existe na tabela usuario.',
            'como_resolver': 'Confira o id. `SELECT id, email, tipo_usuario, '
                             'versao_sistema FROM usuario WHERE tipo_usuario '
                             "IN ('ADMIN','SUPER_ADMIN');`",
        })
    else:
        if tipo != 'ADMIN':
            bloqueios.append({
                'codigo': 'nao_e_admin_de_tenant',
                'gravidade': 'total',
                'mensagem': f'usuario {admin_id} é {tipo}, não ADMIN. '
                            'is_v2_active() devolve False para SUPER_ADMIN '
                            '(utils/tenant.py:78-79).',
                'como_resolver': 'Rode o diagnóstico com o id do ADMIN do '
                                 'tenant, não com o do SUPER_ADMIN.',
            })
        if not v2_ativo:
            bloqueios.append({
                'codigo': 'versao_sistema_nao_v2',
                'gravidade': 'total',
                'mensagem': f'versao_sistema={versao!r}. Com isso _check_v2() '
                            '(cronograma_views.py:39) redireciona TODAS as '
                            'rotas de cronograma para o dashboard e o menu '
                            'some de base_completo.html:738.',
                'como_resolver': "UPDATE usuario SET versao_sistema='v2' "
                                 f'WHERE id={admin_id};',
            })

        if config is None:
            bloqueios.append({
                'codigo': 'sem_configuracao_empresa',
                'gravidade': 'parcial',
                'mensagem': 'não existe linha em configuracao_empresa para '
                            'este tenant — todas as flags por tenant leem '
                            'como desligadas.',
                'como_resolver': 'python scripts/flag_cronograma_mpp.py '
                                 f'{admin_id} --ligar  (cria a linha)',
            })
        if not mpp_ativo:
            bloqueios.append({
                'codigo': 'cronograma_mpp_desligado',
                'gravidade': 'parcial',
                'mensagem': 'cronograma_mpp_ativo=FALSE — a aba de importação '
                            '.mpp/.xml não aparece na obra '
                            '(detalhes_obra_profissional.html:2134).',
                'como_resolver': 'python scripts/flag_cronograma_mpp.py '
                                 f'{admin_id} --ligar',
            })
        if escopo_ativo:
            bloqueios.append({
                'codigo': 'escopo_obra_ativo',
                'gravidade': 'parcial',
                'mensagem': 'escopo_obra_ativo=TRUE — quem não é ADMIN só '
                            'enxerga obra com linha ativa em usuario_obra.',
                'como_resolver': 'python scripts/flag_escopo_obra.py '
                                 f'{admin_id} --desligar  (ou crie os '
                                 'vínculos em usuario_obra)',
            })
        if presas_no_gate:
            bloqueios.append({
                'codigo': 'obras_no_gate_de_revisao',
                'gravidade': 'parcial',
                'mensagem': f'{len(presas_no_gate)} obra(s) com '
                            'cronograma_revisado_em NULL e proposta de origem '
                            '— o detalhe pode redirecionar para a tela de '
                            'revisão inicial (views/obras.py:2339).',
                'como_resolver': 'Abra a obra e confirme a revisão, ou '
                                 'materialize as tarefas manualmente.',
            })
        if servicos and not servicos_com_template:
            bloqueios.append({
                'codigo': 'nenhum_servico_com_template',
                'gravidade': 'informativo',
                'mensagem': f'{len(servicos)} serviço(s) cadastrado(s), '
                            'nenhum com template_padrao_id — o caminho '
                            'automático proposta→obra não gera tarefa '
                            '(services/cronograma_proposta.py:227). Criação '
                            'MANUAL de tarefa continua funcionando.',
                'como_resolver': 'Defina Servico.template_padrao_id, ou crie '
                                 'as tarefas manualmente no Gantt.',
            })

    ordem = {'total': 0, 'parcial': 1, 'informativo': 2}
    bloqueios.sort(key=lambda b: ordem.get(b['gravidade'], 9))

    return {
        'admin_id': admin_id,
        'admin_existe': admin is not None,
        'email': getattr(admin, 'email', None),
        'tipo_usuario': tipo,
        'versao_sistema': versao,
        'v2_ativo': v2_ativo,
        'tem_configuracao_empresa': config is not None,
        'cronograma_mpp_ativo': mpp_ativo,
        'escopo_obra_coluna_existe': escopo_existe,
        'escopo_obra_ativo': escopo_ativo,
        'obras_total': len(obras),
        'obras_com_tarefa': len(com_tarefa),
        'obras_sem_tarefa': len(sem_tarefa),
        'obras_no_gate_de_revisao': len(presas_no_gate),
        'servicos_total': len(servicos),
        'servicos_com_template': len(servicos_com_template),
        'amostra_obras_sem_tarefa': [
            {'id': o.id, 'nome': o.nome} for o in sem_tarefa[:LIMITE_AMOSTRA]
        ],
        'amostra_obras_no_gate': [
            {'id': o.id, 'nome': o.nome} for o in presas_no_gate[:LIMITE_AMOSTRA]
        ],
        'bloqueios': bloqueios,
    }


def _imprimir(rel: dict) -> None:
    print('=' * 72)
    print(f'DIAGNÓSTICO DE CRONOGRAMA — admin_id={rel["admin_id"]}')
    print('=' * 72)
    if not rel['admin_existe']:
        print('  admin NÃO existe.')
    else:
        print(f'  e-mail ...................: {rel["email"]}')
        print(f'  tipo_usuario .............: {rel["tipo_usuario"]}')
        print(f'  versao_sistema ...........: {rel["versao_sistema"]}')
        print(f'  V2 ativo (módulo visível) : {rel["v2_ativo"]}')
        print(f'  configuracao_empresa .....: '
              f'{"existe" if rel["tem_configuracao_empresa"] else "AUSENTE"}')
        print(f'  cronograma_mpp_ativo .....: {rel["cronograma_mpp_ativo"]}')
        print(f'  escopo_obra_ativo ........: {rel["escopo_obra_ativo"]}'
              f'{"" if rel["escopo_obra_coluna_existe"] else "  (coluna ainda não existe)"}')
        print('  ' + '-' * 68)
        print(f'  obras ....................: {rel["obras_total"]}')
        print(f'    com tarefa .............: {rel["obras_com_tarefa"]}')
        print(f'    SEM tarefa .............: {rel["obras_sem_tarefa"]}')
        print(f'    no gate de revisão .....: {rel["obras_no_gate_de_revisao"]}')
        print(f'  serviços .................: {rel["servicos_total"]}')
        print(f'    com template padrão ....: {rel["servicos_com_template"]}')

    print()
    if not rel['bloqueios']:
        print('NENHUM BLOQUEIO. O cronograma deve estar visível e utilizável.')
        return

    print(f'BLOQUEIOS ({len(rel["bloqueios"])}), do mais grave para o menos:')
    for i, b in enumerate(rel['bloqueios'], 1):
        print(f'\n  {i}. [{b["gravidade"].upper()}] {b["codigo"]}')
        print(f'     {b["mensagem"]}')
        print(f'     → {b["como_resolver"]}')

    if rel['amostra_obras_sem_tarefa']:
        print('\n  Obras sem nenhuma tarefa (amostra):')
        for o in rel['amostra_obras_sem_tarefa']:
            print(f'     id={o["id"]}  {o["nome"]}')
    if rel['amostra_obras_no_gate']:
        print('\n  Obras presas no gate de revisão (amostra):')
        for o in rel['amostra_obras_no_gate']:
            print(f'     id={o["id"]}  {o["nome"]}')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('admin_id', type=int)
    parser.add_argument('--json', action='store_true',
                        help='imprime o relatório cru em JSON')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        rel = diagnosticar(args.admin_id)

    if args.json:
        print(_json.dumps(rel, indent=2, ensure_ascii=False))
    else:
        _imprimir(rel)

    return 0 if rel['admin_existe'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
