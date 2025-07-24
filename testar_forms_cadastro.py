#!/usr/bin/env python3
"""
Script para testar problemas específicos dos formulários de cadastro
"""

from app import app
from forms import DepartamentoForm, FuncaoForm
from werkzeug.test import Client

def testar_forms():
    with app.test_request_context():
        print("🔍 Testando formulários de cadastro...")
        
        # 1. Testar se os formulários são válidos
        print("\n1. Validação de formulários:")
        
        # Teste DepartamentoForm
        form_data = {'nome': 'Departamento Teste', 'descricao': 'Teste', 'csrf_token': 'test'}
        form = DepartamentoForm(data=form_data)
        
        print(f"DepartamentoForm válido: {form.validate()}")
        if not form.validate():
            print(f"Erros: {form.errors}")
        
        # Teste FuncaoForm
        form_data = {'nome': 'Função Teste', 'descricao': 'Teste', 'salario_base': 2500.0, 'csrf_token': 'test'}
        form = FuncaoForm(data=form_data)
        
        print(f"FuncaoForm válido: {form.validate()}")
        if not form.validate():
            print(f"Erros: {form.errors}")

def testar_rotas():
    """Testar se as rotas estão respondendo"""
    with app.test_client() as client:
        print("\n2. Testando rotas:")
        
        # Testar GET das páginas
        response = client.get('/departamentos')
        print(f"GET /departamentos: {response.status_code}")
        
        response = client.get('/funcoes')
        print(f"GET /funcoes: {response.status_code}")
        
        response = client.get('/horarios')
        print(f"GET /horarios: {response.status_code}")
        
        response = client.get('/servicos')
        print(f"GET /servicos: {response.status_code}")

if __name__ == "__main__":
    testar_forms()
    testar_rotas()