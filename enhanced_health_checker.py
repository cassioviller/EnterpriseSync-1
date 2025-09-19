#!/usr/bin/env python3
"""
🏥 SISTEMA DE HEALTH CHECK APRIMORADO PARA PRODUÇÃO
==================================================
FASE 3: Health checks comprehensive pós-migração com detecção de problemas
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from flask import jsonify
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

class EnhancedHealthChecker:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'status': 'unknown',
            'checks': {},
            'errors': [],
            'warnings': [],
            'info': [],
            'performance': {},
            'duracao_ms': 0
        }
        
        # Configurar logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _log_result(self, check_name, status, message, level='info'):
        """Log resultado de uma verificação"""
        self.results['checks'][check_name] = status
        
        if level == 'error':
            self.results['errors'].append(f"{check_name}: {message}")
            self.logger.error(f"❌ {check_name}: {message}")
        elif level == 'warning':
            self.results['warnings'].append(f"{check_name}: {message}")
            self.logger.warning(f"⚠️ {check_name}: {message}")
        else:
            self.results['info'].append(f"{check_name}: {message}")
            self.logger.info(f"✅ {check_name}: {message}")
    
    def check_database_connectivity(self):
        """Verificação básica de conectividade"""
        try:
            engine = create_engine(self.database_url)
            start_time = datetime.now()
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.results['performance']['db_connection_ms'] = round(duration, 2)
            
            self._log_result('database_connection', 'OK', f'Conectado em {duration:.2f}ms')
            return True
            
        except Exception as e:
            self._log_result('database_connection', 'FAIL', str(e), 'error')
            return False
    
    def check_critical_tables(self):
        """Verificar tabelas críticas do sistema"""
        try:
            engine = create_engine(self.database_url)
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            # Tabelas críticas que devem existir
            critical_tables = {
                'usuario': 'Usuários do sistema',
                'funcionario': 'Funcionários',
                'obra': 'Obras',
                'veiculo': 'Veículos',
                'uso_veiculo': 'Usos de veículos',
                'custo_veiculo': 'Custos de veículos',
                'passageiro_veiculo': 'Passageiros de veículos'
            }
            
            missing_tables = []
            present_tables = []
            
            for table, description in critical_tables.items():
                if table in existing_tables:
                    present_tables.append(table)
                    self._log_result(f'table_{table}', 'OK', f'{description} - Presente')
                else:
                    missing_tables.append(table)
                    self._log_result(f'table_{table}', 'MISSING', f'{description} - Ausente', 'error')
            
            if missing_tables:
                self._log_result('critical_tables', 'PARTIAL', 
                               f'{len(missing_tables)} tabelas ausentes: {missing_tables}', 'error')
                return False
            else:
                self._log_result('critical_tables', 'OK', 
                               f'Todas as {len(critical_tables)} tabelas críticas presentes')
                return True
                
        except Exception as e:
            self._log_result('critical_tables', 'ERROR', str(e), 'error')
            return False
    
    def check_obsolete_tables(self):
        """Verificar se tabelas obsoletas foram removidas"""
        try:
            engine = create_engine(self.database_url)
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            # Tabelas obsoletas que devem ter sido removidas
            obsolete_tables = {
                'alocacao_veiculo': 'Sistema antigo de alocação',
                'equipe_veiculo': 'Sistema antigo de equipes',
                'transferencia_veiculo': 'Sistema antigo de transferências',
                'manutencao_veiculo': 'Sistema antigo de manutenção',
                'alerta_veiculo': 'Sistema antigo de alertas'
            }
            
            found_obsolete = []
            removed_obsolete = []
            
            for table, description in obsolete_tables.items():
                if table in existing_tables:
                    found_obsolete.append(table)
                    self._log_result(f'obsolete_{table}', 'PRESENT', 
                                   f'{description} - Ainda presente (problema)', 'warning')
                else:
                    removed_obsolete.append(table)
                    self._log_result(f'obsolete_{table}', 'REMOVED', 
                                   f'{description} - Removida corretamente')
            
            if found_obsolete:
                self._log_result('obsolete_tables', 'WARNING', 
                               f'{len(found_obsolete)} tabelas obsoletas ainda presentes: {found_obsolete}', 'warning')
                return False
            else:
                self._log_result('obsolete_tables', 'OK', 
                               f'Todas as {len(obsolete_tables)} tabelas obsoletas removidas')
                return True
                
        except Exception as e:
            self._log_result('obsolete_tables', 'ERROR', str(e), 'error')
            return False
    
    def check_data_integrity(self):
        """Verificar integridade básica dos dados"""
        try:
            engine = create_engine(self.database_url)
            
            with engine.connect() as conn:
                # Contar registros principais
                counts = {}
                tables_to_count = ['usuario', 'funcionario', 'obra', 'veiculo', 'uso_veiculo', 'custo_veiculo']
                
                for table in tables_to_count:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        counts[table] = count
                        self._log_result(f'count_{table}', count, f'{count} registros')
                    except Exception as e:
                        self._log_result(f'count_{table}', 'ERROR', str(e), 'warning')
                        counts[table] = -1
                
                self.results['data_counts'] = counts
                
                # Verificações de integridade específicas
                integrity_issues = []
                
                # 1. Verificar se há usuários
                if counts.get('usuario', 0) == 0:
                    integrity_issues.append("Nenhum usuário encontrado")
                
                # 2. Verificar se veículos têm admin_id (multi-tenant)
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM veiculo WHERE admin_id IS NULL
                    """))
                    null_admin_id = result.scalar()
                    
                    if null_admin_id > 0:
                        integrity_issues.append(f"{null_admin_id} veículos sem admin_id")
                        self._log_result('vehicle_admin_id', 'WARNING', 
                                       f'{null_admin_id} veículos sem admin_id', 'warning')
                    else:
                        self._log_result('vehicle_admin_id', 'OK', 'Todos veículos têm admin_id')
                        
                except Exception as e:
                    self._log_result('vehicle_admin_id', 'ERROR', str(e), 'warning')
                
                # 3. Verificar constraints de veículos
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.table_constraints
                        WHERE table_name = 'veiculo' 
                        AND constraint_type = 'UNIQUE'
                        AND constraint_name LIKE '%admin_id%placa%'
                    """))
                    unique_constraints = result.scalar()
                    
                    if unique_constraints > 0:
                        self._log_result('vehicle_constraints', 'OK', 'Constraints de unicidade presentes')
                    else:
                        integrity_issues.append("Constraint única (admin_id, placa) ausente")
                        self._log_result('vehicle_constraints', 'WARNING', 
                                       'Constraint única ausente', 'warning')
                        
                except Exception as e:
                    self._log_result('vehicle_constraints', 'ERROR', str(e), 'warning')
                
                if integrity_issues:
                    self._log_result('data_integrity', 'ISSUES', 
                                   f'{len(integrity_issues)} problemas: {integrity_issues}', 'warning')
                    return False
                else:
                    self._log_result('data_integrity', 'OK', 'Integridade dos dados verificada')
                    return True
                    
        except Exception as e:
            self._log_result('data_integrity', 'ERROR', str(e), 'error')
            return False
    
    def check_vehicle_system_health(self):
        """Verificação específica do sistema de veículos"""
        try:
            engine = create_engine(self.database_url)
            
            with engine.connect() as conn:
                vehicle_checks = {}
                
                # 1. Testar query básica de veículos
                try:
                    result = conn.execute(text("SELECT id, placa, admin_id FROM veiculo LIMIT 5"))
                    vehicles = result.fetchall()
                    vehicle_checks['basic_query'] = 'OK'
                    self._log_result('vehicle_basic_query', 'OK', f'{len(vehicles)} veículos testados')
                except Exception as e:
                    vehicle_checks['basic_query'] = 'FAIL'
                    self._log_result('vehicle_basic_query', 'FAIL', str(e), 'error')
                
                # 2. Testar relações de uso
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM uso_veiculo uv 
                        JOIN veiculo v ON uv.veiculo_id = v.id 
                        LIMIT 1
                    """))
                    join_test = result.scalar()
                    vehicle_checks['usage_relation'] = 'OK'
                    self._log_result('vehicle_usage_relation', 'OK', 'Relação veiculo-uso funcional')
                except Exception as e:
                    vehicle_checks['usage_relation'] = 'FAIL'
                    self._log_result('vehicle_usage_relation', 'FAIL', str(e), 'error')
                
                # 3. Testar relações de custo
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM custo_veiculo cv 
                        JOIN veiculo v ON cv.veiculo_id = v.id 
                        LIMIT 1
                    """))
                    cost_test = result.scalar()
                    vehicle_checks['cost_relation'] = 'OK'
                    self._log_result('vehicle_cost_relation', 'OK', 'Relação veiculo-custo funcional')
                except Exception as e:
                    vehicle_checks['cost_relation'] = 'FAIL'
                    self._log_result('vehicle_cost_relation', 'FAIL', str(e), 'error')
                
                self.results['vehicle_system'] = vehicle_checks
                
                # Determinar status geral do sistema de veículos
                failed_checks = [k for k, v in vehicle_checks.items() if v == 'FAIL']
                
                if failed_checks:
                    self._log_result('vehicle_system_health', 'ISSUES', 
                                   f'{len(failed_checks)} problemas: {failed_checks}', 'warning')
                    return False
                else:
                    self._log_result('vehicle_system_health', 'HEALTHY', 'Sistema de veículos operacional')
                    return True
                    
        except Exception as e:
            self._log_result('vehicle_system_health', 'ERROR', str(e), 'error')
            return False
    
    def run_comprehensive_check(self):
        """Executa verificação completa do sistema"""
        start_time = datetime.now()
        
        self.logger.info("🏥 Iniciando health check abrangente...")
        
        # Lista de verificações a executar
        checks = [
            ('database_connectivity', self.check_database_connectivity),
            ('critical_tables', self.check_critical_tables),
            ('obsolete_tables', self.check_obsolete_tables),
            ('data_integrity', self.check_data_integrity),
            ('vehicle_system_health', self.check_vehicle_system_health)
        ]
        
        passed_checks = 0
        failed_checks = 0
        
        for check_name, check_func in checks:
            try:
                if check_func():
                    passed_checks += 1
                else:
                    failed_checks += 1
            except Exception as e:
                failed_checks += 1
                self._log_result(check_name, 'ERROR', f'Erro na execução: {e}', 'error')
        
        # Calcular duração
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        self.results['duracao_ms'] = round(duration_ms, 2)
        
        # Determinar status final
        if self.results['errors']:
            self.results['status'] = 'error'
            status_code = 500
        elif self.results['warnings']:
            self.results['status'] = 'warning'
            status_code = 200
        else:
            self.results['status'] = 'healthy'
            status_code = 200
        
        # Resumo final
        self.results['summary'] = {
            'passed_checks': passed_checks,
            'failed_checks': failed_checks,
            'total_checks': len(checks),
            'total_errors': len(self.results['errors']),
            'total_warnings': len(self.results['warnings']),
            'duration_ms': duration_ms
        }
        
        self.logger.info(f"🏥 Health check concluído: {self.results['status']} "
                        f"({passed_checks}/{len(checks)} checks OK)")
        
        return self.results, status_code
    
    def save_health_report(self):
        """Salva relatório detalhado do health check"""
        report_file = f'/tmp/health_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        try:
            with open(report_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            self.logger.info(f"📊 Relatório salvo: {report_file}")
            return report_file
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar relatório: {e}")
            return None

def create_enhanced_health_endpoint():
    """Cria endpoint Flask para health check aprimorado"""
    def enhanced_health_check():
        checker = EnhancedHealthChecker()
        results, status_code = checker.run_comprehensive_check()
        checker.save_health_report()
        return jsonify(results), status_code
    
    return enhanced_health_check

if __name__ == '__main__':
    # Teste standalone do health checker
    checker = EnhancedHealthChecker()
    results, status_code = checker.run_comprehensive_check()
    checker.save_health_report()
    
    print(f"\n🏥 HEALTH CHECK RESULT: {results['status'].upper()}")
    print(f"📊 Status Code: {status_code}")
    print(f"⏱️ Duration: {results['duracao_ms']}ms")
    
    if results['errors']:
        print(f"❌ Errors: {len(results['errors'])}")
        for error in results['errors']:
            print(f"   - {error}")
    
    if results['warnings']:
        print(f"⚠️ Warnings: {len(results['warnings'])}")
        for warning in results['warnings']:
            print(f"   - {warning}")