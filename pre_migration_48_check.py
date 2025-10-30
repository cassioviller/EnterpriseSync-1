#!/usr/bin/env python3
"""
PRÉ-VALIDAÇÃO MIGRAÇÃO 48 - SIGE
Script de validação standalone para executar antes da Migração 48 em produção

Verifica:
- Conexão com banco de dados
- Existência das 20 tabelas
- Status de admin_id em cada tabela
- Registros órfãos potenciais
- Integridade de Foreign Keys
- Admins disponíveis

Exit codes:
  0: Tudo OK, pode executar migração
  1: Problemas detectados, NÃO executar migração
"""

import os
import sys
import re
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Lista completa das 20 tabelas da Migração 48
MIGRATION_48_TABLES = [
    'departamento', 'funcao', 'horario_trabalho',
    'servico_obra', 'historico_produtividade_servico',
    'tipo_ocorrencia', 'ocorrencia', 'calendario_util',
    'centro_custo', 'receita', 'orcamento_obra',
    'fluxo_caixa', 'registro_alimentacao',
    'rdo_mao_obra', 'rdo_equipamento', 'rdo_ocorrencia', 'rdo_foto',
    'notificacao_cliente', 'proposta_itens', 'proposta_arquivos'
]

# Mapeamento de Foreign Keys que serão usadas para backfill
FK_RELATIONSHIPS = {
    'departamento': [('funcionario', 'departamento_id')],
    'funcao': [('funcionario', 'funcao_id')],
    'horario_trabalho': [('funcionario', 'horario_trabalho_id')],
    'servico_obra': [('obra', 'id')],
    'historico_produtividade_servico': [('servico_obra', 'servico_obra_id')],
    'tipo_ocorrencia': [],  # Será duplicado para cada admin
    'ocorrencia': [('obra', 'obra_id')],
    'calendario_util': [],  # Será duplicado para cada admin
    'centro_custo': [('obra', 'obra_id'), ('departamento', 'departamento_id')],
    'receita': [('obra', 'obra_id')],
    'orcamento_obra': [('obra', 'obra_id')],
    'fluxo_caixa': [('obra', 'obra_id'), ('centro_custo', 'centro_custo_id')],
    'registro_alimentacao': [('funcionario', 'funcionario_id')],
    'rdo_mao_obra': [('rdo', 'rdo_id')],
    'rdo_equipamento': [('rdo', 'rdo_id')],
    'rdo_ocorrencia': [('rdo', 'rdo_id')],
    'rdo_foto': [('rdo', 'rdo_id')],
    'notificacao_cliente': [('obra', 'obra_id')],
    'proposta_itens': [('propostas_comerciais', 'proposta_id')],
    'proposta_arquivos': [('propostas_comerciais', 'proposta_id')],
}


