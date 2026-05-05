"""
cobertura_ociosa_cli.py

Flask CLI command para o job de cobertura ociosa de mensalistas.
Registrado em app.py como 'cobertura-ociosa'.

Uso (via flask CLI):
    flask cobertura-ociosa              # processa mês anterior, todos os tenants
    flask cobertura-ociosa --ano 2026 --mes 2
    flask cobertura-ociosa --ano 2026 --mes 2 --admin-id 1
"""

import click
from flask.cli import with_appcontext


@click.command('cobertura-ociosa')
@click.option('--ano',      default=None, type=int,
              help='Ano de referência (default: mês anterior)')
@click.option('--mes',      default=None, type=int,
              help='Mês de referência (default: mês anterior)')
@click.option('--admin-id', default=None, type=int,
              help='ID do admin/tenant (default: todos os ativos)')
@with_appcontext
def cobertura_ociosa_cmd(ano, mes, admin_id):
    """Cria registros ocioso_mensal para mensalistas sem RDO no mês."""
    from datetime import date

    if ano is None or mes is None:
        hoje = date.today()
        if hoje.month == 1:
            ano, mes = hoje.year - 1, 12
        else:
            ano, mes = hoje.year, hoje.month - 1

    click.echo(f'[cobertura-ociosa] período={ano}/{mes:02d} admin={admin_id or "todos"}')

    from jobs.cobertura_ociosa_mensalistas import executar
    resultado = executar(ano, mes, admin_id)

    total_dias = sum(resultado.values())
    click.echo(
        f'[cobertura-ociosa] Concluído: '
        f'{len(resultado)} funcionário(s), {total_dias} dia(s) criado(s).'
    )
