#!/usr/bin/env python3
"""
Correção dos tipos de lançamento de ponto no sistema
Atualiza interface e lógica para usar tipos padronizados
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date

def atualizar_tipos_registro():
    """Atualiza tipos de registro existentes para padronização"""
    with app.app_context():
        print("🔧 ATUALIZANDO TIPOS DE REGISTRO NO BANCO...")
        
        # Mapeamento de tipos antigos para novos
        mapeamento_tipos = {
            'trabalho_normal': 'trabalhado',
            'sabado_horas_extras': 'sabado_trabalhado',
            'domingo_horas_extras': 'domingo_trabalhado',
            'feriado_horas_extras': 'feriado_trabalhado',
            'falta_injustificada': 'falta',
            'falta_nao_justificada': 'falta',
        }
        
        atualizacoes = 0
        registros = RegistroPonto.query.all()
        
        for registro in registros:
            tipo_atual = registro.tipo_registro
            if tipo_atual in mapeamento_tipos:
                novo_tipo = mapeamento_tipos[tipo_atual]
                registro.tipo_registro = novo_tipo
                atualizacoes += 1
                print(f"  • Atualizado: {tipo_atual} → {novo_tipo}")
        
        db.session.commit()
        print(f"✅ {atualizacoes} registros atualizados")

def gerar_relatorio_tipos_utilizados():
    """Gera relatório dos tipos de registro utilizados"""
    with app.app_context():
        print("\n📊 TIPOS DE REGISTRO UTILIZADOS NO SISTEMA:")
        
        from sqlalchemy import func
        
        tipos_query = db.session.query(
            RegistroPonto.tipo_registro,
            func.count(RegistroPonto.id).label('total')
        ).group_by(RegistroPonto.tipo_registro).order_by(func.count(RegistroPonto.id).desc())
        
        for tipo, total in tipos_query:
            print(f"  • {tipo or 'NULL'}: {total} registros")

if __name__ == "__main__":
    atualizar_tipos_registro()
    gerar_relatorio_tipos_utilizados()