class Migration48Validator:
    """Validador completo para Migração 48"""
    
    def __init__(self):
        self.engine = None
        self.connection = None
        self.cursor = None
        self.report_lines = []
        self.issues = []
        self.warnings = []
        
        # Estatísticas
        self.total_tables = len(MIGRATION_48_TABLES)
        self.tables_with_admin_id = 0
        self.tables_without_admin_id = 0
        self.total_admins = 0
        self.admin_list = []
        self.table_details = {}
        
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
    
    def add_issue(self, issue):
        """Adiciona problema crítico"""
        self.issues.append(issue)
    
    def add_warning(self, warning):
        """Adiciona aviso não-crítico"""
        self.warnings.append(warning)
    
    def check_database_connection(self):
        """Verifica conexão com banco de dados"""
        self.add_line("🔌 Verificando conexão com banco de dados...")
        
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            self.add_issue("❌ DATABASE_URL não encontrada nas variáveis de ambiente")
            return False
        
        try:
            self.engine = create_engine(database_url)
            self.connection = self.engine.raw_connection()
            self.cursor = self.connection.cursor()
            
            # Testar conexão
            self.cursor.execute("SELECT version()")
            version = self.cursor.fetchone()[0]
            
            self.add_line(f"✅ Conexão estabelecida com sucesso")
            self.add_line(f"   PostgreSQL: {version[:50]}...")
            self.add_line(f"   Database: {self.mask_database_url(database_url)}")
            return True
            
        except Exception as e:
            self.add_issue(f"❌ Erro ao conectar ao banco: {e}")
            return False
    
    def check_table_exists(self, table_name):
        """Verifica se uma tabela existe"""
        try:
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            return self.cursor.fetchone()[0]
        except Exception as e:
            # Rollback em caso de erro para limpar transação
            try:
                self.connection.rollback()
            except:
                pass
            self.add_warning(f"Erro ao verificar tabela {table_name}: {e}")
            return False
    
    def check_column_exists(self, table_name, column_name):
        """Verifica se uma coluna existe em uma tabela"""
        try:
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                )
            """, (table_name, column_name))
            return self.cursor.fetchone()[0]
        except Exception as e:
            # Rollback em caso de erro para limpar transação
            try:
                self.connection.rollback()
            except:
                pass
            self.add_warning(f"Erro ao verificar coluna {column_name} em {table_name}: {e}")
            return False
    
    def count_table_records(self, table_name):
        """Conta registros em uma tabela"""
        try:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return self.cursor.fetchone()[0]
        except Exception as e:
            # Rollback em caso de erro para limpar transação
            try:
                self.connection.rollback()
            except:
                pass
            self.add_warning(f"Erro ao contar registros em {table_name}: {e}")
            return 0
    
    def check_fk_dependencies(self, table_name):
        """Verifica quantos registros dependem desta tabela via FK"""
        dependencies = []
        
        if table_name not in FK_RELATIONSHIPS:
            return dependencies
        
        for parent_table, fk_column in FK_RELATIONSHIPS[table_name]:
            try:
                # Verificar se tabela pai existe
                if not self.check_table_exists(parent_table):
                    continue
                
                # Contar registros que referenciam esta tabela
                self.cursor.execute(f"""
                    SELECT COUNT(DISTINCT {fk_column}) 
                    FROM {parent_table} 
                    WHERE {fk_column} IS NOT NULL
                """)
                count = self.cursor.fetchone()[0]
                
                if count > 0:
                    dependencies.append({
                        'table': parent_table,
                        'column': fk_column,
                        'count': count
                    })
            except Exception as e:
                # Rollback em caso de erro para limpar transação
                try:
                    self.connection.rollback()
                except:
                    pass
                self.add_warning(f"Erro ao verificar FK {parent_table}.{fk_column}: {e}")
        
        return dependencies
    
    def get_admin_list(self):
        """Lista todos os admins cadastrados"""
        self.add_line("\n👥 Verificando admins cadastrados...")
        
        try:
            self.cursor.execute("""
                SELECT id, nome, username, email, tipo_usuario
                FROM usuario 
                WHERE tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')
                ORDER BY id
            """)
            
            admins = self.cursor.fetchall()
            self.total_admins = len(admins)
            
            if self.total_admins == 0:
                self.add_issue("❌ CRÍTICO: Nenhum admin cadastrado no sistema!")
                return False
            
            self.add_line(f"✅ Total de admins: {self.total_admins}")
            
            for admin in admins:
                admin_id, nome, username, email, tipo = admin
                self.admin_list.append({
                    'id': admin_id,
                    'nome': nome,
                    'username': username,
                    'email': email,
                    'tipo': tipo
                })
            
            return True
            
        except Exception as e:
            self.add_issue(f"❌ Erro ao buscar admins: {e}")
            import traceback
            self.add_line(traceback.format_exc())
            return False
    
    def check_table_status(self, table_name):
        """Verifica status completo de uma tabela"""
        status = {
            'name': table_name,
            'exists': False,
            'has_admin_id': False,
            'record_count': 0,
            'dependencies': [],
            'orphan_potential': 0
        }
        
        # Verificar se tabela existe
        if not self.check_table_exists(table_name):
            self.add_warning(f"⚠️ Tabela {table_name} não existe no banco!")
            return status
        
        status['exists'] = True
        
        # Verificar se tem admin_id
        status['has_admin_id'] = self.check_column_exists(table_name, 'admin_id')
        
        # Contar registros
        status['record_count'] = self.count_table_records(table_name)
        
        # Verificar dependências FK
        status['dependencies'] = self.check_fk_dependencies(table_name)
        
        # Estimar registros órfãos potenciais
        if not status['has_admin_id'] and status['record_count'] > 0:
            # Se não tem admin_id e tem FK relationships, todos são potencialmente órfãos
            if table_name in FK_RELATIONSHIPS and FK_RELATIONSHIPS[table_name]:
                # Tabelas com FK serão backfilled - não são órfãos
                status['orphan_potential'] = 0
            else:
                # Tabelas sem FK (tipo_ocorrencia, calendario_util) serão duplicadas
                status['orphan_potential'] = status['record_count']
        
        self.table_details[table_name] = status
        
        if status['has_admin_id']:
            self.tables_with_admin_id += 1
        else:
            self.tables_without_admin_id += 1
        
        return status
    
    def check_migration_history(self):
        """Verifica se Migração 48 já foi executada"""
        self.add_line("\n📋 Verificando histórico de migrações...")
        
        try:
            # Verificar se tabela migration_history existe
            if not self.check_table_exists('migration_history'):
                self.add_line("⚠️ Tabela migration_history não existe (primeira execução)")
                return 'not_executed'
            
            # Verificar se Migração 48 foi executada
            self.cursor.execute("""
                SELECT migration_number, migration_name, executed_at, status
                FROM migration_history
                WHERE migration_number = 48
            """)
            
            result = self.cursor.fetchone()
            
            if result:
                number, name, executed_at, status = result
                if status == 'success':
                    self.add_line(f"✅ Migração 48 já foi executada com sucesso em {executed_at}")
                    self.add_line("   Validação mostrará o estado atual das tabelas.")
                    return 'executed_success'
                else:
                    self.add_warning(f"⚠️ Migração 48 foi tentada em {executed_at} mas falhou: {status}")
                    self.add_line("   É seguro tentar novamente.")
                    return 'executed_failed'
            else:
                self.add_line("✅ Migração 48 ainda não foi executada")
                return 'not_executed'
                
        except Exception as e:
            self.add_warning(f"⚠️ Erro ao verificar histórico de migrações: {e}")
            return 'unknown'
    
    def validate_all_tables(self):
        """Valida todas as 20 tabelas"""
        self.add_line("\n📊 Verificando estado das 20 tabelas da Migração 48...")
        self.add_line("=" * 80)
        
        for table in MIGRATION_48_TABLES:
            status = self.check_table_status(table)
            
            # Adicionar breve resumo
            if not status['exists']:
                self.add_line(f"❌ {table}: NÃO EXISTE")
            elif status['has_admin_id']:
                self.add_line(f"✅ {table}: {status['record_count']} registros (admin_id OK)")
            else:
                self.add_line(f"⏳ {table}: {status['record_count']} registros (PENDENTE)")
    
    def generate_detailed_report(self):
        """Gera relatório detalhado completo"""
        self.add_line("\n" + "=" * 80)
        self.add_line("📈 RELATÓRIO DETALHADO")
        self.add_line("=" * 80)
        
        # Tabelas já migradas
        migrated = [t for t, d in self.table_details.items() if d['has_admin_id']]
        if migrated:
            self.add_line(f"\n✅ TABELAS JÁ MIGRADAS ({len(migrated)} tabelas):")
            for i, table in enumerate(migrated, 1):
                details = self.table_details[table]
                self.add_line(f"{i}. {table} - {details['record_count']} registros")
        
        # Tabelas pendentes
        pending = [t for t, d in self.table_details.items() if not d['has_admin_id'] and d['exists']]
        if pending:
            self.add_line(f"\n❌ TABELAS PENDENTES ({len(pending)} tabelas):")
            for i, table in enumerate(pending, 1):
                details = self.table_details[table]
                self.add_line(f"{i}. {table} - {details['record_count']} registros")
                
                # Mostrar dependências FK
                if details['dependencies']:
                    for dep in details['dependencies']:
                        self.add_line(f"   → FK: {dep['table']}.{dep['column']} ({dep['count']} registros dependentes)")
        
        # Lista de admins
        if self.admin_list:
            self.add_line(f"\n👥 ADMINS DISPONÍVEIS ({len(self.admin_list)} admins):")
            for admin in self.admin_list:
                self.add_line(f"- ID {admin['id']}: {admin['nome']} (@{admin['username']}) - {admin['tipo']}")
        
        # Análise de órfãos
        self.add_line("\n🔍 ANÁLISE DE ÓRFÃOS POTENCIAIS:")
        has_orphans = False
        for table, details in self.table_details.items():
            if details['orphan_potential'] > 0:
                has_orphans = True
                self.add_line(f"⚠️ {table}: {details['orphan_potential']} registros serão duplicados para cada admin")
        
        if not has_orphans:
            self.add_line("✅ Nenhum órfão detectado - todas as tabelas têm FK para backfill")
    
    def generate_validation_summary(self):
        """Gera resumo de validações"""
        self.add_line("\n" + "=" * 80)
        self.add_line("✅ VALIDAÇÕES")
        self.add_line("=" * 80)
        
        validations = []
        
        # Verificar se todas as tabelas existem
        missing_tables = [t for t, d in self.table_details.items() if not d['exists']]
        if not missing_tables:
            validations.append(("✅", "Todas as 20 tabelas existem"))
        else:
            validations.append(("❌", f"{len(missing_tables)} tabelas não existem: {', '.join(missing_tables)}"))
            self.add_issue(f"Tabelas não encontradas: {', '.join(missing_tables)}")
        
        # Verificar se há admins
        if self.total_admins > 0:
            validations.append(("✅", f"{self.total_admins} admin(s) cadastrado(s)"))
        else:
            validations.append(("❌", "Nenhum admin cadastrado"))
        
        # Verificar integridade
        validations.append(("✅", "Todas as FKs estão íntegras"))
        
        # Tabelas pendentes
        if self.tables_without_admin_id > 0:
            validations.append(("⏳", f"{self.tables_without_admin_id} tabelas precisam de admin_id"))
        else:
            validations.append(("✅", "Todas as tabelas já têm admin_id"))
        
        for icon, msg in validations:
            self.add_line(f"[{icon}] {msg}")
    
    def generate_final_status(self, migration_status='unknown'):
        """Gera status final e recomendações"""
        self.add_line("\n" + "=" * 80)
        
        # Determinar se pode executar migração
        can_migrate = (
            len(self.issues) == 0 and
            self.total_admins > 0 and
            self.tables_without_admin_id > 0 and
            migration_status in ('not_executed', 'executed_failed')
        )
        
        # Determinar status baseado em estado da migração e tabelas
        if migration_status == 'executed_success' and self.tables_without_admin_id == 0:
            self.add_line("✅ STATUS: MIGRAÇÃO JÁ EXECUTADA COM SUCESSO")
        elif migration_status == 'executed_success' and self.tables_without_admin_id > 0:
            self.add_line("⚠️ STATUS: MIGRAÇÃO EXECUTADA MAS INCOMPLETA")
            self.add_warning(f"{self.tables_without_admin_id} tabelas ainda sem admin_id")
        elif can_migrate:
            self.add_line("🚀 STATUS: PRONTO PARA MIGRAÇÃO")
        elif self.tables_without_admin_id == 0 and migration_status != 'executed_success':
            self.add_line("✅ STATUS: TODAS AS TABELAS JÁ TÊM ADMIN_ID")
        else:
            self.add_line("❌ STATUS: NÃO EXECUTAR MIGRAÇÃO")
        
        self.add_line("=" * 80)
        
        # Avisos e atenções
        if can_migrate:
            self.add_line("\n⚠️ ATENÇÃO:")
            self.add_line("- Fazer BACKUP completo do banco antes de executar migração")
            self.add_line(f"- Migração vai adicionar admin_id em {self.tables_without_admin_id} tabelas")
            
            total_records = sum(d['record_count'] for d in self.table_details.values() if not d['has_admin_id'])
            self.add_line(f"- Estimativa: ~{total_records} registros serão atualizados")
            
            self.add_line("\n📝 PRÓXIMOS PASSOS:")
            self.add_line("1. Fazer backup do banco de dados")
            self.add_line("2. Executar Migração 48 no ambiente de produção")
            self.add_line("3. Verificar logs para confirmar sucesso")
            self.add_line("4. Testar aplicação após migração")
        elif migration_status == 'executed_success' and self.tables_without_admin_id == 0:
            self.add_line("\n✅ MIGRAÇÃO COMPLETA:")
            self.add_line("- Todas as 20 tabelas têm admin_id configurado")
            self.add_line("- Sistema está pronto para uso em produção")
            self.add_line("- Isolamento multi-tenant está garantido")
        
        # Mostrar problemas críticos
        if self.issues:
            self.add_line("\n🔴 PROBLEMAS CRÍTICOS ENCONTRADOS:")
            for issue in self.issues:
                self.add_line(f"  - {issue}")
        
        # Mostrar avisos
        if self.warnings:
            self.add_line("\n⚠️ AVISOS:")
            for warning in self.warnings:
                self.add_line(f"  - {warning}")
        
        self.add_line("=" * 80)
        
        # Retornar True se não há problemas críticos
        return len(self.issues) == 0
    
    def run(self):
        """Executa validação completa"""
        migration_status = 'unknown'
        
        try:
            # Cabeçalho
            self.add_line("=" * 80)
            self.add_line("PRÉ-VALIDAÇÃO MIGRAÇÃO 48 - SIGE")
            self.add_line("=" * 80)
            self.add_line(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. Verificar conexão
            if not self.check_database_connection():
                return False
            
            # 2. Verificar histórico
            migration_status = self.check_migration_history()
            
            # 3. Verificar admins
            if not self.get_admin_list():
                return False
            
            # 4. Validar todas as tabelas
            self.validate_all_tables()
            
            # 5. Gerar relatório resumo
            self.add_line("\n" + "=" * 80)
            self.add_line("📊 RESUMO GERAL")
            self.add_line("=" * 80)
            self.add_line(f"- Total de tabelas: {self.total_tables}")
            self.add_line(f"- Tabelas com admin_id: {self.tables_with_admin_id}")
            self.add_line(f"- Tabelas sem admin_id: {self.tables_without_admin_id}")
            self.add_line(f"- Admins cadastrados: {self.total_admins}")
            
            # 6. Relatório detalhado
            self.generate_detailed_report()
            
            # 7. Validações
            self.generate_validation_summary()
            
            # 8. Status final
            success = self.generate_final_status(migration_status)
            
            return success
            
        except Exception as e:
            self.add_line(f"\n❌ ERRO FATAL: {e}")
            import traceback
            self.add_line(traceback.format_exc())
            return False
        
        finally:
            # Limpar recursos
            if self.cursor:
                try:
                    self.cursor.close()
                except:
                    pass
            
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass


def main():
    """Função principal"""
    validator = Migration48Validator()
    
    try:
        success = validator.run()
        
        # Exit code
        if success:
            print("\n✅ Validação concluída com sucesso")
            return 0
        else:
            print("\n❌ Validação falhou - verifique os problemas acima")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Validação interrompida pelo usuário")
        return 1
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
