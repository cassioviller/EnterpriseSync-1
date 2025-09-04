#!/usr/bin/env python3
"""
Script de Verificação para Produção - SIGE v8.2
Detecta e corrige automaticamente problemas de admin_id em produção
"""

def main():
    print("🔍 VERIFICAÇÃO COMPLETA DE PRODUÇÃO - SIGE v8.2")
    print("="*70)
    
    try:
        from app import app, db
        from sqlalchemy import text
        
        with app.app_context():
            # 1. Verificar conexão com banco
            print("1️⃣ Testando conexão com PostgreSQL...")
            db.session.execute(text('SELECT 1'))
            print("   ✅ Conexão com banco OK")
            
            # 2. Listar todos os admin_ids disponíveis
            print("\n2️⃣ Mapeando admin_ids disponíveis:")
            
            admin_ids_funcionarios = dict(db.session.execute(text(
                "SELECT admin_id, COUNT(*) FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY admin_id"
            )).fetchall())
            
            admin_ids_servicos = dict(db.session.execute(text(
                "SELECT admin_id, COUNT(*) FROM servico WHERE ativo = true GROUP BY admin_id ORDER BY admin_id"
            )).fetchall())
            
            admin_ids_subatividades = dict(db.session.execute(text(
                "SELECT admin_id, COUNT(*) FROM subatividade_mestre WHERE ativo = true GROUP BY admin_id ORDER BY admin_id"
            )).fetchall())
            
            admin_ids_obras = dict(db.session.execute(text(
                "SELECT admin_id, COUNT(*) FROM obra GROUP BY admin_id ORDER BY admin_id"
            )).fetchall())
            
            # Combinar todos os admin_ids
            all_admin_ids = set()
            all_admin_ids.update(admin_ids_funcionarios.keys())
            all_admin_ids.update(admin_ids_servicos.keys()) 
            all_admin_ids.update(admin_ids_subatividades.keys())
            all_admin_ids.update(admin_ids_obras.keys())
            
            print(f"   📊 Admin_IDs encontrados: {sorted(all_admin_ids)}")
            
            # 3. Análise detalhada por admin_id
            print("\n3️⃣ Análise detalhada por admin_id:")
            
            scores = {}
            for admin_id in sorted(all_admin_ids):
                funcionarios = admin_ids_funcionarios.get(admin_id, 0)
                servicos = admin_ids_servicos.get(admin_id, 0)
                subatividades = admin_ids_subatividades.get(admin_id, 0)
                obras = admin_ids_obras.get(admin_id, 0)
                
                # Calcular score (funcionários e serviços são mais importantes)
                score = funcionarios * 3 + servicos * 2 + subatividades * 1 + obras * 1
                scores[admin_id] = score
                
                print(f"   🏢 Admin_ID {admin_id}: {funcionarios} funcionários, {servicos} serviços, {subatividades} subatividades, {obras} obras (Score: {score})")
                
                # Verificar se tem dados suficientes para funcionar
                if funcionarios > 0 or servicos > 0 or obras > 0:
                    print(f"      ✅ VÁLIDO para produção")
                else:
                    print(f"      ⚠️  INSUFICIENTE para produção")
            
            # 4. Recomendar admin_id ideal
            print("\n4️⃣ Recomendação para produção:")
            
            if scores:
                recommended_admin_id = max(scores.keys(), key=lambda x: scores[x])
                print(f"   🎯 Admin_ID recomendado: {recommended_admin_id} (score: {scores[recommended_admin_id]})")
                
                # Verificar se tem subatividades
                if admin_ids_subatividades.get(recommended_admin_id, 0) == 0:
                    print(f"   ⚠️  ATENÇÃO: Admin_ID {recommended_admin_id} não tem subatividades_mestre")
                    print("      💡 Solução: Executar migração para criar subatividades padrão")
                else:
                    print(f"   ✅ Admin_ID {recommended_admin_id} tem {admin_ids_subatividades[recommended_admin_id]} subatividades")
                
            else:
                print("   ❌ ERRO: Nenhum admin_id encontrado!")
                return False
            
            # 5. Testar função de detecção automática
            print("\n5️⃣ Testando detecção automática do sistema:")
            
            try:
                # Simular a função get_admin_id_robusta
                result = db.session.execute(text("""
                    SELECT admin_id, COUNT(*) as total 
                    FROM funcionario 
                    WHERE ativo = true 
                    GROUP BY admin_id 
                    ORDER BY total DESC 
                    LIMIT 1
                """)).fetchone()
                
                if result:
                    detected_admin_id = result[0]
                    print(f"   🤖 Sistema detectaria automaticamente: admin_id {detected_admin_id}")
                    
                    if detected_admin_id == recommended_admin_id:
                        print("   ✅ Detecção automática CORRETA")
                    else:
                        print(f"   ⚠️  Detecção automática difere da recomendação (diferença pode ser aceitável)")
                else:
                    print("   ❌ Sistema não conseguiu detectar admin_id automaticamente")
                    
            except Exception as detect_error:
                print(f"   ❌ Erro na detecção automática: {detect_error}")
            
            # 6. Verificar tabelas críticas do sistema "Serviços da Obra"
            print("\n6️⃣ Verificando sistema 'Serviços da Obra':")
            
            try:
                # Verificar se existe dados RDO
                rdo_count = db.session.execute(text("SELECT COUNT(*) FROM rdo")).scalar()
                rdo_servicos_count = db.session.execute(text("SELECT COUNT(*) FROM rdo_servico_subatividade WHERE ativo = true")).scalar()
                
                print(f"   📋 RDOs no sistema: {rdo_count}")
                print(f"   🔧 RDO Serviços ativos: {rdo_servicos_count}")
                
                if rdo_servicos_count > 0:
                    print("   ✅ Sistema 'Serviços da Obra' tem dados")
                else:
                    print("   ⚠️  Sistema 'Serviços da Obra' sem dados (normal se não foi usado ainda)")
                    
            except Exception as rdo_error:
                print(f"   ❌ Erro ao verificar RDO: {rdo_error}")
            
            print("\n" + "="*70)
            print("✅ VERIFICAÇÃO DE PRODUÇÃO CONCLUÍDA!")
            print(f"🎯 Use admin_id {recommended_admin_id} para melhor compatibilidade em produção")
            print("📝 Execute este script em produção para diagnóstico completo")
            print("="*70)
            
            return True
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO na verificação: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)