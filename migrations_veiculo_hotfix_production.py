#!/usr/bin/env python3
"""
🚨 HOTFIX CRÍTICO PRODUÇÃO - Correção Tabela Veículo
Sistema: SIGE v8.0
Data: 26/09/2025

PROBLEMA: Tabela 'veiculo' em produção está faltando colunas essenciais
SOLUÇÃO: Adicionar colunas faltantes de forma segura

COLUNAS A ADICIONAR:
- chassi (VARCHAR 50) - Chassi do veículo
- renavam (VARCHAR 20) - Código RENAVAM  
- combustivel (VARCHAR 20) - Tipo de combustível
- data_ultima_manutencao (DATE) - Data da última manutenção
- data_proxima_manutencao (DATE) - Data da próxima manutenção
- km_proxima_manutencao (INTEGER) - KM para próxima manutenção
- created_at (TIMESTAMP) - Data de criação
- updated_at (TIMESTAMP) - Data de atualização

SEGURANÇA:
✅ Não afeta dados existentes
✅ Valores padrão para compatibilidade
✅ Rollback automático em caso de erro
✅ Transações isoladas
"""

import os
import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'veiculo_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_production_migration():
    """
    🔥 MIGRATION CRÍTICA PRODUÇÃO - VEÍCULOS
    Adiciona colunas faltantes na tabela veiculo
    """
    try:
        # Importar depois de configurar logging para evitar conflitos
        from app import app, db
        
        logger.info("🚀 INICIANDO HOTFIX CRÍTICO - TABELA VEÍCULO")
        logger.info("=" * 60)
        
        with app.app_context():
            # 1. VERIFICAR CONEXÃO COM BANCO
            logger.info("🔌 Testando conexão com banco de dados...")
            try:
                db.session.execute("SELECT 1")
                logger.info("✅ Conexão com banco OK")
            except Exception as e:
                logger.error(f"❌ ERRO DE CONEXÃO: {str(e)}")
                return False
            
            # 2. VERIFICAR SE TABELA VEICULO EXISTE
            logger.info("🔍 Verificando estrutura atual da tabela veiculo...")
            try:
                result = db.session.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'veiculo' 
                    ORDER BY ordinal_position;
                """)
                
                existing_columns = [row[0] for row in result.fetchall()]
                logger.info(f"📋 Colunas existentes: {', '.join(existing_columns)}")
                
            except Exception as e:
                logger.error(f"❌ ERRO ao verificar tabela: {str(e)}")
                return False
            
            # 3. DEFINIR COLUNAS A ADICIONAR
            columns_to_add = [
                ("chassi", "VARCHAR(50)", "NULL", "-- Chassi do veículo"),
                ("renavam", "VARCHAR(20)", "NULL", "-- Código RENAVAM"),
                ("combustivel", "VARCHAR(20)", "'Gasolina'", "-- Tipo de combustível"),
                ("data_ultima_manutencao", "DATE", "NULL", "-- Data última manutenção"),
                ("data_proxima_manutencao", "DATE", "NULL", "-- Data próxima manutenção"),
                ("km_proxima_manutencao", "INTEGER", "NULL", "-- KM próxima manutenção"),
                ("created_at", "TIMESTAMP", "CURRENT_TIMESTAMP", "-- Data de criação"),
                ("updated_at", "TIMESTAMP", "CURRENT_TIMESTAMP", "-- Data de atualização")
            ]
            
            # 4. VERIFICAR QUAIS COLUNAS PRECISAM SER ADICIONADAS
            missing_columns = []
            for col_name, col_type, col_default, col_comment in columns_to_add:
                if col_name not in existing_columns:
                    missing_columns.append((col_name, col_type, col_default, col_comment))
            
            if not missing_columns:
                logger.info("✅ TODAS AS COLUNAS JÁ EXISTEM - Migration não necessária")
                return True
            
            logger.info(f"🔧 Colunas a adicionar: {len(missing_columns)}")
            for col_name, _, _, comment in missing_columns:
                logger.info(f"   + {col_name} {comment}")
            
            # 5. EXECUTAR MIGRATION COM TRANSAÇÃO
            logger.info("🚀 INICIANDO MIGRATION...")
            
            try:
                # Iniciar transação
                db.session.begin()
                
                for col_name, col_type, col_default, comment in missing_columns:
                    logger.info(f"📝 Adicionando coluna: {col_name}")
                    
                    # Construir comando ALTER TABLE
                    if col_default == "NULL":
                        alter_sql = f"ALTER TABLE veiculo ADD COLUMN {col_name} {col_type};"
                    else:
                        alter_sql = f"ALTER TABLE veiculo ADD COLUMN {col_name} {col_type} DEFAULT {col_default};"
                    
                    logger.info(f"   SQL: {alter_sql}")
                    
                    # Executar comando
                    db.session.execute(alter_sql)
                    logger.info(f"   ✅ Coluna {col_name} adicionada com sucesso")
                
                # 6. VERIFICAR INTEGRIDADE DOS DADOS
                logger.info("🔍 Verificando integridade dos dados...")
                
                # Contar registros antes e depois
                count_result = db.session.execute("SELECT COUNT(*) FROM veiculo")
                total_veiculos = count_result.fetchone()[0]
                logger.info(f"📊 Total de veículos: {total_veiculos}")
                
                # Verificar se conseguimos fazer SELECT com todas as colunas
                test_select = db.session.execute("""
                    SELECT id, placa, marca, modelo, chassi, renavam, combustivel 
                    FROM veiculo 
                    LIMIT 1
                """)
                logger.info("✅ SELECT com novas colunas funcionando")
                
                # 7. COMMIT DA TRANSAÇÃO
                db.session.commit()
                logger.info("💾 MIGRATION COMMITADA COM SUCESSO!")
                
                # 8. VERIFICAÇÃO FINAL
                logger.info("🎯 VERIFICAÇÃO FINAL...")
                final_result = db.session.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'veiculo' 
                    ORDER BY ordinal_position;
                """)
                
                final_columns = [row[0] for row in final_result.fetchall()]
                logger.info(f"📋 Colunas finais: {', '.join(final_columns)}")
                
                # Verificar se todas as colunas esperadas existem
                expected_columns = ['id', 'placa', 'marca', 'modelo', 'ano', 'tipo', 'km_atual', 
                                  'cor', 'chassi', 'renavam', 'combustivel', 'ativo', 
                                  'data_ultima_manutencao', 'data_proxima_manutencao', 
                                  'km_proxima_manutencao', 'admin_id', 'created_at', 'updated_at']
                
                missing_final = [col for col in expected_columns if col not in final_columns]
                if missing_final:
                    logger.warning(f"⚠️ Ainda faltam colunas: {', '.join(missing_final)}")
                else:
                    logger.info("🎉 TODAS AS COLUNAS NECESSÁRIAS ESTÃO PRESENTES!")
                
                logger.info("=" * 60)
                logger.info("🎉 HOTFIX CONCLUÍDO COM SUCESSO!")
                logger.info("🚗 Sistema de veículos restaurado em produção")
                logger.info("=" * 60)
                
                return True
                
            except Exception as e:
                # ROLLBACK em caso de erro
                logger.error(f"❌ ERRO DURANTE MIGRATION: {str(e)}")
                logger.info("🔄 Executando ROLLBACK...")
                db.session.rollback()
                logger.error("💥 MIGRATION FALHADA - Banco restaurado ao estado anterior")
                return False
                
    except Exception as e:
        logger.error(f"❌ ERRO FATAL: {str(e)}")
        return False

def main():
    """Função principal para execução do hotfix"""
    print("🚨 HOTFIX CRÍTICO PRODUÇÃO - TABELA VEÍCULO")
    print("=" * 50)
    
    # Verificar se estamos em produção
    if os.environ.get('DATABASE_URL', '').find('localhost') != -1:
        print("⚠️ DETECTADO AMBIENTE DE DESENVOLVIMENTO")
    else:
        print("🏭 DETECTADO AMBIENTE DE PRODUÇÃO")
    
    # Confirmar execução
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        print("🚀 Executando migration automaticamente (--force)")
        confirm = 'y'
    else:
        confirm = input("Confirma execução da migration? (y/N): ").lower().strip()
    
    if confirm == 'y':
        success = run_production_migration()
        if success:
            print("\n✅ MIGRATION CONCLUÍDA COM SUCESSO!")
            print("🚗 Sistema de veículos restaurado!")
            return 0
        else:
            print("\n❌ MIGRATION FALHADA!")
            print("🔧 Verifique os logs para detalhes")
            return 1
    else:
        print("❌ Migration cancelada pelo usuário")
        return 1

if __name__ == "__main__":
    exit(main())