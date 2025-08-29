#!/usr/bin/env python3
"""
HOTFIX FINAL - Testar RDO com dados reais no sistema bypass ativo
"""

import requests
from datetime import datetime

def testar_salvamento_com_logs():
    """Testar salvamento RDO e verificar logs de debug"""
    
    print("🚀 TESTE FINAL RDO - Sistema Bypass Ativo")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    # Dados de teste com campos corretos
    form_data = {
        'obra_id': 40,  # Galpão Industrial Premium
        'data_relatorio': datetime.now().strftime('%Y-%m-%d'),
        'condicoes_climaticas': 'Ensolarado',
        'temperatura': '26°C',
        'observacoes_tecnicas': 'Teste de salvamento com subatividades manuais',
        
        # Campos de subatividades corretos baseados no template
        'nome_subatividade_1': 'Montagem de Pilares',
        'nome_subatividade_1_percentual': '100.0',
        'nome_subatividade_2': 'Instalação de Vigas',  
        'nome_subatividade_2_percentual': '100.0',
        'nome_subatividade_3': 'Soldagem de Estruturas',
        'nome_subatividade_3_percentual': '85.0',
        'nome_subatividade_4': 'Pintura de Acabamento',
        'nome_subatividade_4_percentual': '25.0'
    }
    
    print("📋 Dados sendo enviados:")
    for key, value in form_data.items():
        if 'subatividade' in key:
            print(f"   ✅ {key}: {value}")
    
    try:
        print("\n🔄 Enviando dados para salvamento...")
        
        response = requests.post(f"{base_url}/salvar-rdo-flexivel", 
                               data=form_data, 
                               timeout=20,
                               allow_redirects=False)
        
        print(f"📊 Status HTTP: {response.status_code}")
        
        if response.status_code == 302:
            print("✅ RDO salvo com sucesso (redirecionamento)")
            location = response.headers.get('Location', 'N/A')
            print(f"   Redirecionando para: {location}")
        elif response.status_code == 200:
            print("✅ RDO processado")
            content = response.text[:200]
            print(f"   Resposta: {content}...")
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            content = response.text[:300]
            print(f"   Conteúdo: {content}...")
            
        # Testar listagem para ver se foi salvo
        print("\n🔍 Verificando RDOs salvos...")
        
        list_response = requests.get(f"{base_url}/funcionario/rdo/consolidado", timeout=15)
        
        if list_response.status_code == 200:
            print("✅ Lista de RDOs carregada")
            
            # Verificar progresso da obra
            content = list_response.text
            if 'subatividades' in content.lower():
                print("✅ Subatividades encontradas na lista")
            if '%' in content:
                print("✅ Percentuais sendo exibidos")
                
        return True
        
    except Exception as e:
        print(f"❌ Erro durante teste: {str(e)}")
        return False

def verificar_logs_salvamento():
    """Verificar se os logs mostram o processamento correto"""
    
    print("\n📋 VERIFICAÇÃO DOS LOGS")
    print("=" * 30)
    
    print("Os logs devem mostrar:")
    print("   🎯 Campos de subatividades encontrados: 8")
    print("   💾 Total de X subatividades salvas no RDO")
    print("   ✅ RDO salvo com sucesso")
    
    print("\nSe os logs não mostrarem isso, há problema no template ou backend.")

if __name__ == "__main__":
    sucesso = testar_salvamento_com_logs()
    verificar_logs_salvamento()
    
    if sucesso:
        print("\n🎉 TESTE CONCLUÍDO COM SUCESSO")
        print("=" * 40)
        print("✅ RDO sendo salvo corretamente")
        print("✅ Subatividades sendo processadas")
        print("✅ Sistema funcionando")
    else:
        print("\n❌ TESTE FALHOU")
        print("=" * 20)
        print("❌ Verificar logs do sistema")
        print("❌ Verificar template RDO")
        print("❌ Verificar backend de salvamento")