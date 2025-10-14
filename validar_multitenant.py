#!/usr/bin/env python3
"""
Validar integridade multi-tenant - Verificar se queries usam admin_id
"""
import re
from pathlib import Path

def analisar_queries_views():
    """Analisa arquivos *_views.py e *_service.py para queries perigosas"""
    
    # Padrões PERIGOSOS (não usam admin_id)
    padroes_perigosos = [
        r'\.query\.get\(',  # Model.query.get(id) - NÃO valida admin_id
        r'\.query\.first\(\)',  # Model.query.first() - pega qualquer
        r'\.query\.all\(\)',  # Model.query.all() - pega todos admins
        r'\.query\.filter\((?!.*admin_id)',  # filter sem admin_id
    ]
    
    # Padrões SEGUROS
    padroes_seguros = [
        r'filter_by\(.*admin_id',  # filter_by com admin_id
        r'get_tenant_admin_id\(',  # Usa helper
        r'multitenant_helper',  # Usa helper module
    ]
    
    # Arquivos críticos para verificar
    arquivos_criticos = [
        'views.py',
        'ponto_views.py',
        'financeiro_views.py',
        'contabilidade_views.py',
        'folha_pagamento_views.py',
        'almoxarifado_views.py',
        'frota_views.py',
        'alimentacao_views.py',
        'propostas_views.py',
        'ponto_service.py',
        'financeiro_service.py',
    ]
    
    problemas = []
    
    for arquivo in arquivos_criticos:
        path = Path(arquivo)
        if not path.exists():
            continue
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            
            for i, linha in enumerate(linhas, 1):
                # Verificar padrões perigosos
                for padrao in padroes_perigosos:
                    if re.search(padrao, linha):
                        # Verificar se linha tem algum padrão seguro
                        tem_seguro = any(re.search(ps, linha) for ps in padroes_seguros)
                        
                        if not tem_seguro and 'admin_id' not in linha:
                            problemas.append({
                                'arquivo': arquivo,
                                'linha': i,
                                'codigo': linha.strip(),
                                'tipo': 'QUERY_SEM_ADMIN_ID'
                            })
        except Exception as e:
            print(f"⚠️  Erro ao processar {arquivo}: {e}")
    
    return problemas

def analisar_models():
    """Verifica se modelos críticos têm admin_id"""
    
    modelos_criticos = [
        'Funcionario', 'Obra', 'RegistroPonto', 'ServicoObra',
        'ContaPagar', 'ContaReceber', 'BancoEmpresa',
        'AlmoxarifadoItem', 'Veiculo', 'CustoVeiculo',
        'FolhaPagamento', 'Proposta'
    ]
    
    try:
        with open('models.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        problemas = []
        
        for modelo in modelos_criticos:
            # Buscar definição da classe
            padrao_classe = rf'class {modelo}\([^)]*\):'
            match = re.search(padrao_classe, content)
            
            if match:
                # Pegar próximas 50 linhas após a classe
                inicio = match.start()
                trecho = content[inicio:inicio+2000]
                
                # Verificar se tem admin_id
                if 'admin_id' not in trecho:
                    problemas.append({
                        'modelo': modelo,
                        'tipo': 'MODELO_SEM_ADMIN_ID'
                    })
        
        return problemas
        
    except Exception as e:
        print(f"⚠️  Erro ao processar models.py: {e}")
        return []

def main():
    print("🔒 VALIDAÇÃO DE INTEGRIDADE MULTI-TENANT")
    print("="*80)
    
    # 1. Analisar queries em views/services
    print("\n🔍 Analisando queries em views e services...")
    problemas_queries = analisar_queries_views()
    
    if problemas_queries:
        print(f"\n⚠️  ENCONTRADOS {len(problemas_queries)} PROBLEMAS EM QUERIES:\n")
        for p in problemas_queries[:20]:  # Mostrar primeiros 20
            print(f"  ❌ {p['arquivo']}:{p['linha']}")
            print(f"     {p['codigo']}")
            print()
        
        if len(problemas_queries) > 20:
            print(f"  ... e mais {len(problemas_queries)-20} problemas")
    else:
        print("✅ Nenhum problema crítico encontrado em queries!")
    
    # 2. Analisar modelos
    print("\n🔍 Analisando modelos críticos...")
    problemas_models = analisar_models()
    
    if problemas_models:
        print(f"\n⚠️  MODELOS SEM admin_id ({len(problemas_models)}):\n")
        for p in problemas_models:
            print(f"  ❌ {p['modelo']}")
    else:
        print("✅ Todos os modelos críticos têm admin_id!")
    
    # 3. Resumo
    total_problemas = len(problemas_queries) + len(problemas_models)
    
    print("\n" + "="*80)
    print(f"\n📊 RESUMO:")
    print(f"  Problemas em queries: {len(problemas_queries)}")
    print(f"  Modelos sem admin_id: {len(problemas_models)}")
    print(f"  TOTAL: {total_problemas}")
    
    if total_problemas == 0:
        print("\n✅ Sistema SEGURO - Integridade multi-tenant validada!")
    else:
        print(f"\n⚠️  Sistema tem {total_problemas} problemas de multi-tenant")
    
    # 4. Salvar relatório
    with open('relatorio_multitenant.txt', 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE VALIDAÇÃO MULTI-TENANT\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Total de problemas: {total_problemas}\n\n")
        
        f.write("PROBLEMAS EM QUERIES:\n")
        f.write("-"*80 + "\n")
        for p in problemas_queries:
            f.write(f"{p['arquivo']}:{p['linha']} - {p['codigo']}\n")
        
        f.write("\n\nMODELOS SEM admin_id:\n")
        f.write("-"*80 + "\n")
        for p in problemas_models:
            f.write(f"{p['modelo']}\n")
    
    print(f"\n💾 Relatório: relatorio_multitenant.txt\n")

if __name__ == '__main__':
    main()
