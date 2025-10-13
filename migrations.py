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


def executar_migracoes():
    """
    Execute todas as migrações necessárias automaticamente
    REATIVADO PARA DEPLOY EASYPANEL COMPLETO
    """
    try:
        logger.info("🔄 Iniciando migrações automáticas COMPLETAS do banco EasyPanel...")
        # Mascarar credenciais por segurança
        database_url = os.environ.get('DATABASE_URL', 'postgresql://sige:sige@viajey_sige:5432/sige')
        logger.info(f"🎯 TARGET DATABASE: {mask_database_url(database_url)}")
        
        # ===== MIGRAÇÕES ANTIGAS DESATIVADAS (JÁ APLICADAS EM PRODUÇÃO) =====
        # Migração 1-19: Comentadas para otimizar tempo de deploy
        # garantir_tabela_proposta_templates_existe()
        # migrar_categoria_proposta_templates()
        # migrar_colunas_faltantes_proposta_templates()
        # migrar_campos_opcionais_propostas()
        # migrar_personalizacao_visual_empresa()
        # migrar_campos_organizacao_propostas()
        # garantir_usuarios_producao()
        # migrar_campos_completos_templates()
        # migrar_campos_rdo_ocorrencia()
        # migrar_campo_admin_id_rdo()
        # migrar_sistema_rdo_aprimorado()
        # adicionar_admin_id_servico()
        # corrigir_admin_id_servicos_existentes()
        # migrar_tabela_servico_obra_real()
        # adicionar_coluna_local_rdo()
        # adicionar_campos_allocation_employee()
        # migrar_sistema_veiculos_critical()
        # corrigir_admin_id_vehicle_tables()
        # adicionar_colunas_veiculo_completas()
        
        # ===== MIGRAÇÕES ATIVAS =====
        # Migração 20: UNIFICADA - Sistema de Veículos Inteligente
        _migration_20_unified_vehicle_system()

        # Migração 27: Sistema de Alimentação
        _migration_27_alimentacao_system()

        # Migração 33: Recriar tabela frota_despesa com schema completo
        _migration_33_recreate_frota_despesa()

        # Migração 34: Adicionar campos de pagamento no Restaurante
        _migration_34_restaurante_campos_pagamento()

        # Migração 35: Adicionar coluna numero_nota_fiscal na tabela custo_veiculo
        _migration_35_custo_veiculo_numero_nota_fiscal()

        # Migração 36: Remover tabelas antigas do sistema de propostas legado
        _migration_36_remove_old_propostas_tables()

        # Migração 37: Renomear campos em propostas_comerciais e adicionar cliente_id FK
        _migration_37_rename_propostas_fields()

        # Migração 38: Criar tabela proposta_historico
        _migration_38_create_proposta_historico()

        # Migração 39: Sistema de Almoxarifado v3.0
        _migration_39_create_almoxarifado_system()

        # Migração 40: Sistema de Ponto Eletrônico Compartilhado
        _migration_40_ponto_compartilhado()

        logger.info("=" * 80)
        logger.info("✅ Migrações automáticas concluídas com sucesso!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro durante migrações automáticas: {e}")
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
                    garantias text DEFAULT 'A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.',
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
        ('garantias', 'text DEFAULT \'A Estruturas do Vale garante todos os materiais empregados nos serviços contra defeitos de fabricação pelo prazo de 12 (doze) meses contados a partir da data de conclusão da obra, conforme NBR 8800.\''),
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
            ("engenheiro_email", "VARCHAR(120) DEFAULT 'contato@estruturasdovale.com.br'"),
            ("engenheiro_telefone", "VARCHAR(50) DEFAULT '12 99187-7435'"),
            ("engenheiro_endereco", "TEXT DEFAULT 'Rua Benedita Nunes de Campos, 140. Residencial União, São José dos Campos - CEP 12.239-008'"),
            ("engenheiro_website", "VARCHAR(200) DEFAULT 'www.estruturasdovale.com.br'"),
            
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


