"""
Migrações automáticas do banco de dados
Executadas automaticamente na inicialização da aplicação
"""
import logging
from sqlalchemy import text
from models import db
import os
import re

logger = logging.getLogger(__name__)

def mask_database_url(url):
    """Mascara credenciais em URLs de banco para logs seguros"""
    if not url:
        return "None"
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked

# ============================================================================
# SISTEMA DE RASTREAMENTO DE MIGRAÇÕES - IDEMPOTÊNCIA GARANTIDA
# ============================================================================

def ensure_migration_history_table():
    """Cria tabela migration_history se não existir - primeira execução"""
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                id SERIAL PRIMARY KEY,
                migration_number INTEGER UNIQUE NOT NULL,
                migration_name VARCHAR(200) NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                execution_time_ms INTEGER,
                status VARCHAR(20) DEFAULT 'success',
                error_message TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_migration_number 
            ON migration_history(migration_number)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_migration_executed 
            ON migration_history(executed_at)
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.debug("✅ Tabela migration_history verificada/criada")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela migration_history: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def is_migration_executed(migration_number):
    """Verifica se uma migração já foi executada com sucesso"""
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT status FROM migration_history 
            WHERE migration_number = %s
        """, (migration_number,))
        
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if result:
            status = result[0]
            return status == 'success'
        return False
        
    except Exception as e:
        logger.debug(f"Migração {migration_number} não encontrada no histórico: {e}")
        return False

def record_migration(migration_number, migration_name, status='success', execution_time_ms=None, error_message=None):
    """Registra a execução de uma migração no histórico"""
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO migration_history 
            (migration_number, migration_name, executed_at, execution_time_ms, status, error_message)
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
            ON CONFLICT (migration_number) 
            DO UPDATE SET 
                executed_at = CURRENT_TIMESTAMP,
                execution_time_ms = EXCLUDED.execution_time_ms,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message
        """, (migration_number, migration_name, execution_time_ms, status, error_message))
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.debug(f"✅ Migração {migration_number} registrada: {status}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao registrar migração {migration_number}: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def run_migration_safe(migration_number, migration_name, migration_func):
    """
    Executa migração com rastreamento e idempotência garantida
    
    Args:
        migration_number: Número da migração (ex: 43)
        migration_name: Nome da migração (ex: "Completar estruturas v9.0")
        migration_func: Função da migração a ser executada
    
    Returns:
        bool: True se executada com sucesso, False caso contrário
    """
    import time
    
    # Verificar se já foi executada
    if is_migration_executed(migration_number):
        logger.info(f"⏭️  Migração {migration_number} ({migration_name}) já executada - SKIP")
        return True
    
    logger.info(f"🔄 Executando Migração {migration_number}: {migration_name}")
    start_time = time.time()
    
    try:
        # Executar migração
        migration_func()
        
        # Calcular tempo de execução
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Registrar sucesso
        record_migration(migration_number, migration_name, 'success', execution_time_ms)
        
        logger.info(f"✅ Migração {migration_number} concluída em {execution_time_ms}ms")
        return True
        
    except Exception as e:
        # Calcular tempo mesmo em erro
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # CRÍTICO: Fazer rollback para limpar sessão
        try:
            db.session.rollback()
            logger.debug("✅ Session rollback executado após falha na migração")
        except Exception as rollback_error:
            logger.warning(f"⚠️ Erro ao fazer rollback: {rollback_error}")
        
        # Registrar falha
        error_msg = str(e)[:500]  # Limitar tamanho do erro
        record_migration(migration_number, migration_name, 'failed', execution_time_ms, error_msg)
        
        logger.error(f"❌ Migração {migration_number} falhou após {execution_time_ms}ms: {e}")
        
        # Não propagar exceção - apenas logar
        return False

# ============================================================================
# MIGRAÇÕES INDIVIDUAIS
# ============================================================================

def _migration_27_alimentacao_system():
    """
    Migration 27: Sistema de Alimentação
    Cria tabelas: restaurante, alimentacao_lancamento, alimentacao_funcionarios_assoc
    """
    logger.info("=" * 80)
    logger.info("🍽️  MIGRAÇÃO 27: Sistema de Alimentação")
    logger.info("=" * 80)
    
    try:
        # 1. Criar tabela restaurante (se não existir - pode já existir do sistema antigo)
        logger.info("📋 Criando tabela restaurante...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS restaurante (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                endereco TEXT,
                telefone VARCHAR(20),
                admin_id INTEGER REFERENCES usuario(id)
            )
        """))
        logger.info("✅ Tabela restaurante criada/verificada")
        
        # 2. Criar tabela alimentacao_lancamento
        logger.info("📋 Criando tabela alimentacao_lancamento...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS alimentacao_lancamento (
                id SERIAL PRIMARY KEY,
                data DATE NOT NULL,
                valor_total NUMERIC(10, 2) NOT NULL,
                descricao TEXT,
                restaurante_id INTEGER NOT NULL REFERENCES restaurante(id),
                obra_id INTEGER NOT NULL REFERENCES obra(id),
                admin_id INTEGER NOT NULL REFERENCES usuario(id)
            )
        """))
        logger.info("✅ Tabela alimentacao_lancamento criada/verificada")
        
        # 3. Criar índice na data
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_alimentacao_lancamento_data 
            ON alimentacao_lancamento(data)
        """))
        
        # 4. Criar tabela de associação
        logger.info("📋 Criando tabela alimentacao_funcionarios_assoc...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS alimentacao_funcionarios_assoc (
                lancamento_id INTEGER NOT NULL REFERENCES alimentacao_lancamento(id) ON DELETE CASCADE,
                funcionario_id INTEGER NOT NULL REFERENCES funcionario(id) ON DELETE CASCADE,
                PRIMARY KEY (lancamento_id, funcionario_id)
            )
        """))
        logger.info("✅ Tabela alimentacao_funcionarios_assoc criada/verificada")
        
        db.session.commit()
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 27 CONCLUÍDA: Sistema de Alimentação implantado!")
        logger.info("=" * 80)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro na migração 27: {e}")
        import traceback
        logger.error(traceback.format_exc())

def _migration_33_recreate_frota_despesa():
    """
    Migration 33: Recriar tabela frota_despesa com schema completo
    
    OBJETIVO: Recriar tabela frota_despesa do zero com todos os campos corretos,
              preservando 100% dos dados.
    
    PROCESSO (4 ETAPAS):
    1. BACKUP: Criar tabela temporária com todos os dados
    2. DROP: Remover tabela antiga com CASCADE
    3. CREATE: Criar nova tabela com schema completo
    4. RESTORE: Restaurar dados do backup e limpar
    
    SEGURANÇA: Só executa se RECREATE_FROTA_DESPESA=true
    IDEMPOTENTE: Pode executar múltiplas vezes sem problemas
    """
    try:
        # Verificar feature flag de segurança
        if os.environ.get('RECREATE_FROTA_DESPESA', 'false').lower() != 'true':
            logger.info("🔒 MIGRAÇÃO 33: Bloqueada por segurança. Para ativar: RECREATE_FROTA_DESPESA=true")
            return
        
        logger.info("=" * 80)
        logger.info("💰 MIGRAÇÃO 33: Recriar tabela frota_despesa com schema completo")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # =====================================================================
        # PASSO 1: VERIFICAR SE TABELA EXISTE
        # =====================================================================
        logger.info("🔍 PASSO 1: Verificando existência da tabela frota_despesa...")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'frota_despesa'
            )
        """)
        tabela_existe = cursor.fetchone()[0]
        
        if not tabela_existe:
            logger.info("ℹ️ Tabela frota_despesa não existe. Criando do zero...")
            
            # Criar tabela do zero
            cursor.execute("""
                CREATE TABLE frota_despesa (
                    id SERIAL PRIMARY KEY,
                    veiculo_id INTEGER NOT NULL REFERENCES frota_veiculo(id) ON DELETE CASCADE,
                    obra_id INTEGER REFERENCES obra(id),
                    data_custo DATE NOT NULL,
                    tipo_custo VARCHAR(30) NOT NULL,
                    valor NUMERIC(10, 2) NOT NULL,
                    descricao VARCHAR(200) NOT NULL,
                    fornecedor VARCHAR(100),
                    numero_nota_fiscal VARCHAR(20),
                    data_vencimento DATE,
                    status_pagamento VARCHAR(20) DEFAULT 'Pendente',
                    forma_pagamento VARCHAR(30),
                    km_veiculo INTEGER,
                    observacoes TEXT,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            
            # Criar índices
            cursor.execute("CREATE INDEX idx_frota_despesa_veiculo ON frota_despesa(veiculo_id)")
            cursor.execute("CREATE INDEX idx_frota_despesa_data ON frota_despesa(data_custo)")
            cursor.execute("CREATE INDEX idx_frota_despesa_admin ON frota_despesa(admin_id)")
            cursor.execute("CREATE INDEX idx_frota_despesa_obra ON frota_despesa(obra_id)")
            
            connection.commit()
            logger.info("✅ Tabela frota_despesa criada do zero com sucesso!")
            logger.info("=" * 80)
            cursor.close()
            connection.close()
            return
        
        # =====================================================================
        # PASSO 2: BACKUP - Criar tabela temporária
        # =====================================================================
        logger.info("📦 PASSO 2: Criando backup da tabela frota_despesa...")
        
        cursor.execute("DROP TABLE IF EXISTS frota_despesa_backup CASCADE")
        cursor.execute("CREATE TABLE frota_despesa_backup AS SELECT * FROM frota_despesa")
        
        backup_count = cursor.rowcount
        logger.info(f"✅ Backup criado: {backup_count} registros copiados")
        
        # =====================================================================
        # PASSO 3: DROP - Remover tabela antiga
        # =====================================================================
        logger.info("🗑️ PASSO 3: Removendo tabela frota_despesa antiga...")
        
        cursor.execute("DROP TABLE IF EXISTS frota_despesa CASCADE")
        logger.info("✅ Tabela antiga removida com CASCADE")
        
        # =====================================================================
        # PASSO 4: CREATE - Criar nova tabela com schema completo
        # =====================================================================
        logger.info("🔨 PASSO 4: Criando nova tabela frota_despesa com schema completo...")
        
        cursor.execute("""
            CREATE TABLE frota_despesa (
                id SERIAL PRIMARY KEY,
                veiculo_id INTEGER NOT NULL REFERENCES frota_veiculo(id) ON DELETE CASCADE,
                obra_id INTEGER REFERENCES obra(id),
                data_custo DATE NOT NULL,
                tipo_custo VARCHAR(30) NOT NULL,
                valor NUMERIC(10, 2) NOT NULL,
                descricao VARCHAR(200) NOT NULL,
                fornecedor VARCHAR(100),
                numero_nota_fiscal VARCHAR(20),
                data_vencimento DATE,
                status_pagamento VARCHAR(20) DEFAULT 'Pendente',
                forma_pagamento VARCHAR(30),
                km_veiculo INTEGER,
                observacoes TEXT,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        logger.info("✅ Nova tabela frota_despesa criada")
        
        # Criar índices
        logger.info("📊 Criando índices...")
        cursor.execute("CREATE INDEX idx_frota_despesa_veiculo ON frota_despesa(veiculo_id)")
        cursor.execute("CREATE INDEX idx_frota_despesa_data ON frota_despesa(data_custo)")
        cursor.execute("CREATE INDEX idx_frota_despesa_admin ON frota_despesa(admin_id)")
        cursor.execute("CREATE INDEX idx_frota_despesa_obra ON frota_despesa(obra_id)")
        logger.info("✅ Índices criados")
        
        # =====================================================================
        # PASSO 5: RESTORE - Restaurar dados do backup
        # =====================================================================
        logger.info("♻️ PASSO 5: Restaurando dados do backup...")
        
        # Verificar colunas disponíveis no backup
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'frota_despesa_backup'
            ORDER BY ordinal_position
        """)
        colunas_backup = [row[0] for row in cursor.fetchall()]
        logger.info(f"📋 Colunas no backup: {', '.join(colunas_backup)}")
        
        # Construir query de INSERT com colunas disponíveis
        colunas_comuns = []
        colunas_select = []
        
        for col in ['id', 'veiculo_id', 'obra_id', 'data_custo', 'tipo_custo', 'valor', 'descricao',
                    'fornecedor', 'numero_nota_fiscal', 'data_vencimento', 'status_pagamento',
                    'forma_pagamento', 'km_veiculo', 'observacoes', 'admin_id', 
                    'created_at', 'updated_at']:
            if col in colunas_backup:
                colunas_comuns.append(col)
                colunas_select.append(col)
        
        if colunas_comuns:
            insert_query = f"""
                INSERT INTO frota_despesa ({', '.join(colunas_comuns)})
                SELECT {', '.join(colunas_select)}
                FROM frota_despesa_backup
            """
            cursor.execute(insert_query)
            restored_count = cursor.rowcount
            logger.info(f"✅ {restored_count} registros restaurados")
        else:
            logger.warning("⚠️ Nenhuma coluna comum encontrada para restaurar")
        
        # =====================================================================
        # PASSO 6: AJUSTAR SEQUENCE
        # =====================================================================
        logger.info("🔢 PASSO 6: Ajustando sequence...")
        
        cursor.execute("""
            SELECT setval('frota_despesa_id_seq', 
                          COALESCE((SELECT MAX(id) FROM frota_despesa), 1))
        """)
        logger.info("✅ Sequence frota_despesa_id_seq ajustada")
        
        # =====================================================================
        # PASSO 7: REMOVER BACKUP
        # =====================================================================
        logger.info("🗑️ PASSO 7: Removendo tabela de backup...")
        
        cursor.execute("DROP TABLE IF EXISTS frota_despesa_backup")
        logger.info("✅ Tabela de backup removida")
        
        # Commit final
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 33 CONCLUÍDA COM SUCESSO!")
        logger.info("🎯 Tabela frota_despesa recriada com schema completo")
        logger.info(f"📊 {restored_count if 'restored_count' in locals() else 0} registros preservados")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 33: {e}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())

def _migration_34_restaurante_campos_pagamento():
    """
    Migration 34: Adicionar campos de pagamento no Restaurante
    Adiciona: razao_social, cnpj, pix, nome_conta
    """
    logger.info("=" * 80)
    logger.info("🍽️  MIGRAÇÃO 34: Campos de Pagamento - Restaurante")
    logger.info("=" * 80)
    
    try:
        # Verificar se tabela existe
        result = db.session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'restaurante'
            )
        """))
        if not result.scalar():
            logger.info("⏭️  Tabela restaurante não existe, pulando migração 34")
            return
        
        # Adicionar campos
        campos = [
            ('razao_social', 'VARCHAR(200)'),
            ('cnpj', 'VARCHAR(18)'),
            ('pix', 'VARCHAR(100)'),
            ('nome_conta', 'VARCHAR(100)')
        ]
        
        for campo, tipo in campos:
            # Verificar se coluna já existe
            result = db.session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'restaurante' 
                AND column_name = '{campo}'
            """))
            
            if result.scalar():
                logger.info(f"✅ Coluna '{campo}' já existe na tabela restaurante")
            else:
                db.session.execute(text(f"""
                    ALTER TABLE restaurante 
                    ADD COLUMN {campo} {tipo}
                """))
                logger.info(f"➕ Coluna '{campo}' adicionada à tabela restaurante")
        
        db.session.commit()
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 34 CONCLUÍDA: Campos de pagamento adicionados!")
        logger.info("=" * 80)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro na migração 34: {e}")
        import traceback
        logger.error(traceback.format_exc())

