#!/usr/bin/env python3
"""
CRIAR REGISTROS DE FÉRIAS
Adiciona registros do tipo 'ferias' para completar os 10 tipos
"""

from app import app, db
from models import *
from datetime import date, datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def criar_registros_ferias():
    """Cria registros de férias para funcionários específicos"""
    
    print("CRIANDO REGISTROS DE FÉRIAS")
    print("=" * 50)
    
    # Funcionários que terão férias
    funcionarios_ferias = [
        'Carlos Silva Vale Verde',
        'João Silva Santos',  # Primeiro da lista
        'Cássio Viller Silva de Azevedo'
    ]
    
    registros_criados = 0
    
    for nome_funcionario in funcionarios_ferias:
        funcionario = Funcionario.query.filter(
            Funcionario.nome.contains(nome_funcionario.split()[0])
        ).first()
        
        if not funcionario:
            print(f"❌ Funcionário não encontrado: {nome_funcionario}")
            continue
        
        print(f"Criando férias para: {funcionario.nome}")
        
        # Período de férias: 15-29 de julho
        data_inicio = date(2025, 7, 15)
        data_fim = date(2025, 7, 29)
        
        data_atual = data_inicio
        while data_atual <= data_fim:
            # Verificar se não existe registro
            registro_existente = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == funcionario.id,
                RegistroPonto.data == data_atual
            ).first()
            
            if registro_existente:
                # Atualizar para férias se for trabalho normal
                if registro_existente.tipo_registro == 'trabalho_normal':
                    registro_existente.tipo_registro = 'ferias'
                    registro_existente.horas_trabalhadas = 0
                    registro_existente.observacoes = f'Férias - período 15-29/07/2025 (convertido)'
                    registros_criados += 1
            else:
                # Criar novo registro
                registro_ferias = RegistroPonto(
                    funcionario_id=funcionario.id,
                    data=data_atual,
                    tipo_registro='ferias',
                    horas_trabalhadas=0,
                    observacoes=f'Férias - período 15-29/07/2025'
                )
                
                db.session.add(registro_ferias)
                registros_criados += 1
            
            data_atual += timedelta(days=1)
    
    db.session.commit()
    print(f"✅ Registros de férias criados/convertidos: {registros_criados}")
    
    return registros_criados

def validar_tipo_ferias():
    """Valida se o tipo férias está sendo usado"""
    
    count_ferias = db.session.query(RegistroPonto).filter_by(tipo_registro='ferias').count()
    print(f"\nRegistros do tipo 'ferias': {count_ferias}")
    
    if count_ferias > 0:
        # Mostrar alguns exemplos
        exemplos = db.session.query(RegistroPonto).filter_by(tipo_registro='ferias').limit(5).all()
        print("Exemplos:")
        for registro in exemplos:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            print(f"  • {funcionario.nome} - {registro.data} - {registro.observacoes}")
    
    return count_ferias > 0

if __name__ == "__main__":
    with app.app_context():
        print("ADICIONANDO TIPO FÉRIAS - COMPLETAR v8.1")
        print("=" * 60)
        
        # Criar registros de férias
        registros_criados = criar_registros_ferias()
        
        # Validar
        tipo_ok = validar_tipo_ferias()
        
        print(f"\n{'✅' if tipo_ok else '❌'} Tipo 'ferias' {'implementado' if tipo_ok else 'não encontrado'}")
        print(f"Total de registros criados: {registros_criados}")