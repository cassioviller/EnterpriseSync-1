#!/usr/bin/env python3
"""
Script para testar se template RDO tem campos com name attributes corretos
"""

import requests
import re

def analisar_template_rdo():
    """Analisar template RDO para verificar campos"""
    
    print("🔍 ANÁLISE DO TEMPLATE RDO")
    print("=" * 40)
    
    try:
        response = requests.get("http://localhost:5000/funcionario/rdo/novo", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Erro HTTP: {response.status_code}")
            return
            
        content = response.text
        
        print("✅ Template carregado com sucesso")
        print(f"   Tamanho: {len(content)} bytes")
        
        # Procurar campos com name attributes
        pattern_names = r'name="([^"]+)"'
        names = re.findall(pattern_names, content)
        
        print(f"\n📋 CAMPOS COM NAME ATTRIBUTES: {len(names)}")
        for name in sorted(set(names)):
            print(f"   - {name}")
        
        # Procurar especificamente campos de subatividades
        subativ_fields = [name for name in names if 'subatividade' in name.lower()]
        print(f"\n🎯 CAMPOS DE SUBATIVIDADES: {len(subativ_fields)}")
        for field in subativ_fields:
            print(f"   - {field}")
        
        # Verificar se tem os campos que esperamos
        expected_fields = [
            'nome_subatividade_1_percentual',
            'nome_subatividade_1',
            'nome_subatividade_2_percentual',
            'nome_subatividade_2'
        ]
        
        print(f"\n✅ VERIFICAÇÃO DE CAMPOS ESPERADOS:")
        for field in expected_fields:
            if field in names:
                print(f"   ✅ {field} - ENCONTRADO")
            else:
                print(f"   ❌ {field} - AUSENTE")
        
        # Procurar inputs sem name
        pattern_inputs = r'<input[^>]*type="number"[^>]*>'
        inputs = re.findall(pattern_inputs, content)
        inputs_sem_name = []
        
        for input_tag in inputs:
            if 'name=' not in input_tag:
                inputs_sem_name.append(input_tag)
        
        print(f"\n⚠️ INPUTS SEM NAME ATTRIBUTE: {len(inputs_sem_name)}")
        for i, input_tag in enumerate(inputs_sem_name[:5]):  # Mostrar apenas 5
            print(f"   {i+1}. {input_tag[:80]}...")
            
        # Contar forms
        forms = re.findall(r'<form[^>]*>', content)
        print(f"\n📝 FORMULÁRIOS ENCONTRADOS: {len(forms)}")
        for i, form in enumerate(forms):
            print(f"   {i+1}. {form}")
    
    except Exception as e:
        print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    analisar_template_rdo()