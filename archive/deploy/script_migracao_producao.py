#!/usr/bin/env python3
"""
Script de Migração para Produção - Sistema de Personalização de Empresa
Garante que todas as configurações funcionem em produção
"""

from models import db, Usuario, ConfiguracaoEmpresa
from app import app

def migrar_configuracoes_producao():
    """Executa migrações necessárias para produção"""
    with app.app_context():
        print("🔄 Iniciando migração de configurações para produção...")
        
        # 1. Corrigir admin_id de usuários que são administradores
        usuarios_admin = Usuario.query.filter(
            Usuario.tipo_usuario.in_(['admin', 'super_admin']),
            Usuario.admin_id.is_(None)
        ).all()
        
        for usuario in usuarios_admin:
            usuario.admin_id = usuario.id
            print(f"✅ Corrigido admin_id do usuário {usuario.email}: {usuario.id}")
        
        # 2. Garantir que existe configuração da empresa para todos os admins
        admins = Usuario.query.filter(
            Usuario.tipo_usuario.in_(['admin', 'super_admin'])
        ).all()
        
        for admin in admins:
            config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
            if not config:
                config = ConfiguracaoEmpresa(
                    admin_id=admin.id,
                    nome_empresa="Estruturas do Vale",
                    cnpj="00.000.000/0001-00",
                    cor_primaria="#007bff",
                    cor_secundaria="#6c757d", 
                    cor_fundo_proposta="#f8f9fa"
                )
                db.session.add(config)
                print(f"✅ Criada configuração da empresa para admin {admin.email}")
        
        # 3. Commit das alterações
        db.session.commit()
        print("✅ Migração concluída com sucesso!")
        
        # 4. Verificar configurações finais
        print("\n📊 Estado final das configurações:")
        configs = ConfiguracaoEmpresa.query.all()
        for config in configs:
            print(f"   Admin ID {config.admin_id}: {config.nome_empresa}")
            print(f"   Cores: {config.cor_primaria} / {config.cor_secundaria}")
            print(f"   Logo: {'✅ Sim' if config.logo_base64 else '❌ Não'}")
            print()

if __name__ == "__main__":
    migrar_configuracoes_producao()