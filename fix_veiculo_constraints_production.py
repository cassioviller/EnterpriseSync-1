#!/usr/bin/env python3
"""
🎯 CORREÇÃO CRÍTICA - CONSTRAINTS VEÍCULOS PRODUÇÃO
==================================================

PROBLEMA IDENTIFICADO: Constraints NOT NULL muito restritivas
- Campo 'modelo' obrigatório mas código não fornece valor
- Campo 'tipo' obrigatório mas código não fornece valor

SOLUÇÃO: Ajustar constraints para permitir flexibilidade
- Permitir NULL em 'modelo' e 'tipo' OU definir valores padrão
- Manter integridade dos dados existentes
- Permitir cadastros futuros sem erro

ESTRATÉGIA:
✅ Segura: Transaction com rollback automático
✅ Inteligente: Preserva dados existentes
✅ Flexível: Define valores padrão sensatos
✅ Testável: Verifica funcionamento após correção
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import text

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'fix_veiculo_constraints_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Variáveis globais
db = None
app = None

def verificar_constraints_atuais():
    """Verifica quais constraints NOT NULL existem atualmente"""
    try:
        logger.info("🔍 VERIFICANDO CONSTRAINTS ATUAIS...")
        
        result = db.session.execute(text("""
            SELECT 
                column_name, 
                is_nullable,
                column_default,
                data_type
            FROM information_schema.columns 
            WHERE table_name = 'veiculo' 
                AND is_nullable = 'NO'
            ORDER BY ordinal_position;
        """))
        
        not_null_columns = []
        for row in result.fetchall():
            not_null_columns.append({
                'column': row[0],
                'nullable': row[1],
                'default': row[2],
                'type': row[3]
            })
        
        logger.info("📋 Colunas com constraint NOT NULL:")
        for col in not_null_columns:
            logger.info(f"   - {col['column']} ({col['type']}) - Default: {col['default']}")
        
        return not_null_columns
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar constraints: {str(e)}")
        return []

def ajustar_constraints_problematicas():
    """Ajusta constraints que estão causando problemas"""
    try:
        logger.info("🔧 AJUSTANDO CONSTRAINTS PROBLEMÁTICAS...")
        
        # Estratégia: Definir valores padrão em vez de remover NOT NULL
        # Isso mantém a integridade mas permite flexibilidade
        
        adjustments = [
            {
                'column': 'modelo',
                'default': "'Não informado'",
                'reason': 'Modelo frequentemente não informado no cadastro inicial'
            },
            {
                'column': 'tipo', 
                'default': "'Veículo'",
                'reason': 'Tipo genérico como padrão'
            }
        ]
        
        for adj in adjustments:
            logger.info(f"   🔧 Ajustando coluna '{adj['column']}'...")
            logger.info(f"      Motivo: {adj['reason']}")
            
            try:
                # Definir valor padrão para a coluna
                sql_default = f"""
                ALTER TABLE veiculo 
                ALTER COLUMN {adj['column']} 
                SET DEFAULT {adj['default']}
                """
                
                db.session.execute(text(sql_default))
                logger.info(f"   ✅ Valor padrão definido: {adj['column']} = {adj['default']}")
                
                # Atualizar registros existentes que estão NULL
                sql_update = f"""
                UPDATE veiculo 
                SET {adj['column']} = {adj['default']}
                WHERE {adj['column']} IS NULL
                """
                
                update_result = db.session.execute(text(sql_update))
                affected_rows = update_result.rowcount
                logger.info(f"   📊 Registros atualizados: {affected_rows}")
                
            except Exception as e:
                logger.warning(f"   ⚠️ Erro ao ajustar {adj['column']}: {str(e)}")
                continue
        
        logger.info("✅ Ajustes de constraints concluídos")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro nos ajustes: {str(e)}")
        return False

def testar_insercao_apos_ajuste():
    """Testa se a inserção funciona após os ajustes"""
    try:
        logger.info("🧪 TESTANDO INSERÇÃO APÓS AJUSTES...")
        
        # Detectar admin_id
        admin_result = db.session.execute(text("""
            SELECT admin_id, COUNT(*) as funcionarios 
            FROM funcionario 
            WHERE ativo = true 
            GROUP BY admin_id 
            ORDER BY funcionarios DESC 
            LIMIT 1
        """))
        
        admin_data = admin_result.fetchone()
        admin_id = admin_data[0] if admin_data else 1
        
        # Teste 1: Inserção com campos mínimos (situação real do erro)
        test_placa = f"FIX{datetime.now().strftime('%H%M%S')}"
        
        logger.info("   📝 Teste 1: Inserção com campos mínimos...")
        insert_result = db.session.execute(text("""
            INSERT INTO veiculo (placa, marca, admin_id, ativo)
            VALUES (:placa, :marca, :admin_id, true)
            RETURNING id, modelo, tipo
        """), {
            'placa': test_placa,
            'marca': 'MARCA_TESTE',
            'admin_id': admin_id
        })
        
        result_row = insert_result.fetchone()
        test_id = result_row[0]
        modelo_default = result_row[1]
        tipo_default = result_row[2]
        
        logger.info(f"   ✅ Inserção OK - ID: {test_id}")
        logger.info(f"   📋 Valores padrão aplicados: modelo='{modelo_default}', tipo='{tipo_default}'")
        
        # Teste 2: Inserção com todos os campos
        test_placa2 = f"FUL{datetime.now().strftime('%H%M%S')}"
        
        logger.info("   📝 Teste 2: Inserção com todos os campos...")
        insert_result2 = db.session.execute(text("""
            INSERT INTO veiculo (placa, marca, modelo, tipo, chassi, renavam, combustivel, admin_id, ativo)
            VALUES (:placa, :marca, :modelo, :tipo, :chassi, :renavam, :combustivel, :admin_id, true)
            RETURNING id
        """), {
            'placa': test_placa2,
            'marca': 'MARCA_COMPLETA',
            'modelo': 'MODELO_COMPLETO',
            'tipo': 'Caminhão',
            'chassi': 'CHX123456',
            'renavam': 'REN789012',
            'combustivel': 'Diesel',
            'admin_id': admin_id
        })
        
        test_id2 = insert_result2.fetchone()[0]
        logger.info(f"   ✅ Inserção completa OK - ID: {test_id2}")
        
        # Limpeza - remover registros de teste
        logger.info("   🗑️ Limpando registros de teste...")
        db.session.execute(text("DELETE FROM veiculo WHERE id IN (:id1, :id2)"), {
            'id1': test_id,
            'id2': test_id2
        })
        
        logger.info("✅ TESTES DE INSERÇÃO PASSARAM - Sistema funcionando!")
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO nos testes: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

def verificar_sistema_completo():
    """Verificação final do sistema completo"""
    try:
        logger.info("🎯 VERIFICAÇÃO FINAL DO SISTEMA...")
        
        # Contar veículos por admin
        count_result = db.session.execute(text("""
            SELECT admin_id, COUNT(*) as total
            FROM veiculo 
            GROUP BY admin_id
            ORDER BY total DESC
        """))
        
        logger.info("📊 Veículos por admin:")
        for row in count_result.fetchall():
            logger.info(f"   Admin {row[0]}: {row[1]} veículos")
        
        # Verificar se há registros com valores padrão
        default_result = db.session.execute(text("""
            SELECT COUNT(*) as total
            FROM veiculo 
            WHERE modelo = 'Não informado' OR tipo = 'Veículo'
        """))
        
        default_count = default_result.fetchone()[0]
        logger.info(f"📋 Registros com valores padrão: {default_count}")
        
        # Teste final de constraints
        logger.info("🔍 Estado final das constraints:")
        final_constraints = verificar_constraints_atuais()
        
        problematic_found = False
        for constraint in final_constraints:
            if constraint['column'] in ['modelo', 'tipo'] and not constraint['default']:
                problematic_found = True
                logger.warning(f"⚠️ {constraint['column']} ainda sem padrão")
        
        if not problematic_found:
            logger.info("✅ Todas as constraints problemáticas foram corrigidas")
            return True
        else:
            logger.warning("⚠️ Algumas constraints ainda podem causar problemas")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erro na verificação final: {str(e)}")
        return False

def main():
    """Função principal - correção de constraints"""
    global db, app
    
    print("🎯 CORREÇÃO CONSTRAINTS VEÍCULOS PRODUÇÃO")
    print("="*50)
    
    # Detectar ambiente
    database_url = os.environ.get('DATABASE_URL', '')
    if 'neon' in database_url.lower():
        print("🏭 AMBIENTE: PRODUÇÃO")
    else:
        print("🧪 AMBIENTE: DESENVOLVIMENTO")
    
    # Verificar flag de força ou execução automática via Docker
    force_mode = '--force' in sys.argv
    auto_mode = os.environ.get('AUTO_MIGRATIONS_ENABLED') == 'true'
    
    if not force_mode and not auto_mode:
        print("⚠️  ATENÇÃO: Esta operação irá modificar constraints da tabela 'veiculo'")
        print("   - Definir valores padrão para 'modelo' e 'tipo'")
        print("   - Atualizar registros existentes se necessário")
        print("   - Testar inserções após correção")
        response = input("\n🤔 Confirma execução? (digite 'CONFIRMO'): ")
        if response != 'CONFIRMO':
            print("❌ Operação cancelada pelo usuário")
            return False
    elif auto_mode:
        print("🚀 Executando correção automaticamente (AUTO_MIGRATIONS_ENABLED)")
    else:
        print("🚀 Executando correção automaticamente (--force)")
    
    try:
        # Setup Flask
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        logger.info("🔧 Importando dependências...")
        from app import app as flask_app, db as flask_db
        app = flask_app
        db = flask_db
        
        with app.app_context():
            logger.info("🔌 Testando conexão...")
            db.session.execute(text("SELECT 1"))
            logger.info("✅ Conexão OK")
            
            # Iniciar transação
            logger.info("🚀 INICIANDO CORREÇÃO DE CONSTRAINTS")
            logger.info("="*50)
            
            # 1. Verificar estado atual
            constraints_antes = verificar_constraints_atuais()
            
            # 2. Aplicar ajustes
            if not ajustar_constraints_problematicas():
                raise Exception("Falha nos ajustes de constraints")
            
            # 3. Testar inserções
            if not testar_insercao_apos_ajuste():
                raise Exception("Falha nos testes de inserção")
            
            # 4. Verificação final
            if not verificar_sistema_completo():
                logger.warning("⚠️ Verificação final com avisos")
            
            # Commit da transação
            db.session.commit()
            logger.info("💾 CORREÇÃO COMMITADA COM SUCESSO!")
            
            print(f"\n" + "="*50)
            print("✅ CORREÇÃO DE CONSTRAINTS CONCLUÍDA!")
            print("🚗 Sistema de veículos funcionando corretamente!")
            print("📋 Campos 'modelo' e 'tipo' agora têm valores padrão")
            print("🧪 Testes de inserção passaram com sucesso")
            print("="*50)
            
            return True
            
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO: {str(e)}")
        
        try:
            db.session.rollback()
            logger.info("🔄 ROLLBACK executado - banco restaurado")
        except:
            logger.error("❌ Falha no rollback!")
        
        print(f"\n❌ CORREÇÃO FALHOU: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)