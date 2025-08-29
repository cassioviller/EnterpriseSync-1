#!/usr/bin/env python3
"""
Script para corrigir problema de salvamento de RDO
O problema: dados não persistem corretamente quando "Testar Último RDO" é usado
"""

def debug_problema_salvamento():
    """Debugar o problema de salvamento de subatividades"""
    from app import app, db
    from models import RDO, RDOServicoSubatividade, Obra
    
    with app.app_context():
        print("🔍 DIAGNÓSTICO DO PROBLEMA DE SALVAMENTO")
        print("=" * 50)
        
        # Buscar obra 40
        obra = Obra.query.get(40)
        if obra:
            print(f"✅ Obra encontrada: {obra.nome}")
        else:
            print("❌ Obra 40 não encontrada")
            return
        
        # Buscar último RDO da obra 40
        ultimo_rdo = RDO.query.filter_by(obra_id=40).order_by(RDO.id.desc()).first()
        if ultimo_rdo:
            print(f"✅ Último RDO: {ultimo_rdo.numero_rdo} (ID: {ultimo_rdo.id})")
            print(f"   Data: {ultimo_rdo.data_relatorio}")
            print(f"   Status: {ultimo_rdo.status}")
        else:
            print("❌ Nenhum RDO encontrado para obra 40")
            return
        
        # Buscar subatividades do último RDO
        subatividades = RDOServicoSubatividade.query.filter_by(rdo_id=ultimo_rdo.id).all()
        print(f"📊 Subatividades encontradas: {len(subatividades)}")
        
        for i, sub in enumerate(subatividades, 1):
            print(f"   {i}. {sub.nome_subatividade}: {sub.percentual_conclusao}%")
            if sub.observacoes_tecnicas:
                print(f"      Obs: {sub.observacoes_tecnicas}")
        
        # Verificar se existem registros com os dados mencionados pelo usuário
        montagem_pilares = RDOServicoSubatividade.query.filter(
            RDOServicoSubatividade.nome_subatividade.like('%Montagem de Pilares%'),
            RDOServicoSubatividade.rdo_id == ultimo_rdo.id
        ).first()
        
        if montagem_pilares:
            print(f"✅ Encontrado: {montagem_pilares.nome_subatividade} = {montagem_pilares.percentual_conclusao}%")
        else:
            print("❌ 'Montagem de Pilares' não encontrado no último RDO")
        
        # Buscar por qualquer subatividade com 100%
        cem_por_cento = RDOServicoSubatividade.query.filter(
            RDOServicoSubatividade.rdo_id == ultimo_rdo.id,
            RDOServicoSubatividade.percentual_conclusao == 100.0
        ).all()
        
        print(f"🎯 Subatividades com 100%: {len(cem_por_cento)}")
        for sub in cem_por_cento:
            print(f"   - {sub.nome_subatividade}")

def criar_teste_salvamento():
    """Criar um teste para validar salvamento de RDO"""
    print("\n🧪 CRIANDO TESTE DE SALVAMENTO")
    print("=" * 50)
    
    script_teste = '''
# Script de teste para salvamento RDO
import requests
import json

# Dados de teste (simulando os dados que o usuário preencheu)
dados_teste = {
    "obra_id": 40,
    "data_relatorio": "2025-08-30",
    "subatividades": [
        {
            "nome_subatividade": "Montagem de Pilares",
            "percentual_conclusao": 100,
            "servico_id": 58,
            "servico_nome": "Estrutura Metálica",
            "observacoes_tecnicas": "Teste manual usuario"
        },
        {
            "nome_subatividade": "Instalação de Vigas", 
            "percentual_conclusao": 100,
            "servico_id": 58,
            "servico_nome": "Estrutura Metálica",
            "observacoes_tecnicas": "Teste manual usuario"
        },
        {
            "nome_subatividade": "Soldagem de bases",
            "percentual_conclusao": 100,
            "servico_id": 59,
            "servico_nome": "Soldagem Especializada", 
            "observacoes_tecnicas": "Teste manual usuario"
        }
    ]
}

# Teste via API
response = requests.post(
    'http://localhost:5000/api/test/rdo/salvar-subatividades',
    json=dados_teste
)

print("Resultado:", response.json())
'''
    
    with open('teste_salvamento_rdo.py', 'w') as f:
        f.write(script_teste)
    
    print("✅ Script de teste criado: teste_salvamento_rdo.py")

def identificar_problema_api():
    """Identificar onde está o problema na API"""
    print("\n🔧 IDENTIFICANDO PROBLEMA NA API")
    print("=" * 50)
    
    print("❓ POSSÍVEIS CAUSAS:")
    print("1. API '/api/test/rdo/ultimo-rdo-dados' não busca corretamente")
    print("2. Filtros incorretos na query (percentual > 0)")
    print("3. Campo field_name não está sendo usado no frontend")
    print("4. Conflito entre salvamento manual e carregamento automático")
    print("5. Dados sendo sobrescritos ao clicar 'Testar Último RDO'")
    
    print("\n💡 SOLUÇÃO PROPOSTA:")
    print("1. Corrigir API para buscar dados salvos corretamente")
    print("2. Garantir que frontend preserva dados manuais")
    print("3. Adicionar logs detalhados para debug")
    print("4. Testar fluxo completo: salvar → carregar → verificar")

def main():
    print("🚨 CORREÇÃO URGENTE - PROBLEMA DE SALVAMENTO RDO")
    print("=" * 55)
    
    debug_problema_salvamento()
    identificar_problema_api()
    criar_teste_salvamento()
    
    print("\n🎯 PRÓXIMOS PASSOS:")
    print("1. Executar: python corrigir_salvamento_rdo.py")
    print("2. Verificar logs no console da aplicação")
    print("3. Testar: criar RDO → preencher → salvar → testar último RDO")
    print("4. Confirmar se dados persistem corretamente")

if __name__ == "__main__":
    main()