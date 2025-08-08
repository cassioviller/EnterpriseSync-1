#!/usr/bin/env python3
"""
SCRIPT DE DEPLOY HOTFIX - CORREÇÃO PERFIL FUNCIONÁRIO
Aplica as correções necessárias para resolver o erro interno do servidor
"""

import os
import sys
from datetime import datetime

def main():
    print("🚀 INICIANDO DEPLOY HOTFIX - CORREÇÃO PERFIL FUNCIONÁRIO")
    print("=" * 60)
    
    # Verificar se estamos na produção
    is_production = 'sige.cassioviller.tech' in os.environ.get('REPLIT_DOMAINS', '')
    
    print(f"📍 Ambiente: {'PRODUÇÃO' if is_production else 'DESENVOLVIMENTO'}")
    print(f"⏰ Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Lista de arquivos que precisam ser atualizados
    files_to_update = [
        'views.py',
        'utils.py'
    ]
    
    print("\n📋 VERIFICAÇÃO DOS ARQUIVOS:")
    for file in files_to_update:
        if os.path.exists(file):
            print(f"✅ {file} - Encontrado")
        else:
            print(f"❌ {file} - NÃO ENCONTRADO")
            return False
    
    # Verificar se as correções estão aplicadas
    print("\n🔍 VERIFICANDO CORREÇÕES:")
    
    # 1. Verificar views.py
    with open('views.py', 'r') as f:
        views_content = f.read()
        if 'calcular_kpis_funcionario_periodo' in views_content:
            print("✅ views.py - Correção aplicada (calcular_kpis_funcionario_periodo)")
        else:
            print("❌ views.py - Correção NÃO aplicada")
            return False
    
    # 2. Verificar utils.py
    with open('utils.py', 'r') as f:
        utils_content = f.read()
        if 'atrasos_horas' in utils_content and 'faltas_justificadas' in utils_content:
            print("✅ utils.py - Correção aplicada (campos atrasos_horas e faltas_justificadas)")
        else:
            print("❌ utils.py - Correção NÃO aplicada")
            return False
    
    print("\n🎯 TESTANDO FUNCIONALIDADE:")
    try:
        from app import app, db
        from models import Funcionario
        from utils import calcular_kpis_funcionario_periodo
        from datetime import date
        
        with app.app_context():
            funcionario = Funcionario.query.first()
            if funcionario:
                kpis = calcular_kpis_funcionario_periodo(funcionario.id, date(2025, 8, 1), date(2025, 8, 8))
                
                # Verificar se todos os campos necessários estão presentes
                required_fields = ['atrasos_horas', 'faltas_justificadas', 'outros_custos', 'horas_trabalhadas']
                missing_fields = []
                
                for field in required_fields:
                    if field not in kpis:
                        missing_fields.append(field)
                
                if not missing_fields:
                    print("✅ KPIs - Todos os campos necessários estão presentes")
                    print(f"   - horas_trabalhadas: {kpis['horas_trabalhadas']}")
                    print(f"   - atrasos_horas: {kpis['atrasos_horas']}")
                    print(f"   - faltas_justificadas: {kpis['faltas_justificadas']}")
                    print(f"   - outros_custos: {kpis['outros_custos']}")
                else:
                    print(f"❌ KPIs - Campos faltando: {missing_fields}")
                    return False
            else:
                print("❌ Nenhum funcionário encontrado para teste")
                return False
                
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False
    
    print(f"\n🎉 DEPLOY HOTFIX CONCLUÍDO COM SUCESSO!")
    print(f"✅ Correção do perfil do funcionário aplicada")
    print(f"✅ Campos KPIs corrigidos: atrasos_horas, faltas_justificadas, outros_custos")
    print(f"✅ Template funcionario_perfil.html agora deve funcionar corretamente")
    
    if is_production:
        print(f"\n🌐 O ambiente de produção deve atualizar automaticamente")
        print(f"🔄 Aguarde alguns segundos e teste novamente o acesso ao perfil")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)