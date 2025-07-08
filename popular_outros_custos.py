"""
Script para popular dados de exemplo de outros custos para os funcionários
"""

from app import app, db
from models import OutroCusto, Funcionario, Obra
from datetime import date

def popular_outros_custos():
    """
    Cria dados de exemplo para outros custos dos funcionários
    """
    
    with app.app_context():
        # Verificar se já existem dados
        if OutroCusto.query.count() > 0:
            print("Dados de outros custos já existem!")
            return
        
        # Buscar funcionários e obras existentes
        cassio = Funcionario.query.filter_by(nome="Cássio Silva").first()
        pedro = Funcionario.query.filter_by(nome="Pedro Lima Sousa").first()
        obra1 = Obra.query.first()
        
        if not cassio or not pedro:
            print("Funcionários não encontrados!")
            return
        
        outros_custos = [
            # Vale transporte - Cássio
            OutroCusto(
                funcionario_id=cassio.id,
                data=date(2025, 6, 1),
                tipo='vale_transporte',
                categoria='adicional',
                valor=150.00,
                descricao='Vale transporte mensal junho/2025',
                obra_id=obra1.id if obra1 else None
            ),
            
            # Desconto VT 6% - Cássio
            OutroCusto(
                funcionario_id=cassio.id,
                data=date(2025, 6, 1),
                tipo='desconto_vt',
                categoria='desconto',
                valor=150.00,
                percentual=6.0,
                descricao='Desconto 6% vale transporte sobre salário',
                obra_id=obra1.id if obra1 else None
            ),
            
            # Vale alimentação - Cássio
            OutroCusto(
                funcionario_id=cassio.id,
                data=date(2025, 6, 15),
                tipo='vale_alimentacao',
                categoria='adicional',
                valor=300.00,
                descricao='Vale alimentação quinzenal',
                obra_id=obra1.id if obra1 else None
            ),
            
            # Vale transporte - Pedro
            OutroCusto(
                funcionario_id=pedro.id,
                data=date(2025, 6, 1),
                tipo='vale_transporte',
                categoria='adicional',
                valor=120.00,
                descricao='Vale transporte mensal junho/2025',
                obra_id=obra1.id if obra1 else None
            ),
            
            # Desconto VT 6% - Pedro
            OutroCusto(
                funcionario_id=pedro.id,
                data=date(2025, 6, 1),
                tipo='desconto_vt',
                categoria='desconto',
                valor=120.00,
                percentual=6.0,
                descricao='Desconto 6% vale transporte sobre salário',
                obra_id=obra1.id if obra1 else None
            ),
            
            # Outros descontos - Pedro
            OutroCusto(
                funcionario_id=pedro.id,
                data=date(2025, 6, 10),
                tipo='desconto_outras',
                categoria='desconto',
                valor=50.00,
                descricao='Desconto por dano em equipamento',
                obra_id=obra1.id if obra1 else None
            ),
        ]
        
        for custo in outros_custos:
            db.session.add(custo)
        
        db.session.commit()
        print(f"✅ {len(outros_custos)} registros de outros custos criados com sucesso!")
        
        # Exibir resumo
        print("\n📊 Resumo dos outros custos criados:")
        for funcionario in [cassio, pedro]:
            custos_func = OutroCusto.query.filter_by(funcionario_id=funcionario.id).all()
            print(f"\n{funcionario.nome}:")
            total_adicional = sum(c.valor for c in custos_func if c.categoria == 'adicional')
            total_desconto = sum(c.valor for c in custos_func if c.categoria == 'desconto')
            print(f"  - Adicionais: +R$ {total_adicional:.2f}")
            print(f"  - Descontos: -R$ {total_desconto:.2f}")
            print(f"  - Líquido: R$ {total_adicional - total_desconto:.2f}")

if __name__ == '__main__':
    popular_outros_custos()