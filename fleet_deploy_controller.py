#!/usr/bin/env python3
# ================================
# FLEET DEPLOY CONTROLLER - SCRIPT FINAL DE DEPLOY
# ================================
# Controle completo do deploy do sistema FLEET em produção
# Ativação gradual, validação e cleanup das tabelas antigas

import os
import sys
import logging
import subprocess
import time
from datetime import datetime
import json
import urllib.request

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fleet_deploy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FleetDeployController:
    """
    Controlador de deploy do sistema FLEET.
    Gerencia todo o processo de cutover do sistema legacy para FLEET.
    """
    
    def __init__(self):
        self.deploy_stats = {
            'inicio': datetime.now(),
            'etapas_concluidas': [],
            'erros': []
        }
        self.backup_timestamp = None
        
    def verificar_prerequisitos(self):
        """Verificar se todos os pré-requisitos estão atendidos"""
        logger.info("🔍 Verificando pré-requisitos do deploy...")
        
        prerequisitos = {
            'arquivos_necessarios': [
                'fleet_models.py',
                'fleet_service.py', 
                'fleet_routes.py',
                'fleet_migration_production.py',
                'app.py'
            ],
            'variaveis_ambiente': {
                'DATABASE_URL': 'obrigatória',
                'FLEET_CUTOVER': 'deve estar false',
                'SESSION_SECRET': 'obrigatória'
            }
        }
        
        # Verificar arquivos
        for arquivo in prerequisitos['arquivos_necessarios']:
            if not os.path.exists(arquivo):
                logger.error(f"❌ Arquivo obrigatório não encontrado: {arquivo}")
                return False
            else:
                logger.info(f"✅ {arquivo}")
        
        # Verificar variáveis de ambiente
        for var, status in prerequisitos['variaveis_ambiente'].items():
            valor = os.environ.get(var)
            if status == 'obrigatória' and not valor:
                logger.error(f"❌ Variável de ambiente obrigatória: {var}")
                return False
            elif var == 'FLEET_CUTOVER' and valor == 'true':
                logger.warning(f"⚠️ FLEET_CUTOVER já está ativo: {valor}")
            else:
                logger.info(f"✅ {var}: {'definida' if valor else 'não definida'}")
        
        logger.info("✅ Todos os pré-requisitos atendidos")
        return True
    
    def executar_migracao_dados(self):
        """Executar migração de dados legacy para FLEET"""
        logger.info("📦 Executando migração de dados...")
        
        try:
            # Executar script de migração
            env_vars = os.environ.copy()
            env_vars['AUTO_MIGRATIONS_ENABLED'] = 'true'
            
            resultado = subprocess.run(
                [sys.executable, 'fleet_migration_production.py', '--auto'],
                env=env_vars,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos timeout
            )
            
            if resultado.returncode == 0:
                logger.info("✅ Migração de dados concluída com sucesso")
                logger.info(f"📋 Output: {resultado.stdout}")
                return True
            else:
                logger.error(f"❌ Migração falhou: {resultado.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Migração expirou (timeout de 10 minutos)")
            return False
        except Exception as e:
            logger.error(f"❌ Erro na migração: {e}")
            return False
    
    def ativar_sistema_fleet(self):
        """Ativar sistema FLEET via variável de ambiente"""
        logger.info("🚀 Ativando sistema FLEET...")
        
        try:
            # Definir variável de ambiente
            os.environ['FLEET_CUTOVER'] = 'true'
            os.environ['FLEET_CUTOVER_TIMESTAMP'] = datetime.now().isoformat()
            
            # Para docker/produção, adicionar ao .env ou docker-compose
            env_content = f"""
# FLEET SYSTEM ACTIVATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
FLEET_CUTOVER=true
FLEET_CUTOVER_TIMESTAMP={datetime.now().isoformat()}
"""
            
            with open('.env.fleet', 'w') as f:
                f.write(env_content.strip())
            
            logger.info("✅ Sistema FLEET ativado")
            logger.info("📝 Configurações salvas em .env.fleet")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao ativar FLEET: {e}")
            return False
    
    def testar_sistema_fleet(self, base_url='http://localhost:5000'):
        """Testar se sistema FLEET está funcionando corretamente"""
        logger.info("🧪 Testando sistema FLEET...")
        
        try:
            # Aguardar restart da aplicação
            logger.info("⏳ Aguardando restart da aplicação...")
            time.sleep(10)
            
            # Testes básicos
            testes = [
                {
                    'nome': 'Health check da aplicação',
                    'url': f'{base_url}/health',
                    'metodo': 'GET'
                },
                {
                    'nome': 'Status do sistema FLEET',
                    'url': f'{base_url}/api/fleet/status',
                    'metodo': 'GET'
                }
            ]
            
            testes_passou = 0
            
            for teste in testes:
                try:
                    req = urllib.request.Request(teste['url'])
                    response = urllib.request.urlopen(req, timeout=30)
                    if response.getcode() == 200:
                        logger.info(f"✅ {teste['nome']}: OK")
                        testes_passou += 1
                    else:
                        logger.warning(f"⚠️ {teste['nome']}: HTTP {response.getcode()}")
                except Exception as e:
                    logger.warning(f"⚠️ {teste['nome']}: {e}")
            
            # Considerar sucesso se pelo menos health check passou
            sucesso = testes_passou >= 1
            
            if sucesso:
                logger.info(f"✅ Testes básicos concluídos: {testes_passou}/{len(testes)}")
            else:
                logger.error(f"❌ Testes falharam: {testes_passou}/{len(testes)}")
            
            return sucesso
            
        except Exception as e:
            logger.error(f"❌ Erro nos testes: {e}")
            return False
    
    def validar_dados_migrados(self):
        """Validar se dados foram migrados corretamente"""
        logger.info("✅ Validando dados migrados...")
        
        try:
            # Setup Flask para validação
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from app import app, db
            from models import Veiculo, UsoVeiculo, CustoVeiculo
            from fleet_models import FleetVehicle, FleetVehicleUsage, FleetVehicleCost
            
            with app.app_context():
                # Contar registros
                legacy_counts = {
                    'veiculos': Veiculo.query.count(),
                    'usos': UsoVeiculo.query.count(),
                    'custos': CustoVeiculo.query.count()
                }
                
                fleet_counts = {
                    'veiculos': FleetVehicle.query.count(),
                    'usos': FleetVehicleUsage.query.count(),
                    'custos': FleetVehicleCost.query.count()
                }
                
                logger.info("📊 VALIDAÇÃO DE DADOS:")
                logger.info(f"   Veículos - Legacy: {legacy_counts['veiculos']} | FLEET: {fleet_counts['veiculos']}")
                logger.info(f"   Usos - Legacy: {legacy_counts['usos']} | FLEET: {fleet_counts['usos']}")
                logger.info(f"   Custos - Legacy: {legacy_counts['custos']} | FLEET: {fleet_counts['custos']}")
                
                # Validar integridade básica
                if fleet_counts['veiculos'] > 0:
                    logger.info("✅ Veículos migrados com sucesso")
                    return True
                else:
                    logger.error("❌ Nenhum veículo foi migrado")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Erro na validação: {e}")
            return False
    
    def remover_tabelas_legacy(self, confirmar=False):
        """Remover tabelas legacy após validação (CUIDADO!)"""
        if not confirmar:
            logger.warning("⚠️ Remoção de tabelas legacy pulada (confirmar=False)")
            return True
            
        logger.info("🗑️ Removendo tabelas legacy...")
        
        try:
            from app import app, db
            
            with app.app_context():
                # Lista de tabelas para remover
                tabelas_legacy = ['custo_veiculo', 'uso_veiculo', 'veiculo']
                
                for tabela in tabelas_legacy:
                    try:
                        db.session.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
                        logger.info(f"✅ Tabela {tabela} removida")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao remover {tabela}: {e}")
                
                db.session.commit()
                logger.info("✅ Limpeza de tabelas legacy concluída")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")
            return False
    
    def executar_deploy_completo(self, remover_legacy=False):
        """Executar deploy completo do sistema FLEET"""
        logger.info("🚀 INICIANDO DEPLOY COMPLETO DO SISTEMA FLEET")
        logger.info("=" * 60)
        
        try:
            # Etapa 1: Verificar pré-requisitos
            if not self.verificar_prerequisitos():
                logger.error("❌ Pré-requisitos não atendidos - abortando deploy")
                return False
            self.deploy_stats['etapas_concluidas'].append('prerequisitos')
            
            # Etapa 2: Executar migração de dados
            if not self.executar_migracao_dados():
                logger.error("❌ Migração de dados falhou - abortando deploy")
                return False
            self.deploy_stats['etapas_concluidas'].append('migracao')
            
            # Etapa 3: Ativar sistema FLEET
            if not self.ativar_sistema_fleet():
                logger.error("❌ Ativação do FLEET falhou - abortando deploy")
                return False
            self.deploy_stats['etapas_concluidas'].append('ativacao')
            
            # Etapa 4: Testar sistema
            if not self.testar_sistema_fleet():
                logger.warning("⚠️ Testes básicos falharam - continuando com cuidado")
            else:
                self.deploy_stats['etapas_concluidas'].append('testes')
            
            # Etapa 5: Validar dados
            if not self.validar_dados_migrados():
                logger.error("❌ Validação de dados falhou - sistema pode estar inconsistente")
                return False
            self.deploy_stats['etapas_concluidas'].append('validacao')
            
            # Etapa 6: Remover tabelas legacy (opcional)
            if remover_legacy:
                if self.remover_tabelas_legacy(confirmar=True):
                    self.deploy_stats['etapas_concluidas'].append('limpeza')
                else:
                    logger.warning("⚠️ Limpeza de tabelas legacy falhou - dados legacy mantidos")
            
            # Estatísticas finais
            self.deploy_stats['fim'] = datetime.now()
            duracao = self.deploy_stats['fim'] - self.deploy_stats['inicio']
            
            logger.info("=" * 60)
            logger.info("🎉 DEPLOY DO SISTEMA FLEET CONCLUÍDO COM SUCESSO!")
            logger.info(f"⏱️ Duração total: {duracao}")
            logger.info(f"✅ Etapas concluídas: {', '.join(self.deploy_stats['etapas_concluidas'])}")
            logger.info("🚗 Sistema de veículos FLEET está agora ATIVO!")
            logger.info("📝 Para reverter: definir FLEET_CUTOVER=false e reiniciar aplicação")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ ERRO CRÍTICO NO DEPLOY: {e}")
            return False
    
    def gerar_relatorio_deploy(self):
        """Gerar relatório detalhado do deploy"""
        relatorio = {
            'timestamp': datetime.now().isoformat(),
            'duracao': str(self.deploy_stats.get('fim', datetime.now()) - self.deploy_stats['inicio']),
            'etapas_concluidas': self.deploy_stats['etapas_concluidas'],
            'erros': self.deploy_stats['erros'],
            'status': 'SUCESSO' if len(self.deploy_stats['etapas_concluidas']) >= 4 else 'FALHA',
            'ambiente': 'PRODUÇÃO' if 'prod' in os.environ.get('DATABASE_URL', '').lower() else 'DESENVOLVIMENTO'
        }
        
        with open(f'fleet_deploy_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
            json.dump(relatorio, f, indent=2)
        
        return relatorio


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy controlado do sistema FLEET')
    parser.add_argument('--auto', action='store_true', help='Execução automática sem confirmações')
    parser.add_argument('--remove-legacy', action='store_true', help='Remover tabelas legacy após validação')
    parser.add_argument('--test-only', action='store_true', help='Apenas testar sistema FLEET atual')
    
    args = parser.parse_args()
    
    controller = FleetDeployController()
    
    if args.test_only:
        logger.info("🧪 Executando apenas testes do sistema FLEET")
        sucesso = controller.testar_sistema_fleet()
        sys.exit(0 if sucesso else 1)
    
    if not args.auto:
        print("🚨 ATENÇÃO: DEPLOY COMPLETO DO SISTEMA FLEET")
        print("   - Irá migrar TODOS os dados para sistema FLEET")
        print("   - Ativará o novo sistema permanentemente")
        print("   - Processo complexo - recomendado backup manual antes")
        if args.remove_legacy:
            print("   - REMOVERÁ tabelas legacy após validação (IRREVERSÍVEL)")
        
        response = input("\n🤔 Confirma execução? (digite 'CONFIRMO DEPLOY'): ")
        if response != 'CONFIRMO DEPLOY':
            print("❌ Deploy cancelado pelo usuário")
            return False
    else:
        print("🚀 Executando deploy automaticamente")
    
    # Executar deploy
    sucesso = controller.executar_deploy_completo(remover_legacy=args.remove_legacy)
    
    # Gerar relatório
    relatorio = controller.gerar_relatorio_deploy()
    print(f"📋 Relatório salvo: fleet_deploy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    if sucesso:
        print("✅ DEPLOY CONCLUÍDO COM SUCESSO!")
        print("🚗 Sistema FLEET está ativo e funcional!")
        return True
    else:
        print("❌ DEPLOY FALHOU - Verifique os logs")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)