"""
AUTO-FIX UNIVERSAL: Adiciona admin_id em TODAS as tabelas que precisam
Executa automaticamente no startup para garantir 100% de cobertura
"""
import logging
from sqlalchemy import text, inspect

logger = logging.getLogger(__name__)

# Mapeamento de tabelas para estratégias de backfill
BACKFILL_STRATEGIES = {
    # Via relacionamento direto com obra
    'servico_obra': 'obra_id',
    'servico_obra_real': 'obra_id',
    'orcamento_obra': 'obra_id',
    'custo_obra': 'obra_id',
    'notificacao_cliente': 'obra_id',
    'rdo': 'obra_id',
    'alocacao_equipe': 'obra_id',
    'allocation': 'obra_id',
    
    # Via RDO
    'rdo_mao_obra': 'rdo_id',
    'rdo_equipamento': 'rdo_id',
    'rdo_ocorrencia': 'rdo_id',
    'rdo_foto': 'rdo_id',
    'rdo_servico_subatividade': 'rdo_id',
    
    # Via funcionário
    'registro_ponto': 'funcionario_id',
    'beneficio_funcionario': 'funcionario_id',
    'calculo_horas_mensal': 'funcionario_id',
    'ferias_decimo': 'funcionario_id',
    'funcionario_obras_ponto': 'funcionario_id',
    
    # Via allocation
    'allocation_employee': 'allocation_id',
    
    # Via proposta
    'proposta_historico': 'proposta_id',
    'proposta_itens': 'proposta_id',
    'proposta_arquivos': 'proposta_id',
    
    # Via veiculo/frota
    'uso_veiculo': 'veiculo_id',
    'custo_veiculo': 'veiculo_id',
    'frota_utilizacao': 'veiculo_id',
    'frota_despesa': 'veiculo_id',
    
    # Via almoxarifado
    'almoxarifado_estoque': 'item_id',
    'almoxarifado_movimento': 'item_id',
    
    # Via restaurante
    'alimentacao_lancamento': 'restaurante_id',
    
    # Tabelas que usam mode (valor mais comum)
    'funcao': 'mode',
    'departamento': 'mode',
    'horario_trabalho': 'mode',
    'registro_alimentacao': 'mode',
    'categoria_servico': 'mode',
    'categoria_produto': 'mode',
    'tipo_ocorrencia': 'mode',
}

# Tabelas globais que NÃO precisam de admin_id
GLOBAL_TABLES = {
    'migration_history',
    'calendario_util',
}

def get_admin_id_via_relationship(table_name, foreign_key):
    """Gera SQL para backfill via relacionamento"""
    
    # Mapeamento de FK para tabela relacionada
    FK_TABLE_MAP = {
        'obra_id': ('obra', 'o'),
        'rdo_id': ('rdo', 'r'),
        'funcionario_id': ('funcionario', 'f'),
        'allocation_id': ('allocation', 'a'),
        'proposta_id': ('propostas_comerciais', 'p'),
        'veiculo_id': ('veiculo', 'v'),
        'item_id': ('almoxarifado_item', 'ai'),
        'restaurante_id': ('restaurante', 'res'),
    }
    
    if foreign_key not in FK_TABLE_MAP:
        return None
    
    related_table, alias = FK_TABLE_MAP[foreign_key]
    table_alias = table_name[:3]
    
    # Para RDO, precisa fazer join em cascata: rdo -> obra
    if foreign_key == 'rdo_id':
        return f"""
            UPDATE {table_name} {table_alias}
            SET admin_id = o.admin_id
            FROM rdo r
            JOIN obra o ON r.obra_id = o.id
            WHERE {table_alias}.rdo_id = r.id
              AND {table_alias}.admin_id IS NULL;
        """
    
    # Para outros, join direto
    return f"""
        UPDATE {table_name} {table_alias}
        SET admin_id = {alias}.admin_id
        FROM {related_table} {alias}
        WHERE {table_alias}.{foreign_key} = {alias}.id
          AND {table_alias}.admin_id IS NULL;
    """

def get_admin_id_via_mode(table_name):
    """Gera SQL para backfill usando modo (valor mais comum)"""
    return f"""
        UPDATE {table_name}
        SET admin_id = (
            SELECT admin_id
            FROM usuario
            GROUP BY admin_id
            ORDER BY COUNT(*) DESC
            LIMIT 1
        )
        WHERE admin_id IS NULL;
    """

