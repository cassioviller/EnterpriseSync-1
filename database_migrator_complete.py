#!/usr/bin/env python3
"""
🚀 SISTEMA DE MIGRAÇÕES ROBUSTO E COMPLETO - SIGE v10.0
======================================================
Sistema inteligente de migrações com detecção automática de estrutura,
tratamento seguro de erros e logging detalhado.

Autor: Sistema SIGE v10.0
Data: 2025-01-19
Versão: 1.0.0 - Primeira implementação completa
"""

import os
import sys
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import create_engine, text, inspect, MetaData, Table, Column
from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool


class CompleteDatabaseMigrator:
    """
    Migrador de banco de dados completo com detecção automática de estrutura
    e sistema avançado de logging e tratamento de erros.
    """
    
    def __init__(self, database_url: str, log_file: str = "/tmp/database_migrator.log"):
        """
        Inicializa o migrador com configurações de banco e logging.
        
        Args:
            database_url: URL de conexão com o banco de dados
            log_file: Caminho para o arquivo de log
        """
        self.database_url = database_url
        self.log_file = log_file
        self.engine: Optional[Engine] = None
        self.inspector = None
        self.metadata = MetaData()
        
        # Configurar sistema de logging duplo (console + arquivo)
        self._setup_logging()
        
        # Estatísticas da migração
        self.migration_stats = {
            'tables_analyzed': 0,
            'columns_added': 0,
            'columns_skipped': 0,
            'admin_ids_fixed': 0,
            'errors_handled': 0,
            'warnings_logged': 0
        }
        
        # Definições das estruturas das tabelas conforme especificação
        self.table_structures = self._define_table_structures()
        
        self.logger.info("🚀 CompleteDatabaseMigrator inicializado")
        self.logger.info(f"📁 Log file: {log_file}")
        self.logger.info(f"🔗 Database: {self._mask_database_url(database_url)}")
        
    def _setup_logging(self):
        """Configura sistema de logging duplo (console + arquivo)"""
        # Configurar formatador
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configurar logger principal
        self.logger = logging.getLogger('DatabaseMigrator')
        self.logger.setLevel(logging.DEBUG)
        
        # Limpar handlers existentes
        self.logger.handlers.clear()
        
        # Handler para console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Handler para arquivo
        try:
            # Criar diretório se não existir
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            
            file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            self.logger.info(f"📝 Sistema de logging configurado: Console + {self.log_file}")
        except Exception as e:
            self.logger.warning(f"⚠️ Não foi possível configurar log em arquivo: {e}")
    
    def _mask_database_url(self, url: str) -> str:
        """Mascara credenciais na URL do banco para logs seguros"""
        if not url:
            return "None"
        # Mascarar senha: user:password@host -> user:****@host
        masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
        return masked
    
    def _define_table_structures(self) -> Dict[str, Dict[str, str]]:
        """
        Define as estruturas das tabelas conforme especificação.
        Retorna apenas as colunas que DEVEM existir, não necessariamente todas.
        """
        return {
            'veiculo': {
                # Colunas básicas obrigatórias
                'id': 'INTEGER PRIMARY KEY',
                'placa': 'VARCHAR(10) NOT NULL',
                'marca_modelo': 'VARCHAR(100)',  # Esta pode precisar ser criada
                'ano': 'INTEGER',
                'cor': 'VARCHAR(30)',  # Esta provavelmente precisa ser criada
                'km_atual': 'INTEGER DEFAULT 0',
                'status': 'VARCHAR(20) DEFAULT \'Disponível\'',
                'observacoes': 'TEXT',  # Esta provavelmente precisa ser criada
                # Multi-tenant
                'admin_id': 'INTEGER REFERENCES usuario(id)',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            },
            'uso_veiculo': {
                # Colunas básicas
                'id': 'INTEGER PRIMARY KEY',
                'veiculo_id': 'INTEGER REFERENCES veiculo(id)',
                'funcionario_id': 'INTEGER REFERENCES funcionario(id)',
                'obra_id': 'INTEGER REFERENCES obra(id)',
                'data_uso': 'DATE NOT NULL',
                'km_inicial': 'INTEGER',
                'km_final': 'INTEGER',
                'horario_saida': 'TIME',
                'horario_chegada': 'TIME',
                'finalidade': 'VARCHAR(200)',
                'observacoes': 'TEXT',
                # Colunas avançadas
                'porcentagem_combustivel': 'INTEGER',
                'km_percorrido': 'INTEGER DEFAULT 0',
                'horas_uso': 'FLOAT DEFAULT 0.0',
                'custo_estimado': 'FLOAT DEFAULT 0.0',
                'aprovado': 'BOOLEAN DEFAULT FALSE',
                'aprovado_por_id': 'INTEGER REFERENCES usuario(id)',
                'data_aprovacao': 'TIMESTAMP',
                # Multi-tenant
                'admin_id': 'INTEGER REFERENCES usuario(id)',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            },
            'custo_veiculo': {
                # Colunas básicas
                'id': 'INTEGER PRIMARY KEY',
                'veiculo_id': 'INTEGER REFERENCES veiculo(id)',
                'data_custo': 'DATE NOT NULL',
                'tipo_custo': 'VARCHAR(50) NOT NULL',
                'valor': 'FLOAT NOT NULL',
                'descricao': 'TEXT',
                # Colunas específicas
                'litros_combustivel': 'FLOAT',
                'preco_por_litro': 'FLOAT',
                'km_atual': 'INTEGER',
                # Multi-tenant
                'admin_id': 'INTEGER REFERENCES usuario(id)',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
        }
    
    def connect_to_database(self) -> bool:
        """
        Estabelece conexão com o banco de dados com configurações otimizadas.
        
        Returns:
            bool: True se conexão foi bem-sucedida
        """
        try:
            # Configurações da engine para máxima estabilidade
            self.engine = create_engine(
                self.database_url,
                poolclass=NullPool,  # Evitar problemas de pool em migrações
                isolation_level="AUTOCOMMIT",  # Para DDL statements
                echo=False,  # Não logar SQL para manter logs limpos
                future=True
            )
            
            # Testar conexão
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            
            # Configurar inspector para análise de estrutura
            self.inspector = inspect(self.engine)
            
            self.logger.info("✅ Conexão com banco de dados estabelecida")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao conectar com banco: {e}")
            return False
    
    def analyze_table_structure(self, table_name: str) -> Dict[str, Any]:
        """
        Analisa a estrutura atual de uma tabela.
        
        Args:
            table_name: Nome da tabela a ser analisada
            
        Returns:
            Dict com informações da estrutura
        """
        try:
            if not self.inspector or not self.inspector.has_table(table_name):
                return {
                    'exists': False,
                    'columns': [],
                    'column_names': [],
                    'needs_creation': True
                }
            
            if not self.inspector:
                return {
                    'exists': False,
                    'columns': [],
                    'column_names': [],
                    'error': 'Inspector não inicializado'
                }
            
            columns = self.inspector.get_columns(table_name)
            column_names = [col['name'].lower() for col in columns]
            
            self.logger.debug(f"📊 Tabela {table_name}: {len(columns)} colunas encontradas")
            
            return {
                'exists': True,
                'columns': columns,
                'column_names': column_names,
                'needs_creation': False
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao analisar tabela {table_name}: {e}")
            return {
                'exists': False,
                'columns': [],
                'column_names': [],
                'error': str(e)
            }
    
    def check_column_exists(self, table_name: str, column_name: str) -> bool:
        """
        Verifica se uma coluna específica existe na tabela.
        
        Args:
            table_name: Nome da tabela
            column_name: Nome da coluna
            
        Returns:
            bool: True se a coluna existir
        """
        try:
            structure = self.analyze_table_structure(table_name)
            return column_name.lower() in structure['column_names']
        except Exception as e:
            self.logger.error(f"❌ Erro ao verificar coluna {column_name} em {table_name}: {e}")
            return False
    
    def execute_migration_sql(self, sql: str, description: str) -> bool:
        """
        Executa comando SQL de migração com tratamento robusto de erros.
        
        Args:
            sql: Comando SQL a ser executado
            description: Descrição da operação
            
        Returns:
            bool: True se execução foi bem-sucedida
        """
        try:
            if not self.engine:
                self.logger.error(f"❌ {description} - Engine não inicializada")
                return False
                
            with self.engine.connect() as conn:
                # Executar em transação para DDL seguro
                trans = conn.begin()
                try:
                    conn.execute(text(sql))
                    trans.commit()
                    self.logger.info(f"✅ {description}")
                    return True
                except Exception as e:
                    trans.rollback()
                    raise e
                    
        except (OperationalError, ProgrammingError) as e:
            error_msg = str(e).lower()
            
            # Verificar se é erro de coluna/tabela já existente (não é erro real)
            if any(keyword in error_msg for keyword in [
                'already exists', 'duplicate column', 'column already exists',
                'relation already exists', 'duplicate key'
            ]):
                self.logger.info(f"⚠️ {description} - Já existe")
                self.migration_stats['columns_skipped'] += 1
                return True
            else:
                self.logger.error(f"❌ {description} - ERRO SQL: {e}")
                self.migration_stats['errors_handled'] += 1
                return False
                
        except Exception as e:
            self.logger.error(f"❌ {description} - ERRO INESPERADO: {e}")
            self.migration_stats['errors_handled'] += 1
            return False
    
    def migrate_veiculo_complete(self) -> bool:
        """
        Migração completa da tabela veiculo com detecção inteligente.
        """
        self.logger.info("🔄 Iniciando migração completa da tabela veiculo...")
        
        # Analisar estrutura atual
        structure = self.analyze_table_structure('veiculo')
        self.migration_stats['tables_analyzed'] += 1
        
        if not structure['exists']:
            self.logger.warning("⚠️ Tabela veiculo não existe - será criada")
            # TODO: Implementar criação de tabela completa se necessário
            return False
        
        success_count = 0
        total_operations = 0
        
        # Lista de colunas que precisam ser adicionadas (baseado na análise)
        missing_columns = [
            {
                'name': 'cor',
                'sql': 'ALTER TABLE veiculo ADD COLUMN cor VARCHAR(30);',
                'description': 'Adicionar coluna cor'
            },
            {
                'name': 'observacoes',
                'sql': 'ALTER TABLE veiculo ADD COLUMN observacoes TEXT;',
                'description': 'Adicionar coluna observacoes'
            },
            {
                'name': 'marca_modelo',
                'sql': 'ALTER TABLE veiculo ADD COLUMN marca_modelo VARCHAR(100);',
                'description': 'Adicionar coluna marca_modelo unificada'
            }
        ]
        
        # Verificar e adicionar colunas faltantes
        for column in missing_columns:
            total_operations += 1
            if not self.check_column_exists('veiculo', column['name']):
                self.logger.info(f"🔄 Coluna {column['name']} não existe, adicionando...")
                if self.execute_migration_sql(column['sql'], column['description']):
                    success_count += 1
                    self.migration_stats['columns_added'] += 1
            else:
                self.logger.info(f"✅ Coluna {column['name']} já existe")
                success_count += 1
                self.migration_stats['columns_skipped'] += 1
        
        # Atualizar marca_modelo baseado em marca + modelo se necessário
        if self.check_column_exists('veiculo', 'marca_modelo') and \
           self.check_column_exists('veiculo', 'marca') and \
           self.check_column_exists('veiculo', 'modelo'):
            
            update_sql = """
            UPDATE veiculo 
            SET marca_modelo = CONCAT(COALESCE(marca, ''), ' ', COALESCE(modelo, ''))
            WHERE marca_modelo IS NULL OR marca_modelo = '';
            """
            
            if self.execute_migration_sql(update_sql, "Atualizar marca_modelo com dados existentes"):
                self.logger.info("✅ Campo marca_modelo atualizado com dados de marca + modelo")
        
        self.logger.info(f"📊 Migração veiculo: {success_count}/{total_operations} operações OK")
        return success_count == total_operations
    
    def migrate_uso_veiculo_complete(self) -> bool:
        """
        Migração completa da tabela uso_veiculo (análise indica que já está completa).
        """
        self.logger.info("🔄 Verificando migração da tabela uso_veiculo...")
        
        # Analisar estrutura atual
        structure = self.analyze_table_structure('uso_veiculo')
        self.migration_stats['tables_analyzed'] += 1
        
        if not structure['exists']:
            self.logger.error("❌ Tabela uso_veiculo não existe!")
            return False
        
        # Verificar colunas críticas (a tabela já tem 25 colunas, mais que as 21 especificadas)
        critical_columns = [
            'id', 'veiculo_id', 'funcionario_id', 'data_uso', 'admin_id',
            'km_inicial', 'km_final', 'horario_saida', 'horario_chegada',
            'porcentagem_combustivel', 'km_percorrido', 'horas_uso', 'custo_estimado'
        ]
        
        missing_critical = []
        for col in critical_columns:
            if not self.check_column_exists('uso_veiculo', col):
                missing_critical.append(col)
        
        if missing_critical:
            self.logger.warning(f"⚠️ Colunas críticas faltantes em uso_veiculo: {missing_critical}")
            # Adicionar colunas faltantes se necessário
            for col in missing_critical:
                sql = f"ALTER TABLE uso_veiculo ADD COLUMN {col} VARCHAR(255);"
                self.execute_migration_sql(sql, f"Adicionar coluna crítica {col}")
        else:
            self.logger.info("✅ Tabela uso_veiculo possui todas as colunas necessárias")
        
        return len(missing_critical) == 0
    
    def migrate_custo_veiculo_complete(self) -> bool:
        """
        Migração completa da tabela custo_veiculo (análise indica que já está completa).
        """
        self.logger.info("🔄 Verificando migração da tabela custo_veiculo...")
        
        # Analisar estrutura atual
        structure = self.analyze_table_structure('custo_veiculo')
        self.migration_stats['tables_analyzed'] += 1
        
        if not structure['exists']:
            self.logger.error("❌ Tabela custo_veiculo não existe!")
            return False
        
        # Verificar colunas críticas (a tabela já tem 27 colunas, mais que as 12 especificadas)
        critical_columns = [
            'id', 'veiculo_id', 'data_custo', 'tipo_custo', 'valor', 'descricao',
            'litros_combustivel', 'preco_por_litro', 'km_atual',
            'admin_id', 'created_at', 'updated_at'
        ]
        
        missing_critical = []
        for col in critical_columns:
            if not self.check_column_exists('custo_veiculo', col):
                missing_critical.append(col)
        
        if missing_critical:
            self.logger.warning(f"⚠️ Colunas críticas faltantes em custo_veiculo: {missing_critical}")
            # Adicionar colunas faltantes se necessário
            for col in missing_critical:
                sql = f"ALTER TABLE custo_veiculo ADD COLUMN {col} VARCHAR(255);"
                self.execute_migration_sql(sql, f"Adicionar coluna crítica {col}")
        else:
            self.logger.info("✅ Tabela custo_veiculo possui todas as colunas necessárias")
        
        return len(missing_critical) == 0
    
    def fix_null_admin_ids(self) -> bool:
        """
        Corrige admin_id NULL nas tabelas de veículos.
        """
        self.logger.info("🔧 Iniciando correção de admin_id NULL...")
        
        tables_to_fix = ['veiculo', 'uso_veiculo', 'custo_veiculo']
        total_fixed = 0
        
        for table in tables_to_fix:
            try:
                # Verificar se tabela existe e tem admin_id
                if not self.check_column_exists(table, 'admin_id'):
                    continue
                
                # Buscar o primeiro admin disponível
                find_admin_sql = """
                SELECT id FROM usuario 
                WHERE tipo_usuario IN ('admin', 'super_admin') 
                ORDER BY id LIMIT 1;
                """
                
                if not self.engine:
                    self.logger.warning(f"⚠️ Engine não inicializada para corrigir {table}")
                    continue
                    
                with self.engine.connect() as conn:
                    result = conn.execute(text(find_admin_sql))
                    admin_row = result.fetchone()
                    
                    if not admin_row:
                        self.logger.warning(f"⚠️ Nenhum admin encontrado para corrigir {table}")
                        continue
                    
                    admin_id = admin_row[0]
                    
                    # Corrigir admin_id NULL
                    fix_sql = f"""
                    UPDATE {table} 
                    SET admin_id = {admin_id} 
                    WHERE admin_id IS NULL;
                    """
                    
                    result = conn.execute(text(fix_sql))
                    fixed_count = result.rowcount
                    
                    if fixed_count > 0:
                        conn.commit()
                        self.logger.info(f"✅ Corrigidos {fixed_count} registros em {table}")
                        total_fixed += fixed_count
                        self.migration_stats['admin_ids_fixed'] += fixed_count
                    else:
                        self.logger.info(f"✅ Tabela {table} já possui admin_id correto")
            
            except Exception as e:
                self.logger.error(f"❌ Erro ao corrigir admin_id em {table}: {e}")
                continue
        
        self.logger.info(f"📊 Total de admin_ids corrigidos: {total_fixed}")
        return True
    
    def generate_migration_report(self) -> str:
        """
        Gera relatório completo da migração executada.
        
        Returns:
            str: Relatório formatado
        """
        report = f"""
        
🏁 RELATÓRIO FINAL DE MIGRAÇÃO - SIGE v10.0
{'='*60}
📅 Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🗄️ Banco: {self._mask_database_url(self.database_url)}
📁 Log File: {self.log_file}

📊 ESTATÍSTICAS GERAIS:
├── Tabelas analisadas: {self.migration_stats['tables_analyzed']}
├── Colunas adicionadas: {self.migration_stats['columns_added']}
├── Colunas já existentes: {self.migration_stats['columns_skipped']}
├── Admin IDs corrigidos: {self.migration_stats['admin_ids_fixed']}
├── Erros tratados: {self.migration_stats['errors_handled']}
└── Avisos registrados: {self.migration_stats['warnings_logged']}

🎯 STATUS DA MIGRAÇÃO:
"""
        
        # Verificar status de cada tabela
        for table_name in ['veiculo', 'uso_veiculo', 'custo_veiculo']:
            structure = self.analyze_table_structure(table_name)
            if structure['exists']:
                column_count = len(structure['columns'])
                report += f"├── {table_name}: ✅ OK ({column_count} colunas)\n"
            else:
                report += f"├── {table_name}: ❌ AUSENTE\n"
        
        # Adicionar recomendações
        report += f"""
🔍 RECOMENDAÇÕES:
├── Verificar logs detalhados em: {self.log_file}
├── Executar testes funcionais nas tabelas migradas
├── Monitorar performance das consultas
└── Fazer backup antes de futuras migrações

💡 PRÓXIMOS PASSOS:
├── Executar verify_migrations.py para validação completa
├── Testar funcionalidades de veículos na aplicação
└── Documentar mudanças realizadas

{'='*60}
"""
        return report
    
    def run_complete_migration(self) -> bool:
        """
        Executa o processo completo de migração.
        
        Returns:
            bool: True se todas as migrações foram bem-sucedidas
        """
        start_time = datetime.now()
        self.logger.info("🚀 INICIANDO MIGRAÇÃO COMPLETA DO SISTEMA DE VEÍCULOS")
        self.logger.info("=" * 60)
        
        try:
            # 1. Conectar ao banco
            if not self.connect_to_database():
                return False
            
            # 2. Executar migrações específicas por tabela
            results = []
            
            self.logger.info("📋 Executando migrações das tabelas...")
            results.append(self.migrate_veiculo_complete())
            results.append(self.migrate_uso_veiculo_complete())
            results.append(self.migrate_custo_veiculo_complete())
            
            # 3. Corrigir admin_ids NULL
            self.logger.info("🔧 Corrigindo admin_ids NULL...")
            self.fix_null_admin_ids()
            
            # 4. Verificar resultado geral
            all_successful = all(results)
            duration = datetime.now() - start_time
            
            if all_successful:
                self.logger.info("🎉 TODAS AS MIGRAÇÕES EXECUTADAS COM SUCESSO!")
                self.logger.info(f"⏱️ Tempo total: {duration.total_seconds():.2f} segundos")
            else:
                self.logger.error("❌ ALGUMAS MIGRAÇÕES FALHARAM - Verificar logs")
                self.migration_stats['errors_handled'] += 1
            
            # 5. Gerar e exibir relatório final
            report = self.generate_migration_report()
            self.logger.info(report)
            
            return all_successful
            
        except Exception as e:
            self.logger.error(f"❌ ERRO CRÍTICO na migração: {e}")
            return False
        
        finally:
            # Fechar conexões
            if self.engine:
                self.engine.dispose()
                self.logger.info("🔌 Conexões com banco encerradas")


def main():
    """
    Função principal para execução do migrador completo.
    """
    print("🚀 SIGE v10.0 - Sistema de Migrações Robusto e Completo")
    print("=" * 60)
    
    # Obter URL do banco
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ Erro: DATABASE_URL não encontrada")
        sys.exit(1)
    
    # Configurar caminho do log
    log_file = "/tmp/database_migrator.log"
    
    # Inicializar e executar migrador
    migrator = CompleteDatabaseMigrator(database_url, log_file)
    
    try:
        success = migrator.run_complete_migration()
        
        if success:
            print("\n🎉 Migração concluída com SUCESSO!")
            print(f"📁 Logs detalhados: {log_file}")
            sys.exit(0)
        else:
            print("\n❌ Migração concluída com ERROS!")
            print(f"📁 Verificar logs: {log_file}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Migração interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Erro crítico: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()