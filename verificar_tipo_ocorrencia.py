#!/usr/bin/env python3
"""
Script para verificar e criar tipos de ocorrência no banco de dados
"""

from app import app, db
from models import TipoOcorrencia

def verificar_e_criar_tipos():
    """Verifica se os tipos de ocorrência existem e cria se necessário"""
    
    tipos_necessarios = [
        {'nome': 'Atestado Médico', 'descricao': 'Falta justificada por atestado médico'},
        {'nome': 'Falta Justificada', 'descricao': 'Falta justificada por motivo válido'},
        {'nome': 'Licença Médica', 'descricao': 'Licença médica prolongada'},
        {'nome': 'Falta Injustificada', 'descricao': 'Falta sem justificativa'},
        {'nome': 'Atraso', 'descricao': 'Chegada após horário de trabalho'},
        {'nome': 'Saída Antecipada', 'descricao': 'Saída antes do horário previsto'},
        {'nome': 'Férias', 'descricao': 'Período de férias'},
        {'nome': 'Licença Paternidade', 'descricao': 'Licença paternidade'},
        {'nome': 'Licença Maternidade', 'descricao': 'Licença maternidade'},
        {'nome': 'Outros', 'descricao': 'Outros tipos de ocorrência'}
    ]
    
    print("Verificando tipos de ocorrência...")
    
    for tipo_info in tipos_necessarios:
        tipo_existente = TipoOcorrencia.query.filter_by(nome=tipo_info['nome']).first()
        
        if not tipo_existente:
            novo_tipo = TipoOcorrencia(
                nome=tipo_info['nome'],
                descricao=tipo_info['descricao']
            )
            db.session.add(novo_tipo)
            print(f"✓ Criado tipo: {tipo_info['nome']}")
        else:
            print(f"• Tipo já existe: {tipo_info['nome']}")
    
    try:
        db.session.commit()
        print("\nTodos os tipos de ocorrência foram verificados e criados com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar tipos: {e}")

if __name__ == '__main__':
    with app.app_context():
        verificar_e_criar_tipos()