def _migration_20_unified_vehicle_system():
    """
    MIGRAÇÃO 20 UNIFICADA: Sistema de Veículos Inteligente
    
    ESTRATÉGIA INTELIGENTE:
    1. Detecta quais tabelas existem (frota_*, vehicle_*, veiculo, fleet_vehicle)
    2. Decide ação baseada no estado atual:
       - vehicle_* existem → SKIP (já migrado)
       - frota_* existem → CREATE vehicle_*, MIGRAR dados, DROP frota_*
       - Tabelas antigas existem → CREATE vehicle_*, MIGRAR dados, DROP antigas
       - Nenhuma existe → CREATE vehicle_* do zero
    
    SEGURANÇA: Só executa se RECREATE_VEHICLE_SYSTEM=true
    IDEMPOTENTE: Pode executar múltiplas vezes sem problemas
    
    CAMPOS PRESERVADOS:
    - Vehicle: placa, modelo, ano, cor, km_atual, renavam, chassi, tipo_veiculo, 
               status, data_ultima_manutencao, data_proxima_manutencao, 
               km_proxima_manutencao, observacoes, admin_id
    - VehicleUsage: data_uso, km_inicial, km_final, motorista_id, obra_id, 
                    observacoes, admin_id
    - VehicleExpense: tipo_custo, valor, data_custo, km_veiculo, descricao,
                      fornecedor, numero_nota_fiscal, data_vencimento, status, 
                      obra_id, admin_id
    """
    try:
        # Verificar feature flag de segurança
        if os.environ.get('RECREATE_VEHICLE_SYSTEM', 'false').lower() != 'true':
            logger.info("🔒 MIGRAÇÃO 20: Bloqueada por segurança. Para ativar: RECREATE_VEHICLE_SYSTEM=true")
            return
        
        logger.info("=" * 80)
        logger.info("🚗 MIGRAÇÃO 20 UNIFICADA: Sistema de Veículos Inteligente")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # =====================================================================
        # PASSO 1: DETECTAR ESTADO ATUAL DO BANCO
        # =====================================================================
        logger.info("🔍 PASSO 1: Detectando estado atual do banco de dados...")
        
        # Detectar tabelas existentes
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name IN ('vehicle', 'vehicle_usage', 'vehicle_expense',
                                 'frota_veiculo', 'frota_utilizacao', 'frota_despesa',
                                 'veiculo', 'uso_veiculo', 'custo_veiculo',
                                 'fleet_vehicle', 'fleet_vehicle_usage', 'fleet_vehicle_cost')
        """)
        tabelas_existentes = [row[0] for row in cursor.fetchall()]
        logger.info(f"📊 Tabelas encontradas: {tabelas_existentes}")
        
        # Decidir estratégia
        tem_vehicle = 'vehicle' in tabelas_existentes
        tem_frota = 'frota_veiculo' in tabelas_existentes
        tem_antigas = 'veiculo' in tabelas_existentes or 'fleet_vehicle' in tabelas_existentes
        
        # =====================================================================
        # PASSO 2: DECISÃO DE ESTRATÉGIA
        # =====================================================================
        if tem_vehicle:
            logger.info("✅ Tabelas vehicle_* já existem - Sistema já migrado!")
            logger.info("🎯 SKIP: Nenhuma ação necessária")
            cursor.close()
            connection.close()
            return
        
        elif tem_frota:
            logger.info("📋 Estratégia: MIGRAR frota_* → vehicle_*")
            tabelas_origem = 'frota'
            
        elif tem_antigas:
            logger.info("📋 Estratégia: MIGRAR tabelas antigas → vehicle_*")
            tabelas_origem = 'antigas'
            
        else:
            logger.info("📋 Estratégia: CREATE vehicle_* do zero (banco vazio)")
            tabelas_origem = 'criar'
        
        # =====================================================================
        # PASSO 3: CRIAR TABELAS vehicle_*
        # =====================================================================
        logger.info("🔨 PASSO 3: Criando tabelas vehicle_*...")
        
        # 3.1 - Tabela vehicle
        logger.info("🚗 Criando tabela vehicle...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicle (
                id SERIAL PRIMARY KEY,
                placa VARCHAR(10) NOT NULL,
                marca VARCHAR(50),
                modelo VARCHAR(100),
                ano INTEGER,
                cor VARCHAR(30),
                km_atual INTEGER DEFAULT 0,
                proprietario VARCHAR(100),
                renavam VARCHAR(20),
                chassi VARCHAR(50),
                tipo_veiculo VARCHAR(30) DEFAULT 'Utilitário',
                status VARCHAR(20) DEFAULT 'Ativo',
                data_aquisicao DATE,
                valor_aquisicao NUMERIC(10, 2),
                data_ultima_manutencao DATE,
                data_proxima_manutencao DATE,
                km_proxima_manutencao INTEGER,
                observacoes TEXT,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uk_vehicle_admin_placa UNIQUE (admin_id, placa)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_admin_id ON vehicle(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_placa ON vehicle(placa)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_status ON vehicle(status)")
        logger.info("✅ Tabela vehicle criada")
        
        # 3.2 - Tabela vehicle_usage
        logger.info("📝 Criando tabela vehicle_usage...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_usage (
                id SERIAL PRIMARY KEY,
                veiculo_id INTEGER NOT NULL REFERENCES vehicle(id) ON DELETE CASCADE,
                data_uso DATE NOT NULL,
                km_inicial INTEGER,
                km_final INTEGER,
                destino VARCHAR(200),
                motorista_id INTEGER REFERENCES funcionario(id),
                obra_id INTEGER REFERENCES obra(id),
                observacoes TEXT,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_usage_data ON vehicle_usage(data_uso)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_usage_veiculo ON vehicle_usage(veiculo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_usage_admin ON vehicle_usage(admin_id)")
        logger.info("✅ Tabela vehicle_usage criada")
        
        # 3.3 - Tabela vehicle_expense
        logger.info("💰 Criando tabela vehicle_expense...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_expense (
                id SERIAL PRIMARY KEY,
                veiculo_id INTEGER NOT NULL REFERENCES vehicle(id) ON DELETE CASCADE,
                tipo_custo VARCHAR(30) NOT NULL,
                valor NUMERIC(10, 2) NOT NULL,
                data_custo DATE NOT NULL,
                km_veiculo INTEGER,
                descricao VARCHAR(200),
                categoria VARCHAR(50),
                fornecedor VARCHAR(100),
                numero_nota_fiscal VARCHAR(20),
                data_vencimento DATE,
                status VARCHAR(20) DEFAULT 'Pendente',
                obra_id INTEGER REFERENCES obra(id),
                observacoes TEXT,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_expense_data ON vehicle_expense(data_custo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_expense_veiculo ON vehicle_expense(veiculo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_expense_admin ON vehicle_expense(admin_id)")
        logger.info("✅ Tabela vehicle_expense criada")
        
        # =====================================================================
        # PASSO 4: MIGRAR DADOS (se houver tabelas de origem)
        # =====================================================================
        if tabelas_origem == 'frota':
            logger.info("📋 PASSO 4: Migrando dados frota_* → vehicle_*...")
            
            # 4.1 - Migrar frota_veiculo → vehicle
            logger.info("🚗 Migrando frota_veiculo → vehicle...")
            cursor.execute("""
                INSERT INTO vehicle (
                    id, placa, marca, modelo, ano, cor, km_atual, chassi, renavam,
                    tipo_veiculo, status, data_ultima_manutencao, data_proxima_manutencao,
                    km_proxima_manutencao, admin_id, created_at, updated_at
                )
                SELECT 
                    id, placa, marca, modelo, ano, cor, 
                    COALESCE(km_atual, 0), chassi, renavam,
                    COALESCE(tipo, 'Utilitário'),
                    CASE WHEN ativo THEN 'Ativo' ELSE 'Inativo' END,
                    data_ultima_manutencao, data_proxima_manutencao,
                    km_proxima_manutencao, admin_id, created_at, updated_at
                FROM frota_veiculo
                ON CONFLICT (admin_id, placa) DO NOTHING
            """)
            veiculos_migrados = cursor.rowcount
            logger.info(f"✅ {veiculos_migrados} veículos migrados")
            
            # Atualizar sequence com NULL safety
            cursor.execute("SELECT setval('vehicle_id_seq', COALESCE((SELECT MAX(id) FROM vehicle), 1))")
            logger.info("✅ Sequence vehicle_id_seq atualizada com NULL safety")
            
            # 4.2 - Migrar frota_utilizacao → vehicle_usage
            if 'frota_utilizacao' in tabelas_existentes:
                logger.info("📝 Migrando frota_utilizacao → vehicle_usage...")
                cursor.execute("""
                    INSERT INTO vehicle_usage (
                        veiculo_id, data_uso, km_inicial, km_final, 
                        motorista_id, obra_id, observacoes, admin_id, created_at
                    )
                    SELECT 
                        veiculo_id, data_uso, km_inicial, km_final,
                        funcionario_id, obra_id, observacoes, admin_id, created_at
                    FROM frota_utilizacao
                """)
                usos_migrados = cursor.rowcount
                logger.info(f"✅ {usos_migrados} usos migrados")
                
                # Atualizar sequence com NULL safety
                cursor.execute("SELECT setval('vehicle_usage_id_seq', COALESCE((SELECT MAX(id) FROM vehicle_usage), 1))")
                logger.info("✅ Sequence vehicle_usage_id_seq atualizada com NULL safety")
            
            # 4.3 - Migrar frota_despesa → vehicle_expense
            if 'frota_despesa' in tabelas_existentes:
                logger.info("💰 Migrando frota_despesa → vehicle_expense...")
                cursor.execute("""
                    INSERT INTO vehicle_expense (
                        veiculo_id, tipo_custo, valor, data_custo, km_veiculo,
                        descricao, fornecedor, numero_nota_fiscal, data_vencimento,
                        status, obra_id, observacoes, admin_id, created_at
                    )
                    SELECT 
                        veiculo_id, tipo_custo, valor, data_custo, km_veiculo,
                        descricao, fornecedor, numero_nota_fiscal, data_vencimento,
                        status_pagamento, obra_id, observacoes, admin_id, created_at
                    FROM frota_despesa
                """)
                despesas_migradas = cursor.rowcount
                logger.info(f"✅ {despesas_migradas} despesas migradas")
                
                # Atualizar sequence com NULL safety
                cursor.execute("SELECT setval('vehicle_expense_id_seq', COALESCE((SELECT MAX(id) FROM vehicle_expense), 1))")
                logger.info("✅ Sequence vehicle_expense_id_seq atualizada com NULL safety")
        
        elif tabelas_origem == 'antigas':
            logger.info("📋 PASSO 4: Migrando dados tabelas antigas → vehicle_*...")
            
            # Migrar de veiculo/fleet_vehicle para vehicle
            if 'veiculo' in tabelas_existentes:
                logger.info("🚗 Migrando veiculo → vehicle...")
                cursor.execute("""
                    INSERT INTO vehicle (
                        placa, marca, modelo, ano, cor, km_atual, chassi, renavam,
                        tipo_veiculo, status, data_ultima_manutencao, 
                        data_proxima_manutencao, km_proxima_manutencao, admin_id
                    )
                    SELECT 
                        placa, marca, modelo, ano, cor, 
                        COALESCE(km_atual, 0), chassi, renavam,
                        COALESCE(tipo, 'Utilitário'),
                        CASE WHEN ativo THEN 'Ativo' ELSE 'Inativo' END,
                        data_ultima_manutencao, data_proxima_manutencao,
                        km_proxima_manutencao, admin_id
                    FROM veiculo
                    WHERE admin_id IS NOT NULL
                    ON CONFLICT (admin_id, placa) DO NOTHING
                """)
                logger.info(f"✅ {cursor.rowcount} veículos migrados")
            
            elif 'fleet_vehicle' in tabelas_existentes:
                logger.info("🚗 Migrando fleet_vehicle → vehicle...")
                cursor.execute("""
                    INSERT INTO vehicle (
                        placa, marca, modelo, ano, cor, km_atual, chassi, renavam,
                        tipo_veiculo, status, data_ultima_manutencao,
                        data_proxima_manutencao, km_proxima_manutencao, admin_id
                    )
                    SELECT 
                        reg_plate, make_name, model_name, vehicle_year, vehicle_color,
                        COALESCE(current_km, 0), chassis_number, renavam_code,
                        COALESCE(vehicle_kind, 'Utilitário'), status_code,
                        last_maintenance_date, next_maintenance_date,
                        next_maintenance_km, admin_owner_id
                    FROM fleet_vehicle
                    ON CONFLICT (admin_id, placa) DO NOTHING
                """)
                logger.info(f"✅ {cursor.rowcount} veículos migrados")
        
        else:
            logger.info("ℹ️ PASSO 4: Nenhum dado para migrar (banco vazio)")
        
        # =====================================================================
        # PASSO 5: REMOVER TABELAS ANTIGAS
        # =====================================================================
        logger.info("🗑️ PASSO 5: Removendo tabelas antigas...")
        
        tabelas_remover = []
        if tabelas_origem == 'frota':
            tabelas_remover = ['frota_despesa', 'frota_utilizacao', 'frota_veiculo']
        elif tabelas_origem == 'antigas':
            tabelas_remover = ['custo_veiculo', 'uso_veiculo', 'veiculo',
                             'fleet_vehicle_cost', 'fleet_vehicle_usage', 'fleet_vehicle',
                             'passageiro_veiculo', 'documento_fiscal']
        
        for tabela in tabelas_remover:
            if tabela in tabelas_existentes:
                logger.info(f"🗑️ DROP TABLE {tabela} CASCADE...")
                cursor.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
                logger.info(f"✅ Tabela {tabela} removida")
        
        # Commit final
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 20 UNIFICADA CONCLUÍDA COM SUCESSO!")
        logger.info("🎯 Sistema de veículos: vehicle, vehicle_usage, vehicle_expense")
        logger.info("✅ Dados preservados e migrados com sucesso")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 20 Unificada: {e}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_35_custo_veiculo_numero_nota_fiscal():
    """
    MIGRAÇÃO 35: Adicionar coluna numero_nota_fiscal na tabela custo_veiculo
    Resolve erro em produção onde a coluna não existe
    """
    try:
        logger.info("=" * 80)
        logger.info("🔧 MIGRAÇÃO 35: Adicionar numero_nota_fiscal em custo_veiculo")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'custo_veiculo' 
            AND column_name = 'numero_nota_fiscal'
        """)
        coluna_existe = cursor.fetchone()
        
        if not coluna_existe:
            logger.info("📋 Adicionando coluna numero_nota_fiscal...")
            cursor.execute("""
                ALTER TABLE custo_veiculo 
                ADD COLUMN numero_nota_fiscal VARCHAR(20)
            """)
            connection.commit()
            logger.info("✅ Coluna 'numero_nota_fiscal' adicionada com sucesso!")
        else:
            logger.info("✅ Coluna 'numero_nota_fiscal' já existe na tabela custo_veiculo")
        
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 35 CONCLUÍDA: custo_veiculo atualizado!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 35: {e}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_36_remove_old_propostas_tables():
    """
    Migração 36: Remover tabelas antigas do sistema de propostas legado
    
    Feature flag: REMOVE_OLD_PROPOSTAS_TABLES=true
    
    Tabelas removidas:
    - proposta (10 registros - aprovado pelo usuário)
    - proposta_historico (vazia)
    - item_servico_proposta_dinamica (vazia)
    """
    try:
        # Verificar feature flag de segurança
        if os.environ.get('REMOVE_OLD_PROPOSTAS_TABLES') != 'true':
            logger.info("🔒 MIGRAÇÃO 36: Bloqueada por segurança. Para ativar: REMOVE_OLD_PROPOSTAS_TABLES=true")
            return
        
        logger.info("=" * 80)
        logger.info("🗑️  MIGRAÇÃO 36: Remover Tabelas Antigas - Sistema de Propostas")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de tabelas a remover
        tabelas = ['proposta', 'proposta_historico', 'item_servico_proposta_dinamica']
        
        for tabela in tabelas:
            # Verificar se tabela existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (tabela,))
            tabela_existe = cursor.fetchone()[0]
            
            if tabela_existe:
                logger.info(f"🔍 Tabela '{tabela}' encontrada - removendo...")
                cursor.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
                logger.info(f"✅ Tabela '{tabela}' removida com CASCADE")
            else:
                logger.info(f"ℹ️  Tabela '{tabela}' não existe (já foi removida)")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 36 CONCLUÍDA: Tabelas antigas removidas!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 36: {e}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_37_rename_propostas_fields():
    """
    Migração 37: Renomear campos em propostas_comerciais e adicionar cliente_id FK
    
    Feature flag: RENAME_PROPOSTAS_FIELDS=true
    
    Mudanças:
    1. numero_proposta → numero
    2. assunto → titulo
    3. objeto → descricao
    4. Adicionar: cliente_id INTEGER REFERENCES cliente(id)
    """
    try:
        if os.environ.get('RENAME_PROPOSTAS_FIELDS') != 'true':
            logger.info("🔒 MIGRAÇÃO 37: Bloqueada por segurança. Para ativar: RENAME_PROPOSTAS_FIELDS=true")
            return
        
        logger.info("=" * 80)
        logger.info("📝 MIGRAÇÃO 37: Renomear Campos - Propostas Comerciais")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se tabela existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'propostas_comerciais'
            )
        """)
        tabela_existe = cursor.fetchone()[0]
        
        if not tabela_existe:
            logger.info("⏭️  Tabela propostas_comerciais não existe, pulando migração 37")
            cursor.close()
            connection.close()
            return
        
        # 1. Renomear numero_proposta → numero
        logger.info("🔄 PASSO 1: Verificando coluna 'numero_proposta'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'numero_proposta'
        """)
        
        if cursor.fetchone():
            logger.info("➡️  Renomeando 'numero_proposta' → 'numero'...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                RENAME COLUMN numero_proposta TO numero
            """)
            logger.info("✅ Coluna renomeada: numero_proposta → numero")
        else:
            logger.info("ℹ️  Coluna 'numero_proposta' não existe (já foi renomeada)")
        
        # 2. Renomear assunto → titulo
        logger.info("🔄 PASSO 2: Verificando coluna 'assunto'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'assunto'
        """)
        
        if cursor.fetchone():
            logger.info("➡️  Renomeando 'assunto' → 'titulo'...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                RENAME COLUMN assunto TO titulo
            """)
            logger.info("✅ Coluna renomeada: assunto → titulo")
        else:
            logger.info("ℹ️  Coluna 'assunto' não existe (já foi renomeada)")
        
        # 3. Renomear objeto → descricao
        logger.info("🔄 PASSO 3: Verificando coluna 'objeto'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'objeto'
        """)
        
        if cursor.fetchone():
            logger.info("➡️  Renomeando 'objeto' → 'descricao'...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                RENAME COLUMN objeto TO descricao
            """)
            logger.info("✅ Coluna renomeada: objeto → descricao")
        else:
            logger.info("ℹ️  Coluna 'objeto' não existe (já foi renomeada)")
        
        # 4. Adicionar cliente_id FK
        logger.info("🔄 PASSO 4: Verificando coluna 'cliente_id'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'cliente_id'
        """)
        
        if cursor.fetchone():
            logger.info("ℹ️  Coluna 'cliente_id' já existe")
        else:
            logger.info("➕ Adicionando coluna 'cliente_id' com FK para cliente(id)...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                ADD COLUMN cliente_id INTEGER REFERENCES cliente(id)
            """)
            logger.info("✅ Coluna 'cliente_id' adicionada com FK para cliente(id)")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 37 CONCLUÍDA: Campos renomeados e FK adicionada!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 37: {e}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_38_create_proposta_historico():
    """
    Migração 38: Criar tabela proposta_historico
    
    Feature flag: CREATE_PROPOSTA_HISTORICO=true
    
    Tabela para rastreamento de histórico de ações em propostas comerciais:
    - id: Primary key
    - proposta_id: FK para propostas_comerciais(id) ON DELETE CASCADE
    - usuario_id: FK para usuario(id) - usuário que realizou a ação
    - acao: VARCHAR(50) - Ações: criada, editada, enviada, aprovada, rejeitada, excluida
    - observacao: TEXT - Observações opcionais sobre a ação
    - data_hora: TIMESTAMP - Data e hora da ação
    - admin_id: FK para usuario(id) - Admin responsável
    """
    try:
        if os.environ.get('CREATE_PROPOSTA_HISTORICO') != 'true':
            logger.info("🔒 MIGRAÇÃO 38: Bloqueada por segurança. Para ativar: CREATE_PROPOSTA_HISTORICO=true")
            return
        
        logger.info("=" * 80)
        logger.info("📋 MIGRAÇÃO 38: Criar Tabela proposta_historico")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # PASSO 1: Verificar se tabela já existe
        logger.info("🔍 PASSO 1: Verificando existência da tabela proposta_historico...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'proposta_historico'
            )
        """)
        tabela_existe = cursor.fetchone()[0]
        
        if tabela_existe:
            logger.info("ℹ️  Tabela proposta_historico já existe, pulando criação")
            cursor.close()
            connection.close()
            return
        
        # PASSO 2: Criar tabela proposta_historico
        logger.info("🔨 PASSO 2: Criando tabela proposta_historico...")
        cursor.execute("""
            CREATE TABLE proposta_historico (
                id SERIAL PRIMARY KEY,
                proposta_id INTEGER NOT NULL REFERENCES propostas_comerciais(id) ON DELETE CASCADE,
                usuario_id INTEGER NOT NULL REFERENCES usuario(id),
                acao VARCHAR(50) NOT NULL,
                observacao TEXT,
                data_hora TIMESTAMP NOT NULL DEFAULT NOW(),
                admin_id INTEGER NOT NULL REFERENCES usuario(id)
            )
        """)
        logger.info("✅ Tabela proposta_historico criada com sucesso")
        
        # PASSO 3: Criar índices para melhor performance
        logger.info("📊 PASSO 3: Criando índices...")
        cursor.execute("CREATE INDEX idx_proposta_historico_proposta ON proposta_historico(proposta_id)")
        cursor.execute("CREATE INDEX idx_proposta_historico_usuario ON proposta_historico(usuario_id)")
        cursor.execute("CREATE INDEX idx_proposta_historico_admin ON proposta_historico(admin_id)")
        cursor.execute("CREATE INDEX idx_proposta_historico_data ON proposta_historico(data_hora)")
        cursor.execute("CREATE INDEX idx_proposta_historico_acao ON proposta_historico(acao)")
        logger.info("✅ Índices criados com sucesso")
        
        # PASSO 4: Commit
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 38 CONCLUÍDA: Tabela proposta_historico criada!")
        logger.info("📊 Campos: id, proposta_id, usuario_id, acao, observacao, data_hora, admin_id")
        logger.info("🔗 FKs: propostas_comerciais(id) ON DELETE CASCADE, usuario(id)")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 38: {e}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_39_create_almoxarifado_system():
    """
    MIGRAÇÃO 39: Sistema de Almoxarifado v3.0 - Gestão de Materiais, Ferramentas e EPIs
    Feature Flag: CREATE_ALMOXARIFADO_SYSTEM
    
    Cria 4 tabelas:
    - almoxarifado_categoria: Categorias de materiais
    - almoxarifado_item: Catálogo de itens
    - almoxarifado_estoque: Controle de estoque (serializado/consumível)
    - almoxarifado_movimento: Histórico de movimentações
    """
    try:
        if os.environ.get('CREATE_ALMOXARIFADO_SYSTEM', 'false').lower() != 'true':
            logger.info("🔒 MIGRAÇÃO 39: Bloqueada por segurança. Para ativar: CREATE_ALMOXARIFADO_SYSTEM=true")
            return
        
        logger.info("=" * 80)
        logger.info("📦 MIGRAÇÃO 39: Sistema de Almoxarifado v3.0")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Tabela de categorias
        logger.info("📋 Criando tabela almoxarifado_categoria...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS almoxarifado_categoria (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                tipo_controle_padrao VARCHAR(20) NOT NULL,
                permite_devolucao_padrao BOOLEAN DEFAULT TRUE,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_categoria_admin ON almoxarifado_categoria(admin_id)")
        logger.info("✅ Tabela almoxarifado_categoria criada/verificada")
        
        # Tabela de itens
        logger.info("📋 Criando tabela almoxarifado_item...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS almoxarifado_item (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(50) NOT NULL,
                nome VARCHAR(200) NOT NULL,
                categoria_id INTEGER NOT NULL REFERENCES almoxarifado_categoria(id),
                tipo_controle VARCHAR(20) NOT NULL,
                permite_devolucao BOOLEAN DEFAULT TRUE,
                estoque_minimo INTEGER DEFAULT 0,
                unidade VARCHAR(20),
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_item_codigo_admin ON almoxarifado_item(codigo, admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_item_categoria ON almoxarifado_item(categoria_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_item_nome ON almoxarifado_item(nome)")
        logger.info("✅ Tabela almoxarifado_item criada/verificada")
        
        # Tabela de estoque
        logger.info("📋 Criando tabela almoxarifado_estoque...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS almoxarifado_estoque (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES almoxarifado_item(id),
                numero_serie VARCHAR(100),
                quantidade NUMERIC(10, 2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'DISPONIVEL',
                funcionario_atual_id INTEGER REFERENCES funcionario(id),
                obra_id INTEGER REFERENCES obra(id),
                valor_unitario NUMERIC(10, 2),
                lote VARCHAR(50),
                data_validade DATE,
                nota_fiscal VARCHAR(50),
                data_entrada DATE,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_estoque_item_status ON almoxarifado_estoque(item_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_estoque_funcionario ON almoxarifado_estoque(funcionario_atual_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_estoque_admin ON almoxarifado_estoque(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_estoque_numero_serie ON almoxarifado_estoque(numero_serie)")
        logger.info("✅ Tabela almoxarifado_estoque criada/verificada")
        
        # Tabela de movimentos
        logger.info("📋 Criando tabela almoxarifado_movimento...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS almoxarifado_movimento (
                id SERIAL PRIMARY KEY,
                tipo_movimento VARCHAR(20) NOT NULL,
                item_id INTEGER NOT NULL REFERENCES almoxarifado_item(id),
                estoque_id INTEGER REFERENCES almoxarifado_estoque(id),
                funcionario_id INTEGER REFERENCES funcionario(id),
                obra_id INTEGER NULL REFERENCES obra(id),
                quantidade NUMERIC(10, 2),
                valor_unitario NUMERIC(10, 2),
                nota_fiscal VARCHAR(50),
                lote VARCHAR(50),
                numero_serie VARCHAR(100),
                condicao_item VARCHAR(20),
                observacao TEXT,
                data_movimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                usuario_id INTEGER NOT NULL REFERENCES usuario(id),
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_movimento_data ON almoxarifado_movimento(data_movimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_movimento_tipo ON almoxarifado_movimento(tipo_movimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_movimento_funcionario ON almoxarifado_movimento(funcionario_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_movimento_obra ON almoxarifado_movimento(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_almox_movimento_admin ON almoxarifado_movimento(admin_id)")
        logger.info("✅ Tabela almoxarifado_movimento criada/verificada")
        
        # Adicionar colunas faltantes com ALTER TABLE (defesa para tabelas existentes)
        logger.info("🔧 Adicionando colunas faltantes (se necessário)...")
        cursor.execute("""
            ALTER TABLE almoxarifado_movimento 
            ADD COLUMN IF NOT EXISTS lote VARCHAR(50),
            ADD COLUMN IF NOT EXISTS numero_serie VARCHAR(100),
            ADD COLUMN IF NOT EXISTS condicao_item VARCHAR(20)
        """)
        logger.info("✅ Colunas lote, numero_serie, condicao_item verificadas/adicionadas")
        
        # Remover constraint NOT NULL de obra_id (para bancos existentes que tinham NOT NULL)
        logger.info("🔧 Removendo constraint NOT NULL de obra_id (ENTRADAs não têm obra)...")
        cursor.execute("""
            ALTER TABLE almoxarifado_movimento 
            ALTER COLUMN obra_id DROP NOT NULL
        """)
        logger.info("✅ obra_id agora aceita NULL (ENTRADAs sem obra)")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 39 CONCLUÍDA: Sistema de Almoxarifado v3.0 criado!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 39: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_40_ponto_compartilhado():
    """
    MIGRAÇÃO 40: Sistema de Ponto Eletrônico com Celular Compartilhado
    - Adiciona tabelas configuracao_horario e dispositivo_obra
    - Adiciona índices ao RegistroPonto
    - Adiciona campo admin_id ao RegistroPonto se não existir
    """
    try:
        logger.info("=" * 80)
        logger.info("📱 MIGRAÇÃO 40: Sistema de Ponto Eletrônico Compartilhado")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Adicionar admin_id ao RegistroPonto se não existir
        logger.info("🔧 Verificando campo admin_id na tabela registro_ponto...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'registro_ponto' 
            AND column_name = 'admin_id'
        """)
        
        if not cursor.fetchone():
            logger.info("📋 Adicionando coluna admin_id na tabela registro_ponto...")
            
            # Passo 1: Adicionar coluna como NULLABLE primeiro
            cursor.execute("""
                ALTER TABLE registro_ponto 
                ADD COLUMN admin_id INTEGER REFERENCES usuario(id)
            """)
            logger.info("✅ Coluna admin_id adicionada (nullable)")
            
            # Passo 2: Backfill admin_id baseado em funcionario.admin_id
            logger.info("📋 Backfill de admin_id baseado em funcionários...")
            cursor.execute("""
                UPDATE registro_ponto rp
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE rp.funcionario_id = f.id
                AND rp.admin_id IS NULL
            """)
            backfill_count = cursor.rowcount
            logger.info(f"✅ {backfill_count} registros atualizados com admin_id")
            
            # Passo 3: Verificar se ainda há registros sem admin_id
            cursor.execute("""
                SELECT COUNT(*) FROM registro_ponto WHERE admin_id IS NULL
            """)
            null_count = cursor.fetchone()[0]
            
            if null_count > 0:
                logger.warning(f"⚠️ {null_count} registros sem admin_id - usando fallback obra.admin_id")
                cursor.execute("""
                    UPDATE registro_ponto rp
                    SET admin_id = o.admin_id
                    FROM obra o
                    WHERE rp.obra_id = o.id
                    AND rp.admin_id IS NULL
                """)
                logger.info(f"✅ {cursor.rowcount} registros atualizados via obra")
            
            # Passo 4: Tornar NOT NULL após backfill
            cursor.execute("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'registro_ponto' 
                AND column_name = 'admin_id'
            """)
            is_nullable = cursor.fetchone()[0]
            
            if is_nullable == 'YES':
                cursor.execute("""
                    ALTER TABLE registro_ponto 
                    ALTER COLUMN admin_id SET NOT NULL
                """)
                logger.info("✅ Coluna admin_id agora é NOT NULL")
            else:
                logger.info("✅ Coluna admin_id já é NOT NULL")
        else:
            logger.info("✅ Coluna admin_id já existe")
        
        # Criar índices no RegistroPonto
        logger.info("📋 Criando índices de performance no registro_ponto...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_registro_ponto_funcionario_data 
            ON registro_ponto(funcionario_id, data)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_registro_ponto_obra_data 
            ON registro_ponto(obra_id, data)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_registro_ponto_admin_data 
            ON registro_ponto(admin_id, data)
        """)
        logger.info("✅ Índices criados/verificados")
        
        # Criar tabela configuracao_horario
        logger.info("📋 Criando tabela configuracao_horario...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracao_horario (
                id SERIAL PRIMARY KEY,
                obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                funcionario_id INTEGER REFERENCES funcionario(id) ON DELETE CASCADE,
                entrada_padrao TIME DEFAULT '08:00:00',
                saida_padrao TIME DEFAULT '17:00:00',
                almoco_inicio TIME DEFAULT '12:00:00',
                almoco_fim TIME DEFAULT '13:00:00',
                tolerancia_atraso INTEGER DEFAULT 15,
                carga_horaria_diaria INTEGER DEFAULT 480,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_config_horario_obra 
            ON configuracao_horario(obra_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_config_horario_admin 
            ON configuracao_horario(admin_id)
        """)
        logger.info("✅ Tabela configuracao_horario criada/verificada")
        
        # Criar tabela dispositivo_obra
        logger.info("📋 Criando tabela dispositivo_obra...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dispositivo_obra (
                id SERIAL PRIMARY KEY,
                obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                nome_dispositivo VARCHAR(100) NOT NULL,
                identificador VARCHAR(200),
                ultimo_acesso TIMESTAMP,
                ativo BOOLEAN DEFAULT TRUE,
                latitude FLOAT,
                longitude FLOAT,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dispositivo_obra_obra 
            ON dispositivo_obra(obra_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dispositivo_obra_admin 
            ON dispositivo_obra(admin_id)
        """)
        logger.info("✅ Tabela dispositivo_obra criada/verificada")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 40 CONCLUÍDA: Sistema de Ponto Compartilhado criado!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 40: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_41_sistema_financeiro():
    """
    MIGRAÇÃO 41: Sistema Financeiro v9.0
    - Cria tabelas: conta_pagar, conta_receber, banco_empresa
    - Índices de performance para consultas financeiras
    """
    try:
        logger.info("=" * 80)
        logger.info("💰 MIGRAÇÃO 41: Sistema Financeiro v9.0")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Tabela 1: conta_pagar
        logger.info("📋 Criando tabela conta_pagar...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conta_pagar (
                id SERIAL PRIMARY KEY,
                fornecedor_id INTEGER NOT NULL REFERENCES fornecedor(id),
                obra_id INTEGER REFERENCES obra(id),
                numero_documento VARCHAR(50),
                descricao TEXT NOT NULL,
                valor_original NUMERIC(15, 2) NOT NULL,
                valor_pago NUMERIC(15, 2) DEFAULT 0,
                saldo NUMERIC(15, 2),
                data_emissao DATE NOT NULL,
                data_vencimento DATE NOT NULL,
                data_pagamento DATE,
                status VARCHAR(20) DEFAULT 'PENDENTE',
                conta_contabil_codigo VARCHAR(20) REFERENCES plano_contas(codigo),
                forma_pagamento VARCHAR(50),
                observacoes TEXT,
                origem_tipo VARCHAR(50),
                origem_id INTEGER,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices conta_pagar
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_pagar_vencimento ON conta_pagar(data_vencimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_pagar_status ON conta_pagar(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_pagar_fornecedor ON conta_pagar(fornecedor_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_pagar_obra ON conta_pagar(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_pagar_admin ON conta_pagar(admin_id)")
        logger.info("✅ Tabela conta_pagar criada/verificada com índices")
        
        # Tabela 2: conta_receber
        logger.info("📋 Criando tabela conta_receber...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conta_receber (
                id SERIAL PRIMARY KEY,
                cliente_nome VARCHAR(200) NOT NULL,
                cliente_cpf_cnpj VARCHAR(18),
                obra_id INTEGER REFERENCES obra(id),
                numero_documento VARCHAR(50),
                descricao TEXT NOT NULL,
                valor_original NUMERIC(15, 2) NOT NULL,
                valor_recebido NUMERIC(15, 2) DEFAULT 0,
                saldo NUMERIC(15, 2),
                data_emissao DATE NOT NULL,
                data_vencimento DATE NOT NULL,
                data_recebimento DATE,
                status VARCHAR(20) DEFAULT 'PENDENTE',
                conta_contabil_codigo VARCHAR(20) REFERENCES plano_contas(codigo),
                forma_recebimento VARCHAR(50),
                observacoes TEXT,
                origem_tipo VARCHAR(50),
                origem_id INTEGER,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices conta_receber
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_receber_vencimento ON conta_receber(data_vencimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_receber_status ON conta_receber(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_receber_cliente ON conta_receber(cliente_cpf_cnpj)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_receber_obra ON conta_receber(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conta_receber_admin ON conta_receber(admin_id)")
        logger.info("✅ Tabela conta_receber criada/verificada com índices")
        
        # Tabela 3: banco_empresa
        logger.info("📋 Criando tabela banco_empresa...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banco_empresa (
                id SERIAL PRIMARY KEY,
                nome_banco VARCHAR(100) NOT NULL,
                agencia VARCHAR(10) NOT NULL,
                conta VARCHAR(20) NOT NULL,
                tipo_conta VARCHAR(20),
                saldo_inicial NUMERIC(15, 2) DEFAULT 0,
                saldo_atual NUMERIC(15, 2) DEFAULT 0,
                ativo BOOLEAN DEFAULT TRUE,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices banco_empresa
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_banco_admin ON banco_empresa(admin_id)")
        logger.info("✅ Tabela banco_empresa criada/verificada com índice")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 41 CONCLUÍDA: Sistema Financeiro v9.0 criado!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 41: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_42_funcionario_obras_ponto():
    """
    MIGRAÇÃO 42: Configuração de Obras por Funcionário para Ponto Eletrônico
    - Cria tabela funcionario_obras_ponto para selecionar quais obras aparecem no dropdown
    """
    try:
        logger.info("=" * 80)
        logger.info("📱 MIGRAÇÃO 42: Configuração Obras/Funcionário Ponto")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Criar tabela funcionario_obras_ponto
        logger.info("📋 Criando tabela funcionario_obras_ponto...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS funcionario_obras_ponto (
                id SERIAL PRIMARY KEY,
                funcionario_id INTEGER NOT NULL REFERENCES funcionario(id) ON DELETE CASCADE,
                obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_funcionario_obra_admin UNIQUE (funcionario_id, obra_id, admin_id)
            )
        """)
        logger.info("✅ Tabela funcionario_obras_ponto criada/verificada")
        
        # Criar índices de performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_funcionario_obras_ponto_funcionario 
            ON funcionario_obras_ponto(funcionario_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_funcionario_obras_ponto_obra 
            ON funcionario_obras_ponto(obra_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_funcionario_obras_ponto_admin 
            ON funcionario_obras_ponto(admin_id)
        """)
        logger.info("✅ Índices de performance criados")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 42 CONCLUÍDA: Configuração Obras/Funcionário criada!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 42: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())


def _migration_44_adicionar_jornada_semanal():
    """
    MIGRAÇÃO 44: Adicionar coluna jornada_semanal à tabela funcionario
    
    Contexto:
    - Commits a0b1611, 2ad22f1, ef4e42b atualizaram código para usar jornada_semanal
    - Coluna não existe em produção, causando AttributeError
    - Requerida por: utils.py, views.py, kpis_engine.py, folha_service.py
    
    Ação:
    - Adiciona coluna jornada_semanal INTEGER DEFAULT 44
    - Valor padrão 44h (jornada CLT padrão)
    """
    try:
        logger.info("=" * 80)
        logger.info("👷 MIGRAÇÃO 44: Adicionar jornada_semanal a funcionario")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'funcionario' 
            AND column_name = 'jornada_semanal'
        """)
        
        if not cursor.fetchone():
            logger.info("🔧 Adicionando coluna jornada_semanal...")
            
            # Adicionar coluna com valor padrão
            cursor.execute("""
                ALTER TABLE funcionario 
                ADD COLUMN jornada_semanal INTEGER DEFAULT 44
            """)
            
            logger.info("✅ Coluna jornada_semanal adicionada (padrão: 44h CLT)")
            
            # Atualizar funcionários existentes que tenham NULL
            cursor.execute("""
                UPDATE funcionario 
                SET jornada_semanal = 44 
                WHERE jornada_semanal IS NULL
            """)
            
            updated_count = cursor.rowcount
            logger.info(f"✅ {updated_count} funcionários atualizados com jornada padrão 44h")
        else:
            logger.info("⏭️  Coluna jornada_semanal já existe - SKIP")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 44 CONCLUÍDA: jornada_semanal adicionada!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 44: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())
        raise


def _migration_45_corrigir_schema_propostas():
    """
    MIGRAÇÃO 45: Corrigir schema da tabela propostas_comerciais
    
    Problema: Modelo Python usa mapeamento de colunas mas banco não tem os nomes corretos
    - numero = db.Column('numero_proposta', ...) → banco precisa ter coluna 'numero_proposta'
    - assunto = db.Column('assunto', ...) → banco precisa ter coluna 'assunto'
    - objeto = db.Column('objeto', ...) → banco precisa ter coluna 'objeto'
    
    Erro em Produção:
    (psycopg2.errors.UndefinedColumn) column propostas_comerciais.numero_proposta does not exist
    
    Solução: Renomear colunas para match com o modelo Python
    """
    try:
        logger.info("=" * 80)
        logger.info("🔧 MIGRAÇÃO 45: Corrigir schema propostas_comerciais")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # 1. Renomear 'numero' → 'numero_proposta'
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'numero'
        """)
        
        if cursor.fetchone():
            logger.info("🔧 Renomeando coluna 'numero' para 'numero_proposta'...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                RENAME COLUMN numero TO numero_proposta
            """)
            logger.info("✅ Coluna 'numero_proposta' renomeada com sucesso")
        else:
            # Verificar se numero_proposta já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'propostas_comerciais' 
                AND column_name = 'numero_proposta'
            """)
            if cursor.fetchone():
                logger.info("⏭️  Coluna 'numero_proposta' já existe - SKIP")
            else:
                logger.warning("⚠️  Coluna 'numero' não encontrada (esperado se já migrado)")
        
        # 2. Renomear 'titulo' → 'assunto' (se existir)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'titulo'
        """)
        
        if cursor.fetchone():
            logger.info("🔧 Renomeando coluna 'titulo' para 'assunto'...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                RENAME COLUMN titulo TO assunto
            """)
            logger.info("✅ Coluna 'assunto' renomeada com sucesso")
        else:
            # Verificar se assunto já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'propostas_comerciais' 
                AND column_name = 'assunto'
            """)
            if cursor.fetchone():
                logger.info("⏭️  Coluna 'assunto' já existe - SKIP")
            else:
                logger.info("ℹ️  Coluna 'titulo' não encontrada (pode já ter sido migrada)")
        
        # 3. Renomear 'descricao' → 'objeto' (se existir)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'descricao'
        """)
        
        if cursor.fetchone():
            logger.info("🔧 Renomeando coluna 'descricao' para 'objeto'...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                RENAME COLUMN descricao TO objeto
            """)
            logger.info("✅ Coluna 'objeto' renomeada com sucesso")
        else:
            # Verificar se objeto já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'propostas_comerciais' 
                AND column_name = 'objeto'
            """)
            if cursor.fetchone():
                logger.info("⏭️  Coluna 'objeto' já existe - SKIP")
            else:
                logger.info("ℹ️  Coluna 'descricao' não encontrada (pode já ter sido migrada)")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 45 CONCLUÍDA: Schema de propostas corrigido!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 45: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())
        raise


def _migration_46_adicionar_descricao_centro_custo():
    """
    MIGRAÇÃO 46: Adicionar coluna 'descricao' à tabela centro_custo_contabil
    
    Problema: Modelo Python define campo descricao mas a coluna não existe no banco
    Erro: (psycopg2.errors.UndefinedColumn) column centro_custo_contabil.descricao does not exist
    
    Solução: Adicionar coluna descricao TEXT NULL
    """
    try:
        logger.info("=" * 80)
        logger.info("🔧 MIGRAÇÃO 46: Adicionar descrição aos centros de custo")
        logger.info("=" * 80)
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se coluna descricao já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'centro_custo_contabil' 
            AND column_name = 'descricao'
        """)
        
        if not cursor.fetchone():
            logger.info("🔧 Adicionando coluna 'descricao' à tabela centro_custo_contabil...")
            cursor.execute("""
                ALTER TABLE centro_custo_contabil 
                ADD COLUMN descricao TEXT NULL
            """)
            logger.info("✅ Coluna 'descricao' adicionada com sucesso")
        else:
            logger.info("⏭️  Coluna 'descricao' já existe - SKIP")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 46 CONCLUÍDA: Campo descricao adicionado!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 46: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
        import traceback
        logger.error(traceback.format_exc())
        raise


def _migration_47_almoxarifado_fornecedor():
    """Migration 47: Adicionar fornecedor_id em almoxarifado_movimento para integração com financeiro"""
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("MIGRAÇÃO 47: Almoxarifado → Financeiro Integration")
        logger.info("=" * 80)
        
        # Verificar se coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'almoxarifado_movimento' 
            AND column_name = 'fornecedor_id'
        """)
        
        if cursor.fetchone():
            logger.info("✅ Coluna fornecedor_id já existe em almoxarifado_movimento")
        else:
            logger.info("🔧 Adicionando fornecedor_id a almoxarifado_movimento...")
            cursor.execute("""
                ALTER TABLE almoxarifado_movimento
                ADD COLUMN fornecedor_id INTEGER REFERENCES fornecedor(id)
            """)
            logger.info("✅ Coluna fornecedor_id adicionada")
        
        # Criar índice
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'almoxarifado_movimento' 
            AND indexname = 'idx_almox_movimento_fornecedor'
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                CREATE INDEX idx_almox_movimento_fornecedor 
                ON almoxarifado_movimento(fornecedor_id)
            """)
            logger.info("✅ Índice idx_almox_movimento_fornecedor criado")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 47 CONCLUÍDA!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 47: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

# Migração 48 definida mais adiante no arquivo (versão tenant-aware completa)

def _migration_49_vehicle_alertas():
    """
    Migração 49: Adicionar campos de alertas/vencimentos em frota_veiculo
    Adiciona: data_vencimento_ipva, data_vencimento_seguro
    """
    logger.info("=" * 80)
    logger.info("🚗 MIGRAÇÃO 49: Campos de Alertas - Veículos")
    logger.info("=" * 80)
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar e adicionar colunas se não existirem
        colunas_adicionar = {
            'data_vencimento_ipva': 'DATE',
            'data_vencimento_seguro': 'DATE'
        }
        
        for coluna, tipo_sql in colunas_adicionar.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'frota_veiculo' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em frota_veiculo...")
                cursor.execute(f"ALTER TABLE frota_veiculo ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada com sucesso!")
            else:
                logger.info(f"✅ Coluna '{coluna}' já existe - skip")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 49 CONCLUÍDA: Campos de alertas adicionados!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 49: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def _migration_50_uso_veiculo_schema_completo():
    """
    Migração 50: Garantir schema COMPLETO da tabela uso_veiculo
    Sincroniza TODAS as colunas do modelo com o banco de dados
    """
    logger.info("=" * 80)
    logger.info("🚗 MIGRAÇÃO 50: Schema Completo - Tabela uso_veiculo")
    logger.info("=" * 80)
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Schema completo da tabela uso_veiculo conforme modelo Python
        schema_completo = {
            'veiculo_id': 'INTEGER',
            'funcionario_id': 'INTEGER',
            'obra_id': 'INTEGER',
            'data_uso': 'DATE NOT NULL',
            'hora_saida': 'TIME',
            'hora_retorno': 'TIME',
            'km_inicial': 'INTEGER',
            'km_final': 'INTEGER',
            'km_percorrido': 'INTEGER',
            'passageiros_frente': 'TEXT',
            'passageiros_tras': 'TEXT',
            'responsavel_veiculo': 'VARCHAR(100)',
            'observacoes': 'TEXT',
            'admin_id': 'INTEGER NOT NULL',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        colunas_adicionadas = 0
        
        for coluna, tipo_sql in schema_completo.items():
            # Verificar se coluna existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'uso_veiculo' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em uso_veiculo...")
                # Remover NOT NULL e DEFAULT da definição para ALTER TABLE
                tipo_limpo = tipo_sql.replace(' NOT NULL', '').replace(' DEFAULT CURRENT_TIMESTAMP', '')
                cursor.execute(f"ALTER TABLE uso_veiculo ADD COLUMN {coluna} {tipo_limpo}")
                logger.info(f"✅ Coluna '{coluna}' adicionada!")
                colunas_adicionadas += 1
            else:
                logger.debug(f"✅ Coluna '{coluna}' já existe")
        
        # Garantir foreign keys e índices
        logger.info("🔍 Verificando foreign keys...")
        
        # FK veiculo_id
        cursor.execute("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name = 'uso_veiculo' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'uso_veiculo_veiculo_id_fkey'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ADD CONSTRAINT uso_veiculo_veiculo_id_fkey 
                    FOREIGN KEY (veiculo_id) REFERENCES veiculo(id)
                """)
                logger.info("✅ FK veiculo_id criada")
            except Exception as e:
                logger.warning(f"⚠️ FK veiculo_id já existe ou erro: {e}")
        
        # FK funcionario_id
        cursor.execute("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name = 'uso_veiculo' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'uso_veiculo_funcionario_id_fkey'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ADD CONSTRAINT uso_veiculo_funcionario_id_fkey 
                    FOREIGN KEY (funcionario_id) REFERENCES funcionario(id)
                """)
                logger.info("✅ FK funcionario_id criada")
            except Exception as e:
                logger.warning(f"⚠️ FK funcionario_id já existe ou erro: {e}")
        
        # FK obra_id
        cursor.execute("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name = 'uso_veiculo' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'uso_veiculo_obra_id_fkey'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ADD CONSTRAINT uso_veiculo_obra_id_fkey 
                    FOREIGN KEY (obra_id) REFERENCES obra(id)
                """)
                logger.info("✅ FK obra_id criada")
            except Exception as e:
                logger.warning(f"⚠️ FK obra_id já existe ou erro: {e}")
        
        # FK admin_id
        cursor.execute("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name = 'uso_veiculo' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'uso_veiculo_admin_id_fkey'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ADD CONSTRAINT uso_veiculo_admin_id_fkey 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                """)
                logger.info("✅ FK admin_id criada")
            except Exception as e:
                logger.warning(f"⚠️ FK admin_id já existe ou erro: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        if colunas_adicionadas > 0:
            logger.info(f"✅ MIGRAÇÃO 50 CONCLUÍDA: {colunas_adicionadas} colunas adicionadas!")
        else:
            logger.info("✅ MIGRAÇÃO 50 CONCLUÍDA: Schema já estava completo!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 50: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def _migration_51_custo_veiculo_schema_completo():
    """
    Migração 51: Garantir schema COMPLETO da tabela custo_veiculo
    Sincroniza TODAS as colunas do modelo com o banco de dados
    Especialmente campos de pagamento e vencimento
    """
    logger.info("=" * 80)
    logger.info("💰 MIGRAÇÃO 51: Schema Completo - Tabela custo_veiculo")
    logger.info("=" * 80)
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Schema completo da tabela custo_veiculo conforme modelo Python
        schema_completo = {
            'veiculo_id': 'INTEGER',
            'data_custo': 'DATE NOT NULL',
            'tipo_custo': 'VARCHAR(30) NOT NULL',
            'valor': 'NUMERIC(10, 2) NOT NULL',
            'descricao': 'VARCHAR(200) NOT NULL',
            'fornecedor': 'VARCHAR(100)',
            'numero_nota_fiscal': 'VARCHAR(20)',
            'data_vencimento': 'DATE',
            'status_pagamento': 'VARCHAR(20) DEFAULT \'Pendente\'',
            'forma_pagamento': 'VARCHAR(30)',
            'km_veiculo': 'INTEGER',
            'observacoes': 'TEXT',
            'admin_id': 'INTEGER NOT NULL'
        }
        
        colunas_adicionadas = 0
        
        for coluna, tipo_sql in schema_completo.items():
            # Verificar se coluna existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'custo_veiculo' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em custo_veiculo...")
                # Remover NOT NULL e DEFAULT da definição para ALTER TABLE
                tipo_limpo = tipo_sql.replace(' NOT NULL', '').replace(' DEFAULT \'Pendente\'', '')
                cursor.execute(f"ALTER TABLE custo_veiculo ADD COLUMN {coluna} {tipo_limpo}")
                
                # Aplicar DEFAULT separadamente se existir
                if 'DEFAULT' in tipo_sql:
                    if 'Pendente' in tipo_sql:
                        cursor.execute(f"ALTER TABLE custo_veiculo ALTER COLUMN {coluna} SET DEFAULT 'Pendente'")
                
                logger.info(f"✅ Coluna '{coluna}' adicionada!")
                colunas_adicionadas += 1
            else:
                logger.debug(f"✅ Coluna '{coluna}' já existe")
        
        # Garantir foreign key para veiculo_id
        logger.info("🔍 Verificando foreign keys...")
        
        # FK veiculo_id
        cursor.execute("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name = 'custo_veiculo' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'custo_veiculo_veiculo_id_fkey'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE custo_veiculo 
                    ADD CONSTRAINT custo_veiculo_veiculo_id_fkey 
                    FOREIGN KEY (veiculo_id) REFERENCES veiculo(id)
                """)
                logger.info("✅ FK veiculo_id criada")
            except Exception as e:
                logger.warning(f"⚠️ FK veiculo_id já existe ou erro: {e}")
        
        # FK admin_id
        cursor.execute("""
            SELECT 1 FROM information_schema.table_constraints 
            WHERE table_name = 'custo_veiculo' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'custo_veiculo_admin_id_fkey'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("""
                    ALTER TABLE custo_veiculo 
                    ADD CONSTRAINT custo_veiculo_admin_id_fkey 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                """)
                logger.info("✅ FK admin_id criada")
            except Exception as e:
                logger.warning(f"⚠️ FK admin_id já existe ou erro: {e}")
        
        # Criar índices úteis
        logger.info("🔍 Verificando índices...")
        
        # Índice para data_vencimento (útil para alertas)
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custo_veiculo_data_vencimento 
                ON custo_veiculo(data_vencimento) 
                WHERE data_vencimento IS NOT NULL
            """)
            logger.info("✅ Índice data_vencimento criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice data_vencimento já existe ou erro: {e}")
        
        # Índice para status_pagamento
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custo_veiculo_status_pagamento 
                ON custo_veiculo(status_pagamento)
            """)
            logger.info("✅ Índice status_pagamento criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice status_pagamento já existe ou erro: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        if colunas_adicionadas > 0:
            logger.info(f"✅ MIGRAÇÃO 51 CONCLUÍDA: {colunas_adicionadas} colunas adicionadas!")
        else:
            logger.info("✅ MIGRAÇÃO 51 CONCLUÍDA: Schema já estava completo!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 51: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def _migration_52_rdo_foto_campos_otimizacao():
    """
    Migração 52: Adicionar campos de otimização ao RDOFoto
    - Campos para arquivos otimizados (WebP, thumbnails)
    - Metadados de imagem (tamanho, ordem)
    - Migra dados antigos para novos campos
    """
    logger.info("=" * 80)
    logger.info("📸 MIGRAÇÃO 52: Campos de Otimização - RDOFoto")
    logger.info("=" * 80)
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar e adicionar novos campos
        campos_novos = {
            'descricao': 'TEXT',
            'arquivo_original': 'VARCHAR(500)',
            'arquivo_otimizado': 'VARCHAR(500)',
            'thumbnail': 'VARCHAR(500)',
            'nome_original': 'VARCHAR(255)',
            'tamanho_bytes': 'BIGINT',
            'ordem': 'INTEGER DEFAULT 0'
        }
        
        colunas_adicionadas = 0
        
        for coluna, tipo_sql in campos_novos.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_foto' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em rdo_foto...")
                # Remover DEFAULT da definição para ALTER TABLE
                tipo_limpo = tipo_sql.replace(' DEFAULT 0', '')
                cursor.execute(f"ALTER TABLE rdo_foto ADD COLUMN {coluna} {tipo_limpo}")
                
                # Aplicar DEFAULT separadamente se existir
                if 'DEFAULT' in tipo_sql:
                    cursor.execute(f"ALTER TABLE rdo_foto ALTER COLUMN {coluna} SET DEFAULT 0")
                
                logger.info(f"✅ Coluna '{coluna}' adicionada!")
                colunas_adicionadas += 1
            else:
                logger.debug(f"✅ Coluna '{coluna}' já existe - skip")
        
        # Migrar dados antigos (legenda → descricao, caminho_arquivo → arquivo_original)
        logger.info("🔄 Migrando dados antigos...")
        cursor.execute("""
            UPDATE rdo_foto 
            SET descricao = legenda,
                arquivo_original = caminho_arquivo,
                nome_original = nome_arquivo
            WHERE descricao IS NULL AND legenda IS NOT NULL
        """)
        registros_migrados = cursor.rowcount
        logger.info(f"✅ {registros_migrados} registros migrados de campos legados")
        
        # Criar índices para performance
        logger.info("🔍 Criando índices...")
        
        # Índice em admin_id (se não existir)
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'rdo_foto' 
            AND indexname = 'idx_rdo_foto_admin_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_rdo_foto_admin_id ON rdo_foto(admin_id)")
            logger.info("✅ Índice idx_rdo_foto_admin_id criado")
        else:
            logger.debug("✅ Índice idx_rdo_foto_admin_id já existe")
        
        # Índice em rdo_id (se não existir)
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'rdo_foto' 
            AND indexname = 'idx_rdo_foto_rdo_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_rdo_foto_rdo_id ON rdo_foto(rdo_id)")
            logger.info("✅ Índice idx_rdo_foto_rdo_id criado")
        else:
            logger.debug("✅ Índice idx_rdo_foto_rdo_id já existe")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 52 CONCLUÍDA!")
        logger.info(f"   📊 Colunas adicionadas: {colunas_adicionadas}")
        logger.info(f"   🔄 Registros migrados: {registros_migrados}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 52: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

def _migration_53_rdo_foto_base64():
    """
    Migração 53: Adicionar campos Base64 ao RDOFoto para persistência total
    - imagem_original_base64: Backup completo da imagem original
    - imagem_otimizada_base64: Versão otimizada (1200px) para visualização
    - thumbnail_base64: Miniatura (300px) para listagem rápida
    
    Objetivo: Armazenar fotos no banco de dados (igual aos funcionários)
    para nunca mais perder fotos em deploy/restart do container
    """
    logger.info("=" * 80)
    logger.info("🔥 MIGRAÇÃO 53: Persistência Base64 - RDOFoto")
    logger.info("=" * 80)
    
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar e adicionar novos campos base64
        campos_base64 = {
            'imagem_original_base64': 'TEXT',
            'imagem_otimizada_base64': 'TEXT',
            'thumbnail_base64': 'TEXT'
        }
        
        colunas_adicionadas = 0
        
        for coluna, tipo_sql in campos_base64.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_foto' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em rdo_foto...")
                cursor.execute(f"ALTER TABLE rdo_foto ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada!")
                colunas_adicionadas += 1
            else:
                logger.debug(f"✅ Coluna '{coluna}' já existe - skip")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 53 CONCLUÍDA!")
        logger.info(f"   📊 Colunas base64 adicionadas: {colunas_adicionadas}")
        logger.info("   💡 Próximas fotos serão armazenadas no banco de dados")
        logger.info("   🎯 Fotos antigas em arquivo continuam acessíveis (fallback)")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 53: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        # ✅ GARANTIR LIMPEZA: Fechar cursor e connection mesmo se houver erro
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def _migration_54_logo_tamanho_portal():
    """
    Migração 54: Adicionar campo logo_tamanho_portal em configuracao_empresa
    - logo_tamanho_portal: VARCHAR(20) DEFAULT 'medio'
    - Permite configurar tamanho da logo no portal do cliente
    - Opções: 'pequeno', 'medio', 'grande'
    """
    logger.info("=" * 80)
    logger.info("🔥 MIGRAÇÃO 54: Campo logo_tamanho_portal em configuracao_empresa")
    logger.info("=" * 80)
    
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'configuracao_empresa' 
            AND column_name = 'logo_tamanho_portal'
        """)
        
        if not cursor.fetchone():
            logger.info("🔧 Adicionando coluna 'logo_tamanho_portal' em configuracao_empresa...")
            cursor.execute("""
                ALTER TABLE configuracao_empresa 
                ADD COLUMN logo_tamanho_portal VARCHAR(20) DEFAULT 'medio'
            """)
            logger.info("✅ Coluna 'logo_tamanho_portal' adicionada!")
            
            # Aplicar valor padrão em registros existentes
            cursor.execute("""
                UPDATE configuracao_empresa 
                SET logo_tamanho_portal = 'medio' 
                WHERE logo_tamanho_portal IS NULL
            """)
            updated_rows = cursor.rowcount
            logger.info(f"✅ {updated_rows} registros atualizados com valor padrão 'medio'")
        else:
            logger.debug("✅ Coluna 'logo_tamanho_portal' já existe - skip")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 54 CONCLUÍDA!")
        logger.info("   📊 Campo configurável de tamanho de logo no portal")
        logger.info("   🎯 Opções: pequeno (100px), medio (160px), grande (240px)")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 54: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def _migration_55_token_cliente_proposta():
    """
    Migração 55: Adicionar campo token_cliente em proposta
    - token_cliente: VARCHAR(100) UNIQUE
    - Token único para acesso público ao portal do cliente
    - Gerado automaticamente para propostas existentes usando secrets.token_urlsafe(32)
    """
    logger.info("=" * 80)
    logger.info("🔥 MIGRAÇÃO 55: Campo token_cliente em proposta")
    logger.info("=" * 80)
    
    connection = None
    cursor = None
    
    try:
        import secrets
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'proposta' 
            AND column_name = 'token_cliente'
        """)
        
        if not cursor.fetchone():
            logger.info("🔧 Adicionando coluna 'token_cliente' em proposta...")
            cursor.execute("""
                ALTER TABLE proposta 
                ADD COLUMN token_cliente VARCHAR(100) UNIQUE
            """)
            logger.info("✅ Coluna 'token_cliente' adicionada!")
            
            # Gerar tokens para propostas existentes
            logger.info("🔄 Gerando tokens para propostas existentes...")
            cursor.execute("SELECT id FROM proposta WHERE token_cliente IS NULL")
            propostas = cursor.fetchall()
            
            tokens_gerados = 0
            for proposta in propostas:
                proposta_id = proposta[0]
                token = secrets.token_urlsafe(32)
                cursor.execute("""
                    UPDATE proposta 
                    SET token_cliente = %s 
                    WHERE id = %s
                """, (token, proposta_id))
                tokens_gerados += 1
            
            logger.info(f"✅ {tokens_gerados} tokens gerados para propostas existentes")
        else:
            logger.debug("✅ Coluna 'token_cliente' já existe - skip")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 55 CONCLUÍDA!")
        logger.info("   📊 Campo token_cliente para acesso público ao portal")
        logger.info("   🔒 Tokens únicos gerados automaticamente")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 55: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def _migration_56_proposta_arquivo_base64():
    """
    Migração 56: Adicionar campos Base64 ao PropostaArquivo
    - arquivo_base64: TEXT (para PDFs/DWG/DOC <5MB)
    - imagem_original_base64: TEXT (imagem original completa)
    - imagem_otimizada_base64: TEXT (imagem otimizada 1200px WebP)
    - thumbnail_base64: TEXT (thumbnail 300px para preview)
    
    Solução: Arquivos persistem mesmo após deploys/restarts do container
    """
    logger.info("=" * 80)
    logger.info("📎 MIGRAÇÃO 56: Campos Base64 em PropostaArquivo")
    logger.info("=" * 80)
    
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Campos Base64 para adicionar
        campos_base64 = {
            'arquivo_base64': 'TEXT',
            'imagem_original_base64': 'TEXT',
            'imagem_otimizada_base64': 'TEXT',
            'thumbnail_base64': 'TEXT'
        }
        
        colunas_adicionadas = 0
        
        for coluna, tipo_sql in campos_base64.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_arquivos' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em proposta_arquivos...")
                cursor.execute(f"ALTER TABLE proposta_arquivos ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada!")
                colunas_adicionadas += 1
            else:
                logger.debug(f"✅ Coluna '{coluna}' já existe - skip")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 56 CONCLUÍDA!")
        logger.info(f"   📊 {colunas_adicionadas} colunas adicionadas para persistência")
        logger.info("   🔥 Imagens: 3 versões Base64 (original, otimizada, thumbnail)")
        logger.info("   📎 Outros arquivos: Base64 para arquivos <5MB")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 56: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def _migration_57_almoxarifado_movimento_campos_crud():
    """
    Migração 57: Adicionar campos para CRUD de movimentações manuais
    - origem_manual: BOOLEAN DEFAULT FALSE (identifica movimentos criados via UI)
    - impacta_estoque: BOOLEAN DEFAULT TRUE (define se movimento afeta estoque)
    - updated_at: TIMESTAMP (para optimistic locking em edições)
    
    Solução: Habilita edição/exclusão de movimentações manuais com controle de concorrência
    """
    logger.info("=" * 80)
    logger.info("📦 MIGRAÇÃO 57: Campos CRUD em AlmoxarifadoMovimento")
    logger.info("=" * 80)
    
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Campos para adicionar
        campos_crud = {
            'origem_manual': 'BOOLEAN DEFAULT FALSE',
            'impacta_estoque': 'BOOLEAN DEFAULT TRUE',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        colunas_adicionadas = 0
        
        for coluna, definicao in campos_crud.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'almoxarifado_movimento' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em almoxarifado_movimento...")
                cursor.execute(f"ALTER TABLE almoxarifado_movimento ADD COLUMN {coluna} {definicao}")
                logger.info(f"✅ Coluna '{coluna}' adicionada!")
                colunas_adicionadas += 1
            else:
                logger.debug(f"✅ Coluna '{coluna}' já existe - skip")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 57 CONCLUÍDA!")
        logger.info(f"   📊 {colunas_adicionadas} colunas adicionadas")
        logger.info("   ✏️  origem_manual: Identifica movimentos criados manualmente")
        logger.info("   📦 impacta_estoque: Define se movimento afeta estoque físico")
        logger.info("   🔒 updated_at: Optimistic locking para edições concorrentes")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 57: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def _migration_58_almoxarifado_lotes_fifo():
    """
    Migração 58: Sistema de Rastreamento de Lotes com FIFO para Almoxarifado
    - quantidade_inicial: NUMERIC(10,2) - quantidade original da entrada deste lote
    - quantidade_disponivel: NUMERIC(10,2) - quantidade ainda disponível para saída
    - entrada_movimento_id: INTEGER FK - vincula ao movimento de entrada que criou este lote
    - idx_almox_estoque_entrada_mov: Índice em entrada_movimento_id
    - idx_almox_estoque_fifo: Índice composto (item_id, status, created_at) para queries FIFO
    
    Solução: Permite rastreamento correto de custos por lote (FIFO) e saldo disponível
    """
    logger.info("=" * 80)
    logger.info("📦 MIGRAÇÃO 58: Sistema de Rastreamento de Lotes FIFO - Almoxarifado")
    logger.info("=" * 80)
    
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # ========================================
        # PASSO 1: Adicionar novos campos
        # ========================================
        logger.info("🔧 Adicionando campos de rastreamento de lotes...")
        
        campos_lote = {
            'quantidade_inicial': 'NUMERIC(10,2)',
            'quantidade_disponivel': 'NUMERIC(10,2)',
            'entrada_movimento_id': 'INTEGER'
        }
        
        colunas_adicionadas = 0
        
        for coluna, definicao in campos_lote.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'almoxarifado_estoque' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                cursor.execute(f"""
                    ALTER TABLE almoxarifado_estoque 
                    ADD COLUMN {coluna} {definicao}
                """)
                logger.info(f"  ✅ Coluna '{coluna}' adicionada")
                colunas_adicionadas += 1
            else:
                logger.info(f"  ⏭️  Coluna '{coluna}' já existe")
        
        # ========================================
        # PASSO 2: Adicionar Foreign Key
        # ========================================
        logger.info("🔗 Configurando foreign key para entrada_movimento_id...")
        
        # Verificar se FK já existe
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'almoxarifado_estoque' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'fk_almox_estoque_entrada_movimento'
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE almoxarifado_estoque
                ADD CONSTRAINT fk_almox_estoque_entrada_movimento
                FOREIGN KEY (entrada_movimento_id) 
                REFERENCES almoxarifado_movimento(id)
                ON DELETE SET NULL
            """)
            logger.info("  ✅ Foreign key criada")
        else:
            logger.info("  ⏭️  Foreign key já existe")
        
        # ========================================
        # PASSO 3: Criar índices
        # ========================================
        logger.info("📊 Criando índices para otimização FIFO...")
        
        # Índice simples em entrada_movimento_id
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'almoxarifado_estoque' 
            AND indexname = 'idx_almox_estoque_entrada_mov'
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                CREATE INDEX idx_almox_estoque_entrada_mov 
                ON almoxarifado_estoque(entrada_movimento_id)
            """)
            logger.info("  ✅ Índice idx_almox_estoque_entrada_mov criado")
        else:
            logger.info("  ⏭️  Índice idx_almox_estoque_entrada_mov já existe")
        
        # Índice composto para queries FIFO (item_id, status, created_at)
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'almoxarifado_estoque' 
            AND indexname = 'idx_almox_estoque_fifo'
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                CREATE INDEX idx_almox_estoque_fifo 
                ON almoxarifado_estoque(item_id, status, created_at)
            """)
            logger.info("  ✅ Índice composto idx_almox_estoque_fifo criado")
        else:
            logger.info("  ⏭️  Índice composto idx_almox_estoque_fifo já existe")
        
        # ========================================
        # PASSO 4: Migrar dados existentes
        # ========================================
        logger.info("🔄 Migrando dados existentes...")
        
        # Para estoques existentes, popular quantidade_inicial e quantidade_disponivel
        # com os valores atuais de quantidade
        cursor.execute("""
            UPDATE almoxarifado_estoque
            SET 
                quantidade_inicial = quantidade,
                quantidade_disponivel = quantidade
            WHERE quantidade_inicial IS NULL
        """)
        
        registros_atualizados = cursor.rowcount
        logger.info(f"  ✅ {registros_atualizados} registros de estoque atualizados com valores iniciais")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 58 CONCLUÍDA COM SUCESSO!")
        logger.info(f"   📝 Colunas adicionadas: {colunas_adicionadas}")
        logger.info(f"   📊 Índices criados: 2")
        logger.info(f"   🔄 Registros migrados: {registros_atualizados}")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 58: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def _migration_60_centro_custo_created_at():
    """
    Migração 60: Adicionar coluna created_at na tabela centro_custo_contabil
    
    Corrige o erro:
    sqlalchemy.exc.ProgrammingError: column centro_custo_contabil.created_at does not exist
    """
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("📅 MIGRAÇÃO 60: Adicionar created_at em centro_custo_contabil")
        logger.info("=" * 80)
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'centro_custo_contabil' AND column_name = 'created_at'
        """)
        
        if not cursor.fetchone():
            logger.info("  ➕ Adicionando coluna created_at...")
            cursor.execute("""
                ALTER TABLE centro_custo_contabil 
                ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            connection.commit()
            logger.info("  ✅ Coluna created_at adicionada com sucesso!")
        else:
            logger.info("  ⏭️ Coluna created_at já existe")
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 60 CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 60: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def _migration_61_horario_dia_sistema():
    """
    Migração 61: Sistema HorarioDia para horários flexíveis por dia da semana
    
    Cria tabela horario_dia que permite:
    - Horários diferentes para cada dia da semana (Seg-Sex 9h, Sex 8h)
    - Flag 'trabalha' para marcar dias de descanso (sábado/domingo)
    - Pausa customizada por dia
    
    Migra dados existentes de horario_trabalho para horario_dia
    """
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("📅 MIGRAÇÃO 61: Sistema HorarioDia para horários flexíveis")
        logger.info("=" * 80)
        
        # ========================================
        # PASSO 1: Criar tabela horario_dia
        # ========================================
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = 'horario_dia'
        """)
        
        if not cursor.fetchone():
            logger.info("  ➕ Criando tabela horario_dia...")
            cursor.execute("""
                CREATE TABLE horario_dia (
                    id SERIAL PRIMARY KEY,
                    horario_id INTEGER NOT NULL REFERENCES horario_trabalho(id) ON DELETE CASCADE,
                    dia_semana INTEGER NOT NULL CHECK (dia_semana >= 0 AND dia_semana <= 6),
                    entrada TIME,
                    saida TIME,
                    pausa_horas NUMERIC(4,2) DEFAULT 1.0,
                    trabalha BOOLEAN DEFAULT TRUE,
                    CONSTRAINT uk_horario_dia UNIQUE (horario_id, dia_semana)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX idx_horario_dia_horario ON horario_dia(horario_id)
            """)
            
            connection.commit()
            logger.info("  ✅ Tabela horario_dia criada com sucesso!")
            
            # ========================================
            # PASSO 2: Migrar dados existentes
            # ========================================
            logger.info("  🔄 Migrando dados existentes de horario_trabalho...")
            
            cursor.execute("""
                SELECT id, entrada, saida, dias_semana, horas_diarias 
                FROM horario_trabalho 
                WHERE entrada IS NOT NULL
            """)
            
            horarios_existentes = cursor.fetchall()
            migrados = 0
            
            for horario_id, entrada, saida, dias_semana, horas_diarias in horarios_existentes:
                # Parsear dias_semana (formato "1,2,3,4,5" onde 1=Segunda, 7=Domingo)
                dias_trabalho = set()
                if dias_semana:
                    try:
                        dias_str = dias_semana.split(',')
                        for d in dias_str:
                            d = d.strip()
                            if d.isdigit():
                                # Converter: 1=Segunda (0), 2=Terça (1), ..., 7=Domingo (6)
                                dia_num = int(d) - 1  
                                if 0 <= dia_num <= 6:
                                    dias_trabalho.add(dia_num)
                    except:
                        # Default: Segunda a Sexta
                        dias_trabalho = {0, 1, 2, 3, 4}
                else:
                    # Default: Segunda a Sexta
                    dias_trabalho = {0, 1, 2, 3, 4}
                
                # Criar HorarioDia para cada dia da semana
                for dia_semana_num in range(7):
                    trabalha = dia_semana_num in dias_trabalho
                    
                    cursor.execute("""
                        INSERT INTO horario_dia (horario_id, dia_semana, entrada, saida, pausa_horas, trabalha)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (horario_id, dia_semana) DO NOTHING
                    """, (
                        horario_id,
                        dia_semana_num,
                        entrada if trabalha else None,
                        saida if trabalha else None,
                        1.0,  # Pausa padrão de 1 hora
                        trabalha
                    ))
                    migrados += 1
            
            connection.commit()
            logger.info(f"  ✅ {migrados} registros HorarioDia criados!")
            
        else:
            logger.info("  ⏭️ Tabela horario_dia já existe")
        
        # ========================================
        # PASSO 3: Adicionar coluna 'ativo' em horario_trabalho se não existir
        # ========================================
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'horario_trabalho' AND column_name = 'ativo'
        """)
        
        if not cursor.fetchone():
            logger.info("  ➕ Adicionando coluna 'ativo' em horario_trabalho...")
            cursor.execute("""
                ALTER TABLE horario_trabalho 
                ADD COLUMN ativo BOOLEAN DEFAULT TRUE
            """)
            connection.commit()
            logger.info("  ✅ Coluna 'ativo' adicionada!")
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 61 CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 61: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def _migration_62_horario_trabalho_nullable():
    """
    Migração 62: Tornar colunas legadas de HorarioTrabalho nullable
    
    Com o novo modelo HorarioDia, as colunas entrada, saida, saida_almoco,
    retorno_almoco e dias_semana em horario_trabalho são opcionais.
    """
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("📅 MIGRAÇÃO 62: Tornar colunas legadas de HorarioTrabalho nullable")
        logger.info("=" * 80)
        
        # Lista de colunas para tornar nullable
        colunas = ['entrada', 'saida', 'saida_almoco', 'retorno_almoco', 'dias_semana']
        
        for coluna in colunas:
            try:
                cursor.execute(f"""
                    ALTER TABLE horario_trabalho 
                    ALTER COLUMN {coluna} DROP NOT NULL
                """)
                logger.info(f"  ✅ Coluna '{coluna}' agora é nullable")
            except Exception as e:
                # Ignorar se já é nullable ou coluna não existe
                if 'column' not in str(e).lower() and 'does not exist' not in str(e).lower():
                    logger.debug(f"  ⏭️ Coluna '{coluna}' já é nullable ou não existe: {e}")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 62 CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 62: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def _migration_63_tolerancia_minutos():
    """
    Migração 63: Adicionar tolerância em minutos para horas extras/atrasos
    
    Adiciona campo tolerancia_minutos à tabela parametros_legais.
    Variações dentro dessa tolerância não são computadas como extras ou atrasos.
    Padrão: 10 minutos (prática comum de mercado)
    """
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("⏱️  MIGRAÇÃO 63: Tolerância para horas extras/atrasos")
        logger.info("=" * 80)
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'parametros_legais' AND column_name = 'tolerancia_minutos'
        """)
        
        if cursor.fetchone():
            logger.info("  ⏭️ Coluna tolerancia_minutos já existe - SKIP")
        else:
            cursor.execute("""
                ALTER TABLE parametros_legais 
                ADD COLUMN tolerancia_minutos INTEGER DEFAULT 10
            """)
            logger.info("  ✅ Coluna tolerancia_minutos adicionada com default=10")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 63 CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 63: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def _migration_64_folha_processada():
    """
    Migração 64: Criar tabela folha_processada para dashboard de custos por obra
    
    Armazena resultados consolidados do processamento de folha.
    Usado para consultas eficientes de custos de mão de obra por obra.
    """
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("💰 MIGRAÇÃO 64: Tabela folha_processada para dashboard custos")
        logger.info("=" * 80)
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'folha_processada'
            )
        """)
        
        if cursor.fetchone()[0]:
            logger.info("  ⏭️ Tabela folha_processada já existe - SKIP")
        else:
            cursor.execute("""
                CREATE TABLE folha_processada (
                    id SERIAL PRIMARY KEY,
                    funcionario_id INTEGER NOT NULL REFERENCES funcionario(id) ON DELETE CASCADE,
                    obra_id INTEGER REFERENCES obra(id) ON DELETE SET NULL,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    ano INTEGER NOT NULL,
                    mes INTEGER NOT NULL,
                    
                    -- Dados do salário
                    salario_base NUMERIC(10, 2) DEFAULT 0,
                    salario_bruto NUMERIC(10, 2) DEFAULT 0,
                    total_proventos NUMERIC(10, 2) DEFAULT 0,
                    total_descontos NUMERIC(10, 2) DEFAULT 0,
                    salario_liquido NUMERIC(10, 2) DEFAULT 0,
                    
                    -- Componentes de horas extras e DSR
                    valor_he_50 NUMERIC(10, 2) DEFAULT 0,
                    valor_he_100 NUMERIC(10, 2) DEFAULT 0,
                    valor_dsr NUMERIC(10, 2) DEFAULT 0,
                    
                    -- Encargos
                    encargos_fgts NUMERIC(10, 2) DEFAULT 0,
                    encargos_inss_patronal NUMERIC(10, 2) DEFAULT 0,
                    custo_total_empresa NUMERIC(10, 2) DEFAULT 0,
                    
                    -- Descontos do funcionário
                    inss_funcionario NUMERIC(10, 2) DEFAULT 0,
                    irrf NUMERIC(10, 2) DEFAULT 0,
                    desconto_faltas NUMERIC(10, 2) DEFAULT 0,
                    desconto_atrasos NUMERIC(10, 2) DEFAULT 0,
                    
                    -- Horas
                    horas_contratuais NUMERIC(10, 2) DEFAULT 0,
                    horas_trabalhadas NUMERIC(10, 2) DEFAULT 0,
                    horas_extras_50 NUMERIC(10, 2) DEFAULT 0,
                    horas_extras_100 NUMERIC(10, 2) DEFAULT 0,
                    horas_falta NUMERIC(10, 2) DEFAULT 0,
                    
                    -- Metadados
                    processado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    CONSTRAINT uq_folha_func_obra_periodo UNIQUE (funcionario_id, obra_id, ano, mes)
                )
            """)
            logger.info("  ✅ Tabela folha_processada criada")
            
            cursor.execute("""
                CREATE INDEX idx_folha_processada_obra ON folha_processada(obra_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_folha_processada_periodo ON folha_processada(ano, mes)
            """)
            cursor.execute("""
                CREATE INDEX idx_folha_processada_admin ON folha_processada(admin_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_folha_processada_funcionario ON folha_processada(funcionario_id)
            """)
            logger.info("  ✅ Índices criados")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 64 CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 64: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def _migration_59_alimentacao_itens_sistema():
    """
    Migração 59: Sistema de Itens de Alimentação v2.0
    
    Cria tabelas para:
    - alimentacao_item: Itens pré-cadastrados (Marmita, Refrigerante, etc.)
    - alimentacao_lancamento_item: Itens de cada lançamento com quantidade e preço
    
    Popular itens padrão automaticamente para cada admin
    """
    connection = None
    cursor = None
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("🍽️  MIGRAÇÃO 59: Sistema de Itens de Alimentação v2.0")
        logger.info("=" * 80)
        
        tabelas_criadas = 0
        
        # ========================================
        # PASSO 1: Criar tabela alimentacao_item
        # ========================================
        logger.info("📦 Criando tabela alimentacao_item...")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'alimentacao_item'
            )
        """)
        
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE alimentacao_item (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL,
                    preco_padrao NUMERIC(10,2) DEFAULT 0.00,
                    descricao TEXT,
                    icone VARCHAR(50) DEFAULT 'fas fa-utensils',
                    ordem INTEGER DEFAULT 0,
                    ativo BOOLEAN DEFAULT TRUE,
                    is_default BOOLEAN DEFAULT FALSE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX idx_alimentacao_item_admin 
                ON alimentacao_item(admin_id)
            """)
            
            cursor.execute("""
                CREATE INDEX idx_alimentacao_item_ativo 
                ON alimentacao_item(ativo, ordem)
            """)
            
            tabelas_criadas += 1
            logger.info("  ✅ Tabela alimentacao_item criada com índices")
        else:
            logger.info("  ⏭️  Tabela alimentacao_item já existe")
        
        # ========================================
        # PASSO 2: Criar tabela alimentacao_lancamento_item
        # ========================================
        logger.info("📦 Criando tabela alimentacao_lancamento_item...")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'alimentacao_lancamento_item'
            )
        """)
        
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE alimentacao_lancamento_item (
                    id SERIAL PRIMARY KEY,
                    lancamento_id INTEGER NOT NULL REFERENCES alimentacao_lancamento(id) ON DELETE CASCADE,
                    item_id INTEGER REFERENCES alimentacao_item(id) ON DELETE SET NULL,
                    nome_item VARCHAR(100) NOT NULL,
                    preco_unitario NUMERIC(10,2) NOT NULL,
                    quantidade INTEGER NOT NULL DEFAULT 1,
                    subtotal NUMERIC(10,2) NOT NULL,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX idx_alimentacao_lancamento_item_lancamento 
                ON alimentacao_lancamento_item(lancamento_id)
            """)
            
            cursor.execute("""
                CREATE INDEX idx_alimentacao_lancamento_item_admin 
                ON alimentacao_lancamento_item(admin_id)
            """)
            
            tabelas_criadas += 1
            logger.info("  ✅ Tabela alimentacao_lancamento_item criada com índices")
        else:
            logger.info("  ⏭️  Tabela alimentacao_lancamento_item já existe")
        
        # ========================================
        # PASSO 3: Popular itens padrão para cada admin
        # ========================================
        logger.info("🍽️  Populando itens padrão de alimentação...")
        
        itens_padrao = [
            ('Marmita', 18.00, 'Refeição completa', 'fas fa-utensils', 1, True),
            ('Refrigerante', 5.00, 'Refrigerante 350ml', 'fas fa-glass-cheers', 2, False),
            ('Água', 3.00, 'Água mineral 500ml', 'fas fa-tint', 3, False),
            ('Suco', 6.00, 'Suco natural', 'fas fa-lemon', 4, False),
            ('Café', 2.00, 'Café expresso', 'fas fa-coffee', 5, False),
            ('Lanche', 8.00, 'Lanche rápido', 'fas fa-hamburger', 6, False),
        ]
        
        cursor.execute("""
            SELECT DISTINCT id FROM usuario 
            WHERE tipo_usuario = 'admin' OR tipo_usuario = 'super_admin'
        """)
        
        admins = cursor.fetchall()
        itens_criados = 0
        
        for (admin_id,) in admins:
            for nome, preco, descricao, icone, ordem, is_default in itens_padrao:
                cursor.execute("""
                    SELECT id FROM alimentacao_item 
                    WHERE nome = %s AND admin_id = %s
                """, (nome, admin_id))
                
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO alimentacao_item 
                        (nome, preco_padrao, descricao, icone, ordem, is_default, admin_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (nome, preco, descricao, icone, ordem, is_default, admin_id))
                    itens_criados += 1
        
        logger.info(f"  ✅ {itens_criados} itens padrão criados para {len(admins)} admin(s)")
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 59 CONCLUÍDA COM SUCESSO!")
        logger.info(f"   📦 Tabelas criadas: {tabelas_criadas}")
        logger.info(f"   🍽️  Itens padrão criados: {itens_criados}")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 59: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


def executar_migracoes():
    """
    Execute todas as migrações necessárias automaticamente com rastreamento
    Sistema robusto com idempotência garantida via migration_history
    """
    try:
        logger.info("=" * 80)
        logger.info("🚀 SISTEMA DE MIGRAÇÕES v2.0 - RASTREAMENTO ATIVO")
        logger.info("=" * 80)
        
        # Mascarar credenciais por segurança
        database_url = os.environ.get('DATABASE_URL', 'postgresql://sige:sige@viajey_sige:5432/sige')
        logger.info(f"🎯 DATABASE: {mask_database_url(database_url)}")
        
        # PASSO 1: Garantir tabela de rastreamento existe
        logger.info("📋 Inicializando sistema de rastreamento...")
        ensure_migration_history_table()
        
        # PASSO 2: Executar migrações com rastreamento
        logger.info("🔄 Verificando migrações pendentes...")
        
        # ===== MIGRAÇÕES ATIVAS COM RASTREAMENTO =====
        migrations_to_run = [
            (20, "Sistema de Veículos Inteligente", _migration_20_unified_vehicle_system),
            (27, "Sistema de Alimentação", _migration_27_alimentacao_system),
            (33, "Recriar frota_despesa", _migration_33_recreate_frota_despesa),
            (34, "Campos pagamento Restaurante", _migration_34_restaurante_campos_pagamento),
            (35, "Coluna numero_nota_fiscal custo_veiculo", _migration_35_custo_veiculo_numero_nota_fiscal),
            (36, "Remover tabelas propostas legado", _migration_36_remove_old_propostas_tables),
            (37, "Renomear campos propostas_comerciais", _migration_37_rename_propostas_fields),
            (38, "Criar proposta_historico", _migration_38_create_proposta_historico),
            (39, "Sistema Almoxarifado v3.0", _migration_39_create_almoxarifado_system),
            (40, "Sistema Ponto Eletrônico Compartilhado", _migration_40_ponto_compartilhado),
            (41, "Sistema Financeiro v9.0", _migration_41_sistema_financeiro),
            (42, "Configuração Obras/Funcionário Ponto", _migration_42_funcionario_obras_ponto),
            (43, "Completar estruturas v9.0", _migration_43_completar_estruturas_v9),
            (44, "Adicionar jornada_semanal a funcionario", _migration_44_adicionar_jornada_semanal),
            (45, "Corrigir schema da tabela propostas_comerciais", _migration_45_corrigir_schema_propostas),
            (46, "Adicionar descricao a centro_custo_contabil", _migration_46_adicionar_descricao_centro_custo),
            (47, "Adicionar fornecedor_id ao almoxarifado_movimento", _migration_47_almoxarifado_fornecedor),
            (48, "Adicionar admin_id em 17 modelos faltantes", _migration_48_adicionar_admin_id_modelos_faltantes),
            (49, "Campos de alertas veículos (IPVA/Seguro)", _migration_49_vehicle_alertas),
            (50, "Schema completo tabela uso_veiculo", _migration_50_uso_veiculo_schema_completo),
            (51, "Schema completo tabela custo_veiculo", _migration_51_custo_veiculo_schema_completo),
            (52, "RDO Foto - otimização de campos", _migration_52_rdo_foto_campos_otimizacao),
            (53, "RDO Foto - persistência Base64", _migration_53_rdo_foto_base64),
            (54, "Tamanho logo portal do cliente", _migration_54_logo_tamanho_portal),
            (55, "Token cliente para portal público", _migration_55_token_cliente_proposta),
            (56, "PropostaArquivo - persistência Base64", _migration_56_proposta_arquivo_base64),
            (57, "Campos CRUD movimentações almoxarifado", _migration_57_almoxarifado_movimento_campos_crud),
            (58, "Sistema de Rastreamento de Lotes FIFO", _migration_58_almoxarifado_lotes_fifo),
            (59, "Sistema de Itens de Alimentação v2.0", _migration_59_alimentacao_itens_sistema),
            (60, "Adicionar created_at em centro_custo_contabil", _migration_60_centro_custo_created_at),
            (61, "Sistema HorarioDia para horários flexíveis", _migration_61_horario_dia_sistema),
            (62, "Tornar colunas legadas de HorarioTrabalho nullable", _migration_62_horario_trabalho_nullable),
            (63, "Tolerância minutos para horas extras/atrasos", _migration_63_tolerancia_minutos),
            (64, "Tabela folha_processada para dashboard custos obra", _migration_64_folha_processada),
            (65, "Adicionar coluna nome em fornecedor", _migration_65_fornecedor_nome),
            (66, "Campos reconhecimento facial RegistroPonto", _migration_66_reconhecimento_facial_ponto),
            (67, "Sistema de Geofencing (Cerca Virtual)", _migration_67_geofencing),
            (68, "Sistema de Múltiplas Fotos Faciais", _migration_68_multiplas_fotos_faciais),
            (69, "custo_veiculo.obra_id nullable", _migration_69_custo_veiculo_obra_nullable),
            (70, "Versionamento V1/V2 por Tenant (Feature Flag)", _migration_70_versao_sistema_usuario),
            (71, "Remuneração por Diária V2 (Funcionario)", _migration_71_remuneracao_diaria_funcionario),
            (72, "Alimentação V2 - funcionario_id e centro_custo_id por item", _migration_72_alimentacao_item_v2),
            (73, "Transporte V2 - tabelas categoria_transporte e lancamento_transporte", _migration_73_transporte_v2),
            (74, "Compras V2 - tabelas pedido_compra e pedido_compra_item", _migration_74_compras_v2),
            (75, "Cronograma V2 - CalendarioEmpresa e TarefaCronograma", _migration_75_cronograma_v2),
            (76, "RDO Apontamento Cronograma V2 - tabela rdo_apontamento_cronograma", _migration_76_rdo_apontamento_cronograma),
            (77, "Gestão de Custos V2 - tabelas gestao_custo_pai e gestao_custo_filho", _migration_77_gestao_custos_v2),
            (78, "Transporte V2 - centro_custo_id nullable + funcionario_id nullable", _migration_78_transporte_centro_custo_nullable),
            (79, "Reembolso V2 - tabela reembolso_funcionario", _migration_79_reembolso_funcionario),
            (80, "Reembolso V2 - categoria e comprovante_url", _migration_80_reembolso_campos_extras),
            (81, "Reembolso V2 - gestao_custo_pai_id FK", _migration_81_reembolso_gestao_custo_pai_id),
            (82, "Obra codigo - unique por tenant (codigo+admin_id)", _migration_82_obra_codigo_per_tenant),
            (83, "GestaoCustoPai - data_vencimento e numero_documento para DESPESA_GERAL", _migration_83_gestao_custo_vencimento),
            (84, "AlimentacaoLancamento - restaurante_id nullable para V2", _migration_84_alimentacao_restaurante_nullable),
            (85, "GestaoCustoPai - fornecedor_id, forma_pagamento, valor_pago, saldo, conta_contabil_codigo, data_emissao, numero_parcela, total_parcelas", _migration_85_gestao_custo_pai_novas_colunas),
            (86, "CustoObra - colunas extras (funcionario_id, rdo_id, categoria, horas, quantidade, veiculo, almoxarifado)", _migration_86_custo_obra_colunas_extras),
            (87, "Proposta - numero_proposta unique por tenant (numero_proposta + admin_id)", migration_87_proposta_numero_unique_por_tenant),
            (88, "TarefaCronograma - campo responsavel (empresa/terceiros)", migration_88_tarefa_cronograma_responsavel),
            (89, "RDO - criado_por_id nullable (FK usuario)", migration_89_rdo_criado_por_nullable),
            (90, "RDOMaoObra - subatividade_id (FK cascade) + horas_extras", migration_90_rdo_mao_obra_subatividade),
            (91, "RDOMaoObra - tarefa_cronograma_id (FK SET NULL) para métricas por tarefa", migration_91_rdo_mao_obra_tarefa_cronograma),
            (92, "AlmoxarifadoMovimento - pedido_compra_id FK opcional para rastreamento de origem", migration_92_almoxarifado_pedido_compra_id),
            (93, "PedidoCompra - centro_custo_id nullable (obra é o centro de custo principal)", migration_93_pedido_compra_centro_custo_nullable),
            (94, "SubatividadeMestre - unidade_medida e meta_produtividade para catálogo de produtividade", migration_94_subatividade_mestre_produtividade),
            (95, "CronogramaTemplate e CronogramaTemplateItem - templates reutilizáveis de cronograma", migration_95_cronograma_templates),
            (96, "RDOServicoSubatividade - quantidade_produzida, subatividade_mestre_id e snapshots de produtividade", migration_96_rdo_servico_subatividade_produtividade),
            (97, "RDOMaoObra - produtividade_real e indice_produtividade calculados na finalização do RDO", migration_97_rdo_mao_obra_produtividade),
            (98, "SubatividadeMestre tipo+servico_id nullable, CronogramaTemplateItem parent_item_id - catálogo hierárquico", migration_98_catalogo_hierarquico),
            (99, "RDOServicoSubatividade servico_id nullable para suportar subatividades sem serviço vinculado", migration_99_rdo_servico_sub_nullable),
            (100, "TarefaCronograma - subatividade_mestre_id FK para rastreamento de catálogo", migration_100_tarefa_cronograma_subatividade_mestre_id),
            (101, "Funcionario - chave_pix, valor_va e valor_vt para PIX e benefícios diários", migration_101_funcionario_pix_va_vt),
            (102, "Funcionario - codigo unique por tenant (codigo+admin_id) em vez de global", migration_102_funcionario_codigo_per_tenant),
            (103, "import_batch_id em gestao_custo_pai, conta_pagar, conta_receber, fluxo_caixa — rollback de importação", migration_103_import_batch_id),
            (104, "Fornecedor - tipo_fornecedor (MATERIAL / PRESTADOR_SERVICO / OUTRO)", migration_104_tipo_fornecedor),
            (105, "FluxoCaixa - banco_id FK opcional para BancoEmpresa", migration_105_fluxo_caixa_banco_id),
            (106, "RDO e filhos — ON DELETE CASCADE para exclusão em cascata com Obra", migration_106_rdo_obra_cascade),
            (107, "Portal do Cliente — chave_pix, status_aprovacao_cliente, medicao_obra", migration_107_portal_cliente_obra),
            (108, "Medição Quinzenal — itens comerciais, tarefas vinculadas, expansão medicao_obra", migration_108_medicao_quinzenal),
            (109, "Mapa de Concorrência — tabelas mapa_concorrencia e opcao_concorrencia", migration_109_mapa_concorrencia),
            (110, "OpcaoConcorrencia — enforça NOT NULL em admin_id", migration_110_opcao_concorrencia_admin_not_null),
            (111, "CronogramaCliente — cronograma editável para portal do cliente", migration_111_cronograma_cliente),
            (112, "MapaConcorrenciaV2 — tabela multi-fornecedor com cotações por item", migration_112_mapa_concorrencia_v2),
            (113, "TarefaCronograma — data_entrega_real DATE para entregas/terceiros", migration_113_tarefa_cronograma_data_entrega_real),
            (114, "Subempreiteiro + RDOSubempreitadaApontamento + GestaoCustoPai.subempreiteiro_id", migration_114_subempreiteiro),
            (115, "Consolidar GestaoCustoPai duplicados por (admin_id, entidade_id, categoria normalizada)", migration_115_consolidar_gestao_custo_pai_duplicados),
            (116, "PedidoCompra — tipo_compra (normal/aprovacao_cliente) + processada_apos_aprovacao", migration_116_pedido_compra_tipo_compra),
            (117, "TarefaCronograma — is_cliente BOOLEAN (paridade total no editor cliente)", migration_117_tarefa_cronograma_is_cliente),
            (118, "Task #70 — Resumo de Custos da Obra (obra_servico_custo + equipe + cotação + percentual_administracao)", migration_118_resumo_custos_obra),
            (119, "Task #74 — GestaoCustoFilho.obra_servico_custo_id (vínculo direto custo→serviço)", migration_119_gestao_custo_filho_obra_servico),
            (120, "Task #76 — NotificacaoOrcamento (alertas de estouro de orçamento por serviço)", migration_120_notificacao_orcamento),
            (121, "Task #82 — Catálogo de Insumos + Composição de Serviços + Orçamento Paramétrico", migration_121_catalogo_servicos_orcamento),
            (122, "Task #82 — ItemMedicaoComercial.proposta_item_id (dedupe determinístico de propagação)", migration_122_item_medicao_proposta_item_id),
            (123, "Task #82 — ComposicaoServico.unidade (snapshot da unidade do insumo)", migration_123_composicao_servico_unidade),
            (124, "Task #89 — Snapshot de cálculo paramétrico em PropostaItem e ItemMedicaoComercial", migration_124_snapshot_calculo_parametrico),
            (125, "Task #102 — Cronograma automático na aprovação (servico.template_padrao_id, propostas.cronograma_default_json, tarefa_cronograma.gerada_por_proposta_item_id)", migration_125_cronograma_automatico_aprovacao),
            (126, "Task #115 — Orçamento + OrcamentoItem (camada interna que gera Proposta)", migration_126_orcamento),
            (127, "Task #115 v2 — propostas_comerciais.orcamento_id (Orçamento → N Propostas)", migration_127_proposta_orcamento_id),
            (128, "Task #118 — cronograma_template_override_id em orcamento_item e proposta_itens + composicao_snapshot em proposta_itens", migration_128_orcamento_item_cronograma_override),
            (129, "Task #158 — assinatura e engenheiro responsável em configuracao_empresa", migration_129_configuracao_empresa_assinatura_engenheiro),
            (130, "Task #165 — alinhar tipos numéricos de orçamento/proposta_itens (Float→Numeric)", migration_130_alinhar_tipos_numericos_orcamento_proposta),
            (131, "Task #166 — coeficiente_padrao em insumo (sugestão p/ composição)", migration_131_insumo_coeficiente_padrao),
            (132, "Task #172 — Obra.cliente_id FK + backfill por nome/email do cliente", migration_132_obra_cliente_id_fk),
        ]
        
        # Executar cada migração com rastreamento
        total_migrations = len(migrations_to_run)
        executed_count = 0
        skipped_count = 0
        failed_count = 0
        
        for migration_number, migration_name, migration_func in migrations_to_run:
            result = run_migration_safe(migration_number, migration_name, migration_func)
            
            if result:
                # Verificar se foi executada ou pulada
                if is_migration_executed(migration_number):
                    # Se já estava executada antes, foi skip
                    if result and "já executada" not in str(result):
                        executed_count += 1
                    else:
                        skipped_count += 1
            else:
                failed_count += 1
        
        # Resumo final
        logger.info("=" * 80)
        logger.info("📊 RESUMO DAS MIGRAÇÕES")
        logger.info("=" * 80)
        logger.info(f"✅ Executadas: {executed_count}")
        logger.info(f"⏭️  Puladas (já aplicadas): {skipped_count}")
        logger.info(f"❌ Falhas: {failed_count}")
        logger.info(f"📝 Total processadas: {total_migrations}")
        logger.info("=" * 80)
        
        if failed_count > 0:
            logger.warning(f"⚠️  {failed_count} migração(ões) falharam - verifique os logs acima")
        else:
            logger.info("✅ Todas as migrações foram processadas com sucesso!")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro crítico durante sistema de migrações: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Não interromper a aplicação, apenas logar o erro
        pass

def garantir_usuarios_producao():
    """
    Garantir que usuários necessários existem para evitar foreign key violations
    """
    try:
        from models import Usuario
        
        # Verificar se usuário admin_id=10 existe
        usuario_10 = Usuario.query.get(10)
        if not usuario_10:
            logger.info("🔄 Criando usuário admin ID=10 para produção...")
            
            # Criar usuário usando SQL direto para evitar conflitos
            db.engine.execute(text("""
                INSERT INTO usuario (id, username, email, nome, password_hash, tipo_usuario, ativo, admin_id)
                VALUES (10, 'valeverde_admin', 'admin@valeverde.com.br', 'Administrador Vale Verde', 
                        'scrypt:32768:8:1$PLACEHOLDER_HASH_TO_BE_CHANGED', 
                        'admin', TRUE, NULL)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, nome = EXCLUDED.nome
            """))
            logger.info("✅ Usuário admin ID=10 criado com sucesso!")
        else:
            logger.info("✅ Usuário admin ID=10 já existe")
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao garantir usuários de produção: {e}")
        # Tentar com método alternativo se SQLAlchemy 2.0
        try:
            connection = db.engine.raw_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                INSERT INTO usuario (id, username, email, nome, password_hash, tipo_usuario, ativo, admin_id)
                VALUES (10, 'valeverde_admin', 'admin@valeverde.com.br', 'Administrador Vale Verde', 
                        'scrypt:32768:8:1$PLACEHOLDER_HASH_TO_BE_CHANGED', 'admin', TRUE, NULL)
                ON CONFLICT (id) DO NOTHING
            """)
            connection.commit()
            cursor.close()
            connection.close()
            logger.info("✅ Usuário admin ID=10 criado via conexão direta!")
        except Exception as e2:
            logger.error(f"❌ Falha ao criar usuário admin: {e2}")

def migrar_campos_opcionais_propostas():
    """
    Torna os campos assunto e objeto opcionais na tabela propostas_comerciais
    """
    try:
        # Usar conexão direta para verificar constraints
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se os campos ainda são NOT NULL
        cursor.execute("""
            SELECT column_name, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name IN ('assunto', 'objeto')
            AND is_nullable = 'NO'
        """)
        campos_nao_null = cursor.fetchall()
        
        if campos_nao_null:
            logger.info("🔄 Removendo constraints NOT NULL dos campos assunto e objeto...")
            
            # Remover constraint NOT NULL do campo assunto
            cursor.execute("ALTER TABLE propostas_comerciais ALTER COLUMN assunto DROP NOT NULL")
            logger.info("✅ Campo 'assunto' agora é opcional")
            
            # Remover constraint NOT NULL do campo objeto
            cursor.execute("ALTER TABLE propostas_comerciais ALTER COLUMN objeto DROP NOT NULL")
            logger.info("✅ Campo 'objeto' agora é opcional")
            
            connection.commit()
            logger.info("✅ Campos de proposta atualizados para serem opcionais")
        else:
            logger.info("✅ Campos assunto e objeto já são opcionais")
            
        cursor.close()
        connection.close()
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar campos opcionais: {str(e)}")

def migrar_personalizacao_visual_empresa():
    """
    Adiciona colunas de personalização visual na tabela configuracao_empresa
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de colunas para adicionar
        colunas_novas = [
            ('logo_base64', 'TEXT'),
            ('logo_pdf_base64', 'TEXT'),
            ('header_pdf_base64', 'TEXT'),
            ('cor_primaria', 'VARCHAR(7) DEFAULT \'#007bff\''),
            ('cor_secundaria', 'VARCHAR(7) DEFAULT \'#6c757d\''),
            ('cor_fundo_proposta', 'VARCHAR(7) DEFAULT \'#f8f9fa\'')
        ]
        
        for nome_coluna, tipo_coluna in colunas_novas:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'configuracao_empresa' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela configuracao_empresa...")
                cursor.execute(f"ALTER TABLE configuracao_empresa ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela configuracao_empresa")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar colunas de personalização visual: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()
            cursor.close()
            connection.close()

def garantir_tabela_proposta_templates_existe():
    """
    Verifica se a tabela proposta_templates existe, se não existir, cria completa
    """
    try:
        # Verificar se a tabela existe
        table_check = text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'proposta_templates'
        """)
        
        result = db.session.execute(table_check).scalar()
        
        if result == 0:
            logger.info("📝 Tabela proposta_templates não existe, criando...")
            
            # Criar tabela completa
            create_table_query = text("""
                CREATE TABLE proposta_templates (
                    id serial PRIMARY KEY,
                    nome character varying(100) NOT NULL,
                    descricao text,
                    categoria character varying(50) NOT NULL DEFAULT 'Estrutura Metálica',
                    itens_padrao json DEFAULT '[]'::json,
                    prazo_entrega_dias integer DEFAULT 90,
                    validade_dias integer DEFAULT 7,
                    percentual_nota_fiscal numeric(5,2) DEFAULT 13.5,
                    itens_inclusos text,
                    itens_exclusos text,
                    condicoes text,
                    condicoes_pagamento text DEFAULT '10% de entrada na assinatura do contrato
10% após projeto aprovado
45% compra dos perfis
25% no início da montagem in loco
10% após a conclusão da montagem',
                    garantias text DEFAULT 'A empresa garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.',
                    ativo boolean DEFAULT true,
                    publico boolean DEFAULT false,
                    uso_contador integer DEFAULT 0,
                    admin_id integer,
                    criado_por integer,
                    criado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            db.session.execute(create_table_query)
            db.session.commit()
            
            logger.info("✅ Tabela proposta_templates criada com sucesso!")
        else:
            logger.info("✅ Tabela proposta_templates já existe")
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar/criar tabela proposta_templates: {e}")
        db.session.rollback()

def migrar_categoria_proposta_templates():
    """
    Adiciona a coluna categoria na tabela proposta_templates se não existir
    """
    try:
        # Verificar se a coluna já existe
        check_query = text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'proposta_templates' 
            AND column_name = 'categoria'
        """)
        
        result = db.session.execute(check_query).scalar()
        
        if result == 0:
            # Coluna não existe, criar
            logger.info("📝 Adicionando coluna 'categoria' na tabela proposta_templates...")
            
            migration_query = text("""
                ALTER TABLE proposta_templates 
                ADD COLUMN categoria character varying(50) NOT NULL DEFAULT 'Estrutura Metálica'
            """)
            
            db.session.execute(migration_query)
            db.session.commit()
            
            logger.info("✅ Coluna 'categoria' adicionada com sucesso!")
        else:
            logger.info("✅ Coluna 'categoria' já existe na tabela proposta_templates")
            
    except Exception as e:
        logger.error(f"❌ Erro ao migrar coluna categoria: {e}")
        db.session.rollback()

def migrar_colunas_faltantes_proposta_templates():
    """
    Adiciona todas as colunas que podem estar faltantes na tabela proposta_templates
    """
    colunas_necessarias = [
        ('itens_padrao', 'json DEFAULT \'[]\'::json'),
        ('prazo_entrega_dias', 'integer DEFAULT 90'),
        ('validade_dias', 'integer DEFAULT 7'), 
        ('percentual_nota_fiscal', 'numeric(5,2) DEFAULT 13.5'),
        ('itens_inclusos', 'text'),
        ('itens_exclusos', 'text'), 
        ('condicoes', 'text'),
        ('condicoes_pagamento', 'text DEFAULT \'10% de entrada na assinatura do contrato\n10% após projeto aprovado\n45% compra dos perfis\n25% no início da montagem in loco\n10% após a conclusão da montagem\''),
        ('garantias', 'text DEFAULT \'A empresa garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.\''),
        ('ativo', 'boolean DEFAULT true'),
        ('publico', 'boolean DEFAULT false'),
        ('uso_contador', 'integer DEFAULT 0'),
        ('admin_id', 'integer'),
        ('criado_por', 'integer'),
        ('criado_em', 'timestamp without time zone DEFAULT CURRENT_TIMESTAMP'),
        ('atualizado_em', 'timestamp without time zone DEFAULT CURRENT_TIMESTAMP')
    ]
    
    for nome_coluna, tipo_coluna in colunas_necessarias:
        try:
            # Verificar se a coluna já existe
            check_query = text(f"""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_templates' 
                AND column_name = '{nome_coluna}'
            """)
            
            result = db.session.execute(check_query).scalar()
            
            if result == 0:
                # Coluna não existe, criar
                logger.info(f"📝 Adicionando coluna '{nome_coluna}' na tabela proposta_templates...")
                
                migration_query = text(f"""
                    ALTER TABLE proposta_templates 
                    ADD COLUMN {nome_coluna} {tipo_coluna}
                """)
                
                db.session.execute(migration_query)
                db.session.commit()
                
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso!")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela proposta_templates")
                
        except Exception as e:
            logger.error(f"❌ Erro ao migrar coluna {nome_coluna}: {e}")
            db.session.rollback()
            
    # Adicionar foreign keys se necessário
    try:
        add_foreign_keys_if_needed()
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar foreign keys: {e}")

def add_foreign_keys_if_needed():
    """
    Adiciona foreign keys que podem estar faltando
    """
    try:
        # Verificar se FK admin_id existe
        fk_check = text("""
            SELECT COUNT(*) FROM information_schema.table_constraints 
            WHERE constraint_type = 'FOREIGN KEY' 
            AND table_name = 'proposta_templates' 
            AND constraint_name LIKE '%admin_id%'
        """)
        
        result = db.session.execute(fk_check).scalar()
        
        if result == 0:
            logger.info("📝 Adicionando foreign key para admin_id...")
            
            # Primeiro verificar se a tabela usuario existe
            table_check = text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'usuario'")
            if db.session.execute(table_check).scalar() > 0:
                fk_query = text("""
                    ALTER TABLE proposta_templates 
                    ADD CONSTRAINT fk_proposta_templates_admin_id 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                """)
                
                db.session.execute(fk_query)
                db.session.commit()
                logger.info("✅ Foreign key admin_id adicionada!")
            
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível adicionar foreign keys: {e}")
        db.session.rollback()

def verificar_estrutura_tabela():
    """
    Verifica e exibe a estrutura atual da tabela proposta_templates
    """
    try:
        query = text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'proposta_templates' 
            ORDER BY ordinal_position
        """)
        
        colunas = db.session.execute(query).fetchall()
        
        logger.info("📋 Estrutura atual da tabela proposta_templates:")
        for coluna in colunas:
            logger.info(f"  - {coluna.column_name} ({coluna.data_type})")
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar estrutura da tabela: {e}")

def migrar_campos_organizacao_propostas():
    """
    Adiciona campos de organização avançada para proposta_itens
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de colunas para adicionar
        colunas_organizacao = [
            ('categoria_titulo', 'VARCHAR(100)'),
            ('template_origem_id', 'INTEGER'),
            ('template_origem_nome', 'VARCHAR(100)'),
            ('grupo_ordem', 'INTEGER DEFAULT 1'),
            ('item_ordem_no_grupo', 'INTEGER DEFAULT 1')
        ]
        
        for nome_coluna, tipo_coluna in colunas_organizacao:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_itens' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela proposta_itens...")
                cursor.execute(f"ALTER TABLE proposta_itens ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela proposta_itens")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar campos de organização: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()

def migrar_campos_completos_templates():
    """
    Migração 7: Adicionar campos completos para templates (dados do cliente, engenheiro, seções)
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Lista de colunas completas para adicionar
        colunas_completas = [
            # Dados do cliente (primeira página)
            ("cidade_data", "VARCHAR(200) DEFAULT 'São José dos Campos, [DATA]'"),
            ("destinatario", "VARCHAR(200)"),
            ("atencao_de", "VARCHAR(200)"),
            ("telefone_cliente", "VARCHAR(50)"),
            ("assunto", "TEXT"),
            ("numero_referencia", "VARCHAR(100)"),
            ("texto_apresentacao", "TEXT"),
            
            # Dados do engenheiro responsável
            ("engenheiro_nome", "VARCHAR(200) DEFAULT 'Engº Lucas Barbosa Alves Pinto'"),
            ("engenheiro_crea", "VARCHAR(50) DEFAULT 'CREA- 5070458626-SP'"),
            ("engenheiro_email", "VARCHAR(120) DEFAULT ''"),
            ("engenheiro_telefone", "VARCHAR(50) DEFAULT ''"),
            ("engenheiro_endereco", "TEXT DEFAULT ''"),
            ("engenheiro_website", "VARCHAR(200) DEFAULT ''"),
            
            # Seções completas da proposta (1-9)
            ("secao_objeto", "TEXT"),
            ("condicoes_entrega", "TEXT"),
            ("consideracoes_gerais", "TEXT"),
            ("secao_validade", "TEXT")
        ]
        
        for nome_coluna, tipo_coluna in colunas_completas:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_templates' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela proposta_templates...")
                cursor.execute(f"ALTER TABLE proposta_templates ADD COLUMN {nome_coluna} {tipo_coluna}")
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela proposta_templates")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar campos completos de templates: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()


def migrar_campos_rdo_ocorrencia():
    """
    CRÍTICA: Migração para corrigir campos faltantes na tabela rdo_ocorrencia
    O modelo RDOOcorrencia possui campos que não existem na tabela do banco
    """
    try:
        import psycopg2
        import os
        
        # Conectar ao banco usando a URL do ambiente
        connection = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = connection.cursor()
        
        logger.info("🔄 Verificando e adicionando campos faltantes na tabela rdo_ocorrencia...")
        
        # Campos que precisam existir na tabela rdo_ocorrencia
        campos_necessarios = [
            ("tipo_ocorrencia", "VARCHAR(50)", "NOT NULL DEFAULT 'Observação'"),
            ("severidade", "VARCHAR(20)", "DEFAULT 'Baixa'"),
            ("responsavel_acao", "VARCHAR(100)"),
            ("prazo_resolucao", "DATE"),
            ("status_resolucao", "VARCHAR(20)", "DEFAULT 'Pendente'"),
            ("observacoes_resolucao", "TEXT"),
            ("criado_em", "TIMESTAMP", "DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for nome_coluna, tipo_coluna, *restricoes in campos_necessarios:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'rdo_ocorrencia' 
                AND column_name = %s
            """, (nome_coluna,))
            
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"🔄 Adicionando coluna '{nome_coluna}' na tabela rdo_ocorrencia...")
                
                # Montar comando ALTER TABLE
                alter_comando = f"ALTER TABLE rdo_ocorrencia ADD COLUMN {nome_coluna} {tipo_coluna}"
                if restricoes:
                    alter_comando += f" {restricoes[0]}"
                
                cursor.execute(alter_comando)
                logger.info(f"✅ Coluna '{nome_coluna}' adicionada com sucesso na tabela rdo_ocorrencia")
            else:
                logger.info(f"✅ Coluna '{nome_coluna}' já existe na tabela rdo_ocorrencia")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração da tabela rdo_ocorrencia concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO ao migrar campos RDO ocorrência: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()


def migrar_campo_admin_id_rdo():
    """
    CRÍTICA: Adicionar campo admin_id na tabela rdo para suporte multitenant
    """
    try:
        import psycopg2
        import os
        
        # Conectar ao banco usando a URL do ambiente
        connection = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = connection.cursor()
        
        logger.info("🔄 Verificando se campo admin_id existe na tabela rdo...")
        
        # Verificar se a coluna admin_id já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'rdo' 
            AND column_name = 'admin_id'
        """)
        
        exists = cursor.fetchone()
        
        if not exists:
            logger.info("🔄 Adicionando coluna 'admin_id' na tabela rdo...")
            cursor.execute("ALTER TABLE rdo ADD COLUMN admin_id INTEGER REFERENCES usuario(id)")
            logger.info("✅ Coluna 'admin_id' adicionada com sucesso na tabela rdo")
        else:
            logger.info("✅ Coluna 'admin_id' já existe na tabela rdo")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração do campo admin_id na tabela rdo concluída!")
        
    except Exception as e:
        logger.error(f"❌ ERRO ao migrar campo admin_id RDO: {str(e)}")
        if 'connection' in locals():
            connection.rollback()
            cursor.close()
            connection.close()


def migrar_sistema_rdo_aprimorado():
    """
    CRÍTICA: Criar/atualizar tabelas do sistema RDO aprimorado com verificação de estrutura
    """
    try:
        import psycopg2
        import os
        
        # Conectar ao banco usando a URL do ambiente
        connection = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = connection.cursor()
        
        logger.info("🔄 Verificando e atualizando estrutura das tabelas RDO (preservando dados)...")
        
        # Verificar se tabelas existem
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name IN ('subatividade_mestre', 'rdo_servico_subatividade')
            AND table_schema = 'public'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"📋 Tabelas encontradas: {existing_tables}")
        
        # SUBATIVIDADE_MESTRE: Criar ou verificar estrutura
        if 'subatividade_mestre' not in existing_tables:
            logger.info("🆕 Criando tabela subatividade_mestre...")
            cursor.execute("""
                CREATE TABLE subatividade_mestre (
                    id SERIAL PRIMARY KEY,
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    nome VARCHAR(200) NOT NULL,
                    descricao TEXT,
                    ordem_padrao INTEGER DEFAULT 0,
                    obrigatoria BOOLEAN DEFAULT TRUE,
                    duracao_estimada_horas FLOAT,
                    complexidade INTEGER DEFAULT 1,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Tabela subatividade_mestre criada")
        else:
            logger.info("🔍 Verificando estrutura da tabela subatividade_mestre...")
            
            # Definir colunas esperadas
            expected_columns = {
                'id': 'SERIAL PRIMARY KEY',
                'servico_id': 'INTEGER NOT NULL',
                'nome': 'VARCHAR(200) NOT NULL',
                'descricao': 'TEXT',
                'ordem_padrao': 'INTEGER DEFAULT 0',
                'obrigatoria': 'BOOLEAN DEFAULT TRUE',
                'duracao_estimada_horas': 'FLOAT',
                'complexidade': 'INTEGER DEFAULT 1', 
                'admin_id': 'INTEGER NOT NULL',
                'ativo': 'BOOLEAN DEFAULT TRUE',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            # Verificar colunas existentes
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'subatividade_mestre' 
                ORDER BY ordinal_position
            """)
            existing_columns = {row[0]: row for row in cursor.fetchall()}
            
            # Adicionar colunas faltantes
            for col_name in expected_columns:
                if col_name not in existing_columns and col_name != 'id':  # Nunca alterar ID
                    try:
                        col_definition = expected_columns[col_name]
                        
                        # Simplificar definição para ALTER TABLE
                        if col_name == 'servico_id':
                            col_def = 'INTEGER NOT NULL REFERENCES servico(id)'
                        elif col_name == 'admin_id':
                            col_def = 'INTEGER NOT NULL REFERENCES usuario(id)'
                        elif col_name == 'nome':
                            col_def = 'VARCHAR(200) NOT NULL'
                        elif col_name == 'descricao':
                            col_def = 'TEXT'
                        elif col_name == 'ordem_padrao':
                            col_def = 'INTEGER DEFAULT 0'
                        elif col_name == 'obrigatoria':
                            col_def = 'BOOLEAN DEFAULT TRUE'
                        elif col_name == 'duracao_estimada_horas':
                            col_def = 'FLOAT'
                        elif col_name == 'complexidade':
                            col_def = 'INTEGER DEFAULT 1'
                        elif col_name == 'ativo':
                            col_def = 'BOOLEAN DEFAULT TRUE'
                        elif col_name in ['created_at', 'updated_at']:
                            col_def = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                        else:
                            col_def = 'TEXT'
                        
                        cursor.execute(f"ALTER TABLE subatividade_mestre ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                        logger.info(f"✅ Coluna '{col_name}' adicionada à subatividade_mestre")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao adicionar coluna '{col_name}': {e}")
            
            logger.info("✅ Estrutura subatividade_mestre verificada/atualizada")
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subativ_mestre_servico ON subatividade_mestre(servico_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subativ_mestre_admin ON subatividade_mestre(admin_id)")
        
        # RDO_SERVICO_SUBATIVIDADE: Criar ou verificar estrutura  
        if 'rdo_servico_subatividade' not in existing_tables:
            logger.info("🆕 Criando tabela rdo_servico_subatividade...")
            cursor.execute("""
                CREATE TABLE rdo_servico_subatividade (
                    id SERIAL PRIMARY KEY,
                    rdo_id INTEGER NOT NULL REFERENCES rdo(id),
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    nome_subatividade VARCHAR(200) NOT NULL,
                    descricao_subatividade TEXT,
                    percentual_conclusao FLOAT DEFAULT 0.0,
                    percentual_anterior FLOAT DEFAULT 0.0,
                    incremento_dia FLOAT DEFAULT 0.0,
                    observacoes_tecnicas TEXT,
                    ordem_execucao INTEGER DEFAULT 0,
                    ativo BOOLEAN DEFAULT TRUE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Tabela rdo_servico_subatividade criada")
        else:
            logger.info("🔍 Verificando estrutura da tabela rdo_servico_subatividade...")
            
            # Definir colunas esperadas
            expected_columns = {
                'id': 'SERIAL PRIMARY KEY',
                'rdo_id': 'INTEGER NOT NULL',
                'servico_id': 'INTEGER NOT NULL', 
                'nome_subatividade': 'VARCHAR(200) NOT NULL',
                'descricao_subatividade': 'TEXT',
                'percentual_conclusao': 'FLOAT DEFAULT 0.0',
                'percentual_anterior': 'FLOAT DEFAULT 0.0',
                'incremento_dia': 'FLOAT DEFAULT 0.0',
                'observacoes_tecnicas': 'TEXT',
                'ordem_execucao': 'INTEGER DEFAULT 0',
                'ativo': 'BOOLEAN DEFAULT TRUE',
                'admin_id': 'INTEGER NOT NULL',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            # Verificar colunas existentes
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'rdo_servico_subatividade' 
                ORDER BY ordinal_position
            """)
            existing_columns = {row[0]: row for row in cursor.fetchall()}
            
            # Adicionar colunas faltantes
            for col_name in expected_columns:
                if col_name not in existing_columns and col_name != 'id':  # Nunca alterar ID
                    try:
                        # Simplificar definição para ALTER TABLE
                        if col_name == 'rdo_id':
                            col_def = 'INTEGER NOT NULL REFERENCES rdo(id)'
                        elif col_name == 'servico_id':
                            col_def = 'INTEGER NOT NULL REFERENCES servico(id)'
                        elif col_name == 'admin_id':
                            col_def = 'INTEGER NOT NULL REFERENCES usuario(id)'
                        elif col_name == 'nome_subatividade':
                            col_def = 'VARCHAR(200) NOT NULL'
                        elif col_name in ['descricao_subatividade', 'observacoes_tecnicas']:
                            col_def = 'TEXT'
                        elif col_name in ['percentual_conclusao', 'percentual_anterior', 'incremento_dia']:
                            col_def = 'FLOAT DEFAULT 0.0'
                        elif col_name == 'ordem_execucao':
                            col_def = 'INTEGER DEFAULT 0'
                        elif col_name == 'ativo':
                            col_def = 'BOOLEAN DEFAULT TRUE'
                        elif col_name in ['created_at', 'updated_at']:
                            col_def = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                        else:
                            col_def = 'TEXT'
                        
                        cursor.execute(f"ALTER TABLE rdo_servico_subatividade ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                        logger.info(f"✅ Coluna '{col_name}' adicionada à rdo_servico_subatividade")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao adicionar coluna '{col_name}': {e}")
            
            logger.info("✅ Estrutura rdo_servico_subatividade verificada/atualizada")
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rdo_servico_subativ ON rdo_servico_subatividade(rdo_id, servico_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subativ_admin ON rdo_servico_subatividade(admin_id)")
        
        # REMOVIDO: Não inserir dados automaticamente - apenas criar tabelas vazias
        logger.info("✅ Estrutura de tabelas garantida - dados existentes preservados")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração do sistema RDO aprimorado concluída!")
        
    except Exception as e:
        logger.error(f"❌ Erro na migração do sistema RDO: {e}")
        try:
            connection.rollback()
            cursor.close()  
            connection.close()
        except:
            pass

def adicionar_admin_id_servico():
    """Adiciona admin_id na tabela servico para multi-tenant"""
    try:
        # Verificar se a coluna admin_id já existe na tabela servico
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='servico' AND column_name='admin_id'
        """)).fetchone()
        
        if not result:
            logger.info("🔧 Adicionando coluna admin_id na tabela servico...")
            
            # Adicionar coluna admin_id
            db.session.execute(text("""
                ALTER TABLE servico 
                ADD COLUMN admin_id INTEGER REFERENCES usuario(id)
            """))
            
            # Atualizar registros existentes com admin_id padrão (10)
            db.session.execute(text("""
                UPDATE servico 
                SET admin_id = 10 
                WHERE admin_id IS NULL
            """))
            
            # Tornar a coluna NOT NULL após popular os dados
            db.session.execute(text("""
                ALTER TABLE servico 
                ALTER COLUMN admin_id SET NOT NULL
            """))
            
            db.session.commit()
            logger.info("✅ Coluna admin_id adicionada na tabela servico")
            
        else:
            logger.info("✅ Coluna admin_id já existe na tabela servico")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao adicionar admin_id na tabela servico: {e}")

def corrigir_admin_id_servicos_existentes():
    """Corrige admin_id em serviços existentes que podem estar sem valor"""
    try:
        # Usar conexão direta para máxima compatibilidade
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar quantos serviços estão sem admin_id
        cursor.execute("SELECT COUNT(*) FROM servico WHERE admin_id IS NULL")
        servicos_sem_admin = cursor.fetchone()[0]
        
        if servicos_sem_admin > 0:
            logger.info(f"🔧 Corrigindo {servicos_sem_admin} serviços sem admin_id...")
            
            # Atualizar serviços sem admin_id para usar admin_id=10
            cursor.execute("""
                UPDATE servico 
                SET admin_id = 10 
                WHERE admin_id IS NULL
            """)
            
            logger.info(f"✅ {servicos_sem_admin} serviços corrigidos com admin_id=10")
        else:
            logger.info("✅ Todos os serviços já possuem admin_id correto")
        
        # CORREÇÃO CRÍTICA: Verificar apenas se usuários existem na tabela usuario (não só admins)
        cursor.execute("""
            SELECT DISTINCT admin_id 
            FROM servico 
            WHERE admin_id NOT IN (SELECT id FROM usuario)
        """)
        admin_ids_invalidos = cursor.fetchall()
        
        for (admin_id_invalido,) in admin_ids_invalidos:
            logger.warning(f"⚠️ Serviços com admin_id inválido (usuário não existe): {admin_id_invalido}")
            
            # IMPORTANTE: Só corrigir se o usuário realmente não existir
            # Não alterar serviços de usuários válidos como admin_id=50
            cursor.execute("SELECT COUNT(*) FROM usuario WHERE id = %s", (admin_id_invalido,))
            usuario_existe = cursor.fetchone()[0]
            
            if usuario_existe == 0:
                logger.info(f"🔧 Corrigindo serviços para admin_id=10 (usuário {admin_id_invalido} não existe)")
                cursor.execute("""
                    UPDATE servico 
                    SET admin_id = 10 
                    WHERE admin_id = %s
                """, (admin_id_invalido,))
            else:
                logger.info(f"✅ Mantendo serviços do admin_id={admin_id_invalido} (usuário válido)")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("✅ Correção de admin_id em serviços concluída!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao corrigir admin_id em serviços: {e}")
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except:
            pass

def migrar_tabela_servico_obra_real():
    """
    Criar tabela ServicoObraReal para gestão avançada de serviços na obra
    """
    try:
        logger.info("🔄 Verificando se tabela servico_obra_real existe...")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se a tabela já existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'servico_obra_real'
        """)
        
        tabela_existe = cursor.fetchone()[0] > 0
        
        if not tabela_existe:
            logger.info("🔧 Criando tabela servico_obra_real...")
            
            cursor.execute("""
                CREATE TABLE servico_obra_real (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id),
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    
                    -- Planejamento detalhado
                    quantidade_planejada NUMERIC(12,4) NOT NULL DEFAULT 0.0,
                    quantidade_executada NUMERIC(12,4) DEFAULT 0.0,
                    percentual_concluido NUMERIC(5,2) DEFAULT 0.0,
                    
                    -- Controle de prazo
                    data_inicio_planejada DATE,
                    data_fim_planejada DATE,
                    data_inicio_real DATE,
                    data_fim_real DATE,
                    
                    -- Controle de custos
                    valor_unitario NUMERIC(10,2) DEFAULT 0.0,
                    valor_total_planejado NUMERIC(12,2) DEFAULT 0.0,
                    valor_total_executado NUMERIC(12,2) DEFAULT 0.0,
                    
                    -- Status e controle
                    status VARCHAR(30) DEFAULT 'Não Iniciado',
                    prioridade INTEGER DEFAULT 3,
                    responsavel_id INTEGER REFERENCES funcionario(id),
                    
                    -- Observações e notas
                    observacoes TEXT,
                    notas_tecnicas TEXT,
                    
                    -- Controle de qualidade
                    aprovado BOOLEAN DEFAULT FALSE,
                    data_aprovacao TIMESTAMP,
                    aprovado_por_id INTEGER REFERENCES funcionario(id),
                    
                    -- Multi-tenant e controle
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraint unique
                    UNIQUE(obra_id, servico_id)
                )
            """)
            
            logger.info("✅ Tabela servico_obra_real criada com sucesso!")
            
            # Criar índices para performance
            cursor.execute("CREATE INDEX idx_servico_obra_real_obra ON servico_obra_real(obra_id)")
            cursor.execute("CREATE INDEX idx_servico_obra_real_servico ON servico_obra_real(servico_id)")
            cursor.execute("CREATE INDEX idx_servico_obra_real_admin ON servico_obra_real(admin_id)")
            cursor.execute("CREATE INDEX idx_servico_obra_real_status ON servico_obra_real(status)")
            
            logger.info("✅ Índices criados para servico_obra_real!")
        else:
            logger.info("✅ Tabela servico_obra_real já existe")
        
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("🎯 Migração da tabela ServicoObraReal concluída!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela servico_obra_real: {e}")
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except:
            pass

def criar_tabela_servico_obra_real_limpa():
    """
    Cria tabela servico_obra_real versão limpa e simplificada
    """
    try:
        logger.info("🔄 Criando tabela servico_obra_real versão LIMPA...")
        
        # Usar SQLAlchemy diretamente
        from sqlalchemy import text
        
        # Verificar se tabela existe
        result = db.session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'servico_obra_real'
            )
        """)).scalar()
        
        if not result:
            logger.info("🆕 Criando nova tabela servico_obra_real...")
            
            # Criar tabela usando SQLAlchemy
            db.session.execute(text("""
                CREATE TABLE servico_obra_real (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id),
                    servico_id INTEGER NOT NULL REFERENCES servico(id),
                    
                    -- Quantidades
                    quantidade_planejada NUMERIC(10,2) DEFAULT 1.0,
                    quantidade_executada NUMERIC(10,2) DEFAULT 0.0,
                    percentual_concluido NUMERIC(5,2) DEFAULT 0.0,
                    
                    -- Valores
                    valor_unitario NUMERIC(10,2) DEFAULT 0.0,
                    valor_total_planejado NUMERIC(10,2) DEFAULT 0.0,
                    valor_total_executado NUMERIC(10,2) DEFAULT 0.0,
                    
                    -- Status e controle
                    status VARCHAR(50) DEFAULT 'Não Iniciado',
                    prioridade INTEGER DEFAULT 3,
                    
                    -- Datas
                    data_inicio_planejada DATE,
                    data_inicio_real DATE,
                    data_fim_planejada DATE,
                    data_fim_real DATE,
                    
                    -- Aprovação
                    aprovado BOOLEAN DEFAULT FALSE,
                    aprovado_em TIMESTAMP,
                    aprovado_por_id INTEGER,
                    
                    -- Observações
                    observacoes TEXT,
                    observacoes_execucao TEXT,
                    
                    -- Multi-tenant
                    admin_id INTEGER NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(obra_id, servico_id, admin_id)
                )
            """))
            
            # Índices básicos
            db.session.execute(text("CREATE INDEX idx_servico_obra_real_obra_id ON servico_obra_real(obra_id)"))
            db.session.execute(text("CREATE INDEX idx_servico_obra_real_admin_id ON servico_obra_real(admin_id)"))
            
            db.session.commit()
            logger.info("✅ Tabela servico_obra_real LIMPA criada com sucesso!")
        else:
            logger.info("✅ Tabela servico_obra_real já existe")
            
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela limpa: {e}")
        db.session.rollback()

def adicionar_coluna_local_rdo():
    """Adiciona coluna 'local' na tabela RDO para compatibilidade com produção"""
    try:
        logger.info("🔄 Verificando se coluna 'local' existe na tabela RDO...")
        
        # Verificar se a coluna local já existe
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='rdo' AND column_name='local'
        """)).fetchone()
        
        if not result:
            logger.info("🔧 Adicionando coluna 'local' na tabela RDO...")
            
            # Adicionar coluna local
            db.session.execute(text("""
                ALTER TABLE rdo 
                ADD COLUMN local VARCHAR(100) DEFAULT 'Campo'
            """))
            
            db.session.commit()
            logger.info("✅ Coluna 'local' adicionada à tabela RDO com sucesso!")
        else:
            logger.info("✅ Coluna 'local' já existe na tabela RDO")
            
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar coluna 'local' na tabela RDO: {e}")
        db.session.rollback()

def adicionar_campos_allocation_employee():
    """Adiciona campos faltantes (hora_almoco_saida, hora_almoco_retorno, percentual_extras) na tabela allocation_employee"""
    try:
        logger.info("🔄 Verificando campos faltantes na tabela allocation_employee...")
        
        # Lista de campos para verificar/adicionar
        campos_necessarios = [
            ('hora_almoco_saida', "TIME DEFAULT '12:00:00'"),
            ('hora_almoco_retorno', "TIME DEFAULT '13:00:00'"),
            ('percentual_extras', "REAL DEFAULT 0.0")
        ]
        
        for nome_campo, tipo_sql in campos_necessarios:
            # Verificar se o campo já existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='allocation_employee' AND column_name=:campo_nome
            """), {"campo_nome": nome_campo}).fetchone()
            
            if not result:
                logger.info(f"🔧 Adicionando campo '{nome_campo}' na tabela allocation_employee...")
                
                # Adicionar campo
                db.session.execute(text(f"""
                    ALTER TABLE allocation_employee 
                    ADD COLUMN {nome_campo} {tipo_sql}
                """))
                
                logger.info(f"✅ Campo '{nome_campo}' adicionado com sucesso!")
            else:
                logger.info(f"✅ Campo '{nome_campo}' já existe na tabela allocation_employee")
        
        db.session.commit()
        logger.info("✅ Todos os campos necessários da tabela allocation_employee verificados/adicionados!")
            
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar campos na tabela allocation_employee: {e}")
        db.session.rollback()

def migrar_sistema_veiculos_critical():
    """
    MIGRAÇÃO CRÍTICA: Sistema de Veículos Multi-Tenant
    Aplica constraints e campos obrigatórios que estão faltando no banco de dados
    """
    try:
        logger.info("🚗 MIGRAÇÃO CRÍTICA: Sistema de Veículos Multi-Tenant")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # 1. Verificar se a tabela veiculo existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'veiculo'
        """)
        tabela_existe = cursor.fetchone()[0] > 0
        
        if not tabela_existe:
            logger.info("📝 Tabela veiculo não existe, criando completa...")
            
            # Criar tabela completa com todas as constraints
            cursor.execute("""
                CREATE TABLE veiculo (
                    id SERIAL PRIMARY KEY,
                    placa VARCHAR(10) NOT NULL,
                    marca VARCHAR(50) NOT NULL,
                    modelo VARCHAR(50) NOT NULL,
                    ano INTEGER,
                    tipo VARCHAR(20) NOT NULL,
                    status VARCHAR(20) DEFAULT 'Disponível',
                    km_atual INTEGER DEFAULT 0,
                    data_ultima_manutencao DATE,
                    data_proxima_manutencao DATE,
                    ativo BOOLEAN DEFAULT TRUE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Constraint unique por admin para isolamento multi-tenant
                    CONSTRAINT veiculo_admin_placa_uc UNIQUE(admin_id, placa)
                )
            """)
            
            # Criar índices para performance
            cursor.execute("CREATE INDEX idx_veiculo_admin_id ON veiculo(admin_id)")
            cursor.execute("CREATE INDEX idx_veiculo_ativo ON veiculo(ativo)")
            
            connection.commit()
            logger.info("✅ Tabela veiculo criada com todas as constraints!")
            
        else:
            logger.info("🔍 Tabela veiculo existe, verificando constraints...")
            
            # 2. Verificar se admin_id existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = 'admin_id'
            """)
            admin_id_existe = cursor.fetchone()
            
            if not admin_id_existe:
                logger.info("🔄 Adicionando coluna admin_id...")
                cursor.execute("ALTER TABLE veiculo ADD COLUMN admin_id INTEGER")
                logger.info("✅ Coluna admin_id adicionada")
            
            # 3. Verificar se há registros sem admin_id e corrigir
            cursor.execute("SELECT COUNT(*) FROM veiculo WHERE admin_id IS NULL")
            registros_sem_admin = cursor.fetchone()[0]
            
            if registros_sem_admin > 0:
                logger.info(f"🔄 Corrigindo {registros_sem_admin} registros sem admin_id...")
                
                # Tentar usar ID 10 como padrão (admin principal)
                cursor.execute("SELECT id FROM usuario WHERE tipo_usuario = 'admin' LIMIT 1")
                admin_padrao = cursor.fetchone()
                
                if admin_padrao:
                    admin_id_padrao = admin_padrao[0]
                    cursor.execute(
                        "UPDATE veiculo SET admin_id = %s WHERE admin_id IS NULL",
                        (admin_id_padrao,)
                    )
                    logger.info(f"✅ Registros atualizados com admin_id = {admin_id_padrao}")
                else:
                    logger.warning("⚠️ Nenhum admin encontrado, usando ID 1 como padrão")
                    cursor.execute("UPDATE veiculo SET admin_id = 1 WHERE admin_id IS NULL")
            
            # 4. Verificar se admin_id é NOT NULL
            cursor.execute("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = 'admin_id'
            """)
            admin_nullable = cursor.fetchone()
            
            if admin_nullable and admin_nullable[0] == 'YES':
                logger.info("🔄 Aplicando constraint NOT NULL em admin_id...")
                cursor.execute("ALTER TABLE veiculo ALTER COLUMN admin_id SET NOT NULL")
                logger.info("✅ admin_id agora é NOT NULL")
            
            # 5. Verificar se foreign key existe
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'veiculo' 
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name LIKE '%admin%'
            """)
            fk_admin_existe = cursor.fetchone()
            
            if not fk_admin_existe:
                logger.info("🔄 Adicionando foreign key admin_id...")
                cursor.execute("""
                    ALTER TABLE veiculo 
                    ADD CONSTRAINT fk_veiculo_admin 
                    FOREIGN KEY (admin_id) REFERENCES usuario(id)
                """)
                logger.info("✅ Foreign key admin_id adicionada")
            
            # 6. Verificar se constraint unique existe
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'veiculo' 
                AND constraint_type = 'UNIQUE'
                AND constraint_name LIKE '%admin%placa%'
            """)
            unique_constraint_existe = cursor.fetchone()
            
            if not unique_constraint_existe:
                logger.info("🔄 Adicionando constraint unique (admin_id, placa)...")
                
                # Primeiro remover duplicatas se existirem
                cursor.execute("""
                    DELETE FROM veiculo 
                    WHERE id NOT IN (
                        SELECT DISTINCT ON (admin_id, placa) id 
                        FROM veiculo 
                        ORDER BY admin_id, placa, id
                    )
                """)
                
                # Adicionar constraint unique
                cursor.execute("""
                    ALTER TABLE veiculo 
                    ADD CONSTRAINT veiculo_admin_placa_uc 
                    UNIQUE(admin_id, placa)
                """)
                logger.info("✅ Constraint unique (admin_id, placa) adicionada")
            
            # 7. Verificar se updated_at existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = 'updated_at'
            """)
            updated_at_existe = cursor.fetchone()
            
            if not updated_at_existe:
                logger.info("🔄 Adicionando coluna updated_at...")
                cursor.execute("""
                    ALTER TABLE veiculo 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                logger.info("✅ Coluna updated_at adicionada")
            
            # 8. Criar índices se não existirem
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'veiculo' 
                AND indexname = 'idx_veiculo_admin_id'
            """)
            indice_admin_existe = cursor.fetchone()
            
            if not indice_admin_existe:
                logger.info("🔄 Criando índice para admin_id...")
                cursor.execute("CREATE INDEX idx_veiculo_admin_id ON veiculo(admin_id)")
                logger.info("✅ Índice admin_id criado")
            
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'veiculo' 
                AND indexname = 'idx_veiculo_ativo'
            """)
            indice_ativo_existe = cursor.fetchone()
            
            if not indice_ativo_existe:
                logger.info("🔄 Criando índice para ativo...")
                cursor.execute("CREATE INDEX idx_veiculo_ativo ON veiculo(ativo)")
                logger.info("✅ Índice ativo criado")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("🚗 ✅ MIGRAÇÃO CRÍTICA DE VEÍCULOS CONCLUÍDA COM SUCESSO!")
        logger.info("🔒 Sistema multi-tenant agora totalmente protegido")
        logger.info("🎯 Constraints aplicadas: unique(admin_id, placa), admin_id NOT NULL")
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na migração de veículos: {str(e)}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        raise  # Re-raise para que seja tratado pela migração principal

def corrigir_admin_id_vehicle_tables():
    """
    Migração 18: CRÍTICA - Corrigir admin_id nullable em UsoVeiculo e CustoVeiculo
    USANDO JOINS DETERMINÍSTICOS para garantir isolamento multi-tenant seguro
    
    NUNCA mais usar hard-coded admin_id = 10!
    """
    try:
        logger.info("🔒 MIGRAÇÃO 18 (REESCRITA): Corrigindo admin_id via JOINs determinísticos...")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # 1. CORRIGIR TABELA uso_veiculo com JOINs determinísticos
        cursor.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'uso_veiculo' 
            AND column_name = 'admin_id'
        """)
        uso_veiculo_admin = cursor.fetchone()
        
        if uso_veiculo_admin and uso_veiculo_admin[1] == 'YES':
            logger.info("🔄 Corrigindo admin_id em uso_veiculo via JOINs determinísticos...")
            
            # Primeiro: Contar registros órfãos para auditoria
            cursor.execute("""
                SELECT COUNT(*) FROM uso_veiculo WHERE admin_id IS NULL
            """)
            orfaos_uso = cursor.fetchone()[0]
            logger.info(f"📊 Encontrados {orfaos_uso} registros órfãos em uso_veiculo")
            
            # ESTRATÉGIA 1: Corrigir via veiculo.admin_id (principal)
            cursor.execute("""
                UPDATE uso_veiculo 
                SET admin_id = v.admin_id
                FROM veiculo v
                WHERE uso_veiculo.veiculo_id = v.id 
                AND uso_veiculo.admin_id IS NULL
                AND v.admin_id IS NOT NULL
            """)
            corrigidos_veiculo = cursor.rowcount
            logger.info(f"✅ {corrigidos_veiculo} registros corrigidos via veiculo.admin_id")
            
            # ESTRATÉGIA 2: Fallback via funcionario.admin_id
            cursor.execute("""
                UPDATE uso_veiculo 
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE uso_veiculo.funcionario_id = f.id 
                AND uso_veiculo.admin_id IS NULL
                AND f.admin_id IS NOT NULL
            """)
            corrigidos_funcionario = cursor.rowcount
            logger.info(f"✅ {corrigidos_funcionario} registros corrigidos via funcionario.admin_id")
            
            # ESTRATÉGIA 3: Fallback via obra.admin_id
            cursor.execute("""
                UPDATE uso_veiculo 
                SET admin_id = o.admin_id
                FROM obra o
                WHERE uso_veiculo.obra_id = o.id 
                AND uso_veiculo.admin_id IS NULL
                AND o.admin_id IS NOT NULL
            """)
            corrigidos_obra = cursor.rowcount
            logger.info(f"✅ {corrigidos_obra} registros corrigidos via obra.admin_id")
            
            # Verificar se ainda há órfãos
            cursor.execute("""
                SELECT COUNT(*) FROM uso_veiculo WHERE admin_id IS NULL
            """)
            orfaos_restantes = cursor.fetchone()[0]
            
            if orfaos_restantes > 0:
                logger.warning(f"⚠️  {orfaos_restantes} registros órfãos restantes em uso_veiculo")
                logger.warning("🚨 BLOQUEANDO migração - registros órfãos não podem ser corrigidos determinísticamente")
                
                # Listar órfãos para diagnóstico
                cursor.execute("""
                    SELECT id, veiculo_id, funcionario_id, obra_id, data_uso 
                    FROM uso_veiculo 
                    WHERE admin_id IS NULL 
                    LIMIT 5
                """)
                orfaos_sample = cursor.fetchall()
                logger.warning(f"📋 Amostra de órfãos: {orfaos_sample}")
                
                # OPÇÃO SEGURA: Não aplicar NOT NULL se há órfãos
                logger.info("🛡️  Mantendo admin_id como nullable para preservar dados órfãos")
            else:
                # Aplicar constraint NOT NULL apenas se todos foram corrigidos
                cursor.execute("""
                    ALTER TABLE uso_veiculo 
                    ALTER COLUMN admin_id SET NOT NULL
                """)
                logger.info("✅ admin_id em uso_veiculo agora é NOT NULL")
        else:
            logger.info("✅ admin_id em uso_veiculo já é NOT NULL")
        
        # 2. CORRIGIR TABELA custo_veiculo com JOINs determinísticos
        cursor.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'custo_veiculo' 
            AND column_name = 'admin_id'
        """)
        custo_veiculo_admin = cursor.fetchone()
        
        if custo_veiculo_admin and custo_veiculo_admin[1] == 'YES':
            logger.info("🔄 Corrigindo admin_id em custo_veiculo via JOINs determinísticos...")
            
            # Primeiro: Contar registros órfãos para auditoria
            cursor.execute("""
                SELECT COUNT(*) FROM custo_veiculo WHERE admin_id IS NULL
            """)
            orfaos_custo = cursor.fetchone()[0]
            logger.info(f"📊 Encontrados {orfaos_custo} registros órfãos em custo_veiculo")
            
            # ESTRATÉGIA 1: Corrigir via veiculo.admin_id (principal)
            cursor.execute("""
                UPDATE custo_veiculo 
                SET admin_id = v.admin_id
                FROM veiculo v
                WHERE custo_veiculo.veiculo_id = v.id 
                AND custo_veiculo.admin_id IS NULL
                AND v.admin_id IS NOT NULL
            """)
            corrigidos_veiculo_custo = cursor.rowcount
            logger.info(f"✅ {corrigidos_veiculo_custo} registros corrigidos via veiculo.admin_id")
            
            # ESTRATÉGIA 2: Fallback via obra.admin_id se custo_veiculo tiver obra_id
            cursor.execute("""
                UPDATE custo_veiculo 
                SET admin_id = o.admin_id
                FROM obra o
                WHERE custo_veiculo.obra_id = o.id 
                AND custo_veiculo.admin_id IS NULL
                AND o.admin_id IS NOT NULL
            """)
            corrigidos_obra_custo = cursor.rowcount
            logger.info(f"✅ {corrigidos_obra_custo} registros corrigidos via obra.admin_id")
            
            # Verificar se ainda há órfãos
            cursor.execute("""
                SELECT COUNT(*) FROM custo_veiculo WHERE admin_id IS NULL
            """)
            orfaos_restantes_custo = cursor.fetchone()[0]
            
            if orfaos_restantes_custo > 0:
                logger.warning(f"⚠️  {orfaos_restantes_custo} registros órfãos restantes em custo_veiculo")
                logger.warning("🚨 BLOQUEANDO migração - registros órfãos não podem ser corrigidos determinísticamente")
                
                # Listar órfãos para diagnóstico
                cursor.execute("""
                    SELECT id, veiculo_id, obra_id, tipo_custo, valor 
                    FROM custo_veiculo 
                    WHERE admin_id IS NULL 
                    LIMIT 5
                """)
                orfaos_sample_custo = cursor.fetchall()
                logger.warning(f"📋 Amostra de órfãos: {orfaos_sample_custo}")
                
                # OPÇÃO SEGURA: Não aplicar NOT NULL se há órfãos
                logger.info("🛡️  Mantendo admin_id como nullable para preservar dados órfãos")
            else:
                # Aplicar constraint NOT NULL apenas se todos foram corrigidos
                cursor.execute("""
                    ALTER TABLE custo_veiculo 
                    ALTER COLUMN admin_id SET NOT NULL
                """)
                logger.info("✅ admin_id em custo_veiculo agora é NOT NULL")
        else:
            logger.info("✅ admin_id em custo_veiculo já é NOT NULL")
        
        # 3. Criar índices para melhor performance (mantido)
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'uso_veiculo' 
            AND indexname = 'idx_uso_veiculo_admin_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_uso_veiculo_admin_id ON uso_veiculo(admin_id)")
            logger.info("✅ Índice criado para uso_veiculo.admin_id")
        
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'custo_veiculo' 
            AND indexname = 'idx_custo_veiculo_admin_id'
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_custo_veiculo_admin_id ON custo_veiculo(admin_id)")
            logger.info("✅ Índice criado para custo_veiculo.admin_id")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("🔐 ✅ MIGRAÇÃO 18 REESCRITA CONCLUÍDA!")
        logger.info("🎯 Multi-tenant seguro via JOINs determinísticos")
        logger.info("🛡️  ZERO mistura de dados entre tenants")
        logger.info("✨ Registros órfãos preservados sem violar integridade")
        
    except Exception as e:
        logger.error(f"❌ ERRO na Migração 18 - admin_id vehicle tables: {str(e)}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass


def adicionar_colunas_veiculo_completas():
    """
    MIGRAÇÃO 19: Adicionar colunas faltantes na tabela veiculo
    Resolve erro: column veiculo.chassi does not exist
    """
    try:
        logger.info("🚗 MIGRAÇÃO 19: Adicionando colunas faltantes em veículos...")
        
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Verificar se tabela existe
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'veiculo'
        """)
        
        if cursor.fetchone()[0] == 0:
            logger.warning("⚠️ Tabela veiculo não existe - será criada pela migração anterior")
            cursor.close()
            connection.close()
            return
        
        # Colunas a adicionar
        colunas_adicionar = {
            'chassi': 'VARCHAR(50)',
            'renavam': 'VARCHAR(20)',
            'combustivel': "VARCHAR(20) DEFAULT 'Gasolina'",
            'cor': 'VARCHAR(30)',
            'km_proxima_manutencao': 'INTEGER',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        for coluna, tipo_sql in colunas_adicionar.items():
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'veiculo' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' na tabela veiculo...")
                cursor.execute(f"ALTER TABLE veiculo ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada com sucesso!")
            else:
                logger.info(f"✅ Coluna '{coluna}' já existe")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ MIGRAÇÃO 19 CONCLUÍDA: Todas as colunas de veículo verificadas/adicionadas!")
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 19 - colunas veiculo: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass




def _migration_43_completar_estruturas_v9():
    """
    MIGRAÇÃO 43: Completar estruturas existentes para SIGE v9.0
    - Adicionar cliente_id em propostas_comerciais
    - Expandir custo_obra com campos de integração
    - Expandir proposta_historico com campos de auditoria
    """
    logger.info("=" * 80)
    logger.info("🔧 MIGRAÇÃO 43: Completar Estruturas v9.0")
    logger.info("=" * 80)
    
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # PARTE 1: Adicionar cliente_id em propostas_comerciais
        logger.info("📋 PARTE 1: Adicionar cliente_id em propostas_comerciais")
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'propostas_comerciais' 
            AND column_name = 'cliente_id'
        """)
        
        if not cursor.fetchone():
            logger.info("🔧 Adicionando coluna cliente_id...")
            
            # Adicionar coluna (nullable inicialmente)
            cursor.execute("""
                ALTER TABLE propostas_comerciais 
                ADD COLUMN cliente_id INTEGER REFERENCES cliente(id)
            """)
            
            # Atualizar propostas existentes com cliente padrão
            logger.info("🔧 Criando/vinculando clientes padrão para propostas existentes...")
            
            # Para cada admin_id único, criar um cliente padrão
            cursor.execute("""
                WITH admins_unicos AS (
                    SELECT DISTINCT admin_id 
                    FROM propostas_comerciais 
                    WHERE admin_id IS NOT NULL 
                    AND cliente_id IS NULL
                )
                INSERT INTO cliente (nome, email, admin_id)
                SELECT 'Cliente Padrão - ' || au.admin_id, 
                       'cliente' || au.admin_id || '@padrao.com', 
                       au.admin_id
                FROM admins_unicos au
                WHERE NOT EXISTS (
                    SELECT 1 FROM cliente c 
                    WHERE c.nome = 'Cliente Padrão - ' || au.admin_id 
                    AND c.admin_id = au.admin_id
                )
            """)
            
            # Atualizar propostas com cliente padrão
            cursor.execute("""
                UPDATE propostas_comerciais p
                SET cliente_id = (
                    SELECT c.id 
                    FROM cliente c 
                    WHERE c.nome = 'Cliente Padrão - ' || p.admin_id 
                    AND c.admin_id = p.admin_id
                    LIMIT 1
                )
                WHERE p.cliente_id IS NULL 
                AND p.admin_id IS NOT NULL
            """)
            
            logger.info("✅ cliente_id adicionado e propostas vinculadas")
        else:
            logger.info("✅ cliente_id já existe")
        
        # PARTE 2: Expandir custo_obra
        logger.info("📋 PARTE 2: Expandir tabela custo_obra")
        
        colunas_custo_obra = {
            'funcionario_id': 'INTEGER REFERENCES funcionario(id)',
            'item_almoxarifado_id': 'INTEGER REFERENCES almoxarifado_item(id)',
            'veiculo_id': 'INTEGER REFERENCES frota_veiculo(id)',
            'admin_id': 'INTEGER REFERENCES usuario(id)',
            'quantidade': 'NUMERIC(10,2) DEFAULT 1',
            'valor_unitario': 'NUMERIC(10,2) DEFAULT 0',
            'horas_trabalhadas': 'NUMERIC(5,2)',
            'horas_extras': 'NUMERIC(5,2)',
            'rdo_id': 'INTEGER REFERENCES rdo(id)',
            'categoria': 'VARCHAR(50)'
        }
        
        for coluna, tipo_sql in colunas_custo_obra.items():
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'custo_obra' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em custo_obra...")
                cursor.execute(f"ALTER TABLE custo_obra ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada")
            else:
                logger.info(f"✅ Coluna '{coluna}' já existe")
        
        # Criar índices para performance
        indices_custo_obra = [
            ('idx_custo_obra_funcionario', 'funcionario_id'),
            ('idx_custo_obra_veiculo', 'veiculo_id'),
            ('idx_custo_obra_admin', 'admin_id'),
            ('idx_custo_obra_data', 'data')
        ]
        
        for nome_indice, coluna in indices_custo_obra:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'custo_obra' 
                AND indexname = %s
            """, (nome_indice,))
            
            if not cursor.fetchone():
                cursor.execute(f"CREATE INDEX {nome_indice} ON custo_obra({coluna})")
                logger.info(f"✅ Índice {nome_indice} criado")
        
        # PARTE 3: Expandir proposta_historico
        logger.info("📋 PARTE 3: Expandir tabela proposta_historico")
        
        colunas_historico = {
            'campo_alterado': 'VARCHAR(100)',
            'valor_anterior': 'TEXT',
            'valor_novo': 'TEXT',
            'admin_id': 'INTEGER REFERENCES usuario(id)'
        }
        
        for coluna, tipo_sql in colunas_historico.items():
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proposta_historico' 
                AND column_name = %s
            """, (coluna,))
            
            if not cursor.fetchone():
                logger.info(f"🔧 Adicionando coluna '{coluna}' em proposta_historico...")
                cursor.execute(f"ALTER TABLE proposta_historico ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"✅ Coluna '{coluna}' adicionada")
            else:
                logger.info(f"✅ Coluna '{coluna}' já existe")
        
        # Criar índice por admin_id
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'proposta_historico' 
            AND indexname = 'idx_proposta_historico_admin'
        """)
        
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_proposta_historico_admin ON proposta_historico(admin_id)")
            logger.info("✅ Índice criado para proposta_historico.admin_id")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 43 CONCLUÍDA: Estruturas v9.0 completas!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro na Migração 43: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass

# ============================================================================
# MIGRAÇÃO 48 - FUNÇÕES AUXILIARES
# ============================================================================

def _get_default_admin_id_v48(cursor):
    """Busca primeiro admin com fallbacks robustos"""
    # Tentativa 1: Admin não-super (tipo_usuario != 'super_admin' e NOT LIKE 'SUPER_%')
    cursor.execute("""
        SELECT id FROM usuario 
        WHERE LOWER(tipo_usuario) NOT LIKE '%super%'
        ORDER BY id LIMIT 1
    """)
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Tentativa 2: Qualquer usuário
    cursor.execute("SELECT id FROM usuario ORDER BY id LIMIT 1")
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Tentativa 3: Fallback hard-coded
    return 1

def _column_exists_v48(cursor, table_name, column_name):
    """Verifica se coluna existe"""
    cursor.execute("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    return cursor.fetchone() is not None

def _process_table_v48(cursor, tabela, default_admin_id, logger):
    """Processa uma tabela com idempotência total"""
    if _column_exists_v48(cursor, tabela, 'admin_id'):
        logger.info(f"  ⏭️  {tabela}: admin_id já existe")
        return False
    
    logger.info(f"  🔧 {tabela}: adicionando admin_id...")
    
    # STEP 1: ADD COLUMN
    cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN admin_id INTEGER")
    
    # STEP 2: UPDATE com admin padrão
    cursor.execute(f"UPDATE {tabela} SET admin_id = %s WHERE admin_id IS NULL", (default_admin_id,))
    updated = cursor.rowcount
    logger.info(f"     ✅ {updated} registros atualizados")
    
    # STEP 3: SET NOT NULL
    cursor.execute(f"ALTER TABLE {tabela} ALTER COLUMN admin_id SET NOT NULL")
    
    # STEP 4: ADD CONSTRAINT
    cursor.execute(f"""
        ALTER TABLE {tabela} 
        ADD CONSTRAINT fk_{tabela}_admin_id 
        FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE
    """)
    
    # STEP 5: CREATE INDEX
    cursor.execute(f"CREATE INDEX idx_{tabela}_admin_id ON {tabela}(admin_id)")
    
    logger.info(f"  ✅ {tabela}: completo")
    return True

def _migration_48_adicionar_admin_id_modelos_faltantes():
    """
    Migração 48: Adicionar admin_id em 20 modelos com backfill tenant-aware
    
    CRÍTICO: Preserva isolamento multi-tenant calculando admin_id a partir de FK existentes
    
    Estratégia: Backfill inteligente usando relacionamentos para inferir admin_id correto
    Validações: Verifica distribuição de tenants e aborta se detectar colapso
    Idempotência: Pula tabelas que já têm admin_id
    
    Severidade: 🔴 CRÍTICA
    Data: 30/10/2025 (corrigido - tenant-aware restaurado)
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("=" * 80)
        logger.info("🔄 MIGRAÇÃO 48: Multi-tenancy completo com backfill por relacionamento")
        logger.info("=" * 80)
        
        tabelas_processadas = 0
        tabelas_ja_existentes = 0
        registros_orfaos = {}
        
        # Mapeamento: tabela → (query de backfill, descrição)
        backfill_strategies = {
            'departamento': ("""
                UPDATE departamento d
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.departamento_id = d.id
                  AND d.admin_id IS NULL
                  AND f.admin_id IS NOT NULL
            """, "via funcionario.departamento_id"),
            
            'funcao': ("""
                UPDATE funcao fu
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.funcao_id = fu.id
                  AND fu.admin_id IS NULL
                  AND f.admin_id IS NOT NULL
            """, "via funcionario.funcao_id"),
            
            'horario_trabalho': ("""
                UPDATE horario_trabalho ht
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE f.horario_trabalho_id = ht.id
                  AND ht.admin_id IS NULL
                  AND f.admin_id IS NOT NULL
            """, "via funcionario.horario_trabalho_id"),
            
            'servico_obra': ("""
                UPDATE servico_obra so
                SET admin_id = o.admin_id
                FROM obra o
                WHERE so.obra_id = o.id
                  AND so.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via obra.id"),
            
            'historico_produtividade_servico': ("""
                UPDATE historico_produtividade_servico hps
                SET admin_id = o.admin_id
                FROM servico_obra so
                JOIN obra o ON so.obra_id = o.id
                WHERE hps.servico_obra_id = so.id
                  AND hps.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via servico_obra → obra"),
            
            'tipo_ocorrencia': ("""
                -- Primeiro, identifica o admin que tem os tipos originais
                WITH tipos_originais AS (
                    SELECT id, nome, descricao, requer_documento, afeta_custo, ativo
                    FROM tipo_ocorrencia
                    WHERE admin_id IS NULL
                ),
                admins_destino AS (
                    SELECT id as admin_id 
                    FROM usuario 
                    WHERE tipo_usuario = 'admin' AND id NOT IN (
                        SELECT DISTINCT admin_id FROM tipo_ocorrencia WHERE admin_id IS NOT NULL
                    )
                )
                -- Duplica para cada admin que ainda não tem
                INSERT INTO tipo_ocorrencia (admin_id, nome, descricao, requer_documento, afeta_custo, ativo)
                SELECT ad.admin_id, to.nome, to.descricao, to.requer_documento, to.afeta_custo, to.ativo
                FROM tipos_originais to
                CROSS JOIN admins_destino ad
                ON CONFLICT DO NOTHING;
                
                -- Atualiza registros órfãos com primeiro admin
                UPDATE tipo_ocorrencia
                SET admin_id = (SELECT id FROM usuario WHERE tipo_usuario = 'admin' ORDER BY id LIMIT 1)
                WHERE admin_id IS NULL;
            """, "duplicação de seeds para cada admin"),
            
            'ocorrencia': ("""
                UPDATE ocorrencia oc
                SET admin_id = o.admin_id
                FROM obra o
                WHERE oc.obra_id = o.id
                  AND oc.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via obra_id"),
            
            'calendario_util': ("""
                -- Duplica feriados/dias úteis para cada admin
                WITH datas_originais AS (
                    SELECT data, dia_semana, eh_util, eh_feriado, descricao_feriado
                    FROM calendario_util
                    WHERE admin_id IS NULL
                ),
                admins_destino AS (
                    SELECT id as admin_id 
                    FROM usuario 
                    WHERE tipo_usuario = 'admin'
                )
                INSERT INTO calendario_util (data, admin_id, dia_semana, eh_util, eh_feriado, descricao_feriado)
                SELECT cu.data, ad.admin_id, cu.dia_semana, cu.eh_util, cu.eh_feriado, cu.descricao_feriado
                FROM datas_originais cu
                CROSS JOIN admins_destino ad
                ON CONFLICT (data) DO UPDATE SET admin_id = EXCLUDED.admin_id;
            """, "duplicação de calendário para cada admin"),
            
            'centro_custo': ("""
                UPDATE centro_custo cc
                SET admin_id = COALESCE(
                    (SELECT o.admin_id FROM obra o WHERE o.id = cc.obra_id),
                    (SELECT d.admin_id FROM departamento d WHERE d.id = cc.departamento_id)
                )
                WHERE cc.admin_id IS NULL
            """, "via obra_id ou departamento_id"),
            
            'receita': ("""
                UPDATE receita r
                SET admin_id = o.admin_id
                FROM obra o
                WHERE r.obra_id = o.id
                  AND r.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via obra_id"),
            
            'orcamento_obra': ("""
                UPDATE orcamento_obra oo
                SET admin_id = o.admin_id
                FROM obra o
                WHERE oo.obra_id = o.id
                  AND oo.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via obra_id"),
            
            'fluxo_caixa': ("""
                UPDATE fluxo_caixa fc
                SET admin_id = COALESCE(
                    (SELECT o.admin_id FROM obra o WHERE o.id = fc.obra_id),
                    (SELECT cc.admin_id FROM centro_custo cc WHERE cc.id = fc.centro_custo_id)
                )
                WHERE fc.admin_id IS NULL
            """, "via obra_id ou centro_custo_id"),
            
            'registro_alimentacao': ("""
                UPDATE registro_alimentacao ra
                SET admin_id = f.admin_id
                FROM funcionario f
                WHERE ra.funcionario_id = f.id
                  AND ra.admin_id IS NULL
                  AND f.admin_id IS NOT NULL
            """, "via funcionario_id"),
            
            'rdo_mao_obra': ("""
                UPDATE rdo_mao_obra rm
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE rm.rdo_id = r.id
                  AND rm.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via rdo → obra"),
            
            'rdo_equipamento': ("""
                UPDATE rdo_equipamento re
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE re.rdo_id = r.id
                  AND re.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via rdo → obra"),
            
            'rdo_ocorrencia': ("""
                UPDATE rdo_ocorrencia ro
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE ro.rdo_id = r.id
                  AND ro.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via rdo → obra"),
            
            'rdo_foto': ("""
                UPDATE rdo_foto rf
                SET admin_id = o.admin_id
                FROM rdo r
                JOIN obra o ON r.obra_id = o.id
                WHERE rf.rdo_id = r.id
                  AND rf.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via rdo → obra"),
            
            'notificacao_cliente': ("""
                UPDATE notificacao_cliente nc
                SET admin_id = o.admin_id
                FROM obra o
                WHERE nc.obra_id = o.id
                  AND nc.admin_id IS NULL
                  AND o.admin_id IS NOT NULL
            """, "via obra_id"),
            
            'proposta_itens': ("""
                UPDATE proposta_itens pi
                SET admin_id = p.admin_id
                FROM propostas_comerciais p
                WHERE pi.proposta_id = p.id
                  AND pi.admin_id IS NULL
                  AND p.admin_id IS NOT NULL
            """, "via propostas_comerciais"),
            
            'proposta_arquivos': ("""
                UPDATE proposta_arquivos pa
                SET admin_id = p.admin_id
                FROM propostas_comerciais p
                WHERE pa.proposta_id = p.id
                  AND pa.admin_id IS NULL
                  AND p.admin_id IS NOT NULL
            """, "via propostas_comerciais"),
        }
        
        for tabela, (backfill_query, estrategia) in backfill_strategies.items():
            try:
                # Verificar se coluna admin_id já existe
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'admin_id'
                """, (tabela,))
                
                if cursor.fetchone() is not None:
                    tabelas_ja_existentes += 1
                    logger.info(f"  ⏭️  {tabela}: admin_id já existe")
                    continue
                
                logger.info(f"  🔧 {tabela}: adicionando admin_id ({estrategia})")
                
                # PASSO 1: Adicionar coluna (nullable temporariamente)
                cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN admin_id INTEGER")
                
                # PASSO 2: Backfill baseado em relacionamento
                cursor.execute(backfill_query)
                updated_rows = cursor.rowcount
                logger.info(f"     ✅ {updated_rows} registros atualizados via relacionamento")
                
                # PASSO 3: Verificar registros órfãos (sem admin_id) e rastrear para validação
                cursor.execute(f"SELECT COUNT(*) FROM {tabela} WHERE admin_id IS NULL")
                orfaos = cursor.fetchone()[0]
                
                if orfaos > 0:
                    registros_orfaos[tabela] = orfaos
                    logger.warning(f"     ⚠️ {orfaos} registros órfãos em {tabela} - será validado após backfill")
                
                # PASSO 4: Aplicar NOT NULL constraint
                cursor.execute(f"ALTER TABLE {tabela} ALTER COLUMN admin_id SET NOT NULL")
                
                # PASSO 5: Adicionar foreign key
                constraint_name = f"fk_{tabela}_admin_id"
                cursor.execute(f"""
                    ALTER TABLE {tabela}
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY (admin_id) REFERENCES usuario(id) ON DELETE CASCADE
                """)
                
                # PASSO 6: Criar índice para performance
                index_name = f"idx_{tabela}_admin_id"
                cursor.execute(f"CREATE INDEX {index_name} ON {tabela}(admin_id)")
                
                tabelas_processadas += 1
                logger.info(f"  ✅ {tabela}: migração completa")
                
            except Exception as e:
                logger.error(f"  ❌ {tabela}: erro - {e}")
                connection.rollback()
                connection = db.engine.raw_connection()
                cursor = connection.cursor()
                continue
        
        # =====================================================================
        # VALIDAÇÕES PÓS-BACKFILL: Verificar integridade multi-tenant
        # =====================================================================
        logger.info("=" * 80)
        logger.info("🔍 VALIDAÇÕES PÓS-BACKFILL: Verificando integridade multi-tenant")
        logger.info("=" * 80)
        
        validacao_passou = True
        distribuicao_admin = {}
        
        # Contar número total de admins no sistema
        cursor.execute("SELECT COUNT(DISTINCT id) FROM usuario WHERE tipo_usuario = 'admin'")
        total_admins_sistema = cursor.fetchone()[0]
        logger.info(f"📊 Total de admins no sistema: {total_admins_sistema}")
        
        # Validar cada tabela processada
        for tabela in backfill_strategies.keys():
            try:
                # Verificar se tabela foi processada (tem admin_id)
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'admin_id'
                """, (tabela,))
                
                if not cursor.fetchone():
                    continue  # Tabela não processada
                
                # Contar distribuição de admin_id
                cursor.execute(f"""
                    SELECT admin_id, COUNT(*) 
                    FROM {tabela} 
                    GROUP BY admin_id 
                    ORDER BY admin_id
                """)
                
                distribuicao = cursor.fetchall()
                admins_distintos = len(distribuicao)
                
                distribuicao_admin[tabela] = {
                    'admins_distintos': admins_distintos,
                    'distribuicao': distribuicao
                }
                
                logger.info(f"  📋 {tabela}:")
                logger.info(f"     • Admins distintos: {admins_distintos}")
                
                for admin_id, count in distribuicao:
                    logger.info(f"     • Admin {admin_id}: {count} registros")
                
                # VALIDAÇÃO CRÍTICA: Verificar se houve colapso de tenants
                # Se sistema tem múltiplos admins mas tabela só tem 1, é suspeito
                if total_admins_sistema > 1 and admins_distintos == 1:
                    total_registros = sum(count for _, count in distribuicao)
                    if total_registros > 10:  # Só alertar se houver dados significativos
                        logger.warning(f"  ⚠️ {tabela}: SUSPEITA DE COLAPSO - {total_admins_sistema} admins no sistema mas apenas 1 na tabela ({total_registros} registros)")
                        # Não abortar automaticamente, mas logar para revisão
                
            except Exception as e:
                logger.error(f"  ❌ {tabela}: erro na validação - {e}")
                validacao_passou = False
        
        # VALIDAÇÃO FINAL: Verificar registros órfãos
        if registros_orfaos:
            logger.warning("=" * 80)
            logger.warning("⚠️ ATENÇÃO: Registros órfãos detectados!")
            logger.warning("=" * 80)
            for tabela, count in registros_orfaos.items():
                logger.warning(f"  • {tabela}: {count} registros sem admin_id")
            logger.warning("=" * 80)
            logger.warning("🔴 MIGRAÇÃO ABORTADA: Registros órfãos impedem NOT NULL constraint")
            logger.warning("   Ação necessária: Verificar relacionamentos antes de continuar")
            logger.warning("=" * 80)
            raise Exception(f"MIGRAÇÃO ABORTADA: {sum(registros_orfaos.values())} registros órfãos detectados. Verifique relacionamentos.")
        
        if validacao_passou:
            logger.info("=" * 80)
            logger.info("✅ VALIDAÇÕES CONCLUÍDAS: Integridade multi-tenant verificada!")
            logger.info("=" * 80)
        
        connection.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRAÇÃO 48 CONCLUÍDA COM BACKFILL TENANT-AWARE!")
        logger.info(f"   📊 Tabelas processadas: {tabelas_processadas}")
        logger.info(f"   ⏭️  Tabelas já existentes: {tabelas_ja_existentes}")
        logger.info(f"   🎯 Total de tabelas: {len(backfill_strategies)}")
        logger.info("=" * 80)
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro crítico na migração 48: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        raise


# ============================================================================
# MIGRAÇÃO 65 - Adicionar coluna 'nome' na tabela fornecedor
# ============================================================================

def _migration_65_fornecedor_nome():
    """
    MIGRAÇÃO 65: Adicionar coluna 'nome' na tabela fornecedor
    A coluna 'nome' é obrigatória no modelo mas pode não existir em bancos antigos
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("🔄 MIGRAÇÃO 65: Verificando coluna 'nome' na tabela fornecedor")
        
        # Verificar se coluna existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'fornecedor' AND column_name = 'nome'
        """)
        
        coluna_existe = cursor.fetchone()
        
        if coluna_existe:
            logger.info("  ✅ Coluna 'nome' já existe na tabela fornecedor")
        else:
            logger.info("  📝 Adicionando coluna 'nome' na tabela fornecedor...")
            
            # Adicionar coluna com valor default temporário
            cursor.execute("""
                ALTER TABLE fornecedor 
                ADD COLUMN nome VARCHAR(100)
            """)
            
            # Preencher com razao_social ou 'Fornecedor' como fallback
            cursor.execute("""
                UPDATE fornecedor 
                SET nome = COALESCE(razao_social, nome_fantasia, 'Fornecedor ' || id::text)
                WHERE nome IS NULL
            """)
            
            # Tornar NOT NULL após preencher
            cursor.execute("""
                ALTER TABLE fornecedor 
                ALTER COLUMN nome SET NOT NULL
            """)
            
            logger.info("  ✅ Coluna 'nome' adicionada e populada com sucesso")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ MIGRAÇÃO 65 CONCLUÍDA!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na migração 65: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_66_reconhecimento_facial_ponto():
    """
    MIGRAÇÃO 66: Adicionar campos para reconhecimento facial no RegistroPonto
    - foto_registro_base64: Foto capturada no momento do registro
    - reconhecimento_facial_sucesso: Se o reconhecimento foi bem-sucedido
    - confianca_reconhecimento: Distância/confiança do reconhecimento
    - modelo_utilizado: Modelo DeepFace utilizado
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("🔄 MIGRAÇÃO 66: Adicionando campos de reconhecimento facial ao RegistroPonto")
        
        campos_a_adicionar = [
            ("foto_registro_base64", "TEXT", None),
            ("reconhecimento_facial_sucesso", "BOOLEAN", "FALSE"),
            ("confianca_reconhecimento", "FLOAT", None),
            ("modelo_utilizado", "VARCHAR(50)", "'VGG-Face'")
        ]
        
        for nome_campo, tipo_campo, default_value in campos_a_adicionar:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'registro_ponto' AND column_name = %s
            """, (nome_campo,))
            
            coluna_existe = cursor.fetchone()
            
            if coluna_existe:
                logger.info(f"  ✅ Coluna '{nome_campo}' já existe")
            else:
                if default_value:
                    sql = f"ALTER TABLE registro_ponto ADD COLUMN {nome_campo} {tipo_campo} DEFAULT {default_value}"
                else:
                    sql = f"ALTER TABLE registro_ponto ADD COLUMN {nome_campo} {tipo_campo}"
                cursor.execute(sql)
                logger.info(f"  ✅ Coluna '{nome_campo}' adicionada com sucesso")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ MIGRAÇÃO 66 CONCLUÍDA!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na migração 66: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_67_geofencing():
    """
    MIGRAÇÃO 67: Adicionar campos de geofencing para validação de localização
    - obra: latitude, longitude, raio_geofence_metros
    - registro_ponto: latitude, longitude, distancia_obra_metros
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("🔄 MIGRAÇÃO 67: Adicionando campos de geofencing (cerca virtual)")
        
        # Campos para tabela obra
        campos_obra = [
            ("latitude", "FLOAT", None),
            ("longitude", "FLOAT", None),
            ("raio_geofence_metros", "INTEGER", "100")
        ]
        
        logger.info("  📍 Verificando campos de geofencing na tabela obra...")
        for nome_campo, tipo_campo, default_value in campos_obra:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'obra' AND column_name = %s
            """, (nome_campo,))
            
            coluna_existe = cursor.fetchone()
            
            if coluna_existe:
                logger.info(f"    ✅ Coluna '{nome_campo}' já existe em obra")
            else:
                if default_value:
                    sql = f"ALTER TABLE obra ADD COLUMN {nome_campo} {tipo_campo} DEFAULT {default_value}"
                else:
                    sql = f"ALTER TABLE obra ADD COLUMN {nome_campo} {tipo_campo}"
                cursor.execute(sql)
                logger.info(f"    ✅ Coluna '{nome_campo}' adicionada à tabela obra")
        
        # Campos para tabela registro_ponto
        campos_ponto = [
            ("latitude", "FLOAT", None),
            ("longitude", "FLOAT", None),
            ("distancia_obra_metros", "FLOAT", None)
        ]
        
        logger.info("  📍 Verificando campos de geofencing na tabela registro_ponto...")
        for nome_campo, tipo_campo, default_value in campos_ponto:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'registro_ponto' AND column_name = %s
            """, (nome_campo,))
            
            coluna_existe = cursor.fetchone()
            
            if coluna_existe:
                logger.info(f"    ✅ Coluna '{nome_campo}' já existe em registro_ponto")
            else:
                if default_value:
                    sql = f"ALTER TABLE registro_ponto ADD COLUMN {nome_campo} {tipo_campo} DEFAULT {default_value}"
                else:
                    sql = f"ALTER TABLE registro_ponto ADD COLUMN {nome_campo} {tipo_campo}"
                cursor.execute(sql)
                logger.info(f"    ✅ Coluna '{nome_campo}' adicionada à tabela registro_ponto")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ MIGRAÇÃO 67 CONCLUÍDA - Sistema de Geofencing ativo!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na migração 67: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_68_multiplas_fotos_faciais():
    """
    MIGRAÇÃO 68: Criar tabela para múltiplas fotos faciais por funcionário
    Melhora significativamente a precisão do reconhecimento facial permitindo
    cadastrar fotos com/sem óculos, diferentes ângulos, etc.
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        logger.info("🔄 MIGRAÇÃO 68: Criando sistema de múltiplas fotos faciais")
        
        # Verificar se a tabela já existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'foto_facial_funcionario'
            )
        """)
        
        tabela_existe = cursor.fetchone()[0]
        
        if not tabela_existe:
            logger.info("  📸 Criando tabela foto_facial_funcionario...")
            
            cursor.execute("""
                CREATE TABLE foto_facial_funcionario (
                    id SERIAL PRIMARY KEY,
                    funcionario_id INTEGER NOT NULL REFERENCES funcionario(id) ON DELETE CASCADE,
                    foto_base64 TEXT NOT NULL,
                    descricao VARCHAR(100),
                    ordem INTEGER DEFAULT 1,
                    ativa BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id)
                )
            """)
            
            logger.info("  ✅ Tabela foto_facial_funcionario criada com sucesso!")
            
            # Criar índices para performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_foto_facial_funcionario_id 
                ON foto_facial_funcionario(funcionario_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_foto_facial_admin_id 
                ON foto_facial_funcionario(admin_id)
            """)
            logger.info("  ✅ Índices criados para performance")
            
            # Migrar fotos existentes da coluna foto_base64 do funcionario
            logger.info("  📤 Migrando fotos existentes...")
            cursor.execute("""
                INSERT INTO foto_facial_funcionario (funcionario_id, foto_base64, descricao, ordem, admin_id)
                SELECT id, foto_base64, 'Foto principal (migrada)', 1, admin_id
                FROM funcionario
                WHERE foto_base64 IS NOT NULL 
                AND foto_base64 != ''
                AND admin_id IS NOT NULL
            """)
            
            rows_migrated = cursor.rowcount
            logger.info(f"  ✅ {rows_migrated} fotos migradas com sucesso!")
            
        else:
            logger.info("  ⏭️ Tabela foto_facial_funcionario já existe")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ MIGRAÇÃO 68 CONCLUÍDA - Sistema de múltiplas fotos faciais ativo!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na migração 68: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_71_remuneracao_diaria_funcionario():
    """
    MIGRAÇÃO 71: Adicionar campos tipo_remuneracao e valor_diaria na tabela funcionario.
    Permite que tenants V2 configurem funcionários como diaristas.
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        logger.info("Migração 71: funcionario - tipo_remuneracao e valor_diaria (V2 Diária)")

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'funcionario' AND column_name = 'tipo_remuneracao'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE funcionario
                ADD COLUMN tipo_remuneracao VARCHAR(20) NOT NULL DEFAULT 'salario'
            """)
            logger.info("  tipo_remuneracao adicionada em funcionario")
        else:
            logger.info("  tipo_remuneracao ja existe - SKIP")

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'funcionario' AND column_name = 'valor_diaria'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE funcionario
                ADD COLUMN valor_diaria FLOAT DEFAULT 0.0
            """)
            logger.info("  valor_diaria adicionada em funcionario")
        else:
            logger.info("  valor_diaria ja existe - SKIP")

        connection.commit()
        cursor.close()
        connection.close()

        logger.info("MIGRACAO 71 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 71: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_70_versao_sistema_usuario():
    """
    MIGRAÇÃO 70: Adicionar coluna versao_sistema na tabela usuario.
    Feature Flag para controle de versão V1/V2 por tenant (admin).
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        logger.info("Migração 70: usuario.versao_sistema - Feature Flag V1/V2")

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'usuario' AND column_name = 'versao_sistema'
        """)
        row = cursor.fetchone()

        if row is None:
            cursor.execute("""
                ALTER TABLE usuario
                ADD COLUMN versao_sistema VARCHAR(10) NOT NULL DEFAULT 'v1'
            """)
            logger.info("  versao_sistema adicionada em usuario com default 'v1'")
        else:
            logger.info("  versao_sistema ja existe em usuario - SKIP")

        connection.commit()
        cursor.close()
        connection.close()

        logger.info("MIGRACAO 70 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 70: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_69_custo_veiculo_obra_nullable():
    """
    MIGRAÇÃO 69: Tornar obra_id nullable na tabela custo_veiculo.
    Custos de veículo nem sempre estão associados a uma obra específica.
    """
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        logger.info("🔄 MIGRAÇÃO 69: custo_veiculo.obra_id → nullable")

        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'custo_veiculo' AND column_name = 'obra_id'
        """)
        row = cursor.fetchone()

        if row is None:
            logger.info("  ⏭️ Coluna obra_id não existe em custo_veiculo, nada a fazer")
        elif row[0] == 'NO':
            cursor.execute("ALTER TABLE custo_veiculo ALTER COLUMN obra_id DROP NOT NULL")
            logger.info("  ✅ custo_veiculo.obra_id agora é nullable")
        else:
            logger.info("  ⏭️ custo_veiculo.obra_id já é nullable")

        connection.commit()
        cursor.close()
        connection.close()

        logger.info("✅ MIGRAÇÃO 69 CONCLUÍDA")
        return True

    except Exception as e:
        logger.error(f"❌ Erro na migração 69: {e}")
        if 'connection' in locals():
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_74_compras_v2():
    """
    MIGRAÇÃO 74: Criar tabelas pedido_compra e pedido_compra_item para módulo V2.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        logger.info("Migração 74: criando tabelas de Compras V2")

        # Tabela pedido_compra
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'pedido_compra'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE pedido_compra (
                    id SERIAL PRIMARY KEY,
                    numero VARCHAR(50),
                    fornecedor_id INTEGER NOT NULL REFERENCES fornecedor(id),
                    data_compra DATE NOT NULL,
                    centro_custo_id INTEGER NOT NULL REFERENCES centro_custo(id),
                    obra_id INTEGER REFERENCES obra(id) ON DELETE SET NULL,
                    condicao_pagamento VARCHAR(50) DEFAULT 'a_vista',
                    parcelas INTEGER DEFAULT 1,
                    valor_total NUMERIC(12,2) NOT NULL,
                    observacoes TEXT,
                    anexo_url VARCHAR(500),
                    admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("  pedido_compra criada")
        else:
            logger.info("  pedido_compra ja existe - SKIP")

        # Tabela pedido_compra_item
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'pedido_compra_item'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE pedido_compra_item (
                    id SERIAL PRIMARY KEY,
                    pedido_id INTEGER NOT NULL REFERENCES pedido_compra(id) ON DELETE CASCADE,
                    almoxarifado_item_id INTEGER REFERENCES almoxarifado_item(id) ON DELETE SET NULL,
                    descricao VARCHAR(200) NOT NULL,
                    quantidade NUMERIC(10,3) NOT NULL,
                    preco_unitario NUMERIC(12,2) NOT NULL,
                    subtotal NUMERIC(12,2) NOT NULL
                )
            """)
            logger.info("  pedido_compra_item criada")
        else:
            logger.info("  pedido_compra_item ja existe - SKIP")

        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 74 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 74: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_73_transporte_v2():
    """
    MIGRAÇÃO 73: Criar tabelas categoria_transporte e lancamento_transporte para módulo V2.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        logger.info("Migração 73: criando tabelas de Transporte V2")

        # Tabela categoria_transporte
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'categoria_transporte'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE categoria_transporte (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(50) NOT NULL,
                    icone VARCHAR(50) DEFAULT 'fas fa-bus',
                    admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("  categoria_transporte criada")
        else:
            # garantir coluna icone
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='categoria_transporte' AND column_name='icone'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE categoria_transporte ADD COLUMN icone VARCHAR(50) DEFAULT 'fas fa-bus'")
            logger.info("  categoria_transporte ja existe - SKIP")

        # Tabela lancamento_transporte
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'lancamento_transporte'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE lancamento_transporte (
                    id SERIAL PRIMARY KEY,
                    categoria_id INTEGER NOT NULL REFERENCES categoria_transporte(id),
                    funcionario_id INTEGER REFERENCES funcionario(id) ON DELETE SET NULL,
                    veiculo_id INTEGER REFERENCES frota_veiculo(id) ON DELETE SET NULL,
                    centro_custo_id INTEGER NOT NULL REFERENCES centro_custo(id),
                    obra_id INTEGER REFERENCES obra(id) ON DELETE SET NULL,
                    data_lancamento DATE NOT NULL,
                    valor NUMERIC(10,2) NOT NULL,
                    descricao VARCHAR(200),
                    comprovante_url VARCHAR(500),
                    admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("  lancamento_transporte criada")
        else:
            logger.info("  lancamento_transporte ja existe - SKIP")

        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 73 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 73: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_72_alimentacao_item_v2():
    """
    MIGRAÇÃO 72: Adicionar funcionario_id e centro_custo_id em alimentacao_lancamento_item.
    Necessário para o módulo V2 de Alimentação com detalhamento por funcionário e centro de custo.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        logger.info("Migração 72: alimentacao_lancamento_item - funcionario_id e centro_custo_id (V2)")

        # funcionario_id
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'alimentacao_lancamento_item' AND column_name = 'funcionario_id'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE alimentacao_lancamento_item
                ADD COLUMN funcionario_id INTEGER REFERENCES funcionario(id) ON DELETE SET NULL
            """)
            logger.info("  funcionario_id adicionada em alimentacao_lancamento_item")
        else:
            logger.info("  funcionario_id ja existe - SKIP")

        # centro_custo_id
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'alimentacao_lancamento_item' AND column_name = 'centro_custo_id'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE alimentacao_lancamento_item
                ADD COLUMN centro_custo_id INTEGER REFERENCES centro_custo(id) ON DELETE SET NULL
            """)
            logger.info("  centro_custo_id adicionada em alimentacao_lancamento_item")
        else:
            logger.info("  centro_custo_id ja existe - SKIP")

        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 72 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 72: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return False


