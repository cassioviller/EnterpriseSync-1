#!/usr/bin/env python3
"""Script para verificar rotas do SIGE"""

import sys
import os

# Adicionar o diretório da aplicação ao path
sys.path.insert(0, '/app')

try:
    from app import app
    
    print("🔍 Verificando rotas do SIGE...")
    
    with app.app_context():
        # Listar todas as rotas
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'rule': rule.rule,
                'methods': list(rule.methods)
            })
        
        print(f"📊 Total de rotas encontradas: {len(routes)}")
        
        # Verificar rotas específicas das correções
        rotas_novas = [
            'main.adicionar_servico_rdo_obra',
            'main.api_servicos_disponiveis_obra'
        ]
        
        endpoints_existentes = [r['endpoint'] for r in routes]
        
        for rota in rotas_novas:
            if rota in endpoints_existentes:
                print(f"✅ Nova rota encontrada: {rota}")
            else:
                print(f"❌ Nova rota não encontrada: {rota}")
        
        # Mostrar algumas rotas importantes
        print("\n📋 Rotas principais:")
        for route in routes[:10]:
            print(f"   {route['endpoint']}: {route['rule']}")
        
        print("✅ Verificação concluída com sucesso!")
        
except Exception as e:
    print(f"❌ Erro ao verificar rotas: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)