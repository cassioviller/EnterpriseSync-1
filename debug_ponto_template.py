#!/usr/bin/env python3
"""
Debug específico para template do ponto
Verifica se o problema está na renderização
"""

from app import app, db
from models import *
from flask import render_template_string
from datetime import date, time

def debug_template_rendering():
    """Debug da renderização do template"""
    
    with app.app_context():
        # Buscar um registro real
        registro = RegistroPonto.query.filter(
            RegistroPonto.hora_almoco_saida.isnot(None)
        ).first()
        
        if not registro:
            print("❌ Nenhum registro com horário de almoço encontrado")
            return
        
        print(f"✓ Debugando registro ID: {registro.id}")
        print(f"  Data: {registro.data}")
        print(f"  Almoço Saída: {registro.hora_almoco_saida}")
        print(f"  Almoço Retorno: {registro.hora_almoco_retorno}")
        
        # Template simplificado para teste
        template_teste = """
        <tr>
            <td>{{ registro.funcionario_ref.nome }}</td>
            <td>{{ registro.data.strftime('%d/%m/%Y') }}</td>
            <td>
                {% if registro.hora_almoco_saida %}
                    <span class="badge bg-warning">{{ registro.hora_almoco_saida.strftime('%H:%M') }}</span>
                {% else %}
                    <span class="text-muted">-</span>
                {% endif %}
            </td>
            <td>
                {% if registro.hora_almoco_retorno %}
                    <span class="badge bg-info">{{ registro.hora_almoco_retorno.strftime('%H:%M') }}</span>
                {% else %}
                    <span class="text-muted">-</span>
                {% endif %}
            </td>
        </tr>
        """
        
        # Renderizar template
        html_resultado = render_template_string(template_teste, registro=registro)
        
        print("\n=== RESULTADO DA RENDERIZAÇÃO ===")
        print(html_resultado)
        
        # Verificar se campos estão vazios
        if not registro.hora_almoco_saida:
            print("⚠️ PROBLEMA: hora_almoco_saida está vazio no banco!")
        
        if not registro.hora_almoco_retorno:
            print("⚠️ PROBLEMA: hora_almoco_retorno está vazio no banco!")

def verificar_formulario_modal():
    """Verifica se o modal do formulário tem os campos"""
    
    print("\n=== VERIFICAÇÃO DO MODAL ===")
    
    # Ler template ponto.html
    try:
        with open('templates/ponto.html', 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Procurar pelos campos de almoço no modal
        if 'hora_almoco_saida' in conteudo:
            print("✓ Campo hora_almoco_saida encontrado no template")
        else:
            print("❌ Campo hora_almoco_saida NÃO encontrado no template")
        
        if 'hora_almoco_retorno' in conteudo:
            print("✓ Campo hora_almoco_retorno encontrado no template")
        else:
            print("❌ Campo hora_almoco_retorno NÃO encontrado no template")
            
        # Verificar labels
        if 'Saída Almoço' in conteudo:
            print("✓ Label 'Saída Almoço' encontrado")
        else:
            print("❌ Label 'Saída Almoço' NÃO encontrado")
            
        if 'Retorno Almoço' in conteudo:
            print("✓ Label 'Retorno Almoço' encontrado")
        else:
            print("❌ Label 'Retorno Almoço' NÃO encontrado")
        
    except Exception as e:
        print(f"❌ Erro ao ler template: {e}")

if __name__ == "__main__":
    print("=== DEBUG DO TEMPLATE PONTO ===")
    
    debug_template_rendering()
    verificar_formulario_modal()
    
    print("\n✅ Debug finalizado!")