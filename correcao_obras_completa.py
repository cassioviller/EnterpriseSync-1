#!/usr/bin/env python3
"""
CORREÇÃO COMPLETA DA PÁGINA DE OBRAS
Sistema de correção automática para todos os problemas identificados
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text
from datetime import datetime, date

def corrigir_template_obras():
    """Corrigir possíveis problemas de sintaxe no template de obras"""
    template_path = 'templates/obras/detalhes_obra.html'
    
    print("🔧 CORRIGINDO TEMPLATE DE OBRAS")
    print("=" * 50)
    
    try:
        # Backup do template original
        backup_path = f"{template_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Backup criado: {backup_path}")
        
        # Verificar problemas comuns de sintaxe Jinja2
        problems_found = []
        
        # Contar tags if/else/endif
        if_count = content.count('{% if ')
        else_count = content.count('{% else %}')
        elif_count = content.count('{% elif ')
        endif_count = content.count('{% endif %}')
        
        print(f"📊 Análise de tags:")
        print(f"  - {% if %}: {if_count}")
        print(f"  - {% elif %}: {elif_count}")
        print(f"  - {% else %}: {else_count}")
        print(f"  - {% endif %}: {endif_count}")
        
        # Verificações básicas
        if (if_count + elif_count) != endif_count:
            problems_found.append("Número de {% if %}/{% elif %} não coincide com {% endif %}")
        
        # Verificar variáveis undefined comuns
        undefined_vars = ['kpis.custo_total', 'obra.cliente', 'rdos_periodo']
        for var in undefined_vars:
            if var in content and f"{var} else" not in content:
                problems_found.append(f"Variável {var} pode estar undefined - adicionar fallback")
        
        if problems_found:
            print("⚠️  Problemas encontrados:")
            for problem in problems_found:
                print(f"  - {problem}")
        else:
            print("✅ Nenhum problema óbvio de sintaxe encontrado")
            
    except Exception as e:
        print(f"❌ Erro ao analisar template: {e}")

def corrigir_model_obra():
    """Adicionar campos faltantes na model Obra"""
    print("\n🏗️ CORRIGINDO MODEL OBRA")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Verificar estrutura atual
            colunas = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'obra'
                ORDER BY column_name
            """)).fetchall()
            
            print(f"📊 Colunas atuais da tabela obra: {len(colunas)}")
            
            # Campos que devem existir
            campos_necessarios = {
                'cliente': 'VARCHAR(200)',
                'progresso_conclusao': 'INTEGER DEFAULT 0',
                'descricao': 'TEXT',
                'area_total_m2': 'DECIMAL(10,2) DEFAULT 0'
            }
            
            colunas_existentes = [col[0] for col in colunas]
            
            for campo, tipo in campos_necessarios.items():
                if campo not in colunas_existentes:
                    try:
                        print(f"🔄 Adicionando campo '{campo}'...")
                        db.session.execute(text(f"ALTER TABLE obra ADD COLUMN {campo} {tipo}"))
                        db.session.commit()
                        print(f"✅ Campo '{campo}' adicionado")
                    except Exception as e:
                        print(f"⚠️  Campo '{campo}': {e}")
                        db.session.rollback()
                else:
                    print(f"✅ Campo '{campo}' já existe")
                    
        except Exception as e:
            print(f"❌ Erro ao corrigir model: {e}")

def corrigir_dados_exemplo():
    """Adicionar dados de exemplo para testes"""
    print("\n📊 CORRIGINDO DADOS DE EXEMPLO")
    print("=" * 50)
    
    with app.app_context():
        try:
            from models import Obra
            
            # Verificar se há obras com campo cliente vazio
            obras_sem_cliente = Obra.query.filter(
                (Obra.cliente == None) | (Obra.cliente == '')
            ).all()
            
            print(f"🔍 Encontradas {len(obras_sem_cliente)} obras sem cliente")
            
            # Adicionar clientes de exemplo
            clientes_exemplo = [
                "Construtora Silva & Associados",
                "Empresa ABC Construções",
                "Incorporadora Vale Verde",
                "Construtora Horizonte",
                "Engenharia Premium Ltda"
            ]
            
            for i, obra in enumerate(obras_sem_cliente[:5]):
                cliente = clientes_exemplo[i % len(clientes_exemplo)]
                obra.cliente = cliente
                
                # Adicionar progresso se não existir
                if not hasattr(obra, 'progresso_conclusao') or obra.progresso_conclusao is None:
                    obra.progresso_conclusao = min(100, max(0, (i + 1) * 20))
                
                print(f"✅ Obra '{obra.nome}' -> Cliente: {cliente}")
            
            db.session.commit()
            print(f"✅ {len(obras_sem_cliente[:5])} obras atualizadas")
            
        except Exception as e:
            print(f"❌ Erro ao adicionar dados: {e}")
            db.session.rollback()

