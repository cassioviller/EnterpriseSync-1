#!/usr/bin/env python3
"""
FLEET MANAGEMENT SYSTEM V3.0 - MIGRAÇÃO COMPLETA
=====================================================
Script único e determinístico para reconstrução total do sistema de veículos
- Backup de dados existentes
- Drop de todas as tabelas legadas 
- Criação das novas tabelas Fleet
- Migração de dados (se necessário)
- Validação do novo sistema

🎯 OBJETIVO: Solução definitiva sem conflitos de nomenclatura
"""

import os
import sys
import json
import traceback
from datetime import datetime, date
import psycopg2
from decimal import Decimal

# Configurar caminhos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log_migration(message):
    """Log com timestamp para acompanhar o progresso"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

def execute_sql_safe(cursor, sql, description):
    """Executa SQL com tratamento de erro robusto"""
    try:
        log_migration(f"🔧 {description}")
        cursor.execute(sql)
        log_migration(f"✅ {description} - SUCESSO")
        return True
    except Exception as e:
        log_migration(f"⚠️ {description} - ERRO: {e}")
        return False

def backup_legacy_tables(cursor):
    """Backup de dados das tabelas legadas para possível recuperação"""
    log_migration("📦 INICIANDO BACKUP DAS TABELAS LEGADAS")
    
    backup_data = {
        'backup_timestamp': datetime.now().isoformat(),
        'tables': {}
    }
    
    # Lista de tabelas legadas para backup
    legacy_tables = [
        'veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo',
        'alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo', 
        'manutencao_veiculo', 'alerta_veiculo'
    ]
    
    for table_name in legacy_tables:
        try:
            # Verificar se a tabela existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table_name,))
            
            if cursor.fetchone()[0]:
                # Backup dos dados
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                # Obter nomes das colunas
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    ORDER BY ordinal_position
                """, (table_name,))
                columns = [row[0] for row in cursor.fetchall()]
                
                # Converter dados para formato JSON serializável
                table_data = []
                for row in rows:
                    row_dict = {}
                    for i, value in enumerate(row):
                        if isinstance(value, (date, datetime)):
                            row_dict[columns[i]] = value.isoformat()
                        elif isinstance(value, Decimal):
                            row_dict[columns[i]] = float(value)
                        else:
                            row_dict[columns[i]] = value
                    table_data.append(row_dict)
                
                backup_data['tables'][table_name] = {
                    'columns': columns,
                    'data': table_data,
                    'row_count': len(table_data)
                }
                
                log_migration(f"✅ Backup {table_name}: {len(table_data)} registros")
            else:
                log_migration(f"⚠️ Tabela {table_name} não existe - pular backup")
                
        except Exception as e:
            log_migration(f"❌ Erro no backup de {table_name}: {e}")
    
    # Salvar backup em arquivo
    backup_filename = f"fleet_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        log_migration(f"💾 Backup salvo em: {backup_filename}")
        return backup_filename
    except Exception as e:
        log_migration(f"❌ Erro ao salvar backup: {e}")
        return None

def drop_legacy_tables(cursor):
    """Remove todas as tabelas legadas de veículos"""
    log_migration("🗑️ REMOVENDO TABELAS LEGADAS")
    
    # Lista completa de tabelas para remover (ordem importa devido a FKs)
    legacy_tables = [
        'passageiro_veiculo',
        'custo_veiculo', 
        'uso_veiculo',
        'alocacao_veiculo',
        'equipe_veiculo',
        'transferencia_veiculo',
        'manutencao_veiculo',
        'alerta_veiculo',
        'veiculo'  # Por último devido às FKs
    ]
    
    dropped_count = 0
    
    for table_name in legacy_tables:
        if execute_sql_safe(cursor, f"DROP TABLE IF EXISTS {table_name} CASCADE", 
                           f"Removendo tabela {table_name}"):
            dropped_count += 1
    
    log_migration(f"✅ Removidas {dropped_count} tabelas legadas")
    return dropped_count

