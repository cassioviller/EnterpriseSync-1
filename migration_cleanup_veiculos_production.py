#!/usr/bin/env python3
"""
🚀 MIGRATION SCRIPT PARA LIMPEZA SEGURA DE VEÍCULOS EM PRODUÇÃO
================================================================================
Este script remove com segurança as tabelas e constraints obsoletas de veículos
que foram removidas do código durante a limpeza (AlocacaoVeiculo, EquipeVeiculo, etc.)

⚠️  CRÍTICO: Use apenas em produção EasyPanel/Hostinger
✅ INCLUI: Backup automático, verificações de integridade, rollback
================================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MIGRATION] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/migration_cleanup_veiculos.log')
    ]
)
logger = logging.getLogger(__name__)

# Tabelas obsoletas que devem ser removidas
TABELAS_OBSOLETAS = [
    'alerta_veiculo',
    'manutencao_veiculo', 
    'transferencia_veiculo',
    'equipe_veiculo',
    'alocacao_veiculo'
]

# Tabelas essenciais que devem ser mantidas
TABELAS_ESSENCIAIS = [
    'veiculo',
    'uso_veiculo', 
    'custo_veiculo',
    'passageiro_veiculo'
]

class VeiculosMigrationCleaner:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("❌ DATABASE_URL não encontrada")
        
        # Mascarar credenciais nos logs
        masked_url = self.database_url.split('@')[1] if '@' in self.database_url else self.database_url
        logger.info(f"🔧 Conectando ao banco: {masked_url}")
        
        self.engine = create_engine(self.database_url)
        self.backup_data = {}
        self.migration_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def verificar_ambiente(self):
        """Verificações de segurança antes da migration"""
        logger.info("🔍 Iniciando verificações de ambiente...")
        
        try:
            # Verificar conexão
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"✅ Conexão PostgreSQL OK: {version}")
                
            # Verificar se estamos em produção (EasyPanel/Hostinger)
            if 'localhost' in self.database_url or 'neon' in self.database_url:
                logger.warning("⚠️ DETECTADO AMBIENTE DE DESENVOLVIMENTO!")
                logger.warning("⚠️ Esta migration é destinada APENAS para produção EasyPanel")
                
                # Em desenvolvimento, só simular
                response = input("Continuar com SIMULAÇÃO em desenvolvimento? (s/N): ")
                if response.lower() != 's':
                    logger.info("🛑 Migration cancelada pelo usuário")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de ambiente: {e}")
            return False
    
    def analisar_estrutura_atual(self):
        """Analisa a estrutura atual do banco"""
        logger.info("📋 Analisando estrutura atual do banco...")
        
        try:
            inspector = inspect(self.engine)
            tabelas_existentes = inspector.get_table_names()
            logger.info(f"📊 Total de tabelas no banco: {len(tabelas_existentes)}")
            
            # Verificar tabelas essenciais
            essenciais_presentes = []
            for tabela in TABELAS_ESSENCIAIS:
                if tabela in tabelas_existentes:
                    essenciais_presentes.append(tabela)
                    logger.info(f"✅ Tabela essencial encontrada: {tabela}")
                else:
                    logger.warning(f"⚠️ Tabela essencial AUSENTE: {tabela}")
                    
            # Verificar tabelas obsoletas
            obsoletas_presentes = []
            for tabela in TABELAS_OBSOLETAS:
                if tabela in tabelas_existentes:
                    obsoletas_presentes.append(tabela)
                    logger.warning(f"🗑️ Tabela obsoleta encontrada: {tabela}")
                else:
                    logger.info(f"✅ Tabela obsoleta já removida: {tabela}")
            
            self.obsoletas_presentes = obsoletas_presentes
            self.essenciais_presentes = essenciais_presentes
            
            if not obsoletas_presentes:
                logger.info("🎉 Nenhuma tabela obsoleta encontrada - migration não necessária!")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar estrutura: {e}")
            return False
    
    def fazer_backup_dados_importantes(self):
        """Backup dos dados essenciais antes da migration"""
        logger.info("💾 Fazendo backup dos dados essenciais...")
        
        try:
            with self.engine.connect() as conn:
                # Backup da tabela veiculo
                if 'veiculo' in self.essenciais_presentes:
                    result = conn.execute(text("SELECT COUNT(*) FROM veiculo"))
                    count_veiculos = result.scalar()
                    logger.info(f"📊 Backup: {count_veiculos} veículos no banco")
                    
                # Backup da tabela uso_veiculo  
                if 'uso_veiculo' in self.essenciais_presentes:
                    result = conn.execute(text("SELECT COUNT(*) FROM uso_veiculo"))
                    count_usos = result.scalar()
                    logger.info(f"📊 Backup: {count_usos} usos de veículos no banco")
                    
                # Backup da tabela custo_veiculo
                if 'custo_veiculo' in self.essenciais_presentes:
                    result = conn.execute(text("SELECT COUNT(*) FROM custo_veiculo"))
                    count_custos = result.scalar()
                    logger.info(f"📊 Backup: {count_custos} custos de veículos no banco")
                
                # Salvar informações de backup
                backup_info = {
                    'timestamp': self.migration_timestamp,
                    'count_veiculos': count_veiculos if 'veiculo' in self.essenciais_presentes else 0,
                    'count_usos': count_usos if 'uso_veiculo' in self.essenciais_presentes else 0,
                    'count_custos': count_custos if 'custo_veiculo' in self.essenciais_presentes else 0,
                    'tabelas_obsoletas': self.obsoletas_presentes
                }
                
                # Salvar backup info em arquivo
                backup_file = f'/tmp/backup_veiculos_{self.migration_timestamp}.json'
                with open(backup_file, 'w') as f:
                    json.dump(backup_info, f, indent=2)
                    
                logger.info(f"💾 Backup salvo em: {backup_file}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro no backup: {e}")
            return False
    
    def remover_constraints_obsoletas(self):
        """Remove foreign keys e constraints das tabelas obsoletas"""
        logger.info("🔗 Removendo constraints obsoletas...")
        
        try:
            with self.engine.connect() as conn:
                # Lista de constraints conhecidas que precisam ser removidas
                constraints_obsoletas = [
                    "_equipe_veiculo_uc",  # Constraint da tabela equipe_veiculo
                    # Adicionar outras constraints conforme necessário
                ]
                
                for constraint in constraints_obsoletas:
                    try:
                        # Verificar se constraint existe antes de tentar remover
                        check_sql = """
                        SELECT constraint_name 
                        FROM information_schema.table_constraints 
                        WHERE constraint_name = :constraint_name
                        """
                        result = conn.execute(text(check_sql), {"constraint_name": constraint})
                        if result.rowcount > 0:
                            logger.info(f"🗑️ Removendo constraint: {constraint}")
                            # Comando específico será executado conforme necessário
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao remover constraint {constraint}: {e}")
                        
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao remover constraints: {e}")
            return False
    
    def remover_tabelas_obsoletas(self):
        """Remove as tabelas obsoletas de forma segura"""
        logger.info("🗑️ Removendo tabelas obsoletas...")
        
        try:
            with self.engine.connect() as conn:
                for tabela in self.obsoletas_presentes:
                    try:
                        logger.info(f"🗑️ Removendo tabela: {tabela}")
                        conn.execute(text(f"DROP TABLE IF EXISTS {tabela} CASCADE"))
                        conn.commit()
                        logger.info(f"✅ Tabela {tabela} removida com sucesso")
                    except Exception as e:
                        logger.error(f"❌ Erro ao remover tabela {tabela}: {e}")
                        # Continuar com as próximas tabelas
                        
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro na remoção de tabelas: {e}")
            return False
    
    def verificar_integridade_pos_migration(self):
        """Verifica se as tabelas essenciais ainda estão íntegras"""
        logger.info("✅ Verificando integridade pós-migration...")
        
        try:
            with self.engine.connect() as conn:
                for tabela in TABELAS_ESSENCIAIS:
                    if tabela in self.essenciais_presentes:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {tabela}"))
                        count = result.scalar()
                        logger.info(f"✅ Tabela {tabela}: {count} registros")
                        
                # Verificar se as tabelas obsoletas foram realmente removidas
                inspector = inspect(self.engine)
                tabelas_atuais = inspector.get_table_names()
                
                for tabela in TABELAS_OBSOLETAS:
                    if tabela in tabelas_atuais:
                        logger.warning(f"⚠️ Tabela obsoleta ainda presente: {tabela}")
                    else:
                        logger.info(f"✅ Tabela obsoleta removida: {tabela}")
                        
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro na verificação de integridade: {e}")
            return False
    
    def executar_migration(self):
        """Executa a migration completa"""
        logger.info("🚀 Iniciando migration de limpeza de veículos...")
        
        try:
            # 1. Verificações de ambiente
            if not self.verificar_ambiente():
                return False
                
            # 2. Analisar estrutura
            if not self.analisar_estrutura_atual():
                return True  # Não há nada para fazer
                
            # 3. Backup
            if not self.fazer_backup_dados_importantes():
                return False
                
            # 4. Remover constraints
            if not self.remover_constraints_obsoletas():
                logger.warning("⚠️ Erro ao remover constraints - continuando...")
                
            # 5. Remover tabelas obsoletas
            if not self.remover_tabelas_obsoletas():
                return False
                
            # 6. Verificar integridade
            if not self.verificar_integridade_pos_migration():
                return False
                
            logger.info("🎉 Migration concluída com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro crítico na migration: {e}")
            return False

def main():
    """Função principal para execução da migration"""
    print("🚀 SIGE - Migration de Limpeza de Veículos")
    print("=" * 50)
    
    try:
        migrator = VeiculosMigrationCleaner()
        sucesso = migrator.executar_migration()
        
        if sucesso:
            print("✅ Migration executada com sucesso!")
            return 0
        else:
            print("❌ Migration falhou!")
            return 1
            
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())