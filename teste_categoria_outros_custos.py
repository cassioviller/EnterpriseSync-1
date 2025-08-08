#!/usr/bin/env python3
"""
Script para testar a implementação do campo categoria em Outros Custos
"""

from app import app, db
from models import OutroCusto, Funcionario, Usuario
from datetime import date

def main():
    with app.app_context():
        print("🧪 Testando implementação do campo categoria em Outros Custos...")
        
        # 1. Verificar estrutura do modelo
        print("\n1. Verificando estrutura da tabela outro_custo...")
        columns = db.engine.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'outro_custo' 
            ORDER BY ordinal_position
        """).fetchall()
        
        for col in columns:
            print(f"   - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
        
        # 2. Verificar registros existentes
        print("\n2. Verificando registros existentes...")
        total_custos = OutroCusto.query.count()
        print(f"   Total de registros: {total_custos}")
        
        # Verificar distribuição por categoria
        if total_custos > 0:
            categorias = db.session.execute("""
                SELECT categoria, COUNT(*) as total 
                FROM outro_custo 
                GROUP BY categoria 
                ORDER BY total DESC
            """).fetchall()
            
            print("   Distribuição por categoria:")
            for cat in categorias:
                print(f"     - {cat[0] or 'NULL'}: {cat[1]} registros")
        
        # 3. Testar criação de novo registro
        print("\n3. Testando criação de novo registro...")
        funcionario = Funcionario.query.filter_by(ativo=True).first()
        admin = Usuario.query.filter_by(tipo_usuario='admin').first()
        
        if funcionario and admin:
            novo_custo = OutroCusto(
                funcionario_id=funcionario.id,
                data=date.today(),
                tipo="Teste de Categoria",
                categoria="alimentacao",
                valor=25.50,
                descricao="Teste do campo categoria",
                admin_id=admin.id
            )
            
            try:
                db.session.add(novo_custo)
                db.session.commit()
                print(f"   ✅ Registro criado com sucesso: ID {novo_custo.id}")
                print(f"   📊 Funcionário: {funcionario.nome}")
                print(f"   🏷️ Categoria: {novo_custo.categoria}")
                print(f"   💰 Valor: R$ {novo_custo.valor}")
                
                # Remover o registro de teste
                db.session.delete(novo_custo)
                db.session.commit()
                print("   🗑️ Registro de teste removido")
                
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Erro ao criar registro: {e}")
        else:
            print("   ⚠️ Funcionário ativo ou admin não encontrado para teste")
        
        # 4. Verificar campos obrigatórios
        print("\n4. Verificando validação do modelo...")
        try:
            # Teste com categoria válida
            campos_validos = {
                'funcionario_id': funcionario.id if funcionario else 1,
                'data': date.today(),
                'tipo': 'Teste',
                'categoria': 'transporte',
                'valor': 10.0,
                'admin_id': admin.id if admin else 1
            }
            
            custo_teste = OutroCusto(**campos_validos)
            print("   ✅ Modelo aceita categorias válidas: transporte")
            
        except Exception as e:
            print(f"   ❌ Erro na validação: {e}")
        
        print("\n🎉 Teste concluído!")
        print("\n📋 Categorias disponíveis:")
        print("   - outros_custos (padrão)")
        print("   - alimentacao")
        print("   - transporte")

if __name__ == "__main__":
    main()