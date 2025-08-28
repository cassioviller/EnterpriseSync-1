#!/usr/bin/env python3
"""
HOTFIX DASHBOARD PRODUÇÃO
Corrige problemas de dashboard que não mostra informações corretas
"""

import os
import sys
from datetime import date, datetime, timedelta
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

def executar_hotfix_dashboard():
    """Executa correções no dashboard para produção"""
    
    print("🚨 HOTFIX DASHBOARD PRODUÇÃO - INICIANDO")
    print("=" * 60)
    
    try:
        # Conectar com banco de produção
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL não encontrada")
            return False
            
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print("✅ Conexão com banco estabelecida")
        
        # DIAGNÓSTICO COMPLETO
        print("\n🔍 DIAGNÓSTICO DO BANCO DE DADOS:")
        
        # 1. Verificar tabelas existentes
        tabelas = session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        ).fetchall()
        tabelas_lista = [t[0] for t in tabelas]
        print(f"📋 TABELAS EXISTENTES: {len(tabelas_lista)}")
        
        tabelas_criticas = ['funcionario', 'obra', 'rdo', 'registro_ponto']
        for tabela in tabelas_criticas:
            if tabela in tabelas_lista:
                print(f"  ✅ {tabela}: OK")
            else:
                print(f"  ❌ {tabela}: FALTANDO")
        
        # 2. Verificar dados por admin_id
        try:
            funcionarios_admin = session.execute(
                text("SELECT admin_id, COUNT(*) as total, COUNT(CASE WHEN ativo = true THEN 1 END) as ativos FROM funcionario GROUP BY admin_id ORDER BY admin_id")
            ).fetchall()
            print(f"\n👥 FUNCIONÁRIOS POR ADMIN_ID:")
            for row in funcionarios_admin:
                print(f"  Admin {row[0]}: {row[2]} ativos de {row[1]} total")
                
            # Detectar admin_id principal
            if funcionarios_admin:
                admin_id_principal = funcionarios_admin[0][0]
                print(f"🎯 ADMIN_ID PRINCIPAL: {admin_id_principal}")
            else:
                admin_id_principal = 10
                print(f"🆘 FALLBACK ADMIN_ID: {admin_id_principal}")
                
        except Exception as e:
            print(f"❌ Erro ao verificar funcionários: {e}")
            admin_id_principal = 10
        
        # 3. Verificar obras por admin_id
        try:
            obras_admin = session.execute(
                text("SELECT admin_id, COUNT(*) as total FROM obra GROUP BY admin_id ORDER BY admin_id")
            ).fetchall()
            print(f"\n🏗️ OBRAS POR ADMIN_ID:")
            for row in obras_admin:
                print(f"  Admin {row[0]}: {row[1]} obras")
        except Exception as e:
            print(f"❌ Erro ao verificar obras: {e}")
        
        # 4. Criar tabelas RDO se não existirem
        tabelas_rdo = ['rdo', 'rdo_funcionario', 'rdo_atividade']
        for tabela_rdo in tabelas_rdo:
            if tabela_rdo not in tabelas_lista:
                print(f"\n🔧 CRIANDO TABELA: {tabela_rdo}")
                
                if tabela_rdo == 'rdo':
                    session.execute(text("""
                        CREATE TABLE rdo (
                            id SERIAL PRIMARY KEY,
                            numero VARCHAR(50) UNIQUE NOT NULL,
                            obra_id INTEGER NOT NULL,
                            data_relatorio DATE NOT NULL,
                            clima VARCHAR(50),
                            temperatura INTEGER,
                            observacoes_gerais TEXT,
                            admin_id INTEGER NOT NULL,
                            criado_por INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    
                elif tabela_rdo == 'rdo_funcionario':
                    session.execute(text("""
                        CREATE TABLE rdo_funcionario (
                            id SERIAL PRIMARY KEY,
                            rdo_id INTEGER NOT NULL,
                            funcionario_id INTEGER NOT NULL,
                            presente BOOLEAN DEFAULT TRUE,
                            observacoes TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    
                elif tabela_rdo == 'rdo_atividade':
                    session.execute(text("""
                        CREATE TABLE rdo_atividade (
                            id SERIAL PRIMARY KEY,
                            rdo_id INTEGER NOT NULL,
                            descricao TEXT NOT NULL,
                            percentual DECIMAL(5,2) DEFAULT 0.0,
                            observacoes TEXT,
                            servico_id INTEGER,
                            categoria VARCHAR(100),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                
                print(f"✅ Tabela {tabela_rdo} criada com sucesso")
        
        # 5. Verificar estrutura registro_ponto
        try:
            colunas_ponto = session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'registro_ponto' ORDER BY ordinal_position")
            ).fetchall()
            colunas_lista = [col[0] for col in colunas_ponto]
            print(f"\n⏰ COLUNAS REGISTRO_PONTO: {colunas_lista}")
            
            # Verificar se há dados recentes
            if 'data' in colunas_lista:
                registros_recentes = session.execute(
                    text("SELECT COUNT(*) FROM registro_ponto WHERE data >= '2025-07-01'")
                ).fetchone()
                print(f"📊 REGISTROS DE PONTO (desde Jul/2025): {registros_recentes[0]}")
            elif 'data_registro' in colunas_lista:
                registros_recentes = session.execute(
                    text("SELECT COUNT(*) FROM registro_ponto WHERE data_registro >= '2025-07-01'")
                ).fetchone()
                print(f"📊 REGISTROS DE PONTO (desde Jul/2025): {registros_recentes[0]}")
                
        except Exception as e:
            print(f"❌ Erro ao verificar registro_ponto: {e}")
        
        # 6. Commit das alterações
        session.commit()
        print(f"\n✅ HOTFIX APLICADO COM SUCESSO!")
        
        # 7. Teste final - simular consultas do dashboard
        print(f"\n🧪 TESTE DAS CONSULTAS DO DASHBOARD:")
        
        try:
            total_funcionarios = session.execute(
                text(f"SELECT COUNT(*) FROM funcionario WHERE admin_id = {admin_id_principal} AND ativo = true")
            ).fetchone()[0]
            print(f"✅ Total funcionários ativos: {total_funcionarios}")
            
            total_obras = session.execute(
                text(f"SELECT COUNT(*) FROM obra WHERE admin_id = {admin_id_principal}")
            ).fetchone()[0]
            print(f"✅ Total obras: {total_obras}")
            
            # Se tudo funcionou até aqui, o dashboard deve funcionar
            print(f"\n🎉 HOTFIX CONCLUÍDO - DASHBOARD DEVE FUNCIONAR")
            
        except Exception as e:
            print(f"❌ Erro no teste final: {e}")
            return False
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO NO HOTFIX: {e}")
        return False

def verificar_status_dashboard():
    """Verifica se o dashboard está funcionando após hotfix"""
    
    print("\n🔍 VERIFICAÇÃO PÓS-HOTFIX:")
    
    try:
        import requests
        
        # Tentar acessar o dashboard (se aplicação estiver rodando)
        try:
            response = requests.get('http://localhost:5000/dashboard', timeout=10)
            if response.status_code == 200:
                print("✅ Dashboard acessível via HTTP")
            else:
                print(f"⚠️ Dashboard retornou status {response.status_code}")
        except:
            print("⚠️ Aplicação não está rodando ou não acessível")
        
    except ImportError:
        print("⚠️ Requests não disponível para teste HTTP")
    
    print("✅ Verificação concluída")

if __name__ == "__main__":
    print("HOTFIX DASHBOARD PRODUÇÃO")
    print("=" * 40)
    
    sucesso = executar_hotfix_dashboard()
    
    if sucesso:
        verificar_status_dashboard()
        print("\n🎯 PRÓXIMOS PASSOS:")
        print("1. Reiniciar aplicação no EasyPanel")
        print("2. Acessar /dashboard na produção")
        print("3. Verificar se KPIs estão sendo exibidos")
        print("4. Testar filtros de data")
    else:
        print("\n❌ HOTFIX FALHOU - NECESSÁRIA INTERVENÇÃO MANUAL")
        print("1. Verificar logs do banco de dados")
        print("2. Executar SQL manualmente se necessário")
        print("3. Verificar conectividade com banco")