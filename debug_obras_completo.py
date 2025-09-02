#!/usr/bin/env python3
"""
DEBUG COMPLETO DA PÁGINA DE OBRAS
Sistema de diagnóstico abrangente para identificar problemas na página de obras
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Obra, Funcionario, RDO, RegistroPonto
from sqlalchemy import text, func, desc
from datetime import datetime, date

def debug_estrutura_tabelas():
    """Debug da estrutura das tabelas relacionadas"""
    print("🔍 ESTRUTURA DAS TABELAS")
    print("=" * 50)
    
    try:
        # Verificar colunas da tabela obra
        colunas_obra = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'obra'")).fetchall()
        print(f"📊 COLUNAS TABELA OBRA ({len(colunas_obra)}):")
        for col in colunas_obra:
            print(f"  - {col[0]}")
        
        # Verificar colunas da tabela funcionario
        colunas_func = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'funcionario'")).fetchall()
        print(f"\n👤 COLUNAS TABELA FUNCIONARIO ({len(colunas_func)}):")
        for col in colunas_func:
            print(f"  - {col[0]}")
            
        # Verificar colunas da tabela rdo
        colunas_rdo = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'rdo'")).fetchall()
        print(f"\n📝 COLUNAS TABELA RDO ({len(colunas_rdo)}):")
        for col in colunas_rdo:
            print(f"  - {col[0]}")
            
    except Exception as e:
        print(f"❌ Erro ao verificar estrutura: {e}")

def debug_dados_obras():
    """Debug dos dados das obras"""
    print("\n🏗️ DADOS DAS OBRAS")
    print("=" * 50)
    
    try:
        # Contagem total de obras
        total_obras = Obra.query.count()
        print(f"📊 TOTAL DE OBRAS: {total_obras}")
        
        # Obras por admin_id
        obras_por_admin = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM obra GROUP BY admin_id ORDER BY total DESC")).fetchall()
        print(f"\n🔑 OBRAS POR ADMIN_ID:")
        for admin_id, total in obras_por_admin:
            print(f"  - Admin {admin_id}: {total} obras")
        
        # Obras por status
        obras_por_status = db.session.execute(text("SELECT status, COUNT(*) as total FROM obra GROUP BY status")).fetchall()
        print(f"\n📈 OBRAS POR STATUS:")
        for status, total in obras_por_status:
            print(f"  - {status}: {total} obras")
            
        # Últimas 5 obras criadas
        obras_recentes = Obra.query.order_by(desc(Obra.id)).limit(5).all()
        print(f"\n🆕 ÚLTIMAS 5 OBRAS CRIADAS:")
        for obra in obras_recentes:
            print(f"  - {obra.id}: {obra.nome} (Admin: {obra.admin_id}, Status: {obra.status})")
            
    except Exception as e:
        print(f"❌ Erro ao verificar dados das obras: {e}")

def debug_relacionamentos():
    """Debug dos relacionamentos entre tabelas"""
    print("\n🔗 RELACIONAMENTOS")
    print("=" * 50)
    
    try:
        # RDOs por obra
        rdos_por_obra = db.session.execute(text("SELECT obra_id, COUNT(*) as total FROM rdo GROUP BY obra_id ORDER BY total DESC LIMIT 10")).fetchall()
        print(f"📊 RDOs POR OBRA (Top 10):")
        for obra_id, total in rdos_por_obra:
            try:
                obra = Obra.query.get(obra_id)
                nome_obra = obra.nome if obra else f"Obra {obra_id} (não encontrada)"
                print(f"  - {nome_obra}: {total} RDOs")
            except:
                print(f"  - Obra {obra_id}: {total} RDOs")
        
        # Funcionários por admin_id
        func_por_admin = db.session.execute(text("SELECT admin_id, COUNT(*) as total FROM funcionario GROUP BY admin_id ORDER BY total DESC")).fetchall()
        print(f"\n👥 FUNCIONÁRIOS POR ADMIN_ID:")
        for admin_id, total in func_por_admin:
            print(f"  - Admin {admin_id}: {total} funcionários")
            
    except Exception as e:
        print(f"❌ Erro ao verificar relacionamentos: {e}")

def debug_views_routes():
    """Debug das rotas e views"""
    print("\n🛣️ ROTAS E VIEWS")
    print("=" * 50)
    
    try:
        from flask import url_for
        with app.app_context():
            # Verificar se as rotas existem
            rotas_importantes = [
                'main.obras',
                'main.detalhes_obra',
                'main.nova_obra',
                'main.editar_obra'
            ]
            
            for rota in rotas_importantes:
                try:
                    if rota == 'main.detalhes_obra':
                        url = url_for(rota, id=1)
                    else:
                        url = url_for(rota)
                    print(f"✅ {rota}: {url}")
                except Exception as e:
                    print(f"❌ {rota}: ERRO - {e}")
                    
    except Exception as e:
        print(f"❌ Erro ao verificar rotas: {e}")

def debug_templates():
    """Debug dos templates"""
    print("\n📄 TEMPLATES")
    print("=" * 50)
    
    templates_importantes = [
        'templates/obras.html',
        'templates/obras/detalhes_obra.html',
        'templates/obra_form.html'
    ]
    
    for template in templates_importantes:
        if os.path.exists(template):
            size = os.path.getsize(template)
            print(f"✅ {template}: {size} bytes")
            
            # Verificar sintaxe básica
            try:
                with open(template, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if '{% else %}' in content and content.count('{% endif %}') < content.count('{% else %}'):
                        print(f"⚠️  {template}: Possível problema de sintaxe Jinja2")
                    else:
                        print(f"✅ {template}: Sintaxe Jinja2 OK")
            except Exception as e:
                print(f"❌ {template}: Erro ao ler - {e}")
        else:
            print(f"❌ {template}: Arquivo não encontrado")

def debug_modelo_obra():
    """Debug específico do modelo Obra"""
    print("\n🏗️ MODELO OBRA")
    print("=" * 50)
    
    try:
        # Verificar atributos do modelo
        atributos_obra = [attr for attr in dir(Obra) if not attr.startswith('_')]
        print(f"🔧 ATRIBUTOS DO MODELO OBRA ({len(atributos_obra)}):")
        for attr in sorted(atributos_obra):
            print(f"  - {attr}")
        
        # Verificar se campo cliente existe
        if hasattr(Obra, 'cliente'):
            print(f"\n✅ Campo 'cliente' existe no modelo Obra")
        else:
            print(f"\n❌ Campo 'cliente' NÃO existe no modelo Obra")
            
        # Verificar se outros campos importantes existem
        campos_importantes = ['nome', 'status', 'admin_id', 'data_inicio', 'orcamento', 'endereco']
        print(f"\n🔍 VERIFICAÇÃO DE CAMPOS IMPORTANTES:")
        for campo in campos_importantes:
            if hasattr(Obra, campo):
                print(f"  ✅ {campo}")
            else:
                print(f"  ❌ {campo}")
                
    except Exception as e:
        print(f"❌ Erro ao verificar modelo Obra: {e}")

def debug_consultas_sql():
    """Debug das consultas SQL mais usadas"""
    print("\n💾 CONSULTAS SQL")
    print("=" * 50)
    
    try:
        # Testar consulta básica de obras
        obras = Obra.query.limit(3).all()
        print(f"✅ Consulta básica obras: {len(obras)} resultados")
        
        # Testar consulta com filtro admin_id
        obras_admin = Obra.query.filter_by(admin_id=10).limit(3).all()
        print(f"✅ Consulta obras admin_id=10: {len(obras_admin)} resultados")
        
        # Testar consulta com join (se houver RDOs)
        try:
            rdos_obras = db.session.query(RDO, Obra).join(Obra).limit(3).all()
            print(f"✅ Consulta RDO + Obra: {len(rdos_obras)} resultados")
        except Exception as e:
            print(f"⚠️  Consulta RDO + Obra: {e}")
            
    except Exception as e:
        print(f"❌ Erro nas consultas SQL: {e}")

def main():
    """Função principal do debug"""
    print("🚀 INICIANDO DEBUG COMPLETO DA PÁGINA DE OBRAS")
    print("=" * 70)
    
    with app.app_context():
        debug_estrutura_tabelas()
        debug_dados_obras()
        debug_relacionamentos()
        debug_views_routes()
        debug_templates()
        debug_modelo_obra()
        debug_consultas_sql()
        
    print("\n" + "=" * 70)
    print("🎯 DEBUG COMPLETO FINALIZADO")
    print("=" * 70)

if __name__ == "__main__":
    main()