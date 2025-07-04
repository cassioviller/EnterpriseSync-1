"""
Script para criar as tabelas de ocorrência no banco de dados
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import TipoOcorrencia, Ocorrencia
from datetime import datetime

def criar_tabelas_ocorrencia():
    """
    Cria as tabelas de ocorrência no banco de dados
    """
    print("Criando tabelas de ocorrência...")
    
    with app.app_context():
        # Criar as tabelas
        db.create_all()
        
        # Verificar se existem tipos de ocorrência
        tipos_existentes = TipoOcorrencia.query.count()
        
        if tipos_existentes == 0:
            print("Criando tipos de ocorrência padrão...")
            
            tipos_padrao = [
                {
                    'nome': 'Atestado Médico',
                    'descricao': 'Falta por motivo de saúde com atestado médico',
                    'requer_documento': True,
                    'afeta_custo': True
                },
                {
                    'nome': 'Atraso Justificado',
                    'descricao': 'Atraso com justificativa válida',
                    'requer_documento': False,
                    'afeta_custo': False
                },
                {
                    'nome': 'Falta Justificada',
                    'descricao': 'Falta com justificativa válida',
                    'requer_documento': False,
                    'afeta_custo': False
                },
                {
                    'nome': 'Licença Médica',
                    'descricao': 'Licença médica por período prolongado',
                    'requer_documento': True,
                    'afeta_custo': True
                },
                {
                    'nome': 'Licença Paternidade',
                    'descricao': 'Licença paternidade/maternidade',
                    'requer_documento': True,
                    'afeta_custo': False
                },
                {
                    'nome': 'Falta Injustificada',
                    'descricao': 'Falta sem justificativa',
                    'requer_documento': False,
                    'afeta_custo': True
                }
            ]
            
            for tipo_data in tipos_padrao:
                tipo = TipoOcorrencia(
                    nome=tipo_data['nome'],
                    descricao=tipo_data['descricao'],
                    requer_documento=tipo_data['requer_documento'],
                    afeta_custo=tipo_data['afeta_custo']
                )
                db.session.add(tipo)
            
            db.session.commit()
            print(f"Criados {len(tipos_padrao)} tipos de ocorrência")
        else:
            print(f"Já existem {tipos_existentes} tipos de ocorrência")
        
        print("Tabelas de ocorrência criadas com sucesso!")

if __name__ == '__main__':
    criar_tabelas_ocorrencia()