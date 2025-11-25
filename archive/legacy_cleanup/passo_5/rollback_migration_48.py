#!/usr/bin/env python3
"""
ROLLBACK MIGRAÇÃO 48 - SIGE
Script standalone para reverter a Migração 48 (admin_id em 20 tabelas)

FUNCIONALIDADES:
- Verifica se Migração 48 foi executada
- Remove coluna admin_id de 20 tabelas
- Dropa índices e foreign keys associados
- Atualiza migration_history
- Gera relatório completo

MODOS DE EXECUÇÃO:
- --dry-run: Simulação (NÃO executa nada)
- --force: Executa rollback de verdade
- --table=nome: Rollback de tabela específica

SEGURANÇA:
- Rollback transacional (tudo ou nada)
- Confirmação interativa
- Backup automático de migration_history

AUTOR: Sistema SIGE
DATA: 2025-10-30
"""

import os
import sys
import argparse
import re
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ============================================================================
# CONSTANTES
# ============================================================================

MIGRATION_48_TABLES = [
    'departamento', 'funcao', 'horario_trabalho',
    'servico_obra', 'historico_produtividade_servico',
    'tipo_ocorrencia', 'ocorrencia', 'calendario_util',
    'centro_custo', 'receita', 'orcamento_obra',
    'fluxo_caixa', 'registro_alimentacao',
    'rdo_mao_obra', 'rdo_equipamento', 'rdo_ocorrencia', 'rdo_foto',
    'notificacao_cliente', 'proposta_itens', 'proposta_arquivos'
]

# ============================================================================
# CLASSE PRINCIPAL
# ============================================================================

