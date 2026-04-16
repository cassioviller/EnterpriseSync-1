"""Task #70 — CLI: `flask init-planejamento-custos --obra=<id>` / `--all`.

Bootstrap que popula `obra_servico_custo` para obras existentes:
  - 1 linha por ItemMedicaoComercial (com FK UNIQUE), caso ainda não exista
  - Complementa com 1 linha por ServicoObraReal sem par

Distribui o realizado proporcionalmente via recalcular_obra.
Idempotente.
"""
import click
from flask.cli import with_appcontext

from app import db
from models import (
    Obra,
    ItemMedicaoComercial,
    ServicoObraReal,
    ObraServicoCusto,
)
from services.resumo_custos_obra import recalcular_obra


def _bootstrap_obra(obra: Obra) -> int:
    criados = 0

    itens = ItemMedicaoComercial.query.filter_by(
        obra_id=obra.id, admin_id=obra.admin_id
    ).all()
    for it in itens:
        ja = ObraServicoCusto.query.filter_by(item_medicao_comercial_id=it.id).first()
        if ja:
            continue
        db.session.add(ObraServicoCusto(
            admin_id=obra.admin_id,
            obra_id=obra.id,
            item_medicao_comercial_id=it.id,
            nome=it.nome,
            valor_orcado=0,
        ))
        criados += 1

    try:
        reais = ServicoObraReal.query.filter_by(obra_id=obra.id).all()
    except Exception:
        reais = []
    for sr in reais:
        ja = ObraServicoCusto.query.filter_by(servico_obra_real_id=sr.id).first()
        if ja:
            continue
        db.session.add(ObraServicoCusto(
            admin_id=obra.admin_id,
            obra_id=obra.id,
            servico_obra_real_id=sr.id,
            nome=getattr(sr, 'nome_servico', None) or f'Serviço #{sr.id}',
            valor_orcado=0,
        ))
        criados += 1

    db.session.commit()
    # Sempre recalcula para que obras já com serviços também obtenham
    # o snapshot de realizado proporcional atualizado.
    recalcular_obra(obra.id, admin_id=obra.admin_id)
    db.session.commit()
    return criados


@click.command('init-planejamento-custos')
@click.option('--obra', 'obra_id', type=int, default=None, help='ID da obra')
@click.option('--all', 'todas', is_flag=True, default=False, help='Processar todas as obras')
@with_appcontext
def init_planejamento_custos(obra_id, todas):
    """Cria ObraServicoCusto para obras existentes (idempotente)."""
    if not obra_id and not todas:
        click.echo('Use --obra=<id> ou --all', err=True)
        return

    if todas:
        obras = Obra.query.all()
    else:
        obra = Obra.query.get(obra_id)
        if not obra:
            click.echo(f'Obra {obra_id} não encontrada', err=True)
            return
        obras = [obra]

    total_criados = 0
    for obra in obras:
        try:
            n = _bootstrap_obra(obra)
            total_criados += n
            click.echo(f'Obra #{obra.id} "{obra.nome}": {n} serviço(s) de custo criado(s)')
        except Exception as e:
            db.session.rollback()
            click.echo(f'Erro na obra #{obra.id}: {e}', err=True)

    click.echo(f'✅ Concluído. Total criados: {total_criados}')
