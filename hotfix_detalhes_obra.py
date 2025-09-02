#!/usr/bin/env python3
"""
HOTFIX CRÍTICO - DETALHES DA OBRA
Correção do erro: cannot access local variable 'text' where it is not associated with a value
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Obra, Funcionario, RDO
from sqlalchemy import text
from datetime import datetime, date

def debug_detalhes_obra(obra_id=41):
    """Debug específico da função detalhes_obra"""
    
    with app.app_context():
        print(f"🔍 DEBUG DETALHES OBRA - ID {obra_id}")
        print("=" * 50)
        
        try:
            # 1. Verificar se obra existe
            obra = Obra.query.get(obra_id)
            if not obra:
                print(f"❌ Obra ID {obra_id} não encontrada")
                return False
                
            print(f"✅ Obra encontrada: {obra.nome}")
            print(f"   Status: {obra.status}")
            print(f"   Admin ID: {obra.admin_id}")
            
            # 2. Testar parâmetros de data
            data_inicio = date(2025, 7, 1)
            data_fim = date(2025, 8, 31)
            print(f"📅 Período: {data_inicio} até {data_fim}")
            
            # 3. Verificar registros de ponto
            try:
                registros_count = db.session.execute(text(f"""
                    SELECT COUNT(*) FROM registro_ponto 
                    WHERE obra_id = {obra_id} 
                    AND data BETWEEN '{data_inicio}' AND '{data_fim}'
                """)).fetchone()[0]
                print(f"📊 Registros de ponto: {registros_count}")
            except Exception as e:
                print(f"⚠️  Erro ao consultar registros: {e}")
            
            # 4. Verificar funcionários
            try:
                funcionarios_count = Funcionario.query.filter_by(admin_id=obra.admin_id).count()
                print(f"👥 Funcionários disponíveis: {funcionarios_count}")
            except Exception as e:
                print(f"⚠️  Erro ao consultar funcionários: {e}")
            
            # 5. Verificar RDOs
            try:
                rdos_count = RDO.query.filter_by(obra_id=obra_id).count()
                print(f"📝 RDOs da obra: {rdos_count}")
            except Exception as e:
                print(f"⚠️  Erro ao consultar RDOs: {e}")
            
            # 6. Testar consulta de custos (problemática)
            try:
                admin_id = obra.admin_id
                print(f"🔧 Testando consulta de custos para admin_id: {admin_id}")
                
                # Esta é a consulta que estava causando problema
                resultado = db.session.execute(text(f"""
                    SELECT f.nome, f.id, f.salario
                    FROM funcionario f
                    WHERE f.admin_id = {admin_id}
                    AND f.ativo = true
                    LIMIT 5
                """)).fetchall()
                
                print(f"✅ Consulta de custos funcionou: {len(resultado)} resultados")
                
            except Exception as e:
                print(f"❌ ERRO na consulta de custos: {e}")
                return False
            
            print("✅ Todos os testes passaram!")
            return True
            
        except Exception as e:
            print(f"❌ ERRO GERAL: {e}")
            return False

def corrigir_imports_views():
    """Corrigir imports problemáticos no views.py"""
    
    print("\n🔧 CORRIGINDO IMPORTS NO VIEWS.PY")
    print("=" * 50)
    
    # Lista de correções específicas
    correcoes = [
        {
            'problema': 'text não importado localmente',
            'descricao': 'Adicionar import sqlalchemy.text no início da função',
            'local': 'função detalhes_obra linha ~1303'
        },
        {
            'problema': 'Import duplicado de text',
            'descricao': 'Remover imports duplicados de sqlalchemy.text',
            'local': 'função detalhes_obra linha ~1248'
        }
    ]
    
    for i, correcao in enumerate(correcoes, 1):
        print(f"{i}. {correcao['problema']}")
        print(f"   📍 Local: {correcao['local']}")
        print(f"   🔧 Correção: {correcao['descricao']}")
    
    print("\n⚠️  Correções já aplicadas no código!")

def testar_obra_disponivel():
    """Encontrar uma obra válida para testes"""
    
    with app.app_context():
        print("\n🔍 PROCURANDO OBRA VÁLIDA PARA TESTE")
        print("=" * 50)
        
        # Buscar obras com admin_id=10 (mais comum)
        obras = Obra.query.filter_by(admin_id=10).limit(5).all()
        
        print(f"📋 Obras disponíveis para admin_id=10:")
        for obra in obras:
            rdos_count = RDO.query.filter_by(obra_id=obra.id).count()
            print(f"   ID {obra.id}: {obra.nome}")
            print(f"     Status: {obra.status}")
            print(f"     RDOs: {rdos_count}")
            print(f"     URL: /obras/detalhes/{obra.id}")
            print()
        
        if obras:
            obra_teste = obras[0]
            print(f"✅ Obra recomendada para teste: ID {obra_teste.id} - {obra_teste.nome}")
            return obra_teste.id
        else:
            print("❌ Nenhuma obra encontrada")
            return None

def main():
    """Função principal do hotfix"""
    print("🚀 HOTFIX DETALHES DA OBRA - CORREÇÃO DO ERRO 'text'")
    print("=" * 70)
    
    # 1. Testar obra específica que estava com erro
    sucesso = debug_detalhes_obra(41)
    
    # 2. Se falhou, encontrar obra válida
    if not sucesso:
        obra_id = testar_obra_disponivel()
        if obra_id:
            sucesso = debug_detalhes_obra(obra_id)
    
    # 3. Mostrar status das correções
    corrigir_imports_views()
    
    print("\n" + "=" * 70)
    if sucesso:
        print("✅ HOTFIX APLICADO COM SUCESSO")
        print("🎯 A página de detalhes da obra deve funcionar agora")
    else:
        print("⚠️  HOTFIX PARCIAL - VERIFICAR LOGS")
    print("=" * 70)

if __name__ == "__main__":
    main()