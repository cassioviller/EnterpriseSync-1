#!/usr/bin/env python3
"""
Debug do formulário RDO - verificar campos e estrutura
"""

def analisar_template_novo_html():
    """Analisar o template novo.html para identificar campos do formulário"""
    print("🔍 ANÁLISE DO TEMPLATE novo.html")
    print("=" * 50)
    
    try:
        with open('templates/rdo/novo.html', 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Procurar por campos de input relacionados a subatividades
        import re
        
        # Buscar campos de nome de subatividade
        nomes_subatividade = re.findall(r'name=["\']nome_subatividade_\d+["\']', conteudo)
        print(f"📝 Campos nome_subatividade encontrados: {len(nomes_subatividade)}")
        for campo in nomes_subatividade[:5]:  # Mostrar primeiros 5
            print(f"   {campo}")
        
        # Buscar campos de percentual
        percentuais = re.findall(r'name=["\']percentual_subatividade_\d+["\']', conteudo)
        print(f"📊 Campos percentual_subatividade encontrados: {len(percentuais)}")
        for campo in percentuais[:5]:
            print(f"   {campo}")
        
        # Buscar campos subatividade_ (sistema padrão)
        sistema_padrao = re.findall(r'name=["\']subatividade_\d+_percentual["\']', conteudo)
        print(f"⚙️ Campos subatividade_X_percentual encontrados: {len(sistema_padrao)}")
        for campo in sistema_padrao[:5]:
            print(f"   {campo}")
        
        # Verificar se há botão "Testar Último RDO"
        if 'Testar Último RDO' in conteudo:
            print("✅ Botão 'Testar Último RDO' presente")
        else:
            print("❌ Botão 'Testar Último RDO' NÃO encontrado")
        
        # Verificar se há JavaScript relacionado
        if 'api/test/rdo/ultimo-rdo-dados' in conteudo:
            print("✅ JavaScript para carregar último RDO presente")
        else:
            print("❌ JavaScript para carregar último RDO NÃO encontrado")
        
        return True
        
    except FileNotFoundError:
        print("❌ Arquivo templates/rdo/novo.html não encontrado")
        return False
    except Exception as e:
        print(f"❌ Erro ao analisar template: {e}")
        return False

def identificar_formato_campos():
    """Identificar qual formato de campos está sendo usado"""
    print("\n🎯 IDENTIFICAÇÃO DO FORMATO DOS CAMPOS")
    print("=" * 50)
    
    print("💭 FORMATOS POSSÍVEIS:")
    print("1. Campo manual: name='nome_subatividade_1', name='percentual_subatividade_1'")
    print("2. Sistema padrão: name='subatividade_123_percentual'")  
    print("3. Híbrido: ambos os formatos")
    print("4. Outro formato não identificado")
    
    print("\n🔧 CORREÇÃO APLICADA NO views.py:")
    print("- ✅ Suporte para campos manuais (nome_subatividade_X)")
    print("- ✅ Suporte para sistema padrão (subatividade_X_percentual)")
    print("- ✅ Logs detalhados para debugging")
    
    print("\n❓ PRÓXIMA VERIFICAÇÃO:")
    print("- Testar se o template usa o formato correto")
    print("- Verificar se JavaScript preenche campos corretos")
    print("- Confirmar se dados chegam no backend")

def simular_request_form():
    """Simular dados do request.form que deveriam chegar do frontend"""
    print("\n📝 SIMULAÇÃO DOS DADOS DO FORMULÁRIO")
    print("=" * 50)
    
    print("🎯 DADOS QUE O USUÁRIO PREENCHEU:")
    print("   Montagem de Pilares: 100%")
    print("   Instalação de Vigas: 100%")  
    print("   Soldagem de bases: 100%")
    
    print("\n📋 FORMATO ESPERADO NO request.form:")
    formatos = [
        "# Formato Manual:",
        "nome_subatividade_1 = 'Montagem de Pilares'",
        "percentual_subatividade_1 = '100'",
        "observacoes_subatividade_1 = ''",
        "",
        "# Formato Sistema:",
        "subatividade_58_percentual = '100'",  # ID da subatividade
        "subatividade_58_observacoes = ''",
        "",
        "# Outros campos:",
        "obra_id = '40'",
        "data_relatorio = '2025-08-30'"
    ]
    
    for linha in formatos:
        print(f"   {linha}")
    
    print("\n🔍 VERIFICAÇÃO NECESSÁRIA:")
    print("1. Adicionar logs para mostrar TODOS os campos do request.form")
    print("2. Confirmar se dados chegam com formato esperado")
    print("3. Testar salvamento com dados simulados")

def main():
    print("🔍 DEBUG COMPLETO DO FORMULÁRIO RDO")
    print("=" * 55)
    
    # Analisar template
    template_ok = analisar_template_novo_html()
    
    # Identificar formatos
    identificar_formato_campos()
    
    # Simular dados
    simular_request_form()
    
    print("\n📊 RESUMO DO DIAGNÓSTICO:")
    if template_ok:
        print("✅ Template novo.html existe e foi analisado")
        print("✅ Correção no views.py aplicada")
        print("⏳ Próximo passo: testar salvamento real")
    else:
        print("❌ Problema no template - template não encontrado")
    
    print("\n🎯 AÇÃO IMEDIATA:")
    print("Testar criação de RDO e verificar logs detalhados no console")

if __name__ == "__main__":
    main()