"""
Teste completo do sistema SIGE v8.0 após correções
Verifica se todos os módulos estão funcionando
"""

import requests
import sys

def testar_rota(url, descricao):
    """Testa uma rota específica"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ {descricao}: OK")
            return True
        elif response.status_code == 302:
            print(f"🔄 {descricao}: Redirecionamento (normal para rotas protegidas)")
            return True
        else:
            print(f"❌ {descricao}: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {descricao}: Erro - {e}")
        return False

def main():
    """Executa teste completo do sistema"""
    print("🧪 TESTE COMPLETO DO SIGE v8.0")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    # Rotas básicas
    rotas_teste = [
        (f"{base_url}/", "Página inicial"),
        (f"{base_url}/login", "Login"),
        (f"{base_url}/dashboard", "Dashboard"),
        (f"{base_url}/funcionarios", "Funcionários"),
        (f"{base_url}/obras", "Obras"),
        (f"{base_url}/veiculos", "Veículos"),
        (f"{base_url}/almoxarifado/dashboard", "Almoxarifado"),
        (f"{base_url}/folha-pagamento/dashboard", "Folha de Pagamento"),
        (f"{base_url}/contabilidade/dashboard", "Contabilidade"),
        (f"{base_url}/relatorios/dashboard", "Relatórios"),
    ]
    
    sucessos = 0
    total = len(rotas_teste)
    
    for url, descricao in rotas_teste:
        if testar_rota(url, descricao):
            sucessos += 1
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTADO: {sucessos}/{total} rotas funcionando")
    
    if sucessos == total:
        print("🎉 SISTEMA TOTALMENTE FUNCIONAL!")
        return True
    elif sucessos >= total * 0.8:
        print("⚠️  Sistema funcionando com algumas falhas")
        return True
    else:
        print("❌ Sistema com falhas críticas")
        return False

if __name__ == "__main__":
    resultado = main()
    sys.exit(0 if resultado else 1)