#!/usr/bin/env python3
"""
Script para criar horários de trabalho básicos
"""

from app import app, db
from models import HorarioTrabalho
from datetime import time

def create_horarios():
    with app.app_context():
        # Limpar horários existentes
        HorarioTrabalho.query.delete()
        
        # Criar horários de trabalho
        horarios = [
            HorarioTrabalho(
                nome='Comercial - Segunda a Sexta',
                entrada=time(8, 0),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                dias_semana='1,2,3,4,5'
            ),
            HorarioTrabalho(
                nome='Obra - Segunda a Sábado',
                entrada=time(7, 0),
                saida_almoco=time(11, 30),
                retorno_almoco=time(12, 30),
                saida=time(16, 0),
                dias_semana='1,2,3,4,5,6'
            ),
            HorarioTrabalho(
                nome='Noturno - Segunda a Sexta',
                entrada=time(22, 0),
                saida_almoco=time(2, 0),
                retorno_almoco=time(3, 0),
                saida=time(6, 0),
                dias_semana='1,2,3,4,5'
            )
        ]
        
        for horario in horarios:
            db.session.add(horario)
        
        db.session.commit()
        print("Horários de trabalho criados com sucesso!")

if __name__ == '__main__':
    create_horarios()