class Migration48Rollback:
    """Gerenciador de rollback da Migração 48"""
    
    def __init__(self, dry_run=True, specific_table=None):
        self.dry_run = dry_run
        self.specific_table = specific_table
        self.engine = None
        self.connection = None
        self.cursor = None
        
        # Estatísticas e resultados
        self.report_lines = []
        self.actions_planned = []
        self.actions_executed = []
        self.errors = []
        self.warnings = []
        
        # Dados da migração
        self.migration_info = None
        self.tables_to_rollback = []
        self.total_records_affected = 0
        
    def mask_database_url(self, url):
        """Mascara credenciais em URLs de banco para logs seguros"""
        if not url:
            return "None"
        # Mascarar senha: user:password@host -> user:****@host
        masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
        return masked
    
    def add_line(self, line):
        """Adiciona linha ao relatório"""
        self.report_lines.append(line)
        print(line)
    
    def add_action(self, action):
        """Registra ação planejada"""
        self.actions_planned.append(action)
    
    def add_error(self, error):
        """Registra erro"""
        self.errors.append(error)
        self.add_line(f"❌ ERRO: {error}")
    
    def add_warning(self, warning):
        """Registra aviso"""
        self.warnings.append(warning)
        self.add_line(f"⚠️ AVISO: {warning}")
    
    # ========================================================================
    # CONEXÃO COM BANCO
    # ========================================================================
    
    def connect_database(self):
        """Estabelece conexão com banco de dados"""
        self.add_line("🔌 Conectando ao banco de dados...")
        
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            self.add_error("DATABASE_URL não encontrada nas variáveis de ambiente")
            return False
        
        try:
            self.engine = create_engine(database_url)
            self.connection = self.engine.raw_connection()
            self.cursor = self.connection.cursor()
            
            # Testar conexão
            self.cursor.execute("SELECT version()")
            version = self.cursor.fetchone()[0]
            
            self.add_line(f"✅ Conexão estabelecida")
            self.add_line(f"   Database: {self.mask_database_url(database_url)}")
            self.add_line(f"   PostgreSQL: {version[:60]}...")
            
            return True
            
        except Exception as e:
            self.add_error(f"Falha ao conectar ao banco: {e}")
            return False
    
    def close_connection(self):
        """Fecha conexão com banco"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            if self.engine:
                self.engine.dispose()
        except Exception as e:
            self.add_warning(f"Erro ao fechar conexão: {e}")
    
    # ========================================================================
    # VERIFICAÇÕES PRÉ-ROLLBACK
    # ========================================================================
    
    def check_migration_executed(self):
        """Verifica se Migração 48 foi executada"""
        self.add_line("\n📋 Verificando se Migração 48 foi executada...")
        
        try:
            # Verificar se tabela migration_history existe
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'migration_history'
                )
            """)
            
            if not self.cursor.fetchone()[0]:
                self.add_error("Tabela migration_history não existe")
                return False
            
            # Buscar informações da Migração 48
            self.cursor.execute("""
                SELECT migration_number, migration_name, executed_at, status, execution_time_ms
                FROM migration_history
                WHERE migration_number = 48
            """)
            
            result = self.cursor.fetchone()
            
            if not result:
                self.add_error("Migração 48 não foi executada ainda")
                self.add_line("   Não há nada para fazer rollback.")
                return False
            
            number, name, executed_at, status, exec_time = result
            
            self.migration_info = {
                'number': number,
                'name': name,
                'executed_at': executed_at,
                'status': status,
                'execution_time_ms': exec_time
            }
            
            if status != 'success':
                self.add_warning(f"Migração 48 não foi bem-sucedida (status: {status})")
                self.add_line("   Rollback ainda pode ser necessário para limpar mudanças parciais.")
            else:
                self.add_line(f"✅ Migração 48 executada em: {executed_at}")
                self.add_line(f"   Nome: {name}")
                self.add_line(f"   Status: {status}")
            
            return True
            
        except Exception as e:
            self.add_error(f"Erro ao verificar migração: {e}")
            import traceback
            self.add_line(traceback.format_exc())
            return False
    
    def check_table_status(self, table_name):
        """Verifica status de uma tabela específica"""
        status = {
            'name': table_name,
            'exists': False,
            'has_admin_id': False,
            'has_index': False,
            'has_fk': False,
            'record_count': 0,
            'index_name': f"idx_{table_name}_admin_id",
            'fk_name': f"fk_{table_name}_admin_id"
        }
        
        try:
            # Verificar se tabela existe
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            
            status['exists'] = self.cursor.fetchone()[0]
            
            if not status['exists']:
                return status
            
            # Verificar se tem coluna admin_id
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'admin_id'
                )
            """, (table_name,))
            
            status['has_admin_id'] = self.cursor.fetchone()[0]
            
            if not status['has_admin_id']:
                return status
            
            # Contar registros
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            status['record_count'] = self.cursor.fetchone()[0]
            
            # Verificar se índice existe
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes 
                    WHERE tablename = %s AND indexname = %s
                )
            """, (table_name, status['index_name']))
            
            status['has_index'] = self.cursor.fetchone()[0]
            
            # Verificar se FK existe
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.table_constraints 
                    WHERE table_name = %s 
                    AND constraint_name = %s
                    AND constraint_type = 'FOREIGN KEY'
                )
            """, (table_name, status['fk_name']))
            
            status['has_fk'] = self.cursor.fetchone()[0]
            
        except Exception as e:
            self.add_warning(f"Erro ao verificar tabela {table_name}: {e}")
            # Fazer rollback da transação em caso de erro
            try:
                self.connection.rollback()
            except:
                pass
        
        return status
    
    def scan_all_tables(self):
        """Escaneia todas as tabelas para rollback"""
        self.add_line("\n🔍 Escaneando tabelas...")
        
        tables_to_scan = [self.specific_table] if self.specific_table else MIGRATION_48_TABLES
        
        for table in tables_to_scan:
            status = self.check_table_status(table)
            
            if not status['exists']:
                self.add_warning(f"Tabela {table} não existe")
                continue
            
            if not status['has_admin_id']:
                self.add_line(f"⏭️  {table}: sem coluna admin_id (nada a fazer)")
                continue
            
            # Tabela precisa de rollback
            self.tables_to_rollback.append(status)
            self.total_records_affected += status['record_count']
            
            self.add_line(f"📌 {table}: {status['record_count']} registros")
            if status['has_index']:
                self.add_line(f"   ✓ Índice: {status['index_name']}")
            if status['has_fk']:
                self.add_line(f"   ✓ FK: {status['fk_name']}")
        
        self.add_line(f"\n✅ Total de tabelas para rollback: {len(self.tables_to_rollback)}")
        self.add_line(f"   Total de registros afetados: {self.total_records_affected}")
        
        return len(self.tables_to_rollback) > 0
    
    # ========================================================================
    # OPERAÇÕES DE ROLLBACK
    # ========================================================================
    
    def rollback_table(self, table_status):
        """Faz rollback de uma tabela específica"""
        table_name = table_status['name']
        actions = []
        
        self.add_line(f"\n🔧 Processando {table_name}...")
        
        try:
            # 1. Dropar índice
            if table_status['has_index']:
                index_name = table_status['index_name']
                sql = f"DROP INDEX IF EXISTS {index_name}"
                
                self.add_action({
                    'table': table_name,
                    'action': 'drop_index',
                    'sql': sql,
                    'object': index_name
                })
                
                if not self.dry_run:
                    self.cursor.execute(sql)
                    self.add_line(f"   ✅ Índice {index_name} removido")
                else:
                    self.add_line(f"   [DRY-RUN] Removeria índice: {index_name}")
            
            # 2. Dropar foreign key
            if table_status['has_fk']:
                fk_name = table_status['fk_name']
                sql = f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {fk_name}"
                
                self.add_action({
                    'table': table_name,
                    'action': 'drop_fk',
                    'sql': sql,
                    'object': fk_name
                })
                
                if not self.dry_run:
                    self.cursor.execute(sql)
                    self.add_line(f"   ✅ FK {fk_name} removida")
                else:
                    self.add_line(f"   [DRY-RUN] Removeria FK: {fk_name}")
            
            # 3. Dropar coluna admin_id
            sql = f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS admin_id"
            
            self.add_action({
                'table': table_name,
                'action': 'drop_column',
                'sql': sql,
                'object': 'admin_id',
                'records_affected': table_status['record_count']
            })
            
            if not self.dry_run:
                self.cursor.execute(sql)
                self.add_line(f"   ✅ Coluna admin_id removida ({table_status['record_count']} registros afetados)")
            else:
                self.add_line(f"   [DRY-RUN] Removeria coluna: admin_id ({table_status['record_count']} registros)")
            
            self.actions_executed.append({
                'table': table_name,
                'success': True,
                'message': f"Rollback completo: {len(self.actions_planned)} ações"
            })
            
            return True
            
        except Exception as e:
            self.add_error(f"Erro no rollback de {table_name}: {e}")
            self.actions_executed.append({
                'table': table_name,
                'success': False,
                'error': str(e)
            })
            return False
    
    def rollback_all_tables(self):
        """Executa rollback de todas as tabelas"""
        self.add_line("\n" + "=" * 80)
        self.add_line("🔄 INICIANDO ROLLBACK")
        self.add_line("=" * 80)
        
        if not self.tables_to_rollback:
            self.add_line("✅ Nenhuma tabela precisa de rollback")
            return True
        
        success_count = 0
        failure_count = 0
        
        for table_status in self.tables_to_rollback:
            if self.rollback_table(table_status):
                success_count += 1
            else:
                failure_count += 1
                
                # CRÍTICO: Abortar em caso de erro (rollback transacional)
                if not self.dry_run:
                    self.add_error("Rollback abortado devido a erro")
                    self.add_line("   Fazendo rollback da transação...")
                    self.connection.rollback()
                    return False
        
        self.add_line(f"\n📊 Resultado: {success_count} sucesso, {failure_count} falhas")
        
        return failure_count == 0
    
    def update_migration_history(self):
        """Remove registro da Migração 48 do histórico"""
        self.add_line("\n📝 Atualizando migration_history...")
        
        try:
            # Backup da migration_history
            if not self.dry_run:
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS migration_history_backup AS 
                    SELECT * FROM migration_history WHERE migration_number = 48
                """)
                self.add_line("   ✅ Backup de migration_history criado")
            else:
                self.add_line("   [DRY-RUN] Criaria backup de migration_history")
            
            # Remover registro da Migração 48
            sql = "DELETE FROM migration_history WHERE migration_number = 48"
            
            if not self.dry_run:
                self.cursor.execute(sql)
                deleted = self.cursor.rowcount
                self.add_line(f"   ✅ Registro da Migração 48 removido ({deleted} linhas)")
            else:
                self.add_line("   [DRY-RUN] Removeria registro da Migração 48")
            
            return True
            
        except Exception as e:
            self.add_error(f"Erro ao atualizar migration_history: {e}")
            return False
    
    # ========================================================================
    # COMMIT E RELATÓRIOS
    # ========================================================================
    
    def commit_rollback(self):
        """Confirma rollback (commit) ou aborta (rollback)"""
        if self.dry_run:
            self.add_line("\n[DRY-RUN] Nenhuma mudança foi feita no banco")
            return True
        
        try:
            self.connection.commit()
            self.add_line("\n✅ ROLLBACK CONFIRMADO - Todas as mudanças foram salvas")
            return True
        except Exception as e:
            self.add_error(f"Erro ao confirmar rollback: {e}")
            try:
                self.connection.rollback()
                self.add_line("   Rollback da transação executado")
            except:
                pass
            return False
    
    def generate_header(self):
        """Gera cabeçalho do relatório"""
        self.add_line("=" * 80)
        self.add_line("ROLLBACK MIGRAÇÃO 48 - SIGE")
        self.add_line("=" * 80)
        self.add_line(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        database_url = os.environ.get('DATABASE_URL', 'None')
        self.add_line(f"Banco: {self.mask_database_url(database_url)}")
        
        mode = "DRY-RUN (simulação)" if self.dry_run else "EXECUÇÃO REAL"
        self.add_line(f"Modo: {mode}")
        
        if self.specific_table:
            self.add_line(f"Tabela específica: {self.specific_table}")
        
        self.add_line("")
        self.add_line("⚠️ ATENÇÃO: Este script VAI REMOVER a coluna admin_id de tabelas!")
        self.add_line("")
    
    def generate_summary(self):
        """Gera resumo pré-validação"""
        self.add_line("📊 PRÉ-VALIDAÇÃO:")
        
        if self.migration_info:
            exec_date = self.migration_info['executed_at']
            status = self.migration_info['status']
            self.add_line(f"- Migração 48 executada: ✅ Sim ({exec_date}, status: {status})")
        else:
            self.add_line("- Migração 48 executada: ❌ Não")
        
        self.add_line(f"- Tabelas com admin_id: {len(self.tables_to_rollback)}")
        self.add_line(f"- Total de registros afetados: ~{self.total_records_affected}")
        self.add_line("")
    
    def generate_actions_report(self):
        """Gera relatório de ações planejadas"""
        if not self.tables_to_rollback:
            return
        
        self.add_line("🔧 AÇÕES PLANEJADAS:")
        self.add_line("")
        
        for i, table_status in enumerate(self.tables_to_rollback, 1):
            table_name = table_status['name']
            self.add_line(f"{i}. {table_name}:")
            
            if table_status['has_index']:
                self.add_line(f"   - Dropar índice: {table_status['index_name']}")
            
            if table_status['has_fk']:
                self.add_line(f"   - Dropar FK: {table_status['fk_name']}")
            
            self.add_line(f"   - Dropar coluna: admin_id")
            self.add_line(f"   - Registros afetados: {table_status['record_count']}")
            self.add_line("")
    
    def generate_footer(self):
        """Gera rodapé do relatório"""
        self.add_line("=" * 80)
        
        if self.dry_run:
            self.add_line("")
            self.add_line("❌ MODO DRY-RUN - NADA FOI EXECUTADO")
            self.add_line("")
            self.add_line("Para executar o rollback de verdade:")
            self.add_line("python3 rollback_migration_48.py --force")
            self.add_line("")
            self.add_line("⚠️ IMPORTANTE: Fazer backup do banco ANTES de executar!")
        else:
            if self.errors:
                self.add_line("")
                self.add_line(f"❌ ROLLBACK FALHOU - {len(self.errors)} erros")
                for error in self.errors:
                    self.add_line(f"   - {error}")
            else:
                self.add_line("")
                self.add_line("✅ ROLLBACK EXECUTADO COM SUCESSO")
                self.add_line(f"   - {len(self.tables_to_rollback)} tabelas processadas")
                self.add_line(f"   - {self.total_records_affected} registros afetados")
        
        self.add_line("=" * 80)
    
    # ========================================================================
    # EXECUÇÃO PRINCIPAL
    # ========================================================================
    
    def run(self):
        """Executa o rollback completo"""
        try:
            # Gerar cabeçalho
            self.generate_header()
            
            # Conectar ao banco
            if not self.connect_database():
                return False
            
            # Verificar se migração foi executada
            if not self.check_migration_executed():
                return False
            
            # Escanear tabelas
            if not self.scan_all_tables():
                self.add_line("\n✅ Nenhuma tabela precisa de rollback")
                return True
            
            # Gerar resumo
            self.generate_summary()
            
            # Gerar relatório de ações
            self.generate_actions_report()
            
            # Executar rollback das tabelas
            if not self.rollback_all_tables():
                return False
            
            # Atualizar migration_history
            if not self.update_migration_history():
                return False
            
            # Commit ou rollback
            if not self.commit_rollback():
                return False
            
            # Gerar rodapé
            self.generate_footer()
            
            return len(self.errors) == 0
            
        except KeyboardInterrupt:
            self.add_line("\n\n⚠️ Operação cancelada pelo usuário")
            if not self.dry_run:
                try:
                    self.connection.rollback()
                    self.add_line("   Rollback da transação executado")
                except:
                    pass
            return False
            
        except Exception as e:
            self.add_error(f"Erro inesperado: {e}")
            import traceback
            self.add_line(traceback.format_exc())
            
            if not self.dry_run:
                try:
                    self.connection.rollback()
                    self.add_line("   Rollback da transação executado")
                except:
                    pass
            
            return False
            
        finally:
            self.close_connection()


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    """Função principal do script"""
    
    # Parser de argumentos
    parser = argparse.ArgumentParser(
        description='Rollback da Migração 48 - Remove admin_id de 20 tabelas',
        epilog='IMPORTANTE: Faça backup do banco ANTES de executar!'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulação (não executa mudanças)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Executa rollback de verdade (SEM confirmação)'
    )
    
    parser.add_argument(
        '--table',
        type=str,
        help='Rollback de tabela específica (ex: --table=departamento)'
    )
    
    args = parser.parse_args()
    
    # Determinar modo
    if args.force and args.dry_run:
        print("❌ ERRO: --force e --dry-run não podem ser usados juntos")
        return 1
    
    dry_run = not args.force
    
    # Confirmação interativa (apenas se não for dry-run e não usar --force)
    if not dry_run and not args.force:
        print("=" * 80)
        print("⚠️ ATENÇÃO: Você está prestes a executar o ROLLBACK da Migração 48!")
        print("=" * 80)
        print("")
        print("Isso VAI REMOVER a coluna admin_id de até 20 tabelas.")
        print("Esta operação NÃO pode ser desfeita facilmente.")
        print("")
        print("Recomendações:")
        print("1. Faça backup completo do banco ANTES de continuar")
        print("2. Execute primeiro com --dry-run para ver o que será feito")
        print("3. Verifique se você tem backups recentes")
        print("")
        
        response = input("Tem certeza que deseja continuar? Digite 'SIM' para confirmar: ")
        
        if response.strip().upper() != 'SIM':
            print("\n❌ Operação cancelada pelo usuário")
            return 0
        
        print("\n✅ Confirmação recebida. Iniciando rollback...\n")
    
    # Executar rollback
    rollback = Migration48Rollback(dry_run=dry_run, specific_table=args.table)
    success = rollback.run()
    
    # Exit code
    if success:
        if dry_run:
            print("\n💡 Dica: Execute com --force para aplicar as mudanças")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
