#!/usr/bin/env python3
"""Análise rápida - sem grep"""
import os
import re
from pathlib import Path
from collections import defaultdict

def main():
    print("🔍 ANÁLISE RÁPIDA DO SISTEMA SIGE")
    print("="*80)
    
    # Listar arquivos Python
    arquivos = [f.name for f in Path('.').glob('*.py') if not f.name.startswith('analise_')]
    
    # Arquivos críticos (sempre manter)
    criticos = {
        'app.py', 'main.py', 'models.py', 'auth.py', 'views.py',
        'migrations.py', 'wsgi.py', 'gunicorn_config.py'
    }
    
    # Detectar imports
    importados = set(criticos)
    
    for arquivo in arquivos:
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar imports
            for match in re.finditer(r'^\s*(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)', content, re.MULTILINE):
                modulo = match.group(1)
                if f"{modulo}.py" in arquivos:
                    importados.add(f"{modulo}.py")
        except:
            pass
    
    # Órfãos
    orfaos = set(arquivos) - importados
    
    # Categorizar órfãos
    categorias = {
        'migration': [],
        'deploy': [],
        'fix': [],
        'test': [],
        'seed': [],
        'outros': []
    }
    
    for arq in sorted(orfaos):
        nome = arq.lower()
        if any(x in nome for x in ['migrat', 'adicionar_', 'atualizar_', 'create_']):
            categorias['migration'].append(arq)
        elif 'deploy' in nome or 'produc' in nome:
            categorias['deploy'].append(arq)
        elif 'fix_' in nome or 'correc' in nome or 'validar' in nome:
            categorias['fix'].append(arq)
        elif 'test' in nome:
            categorias['test'].append(arq)
        elif 'popul' in nome or 'gerar_' in nome or 'seed' in nome:
            categorias['seed'].append(arq)
        else:
            categorias['outros'].append(arq)
    
    # Resultados
    print(f"\n📊 Total arquivos Python: {len(arquivos)}")
    print(f"✅ Arquivos EM USO: {len(importados)}")
    print(f"⚠️  Arquivos ÓRFÃOS: {len(orfaos)} ({len(orfaos)/len(arquivos)*100:.1f}%)")
    print("\n" + "="*80)
    
    # Mostrar categorias
    print("\n📋 ARQUIVOS ÓRFÃOS POR CATEGORIA:\n")
    
    for cat, arqs in categorias.items():
        if arqs:
            print(f"\n🗂️  {cat.upper()} ({len(arqs)}):")
            for arq in arqs[:15]:
                print(f"   • {arq}")
            if len(arqs) > 15:
                print(f"   ... e mais {len(arqs)-15}")
    
    # Arquivos SEGUROS para mover (scripts de migração/deploy já executados)
    seguros_migration = [
        'adicionar_tipos_folga_ferias.py',
        'atualizar_admin_ids.py',
        'atualizar_badges_tabela.py',
        'correcao_horas_extras_final.py',
        'create_foto_base64_column.py',
        'deploy_final_checklist.py',
        'excluir_registros_agosto.py',
        'fix_detalhes_uso_production.py',
        'migrate_v8_0.py',
        'populacao_nova_simples.py',
        'script_migracao_producao.py',
    ]
    
    seguros_existentes = [s for s in seguros_migration if s in orfaos]
    
    print("\n" + "="*80)
    print(f"\n✅ Arquivos SEGUROS para mover para archive/ ({len(seguros_existentes)}):")
    for arq in seguros_existentes:
        print(f"   ✓ {arq}")
    
    # Salvar relatório
    with open('relatorio_rapido.txt', 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO RÁPIDO - ANÁLISE SIGE\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total: {len(arquivos)}\n")
        f.write(f"Em uso: {len(importados)}\n")
        f.write(f"Órfãos: {len(orfaos)}\n\n")
        
        f.write("ARQUIVOS EM USO:\n")
        for arq in sorted(importados):
            f.write(f"  {arq}\n")
        
        f.write("\n\nARQUIVOS ÓRFÃOS:\n")
        for cat, arqs in categorias.items():
            if arqs:
                f.write(f"\n{cat.upper()}:\n")
                for arq in sorted(arqs):
                    f.write(f"  {arq}\n")
    
    print(f"\n💾 Relatório: relatorio_rapido.txt")
    print("\n✅ Análise concluída!\n")

if __name__ == '__main__':
    main()
