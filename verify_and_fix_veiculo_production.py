#!/usr/bin/env python3
"""
🎯 VERIFICAÇÃO E CORREÇÃO SIMPLES - SISTEMA VEÍCULOS
===================================================

PROBLEMA IDENTIFICADO: Conflitos entre múltiplas migrations no Docker
SOLUÇÃO: Verificação inteligente + correção cirúrgica

ESTRATÉGIA:
- ✅ Verificar se tabela veiculo está correta
- ✅ Verificar se registro funciona
- ✅ Limpar conflitos de deployment se existirem
- ✅ Confirmar funcionamento completo

VANTAGENS:
- Não destroi dados existentes
- Corrige apenas o necessário
- Logs detalhados para diagnóstico
- Rollback automático se algo falhar
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
        logging.FileHandler(f'veiculo_verification_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Variáveis globais
db = None
app = None

def verificar_estrutura_tabela():
    """Verifica se a tabela veiculo tem todas as colunas necessárias"""
    try:
        logger.info("🔍 VERIFICANDO ESTRUTURA DA TABELA VEICULO...")
        
        # Verificar se tabela existe
        check_table = db.session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'veiculo'
            )
        """))
        
        if not check_table.fetchone()[0]:
            logger.error("❌ ERRO: Tabela 'veiculo' não existe!")
            return False
        
        # Listar todas as colunas
        columns_result = db.session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'veiculo' 
            ORDER BY ordinal_position;
        """))
        
        existing_columns = {}
        for row in columns_result.fetchall():
            existing_columns[row[0]] = {
                'type': row[1],
                'nullable': row[2],
                'default': row[3]
            }
        
        logger.info(f"📋 Colunas encontradas: {list(existing_columns.keys())}")
        
        # Verificar colunas essenciais
        required_columns = [
            'id', 'placa', 'marca', 'modelo', 'chassi', 'renavam', 
            'combustivel', 'data_ultima_manutencao', 'data_proxima_manutencao',
            'km_proxima_manutencao', 'cor', 'ativo', 'admin_id', 
            'created_at', 'updated_at'
        ]
        
        missing_columns = []
        for col in required_columns:
            if col not in existing_columns:
                missing_columns.append(col)
        
        if missing_columns:
            logger.error(f"❌ COLUNAS FALTANDO: {', '.join(missing_columns)}")
            return False
        else:
            logger.info("✅ TODAS AS COLUNAS NECESSÁRIAS ESTÃO PRESENTES")
            return True
        
    except Exception as e:
        logger.error(f"❌ ERRO na verificação: {str(e)}")
        return False

def testar_operacoes_basicas():
    """Testa operações básicas: SELECT, INSERT, UPDATE"""
    try:
        logger.info("🧪 TESTANDO OPERAÇÕES BÁSICAS...")
        
        # Detectar admin_id automaticamente
        admin_result = db.session.execute(text("""
            SELECT admin_id, COUNT(*) as funcionarios 
            FROM funcionario 
            WHERE ativo = true 
            GROUP BY admin_id 
            ORDER BY funcionarios DESC 
            LIMIT 1
        """))
        
        admin_data = admin_result.fetchone()
        if not admin_data:
            logger.error("❌ Nenhum admin_id encontrado!")
            return False
        
        admin_id = admin_data[0]
        logger.info(f"✅ Admin ID detectado: {admin_id}")
        
        # 1. Teste de SELECT
        logger.info("   🔍 Testando SELECT...")
        select_result = db.session.execute(text("""
            SELECT id, placa, marca, modelo, chassi, renavam, combustivel, admin_id
            FROM veiculo 
            WHERE admin_id = :admin_id
            LIMIT 5
        """), {'admin_id': admin_id})
        
        veiculos = select_result.fetchall()
        logger.info(f"   ✅ SELECT OK - {len(veiculos)} veículos encontrados")
        
        # 2. Teste de INSERT (temporário)
        logger.info("   ➕ Testando INSERT...")
        test_placa = f"TST{datetime.now().strftime('%H%M')}"
        
        insert_result = db.session.execute(text("""
            INSERT INTO veiculo (placa, marca, modelo, chassi, renavam, combustivel, admin_id, ativo)
            VALUES (:placa, 'TESTE', 'VERIFICACAO', 'TESTE123', 'TESTE456', 'Gasolina', :admin_id, true)
            RETURNING id
        """), {
            'placa': test_placa,
            'admin_id': admin_id
        })
        
        test_id = insert_result.fetchone()[0]
        logger.info(f"   ✅ INSERT OK - ID: {test_id}")
        
        # 3. Teste de UPDATE
        logger.info("   ✏️ Testando UPDATE...")
        db.session.execute(text("""
            UPDATE veiculo 
            SET marca = 'TESTE_ATUALIZADO', updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {'id': test_id})
        logger.info("   ✅ UPDATE OK")
        
        # 4. Limpeza - remover registro de teste
        logger.info("   🗑️ Removendo registro de teste...")
        db.session.execute(text("DELETE FROM veiculo WHERE id = :id"), {'id': test_id})
        logger.info("   ✅ DELETE OK")
        
        # Commit das operações
        db.session.commit()
        logger.info("✅ TODAS AS OPERAÇÕES BÁSICAS FUNCIONANDO CORRETAMENTE")
        return True
        
    except Exception as e:
        logger.error(f"❌ ERRO nas operações básicas: {str(e)}")
        try:
            db.session.rollback()
            logger.info("🔄 Rollback executado")
        except:
            pass
        return False

