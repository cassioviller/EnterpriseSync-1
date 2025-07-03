#!/usr/bin/env python3
"""
Script para popular campos vazios de restaurante e obra nos registros de alimentação existentes.
Este script vai atribuir restaurantes e obras aleatoriamente aos registros que estão com esses campos vazios.
"""

import random
from datetime import datetime
from app import app, db
from models import RegistroAlimentacao, Restaurante, Obra, CustoObra

def popular_campos_alimentacao():
    """Popula campos vazios de restaurante e obra nos registros de alimentação"""
    
    with app.app_context():
        print("🍽️ Iniciando população de campos de alimentação...")
        
        # Buscar todos os restaurantes ativos
        restaurantes = Restaurante.query.filter_by(ativo=True).all()
        if not restaurantes:
            print("❌ Nenhum restaurante encontrado!")
            return
        
        # Buscar todas as obras em andamento
        obras = Obra.query.filter_by(status='Em andamento').all()
        if not obras:
            print("❌ Nenhuma obra em andamento encontrada!")
            return
        
        # Buscar registros de alimentação sem restaurante ou obra
        registros_sem_restaurante = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.restaurante_id.is_(None)
        ).all()
        
        registros_sem_obra = RegistroAlimentacao.query.filter(
            RegistroAlimentacao.obra_id.is_(None)
        ).all()
        
        print(f"📊 Encontrados:")
        print(f"   - {len(registros_sem_restaurante)} registros sem restaurante")
        print(f"   - {len(registros_sem_obra)} registros sem obra")
        print(f"   - {len(restaurantes)} restaurantes disponíveis")
        print(f"   - {len(obras)} obras em andamento")
        
        # Atualizar registros sem restaurante
        if registros_sem_restaurante:
            print("\n🏪 Atribuindo restaurantes aos registros...")
            for registro in registros_sem_restaurante:
                # Atribuir restaurante aleatório
                restaurante = random.choice(restaurantes)
                registro.restaurante_id = restaurante.id
                print(f"   ✓ Registro {registro.id} → {restaurante.nome}")
        
        # Atualizar registros sem obra (70% dos registros terão obra)
        if registros_sem_obra:
            print("\n🏗️ Atribuindo obras aos registros...")
            for registro in registros_sem_obra:
                # 70% de chance de ter obra
                if random.random() < 0.7:
                    obra = random.choice(obras)
                    registro.obra_id = obra.id
                    print(f"   ✓ Registro {registro.id} → {obra.nome}")
                else:
                    print(f"   - Registro {registro.id} → Sem obra")
        
        # Salvar alterações
        try:
            db.session.commit()
            print("\n✅ Campos atualizados com sucesso!")
            
            # Agora criar registros de custo para obras
            print("\n💰 Criando registros de custo para obras...")
            
            # Buscar registros de alimentação com obra
            registros_com_obra = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.obra_id.isnot(None)
            ).all()
            
            custos_criados = 0
            for registro in registros_com_obra:
                # Verificar se já existe custo para este registro
                custo_existente = CustoObra.query.filter_by(
                    obra_id=registro.obra_id,
                    tipo='alimentacao',
                    data=registro.data,
                    valor=registro.valor
                ).first()
                
                if not custo_existente:
                    # Criar registro de custo
                    custo = CustoObra(
                        obra_id=registro.obra_id,
                        tipo='alimentacao',
                        descricao=f'Alimentação - {registro.tipo} - {registro.funcionario_ref.nome}',
                        valor=registro.valor,
                        data=registro.data
                    )
                    db.session.add(custo)
                    custos_criados += 1
            
            db.session.commit()
            print(f"✅ {custos_criados} registros de custo criados!")
            
            # Estatísticas finais
            print("\n📈 Estatísticas finais:")
            total_registros = RegistroAlimentacao.query.count()
            com_restaurante = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.restaurante_id.isnot(None)
            ).count()
            com_obra = RegistroAlimentacao.query.filter(
                RegistroAlimentacao.obra_id.isnot(None)
            ).count()
            
            print(f"   - Total de registros: {total_registros}")
            print(f"   - Com restaurante: {com_restaurante} ({com_restaurante/total_registros*100:.1f}%)")
            print(f"   - Com obra: {com_obra} ({com_obra/total_registros*100:.1f}%)")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao salvar: {e}")

if __name__ == '__main__':
    popular_campos_alimentacao()