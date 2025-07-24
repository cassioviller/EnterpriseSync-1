#!/usr/bin/env python3
"""
Script para popular categorias de serviços padrão no SIGE v8.0
Executa criação das categorias padrão para construção civil
"""

from app import app, db
from models import CategoriaServico, Usuario
from datetime import datetime

def popular_categorias_servicos():
    """Criar categorias padrão de serviços para construção civil"""
    
    with app.app_context():
        print("🏗️  Populando Categorias de Serviços - SIGE v8.0")
        print("=" * 50)
        
        # Buscar admin para associar as categorias (multi-tenant)
        admin = Usuario.query.filter_by(username='valeverde').first()
        if not admin:
            print("❌ Admin 'valeverde' não encontrado. Execute o script de criação de usuários primeiro.")
            return
        
        print(f"✅ Admin encontrado: {admin.username} (ID: {admin.id})")
        
        # Categorias padrão da construção civil
        categorias_padrao = [
            {
                'nome': 'Estrutura',
                'descricao': 'Serviços estruturais como fundações, pilares, vigas e lajes',
                'cor': '#dc3545',  # Vermelho
                'icone': 'fas fa-building',
                'ordem': 1
            },
            {
                'nome': 'Alvenaria',
                'descricao': 'Serviços de alvenaria de vedação e estrutural',
                'cor': '#fd7e14',  # Laranja
                'icone': 'fas fa-chess-board',
                'ordem': 2
            },
            {
                'nome': 'Cobertura',
                'descricao': 'Estrutura de telhado, telhas e impermeabilização de cobertura',
                'cor': '#20c997',  # Verde água
                'icone': 'fas fa-home',
                'ordem': 3
            },
            {
                'nome': 'Instalações',
                'descricao': 'Instalações elétricas, hidráulicas, gás e telecomunicações',
                'cor': '#0dcaf0',  # Azul claro
                'icone': 'fas fa-plug',
                'ordem': 4
            },
            {
                'nome': 'Acabamento',
                'descricao': 'Revestimentos, pinturas, pisos e acabamentos finais',
                'cor': '#6f42c1',  # Roxo
                'icone': 'fas fa-paint-brush',
                'ordem': 5
            },
            {
                'nome': 'Esquadrias',
                'descricao': 'Portas, janelas, portões e elementos de fechamento',
                'cor': '#6c757d',  # Cinza
                'icone': 'fas fa-door-open',
                'ordem': 6
            },
            {
                'nome': 'Fundação',
                'descricao': 'Escavação, sapatas, blocos e elementos de fundação',
                'cor': '#795548',  # Marrom
                'icone': 'fas fa-mountain',
                'ordem': 7
            },
            {
                'nome': 'Impermeabilização',
                'descricao': 'Serviços de impermeabilização e proteção contra umidade',
                'cor': '#607d8b',  # Azul acinzentado
                'icone': 'fas fa-tint',
                'ordem': 8
            },
            {
                'nome': 'Paisagismo',
                'descricao': 'Jardins, gramados e elementos paisagísticos',
                'cor': '#4caf50',  # Verde
                'icone': 'fas fa-seedling',
                'ordem': 9
            },
            {
                'nome': 'Infraestrutura',
                'descricao': 'Terraplenagem, drenagem e infraestrutura urbana',
                'cor': '#ff9800',  # Âmbar
                'icone': 'fas fa-road',
                'ordem': 10
            }
        ]
        
        categorias_criadas = 0
        categorias_existentes = 0
        
        for cat_data in categorias_padrao:
            # Verificar se categoria já existe para este admin
            categoria_existente = CategoriaServico.query.filter_by(
                nome=cat_data['nome'],
                admin_id=admin.id
            ).first()
            
            if categoria_existente:
                print(f"⚠️  Categoria '{cat_data['nome']}' já existe - pulando")
                categorias_existentes += 1
                continue
            
            # Criar nova categoria
            categoria = CategoriaServico(
                nome=cat_data['nome'],
                descricao=cat_data['descricao'],
                cor=cat_data['cor'],
                icone=cat_data['icone'],
                ordem=cat_data['ordem'],
                admin_id=admin.id,
                ativo=True
            )
            
            db.session.add(categoria)
            print(f"✅ Categoria criada: {cat_data['nome']} ({cat_data['cor']}) - {cat_data['icone']}")
            categorias_criadas += 1
        
        # Salvar no banco
        try:
            db.session.commit()
            print("\n" + "=" * 50)
            print(f"🎉 Categorias populadas com sucesso!")
            print(f"📊 Estatísticas:")
            print(f"   • Categorias criadas: {categorias_criadas}")
            print(f"   • Categorias já existiam: {categorias_existentes}")
            print(f"   • Total no sistema: {categorias_criadas + categorias_existentes}")
            print(f"   • Admin: {admin.username}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao salvar no banco: {str(e)}")
            return
        
        # Verificar criação
        total_categorias = CategoriaServico.query.filter_by(
            admin_id=admin.id,
            ativo=True
        ).count()
        
        print(f"\n✅ Verificação: {total_categorias} categorias ativas no banco")
        print("\n🔧 Agora você pode:")
        print("   1. Acessar a página de Serviços")
        print("   2. Clicar no botão '+' ao lado do campo Categoria")
        print("   3. Gerenciar suas categorias de serviços")
        print("\n🌟 Sistema pronto para uso!")

if __name__ == '__main__':
    popular_categorias_servicos()