#!/usr/bin/env python3
"""
🔍 VERIFICAÇÃO DEPLOY VEÍCULOS - PRODUÇÃO
========================================
Script para diagnosticar e verificar o deploy de veículos em produção
"""

import os
import sys
import json
from datetime import datetime

def verificar_deploy():
    """Verificar status do deploy de veículos"""
    print("🔍 VERIFICANDO DEPLOY DE VEÍCULOS EM PRODUÇÃO")
    print("=" * 50)
    
    # Verificar se arquivo de resultado existe
    result_file = '/tmp/veiculos_v2_deploy_result.json'
    if os.path.exists(result_file):
        print(f"✅ Arquivo de resultado encontrado: {result_file}")
        try:
            with open(result_file, 'r') as f:
                result = json.load(f)
            print(f"📊 Status do último deploy: {result['status']}")
            print(f"📅 Timestamp: {result['timestamp']}")
            print(f"✅ Fases completas: {result['success_count']}/{result['total_phases']}")
            
            if result['errors']:
                print(f"❌ Erros: {len(result['errors'])}")
                for error in result['errors']:
                    print(f"   - {error}")
            
            if result['warnings']:
                print(f"⚠️ Warnings: {len(result['warnings'])}")
                for warning in result['warnings']:
                    print(f"   - {warning}")
                    
        except Exception as e:
            print(f"❌ Erro ao ler resultado: {e}")
    else:
        print("⚠️ Arquivo de resultado não encontrado")
    
    # Verificar logs de deploy
    log_file = '/tmp/veiculos_v2_deploy.log'
    if os.path.exists(log_file):
        print(f"✅ Log de deploy encontrado: {log_file}")
        print("📋 Últimas 10 linhas do log:")
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            for line in lines[-10:]:
                print(f"   {line.strip()}")
        except Exception as e:
            print(f"❌ Erro ao ler log: {e}")
    else:
        print("⚠️ Log de deploy não encontrado")

if __name__ == "__main__":
    verificar_deploy()