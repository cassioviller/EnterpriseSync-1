
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
