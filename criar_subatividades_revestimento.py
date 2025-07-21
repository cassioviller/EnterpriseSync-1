#!/usr/bin/env python3
"""
Script para criar subatividades detalhadas do serviço Revestimento Cerâmico
"""

from app import app, db
from models import Servico, SubAtividade

def criar_subatividades_revestimento():
    with app.app_context():
        print("Criando subatividades para Revestimento Cerâmico...")
        
        # Buscar serviço de revestimento cerâmico
        servico = Servico.query.filter_by(nome="Revestimento Cerâmico").first()
        
        if not servico:
            print("❌ Serviço 'Revestimento Cerâmico' não encontrado!")
            return
        
        print(f"✓ Serviço encontrado: {servico.nome}")
        
        # Limpar subatividades existentes
        SubAtividade.query.filter_by(servico_id=servico.id).delete()
        
        # Definir subatividades
        subatividades = [
            {
                'nome': 'Preparação da Base',
                'descricao': 'Limpeza e preparação da superfície para aplicação do revestimento',
                'ordem_execucao': 1,
                'ferramentas_necessarias': 'Vassoura, escova, mangueira, esponja',
                'materiais_principais': 'Água, detergente, lixa',
                'qualificacao_minima': 'ajudante',
                'pode_executar_paralelo': False
            },
            {
                'nome': 'Aplicação de Chapisco',
                'descricao': 'Aplicação de chapisco para melhor aderência',
                'ordem_execucao': 2,
                'ferramentas_necessarias': 'Colher de pedreiro, desempenadeira',
                'materiais_principais': 'Cimento, areia, água',
                'qualificacao_minima': 'meio_oficial',
                'pode_executar_paralelo': False
            },
            {
                'nome': 'Aplicação de Emboço',
                'descricao': 'Aplicação de emboço nivelado',
                'ordem_execucao': 3,
                'ferramentas_necessarias': 'Desempenadeira, régua, nível',
                'materiais_principais': 'Argamassa de emboço',
                'qualificacao_minima': 'oficial',
                'pode_executar_paralelo': True
            },
            {
                'nome': 'Aplicação de Argamassa Colante',
                'descricao': 'Aplicação de argamassa colante com desempenadeira dentada',
                'ordem_execucao': 4,
                'ferramentas_necessarias': 'Desempenadeira dentada, balde',
                'materiais_principais': 'Argamassa colante AC-I ou AC-II',
                'qualificacao_minima': 'oficial',
                'pode_executar_paralelo': True
            },
            {
                'nome': 'Assentamento das Cerâmicas',
                'descricao': 'Assentamento das peças cerâmicas com espaçadores',
                'ordem_execucao': 5,
                'ferramentas_necessarias': 'Cortador cerâmico, martelo de borracha, espaçadores',
                'materiais_principais': 'Cerâmica, espaçadores plásticos',
                'qualificacao_minima': 'oficial',
                'pode_executar_paralelo': True
            },
            {
                'nome': 'Rejuntamento',
                'descricao': 'Aplicação de rejunte entre as peças cerâmicas',
                'ordem_execucao': 6,
                'ferramentas_necessarias': 'Desempenadeira de borracha, esponja',
                'materiais_principais': 'Rejunte, água',
                'qualificacao_minima': 'meio_oficial',
                'pode_executar_paralelo': True
            },
            {
                'nome': 'Limpeza Final',
                'descricao': 'Limpeza final e acabamento do revestimento',
                'ordem_execucao': 7,
                'ferramentas_necessarias': 'Panos, esponjas, balde',
                'materiais_principais': 'Água, detergente neutro',
                'qualificacao_minima': 'ajudante',
                'pode_executar_paralelo': False
            }
        ]
        
        # Criar subatividades
        for sub_data in subatividades:
            subatividade = SubAtividade(
                servico_id=servico.id,
                nome=sub_data['nome'],
                descricao=sub_data['descricao'],
                ordem_execucao=sub_data['ordem_execucao'],
                ferramentas_necessarias=sub_data['ferramentas_necessarias'],
                materiais_principais=sub_data['materiais_principais'],
                qualificacao_minima=sub_data['qualificacao_minima'],
                pode_executar_paralelo=sub_data['pode_executar_paralelo'],
                requer_aprovacao=sub_data['ordem_execucao'] in [3, 5],  # Emboço e assentamento precisam aprovação
                ativo=True
            )
            db.session.add(subatividade)
            print(f"  ✓ {sub_data['ordem_execucao']}. {sub_data['nome']}")
        
        # Salvar no banco
        db.session.commit()
        print(f"\n✅ {len(subatividades)} subatividades criadas para {servico.nome}")
        
        # Verificar resultado
        total_subatividades = SubAtividade.query.filter_by(servico_id=servico.id, ativo=True).count()
        print(f"📊 Total de subatividades ativas: {total_subatividades}")

if __name__ == '__main__':
    criar_subatividades_revestimento()