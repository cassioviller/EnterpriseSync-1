"""
Seeds para módulo financeiro - Plano de Contas padrão para construção civil
"""
from app import app, db
from models import PlanoContas
import logging

logger = logging.getLogger(__name__)

PLANO_CONTAS_CONSTRUCAO = [
    # 1. ATIVO
    {"codigo": "1", "nome": "ATIVO", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 1, "conta_pai_codigo": None, "aceita_lancamento": False},
    {"codigo": "1.1", "nome": "ATIVO CIRCULANTE", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 2, "conta_pai_codigo": "1", "aceita_lancamento": False},
    
    # 1.1.01 DISPONIBILIDADES
    {"codigo": "1.1.01", "nome": "DISPONIBILIDADES", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "1.1", "aceita_lancamento": False},
    {"codigo": "1.1.01.001", "nome": "Caixa Geral", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.01", "aceita_lancamento": True},
    {"codigo": "1.1.01.002", "nome": "Banco Bradesco CC", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.01", "aceita_lancamento": True},
    {"codigo": "1.1.01.003", "nome": "Banco Itaú CC", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.01", "aceita_lancamento": True},
    
    # 1.1.02 CLIENTES
    {"codigo": "1.1.02", "nome": "CLIENTES", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "1.1", "aceita_lancamento": False},
    {"codigo": "1.1.02.001", "nome": "Clientes a Receber", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.02", "aceita_lancamento": True},
    
    # 1.1.03 ESTOQUE
    {"codigo": "1.1.03", "nome": "ESTOQUE", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "1.1", "aceita_lancamento": False},
    {"codigo": "1.1.03.001", "nome": "Material de Construção", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.03", "aceita_lancamento": True},
    {"codigo": "1.1.03.002", "nome": "Ferramentas e Equipamentos", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.03", "aceita_lancamento": True},
    {"codigo": "1.1.03.003", "nome": "EPIs", "tipo_conta": "ATIVO", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "1.1.03", "aceita_lancamento": True},
    
    # 2. PASSIVO
    {"codigo": "2", "nome": "PASSIVO", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 1, "conta_pai_codigo": None, "aceita_lancamento": False},
    {"codigo": "2.1", "nome": "PASSIVO CIRCULANTE", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 2, "conta_pai_codigo": "2", "aceita_lancamento": False},
    
    # 2.1.01 FORNECEDORES
    {"codigo": "2.1.01", "nome": "FORNECEDORES", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 3, "conta_pai_codigo": "2.1", "aceita_lancamento": False},
    {"codigo": "2.1.01.001", "nome": "Fornecedores a Pagar", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "2.1.01", "aceita_lancamento": True},
    
    # 2.1.02 OBRIGAÇÕES TRABALHISTAS
    {"codigo": "2.1.02", "nome": "OBRIGAÇÕES TRABALHISTAS", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 3, "conta_pai_codigo": "2.1", "aceita_lancamento": False},
    {"codigo": "2.1.02.001", "nome": "Salários a Pagar", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "2.1.02", "aceita_lancamento": True},
    {"codigo": "2.1.02.002", "nome": "INSS a Recolher", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "2.1.02", "aceita_lancamento": True},
    {"codigo": "2.1.02.003", "nome": "FGTS a Recolher", "tipo_conta": "PASSIVO", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "2.1.02", "aceita_lancamento": True},
    
    # 3. PATRIMÔNIO LÍQUIDO
    {"codigo": "3", "nome": "PATRIMÔNIO LÍQUIDO", "tipo_conta": "PATRIMONIO", "natureza": "CREDORA", "nivel": 1, "conta_pai_codigo": None, "aceita_lancamento": False},
    {"codigo": "3.1", "nome": "CAPITAL SOCIAL", "tipo_conta": "PATRIMONIO", "natureza": "CREDORA", "nivel": 2, "conta_pai_codigo": "3", "aceita_lancamento": False},
    {"codigo": "3.1.01", "nome": "Capital Subscrito", "tipo_conta": "PATRIMONIO", "natureza": "CREDORA", "nivel": 3, "conta_pai_codigo": "3.1", "aceita_lancamento": True},
    
    # 4. RECEITAS
    {"codigo": "4", "nome": "RECEITAS", "tipo_conta": "RECEITA", "natureza": "CREDORA", "nivel": 1, "conta_pai_codigo": None, "aceita_lancamento": False},
    {"codigo": "4.1", "nome": "RECEITAS OPERACIONAIS", "tipo_conta": "RECEITA", "natureza": "CREDORA", "nivel": 2, "conta_pai_codigo": "4", "aceita_lancamento": False},
    
    # 4.1.01 RECEITA COM OBRAS
    {"codigo": "4.1.01", "nome": "RECEITA COM OBRAS", "tipo_conta": "RECEITA", "natureza": "CREDORA", "nivel": 3, "conta_pai_codigo": "4.1", "aceita_lancamento": False},
    {"codigo": "4.1.01.001", "nome": "Receita de Obras Residenciais", "tipo_conta": "RECEITA", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "4.1.01", "aceita_lancamento": True},
    {"codigo": "4.1.01.002", "nome": "Receita de Obras Comerciais", "tipo_conta": "RECEITA", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "4.1.01", "aceita_lancamento": True},
    {"codigo": "4.1.01.003", "nome": "Receita de Reformas", "tipo_conta": "RECEITA", "natureza": "CREDORA", "nivel": 4, "conta_pai_codigo": "4.1.01", "aceita_lancamento": True},
    
    # 5. DESPESAS
    {"codigo": "5", "nome": "DESPESAS", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 1, "conta_pai_codigo": None, "aceita_lancamento": False},
    {"codigo": "5.1", "nome": "DESPESAS OPERACIONAIS", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 2, "conta_pai_codigo": "5", "aceita_lancamento": False},
    
    # 5.1.01 MÃO DE OBRA
    {"codigo": "5.1.01", "nome": "MÃO DE OBRA", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "5.1", "aceita_lancamento": False},
    {"codigo": "5.1.01.001", "nome": "Salários", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.01", "aceita_lancamento": True},
    {"codigo": "5.1.01.002", "nome": "Encargos Sociais", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.01", "aceita_lancamento": True},
    {"codigo": "5.1.01.003", "nome": "Vale Transporte", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.01", "aceita_lancamento": True},
    {"codigo": "5.1.01.004", "nome": "Vale Alimentação", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.01", "aceita_lancamento": True},
    
    # 5.1.02 MATERIAIS
    {"codigo": "5.1.02", "nome": "MATERIAIS", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "5.1", "aceita_lancamento": False},
    {"codigo": "5.1.02.001", "nome": "Material de Construção", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.02", "aceita_lancamento": True},
    {"codigo": "5.1.02.002", "nome": "Ferramentas", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.02", "aceita_lancamento": True},
    {"codigo": "5.1.02.003", "nome": "EPIs", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.02", "aceita_lancamento": True},
    
    # 5.1.03 EQUIPAMENTOS
    {"codigo": "5.1.03", "nome": "EQUIPAMENTOS", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "5.1", "aceita_lancamento": False},
    {"codigo": "5.1.03.001", "nome": "Aluguel de Equipamentos", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.03", "aceita_lancamento": True},
    {"codigo": "5.1.03.002", "nome": "Manutenção de Equipamentos", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.03", "aceita_lancamento": True},
    
    # 5.1.04 VEÍCULOS
    {"codigo": "5.1.04", "nome": "VEÍCULOS", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "5.1", "aceita_lancamento": False},
    {"codigo": "5.1.04.001", "nome": "Combustível", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.04", "aceita_lancamento": True},
    {"codigo": "5.1.04.002", "nome": "Manutenção de Veículos", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.04", "aceita_lancamento": True},
    {"codigo": "5.1.04.003", "nome": "IPVA e Licenciamento", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.04", "aceita_lancamento": True},
    
    # 5.1.05 DESPESAS ADMINISTRATIVAS
    {"codigo": "5.1.05", "nome": "DESPESAS ADMINISTRATIVAS", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 3, "conta_pai_codigo": "5.1", "aceita_lancamento": False},
    {"codigo": "5.1.05.001", "nome": "Material de Escritório", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.05", "aceita_lancamento": True},
    {"codigo": "5.1.05.002", "nome": "Telefone e Internet", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.05", "aceita_lancamento": True},
    {"codigo": "5.1.05.003", "nome": "Energia Elétrica", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.05", "aceita_lancamento": True},
    {"codigo": "5.1.05.004", "nome": "Água e Esgoto", "tipo_conta": "DESPESA", "natureza": "DEVEDORA", "nivel": 4, "conta_pai_codigo": "5.1.05", "aceita_lancamento": True},
]


def criar_plano_contas_padrao(admin_id):
    """
    Cria plano de contas padrão para construção civil para um admin_id específico
    
    Args:
        admin_id: ID do usuário administrador
    
    Returns:
        int: Número de contas criadas
    """
    try:
        contas_criadas = 0
        
        # Verificar se já existe plano de contas para este admin
        contas_existentes = PlanoContas.query.filter_by(admin_id=admin_id).count()
        if contas_existentes > 0:
            logger.info(f"⚠️ Admin {admin_id} já possui {contas_existentes} contas no plano")
            return 0
        
        logger.info(f"📊 Criando plano de contas padrão para admin_id={admin_id}")
        
        # Criar contas na ordem hierárquica
        for conta_data in PLANO_CONTAS_CONSTRUCAO:
            # Verificar se a conta já existe
            conta_existente = PlanoContas.query.filter_by(
                codigo=conta_data['codigo'],
                admin_id=admin_id
            ).first()
            
            if not conta_existente:
                nova_conta = PlanoContas(
                    codigo=conta_data['codigo'],
                    nome=conta_data['nome'],
                    tipo_conta=conta_data['tipo_conta'],
                    natureza=conta_data['natureza'],
                    nivel=conta_data['nivel'],
                    conta_pai_codigo=conta_data['conta_pai_codigo'],
                    aceita_lancamento=conta_data['aceita_lancamento'],
                    ativo=True,
                    admin_id=admin_id
                )
                db.session.add(nova_conta)
                contas_criadas += 1
        
        db.session.commit()
        
        # Invalidar cache após criação do plano de contas
        PlanoContas.invalidar_cache()
        
        logger.info(f"✅ {contas_criadas} contas criadas com sucesso!")
        return contas_criadas
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar plano de contas: {str(e)}")
        raise


def listar_plano_contas(admin_id):
    """Lista plano de contas de um admin"""
    contas = PlanoContas.query.filter_by(admin_id=admin_id).order_by(PlanoContas.codigo).all()
    
    print(f"\n📊 PLANO DE CONTAS - Admin {admin_id}")
    print("=" * 80)
    
    for conta in contas:
        indent = "  " * (conta.nivel - 1)
        tipo_icon = "💰" if conta.aceita_lancamento else "📂"
        print(f"{tipo_icon} {indent}{conta.codigo} - {conta.nome} ({conta.tipo_conta})")
    
    print("=" * 80)
    print(f"Total: {len(contas)} contas")


if __name__ == "__main__":
    # Exemplo de uso
    with app.app_context():
        # Criar para admin_id=10 (exemplo)
        admin_id = 10
        contas = criar_plano_contas_padrao(admin_id)
        print(f"✅ {contas} contas criadas!")
        
        # Listar
        listar_plano_contas(admin_id)
