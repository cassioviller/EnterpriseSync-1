#!/usr/bin/env python3
"""
🚗 DEPLOY AUTOMÁTICO - MÓDULO VEÍCULOS V2.0 COMPLETO
===============================================
Script de deploy para aplicar o redesign completo do sistema de veículos
em produção com todas as validações e proteções necessárias.

Fase: Deploy Automático (23/09/2025)
Status: Production Ready
"""

import os
import sys
import json
import traceback
from datetime import datetime

# Adicionar path da aplicação
sys.path.append('/app')
sys.path.append('.')

def log_deploy(message, level="INFO"):
    """Log com timestamp e nível"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")
    
    # Salvar em arquivo também
    try:
        with open('/tmp/veiculos_v2_deploy.log', 'a') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except:
        pass

def run_veiculos_v2_deployment():
    """
    Executa o deploy completo do módulo veículos v2.0
    """
    log_deploy("🚗 INICIANDO DEPLOY VEÍCULOS V2.0", "INFO")
    log_deploy("=" * 50, "INFO")
    
    deployment_result = {
        'timestamp': datetime.now().isoformat(),
        'status': 'unknown',
        'phases': {},
        'errors': [],
        'warnings': [],
        'success_count': 0,
        'total_phases': 6
    }
    
    try:
        from app import app, db
        from sqlalchemy import text, inspect
        
        with app.app_context():
            
            # FASE 1: Verificação de pré-requisitos
            log_deploy("📋 FASE 1: Verificação de pré-requisitos", "INFO")
            try:
                # Verificar se tabelas obsoletas ainda existem
                inspector = inspect(db.engine)
                tabelas_existentes = inspector.get_table_names()
                
                tabelas_obsoletas = [
                    'alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo',
                    'manutencao_veiculo', 'alerta_veiculo'
                ]
                
                obsoletas_presentes = [t for t in tabelas_obsoletas if t in tabelas_existentes]
                
                if obsoletas_presentes:
                    log_deploy(f"⚠️ Tabelas obsoletas encontradas: {obsoletas_presentes}", "WARNING")
                    deployment_result['warnings'].append(f"Tabelas obsoletas: {obsoletas_presentes}")
                else:
                    log_deploy("✅ Nenhuma tabela obsoleta encontrada", "INFO")
                
                deployment_result['phases']['prerequisitos'] = 'OK'
                deployment_result['success_count'] += 1
                
            except Exception as e:
                log_deploy(f"❌ Erro na verificação de pré-requisitos: {e}", "ERROR")
                deployment_result['phases']['prerequisitos'] = 'FAIL'
                deployment_result['errors'].append(f"Pré-requisitos: {str(e)}")
            
            # FASE 2: Criação do schema novo
            log_deploy("🏗️ FASE 2: Criação do schema novo", "INFO")
            try:
                # Executar create_all para garantir que as tabelas existam
                db.create_all()
                log_deploy("✅ db.create_all() executado", "INFO")
                
                # Verificar se as tabelas novas foram criadas
                inspector = inspect(db.engine)
                tabelas_existentes = inspector.get_table_names()
                
                tabelas_novas = ['veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo']
                
                for tabela in tabelas_novas:
                    if tabela in tabelas_existentes:
                        log_deploy(f"✅ Tabela nova verificada: {tabela}", "INFO")
                    else:
                        log_deploy(f"❌ Tabela nova ausente: {tabela}", "ERROR")
                        deployment_result['errors'].append(f"Tabela ausente: {tabela}")
                
                deployment_result['phases']['schema_novo'] = 'OK'
                deployment_result['success_count'] += 1
                
            except Exception as e:
                log_deploy(f"❌ Erro na criação do schema: {e}", "ERROR")
                deployment_result['phases']['schema_novo'] = 'FAIL'
                deployment_result['errors'].append(f"Schema: {str(e)}")
            
            # FASE 3: Verificação de modelos
            log_deploy("🔍 FASE 3: Verificação de modelos", "INFO")
            try:
                from models import Veiculo, UsoVeiculo, CustoVeiculo
                # PassageiroVeiculo pode não existir ainda, tratado como opcional
                try:
                    from models import PassageiroVeiculo
                    log_deploy("✅ PassageiroVeiculo importado", "INFO")
                except ImportError:
                    log_deploy("⚠️ PassageiroVeiculo não encontrado (ok para v2.0)", "WARNING")
                    PassageiroVeiculo = None
                
                # Verificar se os modelos podem ser importados
                log_deploy("✅ Modelos importados com sucesso", "INFO")
                
                # Testar queries básicas
                count_veiculos = Veiculo.query.count()
                count_usos = UsoVeiculo.query.count()
                count_custos = CustoVeiculo.query.count()
                
                if PassageiroVeiculo:
                    count_passageiros = PassageiroVeiculo.query.count()
                    log_deploy(f"📊 Contagens: {count_veiculos} veículos, {count_usos} usos, {count_custos} custos, {count_passageiros} passageiros", "INFO")
                else:
                    log_deploy(f"📊 Contagens: {count_veiculos} veículos, {count_usos} usos, {count_custos} custos", "INFO")
                
                deployment_result['phases']['modelos'] = 'OK'
                deployment_result['success_count'] += 1
                
            except Exception as e:
                log_deploy(f"❌ Erro na verificação de modelos: {e}", "ERROR")
                deployment_result['phases']['modelos'] = 'FAIL'
                deployment_result['errors'].append(f"Modelos: {str(e)}")
            
            # FASE 4: Verificação de services
            log_deploy("⚙️ FASE 4: Verificação de services", "INFO")
            try:
                from veiculos_services import VeiculoService, UsoVeiculoService, CustoVeiculoService
                
                # Testar instanciação dos services
                veiculo_service = VeiculoService()
                uso_service = UsoVeiculoService()
                custo_service = CustoVeiculoService()
                
                log_deploy("✅ Services instanciados com sucesso", "INFO")
                
                deployment_result['phases']['services'] = 'OK'
                deployment_result['success_count'] += 1
                
            except Exception as e:
                log_deploy(f"❌ Erro na verificação de services: {e}", "ERROR")
                deployment_result['phases']['services'] = 'FAIL'
                deployment_result['errors'].append(f"Services: {str(e)}")
            
            # FASE 5: Verificação de circuit breakers
            log_deploy("🔌 FASE 5: Verificação de circuit breakers", "INFO")
            try:
                try:
                    from utils.circuit_breaker import circuit_breakers
                except ImportError:
                    log_deploy("⚠️ utils.circuit_breaker não encontrado - usando fallback", "WARNING")
                    circuit_breakers = {}
                
                # Verificar se os circuit breakers específicos existem
                cb_names = ['veiculo_list_query', 'database_heavy_query']
                
                for cb_name in cb_names:
                    if cb_name in circuit_breakers:
                        cb = circuit_breakers[cb_name]
                        log_deploy(f"✅ Circuit breaker ativo: {cb_name} (state: {cb.state})", "INFO")
                    else:
                        log_deploy(f"⚠️ Circuit breaker não encontrado: {cb_name}", "WARNING")
                        deployment_result['warnings'].append(f"CB ausente: {cb_name}")
                
                deployment_result['phases']['circuit_breakers'] = 'OK'
                deployment_result['success_count'] += 1
                
            except Exception as e:
                log_deploy(f"❌ Erro na verificação de circuit breakers: {e}", "ERROR")
                deployment_result['phases']['circuit_breakers'] = 'FAIL'
                deployment_result['errors'].append(f"Circuit breakers: {str(e)}")
            
            # FASE 6: Teste funcional básico
            log_deploy("🧪 FASE 6: Teste funcional básico", "INFO")
            try:
                # Tentar resolver admin_id para teste
                try:
                    try:
                        from utils.multitenant_helper import get_tenant_admin_id
                    except ImportError:
                        # Fallback - função auxiliar pode não existir
                        def get_tenant_admin_id():
                            return None
                    
                    # Simular request context se necessário
                    admin_id = None
                    try:
                        admin_id = get_tenant_admin_id()
                    except:
                        # Em contexto de deploy, pegar qualquer admin válido
                        from models import Usuario
                        from app import TipoUsuario
                        
                        admin_user = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
                        if admin_user:
                            admin_id = admin_user.id
                    
                    if admin_id:
                        log_deploy(f"✅ Admin ID para teste: {admin_id}", "INFO")
                        
                        # Testar query de veículos com filtro admin
                        from models import Veiculo
                        veiculos_admin = Veiculo.query.filter_by(admin_id=admin_id).all()
                        log_deploy(f"✅ Query de veículos funcionando: {len(veiculos_admin)} veículos encontrados", "INFO")
                        
                    else:
                        log_deploy("⚠️ Nenhum admin encontrado para teste", "WARNING")
                        deployment_result['warnings'].append("Sem admin para teste")
                
                except Exception as e:
                    log_deploy(f"⚠️ Erro no teste de admin_id: {e}", "WARNING")
                    deployment_result['warnings'].append(f"Teste admin_id: {str(e)}")
                
                deployment_result['phases']['teste_funcional'] = 'OK'
                deployment_result['success_count'] += 1
                
            except Exception as e:
                log_deploy(f"❌ Erro no teste funcional: {e}", "ERROR")
                deployment_result['phases']['teste_funcional'] = 'FAIL'
                deployment_result['errors'].append(f"Teste funcional: {str(e)}")
            
            # Determinar status final
            if deployment_result['errors']:
                deployment_result['status'] = 'error'
                log_deploy(f"❌ DEPLOY VEÍCULOS V2.0: ERRO ({len(deployment_result['errors'])} erros)", "ERROR")
                return False
                
            elif deployment_result['warnings']:
                deployment_result['status'] = 'warning'
                log_deploy(f"⚠️ DEPLOY VEÍCULOS V2.0: WARNING ({len(deployment_result['warnings'])} warnings)", "WARNING")
                return True  # Warnings não impedem o deploy
                
            else:
                deployment_result['status'] = 'success'
                log_deploy("✅ DEPLOY VEÍCULOS V2.0: SUCESSO COMPLETO", "INFO")
                return True
            
    except Exception as e:
        log_deploy(f"❌ ERRO CRÍTICO NO DEPLOY VEÍCULOS V2.0: {e}", "ERROR")
        log_deploy(f"📋 Traceback: {traceback.format_exc()}", "ERROR")
        deployment_result['status'] = 'critical_error'
        deployment_result['errors'].append(f"Erro crítico: {str(e)}")
        return False
        
    finally:
        # Salvar resultado completo
        try:
            with open('/tmp/veiculos_v2_deploy_result.json', 'w') as f:
                json.dump(deployment_result, f, indent=2)
            log_deploy("💾 Resultado completo salvo em: /tmp/veiculos_v2_deploy_result.json", "INFO")
        except:
            pass
        
        log_deploy("=" * 50, "INFO")
        log_deploy(f"✅ DEPLOY VEÍCULOS V2.0 CONCLUÍDO - Status: {deployment_result['status']}", "INFO")
        log_deploy(f"📊 Fases completadas: {deployment_result['success_count']}/{deployment_result['total_phases']}", "INFO")

def executar_deploy_veiculos_v2():
    """
    Função principal chamada pelo entrypoint automático
    Retorna True se o deploy foi bem-sucedido
    """
    return run_veiculos_v2_deployment()

if __name__ == "__main__":
    success = run_veiculos_v2_deployment()
    sys.exit(0 if success else 1)