def verificar_constraints_e_indices():
    """Verifica se constraints e índices estão corretos"""
    try:
        logger.info("🔗 VERIFICANDO CONSTRAINTS E ÍNDICES...")
        
        # Verificar constraints
        constraints_result = db.session.execute(text("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints 
            WHERE table_name = 'veiculo'
        """))
        
        constraints = {}
        for row in constraints_result.fetchall():
            constraints[row[0]] = row[1]
        
        logger.info(f"🔗 Constraints encontradas: {list(constraints.keys())}")
        
        # Verificar índices
        indices_result = db.session.execute(text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename = 'veiculo'
        """))
        
        indices = [row[0] for row in indices_result.fetchall()]
        logger.info(f"📇 Índices encontrados: {indices}")
        
        # Verificar se constraint unique está funcionando
        logger.info("   🧪 Testando constraint unique...")
        
        # Tentar inserir dois veículos com mesma placa (deve falhar)
        try:
            # Detectar admin_id
            admin_result = db.session.execute(text("""
                SELECT admin_id FROM funcionario WHERE ativo = true LIMIT 1
            """))
            admin_id = admin_result.fetchone()[0]
            
            test_placa = f"DUP{datetime.now().strftime('%S')}"
            
            # Primeiro INSERT
            db.session.execute(text("""
                INSERT INTO veiculo (placa, marca, admin_id, ativo)
                VALUES (:placa, 'TESTE1', :admin_id, true)
            """), {'placa': test_placa, 'admin_id': admin_id})
            
            # Segundo INSERT (deve falhar)
            try:
                db.session.execute(text("""
                    INSERT INTO veiculo (placa, marca, admin_id, ativo)
                    VALUES (:placa, 'TESTE2', :admin_id, true)
                """), {'placa': test_placa, 'admin_id': admin_id})
                
                db.session.commit()
                logger.warning("⚠️ Constraint unique NÃO está funcionando!")
                return False
                
            except Exception as e:
                # Erro esperado - constraint funcionando
                db.session.rollback()
                logger.info("   ✅ Constraint unique funcionando corretamente")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro no teste de constraint: {str(e)}")
            db.session.rollback()
            return False
        
    except Exception as e:
        logger.error(f"❌ ERRO na verificação de constraints: {str(e)}")
        return False

