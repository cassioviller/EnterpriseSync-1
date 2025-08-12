from app import app, db
from models_propostas import Proposta, PropostaItem, PropostaArquivo, PropostaTemplate
from models import Usuario
from datetime import datetime, date, timedelta

def criar_templates_padrao():
    """Cria templates padrão para as propostas"""
    templates = [
        {
            'nome': 'MEZANINO',
            'descricao': 'Template para estruturas de mezanino',
            'itens_padrao': [
                {
                    'descricao': 'Fornecimento de ART (Atestado de Responsabilidade Técnica)',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 1000.00
                },
                {
                    'descricao': 'Perfis Metálicos para estrutura do mezanino',
                    'quantidade': 500,
                    'unidade': 'kg',
                    'preco_unitario': 14.00
                },
                {
                    'descricao': 'Mão de obra para fabricação e montagem das estruturas',
                    'quantidade': 500,
                    'unidade': 'kg',
                    'preco_unitario': 14.00
                },
                {
                    'descricao': 'Fornecimento de placa NTF INFIBRA 25mm',
                    'quantidade': 20,
                    'unidade': 'uni',
                    'preco_unitario': 450.00
                },
                {
                    'descricao': 'Mão de obra para montagem das placas NTF',
                    'quantidade': 20,
                    'unidade': 'uni',
                    'preco_unitario': 140.00
                }
            ]
        },
        {
            'nome': 'ESTRUTURA METÁLICA - VIGA W',
            'descricao': 'Template para estruturas com vigas W',
            'itens_padrao': [
                {
                    'descricao': 'ART (Atestado de responsabilidade técnica)',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 1200.00
                },
                {
                    'descricao': 'Içamento das estruturas',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 3250.00
                },
                {
                    'descricao': 'Fornecimento de perfis metálicos e montagem da estrutura',
                    'quantidade': 800,
                    'unidade': 'kg',
                    'preco_unitario': 37.00
                },
                {
                    'descricao': 'Fornecimento de telha termo acústica trapézio 40/980',
                    'quantidade': 150,
                    'unidade': 'm²',
                    'preco_unitario': 190.00
                },
                {
                    'descricao': 'Mão de obra para fabricação e montagem das telhas',
                    'quantidade': 150,
                    'unidade': 'm²',
                    'preco_unitario': 45.00
                },
                {
                    'descricao': 'Fornecimento de calhas e rufos metálicos',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 4381.00
                },
                {
                    'descricao': 'Fornecimento de platibanda metálica',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 5555.00
                }
            ]
        },
        {
            'nome': 'COBERTURA ÁREA GOURMET',
            'descricao': 'Template para coberturas de áreas gourmet',
            'itens_padrao': [
                {
                    'descricao': 'ART (Atestado de responsabilidade técnica)',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 1200.00
                },
                {
                    'descricao': 'Içamento das estruturas',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 3250.00
                },
                {
                    'descricao': 'Fornecimento de perfis metálicos e montagem da estrutura',
                    'quantidade': 300,
                    'unidade': 'kg',
                    'preco_unitario': 37.00
                },
                {
                    'descricao': 'Fornecimento de telha termo acústica trapézio 40/980',
                    'quantidade': 80,
                    'unidade': 'm²',
                    'preco_unitario': 190.00
                },
                {
                    'descricao': 'Mão de obra para fabricação e montagem das telhas',
                    'quantidade': 80,
                    'unidade': 'm²',
                    'preco_unitario': 45.00
                },
                {
                    'descricao': 'Fornecimento de calhas e rufos metálicos',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 2800.00
                }
            ]
        }
    ]
    
    for template_data in templates:
        # Verificar se já existe
        existing = PropostaTemplate.query.filter_by(nome=template_data['nome']).first()
        if existing:
            print(f"Template '{template_data['nome']}' já existe, pulando...")
            continue
        
        template = PropostaTemplate()
        template.nome = template_data['nome']
        template.descricao = template_data['descricao']
        template.itens_padrao = template_data['itens_padrao']
        template.ativo = True
        
        db.session.add(template)
        print(f"✅ Template '{template_data['nome']}' criado")
    
    db.session.commit()

