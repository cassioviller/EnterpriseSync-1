#!/usr/bin/env python3
"""
Script para inicializar e executar migrações do Flask-Migrate
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

import os
import subprocess
import sys
from flask import Flask
from flask_migrate import init, migrate, upgrade
from app import app, db

def run_flask_command(command_args):
    """Executa comando do Flask"""
    env = os.environ.copy()
    env['FLASK_APP'] = 'app.py'
    
    try:
        result = subprocess.run(
            ['flask'] + command_args,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Comando executado: flask {' '.join(command_args)}")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar: flask {' '.join(command_args)}")
        if e.stderr:
            print(f"Erro: {e.stderr}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        return False

def initialize_migrations():
    """Inicializa sistema de migrações"""
    print("🚀 INICIALIZANDO SISTEMA DE MIGRAÇÕES - SIGE v8.0")
    print("=" * 60)
    
    with app.app_context():
        # Verificar se diretório migrations existe
        if not os.path.exists('migrations'):
            print("📁 Inicializando diretório de migrações...")
            if not run_flask_command(['db', 'init']):
                return False
        else:
            print("✅ Diretório de migrações já existe")
        
        # Criar migração inicial
        print("📋 Criando migração inicial...")
        if not run_flask_command(['db', 'migrate', '-m', 'Initial migration']):
            print("⚠️  Migração pode já existir, tentando aplicar...")
        
        # Aplicar migrações
        print("🔄 Aplicando migrações ao banco de dados...")
        if run_flask_command(['db', 'upgrade']):
            print("✅ Migrações aplicadas com sucesso!")
            return True
        else:
            print("❌ Erro ao aplicar migrações")
            return False

def create_production_setup():
    """Cria script de setup para produção"""
    setup_script = '''#!/usr/bin/env python3
"""
Script de setup para produção - SIGE v8.0
Execute este arquivo no container de produção
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time

# Configurar Flask app
os.environ.setdefault('FLASK_APP', 'app.py')

# Importar app e modelos
from app import app, db
from models import *

def setup_production_database():
    """Configura banco de dados para produção"""
    print("🚀 CONFIGURAÇÃO PRODUÇÃO - SIGE v8.0")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Aplicar migrações
            print("🔄 Aplicando migrações...")
            os.system('flask db upgrade')
            
            # Verificar se super admin existe
            super_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
            
            if not super_admin:
                print("👑 Criando Super Admin...")
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
                print("✅ Super Admin criado: admin@sige.com / admin123")
            else:
                print("✅ Super Admin já existe")
            
            # Criar admin demo se não existir
            demo_admin = Usuario.query.filter_by(username='valeverde').first()
            
            if not demo_admin:
                print("🏗️ Criando Admin Demo...")
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
                print("✅ Admin Demo criado: valeverde / admin123")
            else:
                print("✅ Admin Demo já existe")
            
            # Criar dados básicos se necessário
            if Departamento.query.count() == 0:
                print("📋 Criando dados básicos...")
                
                # Departamentos
                departamentos = [
                    Departamento(nome='Administração', descricao='Setor administrativo'),
                    Departamento(nome='Obras', descricao='Execução de obras'),
                    Departamento(nome='Engenharia', descricao='Projetos e planejamento'),
                    Departamento(nome='Manutenção', descricao='Manutenção de equipamentos')
                ]
                for dept in departamentos:
                    db.session.add(dept)
                
                # Funções
                funcoes = [
                    Funcao(nome='Pedreiro', salario_base=2500.0, descricao='Execução de alvenaria'),
                    Funcao(nome='Servente', salario_base=1800.0, descricao='Auxílio geral'),
                    Funcao(nome='Encarregado', salario_base=3500.0, descricao='Supervisão de equipes'),
                    Funcao(nome='Engenheiro', salario_base=8000.0, descricao='Gestão técnica')
                ]
                for funcao in funcoes:
                    db.session.add(funcao)
                
                # Horário padrão
                horario = HorarioTrabalho(
                    nome='Padrão (7h12-17h)',
                    entrada=time(7, 12),
                    saida_almoco=time(12, 0),
                    retorno_almoco=time(13, 0),
                    saida=time(17, 0),
                    dias_semana='1,2,3,4,5',
                    horas_diarias=8.0,
                    valor_hora=15.0
                )
                db.session.add(horario)
                
                db.session.commit()
                print("✅ Dados básicos criados")
            
            print("\\n🎯 SETUP CONCLUÍDO COM SUCESSO!")
            print("=" * 50)
            print("🔑 CREDENCIAIS:")
            print("   Super Admin: admin@sige.com / admin123")
            print("   Admin Demo:  valeverde / admin123")
            print("\\n📊 DADOS:")
            print(f"   • {Usuario.query.count()} usuários")
            print(f"   • {Departamento.query.count()} departamentos")
            print(f"   • {Funcao.query.count()} funções")
            print(f"   • {HorarioTrabalho.query.count()} horários")
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    return True

if __name__ == "__main__":
    setup_production_database()
'''
    
    with open('setup_prod.py', 'w', encoding='utf-8') as f:
        f.write(setup_script)
    
    print("✅ Script de produção criado: setup_prod.py")

def main():
    """Função principal"""
    print("Escolha uma opção:")
    print("1. Inicializar migrações (desenvolvimento)")
    print("2. Criar script de produção")
    print("3. Executar ambos")
    
    choice = input("Digite sua escolha (1-3): ").strip()
    
    if choice in ['1', '3']:
        if not initialize_migrations():
            sys.exit(1)
    
    if choice in ['2', '3']:
        create_production_setup()
    
    print("\\n✅ Processo concluído!")

if __name__ == "__main__":
    main()