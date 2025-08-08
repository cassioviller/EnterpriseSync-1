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

# CORREÇÃO SQL URGENTE - categoria_id
echo "Aplicando correção SQL urgente..."
python3 -c "
import os
if os.path.exists('/app/views.py'):
    with open('/app/views.py', 'r') as f:
        content = f.read()
    
    # Correção específica para erro categoria_id
    old_query = 'categorias = db.session.query(Servico.categoria).distinct().all()'
    new_query = 'categorias_query = db.session.query(Servico.categoria).distinct().filter(Servico.categoria.isnot(None)).all()'
    
    if old_query in content:
        content = content.replace(old_query, new_query)
        content = content.replace(
            'categorias = [cat[0] for cat in categorias if cat[0]]',
            'categorias = [cat[0] for cat in categorias_query if cat[0]]'
        )
        
        with open('/app/views.py', 'w') as f:
            f.write(content)
        print('Correção SQL categoria_id aplicada!')
    else:
        print('Correção já aplicada ou não necessária')
"

# Correção automática do schema restaurante
echo "🔧 Verificando e corrigindo schema de restaurantes..."
python3 auto_fix_schema.py

# CORREÇÃO ADMIN_ID - Adicionar coluna se não existir
echo "🔧 Verificando coluna admin_id..."
python3 -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Verificar se admin_id existe
        result = db.session.execute(text('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'outro_custo' AND column_name = 'admin_id'
        '''))
        
        if not result.fetchone():
            print('⚡ Adicionando coluna admin_id...')
            db.session.execute(text('ALTER TABLE outro_custo ADD COLUMN admin_id INTEGER'))
            
            # Atualizar registros existentes
            updated = db.session.execute(text('''
                UPDATE outro_custo 
                SET admin_id = (
                    SELECT admin_id 
                    FROM funcionario 
                    WHERE funcionario.id = outro_custo.funcionario_id
                    LIMIT 1
                )
                WHERE admin_id IS NULL
            ''')).rowcount
            
            db.session.commit()
            print(f'✅ Coluna admin_id adicionada - {updated} registros atualizados')
        else:
            print('✅ Coluna admin_id já existe')
    except Exception as e:
        print(f'❌ Erro na correção admin_id: {e}')
"

# CORREÇÃO KPI_ASSOCIADO - Adicionar coluna se não existir
echo "🔧 Verificando coluna kpi_associado..."
python3 -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Verificar se kpi_associado existe
        result = db.session.execute(text('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'outro_custo' AND column_name = 'kpi_associado'
        '''))
        
        if not result.fetchone():
            print('⚡ Adicionando coluna kpi_associado...')
            db.session.execute(text(\"ALTER TABLE outro_custo ADD COLUMN kpi_associado VARCHAR(30) DEFAULT 'outros_custos'\"))
            
            # Atualizar registros existentes
            updated = db.session.execute(text('''
                UPDATE outro_custo 
                SET kpi_associado = 'outros_custos'
                WHERE kpi_associado IS NULL
            ''')).rowcount
            
            db.session.commit()
            print(f'✅ Coluna kpi_associado adicionada - {updated} registros atualizados')
        else:
            print('✅ Coluna kpi_associado já existe')
    except Exception as e:
        print(f'❌ Erro na correção kpi_associado: {e}')
"

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