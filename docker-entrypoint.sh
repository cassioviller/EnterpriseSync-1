#!/bin/bash
# DOCKER ENTRYPOINT - SIGE v8.0
# Script de inicialização para container de produção
# Implementa: 1) Usuário superadmin automático 2) Migrações de banco

set -e

echo "🚀 Iniciando SIGE v8.0 em container Docker..."

# Aguardar banco de dados estar disponível
echo "⏳ Aguardando banco de dados PostgreSQL..."

# Extrair host e porta da DATABASE_URL
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')

# Usar valores padrão se não conseguir extrair
DB_HOST=${DB_HOST:-viajey_sige}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-sige}

echo "   Conectando em: $DB_HOST:$DB_PORT como $DB_USER"

until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
    echo "   Banco ainda não disponível, aguardando..."
    sleep 3
done
echo "✅ Banco de dados conectado!"

# ==========================================
# MELHORIA 2: APLICAR MIGRAÇÕES DE BANCO
# ==========================================
echo "🗄️ Aplicando migrações de banco de dados..."
cd /app

# Configurar variável de ambiente para Flask-Migrate
export FLASK_APP=app.py

# Tentar executar migrações primeiro
echo "   Tentando aplicar migrações existentes..."
flask db upgrade 2>/dev/null && echo "✅ Migrações aplicadas" || {
    echo "   Nenhuma migração encontrada, criando migração inicial..."
    
    # Se não há migrações, criar uma
    if [ ! -f "migrations/versions/"*.py ] 2>/dev/null; then
        echo "   Gerando migração inicial..."
        flask db migrate -m "Initial migration from models" 2>/dev/null || echo "   Aviso: Erro ao gerar migração"
    fi
    
    # Aplicar migrações ou criar tabelas manualmente
    flask db upgrade 2>/dev/null || {
        echo "   Migrações falharam, criando tabelas diretamente..."
        python -c "
from app import app, db
with app.app_context():
    try:
        db.create_all()
        print('✅ Tabelas criadas diretamente')
    except Exception as e:
        print(f'❌ Erro ao criar tabelas: {e}')
        exit(1)
        "
    }
}
echo "✅ Migrações aplicadas/verificadas com sucesso"

# ==========================================
# MELHORIA 1: USUÁRIO SUPERADMIN AUTOMÁTICO
# ==========================================
echo "👤 Verificando/Criando usuário superadmin..."
python -c "
import os
from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

with app.app_context():
    try:
        # Configurações do superadmin via variáveis de ambiente
        admin_email = os.environ.get('SUPERADMIN_EMAIL', 'admin@sige.com')
        admin_password = os.environ.get('SUPERADMIN_PASSWORD', 'admin123')
        admin_nome = os.environ.get('SUPERADMIN_NAME', 'Super Admin')
        admin_username = os.environ.get('SUPERADMIN_USERNAME', 'admin')
        
        # Verificar se já existe um superadmin
        existing_admin = Usuario.query.filter_by(email=admin_email).first()
        
        if not existing_admin:
            # Verificar se já existe algum superadmin
            existing_superadmin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.SUPER_ADMIN).first()
            
            if existing_superadmin:
                print(f'☑️ Já existe um usuário superadmin: {existing_superadmin.email}')
            else:
                # Criar hash da senha
                password_hash = generate_password_hash(admin_password)
                
                # Criar novo superadmin
                new_admin = Usuario(
                    username=admin_username,
                    email=admin_email,
                    nome=admin_nome,
                    password_hash=password_hash,
                    tipo_usuario=TipoUsuario.SUPER_ADMIN,
                    ativo=True,
                    admin_id=None  # Superadmin não tem admin pai
                )
                
                db.session.add(new_admin)
                db.session.commit()
                
                print(f'✅ Usuário superadmin criado com sucesso!')
                print(f'   Email: {admin_email}')
                print(f'   Username: {admin_username}')
                print(f'   Nome: {admin_nome}')
        else:
            print(f'☑️ Usuário superadmin já existe: {admin_email}')
            # Garantir que seja SUPER_ADMIN e esteja ativo
            if existing_admin.tipo_usuario != TipoUsuario.SUPER_ADMIN or not existing_admin.ativo:
                existing_admin.tipo_usuario = TipoUsuario.SUPER_ADMIN
                existing_admin.ativo = True
                db.session.commit()
                print(f'✅ Tipo de usuário atualizado para SUPER_ADMIN')
                
    except Exception as e:
        print(f'❌ Erro ao criar/verificar superadmin: {e}')
        # Não sair com erro fatal aqui, pois pode ser um problema temporário
        import traceback
        traceback.print_exc()
" || echo "⚠️ Problema na criação do superadmin, continuando..."

# Verificar saúde da aplicação
echo "🔍 Verificando aplicação..."
python -c "
from app import app
try:
    with app.app_context():
        print('✅ Aplicação carregada com sucesso')
except Exception as e:
    print(f'❌ Erro na aplicação: {e}')
    exit(1)
"

# Mostrar credenciais de acesso
echo ""
echo "🔑 CREDENCIAIS DE ACESSO SUPERADMIN:"
echo "   Email: ${SUPERADMIN_EMAIL:-admin@sige.com}"
echo "   Senha: ${SUPERADMIN_PASSWORD:-admin123}"
echo ""

# Iniciar aplicação com Gunicorn
echo "🌐 Iniciando servidor Gunicorn na porta ${PORT}..."
exec gunicorn \
    --bind 0.0.0.0:${PORT} \
    --workers 4 \
    --worker-class sync \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    main:app