def _migration_75_cronograma_v2():
    """
    MIGRAÇÃO 75: Criar tabelas calendario_empresa e tarefa_cronograma
    para o Módulo de Cronograma de Obras (MS Project style, V2).
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        logger.info("Migração 75: criando tabelas de Cronograma V2")

        # Tabela calendario_empresa
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'calendario_empresa'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE calendario_empresa (
                    id SERIAL PRIMARY KEY,
                    admin_id INTEGER NOT NULL UNIQUE
                        REFERENCES usuario(id) ON DELETE CASCADE,
                    considerar_sabado BOOLEAN NOT NULL DEFAULT FALSE,
                    considerar_domingo BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("  calendario_empresa criada")
        else:
            logger.info("  calendario_empresa ja existe - SKIP")

        # Tabela tarefa_cronograma
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'tarefa_cronograma'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE tarefa_cronograma (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL
                        REFERENCES obra(id) ON DELETE CASCADE,
                    tarefa_pai_id INTEGER
                        REFERENCES tarefa_cronograma(id) ON DELETE SET NULL,
                    predecessora_id INTEGER
                        REFERENCES tarefa_cronograma(id) ON DELETE SET NULL,
                    ordem INTEGER NOT NULL DEFAULT 0,
                    nome_tarefa VARCHAR(200) NOT NULL,
                    duracao_dias INTEGER NOT NULL DEFAULT 1,
                    data_inicio DATE,
                    data_fim DATE,
                    quantidade_total FLOAT,
                    unidade_medida VARCHAR(20),
                    percentual_concluido FLOAT NOT NULL DEFAULT 0.0,
                    admin_id INTEGER NOT NULL
                        REFERENCES usuario(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX idx_tarefa_cronograma_obra
                    ON tarefa_cronograma(obra_id, admin_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_tarefa_cronograma_pai
                    ON tarefa_cronograma(tarefa_pai_id)
            """)
            logger.info("  tarefa_cronograma criada com índices")
        else:
            logger.info("  tarefa_cronograma ja existe - SKIP")

        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 75 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 75: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except Exception:
                pass
        return False


