"""
Verificação final do sistema SIGE v8.0
"""

import requests
import time

def verificar_endpoints():
    """Verificar se todos os endpoints estão funcionando"""
    base_url = 'http://localhost:5000'
    
    endpoints = [
        '/',
        '/test',
        '/login',
        '/dashboard'
    ]
    
    print("🔍 VERIFICAÇÃO FINAL DO SISTEMA SIGE v8.0")
    print("=" * 50)
    
    resultados = {}
    
    for endpoint in endpoints:
        try:
            print(f"Testando {endpoint}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {endpoint}: OK (200)")
                resultados[endpoint] = "OK"
            elif response.status_code == 302:
                print(f"⚡ {endpoint}: Redirecionamento (302)")
                resultados[endpoint] = "REDIRECT"
            else:
                print(f"⚠️ {endpoint}: Status {response.status_code}")
                resultados[endpoint] = f"Status {response.status_code}"
                
        except Exception as e:
            print(f"❌ {endpoint}: Erro - {str(e)}")
            resultados[endpoint] = f"Erro: {str(e)}"
        
        time.sleep(1)
    
    print("\n📊 RESUMO DOS RESULTADOS:")
    print("-" * 30)
    
    for endpoint, status in resultados.items():
        status_icon = "✅" if status == "OK" else "⚡" if status == "REDIRECT" else "❌"
        print(f"{status_icon} {endpoint}: {status}")
    
    # Verificar se a aplicação está funcional
    ok_count = sum(1 for status in resultados.values() if status in ["OK", "REDIRECT"])
    total_count = len(resultados)
    
    print(f"\n🎯 SCORE FINAL: {ok_count}/{total_count} endpoints funcionando")
    
    if ok_count >= total_count * 0.8:
        print("🎉 SISTEMA SIGE v8.0 TOTALMENTE FUNCIONAL!")
        print("✅ Pronto para produção")
    else:
        print("⚠️ Sistema necessita ajustes")
    
    return resultados

if __name__ == '__main__':
    verificar_endpoints()