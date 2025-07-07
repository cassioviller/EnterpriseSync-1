"""
Script para popular dados financeiros de demonstração
Sistema Integrado de Gestão Empresarial - Estruturas do Vale
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import *
from datetime import date, datetime, timedelta
import random

def criar_centros_custo():
    """Criar centros de custo de demonstração"""
    centros = [
        {
            'codigo': 'CC001',
            'nome': 'Obra Residencial Alpha',
            'tipo': 'obra',
            'descricao': 'Centro de custo para obra residencial Alpha'
        },
        {
            'codigo': 'CC002',
            'nome': 'Departamento Engenharia',
            'tipo': 'departamento',
            'descricao': 'Custos do departamento de engenharia'
        },
        {
            'codigo': 'CC003',
            'nome': 'Projeto Infraestrutura',
            'tipo': 'projeto',
            'descricao': 'Projeto de infraestrutura urbana'
        },
        {
            'codigo': 'CC004',
            'nome': 'Atividade Fundação',
            'tipo': 'atividade',
            'descricao': 'Custos relacionados a atividades de fundação'
        },
        {
            'codigo': 'CC005',
            'nome': 'Obra Comercial Beta',
            'tipo': 'obra',
            'descricao': 'Centro de custo para obra comercial Beta'
        }
    ]
    
    for centro_data in centros:
        centro = CentroCusto.query.filter_by(codigo=centro_data['codigo']).first()
        if not centro:
            centro = CentroCusto(**centro_data)
            db.session.add(centro)
    
    print("Centros de custo criados!")

def criar_receitas():
    """Criar receitas de demonstração"""
    hoje = date.today()
    
    receitas = [
        {
            'numero_receita': 'REC001',
            'origem': 'obra',
            'descricao': 'Primeira parcela Obra Alpha',
            'valor': 45000.00,
            'data_receita': hoje - timedelta(days=30),
            'data_recebimento': hoje - timedelta(days=25),
            'status': 'Recebido',
            'forma_recebimento': 'Transferência'
        },
        {
            'numero_receita': 'REC002',
            'origem': 'obra',
            'descricao': 'Segunda parcela Obra Alpha',
            'valor': 45000.00,
            'data_receita': hoje - timedelta(days=15),
            'status': 'Pendente'
        },
        {
            'numero_receita': 'REC003',
            'origem': 'obra',
            'descricao': 'Pagamento inicial Obra Beta',
            'valor': 25000.00,
            'data_receita': hoje - timedelta(days=20),
            'data_recebimento': hoje - timedelta(days=18),
            'status': 'Recebido',
            'forma_recebimento': 'PIX'
        },
        {
            'numero_receita': 'REC004',
            'origem': 'servico',
            'descricao': 'Consultoria em engenharia estrutural',
            'valor': 8000.00,
            'data_receita': hoje - timedelta(days=10),
            'data_recebimento': hoje - timedelta(days=5),
            'status': 'Recebido',
            'forma_recebimento': 'Transferência'
        },
        {
            'numero_receita': 'REC005',
            'origem': 'obra',
            'descricao': 'Terceira parcela Obra Alpha',
            'valor': 45000.00,
            'data_receita': hoje + timedelta(days=15),
            'status': 'Pendente'
        }
    ]
    
    for receita_data in receitas:
        receita = Receita.query.filter_by(numero_receita=receita_data['numero_receita']).first()
        if not receita:
            receita = Receita(**receita_data)
            db.session.add(receita)
    
    print("Receitas criadas!")

def criar_orcamentos_obra():
    """Criar orçamentos vs. realizado para obras"""
    orcamentos = [
        # Exemplo de orçamentos genéricos
        {
            'categoria': 'mao_obra',
            'orcamento_planejado': 50000.00,
            'receita_planejada': 135000.00  # Total esperado
        },
        {
            'categoria': 'material',
            'orcamento_planejado': 30000.00
        },
        {
            'categoria': 'equipamento',
            'orcamento_planejado': 15000.00
        },
        {
            'categoria': 'alimentacao',
            'orcamento_planejado': 8000.00
        }
    ]
    
    for orc_data in orcamentos:
        orcamento = OrcamentoObra.query.filter_by(
            categoria=orc_data['categoria']
        ).first()
        if not orcamento:
            orcamento = OrcamentoObra(**orc_data)
            db.session.add(orcamento)
    
    print("Orçamentos criados!")

def sincronizar_fluxo_caixa():
    """Sincronizar fluxo de caixa com dados existentes"""
    from financeiro import sincronizar_fluxo_caixa
    try:
        sincronizar_fluxo_caixa()
        print("Fluxo de caixa sincronizado!")
    except Exception as e:
        print(f"Erro ao sincronizar fluxo de caixa: {e}")

def main():
    """Executar todas as funções de seed"""
    with app.app_context():
        try:
            # Criar estruturas básicas
            db.create_all()
            
            # Popular dados financeiros
            criar_centros_custo()
            criar_receitas()
            criar_orcamentos_obra()
            
            # Commit das mudanças
            db.session.commit()
            
            # Sincronizar fluxo de caixa
            sincronizar_fluxo_caixa()
            
            print("\n✅ Dados financeiros de demonstração criados com sucesso!")
            print("\nDados criados:")
            print("- 5 Centros de custo")
            print("- 5 Receitas (3 recebidas, 2 pendentes)")
            print("- Orçamentos para 2 obras")
            print("- Fluxo de caixa sincronizado")
            
            # Estatísticas
            print(f"\nEstatísticas:")
            print(f"- Centros de custo: {CentroCusto.query.count()}")
            print(f"- Receitas: {Receita.query.count()}")
            print(f"- Orçamentos: {OrcamentoObra.query.count()}")
            print(f"- Movimentos fluxo de caixa: {FluxoCaixa.query.count()}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar dados: {e}")

if __name__ == "__main__":
    main()