def fix_table_admin_id(connection, table_name):
    """Adiciona admin_id em uma tabela específica"""
    try:
        # Verificar se coluna já existe
        result = connection.execute(text(f"""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
              AND column_name = 'admin_id'
        """))
        
        if result.scalar() > 0:
            return True, "skip"
        
        logger.warning(f"⚠️  {table_name}.admin_id NÃO EXISTE - adicionando...")
        
        # Adicionar coluna
        connection.execute(text(f"""
            ALTER TABLE {table_name} ADD COLUMN admin_id INTEGER;
        """))
        
        # Backfill
        strategy = BACKFILL_STRATEGIES.get(table_name, 'mode')
        
        if strategy == 'mode':
            backfill_sql = get_admin_id_via_mode(table_name)
        else:
            backfill_sql = get_admin_id_via_relationship(table_name, strategy)
        
        if backfill_sql:
            connection.execute(text(backfill_sql))
        
        # Aplicar NOT NULL
        connection.execute(text(f"""
            ALTER TABLE {table_name} ALTER COLUMN admin_id SET NOT NULL;
        """))
        
        # Adicionar FK
        connection.execute(text(f"""
            ALTER TABLE {table_name}
            ADD CONSTRAINT fk_{table_name}_admin_id
            FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE;
        """))
        
        # Criar índice
        connection.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_admin_id 
            ON {table_name}(admin_id);
        """))
        
        connection.commit()
        logger.info(f"✅ {table_name}.admin_id adicionado com sucesso")
        return True, "added"
        
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir {table_name}: {e}")
        try:
            connection.rollback()
        except:
            pass
        return False, str(e)

def get_all_tables_with_admin_id(db_engine):
    """Lista todas as tabelas que deveriam ter admin_id"""
    inspector = inspect(db_engine)
    all_tables = inspector.get_table_names()
    
    # Filtrar tabelas globais
    tables_needing_admin = [
        t for t in all_tables 
        if t not in GLOBAL_TABLES
    ]
    
    return tables_needing_admin

def auto_fix_all_admin_id():
    """
    AUTO-FIX UNIVERSAL: Verifica e corrige TODAS as tabelas
    """
    from app import db
    
    logger.info("=" * 100)
    logger.info("🔧 AUTO-FIX UNIVERSAL: Verificando TODAS as tabelas para admin_id...")
    logger.info("=" * 100)
    
    try:
        with db.engine.connect() as connection:
            # Obter lista de todas as tabelas
            tables = get_all_tables_with_admin_id(db.engine)
            
            results = {
                'skip': [],
                'added': [],
                'failed': []
            }
            
            # Processar cada tabela
            for table_name in sorted(tables):
                success, status = fix_table_admin_id(connection, table_name)
                
                if success:
                    if status == 'skip':
                        results['skip'].append(table_name)
                        logger.debug(f"✅ {table_name}.admin_id já existe")
                    else:
                        results['added'].append(table_name)
                else:
                    results['failed'].append((table_name, status))
            
            # Resumo
            logger.info("=" * 100)
            logger.info("📊 RESUMO DO AUTO-FIX UNIVERSAL")
            logger.info("=" * 100)
            logger.info(f"✅ Tabelas já OK: {len(results['skip'])}")
            logger.info(f"➕ Tabelas corrigidas: {len(results['added'])}")
            logger.info(f"❌ Tabelas com erro: {len(results['failed'])}")
            logger.info(f"📊 Total verificadas: {len(tables)}")
            
            if results['added']:
                logger.info("")
                logger.info("➕ Tabelas que foram corrigidas:")
                for table in results['added']:
                    logger.info(f"  ➕ {table}")
            
            if results['failed']:
                logger.warning("")
                logger.warning("❌ Tabelas com erro:")
                for table, error in results['failed']:
                    logger.warning(f"  ❌ {table}: {error}")
            
            logger.info("=" * 100)
            
            if len(results['failed']) == 0:
                logger.info("✅ AUTO-FIX UNIVERSAL CONCLUÍDO COM SUCESSO!")
            else:
                logger.warning("⚠️  AUTO-FIX UNIVERSAL concluído com algumas falhas")
            
            logger.info("=" * 100)
            
            return len(results['failed']) == 0
            
    except Exception as e:
        logger.error(f"❌ Erro crítico no auto-fix universal: {e}")
        return False