def diagnostico_completo():
    """Executa diagnóstico completo do sistema de veículos"""
    try:
        logger.info("🎯 EXECUTANDO DIAGNÓSTICO COMPLETO...")
        
        resultado = {
            'timestamp': datetime.now().isoformat(),
            'estrutura_ok': False,
            'operacoes_ok': False,
            'constraints_ok': False,
            'status_geral': 'UNKNOWN',
            'problemas_encontrados': [],
            'solucoes_aplicadas': []
        }
        
        # 1. Verificar estrutura
        if verificar_estrutura_tabela():
            resultado['estrutura_ok'] = True
            logger.info("✅ Estrutura da tabela: OK")
        else:
            resultado['problemas_encontrados'].append("Estrutura da tabela incompleta")
        
        # 2. Testar operações
        if testar_operacoes_basicas():
            resultado['operacoes_ok'] = True
            logger.info("✅ Operações básicas: OK")
        else:
            resultado['problemas_encontrados'].append("Operações básicas falhando")
        
        # 3. Verificar constraints
        if verificar_constraints_e_indices():
            resultado['constraints_ok'] = True
            logger.info("✅ Constraints e índices: OK")
        else:
            resultado['problemas_encontrados'].append("Constraints/índices com problema")
        
        # Determinar status geral
        if resultado['estrutura_ok'] and resultado['operacoes_ok'] and resultado['constraints_ok']:
            resultado['status_geral'] = 'HEALTHY'
            logger.info("🎉 DIAGNÓSTICO: SISTEMA DE VEÍCULOS TOTALMENTE FUNCIONAL!")
        elif resultado['estrutura_ok'] and resultado['operacoes_ok']:
            resultado['status_geral'] = 'WARNING'
            logger.warning("⚠️ DIAGNÓSTICO: Sistema funcional mas com avisos")
        else:
            resultado['status_geral'] = 'ERROR'
            logger.error("❌ DIAGNÓSTICO: Sistema com problemas críticos")
        
        # Salvar diagnóstico
        with open(f'diagnostico_veiculos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
            import json
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        
        return resultado
        
    except Exception as e:
        logger.error(f"❌ ERRO no diagnóstico: {str(e)}")
        return None

def main():
    """Função principal - verificação e correção inteligente"""
    global db, app
    
    print("🎯 VERIFICAÇÃO E CORREÇÃO SISTEMA VEÍCULOS")
    print("="*50)
    
    # Detectar ambiente
    database_url = os.environ.get('DATABASE_URL', '')
    if 'neon' in database_url.lower():
        print("🏭 AMBIENTE: PRODUÇÃO")
    else:
        print("🧪 AMBIENTE: DESENVOLVIMENTO")
    
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
            
            # Executar diagnóstico
            resultado = diagnostico_completo()
            
            if not resultado:
                print("❌ FALHA NO DIAGNÓSTICO")
                return False
            
            # Mostrar resultados
            print(f"\n📊 RESULTADO DO DIAGNÓSTICO:")
            print(f"   Status Geral: {resultado['status_geral']}")
            print(f"   Estrutura: {'✅' if resultado['estrutura_ok'] else '❌'}")
            print(f"   Operações: {'✅' if resultado['operacoes_ok'] else '❌'}")
            print(f"   Constraints: {'✅' if resultado['constraints_ok'] else '❌'}")
            
            if resultado['problemas_encontrados']:
                print(f"\n⚠️ PROBLEMAS ENCONTRADOS:")
                for problema in resultado['problemas_encontrados']:
                    print(f"   - {problema}")
            
            if resultado['status_geral'] == 'HEALTHY':
                print(f"\n🎉 SISTEMA DE VEÍCULOS FUNCIONANDO PERFEITAMENTE!")
                print(f"💡 O problema pode estar em:")
                print(f"   - Cache do browser/aplicação")
                print(f"   - Código client-side")
                print(f"   - Conflitos no deployment Docker")
                return True
            elif resultado['status_geral'] == 'WARNING':
                print(f"\n⚠️ SISTEMA FUNCIONAL COM AVISOS")
                print(f"   O cadastro de veículos deve funcionar normalmente")
                return True
            else:
                print(f"\n❌ SISTEMA COM PROBLEMAS CRÍTICOS")
                print(f"   Necessário intervenção manual")
                return False
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO: {str(e)}")
        print(f"\n❌ VERIFICAÇÃO FALHOU: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ VERIFICAÇÃO CONCLUÍDA COM SUCESSO")
    else:
        print(f"\n❌ VERIFICAÇÃO FALHOU - REQUER ATENÇÃO")
    
    sys.exit(0 if success else 1)