#!/usr/bin/env python3
"""
🏥 HEALTH CHECK ESPECÍFICO PARA SISTEMA DE VEÍCULOS
==================================================
Diagnóstico completo do sistema de veículos para produção
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask, jsonify
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

def create_health_check_app():
    """Cria app Flask específico para health check"""
    app = Flask(__name__)
    
    @app.route('/health/veiculos')
    def health_check_veiculos():
        """Health check detalhado do sistema de veículos"""
        start_time = datetime.now()
        resultado = {
            'timestamp': start_time.isoformat(),
            'status': 'unknown',
            'checks': {},
            'errors': [],
            'warnings': [],
            'duracao_ms': 0
        }
        
        try:
            # 1. Verificar conexão com banco
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                resultado['errors'].append("DATABASE_URL não encontrada")
                resultado['status'] = 'error'
                return jsonify(resultado), 500
                
            engine = create_engine(database_url)
            
            # Teste de conectividade
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                resultado['checks']['database_connection'] = 'OK'
            except Exception as e:
                resultado['checks']['database_connection'] = 'FAIL'
                resultado['errors'].append(f"Conexão banco: {str(e)}")
                
            # 2. Verificar tabelas essenciais
            try:
                inspector = inspect(engine)
                tabelas_existentes = inspector.get_table_names()
                
                tabelas_essenciais = ['veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo']
                tabelas_obsoletas = ['alocacao_veiculo', 'equipe_veiculo', 'transferencia_veiculo', 'manutencao_veiculo', 'alerta_veiculo']
                
                # Verificar tabelas essenciais
                for tabela in tabelas_essenciais:
                    if tabela in tabelas_existentes:
                        resultado['checks'][f'tabela_{tabela}'] = 'OK'
                    else:
                        resultado['checks'][f'tabela_{tabela}'] = 'MISSING'
                        resultado['errors'].append(f"Tabela essencial ausente: {tabela}")
                
                # Verificar se tabelas obsoletas foram removidas
                for tabela in tabelas_obsoletas:
                    if tabela in tabelas_existentes:
                        resultado['checks'][f'obsoleta_{tabela}'] = 'PRESENT'
                        resultado['warnings'].append(f"Tabela obsoleta ainda presente: {tabela}")
                    else:
                        resultado['checks'][f'obsoleta_{tabela}'] = 'REMOVED'
                        
            except Exception as e:
                resultado['errors'].append(f"Erro ao verificar tabelas: {str(e)}")
                
            # 3. Verificar contagem de dados
            try:
                with engine.connect() as conn:
                    # Contar veículos
                    if 'veiculo' in tabelas_existentes:
                        result = conn.execute(text("SELECT COUNT(*) FROM veiculo"))
                        count_veiculos = result.scalar()
                        resultado['checks']['count_veiculos'] = count_veiculos
                        
                    # Contar usos
                    if 'uso_veiculo' in tabelas_existentes:
                        result = conn.execute(text("SELECT COUNT(*) FROM uso_veiculo"))
                        count_usos = result.scalar()
                        resultado['checks']['count_usos'] = count_usos
                        
                    # Contar custos
                    if 'custo_veiculo' in tabelas_existentes:
                        result = conn.execute(text("SELECT COUNT(*) FROM custo_veiculo"))
                        count_custos = result.scalar()
                        resultado['checks']['count_custos'] = count_custos
                        
            except Exception as e:
                resultado['errors'].append(f"Erro ao contar dados: {str(e)}")
                
            # 4. Verificar constraints e relacionamentos
            try:
                with engine.connect() as conn:
                    # Verificar foreign keys essenciais
                    sql_fk_check = """
                    SELECT tc.constraint_name, tc.table_name, kcu.column_name, 
                           ccu.table_name AS foreign_table_name,
                           ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name IN ('veiculo', 'uso_veiculo', 'custo_veiculo', 'passageiro_veiculo')
                    """
                    
                    result = conn.execute(text(sql_fk_check))
                    fks = result.fetchall()
                    resultado['checks']['foreign_keys_count'] = len(fks)
                    
            except Exception as e:
                resultado['warnings'].append(f"Erro ao verificar constraints: {str(e)}")
                
            # 5. Determinar status final
            if resultado['errors']:
                resultado['status'] = 'error'
                status_code = 500
            elif resultado['warnings']:
                resultado['status'] = 'warning'
                status_code = 200
            else:
                resultado['status'] = 'healthy'
                status_code = 200
                
            # Calcular duração
            end_time = datetime.now()
            duracao = (end_time - start_time).total_seconds() * 1000
            resultado['duracao_ms'] = round(duracao, 2)
            
            return jsonify(resultado), status_code
            
        except Exception as e:
            resultado['status'] = 'error'
            resultado['errors'].append(f"Erro crítico: {str(e)}")
            return jsonify(resultado), 500
    
    @app.route('/health')
    def health_check_geral():
        """Health check geral do sistema"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'SIGE v10.0',
            'veiculos_check': '/health/veiculos'
        })
    
    return app

if __name__ == '__main__':
    app = create_health_check_app()
    app.run(debug=True, host='0.0.0.0', port=5001)