#!/usr/bin/env python3
"""
Script para cadastrar serviços na obra do usuário teste5
"""

from app import app, db
from models import Obra, Servico
from sqlalchemy import text
from datetime import datetime

def cadastrar_servicos():
    """Cadastrar serviços na obra Casa Família Silva"""
    with app.app_context():
        # Buscar obra do usuário teste5
        obra = Obra.query.filter_by(admin_id=50, nome='Casa Família Silva').first()
        servicos = Servico.query.filter_by(admin_id=50).all()
        
        if not obra:
            print("❌ Obra não encontrada")
            return False
            
        print(f"✅ Obra encontrada: {obra.nome} (ID: {obra.id})")
        print(f"✅ Serviços encontrados: {len(servicos)}")
        
        # Atualizar campo serviços_ids na obra
        servicos_ids = [str(s.id) for s in servicos]
        obra.servicos_ids = ','.join(servicos_ids)
        
        try:
            db.session.commit()
            print(f"✅ Serviços cadastrados na obra: {servicos_ids}")
            
            # Criar alguns RDOs de exemplo
            for i, servico in enumerate(servicos):
                rdo_sql = f"""
                INSERT INTO rdo (obra_id, funcionario_id, data, servico_realizado, observacoes, admin_id, created_at, status) 
                VALUES ({obra.id}, 51, '2025-09-0{i+1}', '{servico.nome}', 'RDO automático para teste', 50, NOW(), 'aprovado')
                """
                db.session.execute(text(rdo_sql))
                print(f"✅ RDO criado para serviço: {servico.nome}")
                
            db.session.commit()
            return True
            
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    cadastrar_servicos()