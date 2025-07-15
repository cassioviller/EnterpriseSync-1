#!/usr/bin/env python3
"""
Script para migrar tabela HorarioTrabalho adicionando campos horas_diarias e valor_hora
"""

from app import app, db
from models import HorarioTrabalho
from datetime import datetime, time

def migrar_horarios_trabalho():
    """
    Adiciona campos horas_diarias e valor_hora à tabela HorarioTrabalho
    """
    with app.app_context():
        try:
            # Verificar se as colunas já existem
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('horario_trabalho')]
            
            # Adicionar colunas se não existirem
            if 'horas_diarias' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE horario_trabalho ADD COLUMN horas_diarias FLOAT DEFAULT 8.0'))
                    conn.commit()
                print("✓ Coluna horas_diarias adicionada")
            
            if 'valor_hora' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE horario_trabalho ADD COLUMN valor_hora FLOAT DEFAULT 12.0'))
                    conn.commit()
                print("✓ Coluna valor_hora adicionada")
            
            # Atualizar registros existentes calculando horas_diarias
            horarios = HorarioTrabalho.query.all()
            for horario in horarios:
                if horario.horas_diarias is None or horario.horas_diarias == 0:
                    # Calcular horas trabalhadas
                    entrada = datetime.combine(datetime.today(), horario.entrada)
                    saida_almoco = datetime.combine(datetime.today(), horario.saida_almoco)
                    retorno_almoco = datetime.combine(datetime.today(), horario.retorno_almoco)
                    saida = datetime.combine(datetime.today(), horario.saida)
                    
                    # Calcular horas (manhã + tarde)
                    horas_manha = (saida_almoco - entrada).total_seconds() / 3600
                    horas_tarde = (saida - retorno_almoco).total_seconds() / 3600
                    horas_diarias = horas_manha + horas_tarde
                    
                    # Atualizar registro
                    horario.horas_diarias = horas_diarias
                    horario.valor_hora = 12.0  # Valor padrão
                    
                    print(f"✓ Atualizado {horario.nome}: {horas_diarias:.1f}h/dia")
            
            db.session.commit()
            print(f"✓ Migração concluída com sucesso! {len(horarios)} registros atualizados.")
            
        except Exception as e:
            print(f"✗ Erro na migração: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    migrar_horarios_trabalho()