def create_fleet_tables(cursor):
    """Cria as novas tabelas Fleet com schema moderno"""
    log_migration("🏗️ CRIANDO NOVAS TABELAS FLEET")
    
    # 1. FleetVehicle - Tabela principal de veículos
    fleet_vehicle_sql = """
    CREATE TABLE IF NOT EXISTS fleet_vehicle (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        
        -- Dados obrigatórios
        plate VARCHAR(20) NOT NULL,
        brand VARCHAR(50) NOT NULL,
        model VARCHAR(100) NOT NULL DEFAULT 'Não informado',
        kind VARCHAR(30) NOT NULL DEFAULT 'Veículo',
        
        -- Dados opcionais
        year INTEGER,
        color VARCHAR(30),
        chassis VARCHAR(50),
        renavam VARCHAR(20),
        fuel_type VARCHAR(20) DEFAULT 'Gasolina',
        
        -- Controle
        odometer INTEGER DEFAULT 0,
        status VARCHAR(20) DEFAULT 'Ativo',
        last_maintenance_date DATE,
        next_maintenance_date DATE,
        next_maintenance_km INTEGER,
        
        -- Auditoria
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT uk_fleet_vehicle_admin_plate UNIQUE(admin_id, plate),
        CONSTRAINT ck_fleet_vehicle_positive_odometer CHECK(odometer >= 0)
    );
    """
    
    # 2. FleetTrip - Viagens/uso
    fleet_trip_sql = """
    CREATE TABLE IF NOT EXISTS fleet_trip (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        
        -- Relacionamentos
        vehicle_id INTEGER NOT NULL REFERENCES fleet_vehicle(id) ON DELETE CASCADE,
        driver_id INTEGER REFERENCES funcionario(id) ON DELETE SET NULL,
        obra_id INTEGER REFERENCES obra(id) ON DELETE SET NULL,
        
        -- Dados da viagem
        trip_date DATE NOT NULL,
        start_time TIME,
        end_time TIME,
        
        -- Quilometragem
        start_odometer INTEGER,
        end_odometer INTEGER,
        distance INTEGER,
        
        -- Detalhes
        purpose VARCHAR(200),
        notes TEXT,
        
        -- Auditoria
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT ck_fleet_trip_time_order CHECK(
            end_time >= start_time OR end_time IS NULL OR start_time IS NULL
        ),
        CONSTRAINT ck_fleet_trip_odometer_order CHECK(
            end_odometer >= start_odometer OR end_odometer IS NULL OR start_odometer IS NULL
        )
    );
    """
    
    # 3. FleetCost - Custos
    fleet_cost_sql = """
    CREATE TABLE IF NOT EXISTS fleet_cost (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        
        -- Relacionamentos
        vehicle_id INTEGER NOT NULL REFERENCES fleet_vehicle(id) ON DELETE CASCADE,
        obra_id INTEGER REFERENCES obra(id) ON DELETE SET NULL,
        
        -- Categoria e financeiro
        category VARCHAR(30) NOT NULL,
        amount NUMERIC(12,2) NOT NULL,
        cost_date DATE NOT NULL,
        
        -- Detalhes
        description VARCHAR(200) NOT NULL,
        supplier VARCHAR(100),
        invoice_number VARCHAR(20),
        due_date DATE,
        
        -- Pagamento
        payment_status VARCHAR(20) DEFAULT 'Pendente',
        payment_method VARCHAR(30),
        
        -- Controle
        vehicle_odometer INTEGER,
        notes TEXT,
        
        -- Auditoria
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT ck_fleet_cost_positive_amount CHECK(amount > 0)
    );
    """
    
    # 4. FleetPassenger - Passageiros
    fleet_passenger_sql = """
    CREATE TABLE IF NOT EXISTS fleet_passenger (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        
        -- Relacionamentos
        trip_id INTEGER NOT NULL REFERENCES fleet_trip(id) ON DELETE CASCADE,
        funcionario_id INTEGER NOT NULL REFERENCES funcionario(id) ON DELETE CASCADE,
        
        -- Auditoria
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT uk_fleet_passenger_trip_funcionario UNIQUE(trip_id, funcionario_id)
    );
    """
    
    # Executar criação das tabelas
    tables = [
        (fleet_vehicle_sql, "fleet_vehicle"),
        (fleet_trip_sql, "fleet_trip"), 
        (fleet_cost_sql, "fleet_cost"),
        (fleet_passenger_sql, "fleet_passenger")
    ]
    
    created_count = 0
    for sql, name in tables:
        if execute_sql_safe(cursor, sql, f"Criando tabela {name}"):
            created_count += 1
    
    log_migration(f"✅ Criadas {created_count}/4 tabelas Fleet")
    return created_count

