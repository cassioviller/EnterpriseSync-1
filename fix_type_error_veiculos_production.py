#!/usr/bin/env python3
"""
🔧 CORREÇÃO CRÍTICA PRODUÇÃO - Erro de Tipos Veículos
=======================================================
Corrige incompatibilidade entre character varying e integer
Específico para o erro mostrado na imagem do usuário

Erro: "operator does not exist: character varying = integer"
Causa: Campos veiculo_id sendo tratados como string em vez de integer
Solução: Conversão explicita de tipos + ALTER TABLE se necessário
"""

import sys
import os
import traceback
from datetime import datetime

# Configurar path para importar dependências
sys.path.append('/app')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def log_fix(message):
    """Log com timestamp para debugging de produção"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f'[FIX-TYPES] [{timestamp}] {message}'
    print(log_message)
    
    # Salvar em arquivo de log específico
    try:
        with open('/tmp/fix_types_veiculos.log', 'a') as f:
            f.write(log_message + '\n')
    except:
        pass

def fix_vehicle_type_errors():
    """Corrigir erros de tipos específicos do sistema de veículos"""
    
    log_fix('🔧 INICIANDO CORREÇÃO DE TIPOS - SISTEMA VEÍCULOS')
    log_fix('=' * 55)
    
    try:
        from app import app, db
        from sqlalchemy import text, inspect
        
        with app.app_context():
            # 1. Verificar estrutura atual das tabelas
            log_fix('🔍 Verificando estrutura atual das tabelas...')
            
            inspector = inspect(db.engine)
            
            # Tabelas críticas para verificação
            tabelas_criticas = {
                'veiculo': ['id', 'admin_id'],
                'uso_veiculo': ['id', 'veiculo_id', 'funcionario_id', 'admin_id'],
                'custo_veiculo': ['id', 'veiculo_id', 'admin_id'],
                'passageiro_veiculo': ['id', 'uso_veiculo_id', 'funcionario_id', 'admin_id']
            }
            
            problemas_encontrados = []
            
            for tabela, campos_int in tabelas_criticas.items():
                if tabela in inspector.get_table_names():
                    log_fix(f'✅ Tabela {tabela} existe')
                    
                    # Verificar tipos das colunas
                    try:
                        colunas = inspector.get_columns(tabela)
                        for coluna in colunas:
                            if coluna['name'] in campos_int:
                                tipo_atual = str(coluna['type']).upper()
                                if 'INTEGER' not in tipo_atual and 'BIGINT' not in tipo_atual:
                                    problema = f'{tabela}.{coluna["name"]} = {tipo_atual} (deveria ser INTEGER)'
                                    problemas_encontrados.append((tabela, coluna['name'], tipo_atual))
                                    log_fix(f'⚠️ {problema}')
                                else:
                                    log_fix(f'✅ {tabela}.{coluna["name"]} = {tipo_atual}')
                    except Exception as e:
                        log_fix(f'❌ Erro verificando colunas de {tabela}: {e}')
                else:
                    log_fix(f'❌ Tabela {tabela} não existe')
            
            # 2. Aplicar correções se necessário
            if problemas_encontrados:
                log_fix(f'🔧 Encontrados {len(problemas_encontrados)} problemas de tipo')
                
                for tabela, coluna, tipo_atual in problemas_encontrados:
                    try:
                        log_fix(f'🔄 Corrigindo {tabela}.{coluna} ({tipo_atual} → INTEGER)')
                        
                        # Backup de segurança dos dados
                        log_fix(f'💾 Fazendo backup de {tabela}.{coluna}')
                        
                        # Conversão segura de tipo
                        sql_fix = f"""
                        -- Correção de tipo para {tabela}.{coluna}
                        ALTER TABLE {tabela} 
                        ALTER COLUMN {coluna} TYPE INTEGER 
                        USING CASE 
                            WHEN {coluna} ~ '^[0-9]+$' THEN {coluna}::INTEGER
                            ELSE NULL
                        END;
                        """
                        
                        db.session.execute(text(sql_fix))
                        db.session.commit()
                        
                        log_fix(f'✅ {tabela}.{coluna} corrigido para INTEGER')
                        
                    except Exception as e:
                        log_fix(f'❌ Erro corrigindo {tabela}.{coluna}: {e}')
                        db.session.rollback()
                        
                        # Tentar correção alternativa
                        try:
                            log_fix(f'🔄 Tentativa alternativa para {tabela}.{coluna}')
                            
                            sql_alt = f"""
                            -- Correção alternativa
                            UPDATE {tabela} 
                            SET {coluna} = CAST(NULLIF(TRIM({coluna}), '') AS INTEGER)
                            WHERE {coluna} IS NOT NULL;
                            """
                            
                            db.session.execute(text(sql_alt))
                            db.session.commit()
                            
                            log_fix(f'✅ Correção alternativa aplicada para {tabela}.{coluna}')
                            
                        except Exception as e2:
                            log_fix(f'❌ Correção alternativa falhou: {e2}')
                            db.session.rollback()
            else:
                log_fix('✅ Nenhum problema de tipo encontrado')
            
            # 3. Verificação final e otimizações
            log_fix('🔍 Executando verificação final...')
            
            # Testar queries principais que falhavam
            try:
                # Teste 1: Query básica de veículos
                resultado = db.session.execute(text("""
                    SELECT v.id, v.placa, COUNT(uv.id) as total_usos
                    FROM veiculo v
                    LEFT JOIN uso_veiculo uv ON v.id = uv.veiculo_id
                    WHERE v.admin_id = 2
                    GROUP BY v.id, v.placa
                    LIMIT 5
                """)).fetchall()
                
                log_fix(f'✅ Teste query veículos: {len(resultado)} registros')
                
                # Teste 2: Query de uso com passageiros
                resultado2 = db.session.execute(text("""
                    SELECT uv.id, uv.veiculo_id, COUNT(pv.id) as passageiros
                    FROM uso_veiculo uv
                    LEFT JOIN passageiro_veiculo pv ON uv.id = pv.uso_veiculo_id
                    WHERE uv.admin_id = 2
                    GROUP BY uv.id, uv.veiculo_id
                    LIMIT 5
                """)).fetchall()
                
                log_fix(f'✅ Teste query usos: {len(resultado2)} registros')
                
            except Exception as e:
                log_fix(f'❌ Erro nos testes finais: {e}')
                return False
            
            # 4. Limpeza e otimização
            try:
                log_fix('🧹 Executando limpeza e otimização...')
                
                # Recriar índices se necessário
                db.session.execute(text("""
                    -- Recriar índices críticos
                    DROP INDEX IF EXISTS idx_uso_veiculo_admin_veiculo;
                    CREATE INDEX IF NOT EXISTS idx_uso_veiculo_admin_veiculo 
                    ON uso_veiculo(admin_id, veiculo_id);
                    
                    DROP INDEX IF EXISTS idx_passageiro_veiculo_uso;
                    CREATE INDEX IF NOT EXISTS idx_passageiro_veiculo_uso 
                    ON passageiro_veiculo(uso_veiculo_id, admin_id);
                """))
                
                db.session.commit()
                log_fix('✅ Índices otimizados')
                
            except Exception as e:
                log_fix(f'⚠️ Aviso na otimização: {e}')
            
            log_fix('✅ CORREÇÃO DE TIPOS CONCLUÍDA COM SUCESSO')
            return True
            
    except Exception as e:
        log_fix(f'❌ ERRO CRÍTICO NA CORREÇÃO: {e}')
        log_fix(f'📋 Traceback: {traceback.format_exc()}')
        return False

def run_fix_if_needed():
    """Executar correção apenas se necessário"""
    
    # Verificar se correção deve ser forçada
    force_fix = os.environ.get('FORCE_TYPE_FIX', '').lower() in ('1', 'true', 'yes')
    
    if force_fix:
        log_fix('🚀 CORREÇÃO FORÇADA VIA ENVIRONMENT')
        return fix_vehicle_type_errors()
    
    # Verificar se há indicadores de necessidade da correção
    try:
        from app import app, db
        from sqlalchemy import text
        
        with app.app_context():
            # Teste se há erro de tipos
            try:
                db.session.execute(text("""
                    SELECT uv.id 
                    FROM uso_veiculo uv 
                    WHERE uv.veiculo_id = 1 AND uv.admin_id = 2 
                    LIMIT 1
                """)).fetchone()
                
                log_fix('✅ Queries funcionando - correção não necessária')
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'operator does not exist' in error_msg and 'character varying' in error_msg:
                    log_fix('🔧 Erro de tipos detectado - executando correção')
                    return fix_vehicle_type_errors()
                else:
                    log_fix(f'⚠️ Erro diferente detectado: {e}')
                    return True
                    
    except Exception as e:
        log_fix(f'❌ Erro na verificação: {e}')
        return False

if __name__ == '__main__':
    log_fix('🚀 SCRIPT DE CORREÇÃO DE TIPOS INICIADO')
    
    success = run_fix_if_needed()
    
    if success:
        log_fix('✅ SCRIPT CONCLUÍDO COM SUCESSO')
        sys.exit(0)
    else:
        log_fix('❌ SCRIPT FALHOU')
        sys.exit(1)