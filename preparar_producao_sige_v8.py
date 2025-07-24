#!/usr/bin/env python3
"""
Script DEFINITIVO para preparar SIGE v8.0 em produção
Limpa dados órfãos e configura sistema completo
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time

# Configurar Flask
os.environ.setdefault('FLASK_APP', 'app.py')

from app import app, db
from models import *

def limpar_dados_orfaos():
    """Remove dados órfãos que impedem as migrações"""
    print("🧹 Limpando dados órfãos...")
    
    with app.app_context():
        try:
            # Limpar RDOs com criado_por_id inválido
            rdos_orfaos = db.session.execute(
                db.text("""
                DELETE FROM rdo 
                WHERE criado_por_id NOT IN (SELECT id FROM usuario)
                """)
            ).rowcount
            
            # Limpar outros registros órfãos se necessário
            db.session.commit()
            
            if rdos_orfaos > 0:
                print(f"   ✅ Removidos {rdos_orfaos} RDOs órfãos")
            else:
                print("   ✅ Nenhum dado órfão encontrado")
                
        except Exception as e:
            print(f"   ⚠️ Erro na limpeza: {e}")
            db.session.rollback()

def aplicar_migracoes():
    """Aplica migrações do Flask-Migrate"""
    print("📋 Aplicando migrações...")
    
    try:
        # Tentar aplicar migrações
        result = os.system('cd /app && flask db upgrade')
        if result == 0:
            print("   ✅ Migrações aplicadas com sucesso")
            return True
        else:
            print("   ⚠️ Erro ao aplicar migrações, usando db.create_all()")
            with app.app_context():
                db.create_all()
            print("   ✅ Tabelas criadas diretamente")
            return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False

def configurar_usuarios():
    """Configura usuários administrativos"""
    print("👤 Configurando usuários...")
    
    with app.app_context():
        # Super Admin
        super_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
        
        if not super_admin:
            # Verificar se há um admin para converter
            admin_existente = Usuario.query.filter_by(username='admin').first()
            if admin_existente:
                admin_existente.tipo_usuario = TipoUsuario.SUPER_ADMIN
                admin_existente.ativo = True
                admin_existente.email = 'admin@sige.com'
                db.session.commit()
                print("   ✅ Admin convertido para SUPER_ADMIN")
                super_admin = admin_existente
            else:
                # Criar novo
                super_admin = Usuario(
                    nome='Super Administrador',
                    username='admin',
                    email='admin@sige.com',
                    password_hash=generate_password_hash('admin123'),
                    tipo_usuario=TipoUsuario.SUPER_ADMIN,
                    ativo=True
                )
                db.session.add(super_admin)
                db.session.commit()
                print("   ✅ Super Admin criado")
        else:
            print("   ✅ Super Admin já existe")
        
        # Admin Demo
        demo_admin = Usuario.query.filter_by(username='valeverde').first()
        
        if not demo_admin:
            demo_admin = Usuario(
                nome='Vale Verde Construções',
                username='valeverde',
                email='admin@valeverde.com',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True
            )
            db.session.add(demo_admin)
            db.session.commit()
            print("   ✅ Admin Demo criado")
        else:
            print("   ✅ Admin Demo já existe")
        
        return super_admin, demo_admin

def criar_dados_basicos():
    """Cria dados básicos do sistema"""
    print("📊 Criando dados básicos...")
    
    with app.app_context():
        # Departamentos
        if Departamento.query.count() == 0:
            depts = [
                Departamento(nome='Administração', descricao='Setor administrativo'),
                Departamento(nome='Obras', descricao='Execução de obras'),
                Departamento(nome='Engenharia', descricao='Projetos e planejamento')
            ]
            for d in depts:
                db.session.add(d)
            print("   ✅ Departamentos criados")
        
        # Funções
        if Funcao.query.count() == 0:
            funcs = [
                Funcao(nome='Pedreiro', salario_base=2500.0, descricao='Execução de alvenaria'),
                Funcao(nome='Servente', salario_base=1800.0, descricao='Auxílio geral'),
                Funcao(nome='Encarregado', salario_base=3500.0, descricao='Supervisão de equipes')
            ]
            for f in funcs:
                db.session.add(f)
            print("   ✅ Funções criadas")
        
        # Horário padrão
        if HorarioTrabalho.query.count() == 0:
            horario = HorarioTrabalho(
                nome='Padrão (8h-17h)',
                entrada=time(8, 0),
                saida_almoco=time(12, 0),
                retorno_almoco=time(13, 0),
                saida=time(17, 0),
                dias_semana='1,2,3,4,5',
                horas_diarias=8.0,
                valor_hora=15.0
            )
            db.session.add(horario)
            print("   ✅ Horário padrão criado")
        
        db.session.commit()

def main():
    """Função principal"""
    print("🚀 PREPARAÇÃO COMPLETA - SIGE v8.0 PRODUÇÃO")
    print("=" * 60)
    
    try:
        # 1. Limpar dados órfãos
        limpar_dados_orfaos()
        
        # 2. Aplicar migrações
        if not aplicar_migracoes():
            print("❌ Falha ao aplicar migrações")
            return False
        
        # 3. Configurar usuários
        super_admin, demo_admin = configurar_usuarios()
        
        # 4. Criar dados básicos
        criar_dados_basicos()
        
        # 5. Estatísticas finais
        with app.app_context():
            print("\n🎯 CONFIGURAÇÃO CONCLUÍDA!")
            print("=" * 60)
            print("🔑 CREDENCIAIS:")
            print("   Super Admin: admin@sige.com / admin123")
            print("   Admin Demo:  valeverde / admin123")
            print(f"\n📊 DADOS:")
            print(f"   • Usuários: {Usuario.query.count()}")
            print(f"   • Funcionários: {Funcionario.query.count()}")
            print(f"   • Departamentos: {Departamento.query.count()}")
            print(f"   • Funções: {Funcao.query.count()}")
            print(f"   • Horários: {HorarioTrabalho.query.count()}")
            print(f"   • Obras: {Obra.query.count()}")
            print(f"   • Veículos: {Veiculo.query.count()}")
            
            print(f"\n🌐 SISTEMA OPERACIONAL!")
            print("   Acesse pelo navegador e faça login")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)