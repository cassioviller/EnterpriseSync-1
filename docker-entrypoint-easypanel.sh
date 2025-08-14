#!/bin/bash
# DOCKER ENTRYPOINT EASYPANEL - SIGE v8.0 FINAL
# Versão simplificada e robusta para deploy em produção

set -e

# Configurações de ambiente para EasyPanel
export DATABASE_URL="${DATABASE_URL:-postgresql://sige:sige@viajey_sige:5432/sige}"
export FLASK_APP=app.py
export FLASK_ENV=production
export PYTHONPATH=/app

echo "🚀 SIGE v8.0 - Deploy EasyPanel"
echo "DATABASE_URL: $DATABASE_URL"

# Aguardar PostgreSQL
echo "⏳ Aguardando PostgreSQL..."
for i in {1..30}; do
    if pg_isready -h viajey_sige -p 5432 -U sige >/dev/null 2>&1; then
        echo "✅ PostgreSQL conectado!"
        break
    fi
    echo "Tentativa $i/30..."
    sleep 2
done

cd /app

# Criar tabelas diretamente (método mais confiável)
echo "🗄️ Criando estrutura do banco de dados..."
python3 -c "
import os
import sys
sys.path.insert(0, '/app')

try:
    from app import app, db
    print('✅ App importado com sucesso')
    
    with app.app_context():
        # Dropar e recriar todas as tabelas
        db.drop_all()
        print('🗑️ Tabelas antigas removidas')
        
        db.create_all()
        print('✅ Tabelas criadas com sucesso')
        
        # Verificar tabelas criadas
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f'📊 {len(tables)} tabelas criadas: {tables[:5]}...')
        
except Exception as e:
    print(f'❌ Erro na criação de tabelas: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# Criar usuários administrativos
echo "👤 Criando usuários administrativos..."
python3 -c "
import sys
sys.path.insert(0, '/app')

try:
    from app import app, db
    from models import Usuario, TipoUsuario
    from werkzeug.security import generate_password_hash
    
    with app.app_context():
        # Super Admin
        if not Usuario.query.filter_by(email='admin@sige.com').first():
            admin = Usuario(
                username='admin',
                email='admin@sige.com',
                nome='Super Admin',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.SUPER_ADMIN,
                ativo=True
            )
            db.session.add(admin)
            print('✅ Super Admin criado')
        
        # Admin Demo
        if not Usuario.query.filter_by(username='valeverde').first():
            admin_demo = Usuario(
                username='valeverde',
                email='valeverde@sige.com',
                nome='Vale Verde Admin',
                password_hash=generate_password_hash('admin123'),
                tipo_usuario=TipoUsuario.ADMIN,
                ativo=True
            )
            db.session.add(admin_demo)
            print('✅ Admin Demo criado')
        
        db.session.commit()
        
        # Relatório final
        total = Usuario.query.count()
        print(f'📊 Total de usuários: {total}')
        
except Exception as e:
    print(f'❌ Erro na criação de usuários: {e}')
    import traceback
    traceback.print_exc()
"

echo "✅ SIGE v8.0 PRONTO PARA PRODUÇÃO!"
echo "🔐 CREDENCIAIS:"
echo "   • Super Admin: admin@sige.com / admin123"
echo "   • Admin Demo: valeverde / admin123"

# Iniciar servidor
echo "🚀 Iniciando servidor Gunicorn..."
exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --timeout 120 --access-logfile - main:app