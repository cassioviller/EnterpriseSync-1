#!/bin/bash
# DOCKER ENTRYPOINT - SIGE v8.0 SIMPLIFICADO
# Correção para problemas de SQLAlchemy

set -e

# URL do banco PostgreSQL
export DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige"
export FLASK_APP=app.py

echo "🚀 SIGE v8.0 - Inicializando..."
echo "DATABASE_URL: $DATABASE_URL"

# Aguardar PostgreSQL
echo "Aguardando PostgreSQL..."
for i in {1..15}; do
    if pg_isready -h viajey_sige -p 5432 -U sige >/dev/null 2>&1; then
        echo "PostgreSQL conectado!"
        break
    fi
    sleep 2
done

cd /app

# Tentar usar migrações primeiro
echo "Aplicando migrações..."
flask db upgrade 2>/dev/null || {
    echo "Migrações falharam, criando tabelas diretamente..."
    python3 -c "
from app import app, db
import models
with app.app_context():
    try:
        db.create_all()
        print('Tabelas criadas com sucesso!')
    except Exception as e:
        print(f'Erro ao criar tabelas: {e}')
        exit(1)
"
}

# Criar usuário admin
echo "Criando usuários..."
python3 -c "
from app import app, db
from models import Usuario, TipoUsuario
from werkzeug.security import generate_password_hash

with app.app_context():
    try:
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
            db.session.commit()
            print('Admin criado: admin@sige.com / admin123')
        else:
            print('Admin já existe')
    except Exception as e:
        print(f'Erro ao criar admin: {e}')
"

echo "SIGE v8.0 pronto!"
echo "Acesso: admin@sige.com / admin123"

# Iniciar servidor
exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --timeout 120 --access-logfile - main:app