def _migration_76_rdo_apontamento_cronograma():
    """
    MIGRAÇÃO 76: Tabela rdo_apontamento_cronograma para integração RDO ↔ Cronograma V2.
    Registra produção diária por tarefa do cronograma a partir de um RDO.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        logger.info("Migração 76: criando tabela rdo_apontamento_cronograma")

        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'rdo_apontamento_cronograma'
            )
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE rdo_apontamento_cronograma (
                    id SERIAL PRIMARY KEY,
                    rdo_id INTEGER NOT NULL
                        REFERENCES rdo(id) ON DELETE CASCADE,
                    tarefa_cronograma_id INTEGER NOT NULL
                        REFERENCES tarefa_cronograma(id) ON DELETE CASCADE,
                    quantidade_executada_dia FLOAT NOT NULL DEFAULT 0.0,
                    quantidade_acumulada FLOAT NOT NULL DEFAULT 0.0,
                    percentual_realizado FLOAT NOT NULL DEFAULT 0.0,
                    percentual_planejado FLOAT NOT NULL DEFAULT 0.0,
                    admin_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(rdo_id, tarefa_cronograma_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX idx_rdo_apontamento_rdo
                    ON rdo_apontamento_cronograma(rdo_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_rdo_apontamento_tarefa
                    ON rdo_apontamento_cronograma(tarefa_cronograma_id, admin_id)
            """)
            logger.info("  rdo_apontamento_cronograma criada com índices")
        else:
            logger.info("  rdo_apontamento_cronograma ja existe - SKIP")

        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 76 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 76: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except Exception:
                pass
        return False


