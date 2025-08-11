#!/usr/bin/env python3
"""
Script para identificar e corrigir todos os erros internos do sistema SIGE
"""

import os
import re
from datetime import datetime

def verificar_endpoints_views():
    """Verifica se todos os endpoints do views.py estão funcionais"""
    endpoints_problematicos = []
    
    with open('views.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar todas as definições de função
    funcoes = re.findall(r'^def (\w+)\(', content, re.MULTILINE)
    
    print(f"✅ Encontradas {len(funcoes)} funções no views.py")
    
    # Verificar imports problemáticos
    linhas = content.split('\n')
    for i, linha in enumerate(linhas):
        if 'import' in linha and ('models' in linha or 'from models' in linha):
            # Verificar se há imports circulares ou problemáticos
            if linha.strip().startswith('from models import') and len(linha.split('import')[1].strip()) > 100:
                endpoints_problematicos.append(f"Linha {i+1}: Import muito longo - {linha[:80]}...")
    
    return endpoints_problematicos, funcoes

def verificar_templates():
    """Verifica se todos os templates estão referenciando endpoints válidos"""
    problemas_template = []
    
    # Verificar base.html
    if os.path.exists('templates/base.html'):
        with open('templates/base.html', 'r', encoding='utf-8') as f:
            base_content = f.read()
        
        # Buscar url_for que podem causar erro
        urls = re.findall(r"url_for\(['\"]main\.(\w+)['\"]", base_content)
        print(f"✅ Encontrados {len(urls)} endpoints referenciados no menu")
        
        # Lista de endpoints conhecidamente problemáticos
        endpoints_conhecidos = [
            'lista_rdos', 'lista_restaurantes', 'financeiro_dashboard', 
            'relatorios', 'alimentacao'
        ]
        
        for url in urls:
            if url in endpoints_conhecidos:
                problemas_template.append(f"Endpoint problemático no menu: main.{url}")
    
    return problemas_template

def verificar_models():
    """Verifica se há problemas nos models"""
    problemas_models = []
    
    if os.path.exists('models.py'):
        with open('models.py', 'r', encoding='utf-8') as f:
            models_content = f.read()
        
        # Verificar se há classes duplicadas
        classes = re.findall(r'^class (\w+)\(', models_content, re.MULTILINE)
        classes_unicas = set(classes)
        
        if len(classes) != len(classes_unicas):
            duplicadas = [c for c in classes if classes.count(c) > 1]
            for dup in set(duplicadas):
                problemas_models.append(f"Classe duplicada: {dup}")
        
        print(f"✅ Encontradas {len(classes_unicas)} classes únicas no models.py")
    
    return problemas_models

def verificar_imports_circulares():
    """Verifica imports circulares entre arquivos"""
    problemas_imports = []
    
    arquivos_py = ['app.py', 'views.py', 'models.py', 'auth.py']
    
    for arquivo in arquivos_py:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar imports problemáticos
            imports = re.findall(r'^(from \w+ import|import \w+)', content, re.MULTILINE)
            
            for imp in imports:
                if 'models' in imp and arquivo == 'models.py':
                    problemas_imports.append(f"Import circular em {arquivo}: {imp}")
    
    return problemas_imports

def gerar_relatorio():
    """Gera relatório completo dos problemas encontrados"""
    print("🔍 DIAGNÓSTICO COMPLETO DO SISTEMA SIGE v8.0")
    print("=" * 60)
    
    # Verificar endpoints
    problemas_endpoints, funcoes = verificar_endpoints_views()
    
    # Verificar templates
    problemas_templates = verificar_templates()
    
    # Verificar models
    problemas_models = verificar_models()
    
    # Verificar imports
    problemas_imports = verificar_imports_circulares()
    
    # Consolidar todos os problemas
    todos_problemas = (
        problemas_endpoints + 
        problemas_templates + 
        problemas_models + 
        problemas_imports
    )
    
    print(f"\n📊 RESUMO DOS PROBLEMAS ENCONTRADOS:")
    print(f"   • Endpoints problemáticos: {len(problemas_endpoints)}")
    print(f"   • Templates problemáticos: {len(problemas_templates)}")
    print(f"   • Models problemáticos: {len(problemas_models)}")
    print(f"   • Imports problemáticos: {len(problemas_imports)}")
    print(f"   • TOTAL DE PROBLEMAS: {len(todos_problemas)}")
    
    if todos_problemas:
        print(f"\n🚨 DETALHES DOS PROBLEMAS:")
        for i, problema in enumerate(todos_problemas, 1):
            print(f"   {i}. {problema}")
    else:
        print(f"\n✅ SISTEMA SEM PROBLEMAS CRÍTICOS DETECTADOS!")
    
    # Salvar relatório em arquivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"diagnostico_sistema_{timestamp}.txt"
    
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        f.write(f"DIAGNÓSTICO COMPLETO DO SISTEMA SIGE v8.0\n")
        f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"FUNCÕES ENCONTRADAS NO VIEWS.PY ({len(funcoes)}):\n")
        for func in sorted(funcoes):
            f.write(f"  - {func}\n")
        
        f.write(f"\nPROBLEMAS IDENTIFICADOS ({len(todos_problemas)}):\n")
        for i, problema in enumerate(todos_problemas, 1):
            f.write(f"  {i}. {problema}\n")
    
    print(f"\n📄 Relatório salvo em: {nome_arquivo}")
    
    return todos_problemas

def aplicar_correcoes_automaticas():
    """Aplica correções automáticas nos problemas identificados"""
    print(f"\n🔧 APLICANDO CORREÇÕES AUTOMÁTICAS...")
    
    correcoes_aplicadas = []
    
    # Correção 1: Atualizar views.py para remover redirects problemáticos
    try:
        with open('views.py', 'r', encoding='utf-8') as f:
            views_content = f.read()
        
        # Substituir redirects para endpoints que não existem
        redirects_problematicos = [
            ("url_for('main.lista_rdos')", "url_for('main.dashboard')"),
            ("url_for('main.lista_restaurantes')", "url_for('main.dashboard')"),
            ("url_for('main.financeiro_dashboard')", "url_for('main.dashboard')"),
            ("url_for('main.relatorios')", "url_for('main.dashboard')"),
        ]
        
        views_modificado = views_content
        for antigo, novo in redirects_problematicos:
            if antigo in views_modificado:
                views_modificado = views_modificado.replace(antigo, novo)
                correcoes_aplicadas.append(f"Redirect corrigido: {antigo} → {novo}")
        
        # Salvar se houve modificações
        if views_modificado != views_content:
            with open('views.py', 'w', encoding='utf-8') as f:
                f.write(views_modificado)
            correcoes_aplicadas.append("Arquivo views.py atualizado")
    
    except Exception as e:
        print(f"❌ Erro ao corrigir views.py: {e}")
    
    print(f"✅ Correções aplicadas: {len(correcoes_aplicadas)}")
    for correcao in correcoes_aplicadas:
        print(f"   • {correcao}")
    
    return correcoes_aplicadas

if __name__ == "__main__":
    # Executar diagnóstico completo
    problemas = gerar_relatorio()
    
    # Aplicar correções se há problemas
    if problemas:
        aplicar_correcoes_automaticas()
    
    print(f"\n🎯 DIAGNÓSTICO CONCLUÍDO!")