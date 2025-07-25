#!/bin/bash
set -e

echo "🚀 Iniciando SIGE v8.0 com Correção Automática..."

# Função para aguardar banco de dados
wait_for_db() {
    echo "⏳ Aguardando banco de dados..."
    until python -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.close()
    print('✅ Banco de dados conectado!')
except:
    exit(1)
" 2>/dev/null; do
        echo "   Tentando conectar ao banco..."
        sleep 2
    done
}

# Função para corrigir schema da tabela restaurante automaticamente
fix_restaurante_schema() {
    echo "🔧 CORREÇÃO AUTOMÁTICA: Verificando schema da tabela restaurante..."
    
    python -c "
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    # Conectar ao banco
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Verificar se tabela restaurante existe
    cursor.execute(\"\"\"
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'restaurante'
        );
    \"\"\")
    
    if not cursor.fetchone()[0]:
        print('ℹ️ Tabela restaurante não existe ainda, será criada pelo SQLAlchemy')
        cursor.close()
        conn.close()
        exit(0)
    
    print('🔍 Tabela restaurante encontrada, verificando colunas...')
    
    # Verificar colunas existentes
    cursor.execute(\"\"\"
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'restaurante'
    \"\"\")
    colunas_existentes = [row[0] for row in cursor.fetchall()]
    print(f'   Colunas atuais: {colunas_existentes}')
    
    # Colunas necessárias identificadas pelo diagnóstico
    colunas_necessarias = {
        'responsavel': 'VARCHAR(100)',
        'preco_almoco': 'DECIMAL(10,2) DEFAULT 0.00',
        'preco_jantar': 'DECIMAL(10,2) DEFAULT 0.00', 
        'preco_lanche': 'DECIMAL(10,2) DEFAULT 0.00',
        'admin_id': 'INTEGER'
    }
    
    # Identificar e adicionar colunas faltantes
    colunas_adicionadas = 0
    for col_nome, col_tipo in colunas_necessarias.items():
        if col_nome not in colunas_existentes:
            sql = f'ALTER TABLE restaurante ADD COLUMN {col_nome} {col_tipo};'
            cursor.execute(sql)
            print(f'   ✅ Coluna {col_nome} adicionada automaticamente')
            colunas_adicionadas += 1
    
    # Remover coluna duplicada se existir (problema identificado)
    if 'contato_responsavel' in colunas_existentes:
        cursor.execute('ALTER TABLE restaurante DROP COLUMN contato_responsavel;')
        print('   ✅ Coluna duplicada contato_responsavel removida automaticamente')
    
    # Configurar admin_id para restaurantes existentes
    cursor.execute(\"\"\"
        UPDATE restaurante 
        SET admin_id = 1 
        WHERE admin_id IS NULL OR admin_id = 0;
    \"\"\")
    affected = cursor.rowcount
    if affected > 0:
        print(f'   ✅ {affected} restaurantes atualizados com admin_id')
    
    if colunas_adicionadas > 0:
        print(f'🎉 CORREÇÃO AUTOMÁTICA CONCLUÍDA: {colunas_adicionadas} colunas adicionadas')
        print('   Agora o módulo de restaurantes funcionará corretamente!')
    else:
        print('✅ Schema restaurante já está correto')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'⚠️ Erro na correção automática: {e}')
    print('   O sistema tentará funcionar normalmente')
"
}

# Função para criar estrutura básica
setup_database() {
    echo "🗄️ Configurando banco de dados..."
    
    # Criar tabelas básicas
    python -c "
from app import app, db
import models
with app.app_context():
    try:
        db.create_all()
        print('✅ Tabelas criadas/verificadas')
    except Exception as e:
        print(f'❌ Erro ao criar tabelas: {e}')
        exit(1)
"

    # Corrigir schema da tabela restaurante após criação
    fix_restaurante_schema

    # Criar usuários administrativos
    python -c "
from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

with app.app_context():
    try:
        # Super Admin
        if not Usuario.query.filter_by(email='admin@sige.com').first():
            super_admin = Usuario(
                email='admin@sige.com',
                nome='Super Administrador',
                tipo_usuario=TipoUsuario.SUPER_ADMIN,
                ativo=True
            )
            super_admin.password_hash = generate_password_hash('admin123')
            db.session.add(super_admin)
            print('✅ Super Admin criado: admin@sige.com / admin123')
        
        # Admin Demo Vale Verde
        if not Usuario.query.filter_by(email='valeverde@admin.com').first():
            admin_demo = Usuario(
                email='valeverde@admin.com',
                nome='Vale Verde Admin',
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True
            )
            admin_demo.password_hash = generate_password_hash('admin123')
            db.session.add(admin_demo)
            print('✅ Admin Demo criado: valeverde@admin.com / admin123')
        
        db.session.commit()
        print('✅ Usuários administrativos configurados')
        
    except Exception as e:
        print(f'❌ Erro ao criar usuários: {e}')
        db.session.rollback()
"
}

# Função para verificar saúde do sistema
health_check() {
    echo "🔍 Verificação de saúde do sistema..."
    
    python -c "
from app import app, db
from models import Usuario
import sys

with app.app_context():
    try:
        # Testar conexão e contar usuários
        total_usuarios = Usuario.query.count()
        print(f'✅ Sistema operacional: {total_usuarios} usuários no banco')
        
        if total_usuarios == 0:
            print('⚠️ Nenhum usuário encontrado, executando setup...')
            sys.exit(1)
            
    except Exception as e:
        print(f'❌ Erro na verificação: {e}')
        sys.exit(1)
"
}

# Fluxo principal
main() {
    wait_for_db
    
    # Tentar verificação de saúde primeiro
    if ! health_check; then
        echo "🔧 Sistema requer configuração inicial..."
        setup_database
        health_check
    else
        echo "🔧 Sistema já existe, verificando correções necessárias..."
        # Se sistema já existe, verificar e corrigir schema automaticamente
        fix_restaurante_schema
    fi
    
    echo "🎉 SIGE v8.0 pronto para uso!"
    echo "   Credenciais:"
    echo "   Super Admin: admin@sige.com / admin123"
    echo "   Admin Demo: valeverde@admin.com / admin123"
    echo "   📍 Correção automática de schema ativada!"
    echo ""
}

# Executar configuração
main

# Iniciar aplicação
echo "🚀 Iniciando servidor Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app