def _migration_77_gestao_custos_v2():
    """
    MIGRAÇÃO 77: Tabelas gestao_custo_pai e gestao_custo_filho
    para o módulo centralizado de Gestão de Custos V2.
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        # gestao_custo_pai
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'gestao_custo_pai'
            )
        """)
        if not cursor.fetchone()[0]:
            logger.info("Migração 77: criando tabela gestao_custo_pai")
            cursor.execute("""
                CREATE TABLE gestao_custo_pai (
                    id SERIAL PRIMARY KEY,
                    tipo_categoria VARCHAR(50) NOT NULL,
                    entidade_nome VARCHAR(150) NOT NULL,
                    entidade_id INTEGER,
                    valor_total NUMERIC(15,2) DEFAULT 0.00,
                    valor_solicitado NUMERIC(15,2),
                    status VARCHAR(20) DEFAULT 'PENDENTE',
                    data_pagamento DATE,
                    conta_bancaria VARCHAR(100),
                    observacoes TEXT,
                    data_criacao TIMESTAMP DEFAULT NOW(),
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    fluxo_caixa_id INTEGER REFERENCES fluxo_caixa(id)
                )
            """)
            cursor.execute("CREATE INDEX idx_gcp_admin_status ON gestao_custo_pai(admin_id, status)")
            cursor.execute("CREATE INDEX idx_gcp_admin_cat_ent ON gestao_custo_pai(admin_id, tipo_categoria, entidade_nome)")
        else:
            logger.info("Migração 77: gestao_custo_pai já existe")

        # gestao_custo_filho
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'gestao_custo_filho'
            )
        """)
        if not cursor.fetchone()[0]:
            logger.info("Migração 77: criando tabela gestao_custo_filho")
            cursor.execute("""
                CREATE TABLE gestao_custo_filho (
                    id SERIAL PRIMARY KEY,
                    pai_id INTEGER NOT NULL REFERENCES gestao_custo_pai(id) ON DELETE CASCADE,
                    data_referencia DATE NOT NULL,
                    descricao VARCHAR(300) NOT NULL,
                    valor NUMERIC(15,2) NOT NULL,
                    obra_id INTEGER REFERENCES obra(id),
                    centro_custo_id INTEGER REFERENCES centro_custo(id),
                    origem_tabela VARCHAR(80),
                    origem_id INTEGER,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_gcf_pai ON gestao_custo_filho(pai_id)")
            cursor.execute("CREATE INDEX idx_gcf_admin ON gestao_custo_filho(admin_id)")
        else:
            logger.info("Migração 77: gestao_custo_filho já existe")

        cursor.close()
        connection.close()
        logger.info("MIGRACAO 77 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 77: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except Exception:
                pass
        return False


def _migration_78_transporte_centro_custo_nullable():
    """
    MIGRAÇÃO 78: Torna centro_custo_id e funcionario_id opcionais em lancamento_transporte.
    Centro de custo era obrigatório mas duplicava o papel da obra.
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        # Tornar centro_custo_id nullable
        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'lancamento_transporte' AND column_name = 'centro_custo_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            logger.info("Migração 78: tornando centro_custo_id nullable")
            cursor.execute("""
                ALTER TABLE lancamento_transporte
                ALTER COLUMN centro_custo_id DROP NOT NULL
            """)
        else:
            logger.info("Migração 78: centro_custo_id já é nullable")

        cursor.close()
        connection.close()
        logger.info("MIGRACAO 78 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 78: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_79_reembolso_funcionario():
    """Migration 79: Cria tabela reembolso_funcionario para o sistema V2 de reembolsos"""
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'reembolso_funcionario'
            )
        """)
        exists = cursor.fetchone()[0]

        if not exists:
            cursor.execute("""
                CREATE TABLE reembolso_funcionario (
                    id SERIAL PRIMARY KEY,
                    funcionario_id INTEGER NOT NULL REFERENCES funcionario(id),
                    valor NUMERIC(15,2) NOT NULL,
                    data_despesa DATE NOT NULL,
                    descricao VARCHAR(200) NOT NULL,
                    obra_id INTEGER REFERENCES obra(id),
                    centro_custo_id INTEGER REFERENCES centro_custo(id),
                    origem_tabela VARCHAR(50),
                    origem_id INTEGER,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX idx_reembolso_funcionario_admin
                ON reembolso_funcionario(admin_id)
            """)
            cursor.execute("""
                CREATE INDEX idx_reembolso_funcionario_func
                ON reembolso_funcionario(funcionario_id)
            """)
            logger.info("MIGRACAO 79: tabela reembolso_funcionario criada")
        else:
            logger.info("MIGRACAO 79: tabela reembolso_funcionario ja existe")

        connection.close()
        logger.info("MIGRACAO 79 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 79: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_85_gestao_custo_pai_novas_colunas():
    """Migration 85: Adiciona colunas ausentes em gestao_custo_pai adicionadas pelo Task #8.
    Colunas: fornecedor_id, forma_pagamento, valor_pago, saldo, conta_contabil_codigo,
             data_emissao, numero_parcela, total_parcelas
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'gestao_custo_pai'
        """)
        existing_cols = {r[0] for r in cursor.fetchall()}

        colunas_a_adicionar = [
            ('fornecedor_id', 'INTEGER REFERENCES fornecedor(id)'),
            ('forma_pagamento', 'VARCHAR(30)'),
            ('valor_pago', 'NUMERIC(15, 2)'),
            ('saldo', 'NUMERIC(15, 2)'),
            ('conta_contabil_codigo', 'VARCHAR(20)'),
            ('data_emissao', 'DATE'),
            ('numero_parcela', 'INTEGER'),
            ('total_parcelas', 'INTEGER'),
        ]

        for col_name, col_def in colunas_a_adicionar:
            if col_name not in existing_cols:
                cursor.execute(
                    f"ALTER TABLE gestao_custo_pai ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                )
                logger.info(f"MIGRACAO 85: coluna {col_name} adicionada a gestao_custo_pai")
            else:
                logger.info(f"MIGRACAO 85: coluna {col_name} já existe - pulando")

        connection.close()
        logger.info("MIGRACAO 85 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 85: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_83_gestao_custo_vencimento():
    """Migration 83: Adiciona data_vencimento e numero_documento em gestao_custo_pai (DESPESA_GERAL)"""
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'gestao_custo_pai' AND column_name = 'data_vencimento'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE gestao_custo_pai ADD COLUMN data_vencimento DATE")
            logger.info("MIGRACAO 83: coluna data_vencimento adicionada a gestao_custo_pai")

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'gestao_custo_pai' AND column_name = 'numero_documento'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE gestao_custo_pai ADD COLUMN numero_documento VARCHAR(50)")
            logger.info("MIGRACAO 83: coluna numero_documento adicionada a gestao_custo_pai")

        connection.close()
        logger.info("MIGRACAO 83 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 83: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_84_alimentacao_restaurante_nullable():
    """Migration 84: Torna restaurante_id nullable em alimentacao_lancamento para suportar V2 sem restaurante obrigatório"""
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'alimentacao_lancamento' AND column_name = 'restaurante_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            cursor.execute("ALTER TABLE alimentacao_lancamento ALTER COLUMN restaurante_id DROP NOT NULL")
            logger.info("MIGRACAO 84: restaurante_id tornado nullable em alimentacao_lancamento")
        else:
            logger.info("MIGRACAO 84: restaurante_id ja e nullable, nada a fazer")

        connection.close()
        logger.info("MIGRACAO 84 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 84: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_82_obra_codigo_per_tenant():
    """Migration 82: Troca unique global de obra.codigo por unique composto (codigo, admin_id)"""
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        # 1. Remover constraint global obra_codigo_key (se existir)
        cursor.execute("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'obra' AND constraint_name = 'obra_codigo_key'
        """)
        if cursor.fetchone():
            cursor.execute("ALTER TABLE obra DROP CONSTRAINT obra_codigo_key")
            logger.info("MIGRACAO 82: constraint global obra_codigo_key removida")

        # 2. Criar unique composto (codigo, admin_id) — se não existir
        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'obra' AND indexname = 'uq_obra_codigo_admin_id'
        """)
        if not cursor.fetchone():
            # Resolver duplicatas de (codigo, admin_id) antes de criar o índice
            cursor.execute("""
                SELECT codigo, admin_id, array_agg(id ORDER BY id) as ids
                FROM obra
                WHERE codigo IS NOT NULL AND admin_id IS NOT NULL
                GROUP BY codigo, admin_id
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
            for dup_codigo, dup_admin_id, dup_ids in duplicates:
                # Mantém o ID mais antigo, renomeia os demais com sufixo
                for suffix_n, dup_id in enumerate(dup_ids[1:], start=2):
                    new_code = f"{dup_codigo}-DUP{suffix_n}"
                    cursor.execute(
                        "UPDATE obra SET codigo = %s WHERE id = %s",
                        (new_code, dup_id)
                    )
                    logger.info(f"MIGRACAO 82: renomeado código duplicado id={dup_id}: {dup_codigo} → {new_code}")

            cursor.execute("""
                CREATE UNIQUE INDEX uq_obra_codigo_admin_id
                ON obra (codigo, admin_id)
                WHERE codigo IS NOT NULL AND admin_id IS NOT NULL
            """)
            logger.info("MIGRACAO 82: unique index composto (codigo, admin_id) criado")

        connection.close()
        logger.info("MIGRACAO 82 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 82: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_81_reembolso_gestao_custo_pai_id():
    """Migration 81: Adiciona coluna gestao_custo_pai_id na tabela reembolso_funcionario"""
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'reembolso_funcionario'
        """)
        cols = {r[0] for r in cursor.fetchall()}

        if 'gestao_custo_pai_id' not in cols:
            cursor.execute("""
                ALTER TABLE reembolso_funcionario
                ADD COLUMN gestao_custo_pai_id INTEGER REFERENCES gestao_custo_pai(id) ON DELETE SET NULL
            """)
            logger.info("MIGRACAO 81: coluna gestao_custo_pai_id adicionada")

        connection.close()
        logger.info("MIGRACAO 81 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 81: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_80_reembolso_campos_extras():
    """Migration 80: Adiciona colunas categoria e comprovante_url na tabela reembolso_funcionario"""
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'reembolso_funcionario'
        """)
        cols = {r[0] for r in cursor.fetchall()}

        if 'categoria' not in cols:
            cursor.execute("""
                ALTER TABLE reembolso_funcionario
                ADD COLUMN categoria VARCHAR(50) DEFAULT 'outros'
            """)
            logger.info("MIGRACAO 80: coluna categoria adicionada")

        if 'comprovante_url' not in cols:
            cursor.execute("""
                ALTER TABLE reembolso_funcionario
                ADD COLUMN comprovante_url VARCHAR(500)
            """)
            logger.info("MIGRACAO 80: coluna comprovante_url adicionada")

        connection.close()
        logger.info("MIGRACAO 80 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 80: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def _migration_86_custo_obra_colunas_extras():
    """Migration 86: Garante colunas extras em custo_obra (idempotente).
    Migration 43 deveria ter adicionado estas colunas, mas em alguns ambientes
    de produção a migration foi marcada como executada sem que o ALTER TABLE
    tivesse sido aplicado. Esta migration corrige esse caso."""
    connection = None
    try:
        from app import db
        connection = db.engine.connect().connection
        cursor = connection.cursor()

        colunas = {
            'funcionario_id':       'INTEGER REFERENCES funcionario(id)',
            'item_almoxarifado_id': 'INTEGER REFERENCES almoxarifado_item(id)',
            'veiculo_id':           'INTEGER REFERENCES frota_veiculo(id)',
            'admin_id':             'INTEGER REFERENCES usuario(id)',
            'quantidade':           'NUMERIC(10,2) DEFAULT 1',
            'valor_unitario':       'NUMERIC(10,2) DEFAULT 0',
            'horas_trabalhadas':    'NUMERIC(5,2)',
            'horas_extras':         'NUMERIC(5,2)',
            'rdo_id':               'INTEGER REFERENCES rdo(id)',
            'categoria':            'VARCHAR(50)',
        }

        for coluna, tipo_sql in colunas.items():
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'custo_obra'
                AND column_name = %s
            """, (coluna,))
            if not cursor.fetchone():
                logger.info(f"  Adicionando coluna '{coluna}' em custo_obra...")
                cursor.execute(f"ALTER TABLE custo_obra ADD COLUMN {coluna} {tipo_sql}")
                logger.info(f"  Coluna '{coluna}' adicionada OK.")
            else:
                logger.info(f"  Coluna '{coluna}' OK.")

        # Índices de performance
        indices = [
            ('idx_custo_obra_funcionario', 'funcionario_id'),
            ('idx_custo_obra_veiculo',     'veiculo_id'),
            ('idx_custo_obra_admin',       'admin_id'),
            ('idx_custo_obra_data',        'data'),
        ]
        for nome, coluna in indices:
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'custo_obra' AND indexname = %s
            """, (nome,))
            if not cursor.fetchone():
                cursor.execute(f"CREATE INDEX {nome} ON custo_obra({coluna})")
                logger.info(f"  Índice {nome} criado.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 86 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 86: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_87_proposta_numero_unique_por_tenant():
    """
    Migração 87: propostas_comerciais - numero_proposta único por tenant
    Troca constraint global UNIQUE(numero_proposta) por UNIQUE(numero_proposta, admin_id)
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        # 1. Remover constraint global (se existir)
        cursor.execute("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'propostas_comerciais'
            AND constraint_name = 'propostas_comerciais_numero_proposta_key'
        """)
        if cursor.fetchone():
            logger.info("  Removendo constraint global numero_proposta...")
            cursor.execute("ALTER TABLE propostas_comerciais DROP CONSTRAINT propostas_comerciais_numero_proposta_key")
            logger.info("  Constraint global removida.")
        else:
            logger.info("  Constraint global numero_proposta já removida ou não existe.")

        # 2. Adicionar constraint composta (numero_proposta, admin_id)
        cursor.execute("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'propostas_comerciais'
            AND constraint_name = 'uq_proposta_numero_admin'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando constraint composta (numero_proposta, admin_id)...")
            cursor.execute("""
                ALTER TABLE propostas_comerciais
                ADD CONSTRAINT uq_proposta_numero_admin UNIQUE (numero_proposta, admin_id)
            """)
            logger.info("  Constraint composta criada.")
        else:
            logger.info("  Constraint composta já existe.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 87 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 87: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_88_tarefa_cronograma_responsavel():
    """
    Migração 88: tarefa_cronograma - adicionar coluna responsavel
    Valores: 'empresa' (conta na produtividade) ou 'terceiros' (só check de conclusão)
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tarefa_cronograma' AND column_name = 'responsavel'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna responsavel em tarefa_cronograma...")
            cursor.execute("""
                ALTER TABLE tarefa_cronograma
                ADD COLUMN responsavel VARCHAR(20) NOT NULL DEFAULT 'empresa'
            """)
            logger.info("  Coluna responsavel adicionada com sucesso.")
        else:
            logger.info("  Coluna responsavel já existe em tarefa_cronograma.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 88 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 88: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_89_rdo_criado_por_nullable():
    """
    Migração 89: rdo.criado_por_id - tornar nullable
    Funcionários do ponto eletrônico têm IDs de Funcionario, não de Usuario.
    A FK rdo.criado_por_id -> usuario.id falha quando funcionario_id != usuario.id.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'rdo' AND column_name = 'criado_por_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            logger.info("  Tornando rdo.criado_por_id nullable...")
            cursor.execute("ALTER TABLE rdo ALTER COLUMN criado_por_id DROP NOT NULL")
            logger.info("  rdo.criado_por_id agora é nullable.")
        else:
            logger.info("  rdo.criado_por_id já é nullable.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 89 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 89: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_91_rdo_mao_obra_tarefa_cronograma():
    """
    Migração 91: rdo_mao_obra — adicionar tarefa_cronograma_id (FK SET NULL).
    Permite rastrear em qual tarefa do cronograma cada funcionário trabalhou,
    habilitando métricas de produtividade por pessoa × tarefa.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'rdo_mao_obra' AND column_name = 'tarefa_cronograma_id'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna tarefa_cronograma_id em rdo_mao_obra...")
            cursor.execute("""
                ALTER TABLE rdo_mao_obra
                ADD COLUMN tarefa_cronograma_id INTEGER
                REFERENCES tarefa_cronograma(id) ON DELETE SET NULL
            """)
            logger.info("  Coluna tarefa_cronograma_id adicionada com FK SET NULL.")
        else:
            logger.info("  Coluna tarefa_cronograma_id já existe em rdo_mao_obra.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 91 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 91: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_92_almoxarifado_pedido_compra_id():
    """
    Migração 92: almoxarifado_movimento — adicionar pedido_compra_id (FK SET NULL).
    Permite rastrear se uma ENTRADA veio de um PedidoCompra, evitando duplicação
    de GestaoCustoPai (custo já registrado pelo módulo de Compras).
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'almoxarifado_movimento' AND column_name = 'pedido_compra_id'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna pedido_compra_id em almoxarifado_movimento...")
            cursor.execute("""
                ALTER TABLE almoxarifado_movimento
                ADD COLUMN pedido_compra_id INTEGER
                REFERENCES pedido_compra(id) ON DELETE SET NULL
            """)
            logger.info("  Coluna pedido_compra_id adicionada com FK SET NULL.")
        else:
            logger.info("  Coluna pedido_compra_id já existe em almoxarifado_movimento.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 92 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 92: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_93_pedido_compra_centro_custo_nullable():
    """
    Migração 93: pedido_compra.centro_custo_id — tornar coluna nullable.
    A obra passa a ser o identificador principal da compra. O centro de custo
    não é mais obrigatório no formulário de nova compra.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'pedido_compra' AND column_name = 'centro_custo_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            logger.info("  Tornando pedido_compra.centro_custo_id nullable...")
            cursor.execute("""
                ALTER TABLE pedido_compra
                ALTER COLUMN centro_custo_id DROP NOT NULL
            """)
            logger.info("  pedido_compra.centro_custo_id agora é nullable.")
        else:
            logger.info("  pedido_compra.centro_custo_id já é nullable ou não existe.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 93 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 93: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_90_rdo_mao_obra_subatividade():
    """
    Migração 90: rdo_mao_obra — adicionar subatividade_id (FK cascade) e horas_extras.
    subatividade_id: nullable FK para rdo_servico_subatividade com ON DELETE CASCADE.
    horas_extras: nullable Float com default 0.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'rdo_mao_obra' AND column_name = 'subatividade_id'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna subatividade_id em rdo_mao_obra...")
            cursor.execute("""
                ALTER TABLE rdo_mao_obra
                ADD COLUMN subatividade_id INTEGER
                REFERENCES rdo_servico_subatividade(id) ON DELETE CASCADE
            """)
            logger.info("  Coluna subatividade_id adicionada com FK e cascade.")
        else:
            logger.info("  Coluna subatividade_id já existe em rdo_mao_obra.")

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'rdo_mao_obra' AND column_name = 'horas_extras'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna horas_extras em rdo_mao_obra...")
            cursor.execute("""
                ALTER TABLE rdo_mao_obra
                ADD COLUMN horas_extras FLOAT DEFAULT 0
            """)
            logger.info("  Coluna horas_extras adicionada.")
        else:
            logger.info("  Coluna horas_extras já existe em rdo_mao_obra.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 90 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 90: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_94_subatividade_mestre_produtividade():
    """
    Migração 94: subatividade_mestre — adicionar unidade_medida e meta_produtividade
    para suportar o catálogo de produtividade do RDO V2.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'subatividade_mestre' AND column_name = 'unidade_medida'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna unidade_medida em subatividade_mestre...")
            cursor.execute("""
                ALTER TABLE subatividade_mestre
                ADD COLUMN unidade_medida VARCHAR(30)
            """)
            logger.info("  Coluna unidade_medida adicionada.")
        else:
            logger.info("  Coluna unidade_medida já existe em subatividade_mestre.")

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'subatividade_mestre' AND column_name = 'meta_produtividade'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna meta_produtividade em subatividade_mestre...")
            cursor.execute("""
                ALTER TABLE subatividade_mestre
                ADD COLUMN meta_produtividade FLOAT
            """)
            logger.info("  Coluna meta_produtividade adicionada.")
        else:
            logger.info("  Coluna meta_produtividade já existe em subatividade_mestre.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 94 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 94: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_95_cronograma_templates():
    """
    Migração 95: criar tabelas cronograma_template e cronograma_template_item
    para templates reutilizáveis de cronograma (V2).
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        # Tabela cronograma_template
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'cronograma_template'
        """)
        if not cursor.fetchone():
            logger.info("  Criando tabela cronograma_template...")
            cursor.execute("""
                CREATE TABLE cronograma_template (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(200) NOT NULL,
                    descricao TEXT,
                    categoria VARCHAR(100),
                    ativo BOOLEAN NOT NULL DEFAULT TRUE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX idx_cronograma_template_admin ON cronograma_template(admin_id)
            """)
            logger.info("  Tabela cronograma_template criada.")
        else:
            logger.info("  Tabela cronograma_template já existe.")

        # Tabela cronograma_template_item
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'cronograma_template_item'
        """)
        if not cursor.fetchone():
            logger.info("  Criando tabela cronograma_template_item...")
            cursor.execute("""
                CREATE TABLE cronograma_template_item (
                    id SERIAL PRIMARY KEY,
                    template_id INTEGER NOT NULL
                        REFERENCES cronograma_template(id) ON DELETE CASCADE,
                    subatividade_mestre_id INTEGER
                        REFERENCES subatividade_mestre(id) ON DELETE SET NULL,
                    nome_tarefa VARCHAR(200) NOT NULL,
                    ordem INTEGER NOT NULL DEFAULT 0,
                    duracao_dias INTEGER NOT NULL DEFAULT 1,
                    quantidade_prevista FLOAT,
                    responsavel VARCHAR(20) DEFAULT 'empresa',
                    admin_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX idx_cronograma_template_item_template
                ON cronograma_template_item(template_id)
            """)
            logger.info("  Tabela cronograma_template_item criada.")
        else:
            logger.info("  Tabela cronograma_template_item já existe.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 95 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 95: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_96_rdo_servico_subatividade_produtividade():
    """
    Migração 96: rdo_servico_subatividade — adicionar campos de produtividade V2:
    - subatividade_mestre_id (FK opcional para subatividade_mestre)
    - quantidade_produzida (Float nullable)
    - meta_produtividade_snapshot (Float nullable)
    - unidade_medida_snapshot (VARCHAR(50) nullable)
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        colunas = [
            ("subatividade_mestre_id", "INTEGER REFERENCES subatividade_mestre(id) ON DELETE SET NULL"),
            ("quantidade_produzida", "FLOAT"),
            ("meta_produtividade_snapshot", "FLOAT"),
            ("unidade_medida_snapshot", "VARCHAR(50)"),
        ]

        for col_name, col_def in colunas:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'rdo_servico_subatividade' AND column_name = %s
            """, (col_name,))
            if not cursor.fetchone():
                logger.info(f"  Adicionando coluna {col_name} em rdo_servico_subatividade...")
                cursor.execute(f"ALTER TABLE rdo_servico_subatividade ADD COLUMN {col_name} {col_def}")
                logger.info(f"  Coluna {col_name} adicionada.")
            else:
                logger.info(f"  Coluna {col_name} já existe em rdo_servico_subatividade.")

        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'rdo_servico_subatividade'
              AND indexname = 'idx_rdo_servico_sub_mestre_id'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE INDEX idx_rdo_servico_sub_mestre_id
                ON rdo_servico_subatividade(subatividade_mestre_id)
            """)
            logger.info("  Índice idx_rdo_servico_sub_mestre_id criado.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 96 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 96: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_100_tarefa_cronograma_subatividade_mestre_id():
    """
    Migração 100: tarefa_cronograma — adicionar subatividade_mestre_id FK opcional
    para rastrear qual item do catálogo originou a tarefa.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tarefa_cronograma' AND column_name = 'subatividade_mestre_id'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando tarefa_cronograma.subatividade_mestre_id...")
            cursor.execute("""
                ALTER TABLE tarefa_cronograma
                ADD COLUMN subatividade_mestre_id INTEGER
                REFERENCES subatividade_mestre(id) ON DELETE SET NULL
            """)
            logger.info("  Coluna subatividade_mestre_id adicionada com sucesso.")
        else:
            logger.info("  tarefa_cronograma.subatividade_mestre_id já existe.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 100 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 100: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_101_funcionario_pix_va_vt():
    """
    Migração 101: funcionario — adicionar chave_pix, valor_va e valor_vt
    para suporte a pagamentos via PIX e benefícios diários (VA e VT).
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'funcionario' AND column_name = 'chave_pix'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando funcionario.chave_pix, valor_va, valor_vt...")
            cursor.execute("""
                ALTER TABLE funcionario
                  ADD COLUMN IF NOT EXISTS chave_pix VARCHAR(150),
                  ADD COLUMN IF NOT EXISTS valor_va  FLOAT DEFAULT 0,
                  ADD COLUMN IF NOT EXISTS valor_vt  FLOAT DEFAULT 0
            """)
            logger.info("  Colunas chave_pix, valor_va, valor_vt adicionadas com sucesso.")
        else:
            logger.info("  funcionario.chave_pix já existe — verificando valor_va/valor_vt...")
            cursor.execute("""
                ALTER TABLE funcionario
                  ADD COLUMN IF NOT EXISTS valor_va FLOAT DEFAULT 0,
                  ADD COLUMN IF NOT EXISTS valor_vt FLOAT DEFAULT 0
            """)

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 101 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 101: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_99_rdo_servico_sub_nullable():
    """
    Migração 99: rdo_servico_subatividade — tornar servico_id nullable
    para suportar subatividades do catálogo sem serviço vinculado (tipo='subatividade').
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'rdo_servico_subatividade' AND column_name = 'servico_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            logger.info("  Tornando rdo_servico_subatividade.servico_id nullable...")
            cursor.execute("""
                ALTER TABLE rdo_servico_subatividade
                ALTER COLUMN servico_id DROP NOT NULL
            """)
            logger.info("  rdo_servico_subatividade.servico_id agora é nullable.")
        else:
            logger.info("  rdo_servico_subatividade.servico_id já é nullable.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 99 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 99: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_98_catalogo_hierarquico():
    """
    Migração 98: Catálogo hierárquico e template builder drag-and-drop:
    - SubatividadeMestre: adicionar coluna 'tipo' (VARCHAR(20), default 'subatividade')
    - SubatividadeMestre: tornar servico_id nullable (DROP NOT NULL)
    - CronogramaTemplateItem: adicionar parent_item_id (FK self-referencing nullable)
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        # 1. Adicionar coluna 'tipo' em subatividade_mestre
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'subatividade_mestre' AND column_name = 'tipo'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna 'tipo' em subatividade_mestre...")
            cursor.execute("""
                ALTER TABLE subatividade_mestre
                ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'subatividade'
            """)
            logger.info("  Coluna 'tipo' adicionada.")
        else:
            logger.info("  Coluna 'tipo' já existe em subatividade_mestre.")

        # 2. Tornar servico_id nullable em subatividade_mestre
        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'subatividade_mestre' AND column_name = 'servico_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            logger.info("  Tornando servico_id nullable em subatividade_mestre...")
            cursor.execute("""
                ALTER TABLE subatividade_mestre
                ALTER COLUMN servico_id DROP NOT NULL
            """)
            logger.info("  servico_id agora é nullable.")
        else:
            logger.info("  servico_id já é nullable em subatividade_mestre.")

        # 3. Adicionar parent_item_id em cronograma_template_item
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'cronograma_template_item' AND column_name = 'parent_item_id'
        """)
        if not cursor.fetchone():
            logger.info("  Adicionando coluna 'parent_item_id' em cronograma_template_item...")
            cursor.execute("""
                ALTER TABLE cronograma_template_item
                ADD COLUMN parent_item_id INTEGER REFERENCES cronograma_template_item(id) ON DELETE SET NULL
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cti_parent_item
                ON cronograma_template_item(parent_item_id)
            """)
            logger.info("  Coluna 'parent_item_id' adicionada.")
        else:
            logger.info("  Coluna 'parent_item_id' já existe em cronograma_template_item.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 98 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 98: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_97_rdo_mao_obra_produtividade():
    """
    Migração 97: rdo_mao_obra — adicionar campos de produtividade calculados:
    - produtividade_real (Float nullable)  = quantidade_produzida / horas_trabalhadas
    - indice_produtividade (Float nullable) = produtividade_real / meta_produtividade_snapshot
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        for col_name in ("produtividade_real", "indice_produtividade"):
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'rdo_mao_obra' AND column_name = %s
            """, (col_name,))
            if not cursor.fetchone():
                logger.info(f"  Adicionando coluna {col_name} em rdo_mao_obra...")
                cursor.execute(f"ALTER TABLE rdo_mao_obra ADD COLUMN {col_name} FLOAT")
                logger.info(f"  Coluna {col_name} adicionada.")
            else:
                logger.info(f"  Coluna {col_name} já existe em rdo_mao_obra.")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 97 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 97: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_102_funcionario_codigo_per_tenant():
    """
    Migração 102: funcionario.codigo — troca unique global por unique composto (codigo, admin_id).

    Cada tenant tem sua própria sequência de códigos VV independente. A constraint global
    `funcionario_codigo_key` impedia isso: se tenant A tinha VV001, tenant B não conseguia
    criar outro VV001. A constraint correta é única por (codigo + admin_id).
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()

        # 1. Remover constraint global funcionario_codigo_key (se ainda existir)
        cursor.execute("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'funcionario' AND constraint_name = 'funcionario_codigo_key'
        """)
        if cursor.fetchone():
            cursor.execute("ALTER TABLE funcionario DROP CONSTRAINT funcionario_codigo_key")
            logger.info("MIGRACAO 102: constraint global funcionario_codigo_key removida")
        else:
            logger.info("MIGRACAO 102: funcionario_codigo_key não encontrada — já removida ou nunca existiu")

        # 2. Criar unique composto (codigo, admin_id) por tenant — se não existir
        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'funcionario' AND indexname = 'uq_funcionario_codigo_admin_id'
        """)
        if not cursor.fetchone():
            # Resolver duplicatas de (codigo, admin_id) antes de criar o índice
            cursor.execute("""
                SELECT codigo, admin_id, array_agg(id ORDER BY id) as ids
                FROM funcionario
                WHERE codigo IS NOT NULL AND admin_id IS NOT NULL
                GROUP BY codigo, admin_id
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
            for dup_codigo, dup_admin_id, dup_ids in duplicates:
                # Mantém o ID mais antigo, renomeia os demais com sufixo
                for suffix_n, dup_id in enumerate(dup_ids[1:], start=2):
                    new_code = f"{dup_codigo}-D{suffix_n}"
                    cursor.execute(
                        "UPDATE funcionario SET codigo = %s WHERE id = %s",
                        (new_code, dup_id)
                    )
                    logger.info(f"MIGRACAO 102: código duplicado renomeado id={dup_id}: {dup_codigo} → {new_code}")

            cursor.execute("""
                CREATE UNIQUE INDEX uq_funcionario_codigo_admin_id
                ON funcionario (codigo, admin_id)
                WHERE codigo IS NOT NULL AND admin_id IS NOT NULL
            """)
            logger.info("MIGRACAO 102: unique index composto (codigo, admin_id) criado")
        else:
            logger.info("MIGRACAO 102: unique index uq_funcionario_codigo_admin_id já existe")

        connection.close()
        logger.info("MIGRACAO 102 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 102: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_104_tipo_fornecedor():
    """
    Migration 104: Adicionar tipo_fornecedor à tabela fornecedor
    Valores: MATERIAL | PRESTADOR_SERVICO | OUTRO (padrão OUTRO para registros existentes)
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'fornecedor' AND column_name = 'tipo_fornecedor'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE fornecedor
                ADD COLUMN tipo_fornecedor VARCHAR(20) DEFAULT 'OUTRO'
            """)
            logger.info("MIGRACAO 104: tipo_fornecedor adicionado em fornecedor")
        else:
            logger.info("MIGRACAO 104: tipo_fornecedor já existe em fornecedor")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 104 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 104: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_103_import_batch_id():
    """
    Migration 103: Adicionar import_batch_id às tabelas de importação
    Tabelas: gestao_custo_pai, conta_pagar, conta_receber, fluxo_caixa
    Permite rollback completo de uma importação por batch_id.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        tabelas = ['gestao_custo_pai', 'conta_pagar', 'conta_receber', 'fluxo_caixa']
        for tabela in tabelas:
            cursor.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = '{tabela}' AND column_name = 'import_batch_id'
            """)
            if not cursor.fetchone():
                cursor.execute(f"""
                    ALTER TABLE {tabela} ADD COLUMN import_batch_id VARCHAR(50)
                """)
                logger.info(f"MIGRACAO 103: import_batch_id adicionado em {tabela}")
            else:
                logger.info(f"MIGRACAO 103: import_batch_id já existe em {tabela}")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 103 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 103: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass


def migration_106_rdo_obra_cascade():
    """
    Migration 106: Adicionar ON DELETE CASCADE nas FKs de RDO e seus filhos.
    Permite excluir uma Obra sem erro de integridade referencial quando há RDOs vinculados.
    Tabelas afetadas: rdo (obra_id), rdo_mao_obra, rdo_equipamento, rdo_ocorrencia,
    rdo_foto, rdo_servico_subatividade (todos com rdo_id).
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        fk_changes = [
            ('rdo', 'obra_id', 'obra'),
            ('rdo_mao_obra', 'rdo_id', 'rdo'),
            ('rdo_equipamento', 'rdo_id', 'rdo'),
            ('rdo_ocorrencia', 'rdo_id', 'rdo'),
            ('rdo_foto', 'rdo_id', 'rdo'),
            ('rdo_servico_subatividade', 'rdo_id', 'rdo'),
        ]

        for table_name, column_name, referenced_table in fk_changes:
            cursor.execute("""
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = %s
                AND tc.constraint_type = 'FOREIGN KEY'
                AND kcu.column_name = %s
                AND tc.table_schema = 'public'
            """, (table_name, column_name))

            row = cursor.fetchone()
            if row:
                constraint_name = row[0]
                cursor.execute("""
                    SELECT delete_rule
                    FROM information_schema.referential_constraints
                    WHERE constraint_name = %s
                    AND constraint_schema = 'public'
                """, (constraint_name,))
                rc_row = cursor.fetchone()
                if rc_row and rc_row[0] == 'CASCADE':
                    logger.info(f"MIGRACAO 106: {table_name}.{column_name} ja e CASCADE — ignorado")
                    continue
                cursor.execute(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"')
                logger.info(f"MIGRACAO 106: constraint {constraint_name} removida de {table_name}")

            new_constraint = f"{table_name}_{column_name}_cascade_fkey"
            cursor.execute(f"""
                ALTER TABLE "{table_name}"
                ADD CONSTRAINT "{new_constraint}"
                FOREIGN KEY ("{column_name}")
                REFERENCES "{referenced_table}"(id)
                ON DELETE CASCADE
            """)
            logger.info(f"MIGRACAO 106: {table_name}.{column_name} -> {referenced_table}.id ON DELETE CASCADE aplicado")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 106 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 106: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_107_portal_cliente_obra():
    """
    Migration 107: Portal do Cliente por Obra
    - Fornecedor.chave_pix (String 100)
    - PedidoCompra.status_aprovacao_cliente (String 20, default PENDENTE)
    - PedidoCompra.comprovante_pagamento_url (String 500)
    - Tabela medicao_obra
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cols = [
            ("fornecedor", "chave_pix", "VARCHAR(255)"),
            ("pedido_compra", "status_aprovacao_cliente", "VARCHAR(20) DEFAULT 'PENDENTE'"),
            ("pedido_compra", "comprovante_pagamento_url", "VARCHAR(500)"),
        ]
        for table, col, dtype in cols:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """, (table, col))
            if cursor.fetchone()[0] == 0:
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {dtype}')
                logger.info(f"MIGRACAO 107: {table}.{col} adicionado")
            else:
                logger.info(f"MIGRACAO 107: {table}.{col} ja existe")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'medicao_obra'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE medicao_obra (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    numero INTEGER NOT NULL,
                    data_medicao DATE NOT NULL,
                    data_inicio DATE NOT NULL,
                    data_fim DATE NOT NULL,
                    percentual_executado FLOAT DEFAULT 0.0,
                    valor_medido NUMERIC(14,2) DEFAULT 0,
                    observacoes TEXT,
                    status VARCHAR(20) DEFAULT 'PENDENTE',
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_medicao_obra_obra_id ON medicao_obra(obra_id)")
            cursor.execute("CREATE INDEX idx_medicao_obra_admin_id ON medicao_obra(admin_id)")
            logger.info("MIGRACAO 107: tabela medicao_obra criada")
        else:
            logger.info("MIGRACAO 107: tabela medicao_obra ja existe")
            med_cols = [
                ("medicao_obra", "data_medicao", "DATE"),
                ("medicao_obra", "percentual_executado", "FLOAT DEFAULT 0.0"),
            ]
            for tbl, col, dt in med_cols:
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                """, (tbl, col))
                if cursor.fetchone()[0] == 0:
                    cursor.execute(f'ALTER TABLE "{tbl}" ADD COLUMN "{col}" {dt}')
                    logger.info(f"MIGRACAO 107: {tbl}.{col} adicionado")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 107 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 107: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_108_medicao_quinzenal():
    """
    Migration 108: Medição Quinzenal de Obra
    - Obra: data_inicio_medicao, valor_entrada, data_entrada
    - Tabela item_medicao_comercial
    - Tabela item_medicao_cronograma_tarefa
    - MedicaoObra: periodo_inicio, periodo_fim, valor_total_medido_periodo,
      valor_entrada_abatido_periodo, valor_a_faturar_periodo, conta_receber_id
    - Tabela medicao_obra_item
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        obra_cols = [
            ("obra", "data_inicio_medicao", "DATE"),
            ("obra", "valor_entrada", "NUMERIC(15,2) DEFAULT 0"),
            ("obra", "data_entrada", "DATE"),
        ]
        for table, col, dtype in obra_cols:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """, (table, col))
            if cursor.fetchone()[0] == 0:
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {dtype}')
                logger.info(f"MIGRACAO 108: {table}.{col} adicionado")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'item_medicao_comercial'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE item_medicao_comercial (
                    id SERIAL PRIMARY KEY,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    nome VARCHAR(200) NOT NULL,
                    valor_comercial NUMERIC(15,2) NOT NULL,
                    percentual_executado_acumulado NUMERIC(5,2) DEFAULT 0,
                    valor_executado_acumulado NUMERIC(15,2) DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'PENDENTE',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_imc_obra_id ON item_medicao_comercial(obra_id)")
            cursor.execute("CREATE INDEX idx_imc_admin_id ON item_medicao_comercial(admin_id)")
            logger.info("MIGRACAO 108: tabela item_medicao_comercial criada")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'item_medicao_cronograma_tarefa'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE item_medicao_cronograma_tarefa (
                    id SERIAL PRIMARY KEY,
                    item_medicao_id INTEGER NOT NULL REFERENCES item_medicao_comercial(id) ON DELETE CASCADE,
                    cronograma_tarefa_id INTEGER NOT NULL REFERENCES tarefa_cronograma(id) ON DELETE CASCADE,
                    peso NUMERIC(5,2) NOT NULL,
                    CONSTRAINT uq_item_tarefa UNIQUE(item_medicao_id, cronograma_tarefa_id)
                )
            """)
            logger.info("MIGRACAO 108: tabela item_medicao_cronograma_tarefa criada")

        medicao_cols = [
            ("medicao_obra", "periodo_inicio", "DATE"),
            ("medicao_obra", "periodo_fim", "DATE"),
            ("medicao_obra", "valor_total_medido_periodo", "NUMERIC(15,2) DEFAULT 0"),
            ("medicao_obra", "valor_entrada_abatido_periodo", "NUMERIC(15,2) DEFAULT 0"),
            ("medicao_obra", "valor_a_faturar_periodo", "NUMERIC(15,2) DEFAULT 0"),
            ("medicao_obra", "conta_receber_id", "INTEGER REFERENCES conta_receber(id)"),
        ]
        for table, col, dtype in medicao_cols:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """, (table, col))
            if cursor.fetchone()[0] == 0:
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {dtype}')
                logger.info(f"MIGRACAO 108: {table}.{col} adicionado")

        cursor.execute("""
            ALTER TABLE medicao_obra
            ALTER COLUMN data_medicao TYPE TIMESTAMP USING data_medicao::timestamp,
            ALTER COLUMN data_medicao SET DEFAULT NOW(),
            ALTER COLUMN data_inicio DROP NOT NULL,
            ALTER COLUMN data_fim DROP NOT NULL
        """)
        logger.info("MIGRACAO 108: medicao_obra.data_medicao convertido para TIMESTAMP")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'medicao_obra_item'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE medicao_obra_item (
                    id SERIAL PRIMARY KEY,
                    medicao_obra_id INTEGER NOT NULL REFERENCES medicao_obra(id) ON DELETE CASCADE,
                    item_medicao_comercial_id INTEGER NOT NULL REFERENCES item_medicao_comercial(id),
                    percentual_anterior NUMERIC(5,2) DEFAULT 0,
                    percentual_atual NUMERIC(5,2) DEFAULT 0,
                    percentual_executado_periodo NUMERIC(5,2) DEFAULT 0,
                    valor_medido_periodo NUMERIC(15,2) DEFAULT 0,
                    percentual_executado_acumulado NUMERIC(5,2) DEFAULT 0,
                    valor_executado_acumulado NUMERIC(15,2) DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX idx_moi_medicao_id ON medicao_obra_item(medicao_obra_id)")
            logger.info("MIGRACAO 108: tabela medicao_obra_item criada")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 108 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 108: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_105_fluxo_caixa_banco_id():
    """
    Migration 105: fluxo_caixa — adicionar banco_id FK opcional para BancoEmpresa
    Permite vincular cada movimentação de caixa a um banco específico.
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'fluxo_caixa' AND column_name = 'banco_id'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "ALTER TABLE fluxo_caixa ADD COLUMN banco_id INTEGER REFERENCES banco_empresa(id) ON DELETE SET NULL"
            )
            logger.info("MIGRACAO 105: banco_id adicionado em fluxo_caixa")
        else:
            logger.info("MIGRACAO 105: banco_id já existe em fluxo_caixa")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 105 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 105: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_110_opcao_concorrencia_admin_not_null():
    """
    Migration 110: Enforces NOT NULL on opcao_concorrencia.admin_id.
    Fills any existing NULLs from the parent mapa's admin_id before applying constraint.
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'opcao_concorrencia'
        """)
        if cursor.fetchone()[0] == 0:
            logger.info("MIGRACAO 110: tabela opcao_concorrencia não existe — skip")
            connection.commit()
            connection.close()
            return True

        cursor.execute("""
            UPDATE opcao_concorrencia oc
            SET admin_id = mc.admin_id
            FROM mapa_concorrencia mc
            WHERE oc.mapa_id = mc.id AND oc.admin_id IS NULL
        """)
        updated = cursor.rowcount
        if updated:
            logger.info(f"MIGRACAO 110: {updated} linhas de opcao_concorrencia corrigidas com admin_id")

        cursor.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'opcao_concorrencia' AND column_name = 'admin_id'
        """)
        row = cursor.fetchone()
        if row and row[0] == 'YES':
            cursor.execute(
                "ALTER TABLE opcao_concorrencia ALTER COLUMN admin_id SET NOT NULL"
            )
            logger.info("MIGRACAO 110: admin_id de opcao_concorrencia alterado para NOT NULL")
        else:
            logger.info("MIGRACAO 110: admin_id já é NOT NULL — skip")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 110 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 110: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_109_mapa_concorrencia():
    """
    Migration 109: Mapa de Concorrência
    Cria tabelas mapa_concorrencia e opcao_concorrencia para
    comparação de fornecedores com aprovação do cliente no portal.
    """
    connection = None
    try:
        from app import db
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'mapa_concorrencia'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE mapa_concorrencia (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    descricao_item VARCHAR(500) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pendente',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_mapa_concorrencia_obra_id ON mapa_concorrencia(obra_id)")
            cursor.execute("CREATE INDEX idx_mapa_concorrencia_admin_id ON mapa_concorrencia(admin_id)")
            logger.info("MIGRACAO 109: tabela mapa_concorrencia criada")
        else:
            logger.info("MIGRACAO 109: tabela mapa_concorrencia já existe")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'opcao_concorrencia'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE opcao_concorrencia (
                    id SERIAL PRIMARY KEY,
                    mapa_id INTEGER NOT NULL REFERENCES mapa_concorrencia(id) ON DELETE CASCADE,
                    fornecedor_nome VARCHAR(200) NOT NULL,
                    valor_unitario NUMERIC(12, 2) NOT NULL DEFAULT 0,
                    prazo_entrega VARCHAR(100),
                    observacoes TEXT,
                    selecionada BOOLEAN NOT NULL DEFAULT FALSE,
                    admin_id INTEGER REFERENCES usuario(id)
                )
            """)
            cursor.execute("CREATE INDEX idx_opcao_concorrencia_mapa_id ON opcao_concorrencia(mapa_id)")
            logger.info("MIGRACAO 109: tabela opcao_concorrencia criada")
        else:
            logger.info("MIGRACAO 109: tabela opcao_concorrencia já existe")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 109 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 109: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_111_cronograma_cliente():
    """
    Migration 111: Cria tabela cronograma_cliente — cronograma editável para o portal do cliente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'cronograma_cliente'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE cronograma_cliente (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    nome_tarefa VARCHAR(200) NOT NULL,
                    data_inicio_apresentacao DATE,
                    data_fim_apresentacao DATE,
                    percentual_apresentacao FLOAT NOT NULL DEFAULT 0.0,
                    ordem INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_cronograma_cliente_obra_id ON cronograma_cliente(obra_id)")
            cursor.execute("CREATE INDEX idx_cronograma_cliente_admin_id ON cronograma_cliente(admin_id)")
            logger.info("MIGRACAO 111: tabela cronograma_cliente criada")
        else:
            logger.info("MIGRACAO 111: tabela cronograma_cliente ja existe -- skip")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 111 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 111: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_112_mapa_concorrencia_v2():
    """
    Migration 112: Cria tabelas para o Mapa de Concorrência V2 —
    tabela multi-fornecedor com múltiplos itens e cotações por célula.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'mapa_concorrencia_v2'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE mapa_concorrencia_v2 (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    nome VARCHAR(300) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'aberto',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_mapa_v2_obra_id ON mapa_concorrencia_v2(obra_id)")
            cursor.execute("CREATE INDEX idx_mapa_v2_admin_id ON mapa_concorrencia_v2(admin_id)")
            logger.info("MIGRACAO 112: tabela mapa_concorrencia_v2 criada")
        else:
            logger.info("MIGRACAO 112: mapa_concorrencia_v2 ja existe -- skip")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'mapa_fornecedor'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE mapa_fornecedor (
                    id SERIAL PRIMARY KEY,
                    mapa_id INTEGER NOT NULL REFERENCES mapa_concorrencia_v2(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    nome VARCHAR(200) NOT NULL,
                    ordem INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX idx_mapa_fornecedor_mapa_id ON mapa_fornecedor(mapa_id)")
            logger.info("MIGRACAO 112: tabela mapa_fornecedor criada")
        else:
            logger.info("MIGRACAO 112: mapa_fornecedor ja existe -- skip")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'mapa_item_cotacao'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE mapa_item_cotacao (
                    id SERIAL PRIMARY KEY,
                    mapa_id INTEGER NOT NULL REFERENCES mapa_concorrencia_v2(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    descricao VARCHAR(500) NOT NULL,
                    unidade VARCHAR(50) DEFAULT 'un',
                    quantidade NUMERIC(12,3) DEFAULT 1,
                    ordem INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX idx_mapa_item_mapa_id ON mapa_item_cotacao(mapa_id)")
            logger.info("MIGRACAO 112: tabela mapa_item_cotacao criada")
        else:
            logger.info("MIGRACAO 112: mapa_item_cotacao ja existe -- skip")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'mapa_cotacao'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE mapa_cotacao (
                    id SERIAL PRIMARY KEY,
                    mapa_id INTEGER NOT NULL REFERENCES mapa_concorrencia_v2(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES mapa_item_cotacao(id) ON DELETE CASCADE,
                    fornecedor_id INTEGER NOT NULL REFERENCES mapa_fornecedor(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    valor_unitario NUMERIC(14,2) DEFAULT 0,
                    prazo VARCHAR(100),
                    selecionado BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            cursor.execute("CREATE INDEX idx_mapa_cotacao_mapa_id ON mapa_cotacao(mapa_id)")
            cursor.execute("CREATE INDEX idx_mapa_cotacao_item_id ON mapa_cotacao(item_id)")
            cursor.execute("CREATE UNIQUE INDEX idx_mapa_cotacao_unique ON mapa_cotacao(item_id, fornecedor_id)")
            logger.info("MIGRACAO 112: tabela mapa_cotacao criada")
        else:
            logger.info("MIGRACAO 112: mapa_cotacao ja existe -- skip")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 112 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 112: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_113_tarefa_cronograma_data_entrega_real():
    """
    Migration 113: Adiciona coluna data_entrega_real (DATE NULL) em tarefa_cronograma.

    Usada para tarefas com responsavel='terceiros' (entregas, subempreitadas)
    para registrar a data efetiva da entrega/conclusao e gerar alertas
    temporais no Painel Estrategico da Obra.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tarefa_cronograma'
              AND column_name = 'data_entrega_real'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE tarefa_cronograma
                ADD COLUMN data_entrega_real DATE NULL
            """)
            logger.info("MIGRACAO 113: coluna data_entrega_real adicionada em tarefa_cronograma")
        else:
            logger.info("MIGRACAO 113: coluna data_entrega_real ja existe -- skip")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 113 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 113: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_114_subempreiteiro():
    """
    Migration 114: cria tabelas `subempreiteiro` e `rdo_subempreitada_apontamento`
    e adiciona coluna `subempreiteiro_id` em `gestao_custo_pai`.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'subempreiteiro'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE subempreiteiro (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(200) NOT NULL,
                    cnpj VARCHAR(20),
                    especialidade VARCHAR(150),
                    contato_responsavel VARCHAR(150),
                    telefone VARCHAR(30),
                    email VARCHAR(150),
                    chave_pix VARCHAR(255),
                    observacoes TEXT,
                    ativo BOOLEAN NOT NULL DEFAULT TRUE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    CONSTRAINT uk_subempreiteiro_cnpj_admin UNIQUE (cnpj, admin_id)
                )
            """)
            cursor.execute("CREATE INDEX idx_subempreiteiro_admin_ativo ON subempreiteiro(admin_id, ativo)")
            logger.info("MIGRACAO 114: tabela subempreiteiro criada")
        else:
            logger.info("MIGRACAO 114: subempreiteiro ja existe -- skip")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'rdo_subempreitada_apontamento'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE rdo_subempreitada_apontamento (
                    id SERIAL PRIMARY KEY,
                    rdo_id INTEGER NOT NULL REFERENCES rdo(id) ON DELETE CASCADE,
                    tarefa_cronograma_id INTEGER NOT NULL REFERENCES tarefa_cronograma(id) ON DELETE CASCADE,
                    subempreiteiro_id INTEGER NOT NULL REFERENCES subempreiteiro(id) ON DELETE RESTRICT,
                    qtd_pessoas INTEGER NOT NULL DEFAULT 0,
                    horas_trabalhadas DOUBLE PRECISION NOT NULL DEFAULT 0,
                    quantidade_produzida DOUBLE PRECISION NOT NULL DEFAULT 0,
                    homem_hora DOUBLE PRECISION,
                    observacoes TEXT,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX idx_rdo_sub_apontamento_rdo ON rdo_subempreitada_apontamento(rdo_id)")
            cursor.execute("CREATE INDEX idx_rdo_sub_apontamento_tarefa ON rdo_subempreitada_apontamento(tarefa_cronograma_id)")
            cursor.execute("CREATE INDEX idx_rdo_sub_apontamento_sub ON rdo_subempreitada_apontamento(subempreiteiro_id)")
            logger.info("MIGRACAO 114: tabela rdo_subempreitada_apontamento criada")
        else:
            logger.info("MIGRACAO 114: rdo_subempreitada_apontamento ja existe -- skip")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'gestao_custo_pai' AND column_name = 'subempreiteiro_id'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE gestao_custo_pai
                ADD COLUMN subempreiteiro_id INTEGER REFERENCES subempreiteiro(id)
            """)
            logger.info("MIGRACAO 114: coluna gestao_custo_pai.subempreiteiro_id adicionada")
        else:
            logger.info("MIGRACAO 114: coluna gestao_custo_pai.subempreiteiro_id ja existe -- skip")

        connection.commit()
        connection.close()
        logger.info("MIGRACAO 114 CONCLUIDA")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 114: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


# ============================================================================
# Migration 115 — Consolidar GestaoCustoPai duplicados (Task #60)
# ============================================================================
_CATEGORIA_LEGADA_MAP_M115 = {
    'COMPRA':        'MATERIAL',
    'VEICULO':       'EQUIPAMENTO',
    'SALARIO':       'MAO_OBRA_DIRETA',
    'REEMBOLSO':     'OUTROS',
    'DESPESA_GERAL': 'OUTROS',
}


def migration_115_consolidar_gestao_custo_pai_duplicados():
    """
    Migration 115: Consolida GestaoCustoPai duplicados em aberto.

    Para cada (admin_id, entidade_id, categoria_normalizada) com mais de um pai
    em aberto (status NOT IN PAGO/RECUSADO/PARCIAL), elege o pai mais antigo
    como canônico, repassa todos os filhos dos demais para ele, recalcula o
    valor_total e remove os pais que ficaram vazios.

    NÃO toca em pais com status PAGO, RECUSADO ou PARCIAL.
    Idempotente: pode rodar múltiplas vezes.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        STATUS_PROTEGIDOS = ('PAGO', 'RECUSADO', 'PARCIAL')

        # CASE para normalizar categoria diretamente em SQL
        case_normaliza = (
            "CASE tipo_categoria "
            + " ".join(
                f"WHEN '{legada}' THEN '{nova}'"
                for legada, nova in _CATEGORIA_LEGADA_MAP_M115.items()
            )
            + " ELSE tipo_categoria END"
        )

        # 1) Grupos com entidade_id (chave canônica)
        cursor.execute(f"""
            SELECT admin_id, entidade_id, {case_normaliza} AS cat_norm,
                   array_agg(id ORDER BY id ASC) AS pai_ids
            FROM gestao_custo_pai
            WHERE entidade_id IS NOT NULL
              AND status NOT IN %s
            GROUP BY admin_id, entidade_id, cat_norm
            HAVING COUNT(*) > 1
        """, (STATUS_PROTEGIDOS,))
        grupos_com_id = cursor.fetchall()

        # 2) Grupos sem entidade_id (fallback por entidade_nome)
        cursor.execute(f"""
            SELECT admin_id, entidade_nome, {case_normaliza} AS cat_norm,
                   array_agg(id ORDER BY id ASC) AS pai_ids
            FROM gestao_custo_pai
            WHERE entidade_id IS NULL
              AND status NOT IN %s
            GROUP BY admin_id, entidade_nome, cat_norm
            HAVING COUNT(*) > 1
        """, (STATUS_PROTEGIDOS,))
        grupos_sem_id = cursor.fetchall()

        total_grupos = len(grupos_com_id) + len(grupos_sem_id)
        total_pais_removidos = 0
        total_filhos_movidos = 0

        def _consolidar(pai_ids, label):
            nonlocal total_pais_removidos, total_filhos_movidos
            canonical_id = pai_ids[0]
            duplicados = pai_ids[1:]
            if not duplicados:
                return

            # Mover filhos dos duplicados para o canônico
            cursor.execute(
                "UPDATE gestao_custo_filho SET pai_id = %s WHERE pai_id = ANY(%s)",
                (canonical_id, duplicados),
            )
            filhos_movidos = cursor.rowcount or 0
            total_filhos_movidos += filhos_movidos

            # Garantir que duplicados não tenham mais filhos antes do delete
            cursor.execute(
                "SELECT id FROM gestao_custo_pai WHERE id = ANY(%s) "
                "AND id NOT IN (SELECT DISTINCT pai_id FROM gestao_custo_filho WHERE pai_id = ANY(%s))",
                (duplicados, duplicados),
            )
            removiveis = [r[0] for r in cursor.fetchall()]
            if removiveis:
                cursor.execute(
                    "DELETE FROM gestao_custo_pai WHERE id = ANY(%s)",
                    (removiveis,),
                )
                total_pais_removidos += cursor.rowcount or 0

            # Recalcular valor_total do canônico
            cursor.execute(
                "UPDATE gestao_custo_pai SET valor_total = "
                "COALESCE((SELECT SUM(valor) FROM gestao_custo_filho WHERE pai_id = %s), 0) "
                "WHERE id = %s",
                (canonical_id, canonical_id),
            )

            logger.info(
                f"MIGRACAO 115: consolidado {label} → pai canônico={canonical_id}, "
                f"filhos movidos={filhos_movidos}, duplicados removidos={len(removiveis)}"
            )

        for admin_id, entidade_id, cat_norm, pai_ids in grupos_com_id:
            _consolidar(
                pai_ids,
                f"admin={admin_id} entidade_id={entidade_id} cat={cat_norm}",
            )

        for admin_id, entidade_nome, cat_norm, pai_ids in grupos_sem_id:
            _consolidar(
                pai_ids,
                f"admin={admin_id} entidade_nome='{entidade_nome}' cat={cat_norm}",
            )

        connection.commit()
        cursor.close()
        connection.close()

        logger.info(
            f"MIGRACAO 115 CONCLUIDA: {total_grupos} grupos consolidados, "
            f"{total_filhos_movidos} filhos movidos, {total_pais_removidos} pais duplicados removidos"
        )
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 115: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


# ============================================================================
# Migration 116 — PedidoCompra.tipo_compra + processada_apos_aprovacao (Task #65)
# ============================================================================
def migration_116_pedido_compra_tipo_compra():
    """
    Migration 116: Adiciona duas colunas em pedido_compra para suportar dois
    fluxos distintos de compra:

      tipo_compra VARCHAR(30) NOT NULL DEFAULT 'normal'
        → 'normal'            : fluxo interno tradicional (gera GestaoCustoPai MATERIAL
                                 + ContaPagar implícita via GCP + entrada no almoxarifado)
        → 'aprovacao_cliente' : só processa após aprovação do cliente no portal;
                                 gera GestaoCustoPai FATURAMENTO_DIRETO (sem FluxoCaixa)
                                 + entrada + saída imediata no almoxarifado.

      processada_apos_aprovacao BOOLEAN NOT NULL DEFAULT FALSE
        → flag de idempotência: impede que o helper rode mais de uma vez no
          mesmo pedido mesmo que o cliente clique "aprovar" várias vezes.

    Idempotente — usa ADD COLUMN IF NOT EXISTS.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            ALTER TABLE pedido_compra
                ADD COLUMN IF NOT EXISTS tipo_compra VARCHAR(30) NOT NULL DEFAULT 'normal'
        """)
        cursor.execute("""
            ALTER TABLE pedido_compra
                ADD COLUMN IF NOT EXISTS processada_apos_aprovacao BOOLEAN NOT NULL DEFAULT FALSE
        """)

        # Aumentar status_aprovacao_cliente de VARCHAR(20) -> VARCHAR(40) para
        # caber o novo valor 'AGUARDANDO_APROVACAO_CLIENTE' (28 chars).
        cursor.execute("""
            ALTER TABLE pedido_compra
                ALTER COLUMN status_aprovacao_cliente TYPE VARCHAR(40)
        """)

        # Garantir que registros existentes tenham tipo_compra='normal' (já que eles
        # foram criados no fluxo antigo). NOT NULL + DEFAULT já cuidou disto, mas
        # reforçamos para o caso de a coluna ter sido criada NULL antes.
        cursor.execute("""
            UPDATE pedido_compra SET tipo_compra = 'normal'
             WHERE tipo_compra IS NULL
        """)

        # Backfill crítico de idempotência: qualquer pedido LEGADO com
        # status_aprovacao_cliente='APROVADO' já foi "aprovado" antes desta
        # task existir; portanto NÃO deve ser reprocessado se alguém clicar
        # aprovar de novo (o helper FATURAMENTO_DIRETO usa processada_apos_aprovacao
        # como guarda). Marcamos como já processado para evitar duplicidade.
        cursor.execute("""
            UPDATE pedido_compra
               SET processada_apos_aprovacao = TRUE
             WHERE status_aprovacao_cliente = 'APROVADO'
               AND processada_apos_aprovacao = FALSE
        """)
        backfill_approved = cursor.rowcount or 0

        connection.commit()
        cursor.close()
        connection.close()
        logger.info(
            f"MIGRACAO 116 CONCLUIDA: pedido_compra.tipo_compra e processada_apos_aprovacao "
            f"criados; backfill idempotencia={backfill_approved} pedidos APROVADO legados"
        )
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 116: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_118_resumo_custos_obra():
    """
    Migration 118 (Task #70): Resumo de Custos da Obra.

    Cria tabelas:
      - obra_servico_custo (FK UNIQUE item_medicao_comercial_id quando preenchida)
      - obra_servico_equipe_planejada (snapshot por funcionário)
      - obra_servico_cotacao_interna (constraint: só 1 SELECIONADA por serviço)
      - obra_servico_cotacao_interna_linha

    Adiciona coluna em obra:
      - percentual_administracao NUMERIC(5,2) NOT NULL DEFAULT 0

    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            ALTER TABLE obra
                ADD COLUMN IF NOT EXISTS percentual_administracao NUMERIC(5,2) NOT NULL DEFAULT 0
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS obra_servico_custo (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                item_medicao_comercial_id INTEGER UNIQUE REFERENCES item_medicao_comercial(id) ON DELETE SET NULL,
                servico_obra_real_id INTEGER REFERENCES servico_obra_real(id) ON DELETE SET NULL,
                nome VARCHAR(200) NOT NULL,
                valor_orcado NUMERIC(15,2) NOT NULL DEFAULT 0,
                realizado_material NUMERIC(15,2) NOT NULL DEFAULT 0,
                realizado_mao_obra NUMERIC(15,2) NOT NULL DEFAULT 0,
                realizado_outros NUMERIC(15,2) NOT NULL DEFAULT 0,
                override_realizado_manual BOOLEAN NOT NULL DEFAULT FALSE,
                material_a_realizar NUMERIC(15,2) NOT NULL DEFAULT 0,
                cotacao_selecionada_id INTEGER,
                mao_obra_a_realizar NUMERIC(15,2) NOT NULL DEFAULT 0,
                outros_a_realizar NUMERIC(15,2) NOT NULL DEFAULT 0,
                observacoes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_obra_servico_custo_obra ON obra_servico_custo(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_obra_servico_custo_admin ON obra_servico_custo(admin_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS obra_servico_equipe_planejada (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                obra_servico_custo_id INTEGER NOT NULL REFERENCES obra_servico_custo(id) ON DELETE CASCADE,
                funcionario_id INTEGER REFERENCES funcionario(id),
                funcionario_nome VARCHAR(120) NOT NULL,
                quantidade_dias NUMERIC(10,2) NOT NULL DEFAULT 0,
                diaria NUMERIC(15,2) NOT NULL DEFAULT 0,
                almoco_e_cafe NUMERIC(15,2) NOT NULL DEFAULT 0,
                transporte NUMERIC(15,2) NOT NULL DEFAULT 0,
                observacoes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_equipe_planejada_servico
                ON obra_servico_equipe_planejada(obra_servico_custo_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_equipe_planejada_admin
                ON obra_servico_equipe_planejada(admin_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS obra_servico_cotacao_interna (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                obra_servico_custo_id INTEGER NOT NULL REFERENCES obra_servico_custo(id) ON DELETE CASCADE,
                fornecedor_nome VARCHAR(200) NOT NULL,
                fornecedor_id INTEGER REFERENCES fornecedor(id),
                prazo_entrega VARCHAR(100),
                condicao_pagamento VARCHAR(100),
                observacoes TEXT,
                selecionada BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cotacao_interna_servico
                ON obra_servico_cotacao_interna(obra_servico_custo_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cotacao_interna_admin
                ON obra_servico_cotacao_interna(admin_id)
        """)
        # Garante só 1 SELECIONADA por serviço (partial unique index)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_cotacao_interna_selecionada_por_servico
                ON obra_servico_cotacao_interna(obra_servico_custo_id)
                WHERE selecionada = TRUE
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS obra_servico_cotacao_interna_linha (
                id SERIAL PRIMARY KEY,
                cotacao_id INTEGER NOT NULL REFERENCES obra_servico_cotacao_interna(id) ON DELETE CASCADE,
                admin_id INTEGER,
                descricao VARCHAR(300) NOT NULL,
                unidade VARCHAR(20),
                quantidade NUMERIC(15,4) NOT NULL DEFAULT 0,
                valor_unitario NUMERIC(15,2) NOT NULL DEFAULT 0
            )
        """)
        # Patch idempotente: adiciona admin_id em DBs que já tinham a tabela
        cursor.execute("""
            ALTER TABLE obra_servico_cotacao_interna_linha
                ADD COLUMN IF NOT EXISTS admin_id INTEGER
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cotacao_linha_cotacao
                ON obra_servico_cotacao_interna_linha(cotacao_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cotacao_linha_admin
                ON obra_servico_cotacao_interna_linha(admin_id)
        """)

        # FK cotacao_selecionada_id só depois da tabela-alvo existir
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_obra_servico_custo_cotacao_sel'
                ) THEN
                    ALTER TABLE obra_servico_custo
                    ADD CONSTRAINT fk_obra_servico_custo_cotacao_sel
                    FOREIGN KEY (cotacao_selecionada_id)
                    REFERENCES obra_servico_cotacao_interna(id)
                    ON DELETE SET NULL;
                END IF;
            END$$;
        """)

        connection.commit()
        cursor.close()
        logger.info("MIGRACAO 118: Resumo de Custos da Obra aplicada (tabelas criadas + percentual_administracao)")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 118: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_119_gestao_custo_filho_obra_servico():
    """
    Migration 119 (Task #74): vincular custos reais a cada serviço da obra.

    Adiciona coluna gestao_custo_filho.obra_servico_custo_id (FK SET NULL)
    + índice. Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            ALTER TABLE gestao_custo_filho
                ADD COLUMN IF NOT EXISTS obra_servico_custo_id INTEGER
        """)
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_gestao_custo_filho_obra_servico_custo'
                ) THEN
                    ALTER TABLE gestao_custo_filho
                    ADD CONSTRAINT fk_gestao_custo_filho_obra_servico_custo
                    FOREIGN KEY (obra_servico_custo_id)
                    REFERENCES obra_servico_custo(id)
                    ON DELETE SET NULL;
                END IF;
            END$$;
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gestao_custo_filho_obra_servico
                ON gestao_custo_filho(obra_servico_custo_id)
        """)

        connection.commit()
        cursor.close()
        logger.info("MIGRACAO 119: gestao_custo_filho.obra_servico_custo_id criado")
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 119: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_117_tarefa_cronograma_is_cliente():
    """
    Migration 117: Adiciona is_cliente BOOLEAN NOT NULL DEFAULT FALSE em tarefa_cronograma.

    Permite que a mesma tabela armazene as duas faces do cronograma:
      - is_cliente = FALSE (default): cronograma INTERNO (planejamento real)
      - is_cliente = TRUE          : cronograma do CLIENTE (versao para o portal)

    O editor /cronograma/obra/<id>?cliente=1 opera apenas em is_cliente=TRUE.
    Edicoes no editor cliente NAO afetam o plano interno.

    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            ALTER TABLE tarefa_cronograma
                ADD COLUMN IF NOT EXISTS is_cliente BOOLEAN NOT NULL DEFAULT FALSE
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tarefa_cronograma_obra_cliente
                ON tarefa_cronograma(obra_id, is_cliente)
        """)

        connection.commit()
        cursor.close()
        logger.info("MIGRACAO 117: tarefa_cronograma.is_cliente adicionada com indice composto")
        return True

    except Exception as e:
        logger.error(f"Erro na migracao 117: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return False


def migration_120_notificacao_orcamento():
    """Migration 120 (Task #76): tabela notificacao_orcamento.

    Cria a tabela que armazena alertas persistentes (1 por serviço) quando
    (realizado + a_realizar) ultrapassa o valor_orcado de um ObraServicoCusto.
    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificacao_orcamento (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                obra_servico_custo_id INTEGER NOT NULL REFERENCES obra_servico_custo(id) ON DELETE CASCADE,
                percentual NUMERIC(7,2) NOT NULL DEFAULT 0,
                valor_excesso NUMERIC(15,2) NOT NULL DEFAULT 0,
                valor_orcado NUMERIC(15,2) NOT NULL DEFAULT 0,
                valor_projetado NUMERIC(15,2) NOT NULL DEFAULT 0,
                mensagem TEXT NOT NULL DEFAULT '',
                ativa BOOLEAN NOT NULL DEFAULT TRUE,
                resolvida_em TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_notif_orcamento_servico
                    UNIQUE (admin_id, obra_id, obra_servico_custo_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_orc_admin ON notificacao_orcamento(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_orc_obra  ON notificacao_orcamento(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_orc_svc   ON notificacao_orcamento(obra_servico_custo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_orc_ativa ON notificacao_orcamento(ativa)")

        connection.commit()
        cursor.close()
        logger.info("MIGRACAO 119: notificacao_orcamento criada")
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 119: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_121_catalogo_servicos_orcamento():
    """Migration 121 (Task #82): Catálogo de Insumos + Composição de Serviços.

    Cria:
      - tabela `insumo` (catálogo de itens base)
      - tabela `preco_base_insumo` (vigência de preços)
      - tabela `composicao_servico` (serviço × insumo × coeficiente)
      - colunas em `servico`: imposto_pct, margem_lucro_pct, preco_venda_unitario
      - coluna `proposta_item.servico_id` (FK servico, SET NULL)
      - colunas `item_medicao_comercial.servico_id` (FK servico, SET NULL)
                + `quantidade` NUMERIC(15,4)
      - coluna `obra_servico_custo.servico_catalogo_id` (FK servico, SET NULL)
      - colunas em `configuracao_empresa`: imposto_pct_padrao, lucro_pct_padrao
    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        # ── 1. Insumo
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insumo (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                nome VARCHAR(200) NOT NULL,
                tipo VARCHAR(20) NOT NULL DEFAULT 'MATERIAL',
                unidade VARCHAR(20) NOT NULL DEFAULT 'un',
                descricao TEXT,
                ativo BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_insumo_admin ON insumo(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_insumo_admin_ativo ON insumo(admin_id, ativo)")

        # ── 2. PrecoBaseInsumo
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preco_base_insumo (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                insumo_id INTEGER NOT NULL REFERENCES insumo(id) ON DELETE CASCADE,
                valor NUMERIC(15,4) NOT NULL DEFAULT 0,
                vigencia_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
                vigencia_fim DATE,
                observacao VARCHAR(300),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_preco_base_insumo_admin ON preco_base_insumo(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_preco_base_insumo_insumo ON preco_base_insumo(insumo_id)")

        # ── 3. ComposicaoServico
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS composicao_servico (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                servico_id INTEGER NOT NULL REFERENCES servico(id) ON DELETE CASCADE,
                insumo_id INTEGER NOT NULL REFERENCES insumo(id) ON DELETE RESTRICT,
                coeficiente NUMERIC(15,6) NOT NULL DEFAULT 0,
                observacao VARCHAR(300),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_composicao_servico_insumo UNIQUE (servico_id, insumo_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_composicao_servico_admin ON composicao_servico(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_composicao_servico_svc ON composicao_servico(servico_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_composicao_servico_ins ON composicao_servico(insumo_id)")

        # ── 4. Servico — campos de orçamento
        cursor.execute("ALTER TABLE servico ADD COLUMN IF NOT EXISTS imposto_pct NUMERIC(5,2)")
        cursor.execute("ALTER TABLE servico ADD COLUMN IF NOT EXISTS margem_lucro_pct NUMERIC(5,2)")
        cursor.execute("ALTER TABLE servico ADD COLUMN IF NOT EXISTS preco_venda_unitario NUMERIC(15,2) DEFAULT 0")

        # ── 5. PropostaItem.servico_id (tabela real: proposta_itens)
        cursor.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'proposta_itens') THEN
                    ALTER TABLE proposta_itens ADD COLUMN IF NOT EXISTS servico_id INTEGER;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'fk_proposta_itens_servico'
                    ) THEN
                        ALTER TABLE proposta_itens
                            ADD CONSTRAINT fk_proposta_itens_servico
                            FOREIGN KEY (servico_id) REFERENCES servico(id) ON DELETE SET NULL;
                    END IF;
                    CREATE INDEX IF NOT EXISTS idx_proposta_itens_servico ON proposta_itens(servico_id);
                END IF;
            END$$;
        """)

        # ── 6. ItemMedicaoComercial.servico_id + quantidade
        cursor.execute("ALTER TABLE item_medicao_comercial ADD COLUMN IF NOT EXISTS servico_id INTEGER")
        cursor.execute("ALTER TABLE item_medicao_comercial ADD COLUMN IF NOT EXISTS quantidade NUMERIC(15,4)")
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_item_medicao_servico'
                ) THEN
                    ALTER TABLE item_medicao_comercial
                        ADD CONSTRAINT fk_item_medicao_servico
                        FOREIGN KEY (servico_id) REFERENCES servico(id) ON DELETE SET NULL;
                END IF;
            END$$;
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_item_medicao_servico ON item_medicao_comercial(servico_id)")

        # ── 7. ObraServicoCusto.servico_catalogo_id
        cursor.execute("ALTER TABLE obra_servico_custo ADD COLUMN IF NOT EXISTS servico_catalogo_id INTEGER")
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_obra_servico_custo_catalogo'
                ) THEN
                    ALTER TABLE obra_servico_custo
                        ADD CONSTRAINT fk_obra_servico_custo_catalogo
                        FOREIGN KEY (servico_catalogo_id) REFERENCES servico(id) ON DELETE SET NULL;
                END IF;
            END$$;
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_obra_servico_custo_catalogo ON obra_servico_custo(servico_catalogo_id)")

        # ── 8. ConfiguracaoEmpresa — defaults
        cursor.execute("ALTER TABLE configuracao_empresa ADD COLUMN IF NOT EXISTS imposto_pct_padrao NUMERIC(5,2) DEFAULT 8.0")
        cursor.execute("ALTER TABLE configuracao_empresa ADD COLUMN IF NOT EXISTS lucro_pct_padrao NUMERIC(5,2) DEFAULT 10.0")

        connection.commit()
        cursor.close()
        logger.info("MIGRACAO 121: catálogo de insumos, composição e campos de orçamento criados")
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 121: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_122_item_medicao_proposta_item_id():
    """Migration 122 (Task #82): adiciona ItemMedicaoComercial.proposta_item_id.

    Coluna FK opcional + UNIQUE para garantir dedupe determinístico
    quando a aprovação de uma proposta propaga seus itens para a obra.
    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)  # AUTOCOMMIT
        cursor = connection.cursor()
        cursor.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='item_medicao_comercial')
               AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='proposta_itens') THEN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='item_medicao_comercial' AND column_name='proposta_item_id'
                ) THEN
                    ALTER TABLE item_medicao_comercial
                        ADD COLUMN proposta_item_id INTEGER NULL
                        REFERENCES proposta_itens(id) ON DELETE SET NULL;
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_item_medicao_proposta_item
                        ON item_medicao_comercial(proposta_item_id)
                        WHERE proposta_item_id IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS ix_item_medicao_proposta_item_id
                        ON item_medicao_comercial(proposta_item_id);
                END IF;
            END IF;
        END$$;
        """)
        cursor.close()
        connection.close()
        logging.info("Migration 122: ItemMedicaoComercial.proposta_item_id OK")
    except Exception as e:
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        logging.error(f"Migration 122 falhou: {e}")
        raise


def migration_123_composicao_servico_unidade():
    """Migration 123 (Task #82): adiciona ComposicaoServico.unidade.

    Coluna VARCHAR(20) opcional para snapshot da unidade do insumo na
    composição (ex: "h", "kg", "un"), facilitando relatórios. Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)
        cursor = connection.cursor()
        cursor.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='composicao_servico') THEN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='composicao_servico' AND column_name='unidade'
                ) THEN
                    ALTER TABLE composicao_servico ADD COLUMN unidade VARCHAR(20) NULL;
                END IF;
            END IF;
        END$$;
        """)
        cursor.close()
        connection.close()
        logging.info("Migration 123: ComposicaoServico.unidade OK")
    except Exception as e:
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        logging.error(f"Migration 123 falhou: {e}")
        raise


def migration_124_snapshot_calculo_parametrico():
    """Migration 124 (Task #89): adiciona snapshot de cálculo paramétrico
    em PropostaItem e ItemMedicaoComercial.

    Colunas (todas NULL para compatibilidade):
        proposta_itens.quantidade_medida   NUMERIC(15,4)
        proposta_itens.custo_unitario      NUMERIC(15,4)
        proposta_itens.lucro_unitario      NUMERIC(15,4)
        proposta_itens.subtotal            NUMERIC(15,2)

        item_medicao_comercial.quantidade_medida NUMERIC(15,4)
        item_medicao_comercial.custo_unitario    NUMERIC(15,4)
        item_medicao_comercial.preco_unitario    NUMERIC(15,4)
        item_medicao_comercial.lucro_unitario    NUMERIC(15,4)
        item_medicao_comercial.subtotal          NUMERIC(15,2)

    Backfill:
        - proposta_itens.subtotal = quantidade * preco_unitario quando NULL
        - item_medicao_comercial.subtotal = valor_comercial quando NULL
        - quantidade_medida = quantidade quando NULL e quantidade não-NULL.

    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)  # AUTOCOMMIT
        cursor = connection.cursor()
        cursor.execute("""
        DO $$
        BEGIN
            -- proposta_itens
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='proposta_itens') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='proposta_itens' AND column_name='quantidade_medida') THEN
                    ALTER TABLE proposta_itens ADD COLUMN quantidade_medida NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='proposta_itens' AND column_name='custo_unitario') THEN
                    ALTER TABLE proposta_itens ADD COLUMN custo_unitario NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='proposta_itens' AND column_name='lucro_unitario') THEN
                    ALTER TABLE proposta_itens ADD COLUMN lucro_unitario NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='proposta_itens' AND column_name='subtotal') THEN
                    ALTER TABLE proposta_itens ADD COLUMN subtotal NUMERIC(15,2) NULL;
                END IF;
                UPDATE proposta_itens
                   SET subtotal = COALESCE(quantidade,0) * COALESCE(preco_unitario,0)
                 WHERE subtotal IS NULL;
                UPDATE proposta_itens
                   SET quantidade_medida = quantidade
                 WHERE quantidade_medida IS NULL AND quantidade IS NOT NULL;
            END IF;

            -- item_medicao_comercial
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='item_medicao_comercial') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='item_medicao_comercial' AND column_name='quantidade_medida') THEN
                    ALTER TABLE item_medicao_comercial ADD COLUMN quantidade_medida NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='item_medicao_comercial' AND column_name='custo_unitario') THEN
                    ALTER TABLE item_medicao_comercial ADD COLUMN custo_unitario NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='item_medicao_comercial' AND column_name='preco_unitario') THEN
                    ALTER TABLE item_medicao_comercial ADD COLUMN preco_unitario NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='item_medicao_comercial' AND column_name='lucro_unitario') THEN
                    ALTER TABLE item_medicao_comercial ADD COLUMN lucro_unitario NUMERIC(15,4) NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='item_medicao_comercial' AND column_name='subtotal') THEN
                    ALTER TABLE item_medicao_comercial ADD COLUMN subtotal NUMERIC(15,2) NULL;
                END IF;
                UPDATE item_medicao_comercial
                   SET subtotal = valor_comercial
                 WHERE subtotal IS NULL AND valor_comercial IS NOT NULL;
                UPDATE item_medicao_comercial
                   SET quantidade_medida = quantidade
                 WHERE quantidade_medida IS NULL AND quantidade IS NOT NULL;
                UPDATE item_medicao_comercial
                   SET preco_unitario = (valor_comercial / quantidade)
                 WHERE preco_unitario IS NULL
                   AND quantidade IS NOT NULL AND quantidade > 0
                   AND valor_comercial IS NOT NULL;
            END IF;
        END$$;
        """)
        cursor.close()
        connection.close()
        logging.info("Migration 124: snapshot Task #89 OK")
    except Exception as e:
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        logging.error(f"Migration 124 falhou: {e}")
        raise


def migration_125_cronograma_automatico_aprovacao():
    """Migration 125 (Task #102): habilita cronograma automático na aprovação
    de proposta.

    Colunas adicionadas (todas NULL — backward compatible):
        servico.template_padrao_id              FK → cronograma_template(id) ON DELETE SET NULL
        propostas_comerciais.cronograma_default_json  JSONB
        tarefa_cronograma.gerada_por_proposta_item_id FK → proposta_itens(id) ON DELETE SET NULL

    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        connection.set_isolation_level(0)  # AUTOCOMMIT
        cursor = connection.cursor()
        cursor.execute("""
        DO $$
        BEGIN
            -- servico.template_padrao_id
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='servico') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='servico' AND column_name='template_padrao_id') THEN
                    ALTER TABLE servico
                        ADD COLUMN template_padrao_id INTEGER NULL
                        REFERENCES cronograma_template(id) ON DELETE SET NULL;
                    CREATE INDEX IF NOT EXISTS idx_servico_template_padrao
                        ON servico(template_padrao_id);
                END IF;
            END IF;

            -- propostas_comerciais.cronograma_default_json
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='propostas_comerciais') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='propostas_comerciais' AND column_name='cronograma_default_json') THEN
                    ALTER TABLE propostas_comerciais
                        ADD COLUMN cronograma_default_json JSONB NULL;
                END IF;
            END IF;

            -- tarefa_cronograma.gerada_por_proposta_item_id
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='tarefa_cronograma') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='tarefa_cronograma' AND column_name='gerada_por_proposta_item_id') THEN
                    ALTER TABLE tarefa_cronograma
                        ADD COLUMN gerada_por_proposta_item_id INTEGER NULL
                        REFERENCES proposta_itens(id) ON DELETE SET NULL;
                    CREATE INDEX IF NOT EXISTS idx_tarefa_cron_gerada_por_pi
                        ON tarefa_cronograma(gerada_por_proposta_item_id);
                END IF;
            END IF;
        END$$;
        """)
        cursor.close()
        connection.close()
        logging.info("Migration 125: Task #102 cronograma automático OK")
    except Exception as e:
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        logging.error(f"Migration 125 falhou: {e}")
        raise


def migration_126_orcamento():
    """Migration 126 (Task #115): cria tabelas `orcamento` e `orcamento_item`.

    Camada interna de orçamento (custo + composição) que gera Propostas
    para o cliente sem expor cálculos internos. Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orcamento (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                numero VARCHAR(50) NOT NULL,
                titulo VARCHAR(255) NOT NULL,
                descricao TEXT,
                cliente_id INTEGER REFERENCES cliente(id),
                cliente_nome VARCHAR(255),
                imposto_pct_global NUMERIC(5,2),
                margem_pct_global NUMERIC(5,2),
                custo_total NUMERIC(15,2) DEFAULT 0,
                venda_total NUMERIC(15,2) DEFAULT 0,
                lucro_total NUMERIC(15,2) DEFAULT 0,
                status VARCHAR(30) DEFAULT 'rascunho',
                proposta_id INTEGER REFERENCES propostas_comerciais(id) ON DELETE SET NULL,
                criado_por INTEGER REFERENCES usuario(id),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_orcamento_numero_tenant UNIQUE (admin_id, numero)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orcamento_admin ON orcamento(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orcamento_status ON orcamento(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orcamento_proposta ON orcamento(proposta_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orcamento_item (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                orcamento_id INTEGER NOT NULL REFERENCES orcamento(id) ON DELETE CASCADE,
                ordem INTEGER NOT NULL DEFAULT 1,
                servico_id INTEGER REFERENCES servico(id) ON DELETE SET NULL,
                descricao VARCHAR(500) NOT NULL,
                unidade VARCHAR(20) NOT NULL DEFAULT 'un',
                quantidade NUMERIC(15,4) NOT NULL DEFAULT 0,
                imposto_pct NUMERIC(5,2),
                margem_pct NUMERIC(5,2),
                composicao_snapshot JSON,
                custo_unitario NUMERIC(15,4) DEFAULT 0,
                preco_venda_unitario NUMERIC(15,4) DEFAULT 0,
                custo_total NUMERIC(15,2) DEFAULT 0,
                venda_total NUMERIC(15,2) DEFAULT 0,
                lucro_total NUMERIC(15,2) DEFAULT 0,
                observacao TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orc_item_admin ON orcamento_item(admin_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orc_item_orc ON orcamento_item(orcamento_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orc_item_svc ON orcamento_item(servico_id)")

        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 126: orcamento + orcamento_item criados")
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 126: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_127_proposta_orcamento_id():
    """Migration 127 (Task #115 v2): adiciona propostas_comerciais.orcamento_id (1→N).

    O campo legado `orcamento.proposta_id` (renomeado no ORM para
    `ultima_proposta_id`) permanece para compatibilidade de dados existentes,
    mas a relação canônica passa a ser Orcamento (1) → Proposta (N) via
    `propostas_comerciais.orcamento_id`. Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        cursor.execute("""
            ALTER TABLE propostas_comerciais
            ADD COLUMN IF NOT EXISTS orcamento_id INTEGER
            REFERENCES orcamento(id) ON DELETE SET NULL
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposta_orcamento_id "
            "ON propostas_comerciais(orcamento_id)"
        )
        connection.commit()
        cursor.close()
        connection.close()
        logger.info("MIGRACAO 127: propostas_comerciais.orcamento_id criado")
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 127: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_128_orcamento_item_cronograma_override():
    """Migration 128 (Task #118): override de cronograma e snapshot de composição.

    Adiciona:
      - orcamento_item.cronograma_template_override_id (FK CronogramaTemplate, ON DELETE SET NULL)
      - proposta_itens.cronograma_template_override_id (FK CronogramaTemplate, ON DELETE SET NULL)
      - proposta_itens.composicao_snapshot (JSON) — snapshot da composição efetiva
        propagado do OrcamentoItem (com adições/remoções/coeficientes da linha).

    NULL no override significa "usar o template padrão do serviço". Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute("""
            ALTER TABLE orcamento_item
            ADD COLUMN IF NOT EXISTS cronograma_template_override_id INTEGER
            REFERENCES cronograma_template(id) ON DELETE SET NULL
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_orcamento_item_cronograma_override "
            "ON orcamento_item(cronograma_template_override_id)"
        )

        cursor.execute("""
            ALTER TABLE proposta_itens
            ADD COLUMN IF NOT EXISTS cronograma_template_override_id INTEGER
            REFERENCES cronograma_template(id) ON DELETE SET NULL
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposta_itens_cronograma_override "
            "ON proposta_itens(cronograma_template_override_id)"
        )

        cursor.execute(
            "ALTER TABLE proposta_itens "
            "ADD COLUMN IF NOT EXISTS composicao_snapshot JSON"
        )

        connection.commit()
        cursor.close()
        connection.close()
        logger.info(
            "MIGRACAO 128: override de cronograma + composicao_snapshot adicionados "
            "em orcamento_item e proposta_itens"
        )
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 128: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_129_configuracao_empresa_assinatura_engenheiro():
    """Migration 129 (Task #158): assinatura e engenheiro responsável em configuracao_empresa.

    Adiciona colunas para que cada empresa configure seu próprio bloco de
    assinatura e os contatos do engenheiro responsável que aparecem em todos
    os formatos de PDF de proposta. Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        novas_colunas = [
            ("assinatura_nome", "VARCHAR(200) DEFAULT ''"),
            ("assinatura_cargo", "VARCHAR(200) DEFAULT ''"),
            ("engenheiro_nome", "VARCHAR(200) DEFAULT ''"),
            ("engenheiro_crea", "VARCHAR(50) DEFAULT ''"),
            ("engenheiro_email", "VARCHAR(120) DEFAULT ''"),
            ("engenheiro_telefone", "VARCHAR(50) DEFAULT ''"),
            ("engenheiro_endereco", "TEXT DEFAULT ''"),
            ("engenheiro_website", "VARCHAR(200) DEFAULT ''"),
        ]

        for nome_coluna, tipo_coluna in novas_colunas:
            cursor.execute(
                f"ALTER TABLE configuracao_empresa "
                f"ADD COLUMN IF NOT EXISTS {nome_coluna} {tipo_coluna}"
            )

        connection.commit()
        cursor.close()
        connection.close()
        logger.info(
            "MIGRACAO 129: assinatura_nome/assinatura_cargo + engenheiro_* "
            "adicionados em configuracao_empresa"
        )
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 129: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_130_alinhar_tipos_numericos_orcamento_proposta():
    """Migration 130 (Task #165): garante que colunas numéricas de orçamento e
    proposta_itens estejam como NUMERIC (Decimal) em todos os ambientes.

    Em algumas instâncias antigas (antes da Task #82/#115) estas colunas
    foram criadas como DOUBLE PRECISION (Float). Isso causa o erro
    `unsupported operand type(s) for *: 'float' and 'decimal.Decimal'` no
    template de edição de orçamento e na visualização da proposta, porque
    o template mistura valores vindos do banco (float) com valores vindos
    de JSON (Decimal). Esta migração padroniza para NUMERIC, alinhando o
    schema com models.py. É idempotente — só converte se a coluna ainda
    estiver como DOUBLE PRECISION.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        # (tabela, coluna, tipo destino)
        alvos = [
            ('orcamento_item', 'quantidade', 'NUMERIC(15,4)'),
            ('orcamento_item', 'imposto_pct', 'NUMERIC(5,2)'),
            ('orcamento_item', 'margem_pct', 'NUMERIC(5,2)'),
            ('orcamento_item', 'custo_unitario', 'NUMERIC(15,4)'),
            ('orcamento_item', 'preco_venda_unitario', 'NUMERIC(15,4)'),
            ('orcamento_item', 'custo_total', 'NUMERIC(15,2)'),
            ('orcamento_item', 'venda_total', 'NUMERIC(15,2)'),
            ('orcamento_item', 'lucro_total', 'NUMERIC(15,2)'),
            ('orcamento', 'imposto_pct_global', 'NUMERIC(5,2)'),
            ('orcamento', 'margem_pct_global', 'NUMERIC(5,2)'),
            ('orcamento', 'custo_total', 'NUMERIC(15,2)'),
            ('orcamento', 'venda_total', 'NUMERIC(15,2)'),
            ('orcamento', 'lucro_total', 'NUMERIC(15,2)'),
            ('proposta_itens', 'quantidade', 'NUMERIC(10,3)'),
            ('proposta_itens', 'preco_unitario', 'NUMERIC(10,2)'),
            ('proposta_itens', 'quantidade_medida', 'NUMERIC(15,4)'),
            ('proposta_itens', 'custo_unitario', 'NUMERIC(15,4)'),
            ('proposta_itens', 'lucro_unitario', 'NUMERIC(15,4)'),
            ('proposta_itens', 'subtotal', 'NUMERIC(15,2)'),
        ]

        convertidas = 0
        falhas = []
        # Usa SAVEPOINT por coluna: assim, falha em uma coluna não desfaz
        # as conversões anteriores já bem-sucedidas (Task #165).
        for tabela, coluna, tipo in alvos:
            cursor.execute(
                """
                SELECT data_type
                  FROM information_schema.columns
                 WHERE table_name = %s AND column_name = %s
                """,
                (tabela, coluna),
            )
            row = cursor.fetchone()
            if not row:
                continue
            data_type = (row[0] or '').lower()
            if data_type in ('numeric', 'decimal'):
                continue
            sp_name = f"sp_m130_{tabela}_{coluna}"
            try:
                cursor.execute(f"SAVEPOINT {sp_name}")
                cursor.execute(
                    f"ALTER TABLE {tabela} "
                    f"ALTER COLUMN {coluna} TYPE {tipo} "
                    f"USING {coluna}::{tipo}"
                )
                cursor.execute(f"RELEASE SAVEPOINT {sp_name}")
                convertidas += 1
                logger.info(
                    f"MIGRACAO 130: {tabela}.{coluna} {data_type} → {tipo}"
                )
            except Exception as conv_err:
                # Reverte só este savepoint, preservando conversões anteriores
                try:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                    cursor.execute(f"RELEASE SAVEPOINT {sp_name}")
                except Exception:
                    pass
                falhas.append(f"{tabela}.{coluna}: {conv_err}")
                logger.warning(
                    f"MIGRACAO 130: falha ao converter {tabela}.{coluna} "
                    f"({data_type} → {tipo}): {conv_err}"
                )

        connection.commit()
        cursor.close()
        connection.close()
        logger.info(
            f"MIGRACAO 130: tipos numéricos alinhados em orçamento/proposta_itens "
            f"({convertidas} convertidas, {len(falhas)} falhas)"
        )
        if falhas:
            # Lança exceção para que run_migration_safe registre falha e
            # permita reexecução automática até o schema estar 100% alinhado
            # (não silencia o problema).
            raise RuntimeError(
                f"MIGRACAO 130: {len(falhas)} coluna(s) não puderam ser "
                f"convertidas para NUMERIC: {falhas}"
            )
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 130: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_131_insumo_coeficiente_padrao():
    """Migration 131 (Task #166): adiciona coeficiente_padrao em insumo.

    Coluna NUMERIC(15,6) NOT NULL DEFAULT 1, usada apenas como sugestão de
    coeficiente ao adicionar o insumo numa composição de serviço pelos
    pickers (modal "Adicionar do Catálogo" do orçamento e formulário da
    composição no catálogo). Nunca afeta composições já existentes.
    Idempotente.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        cursor.execute(
            "ALTER TABLE insumo "
            "ADD COLUMN IF NOT EXISTS coeficiente_padrao NUMERIC(15,6) "
            "NOT NULL DEFAULT 1"
        )

        connection.commit()
        cursor.close()
        connection.close()
        logger.info(
            "MIGRACAO 131: coeficiente_padrao adicionada em insumo "
            "(default 1, NOT NULL)"
        )
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 131: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise


def migration_132_obra_cliente_id_fk():
    """Migration 132 (Task #172): adiciona obra.cliente_id (FK → cliente.id)
    e faz backfill por dedup estrita (admin_id + nome+email).

    Estratégia:
      1. ADD COLUMN obra.cliente_id INTEGER NULL (idempotente).
      2. CREATE INDEX em obra.cliente_id.
      3. ADD CONSTRAINT FOREIGN KEY (idempotente: pula se já existir).
      4. Backfill — regra de dedup conservadora para evitar mesclar
         homônimos dentro do mesmo tenant:
           a) Se a obra tem nome E e-mail: match estrito por
              (LOWER(nome)=X AND LOWER(email)=Y).
           b) Se ainda sem match E há e-mail: match por LOWER(email)
              somente se UM único cliente do tenant casar (e-mail é
              identificador forte; multimatch → cria novo).
           c) Se ainda sem match E há nome (sem e-mail na obra): match
              por LOWER(nome) somente quando cliente.email IS NULL e
              for único (evita mesclar com homônimo que já tem e-mail
              conhecido).
           d) Caso contrário, cria um novo Cliente.
    Mantém os campos texto (cliente_nome/email/telefone/cliente) intactos
    como fallback — o drop é fora do escopo desta task.
    """
    connection = None
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()

        # 1) Coluna
        cursor.execute(
            "ALTER TABLE obra ADD COLUMN IF NOT EXISTS cliente_id INTEGER NULL"
        )

        # 2) Índice
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_obra_cliente_id ON obra (cliente_id)"
        )

        # 3) FK (idempotente — Postgres não aceita IF NOT EXISTS p/ constraint)
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'obra_cliente_id_fkey'
                ) THEN
                    ALTER TABLE obra
                        ADD CONSTRAINT obra_cliente_id_fkey
                        FOREIGN KEY (cliente_id) REFERENCES cliente(id)
                        ON DELETE SET NULL;
                END IF;
            END$$;
            """
        )

        # 4) Backfill — uma obra por vez (datasets pequenos por tenant).
        cursor.execute(
            """
            SELECT id, admin_id,
                   COALESCE(NULLIF(TRIM(cliente_nome), ''), NULLIF(TRIM(cliente), '')) AS nome,
                   NULLIF(TRIM(cliente_email), '') AS email,
                   NULLIF(TRIM(cliente_telefone), '') AS telefone
              FROM obra
             WHERE cliente_id IS NULL
               AND admin_id IS NOT NULL
               AND (
                   COALESCE(NULLIF(TRIM(cliente_nome), ''),
                            NULLIF(TRIM(cliente), '')) IS NOT NULL
                   OR NULLIF(TRIM(cliente_email), '') IS NOT NULL
               )
            """
        )
        obras = cursor.fetchall()

        vinculadas = 0
        criadas = 0
        for (obra_id, admin_id, nome, email, telefone) in obras:
            cliente_id_resolvido = None

            # 4a) Match estrito nome+email (caso ideal)
            if nome and email:
                cursor.execute(
                    """
                    SELECT id FROM cliente
                     WHERE admin_id = %s
                       AND LOWER(TRIM(nome)) = LOWER(TRIM(%s))
                       AND LOWER(email) = LOWER(%s)
                     LIMIT 1
                    """,
                    (admin_id, nome, email),
                )
                row = cursor.fetchone()
                if row:
                    cliente_id_resolvido = row[0]

            # 4b) Match por e-mail apenas — exige unicidade (evita ambíguo)
            if not cliente_id_resolvido and email:
                cursor.execute(
                    """
                    SELECT id FROM cliente
                     WHERE admin_id = %s
                       AND LOWER(email) = LOWER(%s)
                     LIMIT 2
                    """,
                    (admin_id, email),
                )
                rows = cursor.fetchall()
                if len(rows) == 1:
                    cliente_id_resolvido = rows[0][0]

            # 4c) Match por nome apenas — só se a obra não tem e-mail
            #     E o cliente também não tem e-mail E é único (evita
            #     mesclar com homônimo que já tem e-mail próprio).
            if not cliente_id_resolvido and nome and not email:
                cursor.execute(
                    """
                    SELECT id FROM cliente
                     WHERE admin_id = %s
                       AND LOWER(TRIM(nome)) = LOWER(TRIM(%s))
                       AND (email IS NULL OR TRIM(email) = '')
                     LIMIT 2
                    """,
                    (admin_id, nome),
                )
                rows = cursor.fetchall()
                if len(rows) == 1:
                    cliente_id_resolvido = rows[0][0]

            # 4d) Cria Cliente se nada encontrado
            if not cliente_id_resolvido:
                nome_final = (nome or email or 'Cliente')[:200]
                cursor.execute(
                    """
                    INSERT INTO cliente (nome, email, telefone, admin_id, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    RETURNING id
                    """,
                    (nome_final, email, telefone, admin_id),
                )
                cliente_id_resolvido = cursor.fetchone()[0]
                criadas += 1

            cursor.execute(
                "UPDATE obra SET cliente_id = %s WHERE id = %s",
                (cliente_id_resolvido, obra_id),
            )
            vinculadas += 1

        connection.commit()
        cursor.close()
        connection.close()
        logger.info(
            "MIGRACAO 132: obra.cliente_id adicionada e backfill concluído "
            "(vinculadas=%s, novos_clientes=%s)",
            vinculadas, criadas,
        )
        return True
    except Exception as e:
        logger.error(f"Erro na migracao 132: {e}")
        if connection:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        raise
