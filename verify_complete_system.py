#!/usr/bin/env python3
"""
🔍 VERIFICADOR COMPLETO DO SISTEMA - SIGE v10.0
============================================
Sistema completo de verificação para validar funcionalidades do sistema de veículos.
Executa testes estruturados para garantir integridade das tabelas e relacionamentos.

Autor: Sistema SIGE v10.0
Data: 2025-01-19
Versão: 1.0.0 - Implementação conforme especificações técnicas
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError, DatabaseError


def test_complete_system(database_url: str) -> Dict[str, Any]:
    """
    Função principal do verificador completo do sistema.
    
    Args:
        database_url: URL de conexão com o banco de dados PostgreSQL
        
    Returns:
        Dict com resultados detalhados dos testes
    """
    
    # ============================================================
    # 1. CONFIGURAÇÃO INICIAL - LOGGING E CONEXÃO
    # ============================================================
    
    # Configurar logging conforme especificação
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 INICIANDO VERIFICADOR COMPLETO DO SISTEMA - SIGE v10.0")
    logger.info("=" * 70)
    logger.info(f"⏰ Início da verificação: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔗 Database URL: {_mask_database_url(database_url)}")
    
    # Estatísticas globais
    stats = {
        'inicio': datetime.now(),
        'total_testes': 0,
        'sucessos': 0,
        'falhas': 0,
        'tests_details': [],
        'failed_tests': [],
        'status_final': 'UNKNOWN',
        'recomendacoes': []
    }
    
    # ============================================================
    # 2. DEFINIÇÃO DO ARRAY DE TESTES ESTRUTURADOS
    # ============================================================
    
    tests_array = [
        {
            'name': 'Estrutura tabela uso_veiculo',
            'sql': "SELECT column_name FROM information_schema.columns WHERE table_name = 'uso_veiculo' ORDER BY column_name;",
            'expected_count': 21,
            'description': 'Verificar se tabela uso_veiculo possui pelo menos 21 colunas conforme especificação',
            'critical': True
        },
        {
            'name': 'Query uso_veiculo com admin_id',
            'sql': "SELECT id, admin_id, porcentagem_combustivel FROM uso_veiculo LIMIT 1;",
            'expected_count': None,
            'description': 'Confirmar que query problemática original com admin_id agora funciona sem erros',
            'critical': True
        },
        {
            'name': 'Estrutura tabela custo_veiculo',
            'sql': "SELECT column_name FROM information_schema.columns WHERE table_name = 'custo_veiculo' ORDER BY column_name;",
            'expected_count': 12,
            'description': 'Verificar se tabela custo_veiculo possui pelo menos 12 colunas conforme especificação',
            'critical': True
        },
        {
            'name': 'JOIN entre tabelas de veículos',
            'sql': """
                SELECT 
                    v.id as veiculo_id,
                    v.placa,
                    uv.id as uso_id,
                    uv.admin_id,
                    cv.id as custo_id,
                    cv.tipo_custo
                FROM veiculo v
                LEFT JOIN uso_veiculo uv ON v.id = uv.veiculo_id
                LEFT JOIN custo_veiculo cv ON v.id = cv.veiculo_id
                LIMIT 5;
            """,
            'expected_count': None,
            'description': 'Testar integridade referencial e relacionamentos entre tabelas de veículos',
            'critical': True
        },
        {
            'name': 'Verificação colunas críticas uso_veiculo',
            'sql': """
                SELECT 
                    CASE WHEN COUNT(*) >= 21 THEN 'PASS' ELSE 'FAIL' END as status,
                    COUNT(*) as total_colunas
                FROM information_schema.columns 
                WHERE table_name = 'uso_veiculo';
            """,
            'expected_count': None,
            'description': 'Verificação detalhada de contagem de colunas em uso_veiculo',
            'critical': False
        },
        {
            'name': 'Verificação admin_id em todas as tabelas de veículos',
            'sql': """
                SELECT 
                    table_name as tabela,
                    'PRESENTE' as status
                FROM information_schema.columns 
                WHERE table_name IN ('veiculo', 'uso_veiculo', 'custo_veiculo') 
                AND column_name = 'admin_id'
                ORDER BY table_name;
            """,
            'expected_count': 3,
            'description': 'Verificar presença de campo admin_id para multi-tenant em todas as tabelas',
            'critical': False
        }
    ]
    
    logger.info(f"📋 Total de testes definidos: {len(tests_array)}")
    stats['total_testes'] = len(tests_array)
    
    # ============================================================
    # 3. CONEXÃO COM BANCO DE DADOS
    # ============================================================
    
    try:
        logger.info("🔌 Estabelecendo conexão com banco de dados...")
        engine = create_engine(
            database_url,
            pool_pre_ping=True,  # Verificar conexão antes de usar
            pool_recycle=300,    # Renovar conexão a cada 5 minutos
            echo=False           # Não logar SQL para manter logs limpos
        )
        
        # Testar conexão
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()
            if test_result[0] != 1:
                raise Exception("Falha no teste básico de conexão")
                
        logger.info("✅ Conexão com banco estabelecida com sucesso")
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO: Falha ao conectar com banco de dados: {e}")
        stats['status_final'] = 'CRITICAL_ERROR'
        stats['recomendacoes'].append("Verificar conectividade e credenciais do banco de dados")
        return _finalize_results(stats)
    
    # ============================================================
    # 4. EXECUÇÃO DOS TESTES EM LOOP
    # ============================================================
    
    logger.info("🚀 Iniciando execução dos testes...")
    logger.info("-" * 70)
    
    for i, test in enumerate(tests_array, 1):
        logger.info(f"🔄 Teste {i}/{len(tests_array)}: {test['name']}")
        logger.info(f"📝 Descrição: {test['description']}")
        
        test_result = _execute_single_test(engine, test, logger)
        
        # Registrar resultado
        stats['tests_details'].append(test_result)
        
        if test_result['success']:
            stats['sucessos'] += 1
            logger.info(f"✅ SUCESSO: {test['name']}")
        else:
            stats['falhas'] += 1
            stats['failed_tests'].append(test_result)
            level = "ERROR" if test.get('critical', False) else "WARNING"
            logger.log(getattr(logging, level), f"❌ FALHA: {test['name']} - {test_result['error']}")
        
        if test_result.get('details'):
            logger.info(f"📊 Detalhes: {test_result['details']}")
            
        logger.info("-" * 50)
    
    # ============================================================
    # 5. ANÁLISE E RELATÓRIO FINAL
    # ============================================================
    
    logger.info("📊 GERANDO RELATÓRIO FINAL...")
    logger.info("=" * 70)
    
    # Calcular status final
    if stats['falhas'] == 0:
        stats['status_final'] = 'PASS'
    elif any(t.get('critical', False) for t in stats['failed_tests']):
        stats['status_final'] = 'CRITICAL_FAIL'
    else:
        stats['status_final'] = 'PARTIAL_FAIL'
    
    # Gerar recomendações baseadas nos resultados
    _generate_recommendations(stats)
    
    # Log do relatório final
    logger.info(f"⏱️  Tempo de execução: {datetime.now() - stats['inicio']}")
    logger.info(f"📈 Estatísticas:")
    logger.info(f"   • Total de testes: {stats['total_testes']}")
    logger.info(f"   • Sucessos: {stats['sucessos']}")
    logger.info(f"   • Falhas: {stats['falhas']}")
    logger.info(f"   • Taxa de sucesso: {(stats['sucessos']/stats['total_testes']*100):.1f}%")
    logger.info(f"🏁 STATUS FINAL: {stats['status_final']}")
    
    if stats['failed_tests']:
        logger.info("❌ TESTES QUE FALHARAM:")
        for failed in stats['failed_tests']:
            logger.info(f"   • {failed['test_name']}: {failed['error']}")
    
    if stats['recomendacoes']:
        logger.info("💡 RECOMENDAÇÕES:")
        for rec in stats['recomendacoes']:
            logger.info(f"   • {rec}")
    
    logger.info("=" * 70)
    logger.info("🔍 VERIFICAÇÃO COMPLETA FINALIZADA")
    
    return _finalize_results(stats)


def _execute_single_test(engine, test: Dict[str, Any], logger) -> Dict[str, Any]:
    """
    Executa um teste individual com tratamento robusto de erros.
    
    Args:
        engine: Engine SQLAlchemy
        test: Dicionário com definição do teste
        logger: Logger para output
        
    Returns:
        Dict com resultado do teste
    """
    result = {
        'test_name': test['name'],
        'success': False,
        'error': None,
        'details': None,
        'row_count': 0,
        'execution_time': None
    }
    
    start_time = datetime.now()
    
    try:
        with engine.connect() as conn:
            # Executar SQL do teste
            sql_result = conn.execute(text(test['sql']))
            rows = sql_result.fetchall()
            result['row_count'] = len(rows)
            
            # Verificar condições específicas do teste
            if test['expected_count'] is not None:
                # Teste que espera um count específico
                if result['row_count'] >= test['expected_count']:
                    result['success'] = True
                    result['details'] = f"Encontradas {result['row_count']} linhas (mínimo {test['expected_count']})"
                else:
                    result['error'] = f"Encontradas apenas {result['row_count']} linhas, esperado mínimo {test['expected_count']}"
            else:
                # Teste que apenas verifica se executa sem erro
                result['success'] = True
                result['details'] = f"Query executada com sucesso, {result['row_count']} linhas retornadas"
                
                # Para alguns testes, verificar conteúdo específico
                if 'admin_id' in test['sql'] and result['row_count'] > 0:
                    # Verificar se admin_id está presente nos resultados
                    first_row = rows[0]
                    if hasattr(first_row, 'admin_id') or 'admin_id' in first_row._asdict():
                        result['details'] += " - Campo admin_id encontrado"
                    else:
                        result['success'] = False
                        result['error'] = "Campo admin_id não encontrado nos resultados"
                        
    except (OperationalError, ProgrammingError, DatabaseError) as e:
        result['error'] = f"Erro SQL: {str(e)}"
        logger.debug(f"Detalhes do erro SQL para {test['name']}: {traceback.format_exc()}")
        
    except Exception as e:
        result['error'] = f"Erro inesperado: {str(e)}"
        logger.debug(f"Detalhes do erro para {test['name']}: {traceback.format_exc()}")
    
    finally:
        result['execution_time'] = datetime.now() - start_time
    
    return result


def _generate_recommendations(stats: Dict[str, Any]) -> None:
    """
    Gera recomendações baseadas nos resultados dos testes.
    
    Args:
        stats: Dicionário com estatísticas dos testes
    """
    
    # Verificar se há falhas críticas
    critical_failures = [t for t in stats['failed_tests'] if t.get('critical', False)]
    
    if critical_failures:
        stats['recomendacoes'].append("AÇÃO CRÍTICA: Corrigir falhas em testes críticos antes de prosseguir")
    
    # Verificar problemas específicos
    failed_names = [t['test_name'] for t in stats['failed_tests']]
    
    if any('uso_veiculo' in name for name in failed_names):
        stats['recomendacoes'].append("Verificar estrutura da tabela uso_veiculo e executar migrações necessárias")
        
    if any('custo_veiculo' in name for name in failed_names):
        stats['recomendacoes'].append("Verificar estrutura da tabela custo_veiculo e executar migrações necessárias")
        
    if any('JOIN' in name for name in failed_names):
        stats['recomendacoes'].append("Verificar integridade referencial entre tabelas de veículos")
        
    if any('admin_id' in name for name in failed_names):
        stats['recomendacoes'].append("Verificar implementação de multi-tenancy (campo admin_id)")
    
    # Recomendações baseadas na taxa de sucesso
    success_rate = (stats['sucessos'] / stats['total_testes']) * 100
    
    if success_rate < 50:
        stats['recomendacoes'].append("Taxa de sucesso muito baixa - revisar toda a estrutura do sistema")
    elif success_rate < 80:
        stats['recomendacoes'].append("Algumas falhas detectadas - revisar testes falhados")
    elif success_rate == 100:
        stats['recomendacoes'].append("Sistema íntegro - todas as verificações passaram")


def _mask_database_url(url: str) -> str:
    """
    Mascara credenciais na URL do banco para logs seguros.
    
    Args:
        url: URL do banco com credenciais
        
    Returns:
        URL mascarada
    """
    import re
    if not url:
        return "None"
    # Mascarar senha: user:password@host -> user:****@host
    masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    return masked


def _finalize_results(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finaliza e retorna os resultados estruturados.
    
    Args:
        stats: Estatísticas dos testes
        
    Returns:
        Resultados finais estruturados
    """
    stats['fim'] = datetime.now()
    stats['duracao_total'] = stats['fim'] - stats['inicio']
    
    return {
        'status_final': stats['status_final'],
        'total_testes': stats['total_testes'],
        'sucessos': stats['sucessos'],
        'falhas': stats['falhas'],
        'taxa_sucesso': round((stats['sucessos'] / stats['total_testes']) * 100, 1),
        'testes_falhados': [t['test_name'] for t in stats['failed_tests']],
        'recomendacoes': stats['recomendacoes'],
        'duracao': str(stats['duracao_total']),
        'timestamp': stats['fim'].isoformat()
    }


def main():
    """
    Função principal para execução via linha de comando.
    """
    if len(sys.argv) != 2:
        print("Uso: python verify_complete_system.py <DATABASE_URL>")
        print("Exemplo: python verify_complete_system.py postgresql://user:pass@host:5432/db")
        sys.exit(1)
    
    database_url = sys.argv[1]
    
    try:
        results = test_complete_system(database_url)
        
        # Determinar código de saída baseado nos resultados
        if results['status_final'] == 'PASS':
            sys.exit(0)  # Sucesso
        elif results['status_final'] == 'CRITICAL_FAIL':
            sys.exit(2)  # Falha crítica
        else:
            sys.exit(1)  # Falha parcial
            
    except Exception as e:
        print(f"ERRO FATAL: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()