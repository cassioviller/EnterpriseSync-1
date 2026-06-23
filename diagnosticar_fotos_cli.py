#!/usr/bin/env python3
"""
Comando Flask CLI para diagnosticar fotos faciais cadastradas.
Mostra estatísticas detalhadas por funcionário.
"""

import click
from flask.cli import with_appcontext
from models import Funcionario, FotoFacialFuncionario


@click.command('diagnosticar-fotos-faciais')
@click.option('--admin-id', default=None, type=int, help='ID do tenant (opcional)')
@with_appcontext
def diagnosticar_fotos_faciais(admin_id):
    """
    Diagnóstico completo de fotos faciais cadastradas.
    Mostra quantas fotos cada funcionário tem e se estão ativas.
    """
    click.echo("🔍 DIAGNÓSTICO DE FOTOS FACIAIS")
    click.echo("=" * 80)
    
    # Filtrar por tenant se fornecido
    query = Funcionario.query.filter(Funcionario.ativo == True)
    if admin_id:
        query = query.filter(Funcionario.admin_id == admin_id)
        click.echo(f"📊 Tenant: admin_id={admin_id}")
    else:
        click.echo(f"📊 Todos os tenants")
    
    funcionarios = query.all()
    click.echo(f"👥 Total de funcionários ativos: {len(funcionarios)}")
    click.echo()
    
    # Estatísticas globais
    total_fotos_multiplas = 0
    total_fotos_ativas = 0
    total_fotos_inativas = 0
    total_com_foto_principal = 0
    total_sem_fotos = 0
    
    # Detalhes por funcionário
    click.echo("📋 DETALHES POR FUNCIONÁRIO:")
    click.echo("-" * 80)
    
    for func in funcionarios:
        # Contar fotos múltiplas
        fotos_multiplas = FotoFacialFuncionario.query.filter_by(
            funcionario_id=func.id,
            admin_id=func.admin_id
        ).all()
        
        fotos_ativas = sum(1 for f in fotos_multiplas if f.ativa)
        fotos_inativas = len(fotos_multiplas) - fotos_ativas
        
        # Verificar foto principal
        tem_foto_principal = func.foto_base64 is not None
        
        # Atualizar estatísticas
        total_fotos_multiplas += len(fotos_multiplas)
        total_fotos_ativas += fotos_ativas
        total_fotos_inativas += fotos_inativas
        if tem_foto_principal:
            total_com_foto_principal += 1
        
        # Status
        if fotos_ativas == 0 and not tem_foto_principal:
            status = "❌ SEM FOTOS"
            total_sem_fotos += 1
        elif fotos_ativas == 0:
            status = "⚠️ SÓ FOTO PRINCIPAL"
        elif fotos_ativas < 3:
            status = "⚠️ POUCAS FOTOS"
        else:
            status = "✅ OK"
        
        # Exibir
        nome_truncado = func.nome[:40] if func.nome else 'N/A'
        click.echo(f"{status} | {nome_truncado:40} | "
                   f"Múltiplas: {fotos_ativas:2} ativas, {fotos_inativas:2} inativas | "
                   f"Principal: {'✓' if tem_foto_principal else '✗'}")
    
    # Resumo
    click.echo()
    click.echo("=" * 80)
    click.echo("📊 RESUMO:")
    click.echo(f"  👥 Total de funcionários: {len(funcionarios)}")
    click.echo(f"  📸 Total de fotos múltiplas: {total_fotos_multiplas}")
    click.echo(f"    ✅ Ativas: {total_fotos_ativas}")
    click.echo(f"    ❌ Inativas: {total_fotos_inativas}")
    click.echo(f"  📷 Funcionários com foto principal: {total_com_foto_principal}")
    click.echo(f"  ❌ Funcionários sem fotos: {total_sem_fotos}")
    click.echo()
    
    # Média
    if len(funcionarios) > 0:
        media_fotos = total_fotos_ativas / len(funcionarios)
        click.echo(f"📊 MÉDIA: {media_fotos:.1f} fotos ativas por funcionário")
        
        if media_fotos < 3:
            click.echo()
            click.echo("⚠️ RECOMENDAÇÃO:")
            click.echo("  Cadastre pelo menos 3-5 fotos por funcionário para melhor precisão!")
            click.echo("  Acesse: /ponto/gerenciar-fotos-faciais")
        elif media_fotos >= 3:
            click.echo("✅ Quantidade de fotos adequada!")
    
    click.echo("=" * 80)
