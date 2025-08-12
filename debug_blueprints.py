#!/usr/bin/env python3
"""
Debug dos Blueprints registrados no Flask
"""

import sys
sys.path.append('.')

from app import app

print("🔍 DEBUG DOS BLUEPRINTS REGISTRADOS")
print("=" * 50)

# Listar todos os blueprints
print("📋 BLUEPRINTS REGISTRADOS:")
for name, blueprint in app.blueprints.items():
    print(f"  • {name}: {blueprint}")

print("\n📍 ROTAS REGISTRADAS:")
for rule in app.url_map.iter_rules():
    print(f"  {rule.rule:<30} -> {rule.endpoint}")

# Verificar rotas específicas
rotas_verificar = [
    '/folha-pagamento/dashboard',
    '/contabilidade/dashboard'
]

print(f"\n🎯 VERIFICAÇÃO ESPECÍFICA:")
for rota in rotas_verificar:
    try:
        with app.test_client() as client:
            response = client.get(rota)
            status = "✅" if response.status_code != 404 else "❌"
            print(f"  {rota:<30} {status} ({response.status_code})")
    except Exception as e:
        print(f"  {rota:<30} ❌ ERRO: {e}")

print("=" * 50)