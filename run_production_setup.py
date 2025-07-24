#!/usr/bin/env python3
"""
Script SIMPLIFICADO para configurar SIGE v8.0 em produção
Execute este arquivo no container EasyPanel para ativar o sistema
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time

# Configurar Flask
os.environ.setdefault('FLASK_APP', 'app.py')

# Importar aplicação
from app import app, db
from models import *

def main():
    """Setup completo em uma função"""
    print("🚀 ATIVANDO SIGE v8.0 - CONFIGURAÇÃO RÁPIDA")
    print("=" * 55)
    
    with app.app_context():
        try:
            # 1. Criar/Verificar tabelas
            print("📋 1. Verificando estrutura do banco...")
            db.create_all()
            print("   ✅ Tabelas verificadas/criadas")
            
            # 2. Super Admin
            print("👑 2. Configurando Super Admin...")
            super_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
            
            if not super_admin:
                # Verificar se usuário 'admin' existe e converter
                admin_user = Usuario.query.filter_by(username='admin').first()
                if admin_user:
                    admin_user.tipo_usuario = TipoUsuario.SUPER_ADMIN
                    admin_user.ativo = True
                    db.session.commit()
                    print(f"   ✅ Usuário admin convertido para SUPER_ADMIN")
                    super_admin = admin_user
                else:
                    # Criar novo super admin
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
                    print("   ✅ Super Admin criado: admin@sige.com / admin123")
            else:
                print("   ✅ Super Admin já existe")
            
            # 3. Admin Demo
            print("🏗️ 3. Configurando Admin Demo...")
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
                print("   ✅ Admin Demo criado: valeverde / admin123")
            else:
                print("   ✅ Admin Demo já existe")
            
            # 4. Dados Básicos
            if Departamento.query.count() == 0:
                print("📊 4. Criando dados básicos...")
                
                # Departamentos
                depts = [
                    Departamento(nome='Administração', descricao='Setor administrativo'),
                    Departamento(nome='Obras', descricao='Execução de obras'),
                    Departamento(nome='Engenharia', descricao='Projetos e planejamento')
                ]
                for d in depts:
                    db.session.add(d)
                
                # Funções
                funcs = [
                    Funcao(nome='Pedreiro', salario_base=2500.0, descricao='Execução de alvenaria'),
                    Funcao(nome='Servente', salario_base=1800.0, descricao='Auxílio geral'),
                    Funcao(nome='Encarregado', salario_base=3500.0, descricao='Supervisão de equipes')
                ]
                for f in funcs:
                    db.session.add(f)
                
                # Horário padrão
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
                
                db.session.commit()
                print("   ✅ Dados básicos criados")
            else:
                print("📊 4. Dados básicos já existem")
            
            # 5. Estatísticas finais
            print("\n🎯 CONFIGURAÇÃO CONCLUÍDA!")
            print("=" * 55)
            print("🔑 CREDENCIAIS DE ACESSO:")
            print("   Super Admin: admin@sige.com / admin123")
            print("   Admin Demo:  valeverde / admin123")
            print(f"\n📊 DADOS NO SISTEMA:")
            print(f"   • Usuários: {Usuario.query.count()}")
            print(f"   • Funcionários: {Funcionario.query.count()}")
            print(f"   • Departamentos: {Departamento.query.count()}")
            print(f"   • Funções: {Funcao.query.count()}")
            print(f"   • Horários: {HorarioTrabalho.query.count()}")
            print(f"   • Obras: {Obra.query.count()}")
            print(f"   • Veículos: {Veiculo.query.count()}")
            
            print(f"\n🌐 SISTEMA PRONTO PARA USO!")
            print("   Acesse sua URL do EasyPanel e faça login")
            
            return True
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)