#!/bin/bash
# DOCKER ENTRYPOINT - SIGE v8.0 - TOTALMENTE AUTOMÁTICO
# Script de inicialização COMPLETO para container de produção
# Zero intervenção manual necessária

set -e

# Definir URL padrão do banco se não estiver definida
export DATABASE_URL=${DATABASE_URL:-"postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable"}

echo "🚀 INICIALIZANDO SIGE v8.0 - MODO TOTALMENTE AUTOMÁTICO"
echo "=" * 60
echo "📋 DATABASE_URL: $DATABASE_URL"

# Aguardar banco de dados estar disponível
echo "⏳ Aguardando banco PostgreSQL (viajey_sige:5432)..."

# Tentar conectar várias vezes
for i in {1..30}; do
    if pg_isready -h viajey_sige -p 5432 -U sige; then
        echo "✅ Banco de dados conectado na tentativa $i!"
        break
    fi
    echo "   Tentativa $i/30: Banco não disponível, aguardando 3s..."
    sleep 3
    
    if [ $i -eq 30 ]; then
        echo "❌ Banco não conectou após 30 tentativas, continuando mesmo assim..."
    fi
done

cd /app
export FLASK_APP=app.py

# ==========================================
# ETAPA 1: IMPORTAR MODELOS E CRIAR TABELAS
# ==========================================
echo ""
echo "🗄️ ETAPA 1: CRIANDO ESTRUTURA DO BANCO DE DADOS..."
python -c "
import os
import sys
from app import app, db

print('🔍 Verificando conexão e criando tabelas...')
try:
    with app.app_context():
        # Importar todos os modelos
        import models
        print('✅ Modelos importados com sucesso')
        
        # Criar todas as tabelas
        db.create_all()
        print('✅ Comando db.create_all() executado')
        
        # Verificar tabelas criadas
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f'📊 Total de tabelas criadas: {len(tables)}')
        
        if len(tables) > 0:
            print('📋 Tabelas criadas:')
            for i, table in enumerate(sorted(tables), 1):
                print(f'   {i:2d}. {table}')
            print('✅ BANCO DE DADOS CONFIGURADO COM SUCESSO!')
        else:
            print('❌ ERRO: Nenhuma tabela foi criada!')
            sys.exit(1)
            
except Exception as e:
    print(f'❌ ERRO CRÍTICO na criação do banco: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ FALHA na criação do banco de dados. Parando container."
    exit 1
fi

# ==========================================
# ETAPA 2: CRIAR USUÁRIOS ADMINISTRATIVOS
# ==========================================
echo ""
echo "👤 ETAPA 2: CRIANDO USUÁRIOS ADMINISTRATIVOS..."
python -c "
import sys
from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

try:
    with app.app_context():
        print('🔐 Criando usuários padrão do sistema...')
        
        # 1. SUPER ADMIN
        super_admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
        if not super_admin:
            super_admin = Usuario(
                username='admin',
                email='admin@sige.com',
                nome='Super Administrador',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.SUPER_ADMIN,
                ativo=True,
                admin_id=None
            )
            db.session.add(super_admin)
            print('✅ Super Admin criado: admin@sige.com / admin123')
        else:
            print('✅ Super Admin já existe: admin@sige.com')
        
        # 2. ADMIN DEMO
        demo_admin = Usuario.query.filter_by(username='valeverde').first()
        if not demo_admin:
            demo_admin = Usuario(
                username='valeverde',
                email='admin@valeverde.com',
                nome='Vale Verde Construções',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True,
                admin_id=None
            )
            db.session.add(demo_admin)
            print('✅ Admin Demo criado: valeverde / admin123')
        else:
            print('✅ Admin Demo já existe: valeverde')
        
        # Salvar no banco
        db.session.commit()
        
        # Verificar total de usuários
        total_users = Usuario.query.count()
        print(f'📊 Total de usuários no sistema: {total_users}')
        print('✅ USUÁRIOS ADMINISTRATIVOS CONFIGURADOS!')
        
except Exception as e:
    print(f'❌ ERRO na criação de usuários: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ FALHA na criação de usuários. Parando container."
    exit 1
fi

# ==========================================
# ETAPA 3: VERIFICAÇÃO FINAL DO SISTEMA
# ==========================================
echo ""
echo "🔍 ETAPA 3: VERIFICAÇÃO FINAL DO SISTEMA..."
python -c "
from app import app, db
from models import Usuario, TipoUsuario

try:
    with app.app_context():
        # Contar tabelas
        inspector = db.inspect(db.engine)
        total_tables = len(inspector.get_table_names())
        
        # Contar usuários por tipo
        super_admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).count()
        admins = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).count()
        funcionarios = Usuario.query.filter_by(tipo_usuario=TipoUsuario.FUNCIONARIO).count()
        
        print('📊 RELATÓRIO FINAL DO SISTEMA:')
        print(f'   • Tabelas no banco: {total_tables}')
        print(f'   • Super Admins: {super_admins}')
        print(f'   • Admins: {admins}')
        print(f'   • Funcionários: {funcionarios}')
        print('✅ SISTEMA TOTALMENTE OPERACIONAL!')
        
except Exception as e:
    print(f'❌ ERRO na verificação: {e}')
"

# ==========================================
# MOSTRAR CREDENCIAIS DE ACESSO
# ==========================================
echo ""
echo "🎯 SISTEMA SIGE v8.0 ATIVADO COM SUCESSO!"
echo "=" * 60
echo "🔐 CREDENCIAIS DE ACESSO:"
echo ""
echo "   🔹 SUPER ADMIN (Gerenciar Administradores):"
echo "      Email: admin@sige.com"
echo "      Senha: admin123"
echo ""
echo "   🔹 ADMIN DEMO (Sistema Completo):"
echo "      Login: valeverde"
echo "      Senha: admin123"
echo ""
echo "🌐 Acesse sua URL do EasyPanel e faça login!"
echo "=" * 60

# ==========================================
# INICIAR SERVIDOR GUNICORN
# ==========================================
echo "🚀 Iniciando servidor Gunicorn na porta ${PORT:-5000}..."
exec gunicorn \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers 2 \
    --worker-class sync \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --preload \
    main:app