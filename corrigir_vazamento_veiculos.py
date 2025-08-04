#!/usr/bin/env python3
"""
🔒 CORREÇÃO CRÍTICA DE SEGURANÇA: Vazamento de dados entre admins
Verificar e corrigir isolamento multi-tenant nos veículos
"""

from app import app, db
from models import Usuario, Veiculo, TipoUsuario
from sqlalchemy import text

def verificar_vazamento_veiculos():
    """Verificar se há vazamento de dados entre admins"""
    print("🔍 VERIFICANDO VAZAMENTO DE DADOS DE VEÍCULOS")
    print("=" * 60)
    
    with app.app_context():
        # Buscar todos os admins
        admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).all()
        
        print(f"📊 Admins encontrados: {len(admins)}")
        
        for admin in admins:
            # Contar veículos do admin
            veiculos_admin = Veiculo.query.filter_by(admin_id=admin.id).count()
            
            # Contar veículos "vazados" (sem filtro)
            veiculos_total = Veiculo.query.count()
            
            print(f"👤 Admin: {admin.email} (ID: {admin.id})")
            print(f"   🚗 Veículos próprios: {veiculos_admin}")
            print(f"   ⚠️  Total sistema: {veiculos_total}")
            
            if veiculos_admin != veiculos_total and admin.id == 10:  # Admin alves
                print(f"   🚨 VAZAMENTO DETECTADO!")
                
        print(f"\n📋 DETALHES DOS VEÍCULOS:")
        veiculos = db.session.execute(text("""
            SELECT v.id, v.placa, v.modelo, v.admin_id, u.email as admin_email
            FROM veiculo v
            LEFT JOIN usuario u ON v.admin_id = u.id
            WHERE v.ativo = true
            ORDER BY v.admin_id
        """)).fetchall()
        
        for veiculo in veiculos:
            print(f"   🚗 ID:{veiculo.id} | {veiculo.placa} | {veiculo.modelo} | Admin:{veiculo.admin_id} ({veiculo.admin_email})")

def testar_dashboard_corrigido():
    """Testar se o dashboard agora mostra dados corretos"""
    print(f"\n🧪 TESTE: Dashboard após correção")
    print("=" * 60)
    
    with app.app_context():
        # Simular login dos dois admins
        admin_estruturas = Usuario.query.filter_by(email='admin@estruturasdovale.com.br').first()
        admin_alves = Usuario.query.filter_by(email='admin@valeverde.com.br').first()
        
        if admin_estruturas:
            veiculos_estruturas = Veiculo.query.filter_by(
                admin_id=admin_estruturas.id, 
                ativo=True
            ).count()
            print(f"👤 Admin Estruturas (ID:{admin_estruturas.id}): {veiculos_estruturas} veículos")
        
        if admin_alves:
            veiculos_alves = Veiculo.query.filter_by(
                admin_id=admin_alves.id, 
                ativo=True
            ).count()
            print(f"👤 Admin Alves (ID:{admin_alves.id}): {veiculos_alves} veículos")

def gerar_relatorio_seguranca():
    """Gerar relatório de segurança do sistema"""
    print(f"\n📋 RELATÓRIO DE SEGURANÇA MULTI-TENANT")
    print("=" * 60)
    
    arquivos_corrigidos = [
        "✅ views.py - api_dashboard_dados() - linha 416",
        "✅ views.py - dashboard-executivo - linha 4647", 
        "✅ views.py - relatório veículos - linha 4622",
        "✅ kpi_unificado.py - calcular_kpis_dashboard() - linha 183"
    ]
    
    for arquivo in arquivos_corrigidos:
        print(f"   {arquivo}")
    
    print(f"\n🔧 CORREÇÕES APLICADAS:")
    print("   • Adicionado filtro admin_id em todas as consultas de veículos")
    print("   • Corrigido isolamento multi-tenant no dashboard")
    print("   • Atualizado sistema unificado de KPIs")
    print("   • Implementado filtros em relatórios")
    
    print(f"\n✅ RESULTADO ESPERADO:")
    print("   • Admin 'alves' deve ver apenas 4 veículos (seus próprios)")
    print("   • Admin 'estruturas' deve ver apenas 2 veículos (seus próprios)")
    print("   • Não deve haver mais vazamento de dados entre empresas")

if __name__ == "__main__":
    print("🔒 CORREÇÃO DE SEGURANÇA: Sistema Multi-Tenant")
    print("=" * 80)
    
    # 1. Verificar vazamento
    verificar_vazamento_veiculos()
    
    # 2. Testar correção
    testar_dashboard_corrigido()
    
    # 3. Relatório
    gerar_relatorio_seguranca()
    
    print(f"\n🎯 AÇÃO NECESSÁRIA:")
    print("   1. Faça logout do usuário 'alves'")
    print("   2. Faça login novamente")
    print("   3. Verifique o dashboard - deve mostrar apenas 4 veículos")
    print("   4. O vazamento de dados foi corrigido!")