def create_fleet_indexes(cursor):
    """Cria índices otimizados para performance"""
    log_migration("⚡ CRIANDO ÍNDICES DE PERFORMANCE")
    
    indexes = [
        # FleetVehicle
        ("CREATE INDEX IF NOT EXISTS idx_fleet_vehicle_admin ON fleet_vehicle(admin_id)", "fleet_vehicle admin"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_vehicle_status ON fleet_vehicle(admin_id, status)", "fleet_vehicle status"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_vehicle_kind ON fleet_vehicle(admin_id, kind)", "fleet_vehicle kind"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_vehicle_plate ON fleet_vehicle(plate)", "fleet_vehicle plate"),
        
        # FleetTrip  
        ("CREATE INDEX IF NOT EXISTS idx_fleet_trip_admin ON fleet_trip(admin_id)", "fleet_trip admin"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_trip_date_admin ON fleet_trip(trip_date, admin_id)", "fleet_trip date"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_trip_vehicle ON fleet_trip(vehicle_id, trip_date)", "fleet_trip vehicle"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_trip_driver ON fleet_trip(driver_id)", "fleet_trip driver"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_trip_obra ON fleet_trip(obra_id)", "fleet_trip obra"),
        
        # FleetCost
        ("CREATE INDEX IF NOT EXISTS idx_fleet_cost_admin ON fleet_cost(admin_id)", "fleet_cost admin"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_cost_date_admin ON fleet_cost(cost_date, admin_id)", "fleet_cost date"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_cost_category ON fleet_cost(category, admin_id)", "fleet_cost category"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_cost_vehicle ON fleet_cost(vehicle_id, cost_date)", "fleet_cost vehicle"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_cost_obra ON fleet_cost(obra_id, cost_date)", "fleet_cost obra"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_cost_status ON fleet_cost(payment_status, admin_id)", "fleet_cost status"),
        
        # FleetPassenger
        ("CREATE INDEX IF NOT EXISTS idx_fleet_passenger_admin ON fleet_passenger(admin_id)", "fleet_passenger admin"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_passenger_trip ON fleet_passenger(trip_id)", "fleet_passenger trip"),
        ("CREATE INDEX IF NOT EXISTS idx_fleet_passenger_funcionario ON fleet_passenger(funcionario_id)", "fleet_passenger funcionario"),
    ]
    
    created_count = 0
    for sql, description in indexes:
        if execute_sql_safe(cursor, sql, f"Criando índice {description}"):
            created_count += 1
    
    log_migration(f"✅ Criados {created_count}/{len(indexes)} índices")
    return created_count

def validate_fleet_schema(cursor):
    """Valida se o novo schema Fleet foi criado corretamente"""
    log_migration("🔍 VALIDANDO NOVO SCHEMA FLEET")
    
    # Verificar se todas as tabelas existem
    required_tables = ['fleet_vehicle', 'fleet_trip', 'fleet_cost', 'fleet_passenger']
    
    validation_results = {
        'tables_exist': 0,
        'constraints_ok': 0,
        'indexes_ok': 0,
        'ready_for_use': False
    }
    
    for table in required_tables:
        try:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table,))
            
            if cursor.fetchone()[0]:
                validation_results['tables_exist'] += 1
                log_migration(f"✅ Tabela {table} existe")
            else:
                log_migration(f"❌ Tabela {table} NÃO existe")
        except Exception as e:
            log_migration(f"❌ Erro validando {table}: {e}")
    
    # Verificar constraints principais
    constraints_to_check = [
        ('fleet_vehicle', 'uk_fleet_vehicle_admin_plate'),
        ('fleet_passenger', 'uk_fleet_passenger_trip_funcionario')
    ]
    
    for table, constraint in constraints_to_check:
        try:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.table_constraints 
                    WHERE table_name = %s AND constraint_name = %s
                );
            """, (table, constraint))
            
            if cursor.fetchone()[0]:
                validation_results['constraints_ok'] += 1
                log_migration(f"✅ Constraint {constraint} existe")
            else:
                log_migration(f"⚠️ Constraint {constraint} não encontrada")
        except Exception as e:
            log_migration(f"❌ Erro validando constraint {constraint}: {e}")
    
    # Verificar se está pronto para uso
    validation_results['ready_for_use'] = (
        validation_results['tables_exist'] == len(required_tables) and
        validation_results['constraints_ok'] >= 2
    )
    
    if validation_results['ready_for_use']:
        log_migration("🎉 SCHEMA FLEET VALIDADO COM SUCESSO!")
    else:
        log_migration("⚠️ Schema Fleet incompleto - verificar erros acima")
    
    return validation_results

def main():
    """Função principal da migração completa"""
    log_migration("🚀 INICIANDO MIGRAÇÃO FLEET V3.0 - RECONSTRUÇÃO COMPLETA")
    log_migration("=" * 60)
    
    # Verificar ambiente
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        log_migration("❌ DATABASE_URL não encontrada")
        return False
    
    # Detectar ambiente
    is_production = 'neon.tech' in database_url or 'amazonaws.com' in database_url
    environment = "PRODUÇÃO" if is_production else "DESENVOLVIMENTO"
    log_migration(f"🏭 AMBIENTE: {environment}")
    
    # Verificar flag de confirmação para produção
    if is_production:
        run_in_production = os.environ.get('RUN_FLEET_MIGRATION_PRODUCTION') == 'true'
        if not run_in_production:
            log_migration("⚠️ PRODUÇÃO: Defina RUN_FLEET_MIGRATION_PRODUCTION=true para executar")
            return False
        log_migration("🚨 EXECUTANDO EM PRODUÇÃO - BACKUP OBRIGATÓRIO")
    
    try:
        # Conectar ao banco
        log_migration("🔌 Conectando ao banco de dados...")
        conn = psycopg2.connect(database_url)
        conn.autocommit = False  # Usar transações
        cursor = conn.cursor()
        
        # Iniciar transação principal
        cursor.execute("BEGIN")
        log_migration("🔄 Transação iniciada")
        
        # 1. Backup das tabelas legadas
        backup_file = backup_legacy_tables(cursor)
        if not backup_file and is_production:
            log_migration("❌ ERRO: Backup obrigatório em produção falhou")
            cursor.execute("ROLLBACK")
            return False
        
        # 2. Remover tabelas legadas
        dropped_count = drop_legacy_tables(cursor)
        log_migration(f"🗑️ Removidas {dropped_count} tabelas legadas")
        
        # 3. Criar tabelas Fleet
        created_count = create_fleet_tables(cursor)
        if created_count != 4:
            log_migration("❌ ERRO: Nem todas as tabelas Fleet foram criadas")
            cursor.execute("ROLLBACK")
            return False
        
        # 4. Criar índices
        indexes_count = create_fleet_indexes(cursor)
        log_migration(f"⚡ Criados {indexes_count} índices")
        
        # 5. Validar schema
        validation = validate_fleet_schema(cursor)
        if not validation['ready_for_use']:
            log_migration("❌ ERRO: Validação do schema falhou")
            cursor.execute("ROLLBACK")
            return False
        
        # 6. Commit da transação
        cursor.execute("COMMIT")
        log_migration("✅ TRANSAÇÃO COMMITADA COM SUCESSO")
        
        # 7. Relatório final
        log_migration("=" * 60)
        log_migration("🎉 MIGRAÇÃO FLEET V3.0 CONCLUÍDA COM SUCESSO!")
        log_migration(f"📊 RESULTADOS:")
        log_migration(f"   • Backup gerado: {backup_file or 'N/A'}")
        log_migration(f"   • Tabelas removidas: {dropped_count}")
        log_migration(f"   • Tabelas criadas: {created_count}/4")
        log_migration(f"   • Índices criados: {indexes_count}")
        log_migration(f"   • Schema validado: {'✅' if validation['ready_for_use'] else '❌'}")
        log_migration("=" * 60)
        
        return True
        
    except Exception as e:
        log_migration(f"❌ ERRO CRÍTICO: {e}")
        log_migration(f"📋 Stack trace: {traceback.format_exc()}")
        try:
            cursor.execute("ROLLBACK")
            log_migration("🔄 Rollback executado")
        except:
            log_migration("❌ Erro durante rollback")
        return False
        
    finally:
        try:
            cursor.close()
            conn.close()
            log_migration("🔌 Conexão fechada")
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)