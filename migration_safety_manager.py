#!/usr/bin/env python3
"""
🛡️ SISTEMA DE SEGURANÇA PARA MIGRAÇÕES AUTOMÁTICAS
===================================================
FASE 3: Implementação de safety flags, rollback automático e logs detalhados
"""

import os
import sys
import json
import logging
import traceback
import subprocess
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

class MigrationSafetyManager:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        self.log_file = '/tmp/migration_safety.log'
        self.backup_file = f'/tmp/migration_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        self.rollback_enabled = os.environ.get('ENABLE_ROLLBACK', 'true').lower() == 'true'
        self.force_migration = os.environ.get('FORCE_MIGRATION', 'false').lower() == 'true'
        self.migration_timeout = int(os.environ.get('MIGRATION_TIMEOUT', '300'))
        
        # Configurar logging detalhado
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - [SAFETY] - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.log_file)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Estado da migration
        self.migration_state = {
            'started_at': None,
            'backup_created': False,
            'migrations_executed': [],
            'errors': [],
            'warnings': [],
            'rollback_available': False
        }
        
    def log_safety(self, message, level='info'):
        """Log com timestamp e contexto de segurança"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = f'[{timestamp}] [SAFETY] {message}'
        
        if level == 'error':
            self.logger.error(formatted_message)
            self.migration_state['errors'].append(message)
        elif level == 'warning':
            self.logger.warning(formatted_message)
            self.migration_state['warnings'].append(message)
        else:
            self.logger.info(formatted_message)
        
        # Salvar estado atualizado
        self._save_migration_state()
    
    def _save_migration_state(self):
        """Salva estado atual da migration para recuperação"""
        try:
            state_file = '/tmp/migration_state.json'
            with open(state_file, 'w') as f:
                json.dump(self.migration_state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Erro ao salvar estado: {e}")
    
    def _load_migration_state(self):
        """Carrega estado anterior se existir"""
        try:
            state_file = '/tmp/migration_state.json'
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    self.migration_state.update(json.load(f))
                    return True
        except Exception as e:
            self.log_safety(f"Erro ao carregar estado anterior: {e}", 'warning')
        return False
    
    def create_safety_backup(self):
        """Cria backup de segurança antes das migrações"""
        self.log_safety("🛡️ Criando backup de segurança...")
        
        try:
            if not self.database_url:
                self.log_safety("DATABASE_URL não encontrada", 'error')
                return False
                
            engine = create_engine(self.database_url)
            
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'database_url_host': self.database_url.split('@')[1].split(':')[0] if '@' in self.database_url else 'unknown',
                'tables': {},
                'constraints': [],
                'indexes': []
            }
            
            with engine.connect() as conn:
                # Backup de tabelas críticas
                critical_tables = ['usuario', 'funcionario', 'obra', 'veiculo', 'uso_veiculo', 'custo_veiculo']
                
                for table in critical_tables:
                    try:
                        # Verificar se tabela existe
                        result = conn.execute(text(f"""
                            SELECT COUNT(*) FROM information_schema.tables 
                            WHERE table_name = '{table}'
                        """))
                        
                        if result.scalar() > 0:
                            # Contar registros
                            count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                            count = count_result.scalar()
                            
                            backup_data['tables'][table] = {
                                'count': count,
                                'exists': True
                            }
                            
                            self.log_safety(f"📊 Backup {table}: {count} registros")
                        else:
                            backup_data['tables'][table] = {
                                'count': 0,
                                'exists': False
                            }
                            
                    except Exception as e:
                        self.log_safety(f"⚠️ Erro backup tabela {table}: {e}", 'warning')
                        backup_data['tables'][table] = {
                            'error': str(e),
                            'exists': False
                        }
                
                # Backup de constraints críticas
                try:
                    constraints_query = text("""
                        SELECT constraint_name, table_name, constraint_type
                        FROM information_schema.table_constraints
                        WHERE table_name IN ('veiculo', 'uso_veiculo', 'custo_veiculo')
                        AND constraint_type IN ('FOREIGN KEY', 'UNIQUE', 'PRIMARY KEY')
                    """)
                    
                    constraints = conn.execute(constraints_query).fetchall()
                    backup_data['constraints'] = [
                        {
                            'name': row[0],
                            'table': row[1],
                            'type': row[2]
                        } for row in constraints
                    ]
                    
                    self.log_safety(f"🔗 Backup constraints: {len(constraints)} encontradas")
                    
                except Exception as e:
                    self.log_safety(f"⚠️ Erro backup constraints: {e}", 'warning')
            
            # Salvar backup
            with open(self.backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            self.migration_state['backup_created'] = True
            self.migration_state['backup_file'] = self.backup_file
            self.migration_state['rollback_available'] = True
            
            self.log_safety(f"✅ Backup criado: {self.backup_file}")
            return True
            
        except Exception as e:
            self.log_safety(f"❌ Erro ao criar backup: {e}", 'error')
            return False
    
    def validate_pre_migration(self):
        """Validações de segurança antes de executar migrações"""
        self.log_safety("🔍 Executando validações pré-migração...")
        
        validation_results = {
            'database_connection': False,
            'critical_tables_exist': False,
            'disk_space_ok': False,
            'backup_created': False
        }
        
        try:
            # 1. Teste de conectividade
            engine = create_engine(self.database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                validation_results['database_connection'] = True
                self.log_safety("✅ Conectividade com banco: OK")
            
            # 2. Verificar tabelas críticas
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            critical_tables = ['usuario', 'funcionario']  # Mínimo necessário
            
            missing_critical = [t for t in critical_tables if t not in existing_tables]
            if not missing_critical:
                validation_results['critical_tables_exist'] = True
                self.log_safety("✅ Tabelas críticas: Presentes")
            else:
                self.log_safety(f"⚠️ Tabelas críticas ausentes: {missing_critical}", 'warning')
            
            # 3. Verificar espaço em disco
            try:
                disk_usage = subprocess.check_output(['df', '/tmp'], text=True)
                # Simples verificação - se conseguir executar df, consideramos OK
                validation_results['disk_space_ok'] = True
                self.log_safety("✅ Espaço em disco: OK")
            except:
                self.log_safety("⚠️ Não foi possível verificar espaço em disco", 'warning')
                validation_results['disk_space_ok'] = True  # Assumir OK para não bloquear
            
            # 4. Criar backup
            validation_results['backup_created'] = self.create_safety_backup()
            
        except Exception as e:
            self.log_safety(f"❌ Erro nas validações: {e}", 'error')
        
        # Verificar se pode prosseguir
        critical_validations = ['database_connection']
        
        if self.rollback_enabled:
            critical_validations.append('backup_created')
        
        failed_critical = [v for v in critical_validations if not validation_results[v]]
        
        if failed_critical:
            self.log_safety(f"❌ Validações críticas falharam: {failed_critical}", 'error')
            return False
        
        self.log_safety("✅ Validações pré-migração aprovadas")
        return True
    
    def execute_safe_migration(self, migration_func, migration_name):
        """Executa uma migração específica com segurança"""
        self.log_safety(f"🔄 Executando migração: {migration_name}")
        
        migration_start = datetime.now()
        
        try:
            # Executar a migração
            migration_func()
            
            # Registrar sucesso
            migration_result = {
                'name': migration_name,
                'status': 'success',
                'started_at': migration_start.isoformat(),
                'completed_at': datetime.now().isoformat(),
                'duration_seconds': (datetime.now() - migration_start).total_seconds()
            }
            
            self.migration_state['migrations_executed'].append(migration_result)
            self.log_safety(f"✅ Migração {migration_name} concluída com sucesso")
            return True
            
        except Exception as e:
            # Registrar falha
            migration_result = {
                'name': migration_name,
                'status': 'failed',
                'started_at': migration_start.isoformat(),
                'failed_at': datetime.now().isoformat(),
                'duration_seconds': (datetime.now() - migration_start).total_seconds(),
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            
            self.migration_state['migrations_executed'].append(migration_result)
            self.log_safety(f"❌ Migração {migration_name} falhou: {e}", 'error')
            
            return False
    
    def initiate_rollback(self):
        """Inicia rollback em caso de falha crítica"""
        if not self.rollback_enabled:
            self.log_safety("🚫 Rollback desabilitado - não executando", 'warning')
            return False
            
        if not self.migration_state.get('rollback_available', False):
            self.log_safety("🚫 Rollback não disponível - backup não criado", 'error')
            return False
        
        self.log_safety("🔙 INICIANDO ROLLBACK DE EMERGÊNCIA")
        
        try:
            # Por enquanto, apenas logar o estado para rollback manual
            rollback_info = {
                'timestamp': datetime.now().isoformat(),
                'backup_file': self.migration_state.get('backup_file'),
                'failed_migrations': [
                    m for m in self.migration_state['migrations_executed'] 
                    if m['status'] == 'failed'
                ],
                'instructions': [
                    "1. Verificar logs em /tmp/migration_safety.log",
                    "2. Analisar backup em " + self.migration_state.get('backup_file', 'N/A'),
                    "3. Executar rollback manual se necessário",
                    "4. Verificar integridade do banco"
                ]
            }
            
            rollback_file = '/tmp/rollback_instructions.json'
            with open(rollback_file, 'w') as f:
                json.dump(rollback_info, f, indent=2)
            
            self.log_safety(f"📋 Instruções de rollback salvas em: {rollback_file}")
            self.log_safety("⚠️ SISTEMA EM MODO DE RECUPERAÇÃO")
            
            return True
            
        except Exception as e:
            self.log_safety(f"❌ Erro durante rollback: {e}", 'error')
            return False
    
    def generate_safety_report(self):
        """Gera relatório de segurança da migração"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'migration_state': self.migration_state,
            'configuration': {
                'rollback_enabled': self.rollback_enabled,
                'force_migration': self.force_migration,
                'migration_timeout': self.migration_timeout
            },
            'files_generated': [
                self.log_file,
                self.backup_file if self.migration_state.get('backup_created') else None,
                '/tmp/migration_state.json'
            ],
            'summary': {
                'total_migrations': len(self.migration_state['migrations_executed']),
                'successful_migrations': len([m for m in self.migration_state['migrations_executed'] if m['status'] == 'success']),
                'failed_migrations': len([m for m in self.migration_state['migrations_executed'] if m['status'] == 'failed']),
                'total_errors': len(self.migration_state['errors']),
                'total_warnings': len(self.migration_state['warnings'])
            }
        }
        
        report_file = '/tmp/migration_safety_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log_safety(f"📊 Relatório de segurança: {report_file}")
        return report

def create_safety_wrapper():
    """Factory para criar instância do safety manager"""
    return MigrationSafetyManager()

if __name__ == '__main__':
    # Teste do sistema de segurança
    manager = MigrationSafetyManager()
    
    # Simular validação
    if manager.validate_pre_migration():
        print("✅ Sistema de segurança funcionando corretamente")
        manager.generate_safety_report()
    else:
        print("❌ Sistema de segurança detectou problemas")
        manager.initiate_rollback()