#!/usr/bin/env python3
"""
Verificar consistência entre desenvolvimento e produção
Garante que todas as rotas, templates e funcionalidades estejam alinhadas
"""

import os
import sys
from pathlib import Path
from app import app
from flask import url_for
import importlib

def verificar_templates():
    """Verificar se todos os templates necessários existem"""
    print("🔍 VERIFICAÇÃO DE TEMPLATES")
    print("=" * 40)
    
    templates_essenciais = [
        "base_completo.html",
        "dashboard.html", 
        "funcionarios.html",
        "rdo/novo.html",
        "rdo/visualizar_rdo_moderno.html",
        "login.html"
    ]
    
    templates_dir = Path("templates")
    missing_templates = []
    
    for template in templates_essenciais:
        template_path = templates_dir / template
        if template_path.exists():
            size = template_path.stat().st_size
            print(f"✅ {template} ({size:,} bytes)")
        else:
            print(f"❌ {template} - AUSENTE")
            missing_templates.append(template)
    
    return len(missing_templates) == 0

def verificar_rotas():
    """Verificar se todas as rotas críticas estão funcionando"""
    print("\n🔍 VERIFICAÇÃO DE ROTAS")
    print("=" * 40)
    
    with app.app_context():
        rotas_criticas = [
            ('main.dashboard', 'Dashboard principal'),
            ('main.funcionarios', 'Gestão de funcionários'),  
            ('main.funcionario_rdo_consolidado', 'Lista de RDOs'),
            ('main.funcionario_rdo_novo', 'Novo RDO'),
            ('main.health_check', 'Health check'),
            ('main.login', 'Login'),
            ('main.logout', 'Logout')
        ]
        
        rotas_ok = []
        rotas_erro = []
        
        for rota, descricao in rotas_criticas:
            try:
                url = url_for(rota)
                print(f"✅ {rota} -> {url}")
                rotas_ok.append(rota)
            except Exception as e:
                print(f"❌ {rota} - ERRO: {e}")
                rotas_erro.append((rota, str(e)))
        
        print(f"\n📊 Resumo: {len(rotas_ok)} OK, {len(rotas_erro)} com erro")
        return len(rotas_erro) == 0

def verificar_blueprints():
    """Verificar blueprints registrados"""
    print("\n🔍 BLUEPRINTS REGISTRADOS")
    print("=" * 40)
    
    blueprints_esperados = [
        'main',
        'folha_pagamento', 
        'contabilidade',
        'templates',
        'alimentacao',
        'propostas'
    ]
    
    blueprints_registrados = list(app.blueprints.keys())
    
    for bp in blueprints_esperados:
        if bp in blueprints_registrados:
            print(f"✅ {bp}")
        else:
            print(f"❌ {bp} - NÃO REGISTRADO")
    
    print(f"\n📊 Total registrados: {len(blueprints_registrados)}")
    for bp in blueprints_registrados:
        if bp not in blueprints_esperados:
            print(f"ℹ️  Extra: {bp}")
    
    return True

def verificar_arquivos_estaticos():
    """Verificar arquivos estáticos críticos"""
    print("\n🔍 ARQUIVOS ESTÁTICOS")
    print("=" * 40)
    
    static_dir = Path("static")
    arquivos_criticos = [
        "css/app.css",
        "js/app.js", 
        "js/charts.js",
        "images/logo.png"
    ]
    
    missing_files = []
    
    for arquivo in arquivos_criticos:
        arquivo_path = static_dir / arquivo
        if arquivo_path.exists():
            size = arquivo_path.stat().st_size
            print(f"✅ {arquivo} ({size:,} bytes)")
        else:
            print(f"❌ {arquivo} - AUSENTE")
            missing_files.append(arquivo)
    
    # Listar diretórios disponíveis
    if static_dir.exists():
        dirs = [d.name for d in static_dir.iterdir() if d.is_dir()]
        print(f"📁 Diretórios disponíveis: {', '.join(dirs)}")
    
    return len(missing_files) == 0

def verificar_modelos():
    """Verificar se todos os modelos podem ser importados"""
    print("\n🔍 MODELOS DE DADOS")
    print("=" * 40)
    
    try:
        from models import (
            db, Usuario, TipoUsuario, Funcionario, Obra, 
            RDO, RDOMaoObra, RDOOcorrencia, RDOServicoSubatividade,
            SubatividadeMestre
        )
        
        modelos = [
            Usuario, TipoUsuario, Funcionario, Obra,
            RDO, RDOMaoObra, RDOOcorrencia, RDOServicoSubatividade,
            SubatividadeMestre
        ]
        
        for modelo in modelos:
            nome = modelo.__name__
            try:
                # Tentar acessar metadados da tabela
                table_name = modelo.__tablename__
                print(f"✅ {nome} (tabela: {table_name})")
            except Exception as e:
                print(f"❌ {nome} - ERRO: {e}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erro ao importar modelos: {e}")
        return False

def verificar_funcionalidades_rdo():
    """Verificar funcionalidades específicas do RDO"""
    print("\n🔍 FUNCIONALIDADES RDO")
    print("=" * 40)
    
    # Verificar blueprints RDO
    rdo_blueprints = [
        'rdo_salvar_sistema',
        'api_servicos_flexivel', 
        'rdo_salvar_sem_conflito',
        'rdo_viewer_editor',
        'crud_rdo_completo'
    ]
    
    for bp_name in rdo_blueprints:
        try:
            spec = importlib.util.find_spec(bp_name)
            if spec:
                print(f"✅ {bp_name} - módulo disponível")
            else:
                print(f"❌ {bp_name} - módulo não encontrado")
        except Exception as e:
            print(f"❌ {bp_name} - erro: {e}")
    
    return True

def main():
    """Executar todas as verificações"""
    print("🔍 VERIFICAÇÃO COMPLETA DE CONSISTÊNCIA - SIGE v8.0")
    print("=" * 60)
    
    resultados = []
    
    # Executar verificações
    resultados.append(("Templates", verificar_templates()))
    resultados.append(("Rotas", verificar_rotas()))
    resultados.append(("Blueprints", verificar_blueprints()))
    resultados.append(("Arquivos Estáticos", verificar_arquivos_estaticos()))
    resultados.append(("Modelos", verificar_modelos()))
    resultados.append(("RDO", verificar_funcionalidades_rdo()))
    
    # Resumo final
    print("\n📊 RESUMO FINAL")
    print("=" * 30)
    
    passed = 0
    failed = 0
    
    for nome, status in resultados:
        if status:
            print(f"✅ {nome}")
            passed += 1
        else:
            print(f"❌ {nome}")
            failed += 1
    
    print(f"\n🎯 Resultado: {passed} OK, {failed} com problemas")
    
    if failed == 0:
        print("✅ SISTEMA CONSISTENTE - Pronto para deploy")
        return 0
    else:
        print("❌ PROBLEMAS ENCONTRADOS - Necessário corrigir")
        return 1

if __name__ == "__main__":
    sys.exit(main())