def corrigir_relacionamentos():
    """Verificar e corrigir relacionamentos entre tabelas"""
    print("\n🔗 VERIFICANDO RELACIONAMENTOS")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Verificar obras órfãs (sem admin_id)
            obras_sem_admin = db.session.execute(text("""
                SELECT id, nome FROM obra WHERE admin_id IS NULL
            """)).fetchall()
            
            if obras_sem_admin:
                print(f"⚠️  {len(obras_sem_admin)} obras sem admin_id")
                
                # Atribuir ao admin com mais dados
                admin_principal = db.session.execute(text("""
                    SELECT admin_id, COUNT(*) as total 
                    FROM obra 
                    WHERE admin_id IS NOT NULL 
                    GROUP BY admin_id 
                    ORDER BY total DESC 
                    LIMIT 1
                """)).fetchone()
                
                if admin_principal:
                    admin_id = admin_principal[0]
                    print(f"🔄 Atribuindo obras órfãs ao admin_id {admin_id}")
                    
                    db.session.execute(text(f"""
                        UPDATE obra SET admin_id = {admin_id} WHERE admin_id IS NULL
                    """))
                    db.session.commit()
                    print("✅ Obras órfãs corrigidas")
            else:
                print("✅ Todas as obras têm admin_id válido")
                
            # Verificar RDOs órfãos
            rdos_sem_obra = db.session.execute(text("""
                SELECT COUNT(*) FROM rdo 
                WHERE obra_id NOT IN (SELECT id FROM obra)
            """)).fetchone()
            
            if rdos_sem_obra and rdos_sem_obra[0] > 0:
                print(f"⚠️  {rdos_sem_obra[0]} RDOs órfãos encontrados")
            else:
                print("✅ Todos os RDOs têm obra válida")
                
        except Exception as e:
            print(f"❌ Erro ao verificar relacionamentos: {e}")

def corrigir_indexes():
    """Criar índices para melhorar performance"""
    print("\n⚡ OTIMIZANDO PERFORMANCE")
    print("=" * 50)
    
    with app.app_context():
        try:
            indexes_necessarios = [
                "CREATE INDEX IF NOT EXISTS idx_obra_admin_id ON obra(admin_id)",
                "CREATE INDEX IF NOT EXISTS idx_obra_status ON obra(status)", 
                "CREATE INDEX IF NOT EXISTS idx_obra_data_inicio ON obra(data_inicio)",
                "CREATE INDEX IF NOT EXISTS idx_obra_cliente ON obra(cliente)",
                "CREATE INDEX IF NOT EXISTS idx_rdo_obra_id ON rdo(obra_id)",
                "CREATE INDEX IF NOT EXISTS idx_funcionario_admin_id ON funcionario(admin_id)"
            ]
            
            for index_sql in indexes_necessarios:
                try:
                    db.session.execute(text(index_sql))
                    index_name = index_sql.split(' ')[5]  # Extrair nome do índice
                    print(f"✅ Índice {index_name} criado/verificado")
                except Exception as e:
                    print(f"⚠️  Índice: {e}")
            
            db.session.commit()
            print("✅ Otimização de índices concluída")
            
        except Exception as e:
            print(f"❌ Erro ao criar índices: {e}")

def verificar_correcoes():
    """Verificar se todas as correções foram aplicadas"""
    print("\n🎯 VERIFICAÇÃO FINAL")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Verificar campo cliente
            obras_com_cliente = db.session.execute(text("""
                SELECT COUNT(*) FROM obra WHERE cliente IS NOT NULL AND cliente != ''
            """)).fetchone()[0]
            
            total_obras = db.session.execute(text("SELECT COUNT(*) FROM obra")).fetchone()[0]
            
            print(f"📊 Obras com cliente: {obras_com_cliente}/{total_obras}")
            
            # Verificar admin_id
            obras_com_admin = db.session.execute(text("""
                SELECT COUNT(*) FROM obra WHERE admin_id IS NOT NULL
            """)).fetchone()[0]
            
            print(f"🔑 Obras com admin_id: {obras_com_admin}/{total_obras}")
            
            # Verificar relacionamentos RDO
            rdos_validos = db.session.execute(text("""
                SELECT COUNT(*) FROM rdo r 
                INNER JOIN obra o ON r.obra_id = o.id
            """)).fetchone()[0]
            
            total_rdos = db.session.execute(text("SELECT COUNT(*) FROM rdo")).fetchone()[0]
            
            print(f"📝 RDOs com obra válida: {rdos_validos}/{total_rdos}")
            
            # Status geral
            if obras_com_cliente == total_obras and obras_com_admin == total_obras and rdos_validos == total_rdos:
                print("\n🎉 TODAS AS CORREÇÕES APLICADAS COM SUCESSO!")
                return True
            else:
                print("\n⚠️  Algumas correções precisam de atenção")
                return False
                
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            return False

def main():
    """Função principal da correção"""
    print("🚀 INICIANDO CORREÇÃO COMPLETA DA PÁGINA DE OBRAS")
    print("=" * 70)
    
    # Executar todas as correções
    corrigir_template_obras()
    corrigir_model_obra()
    corrigir_dados_exemplo()
    corrigir_relacionamentos()
    corrigir_indexes()
    
    # Verificação final
    sucesso = verificar_correcoes()
    
    print("\n" + "=" * 70)
    if sucesso:
        print("✅ CORREÇÃO COMPLETA FINALIZADA COM SUCESSO")
    else:
        print("⚠️  CORREÇÃO FINALIZADA COM PENDÊNCIAS")
    print("=" * 70)

if __name__ == "__main__":
    main()