def criar_propostas_exemplo():
    """Cria algumas propostas de exemplo"""
    
    # Buscar usuário admin
    admin = Usuario.query.filter_by(email='admin@sige.com').first()
    if not admin:
        print("❌ Usuário admin não encontrado")
        return
    
    propostas_exemplo = [
        {
            'cliente_nome': 'João Silva Construções',
            'cliente_telefone': '(35) 99999-1234',
            'cliente_email': 'joao@construcoes.com',
            'cliente_endereco': 'Rua das Obras, 123 - Centro - Varginha/MG',
            'assunto': 'Fabricação e montagem de mezanino industrial',
            'objeto': '''Fornecimento e montagem de estrutura metálica para mezanino industrial com as seguintes especificações:
- Área total: 100m²
- Capacidade: 300kg/m²
- Altura: 4,50m
- Piso em chapa xadrez
- Guarda-corpo e escada de acesso inclusos''',
            'documentos_referencia': 'Plantas baixas fornecidas pelo cliente em 15/01/2025',
            'prazo_entrega_dias': 45,
            'observacoes_entrega': 'Início após aprovação do projeto estrutural pelo cliente',
            'validade_dias': 15,
            'status': 'enviada',
            'itens': [
                {
                    'descricao': 'Fornecimento de ART (Atestado de Responsabilidade Técnica)',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 1000.00
                },
                {
                    'descricao': 'Perfis Metálicos para estrutura do mezanino',
                    'quantidade': 600,
                    'unidade': 'kg',
                    'preco_unitario': 15.50
                },
                {
                    'descricao': 'Mão de obra para fabricação e montagem',
                    'quantidade': 600,
                    'unidade': 'kg',
                    'preco_unitario': 16.00
                },
                {
                    'descricao': 'Fornecimento e instalação de piso em chapa xadrez',
                    'quantidade': 100,
                    'unidade': 'm²',
                    'preco_unitario': 85.00
                },
                {
                    'descricao': 'Guarda-corpo e escada de acesso',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 3200.00
                }
            ]
        },
        {
            'cliente_nome': 'Maria Santos Empreendimentos',
            'cliente_telefone': '(35) 98888-5678',
            'cliente_email': 'maria@empreendimentos.com',
            'cliente_endereco': 'Av. Industrial, 456 - Distrito Industrial - Pouso Alegre/MG',
            'assunto': 'Cobertura metálica para área de eventos',
            'objeto': '''Execução de cobertura metálica para área de eventos com as seguintes características:
- Área: 200m²
- Vão livre de 15m
- Pé-direito de 4,5m
- Telha termoacústica
- Sistema de captação de águas pluviais''',
            'documentos_referencia': 'Projeto arquitetônico e levantamento topográfico',
            'prazo_entrega_dias': 60,
            'observacoes_entrega': 'Execução programada para período seco (maio a setembro)',
            'validade_dias': 10,
            'status': 'rascunho',
            'itens': [
                {
                    'descricao': 'ART (Atestado de responsabilidade técnica)',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 1200.00
                },
                {
                    'descricao': 'Içamento das estruturas',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 4500.00
                },
                {
                    'descricao': 'Fornecimento de perfis metálicos e montagem',
                    'quantidade': 1200,
                    'unidade': 'kg',
                    'preco_unitario': 38.50
                },
                {
                    'descricao': 'Fornecimento de telha termoacústica',
                    'quantidade': 210,
                    'unidade': 'm²',
                    'preco_unitario': 195.00
                },
                {
                    'descricao': 'Mão de obra para montagem das telhas',
                    'quantidade': 210,
                    'unidade': 'm²',
                    'preco_unitario': 48.00
                },
                {
                    'descricao': 'Sistema de calhas e condutores',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 5800.00
                }
            ]
        },
        {
            'cliente_nome': 'Indústria Vale do Aço Ltda',
            'cliente_telefone': '(35) 97777-9999',
            'cliente_email': 'projetos@valedoaco.com.br',
            'cliente_endereco': 'Rod. Fernão Dias, km 45 - Itajubá/MG',
            'assunto': 'Ampliação de galpão industrial',
            'objeto': '''Ampliação de galpão industrial existente com:
- Área adicional: 500m²
- Estrutura metálica em perfis laminados
- Cobertura em telha metálica
- Fechamentos laterais
- Integração com estrutura existente''',
            'documentos_referencia': 'Projeto estrutural da edificação existente e plantas de ampliação',
            'prazo_entrega_dias': 90,
            'observacoes_entrega': 'Execução em etapas para não interromper atividades da indústria',
            'validade_dias': 20,
            'status': 'aprovada',
            'data_resposta_cliente': datetime.now() - timedelta(days=5),
            'observacoes_cliente': 'Proposta aprovada. Aguardamos cronograma detalhado.',
            'itens': [
                {
                    'descricao': 'ART e projetos complementares',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 2500.00
                },
                {
                    'descricao': 'Estrutura metálica principal',
                    'quantidade': 2500,
                    'unidade': 'kg',
                    'preco_unitario': 42.00
                },
                {
                    'descricao': 'Mão de obra especializada',
                    'quantidade': 2500,
                    'unidade': 'kg',
                    'preco_unitario': 25.00
                },
                {
                    'descricao': 'Cobertura em telha metálica',
                    'quantidade': 520,
                    'unidade': 'm²',
                    'preco_unitario': 145.00
                },
                {
                    'descricao': 'Fechamentos laterais',
                    'quantidade': 300,
                    'unidade': 'm²',
                    'preco_unitario': 125.00
                },
                {
                    'descricao': 'Sistema de drenagem completo',
                    'quantidade': 1,
                    'unidade': 'vb',
                    'preco_unitario': 8500.00
                }
            ]
        }
    ]
    
    for prop_data in propostas_exemplo:
        # Criar proposta
        proposta = Proposta()
        proposta.cliente_nome = prop_data['cliente_nome']
        proposta.cliente_telefone = prop_data['cliente_telefone']
        proposta.cliente_email = prop_data['cliente_email']
        proposta.cliente_endereco = prop_data['cliente_endereco']
        proposta.assunto = prop_data['assunto']
        proposta.objeto = prop_data['objeto']
        proposta.documentos_referencia = prop_data['documentos_referencia']
        proposta.prazo_entrega_dias = prop_data['prazo_entrega_dias']
        proposta.observacoes_entrega = prop_data['observacoes_entrega']
        proposta.validade_dias = prop_data['validade_dias']
        proposta.status = prop_data['status']
        proposta.criado_por = admin.id
        
        if 'data_resposta_cliente' in prop_data:
            proposta.data_resposta_cliente = prop_data['data_resposta_cliente']
        if 'observacoes_cliente' in prop_data:
            proposta.observacoes_cliente = prop_data['observacoes_cliente']
        
        db.session.add(proposta)
        db.session.flush()  # Para obter ID
        
        # Adicionar itens
        total_value = 0
        for i, item_data in enumerate(prop_data['itens']):
            item = PropostaItem()
            item.proposta_id = proposta.id
            item.item_numero = i + 1
            item.descricao = item_data['descricao']
            item.quantidade = item_data['quantidade']
            item.unidade = item_data['unidade']
            item.preco_unitario = item_data['preco_unitario']
            item.ordem = i + 1
            
            db.session.add(item)
            total_value += float(item.quantidade) * float(item.preco_unitario)
        
        # Calcular valor total
        proposta.valor_total = total_value
        
        print(f"✅ Proposta criada: {proposta.cliente_nome} - R$ {total_value:,.2f}")
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        print("🚀 Criando dados de exemplo para propostas...")
        
        # Criar templates
        print("\n📋 Criando templates padrão...")
        criar_templates_padrao()
        
        # Criar propostas exemplo
        print("\n📄 Criando propostas de exemplo...")
        criar_propostas_exemplo()
        
        print("\n✅ Dados de exemplo criados com sucesso!")
        print("\n📊 Resumo:")
        print(f"   Templates: {PropostaTemplate.query.count()}")
        print(f"   Propostas: {Proposta.query.count()}")
        print(f"   Itens: {PropostaItem.query.count()}")